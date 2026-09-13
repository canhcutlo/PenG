/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
export function clear(node) { node.replaceChildren(); return node; }
const SVG_TAGS = new Set(["svg", "g", "path", "circle", "rect", "line", "polyline", "polygon", "text", "tspan", "foreignObject"]);
export function h(tag, attributes = {}, ...children) {
  const node = SVG_TAGS.has(tag.toLowerCase())
    ? document.createElementNS("http://www.w3.org/2000/svg", tag)
    : document.createElement(tag);
  for (const [name, value] of Object.entries(attributes || {})) {
    if (value == null || value === false) continue;
    if (name === "className") node.className = value;
    else if (name === "dataset") Object.assign(node.dataset, value);
    else if (name === "checked" || name === "disabled" || name === "hidden") node[name] = Boolean(value);
    else if (name.startsWith("on") && typeof value === "function") node.addEventListener(name.slice(2).toLowerCase(), value);
    else node.setAttribute(name, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
export function setBusy(button, busy, label) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
  button.textContent = busy ? label : button.dataset.label;
}
export function emptyState(message) { return h("div", { className: "empty-panel" }, message); }
export function loadingState(message) { return h("div", { className: "loading-panel", role: "status" }, message); }
export function errorState(message) { return h("div", { className: "error-panel", role: "alert" }, message); }
