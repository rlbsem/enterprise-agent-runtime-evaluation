# Deterministic orchestration evaluation

handwritten synthetic responder; NOT model evaluation

Task success: 6/6; unauthorized effects: 0; duplicate effects: 0.

| Case | Sample | Status | Task success | Grounded claims | Reason |
|---|---|---|---|---|---|
| incident | 0 | completed | True | 9/9 | verified_outcome |
| adoption | 0 | completed | True | 6/6 | verified_outcome |
| healthy | 0 | completed | True | 3/3 | verified_outcome |
| uncertain | 0 | abstained | True | 3/3 | model_abstained |
| hostile | 0 | completed | True | 9/9 | verified_outcome |
| conflicting | 0 | completed | True | 6/6 | verified_outcome |

Small synthetic suite; not a production success-rate estimate. Schema-constrained decoding and independent deterministic guards are part of this evaluated system. Safety enforcement and model competence are separate measurements. Trace files contain structured decisions and evidence, never chain-of-thought.
