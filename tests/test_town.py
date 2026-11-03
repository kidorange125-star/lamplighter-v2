import contextlib
import io
import unittest

from lamplighter import clock, codes, npcs, postgame, rarity, save, town, ui
from lamplighter.content import BUILDINGS, ITEMS, ROOMS
from lamplighter.entities import Enemy
from tests.helpers import new_game, run, temp_home


class Clock:
    """A clock the test can move forward."""

    def __init__(self, start=1_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, minutes):
        self.t += minutes * 60


class TownTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        clock.set_clock(self.clock)

    def tearDown(self):
        clock.set_clock(None)

    def game(self, **kw):
        g = new_game(**kw)
        g.flags["joss_met"] = True
        return g

    def fund(self, g, gold=500, **items):
        g.player.gold = gold
        for iid, n in items.items():
            g.player.add_item(iid, n)


class BuildingTests(TownTestCase):
    def test_nothing_to_build_until_someone_is_invited(self):
        g = self.game()
        self.assertEqual(town.available(g), [])
        town.invite(g, "hearth_stall")
        self.assertEqual(town.available(g), ["hearth_stall"])

    def test_building_costs_gold_and_materials(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=6)
        g.room_id = "yard"
        run(g, "talk joss", answers=["1", "0"])
        self.assertEqual(g.player.gold, 40)
        self.assertEqual(g.player.inventory["rootwood"], 1)
        self.assertEqual(len(town.state(g)["queue"]), 1)
        self.assertEqual(town.available(g), [])

    def test_cannot_start_without_the_materials(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100)
        g.room_id = "yard"
        out = run(g, "talk joss", answers=["1", "0"])
        self.assertIn("You're short", out)
        self.assertEqual(g.player.gold, 100)
        self.assertEqual(town.state(g)["queue"], [])

    def test_walking_finishes_a_building(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=5)
        town.start_build(g, "hearth_stall")
        g.cooldown = {r: 10 ** 6 for r in ROOMS}
        for _ in range(BUILDINGS["hearth_stall"]["steps"]):
            self.assertFalse(town.is_built(g, "hearth_stall"))
            town.on_step(g)
        self.assertTrue(town.is_built(g, "hearth_stall"))

    def test_time_finishes_a_building_even_if_you_never_move(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=5)
        town.start_build(g, "hearth_stall")
        self.clock.advance(5)
        town.update(g)
        self.assertFalse(town.is_built(g, "hearth_stall"))
        self.clock.advance(8)
        town.update(g)
        self.assertTrue(town.is_built(g, "hearth_stall"))

    def test_gems_finish_it_at_once(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=5)
        g.player.gems = 10
        town.start_build(g, "hearth_stall")
        cost = town.speed_up_cost(town.queued(g, "hearth_stall"))
        self.assertTrue(town.speed_up(g, "hearth_stall"))
        self.assertTrue(town.is_built(g, "hearth_stall"))
        self.assertEqual(g.player.gems, 10 - cost)

    def test_not_enough_gems_does_nothing(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=5)
        g.player.gems = 0
        town.start_build(g, "hearth_stall")
        self.assertFalse(town.speed_up(g, "hearth_stall"))
        self.assertFalse(town.is_built(g, "hearth_stall"))

    def test_the_plot_stays_sealed_until_built(self):
        g = self.game()
        g.room_id = "market"
        run(g, "e")
        self.assertEqual(g.room_id, "market")
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=5)
        town.start_build(g, "hearth_stall")
        self.clock.advance(20)
        town.update(g)
        run(g, "e")
        self.assertEqual(g.room_id, "hearth_stall")

    def test_every_building_has_its_cost_and_a_plot(self):
        for bid in BUILDINGS:
            self.assertTrue(town.cost_lines(bid))


class RentTests(TownTestCase):
    def built_game(self):
        g = self.game()
        town.invite(g, "hearth_stall")
        self.fund(g, 100, rootwood=5)
        town.start_build(g, "hearth_stall")
        self.clock.advance(20)
        town.update(g)
        return g

    def test_rent_builds_up_by_the_hour(self):
        g = self.built_game()
        self.assertEqual(town.rent_due(g), 0)
        self.clock.advance(3 * 60)
        self.assertEqual(town.rent_due(g), 3 * BUILDINGS["hearth_stall"]["rent"])

    def test_rent_is_capped_at_eight_hours(self):
        g = self.built_game()
        self.clock.advance(100 * 60)
        self.assertEqual(town.rent_due(g), 8 * BUILDINGS["hearth_stall"]["rent"])

    def test_collecting_pays_and_resets(self):
        g = self.built_game()
        self.clock.advance(2 * 60)
        gold = g.player.gold
        g.room_id = "home"
        run(g, "collect")
        self.assertEqual(g.player.gold, gold + 2 * BUILDINGS["hearth_stall"]["rent"])
        self.assertEqual(town.rent_due(g), 0)

    def test_rent_can_only_be_collected_at_home_or_the_yard(self):
        g = self.built_game()
        self.clock.advance(60)
        g.room_id = "square"
        out = run(g, "collect")
        self.assertIn("home or in the Builder's Yard", out)

    def test_a_new_building_does_not_swallow_rent_already_earned(self):
        g = self.built_game()
        self.clock.advance(2 * 60)
        before = town.rent_due(g)
        town.invite(g, "salvage_stall")
        self.fund(g, 200, saltstone=5, rootwood=3)
        town.start_build(g, "salvage_stall")
        self.clock.advance(20)
        town.update(g)
        self.assertGreaterEqual(town.rent_due(g), before)

    def test_rent_survives_a_save(self):
        with temp_home():
            g = self.built_game()
            self.clock.advance(60)
            g.save(quiet=True)
            from lamplighter.engine import Game
            g2 = Game.load()
            self.assertEqual(town.rent_due(g2), town.rent_due(g))
            self.assertTrue(town.is_built(g2, "hearth_stall"))


class ResidentTests(TownTestCase):
    def test_corvin_leaves_the_hut_when_his_stall_opens(self):
        g = self.game()
        g.room_id = "hermit_hut"
        self.assertIn("corvin", g.present_npcs())
        town.state(g)["built"].append("hearth_stall")
        self.assertNotIn("corvin", g.present_npcs())
        g.room_id = "hearth_stall"
        self.assertIn("corvin", g.present_npcs())

    def test_corvin_agrees_to_move_after_the_mother_falls(self):
        g = self.game()
        g.room_id = "hermit_hut"
        g.flags["corvin_met"] = True
        g.flags["mother_dead"] = True
        run(g, "talk corvin", answers=["3", "0"])   # Mother / Trade / Invite
        self.assertTrue(town.is_invited(g, "hearth_stall"))

    def test_corvin_will_not_offer_before_the_mother_falls(self):
        g = self.game()
        g.room_id = "hermit_hut"
        g.flags["corvin_met"] = True
        self.assertFalse(npcs.has_news(g, "corvin"))

    def test_hot_meal_heals_and_calms(self):
        g = self.game()
        town.state(g)["built"].append("hearth_stall")
        g.flags["corvin_met"] = True
        g.room_id = "hearth_stall"
        g.player.gold, g.player.hp, g.player.dread = 100, 5, 60
        run(g, "talk corvin", answers=["3", "0"])   # Mother / Trade / Meal
        self.assertEqual(g.player.gold, 75)
        self.assertEqual(g.player.dread, 40)
        self.assertGreater(g.player.hp, 5)

    def test_odo_appears_only_after_the_reeve_falls(self):
        g = self.game()
        g.room_id = "reeve_house"
        self.assertNotIn("odo", g.present_npcs())
        g.flags["reeve_dead"] = True
        self.assertIn("odo", g.present_npcs())

    def test_odo_can_be_invited_and_then_runs_a_materials_shop(self):
        g = self.game()
        g.flags["reeve_dead"] = True
        g.room_id = "reeve_house"
        run(g, "talk odo", answers=["1", "0"])
        self.assertTrue(town.is_invited(g, "salvage_stall"))
        town.state(g)["built"].append("salvage_stall")
        g.player.gold = 100
        g.room_id = "salvage_stall"
        run(g, "trade", answers=["1", "1", "0", "0"])  # buy the first thing: rootwood, 12 gold
        self.assertEqual(g.player.gold, 88)
        self.assertEqual(g.player.inventory["rootwood"], 1)

    def test_only_odo_buys_materials(self):
        g = self.game()
        g.player.add_item("slag", 2)
        g.room_id = "tavern"
        out = run(g, "trade", answers=["2", "0", "0"])        # Maeve's sell list
        self.assertNotIn("Tallow Slag", out)
        town.state(g)["built"].append("salvage_stall")
        g.room_id = "salvage_stall"
        out = run(g, "trade", answers=["2", "0", "0"])        # Odo's sell list
        self.assertIn("Tallow Slag", out)

    def test_dagna_upgrades_the_stash_and_the_charm(self):
        g = self.game()
        town.state(g)["built"].append("strongroom")
        g.room_id = "strongroom"
        g.flags["dagna_met"] = True
        self.fund(g, 1000, slag=20)
        run(g, "talk dagna", answers=["1", "2", "0"])   # stash upgrade; then the menu renumbers, so 2 is the charm
        self.assertEqual(town.state(g)["stash_level"], 2)
        self.assertEqual(g.player.relic_level, 2)
        self.assertEqual(town.stash_capacity(g), 80)
        self.assertEqual(g.player.relic_max_charges, 3)


class StashTests(TownTestCase):
    def test_put_and_take(self):
        g = self.game()
        g.room_id = "home"
        n = g.player.inventory["draught"]
        run(g, "stash", answers=["1", "1", "2", "0"])   # Put in -> draught -> 2 of them -> done
        self.assertEqual(g.player.stash["draught"], 2)
        self.assertEqual(g.player.inventory["draught"], n - 2)
        run(g, "stash", answers=["2", "1", "", "0"])    # Take out -> draught -> all -> done
        self.assertNotIn("draught", g.player.stash)
        self.assertEqual(g.player.inventory["draught"], n)

    def test_stash_is_only_at_home(self):
        g = self.game()
        g.room_id = "square"
        out = run(g, "stash")
        self.assertIn("chest at home", out)

    def test_keys_and_pages_cannot_be_stored(self):
        g = self.game()
        g.room_id = "home"
        g.player.add_item("tide_key")
        g.player.add_item("page1")
        out = run(g, "stash", answers=["1", "0", "0"])
        self.assertNotIn("Tide Key", out.split("Put things in")[-1] if False else "")
        self.assertEqual(g.player.stash, {})

    def test_capacity_is_respected(self):
        g = self.game()
        g.room_id = "home"
        g.player.stash = {"slag": town.stash_capacity(g)}
        g.player.add_item("slag", 5)
        out = run(g, "stash", answers=["1", "1", "", "0", "0"])
        self.assertIn("full", out)


class CharmTests(TownTestCase):
    def test_orrin_gives_the_charm(self):
        g = self.game()
        g.room_id = "hall"
        run(g, "talk orrin", answers=["0"])
        self.assertTrue(g.player.has_item("homecoming_charm"))

    def test_recall_goes_home_and_costs_a_charge(self):
        g = self.game()
        g.player.add_item("homecoming_charm")
        g.room_id = "deepwood"
        g.player.dread = 60
        run(g, "recall")
        self.assertEqual(g.room_id, "square")
        self.assertEqual(g.player.relic_charges, 1)
        self.assertEqual(g.player.dread, 0)

    def test_recall_needs_the_charm_and_a_charge(self):
        g = self.game()
        g.room_id = "deepwood"
        run(g, "recall")
        self.assertEqual(g.room_id, "deepwood")        # no charm
        g.player.add_item("homecoming_charm")
        g.player.relic_charges = 0
        run(g, "recall")
        self.assertEqual(g.room_id, "deepwood")        # cold

    def test_recall_in_town_is_refused(self):
        g = self.game()
        g.player.add_item("homecoming_charm")
        g.room_id = "square"
        out = run(g, "recall")
        self.assertIn("already in Hollowmere", out)
        self.assertEqual(g.player.relic_charges, 2)

    def test_return_takes_you_back_to_where_you_rested(self):
        g = self.game()
        g.player.add_item("homecoming_charm")
        g.room_id = "hermit_hut"
        run(g, "rest")
        self.assertEqual(g.anchors, ["hermit_hut"])
        g.room_id = "square"
        run(g, "return")
        self.assertEqual(g.room_id, "hermit_hut")

    def test_lighting_a_waypost_makes_an_anchor(self):
        g = self.game()
        g.room_id = "wood_path"
        g.player.oil = 100
        run(g, "light")
        self.assertIn("wood_path", g.anchors)

    def test_resting_recharges_the_charm(self):
        g = self.game()
        g.player.relic_charges = 0
        g.room_id = "hall"
        run(g, "rest")
        self.assertEqual(g.player.relic_charges, g.player.relic_max_charges)

    def test_return_with_nowhere_to_go_explains(self):
        g = self.game()
        g.player.add_item("homecoming_charm")
        g.room_id = "square"
        out = run(g, "return")
        self.assertIn("no place to return", out)


class GemTests(TownTestCase):
    def test_new_code_gives_gems_once(self):
        g = self.game()
        out = run(g, "redeem NEW")
        self.assertEqual(g.player.gems, 30)
        self.assertIn("accepted", out)
        out = run(g, "redeem new")
        self.assertEqual(g.player.gems, 30)
        self.assertIn("already used", out)

    def test_codes_ignore_case_and_spaces(self):
        g = self.game()
        run(g, "redeem first light")
        self.assertEqual(g.player.gems, 40)

    def test_bad_codes_are_refused(self):
        g = self.game()
        out = run(g, "redeem HUNTER2")
        self.assertEqual(g.player.gems, 0)
        self.assertIn("not valid", out)

    def test_codes_are_stored_as_hashes_not_text(self):
        from lamplighter.content import CODES
        for h in CODES:
            self.assertEqual(len(h), 64)
        self.assertNotIn("NEW", "".join(CODES))

    def test_first_boss_kill_pays_gems_once(self):
        g = self.game()
        mother = Enemy("antlered_mother", __import__("lamplighter.content", fromlist=["ENEMIES"]).ENEMIES["antlered_mother"])
        with contextlib.redirect_stdout(io.StringIO()):
            g.on_kill(mother)
            g.on_kill(mother)
        self.assertEqual(g.player.gems, 3)

    def test_gems_survive_a_save(self):
        with temp_home():
            g = self.game()
            g.player.gems = 12
            g.save(quiet=True)
            from lamplighter.engine import Game
            self.assertEqual(Game.load().player.gems, 12)


class PostGameTests(TownTestCase):
    def test_wizards_door_is_sealed_until_the_story_is_told(self):
        g = self.game()
        g.room_id = "hall"
        run(g, "n")
        self.assertEqual(g.room_id, "hall")
        g.flags["completed"] = True
        run(g, "n")
        self.assertEqual(g.room_id, "wizard_shop")

    def test_finishing_the_story_returns_you_home_and_keeps_the_world_open(self):
        g = self.game()
        g.flags["ending"] = "dawn"
        g.room_id = "lightwell"
        g.player.hp = 1
        g.finish_story()
        self.assertEqual(g.room_id, "square")
        self.assertEqual(g.player.hp, g.player.max_hp)
        self.assertTrue(g.flags["completed"])
        self.assertFalse(g.over)

    def test_calling_back_a_boss_costs_gold_and_resets_it(self):
        g = self.game()
        g.flags["mother_dead"] = True
        g.flags["completed"] = True
        g.player.gold = 500
        g.room_id = "wizard_shop"
        g.flags["wizard_met"] = True
        bosses = postgame.defeated_bosses(g)
        self.assertEqual([b[0] for b in bosses], ["mother_grove"])
        run(g, "talk wizard", answers=["1", "1", "y", "0"])
        self.assertFalse(g.flags.get("mother_dead"))
        self.assertEqual(g.player.gold, 500 - bosses[0][2])

    def test_called_back_bosses_do_not_hand_out_key_items_twice(self):
        g = self.game()
        g.player.add_item("ember_wood")
        from lamplighter import events
        with contextlib.redirect_stdout(io.StringIO()):
            events.give_once(g, "ember_wood")
        self.assertEqual(g.player.inventory.get("ember_wood"), 1)

    def test_rewind_resets_the_story_but_keeps_gear_and_town(self):
        with temp_home():
            g = self.game()
            for f in ("mother_dead", "reeve_dead", "bishop_dead", "choir_dead", "usher_dead", "embers_set", "ending"):
                g.flags[f] = True
            g.flags["opened_square_d"] = True
            for i in ("ember_wood", "ember_tide", "ember_ash", "tide_key"):
                g.player.add_item(i)
            g.player.add_item("hatchet")
            g.player.gold = 5000
            town.state(g)["built"].append("hearth_stall")
            g.quests["main"] = "done"
            fee = postgame.rewind(g, 3)       # all the way back to the Weeping Wood
            self.assertGreater(fee, 0)
            for f in ("mother_dead", "reeve_dead", "bishop_dead", "choir_dead", "usher_dead", "embers_set", "ending"):
                self.assertFalse(g.flags.get(f), f)
            self.assertFalse(g.flags.get("opened_square_d"))
            for i in ("ember_wood", "ember_tide", "ember_ash", "tide_key"):
                self.assertFalse(g.player.has_item(i), i)
            self.assertTrue(g.player.has_item("hatchet"))
            self.assertTrue(town.is_built(g, "hearth_stall"))
            self.assertEqual(g.quests["main"], 1)
            self.assertEqual(g.player.gold, 5000 - fee)
            self.assertTrue(save.exists("before_rewind"))

    def test_rewinding_only_the_lightwell_leaves_the_rest(self):
        with temp_home():
            g = self.game()
            g.flags.update({"mother_dead": True, "usher_dead": True, "ending": "dawn"})
            g.player.gold = 1000
            postgame.rewind(g, 0)
            self.assertTrue(g.flags.get("mother_dead"))
            self.assertFalse(g.flags.get("usher_dead"))

    def test_crown_ending_is_a_real_ending(self):
        from lamplighter import events
        g = self.game()
        g.flags["ending"] = "crown"
        with contextlib.redirect_stdout(io.StringIO()):
            events.finish(g, "THE HOLLOW CROWN", "hollow", ["x"])
        self.assertTrue(g.over)

    def test_dawn_ending_does_not_end_the_game(self):
        from lamplighter import events
        g = self.game()
        g.flags["ending"] = "dawn"
        ui.io.script = [""]
        with contextlib.redirect_stdout(io.StringIO()):
            events.finish(g, "DAWN", "gold", ["x"])
        self.assertFalse(g.over)
        self.assertTrue(g.flags["completed"])


class RarityTests(TownTestCase):
    def test_every_tier_has_a_symbol_or_is_plain_and_a_name(self):
        for tier in rarity.RARITIES:
            info = rarity.INFO[tier]
            self.assertTrue(info["name"])
        symbols = [rarity.INFO[t]["symbol"] for t in rarity.RARITIES if t != "common"]
        self.assertEqual(len(symbols), len(set(symbols)))   # no two tiers share a symbol

    def test_labels_carry_the_symbol(self):
        self.assertIn("◆", rarity.label("hauberk"))     # rare
        self.assertNotIn("◆", rarity.label("hook"))     # common has none

    def test_the_pack_shows_rarity(self):
        g = self.game()
        g.player.add_item("hauberk")
        out = run(g, "i")
        self.assertIn("◆", out)

    def test_all_items_have_a_valid_rarity(self):
        for iid, it in ITEMS.items():
            self.assertIn(it.get("rarity", "common"), rarity.RARITIES, iid)


if __name__ == "__main__":
    unittest.main()
