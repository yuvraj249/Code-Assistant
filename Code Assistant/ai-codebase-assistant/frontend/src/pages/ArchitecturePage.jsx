import { useState, useEffect, useRef } from "react";
import mermaid from "mermaid";
import "./ArchitecturePage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  themeVariables: {
    primaryColor: "#7c6dfa",
    primaryTextColor: "#e8eaf0",
    primaryBorderColor: "#2a2d3e",
    lineColor: "#4ecca3",
    secondaryColor: "#1e2030",
    tertiaryColor: "#161822",
    background: "#0f1117",
    mainBkg: "#1e2030",
    nodeBorder: "#2a2d3e",
    clusterBkg: "#161822",
    titleColor: "#e8eaf0",
    edgeLabelBackground: "#161822",
    fontFamily: "JetBrains Mono, monospace",
  },
});

export default function ArchitecturePage({ activeRepo }) {
  const [summary, setSummary]     = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [diagramSvg, setDiagramSvg] = useState("");
  const refreshRef = useRef(null);

  useEffect(() => { if (activeRepo?.repo_id) fetchSummary(); }, [activeRepo]);

  useEffect(() => {
    if (summary?.mermaid_diagram) renderDiagram(summary.mermaid_diagram);
  }, [summary]);

  const fetchSummary = async () => {
    setLoading(true); setError(null);
    try {
      const res  = await fetch(`${API}/repo-summary/${activeRepo.repo_id}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to load summary");
      setSummary(data.summary);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setTimeout(() => refreshRef.current?.focus(), 50);
    }
  };

  const renderDiagram = async (diagramCode) => {
    try {
      const id = "mermaid-" + Date.now();
      const { svg } = await mermaid.render(id, diagramCode);
      setDiagramSvg(svg);
    } catch (e) {
      setDiagramSvg("");
      console.warn("Mermaid render failed:", e);
    }
  };

  if (!activeRepo) {
    return (
      <main className="arch-page" id="main-content">
        <div className="arch-empty" role="status">
          <div className="empty-icon" aria-hidden="true">⬡</div>
          <div className="empty-title">No Repository Loaded</div>
          <p className="empty-sub">Upload or connect a repo to view its architecture.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="arch-page" id="main-content">
      {/* Header */}
      <header className="arch-header">
        <div>
          <div className="terminal-prompt" aria-hidden="true">$ codemind --analyze architecture</div>
          <h1 className="page-title">Architecture Analysis</h1>
          <p className="page-subtitle">AI-generated overview of {activeRepo.repo_name}</p>
        </div>
        <button
          ref={refreshRef}
          className="btn btn-ghost"
          onClick={fetchSummary}
          disabled={loading}
          aria-busy={loading}
          aria-label={loading ? "Analyzing architecture…" : "Refresh architecture analysis"}
        >
          {loading ? <><span className="spinner" aria-hidden="true" /> Analyzing…</> : "↺ Refresh"}
        </button>
      </header>

      {error && (
        <div className="arch-error" role="alert" aria-live="assertive">
          ⚠ {error}
        </div>
      )}

      {loading && !summary && (
        <div className="arch-loading" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <span>Analyzing repository structure with AI…</span>
        </div>
      )}

      {summary && (
        <div className="arch-content">
          {/* Stats row */}
          <div className="stats-row" role="list" aria-label="Repository statistics">
            <StatCard label="Language"     value={summary.language}     icon="◎" color="purple" />
            <StatCard label="Architecture" value={summary.architecture} icon="⬡" color="green"  />
            <StatCard label="Files"        value={summary.file_count}   icon="▦" color="yellow" />
            <StatCard label="Chunks"       value={summary.chunk_count}  icon="◈" color="purple" />
          </div>

          {/* Overview */}
          <section className="arch-section" aria-labelledby="overview-heading">
            <h2 id="overview-heading" className="section-title">◉ Overview</h2>
            <div className="arch-card overview-text">{summary.overview}</div>
          </section>

          {/* Mermaid diagram */}
          {diagramSvg && (
            <section className="arch-section" aria-labelledby="diagram-heading">
              <h2 id="diagram-heading" className="section-title">⬡ Architecture Diagram</h2>
              <div className="arch-card diagram-card">
                <div
                  className="mermaid-svg"
                  dangerouslySetInnerHTML={{ __html: diagramSvg }}
                  role="img"
                  aria-label={`Architecture diagram for ${activeRepo.repo_name}`}
                  tabIndex={0}
                />
              </div>
            </section>
          )}

          {/* Architecture explanation */}
          {summary.architecture_explanation && (
            <section className="arch-section" aria-labelledby="arch-explain-heading">
              <h2 id="arch-explain-heading" className="section-title">▲ Architecture Explanation</h2>
              <div className="arch-card overview-text">{summary.architecture_explanation}</div>
            </section>
          )}

          {/* Modules + Key files + Dependencies */}
          <div className="three-col">
            <section className="arch-section" aria-labelledby="modules-heading">
              <h2 id="modules-heading" className="section-title">◈ Modules</h2>
              <div className="arch-card tag-list">
                {(summary.modules || []).map((m) => (
                  <span key={m} className="arch-tag arch-tag-purple">{m}</span>
                ))}
                {!summary.modules?.length && <span className="arch-empty-tag">None detected</span>}
              </div>
            </section>

            <section className="arch-section" aria-labelledby="keyfiles-heading">
              <h2 id="keyfiles-heading" className="section-title">▦ Key Files</h2>
              <div className="arch-card tag-list">
                {(summary.key_files || []).map((f) => (
                  <span key={f} className="arch-tag arch-tag-green file-tag" title={f}>{f}</span>
                ))}
                {!summary.key_files?.length && <span className="arch-empty-tag">None detected</span>}
              </div>
            </section>

            <section className="arch-section" aria-labelledby="deps-heading">
              <h2 id="deps-heading" className="section-title">⬡ Dependencies</h2>
              <div className="arch-card tag-list">
                {(summary.dependencies || []).map((d) => (
                  <span key={d} className="arch-tag arch-tag-yellow">{d}</span>
                ))}
                {!summary.dependencies?.length && <span className="arch-empty-tag">None detected</span>}
              </div>
            </section>
          </div>

          {/* Raw Mermaid source */}
          <section className="arch-section" aria-labelledby="mermaid-src-heading">
            <h2 id="mermaid-src-heading" className="section-title">◎ Mermaid Source</h2>
            <div className="arch-card">
              <pre className="mermaid-source" tabIndex={0} aria-label="Mermaid diagram source code">
                {summary.mermaid_diagram}
              </pre>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function StatCard({ label, value, icon, color }) {
  return (
    <div
      className={`stat-card stat-${color}`}
      role="listitem"
      aria-label={`${label}: ${value ?? "unknown"}`}
    >
      <div className="stat-icon" aria-hidden="true">{icon}</div>
      <div className="stat-value">{value ?? "—"}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
