import { useState, useEffect, useRef } from "react";
import "./ApiTesterPage.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const HTTP_METHODS = [
  { method: "GET", color: "method-get" },
  { method: "POST", color: "method-post" },
  { method: "PUT", color: "method-put" },
  { method: "DELETE", color: "method-delete" },
  { method: "PATCH", color: "method-patch" },
];

export default function ApiTesterPage({ activeRepo }) {
  const [endpoints, setEndpoints] = useState([]);
  const [loadingEndpoints, setLoadingEndpoints] = useState(false);
  const [methodFilter, setMethodFilter] = useState("ALL");

  // Request state
  const [method, setMethod] = useState("GET");
  const [url, setUrl] = useState("http://localhost:8000/health");
  const [headers, setHeaders] = useState([
    { key: "Content-Type", value: "application/json", active: true },
    { key: "Accept", value: "application/json", active: true },
  ]);
  const [bodyText, setBodyText] = useState('{\n  "example": "data"\n}');
  const [activeTab, setActiveTab] = useState("params"); // "params" | "headers" | "body" | "response"

  // Response state
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState(null);
  const [responseView, setResponseView] = useState("pretty"); // "pretty" | "raw"

  const urlInputRef = useRef(null);

  useEffect(() => {
    if (activeRepo?.repo_id) fetchEndpoints(activeRepo.repo_id);
  }, [activeRepo]);

  const fetchEndpoints = async (repoId) => {
    setLoadingEndpoints(true);
    try {
      const res = await fetch(`${API}/repo-endpoints/${repoId}`);
      const data = await res.json();
      if (data.endpoints?.length) {
        setEndpoints(data.endpoints);
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
    const m = ep.method.toUpperCase();
    setMethod(m);
    const baseUrl = "http://localhost:8000";
    const path = ep.path.startsWith("/") ? ep.path : `/${ep.path}`;
    setUrl(`${baseUrl}${path}`);

    if (ep.sample_body) setBodyText(ep.sample_body);

    if (ep.headers && typeof ep.headers === "object") {
      const parsed = Object.entries(ep.headers).map(([k, v]) => ({
        key: k,
        value: v,
        active: true,
      }));
      setHeaders(parsed.length ? parsed : [{ key: "Content-Type", value: "application/json", active: true }]);
    }

    setActiveTab(m === "GET" ? "params" : "body");
  };

  // Header Key-Value row controls
  const addHeaderRow = () => {
    setHeaders([...headers, { key: "", value: "", active: true }]);
  };

  const updateHeaderRow = (index, field, val) => {
    const updated = [...headers];
    updated[index][field] = val;
    setHeaders(updated);
  };

  const removeHeaderRow = (index) => {
    setHeaders(headers.filter((_, i) => i !== index));
  };

  const prettifyJson = () => {
    try {
      const parsed = JSON.parse(bodyText);
      setBodyText(JSON.stringify(parsed, null, 2));
    } catch (e) {}
  };

  const sendRequest = async () => {
    setSending(true);
    setResponse(null);
    setActiveTab("response");

    const headerDict = {};
    headers.forEach((h) => {
      if (h.active && h.key.trim()) {
        headerDict[h.key.trim()] = h.value;
      }
    });

    try {
      const res = await fetch(`${API}/proxy-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          method,
          url,
          headers: headerDict,
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
      {/* Sleek Postman Top Header */}
      <header className="pm-header">
        <div className="pm-header-left">
          <div className="pm-logo-mark" aria-hidden="true">🚀</div>
          <div>
            <h1 className="pm-title">API Client &amp; Testing Playground</h1>
            <p className="pm-subtitle">Postman-compatible endpoint runner &amp; auto-discovered routes</p>
          </div>
        </div>
        {activeRepo ? (
          <span className="pm-repo-badge">● {activeRepo.repo_name}</span>
        ) : (
          <span className="pm-mode-badge">◈ Standalone API Mode</span>
        )}
      </header>

      <div className="pm-layout">
        {/* Left Sidebar: Discovered Routes */}
        <aside className="pm-sidebar" aria-label="Detected API Endpoints">
          <div className="pm-sidebar-header">
            <span className="pm-sidebar-title">Discovered Routes</span>
            <button
              className="pm-icon-btn"
              onClick={() => activeRepo && fetchEndpoints(activeRepo.repo_id)}
              disabled={loadingEndpoints || !activeRepo}
              aria-label="Refresh endpoints"
              title="Rescan repository"
            >
              ↺
            </button>
          </div>

          {/* Filter Pills */}
          <div className="pm-method-filters" role="group" aria-label="Filter routes by method">
            {["ALL", "GET", "POST", "PUT", "DELETE"].map((m) => (
              <button
                key={m}
                className={`pm-filter-pill ${methodFilter === m ? "active" : ""}`}
                onClick={() => setMethodFilter(m)}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Route List */}
          {loadingEndpoints ? (
            <div className="pm-routes-loading">
              <span className="spinner" aria-hidden="true" /> Scanning code for routes…
            </div>
          ) : filteredEndpoints.length > 0 ? (
            <ul className="pm-routes-list" role="list">
              {filteredEndpoints.map((ep, i) => (
                <li key={i}>
                  <button
                    className="pm-route-item"
                    onClick={() => selectEndpoint(ep)}
                    aria-label={`Test ${ep.method} ${ep.path}`}
                  >
                    <span className={`pm-method-tag pm-tag-${ep.method.toLowerCase()}`}>
                      {ep.method}
                    </span>
                    <span className="pm-route-path" title={ep.path}>{ep.path}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="pm-routes-empty">
              {activeRepo ? (
                <>No REST routes found in <strong>{activeRepo.repo_name}</strong>. Enter any URL manually on the right!</>
              ) : (
                <>Upload a repository to auto-detect its API routes, or test any URL directly!</>
              )}
            </div>
          )}
        </aside>

        {/* Right Main Panel: Postman Request Runner */}
        <section className="pm-main-panel" aria-label="Request Builder">
          {/* Postman URL & Method Input Bar */}
          <div className="pm-url-container">
            <div className="pm-url-bar">
              <select
                className={`pm-method-select pm-method-${method.toLowerCase()}`}
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                aria-label="HTTP Method"
              >
                {HTTP_METHODS.map((m) => (
                  <option key={m.method} value={m.method} className={`pm-opt-${m.method.toLowerCase()}`}>
                    {m.method}
                  </option>
                ))}
              </select>

              <div className="pm-url-divider" aria-hidden="true" />

              <input
                ref={urlInputRef}
                type="text"
                className="pm-url-input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendRequest()}
                placeholder="http://localhost:8000/api/endpoint"
                aria-label="Request URL"
              />

              <button
                className="pm-send-btn"
                onClick={sendRequest}
                disabled={sending || !url.trim()}
                aria-busy={sending}
              >
                {sending ? <span className="spinner" aria-hidden="true" /> : "Send"}
              </button>
            </div>
          </div>

          {/* Request Sub-Tabs */}
          <div className="pm-tabs-bar" role="tablist" aria-label="Request configurations">
            <button
              className={`pm-tab-item ${activeTab === "params" ? "active" : ""}`}
              onClick={() => setActiveTab("params")}
              role="tab"
              aria-selected={activeTab === "params"}
            >
              Params
            </button>
            <button
              className={`pm-tab-item ${activeTab === "headers" ? "active" : ""}`}
              onClick={() => setActiveTab("headers")}
              role="tab"
              aria-selected={activeTab === "headers"}
            >
              Headers ({headers.filter((h) => h.active && h.key).length})
            </button>
            <button
              className={`pm-tab-item ${activeTab === "body" ? "active" : ""}`}
              onClick={() => setActiveTab("body")}
              role="tab"
              aria-selected={activeTab === "body"}
            >
              Body {method !== "GET" && <span className="pm-body-dot" />}
            </button>
            <button
              className={`pm-tab-item ${activeTab === "response" ? "active" : ""}`}
              onClick={() => setActiveTab("response")}
              role="tab"
              aria-selected={activeTab === "response"}
            >
              Response {response && (
                <span className={`pm-status-chip pm-chip-${statusColor(response.status_code)}`}>
                  {response.status_code || "ERR"}
                </span>
              )}
            </button>
          </div>

          {/* Request Config Panes */}
          <div className="pm-pane-container">
            {/* Params Pane */}
            {activeTab === "params" && (
              <div className="pm-pane">
                <div className="pm-pane-header">Query Parameters</div>
                <div className="pm-kv-table">
                  <div className="pm-kv-row pm-kv-head">
                    <span className="pm-col-check"></span>
                    <span className="pm-col-key">KEY</span>
                    <span className="pm-col-val">VALUE</span>
                  </div>
                  <div className="pm-kv-row">
                    <span className="pm-col-check"><input type="checkbox" defaultChecked /></span>
                    <span className="pm-col-key"><input type="text" placeholder="e.g. limit" className="pm-kv-input" /></span>
                    <span className="pm-col-val"><input type="text" placeholder="e.g. 10" className="pm-kv-input" /></span>
                  </div>
                </div>
              </div>
            )}

            {/* Headers Key-Value Table */}
            {activeTab === "headers" && (
              <div className="pm-pane">
                <div className="pm-pane-header">
                  <span>HTTP Request Headers</span>
                  <button className="pm-text-btn" onClick={addHeaderRow}>+ Add Header</button>
                </div>
                <div className="pm-kv-table">
                  <div className="pm-kv-row pm-kv-head">
                    <span className="pm-col-check"></span>
                    <span className="pm-col-key">KEY</span>
                    <span className="pm-col-val">VALUE</span>
                    <span className="pm-col-action"></span>
                  </div>
                  {headers.map((h, i) => (
                    <div key={i} className="pm-kv-row">
                      <span className="pm-col-check">
                        <input
                          type="checkbox"
                          checked={h.active}
                          onChange={(e) => updateHeaderRow(i, "active", e.target.checked)}
                        />
                      </span>
                      <span className="pm-col-key">
                        <input
                          type="text"
                          className="pm-kv-input"
                          placeholder="Header key (e.g. Authorization)"
                          value={h.key}
                          onChange={(e) => updateHeaderRow(i, "key", e.target.value)}
                        />
                      </span>
                      <span className="pm-col-val">
                        <input
                          type="text"
                          className="pm-kv-input"
                          placeholder="Header value"
                          value={h.value}
                          onChange={(e) => updateHeaderRow(i, "value", e.target.value)}
                        />
                      </span>
                      <span className="pm-col-action">
                        <button className="pm-row-del" onClick={() => removeHeaderRow(i)}>✕</button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Body Editor */}
            {activeTab === "body" && (
              <div className="pm-pane">
                <div className="pm-pane-header">
                  <span>JSON Request Body</span>
                  <button className="pm-text-btn" onClick={prettifyJson}>Prettify JSON</button>
                </div>
                <textarea
                  className="pm-body-editor"
                  rows={10}
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  placeholder='{\n  "key": "value"\n}'
                  aria-label="JSON request body"
                />
              </div>
            )}

            {/* Response Viewer */}
            {activeTab === "response" && (
              <div className="pm-pane">
                {sending ? (
                  <div className="pm-response-loading">
                    <span className="spinner" aria-hidden="true" /> Sending request to {url}…
                  </div>
                ) : response ? (
                  <div className="pm-response-container fade-in">
                    {/* Status bar */}
                    <div className="pm-response-status-bar">
                      <div className="pm-status-badge-row">
                        <span className={`pm-status-tag status-${statusColor(response.status_code)}`}>
                          {response.status_code ? `${response.status_code} ${statusText(response.status_code)}` : "Connection Failed"}
                        </span>
                        <span className="pm-stat-item">Time: <strong>{response.elapsed_ms} ms</strong></span>
                      </div>
                      <div className="pm-view-toggle">
                        <button
                          className={`pm-view-btn ${responseView === "pretty" ? "active" : ""}`}
                          onClick={() => setResponseView("pretty")}
                        >
                          Pretty
                        </button>
                        <button
                          className={`pm-view-btn ${responseView === "raw" ? "active" : ""}`}
                          onClick={() => setResponseView("raw")}
                        >
                          Raw
                        </button>
                      </div>
                    </div>

                    {/* Code display */}
                    <pre className="pm-response-code" tabIndex={0}>
                      {responseView === "pretty" && typeof response.data === "object"
                        ? JSON.stringify(response.data, null, 2)
                        : typeof response.data === "string"
                        ? response.data
                        : JSON.stringify(response.data || response.error, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <div className="pm-response-empty">
                    Hit <strong>Send</strong> to execute an HTTP request and inspect live API responses.
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

function statusText(code) {
  const map = {
    200: "OK", 201: "Created", 204: "No Content",
    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
    500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable",
  };
  return map[code] || "";
}
