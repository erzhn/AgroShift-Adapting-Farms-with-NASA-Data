"""Декады — базовый шаг показа водного баланса (раздел 8 ТЗ).

Декады: 1–10, 11–20, 21–конец месяца. 36 декад в году, индекс 1..36
(1 = 1–10 января, 21 = 21–31 июля, 36 = 21–31 декабря).
"""

import calendar as _cal
from datetime import date

import numpy as np

DECADES_PER_YEAR = 36


def decade_index(d: date) -> int:
    """Индекс декады 1..36 для даты."""
    return (d.month - 1) * 3 + min((d.day - 1) // 10, 2) + 1


def decade_indices(dates: np.ndarray) -> np.ndarray:
    """Векторный вариант для массива datetime64[D]."""
    dates = np.asarray(dates, dtype="datetime64[D]")
    months = dates.astype("datetime64[M]")
    month0 = months.astype(int) % 12
    day0 = (dates - months.astype("datetime64[D]")).astype(int)
    return month0 * 3 + np.minimum(day0 // 10, 2) + 1


def decade_bounds(year: int, index: int) -> tuple[date, date]:
    """Первый и последний день декады (включительно)."""
    if not 1 <= index <= DECADES_PER_YEAR:
        raise ValueError(f"decade index must be 1..36, got {index}")
    month0, part = divmod(index - 1, 3)
    month = month0 + 1
    start_day = part * 10 + 1
    end_day = _cal.monthrange(year, month)[1] if part == 2 else start_day + 9
    return date(year, month, start_day), date(year, month, end_day)


def decade_length(year: int, index: int) -> int:
    start, end = decade_bounds(year, index)
    return (end - start).days + 1


def decade_month(index: int) -> int:
    """Месяц 1..12, к которому относится декада."""
    return (index - 1) // 3 + 1


def decade_key(year: int, index: int) -> str:
    """Ключ периода: '2027-D21'."""
    return f"{year}-D{index:02d}"
