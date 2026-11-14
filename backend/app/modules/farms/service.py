"""Read contracts for other modules; no HTTP calls and no implicit seed fallback.

Call get_farm(farm_id) or get_crop(crop_id) directly. An optional keyword-only
session lets a caller read within its own transaction; this service never commits.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.core.errors import NotFoundError
from app.modules.farms import schemas


@contextmanager
def _session(existing: Session | None) -> Iterator[Session]:
    if existing is not None:
        yield existing
    else:
        from app.db.session import SessionLocal

        with SessionLocal() as owned:
            yield owned


def _id(value: UUID | str, entity: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise NotFoundError(entity, value) from exc


def _data(row: object, schema: type[schemas.Contract], *exclude: str) -> dict:
    return {name: getattr(row, name) for name in schema.model_fields if name not in exclude}


def list_crops(*, session: Session | None = None) -> list[schemas.Crop]:
    with _session(session) as db:
        return [
            get_crop(id_, session=db)
            for id_ in db.scalars(select(models.Crop.id).order_by(models.Crop.code))
        ]


def get_farm(farm_id: UUID | str, *, session: Session | None = None) -> schemas.Farm:
    with _session(session) as db:
        farm = db.scalar(
            select(models.Farm)
            .where(models.Farm.id == _id(farm_id, "Farm"))
            .options(
                selectinload(models.Farm.fields).selectinload(models.Field.seasons),
                selectinload(models.Farm.orchards),
                selectinload(models.Farm.herds),
                selectinload(models.Farm.cash_accounts),
            )
        )
        if farm is None:
            raise NotFoundError("Farm", farm_id)
        variant_ids = {s.crop_variant_id for field in farm.fields for s in field.seasons}
        crops = (
            dict(
                db.execute(
                    select(models.CropVariant.id, models.CropVariant.crop_id).where(
                        models.CropVariant.id.in_(variant_ids)
                    )
                ).all()
            )
            if variant_ids
            else {}
        )
        fields = []
        for field in sorted(farm.fields, key=lambda item: str(item.id)):
            values = _data(field, schemas.Field, "geometry", "location", "seasons")
            values.update(
                geometry=json.loads(field.geometry_geojson) if field.geometry_geojson else None,
                location=json.loads(field.location_geojson) if field.location_geojson else None,
                seasons=[
                    schemas.CropSeason(
                        **_data(season, schemas.CropSeason, "crop_id"),
                        crop_id=crops[season.crop_variant_id],
                    )
                    for season in sorted(field.seasons, key=lambda s: (s.year, str(s.id)))
                ],
            )
            fields.append(schemas.Field(**values))
        rights = db.scalars(
            select(models.WaterRight)
            .where(models.WaterRight.farm_id == farm.id)
            .order_by(models.WaterRight.season, models.WaterRight.id)
        ).all()
        return schemas.Farm(
            **_data(
                farm, schemas.Farm, "fields", "orchards", "herds", "cash_accounts", "water_rights"
            ),
            fields=fields,
            orchards=[
                schemas.Orchard.model_validate(x)
                for x in sorted(farm.orchards, key=lambda x: str(x.id))
            ],
            herds=[
                schemas.Herd.model_validate(x) for x in sorted(farm.herds, key=lambda x: str(x.id))
            ],
            cash_accounts=[
                schemas.CashAccount.model_validate(x)
                for x in sorted(farm.cash_accounts, key=lambda x: str(x.id))
            ],
            water_rights=[schemas.WaterRight.model_validate(x) for x in rights],
        )


def get_crop(crop_id: UUID | str, *, session: Session | None = None) -> schemas.Crop:
    """Return agronomy, variants, monthly costs, and the latest regional price in som/t.

    Farm-specific prices and other units are deliberately not mixed into this
    shared Chuy catalog. Missing prices remain None and mark completeness partial.
    """
    with _session(session) as db:
        crop = db.scalar(
            select(models.Crop)
            .where(models.Crop.id == _id(crop_id, "Crop"))
            .options(
                selectinload(models.Crop.variants),
            )
        )
        if crop is None:
            raise NotFoundError("Crop", crop_id)
        variant_ids = [variant.id for variant in crop.variants]
        norms = db.scalars(
            select(models.CostNorm)
            .where(models.CostNorm.crop_variant_id.in_(variant_ids))
            .order_by(models.CostNorm.month, models.CostNorm.operation, models.CostNorm.id)
        ).all()
        price = db.scalar(
            select(models.PriceItem)
            .where(
                models.PriceItem.item_kind == "crop",
                models.PriceItem.item_code == crop.code,
                models.PriceItem.region == "chuy",
                models.PriceItem.unit == "t",
                models.PriceItem.farm_id.is_(None),
            )
            .order_by(models.PriceItem.date.desc(), models.PriceItem.id)
            .limit(1)
        )
        return schemas.Crop(
            **_data(crop, schemas.Crop, "variants", "price"),
            price=schemas.Price.model_validate(price) if price else None,
            variants=[
                schemas.CropVariant(
                    **_data(variant, schemas.CropVariant, "costs"),
                    costs=[
                        schemas.CostNorm.model_validate(norm)
                        for norm in norms
                        if norm.crop_variant_id == variant.id
                    ],
                )
                for variant in sorted(crop.variants, key=lambda item: item.code)
            ],
        )


def list_scenario_presets(*, session: Session | None = None) -> list[schemas.Scenario]:
    with _session(session) as db:
        rows = db.scalars(
            select(models.Scenario)
            .where(models.Scenario.preset_code.is_not(None), models.Scenario.farm_id.is_(None))
            .order_by(models.Scenario.preset_code)
        ).all()
        return [schemas.Scenario.model_validate(row) for row in rows]
