"""The Long Quench: the week-long smith upgrade for a Godlike weapon (docs/M6-SPEC.md section 11.3).

Brann and Tamsin take a Godlike weapon for seven real days (or 5,000 steps, whichever comes first) and temper it in the
third quench. It comes back with a damage multiplier of x2.0, x2.5 or x3.0, stored on the weapon as inst["temper"] and
applied by gear.rebuild. It never destroys anything and never goes below x2.0. A weapon keeps the better of its old and
new result, a x3.0 weapon is finished, and every result below x3.0 makes the next x3.0 likelier (pity).

A Long Quench is a forge job with kind "temper" (see forge.py): it holds one anvil, you carry the usual loaner of the
weapon while it works, and gems can skip at most two of its days. The numbers live in data/smith.json.
"""
from . import clock, forge, gear
from .content import ITEMS, load_json

CFG = load_json("smith.json")["quench"]
DAY = 86400
PITY_FLAG = "late_quench_pity"


# ---------------------------------------------------------------------------- the odds
def outcomes():
    """[(multiplier, base weight)] from the lowest to the best."""
    return sorted((o["mult"], o["weight"]) for o in CFG["outcomes"])


def best_mult():
    return outcomes()[-1][0]


def pity(g):
    return int(g.flags.get(PITY_FLAG, 0))


def chances(pity_count=0):
    """[(multiplier, probability)] from the lowest to the best. The best result gains `pity_step` per earlier result that
    fell short of it (up to `pity_cap`); the rest of the probability keeps the base proportions of the lower results."""
    outs = outcomes()
    total = sum(w for _, w in outs)
    low = outs[:-1]
    p_best = min(CFG["pity_cap"], outs[-1][1] / total + CFG["pity_step"] * pity_count)
    low_total = sum(w for _, w in low)
    return [(m, (1 - p_best) * w / low_total) for m, w in low] + [(outs[-1][0], p_best)]


def roll(rng, pity_count=0):
    """One draw: the multiplier."""
    u = rng.random()
    acc = 0.0
    table = chances(pity_count)
    for m, p in table:
        acc += p
        if u < acc:
            return m
    return table[-1][0]


# ---------------------------------------------------------------------------- what can be quenched
def temper_of(iid):
    return ITEMS[iid].get("temper", 1.0) if gear.is_instance(iid) else 1.0


def can_quench(iid):
    it = ITEMS[iid]
    return (gear.is_instance(iid) and it.get("kind") == "weapon" and it.get("rarity") == "godlike"
            and not it.get("loaner") and temper_of(iid) < best_mult())


def candidates(g):
    """[(item_id, where)] for every Godlike weapon the player could hand over, worn first."""
    p = g.player
    out = [(iid, "worn") for iid in p.equipment.values() if iid and can_quench(iid)]
    out += [(iid, "pack") for iid in p.inventory if can_quench(iid) and iid not in [c[0] for c in out]]
    return out


def holds_godlike_weapon(g):
    p = g.player
    ids = [v for v in p.equipment.values() if v] + list(p.inventory)
    return any(i in ITEMS and ITEMS[i].get("kind") == "weapon" and ITEMS[i].get("rarity") == "godlike"
               and not ITEMS[i].get("loaner") for i in ids)


def jobs(g):
    return [j for j in forge.state(g)["jobs"] if j.get("kind") == "temper"]


def running(g):
    return bool(jobs(g))


def unlocked(g):
    """Is the Long Quench offered at the forge yet? (The recipe, or a Godlike weapon to look at.)"""
    return bool(g.flags.get(CFG["needs_flag"])) or holds_godlike_weapon(g)


def cost_text():
    parts = ["%d gold" % CFG["gold"]] + ["%d %s" % (n, ITEMS[m]["name"] if m in ITEMS else m) for m, n in CFG["items"].items()]
    return ", ".join(parts)


def missing(g, iid):
    """What stands in the way of quenching this weapon now, as phrases for 'You still need ...'."""
    from . import town
    p = g.player
    out = []
    if not g.flags.get(CFG["needs_flag"]):
        out.append("the third quench (ask Orrin about Aldric's receipts, then Brann and Tamsin)")
    if not town.is_built(g, CFG["needs_building"]):
        out.append("both smiths at the anvil (build the Ember Smithy)")
    if p.gold < CFG["gold"]:
        out.append("%d more gold" % (CFG["gold"] - p.gold))
    for mid, n in CFG["items"].items():
        have = p.inventory.get(mid, 0)
        if have < n:
            out.append("%d more %s" % (n - have, ITEMS[mid]["name"] if mid in ITEMS else mid))
    return out


def start(g, iid):
    """Hand a Godlike weapon to the smiths. Returns (ok, message)."""
    st = forge.state(g)
    p = g.player
    if not can_quench(iid):
        if iid in ITEMS and gear.is_instance(iid) and temper_of(iid) >= best_mult():
            return False, "That blade is already tempered as far as the third quench goes."
        return False, "Only a Godlike weapon can be Long-Quenched."
    if running(g):
        return False, "A weapon is already in the Long Quench. It takes a week; one at a time."
    if forge.free_slots(g) < 1:
        return False, "Every forge slot is busy. Collect finished work first."
    lack = missing(g, iid)
    if lack:
        return False, "You still need " + ", ".join(lack) + "."
    p.gold -= CFG["gold"]
    for mid, n in CFG["items"].items():
        p.remove_item(mid, n)
    slot, loaner = forge._hand_over(g, iid)
    st["jobs"].append({"item": iid, "slot": slot, "loaner": loaner, "done": False,
                       "ready_at": clock.now() + CFG["days"] * DAY, "steps": CFG["steps"],
                       "slots": 1, "kind": "temper", "hurried": 0})
    return True, "ok"


# ---------------------------------------------------------------------------- waiting and hurrying
def seconds_left(job):
    return max(0, job["ready_at"] - clock.now())


def time_left_text(job):
    s = seconds_left(job)
    if s >= DAY:
        d = -(-int(s) // DAY)
        return "about %d day%s" % (d, "" if d == 1 else "s")
    h = max(1, -(-int(s) // 3600))
    return "about %d hour%s" % (h, "" if h == 1 else "s")


def hurry_cost(job):
    return CFG["hurry"]["gems_per_day"]


def hurry_left(job):
    return max(0, CFG["hurry"]["max_days"] - job.get("hurried", 0))


def hurry(g, index):
    """Skip one day of a Long Quench for gems. At most `max_days` days per job; the rest is real time. True on success."""
    job = forge.state(g)["jobs"][index]
    if job.get("kind") != "temper" or job["done"] or hurry_left(job) <= 0 or g.player.gems < hurry_cost(job):
        return False
    g.player.gems -= hurry_cost(job)
    job["hurried"] = job.get("hurried", 0) + 1
    job["ready_at"] -= DAY
    forge.update(g)
    return True


# ---------------------------------------------------------------------------- the result
def collect(g, job):
    """Settle a finished Long Quench (forge.collect has already taken the job off the list). Nothing is ever lost:
    the weapon keeps the better of its old and new multiplier. Returns the result for forge_ui.reveal_temper."""
    p = g.player
    iid = job["item"]
    before_pity = pity(g)
    table = chances(before_pity)
    mult = roll(g.rng, before_pity)
    odds = dict(table)[mult]
    if mult >= best_mult():
        g.flags[PITY_FLAG] = 0
    else:
        g.flags[PITY_FLAG] = before_pity + 1
    old = temper_of(iid)
    improved = mult > old
    inst = ITEMS[iid]
    if improved:
        inst["temper"] = mult
    gear.rebuild(inst)
    # hand back the real thing in place of the loaner
    if job.get("loaner"):
        gear.discard(p, job["loaner"])
    p.inventory[iid] = 1
    if job.get("slot") and p.equipment.get(job["slot"]) is None:
        p.inventory.pop(iid, None)
        p.equipment[job["slot"]] = iid
    return {"kind": "temper", "item": iid, "name": inst["name"], "rolled": mult, "before": old,
            "after": temper_of(iid), "improved": improved, "chance": odds, "pity": g.flags[PITY_FLAG],
            "slot": job.get("slot")}


# ---------------------------------------------------------------------------- the menu
def odds_text(g):
    return ",  ".join("x%.1f %d%%" % (m, round(100 * p)) for m, p in reversed(chances(pity(g))))


def menu(g):
    """The Long Quench screen, reached from the forge menu. Returns a note for the forge menu to show."""
    from . import rarity, ui
    from .ui import blank, say
    ui.clear()
    ui.rule("THE LONG QUENCH", color="ember")
    for j in jobs(g):
        say("{amber}A weapon is in the Long Quench:{/} %s  {grey}(%s left)%s{/}" % (
            rarity.label(j["item"]), "ready" if j["done"] else time_left_text(j),
            "" if j["done"] else ", or %d steps" % max(0, j["steps"])))
        blank()
    say("Brann and Tamsin take a {b}Godlike weapon{/} between them and quench it a third time, in a flame that was given. "
        "It takes {b}a week{/} of real time (or %d steps of walking, whichever comes first). It costs %s." % (
            CFG["steps"], cost_text()))
    say("It {b}never destroys{/} the weapon and never leaves it below x%.1f. The result multiplies {b}all{/} its damage: "
        "blows, spells and flares alike. If the weapon is already quenched you keep the better result." % outcomes()[0][0])
    say("If it is the weapon in your hand, you carry a loaner of it, %d%% weaker, until it comes back." % round(
        (1 - forge_penalty()) * 100))
    blank()
    if not g.flags.get(CFG["needs_flag"]):
        return "{grey}Brann shakes his head. Not yet: the third quench is not known. Ask Orrin about Aldric's receipts.{/}"
    if running(g):
        # (checked first: the weapon in the quench is not in the pack, so it would otherwise read as "no Godlike weapon")
        job = jobs(g)[0]
        if job["done"]:
            return "{grey}One weapon at a time. The finished one is waiting: collect it at the forge.{/}"
        return "{grey}One weapon at a time. Your blade is in the third quench; it comes back in %s.{/}" % time_left_text(job)
    cands = candidates(g)
    if not cands:
        return "{grey}You hold no Godlike weapon that could take more (a x%.1f blade is finished).{/}" % best_mult()
    say("{grey}Odds now: %s.  (Quenches in a row below x%.1f: %d. Each makes the best result likelier.){/}" % (
        odds_text(g), best_mult(), pity(g)))
    labels = ["%s {grey}(%s%s){/}" % (rarity.label(i), w,
                                     ", now x%.1f" % temper_of(i) if temper_of(i) > 1.0 else "") for i, w in cands]
    idx = ui.menu(labels, prompt="Quench which", cancel_label="Back")
    if idx is None:
        return ""
    iid, where = cands[idx]
    lack = missing(g, iid)
    if lack:
        return "{grey}You still need %s.{/}" % ", ".join(lack)
    if forge.free_slots(g) < 1:
        return "{grey}Every forge slot is busy. Collect finished work first.{/}"
    say("{grey}Odds: %s.  Cost: %s.  It will be away for %d days.{/}" % (odds_text(g), cost_text(), CFG["days"]))
    if where == "worn" and temper_of(iid) > 1.0:
        # the loaner is a plain Godlike blade (no temper), so it is far weaker than a quenched weapon
        say("{amber}The loaner is a plain Godlike blade: about %d%% of your quenched weapon's strength, until it "
            "comes back.{/}" % round(100 * forge_penalty() / temper_of(iid)))
    if not ui.confirm("Put %s in the third quench?" % ITEMS[iid]["name"]):
        return ""
    ok, msg = start(g, iid)
    if not ok:
        return "{grey}%s{/}" % msg
    say('{ember}Tamsin:{/} "Seven days. Don\'t come asking on the third; it will not be any different."')
    return "{bgreen}Brann and Tamsin take the %s to the fire. See you in a week.{/}" % ITEMS[iid]["name"]


def forge_penalty():
    from .content import FORGE
    return FORGE["loaner_penalty"]
