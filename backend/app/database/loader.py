import math
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database.models import Company, CompanyLink, Person, Payment


class DatasetLoader:
    """Загружает компании и граф связей из CSV в БД"""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)

    # пути к файлам
    @property
    def companies_csv(self) -> Path:
        return self.data_dir / "df_Uid_data_hack.csv"

    @property
    def payments_csv(self) -> Path:
        return self.data_dir / "df_Uid_payment_hack.csv"

    @property
    def persons_csv(self) -> Path:
        return self.data_dir / "df_Fid_Uid_link_hack.csv"

    def load_all(self, db: Session) -> dict:
        n_companies = self.load_companies(db)
        n_persons = self.load_persons(db)
        n_payments = self.load_payments(db)

        n_payments_links = self.load_payments_links(db)
        n_group = self.build_group_links(db)
        n_person = self.build_person_links(db)

        self.ensure_indexes(db)
        return {
            "companies": n_companies,
            "persons": n_persons,
            "payments_raw": n_payments,
            "payment_links": n_payments_links,
            "group_links": n_group,
            "person_links": n_person,
        }

    # компании
    def load_companies(self, db: Session, batch_size: int = 5000) -> int:
        """Загрузить компании

        :param db: сессия SQLAlchemy.
        :param batch_size: размер пачки

        :return: количество записанных компаний
        """
        batch: list[dict] = []
        total = 0
        for row in self._iter_company_rows(self.companies_csv):
            batch.append(row)
            if len(batch) >= batch_size:
                db.bulk_insert_mappings(Company, batch)
                db.commit()
                total += len(batch)
                batch.clear()
                print(f"companies: {total}", end="\r")
        if batch:
            db.bulk_insert_mappings(Company, batch)
            db.commit()
            total += len(batch)
        print(f"companies: {total}")
        return total

    def load_persons(self, db: Session, batch_size: int = 10000) -> int:
        """Загрузить физлиц (связи компаний через собственников)."""
        df = pd.read_csv(self.persons_csv, sep=";", encoding="utf-8")

        batch: list[dict] = []
        total = 0
        for row in df.to_dict(orient="records"):
            batch.append({
                "id": str(uuid.uuid4()),
                "synthetic_f": row["SYNTHETIC_F"],
                "synthetic_u": row["SYNTHETIC_U"],
                "city_name": self._to_py(row.get("CITY_NAME")),
                "rc_name": self._to_py(row.get("RC_NAME")),
            })
            if len(batch) >= batch_size:
                db.bulk_insert_mappings(Person, batch)
                db.commit()
                total += len(batch)
                batch.clear()
        if batch:
            db.bulk_insert_mappings(Person, batch)
            db.commit()
            total += len(batch)

        print(f"persons: {total}")
        return total

    # сырые
    def load_payments(self, db: Session, batch_size: int = 50000) -> int:
        """Загрузить сырые платежи в payments"""
        df = pd.read_csv(self.payments_csv, sep=";", encoding="utf-8")

        before = len(df)
        df = df[df.PAYER != df.BENEFICIARY]
        if before != len(df):
            print(f"payments: убрано self-loops: {before - len(df)}")

        batch: list[dict] = []
        total = 0
        for row in df.to_dict(orient="records"):
            batch.append({
                "id": str(uuid.uuid4()),
                "payer_id": row["PAYER"],
                "beneficiary_id": row["BENEFICIARY"],
                "pay_amt": float(row["PAY_AMT"]),
                "pay_cnt": float(row["PAY_CNT"]),
            })
            if len(batch) >= batch_size:
                db.bulk_insert_mappings(Payment, batch)
                db.commit()
                total += len(batch)
                batch.clear()
                print(f"payments: {total}", end="\r")

        if batch:
            db.bulk_insert_mappings(Payment, batch)
            db.commit()
            total += len(batch)

        print(f"payments: {total}")
        return total

    # __________таблица связей____________

    # платежи (связи типа payment)
    def load_payments_links(self, db: Session, min_pay_amt: float = 0.0, batch_size: int = 50000) -> int:
        """
        Загрузить платежи как связи payment.

        :param db: сессия SQLAlchemy.
        :param min_pay_amt: минимальная величина платежа
        :param batch_size: размер пачки

        self-loops (PAYER == BENEFICIARY) отбрасываются
        дубли пар (PAYER, BENEFICIARY) агрегируются по сумме
        weight = min(1.0, log10(PAY_AMT + 1) / 10).

        :return: количество записанных платежей
        """
        df = pd.read_csv(self.payments_csv, sep=";", encoding="utf-8")
        if min_pay_amt > 0:
            df = df[df.PAY_AMT >= min_pay_amt]

        before = len(df)
        df = df[df.PAYER != df.BENEFICIARY]
        if before != len(df):
            print(f"убрано self-loops: {before - len(df)}")

        before = len(df)
        df = df.groupby(["PAYER", "BENEFICIARY"], as_index=False).agg({
            "PAY_AMT": "sum",
            "PAY_CNT": "sum",
        })
        if before != len(df):
            print(f"убрано дублей платежей: {before - len(df)}")

        batch: list[dict] = []
        total = 0
        for row in df.to_dict(orient="records"):
            pay_amt = float(row["PAY_AMT"])
            pay_cnt = float(row["PAY_CNT"])
            weight = min(1.0, math.log10(pay_amt + 1) / 10.0)
            batch.append(self._link_row(
                src_id=row["PAYER"],
                dst_id=row["BENEFICIARY"],
                link_type="payment",
                weight=weight,
                meta={"pay_amt": pay_amt, "pay_cnt": pay_cnt},
            ))

            if len(batch) >= batch_size:
                db.bulk_insert_mappings(CompanyLink, batch)
                db.commit()
                total += len(batch)
                batch.clear()
                print(f"payments: {total}", end="\r")

        if batch:
            db.bulk_insert_mappings(CompanyLink, batch)
            db.commit()
            total += len(batch)

        print(f"payments: {total}")
        return total

    # группы компаний (тип связи group)
    def build_group_links(self, db: Session, max_members_per_group: int = 20) -> int:
        """Связи внутри одной группы (общий group_id)"""
        rows = (
            db.query(Company.id, Company.group_id, Company.revenue)
            .filter(Company.group_id.isnot(None))
            .all()
        )

        groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for cid, gid, revenue in rows:
            groups[gid].append((cid, revenue or 0.0))

        links: list[dict] = []
        for gid, members in groups.items():
            if len(members) < 2:
                continue

            members = sorted(members, key=lambda x: -x[1])[:max_members_per_group]
            ids = [m[0] for m in members]
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    links.append(self._link_row(
                        src_id=a,
                        dst_id=b,
                        link_type="group",
                        weight=1.0,
                        meta={"group_id": gid}
                    ))

        n = self._insert_links_in_batches(db, links)
        print(f"group links: {n}")
        return n

    # руководители (тип связи person)
    def build_person_links(self, db: Session) -> int:
        """Связи через общих физлиц"""
        df = pd.read_csv(self.persons_csv, sep=";", encoding="utf-8")

        by_person: dict[str, list[str]] = defaultdict(list)
        for row in df.to_dict(orient="records"):
            by_person[row["SYNTHETIC_F"]].append(row["SYNTHETIC_U"])

        links: list[dict] = []
        for person_id, companies in by_person.items():
            companies = list(dict.fromkeys(companies))
            if len(companies) < 2:
                continue
            for i, a in enumerate(companies):
                for b in companies[i + 1:]:
                    links.append(self._link_row(
                        src_id=a,
                        dst_id=b,
                        link_type="person",
                        weight=0.7, meta={"person_id": person_id}
                    ))

        n = self._insert_links_in_batches(db, links)
        print(f"person links: {n}")
        return n

    @staticmethod
    def ensure_indexes(db: Session) -> None:
        for name, col in [
            ("ix_company_links_src_id", "src_id"),
            ("ix_company_links_dst_id", "dst_id"),
            ("ix_company_links_type",   "link_type"),
        ]:
            db.execute(text(
                f"CREATE INDEX IF NOT EXISTS {name} ON company_links({col})"
            ))

        db.commit()

    @staticmethod
    def _to_py(v):
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        if hasattr(v, "item"):
            v = v.item()
            if isinstance(v, float) and math.isnan(v):
                return None
        return v

    @staticmethod
    def _link_row(src_id: str, dst_id: str, link_type: str,
                  weight: float, meta: dict) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "src_id": src_id,
            "dst_id": dst_id,
            "link_type": link_type,
            "weight": weight,
            "meta": meta,
        }

    @classmethod
    def _iter_company_rows(cls, csv_path: Path) -> Iterator[dict]:
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8")

        before = len(df)
        df = (df.sort_values("REVENUE_COMPANY", ascending=False, na_position="last")
                .drop_duplicates(subset=["SYNTHETIC_U"], keep="first")
                .reset_index(drop=True))
        if before != len(df):
            print(f"убрано дубликатов компаний: {before - len(df)} дубликатов SYNTHETIC_U")

        column_fields = {
            "SYNTHETIC_U", "CL_TYPE", "ORG_TYPE", "MAINOKVED_CODE",
            "MAINOKVED_NAME", "REVENUE_COMPANY", "REGION", "CITY", "GROUP_ID",
        }

        for row in df.to_dict(orient="records"):
            profile = {k: cls._to_py(v) for k, v in row.items() if k not in column_fields}
            yield {
                "id": row["SYNTHETIC_U"],
                "client_type": row["CL_TYPE"],
                "org_type": row["ORG_TYPE"],
                "okved_code": str(row["MAINOKVED_CODE"]),
                "okved_name": row["MAINOKVED_NAME"],
                "revenue": float(row.get("REVENUE_COMPANY") or 0.0),
                "region": row["REGION"],
                "city": row["CITY"],
                "group_id": cls._to_py(row.get("GROUP_ID")) or None,
                "negative_mark": bool(float(row.get("NEGATIVEMARK") or 0.0) > 0),
                "profile_json": profile,
            }

    @staticmethod
    def _insert_links_in_batches(db: Session, links: list[dict], batch_size: int = 10000) -> int:
        total = 0
        for i in range(0, len(links), batch_size):
            chunk = links[i:i + batch_size]
            db.bulk_insert_mappings(CompanyLink, chunk)
            db.commit()
            total += len(chunk)

        return total
