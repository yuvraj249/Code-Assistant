import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import "./ChatPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const MODES = [
  { id: "explain",      label: "Explain",      icon: "◉", color: "purple", ariaLabel: "Explain mode: explain code and architecture" },
  { id: "bugs",         label: "Bug Hunt",     icon: "▲", color: "red",    ariaLabel: "Bug Hunt mode: detect bugs and vulnerabilities" },
  { id: "tests",        label: "Gen Tests",    icon: "◈", color: "green",  ariaLabel: "Generate Tests mode: create unit tests" },
  { id: "architecture", label: "Architecture", icon: "⬡", color: "yellow", ariaLabel: "Architecture mode: high-level architectural analysis" },
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
  const [streamingMsg, setStreamingMsg] = useState("");
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingMsg]);

  // Focus input on mount
  useEffect(() => { inputRef.current?.focus(); }, []);

  const sendMessage = useCallback(async (question) => {
    const q = (question || input).trim();
    if (!q || loading) return;

    if (!activeRepo) {
      setMessages((m) => [...m, {
        role: "assistant", content: "⚠ No repository loaded. Please upload or connect a repo first.", mode: "explain",
      }]);
      return;
    }

    setMessages((m) => [...m, { role: "user", content: q, mode }]);
    if (!question) setInput("");
    setLoading(true);
    setStreamingMsg("");

    try {
      // Use SSE streaming endpoint
      const res = await fetch(`${API}/stream-answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, repo_id: activeRepo.repo_id, mode }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || "Request failed");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.done) break;
            if (payload.error) throw new Error(payload.error);
            if (payload.token) {
              fullText += payload.token;
              setStreamingMsg(fullText);
            }
          } catch (parseErr) {
            // skip malformed lines
          }
        }
      }

      setMessages((m) => [...m, { role: "assistant", content: fullText, mode }]);
      setStreamingMsg("");
    } catch (e) {
      setStreamingMsg("");
      setMessages((m) => [...m, {
        role: "assistant", content: `❌ ${e.message}`, mode: "error",
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
          <h1 className="page-title">AI Chat</h1>
          {activeRepo ? (
            <span className="badge badge-green" role="status" aria-label={`Active repository: ${activeRepo.repo_name}`}>
              ● {activeRepo.repo_name}
            </span>
          ) : (
            <span className="badge badge-red" role="alert">No repo loaded</span>
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
            <div className="empty-title">Ask anything about the codebase</div>
            <div className="empty-subtitle">
              {activeRepo
                ? `Repository: ${activeRepo.repo_name} is ready`
                : <>Load a repository first. <button className="inline-link" onClick={() => setCurrentPage("upload")}>Go to Upload</button></>}
            </div>
            {activeRepo && (
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
            )}
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
            placeholder="Ask a question about the codebase…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            aria-label="Ask a question about the codebase"
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
