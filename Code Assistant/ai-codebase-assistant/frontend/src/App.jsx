import { useState } from "react";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import ArchitecturePage from "./pages/ArchitecturePage";
import ApiTesterPage from "./pages/ApiTesterPage";
import Sidebar from "./components/Sidebar";
import "./styles/globals.css";

export default function App() {
  const [currentPage, setCurrentPage] = useState("upload");
  const [activeRepo, setActiveRepo] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Skip-to-content for keyboard users */}
      <a href="#main-content" className="skip-link">Skip to main content</a>

      <div className="app-shell">
        {/* Top Mobile Bar for small screens */}
        <header className="mobile-topbar" aria-label="Mobile Navigation Header">
          <div className="mobile-logo">
            <span className="logo-mark">▸▸</span>
            <span className="logo-text">CodeMind</span>
          </div>

          <div className="mobile-topbar-right">
            {activeRepo && (
              <span className="mobile-repo-badge">
                <span className="repo-dot" />
                <span className="mobile-repo-text">{activeRepo.repo_name}</span>
              </span>
            )}
            <button
              className="mobile-hamburger-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? "✕" : "☰"}
            </button>
          </div>
        </header>

        {/* Mobile Backdrop */}
        {mobileMenuOpen && (
          <div
            className="sidebar-backdrop"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
        )}

        <Sidebar
          currentPage={currentPage}
          setCurrentPage={(page) => {
            setCurrentPage(page);
            setMobileMenuOpen(false);
          }}
          activeRepo={activeRepo}
          mobileMenuOpen={mobileMenuOpen}
          setMobileMenuOpen={setMobileMenuOpen}
        />

        <main className="main-content" id="root-main">
          {currentPage === "upload" && (
            <UploadPage
              onRepoLoaded={(repo) => {
                setActiveRepo(repo);
                setCurrentPage("chat");
              }}
            />
          )}
          {currentPage === "chat" && (
            <ChatPage activeRepo={activeRepo} setCurrentPage={setCurrentPage} />
          )}
          {currentPage === "architecture" && (
            <ArchitecturePage activeRepo={activeRepo} />
          )}
          {currentPage === "api-tester" && (
            <ApiTesterPage activeRepo={activeRepo} setCurrentPage={setCurrentPage} />
          )}
        </main>
      </div>
    </>
  );
}
