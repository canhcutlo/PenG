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

    llm_model: str = "Qwen/Qwen2.5-3B-Instruct"
    llm_device: str = "cuda"
    llm_quantize: bool = True
    use_instructor: bool = False

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

    @field_validator("upload_dir", "sqlite_path", "lightrag_working_dir", mode="after")
    @classmethod
    def _resolve_relative_paths(cls, v: Path) -> Path:
        """Resolve relative paths against the project root; keep absolute paths as-is."""
        if v.is_absolute():
            return v
        return (PROJECT_ROOT / v).resolve()


settings = Settings()
