from pathlib import Path

from dotenv import load_dotenv


_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Load root env first, then backend-specific env to allow backend overrides.
load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env", override=True)

