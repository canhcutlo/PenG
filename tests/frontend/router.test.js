/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readRoute, routeSearch } from "../../static/js/router.js";

test("route parser restores deep-link workspace state", () => {
  assert.deepEqual(readRoute("?doc=d1&session=s1&canvas=quiz&canvasDoc=d2&chunk=c9"), {
    selectedDocumentId: "d1",
    activeSessionId: "s1",
    activeCanvas: "quiz",
    canvasTargetDocumentId: "d2",
    sourceLocator: { chunkId: "c9" }
  });
});

test("route serializer omits defaults and preserves source focus", () => {
  const search = routeSearch({ selectedDocumentId: "d1", activeSessionId: null, activeCanvas: "source", canvasTargetDocumentId: "d1", sourceLocator: { chunkId: "c1" } });
  assert.equal(search, "?doc=d1&chunk=c1");
});

test("source locators round-trip with priority", () => {
  assert.deepEqual(readRoute("?page=4").sourceLocator, { page: 4 });
  assert.deepEqual(readRoute("?scene=3").sourceLocator, { scene: 3 });
  assert.deepEqual(readRoute("?t=84.2").sourceLocator, { timestamp: 84.2 });
  assert.equal(routeSearch({ activeCanvas: "source", sourceLocator: { timestamp: 84.2 } }), "?t=84.2");
});

test("unknown canvas falls back to source", () => {
  assert.equal(readRoute("?canvas=unsafe").activeCanvas, "source");
});
