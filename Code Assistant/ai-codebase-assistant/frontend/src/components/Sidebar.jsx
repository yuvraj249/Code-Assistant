import "./Sidebar.css";

const NAV_ITEMS = [
  { id: "upload",       icon: "⬆",  label: "Upload Repo"   },
  { id: "chat",         icon: "◉",  label: "AI Chat"       },
  { id: "architecture", icon: "⬡",  label: "Architecture"  },
];

export default function Sidebar({ currentPage, setCurrentPage, activeRepo }) {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <span className="logo-mark">▸▸</span>
        <span className="logo-text">CodeMind</span>
      </div>

      {/* Active repo badge */}
      {activeRepo && (
        <div className="repo-badge">
          <div className="repo-dot" />
          <span className="repo-name">{activeRepo.repo_name}</span>
        </div>
      )}

      {/* Nav */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${currentPage === item.id ? "active" : ""}`}
            onClick={() => setCurrentPage(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
            {currentPage === item.id && <span className="nav-indicator" />}
          </button>
        ))}
      </nav>

      {/* Bottom info */}
      <div className="sidebar-footer">
        <div className="footer-label">RAG · ChromaDB · GPT-4o</div>
        <div className="footer-version">v1.0.0</div>
      </div>
    </aside>
  );
}
