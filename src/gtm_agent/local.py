"""Ephemeral local HTTP process with isolated synthetic enterprise persistence."""
import os
import secrets
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

from .enterprise import seed


@contextmanager
def enterprise_server(workspace):
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / "enterprise.sqlite"
    seed(path)
    read, write = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "ENTERPRISE_DB": str(path), "READ_TOKEN": read, "WRITE_TOKEN": write}
    with (workspace / "enterprise.log").open("w") as log:
        p = subprocess.Popen([sys.executable, "-m", "uvicorn", "gtm_agent.enterprise:app", "--host", "127.0.0.1",
                              "--port", str(port), "--no-access-log"], env=env, stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            for _ in range(100):
                try:
                    if httpx.get(url + "/health", trust_env=False).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if p.poll() is not None:
                    raise RuntimeError("enterprise process exited; inspect local log")
                time.sleep(0.05)
            else:
                raise RuntimeError("enterprise did not become healthy")
            yield {"url": url, "read_token": read, "write_token": write, "path": path}
        finally:
            p.terminate()
            p.wait(timeout=10)
