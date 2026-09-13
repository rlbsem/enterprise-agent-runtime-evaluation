"""Optional pinned model download; no model weights or runtime binaries are bundled."""
import hashlib
import json
import urllib.request
from pathlib import Path

import gtm_agent


def main():
    info = json.loads(Path(gtm_agent.__file__).with_name("model-artifact.json").read_text())
    target = Path("work/models") / info["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(".download")
        urllib.request.urlretrieve(f"https://huggingface.co/{info['model_repo']}/resolve/{info['revision']}/{info['file']}", temporary)
        temporary.replace(target)
    h = hashlib.sha256()
    with target.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            h.update(chunk)
    if h.hexdigest() != info["sha256"]:
        raise RuntimeError("Model digest mismatch; do not load this file")
    print("Verified model:", target)
    print("Start a local llama.cpp server using the pinned runtime in model-artifact.json. See docs/operations.md.")


if __name__ == "__main__":
    main()
