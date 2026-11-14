"""Insert-only seed: stable IDs, one transaction, no replacement of user edits."""

from collections import Counter

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import models
from app.modules.farms.demo import SeedBundle, load_seed
from app.modules.farms.schemas import Contract


def _values(dto: Contract, *exclude: str) -> dict:
    values = dto.model_dump(mode="python", round_trip=True, exclude=set(exclude))
    if hasattr(dto, "provenance"):
        values["provenance"] = {
            name: source.model_dump(mode="json") for name, source in dto.provenance.items()
        }
    return values


def seed_farms(session: Session, bundle: SeedBundle | None = None) -> dict[str, int]:
    """Flush all seed rows without committing the caller's transaction.

    A savepoint rolls back this whole batch on failure. An unrelated row with a
    matching unique code raises IntegrityError; we never adopt or overwrite it.
    The CLI commits only after this function has succeeded.
    """
    bundle = bundle or load_seed()
    inserted: Counter = Counter()

    def add(model: type, values: dict) -> None:
        result = session.scalar(
            insert(model)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[model.id])
            .returning(model.id)
        )
        inserted[model.__tablename__] += int(result is not None)

    with session.begin_nested():
        for crop in bundle.crops:
            add(models.Crop, _values(crop, "variants", "price"))
            for variant in crop.variants:
                add(models.CropVariant, _values(variant, "costs"))
                for cost in variant.costs:
                    add(models.CostNorm, dict(_values(cost), crop_variant_id=variant.id))
            if crop.price:
                add(models.PriceItem, dict(_values(crop.price), item_kind="crop", farm_id=None))

        farm = bundle.farm
        add(
            models.Workspace,
            {
                "id": farm.workspace_id,
                "type": "farm",
                "name": farm.name,
                "region_id": "chuy",
            },
        )
        # Only the reference needed by Asan. Zhanibek owns the 20-farm canal demo.
        add(models.Canal, _values(bundle.canal))
        add(
            models.Farm,
            _values(farm, "fields", "orchards", "herds", "cash_accounts", "water_rights"),
        )
        for field in farm.fields:
            values = _values(field, "seasons", "geometry", "location")
            for name in ("geometry", "location"):
                geometry = getattr(field, name)
                values[name] = (
                    func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry.model_dump_json()), 4326)
                    if geometry
                    else None
                )
            add(models.Field, values)
            for season in field.seasons:
                add(models.CropSeason, _values(season, "crop_id"))
        for model, collection in (
            (models.Orchard, farm.orchards),
            (models.Herd, farm.herds),
            (models.CashAccount, farm.cash_accounts),
            (models.WaterRight, farm.water_rights),
        ):
            for item in collection:
                add(model, _values(item))
        for scenario in bundle.scenarios:
            add(models.Scenario, _values(scenario))
        for rotation in bundle.rotations:
            add(models.RotationTemplate, _values(rotation))
    return dict(inserted)
