"""Reproduce software and deterministic release evidence without model downloads or paid keys."""
import hashlib
import json
import platform
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import gtm_agent

ROOT = Path(__file__).resolve().parents[1]


def manifest():
    folders = ("src", "tests", "scripts", ".github")
    paths = [p for folder in folders for p in (ROOT / folder).rglob("*")
             if p.is_file() and p.suffix in (".py", ".sql", ".txt", ".json", ".yml") and "__pycache__" not in p.parts
             and not any(part.endswith(".egg-info") for part in p.parts)]
    paths += [ROOT / "pyproject.toml", ROOT / "requirements.lock"]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    import os
    import time
    start = time.monotonic()
    output = ROOT / "docs/evidence"
    output.mkdir(parents=True, exist_ok=True)
    workspace = ROOT / "work/verification" / uuid4().hex
    workspace.mkdir(parents=True)
    installed = Path(gtm_agent.__file__).parent
    for p in (ROOT / "src/gtm_agent").iterdir():
        if p.is_file() and p.read_bytes() != (installed / p.name).read_bytes():
            raise RuntimeError("Installed package differs from source; reinstall before validation")
    before = manifest()
    def run(*args):
        subprocess.run([sys.executable, *args], cwd=ROOT, check=True,
                       env={**os.environ, "ADVERSARIAL_EVIDENCE": str(output / "adversarial")})
    run("-m", "ruff", "check", "src", "tests", "scripts")
    run("-m", "pip", "check")
    run("-m", "pytest", "-q", "--basetemp", str(workspace / "pytest"),
        "-o", "cache_dir=" + str(workspace / "pytest-cache"), "--junitxml", str(output / "tests.xml"))
    run("scripts/run_evaluation.py", "--workspace", str(workspace / "fixture"), "--output", str(output / "fixture"))
    run("scripts/release_demo.py", "--workspace", str(workspace / "releases"), "--output", str(output / "releases"))
    if before != manifest():
        raise RuntimeError("Source changed during validation")
    suite = ET.parse(output / "tests.xml").getroot().find("testsuite")
    result = {"executed_at": datetime.now(UTC).isoformat(), "python": platform.python_version(),
              "sqlite": sqlite3.sqlite_version, "platform": platform.platform(), "tests": int(suite.attrib["tests"]),
              "failures": int(suite.attrib["failures"]), "errors": int(suite.attrib["errors"]),
              "skipped": int(suite.attrib["skipped"]), "seconds": round(time.monotonic() - start, 2),
              "installation": "source" if installed.resolve() == (ROOT / "src/gtm_agent").resolve() else "installed_wheel",
              "source_sha256": before, "hosted_ci": "not_observed" if not os.getenv("GITHUB_ACTIONS") else "workflow_in_progress",
              "model_evaluation": "separate artifacts; this command executes synthetic responders only"}
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {result['tests']} tests; fixture evaluation and local release lifecycle completed.")


if __name__ == "__main__":
    main()
