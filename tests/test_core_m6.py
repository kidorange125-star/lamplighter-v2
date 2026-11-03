"""M6 core plumbing (docs/M6-SPEC.md section 4, rows C1 to C12): attach patches, lock kinds, merged area hooks,
the validator's new rules, text hooks, the dealer's region rules and the small fixes. The Court's text is untouched."""
import contextlib
import copy
import io
import json
import os
import tempfile
import types
import unittest
from unittest import mock

from lamplighter import areas, content, dealer, entities, events, gear, navigation, npcs, powerroll, town, validate
from lamplighter.content import AFFIXES, BUILDINGS, DEALER, ENEMIES, FORGE, ITEMS, REGION_INFO, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, run


def stub_room(**kw):
    room = {"name": "Stub", "region": "Hollowmere", "pos": (90, 90), "dark": True, "desc": "A stub.",
            "exits": {}, "features": {"stub": "A stub."}}
    room.update(kw)
    return room


class AreaStubCase(unittest.TestCase):
    """Base class: inject stub area modules into areas._mods and take them out again."""

    def run(self, result=None):
        # the real area modules would add their own topics, objectives and hooks to every assertion below
        areas.modules()
        saved = list(areas._mods)
        areas._mods[:] = []
        try:
            return super().run(result)
        finally:
            areas._mods[:] = saved

    def inject(self, **attrs):
        areas.modules()
        mod = types.ModuleType("lamplighter.areas.zz_stub_%d" % len(areas._mods))
        mod.__dict__.update(attrs)
        areas._mods.append(mod)
        self.addCleanup(areas._mods.remove, mod)
        return mod


# ============================================================================ C1 attach patches
class AttachTests(unittest.TestCase):
    def write(self, folder, name, data):
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def rooms(self):
        return {"a": {"exits": {"n": "b"}, "npcs": ["x"]}, "b": {"exits": {"s": "a"}}}

    def test_exits_locks_npcs_and_items_are_merged(self):
        rooms = self.rooms()
        with tempfile.TemporaryDirectory() as d:
            path = self.write(d, "one.json", {"a": {
                "exits": {"e": "b"}, "locks": {"e": {"flag": "f", "msg": "m"}}, "npcs": ["y"], "items": ["oil"]}})
            content.apply_attach(rooms, [path])
        self.assertEqual(rooms["a"]["exits"], {"n": "b", "e": "b"})
        self.assertEqual(rooms["a"]["locks"], {"e": {"flag": "f", "msg": "m"}})
        self.assertEqual(rooms["a"]["npcs"], ["x", "y"])
        self.assertEqual(rooms["a"]["items"], ["oil"])
        self.assertNotIn("locks", rooms["b"])

    def test_files_apply_in_the_order_given(self):
        rooms = self.rooms()
        with tempfile.TemporaryDirectory() as d:
            p1 = self.write(d, "a.json", {"b": {"items": ["oil"]}})
            p2 = self.write(d, "b.json", {"b": {"items": ["tonic"]}})
            content.apply_attach(rooms, [p1, p2])
        self.assertEqual(rooms["b"]["items"], ["oil", "tonic"])

    def test_an_existing_exit_is_an_error_naming_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.write(d, "clash.json", {"a": {"exits": {"n": "b"}}})
            with self.assertRaisesRegex(ValueError, "clash.json"):
                content.apply_attach(self.rooms(), [path])

    def test_an_existing_lock_is_an_error(self):
        rooms = self.rooms()
        rooms["a"]["locks"] = {"n": {"flag": "f", "msg": "m"}}
        with tempfile.TemporaryDirectory() as d:
            path = self.write(d, "lock.json", {"a": {"locks": {"n": {"flag": "g", "msg": "m"}}}})
            with self.assertRaisesRegex(ValueError, "lock.json"):
                content.apply_attach(rooms, [path])

    def test_an_unknown_room_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.write(d, "ghost.json", {"nowhere": {"exits": {"e": "a"}}})
            with self.assertRaisesRegex(ValueError, "ghost.json.*nowhere"):
                content.apply_attach(self.rooms(), [path])

    def test_content_applies_the_attach_folder_to_the_real_rooms(self):
        # whatever attach files exist, every exit they added is in ROOMS and the world still validates its own shape
        folder = os.path.join(content.DATA_DIR, "attach")
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                for rid, patch in json.load(f).items():
                    for d, dest in patch.get("exits", {}).items():
                        self.assertEqual(ROOMS[rid]["exits"][d], dest, name)


# ============================================================================ C2 lock kinds
class LockTests(unittest.TestCase):
    def setUp(self):
        self.g = new_game()

    def relic_gear(self, kind_base, relic_base, rarity="epic", slot="weapon", worn=True):
        inst = gear.make(kind_base, "epic", self.g.rng, affixes=[], relics=[{"base": relic_base, "rarity": rarity}])
        gear.give(self.g.player, inst)
        if worn:
            self.g.player.equipment[slot] = inst["id"]
        return inst

    def test_flags_lock_needs_every_flag(self):
        lock = {"flags": ["a", "b", "c"], "msg": "m"}
        self.assertFalse(self.g.unlocked(lock))
        self.g.flags.update(a=True, b=True)
        self.assertFalse(self.g.unlocked(lock))
        self.assertEqual(self.g.lock_status(lock), "2 of 3 done.")
        self.g.flags["c"] = True
        self.assertTrue(self.g.unlocked(lock))
        self.assertEqual(self.g.lock_status(lock), "3 of 3 done.")

    def test_dread_lock_has_inclusive_bounds_and_defaults(self):
        lock = {"dread": {"max": 24}, "msg": "m"}
        for dread, want in ((0, True), (24, True), (25, False), (31, False)):
            self.g.player.dread = dread
            self.assertEqual(self.g.unlocked(lock), want, dread)
        band = {"dread": {"min": 50, "max": 74}, "msg": "m"}
        for dread, want in ((49, False), (50, True), (74, True), (75, False)):
            self.g.player.dread = dread
            self.assertEqual(self.g.unlocked(band), want, dread)
        self.g.player.dread = 31
        self.assertEqual(self.g.lock_status(lock), "Dread is 31 now.")
        self.assertTrue(self.g.unlocked({"dread": {"min": 0}, "msg": "m"}))

    def test_relic_lock_wants_a_socketed_worn_relic(self):
        lock = {"relic": "lamp", "msg": "m"}
        self.assertFalse(self.g.unlocked(lock))
        self.assertEqual(self.g.lock_status(lock), "Worn relics: none")
        self.g.player.add_item("relic_lamp")                       # in the pack is not enough
        self.assertFalse(self.g.unlocked(lock))
        self.relic_gear("hunting_spear", "relic_ember")             # the wrong type, socketed and worn
        self.assertFalse(self.g.unlocked(lock))
        self.assertEqual(self.g.lock_status(lock), "Worn relics: Ember (epic)")

    def test_relic_lock_opens_for_a_lamp_in_weapon_armour_or_trinket(self):
        lock = {"relic": "lamp", "msg": "m"}
        for kind_base, slot in (("hunting_spear", "weapon"), ("hauberk", "armor")):
            g = self.g = new_game()
            self.relic_gear(kind_base, "relic_lamp", slot=slot)
            self.assertTrue(g.unlocked(lock), slot)
            self.assertEqual(g.lock_status(lock), "Worn relics: Lamp (epic)")
        trinket = next(i for i, it in ITEMS.items() if it.get("kind") == "trinket" and "instance" not in it)
        g = self.g = new_game()
        self.relic_gear(trinket, "relic_lamp", slot="trinket")
        self.assertTrue(g.unlocked(lock), "trinket")

    def test_relic_lock_accepts_a_list_of_types_and_an_unworn_relic_does_not_count(self):
        self.relic_gear("hunting_spear", "relic_pulse", worn=False)
        self.assertFalse(self.g.unlocked({"relic": ["pulse", "lamp"], "msg": "m"}))
        self.g.player.equipment["weapon"] = next(i for i, it in ITEMS.items() if it.get("relics"))
        self.assertTrue(self.g.unlocked({"relic": ["lamp", "pulse"], "msg": "m"}))

    def test_all_lock_needs_every_part_and_prints_each_status(self):
        lock = {"all": [{"item": "oil"}, {"dread": {"max": 24}}, {"flags": ["a", "b"]}], "msg": "m"}
        self.g.player.dread = 40
        self.assertFalse(self.g.unlocked(lock))
        self.assertEqual(self.g.lock_status(lock), "Dread is 40 now. 0 of 2 done.")
        self.g.player.add_item("oil")
        self.g.player.dread = 10
        self.g.flags.update(a=True, b=True)
        self.assertTrue(self.g.unlocked(lock))

    def test_element_status_lists_equipped_books(self):
        lock = {"element": ["fire"], "msg": "m"}
        self.assertEqual(self.g.lock_status(lock), "Equipped books: none")
        self.g.player.add_item("book_earth")
        self.g.player.spells = ["book_earth"]
        self.assertEqual(self.g.lock_status(lock), "Equipped books: Earth")
        self.assertFalse(self.g.unlocked(lock))

    def test_plain_locks_print_no_status(self):
        for lock in ({"item": "oil"}, {"flag": "x"}, {"shards": 2}, {"building": "strongroom"}):
            self.assertEqual(self.g.lock_status(lock), "", lock)

    def test_remember_still_comes_first(self):
        self.g.flags["kept"] = True
        self.assertTrue(self.g.unlocked({"flags": ["never"], "remember": "kept", "msg": "m"}))

    def test_a_refused_move_prints_the_message_then_the_status_line(self):
        locks = dict(ROOMS["hall"].get("locks", {}), e={"flags": ["zz_a", "zz_b"], "msg": "The way is barred."})
        with mock.patch.dict(ROOMS, {"hall": dict(ROOMS["hall"], locks=locks)}):
            run(self.g, "e")
            self.assertEqual(self.g.room_id, "hall")
            self.assertEqual(self.g.notices[-2:], ["The way is barred.", "{grey}0 of 2 done.{/}"])
            self.g.flags.update(zz_a=True, zz_b=True)
            run(self.g, "e")
            self.assertEqual(self.g.room_id, "square")

    def test_the_existing_locks_print_no_extra_line(self):
        run(self.g, "n")                      # the hall's north door wants the `completed` flag
        self.assertEqual(len(self.g.notices), 1)
        self.assertIn("SHOP OPENS", self.g.notices[0])

    def test_the_map_and_the_area_screen_draw_every_new_lock_kind(self):
        for lock in ({"flags": ["a"]}, {"relic": "lamp"}, {"dread": {"max": 5}},
                     {"all": [{"item": "oil"}, {"dread": {"max": 5}}]}):
            locks = dict(ROOMS["hall"].get("locks", {}), e=dict(lock, msg="m"))
            with mock.patch.dict(ROOMS, {"hall": dict(ROOMS["hall"], locks=locks)}):
                g = new_game()
                g.player.dread = 50
                g.visited.update(("hall", "square"))
                out = run(g, "look", "map", "map world")
                self.assertTrue(out, lock)
                with contextlib.redirect_stdout(io.StringIO()):
                    g.render_room()
                self.assertFalse([x for x in g.suggestions() if "Go east" in str(x)], lock)   # shut, so not offered

    def test_pathfinding_respects_the_new_kinds(self):
        locks = dict(ROOMS["hall"].get("locks", {}), e={"dread": {"max": 5}, "msg": "m"})
        with mock.patch.dict(ROOMS, {"hall": dict(ROOMS["hall"], locks=locks)}):
            self.g.player.dread = 50
            self.assertIsNone(navigation.find_path(self.g, "hall", "square"))
            self.g.player.dread = 0
            self.assertIsNotNone(navigation.find_path(self.g, "hall", "square"))


# ============================================================================ C3 merged hooks
class MergedHookTests(AreaStubCase):
    def setUp(self):
        self.g = new_game()

    def test_merged_collects_the_same_key_from_two_modules(self):
        self.inject(TOPICS={"orrin": lambda g: [("One", lambda g: None)]})
        self.inject(TOPICS={"orrin": lambda g: [("Two", lambda g: None)], "brann": lambda g: []})
        self.assertEqual(len(areas.merged("TOPICS")["orrin"]), 2)
        self.assertEqual([label for label, _ in areas.topics(self.g, "orrin")], ["One", "Two"])
        self.assertEqual(areas.topics(self.g, "nobody"), [])

    def test_extra_news_is_or_ed(self):
        self.inject(EXTRA_NEWS={"hesk": lambda g: False})
        self.assertFalse(areas.extra_news(self.g, "hesk"))
        self.inject(EXTRA_NEWS={"hesk": lambda g: True})
        self.assertTrue(areas.extra_news(self.g, "hesk"))

    def test_extra_news_adds_to_the_core_rule_and_never_replaces_it(self):
        self.g.flags["hesk_met"] = True
        self.assertFalse(npcs.has_news(self.g, "hesk"))
        self.inject(EXTRA_NEWS={"hesk": lambda g: True})
        self.assertTrue(npcs.has_news(self.g, "hesk"))
        self.g.flags["hesk_met"] = False
        self.inject(EXTRA_NEWS={"hesk": lambda g: False})
        self.assertTrue(npcs.has_news(self.g, "hesk"))             # the core rule still says yes

    def test_sells_adds_wares_without_duplicates(self):
        base = npcs.stock_for(self.g, "odo")
        self.inject(SELLS={"odo": lambda g: ["tonic", "slag"]})
        self.inject(SELLS={"odo": lambda g: ["tonic", "oil"]})
        self.assertEqual(npcs.stock_for(self.g, "odo"), base + ["tonic", "oil"])

    def test_prices_come_from_collect_and_a_duplicate_is_an_error(self):
        self.assertEqual(npcs.price("tonic"), ITEMS["tonic"]["value"])
        self.inject(PRICES={"tonic": 7})
        self.assertEqual(npcs.price("tonic"), 7)
        self.assertEqual(npcs.price("lens"), 140)                  # the local table still wins for its own items
        self.inject(PRICES={"tonic": 8})
        with self.assertRaises(ValueError):
            npcs.price("tonic")

    def test_after_gain_runs_the_hook_and_a_duplicate_is_an_error(self):
        seen = []
        self.inject(AFTER_GAIN={"tonic": lambda g: seen.append("tonic")})
        run(self.g, "look")
        self.g.give("tonic", quiet=True)
        self.g.give("oil", quiet=True)
        self.assertEqual(seen, ["tonic"])
        self.inject(AFTER_GAIN={"tonic": lambda g: None})
        with self.assertRaises(ValueError):
            areas.collect("AFTER_GAIN")                  # what the validator runs: two modules, one item

    def test_rumours_are_joined_from_every_module(self):
        self.inject(RUMOURS=lambda g: ["Rumour A"])
        self.inject(RUMOURS=lambda g: ["Rumour B", "Rumour C"])
        self.assertEqual(areas.rumours(self.g), ["Rumour A", "Rumour B", "Rumour C"])

    def test_maeve_can_tell_an_area_rumour(self):
        self.inject(RUMOURS=lambda g: ["The stub lamps are lit."])
        self.g.quests["wren"] = "done"
        self.g.room_id = "tavern"
        with mock.patch.object(self.g.rng, "choice", side_effect=lambda seq: seq[-1]):
            out = run(self.g, "talk maeve", answers=["1", "0"])
        self.assertIn("The stub lamps are lit.", out)

    def test_give_first_gives_once_ever(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(areas.give_first(self.g, "tonic"))
            self.assertFalse(areas.give_first(self.g, "tonic"))
            self.assertEqual(self.g.player.inventory["tonic"], 1)
            self.assertTrue(self.g.flags["got_tonic"])
            before = self.g.player.inventory.get("oil", 0)
            self.assertTrue(areas.give_first(self.g, "oil", 3))
        self.assertEqual(self.g.player.inventory["oil"], before + 3)


class TopicMenuTests(AreaStubCase):
    def setUp(self):
        self.g = new_game()
        self.g.flags["oskar_met"] = True
        self.g.room_id = "docks"

    def test_oskar_is_a_menu_with_a_tip_and_a_farewell(self):
        out = run(self.g, "talk oskar", answers=["1", "0"])
        self.assertIn("Ask for advice about the marsh", out)
        self.assertIn("Mind the water.", out)
        self.assertTrue(self.g.flags["talked_oskar"])

    def test_oskar_keeps_his_first_meeting(self):
        self.g.flags["oskar_met"] = False
        out = run(self.g, "talk oskar")
        self.assertIn("Nobody goes to the marsh", out)
        self.assertNotIn("Mind the water.", out)

    def test_an_area_topic_runs_on_the_same_screen_and_the_menu_comes_back(self):
        ran = []

        def handler(g):
            ran.append(g.room_id)
            from lamplighter.ui import say
            say("STUB TOPIC TEXT")

        self.inject(TOPICS={"oskar": lambda g: [("Ask about the stub", handler)]})
        out = run(self.g, "talk oskar", answers=["2", "1", "0"])
        self.assertEqual(ran, ["docks"])
        self.assertIn("STUB TOPIC TEXT", out)
        self.assertIn("You: Ask about the stub", out)
        self.assertEqual(out.count("[1] Ask for advice about the marsh"), 3)    # the menu was drawn three times
        self.assertIn("Mind the water.", out)

    def test_a_caller_option_still_returns_its_own_key(self):
        self.inject(TOPICS={"oskar": lambda g: [("Extra", lambda g: None)]})
        npcs._speaker[0], npcs._speaker_g[0] = "oskar", self.g
        with contextlib.redirect_stdout(io.StringIO()):
            from lamplighter import ui
            ui.io.script = ["1"]
            self.assertEqual(npcs.topic_menu([("First", "one"), ("Second", "two")]), "one")
            ui.io.script = ["2"]
            self.assertEqual(npcs.topic_menu([("First", "one"), ("Second", "two")]), "two")
            ui.io.script = ["0"]
            self.assertIsNone(npcs.topic_menu([("First", "one")]))

    def test_every_menu_speaker_gains_area_topics(self):
        # the generic path: any NPC that goes through topic_menu shows area topics (checked with Hesk, who has no menu change)
        self.inject(TOPICS={"maeve": lambda g: [("Ask about the stub", lambda g: None)]})
        self.g.quests["wren"] = "done"
        self.g.room_id = "tavern"
        out = run(self.g, "talk maeve", answers=["0"])
        self.assertIn("Ask about the stub", out)

    def test_nothing_changes_without_area_topics(self):
        out = run(self.g, "talk oskar", answers=["0"])
        self.assertEqual(out.count("[1]"), 1)


# ============================================================================ C4 validator
class ValidatorTests(AreaStubCase):
    def lock_errors(self, lock):
        errs = []
        validate.check_lock(lock, "L", errs.append)
        return errs

    def test_good_locks_pass(self):
        for lock in ({"relic": ["lamp", "ember"], "msg": "m"}, {"relic": "lamp", "msg": "m"},
                     {"flags": ["a"], "msg": "m"}, {"dread": {"max": 24}, "msg": "m"},
                     {"dread": {"min": 3, "max": 9}, "msg": "m"}, {"flag": "x", "remember": "r", "msg": "m"},
                     {"all": [{"item": "oil"}, {"dread": {"max": 24}}], "msg": "m"},
                     {"all": [{"all": [{"flag": "x"}]}], "msg": "m"}):
            self.assertEqual(self.lock_errors(lock), [], lock)

    def test_bad_locks_are_rejected(self):
        bad = [{"msg": "m"}, {"flag": "x"},
               {"flags": [], "msg": "m"}, {"flags": "a", "msg": "m"}, {"flags": [1], "msg": "m"},
               {"relic": "sparkle", "msg": "m"}, {"relic": [], "msg": "m"}, {"relic": ["lamp", "nope"], "msg": "m"},
               {"dread": {}, "msg": "m"}, {"dread": {"max": 101}, "msg": "m"}, {"dread": {"min": -1}, "msg": "m"},
               {"dread": {"max": "x"}, "msg": "m"}, {"dread": {"mid": 5}, "msg": "m"},
               {"dread": {"min": 50, "max": 10}, "msg": "m"}, {"dread": 5, "msg": "m"},
               {"all": [], "msg": "m"}, {"all": [{"msg": "no requirement"}], "msg": "m"},
               {"all": [{"item": "nope_item"}], "msg": "m"}, {"item": "nope_item", "msg": "m"},
               {"building": "nope", "msg": "m"}, {"element": ["plasma"], "msg": "m"},
               {"flag": "x", "remember": 5, "msg": "m"}]
        for lock in bad:
            self.assertTrue(self.lock_errors(lock), lock)

    def test_two_requirement_kinds_in_one_lock_are_rejected(self):
        for lock in ({"item": "oil", "flag": "x", "msg": "m"}, {"relic": "lamp", "flag": "x", "msg": "m"},
                     {"dread": {"max": 5}, "item": "oil", "msg": "m"}, {"flag": "x", "flags": ["y"], "msg": "m"},
                     {"all": [{"item": "oil", "flag": "x"}], "msg": "m"}):
            errs = self.lock_errors(lock)
            self.assertTrue(any("combine requirements with 'all'" in e for e in errs), lock)
        self.assertEqual(self.lock_errors({"all": [{"item": "oil"}, {"flag": "x"}], "msg": "m"}), [])

    def test_sub_locks_need_no_message_but_the_top_lock_does(self):
        self.assertEqual(self.lock_errors({"all": [{"flag": "x"}], "msg": "m"}), [])
        self.assertTrue(self.lock_errors({"all": [{"flag": "x"}]}))

    def test_whole_validation_reports_a_bad_lock_in_a_room(self):
        locks = {"e": {"relic": "nope", "msg": "m"}}
        with mock.patch.dict(ROOMS, {"hall": dict(ROOMS["hall"], locks=dict(ROOMS["hall"]["locks"], **locks))}):
            errs = validate.validate()
        self.assertTrue(any("room hall: lock on e" in e and "relic" in e for e in errs), errs)

    def room_errors(self, rid, room):
        with mock.patch.dict(ROOMS, {rid: room}):
            return [e for e in validate.validate() if rid in e]

    def test_wake_text_is_checked(self):
        for wake in ("You wake. Lighter by %d gold.", "You wake in the warm.", None):
            room = stub_room() if wake is None else stub_room(wake=wake)
            self.assertFalse([e for e in self.room_errors("zz_room", room) if "wake must" in e], wake)
        for wake in ("Lighter by 100%", "%d and %d", "%s gold", "%d%%"):
            errs = self.room_errors("zz_room", stub_room(wake=wake))
            self.assertTrue(any("wake must" in e for e in errs), wake)

    def test_field_is_checked(self):
        good = {"name": "Black Ice", "fire": 0.75, "earth": 1.25, "msg": "The ice drinks heat."}
        self.assertFalse([e for e in self.room_errors("zz_room", stub_room(field=good)) if "field" in e])
        for bad in ({"fire": 0.75}, {"name": "x"}, {"name": "x", "plasma": 1.0}, {"name": "x", "fire": 2.0},
                    {"name": "x", "fire": 0.4}, {"name": "x", "fire": "hot"}, {"name": "x", "fire": 1.0, "msg": 5},
                    "ice"):
            errs = self.room_errors("zz_room", stub_room(field=bad))
            self.assertTrue(any("field" in e for e in errs), bad)

    def test_no_dealer_and_text_hook_keys_are_checked(self):
        errs = self.room_errors("zz_nd", stub_room(no_dealer="yes", beacon_text=5, waypost_text=[]))
        self.assertTrue(any("no_dealer" in e for e in errs))
        self.assertTrue(any("beacon_text" in e for e in errs))
        self.assertTrue(any("waypost_text" in e for e in errs))
        self.assertFalse([e for e in self.room_errors("zz_nd", stub_room(no_dealer=True, beacon_text="x"))
                          if "no_dealer" in e or "beacon_text" in e])

    def test_an_area_enter_hook_makes_a_boss_room_valid(self):
        room = stub_room(boss="zz_flag", boss_name="Nobody")
        errs = self.room_errors("zz_boss", room)
        self.assertTrue(any("boss flag zz_flag is never set" in e for e in errs), errs)
        self.inject(ENTER={"zz_boss": lambda g, first: True})
        with mock.patch.dict(ROOMS, {"zz_boss": room}):
            errs = validate.validate()
        self.assertFalse([e for e in errs if "zz_boss" in e and "never set" in e], errs)

    def test_a_fixed_fight_still_validates_a_boss_room(self):
        room = stub_room(boss="zz_flag", boss_name="Nobody", fixed={"flag": "zz_flag", "enemies": ["wisp"]})
        self.assertFalse([e for e in self.room_errors("zz_boss", room) if "never set" in e])

    def test_roll_pronouns_and_place_are_checked(self):
        base = copy.deepcopy(ENEMIES["cinder_queen"])
        for roll_extra, bad in (({"pron": {"subj": "he", "obj": "him", "poss": "his"}, "place": "The Fair"}, False),
                                ({"pron": {"subj": "it", "obj": "it"}}, True),
                                ({"pron": "he"}, True), ({"place": 5}, True)):
            enemy = copy.deepcopy(base)
            enemy["roll"].update(roll_extra)
            with mock.patch.dict(ENEMIES, {"zz_rolled": enemy}):
                errs = [e for e in validate.validate() if "zz_rolled" in e]
            self.assertEqual(bool(errs), bad, (roll_extra, errs))

    def attune_errors(self, attune, tags=("elite",)):
        enemy = dict(ENEMIES["wisp"], tags=list(tags), attune=attune)
        enemy.pop("weak", None)
        enemy.pop("resist", None)
        errs = []
        validate.check_attune("zz_att", enemy, errs.append)
        return errs

    def test_attune_is_checked(self):
        good = {"every": 2, "stances": [{"name": "Sun", "weak": ["ice"], "resist": ["fire"]},
                                         {"name": "Moon", "weak": ["fire", "earth"], "msg": "It turns."}]}
        self.assertEqual(self.attune_errors(good), [])
        st = lambda **kw: dict({"name": "S", "weak": ["ice"]}, **kw)
        for bad in ({"every": 0, "stances": [st(), st()]}, {"every": 2, "stances": [st()]},
                    {"every": 2, "stances": [st()] * 5}, {"every": 2},
                    {"every": 2, "stances": [st(weak=[]), st()]}, {"every": 2, "stances": [st(weak=["ice", "fire", "earth"]), st()]},
                    {"every": 2, "stances": [st(resist=["fire", "earth", "water"]), st()]},
                    {"every": 2, "stances": [st(weak=["ice"], resist=["ice"]), st()]},
                    {"every": 2, "stances": [st(weak=["plasma"]), st()]}, {"every": 2, "stances": [{"weak": ["ice"]}, st()]}):
            self.assertTrue(self.attune_errors(bad), bad)

    def test_a_hollow_attune_enemy_cannot_be_weak_to_light(self):
        stances = {"every": 2, "stances": [{"name": "A", "weak": ["light"]}, {"name": "B", "weak": ["ice"]}]}
        self.assertTrue(self.attune_errors(stances, tags=("hollow",)))
        self.assertEqual(self.attune_errors(stances, tags=("construct",)), [])

    def test_attune_is_reached_by_the_whole_validation(self):
        enemy = dict(ENEMIES["wisp"], attune={"every": 0, "stances": []})
        with mock.patch.dict(ENEMIES, {"zz_att": enemy}):
            errs = validate.validate()
        self.assertTrue(any("zz_att" in e and "attune" in e for e in errs), errs)

    def test_forge_and_smith_items_must_exist(self):
        bad = {"to": "x", "chance": 0.1, "pity": 1, "gold": 1, "items": {"nope_item": 1}, "minutes": 1, "steps": 1}
        with mock.patch.dict(FORGE["tiers"], {"zz": bad}):
            errs = validate.validate()
        self.assertTrue(any("unknown item nope_item" in e for e in errs), errs)
        with mock.patch.dict(FORGE["relic_tiers"], {"zz": bad}):
            errs = validate.validate()
        self.assertTrue(any("unknown item nope_item" in e for e in errs), errs)

    def test_region_dealer_keys_are_checked(self):
        info = {"id": "ZZ Region", "ring": 0, "levels": "1", "gear": "x", "blurb": "", "dealer": "no"}
        cases = ((dict(info, dealer="no"), "dealer must be"), (dict(info, dealer_after=5), "dealer_after must be"),
                 (dict(info, dealer_after="beacon_Nowhere"), "names no region"))
        for bad, text in cases:
            with mock.patch.dict(REGION_INFO, {"ZZ Region": bad}):
                errs = validate.validate()
            self.assertTrue(any("ZZ Region" in e and text in e for e in errs), (text, errs))
        good = dict(info, dealer=False, dealer_after="beacon_Ember Court")
        with mock.patch.dict(REGION_INFO, {"ZZ Region": good}):
            self.assertFalse([e for e in validate.validate() if "ZZ Region" in e])

    def test_area_hook_keys_are_checked(self):
        self.inject(AFTER_GAIN={"nope_item": lambda g: None}, PRICES={"nope_price": 5},
                    TOPICS={"nobody": lambda g: []}, EXTRA_NEWS={"nobody2": lambda g: False},
                    SELLS={"nobody3": lambda g: []})
        errs = validate.validate()
        for text in ("AFTER_GAIN: unknown item 'nope_item'", "PRICES: unknown item 'nope_price'",
                     "TOPICS: unknown npc 'nobody'", "EXTRA_NEWS: unknown npc 'nobody2'", "SELLS: unknown npc 'nobody3'"):
            self.assertTrue(any(text in e for e in errs), (text, errs))

    def test_real_hooks_with_real_npcs_pass(self):
        self.inject(TOPICS={"oskar": lambda g: []}, EXTRA_NEWS={"hesk": lambda g: False}, SELLS={"odo": lambda g: []},
                    AFTER_GAIN={"tonic": lambda g: None}, PRICES={"tonic": 9})
        self.assertFalse([e for e in validate.validate() if "area hook" in e])


# ============================================================================ C5 pronouns
class RollTextTests(unittest.TestCase):
    def shown(self, eid, power=50, cap=100):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            powerroll.show(eid, power, cap)
        return out.getvalue()

    def test_the_queens_text_is_unchanged(self):
        out = self.shown("cinder_queen", 50, 55)
        self.assertIn("Power 50 of 100. The stronger she is, the more she pays.", out)
        self.assertIn("(The Court holds back. Your bad luck so far has lowered the ceiling to 55.)", out)
        self.assertNotIn("holds back", self.shown("cinder_queen", 50, 100))

    def test_he_and_it_render_with_their_own_place(self):
        for pron, subj in (({"subj": "he", "obj": "him", "poss": "his"}, "he"), ({"subj": "it", "obj": "it", "poss": "its"}, "it")):
            enemy = copy.deepcopy(ENEMIES["cinder_queen"])
            enemy["roll"].update(pron=pron, place="The Fair")
            with mock.patch.dict(ENEMIES, {"zz_rolled": enemy}):
                out = self.shown("zz_rolled", 70, 55)
            self.assertIn("The stronger %s is, the more %s pays." % (subj, subj), out)
            self.assertIn("(The Fair holds back.", out)
            self.assertNotIn("more she pays", out)
            self.assertNotIn("Court holds back", out)

    def test_a_partial_pron_falls_back_per_key(self):
        enemy = copy.deepcopy(ENEMIES["cinder_queen"])
        enemy["roll"]["pron"] = {"subj": "he"}
        with mock.patch.dict(ENEMIES, {"zz_rolled": enemy}):
            self.assertEqual(powerroll.pron("zz_rolled"), {"subj": "he", "obj": "her", "poss": "her"})

    def test_the_flee_line_follows_the_pronoun(self):
        for eid, want in (("cinder_queen", "She does not follow."), ("zz_rolled", "He does not follow.")):
            enemy = copy.deepcopy(ENEMIES["cinder_queen"])
            enemy["roll"]["pron"] = {"subj": "he", "obj": "him", "poss": "his"}
            with mock.patch.dict(ENEMIES, {"zz_rolled": enemy}):
                g = new_game()
                g.fight = lambda ids, intro=None: "fled"
                out = run(g, "look", answers=[])
                from lamplighter import ui
                ui.io.script = ["1"]
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    powerroll.boss_scene(g, eid, "zz_flag", "hall", lambda g, p: None)
                self.assertIn(want, buf.getvalue(), eid)

    def test_the_decision_menu_follows_the_pronoun(self):
        from lamplighter import ui
        for pron, want in ((None, "Face her at this strength"),
                           ({"subj": "he", "obj": "him", "poss": "his"}, "Face him at this strength"),
                           ({"subj": "it", "obj": "it", "poss": "its"}, "Face it at this strength")):
            enemy = copy.deepcopy(ENEMIES["cinder_queen"])
            if pron:
                enemy["roll"]["pron"] = pron
            with mock.patch.dict(ENEMIES, {"zz_rolled": enemy}):
                g = new_game()
                ui.io.script = ["0"]
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    powerroll.boss_scene(g, "zz_rolled", "zz_flag", "hall", lambda g, p: None)
                self.assertIn(want, buf.getvalue())
                self.assertNotIn("Face her" if pron else "Face him", buf.getvalue())


# ============================================================================ C8 text hooks
class TextHookTests(AreaStubCase):
    def test_a_room_wake_text_is_used_with_the_gold_lost(self):
        g = new_game()
        g.player.gold = 100
        wake = "You wake on a cot in the stub, under a coat. Your purse is lighter by %d gold."
        with mock.patch.dict(ROOMS, {"zz_wake": stub_room(wake=wake)}):
            g.last_rest = "zz_wake"
            out = run(g, "look")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                g.death()
        self.assertIn("lighter by 50 gold.", buf.getvalue())
        self.assertIn("under a coat", buf.getvalue())
        self.assertNotIn("steady flame", " ".join(buf.getvalue().split()))
        self.assertEqual(g.room_id, "zz_wake")

    def test_a_wake_text_without_a_number_is_printed_as_it_is(self):
        g = new_game()
        with mock.patch.dict(ROOMS, {"zz_wake": stub_room(wake="You wake. The stub is quiet.")}):
            g.last_rest = "zz_wake"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                g.death()
        self.assertIn("The stub is quiet.", buf.getvalue())

    def test_the_generic_wake_and_the_court_wake_are_unchanged(self):
        g = new_game()
        g.last_rest = "moth_shrine"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.death()
        self.assertIn("steady flame", " ".join(buf.getvalue().split()))
        g.last_rest = "court_gate"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.death()
        self.assertIn("Pell is sitting by the hearth", " ".join(buf.getvalue().split()))

    def beacon_game(self):
        g = new_game()
        g.room_id = "throne_room"
        g.flags["queen_dead"] = True
        g.player.oil = 100
        g.player.level, g.player.xp = 12, 0           # no level-up screen from the beacon's xp
        return g

    def test_the_court_beacon_text_is_the_built_in_one(self):
        g = self.beacon_game()
        out = run(g, "light")
        self.assertIn("great iron bowl", out)
        self.assertIn("every window in the house turns gold", " ".join(out.split()))

    def test_beacon_text_replaces_the_narration(self):
        g = self.beacon_game()
        with mock.patch.dict(ROOMS, {"throne_room": dict(ROOMS["throne_room"], beacon_text="The stub lantern catches.")}):
            out = run(g, "light")
        self.assertIn("The stub lantern catches.", out)
        self.assertNotIn("great iron bowl", out)
        self.assertTrue(g.flags["beacon_Ember Court"])

    def test_the_built_in_court_text_comes_before_the_area_hook(self):
        g = self.beacon_game()
        self.inject(AFTER_BEACON={"Ember Court": lambda g: print("AREA HOOK RAN")})
        out = run(g, "light")
        self.assertIn("AREA HOOK RAN", out)
        self.assertLess(out.index("The whole Court is lit"), out.index("AREA HOOK RAN"))

    def test_the_area_hook_runs_for_a_region_with_no_built_in_text(self):
        g = new_game()
        self.inject(AFTER_BEACON={"ZZ Region": lambda g: print("ZZ HOOK")})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            events.after_beacon(g, "ZZ Region")
        self.assertEqual(out.getvalue().strip(), "ZZ HOOK")

    def wood_game(self, here):
        g = new_game()
        g.room_id = here
        g.player.oil = 100
        g.player.level, g.player.xp = 12, 0
        return g

    def test_a_waypost_outside_the_wood_does_not_retell_the_tollroad(self):
        g = self.wood_game("zz_post")
        for x in ("wood_path", "thicket", "moth_shrine"):
            g.flags["lit_" + x] = True
        before_xp, before_quest = g.player.xp, g.quest("wayposts")
        with mock.patch.dict(ROOMS, {"zz_post": stub_room(waypost=True, waypost_text="The stub post kindles.")}):
            out = run(g, "light")
        self.assertIn("The stub post kindles.", out)
        self.assertNotIn("Tollroad", out)
        self.assertNotIn("Wayposts lit", out)
        self.assertNotIn("+40 xp", out)
        self.assertEqual(g.quest("wayposts"), before_quest)
        self.assertEqual(g.player.xp, before_xp)
        self.assertTrue(g.flags["lit_zz_post"])

    def test_the_wood_wayposts_still_finish_the_tollroad(self):
        g = self.wood_game("moth_shrine")
        g.flags["lit_wood_path"] = g.flags["lit_thicket"] = True
        g.quests["wayposts"] = 0
        out = run(g, "light")
        self.assertIn("The Tollroad is lit", out)
        self.assertEqual(g.quest("wayposts"), "done")
        self.assertIn("+40 xp", out)

    def test_the_first_wood_waypost_starts_the_quest_and_counts(self):
        g = self.wood_game("wood_path")
        out = run(g, "light")
        self.assertEqual(g.quest("wayposts"), 0)
        self.assertIn("Wayposts lit: 1/3", out)
        self.assertIn("dark draws back to the treeline", " ".join(out.split()))


# ============================================================================ C9 old saves, C10, C11, C12
class SmallFixTests(AreaStubCase):
    def test_a_save_made_before_a_room_existed_gives_it_its_floor_items(self):
        g = new_game()
        save = g.to_dict()
        with mock.patch.dict(ROOMS, {"zz_loot": stub_room(items=["oil", "tonic"])}):
            self.assertNotIn("zz_loot", save["room_items"])
            h = Game.from_dict(copy.deepcopy(save))
            self.assertEqual(h.room_items["zz_loot"], ["oil", "tonic"])
            h.room_items["zz_loot"].remove("oil")
            self.assertEqual(ROOMS["zz_loot"]["items"], ["oil", "tonic"])         # a copy, not the room's own list

    def test_rooms_already_in_the_save_keep_what_the_player_left(self):
        g = new_game()
        g.room_items["square"] = ["tonic"]
        h = Game.from_dict(copy.deepcopy(g.to_dict()))
        self.assertEqual(h.room_items["square"], ["tonic"])

    @unittest.skipUnless("hos_scriptorium" in ROOMS, "the hos package has not landed")
    def test_a_pre_m6_save_finds_the_hospice_receipt_on_the_floor(self):
        g = new_game()
        save = g.to_dict()
        for rid in [r for r in save["room_items"] if r.startswith("hos_")]:
            del save["room_items"][rid]
        h = Game.from_dict(save)
        self.assertIn("hos_receipt", h.room_items["hos_scriptorium"])

    def test_of_havoc_is_the_weapon_affix_and_of_ruin_stays_the_curse(self):
        self.assertIn("of_havoc", AFFIXES)
        self.assertEqual(AFFIXES["of_havoc"]["name"], "of Havoc")
        self.assertEqual(AFFIXES["of_havoc"]["mult"]["dmg"], 1.05)
        self.assertFalse(AFFIXES["of_havoc"].get("curse"))
        self.assertTrue(AFFIXES["of_ruin"]["curse"])
        self.assertEqual(AFFIXES["of_ruin"]["stats"], {"crit": -4})
        raw = content.load_json("affixes.json")["affixes"]
        ids = [a["id"] for a in raw]
        self.assertEqual(len(ids), len(set(ids)), "an affix id is used twice")

    def test_of_havoc_is_in_the_roll_pool(self):
        pool = [a["id"] for a in AFFIXES.values() if "weapon" in a["slots"] and not a.get("curse")]
        self.assertIn("of_havoc", pool)
        self.assertNotIn("of_ruin", pool)
        seen = set()
        import random
        rng = random.Random(7)
        for _ in range(400):
            seen.update(gear.make("hunting_spear", "legendary", rng)["affixes"])
        self.assertIn("of_havoc", seen)

    def test_the_level_cap_is_twelve_and_is_what_gain_xp_uses(self):
        self.assertEqual(entities.LEVEL_CAP, 12)
        p = new_game().player
        p.level, p.xp = 12, 0
        self.assertEqual(p.gain_xp(10 ** 6), 0)
        self.assertEqual(p.level, 12)
        with mock.patch.object(entities, "LEVEL_CAP", 3):
            p.level = 2
            self.assertEqual(p.gain_xp(10 ** 6), 1)
            self.assertEqual(p.level, 3)

    def test_the_town_summary_shows_display_names(self):
        g = new_game()
        zz = {"name": "The Stub Stall", "room": "square", "resident": "zz_npc", "cost": {}, "rent": 5, "blurb": "b"}
        with mock.patch.dict(BUILDINGS, {"zz_b": zz}), mock.patch.dict(npcs.NPCS, {"zz_npc": {"name": "Zed the stubber"}}):
            text = "\n".join(town.summary_lines(g))
            self.assertIn("Zed the stubber has not been asked yet", text)
            town.state(g)["built"].append("zz_b")
            text = "\n".join(town.summary_lines(g))
            self.assertIn("Zed the stubber lives there", text)
        self.assertNotIn("Zz_Npc", text)
        self.assertIn("Corvin the hermit", "\n".join(town.summary_lines(g)))

    def test_the_journal_lists_late_lending_only_when_it_exists(self):
        g = new_game()
        out = run(g, "journal")                    # the quest id is in the order list but not in the save: no crash
        self.assertIn("JOURNAL", out.upper())

    def test_a_late_lending_quest_is_listed_when_defined(self):
        from lamplighter.quests import QUESTS
        g = new_game()
        g.quests["late_lending"] = 0
        with mock.patch.dict(QUESTS, {"late_lending": {"name": "The Lending", "stages": {0: "Return the flames."}}}):
            out = run(g, "journal")
        self.assertIn("The Lending", out)
        self.assertIn("Return the flames.", out)

    def test_the_core_heart_items_exist(self):
        for el in ("fire", "ice", "water", "light", "shadow", "earth"):
            it = ITEMS["core_heart_" + el]
            self.assertEqual(it["kind"], "material")
            self.assertTrue(it["stack"])
            self.assertTrue(it["desc"])


# ============================================================================ C7 navigation
class NavigationHookTests(AreaStubCase):
    def done_game(self):
        g = new_game()
        g.quests["main"] = "done"
        g.flags.update(steward_dead=True, queen_dead=True)
        g.flags["beacon_Ember Court"] = True
        return g

    def test_the_story_is_told_is_still_the_end_of_the_ladder(self):
        g = self.done_game()
        self.assertIn("The story is told", navigation.main_objective(g)["text"])

    def test_a_side_objective_does_not_replace_it(self):
        self.inject(OBJECTIVES=lambda g, add: add("A small errand", "square", side=True))
        g = self.done_game()
        self.assertIn("The story is told", navigation.main_objective(g)["text"])
        self.assertIn("A small errand", [o["text"] for o in navigation.objectives(g)])

    def test_an_area_main_objective_comes_first(self):
        self.inject(OBJECTIVES=lambda g, add: add("Go to the gate", "gate"))
        g = self.done_game()
        objs = navigation.objectives(g)
        self.assertEqual([o["text"] for o in objs if not o["side"]], ["Go to the gate"])
        self.assertFalse(any("The story is told" in o["text"] for o in objs))
        self.assertEqual(navigation.main_objective(g)["room"], "gate")

    def test_the_area_objective_appears_once(self):
        self.inject(OBJECTIVES=lambda g, add: add("Go to the gate", "gate"))
        texts = [o["text"] for o in navigation.objectives(self.done_game())]
        self.assertEqual(texts.count("Go to the gate"), 1)

    def test_boss_tip_reads_core_then_area_tips(self):
        self.assertEqual(navigation.boss_tip("throne_room"), navigation.BOSS_TIPS["throne_room"])
        self.assertIsNone(navigation.boss_tip("hall"))
        self.inject(BOSS_TIPS={"hall": "Mind the stub."})
        self.assertEqual(navigation.boss_tip("hall"), "Mind the stub.")
        self.assertEqual(navigation.boss_tip("throne_room"), navigation.BOSS_TIPS["throne_room"])

    def test_the_danger_ahead_screen_shows_an_area_tip(self):
        self.inject(BOSS_TIPS={"zz_boss": "Mind the stub."})
        g = new_game()
        g.player.oil = 5
        g.room_id = "hall"
        room = stub_room(boss="zz_flag", boss_name="Nobody", exits={"w": "hall"})
        hall = dict(ROOMS["hall"], exits=dict(ROOMS["hall"]["exits"], s="zz_boss"))
        with mock.patch.dict(ROOMS, {"zz_boss": room, "hall": hall}):
            out = run(g, "s", answers=["n"])
        self.assertIn("DANGER AHEAD", out)
        self.assertIn("Tip: Mind the stub.", out)


# ============================================================================ C6 dealer
class DealerRegionTests(unittest.TestCase):
    RING = 7

    def setUp(self):
        self.g = new_game()
        info = lambda i, **kw: dict({"id": i, "ring": self.RING, "levels": "1", "gear": "x", "blurb": ""}, **kw)
        self.regions = {"ZZ Base": info("ZZ Base"), "ZZ Annex": info("ZZ Annex", dealer=False),
                        "ZZ Late": info("ZZ Late", dealer_after="zz_after")}
        rooms = {}
        for i in range(4):
            rooms["zz_b%d" % i] = stub_room(region="ZZ Base", pos=(i, 0))
            rooms["zz_a%d" % i] = stub_room(region="ZZ Annex", pos=(i, 0))
            rooms["zz_l%d" % i] = stub_room(region="ZZ Late", pos=(i, 0))
        rooms["zz_b_off"] = stub_room(region="ZZ Base", pos=(9, 0), no_dealer=True)
        for patcher in (mock.patch.dict(REGION_INFO, self.regions), mock.patch.dict(ROOMS, rooms)):
            patcher.start()
            self.addCleanup(patcher.stop)
        dealer._seats.pop(self.RING, None)
        self.addCleanup(dealer._seats.pop, self.RING, None)

    def sat(self, days=80):
        return {dealer.room_for(self.g, self.RING, 20000 + d) for d in range(days)}

    def test_seats_exclude_dealer_false_regions_and_no_dealer_rooms(self):
        seats = dealer.seats(self.RING)
        self.assertEqual(sorted(seats), sorted(["zz_b0", "zz_b1", "zz_b2", "zz_b3"] + ["zz_l0", "zz_l1", "zz_l2", "zz_l3"]))
        self.assertNotIn("zz_b_off", seats)

    def test_room_for_honours_dealer_false_and_no_dealer(self):
        sat = self.sat()
        self.assertFalse({r for r in sat if r and r.startswith("zz_a")})
        self.assertNotIn("zz_b_off", sat)

    def test_dealer_after_is_read_live(self):
        before = self.sat()
        self.assertFalse({r for r in before if r and r.startswith("zz_l")})
        self.assertTrue({r for r in before if r and r.startswith("zz_b")})
        self.g.flags["zz_after"] = True
        after = self.sat()
        self.assertTrue({r for r in after if r and r.startswith("zz_l")})
        self.assertEqual(dealer.seats(self.RING), dealer.seats(self.RING))      # the cached seats did not change
        del self.g.flags["zz_after"]
        self.assertFalse({r for r in self.sat() if r and r.startswith("zz_l")})

    def test_a_lit_base_leaves_only_the_gated_region_once_the_flag_is_set(self):
        for i in range(4):
            self.g.flags["lit_zz_b%d" % i] = True
        self.assertEqual(self.sat(), {None})
        self.g.flags["zz_after"] = True
        self.assertTrue(all(r and r.startswith("zz_l") for r in self.sat()))

    def test_check_passes_with_two_regions_in_one_ring(self):
        base = dealer.check(DEALER)
        twin = {"id": "ZZ Twin", "ring": 1, "levels": "1", "gear": "x", "blurb": ""}
        with mock.patch.dict(REGION_INFO, {"ZZ Twin": twin}):
            self.assertEqual(dealer.check(DEALER), base)

    def test_check_still_wants_a_config_for_every_ring(self):
        gone = copy.deepcopy(DEALER)
        gone["rings"].pop("1")
        self.assertTrue(any("rings" in e for e in dealer.check(gone)))


if __name__ == "__main__":
    unittest.main()
