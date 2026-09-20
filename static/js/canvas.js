/*
 * Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
 * SPDX-License-Identifier: MIT
 */
import { api } from "./api.js";
import { $, clear, h, emptyState, loadingState, errorState, setBusy } from "./dom.js";
import { contentUrl, mediaKind, chunkLabel } from "./source.js";
import { parsePersisted } from "./state.js";

const actionLabels = { uploaded: "Đã tải lên", viewed: "Đã xem", quizzed: "Đã làm quiz", mindmapped: "Đã mở sơ đồ", summary_generated: "Đã tạo tóm tắt", mindmap_generated: "Đã tạo sơ đồ", artifact_failed: "Tạo nội dung thất bại" };
export function downloadText(name, content, type = "text/markdown;charset=utf-8") {
  const href = URL.createObjectURL(new Blob([content || ""], { type }));
  const link = h("a", { href, download: name });
  document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(href);
}
function toolbar(...items) { return h("div", { className: "toolbar" }, ...items); }
function docFor(state, id) { return state.documents.find((doc) => doc.doc_id === id); }
function documentRequired(panel) { clear(panel).append(errorState("Chọn một tài liệu để mở nội dung này.")); }
function mediaPreview(doc) {
  const url = contentUrl(doc.doc_id); const kind = mediaKind(doc);
  if (kind === "pdf") return h("iframe", { className: "source-media", src: url, title: `Bản gốc ${doc.original_name || doc.filename}` });
  if (kind === "image") return h("img", { className: "source-media image", src: url, alt: `Nội dung gốc của ${doc.original_name || doc.filename}` });
  if (kind === "audio") return h("audio", { className: "source-media audio", src: url, controls: true, preload: "metadata" });
  if (kind === "video") return h("video", { className: "source-media", src: url, controls: true, preload: "metadata" });
  return null;
}
export async function renderSource(panel, state, locator = null) {
  const docId = state.canvasTargetDocumentId || state.selectedDocumentId;
  if (!docId) return documentRequired(panel);
  clear(panel).append(loadingState("Đang tải nội dung nguồn…"));
  try {
    const [data, exact] = await Promise.all([api.source(docId, 100, 0, locator), locator?.chunkId ? api.chunk(docId, locator.chunkId).catch(() => null) : null]);
    const doc = docFor(state, docId) || { doc_id: docId };
    clear(panel);
    const preview = mediaPreview(doc); if (preview) panel.append(preview);
    panel.append(h("div", { className: "row-between" }, h("h3", {}, `Nội dung trích xuất (${data.total})`), h("a", { className: "button secondary", href: contentUrl(docId), target: "_blank", rel: "noopener" }, "Mở bản gốc")));
    const chunks = h("div", { className: "chunk-list" });
    const locatedChunk = exact || findLocatedChunk(data.chunks || [], locator);
    for (const chunk of data.chunks || []) chunks.append(chunkNode(chunk, locatedChunk?.chunk_id === chunk.chunk_id));
    if (exact && !(data.chunks || []).some((item) => item.chunk_id === exact.chunk_id)) chunks.prepend(chunkNode(exact, true));
    panel.append(chunks.children.length ? chunks : emptyState("Chưa có đoạn nội dung trích xuất."));
    const focused = panel.querySelector(".chunk.focused");
    requestAnimationFrame(() => { focused?.scrollIntoView({ block: "center" }); focused?.focus({ preventScroll: true }); });
    const media = panel.querySelector("audio, video");
    if (media && locator?.timestamp != null) media.addEventListener("loadedmetadata", () => { media.currentTime = Number(locator.timestamp); }, { once: true });
  } catch (error) { clear(panel).append(errorState(`Không tải được nguồn: ${error.message}`)); }
}
function findLocatedChunk(chunks, locator) {
  if (!locator) return null;
  if (locator.page != null) return chunks.find((chunk) => chunk.page === locator.page) || null;
  if (locator.scene != null) return chunks.find((chunk) => chunk.scene === locator.scene) || null;
  if (locator.timestamp != null) return chunks.filter((chunk) => chunk.timestamp != null).sort((a, b) => Math.abs(a.timestamp - locator.timestamp) - Math.abs(b.timestamp - locator.timestamp))[0] || null;
  return null;
}
function chunkNode(chunk, focused) {
  return h("article", { className: `chunk${focused ? " focused" : ""}`, id: `chunk-${chunk.chunk_id}`, tabindex: focused ? "-1" : null }, h("p", { className: "meta" }, chunkLabel(chunk)), h("div", { className: "markdown" }, chunk.text || ""));
}
export async function renderSummary(panel, state) {
  const docId = state.canvasTargetDocumentId || state.selectedDocumentId; if (!docId) return documentRequired(panel);
  clear(panel).append(loadingState("Đang tải tóm tắt…"));
  try {
    const [latest, artifacts] = await Promise.all([api.summary(docId).catch(() => null), api.artifacts(docId)]);
    clear(panel);
    const regenerate = h("button", { className: "button secondary", type: "button" }, "Tạo lại tóm tắt");
    regenerate.addEventListener("click", async () => { setBusy(regenerate, true, "Đang tạo…"); try { await api.regenerate(docId, "summary"); await renderSummary(panel, state); } catch (error) { panel.prepend(errorState(error.message)); } finally { setBusy(regenerate, false); } });
    panel.append(toolbar(regenerate, latest?.content ? h("button", { className: "button secondary", type: "button", onclick: () => downloadText(`${docId}-tom-tat.md`, latest.content) }, "Tải Markdown") : null));
    panel.append(latest?.content ? h("article", { className: "markdown" }, latest.content) : emptyState("Chưa có bản tóm tắt hoàn tất."));
    const list = h("div", { className: "artifact-list" }, h("h3", {}, "Các phiên bản"));
    for (const item of artifacts.filter((artifact) => artifact.type === "summary")) list.append(h("div", { className: "row row-between" }, h("span", {}, `Phiên bản ${item.version} · ${item.status}`), item.content ? h("button", { className: "mini-button", type: "button", onclick: () => downloadText(`${docId}-tom-tat-v${item.version}.md`, item.content) }, "Tải") : null));
    panel.append(list);
  } catch (error) { clear(panel).append(errorState(`Không tải được tóm tắt: ${error.message}`)); }
}
function validateMindmapMarkdown(markdown) {
  const text = String(markdown || "").trim();
  return text.length > 0 && text.includes("#");
}
let markmapCssInjected = false;
async function markmapRender(container, markdown) {
  try {
    if (!markdown || !String(markdown).trim()) return { ok: false, stage: "structure" };
    const [{ Transformer }, { Markmap, globalCSS, loadCSS, loadJS }] = await Promise.all([
      import("https://cdn.jsdelivr.net/npm/markmap-lib@0.18.12/+esm"),
      import("https://cdn.jsdelivr.net/npm/markmap-view@0.18.12/+esm")
    ]);

    if (!markmapCssInjected && globalCSS) {
      const style = document.createElement("style");
      style.id = "markmap-global-css";
      style.textContent = `${globalCSS}\n.markmap { width: 100%; height: 100%; min-height: 28rem; display: block; }`;
      document.head.append(style);
      markmapCssInjected = true;
    }

    const transformer = new Transformer();
    const { root } = transformer.transform(markdown);
    if (!root) return { ok: false, stage: "structure" };

    const { styles, scripts } = transformer.getAssets();
    if (styles && loadCSS) loadCSS(styles);
    if (scripts && loadJS) loadJS(scripts);

    clear(container);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "markmap");
    svg.setAttribute("style", "width: 100%; height: 100%; min-height: 28rem; display: block;");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Sơ đồ tư duy của tài liệu");
    container.append(svg);

    const mindmap = Markmap.create(svg, { autoFit: true }, root);
    requestAnimationFrame(() => mindmap.fit());
    const observer = new ResizeObserver(() => mindmap.fit());
    observer.observe(container);
    return { ok: true, observer, mindmap };
  } catch (error) {
    console.error("[mindmap] render failed", error);
    return { ok: false, stage: "module-or-render", error };
  }
}
export async function renderMindmap(panel, state) {
  const docId = state.canvasTargetDocumentId || state.selectedDocumentId; if (!docId) return documentRequired(panel);
  clear(panel).append(loadingState("Đang tải sơ đồ tư duy…"));
  try {
    const [data, artifacts] = await Promise.all([api.mindmap(docId), api.artifacts(docId)]); clear(panel);
    const regenerate = h("button", { className: "button secondary", type: "button" }, "Tạo lại sơ đồ");
    regenerate.addEventListener("click", async () => { setBusy(regenerate, true, "Đang tạo…"); try { const artifact = await api.regenerate(docId, "mindmap"); if (artifact.status !== "completed") throw new Error(artifact.error_message || "Tạo mindmap thất bại"); await renderMindmap(panel, state); } catch (error) { panel.prepend(errorState(error.message)); } finally { setBusy(regenerate, false); } });
    panel.append(toolbar(regenerate, h("button", { className: "button secondary", type: "button", onclick: () => downloadText(`${docId}-so-do.md`, data.markdown) }, "Tải Markdown")));
    const frame = h("div", { className: "mindmap-frame" }); panel.append(frame);
    const rendered = await markmapRender(frame, data.markdown);
    if (!rendered.ok) {
      const message = rendered.stage === "structure" ? "Mindmap chưa có cấu trúc phân nhánh hợp lệ." : "Không tải được trình vẽ Markmap. Kiểm tra kết nối mạng hoặc thử lại.";
      clear(frame).append(h("pre", { className: "markdown" }, data.markdown), h("p", { className: "status-text" }, message));
    }
    const versions = artifacts.filter((item) => item.type === "mindmap"); if (versions.length) panel.append(h("p", { className: "status-text" }, `${versions.length} phiên bản đã lưu.`));
  } catch (error) { clear(panel).append(errorState(`Không tải được sơ đồ: ${error.message}`)); }
}
export async function renderQuiz(panel, state) {
  const docId = state.canvasTargetDocumentId || state.selectedDocumentId; if (!docId) return documentRequired(panel);
  clear(panel).append(loadingState("Đang tìm quiz đã lưu…"));
  try {
    const data = await api.quizzes(docId); clear(panel);
    const count = h("select", { "aria-label": "Số câu hỏi" }, ...[3, 5, 10].map((value) => h("option", { value, selected: value === 3 }, `${value} câu`)));
    const generate = h("button", { className: "button primary", type: "button" }, "Tạo quiz mới");
    generate.addEventListener("click", async () => { setBusy(generate, true, "Đang tạo quiz…"); try { const quiz = await api.generateQuiz(docId, Number(count.value)); await openQuiz(panel, quiz); } catch (error) { panel.prepend(errorState(error.message)); } finally { setBusy(generate, false); } });
    panel.append(h("div", { className: "toolbar quiz-toolbar" }, count, generate));
    const list = h("div", { className: "quiz-list" });
    for (const quiz of data.quizzes || []) {
      const score = quiz.latest_score == null ? "Chưa làm" : `Gần nhất ${quiz.latest_score}/${quiz.question_count}`;
      list.append(h("div", { className: "row row-between" }, h("div", {}, h("strong", {}, `${quiz.question_count} câu`), h("div", { className: "status-text" }, `${score} · ${quiz.attempt_count} lượt làm`)), h("button", { className: "button secondary", type: "button", onclick: async () => openQuiz(panel, await api.quiz(quiz.quiz_id)) }, "Mở quiz")));
    }
    panel.append(list.children.length ? list : emptyState("Chưa có quiz cho tài liệu này."));
  } catch (error) { clear(panel).append(errorState(`Không tải được quiz: ${error.message}`)); }
}
async function openQuiz(panel, quiz) {
  clear(panel); const form = h("form", { className: "quiz-form" });
  form.append(h("div", { className: "quiz-header" }, h("h3", {}, `Quiz · ${quiz.questions.length} câu`), h("button", { className: "button secondary quiz-back", type: "button", onclick: () => renderQuiz(panel, { selectedDocumentId: quiz.doc_id, canvasTargetDocumentId: quiz.doc_id }) }, "Quay lại")));
  quiz.questions.forEach((question, index) => {
    const field = h("fieldset", { className: "quiz-question" }, h("legend", {}, `Câu ${index + 1}. ${question.question}`));
    question.options.forEach((option, optionIndex) => field.append(h("label", { className: "quiz-option" }, h("input", { type: "radio", name: `question-${index}`, value: optionIndex, required: true }), h("span", {}, option)))); form.append(field);
  });
  const result = h("div", { role: "status" }); const submit = h("button", { className: "button primary", type: "submit" }, "Nộp bài"); form.append(submit, result);
  form.addEventListener("submit", async (event) => { event.preventDefault(); const answers = quiz.questions.map((_, index) => Number(new FormData(form).get(`question-${index}`))); if (answers.some(Number.isNaN)) return; setBusy(submit, true, "Đang chấm bài…"); try { const scored = await api.submitQuiz(quiz.quiz_id, answers); clear(result).append(h("p", { className: "score" }, `Kết quả: ${scored.score}/${scored.total} câu đúng.`)); quiz.questions.forEach((question, index) => { const labels = form.querySelectorAll(`input[name="question-${index}"]`); labels.forEach((input) => {
        const label = input.closest("label");
        const className = Number(input.value) === question.correct_index ? "correct" : Number(input.value) === answers[index] ? "incorrect" : null;
        if (className) label.classList.add(className);
      }); }); const attempts = await api.attempts(quiz.quiz_id); result.append(h("p", { className: "status-text" }, `Đã lưu ${attempts.total} lượt làm.`)); } catch (error) { clear(result).append(errorState(error.message)); } finally { setBusy(submit, false); } });
  panel.append(form);
}
export async function renderKnowledge(panel, state) {
  const docId = state.canvasTargetDocumentId || state.selectedDocumentId; if (!docId) return documentRequired(panel);
  clear(panel).append(loadingState("Đang tải dữ liệu tri thức…"));
  const [nodeResult, edgeResult] = await Promise.allSettled([api.knowledge(docId), api.related(docId)]); clear(panel);
  if (nodeResult.status === "fulfilled") {
    const node = nodeResult.value; panel.append(h("article", {}, h("h3", {}, node.title || "Tri thức tài liệu"), node.summary ? h("p", {}, node.summary) : null, h("p", { className: "status-text" }, `Trạng thái: ${node.status} · Ngôn ngữ: ${node.language || "không rõ"}`), metric("Tính nhất quán nội bộ", node.internal_consistency), metric("Độ phủ bằng chứng", node.evidence_coverage), metric("Chất lượng trích xuất", node.extraction_quality)));
  }
  if (edgeResult.status === "fulfilled") {
    const list = h("div", { className: "knowledge-list" }, h("h3", {}, "Liên kết tài liệu"));
    for (const edge of edgeResult.value.edges || []) {
      const doc = (state.documents || []).find((d) => d.doc_id === edge.target_doc_id);
      const displayTitle = edge.target_title || doc?.original_name || doc?.filename || edge.evidence?.target_title || edge.target_doc_id;
      list.append(h("div", { className: "row row-between" },
        h("div", {},
          h("strong", {}, displayTitle),
          edge.target_doc_id && edge.target_doc_id !== displayTitle ? h("div", { className: "status-text" }, `Mã: ${edge.target_doc_id}`) : null
        ),
        h("div", { className: "status-text" }, `${edge.relation_type} · ${Math.round(edge.similarity_score * 100)}% tương đồng`)
      ));
    }
    panel.append(list);
  }
  if (nodeResult.status === "rejected" && edgeResult.status === "rejected") panel.append(emptyState("Chưa có dữ liệu tri thức cho tài liệu này."));
}
function metric(label, value) { const percentage = Math.round(Number(value || 0) * 100); return h("div", { className: "metric" }, h("span", {}, label), h("strong", {}, `${percentage}%`), h("progress", { max: 100, value: percentage }, `${percentage}%`)); }
export async function renderHistory(container) {
  clear(container).append(loadingState("Đang tải lịch sử…")); try { const rows = await api.history(); clear(container); const list = h("div", { className: "history-list" }); for (const row of rows) list.append(h("div", { className: "row" }, h("strong", {}, row.original_name || row.doc_id), h("div", {}, actionLabels[row.action] || row.action), h("div", { className: "status-text" }, row.created_at ? new Date(row.created_at).toLocaleString("vi-VN") : ""))); container.append(list.children.length ? list : emptyState("Chưa có hoạt động nào.")); } catch (error) { clear(container).append(errorState(error.message)); }
}
export { parsePersisted };
