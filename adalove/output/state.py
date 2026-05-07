import json
from pathlib import Path


def _path() -> Path:
    return Path.cwd() / "output" / ".state.json"


def load_written_uuids() -> set[str]:
    p = _path()
    if not p.exists():
        return set()
    try:
        with p.open(encoding="utf-8") as f:
            return set(json.load(f).get("written_uuids", []))
    except (json.JSONDecodeError, KeyError, OSError):
        return set()


def save_written_uuids(uuids: set[str]) -> None:
    p = _path()
    p.parent.mkdir(exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump({"written_uuids": sorted(uuids)}, f, indent=2)
