"""LLM integration: load Qwen/Llama model, provide generation + embedding.

- Lazy-load models only when needed (never on import/health check).
- `complete()` falls back to a deterministic fake reply when no LLM is
  configured/available, so unit tests and retrieval tests don't need a model.
- `embed()` uses sentence-transformers; verified dimension 768 for
  `keepitreal/vietnamese-sbert`. Returns a NumPy array because LightRAG's
  EmbeddingFunc requires `.size` on the result.
"""
import logging
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

_llm_model = None
_llm_tokenizer = None
_embedding_model: SentenceTransformer | None = None


def llm_available() -> bool:
    """Whether an LLM is configured to be loaded on this device."""
    return bool(settings.llm_model)


def reset_llm_for_tests():
    """Reset cached LLM/embedding models (used by unit tests)."""
    global _llm_model, _llm_tokenizer, _embedding_model
    _llm_model = None
    _llm_tokenizer = None
    _embedding_model = None


def device_info() -> dict:
    """Describe the runtime device without loading any model."""
    return {
        "cuda_available": torch.cuda.is_available(),
        "device": settings.llm_device,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "llm_loaded": _llm_model is not None,
    }


def _get_llm():
    """Lazy-load the causal LM. Raises if unavailable on this runtime."""
    global _llm_model, _llm_tokenizer
    if _llm_model is None:
        if settings.llm_quantize and torch.cuda.is_available():
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
            )
        else:
            bnb_config = None

        _llm_tokenizer = AutoTokenizer.from_pretrained(settings.llm_model)
        _llm_model = AutoModelForCausalLM.from_pretrained(
            settings.llm_model,
            quantization_config=bnb_config,
            device_map="auto" if torch.cuda.is_available() else "cpu",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
    return _llm_model, _llm_tokenizer


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            settings.embedding_model,
            device="cuda" if torch.cuda.is_available() else "cpu",
        )
    return _embedding_model


async def complete(prompt: str, system_prompt: str | None = None, max_new_tokens: int = 512, **kwargs) -> str:
    """Generate a completion. Falls back to fake reply if LLM not loadable."""
    try:
        model, tokenizer = _get_llm()
    except Exception as exc:
        logger.warning("LLM not available, using fake completion: %s", exc)
        return _fake_completion(prompt, system_prompt)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    input_len = inputs.input_ids.shape[1]
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=0.3,
        do_sample=True,
    )
    response_ids = outputs[0][input_len:]
    response = tokenizer.decode(response_ids, skip_special_tokens=True)

    for marker in ["assistant", "<|im_start|>assistant", "<|im_end|>", "<|endoftext|>"]:
        if marker in response:
            response = response.split(marker)[-1].strip()

    return response


def _fake_completion(prompt: str, system_prompt: str | None = None) -> str:
    """Deterministic fallback for tests: echo a short summary of the prompt."""
    words = [w for w in prompt.split() if len(w) > 3][:20]
    return " ".join(words) if words else "No LLM available."


async def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns a NumPy array of shape (n_texts, dim)."""
    model = _get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings
