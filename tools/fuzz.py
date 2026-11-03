"""Plays the game with random input to find crashes.

usage: python tools/fuzz.py [games=40] [reads_per_game=1500] [first_seed=0]

Each game uses a random class, random teleports, random item grants and random keystrokes at every
prompt. Any exception is reported once per distinct traceback, with the seed and the last inputs, so
it can be replayed.

When a game ends it is also saved, loaded again and compared: the two must be identical, which catches a
field that to_dict forgets or from_dict cannot restore. Those are reported once per distinct set of fields.
"""
import json
import os
import random
import re
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LAMPLIGHTER_HOME"] = tempfile.mkdtemp(prefix="ll_fuzz_")

from lamplighter import ui  # noqa: E402
from lamplighter.content import ITEMS, ROOMS  # noqa: E402
from lamplighter.engine import Game, QuitGame  # noqa: E402
from lamplighter.entities import Player  # noqa: E402
from lamplighter import clock, dealer, gear, npcs, save, town  # noqa: E402
from lamplighter.content import BUILDINGS  # noqa: E402

GAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 40
READS = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
FIRST = int(sys.argv[3]) if len(sys.argv) > 3 else 0

MAIN = ["spells", "talk mirelle", "go tower", "n", "s", "e", "w", "u", "d", "north", "go south", "look", "take all", "take", "i", "inventory", "stats", "skills",
        "journal", "map", "map world", "map saltmarsh", "hint", "travel", "travel objective", "travel hall", "lantern",
        "rest", "light", "bounty", "wait", "save", "load", "settings", "help", "pages", "train", "trade", "read", "read 1",
        "read page 4", "unequip hook", "unequip armor", "drop hook", "drop all", "equip", "use", "use oil", "use draught",
        "use tallow", "talk", "talk orrin", "talk maeve", "talk brann", "talk wren", "talk tallow", "x", "x lantern",
        "x me", "x desk", "examine well", "go docks", "go lightwell", "dance", "", "   ", "n then e then s",
        "forge", "talk brann", "collect", "stash", "recall", "return", "redeem NEW", "redeem zzz", "redeem", "town", "talk joss", "talk odo",
        "talk dagna", "talk corvin", "talk ysolde", "talk wizard", "go market", "go home", "go yard", "travel stall",
        "take page", "light waypost", "equip fang", "equip tooth", "equip censer", "equip spear", "equip signet"]
COMBAT = ["s1", "s2", "s3", "s1 1", "s2 2", "s4", "firebolt", "", "a", "g", "f", "i", "r", "1", "2", "3", "4", "help", "a 1", "a 2", "a 3", "1 1", "2 2", "3 3", "4 2",
          "attack", "guard", "flare", "items", "flee", "twin cut", "bash", "zzz", "0", "9", "g", "a"]


class Fuzz:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.seed = seed
        self.reads = 0
        self.trail = []
        self.g = None

    def grant(self):
        g, rng = self.g, self.rng
        p = g.player
        what = rng.random()
        if what < 0.25:
            # base items only: a forged piece (g12) is real only while it is in the player's gear, and ITEMS keeps
            # the ones from earlier games, which a saved game could not bring back in a new process
            iid = rng.choice([k for k, v in ITEMS.items() if not v.get("instance")])
            g.give(iid, rng.randint(1, 3), quiet=True)
        elif what < 0.40:
            p.gold += rng.randint(50, 600)
        elif what < 0.50:
            p.gain_xp(rng.randint(20, 400))
        elif what < 0.60:
            for k in ("mother_dead", "reeve_dead", "bishop_dead", "choir_dead", "golem_dead", "brood_dead", "usher_dead",
                      "camp_wight", "nave_guard", "shrine_moths"):
                if rng.random() < 0.3:
                    g.flags[k] = True
        elif what < 0.68:
            for iid in ("ember_wood", "ember_tide", "ember_ash"):
                if rng.random() < 0.5:
                    p.add_item(iid)
        elif what < 0.76:
            for iid in ("rootwood", "saltstone", "slag"):
                p.add_item(iid, rng.randint(0, 8))
            p.gems += rng.randint(0, 30)
        elif what < 0.84:
            town.invite(g, rng.choice(list(BUILDINGS)))
            if rng.random() < 0.4:
                clock.advance_fuzz(rng.randint(5, 600))
        elif what < 0.88:
            g.flags["completed"] = True
            p.add_item("homecoming_charm")
        elif what < 0.90:
            for iid in ("hollow_core", "relic_ember", "relic_edge", "relic_heart", "hauberk", "saltsteel_saber", "slag", "saltstone"):
                if rng.random() < 0.5:
                    p.add_item(iid, rng.randint(1, 4))
            p.gold += rng.randint(0, 3000)
            if rng.random() < 0.3:
                from lamplighter import gear
                inst = gear.make(rng.choice(["hunting_spear", "hauberk", "ashwood_rod", "moth_charm"]),
                                 rng.choice(["rare", "epic", "ultra", "legendary", "godlike"]), rng)
                gear.give(p, inst)
            if rng.random() < 0.3:
                g.flags["godlike_recipe"] = True
        elif what < 0.915:
            from lamplighter import elements, spells as spl
            for _ in range(rng.randint(1, 4)):
                spl.make_book(g, rng.choice(elements.ELEMENTS),
                              rng.choice(["common", "common", "uncommon", "rare", "epic", "ultra", "legendary", "godlike"]))
            for e in elements.ELEMENTS:
                p.add_item("essence_" + e, rng.randint(0, 6))
            if rng.random() < 0.3:
                g.flags["apex_unlocked"] = True
            if rng.random() < 0.5 and spl.books_in_pack(p):
                spl.equip(p, rng.choice(spl.books_in_pack(p)))
        elif what < 0.92:
            p.dread = rng.choice([0, 30, 60, 80, 99])
            p.relic_charges = rng.randint(0, 3)
        else:
            p.hp = rng.randint(1, p.max_hp)
            p.oil = rng.choice([0, 5, 30, 100])
            g.flags["wren_home"] = rng.random() < 0.5
            g.flags["wren_ready"] = rng.random() < 0.5
            g.flags["wren_following"] = rng.random() < 0.2
            g.quests["main"] = rng.choice([-1, 0, 1, 2, 3, "done"])

    def read(self, prompt=""):
        self.reads += 1
        plain = re.sub(r"\x1b\[[0-9;]*m", "", prompt).strip()
        rng = self.rng
        if self.reads > READS:
            raise QuitGame()
        if "What will you do?" in plain:
            roll = rng.random()
            if roll < 0.03:
                rid = rng.choice(list(ROOMS))
                self.g.room_id = rid
                self.g.visited.add(rid)
                ans = "look"
            elif roll < 0.045:
                # sit down at a Darkness Dealer's cloth with gems to spend, sometimes after the clock has jumped a day
                if rng.random() < 0.3:
                    clock.advance_fuzz(rng.choice([-1440, 600, 1440, 2880, 43200]))
                self.g.player.gems = rng.choice([0, 2, 9, 40, 200, 100000])
                rid = dealer.room_for(self.g, rng.randint(1, 4))
                if rid:
                    self.g.room_id = rid
                    self.g.visited.add(rid)
                ans = "talk dealer"
            elif roll < 0.08:
                self.grant()
                ans = "i"
            elif roll < 0.35:
                ans = str(rng.randint(1, 9))
            else:
                ans = rng.choice(MAIN)
        elif plain.startswith("action"):
            ans = rng.choice(COMBAT)
        elif plain.startswith("target"):
            ans = rng.choice(["", "1", "2", "3", "0", "x", "9"])
        elif "(press Enter" in plain or plain.startswith("(press"):
            ans = ""
        elif plain == ">":
            ans = rng.choice(["y", "n", "", "yes"])
        else:  # a numbered menu: Say, Use, Buy, Sell, Trade, Train, Travel to, Settings, Which one, Your path ...
            ans = rng.choice(["0", "1", "1", "2", "2", "3", "4", "5", "6", "7", "8", "9", "", "back", "zzz", "talk orrin", "n"])
        self.trail.append((plain[:30], ans))
        self.trail = self.trail[-12:]
        return ans


def _diff(a, b, path=""):
    """Paths where two saved-game dicts differ (stops at the first level that differs inside a leaf)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append("%s.%s (%s)" % (path, k, "only after loading" if k in b else "lost on loading"))
            else:
                out += _diff(a[k], b[k], "%s.%s" % (path, k))
        return out
    return [] if a == b else [path or "."]


def forget_forged_gear():
    """Like a fresh process: no forged items registered, the id counter at zero."""
    for k in [k for k, v in ITEMS.items() if v.get("instance")]:
        del ITEMS[k]
    gear._counter[0] = 0


def round_trip(g):
    """Save and reload a finished game. Returns a list of differing paths, or None if it round-trips."""
    # Game.load adds the Homecoming Charm to a save past the start of the story that lacks one; do the same here
    # so that deliberate repair is not reported as a lost field.
    if g.quest("main") not in (-1, 0) and not g.player.has_item("homecoming_charm"):
        g.player.add_item("homecoming_charm")
    before = json.loads(json.dumps(g.to_dict()))
    save.write(g.to_dict(), "fuzz")
    forget_forged_gear()    # loading must register the forged items again, as it has to in a new process
    after = json.loads(json.dumps(Game.load("fuzz").to_dict()))
    diffs = _diff(before, after)
    return diffs or None


def make_game(seed, fz):
    rng = random.Random(seed * 7919 + 1)
    forget_forged_gear()
    g = Game(seed=seed)
    g.player = Player("Fuzz", rng.choice(["warden", "ashblade", "wayfarer"]))
    g.difficulty = rng.choice([0.7, 1.0, 1.3])
    g.visited.add("hall")
    g.flags["visited_regions"] = ["Hollowmere"]
    fz.g = g
    return g


_fuzz_time = [1_000_000.0]
clock.set_clock(lambda: _fuzz_time[0])
clock.advance_fuzz = lambda minutes: _fuzz_time.__setitem__(0, _fuzz_time[0] + minutes * 60)


def main():
    ui.settings.typewriter = False
    ui.settings.color = rng_color = False
    ui.io.mute = True
    seen = {}
    round_trips = {}
    games_run = 0
    cov = {"reads": 0, "battles": 0, "deaths": 0, "rooms": set(), "endings": set(), "finished": 0}
    for seed in range(FIRST, FIRST + GAMES):
        fz = Fuzz(seed)
        g = make_game(seed, fz)
        ui.io.read = fz.read
        ui.io.script = None
        ui.io.pending = None
        crashed = False
        try:
            g.run()
        except QuitGame:
            pass
        except Exception:
            crashed = True
            tb = traceback.format_exc()
            lines = [l for l in tb.strip().split("\n") if l.strip()]
            sig = "\n".join(lines[-3:])
            if sig not in seen:
                seen[sig] = (seed, fz.trail[:], tb)
        if not crashed:   # a game that ended (or was cut off) must save and load back to exactly itself
            try:
                diffs = round_trip(g)
            except Exception:
                tb = traceback.format_exc()
                diffs = ["save/load raised: " + tb.strip().splitlines()[-1]]
            if diffs:
                sig = "; ".join(diffs[:6])
                if sig not in round_trips:
                    round_trips[sig] = (seed, diffs)
        games_run += 1
        cov["reads"] += fz.reads
        cov["battles"] += g.stats.get("battles", 0)
        cov["deaths"] += g.stats.get("deaths", 0)
        cov["rooms"] |= set(g.visited)
        if g.flags.get("ending"):
            cov["endings"].add(g.flags["ending"])
        if g.over:
            cov["finished"] += 1
    ui.io.mute = False
    print("%d games, %d inputs, %d battles won, %d deaths, %d/%d rooms reached, endings seen: %s" % (
        games_run, cov["reads"], cov["battles"], cov["deaths"], len(cov["rooms"]), len(ROOMS), sorted(cov["endings"]) or "none"))
    print("%d distinct crash%s" % (len(seen), "" if len(seen) == 1 else "es"))
    print("%d distinct save/load mismatch%s" % (len(round_trips), "" if len(round_trips) == 1 else "es"))
    for sig, (seed, diffs) in round_trips.items():
        print("\n--- save/load, seed %d: %d field(s) differ ---" % (seed, len(diffs)))
        for d in diffs[:12]:
            print("  ", d)
    for sig, (seed, trail, tb) in seen.items():
        print("\n--- seed %d ---" % seed)
        print(tb[-1400:])
        print("last inputs:", trail)
    sys.exit(1 if seen or round_trips else 0)


main()
