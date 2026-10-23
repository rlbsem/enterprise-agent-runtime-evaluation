"""Source-only review archive with exact hashes; never includes local model/runtime state."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = {"README.md", "LICENSE", "requirements.lock", "pyproject.toml", ".gitignore", ".gitattributes"}
FOLDERS = {"src", "tests", "scripts", "docs", ".github"}


def inventory():
    files = {}
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file() or (rel.parts[0] not in FOLDERS and rel.as_posix() not in TOP):
            continue
        if any(p in {"__pycache__", ".pytest_cache", ".ruff_cache"} or p.endswith(".egg-info") for p in rel.parts):
            continue
        if path.is_symlink() or path.suffix in {".gguf", ".sqlite", ".db", ".key", ".pem", ".pyc", ".log"}:
            raise ValueError("private_or_runtime_file_in_public_tree:" + rel.as_posix())
        content = path.read_bytes()
        if any(re.search(pattern, content) for pattern in (
                rb"-----BEGIN (?:RSA |EC |ENCRYPTED |OPENSSH )?PRIVATE KEY-----",
                rb"gh[pousr]_[A-Za-z0-9]{30,}", rb"(?:AKIA|ASIA)[A-Z0-9]{16}",
                rb"Bearer [A-Za-z0-9_-]{25,}")):
            raise ValueError("credential_signature:" + rel.as_posix())
        files[rel.as_posix()] = hashlib.sha256(content).hexdigest()
    return dict(sorted(files.items()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()
    hashes = inventory()
    manifest = ROOT / "package-manifest.json"
    if args.refresh:
        manifest.write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf8", newline="\n")
    elif json.loads(manifest.read_text(encoding="utf8")) != hashes:
        raise ValueError("package_manifest_mismatch")
    if args.zip:
        output = ROOT / "dist/Enterprise_Agent_Real_LLM_Acceptance_Review.zip"
        output.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in [*hashes, "package-manifest.json"]:
                archive.write(ROOT / name, "enterprise-agent-runtime-evaluation/" + name)
        with zipfile.ZipFile(output) as archive:
            assert len(archive.namelist()) == len(hashes) + 1 and archive.testzip() is None
            for name, expected in hashes.items():
                assert hashlib.sha256(archive.read("enterprise-agent-runtime-evaluation/" + name)).hexdigest() == expected
        print(json.dumps({"files": len(hashes), "zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))
    else:
        print(json.dumps({"files": len(hashes), "integrity": "passed"}))


if __name__ == "__main__":
    main()
