/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
export function mediaKind(document) {
  const category = String(document?.category || "").toLowerCase();
  if (["pdf", "image", "audio", "video"].includes(category)) return category;
  const extension = String(document?.original_name || document?.filename || "").split(".").pop().toLowerCase();
  if (extension === "pdf") return "pdf";
  if (["png", "jpg", "jpeg", "gif", "webp", "bmp"].includes(extension)) return "image";
  if (["mp3", "wav", "ogg", "m4a", "flac"].includes(extension)) return "audio";
  if (["mp4", "webm", "mov", "mkv", "avi"].includes(extension)) return "video";
  return "unknown";
}
export function contentUrl(docId) { return `/api/documents/${encodeURIComponent(docId)}/content`; }
export function formatTimestamp(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = Math.floor(seconds % 60);
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}` : `${minutes}:${String(rest).padStart(2, "0")}`;
}
export function chunkLabel(chunk) {
  const parts = [`Đoạn ${Number(chunk?.position || 0) + 1}`];
  if (chunk?.page != null) parts.push(`Trang ${chunk.page}`);
  if (chunk?.scene != null) parts.push(`Cảnh ${chunk.scene}`);
  const time = formatTimestamp(chunk?.timestamp);
  if (time) parts.push(time);
  return parts.join(" · ");
}
