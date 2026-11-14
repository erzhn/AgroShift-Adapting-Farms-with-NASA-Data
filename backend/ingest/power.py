"""Загрузка NASA POWER (daily, community=AG) в неизменяемые снимки — разделы 6.1 и 6.3 ТЗ.

Открытый REST API без ключа. Запуск (скачать три пилотные точки Чуйской области, 1995–2025):

    docker compose exec api python -m ingest.power

Одна произвольная точка:

    docker compose exec api python -m ingest.power --name bishkek --lat 42.87 --lon 74.59

Data: NASA Langley Research Center (LaRC) POWER Project.
"""

import argparse
import time
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from ingest.snapshots import DEFAULT_DIR, SnapshotExistsError, list_snapshots, save_snapshot

SOURCE = "nasa_power_daily_ag"
API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
ATTRIBUTION = (
    "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project "
    "funded through the NASA Earth Science/Applied Science Program."
)

# Параметр POWER -> колонка снимка (раздел 6.1)
PARAMETERS = {
    "T2M": "t2m",                    # °C
    "T2M_MAX": "tmax",               # °C
    "T2M_MIN": "tmin",               # °C
    "T2MDEW": "tdew",                # °C
    "RH2M": "rh",                    # %
    "WS2M": "ws2m",                  # м/с
    "ALLSKY_SFC_SW_DWN": "rs",       # в снимке всегда МДж/м²/сут
    "PRECTOTCORR": "precip",         # мм/сут
}

# Сетка POWER (MERRA-2): метео 0,5° × 0,625°; радиация (CERES) 1° × 1°
GRID_LAT_STEP = 0.5
GRID_LON_STEP = 0.625

# Пилотные точки Чуйской области (раздел 15.5)
PILOT_POINTS = {
    "sokuluk": {"name_ru": "Сокулук", "name_en": "Sokuluk", "lat": 42.860, "lon": 74.300},
    "kant": {"name_ru": "Кант", "name_en": "Kant", "lat": 42.891, "lon": 74.851},
    "kara_balta": {"name_ru": "Кара-Балта", "name_en": "Kara-Balta",
                   "lat": 42.814, "lon": 73.849},
}

DEFAULT_START = date(1995, 1, 1)
DEFAULT_END = date(2025, 12, 31)


def grid_cell(lat: float, lon: float) -> dict:
    """Ячейка метеосетки POWER, в которую попадает точка (для подписи «климат района»)."""
    c_lat = round(lat / GRID_LAT_STEP) * GRID_LAT_STEP
    c_lon = round(lon / GRID_LON_STEP) * GRID_LON_STEP
    return {
        "center": [c_lon, c_lat],
        "bbox": [c_lon - GRID_LON_STEP / 2, c_lat - GRID_LAT_STEP / 2,
                 c_lon + GRID_LON_STEP / 2, c_lat + GRID_LAT_STEP / 2],
        "lat_step": GRID_LAT_STEP,
        "lon_step": GRID_LON_STEP,
    }


def fetch_power(lat: float, lon: float, start: date, end: date,
                retries: int = 4, timeout: float = 120.0) -> tuple[dict, str]:
    """Запрос к POWER с повторами и экспоненциальной задержкой (раздел 12.2)."""
    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            r = httpx.get(API_URL, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json(), str(r.url)
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"NASA POWER недоступен после {retries} попыток: {last_error}")


def parse_power(payload: dict) -> tuple[pd.DataFrame, dict]:
    """JSON POWER -> суточная таблица. Пропуски (fill_value) -> NaN, радиация -> МДж/м²/сут."""
    series = payload["properties"]["parameter"]
    fill = float(payload.get("header", {}).get("fill_value", -999.0))
    units = {k: v.get("units", "") for k, v in payload.get("parameters", {}).items()}

    dates = sorted(next(iter(series.values())))
    df = pd.DataFrame({"date": pd.to_datetime(dates, format="%Y%m%d")})
    for param, column in PARAMETERS.items():
        values = np.array([series[param][d] for d in dates], dtype="float64")
        values[np.isclose(values, fill)] = np.nan
        df[column] = values

    # Радиация: сообщество AG отдаёт МДж/м²/сут, другие — кВт·ч/м²/сут (× 3,6)
    rs_unit = units.get("ALLSKY_SFC_SW_DWN", "")
    if "kw" in rs_unit.lower():
        df["rs"] = df["rs"] * 3.6
    df["date"] = df["date"].dt.date

    lon, lat, cell_elevation = payload["geometry"]["coordinates"]
    header = payload.get("header", {})
    info = {
        "api_version": header.get("api", {}).get("version"),
        "sources": header.get("sources"),
        "fill_value": fill,
        "units_original": units,
        "cell_elevation_m": float(cell_elevation),
        "lat": float(lat),
        "lon": float(lon),
        "missing": {c: int(df[c].isna().sum()) for c in PARAMETERS.values()},
    }
    return df, info


def snapshot_code(lat: float, lon: float, fetched: date) -> str:
    """Формат из примера ТЗ (11.2): power_ag_42.87_74.59_v2025-11-10."""
    return f"power_ag_{lat:.2f}_{lon:.2f}_v{fetched.isoformat()}"


def ingest_point(name: str, lat: float, lon: float, start: date = DEFAULT_START,
                 end: date = DEFAULT_END, directory: Path = DEFAULT_DIR,
                 extra_meta: dict | None = None) -> dict:
    payload, url = fetch_power(lat, lon, start, end)
    df, info = parse_power(payload)
    fetched_at = datetime.now(UTC)
    meta = {
        "source": SOURCE,
        "product": "NASA POWER Daily, community AG",
        "product_version": info["api_version"],
        "name": name,
        **(extra_meta or {}),
        "lat": lat,
        "lon": lon,
        "cell_elevation_m": info["cell_elevation_m"],
        "grid_cell": grid_cell(lat, lon),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "request_url": url,
        "columns": {
            "t2m": "°C", "tmax": "°C", "tmin": "°C", "tdew": "°C", "rh": "%",
            "ws2m": "m/s", "rs": "MJ/m²/day", "precip": "mm/day",
        },
        "units_original": info["units_original"],
        "power_sources": info["sources"],
        "missing": info["missing"],
        "attribution": ATTRIBUTION,
    }
    return save_snapshot(snapshot_code(lat, lon, fetched_at.date()), df, meta, directory)


def main() -> None:
    parser = argparse.ArgumentParser(description="Скачать NASA POWER в снимки data/snapshots")
    parser.add_argument("--name", help="имя точки (по умолчанию — все пилотные)")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END)
    parser.add_argument("--force", action="store_true",
                        help="качать, даже если для точки уже есть снимок")
    args = parser.parse_args()

    if args.lat is not None and args.lon is not None:
        points = {args.name or "point": {"lat": args.lat, "lon": args.lon}}
    elif args.name:
        points = {args.name: PILOT_POINTS[args.name]}
    else:
        points = PILOT_POINTS

    existing = {m["name"] for m in list_snapshots(source=SOURCE)}
    for name, p in points.items():
        if name in existing and not args.force:
            print(f"[skip] {name}: снимок уже есть (—force чтобы скачать новый)")
            continue
        extra = {k: v for k, v in p.items() if k.startswith("name_")}
        try:
            meta = ingest_point(name, p["lat"], p["lon"], args.start, args.end, extra_meta=extra)
        except SnapshotExistsError as exc:
            print(f"[skip] {name}: снимок {exc} уже существует")
            continue
        print(f"[ok]   {name}: {meta['code']}  rows={meta['rows']}  "
              f"cell_elev={meta['cell_elevation_m']:.0f} m  missing={meta['missing']}")


if __name__ == "__main__":
    main()
