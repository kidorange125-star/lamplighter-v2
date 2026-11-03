"""Brann's forge: raise gear and relics to a higher rarity, for gold, materials and time. Never guaranteed.

State lives in game.forge (plain JSON):
  slots   how many anvils there are (each smith resident adds one)
  jobs    [{"item", "slot", "loaner", "ready_at", "steps", "done", "slots"?, "kind"?}]
          "slots" is how many anvils the job holds (default 1; a Godlike forging holds two) and "kind" is
          "forge" (default) or "temper" (the Long Quench, see quench.py)
  heat    consecutive failures per tier. Heat raises the chance, and a full heat bar is a guaranteed success.

A failed forging never destroys anything: the item comes back unchanged and half the materials are refunded.
While your equipped weapon is in the forge you carry a Loaner of the same weapon, weaker by a stated amount.
"""
import math

from . import clock, gear
from .content import FORGE, ITEMS

GEMS_PER_MINUTE = 0.25


def new_state():
    return {"slots": 1, "jobs": [], "heat": {}}


def state(g):
    st = g.forge
    for k, v in new_state().items():
        st.setdefault(k, v)
    return st


def tiers_for(iid):
    return FORGE["relic_tiers"] if ITEMS[iid]["kind"] == "relic" else FORGE["tiers"]


def rarity_of(iid):
    return ITEMS[iid].get("rarity", "common")


def info(iid):
    """The forging step available to this item, or None if it cannot be forged further."""
    if ITEMS[iid]["kind"] not in ("weapon", "armor", "trinket", "relic") or ITEMS[iid].get("loaner"):
        return None
    return tiers_for(iid).get(rarity_of(iid))


def heat_key(iid):
    return ("relic:" if ITEMS[iid]["kind"] == "relic" else "gear:") + rarity_of(iid)


def heat(g, iid):
    return state(g)["heat"].get(heat_key(iid), 0)


def chance(g, iid):
    t = info(iid)
    h = heat(g, iid)
    if h >= t["pity"]:
        return 1.0
    return min(1.0, t["chance"] + FORGE["heat_bonus"] * h)


def missing(g, iid):
    t = info(iid)
    p = g.player
    out = []
    if t.get("needs_flag") and not g.flags.get(t["needs_flag"]):
        out.append("the third quench (ask Orrin about Aldric's receipts, then Brann and Tamsin)")
    if state(g)["slots"] < slots_needed(iid):
        out.append("a second anvil (build the Ember Smithy)")
    if p.gold < t["gold"]:
        out.append("%d more gold" % (t["gold"] - p.gold))
    for mid, n in t["items"].items():
        have = p.inventory.get(mid, 0)
        if have < n:
            out.append("%d more %s" % (n - have, ITEMS[mid]["name"]))
    return out


def cost_text(iid):
    t = info(iid)
    parts = ["%d gold" % t["gold"]] + ["%d %s" % (n, ITEMS[m]["name"]) for m, n in t["items"].items()]
    return ", ".join(parts)


def candidates(g):
    """Everything the player could put in the forge: [(item_id, where)] where is 'worn' or 'pack'."""
    p = g.player
    out = []
    for slot, iid in p.equipment.items():
        if iid and info(iid):
            out.append((iid, "worn"))
    for iid in p.inventory:
        if info(iid) and iid not in [c[0] for c in out]:
            out.append((iid, "pack"))
    return out


def free_slots(g):
    st = state(g)
    return st["slots"] - sum(j.get("slots", 1) for j in st["jobs"])


def slots_needed(iid):
    """How many anvils forging this item holds at once (a Godlike forging needs both)."""
    t = info(iid)
    return t.get("slots", 1) if t else 1


def slot_block(g, iid):
    """Why the anvils are too busy to start forging this item now ('' when they are free enough)."""
    st = state(g)
    need = slots_needed(iid)
    if st["slots"] < need or free_slots(g) >= need:
        return ""
    if any(j.get("kind") == "temper" for j in st["jobs"]):
        # the Long Quench cannot be collected early, so "collect finished work first" would send the player nowhere
        if need > 1:
            return ("The Long Quench holds one anvil until its week is up (gems can skip two of its days); a Godlike "
                    "forging needs both anvils at once.")
        return "Every forge slot is busy: the Long Quench holds one and the rest are working."
    if need > 1:
        return "This takes both anvils at once. Collect finished work first."
    return "Every forge slot is busy. Collect finished work first."


def _hand_over(g, iid):
    """Take an item out of the player's hands for the forge. A worn weapon is replaced by a weaker loaner of the same
    weapon. Returns (slot, loaner_id): the slot the item was worn in (or None) and the loaner's id (or None)."""
    p = g.player
    slot = next((s for s, v in p.equipment.items() if v == iid), None)
    if slot:
        p.equipment[slot] = None
    else:
        p.remove_item(iid)
    loaner = None
    if slot == "weapon":
        lo = gear.make_loaner(iid, g.rng)
        gear.give(p, lo)
        p.inventory.pop(lo["id"], None)
        p.equipment["weapon"] = lo["id"]
        loaner = lo["id"]
    return slot, loaner


def start(g, iid):
    """Put an item in the forge. Returns (ok, message)."""
    st = state(g)
    p = g.player
    if not info(iid):
        return False, "That cannot be forged any further."
    block = slot_block(g, iid)
    if block:
        return False, block
    need = slots_needed(iid)
    lack = missing(g, iid)
    if lack:
        return False, "You still need " + ", ".join(lack) + "."
    t = info(iid)
    p.gold -= t["gold"]
    for mid, n in t["items"].items():
        p.remove_item(mid, n)
    slot, loaner = _hand_over(g, iid)
    st["jobs"].append({"item": iid, "slot": slot, "loaner": loaner, "done": False,
                       "ready_at": clock.now() + t["minutes"] * 60, "steps": t["steps"],
                       "slots": need, "kind": "forge"})
    return True, "ok"


def minutes_left(job):
    return max(0, math.ceil((job["ready_at"] - clock.now()) / 60))


def hurry_cost(job):
    if job.get("kind") == "temper":
        from . import quench
        return quench.hurry_cost(job)
    return max(1, math.ceil(minutes_left(job) * GEMS_PER_MINUTE))


def hurry(g, index):
    job = state(g)["jobs"][index]
    if job.get("kind") == "temper":
        from . import quench
        return quench.hurry(g, index)
    if job["done"] or g.player.gems < hurry_cost(job):
        return False
    g.player.gems -= hurry_cost(job)
    job["done"] = True
    return True


def update(g):
    for job in state(g)["jobs"]:
        if not job["done"] and (clock.now() >= job["ready_at"] or job["steps"] <= 0):
            job["done"] = True
            name = ITEMS[job["item"]]["name"]
            if job.get("kind") == "temper":
                g.notice("{bgreen}The Long Quench of your %s is done. It is ready at the forge.{/}" % name)
            else:
                g.notice("{bgreen}Your %s is ready at Brann's forge.{/}" % name)


def on_step(g):
    for job in state(g)["jobs"]:
        if not job["done"]:
            job["steps"] -= 1
    update(g)


def ready_jobs(g):
    return [i for i, j in enumerate(state(g)["jobs"]) if j["done"]]


def collect(g, index):
    """Finish a job. Returns a result dict for the reveal: before, after, success, item, name, chance, heat.
    A Long Quench (kind "temper") is settled by quench.collect and returns {"kind": "temper", ...}."""
    st = state(g)
    job = st["jobs"].pop(index)
    p = g.player
    iid = job["item"]
    if job.get("kind") == "temper":
        from . import quench
        return quench.collect(g, job)
    t = info(iid)
    before = rarity_of(iid)
    odds = chance(g, iid)
    hk = heat_key(iid)
    h = st["heat"].get(hk, 0)
    success = h >= t["pity"] or g.rng.random() < odds
    if success:
        st["heat"][hk] = 0
        if gear.is_instance(iid):
            inst = gear.upgrade(ITEMS[iid], t["to"], g.rng)
            result = inst["id"]
            p.inventory[result] = 1      # (start took it out of the pack; the equip step below moves it if it was worn)
        else:
            inst = gear.make(iid, t["to"], g.rng)
            gear.give(p, inst)
            result = inst["id"]
        after = t["to"]
    else:
        st["heat"][hk] = h + 1
        for mid, n in t["items"].items():
            back = int(n * FORGE["refund"])
            if back:
                p.add_item(mid, back)
        result = iid
        after = before
        if gear.is_instance(iid):
            p.inventory[iid] = 1
        else:
            p.add_item(iid)
    # hand back the real thing in place of the loaner
    if job["loaner"]:
        gear.discard(p, job["loaner"])
    if job["slot"] and p.equipment.get(job["slot"]) is None:
        p.inventory.pop(result, None)
        p.equipment[job["slot"]] = result
    return {"before": before, "after": after, "success": success, "item": result, "name": ITEMS[result]["name"],
            "chance": odds, "heat": st["heat"].get(hk, 0), "slot": job["slot"]}


# ---------------------------------------------------------------------------- relics and sockets
def socketable_hosts(g):
    p = g.player
    ids = [v for v in p.equipment.values() if v] + [i for i in p.inventory]
    seen, out = set(), []
    for iid in ids:
        if iid in seen or ITEMS[iid]["kind"] not in ("weapon", "armor", "trinket") or ITEMS[iid].get("loaner"):
            continue
        seen.add(iid)
        if gear.sockets_of(iid) > 0:
            out.append(iid)
    return out


def relics_in_pack(g):
    return [i for i in g.player.inventory if ITEMS[i]["kind"] == "relic"]


def socket_in(g, host, relic):
    """Put a relic from the pack into a host item. Returns the host's (possibly new) id."""
    p = g.player
    host = gear.as_instance(p, host, g.rng)
    h = ITEMS[host]
    if len(h["relics"]) >= h["sockets"]:
        return None
    h["relics"].append({"base": gear.base_id(relic), "rarity": rarity_of(relic)})
    gear.rebuild(h)
    if gear.is_instance(relic):
        gear.discard(p, relic)
    else:
        p.remove_item(relic)
    return host


def take_out(g, host, index):
    """Remove a socketed relic and put it back in the pack. Nothing is lost."""
    p = g.player
    h = ITEMS[host]
    rel = h["relics"].pop(index)
    gear.rebuild(h)
    if rel["rarity"] == "common":
        p.add_item(rel["base"])
        return rel["base"]
    inst = gear.make(rel["base"], rel["rarity"], g.rng, affixes=[])
    gear.give(p, inst)
    return inst["id"]
