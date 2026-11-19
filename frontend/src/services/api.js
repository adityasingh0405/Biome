/**
 * Biome RAG API Client Service
 *
 * Phase 7 — All mock/fallback responses removed.
 * Every function propagates real errors so the UI can display them.
 *
 * Base URL: controlled by the VITE_API_BASE_URL env variable.
 * During Vite dev-server the proxy at /v1 → http://127.0.0.1:8000 is used
 * (see vite.config.js), so API_BASE is empty by default.
 * For production / Docker deployments, set VITE_API_BASE_URL in frontend/.env.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

/** Default request timeout in milliseconds */
const DEFAULT_TIMEOUT_MS = 180_000;

/**
 * Thin wrapper around fetch with:
 *   - Abort-controller based timeout
 *   - Uniform JSON error extraction (FastAPI returns { detail: "..." })
 *
 * @param {string} url
 * @param {RequestInit} options
 * @param {number} [timeoutMs]
 * @returns {Promise<any>} Parsed JSON body
 */
async function apiFetch(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, { ...options, signal: controller.signal });

    if (!res.ok) {
      // Try to surface the FastAPI error detail
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        detail = body?.detail ?? detail;
      } catch {
        /* ignore JSON parse failure on error body */
      }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }

    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function fetchHealth() {
  return apiFetch(`${API_BASE}/v1/health`);
}

// ---------------------------------------------------------------------------
// Query endpoints
// ---------------------------------------------------------------------------

/**
 * POST /v1/ask
 *
 * @param {string} question
 * @param {string} [mode="hybrid"]  retrieval_mode
 * @param {string[]|null} [scope]   access_scope — required for structured queries
 * @param {string|null} [routeOverride]  "auto" | "structured" | "semantic"
 */
export async function askQuestion(question, mode = 'hybrid', scope = null, routeOverride = null) {
  const payload = {
    question,
    retrieval_mode: mode,
    access_scope: scope && scope.length > 0 ? scope : null,
    route_override: routeOverride || null,
  };
  return apiFetch(`${API_BASE}/v1/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/**
 * POST /v1/chat
 *
 * @param {string} message
 * @param {string} sessionId   Required — UUID generated client-side
 * @param {string} [mode="hybrid"]
 * @param {string[]|null} [scope]
 * @param {string|null} [routeOverride]
 */
export async function sendChatMessage(message, sessionId, mode = 'hybrid', scope = null, routeOverride = null) {
  const payload = {
    message,
    session_id: sessionId,
    retrieval_mode: mode,
    access_scope: scope && scope.length > 0 ? scope : null,
    route_override: routeOverride || null,
  };
  return apiFetch(`${API_BASE}/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/**
 * POST /v1/compare
 *
 * @param {string} question
 */
export async function compareRetrieval(question) {
  return apiFetch(`${API_BASE}/v1/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
}

// ---------------------------------------------------------------------------
// Document / index management
// ---------------------------------------------------------------------------

export async function fetchDocuments() {
  return apiFetch(`${API_BASE}/v1/documents`);
}

/**
 * POST /v1/index/upload  — preferred ingest path (runs full Phase 1→2→3)
 *
 * @param {File[]} files
 */
export async function uploadFiles(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  return apiFetch(
    `${API_BASE}/v1/index/upload`,
    { method: 'POST', body: formData },
    300_000, // 5-minute timeout for large uploads
  );
}

/**
 * POST /v1/ingest/directory
 * NOTE: directory_path is validated server-side against INGEST_BASE_DIR.
 *
 * @param {string} directoryPath
 * @param {boolean} [recursive=true]
 */
export async function ingestDirectory(directoryPath, recursive = true) {
  return apiFetch(`${API_BASE}/v1/ingest/directory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ directory_path: directoryPath, recursive }),
  });
}

/**
 * POST /v1/ingest/text
 *
 * @param {string} title
 * @param {string} content
 */
export async function ingestText(title, content) {
  return apiFetch(`${API_BASE}/v1/ingest/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content }),
  });
}

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

/**
 * DELETE /v1/session/{sessionId}
 *
 * @param {string} sessionId
 */
export async function clearSession(sessionId) {
  return apiFetch(`${API_BASE}/v1/session/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  });
}
