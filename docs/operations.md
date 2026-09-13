# Reproduction and operator handoff

## Default verification

Install Python 3.12, create/activate a virtual environment, install `requirements.lock`, then install the project with `python -m pip install --no-deps --no-build-isolation -e .`. Run:

```bash
python scripts/verify.py
```

The command checks installed/source parity, dependency consistency and lint; runs all tests; then executes fixture evaluation and the local release lifecycle. It writes proof under `docs/evidence` and uses unique disposable working directories. It never downloads a model or uses a paid key. The test suite does not silently skip unavailable infrastructure.

For the short release demonstration alone:

```bash
python scripts/release_demo.py
```

The report and complete registry history are in `docs/evidence/releases`. Each execution uses a new local registry. Existing operator state is not deleted to make a replay appear successful.

## Actual local model

The checked-in `src/gtm_agent/model-artifact.json` pins the official model repository, revision, file hash and the tested llama.cpp release. The model is approximately 1.12 GB and is excluded from delivery. Download and verify it with:

```bash
python scripts/fetch_model.py
```

Obtain the appropriate platform binary for [llama.cpp release b10809](https://github.com/ggml-org/llama.cpp/releases/tag/b10809). The build host executed the Windows CPU binary. Other platform binaries are available upstream but were not executed here. Use the release's licensing information; the project's MIT license does not relicense the runtime or model.

Start the server in a separate terminal:

```bash
llama-server -m work/models/qwen2.5-1.5b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8093 -c 4096 -t 4 --parallel 1 --api-key local-model-only
```

The supplied key is a local example. Set `MODEL_API_KEY` to match if you choose another key. The adapter sends credentials only as HTTP headers, never into prompts or traces. Keep the server on loopback. Do not expose this local development service to untrusted networks.

Run both frozen configurations and compare:

```bash
python scripts/run_evaluation.py --mode live --version reference-v1 --repeats 2 --workspace work/reference --output docs/evidence/live-reference
python scripts/run_evaluation.py --mode live --version summary-first-v2 --repeats 2 --workspace work/candidate --output docs/evidence/live-candidate
python scripts/compare_versions.py docs/evidence/live-reference/summary.json docs/evidence/live-candidate/summary.json --shadow-model-url http://127.0.0.1:8093
```

These calls perform actual local inference. A health preflight refuses a missing model server. Every run uses a new ID, and all model decisions and effect receipts remain auditable. Repeated seeds do not guarantee bit-for-bit reproducibility across hardware/runtime changes. The final comparison and shadow output are under `docs/evidence/comparison`.

The official [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) describes the model distribution. The [llama.cpp server reference](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) documents the local HTTP and constrained-output interfaces. This project exercises a local adapter; it does not exercise a hosted OpenAI or other paid API.

## Reading the evidence

Each run JSON contains the objective, evaluation and ordered trace. Context entries retain source revisions and retrieved documents. Model entries retain structured decisions, token usage, decoding settings and prompt/input hashes. Policy entries explain refusals. Action, approval and verified-receipt entries connect decisions to outcomes. Private chain-of-thought and raw malformed model text are excluded.

`comparison/gate.json` is the machine-readable release decision. `releases/lifecycle.json` records the executed fixture gate, shadow snapshots, canary routing, promotion, injected regression and rollback. Its routed-run traces show which responder was actually selected after channel changes.

SQLite database files under `work/` are for local inspection and are excluded from publication. A trusted operator can use `Registry` to register immutable version/evidence bodies and perform guarded transitions. This is an executable local library/CLI demonstration, not a deployed multi-user release-management API. Protect the files and process environment if adapting it.

## Before publishing

1. Read the live failures and factual boundaries; preserve them in the public repository.
2. Reproduce `scripts/verify.py` from the extracted artifact. Re-run local inference if changing prompts, model, tools, retrieval or runtime code.
3. Review the complete source and license files, then publish to the intended new GitHub repository yourself.
4. Observe both GitHub Actions jobs and resolve any platform failures before adding a passing-CI claim.
5. If proposing production use, expand the evaluation dataset and identity/deployment controls described in validation; the local fixture promotion is not production approval.
