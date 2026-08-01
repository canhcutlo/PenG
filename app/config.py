from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "PenG"
    debug: bool = True

    # Paths
    upload_dir: Path = Path("uploads")
    chroma_dir: Path = Path("chroma_data")
    sqlite_path: Path = Path("peng_history.db")

    # LLM
    llm_model: str = "Qwen/Qwen2-7B-Instruct"  # or "meta-llama/Meta-Llama-3-8B-Instruct"
    llm_device: str = "cuda"
    llm_quantize: bool = True  # 4-bit for Colab T4
    use_instructor: bool = False  # True only when OpenAI-compatible endpoint configured

    # Embedding
    embedding_model: str = "keepitreal/vietnamese-sbert"
    embedding_dim: int = 768  # verify after loading actual model

    # faster-whisper
    whisper_model: str = "base"  # tiny/base/small/medium/large-v3

    # OCR
    # Default: tesseract (works on Python 3.14+). Use 'surya' on Python <=3.11.
    ocr_engine: str = "tesseract"  # tesseract | easyocr | surya

    # LightRAG
    lightrag_working_dir: Path = Path("lightrag_data")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # ChromaDB
    chroma_collection_name: str = "learning_materials"

    # Upload limits
    max_upload_size_mb: int = 500
    allowed_audio_extensions: str = ".mp3,.wav,.m4a,.ogg,.flac"
    allowed_image_extensions: str = ".png,.jpg,.jpeg,.bmp,.tiff"
    allowed_pdf_extensions: str = ".pdf"
    allowed_video_extensions: str = ".mp4,.avi,.mov,.mkv"
    allowed_mime_types: str = (
        "audio/mpeg,audio/wav,audio/x-wav,audio/m4a,audio/ogg,audio/flac,"
        "image/png,image/jpeg,image/bmp,image/tiff,"
        "application/pdf,"
        "video/mp4,video/x-msvideo,video/quicktime,video/x-matroska"
    )
    processing_timeout_seconds: int = 600  # 10 minutes max per job
    process_on_upload: bool = True  # Set False in unit tests to skip background processing
    index_on_upload: bool = True  # Index extracted text into LightRAG after extraction


settings = Settings()
