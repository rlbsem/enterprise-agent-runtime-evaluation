"""Executed fixture release lifecycle; no claims about live-model quality are made here."""
import json
from pathlib import Path

from gtm_agent.contracts import canonical, digest
from gtm_agent.engine import Engine
from gtm_agent.enterprise import CASES, connection
from gtm_agent.evaluate import EXPECTED, score
from gtm_agent.local import enterprise_server
from gtm_agent.model import FixtureModel
from gtm_agent.releases import Registry, REQUIRED_CASES
from gtm_agent.shadow import compare_shadow
from gtm_agent.store import Store
from gtm_agent.deployment import routed_run


class SummaryFirst(FixtureModel):
    mode = "synthetic_fault_mutant"

    def decide(self, observation):
        raw, meta = super().decide(observation)
        d = json.loads(raw)
        if len(observation["context"]) == 4:
            d.update(kind="finish", tool="none", assessment="healthy")
        return canonical(d), {"mode": self.mode}


class ReorderedClaims(FixtureModel):
    mode = "synthetic_equivalent_candidate"

    def decide(self, observation):
        raw, _ = super().decide(observation)
        d = json.loads(raw)
        d["claims"].reverse()
        return canonical(d), {"mode": self.mode}


def evaluate(store, server, model, version, output):
    config = {"version": version, "model": "handwritten fixture; no LLM execution",
              "behavior": model.mode, "implementation_hash": digest(Path(__file__).read_text(encoding="utf-8"))}
    config["fingerprint"] = digest(config)
    rows = []
    for case in sorted(REQUIRED_CASES):
        engine = Engine(store, model, server["url"], server["read_token"], server["write_token"])
        rid = store.create("acme", case, model.mode)
        run = engine.drive(rid, reviewer=True)
        trace = store.trace(rid)
        with connection(server["path"]) as c:
            effects = [{"key": r["key"], "hash": r["hash"], "effect": json.loads(r["payload"])} for r in c.execute("SELECT * FROM effects")]
        result = score(run, trace, effects)
        rows.append({**result, "sample": 0})
        (output / f"{version}-{case}.json").write_text(json.dumps({"evaluation": result, "trace": trace}, indent=2), encoding="utf-8")
    evidence = {"mode": "fixture", "configuration": config, "case_spec_hash": digest({"cases": CASES, "expected": {k: sorted(v) for k, v in EXPECTED.items()}}), "results": rows}
    (output / f"{version}-summary.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return evidence


def main():
    import argparse
    from uuid import uuid4
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=Path("docs/evidence/releases"))
    p.add_argument("--workspace", type=Path, default=Path("work/releases"))
    args = p.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    # Each run gets its own registry; repeat execution never resets an existing release channel.
    workspace = args.workspace / uuid4().hex
    with enterprise_server(workspace) as server:
        store = Store(workspace / "runs.sqlite")
        registry = Registry(workspace / "registry.sqlite")
        a = evaluate(store, server, FixtureModel(), "fixture-reference", output)
        bad = evaluate(store, server, SummaryFirst(), "fixture-regression", output)
        good = evaluate(store, server, ReorderedClaims(), "fixture-equivalent", output)
        for item in (a, bad, good):
            registry.register(item["configuration"], item)
        registry.bootstrap(a["configuration"]["version"], digest(a))
        blocked = registry.evaluate(digest(a), digest(bad))
        assert blocked["decision"] == "blocked"
        passed = registry.evaluate(digest(a), digest(good))
        assert passed["decision"] == "eligible"
        fingerprint = good["configuration"]["fingerprint"]
        shadow = compare_shadow(store, server, FixtureModel(), ReorderedClaims(), fingerprint, sorted(REQUIRED_CASES))
        assert registry.observation("fixture-equivalent", "shadow", shadow)
        registry.start_canary("fixture-equivalent")
        factories = {"fixture-reference": FixtureModel, "fixture-equivalent": ReorderedClaims}
        routes = [registry.route(str(k), "healthy", "fixture-equivalent") for k in range(100)]
        selected_key = next(str(k) for k, r in enumerate(routes) if r["canary_selected"])
        routed_canary = routed_run(registry, store, server, factories, "adoption", selected_key, "fixture-equivalent")
        assert routed_canary["route"]["mode"] == "shadow" and routed_canary["status"] == "shadowed"
        canary = compare_shadow(store, server, FixtureModel(), ReorderedClaims(), fingerprint, ["healthy", "adoption"])
        assert registry.observation("fixture-equivalent", "canary", canary)
        registry.promote("fixture-equivalent", "fixture-reference")
        promoted = registry.route("example", "healthy")
        promoted_run = routed_run(registry, store, server, factories, "healthy", "example")
        # An executed injected post-release check finds the same summary-first regression.
        from gtm_agent.releases import compare
        runtime_failure = evaluate(store, server, SummaryFirst(), "fixture-runtime-fault", output)
        regression = compare(good, runtime_failure)
        assert regression["decision"] == "blocked"
        registry.rollback("fixture-equivalent", "Injected post-release summary-first regression failed evaluation: " + digest(regression))
        rolled_back = registry.route("example", "healthy")
        rollback_run = routed_run(registry, store, server, factories, "healthy", "example")
        assert promoted["version"] == "fixture-equivalent" and rolled_back["version"] == "fixture-reference"
        with registry.tx() as c:
            history = [{**dict(r), "detail": json.loads(r["detail"])} for r in c.execute("SELECT * FROM history ORDER BY seq")]
        proof = {"mode": "executed deterministic fixture lifecycle; NOT live-model promotion",
                 "blocked_candidate": blocked, "eligible_candidate": passed, "shadow": shadow, "canary": canary,
                 "canary_selected_of_100": sum(r["canary_selected"] for r in routes), "promoted_route": promoted,
                 "routed_canary_run": routed_canary, "promoted_run": promoted_run, "rollback_run": rollback_run,
                 "post_release_injected_regression": regression, "rollback_route": rolled_back, "history": history}
        (output / "lifecycle.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        (output / "report.md").write_text("# Executed release lifecycle\n\nDeterministic fixture behavior, not live-model promotion.\n\n"
            "- Summary-first fault mutant: **BLOCKED** by executed behavioral regression.\n"
            "- Equivalent candidate with reordered claims: offline gate passed.\n"
            "- Shadow: six paired context snapshots; zero external effects.\n"
            f"- Canary: recommendation only; {proof['canary_selected_of_100']}/100 synthetic keys selected by 20% hash buckets.\n"
            "- Candidate promoted locally, then routed back to the reference after an injected failing runtime evaluation.\n"
            "- Rollback changes future version routing; it does not undo business effects.\n", encoding="utf-8")
        print("Blocked regression; passed equivalent candidate; executed shadow/canary, promotion and rollback.")


if __name__ == "__main__":
    main()
