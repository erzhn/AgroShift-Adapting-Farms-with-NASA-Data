"""Offline, deterministic demo inputs. No database connection or NASA downloads.

The JSON is the editable source of seed values. This module adds stable IDs and
explicit per-input provenance, then validates the public contracts.
"""

import json
from datetime import date
from math import cos, radians, sqrt
from pathlib import Path
from uuid import UUID, uuid5

from pydantic import Field as Attr

from app.modules.farms.schemas import (
    CashAccount,
    Contract,
    CostNorm,
    Crop,
    CropSeason,
    CropVariant,
    Farm,
    Field,
    Herd,
    Orchard,
    Point,
    Polygon,
    Price,
    Scenario,
    Source,
    WaterRight,
)

SEED_PATH = Path(__file__).resolve().parents[3] / "data" / "seed" / "farms.json"
SEED_NAMESPACE = UUID("83478b36-f347-54c8-9a3a-8467896af13a")


def seed_id(key: str) -> UUID:
    return uuid5(SEED_NAMESPACE, key)


FARM_ID = seed_id("farm/asan")
WORKSPACE_ID = seed_id("workspace/asan")
CANAL_ID = seed_id("canal/asan-demo")


class DemoCanal(Contract):
    id: UUID = CANAL_ID
    name: str = "Демо-водовыпуск Асана"
    conveyance_efficiency: float = Attr(gt=0, le=1)
    conveyance_source_type: str = "user_estimate"


class SeedBundle(Contract):
    version: int
    season: int
    crops: list[Crop]
    farm: Farm
    canal: DemoCanal
    scenarios: list[Scenario]


def _provenance(values: dict, source: Source) -> dict[str, Source]:
    """Dates, numeric arrays and nested numeric parameters use the same input source."""
    return {
        key: source.model_copy(deep=True)
        for key, value in values.items()
        if not isinstance(value, bool) and isinstance(value, (int, float, list, dict, date))
    }


def _polygon(lon: float, lat: float, area_ha: float) -> Polygon:
    """Synthetic square, locally scaled to WGS84; not a cadastral boundary.

    The geodesic area is independently checked with PostGIS in integration tests.
    """
    phi = radians(lat)
    lat_m = 111132.92 - 559.82 * cos(2 * phi) + 1.175 * cos(4 * phi) - 0.0023 * cos(6 * phi)
    lon_m = 111412.84 * cos(phi) - 93.5 * cos(3 * phi) + 0.118 * cos(5 * phi)
    half = sqrt(area_ha * 10000) / 2
    dx, dy = half / lon_m, half / lat_m
    ring = [
        (lon - dx, lat - dy),
        (lon + dx, lat - dy),
        (lon + dx, lat + dy),
        (lon - dx, lat + dy),
        (lon - dx, lat - dy),
    ]
    return Polygon(coordinates=[ring])


def load_seed() -> SeedBundle:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(raw["as_of"])
    sources = {key: Source(**value, as_of=as_of) for key, value in raw["sources"].items()}
    estimate = sources["demo"]
    crops = []
    for row in raw["crops"]:
        values = {k: v for k, v in row.items() if k not in ("variant", "note")}
        crop_id = seed_id(f"crop/{row['code']}")
        variant = row["variant"]
        variant_id = seed_id(f"variant/{variant['code']}")
        provenance = _provenance(values, estimate)
        for name in ("kc_ini", "kc_mid", "kc_end", "height_m"):
            provenance[name] = sources["kc"].model_copy(
                update={"note": sources["kc"].note + " " + row["note"]}
            )
        provenance["root_depth_m"] = sources["roots"]
        provenance["p_depletion"] = sources["p"]
        if row["code"] != "apple":
            provenance["ky"] = sources["ky"]
        else:
            provenance["ky"] = estimate.model_copy(update={"note": row["note"]})
        if row["code"] in ("wheat", "beans"):
            provenance["stage_days"] = sources[f"stages_{row['code']}"]
        for name in (
            "ky_stages",
            "t_min_kill",
            "gdd_required",
            "t_crit_heat",
            "k_heat",
            "water_critical_stages",
        ):
            provenance[name] = Source(
                source_type="unknown",
                confidence=0,
                note="Нет проверенного локального значения; не подставлять 0.",
            )
        costs = [
            CostNorm(
                id=seed_id(f"cost/{variant['code']}/{cost['operation']}/{cost['month']}"),
                **cost,
                provenance=_provenance(cost, estimate),
            )
            for cost in variant["costs"]
        ]
        crops.append(
            Crop(
                id=crop_id,
                **values,
                provenance=provenance,
                variants=[
                    CropVariant(
                        id=variant_id,
                        crop_id=crop_id,
                        code=variant["code"],
                        maturity_class="mid",
                        product=variant["product"],
                        yield_potential_t_ha=variant["yield_potential_t_ha"],
                        costs=costs,
                        provenance={"yield_potential_t_ha": estimate},
                    )
                ],
                price=Price(
                    id=seed_id(f"price/{row['code']}/chuy"),
                    item_code=row["code"],
                    region="chuy",
                    price_som=variant["price_som_t"],
                    date=as_of,
                    source_type="user_estimate",
                    confidence=0.3,
                    source_note=estimate.note,
                ),
            )
        )

    by_code = {crop.code: crop for crop in crops}
    profile = raw["farm"]
    season = raw["season"]
    fields = []
    for row in profile["fields"]:
        crop = by_code[row["crop"]]
        field_id = seed_id(f"field/asan/{row['code']}")
        crop_season = dict(
            year=season,
            sowing_date=date.fromisoformat(row["sowing_date"]),
            harvest_date=date.fromisoformat(row["harvest_date"]),
            planned_yield_t_ha=crop.variants[0].yield_potential_t_ha,
        )
        field_values = dict(
            area_ha=row["area_ha"],
            soil_type="loam",
            taw_mm_per_m=140.0,
            geometry=_polygon(row["lon"], row["lat"], row["area_ha"]),
            location=Point(coordinates=(row["lon"], row["lat"])),
        )
        field_sources = _provenance(field_values, estimate)
        field_sources.update(geometry=estimate, location=estimate)
        fields.append(
            Field(
                id=field_id,
                farm_id=FARM_ID,
                name=row["name"],
                **field_values,
                irrigation_method="furrow",
                canal_id=CANAL_ID,
                provenance=field_sources,
                seasons=[
                    CropSeason(
                        id=seed_id(f"season/{row['code']}/{season}"),
                        field_id=field_id,
                        crop_id=crop.id,
                        crop_variant_id=crop.variants[0].id,
                        **crop_season,
                        provenance=_provenance(crop_season, estimate),
                    )
                ],
            )
        )

    farm = Farm(
        id=FARM_ID,
        workspace_id=WORKSPACE_ID,
        name=profile["name"],
        district=profile["district"],
        village=profile["village"],
        language=profile["language"],
        family_reserve_som=profile["family_reserve_som"],
        labour_hours_month=profile["labour_hours_month"],
        fields=fields,
        provenance={name: estimate for name in ("family_reserve_som", "labour_hours_month")},
        orchards=[
            Orchard(
                id=seed_id("orchard/asan"),
                farm_id=FARM_ID,
                field_id=fields[0].id,
                species="apple",
                planted_year=profile["orchard_planted_year"],
                density_trees_ha=profile["orchard_density_trees_ha"],
                rootstock="seedling",
                provenance={name: estimate for name in ("planted_year", "density_trees_ha")},
            )
        ],
        herds=[
            Herd(
                id=seed_id("herd/asan/cows"),
                farm_id=FARM_ID,
                species="cow",
                head_count=profile["herd_head_count"],
                purpose="milk",
                provenance={"head_count": estimate},
            )
        ],
        cash_accounts=[
            CashAccount(
                id=seed_id("cash/asan"),
                farm_id=FARM_ID,
                name="Основной",
                balance_som=profile["cash_som"],
                as_of=date(season, 1, 1),
                provenance={"balance_som": estimate, "as_of": estimate},
            )
        ],
        water_rights=[
            WaterRight(
                id=seed_id(f"water-right/asan/{season}"),
                farm_id=FARM_ID,
                canal_id=CANAL_ID,
                season=season,
                limit_m3=profile["limit_m3"],
                flow_l_s=profile["flow_l_s"],
                turn_interval_days=profile["turn_interval_days"],
                turn_hours=profile["turn_hours"],
                failure_months=profile["failure_months"],
                source_type="user_estimate",
                confidence=0.3,
                legal_basis=(
                    "Синтетическое демо. Объём и расход на водовыпуске хозяйства; не право АВП."
                ),
            )
        ],
    )
    scenarios = []
    for row in raw["scenarios"]:
        scenario = Scenario(id=seed_id(f"scenario/{row['preset_code']}"), **row)
        source = estimate.model_copy(
            update={
                "note": (
                    "Параметры демонстрационного стресс-теста (ТЗ FR-5.2), не прогноз. "
                    "Малоснежная зима — условное снижение подачи, не модель снегозапаса. "
                    "Исторический год требует отдельного снимка NASA POWER."
                )
            }
        )
        scenario.provenance = _provenance(scenario.model_dump(round_trip=True), source)
        scenario.provenance.pop("provenance", None)
        scenarios.append(scenario)
    return SeedBundle(
        version=raw["version"],
        season=season,
        crops=crops,
        farm=farm,
        canal=DemoCanal(conveyance_efficiency=profile["conveyance_efficiency"]),
        scenarios=scenarios,
    )
