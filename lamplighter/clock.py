"""The game's clock. Build timers and rent run on real time, so they keep going while the game is closed.

Tests replace the clock with a fixed or movable one.
"""
import time

_override = None


def now():
    return _override() if _override else time.time()


def set_clock(fn):
    """Use fn() instead of the system time. Pass None to go back to the real clock."""
    global _override
    _override = fn
