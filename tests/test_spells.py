import contextlib
import io
import random
import unittest

from lamplighter import elements, gear, magic_ui, sim, spells, ui
from lamplighter.combat import Action, Combat
from lamplighter.content import ENEMIES, ITEMS, SPELL_RULES, SPELLS
from lamplighter.engine import Game
from tests.helpers import new_game, run, temp_home


class Rig(random.Random):
    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


def game(cls="ashblade", roll=0.0, level=5):
    g = new_game(cls)
    g.player = sim.build_player(cls=cls, level=level)
    g.rng = Rig(roll)
    return g


def fight(g, enemy="gloam_wolf"):
    ui.io.mute = True
    c = Combat(g, [enemy], policy=lambda cmb: Action("guard"), no_flee=True)
    ui.io.mute = False
    return c


def cast(c, book, target=None):
    ui.io.mute = True
    try:
        return c.exec_spell(book, target)
    finally:
        ui.io.mute = False


class SlotAndEquipTests(unittest.TestCase):
    def test_slots_grow_with_level(self):
        self.assertEqual([spells.slot_count(l) for l in (1, 2, 3, 4, 5, 7, 9, 11, 20)], [1, 1, 2, 2, 3, 4, 5, 6, 6])

    def test_equip_moves_the_book_out_of_the_pack(self):
        g = game(level=1)
        g.player.add_item("book_fire")
        ok, _ = spells.equip(g.player, "book_fire")
        self.assertTrue(ok)
        self.assertEqual(g.player.spells, ["book_fire"])
        self.assertFalse(g.player.has_item("book_fire"))

    def test_no_free_slot_no_duplicates(self):
        g = game(level=1)
        g.player.add_item("book_fire")
        g.player.add_item("book_ice")
        spells.equip(g.player, "book_fire")
        ok, msg = spells.equip(g.player, "book_ice")
        self.assertFalse(ok)
        self.assertIn("full", msg)
        g.player.level = 5
        g.player.add_item("book_fire")
        ok, msg = spells.equip(g.player, "book_fire")
        self.assertFalse(ok)
        self.assertIn("already", msg)

    def test_unequip_returns_it(self):
        g = game()
        g.player.add_item("book_fire")
        spells.equip(g.player, "book_fire")
        spells.unequip(g.player, 0)
        self.assertEqual(g.player.spells, [])
        self.assertEqual(g.player.inventory["book_fire"], 1)

    def test_equipped_spells_survive_a_save(self):
        with temp_home():
            g = game()
            inst = gear.make("book_ice", "epic", random.Random(1), affixes=[])
            gear.give(g.player, inst)
            g.player.inventory.pop(inst["id"])
            g.player.spells = [inst["id"]]
            g.save(quiet=True)
            ITEMS.pop(inst["id"])
            g2 = Game.load()
            self.assertEqual(g2.player.spells, [inst["id"]])
            self.assertEqual(spells.rarity_of(inst["id"]), "epic")

    def test_book_instances_read_like_items(self):
        inst = gear.make("book_fire", "legendary", random.Random(1), affixes=[])
        self.assertEqual(inst["kind"], "book")
        self.assertIn("Firebolt", inst["name"])
        self.assertIn("Power x", inst["desc"])
        inst["plus"] = 2
        gear.rebuild(inst)
        self.assertIn("+2", inst["name"])
        self.assertGreater(spells.power_mult(inst["id"]), SPELL_RULES["spell_power"]["legendary"])


class CraftTests(unittest.TestCase):
    def stock(self, g):
        g.player.gold = 1000
        g.player.add_item("essence_fire", 12)
        g.player.add_item("hollow_core", 3)

    def test_basic_craft_costs_and_yields_a_book(self):
        g = game(roll=0.0)
        self.stock(g)
        book = spells.craft(g, "fire", "basic")
        self.assertEqual(g.player.gold, 1000 - 40)
        self.assertEqual(g.player.inventory["essence_fire"], 12 - 3)
        self.assertEqual(spells.rarity_of(book), "common")        # roll 0.0 is the first, most common outcome

    def test_craft_rarity_follows_the_weights(self):
        g = game()
        self.stock(g)
        g.rng = Rig(0.99)
        book = spells.craft(g, "fire", "basic")
        self.assertEqual(spells.rarity_of(book), "rare")          # the last, rarest outcome of a basic binding

    def test_refined_craft_needs_a_core_and_never_yields_common(self):
        g = game(roll=0.0)
        self.stock(g)
        book = spells.craft(g, "fire", "refined")
        self.assertEqual(spells.rarity_of(book), "uncommon")
        self.assertEqual(g.player.inventory["hollow_core"], 2)

    def test_missing_ingredients_make_nothing(self):
        g = game()
        g.player.gold = 5
        self.assertIsNone(spells.craft(g, "fire", "basic"))
        self.assertIn("gold", " ".join(spells.craft_missing(g, "fire", "basic")))
        self.assertEqual(g.player.gold, 5)

    def test_every_craft_weight_table_sums_sensibly(self):
        for tier, c in SPELL_RULES["craft"].items():
            self.assertAlmostEqual(sum(c["weights"].values()), 1.0, places=2, msg=tier)


class CombineTests(unittest.TestCase):
    def two(self, g, ea, ra, eb, rb):
        a = spells.make_book(g, ea, ra)
        b = spells.make_book(g, eb, rb)
        return a, b

    def test_odds_always_sum_to_one(self):
        g = game()
        elems = elements.ELEMENTS
        for ea in elems:
            for eb in elems:
                for ra in ("common", "rare", "legendary"):
                    for rb in ("common", "epic", "legendary"):
                        a, b = self.two(g, ea, ra, eb, rb)
                        odds = spells.combine_outcomes(a, b)
                        self.assertAlmostEqual(sum(p for _, p in odds["outcomes"]), 1.0, places=2)

    def test_same_element_can_rise_stay_or_fall(self):
        g = game()
        a, b = self.two(g, "ice", "epic", "ice", "epic")
        odds = spells.combine_outcomes(a, b)
        self.assertEqual(odds["element"], "ice")
        self.assertFalse(odds["mixed"])
        self.assertEqual([r for r, _ in odds["outcomes"]], ["ultra", "epic", "rare"])

    def test_a_weaker_partner_lowers_the_chance_to_rise(self):
        g = game()
        a, b = self.two(g, "ice", "epic", "ice", "epic")
        c, d = self.two(g, "ice", "epic", "ice", "common")
        even = dict(spells.combine_outcomes(a, b)["outcomes"])["ultra"]
        lopsided = dict(spells.combine_outcomes(c, d)["outcomes"])["ultra"]
        self.assertLess(lopsided, even)

    def test_two_godlike_books_of_one_element_cannot_be_combined(self):
        g = game()
        a, b = self.two(g, "fire", "godlike", "fire", "godlike")
        self.assertIsNone(spells.combine_outcomes(a, b))

    def test_two_legendary_ice_books_can_make_a_godlike(self):
        g = game()
        a, b = self.two(g, "ice", "legendary", "ice", "legendary")
        self.assertIn("godlike", [r for r, _ in spells.combine_outcomes(a, b)["outcomes"]])

    def test_mixed_elements_make_a_third_usually_a_tier_lower(self):
        g = game()
        a, b = self.two(g, "fire", "legendary", "ice", "legendary")
        odds = spells.combine_outcomes(a, b)
        self.assertEqual(odds["element"], "water")
        self.assertTrue(odds["mixed"])
        top = max(odds["outcomes"], key=lambda t: t[1])
        self.assertEqual(top[0], "ultra")                         # the likeliest result is one tier down

    def test_every_pair_of_elements_has_a_result(self):
        for a in elements.ELEMENTS:
            for b in elements.ELEMENTS:
                if a != b:
                    self.assertIn(spells.combo_element(a, b), elements.ELEMENTS)
                    self.assertEqual(spells.combo_element(a, b), spells.combo_element(b, a))

    def test_combining_uses_both_books_and_makes_one(self):
        g = game(roll=0.0)
        a, b = self.two(g, "fire", "rare", "ice", "rare")
        res = spells.combine(g, a, b)
        self.assertEqual(res["element"], "water")
        self.assertFalse(g.player.has_item(a))
        self.assertFalse(g.player.has_item(b))
        self.assertTrue(g.player.has_item(res["book"]))

    def test_mixing_discovers_a_recipe_once(self):
        g = game(roll=0.0)
        a, b = self.two(g, "fire", "rare", "ice", "rare")
        first = spells.combine(g, a, b)
        self.assertTrue(first["new_recipe"])
        self.assertIn("fire+ice", spells.known_recipes(g))
        c, d = self.two(g, "ice", "rare", "fire", "rare")
        self.assertFalse(spells.combine(g, c, d)["new_recipe"])

    def test_two_common_books_of_one_kind_need_two_copies(self):
        g = game()
        g.player.add_item("book_fire")
        self.assertFalse(spells.can_combine(g, "book_fire", "book_fire"))
        g.player.add_item("book_fire")
        self.assertTrue(spells.can_combine(g, "book_fire", "book_fire"))

    def test_the_roll_picks_the_outcome(self):
        g = game(roll=0.0)
        a, b = self.two(g, "ice", "epic", "ice", "epic")
        self.assertEqual(spells.combine(g, a, b)["rarity"], "ultra")      # lowest roll = the best outcome
        g2 = game(roll=0.999)
        a, b = self.two(g2, "ice", "epic", "ice", "epic")
        self.assertEqual(spells.combine(g2, a, b)["rarity"], "rare")      # highest roll = the worst


class ApexTests(unittest.TestCase):
    def six(self, g):
        return [spells.make_book(g, e, "godlike") for e in elements.ELEMENTS]

    def test_locked_until_the_recipe_is_unlocked(self):
        g = game()
        books = self.six(g)
        self.assertFalse(spells.apex_ready(g, books))
        self.assertIsNone(spells.combine_apex(g, books))
        self.assertTrue(all(g.player.has_item(b) for b in books))

    def test_needs_one_godlike_book_of_every_element(self):
        g = game()
        g.flags["apex_unlocked"] = True
        books = self.six(g)
        self.assertTrue(spells.apex_ready(g, books))
        self.assertFalse(spells.apex_ready(g, books[:5]))
        bad = books[:5] + [spells.make_book(g, "fire", "godlike")]
        self.assertFalse(spells.apex_ready(g, bad))

    def test_a_low_roll_makes_the_apex(self):
        g = game(roll=0.0)
        g.flags["apex_unlocked"] = True
        books = self.six(g)
        res = spells.combine_apex(g, books)
        self.assertEqual(res["kind"], "apex")
        self.assertEqual(ITEMS[res["book"]]["spell"], "apex")
        self.assertFalse(any(g.player.has_item(b) for b in books))

    def test_a_failure_gives_a_buffed_legendary_or_a_downgraded_book(self):
        outcomes = set()
        for roll in (0.5, 0.95):
            g = game(roll=roll)
            g.flags["apex_unlocked"] = True
            res = spells.combine_apex(g, self.six(g))
            outcomes.add(res["kind"])
            self.assertEqual(spells.rarity_of(res["book"]), "legendary")
            if res["kind"] == "buffed":
                self.assertEqual(spells.plus_of(res["book"]), 1)
        self.assertEqual(outcomes, {"buffed", "downgraded"})

    def test_overall_apex_chance_is_about_ten_percent(self):
        g = game()
        g.flags["apex_unlocked"] = True
        g.rng = random.Random(42)
        wins = 0
        for _ in range(400):
            res = spells.combine_apex(g, self.six(g))
            wins += res["kind"] == "apex"
            for iid in list(g.player.gear):
                gear.discard(g.player, iid)
        self.assertAlmostEqual(wins / 400, SPELL_RULES["apex"]["chance"], delta=0.05)


class CastingTests(unittest.TestCase):
    def setup(self, element="fire", rarity="common", cls="ashblade", enemy="gloam_wolf"):
        g = game(cls=cls)
        g.player = sim.build_player(cls=cls, level=5, spells=[(element, rarity)])
        c = fight(g, enemy)
        c.p.focus = 10
        c.round = 1
        for e in c.enemies:
            e.choose_intent(c.rng, c.enemies)         # as a real fight would, before the first turn
        return g, c, c.p.spells[0]

    def test_a_spell_damages_and_costs_focus_and_starts_a_cooldown(self):
        g, c, book = self.setup("fire")
        e = c.enemies[0]
        hp = e.hp
        self.assertTrue(cast(c, book, e))
        self.assertLess(e.hp, hp)
        self.assertEqual(c.p.focus, 10 - SPELLS["fire"]["focus"])
        self.assertEqual(c.spell_cd[book], SPELLS["fire"]["cooldown"])

    def test_cooldown_blocks_a_second_cast_and_then_expires(self):
        g, c, book = self.setup("ice")
        e = c.enemies[0]
        cast(c, book, e)
        self.assertFalse(cast(c, book, e))
        self.assertFalse(c.spell_ready(book))
        c.spell_cd[book] = 1
        c.spell_cd[book] -= 1
        del c.spell_cd[book]
        c.p.focus = 10
        self.assertTrue(c.spell_ready(book))

    def test_not_enough_focus(self):
        g, c, book = self.setup("fire")
        c.p.focus = 1
        self.assertFalse(cast(c, book, c.enemies[0]))

    def test_weakness_hits_harder_and_resistance_softer(self):
        def damage(enemy):
            g, c, book = self.setup("fire", enemy=enemy)
            e = c.enemies[0]
            e.defense, e.dodge = 0, 0
            e.max_hp = e.hp = 10 ** 6
            e.weak, e.resist = ENEMIES[enemy].get("weak", []), ENEMIES[enemy].get("resist", [])
            before = e.hp
            cast(c, book, e)
            return before - e.hp, e
        base_e = "gloam_wolf"                                    # weak to fire
        weak_dmg, _ = damage(base_e)
        g, c, book = self.setup("fire")
        e = c.enemies[0]
        e.defense, e.dodge, e.max_hp, e.hp = 0, 0, 10 ** 6, 10 ** 6
        e.weak, e.resist = [], []
        cast(c, book, e)
        neutral = 10 ** 6 - e.hp
        g, c, book = self.setup("fire")
        e = c.enemies[0]
        e.defense, e.dodge, e.max_hp, e.hp = 0, 0, 10 ** 6, 10 ** 6
        e.weak, e.resist = [], ["fire"]
        cast(c, book, e)
        resisted = 10 ** 6 - e.hp
        self.assertAlmostEqual(weak_dmg / neutral, SPELL_RULES["weak_mult"], delta=0.15)
        self.assertAlmostEqual(resisted / neutral, SPELL_RULES["resist_mult"], delta=0.08)

    def test_higher_rarity_hits_harder(self):
        dmg = []
        for rarity in ("common", "rare", "legendary"):
            g, c, book = self.setup("ice", rarity)
            e = c.enemies[0]
            e.defense, e.dodge, e.weak, e.resist, e.max_hp, e.hp = 0, 0, [], [], 10 ** 6, 10 ** 6
            cast(c, book, e)
            dmg.append(10 ** 6 - e.hp)
        self.assertLess(dmg[0], dmg[1])
        self.assertLess(dmg[1], dmg[2])

    def test_fire_burns_ice_chills_light_blinds(self):
        for el, status in (("fire", "burn"), ("ice", "weak"), ("light", "blind")):
            g, c, book = self.setup(el)
            e = c.enemies[0]
            e.max_hp = e.hp = 10 ** 6
            cast(c, book, e)
            self.assertTrue(e.has(status), el)

    def test_shadow_drains_health_back(self):
        g, c, book = self.setup("shadow")
        c.p.hp = 5
        e = c.enemies[0]
        e.max_hp = e.hp = 10 ** 6
        cast(c, book, e)
        self.assertGreater(c.p.hp, 5)

    def test_earth_gives_a_shield_that_lasts(self):
        g, c, book = self.setup("earth")
        cast(c, book, c.enemies[0])
        self.assertGreater(c.p.shield, 0)
        self.assertTrue(c.p.has("ward"))
        c.p.tick_end()
        self.assertGreater(c.p.shield, 0)               # a ward keeps its shield past the turn

    def test_water_hits_everyone_and_cleanses(self):
        g, c, book = self.setup("water")
        ui.io.mute = True
        c2 = Combat(g, ["gloam_wolf", "gloam_wolf"], policy=lambda cmb: Action("guard"), no_flee=True)
        ui.io.mute = False
        c2.p.focus = 10
        c2.p.apply("burn", 3, 4)
        hp = [e.hp for e in c2.enemies]
        cast(c2, c2.p.spells[0])
        self.assertTrue(all(e.hp < h for e, h in zip(c2.enemies, hp)))
        self.assertFalse(c2.p.has("burn"))

    def test_the_apex_ignores_shields_weakness_and_hits_all(self):
        g = game()
        inst = gear.make("book_apex", "godlike", random.Random(1), affixes=[])
        gear.give(g.player, inst)
        g.player.inventory.pop(inst["id"])
        g.player.spells = [inst["id"]]
        ui.io.mute = True
        c = Combat(g, ["gloam_wolf", "rootwight"], policy=lambda cmb: Action("guard"), no_flee=True)
        ui.io.mute = False
        c.p.focus = 10
        hp = [e.hp for e in c.enemies]
        cast(c, inst["id"])
        self.assertTrue(all(e.hp < h for e, h in zip(c.enemies, hp)))

    def test_suggestion_casts_into_a_weakness(self):
        g, c, book = self.setup("fire", enemy="rootwight")           # a plant: weak to fire
        action, reason = c.suggest()
        self.assertEqual(action.kind, "spell")
        self.assertIn("weak to Fire", reason)

    def test_suggestion_does_not_cast_into_a_resistance(self):
        g, c, book = self.setup("earth", enemy="rootwight")          # resists earth
        action, _ = c.suggest()
        self.assertNotEqual(action.kind, "spell")

    def test_a_policy_fight_with_spells_runs(self):
        r = sim.win_rate(["rootwight"], sim.suggested, n=20, cls="ashblade", level=3, spells=[("fire", "rare")])
        self.assertGreater(r["win"], 0.9)


class CombatMenuSpellTests(unittest.TestCase):
    def play(self, keys, spells_=(("fire", "common"),), enemy="rootwight", level=5):
        g = new_game("ashblade")
        g.player = sim.build_player(cls="ashblade", level=level, spells=list(spells_))
        g.room_id = "wood_path"
        c = Combat(g, [enemy], no_flee=False)
        ui.io.script = ["#"] + list(keys)
        ui.io.since_clear = 1
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                outcome = c.run()
            except EOFError:
                outcome = "keys ran out"
        return outcome, out.getvalue(), g

    def test_the_menu_shows_the_spell_row_and_weaknesses(self):
        outcome, out, g = self.play(["s1"] + ["a"] * 10)
        self.assertIn("Spells", out)
        self.assertIn("[S1]", out)
        self.assertIn("weak to", out)

    def test_s1_casts_the_first_spell(self):
        outcome, out, g = self.play(["s1"] + ["a"] * 10)
        self.assertIn("You cast Firebolt!", out)

    def test_casting_by_name_works(self):
        outcome, out, g = self.play(["firebolt"] + ["a"] * 10)
        self.assertIn("You cast Firebolt!", out)

    def test_a_second_cast_is_refused_with_a_reason(self):
        outcome, out, g = self.play(["s1", "s1"] + ["a"] * 10, enemy="antlered_mother")
        self.assertTrue("recharging" in out or "Not enough focus" in out)

    def test_no_spells_no_row(self):
        outcome, out, g = self.play(["a"] * 10, spells_=())
        self.assertNotIn("[S1]", out)


class MagicianTests(unittest.TestCase):
    def test_first_visit_gives_a_class_book_already_equipped(self):
        for cls, el in (("ashblade", "fire"), ("warden", "earth"), ("wayfarer", "shadow")):
            g = new_game(cls)
            g.player = sim.build_player(cls=cls, level=1)
            g.room_id = "tower"
            run(g, "talk mirelle", answers=["0"])
            self.assertEqual(g.player.spells, ["book_" + el], cls)
            self.assertTrue(g.flags["mirelle_met"])

    def test_the_tower_is_west_of_the_chapel(self):
        g = new_game()
        g.room_id = "chapel"
        run(g, "w")
        self.assertEqual(g.room_id, "tower")

    def test_buying_a_common_book_with_gold(self):
        g = game()
        g.flags["mirelle_met"] = True
        g.room_id = "tower"
        g.player.gold = 500
        run(g, "talk mirelle", answers=["3", "1", "1", "0"])      # Buy / the gold option / Fire / leave
        self.assertEqual(g.player.gold, 500 - 120)
        self.assertEqual(g.player.inventory.get("book_fire"), 1)

    def test_buying_with_gems(self):
        g = game()
        g.flags["mirelle_met"] = True
        g.room_id = "tower"
        g.player.gems = 30
        run(g, "talk mirelle", answers=["3", "3", "2", "0"])      # Buy / a Rare book for 20 gems / Ice / leave
        self.assertEqual(g.player.gems, 10)
        rares = [i for i in g.player.inventory if ITEMS[i].get("kind") == "book" and ITEMS[i]["rarity"] == "rare"]
        self.assertEqual(len(rares), 1)

    def test_crafting_through_the_menu(self):
        g = game(roll=0.0)
        g.flags["mirelle_met"] = True
        g.room_id = "tower"
        g.player.gold = 500
        g.player.add_item("essence_fire", 3)
        run(g, "talk mirelle", answers=["2", "1", "1", "y", "", "0"])   # Craft / Fire / basic / yes / Enter / leave
        self.assertEqual(g.player.inventory.get("essence_fire", 0), 0)
        self.assertEqual(g.player.inventory.get("book_fire"), 1)

    def test_combining_shows_the_odds_first(self):
        g = game(roll=0.0)
        g.flags["mirelle_met"] = True
        g.room_id = "tower"
        a = spells.make_book(g, "ice", "epic")
        b = spells.make_book(g, "ice", "epic")
        pack = spells.books_in_pack(g.player)
        out = run(g, "talk mirelle",
                  answers=["4", str(pack.index(a) + 1), str(pack.index(b) + 1), "y", "", "0"])
        self.assertIn("%", out)
        self.assertIn("Ultra", out)
        self.assertFalse(g.player.has_item(a))
        self.assertFalse(g.player.has_item(b))

    def test_undiscovered_recipes_stay_hidden_until_tried(self):
        g = game(roll=0.0)
        g.flags["mirelle_met"] = True
        g.room_id = "tower"
        a = spells.make_book(g, "fire", "rare")
        b = spells.make_book(g, "ice", "rare")
        pack = spells.books_in_pack(g.player)
        out = run(g, "talk mirelle", answers=["4", str(pack.index(a) + 1), str(pack.index(b) + 1), "n", "0"])
        self.assertIn("???", out)
        self.assertNotIn("a Water book", out)

    def test_the_recipe_log_lists_what_you_know(self):
        g = game()
        g.flags["mirelle_met"] = True
        g.flags["recipes"] = ["fire+ice"]
        g.room_id = "tower"
        out = run(g, "talk mirelle", answers=["5", "", "0"])
        self.assertIn("Discovered 1 of 15", out)

    def test_the_spells_command_equips_books(self):
        g = game()
        g.player.add_item("book_ice")
        out = run(g, "spells", answers=["1", "1", "0"])
        self.assertEqual(g.player.spells, ["book_ice"])

    def test_every_essence_drop_references_a_real_item(self):
        for eid, e in ENEMIES.items():
            for iid, chance in e.get("drops", []):
                self.assertIn(iid, ITEMS, eid)


if __name__ == "__main__":
    unittest.main()
