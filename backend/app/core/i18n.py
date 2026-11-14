"""Локализация серверных текстов (раздел 12.4): никакого текста в коде — только ключи.

Файлы: app/i18n/{ru,ky,en}.json. Ключи используют, например, Breakpoint.explanation_key
и тревожные маркеры на шкале. Кыргызские тексты вычитывает носитель языка.
"""

import json
from functools import lru_cache
from pathlib import Path

LANGS = ("ky", "ru", "en")
_DIR = Path(__file__).resolve().parents[1] / "i18n"


@lru_cache
def _load(lang: str) -> dict[str, str]:
    path = _DIR / f"{lang}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def t(key: str, lang: str = "ru", **params: object) -> str:
    """Перевод ключа; если в языке нет — берём русский, затем сам ключ."""
    text = _load(lang).get(key) or _load("ru").get(key) or key
    return text.format(**params) if params else text
