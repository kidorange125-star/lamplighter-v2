import contextlib
import io
import random
import unittest

from lamplighter import clock, forge, forge_ui, gear, ui
from lamplighter.content import AFFIXES, FORGE, ITEMS
from lamplighter.engine import Game
from tests.helpers import new_game, run, temp_home


class Rig(random.Random):
    """A random source whose .random() always returns the same number, to force success or failure."""

    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


class Clock:
    def __init__(self):
        self.t = 2_000_000.0

    def __call__(self):
        return self.t

    def advance(self, minutes):
        self.t += minutes * 60


class ForgeCase(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        clock.set_clock(self.clock)

    def tearDown(self):
        clock.set_clock(None)

    def game(self, roll=0.0):
        g = new_game()
        g.rng = Rig(roll)
        g.player.gold = 5000
        g.player.add_item("slag", 40)
        g.player.add_item("saltstone", 20)
        g.player.add_item("hollow_core", 10)
        return g

    def finish(self, g):
        self.clock.advance(100000)
        forge.update(g)


class GearTests(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(5)

    def test_rarity_scales_stats_upward(self):
        defs = [gear.make("hauberk", r, self.rng, affixes=[])["stats"]["def"] for r in ("rare", "epic", "ultra", "legendary", "godlike")]
        self.assertEqual(defs, sorted(defs))
        self.assertGreater(defs[-1], defs[0] * 2)

    def test_weapons_gain_a_damage_multiplier_with_rarity(self):
        m = [gear.make("hunting_spear", r, self.rng, affixes=[])["mult"].get("dmg", 1.0)
             for r in ("rare", "epic", "ultra", "legendary", "godlike")]
        self.assertEqual(m, sorted(m))
        self.assertAlmostEqual(m[-1] / m[0], gear.WEAPON_MULT["godlike"], places=1)

    def test_sockets_by_rarity(self):
        s = [gear.make("hauberk", r, self.rng)["sockets"] for r in ("rare", "epic", "ultra", "legendary", "godlike")]
        self.assertEqual(s, [1, 1, 2, 3, 3])

    def test_affix_counts_by_rarity(self):
        for r, n in (("rare", 0), ("epic", 1), ("ultra", 2), ("legendary", 2), ("godlike", 3)):
            self.assertEqual(len(gear.make("hunting_spear", r, self.rng)["affixes"]), n, r)

    def test_affixes_fit_the_slot(self):
        for _ in range(30):
            inst = gear.make("hauberk", "godlike", self.rng)
            for aid in inst["affixes"]:
                self.assertIn("armor", AFFIXES[aid]["slots"])

    def test_relics_multiply_in(self):
        plain = gear.make("hunting_spear", "legendary", self.rng, affixes=[])
        loaded = gear.make("hunting_spear", "legendary", self.rng, affixes=[],
                           relics=[{"base": "relic_edge", "rarity": "legendary"}] * 3)
        self.assertAlmostEqual(loaded["mult"]["phys"], 1.25 ** 3, places=2)
        self.assertNotIn("phys", plain["mult"])

    def test_instances_behave_like_items_everywhere(self):
        inst = gear.make("saltsteel_saber", "epic", self.rng)
        self.assertIn(inst["id"], ITEMS)
        self.assertEqual(ITEMS[inst["id"]]["kind"], "weapon")
        self.assertTrue(gear.is_instance(inst["id"]))
        self.assertEqual(gear.base_id(inst["id"]), "saltsteel_saber")

    def test_player_uses_instance_stats_and_multipliers(self):
        g = new_game()
        base_attack = g.player.attack
        inst = gear.make("hunting_spear", "legendary", self.rng, affixes=[])
        gear.give(g.player, inst)
        g.player.inventory.pop(inst["id"])
        g.player.equipment["weapon"] = inst["id"]
        self.assertGreater(g.player.attack, base_attack + 5)
        self.assertAlmostEqual(g.player.mult("phys"), gear.WEAPON_MULT["legendary"])

    def test_instances_survive_a_save(self):
        with temp_home():
            g = new_game()
            inst = gear.make("hunting_spear", "epic", self.rng)
            gear.give(g.player, inst)
            g.player.inventory.pop(inst["id"])
            g.player.equipment["weapon"] = inst["id"]
            name, mult = inst["name"], inst["mult"]
            g.save(quiet=True)
            ITEMS.pop(inst["id"])                  # a fresh process would not know it yet
            g2 = Game.load()
            self.assertEqual(g2.player.equipment["weapon"], inst["id"])
            self.assertEqual(ITEMS[inst["id"]]["name"], name)
            self.assertEqual(ITEMS[inst["id"]]["mult"], mult)

    def test_new_ids_never_collide_with_loaded_ones(self):
        inst = {"id": "g9999", "instance": True, "base": "hauberk", "kind": "armor", "rarity": "rare", "affixes": [],
                "relics": []}
        gear.rebuild(inst)
        gear.register(inst)
        fresh = gear.make("hauberk", "rare", self.rng)
        self.assertNotEqual(fresh["id"], "g9999")
        self.assertGreater(int(fresh["id"][1:]), 9999)

    def test_pack_and_examine_show_rarity_and_sockets(self):
        g = new_game()
        inst = gear.make("hauberk", "legendary", self.rng)
        gear.give(g.player, inst)
        out = run(g, "i", "x " + inst["name"].split()[-1])
        self.assertIn("✦", out)               # the legendary symbol


class ForgeTests(ForgeCase):
    def test_only_rare_and_better_can_be_forged(self):
        g = self.game()
        ids = [c[0] for c in forge.candidates(g)]
        self.assertNotIn("hook", ids)
        self.assertNotIn("oilskin", ids)
        g.player.add_item("hauberk")
        self.assertIn("hauberk", [c[0] for c in forge.candidates(g)])

    def test_starting_costs_gold_and_materials_and_takes_the_item(self):
        g = self.game()
        g.player.add_item("hauberk")
        gold, slag = g.player.gold, g.player.inventory["slag"]
        ok, _ = forge.start(g, "hauberk")
        self.assertTrue(ok)
        self.assertEqual(g.player.gold, gold - FORGE["tiers"]["rare"]["gold"])
        self.assertEqual(g.player.inventory["slag"], slag - 4)
        self.assertFalse(g.player.has_item("hauberk"))

    def test_cannot_start_without_the_cost_or_a_free_slot(self):
        g = self.game()
        g.player.add_item("hauberk")
        g.player.add_item("drowned_mail")
        g.player.gold = 10
        ok, msg = forge.start(g, "hauberk")
        self.assertFalse(ok)
        self.assertIn("gold", msg)
        g.player.gold = 5000
        self.assertTrue(forge.start(g, "hauberk")[0])
        ok, msg = forge.start(g, "drowned_mail")
        self.assertFalse(ok)
        self.assertIn("slot", msg)

    def test_the_worn_weapon_is_replaced_by_a_weaker_loaner(self):
        g = self.game()
        g.player.equipment["weapon"] = "saltsteel_saber"
        before = g.player.attack
        self.assertTrue(forge.start(g, "saltsteel_saber")[0])
        loaner = g.player.equipment["weapon"]
        self.assertTrue(ITEMS[loaner].get("loaner"))
        # exactly the stated penalty on top of everything the real weapon had
        self.assertAlmostEqual(g.player.mult("phys"), FORGE["loaner_penalty"] * ITEMS["saltsteel_saber"]["mult"]["phys"])
        self.assertIn("weaker", ITEMS[loaner]["desc"])
        self.assertEqual(ITEMS[loaner]["rarity"], "rare")

    def test_the_loaner_matches_the_original_weapons_rarity(self):
        g = self.game()
        orig = gear.make("hunting_spear", "legendary", random.Random(2), affixes=["keen"])
        gear.give(g.player, orig)
        g.player.inventory.pop(orig["id"])
        g.player.equipment["weapon"] = orig["id"]
        g.player.gold = 99999
        g.flags["godlike_recipe"] = True
        forge.state(g)["slots"] = 2
        for mat in ("slag", "saltstone", "hollow_core", "ff_rime", "vg_starglass"):
            g.player.add_item(mat, 100)
        forge.start(g, orig["id"])
        lo = ITEMS[g.player.equipment["weapon"]]
        self.assertEqual(lo["rarity"], "legendary")
        self.assertEqual(lo["affixes"], ["keen"])
        self.assertEqual(lo["relics"], [])
        self.assertAlmostEqual(lo["mult"]["dmg"], gear.WEAPON_MULT["legendary"] * FORGE["loaner_penalty"], places=3)

    def test_worn_armour_just_comes_off(self):
        g = self.game()
        g.player.equipment["armor"] = "hauberk"
        forge.start(g, "hauberk")
        self.assertIsNone(g.player.equipment["armor"])

    def test_time_finishes_a_job(self):
        g = self.game()
        g.player.add_item("hauberk")
        forge.start(g, "hauberk")
        self.clock.advance(5)
        forge.update(g)
        self.assertEqual(forge.ready_jobs(g), [])
        self.clock.advance(20)
        forge.update(g)
        self.assertEqual(forge.ready_jobs(g), [0])

    def test_steps_finish_a_job(self):
        g = self.game()
        g.player.add_item("hauberk")
        forge.start(g, "hauberk")
        for _ in range(FORGE["tiers"]["rare"]["steps"]):
            forge.on_step(g)
        self.assertEqual(forge.ready_jobs(g), [0])

    def test_gems_hurry_a_job(self):
        g = self.game()
        g.player.add_item("hauberk")
        forge.start(g, "hauberk")
        g.player.gems = 50
        self.assertTrue(forge.hurry(g, 0))
        self.assertEqual(forge.ready_jobs(g), [0])
        self.assertLess(g.player.gems, 50)

    def test_success_raises_the_tier_and_returns_the_worn_weapon(self):
        g = self.game(roll=0.0)
        g.player.equipment["weapon"] = "saltsteel_saber"
        forge.start(g, "saltsteel_saber")
        loaner = g.player.equipment["weapon"]
        self.finish(g)
        result = forge.collect(g, 0)
        self.assertTrue(result["success"])
        self.assertEqual((result["before"], result["after"]), ("rare", "epic"))
        self.assertEqual(g.player.equipment["weapon"], result["item"])     # re-equipped
        self.assertNotIn(loaner, g.player.gear)                            # the loaner is gone
        self.assertEqual(ITEMS[result["item"]]["rarity"], "epic")
        self.assertEqual(forge.heat(g, result["item"]), 0)

    def test_failure_keeps_the_item_refunds_materials_and_adds_heat(self):
        g = self.game(roll=0.99)
        g.player.add_item("hauberk")
        slag = g.player.inventory["slag"]
        forge.start(g, "hauberk")
        self.assertEqual(g.player.inventory["slag"], slag - 4)
        self.finish(g)
        result = forge.collect(g, 0)
        self.assertFalse(result["success"])
        self.assertTrue(g.player.has_item("hauberk"))                      # nothing was destroyed
        self.assertEqual(g.player.inventory["slag"], slag - 4 + 2)         # half back
        self.assertEqual(result["heat"], 1)

    def test_heat_raises_the_chance_and_a_full_bar_is_a_sure_thing(self):
        g = self.game(roll=0.99)
        g.player.add_item("hauberk")
        base = forge.chance(g, "hauberk")
        forge.state(g)["heat"]["gear:rare"] = 3
        self.assertAlmostEqual(forge.chance(g, "hauberk"), base + 3 * FORGE["heat_bonus"])
        forge.state(g)["heat"]["gear:rare"] = FORGE["tiers"]["rare"]["pity"]
        self.assertEqual(forge.chance(g, "hauberk"), 1.0)
        forge.start(g, "hauberk")
        self.finish(g)
        self.assertTrue(forge.collect(g, 0)["success"])                    # roll of 0.99 still succeeds

    def test_pity_is_per_tier(self):
        g = self.game()
        forge.state(g)["heat"]["gear:rare"] = 5
        gear_epic = gear.make("hauberk", "epic", random.Random(1))
        gear.give(g.player, gear_epic)
        self.assertEqual(forge.heat(g, gear_epic["id"]), 0)

    def test_godlike_needs_a_recipe(self):
        g = self.game()
        inst = gear.make("hunting_spear", "legendary", random.Random(1))
        gear.give(g.player, inst)
        g.player.gold = 99999
        ok, msg = forge.start(g, inst["id"])
        self.assertFalse(ok)
        self.assertIn("third quench", msg)
        self.assertIn("second anvil", msg)
        g.flags["godlike_recipe"] = True
        forge.state(g)["slots"] = 2
        for mat in ("slag", "saltstone", "hollow_core", "ff_rime", "vg_starglass"):
            g.player.add_item(mat, 100)
        self.assertTrue(forge.start(g, inst["id"])[0])

    def test_an_instance_keeps_its_relics_when_upgraded(self):
        g = self.game(roll=0.0)
        inst = gear.make("hauberk", "rare", g.rng, affixes=[], relics=[{"base": "relic_heart", "rarity": "rare"}])
        gear.give(g.player, inst)
        forge.start(g, inst["id"])
        self.finish(g)
        result = forge.collect(g, 0)
        self.assertEqual(len(ITEMS[result["item"]]["relics"]), 1)
        self.assertEqual(result["item"], inst["id"])

    def test_forge_state_survives_a_save(self):
        with temp_home():
            g = self.game()
            g.player.add_item("hauberk")
            forge.start(g, "hauberk")
            g.save(quiet=True)
            g2 = Game.load()
            self.assertEqual(len(forge.state(g2)["jobs"]), 1)


class RelicTests(ForgeCase):
    def test_relics_can_be_forged_up_with_hollow_cores(self):
        g = self.game(roll=0.0)
        g.player.add_item("relic_ember")
        cores = g.player.inventory["hollow_core"]
        self.assertTrue(forge.start(g, "relic_ember")[0])
        self.assertEqual(g.player.inventory["hollow_core"], cores - 1)
        self.finish(g)
        r = forge.collect(g, 0)
        self.assertEqual(r["after"], "uncommon")
        self.assertGreater(ITEMS[r["item"]]["relic_mult"]["fire"], 1.04)

    def test_socketing_turns_a_base_item_into_an_instance_with_the_relic(self):
        g = self.game()
        g.player.add_item("hauberk")
        g.player.add_item("relic_heart")
        new = forge.socket_in(g, "hauberk", "relic_heart")
        self.assertTrue(gear.is_instance(new))
        self.assertEqual(len(ITEMS[new]["relics"]), 1)
        self.assertFalse(g.player.has_item("relic_heart"))
        self.assertAlmostEqual(ITEMS[new]["mult"]["heal"], 1.04)

    def test_full_sockets_refuse_more(self):
        g = self.game()
        g.player.add_item("hauberk")
        g.player.add_item("relic_heart", 2)
        host = forge.socket_in(g, "hauberk", "relic_heart")
        self.assertIsNone(forge.socket_in(g, host, "relic_heart"))
        self.assertEqual(g.player.inventory["relic_heart"], 1)

    def test_taking_a_relic_out_loses_nothing(self):
        g = self.game()
        g.player.add_item("hauberk")
        g.player.add_item("relic_heart")
        host = forge.socket_in(g, "hauberk", "relic_heart")
        back = forge.take_out(g, host, 0)
        self.assertEqual(back, "relic_heart")
        self.assertTrue(g.player.has_item("relic_heart"))
        self.assertEqual(ITEMS[host]["relics"], [])

    def test_a_better_relic_comes_back_as_the_same_rarity(self):
        g = self.game()
        host = gear.make("hunting_spear", "legendary", g.rng, affixes=[], relics=[{"base": "relic_edge", "rarity": "epic"}])
        gear.give(g.player, host)
        back = forge.take_out(g, host["id"], 0)
        self.assertEqual(ITEMS[back]["rarity"], "epic")
        self.assertEqual(ITEMS[back]["kind"], "relic")

    def test_bosses_drop_hollow_cores(self):
        from lamplighter.content import ENEMIES
        for eid in ("antlered_mother", "drowned_bishop", "pale_usher", "hollow_king"):
            self.assertTrue(any(d[0] == "hollow_core" and d[1] == 1.0 for d in ENEMIES[eid]["drops"]), eid)


class ForgeMenuTests(ForgeCase):
    def test_start_a_forging_through_the_menu(self):
        g = self.game()
        g.player.add_item("hauberk")
        out = io.StringIO()
        ui.io.script = ["1", "1", "y", "0"]        # Forge something better / the hauberk / yes / leave
        with contextlib.redirect_stdout(out):
            forge_ui.menu(g)
        self.assertEqual(len(forge.state(g)["jobs"]), 1)
        self.assertIn("35%", out.getvalue())       # the odds were shown before committing
        self.assertIn("working", out.getvalue())

    def test_collect_through_the_menu_runs_the_reveal(self):
        g = self.game(roll=0.0)
        g.player.add_item("hauberk")
        forge.start(g, "hauberk")
        self.finish(g)
        out = io.StringIO()
        ui.io.script = ["1", "", "0"]              # Collect / press Enter / leave
        with contextlib.redirect_stdout(out):
            forge_ui.menu(g)
        text = out.getvalue()
        self.assertIn("EPIC", text)
        self.assertIn("It took", text)

    def test_a_failed_forging_is_explained_kindly(self):
        g = self.game(roll=0.99)
        g.player.add_item("hauberk")
        forge.start(g, "hauberk")
        self.finish(g)
        out = io.StringIO()
        ui.io.script = ["1", "", "0"]
        with contextlib.redirect_stdout(out):
            forge_ui.menu(g)
        self.assertIn("did not take", out.getvalue())
        self.assertIn("more likely", out.getvalue())

    def test_the_forge_command_only_works_at_brann(self):
        g = new_game()
        g.room_id = "square"
        out = run(g, "forge")
        self.assertIn("Brann's", out)

    def test_brann_offers_the_forge(self):
        g = new_game()
        g.room_id = "smithy"
        g.flags["brann_met"] = True
        ui.io.script = ["1", "0", "0"]             # Use the forge / leave the forge / leave Brann
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            g.handle("talk brann")
        self.assertIn("BRANN'S FORGE", out.getvalue())


class SweepTests(unittest.TestCase):
    def test_sweep_prints_the_landing_tier(self):
        ui.settings.color = False
        ui.settings.typewriter = False
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ui.sweep(forge_ui._stops(), 4)
        self.assertIn("ULTRA", out.getvalue())


if __name__ == "__main__":
    unittest.main()
