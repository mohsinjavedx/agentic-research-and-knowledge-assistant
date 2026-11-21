# Step 3: Focused evidence

`app/services/generation/evidence.py` chooses a complete Markdown block from each retrieved chunk using weighted question-term overlap. It preserves the selected text as a slice of the original normalized chunk. Adjacent headings and table context are retained; loose lists, their introductory qualifier, and indented continuations are grouped before scoring, even when blank lines separate the items.

For the reported benchmark question, the selected first excerpt is the heading and paragraph under `2.4 Evaluation datasets`. The preceding figure and long background discussion are omitted from that excerpt. Other source candidates remain available for context packing.

Local Ollama packs complete selected passages under the configured context/output budget. A passage that cannot fit is skipped; its list/table is never truncated to squeeze it in. Context indices therefore may differ from retrieval indices. The provider returns the exact passage mapping with its draft, and the service validates it against the original retrieval results. Hosted generation also uses focused passages and returns its actual supplied context.

The existing conservative `cl100k_base` budget is an estimate, not the local model's exact tokenizer. Selection is lexical and does not guarantee that every fact needed for synthesis is retained. Large atomic tables can still exceed context, and a complex question may abstain. Quote checks and quality evaluation do not remove these limitations.

Offsets count Unicode code points in the normalized chunk string. They are half-open ranges: `chunk.text[start:end]`. They are not PDF byte offsets or raw extraction offsets. JavaScript clients must account for the difference between Unicode code points and UTF-16 code units when highlighting astral characters.
