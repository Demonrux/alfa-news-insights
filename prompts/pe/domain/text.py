from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from .model import Article

_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
_OUR_TAGS = re.compile(r"</?\s*(untrusted_\w+|news|report|external|question|system|user|assistant|developer|instructions?)\b[^>]*>", re.I)
_OUR_MARKERS = re.compile(r"<<<\s*(SYSTEM|USER)\s*>>>", re.I)
_INJ = [re.compile(p, re.I) for p in (
    r"игнорир\w*\s+(все\s+)?(предыдущ|прошл|выше|инструкц|правил)",
    r"забудь\s+(все\s+)?(предыдущ|инструкц|правил)",
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)",
    r"disregard\s+(the\s+)?(previous|above|system)",
    r"(выведи|покажи|раскрой|напечатай)\s+(свой\s+|твой\s+)?(системн\w*\s+)?(промпт|инструкци)",
    r"(system|developer)\s+prompt",
    r"ты\s+(теперь|больше\s+не)\b",
    r"you\s+are\s+now\b",
    r"(новая|новые)\s+инструкци",
    r"(порекомендуй|рекомендуй|посоветуй)\s+(клиент\w*\s+)?(продать|купить|вывести|перевести)",
    r"(переведи|отправь)\s+(деньги|средства)",
    r"assistant\s*:",
    r"system\s*:",
)]

_NUM = re.compile(r"(?<![\w,.])[-−]?\d+(?:[  ]\d{3})*(?:[.,]\d+)?")
_WORD = re.compile(r"[а-яёa-z0-9]+", re.I)
_STOP = set("и в во на с со по к ко о об от до за из у для при не что это как а но или же ли бы то так его ее её их "
            "мы вы они он она оно был была были быть будет может".split())
_PERIODS = {k: re.compile(v, re.I) for k, v in {
    "январь": r"январ", "февраль": r"феврал", "март": r"\bмарт", "апрель": r"апрел", "май": r"\bма[йяе]\b",
    "июнь": r"\bиюн", "июль": r"\bиюл", "август": r"\bавгуст", "сентябрь": r"сентябр", "октябрь": r"октябр",
    "ноябрь": r"ноябр", "декабрь": r"декабр", "квартал": r"квартал|\b[1-4]\s?[кК]\b|\b[1-4][кК]\d{2}",
    "полугодие": r"полугод|\b[12]\s?[пП]\b|\b[12][пП]\d{2}",
}.items()}
PII = [
    (re.compile(r"SYNTHETIC_[A-Z]", re.I), "внутренний идентификатор SYNTHETIC_*"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "похоже на внутренний идентификатор"),
    (re.compile(r"\b\d{1,3}(?:[  ]\d{3}){2,}(?:[.,]\d+)?\s*(?:руб|₽|р\.)", re.I), "точная сумма в рублях"),
    (re.compile(r"\b\d{7,}\b"), "длинное число — возможно, точная сумма или идентификатор"),
    (re.compile(r"\b(PAYER|BENEFICIARY|GROUP_ID|PAY_AMT)\b"), "служебное поле датасета"),
]


def to_json(obj: Any, pretty: bool = False) -> str:
    """Переводит объект в JSON с русскими буквами"""
    return json.dumps(obj, ensure_ascii=False, indent=2 if pretty else None, default=str)


def normalize(text: str) -> str:
    """Убирает невидимые символы и приводит текст к одному виду"""
    return _ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text or ""))


def neutralize(text: str) -> str:
    """Ломает служебные теги внутри чужого текста"""
    text = _OUR_MARKERS.sub(lambda m: m.group(0).replace("<<<", "‹‹‹").replace(">>>", "›››"), normalize(text))
    return _OUR_TAGS.sub(lambda m: m.group(0).replace("<", "‹").replace(">", "›"), text)


def detect_injection(text: str) -> list[str]:
    """Находит в тексте команды для модели"""
    text = normalize(text)
    return [m.group(0) for rx in _INJ for m in rx.finditer(text)]


def _tag(kind: str, ref: str, body: str, attrs: dict) -> str:
    """Оборачивает текст в тег недоверенных данных"""
    extra = "".join(f' {k}="{neutralize(v)[:120]}"' for k, v in attrs.items() if v)
    return f'<untrusted_{kind} id="{ref}"{extra}>\n{body}\n</untrusted_{kind}>'


def wrap_article(a: Article, max_chars: int = 3500) -> str:
    """Оборачивает новость в тег untrusted_news"""
    body = neutralize(a.text).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rsplit(" ", 1)[0] + " […]"
    return _tag("news", a.ref, f"Заголовок: {neutralize(a.title).strip()}\n{body}",
                {"source": a.source, "date": a.published_at[:10]})


def wrap_untrusted(kind: str, ref: str, text: str, **attrs: str) -> str:
    """Оборачивает чужой текст в тег недоверенных данных"""
    return _tag(kind, ref, neutralize(text).strip(), attrs)


def numbers(text: str) -> set[float]:
    """Находит все числа в тексте"""
    out = set()
    for m in _NUM.finditer(text or ""):
        s = m.group(0).replace("−", "-").replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            out.add(round(float(s), 4))
        except ValueError:
            pass
    return out


_PCT = re.compile(r"\d+(?:[.,]\d+)?(?:\s*[–—-]\s*\d+(?:[.,]\d+)?)?\s*%")


def percents(text: str) -> set[float]:
    """Находит числа, которые стоят перед знаком процента, в том числе в диапазонах"""
    return {x for m in _PCT.finditer(text or "") for x in numbers(m.group(0).replace("-", " ").replace("–", " ").replace("—", " "))}


def stems(text: str, n: int = 5) -> set[str]:
    """Берёт начала значимых слов"""
    return {w.lower()[:n] for w in _WORD.findall(text or "") if w.lower() not in _STOP and len(w) > 2}


def overlap(a: str, b: str) -> float:
    """Считает, какая часть слов первого текста есть во втором"""
    sa, sb = stems(a), stems(b)
    return len(sa & sb) / len(sa) if sa else 0.0


def jaccard(a: str, b: str) -> float:
    """Считает похожесть двух текстов"""
    sa, sb = stems(a), stems(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def periods(text: str) -> set[str]:
    """Находит упомянутые месяцы, кварталы и полугодия"""
    return {k for k, rx in _PERIODS.items() if rx.search(text or "")}


def sentences(text: str) -> int:
    """Считает предложения"""
    return len([s for s in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if s])


def plural(n: int, one: str, few: str, many: str) -> str:
    """Ставит слово в нужную форму после числа"""
    k = abs(n) % 100
    word = many if 11 <= k <= 14 else one if k % 10 == 1 else few if 2 <= k % 10 <= 4 else many
    return f"{n} {word}"


def round_share(x: float) -> str:
    """Округляет долю до пяти процентов"""
    return "менее 5%" if x < 0.05 else f"{int(round(x * 20) * 5)}%"
