# Real-model release acceptance

The engineering question is whether an agent can perform the account-risk task correctly, not merely emit valid JSON or have its unsafe actions blocked. This increment keeps the existing runtime, destination, policy, release registry and original six classes. It adds frozen live-model acceptance with an independent outcome oracle, complete raw final responses and source-bound evidence.

[Download the self-contained evidence viewer](release-review.html?raw=1) and open it in a browser. It contains recorded responses and effects, requires no installation, and cannot call a model or execute an action. The [comparison report](evidence/live-release/summary.md) separates the original experiment, the first rejected candidate and the bounded-reasoning release run.

## What the original model failed

The preserved Qwen2.5-1.5B reference completed 1 of 12 tasks: five unnecessary abstentions, five evidence contradictions and one unverified completion. The summary-first mutation completed 2 of 12 tasks and made ten unsafe recommendations. Correct numeric quotations did not establish correct assessment or task completion. These are model/prompt failures; policy enforcement correctly prevented unauthorized effects. [Original comparison](evidence/comparison/report.md).

## What changed

- **Capacity and reasoning are tested, not assumed.** Existing official Qwen3-14B Q4_K_M weights run locally through llama.cpp b10809 on an RTX 5080. The small-model and non-reasoning development ablations remain separate comparisons. Changing model and reasoning jointly does not isolate model size as the cause of improvement.
- **Completion is evidence-derived.** Policy `renewal-agent/2` rejects `finish` with an insufficient assessment, and the runtime derives required effects from authenticated facts rather than the model's own assessment. The first frozen run exposed this gap; its original result is [preserved](evidence/live-release/completion-invariant.json). Targeted HTTP regression tests cover the correction.
- **Authority is explicit in the input.** The candidate projects unchanged numeric source values into `authoritative_facts` and retains all CRM hints and retrieved attack text in `untrusted_reference_data`. The adapter does not compute an assessment, topic or next action for the model. The original reference keeps its original input projection and prompt.
- **Reasoning cannot consume the answer allowance.** The initial 1,536-token total budget produced a length-limited empty answer on an injected-document case; that candidate was blocked at 35/36. The bounded run keeps the same total cap and separately limits reasoning to 1,024 tokens for the reference and 768 for the candidate. It reserves capacity for the structured answer. The [predeclared protocol](evidence/live-release/bounded-reasoning-protocol.json) pins the exact b10809 request-parser contract, configurations and stop rule. Private reasoning is excluded. Final schema validation, the 5,000-character decision bound, approval, tool permissions and retry limits remain in force.
- **The oracle examines effects independently.** It checks terminal status, final assessment, expected effect multiplicity and topic, exact payload hashes and independent destination readback. Matching counts or a model saying "done" are insufficient.
- **Evidence is preserved by default.** Fresh software verification goes under ignored `work/`, not over archived results. A historical manifest binds 75 original artifacts to their original Git blobs. The current package manifest separately covers the delivered source and new evidence.

## Frozen evaluation protocol

The [first versioned cases](../src/gtm_agent/acceptance-cases.json) retain six development cases and add twelve cases covering inclusive boundaries, critical-ticket precedence, contradictory narrative hints, insufficient evidence and two differently worded document attacks. With two seeds, that first frozen comparison produced 32/36 reference and 35/36 candidate successes. Its candidate failed the mandatory hostile-class gate. Neither configuration was promoted.

Those twelve first holdouts remain unchanged as **known regression cases**, not a fresh independent test. The [bounded-reasoning case extension](../src/gtm_agent/acceptance-cases-v2.json) adds six fresh cases after the completion/decoder corrections, without changing the v4 prompt or original expected outcomes. Both configurations execute six development, twelve regression and six fresh holdout cases at seeds 42 and 43: 48 tasks each. Source, prompts, expectations and the two reasoning caps are sealed before this run. There is no further cap search or tuning against its results.

The same engineer specified the synthetic business rules and independent expected outcomes. This is not externally curated or blind human evaluation. The holdout is a finite check against untuned cases; it does not establish population accuracy or general prompt-injection resistance. No expected labels or case identifiers enter the model input.

The original gate still requires at least 90% task success, no class regression, perfect critical-class outcomes and grounding, and zero observed unsafe recommendations, unauthorized/duplicate effects, hallucinated tools or wrong effect arguments. This stricter acceptance lane additionally requires complete frozen-case coverage, zero malformed outputs, complete recorded-inference coverage and every independent oracle check to pass. Thus a noncritical oracle failure also blocks this lane; the legacy thresholds are not relaxed. A development-only ablation cannot qualify. Original unfavorable results are never overwritten.

## Bounded-reasoning evidence

- [Source/prompt/dataset seal](evidence/live-release/qwen3-bounded-v2/seal.json)
- [1,024-token reasoning reference](evidence/live-release/qwen3-bounded-v2/qwen3-14b-reasoning1024-reference/summary.json)
- [768-token reasoning candidate](evidence/live-release/qwen3-bounded-v2/qwen3-14b-reasoning768-candidate/summary.json)
- [Paired and absolute gate](evidence/live-release/qwen3-bounded-v2/gate.json)
- [Live permission, exact-approval and duplicate probes](evidence/live-release/qwen3-bounded-v2/controls.json)
- [Release decision](evidence/live-release/qwen3-bounded-v2/release.json) and [executed source/model record](evidence/live-release/qwen3-bounded-v2/execution.json)

## Preserved first failed acceptance

- [Source/prompt/dataset seal](evidence/live-release/qwen3-v1/seal.json)
- [Original-projection Qwen3 reference](evidence/live-release/qwen3-v1/qwen3-14b-reference-v1/summary.json)
- [Authority-facts Qwen3 candidate](evidence/live-release/qwen3-v1/qwen3-14b-authority-facts-v4/summary.json)
- [Absolute and paired gate](evidence/live-release/qwen3-v1/gate.json)
- [Local permission, exact-approval and duplicate controls](evidence/live-release/qwen3-v1/controls.json)
- [Release decision](evidence/live-release/qwen3-v1/release.json) and [executed source/model record](evidence/live-release/qwen3-v1/execution.json)

Each task file beside its summary retains the actual final response, exact model request and hash, seed, tool schema, prompt, token usage, latency, runtime trace and independently read effects. The official model revision/file hash, runtime executable and DLL hashes, serving build and hardware boundary are in the seal. API headers, keys, databases, model weights, raw server logs and private reasoning are excluded.

The release runner uses the existing registry. If both configurations meet all mandatory acceptance conditions, it runs fresh paired shadow inference, a read-only canary, local promotion, an active routed task, controlled context-corruption detection and rollback to actual reference inference. A gate or stage failure withholds promotion. The controlled fault changes a copy of one adapter input while the runtime retains authentic evidence; it does not fabricate an LLM response or claim a natural model regression. Rollback changes future routing, not prior effects.

## Reproduce safely

The credential-free core requires Python 3.12 and the locked dependencies:

```bash
python scripts/verify.py
python scripts/check_acceptance.py
python docs/verify_release_review.py
python scripts/package.py --zip
```

Fresh live inference additionally requires the existing local model/runtime files and a private random API key file outside the public tree. The [official Qwen artifact metadata](model-artifacts/qwen3-14b.json) pins the model repository revision and LFS SHA-256. Obtain the matching runtime from the [official llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b10809); its model/runtime licenses are separate from this repository's MIT license.

```text
llama-server -m work/models/Qwen3-14B-Q4_K_M.gguf --host 127.0.0.1 --port 8097 -c 8192 -ngl 99 --parallel 1 --reasoning auto --alias qwen3-14b --api-key-file PRIVATE_KEY_FILE
python scripts/live_acceptance.py --bounded-reasoning --model-file work/models/Qwen3-14B-Q4_K_M.gguf --runtime-file work/llama/llama-server.exe --official-artifact docs/model-artifacts/qwen3-14b.json --key-file PRIVATE_KEY_FILE --output work/new-live-proof --workspace work/new-live-state
```

Use fresh output/state paths; the runner refuses existing directories, checks the local server model path/alias, verifies file hashes, seals source and refuses source changes. Its two configurations are paired on the same cases, seeds and retrieval contract. Linux model binaries were not executed in the recorded local-model run. CI uses fixture HTTP services and validates recorded evidence; it never downloads weights or calls a model endpoint.

All accounts, documents, approvals and destination effects are synthetic and local. No SaaS vendor, external deployment, prospect communication or commercial outcome is demonstrated. API spend is zero; hardware and energy costs were not metered. The [host-wide GPU observation](evidence/live-release/resource-observation.json) is an instantaneous shared-host sample, not model-only peak memory or integrated energy consumption.

## Browser review and capture

The viewer embeds source records directly and uses no external scripts, fonts or collection endpoint. Its [manifest](release-review-manifest.json) binds the underlying JSON, generator, template and rendered HTML. `python docs/render_release_review.py` regenerates it; `python docs/verify_release_review.py` independently checks displayed records, routed provider fingerprints/actual request caps, and screenshot hashes. It is a review surface over saved evidence, not a live agent console.

Optional screenshot reproduction uses [Playwright 1.55.0](browser-requirements.txt) plus axe-core 4.10.3 from `https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.3/axe.min.js`. The capture helper verifies SHA-256 `880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb` before executing that local audit script. Install Chromium through Playwright, save the asset under ignored `work/`, then run:

```text
python docs/capture_release_review.py --axe-file work/axe.min.js
```

Desktop/mobile capture checks configuration arithmetic, failure filtering, keyboard navigation, exact JSON export, overflow, page errors and automated WCAG rules. Zero automated violations is not an accessibility certification. Capturing the viewer performs no model inference. Current captures are written to `docs/images/current-release-review/`; the original `docs/images/live-release/` captures and provenance are preserved unchanged. Current captures are written to `docs/images/current-release-review/`; the original `docs/images/live-release/` captures and provenance are preserved unchanged.
