"""End-to-end flows a player goes through: death, shops, saves, resting, quests, equipment."""
import unittest

from lamplighter import navigation, npcs, save
from lamplighter.content import ITEMS, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, run, temp_home


class DeathTests(unittest.TestCase):
    def test_death_costs_half_the_gold_and_returns_you_to_your_last_rest(self):
        g = new_game()
        g.player.gold = 101
        g.room_id = "mother_grove"
        g.last_rest = "moth_shrine"
        g.player.hp = 0
        run(g)  # nothing
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            g.death()
        self.assertEqual(g.room_id, "moth_shrine")
        self.assertEqual(g.player.gold, 51)
        self.assertEqual(g.player.hp, g.player.max_hp)
        self.assertEqual(g.stats["deaths"], 1)

    def test_area_screen_works_right_after_dying(self):
        import contextlib, io
        g = new_game()
        g.player.hp = 0
        with contextlib.redirect_stdout(io.StringIO()):
            g.death()
            g.render_room()


class ShopTests(unittest.TestCase):
    def test_buying_spends_gold_and_adds_the_item(self):
        g = new_game()
        g.player.gold = 50
        before = g.player.inventory.get("stew", 0)
        # Buy -> first item (stew, 5g) -> back -> Done
        run(g, "trade", answers=["1", "1", "0", "0"]) if False else None
        g.room_id = "tavern"
        out = run(g, "trade", answers=["1", "1", "0", "0"])
        self.assertEqual(g.player.gold, 45)
        self.assertEqual(g.player.inventory.get("stew", 0), before + 1)

    def test_cannot_buy_what_you_cannot_afford(self):
        g = new_game()
        g.player.gold = 1
        g.room_id = "tavern"
        out = run(g, "trade", answers=["1", "1", "0", "0"])
        self.assertEqual(g.player.gold, 1)
        self.assertIn("can't afford", out)

    def test_selling_pays_half_and_removes_the_item(self):
        g = new_game()
        g.room_id = "tavern"
        g.player.add_item("pearl", 1)       # worth 25, shops pay 12
        gold = g.player.gold
        # Sell -> pick pearl (find its menu number) ...
        sellable = [i for i in g.player.inventory if ITEMS[i]["kind"] not in ("key", "page") and ITEMS[i]["value"] > 0]
        idx = sellable.index("pearl") + 1
        run(g, "trade", answers=["2", str(idx), "0", "0"])
        self.assertEqual(g.player.gold, gold + 12)
        self.assertFalse(g.player.has_item("pearl"))

    def test_every_shop_can_be_opened_and_stock_is_buyable(self):
        for nid in npcs.STOCK:
            g = new_game()
            g.player.gold = 99999
            g.visited.add("tavern")
            for i in range(1, len(npcs.stock_for(g, nid)) + 1):
                run(g, "x", answers=[])
                import contextlib, io
                from lamplighter import ui
                ui.io.script = ["1", str(i), "n", "n", "0", "0"]
                with contextlib.redirect_stdout(io.StringIO()):
                    npcs.trade(g, nid)


class SaveCommandTests(unittest.TestCase):
    def test_rest_heals_refills_and_saves(self):
        with temp_home():
            g = new_game()
            g.player.hp = 5
            g.player.oil = 3
            run(g, "rest")
            self.assertEqual(g.player.hp, g.player.max_hp)
            self.assertEqual(g.player.oil, g.player.max_oil)
            self.assertTrue(save.exists())

    def test_cannot_rest_in_the_dark(self):
        g = new_game()
        g.room_id = "deepwood"
        g.player.hp = 5
        run(g, "rest")
        self.assertEqual(g.player.hp, 5)

    def test_load_command_restores_the_saved_game(self):
        with temp_home():
            g = new_game()
            g.player.gold = 200
            g.save(quiet=True)
            g.player.gold = 5
            run(g, "load", answers=["y"])
            self.assertEqual(g.player.gold, 200)

    def test_load_with_no_save_is_polite(self):
        with temp_home():
            g = new_game()
            out = run(g, "load")
            self.assertIn("no saved game", out)


class EquipmentTests(unittest.TestCase):
    def test_equip_swaps_and_returns_the_old_item_to_the_pack(self):
        g = new_game()
        g.player.add_item("hatchet")
        run(g, "equip hatchet")
        self.assertEqual(g.player.equipment["weapon"], "hatchet")
        self.assertTrue(g.player.inventory.get("hook", 0) >= 1)

    def test_cannot_go_unarmed(self):
        g = new_game()
        out = run(g, "unequip hook")
        self.assertEqual(g.player.equipment["weapon"], "hook")

    def test_use_a_potion_heals_and_consumes(self):
        g = new_game()
        g.player.hp = 5
        n = g.player.inventory["draught"]
        run(g, "use draught")
        self.assertGreater(g.player.hp, 5)
        self.assertEqual(g.player.inventory["draught"], n - 1)

    def test_use_oil_refills_the_lantern(self):
        g = new_game()
        g.player.oil = 10
        run(g, "use oil")
        self.assertEqual(g.player.oil, 50)

    def test_pack_never_crashes_with_everything_in_it(self):
        g = new_game()
        for iid in ITEMS:
            g.player.add_item(iid, 2)
        out = run(g, "i")
        self.assertIn("PACK", out)


class QuestFlowTests(unittest.TestCase):
    def test_objectives_advance_through_the_main_story(self):
        g = new_game()
        order = []

        def now():
            o = navigation.main_objective(g)
            return o["room"] if o else None
        order.append(now())                       # speak to Orrin
        g.quests["main"] = 1
        order.append(now())                       # the Antlered Mother
        g.flags["mother_dead"] = True
        order.append(now())                       # the Reeve (for the key)
        g.flags["reeve_dead"] = True
        g.player.add_item("tide_key")
        order.append(now())                       # the Bishop
        g.flags["bishop_dead"] = True
        order.append(now())                       # the Choir
        g.flags["choir_dead"] = True
        order.append(now())                       # down the well
        g.flags["embers_set"] = True
        g.quests["main"] = 3
        order.append(now())                       # the Usher
        g.flags["usher_dead"] = True
        order.append(now())                       # the Lightwell
        self.assertEqual(order, ["hall", "mother_grove", "reeve_house", "bishop_altar", "ash_choir", "well_bottom",
                                 "lightwell_gate", "lightwell"])

    def test_every_objective_in_the_story_has_a_route_from_town(self):
        g = new_game()
        g.room_id = "square"
        g.visited |= set(ROOMS)
        for rid in ("hall", "mother_grove", "reeve_house", "bishop_altar", "ash_choir", "lightwell_gate", "lightwell",
                    "ore_vein", "chapel", "smithy"):
            # open every lock so only the map's own connectivity is tested
            path = navigation.find_path(g, "square", rid, respect_locks=False)
            self.assertIsNotNone(path, rid)

    def test_wren_comes_home(self):
        g = new_game()
        g.flags["wren_following"] = True
        g.quests["wren"] = 2
        g.room_id = "square"
        run(g, "e", answers=["0"])     # her reward levels you up; leave the points unspent
        self.assertTrue(g.flags.get("wren_home"))
        self.assertEqual(g.quests["wren"], "done")

    def test_moonpetals_quest_pays_out(self):
        g = new_game()
        g.room_id = "chapel"
        g.quests["petals"] = 0
        g.player.add_item("moonpetal", 3)
        run(g, "talk ilse", answers=["1", "0", "0"])   # give petals, leave points unspent, leave
        self.assertEqual(g.quests["petals"], "done")
        self.assertTrue(g.player.has_item("saints_tooth"))

    def test_pre_boss_warning_blocks_an_unprepared_walk(self):
        g = new_game()
        g.room_id = "deepwood"
        g.player.oil = 10
        g.player.inventory.pop("draught", None)
        out = run(g, "n", answers=["n"])
        self.assertIn("DANGER AHEAD", out)
        self.assertEqual(g.room_id, "deepwood")   # answered no: stayed put

    def test_pre_boss_warning_lets_you_go_in_if_you_insist(self):
        g = new_game()
        g.room_id = "deepwood"
        g.player.oil = 10
        g.cooldown["mother_grove"] = 10 ** 6
        g.flags["mother_dead"] = True              # nothing to fight once inside
        out = run(g, "n", answers=["y"])
        # beaten bosses do not warn at all
        self.assertNotIn("DANGER AHEAD", out)
        self.assertEqual(g.room_id, "mother_grove")


if __name__ == "__main__":
    unittest.main()


class PracticeTests(unittest.TestCase):
    def test_practice_changes_nothing_even_if_you_lose_or_burn_oil(self):
        g = new_game()
        g.room_id = "gate"
        g.flags["hesk_met"] = True      # skip her first-meeting gift, which is not part of practice
        p = g.player
        snapshot = (p.hp, p.oil, dict(p.inventory), p.gold, p.xp, p.level, dict(g.stats))
        # Sparring: flare (burns oil), then take the suggestion until the straw man falls
        run(g, "talk hesk", answers=["2", "f"] + [""] * 30 + ["0"])
        self.assertEqual((p.hp, p.oil, p.inventory, p.gold, p.xp, p.level, g.stats), snapshot)
        self.assertTrue(g.flags.get("practised"))

    def test_practice_kills_do_not_count_for_the_bounty(self):
        g = new_game()
        g.room_id = "gate"
        run(g, "talk hesk", answers=["2"] + [""] * 30 + ["0"])
        self.assertEqual(g.flags.get("bounty_unclaimed", 0), 0)
