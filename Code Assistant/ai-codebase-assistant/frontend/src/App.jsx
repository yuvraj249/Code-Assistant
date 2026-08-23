import { useState } from "react";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import ArchitecturePage from "./pages/ArchitecturePage";
import Sidebar from "./components/Sidebar";
import "./styles/globals.css";

export default function App() {
  const [currentPage, setCurrentPage] = useState("upload");
  const [activeRepo, setActiveRepo] = useState(null);

  return (
    <>
      {/* Skip-to-content for keyboard users */}
      <a href="#main-content" className="skip-link">Skip to main content</a>

      <div className="app-shell">
        <Sidebar
          currentPage={currentPage}
          setCurrentPage={setCurrentPage}
          activeRepo={activeRepo}
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
        </main>
      </div>
    </>
  );
}
