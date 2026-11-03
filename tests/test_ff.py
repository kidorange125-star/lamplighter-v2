"""M6 package ff: the Frostfair (ring 5, area A), its annex and Marit's stall. See docs/M6-SPEC.md section 9."""
import contextlib
import io
import unittest
from collections import deque

from lamplighter import areas, clock, dealer, events, navigation, npcs, powerroll, town, ui, validate
from lamplighter.areas import ff
from lamplighter.content import BUILDINGS, ENEMIES, ITEMS, REGION_INFO, ROOMS
from tests.helpers import new_game, run

FROSTFAIR = "The Frostfair"
BELOW = "The Fair Below"

# the ids of docs/M6-SPEC.md section 18 for this package
ROOM_IDS = ["ff_frost_road", "ff_fair_gate", "ff_lending_tent", "ff_midway", "ff_skate_pond", "ff_ice_cellars",
            "ff_lamp_row", "ff_wardens_booth", "ff_carousel", "ff_sculptors_row", "ff_great_gate", "ff_wintering",
            "ff_signal_stair", "ff_stall", "ff_below_stair", "ff_below_hall", "ff_below_pool"]
ENEMY_IDS = ["ff_hawker", "ff_skater", "ff_horse", "ff_ice_figure", "ff_lamp", "ff_below_sleeper", "ff_ringmaster",
             "ff_lampmaster"]
ITEM_IDS = ["ff_rime", "ff_fair_token", "ff_cider", "ff_fairlight", "ff_wardens_key", "ff_cellar_key", "ff_receipt",
            "ff_given_flame", "ff_wintering_flame", "ff_greatcoat", "ff_lamp_pole"]


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def flat(text):
    """Printed text is wrapped to the terminal: compare it as one line."""
    return " ".join(text.split())


def ff_game(**kw):
    """A player past the story with the Court lit, in the Frostfair's level range, full of oil."""
    g = new_game(**kw)
    g.flags["completed"] = True
    g.flags["beacon_Ember Court"] = True
    g.player.level = 11
    g.player.hp = g.player.max_hp
    g.player.oil = g.player.max_oil
    g.player.add_item("draught", 3)
    return g


def say_at(g, room, *commands, answers=()):
    """Stand in `room` (no ambush) and run commands; returns the printed text plus the notices."""
    g.room_id = room
    g.cooldown = {rid: 10 ** 6 for rid in ROOMS}
    out = run(g, *commands, answers=answers)
    return flat(out + " " + " ".join(g.notices))


class Fights:
    """Replace g.fight with a stub that returns a fixed outcome and records the enemies."""

    def __init__(self, g, outcome):
        self.calls = []
        self.outcome = outcome
        g.fight = self

    def __call__(self, ids, intro=None, **kw):
        self.calls.append(list(ids))
        return self.outcome


# ============================================================================ content
class ContentTests(unittest.TestCase):
    def test_every_id_of_the_register_exists(self):
        for rid in ROOM_IDS:
            self.assertIn(rid, ROOMS)
        for eid in ENEMY_IDS:
            self.assertIn(eid, ENEMIES)
        for iid in ITEM_IDS:
            self.assertIn(iid, ITEMS)
        for nid in ("ff_dunmore", "ff_marit"):
            self.assertIn(nid, npcs.NPCS)
            self.assertTrue(hasattr(npcs, "talk_" + nid))
        self.assertIn("ff_fair_stall", BUILDINGS)

    def test_thirteen_field_rooms_three_annex_rooms_and_the_stall(self):
        self.assertEqual(sum(1 for r in ROOMS.values() if r["region"] == FROSTFAIR), 13)
        self.assertEqual(sum(1 for r in ROOMS.values() if r["region"] == BELOW), 3)
        self.assertEqual(ROOMS["ff_stall"]["region"], "Hollowmere")
        self.assertEqual(len([rid for rid in ROOMS if rid.startswith("ff_")]), 17)

    def test_the_regions_are_ring_five_and_the_annex_has_no_dealer(self):
        a, b = REGION_INFO[FROSTFAIR], REGION_INFO[BELOW]
        self.assertEqual((a["ring"], b["ring"]), (5, 5))
        self.assertEqual(a["levels"], "10-11")
        self.assertEqual(b["levels"], "11-12")
        self.assertTrue(a["dealer"])
        self.assertEqual(a["dealer_after"], "beacon_Ember Court")
        self.assertIs(b["dealer"], False)

    def test_every_room_has_a_description_and_features(self):
        for rid in ROOM_IDS:
            self.assertTrue(ROOMS[rid]["desc"], rid)
            self.assertTrue(ROOMS[rid]["features"], rid)

    def test_no_hollow_is_weak_to_light(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            if "hollow" in e["tags"]:
                self.assertNotIn("light", e["weak"], eid)

    def test_ice_is_never_a_weakness_and_water_only_hurts_the_hung_lamp(self):
        for eid in ENEMY_IDS:
            self.assertNotIn("ice", ENEMIES[eid]["weak"], eid)
            if eid != "ff_lamp":
                self.assertNotIn("water", ENEMIES[eid]["weak"], eid)
        for eid in ("ff_hawker", "ff_skater", "ff_ice_figure", "ff_below_sleeper", "ff_ringmaster", "ff_lampmaster"):
            self.assertEqual(set(ENEMIES[eid]["resist"]), {"ice", "water"}, eid)
        self.assertEqual(ENEMIES["ff_lampmaster"]["weak"], ["fire", "earth"])

    def test_every_heavy_or_charge_move_has_a_tell(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            moves = list(e["moves"]) + [m for ph in e.get("phases", []) for m in ph["moves"]]
            for m in moves:
                self.assertTrue(m.get("tell"), "%s %s" % (eid, m["name"]))
                self.assertTrue(e["desc"], eid)

    def test_encounter_groups_have_at_most_two_and_enough_singles(self):
        for rid in ROOM_IDS:
            groups = ROOMS[rid].get("enc", {}).get("groups", [])
            if not groups:
                continue
            self.assertTrue(all(len(g) <= 2 for g, _ in groups), rid)
            single = sum(w for g, w in groups if len(g) == 1)
            self.assertGreaterEqual(single * 100, 40 * sum(w for _, w in groups), rid)

    def test_the_area_check_is_clean(self):
        self.assertEqual(ff.CHECK(), [])
        self.assertFalse([e for e in areas.check() if e.startswith("ff:")])

    def test_the_validator_has_nothing_to_say_about_this_area(self):
        mine = [p for p in validate.validate() if "ff_" in p or FROSTFAIR in p or BELOW in p]
        self.assertEqual(mine, [])

    def test_hobb_is_a_queen_shaped_boss_with_a_roll_and_two_phases(self):
        h = ENEMIES["ff_lampmaster"]
        self.assertEqual(len(h["phases"]), 2)
        self.assertEqual([p["at"] for p in h["phases"]], [0.66, 0.33])
        self.assertEqual(len(h["roll"]["flavour"]), 5)
        self.assertEqual(h["roll"]["pron"], {"subj": "he", "obj": "him", "poss": "his"})
        self.assertEqual(h["roll"]["place"], "The Fair")
        self.assertIn("boss", h["tags"])
        self.assertFalse(h["roll"]["story"])
        bonus = {b["item"] for b in h["roll"]["bonus"]}
        self.assertEqual(bonus, {"ff_wintering_flame", "hollow_core", "ff_rime", "essence_fire"})

    def test_the_ringmaster_is_an_elite_with_one_phase(self):
        r = ENEMIES["ff_ringmaster"]
        self.assertIn("elite", r["tags"])
        self.assertEqual(len(r["phases"]), 1)
        names = [m["name"] for m in r["phases"][0]["moves"]]
        self.assertEqual(names[-1], "Merry-Go-Round")
        self.assertEqual(len(names), len(r["moves"]) + 1)
        self.assertNotIn("boss", r["tags"])

    def test_the_two_fields(self):
        pond, square = ROOMS["ff_skate_pond"]["field"], ROOMS["ff_wintering"]["field"]
        self.assertEqual((pond["name"], pond["fire"], pond["earth"]), ("Black Ice", 0.75, 1.25))
        self.assertEqual((square["name"], square["fire"], square["light"]), ("Midwinter", 0.8, 0.85))

    def test_the_gear_is_at_the_right_tiers(self):
        self.assertEqual(ITEMS["ff_greatcoat"]["rarity"], "ultra")
        self.assertEqual(ITEMS["ff_wintering_flame"]["rarity"], "ultra")
        self.assertEqual(ITEMS["ff_lamp_pole"]["rarity"], "rare")
        for iid in ("ff_receipt", "ff_given_flame", "ff_cellar_key", "ff_wardens_key"):
            self.assertEqual(ITEMS[iid]["kind"], "key")
        self.assertIn("Held in trust", ITEMS["ff_receipt"]["desc"].replace("in trust until", "Held in trust"))

    def test_the_receipt_lies_on_the_floor_of_the_lending_tent(self):
        g = ff_game()
        self.assertIn("ff_receipt", g.room_items["ff_lending_tent"])

    def test_every_room_is_reachable_from_the_hall_ignoring_locks(self):
        seen, queue = {"hall"}, deque(["hall"])
        while queue:
            for dest in ROOMS[queue.popleft()]["exits"].values():
                if dest not in seen:
                    seen.add(dest)
                    queue.append(dest)
        self.assertEqual(set(ROOM_IDS) - seen, set())

    def test_the_hollowmere_doors_are_attached(self):
        self.assertEqual(ROOMS["gate"]["exits"]["w"], "ff_frost_road")
        self.assertEqual(ROOMS["hearth_stall"]["exits"]["e"], "ff_stall")
        self.assertEqual(ROOMS["ff_frost_road"]["exits"]["e"], "gate")
        self.assertEqual(ROOMS["ff_stall"]["exits"], {"w": "hearth_stall"})
        self.assertEqual(ROOMS["ff_ice_cellars"]["exits"]["d"], "ff_below_stair")
        self.assertEqual(ROOMS["ff_signal_stair"]["exits"]["e"], "ff_wintering")

    def test_the_building(self):
        b = BUILDINGS["ff_fair_stall"]
        self.assertEqual(b["room"], "ff_stall")
        self.assertEqual(b["resident"], "ff_marit")
        self.assertEqual(b["cost"], {"gold": 1200, "items": {"ff_rime": 8, "cinder": 6}})
        self.assertEqual((b["minutes"], b["steps"], b["rent"]), (40, 60, 14))
        self.assertFalse(b.get("forge_slot"))


# ============================================================================ locks
class LockTests(unittest.TestCase):
    def test_the_frost_road_waits_for_the_courts_beacon(self):
        g = new_game()
        out = say_at(g, "gate", "west")
        self.assertEqual(g.room_id, "gate")
        self.assertIn(ROOMS["gate"]["locks"]["w"]["msg"], out)
        self.assertIn("relight the Ember Court's beacon", out)
        g.flags["beacon_Ember Court"] = True
        say_at(g, "gate", "west")
        self.assertEqual(g.room_id, "ff_frost_road")

    def test_the_stall_plot_waits_for_the_building(self):
        g = ff_game()
        out = say_at(g, "hearth_stall", "east")
        self.assertEqual(g.room_id, "hearth_stall")
        self.assertIn("Marit Ostrand", out)
        self.assertIn("Joss", out)
        town.state(g)["built"].append("ff_fair_stall")
        say_at(g, "hearth_stall", "east")
        self.assertEqual(g.room_id, "ff_stall")

    def test_the_booth_wants_the_wardens_key(self):
        g = ff_game()
        out = say_at(g, "ff_lamp_row", "north")
        self.assertEqual(g.room_id, "ff_lamp_row")
        self.assertIn("Ringmaster of Rime wears the key", out)
        self.assertIn("Defeat him in the carousel", out)
        g.player.add_item("ff_wardens_key")
        say_at(g, "ff_lamp_row", "north")
        self.assertEqual(g.room_id, "ff_wardens_booth")

    def test_the_great_gate_wants_all_three_posts_and_says_how_many(self):
        g = ff_game()
        out = say_at(g, "ff_great_gate", "west")
        self.assertEqual(g.room_id, "ff_great_gate")
        self.assertIn("relight all three Lending Posts", out)
        self.assertIn("0 of 3 done.", out)
        g.flags["lit_ff_midway"] = True
        g.flags["lit_ff_lamp_row"] = True
        out = say_at(g, "ff_great_gate", "west")
        self.assertIn("2 of 3 done.", out)
        self.assertEqual(g.room_id, "ff_great_gate")

    def test_lighting_the_three_posts_opens_the_gate(self):
        g = ff_game()
        g.flags["ff_lampmaster_dead"] = True              # keeps the boss scene out of this test
        for post in ff.POSTS:
            say_at(g, post, "light")
            self.assertTrue(g.flags["lit_" + post], post)
            self.assertTrue(g.is_dark(post) is False)
        self.assertEqual(g.player.oil, g.player.max_oil - 30)
        out = say_at(g, "ff_great_gate", "west")
        self.assertEqual(g.room_id, "ff_wintering")
        self.assertIn("borrowed gold", out)

    def test_each_post_says_a_frozen_mouth_finishes_its_word(self):
        g = ff_game()
        for post in ff.POSTS:
            self.assertIn("finishes its word", say_at(g, post, "light"))

    def test_the_pond_trapdoor_wants_the_key_and_a_steady_heart(self):
        g = ff_game()
        g.player.dread = 10
        out = say_at(g, "ff_skate_pond", "south")                 # no key
        self.assertEqual(g.room_id, "ff_skate_pond")
        self.assertIn("the Fair's cellar-key", out)
        g.player.add_item("ff_cellar_key")
        g.player.dread = 25                                         # the key, but a racing heart
        out = say_at(g, "ff_skate_pond", "south")
        self.assertEqual(g.room_id, "ff_skate_pond")
        self.assertIn("Dread under 25", out)
        self.assertIn("Dread is 25 now.", out)
        g.player.dread = 24
        say_at(g, "ff_skate_pond", "south")
        self.assertEqual(g.room_id, "ff_ice_cellars")

    def test_the_steady_heart_alone_is_not_enough(self):
        g = ff_game()
        g.player.dread = 0
        say_at(g, "ff_skate_pond", "south")
        self.assertEqual(g.room_id, "ff_skate_pond")

    def test_the_annex_hatch_is_shut_until_the_great_lantern_is_lit(self):
        g = ff_game()
        out = say_at(g, "ff_ice_cellars", "down")
        self.assertEqual(g.room_id, "ff_ice_cellars")
        self.assertIn("light the Great Lantern in the Wintering Square", out)
        g.flags["beacon_" + FROSTFAIR] = True
        say_at(g, "ff_ice_cellars", "down")
        self.assertEqual(g.room_id, "ff_below_stair")

    def test_every_lock_message_says_what_it_needs(self):
        needs = {("gate", "w"): "beacon", ("hearth_stall", "e"): "Joss", ("ff_skate_pond", "s"): "cellar-key",
                 ("ff_ice_cellars", "d"): "Great Lantern", ("ff_lamp_row", "n"): "Ringmaster",
                 ("ff_great_gate", "w"): "Lending Posts"}
        for (rid, d), word in needs.items():
            self.assertIn(word, ROOMS[rid]["locks"][d]["msg"], (rid, d))

    def test_the_locked_doors_are_not_offered_as_suggestions(self):
        g = ff_game()
        g.room_id = "ff_great_gate"
        self.assertFalse(any(cmd == "west" for _, cmd, _ in g.suggestions()))


# ============================================================================ the Ringmaster
class RingmasterTests(unittest.TestCase):
    def test_the_carousel_fight_is_the_ringmaster_alone_and_gives_the_key_once(self):
        g = ff_game()
        fights = Fights(g, "win")
        say_at(g, "ff_skate_pond", "west")
        self.assertEqual(fights.calls, [["ff_ringmaster"]])
        self.assertTrue(g.flags["ff_ringmaster_dead"])
        self.assertEqual(g.player.inventory["ff_wardens_key"], 1)
        with quiet():
            events.after_fixed(g, "ff_ringmaster_dead")
        self.assertEqual(g.player.inventory["ff_wardens_key"], 1)

    def test_two_gems_once(self):
        g = ff_game()
        before = g.player.gems
        with quiet():
            events.after_fixed(g, "ff_ringmaster_dead")
            events.after_fixed(g, "ff_ringmaster_dead")
        self.assertEqual(g.player.gems, before + 2)
        self.assertTrue(g.flags["ff_gems_ringmaster"])

    def test_the_ringmaster_carries_the_booth_key_and_the_light_heart(self):
        d = {i for i, c in ENEMIES["ff_ringmaster"]["drops"] if c == 1.0}
        self.assertEqual(d, {"hollow_core", "ff_rime", "essence_light", "core_heart_light"})
        self.assertEqual(sum(1 for i, _ in ENEMIES["ff_ringmaster"]["drops"] if i == "hollow_core"), 2)
        self.assertEqual(sum(1 for i, _ in ENEMIES["ff_ringmaster"]["drops"] if i == "ff_rime"), 3)

    def test_the_boss_tips(self):
        self.assertIn("elite", areas.collect("BOSS_TIPS")["ff_carousel"])
        self.assertIn("Keep 40 or more oil", navigation.boss_tip("ff_wintering"))


# ============================================================================ Hobb
class HobbSceneTests(unittest.TestCase):
    def go(self, g, outcome, answers=("1",)):
        calls = []

        def fake(ids, intro=None, **kw):
            calls.append(ids)
            return outcome
        g.fight = fake
        g.room_id = "ff_wintering"
        ui.io.script = list(answers)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            ff.ENTER["ff_wintering"](g, True)
        return calls, flat(buf.getvalue())

    def test_stepping_back_is_free_and_starts_no_fight(self):
        g = ff_game()
        calls, out = self.go(g, "win", answers=["0"])
        self.assertEqual(calls, [])
        self.assertEqual(g.room_id, "ff_great_gate")
        self.assertFalse(g.flags.get("ff_lampmaster_dead"))
        self.assertEqual(g.flags.get("deaths_ff_lampmaster", 0), 0)
        self.assertIn("Power", out)
        self.assertIn("The stronger he is, the more he pays.", out)
        self.assertIn("Admission is one story or one coin", out)

    def test_the_second_meeting_has_the_other_prologue(self):
        g = ff_game()
        self.go(g, "win", answers=["0"])
        _, out = self.go(g, "win", answers=["0"])
        self.assertIn("Still open, friend", out)
        self.assertNotIn("Admission is", out)

    def test_winning_sets_the_flag_and_remembers_the_power(self):
        g = ff_game()
        calls, out = self.go(g, "win")
        self.assertTrue(calls[0][0].startswith("ff_lampmaster@"))
        self.assertTrue(g.flags["ff_lampmaster_dead"])
        self.assertIn(g.flags["power_ff_lampmaster"], range(1, 101))
        self.assertIn("Tell Marit I held it", out)
        self.assertIn("light", out)

    def test_fleeing_puts_you_back_and_he_does_not_follow(self):
        g = ff_game()
        _, out = self.go(g, "fled")
        self.assertEqual(g.room_id, "ff_great_gate")
        self.assertIn("He does not follow.", out)

    def test_dying_twice_lowers_the_ceiling_to_fifty_five_and_a_win_clears_it(self):
        g = ff_game()
        self.go(g, "dead")
        self.assertEqual(g.flags["deaths_ff_lampmaster"], 1)
        _, out = self.go(g, "dead")
        self.assertEqual(g.flags["deaths_ff_lampmaster"], 2)
        self.assertIn("gentler", out)
        _, out = self.go(g, "win", answers=["0"])
        self.assertIn("The Fair holds back", out)
        self.assertIn("lowered the ceiling to 55", out)
        for _ in range(40):
            self.assertLessEqual(powerroll.roll(g, "ff_lampmaster")[0], 55)
        self.go(g, "win")
        self.assertNotIn("deaths_ff_lampmaster", g.flags)

    def test_a_beaten_lamp_master_does_not_come_back(self):
        g = ff_game()
        g.flags["ff_lampmaster_dead"] = True
        self.assertFalse(ff.ENTER["ff_wintering"](g, False))

    def test_hobb_scales_with_the_roll_and_can_be_fled(self):
        weak, strong = powerroll.scaled("ff_lampmaster", 10), powerroll.scaled("ff_lampmaster", 90)
        self.assertLess(ENEMIES[weak]["hp"], ENEMIES[strong]["hp"])
        from lamplighter.combat import Combat
        self.assertFalse(Combat(ff_game(), [powerroll.scaled("ff_lampmaster", 50)]).no_flee)

    def test_the_band_gems_are_given_once_and_not_burned_by_a_weak_first_win(self):
        g = ff_game()
        before = g.player.gems
        with quiet():
            ff._hobb_won(g, 10)                         # Faltering: no gems, and the once-only flag stays free
        self.assertEqual(g.player.gems, before)
        self.assertFalse(g.flags.get("ff_gems_band"))
        with quiet():
            ff._hobb_won(g, 70)                         # Roused: 1 gem
            ff._hobb_won(g, 95)                         # Ablaze later: nothing more
        self.assertEqual(g.player.gems, before + 1)
        self.assertTrue(g.flags["ff_gems_band"])

    def test_an_ablaze_first_win_gives_two_gems(self):
        g = ff_game()
        before = g.player.gems
        with quiet():
            ff._hobb_won(g, 95)
        self.assertEqual(g.player.gems, before + 2)

    def test_the_first_kill_gems_come_from_the_boss_tag(self):
        g = ff_game()
        from lamplighter.entities import Enemy
        eid = powerroll.scaled("ff_lampmaster", 30)
        before = g.player.gems
        with quiet():
            g.on_kill(Enemy(eid, ENEMIES[eid]))
        self.assertEqual(g.player.gems, before + 3)


# ============================================================================ the beacon, the thaw and the annex
class BeaconTests(unittest.TestCase):
    def lit_ready(self):
        g = ff_game()
        g.flags["ff_lampmaster_dead"] = True
        g.room_id = "ff_wintering"
        return g

    def test_it_cannot_be_lit_while_hobb_holds_the_square(self):
        g = ff_game()
        g.room_id = "ff_wintering"
        run(g, "light")
        self.assertFalse(g.flags.get("beacon_" + FROSTFAIR))

    def test_lighting_it_lights_all_thirteen_rooms_and_none_of_the_annex(self):
        g = self.lit_ready()
        before = g.player.oil
        out = flat(run(g, "light"))
        self.assertTrue(g.flags["beacon_" + FROSTFAIR])
        self.assertEqual(before - g.player.oil, 30)
        mine = [rid for rid, r in ROOMS.items() if r["region"] == FROSTFAIR]
        self.assertEqual(len(mine), 13)
        for rid in mine:
            self.assertFalse(g.is_dark(rid), rid)
        for rid, r in ROOMS.items():
            if r["region"] == BELOW:
                self.assertTrue(g.is_dark(rid), rid)
        self.assertIn("For a moment nothing happens.", out)
        self.assertNotIn("great iron bowl", out)

    def test_the_thaw_is_told_in_order_and_sets_its_flag(self):
        g = self.lit_ready()
        out = flat(run(g, "light"))
        self.assertTrue(g.flags["ff_thaw"])
        self.assertLess(out.index("For a moment nothing happens."), out.index("six hundred lamps"))
        self.assertIn("It is spring.", out)
        self.assertIn("ice on Maeve's pump cracks and runs", out)

    def test_the_lit_fair_is_safe_to_rest_in_anywhere_and_the_annex_is_not(self):
        g = self.lit_ready()
        run(g, "light")
        g.room_id = "ff_carousel"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)
        g.room_id = "ff_below_hall"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, 1)

    def test_the_annex_post_can_be_lit_and_then_rested_at(self):
        g = ff_game()
        g.flags["beacon_" + FROSTFAIR] = True
        out = say_at(g, "ff_below_stair", "light")
        self.assertTrue(g.flags["lit_ff_below_stair"])
        self.assertIn("never lit", out)
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)

    def test_the_lit_fair_has_no_ambushes_but_the_annex_still_does(self):
        g = self.lit_ready()
        run(g, "light")
        fights = Fights(g, "win")
        g.cooldown = {}
        for rid in ("ff_lamp_row", "ff_skate_pond", "ff_great_gate"):
            g.room_id = rid
            for _ in range(40):
                g.maybe_encounter()
        self.assertEqual(fights.calls, [])
        g.room_id = "ff_below_pool"
        for _ in range(40):
            g.cooldown = {}
            g.maybe_encounter()
        self.assertTrue(fights.calls)

    def test_dying_at_the_fair_gate_wakes_you_by_dunmores_stove(self):
        g = ff_game()
        g.last_rest = "ff_fair_gate"
        g.player.gold = 100
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            g.death()
        self.assertEqual(g.room_id, "ff_fair_gate")
        out = flat(buf.getvalue())
        self.assertIn("Dunmore", out)
        self.assertIn("Third night of the Fair", out)
        self.assertIn("lighter by 50 gold", out)

    def test_the_fair_gate_is_a_safe_place_to_rest(self):
        g = ff_game()
        g.room_id = "ff_fair_gate"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)
        self.assertEqual(g.last_rest, "ff_fair_gate")

    def test_dying_after_the_beacon_wakes_you_at_the_great_lantern(self):
        g = self.lit_ready()
        run(g, "light")
        self.assertEqual(g.last_rest, "ff_wintering")
        with quiet():
            g.death()
        self.assertEqual(g.room_id, "ff_wintering")

    def test_the_signal_stair_is_reached_only_through_the_boss_room(self):
        incoming = [(rid, d) for rid, r in ROOMS.items() for d, dest in r["exits"].items()
                    if dest == "ff_signal_stair" and rid.startswith("ff_")]
        self.assertEqual([rid for rid, _ in incoming], ["ff_wintering"])
        self.assertTrue(ROOMS["ff_signal_stair"]["no_dealer"])


# ============================================================================ the Dealer
class DealerTests(unittest.TestCase):
    def seats(self):
        return [r for r in dealer.seats(5) if ROOMS[r]["region"] == FROSTFAIR]

    def test_four_seats_in_the_frostfair_and_none_in_the_annex(self):
        self.assertEqual(self.seats(), ["ff_frost_road", "ff_great_gate", "ff_lending_tent", "ff_skate_pond"])
        self.assertFalse([r for r in dealer.seats(5) if ROOMS[r]["region"] == BELOW])

    def test_he_only_sits_here_once_the_court_is_lit(self):
        g = new_game()
        for day in range(30):
            self.assertIsNone(dealer.room_for(g, 5, day))
        g.flags["beacon_Ember Court"] = True
        seen = {dealer.room_for(g, 5, day) for day in range(60)}
        self.assertTrue(seen)
        self.assertLessEqual(seen, set(self.seats()))
        self.assertGreater(len(seen), 1)

    def test_the_lit_fair_has_no_dark_left_for_him(self):
        g = ff_game()
        g.flags.update({"lit_" + rid: True for rid, r in ROOMS.items() if r["region"] == FROSTFAIR})
        for day in range(30):
            self.assertNotIn(dealer.room_for(g, 5, day), self.seats())


# ============================================================================ Hollowmere reacts
class HollowmereTests(unittest.TestCase):
    def test_the_courts_beacon_is_answered(self):
        g = new_game()
        g.flags["completed"] = True
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            events.after_beacon(g, "Ember Court")
        self.assertTrue(g.flags["ff_signal_seen"])
        out = flat(buf.getvalue())
        self.assertLess(out.index("The whole Court is lit"), out.index("a second light answers"))
        self.assertIn("lantern held up very high", out)
        self.assertIn("Hesk will want to know", out)

    def test_hesk_has_news_and_a_topic_until_he_has_told_it(self):
        g = new_game()
        g.flags["completed"] = True
        g.flags["hesk_met"] = True
        self.assertFalse(npcs.has_news(g, "hesk"))
        g.flags["ff_signal_seen"] = True
        self.assertTrue(npcs.has_news(g, "hesk"))
        out = say_at(g, "gate", "talk hesk", answers=["3", "0"])
        self.assertIn("It's not winter, it's wanting.", out)
        self.assertTrue(g.flags["ff_hesk_told"])
        self.assertFalse(npcs.has_news(g, "hesk"))
        self.assertEqual(ff.hesk_topics(g), [])

    def test_a_save_that_lit_the_court_before_m6_still_gets_the_frost_story(self):
        g = ff_game()                                        # the Court's beacon is lit, ff_signal_seen was never set
        self.assertNotIn("ff_signal_seen", g.flags)
        g.flags["hesk_met"] = True
        self.assertTrue(npcs.has_news(g, "hesk"))
        self.assertEqual([label for label, _ in ff.hesk_topics(g)], ["Ask about the frost on the gate"])
        self.assertIn("The pump froze solid last night", areas.rumours(g)[0])
        out = say_at(g, "gate", "talk hesk", answers=["3", "0"])
        self.assertIn("It's not winter, it's wanting.", out)
        self.assertFalse(npcs.has_news(g, "hesk"))

    def test_hesk_tells_the_thaw_version_after_the_beacon(self):
        g = ff_game()
        g.flags.update({"hesk_met": True, "ff_signal_seen": True, "ff_hesk_told": True, "ff_thaw": True})
        out = say_at(g, "gate", "talk hesk", answers=["3", "0"])
        self.assertIn("I almost cried at my own gate.", out)
        self.assertEqual(ff.hesk_topics(g), [])

    def test_the_rumours_follow_the_story(self):
        g = new_game()
        self.assertEqual(ff.RUMOURS(g), [])
        g.flags["ff_signal_seen"] = True
        self.assertIn("The pump froze solid last night", ff.RUMOURS(g)[0])
        g.flags["ff_thaw"] = True
        self.assertIn("paper lanterns on the Hearth Stall", ff.RUMOURS(g)[0])
        town.state(g)["built"].append("ff_fair_stall")
        self.assertEqual(ff.RUMOURS(g), [])
        self.assertTrue(set(ff.RUMOURS(g)) <= set(areas.rumours(g)))

    def test_odo_sells_rime_once_hobb_is_dead(self):
        g = ff_game()
        self.assertNotIn("ff_rime", npcs.stock_for(g, "odo"))
        g.flags["ff_lampmaster_dead"] = True
        self.assertIn("ff_rime", npcs.stock_for(g, "odo"))
        self.assertEqual(npcs.price("ff_rime"), 70)

    def test_odo_can_be_bought_from_for_rime(self):
        g = ff_game()
        g.flags["ff_lampmaster_dead"] = True
        g.flags["reeve_dead"] = True
        town.state(g)["built"].append("salvage_stall")
        g.player.gold = 500
        items = npcs.stock_for(g, "odo")
        idx = items.index("ff_rime") + 1
        say_at(g, "salvage_stall", "talk odo", answers=["1", "1", str(idx), "0", "0", "0"])
        self.assertEqual(g.player.inventory.get("ff_rime"), 1)
        self.assertEqual(g.player.gold, 430)


# ============================================================================ objectives
class ObjectiveTests(unittest.TestCase):
    def test_the_main_chain(self):
        g = ff_game()
        g.flags["queen_dead"] = g.flags["steward_dead"] = True
        g.set_quest("main", "done", quiet=True)
        first = lambda: next(o for o in navigation.objectives(g) if not o["side"])
        self.assertEqual(first()["room"], "ff_frost_road")
        g.visited.add("ff_frost_road")
        self.assertEqual(first()["room"], "ff_midway")
        self.assertIn("(0 of 3)", first()["text"])
        g.flags["lit_ff_midway"] = True
        self.assertEqual(first()["room"], "ff_lamp_row")
        self.assertIn("(1 of 3)", first()["text"])
        g.flags["lit_ff_lamp_row"] = g.flags["lit_ff_sculptors_row"] = True
        self.assertEqual(first()["room"], "ff_wintering")
        self.assertIn("Face the Lamp-Master", first()["text"])
        g.flags["ff_lampmaster_dead"] = True
        self.assertIn("Light the Great Lantern", first()["text"])
        g.flags["beacon_" + FROSTFAIR] = True
        mine = [o for o in navigation.objectives(g) if not o["side"] and o["room"].startswith("ff_")]
        self.assertEqual(mine, [])                                  # a lit Fair asks for nothing more

    def test_nothing_is_offered_before_the_courts_beacon(self):
        g = new_game()
        g.flags["completed"] = True
        self.assertFalse([o for o in navigation.objectives(g) if o["room"].startswith("ff_")])

    def test_the_side_objectives(self):
        g = ff_game()
        g.visited.add("ff_fair_gate")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertIn("Ringmaster of Rime", texts["ff_carousel"])
        g.flags["ff_ringmaster_dead"] = True
        g.player.add_item("ff_cellar_key")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertNotIn("ff_carousel", texts)
        self.assertIn("Ice Cellars", texts["ff_skate_pond"])
        g.visited.add("ff_ice_cellars")
        g.flags["ff_lampmaster_dead"] = True
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertNotIn("ff_skate_pond", texts)
        self.assertIn("Ask her, then see Joss", texts["ff_wardens_booth"])
        town.invite(g, "ff_fair_stall")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertIn("yard", texts)
        town.state(g)["built"].append("ff_fair_stall")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertNotIn("yard", texts)

    def test_the_first_visit_to_the_frost_road_is_told_once(self):
        g = ff_game()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertFalse(events.on_enter(g, "ff_frost_road", True))
            self.assertFalse(events.on_enter(g, "ff_frost_road", False))
        self.assertEqual(flat(buf.getvalue()).count("The air stops being air."), 1)


# ============================================================================ people
class DunmoreTests(unittest.TestCase):
    def test_he_is_at_the_fair_gate_and_sells_supplies(self):
        g = ff_game()
        g.room_id = "ff_fair_gate"
        self.assertIn("ff_dunmore", g.present_npcs())
        g.player.gold = 100
        say_at(g, "ff_fair_gate", "talk dunmore", answers=["1", "1", "4", "0", "0", "0"])
        self.assertEqual(g.player.inventory.get("ff_cider"), 1)
        self.assertEqual(g.player.gold, 60)

    def test_his_shop_has_the_fair_lights(self):
        for iid in ("ff_cider", "ff_fairlight", "firepot", "smokebomb", "tonic", "honeycake", "strong_draught", "oil"):
            self.assertIn(iid, npcs.stock_for(ff_game(), "ff_dunmore"))

    def test_the_fair_the_posts_and_the_booth(self):
        g = ff_game()
        out = say_at(g, "ff_fair_gate", "talk dunmore", answers=["2", "3", "4", "0"])
        self.assertIn("Two coins, or one story.", out)
        self.assertIn("Great Lantern's gone on a little holiday", out)
        self.assertIn("The Cider Post, the Row Post, and the Sculptors'", out)
        self.assertIn("Someone's keeping a stove lit up there", out)

    def test_after_the_thaw_he_keeps_the_booth(self):
        g = ff_game()
        g.flags["ff_thaw"] = True
        out = say_at(g, "ff_fair_gate", "talk dunmore", answers=["0"])
        self.assertIn("Closing time, is it?", out)
        self.assertIn("It's a good booth.", out)
        out = say_at(g, "ff_fair_gate", "talk dunmore", answers=["0"])
        self.assertNotIn("Closing time", out)


class MaritTests(unittest.TestCase):
    def setUp(self):
        self.t = [86400.0 * 20000]
        clock.set_clock(lambda: self.t[0])

    def tearDown(self):
        clock.set_clock(None)

    def booth(self):
        g = ff_game()
        g.room_id = "ff_wardens_booth"
        return g

    def test_the_first_talk_gives_the_cellar_key_once(self):
        g = self.booth()
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertIn("He'd have knocked.", out)
        self.assertEqual(g.player.inventory["ff_cellar_key"], 1)
        say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertEqual(g.player.inventory["ff_cellar_key"], 1)

    def test_the_truth_about_aldric(self):
        g = self.booth()
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["1", "1", "0"])      # Aldric, the truth
        self.assertIn("he was only gone", out)
        self.assertTrue(g.flags["ff_marit_told"])

    def test_the_kind_lie_about_aldric(self):
        g = self.booth()
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["1", "2", "0"])      # Aldric, the kindness
        self.assertIn("Let him walk.", out)
        self.assertTrue(g.flags["ff_marit_told"])

    def test_walking_away_from_the_aldric_question_does_not_answer_it(self):
        g = self.booth()
        say_at(g, "ff_wardens_booth", "talk marit", answers=["1", "0", "0"])
        self.assertFalse(g.flags.get("ff_marit_told"))

    def test_hobb_and_the_lantern(self):
        g = self.booth()
        g.flags["ff_marit_told"] = True
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["1", "2", "0"])      # Hobb, then the Lantern
        self.assertIn("couldn't put a thing down", out)
        self.assertIn("six hundred households", out)

    def test_telling_her_hobb_held_it(self):
        g = self.booth()
        g.flags.update({"ff_marit_told": True, "ff_lampmaster_dead": True})
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["3", "0"])
        self.assertIn("You can go home, love.", out)
        self.assertTrue(g.flags["ff_marit_hobb"])

    def test_the_hobb_topic_waits_for_hobbs_death_and_goes_once_told(self):
        g = self.booth()
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertNotIn("Tell her Hobb held it", out)
        self.assertNotIn("come to Hollowmere", out)
        g.flags["ff_lampmaster_dead"] = True
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertIn("Tell her Hobb held it", out)
        self.assertIn("Ask her to come to Hollowmere", out)
        g.flags["ff_marit_hobb"] = True
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertNotIn("Tell her Hobb held it", out)

    def test_she_has_news_until_everything_is_done(self):
        g = ff_game()
        self.assertTrue(npcs.has_news(g, "ff_marit"))
        g.flags["ff_marit_met"] = True
        self.assertFalse(npcs.has_news(g, "ff_marit"))
        g.flags["ff_lampmaster_dead"] = True
        self.assertTrue(npcs.has_news(g, "ff_marit"))
        town.invite(g, "ff_fair_stall")
        self.assertFalse(npcs.has_news(g, "ff_marit"))
        g.flags["ff_thaw"] = True
        self.assertTrue(npcs.has_news(g, "ff_marit"))
        g.flags["ff_flame_given"] = True
        self.assertFalse(npcs.has_news(g, "ff_marit"))

    def test_the_given_flame_comes_after_the_thaw_and_only_once_across_a_call_back(self):
        g = self.booth()
        g.flags["ff_marit_met"] = True
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertNotIn("given_flame", out)
        self.assertFalse(g.player.has_item("ff_given_flame"))
        g.flags.update({"ff_lampmaster_dead": True, "ff_thaw": True})
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertIn("That's not a loan.", out)
        self.assertEqual(g.player.inventory["ff_given_flame"], 1)
        self.assertTrue(g.flags["ff_flame_given"])
        # the Wizard's call-back clears the boss; the flame is spent (the smiths take it) and must not come twice
        g.flags.pop("ff_lampmaster_dead")
        g.player.remove_item("ff_given_flame")
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertNotIn("That's not a loan.", out)
        self.assertFalse(g.player.has_item("ff_given_flame"))
        g.flags["ff_lampmaster_dead"] = True
        say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertFalse(g.player.has_item("ff_given_flame"))

    def test_the_flame_is_not_duplicated_when_still_held(self):
        g = self.booth()
        g.flags.update({"ff_marit_met": True, "ff_thaw": True, "ff_lampmaster_dead": True})
        say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        g.flags.pop("ff_flame_given")                        # even if the flag were lost, the key is not doubled
        say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertEqual(g.player.inventory["ff_given_flame"], 1)

    def build_stall(self, g):
        g.flags["joss_met"] = True
        g.player.gold = 1500
        g.player.add_item("ff_rime", 8)
        g.player.add_item("cinder", 6)
        say_at(g, "yard", "talk joss", answers=["1", "0"])
        self.t[0] += 41 * 60
        town.update(g)

    def test_inviting_her_then_joss_then_she_moves_to_the_stall(self):
        g = self.booth()
        g.flags.update({"ff_marit_met": True, "ff_lampmaster_dead": True})
        self.assertIn("ff_marit", g.present_npcs())
        # the options are Aldric, Hobb, Lantern, Held, Invite (Trade comes with the stall)
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["5", "0"])
        self.assertIn("A market? With stalls?", out)
        self.assertTrue(town.is_invited(g, "ff_fair_stall"))
        self.assertIn("ff_fair_stall", town.available(g))
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["5", "0"])
        self.assertIn("Tell Joss, in the yard on Market Row.", out)
        self.build_stall(g)
        self.assertTrue(town.is_built(g, "ff_fair_stall"))
        self.assertEqual(g.player.gold, 300)
        g.room_id = "ff_wardens_booth"
        self.assertNotIn("ff_marit", g.present_npcs())
        g.room_id = "ff_stall"
        self.assertIn("ff_marit", g.present_npcs())
        say_at(g, "hearth_stall", "east")
        self.assertEqual(g.room_id, "ff_stall")

    def test_the_stall_pays_rent(self):
        g = self.booth()
        town.invite(g, "ff_fair_stall")
        self.build_stall(g)
        self.assertGreaterEqual(town.rent_rate(g), 14)

    def test_the_town_summary_names_her_properly(self):
        g = self.booth()
        town.invite(g, "ff_fair_stall")
        self.build_stall(g)
        text = " ".join(town.summary_lines(g))
        self.assertIn("Marit Ostrand", text)
        self.assertNotIn("Ff_Marit", text)

    def stall_game(self):
        g = ff_game()
        g.flags["ff_marit_met"] = True
        town.state(g)["built"].append("ff_fair_stall")
        return g

    def test_the_daily_candle_comes_once_per_day(self):
        g = self.stall_game()
        out = say_at(g, "ff_stall", "talk marit", answers=["0"])
        self.assertIn("Day's candle.", out)
        self.assertEqual(g.player.inventory["ff_fairlight"], 1)
        self.assertEqual(g.flags["ff_gift_day"], dealer.today())
        out = say_at(g, "ff_stall", "talk marit", answers=["0"])
        self.assertNotIn("Day's candle.", out)
        self.assertEqual(g.player.inventory["ff_fairlight"], 1)
        self.t[0] += 86400
        say_at(g, "ff_stall", "talk marit", answers=["0"])
        self.assertEqual(g.player.inventory["ff_fairlight"], 2)

    def test_the_stall_sells_fair_lights_and_cider(self):
        g = self.stall_game()
        g.flags["ff_gift_day"] = dealer.today()
        g.player.gold = 200
        say_at(g, "ff_stall", "talk marit", answers=["1", "1", "1", "0", "0", "0"])      # trade, buy, first ware
        self.assertEqual(g.player.inventory.get("ff_fairlight"), 1)
        self.assertEqual(g.player.gold, 145)
        self.assertEqual(npcs.stock_for(g, "ff_marit"),
                         ["ff_fairlight", "ff_cider", "oil", "essence_ice", "essence_light", "honeycake"])

    def test_the_fairlight_calms_the_heart_enough_for_the_cellars(self):
        g = ff_game()
        g.player.dread = 60
        g.player.add_item("ff_fairlight")
        run(g, "use fairlight")
        self.assertEqual(g.player.dread, 20)


class RegressionTests(unittest.TestCase):
    """Defects found in review."""

    def test_marit_trades_only_once_her_stall_is_built(self):
        g = ff_game()
        g.flags["ff_marit_met"] = True
        self.assertEqual(npcs.stock_for(g, "ff_marit"), [])
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertNotIn("Trade", out)
        out = say_at(g, "ff_wardens_booth", "trade", answers=["1", "0", "0"])           # the shop command in her booth
        self.assertNotIn("Fairlight", out)
        self.assertNotIn("Cider", out)
        for iid in ("ff_fairlight", "ff_cider", "essence_ice", "essence_light"):
            self.assertNotIn(iid, npcs.stock_for(g, "ff_marit"))
        town.state(g)["built"].append("ff_fair_stall")
        self.assertEqual(npcs.stock_for(g, "ff_marit"), ff.MARIT_WARES)
        out = say_at(g, "ff_stall", "talk marit", answers=["0"])
        self.assertIn("Trade", out)

    def test_the_first_meeting_stove_is_not_cold(self):
        g = ff_game()
        g.room_id = "ff_wardens_booth"
        out = say_at(g, "ff_wardens_booth", "talk marit", answers=["0"])
        self.assertNotIn("cold stove", out)
        self.assertIn("small stove", out)

    def test_every_feature_of_every_room_can_be_examined(self):
        # the built-in 'x lantern' and 'x lamp' answer for the player's own lantern and shadow a feature of that name
        for rid in [r for r in ROOMS if r.startswith("ff_")]:
            for keys, text in ROOMS[rid]["features"].items():
                aliases = keys.split("|")
                self.assertFalse({"lantern", "lamp"} & set(aliases) and len(aliases) == 1, (rid, keys))
                g = ff_game()
                reached = False
                for alias in aliases:
                    if alias in ("lantern", "lamp"):
                        continue
                    out = say_at(g, rid, "x " + alias)
                    # a room item of that name may answer first, which is not a defect
                    if flat(text)[:40] in out or g.resolve(alias):
                        reached = True
                        break
                self.assertTrue(reached, (rid, keys))

    def test_the_great_lantern_and_the_booth_lamp_can_be_read(self):
        out = say_at(ff_game(), "ff_wintering", "x great lantern")
        self.assertIn("Its base is a bowl, empty and cold.", out)
        out = say_at(ff_game(), "ff_wardens_booth", "x thimble")
        self.assertIn("No bigger than a thimble. Burning.", out)
        self.assertNotIn("nothing special", say_at(ff_game(), "ff_wardens_booth", "x stove"))
        self.assertNotIn("nothing special", say_at(ff_game(), "ff_wardens_booth", "x cot"))

    def test_the_move_tells_read_as_sentences_after_the_enemy_name(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            moves = list(e.get("moves", []))
            for ph in e.get("phases", []):
                moves += ph.get("moves", [])
            for m in moves:
                if m.get("tell"):
                    self.assertNotIn(m["tell"].split()[0], ("its", "the", "his", "her", "their", "a"), (eid, m["name"]))
        tells = {m["name"]: m["tell"] for eid in ENEMY_IDS for m in ENEMIES[eid].get("moves", []) if m.get("tell")}
        for ph in ENEMIES["ff_ringmaster"].get("phases", []) + ENEMIES["ff_lampmaster"].get("phases", []):
            tells.update({m["name"]: m["tell"] for m in ph.get("moves", []) if m.get("tell")})
        self.assertTrue(tells["Gallop"].startswith("rears"))
        self.assertTrue(tells["Music Box Gutter"].startswith("falters"))
        self.assertTrue(tells["Shatter"].startswith("begins to crack"))
        self.assertTrue(tells["Merry-Go-Round"].startswith("sets the horses"))
        self.assertTrue(tells["Whiteout"].startswith("makes the lamps"))

    def test_the_lamp_pole_desc_is_world_text(self):
        desc = ITEMS["ff_lamp_pole"]["desc"]
        self.assertNotIn("Dealer", desc)
        self.assertNotIn("forge", desc)

    def test_the_booth_has_one_lamp_and_marit_wears_it(self):
        self.assertNotIn("hand-lamp", ROOMS["ff_wardens_booth"]["desc"])
        self.assertIn("thimble", npcs.NPCS["ff_marit"]["desc"])

    def test_a_walk_over_the_real_exits_reaches_all_seventeen_rooms(self):
        """Every door taken by the movement command itself, with every lock satisfied and every boss already beaten."""
        g = ff_game()
        g.flags.update({"beacon_" + FROSTFAIR: True, "ff_lampmaster_dead": True, "ff_ringmaster_dead": True,
                        "lit_ff_midway": True, "lit_ff_lamp_row": True, "lit_ff_sculptors_row": True})
        g.player.add_item("ff_wardens_key")
        g.player.add_item("ff_cellar_key")
        town.state(g)["built"].append("ff_fair_stall")
        Fights(g, "win")
        seen, queue = {"gate", "hearth_stall"}, deque(["gate", "hearth_stall"])
        while queue:
            rid = queue.popleft()
            for d, dest in ROOMS[rid]["exits"].items():
                if not (dest.startswith("ff_") or (rid.startswith("ff_") and dest in ("gate", "hearth_stall"))):
                    continue
                g.player.dread = 0
                g.player.oil = g.player.max_oil
                say_at(g, rid, d)
                self.assertEqual(g.room_id, dest, (rid, d))
                if dest not in seen:
                    seen.add(dest)
                    queue.append(dest)
        self.assertEqual(set(ROOM_IDS) - seen, set())


class RegistrationTests(unittest.TestCase):
    def test_the_hooks_are_registered_under_real_ids(self):
        self.assertIn("ff_wintering", areas.collect("ENTER"))
        self.assertIn("ff_frost_road", areas.collect("ENTER"))
        self.assertIn("Ember Court", areas.collect("AFTER_BEACON"))
        self.assertIn(FROSTFAIR, areas.collect("AFTER_BEACON"))
        self.assertIn("ff_ringmaster_dead", areas.collect("AFTER_FIXED"))
        self.assertIn(("ff_great_gate", "w"), areas.collect("UNLOCK"))
        self.assertEqual(areas.collect("PRICES")["ff_rime"], 70)
        self.assertIn("hesk", areas.merged("TOPICS"))
        self.assertIn("hesk", areas.merged("EXTRA_NEWS"))
        self.assertIn("odo", areas.merged("SELLS"))

    def test_the_npc_entries_are_complete(self):
        for nid in ("ff_dunmore", "ff_marit"):
            spec = npcs.NPCS[nid]
            self.assertTrue(spec["name"] and spec["aliases"] and spec["desc"])
            self.assertIn(nid, npcs.STOCK)
        self.assertEqual(npcs.NPCS["ff_marit"]["where"](new_game()), None)


if __name__ == "__main__":
    unittest.main()
