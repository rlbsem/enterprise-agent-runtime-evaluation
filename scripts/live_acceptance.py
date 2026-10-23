"""Execute frozen real-model acceptance and, only if eligible, staged local routing."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from gtm_agent.acceptance import (ContextFault, cases, configuration, evaluate, gate, model,
                                  read_effects, source_hashes)
from gtm_agent.contracts import canonical, digest
from gtm_agent.deployment import routed_run
from gtm_agent.engine import Engine
from gtm_agent.local import enterprise_server
from gtm_agent.releases import Registry, REQUIRED_CASES
from gtm_agent.shadow import compare_shadow
from gtm_agent.store import Store

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf8", newline="\n")


def attest(model_file, runtime, official_file, alias):
    official = json.loads(official_file.read_text(encoding="utf-8-sig"))
    fingerprint = hashlib.file_digest(model_file.open("rb"), "sha256").hexdigest()
    if fingerprint != official["file"]["lfs"]["sha256"] or model_file.stat().st_size != official["file"]["size"]:
        raise ValueError("official_model_artifact_mismatch")
    dependencies = {p.name: hashlib.file_digest(p.open("rb"), "sha256").hexdigest()
                    for p in sorted(runtime.parent.glob("*.dll"))}
    try:
        gpu_inventory = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total",
                         "--format=csv,noheader,nounits"], text=True, timeout=5).strip().splitlines()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        gpu_inventory = ["not_observed"]
    return {"repository": official["repository"], "revision": official["revision"],
            "file": model_file.name, "sha256": fingerprint, "bytes": model_file.stat().st_size,
            "alias": alias, "runtime_version": subprocess.check_output([str(runtime), "--version"],
                text=True, stderr=subprocess.STDOUT).strip(),
            "runtime_sha256": hashlib.file_digest(runtime.open("rb"), "sha256").hexdigest(),
            "runtime_dependencies_sha256": dependencies,
            "transport": "private authenticated loopback llama.cpp; reasoning channel excluded",
            "hardware": {"os": platform.system(), "architecture": platform.machine(),
                         "logical_cpus": os.cpu_count(), "available_gpu_name_and_memory_mib": gpu_inventory},
            "financial_cost": {"paid_api_usd": 0, "hardware_energy_cost": "not_metered"}}


def stages(baseline, candidate, workspace, output, url):
    with enterprise_server(workspace) as server:
        store = Store(workspace / "runs.sqlite")
        registry = Registry(workspace / "registry.sqlite")
        for item in (baseline, candidate):
            registry.register(item["configuration"], item)
        a, b = (r["configuration"]["version"] for r in (baseline, candidate))
        registry.bootstrap(a, digest(baseline))
        decision = registry.evaluate(digest(baseline), digest(candidate))
        if decision["decision"] != "eligible":
            raise RuntimeError("registered_candidate_blocked")
        journals = {a: [], b: []}
        configs = {a: baseline["configuration"], b: candidate["configuration"]}
        factories = {name: (lambda name=name: model(configs[name], url, 42, journals[name])) for name in (a, b)}
        before = len(read_effects(server))
        shadow = compare_shadow(store, server, factories[a](), factories[b](), configs[b]["fingerprint"], sorted(REQUIRED_CASES))
        save(output / "shadow.json", {**shadow, "inference": journals})
        if not registry.observation(b, "shadow", shadow):
            return {"decision": "withheld", "reason": "shadow_blocked", "shadow": shadow}
        registry.start_canary(b)
        key = next(str(i) for i in range(1000) if registry.route(str(i), "adoption", b)["canary_selected"])
        canary_run = routed_run(registry, store, server, factories, "adoption", key, b)
        assert canary_run["route"]["version"] == b and canary_run["route"]["mode"] == "shadow"
        canary = compare_shadow(store, server, factories[a](), factories[b](), configs[b]["fingerprint"], ["healthy", "adoption"])
        assert len(read_effects(server)) == before
        save(output / "canary.json", {**canary, "routed_run": canary_run, "inference": journals})
        if not registry.observation(b, "canary", canary):
            return {"decision": "withheld", "reason": "canary_blocked"}
        registry.promote(b, a)
        promoted = routed_run(registry, store, server, factories, "adoption", "active-proof")
        assert promoted["route"]["version"] == b and promoted["status"] == "completed"
        # Damage an adapter input, not an expected answer or saved response. Actual LLM inference still runs.
        faulty_factories = {**factories, b: lambda: ContextFault(factories[b]())}
        fault = routed_run(registry, store, server, faulty_factories, "incident", "fault-proof")
        assert fault["status"] == "escalated", "injected_fault_not_detected"
        assert any(t["kind"] == "guardrail" for t in fault["trace"])
        registry.rollback(b, "Controlled adapter-input corruption was detected against authentic support evidence")
        rollback = routed_run(registry, store, server, factories, "healthy", "after-rollback")
        assert rollback["route"]["version"] == a and rollback["status"] == "completed"
        with registry.tx() as c:
            history = [{**dict(r), "detail": json.loads(r["detail"])} for r in c.execute("SELECT * FROM history ORDER BY seq")]
        result = {"decision": "promoted_then_rolled_back", "scope": "local synthetic effects; no production deployment",
                  "gate": decision, "shadow": shadow, "canary": canary, "routed_canary": canary_run,
                  "promoted_run": promoted, "injected_context_fault": fault, "rollback_run": rollback,
                  "history": history, "inference": journals, "independent_effects": read_effects(server)}
        save(output / "lifecycle.json", result)
        return result


def controls(config, workspace, output, url):
    """Real inference proposes; restricted HTTP identities and exact review still govern effects."""
    journal = []
    with enterprise_server(workspace) as server:
        store = Store(workspace / "runs.sqlite")
        engine = Engine(store, model(config, url, 42, journal), server["url"], server["read_token"], "wrong-test-credential")
        rid = store.create("acme", "adoption", engine.model.mode)
        denied = engine.drive(rid)
        permission = denied["reason"] == "remote_rejected_or_context_changed" and not read_effects(server)
        engine = Engine(store, model(config, url, 43, journal), server["url"], server["read_token"], server["write_token"])
        rid = store.create("acme", "incident", engine.model.mode)
        pending = engine.drive(rid)
        checks = {"wrong_write_identity_blocked": permission, "awaiting_exact_approval": pending["status"] == "awaiting_approval"}
        if checks["awaiting_exact_approval"]:
            for actor, expected, label in (("not-reviewer", "wrong", "wrong_reviewer_blocked"),
                                           ("reviewer", "wrong", "wrong_approval_hash_blocked")):
                try:
                    engine.approve(rid, actor, True, expected)
                except (PermissionError, ValueError):
                    checks[label] = True
                else:
                    checks[label] = False
            with store.tx() as c:
                correct_hash = c.execute("SELECT hash FROM actions WHERE run_id=? AND status='approval'", (rid,)).fetchone()["hash"]
            engine.approve(rid, "reviewer", False, correct_hash)
            checks["rejected_escalation_not_dispatched"] = store.get(rid)["status"] == "rejected"
        effects = read_effects(server)
        checks["only_unprivileged_internal_task_exists"] = len(effects) == 1 and effects[0]["effect"]["tool"] == "create_task"
        if effects:
            original = effects[0]
            with httpx.Client(base_url=server["url"], trust_env=False,
                              headers={"Authorization": "Bearer " + server["write_token"]}) as client:
                replay = client.post("/effects", json=original["effect"], headers={"Idempotency-Key": original["key"]})
                altered = {**original["effect"], "topic": "adoption"}
                conflict = client.post("/effects", json=altered, headers={"Idempotency-Key": original["key"]})
            checks["exact_duplicate_returns_original_receipt"] = replay.status_code == 200 and replay.json() == original
            checks["different_content_same_key_rejected"] = conflict.status_code == 409
            checks["independent_readback_unchanged_after_replay"] = read_effects(server) == effects
        with store.tx() as c:
            traces = [{**dict(r), "detail": json.loads(r["detail"])} for r in c.execute("SELECT * FROM trace ORDER BY seq")]
        proof = {"mode": "actual local LLM and synthetic HTTP", "checks": checks, "passed": all(checks.values()),
                 "inference": journal, "trace": traces, "independent_effects": read_effects(server)}
        save(output / "controls.json", proof)
        return proof


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8097")
    p.add_argument("--key-file", type=Path, required=True)
    p.add_argument("--model-file", type=Path, required=True)
    p.add_argument("--runtime-file", type=Path, required=True)
    p.add_argument("--official-artifact", type=Path, required=True)
    p.add_argument("--alias", default="qwen3-14b")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--development-only", action="store_true", help="Ablation only; cannot qualify or promote")
    p.add_argument("--no-thinking", action="store_true")
    p.add_argument("--bounded-reasoning", action="store_true", help="Frozen v2: 1024/768 reasoning caps, same 1536 total budget")
    args = p.parse_args()
    if args.bounded_reasoning and args.no_thinking:
        p.error("bounded reasoning cannot be combined with no-thinking")
    parsed = urlsplit(args.url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.query:
        raise ValueError("loopback_model_endpoint_required")
    if args.output.exists() or args.workspace.exists():
        raise ValueError("fresh_paths_required")
    os.environ["MODEL_API_KEY"] = args.key_file.read_text(encoding="utf8").strip()
    artifact = attest(args.model_file, args.runtime_file, args.official_artifact, args.alias)
    with httpx.Client(trust_env=False, timeout=10, headers={"Authorization": "Bearer " + os.environ["MODEL_API_KEY"]}) as client:
        response = client.get(args.url.rstrip("/") + "/v1/models")
        response.raise_for_status()
        if args.alias not in {r["id"] for r in response.json()["data"]}:
            raise ValueError("server_alias_mismatch")
        props_response = client.get(args.url.rstrip("/") + "/props")
        props_response.raise_for_status()
        props = props_response.json()
        if Path(props["model_path"].replace("\\\\", "\\")).resolve() != args.model_file.resolve():
            raise ValueError("server_model_file_mismatch")
        artifact["server_build"] = props["build_info"]
    args.output.mkdir(parents=True)
    args.workspace.mkdir(parents=True)
    frozen = source_hashes(ROOT)
    prefix = args.alias
    if args.bounded_reasoning:
        configs = [configuration(prefix + "-reasoning1024-reference", artifact, compact=True,
                                 reasoning_cap=1024, dataset_version="v2"),
                   configuration(prefix + "-reasoning768-candidate", artifact, compact=True,
                                 reasoning_cap=768, dataset_version="v2")]
    else:
        configs = [configuration(prefix + "-reference-v1", artifact, compact=False, thinking=not args.no_thinking),
                   configuration(prefix + "-authority-facts-v4", artifact, compact=True, thinking=not args.no_thinking)]
    seal = {"sealed_at": datetime.now(UTC).isoformat(), "source_sha256": frozen,
            "configurations": configs, "dataset": cases(configs[0].get("dataset_version", "v1")),
            "holdout_rule": "Do not inspect holdout responses or revise prompts/expected outcomes between seal and final gate."}
    save(args.output / "seal.json", seal)
    results = []
    for config in configs:
        name = config["version"]
        with enterprise_server(args.workspace / name) as server:
            result = evaluate(config, server, args.workspace / name, args.output / name, args.url,
                              splits=("development",) if args.development_only else None)
        results.append(result)
        if source_hashes(ROOT) != frozen:
            raise RuntimeError("frozen_source_changed")
    report = gate(*results)
    if not args.development_only:
        control_report = controls(configs[1], args.workspace / "controls", args.output, args.url)
        if not control_report["passed"]:
            report["decision"] = "blocked"
            report["reasons"].append("live_permission_approval_or_replay_control_failed")
    save(args.output / "gate.json", report)
    release = {"decision": "withheld", "reason": "mandatory_live_gate_failed"}
    # Both baseline and candidate must independently satisfy all absolute thresholds.
    if not args.development_only and report["decision"] == "eligible" and gate(results[0], results[0])["decision"] == "eligible":
        release = stages(*results, args.workspace / "stages", args.output, args.url)
    save(args.output / "release.json", release)
    if source_hashes(ROOT) != frozen:
        raise RuntimeError("source_changed_during_release")
    save(args.output / "execution.json", {"executed_at": datetime.now(UTC).isoformat(), "seal_hash": digest(seal),
         "source_sha256": frozen, "model_artifact": artifact, "gate": report["decision"],
         "release": release["decision"], "fresh_inference": True, "native_vendors": "not_executed"})
    print(canonical({"gate": report, "release": release["decision"]}), flush=True)


if __name__ == "__main__":
    main()
