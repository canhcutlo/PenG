"""Prompt templates for answer, summary, mindmap, and quiz generation.

Each prompt includes: input format, output requirements, and constraints.
"""


ANSWER_SYSTEM = (
    "Bạn là trợ lý học tập. Trả lời dựa trên context được cung cấp. "
    "Nếu context không đủ thông tin, hãy trả lời: 'Không đủ dữ liệu trong tài liệu.' "
    "Luôn trích dẫn nguồn (trang/cảnh/thời gian) khi có."
)

ANSWER_PROMPT = """Context:
{context}

Câu hỏi: {question}

Trả lời ngắn gọn, chính xác, có trích dẫn nguồn. Nếu không đủ dữ liệu, nói rõ."""


def build_answer_prompt(question: str, context: str) -> str:
    return ANSWER_PROMPT.format(question=question, context=context)



SUMMARY_PROMPT = """Tóm tắt tài liệu sau thành các ý chính dạng bullet points.
- Mỗi bullet tối đa 15 từ.
- Tối đa 8 bullets.
- Dùng tiếng Việt nếu văn bản tiếng Việt.

Text:
{text}

Output (chỉ bullets, không giải thích):"""


def build_summary_prompt(text: str) -> str:
    return SUMMARY_PROMPT.format(text=text[:6000])



MINDMAP_PROMPT = """Chuyển nội dung sau thành mindmap dạng Markdown:
- Dòng đầu: `# <chủ đề chính>` (1 dòng)
- Mỗi nhánh chính: `## <nhánh>` (3-7 nhánh)
- Mỗi chi tiết: `- <ý>` (2-5 ý mỗi nhánh)
- Không dùng code fence, không thêm ghi chú ngoài cấu trúc.
- Dùng tiếng Việt nếu văn bản tiếng Việt.

Text:
{text}"""


def build_mindmap_prompt(text: str) -> str:
    return MINDMAP_PROMPT.format(text=text[:6000])



QUIZ_SYSTEM = (
    "Bạn là chuyên gia tạo câu hỏi trắc nghiệm. Tạo câu hỏi rõ ràng, "
    "4 lựa chọn, duy nhất một đáp án đúng, có giải thích. Dùng tiếng Việt "
    "nếu văn bản tiếng Việt. Chỉ trả về JSON."
)

QUIZ_JSON_SCHEMA = """{
  "questions": [
    {
      "question": "string",
      "options": ["A", "B", "C", "D"],
      "correct_index": 0,
      "explanation": "string"
    }
  ]
}"""

QUIZ_PROMPT = """Tạo {num} câu hỏi trắc nghiệm từ nội dung sau.

Yêu cầu:
- Mỗi câu có đúng 4 lựa chọn.
- correct_index là chỉ số (0-3) của đáp án đúng.
- Mỗi câu có explanation giải thích ngắn.
- Không có đáp án trùng lặp, không mơ hồ.

Chỉ trả về JSON đúng schema:
{json_schema}

Text:
{text}"""


def build_quiz_prompt(text: str, num_questions: int = 5) -> str:
    return QUIZ_PROMPT.format(text=text[:4000], num=num_questions, json_schema=QUIZ_JSON_SCHEMA)


FAITHFUL_ANSWER_PROMPT_VERSION = "faithful_answer_v1"
FAITHFUL_CHAT_PROMPT_VERSION = "faithful_chat_v1"

FAITHFUL_ANSWER_SYSTEM = (
    "You are a careful evidence-based assistant. "
    "Respond with ONLY valid JSON matching the provided schema. "
    "Use ONLY the evidence supplied in the prompt. "
    "Do not invent evidence, citations, or page numbers. "
    "Set polarity to 'yes' only when the evidence clearly supports an affirmative answer. "
    "Set polarity to 'no' only when the evidence clearly supports a negative answer. "
    "Set polarity to 'unknown' when the evidence is insufficient or irrelevant. "
    "If evidence contains a restrictive eligibility phrase (e.g., 'only students', 'chỉ sinh viên') "
    "and the question asks about outsiders/non-members, answer 'no' or 'unknown', never 'yes'."
)

FAITHFUL_ANSWER_PROMPT = """Use ONLY the evidence below to answer the question.

Evidence:
{context}

Question: {question}

{history}

Respond with JSON matching this schema:
{{
  "answer": "your concise answer in the same language as the question",
  "polarity": "yes|no|unknown",
  "evidence_ids": ["E1", ...],
  "warnings": []
}}

Rules:
- evidence_ids must reference ONLY the evidence IDs listed above.
- Do not fabricate evidence IDs.
- If the evidence does not fully answer the question, say so and set polarity to 'unknown'."""


def build_faithful_answer_prompt(question: str, context: str, history: str = "") -> str:
    return FAITHFUL_ANSWER_PROMPT.format(
        question=question, context=context, history=history or ""
    )


FAITHFUL_CHAT_PROMPT = """You are in a chat about uploaded learning materials. Use ONLY the evidence below.

Conversation history:
{history}

Evidence:
{context}

User question: {question}

Respond with JSON matching this schema:
{{
  "answer": "your concise answer in the same language as the question",
  "polarity": "yes|no|unknown",
  "evidence_ids": ["E1", ...],
  "warnings": []
}}

Rules:
- evidence_ids must reference ONLY the evidence IDs listed above.
- Do not fabricate evidence IDs.
- If the evidence does not fully answer the question, say so and set polarity to 'unknown'."""


def build_faithful_chat_prompt(question: str, context: str, history: str = "") -> str:
    return FAITHFUL_CHAT_PROMPT.format(
        question=question, context=context, history=history or ""
    )


CHAT_PROMPT_VERSION = "chat_v1"

CHAT_SYSTEM = (
    "Bạn là trợ lý học tập. Chỉ trả lờI dựa trên bằng chứng được cung cấp. "
    "Nếu thiếu bằng chứng, hãy nói rõ: 'Không tìm thấy đủ bằng chứng trong các tài liệu đã tải lên.' "
    "Nếu có mâu thuẫn, trình bày cả hai nguồn và không tự chọn bên đúng. "
    "Không thay đổi, bịa đặt, hoặc làm ảnh hưởng đến summary, quiz hay mindmap đã lưu. "
    "Trích dẫn nguồn bằng [doc_id] và trang/cảnh/thờI gian nếu có."
)

CHAT_PROMPT = """Lịch sử trò chuyện:
{history}

Bằng chứng từ tài liệu:
{context}

Câu hỏi: {question}

Trả lờI ngắn gọn, dựa trên bằng chứng, có trích dẫn nguồn. Nếu không đủ bằng chứng, nói rõ."""


def build_chat_prompt(question: str, context: str, history: str = "") -> str:
    return CHAT_PROMPT.format(question=question, context=context, history=history)
