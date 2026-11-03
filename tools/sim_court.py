"""Ember Court calibration: how each fight there fares against rare, epic, ultra and legendary builds.

usage: python tools/sim_court.py [--n 40] [--class wayfarer] [--level 9] [--only queen]

Targets (docs/V2-PLAN.md, M4): road and hall fights are fair for Epic gear (a Rare build struggles); a group costs
a third to a half of your health; the Steward is a real test for Epic; the Queen at median power (50) is hard for
Ultra and comfortable for Godlike, and her roll spans roughly 0.5x to 1.5x of that.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import powerroll, sim  # noqa: E402
from lamplighter.content import ROOMS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=40)
ap.add_argument("--class", dest="cls", default="wayfarer")
ap.add_argument("--level", type=int, default=9)
ap.add_argument("--only", default="")
ap.add_argument("--powers", default="1,25,50,75,100")
args = ap.parse_args()

WEAPON = {"warden": "saltsteel_saber", "wayfarer": "saltsteel_saber", "ashblade": "ashwood_rod"}[args.cls]
ITEMS = {"draught": 3, "strong_draught": 3, "oil": 3}
LANTERN = {"shroud": True, "trim": True, "lens": True}
RARITIES = ["rare", "epic", "ultra", "legendary", "godlike"]


def build(rarity):
    return lambda: sim.maxed(args.cls, args.level, WEAPON, "hauberk", rarity, items=ITEMS, lantern=LANTERN)


def row(label, ids, rarities=RARITIES):
    out = "%-34s" % label
    for r in rarities:
        s = sim.win_rate(ids, sim.suggested, n=args.n, builder=build(r), room="throne_room")
        mx = build(r)().max_hp
        out += "%14s" % ("%d%% hp%d%%" % (round(100 * s["win"]), round(100 * s["hp_on_win"] / mx)))
    print(out)


print("%s, level %d.  Win rate and average health left on a win (hp percent), with the game's suggested play" % (args.cls, args.level))
print("%-34s" % "fight" + "".join("%14s" % r for r in RARITIES))
if not args.only or args.only == "mobs":
    seen = set()
    for rid in ("cinder_road", "grand_hall", "ballroom", "kitchens"):
        for group, w in ROOMS[rid]["enc"]["groups"]:
            key = tuple(group)
            if key in seen:
                continue
            seen.add(key)
            row("+".join(group), list(group))
if not args.only or args.only == "steward":
    row("cinder_steward", ["cinder_steward"])
if not args.only or args.only == "queen":
    for p in [int(x) for x in args.powers.split(",")]:
        eid = powerroll.scaled("cinder_queen", p)
        row("queen at power %d" % p, [eid])
