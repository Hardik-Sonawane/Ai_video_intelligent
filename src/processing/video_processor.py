"""
Video processing module.
Handles audio extraction, Whisper transcription, and frame extraction.
"""

import os
import json
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

import cv2
import whisper
import numpy as np
from PIL import Image

from src.config import config
from src.utils.helpers import get_ffmpeg_path

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Processes a video file:
    1. Extracts audio → WAV
    2. Transcribes with Whisper (with timestamps)
    3. Extracts frames at configurable intervals
    """

    def __init__(self, video_path: str):
        self.video_path = Path(video_path)
        self.video_id = self.video_path.stem
        self.frames_dir = config.FRAMES_DIR / self.video_id
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._model: Optional[whisper.Whisper] = None

    # ── Metadata ─────────────────────────────────────────────────────────

    def get_metadata(self) -> dict:
        """Extract basic video metadata using OpenCV."""
        cap = cv2.VideoCapture(str(self.video_path))
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration_sec = total_frames / fps if fps > 0 else 0
            size_mb = self.video_path.stat().st_size / (1024 * 1024)
        finally:
            cap.release()

        return {
            "filename": self.video_path.name,
            "video_id": self.video_id,
            "duration_seconds": round(duration_sec, 2),
            "duration_formatted": self._format_time(duration_sec),
            "fps": round(fps, 2),
            "resolution": f"{width}x{height}",
            "total_frames": total_frames,
            "size_mb": round(size_mb, 2),
            "format": self.video_path.suffix.lstrip(".").upper(),
        }

    # ── Audio extraction ─────────────────────────────────────────────────

    def extract_audio(self) -> str:
        """Extract audio from the video to a WAV file using FFmpeg."""
        ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
        audio_path = str(self.video_path.with_suffix(".wav"))
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(self.video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")
        logger.info(f"Audio extracted to {audio_path}")
        return audio_path

    # ── Transcription ────────────────────────────────────────────────────

    def transcribe(self, audio_path: str) -> dict:
        """
        Run Whisper transcription.
        Returns dict with 'text' and 'segments' (list of timestamped chunks).
        """
        if self._model is None:
            logger.info(f"Loading Whisper model: {config.WHISPER_MODEL}")
            self._model = whisper.load_model(config.WHISPER_MODEL)

        logger.info("Running Whisper transcription...")
        result = self._model.transcribe(
            audio_path,
            verbose=False,
            word_timestamps=False,
        )

        # Build structured segments
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "id": seg["id"],
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
                "start_formatted": self._format_time(seg["start"]),
                "end_formatted": self._format_time(seg["end"]),
            })

        transcript_data = {
            "full_text": result["text"].strip(),
            "segments": segments,
            "language": result.get("language", "en"),
        }

        # Save transcript JSON
        transcript_path = config.UPLOADS_DIR / f"{self.video_id}_transcript.json"
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Transcript saved: {transcript_path}")
        return transcript_data

    # ── Frame extraction ─────────────────────────────────────────────────

    def extract_frames(
        self, interval_sec: int = None, max_frames: int = 200
    ) -> list[dict]:
        """
        Extract frames at a fixed time interval.
        Returns list of {timestamp_sec, timestamp_formatted, frame_path}.
        """
        interval = interval_sec or config.FRAME_EXTRACTION_INTERVAL
        cap = cv2.VideoCapture(str(self.video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        frame_records = []
        t = 0.0
        count = 0

        while t < duration and count < max_frames:
            frame_no = int(t * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret:
                break

            frame_name = f"frame_{int(t):06d}.jpg"
            frame_path = self.frames_dir / frame_name
            cv2.imwrite(str(frame_path), frame)

            frame_records.append({
                "timestamp_sec": round(t, 2),
                "timestamp_formatted": self._format_time(t),
                "frame_path": str(frame_path),
            })

            t += interval
            count += 1

        cap.release()
        logger.info(f"Extracted {len(frame_records)} frames")
        return frame_records

    def extract_frame_at(self, timestamp_sec: float) -> Optional[str]:
        """Extract a single frame at a specific timestamp. Returns path."""
        cap = cv2.VideoCapture(str(self.video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_no = int(timestamp_sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        frame_name = f"frame_query_{int(timestamp_sec):06d}.jpg"
        frame_path = self.frames_dir / frame_name
        cv2.imwrite(str(frame_path), frame)
        return str(frame_path)

    def extract_frames_range(
        self, start_sec: float, end_sec: float, max_frames: int = 5
    ) -> list[str]:
        """Extract up to max_frames evenly spaced between start and end."""
        duration = end_sec - start_sec
        if duration <= 0:
            return []

        interval = duration / max(max_frames, 1)
        paths = []
        for i in range(max_frames):
            t = start_sec + i * interval
            p = self.extract_frame_at(t)
            if p:
                paths.append(p)
        return paths

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Convert seconds to HH:MM:SS format."""
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
