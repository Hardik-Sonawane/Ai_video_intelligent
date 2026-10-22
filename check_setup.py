r"""
Quick setup verification script for AI Video Intelligence Agent.
Run: venv\Scripts\python.exe check_setup.py
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check(label: str, fn):
    try:
        fn()
        print(f"  [OK] {label}")
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("  AI Video Intelligence Agent -- Setup Verification")
    print("=" * 60 + "\n")

    results = []

    # Python version
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    print(f"  {'[OK]' if ok else '[FAIL]'} Python {v.major}.{v.minor}.{v.micro} {'(OK)' if ok else '(Need 3.10+)'}")
    results.append(ok)

    # ── Core packages ────────────────────────────────────────────
    print("\n[*] Core Python packages:")
    results.append(check("streamlit", lambda: __import__("streamlit")))
    results.append(check("langchain", lambda: __import__("langchain")))
    results.append(check("langchain_core", lambda: __import__("langchain_core")))
    results.append(check("langchain_community", lambda: __import__("langchain_community")))
    results.append(check("langchain_text_splitters", lambda: __import__("langchain_text_splitters")))

    # ── LLM providers ────────────────────────────────────────────
    print("\n[*] LLM Provider packages:")
    results.append(check("langchain_google_genai", lambda: __import__("langchain_google_genai")))
    results.append(check("google.genai (new SDK)", lambda: __import__("google.genai")))
    results.append(check("langchain_ollama", lambda: __import__("langchain_ollama")))

    # ── AI / ML packages ─────────────────────────────────────────
    print("\n[*] AI/ML packages:")
    results.append(check("chromadb", lambda: __import__("chromadb")))
    results.append(check("sentence_transformers", lambda: __import__("sentence_transformers")))
    results.append(check("whisper (openai-whisper)", lambda: __import__("whisper")))

    # ── Video/Image processing ───────────────────────────────────
    print("\n[*] Video/Image processing:")
    results.append(check("cv2 (OpenCV)", lambda: __import__("cv2")))
    results.append(check("PIL (Pillow)", lambda: __import__("PIL")))
    results.append(check("numpy", lambda: __import__("numpy")))

    # ── Utilities ────────────────────────────────────────────────
    print("\n[*] Utilities:")
    results.append(check("python-dotenv", lambda: __import__("dotenv")))
    results.append(check("requests", lambda: __import__("requests")))
    results.append(check("soundfile", lambda: __import__("soundfile")))

    # ── FFmpeg check ─────────────────────────────────────────────
    print("\n[*] System tools:")
    try:
        from src.utils.helpers import get_ffmpeg_path
        ffmpeg_bin = get_ffmpeg_path()
        ffmpeg_ok = ffmpeg_bin is not None
        if ffmpeg_ok:
            print(f"  [OK] FFmpeg (found: {ffmpeg_bin})")
        else:
            # Try imageio-ffmpeg
            try:
                import imageio_ffmpeg
                ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
                ffmpeg_ok = True
                print(f"  [OK] FFmpeg via imageio-ffmpeg: {ffmpeg_bin}")
            except Exception:
                print("  [FAIL] FFmpeg NOT FOUND")
                print("     -> Install: pip install imageio-ffmpeg")
                print("     -> Or download: https://ffmpeg.org/download.html")
    except Exception as e:
        import shutil
        ffmpeg_bin = shutil.which("ffmpeg")
        ffmpeg_ok = ffmpeg_bin is not None
        print(f"  {'[OK]' if ffmpeg_ok else '[FAIL]'} FFmpeg {'(found in PATH)' if ffmpeg_ok else '(NOT FOUND)'}")
    results.append(ffmpeg_ok)

    # ── Load config ──────────────────────────────────────────────
    print("\n[*] Application config:")
    try:
        from src.config import config
        print(f"  [OK] Config loaded")
        print(f"       LLM Provider : {config.LLM_PROVIDER.upper()}")
        print(f"       Whisper Model: {config.WHISPER_MODEL}")
        print(f"       Gemini Model : {config.GEMINI_MODEL}")
        print(f"       Ollama Model : {config.OLLAMA_MODEL}")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] Config error: {e}")
        results.append(False)
        config = None

    # ── LLM Provider check ───────────────────────────────────────
    if config is not None:
        print(f"\n[*] LLM Provider: {config.LLM_PROVIDER.upper()}")

        # Gemini check
        if config.LLM_PROVIDER.lower() == "gemini" or config.GEMINI_API_KEY:
            print("\n[*] Google Gemini:")
            if config.GEMINI_API_KEY and config.GEMINI_API_KEY != "your_gemini_api_key_here":
                try:
                    from google import genai
                    client = genai.Client(api_key=config.GEMINI_API_KEY)
                    list(client.models.list(config={"page_size": 1}))
                    print(f"  [OK] Gemini API connected | Model: {config.GEMINI_MODEL}")
                    results.append(True)
                except Exception as e:
                    print(f"  [WARN] Gemini connection check: {e}")
                    results.append(True)  # Don't fail - key may still work
            else:
                print("  [WARN] GEMINI_API_KEY not set in .env")
                print("     -> Get your key at: https://aistudio.google.com/app/apikey")
                print("     -> Or enter it in the sidebar after starting the app")
                results.append(True)

        # Ollama check
        if config.LLM_PROVIDER.lower() == "ollama" or not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "your_gemini_api_key_here":
            print("\n[*] Ollama (Local LLM):")
            import requests as req
            try:
                r = req.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3)
                models = [m["name"] for m in r.json().get("models", [])]
                print(f"  [OK] Ollama running | {len(models)} model(s) available")

                llama_ok = any(config.OLLAMA_MODEL.split(":")[0] in m for m in models)
                llava_ok = any("llava" in m for m in models)

                print(f"  {'[OK]' if llama_ok else '[WARN]'} {config.OLLAMA_MODEL} "
                      f"{'(ready)' if llama_ok else '(run: ollama pull ' + config.OLLAMA_MODEL + ')'}")
                print(f"  {'[OK]' if llava_ok else '[WARN]'} llava (vision model) "
                      f"{'(ready)' if llava_ok else '(run: ollama pull llava) -- needed for visual analysis'}")
                results.append(True)
            except Exception as e:
                if config.LLM_PROVIDER.lower() == "ollama":
                    print(f"  [FAIL] Ollama not running: {e}")
                    print("     -> Start Ollama: https://ollama.ai")
                    results.append(False)
                else:
                    print(f"  [INFO] Ollama not running (optional when using Gemini): {e}")
                    results.append(True)

    # ── Module import check ──────────────────────────────────────
    print("\n[*] Internal modules:")
    try:
        sys.path.insert(0, str(os.getcwd()))
        from src.processing.video_processor import VideoProcessor
        from src.processing.vector_store import VectorStore
        from src.agent.video_agent import VideoAgent
        from src.tools.agent_tools import ALL_TOOLS
        print(f"  [OK] VideoProcessor, VectorStore, VideoAgent loaded")
        print(f"  [OK] Agent tools: {len(ALL_TOOLS)} tools registered")
        results.append(True)
    except Exception as e:
        print(f"  [FAIL] Module import error: {e}")
        results.append(False)

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"[OK] All {passed}/{total} checks passed! Ready to run.\n")
        print("  Start the app with:")
        print("    python run.py")
        print("  Or directly:")
        print("    venv\\Scripts\\streamlit.exe run app.py")
        print("\n  Then open: http://localhost:8501\n")
    else:
        failed = total - passed
        print(f"[WARN] {passed}/{total} checks passed ({failed} failed). Fix issues above.\n")
        print("  See README.md for setup instructions.")
        if not ffmpeg_ok:
            print("\n  CRITICAL: FFmpeg is required!")
            print("    pip install imageio-ffmpeg")


if __name__ == "__main__":
    main()
