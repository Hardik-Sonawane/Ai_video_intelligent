"""
Agent Tools for AI Video Intelligence Agent.
Each tool wraps a specific capability the LangChain agent can invoke.
"""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import requests
from langchain.tools import tool

from src.config import config

logger = logging.getLogger(__name__)

# These globals are set by the agent runner before invoking tools
_vector_store = None
_video_processor = None
_video_metadata = None
_current_video_id = None
_transcript_data = None
_frames_data = None
_llm = None  # LLM instance for tools that need direct LLM access


def init_tools(
    vector_store,
    video_processor,
    video_metadata: dict,
    transcript_data: dict,
    frames_data: list,
    llm=None,
):
    """Inject shared state into the tools module."""
    global _vector_store, _video_processor, _video_metadata
    global _current_video_id, _transcript_data, _frames_data, _llm

    _vector_store = vector_store
    _video_processor = video_processor
    _video_metadata = video_metadata
    _current_video_id = video_metadata.get("video_id", "")
    _transcript_data = transcript_data
    _frames_data = frames_data
    _llm = llm


# ── Tool 1: RAG / Transcript Search ─────────────────────────────────────────

@tool
def search_transcript(query: str) -> str:
    """
    Search the video transcript using semantic (RAG) search.
    Use this for text-based questions about what was said in the video.
    Returns the most relevant transcript segments with timestamps.
    Input: a natural language query string.
    """
    if _vector_store is None or _current_video_id is None:
        return "Error: No video loaded. Please upload and process a video first."

    results = _vector_store.search(query, _current_video_id, top_k=config.TOP_K_RESULTS)
    if not results:
        return "No relevant transcript segments found for this query."

    output = [f"Found {len(results)} relevant transcript segment(s):\n"]
    for i, r in enumerate(results, 1):
        output.append(
            f"[Segment {i}] ⏱ {r['start_formatted']} → {r['end_formatted']}\n"
            f"Relevance: {r['relevance_score']:.2f}\n"
            f"Text: {r['text']}\n"
        )
    return "\n".join(output)


# ── Tool 2: Timestamp Lookup ─────────────────────────────────────────────────

@tool
def get_transcript_at_timestamp(timestamp: str) -> str:
    """
    Get the transcript content at a specific timestamp in the video.
    Use this when the user asks what happened at a specific time.
    Input: timestamp as 'MM:SS' or 'HH:MM:SS' string (e.g. '02:30' or '01:15:00').
    Also accepts plain seconds like '150'.
    """
    if _transcript_data is None:
        return "Error: No video loaded."

    # Parse timestamp to seconds
    try:
        ts = timestamp.strip()
        if ":" in ts:
            parts = ts.split(":")
            if len(parts) == 2:
                sec = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            else:
                return f"Invalid timestamp format: {timestamp}. Use MM:SS or HH:MM:SS."
        else:
            sec = float(ts)
    except (ValueError, IndexError):
        return f"Cannot parse timestamp: {timestamp}"

    # Search in local transcript first (faster)
    segments = _transcript_data.get("segments", [])
    window = 60.0
    nearby = [
        s for s in segments
        if s["start"] <= sec + window and s["end"] >= sec - window
    ]

    if nearby:
        output = [f"Transcript near timestamp {timestamp}:\n"]
        for s in nearby[:8]:
            output.append(f"  ⏱ {s['start_formatted']} → {s['end_formatted']}: {s['text']}")
        return "\n".join(output)

    # Fallback to vector store
    if _vector_store and _current_video_id:
        results = _vector_store.search_by_timestamp(sec, _current_video_id, window_sec=window)
        if results:
            output = [f"Transcript near {timestamp}:\n"]
            for r in results:
                output.append(f"⏱ {r['start_formatted']} → {r['end_formatted']}: {r['text']}")
            return "\n".join(output)

    return f"No transcript found near timestamp {timestamp}."


# ── Tool 3: Video Metadata ───────────────────────────────────────────────────

@tool
def get_video_metadata(query: str = "") -> str:
    """
    Get metadata information about the uploaded video.
    Returns filename, duration, resolution, FPS, format, and size.
    Use for questions about the video itself (how long is it, what format, etc.).
    Input: any string (ignored, always returns full metadata).
    """
    if _video_metadata is None:
        return "Error: No video loaded."

    m = _video_metadata
    return (
        f"📹 Video Metadata\n"
        f"  Filename  : {m.get('filename', 'N/A')}\n"
        f"  Duration  : {m.get('duration_formatted', 'N/A')} "
        f"({m.get('duration_seconds', 0):.1f}s)\n"
        f"  Resolution: {m.get('resolution', 'N/A')}\n"
        f"  FPS       : {m.get('fps', 'N/A')}\n"
        f"  Format    : {m.get('format', 'N/A')}\n"
        f"  Size      : {m.get('size_mb', 'N/A')} MB\n"
        f"  Frames    : {m.get('total_frames', 'N/A')}"
    )


# ── Tool 4: Full Transcript ──────────────────────────────────────────────────

@tool
def get_full_transcript(query: str = "") -> str:
    """
    Get the complete transcript of the video with timestamps.
    Use this for summarization tasks or when you need the full context.
    Input: any string (ignored).
    """
    if _transcript_data is None:
        return "Error: No transcript available."

    segments = _transcript_data.get("segments", [])
    if not segments:
        full = _transcript_data.get("full_text", "")
        if not full:
            return "Transcript is empty."
        return full[:6000] + ("\n[... truncated ...]" if len(full) > 6000 else "")

    # Return segments with timestamps for better grounding
    lines = []
    for seg in segments:
        lines.append(f"[{seg['start_formatted']}] {seg['text']}")

    full_timestamped = "\n".join(lines)
    if len(full_timestamped) > 6000:
        return full_timestamped[:6000] + "\n[... transcript truncated for context window ...]"
    return full_timestamped


# ── Tool 5: Visual Frame Analysis ───────────────────────────────────────────

@tool
def analyze_video_frame(timestamp: str) -> str:
    """
    Extract and visually analyze a video frame at a specific timestamp.
    Use this for visual questions: 'What is shown at 05:30?', 'What object is visible?',
    'What is the speaker holding?', 'What text is on screen?'.
    Input: timestamp as 'MM:SS' or 'HH:MM:SS', or seconds like '150'.
    """
    if _video_processor is None:
        return "Error: No video loaded."

    # Parse timestamp
    try:
        ts = timestamp.strip()
        if ":" in ts:
            parts = ts.split(":")
            if len(parts) == 2:
                sec = int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            else:
                return f"Invalid timestamp: {timestamp}"
        else:
            sec = float(ts)
    except (ValueError, IndexError):
        return f"Cannot parse timestamp: {timestamp}"

    frame_path = _video_processor.extract_frame_at(sec)
    if not frame_path:
        return f"Could not extract frame at {timestamp}."

    # Visual analysis using selected LLM provider
    if config.LLM_PROVIDER.lower() == "gemini":
        if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "your_gemini_api_key_here":
            return (
                f"Visual frame extracted at {frame_path}, but GEMINI_API_KEY is not configured. "
                "Please set your GEMINI_API_KEY in the .env file or sidebar."
            )
        try:
            from google import genai
            from PIL import Image

            client = genai.Client(api_key=config.GEMINI_API_KEY)
            img = Image.open(frame_path)
            response = client.models.generate_content(
                model=config.GEMINI_VISION_MODEL,
                contents=[
                    img,
                    (
                        "Describe what you see in this video frame in detail. "
                        "List all visible objects, people, text, colors, and activities. "
                        "Be specific and comprehensive."
                    ),
                ],
            )
            analysis = response.text or "No response from Gemini vision model."
            return (
                f"🖼 Visual Analysis at {timestamp} (Gemini Vision):\n{analysis}\n"
                f"(Frame saved at: {frame_path})"
            )
        except Exception as e:
            logger.error(f"Gemini vision error: {e}", exc_info=True)
            return (
                f"Gemini vision analysis failed: {str(e)}\n"
                f"Frame was extracted at: {frame_path}"
            )

    # ── Ollama vision model (llava) ──────────────────────────────────────
    try:
        with open(frame_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": config.OLLAMA_VISION_MODEL,
                "prompt": (
                    "Describe what you see in this video frame in detail. "
                    "List all visible objects, people, text, colors, and activities. "
                    "Be specific and comprehensive."
                ),
                "images": [img_b64],
                "stream": False,
            },
            timeout=120,
        )
        if response.status_code == 200:
            analysis = response.json().get("response", "No response from vision model.")
            return (
                f"🖼 Visual Analysis at {timestamp} (Ollama/{config.OLLAMA_VISION_MODEL}):\n{analysis}\n"
                f"(Frame saved at: {frame_path})"
            )
        else:
            return (
                f"Vision model returned status {response.status_code}. "
                f"Make sure '{config.OLLAMA_VISION_MODEL}' is pulled: "
                f"`ollama pull {config.OLLAMA_VISION_MODEL}`\n"
                f"Frame extracted at: {frame_path}"
            )
    except requests.exceptions.ConnectionError:
        return (
            "Could not connect to Ollama for visual analysis. "
            "Please ensure Ollama is running.\n"
            f"Frame extracted at: {frame_path}"
        )
    except Exception as e:
        return f"Visual analysis error: {str(e)}\nFrame extracted at: {frame_path}"


# ── Tool 6: Summarize Video ──────────────────────────────────────────────────

@tool
def summarize_video(detail_level: str = "medium") -> str:
    """
    Generate a comprehensive summary of the video content.
    Use this when user asks to summarize the video or explain what it's about.
    Input: detail_level - 'brief', 'medium', or 'detailed'.
    """
    if _transcript_data is None:
        return "Error: No transcript available for summarization."

    full_text = _transcript_data.get("full_text", "")
    segments = _transcript_data.get("segments", [])
    metadata = _video_metadata or {}

    if not full_text:
        return "The video has no detected speech content."

    # Determine content length based on detail level
    detail_map = {"brief": 1000, "medium": 2500, "detailed": 5000}
    max_chars = detail_map.get(detail_level.lower(), 2500)

    # Get key moments (evenly sampled)
    key_moments = []
    if segments:
        n = len(segments)
        sample_size = {"brief": 3, "medium": 6, "detailed": 10}.get(detail_level.lower(), 6)
        indices = [int(i * n / sample_size) for i in range(sample_size)]
        for idx in indices:
            seg = segments[min(idx, n - 1)]
            key_moments.append(f"  • [{seg['start_formatted']}] {seg['text'][:120]}")

    duration = metadata.get("duration_formatted", "unknown")
    language = _transcript_data.get("language", "en")
    word_count = len(full_text.split())

    summary_parts = [
        f"📋 Video Summary ({detail_level.capitalize()} Detail)\n",
        f"Duration: {duration} | Language: {language.upper()} | ~{word_count} words spoken\n",
        f"\nKey Moments from the Video:",
    ]
    summary_parts.extend(key_moments)

    content_preview = full_text[:max_chars]
    if len(full_text) > max_chars:
        content_preview += "\n[... content continues ...]"

    summary_parts.append(f"\nFull Transcript Content:\n{content_preview}")

    return "\n".join(summary_parts)


# ── Tool 7: Generate MCQ Quiz ────────────────────────────────────────────────

@tool
def generate_quiz(num_questions: str = "5") -> str:
    """
    Generate multiple-choice questions (MCQs) from the video transcript.
    Use when user asks to 'create quiz', 'generate MCQs', or 'test my knowledge'.
    Input: number of questions as a string (e.g. '5', '10').
    """
    if _transcript_data is None:
        return "Error: No transcript available for quiz generation."

    try:
        n = int(str(num_questions).strip())
        n = max(1, min(n, 20))  # clamp between 1 and 20
    except (ValueError, TypeError):
        n = 5

    full_text = _transcript_data.get("full_text", "")
    segments = _transcript_data.get("segments", [])

    if not full_text:
        return "Cannot generate quiz: transcript is empty."

    # Build a well-structured source text with timestamps
    timestamped_content = []
    if segments:
        sample_size = min(n * 3, len(segments))
        step = max(1, len(segments) // sample_size)
        for i in range(0, len(segments), step):
            seg = segments[i]
            timestamped_content.append(f"[{seg['start_formatted']}] {seg['text']}")
    source_text = "\n".join(timestamped_content[:50]) if timestamped_content else full_text[:3000]

    # Build the quiz generation prompt for the LLM
    quiz_prompt = (
        f"Based on the following video transcript, generate exactly {n} multiple-choice questions (MCQs).\n\n"
        f"TRANSCRIPT:\n{source_text}\n\n"
        f"FORMAT REQUIREMENTS:\n"
        f"For each question, use this exact format:\n\n"
        f"Q1. [Question text]\n"
        f"A) [Option A]\n"
        f"B) [Option B]\n"
        f"C) [Option C]\n"
        f"D) [Option D]\n"
        f"✅ Correct Answer: [Letter] - [Brief explanation with timestamp if available]\n\n"
        f"RULES:\n"
        f"- Questions must be based ONLY on the transcript content above\n"
        f"- Include the timestamp reference in answers where possible\n"
        f"- Make distractors plausible but clearly wrong\n"
        f"- Cover different topics from the video\n\n"
        f"Generate {n} MCQs now:"
    )

    # Try to use the LLM directly for better quiz generation
    if _llm is not None:
        try:
            from langchain_core.messages import HumanMessage
            response = _llm.invoke([HumanMessage(content=quiz_prompt)])
            return f"📝 Quiz: {n} Multiple-Choice Questions\n\n{response.content}"
        except Exception as e:
            logger.warning(f"LLM quiz generation failed: {e}, returning prompt template")

    # Fallback: return the prompt so the ReAct agent can use it as context
    return (
        f"QUIZ_GENERATION_CONTEXT\n"
        f"Number of questions requested: {n}\n"
        f"Source material:\n{source_text[:3000]}\n\n"
        f"Please generate {n} well-formatted MCQs based on the above transcript. "
        f"For each question provide: Q#, question text, 4 options (A/B/C/D), "
        f"and mark the correct answer with explanation."
    )


# ── Tool 8: Find Topic Timestamp ─────────────────────────────────────────────

@tool
def find_topic_timestamp(topic: str) -> str:
    """
    Find when a specific topic or concept is discussed in the video.
    Use when the user asks 'when is X explained?', 'at what time does the speaker talk about Y?'.
    Input: the topic or concept to search for.
    """
    if _vector_store is None or _current_video_id is None:
        return "Error: No video loaded."

    results = _vector_store.search(topic, _current_video_id, top_k=5)
    if not results:
        return f"The topic '{topic}' does not appear to be discussed in this video."

    output = [f"🔍 '{topic}' is discussed at:\n"]
    for r in results:
        output.append(
            f"  ⏱ [{r['start_formatted']} → {r['end_formatted']}] "
            f"(relevance: {r['relevance_score']:.2f})\n"
            f"  Context: {r['text'][:200]}\n"
        )
    return "\n".join(output)


# ── Tool 9: Extract Key Topics ───────────────────────────────────────────────

@tool
def extract_key_topics(query: str = "") -> str:
    """
    Extract key topics and important points from the video.
    Use when user asks 'what are the main topics?', 'what are the key points?',
    'what does the video cover?'.
    Input: any string (ignored).
    """
    if _transcript_data is None:
        return "Error: No transcript available."

    segments = _transcript_data.get("segments", [])
    if not segments:
        return "No segments found in transcript."

    total = len(segments)
    # Sample evenly-spaced segments to get topic coverage
    sample_size = min(15, total)
    step = max(1, total // sample_size)
    sample_segs = [segments[i] for i in range(0, total, step)][:sample_size]

    output = ["📌 Key Content Segments from the Video:\n"]
    for seg in sample_segs:
        output.append(f"  [{seg['start_formatted']}] {seg['text'][:150]}")

    # Also include first and last segments
    if segments[0] not in sample_segs:
        output.insert(1, f"  [{segments[0]['start_formatted']}] {segments[0]['text'][:150]} (Opening)")
    if segments[-1] not in sample_segs:
        output.append(f"  [{segments[-1]['start_formatted']}] {segments[-1]['text'][:150]} (Closing)")

    return "\n".join(output)


# ── Tool 10: Analyze Frame Range ─────────────────────────────────────────────

@tool
def analyze_frame_range(time_range: str) -> str:
    """
    Extract and analyze multiple frames from a time range in the video.
    Use this for scene-level visual questions like 'what happens between 2:00 and 5:00?'.
    Input: time range as 'START_TIMESTAMP-END_TIMESTAMP' e.g. '02:00-05:00'.
    """
    if _video_processor is None:
        return "Error: No video loaded."

    try:
        if "-" not in time_range:
            return "Invalid format. Use 'START-END' e.g. '02:00-05:00'."

        parts = time_range.strip().split("-", 1)
        start_str, end_str = parts[0].strip(), parts[1].strip()

        def parse_ts(ts: str) -> float:
            if ":" in ts:
                p = ts.split(":")
                if len(p) == 2:
                    return int(p[0]) * 60 + float(p[1])
                elif len(p) == 3:
                    return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
            return float(ts)

        start_sec = parse_ts(start_str)
        end_sec = parse_ts(end_str)

        if end_sec <= start_sec:
            return "End time must be after start time."
        if end_sec - start_sec > 600:
            return "Time range too large (max 10 minutes). Please use a smaller range."

    except Exception as e:
        return f"Could not parse time range '{time_range}': {e}"

    frame_paths = _video_processor.extract_frames_range(start_sec, end_sec, max_frames=4)
    if not frame_paths:
        return f"Could not extract frames from {time_range}."

    if config.LLM_PROVIDER.lower() == "gemini" and config.GEMINI_API_KEY and config.GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            from google import genai
            from PIL import Image

            client = genai.Client(api_key=config.GEMINI_API_KEY)
            contents = []
            for p in frame_paths:
                contents.append(Image.open(p))
            contents.append(
                f"These are frames from a video between {start_str} and {end_str}. "
                "Describe what is happening in this scene, any changes between frames, "
                "and key visual elements present."
            )
            response = client.models.generate_content(
                model=config.GEMINI_VISION_MODEL,
                contents=contents,
            )
            analysis = response.text or "No response from Gemini vision model."
            return (
                f"🎬 Scene Analysis ({start_str} → {end_str}) — {len(frame_paths)} frames:\n{analysis}"
            )
        except Exception as e:
            logger.error(f"Gemini scene analysis error: {e}", exc_info=True)
            return (
                f"Scene analysis failed: {str(e)}\n"
                f"Extracted {len(frame_paths)} frames from {time_range}."
            )

    return (
        f"Extracted {len(frame_paths)} frames from {time_range}. "
        "Visual analysis requires Gemini API key or Ollama with llava model configured. "
        f"Frames saved at: {', '.join(frame_paths)}"
    )


# ── Tool registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [
    search_transcript,
    get_transcript_at_timestamp,
    get_video_metadata,
    get_full_transcript,
    analyze_video_frame,
    summarize_video,
    generate_quiz,
    find_topic_timestamp,
    extract_key_topics,
    analyze_frame_range,
]
