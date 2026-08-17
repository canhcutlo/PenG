"""LLM integration: load Qwen/Llama model or a local GGUF, provide generation + embedding.

- Lazy-load models only when needed (never on import/health check).
- `complete()` falls back to a deterministic fake reply when no LLM is
  configured/available, so unit tests and retrieval tests don't need a model.
- `embed()` uses sentence-transformers; verified dimension 768 for
  `keepitreal/vietnamese-sbert`. Returns a NumPy array because LightRAG's
  EmbeddingFunc requires `.size` on the result.
- Supports two runtimes selected by `LLM_RUNTIME`:
  * "transformers" (default): Hugging Face Transformers + optional 4-bit quantize.
  * "llama_cpp": local GGUF via `llama-cpp-python`, CPU-friendly.
"""
import logging
import os
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from app.config import settings

logger = logging.getLogger(__name__)

_llm_model = None
_llm_tokenizer = None
_llm_llama = None
_embedding_model: SentenceTransformer | None = None


def llm_available() -> bool:
    """Whether an LLM is configured to be loaded on this device."""
    if settings.llm_runtime == "llama_cpp":
        return bool(settings.llm_gguf_model_path)
    return bool(settings.llm_model)


def reset_llm_for_tests():
    """Reset cached LLM/embedding models (used by unit tests)."""
    global _llm_model, _llm_tokenizer, _llm_llama, _embedding_model
    _llm_model = None
    _llm_tokenizer = None
    _llm_llama = None
    _embedding_model = None


def device_info() -> dict:
    """Describe the runtime device without loading any model."""
    info = {
        "cuda_available": torch.cuda.is_available(),
        "device": settings.llm_device,
        "llm_runtime": settings.llm_runtime,
        "llm_model": settings.llm_model,
        "llm_gguf_model_path": (
            str(settings.llm_gguf_model_path) if settings.llm_gguf_model_path else None
        ),
        "llm_gguf_chat_format": settings.llm_gguf_chat_format,
        "embedding_model": settings.embedding_model,
        "llm_loaded": _llm_model is not None or _llm_llama is not None,
    }
    return info


def _get_llm():
    """Lazy-load the configured LLM. Raises if unavailable on this runtime."""
    if settings.llm_runtime == "llama_cpp":
        return _get_llama_cpp_llm()
    return _get_transformers_llm()


def _get_transformers_llm():
    """Lazy-load the causal LM via Transformers."""
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


def _get_llama_cpp_llm():
    """Lazy-load a GGUF model via llama-cpp-python."""
    global _llm_llama
    if _llm_llama is None:
        if not settings.llm_gguf_model_path:
            raise RuntimeError(
                "LLM_RUNTIME=llama_cpp requires LLM_GGUF_MODEL_PATH to be set"
            )
        gguf_path = Path(settings.llm_gguf_model_path)
        if not gguf_path.exists():
            raise FileNotFoundError(f"GGUF model not found: {gguf_path}")

        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                "Install it with: pip install llama-cpp-python"
            ) from exc

        n_threads = settings.llm_gguf_n_threads or os.cpu_count() or 4
        chat_format = settings.llm_gguf_chat_format
        kwargs = {
            "model_path": str(gguf_path),
            "n_ctx": settings.llm_gguf_n_ctx,
            "n_threads": n_threads,
            "verbose": False,
        }
        if chat_format:
            kwargs["chat_format"] = chat_format

        _llm_llama = Llama(**kwargs)
    return _llm_llama


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            settings.embedding_model,
            device="cuda" if torch.cuda.is_available() else "cpu",
        )
    return _embedding_model


def _build_messages(prompt: str, system_prompt: str | None = None) -> list[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


async def complete(
    prompt: str,
    system_prompt: str | None = None,
    max_new_tokens: int = 512,
    **kwargs,
) -> str:
    """Generate a completion. Falls back to fake reply if LLM not loadable."""
    try:
        llm = _get_llm()
    except Exception as exc:
        logger.warning("LLM not available, using fake completion: %s", exc)
        return _fake_completion(prompt, system_prompt)

    try:
        if settings.llm_runtime == "llama_cpp":
            return await _complete_llama_cpp(llm, prompt, system_prompt, max_new_tokens)
        return await _complete_transformers(llm, prompt, system_prompt, max_new_tokens)
    except Exception as exc:
        logger.warning("LLM generation failed, using fake completion: %s", exc)
        return _fake_completion(prompt, system_prompt)


async def _complete_transformers(
    model_tokenizer,
    prompt: str,
    system_prompt: str | None,
    max_new_tokens: int,
) -> str:
    model, tokenizer = model_tokenizer
    text = tokenizer.apply_chat_template(
        _build_messages(prompt, system_prompt),
        tokenize=False,
        add_generation_prompt=True,
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


async def _complete_llama_cpp(
    llm,
    prompt: str,
    system_prompt: str | None,
    max_new_tokens: int,
) -> str:
    messages = _build_messages(prompt, system_prompt)

    try:
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=0.3,
        )
    except Exception:
        # Fallback for chat-format incompatible GGUFs: use a simple prompt string.
        prompt_text = ""
        if system_prompt:
            prompt_text += f"System: {system_prompt}\n\n"
        prompt_text += f"User: {prompt}\n\nAssistant:"
        response = llm(
            prompt=prompt_text,
            max_tokens=max_new_tokens,
            temperature=0.3,
            stop=["User:", "</s>"],
        )

    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if content:
                return content.strip()
            return choices[0].get("text", "").strip()
        return response.get("text", "").strip()
    return str(response).strip()


def _fake_completion(prompt: str, system_prompt: str | None = None) -> str:
    """Deterministic fallback for tests: echo a short summary of the prompt."""
    words = [w for w in prompt.split() if len(w) > 3][:20]
    return " ".join(words) if words else "No LLM available."


async def embed(texts: list[str]) -> np.ndarray:
    """Embed a list of texts. Returns a NumPy array of shape (n_texts, dim)."""
    model = _get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings
