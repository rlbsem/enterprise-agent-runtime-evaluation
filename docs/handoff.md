# Finished project handoff

## Result and evidence

The repository demonstrates agent evaluation and release governance with actual local inference. It does **not** demonstrate a release-ready local model. That distinction is the central result: a candidate can improve one aggregate score while becoming less safe to recommend actions.

| Final experiment | Observed result | Inspectable proof |
|---|---|---|
| Clean installation | Built and installed a wheel in a fresh Python 3.12 environment; 59 tests passed, none skipped | [Verification and source hashes](evidence/verification.json), [test results](evidence/tests.xml) |
| Live reference | 1/12 successful tasks; 5 unsafe recommendations; 48/48 grounded numeric claims | [Reference report](evidence/live-reference/report.md) |
| Live candidate | 2/12 successful tasks; 10 unsafe recommendations; 36/36 grounded numeric claims | [Candidate report](evidence/live-candidate/report.md) |
| Live release decision | Both fail the absolute thresholds; candidate blocked; zero unauthorized or duplicate effects | [Generated comparison](evidence/comparison/report.md), [gate JSON](evidence/comparison/gate.json) |
| Live shadow | Six paired snapshots; zero external effects | [Actual paired decisions and context](evidence/comparison/shadow.json) |
| Fixture release lifecycle | Fault mutant blocked; equivalent candidate passes, promotes locally, then rolls back after an injected regression | [Lifecycle report](evidence/releases/report.md), [complete history and routed traces](evidence/releases/lifecycle.json) |
| Credential-export injection | Deliberately compliant adversarial responder refused at the contract boundary; zero remote effects | [Attack trace](evidence/adversarial/injection.json) |

The higher candidate task count comes only from the healthy class. Both configurations fail every critical class. Correctly copied numeric facts do not imply a correct assessment. Preventing an external effect does not imply successful agent behavior. These are measured distinctions, not a claim that one small prompt experiment ranks model providers.

## Architecture and agent behavior

One explicit Python agent runtime gathers synthetic account, usage and support facts plus approved, scoped playbooks. SQLite stores runtime state and release history; FTS5 supplies a small topic search; a separate FastAPI process implements the synthetic enterprise tools. The model chooses a task, escalation, completion or abstention using typed decisions and evidence references. Deterministic policy independently checks those choices and binds escalation approval to the exact action. Required reads are fixed because every scenario needs them.

This architecture keeps model decisions, evidence, execution and scoring separately inspectable. There is no agent framework, MCP layer, vector database, broker, distributed database, multi-agent topology or cloud deployment. The fixed capability set and tiny corpus do not justify those costs. The [architecture document](architecture.md) records the boundaries and tradeoffs.

## Versions, evaluation and release

Live versions fingerprint prompts, pinned model/runtime artifacts, decoding, tool schema, policy, retrieval settings and implementation. `reference-v1` prioritizes authenticated facts. `summary-first-v2` intentionally mutates evidence priority toward the narrative CRM summary. Both use the same local model and six-case dataset, with seeds 42 and 43.

Evaluation checks actual remote effects, expected tool sets and arguments, terminal outcomes, grounded claims, unsafe recommendations and trace events. It separates probabilistic model quality from deterministic software invariants. The gate requires paired coverage, no class regression, no critical-class failure, at least 90% overall success, fully grounded claims and zero observed unsafe recommendations or unauthorized/duplicate effects. These are finite-suite criteria, not statistically calibrated production assurances.

An immutable local registry requires offline eligibility, paired shadow observation and canary observation before activation. Shadow uses identical context and no write credential. Canary selects 20 of 100 stable hash buckets, admits only healthy/adoption classes and forces recommendation-only execution; the demonstration selects 21 of 100 example keys. Rollback changes the responder used by subsequent runtime requests and retains release history. It does not undo past business effects.

Successful promotion belongs exclusively to the deterministic fixture demonstration. The local Qwen model is withheld. The [evaluation protocol](evaluation.md) explains this separation and why neither the small dataset nor the intentional mutation is a blind benchmark.

## Real execution and its limits

Qwen2.5-1.5B-Instruct Q4_K_M ran locally through llama.cpp b10809: 24 complete evaluation runs, followed by six paired first-recommendation comparisons. Full runs issued 28 model requests. Model outputs and returned token usage are recorded. No paid provider was exercised, no saved response was replayed as live inference, and no synthetic CRM endpoint is presented as a vendor integration. Model weights and runtime binaries are excluded; exact download references and measured hashes are included.

The strongest observability artifacts are individual run traces, which link objective, context revisions, structured decisions, evidence claims, policy outcomes, approval, effect receipts and evaluation. The fixture incident trace also shows reconciliation after a committed HTTP effect loses its response. Private chain-of-thought and credentials are excluded.

Red-team corrections addressed scenario-label leakage, incidental clocks/nonces influencing inference, contradictory output fields, unsafe recommendations being mistaken for success, duplicate/missing evaluation samples, type coercion, caller-supplied shadow pass flags, shadow resuming effects, and rollback that could otherwise change only a label. The final validation also uses isolated scratch/cache directories. [Validation](validation.md) links the failure matrix and records remaining risks.

Unexecuted work includes hosted CI, Linux runtime validation, cloud deployment, real SaaS integrations, distributed rollout, load testing, host-loss recovery and enterprise identity. The six visible cases, two seeds, one small local model and one blatant poisoned supplement do not establish general model quality or broad injection resistance. Numeric grounding does not establish arbitrary semantic entailment. A trusted filesystem/process owner can alter local evidence and registry state.

## Exact next steps before publishing

1. Extract the finished archive into a new folder and read the live failures, release lifecycle, license and limitations.
2. Create a Python 3.12 virtual environment; install `requirements.lock`; install the project with `python -m pip install --no-deps --no-build-isolation -e .`; run `python scripts/verify.py`.
3. If changing model, prompt, tools, retrieval or runtime, rerun both live configurations and shadow comparison using the exact [operations commands](operations.md). Preserve the unfavorable results and disclose any further tuning.
4. Review the source and generated evidence, initialize normal Git history, and publish to the intended new repository yourself. No remote repository was created or pushed by this build.
5. Observe both supplied GitHub Actions jobs. Resolve platform failures before adding any passing-CI claim. Treat production rollout as separate work requiring broader evaluation and operational controls.
