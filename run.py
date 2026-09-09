#!/usr/bin/env python3
"""
Smart Attendance System - All-in-One Launcher:
Starts the FastAPI backend (if not already running via Docker),
opens the Dashboard in your default browser, and launches the Computer Vision
tracking pipeline with physical webcam access in a single command.
"""
import sys
import time
import signal
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

PYTHON_EXEC = PROJECT_ROOT / ".venv" / "bin" / "python"
if not PYTHON_EXEC.exists():
    PYTHON_EXEC = Path(sys.executable)

def check_backend_health(url: str = "http://localhost:8000/health", max_retries: int = 20) -> bool:
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=" * 60)
    print("    Smart Attendance System - All-in-One Launcher")
    print("=" * 60)

    # 1. Check if backend is already online (e.g. running inside Docker)
    already_online = False
    try:
        with urllib.request.urlopen("http://localhost:8000/health", timeout=1.0) as resp:
            if resp.status == 200:
                already_online = True
    except Exception:
        pass

    backend_proc = None
    if already_online:
        print("[1/3] Backend server is already online on http://localhost:8000 (Docker or background service)!")
    else:
        print("[1/3] Starting backend server on http://localhost:8000...")
        backend_proc = subprocess.Popen(
            [
                str(PYTHON_EXEC),
                "-m",
                "uvicorn",
                "app.main:app",
                "--app-dir",
                "backend",
                "--port",
                "8000"
            ],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    def cleanup(signum=None, frame=None):
        if backend_proc is not None:
            print("\n[Shutdown] Stopping local backend server...")
            try:
                backend_proc.terminate()
                backend_proc.wait(timeout=3.0)
            except Exception:
                backend_proc.kill()
        print("[Shutdown] Vision and launcher stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 2. Wait for backend to be ready if we launched it
    if not already_online:
        print("[2/3] Waiting for backend to become ready...")
        if not check_backend_health():
            print("[ERROR] Backend server failed to start within timeout.")
            cleanup()
        print("[OK] Backend server is online!")
    else:
        print("[2/3] Verified backend connectivity at http://localhost:8000")

    # Open Dashboard in default browser
    try:
        print("     Opening Instructor Dashboard in default browser...")
        webbrowser.open("http://localhost:8000/dashboard")
    except Exception as e:
        print(f"     Note: Could not open browser automatically: {e}")

    # 3. Start Vision Tracking in foreground (Standby mode)
    print("[3/3] Starting Vision Tracking with webcam (Standby mode)...")
    print("     (Press 'q' in the video window or Ctrl+C in terminal to stop)")
    print("-" * 60)

    vision_cmd = [
        str(PYTHON_EXEC),
        "vision/main.py",
        "--source",
        "0",
        "--group",
        "Group A",
        "--backend-url",
        "http://localhost:8000"
    ] + sys.argv[1:]

    try:
        subprocess.run(vision_cmd, cwd=str(PROJECT_ROOT))
    finally:
        cleanup()

if __name__ == "__main__":
    main()
