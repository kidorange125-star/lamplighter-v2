"""Redeemable codes. Only hashes are stored in the game files; each code works once per save.

Add a new code with:  python tools/make_code.py CODE GEMS "label"
"""
import hashlib

from .content import CODES


def code_hash(code):
    norm = "".join(ch for ch in code.upper() if ch.isalnum())
    return hashlib.sha256(("lamplighter:" + norm).encode("utf-8")).hexdigest()


def redeem(game, text):
    """Returns (ok, message)."""
    h = code_hash(text)
    info = CODES.get(h)
    if not info or not any(ch.isalnum() for ch in text):
        return False, "That code is not valid."
    used = game.flags.setdefault("codes_used", [])
    if h in used:
        return False, "You have already used that code."
    used.append(h)
    game.player.gems += info["gems"]
    return True, "Code accepted: %s. +%d gems (you have %d)." % (info["label"], info["gems"], game.player.gems)
