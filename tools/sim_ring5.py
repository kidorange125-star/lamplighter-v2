"""Ring-5 and extension calibration (docs/M6-SPEC.md sections 14 and 15): how the new fights fare against each build.

usage: python tools/sim_ring5.py [--area ff|vg|hos|rl|lw|all] [--level N] [--n 60] [--kit none|kit|both]
                                 [--powers 1,25,50,75,100] [--classes] [--lane] [--standin] [--check] [--strict]

Every ordinary group of the area, the mini-boss and the boss at each power, for the builds of section 14.1, with the
three classes (warden, wayfarer, ashblade) averaged; --classes also prints them separately. Rooms are passed to the
simulator, so damage fields (Black Ice, Midwinter, Hall of Mirrors, Noon) and rotating weaknesses apply, and the rolled
bosses are scaled with powerroll.scaled exactly as the game does.

  none   no spell books (the floor)
  kit    three Epic books, two on the fight's weak elements and one neutral (the typical play)

  --lane     two Epic books on the area's strong elements vs two on its resisted ones vs none (section 14.3)
  --standin  also run the Queen / Steward stand-ins the tables of section 14 were first measured with
  --check    compare the real fights with the pinned cells of section 14 and exit 1 if any is outside its band;
             it honours --area, --kit, --powers and --level (only the cells you asked for are run), and prints the
             warnings (per-class floors, the Reedlight's ordinary groups) after the failures; --strict fails on them too

Method (section 14.1): level 11 for area A, 12 for area B; saltsteel saber (ashwood rod for the ashblade) and a hauberk
at the stated rarity, 3 draughts, 3 strong draughts, 3 oil, the full lantern kit, Dread 0, n seeded fights per class.
"Leg + 3" is a Legendary weapon with 3 Legendary relics (Edge, or Ember for the ashblade); "God + 3" the same on
Godlike; "+ arm" adds 3 Legendary Heart relics in the armour; "Q2.0" / "Q3.0" multiply the weapon's damage by 2.0 / 3.0,
which is what a Long Quench does (gear.rebuild applies inst["temper"]).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import powerroll, sim  # noqa: E402
from lamplighter.content import ENEMIES, ITEMS, ROOMS  # noqa: E402
from lamplighter.elements import ELEMENTS  # noqa: E402

CLASSES = ["warden", "wayfarer", "ashblade"]
WEAPON = {"warden": "saltsteel_saber", "wayfarer": "saltsteel_saber", "ashblade": "ashwood_rod"}
RELIC = {"warden": "edge", "wayfarer": "edge", "ashblade": "ember"}
ITEM_KIT = {"draught": 3, "strong_draught": 3, "oil": 3}
LANTERN = {"shroud": True, "trim": True, "lens": True}
NEUTRAL_ORDER = ["ice", "water", "shadow", "light", "fire", "earth"]

# ---------------------------------------------------------------------------- the areas
# boss: the rolled boss; mini: the elite's fixed fight; room: where the boss is met (its field applies)
RING5 = {
    "ff": {"label": "The Frostfair (area A)", "regions": ["The Frostfair", "The Fair Below"], "level": 11,
           "boss": "ff_lampmaster", "boss_room": "ff_wintering", "mini": "ff_ringmaster", "mini_room": "ff_carousel",
           "recommended": "ultra", "strong": ["fire", "earth"], "resisted": ["ice", "water"]},
    "vg": {"label": "The Vigil (area B)", "regions": ["The Vigil", "The Waking Cellars"], "level": 12,
           "boss": "vg_prior_eye", "boss_room": "vg_eye", "mini": "vg_orrery", "mini_room": "vg_orrery_hall",
           "recommended": "legendary", "strong": ["shadow", "earth"], "resisted": ["light", "fire"]},
}
# the extensions: the base game's gear and levels (section 14.6). stand-in: (enemy, hp x, atk x, hp range, left range)
EXTENSIONS = {
    "hos": {"label": "The Moth-Saint's Hospice", "regions": ["The Moth-Saint's Hospice"], "level": 4,
            "boss": "hos_vesper", "boss_room": "hos_belfry",
            "gear": dict(weapon="hunting_spear", armor="oilskin", items={"draught": 3, "oil": 2}),
            "standin": ("antlered_mother", 1.8, 1.4), "win": (90, 97), "left": (40, 50)},
    "rl": {"label": "The Reedlight", "regions": ["The Reedlight"], "level": 6,
           "boss": "rl_heron", "boss_room": "rl_lantern_room",
           "gear": dict(weapon="saltsteel_saber", armor="jerkin", lantern={"shroud": True, "trim": True},
                        items={"draught": 3, "oil": 2}),
           "standin": ("drowned_bishop", 1.7, 1.4), "win": (85, 95), "left": (45, 55)},
    "lw": {"label": "The Lampwrights' Deep", "regions": ["The Lampwrights' Deep"], "level": 7,
           "boss": "lw_foreman", "boss_room": "lw_workshop",
           "gear": dict(weapon="saltsteel_saber", armor="hauberk", trinket="saints_tooth",
                        items={"draught": 3, "oil": 2}),
           "standin": ("starsteel_golem", 2.8, 1.4), "win": (82, 92), "left": (55, 65)},
}

# the builds of section 14.1: (label, rarity, weapon relics, armour relics, quench)
BUILDS = [
    ("Epic", "epic", 0, 0, 1.0),
    ("Ultra", "ultra", 0, 0, 1.0),
    ("Legendary", "legendary", 0, 0, 1.0),
    ("Godlike", "godlike", 0, 0, 1.0),
    ("Leg+3", "legendary", 3, 0, 1.0),
    ("God+3", "godlike", 3, 0, 1.0),
    ("God+3+arm", "godlike", 3, 3, 1.0),
    ("+Q2.0", "godlike", 3, 3, 2.0),
    ("+Q3.0", "godlike", 3, 3, 3.0),
    ("God+Q2", "godlike", 0, 0, 2.0),
]
ORDINARY = ["epic", "ultra", "legendary", "godlike"]
MINI_BUILDS = [b for b in BUILDS if b[0] in ("Epic", "Ultra", "Legendary", "Godlike", "Leg+3", "God+3")]
POWERS = [1, 25, 50, 75, 100]

# ---------------------------------------------------------------------------- the pinned cells (section 14.2 to 14.6)
# {(area, kit): {power: [Epic, Ultra, Legendary, Godlike, Leg+3, God+3, God+3+arm, +Q2.0, +Q3.0, God+Q2]}}
BOSS_CELLS = {
    ("ff", "kit"): {1: [83, 94, 100, 100, 100, 100, 100, 100, 100, 100],
                    25: [46, 71, 86, 96, 91, 100, 100, 99, 99, 99],
                    50: [14, 36, 53, 83, 61, 88, 92, 96, 96, 90],
                    75: [5, 6, 24, 57, 28, 62, 68, 85, 88, 78],
                    100: [1, 3, 10, 38, 12, 42, 50, 68, 77, 50]},
    ("ff", "none"): {1: [65, 83, 93, 100, 99, 100, 100, 100, 100, 100],
                     25: [16, 28, 54, 90, 72, 95, 96, 96, 97, 95],
                     50: [1, 6, 16, 51, 36, 69, 74, 89, 89, 83],
                     75: [0, 1, 3, 31, 12, 44, 52, 73, 77, 61],
                     100: [0, 1, 1, 15, 3, 24, 29, 50, 61, 33]},
    ("vg", "kit"): {1: [76, 90, 95, 100, 98, 100, 100, 100, 100, 100],
                    25: [26, 57, 67, 90, 74, 95, 96, 99, 99, 97],
                    50: [7, 13, 34, 67, 36, 76, 80, 90, 91, 82],
                    75: [1, 4, 9, 39, 10, 44, 53, 69, 79, 52],
                    100: [1, 2, 6, 23, 6, 30, 38, 46, 59, 32]},
    ("vg", "none"): {1: [44, 63, 83, 98, 96, 99, 99, 99, 99, 99],
                     25: [3, 15, 34, 69, 49, 84, 90, 92, 94, 89],
                     50: [0, 1, 6, 32, 17, 51, 62, 78, 78, 67],
                     75: [0, 1, 0, 17, 2, 24, 32, 57, 63, 36],
                     100: [0, 0, 0, 5, 1, 14, 18, 34, 45, 24]},
}
# the mini-bosses (14.5): [Epic, Ultra, Legendary, Godlike, Leg+3, God+3]
MINI_CELLS = {
    ("ff", "none"): [22, 44, 71, 92, 84, 98], ("ff", "kit"): [56, 73, 86, 97, 89, 99],
    ("vg", "none"): [11, 32, 59, 91, 78, 97], ("vg", "kit"): [46, 64, 83, 96, 87, 99],
}
TOL_P50, TOL_OTHER, TOL_MINI = 8, 10, 10

# ---------------------------------------------------------------------------- building and running
_cache = {}


def build(cls, lvl, rarity, nrel=0, arel=0, spells=(), quench=1.0):
    def f():
        p = sim.maxed(cls, lvl, WEAPON[cls], "hauberk", rarity,
                      relics=[(RELIC[cls], "legendary")] * nrel, armor_relics=[("heart", "legendary")] * arel,
                      items=dict(ITEM_KIT), lantern=dict(LANTERN), spells=spells)
        if quench != 1.0:
            w = ITEMS[p.equipment["weapon"]]
            w["mult"]["dmg"] = w["mult"].get("dmg", 1.0) * quench
        return p
    return f


def build_gear(cls, lvl, gear):
    """A player in the base game's gear (the extensions): the dict is sim.build_player's weapon / armor / items."""
    def f():
        kw = {k: (dict(v) if isinstance(v, dict) else v) for k, v in gear.items()}
        return sim.build_player(cls=cls, level=lvl, **kw)
    return f


def weak_of(eid):
    e = ENEMIES[eid]
    out = list(e.get("weak", []))
    for st in e.get("attune", {}).get("stances", []):
        out += st.get("weak", [])
    return out


def kit_for(eids):
    """Three Epic books: the two elements most of the fight is weak to, and a neutral one (neither weak nor resisted)."""
    base = [powerroll.base_id(e) for e in eids]
    count = {}
    resisted = set()
    for e in base:
        ent = ENEMIES[e]
        st = ent.get("attune", {}).get("stances")
        weaks = [st[0]["weak"]] if st else [ent.get("weak", [])]
        for w in weaks[0]:
            count[w] = count.get(w, 0) + 1
        resisted.update(ent.get("resist", []))
        if st:
            for s in st:
                resisted.update(s.get("resist", []))
    ranked = sorted(count, key=lambda el: (-count[el], ELEMENTS.index(el)))[:2]
    neutral = next((el for el in NEUTRAL_ORDER if el not in count and el not in resisted), None)
    books = ranked + ([neutral] if neutral else [])
    return tuple((el, "epic") for el in books)


def orrery_books(eid, right=True):
    """The rotating-weakness fight: 'right' carries a weakness of each stance; 'wrong' is Light, Fire and Water."""
    if not right:
        return (("light", "epic"), ("fire", "epic"), ("water", "epic"))
    return tuple((st["weak"][0], "epic") for st in ENEMIES[eid]["attune"]["stances"])


def run(eids, room, level, cls, n, rarity="epic", nrel=0, arel=0, spells=(), quench=1.0, gear=None):
    key = (tuple(eids), room, level, cls, n, rarity, nrel, arel, tuple(spells), quench, repr(sorted(gear.items())) if gear else "")
    if key not in _cache:
        b = build_gear(cls, level, gear) if gear else build(cls, level, rarity, nrel, arel, spells, quench)
        r = sim.win_rate(list(eids), sim.suggested, n=n, builder=b, room=room)
        r["max_hp"] = b().max_hp
        _cache[key] = r
    return _cache[key]


def mean_run(eids, room, level, n, classes=CLASSES, **kw):
    """The three classes averaged: {"win": %, "left": % of health on a win, "by_class": {cls: %}}."""
    wins, lefts, by = [], [], {}
    for cls in classes:
        r = run(eids, room, level, cls, n, **kw)
        wins.append(100.0 * r["win"])
        by[cls] = 100.0 * r["win"]
        if r["win"]:
            lefts.append(100.0 * r["hp_on_win"] / r["max_hp"])
    return {"win": sum(wins) / len(wins), "left": sum(lefts) / len(lefts) if lefts else 0.0, "by_class": by}


def build_kw(b, spells):
    return dict(rarity=b[1], nrel=b[2], arel=b[3], quench=b[4], spells=spells)


# ---------------------------------------------------------------------------- the area's fights
def groups_of(regions):
    """[(group, weight, room)] for every random encounter in the regions: the same group in many rooms is one row
    whose weight is the sum of (room chance x group share), so the average is what a player meets."""
    out = {}
    order = []
    for rid, r in ROOMS.items():
        if r["region"] not in regions or not r.get("enc"):
            continue
        total = sum(w for _, w in r["enc"]["groups"])
        for grp, w in r["enc"]["groups"]:
            key = tuple(grp)
            if key not in out:
                out[key] = [0.0, rid]
                order.append(key)
            out[key][0] += r["enc"]["chance"] * w / total
    return [(list(k), out[k][0], out[k][1]) for k in order]


def fmt(v):
    return "%4d" % round(v)


def heading(text):
    print("\n" + text)
    print("-" * len(text))


def per_class_text(res):
    return "  [" + " ".join("%s %d" % (c[:3], round(v)) for c, v in res["by_class"].items()) + "]"


def report_ring5(key, args, kits):
    a = RING5[key]
    lvl = args.level or a["level"]
    heading("%s, level %d, %d fights per class" % (a["label"], lvl, args.n))
    groups = groups_of(a["regions"])
    for kit in kits:
        print("\nOrdinary groups (%s): win%% (health left on a win%%), weight = share of an hour's fights" % kit)
        print("%-34s %6s" % ("group", "weight") + "".join("%14s" % r.title() for r in ORDINARY))
        tot = sum(w for _, w, _ in groups)
        for grp, w, room in groups:
            spells = kit_for(grp) if kit == "kit" else ()
            row = "%-34s %5.0f%%" % ("+".join(g.replace(key + "_", "") for g in grp), 100 * w / tot)
            for rar in ORDINARY:
                m = mean_run(grp, room, lvl, args.n, rarity=rar, spells=spells)
                row += "%14s" % ("%d (%d%%)" % (round(m["win"]), round(m["left"])))
            print(row)
    for kit in kits:
        print("\nMini-boss %s, %s" % (a["mini"], kit))
        print("%-12s" % "" + "".join("%11s" % b[0] for b in MINI_BUILDS))
        spells = ()
        if kit == "kit":
            spells = orrery_books(a["mini"]) if "attune" in ENEMIES[a["mini"]] else kit_for([a["mini"]])
        row = "%-12s" % "win%"
        for b in MINI_BUILDS:
            m = mean_run([a["mini"]], a["mini_room"], lvl, args.n, **build_kw(b, spells))
            row += "%11s" % ("%d (%d%%)" % (round(m["win"]), round(m["left"])))
        print(row)
    for kit in kits:
        spells = kit_for([powerroll.scaled(a["boss"], 50)]) if kit == "kit" else ()
        print("\nBoss %s, %s%s" % (a["boss"], kit, "  (books: %s)" % ", ".join(e for e, _ in spells) if spells else ""))
        print("%-10s" % "power" + "".join("%11s" % b[0] for b in BUILDS))
        for p in args.powers:
            eid = powerroll.scaled(a["boss"], p)
            row = "%-10s" % ("p%d" % p)
            extra = ""
            for b in BUILDS:
                m = mean_run([eid], a["boss_room"], lvl, args.n, **build_kw(b, spells))
                row += "%11s" % fmt(m["win"])
                if args.classes and b[0] == "Godlike":
                    extra = per_class_text(m)
            print(row + (("   Godlike by class" + extra) if args.classes else ""))
    if args.standin:
        report_standin(key, args, lvl)


def report_standin(key, args, lvl):
    a = RING5[key]
    hp, atk = (1.45, 1.45) if key == "ff" else (1.8, 1.8)
    print("\nStand-in (Cinder Queen x%.2f hp and atk, no kit; the numbers the spec was written from)" % hp)
    print("%-10s" % "power" + "".join("%11s" % b[0] for b in BUILDS))
    for p in args.powers:
        k = hp * powerroll.mult(p)
        eid = sim.scaled_enemy("cinder_queen", hp=k, atk=k)
        row = "%-10s" % ("p%d" % p)
        for b in BUILDS:
            m = mean_run([eid], "throne_room", lvl, args.n, **build_kw(b, ()))
            row += "%11s" % fmt(m["win"])
        print(row)


def report_ext(key, args):
    a = EXTENSIONS[key]
    lvl = args.level or a["level"]
    heading("%s, level %d, %s, %d fights per class" % (a["label"], lvl, a["gear"]["weapon"], args.n))
    for grp, w, room in groups_of(a["regions"]):
        m = mean_run(grp, room, lvl, args.n, gear=a["gear"])
        print("%-34s win %3d%%  health left %3d%%" % ("+".join(grp), round(m["win"]), round(m["left"])))
    m = ext_boss(key, args.n, lvl)
    print("%-34s win %3d%%  health left %3d%%   (target %d-%d%%, %d-%d%% left)%s" % (
        a["boss"], round(m["win"]), round(m["left"]), a["win"][0], a["win"][1], a["left"][0], a["left"][1],
        per_class_text(m) if args.classes else ""))
    if args.standin:
        e, hx, ax = a["standin"]
        sid = sim.scaled_enemy(e, hp=hx, atk=ax)
        m = mean_run([sid], a["boss_room"], lvl, args.n, gear=a["gear"])
        print("%-34s win %3d%%  health left %3d%%   (stand-in %s x%g hp / x%g atk)" % (
            "stand-in", round(m["win"]), round(m["left"]), e, hx, ax))


def ext_boss(key, n, lvl=None):
    a = EXTENSIONS[key]
    return mean_run([a["boss"]], a["boss_room"], lvl or a["level"], n, gear=a["gear"])


def ext_groups(key, n, lvl=None):
    """Encounter-weighted mean win and health left over the extension's ordinary groups."""
    a = EXTENSIONS[key]
    groups = groups_of(a["regions"])
    tot = sum(w for _, w, _ in groups)
    win = left = 0.0
    for grp, w, room in groups:
        m = mean_run(grp, room, lvl or a["level"], n, gear=a["gear"])
        win += m["win"] * w / tot
        left += m["left"] * w / tot
    return {"win": win, "left": left}


# ---------------------------------------------------------------------------- lanes
def lane_rows(key, n, lvl=None):
    """[(label, right, wrong, none)] mean win rates for the p50 boss and for the area's ordinary pairs."""
    a = RING5[key]
    lvl = lvl or a["level"]
    rar = a["recommended"]
    right = tuple((e, "epic") for e in a["strong"])
    wrong = tuple((e, "epic") for e in a["resisted"])
    out = []
    boss = powerroll.scaled(a["boss"], 50)
    cells = [("boss p50", [boss], a["boss_room"])]
    pairs = [(g, r) for g, w, r in groups_of(a["regions"][:1]) if len(g) == 2]
    if pairs:
        cells.append(("ordinary pairs", None, None))
    for label, eids, room in cells:
        vals = []
        for books in (right, wrong, ()):
            if eids is not None:
                vals.append(mean_run(eids, room, lvl, n, rarity=rar, spells=books)["win"])
            else:
                vals.append(sum(mean_run(g, r, lvl, n, rarity=rar, spells=books)["win"] for g, r in pairs) / len(pairs))
        out.append((label, vals[0], vals[1], vals[2]))
    return out


def report_lanes(key, args):
    a = RING5[key]
    lvl = args.level or a["level"]
    heading("Lane test, %s (%s gear, level %d): right lane %s, wrong lane %s" % (
        a["label"], a["recommended"], lvl, "+".join(a["strong"]), "+".join(a["resisted"])))
    print("%-16s %8s %8s %8s   %s" % ("", "right", "wrong", "none", "lift / wrong vs none"))
    for label, r, w, z in lane_rows(key, args.n, lvl):
        print("%-16s %8.0f %8.0f %8.0f   %+.0f / %+.0f" % (label, r, w, z, r - z, w - z))


# ---------------------------------------------------------------------------- --check
class Checker:
    def __init__(self):
        self.fails = []
        self.warns = []
        self.cells = 0

    def warn(self, label, ok, detail):
        """Reported, never failing: prose guidelines and class-balance notes that the Queen stand-in shares."""
        if not ok:
            self.warns.append("%s: %s" % (label, detail))

    def report(self, areas):
        """The failures, then the warnings: nothing the checker found is left unprinted."""
        print("\nchecked %d cells (%s): %d outside their band, %d warnings" % (
            self.cells, ", ".join(areas), len(self.fails), len(self.warns)))
        for f in self.fails:
            print("  FAIL " + f)
        for w in self.warns:
            print("  WARN " + w)

    def exit_code(self, strict=False):
        return 1 if self.fails or (strict and self.warns) else 0

    def band(self, label, got, want, tol):
        self.cells += 1
        if abs(got - want) > tol:
            self.fails.append("%s: measured %.0f, pinned %d (+-%d)" % (label, got, want, tol))

    def span(self, label, got, lo, hi, slop):
        self.cells += 1
        if not (lo - slop <= got <= hi + slop):
            self.fails.append("%s: measured %.0f, wanted %d-%d (+-%d)" % (label, got, lo, hi, slop))

    def flag(self, label, ok, detail):
        self.cells += 1
        if not ok:
            self.fails.append("%s: %s" % (label, detail))


def check(args, areas=None):
    """Run the pinned cells of the selected areas, kits and powers; print the failures and the warnings; return the
    Checker. Warnings (per-class floors outside the Godlike-with-books rule, ordinary groups that cost too little or
    too much) never fail unless --strict; they are printed because spec 14.3 asks for them and they are the list of
    accepted exceptions kept in docs/V2-PLAN.md section 5f."""
    ck = Checker()
    n = args.n
    areas = areas or selected_areas(args)
    kits = ("kit", "none") if args.kit == "both" else (args.kit,)
    powers = set(args.powers)
    for key in (k for k in areas if k in RING5):
        a = RING5[key]
        lvl = args.level or a["level"]
        # bosses
        for kit in kits:
            for p, want in BOSS_CELLS[(key, kit)].items():
                if p not in powers:
                    continue
                eid = powerroll.scaled(a["boss"], p)
                spells = kit_for([powerroll.scaled(a["boss"], 50)]) if kit == "kit" else ()
                for b, w in zip(BUILDS, want):
                    m = mean_run([eid], a["boss_room"], lvl, n, **build_kw(b, spells))
                    ck.band("%s boss %s p%d %s" % (key, kit, p, b[0]), m["win"], w, TOL_P50 if p == 50 else TOL_OTHER)
                    if m["win"] > 30:
                        low = [c for c, v in m["by_class"].items() if v < m["win"] / 2]
                        detail = "%s below half the class mean %.0f (%s)" % (",".join(low), m["win"], per_class_text(m).strip())
                        label = "%s boss %s p%d %s per-class floor" % (key, kit, p, b[0])
                        if kit == "kit" and b[1] == "godlike":
                            ck.flag(label, not low, detail)       # the endgame builds with books: a hard rule
                        else:
                            ck.warn(label, not low, detail)       # the Queen stand-in has the same class gaps
        # minis
        for kit in kits:
            spells = ()
            if kit == "kit":
                spells = orrery_books(a["mini"]) if "attune" in ENEMIES[a["mini"]] else kit_for([a["mini"]])
            for b, w in zip(MINI_BUILDS, MINI_CELLS[(key, kit)]):
                m = mean_run([a["mini"]], a["mini_room"], lvl, n, **build_kw(b, spells))
                ck.band("%s mini %s %s" % (key, kit, b[0]), m["win"], w, TOL_MINI)
        if "attune" in ENEMIES[a["mini"]]:
            right = orrery_books(a["mini"], True)
            wrong = orrery_books(a["mini"], False)
            gaps = []
            for b in MINI_BUILDS:
                r = mean_run([a["mini"]], a["mini_room"], lvl, n, **build_kw(b, right))["win"]
                w = mean_run([a["mini"]], a["mini_room"], lvl, n, **build_kw(b, wrong))["win"]
                gaps.append(r - w)
            mid = sum(g for g in gaps[1:5]) / 4         # Ultra .. Leg+3: the builds where the books matter
            ck.span("%s orrery right-vs-wrong gap (mean of Ultra..Leg+3)" % key, mid, 15, 25, 5)
        # ordinary fights: the recommended tier, weighted by what a player meets
        groups = groups_of(a["regions"][:1])
        tot = sum(w for _, w, _ in groups)
        win = left = 0.0
        for grp, w, room in groups:
            m = mean_run(grp, room, lvl, n, rarity=a["recommended"], spells=())
            win += m["win"] * w / tot
            left += m["left"] * w / tot
            g = mean_run(grp, room, lvl, n, rarity="godlike", spells=())
            ck.flag("%s ordinary %s Godlike clears it" % (key, "+".join(grp)), g["win"] >= 69,
                    "Godlike wins only %.0f%%" % g["win"])
        ck.span("%s ordinary fights, %s win%% (weighted)" % (key, a["recommended"]), win, 55, 100, 10)
        ck.span("%s ordinary fights, %s health left (weighted)" % (key, a["recommended"]), left, 45, 60, 10)
        # lanes
        for label, r, w, z in lane_rows(key, n, lvl):
            ck.flag("%s lane %s: right lane lifts by 8 or more" % (key, label), r - z >= 8,
                    "right %.0f vs none %.0f" % (r, z))
            ck.flag("%s lane %s: wrong lane does not help" % (key, label), w - z <= 2,
                    "wrong %.0f vs none %.0f" % (w, z))
    for key in (k for k in areas if k in EXTENSIONS):
        a = EXTENSIONS[key]
        lvl = args.level or None
        m = ext_boss(key, n, lvl)
        ck.span("%s boss win%%" % a["boss"], m["win"], a["win"][0], a["win"][1], 5)
        ck.span("%s boss health left" % a["boss"], m["left"], a["left"][0], a["left"][1], 5)
        g = ext_groups(key, n, lvl)
        lost = 100 - g["left"]
        ck.warn("%s ordinary groups cost 20-40%% of health (weighted)" % key, 10 <= lost <= 50,
                "measured %.0f%% lost" % lost)
    ck.report(areas)
    return ck


def selected_areas(args):
    return list(RING5) + list(EXTENSIONS) if args.area == "all" else [args.area]


def main():
    ap = argparse.ArgumentParser(description="Ring-5 and extension calibration (docs/M6-SPEC.md sections 14 and 15)")
    ap.add_argument("--area", default="all", help="ff, vg, hos, rl, lw or all")
    ap.add_argument("--level", type=int, default=0, help="override the area's level")
    ap.add_argument("--n", type=int, default=60, help="fights per class per cell")
    ap.add_argument("--kit", default="both", choices=["none", "kit", "both"])
    ap.add_argument("--powers", default=",".join(str(p) for p in POWERS))
    ap.add_argument("--classes", action="store_true", help="also print the classes separately")
    ap.add_argument("--lane", action="store_true", help="the right lane vs the wrong lane vs no books")
    ap.add_argument("--standin", action="store_true", help="also run the Queen / Steward stand-ins")
    ap.add_argument("--check", action="store_true", help="exit 1 if a pinned cell of section 14 is out of its band")
    ap.add_argument("--strict", action="store_true", help="with --check: warnings (per-class floors) fail too")
    args = ap.parse_args()
    args.powers = [int(x) for x in args.powers.split(",")]
    areas = selected_areas(args)
    for a in areas:
        if a not in RING5 and a not in EXTENSIONS:
            sys.exit("unknown area %r (ff, vg, hos, rl, lw, all)" % a)
    if args.check:
        ck = check(args, areas)
        sys.exit(ck.exit_code(args.strict))
    kits = ["none", "kit"] if args.kit == "both" else [args.kit]
    for a in areas:
        if a in RING5:
            report_ring5(a, args, kits)
            if args.lane:
                report_lanes(a, args)
        else:
            report_ext(a, args)


if __name__ == "__main__":
    main()
