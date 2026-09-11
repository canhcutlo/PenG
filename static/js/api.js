/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
function cookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const value = document.cookie.split("; ").find((item) => item.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}
export class ApiError extends Error {
  constructor(message, status, payload) { super(message); this.name = "ApiError"; this.status = status; this.payload = payload; }
}
export async function apiFetch(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = cookie("peng_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(path, { ...options, method, headers, credentials: "include" });
  if (!response.ok) {
    let payload = null;
    try { payload = await response.json(); } catch { payload = null; }
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : response.statusText || "Yêu cầu thất bại";
    if (response.status === 401) window.dispatchEvent(new CustomEvent("peng:auth-expired"));
    throw new ApiError(message, response.status, payload);
  }
  if (response.status === 204) return null;
  const type = response.headers.get("content-type") || "";
  return type.includes("json") ? response.json() : response;
}
export const api = {
  me: () => apiFetch("/api/auth/me"),
  login: (body) => apiFetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  register: (body) => apiFetch("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  logout: () => apiFetch("/api/auth/logout", { method: "POST" }),
  health: () => apiFetch("/api/health"),
  documents: () => apiFetch("/api/documents?limit=100"),
  upload: (body) => apiFetch("/api/upload", { method: "POST", body }),
  job: (id) => apiFetch(`/api/jobs/${encodeURIComponent(id)}`),
  sessions: () => apiFetch("/api/chat/sessions?limit=50"),
  createSession: (docId) => apiFetch("/api/chat/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ doc_id: docId }) }),
  session: (id) => apiFetch(`/api/chat/${encodeURIComponent(id)}`),
  send: (id, content) => apiFetch(`/api/chat/${encodeURIComponent(id)}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content, mode: "document_and_related" }) }),
  source: (docId, limit = 100, offset = 0, locator = null) => {
    const params = new URLSearchParams({ limit, offset });
    if (locator?.chunkId) params.set("chunk_id", locator.chunkId);
    else if (locator?.page != null) params.set("page", locator.page);
    else if (locator?.scene != null) params.set("scene", locator.scene);
    else if (locator?.timestamp != null) params.set("timestamp", locator.timestamp);
    return apiFetch(`/api/documents/${encodeURIComponent(docId)}/source?${params}`);
  },
  chunk: (docId, chunkId) => apiFetch(`/api/documents/${encodeURIComponent(docId)}/source/chunks/${encodeURIComponent(chunkId)}`),
  artifacts: (docId) => apiFetch(`/api/documents/${encodeURIComponent(docId)}/artifacts`),
  summary: (docId) => apiFetch(`/api/documents/${encodeURIComponent(docId)}/summary`),
  regenerate: (docId, type) => apiFetch(`/api/documents/${encodeURIComponent(docId)}/artifacts/regenerate?artifact_type=${encodeURIComponent(type)}`, { method: "POST" }),
  mindmap: (docId) => apiFetch(`/api/mindmap/${encodeURIComponent(docId)}`),
  quizzes: (docId) => apiFetch(`/api/documents/${encodeURIComponent(docId)}/quizzes?limit=100`),
  quiz: (id) => apiFetch(`/api/quiz/${encodeURIComponent(id)}`),
  attempts: (id) => apiFetch(`/api/quiz/${encodeURIComponent(id)}/attempts?limit=100`),
  generateQuiz: (docId, count) => apiFetch(`/api/quiz/generate?doc_id=${encodeURIComponent(docId)}&num_questions=${count}`, { method: "POST" }),
  submitQuiz: (id, answers) => apiFetch(`/api/quiz/${encodeURIComponent(id)}/submit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ quiz_id: id, answers }) }),
  knowledge: (docId) => apiFetch(`/api/knowledge/nodes/${encodeURIComponent(docId)}`),
  related: (docId) => apiFetch(`/api/knowledge/related/${encodeURIComponent(docId)}`),
  history: () => apiFetch("/api/history?limit=100")
};
