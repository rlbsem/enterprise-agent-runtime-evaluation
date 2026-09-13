import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from gtm_agent.contracts import canonical, digest
from gtm_agent.engine import Engine
from gtm_agent.enterprise import CASES, connection
from gtm_agent.evaluate import EXPECTED, score
from gtm_agent.local import enterprise_server
from gtm_agent.model import FixtureModel, LocalModel
from gtm_agent.store import Store
from gtm_agent.releases import configuration


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["fixture", "live"], default="fixture")
    p.add_argument("--model-url", default="http://127.0.0.1:8093")
    p.add_argument("--workspace", type=Path, default=Path("work/evaluation"))
    p.add_argument("--output", type=Path, default=Path("docs/evidence/fixture"))
    p.add_argument("--cases", nargs="+", default=list(CASES))
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--version", choices=["reference-v1", "summary-first-v2"], default="reference-v1")
    args = p.parse_args()
    if args.mode == "live":
        import httpx
        httpx.get(args.model_url + "/health", timeout=5, trust_env=False).raise_for_status()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    config = configuration(args.version)
    start = time.monotonic()
    with enterprise_server(args.workspace) as server:
        store = Store(args.workspace / "runs.sqlite")
        for sample in range(args.repeats):
            for case in args.cases:
                model = LocalModel(args.model_url, seed=42 + sample, prompt=config["prompt"]) if args.mode == "live" else FixtureModel()
                engine = Engine(store, model, server["url"], server["read_token"], server["write_token"])
                rid = store.create("acme", case, model.mode)
                # Every case is independent; the incident task loses its response after commit.
                with connection(server["path"]) as c:
                    c.execute("INSERT OR REPLACE INTO faults VALUES (?,?)", (case, canonical(["timeout_after"] if case == "incident" else [])))
                run = engine.drive(rid, reviewer=True)
                trace = store.trace(rid)
                with connection(server["path"]) as c:
                    effects = [{"key": r["key"], "hash": r["hash"], "effect": json.loads(r["payload"])} for r in c.execute("SELECT * FROM effects")]
                result = score(run, trace, effects)
                result["sample"] = sample
                result["model_usage"] = [t["detail"]["provider"].get("usage") for t in trace if t["kind"] == "model_decision"]
                results.append(result)
                artifact = {"run_id": rid, "objective": run["objective"], "evaluation": result, "trace": trace}
                (args.output / f"{case}-{sample}.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
                print(f"{args.mode} {case} sample={sample}: {run['status']} success={result['task_success']} calls={run['calls']}", flush=True)
    if configuration(args.version)["fingerprint"] != config["fingerprint"]:
        raise RuntimeError("Agent configuration changed during evaluation; comparison evidence is invalid")
    summary = {"generated_at": datetime.now(UTC).isoformat(), "mode": args.mode,
               "model_behavior": "actual local LLM inference" if args.mode == "live" else "handwritten synthetic responder; NOT model evaluation",
               "prompt_hash": config["prompt_hash"], "configuration": config,
               "case_spec_hash": digest({"cases": CASES, "expected": {k: sorted(v) for k, v in EXPECTED.items()}}), "seconds": round(time.monotonic() - start, 2),
               "runs": len(results), "task_successes": sum(r["task_success"] for r in results),
               "unauthorized_effects": sum(r["unauthorized_effects"] for r in results),
               "duplicate_effects": sum(r["duplicate_effects"] for r in results), "results": results,
               "approval_behavior": "trusted evaluation harness approves requested escalations; human decision quality not measured"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report = ["# " + ("Executed local model evaluation" if args.mode == "live" else "Deterministic orchestration evaluation"), "",
              summary["model_behavior"], "", f"Task success: {summary['task_successes']}/{summary['runs']}; unauthorized effects: "
              f"{summary['unauthorized_effects']}; duplicate effects: {summary['duplicate_effects']}.", "",
              "| Case | Sample | Status | Task success | Grounded claims | Reason |", "|---|---|---|---|---|---|"]
    report += [f"| {r['account']} | {r['sample']} | {r['status']} | {r['task_success']} | "
               f"{r['grounded_claims']}/{r['total_claims']} | {r['reason']} |" for r in results]
    report += ["", "Small synthetic suite; not a production success-rate estimate. Schema-constrained decoding and independent deterministic "
               "guards are part of this evaluated system. Safety enforcement and model competence are separate measurements. "
               "Trace files contain structured decisions and evidence, never chain-of-thought.", ""]
    (args.output / "report.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
