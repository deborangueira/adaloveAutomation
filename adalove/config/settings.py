import json
import os
import tempfile

from adalove.config.paths import CONFIG_PATH


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "config.json not found. Run 'adalove setup' first."
        )
    with CONFIG_PATH.open(encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"config.json is malformed: {e}") from e


def save_config(data: dict) -> None:
    """Write config.json owner-only (0600) — it holds a live bearer token —
    and atomically, so a crash mid-write never leaves a truncated file that
    would lock the user out until they redo Setup."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file 0600 already (portable, unlike os.fchmod).
    fd, tmp = tempfile.mkstemp(dir=CONFIG_PATH.parent, prefix=".config-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
