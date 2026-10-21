import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database.database import Database
from backend.app.database.session import SessionLocal
from backend.app.ingest.parser import NewsParser, SOURCES
from backend.app.demo.select_demo import select_demo, dump_demo_json
from backend.app.config import DATA_DIR


def main() -> None:
    Database.create_all()

    parser = NewsParser()
    items, fetch_stats = parser.collect(sources=SOURCES)
    print("fetch:", fetch_stats)

    db_session = SessionLocal()
    try:
        save_stats = parser.save_to_db(db=db_session, items=items)
        print("save:", save_stats)
    finally:
        db_session.close()

    n = parser.save_to_json(path=str(DATA_DIR / "news.json"), items=items)
    print(f"json: {n} записей")

    companies = select_demo(Database())
    if not companies:
        print("demo-компании не найдены")
        return

    for c in companies:
        print(f"{c.id:12} | {c.client_type:12} | "
              f"{c.revenue / 1e9:6.2f}B ₽ | {c.okved_name[:60]}")

    dump_demo_json(companies, str(DATA_DIR / "demo_companies.json"))


if __name__ == "__main__":
    main()
