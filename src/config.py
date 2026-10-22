"""
Central configuration for AI Video Intelligence Agent.
Loads settings from .env file with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


class Config:
    # ── Paths ────────────────────────────────────────────────────────────
    ROOT_DIR: Path = _ROOT
    UPLOADS_DIR: Path = _ROOT / "uploads"
    FRAMES_DIR: Path = _ROOT / "frames"
    LOGS_DIR: Path = _ROOT / "logs"
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", str(_ROOT / "chroma_db"))

    # ── LLM Provider & Gemini ───────────────────────────────────────────
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" or "ollama"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_VISION_MODEL: str = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-flash")

    # ── Ollama ───────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    OLLAMA_VISION_MODEL: str = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")

    # ── Whisper ──────────────────────────────────────────────────────────
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")

    # ── ChromaDB ─────────────────────────────────────────────────────────
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "video_transcripts")

    # ── Langfuse ─────────────────────────────────────────────────────────
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    LANGFUSE_ENABLED: bool = bool(
        os.getenv("LANGFUSE_SECRET_KEY", "")
        and os.getenv("LANGFUSE_PUBLIC_KEY", "")
        and os.getenv("LANGFUSE_SECRET_KEY", "") != "your_langfuse_secret_key"
    )

    # ── Processing ───────────────────────────────────────────────────────
    MAX_VIDEO_SIZE_MB: int = int(os.getenv("MAX_VIDEO_SIZE_MB", "500"))
    FRAME_EXTRACTION_INTERVAL: int = int(os.getenv("FRAME_EXTRACTION_INTERVAL", "30"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    TOP_K_RESULTS: int = int(os.getenv("TOP_K_RESULTS", "5"))

    # ── Supported formats ────────────────────────────────────────────────
    SUPPORTED_VIDEO_FORMATS: list = ["mp4", "mov", "avi", "mkv", "webm"]

    @classmethod
    def ensure_dirs(cls):
        """Create required directories if they don't exist."""
        for d in [cls.UPLOADS_DIR, cls.FRAMES_DIR, cls.LOGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)


config = Config()
config.ensure_dirs()
