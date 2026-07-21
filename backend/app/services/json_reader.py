import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def load_json_file(filename: str):
    file_path = DATA_DIR / filename

    if not file_path.exists():
        return {
            "error": f"{filename} not found",
            "file_path": str(file_path)
        }

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)