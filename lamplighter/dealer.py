"""The Darkness Dealers: gear and relics for gems, only in the dark.

There is one Dealer in each ring (the Weeping Wood, the Saltmarsh, the Underdeep, the Ember Court) and none in
Hollowmere. Each day a Dealer sits in one dark, ordinary room of its ring (never a boss room, a rest room, a fixed
fight or a waypost), stays there all day, and is somewhere else tomorrow. Light the room and the Dealer moves on.
The beacon of a ring lights all of it, and then that ring has no Dealer. A room whose only way in is a locked door is
never a seat, and nobody sees him at all while their lantern is dry.

Each day's cloth has four wares: two fair pieces of gear, a bargain (a tier up, to the ring's limit, cursed in plain
sight, with relics already socketed) and a loose relic. Fair gear arrives with a relic socketed when its rarity has a
socket. A socketed relic costs what the same relic costs loose, because the forge hands it back; the bargain's
discount is only on the gear. Everything is shown before you pay and what you see is exactly what you get: a ware's id
carries the day, so a menu left open past midnight cannot sell you tomorrow's item. Gems never buy Godlike.

Tunables (prices, odds, restocks) live in data/dealer.json. State lives only in game.dealers:
  salt      re-rolls the whole world's cloth (0 normally)
  bought    {day: ["ring:cloth:slot", ...]}  what has been sold today (older days are dropped)
  restocks  {day: n}  how many times the cloth was turned today, shared by all the Dealers
"""
import math
import random

from . import clock, gear, rarity, ui
from .content import AFFIXES, DEALER, ITEMS, REGION_INFO, RELIC_INFO, ROOMS
from .ui import blank, say

CAP = "legendary"          # gems never buy anything above this
SLOT_NAMES = ["fair", "fair", "bargain", "relic"]
CURSES = sorted(a["id"] for a in AFFIXES.values() if a.get("curse"))
GEAR_BASES = [b for kind in ("weapon", "armor", "trinket") for b in DEALER["gear"][kind]]
# a room that is any of these is never a Dealer's seat
NOT_A_SEAT = ("boss", "rest", "fixed", "waypost", "outpost", "beacon")
NAMES = {"dmg": "all damage", "phys": "weapon damage", "fire": "fire damage", "light": "flare damage",
         "heal": "healing", "ice": "ice damage", "water": "water damage", "earth": "earth damage",
         "shadow": "shadow damage", "spell": "spell damage"}


def new_state():
    """Saved under game.dealers (see the module docstring)."""
    return {"salt": 0, "bought": {}, "restocks": {}}


def load_state(raw):
    """The saved dealers block, or a fresh one when the save has nothing usable there (missing, empty or not a dict)."""
    return raw if isinstance(raw, dict) and raw else new_state()


def today():
    return int(clock.now() // 86400)


# ---------------------------------------------------------------------------- where the Dealers are
def _state(g):
    if not isinstance(g.dealers, dict):
        g.dealers = new_state()
    return g.dealers


def _salt(g):
    s = _state(g).get("salt", 0)
    return s if isinstance(s, int) and not isinstance(s, bool) else 0


def _table(g, name):
    """One of the two day-keyed tables, repaired if a damaged or hand-edited save left it as something else."""
    t = _state(g).get(name)
    if not isinstance(t, dict):
        t = g.dealers[name] = {}
    return t


def ring_of(rid):
    return REGION_INFO[ROOMS[rid]["region"]]["ring"]


_seats = {}


def _behind_a_lock(rid):
    """True when every way into this room goes through a locked exit, so a Dealer there could not be reached."""
    ways = [(src, d) for src, r in ROOMS.items() for d, dest in r["exits"].items() if dest == rid]
    return bool(ways) and all(d in ROOMS[src].get("locks", {}) for src, d in ways)


def seats(ring):
    """Rooms of this ring that could ever hold a Dealer: dark by nature, ordinary and reachable without a key, a
    book or a quest. Sorted, so seeding is stable. A region marked "dealer": false (an unlit annex) and a room marked
    "no_dealer" never hold one. What a region's "dealer_after" flag allows is decided live, in room_for."""
    if ring not in _seats:
        _seats[ring] = sorted(rid for rid, r in ROOMS.items()
                              if REGION_INFO[r["region"]]["ring"] == ring and r["dark"]
                              and REGION_INFO[r["region"]].get("dealer", True) and not r.get("no_dealer")
                              and not any(r.get(k) for k in NOT_A_SEAT) and not _behind_a_lock(rid))
    return _seats[ring]


def _allowed(g, rid):
    """A region with a "dealer_after" flag only seats the Dealer once that flag is set (the cache stays static)."""
    flag = REGION_INFO[ROOMS[rid]["region"]].get("dealer_after")
    return not flag or bool(g.flags.get(flag))


def room_for(g, ring, day=None):
    """The room this ring's Dealer is in today, or None. The day's seed shuffles the seats; the Dealer takes the
    first one that is still dark. So nothing moves him all day except that room being lit, and then he moves on
    to the next seat; with every seat lit (a beacon) he is gone."""
    if ring < 1:
        return None
    day = today() if day is None else day
    order = list(seats(ring))
    random.Random("dealer-room:%d:%d:%d" % (day, _salt(g), ring)).shuffle(order)
    for rid in order:
        if g.is_dark(rid) and _allowed(g, rid):
            return rid
    return None


def where(g):
    """For NPCS["dealer"]: the room the player stands in, if a Dealer is sitting in it today. With a dry lantern
    nothing in the room can be seen (the area screen and `examine` say so), so he is not talked to either."""
    rid = g.room_id
    ring = ring_of(rid)
    return rid if ring >= 1 and not g.benighted() and room_for(g, ring) == rid else None


def ring_here(g):
    return ring_of(g.room_id)


# ---------------------------------------------------------------------------- the cloth
def cloth_no(g, day=None):
    n = _table(g, "restocks").get(str(today() if day is None else day), 0)
    return n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else 0


def _clamp(tier, cap=CAP):
    order = gear.RARITY_ORDER
    return cap if order.index(tier) > order.index(cap) else tier


def _pick(rng, odds):
    return _clamp(rng.choices(list(odds), weights=list(odds.values()))[0])


def bargain_tier(tier, steps, cap):
    """A bargain is `steps` tiers above what the ring rolled, but never above the ring's bargain limit (and never
    below what was rolled, whatever the limit says)."""
    order = gear.RARITY_ORDER
    up = _clamp(order[min(len(order) - 1, order.index(tier) + steps)], _clamp(cap))
    return up if order.index(up) > order.index(tier) else tier


def _sockets(rng, cfg, tier, count):
    """Relics already socketed in a piece of this rarity. Their rarity is the piece's, up to the ring's limit."""
    order = gear.RARITY_ORDER
    cap = cfg["socket_cap"]
    rar = tier if order.index(tier) <= order.index(cap) else cap
    return [{"base": rng.choice(DEALER["relics"]), "rarity": _clamp(rar)} for _ in range(min(count, gear.SOCKETS[tier]))]


def price_of(w):
    """Gems. The bargain's discount is on the gear only: a relic in a socket costs at least what it costs loose."""
    base = DEALER["relic_price" if w["kind"] == "relic" else "price"][w["rarity"]]
    if w["curse"]:
        base = max(1, int(base * (1 - DEALER["bargain"]["discount"]) + 0.5))
    return base + sum(math.ceil(DEALER["socket_share"] * DEALER["relic_price"][r["rarity"]]) for r in w["relics"])


def _base_for(rng, tier, taken):
    """A gear base for a piece of this rarity: one that is not already on the cloth, and not native to a higher
    rarity (which would arrive weaker than itself, with a smaller damage multiplier and nothing said about why)."""
    order = gear.RARITY_ORDER
    pool = [b for b in GEAR_BASES if b not in taken and order.index(ITEMS[b].get("rarity", "common")) <= order.index(tier)]
    return rng.choice(pool)


def _wares(g, ring, day, cloth):
    """The four wares for this ring, day and cloth: the same every time you look. Everything is decided here.
    A ware's id is "day:ring:cloth:slot", so it names exactly one item and never means another one tomorrow."""
    cfg = DEALER["rings"][str(ring)]
    rng = random.Random("dealer-cloth:%d:%d:%d:%d" % (day, _salt(g), ring, cloth))
    out, taken = [], []
    for slot, name in enumerate(SLOT_NAMES):
        w = {"id": "%d:%d:%d:%d" % (day, ring, cloth, slot), "ring": ring, "slot": slot, "kind": "gear", "curse": None,
             "relics": [], "seed": rng.randrange(1 << 30)}
        if name == "relic":
            w.update(kind="relic", base=rng.choice(DEALER["relics"]), rarity=_pick(rng, cfg["relic_odds"]))
        else:
            tier = _pick(rng, cfg["gear_odds"])
            if name == "bargain":
                tier = bargain_tier(tier, DEALER["bargain"]["uplift"], cfg["bargain_cap"])
            w.update(base=_base_for(rng, tier, taken), rarity=tier)
            taken.append(w["base"])
            w["relics"] = _sockets(rng, cfg, tier, DEALER["bargain"]["relics"] if name == "bargain" else DEALER["fair_relics"])
            if name == "bargain":
                kind = ITEMS[w["base"]]["kind"]
                w["curse"] = rng.choice([c for c in CURSES if kind in AFFIXES[c]["slots"]])
        w["price"] = price_of(w)
        out.append(w)
    return out


def _bought(g, day=None):
    gone = _table(g, "bought").get(str(today() if day is None else day), [])
    return gone if isinstance(gone, list) else []


def wares(g, ring=None, day=None):
    """What is still for sale from this ring's cloth on `day` (today), as [(slot, ware)]."""
    ring = ring_here(g) if ring is None else ring
    if ring < 1:
        return []
    day = today() if day is None else day
    gone = _bought(g, day)
    return [(w["slot"], w) for w in _wares(g, ring, day, cloth_no(g, day)) if w["id"] not in gone]


def _prune(g, day):
    """Days before `day` no longer matter, so they go and the save stays small. Later days are kept: a clock that
    steps back must not wipe what was already sold or turned."""
    for name in ("bought", "restocks"):
        t = _table(g, name)
        for k in [k for k in t if not (str(k).isdigit() and int(k) >= day)]:
            del t[k]


# ---------------------------------------------------------------------------- making the real thing
def _build(w):
    inst = gear.make(w["base"], w["rarity"], random.Random(w["seed"]), relics=[dict(r) for r in w["relics"]])
    if w["curse"]:
        inst["affixes"].append(w["curse"])
        gear.rebuild(inst)
    return inst


def _make(w):
    """The real item, registered and ready to give. The same seed always rolls the same affixes."""
    return _build(w)


def sketch(w):
    """The same item as _make, for looking at: it is taken straight back out of ITEMS and the id counter is put
    back, so previewing leaves no trace."""
    saved = gear._counter[0]
    inst = _build(w)
    ITEMS.pop(inst["id"], None)
    gear._counter[0] = saved
    return inst


def _stat_parts(stats, mult):
    parts = ["%s %+d" % (k.upper(), v) for k, v in stats.items() if v]
    parts += ["x%.2f %s" % (v, NAMES.get(k, k)) for k, v in mult.items()]
    return parts


def curse_text(inst, curse):
    """What the curse costs, exactly: the item as it is, against the same item without the curse."""
    clean = dict(inst)
    clean["affixes"] = [a for a in inst["affixes"] if a != curse]
    clean["relics"] = list(inst.get("relics", []))
    gear.rebuild(clean)
    stats = {k: inst["stats"].get(k, 0) - clean["stats"].get(k, 0) for k in set(inst["stats"]) | set(clean["stats"])}
    mult = {k: inst["mult"].get(k, 1.0) / clean["mult"].get(k, 1.0) for k in set(inst["mult"]) | set(clean["mult"])}
    parts = _stat_parts({k: v for k, v in sorted(stats.items()) if v},
                        {k: v for k, v in sorted(mult.items()) if abs(v - 1) > 1e-6})
    return "%s: %s" % (AFFIXES[curse]["name"].title(), ", ".join(parts))


def _stat_line(inst):
    parts = _stat_parts(inst.get("stats", {}), inst.get("mult", {}))
    for k, v in inst.get("relic_mult", {}).items():
        parts.append("+%d%% %s" % (round((v - 1) * 100), NAMES.get(k, k)))
    return ", ".join(parts)


def _head(inst, w):
    head = "%s %s" % (inst["name"], rarity.describe_name(w["rarity"]))
    return head + " {bred}CURSED{/}" if w["curse"] else head


def preview(w):
    """One heading and the stat line for a ware, from an item that is thrown away again."""
    inst = sketch(w)
    return _head(inst, w), _stat_line(inst)


def _socket_text(r):
    info = RELIC_INFO["types"][ITEMS[r["base"]]["relic"]]
    return "%s, %s: +%d%% %s" % (ITEMS[r["base"]]["name"], r["rarity"], round(RELIC_INFO["scale"][r["rarity"]] * 100),
                                 NAMES.get(info["key"], info["key"]))


def detail_lines(w):
    """Everything the buyer should know beyond the heading: stats, sockets with their relics, the curse."""
    inst = sketch(w)
    stats = _stat_line(inst)
    lines = [stats] if stats else []
    if w["kind"] != "relic" and gear.SOCKETS[w["rarity"]]:
        lines.append("Sockets %d/%d%s" % (len(w["relics"]), gear.SOCKETS[w["rarity"]], "" if w["relics"] else ", all empty"))
        lines += ["Socketed: " + _socket_text(r) for r in w["relics"]]
    if w["curse"]:
        lines.append("{bred}Curse{/} {grey}(the forge cannot lift it){/} %s" % curse_text(inst, w["curse"]))
    return lines


# ---------------------------------------------------------------------------- buying and restocking
def buy(g, ring, wid):
    """Returns ("ok", item), ("poor", price) or ("gone", None). Gems are only taken when the item is handed over."""
    day = today()
    found = [w for _, w in wares(g, ring, day) if w["id"] == wid]
    if not found:
        return "gone", None
    w = found[0]
    p = g.player
    if p.gems < w["price"]:
        return "poor", w["price"]
    inst = _make(w)
    p.gems -= w["price"]
    gear.give(p, inst)
    _prune(g, day)
    bought = _table(g, "bought")
    if not isinstance(bought.get(str(day)), list):
        bought[str(day)] = []
    bought[str(day)].append(w["id"])
    return "ok", inst


def restocks_left(g, day=None):
    return max(0, DEALER["restock"]["max"] - cloth_no(g, day))


def restock_price(g, day=None):
    """Gems to turn the cloth now, or None when it has been turned as often as it can be today."""
    return DEALER["restock"]["prices"][cloth_no(g, day)] if restocks_left(g, day) else None


def restock(g, day=None, cloth=None):
    """Pay to turn the cloth. Returns ("ok", price), ("poor", price), ("max", None) or ("stale", None).
    A menu that showed a price passes the day and cloth number it showed; if midnight has passed since, the cloth
    is not the one that was priced, so nothing is taken."""
    now = today()
    if (day is not None and day != now) or (cloth is not None and cloth != cloth_no(g, now)):
        return "stale", None
    price = restock_price(g, now)
    if price is None:
        return "max", None
    if g.player.gems < price:
        return "poor", price
    g.player.gems -= price
    _prune(g, now)
    _table(g, "restocks")[str(now)] = cloth_no(g, now) + 1
    return "ok", price


# ---------------------------------------------------------------------------- the table
def _label(w):
    """A menu entry: the heading, then each detail line wrapped here with a hanging indent. They are cut short enough
    that the menu does not wrap them again (it would drop the indent on every continuation line)."""
    head, _ = preview(w)
    lines = ["%s  {sky}%d gems{/}" % (head, w["price"])]
    for l in detail_lines(w):
        for i, part in enumerate(ui._wrap_tagged("{grey}%s{/}" % l, ui.width() - 4 - 8)):
            lines.append(("    " if i == 0 else "        ") + part)
    return "\n".join(lines) + "\n"


COUNTS = ["No", "One", "Two", "Three", "Four"]


def menu(g):
    from .npcs import line
    p = g.player
    ring = ring_here(g)
    if ring < 1:
        return
    while True:
        day = today()
        if room_for(g, ring, day) != g.room_id:
            say("{grey}The dark has moved on while you stood here. The Dealer is gone from this room.{/}")
            ui.pause()
            return
        ui.clear()
        ui.rule("THE DARKNESS DEALER  ·  you have %d gems" % p.gems, color="night")
        offers = wares(g, ring, day)
        cloth = cloth_no(g, day)
        if offers:
            say("{grey}%s on the cloth. Everything is shown as it is, curses too, and what you see is what you get. "
                "What you buy is gone until tomorrow.{/}" % (COUNTS[4] + " wares" if len(offers) == 4 else
                                                           COUNTS[len(offers)] + " of the four wares are still"))
        else:
            say("{grey}The cloth is bare. What you bought is gone until tomorrow.{/}")
        blank()
        labels = [_label(w) for _, w in offers]
        price = restock_price(g, day)
        if price is None:
            say("{grey}The cloth has been turned %d times today. It will not be turned again until tomorrow.{/}"
                % DEALER["restock"]["max"])
            blank()
        else:
            labels.append("Turn the cloth for new wares  {sky}%d gems{/} {grey}(turn %d of %d today){/}" % (
                price, cloth + 1, DEALER["restock"]["max"]))
        if not offers:
            line("The Dealer", "Nothing left on the cloth. %s." % ("Come back tomorrow" if price is None
                                                                  else "Turn it, or come back tomorrow"), "night")
        if not labels:
            ui.pause()
            return
        i = ui.menu(labels, prompt="Buy", cancel_label="Walk away")
        if i is None:
            return
        if i == len(offers):
            if p.gems < price:
                say("{grey}You have %d gems. Turning the cloth takes %d.{/}" % (p.gems, price))
                ui.pause()
                continue
            if not ui.confirm("Pay %d gems to turn the cloth? Every Dealer's cloth turns with it, and whatever is unsold is gone." % price):
                continue
            state, cost = restock(g, day, cloth)
            if state == "ok":
                say("{bgreen}The Dealer turns the cloth over, and there is something else on it.{/}")
            elif state == "stale":
                say("{grey}The day turned over while you were deciding. Nothing was taken.{/}")
            else:
                say("{grey}You have %d gems. Turning the cloth takes %d.{/}" % (p.gems, cost))
            ui.pause()
            continue
        w = offers[i][1]
        if p.gems < w["price"]:
            say("{grey}You have %d gems. That is %d.{/}" % (p.gems, w["price"]))
            ui.pause()
            continue
        if not ui.confirm("Pay %d gems for it%s?" % (w["price"], " and carry the curse" if w["curse"] else "")):
            continue
        state, inst = buy(g, ring, w["id"])
        if state == "ok":
            say("{bgreen}You take: %s{/} {grey}(%s){/}" % (inst["name"], rarity.describe(inst["id"])))
        elif today() != day:
            say("{grey}The day turned over while you were deciding. That cloth is gone, and nothing was taken.{/}")
        else:
            say("{grey}That one is gone from the cloth.{/}")
        ui.pause()


# ---------------------------------------------------------------------------- content checks
def check(data):
    """Problems in a dealer.json-shaped dict, as messages (used by the content validator and its tests)."""
    errs = []
    order = gear.RARITY_ORDER
    cap = order.index(CAP)

    def tiers(where, table, need_price=None):
        if not isinstance(table, dict) or not table:
            errs.append("dealer %s: needs at least one rarity" % where)
            return
        for t, v in table.items():
            if t not in order:
                errs.append("dealer %s: unknown rarity %r" % (where, t))
            elif order.index(t) > cap:
                errs.append("dealer %s: %s is above %s; gems never buy it" % (where, t, CAP))
            elif need_price is not None and t not in need_price:
                errs.append("dealer %s: %s has no price" % (where, t))
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
                errs.append("dealer %s: %s must be a positive number" % (where, t))

    if not isinstance(data.get("notes"), str) or not data["notes"].strip():
        errs.append("dealer: needs a notes string justifying the prices")
    tiers("price", data.get("price"))
    tiers("relic_price", data.get("relic_price"))
    for t, v in data.get("price", {}).items():
        if not isinstance(v, int) or isinstance(v, bool):
            errs.append("dealer price %s: gem prices are whole numbers" % t)
    rs = data.get("restock", {})
    prices = rs.get("prices")
    if not isinstance(prices, list) or not prices or any(not isinstance(x, int) or x < 1 for x in prices):
        errs.append("dealer restock: prices must be a list of whole numbers of at least 1")
    elif sorted(prices) != prices:
        errs.append("dealer restock: prices must not fall")
    if not isinstance(rs.get("max"), int) or rs["max"] < 1:
        errs.append("dealer restock: max must be at least 1")
    elif isinstance(prices, list) and len(prices) < rs["max"]:
        errs.append("dealer restock: %d restocks allowed but only %d prices" % (rs["max"], len(prices)))
    b = data.get("bargain", {})
    if not isinstance(b.get("discount"), (int, float)) or not 0 < b["discount"] < 1:
        errs.append("dealer bargain: discount must be between 0 and 1")
    if b.get("uplift") not in (0, 1, 2):
        errs.append("dealer bargain: uplift must be 0, 1 or 2 tiers")
    if not isinstance(b.get("relics"), int) or not 0 <= b["relics"] <= 3:
        errs.append("dealer bargain: relics must be 0 to 3")
    if not isinstance(data.get("fair_relics"), int) or not 0 <= data["fair_relics"] <= 3:
        errs.append("dealer: fair_relics must be 0 to 3")
    if not isinstance(data.get("socket_share"), (int, float)) or not 1 <= data["socket_share"] <= 2:
        errs.append("dealer: socket_share must be between 1 and 2 (a socketed relic costs at least its loose price, "
                    "or the forge would hand back relics cheaper than the Dealer sells them)")
    ring_ids = sorted({str(i["ring"]) for i in REGION_INFO.values() if i["ring"] >= 1})
    rings = data.get("rings", {})
    if sorted(rings) != ring_ids:
        errs.append("dealer rings: needs exactly one entry per ring %s, has %s" % (ring_ids, sorted(rings)))
    for rid, cfg in rings.items():
        tiers("ring %s gear_odds" % rid, cfg.get("gear_odds"), data.get("price", {}))
        tiers("ring %s relic_odds" % rid, cfg.get("relic_odds"), data.get("relic_price", {}))
        if cfg.get("socket_cap") not in order or order.index(cfg["socket_cap"]) > cap:
            errs.append("dealer ring %s: socket_cap must be a rarity up to %s" % (rid, CAP))
        elif cfg["socket_cap"] not in data.get("relic_price", {}):
            errs.append("dealer ring %s: socket_cap %s has no relic price" % (rid, cfg["socket_cap"]))
        if cfg.get("bargain_cap") not in order or order.index(cfg["bargain_cap"]) > cap:
            errs.append("dealer ring %s: bargain_cap must be a rarity up to %s" % (rid, CAP))
            continue
        if cfg.get("socket_cap") not in order:
            continue
        # the bargain's tier up, and the relics socketed in gear, need prices too
        for t in cfg.get("gear_odds", {}):
            if t in order:
                up = bargain_tier(t, b.get("uplift") or 0, cfg["bargain_cap"])
                if up not in data.get("price", {}):
                    errs.append("dealer ring %s: bargain tier %s has no price" % (rid, up))
                for r in (t, up):
                    held = r if order.index(r) <= order.index(cfg["socket_cap"]) else cfg["socket_cap"]
                    if gear.SOCKETS[r] and held not in data.get("relic_price", {}):
                        errs.append("dealer ring %s: socketed %s relics have no price" % (rid, held))
    seen = []
    for kind, ids in data.get("gear", {}).items():
        if kind not in ("weapon", "armor", "trinket"):
            errs.append("dealer gear: unknown kind %r" % kind)
        for iid in ids:
            if iid not in ITEMS:
                errs.append("dealer gear: unknown item %s" % iid)
            elif ITEMS[iid]["kind"] != kind:
                errs.append("dealer gear: %s is a %s, not a %s" % (iid, ITEMS[iid]["kind"], kind))
            seen.append(iid)
    if len(set(seen)) < 3:
        errs.append("dealer gear: needs at least 3 different pieces")
    if not any(ITEMS.get(i, {}).get("kind") == "weapon" for i in seen) or sorted(data.get("gear", {})) != ["armor", "trinket", "weapon"]:
        errs.append("dealer gear: needs weapon, armor and trinket lists")
    if not data.get("relics"):
        errs.append("dealer: needs a list of relics")
    for iid in data.get("relics", []):
        if iid not in ITEMS:
            errs.append("dealer relics: unknown item %s" % iid)
        elif ITEMS[iid]["kind"] != "relic":
            errs.append("dealer relics: %s is not a relic" % iid)
    return errs
