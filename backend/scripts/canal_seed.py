from __future__ import annotations

from datetime import date

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Crop, CropVariant
from app.models.enums import IrrigationMethod, MaturityClass, SourceType, WorkspaceType
from app.models.farm import CropSeason, Farm, Field
from app.models.identity import Workspace
from app.models.water import Canal, SupplySchedule, WaterRight

SEASON = 2027
DEMO_INVITE_CODE = "AGROSHIFT-DEMO"

# The values below are intentionally synthetic placeholders for demo flows.
# They are not agronomic recommendations or local measurements.
CROP_SEED = (
    {
        "code": "alfalfa",
        "names": ("Беде", "Люцерна", "Alfalfa"),
        "family": "legume",
        "kc": (0.40, 1.20, 1.15),
        "days": [20, 30, 40, 25],
        "root": 1.0,
        "ky": 1.0,
        "yield": 8.0,
        "product": "hay",
    },
    {
        "code": "maize",
        "names": ("Жүгөрү", "Кукуруза", "Maize"),
        "family": "grass",
        "kc": (0.30, 1.20, 0.60),
        "days": [20, 35, 40, 25],
        "root": 1.2,
        "ky": 1.25,
        "yield": 12.0,
        "product": "silage",
    },
    {
        "code": "wheat",
        "names": ("Буудай", "Пшеница", "Wheat"),
        "family": "grass",
        "kc": (0.30, 1.15, 0.25),
        "days": [20, 30, 60, 30],
        "root": 1.2,
        "ky": 1.0,
        "yield": 4.0,
        "product": "grain",
    },
    {
        "code": "beans",
        "names": ("Буурчак", "Фасоль", "Beans"),
        "family": "legume",
        "kc": (0.40, 1.15, 0.35),
        "days": [20, 30, 40, 25],
        "root": 0.9,
        "ky": 1.15,
        "yield": 2.5,
        "product": "grain",
    },
    {
        "code": "apple",
        "names": ("Алма", "Яблоня", "Apple"),
        "family": "orchard",
        "kc": (0.45, 0.95, 0.70),
        "days": [30, 40, 150, 60],
        "root": 1.0,
        "ky": 0.9,
        "yield": 15.0,
        "product": "fruit",
    },
)


def _get_or_create_demo_workspace(db: Session, code: str, name: str,
                                  workspace_type: WorkspaceType) -> Workspace:
    workspace = db.scalar(select(Workspace).where(Workspace.region_id == code))
    if workspace is None:
        workspace = Workspace(type=workspace_type, name=name, region_id=code)
        db.add(workspace)
        db.flush()
    return workspace


def _seed_catalog(db: Session) -> list[CropVariant]:
    variants: list[CropVariant] = []
    for item in CROP_SEED:
        crop = db.scalar(select(Crop).where(Crop.code == item["code"]))
        if crop is None:
            crop = Crop(
                code=item["code"],
                name_ky=item["names"][0],
                name_ru=item["names"][1],
                name_en=item["names"][2],
                family=item["family"],
                is_perennial=item["code"] == "apple",
                kc_ini=item["kc"][0],
                kc_mid=item["kc"][1],
                kc_end=item["kc"][2],
                stage_days=item["days"],
                height_m=1.0,
                root_depth_m=item["root"],
                p_depletion=0.5,
                ky=item["ky"],
                ky_stages=[0.2, 0.4, 0.3, 0.1],
                t_base=5.0,
                t_min_kill=-2.0,
                gdd_required=1200.0,
                t_crit_heat=35.0,
                k_heat=0.02,
                water_critical_stages=[2, 3],
                provenance={"source_type": "user_estimate", "confidence": 0.2,
                            "note": "synthetic hackathon seed; agronomist review required"},
            )
            db.add(crop)
            db.flush()
        variant = db.scalar(
            select(CropVariant)
            .where(CropVariant.crop_id == crop.id)
            .order_by(CropVariant.code)
            .limit(1)
        )
        if variant is None:
            variant_code = f"{item['code']}_demo_mid"
            variant = CropVariant(
                crop_id=crop.id,
                code=variant_code,
                maturity_class=MaturityClass.MID,
                stage_days_override=item["days"],
                yield_potential_t_ha=item["yield"],
                product=item["product"],
            )
            db.add(variant)
            db.flush()
        variants.append(variant)
    return variants


def seed_canal_demo(db: Session) -> Canal:
    """Create/reuse one demo canal, 20 farms, field plans, rights, and supply data."""
    canal = db.scalar(select(Canal).where(Canal.invite_code == DEMO_INVITE_CODE))
    if canal is None:
        workspace = _get_or_create_demo_workspace(
            db, "demo-canal-2027", "Демо АВП AgroShift", WorkspaceType.CANAL
        )
        canal = Canal(
            workspace_id=workspace.id,
            name="Демо-канал AgroShift",
            avp_name="Демо АВП",
            geometry=WKTElement(
                "MULTILINESTRING ((74.56 42.83, 74.61 42.87, 74.66 42.90))", srid=4326
            ),
            snow_catchment_geometry=WKTElement(
                "MULTIPOLYGON (((74.48 42.78, 74.72 42.78, 74.72 42.98, "
                "74.48 42.98, 74.48 42.78)))",
                srid=4326,
            ),
            conveyance_efficiency=0.5,
            conveyance_source_type=SourceType.USER_ESTIMATE,
            invite_code=DEMO_INVITE_CODE,
        )
        db.add(canal)
        db.flush()

    variants = _seed_catalog(db)
    irrigation_options = [IrrigationMethod.FURROW, IrrigationMethod.DRIP,
                          IrrigationMethod.SPRINKLER]
    for index in range(20):
        farm_code = f"demo-farm-{index + 1:02d}"
        workspace = _get_or_create_demo_workspace(
            db, farm_code, f"Демо хозяйство {index + 1:02d}", WorkspaceType.FARM
        )
        farm = db.scalar(select(Farm).where(Farm.workspace_id == workspace.id))
        if farm is None:
            farm = Farm(workspace_id=workspace.id, name=f"Хозяйство {index + 1:02d}",
                        district="Сокулук", village="Демо", language="ru")
            db.add(farm)
            db.flush()
        # The seeded cohort is synthetic and explicitly opts into the demo plan.
        farm.consent_canal_plan = True

        lon = 74.55 + (index % 5) * 0.025
        lat = 42.82 + (index // 5) * 0.035
        half = 0.003
        polygon_wkt = (
            f"POLYGON (({lon-half} {lat-half}, {lon+half} {lat-half}, "
            f"{lon+half} {lat+half}, {lon-half} {lat+half}, {lon-half} {lat-half}))"
        )
        field = db.scalar(select(Field).where(Field.farm_id == farm.id,
                                              Field.name == "Демо поле 1"))
        if field is None:
            field = Field(
                farm_id=farm.id,
                name="Демо поле 1",
                geometry=WKTElement(polygon_wkt, srid=4326),
                location=WKTElement(f"POINT ({lon} {lat})", srid=4326),
                area_ha=1.5 + (index % 4) * 0.5,
                elevation_m=750 + index * 5,
                slope_deg=1.0,
                soil_type="synthetic_demo",
                taw_mm_per_m=140.0,
                irrigation_method=irrigation_options[index % len(irrigation_options)],
                canal_id=canal.id,
            )
            db.add(field)
            db.flush()

        variant = variants[index % len(variants)]
        sowing_date = date(SEASON, 4, 1 + (index % 3) * 10)
        season_row = db.scalar(select(CropSeason).where(
            CropSeason.field_id == field.id,
            CropSeason.year == SEASON,
            CropSeason.is_main.is_(True),
        ))
        if season_row is None:
            db.add(CropSeason(
                field_id=field.id,
                crop_variant_id=variant.id,
                year=SEASON,
                is_main=True,
                sowing_date=sowing_date,
                harvest_date=date(SEASON, 9, 15),
                planned_yield_t_ha=variant.yield_potential_t_ha,
            ))
        else:
            season_row.crop_variant_id = variant.id
            season_row.sowing_date = sowing_date
            season_row.harvest_date = date(SEASON, 9, 15)
            season_row.planned_yield_t_ha = variant.yield_potential_t_ha

        right = db.scalar(select(WaterRight).where(
            WaterRight.canal_id == canal.id,
            WaterRight.farm_id == farm.id,
            WaterRight.season == SEASON,
        ))
        if right is None:
            right = WaterRight(
                farm_id=farm.id,
                canal_id=canal.id,
                season=SEASON,
                limit_m3=12_000 + (index % 4) * 1_000,
                turn_interval_days=10,
                legal_basis="synthetic_demo_water_right",
                source_type=SourceType.USER_ESTIMATE,
                confidence=0.2,
            )
            db.add(right)
        else:
            right.limit_m3 = 12_000 + (index % 4) * 1_000

    for decade in range(36):
        # A synthetic seasonal supply pattern with a summer peak, solely for demo.
        volume = 0.0 if decade < 9 or decade > 28 else (14_000.0 if 18 <= decade <= 23
                                                       else 8_000.0)
        row = db.scalar(select(SupplySchedule).where(
            SupplySchedule.canal_id == canal.id,
            SupplySchedule.season == SEASON,
            SupplySchedule.decade_index == decade,
        ))
        if row is None:
            db.add(SupplySchedule(
                canal_id=canal.id,
                season=SEASON,
                decade_index=decade,
                volume_m3=volume,
                source_type=SourceType.USER_ESTIMATE,
                reliability=0.8,
            ))
        else:
            row.volume_m3 = volume
            row.source_type = SourceType.USER_ESTIMATE
            row.reliability = 0.8

    db.flush()
    db.refresh(canal)
    return canal
