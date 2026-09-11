/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
import { CANVASES } from "./state.js";
function sourceLocator(params) {
  if (params.get("chunk")) return { chunkId: params.get("chunk") };
  if (params.has("page")) return { page: Number(params.get("page")) };
  if (params.has("scene")) return { scene: Number(params.get("scene")) };
  if (params.has("t")) return { timestamp: Number(params.get("t")) };
  return null;
}
export function readRoute(search = location.search) {
  const params = new URLSearchParams(search);
  const canvas = params.get("canvas");
  return {
    selectedDocumentId: params.get("doc") || null,
    activeSessionId: params.get("session") || null,
    activeCanvas: CANVASES.includes(canvas) ? canvas : "source",
    canvasTargetDocumentId: params.get("canvasDoc") || params.get("doc") || null,
    sourceLocator: sourceLocator(params)
  };
}
export function routeSearch(state) {
  const params = new URLSearchParams();
  if (state.selectedDocumentId) params.set("doc", state.selectedDocumentId);
  if (state.activeSessionId) params.set("session", state.activeSessionId);
  if (state.activeCanvas && state.activeCanvas !== "source") params.set("canvas", state.activeCanvas);
  if (state.canvasTargetDocumentId && state.canvasTargetDocumentId !== state.selectedDocumentId) params.set("canvasDoc", state.canvasTargetDocumentId);
  if (state.sourceLocator?.chunkId) params.set("chunk", state.sourceLocator.chunkId);
  else if (state.sourceLocator?.page != null) params.set("page", state.sourceLocator.page);
  else if (state.sourceLocator?.scene != null) params.set("scene", state.sourceLocator.scene);
  else if (state.sourceLocator?.timestamp != null) params.set("t", state.sourceLocator.timestamp);
  const value = params.toString();
  return value ? `?${value}` : location.pathname;
}
export function writeRoute(state, mode = "replace") {
  const url = routeSearch(state);
  history[mode === "push" ? "pushState" : "replaceState"]({}, "", url);
}
