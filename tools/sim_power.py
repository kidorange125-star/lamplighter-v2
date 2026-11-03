"""Power-curve report: how each gear tier fares against the final base-game boss and against stronger, future ones.

usage: python tools/sim_power.py [--n 60] [--class wayfarer] [--boss hollow_king] [--level 8]

Rows are builds, columns are boss strength (1.0 = the real boss, 2.0 = twice the health and damage, and so on).
The design targets (docs/V2-PLAN.md section 2.4):
  - a plain Godlike weapon beats every base-game boss comfortably;
  - bosses of future areas outgrow it, so staying ahead takes stacking: Legendary or Godlike plus relics.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import sim  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=60)
ap.add_argument("--class", dest="cls", default="wayfarer")
ap.add_argument("--boss", default="hollow_king")
ap.add_argument("--level", type=int, default=8)
ap.add_argument("--scales", default="1,1.5,2,3,4")
args = ap.parse_args()

WEAPON = {"warden": "saltsteel_saber", "wayfarer": "saltsteel_saber", "ashblade": "ashwood_rod"}[args.cls]
ITEMS = {"draught": 4, "strong_draught": 4, "oil": 4}
LANTERN = {"shroud": True, "trim": True, "lens": True}
RELIC = {"warden": "edge", "wayfarer": "edge", "ashblade": "ember"}[args.cls]


def build(rarity, n_relics=0, relic_rarity="legendary", armor_relics=0):
    return lambda: sim.maxed(args.cls, args.level, WEAPON, "hauberk", rarity,
                             relics=[(RELIC, relic_rarity)] * n_relics,
                             armor_relics=[("heart", relic_rarity)] * armor_relics,
                             items=ITEMS, lantern=LANTERN)


BUILDS = [
    ("Rare (what the base game gives)", build("rare")),
    ("Epic", build("epic")),
    ("Ultra", build("ultra")),
    ("Legendary", build("legendary")),
    ("Godlike, plain", build("godlike")),
    ("Legendary + 3 Legendary relics", build("legendary", 3)),
    ("Godlike + 3 Legendary relics", build("godlike", 3)),
    ("Godlike + 3 relics + armour relics", build("godlike", 3, armor_relics=3)),
]

scales = [float(x) for x in args.scales.split(",")]
print("%s, level %d, vs %s. Win rate with the game's suggested play (average rounds)" % (args.cls, args.level, args.boss))
print("%-38s" % "build" + "".join("%12s" % ("x%g" % s) for s in scales))
for label, builder in BUILDS:
    row = "%-38s" % label
    for s in scales:
        eid = sim.scaled_enemy(args.boss, hp=s, atk=s)
        r = sim.win_rate([eid], sim.suggested, n=args.n, builder=builder, room="lightwell")
        row += "%12s" % ("%d%% /%4.1f" % (round(100 * r["win"]), r["rounds"]))
    print(row)
