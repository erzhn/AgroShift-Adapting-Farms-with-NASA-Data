"""Каталог наборов данных NASA для страницы «Данные NASA» (FR-11.2, раздел 6.1 ТЗ).

status = "active" только у того, что реально участвует в расчёте. Остальное — "planned":
честно показываем, что это следующий шаг, а не использованные данные.
"""

from collections.abc import Callable
from datetime import date, datetime

from app.modules.water.schemas import Dataset, SnapshotInfo

ATTRIBUTION = (
    "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project "
    "funded through the NASA Earth Science/Applied Science Program."
)

_T = dict[str, str]

_DATASETS: list[dict] = [
    {
        "id": "nasa_power_daily_ag",
        "name": "NASA POWER (community AG), daily",
        "provider": "NASA LaRC",
        "parameters": "T2M, T2M_MAX, T2M_MIN, T2MDEW, RH2M, WS2M, ALLSKY_SFC_SW_DWN, "
                      "PRECTOTCORR",
        "resolution": {"ru": "0,5° × 0,625° (метео), 1° × 1° (радиация)",
                       "en": "0.5° × 0.625° (meteorology), 1° × 1° (radiation)"},
        "frequency": {"ru": "сутки, с 1981 г.", "en": "daily, since 1981"},
        "used_for": {
            "ru": "ET0 по FAO Penman–Monteith, сумма активных температур, заморозки, "
                  "30-летняя история для вероятностей",
            "en": "FAO Penman–Monteith ET0, growing degree days, frost dates, "
                  "30-year history for probabilities"},
        "limitations": {
            "ru": "Это климат района (ячейка ~55 × 50 км), а не данные конкретного поля. "
                  "Температура поправляется на высоту поля.",
            "en": "District-scale climate (~55 × 50 km cell), not field-level data. "
                  "Temperature is corrected for field elevation."},
        "priority": "MVP",
        "status": "active",
        "url": "https://power.larc.nasa.gov/",
    },
    {
        "id": "nasadem",
        "name": "SRTM / NASADEM",
        "provider": "NASA JPL",
        "parameters": {"ru": "высота, уклон", "en": "elevation, slope"},
        "resolution": {"ru": "30 м", "en": "30 m"},
        "frequency": {"ru": "статичный", "en": "static"},
        "used_for": {"ru": "Поправка температуры по высоте, давление для ET0, сток",
                     "en": "Elevation correction of temperature, pressure for ET0, runoff"},
        "limitations": {"ru": "Сейчас высота поля задаётся в профиле хозяйства.",
                        "en": "Field elevation currently comes from the farm profile."},
        "priority": "MVP",
        "status": "planned",
        "url": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001",
    },
    {
        "id": "gpm_imerg",
        "name": "GPM IMERG",
        "provider": "NASA GSFC",
        "parameters": {"ru": "осадки", "en": "precipitation"},
        "resolution": {"ru": "≈ 0,1°", "en": "≈ 0.1°"},
        "frequency": {"ru": "сутки", "en": "daily"},
        "used_for": {"ru": "Уточнение осадков в горном рельефе",
                     "en": "Refining precipitation in mountain terrain"},
        "limitations": {"ru": "Не подключено.", "en": "Not connected yet."},
        "priority": "MVP+",
        "status": "planned",
        "url": "https://gpm.nasa.gov/data/imerg",
    },
    {
        "id": "modis_snow",
        "name": "MODIS MOD10A1 / VIIRS",
        "provider": "NASA NSIDC DAAC",
        "parameters": {"ru": "снежный покров", "en": "snow cover"},
        "resolution": {"ru": "≈ 500 м", "en": "≈ 500 m"},
        "frequency": {"ru": "сутки", "en": "daily"},
        "used_for": {"ru": "Индекс снегозапаса в водосборе канала — ранний сигнал маловодья",
                     "en": "Snowpack index of the canal catchment — early low-water signal"},
        "limitations": {"ru": "Не подключено.", "en": "Not connected yet."},
        "priority": "MVP+",
        "status": "planned",
        "url": "https://nsidc.org/data/mod10a1",
    },
    {
        "id": "hls",
        "name": "HLS (Harmonized Landsat–Sentinel-2)",
        "provider": "NASA LP DAAC",
        "parameters": "NDVI, NDWI",
        "resolution": {"ru": "30 м", "en": "30 m"},
        "frequency": {"ru": "2–3 дня без облаков", "en": "2–3 days, cloud permitting"},
        "used_for": {"ru": "Состояние посевов на поле, калибровка Kc",
                     "en": "Crop condition per field, Kc calibration"},
        "limitations": {"ru": "Не подключено. Подходит для полей от ~1 га.",
                        "en": "Not connected yet. Suitable for fields from ~1 ha."},
        "priority": "MVP+",
        "status": "planned",
        "url": "https://www.earthdata.nasa.gov/data/projects/hls",
    },
    {
        "id": "smap_l4",
        "name": "SMAP L4 Soil Moisture",
        "provider": "NASA NSIDC DAAC",
        "parameters": {"ru": "влажность корневой зоны", "en": "root-zone soil moisture"},
        "resolution": {"ru": "≈ 9 км", "en": "≈ 9 km"},
        "frequency": {"ru": "3 часа", "en": "3-hourly"},
        "used_for": {"ru": "Начальные условия водного баланса весной",
                     "en": "Initial conditions of the spring water balance"},
        "limitations": {"ru": "Не подключено. Сейчас начальное истощение = 0,5·TAW.",
                        "en": "Not connected yet. Initial depletion is 0.5·TAW for now."},
        "priority": "Roadmap",
        "status": "planned",
        "url": "https://smap.jpl.nasa.gov/",
    },
]


def _text(value, lang: str) -> str:
    if isinstance(value, dict):
        return value.get(lang) or value["ru"]
    return value


def _snapshot(meta: dict, cell_of: Callable) -> SnapshotInfo:
    return SnapshotInfo(
        code=meta["code"], point_name=meta.get("name_ru") or meta.get("name"),
        lat=meta["lat"], lon=meta["lon"], cell=cell_of(meta),
        period_start=date.fromisoformat(meta["period_start"]),
        period_end=date.fromisoformat(meta["period_end"]),
        fetched_at=datetime.fromisoformat(meta["fetched_at"]),
        rows=meta["rows"], sha256=meta["sha256"], product_version=meta.get("product_version"),
        missing_values=sum(meta.get("missing", {}).values()),
    )


def datasets(lang: str, power_metas, cell_of: Callable) -> list[Dataset]:
    lang = lang if lang in ("ru", "en") else "ru"
    result = []
    for item in _DATASETS:
        snapshots = ([_snapshot(m, cell_of) for m in power_metas]
                     if item["id"] == "nasa_power_daily_ag" else [])
        result.append(Dataset(
            id=item["id"], name=item["name"], provider=item["provider"],
            parameters=_text(item["parameters"], lang),
            resolution=_text(item["resolution"], lang),
            frequency=_text(item["frequency"], lang),
            used_for=_text(item["used_for"], lang),
            limitations=_text(item["limitations"], lang),
            priority=item["priority"], status=item["status"], url=item["url"],
            snapshots=snapshots,
        ))
    return result
