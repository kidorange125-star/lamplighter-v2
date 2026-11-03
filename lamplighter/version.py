"""The game version, read from version.json at the project root."""
import json
import os

from . import paths


def info():
    try:
        with open(os.path.join(paths.game_root(), "version.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"version": "unknown", "changelog": []}


VERSION = info()["version"]
