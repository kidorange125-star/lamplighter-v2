"""Gear instances: forged items with their own rarity, affixes, sockets and relics.

A plain item from the shop is a base item (`ITEMS["hauberk"]`). Forging, socketing, or finding a rolled
item produces an *instance*: a one-of-a-kind copy with its own id ("g12"). Instances are registered in
ITEMS under that id, so every part of the game that looks an item up (the pack, shops, stash, equipment,
combat) treats them exactly like base items. Instances are saved with the player and re-registered on load.

Power comes from stacking: rarity scales the base stats and, for weapons, adds a damage multiplier; affixes
add stats or multipliers; relics socketed into the item add more multipliers. All multipliers multiply.
"""
from .content import AFFIXES, FORGE, ITEMS, RELIC_INFO, SPELLS

RARITY_ORDER = ["common", "uncommon", "rare", "epic", "ultra", "legendary", "godlike"]
# Calibrated with tools/sim_power.py: from Rare upward each tier is 1.4x the stats and 1.2x the weapon multiplier.
# Against a late-game boss (the King at 2.5x health and damage) that gives about Epic 12%, Ultra 33%,
# Legendary 58%, Godlike 83% wins with the game's suggested play, the ladder in docs/V2-PLAN.md section 2.4.
POWER = {"common": 1.0, "uncommon": 1.1, "rare": 1.25, "epic": 1.75, "ultra": 2.45, "legendary": 3.43, "godlike": 4.8}
WEAPON_MULT = {"common": 1.0, "uncommon": 1.0, "rare": 1.0, "epic": 1.20, "ultra": 1.44, "legendary": 1.73,
               "godlike": 2.07}
SOCKETS = {"common": 0, "uncommon": 0, "rare": 1, "epic": 1, "ultra": 2, "legendary": 3, "godlike": 3}
AFFIX_COUNT = {"epic": 1, "ultra": 2, "legendary": 2, "godlike": 3}
VALUE = {"common": 1, "uncommon": 1.5, "rare": 3, "epic": 8, "ultra": 20, "legendary": 60, "godlike": 200}
MULT_NAMES = {"dmg": "all damage", "phys": "weapon damage", "fire": "fire damage", "light": "flare damage",
              "heal": "healing"}

_counter = [0]


def _new_id():
    _counter[0] += 1
    return "g%d" % _counter[0]


def register(inst):
    ITEMS[inst["id"]] = inst
    try:
        _counter[0] = max(_counter[0], int(inst["id"][1:]))
    except ValueError:
        pass


def register_all(instances):
    for inst in instances.values():
        register(inst)


def is_instance(iid):
    return bool(ITEMS.get(iid, {}).get("instance"))


def base_id(iid):
    return ITEMS[iid].get("base", iid)


def rarity_index(r):
    return RARITY_ORDER.index(r)


def _scale(v, f):
    if v == 0:
        return 0
    out = max(1, round(abs(v) * f))
    return out if v > 0 else -out


def rebuild(inst):
    """Recompute everything derived: stats, multipliers, sockets, name, value, description."""
    b = ITEMS[inst["base"]]
    r = inst["rarity"]
    if b["kind"] == "book":
        from . import spells as _spells
        plus = inst.get("plus", 0)
        inst.update(kind="book", spell=b["spell"], element=b["element"], sockets=0, stats={}, mult={},
                    name="Tome of %s%s" % (SPELLS[b["spell"]]["name"], " +%d" % plus if plus else ""),
                    value=max(1, int(b["value"] * VALUE[r])))
        inst["desc"] = _spells.describe(b["spell"], r, plus)
        return inst
    if b["kind"] == "relic":
        key = RELIC_INFO["types"][b["relic"]]["key"]
        gain = RELIC_INFO["scale"][r]
        inst.update(kind="relic", relic=b["relic"], name=b["name"], sockets=0,
                    value=max(1, int(b["value"] * VALUE[r])), relic_mult={key: round(1 + gain, 4)})
        inst["desc"] = "%s +%d%% %s while socketed. Socket it into gear at Brann's forge." % (
            RELIC_INFO["types"][b["relic"]]["blurb"], round(gain * 100), MULT_NAMES[key])
        return inst
    nat = b.get("rarity", "common")
    f = POWER[r] / POWER[nat]
    stats = {k: _scale(v, f) for k, v in b.get("stats", {}).items()}
    mult = {k: v for k, v in b.get("mult", {}).items()}
    if b["kind"] == "weapon":
        mult["dmg"] = mult.get("dmg", 1.0) * WEAPON_MULT[r] / WEAPON_MULT[nat]
    affix_f = 1 + max(0, rarity_index(r) - rarity_index("rare")) * 0.25
    prefixes, suffixes = [], []
    for aid in inst.get("affixes", []):
        a = AFFIXES[aid]
        for k, v in a.get("stats", {}).items():
            stats[k] = stats.get(k, 0) + _scale(v, affix_f)
        for k, v in a.get("mult", {}).items():
            mult[k] = mult.get(k, 1.0) * (1 + (v - 1) * affix_f)
        (prefixes if a["pos"] == "prefix" else suffixes).append(a["name"])
    relic_lines = []
    for rel in inst.get("relics", []):
        rb = ITEMS[rel["base"]]
        key = RELIC_INFO["types"][rb["relic"]]["key"]
        gain = RELIC_INFO["scale"][rel["rarity"]]
        mult[key] = mult.get(key, 1.0) * (1 + gain)
        relic_lines.append("%s (%s)" % (rb["name"], rel["rarity"]))
    if inst.get("loaner"):
        mult["dmg"] = mult.get("dmg", 1.0) * FORGE["loaner_penalty"]
    # the Long Quench (quench.py): a Godlike weapon's tempering multiplies every kind of damage, relics or not
    temper = inst.get("temper") if not inst.get("loaner") else None
    if temper:
        mult["dmg"] = mult.get("dmg", 1.0) * temper
    name = " ".join(prefixes + [b["name"]] + suffixes)
    if temper:
        name = "Long-Quenched " + name
    if inst.get("loaner"):
        name = "Loaner " + name
    inst.update(stats=stats, mult={k: round(v, 4) for k, v in mult.items() if abs(v - 1.0) > 1e-9},
                sockets=SOCKETS[r], name=name, value=max(1, int(b["value"] * VALUE[r] / VALUE[nat])))
    desc = b["desc"]
    if inst.get("loaner"):
        desc = "A stand-in while the forge has your real weapon: %d%% weaker. " % round((1 - FORGE["loaner_penalty"]) * 100) + desc
    if SOCKETS[r]:
        desc += " Sockets %d/%d%s." % (len(relic_lines), SOCKETS[r], (": " + ", ".join(relic_lines)) if relic_lines else "")
    if temper:
        desc += " Long-Quenched: all damage x%.1f." % temper
    inst["desc"] = desc
    return inst


def _roll_affixes(inst, rng, want):
    pool = [a for a in AFFIXES.values() if inst["kind"] in a["slots"] and a["id"] not in inst["affixes"] and not a.get("curse")]
    # a curse (only the Dealer's bargains carry one) is a cost, not one of the piece's affixes: it must not fill a slot
    while sum(1 for a in inst["affixes"] if not AFFIXES[a].get("curse")) < want and pool:
        a = pool.pop(rng.randrange(len(pool)))
        inst["affixes"].append(a["id"])


def make(base, rarity, rng, affixes=None, relics=None, loaner=False):
    """Create and register a new instance of a base item at the given rarity."""
    b = ITEMS[base]
    inst = {"id": _new_id(), "instance": True, "base": base, "kind": b["kind"], "rarity": rarity,
            "affixes": list(affixes) if affixes is not None else [], "relics": list(relics or [])}
    if loaner:
        inst["loaner"] = True
    if affixes is None and b["kind"] in ("weapon", "armor", "trinket"):
        _roll_affixes(inst, rng, AFFIX_COUNT.get(rarity, 0))
    rebuild(inst)
    register(inst)
    return inst


def upgrade(inst, rarity, rng):
    """Raise an instance to a higher rarity, topping up its affixes. The id stays the same."""
    inst["rarity"] = rarity
    if inst["kind"] in ("weapon", "armor", "trinket"):
        _roll_affixes(inst, rng, AFFIX_COUNT.get(rarity, 0))
    rebuild(inst)
    return inst


def make_loaner(original, rng):
    """A stand-in for a weapon that is in the forge: the same weapon at the same rarity and with the same affixes
    (but no relics, which stay with the original), weaker by the stated penalty."""
    affixes = list(ITEMS[original].get("affixes", [])) if is_instance(original) else []
    return make(base_id(original), ITEMS[original].get("rarity", "common"), rng, affixes=affixes, loaner=True)


# ---------------------------------------------------------------------------- the player's gear
def give(p, inst):
    p.gear[inst["id"]] = inst
    p.inventory[inst["id"]] = 1


def discard(p, iid):
    """Remove an instance from everywhere it could be."""
    p.inventory.pop(iid, None)
    p.gear.pop(iid, None)
    p.stash.pop(iid, None)
    if iid in p.spells:
        p.spells.remove(iid)
    for slot, v in list(p.equipment.items()):
        if v == iid:
            p.equipment[slot] = None


def sockets_of(iid):
    """How many relic sockets this item has, instance or base."""
    it = ITEMS[iid]
    if it["kind"] not in ("weapon", "armor", "trinket"):
        return 0
    return SOCKETS[it.get("rarity", "common")]


def socketed(iid):
    return list(ITEMS[iid].get("relics", [])) if is_instance(iid) else []


def as_instance(p, iid, rng):
    """Make sure an item is an instance (a base item becomes one of the same rarity). Returns the instance id."""
    if is_instance(iid):
        return iid
    inst = make(iid, ITEMS[iid].get("rarity", "common"), rng, affixes=[])
    p.gear[inst["id"]] = inst
    if iid in p.inventory:
        p.remove_item(iid)
        p.inventory[inst["id"]] = 1
    for slot, v in list(p.equipment.items()):
        if v == iid:
            p.equipment[slot] = inst["id"]
    return inst["id"]
