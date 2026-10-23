"""Single-host durable state. All transactions end before model or enterprise HTTP calls."""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .contracts import POLICY_HASH, canonical


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.tx() as c:
            c.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def create(self, tenant, account, mode, objective="Assess renewal risk and arrange evidenced follow-up"):
        rid = str(uuid4())
        with self.tx() as c:
            c.execute("INSERT INTO runs(id,tenant,account,objective,model_mode,policy,created) VALUES (?,?,?,?,?,?,?)",
                      (rid, tenant, account, objective, mode, POLICY_HASH, time.time()))
            self.log(c, rid, "objective", {"objective": objective, "tenant": tenant, "account": account, "mode": mode,
                                           "policy": POLICY_HASH})
        return rid

    def get(self, rid):
        with self.tx() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            if not row:
                raise LookupError("run_not_found")
            return dict(row)

    def claim(self, rid, duration=180):
        now, token = time.time(), str(uuid4())
        with self.tx() as c:
            row = c.execute("UPDATE runs SET lease=?,lease_until=? WHERE id=? AND status='running' "
                            "AND retry_at<=? AND (lease IS NULL OR lease_until<?) RETURNING *",
                            (token, now + duration, rid, now, now)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def log(c, rid, kind, detail):
        c.execute("INSERT INTO trace(run_id,at,kind,detail) VALUES (?,?,?,?)", (rid, time.time(), kind, canonical(detail)))

    def trace(self, rid):
        import json
        with self.tx() as c:
            return [{**dict(r), "detail": json.loads(r["detail"])} for r in c.execute(
                "SELECT * FROM trace WHERE run_id=? ORDER BY seq", (rid,))]
