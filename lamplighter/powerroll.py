"""Power rolls: the big bosses of the later areas are not the same every time you meet them.

Each time you step into the boss's room it rolls a power from 1 to 100, shown as a band with a line of flavour (and
the number, small). A low roll is a boss that is half-asleep; a high roll is one at the height of its strength, and it
pays better. You may always step back for free, or run once the fight has begun, and the boss will roll again when you return.
  - Mercy: after two deaths to the same boss the ceiling of the roll drops, and keeps dropping, so a stubborn
    player is never stuck.
  - Story bosses (the ones the plot hangs on) are capped, so the story is never out of reach.
The roll scales health and damage together (`mult`) and the rewards (`reward_mult`); a boss can also carry bonus drops
that become likelier as the roll rises. The template lives in enemies.json under "roll".
"""
import copy

from . import ui
from .content import ENEMIES
from .ui import say, blank, narrate

BANDS = [(15, "Faltering", "bgreen"), (40, "Subdued", "green"), (65, "Whole", "gold"),
         (85, "Roused", "ember"), (100, "Ablaze", "bred")]
STORY_CAP = 60
DEFAULT_FLAVOUR = [
    "It barely seems to know you are there.",
    "It is not at its best, and moves like it knows.",
    "It stands exactly as it was always meant to.",
    "It is stirred up, and the air around it hums.",
    "It is at the very peak of its strength.",
]


def band_index(power):
    for i, (hi, _, _) in enumerate(BANDS):
        if power <= hi:
            return i
    return len(BANDS) - 1


def band(power):
    hi, name, colour = BANDS[band_index(power)]
    return name, colour


def mult(power):
    """Health and damage multiplier: 0.51 at power 1, 1.0 at 50, 1.5 at 100."""
    return 0.5 + power / 100.0


def reward_mult(power):
    """Gold and experience: 0.6x at power 1, 1.8x at power 100."""
    return 0.6 + 0.012 * power


def mercy_cap(deaths):
    """The ceiling of the roll after dying to this boss: nothing for one death, then the Court holds back."""
    if deaths < 2:
        return 100
    return {2: 55, 3: 35}.get(deaths, 20)


def cap_for(eid, deaths):
    cap = mercy_cap(deaths)
    if ENEMIES[eid].get("roll", {}).get("story"):
        cap = min(cap, STORY_CAP)
    return cap


def roll(g, eid):
    """Roll a power for this meeting. Returns (power, cap)."""
    cap = cap_for(eid, g.flags.get("deaths_" + eid, 0))
    return g.rng.randint(1, cap), cap


def flavour(eid, power):
    lines = ENEMIES[eid].get("roll", {}).get("flavour") or DEFAULT_FLAVOUR
    return lines[band_index(power)]


def base_id(eid):
    return eid.split("@")[0]


def scaled(eid, power):
    """Register the boss as it is at this power and return its id (e.g. cinder_queen@73)."""
    new = "%s@%d" % (eid, power)
    if new in ENEMIES:
        return new
    t = copy.deepcopy(ENEMIES[eid])
    m, rm = mult(power), reward_mult(power)
    t["hp"] = max(1, int(t["hp"] * m))
    t["atk"] = max(1, int(round(t["atk"] * m)))
    t["xp"] = int(t.get("xp", 0) * rm)
    lo, hi = t.get("gold", (0, 0))
    t["gold"] = [int(lo * rm), int(hi * rm)]
    for b in t.get("roll", {}).get("bonus", []):
        span = max(1, b["to"] - b["from"])
        chance = min(1.0, max(0.0, (power - b["from"]) / span))
        for _ in range(b.get("count", 1)):
            if chance > 0:
                t["drops"].append([b["item"], round(chance, 3)])
    ENEMIES[new] = t
    return new


DEFAULT_PRON = {"subj": "she", "obj": "her", "poss": "her"}
DEFAULT_PLACE = "The Court"


def pron(eid):
    """The boss's pronouns for the roll text (she/her/her unless the enemy's `roll.pron` says otherwise)."""
    return dict(DEFAULT_PRON, **ENEMIES[base_id(eid)].get("roll", {}).get("pron", {}))


def place(eid):
    return ENEMIES[base_id(eid)].get("roll", {}).get("place", DEFAULT_PLACE)


def show(eid, power, cap):
    name, colour = band(power)
    subj = pron(eid)["subj"]
    blank()
    ui.rule("%s  ·  %s" % (ENEMIES[eid]["name"].replace("The ", "", 1), name.upper()), color=colour)
    say("{%s}%s{/}" % (colour, flavour(eid, power)))
    say("{grey}Power %d of 100. The stronger %s is, the more %s pays.{/}" % (power, subj, subj))
    if cap < 100:
        say("{grey}(%s holds back. Your bad luck so far has lowered the ceiling to %d.){/}" % (place(eid), cap))


def boss_scene(g, eid, flag, back, on_win, intro=None, prologue=None, step_back_text=None):
    """Roll, show, let the player choose, fight. Returns True (the event always takes over the room).

    flag      the flag set when the boss is beaten
    back      the room to step back to
    on_win    called as on_win(g, power) after a win
    """
    deaths = g.flags.get("deaths_" + eid, 0)
    power, cap = roll(g, eid)
    if prologue:
        prologue()
    show(eid, power, cap)
    blank()
    k = ui.menu(["Face %s at this strength" % pron(eid)["obj"]], prompt="Decide",
                cancel_label=step_back_text or "Step back and come again later (free)")
    if k is None:
        g.room_id = back
        say("{grey}You back out of the room, slowly. The roll will be different when you return.{/}")
        return True
    outcome = g.fight([scaled(eid, power)], intro=intro)
    if outcome == "win":
        g.flags[flag] = True
        g.flags.pop("deaths_" + eid, None)
        g.flags["power_" + eid] = power
        on_win(g, power)
    elif outcome == "fled":
        g.room_id = back
        say("{grey}You stumble back through the doors. %s does not follow. The roll will be different when you return.{/}"
            % pron(eid)["subj"].capitalize())
    elif outcome == "dead":
        g.flags["deaths_" + eid] = deaths + 1
        if deaths + 1 >= 2:
            say("{grey}Somewhere, something relents. Next time the roll will be gentler.{/}")
    return True
