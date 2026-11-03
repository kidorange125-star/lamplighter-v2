"""Smith report: what the Long Quench and a Godlike forging cost in gold, materials and calendar days.

usage: python tools/sim_smith.py [--n 10000] [--seed 1] [--session-days 1.75]

The Long Quench (lamplighter/quench.py, data/smith.json): 10,000 runs of "quench a fresh Godlike weapon until it is x3.0"
with the pity rule, keeping the better result each time. Shows the outcome distribution of a single quench at pity 0, how
many quenches (and so gold and calendar days) it takes to reach x3.0, and the cost of stopping at x2.5 or better.

The Godlike forging (data/forge.json): the odds, heat and pity of the Legendary tier, one attempt a day (it holds both
anvils for 1,440 minutes). A failure refunds half the materials. The casual player has a session every 1.75 days (four
30-minute sessions a week), so an attempt can only be collected and restarted at a session.

The design targets (docs/M6-SPEC.md sections 11 and 16): Godlike about 19.3k gold in 6.42 expected attempts; the Long
Quench a further week or two of waiting, and it is never mandatory.
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import quench  # noqa: E402
from lamplighter.content import FORGE, ITEMS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=10000)
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--session-days", type=float, default=1.75, help="days between casual play sessions")
args = ap.parse_args()
rng = random.Random(args.seed)
CFG = quench.CFG


def name(iid):
    return ITEMS[iid]["name"] if iid in ITEMS else iid


def next_session(days):
    """Calendar days until the first session at or after `days` have passed (a session every `session_days`)."""
    return math.ceil(days / args.session_days - 1e-9) * args.session_days


def quench_run(stop_at):
    """Quench a fresh weapon until it holds at least `stop_at`. Returns (attempts, days, final pity)."""
    held, pity, attempts, days = 1.0, 0, 0, 0.0
    while held < stop_at:
        attempts += 1
        days += next_session(CFG["days"])
        m = quench.roll(rng, pity)
        pity = 0 if m >= quench.best_mult() else pity + 1
        held = max(held, m)
    return attempts, days, pity


def mean(xs):
    return sum(xs) / len(xs)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


print("THE LONG QUENCH   (%d gold, %s; %d days; %d runs)" % (
    CFG["gold"], ", ".join("%d %s" % (n, name(m)) for m, n in CFG["items"].items()), CFG["days"], args.n))
print()
print("one quench at pity 0:")
base = {m: 0 for m, _ in quench.chances(0)}
for _ in range(args.n):
    base[quench.roll(rng, 0)] += 1
for (m, p) in reversed(quench.chances(0)):
    print("  x%.1f   drawn %5.1f%%   (odds %4.1f%%)" % (m, 100 * base[m] / args.n, 100 * p))
print()
print("pity ladder (chance of the best result after k results below it):")
print("  " + "   ".join("%d: %d%%" % (k, round(100 * dict(quench.chances(k))[quench.best_mult()])) for k in range(0, 6)))
print()
print("%-24s %9s %9s %9s %12s %10s" % ("goal (from a fresh Godlike)", "quenches", "median", "p90", "gold (mean)", "days"))
for label, stop in (("x2.0 or better", 2.0), ("x2.5 or better", 2.5), ("x3.0 (finished)", 3.0)):
    runs = [quench_run(stop) for _ in range(args.n)]
    att = [r[0] for r in runs]
    print("%-24s %9.2f %9d %9d %12d %10.1f" % (label, mean(att), pct(att, 0.5), pct(att, 0.9),
                                               mean(att) * CFG["gold"], mean([r[1] for r in runs])))
print()
print("(days assume a session every %.2f days; a quench takes %d real days, so it is collected at the session on or after that.)"
      % (args.session_days, CFG["days"]))
print("(gems can skip %d days of each quench at %d gems a day; that is not modelled here.)" % (
    CFG["hurry"]["max_days"], CFG["hurry"]["gems_per_day"]))

# ---------------------------------------------------------------- the Godlike forging
T = FORGE["tiers"]["legendary"]


def forging_run():
    """Forge a Legendary piece up to Godlike. Returns (attempts, gold, {material: spent}, days at 24h, days at sessions)."""
    heat, attempts = 0, 0
    spent = {m: 0.0 for m in T["items"]}
    while True:
        attempts += 1
        for m, n in T["items"].items():
            spent[m] += n
        if heat >= T["pity"] or rng.random() < min(1.0, T["chance"] + FORGE["heat_bonus"] * heat):
            return attempts, attempts * T["gold"], spent
        heat += 1
        for m, n in T["items"].items():
            spent[m] -= int(n * FORGE["refund"])


runs = [forging_run() for _ in range(args.n)]
att = [r[0] for r in runs]
print()
print("A GODLIKE FORGING   (%d gold, %s; %d minutes, both anvils; chance %d%%, pity %d, +%d%% a failure)" % (
    T["gold"], ", ".join("%d %s" % (n, name(m)) for m, n in T["items"].items()), T["minutes"],
    round(100 * T["chance"]), T["pity"], round(100 * FORGE["heat_bonus"])))
print("  attempts   mean %.2f   median %d   p90 %d   max %d" % (mean(att), pct(att, 0.5), pct(att, 0.9), max(att)))
print("  gold       mean %d   p90 %d" % (mean([r[1] for r in runs]), pct([r[1] for r in runs], 0.9)))
day = T["minutes"] / 1440.0
print("  days       %.1f at one attempt per %d hours;  %.1f with a session every %.2f days" % (
    mean(att) * day, T["minutes"] // 60, mean(att) * next_session(day), args.session_days))
print("  materials  " + ", ".join("%s %d" % (name(m), mean([r[2][m] for r in runs])) for m in T["items"]))
forge_gold = mean([r[1] for r in runs])
q = [quench_run(3.0) for _ in range(args.n)]
print()
print("Godlike, then the Long Quench to x3.0: about %d + %d = %d gold, and about %.0f + %.0f days at a session every "
      "%.2f days." % (forge_gold, mean([r[0] for r in q]) * CFG["gold"], forge_gold + mean([r[0] for r in q]) * CFG["gold"],
                      mean(att) * next_session(day), mean([r[1] for r in q]), args.session_days))
