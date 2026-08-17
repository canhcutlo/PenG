"""Tests for the LLM service: runtime selection, lazy load, fallback, and GGUF path."""
import builtins
from pathlib import Path

import pytest

from app import config as config_module
from app.config import PROJECT_ROOT, settings
from app.services import llm as llm_module
from app.services.llm import (
    complete,
    device_info,
    llm_available,
    reset_llm_for_tests,
)


@pytest.fixture(autouse=True)
def reset_and_restore():
    """Reset LLM caches before each test and restore settings after."""
    original_runtime = settings.llm_runtime
    original_gguf = settings.llm_gguf_model_path
    original_model = settings.llm_model
    reset_llm_for_tests()
    yield
    reset_llm_for_tests()
    settings.llm_runtime = original_runtime
    settings.llm_gguf_model_path = original_gguf
    settings.llm_model = original_model


@pytest.mark.asyncio
async def test_complete_fallback_when_no_model(monkeypatch):
    """If model loading fails, complete() returns the fake fallback."""
    settings.llm_runtime = "transformers"
    settings.llm_model = ""

    def failing_get():
        raise RuntimeError("model missing")

    monkeypatch.setattr(llm_module, "_get_llm", failing_get)
    response = await complete("hello world", system_prompt="sys")
    assert isinstance(response, str)
    assert response  # fake fallback returns non-empty text


@pytest.mark.asyncio
async def test_llama_cpp_missing_dependency_uses_fallback(monkeypatch, tmp_path):
    """If llama-cpp-python is not installed, complete() falls back gracefully."""
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = tmp_path / "fake.gguf"
    settings.llm_gguf_model_path.write_text("fake")

    original_import = builtins.__import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "llama_cpp":
            raise ImportError("No module named 'llama_cpp'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", failing_import)

    response = await complete("hello world")
    assert isinstance(response, str)
    assert response


@pytest.mark.asyncio
async def test_llama_cpp_missing_path_uses_fallback():
    """If the GGUF path is not set, complete() falls back gracefully."""
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = None

    response = await complete("hello world")
    assert isinstance(response, str)
    assert response


def test_llm_available_transformers():
    settings.llm_runtime = "transformers"
    settings.llm_model = "Qwen/Qwen2.5-1.5B-Instruct"
    assert llm_available() is True

    settings.llm_model = ""
    assert llm_available() is False


def test_llm_available_llama_cpp():
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = PROJECT_ROOT / "models" / "model.gguf"
    assert llm_available() is True

    settings.llm_gguf_model_path = None
    assert llm_available() is False


def test_device_info_reports_runtime():
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = PROJECT_ROOT / "models" / "model.gguf"
    info = device_info()
    assert info["llm_runtime"] == "llama_cpp"
    assert info["llm_gguf_model_path"] == str(PROJECT_ROOT / "models" / "model.gguf")
    assert "llm_loaded" in info


def test_gguf_path_resolves_relative_to_project_root(monkeypatch):
    """Relative GGUF paths resolve from project root."""
    monkeypatch.setenv("LLM_GGUF_MODEL_PATH", "models/my-model.gguf")
    fresh = config_module.Settings()
    assert fresh.llm_gguf_model_path == PROJECT_ROOT / "models" / "my-model.gguf"


@pytest.mark.asyncio
async def test_llama_cpp_complete_uses_chat_completion(monkeypatch):
    """A monkeypatched Llama instance returns assistant content."""
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = PROJECT_ROOT / "models" / "fake.gguf"

    class FakeLlama:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_chat_completion(self, messages, max_tokens, temperature):
            assert any(m["role"] == "user" for m in messages)
            return {
                "choices": [
                    {"message": {"content": "  Hello from GGUF  "}}
                ]
            }

    monkeypatch.setattr(llm_module, "_llm_llama", FakeLlama())
    response = await llm_module._complete_llama_cpp(
        llm_module._llm_llama,
        "hi",
        None,
        32,
    )
    assert response == "Hello from GGUF"


@pytest.mark.asyncio
async def test_llama_cpp_complete_fallback_to_prompt(monkeypatch):
    """If create_chat_completion fails, the generator falls back to __call__."""
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = PROJECT_ROOT / "models" / "fake.gguf"

    class FakeLlama:
        def __init__(self, **kwargs):
            pass

        def create_chat_completion(self, messages, max_tokens, temperature):
            raise ValueError("unsupported chat format")

        def __call__(self, prompt, max_tokens, temperature, stop):
            return {"choices": [{"text": "fallback answer"}]}

    monkeypatch.setattr(llm_module, "_llm_llama", FakeLlama())
    response = await llm_module._complete_llama_cpp(
        llm_module._llm_llama,
        "hi",
        None,
        32,
    )
    assert response == "fallback answer"


def test_llama_lazy_load_caches_instance(monkeypatch, tmp_path):
    """_get_llama_cpp_llm caches the Llama instance."""
    settings.llm_runtime = "llama_cpp"
    settings.llm_gguf_model_path = tmp_path / "model.gguf"
    settings.llm_gguf_model_path.write_text("fake")

    created = {"count": 0}

    class FakeLlama:
        def __init__(self, **kwargs):
            created["count"] += 1

    fake_module = type("llama_cpp", (), {"Llama": FakeLlama})()
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "llama_cpp":
            return fake_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(llm_module, "_llm_llama", None)

    first = llm_module._get_llama_cpp_llm()
    second = llm_module._get_llama_cpp_llm()
    assert first is second
    assert created["count"] == 1
