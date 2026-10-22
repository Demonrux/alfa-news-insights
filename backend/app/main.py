import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tqdm import tqdm
from backend.app.database.database import Database
from backend.app.database.session import SessionLocal
from backend.app.ingest.parser import NewsParser, SOURCES
from backend.app.demo.select_demo import select_demo, dump_demo_json
from backend.app.config import DATA_DIR


def main() -> None:
    Database.create_all()
    parser = NewsParser()

    with tqdm(total=4, desc="Пайплайн", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]") as pbar:

        pbar.set_description("Сбор новостей")
        items, fetch_stats = parser.collect(sources=SOURCES)
        pbar.update(1)

        pbar.set_description("Сохранение новостей")
        db_session = SessionLocal()
        try:
            save_stats = parser.save_to_db(db=db_session, items=items)
        finally:
            db_session.close()
        pbar.update(1)

        pbar.set_description("Экспорт в JSON")
        n = parser.save_to_json(path=str(DATA_DIR / "news.json"), items=items)
        pbar.update(1)

        pbar.set_description("Выбор demo-компаний")
        with Database() as db:
            companies = select_demo(db)
        pbar.update(1)

    tqdm.write("\n" + "=" * 50)
    tqdm.write(f"Fetch: {fetch_stats}")
    tqdm.write(f"Saved: {save_stats['saved']} (дублей: {save_stats['duplicates_url']})")
    tqdm.write(f"JSON: {n} записей")
    tqdm.write("=" * 50)

    if not companies:
        tqdm.write("demo-компании не найдены")
        return

    tqdm.write("\nDemo-компании:")
    for c in companies:
        tqdm.write(f"{c.id:12} | {c.client_type:12} | "
                   f"{c.revenue / 1e9:6.2f}B ₽ | {c.label:30} | {c.okved_name[:40]}")

    dump_demo_json(companies, str(DATA_DIR / "demo_companies.json"))
    tqdm.write(f"\nГотово! Файл сохранен: {DATA_DIR / 'demo_companies.json'}")


if __name__ == "__main__":
    main()
