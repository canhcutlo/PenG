/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
import test from "node:test";
import assert from "node:assert/strict";
import { initialState, reducer, parsePersisted, loadPreferences, savePreference } from "../../static/js/state.js";

test("reducer keeps canonical document and canvas target aligned", () => {
  const state = reducer(initialState, { type: "selectDocument", id: "doc-1" });
  assert.equal(state.selectedDocumentId, "doc-1");
  assert.equal(state.canvasTargetDocumentId, "doc-1");
  assert.equal(state.sourceLocator, null);
});

test("reducer records exact source locator and jobs immutably", () => {
  const opened = reducer(initialState, { type: "openCanvas", canvas: "source", docId: "d", locator: { chunkId: "c" } });
  const jobbed = reducer(opened, { type: "setJob", job: { job_id: "j", progress: 40 } });
  assert.deepEqual(jobbed.sourceLocator, { chunkId: "c" });
  assert.equal(jobbed.jobs.j.progress, 40);
  assert.deepEqual(opened.jobs, {});
});

test("persisted JSON accepts arrays, strings and invalid values", () => {
  assert.deepEqual(parsePersisted([1]), [1]);
  assert.deepEqual(parsePersisted('[{"id":1}]'), [{ id: 1 }]);
  assert.deepEqual(parsePersisted("not-json"), []);
});

test("preferences only use supplied local storage adapter", () => {
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
  assert.equal(savePreference("canvas-open", true, storage), true);
  assert.deepEqual(loadPreferences(storage), { canvasOpen: true });
});
