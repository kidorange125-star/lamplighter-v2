"""Package arc (docs/M6-SPEC.md section 12): the Sixfold Chart unlock, the Grand Binding, apex heat.

The chart (`vg_sixfold_chart`) belongs to the Vigil package, so these tests put it in the pack by id and never need its
item definition: the unlock only asks whether the pack holds it.
"""
import contextlib
import io
import random
import unittest

from lamplighter import areas, elements, gear, magic_ui, npcs, sim, spells, town, ui, validate
from lamplighter.areas import arc
from lamplighter.content import ITEMS, SPELL_RULES
from tests.helpers import new_game


class Rig(random.Random):
    """Every random() call returns one fixed value (the other methods keep working)."""
    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


def game(roll=0.5, cls="wayfarer", level=12):
    g = new_game(cls)
    g.player = sim.build_player(cls=cls, level=level)
    g.rng = Rig(roll)
    return g


def ready(g):
    """Everything the unlock asks for: the chart in the pack, Hale has read it, his almanac is built."""
    g.player.inventory[arc.CHART] = 1
    g.flags[arc.READ_FLAG] = True
    town.state(g)["built"].append(arc.ALMANAC)


def stock_grand(g, element="fire", hearts=1, gold=5000):
    p = g.player
    p.gold = gold
    p.inventory["essence_" + element] = 20
    p.inventory["hollow_core"] = 10
    p.inventory[spells.heart_id(element)] = hearts


def six(g):
    return [spells.make_book(g, e, "godlike") for e in elements.ELEMENTS]


def drive(fn, *args, answers=()):
    """Call fn with scripted answers, returning (result, everything printed)."""
    ui.io.script = list(answers)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            res = fn(*args)
    finally:
        ui.io.script = []
    return res, out.getvalue()


class UnlockConditionTests(unittest.TestCase):
    def test_ready_when_all_three_hold(self):
        g = game()
        ready(g)
        self.assertTrue(arc.unlock_ready(g))
        self.assertEqual(arc.unlock_missing(g), [])

    def test_each_missing_piece_blocks_it(self):
        cases = {
            "the Sixfold Chart": lambda g: g.player.inventory.pop(arc.CHART),
            "Hale to read it": lambda g: g.flags.pop(arc.READ_FLAG),
            "Hale's almanac built": lambda g: town.state(g)["built"].remove(arc.ALMANAC),
        }
        for phrase, undo in cases.items():
            g = game()
            ready(g)
            undo(g)
            self.assertFalse(arc.unlock_ready(g), phrase)
            self.assertEqual(arc.unlock_missing(g), [phrase])
            out = drive(magic_ui.menu, g, answers=["0"])[1]
            self.assertNotIn("Sixfold", out, phrase)

    def test_nothing_ready_on_a_fresh_game(self):
        g = game()
        self.assertEqual(len(arc.unlock_missing(g)), 3)
        self.assertEqual(arc.unlock_scene(g), "")
        self.assertFalse(g.flags.get("apex_unlocked"))

    def test_already_unlocked_hides_the_option(self):
        g = game()
        ready(g)
        g.flags["apex_unlocked"] = True
        self.assertFalse(arc.unlock_ready(g))
        self.assertNotIn("Sixfold", drive(magic_ui.menu, g, answers=["0"])[1])


class UnlockSceneTests(unittest.TestCase):
    def test_the_menu_offers_the_chart_first_and_the_scene_unlocks(self):
        g = game()
        ready(g)
        out = drive(magic_ui.menu, g, answers=["0"])[1]
        self.assertIn("Show her the Sixfold Chart", out)
        self.assertIn("[1] ", out.split("Show her the Sixfold Chart")[0].splitlines()[-1])
        _, out = drive(magic_ui.menu, g, answers=["1", "", "0"])
        self.assertTrue(g.flags["apex_unlocked"])
        self.assertIn("Six wheels, six lights", out)
        self.assertIn("Hale", out)
        self.assertIn("sing at once", out)

    def test_the_option_is_gone_afterwards_and_the_chart_stays(self):
        g = game()
        ready(g)
        drive(magic_ui.menu, g, answers=["1", "", "0"])
        out = drive(magic_ui.menu, g, answers=["0"])[1]
        self.assertNotIn("Sixfold", out)
        self.assertTrue(g.player.has_item(arc.CHART))

    def test_the_scene_is_idempotent(self):
        g = game()
        ready(g)
        first = drive(arc.unlock_scene, g, answers=[""])[0]
        self.assertTrue(first)
        again, out = drive(arc.unlock_scene, g)
        self.assertEqual(again, "")
        self.assertEqual(out, "")
        self.assertTrue(g.flags["apex_unlocked"])
        self.assertEqual(g.player.inventory[arc.CHART], 1)

    def test_unlocking_makes_the_apex_attemptable(self):
        g = game()
        ready(g)
        books = six(g)
        self.assertFalse(spells.apex_ready(g, books))
        drive(arc.unlock_scene, g, answers=[""])
        self.assertTrue(spells.apex_ready(g, books))

    def test_mirelle_has_news_exactly_while_the_unlock_waits(self):
        g = game()
        g.flags["mirelle_met"] = True
        self.assertFalse(npcs.has_news(g, "mirelle"))
        ready(g)
        self.assertTrue(npcs.has_news(g, "mirelle"))
        drive(arc.unlock_scene, g, answers=[""])
        self.assertFalse(npcs.has_news(g, "mirelle"))

    def test_the_old_cannot_do_it_yet_lines_point_to_the_vigil(self):
        g = game()
        six(g)
        out = drive(magic_ui._combine, g, answers=["2", "0"])[1]
        self.assertIn("ask in the Vigil", out)
        self.assertNotIn("cannot do it yet", out)
        self.assertIn("ask in the Vigil", drive(magic_ui._combine, g, answers=["2"])[1])
        help_text = drive(magic_ui._help, g, answers=[""])[1]
        self.assertIn("ask in the Vigil", help_text)
        self.assertNotIn("beyond her art", help_text)

    def test_the_hint_follows_the_chain_not_just_the_vigil(self):
        # chart held, Hale has not read it, almanac not built: whoever reads the stars, no Vigil, no loft
        g = game()
        six(g)
        g.player.inventory[arc.CHART] = 1
        out = drive(magic_ui._combine, g, answers=["2", "0"])[1]
        self.assertNotIn("ask in the Vigil", out)
        self.assertIn("whoever reads the stars", out)
        self.assertNotIn("loft", out)
        # almanac built: she names the loft beside the tower
        town.state(g)["built"].append(arc.ALMANAC)
        out = drive(magic_ui._combine, g, answers=["2", "0"])[1]
        self.assertNotIn("ask in the Vigil", out)
        self.assertIn("Hale is in the loft next door", out)
        # Hale has read it but has no almanac yet: find him a roof
        g = game()
        six(g)
        g.player.inventory[arc.CHART] = 1
        g.flags[arc.READ_FLAG] = True
        out = drive(magic_ui._combine, g, answers=["2", "0"])[1]
        self.assertNotIn("ask in the Vigil", out)
        self.assertIn("roof in Hollowmere", out)

    def test_a_ready_unlock_points_at_the_chart_and_runs_it(self):
        g = game()
        ready(g)
        six(g)
        menu = drive(magic_ui._combine, g, answers=[""])[1]
        self.assertIn("Sixfold Chart", menu)
        self.assertNotIn("ask in the Vigil", menu)
        res, out = drive(magic_ui._combine, g, answers=["2", ""])
        self.assertTrue(g.flags["apex_unlocked"])
        self.assertIn("Six wheels, six lights", out)
        self.assertNotIn("ask in the Vigil", out)
        self.assertIn("The chart stays in your pack", res)
        self.assertNotIn("copy", res)
        self.assertTrue(g.player.has_item(arc.CHART))

    def test_the_help_text_changes_once_the_apex_is_unlocked(self):
        g = game()
        ready(g)
        drive(arc.unlock_scene, g, answers=[""])
        help_text = drive(magic_ui._help, g, answers=[""])[1]
        self.assertNotIn("ask in the Vigil", help_text)
        self.assertIn("Mirelle has the order now", help_text)
        self.assertIn("starts at 10%", help_text)
        self.assertIn("10 points", help_text)


class GrandBindingTests(unittest.TestCase):
    def test_the_rule_is_in_the_data(self):
        c = SPELL_RULES["craft"]["grand"]
        self.assertEqual((c["gold"], c["essence"], c["cores"], c["heart"]), (500, 5, 2, 1))
        self.assertEqual(c["weights"], {"ultra": 0.40, "legendary": 0.45, "godlike": 0.15})

    def test_a_missing_heart_blocks_the_binding_and_costs_nothing(self):
        g = game()
        stock_grand(g, hearts=0)
        self.assertEqual(spells.craft_missing(g, "fire", "grand"), ["1 more Heart of Fire"])
        self.assertIsNone(spells.craft(g, "fire", "grand"))
        self.assertEqual(g.player.gold, 5000)
        self.assertEqual(g.player.inventory["essence_fire"], 20)
        self.assertEqual(g.player.inventory["hollow_core"], 10)

    def test_a_heart_of_the_wrong_element_does_not_count(self):
        g = game()
        stock_grand(g, "fire", hearts=0)
        g.player.inventory[spells.heart_id("ice")] = 3
        self.assertIn("1 more Heart of Fire", spells.craft_missing(g, "fire", "grand"))
        self.assertIsNone(spells.craft(g, "fire", "grand"))
        self.assertEqual(g.player.inventory[spells.heart_id("ice")], 3)

    def test_the_other_costs_are_still_asked_for(self):
        g = game()
        stock_grand(g, gold=100)
        g.player.inventory["essence_fire"] = 2
        g.player.inventory["hollow_core"] = 0
        lack = " ".join(spells.craft_missing(g, "fire", "grand"))
        for need in ("400 more gold", "3 more Fire Essence", "2 more Hollow Core"):
            self.assertIn(need, lack)
        self.assertNotIn("Heart", lack)

    def test_crafting_consumes_exactly_one_heart_of_that_element(self):
        for element in elements.ELEMENTS:
            g = game(roll=0.0)
            stock_grand(g, element, hearts=2)
            g.player.inventory[spells.heart_id("fire" if element != "fire" else "ice")] = 1
            book = spells.craft(g, element, "grand")
            self.assertEqual(spells.element_of(book), element)
            self.assertEqual(g.player.gold, 4500)
            self.assertEqual(g.player.inventory["essence_" + element], 15)
            self.assertEqual(g.player.inventory["hollow_core"], 8)
            self.assertEqual(g.player.inventory[spells.heart_id(element)], 1)
            self.assertEqual(g.player.inventory[spells.heart_id("fire" if element != "fire" else "ice")], 1)

    def test_the_ordinary_bindings_do_not_touch_hearts(self):
        g = game(roll=0.0)
        stock_grand(g, hearts=1)
        spells.craft(g, "fire", "refined")
        self.assertEqual(g.player.inventory[spells.heart_id("fire")], 1)
        self.assertEqual(spells.craft_missing(g, "fire", "basic"), [])

    def test_the_roll_picks_the_rarity_from_the_ends(self):
        for roll, expect in ((0.0, "ultra"), (0.5, "legendary"), (0.99, "godlike")):
            g = game(roll=roll)
            stock_grand(g)
            self.assertEqual(spells.rarity_of(spells.craft(g, "fire", "grand")), expect, roll)

    def test_rarity_distribution_over_5000_seeded_draws(self):
        g = game()
        g.rng = random.Random(2026)
        counts = {"ultra": 0, "legendary": 0, "godlike": 0}
        n = 5000
        for _ in range(n):
            stock_grand(g)
            book = spells.craft(g, "fire", "grand")
            counts[spells.rarity_of(book)] += 1
            gear.discard(g.player, book)
        self.assertEqual(sum(counts.values()), n)
        for rarity, want in (("ultra", 0.40), ("legendary", 0.45), ("godlike", 0.15)):
            self.assertAlmostEqual(counts[rarity] / n, want, delta=0.03, msg=rarity)

    def test_the_menu_shows_the_odds_first_and_names_the_heart(self):
        label = magic_ui._craft_label("grand", "fire")
        self.assertTrue(label.startswith("Grand Binding: Godlike 15%, Legendary 45%, Ultra 40%."), label)
        self.assertIn("Heart of Fire", label)
        self.assertIn("500 gold, 5 Fire Essence, 2 Hollow Core", label)
        # the older bindings keep their own wording
        self.assertTrue(magic_ui._craft_label("basic", "fire").startswith("Basic: 40 gold, 3 Fire Essence."))

    def test_binding_through_the_menu(self):
        g = game(roll=0.99)
        stock_grand(g, hearts=1)
        tiers = list(SPELL_RULES["craft"])
        self.assertEqual(tiers[-1], "grand")
        note, out = drive(magic_ui._craft, g, answers=["1", str(len(tiers)), "y", ""])
        self.assertIn("Grand Binding", out)
        self.assertIn("Heart of Fire", out)
        self.assertIn("Firebolt", note)
        book = [b for b in g.player.inventory if spells.is_book(b)][0]
        self.assertEqual(spells.rarity_of(book), "godlike")       # the roll was rigged to the best outcome
        self.assertEqual(g.player.inventory.get(spells.heart_id("fire"), 0), 0)

    def test_the_menu_says_what_is_missing_without_a_heart(self):
        g = game()
        stock_grand(g, hearts=0)
        note, _ = drive(magic_ui._craft, g, answers=["1", "3"])
        self.assertIn("Heart of Fire", note)
        self.assertEqual(g.player.gold, 5000)


class ApexHeatTests(unittest.TestCase):
    def setUp(self):
        self.g = game(roll=0.95)
        self.g.flags["apex_unlocked"] = True

    def test_the_numbers(self):
        self.assertEqual(SPELL_RULES["apex"]["heat"], 0.10)
        self.assertEqual(spells.apex_heat(self.g), 0)
        self.assertAlmostEqual(spells.apex_chance(self.g), 0.10)

    def test_each_failure_adds_ten_points(self):
        g = self.g
        for n in range(1, 4):
            res = spells.attempt_apex(g, six(g))
            self.assertNotEqual(res["kind"], "apex")
            self.assertEqual(spells.apex_heat(g), n)
            self.assertAlmostEqual(spells.apex_chance(g), 0.10 + 0.10 * n)
            self.assertEqual(g.flags["arc_apex_heat"], n)

    def test_the_rolled_chance_is_reported(self):
        g = self.g
        self.assertAlmostEqual(spells.attempt_apex(g, six(g))["chance"], 0.10)
        self.assertAlmostEqual(spells.attempt_apex(g, six(g))["chance"], 0.20)

    def test_it_is_a_sure_thing_after_nine_failures_and_then_resets(self):
        g = self.g                                   # 0.95 never beats a chance below 1.0
        for _ in range(9):
            self.assertNotEqual(spells.attempt_apex(g, six(g))["kind"], "apex")
        self.assertEqual(spells.apex_heat(g), 9)
        self.assertEqual(spells.apex_chance(g), 1.0)
        res = spells.attempt_apex(g, six(g))
        self.assertEqual(res["kind"], "apex")
        self.assertEqual(spells.apex_heat(g), 0)
        self.assertAlmostEqual(spells.apex_chance(g), 0.10)

    def test_the_chance_never_exceeds_one(self):
        self.g.flags["arc_apex_heat"] = 50
        self.assertEqual(spells.apex_chance(self.g), 1.0)

    def test_heat_survives_a_save(self):
        g = self.g
        spells.attempt_apex(g, six(g))
        spells.attempt_apex(g, six(g))
        from lamplighter.engine import Game
        g2 = Game.from_dict(g.to_dict())
        self.assertEqual(spells.apex_heat(g2), 2)
        self.assertAlmostEqual(spells.apex_chance(g2), 0.30)

    def test_a_refused_attempt_adds_no_heat(self):
        g = game(roll=0.95)                           # not unlocked
        self.assertIsNone(spells.attempt_apex(g, six(g)))
        self.assertEqual(spells.apex_heat(g), 0)
        g.flags["apex_unlocked"] = True
        self.assertIsNone(spells.attempt_apex(g, six(g)[:5]))
        self.assertEqual(spells.apex_heat(g), 0)

    def test_the_failure_refund_is_unchanged(self):
        kinds = set()
        for roll in (0.5, 0.95):                      # heat 0: chance 10%, so both fail
            g = game(roll=roll)
            g.flags["apex_unlocked"] = True
            res = spells.attempt_apex(g, six(g))
            kinds.add(res["kind"])
            self.assertEqual(spells.rarity_of(res["book"]), "legendary")
        self.assertEqual(kinds, {"buffed", "downgraded"})

    def test_plain_combine_apex_keeps_the_base_chance(self):
        g = game(roll=0.15)
        g.flags["apex_unlocked"] = True
        g.flags["arc_apex_heat"] = 5                  # heat only counts through attempt_apex
        self.assertNotEqual(spells.combine_apex(g, six(g))["kind"], "apex")
        g2 = game(roll=0.15)
        g2.flags["apex_unlocked"] = True
        g2.flags["arc_apex_heat"] = 5
        self.assertEqual(spells.attempt_apex(g2, six(g2))["kind"], "apex")

    def test_the_menu_shows_base_plus_heat(self):
        g = self.g
        books = six(g)
        out = drive(magic_ui._apex, g, books, answers=["n"])[1]
        self.assertIn("Chance of success: 10%", out)
        self.assertNotIn("heat =", out)
        g.flags["arc_apex_heat"] = 2
        out = drive(magic_ui._apex, g, books, answers=["n"])[1]
        self.assertIn("10% + 20% heat = 30%", out)
        self.assertTrue(all(g.player.has_item(b) for b in books))      # declined: nothing spent

    def test_attempting_through_the_menu_warms_the_apex(self):
        g = self.g
        note, _ = drive(magic_ui._apex, g, six(g), answers=["y", ""])
        self.assertEqual(spells.apex_heat(g), 1)
        self.assertTrue(note)
        g.rng = Rig(0.0)
        note, _ = drive(magic_ui._apex, g, six(g), answers=["y", ""])
        self.assertIn("apex spell", note)
        self.assertEqual(spells.apex_heat(g), 0)


class DataChecks(unittest.TestCase):
    def test_arc_check_is_clean(self):
        self.assertEqual(arc.CHECK(), [])
        self.assertEqual([e for e in areas.check() if e.startswith("arc:")], [])

    def test_every_heart_exists_and_names_its_use(self):
        for e in elements.ELEMENTS:
            self.assertIn(spells.heart_id(e), ITEMS)

    def test_the_validator_has_nothing_to_say_about_the_spell_data(self):
        mine = [e for e in validate.validate()
                if any(w in e.lower() for w in ("spell", "grand", "heart", "apex", "arc."))]
        self.assertEqual(mine, [])

    def test_arc_registers_only_its_own_hooks(self):
        self.assertEqual(set(arc.EXTRA_NEWS), {"mirelle"})
        for attr in ("ENTER", "NPCS", "TOPICS", "AFTER_BEACON", "SELLS"):
            self.assertFalse(hasattr(arc, attr), attr)


if __name__ == "__main__":
    unittest.main()
