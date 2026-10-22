import math
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Iterator
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
from tqdm import tqdm

from backend.app.database.models import Company, CompanyLink, Person, Payment
from backend.app.database.database import Database


class DatasetLoader:
    """Загружает компании и граф связей из CSV в БД"""

    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)

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
        """Загрузить компании"""
        batch: list[dict] = []
        total = 0

        for row in self._iter_company_rows(self.companies_csv):
            batch.append(row)
            if len(batch) >= batch_size:
                db.bulk_insert_mappings(Company, batch)
                db.commit()
                total += len(batch)
                batch.clear()

        if batch:
            db.bulk_insert_mappings(Company, batch)
            db.commit()
            total += len(batch)

        tqdm.write(f"companies total: {total}")
        return total

    # физлица
    def load_persons(self, db: Session, batch_size: int = 10000) -> int:
        df = pd.read_csv(self.persons_csv, sep=";", encoding="utf-8")
        batch: list[dict] = []
        total = 0

        for row in tqdm(df.to_dict(orient="records"), desc="  persons", unit="rows", leave=False):
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

        tqdm.write(f"persons: {total}")
        return total

    # платежи
    def load_payments(self, db: Session, batch_size: int = 50000) -> int:
        df = pd.read_csv(self.payments_csv, sep=";", encoding="utf-8")

        from backend.app.database.models import Company
        valid_ids = set(r[0] for r in db.query(Company.id).all())

        before = len(df)
        df = df[df.PAYER != df.BENEFICIARY]
        df = df[df.PAYER.isin(valid_ids) & df.BENEFICIARY.isin(valid_ids)]
        if before != len(df):
            tqdm.write(f"payments: убрано self-loops/неизвестных ID: {before - len(df)}")

        batch: list[dict] = []
        total = 0

        for row in tqdm(df.to_dict(orient="records"), desc="  payments raw", unit="rows", leave=False):
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

        if batch:
            db.bulk_insert_mappings(Payment, batch)
            db.commit()
            total += len(batch)

        tqdm.write(f"payments total: {total}")
        return total

    # связи по платежам
    def load_payments_links(self, db: Session, min_pay_amt: float = 0.0, batch_size: int = 50000) -> int:
        df = pd.read_csv(self.payments_csv, sep=";", encoding="utf-8")

        from backend.app.database.models import Company
        valid_ids = set(r[0] for r in db.query(Company.id).all())

        if min_pay_amt > 0:
            df = df[df.PAY_AMT >= min_pay_amt]

        before = len(df)
        df = df[df.PAYER != df.BENEFICIARY]
        df = df[df.PAYER.isin(valid_ids) & df.BENEFICIARY.isin(valid_ids)]
        if before != len(df):
            tqdm.write(f"payments links: убрано self-loops/неизвестных ID: {before - len(df)}")

        before = len(df)
        df = df.groupby(["PAYER", "BENEFICIARY"], as_index=False).agg({
            "PAY_AMT": "sum",
            "PAY_CNT": "sum",
        })
        if before != len(df):
            tqdm.write(f"payments links: убрано дублей платежей: {before - len(df)}")

        batch: list[dict] = []
        total = 0

        for row in tqdm(df.to_dict(orient="records"), desc="  payments links", unit="rows", leave=False):
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

        if batch:
            db.bulk_insert_mappings(CompanyLink, batch)
            db.commit()
            total += len(batch)

        tqdm.write(f"payments links total: {total}")
        return total

    # связи по группам
    def build_group_links(self, db: Session, max_members_per_group: int = 20) -> int:
        rows = (
            db.query(Company.id, Company.group_id, Company.revenue)
            .filter(Company.group_id.isnot(None))
            .all()
        )

        groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for cid, gid, revenue in rows:
            groups[gid].append((cid, revenue or 0.0))

        links: list[dict] = []
        for gid, members in tqdm(groups.items(), desc="  group links", leave=False):
            if len(members) < 2:
                continue
            members = sorted(members, key=lambda x: -x[1])[:max_members_per_group]
            ids = [m[0] for m in members]
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    links.append(self._link_row(
                        src_id=a, dst_id=b, link_type="group", weight=1.0, meta={"group_id": gid}
                    ))

        n = self._insert_links_in_batches(db, links, desc="  insert groups")
        tqdm.write(f"group links total: {n}")
        return n

    # связи по физлицам
    def build_person_links(self, db: Session) -> int:
        df = pd.read_csv(self.persons_csv, sep=";", encoding="utf-8")

        by_person: dict[str, list[str]] = defaultdict(list)
        for row in df.to_dict(orient="records"):
            by_person[row["SYNTHETIC_F"]].append(row["SYNTHETIC_U"])

        links: list[dict] = []
        for person_id, companies in tqdm(by_person.items(), desc="  person links", leave=False):
            companies = list(dict.fromkeys(companies))
            if len(companies) < 2:
                continue
            for i, a in enumerate(companies):
                for b in companies[i + 1:]:
                    links.append(self._link_row(
                        src_id=a, dst_id=b, link_type="person", weight=0.7, meta={"person_id": person_id}
                    ))

        n = self._insert_links_in_batches(db, links, desc="  insert persons")
        tqdm.write(f"person links total: {n}")
        return n

    @staticmethod
    def ensure_indexes(db: Session) -> None:
        for name, col in [
            ("ix_company_links_src_id", "src_id"),
            ("ix_company_links_dst_id", "dst_id"),
            ("ix_company_links_type", "link_type"),
        ]:
            db.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON company_links({col})"))

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
    def _link_row(src_id: str, dst_id: str, link_type: str, weight: float, meta: dict) -> dict:
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
        df = pd.read_csv(csv_path, sep=";", encoding="utf-8", dtype={"MAINOKVED_CODE": str})

        before = len(df)
        df = (df.sort_values("REVENUE_COMPANY", ascending=False, na_position="last")
              .drop_duplicates(subset=["SYNTHETIC_U"], keep="first")
              .reset_index(drop=True))

        if before != len(df):
            tqdm.write(f"companies: убрано дубликатов SYNTHETIC_U: {before - len(df)}")

        column_fields = {
            "SYNTHETIC_U", "CL_TYPE", "ORG_TYPE", "MAINOKVED_CODE",
            "MAINOKVED_NAME", "REVENUE_COMPANY", "REGION", "CITY", "GROUP_ID",
        }

        skipped_revenue = 0
        skipped_type = 0

        for row in tqdm(df.to_dict(orient="records"), desc="  companies", unit="rows", leave=False):
            if row.get("CL_TYPE") != "CLIENT":
                skipped_type += 1
                continue

            revenue = cls._to_py(row.get("REVENUE_COMPANY"))
            revenue = float(revenue) if revenue is not None else 0.0

            if revenue <= 1000:
                skipped_revenue += 1
                continue

            profile = {k: cls._to_py(v) for k, v in row.items() if k not in column_fields}

            yield {
                "id": row["SYNTHETIC_U"],
                "client_type": row.get("CL_TYPE") or "UNKNOWN",
                "org_type": row.get("ORG_TYPE") or "",
                "okved_code": str(row.get("MAINOKVED_CODE") or ""),
                "okved_name": row.get("MAINOKVED_NAME") or "",
                "revenue": revenue,
                "region": row.get("REGION") or "",
                "city": row.get("CITY") or "",
                "group_id": cls._to_py(row.get("GROUP_ID")),
                "negative_mark": bool(float(row.get("NEGATIVEMARK") or 0.0) > 0),
                "profile_json": profile,
            }

        if skipped_revenue:
            tqdm.write(f"companies: отброшено с выручкой <= 1000: {skipped_revenue}")

        if skipped_type:
            tqdm.write(f"companies: отброшено не-CLIENT: {skipped_type}")

    @staticmethod
    def _insert_links_in_batches(db: Session, links: list[dict], batch_size: int = 10000, desc: str = "insert links") -> int:
        total = 0

        for i in tqdm(range(0, len(links), batch_size), desc=desc, leave=False):
            chunk = links[i:i + batch_size]
            db.bulk_insert_mappings(CompanyLink, chunk)
            db.commit()
            total += len(chunk)

        return total
