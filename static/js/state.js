/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
export const CANVASES = ["source", "summary", "mindmap", "quiz", "knowledge"];
export const initialState = Object.freeze({
  selectedDocumentId: null,
  activeSessionId: null,
  activeCanvas: "source",
  canvasTargetDocumentId: null,
  sourceLocator: null,
  jobs: {},
  documents: [],
  sessions: [],
  user: null
});
export function reducer(state, action) {
  switch (action.type) {
    case "bootstrap": return { ...state, ...action.payload };
    case "selectDocument": return { ...state, selectedDocumentId: action.id, canvasTargetDocumentId: action.id, sourceLocator: null };
    case "selectSession": return { ...state, activeSessionId: action.id, selectedDocumentId: action.docId || state.selectedDocumentId, canvasTargetDocumentId: action.docId || state.canvasTargetDocumentId };
    case "openCanvas": return { ...state, activeCanvas: CANVASES.includes(action.canvas) ? action.canvas : "source", canvasTargetDocumentId: action.docId || state.selectedDocumentId, sourceLocator: action.locator || null };
    case "setJob": return { ...state, jobs: { ...state.jobs, [action.job.job_id]: action.job } };
    case "removeJob": { const jobs = { ...state.jobs }; delete jobs[action.id]; return { ...state, jobs }; }
    case "reset": return { ...initialState };
    default: return state;
  }
}
export function createStore(seed = initialState) {
  let state = { ...seed };
  const listeners = new Set();
  return {
    getState: () => state,
    dispatch(action) { state = reducer(state, action); listeners.forEach((listener) => listener(state, action)); return state; },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
  };
}
export function parsePersisted(value, fallback = []) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return value;
  if (typeof value !== "string") return fallback;
  try { const parsed = JSON.parse(value); return parsed ?? fallback; } catch { return fallback; }
}
export function loadPreferences(storage = localStorage) {
  try { return { canvasOpen: storage.getItem("peng:canvas-open") === "true" }; } catch { return { canvasOpen: false }; }
}
export function savePreference(key, value, storage = localStorage) {
  try { storage.setItem(`peng:${key}`, String(value)); } catch { return false; }
  return true;
}
