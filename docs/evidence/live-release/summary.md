# Executed model comparison

All sources, effects and approvals are synthetic and local. These are recorded model calls, not replayed answers. Earlier failures remain unchanged. No production release, SaaS integration or commercial outcome is established.

| Configuration | Tasks passed | Unsafe recommendations | Unauthorized / duplicate effects | Release boundary |
|---|---:|---:|---:|---|
| [Original Qwen2.5 / reference-v1](../live-reference/summary.json) | 1/12 | 5 | 0 / 0 | withheld (original archive) |
| [Original Qwen2.5 / summary-first-v2](../live-candidate/summary.json) | 2/12 | 10 | 0 / 0 | withheld (original archive) |
| [qwen3-14b-reference-v1](qwen3-v1/qwen3-14b-reference-v1/summary.json) | 32/36 | 0 | 0 / 0 | withheld |
| [qwen3-14b-authority-facts-v4](qwen3-v1/qwen3-14b-authority-facts-v4/summary.json) | 35/36 | 0 | 0 / 0 | withheld |
| [qwen3-14b-reasoning1024-reference](qwen3-bounded-v2/qwen3-14b-reasoning1024-reference/summary.json) | 48/48 | 0 | 0 / 0 | promoted_then_rolled_back |
| [qwen3-14b-reasoning768-candidate](qwen3-bounded-v2/qwen3-14b-reasoning768-candidate/summary.json) | 48/48 | 0 | 0 / 0 | promoted_then_rolled_back |
| [qwen3-14b-reference-v1](qwen3-nonthinking-development/qwen3-14b-reference-v1/summary.json) | 6/12 | 6 | 0 / 0 | withheld |
| [qwen3-14b-authority-facts-v4](qwen3-nonthinking-development/qwen3-14b-authority-facts-v4/summary.json) | 8/12 | 4 | 0 / 0 | withheld |
| [qwen25-1.5b-reference-v1](qwen25-development/qwen25-1.5b-reference-v1/summary.json) | 1/12 | 4 | 0 / 0 | withheld |
| [qwen25-1.5b-authority-facts-v4](qwen25-development/qwen25-1.5b-authority-facts-v4/summary.json) | 2/12 | 2 | 0 / 0 | withheld |

Development-only ablations cannot qualify even if all six visible cases pass. The first Qwen3 holdout is retained as known regression in the later run; fresh cases are sealed separately. The same engineer authored the known rules and cases. This is not a blind external benchmark.

## Observed local inference resources

| Configuration | Model requests | Completion tokens | Mean request seconds | p95 request seconds |
|---|---:|---:|---:|---:|
| Original Qwen2.5 / reference-v1 | 16 | 905 | not separately recorded | not separately recorded |
| Original Qwen2.5 / summary-first-v2 | 12 | 796 | not separately recorded | not separately recorded |
| qwen3-14b-reference-v1 | 72 | 29,957 | 4.971 | 8.187 |
| qwen3-14b-authority-facts-v4 | 71 | 40,592 | 7.034 | 11.578 |
| qwen3-14b-reasoning1024-reference | 96 | 55,065 | 6.78 | 11.813 |
| qwen3-14b-reasoning768-candidate | 96 | 53,306 | 6.501 | 9.937 |
| qwen3-14b-reference-v1 | 20 | 1,652 | 1.263 | 1.328 |
| qwen3-14b-authority-facts-v4 | 24 | 1,999 | 1.251 | 1.281 |
| qwen25-1.5b-reference-v1 | 16 | 910 | 0.34 | 0.453 |
| qwen25-1.5b-authority-facts-v4 | 12 | 1,270 | 0.421 | 0.5 |

Completion counts include reasoning where enabled; its content is excluded. p95 uses nearest rank. These are small descriptive host observations, not a controlled capacity benchmark or latency SLA. Paid API spend is zero; hardware and energy costs were not metered.

## Latest full acceptance

Local decision: **promoted_then_rolled_back**. [Exact gate](qwen3-bounded-v2/gate.json) · [Release record](qwen3-bounded-v2/release.json).

Mandatory gate reasons: none.

- Fresh shadow: 6 paired contexts, 0 external effects.
- Read-only canary: 2 paired contexts plus an actual selected routed run.
- Active route: `qwen3-14b-reasoning768-candidate`.
- Controlled adapter-input corruption: `escalated`; not a natural model regression and not a fabricated response.
- Subsequent actual rollback route: `qwen3-14b-reasoning1024-reference`.
- [Full traces, inference and immutable registry history](qwen3-bounded-v2/lifecycle.json).

[Permission, exact-approval and replay controls](qwen3-bounded-v2/controls.json): 9/9 checks passed. Exact escalation approvals are supplied by the trusted harness, not a measured human review study.
