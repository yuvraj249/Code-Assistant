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
  const [summary, setSummary]   = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [diagramSvg, setDiagramSvg] = useState("");
  const diagramRef              = useRef(null);

  useEffect(() => {
    if (activeRepo?.repo_id) fetchSummary();
  }, [activeRepo]);

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
    }
  };

  const renderDiagram = async (diagramCode) => {
    try {
      const id  = "mermaid-" + Date.now();
      const { svg } = await mermaid.render(id, diagramCode);
      setDiagramSvg(svg);
    } catch (e) {
      setDiagramSvg("");
      console.warn("Mermaid render failed:", e);
    }
  };

  if (!activeRepo) {
    return (
      <div className="arch-page">
        <div className="arch-empty">
          <div className="empty-icon">⬡</div>
          <div className="empty-title">No Repository Loaded</div>
          <p className="empty-sub">Upload or connect a repo to view its architecture.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="arch-page">
      {/* Header */}
      <div className="arch-header">
        <div>
          <div className="terminal-prompt">$ codemind --analyze architecture</div>
          <h1 className="page-title">Architecture Analysis</h1>
          <p className="page-subtitle">AI-generated overview of {activeRepo.repo_name}</p>
        </div>
        <button className="btn btn-ghost" onClick={fetchSummary} disabled={loading}>
          {loading ? <><span className="spinner" /> Analyzing…</> : "↺ Refresh"}
        </button>
      </div>

      {error && <div className="arch-error">⚠ {error}</div>}

      {loading && !summary && (
        <div className="arch-loading">
          <span className="spinner" />
          <span>Analyzing repository structure…</span>
        </div>
      )}

      {summary && (
        <div className="arch-content">
          {/* Stats row */}
          <div className="stats-row">
            <StatCard label="Language"     value={summary.language}     icon="◎" color="purple" />
            <StatCard label="Architecture" value={summary.architecture} icon="⬡" color="green"  />
            <StatCard label="Files"        value={summary.file_count}   icon="▦" color="yellow" />
            <StatCard label="Chunks"       value={summary.chunk_count}  icon="◈" color="purple" />
          </div>

          {/* Overview */}
          <section className="arch-section">
            <div className="section-title">◉ Overview</div>
            <div className="arch-card overview-text">{summary.overview}</div>
          </section>

          {/* Mermaid diagram */}
          {diagramSvg && (
            <section className="arch-section">
              <div className="section-title">⬡ Architecture Diagram</div>
              <div className="arch-card diagram-card">
                <div
                  ref={diagramRef}
                  className="mermaid-svg"
                  dangerouslySetInnerHTML={{ __html: diagramSvg }}
                />
              </div>
            </section>
          )}

          {/* Architecture explanation */}
          {summary.architecture_explanation && (
            <section className="arch-section">
              <div className="section-title">▲ Architecture Explanation</div>
              <div className="arch-card overview-text">{summary.architecture_explanation}</div>
            </section>
          )}

          {/* Modules + Key files + Dependencies */}
          <div className="three-col">
            <section className="arch-section">
              <div className="section-title">◈ Modules</div>
              <div className="arch-card tag-list">
                {(summary.modules || []).map((m) => (
                  <span key={m} className="arch-tag arch-tag-purple">{m}</span>
                ))}
              </div>
            </section>

            <section className="arch-section">
              <div className="section-title">▦ Key Files</div>
              <div className="arch-card tag-list">
                {(summary.key_files || []).map((f) => (
                  <span key={f} className="arch-tag arch-tag-green file-tag">{f}</span>
                ))}
              </div>
            </section>

            <section className="arch-section">
              <div className="section-title">⬡ Dependencies</div>
              <div className="arch-card tag-list">
                {(summary.dependencies || []).map((d) => (
                  <span key={d} className="arch-tag arch-tag-yellow">{d}</span>
                ))}
              </div>
            </section>
          </div>

          {/* Raw Mermaid source */}
          <section className="arch-section">
            <div className="section-title">◎ Mermaid Source</div>
            <div className="arch-card">
              <pre className="mermaid-source">{summary.mermaid_diagram}</pre>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }) {
  return (
    <div className={`stat-card stat-${color}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">{value ?? "—"}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
