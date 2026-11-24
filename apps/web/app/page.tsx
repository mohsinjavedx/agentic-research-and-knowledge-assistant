import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  BookOpenCheck,
  BrainCircuit,
  Check,
  ChevronDown,
  Code2,
  Database,
  FileText,
  Files,
  Layers3,
  MessageSquare,
  Network,
  Plus,
  Quote,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
} from "lucide-react";
import { PublicFooter, PublicNavbar } from "@/components/public-chrome";
import { REPOSITORY_URL } from "@/lib/product";
import { Brand } from "@/components/brand";

const features = [
  {
    icon: Files,
    title: "Your documents, understood.",
    text: "Turn text-based PDFs into searchable knowledge, with the page and passage kept alongside every chunk.",
  },
  {
    icon: Network,
    title: "Search beyond the keywords.",
    text: "Find related ideas with BGE embeddings and PostgreSQL vector retrieval. Explore the passages behind a result.",
  },
  {
    icon: BookOpenCheck,
    title: "Answers with a paper trail.",
    text: "Follow inline citations to exact supporting quotes. Know when the evidence is too thin to support an answer.",
  },
  {
    icon: Workflow,
    title: "Go deeper, across papers.",
    text: "Run a bounded research workflow. Follow its plan, tool calls, collected evidence, and cited report as it progresses.",
  },
  {
    icon: SlidersHorizontal,
    title: "Keep your research in scope.",
    text: "Choose the documents behind each question. Separate included sample papers from your session’s private uploads.",
  },
  {
    icon: ShieldCheck,
    title: "Built to be inspected.",
    text: "From offline retrieval evaluation to validated citation offsets, the engineering is open to a closer look.",
  },
];

function ProductPreview() {
  return (
    <div
      className="product-preview"
      id="product"
      aria-label="Illustrated workspace example using an included research paper"
    >
      <div className="preview-window-bar">
        <span className="window-dots">
          <i />
          <i />
          <i />
        </span>
        <span>
          <ShieldCheck size={12} /> Research workspace
        </span>
        <span className="preview-example-label">Included paper example</span>
      </div>
      <div className="preview-body">
        <aside className="preview-sidebar">
          <Brand />
          <div className="preview-new">
            <Plus size={13} /> New research
          </div>
          <div className="preview-nav selected">
            <MessageSquare size={14} /> Research
          </div>
          <div className="preview-nav">
            <Files size={14} /> Documents
          </div>
          <div className="preview-nav">
            <Database size={14} /> Knowledge base
          </div>
          <small>INCLUDED COLLECTION</small>
          <span>
            <FileText size={13} /> Educational QA
          </span>
          <span>
            <FileText size={13} /> Personalized nutrition
          </span>
          <span>
            <FileText size={13} /> Medical QA
          </span>
          <div className="preview-private">
            <ShieldCheck size={12} /> Private browser session
          </div>
        </aside>
        <div className="preview-conversation">
          <div className="preview-chat-header">
            <span>Educational question answering</span>
            <span>
              <Layers3 size={12} /> 1 selected paper
            </span>
          </div>
          <div className="preview-question">
            <span className="preview-avatar">You</span>
            <p>
              Which five benchmarks are used to evaluate the educational question-answering system?
            </p>
          </div>
          <div className="preview-answer">
            <span className="preview-answer-icon">
              <BrainCircuit size={19} />
            </span>
            <div>
              <strong>Five benchmarks, one clear source.</strong>
              <p>
                The system is evaluated on <b>AI2_ARC</b>, <b>OpenBookQA</b>, <b>E-EVAL</b>,{" "}
                <b>Textbook Question Answering (TQA)</b>, and <b>ScienceQA</b>.{" "}
                <span className="preview-citation">1</span>
              </p>
              <div className="preview-answer-source">
                <FileText size={13} /> Educational QA <span>Page 7</span>
                <Check size={12} />
              </div>
              <small>This example is drawn from the included paper.</small>
            </div>
          </div>
          <div className="preview-input">
            <span>Ask a question about your documents…</span>
            <div>
              <Plus size={14} />
              <span>
                1 source <ChevronDown size={11} />
              </span>
              <span className="preview-send">
                <ArrowUp size={14} />
              </span>
            </div>
          </div>
          <span className="preview-disclaimer">
            Source-grounded answers. Evidence you can inspect.
          </span>
        </div>
        <aside className="preview-evidence">
          <div>
            <BookOpenCheck size={16} />
            <strong>Sources & evidence</strong>
          </div>
          <small>SUPPORTING PASSAGE</small>
          <section>
            <span>
              <FileText size={15} /> Educational QA
            </span>
            <b>2.4 Evaluation datasets</b>
            <p>
              This study selects five representative public datasets…{" "}
              <mark>
                AI2_ARC, OpenBookQA, E-EVAL, Textbook Question Answering (TQA), and ScienceQA.
              </mark>
            </p>
            <span className="preview-page">
              Page 7 <Quote size={12} />
            </span>
          </section>
          <p className="preview-evidence-note">
            <ShieldCheck size={13} /> Trace a claim to its source. Keep the surrounding context.
          </p>
        </aside>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="public-site">
      <PublicNavbar />
      <main id="main">
        <section className="marketing-hero section-container">
          <div className="hero-eyebrow">
            <span /> AI-powered research workspace{" "}
            <span className="hero-eyebrow-detail">Built around your evidence</span>
          </div>
          <h1>
            Turn your documents into <span>intelligent answers.</span>
          </h1>
          <p className="hero-description">
            Your best ideas are already in your documents.
            <br className="desktop-break" /> Ask a better question. Find the connection. Follow the
            source.
          </p>
          <div className="hero-actions">
            <Link className="button large" href="/workspace">
              Start researching <ArrowUpRight size={18} />
            </Link>
            <Link className="button secondary large" href="#how-it-works">
              Explore how it works <ArrowDown size={16} />
            </Link>
          </div>
          <p className="hero-trust">
            <span>
              <Check size={14} /> No account required
            </span>
            <span>
              <Check size={14} /> Three included research papers
            </span>
            <span>
              <Check size={14} /> Transparent citations
            </span>
          </p>
          <ProductPreview />
          <div className="built-with-strip">
            <span>A considered stack. An inspectable system.</span>
            <div>
              <span>Next.js</span>
              <span>FastAPI</span>
              <span>PostgreSQL + pgvector</span>
              <span>LangGraph</span>
              <span>Groq</span>
            </div>
          </div>
        </section>
        <section className="features-section section-container" id="features">
          <div className="section-intro">
            <span className="section-kicker">Less searching. More understanding.</span>
            <h2>
              Research is a process.
              <br />
              Your tools should keep up.
            </h2>
            <p>A focused workspace for asking, exploring, and checking the evidence.</p>
          </div>
          <div className="feature-grid">
            {features.map(({ icon: Icon, title, text }) => (
              <article className="feature-item" key={title}>
                <Icon size={23} />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="how-section" id="how-it-works">
          <div className="section-container">
            <div className="section-intro">
              <span className="section-kicker">A clear path through your knowledge</span>
              <h2>From documents to discovery.</h2>
              <p>Every answer starts with a source. Every step keeps it in view.</p>
            </div>
            <div className="how-grid">
              {[
                [
                  "Upload knowledge",
                  "Bring a searchable PDF, or start with the included research papers.",
                ],
                [
                  "Process and index",
                  "Extract Markdown, normalize text, chunk by page, and embed with BGE.",
                ],
                [
                  "Retrieve the context",
                  "Search your selected documents for related passages and assemble evidence.",
                ],
                [
                  "Follow the answer",
                  "Read the response. Open a citation. Inspect the original source passage.",
                ],
              ].map(([title, description], index) => (
                <article key={title}>
                  <span className="step-number">0{index + 1}</span>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section className="technology-section section-container" id="technology">
          <div className="technology-copy">
            <span className="section-kicker">Designed to be understood</span>
            <h2>
              Serious engineering.
              <br />
              Visible by design.
            </h2>
            <p>
              Local embeddings. PostgreSQL vector search. Validated, source-grounded generation. The
              architecture is part of the product.
            </p>
            <div className="tech-badges">
              {[
                "Python",
                "FastAPI",
                "Pydantic",
                "BGE embeddings",
                "pgvector",
                "LangGraph",
                "Groq / Ollama",
                "Next.js",
              ].map((tech) => (
                <span key={tech}>{tech}</span>
              ))}
            </div>
            <Link className="text-button accent-text" href="/about">
              Explore the architecture <ArrowUpRight size={16} />
            </Link>
          </div>
          <div className="pipeline-card">
            <div className="pipeline-heading">
              <Workflow size={18} />
              <strong>Two paths. One grounded answer.</strong>
            </div>
            <div className="pipeline-label">Build your knowledge</div>
            <div className="pipeline-flow">
              {["PDF", "Markdown", "Chunks", "BGE", "pgvector"].map((node, index) => (
                <span key={node}>
                  {index > 0 && <ArrowRight size={13} />}
                  <b>{node}</b>
                </span>
              ))}
            </div>
            <div className="pipeline-divider" />
            <div className="pipeline-label">Ask a question</div>
            <div className="pipeline-nodes">
              <div>
                <Search size={17} />
                <span>Query + document scope</span>
              </div>
              <ArrowDown size={15} />
              <div>
                <Network size={17} />
                <span>Embed, retrieve & assemble</span>
              </div>
              <ArrowDown size={15} />
              <div>
                <BrainCircuit size={17} />
                <span>Generate & validate citations</span>
              </div>
              <ArrowDown size={15} />
              <div className="pipeline-result">
                <BookOpenCheck size={17} />
                <span>Answer + supporting passages</span>
                <Check size={14} />
              </div>
            </div>
          </div>
        </section>
        <section className="final-cta section-container">
          <span className="section-kicker">Bring your curiosity</span>
          <h2>
            Your knowledge deserves
            <br />
            more than a search bar.
          </h2>
          <p>Start with a paper. Leave with a clearer perspective.</p>
          <div>
            <Link className="button large" href="/workspace">
              Launch research workspace <ArrowUpRight size={18} />
            </Link>
            <a
              className="text-button"
              href={REPOSITORY_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Code2 size={17} /> Explore the source
            </a>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
