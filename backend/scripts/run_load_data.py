import sys
import time
from pathlib import Path
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.database.session import Base, engine, session_scope
from backend.app.database.models import Company, CompanyLink, Person, Payment
from backend.app.database.loader import DatasetLoader
from backend.app.config import DATA_DIR


def main() -> None:
    # для чистой перезаписи
    CompanyLink.__table__.drop(bind=engine, checkfirst=True)
    Company.__table__.drop(bind=engine, checkfirst=True)
    Person.__table__.drop(bind=engine, checkfirst=True)
    Payment.__table__.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)

    loader = DatasetLoader(data_dir=DATA_DIR)

    with tqdm(total=6, desc="Загрузка датасета") as pbar:
        with session_scope() as db:
            t0 = time.time()

            pbar.set_description("[1/6] companies")
            n1 = loader.load_companies(db=db)
            pbar.update(1)

            pbar.set_description("[2/6] persons")
            n2 = loader.load_persons(db=db)
            pbar.update(1)

            pbar.set_description("[3/6] payments raw")
            n3 = loader.load_payments(db=db)
            pbar.update(1)

            pbar.set_description("[4/6] payments links")
            n4 = loader.load_payments_links(db=db)
            pbar.update(1)

            pbar.set_description("[5/6] group links")
            n5 = loader.build_group_links(db=db)
            pbar.update(1)

            pbar.set_description("[6/6] person links")
            n6 = loader.build_person_links(db=db)
            pbar.update(1)

            loader.ensure_indexes(db=db)

    tqdm.write(f"\nDONE: companies={n1}, persons={n2}, "
               f"payments={n3}, payment_links={n4}, "
               f"group_links={n5}, person_links={n6}")
    tqdm.write(f"time: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
