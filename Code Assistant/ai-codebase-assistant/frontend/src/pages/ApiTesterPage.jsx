import { useState, useEffect, useRef } from "react";
import "./ApiTesterPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const HTTP_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"];

export default function ApiTesterPage({ activeRepo, setCurrentPage }) {
  const [endpoints, setEndpoints] = useState([]);
  const [loadingEndpoints, setLoadingEndpoints] = useState(false);
  const [methodFilter, setMethodFilter] = useState("ALL");

  // Active request state
  const [method, setMethod] = useState("GET");
  const [url, setUrl] = useState("http://localhost:8000/health");
  const [headersText, setHeadersText] = useState('{\n  "Content-Type": "application/json"\n}');
  const [bodyText, setBodyText] = useState('{\n  "example": "data"\n}');
  const [activeTab, setActiveTab] = useState("body"); // "body" | "headers" | "response"

  // Response state
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState(null); // { status_code, elapsed_ms, headers, data, error }

  const urlInputRef = useRef(null);

  // Load auto-detected endpoints when activeRepo changes
  useEffect(() => {
    if (activeRepo?.repo_id) {
      fetchEndpoints(activeRepo.repo_id);
    }
  }, [activeRepo]);

  const fetchEndpoints = async (repoId) => {
    setLoadingEndpoints(true);
    try {
      const res = await fetch(`${API}/repo-endpoints/${repoId}`);
      const data = await res.json();
      if (data.endpoints?.length) {
        setEndpoints(data.endpoints);
        // Pre-select first endpoint
        selectEndpoint(data.endpoints[0]);
      } else {
        setEndpoints([]);
      }
    } catch (e) {
      setEndpoints([]);
    } finally {
      setLoadingEndpoints(false);
    }
  };

  const selectEndpoint = (ep) => {
    setMethod(ep.method.toUpperCase());
    const baseUrl = "http://localhost:8000";
    const path = ep.path.startsWith("/") ? ep.path : `/${ep.path}`;
    setUrl(`${baseUrl}${path}`);
    if (ep.sample_body) setBodyText(ep.sample_body);
    if (ep.headers) setHeadersText(JSON.stringify(ep.headers, null, 2));
    setActiveTab(ep.method === "GET" ? "response" : "body");
  };

  const sendRequest = async () => {
    setSending(true);
    setResponse(null);
    setActiveTab("response");

    let parsedHeaders = {};
    try {
      if (headersText.trim()) parsedHeaders = JSON.parse(headersText);
    } catch (e) {
      setResponse({ status_code: 0, elapsed_ms: 0, error: "Invalid JSON in Headers tab" });
      setSending(false);
      return;
    }

    try {
      const res = await fetch(`${API}/proxy-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method,
          url,
          headers: parsedHeaders,
          body: method !== "GET" ? bodyText : null,
        }),
      });

      const data = await res.json();
      setResponse(data);
    } catch (e) {
      setResponse({ status_code: 0, elapsed_ms: 0, error: e.message });
    } finally {
      setSending(false);
    }
  };

  const filteredEndpoints = endpoints.filter(
    (e) => methodFilter === "ALL" || e.method.toUpperCase() === methodFilter
  );

  return (
    <main className="api-tester-page" id="main-content">
      {/* Header */}
      <header className="tester-header">
        <div>
          <div className="terminal-prompt" aria-hidden="true">$ codemind --api-tester</div>
          <h1 className="page-title">⚡ Interactive API Tester</h1>
          <p className="page-subtitle">Auto-extract REST routes from repository and test API calls live</p>
        </div>
        {activeRepo ? (
          <span className="badge badge-green" role="status">● {activeRepo.repo_name}</span>
        ) : (
          <span className="badge badge-purple" role="status">◈ Demo Endpoint Mode</span>
        )}
      </header>

      <div className="tester-layout">
        {/* Left Sidebar: Detected Routes */}
        <aside className="routes-sidebar" aria-label="Detected API Endpoints">
          <div className="routes-header">
            <span className="routes-title">Detected Routes</span>
            <button
              className="refresh-btn"
              onClick={() => activeRepo && fetchEndpoints(activeRepo.repo_id)}
              disabled={loadingEndpoints || !activeRepo}
              aria-label="Refresh endpoints"
              title="Rescan repository"
            >
              ↺
            </button>
          </div>

          {/* Filter pills */}
          <div className="method-filters" role="group" aria-label="Filter by HTTP method">
            {["ALL", "GET", "POST", "PUT", "DELETE"].map((m) => (
              <button
                key={m}
                className={`filter-chip ${methodFilter === m ? "active" : ""}`}
                onClick={() => setMethodFilter(m)}
                aria-pressed={methodFilter === m}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Endpoints List */}
          {loadingEndpoints ? (
            <div className="routes-loading">
              <span className="spinner" aria-hidden="true" /> Extracting endpoints…
            </div>
          ) : filteredEndpoints.length > 0 ? (
            <ul className="routes-list" role="list">
              {filteredEndpoints.map((ep, i) => (
                <li key={i}>
                  <button
                    className="route-card"
                    onClick={() => selectEndpoint(ep)}
                    aria-label={`Test ${ep.method} ${ep.path}`}
                  >
                    <span className={`method-badge method-${ep.method.toLowerCase()}`}>
                      {ep.method}
                    </span>
                    <span className="route-path" title={ep.path}>{ep.path}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="routes-empty">
              {activeRepo ? (
                <>No REST routes auto-detected in <strong>{activeRepo.repo_name}</strong>. You can manually enter any URL on the right.</>
              ) : (
                <>Upload a repository to auto-detect its REST API routes, or test any local/external endpoint directly!</>
              )}
            </div>
          )}
        </aside>

        {/* Right Main Panel: Request & Response Playground */}
        <section className="playground-main" aria-label="API Playground">
          {/* URL & Method Bar */}
          <div className="url-bar">
            <select
              className="method-select"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              aria-label="HTTP Method"
            >
              {HTTP_METHODS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>

            <input
              ref={urlInputRef}
              type="text"
              className="url-input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendRequest()}
              placeholder="http://localhost:8000/api/endpoint"
              aria-label="Target Request URL"
            />

            <button
              className="btn btn-primary send-request-btn"
              onClick={sendRequest}
              disabled={sending || !url.trim()}
              aria-busy={sending}
            >
              {sending ? <span className="spinner" aria-hidden="true" /> : "⚡ Send"}
            </button>
          </div>

          {/* Playground Tabs */}
          <div className="playground-tabs" role="tablist" aria-label="Request Payload Tabs">
            <button
              className={`p-tab ${activeTab === "body" ? "active" : ""}`}
              onClick={() => setActiveTab("body")}
              role="tab"
              aria-selected={activeTab === "body"}
            >
              Body (JSON)
            </button>
            <button
              className={`p-tab ${activeTab === "headers" ? "active" : ""}`}
              onClick={() => setActiveTab("headers")}
              role="tab"
              aria-selected={activeTab === "headers"}
            >
              Headers
            </button>
            <button
              className={`p-tab ${activeTab === "response" ? "active" : ""}`}
              onClick={() => setActiveTab("response")}
              role="tab"
              aria-selected={activeTab === "response"}
            >
              Response {response && <span className={`status-pill status-${statusColor(response.status_code)}`}>{response.status_code || "ERR"}</span>}
            </button>
          </div>

          {/* Tab Contents */}
          <div className="tab-content-area">
            {activeTab === "body" && (
              <div className="tab-pane">
                <label className="field-label">Request Body (JSON)</label>
                <textarea
                  className="code-textarea"
                  rows={10}
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  placeholder='{\n  "key": "value"\n}'
                  aria-label="Request body JSON"
                />
              </div>
            )}

            {activeTab === "headers" && (
              <div className="tab-pane">
                <label className="field-label">HTTP Headers (JSON)</label>
                <textarea
                  className="code-textarea"
                  rows={8}
                  value={headersText}
                  onChange={(e) => setHeadersText(e.target.value)}
                  placeholder='{\n  "Authorization": "Bearer token"\n}'
                  aria-label="Request headers JSON"
                />
              </div>
            )}

            {activeTab === "response" && (
              <div className="tab-pane">
                {sending ? (
                  <div className="response-loading" role="status">
                    <span className="spinner" aria-hidden="true" /> Executing HTTP Request to {url}…
                  </div>
                ) : response ? (
                  <div className="response-viewer fade-in">
                    <div className="response-meta">
                      <span className={`status-badge status-${statusColor(response.status_code)}`}>
                        {response.status_code ? `Status: ${response.status_code}` : "Connection Failed"}
                      </span>
                      <span className="meta-item">⏱ {response.elapsed_ms} ms</span>
                    </div>

                    <label className="field-label">Response Body</label>
                    <pre className="response-body-code" tabIndex={0}>
                      {typeof response.data === "object"
                        ? JSON.stringify(response.data, null, 2)
                        : response.data || response.error}
                    </pre>
                  </div>
                ) : (
                  <div className="response-empty">
                    Click <strong>⚡ Send</strong> to execute an HTTP request and inspect the live response.
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function statusColor(code) {
  if (code >= 200 && code < 300) return "green";
  if (code >= 300 && code < 400) return "yellow";
  if (code >= 400) return "red";
  return "muted";
}
