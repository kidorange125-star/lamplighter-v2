"""The Last Lamplighter - a text RPG of oil, ash and the long night.

    python main.py              play
    python main.py --fast       no typewriter effect
    python main.py --no-color   plain text
    python main.py --seed 7 --script moves.txt   replay a list of commands (for testing)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import ui  # noqa: E402
from game.ui import say, blank, narrate  # noqa: E402
from game.engine import Game, QuitGame, save_path  # noqa: E402
from game.entities import Player  # noqa: E402
from game.data.classes import CLASSES, SKILLS  # noqa: E402


def create_character(g):
    ui.clear()
    ui.rule("A NEW APPRENTICE")
    say("You are the last apprentice of the Guild of Lamplighters.")
    name = ""
    while not name:
        name = ui.ask("What is your name? > ").strip()[:20]
        if not name:
            name = "Wick"
    name = name[0].upper() + name[1:]
    blank()
    say("Every lamplighter learns the hook and the wick. But each finds their own way to fight the dark.")
    blank()
    keys = list(CLASSES)
    labels = []
    for k in keys:
        c = CLASSES[k]
        b = c["base"]
        sk = ", ".join(SKILLS[s]["name"] for s in c["skills"])
        labels.append("{%s}{b}%s{/}{/} - %s\n        {grey}HP %d  STR %d  WIL %d  AGI %d   Skills: %s{/}" % (
            c["color"], c["name"], c["blurb"], b["hp"] + b["vit"] * 5, b["str"], b["wil"], b["agi"], sk))
    i = ui.menu(labels, prompt="Your path", allow_cancel=False)
    cls = keys[i]
    blank()
    diffs = [("Story", 0.7, "enemies hit softer; for enjoying the tale"),
             ("Normal", 1.0, "the dark as it was meant to be"),
             ("Hard", 1.3, "enemies hit much harder; every flask of oil matters")]
    j = ui.menu(["%s {grey}- %s{/}" % (n, d) for n, _, d in diffs], prompt="Difficulty", allow_cancel=False)
    g.diff_name, g.difficulty = diffs[j][0], diffs[j][1]
    g.player = Player(name, cls)


def intro(g):
    p = g.player
    ui.clear()
    ui.rule("THE FORTIETH NIGHT", color="night")
    narrate("Forty days ago the sun set over Hollowmere, and it did not rise again.")
    narrate("At first people said it was a storm, or smoke from a fire in the south. Then they stopped saying "
            "anything. The cold came. Then the Hollows came: wolves with no shadows, drowned things walking out "
            "of the marsh, shapes at the edge of the lamplight that are gone when you turn your head.")
    narrate("The Guild of Lamplighters tends the lamps of Hollowmere, as it has for three hundred years. One by one, "
            "the apprentices packed their things and left. Now there is only you, %s, and old Guildmaster Orrin, "
            "who has not left his bed in a month." % p.name)
    narrate("{amber}This morning, if it is morning, Orrin called for you.{/}")
    blank()
    say("{grey}(Type 'help' at any time for commands. Try 'talk orrin' to begin.){/}")
    ui.pause()


def title_screen():
    ui.title_art()
    while True:
        has_save = os.path.exists(save_path())
        opts = ["New game"]
        if has_save:
            opts.insert(0, "Continue")
        opts += ["Settings", "Quit"]
        i = ui.menu(opts, prompt="", allow_cancel=False)
        choice = opts[i]
        if choice == "Continue":
            try:
                g = Game.load()
                blank()
                g.notice("{bgreen}Welcome back, %s.{/}" % g.player.name)
                return g
            except (OSError, ValueError, KeyError) as e:
                say("{bred}That save could not be loaded (%s). Starting fresh.{/}" % e)
        if choice in ("New game", "Continue"):
            if has_save and choice == "New game":
                if not ui.confirm("Starting a new game will overwrite your save when you next rest. Continue?"):
                    continue
            g = Game()
            create_character(g)
            intro(g)
            g.visited.add(g.room_id)
            g.flags["visited_regions"] = ["Hollowmere"]
            return g
        if choice == "Settings":
            Game.cmd_settings(None, "")
            continue
        raise QuitGame()


def main():
    ap = argparse.ArgumentParser(description="The Last Lamplighter")
    ap.add_argument("--fast", action="store_true", help="disable the typewriter effect")
    ap.add_argument("--no-color", action="store_true", help="disable colour")
    ap.add_argument("--seed", type=int, default=None, help="random seed (for testing)")
    ap.add_argument("--script", help="file of commands to play automatically (for testing)")
    args = ap.parse_args()
    if args.fast:
        ui.settings.typewriter = False
    if args.no_color:
        ui.settings.color = False
    if args.script:
        with open(args.script, encoding="utf-8") as f:
            ui.io.script = [l.rstrip("\n") for l in f if not l.startswith("#")]
        ui.settings.typewriter = False
    try:
        g = title_screen()
        if args.seed is not None:
            g.rng.seed(args.seed)
        g.run()
        blank()
        ui.pause("(press Enter to close)")
    except QuitGame:
        pass
    except EOFError:
        pass
    blank()
    say("{amber}Mind your oil.{/}")


if __name__ == "__main__":
    main()
