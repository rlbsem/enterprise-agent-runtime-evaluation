"""Independent read-only checks for routed inference, viewer source records and screenshots."""
import hashlib
import json
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parent


def load(path):
    return json.loads(path.read_text(encoding="utf8"))


def verify():
    manifest = load(DOCS / "release-review-manifest.json")
    for name, expected in manifest["inputs"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    html = (DOCS / "release-review.html").read_bytes()
    assert hashlib.sha256(html).hexdigest() == manifest["html_sha256"]
    assert hashlib.sha256((DOCS / "render_release_review.py").read_bytes()).hexdigest() == manifest["generator_sha256"]
    assert hashlib.sha256((DOCS / "release-review.template.html").read_bytes()).hexdigest() == manifest["template_sha256"]
    embedded = re.search(r'<script id="evidence" type="application/json">(.*?)</script>', html.decode("utf8"), re.S)
    data = json.loads(embedded.group(1))
    tasks = 0
    for config in data["configurations"]:
        for task in config["tasks"]:
            actual = load(ROOT / task["path"])
            assert task["record"] == actual and task["row"] == actual["evaluation"]
            tasks += 1
    routed = 0
    for path in (DOCS / "evidence/live-release").glob("*/lifecycle.json"):
        seal = load(path.parent / "seal.json")
        configs = {c["version"]: c for c in seal["configurations"]}
        lifecycle = load(path)
        requests = {r["input_hash"]: r["request"] for group in lifecycle["inference"].values() for r in group}
        for key in ("routed_canary", "promoted_run", "injected_context_fault", "rollback_run"):
            run = lifecycle[key]
            expected = configs[run["route"]["version"]]
            decisions = [t["detail"] for t in run["trace"] if t["kind"] == "model_decision"]
            assert decisions, "routed_run_has_no_actual_inference"
            for decision in decisions:
                provider = decision["provider"]
                assert provider["mode"] == "live_local_llm"
                assert provider["configuration_fingerprint"] == expected["fingerprint"]
                request = requests[provider["input_hash"]]
                assert request["reasoning_budget_tokens"] == expected["decoding"]["reasoning_cap"]
                assert request["messages"][0]["content"] == expected["prompt"]
                routed += 1
        assert lifecycle["routed_canary"]["route"]["mode"] == "shadow"
        assert lifecycle["promoted_run"]["route"]["version"] != lifecycle["rollback_run"]["route"]["version"]
        assert lifecycle["injected_context_fault"]["status"] == "escalated"
        receipts = [t["detail"]["receipt"] for t in lifecycle["promoted_run"]["trace"] if t["kind"] == "verified_receipt"]
        assert sorted(receipts, key=lambda r: r["key"]) == lifecycle["independent_effects"]
        assert len(receipts) == 1 and receipts[0]["effect"]["tool"] == "create_task"
    screenshot_proof = DOCS / "images/live-release/release-review-provenance.json"
    screenshots = 0
    if screenshot_proof.exists():
        proof = load(screenshot_proof)
        assert proof["html_sha256"] == manifest["html_sha256"]
        assert not proof["page_errors"] and not proof["external_network_requests"]
        for name, expected in proof["image_sha256"].items():
            assert hashlib.sha256((screenshot_proof.parent / name).read_bytes()).hexdigest() == expected
            screenshots += 1
        assert all(not audit["violations"] for audit in proof["accessibility"].values())
    print(json.dumps({"viewer_tasks_match_sources": tasks, "routed_actual_inference_decisions_verified": routed,
                      "screenshot_hashes_verified": screenshots, "viewer_has_no_execution_authority": True}))


if __name__ == "__main__":
    verify()
