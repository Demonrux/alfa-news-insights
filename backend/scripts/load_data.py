import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.database.session import Base, engine, SessionLocal
from backend.app.database.models import (
    Company, CompanyLink, Person, Payment,
)
from backend.app.database.loader import DatasetLoader
from backend.app.config import DATA_DIR


def main() -> None:
    CompanyLink.__table__.drop(bind=engine, checkfirst=True)
    Company.__table__.drop(bind=engine, checkfirst=True)
    Person.__table__.drop(bind=engine, checkfirst=True)
    Payment.__table__.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    loader = DatasetLoader(data_dir=DATA_DIR)

    try:
        t0 = time.time()

        print("[1/6] companies")
        n1 = loader.load_companies(db=db)

        print("[2/6] persons")
        n2 = loader.load_persons(db=db)

        print("[3/6] payments")
        n3 = loader.load_payments(db=db)

        print("[4/6] payments (links)")
        n4 = loader.load_payments_links(db=db)

        print("[5/6] group links")
        n5 = loader.build_group_links(db=db)

        print("[6/6] person links")
        n6 = loader.build_person_links(db=db)

        loader.ensure_indexes(db=db)

        print(f"\nDONE: companies={n1}, persons={n2}, "
              f"payments={n3}, payment_links={n4}, "
              f"group_links={n5}, person_links={n6}")
        print(f"time: {time.time() - t0:.1f}s")

    finally:
        db.close()


if __name__ == "__main__":
    main()
