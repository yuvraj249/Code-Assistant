import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import "./ChatPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const MODES = [
  { id: "explain",      label: "Explain",      icon: "◉", color: "purple", ariaLabel: "Explain mode: explain code, concepts, and architecture" },
  { id: "bugs",         label: "Bug Hunt",     icon: "▲", color: "red",    ariaLabel: "Bug Hunt mode: detect bugs and security issues" },
  { id: "tests",        label: "Gen Tests",    icon: "◈", color: "green",  ariaLabel: "Generate Tests mode: create unit test suites" },
  { id: "architecture", label: "Architecture", icon: "⬡", color: "yellow", ariaLabel: "Architecture mode: high-level structural analysis" },
];

const EXAMPLE_QUESTIONS = [
  "How do I implement JWT authentication in FastAPI?",
  "Explain the difference between interface and abstract class",
  "Write a Python script for async rate limiting",
  "How do vector embeddings work in RAG applications?",
  "What are common OWASP top 10 security vulnerabilities in REST APIs?",
  "Generate pytest unit tests for an async database connection pool",
];

export default function ChatPage({ activeRepo, setCurrentPage }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [mode, setMode]         = useState("explain");
  const [loading, setLoading]   = useState(false);
  const [streamingMsg, setStreamingMsg] = useState("");
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingMsg]);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const sendMessage = useCallback(async (question) => {
    const q = (question || input).trim();
    if (!q || loading) return;

    setMessages((m) => [...m, { role: "user", content: q, mode }]);
    if (!question) setInput("");
    setLoading(true);
    setStreamingMsg("");

    try {
      const res = await fetch(`${API}/stream-answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          repo_id: activeRepo?.repo_id || null,
          mode,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || "Request failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep trailing incomplete line in buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(trimmed.slice(6));
            if (payload.done) break;
            if (payload.error) {
              fullText = `⚠️ ${payload.error}`;
              break;
            }
            if (payload.token) {
              fullText += payload.token;
              setStreamingMsg(fullText);
            }
          } catch (parseErr) {
            // ignore JSON parse errors on broken lines
          }
        }
      }

      if (buffer.trim().startsWith("data: ")) {
        try {
          const payload = JSON.parse(buffer.trim().slice(6));
          if (payload.token) fullText += payload.token;
          if (payload.error) fullText = `⚠️ ${payload.error}`;
        } catch (e) {}
      }

      setMessages((m) => [...m, { role: "assistant", content: fullText || "No response generated.", mode }]);
      setStreamingMsg("");
    } catch (e) {
      setStreamingMsg("");
      setMessages((m) => [...m, {
        role: "assistant",
        content: `⚠️ **Connection Error**: ${e.message}`,
        mode: "explain",
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [input, mode, activeRepo, loading]);

  return (
    <main className="chat-page" id="main-content">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header-left">
          <h1 className="page-title">AI Assistant</h1>
          {activeRepo ? (
            <span className="badge badge-green" role="status" aria-label={`Active repository: ${activeRepo.repo_name}`}>
              ● {activeRepo.repo_name} (RAG Indexed)
            </span>
          ) : (
            <span className="badge badge-purple" role="status" aria-label="General Conversational Mode Active">
              ◈ Conversational AI Mode
            </span>
          )}
        </div>

        {/* Mode selector */}
        <div className="mode-selector" role="group" aria-label="Chat mode selection">
          {MODES.map((m) => (
            <button
              key={m.id}
              id={`mode-${m.id}`}
              className={`mode-btn ${mode === m.id ? "active" : ""} mode-${m.color}`}
              onClick={() => setMode(m.id)}
              aria-pressed={mode === m.id}
              aria-label={m.ariaLabel}
              title={m.label}
            >
              <span aria-hidden="true">{m.icon}</span>
              <span>{m.label}</span>
            </button>
          ))}
        </div>
      </header>

      {/* Messages */}
      <div
        className="messages-area"
        role="log"
        aria-label="Chat messages"
        aria-live="polite"
        aria-relevant="additions"
      >
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-icon" aria-hidden="true">◉</div>
            <div className="empty-title">Ask CodeMind anything</div>
            <div className="empty-subtitle">
              {activeRepo ? (
                <>RAG Search enabled for <strong>{activeRepo.repo_name}</strong></>
              ) : (
                <>Conversational AI Mode active · <button className="inline-link" onClick={() => setCurrentPage("upload")}>Upload a repository</button> for deep codebase search</>
              )}
            </div>
            <div className="example-questions" role="list" aria-label="Example questions">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="example-q"
                  role="listitem"
                  onClick={() => sendMessage(q)}
                  aria-label={`Ask: ${q}`}
                  tabIndex={0}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`message ${msg.role} fade-in`}
            role={msg.role === "assistant" ? "article" : "none"}
            aria-label={msg.role === "assistant" ? `CodeMind response (${msg.mode} mode)` : undefined}
          >
            {msg.role === "user" ? (
              <div className="user-bubble">
                <span className="user-label" aria-hidden="true">you</span>
                <span>{msg.content}</span>
              </div>
            ) : (
              <div className="assistant-bubble">
                <div className="assistant-header">
                  <span className="assistant-label">
                    <span aria-hidden="true">{MODES.find((m) => m.id === msg.mode)?.icon || "◉"}</span>
                    {" "}CodeMind
                  </span>
                  <span className={`badge badge-${modeColor(msg.mode)}`} aria-label={`Mode: ${msg.mode}`}>
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

        {/* Streaming message */}
        {streamingMsg && (
          <div className="message assistant fade-in" role="article" aria-label="CodeMind is responding">
            <div className="assistant-bubble">
              <div className="assistant-header">
                <span className="assistant-label">
                  <span aria-hidden="true">{MODES.find((m) => m.id === mode)?.icon || "◉"}</span>
                  {" "}CodeMind
                </span>
                <span className="badge badge-purple streaming-badge" aria-label="Streaming response">
                  <span className="streaming-dot" aria-hidden="true" /> streaming
                </span>
              </div>
              <div className="markdown-body">
                <ReactMarkdown>{streamingMsg}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {loading && !streamingMsg && (
          <div className="message assistant fade-in" role="status" aria-label="CodeMind is thinking">
            <div className="assistant-bubble">
              <div className="typing-indicator" aria-label="Loading…">
                <span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} aria-hidden="true" />
      </div>

      {/* Input bar */}
      <div className="input-bar" role="region" aria-label="Message input">
        <div className="input-wrapper">
          <span className="input-prompt" aria-hidden="true">▸</span>
          <textarea
            ref={inputRef}
            id="chat-input"
            rows={1}
            placeholder={activeRepo ? `Ask about ${activeRepo.repo_name} or general coding…` : "Ask any coding, architecture, or debugging question…"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            aria-label="Ask a question"
            aria-describedby="input-hint"
            disabled={loading}
          />
          <button
            className="btn btn-primary send-btn"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            aria-busy={loading}
            aria-label={loading ? "Sending…" : "Send message"}
          >
            {loading ? <span className="spinner" aria-hidden="true" /> : "↵ Send"}
          </button>
        </div>
        <div id="input-hint" className="input-hint">
          Enter to send · Shift+Enter for new line · Mode: <strong>{mode}</strong>
        </div>
      </div>
    </main>
  );
}

function modeColor(mode) {
  return { explain: "purple", bugs: "red", tests: "green", architecture: "yellow" }[mode] || "purple";
}
