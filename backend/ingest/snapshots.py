"""Хранилище снимков данных (раздел 6.3 ТЗ).

Снимок = неизменяемая пара файлов в data/snapshots:
    <code>.parquet  — суточные ряды
    <code>.json     — метаданные: источник, версия продукта, дата запроса, координаты, sha256

Расчёт ссылается на снимок, а не на «живой» API: демо работает без интернета.
На хакатоне хранилище — локальная папка; в пилоте — MinIO/S3 с тем же интерфейсом.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "snapshots"


class SnapshotExistsError(FileExistsError):
    """Снимок с таким кодом уже есть. Снимки неизменяемы — нужен новый код."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_snapshot(code: str, df: pd.DataFrame, meta: dict, directory: Path = DEFAULT_DIR) -> dict:
    """Сохранить снимок. Существующий не перезаписывается."""
    directory.mkdir(parents=True, exist_ok=True)
    data_path = directory / f"{code}.parquet"
    meta_path = directory / f"{code}.json"
    if data_path.exists() or meta_path.exists():
        raise SnapshotExistsError(code)
    df.to_parquet(data_path, index=False)
    meta = {**meta, "code": code, "rows": int(len(df)), "sha256": sha256_file(data_path),
            "storage_uri": data_path.name}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def list_snapshots(directory: Path = DEFAULT_DIR, source: str | None = None) -> list[dict]:
    """Метаданные всех снимков (по одному на код), отсортированы по коду."""
    if not directory.exists():
        return []
    metas = []
    for path in sorted(directory.glob("*.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        if source is None or meta.get("source") == source:
            metas.append(meta)
    return metas


def load_snapshot(code: str, directory: Path = DEFAULT_DIR, verify: bool = True) -> pd.DataFrame:
    """Прочитать ряды снимка. verify=True сверяет sha256 с метаданными."""
    data_path = directory / f"{code}.parquet"
    if verify:
        meta = json.loads((directory / f"{code}.json").read_text(encoding="utf-8"))
        actual = sha256_file(data_path)
        if actual != meta["sha256"]:
            raise ValueError(f"Снимок {code} повреждён: sha256 {actual} != {meta['sha256']}")
    return pd.read_parquet(data_path)
