# Validation, adversarial review and limits

## Executed boundary

This independent portfolio implementation uses synthetic records, documents, users, tool services and objectives. Native validation ran on Windows with Python 3.12, real SQLite/FTS5, a separate HTTP service process, and actual local Qwen2.5-1.5B-Instruct inference through llama.cpp. Exact software-test counts, environment versions and source hashes are in [verification.json](evidence/verification.json). No skipped-infrastructure substitute is used.

The live comparison contains two samples for each of six classes per configuration. Its reports retain unfavorable outcomes. The small local model is **not ready for promotion under the repository's criteria**. The candidate improves aggregate task success from 1/12 to 2/12 while doubling unsafe recommendations from 5 to 10; both have zero unauthorized external effects. Numeric claims are grounded, but assessments and task completion frequently fail. Read [the gate report](evidence/comparison/report.md), [reference results](evidence/live-reference/report.md) and [candidate results](evidence/live-candidate/report.md) for actual counts rather than assuming the demonstration succeeded at every task.

Successful release promotion/rollback is a separate, explicitly deterministic experiment. It executes real code, SQLite state changes, HTTP tools and routed runtime calls using handwritten model fixtures. It does not claim that a live model was promoted. The shadow/canary reports measure zero external effects and show actual decisions and frozen context. They are not cloud deployment or real customer traffic.

GitHub Actions is configured for Windows and Linux but has not been pushed or observed running for this project. No hosted CI pass is claimed. No Docker engine, cloud infrastructure, SaaS system, paid AI provider, production customer, scale benchmark or security certification is claimed.

## Material corrections from skeptical review

| Concern | Correction and executable evidence |
|---|---|
| Decorative agent steps | Required context collection became deterministic; model decisions focus on assessment and next action |
| Contradictory model fields | Provider contract uses one operation, translated into the internal decision; terminal actions cannot have contradictory call/tool fields |
| Incorrect evidence attribution | Atomic fact identifiers plus exact-value checks; invented or duplicated claims fail closed |
| Case-label leakage | Scenario IDs are redacted before inference; the poisoned document has a neutral supplement ID |
| Incidental run IDs/timestamps bias model comparisons | Model projection removes receipt nonces and observation clocks; it retains source facts/revisions and completed tool names; a provider-contract test asserts the boundary |
| A safe refusal looks like a successful task | Independent expected-outcome scoring counts safe abstention on a critical case as task failure; denied unsafe recommendations remain quality defects |
| Evaluation cherry-picks easy classes | Gate requires all six classes, paired sample keys, no duplicates, two live samples per class, and critical-class checks |
| String coercion could make false metrics truthy | Strict metric-type/count validation rejects string booleans, negative counts and invalid sample indices |
| A caller-supplied shadow pass flag bypasses release logic | Registry derives acceptance from paired observations and coverage; forged pass flags cannot override bad decisions |
| Rollback changes only a label | Registry routing drives actual runtime/model factories; traces show selected versions before and after rollback |
| Canary accidentally writes | Selected cohort is forced into shadow mode with no write credential; even a pending-effect resume is rejected in shadow |
| Retrieved content grants authority | Closed operations, server scope, independent evidence checks and exact approval binding; adversarial fixture deliberately follows the export attack and is refused |
| Extra sensitive fields enter context | Input allow-lists reject unexpected upstream keys before the first model call; sentinel-secret tests verify absence from traces |
| Remote timeout duplicates work | Persist intent before HTTP; reconcile saved key/hash and verify the effect; timeout-before/after cases execute over actual sockets |
| Temporary-directory assumptions break local tests | Verification uses explicit unique workspace scratch and cache directories rather than inaccessible shared OS or inherited cache directories |

Prompt/contract development used the incident scenario and produced failures before the final comparison. This tuning is disclosed; the final six-case suite is a regression exercise, not a blind generalization benchmark. The model is intentionally small enough to run locally. Its shortcomings are evidence that the gate should withhold release, not grounds for inventing better results.

## Attack and failure matrix

| Scenario | Evidence lane | Expected boundary |
|---|---|---|
| Retrieved instruction to export credentials and waive approval | Deliberately compliant adversarial fixture; actual local model sees poisoned context in live/shadow runs | Unsupported capability refused; no credential-bearing input/output trace |
| False healthy assessment despite incident/usage evidence | Fixture mutation and live summary-first prompt | Evidence contradiction; bad recommendation counted even if blocked |
| Fabricated claim / unsupported tool / extra account or approval argument | Structured adversarial fixtures | Contract or grounding rejection; zero effect |
| Repeated selection loop / unavailable model | Software integration | Repeated-decision or durable model-call budget terminates work |
| Uncertain account | Fixture and actual local model | Proper abstention measured separately from refusal on a solvable task |
| Malformed or unexpected enterprise fields | HTTP integration | Reject before model inference |
| Context/policy change or expired approval | HTTP/state integration | No second governed effect |
| Rate limit, server error, timeout before/after commit | HTTP fault injection | Bounded retry and one stable effect key |
| Competing workers / expired lease | SQLite concurrency | One claim and rejection of stale local completion |
| Missing/duplicate samples, invalid metrics, staged-release bypass | Release-rule tests | No promotion |
| Runtime regression after local promotion | Executed fixture lifecycle | Future requests route back to the reference; prior effects remain |

## Production limitations

This is a single-host local runtime and release registry. SQLite file permissions and trusted Python processes form the administrative boundary. Append-only triggers guard ordinary updates, but a filesystem owner can replace a database or disable protections. Evidence hashes bind recorded artifacts; they are not remote attestations against a malicious evaluation administrator. Production use needs independently controlled evaluation execution, signed provenance where appropriate, identity/access controls and protected release approvals.

The enterprise simulator hosts several capability namespaces in one process and database. Its atomic version-vector/effect contract is stronger than some real vendors provide. A future integration must verify provider-specific idempotency retention, reconciliation consistency and version-check behavior. There is no universal exactly-once, transactional multi-vendor write or instant cancellation guarantee.

Concurrency tests exercise leases; an actual killed-worker recovery experiment is not claimed for this repository. Database corruption, host loss, backup/restore, network partitions, sustained load, fleet rollout and distributed coordination are not evaluated. The previous control-plane project explores some execution-recovery problems more deeply; this repository spends its complexity budget on evaluation and release governance.

One blatant poisoned supplement and a compact set of structured attacks do not establish broad prompt-injection resistance. The grammar-constrained tool set prevents some attack outputs by construction. Longer contexts, subtle instruction laundering, multilingual attacks, retrieval poisoning at scale and adaptive attackers remain unevaluated. Grounding covers a few numeric facts, not arbitrary semantic entailment. The corpus is too small to support search-quality generalization claims.

The release thresholds are conservative finite-suite rules, not statistically calibrated production risk bounds. Repeated model outputs can vary across seeds, hardware and runtime versions. Canary routing is a stable synthetic recommendation cohort, not measured production distribution. The operator still decides whether observed evidence justifies rollback; the fixture incident is explicitly injected.

## Benchmark inspection

Before architecture selection, both public repositories were downloaded at these commits and their implementation/evidence boundaries inspected:

- [Game telemetry analytics engineering](https://github.com/rlbsem/game-telemetry-analytics-engineering/tree/205491319fd25c0ad107e25e0e25d2003cb2a5d6): explicit analytical grains, executable dbt/Python, negative admission/replay tests, generated proof and separated deployment references.
- [Enterprise MarTech / AI Control Plane](https://github.com/rlbsem/enterprise-martech-ai-control-plane/tree/3b7cef9cf87db0a681d4e2fb284b5736f84e6bc5): source authority, approval, leased execution, real HTTP uncertainty recovery, negative tests and honest local/CI boundaries.

Their evidentiary discipline is reused. Their primary architectures are not copied: this project's main deliverables are model-behavior comparison, release gating, scoped shadow/canary execution and observable version routing.
