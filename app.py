"""
AI Video Intelligence Agent - Main Streamlit Application
A full-stack agentic AI web app for video understanding.
"""

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

import streamlit as st

# ── Must be first Streamlit call ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Video Intelligence Agent",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/",
        "About": "AI Video Intelligence Agent — LLM + RAG + Tool Calling + Multimodal",
    },
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import config
from src.utils.helpers import (
    save_uploaded_video,
    get_video_id,
    check_ffmpeg,
    setup_logging,
)
from src.processing.video_processor import VideoProcessor
from src.processing.vector_store import VectorStore
from src.agent.video_agent import VideoAgent

setup_logging()
logger = logging.getLogger(__name__)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Google Font ──────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Root & body ────────────────────────────────────────────── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 50%, #0a1020 100%);
    min-height: 100vh;
}

/* ── Hide default Streamlit branding ────────────────────────── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* ── Main hero header ───────────────────────────────────────── */
.hero-header {
    background: linear-gradient(135deg, #1a1f35 0%, #162040 50%, #1a2850 100%);
    border: 1px solid rgba(99, 179, 237, 0.2);
    border-radius: 20px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.5);
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(99, 179, 237, 0.05) 0%, transparent 60%);
    pointer-events: none;
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #63b3ed, #b794f4, #68d391);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    letter-spacing: -0.5px;
}
.hero-subtitle {
    color: rgba(255,255,255,0.6);
    font-size: 0.95rem;
    margin-top: 0.3rem;
    letter-spacing: 0.3px;
}
.hero-badges {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-top: 1rem;
}
.badge {
    background: rgba(99, 179, 237, 0.1);
    border: 1px solid rgba(99, 179, 237, 0.25);
    color: #63b3ed;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.3px;
}
.badge-green { background: rgba(104, 211, 145, 0.1); border-color: rgba(104, 211, 145, 0.25); color: #68d391; }
.badge-purple { background: rgba(183, 148, 244, 0.1); border-color: rgba(183, 148, 244, 0.25); color: #b794f4; }
.badge-orange { background: rgba(251, 191, 36, 0.1); border-color: rgba(251, 191, 36, 0.25); color: #fbbf24; }

/* ── Cards ──────────────────────────────────────────────────── */
.card {
    background: linear-gradient(135deg, #1a1f35 0%, #161d30 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.4);
}

/* ── Status indicators ──────────────────────────────────────── */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
}
.status-green { background: #68d391; box-shadow: 0 0 8px rgba(104,211,145,0.6); }
.status-red { background: #fc8181; animation: none; }
.status-yellow { background: #fbbf24; animation: none; }

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.7; transform: scale(1.2); }
}

/* ── Processing steps ───────────────────────────────────────── */
.step-container {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 0.75rem;
}
.step-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    flex-shrink: 0;
    background: rgba(99, 179, 237, 0.1);
    border: 1px solid rgba(99, 179, 237, 0.3);
}
.step-done { background: rgba(104, 211, 145, 0.1); border-color: rgba(104, 211, 145, 0.3); }
.step-active { background: rgba(99, 179, 237, 0.15); border-color: rgba(99, 179, 237, 0.5); animation: pulse 1.5s infinite; }

/* ── Chat messages ──────────────────────────────────────────── */
.chat-user {
    background: linear-gradient(135deg, rgba(99, 179, 237, 0.12), rgba(99, 179, 237, 0.06));
    border: 1px solid rgba(99, 179, 237, 0.2);
    border-radius: 16px 16px 4px 16px;
    padding: 1rem 1.25rem;
    margin: 0.5rem 0;
    margin-left: 2rem;
    color: rgba(255,255,255,0.9);
    font-size: 0.95rem;
}
.chat-agent {
    background: linear-gradient(135deg, rgba(183, 148, 244, 0.08), rgba(183, 148, 244, 0.04));
    border: 1px solid rgba(183, 148, 244, 0.15);
    border-radius: 16px 16px 16px 4px;
    padding: 1rem 1.25rem;
    margin: 0.5rem 0;
    margin-right: 2rem;
    color: rgba(255,255,255,0.9);
    font-size: 0.95rem;
    line-height: 1.6;
}
.chat-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    margin-bottom: 0.4rem;
    text-transform: uppercase;
}
.label-user { color: #63b3ed; }
.label-agent { color: #b794f4; }

/* ── Agent reasoning steps ──────────────────────────────────── */
.reasoning-step {
    background: rgba(255,255,255,0.03);
    border-left: 2px solid rgba(251, 191, 36, 0.4);
    border-radius: 0 8px 8px 0;
    padding: 0.6rem 1rem;
    margin-bottom: 0.4rem;
    font-size: 0.83rem;
    color: rgba(255,255,255,0.6);
    font-family: 'JetBrains Mono', monospace;
}
.tool-name {
    color: #fbbf24;
    font-weight: 600;
}
.tool-input {
    color: #68d391;
}

/* ── Metadata grid ──────────────────────────────────────────── */
.meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
    margin: 1rem 0;
}
.meta-item {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 0.75rem;
    text-align: center;
}
.meta-value {
    font-size: 1.2rem;
    font-weight: 700;
    color: #63b3ed;
}
.meta-label {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.5);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 0.2rem;
}

/* ── Transcript viewer ───────────────────────────────────────── */
.transcript-seg {
    display: flex;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.ts-badge {
    background: rgba(99, 179, 237, 0.1);
    color: #63b3ed;
    padding: 0.15rem 0.5rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    white-space: nowrap;
    flex-shrink: 0;
    height: fit-content;
}
.ts-text {
    color: rgba(255,255,255,0.75);
    font-size: 0.88rem;
    line-height: 1.5;
}

/* ── Streamlit widget overrides ─────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #3182ce, #2b6cb0);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.5rem;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(49, 130, 206, 0.3);
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(49, 130, 206, 0.4);
    background: linear-gradient(135deg, #4299e1, #3182ce);
}
.stTextInput > div > input, .stTextArea > div > textarea {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: white !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > input:focus, .stTextArea > div > textarea:focus {
    border-color: rgba(99, 179, 237, 0.5) !important;
    box-shadow: 0 0 0 2px rgba(99, 179, 237, 0.1) !important;
}
.stFileUploader > div {
    background: rgba(255,255,255,0.03) !important;
    border: 2px dashed rgba(99, 179, 237, 0.25) !important;
    border-radius: 14px !important;
}
div[data-testid="metric-container"] {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1rem;
}
.stProgress > div > div {
    background: linear-gradient(90deg, #63b3ed, #b794f4) !important;
    border-radius: 10px !important;
}
.stSidebar > div {
    background: linear-gradient(180deg, #0d1526 0%, #0a1020 100%) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: rgba(255,255,255,0.5) !important;
    font-family: 'Inter', sans-serif !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #63b3ed !important;
    border-bottom-color: #63b3ed !important;
}
.stAlert {
    border-radius: 12px !important;
}
/* Divider */
hr { border-color: rgba(255,255,255,0.08) !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Session State ─────────────────────────────────────────────────────────────

def init_session_state():
    defaults = {
        "chat_history": [],
        "video_processed": False,
        "video_path": None,
        "video_metadata": None,
        "transcript_data": None,
        "frames_data": [],
        "video_id": None,
        "processing_error": None,
        "agent": None,
        "vector_store": None,
        "processor": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ── Cached singletons ─────────────────────────────────────────────────────────

@st.cache_resource
def get_agent(provider: str, model: str, api_key_hash: str) -> VideoAgent:
    return VideoAgent(provider=provider)


def get_current_agent() -> VideoAgent:
    api_key_hash = hashlib.md5(config.GEMINI_API_KEY.encode()).hexdigest() if config.GEMINI_API_KEY else "none"
    active_model = config.GEMINI_MODEL if config.LLM_PROVIDER.lower() == "gemini" else config.OLLAMA_MODEL
    agent = get_agent(config.LLM_PROVIDER, active_model, api_key_hash)

    # Attach video state if already processed in session
    if st.session_state.get("video_processed") and st.session_state.get("processor"):
        agent.configure_video(
            vector_store=get_vector_store(),
            video_processor=st.session_state.processor,
            video_metadata=st.session_state.video_metadata,
            transcript_data=st.session_state.transcript_data,
            frames_data=st.session_state.frames_data,
        )
    return agent


@st.cache_resource
def get_vector_store() -> VectorStore:
    return VectorStore()


# ── Helper: Check system dependencies ────────────────────────────────────────

def render_system_status():
    """Render system dependency check in sidebar."""
    ffmpeg_ok = check_ffmpeg()
    agent = get_current_agent()
    prov_ok, prov_msg = agent.check_provider_connection()

    st.sidebar.markdown("### 🔧 System Status")

    # FFmpeg
    dot = '<span class="status-dot status-green"></span>' if ffmpeg_ok else '<span class="status-dot status-red"></span>'
    label = "FFmpeg" if ffmpeg_ok else "FFmpeg ❌ (Required!)"
    st.sidebar.markdown(f"{dot} **{label}**", unsafe_allow_html=True)

    # Active Provider (Gemini / Ollama)
    dot2 = '<span class="status-dot status-green"></span>' if prov_ok else '<span class="status-dot status-red"></span>'
    st.sidebar.markdown(f"{dot2} {prov_msg}", unsafe_allow_html=True)

    # Langfuse
    lf_dot = '<span class="status-dot status-green"></span>' if config.LANGFUSE_ENABLED else '<span class="status-dot status-yellow"></span>'
    lf_label = "Langfuse: Active" if config.LANGFUSE_ENABLED else "Langfuse: Disabled"
    st.sidebar.markdown(f"{lf_dot} {lf_label}", unsafe_allow_html=True)

    if not ffmpeg_ok:
        st.sidebar.error("FFmpeg is required. Install it or install imageio-ffmpeg.")
    if not prov_ok:
        st.sidebar.warning(f"Provider notice: {prov_msg}")

    return ffmpeg_ok and prov_ok


# ── Video Processing Pipeline ─────────────────────────────────────────────────

def process_video(video_path: str, video_id: str):
    """
    Full pipeline:
    1. Extract metadata
    2. Extract audio
    3. Whisper transcription
    4. Frame extraction
    5. ChromaDB indexing
    """
    vs = get_vector_store()
    processor = VideoProcessor(video_path)

    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Step 1: Metadata
        status_text.markdown("📊 **Step 1/5** — Extracting video metadata...")
        metadata = processor.get_metadata()
        st.session_state.video_metadata = metadata
        progress_bar.progress(10)

        # Check if already indexed
        if vs.collection_exists(video_id):
            # Load existing transcript
            transcript_path = config.UPLOADS_DIR / f"{Path(video_path).stem}_transcript.json"
            if transcript_path.exists():
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)
                st.session_state.transcript_data = transcript_data
                progress_bar.progress(80)
                status_text.markdown("✅ **Using cached transcript** — Re-extracting frames...")
                frames_data = processor.extract_frames()
                st.session_state.frames_data = frames_data
                progress_bar.progress(100)
                status_text.markdown("✅ **Processing complete** (from cache)")
                _finalize_processing(processor, metadata, transcript_data, frames_data, video_id)
                return

        # Step 2: Audio extraction
        status_text.markdown("🎵 **Step 2/5** — Extracting audio with FFmpeg...")
        audio_path = processor.extract_audio()
        progress_bar.progress(25)

        # Step 3: Whisper transcription
        status_text.markdown(
            f"🎙️ **Step 3/5** — Transcribing with Whisper ({config.WHISPER_MODEL})..."
            " *(This may take a few minutes)*"
        )
        transcript_data = processor.transcribe(audio_path)
        st.session_state.transcript_data = transcript_data
        progress_bar.progress(60)

        # Step 4: Frame extraction
        status_text.markdown("🖼️ **Step 4/5** — Extracting video frames...")
        frames_data = processor.extract_frames()
        st.session_state.frames_data = frames_data
        progress_bar.progress(80)

        # Step 5: ChromaDB indexing
        status_text.markdown("🗄️ **Step 5/5** — Building vector index in ChromaDB...")
        chunk_count = vs.index_transcript(video_id, transcript_data)
        progress_bar.progress(100)

        status_text.markdown(
            f"✅ **Processing complete!** — {chunk_count} chunks indexed."
        )

        _finalize_processing(processor, metadata, transcript_data, frames_data, video_id)

    except Exception as e:
        progress_bar.progress(0)
        status_text.markdown(f"❌ **Error:** {str(e)}")
        st.session_state.processing_error = str(e)
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise


def _finalize_processing(processor, metadata, transcript_data, frames_data, video_id):
    """Set session state and configure agent after successful processing."""
    st.session_state.video_processed = True
    st.session_state.processor = processor

    vs = get_vector_store()
    agent = get_current_agent()
    agent.configure_video(
        vector_store=vs,
        video_processor=processor,
        video_metadata=metadata,
        transcript_data=transcript_data,
        frames_data=frames_data,
    )
    st.session_state.agent = agent


# ── Main UI ──────────────────────────────────────────────────────────────────

def main():
    # ── Hero Header
    st.markdown(
        """
<div class="hero-header">
    <h1 class="hero-title">🎬 AI Video Intelligence Agent</h1>
    <p class="hero-subtitle">Upload any video — ask anything. Powered by LLM + RAG + Multimodal Reasoning.</p>
    <div class="hero-badges">
        <span class="badge">🤖 LangChain ReAct Agent</span>
        <span class="badge badge-green">🔍 RAG + ChromaDB</span>
        <span class="badge badge-purple">🎙️ Whisper STT</span>
        <span class="badge badge-orange">👁️ Multimodal Vision</span>
        <span class="badge">✨ Gemini & Ollama LLM</span>
        <span class="badge badge-green">🛠️ 10 Agent Tools</span>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    # ── Sidebar
    with st.sidebar:
        st.markdown(
            """
<div style="text-align:center; margin-bottom: 1.5rem;">
    <div style="font-size: 2.5rem;">🎬</div>
    <div style="font-weight: 700; color: #63b3ed; font-size: 1rem;">Video Intelligence</div>
    <div style="color: rgba(255,255,255,0.4); font-size: 0.75rem;">AI Agent v1.0</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.divider()
        sys_ok = render_system_status()
        st.divider()

        # Settings
        st.markdown("### ⚙️ Settings")

        # Provider Selector
        prov_options = ["gemini", "ollama"]
        current_idx = 0 if config.LLM_PROVIDER.lower() == "gemini" else 1
        chosen_provider = st.selectbox(
            "LLM Provider",
            prov_options,
            index=current_idx,
            help="Select between Google Gemini cloud LLM or Ollama local models",
        )
        if chosen_provider != config.LLM_PROVIDER:
            config.LLM_PROVIDER = chosen_provider

        if config.LLM_PROVIDER.lower() == "gemini":
            gemini_key_val = st.text_input(
                "Gemini API Key",
                value=config.GEMINI_API_KEY,
                type="password",
                help="Google Gemini API Key (or set GEMINI_API_KEY in .env)",
            )
            if gemini_key_val != config.GEMINI_API_KEY:
                config.GEMINI_API_KEY = gemini_key_val
                os.environ["GEMINI_API_KEY"] = gemini_key_val
                os.environ["GOOGLE_API_KEY"] = gemini_key_val

            gemini_models = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-2.0-flash",
                "gemini-2.5-flash",
            ]
            g_idx = gemini_models.index(config.GEMINI_MODEL) if config.GEMINI_MODEL in gemini_models else 0
            config.GEMINI_MODEL = st.selectbox("Gemini Model", gemini_models, index=g_idx)
            config.GEMINI_VISION_MODEL = config.GEMINI_MODEL
        else:
            config.OLLAMA_MODEL = st.text_input("Ollama Model", value=config.OLLAMA_MODEL)
            config.OLLAMA_BASE_URL = st.text_input("Ollama Base URL", value=config.OLLAMA_BASE_URL)

        config.WHISPER_MODEL = st.selectbox(
            "Whisper Model",
            ["tiny", "base", "small", "medium"],
            index=["tiny", "base", "small", "medium"].index(config.WHISPER_MODEL),
        )
        config.FRAME_EXTRACTION_INTERVAL = st.slider(
            "Frame Interval (sec)", 10, 120, config.FRAME_EXTRACTION_INTERVAL
        )
        config.TOP_K_RESULTS = st.slider("RAG Top-K Results", 2, 10, config.TOP_K_RESULTS)

        st.divider()

        # Langfuse config (if not set)
        if not config.LANGFUSE_ENABLED:
            with st.expander("📊 Configure Langfuse (Optional)"):
                lf_secret = st.text_input("Secret Key", type="password")
                lf_public = st.text_input("Public Key")
                lf_host = st.text_input("Host", value=config.LANGFUSE_HOST)
                if st.button("Enable Langfuse") and lf_secret and lf_public:
                    os.environ["LANGFUSE_SECRET_KEY"] = lf_secret
                    os.environ["LANGFUSE_PUBLIC_KEY"] = lf_public
                    os.environ["LANGFUSE_HOST"] = lf_host
                    st.success("Langfuse enabled! Restart required for full effect.")

        st.divider()
        if st.session_state.video_processed:
            if st.button("🗑️ Clear & New Video"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        st.markdown(
            """
<div style="margin-top: auto; text-align:center; color: rgba(255,255,255,0.25); font-size: 0.7rem;">
    Built with ❤️ using LangChain + Gemini / Ollama + Whisper
</div>
""",
            unsafe_allow_html=True,
        )

    # ── Main Tabs
    tab_upload, tab_chat, tab_transcript, tab_frames = st.tabs(
        ["📤 Upload & Process", "💬 Chat with Agent", "📄 Transcript", "🖼️ Frames"]
    )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1: Upload & Process
    # ══════════════════════════════════════════════════════════════════════
    with tab_upload:
        col_upload, col_meta = st.columns([1, 1], gap="large")

        with col_upload:
            st.markdown("### 📤 Upload Video")
            st.markdown(
                '<p style="color:rgba(255,255,255,0.5); font-size:0.88rem;">'
                "Supported: MP4, MOV, AVI, MKV, WebM (max 500MB)</p>",
                unsafe_allow_html=True,
            )

            uploaded = st.file_uploader(
                "Drop your video here or click to browse",
                type=config.SUPPORTED_VIDEO_FORMATS,
                label_visibility="collapsed",
            )

            if uploaded:
                file_size = len(uploaded.getbuffer()) / (1024 * 1024)
                if file_size > config.MAX_VIDEO_SIZE_MB:
                    st.error(
                        f"File too large ({file_size:.1f} MB). Max is {config.MAX_VIDEO_SIZE_MB} MB."
                    )
                else:
                    # Show video preview immediately
                    st.video(uploaded)
                    st.markdown(
                        f'<p style="color:rgba(255,255,255,0.4); font-size:0.8rem; text-align:center;">'
                        f"📁 {uploaded.name} ({file_size:.1f} MB)</p>",
                        unsafe_allow_html=True,
                    )

                    if not st.session_state.video_processed:
                        if not sys_ok:
                            st.warning(
                                "⚠️ Fix system dependencies (FFmpeg + Ollama) before processing."
                            )
                        else:
                            if st.button(
                                "🚀 Start AI Processing",
                                use_container_width=True,
                                key="process_btn",
                            ):
                                with st.spinner("Saving video..."):
                                    video_path = save_uploaded_video(uploaded)
                                    video_id = get_video_id(video_path)
                                    st.session_state.video_path = video_path
                                    st.session_state.video_id = video_id

                                st.markdown("---")
                                st.markdown("#### 🔄 Processing Pipeline")
                                try:
                                    process_video(video_path, video_id)
                                    st.success(
                                        "✅ Video processed successfully! Switch to the **Chat** tab."
                                    )
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Processing failed: {e}")
                    else:
                        st.success("✅ Video already processed! Ask questions in the **Chat** tab.")

        with col_meta:
            if st.session_state.video_metadata:
                m = st.session_state.video_metadata
                st.markdown("### 📊 Video Metadata")
                st.markdown(
                    f"""
<div class="meta-grid">
    <div class="meta-item">
        <div class="meta-value">{m.get('duration_formatted','—')}</div>
        <div class="meta-label">Duration</div>
    </div>
    <div class="meta-item">
        <div class="meta-value">{m.get('fps', 0):.0f}</div>
        <div class="meta-label">FPS</div>
    </div>
    <div class="meta-item">
        <div class="meta-value">{m.get('resolution','—')}</div>
        <div class="meta-label">Resolution</div>
    </div>
    <div class="meta-item">
        <div class="meta-value">{m.get('size_mb','—')}</div>
        <div class="meta-label">Size (MB)</div>
    </div>
    <div class="meta-item">
        <div class="meta-value">{m.get('format','—')}</div>
        <div class="meta-label">Format</div>
    </div>
    <div class="meta-item">
        <div class="meta-value">{m.get('total_frames','—')}</div>
        <div class="meta-label">Frames</div>
    </div>
</div>
""",
                    unsafe_allow_html=True,
                )

                # Processing stats
                if st.session_state.transcript_data:
                    td = st.session_state.transcript_data
                    segs = td.get("segments", [])
                    vs = get_vector_store()
                    st.markdown("#### 🧠 AI Processing Stats")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Transcript Segments", len(segs))
                    c2.metric("Language", td.get("language", "?").upper())
                    c3.metric("Vector Chunks", vs.get_collection_count())

                # Quick actions
                st.markdown("#### 💡 Quick Questions")
                quick_questions = [
                    "What is this video about?",
                    "Summarize the key points",
                    "What are the main topics?",
                    "Generate 5 MCQs from this video",
                ]
                for q in quick_questions:
                    if st.button(f"▶ {q}", key=f"quick_{q}"):
                        st.session_state.chat_history.append(
                            {"role": "user", "content": q}
                        )
                        st.rerun()
            else:
                # Empty state
                st.markdown(
                    """
<div style="
    text-align: center;
    padding: 3rem;
    color: rgba(255,255,255,0.3);
    border: 1px dashed rgba(255,255,255,0.1);
    border-radius: 16px;
    margin-top: 2rem;
">
    <div style="font-size: 3rem; margin-bottom: 1rem;">📹</div>
    <div style="font-size: 1rem; font-weight: 500;">No video uploaded yet</div>
    <div style="font-size: 0.82rem; margin-top: 0.5rem;">Upload a video to see metadata and start chatting</div>
</div>
""",
                    unsafe_allow_html=True,
                )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2: Chat Interface
    # ══════════════════════════════════════════════════════════════════════
    with tab_chat:
        if not st.session_state.video_processed:
            st.markdown(
                """
<div style="text-align:center; padding: 4rem 2rem; color: rgba(255,255,255,0.4);">
    <div style="font-size: 3rem; margin-bottom: 1rem;">💬</div>
    <div style="font-size: 1.1rem; font-weight: 600;">No video processed yet</div>
    <div style="font-size: 0.88rem; margin-top: 0.5rem;">Upload and process a video first to start chatting with the AI agent.</div>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            # Chat layout
            chat_col, info_col = st.columns([2, 1], gap="large")

            with chat_col:
                st.markdown("### 💬 Chat with AI Agent")

                # Suggested questions
                with st.expander("💡 Suggested Questions", expanded=False):
                    suggestions = [
                        "What is this video about?",
                        "Summarize the video in detail",
                        "What are the key takeaways?",
                        "Create 10 MCQs from this video",
                        "What is shown at 00:30?",
                        "When is [topic] explained? (replace with actual topic)",
                        "What does the speaker say about [topic]?",
                        "Analyze the scene between 00:10 and 00:50",
                    ]
                    cols = st.columns(2)
                    for i, s in enumerate(suggestions):
                        if cols[i % 2].button(s, key=f"sug_{i}"):
                            st.session_state.chat_history.append(
                                {"role": "user", "content": s}
                            )

                # Chat history display
                chat_container = st.container()
                with chat_container:
                    for msg in st.session_state.chat_history:
                        if msg["role"] == "user":
                            st.markdown(
                                f"""
<div class="chat-user">
    <div class="chat-label label-user">👤 You</div>
    {msg['content']}
</div>
""",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f"""
<div class="chat-agent">
    <div class="chat-label label-agent">🤖 Agent</div>
    {msg['content'].replace(chr(10), '<br>')}
</div>
""",
                                unsafe_allow_html=True,
                            )

                            # Show reasoning steps if available
                            if msg.get("steps"):
                                with st.expander(
                                    f"🔍 Agent Reasoning ({len(msg['steps'])} steps)",
                                    expanded=False,
                                ):
                                    for step in msg["steps"]:
                                        st.markdown(
                                            f"""
<div class="reasoning-step">
    🔧 <span class="tool-name">{step['tool']}</span>
    <span style="color:rgba(255,255,255,0.4);"> → </span>
    <span class="tool-input">{str(step['input'])[:100]}</span>
</div>
""",
                                            unsafe_allow_html=True,
                                        )
                                        with st.expander("Observation", expanded=False):
                                            st.text(step["observation"][:800])

                # Check for pending question (from quick actions)
                pending_question = None
                if (
                    st.session_state.chat_history
                    and st.session_state.chat_history[-1]["role"] == "user"
                ):
                    last = st.session_state.chat_history[-1]
                    if "answered" not in last:
                        pending_question = last["content"]

                # Input box
                with st.form("chat_form", clear_on_submit=True):
                    user_input = st.text_input(
                        "Ask anything about the video...",
                        placeholder="e.g., What did the speaker explain about machine learning?",
                        label_visibility="collapsed",
                        key="user_input",
                    )
                    col_send, col_clear = st.columns([3, 1])
                    submitted = col_send.form_submit_button(
                        "🚀 Ask Agent", use_container_width=True
                    )
                    cleared = col_clear.form_submit_button("🗑️ Clear", use_container_width=True)

                if cleared:
                    st.session_state.chat_history = []
                    st.rerun()

                # Process question
                question_to_answer = None
                if submitted and user_input.strip():
                    st.session_state.chat_history.append(
                        {"role": "user", "content": user_input.strip(), "answered": True}
                    )
                    question_to_answer = user_input.strip()
                elif pending_question:
                    st.session_state.chat_history[-1]["answered"] = True
                    question_to_answer = pending_question

                if question_to_answer:
                    agent = get_current_agent()
                    with st.spinner("🤖 Agent is thinking... (using tools & reasoning)"):
                        result = agent.run(question_to_answer)

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": result["answer"],
                            "steps": result.get("steps", []),
                            "tools_used": result.get("tools_used", []),
                        }
                    )
                    st.rerun()

            with info_col:
                st.markdown("### 🧠 Agent Info")
                active_model = config.GEMINI_MODEL if config.LLM_PROVIDER.lower() == "gemini" else config.OLLAMA_MODEL
                active_prov = "Gemini" if config.LLM_PROVIDER.lower() == "gemini" else "Ollama"
                st.markdown(
                    f"""
<div class="card">
    <div style="color: rgba(255,255,255,0.5); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px;">Provider & Model</div>
    <div style="color: #63b3ed; font-weight: 600; margin-top: 0.3rem;">{active_prov}: {active_model}</div>
    <div style="color: rgba(255,255,255,0.5); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 0.8rem;">Mode</div>
    <div style="color: #68d391; font-weight: 600; margin-top: 0.3rem;">ReAct Agent</div>
    <div style="color: rgba(255,255,255,0.5); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 0.8rem;">Tools Available</div>
    <div style="color: #b794f4; font-weight: 600; margin-top: 0.3rem;">10 Tools</div>
</div>
""",
                    unsafe_allow_html=True,
                )

                st.markdown("#### 🛠️ Available Tools")
                tools_info = [
                    ("🔍", "search_transcript", "RAG semantic search"),
                    ("⏱️", "get_transcript_at_timestamp", "Timestamp lookup"),
                    ("📊", "get_video_metadata", "Video metadata"),
                    ("📄", "get_full_transcript", "Full transcript"),
                    ("👁️", "analyze_video_frame", "Visual frame analysis"),
                    ("📋", "summarize_video", "Summarization"),
                    ("📝", "generate_quiz", "MCQ generation"),
                    ("🔎", "find_topic_timestamp", "Topic finder"),
                    ("📌", "extract_key_topics", "Key topics"),
                    ("🎬", "analyze_frame_range", "Scene range analysis"),
                ]
                for icon, name, desc in tools_info:
                    st.markdown(
                        f"""
<div style="
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.6rem;
    border-radius: 8px;
    background: rgba(255,255,255,0.03);
    margin-bottom: 0.3rem;
    border: 1px solid rgba(255,255,255,0.05);
">
    <span>{icon}</span>
    <div>
        <div style="font-size: 0.78rem; font-weight: 600; color: rgba(255,255,255,0.8);">{name}</div>
        <div style="font-size: 0.7rem; color: rgba(255,255,255,0.4);">{desc}</div>
    </div>
</div>
""",
                        unsafe_allow_html=True,
                    )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3: Transcript Viewer
    # ══════════════════════════════════════════════════════════════════════
    with tab_transcript:
        if not st.session_state.transcript_data:
            st.info("No transcript available. Upload and process a video first.")
        else:
            td = st.session_state.transcript_data
            segments = td.get("segments", [])

            col_t1, col_t2 = st.columns([2, 1])

            with col_t1:
                st.markdown("### 📄 Video Transcript")
                st.markdown(
                    f'<p style="color:rgba(255,255,255,0.5); font-size:0.85rem;">'
                    f"Language: **{td.get('language','en').upper()}** | "
                    f"{len(segments)} segments | "
                    f"{len(td.get('full_text','').split())} words</p>",
                    unsafe_allow_html=True,
                )

                # Search filter
                search_filter = st.text_input(
                    "🔍 Filter transcript",
                    placeholder="Search words in transcript...",
                    key="transcript_search",
                )

                # Display segments
                filtered = segments
                if search_filter:
                    filtered = [
                        s
                        for s in segments
                        if search_filter.lower() in s["text"].lower()
                    ]
                    st.caption(f"Found {len(filtered)} matching segments")

                for seg in filtered:
                    text = seg["text"]
                    if search_filter:
                        # Highlight search term
                        text = text.replace(
                            search_filter,
                            f"<mark style='background:rgba(99,179,237,0.3); border-radius:3px;'>"
                            f"{search_filter}</mark>",
                        )
                    st.markdown(
                        f"""
<div class="transcript-seg">
    <span class="ts-badge">{seg['start_formatted']}</span>
    <span class="ts-text">{text}</span>
</div>
""",
                        unsafe_allow_html=True,
                    )

            with col_t2:
                st.markdown("### 📊 Transcript Stats")
                words = len(td.get("full_text", "").split())
                st.metric("Total Words", f"{words:,}")
                st.metric("Segments", len(segments))
                st.metric("Language", td.get("language", "en").upper())

                if segments:
                    dur = segments[-1]["end"] - segments[0]["start"]
                    wpm = int(words / (dur / 60)) if dur > 0 else 0
                    st.metric("Speech Rate", f"~{wpm} WPM")

                st.markdown("---")
                st.download_button(
                    "⬇️ Download Transcript (JSON)",
                    data=json.dumps(td, indent=2, ensure_ascii=False),
                    file_name="transcript.json",
                    mime="application/json",
                )
                st.download_button(
                    "⬇️ Download Transcript (TXT)",
                    data=td.get("full_text", ""),
                    file_name="transcript.txt",
                    mime="text/plain",
                )

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4: Frame Viewer
    # ══════════════════════════════════════════════════════════════════════
    with tab_frames:
        if not st.session_state.frames_data:
            st.info("No frames extracted. Upload and process a video first.")
        else:
            frames = st.session_state.frames_data
            st.markdown(f"### 🖼️ Extracted Frames ({len(frames)} total)")

            # Frame filter by timestamp
            max_ts = frames[-1]["timestamp_sec"] if frames else 100
            ts_range = st.slider(
                "Filter by timestamp range (seconds)",
                0.0, float(max_ts), (0.0, float(max_ts)),
                key="frame_ts_range",
            )
            visible = [
                f for f in frames
                if ts_range[0] <= f["timestamp_sec"] <= ts_range[1]
            ]
            st.caption(f"Showing {len(visible)} frames")

            # Grid layout (4 columns)
            cols = st.columns(4)
            for i, fr in enumerate(visible):
                with cols[i % 4]:
                    frame_path = Path(fr["frame_path"])
                    if frame_path.exists():
                        st.image(
                            str(frame_path),
                            caption=f"⏱ {fr['timestamp_formatted']}",
                            use_container_width=True,
                        )
                        # Visual analysis button
                        if st.button(
                            "👁️ Analyze",
                            key=f"analyze_{i}",
                            help=f"Visually analyze frame at {fr['timestamp_formatted']}",
                        ):
                            agent = get_current_agent()
                            with st.spinner(f"Analyzing frame at {fr['timestamp_formatted']}..."):
                                result = agent.run(
                                    f"What is shown at timestamp {fr['timestamp_formatted']}?"
                                )
                            st.info(result["answer"])
                    else:
                        st.warning(f"Frame missing: {frame_path.name}")


if __name__ == "__main__":
    main()
