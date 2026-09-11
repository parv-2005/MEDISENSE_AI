import os
import sys
from pathlib import Path

# Make `app` importable and give tests deterministic settings.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-0123456789abcdef")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB", "medisense_test")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("UPLOAD_DIR", str(ROOT / "tests" / "_uploads"))
os.environ.setdefault("CHROMA_DIR", str(ROOT / "tests" / "_chroma"))
