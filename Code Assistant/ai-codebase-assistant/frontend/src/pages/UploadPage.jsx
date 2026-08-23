import { useState, useRef, useEffect } from "react";
import "./UploadPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const EXAMPLE_REPOS = [
  { label: "FastAPI",   url: "https://github.com/tiangolo/fastapi"  },
  { label: "Requests",  url: "https://github.com/psf/requests"      },
  { label: "Flask",     url: "https://github.com/pallets/flask"     },
];

const FEATURES = [
  { icon: "⬡", label: "RAG Search",    desc: "Semantic vector search over your code"        },
  { icon: "◉", label: "AI Answers",    desc: "GPT-4o-mini explains any part of the codebase" },
  { icon: "▲", label: "Bug Detection", desc: "Spot security and logic issues automatically"  },
  { icon: "◈", label: "Test Generator",desc: "Generate pytest / Jest unit tests instantly"   },
];

export default function UploadPage({ onRepoLoaded }) {
  const [tab, setTab]             = useState("github");
  const [githubUrl, setGithubUrl] = useState("");
  const [dragOver, setDragOver]   = useState(false);
  const [loading, setLoading]     = useState(false);
  const [status, setStatus]       = useState(null);
  const [savedRepos, setSavedRepos] = useState([]);
  const fileRef = useRef(null);

  // Load previously indexed repos on mount
  useEffect(() => {
    fetch(`${API}/repos`)
      .then((r) => r.json())
      .then((data) => { if (data.repos?.length) setSavedRepos(data.repos); })
      .catch(() => {});
  }, []);

  /* ── GitHub ingestion ── */
  const handleGithub = async () => {
    if (!githubUrl.trim()) return;
    setLoading(true); setStatus(null);
    try {
      const res = await fetch(`${API}/load-github-repo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_url: githubUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      setStatus({ type: "success", message: `✓ Indexed ${data.file_count} files · ${data.chunk_count} chunks` });
      setTimeout(() => onRepoLoaded({ repo_id: data.repo_id, repo_name: data.repo_name }), 800);
    } catch (e) {
      setStatus({ type: "error", message: e.message });
    } finally {
      setLoading(false);
    }
  };

  /* ── ZIP upload ── */
  const handleUpload = async (file) => {
    if (!file || !file.name.endsWith(".zip")) {
      setStatus({ type: "error", message: "Please upload a .zip archive of your repository." });
      return;
    }
    setLoading(true); setStatus(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API}/upload-repo`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      setStatus({ type: "success", message: `✓ Indexed ${data.file_count} files · ${data.chunk_count} chunks` });
      setTimeout(() => onRepoLoaded({ repo_id: data.repo_id, repo_name: data.repo_name }), 800);
    } catch (e) {
      setStatus({ type: "error", message: e.message });
    } finally {
      setLoading(false);
    }
  };

  /* ── Keyboard handler for drop zone ── */
  const handleDropZoneKey = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileRef.current?.click();
    }
  };

  return (
    <main className="upload-page" id="main-content">
      {/* Header */}
      <header className="upload-header">
        <div className="terminal-prompt" aria-hidden="true">$ codemind --init</div>
        <h1 className="page-title">Load a Repository</h1>
        <p className="page-subtitle">
          Connect a GitHub repo or upload a ZIP archive — we'll index everything for AI search.
        </p>
      </header>

      {/* Previously indexed repos */}
      {savedRepos.length > 0 && (
        <section className="saved-repos-section" aria-label="Previously indexed repositories">
          <div className="section-label">↻ Previously Indexed — click to reuse</div>
          <ul className="saved-repos-list" role="list">
            {savedRepos.map((repo) => (
              <li key={repo.repo_id}>
                <button
                  className="saved-repo-card"
                  onClick={() => onRepoLoaded({ repo_id: repo.repo_id, repo_name: repo.repo_name })}
                  aria-label={`Load ${repo.repo_name} — ${repo.file_count} files`}
                >
                  <span className="saved-repo-name">{repo.repo_name}</span>
                  <span className="saved-repo-meta">
                    {repo.file_count} files · {repo.chunk_count} chunks
                    {repo.github_url && <span className="saved-repo-badge">GitHub</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Tab switcher */}
      <div className="tab-bar" role="tablist" aria-label="Repository load method">
        <button
          id="tab-github"
          className={`tab-btn ${tab === "github" ? "active" : ""}`}
          role="tab"
          aria-selected={tab === "github"}
          aria-controls="panel-github"
          onClick={() => setTab("github")}
        >
          <span aria-hidden="true">◎</span> GitHub URL
        </button>
        <button
          id="tab-upload"
          className={`tab-btn ${tab === "upload" ? "active" : ""}`}
          role="tab"
          aria-selected={tab === "upload"}
          aria-controls="panel-upload"
          onClick={() => setTab("upload")}
        >
          <span aria-hidden="true">⬆</span> Upload ZIP
        </button>
      </div>

      {/* GitHub tab panel */}
      {tab === "github" && (
        <section
          id="panel-github"
          className="upload-card fade-in"
          role="tabpanel"
          aria-labelledby="tab-github"
        >
          <label className="field-label" htmlFor="github-url-input">Repository URL</label>
          <div className="url-input-row">
            <input
              id="github-url-input"
              type="url"
              placeholder="https://github.com/owner/repo"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGithub()}
              aria-label="GitHub repository URL"
              aria-describedby="github-url-hint"
              disabled={loading}
              autoComplete="url"
            />
            <button
              className="btn btn-primary"
              onClick={handleGithub}
              disabled={loading || !githubUrl.trim()}
              aria-busy={loading}
              aria-label={loading ? "Indexing repository…" : "Index this repository"}
            >
              {loading ? <><span className="spinner" aria-hidden="true" /> Indexing…</> : "→ Index"}
            </button>
          </div>
          <p id="github-url-hint" className="field-hint">
            Only public repositories are supported. Cloning may take 30–60 seconds.
          </p>

          <div className="example-repos" role="group" aria-label="Example repositories">
            <span className="field-label" id="example-repos-label">Try an example:</span>
            <div className="example-chips" aria-labelledby="example-repos-label">
              {EXAMPLE_REPOS.map((r) => (
                <button
                  key={r.url}
                  className="chip"
                  onClick={() => setGithubUrl(r.url)}
                  aria-label={`Load example: ${r.label}`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Upload tab panel */}
      {tab === "upload" && (
        <section
          id="panel-upload"
          className="upload-card fade-in"
          role="tabpanel"
          aria-labelledby="tab-upload"
        >
          <div
            className={`drop-zone ${dragOver ? "drag-over" : ""}`}
            role="button"
            tabIndex={0}
            aria-label="Drop zone: drag and drop a ZIP file here, or press Enter to browse"
            aria-describedby="drop-zone-hint"
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current?.click()}
            onKeyDown={handleDropZoneKey}
          >
            <div className="drop-icon" aria-hidden="true">⬆</div>
            <div className="drop-text">Drop your .zip here or click to browse</div>
            <div id="drop-zone-hint" className="drop-hint">ZIP your project folder before uploading</div>
            <input
              ref={fileRef}
              type="file"
              accept=".zip"
              aria-hidden="true"
              tabIndex={-1}
              style={{ display: "none" }}
              onChange={(e) => handleUpload(e.target.files[0])}
            />
          </div>
          {loading && (
            <div className="upload-progress" role="status" aria-live="polite">
              <span className="spinner" aria-hidden="true" />
              <span>Extracting &amp; indexing — this may take a minute…</span>
            </div>
          )}
        </section>
      )}

      {/* Status */}
      {status && (
        <div
          className={`status-bar ${status.type} fade-in`}
          role="alert"
          aria-live="assertive"
        >
          {status.message}
        </div>
      )}

      {/* Feature grid */}
      <section className="feature-grid" aria-label="CodeMind features">
        {FEATURES.map((f) => (
          <article key={f.label} className="feature-card" aria-label={`${f.label}: ${f.desc}`}>
            <div className="feature-icon" aria-hidden="true">{f.icon}</div>
            <div className="feature-label">{f.label}</div>
            <div className="feature-desc">{f.desc}</div>
          </article>
        ))}
      </section>
    </main>
  );
}
