"""M6 package `late` (docs/M6-SPEC.md section 11): the forge retune, two-slot Godlike forging, the Long Quench, and the
Third Quench chain (six receipts -> Aldric's letter -> Corm's notes -> two Given Flames -> Tamsin -> godlike_recipe).

The items other packages own (the receipts, flames, notes, Rime and Vigil Glass) are stubbed here when their package has
not landed yet, with the ids of section 18; real ones are left alone."""
import contextlib
import copy
import io
import json
import random
import unittest

from lamplighter import clock, forge, forge_ui, gear, navigation, npcs, postgame, quench, savecheck, town, ui
from lamplighter.areas import late
from lamplighter.content import FORGE, ITEMS
from lamplighter.engine import Game
from lamplighter.quests import QUESTS
from tests.helpers import new_game, run, temp_home

STUBS = {
    "ff_rime": ("material", "Rime"), "vg_starglass": ("material", "Vigil Glass"),
    "hos_receipt": ("key", "Receipt: the Moth-Saint's Hospice"), "rl_receipt": ("key", "Receipt: the Reedlight"),
    "lw_receipt": ("key", "Receipt: the Lampwrights' Deep"), "ff_receipt": ("key", "Receipt: the Fair at Wintering"),
    "vg_receipt": ("key", "Receipt: the Vigil"), "ff_given_flame": ("key", "Marit's Flame"),
    "vg_given_flame": ("key", "Hale's Flame"), "lw_quench_notes": ("key", "Corm's Notes on the Quench"),
}
_added = []


def setUpModule():
    for iid, (kind, name) in STUBS.items():
        if iid not in ITEMS:
            ITEMS[iid] = {"name": name, "kind": kind, "value": 1, "desc": "A stand-in for the real item.",
                          "rarity": "common", **({"stack": True} if kind == "material" else {})}
            _added.append(iid)


def tearDownModule():
    for iid in _added:
        ITEMS.pop(iid, None)
    del _added[:]


class Rig(random.Random):
    """A random source whose .random() always returns the same number."""

    def __init__(self, value=0.0):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


class Clock:
    def __init__(self):
        self.t = 2_000_000.0

    def __call__(self):
        return self.t

    def advance(self, minutes=0, days=0):
        self.t += minutes * 60 + days * 86400


def capture(fn, *args, answers=()):
    ui.io.script = list(answers)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fn(*args)
    return " ".join(out.getvalue().split())           # (the screen wraps lines; compare as running text)


def give(g, iid):
    capture(g.give, iid, 1, True)


def talk(g, nid, *answers):
    ui.io.script = list(answers)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        npcs.talk(g, nid)
    return " ".join(out.getvalue().split())


def topic(g, nid, label_start):
    """The handler of the area topic whose label starts with this text (None if it is not on offer)."""
    from lamplighter import areas
    for label, fn in areas.topics(g, nid):
        if label.startswith(label_start):
            return fn
    return None


def run_topic(g, nid, label_start):
    fn = topic(g, nid, label_start)
    assert fn is not None, "%s has no topic %r" % (nid, label_start)
    return capture(fn, g, answers=[""] * 4)       # (a long scene ends with a pause)


class LateCase(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        clock.set_clock(self.clock)

    def tearDown(self):
        clock.set_clock(None)

    def game(self, roll=0.0, smithy=True):
        g = new_game()
        g.rng = Rig(roll)
        p = g.player
        p.gold = 100000
        for iid, n in (("slag", 200), ("saltstone", 100), ("hollow_core", 50), ("ff_rime", 40), ("vg_starglass", 40)):
            p.add_item(iid, n)
        if smithy:
            self.build_smithy(g)
        return g

    def build_smithy(self, g):
        st = town.state(g)
        if "ember_smithy" not in st["built"]:
            st["built"].append("ember_smithy")
            forge.state(g)["slots"] += 1
        g.flags["steward_dead"] = True

    def godlike(self, g, worn=True, temper=None, base="hunting_spear"):
        inst = gear.make(base, "godlike", random.Random(3), affixes=[])
        if temper:
            inst["temper"] = temper
            gear.rebuild(inst)
        gear.give(g.player, inst)
        if worn:
            g.player.inventory.pop(inst["id"])
            g.player.equipment["weapon"] = inst["id"]
        return inst["id"]

    def legendary(self, g, worn=False):
        inst = gear.make("hunting_spear", "legendary", random.Random(2), affixes=["keen"])
        gear.give(g.player, inst)
        if worn:
            g.player.inventory.pop(inst["id"])
            g.player.equipment["weapon"] = inst["id"]
        return inst["id"]

    def finish(self, g, days=8):
        self.clock.advance(days=days)
        forge.update(g)


# ============================================================================ 11.1 the retune
def expected_attempts(t):
    """Expected number of forgings of one tier with its odds, heat bonus and pity (a full heat bar is a sure thing)."""
    total, reach = 0.0, 1.0
    for k in range(t["pity"] + 1):
        total += reach
        p = 1.0 if k >= t["pity"] else min(1.0, t["chance"] + FORGE["heat_bonus"] * k)
        reach *= 1 - p
    return total


class RetuneTests(unittest.TestCase):
    def test_the_new_prices(self):
        t = FORGE["tiers"]
        self.assertEqual(t["rare"]["gold"], 250)
        self.assertEqual(t["epic"]["gold"], 600)
        self.assertEqual(t["ultra"]["gold"], 1500)
        self.assertEqual(t["ultra"]["items"], {"slag": 12, "saltstone": 6, "hollow_core": 2})
        g = t["legendary"]
        self.assertEqual(g["gold"], 3000)
        self.assertEqual(g["items"], {"slag": 20, "saltstone": 10, "hollow_core": 4, "ff_rime": 4, "vg_starglass": 4})
        self.assertEqual(g["slots"], 2)
        self.assertEqual(g["needs_flag"], "godlike_recipe")
        self.assertEqual((g["chance"], g["pity"], g["minutes"], g["steps"]), (0.02, 30, 1440, 800))

    def test_odds_pity_and_heat_are_untouched(self):
        t = FORGE["tiers"]
        self.assertEqual([(t[r]["chance"], t[r]["pity"]) for r in ("rare", "epic", "ultra", "legendary")],
                         [(0.35, 6), (0.2, 9), (0.1, 14), (0.02, 30)])
        self.assertEqual(FORGE["heat_bonus"], 0.04)

    def test_expected_gold_matches_the_spec(self):
        t = FORGE["tiers"]
        attempts = [expected_attempts(t[r]) for r in ("rare", "epic", "ultra", "legendary")]
        for got, want in zip(attempts, (2.48, 3.56, 4.82, 6.42)):
            self.assertAlmostEqual(got, want, places=1)
        gold = [a * t[r]["gold"] for a, r in zip(attempts, ("rare", "epic", "ultra", "legendary"))]
        for got, want in zip(gold, (620, 2140, 7230, 19260)):
            self.assertAlmostEqual(got, want, delta=want * 0.01)

    def test_material_demand_for_one_expected_godlike(self):
        t = FORGE["tiers"]["legendary"]
        # a failure refunds half, so the cost of N attempts is N x the single list x 0.5 plus 0.5 for the one that works
        factor = 1 + (expected_attempts(t) - 1) * (1 - FORGE["refund"])
        self.assertAlmostEqual(factor, 3.71, delta=0.05)
        want = {"slag": 74, "saltstone": 37, "hollow_core": 15, "ff_rime": 15, "vg_starglass": 15}
        for mid, n in want.items():
            self.assertAlmostEqual(t["items"][mid] * factor, n, delta=1.5)


# ============================================================================ 11.2 two-slot forging
class TwoSlotTests(LateCase):
    def test_godlike_attempt_is_refused_with_one_anvil(self):
        g = self.game(smithy=False)
        g.flags["godlike_recipe"] = True
        iid = self.legendary(g)
        ok, msg = forge.start(g, iid)
        self.assertFalse(ok)
        self.assertIn("second anvil", msg)
        self.assertIn("Ember Smithy", msg)
        self.assertEqual(forge.state(g)["jobs"], [])

    def test_the_recipe_text_points_at_orrin_and_the_smiths(self):
        g = self.game()
        iid = self.legendary(g)
        ok, msg = forge.start(g, iid)
        self.assertFalse(ok)
        self.assertIn("the third quench (ask Orrin about Aldric's receipts, then Brann and Tamsin)", msg)

    def test_godlike_attempt_succeeds_with_two_anvils_and_holds_both(self):
        g = self.game()
        g.flags["godlike_recipe"] = True
        iid = self.legendary(g)
        gold = g.player.gold
        ok, msg = forge.start(g, iid)
        self.assertTrue(ok, msg)
        self.assertEqual(g.player.gold, gold - 3000)
        self.assertEqual(g.player.inventory["ff_rime"], 36)
        self.assertEqual(g.player.inventory["vg_starglass"], 36)
        job = forge.state(g)["jobs"][0]
        self.assertEqual((job["slots"], job["kind"]), (2, "forge"))
        self.assertEqual(forge.free_slots(g), 0)
        self.assertEqual(forge.slots_needed(iid), 2)

    def test_mixed_jobs_account_for_slots(self):
        g = self.game()
        g.flags["godlike_recipe"] = True
        g.player.add_item("hauberk")
        god = self.legendary(g)
        self.assertTrue(forge.start(g, "hauberk")[0])
        self.assertEqual(forge.free_slots(g), 1)
        ok, msg = forge.start(g, god)               # one anvil is busy: a Godlike forging needs both
        self.assertFalse(ok)
        self.assertIn("both anvils", msg)
        forge.state(g)["jobs"].clear()
        self.assertTrue(forge.start(g, god)[0])
        g.player.add_item("hauberk")
        ok, msg = forge.start(g, "hauberk")         # the Godlike forging holds both
        self.assertFalse(ok)
        self.assertIn("busy", msg)

    def test_forging_a_godlike_gives_the_item_back_when_it_was_not_worn(self):
        g = self.game(roll=0.0)
        g.flags["godlike_recipe"] = True
        iid = self.legendary(g)
        forge.start(g, iid)
        self.finish(g, days=2)
        r = forge.collect(g, 0)
        self.assertTrue(r["success"])
        self.assertEqual(ITEMS[r["item"]]["rarity"], "godlike")
        self.assertEqual(g.player.inventory.get(r["item"]), 1)

    def test_a_failed_godlike_forging_refunds_half_and_returns_the_item(self):
        g = self.game(roll=0.99)
        g.flags["godlike_recipe"] = True
        iid = self.legendary(g, worn=True)
        forge.start(g, iid)
        self.assertIn("Loaner", ITEMS[g.player.equipment["weapon"]]["name"])
        self.finish(g, days=2)
        r = forge.collect(g, 0)
        self.assertFalse(r["success"])
        self.assertEqual(g.player.equipment["weapon"], iid)
        self.assertEqual(g.player.inventory["ff_rime"], 38)

    def test_old_saves_without_slots_or_kind_load(self):
        with temp_home():
            g = self.game(smithy=False)
            g.player.add_item("hauberk")
            forge.start(g, "hauberk")
            d = json.loads(json.dumps(g.to_dict()))
            for j in d["forge"]["jobs"]:
                j.pop("slots", None)
                j.pop("kind", None)
            savecheck.check(d)
            g2 = Game.from_dict(d)
            self.assertEqual(forge.free_slots(g2), 0)       # a job without "slots" holds one anvil
            self.assertEqual(len(forge.state(g2)["jobs"]), 1)
            self.finish(g2, days=1)
            self.assertEqual(forge.ready_jobs(g2), [0])
            self.assertEqual(forge.collect(g2, 0)["slot"], None)

    def test_savecheck_rejects_a_bad_job_key(self):
        with temp_home():
            g = self.game()
            g.player.add_item("hauberk")
            forge.start(g, "hauberk")
            d = json.loads(json.dumps(g.to_dict()))
            savecheck.check(copy.deepcopy(d))
            for key, bad in (("slots", 0), ("slots", "two"), ("slots", 1.5), ("kind", "melt"), ("hurried", -1)):
                dd = copy.deepcopy(d)
                dd["forge"]["jobs"][0][key] = bad
                with self.assertRaises(Exception, msg="%s=%r" % (key, bad)):
                    savecheck.check(dd)

    def test_forge_menu_shows_both_anvils_in_use(self):
        g = self.game()
        g.flags["godlike_recipe"] = True
        forge.start(g, self.legendary(g))
        out = capture(forge_ui._job_lines, g)
        self.assertIn("2 of 2", out)
        self.assertIn("both anvils", out)


# ============================================================================ 11.3 the Long Quench
class QuenchTests(LateCase):
    def ready(self, **kw):
        g = self.game(**kw)
        g.flags["godlike_recipe"] = True
        return g

    def test_the_odds_and_pity(self):
        self.assertEqual([(m, round(p, 4)) for m, p in quench.chances(0)], [(2.0, 0.45), (2.5, 0.35), (3.0, 0.2)])
        c1 = dict(quench.chances(1))
        self.assertAlmostEqual(c1[3.0], 0.30)
        self.assertAlmostEqual(c1[2.0] / c1[2.5], 45 / 35)
        self.assertAlmostEqual(sum(c1.values()), 1.0)
        self.assertAlmostEqual(dict(quench.chances(4))[3.0], 0.60)
        self.assertAlmostEqual(dict(quench.chances(50))[3.0], 0.60)        # capped

    def test_the_draw_follows_the_odds(self):
        rng = random.Random(7)
        n = 10000
        counts = {2.0: 0, 2.5: 0, 3.0: 0}
        for _ in range(n):
            counts[quench.roll(rng, 0)] += 1
        for m, want in ((2.0, 45), (2.5, 35), (3.0, 20)):
            self.assertAlmostEqual(100 * counts[m] / n, want, delta=1.5)

    def test_the_draw_is_never_below_x2(self):
        rng = random.Random(11)
        self.assertTrue(all(quench.roll(rng, k % 5) >= 2.0 for k in range(2000)))

    def test_only_a_godlike_weapon_is_taken(self):
        g = self.ready()
        legendary = self.legendary(g)
        ok, msg = quench.start(g, legendary)
        self.assertFalse(ok)
        self.assertIn("Godlike", msg)
        self.assertEqual(quench.candidates(g), [])
        g.player.add_item("hauberk")
        self.assertFalse(quench.start(g, "hauberk")[0])

    def test_it_needs_the_recipe_the_smithy_and_the_price(self):
        g = self.game(smithy=False)
        iid = self.godlike(g)
        lack = quench.missing(g, iid)
        self.assertTrue(any("third quench" in x for x in lack))
        self.assertTrue(any("Ember Smithy" in x for x in lack))
        g2 = self.ready()
        iid2 = self.godlike(g2)
        g2.player.gold = 8999
        self.assertEqual(quench.missing(g2, iid2), ["1 more gold"])
        g2.player.gold = 9000
        g2.player.inventory["ff_rime"] = 7
        self.assertEqual(quench.missing(g2, iid2), ["1 more %s" % ITEMS["ff_rime"]["name"]])
        ok, msg = quench.start(g2, iid2)
        self.assertFalse(ok)
        self.assertEqual(g2.player.gold, 9000)

    def test_starting_pays_and_leaves_a_loaner(self):
        g = self.ready()
        iid = self.godlike(g, worn=True)
        before = ITEMS[iid]["mult"]["dmg"]
        gold = g.player.gold
        self.assertTrue(quench.start(g, iid)[0])
        p = g.player
        self.assertEqual(p.gold, gold - 9000)
        self.assertEqual((p.inventory["hollow_core"], p.inventory["ff_rime"], p.inventory["vg_starglass"],
                          p.inventory["slag"]), (44, 32, 32, 180))
        job = forge.state(g)["jobs"][0]
        self.assertEqual((job["kind"], job["slots"], job["steps"]), ("temper", 1, 5000))
        self.assertEqual(job["ready_at"], self.clock.t + 7 * 86400)
        lo = ITEMS[p.equipment["weapon"]]
        self.assertTrue(lo["loaner"])
        self.assertAlmostEqual(lo["mult"]["dmg"], before * FORGE["loaner_penalty"], places=3)
        self.assertEqual(forge.free_slots(g), 1)                      # one anvil only
        self.assertTrue(quench.running(g))
        self.assertFalse(quench.start(g, self.godlike(g, worn=False))[0])     # one at a time

    def test_a_week_of_real_time_finishes_it_and_not_a_day_less(self):
        g = self.ready()
        iid = self.godlike(g)
        quench.start(g, iid)
        self.clock.advance(days=6, minutes=23 * 60)
        forge.update(g)
        self.assertEqual(forge.ready_jobs(g), [])
        self.clock.advance(minutes=61)
        forge.update(g)
        self.assertEqual(forge.ready_jobs(g), [0])
        self.assertTrue(any("Long Quench" in n for n in g.notices))

    def test_five_thousand_steps_also_finish_it(self):
        g = self.ready()
        quench.start(g, self.godlike(g))
        job = forge.state(g)["jobs"][0]
        job["steps"] = 1
        forge.on_step(g)
        self.assertEqual(forge.ready_jobs(g), [0])

    def test_the_result_is_stored_and_applied(self):
        g = self.ready(roll=0.5)                    # 0.5 is x2.5 at pity 0
        iid = self.godlike(g, worn=True)
        plain = ITEMS[iid]["mult"]["dmg"]
        quench.start(g, iid)
        self.finish(g)
        r = forge.collect(g, 0)
        self.assertEqual(r["kind"], "temper")
        self.assertEqual((r["rolled"], r["after"], r["improved"]), (2.5, 2.5, True))
        inst = ITEMS[iid]
        self.assertEqual(inst["temper"], 2.5)
        self.assertAlmostEqual(inst["mult"]["dmg"], plain * 2.5, places=3)
        self.assertTrue(inst["name"].startswith("Long-Quenched "))
        self.assertIn("Long-Quenched: all damage x2.5.", inst["desc"])
        self.assertEqual(g.player.equipment["weapon"], iid)                     # back in hand, loaner gone
        self.assertNotIn(r["item"], [x for x in g.player.inventory])
        self.assertEqual([i for i in g.player.gear if ITEMS[i].get("loaner")], [])

    def test_a_pack_weapon_comes_back_to_the_pack(self):
        g = self.ready(roll=0.0)
        iid = self.godlike(g, worn=False)
        quench.start(g, iid)
        self.assertNotIn(iid, g.player.inventory)
        self.finish(g)
        forge.collect(g, 0)
        self.assertEqual(g.player.inventory[iid], 1)
        self.assertEqual(ITEMS[iid]["temper"], 2.0)

    def test_it_never_destroys_and_never_goes_below_x2(self):
        for roll in (0.0, 0.3, 0.46, 0.8, 0.999):
            g = self.ready(roll=roll)
            iid = self.godlike(g, worn=True)
            quench.start(g, iid)
            self.finish(g)
            r = forge.collect(g, 0)
            self.assertGreaterEqual(ITEMS[iid]["temper"], 2.0)
            self.assertIn(iid, g.player.equipment.values())
            self.assertIn(iid, g.player.gear)
            self.assertEqual(r["after"], ITEMS[iid]["temper"])

    def test_pity_raises_the_best_chance_and_resets_on_x3(self):
        g = self.ready(roll=0.0)                    # always the lowest
        iid = self.godlike(g, worn=False)
        for k in range(1, 4):
            ITEMS[iid].pop("temper", None)
            gear.rebuild(ITEMS[iid])
            quench.start(g, iid)
            self.finish(g)
            r = forge.collect(g, 0)
            self.assertEqual(r["pity"], k)
            self.assertEqual(g.flags["late_quench_pity"], k)
        self.assertAlmostEqual(dict(quench.chances(quench.pity(g)))[3.0], 0.5)
        g.rng = Rig(0.999)
        ITEMS[iid].pop("temper", None)
        gear.rebuild(ITEMS[iid])
        quench.start(g, iid)
        self.finish(g)
        r = forge.collect(g, 0)
        self.assertEqual(r["rolled"], 3.0)
        self.assertEqual(g.flags["late_quench_pity"], 0)

    def test_keep_the_better(self):
        g = self.ready(roll=0.0)                    # rolls x2.0
        iid = self.godlike(g, worn=True, temper=2.5)
        quench.start(g, iid)
        self.finish(g)
        r = forge.collect(g, 0)
        self.assertEqual((r["rolled"], r["before"], r["after"], r["improved"]), (2.0, 2.5, 2.5, False))
        self.assertEqual(ITEMS[iid]["temper"], 2.5)
        self.assertEqual(g.flags["late_quench_pity"], 1)            # a roll below x3.0 still counts for pity
        out = capture(forge_ui.reveal_temper, r)
        self.assertIn("keeps the better", out)
        g.rng = Rig(0.999)
        quench.start(g, iid)
        self.finish(g)
        r = forge.collect(g, 0)
        self.assertEqual((r["after"], r["improved"]), (3.0, True))
        self.assertEqual(ITEMS[iid]["temper"], 3.0)

    def test_a_x3_weapon_cannot_be_requenched(self):
        g = self.ready()
        iid = self.godlike(g, temper=3.0)
        self.assertEqual(quench.candidates(g), [])
        ok, msg = quench.start(g, iid)
        self.assertFalse(ok)
        self.assertIn("already", msg)
        self.assertEqual(g.player.gold, 100000)

    def test_hurry_skips_a_day_twice_and_no_more(self):
        g = self.ready()
        quench.start(g, self.godlike(g))
        g.player.gems = 100
        job = forge.state(g)["jobs"][0]
        ready = job["ready_at"]
        self.assertEqual(forge.hurry_cost(job), 12)
        self.assertTrue(forge.hurry(g, 0))
        self.assertEqual((g.player.gems, job["ready_at"], job["hurried"]), (88, ready - 86400, 1))
        self.assertTrue(forge.hurry(g, 0))
        self.assertEqual((g.player.gems, job["ready_at"], job["hurried"]), (76, ready - 2 * 86400, 2))
        self.assertFalse(forge.hurry(g, 0))
        self.assertEqual(g.player.gems, 76)
        self.assertFalse(job["done"])
        self.clock.advance(days=4)                  # gems never replace the week: five real days remain
        forge.update(g)
        self.assertFalse(job["done"])
        self.clock.advance(days=1.01)
        forge.update(g)
        self.assertTrue(job["done"])

    def test_hurry_needs_the_gems(self):
        g = self.ready()
        quench.start(g, self.godlike(g))
        g.player.gems = 11
        self.assertFalse(forge.hurry(g, 0))
        self.assertEqual(g.player.gems, 11)

    def test_the_menu_shows_the_odds_first(self):
        g = self.ready()
        self.godlike(g)
        out = capture(quench.menu, g, answers=["0"])
        self.assertIn("x3.0 20%", out)
        self.assertIn("x2.5 35%", out)
        self.assertIn("x2.0 45%", out)
        self.assertIn("never destroys", out)
        self.assertEqual(forge.state(g)["jobs"], [])

    def test_the_menu_starts_a_quench(self):
        g = self.ready()
        iid = self.godlike(g)
        ui.io.script = ["1", "y"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            note = quench.menu(g)
        self.assertIn("take the", note)
        self.assertTrue(quench.running(g))
        self.assertEqual(forge.state(g)["jobs"][0]["item"], iid)

    def test_the_menu_says_when_the_recipe_is_unknown(self):
        g = self.game()
        self.godlike(g)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            note = quench.menu(g)
        self.assertTrue(note.startswith("{grey}Brann shakes his head"))
        self.assertIn("never destroys", buf.getvalue())

    def test_the_forge_menu_offers_it_only_once_it_applies(self):
        g = self.game()
        self.assertFalse(quench.unlocked(g))
        g.flags["godlike_recipe"] = True
        self.assertTrue(quench.unlocked(g))
        g.flags.pop("godlike_recipe")
        self.godlike(g, worn=False)
        self.assertTrue(quench.unlocked(g))
        out = capture(forge_ui.menu, g, answers=["0"])
        self.assertIn("Long Quench", out)

    def test_reveal_is_a_three_stop_sweep(self):
        g = self.ready(roll=0.999)
        iid = self.godlike(g)
        quench.start(g, iid)
        self.finish(g)
        r = forge.collect(g, 0)
        out = capture(forge_ui.reveal_temper, r)
        self.assertIn("X3.0", out)
        self.assertIn("It took", out)

    def test_save_round_trip_in_the_middle_of_a_quench(self):
        with temp_home():
            g = self.ready(roll=0.5)
            iid = self.godlike(g, worn=True, temper=2.0)
            quench.start(g, iid)
            g.player.gems = 50
            forge.hurry(g, 0)
            g.save(quiet=True)
            g2 = Game.load()
            job = forge.state(g2)["jobs"][0]
            self.assertEqual((job["kind"], job["slots"], job["hurried"], job["item"]), ("temper", 1, 1, iid))
            self.assertEqual(ITEMS[iid]["temper"], 2.0)
            lo = ITEMS[g2.player.equipment["weapon"]]
            self.assertTrue(lo["loaner"])
            self.assertNotIn("temper", lo)
            g2.rng = Rig(0.5)
            self.finish(g2)
            r = forge.collect(g2, 0)
            self.assertEqual(r["after"], 2.5)
            g2.save(quiet=True)
            g3 = Game.load()
            self.assertEqual(ITEMS[iid]["temper"], 2.5)
            self.assertEqual(g3.player.equipment["weapon"], iid)


class TemperGearTests(LateCase):
    def test_a_relic_socketed_after_the_quench_keeps_the_multiplier(self):
        g = self.game()
        iid = self.godlike(g, worn=False, temper=2.5)
        base = ITEMS[iid]["mult"]["dmg"]
        phys = ITEMS[iid]["mult"].get("phys", 1.0)
        g.player.add_item("relic_edge")
        new = forge.socket_in(g, iid, "relic_edge")
        self.assertEqual(new, iid)
        inst = ITEMS[iid]
        self.assertEqual(inst["temper"], 2.5)
        self.assertAlmostEqual(inst["mult"]["dmg"], base, places=3)           # (the relic is on its own key)
        self.assertGreater(inst["mult"].get("phys", 1.0), phys)
        self.assertTrue(inst["name"].startswith("Long-Quenched "))
        forge.take_out(g, iid, 0)
        self.assertAlmostEqual(ITEMS[iid]["mult"]["dmg"], base, places=3)
        self.assertEqual(ITEMS[iid]["temper"], 2.5)

    def test_the_multiplier_is_on_all_damage(self):
        g = self.game()
        plain = self.godlike(g, worn=False)
        tempered = self.godlike(g, worn=False, temper=3.0)
        self.assertAlmostEqual(ITEMS[tempered]["mult"]["dmg"] / ITEMS[plain]["mult"]["dmg"], 3.0, places=2)

    def test_the_loaner_carries_no_temper(self):
        g = self.game()
        iid = self.godlike(g, worn=True, temper=3.0)
        lo = gear.make_loaner(iid, random.Random(1))
        self.assertNotIn("temper", lo)
        self.assertFalse(lo["name"].startswith("Long-Quenched"))
        self.assertAlmostEqual(lo["mult"]["dmg"], gear.WEAPON_MULT["godlike"] * FORGE["loaner_penalty"] *
                               (ITEMS["hunting_spear"].get("mult", {}).get("dmg", 1.0)), places=2)
        lo["temper"] = 3.0                          # even if one slipped in, a loaner ignores it
        gear.rebuild(lo)
        self.assertFalse(lo["name"].startswith("Long-Quenched"))

    def test_good_gear_rejects_an_impossible_temper(self):
        g = self.game()
        iid = self.godlike(g, temper=2.5)
        inst = copy.deepcopy(ITEMS[iid])
        self.assertTrue(savecheck._good_gear(iid, inst))
        for bad in (9.9, 0.5, "2.5", None, True):
            inst["temper"] = bad
            self.assertFalse(savecheck._good_gear(iid, inst), bad)
        inst["temper"] = 3.5
        self.assertTrue(savecheck._good_gear(iid, inst))
        plain = copy.deepcopy(ITEMS[self.godlike(g)])
        self.assertTrue(savecheck._good_gear(plain["id"], plain))          # no temper key at all is fine


# ============================================================================ 11.4 the Third Quench
class ChainTests(LateCase):
    def give_receipts(self, g, which=late.RECEIPTS):
        for r in which:
            give(g, r)

    def test_each_receipt_starts_the_quest_and_counts(self):
        g = self.game()
        self.assertEqual(g.quest("late_lending"), -1)
        out = capture(g.give, "late_receipt_court")
        self.assertEqual(g.quest("late_lending"), 0)
        self.assertIn("Receipts: 1 of 6", out)
        self.assertIn("New quest", out)
        out = capture(g.give, "hos_receipt")
        self.assertIn("Receipts: 2 of 6", out)
        self.assertNotIn("New quest", out)
        text = QUESTS["late_lending"]["stages"][0](g)
        self.assertIn("2 of 6", text)
        self.assertEqual(sorted(late.AFTER_GAIN), sorted(late.RECEIPTS))

    def test_pell_gives_the_courts_receipt_once_the_queen_is_dead(self):
        g = self.game()
        self.assertIsNone(topic(g, "pell", "Ask for the Court's receipt"))
        g.flags["queen_dead"] = True
        out = run_topic(g, "pell", "Ask for the Court's receipt")
        self.assertIn("I've held it a hundred years", out)
        self.assertTrue(g.player.has_item("late_receipt_court"))
        self.assertIsNone(topic(g, "pell", "Ask for the Court's receipt"))
        self.assertEqual(g.quest("late_lending"), 0)

    def test_the_pell_topic_is_in_her_talk_menu(self):
        g = self.game()
        g.flags.update(queen_dead=True, pell_met=True)
        out = talk(g, "pell", "4", "0")
        self.assertIn("Ask for the Court's receipt", out)
        self.assertTrue(g.player.has_item("late_receipt_court"))

    def test_orrin_with_some_receipts_recognises_hands_and_names_no_place(self):
        g = self.game()
        self.give_receipts(g, ("late_receipt_court", "hos_receipt"))
        out = run_topic(g, "orrin", "Show him the receipts")
        self.assertIn("That is 2. There were six.", out)
        self.assertIn("waylamp", out)
        self.assertIn("last coal", out)
        for place in ("Hospice", "Reedlight", "Frostfair", "Vigil", "Lampwrights", "Moth-Saint"):
            self.assertNotIn(place, out)
        self.assertFalse(g.flags.get("late_letter_read"))
        self.assertFalse(g.player.has_item("late_aldrics_letter"))
        self.assertEqual(g.quest("late_lending"), 0)

    def test_orrin_without_any_receipt_has_no_topic(self):
        g = self.game()
        self.assertIsNone(topic(g, "orrin", "Show him the receipts"))

    def test_orrin_opens_the_letter_when_all_six_are_shown(self):
        g = self.game()
        self.give_receipts(g)
        self.assertTrue(late.EXTRA_NEWS["orrin"](g))
        self.assertTrue(npcs.has_news(g, "orrin"))
        out = run_topic(g, "orrin", "Show him the receipts")
        self.assertIn("drawer under his bed", out)
        self.assertIn("Fifty years. I am a coward, but I can keep a promise.", out)
        self.assertIn("the third quench is a flame that someone chose to give you", out)
        self.assertTrue(g.flags["late_letter_read"])
        self.assertTrue(g.player.has_item("late_aldrics_letter"))
        self.assertEqual(g.quest("late_lending"), 1)
        self.assertFalse(late.EXTRA_NEWS["orrin"](g))
        self.assertIsNone(topic(g, "orrin", "Show him the receipts"))
        again = run_topic(g, "orrin", "Ask him to read Aldric's letter again")
        self.assertIn("so very sorry", again)

    def test_the_orrin_topic_is_in_his_talk_menu(self):
        g = self.game()
        g.set_quest("main", 3, quiet=True)
        self.give_receipts(g)
        out = talk(g, "orrin", "4", "", "0")
        self.assertIn("Show him the receipts", out)
        self.assertTrue(g.flags["late_letter_read"])

    def test_brann_and_corms_notes(self):
        g = self.game()
        self.assertIsNone(topic(g, "brann", "Show him Corm's notes"))
        self.assertIsNone(topic(g, "brann", "Ask what the third quench needs"))
        give(g, "lw_quench_notes")
        self.assertTrue(npcs.has_news(g, "brann"))
        out = run_topic(g, "brann", "Show him Corm's notes")
        self.assertIn("Two quenches I know.", out)
        self.assertIn("How do you make a smith give a flame?", out)
        self.assertTrue(g.flags["late_notes_shown"])
        self.assertIsNone(topic(g, "brann", "Show him Corm's notes"))
        self.assertFalse(late.EXTRA_NEWS["brann"](g))
        out = run_topic(g, "brann", "Ask what the third quench needs")
        self.assertIn("left with Orrin", out)
        self.assertIn("Marit", out)
        self.assertIn("Hale", out)
        self.assertNotIn("Corm's notes have not", out)
        give(g, "ff_given_flame")
        out = run_topic(g, "brann", "Ask what the third quench needs")
        self.assertNotIn("Marit", out)
        self.assertIn("Hale", out)

    def test_tamsin_names_exactly_what_is_missing(self):
        g = self.game()
        self.assertFalse(npcs.has_news(g, "tamsin") and late.EXTRA_NEWS["tamsin"](g))
        out = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertIn("Corm's notes on the quench, left in the Lampwrights' Deep", out)
        self.assertIn("left with Orrin", out)
        self.assertIn("Marit gives", out)
        self.assertIn("Hale gives", out)
        self.assertFalse(g.flags.get("godlike_recipe"))
        give(g, "lw_quench_notes")
        out = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertIn("have not been shown to Brann", out)
        g.flags["late_notes_shown"] = True
        g.flags["late_letter_read"] = True
        give(g, "ff_given_flame")
        out = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertNotIn("Corm", out)
        self.assertNotIn("letter", out)
        self.assertNotIn("Marit", out)
        self.assertIn("Hale gives", out)
        self.assertFalse(g.flags.get("godlike_recipe"))
        self.assertTrue(g.player.has_item("ff_given_flame"))             # nothing is taken until it can work

    def test_tamsin_has_no_topic_before_the_smithy_is_built(self):
        g = self.game(smithy=False)
        self.assertIsNone(topic(g, "tamsin", "Ask about the third quench"))

    def test_the_whole_chain_end_to_end(self):
        g = self.game(smithy=False)
        g.flags["queen_dead"] = True
        for r in late.RECEIPTS[:-1]:
            give(g, r)
        run_topic(g, "pell", "Ask for the Court's receipt")
        self.assertEqual(len(late.receipts_held(g)), 6)
        run_topic(g, "orrin", "Show him the receipts")
        give(g, "lw_quench_notes")
        run_topic(g, "brann", "Show him Corm's notes")
        give(g, "ff_given_flame")
        give(g, "vg_given_flame")
        self.assertIsNone(topic(g, "tamsin", "Ask about the third quench"))     # no smithy yet
        self.build_smithy(g)
        self.assertTrue(npcs.has_news(g, "tamsin"))
        out = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertIn("it sings", out)
        self.assertIn("It's a method.", out)
        self.assertTrue(g.flags["godlike_recipe"])
        self.assertTrue(g.flags["late_quench_done"])
        self.assertFalse(g.player.has_item("ff_given_flame"))
        self.assertFalse(g.player.has_item("vg_given_flame"))
        self.assertEqual(g.quest("late_lending"), "done")
        self.assertFalse(npcs.has_news(g, "tamsin") and late.EXTRA_NEWS["tamsin"](g))
        # and the forge now takes a Legendary piece to Godlike
        iid = self.legendary(g)
        self.assertEqual(forge.missing(g, iid), [])
        self.assertTrue(forge.start(g, iid)[0])

    def test_tamsin_scene_through_her_talk_menu(self):
        g = self.game()
        g.flags.update(late_notes_shown=True, late_letter_read=True, tamsin_met=True)
        give(g, "ff_given_flame")
        give(g, "vg_given_flame")
        out = talk(g, "tamsin", "3", "", "0")
        self.assertIn("Ask about the third quench", out)
        self.assertTrue(g.flags["godlike_recipe"])

    def test_the_journal_follows_the_quest(self):
        g = self.game()
        give(g, "hos_receipt")
        out = run(g, "journal")
        self.assertIn("Held in Trust", out)
        self.assertIn("1 of 6", out)
        g.set_quest("late_lending", 1, quiet=True)
        self.assertIn("Corm's notes", run(g, "journal"))
        g.set_quest("late_lending", "done", quiet=True)
        self.assertIn("third quench is known", QUESTS["late_lending"]["stages"]["done"])

    def test_side_objectives(self):
        g = self.game()
        self.assertEqual([o for o in navigation.objectives(g) if "receipts" in o["text"]], [])
        give(g, "hos_receipt")
        objs = [o for o in navigation.objectives(g) if "Aldric's receipts" in o["text"]]
        self.assertEqual(len(objs), 1)
        self.assertEqual((objs[0]["room"], objs[0]["side"]), ("hall", True))
        self.assertIn("1 of 6", objs[0]["text"])
        g.flags["late_letter_read"] = True
        objs = [o for o in navigation.objectives(g) if "third quench" in o["text"]]
        self.assertEqual((objs[0]["room"], objs[0]["side"]), ("ember_smithy", True))
        self.assertEqual([o for o in navigation.objectives(g) if "Aldric's receipts" in o["text"]], [])
        g.flags["godlike_recipe"] = True
        self.assertEqual([o for o in navigation.objectives(g) if "Long-Quenched" in o["text"]], [])
        iid = self.godlike(g)
        objs = [o for o in navigation.objectives(g) if "Long-Quenched" in o["text"]]
        self.assertEqual((objs[0]["room"], objs[0]["side"]), ("smithy", True))
        quench.start(g, iid)
        self.assertEqual([o for o in navigation.objectives(g) if "Long-Quenched" in o["text"]], [])

    def test_a_side_objective_never_becomes_the_main_one(self):
        g = self.game()
        give(g, "hos_receipt")
        main = navigation.main_objective(g)
        self.assertTrue(main is None or "receipts" not in main["text"])

    def test_nothing_here_is_undone_by_a_rewind(self):
        mine = set(late.RECEIPTS) | {"late_aldrics_letter", "ff_given_flame", "vg_given_flame", "lw_quench_notes"}
        flags = {"godlike_recipe", "late_letter_read", "late_notes_shown", "late_quench_done", "late_quench_pity"}
        for _, f, items in postgame.LAYERS:
            self.assertFalse(mine & set(items))
            self.assertFalse(flags & set(f))

    def test_the_receipts_cannot_be_dropped_sold_or_stashed(self):
        for r in late.RECEIPTS + (late.LETTER,) + late.FLAMES:
            self.assertEqual(ITEMS[r]["kind"], "key", r)

    def test_the_hooks_are_valid(self):
        self.assertEqual(late.CHECK(), [])
        for name in ("pell", "brann", "orrin", "tamsin"):
            self.assertIn(name, npcs.NPCS)
            self.assertIn(name, late.TOPICS)
        self.assertTrue(ITEMS["late_aldrics_letter"]["desc"].startswith("To the one who comes after"))
        self.assertTrue(ITEMS["late_receipt_court"]["desc"].endswith("Held in trust. -A."))


class ReviewFixTests(LateCase):
    """Regressions from the M6 review."""

    def ready(self):
        g = self.game()
        g.flags["godlike_recipe"] = True
        return g

    # -- the Long Quench screen while the only Godlike weapon is away
    def test_menu_does_not_deny_a_weapon_that_is_away_in_the_quench(self):
        g = self.ready()
        quench.start(g, self.godlike(g))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            note = quench.menu(g)
        self.assertNotIn("no Godlike", note)
        self.assertNotIn("finished", note)
        self.assertIn("One weapon at a time", note)
        self.assertIn("7 days", note)

    def test_menu_says_a_finished_job_is_waiting(self):
        g = self.ready()
        quench.start(g, self.godlike(g))
        self.finish(g)
        with contextlib.redirect_stdout(io.StringIO()):
            note = quench.menu(g)
        self.assertIn("collect it at the forge", note)
        self.assertNotIn("no Godlike", note)

    def test_menu_still_denies_when_nothing_is_running_and_nothing_qualifies(self):
        g = self.ready()
        self.godlike(g, temper=3.0)
        with contextlib.redirect_stdout(io.StringIO()):
            note = quench.menu(g)
        self.assertIn("no Godlike weapon", note)

    # -- a Godlike forging during a Long Quench
    def test_godlike_forging_during_the_quench_says_why_and_asks_nothing(self):
        g = self.ready()
        quench.start(g, self.godlike(g))
        god = self.legendary(g)
        ok, msg = forge.start(g, god)
        self.assertFalse(ok)
        self.assertIn("Long Quench", msg)
        self.assertIn("both anvils", msg)
        self.assertNotIn("Collect finished work", msg)
        ui.io.script = ["1"]                          # pick the spear; a confirm would find an empty script
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            note = forge_ui._start(g)
        self.assertIn("Long Quench", note)
        self.assertNotIn("Hand it to Brann", buf.getvalue())
        self.assertEqual(len(forge.state(g)["jobs"]), 1)

    def test_plain_busy_anvils_keep_the_old_wording(self):
        g = self.ready()
        g.player.add_item("hauberk")
        self.assertTrue(forge.start(g, "hauberk")[0])
        ok, msg = forge.start(g, self.legendary(g))
        self.assertFalse(ok)
        self.assertIn("Collect finished work first", msg)

    # -- the loaner of a tempered weapon
    def test_requenching_a_tempered_worn_weapon_warns_about_the_loaner(self):
        g = self.ready()
        self.godlike(g, temper=2.5)
        buf = io.StringIO()
        ui.io.script = ["1", "n"]
        with contextlib.redirect_stdout(buf):
            quench.menu(g)
        text = " ".join(buf.getvalue().split())
        self.assertIn("about 32% of your quenched weapon's strength", text)

    def test_an_untempered_worn_weapon_gets_no_extra_loaner_warning(self):
        g = self.ready()
        self.godlike(g)
        buf = io.StringIO()
        ui.io.script = ["1", "n"]
        with contextlib.redirect_stdout(buf):
            quench.menu(g)
        self.assertNotIn("of your quenched weapon", buf.getvalue())

    # -- the reveal
    def test_reveal_does_not_say_quenched_twice(self):
        g = self.ready()
        iid = self.godlike(g)
        quench.start(g, iid)
        self.finish(g)
        g.rng = Rig(0.999)
        out = capture(forge_ui.reveal_temper, forge.collect(g, 0))
        self.assertNotIn("is Long-Quenched", out)
        self.assertEqual(out.count("Long-Quenched"), 1)

    # -- the Court's receipt can always be found
    def test_pell_has_news_and_an_objective_after_the_talk_is_over(self):
        g = self.game()
        g.flags.update(queen_dead=True, pell_met=True, pell_after=True)
        self.assertTrue(npcs.has_news(g, "pell"))              # (even with no receipts: she is worth asking)
        self.assertEqual([o for o in navigation.objectives(g) if "Court Gate" in o["text"]], [])
        for r in late.RECEIPTS:
            if r != "late_receipt_court":
                give(g, r)
        self.assertEqual(len(late.receipts_held(g)), 5)
        objs = [o for o in navigation.objectives(g) if "Court Gate" in o["text"]]
        self.assertEqual(len(objs), 1)
        self.assertEqual((objs[0]["room"], objs[0]["side"]), ("court_gate", True))
        run_topic(g, "pell", "Ask for the Court's receipt")
        self.assertFalse(npcs.has_news(g, "pell"))
        self.assertEqual([o for o in navigation.objectives(g) if "Court Gate" in o["text"]], [])

    def test_pell_has_no_news_before_the_queen_dies(self):
        g = self.game()
        g.flags.update(pell_met=True, pell_after=True)
        self.assertFalse(npcs.has_news(g, "pell"))

    def test_orrin_still_names_no_place_for_the_courts_receipt(self):
        g = self.game()
        give(g, "late_receipt_court")
        out = run_topic(g, "orrin", "Show him the receipts")
        self.assertIn("last coal of the last dance", out)
        self.assertNotIn("danced", out)
        self.assertNotIn("Court", out)

    # -- what the smiths cannot know
    def test_tamsin_only_claims_brann_told_her_once_he_has(self):
        g = self.game()
        out = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertNotIn("Brann has told me", out)
        self.assertIn("Brann says there is a third quench", out)
        self.assertNotIn("Aldric's letter", out)
        self.assertIn("whatever Aldric left with Orrin", out)
        self.assertIn("0 of 6", out)
        g.flags["late_notes_shown"] = True
        out = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertIn("Brann has told me a little of it", out)

    def test_brann_does_not_repeat_corm_if_he_was_already_told(self):
        g = self.game()
        give(g, "lw_quench_notes")
        g.flags["lw_brann_told"] = True
        out = run_topic(g, "brann", "Show him Corm's notes")
        self.assertIn("That's his hand. My grandfather's.", out)
        g2 = self.game()
        give(g2, "lw_quench_notes")
        out = run_topic(g2, "brann", "Show him Corm's notes")
        self.assertIn("I know this hand", out)
        self.assertIn("Corm's", out)


class ToolTests(unittest.TestCase):
    def test_sim_smith_runs(self):
        import os
        import subprocess
        import sys
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        r = subprocess.run([sys.executable, os.path.join(root, "tools", "sim_smith.py"), "--n", "300"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("THE LONG QUENCH", r.stdout)
        self.assertIn("A GODLIKE FORGING", r.stdout)


if __name__ == "__main__":
    unittest.main()
