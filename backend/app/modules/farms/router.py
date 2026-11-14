"""Bayaman's HTTP API; established endpoint modules re-export these routers."""

import hashlib
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.core.errors import ProblemError
from app.db.session import get_db
from app.modules.farms import crud, requests, schemas, service


def demo_farmer(role: Annotated[str, Header(alias="X-Demo-Role")] = "farmer") -> None:
    if not get_settings().demo_mode:
        raise ProblemError(503, "Service Unavailable", "Для этого модуля требуется DEMO_MODE=true")
    if role != "farmer":
        raise ProblemError(403, "Forbidden", "Профиль и финансы доступны в режиме фермера")


router = APIRouter(tags=["farms"], dependencies=[Depends(demo_farmer)])
catalog_router = APIRouter(tags=["catalog"], dependencies=[Depends(demo_farmer)])
DB = Annotated[Session, Depends(get_db)]
Key = Annotated[str | None, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def _write(db: Session, operation: Callable, *, scope: str | None = None,
           key: str | None = None, payload: schemas.Contract | None = None):
    """Commit validated responses; replay POSTs atomically using the audit journal."""
    try:
        digest = None
        if key and scope and payload:
            digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
            lock = int.from_bytes(hashlib.sha256(f"{scope}:{key}".encode()).digest()[:8],
                                  "big", signed=True)
            db.execute(select(func.pg_advisory_xact_lock(lock)))
            receipt = db.scalar(select(models.AuditLog).where(
                models.AuditLog.action == "idempotency",
                models.AuditLog.diff["scope"].astext == scope,
                models.AuditLog.diff["key"].astext == key,
            ))
            if receipt:
                if receipt.diff["hash"] != digest:
                    raise ProblemError(409, "Conflict", "Idempotency-Key уже использован с другим телом")
                result = receipt.diff["response"]
                db.commit()
                return result
        result = operation()
        response = jsonable_encoder(
            result.model_dump(round_trip=True) if isinstance(result, schemas.Contract) else result
        )
        if digest:
            db.add(models.AuditLog(entity="farms_api", entity_id=str(result.id),
                                  action="idempotency", diff={
                                      "scope": scope, "key": key, "hash": digest,
                                      "response": response,
                                  }))
        db.commit()
        return response
    except IntegrityError as exc:
        db.rollback()
        raise ProblemError(409, "Conflict", "Запись используется другими данными или конфликтует с ними") from exc
    except ValidationError as exc:
        db.rollback()
        raise ProblemError(422, "Unprocessable Entity", "Некорректные данные поля", errors=[
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/farms")
def list_farms(db: DB, limit: Annotated[int, Query(ge=1, le=100)] = 50,
               cursor: UUID | None = None):
    statement = select(models.Farm.id).order_by(models.Farm.id).limit(limit + 1)
    if cursor:
        statement = statement.where(models.Farm.id > cursor)
    ids = list(db.scalars(statement))
    return {"items": [service.get_farm(id_, session=db) for id_ in ids[:limit]],
            "next_cursor": str(ids[limit - 1]) if len(ids) > limit else None}


@router.post("/farms", status_code=201, response_model=schemas.Farm)
def create_farm(payload: requests.FarmCreate, db: DB, idempotency_key: Key = None):
    return _write(db, lambda: crud.create_farm(db, payload), scope="farms",
                  key=idempotency_key, payload=payload)


@router.get("/farms/{farm_id}", response_model=schemas.Farm)
def get_farm(farm_id: UUID, db: DB):
    return service.get_farm(farm_id, session=db)


@router.patch("/farms/{farm_id}", response_model=schemas.Farm)
def patch_farm(farm_id: UUID, payload: requests.FarmPatch, db: DB):
    return _write(db, lambda: crud.update_farm(db, farm_id, payload))


@router.delete("/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: UUID, db: DB):
    _write(db, lambda: crud.remove_farm(db, farm_id))
    return Response(status_code=204)


@router.get("/farms/{farm_id}/fields")
def list_fields(farm_id: UUID, db: DB):
    farm = service.get_farm(farm_id, session=db)
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": str(field.id), "geometry": field.geometry or field.location,
         "properties": field.model_dump(mode="json", exclude={"geometry"})}
        for field in farm.fields
    ]}


@router.get("/farms/{farm_id}/fields/{field_id}", response_model=schemas.Field)
def get_field(farm_id: UUID, field_id: UUID, db: DB):
    crud.field_row(db, farm_id, field_id)
    return next(f for f in service.get_farm(farm_id, session=db).fields if f.id == field_id)


@router.post("/farms/{farm_id}/fields", status_code=201, response_model=schemas.Field)
def create_field(farm_id: UUID, payload: requests.FieldCreate, db: DB, idempotency_key: Key = None):
    return _write(db, lambda: crud.create_field(db, farm_id, payload), scope=f"fields/{farm_id}",
                  key=idempotency_key, payload=payload)


@router.patch("/farms/{farm_id}/fields/{field_id}", response_model=schemas.Field)
def patch_field(farm_id: UUID, field_id: UUID, payload: requests.FieldPatch, db: DB):
    return _write(db, lambda: crud.update_field(db, farm_id, field_id, payload))


@router.delete("/farms/{farm_id}/fields/{field_id}", status_code=204)
def delete_field(farm_id: UUID, field_id: UUID, db: DB):
    _write(db, lambda: crud.remove_field(db, farm_id, field_id))
    return Response(status_code=204)


@catalog_router.get("/catalog/crops", response_model=list[schemas.Crop])
def list_crops(db: DB):
    return [service.get_crop(id_, session=db) for id_ in db.scalars(
        select(models.Crop.id).order_by(models.Crop.code)
    )]


@catalog_router.get("/catalog/rotations", response_model=list[schemas.Rotation])
def list_rotations(db: DB, zone: Annotated[str | None, Query(max_length=64)] = None):
    statement = select(models.RotationTemplate).order_by(models.RotationTemplate.name)
    if zone:
        statement = statement.where(models.RotationTemplate.zone_id == zone)
    return [schemas.Rotation.model_validate(row) for row in db.scalars(statement)]


@catalog_router.get("/scenarios/presets", response_model=list[schemas.Scenario])
def scenario_presets(db: DB):
    return service.list_scenario_presets(session=db)
