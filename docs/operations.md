# Reproduction and operator handoff

## Default verification

Install Python 3.12, create/activate a virtual environment, install `requirements.lock`, then install the project with `python -m pip install --no-deps --no-build-isolation -e .`. Run:

```bash
python scripts/verify.py
```

The command checks installed/source parity, dependency consistency and lint; runs all tests; then executes fixture evaluation and the local release lifecycle. It writes fresh proof under ignored `work/verification-evidence` and uses unique disposable working directories. `--output` can select another directory outside the historical evidence tree. It never downloads a model or uses a paid key. The test suite does not silently skip unavailable infrastructure.

For the short release demonstration alone:

```bash
python scripts/release_demo.py --output work/fixture-release-proof --workspace work/fixture-release-state
```

The fresh report and complete registry history are in `work/fixture-release-proof`; the original record in `docs/evidence/releases` is immutable. Each execution uses a new local registry. Existing operator state is not deleted to make a replay appear successful.

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
python scripts/run_evaluation.py --mode live --version reference-v1 --repeats 2 --workspace work/reference --output work/live-reference
python scripts/run_evaluation.py --mode live --version summary-first-v2 --repeats 2 --workspace work/candidate --output work/live-candidate
python scripts/compare_versions.py work/live-reference/summary.json work/live-candidate/summary.json --output work/comparison --shadow-model-url http://127.0.0.1:8093
```

These calls perform actual local inference. A health preflight refuses a missing model server. Every run uses a new ID, and all model decisions and effect receipts remain auditable. Repeated seeds do not guarantee bit-for-bit reproducibility across hardware/runtime changes. The new comparison and shadow output are under `work/comparison`; archived outputs are not replaced.

## Frozen live release acceptance

See [the executed acceptance record and commands](live-release-acceptance.md) for the Qwen3 reasoning candidate, independent boundary cases, exact model/runtime hashes and staged routing. The original small-model commands above reproduce that older configuration only. Neither reading recorded responses nor running the fixture verifier constitutes fresh inference.

Validate archive bytes, new source binding, response lineage, links and package integrity without a GPU:

```bash
python scripts/check_acceptance.py
python scripts/package.py --zip
```

After an intentional reviewed source or documentation change, `python scripts/package.py --refresh --zip` regenerates the current delivery manifest. It does not rewrite historical evaluation hashes. Live acceptance requires an already available local model, runtime and private key file; it is never launched by CI.

The official [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) describes the model distribution. The [llama.cpp server reference](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) documents the local HTTP and constrained-output interfaces. This project exercises a local adapter; it does not exercise a hosted OpenAI or other paid API.

## Reading the evidence

Each original run JSON contains the objective, evaluation and ordered trace. Context entries retain source revisions and retrieved documents. Model entries retain structured decisions, token usage, decoding settings and prompt/input hashes. Policy entries explain refusals. Action, approval and verified-receipt entries connect decisions to outcomes. The original archive excludes malformed raw text. The later acceptance journal retains final-channel responses from synthetic-only requests, including failed/empty answers; credentials, headers and private reasoning remain excluded.

`comparison/gate.json` is the machine-readable release decision. `releases/lifecycle.json` records the executed fixture gate, shadow snapshots, canary routing, promotion, injected regression and rollback. Its routed-run traces show which responder was actually selected after channel changes.

SQLite database files under `work/` are for local inspection and are excluded from publication. A trusted operator can use `Registry` to register immutable version/evidence bodies and perform guarded transitions. This is an executable local library/CLI demonstration, not a deployed multi-user release-management API. Protect the files and process environment if adapting it.

## Reproduction and release scope

Reproduce the shipped verification with `python scripts/verify.py`. If model, prompt, tool, retrieval, or runtime changes are proposed, rerun live inference and paired comparisons with new versioned output; preserve unfavorable and failed results. Check the [published Windows and Ubuntu CI run](https://github.com/rlbsem/enterprise-agent-runtime-evaluation/actions/runs/35055431823) separately from the archived local-model experiment. Production use would require the larger evaluation and identity, deployment, and monitoring controls described in [validation](validation.md).
