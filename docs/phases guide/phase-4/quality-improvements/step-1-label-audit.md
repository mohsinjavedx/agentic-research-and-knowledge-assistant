# Step 1: Audit evaluation labels

All 30 answerable questions were checked against their original PDFs independently of retrieval rankings. The audit's source checksums match the sample manifest. The 10 out-of-corpus questions are unchanged.

The only required page correction is `education-single-01`: the complete five-benchmark list appears on PDF page 7, section 2.4, rather than page 8. The active schema remains version 1 with dataset revision 2. Other adequate page references remain unchanged, including synthesis references; alternative/minimal support is recorded separately and is not used to inflate scores.

Preserved evidence:

- `data/eval/golden_set.v1.json`: the original dataset, byte-for-byte.
- `data/eval/golden_set.json`: the active corrected dataset.
- `data/eval/label-audit-2026-11-21.json`: all 30 source-based decisions, excerpts, reasons, alternatives, and ambiguity notes.
- `data/eval/retrieval_metrics.json`: the original measured report, unchanged.

The audit also flags `medical-table-01`: the paper's Table 4 has duplicate MPT-7B-Instruct rows with different values. The question and page remain unchanged; a faithful answer must acknowledge the ambiguity or disambiguate the rows. Reported source quirks are not silently rewritten into supposedly correct values.

The corrected dense baseline was saved before selecting a new retrieval default. Its MRR is 0.6244; Recall@5 remains 0.7667 and Precision@5 remains 0.3000. Correcting the label improves scoring accuracy without changing embeddings or retrieval.
