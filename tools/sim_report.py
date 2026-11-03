"""Balance report: a realistic fight from each ring, for every class and a few play styles.

usage: python tools/sim_report.py [--n 60] [--classes wayfarer,warden,ashblade] [--policies suggested,flare_spam,no_flare]

Gear and level are what a sensible player has at that point in the story.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import sim  # noqa: E402

RING1 = dict(level=3, weapon="hunting_spear", armor="oilskin", items={"draught": 3, "oil": 2})
RING2 = dict(lantern={"shroud": True, "trim": True}, level=5, weapon="hunting_spear", armor="jerkin", trinket="saints_tooth", items={"draught": 4, "strong_draught": 1, "oil": 3})
RING3 = dict(lantern={"shroud": True, "trim": True, "lens": True}, level=7, weapon="censer_flail", armor="hauberk", trinket="saints_tooth", items={"draught": 5, "strong_draught": 3, "oil": 3})

# (label, enemies, gear, room)
SCENARIOS = [
    ("wolf pack", ["gloam_wolf", "gloam_wolf"], dict(RING1, level=2), "wood_path"),
    ("rootwight", ["rootwight"], dict(RING1, level=2), "hunters_camp"),
    ("ANTLERED MOTHER", ["antlered_mother"], RING1, "mother_grove"),
    ("lurker+wisp", ["bog_lurker", "wisp"], dict(RING2, level=4), "bog_lights"),
    ("REEVE", ["reeve_haskel"], dict(RING2, level=4), "reeve_house"),
    ("nave guard", ["salt_knight", "drowned_acolyte"], RING2, "chapel_nave"),
    ("DROWNED BISHOP", ["drowned_bishop"], RING2, "bishop_altar"),
    ("ghoul pair", ["tallow_ghoul", "tallow_ghoul"], dict(RING3, level=6), "mine_hall"),
    ("ORE-WARDEN", ["starsteel_golem"], dict(RING3, level=6), "ore_vein"),
    ("BROOD QUEEN", ["brood_queen", "crawler"], dict(RING3, level=6), "hollow_nest"),
    ("ASH CHOIR", ["alto", "tenor", "bass"], dict(RING3, level=6), "ash_choir"),
    ("PALE USHER", ["pale_usher"], RING3, "lightwell_gate"),
    ("HOLLOW KING", ["hollow_king"], RING3, "lightwell"),
]

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=60)
ap.add_argument("--classes", default="wayfarer,warden,ashblade")
ap.add_argument("--policies", default="suggested,flare_spam,no_flare")
ap.add_argument("--only", help="substring filter on scenario label")
args = ap.parse_args()

classes = args.classes.split(",")
policies = args.policies.split(",")
for cls in classes:
    print("\n== %s ==" % cls)
    head = "%-17s %-4s" % ("fight", "lvl")
    for pol in policies:
        head += "  %12s" % pol[:12]
    print(head + "    (win% / avg rounds)")
    for label, ids, gear, room in SCENARIOS:
        if args.only and args.only.lower() not in label.lower():
            continue
        row = "%-17s %-4d" % (label, gear["level"])
        for pol in policies:
            r = sim.win_rate(ids, sim.POLICIES[pol], n=args.n, cls=cls, room=room, **gear)
            row += "  %5d%% /%5.1f" % (round(100 * r["win"]), r["rounds"])
        print(row)
