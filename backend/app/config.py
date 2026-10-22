from pathlib import Path
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if Path("/app").exists():
    load_dotenv("/app/.env")
    DATA_DIR = Path("/data")
else:
    load_dotenv(PROJECT_ROOT / ".env")
    DATA_DIR = PROJECT_ROOT / "data"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5433/alfa")

LLM_BASE_URL = (
    os.getenv("LLM_API_BASE")
    or os.getenv("LLM_BASE_URL")
    or "https://changellenge.up.railway.app/v1"
)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "z-ai/glm-5.3-flash")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
