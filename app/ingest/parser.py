import hashlib
import html
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import certifi
import feedparser
import httpx
import trafilatura
from sqlalchemy.orm import Session

from app.database.models import News


_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; news-analytics/1.0)"}
_HYDRATE_DELAY = 0.3

# Список источников [имя, ссылка, кооф. доверия]
# TODO дополнить
SOURCES = [
    ("cbr", "https://cbr.ru/rss/eventrss", 0.90),
    ("kommersant-business", "https://www.kommersant.ru/RSS/section-business.xml", 0.85),
    ("kommersant-economics", "https://www.kommersant.ru/rss/section-economics.xml", 0.85),
    ("vedomosti-finance", "https://www.vedomosti.ru/rss/rubric/finance.xml", 0.85),
    ("prime", "https://1prime.ru/export/rss2/index.xml", 0.85),
    ("kommersant", "https://www.kommersant.ru/RSS/news.xml", 0.75),
]

BUSINESS_CATEGORY = ("Бизнес", "Инвестиции", "Экономика", "Финансы", "Индустрии")
ALWAYS_BUSINESS_SOURCES = {"cbr", "prime"}  # TODO пока что костыль

# Источники у которых в RSS пустой body
HYDRATE_SOURCES = {"cbr", "prime"}
_PRIME_START_RE = re.compile(r"ПРАЙМ\.")

#TODO бля тут короче всё на костылях таких что пзд

# Маркеры конца статьи у prime
_PRIME_END_MARKERS = (
    'В разделе "Мнения"',
    "Авторы и АЭИ",
    "Доступ к чату заблокирован",
    "Обсуждение закрыто",
    "Читайте также",
    "Подписывайтесь",
    "Смотрите также",
    "Автор:",
)

# отсюда не получиться нормально спарсить
_NON_ARTICLE_URL_PATTERNS = (
    "/statistics/",
    "/vfs/",
    "/Queries/",
    "/interactive/",
    ".xlsx",
    ".xls",
    ".pdf",
    ".zip",
)


def _is_article_url(url: str) -> bool:
    url_lower = url.lower()
    return not any(p in url_lower for p in _NON_ARTICLE_URL_PATTERNS)


def _clean_prime(text: str) -> str:
    """Обрезать мусор вокруг тела статьи на 1prime.ru."""
    m = _PRIME_START_RE.search(text)
    if m and m.end() < 500:
        text = text[m.end():].strip()

    for marker in _PRIME_END_MARKERS:
        idx = text.find(marker)
        if idx > 200:
            text = text[:idx].strip()
            break

    return text


def clean_text(string: str) -> str:
    if not string:
        return ""

    string = html.unescape(string)
    string = re.sub(r"<[^>]+>", " ", string)
    string = re.sub(r"\s+", " ", string).strip()
    string = re.sub(r'([.!?])([«»"\'A-ZА-ЯЁ])', r'\1 \2', string)
    return string


@dataclass
class NewsItem:
    source: str
    source_authority: float
    title: str
    body: str
    url: str
    published_at: Optional[datetime]
    categories: list[str] = field(default_factory=list)

    def raw_hash(self) -> str:
        return hashlib.sha256(f"{self.title}||{self.body}".encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_authority": self.source_authority,
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "categories": self.categories,
            "raw_hash": self.raw_hash(),
        }


class NewsParser:
    """RSS-парсер новостей"""
    def __init__(self, sources: list[tuple[str, str, float]] | None = None,
                 hydrate_sources: set[str] | None = None):
        self.sources = sources if sources is not None else SOURCES
        self.hydrate_sources = (
            hydrate_sources if hydrate_sources is not None else HYDRATE_SOURCES
        )

    def collect(self, sources=None, business_only: bool = True, hydrate: bool = True) -> tuple[list[NewsItem], dict]:
        """Собрать новости из источников.

        :param sources: список источников [name, url, authority]
        :param business_only: оставить только бизнес-новости
        :param hydrate: дотягивать полный текст для источников из hydrate_sources.
        :return: кортеж (items, fetch_stats)
        """
        sources = sources if sources is not None else self.sources
        items: list[NewsItem] = []
        fetch_stats: dict = {}

        for source, url, authority in sources:
            src: dict = {"fetched": 0, "business": 0}
            try:
                fetched = self._fetch(source=source, url=url, authority=authority)
            except Exception as e:
                fetch_stats[source] = {"error": str(e)}
                continue

            src["fetched"] = len(fetched)
            if business_only:
                fetched = [i for i in fetched if self._is_business(i)]
            src["business"] = len(fetched)

            if hydrate and source in self.hydrate_sources:
                fetched = self._hydrate_items(fetched, source=source)

            items.extend(fetched)
            fetch_stats[source] = src

        return items, fetch_stats

    def save_to_db(self, db: Session, items: list[NewsItem]) -> dict:
        """Сохранить новости в таблицу ``news``.

        :param db: сессия SQLAlchemy.
        :param items: список новостей.
        :return: save_stats - словарь со статистикой:
        """
        per_source: dict = {}

        for item in items:
            per_source.setdefault(item.source, {"saved": 0, "duplicates_url": 0, "duplicates_hash": 0})

        save_stats = {
            "saved": 0,
            "duplicates_url": 0,
            "duplicates_hash": 0,
            "skipped_empty": 0,
            "errors": 0,
            "per_source": per_source,
        }

        by_source: dict[str, list[NewsItem]] = {}
        for item in items:
            by_source.setdefault(item.source, []).append(item)

        for source, source_items in by_source.items():
            src = per_source[source]
            for item in source_items:
                self._save_item(db=db, item=item, stats=save_stats, src_stats=src)
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                save_stats["errors"] += 1
                src["error"] = f"commit: {e}"

        return save_stats

    @staticmethod
    def save_to_json(path: str, items: list[NewsItem], dedup: bool = True) -> int:
        """Сохранить items в JSON-файл.

        :param path: путь к файлу (например, ``"data/news.json"``).
        :param items: список новостей.
        :param dedup: схлопнуть дубли по url и raw_hash в памяти.
        :return: количество записей в файле.
        """
        if dedup:
            seen_urls: set[str] = set()
            seen_hashes: set[str] = set()
            unique: list[NewsItem] = []

            for item in items:
                h = item.raw_hash()
                if item.url in seen_urls or h in seen_hashes:
                    continue
                seen_urls.add(item.url)
                seen_hashes.add(h)
                unique.append(item)

            items = unique

        payload = [item.to_dict() for item in items]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return len(payload)

    def _fetch(self, source: str, url: str, authority: float) -> list[NewsItem]:
        """Скачать RSS через httpx (SSL через certifi) и распарсить."""
        try:
            resp = httpx.get(
                url,
                timeout=20.0,
                follow_redirects=True,
                verify=certifi.where(),
                headers=_HEADERS,
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except httpx.HTTPError as e:
            print(f"[{source}] fetch error: {e}")
            return []

        if feed.bozo:
            print(f"[{source}] WARN: {feed.bozo_exception}")
        return [self._parse_entry(source, authority, e) for e in feed.entries]

    def _parse_entry(self, source: str, authority: float, entry) -> NewsItem:
        """Один ``feedparser.entry`` → ``NewsItem``."""
        return NewsItem(
            source=source,
            source_authority=authority,
            title=clean_text(getattr(entry, "title", "")),
            body=self._extract_body(entry=entry),
            url=getattr(entry, "link", "").strip(),
            published_at=self._parse_date(entry=entry),
            categories=[t.get("term") for t in getattr(entry, "tags", []) if t.get("term")],
        )

    def _hydrate_items(self, items: list[NewsItem], source: str = "") -> list[NewsItem]:
        """Гидратировать только статьи. Не-статьи и пустые — отбросить."""
        hydrated = 0
        result: list[NewsItem] = []
        total = len(items)

        for i, item in enumerate(items, 1):
            if len(item.body) < 100:
                if not _is_article_url(item.url):
                    print(f"  [{source}] {i}/{total} — skip")
                    continue

                time.sleep(_HYDRATE_DELAY)
                full = self._fetch_full_text(item.url)
                if full:
                    item.body = full
                    hydrated += 1

                if i % 10 == 0 or i == total:
                    print(f"[{source}] {i}/{total} — гидратировано: {hydrated}")

            result.append(item)

        print(f"[{source}] готово: {hydrated}/{total} гидратировано")
        return result

    @staticmethod
    def _fetch_full_text(url: str) -> str:
        """Скачать страницу и вытащить основной текст"""
        try:
            resp = httpx.get(
                url, timeout=15.0, follow_redirects=True,
                verify=certifi.where(), headers=_HEADERS,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[hydrate] {url}: {e}")
            return ""

        text = trafilatura.extract(
            resp.content,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not text:
            return ""

        text = clean_text(text)

        if "1prime.ru" in url:
            text = _clean_prime(text)

        return text

    @staticmethod
    def _extract_body(entry) -> str:
        """Достать body из summary / content / description."""
        body = clean_text(getattr(entry, "summary", ""))
        if body:
            return body

        content = getattr(entry, "content", None)
        if content:
            try:
                body = clean_text(content[0].get("value", ""))
                if body:
                    return body
            except (IndexError, AttributeError, TypeError):
                pass

        return clean_text(getattr(entry, "description", ""))

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """Извлечь дату из feedparser entry (naive UTC)"""
        for key in ("published_parsed", "updated_parsed"):
            value = getattr(entry, key, None)
            if value:
                try:
                    return datetime(*value[:6])
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _is_business(item: NewsItem) -> bool:
        """True, если новость из бизнес-раздела или из ALWAYS_BUSINESS_SOURCES."""
        if item.source in ALWAYS_BUSINESS_SOURCES:
            return True
        if not item.categories:
            return True
        return any(c.startswith(BUSINESS_CATEGORY) for c in item.categories)

    @staticmethod
    def _save_item(db: Session, item: NewsItem, stats: dict, src_stats: dict) -> None:
        """Дедуп по url и raw_hash """
        if not item.url or not item.title:
            stats["skipped_empty"] += 1
            return

        if item.source in HYDRATE_SOURCES and len(item.body) < 100:
            stats["skipped_empty"] += 1
            return

        if db.query(News.id).filter(News.url == item.url).first():
            src_stats["duplicates_url"] += 1
            stats["duplicates_url"] += 1
            return

        item_hash = item.raw_hash()
        if db.query(News.id).filter(News.raw_hash == item_hash).first():
            src_stats["duplicates_hash"] += 1
            stats["duplicates_hash"] += 1
            return

        db.add(News(
            source=item.source,
            source_authority=item.source_authority,
            title=item.title,
            body=item.body,
            url=item.url,
            categories=item.categories,
            published_at=item.published_at,
            raw_hash=item_hash,
        ))
        src_stats["saved"] += 1
        stats["saved"] += 1