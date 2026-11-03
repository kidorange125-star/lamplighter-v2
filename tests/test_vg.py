"""M6 package vg: the Vigil (ring 5, area B), its annex and Hale's loft. See docs/M6-SPEC.md section 10."""
import contextlib
import io
import unittest
from collections import deque

from lamplighter import areas, clock, dealer, events, navigation, npcs, powerroll, sim, spells, town, ui, validate
from lamplighter.areas import vg
from lamplighter.combat import Combat
from lamplighter.content import BUILDINGS, ENEMIES, ITEMS, REGION_INFO, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, quiet_ui, run

VIGIL = "The Vigil"
CELLARS = "The Waking Cellars"
FROSTFAIR = "The Frostfair"

# the ids of docs/M6-SPEC.md section 18 for this package
ROOM_IDS = ["vg_ladder", "vg_porters_lodge", "vg_great_court", "vg_library", "vg_heliograph", "vg_orrery_hall",
            "vg_dormitory", "vg_reckoning_room", "vg_mirror_gallery", "vg_camera_obscura", "vg_chapel",
            "vg_lens_cupboard", "vg_lens_stair", "vg_eye", "vg_loft", "vg_cellar_stair", "vg_cellar_hall",
            "vg_cellar_cells"]
ENEMY_IDS = ["vg_brother", "vg_sentinel", "vg_glare", "vg_star", "vg_blind_spot", "vg_cellar_dead", "vg_orrery",
             "vg_prior_eye"]
ITEM_IDS = ["vg_starglass", "vg_nightcap", "vg_clear_draught", "vg_star_plate", "vg_lens_key", "vg_receipt",
            "vg_given_flame", "vg_sixfold_chart", "vg_unsleeping_eye", "vg_astrolabe_rod", "vg_nightcloak"]
SEATS = ["vg_dormitory", "vg_great_court", "vg_ladder", "vg_library", "vg_mirror_gallery", "vg_reckoning_room"]


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def flat(text):
    """Printed text is wrapped to the terminal: compare it as one line."""
    return " ".join(text.split())


def vg_game(**kw):
    """A player past the story with both earlier beacons lit, in the Vigil's level range, full of oil."""
    g = new_game(**kw)
    g.flags["completed"] = True
    g.flags["beacon_Ember Court"] = True
    g.flags["beacon_" + FROSTFAIR] = True
    g.player.level = 12
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


def enter(g, room, first, answers=()):
    """Run an area ENTER hook with scripted menu answers; returns (took over the room, printed text)."""
    ui.io.script = list(answers)
    g.room_id = room
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        took = vg.ENTER[room](g, first)
    return took, flat(buf.getvalue())


# ============================================================================ content
class ContentTests(unittest.TestCase):
    def test_every_id_of_the_register_exists(self):
        for rid in ROOM_IDS:
            self.assertIn(rid, ROOMS)
        for eid in ENEMY_IDS:
            self.assertIn(eid, ENEMIES)
        for iid in ITEM_IDS:
            self.assertIn(iid, ITEMS)
        for nid in ("vg_tick", "vg_hale"):
            self.assertIn(nid, npcs.NPCS)
            self.assertTrue(hasattr(npcs, "talk_" + nid))
        self.assertIn("vg_almanac", BUILDINGS)

    def test_fourteen_field_rooms_three_annex_rooms_and_the_loft(self):
        self.assertEqual(sum(1 for r in ROOMS.values() if r["region"] == VIGIL), 14)
        self.assertEqual(sum(1 for r in ROOMS.values() if r["region"] == CELLARS), 3)
        self.assertEqual(ROOMS["vg_loft"]["region"], "Hollowmere")
        self.assertEqual(len([rid for rid in ROOMS if rid.startswith("vg_")]), 18)

    def test_the_regions_are_ring_five_and_the_annex_has_no_dealer(self):
        a, b = REGION_INFO[VIGIL], REGION_INFO[CELLARS]
        self.assertEqual((a["ring"], b["ring"]), (5, 5))
        self.assertEqual((a["levels"], b["levels"]), ("11-12", "12"))
        self.assertTrue(a["dealer"])
        self.assertEqual(a["dealer_after"], "beacon_" + FROSTFAIR)
        self.assertIs(b["dealer"], False)

    def test_every_room_has_a_description_and_features(self):
        for rid in ROOM_IDS:
            self.assertTrue(ROOMS[rid]["desc"], rid)
            self.assertTrue(ROOMS[rid]["features"], rid)

    def test_no_hollow_is_weak_to_light_in_any_stance_either(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            weak = list(e["weak"]) + [w for st in e.get("attune", {}).get("stances", []) for w in st["weak"]]
            if "hollow" in e["tags"]:
                self.assertNotIn("light", weak, eid)
        self.assertEqual([e for e in ENEMY_IDS if "hollow" in ENEMIES[e]["tags"]], ["vg_blind_spot"])

    def test_every_heavy_or_charge_move_has_a_tell_and_every_enemy_a_desc(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            self.assertTrue(e["desc"], eid)
            moves = list(e["moves"]) + list(e.get("extra_moves", {}).values())
            moves += [m for ph in e.get("phases", []) for m in ph["moves"]]
            for m in moves:
                if m["kind"] in ("heavy", "charge"):
                    self.assertTrue(m.get("tell"), "%s %s" % (eid, m["name"]))

    def test_every_charge_move_has_its_follow_up(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            moves = list(e["moves"]) + [m for ph in e.get("phases", []) for m in ph["moves"]]
            for m in moves:
                if m["kind"] == "charge":
                    self.assertIn(m["then"], e["extra_moves"], eid)
                    self.assertEqual(e["extra_moves"][m["then"]]["kind"], "heavy")

    def test_encounter_groups_have_at_most_two_and_enough_singles(self):
        for rid in ROOM_IDS:
            groups = ROOMS[rid].get("enc", {}).get("groups", [])
            if not groups:
                continue
            self.assertTrue(all(len(g) <= 2 for g, _ in groups), rid)
            single = sum(w for g, w in groups if len(g) == 1)
            self.assertGreaterEqual(single * 100, 55 * sum(w for _, w in groups), rid)

    def test_the_area_check_is_clean(self):
        self.assertEqual(vg.CHECK(), [])
        self.assertFalse([e for e in areas.check() if e.startswith("vg:")])

    def test_the_validator_has_nothing_to_say_about_this_area(self):
        mine = [p for p in validate.validate() if "vg_" in p or VIGIL in p or CELLARS in p]
        self.assertEqual(mine, [])

    def test_the_eye_is_a_queen_shaped_boss_with_a_roll_and_two_phases(self):
        e = ENEMIES["vg_prior_eye"]
        # Queen x1.8 is 1386 / 83; the real Eye was retuned against the sim to 1175 / 70 (inside +-30%)
        self.assertTrue(1386 * 0.7 <= e["hp"] <= 1386 * 1.3 and 83 * 0.7 <= e["atk"] <= 83 * 1.3)
        self.assertEqual((e["hp"], e["atk"]), (1175, 70))
        self.assertEqual([p["at"] for p in e["phases"]], [0.66, 0.33])
        self.assertEqual(len(e["roll"]["flavour"]), 5)
        self.assertEqual(e["roll"]["pron"], {"subj": "it", "obj": "it", "poss": "its"})
        self.assertEqual(e["roll"]["place"], VIGIL)
        self.assertIn("boss", e["tags"])
        self.assertNotIn("hollow", e["tags"])
        self.assertFalse(e["roll"]["story"])
        self.assertEqual({b["item"] for b in e["roll"]["bonus"]},
                         {"vg_unsleeping_eye", "hollow_core", "vg_starglass", "essence_shadow"})
        self.assertEqual(e["weak"], ["shadow", "earth"])
        self.assertEqual(e["resist"], ["light", "fire"])

    def test_the_eyes_every_win_drops(self):
        drops = [i for i, c in ENEMIES["vg_prior_eye"]["drops"] if c == 1.0]
        self.assertEqual(sorted(drops), sorted(["hollow_core"] * 2 + ["vg_starglass"] * 3 + ["essence_earth"] * 2 +
                                               ["essence_shadow"] * 2 + ["core_heart_shadow", "core_heart_light",
                                                                          "core_heart_water"]))

    def test_the_orrery_is_an_elite_with_three_stances_and_one_phase(self):
        o = ENEMIES["vg_orrery"]
        self.assertIn("elite", o["tags"])
        self.assertNotIn("boss", o["tags"])
        self.assertEqual(o["attune"]["every"], 2)
        self.assertEqual([s["name"] for s in o["attune"]["stances"]], ["Sun-line", "Moon-line", "Star-line"])
        self.assertEqual((o["weak"], o["resist"]), (o["attune"]["stances"][0]["weak"],
                                                    o["attune"]["stances"][0]["resist"]))
        self.assertEqual(len(o["phases"]), 1)
        names = [m["name"] for m in o["phases"][0]["moves"]]
        self.assertEqual(names[-1], "Precession")
        self.assertEqual(len(names), len(o["moves"]) + 1)
        self.assertEqual(sum(1 for i, c in o["drops"] if i == "hollow_core"), 2)
        self.assertEqual(sum(1 for i, c in o["drops"] if i == "vg_starglass"), 3)
        self.assertNotIn("vg_lens_key", [i for i, _ in o["drops"]])        # the key is given by the hook

    def test_the_stances_cover_every_pair_of_elements_a_loadout_needs(self):
        stances = ENEMIES["vg_orrery"]["attune"]["stances"]
        for pick in (({"shadow", "water"}), ({"fire", "earth"}), ({"light", "ice"})):
            self.assertTrue(any(set(s["weak"]) == pick for s in stances), pick)

    def test_the_roster_follows_the_lane(self):
        for eid in ("vg_brother", "vg_sentinel", "vg_glare", "vg_star", "vg_cellar_dead"):
            self.assertIn("fire", ENEMIES[eid]["resist"], eid)
            if eid != "vg_sentinel":
                self.assertIn("light", ENEMIES[eid]["resist"], eid)
        for eid in ("vg_brother", "vg_cellar_dead"):
            self.assertEqual(ENEMIES[eid]["weak"], ["shadow", "earth"])
        self.assertEqual(ENEMIES["vg_blind_spot"]["weak"], ["fire", "ice"])

    def test_the_two_fields(self):
        gal, eye = ROOMS["vg_mirror_gallery"]["field"], ROOMS["vg_eye"]["field"]
        self.assertEqual((gal["name"], gal["light"], gal["shadow"]), ("Hall of Mirrors", 1.25, 0.8))
        self.assertEqual((eye["name"], eye["shadow"], eye["light"]), ("Noon", 0.75, 1.25))

    def test_the_gear_is_at_the_right_tiers(self):
        self.assertEqual(ITEMS["vg_unsleeping_eye"]["rarity"], "legendary")
        self.assertEqual(ITEMS["vg_astrolabe_rod"]["rarity"], "rare")
        self.assertEqual(ITEMS["vg_nightcloak"]["rarity"], "rare")
        for iid in ("vg_receipt", "vg_given_flame", "vg_lens_key", "vg_sixfold_chart"):
            self.assertEqual(ITEMS[iid]["kind"], "key")
        self.assertEqual(ITEMS["vg_star_plate"]["kind"], "junk")
        self.assertIn("Held in trust", ITEMS["vg_receipt"]["desc"])
        self.assertEqual(ITEMS["vg_nightcap"]["use"], {"dread": -60})       # no heal: it must work at full health
        self.assertTrue(ITEMS["vg_clear_draught"]["use"]["cleanse"])

    def test_the_receipt_the_vault_and_the_cellar_floors(self):
        g = vg_game()
        self.assertIn("vg_receipt", g.room_items["vg_library"])
        self.assertEqual(g.room_items["vg_library"].count("vg_star_plate"), 2)
        obscura = g.room_items["vg_camera_obscura"]
        for iid in ("vg_sixfold_chart", "vg_astrolabe_rod", "vg_nightcloak", "relic_pulse", "core_heart_shadow",
                    "core_heart_light"):
            self.assertIn(iid, obscura)
        self.assertEqual(obscura.count("hollow_core"), 2)
        self.assertEqual(obscura.count("vg_starglass"), 4)
        self.assertEqual(g.room_items["vg_cellar_hall"].count("vg_star_plate"), 2)
        self.assertIn("strong_draught", g.room_items["vg_cellar_hall"])

    def test_every_room_is_reachable_from_the_hall_ignoring_locks(self):
        seen, queue = {"hall"}, deque(["hall"])
        while queue:
            for dest in ROOMS[queue.popleft()]["exits"].values():
                if dest not in seen:
                    seen.add(dest)
                    queue.append(dest)
        self.assertEqual(set(ROOM_IDS) - seen, set())

    def test_every_way_into_a_vault_goes_through_one_lock(self):
        for target, src, d in (("vg_lens_stair", "vg_orrery_hall", "e"), ("vg_camera_obscura", "vg_mirror_gallery", "s"),
                               ("vg_loft", "tower", "w"), ("vg_cellar_stair", "vg_great_court", "d"),
                               ("vg_ladder", "ff_signal_stair", "u")):
            ways = [(rid, dd) for rid, r in ROOMS.items() for dd, dest in r["exits"].items() if dest == target]
            locked = [(rid, dd) for rid, dd in ways if dd in ROOMS[rid].get("locks", {})]
            self.assertIn((src, d), locked, target)
        # the Eye is only reachable through the Lens Stair, which is only reachable through the locked iris
        self.assertEqual([rid for rid, r in ROOMS.items() if "vg_eye" in r["exits"].values()], ["vg_lens_stair"])
        self.assertEqual([rid for rid, r in ROOMS.items() if "vg_lens_stair" in r["exits"].values()],
                         ["vg_orrery_hall", "vg_eye"])

    def test_the_hollowmere_doors_are_attached(self):
        self.assertEqual(ROOMS["ff_signal_stair"]["exits"]["u"], "vg_ladder")
        self.assertEqual(ROOMS["vg_ladder"]["exits"]["d"], "ff_signal_stair")
        self.assertEqual(ROOMS["tower"]["exits"]["w"], "vg_loft")
        self.assertEqual(ROOMS["vg_loft"]["exits"], {"e": "tower"})
        self.assertIs(ROOMS["vg_loft"]["dark"], False)
        self.assertEqual(ROOMS["vg_great_court"]["exits"]["d"], "vg_cellar_stair")
        self.assertEqual(ROOMS["vg_cellar_stair"]["exits"]["u"], "vg_great_court")

    def test_the_building(self):
        b = BUILDINGS["vg_almanac"]
        self.assertEqual(b["room"], "vg_loft")
        self.assertEqual(b["resident"], "vg_hale")
        self.assertEqual(b["cost"], {"gold": 1600, "items": {"vg_starglass": 8, "slag": 10}})
        self.assertEqual((b["minutes"], b["steps"], b["rent"]), (45, 70, 18))
        self.assertFalse(b.get("forge_slot"))

    def test_the_rest_points_and_their_flavour(self):
        self.assertTrue(ROOMS["vg_porters_lodge"]["rest"] and ROOMS["vg_porters_lodge"]["outpost"])
        for rid in ("vg_heliograph", "vg_cellar_stair"):
            self.assertTrue(ROOMS[rid]["waypost"], rid)
            self.assertTrue(ROOMS[rid]["waypost_text"], rid)
        self.assertEqual(ROOMS["vg_eye"]["beacon_oil"], 35)
        self.assertTrue(ROOMS["vg_eye"]["beacon_text"].startswith("You pour the oil into the Signal Brazier"))
        for rid in ("vg_camera_obscura", "vg_chapel", "vg_lens_cupboard", "vg_lens_stair"):
            self.assertTrue(ROOMS[rid]["no_dealer"], rid)


# ============================================================================ locks
class LockTests(unittest.TestCase):
    def test_the_ladder_waits_for_the_great_lantern(self):
        g = new_game()
        g.flags["beacon_Ember Court"] = True
        out = say_at(g, "ff_signal_stair", "up")
        self.assertEqual(g.room_id, "ff_signal_stair")
        self.assertEqual(ROOMS["ff_signal_stair"]["locks"]["u"]["msg"][:48],
                         "The Signal Stair climbs into cloud, but its firs")
        self.assertIn("relight the Great Lantern (the beacon in the Wintering Square)", out)
        g.flags["beacon_" + FROSTFAIR] = True
        say_at(g, "ff_signal_stair", "up")
        self.assertEqual(g.room_id, "vg_ladder")

    def test_the_loft_plot_waits_for_the_building(self):
        g = vg_game()
        out = say_at(g, "tower", "west")
        self.assertEqual(g.room_id, "tower")
        self.assertIn("A vacant plot beside the Magician's Tower", out)
        self.assertIn("Joss can build a loft here once a star-reader is willing to move in.", out)
        town.state(g)["built"].append("vg_almanac")
        say_at(g, "tower", "west")
        self.assertEqual(g.room_id, "vg_loft")

    def test_the_cellar_trapdoor_waits_for_the_signal(self):
        g = vg_game()
        out = say_at(g, "vg_great_court", "down")
        self.assertEqual(g.room_id, "vg_great_court")
        self.assertIn("A trapdoor under the Court's great sundial, bolted.", out)
        self.assertIn("light the brazier under the Eye", out)
        g.flags["beacon_" + VIGIL] = True
        say_at(g, "vg_great_court", "down")
        self.assertEqual(g.room_id, "vg_cellar_stair")

    def test_the_iris_wants_the_orrerys_key(self):
        g = vg_game()
        g.flags["vg_orrery_dead"] = True                  # the key is a separate matter from the fight
        out = say_at(g, "vg_orrery_hall", "east")
        self.assertEqual(g.room_id, "vg_orrery_hall")
        self.assertIn("The Lens Stair is shut behind a bronze iris", out)
        self.assertIn("Defeat it.", out)
        g.player.add_item("vg_lens_key")
        say_at(g, "vg_orrery_hall", "east")
        self.assertEqual(g.room_id, "vg_lens_stair")

    def test_the_felt_door_wants_a_shadow_book(self):
        g = vg_game()
        g.player.spells = ["book_fire"]
        out = say_at(g, "vg_mirror_gallery", "south")
        self.assertEqual(g.room_id, "vg_mirror_gallery")
        self.assertIn("equip a Shadow spell book (type 'spells') and try again.", out)
        self.assertIn("Equipped books: Fire", out)
        g.player.spells = []
        self.assertIn("Equipped books: none", say_at(g, "vg_mirror_gallery", "south"))
        g.player.spells = ["book_light", "book_shadow"]
        out = say_at(g, "vg_mirror_gallery", "south")
        self.assertEqual(g.room_id, "vg_camera_obscura")
        self.assertIn("a darkness so complete it feels like being forgiven", out)
        self.assertTrue(g.flags["vg_obscura_open"])

    def test_the_felt_door_stays_open_once_opened(self):
        g = vg_game()
        g.player.spells = ["book_shadow"]
        say_at(g, "vg_mirror_gallery", "south")
        g.player.spells = ["book_fire"]                    # the book is swapped out; the door remembers
        say_at(g, "vg_camera_obscura", "north")
        self.assertEqual(g.room_id, "vg_mirror_gallery")
        say_at(g, "vg_mirror_gallery", "south")
        self.assertEqual(g.room_id, "vg_camera_obscura")

    def test_every_lock_message_says_what_it_needs(self):
        needs = {("ff_signal_stair", "u"): "Great Lantern", ("tower", "w"): "Joss",
                 ("vg_great_court", "d"): "brazier", ("vg_orrery_hall", "e"): "Orrery's key",
                 ("vg_mirror_gallery", "s"): "Shadow spell book"}
        for (rid, d), word in needs.items():
            self.assertIn(word, ROOMS[rid]["locks"][d]["msg"], (rid, d))

    def test_the_locked_doors_are_not_offered_as_suggestions(self):
        g = vg_game()
        g.room_id = "vg_great_court"
        self.assertFalse(any(cmd == "down" for _, cmd, _ in g.suggestions()))


# ============================================================================ the mercy scene
class ChapelTests(unittest.TestCase):
    def test_the_first_visit_asks_and_leaving_repeats_the_scene(self):
        g = vg_game()
        for _ in range(2):
            took, out = enter(g, "vg_chapel", True, answers=["3"])
            self.assertTrue(took)
            self.assertIn("pressing his own eyelids shut with two thumbs", out)
            self.assertFalse(g.flags.get("vg_chapel_done"))
            self.assertFalse(g.flags.get("vg_brother_slept"))
        self.assertEqual(g.player.gold, new_game().player.gold)

    def test_sitting_with_him_pays_at_least_what_the_fight_would(self):
        g = vg_game()
        g.player.dread = 80
        gold, gems = g.player.gold, g.player.gems
        took, out = enter(g, "vg_chapel", True, answers=["1"])
        self.assertTrue(took)
        self.assertIn("for the first time in fifty years something in this building is asleep", out)
        self.assertTrue(g.flags["vg_brother_slept"] and g.flags["vg_chapel_done"] and g.flags["vg_gems_chapel"])
        self.assertEqual(g.player.dread, 30)
        self.assertEqual(g.player.gold - gold, 180)
        self.assertEqual(g.player.gems - gems, 1)
        self.assertEqual(g.player.inventory["vg_star_plate"], 1)
        # the fight is two Brothers: 148 to 216 gold and 370 xp
        lo, hi = ENEMIES["vg_brother"]["gold"]
        self.assertTrue(2 * lo <= 180 <= 2 * hi)
        self.assertIn("+%d xp" % (2 * ENEMIES["vg_brother"]["xp"]), out)

    def test_dread_does_not_go_below_nothing(self):
        g = vg_game()
        g.player.dread = 20
        enter(g, "vg_chapel", True, answers=["1"])
        self.assertEqual(g.player.dread, 0)

    def test_it_pays_once_only(self):
        g = vg_game()
        enter(g, "vg_chapel", True, answers=["1"])
        gold, gems = g.player.gold, g.player.gems
        took, out = enter(g, "vg_chapel", False)
        self.assertFalse(took)
        self.assertIn("A grey habit on the altar steps, folded as if slept in.", out)
        self.assertEqual((g.player.gold, g.player.gems), (gold, gems))
        self.assertEqual(g.player.inventory["vg_star_plate"], 1)

    def test_the_gem_is_once_ever_even_if_the_scene_were_replayed(self):
        g = vg_game()
        g.flags["vg_gems_chapel"] = True
        gems = g.player.gems
        enter(g, "vg_chapel", True, answers=["1"])
        self.assertEqual(g.player.gems, gems)

    def test_the_fight_path_is_two_brothers_and_ends_the_scene_on_a_win(self):
        g = vg_game()
        fights = Fights(g, "win")
        took, out = enter(g, "vg_chapel", True, answers=["2"])
        self.assertTrue(took)
        self.assertEqual(fights.calls, [["vg_brother", "vg_brother"]])
        self.assertTrue(g.flags["vg_chapel_done"])
        self.assertFalse(g.flags.get("vg_brother_slept"))
        took, out = enter(g, "vg_chapel", False)
        self.assertFalse(took)
        self.assertNotIn("A grey habit", out)               # nobody slept here

    def test_a_lost_fight_leaves_the_scene_to_be_played_again(self):
        g = vg_game()
        Fights(g, "dead")
        enter(g, "vg_chapel", True, answers=["2"])
        self.assertFalse(g.flags.get("vg_chapel_done"))
        took, out = enter(g, "vg_chapel", False, answers=["3"])
        self.assertTrue(took)
        self.assertIn("pressing his own eyelids shut", out)

    def test_the_menu_cannot_be_cancelled_into_a_skip(self):
        g = vg_game()
        _, out = enter(g, "vg_chapel", True, answers=["", "x", "1"])
        self.assertTrue(g.flags["vg_chapel_done"])

    def test_walking_in_runs_the_scene_through_the_engine(self):
        g = vg_game()
        g.visited.add("vg_reckoning_room")
        ui.io.script = ["1"]
        g.room_id = "vg_reckoning_room"
        g.cooldown = {rid: 10 ** 6 for rid in ROOMS}
        with contextlib.redirect_stdout(io.StringIO()):
            g.move("s")
        self.assertEqual(g.room_id, "vg_chapel")
        self.assertTrue(g.flags["vg_brother_slept"])

    def test_the_mercy_path_is_a_side_objective_until_resolved(self):
        g = vg_game()
        g.visited.add("vg_reckoning_room")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertIn("Sit with him?", texts["vg_chapel"])
        g.flags["vg_chapel_done"] = True
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertNotIn("vg_chapel", texts)


# ============================================================================ the Orrery
class OrreryTests(unittest.TestCase):
    def test_the_fight_is_the_orrery_alone_and_gives_the_key_and_gems_once(self):
        g = vg_game()
        fights = Fights(g, "win")
        before = g.player.gems
        say_at(g, "vg_mirror_gallery", "north")
        self.assertEqual(fights.calls, [["vg_orrery"]])
        self.assertTrue(g.flags["vg_orrery_dead"])
        self.assertEqual(g.player.inventory["vg_lens_key"], 1)
        self.assertEqual(g.player.gems, before + 2)
        with quiet():
            events.after_fixed(g, "vg_orrery_dead")
        self.assertEqual(g.player.inventory["vg_lens_key"], 1)
        self.assertEqual(g.player.gems, before + 2)

    def test_the_text_of_the_stopping_sky(self):
        g = vg_game()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            events.after_fixed(g, "vg_orrery_dead")
        out = flat(buf.getvalue())
        self.assertIn("The Orrery slows, ring by ring, to a stop.", out)
        self.assertIn("a held breath being let go by a hundred people at once", out)

    def test_it_is_an_elite_you_cannot_run_from(self):
        g = vg_game()
        self.assertTrue(Combat(g, ["vg_orrery"]).no_flee)

    def test_stances_change_every_two_rounds(self):
        g, c = self.fight()
        e = c.enemies[0]
        c.shift_stances(announce=False)
        seen = []
        for _ in range(12):
            c.round += 1
            c.shift_stances(announce=False)
            seen.append(e.stance)
        self.assertEqual(seen, [0, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 2])

    def fight(self, spells=()):
        quiet_ui()
        g = Game(seed=1)
        g.player = sim.build_player(cls="wayfarer", level=12, spells=list(spells))
        g.room_id = "vg_orrery_hall"
        g.cooldown["vg_orrery_hall"] = 10 ** 6
        return g, Combat(g, ["vg_orrery"], policy=lambda c: c.suggest()[0])

    def test_the_stance_swaps_weak_and_resist(self):
        g, c = self.fight()
        e = c.enemies[0]
        c.shift_stances(announce=False)
        self.assertEqual((e.weak, e.resist), (["shadow", "water"], ["light", "fire"]))
        c.round = 3
        c.shift_stances(announce=False)
        self.assertEqual((e.weak, e.resist), (["fire", "earth"], ["shadow", "ice"]))
        c.round = 5
        c.shift_stances(announce=False)
        self.assertEqual((e.weak, e.resist), (["light", "ice"], ["earth", "water"]))

    def test_the_stance_announcements_use_the_orrerys_own_words(self):
        g, c = self.fight()
        c.shift_stances(announce=False)
        said = []
        from unittest import mock
        with mock.patch("lamplighter.combat.say", side_effect=lambda t="": said.append(t)):
            c.round = 3
            c.shift_stances()
            c.round = 5
            c.shift_stances()
        self.assertEqual(said, ["{hollow}The rings swing to the Moon-line.{/}",
                                "{hollow}The rings settle on the Star-line.{/}"])
        self.assertEqual(ENEMIES["vg_orrery"]["attune"]["stances"][0]["msg"],
                         "{hollow}The inner rings lock to the Sun-line.{/}")

    def test_the_suggested_spell_follows_the_alignment(self):
        g, c = self.fight(spells=[("shadow", "epic"), ("fire", "epic"), ("light", "epic")])
        c.shift_stances(announce=False)
        g.player.focus = 10
        c.round = 1
        action, why = c.best_spell(c.alive)
        self.assertEqual(spells.element_of(action.item), "shadow")  # Sun-line: weak to shadow, resists light and fire
        for rnd, element in ((3, "fire"), (5, "light")):
            c.round = rnd
            c.shift_stances(announce=False)
            g.player.focus = 10
            c.spell_cd.clear()
            action, why = c.best_spell(c.alive)
            self.assertEqual(spells.element_of(action.item), element, rnd)

    def test_the_board_shows_the_next_alignment(self):
        g, c = self.fight()
        ui.io.mute = False
        self.addCleanup(setattr, ui.io, "mute", False)
        c.shift_stances(announce=False)
        c.enemies[0].choose_intent(c.rng, c.enemies)
        c.round = 1
        c.last_log = ""
        ui.io.start_capture()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            c.render()
        self.assertIn("stance: Sun-line, next: Moon-line in 2 rounds", out.getvalue())

    def test_the_boss_tip_is_found_for_the_hall(self):
        self.assertIn("changes alignment every two rounds", navigation.boss_tip("vg_orrery_hall"))


# ============================================================================ the Eye
class EyeSceneTests(unittest.TestCase):
    def go(self, g, outcome, answers=("1",)):
        calls = []

        def fake(ids, intro=None, **kw):
            calls.append(ids)
            return outcome
        g.fight = fake
        g.room_id = "vg_eye"
        ui.io.script = list(answers)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            vg.ENTER["vg_eye"](g, True)
        return calls, flat(buf.getvalue())

    def test_stepping_back_is_free_and_starts_no_fight(self):
        g = vg_game()
        calls, out = self.go(g, "win", answers=["0"])
        self.assertEqual(calls, [])
        self.assertEqual(g.room_id, "vg_lens_stair")
        self.assertFalse(g.flags.get("vg_eye_dead"))
        self.assertEqual(g.flags.get("deaths_vg_prior_eye", 0), 0)
        self.assertIn("Power", out)
        self.assertIn("The stronger it is, the more it pays.", out)
        self.assertIn("A Prior's chain hangs from the mount.", out)
        self.assertIn("Do not close your eyes.", out)

    def test_the_second_meeting_has_the_other_prologue(self):
        g = vg_game()
        self.go(g, "win", answers=["0"])
        _, out = self.go(g, "win", answers=["0"])
        self.assertIn("has not blinked since you left", out)
        self.assertNotIn("The Chamber is a drum", out)

    def test_winning_sets_the_flag_and_remembers_the_power(self):
        g = vg_game()
        calls, out = self.go(g, "win")
        self.assertTrue(calls[0][0].startswith("vg_prior_eye@"))
        self.assertTrue(g.flags["vg_eye_dead"])
        self.assertIn(g.flags["power_vg_prior_eye"], range(1, 101))
        self.assertIn("Is it dark outside?", out)
        self.assertIn("that's what it was supposed to look like", out)
        self.assertIn("the shutters of the Dome roll slowly closed", out)
        self.assertIn("light", out)

    def test_fleeing_puts_you_back_and_it_does_not_follow(self):
        g = vg_game()
        _, out = self.go(g, "fled")
        self.assertEqual(g.room_id, "vg_lens_stair")
        self.assertIn("It does not follow.", out)

    def test_dying_twice_lowers_the_ceiling_to_fifty_five_and_a_win_clears_it(self):
        g = vg_game()
        self.go(g, "dead")
        self.assertEqual(g.flags["deaths_vg_prior_eye"], 1)
        _, out = self.go(g, "dead")
        self.assertEqual(g.flags["deaths_vg_prior_eye"], 2)
        self.assertIn("gentler", out)
        _, out = self.go(g, "win", answers=["0"])
        self.assertIn("The Vigil holds back", out)
        self.assertIn("lowered the ceiling to 55", out)
        for _ in range(40):
            self.assertLessEqual(powerroll.roll(g, "vg_prior_eye")[0], 55)
        self.go(g, "win")
        self.assertNotIn("deaths_vg_prior_eye", g.flags)

    def test_a_beaten_eye_does_not_come_back(self):
        g = vg_game()
        g.flags["vg_eye_dead"] = True
        self.assertFalse(vg.ENTER["vg_eye"](g, False))

    def test_the_eye_scales_with_the_roll_and_can_be_fled(self):
        weak, strong = powerroll.scaled("vg_prior_eye", 10), powerroll.scaled("vg_prior_eye", 90)
        self.assertLess(ENEMIES[weak]["hp"], ENEMIES[strong]["hp"])
        self.assertFalse(Combat(vg_game(), [powerroll.scaled("vg_prior_eye", 50)]).no_flee)

    def test_the_band_gems_are_given_once_and_not_burned_by_a_weak_first_win(self):
        g = vg_game()
        before = g.player.gems
        with quiet():
            vg._won(g, 10)
        self.assertEqual(g.player.gems, before)
        self.assertFalse(g.flags.get("vg_gems_band"))
        with quiet():
            vg._won(g, 70)
            vg._won(g, 95)
        self.assertEqual(g.player.gems, before + 1)
        self.assertTrue(g.flags["vg_gems_band"])

    def test_an_ablaze_first_win_gives_two_gems(self):
        g = vg_game()
        before = g.player.gems
        with quiet():
            vg._won(g, 95)
        self.assertEqual(g.player.gems, before + 2)

    def test_the_first_kill_gems_come_from_the_boss_tag(self):
        g = vg_game()
        from lamplighter.entities import Enemy
        eid = powerroll.scaled("vg_prior_eye", 30)
        before = g.player.gems
        with quiet():
            g.on_kill(Enemy(eid, ENEMIES[eid]))
        self.assertEqual(g.player.gems, before + 3)

    def test_the_boss_tip(self):
        self.assertIn("Shadow and Earth books", navigation.boss_tip("vg_eye"))
        self.assertIn("Noon at Midnight", navigation.boss_tip("vg_eye"))


# ============================================================================ the beacon and the release
class BeaconTests(unittest.TestCase):
    def lit_ready(self):
        g = vg_game()
        g.flags["vg_eye_dead"] = True
        g.room_id = "vg_eye"
        return g

    def test_it_cannot_be_lit_while_the_eye_holds_the_chamber(self):
        g = vg_game()
        g.room_id = "vg_eye"
        run(g, "light")
        self.assertFalse(g.flags.get("beacon_" + VIGIL))

    def test_lighting_it_lights_all_fourteen_rooms_and_none_of_the_cellars(self):
        g = self.lit_ready()
        before = g.player.oil
        out = flat(run(g, "light"))
        self.assertTrue(g.flags["beacon_" + VIGIL])
        self.assertEqual(before - g.player.oil, 35)
        mine = [rid for rid, r in ROOMS.items() if r["region"] == VIGIL]
        self.assertEqual(len(mine), 14)
        for rid in mine:
            self.assertFalse(g.is_dark(rid), rid)
        for rid, r in ROOMS.items():
            if r["region"] == CELLARS:
                self.assertTrue(g.is_dark(rid), rid)
        self.assertIn("You pour the oil into the Signal Brazier under the Eye", out)
        self.assertNotIn("great iron bowl", out)

    def test_the_signal_is_answered_and_told_in_order(self):
        g = self.lit_ready()
        out = flat(run(g, "light"))
        self.assertTrue(g.flags["vg_signal_sent"])
        self.assertLess(out.index("touch your flame to it."), out.index("Far to the south-east"))
        self.assertIn("three flashes, the Hollowmere lamplighters' dusk signal", out)
        self.assertIn("The Vigil is released.", out)

    def test_the_lit_vigil_is_safe_to_rest_in_anywhere_and_the_cellars_are_not(self):
        g = self.lit_ready()
        run(g, "light")
        g.room_id = "vg_dormitory"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)
        g.room_id = "vg_cellar_hall"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, 1)

    def test_the_cellar_post_can_be_lit_and_then_rested_at(self):
        g = vg_game()
        g.flags["beacon_" + VIGIL] = True
        out = say_at(g, "vg_cellar_stair", "light")
        self.assertTrue(g.flags["lit_vg_cellar_stair"])
        self.assertIn("a small gold ceiling", out)
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)

    def test_the_heliograph_flashes_east_when_lit(self):
        g = vg_game()
        out = say_at(g, "vg_heliograph", "light")
        self.assertTrue(g.flags["lit_vg_heliograph"])
        self.assertIn("the first in fifty years. Nothing answers. Not yet.", out)
        self.assertNotIn("Tollroad", out)

    def test_the_lit_vigil_has_no_ambushes_but_the_cellars_still_do(self):
        g = self.lit_ready()
        run(g, "light")
        fights = Fights(g, "win")
        g.cooldown = {}
        for rid in ("vg_ladder", "vg_great_court", "vg_mirror_gallery"):
            g.room_id = rid
            for _ in range(40):
                g.maybe_encounter()
        self.assertEqual(fights.calls, [])
        g.room_id = "vg_cellar_cells"
        for _ in range(40):
            g.cooldown = {}
            g.maybe_encounter()
        self.assertTrue(fights.calls)

    def test_the_cellars_are_fought_in_the_dark_without_the_beacon_light(self):
        g = vg_game()
        self.assertTrue(g.is_dark("vg_cellar_hall"))
        self.assertTrue(g.is_dark("vg_ladder"))

    def test_dying_at_the_porters_lodge_wakes_you_in_slippers(self):
        g = vg_game()
        g.last_rest = "vg_porters_lodge"
        g.player.gold = 100
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            g.death()
        self.assertEqual(g.room_id, "vg_porters_lodge")
        out = flat(buf.getvalue())
        self.assertIn("You wake with slippers on your feet that you did not put there.", out)
        self.assertIn("'Rested,' it says. 'Warm.'", out)
        self.assertIn("lighter by 50 gold", out)

    def test_the_lodge_is_a_safe_place_to_rest(self):
        g = vg_game()
        g.room_id = "vg_porters_lodge"
        g.player.hp = 1
        run(g, "rest")
        self.assertEqual(g.player.hp, g.player.max_hp)
        self.assertEqual(g.last_rest, "vg_porters_lodge")

    def test_dying_after_the_beacon_wakes_you_at_the_eye(self):
        g = self.lit_ready()
        run(g, "light")
        self.assertEqual(g.last_rest, "vg_eye")
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            g.death()
        self.assertEqual(g.room_id, "vg_eye")
        self.assertIn("You wake at the foot of the Eye", flat(buf.getvalue()))

    def test_the_eye_chamber_is_reached_only_through_the_lens_stair(self):
        self.assertEqual([rid for rid, r in ROOMS.items() if "vg_eye" in r["exits"].values()], ["vg_lens_stair"])


# ============================================================================ the Dealer
class DealerTests(unittest.TestCase):
    def seats(self):
        return [r for r in dealer.seats(5) if ROOMS[r]["region"] == VIGIL]

    def test_six_seats_in_the_vigil_and_none_in_the_annex(self):
        self.assertEqual(self.seats(), SEATS)
        self.assertFalse([r for r in dealer.seats(5) if ROOMS[r]["region"] == CELLARS])

    def test_he_does_not_sit_here_until_the_frostfair_is_lit(self):
        g = new_game()
        g.flags["beacon_Ember Court"] = True
        for day in range(60):
            self.assertNotIn(dealer.room_for(g, 5, day), SEATS)

    def test_he_moves_to_the_vigil_once_the_frostfair_is_lit(self):
        g = vg_game()
        g.flags.update({"lit_" + rid: True for rid, r in ROOMS.items() if r["region"] == FROSTFAIR})
        seen = {dealer.room_for(g, 5, day) for day in range(80)}
        self.assertLessEqual(seen, set(SEATS))
        self.assertGreater(len(seen), 1)

    def test_the_lit_vigil_has_no_dark_left_for_him(self):
        g = vg_game()
        g.flags.update({"lit_" + rid: True for rid, r in ROOMS.items() if r["region"] in (FROSTFAIR, VIGIL)})
        for day in range(40):
            self.assertIsNone(dealer.room_for(g, 5, day))


# ============================================================================ Hollowmere reacts
class HollowmereTests(unittest.TestCase):
    def test_hesk_has_news_and_a_topic_until_he_has_told_it(self):
        g = vg_game()
        g.flags.update({"hesk_met": True, "ff_hesk_told": True, "ff_hesk_thawed": True})     # the Frostfair's own talk is done
        g.flags.pop("beacon_" + FROSTFAIR)
        self.assertFalse(npcs.has_news(g, "hesk"))
        self.assertEqual(vg.hesk_topics(g), [])
        g.flags["beacon_" + FROSTFAIR] = True
        self.assertTrue(npcs.has_news(g, "hesk"))
        out = say_at(g, "gate", "talk hesk", answers=["3", "0"])
        self.assertIn("Nobody's sleeping on the east lanes.", out)
        self.assertIn("half a drum of oil I never used", out)
        self.assertTrue(g.flags["vg_hesk_told"])
        self.assertFalse(npcs.has_news(g, "hesk"))
        self.assertEqual(vg.hesk_topics(g), [])

    def test_hesk_tells_the_sleeping_version_after_the_signal(self):
        g = vg_game()
        g.flags.update({"hesk_met": True, "vg_hesk_told": True, "vg_signal_sent": True,
                        "ff_hesk_told": True, "ff_hesk_thawed": True})
        self.assertEqual(len(vg.hesk_topics(g)), 1)
        out = say_at(g, "gate", "talk hesk", answers=["3", "0"])
        self.assertIn("First proper dusk in a month.", out)
        self.assertIn("Half the town fell asleep in the square. I let them.", out)
        self.assertEqual(vg.hesk_topics(g), [])

    def test_hesk_who_was_never_told_gets_only_the_good_news(self):
        g = vg_game()
        g.flags["vg_signal_sent"] = True
        with quiet():
            vg.hesk_topics(g)[0][1](g)
        self.assertTrue(g.flags["vg_hesk_told"] and g.flags["vg_hesk_slept"])
        self.assertEqual(vg.hesk_topics(g), [])

    def test_orrin_hears_the_signal_was_answered_once(self):
        g = vg_game()
        self.assertEqual(vg.orrin_topics(g), [])
        g.flags["vg_signal_sent"] = True
        self.assertEqual([t[0] for t in vg.orrin_topics(g)], ["Tell Orrin the signal was answered"])
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            vg.orrin_topics(g)[0][1](g)
        out = flat(buf.getvalue())
        self.assertIn("Three flashes from the Hall, I gave the order myself.", out)
        self.assertIn("Aldric, you wretched, wonderful man.", out)
        self.assertEqual(vg.orrin_topics(g), [])

    def test_orrin_offers_it_in_his_talk_menu(self):
        g = vg_game()
        g.flags["vg_signal_sent"] = True
        self.assertIn(("Tell Orrin the signal was answered"), [t[0] for t in areas.topics(g, "orrin")])

    def test_the_rumours_follow_the_story(self):
        g = new_game()
        self.assertEqual(vg.RUMOURS(g), [])
        g.flags["beacon_" + FROSTFAIR] = True
        self.assertIn("keeps thanking me for the beds", vg.RUMOURS(g)[0])
        g.flags["vg_signal_sent"] = True
        self.assertEqual(len(vg.RUMOURS(g)), 1)
        self.assertIn("Slept ten hours.", vg.RUMOURS(g)[0])
        self.assertTrue(set(vg.RUMOURS(g)) <= set(areas.rumours(g)))

    def test_odo_sells_vigil_glass_once_the_eye_is_dead(self):
        g = vg_game()
        self.assertNotIn("vg_starglass", npcs.stock_for(g, "odo"))
        g.flags["vg_eye_dead"] = True
        self.assertIn("vg_starglass", npcs.stock_for(g, "odo"))
        self.assertEqual(npcs.price("vg_starglass"), 90)

    def test_odo_can_be_bought_from_for_vigil_glass(self):
        g = vg_game()
        g.flags["vg_eye_dead"] = True
        g.flags["reeve_dead"] = True
        town.state(g)["built"].append("salvage_stall")
        g.player.gold = 500
        items = npcs.stock_for(g, "odo")
        idx = items.index("vg_starglass") + 1
        say_at(g, "salvage_stall", "talk odo", answers=["1", "1", str(idx), "0", "0", "0"])
        self.assertEqual(g.player.inventory.get("vg_starglass"), 1)
        self.assertEqual(g.player.gold, 410)


# ============================================================================ objectives
class ObjectiveTests(unittest.TestCase):
    def test_the_main_chain(self):
        g = vg_game()
        g.flags["queen_dead"] = g.flags["steward_dead"] = True
        g.flags["ff_lampmaster_dead"] = True
        g.set_quest("main", "done", quiet=True)
        first = lambda: next(o for o in navigation.objectives(g) if not o["side"] and o["room"].startswith("vg_"))
        self.assertEqual(first()["room"], "vg_ladder")
        self.assertIn("The Signal Stair is open", first()["text"])
        g.visited.add("vg_ladder")
        self.assertEqual(first()["room"], "vg_orrery_hall")
        self.assertIn("Find the Orrery's key", first()["text"])
        g.flags["vg_orrery_dead"] = True
        self.assertEqual(first()["room"], "vg_eye")
        self.assertIn("Face the Unsleeping Eye", first()["text"])
        g.flags["vg_eye_dead"] = True
        self.assertIn("Send the signal", first()["text"])
        g.flags["beacon_" + VIGIL] = True
        mine = [o for o in navigation.objectives(g) if not o["side"] and o["room"].startswith("vg_")]
        self.assertEqual(mine, [])

    def test_nothing_is_offered_before_the_frostfair_is_lit(self):
        g = new_game()
        g.flags["completed"] = True
        g.flags["beacon_Ember Court"] = True
        self.assertFalse([o for o in navigation.objectives(g) if o["room"].startswith("vg_")])

    def test_the_story_is_told_line_gives_way_to_the_vigil(self):
        g = vg_game()
        g.flags["queen_dead"] = g.flags["steward_dead"] = True
        g.set_quest("main", "done", quiet=True)
        main = [o for o in navigation.objectives(g) if not o["side"]]
        self.assertTrue(any(o["room"] == "vg_ladder" for o in main))
        self.assertFalse(any("story is told" in o["text"].lower() for o in main))

    def test_the_side_objectives(self):
        g = vg_game()
        g.visited.add("vg_mirror_gallery")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertIn("Shadow book", texts["vg_mirror_gallery"])
        g.flags["vg_obscura_open"] = True
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertNotIn("vg_mirror_gallery", texts)
        g.flags["vg_orrery_dead"] = True
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertIn("Ask him, then see Joss", texts["vg_lens_cupboard"])
        town.invite(g, "vg_almanac")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertIn("yard", texts)
        self.assertNotIn("vg_lens_cupboard", texts)
        town.state(g)["built"].append("vg_almanac")
        texts = {o["room"]: o["text"] for o in navigation.objectives(g) if o["side"]}
        self.assertNotIn("yard", texts)
        self.assertNotIn("vg_lens_cupboard", texts)

    def test_the_first_visits_are_told_once(self):
        g = vg_game()
        for rid, phrase in (("vg_ladder", "A thousand steps."), ("vg_dormitory", "Two hundred beds"),
                            ("vg_porters_lodge", "Welcome to the Vigil. Do not close your eyes.")):
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                self.assertFalse(events.on_enter(g, rid, True))
                self.assertFalse(events.on_enter(g, rid, False))
            self.assertEqual(flat(buf.getvalue()).count(phrase), 1, rid)


# ============================================================================ people
class TickTests(unittest.TestCase):
    def test_he_is_at_the_lodge_and_sells_supplies(self):
        g = vg_game()
        g.room_id = "vg_porters_lodge"
        self.assertIn("vg_tick", g.present_npcs())
        self.assertEqual(npcs.stock_for(g, "vg_tick"),
                         ["oil", "strong_draught", "vg_nightcap", "vg_clear_draught", "tonic", "firepot", "smokebomb"])
        g.player.gold = 100
        say_at(g, "vg_porters_lodge", "talk tick", answers=["1", "1", "3", "0", "0", "0"])
        self.assertEqual(g.player.inventory.get("vg_nightcap"), 1)
        self.assertEqual(g.player.gold, 40)

    def test_the_nightcap_and_the_clear_draught_do_their_work(self):
        g = vg_game()
        g.player.dread = 70
        g.player.hp = 10
        g.player.add_item("vg_nightcap")
        run(g, "use nightcap")
        self.assertEqual(g.player.dread, 10)
        self.assertEqual(g.player.hp, 10)

    def test_what_he_says_follows_the_story(self):
        g = vg_game()
        out = say_at(g, "vg_porters_lodge", "talk tick", answers=["0"])
        self.assertIn("You are speaking to me directly. That is permitted.", out)
        out = say_at(g, "vg_porters_lodge", "talk tick", answers=["0"])
        self.assertIn("Eight thousand slippers. Warm.", out)
        g.flags["vg_eye_dead"] = True
        out = say_at(g, "vg_porters_lodge", "talk tick", answers=["0"])
        self.assertIn("Would you like the lights out?", out)
        g.flags["beacon_" + VIGIL] = True
        out = say_at(g, "vg_porters_lodge", "talk tick", answers=["0"])
        self.assertIn("It will take eleven years. That is acceptable.", out)

    def test_the_two_topics(self):
        g = vg_game()
        out = say_at(g, "vg_porters_lodge", "talk tick", answers=["2", "3", "0"])
        self.assertIn("Three hundred years without a missed morning.", out)
        self.assertIn("the cupboard in the south of the Dormitory", out)
        self.assertIn("This year he did not answer.", out)


class HaleTests(unittest.TestCase):
    def setUp(self):
        self.t = [86400.0 * 20000]
        clock.set_clock(lambda: self.t[0])

    def tearDown(self):
        clock.set_clock(None)

    def cupboard(self):
        g = vg_game()
        g.flags["vg_orrery_dead"] = True
        g.room_id = "vg_lens_cupboard"
        return g

    def test_he_is_absent_until_the_orrery_falls_then_in_the_cupboard_then_the_loft(self):
        g = vg_game()
        g.room_id = "vg_lens_cupboard"
        self.assertNotIn("vg_hale", g.present_npcs())
        g.flags["vg_orrery_dead"] = True
        self.assertIn("vg_hale", g.present_npcs())
        town.state(g)["built"].append("vg_almanac")
        self.assertNotIn("vg_hale", g.present_npcs())
        g.room_id = "vg_loft"
        self.assertIn("vg_hale", g.present_npcs())
        self.assertEqual(npcs.NPCS["vg_hale"]["where"](g), "vg_loft")

    def test_where_is_nowhere_before_the_loft_stands(self):
        self.assertIsNone(npcs.NPCS["vg_hale"]["where"](new_game()))

    def test_the_first_talk_asks_if_they_are_very_angry(self):
        g = self.cupboard()
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["1", "0"])
        self.assertIn("'Are they very angry?' he says.", out)
        self.assertIn("The third night of the Vigil.", out)
        self.assertIn("You: \"You were nineteen.\"", out)
        self.assertIn("I'm the Order's last witness, and I'm a sleeper.", out)
        self.assertTrue(g.flags["vg_hale_met"])

    def test_any_of_the_three_answers_gets_the_same_reply(self):
        for k in ("1", "2", "3"):
            g = self.cupboard()
            out = say_at(g, "vg_lens_cupboard", "talk hale", answers=[k, "0"])
            self.assertIn("The universe has a sense of humour.", out)

    def test_he_has_news_until_the_signal_flame_and_the_invitation_are_done(self):
        g = self.cupboard()
        self.assertTrue(npcs.has_news(g, "vg_hale"))
        g.flags["vg_hale_met"] = True
        self.assertTrue(npcs.has_news(g, "vg_hale"))            # the Orrery is down and he is not invited
        town.invite(g, "vg_almanac")
        self.assertFalse(npcs.has_news(g, "vg_hale"))
        g.flags["vg_signal_sent"] = True
        self.assertTrue(npcs.has_news(g, "vg_hale"))
        g.flags["vg_flame_given"] = True
        self.assertFalse(npcs.has_news(g, "vg_hale"))

    def test_the_chapel_topic_waits_for_the_sleeping_brother(self):
        g = self.cupboard()
        g.flags["vg_hale_met"] = True
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertNotIn("Tell him about the Brother in the chapel", out)
        g.flags["vg_brother_slept"] = True
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["2", "0"])
        self.assertIn("Tell him about the Brother in the chapel", out)
        self.assertIn("Is it possible to be forgiven by a man in his sleep?", out)
        self.assertTrue(g.flags["vg_hale_slept"])
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertNotIn("Tell him about the Brother in the chapel", out)

    def test_the_given_flame_comes_after_the_signal_and_only_once_across_a_call_back(self):
        g = self.cupboard()
        g.flags["vg_hale_met"] = True
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertNotIn("It isn't a loan.", out)
        self.assertFalse(g.player.has_item("vg_given_flame"))
        g.flags["vg_signal_sent"] = True
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertIn("It isn't a loan.", out)
        self.assertIn("lights his tiny cupboard-candle from the Signal", out)
        self.assertEqual(g.player.inventory["vg_given_flame"], 1)
        self.assertTrue(g.flags["vg_flame_given"])
        # the Wizard's call-back clears the boss; the flame is spent (the smiths take it) and must not come twice
        g.flags.pop("vg_eye_dead", None)
        g.player.remove_item("vg_given_flame")
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertNotIn("It isn't a loan.", out)
        self.assertFalse(g.player.has_item("vg_given_flame"))
        g.flags["vg_eye_dead"] = True
        say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertFalse(g.player.has_item("vg_given_flame"))

    def test_the_flame_is_not_duplicated_when_still_held(self):
        g = self.cupboard()
        g.flags.update({"vg_hale_met": True, "vg_signal_sent": True})
        say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        g.flags.pop("vg_flame_given")                        # even if the flag were lost, the key is not doubled
        say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertEqual(g.player.inventory["vg_given_flame"], 1)

    def test_a_first_meeting_after_the_signal_still_gets_the_flame(self):
        g = self.cupboard()
        g.flags["vg_signal_sent"] = True
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["1", "0"])
        self.assertIn("'Are they very angry?'", out)
        self.assertIn("It isn't a loan.", out)
        self.assertEqual(g.player.inventory["vg_given_flame"], 1)

    def build_loft(self, g):
        g.flags["joss_met"] = True
        g.player.gold = 2000
        g.player.add_item("vg_starglass", 8)
        g.player.add_item("slag", 10)
        say_at(g, "yard", "talk joss", answers=["1", "0"])
        self.t[0] += 46 * 60
        town.update(g)

    def test_inviting_him_then_joss_then_he_moves_to_the_loft(self):
        g = self.cupboard()
        g.flags["vg_hale_met"] = True
        # the options are: Invite, Order
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["1", "0"])
        self.assertIn("A town with an east-facing window?", out)
        self.assertTrue(town.is_invited(g, "vg_almanac"))
        self.assertIn("vg_almanac", town.available(g))
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["1", "0"])
        self.assertIn("Tell Joss, in the yard on Market Row. An east window, please.", out)
        self.build_loft(g)
        self.assertTrue(town.is_built(g, "vg_almanac"))
        self.assertEqual(g.player.gold, 400)
        g.room_id = "vg_lens_cupboard"
        self.assertNotIn("vg_hale", g.present_npcs())
        g.room_id = "vg_loft"
        self.assertIn("vg_hale", g.present_npcs())
        say_at(g, "tower", "west")
        self.assertEqual(g.room_id, "vg_loft")

    def test_the_loft_pays_rent_and_the_summary_names_him_properly(self):
        g = self.cupboard()
        town.invite(g, "vg_almanac")
        self.build_loft(g)
        self.assertGreaterEqual(town.rent_rate(g), 18)
        text = " ".join(town.summary_lines(g))
        self.assertIn("Hale Teasel", text)
        self.assertNotIn("Vg_Hale", text)

    def loft_game(self):
        g = vg_game()
        g.flags.update({"vg_orrery_dead": True, "vg_hale_met": True})
        town.state(g)["built"].append("vg_almanac")
        return g

    def test_the_chart_is_read_aloud_only_in_the_loft_and_only_once(self):
        g = self.loft_game()
        out = say_at(g, "vg_loft", "talk hale", answers=["0"])
        self.assertNotIn("Show him the Sixfold Chart", out)
        g.player.add_item("vg_sixfold_chart")
        out = say_at(g, "vg_loft", "talk hale", answers=["0"])
        self.assertIn("Show him the Sixfold Chart", out)
        out = say_at(g, "vg_loft", "talk hale", answers=["3", "0"])      # Order, Almanac, Chart
        self.assertIn("This is not a star-map. It's a recipe", out)
        self.assertTrue(g.flags["vg_chart_read"])
        out = say_at(g, "vg_loft", "talk hale", answers=["0"])
        self.assertNotIn("Show him the Sixfold Chart", out)

    def test_the_chart_is_not_offered_before_the_loft_stands(self):
        g = self.cupboard()
        g.flags["vg_hale_met"] = True
        g.player.add_item("vg_sixfold_chart")
        out = say_at(g, "vg_lens_cupboard", "talk hale", answers=["0"])
        self.assertNotIn("Show him the Sixfold Chart", out)
        self.assertNotIn("Read the almanac", out)


# ============================================================================ the almanac
class AlmanacTests(unittest.TestCase):
    def read(self, g, room="vg_loft"):
        g.room_id = room
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            vg.almanac(g)
        return buf.getvalue()

    def test_it_lists_every_ring_for_today_and_tomorrow(self):
        g = vg_game()
        out = self.read(g)
        self.assertIn("Today", out)
        self.assertIn("Tomorrow", out)
        for ring in range(1, 6):
            self.assertEqual(out.count("Ring %d:" % ring), 2, ring)

    def test_it_names_the_room_each_dealer_sits_in(self):
        g = vg_game()
        out = self.read(g)
        for ring in range(1, 5):
            rid = dealer.room_for(g, ring, dealer.today())
            self.assertIn("Ring %d: %s" % (ring, ROOMS[rid]["name"]), out)
            tomorrow = dealer.room_for(g, ring, dealer.today() + 1)
            self.assertIn("Ring %d: %s" % (ring, ROOMS[tomorrow]["name"]), out)

    def test_a_dealer_in_every_ring_and_a_room_you_cannot_reach(self):
        g = new_game()
        g.flags["beacon_" + FROSTFAIR] = True              # the Vigil seats him, but the Court's road is still shut
        for ring in range(1, 6):
            self.assertIsNotNone(dealer.room_for(g, ring, dealer.today()), ring)
        out = self.read(g, "hall")
        reach = [l for l in out.splitlines() if "(you cannot reach it yet)" in l]
        self.assertTrue(reach)
        self.assertTrue(any("Ring 5" in l for l in reach), reach)
        self.assertNotIn("Ring 1: " + ROOMS[dealer.room_for(g, 1, dealer.today())]["name"] + " (you", out)
        rid = dealer.room_for(g, 5, dealer.today())
        self.assertEqual(ROOMS[rid]["region"], VIGIL)
        self.assertIsNone(navigation.find_path(g, "hall", rid))

    def test_a_lit_ring_says_so(self):
        g = vg_game()
        g.flags.update({"lit_" + rid: True for rid, r in ROOMS.items() if r["region"] in (FROSTFAIR, VIGIL)})
        out = self.read(g)
        self.assertEqual(out.count("Ring 5: nowhere (the ring is lit)"), 2)

    def test_reading_it_is_free_and_repeatable(self):
        g = vg_game()
        gold = g.player.gold
        say_at(g, "vg_loft", "talk hale", answers=["0"])
        g.flags["vg_hale_met"] = True
        town.state(g)["built"].append("vg_almanac")
        out1 = say_at(g, "vg_loft", "talk hale", answers=["2", "2", "0"])
        self.assertIn("Ring 5:", out1)
        self.assertEqual(g.player.gold, gold)


# ============================================================================ registration
class RegistrationTests(unittest.TestCase):
    def test_the_hooks_are_registered_under_real_ids(self):
        enter = areas.collect("ENTER")
        for rid in ("vg_ladder", "vg_porters_lodge", "vg_dormitory", "vg_chapel", "vg_eye"):
            self.assertIn(rid, enter)
            self.assertIn(rid, ROOMS)
        self.assertIn(VIGIL, areas.collect("AFTER_BEACON"))
        self.assertIn("vg_orrery_dead", areas.collect("AFTER_FIXED"))
        self.assertIn(("vg_mirror_gallery", "s"), areas.collect("UNLOCK"))
        self.assertEqual(areas.collect("PRICES")["vg_starglass"], 90)
        self.assertIn("hesk", areas.merged("TOPICS"))
        self.assertIn("orrin", areas.merged("TOPICS"))
        self.assertIn("hesk", areas.merged("EXTRA_NEWS"))
        self.assertIn("odo", areas.merged("SELLS"))
        self.assertEqual(set(areas.collect("BOSS_TIPS")) & {"vg_eye", "vg_orrery_hall"}, {"vg_eye", "vg_orrery_hall"})

    def test_the_npc_entries_are_complete(self):
        for nid in ("vg_tick", "vg_hale"):
            spec = npcs.NPCS[nid]
            self.assertTrue(spec["name"] and spec["aliases"] and spec["desc"])
        self.assertIn("vg_tick", npcs.STOCK)
        self.assertTrue(npcs.NPCS["vg_tick"]["shop"])
        self.assertIsNone(npcs.NPCS["vg_hale"]["where"](new_game()))

    def test_every_flag_set_by_this_package_starts_with_the_slug(self):
        import inspect
        import re
        src = inspect.getsource(vg)
        for flag in set(re.findall(r'flags\["([a-z_]+)"\]\s*=', src)):
            self.assertTrue(flag.startswith("vg_"), flag)

    def test_the_text_is_plain_ascii(self):
        import json
        import os
        base = os.path.dirname(vg.__file__)
        for rel in ("vg.py", os.path.join("..", "data", "rooms", "vg.json"),
                    os.path.join("..", "data", "enemies", "vg.json"), os.path.join("..", "data", "items", "vg.json")):
            with open(os.path.join(base, rel), encoding="utf-8") as f:
                text = f.read()
            self.assertTrue(all(ord(c) < 128 for c in text), rel)
        with open(os.path.join(base, "..", "data", "attach", "vg.json"), encoding="utf-8") as f:
            self.assertTrue(f.read().isascii())


# ============================================================================ the reviewers' findings
class ReviewFixTests(unittest.TestCase):
    def test_hale_is_not_advertised_on_the_map_while_he_hides(self):
        from lamplighter import maps
        g = vg_game()
        g.visited.add("vg_lens_cupboard")
        self.assertFalse(vg._hale_news(g))
        self.assertNotIn("!", maps.room_icons(g, "vg_lens_cupboard"))
        g.flags["vg_orrery_dead"] = True
        self.assertIn("!", maps.room_icons(g, "vg_lens_cupboard"))

    def test_the_nightcap_works_at_full_health(self):
        g = vg_game()
        g.player.dread = 80
        g.player.hp = g.player.max_hp
        g.player.add_item("vg_nightcap")
        run(g, "use nightcap")
        self.assertEqual(g.player.dread, 20)
        self.assertEqual(g.player.inventory.get("vg_nightcap", 0), 0)
        self.assertNotIn("heal", ITEMS["vg_nightcap"]["use"])
        self.assertNotIn("health", ITEMS["vg_nightcap"]["desc"].lower())

    def test_the_chart_reads_properly_when_taken(self):
        self.assertEqual(ITEMS["vg_sixfold_chart"]["name"], "Sixfold Chart")
        out = say_at(vg_game(), "vg_camera_obscura", "take all")
        self.assertIn("You take the Sixfold Chart.", out)
        self.assertNotIn("the The", out)

    def test_the_mercy_scene_announces_the_plate_once_and_dread_only_when_it_moved(self):
        g = vg_game()
        g.player.dread = 0
        _, out = enter(g, "vg_chapel", True, answers=["1"])
        self.assertEqual(out.count("Star Plate"), 1)
        self.assertNotIn("Dread -", out)
        g = vg_game()
        g.player.dread = 80
        _, out = enter(g, "vg_chapel", True, answers=["1"])
        self.assertIn("Dread -50", out)

    def test_the_chapel_shows_the_slept_state_when_examined(self):
        g = vg_game()
        enter(g, "vg_chapel", True, answers=["3"])           # leave him be: the awake text stands
        before = say_at(g, "vg_chapel", "examine altar")
        self.assertNotIn("Nobody kneels at it now", before)
        enter(g, "vg_chapel", True, answers=["1"])
        out = say_at(g, "vg_chapel", "examine altar", "examine habit")
        self.assertIn("Nobody kneels at it now", out)
        self.assertIn("A grey habit on the altar steps, folded as if slept in.", out)
        self.assertNotIn("If a Brother", out)

    def test_tick_is_an_it_in_the_trade_menu_too(self):
        out = say_at(vg_game(), "vg_porters_lodge", "talk tick", answers=["0"])
        self.assertIn("Trade (supplies for the Vigil)", out)
        self.assertNotIn("he sells", out)

    def test_the_band_gems_are_pluralised(self):
        g = vg_game()
        with quiet() as buf:
            vg._won(g, 70)
        self.assertIn("+1 gem ", flat(buf.getvalue()))
        self.assertNotIn("+1 gems", flat(buf.getvalue()))
        g = vg_game()
        with quiet() as buf:
            vg._won(g, 95)
        self.assertIn("+2 gems", flat(buf.getvalue()))

    def test_the_descriptions_do_not_repeat_their_names_and_the_key_says_iris(self):
        for eid in ("vg_orrery", "vg_prior_eye"):
            e = ENEMIES[eid]
            self.assertFalse(e["desc"].lower().startswith(e["name"].lower()), eid)
            self.assertFalse(e["desc"].lower().startswith(e["name"].lower().replace("the ", "", 1)), eid)
        self.assertIn("iris", ITEMS["vg_lens_key"]["desc"])
        self.assertNotIn("shutter", ITEMS["vg_lens_key"]["desc"])

    def test_the_eye_can_be_travelled_to_by_the_name_a_player_would_type(self):
        g = vg_game()
        g.visited.update(["vg_eye", "vg_chapel"])
        self.assertEqual(navigation.match_place(g, "eye chamber"), ["vg_eye"])
        self.assertIn("vg_eye", navigation.match_place(g, "eye"))
        self.assertIn("Eye", ROOMS["vg_eye"]["name"])

    def test_the_ordinary_pairs_are_not_harder_than_the_heavy_pair_target(self):
        # the Armillary Sentinel + Fallen Star room was 25% at Legendary (spec 14.4: a heavy pair is about 38 +-10)
        for rid in ("vg_reckoning_room", "vg_mirror_gallery"):
            self.assertTrue(ROOMS[rid]["enc"]["groups"])
        self.assertLessEqual(ENEMIES["vg_sentinel"]["atk"], 62)
        for grp, w in ROOMS["vg_reckoning_room"]["enc"]["groups"]:
            if sorted(grp) == ["vg_sentinel", "vg_star"]:
                self.assertLessEqual(w, 2)

    def test_the_orrery_with_no_books_lands_on_the_calibration_target(self):
        # spec 14.5, "none" row: Ultra 32, Legendary 59, Godlike 91 (+-10); the seeded sim is deterministic
        def mean(rarity):
            tot = 0.0
            for cls, weapon in (("warden", "saltsteel_saber"), ("wayfarer", "saltsteel_saber"),
                                ("ashblade", "ashwood_rod")):
                def b(cls=cls, weapon=weapon):
                    return sim.maxed(cls, 12, weapon, "hauberk", rarity, items={"draught": 3, "strong_draught": 3,
                                                                              "oil": 3},
                                     lantern={"shroud": True, "trim": True, "lens": True})
                tot += 100.0 * sim.win_rate(["vg_orrery"], sim.suggested, n=30, builder=b,
                                            room="vg_orrery_hall")["win"]
            return tot / 3
        self.assertTrue(22 <= mean("ultra") <= 42)
        self.assertTrue(49 <= mean("legendary") <= 69)
        self.assertTrue(81 <= mean("godlike") <= 100)


if __name__ == "__main__":
    unittest.main()
