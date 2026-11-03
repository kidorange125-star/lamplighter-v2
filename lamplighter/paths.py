"""Where the game keeps things that must survive updates: saves and settings.

These live in the user's data folder, never inside the game folder, so replacing the game's
code (the `update` command, a fresh download) can never touch a save.

Set LAMPLIGHTER_HOME to use a different folder (the tests do this).
"""
import os
import sys


def data_dir():
    override = os.environ.get("LAMPLIGHTER_HOME")
    if override:
        base = override
    elif os.name == "nt":
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Lamplighter")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Lamplighter")
    else:
        base = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "lamplighter")
    return base


def saves_dir():
    return os.path.join(data_dir(), "saves")


def game_root():
    """The folder containing main.py and version.json."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
