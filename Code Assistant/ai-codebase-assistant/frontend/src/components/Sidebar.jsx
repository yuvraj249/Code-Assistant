import { useState } from "react";
import AgentPanel from "./AgentPanel";
import "./Sidebar.css";

const NAV_ITEMS = [
  { id: "upload",       icon: "⬆",  label: "Upload Repo",  ariaLabel: "Go to Upload Repository page"  },
  { id: "chat",         icon: "◉",  label: "AI Chat",      ariaLabel: "Go to AI Chat page"            },
  { id: "architecture", icon: "⬡",  label: "Architecture", ariaLabel: "Go to Architecture Analysis page" },
  { id: "api-tester",   icon: "⚡", label: "API Tester",   ariaLabel: "Go to Interactive API Tester page" },
];

export default function Sidebar({ currentPage, setCurrentPage, activeRepo, mobileMenuOpen, setMobileMenuOpen }) {
  const [agentOpen, setAgentOpen] = useState(false);

  return (
    <aside className={`sidebar ${mobileMenuOpen ? "mobile-open" : ""}`} aria-label="Application sidebar">
      {/* Logo Header */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-left">
          <span className="logo-mark">▸▸</span>
          <span className="logo-text">CodeMind</span>
        </div>
        {setMobileMenuOpen && (
          <button
            className="sidebar-close-btn"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close sidebar navigation menu"
          >
            ✕
          </button>
        )}
      </div>

      {/* Active repo badge */}
      {activeRepo && (
        <div className="repo-badge" role="status" aria-label={`Active repository: ${activeRepo.repo_name}`}>
          <div className="repo-dot" aria-hidden="true" />
          <span className="repo-name">{activeRepo.repo_name}</span>
        </div>
      )}

      {/* Main navigation */}
      <nav className="sidebar-nav" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              id={`nav-${item.id}`}
              className={`nav-item ${isActive ? "active" : ""}`}
              onClick={() => {
                setCurrentPage(item.id);
                if (setMobileMenuOpen) setMobileMenuOpen(false);
              }}
              aria-label={item.ariaLabel}
              aria-current={isActive ? "page" : undefined}
              title={item.label}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {isActive && <span className="nav-indicator" aria-hidden="true" />}
            </button>
          );
        })}
      </nav>

      {/* Agent API panel toggle */}
      <div className="sidebar-section">
        <button
          className="agent-toggle-btn"
          onClick={() => setAgentOpen((v) => !v)}
          aria-expanded={agentOpen}
          aria-controls="agent-panel"
          aria-label={agentOpen ? "Close Agent API panel" : "Open Agent API panel"}
        >
          <span aria-hidden="true">⬡</span>
          <span>Agent API</span>
          <span className="toggle-chevron" aria-hidden="true">{agentOpen ? "▴" : "▾"}</span>
        </button>

        {agentOpen && (
          <div id="agent-panel" role="region" aria-label="Agent API documentation">
            <AgentPanel activeRepo={activeRepo} />
          </div>
        )}
      </div>

      {/* Bottom info */}
      <div className="sidebar-footer" aria-label="Application info">
        <div className="footer-label">RAG · Gemini 3.6 · Postman API</div>
        <div className="footer-version">v2.1.0</div>
      </div>
    </aside>
  );
}
