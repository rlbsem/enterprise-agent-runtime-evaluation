import argparse
import json
from pathlib import Path

from gtm_agent.releases import compare


def main():
    p = argparse.ArgumentParser()
    p.add_argument("baseline", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("--output", type=Path, default=Path("docs/evidence/comparison"))
    p.add_argument("--shadow-model-url")
    args = p.parse_args()
    a, b = [json.loads(path.read_text(encoding="utf-8")) for path in (args.baseline, args.candidate)]
    report = compare(a, b)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "gate.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    def total(artifact, metric):
        return sum(row[metric] for row in artifact["results"])
    lines = ["# Agent version regression report", "", f"Evidence mode: **{a['mode']}**. Candidate: **{report['decision'].upper()}**.", "",
             f"Reference: `{a['configuration']['version']}`. Candidate: `{b['configuration']['version']}`. "
             f"Executed samples: {len(a['results'])} per reference and {len(b['results'])} per candidate.", "",
             "The model, tools, retrieval and runtime are held constant. The candidate prompt prioritizes the CRM health hint over numeric evidence.", "",
             "| Measure | Reference | Candidate |", "|---|---|---|"]
    for label, metric in (("Successful tasks", "task_success"), ("Unsafe recommendations (including blocked)", "unsafe_recommendations"),
                          ("Unauthorized effects", "unauthorized_effects"), ("Duplicate effects", "duplicate_effects"),
                          ("Bad effect arguments", "argument_errors"), ("Hallucinated tool outputs", "hallucinated_tool_outputs"),
                          ("Model requests", "model_calls")):
        lines.append(f"| {label} | {total(a, metric)} | {total(b, metric)} |")
    lines += [f"| Grounded numeric claims | {total(a, 'grounded_claims')}/{total(a, 'total_claims')} | "
              f"{total(b, 'grounded_claims')}/{total(b, 'total_claims')} |", "",
              f"Reference evaluated against the absolute thresholds: **{compare(a, a)['decision'].upper()}**. "
              "A higher aggregate score alone cannot overcome critical failures or unsafe recommendations.", "",
             "| Scenario class | Reference task success | Candidate task success |", "|---|---|---|"]
    lines += [f"| {r['class']} | {r['baseline_success']:.0%} | {r['candidate_success']:.0%} |" for r in report["by_class"]]
    lines += ["", "Reasons:", ""] + ["- " + reason for reason in report["reasons"]]
    lines += ["", "The summary-first prompt is an intentional regression mutation. This measures sensitivity of the release gate; "
              "it is not an unbiased contest between providers. A blocked unsafe recommendation still counts as a model-quality defect. "
              "Two seeds per case do not establish a population success rate.", ""]
    (args.output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    if args.shadow_model_url:
        from gtm_agent.local import enterprise_server
        from gtm_agent.model import LocalModel
        from gtm_agent.shadow import compare_shadow
        from gtm_agent.store import Store
        from gtm_agent.releases import REQUIRED_CASES
        from uuid import uuid4
        workspace = Path("work/live-shadow") / uuid4().hex
        with enterprise_server(workspace) as server:
            shadow = compare_shadow(Store(workspace / "runs.sqlite"), server,
                                    LocalModel(args.shadow_model_url, prompt=a["configuration"]["prompt"]),
                                    LocalModel(args.shadow_model_url, prompt=b["configuration"]["prompt"]),
                                    b["configuration"]["fingerprint"], sorted(REQUIRED_CASES))
        (args.output / "shadow.json").write_text(json.dumps(shadow, indent=2), encoding="utf-8")
    print("Candidate", report["decision"], "reasons:", ", ".join(report["reasons"]))


if __name__ == "__main__":
    main()
