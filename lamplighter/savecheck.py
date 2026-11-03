"""Does a loaded save fit this game?

save.py checks the shape of a save (and migrates it). This checks the meaning: that the room and class exist,
that the numbers are numbers, and that every item the player holds is an item this version of the game has
(an `update` can retire or rename one). It runs on the plain dict before the game is built from it.

  - Things that cannot be made sense of (an unknown room or class, text where a number belongs) make the save
    damaged, so the title screen offers the previous save instead of the game crashing mid-play.
  - Items the game no longer has are left out and reported, and the original file is copied first, so
    nothing is lost for good.
"""
import copy
import math

from . import gear as gearlib, save, town
from .content import AFFIXES, BUILDINGS, CLASSES, ITEMS, ROOMS

PLAYER_NUMBERS = ("base_hp", "str", "wil", "agi", "vit", "level", "xp", "points", "gold", "bonus_hp", "oil", "hp")
LATER_NUMBERS = ("gems", "dread", "relic_level", "relic_charges")      # not in the earliest saves


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return isinstance(v, int) or math.isfinite(v)


def _bad(what):
    return save.SaveDamaged("This save has %s that this game cannot use." % what)


def check(d):
    """Validate d (a migrated save) and repair what is safe to repair. Returns the ids of items that were left
    out because this version of the game has no such item (empty when nothing was). Raises SaveDamaged."""
    if d["room"] not in ROOMS:
        raise _bad("a room (%r)" % d["room"])
    if d["last_rest"] not in ROOMS:
        raise _bad("a resting place (%r)" % d["last_rest"])
    if not _num(d["difficulty"]) or d["difficulty"] <= 0:
        raise _bad("a difficulty")
    if not all(isinstance(r, str) for r in d["visited"]):
        raise _bad("a list of visited rooms")
    d["visited"] = [r for r in d["visited"] if r in ROOMS]
    gear = d["player"].get("gear") if isinstance(d["player"].get("gear"), dict) else {}
    d["room_items"] = {r: [i for i in v if isinstance(i, str) and (i in ITEMS or i in gear)]    # left on the floor
                       for r, v in d["room_items"].items() if r in ROOMS and isinstance(v, list)}
    if not all(_num(v) for v in d["stats"].values()):
        raise _bad("a statistic")
    if not all(isinstance(v, str) or _num(v) for v in d["quests"].values()):
        raise _bad("a quest stage")
    if not isinstance(d["flags"].get("visited_regions", []), list):
        raise _bad("a list of regions")
    for key in ("town", "forge"):
        if d.get(key) and not isinstance(d[key], dict):
            raise _bad("a %s record" % key)
    dropped = _check_town(d["town"]) if d.get("town") else []
    if d.get("forge"):
        _check_forge(d["forge"], d["player"].get("gear"))
    if "anchors" in d and not isinstance(d["anchors"], list):
        raise _bad("a list of anchors")
    if "settings" in d and not isinstance(d["settings"], dict):
        raise _bad("settings")
    return sorted(set(dropped + _check_player(d["player"])))


def _check_town(t):
    """The town block, with finished or queued buildings this version does not have left out. Returns their ids."""
    dropped = []
    for key in ("invited", "built"):
        if key in t:
            if not isinstance(t[key], list) or not all(isinstance(b, str) for b in t[key]):
                raise _bad("a town list (%s)" % key)
            if key == "built":     # (an invitation to a building that is gone is harmless; a finished one is not)
                dropped += [b for b in t[key] if b not in BUILDINGS]
                t[key] = [b for b in t[key] if b in BUILDINGS]
    if "queue" in t:
        q = t["queue"]
        if not isinstance(q, list) or not all(
                isinstance(e, dict) and isinstance(e.get("id"), str) and _num(e.get("ready_at")) and _num(e.get("steps"))
                for e in q):
            raise _bad("a building queue")
        dropped += [e["id"] for e in q if e["id"] not in BUILDINGS]
        t["queue"] = [e for e in q if e["id"] in BUILDINGS]
    for key in ("rent_banked",):
        if key in t and not _num(t[key]):
            raise _bad("town %s" % key)
    if t.get("rent_since") is not None and not _num(t.get("rent_since")):
        raise _bad("town rent_since")
    if "stash_level" in t and (not _num(t["stash_level"]) or t["stash_level"] not in town.STASH_CAPACITY):
        raise _bad("a stash level")
    return dropped


def _real(iid, gear):
    return isinstance(iid, str) and (iid in gear or iid in ITEMS)


def _check_forge(f, gear):
    if "slots" in f and not _num(f["slots"]):
        raise _bad("forge slots")
    if "heat" in f and not _numbers(f["heat"]):
        raise _bad("forge heat")
    if "jobs" in f:
        jobs = f["jobs"]
        if not isinstance(jobs, list):
            raise _bad("forge jobs")
        for j in jobs:
            if not (isinstance(j, dict) and isinstance(gear, dict) and _real(j.get("item"), gear)
                    and _num(j.get("ready_at")) and _num(j.get("steps")) and isinstance(j.get("slot"), (str, type(None)))
                    and (not j.get("loaner") or _real(j["loaner"], gear))):
                raise _bad("a forge job")
            # (older saves have neither of these; a Godlike forging holds two anvils, a Long Quench is kind "temper")
            if "slots" in j and not (_num(j["slots"]) and int(j["slots"]) == j["slots"] and j["slots"] >= 1):
                raise _bad("a forge job (anvils)")
            if "kind" in j and j["kind"] not in ("forge", "temper"):
                raise _bad("a forge job (kind)")
            if "hurried" in j and not (_num(j["hurried"]) and j["hurried"] >= 0):
                raise _bad("a forge job (hurried days)")


def _numbers(v):
    return isinstance(v, dict) and all(isinstance(k, str) and _num(n) for k, n in v.items())


def _good_gear(key, inst):
    """A forged item is registered as it was saved, so every part of it has to be usable as it stands."""
    if not isinstance(inst, dict) or inst.get("id") != key or inst.get("base") not in ITEMS:
        return False
    if inst.get("rarity") not in gearlib.RARITY_ORDER:
        return False
    for field in ("name", "desc", "kind"):
        if not isinstance(inst.get(field), str):
            return False
    # (relics and spell books carry no stats or mult, and relics have their own relic_mult)
    if not all(_numbers(inst.get(f, {})) for f in ("stats", "mult", "relic_mult")):
        return False
    if not (_num(inst.get("value")) and _num(inst.get("sockets"))):
        return False
    if "temper" in inst and not (_num(inst["temper"]) and 1.0 <= inst["temper"] <= 3.5):      # the Long Quench
        return False
    affixes = inst.get("affixes", [])
    if not isinstance(affixes, list) or any(a not in AFFIXES for a in affixes):
        return False
    relics = inst.get("relics", [])
    if not isinstance(relics, list) or not all(isinstance(r, dict) and r.get("base") in ITEMS
                                               and r.get("rarity") in gearlib.RARITY_ORDER for r in relics):
        return False
    try:
        gearlib.rebuild(copy.deepcopy(inst))     # the pieces it is built from must still fit together
    except Exception:
        return False
    return True


def _check_player(p):
    if not isinstance(p.get("name"), str) or p.get("cls") not in CLASSES:
        raise _bad("a character (name or class)")
    for key in PLAYER_NUMBERS:
        if not _num(p.get(key)):
            raise _bad("a character %s" % key)
    for key in LATER_NUMBERS:
        if key in p and not _num(p[key]):
            raise _bad("a character %s" % key)
    if not isinstance(p.get("lantern"), dict):
        raise _bad("a lantern")
    for part in ("shroud", "lens"):
        p["lantern"].setdefault(part, False)
    gear = p.setdefault("gear", {})
    if not isinstance(gear, dict) or not all(_good_gear(k, i) for k, i in gear.items()):
        raise _bad("forged gear")
    for key in ("inventory", "stash", "equipment"):
        if not isinstance(p.setdefault(key, {}), dict):
            raise _bad("a %s" % key)
    if not isinstance(p.setdefault("spells", []), list):
        raise _bad("a spell list")

    def known(iid):
        # a forged piece must be one the save carries; anything else must be a base item (not a stale instance
        # left in the registry by an earlier game in this process)
        return iid in gear or (isinstance(iid, str) and iid in ITEMS and not ITEMS[iid].get("instance"))

    dropped = []
    for key in ("inventory", "stash"):
        held = {}
        for iid, n in p[key].items():
            if not _num(n) or int(n) != n:
                raise _bad("an item count (%s)" % iid)
            if not known(iid):
                dropped.append(iid)
            else:
                held[iid] = int(n)     # a count of 0 is normal (a spent stack); the game keeps the entry
        p[key] = held
    for slot in ("weapon", "armor", "trinket"):
        p["equipment"].setdefault(slot, None)
    for slot, iid in list(p["equipment"].items()):
        if iid is not None and not known(iid):
            p["equipment"][slot] = None
            dropped.append(iid)
    dropped += [i for i in p["spells"] if not known(i)]
    p["spells"] = [i for i in p["spells"] if known(i)]
    return sorted(set(map(str, dropped)))


def left_out_line(dropped, slot, keep_copy):
    """The one plain line for the player about items that were left out; makes the copy of the original first."""
    where = ""
    if keep_copy:
        try:
            path, _ = save.keep_a_copy(slot, ".trimmed.bak")
            where = " The save as it was is kept at %s." % path
        except OSError as e:
            where = " A copy of the save as it was could not be made (%s)." % e
    return ("This save held things that are not in this version of the game (%s), so they were left out.%s"
            % (", ".join(dropped), where))
