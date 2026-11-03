"""Checks that all game content is consistent: every reference points at something real.

Run `python tools/validate_content.py` after editing anything in lamplighter/data.
"""
import json
import os
from collections import deque

from . import areas, dealer, npcs
from .combat import Combat
from .content import (BUILDINGS, CLASSES, DATA_DIR, DEALER, ENEMIES, FORGE, ITEMS, PAGES, REGION_INFO, REGION_NAMES,
                      RELIC_INFO, ROOMS, SKILLS, SPELLS, SPELL_RULES)
from .entities import STATUS_INFO

OPPOSITE = {"n": "s", "s": "n", "e": "w", "w": "e", "u": "d", "d": "u"}
ITEM_KINDS = {"weapon", "armor", "trinket", "consumable", "key", "page", "junk", "material", "relic", "book"}
MOVE_KINDS = {"attack", "heavy", "defend", "heal", "buff", "debuff", "summon", "drain", "shroud", "charge"}
RARITIES = {"common", "uncommon", "rare", "epic", "ultra", "legendary", "godlike"}
MULT_KEYS = {"dmg", "phys", "fire", "light", "heal", "ice", "water", "shadow", "earth", "spell"}
STAT_KEYS = {"atk", "def", "wil", "agi", "str", "hp", "crit", "dodge", "regen", "oil_save"}
START_ROOM = "hall"
LOCK_KINDS = ("item", "flag", "flags", "shards", "building", "element", "relic", "dread", "all")


def check_lock(lock, where, err, top=True):
    """Problems in one lock (a room exit's lock or an `all` sub-lock). `where` names it in the messages."""
    from .elements import ELEMENTS
    if not any(k in lock for k in LOCK_KINDS):
        err("%s has no requirement" % where)
    if sum(1 for k in LOCK_KINDS if k in lock) > 1:
        err("%s: combine requirements with 'all', not several keys in one lock" % where)
    if top and "msg" not in lock:
        err("%s has no message" % where)
    if "remember" in lock and not isinstance(lock["remember"], str):
        err("%s: remember must be a flag name" % where)
    if "item" in lock and lock["item"] not in ITEMS:
        err("%s needs unknown item %s" % (where, lock["item"]))
    if "building" in lock and lock["building"] not in BUILDINGS:
        err("%s needs unknown building %s" % (where, lock["building"]))
    for el in lock.get("element", []):
        if el not in ELEMENTS:
            err("%s needs unknown element %s" % (where, el))
    if "flags" in lock:
        fl = lock["flags"]
        if not isinstance(fl, list) or not fl or not all(isinstance(f, str) for f in fl):
            err("%s: flags must be a non-empty list of flag names" % where)
    if "relic" in lock:
        types = lock["relic"] if isinstance(lock["relic"], list) else [lock["relic"]]
        if not types or any(t not in RELIC_INFO["types"] for t in types):
            err("%s: relic %r is not a relic type (%s)" % (where, lock["relic"], ", ".join(RELIC_INFO["types"])))
    if "dread" in lock:
        d = lock["dread"]
        ok = isinstance(d, dict) and d and set(d) <= {"min", "max"} and all(
            isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 for v in d.values())
        if not ok:
            err("%s: dread needs an int min and/or max between 0 and 100" % where)
        elif d.get("min", 0) > d.get("max", 100):
            err("%s: dread min is above max" % where)
    if "all" in lock:
        subs = lock["all"]
        if not isinstance(subs, list) or not subs or not all(isinstance(x, dict) for x in subs):
            err("%s: all must be a non-empty list of locks" % where)
        else:
            for i, sub in enumerate(subs):
                check_lock(sub, "%s, part %d" % (where, i + 1), err, top=False)


def _item_ids(node):
    """Every item id named under an "items" key anywhere in a forge-shaped structure (a dict of counts or a list)."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "items" and isinstance(v, dict):
                out.extend(v)
            elif k == "items" and isinstance(v, list):
                out.extend(x for x in v if isinstance(x, str))
            else:
                out.extend(_item_ids(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_item_ids(v))
    return out


def check_field(rid, field, err):
    """A room's damage field: {"name", "msg"?, <element>: 0.5 to 1.5}."""
    from .elements import ELEMENTS
    if not isinstance(field, dict) or not isinstance(field.get("name"), str) or not field["name"]:
        err("room %s: a field needs a name" % rid)
        return
    for k, v in field.items():
        if k in ("name", "msg"):
            if not isinstance(v, str):
                err("room %s: field %s must be text" % (rid, k))
        elif k not in ELEMENTS:
            err("room %s: field key %r is not an element" % (rid, k))
        elif not isinstance(v, (int, float)) or isinstance(v, bool) or not 0.5 <= v <= 1.5:
            err("room %s: field %s=%r is outside 0.5 to 1.5" % (rid, k, v))
    if not any(k in ELEMENTS for k in field):
        err("room %s: a field needs at least one element" % rid)


def check_attune(eid, e, err):
    """An enemy's rotating weakness: {"every": n, "stances": [{"name", "weak", "resist"?, "msg"?}, ...]}."""
    from .elements import ELEMENTS
    a = e["attune"]
    if not isinstance(a, dict) or not isinstance(a.get("every"), int) or isinstance(a.get("every"), bool) or a["every"] < 1:
        err("enemy %s: attune needs every >= 1" % eid)
        return
    stances = a.get("stances")
    if not isinstance(stances, list) or not 2 <= len(stances) <= 4:
        err("enemy %s: attune needs 2 to 4 stances" % eid)
        return
    names, sigs = set(), set()
    for i, st in enumerate(stances):
        tag = "enemy %s: attune stance %d" % (eid, i + 1)
        if not isinstance(st, dict) or not isinstance(st.get("name"), str) or not st["name"]:
            err("%s needs a name" % tag)
            continue
        weak, resist = st.get("weak", []), st.get("resist", [])
        if not isinstance(weak, list) or not 1 <= len(weak) <= 2:
            err("%s needs 1 to 2 weak elements" % tag)
        if not isinstance(resist, list) or len(resist) > 2:
            err("%s may have at most 2 resist elements" % tag)
        if not isinstance(weak, list) or not isinstance(resist, list):
            continue
        bad = [el for el in weak + resist if not isinstance(el, str) or el not in ELEMENTS]
        for el in bad:
            err("%s: unknown element %r" % (tag, el))
        if bad:
            continue                      # the overlap and light checks below need real element names
        if len(set(weak)) != len(weak) or len(set(resist)) != len(resist):
            err("%s lists an element twice" % tag)
        if set(weak) & set(resist):
            err("%s is both weak and resistant to the same element" % tag)
        if "hollow" in e.get("tags", []) and "light" in weak:
            err("%s: a hollow enemy cannot be weak to light" % tag)
        if "msg" in st and not isinstance(st["msg"], str):
            err("%s: msg must be text" % tag)
        sig = (frozenset(weak), frozenset(resist))
        if st["name"] in names:
            err("%s repeats the stance name %r" % (tag, st["name"]))
        if sig in sigs:
            err("%s has the same weak and resist as another stance, so the rotation would change nothing" % tag)
        names.add(st["name"])
        sigs.add(sig)


def validate():
    errs = []

    def err(msg):
        errs.append(msg)

    # ---- items
    for iid, it in list(ITEMS.items()):
        if it.get("instance"):
            continue                                    # forged gear made during play (a Long Quench pushes dmg past 5)
        for k in ("name", "kind", "value", "desc"):
            if k not in it:
                err("item %s: missing %s" % (iid, k))
        if it.get("kind") not in ITEM_KINDS:
            err("item %s: unknown kind %r" % (iid, it.get("kind")))
        for k in it.get("stats", {}):
            if k not in STAT_KEYS:
                err("item %s: unknown stat %r" % (iid, k))
        for k, v in it.get("mult", {}).items():
            if k not in MULT_KEYS:
                err("item %s: unknown multiplier %r" % (iid, k))
            elif not 0.5 <= v <= 5:
                err("item %s: multiplier %s=%r is outside 0.5 to 5" % (iid, k, v))
        if it.get("rarity", "common") not in RARITIES:
            err("item %s: unknown rarity %r" % (iid, it.get("rarity")))
        if it.get("mult") and it.get("kind") not in ("weapon", "armor", "trinket"):
            err("item %s: only equipment can carry multipliers" % iid)
    for pid in PAGES:
        if pid not in ITEMS:
            err("page %s has no matching item" % pid)

    # ---- classes and skills
    for cid, c in CLASSES.items():
        for sid in c["skills"]:
            if sid not in SKILLS:
                err("class %s: unknown skill %s" % (cid, sid))
        for g in c["gear"]:
            if g not in ITEMS:
                err("class %s: unknown starting gear %s" % (cid, g))
    for sid in SKILLS:
        if not hasattr(Combat, "skill_" + sid):
            err("skill %s has no handler Combat.skill_%s" % (sid, sid))

    # ---- enemies
    for eid, e in ENEMIES.items():
        for k in ("name", "hp", "atk", "moves", "xp"):
            if k not in e:
                err("enemy %s: missing %s" % (eid, k))
        moves = list(e.get("moves", []))
        for ph in e.get("phases", []):
            moves += ph.get("moves", [])
            st = ph.get("status")
            if st and st[0] not in STATUS_INFO:
                err("enemy %s: phase status %r unknown" % (eid, st[0]))
        for m in moves:
            if m.get("kind") not in MOVE_KINDS:
                err("enemy %s: move %r has unknown kind" % (eid, m.get("name")))
            if m.get("kind") == "summon" and m.get("summon") not in ENEMIES:
                err("enemy %s: summons unknown %s" % (eid, m.get("summon")))
            if m.get("kind") == "charge" and m.get("then") not in e.get("extra_moves", {}):
                err("enemy %s: charge leads to missing extra move %r" % (eid, m.get("then")))
            st = m.get("status")
            if st and st[0] not in STATUS_INFO:
                err("enemy %s: move %r applies unknown status %r" % (eid, m.get("name"), st[0]))
        for iid, chance in e.get("drops", []):
            if iid not in ITEMS:
                err("enemy %s: drops unknown item %s" % (eid, iid))
            if not 0 <= chance <= 1:
                err("enemy %s: drop chance %r out of range" % (eid, chance))

    # ---- rooms
    seen_pos = {}
    for rid, r in ROOMS.items():
        if r.get("region") not in REGION_NAMES:
            err("room %s: unknown region %r" % (rid, r.get("region")))
        key = (r.get("region"), r.get("pos"))
        if key in seen_pos:
            err("room %s and %s share map position %s" % (rid, seen_pos[key], r.get("pos")))
        seen_pos[key] = rid
        for d, dest in r["exits"].items():
            if d not in OPPOSITE:
                err("room %s: bad direction %r" % (rid, d))
            elif dest not in ROOMS:
                err("room %s: exit %s leads to unknown room %s" % (rid, d, dest))
            elif ROOMS[dest]["exits"].get(OPPOSITE[d]) != rid:
                err("room %s: exit %s to %s is one-way" % (rid, d, dest))
        for d, dest in r["exits"].items():
            # the map draws compass exits on a grid, so same-region neighbours must be next door
            if d in ("n", "s", "e", "w") and dest in ROOMS and ROOMS[dest]["region"] == r["region"]:
                dx, dy = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}[d]
                want = (r["pos"][0] + dx, r["pos"][1] + dy)
                if ROOMS[dest]["pos"] != want:
                    err("room %s: exit %s to %s is not on the neighbouring map square (expected %s, is %s)"
                        % (rid, d, dest, want, ROOMS[dest]["pos"]))
        for d, lock in r.get("locks", {}).items():
            if d not in r["exits"]:
                err("room %s: lock on missing exit %s" % (rid, d))
            check_lock(lock, "room %s: lock on %s" % (rid, d), err)
        for iid in r.get("items", []):
            if iid not in ITEMS:
                err("room %s: unknown item %s" % (rid, iid))
        for n in r.get("npcs", []):
            if n not in npcs.NPCS:
                err("room %s: unknown npc %s" % (rid, n))
        groups = r.get("enc", {}).get("groups", [])
        for g, w in groups:
            for e in g:
                if e not in ENEMIES:
                    err("room %s: encounter uses unknown enemy %s" % (rid, e))
        for e in r.get("fixed", {}).get("enemies", []):
            if e not in ENEMIES:
                err("room %s: fixed fight uses unknown enemy %s" % (rid, e))

    # ---- spells and elements
    from .elements import ELEMENTS
    for sid, sp in SPELLS.items():
        if sp["element"] not in ELEMENTS + ["all"]:
            err("spell %s: unknown element %r" % (sid, sp["element"]))
        for fx in sp["effects"]:
            if fx["type"] not in ("status", "drain", "shield", "cleanse_self"):
                err("spell %s: unknown effect %r" % (sid, fx["type"]))
            if fx["type"] == "status" and fx["status"] not in STATUS_INFO:
                err("spell %s: unknown status %r" % (sid, fx["status"]))
        if sp["target"] not in ("enemy", "all"):
            err("spell %s: bad target %r" % (sid, sp["target"]))
    for e in ELEMENTS:
        if e not in SPELLS:
            err("element %s has no spell" % e)
        if ITEMS.get("book_" + e, {}).get("spell") != e:
            err("element %s: missing or wrong book_%s item" % (e, e))
        if "essence_" + e not in ITEMS:
            err("element %s: missing essence item" % e)
    if ITEMS.get("book_apex", {}).get("spell") != "apex":
        err("missing book_apex item")
    for a in ELEMENTS:
        for b in ELEMENTS:
            if a < b:
                key = a + "+" + b
                if SPELL_RULES["combos"].get(key) not in ELEMENTS:
                    err("combo %s has no valid result element" % key)
    for eid, e in ENEMIES.items():
        for k in ("weak", "resist"):
            for el in e.get(k, []):
                if el not in ELEMENTS:
                    err("enemy %s: unknown element %r in %s" % (eid, el, k))
        if set(e.get("weak", [])) & set(e.get("resist", [])):
            err("enemy %s is both weak and resistant to the same element" % eid)

    # ---- buildings
    for bid, b in BUILDINGS.items():
        if b["room"] not in ROOMS:
            err("building %s: unknown room %s" % (bid, b["room"]))
        if b["resident"] not in npcs.NPCS:
            err("building %s: unknown resident %s" % (bid, b["resident"]))
        for iid in b["cost"].get("items", {}):
            if iid not in ITEMS:
                err("building %s: costs unknown item %s" % (bid, iid))
        if not any(l.get("building") == bid for r in ROOMS.values() for l in r.get("locks", {}).values()):
            err("building %s has no vacant-plot lock in any room" % bid)

    # ---- every room reachable from the start, ignoring locks
    if START_ROOM not in ROOMS:
        err("start room %s does not exist" % START_ROOM)
    else:
        seen = {START_ROOM}
        queue = deque([START_ROOM])
        while queue:
            for dest in ROOMS[queue.popleft()]["exits"].values():
                if dest in ROOMS and dest not in seen:
                    seen.add(dest)
                    queue.append(dest)
        for rid in ROOMS:
            if rid not in seen:
                err("room %s cannot be reached from %s" % (rid, START_ROOM))

    # ---- power rolls, boss rooms, beacons, element locks, curses
    from . import elements, events
    from .content import AFFIXES
    element_names = set(elements.ELEMENTS)
    for eid, e in ENEMIES.items():
        for k in ("weak", "resist"):
            for el in e.get(k, []):
                if el not in element_names:
                    err("enemy %s: %s lists unknown element %s" % (eid, k, el))
        roll = e.get("roll")
        if roll is None:
            continue
        if "boss" not in e.get("tags", []):
            err("enemy %s: only bosses can roll a power" % eid)
        pron = roll.get("pron")
        if pron is not None and not (isinstance(pron, dict) and all(isinstance(pron.get(k), str) and pron[k]
                                                                     for k in ("subj", "obj", "poss"))):
            err("enemy %s: roll.pron needs subj, obj and poss" % eid)
        if "place" in roll and not isinstance(roll["place"], str):
            err("enemy %s: roll.place must be text" % eid)
        if len(roll.get("flavour", [])) != 5:
            err("enemy %s: a power roll needs exactly 5 lines of flavour (one per band)" % eid)
        for b in roll.get("bonus", []):
            if b.get("item") not in ITEMS:
                err("enemy %s: roll bonus drops unknown item %s" % (eid, b.get("item")))
            if not b.get("from", 0) < b.get("to", 0) <= 100:
                err("enemy %s: roll bonus for %s needs from < to <= 100" % (eid, b.get("item")))
    for rid, r in ROOMS.items():
        flag = r.get("boss")
        if flag and flag != "ending":
            if (r.get("fixed", {}).get("flag") != flag and not hasattr(events, "enter_" + rid)
                    and rid not in areas.collect("ENTER")):
                err("room %s: boss flag %s is never set (no fixed fight, no enter_%s event and no area ENTER hook)"
                    % (rid, flag, rid))
        if r.get("beacon") and not flag:
            err("room %s: a beacon needs a boss flag to guard it" % rid)
        wake = r.get("wake")
        if wake is not None and (not isinstance(wake, str) or wake.count("%d") > 1 or "%" in wake.replace("%d", "", 1)):
            err("room %s: wake must be text with at most one %%d and no other %%" % rid)
        for key in ("beacon_text", "waypost_text"):
            if key in r and not isinstance(r[key], str):
                err("room %s: %s must be text" % (rid, key))
        if "no_dealer" in r and not isinstance(r["no_dealer"], bool):
            err("room %s: no_dealer must be true or false" % rid)
        if "field" in r:
            check_field(rid, r["field"], err)
    for eid, e in ENEMIES.items():
        if "attune" in e:
            check_attune(eid, e, err)
    for aid, a in AFFIXES.items():
        vals = list(a.get("stats", {}).values())
        if a.get("curse") and any(v >= 0 for v in vals):
            err("affix %s: a curse must only have negative stats" % aid)
        if not a.get("curse") and any(v < 0 for v in vals):
            err("affix %s: only a curse may have negative stats" % aid)

    # ---- the Darkness Dealers
    errs.extend(dealer.check(DEALER))
    for info in REGION_INFO.values():
        if "dealer" in info and not isinstance(info["dealer"], bool):
            err("region %s: dealer must be true or false" % info["id"])
        after = info.get("dealer_after")
        if "dealer_after" in info and not isinstance(after, str):
            err("region %s: dealer_after must be a flag name" % info["id"])
        elif isinstance(after, str) and after.startswith("beacon_") and after[len("beacon_"):] not in REGION_NAMES:
            err("region %s: dealer_after %r names no region" % (info["id"], after))

    # ---- the forge and the smiths
    smith = os.path.join(DATA_DIR, "smith.json")
    ids = _item_ids(FORGE)
    if os.path.exists(smith):
        with open(smith, encoding="utf-8") as f:
            ids += _item_ids(json.load(f))
    for iid in sorted(set(ids)):
        if iid not in ITEMS:
            err("forge/smith data: unknown item %s" % iid)

    # ---- area modules
    for key in ("ENTER", "AFTER_BEACON"):
        for k in areas.collect(key):
            if (key == "ENTER" and k not in ROOMS) or (key == "AFTER_BEACON" and k not in REGION_NAMES):
                err("area hook %s: unknown %s %r" % (key, "room" if key == "ENTER" else "region", k))
    for key in ("UNLOCK", "LEAVE"):
        for (a, b) in areas.collect(key):
            if a not in ROOMS:
                err("area hook %s: unknown room %r" % (key, a))
    for k, tip in areas.collect("BOSS_TIPS").items():
        if k not in ROOMS:
            err("area boss tip: unknown room %r" % k)
    for k in areas.collect("AFTER_GAIN"):
        if k not in ITEMS:
            err("area hook AFTER_GAIN: unknown item %r" % k)
    for k in areas.collect("PRICES"):
        if k not in ITEMS:
            err("area hook PRICES: unknown item %r" % k)
    for key in ("TOPICS", "EXTRA_NEWS", "SELLS"):
        for k in areas.merged(key):
            if k not in npcs.NPCS:
                err("area hook %s: unknown npc %r" % (key, k))
    errs.extend(areas.check())

    # ---- npcs and shops
    for nid, n in npcs.NPCS.items():
        if not hasattr(npcs, "talk_" + nid):
            err("npc %s has no talk_%s function" % (nid, nid))
    for nid, stock in npcs.STOCK.items():
        if nid not in npcs.NPCS:
            err("shop stock for unknown npc %s" % nid)
        for iid in stock:
            if iid not in ITEMS and iid != "lens":
                err("shop %s sells unknown item %s" % (nid, iid))
    return errs
