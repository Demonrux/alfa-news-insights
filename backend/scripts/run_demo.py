import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tqdm import tqdm
from backend.app.database.database import Database
from backend.app.demo.select_demo import select_demo, dump_demo_json
from backend.app.config import DATA_DIR


def main() -> None:
    with tqdm(total=2, desc="Выбор demo-компаний", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]") as pbar:

        pbar.set_description("Поиск компаний по профилям")
        with Database() as db:
            companies = select_demo(db)
        pbar.update(1)

        pbar.set_description("Сохранение в JSON")
        if not companies:
            tqdm.write("\ndemo-компании не найдены")
            return

        dump_demo_json(companies, str(DATA_DIR / "demo_companies.json"))
        pbar.update(1)

    tqdm.write("\n" + "=" * 50)
    tqdm.write(f"Найдено {len(companies)} demo-компаний:")
    for c in companies:
        tqdm.write(f"  {c.id:12} | {c.client_type:10} | "
                   f"{c.revenue / 1e9:6.2f}B ₽ | {c.label:30} | {c.okved_name[:40]}")
    tqdm.write("=" * 50)
    tqdm.write(f"\nDONE: Файл: {DATA_DIR / 'demo_companies.json'}")


if __name__ == "__main__":
    main()
