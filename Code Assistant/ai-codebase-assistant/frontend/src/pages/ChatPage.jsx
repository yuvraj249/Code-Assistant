import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import "./ChatPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const MODES = [
  { id: "explain",      label: "Explain",      icon: "◉", color: "purple" },
  { id: "bugs",         label: "Bug Hunt",     icon: "▲", color: "red"    },
  { id: "tests",        label: "Gen Tests",    icon: "◈", color: "green"  },
  { id: "architecture", label: "Architecture", icon: "⬡", color: "yellow" },
];

const EXAMPLE_QUESTIONS = [
  "Where is authentication implemented?",
  "Explain how the API layer works",
  "Which files interact with the database?",
  "Identify possible bugs in this module",
  "Summarize the architecture of this repository",
  "How do services communicate with each other?",
  "Generate unit tests for the main functions",
];

export default function ChatPage({ activeRepo, setCurrentPage }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [mode, setMode]         = useState("explain");
  const [loading, setLoading]   = useState(false);
  const bottomRef               = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async (question) => {
    const q = (question || input).trim();
    if (!q || loading) return;

    if (!activeRepo) {
      setMessages((m) => [...m, {
        role: "assistant",
        content: "⚠ No repository loaded. Please upload or connect a repo first.",
        mode: "explain",
      }]);
      return;
    }

    setMessages((m) => [...m, { role: "user", content: q, mode }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/ask-question`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, repo_id: activeRepo.repo_id, mode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Request failed");

      setMessages((m) => [...m, { role: "assistant", content: data.answer, mode }]);
    } catch (e) {
      setMessages((m) => [...m, {
        role: "assistant",
        content: `Error: ${e.message}`,
        mode: "error",
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-page">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-left">
          <h1 className="page-title">AI Chat</h1>
          {activeRepo ? (
            <span className="badge badge-green">● {activeRepo.repo_name}</span>
          ) : (
            <span className="badge badge-red">No repo loaded</span>
          )}
        </div>

        {/* Mode selector */}
        <div className="mode-selector">
          {MODES.map((m) => (
            <button
              key={m.id}
              className={`mode-btn ${mode === m.id ? "active" : ""} mode-${m.color}`}
              onClick={() => setMode(m.id)}
              title={m.label}
            >
              <span>{m.icon}</span>
              <span>{m.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="messages-area">
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-icon">◉</div>
            <div className="empty-title">Ask anything about the codebase</div>
            <div className="empty-subtitle">
              {activeRepo
                ? `Repository: ${activeRepo.repo_name} is ready`
                : "Load a repository first to get started"}
            </div>
            <div className="example-questions">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="example-q"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role} fade-in`}>
            {msg.role === "user" ? (
              <div className="user-bubble">
                <span className="user-label">you</span>
                <span>{msg.content}</span>
              </div>
            ) : (
              <div className="assistant-bubble">
                <div className="assistant-header">
                  <span className="assistant-label">
                    {MODES.find((m) => m.id === msg.mode)?.icon || "◉"} CodeMind
                  </span>
                  <span className={`badge badge-${modeColor(msg.mode)}`}>
                    {msg.mode}
                  </span>
                </div>
                <div className="markdown-body">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="message assistant fade-in">
            <div className="assistant-bubble">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="input-bar">
        <div className="input-wrapper">
          <span className="input-prompt">▸</span>
          <textarea
            rows={1}
            placeholder="Ask a question about the codebase…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
          />
          <button
            className="btn btn-primary send-btn"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
          >
            {loading ? <span className="spinner" /> : "↵ Send"}
          </button>
        </div>
        <div className="input-hint">Enter to send · Shift+Enter for new line · Mode: <strong>{mode}</strong></div>
      </div>
    </div>
  );
}

function modeColor(mode) {
  return { explain: "purple", bugs: "red", tests: "green", architecture: "yellow" }[mode] || "purple";
}
