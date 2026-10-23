"""Build a self-contained, read-only explorer from executed records, never generated outcomes."""
import hashlib
import json
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parent


def build():
    sources, configurations = {}, []

    def read(path):
        content = path.read_bytes()
        sources[path.relative_to(ROOT).as_posix()] = hashlib.sha256(content).hexdigest()
        return json.loads(content)

    for name in ("live-reference", "live-candidate"):
        folder = DOCS / "evidence" / name
        summary = read(folder / "summary.json")
        tasks = []
        for row in summary["results"]:
            path = folder / f"{row['account']}-{row['sample']}.json"
            tasks.append({"row": row, "record": read(path), "path": path.relative_to(ROOT).as_posix()})
        configurations.append({"id": name, "label": "Original Qwen2.5 · " + summary["configuration"]["version"],
                               "scope": "Original six-case experiment, 2 seeds", "tasks": tasks,
                               "release": {"decision": "withheld"}, "gate": None})
    completed = (DOCS / "evidence/live-release").glob("*/execution.json")
    for execution in sorted(completed, key=lambda p: json.loads((p.parent / "seal.json").read_text())["sealed_at"]):
        folder = execution.parent
        seal, release, gate = (read(folder / name) for name in ("seal.json", "release.json", "gate.json"))
        lifecycle = read(folder / "lifecycle.json") if (folder / "lifecycle.json").exists() else None
        for config in seal["configurations"]:
            run_folder = folder / config["version"]
            summary = read(run_folder / "summary.json")
            tasks = []
            records = [p for p in run_folder.glob("*.json") if p.name != "summary.json"]
            for path in sorted(records):
                record = read(path)
                tasks.append({"row": record["evaluation"], "record": record, "path": path.relative_to(ROOT).as_posix()})
            configurations.append({"id": folder.name + "/" + config["version"], "label": config["version"],
                                   "scope": folder.name + " · " + str(len(tasks)) + " recorded tasks",
                                   "tasks": tasks, "release": release, "gate": gate, "lifecycle": lifecycle,
                                   "full_acceptance": any(t["row"].get("split") == "holdout" for t in tasks)})
    data = {"configurations": configurations, "source_sha256": sources}
    encoded = json.dumps(data, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    template = (DOCS / "release-review.template.html").read_text(encoding="utf8")
    assert "\u00c2\u00b7" not in template and "\u00e2\u20ac" not in template, "template_encoding_corruption"
    output = DOCS / "release-review.html"
    output.write_text(template.replace("__EVIDENCE_JSON__", encoded), encoding="utf8", newline="\n")
    manifest = {"inputs": sources, "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "template_sha256": hashlib.sha256((DOCS / "release-review.template.html").read_bytes()).hexdigest(),
                "html_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "scope": "Self-contained projection of recorded local-model evidence; no inference, network or write authority"}
    (DOCS / "release-review-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8", newline="\n")
    print(json.dumps({"configurations": len(configurations), "source_records": len(sources), "html_bytes": output.stat().st_size}))


if __name__ == "__main__":
    build()
