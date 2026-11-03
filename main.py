"""The Last Lamplighter - a text RPG of oil, ash and the long night.

    python main.py              play
    python main.py --fast       no typewriter effect
    python main.py --no-color   plain text
    python main.py --update     look for a newer version and install it
                                (also: --update check, --update force, --update repo owner/name)
    python main.py --seed 7 --script moves.txt   replay a list of commands (for testing)
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def recover_interrupted_update(root):
    """Finish what a cut-short update left behind. Standard library only, and it runs before the game's own
    code is imported, because that code (the lamplighter folder) may be exactly what is missing.

    The updater writes .update_swap before it moves any file and deletes it after the last move, so a
    marker that is still here means the power went or the process was killed mid-swap. The fix is to go
    back to the old files, which the updater keeps in .update_old: any name that is in there is put back
    (the copy that took its place is the half-installed new one), and names the update added are removed.
    If the game folder already had an .update_old from the update before, the updater moves it to
    .update_new/previous_old first; the marker says whether there was one, so a kill before that first
    move is told apart from a kill after it, and the older copy is never mistaken for the one to restore."""
    marker = os.path.join(root, ".update_swap")
    if not os.path.exists(marker):
        return
    import json
    import shutil
    import stat
    old_dir, stage = os.path.join(root, ".update_old"), os.path.join(root, ".update_new")
    prev = os.path.join(stage, "previous_old")

    def remove(path):
        def fix(func, p, _exc):
            os.chmod(p, stat.S_IWRITE)
            func(p)
        if os.path.isdir(path) and not os.path.islink(path):
            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=fix)
            else:
                shutil.rmtree(path, onerror=fix)
        else:
            os.remove(path)

    try:
        try:
            with open(marker, encoding="utf-8") as f:
                info = json.load(f)
            incoming, existing, had_old = list(info["incoming"]), list(info["existing"]), bool(info["had_old"])
        except (OSError, ValueError, KeyError, TypeError):
            incoming, existing, had_old = [], [], None      # written whole or not at all, so: no moves were made
        # Has anything been moved? The first move is .update_old -> .update_new/previous_old when there was
        # an .update_old; with none, the first move puts a file into a fresh .update_old, so that tells too.
        started = False if had_old is None else os.path.isdir(prev) if had_old else os.path.isdir(old_dir)
        if started:
            for name in incoming:
                if name not in existing and os.path.lexists(os.path.join(root, name)):
                    remove(os.path.join(root, name))
            if os.path.isdir(old_dir):
                for name in os.listdir(old_dir):
                    here = os.path.join(root, name)
                    if os.path.lexists(here):
                        remove(here)
                    os.rename(os.path.join(old_dir, name), here)
                os.rmdir(old_dir)
            if os.path.isdir(prev):
                os.rename(prev, old_dir)
        if os.path.lexists(stage):
            remove(stage)
        os.remove(marker)
    except OSError as e:
        print("A previous update was cut short, and I could not put the earlier game files back (%s)." % e)
        print("They are in %s. Copy everything in there back into %s, then delete the folders .update_old and "
              ".update_new and the file .update_swap." % (old_dir, root))
        sys.exit(1)
    import importlib
    importlib.invalidate_caches()    # the folder listing Python cached at start-up has no lamplighter in it
    print("A previous update was cut short (the power went off or the game was closed during it), so I put "
          "your earlier game files back. Your saves were not touched. Run the update again when you like.")


recover_interrupted_update(ROOT)
sys.path.insert(0, ROOT)

from lamplighter import ui  # noqa: E402
from lamplighter.ui import say, blank, narrate  # noqa: E402
from lamplighter import save  # noqa: E402
from lamplighter.engine import Game, QuitGame  # noqa: E402
from lamplighter.entities import Player  # noqa: E402
from lamplighter.content import CLASSES, SKILLS  # noqa: E402


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
    say("{grey}(Pick a numbered action, or type a command. 'hint' tells you what to do next, 'help' lists everything.){/}")
    ui.pause()


def _welcome(g):
    blank()
    if g.load_note:
        say("{grey}%s{/}" % g.load_note)
    g.notice("{bgreen}Welcome back, %s.{/}" % g.player.name)
    return g


def continue_game():
    """Load the saved game. Returns the Game, or None to go back to the title menu.

    A save from a newer game is left alone and the player is told what to do. A save that cannot be read is
    never deleted: if the previous save (<slot>.bak.json) is good the player is asked whether to use that
    instead, and only if they say yes is the damaged file moved aside (to <slot>.damaged.json). With nothing to
    fall back on it is moved aside at once, so the title screen stops offering it."""
    try:
        return _welcome(Game.load())
    except save.SaveDamaged as e:
        say("{bred}%s{/}" % e)
    except save.SaveError as e:
        say("{bred}%s{/}" % e)
        return None
    except OSError as e:
        say("{bred}The save could not be opened (%s). Nothing has been changed.{/}" % e)
        return None
    # the main save is damaged or missing
    who = None
    try:
        data, _ = save.read_info(save.backup_slot(), keep_copy=False)
        who = "%s, level %s" % (data["player"].get("name", "?"), data["player"].get("level", "?"))
        no_fallback = ""
    except save.SaveTooNew:
        no_fallback = ("Your previous save is from a newer version of the game, which this version cannot read. "
                       "Update the game (run: python main.py --update) to use it. You can also start a new game.")
    except save.SaveError:
        no_fallback = "There is no earlier save to fall back on. You can start a new game."
    except OSError as e:
        say("{bred}The previous save could not be opened (%s). Nothing has been changed.{/}" % e)
        return None
    try:
        if who is None:
            kept = save.set_aside()
            if kept:
                say("Nothing has been deleted: the damaged save is kept as %s." % kept)
            say(no_fallback)
            return None
        say("The game keeps your previous save (%s), the one from just before your last save. Loading it "
            "loses only what you did in between." % who)
        if not ui.confirm("Load your previous save instead?"):
            say("{grey}Nothing has been changed. Choose Continue again if you change your mind.{/}")
            return None
        kept = save.set_aside()
        if kept:
            say("Nothing has been deleted: the damaged save is kept as %s." % kept)
        save.restore_backup()
        return _welcome(Game.load())
    except (save.SaveError, OSError) as e:
        say("{bred}The previous save could not be loaded (%s).{/}" % e)
        return None


def title_screen():
    ui.title_art()
    while True:
        # the previous save counts too: if the main one is gone, Continue can still offer it
        has_save = save.exists() or save.exists(save.backup_slot())
        opts = ["New game"]
        if has_save:
            opts.insert(0, "Continue")
        opts += ["Settings", "Quit"]
        i = ui.menu(opts, prompt="", allow_cancel=False)
        choice = opts[i]
        if choice == "Continue":
            g = continue_game()
            if g is None:
                continue
            return g
        if choice == "New game":
            if has_save:
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
    ap.add_argument("--update", nargs="*", default=None, metavar="WORD",
                    help="check for a newer version and install it; add check, force or repo owner/name")
    args = ap.parse_args()
    if args.fast:
        ui.settings.typewriter = False
    if args.no_color:
        ui.settings.color = False
    if args.script:
        with open(args.script, encoding="utf-8") as f:
            ui.io.script = [l.rstrip("\n") for l in f if not l.startswith("#")]
        ui.settings.typewriter = False
    if args.update is not None:
        from lamplighter import update
        sys.exit(update.run_command(" ".join(args.update), say, ui.confirm, cli=True))
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
