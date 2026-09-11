/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
import test from "node:test";
import assert from "node:assert/strict";
import { mediaKind, contentUrl, formatTimestamp, chunkLabel } from "../../static/js/source.js";

test("media helper uses category and safe content endpoint", () => {
  assert.equal(mediaKind({ category: "pdf" }), "pdf");
  assert.equal(mediaKind({ original_name: "ghi-am.m4a" }), "audio");
  assert.equal(contentUrl("a/b"), "/api/documents/a%2Fb/content");
  assert.equal(contentUrl("a/b").includes("uploads"), false);
});

test("timestamp and chunk labels expose source context", () => {
  assert.equal(formatTimestamp(65.9), "1:05");
  assert.equal(formatTimestamp(3661), "1:01:01");
  assert.equal(chunkLabel({ position: 2, page: 4, scene: 1, timestamp: 65 }), "Đoạn 3 · Trang 4 · Cảnh 1 · 1:05");
});
