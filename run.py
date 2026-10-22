"""
Startup script for AI Video Intelligence Agent.
Runs the Streamlit app with appropriate settings.
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    print("\n" + "=" * 60)
    print("  🎬 AI Video Intelligence Agent")
    print("  LLM + RAG + Tool Calling + Multimodal Video Understanding")
    print("=" * 60 + "\n")

    # Ensure required directories exist
    for d in ["uploads", "frames", "logs", "chroma_db"]:
        (ROOT / d).mkdir(parents=True, exist_ok=True)

    # Find streamlit binary
    venv_streamlit = ROOT / "venv" / "Scripts" / "streamlit.exe"
    if venv_streamlit.exists():
        streamlit_cmd = str(venv_streamlit)
    else:
        streamlit_cmd = "streamlit"

    # Build the command
    cmd = [
        streamlit_cmd,
        "run",
        str(ROOT / "app.py"),
        "--server.port=8501",
        "--server.address=localhost",
        "--browser.gatherUsageStats=false",
        "--server.maxUploadSize=500",
        "--server.enableCORS=false",
    ]

    print(f"Starting app at: http://localhost:8501")
    print("Press Ctrl+C to stop.\n")

    try:
        subprocess.run(cmd, cwd=str(ROOT))
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
    except FileNotFoundError:
        print(
            f"ERROR: Could not find streamlit. Make sure your virtual environment is activated.\n"
            f"Try: venv\\Scripts\\activate  (Windows)\n"
            f"Then: pip install -r requirements.txt\n"
            f"Then: python run.py"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
