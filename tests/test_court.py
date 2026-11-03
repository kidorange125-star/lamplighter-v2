"""M4: the Ember Court vertical slice: power rolls, locks, the beacon, a new resident and the Darkness Dealer."""
import random
import unittest

from lamplighter import clock, dealer, events, gear, npcs, powerroll, save, spells, town
from lamplighter.combat import Combat
from lamplighter.content import AFFIXES, BUILDINGS, ENEMIES, ITEMS, ROOMS
from tests.helpers import new_game, run, temp_home


def quiet():
    import contextlib
    import io
    return contextlib.redirect_stdout(io.StringIO())


def court_game(**kw):
    g = new_game(**kw)
    g.flags["completed"] = True
    g.player.level = 9
    return g


class PowerRollTests(unittest.TestCase):
    def test_the_multiplier_runs_from_half_to_one_and_a_half(self):
        self.assertAlmostEqual(powerroll.mult(1), 0.51)
        self.assertAlmostEqual(powerroll.mult(50), 1.0)
        self.assertAlmostEqual(powerroll.mult(100), 1.5)

    def test_rewards_rise_with_power(self):
        self.assertLess(powerroll.reward_mult(1), powerroll.reward_mult(50))
        self.assertLess(powerroll.reward_mult(50), powerroll.reward_mult(100))

    def test_there_are_five_bands_and_every_power_falls_in_one(self):
        names = {powerroll.band(p)[0] for p in range(1, 101)}
        self.assertEqual(len(names), 5)
        self.assertEqual(powerroll.band(1)[0], "Faltering")
        self.assertEqual(powerroll.band(100)[0], "Ablaze")

    def test_the_queen_has_a_line_of_flavour_for_every_band(self):
        self.assertEqual(len(ENEMIES["cinder_queen"]["roll"]["flavour"]), 5)
        self.assertNotEqual(powerroll.flavour("cinder_queen", 5), powerroll.flavour("cinder_queen", 95))

    def test_mercy_lowers_the_ceiling_after_two_deaths(self):
        self.assertEqual(powerroll.mercy_cap(0), 100)
        self.assertEqual(powerroll.mercy_cap(1), 100)
        self.assertLess(powerroll.mercy_cap(2), 100)
        self.assertLess(powerroll.mercy_cap(3), powerroll.mercy_cap(2))
        self.assertGreater(powerroll.mercy_cap(9), 0)

    def test_rolls_never_exceed_the_ceiling(self):
        g = new_game()
        g.flags["deaths_cinder_queen"] = 3
        cap = powerroll.mercy_cap(3)
        rolls = [powerroll.roll(g, "cinder_queen")[0] for _ in range(300)]
        self.assertLessEqual(max(rolls), cap)
        self.assertGreaterEqual(min(rolls), 1)

    def test_a_story_boss_is_capped(self):
        ENEMIES["_story_test"] = dict(ENEMIES["cinder_queen"], roll={"story": True, "flavour": [], "bonus": []})
        try:
            self.assertEqual(powerroll.cap_for("_story_test", 0), powerroll.STORY_CAP)
            self.assertEqual(powerroll.cap_for("_story_test", 4), 20)
        finally:
            del ENEMIES["_story_test"]

    def test_rolls_cover_the_whole_range(self):
        g = new_game()
        rolls = {powerroll.roll(g, "cinder_queen")[0] for _ in range(2000)}
        self.assertLess(min(rolls), 6)
        self.assertGreater(max(rolls), 95)

    def test_scaling_changes_health_and_damage_together(self):
        weak, strong = powerroll.scaled("cinder_queen", 10), powerroll.scaled("cinder_queen", 90)
        self.assertLess(ENEMIES[weak]["hp"], ENEMIES[strong]["hp"])
        self.assertLess(ENEMIES[weak]["atk"], ENEMIES[strong]["atk"])
        self.assertLess(ENEMIES[weak]["xp"], ENEMIES[strong]["xp"])
        self.assertEqual(ENEMIES[powerroll.scaled("cinder_queen", 50)]["hp"], ENEMIES["cinder_queen"]["hp"])
        self.assertEqual(powerroll.scaled("cinder_queen", 10), weak)       # same power, same registered copy

    def test_bonus_drops_become_likelier_with_power(self):
        def chance(power, item):
            return sum(c for i, c in ENEMIES[powerroll.scaled("cinder_queen", power)]["drops"] if i == item)
        self.assertEqual(chance(5, "queens_ember"), 0)
        self.assertGreater(chance(40, "queens_ember"), 0)
        self.assertEqual(chance(90, "queens_ember"), 1.0)

    def test_the_base_boss_is_not_changed_by_scaling(self):
        before = ENEMIES["cinder_queen"]["hp"], len(ENEMIES["cinder_queen"]["drops"])
        powerroll.scaled("cinder_queen", 77)
        self.assertEqual((ENEMIES["cinder_queen"]["hp"], len(ENEMIES["cinder_queen"]["drops"])), before)

    def test_a_rolled_boss_can_be_fled_but_an_ordinary_boss_cannot(self):
        g = new_game()
        self.assertFalse(Combat(g, [powerroll.scaled("cinder_queen", 50)]).no_flee)
        self.assertTrue(Combat(g, ["hollow_king"]).no_flee)
        self.assertTrue(Combat(g, ["cinder_steward"]).no_flee)

    def test_the_first_gem_bonus_is_given_once_whatever_the_roll(self):
        g = new_game()
        a, b = powerroll.scaled("cinder_queen", 20), powerroll.scaled("cinder_queen", 80)
        before = g.player.gems
        from lamplighter.entities import Enemy
        with quiet():
            g.on_kill(Enemy(a, ENEMIES[a]))
            g.on_kill(Enemy(b, ENEMIES[b]))
        self.assertEqual(g.player.gems, before + 3)


class BossSceneTests(unittest.TestCase):
    def go(self, g, outcome, answers=("1",)):
        calls = []

        def fake(ids, intro=None, **kw):
            calls.append(ids)
            if outcome == "win":
                pass
            return outcome
        g.fight = fake
        g.room_id = "throne_room"
        out = run(g, "look", answers=list(answers)) if False else None
        import contextlib, io
        from lamplighter import ui
        ui.io.script = list(answers)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            events.enter_throne_room(g, True)
        return calls, buf.getvalue()

    def test_stepping_back_is_free_and_starts_no_fight(self):
        g = court_game()
        calls, out = self.go(g, "win", answers=["0"])
        self.assertEqual(calls, [])
        self.assertEqual(g.room_id, "stewards_hall")
        self.assertFalse(g.flags.get("queen_dead"))
        self.assertEqual(g.flags.get("deaths_cinder_queen", 0), 0)

    def test_the_roll_is_shown_before_the_choice(self):
        g = court_game()
        calls, out = self.go(g, "win", answers=["0"])
        self.assertIn("Power", out)
        self.assertTrue(any(b.upper() in out.upper() for _, b, _ in powerroll.BANDS))

    def test_winning_sets_the_flag_and_remembers_the_power(self):
        g = court_game()
        calls, out = self.go(g, "win")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0][0].startswith("cinder_queen@"))
        self.assertTrue(g.flags["queen_dead"])
        self.assertIn(g.flags["power_cinder_queen"], range(1, 101))

    def test_dying_counts_and_two_deaths_trigger_mercy(self):
        g = court_game()
        self.go(g, "dead")
        self.assertEqual(g.flags["deaths_cinder_queen"], 1)
        _, out = self.go(g, "dead")
        self.assertEqual(g.flags["deaths_cinder_queen"], 2)
        self.assertIn("gentler", out)
        _, out = self.go(g, "win", answers=["0"])
        self.assertIn("ceiling", out)

    def test_winning_clears_the_death_count(self):
        g = court_game()
        g.flags["deaths_cinder_queen"] = 3
        self.go(g, "win")
        self.assertNotIn("deaths_cinder_queen", g.flags)

    def test_fleeing_puts_you_back_outside(self):
        g = court_game()
        calls, _ = self.go(g, "fled")
        self.assertEqual(g.room_id, "stewards_hall")
        self.assertFalse(g.flags.get("queen_dead"))

    def test_a_beaten_queen_does_not_come_back(self):
        g = court_game()
        g.flags["queen_dead"] = True
        self.assertFalse(events.enter_throne_room(g, False))


class LockTests(unittest.TestCase):
    def test_the_court_road_waits_for_the_end_of_the_story(self):
        g = new_game()
        g.room_id = "gate"
        run(g, "east")
        self.assertEqual(g.room_id, "gate")
        self.assertIn("LONG NIGHT", " ".join(g.notices))
        g.flags["completed"] = True
        g.cooldown["cinder_road"] = 10 ** 6          # no ambush while we check the door
        run(g, "east")
        self.assertEqual(g.room_id, "cinder_road")

    def test_the_throne_needs_the_crown_key(self):
        g = court_game()
        g.room_id = "stewards_hall"
        run(g, "east")
        self.assertEqual(g.room_id, "stewards_hall")
        self.assertIn("key", " ".join(g.notices).lower())

    def test_the_steward_drops_the_key_once(self):
        g = court_game()
        with quiet():
            events.after_fixed(g, "steward_dead")
            events.after_fixed(g, "steward_dead")
        self.assertEqual(g.player.inventory["court_key"], 1)

    def test_the_cellar_door_asks_for_an_equipped_water_or_ice_book(self):
        g = court_game()
        g.room_id = "kitchens"
        run(g, "south")
        self.assertEqual(g.room_id, "kitchens")
        self.assertIn("Water or Ice", " ".join(g.notices))
        g.player.add_item("book_fire")
        spells.equip(g.player, "book_fire")
        run(g, "south")
        self.assertEqual(g.room_id, "kitchens")           # fire does not help
        g.player.spells.clear()
        g.player.add_item("book_water")
        spells.equip(g.player, "book_water")
        run(g, "south")
        self.assertEqual(g.room_id, "cellars")

    def test_a_carried_book_that_is_not_equipped_does_not_count(self):
        g = court_game()
        g.room_id = "kitchens"
        g.player.add_item("book_ice")
        run(g, "south")
        self.assertEqual(g.room_id, "kitchens")

    def test_once_open_the_cellar_door_stays_open(self):
        g = court_game()
        g.room_id = "kitchens"
        g.player.add_item("book_ice")
        spells.equip(g.player, "book_ice")
        run(g, "south")
        g.player.spells.clear()
        g.room_id = "kitchens"
        run(g, "south")
        self.assertEqual(g.room_id, "cellars")

    def test_the_locked_door_is_not_offered_as_a_suggestion(self):
        g = court_game()
        g.room_id = "kitchens"
        self.assertFalse(any(cmd == "south" for _, cmd, _ in g.suggestions()))


class BeaconTests(unittest.TestCase):
    def lit_ready(self):
        g = court_game()
        g.room_id = "throne_room"
        g.player.oil = g.player.max_oil
        return g

    def test_it_cannot_be_lit_while_the_queen_lives(self):
        g = self.lit_ready()
        run(g, "light")
        self.assertFalse(g.flags.get("beacon_Ember Court"))

    def test_lighting_it_lights_every_room_of_the_court(self):
        g = self.lit_ready()
        g.flags["queen_dead"] = True
        before = g.player.oil
        run(g, "light")
        self.assertTrue(g.flags["beacon_Ember Court"])
        self.assertEqual(before - g.player.oil, 25)
        for rid, r in ROOMS.items():
            if r["region"] == "Ember Court":
                self.assertFalse(g.is_dark(rid), rid)
        self.assertIn("throne_room", g.anchors)

    def test_a_lit_court_is_safe_to_rest_in_anywhere(self):
        g = self.lit_ready()
        g.flags["queen_dead"] = True
        run(g, "light")
        g.room_id = "ballroom"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)

    def test_the_court_gate_is_a_safe_place_before_the_beacon(self):
        g = court_game()
        g.room_id = "court_gate"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)
        self.assertEqual(g.last_rest, "court_gate")

    def test_a_dark_court_room_cannot_be_rested_in(self):
        g = court_game()
        g.room_id = "ballroom"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, 1)

    def test_lighting_needs_oil(self):
        g = self.lit_ready()
        g.flags["queen_dead"] = True
        g.player.oil = 5
        out = run(g, "light")
        self.assertFalse(g.flags.get("beacon_Ember Court"))
        self.assertIn("oil", out)

    def test_dying_in_the_court_wakes_you_at_the_gate(self):
        g = court_game()
        g.last_rest = "court_gate"
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            g.death()
        self.assertEqual(g.room_id, "court_gate")

    def test_the_beacon_state_survives_a_save(self):
        with temp_home():
            g = self.lit_ready()
            g.flags["queen_dead"] = True
            run(g, "light")
            g.save(quiet=True)
            from lamplighter.engine import Game
            h = Game.load() if hasattr(Game, "load") else None
            if h is not None:
                self.assertTrue(h.flags["beacon_Ember Court"])
                self.assertFalse(h.is_dark("ballroom"))


class ResidentTests(unittest.TestCase):
    def setUp(self):
        self.t = [1_000_000.0]
        clock.set_clock(lambda: self.t[0])

    def tearDown(self):
        clock.set_clock(None)

    def test_tamsin_is_hidden_until_the_steward_falls(self):
        g = court_game()
        g.room_id = "court_forge"
        self.assertNotIn("tamsin", g.present_npcs())
        g.flags["steward_dead"] = True
        self.assertIn("tamsin", g.present_npcs())

    def test_pell_is_at_the_gate_and_sells_things(self):
        g = court_game()
        g.room_id = "court_gate"
        self.assertIn("pell", g.present_npcs())
        g.player.gold = 100
        run(g, "trade", answers=["1", "1", "0", "0"])
        self.assertLess(g.player.gold, 100)

    def test_asking_tamsin_invites_her_and_joss_can_build_her_smithy(self):
        g = court_game()
        g.flags["steward_dead"] = True
        g.flags["joss_met"] = True
        g.room_id = "court_forge"
        run(g, "talk tamsin", answers=["1", "0"])
        self.assertTrue(town.is_invited(g, "ember_smithy"))
        self.assertIn("ember_smithy", town.available(g))

    def test_the_second_smithy_adds_a_forge_slot(self):
        g = court_game()
        town.invite(g, "ember_smithy")
        from lamplighter import forge
        self.assertEqual(forge.state(g)["slots"], 1)
        g.player.gold = 1000
        g.player.add_item("slag", 6)
        g.player.add_item("cinder", 6)
        g.flags["joss_met"] = True
        g.room_id = "yard"
        run(g, "talk joss", answers=["1", "0"])
        self.t[0] += 31 * 60
        town.update(g)
        self.assertTrue(town.is_built(g, "ember_smithy"))
        self.assertEqual(forge.state(g)["slots"], 2)

    def test_building_it_twice_never_adds_a_second_slot(self):
        g = court_game()
        town.state(g)["built"].append("ember_smithy")
        from lamplighter import forge
        town._complete(g, "ember_smithy")
        self.assertEqual(forge.state(g)["slots"], 1)

    def test_the_smithy_plot_opens_once_it_is_built(self):
        g = court_game()
        g.room_id = "tavern"
        run(g, "north")
        self.assertEqual(g.room_id, "tavern")
        self.assertIn("vacant plot", " ".join(g.notices))
        town.state(g)["built"].append("ember_smithy")
        run(g, "north")
        self.assertEqual(g.room_id, "ember_smithy")

    def test_the_forge_can_be_used_at_tamsins_smithy(self):
        g = court_game()
        g.room_id = "ember_smithy"
        out = run(g, "forge", answers=["0"])
        self.assertIn("TAMSIN", out.upper())

    def test_tamsin_moves_into_her_smithy(self):
        g = court_game()
        g.flags["steward_dead"] = True
        town.state(g)["built"].append("ember_smithy")
        g.room_id = "court_forge"
        self.assertNotIn("tamsin", g.present_npcs())
        g.room_id = "ember_smithy"
        self.assertIn("tamsin", g.present_npcs())


class DealerTests(unittest.TestCase):
    """The Dealer as the Court's player meets it. The full rules (dark-only, rotation, caps...) are in test_dealer."""

    def setUp(self):
        self.t = [86400.0 * 20000]
        clock.set_clock(lambda: self.t[0])

    def tearDown(self):
        clock.set_clock(None)

    def game(self, gems=100):
        g = court_game()
        g.player.gems = gems
        self.seat(g)
        return g

    def seat(self, g):
        """Stand in the room where the Court's Dealer is sitting today."""
        g.room_id = dealer.room_for(g, 4)
        self.assertIsNotNone(g.room_id)

    def test_four_wares_a_day_and_they_do_not_change_on_a_second_look(self):
        g = self.game()
        a, b = dealer.wares(g), dealer.wares(g)
        self.assertEqual(len(a), 4)
        self.assertEqual(a, b)

    def test_tomorrow_brings_different_wares(self):
        g = self.game()
        days = set()
        for _ in range(8):
            days.add(str(dealer.wares(g, 4)))
            self.t[0] += 86400
        self.assertGreater(len(days), 4)

    def test_the_bargain_is_a_tier_up_and_cursed_and_cheaper(self):
        g = self.game()
        fair, fair2, bargain, relic = [w for _, w in dealer.wares(g)]
        self.assertIsNone(fair["curse"])
        self.assertIsNotNone(bargain["curse"])
        self.assertTrue(AFFIXES[bargain["curse"]]["curse"])
        no_curse = dict(bargain, curse=None)
        self.assertLess(bargain["price"], dealer.price_of(no_curse))
        self.assertEqual(ITEMS[relic["base"]]["kind"], "relic")

    def test_buying_charges_gems_and_gives_what_was_shown(self):
        g = self.game(gems=100)
        _, w = dealer.wares(g)[0]
        head, detail = dealer.preview(w)
        run(g, "talk dealer", answers=["1", "y", "", "0"])
        self.assertEqual(g.player.gems, 100 - w["price"])
        got = [i for i in g.player.inventory if gear.is_instance(i)]
        self.assertEqual(len(got), 1)
        self.assertEqual(ITEMS[got[0]]["rarity"], w["rarity"])
        self.assertIn(ITEMS[got[0]]["name"], head)

    def test_a_ware_is_gone_for_the_day_once_bought(self):
        g = self.game()
        run(g, "talk dealer", answers=["1", "y", "", "0"])
        self.assertEqual(len(dealer.wares(g, 4)), 3)
        self.t[0] += 86400
        self.assertEqual(len(dealer.wares(g, 4)), 4)

    def test_you_cannot_buy_without_enough_gems(self):
        g = self.game(gems=1)
        run(g, "talk dealer", answers=["1", "", "0"])
        self.assertEqual(g.player.gems, 1)
        self.assertFalse([i for i in g.player.inventory if gear.is_instance(i)])

    def test_the_cursed_ware_really_carries_its_curse(self):
        g = self.game(gems=200)
        _, w = dealer.wares(g)[2]
        inst = dealer._make(w)
        self.assertIn(w["curse"], inst["affixes"])
        key, val = next(iter(AFFIXES[w["curse"]]["stats"].items()))
        clean = dict(inst, affixes=[x for x in inst["affixes"] if x != w["curse"]])
        gear.rebuild(clean)
        self.assertLess(inst["stats"].get(key, 0), clean["stats"].get(key, 0))

    def test_the_preview_and_the_purchase_are_the_same_item(self):
        g = self.game()
        for _, w in dealer.wares(g):
            a, b = dealer._make(w), dealer._make(w)
            self.assertEqual(a["affixes"], b["affixes"])
            self.assertEqual(a.get("stats"), b.get("stats"))
            self.assertEqual(a.get("relic_mult"), b.get("relic_mult"))

    def test_previewing_does_not_leave_junk_items_behind(self):
        g = self.game()
        before = len(ITEMS)
        for _, w in dealer.wares(g):
            dealer.preview(w)
            dealer.detail_lines(w)
        self.assertEqual(len(ITEMS), before)

    def test_curses_never_appear_on_ordinary_gear(self):
        rng = random.Random(3)
        for _ in range(300):
            inst = gear.make("saltsteel_saber", "godlike", rng)
            for a in inst["affixes"]:
                self.assertFalse(AFFIXES[a].get("curse"), a)

    def test_dealer_state_survives_a_save(self):
        with temp_home():
            g = self.game()
            run(g, "talk dealer", answers=["1", "y", "", "0"])
            g.save(quiet=True)
            self.assertTrue(g.dealers["bought"])

    def test_the_old_ruined_chapel_is_just_a_room_now(self):
        self.assertNotIn("dealer", ROOMS["ruined_chapel"].get("npcs", []))


class ContentTests(unittest.TestCase):
    def test_every_court_room_is_in_the_region_and_reachable_from_the_gate(self):
        court = [rid for rid, r in ROOMS.items() if r["region"] == "Ember Court"]
        self.assertEqual(len(court), 13)
        g = court_game()
        g.flags["steward_dead"] = True
        g.player.inventory["court_key"] = 1
        g.player.add_item("book_ice")
        spells.equip(g.player, "book_ice")
        from lamplighter import navigation
        for rid in court:
            self.assertTrue(navigation.find_path(g, "gate", rid), rid)

    def test_court_enemies_resist_or_fear_the_right_elements(self):
        for eid in ("ember_hound", "cinder_knight", "molten_gargoyle", "cinder_queen"):
            self.assertIn("fire", ENEMIES[eid]["resist"], eid)
        self.assertIn("water", ENEMIES["cinder_queen"]["weak"])

    def test_the_queen_has_phases_and_rolls(self):
        q = ENEMIES["cinder_queen"]
        self.assertEqual(len(q["phases"]), 2)
        self.assertIn("roll", q)

    def test_the_ember_smithy_costs_and_slot(self):
        b = BUILDINGS["ember_smithy"]
        self.assertTrue(b["forge_slot"])
        self.assertEqual(b["resident"], "tamsin")


if __name__ == "__main__":
    unittest.main()


class ClearTheCourtTests(unittest.TestCase):
    """A strong player walks the Court from the north gate to the lit beacon, fighting with the game's own advice."""

    def setUp(self):
        from lamplighter import engine, sim
        self.engine, self.sim = engine, sim
        self.real = engine.Combat

        class Auto(self.real):
            def __init__(inner, *a, **k):
                k["policy"] = sim.suggested
                super().__init__(*a, **k)
        engine.Combat = Auto

    def tearDown(self):
        self.engine.Combat = self.real

    def test_from_the_north_gate_to_a_lit_court(self):
        sim = self.sim
        g = new_game(seed=5)
        g.player = sim.maxed("wayfarer", 10, "saltsteel_saber", "hauberk", "godlike",
                             items={"draught": 6, "strong_draught": 6, "oil": 6, "honeycake": 3},
                             lantern={"shroud": True, "trim": True, "lens": True},
                             spells=[("water", "epic")])
        g.flags["completed"] = True
        g.room_id = "gate"
        g.visited.add("gate")
        g.player.oil = g.player.max_oil
        for step in ("east", "east", "east", "east"):          # road, gate, hall, steward's hall
            run(g, step, answers=["y"] * 4)
            g.player.oil = g.player.max_oil
            if g.player.hp < g.player.max_hp * 0.5:
                g.player.hp = g.player.max_hp
        self.assertEqual(g.room_id, "stewards_hall")
        self.assertTrue(g.flags.get("steward_dead"))
        self.assertTrue(g.player.has_item("court_key"))
        g.player.hp = g.player.max_hp
        for _ in range(5):                                      # the roll is random: step back until she is beatable
            run(g, "east", answers=["y", "1", "y"])
            if g.flags.get("queen_dead"):
                break
            g.room_id = "stewards_hall"
            g.player.hp, g.player.oil = g.player.max_hp, g.player.max_oil
        self.assertTrue(g.flags.get("queen_dead"))
        self.assertEqual(g.room_id, "throne_room")
        g.player.oil = g.player.max_oil            # the fight drained the lantern; refill from a flask
        out = run(g, "light")
        self.assertTrue(g.flags.get("beacon_Ember Court"), out)
        self.assertFalse(g.is_dark("cellars"))
        self.assertGreaterEqual(g.player.gems, 3)


class ValidatorTests(unittest.TestCase):
    """The content checks must actually catch the mistakes they exist for."""

    def problems(self):
        from lamplighter.validate import validate
        return validate()

    def test_the_real_content_is_clean(self):
        self.assertEqual(self.problems(), [])

    def test_a_roll_with_the_wrong_number_of_flavour_lines_is_caught(self):
        q = ENEMIES["cinder_queen"]["roll"]
        keep = q["flavour"]
        q["flavour"] = keep[:4]
        try:
            self.assertTrue(any("5 lines of flavour" in p for p in self.problems()))
        finally:
            q["flavour"] = keep

    def test_a_bonus_drop_of_a_missing_item_is_caught(self):
        q = ENEMIES["cinder_queen"]["roll"]
        q["bonus"].append({"item": "nope", "from": 1, "to": 50})
        try:
            self.assertTrue(any("nope" in p for p in self.problems()))
        finally:
            q["bonus"].pop()

    def test_a_boss_flag_nobody_sets_is_caught(self):
        r = ROOMS["ballroom"]
        r["boss"] = "nobody_sets_this"
        try:
            self.assertTrue(any("nobody_sets_this" in p for p in self.problems()))
        finally:
            del r["boss"]

    def test_a_lock_that_needs_an_unknown_element_is_caught(self):
        lock = ROOMS["kitchens"]["locks"]["s"]
        keep = lock["element"]
        lock["element"] = ["plasma"]
        try:
            self.assertTrue(any("plasma" in p for p in self.problems()))
        finally:
            lock["element"] = keep

    def test_a_positive_curse_and_a_negative_blessing_are_caught(self):
        AFFIXES["brittle"]["stats"]["def"] = 3
        AFFIXES["keen"]["stats"]["crit"] = -4
        try:
            msgs = " ".join(self.problems())
            self.assertIn("brittle", msgs)
            self.assertIn("keen", msgs)
        finally:
            AFFIXES["brittle"]["stats"]["def"] = -3
            AFFIXES["keen"]["stats"]["crit"] = 4
