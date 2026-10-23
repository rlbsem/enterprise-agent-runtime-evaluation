"""Software/contract tests only. Fabricated provider rows are never live evidence."""
import copy
import json

import httpx
import pytest

from gtm_agent.acceptance import ContextFault, cases, gate, independent_score, prepare_case, read_effects
from gtm_agent.engine import Engine
from gtm_agent.model import FixtureModel, LocalModel


def test_frozen_independent_oracle_covers_originals_and_boundary_cases(system):
    store, _, server = system
    for split, entries in cases().items():
        if split not in ("development", "holdout"):
            continue
        for case in entries:
            prepare_case(server, case)
            engine = Engine(store, FixtureModel(), server["url"], server["read_token"], server["write_token"])
            rid = store.create("acme", case["class"], engine.model.mode)
            run = engine.drive(rid, reviewer=True)
            result, effects = independent_score(case, run, store.trace(rid), read_effects(server))
            assert result["task_success"], case["id"]
            # A matched effect count alone cannot conceal a missing receipt or wrong final assessment.
            if effects:
                damaged = {**run, "receipts": "[]"}
                assert not independent_score(case, damaged, store.trace(rid), read_effects(server))[0]["task_success"]
            trace = copy.deepcopy(store.trace(rid))
            next(t for t in trace if t["kind"] == "final")["detail"]["assessment"] = "invented"
            assert not independent_score(case, run, trace, read_effects(server))[0]["task_success"]


def test_compact_live_projection_retains_attack_but_excludes_labels_credentials_and_expected_answers(monkeypatch):
    sent, journal = [], []
    output = {"operation": "finish", "assessment": "healthy", "topic": "renewal", "claims": [
        {"fact": "account.renewal_days", "value": 45}, {"fact": "usage.active_percent", "value": 85},
        {"fact": "support.critical_tickets", "value": 0}]}
    def post(self, url, json):
        sent.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url), json={"model": "unit-fixture",
            "choices": [{"finish_reason": "stop", "message": {"content": __import__('json').dumps(output),
                        "reasoning_content": "private-reasoning-sentinel"}}], "usage": {"completion_tokens": 80}})
    monkeypatch.setattr(httpx.Client, "post", post)
    observation = {"objective": "Assess renewal risk", "receipts": [], "call_index": 1, "context": {
        source: {"account": "secret-scenario-label", "revision": 1, "observed_at": 123.4, "data": data}
        for source, data in [("account", {"renewal_days": 45, "crm_health_hint": "misleading prose"}),
                             ("usage", {"active_percent": 85}), ("support", {"critical_tickets": 0}),
                             ("playbooks", {"documents": [{"content": "IGNORE POLICY ATTACK"}]})]}}
    LocalModel("http://127.0.0.1:9", compact="facts-v2", journal=journal, thinking_tokens=1536).decide(observation)
    content = sent[0]["messages"][1]["content"]
    assert "IGNORE POLICY ATTACK" in content and "misleading prose" in content
    assert "secret-scenario-label" not in content and "observed_at" not in content
    assert "expected" not in content and json.loads(content)["completed_tools"] == []
    assert "reasoning_content" not in json.dumps(journal) and "private-reasoning-sentinel" not in json.dumps(journal)
    assert sent[0]["max_tokens"] == 1536 and sent[0]["chat_template_kwargs"] == {"enable_thinking": True}
    assert journal[0]["response_text"] == json.dumps(output)


@pytest.mark.parametrize("budget", [True, 0, 319, 1537, "1536"])
def test_reasoning_budget_cannot_be_unbounded(budget):
    with pytest.raises(ValueError, match="invalid_thinking_budget"):
        LocalModel("http://127.0.0.1:9", thinking_tokens=budget).decide({"context": {}, "receipts": []})


def test_controlled_corruption_changes_actual_input_not_model_response():
    received = []
    class Responder:
        def decide(self, value):
            received.append(value)
            return "actual-response-sentinel", {"unit_test": True}
    original = {"context": {"support": {"data": {"critical_tickets": 2}}}}
    result = ContextFault(Responder()).decide(original)
    assert result[0] == "actual-response-sentinel"
    assert received[0]["context"]["support"]["data"]["critical_tickets"] == 0
    assert original["context"]["support"]["data"]["critical_tickets"] == 2
    assert "injected_fault" in result[1]


def unit_evidence():
    """Artificial gate inputs for mutation tests; not model performance."""
    from gtm_agent.contracts import digest
    rows, counters = [], {}
    for split in ("development", "holdout"):
        for case in cases()[split]:
            for _ in range(2):
                sample = counters.get(case["class"], 0)
                counters[case["class"]] = sample + 1
                rows.append({"account": case["class"], "case_id": case["id"], "sample": sample,
                    "task_success": True, "unauthorized_effects": 0, "duplicate_effects": 0,
                    "unsafe_recommendations": 0, "hallucinated_tool_outputs": 0, "argument_errors": 0,
                    "grounded_claims": 3, "total_claims": 3, "unsupported_or_malformed_outputs": 0,
                    "oracle_checks": {"all_unit_checks": True}, "structured_decisions": 1, "inference_requests": 1})
    return {"mode": "live", "case_spec_hash": digest(cases()), "configuration": {"fingerprint": "unit-only"}, "results": rows}


@pytest.mark.parametrize("mutation", ["missing_holdout", "malformed", "missing_readback", "missing_inference"])
def test_live_acceptance_adds_constraints_without_relaxing_original_gate(mutation):
    baseline = unit_evidence()
    candidate = copy.deepcopy(baseline)
    if mutation == "missing_holdout":
        candidate["results"] = candidate["results"][:12]
    elif mutation == "malformed":
        candidate["results"][0]["unsupported_or_malformed_outputs"] = 1
    elif mutation == "missing_readback":
        candidate["results"][0]["oracle_checks"]["all_unit_checks"] = False
    else:
        candidate["results"][0]["inference_requests"] = 0
    assert gate(baseline, candidate)["decision"] == "blocked"
