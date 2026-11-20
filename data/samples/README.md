# Phase 3 sample corpus

These three PLOS research articles are redistributed under Creative Commons
Attribution 4.0 International (CC BY 4.0). The stable document IDs and SHA-256
checksums are recorded in [manifest.json](manifest.json). Sample IDs are derived
from each DOI so evaluation labels remain valid after re-indexing.

| File | Article | Authors | DOI | License |
| --- | --- | --- | --- | --- |
| `educational-qa-rag.pdf` | A novel framework for educational Q&A: Leveraging RAG and Code Interpreters for knowledge retrieval and logical computation | Jin Lu; Ji Li | [10.1371/journal.pone.0337361](https://doi.org/10.1371/journal.pone.0337361) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `personalized-nutrition-rag.pdf` | AI-driven personalized nutrition: RAG-based digital health solution for obesity and type 2 diabetes | Anand K. Gavai; Jos van Hillegersberg | [10.1371/journal.pdig.0000758](https://doi.org/10.1371/journal.pdig.0000758) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `medical-qa-knowledge-embedding.pdf` | Advancing medical question answering with a knowledge embedding transformer | Xiang Zhu; Mustaqeem Khan; Abdelmalik Taleb-Ahmed; Alice Othmani | [10.1371/journal.pone.0329606](https://doi.org/10.1371/journal.pone.0329606) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

Publisher PDF sources: [PLOS ONE article](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0337361&type=printable), [PLOS Digital Health article](https://journals.plos.org/digitalhealth/article/file?id=10.1371/journal.pdig.0000758&type=printable), and [PLOS ONE article](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0329606&type=printable).

The corpus is about 10.1 MB total. From `apps/api`, index it with:

```powershell
uv run python -m app.services.indexing.seed_samples
```

The command verifies every checksum and uses the stable document IDs in the manifest.
