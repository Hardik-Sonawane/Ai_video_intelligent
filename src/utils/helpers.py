"""
Utility helpers for AI Video Intelligence Agent.
"""

import os
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional

from src.config import config

logger = logging.getLogger(__name__)


def get_video_id(filepath: str) -> str:
    """Generate a stable ID from the video file path + size."""
    p = Path(filepath)
    size = p.stat().st_size if p.exists() else 0
    raw = f"{p.stem}_{size}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def format_time(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def save_uploaded_video(uploaded_file) -> str:
    """Save a Streamlit uploaded file to the uploads directory. Returns path."""
    config.ensure_dirs()
    dest = config.UPLOADS_DIR / uploaded_file.name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    logger.info(f"Saved uploaded video to {dest}")
    return str(dest)


def get_file_size_mb(filepath: str) -> float:
    """Return file size in MB."""
    return Path(filepath).stat().st_size / (1024 * 1024)


def cleanup_video_files(video_id: str):
    """Remove all cached files for a video (frames, audio, transcript)."""
    # Remove frames directory
    frames_dir = config.FRAMES_DIR / video_id
    if frames_dir.exists():
        shutil.rmtree(frames_dir)

    # Remove audio file
    for f in config.UPLOADS_DIR.glob(f"*{video_id}*"):
        if f.suffix in [".wav", ".json"]:
            f.unlink()

    logger.info(f"Cleaned up files for video_id: {video_id}")


def get_ffmpeg_path() -> Optional[str]:
    """Get path to FFmpeg binary, checking system PATH and imageio_ffmpeg fallback."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed or bundled."""
    return get_ffmpeg_path() is not None


def setup_logging():
    """Configure logging for the application."""
    log_file = config.LOGS_DIR / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
