import json
from pathlib import Path
from typing import Any

CONFIGS_DIR = Path(__file__).parent.parent / "configs"


def load_config(school_id: str) -> dict[str, Any]:
    """載入學校格式設定檔。"""
    path = CONFIGS_DIR / f"{school_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到學校「{school_id}」的格式設定檔（{path}）")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def list_available_schools() -> list[dict[str, str]]:
    """列出所有可用的學校設定。"""
    schools = []
    for p in CONFIGS_DIR.glob("*.json"):
        try:
            with p.open(encoding="utf-8") as f:
                cfg = json.load(f)
            schools.append({"school_id": cfg["school_id"], "school_name": cfg["school_name"]})
        except Exception:
            pass
    return schools
