"""M6 package rl: the Reedlight (docs/M6-SPEC.md section 7), the Saltmarsh's marsh lighthouse."""
import contextlib
import io
import json
import unittest
from collections import deque

from lamplighter import areas, dealer, events, npcs, spells, validate
from lamplighter.content import ENEMIES, ITEMS, REGION_INFO, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, run

RL_ROOMS = ["rl_causeway", "rl_sluice", "rl_tower_foot", "rl_lantern_room", "rl_cottage", "rl_oilhouse"]
RL_ENEMIES = ["rl_lampman", "rl_heronling", "rl_heron"]
RL_ITEMS = ["rl_heronplume_coat", "rl_keepers_pole", "rl_lens_shard", "rl_tower_key", "rl_receipt"]


def at(g, rid):
    g.room_id = rid
    g.visited.add(rid)
    g.cooldown.update({r: 10 ** 6 for r in ROOMS})      # no random ambushes on the way
    return g


def with_book(g, element):
    g.player.spells = ["book_" + element]
    return g


def capture(fn, *a):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fn(*a)
    return out.getvalue()


def flat(text):
    """Printed text is word-wrapped; compare it with the line breaks folded away."""
    return " ".join(text.split())


def talk_oskar_topic(g, topic_number=2):
    """Talk to Oskar and pick the n-th menu entry once, then leave. Returns what was printed."""
    g.flags["oskar_met"] = True
    at(g, "docks")
    return flat(run(g, "talk oskar", answers=[str(topic_number), "0"]))


class ShapeTests(unittest.TestCase):
    def test_the_region_rooms_enemies_and_items_exist(self):
        info = REGION_INFO["The Reedlight"]
        self.assertEqual((info["ring"], info["levels"]), (2, "5-6"))
        self.assertIs(info["dealer"], False)
        self.assertEqual(sorted(r for r, x in ROOMS.items() if x["region"] == "The Reedlight"), sorted(RL_ROOMS))
        for eid in RL_ENEMIES:
            self.assertIn(eid, ENEMIES)
        for iid in RL_ITEMS:
            self.assertIn(iid, ITEMS)

    def test_every_room_has_a_description_and_features(self):
        for rid in RL_ROOMS:
            self.assertTrue(ROOMS[rid]["desc"], rid)
            self.assertTrue(ROOMS[rid]["features"], rid)

    def test_no_hollow_enemy_is_weak_to_light(self):
        for eid in RL_ENEMIES:
            e = ENEMIES[eid]
            if "hollow" in e["tags"]:
                self.assertNotIn("light", e.get("weak", []), eid)

    def test_every_heavy_move_has_a_tell(self):
        for eid in RL_ENEMIES:
            e = ENEMIES[eid]
            for m in e["moves"] + [m for ph in e.get("phases", []) for m in ph["moves"]]:
                self.assertTrue(m.get("tell"), "%s %s" % (eid, m["name"]))

    def test_encounter_groups_are_at_most_two(self):
        for rid in RL_ROOMS:
            for group, _ in ROOMS[rid].get("enc", {}).get("groups", []):
                self.assertLessEqual(len(group), 2, rid)

    def test_the_heron_phases_at_half_and_adds_beacon_stare(self):
        h = ENEMIES["rl_heron"]
        self.assertEqual(len(h["phases"]), 1)
        self.assertEqual(h["phases"][0]["at"], 0.5)
        self.assertEqual({m["name"] for m in h["phases"][0]["moves"]} - {m["name"] for m in h["moves"]}, {"Beacon Stare"})
        self.assertNotIn("roll", h)

    def test_the_area_has_no_dealer_seat(self):
        self.assertFalse(set(RL_ROOMS) & set(dealer.seats(2)))

    def test_the_validator_and_the_area_checks_have_nothing_to_say_about_it(self):
        mine = [e for e in validate.validate() if "rl_" in e or "Reedlight" in e or "bog_lights" in e]
        self.assertEqual(mine, [])
        self.assertEqual([e for e in areas.check() if e.startswith("rl:")], [])

    def test_all_six_rooms_are_reachable_from_the_hall_ignoring_locks(self):
        seen, queue = {"hall"}, deque(["hall"])
        while queue:
            for dest in ROOMS[queue.popleft()]["exits"].values():
                if dest not in seen:
                    seen.add(dest)
                    queue.append(dest)
        self.assertTrue(set(RL_ROOMS) <= seen)

    def test_every_lock_can_be_opened_with_what_the_area_itself_gives(self):
        """Stands in for the fuzzer's reachability check, which cannot see the key chain: walk the Reedlight
        graph honouring the tower lock. The key's source (the oil-house) must need no key; the lamp room needs it."""
        def reach(have_key):
            seen, queue = {"rl_causeway"}, deque(["rl_causeway"])
            while queue:
                rid = queue.popleft()
                for d, dest in ROOMS[rid]["exits"].items():
                    lock = ROOMS[rid].get("locks", {}).get(d)
                    if lock and lock.get("item") and not have_key:
                        continue
                    if dest not in seen and ROOMS[dest]["region"] == "The Reedlight":
                        seen.add(dest)
                        queue.append(dest)
            return seen
        self.assertEqual(ROOMS["bog_lights"]["locks"]["s"]["element"], ["fire", "light"])
        without_key = reach(False)
        self.assertIn("rl_oilhouse", without_key)
        self.assertIn("rl_tower_foot", without_key)
        self.assertNotIn("rl_lantern_room", without_key)
        self.assertEqual(reach(True), set(RL_ROOMS))

    def test_each_cross_region_exit_is_the_one_attach_door(self):
        self.assertEqual(ROOMS["bog_lights"]["exits"]["s"], "rl_causeway")
        self.assertEqual(ROOMS["rl_causeway"]["exits"]["n"], "bog_lights")


class FogLockTests(unittest.TestCase):
    MSG = ("South of the Bog Lights a wall of white fog stands on the water, thick enough to lean on. Fog burns off "
           "in light. Equip a Fire or Light spell book (type 'spells') and try again. Mirelle, in the Magician's "
           "Tower, sells Common books for gold.")

    def test_the_lock_names_what_it_needs_and_where_to_get_it(self):
        lock = ROOMS["bog_lights"]["locks"]["s"]
        self.assertEqual(lock["element"], ["fire", "light"])
        self.assertEqual(lock["remember"], "rl_fog_burned")
        self.assertEqual(lock["msg"], self.MSG)

    def test_without_a_book_the_fog_holds_and_the_status_line_says_so(self):
        g = at(new_game(), "bog_lights")
        run(g, "south")
        self.assertEqual(g.room_id, "bog_lights")
        self.assertIn(self.MSG, g.notices)
        self.assertIn("{grey}Equipped books: none{/}", g.notices)
        self.assertFalse(g.flags.get("rl_fog_burned"))

    def test_a_book_of_the_wrong_element_does_not_help(self):
        g = with_book(at(new_game(), "bog_lights"), "water")
        run(g, "south")
        self.assertEqual(g.room_id, "bog_lights")
        self.assertIn("{grey}Equipped books: Water{/}", g.notices)

    def test_a_fire_book_parts_the_fog_with_its_line_and_remembers(self):
        g = with_book(at(new_game(), "bog_lights"), "fire")
        out = flat(run(g, "south"))
        self.assertEqual(g.room_id, "rl_causeway")
        self.assertTrue(g.flags["rl_fog_burned"])
        self.assertIn("The fog does not lift, it parts, as a curtain parts for someone it recognises.", out)

    def test_a_light_book_works_too(self):
        g = with_book(at(new_game(), "bog_lights"), "light")
        run(g, "south")
        self.assertEqual(g.room_id, "rl_causeway")

    def test_swapping_the_book_out_afterwards_does_not_close_the_way(self):
        g = with_book(at(new_game(), "bog_lights"), "fire")
        run(g, "south")
        run(g, "north")
        g.player.spells = []
        out = run(g, "south")
        self.assertEqual(g.room_id, "rl_causeway")
        self.assertNotIn("parts, as a curtain", out)          # the unlock line is only told once

    def test_the_way_back_north_is_never_locked(self):
        g = at(new_game(), "rl_causeway")
        run(g, "north")
        self.assertEqual(g.room_id, "bog_lights")


class OilhouseAndTowerTests(unittest.TestCase):
    def test_the_oilhouse_fight_is_two_lampmen_with_the_intro(self):
        fixed = ROOMS["rl_oilhouse"]["fixed"]
        self.assertEqual((fixed["flag"], fixed["enemies"]), ("rl_oilhouse_dead", ["rl_lampman", "rl_lampman"]))
        self.assertIn("They are still on shift.", fixed["intro"])

    def test_the_tower_door_needs_the_key_and_says_where_it_is(self):
        g = at(new_game(), "rl_tower_foot")
        run(g, "north")
        self.assertEqual(g.room_id, "rl_tower_foot")
        self.assertIn("The tower door is locked. The keeper kept his key where he kept the oil, in the oil-house "
                      "south of the sluice, and the oil-house has guests.", g.notices)
        g.give("rl_tower_key", quiet=True)
        g.notices.clear()
        g.player.hp = 5                                                # hurt, so the boss warning is shown
        out = flat(run(g, "north", answers=["n"]))
        self.assertIn("DANGER AHEAD", out)                             # unlocked: the boss warning, which we refuse
        self.assertEqual(g.notices, [])
        self.assertEqual(g.room_id, "rl_tower_foot")

    def test_the_key_is_given_once_even_if_the_fight_is_won_again(self):
        g = at(new_game(), "rl_oilhouse")
        out = flat(capture(events.after_fixed, g, "rl_oilhouse_dead"))
        self.assertIn("In his apron pocket, a key.", out)
        self.assertEqual(g.player.count("rl_tower_key"), 1)
        capture(events.after_fixed, g, "rl_oilhouse_dead")
        self.assertEqual(g.player.count("rl_tower_key"), 1)

    def test_the_key_is_a_key_item_that_cannot_be_dropped_or_sold(self):
        self.assertEqual(ITEMS["rl_tower_key"]["kind"], "key")
        self.assertEqual(ITEMS["rl_receipt"]["kind"], "key")


class HeronTests(unittest.TestCase):
    def test_winning_gives_the_lens_shard_once_only(self):
        g = at(new_game(), "rl_lantern_room")
        out = flat(capture(events.after_fixed, g, "rl_heron_dead"))
        self.assertIn("like a woman at a window", out)
        self.assertEqual(g.player.count("rl_lens_shard"), 1)
        capture(events.after_fixed, g, "rl_heron_dead")
        self.assertEqual(g.player.count("rl_lens_shard"), 1)
        self.assertTrue(g.flags["got_rl_lens_shard"])

    def test_the_gear_is_not_on_the_floor_and_comes_from_the_heron(self):
        g = new_game()
        self.assertEqual(g.room_items.get("rl_lantern_room", []), [])
        at(g, "rl_lantern_room")
        out = flat(capture(events.after_fixed, g, "rl_heron_dead"))
        self.assertIn("snuffing pole", out)
        self.assertTrue(g.player.has_item("rl_heronplume_coat"))
        self.assertTrue(g.player.has_item("rl_keepers_pole"))
        capture(events.after_fixed, g, "rl_heron_dead")          # a call-back must not duplicate the gear
        self.assertEqual(g.player.count("rl_heronplume_coat"), 1)
        self.assertEqual(g.player.count("rl_keepers_pole"), 1)

    def test_fleeing_the_heron_leaves_the_gear_out_of_reach(self):
        from lamplighter import engine
        g = at(new_game(), "rl_tower_foot")
        g.give("rl_tower_key", quiet=True)
        real = engine.Combat.run
        engine.Combat.run = lambda self: "fled"
        try:
            run(g, "north")
        finally:
            engine.Combat.run = real
        self.assertEqual(g.room_id, "rl_lantern_room")
        self.assertFalse(g.flags.get("rl_heron_dead"))
        run(g, "take all")
        self.assertFalse(g.player.has_item("rl_heronplume_coat"))
        self.assertFalse(g.player.has_item("rl_keepers_pole"))

    def test_the_pole_answers_to_a_plain_word_and_is_not_worse_than_the_saber(self):
        self.assertEqual(ITEMS["rl_keepers_pole"]["name"], "Keeper's Snuffing Pole")
        g = new_game()
        g.give("rl_keepers_pole", quiet=True)
        run(g, "equip pole")
        self.assertEqual(g.player.equipment["weapon"], "rl_keepers_pole")
        # it is the boss reward, so it must beat the saber Brann sells once the Saltmarsh is visited
        pole, saber = ITEMS["rl_keepers_pole"], ITEMS["saltsteel_saber"]
        for k, v in saber["stats"].items():
            self.assertGreaterEqual(pole["stats"].get(k, 0), v, k)
        for k, v in saber.get("mult", {}).items():
            self.assertGreaterEqual(pole["mult"].get(k, 1), v, k)
        self.assertGreater(sum(pole["stats"].values()), sum(saber["stats"].values()))

    def test_the_lamp_room_reads_true_after_the_heron_has_gone(self):
        g = at(new_game(), "rl_lantern_room")
        before = flat(capture(g.render_room))
        g.flags["rl_heron_dead"] = True
        after = flat(capture(g.render_room))
        self.assertNotIn("the heron stands", before)
        self.assertNotIn("the heron stands", after)

    def test_the_heron_is_she_in_every_line_the_player_reads(self):
        h = ENEMIES["rl_heron"]
        moves = h["moves"] + [m for ph in h["phases"] for m in ph["moves"]]
        for m in moves:
            self.assertNotRegex(m["tell"], r"\b(its|him|his)\b", m["name"])
        self.assertNotRegex(h["desc"], r"\bit\b")
        self.assertNotIn("Only its", ROOMS["rl_lantern_room"]["fixed"]["intro"])

    def test_every_tell_reads_as_a_verb_after_the_name(self):
        """The combat line is '<name before the comma> <tell>': a tell that starts with a noun reads as broken English."""
        for eid in RL_ENEMIES:
            e = ENEMIES[eid]
            for m in e["moves"] + [m for ph in e.get("phases", []) for m in ph["moves"]]:
                self.assertNotRegex(m["tell"], r"^(the|a|an) ", "%s %s" % (eid, m["name"]))

    def test_the_lampman_is_he_everywhere(self):
        for m in ENEMIES["rl_lampman"]["moves"]:
            self.assertNotIn(" its ", " " + m["tell"] + " ", m["name"])

    def test_the_heron_is_tuned_to_the_spec_band(self):
        """Spec 7.3: a level-6 player in saltsteel gear should win about 85 to 95% (mean over the three classes)."""
        from lamplighter import sim
        self.assertGreaterEqual(ENEMIES["rl_heron"]["atk"], 22)
        wins = []
        for cls in ("warden", "wayfarer", "ashblade"):
            r = sim.win_rate(["rl_heron"], sim.suggested, n=40, cls=cls, level=6, weapon="saltsteel_saber",
                             armor="hauberk", room="rl_lantern_room", items={"draught": 3, "oil": 3})
            wins.append(r["win"])
        mean = sum(wins) / len(wins)
        self.assertTrue(0.80 <= mean <= 0.95, mean)

    def test_a_call_back_of_the_heron_re_locks_nothing(self):
        """A Wizard call-back pops the boss flags; the fog is remembered and the tower key stays in the pack."""
        g = with_book(at(new_game(), "bog_lights"), "fire")
        run(g, "south")
        g.give("rl_tower_key", quiet=True)
        g.flags["rl_oilhouse_dead"] = g.flags["rl_heron_dead"] = True
        g.player.spells = []
        for k in ("rl_oilhouse_dead", "rl_heron_dead"):
            g.flags.pop(k)
        self.assertTrue(g.unlocked(ROOMS["bog_lights"]["locks"]["s"]))
        self.assertTrue(g.unlocked(ROOMS["rl_tower_foot"]["locks"]["n"]))
        run(g, "north")
        self.assertEqual(g.room_id, "bog_lights")
        run(g, "south")
        self.assertEqual(g.room_id, "rl_causeway")

    def test_the_boss_tip_is_shown_for_the_lamp_room(self):
        from lamplighter import navigation
        self.assertIn("Lens Flare blinds", navigation.boss_tip("rl_lantern_room"))


class ReceiptTests(unittest.TestCase):
    def test_the_receipt_is_on_the_cottage_floor_of_a_fresh_game(self):
        g = new_game()
        self.assertIn("rl_receipt", g.room_items["rl_cottage"])

    def test_the_receipt_is_on_the_floor_for_a_save_made_before_the_package(self):
        g = new_game()
        d = json.loads(json.dumps(g.to_dict()))
        for rid in RL_ROOMS:
            d["room_items"].pop(rid, None)
        old = Game.from_dict(d)
        self.assertIn("rl_receipt", old.room_items["rl_cottage"])
        self.assertEqual(old.room_items.get("rl_lantern_room", []), [])

    def test_the_receipt_is_on_the_floor_when_a_real_pre_m6_save_is_loaded(self):
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "saves", "v2_current.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("rl_cottage", data["room_items"])
        old = Game.from_dict(data)
        self.assertIn("rl_receipt", old.room_items["rl_cottage"])

    def test_the_receipt_text_is_the_spec_text(self):
        d = ITEMS["rl_receipt"]["desc"]
        self.assertIn("Held in trust. To be returned lit by spring. The kettle was on. -A.", d)
        self.assertEqual(ITEMS["rl_receipt"]["name"], "Receipt: the Reedlight")

    def test_taking_it_from_the_cottage(self):
        g = at(new_game(), "rl_cottage")
        run(g, "take receipt")
        self.assertTrue(g.player.has_item("rl_receipt"))


class OskarTests(unittest.TestCase):
    def test_no_topic_before_the_heron_or_the_receipt(self):
        g = new_game()
        self.assertEqual(areas.topics(g, "oskar"), [])

    def test_holding_the_receipt_opens_the_topic(self):
        g = new_game()
        g.give("rl_receipt", quiet=True)
        self.assertEqual([label for label, _ in areas.topics(g, "oskar")], ["Ask about the Reedlight"])

    def test_the_dead_heron_opens_it_too(self):
        g = new_game()
        g.flags["rl_heron_dead"] = True
        self.assertEqual(len(areas.topics(g, "oskar")), 1)

    def test_first_time_the_sou_wester_comes_back_and_he_says_ansel(self):
        g = new_game()
        g.flags["rl_heron_dead"] = True
        out = talk_oskar_topic(g)
        self.assertIn("Oskar pushes back his sou'wester for the first time.", out)
        self.assertIn("Ansel.", out)
        self.assertIn("so I'll know where I am", out)
        self.assertNotIn("good receipt", out)          # no receipt in hand
        self.assertTrue(g.flags["rl_oskar_spoke"])

    def test_first_time_with_the_receipt_he_reads_it(self):
        g = new_game()
        g.give("rl_receipt", quiet=True)
        out = talk_oskar_topic(g)
        self.assertIn("Ansel.", out)
        self.assertIn("Held in trust. He always did like a good receipt.", out)

    def test_later_visits_give_the_short_line(self):
        g = new_game()
        g.give("rl_receipt", quiet=True)
        talk_oskar_topic(g)
        out = talk_oskar_topic(g)
        self.assertIn("The line is the same. I pole it anyway.", out)
        self.assertNotIn("pushes back his sou'wester", out)
        self.assertNotIn("good receipt", out)          # he has already read it

    def test_a_receipt_found_after_the_first_talk_is_still_shown_once(self):
        g = new_game()
        g.flags["rl_heron_dead"] = True
        talk_oskar_topic(g)
        g.give("rl_receipt", quiet=True)
        out = talk_oskar_topic(g)
        self.assertIn("The line is the same. I pole it anyway.", out)
        self.assertIn("good receipt", out)
        self.assertNotIn("good receipt", talk_oskar_topic(g))

    def test_oskars_own_menu_still_works(self):
        g = new_game()
        g.flags["rl_heron_dead"] = True
        g.flags["oskar_met"] = True
        at(g, "docks")
        out = flat(run(g, "talk oskar", answers=["1", "0"]))
        self.assertIn("Oskar", out)
        self.assertIn("Mind the water.", out)

    def test_the_rumour_appears_after_he_has_spoken(self):
        g = new_game()
        self.assertEqual(areas.rumours(g), [])
        g.flags["rl_oskar_spoke"] = True
        self.assertIn("Oskar said his brother's name to a customer yesterday. The whole tavern went quiet.",
                      areas.rumours(g))
        self.assertFalse([r for r in areas.rumours(g) if "Four words" in r])

    def test_the_news_marker_shows_until_he_has_been_asked(self):
        g = new_game()
        g.flags["talked_oskar"] = True                 # his own news is spent; only the lighthouse is left
        self.assertFalse(npcs.has_news(g, "oskar"))
        g.give("rl_receipt", quiet=True)
        self.assertTrue(npcs.has_news(g, "oskar"))
        talk_oskar_topic(g)
        self.assertFalse(npcs.has_news(g, "oskar"))

    def test_the_dead_heron_also_raises_the_news_marker(self):
        g = new_game()
        g.flags["talked_oskar"] = True
        g.flags["rl_heron_dead"] = True
        self.assertTrue(npcs.has_news(g, "oskar"))


class JournalTests(unittest.TestCase):
    def objs(self, g):
        from lamplighter import navigation
        return [o for o in navigation.objectives(g) if o["room"] in ("bog_lights", "rl_oilhouse", "rl_lantern_room")]

    def test_the_three_steps_in_order_and_all_are_side(self):
        g = new_game()
        self.assertEqual(self.objs(g), [])                      # the Reedways have not been seen yet
        g.visited.add("reedways")
        o = self.objs(g)
        self.assertEqual([x["room"] for x in o], ["bog_lights"])
        g.flags["rl_fog_burned"] = True
        self.assertEqual([x["room"] for x in self.objs(g)], ["rl_oilhouse"])
        g.flags["rl_oilhouse_dead"] = True
        self.assertEqual([x["room"] for x in self.objs(g)], ["rl_lantern_room"])
        g.flags["rl_heron_dead"] = True
        self.assertEqual(self.objs(g), [])
        g.flags.pop("rl_heron_dead")
        for x in self.objs(g):
            self.assertTrue(x["side"])


class WakeTests(unittest.TestCase):
    def test_dying_with_the_cottage_as_your_last_rest(self):
        g = at(new_game(), "rl_cottage")
        g.player.gold = 100
        g.last_rest = "rl_cottage"
        out = flat(capture(g.death))
        self.assertIn("You wake on the keeper's cot with the kettle singing.", out)
        self.assertIn("lighter by 50 gold", out)
        self.assertEqual(g.room_id, "rl_cottage")

    def test_lighting_the_cottage_waypost_uses_its_own_words(self):
        g = at(new_game(), "rl_cottage")
        g.player.oil = 50
        out = flat(run(g, "light"))
        self.assertTrue(g.flags["lit_rl_cottage"])
        self.assertIn("kettle begin to sing", out)
        self.assertNotIn("Tollroad", out)


class ClearTheReedlightTests(unittest.TestCase):
    """A strong player walks the whole lighthouse with the game's own advice: fog, oil-house, key, heron, receipt."""

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

    def test_from_the_bog_lights_to_the_dead_heron(self):
        sim = self.sim
        g = new_game(seed=3)
        g.player = sim.build_player("wayfarer", 6, weapon="saltsteel_saber", armor="hauberk",
                                    items={"draught": 4, "strong_draught": 3, "oil": 4},
                                    lantern={"shroud": True, "trim": True, "lens": True},
                                    spells=[("fire", "common")])
        at(g, "bog_lights")
        g.flags["completed"] = True
        steps = [("south", "rl_causeway"), ("south", "rl_cottage"), ("take receipt", "rl_cottage"),
                 ("east", "rl_oilhouse")]
        for cmd, want in steps:
            run(g, cmd, answers=["y"] * 4)
            self.assertEqual(g.room_id, want)
            g.player.hp, g.player.oil = g.player.max_hp, g.player.max_oil
        self.assertTrue(g.player.has_item("rl_receipt"))
        self.assertTrue(g.flags.get("rl_oilhouse_dead"))
        self.assertTrue(g.player.has_item("rl_tower_key"))
        for cmd, want in [("north", "rl_sluice"), ("east", "rl_tower_foot")]:
            run(g, cmd, answers=["y"] * 4)
            self.assertEqual(g.room_id, want)
        g.player.hp, g.player.oil = g.player.max_hp, g.player.max_oil
        for _ in range(4):                                       # a boss can win a round of dice: step back and retry
            run(g, "north", answers=["y"] * 4)
            if g.flags.get("rl_heron_dead"):
                break
            g.room_id = "rl_tower_foot"
            g.player.hp, g.player.oil = g.player.max_hp, g.player.max_oil
        self.assertTrue(g.flags.get("rl_heron_dead"))
        self.assertEqual(g.room_id, "rl_lantern_room")
        self.assertTrue(g.player.has_item("rl_lens_shard"))
        self.assertGreaterEqual(g.player.gems, 1)                 # first kill of a boss pays gems
        self.assertTrue(g.player.has_item("rl_heronplume_coat"))  # handed over by the victory, not lying about
        self.assertTrue(g.player.has_item("rl_keepers_pole"))
        self.assertTrue(set(RL_ROOMS) <= g.visited)               # the whole chain was walked with the locks on


if __name__ == "__main__":
    unittest.main()
