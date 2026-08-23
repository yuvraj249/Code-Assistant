/**
 * AgentPanel — Shows the /api/agent endpoint docs inline in the sidebar.
 * Lets developers see exactly how to use CodeMind as a pluggable AI agent.
 */
import "./AgentPanel.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
const BASE = API.replace("/api", "");

export default function AgentPanel({ activeRepo }) {
  const repoId = activeRepo?.repo_id ?? "YOUR_REPO_ID";

  const curlCmd = `curl -X POST ${BASE}/api/agent \\
  -H "Content-Type: application/json" \\
  -d '{
    "question": "Where is auth implemented?",
    "repo_id": "${repoId}",
    "mode": "explain"
  }'`;

  const schema = `{
  "question": "string",    // Your question
  "repo_id":  "string",    // From /api/repos
  "mode": "explain"        // explain | bugs | tests | architecture
  "return_citations": true // Include source citations
}`;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="agent-panel" role="region" aria-label="Agent API documentation">
      <p className="agent-desc">
        Call CodeMind from any AI pipeline — LangGraph, Claude tools, or your own agent.
      </p>

      <div className="agent-section">
        <div className="agent-section-title">
          <span>POST /api/agent</span>
          <button
            className="copy-btn"
            onClick={() => copyToClipboard(curlCmd)}
            aria-label="Copy curl command to clipboard"
            title="Copy"
          >
            ⧉ Copy
          </button>
        </div>
        <pre className="agent-code" tabIndex={0} aria-label="Example curl command">
          {curlCmd}
        </pre>
      </div>

      <div className="agent-section">
        <div className="agent-section-title">Request Schema</div>
        <pre className="agent-code" tabIndex={0} aria-label="Request JSON schema">
          {schema}
        </pre>
      </div>

      <div className="agent-section">
        <div className="agent-section-title">4 Chat Modes</div>
        <ul className="agent-modes" role="list">
          {[
            { mode: "explain",      label: "Explain code & architecture"   },
            { mode: "bugs",         label: "Detect bugs & vulnerabilities" },
            { mode: "tests",        label: "Generate unit tests"           },
            { mode: "architecture", label: "Architectural analysis"        },
          ].map(({ mode, label }) => (
            <li key={mode} className="agent-mode-item">
              <code className="mode-code">{mode}</code>
              <span className="mode-label">{label}</span>
            </li>
          ))}
        </ul>
      </div>

      <a
        href={`${BASE}/docs#/Agent/agent_endpoint_api_agent_post`}
        target="_blank"
        rel="noopener noreferrer"
        className="agent-docs-link"
        aria-label="Open interactive API docs in new tab"
      >
        ↗ Open Interactive Docs
      </a>
    </div>
  );
}
