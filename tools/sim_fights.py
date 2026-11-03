"""Simulate fights and print win rates, to tune balance.

examples:
  python tools/sim_fights.py antlered_mother --class wayfarer --level 3 --weapon hunting_spear
  python tools/sim_fights.py drowned_bishop --class warden --level 5 --policies suggested,no_flare
  python tools/sim_fights.py gloam_wolf,gloam_wolf --level 1 --n 500
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import sim  # noqa: E402
from lamplighter.content import ENEMIES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("enemies", help="comma separated enemy ids")
ap.add_argument("--class", dest="cls", default="wayfarer")
ap.add_argument("--level", type=int, default=3)
ap.add_argument("--weapon")
ap.add_argument("--armor")
ap.add_argument("--trinket")
ap.add_argument("--n", type=int, default=200)
ap.add_argument("--difficulty", type=float, default=1.0)
ap.add_argument("--draughts", type=int, default=3)
ap.add_argument("--oil", type=int, default=3, help="spare oil flasks")
ap.add_argument("--policies", default="suggested,flare_spam,no_flare,attack_only")
args = ap.parse_args()

ids = args.enemies.split(",")
for i in ids:
    if i not in ENEMIES:
        sys.exit("unknown enemy %r" % i)

print("%s vs %s  (level %d, %d runs)" % (args.cls, ", ".join(ids), args.level, args.n))
print("%-14s %7s %8s %10s" % ("policy", "win", "rounds", "hp on win"))
for name in args.policies.split(","):
    r = sim.win_rate(ids, sim.POLICIES[name], n=args.n, cls=args.cls, level=args.level, weapon=args.weapon,
                     armor=args.armor, trinket=args.trinket, difficulty=args.difficulty,
                     items={"draught": args.draughts, "oil": args.oil})
    print("%-14s %6d%% %8.1f %10.0f" % (name, round(100 * r["win"]), r["rounds"], r["hp_on_win"]))
