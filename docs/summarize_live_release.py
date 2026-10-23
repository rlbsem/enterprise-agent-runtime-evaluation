"""Generate concise comparison tables from completed evidence only."""
import json
import math
from pathlib import Path

DOCS = Path(__file__).resolve().parent
OUTPUT = DOCS / "evidence/live-release"


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def main():
    rows = []
    for name in ("live-reference", "live-candidate"):
        summary = read(DOCS / "evidence" / name / "summary.json")
        results = summary["results"]
        usages = [u for r in results for u in r.get("model_usage", []) if u]
        rows.append({"name": "Original Qwen2.5 / " + summary["configuration"]["version"],
                     "source": "../" + name + "/summary.json", "tasks": len(results),
                     "passed": sum(r["task_success"] for r in results),
                     "unsafe": sum(r["unsafe_recommendations"] for r in results),
                     "unauthorized": sum(r["unauthorized_effects"] for r in results),
                     "duplicates": sum(r["duplicate_effects"] for r in results),
                     "requests": sum(r["model_calls"] for r in results),
                     "completion_tokens": sum(u["completion_tokens"] for u in usages),
                     "latency_mean": None, "latency_p95": None, "release": "withheld (original archive)"})
    executions = sorted(OUTPUT.glob("*/execution.json"), key=lambda p: read(p.parent / "seal.json")["sealed_at"])
    for path in executions:
        folder = path.parent
        seal, release = read(folder / "seal.json"), read(folder / "release.json")
        for config in seal["configurations"]:
            summary = read(folder / config["version"] / "summary.json")
            results = summary["results"]
            requests = [i for p in (folder / config["version"]).glob("*.json") if p.name != "summary.json"
                        for i in read(p)["inference"]]
            latencies = sorted(i["seconds"] for i in requests)
            rows.append({"name": config["version"], "source": folder.name + "/" + config["version"] + "/summary.json",
                "tasks": len(results), "passed": sum(r["task_success"] for r in results),
                "unsafe": sum(r["unsafe_recommendations"] for r in results),
                "unauthorized": sum(r["unauthorized_effects"] for r in results),
                "duplicates": sum(r["duplicate_effects"] for r in results), "requests": len(requests),
                "completion_tokens": summary["usage"]["completion_tokens"],
                "latency_mean": round(sum(latencies) / len(latencies), 3) if latencies else None,
                "latency_p95": round(latencies[math.ceil(.95 * len(latencies)) - 1], 3) if latencies else None,
                "release": release["decision"], "splits": sorted({r["split"] for r in results})})
    latest = next((p.parent for p in reversed(executions)
                   if any(r.get("split") == "holdout" for c in read(p.parent / "seal.json")["configurations"]
                          for r in read(p.parent / c["version"] / "summary.json")["results"])), None)
    lines = ["# Executed model comparison", "",
        "All sources, effects and approvals are synthetic and local. These are recorded model calls, not replayed answers. "
        "Earlier failures remain unchanged. No production release, SaaS integration or commercial outcome is established.", "",
        "| Configuration | Tasks passed | Unsafe recommendations | Unauthorized / duplicate effects | Release boundary |",
        "|---|---:|---:|---:|---|"]
    for row in rows:
        lines.append(f"| [{row['name']}]({row['source']}) | {row['passed']}/{row['tasks']} | {row['unsafe']} | "
                     f"{row['unauthorized']} / {row['duplicates']} | {row['release']} |")
    lines += ["", "Development-only ablations cannot qualify even if all six visible cases pass. "
        "The first Qwen3 holdout is retained as known regression in the later run; fresh cases are sealed separately. "
        "The same engineer authored the known rules and cases. This is not a blind external benchmark.", "",
        "## Observed local inference resources", "",
        "| Configuration | Model requests | Completion tokens | Mean request seconds | p95 request seconds |",
        "|---|---:|---:|---:|---:|"]
    for row in rows:
        mean = row["latency_mean"] if row["latency_mean"] is not None else "not separately recorded"
        p95 = row["latency_p95"] if row["latency_p95"] is not None else "not separately recorded"
        lines.append(f"| {row['name']} | {row['requests']} | {row['completion_tokens']:,} | {mean} | {p95} |")
    lines += ["", "Completion counts include reasoning where enabled; its content is excluded. "
        "p95 uses nearest rank. These are small descriptive host observations, not a controlled capacity benchmark or latency SLA. "
        "Paid API spend is zero; hardware and energy costs were not metered.", ""]
    if latest:
        release = read(latest / "release.json")
        gate = read(latest / "gate.json")
        lines += ["## Latest full acceptance", "", f"Local decision: **{release['decision']}**. "
                  f"[Exact gate]({latest.name}/gate.json) · [Release record]({latest.name}/release.json).", "",
                  "Mandatory gate reasons: " + (", ".join(gate["reasons"]) or "none") + ".", ""]
        if (latest / "lifecycle.json").exists():
            life = read(latest / "lifecycle.json")
            lines += [f"- Fresh shadow: {len(life['shadow']['pairs'])} paired contexts, "
                      f"{life['shadow']['external_effects']} external effects.",
                      f"- Read-only canary: {len(life['canary']['pairs'])} paired contexts plus an actual selected routed run.",
                      f"- Active route: `{life['promoted_run']['route']['version']}`.",
                      f"- Controlled adapter-input corruption: `{life['injected_context_fault']['status']}`; "
                      "not a natural model regression and not a fabricated response.",
                      f"- Subsequent actual rollback route: `{life['rollback_run']['route']['version']}`.",
                      f"- [Full traces, inference and immutable registry history]({latest.name}/lifecycle.json).", ""]
        controls = read(latest / "controls.json")
        lines += [f"[Permission, exact-approval and replay controls]({latest.name}/controls.json): "
                  f"{sum(controls['checks'].values())}/{len(controls['checks'])} checks passed. "
                  "Exact escalation approvals are supplied by the trusted harness, not a measured human review study.", ""]
    (OUTPUT / "summary.md").write_text("\n".join(lines), encoding="utf8", newline="\n")
    (OUTPUT / "summary.json").write_text(json.dumps({"rows": rows, "latest_full_acceptance": latest.name if latest else None}, indent=2)
                                          + "\n", encoding="utf8", newline="\n")
    print(json.dumps({"configurations": len(rows), "latest_full_acceptance": latest.name if latest else None}))


if __name__ == "__main__":
    main()
