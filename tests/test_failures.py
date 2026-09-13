import json

import pytest

from gtm_agent.contracts import canonical
from gtm_agent.enterprise import connection
from gtm_agent.evaluate import score
from gtm_agent.releases import compare
from test_agent import remote
from test_releases import evidence


@pytest.mark.parametrize("mode", ["429", "500", "timeout_before", "timeout_after"])
def test_network_recovery_preserves_one_business_effect(system, mode):
    store, engine, server = system
    with connection(server["path"]) as c:
        c.execute("INSERT INTO faults VALUES ('adoption',?)", (canonical([mode]),))
    rid = store.create("acme", "adoption", engine.model.mode)
    result = engine.drive(rid)
    assert result["status"] == "completed"
    assert len(remote(server)) == 1
    with store.tx() as c:
        attempts = c.execute("SELECT attempts FROM actions WHERE run_id=?", (rid,)).fetchone()[0]
    assert attempts == (1 if mode == "timeout_after" else 2)
    if mode == "timeout_after":
        assert score(result, store.trace(rid), remote(server))["reconciled_effects"] == 1


def test_retry_exhaustion_stops_without_erasing_unknown_intent(system):
    store, engine, server = system
    with connection(server["path"]) as c:
        c.execute("INSERT INTO faults VALUES ('adoption',?)", (canonical(["500"] * 3),))
    rid = store.create("acme", "adoption", engine.model.mode)
    assert engine.drive(rid)["reason"] == "effect_retry_exhausted"
    with store.tx() as c:
        action = c.execute("SELECT * FROM actions WHERE run_id=?", (rid,)).fetchone()
        assert action["attempts"] == 3 and action["status"] == "pending"
    assert not remote(server)


@pytest.mark.parametrize("data", [{"active_percent": "twenty"}, {"active_percent": 50, "api_key": "SYNTHETIC_SECRET"}])
def test_malformed_or_unapproved_context_never_reaches_model(system, data):
    store, engine, server = system
    with connection(server["path"]) as c:
        c.execute("UPDATE records SET data=? WHERE source='usage' AND account='adoption'", (canonical(data),))
    rid = store.create("acme", "adoption", engine.model.mode)
    result = engine.drive(rid)
    assert result["reason"] == "invalid_tool_result" and result["calls"] == 0
    assert "SYNTHETIC_SECRET" not in json.dumps(store.trace(rid))


@pytest.mark.parametrize("field,value", [("task_success", "false"), ("grounded_claims", -1), ("sample", True)])
def test_gate_rejects_coerced_or_invalid_metrics(field, value):
    baseline, candidate = evidence(), evidence("v2")
    candidate["results"][0][field] = value
    with pytest.raises(ValueError):
        compare(baseline, candidate)
