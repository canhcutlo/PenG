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
