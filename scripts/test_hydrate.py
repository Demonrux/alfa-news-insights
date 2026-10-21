# scripts/test_hydrate.py
from app.ingest.parser import NewsParser

urls = [
    "https://1prime.ru/20261020/stavka-874330135.html",
    "https://1prime.ru/20261020/nbka-874407827.html",
    "https://www.cbr.ru/press/event/?id=32917",
]

for u in urls:
    text = NewsParser._fetch_full_text(u)
    print(f"\n=== {u} ===")
    print(f"len: {len(text)}")
    print(f"start: {text[:200]!r}")
    print(f"end:   {text[-200:]!r}")