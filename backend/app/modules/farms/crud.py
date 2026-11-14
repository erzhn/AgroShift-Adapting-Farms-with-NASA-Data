"""Transactional farm writes and geospatial validation. The router owns commits."""

import json
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from geoalchemy2 import Geography
from sqlalchemy import cast, delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.core.errors import NotFoundError, ProblemError
from app.modules.farms import requests as inputs
from app.modules.farms import schemas, service


def invalid(detail: str) -> None:
    raise ProblemError(422, "Unprocessable Entity", detail)


def _source(value: object, *, derived: bool = False) -> dict:
    return {
        "source_type": "unknown" if value is None else "model" if derived else "user_estimate",
        "confidence": 0 if value is None else 0.5,
        "note": "Площадь контура WGS84, PostGIS geography" if derived else "Ввод пользователя",
        "as_of": datetime.now(ZoneInfo("Asia/Bishkek")).date().isoformat(),
    }


def audit(db: Session, entity: str, entity_id: UUID, action: str, changes: dict) -> None:
    db.add(models.AuditLog(entity=entity, entity_id=str(entity_id), action=action,
                           diff=jsonable_encoder(changes)))


def farm_row(db: Session, farm_id: UUID) -> models.Farm:
    # Serialize changes of a farm, including field overlap checks and season upserts.
    farm = db.scalar(select(models.Farm).where(models.Farm.id == farm_id).with_for_update())
    if farm is None:
        raise NotFoundError("Farm", farm_id)
    return farm


def field_row(db: Session, farm_id: UUID, field_id: UUID) -> models.Field:
    field = db.scalar(select(models.Field).where(
        models.Field.id == field_id, models.Field.farm_id == farm_id
    ))
    if field is None:
        raise NotFoundError("Field", field_id)
    return field


def _assets(db: Session, farm: models.Farm, values: dict) -> None:
    if "cash_som" in values:
        balance = values.pop("cash_som")
        accounts = list(db.scalars(select(models.CashAccount).where(
            models.CashAccount.farm_id == farm.id
        )))
        if len(accounts) > 1:
            raise ProblemError(409, "Conflict", "У хозяйства несколько счетов: изменяйте их отдельно")
        if balance is None:
            for account in accounts:
                db.delete(account)
        else:
            account = accounts[0] if accounts else models.CashAccount(
                id=uuid4(), farm_id=farm.id, name="Основной"
            )
            account.balance_som = balance
            account.as_of = datetime.now(ZoneInfo("Asia/Bishkek")).date()
            account.provenance = {"balance_som": _source(balance), "as_of": _source(account.as_of)}
            db.add(account)
    if "cow_count" in values:
        count = values.pop("cow_count")
        herds = list(db.scalars(select(models.Herd).where(
            models.Herd.farm_id == farm.id, models.Herd.species == "cow",
            models.Herd.purpose == "milk"
        )))
        if len(herds) > 1:
            raise ProblemError(409, "Conflict", "У хозяйства несколько стад: изменяйте их отдельно")
        if count is None:
            for herd in herds:
                db.delete(herd)
        else:
            herd = herds[0] if herds else models.Herd(
                id=uuid4(), farm_id=farm.id, species="cow", purpose="milk"
            )
            herd.head_count = count
            herd.provenance = {**(herd.provenance or {}), "head_count": _source(count)}
            db.add(herd)


def create_farm(db: Session, payload: inputs.FarmCreate) -> schemas.Farm:
    values = payload.model_dump()
    assets = {key: values.pop(key) for key in ("cash_som", "cow_count")}
    workspace = models.Workspace(id=uuid4(), name=payload.name, type="farm", region_id="chuy")
    db.add(workspace)
    db.flush()
    farm = models.Farm(id=uuid4(), workspace_id=workspace.id, **values,
                      provenance={name: _source(values[name]) for name in (
                          "family_reserve_som", "labour_hours_month"
                      )})
    db.add(farm)
    db.flush()
    _assets(db, farm, assets)
    audit(db, "farm", farm.id, "create", payload.model_dump())
    db.flush()
    db.expire_all()
    return service.get_farm(farm.id, session=db)


def update_farm(db: Session, farm_id: UUID, payload: inputs.FarmPatch) -> schemas.Farm:
    farm = farm_row(db, farm_id)
    values = payload.model_dump(exclude_unset=True)
    audit(db, "farm", farm.id, "update", values)
    _assets(db, farm, values)
    for key, value in values.items():
        setattr(farm, key, value)
        if key in {"family_reserve_som", "labour_hours_month"}:
            farm.provenance = {**farm.provenance, key: _source(value)}
    if "name" in values:
        db.get(models.Workspace, farm.workspace_id).name = farm.name
    db.flush()
    db.expire_all()
    return service.get_farm(farm.id, session=db)


def remove_farm(db: Session, farm_id: UUID) -> None:
    farm = farm_row(db, farm_id)
    audit(db, "farm", farm_id, "delete", {"name": farm.name})
    # PostgreSQL cascades the workspace and all farm-owned entities atomically.
    # Cross-module references without CASCADE intentionally protect referenced farms.
    db.execute(delete(models.Workspace).where(models.Workspace.id == farm.workspace_id))
    db.flush()


def _geo(geometry: dict):
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)


def _validated_field(db: Session, farm_id: UUID, values: dict, field_id: UUID | None) -> dict:
    data = inputs.FieldCreate.model_validate(values)
    result = data.model_dump(exclude={"season"})
    geometry = result["geometry"]
    if data.canal_id and db.get(models.Canal, data.canal_id) is None:
        raise NotFoundError("Canal", data.canal_id)
    if geometry:
        shape = _geo(geometry)
        if not db.scalar(select(func.ST_IsValid(shape))):
            invalid("Контур пересекает сам себя или содержит некорректные кольца")
        area = db.scalar(select(func.ST_Area(cast(shape, Geography)))) / 10000
        if area <= 0 or area > 1000000:
            invalid("Площадь контура вне допустимого диапазона")
        if data.area_ha is not None and abs(data.area_ha - area) > area * 0.001:
            invalid("Указанная площадь отличается от площади контура более чем на 0,1%")
        result["area_ha"] = area
        if data.location:
            if not db.scalar(select(func.ST_Covers(shape, _geo(result["location"])))):
                invalid("Точка поля должна находиться внутри контура")
        else:
            result["location"] = json.loads(db.scalar(select(
                func.ST_AsGeoJSON(func.ST_PointOnSurface(shape))
            )))
        overlap = select(models.Field.id).where(
            models.Field.farm_id == farm_id,
            func.ST_Intersects(models.Field.geometry, shape),
            func.ST_Area(cast(func.ST_Intersection(models.Field.geometry, shape), Geography)) > 1,
        )
        if field_id:
            overlap = overlap.where(models.Field.id != field_id)
        if db.scalar(overlap.limit(1)):
            invalid("Контур пересекается с другим полем хозяйства")
    return result


def _season(db: Session, field: models.Field, data: inputs.SeasonWrite) -> None:
    variant = db.get(models.CropVariant, data.crop_variant_id)
    if variant is None:
        raise NotFoundError("CropVariant", data.crop_variant_id)
    orchard = db.scalar(select(models.Orchard).where(models.Orchard.field_id == field.id))
    if orchard and db.get(models.Crop, variant.crop_id).code != orchard.species:
        invalid("Поле занято садом: смена культуры требует решения о выкорчёвке")
    season = db.scalar(select(models.CropSeason).where(
        models.CropSeason.field_id == field.id, models.CropSeason.year == data.year,
        models.CropSeason.is_main.is_(True),
    ))
    if season is None:
        season = models.CropSeason(id=uuid4(), field_id=field.id, is_main=True)
    values = data.model_dump()
    for key, value in values.items():
        setattr(season, key, value)
    season.provenance = {key: _source(value) for key, value in values.items()
                         if key != "crop_variant_id"}
    db.add(season)


def create_field(db: Session, farm_id: UUID, payload: inputs.FieldCreate) -> schemas.Field:
    farm_row(db, farm_id)
    values = _validated_field(db, farm_id, payload.model_dump(), None)
    field = models.Field(id=uuid4(), farm_id=farm_id)
    _apply_field(field, values)
    db.add(field)
    db.flush()
    if payload.season:
        _season(db, field, payload.season)
    audit(db, "field", field.id, "create", payload.model_dump())
    db.flush()
    db.expire_all()
    return next(f for f in service.get_farm(farm_id, session=db).fields if f.id == field.id)


def _apply_field(field: models.Field, values: dict) -> None:
    for key, value in values.items():
        setattr(field, key, _geo(value) if key in {"geometry", "location"} and value else value)
        if key not in {"canal_id", "name", "irrigation_method"}:
            field.provenance = {**(field.provenance or {}), key: _source(
                value, derived=key == "area_ha" and values.get("geometry") is not None
            )}


def update_field(db: Session, farm_id: UUID, field_id: UUID,
                 payload: inputs.FieldPatch) -> schemas.Field:
    farm_row(db, farm_id)
    field = field_row(db, farm_id, field_id)
    original = next(f for f in service.get_farm(farm_id, session=db).fields if f.id == field_id)
    values = original.model_dump(round_trip=True, exclude={
        "id", "farm_id", "seasons", "provenance"
    })
    updates = payload.model_dump(exclude_unset=True, exclude={"season"})
    values.update(updates)
    if "geometry" in updates and updates["geometry"] is not None:
        if "area_ha" not in updates:
            values["area_ha"] = None
        if "location" not in updates:
            values["location"] = None
    validated = _validated_field(db, farm_id, values, field_id)
    # Preserve provenance of unchanged inputs (including original FAO/seed sources).
    changed = {key: value for key, value in validated.items() if key in updates}
    if "geometry" in updates and updates["geometry"] is not None:
        changed.update({key: validated[key] for key in ("area_ha", "location")})
    _apply_field(field, changed)
    if payload.season:
        _season(db, field, payload.season)
    audit(db, "field", field_id, "update", payload.model_dump(exclude_unset=True))
    db.flush()
    db.expire_all()
    return next(f for f in service.get_farm(farm_id, session=db).fields if f.id == field_id)


def remove_field(db: Session, farm_id: UUID, field_id: UUID) -> None:
    farm_row(db, farm_id)
    field = field_row(db, farm_id, field_id)
    if db.scalar(select(models.Orchard.id).where(models.Orchard.field_id == field_id)):
        raise ProblemError(409, "Conflict", "Нельзя удалить поле с существующим садом")
    audit(db, "field", field_id, "delete", {"name": field.name})
    db.delete(field)
    db.flush()
