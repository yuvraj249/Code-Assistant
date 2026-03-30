import { useState, useRef } from "react";
import "./UploadPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const EXAMPLE_REPOS = [
  { label: "FastAPI",      url: "https://github.com/tiangolo/fastapi" },
  { label: "Requests",     url: "https://github.com/psf/requests" },
  { label: "Flask",        url: "https://github.com/pallets/flask" },
];

export default function UploadPage({ onRepoLoaded }) {
  const [tab, setTab]             = useState("github");   // "github" | "upload"
  const [githubUrl, setGithubUrl] = useState("");
  const [dragOver, setDragOver]   = useState(false);
  const [loading, setLoading]     = useState(false);
  const [status, setStatus]       = useState(null);       // { type, message }
  const fileRef                   = useRef(null);

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

  return (
    <div className="upload-page">
      {/* Header */}
      <div className="upload-header">
        <div className="terminal-prompt">$ codemind --init</div>
        <h1 className="page-title">Load a Repository</h1>
        <p className="page-subtitle">
          Connect a GitHub repo or upload a ZIP archive → we'll index everything for AI search.
        </p>
      </div>

      {/* Tab switcher */}
      <div className="tab-bar">
        <button className={`tab-btn ${tab === "github" ? "active" : ""}`} onClick={() => setTab("github")}>
          <span>◎ GitHub URL</span>
        </button>
        <button className={`tab-btn ${tab === "upload" ? "active" : ""}`} onClick={() => setTab("upload")}>
          <span>⬆ Upload ZIP</span>
        </button>
      </div>

      {/* GitHub tab */}
      {tab === "github" && (
        <div className="upload-card fade-in">
          <label className="field-label">Repository URL</label>
          <div className="url-input-row">
            <input
              type="text"
              placeholder="https://github.com/owner/repo"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGithub()}
            />
            <button className="btn btn-primary" onClick={handleGithub} disabled={loading || !githubUrl.trim()}>
              {loading ? <span className="spinner" /> : "→ Index"}
            </button>
          </div>

          <div className="example-repos">
            <span className="field-label">Try an example:</span>
            <div className="example-chips">
              {EXAMPLE_REPOS.map((r) => (
                <button key={r.url} className="chip" onClick={() => setGithubUrl(r.url)}>
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Upload tab */}
      {tab === "upload" && (
        <div className="upload-card fade-in">
          <div
            className={`drop-zone ${dragOver ? "drag-over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current?.click()}
          >
            <div className="drop-icon">⬆</div>
            <div className="drop-text">Drop your .zip here or click to browse</div>
            <div className="drop-hint">ZIP your project folder before uploading</div>
            <input
              ref={fileRef}
              type="file"
              accept=".zip"
              style={{ display: "none" }}
              onChange={(e) => handleUpload(e.target.files[0])}
            />
          </div>
          {loading && (
            <div className="upload-progress">
              <span className="spinner" />
              <span>Extracting & indexing — this may take a minute…</span>
            </div>
          )}
        </div>
      )}

      {/* Status */}
      {status && (
        <div className={`status-bar ${status.type} fade-in`}>
          {status.message}
        </div>
      )}

      {/* Feature grid */}
      <div className="feature-grid">
        {[
          { icon: "⬡", label: "RAG Search",     desc: "Semantic vector search over your code" },
          { icon: "◉", label: "AI Answers",      desc: "GPT-4o explains any part of the codebase" },
          { icon: "▲", label: "Bug Detection",   desc: "Spot security and logic issues automatically" },
          { icon: "◈", label: "Test Generator",  desc: "Generate pytest / Jest unit tests instantly" },
        ].map((f) => (
          <div key={f.label} className="feature-card">
            <div className="feature-icon">{f.icon}</div>
            <div className="feature-label">{f.label}</div>
            <div className="feature-desc">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
