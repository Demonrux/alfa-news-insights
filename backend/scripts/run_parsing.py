import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tqdm import tqdm
from backend.app.database.database import Database
from backend.app.database.session import SessionLocal
from backend.app.ingest.parser import NewsParser, SOURCES
from backend.app.config import DATA_DIR


def main() -> None:
    Database.create_all()
    parser = NewsParser()

    with tqdm(total=3, desc="Парсинг новостей", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]") as pbar:

        pbar.set_description("Сбор новостей (RSS + гидратация)")
        items, fetch_stats = parser.collect(sources=SOURCES)
        pbar.update(1)

        pbar.set_description("Сохранение в БД")
        db_session = SessionLocal()
        try:
            save_stats = parser.save_to_db(db=db_session, items=items)
        finally:
            db_session.close()
        pbar.update(1)

        pbar.set_description("Экспорт в JSON")
        n = parser.save_to_json(path=str(DATA_DIR / "news.json"), items=items)
        pbar.update(1)

    tqdm.write(f"\nFetch: {fetch_stats}")
    tqdm.write(f"Saved: {save_stats['saved']} (дублей: {save_stats['duplicates_url']})")
    tqdm.write(f"JSON: {n} записей")
    tqdm.write("DONE")


if __name__ == "__main__":
    main()
