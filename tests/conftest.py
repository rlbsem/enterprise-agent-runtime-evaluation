from pathlib import Path

import pytest

from gtm_agent.engine import Engine
from gtm_agent.local import enterprise_server
from gtm_agent.model import FixtureModel
from gtm_agent.store import Store


@pytest.fixture
def system(tmp_path):
    with enterprise_server(tmp_path) as server:
        store = Store(tmp_path / "runs.sqlite")
        engine = Engine(store, FixtureModel(), server["url"], server["read_token"], server["write_token"])
        yield store, engine, server


def collect(engine, rid):
    for _ in range(4):
        assert engine.advance(rid)
    return engine.store.get(rid)


def pending(engine, rid):
    for _ in range(40):
        row = engine.store.get(rid)
        if row["status"] == "awaiting_approval":
            return row
        engine.advance(rid)
    raise AssertionError("no approval reached")


@pytest.fixture
def evidence_dir():
    import os
    folder = os.environ.get("ADVERSARIAL_EVIDENCE")
    return Path(folder) if folder else None
