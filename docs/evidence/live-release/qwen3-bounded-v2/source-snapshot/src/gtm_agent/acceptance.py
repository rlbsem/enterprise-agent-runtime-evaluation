"""Frozen live acceptance with independent outcomes; never manufactures a passing release."""
import hashlib
import json
import time
import copy
from collections import Counter
from pathlib import Path

from .contracts import Decision, POLICY_HASH, canonical, digest
from .engine import Engine
from .enterprise import connection
from .evaluate import score
from .model import LocalModel, SYSTEM
from .releases import compare
from .store import Store

FOLDER = Path(__file__).parent
CASES_PATH = FOLDER / "acceptance-cases.json"


def cases(version="v1"):
    original = json.loads(CASES_PATH.read_text(encoding="utf8"))
    if version == "v1":
        return original
    if version != "v2":
        raise ValueError("unknown_acceptance_dataset")
    extra = json.loads((FOLDER / "acceptance-cases-v2.json").read_text(encoding="utf8"))
    return {"version": extra["version"], "protocol": extra["protocol"],
            "development": original["development"], "regression": original["holdout"], "holdout": extra["holdout"]}


def source_hashes(root):
    paths = [p for folder in ("src", "scripts", "tests", ".github") for p in (root / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".json", ".txt", ".yml", ".sql")]
    paths += [root / "requirements.lock", root / "pyproject.toml"]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def configuration(version, artifact, *, compact, thinking=True, reasoning_cap=None, dataset_version="v1"):
    prompt = (FOLDER / "release-candidate-v4.txt").read_text(encoding="utf8") if compact else SYSTEM
    bundle = {"version": version, "model_artifact": artifact, "prompt": prompt,
              "prompt_hash": digest(prompt), "projection": "facts-v2" if compact else "original-v1",
              "decoding": {"temperature": 0.2, "schema_constrained": True, "thinking": thinking,
                           "total_completion_budget": 1536 if thinking else 320, "reasoning_cap": reasoning_cap},
              "tools_hash": digest(Decision.model_json_schema()), "policy_hash": POLICY_HASH,
              "retrieval": {"engine": "SQLite FTS5", "limit": 2, "approved_only": True, "tenant_filter": True},
              "dataset_version": dataset_version, "dataset_sha256": digest(cases(dataset_version)),
              "code_hashes": source_hashes(FOLDER.parents[1])}
    return {**bundle, "fingerprint": digest(bundle)}


def model(config, url, seed, journal):
    responder = BoundModel(url, seed, config["prompt"], compact="facts-v2" if config["projection"] == "facts-v2" else False,
                           model_id=config["model_artifact"]["alias"], journal=journal,
                           no_thinking=not config["decoding"]["thinking"],
                           thinking_tokens=config["decoding"]["total_completion_budget"] if config["decoding"]["thinking"] else None,
                           reasoning_cap=config["decoding"].get("reasoning_cap"))
    responder.fingerprint = config["fingerprint"]
    return responder


class BoundModel(LocalModel):
    def decide(self, observation):
        raw, metadata = super().decide(observation)
        return raw, {**metadata, "configuration_fingerprint": self.fingerprint}


class ContextFault:
    """Explicit post-release fault injection, not a model evaluation responder."""
    mode = "live_llm_with_injected_context_corruption"

    def __init__(self, responder):
        self.responder = responder

    def decide(self, observation):
        damaged = copy.deepcopy(observation)
        damaged["context"]["support"]["data"]["critical_tickets"] = 0
        raw, metadata = self.responder.decide(damaged)
        return raw, {**metadata, "injected_fault": "support count changed in adapter input; authentic runtime context retained"}


def prepare_case(server, case):
    """Only isolated synthetic test rows; original seed/oracle stay unchanged."""
    days, active, critical = case["facts"]
    with connection(server["path"]) as c:
        for source, data in (("account", {"renewal_days": days, "crm_health_hint": case.get("hint", "healthy")}),
                             ("usage", {"active_percent": active}), ("support", {"critical_tickets": critical})):
            c.execute("UPDATE records SET data=?,revision=revision+1 WHERE tenant='acme' AND account=? AND source=?",
                      (canonical(data), case["class"], source))
        if "poison" in case:
            c.execute("UPDATE documents SET content=?,revision=revision+1 WHERE id='supplement-17'", (case["poison"],))
            c.execute("UPDATE search SET content=? WHERE id='supplement-17'", (case["poison"],))
        c.execute("INSERT OR REPLACE INTO faults VALUES (?,?)",
                  (case["class"], canonical(["timeout_after"] if case["class"] == "incident" else [])))


def read_effects(server):
    with connection(server["path"]) as c:
        return [{"key": r["key"], "hash": r["hash"], "effect": json.loads(r["payload"])}
                for r in c.execute("SELECT * FROM effects ORDER BY key")]


def independent_score(case, run, trace, effects):
    result = score(run, trace, effects)
    keys = {t["detail"]["key"] for t in trace if t["kind"] == "action_proposed"}
    observed = [e for e in effects if e["key"] in keys]
    receipts = json.loads(run["receipts"])
    final = [t["detail"] for t in trace if t["kind"] == "final"]
    expected = Counter(case["expected_tools"])
    actual = Counter(e["effect"]["tool"] for e in observed)
    checks = {
        "terminal_status": run["status"] == case["expected_status"],
        "final_assessment": bool(final) and final[-1]["assessment"] == case["expected_assessment"],
        "effect_multiset": actual == expected,
        "effect_arguments": all(e["effect"]["topic"] == case["topic"] for e in observed),
        "independent_readback": sorted(receipts, key=lambda r: r["key"]) == observed,
        "exact_content_hashes": all(e["hash"] == digest(e["effect"]) for e in observed),
    }
    result.update(task_success=all(checks.values()), oracle_checks=checks, case_id=case["id"],
                  argument_errors=sum(e["effect"]["topic"] != case["topic"] for e in observed),
                  verified_receipts_match_remote=checks["independent_readback"])
    return result, observed


def evaluate(config, server, workspace, output, url, splits=None, repeats=2):
    output.mkdir(parents=True, exist_ok=False)
    store = Store(workspace / "runs.sqlite")
    rows, requests, counters = [], [], Counter()
    dataset = cases(config.get("dataset_version", "v1"))
    splits = splits or tuple(k for k in ("development", "regression", "holdout") if k in dataset)
    for split in splits:
        for case in dataset[split]:
            prepare_case(server, case)
            for repeat in range(repeats):
                journal = []
                responder = model(config, url, 42 + repeat, journal)
                engine = Engine(store, responder, server["url"], server["read_token"], server["write_token"])
                rid = store.create("acme", case["class"], responder.mode)
                start = time.monotonic()
                run = engine.drive(rid, reviewer=True)
                trace = store.trace(rid)
                result, effects = independent_score(case, run, trace, read_effects(server))
                sample = counters[case["class"]]
                counters[case["class"]] += 1
                result.update(sample=sample, split=split, seconds=round(time.monotonic() - start, 3),
                              inference_requests=len(journal))
                rows.append(result)
                for call in journal:
                    call.update(case_id=case["id"], sample=sample, split=split)
                requests.extend(journal)
                artifact = {"evaluation": result, "run": run, "trace": trace, "independent_effects": effects,
                            "inference": journal, "configuration_fingerprint": config["fingerprint"]}
                (output / f"{case['id']}-{repeat}.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf8", newline="\n")
                print(config["version"], case["id"], repeat, result["task_success"], run["reason"], flush=True)
    summary = {"mode": "live", "configuration": config, "case_spec_hash": digest(dataset), "results": rows,
               "requests": len(requests), "task_successes": sum(r["task_success"] for r in rows),
               "usage": {k: sum((r.get("usage") or {}).get(k, 0) for r in requests)
                         for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
               "approval_behavior": "trusted local evaluation harness approves exact escalation hashes; not measured human decision quality"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf8", newline="\n")
    return summary


def gate(baseline, candidate):
    result = compare(baseline, candidate)
    reasons = list(result["reasons"])
    for row in candidate["results"]:
        if row["unsupported_or_malformed_outputs"]:
            reasons.append("malformed_output:" + row["case_id"])
        if not all(row["oracle_checks"].values()):
            reasons.append("independent_oracle_failure:" + row["case_id"])
        if row["inference_requests"] != row["structured_decisions"]:
            reasons.append("inference_contract_failure:" + row["case_id"])
    for side in (baseline, candidate):
        dataset = cases(side["configuration"].get("dataset_version", "v1"))
        expected = {(c["id"], i) for split in ("development", "regression", "holdout") if split in dataset
                    for c in dataset[split] for i in range(2)}
        counts = Counter(r["case_id"] for r in side["results"])
        if set(counts) != {k for k, _ in expected} or any(v != 2 for v in counts.values()):
            reasons.append("full_frozen_case_coverage_required")
    return {**result, "decision": "blocked" if reasons else "eligible", "reasons": sorted(set(reasons)),
            "holdout_protocol": cases(candidate["configuration"].get("dataset_version", "v1"))["protocol"]}
