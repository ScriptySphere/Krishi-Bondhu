"""Launch Crop Shift web app:  python web/run.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT))

from dotenv import load_dotenv

# NASA credentials live in the project-root .env
load_dotenv(PROJECT / ".env")

import uvicorn

if __name__ == "__main__":
    print("Starting Crop Shift on http://localhost:8000")
    uvicorn.run("web.backend.main:app", host="0.0.0.0", port=8000, reload=True)
