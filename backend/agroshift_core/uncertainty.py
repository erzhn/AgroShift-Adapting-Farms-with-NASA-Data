"""М10 — неопределённость: выборки, P10/P50/P90, CVaR, хэш результата.

ТЗ, раздел 8.10. На хакатоне (14.1): 30 исторических лет NASA = 30 выборок + ценовой шум.
Все стратегии видят одни и те же выборки (common random numbers).
"""

import hashlib
import json
from typing import Any

import numpy as np


def _stream(seed: int, key: str) -> np.random.Generator:
    """Независимый поток случайных чисел для ключа.

    Поток зависит только от (seed, key), а не от набора остальных ключей: добавление новой
    культуры в перебор не меняет шум уже посчитанных культур.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return np.random.default_rng(np.random.SeedSequence([seed, int.from_bytes(digest[:8], "big")]))


def lognormal_noise(seed: int, key: str, n_samples: int, sigma: float) -> np.ndarray:
    """Множители с математическим ожиданием 1: exp(N(−σ²/2, σ))."""
    if sigma <= 0:
        return np.ones(n_samples)
    z = _stream(seed, key).standard_normal(n_samples)
    return np.exp(sigma * z - 0.5 * sigma * sigma)


def percentiles(x: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """P10, P50, P90 вдоль оси выборок."""
    p10, p50, p90 = np.percentile(np.asarray(x, dtype=float), [10, 50, 90], axis=axis)
    return p10, p50, p90


def cvar(x: np.ndarray, alpha: float = 0.10) -> float:
    """CVaR_α — среднее худших α исходов (для дохода: нижний хвост)."""
    values = np.sort(np.asarray(x, dtype=float))
    k = max(1, int(np.ceil(alpha * values.size)))
    return float(values[:k].mean())


def result_hash(payload: Any) -> str:
    """sha256 от канонического JSON — для теста воспроизводимости (раздел 13.1)."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
