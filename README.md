# AI Video Intelligence Agent

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red)
![LangChain](https://img.shields.io/badge/LangChain-0.2+-green)
![Ollama](https://img.shields.io/badge/Ollama-LLM-orange)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-purple)
![Whisper](https://img.shields.io/badge/Whisper-STT-yellow)

**A real Agentic AI application that understands videos using LLM + RAG + Tool Calling + Multimodal Reasoning.**

</div>

---

## 🌟 Overview

Upload any video and ask natural language questions. The AI agent automatically:
- Transcribes the audio using **Whisper**
- Stores the transcript in **ChromaDB** as vector embeddings
- Uses a **LangChain ReAct agent** backed by **Ollama (llama3.1:8b)** to answer questions
- Extracts frames and uses **llava** for visual questions
- Traces agent decisions with **Langfuse**

## 🏗️ Architecture

```
Video Upload
    ↓
VideoProcessor (OpenCV + FFmpeg)
    ├── Extract Audio (FFmpeg → WAV)
    ├── Whisper STT → Timestamped Transcript
    └── Frame Extraction (OpenCV)
         ↓
VectorStore (ChromaDB + sentence-transformers)
    ← Index transcript chunks with timestamps
         ↓
VideoAgent (LangChain ReAct + Ollama llama3.1:8b)
    ├── Tool: search_transcript (RAG)
    ├── Tool: get_transcript_at_timestamp
    ├── Tool: get_video_metadata
    ├── Tool: get_full_transcript
    ├── Tool: analyze_video_frame (llava)
    ├── Tool: summarize_video
    ├── Tool: generate_quiz
    ├── Tool: find_topic_timestamp
    └── Tool: extract_key_topics
         ↓
Streamlit Dashboard
    ├── Upload & Process Tab
    ├── Chat Interface Tab
    ├── Transcript Viewer Tab
    └── Frame Browser Tab
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**
2. **FFmpeg** — [Download](https://ffmpeg.org/download.html) and add to PATH
3. **Ollama** — [Download](https://ollama.ai) and run:
   ```bash
   ollama pull llama3.1:8b
   ollama pull llava         # For visual analysis
   ```

### Installation

```bash
# 1. Clone / navigate to project
cd project_ai_iv

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env if needed (Langfuse keys, model names, etc.)

# 5. Run the app
python run.py
# OR
streamlit run app.py
```

Open: **http://localhost:8501**

---

## 🛠️ Features

### 1. Video Processing Pipeline
- Supports MP4, MOV, AVI, MKV, WebM
- FFmpeg-based audio extraction
- Whisper speech-to-text with word-level timestamps
- Automatic frame extraction at configurable intervals
- ChromaDB vector indexing with embedding caching

### 2. AI Agent (LangChain ReAct)
The agent uses **Thought → Action → Observation → Final Answer** reasoning to pick the right tool for each question.

| Tool | Purpose |
|------|---------|
| `search_transcript` | Semantic RAG search over transcript |
| `get_transcript_at_timestamp` | Look up transcript at exact time |
| `get_video_metadata` | Duration, FPS, resolution, size |
| `get_full_transcript` | Complete transcript for summarization |
| `analyze_video_frame` | Visual analysis via llava |
| `summarize_video` | Comprehensive video summary |
| `generate_quiz` | Generate MCQ questions |
| `find_topic_timestamp` | When is a topic discussed? |
| `extract_key_topics` | Key moments from the video |

### 3. Multimodal Analysis
- **Text questions** → Transcript + RAG search
- **Visual questions** → Frame extraction + llava vision model
- **Timestamp questions** → Direct transcript lookup

### 4. Chat Interface
- Full conversation history
- Agent reasoning steps visible (expandable)
- Tools used per response shown
- Quick question buttons
- Download transcript (JSON/TXT)

### 5. Langfuse Tracing (Optional)
Configure in `.env` or via the sidebar UI to trace all agent decisions on [Langfuse Cloud](https://cloud.langfuse.com).

---

## ⚙️ Configuration

All settings are in `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_VISION_MODEL=llava:latest
WHISPER_MODEL=base               # tiny/base/small/medium/large
FRAME_EXTRACTION_INTERVAL=30     # seconds between frames
CHUNK_SIZE=500                   # transcript chunk size
TOP_K_RESULTS=5                  # RAG results to return
MAX_VIDEO_SIZE_MB=500

# Optional Langfuse
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 📁 Project Structure

```
project_ai_iv/
├── app.py                          # Main Streamlit application
├── run.py                          # Convenience launcher
├── requirements.txt
├── .env                            # Environment config
├── .streamlit/
│   └── config.toml                 # Streamlit theme
├── src/
│   ├── config.py                   # Central config
│   ├── processing/
│   │   ├── video_processor.py      # FFmpeg + Whisper + OpenCV
│   │   └── vector_store.py         # ChromaDB + embeddings
│   ├── agent/
│   │   └── video_agent.py          # LangChain ReAct agent
│   ├── tools/
│   │   └── agent_tools.py          # All 9 agent tools
│   └── utils/
│       └── helpers.py              # Utility functions
├── uploads/                        # Uploaded videos + transcripts
├── frames/                         # Extracted frames
├── chroma_db/                      # Vector store data
└── logs/                           # Application logs
```

---

## 🧪 Example Interactions

| Question | Agent Behavior |
|----------|---------------|
| "What is this video about?" | `summarize_video` → comprehensive summary |
| "Summarize the video" | `get_full_transcript` → LLM summary |
| "When is classification explained?" | `find_topic_timestamp` → timestamps |
| "What did the speaker say about neural networks?" | `search_transcript` → RAG retrieval + timestamps |
| "What is shown at 05:30?" | `analyze_video_frame` → llava visual analysis |
| "Create 10 MCQs" | `generate_quiz` → formatted quiz |
| "How long is the video?" | `get_video_metadata` → duration |
| "What happens at 02:15?" | `get_transcript_at_timestamp` → text at time |

---

## 🐳 Docker (Optional)

```bash
docker build -t video-agent .
docker run -p 8501:8501 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  video-agent
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| FFmpeg not found | Install FFmpeg and add to PATH |
| Ollama connection failed | Start Ollama: `ollama serve` |
| Model not found | `ollama pull llama3.1:8b` |
| Out of memory | Use `tiny` Whisper model; smaller Ollama model |
| Slow transcription | Use `tiny` or `base` Whisper model |
| Visual analysis fails | `ollama pull llava` |

---

## 📚 Tech Stack

| Component | Technology |
|-----------|-----------|
| UI | Streamlit 1.35+ |
| Agent Framework | LangChain ReAct |
| LLM | Ollama (llama3.1:8b) |
| Vision LLM | Ollama (llava) |
| Speech-to-Text | OpenAI Whisper |
| Vector Store | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Video Processing | OpenCV + FFmpeg |
| Observability | Langfuse |

---

<div align="center">
Built with ❤️ | LLM + RAG + Tool Calling + Multimodal Video Understanding
</div>
