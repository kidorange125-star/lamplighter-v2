import contextlib
import io
import os
import tempfile

from lamplighter import ui
from lamplighter.engine import Game
from lamplighter.entities import Player


@contextlib.contextmanager
def temp_home():
    """Point the game's data folder at a throwaway directory."""
    old = os.environ.get("LAMPLIGHTER_HOME")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LAMPLIGHTER_HOME"] = tmp
        try:
            yield tmp
        finally:
            if old is None:
                os.environ.pop("LAMPLIGHTER_HOME", None)
            else:
                os.environ["LAMPLIGHTER_HOME"] = old


def quiet_ui():
    ui.settings.color = False
    ui.settings.typewriter = False
    ui.io.script = []
    ui.io.pending = None


def new_game(cls="wayfarer", seed=1):
    quiet_ui()
    g = Game(seed=seed)
    g.player = Player("Test", cls)
    g.visited.add(g.room_id)
    return g


def run(game, *commands, answers=()):
    """Run commands through the game's parser, capturing and returning everything printed."""
    ui.io.script = list(answers)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for c in commands:
            game.handle(c)
    return out.getvalue()
