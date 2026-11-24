import Link from "next/link";
import {
  ArrowUpRight,
  BookOpenCheck,
  BrainCircuit,
  Database,
  FileText,
  Fingerprint,
  Layers3,
  Network,
  Search,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { PublicFooter, PublicNavbar } from "@/components/public-chrome";
import { REPOSITORY_URL } from "@/lib/product";

export default function AboutPage() {
  return (
    <div className="public-site">
      <PublicNavbar />
      <main id="main">
        <header className="about-hero section-container">
          <span className="section-kicker">The thinking behind the workspace</span>
          <h1>
            Built to make research
            <br />
            more intelligent.
          </h1>
          <p>
            A full-stack research assistant that keeps retrieval, reasoning, and source verification
            open to inspection.
          </p>
          <div className="tech-badges">
            <span>Advanced RAG</span>
            <span>Page-level provenance</span>
            <span>Bounded agent workflows</span>
          </div>
        </header>
        <div className="about-layout section-container">
          <nav className="about-nav" aria-label="About sections">
            {[
              ["Overview", "overview"],
              ["Architecture", "architecture"],
              ["Retrieval pipeline", "retrieval"],
              ["Evaluation", "evaluation"],
              ["Engineering decisions", "decisions"],
              ["Documentation", "documentation"],
            ].map(([label, id]) => (
              <a key={id} href={`#${id}`}>
                {label}
              </a>
            ))}
          </nav>
          <article className="about-content">
            <section id="overview">
              <h2>One workspace. A traceable answer.</h2>
              <p>
                Research Assistant helps you explore text-based PDFs, find related passages, and ask
                grounded questions across selected sources. Start with three included papers
                spanning education, nutrition, and medical question answering, or upload your own
                searchable PDF.
              </p>
              <p>
                Quick answers pair a question with retrieved evidence. Agentic research uses a
                bounded LangGraph workflow to plan, retrieve, assess, synthesize, and verify a
                multi-document report. The interface shows actual tool calls and evidence as that
                work progresses.
              </p>
              <Link className="button secondary" href="/workspace">
                Explore the workspace <ArrowUpRight size={15} />
              </Link>
            </section>
            <section id="architecture">
              <h2>A small stack with a clear job.</h2>
              <div className="architecture-steps">
                {[
                  {
                    icon: FileText,
                    title: "Document ingestion",
                    text: "Bounded PDF upload → isolated structure checks → page-preserving Markdown extraction → normalization → traceable chunks.",
                  },
                  {
                    icon: Database,
                    title: "Searchable knowledge",
                    text: "Pinned BGE-small-en-v1.5 embeddings → normalized 384-dimensional vectors → PostgreSQL with pgvector and session-scoped document metadata.",
                  },
                  {
                    icon: Search,
                    title: "Question answering",
                    text: "Validate scope → embed the query → retrieve relevant passages → assemble complete context → generate a structured answer and validate citations.",
                  },
                  {
                    icon: Workflow,
                    title: "Agentic research",
                    text: "LangGraph plans and executes bounded document tools, checks sufficiency, synthesizes a report, and verifies its source claims.",
                  },
                  {
                    icon: BookOpenCheck,
                    title: "Evidence inspection",
                    text: "Return the answer, citations, source passages, page numbers, and retrieval similarities. Exact quote ranges drive the highlight.",
                  },
                ].map(({ icon: Icon, title, text }) => (
                  <div key={title}>
                    <Icon size={20} />
                    <section>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </section>
                  </div>
                ))}
              </div>
              <div className="tech-badges">
                {[
                  "React 19",
                  "Next.js 16",
                  "TypeScript",
                  "FastAPI",
                  "Pydantic",
                  "SQLAlchemy",
                  "PostgreSQL",
                  "pgvector",
                  "LangGraph",
                  "BGE / ONNX",
                  "Groq / Ollama",
                ].map((tech) => (
                  <span key={tech}>{tech}</span>
                ))}
              </div>
            </section>
            <section id="retrieval">
              <h2>Keep the context close to its source.</h2>
              <p>
                Chunks respect PDF page boundaries and retain normalized-to-original text mappings.
                Embedding preparation uses the pinned BGE tokenizer to fit the model’s input limit.
                Query embeddings use the model’s retrieval instruction, with the same vector
                identity checked at indexing and search time.
              </p>
              <p>
                The backend supports dense retrieval and hybrid retrieval with rank fusion, plus
                optional TinyBERT reranking and neighboring context expansion. These are backend
                configuration choices. The interface displays the evidence actually returned, rather
                than inventing a confidence score.
              </p>
              <p>
                Generation can use the configured Groq-compatible hosted endpoint or local Ollama.
                Structured responses are validated, and unsupported or mismatched source ranges
                never receive an invented highlight.
              </p>
            </section>
            <section id="evaluation">
              <h2>Evaluate retrieval. Inspect generation.</h2>
              <p>
                The repository includes a fixed question set and offline retrieval evaluation. These
                definitions describe the implemented evaluation tools; this page does not claim a
                current production quality score.
              </p>
              <dl className="metric-definitions">
                <div>
                  <dt>Precision@K</dt>
                  <dd>
                    The share of the top K retrieved results that match relevant ground-truth pages.
                  </dd>
                </div>
                <div>
                  <dt>Recall@K</dt>
                  <dd>
                    The share of relevant ground-truth pages represented in the retrieved results.
                  </dd>
                </div>
                <div>
                  <dt>Mean reciprocal rank</dt>
                  <dd>
                    How early the first relevant page appears across the evaluation questions.
                  </dd>
                </div>
                <div>
                  <dt>Out-of-corpus detection</dt>
                  <dd>
                    How often unrelated questions fall below the calibrated similarity cutoff.
                  </dd>
                </div>
              </dl>
              <p>
                Request telemetry also records retrieval and generation timing without logging
                question text or PDF contents. A high cosine similarity describes a retrieval match;
                it is not a guarantee that an answer is correct.
              </p>
            </section>
            <section id="decisions">
              <h2>Trust is built into the boundaries.</h2>
              <div className="architecture-steps">
                {[
                  {
                    icon: Layers3,
                    title: "Page-preserving chunks",
                    text: "Source mappings connect the normalized text, retrieved passages, and exact supporting quote.",
                  },
                  {
                    icon: Fingerprint,
                    title: "Private by session",
                    text: "HttpOnly anonymous sessions, owner-scoped document access, expiry, and PostgreSQL-backed request quotas.",
                  },
                  {
                    icon: ShieldCheck,
                    title: "Bounded document processing",
                    text: "20 MiB and 100-page upload limits, isolated native parsing, hard stage/page deadlines, memory limits, and temporary cleanup.",
                  },
                  {
                    icon: BrainCircuit,
                    title: "Bounded reasoning",
                    text: "At most four agent iterations and six tool calls. Partial coverage and failures are represented explicitly.",
                  },
                  {
                    icon: Network,
                    title: "Private observability",
                    text: "Hashed session identities, actual or unknown token counts, fixed error codes, and redacted automated secret scans.",
                  },
                ].map(({ icon: Icon, title, text }) => (
                  <div key={title}>
                    <Icon size={20} />
                    <section>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </section>
                  </div>
                ))}
              </div>
            </section>
            <section id="documentation">
              <h2>Read the implementation.</h2>
              <p>
                Built by{" "}
                <a
                  className="accent-text"
                  href="https://github.com/mohsinjavedx"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  mohsinjavedx
                </a>
                . The repository includes setup instructions, per-phase implementation guides,
                evaluation tools, and tests.
              </p>
              <div className="documentation-links">
                <a href={REPOSITORY_URL} target="_blank" rel="noopener noreferrer">
                  Source repository <ArrowUpRight size={15} />
                </a>
                <a
                  href={`${REPOSITORY_URL}/blob/main/README.md`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Setup & running locally <ArrowUpRight size={15} />
                </a>
                <a
                  href={`${REPOSITORY_URL}/tree/main/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Implementation guides <ArrowUpRight size={15} />
                </a>
                <Link href="/settings#privacy">
                  Session & privacy controls <ArrowUpRight size={15} />
                </Link>
              </div>
            </section>
          </article>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
