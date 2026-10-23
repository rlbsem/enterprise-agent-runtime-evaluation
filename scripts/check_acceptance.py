"""Verify immutable history, source binding, actual-response lineage and current package."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from gtm_agent.acceptance import independent_score, source_hashes
from gtm_agent.contracts import digest, strict_json
from package import inventory

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf8"))


def check():
    historical = load(ROOT / "docs/historical-artifacts.json")
    for name, expected in historical["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, "historical_bytes_changed:" + name
        if (ROOT / ".git").exists():
            blob = subprocess.check_output(["git", "show", historical["revision"] + ":" + name], cwd=ROOT)
            assert hashlib.sha256(blob).hexdigest() == expected, "historical_git_binding_mismatch:" + name
    links = 0
    for path in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf8"), flags=re.S)
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            parsed = urlsplit(target.strip("<>"))
            if parsed.scheme or not parsed.path:
                continue
            assert (path.parent / unquote(parsed.path)).exists(), f"broken_link:{path}:{target}"
            links += 1
    manifests = inventory()
    assert load(ROOT / "package-manifest.json") == manifests, "package_manifest_mismatch"
    trials, responses = 0, 0
    for execution in (ROOT / "docs/evidence/live-release").glob("*/execution.json"):
        folder = execution.parent
        seal = load(folder / "seal.json")
        assert digest(seal) == load(execution)["seal_hash"]
        if seal["source_sha256"] != source_hashes(ROOT):
            snapshot = folder / "source-snapshot"
            pinned = load(folder / "source-commit.json")["commit"]
            for name, expected in seal["source_sha256"].items():
                assert hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == expected, "executed_source_snapshot_changed"
                if (ROOT / ".git").exists():
                    blob = subprocess.check_output(["git", "show", pinned + ":" + name], cwd=ROOT)
                    assert hashlib.sha256(blob).hexdigest() == expected, "executed_source_commit_mismatch"
        archive = folder / "artifact-manifest.json"
        if archive.exists():
            for name, expected in load(archive)["files"].items():
                assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected, "archived_trial_changed"
        case_map = {c["id"]: c for split in ("development", "regression", "holdout") if split in seal["dataset"]
                    for c in seal["dataset"][split]}
        for config in seal["configurations"]:
            assert digest({k: v for k, v in config.items() if k != "fingerprint"}) == config["fingerprint"]
            summary = load(folder / config["version"] / "summary.json")
            assert summary["configuration"] == config
            observed = []
            for path in sorted((folder / config["version"]).glob("*.json")):
                if path.name == "summary.json":
                    continue
                record = load(path)
                row = record["evaluation"]
                case = case_map[row["case_id"]]
                scored, effects = independent_score(case, record["run"], record["trace"], record["independent_effects"])
                assert scored["task_success"] == row["task_success"] and scored["oracle_checks"] == row["oracle_checks"]
                assert len(record["inference"]) == row["inference_requests"]
                decisions = [t["detail"] for t in record["trace"] if t["kind"] == "model_decision"]
                for request in record["inference"]:
                    assert request["input_hash"] == digest(request["request"])
                    assert request["request"]["messages"][0]["content"] == config["prompt"]
                    assert "reasoning_content" not in request
                    # Contract failures remain recorded. Only validated responses may claim structured decisions.
                    if request["finish_reason"] == "stop":
                        matching = [d for d in decisions if d["provider"]["input_hash"] == request["input_hash"]]
                        if matching:
                            raw = strict_json(request["response_text"])
                            decision = matching[0]["decision"]
                            expected_operation = decision["tool"] if decision["kind"] == "call" else decision["kind"]
                            assert raw["operation"] == expected_operation
                    responses += 1
                observed.append(row)
            assert sorted(observed, key=lambda r: (r["account"], r["sample"])) == sorted(
                summary["results"], key=lambda r: (r["account"], r["sample"]))
            trials += len(observed)
        release = load(folder / "release.json")
        if release["decision"] == "promoted_then_rolled_back":
            assert load(folder / "gate.json")["decision"] == "eligible"
            lifecycle = load(folder / "lifecycle.json")
            assert lifecycle["promoted_run"]["route"]["version"] != lifecycle["rollback_run"]["route"]["version"]
            assert lifecycle["injected_context_fault"]["status"] == "escalated"
            assert lifecycle["shadow"]["external_effects"] == lifecycle["canary"]["external_effects"] == 0
    print(json.dumps({"historical_files": len(historical["files"]), "markdown_links": links,
                      "packaged_files": len(manifests), "live_trials": trials, "recorded_model_responses": responses,
                      "native_vendor_execution": "not_executed"}))


if __name__ == "__main__":
    check()
