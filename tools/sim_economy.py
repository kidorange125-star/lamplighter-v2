"""Economy model (docs/M6-SPEC.md sections 15 and 16): what an hour of play pays, and what the forge costs in hours.

usage: python tools/sim_economy.py [--area base|ext|court|ff|vg|annex|all] [--check]

From the data files and the encounter chances (no fights are run): for every place, the gold, Hollow Cores, Rime,
Vigil Glass and Hearts a casual player collects per hour, the hours to afford each forge tier, the Godlike and Long
Quench bills, and the ledger of section 16.1. --check exits 1 if a figure is outside the range section 16.1 gives it:
gold an hour, the single-figure targets, the annex ratio, Hearts an hour, the ledger and the days to the first Godlike.

The figures for the base rings and the Court are the spec's own (150 and 450 an hour): they existed before M6 and the
ledger leaves them as they were; the model's reading of them is checked to within 40 percent.

The model (section 16.1): a casual hour is 5 moves a minute and 1.7 minutes a fight, which the spec rounds to 15 fights an
hour in the base rings and the extensions, 18 in the Court and the Vigil, 20 in the Frostfair and the annexes. A fight is
the room's encounter table, weighted by (the room's chance x the group's share of its table), so each room with
random fights counts equally. A fight pays its group's gold (the middle of each enemy's range) plus its junk at full
price (Tallow and Odo pay it): that, and only that, is the "gold an hour" every range and ledger line is compared with
(section 16.1 defines a fight as group gold plus junk). Materials (Rime, Vigil Glass, essences, Hearts) are the forge's
inputs, which a player keeps, so they are reported in their own column at their sale value and never counted as cash;
other drops (gear) sell at half and are also reported separately. Keys and pages never sell.
A rolled boss pays its gold x the reward multiplier of power 50 (1.2).

casual play: 4 sessions of 30 minutes a week, so a session every 1.75 days and rent always at its cap.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import forge, powerroll  # noqa: E402
from lamplighter.content import BUILDINGS, ENEMIES, FORGE, ITEMS, ROOMS  # noqa: E402
from lamplighter.town import RENT_CAP_HOURS  # noqa: E402

# place: (regions averaged, fights an hour)
PLACES = {
    "base": ("Base rings", ["Weeping Wood", "Saltmarsh", "Underdeep"], 15),
    "ext": ("Extensions (3)", ["The Moth-Saint's Hospice", "The Reedlight", "The Lampwrights' Deep"], 15),
    "court": ("Ember Court", ["Ember Court"], 18),
    "ff": ("The Frostfair", ["The Frostfair"], 20),
    "vg": ("The Vigil", ["The Vigil"], 18),
    "ff_annex": ("The Fair Below", ["The Fair Below"], 20),
    "vg_annex": ("The Waking Cellars", ["The Waking Cellars"], 20),
}
AREA_KEYS = {"base": ["base"], "ext": ["ext"], "court": ["court"], "ff": ["ff"], "vg": ["vg"],
             "annex": ["ff_annex", "vg_annex"], "all": list(PLACES)}
# section 16.1: the explicit gold-per-hour ranges (the model is rounded, so the check allows RANGE_SLOP either side)
RANGES = {"ff": (1600, 2100), "vg": (1900, 2500)}
RANGE_SLOP = 0.05
# single-figure targets of the same table: shown with the measured value and failed when more than TARGET_SLOP off
TARGETS = {"base": 150, "ext": 300, "court": 450}
TARGET_SLOP = 0.40
# the annexes pay x1.2 of their area (section 16.1); Hearts 2 to 3 an hour; the model is rounded, so a margin each way
ANNEX_RATIO, ANNEX_SLOP = 1.2, 0.2
HEARTS_RANGE, HEARTS_SLOP = (2.0, 3.0), 0.10
# days of casual play to afford the first Godlike after the recipe (section 16.1: 9 to 11; a margin of DAYS_SLOP each way)
DAYS_RANGE, DAYS_SLOP = (9, 11), 0.10
# the 16 hours to the Godlike recipe (section 16.2); the last 3.0 hours (turn-ins, forge waits, attempts) come after it
STAGE_HOURS = [("Base game", 4.5, "base"), ("Extensions", 3.0, "ext"), ("Ember Court", 2.0, "court"),
               ("Frostfair", 3.0, "ff"), ("Vigil", 3.5, "vg")]
EXISTING = ("base", "court")                  # unchanged by M6: the spec's own figure is used, not the model's
VAULTS = {"ff": 900, "vg": 600}               # section 16.1: the loot on the vault floors, in gold
SESSION_HOURS, SESSIONS_PER_WEEK = 0.5, 4
SPENT_CONSTANTS = [("trinket and relics", 4000), ("call-back fees", 2500), ("materials bought from Odo", 2000)]
KEEP_BY_HEART = "core_heart_"


# ---------------------------------------------------------------------------- the per-fight model
def region_groups(region):
    """[(group, weight)] for the region's random encounters (weight = room chance x group share, summed over rooms)."""
    out = {}
    for r in ROOMS.values():
        if r["region"] != region or not r.get("enc"):
            continue
        total = sum(w for _, w in r["enc"]["groups"])
        for grp, w in r["enc"]["groups"]:
            out[tuple(grp)] = out.get(tuple(grp), 0.0) + r["enc"]["chance"] * w / total
    s = sum(out.values())
    return [(list(g), w / s) for g, w in out.items()]


def sale_value(iid):
    it = ITEMS[iid]
    if it["kind"] in ("key", "page"):
        return 0
    return it["value"] if it["kind"] in ("junk", "material") else max(1, it["value"] // 2)


def sale_kind(iid):
    """Which column a drop's sale value is reported in: junk is cash, materials are the forge's, the rest is gear."""
    kind = ITEMS[iid]["kind"]
    return kind if kind in ("junk", "material") else "other"


def per_fight(region):
    """Expected per fight: {"gold", "junk", "materials", "other", "drops": {item: expected count}}."""
    gold = 0.0
    sales = {"junk": 0.0, "material": 0.0, "other": 0.0}
    drops = {}
    for grp, w in region_groups(region):
        for eid in grp:
            e = ENEMIES[eid]
            lo, hi = e["gold"]
            gold += w * (lo + hi) / 2.0
            for iid, ch in e.get("drops", []):
                drops[iid] = drops.get(iid, 0.0) + w * ch
                sales[sale_kind(iid)] += w * ch * sale_value(iid)
    return {"gold": gold, "junk": sales["junk"], "materials": sales["material"], "other": sales["other"],
            "drops": drops}


def place_stats(key):
    label, regions, fights = PLACES[key]
    per = [per_fight(r) for r in regions]
    n = len(per)
    drops = {}
    for p in per:
        for iid, c in p["drops"].items():
            drops[iid] = drops.get(iid, 0.0) + c / n
    avg = {k: sum(p[k] for p in per) / n for k in ("gold", "junk", "materials", "other")}
    hearts = sum(c for iid, c in drops.items() if iid.startswith(KEEP_BY_HEART))
    return {"label": label, "fights": fights, "gold_fight": avg["gold"], "junk_fight": avg["junk"],
            "gold_hour": fights * (avg["gold"] + avg["junk"]), "gold_only_hour": fights * avg["gold"],
            "materials_hour": fights * avg["materials"], "other_hour": fights * avg["other"],
            "rime": fights * drops.get("ff_rime", 0.0), "glass": fights * drops.get("vg_starglass", 0.0),
            "cores": fights * drops.get("hollow_core", 0.0), "hearts": fights * hearts}


# ---------------------------------------------------------------------------- the forge
def expected_attempts(chance, pity, bonus=None):
    """Mean forgings to success: each failure adds `heat_bonus` to the chance, and `pity` failures guarantee it."""
    bonus = FORGE["heat_bonus"] if bonus is None else bonus
    e, alive = 0.0, 1.0
    for h in range(pity + 1):
        e += alive
        p = 1.0 if h >= pity else min(1.0, chance + bonus * h)
        alive *= 1 - p
    return e


def tier_costs():
    """{tier: (gold an attempt, expected attempts, expected gold)} for gear."""
    out = {}
    for name, t in FORGE["tiers"].items():
        e = expected_attempts(t["chance"], t["pity"])
        out[name] = (t["gold"], e, t["gold"] * e)
    return out


def rent_rate():
    return sum(b["rent"] for b in BUILDINGS.values())


def rent_per_session():
    """Casual play comes back every 1.75 days, far past the cap, so every collection pays the cap."""
    return rent_rate() * RENT_CAP_HOURS


def annex_ratio(key):
    """How much an annex pays against its area: the spec says x1.2."""
    return place_stats(key)["gold_hour"] / place_stats(key.split("_")[0])["gold_hour"]


def casual_week():
    """Gold in a casual week after the recipe: 4 sessions of 30 minutes in the annexes plus rent at its cap each time."""
    annex = (place_stats("ff_annex")["gold_hour"] + place_stats("vg_annex")["gold_hour"]) / 2
    return SESSIONS_PER_WEEK * SESSION_HOURS * annex + SESSIONS_PER_WEEK * rent_per_session(), annex


def godlike_days():
    """(purse still short at the recipe, days of casual play to cover it): the first Godlike's expected gold less what
    the ledger leaves, earned at a casual week's rate."""
    earned, spent, _ = ledger()
    need = max(0.0, tier_costs()["legendary"][2] - (sum(v for _, v in earned) - sum(v for _, v in spent)))
    return need, need / (casual_week()[0] / 7.0)


def building_gold():
    return sum(b["cost"]["gold"] for b in BUILDINGS.values())


# ---------------------------------------------------------------------------- reports
def report_places(keys):
    print("Per casual hour (fights an hour from section 16.1). gold/hour = group gold + junk, the figure every range uses;")
    print("materials (the forge's inputs, kept) and other drops (gear, half price) are shown apart and are not cash.")
    print("%-22s %6s %9s %7s %10s %9s %10s %7s %6s %6s %6s %8s" % (
        "place", "fights", "gold/fight", "+junk", "gold/hour", "(gold)", "materials", "gear", "cores", "rime", "glass",
        "hearts"))
    for k in keys:
        s = place_stats(k)
        print("%-22s %6d %9.1f %7.1f %10.0f %9.0f %10.0f %7.0f %6.1f %6.1f %6.1f %8.2f" % (
            s["label"], s["fights"], s["gold_fight"], s["junk_fight"], s["gold_hour"], s["gold_only_hour"],
            s["materials_hour"], s["other_hour"], s["cores"], s["rime"], s["glass"], s["hearts"]))
    print("\nTargets of section 16.1:")
    for k in keys:
        s = place_stats(k)
        if k in RANGES:
            lo, hi = RANGES[k]
            print("  %-22s %d - %d gold an hour (measured %.0f)" % (s["label"], lo, hi, s["gold_hour"]))
        elif k in TARGETS:
            print("  %-22s about %d gold an hour (measured %.0f, %+.0f%%)" % (
                s["label"], TARGETS[k], s["gold_hour"], 100.0 * (s["gold_hour"] / TARGETS[k] - 1)))
        elif k.endswith("_annex"):
            print("  %-22s x1.2 of its area (measured x%.2f)" % (s["label"], annex_ratio(k)))


def report_forge(keys):
    ff, vg = place_stats("ff"), place_stats("vg")
    best = max(ff["gold_hour"], vg["gold_hour"])
    print("\nThe forge: expected cost and the hours of play (at the best ring-5 rate, %.0f gold an hour) to pay it" % best)
    print("%-10s %8s %9s %10s %8s" % ("tier", "gold", "attempts", "expected", "hours"))
    for name, (gold, e, tot) in tier_costs().items():
        print("%-10s %8d %9.2f %10.0f %8.1f" % (name + " >", gold, e, tot, tot / best))
    t = FORGE["tiers"]["legendary"]
    e = tier_costs()["legendary"][1]
    print("A Godlike forging also takes %s each attempt (about %.0f of each over %.2f attempts) and both anvils for a day." % (
        ", ".join("%d %s" % (n, ITEMS[m]["name"]) for m, n in t["items"].items() if m in ("ff_rime", "vg_starglass")),
        e * t["items"]["ff_rime"] * (1 - FORGE["refund"] * (e - 1) / e), e))
    print("Rime and Vigil Glass come at about %.1f and %.1f an hour, so the materials cost %.1f and %.1f hours: "
          "gold is the throttle." % (ff["rime"], vg["glass"], e * t["items"]["ff_rime"] / ff["rime"],
                                     e * t["items"]["vg_starglass"] / vg["glass"]))


def ledger():
    """The section 16.1 ledger as numbers: (earned lines, spent lines, hours to the recipe)."""
    earned, hours = [], 0.0
    fights_total = 0.0
    for name, hrs, key in STAGE_HOURS:
        ks = AREA_KEYS[key]
        rate = TARGETS[key] if key in EXISTING else sum(place_stats(k)["gold_hour"] for k in ks) / len(ks)
        fights_total += hrs * rate
        hours += hrs
    boss = 0.0
    for eid, k in (("ff_lampmaster", "ff"), ("vg_prior_eye", "vg")):
        lo, hi = ENEMIES[eid]["gold"]
        boss += (lo + hi) / 2 * powerroll.reward_mult(50) + VAULTS[k]
    earned.append(("fights, bosses and vaults", fights_total + boss))
    sessions = hours / SESSION_HOURS
    # buildings arrive over the game: on average half of the full rent is running
    earned.append(("rent (half the full rate on average, at the cap)", sessions * 0.5 * rent_per_session()))
    tiers = tier_costs()
    spent = [("weapon Rare to Legendary (expected)", sum(tiers[t][2] for t in ("rare", "epic", "ultra"))),
             ("armour to Ultra (expected)", sum(tiers[t][2] for t in ("rare", "epic"))),
             ("buildings", building_gold())] + list(SPENT_CONSTANTS)
    return earned, spent, hours


def report_ledger():
    earned, spent, hours = ledger()
    print("\nLedger to the Godlike recipe (%.1f hours of play; spec: fights about 20k, rent about 8k, spent about 25k)" % hours)
    for n, v in earned:
        print("  earned  %-52s %8.0f" % (n, v))
    for n, v in spent:
        print("  spent   %-52s %8.0f" % (n, v))
    te, ts = sum(v for _, v in earned), sum(v for _, v in spent)
    print("  total   earned %.0f, spent %.0f, left %.0f" % (te, ts, te - ts))
    god = tier_costs()["legendary"]
    week, annex = casual_week()
    need, days_gold = godlike_days()
    print("\nThe first Godlike: %.2f attempts on average, %.0f gold (one attempt a day, so %.1f days of waiting)." % (
        god[1], god[2], god[1]))
    print("  a casual week pays about %.0f (%d sessions in the annexes at %.0f an hour, plus rent at its cap)" % (
        week, SESSIONS_PER_WEEK, annex))
    print("  after the recipe the purse is %.0f short, which is %.0f days of casual play (section 16.1 says %d to %d)." % (
        need, days_gold, DAYS_RANGE[0], DAYS_RANGE[1]))
    print("  Long Quench: %s, then seven days." % ", ".join(
        ["9000 gold"] + ["%d %s" % (n, ITEMS[m]["name"]) for m, n in __import__("lamplighter.quench", fromlist=["CFG"]).CFG["items"].items()]))


# ---------------------------------------------------------------------------- --check
def figures():
    """Every figure --check looks at: [(label, measured, lowest allowed, highest allowed)]."""
    out = []

    def expect(label, got, lo, hi):
        out.append((label, got, lo, hi))

    for k, (lo, hi) in RANGES.items():
        s = place_stats(k)
        expect("%s gold an hour (+-%d%%)" % (s["label"], 100 * RANGE_SLOP), s["gold_hour"],
               lo * (1 - RANGE_SLOP), hi * (1 + RANGE_SLOP))
    for k, e, lo, hi in (("ff", "ff_lampmaster", 600, 750), ("vg", "vg_prior_eye", 1100, 1400)):
        g = ENEMIES[e]["gold"]
        expect("%s boss gold range" % e, g[0], lo, lo)
        expect("%s boss gold range (top)" % e, g[1], hi, hi)
    expect("rent across all buildings", rent_rate(), 63, 63)
    expect("buildings cost (spec: about 3.5k)", building_gold(), 3150, 3850)
    tiers = tier_costs()
    expect("weapon Rare to Legendary expected gold (spec 10.0k)", sum(tiers[t][2] for t in ("rare", "epic", "ultra")),
           9500, 10500)
    expect("armour to Ultra expected gold (spec 2.7k)", sum(tiers[t][2] for t in ("rare", "epic")), 2570, 2830)
    expect("Godlike attempts (spec 6.42)", tiers["legendary"][1], 6.37, 6.47)
    expect("Godlike expected gold (spec 19.3k)", tiers["legendary"][2], 18900, 19700)
    earned, spent, _ = ledger()
    expect("ledger: earned fights/bosses/vaults (spec about 20k)", earned[0][1], 17000, 23000)
    expect("ledger: earned rent (spec about 8k)", earned[1][1], 6500, 9500)
    expect("ledger: spent in all (spec about 25k)", sum(v for _, v in spent), 23000, 27000)
    expect("ledger: earned minus spent", sum(v for _, v in earned) - sum(v for _, v in spent), 0, 10 ** 9)
    for k, target in TARGETS.items():
        s = place_stats(k)
        expect("%s gold an hour against the spec's %d (+-%d%%)" % (s["label"], target, 100 * TARGET_SLOP),
               s["gold_hour"], target * (1 - TARGET_SLOP), target * (1 + TARGET_SLOP))
    for k in ("ff_annex", "vg_annex"):
        s = place_stats(k)
        expect("%s pays x%.1f of its area (+-%.1f)" % (s["label"], ANNEX_RATIO, ANNEX_SLOP), annex_ratio(k),
               ANNEX_RATIO - ANNEX_SLOP, ANNEX_RATIO + ANNEX_SLOP)
        expect("%s Hearts an hour (spec %g to %g, +-%d%%)" % (
            s["label"], HEARTS_RANGE[0], HEARTS_RANGE[1], 100 * HEARTS_SLOP), s["hearts"],
               HEARTS_RANGE[0] * (1 - HEARTS_SLOP), HEARTS_RANGE[1] * (1 + HEARTS_SLOP))
    expect("days of casual play to the first Godlike after the recipe (spec %d to %d, +-%d%%)" % (
        DAYS_RANGE[0], DAYS_RANGE[1], 100 * DAYS_SLOP), godlike_days()[1],
           DAYS_RANGE[0] * (1 - DAYS_SLOP), DAYS_RANGE[1] * (1 + DAYS_SLOP))
    ff, vg = place_stats("ff"), place_stats("vg")
    expect("Rime an hour (a Godlike attempt costs 4)", ff["rime"], 4, 10 ** 9)
    expect("Vigil Glass an hour (a Godlike attempt costs 4)", vg["glass"], 4, 10 ** 9)
    return out


def check():
    figs = figures()
    fails = ["%s: %.1f, wanted %.1f to %.1f" % (label, got, lo, hi) for label, got, lo, hi in figs if not lo <= got <= hi]
    print("checked %d figures: %d outside their range" % (len(figs), len(fails)))
    for f in fails:
        print("  FAIL " + f)
    return not fails


def main():
    ap = argparse.ArgumentParser(description="Economy model (docs/M6-SPEC.md sections 15 and 16)")
    ap.add_argument("--area", default="all", choices=sorted(AREA_KEYS))
    ap.add_argument("--check", action="store_true", help="exit 1 if a figure is outside its range in section 16.1")
    args = ap.parse_args()
    report_places(AREA_KEYS[args.area])
    if args.area == "all":
        report_forge(AREA_KEYS["all"])
        report_ledger()
    print()
    ok = check()
    if args.check and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
