"""Plays the whole game through the real UI to an ending, as a regression test and a difficulty probe.

usage: python tools/bot.py <class> <seed> [difficulty 0.7|1.0|1.3] [ending share|give|leave|crown]

In fights it takes the game's own suggestion every turn. Everything else follows a fixed route.
Exit code 0 means it reached an ending.
"""
import io as _io
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
CLS, SEED = sys.argv[1], int(sys.argv[2])
DIFF = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
ENDING = sys.argv[4] if len(sys.argv) > 4 else "share"
os.environ["LAMPLIGHTER_HOME"] = tempfile.mkdtemp(prefix="ll_bot_")

from lamplighter import combat, ui  # noqa: E402
from lamplighter.engine import Game, QuitGame  # noqa: E402
from lamplighter.entities import Player  # noqa: E402
from lamplighter.content import ITEMS  # noqa: E402

ui.settings.typewriter = False
ui.settings.color = False

ROUTE = """
take page
read 1
talk orrin
e
e
talk maeve
w
s
w
talk ilse
e
e
talk brann
<0>
w
n
n
talk hesk
n
light
n
w
take all
equip spear
e
e
take all
light
w
n
w
talk corvin
rest
e
e
take all
light
rest
w
n
s
s
s
s
s
e
talk wren
w
s
e
talk brann
<~Brass Shroud>
<0>
w
s
talk oskar
e
e
take all
s
take all
n
e
take all
s
take all
n
e
n
take all
n
s
d
e
e
w
s
talk tallow
<0>
rest
w
take all
e
e
take all
e
w
w
s
take all
e
u
s
w
talk ilse
<1>
<0>
e
e
talk brann
<1>
<0>
equip starsteel
w
n
w
talk orrin
<ring>
<0>
rest
e
d
e
e
""".strip().split("\n")

cmds = list(ROUTE)
menu_answers = []
G = None
log = []
events = []
deaths = [0]


# take the game's own suggestion every turn
combat.Combat.decide = lambda self: self.suggest()[0]

orig_finish = combat.Combat.finish


def finish(self, outcome):
    names = ",".join(e.id for e in self.enemies)
    p = self.p
    if any(e.boss or "elite" in e.tags for e in self.enemies) or outcome != "win":
        events.append("%-8s %-40s rounds=%2d hp=%d/%d oil=%d lvl=%d" % (outcome, names[:40], self.round, p.hp, p.max_hp, p.oil, p.level))
    return orig_finish(self, outcome)


combat.Combat.finish = finish

orig_death = Game.death


def death(self):
    deaths[0] += 1
    events.append("DEATH in %s" % self.room_id)
    orig_death(self)
    # after death, walk back is not scripted: abort run
    raise QuitGame()


Game.death = death


READS = [0]


def bot_read(prompt=""):
    READS[0] += 1
    if READS[0] > 40000:
        sys.stdout = real_stdout
        print("HANG; prompt=", repr(prompt))
        NL = chr(10)
        print(NL.join(l for l in buf.getvalue().split(NL) if l.strip() and "Pick a number" not in l)[-3500:])
        raise SystemExit(2)
    plain = re.sub(r"\x1b\[[0-9;]*m", "", prompt)
    if menu_answers:
        a = menu_answers.pop(0)
        log.append(plain + a)
        return a
    if "Train" in plain:
        p = G.player
        a = {"warden": "1", "ashblade": "2", "wayfarer": "3"}[p.cls] if p.points % 2 == 0 else "4"
        return a
    tail = buf.getvalue()[-400:]
    if plain.strip() == ">" and "[y/n]" in tail:
        return ("y" if ENDING == "crown" else "n") if "lantern down" in tail else "y"
    if "Say >" in plain and "Raise your lantern" in buf.getvalue()[-1500:]:
        if ENDING == "crown":
            return pick_label("offering")
        return pick_label("Aldric") or pick_label("fight")
    if "Say >" in plain:
        if cmds and cmds[0].startswith("<"):
            c = cmds.pop(0)[1:-1]
            if c.startswith("~"):          # choose a menu item by its text, so menu reordering cannot break the route
                return pick_label(c[1:]) or "0"
            if c == "ring":
                return "1" if False else _ring()
            return c
        return "0"
    if "Choose >" in plain:
        want = {"share": "Wren's hand", "give": "own flame", "leave": "walk away", "crown": "own flame"}[ENDING]
        return pick_label(want) or pick_label("own flame")
    if "Use >" in plain or "Target" in plain or "Skill" in plain:
        return "1"
    if "(press Enter" in plain:
        return ""
    # pre-step maintenance
    p = G.player
    boss_approach = G.room_id in ("chapel_nave", "deepwood", "lightwell_gate", "choir_gallery", "well_bottom", "mine_hall")
    if (p.oil < 25 or (boss_approach and p.oil < p.max_oil - 40)) and p.inventory.get("oil"):
        return "use oil"
    if p.hp < p.max_hp * 0.45 and (p.inventory.get("draught") or p.inventory.get("strong_draught")):
        return "use draught" if p.inventory.get("draught") else "use strong"
    if p.points:
        return "train"
    if not cmds:
        raise QuitGame()
    c = cmds.pop(0)
    while c.startswith("<"):
        c = cmds.pop(0)
    log.append("CMD " + c)
    return c


def pick_label(sub):
    tail = buf.getvalue()[-1200:]
    found = None
    for n, label in re.findall(r"\[(\d)\] (.*)", tail):
        if sub in label:
            found = n
    return found


def _ring():
    # find index of the 'Show him' option in last printed menu
    tail = buf.getvalue()[-1500:]
    m = re.findall(r"\[(\d)\] (.*)", tail)
    for n, label in m:
        if "Show him" in label:
            return n
    return "0"


buf = _io.StringIO()


class Tee:
    def write(self, s):
        buf.write(s)

    def flush(self):
        pass


ui.io.read = bot_read
real_stdout = sys.stdout
sys.stdout = Tee()
G = Game(seed=SEED)
G.player = Player("Bot", CLS)
if os.environ.get("NO_DREAD"):
    G.player.dread_effects = False   # to measure what Dread costs
G.difficulty = DIFF
G.visited.add("hall")
G.flags["visited_regions"] = ["Hollowmere"]
# final ending menu override
_lightwell_named = []
try:
    G.run()
except QuitGame:
    pass
except Exception:
    import traceback
    sys.stdout = real_stdout
    print(buf.getvalue()[-4000:])
    traceback.print_exc()
    sys.exit(1)
sys.stdout = real_stdout
LOG = os.path.join(tempfile.gettempdir(), "ll_bot_%s_%d.log" % (CLS, SEED))
open(LOG, "w", encoding="utf-8").write(buf.getvalue())
p = G.player
print("class=%s seed=%d diff=%.1f -> room=%s lvl=%d hp=%d/%d gold=%d oil=%d ending=%s kills=%d deaths=%d remaining_cmds=%d" % (
    CLS, SEED, DIFF, G.room_id, p.level, p.hp, p.max_hp, p.gold, p.oil, G.flags.get("ending"), G.stats.get("kills", 0), deaths[0], len(cmds)))
for e in events:
    print("   ", e)
print("   quests:", {k: v for k, v in G.quests.items()})
print("   log:", LOG)
sys.exit(0 if G.flags.get("ending") else 1)
