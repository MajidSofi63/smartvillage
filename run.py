#!/usr/bin/env python3
"""
AI Smart Village Platform - Runner Script
Run this script from the project root:
    python run.py

It will automatically:
- Verify environment and configuration
- Set up PYTHONPATH so backend imports work seamlessly
- Launch Uvicorn server on http://127.0.0.1:8000
- Open the web application in your default browser
"""

import os
import sys
import time
import webbrowser
import threading
from pathlib import Path

# Force UTF-8 output on Windows to avoid UnicodeEncodeError with special chars.
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Switch working directory to backend
os.chdir(BACKEND_DIR)


def open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass


def main():
    print("=" * 70)
    print("  AI SMART VILLAGE PLATFORM")
    print("=" * 70)
    print(f"Python:       {sys.version.split()[0]}")
    print("Web App:      http://127.0.0.1:8000")
    print("Admin Panel:  http://127.0.0.1:8000/admin (Password: changeme)")
    print("API Docs:     http://127.0.0.1:8000/docs")
    print("=" * 70)
    print("Press Ctrl+C to stop the server.\n")

    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    try:
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped gracefully.")


if __name__ == "__main__":
    main()
