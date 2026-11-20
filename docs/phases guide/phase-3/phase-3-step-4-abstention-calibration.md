# Phase 3, step 4: Similarity abstention calibration

The API marks search results as insufficient evidence when the best cosine similarity is at or below `RETRIEVAL_SIMILARITY_THRESHOLD`. The evaluation runner derives a cutoff from the fixed 10 out-of-corpus questions: it selects the score at the 90th-percentile detection target and flags scores less than or equal to that cutoff. This targets at least 9 of 10 negative questions; ties can result in more being flagged.

The calibrated value, the number of detected negatives, and the answerable questions also below the cutoff are recorded in `data/eval/retrieval_metrics.json`. The runtime setting in `.env.example` must match the measured calibration value. Do not select or change the cutoff to make the answerable retrieval metrics appear better; report any answerable questions it would abstain on.

## Acceptance target

At least 90% of the 10 out-of-corpus questions must be flagged below or at the calibrated cutoff. This small fixed set is a baseline calibration result, not a guarantee of generalization to arbitrary user questions.

See the [retrieval evaluation report](../../evaluation-report.md) and [evaluation script](../../../scripts/run_retrieval_eval.py).
