"""Pair recommendations against identical frozen context; no executor credential is supplied."""
import json

from .contracts import digest
from .enterprise import connection
from .engine import Engine
from .model import FixtureModel


def compare_shadow(store, server, baseline_model, candidate_model, fingerprint, cases):
    pairs = []
    for case in cases:
        with connection(server["path"]) as c:
            before = c.execute("SELECT count(*) FROM effects").fetchone()[0]
        collector = Engine(store, FixtureModel(), server["url"], server["read_token"], "")
        rid = store.create("acme", case, "synthetic_context_collection")
        for _ in range(4):
            collector.advance(rid)
        context = store.get(rid)["context"]
        with store.tx() as c:
            c.execute("UPDATE runs SET status='collected',reason='shadow_context_snapshot' WHERE id=?", (rid,))
        decisions, statuses = [], []
        for model in (baseline_model, candidate_model):
            engine = Engine(store, model, server["url"], server["read_token"], "", shadow=True)
            trial = store.create("acme", case, model.mode)
            with store.tx() as c:
                c.execute("UPDATE runs SET context=? WHERE id=?", (context, trial))
            run = engine.drive(trial)
            trace = store.trace(trial)
            model_decisions = [t["detail"]["decision"] for t in trace if t["kind"] == "model_decision"]
            decisions.append(model_decisions[0] if model_decisions else None)
            statuses.append(run["status"])
        # Normalize semantically irrelevant claim ordering rather than comparing raw prose/JSON bytes.
        for d in decisions:
            if d:
                d["claims"] = sorted(d["claims"], key=lambda x: (x["source"], x["field"]))
        with connection(server["path"]) as c:
            effects = c.execute("SELECT count(*) FROM effects").fetchone()[0] - before
        pairs.append({"case": case, "baseline_input_hash": digest(json.loads(context)),
                      "context_snapshot": json.loads(context),
                      "candidate_input_hash": digest(json.loads(context)), "baseline_decision": decisions[0],
                      "candidate_decision": decisions[1], "candidate_allowed": statuses[1] in ("shadowed", "completed", "abstained"),
                      "external_effects": effects})
    return {"candidate_fingerprint": fingerprint, "pairs": pairs, "external_effects": sum(p["external_effects"] for p in pairs),
            "mode": "non-authoritative paired recommendation comparison", "context_collection": "deterministic scoped reads"}
