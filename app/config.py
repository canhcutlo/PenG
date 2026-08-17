from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


def _project_root() -> Path:
    """Return the repository root directory (parent of app/)."""
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PenG"
    debug: bool = True

    upload_dir: Path = PROJECT_ROOT / "uploads"
    sqlite_path: Path = PROJECT_ROOT / "peng_history.db"
    lightrag_working_dir: Path = PROJECT_ROOT / "lightrag_data"

    llm_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    llm_device: str = "cuda"
    llm_quantize: bool = True
    use_instructor: bool = False

    # LLM runtime selection
    # - "transformers" (default): load a Hugging Face model with Transformers/BitsAndBytes (CUDA-friendly).
    # - "llama_cpp": load a local GGUF file via llama-cpp-python (CPU-friendly).
    llm_runtime: str = "transformers"
    llm_gguf_model_path: Path | None = None
    llm_gguf_chat_format: str | None = None  # e.g. "chatml", "qwen", leave None for auto
    llm_gguf_n_threads: int | None = None  # None lets llama.cpp use all logical cores
    llm_gguf_n_ctx: int = 4096

    @field_validator("llm_runtime")
    @classmethod
    def _validate_llm_runtime(cls, v: str) -> str:
        allowed = {"transformers", "llama_cpp"}
        if v not in allowed:
            raise ValueError(f"LLM_RUNTIME must be one of {allowed}, got {v!r}")
        return v

    embedding_model: str = "keepitreal/vietnamese-sbert"
    embedding_dim: int = 768

    whisper_model: str = "base"

    ocr_engine: str = "tesseract"

    host: str = "0.0.0.0"
    port: int = 8000

    max_upload_size_mb: int = 500
    allowed_audio_extensions: str = ".mp3,.wav,.m4a,.ogg,.flac"
    allowed_image_extensions: str = ".png,.jpg,.jpeg,.bmp,.tiff"
    allowed_pdf_extensions: str = ".pdf"
    allowed_video_extensions: str = ".mp4,.avi,.mov,.mkv"
    processing_timeout_seconds: int = 600
    process_on_upload: bool = True
    index_on_upload: bool = True

    # Auth
    auth_cookie_name: str = "peng_session"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "Lax"
    auth_cookie_max_age_seconds: int = 7 * 24 * 60 * 60
    auth_csrf_cookie_name: str = "peng_csrf"
    auth_csrf_header_name: str = "X-CSRF-Token"
    auth_rate_limit_login_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60
    auth_system_user_username: str = "system"

    @field_validator(
        "upload_dir",
        "sqlite_path",
        "lightrag_working_dir",
        "llm_gguf_model_path",
        mode="after",
    )
    @classmethod
    def _resolve_relative_paths(cls, v: Path | None) -> Path | None:
        """Resolve relative paths against the project root; keep absolute paths as-is."""
        if v is None:
            return v
        if v.is_absolute():
            return v
        return (PROJECT_ROOT / v).resolve()


settings = Settings()
