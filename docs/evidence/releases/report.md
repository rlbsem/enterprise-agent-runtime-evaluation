# Executed release lifecycle

Deterministic fixture behavior, not live-model promotion.

- Summary-first fault mutant: **BLOCKED** by executed behavioral regression.
- Equivalent candidate with reordered claims: offline gate passed.
- Shadow: six paired context snapshots; zero external effects.
- Canary: recommendation only; 21/100 synthetic keys selected by 20% hash buckets.
- Candidate promoted locally, then routed back to the reference after an injected failing runtime evaluation.
- Rollback changes future version routing; it does not undo business effects.
