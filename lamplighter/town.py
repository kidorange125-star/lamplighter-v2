"""Hollowmere's growth: invite survivors, pay the Builder, wait, and collect rent.

State lives in game.town (plain JSON):
  invited   building ids whose resident has agreed to move in
  built     finished buildings
  queue     [{"id", "ready_at", "steps"}]: done when the clock passes ready_at OR enough steps are walked
  rent_since / rent_banked   rent accrues per hour while away, up to a cap
  stash_level
"""
import math

from . import clock
from .content import BUILDINGS, ITEMS
from .ui import say

RENT_CAP_HOURS = 8
GEMS_PER_MINUTE = 0.25       # speeding up a build costs this many gems per minute left
STASH_CAPACITY = {1: 40, 2: 80, 3: 140}


def new_state():
    return {"invited": [], "built": [], "queue": [], "rent_since": None, "rent_banked": 0, "stash_level": 1}


def state(g):
    st = g.town
    for k, v in new_state().items():
        st.setdefault(k, v)
    return st


def is_built(g, bid):
    return bid in state(g)["built"]


def is_invited(g, bid):
    return bid in state(g)["invited"]


def queued(g, bid):
    return next((q for q in state(g)["queue"] if q["id"] == bid), None)


def invite(g, bid):
    st = state(g)
    if bid not in st["invited"] and bid not in st["built"]:
        st["invited"].append(bid)


def available(g):
    """Buildings whose resident has agreed to come and which have not been started."""
    st = state(g)
    return [b for b in st["invited"] if b not in st["built"] and not queued(g, b)]


def cost_lines(bid):
    c = BUILDINGS[bid]["cost"]
    parts = []
    if c.get("gold"):
        parts.append("%d gold" % c["gold"])
    for iid, n in c.get("items", {}).items():
        parts.append("%d %s" % (n, ITEMS[iid]["name"]))
    return ", ".join(parts)


def missing(g, bid):
    """What the player still lacks to start this building."""
    p = g.player
    c = BUILDINGS[bid]["cost"]
    out = []
    if p.gold < c.get("gold", 0):
        out.append("%d more gold" % (c["gold"] - p.gold))
    for iid, n in c.get("items", {}).items():
        have = p.inventory.get(iid, 0)
        if have < n:
            out.append("%d more %s" % (n - have, ITEMS[iid]["name"]))
    return out


def start_build(g, bid):
    if bid not in available(g) or missing(g, bid):
        return False
    p = g.player
    c = BUILDINGS[bid]["cost"]
    p.gold -= c.get("gold", 0)
    for iid, n in c.get("items", {}).items():
        p.remove_item(iid, n)
    b = BUILDINGS[bid]
    state(g)["queue"].append({"id": bid, "ready_at": clock.now() + b["minutes"] * 60, "steps": b["steps"]})
    return True


def minutes_left(entry):
    return max(0, math.ceil((entry["ready_at"] - clock.now()) / 60))


def speed_up_cost(entry):
    return max(1, math.ceil(minutes_left(entry) * GEMS_PER_MINUTE))


def speed_up(g, bid):
    entry = queued(g, bid)
    if not entry:
        return False
    cost = speed_up_cost(entry)
    if g.player.gems < cost:
        return False
    g.player.gems -= cost
    _complete(g, bid)
    return True


def _complete(g, bid):
    st = state(g)
    bank_rent(g)
    st["queue"] = [q for q in st["queue"] if q["id"] != bid]
    if bid not in st["built"]:
        st["built"].append(bid)
        if BUILDINGS[bid].get("forge_slot"):
            from . import forge
            forge.state(g)["slots"] += 1
    b = BUILDINGS[bid]
    g.notice("{bgreen}%s is finished.{/} %s" % (b["name"], b["blurb"]))


def update(g):
    """Finish anything whose time has come. Cheap; called often."""
    for entry in list(state(g)["queue"]):
        if clock.now() >= entry["ready_at"] or entry["steps"] <= 0:
            _complete(g, entry["id"])


def on_step(g):
    for entry in state(g)["queue"]:
        entry["steps"] -= 1
    update(g)


# ---------------------------------------------------------------------------- rent
def rent_rate(g):
    return sum(BUILDINGS[b]["rent"] for b in state(g)["built"])


def _accrued(g):
    st = state(g)
    if st["rent_since"] is None:
        return 0
    hours = max(0.0, (clock.now() - st["rent_since"]) / 3600.0)
    return int(min(hours, RENT_CAP_HOURS) * rent_rate(g))


def bank_rent(g):
    """Lock in what has built up so far, before the rate changes."""
    st = state(g)
    st["rent_banked"] += _accrued(g)
    st["rent_since"] = clock.now()


def rent_due(g):
    return state(g)["rent_banked"] + _accrued(g)


def collect_rent(g):
    due = rent_due(g)
    st = state(g)
    st["rent_banked"] = 0
    st["rent_since"] = clock.now()
    g.player.gold += due
    return due


# ---------------------------------------------------------------------------- stash
def stash_capacity(g):
    return STASH_CAPACITY[state(g)["stash_level"]]


def stash_used(g):
    return sum(g.player.stash.values())


def _resident(b):
    """The resident's display name (an NPC id like ff_marit would print as Ff_Marit)."""
    from . import npcs
    return npcs.NPCS[b["resident"]]["name"]


def summary_lines(g):
    st = state(g)
    lines = []
    for bid, b in BUILDINGS.items():
        if bid in st["built"]:
            lines.append("{bgreen}built{/}   %s {grey}- %s lives there, pays %d gold an hour{/}" % (
                b["name"], _resident(b), b["rent"]))
        elif queued(g, bid):
            q = queued(g, bid)
            lines.append("{amber}building{/} %s {grey}- about %d min or %d steps left{/}" % (
                b["name"], minutes_left(q), max(0, q["steps"])))
        elif bid in st["invited"]:
            lines.append("{gold}ready to build{/} %s {grey}- %s{/}" % (b["name"], cost_lines(bid)))
        else:
            lines.append("{grey}vacant     %s - %s has not been asked yet{/}" % (b["name"], _resident(b)))
    return lines
