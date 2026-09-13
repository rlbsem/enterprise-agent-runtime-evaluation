import copy
import json

import pytest

from gtm_agent.contracts import digest
from gtm_agent.releases import CRITICAL, REQUIRED_CASES, Registry, compare
from gtm_agent.shadow import compare_shadow
from gtm_agent.model import FixtureModel


def evidence(version="v1"):
    """Fabricated metric inputs ONLY for release-rule unit tests; not committed evaluation evidence."""
    config = {"version": version, "model": "unit-test-only"}
    config["fingerprint"] = digest(config)
    rows = [{"account": c, "sample": 0, "task_success": True, "unauthorized_effects": 0, "duplicate_effects": 0,
             "unsafe_recommendations": 0, "hallucinated_tool_outputs": 0, "argument_errors": 0,
             "grounded_claims": 3, "total_claims": 3} for c in REQUIRED_CASES]
    return {"mode": "fixture", "configuration": config, "case_spec_hash": "unit-test-dataset", "results": rows}


@pytest.mark.parametrize("metric", ["unauthorized_effects", "duplicate_effects", "unsafe_recommendations", "hallucinated_tool_outputs", "argument_errors"])
def test_gate_has_zero_tolerance_for_known_bad_behavior(metric):
    base, candidate = evidence(), evidence("v2")
    candidate["results"][0][metric] = 1
    report = compare(base, candidate)
    assert report["decision"] == "blocked"
    assert any(metric in r for r in report["reasons"])


@pytest.mark.parametrize("case", sorted(CRITICAL))
def test_high_severity_regression_blocks_even_with_other_successes(case):
    base, candidate = evidence(), evidence("v2")
    next(r for r in candidate["results"] if r["account"] == case)["task_success"] = False
    assert f"critical_class_failure:{case}" in compare(base, candidate)["reasons"]


@pytest.mark.parametrize("mutation,reason", [("missing", "incomplete_scenario_coverage"),
                                            ("mode", "evidence_modes_differ"), ("dataset", "datasets_differ"),
                                            ("duplicate", "duplicate_scenario_samples"), ("claims", "groundedness_below_100_percent")])
def test_evaluation_coverage_and_pairing_cannot_be_gamed(mutation, reason):
    base, candidate = evidence(), evidence("v2")
    if mutation == "missing":
        candidate["results"].pop()
    elif mutation == "mode":
        candidate["mode"] = "other"
    elif mutation == "dataset":
        candidate["case_spec_hash"] = "different"
    elif mutation == "duplicate":
        candidate["results"].append(copy.deepcopy(candidate["results"][0]))
    else:
        candidate["results"][0]["grounded_claims"] = 0
    assert reason in compare(base, candidate)["reasons"]


def test_release_lifecycle_uses_real_shadow_and_canary_runs(system, tmp_path):
    store, _, server = system
    reg = Registry(tmp_path / "registry.sqlite")
    a, b = evidence(), evidence("v2")
    for item in (a, b):
        reg.register(item["configuration"], item)
    reg.bootstrap("v1", digest(a))
    assert reg.evaluate(digest(a), digest(b))["decision"] == "eligible"
    with pytest.raises(ValueError):
        reg.promote("v2", "v1")
    report = compare_shadow(store, server, FixtureModel(), FixtureModel(), b["configuration"]["fingerprint"], sorted(REQUIRED_CASES))
    assert report["external_effects"] == 0
    assert reg.observation("v2", "shadow", report)
    reg.start_canary("v2")
    keys = [str(i) for i in range(100)]
    selected = [k for k in keys if reg.route(k, "healthy", "v2")["canary_selected"]]
    assert selected and len(selected) < len(keys)
    assert all(not reg.route(k, "incident", "v2")["canary_selected"] for k in keys)
    canary = compare_shadow(store, server, FixtureModel(), FixtureModel(), b["configuration"]["fingerprint"], ["healthy", "adoption"])
    reg.observation("v2", "canary", canary)
    reg.promote("v2", "v1")
    assert reg.route("account", "healthy")["version"] == "v2"
    reg.rollback("v2", "Synthetic runtime regression detected")
    assert reg.route("account", "healthy")["version"] == "v1"
    with pytest.raises(ValueError):
        reg.promote("v2", "v1")


def test_shadow_pass_flag_cannot_override_bad_decisions(system, tmp_path):
    store, _, server = system
    a, b = evidence(), evidence("v2")
    reg = Registry(tmp_path / "registry.sqlite")
    for item in (a, b):
        reg.register(item["configuration"], item)
    reg.bootstrap("v1", digest(a))
    reg.evaluate(digest(a), digest(b))
    report = compare_shadow(store, server, FixtureModel(), FixtureModel(), b["configuration"]["fingerprint"], sorted(REQUIRED_CASES))
    report["passed"] = True
    report["pairs"][0]["candidate_allowed"] = False
    assert reg.observation("v2", "shadow", report) is False
    with pytest.raises(ValueError):
        reg.start_canary("v2")


def test_registry_rejects_configuration_tampering(tmp_path):
    reg = Registry(tmp_path / "registry.sqlite")
    e = evidence()
    reg.register(e["configuration"], e)
    e["configuration"]["model"] = "silently changed"
    with pytest.raises(ValueError):
        reg.register(e["configuration"], e)


def test_shadow_cannot_resume_a_pending_effect(system):
    store, engine, server = system
    rid = store.create("acme", "adoption", engine.model.mode)
    for _ in range(6):
        engine.advance(rid)
    with store.tx() as c:
        assert c.execute("SELECT count(*) FROM actions WHERE status='pending'").fetchone()[0] == 1
    engine.shadow = True
    engine.advance(rid)
    assert store.get(rid)["reason"] == "shadow_cannot_resume_effect"
    assert json.loads(store.get(rid)["receipts"]) == []
