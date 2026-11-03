"""Save migrations in practice: real old saves load, are backed up first, and damaged saves are recoverable.

The fixtures in tests/fixtures/saves/ are real saves in older shapes (built by tools/make_save_fixtures.py from a
played-in game). They are never regenerated to follow the code: if the format changes, add a migration and a new
fixture, and these old ones must keep loading.
"""
import contextlib
import copy
import glob
import io
import json
import os
import random
import re
import shutil
import tempfile
import unittest
from unittest import mock

from lamplighter import gear, save, ui
from lamplighter.content import ITEMS
from lamplighter.engine import Game
from tests.helpers import new_game, quiet_ui, run, temp_home

import main as main_script

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "saves")
DEALER_BOUGHT = {"19990": [0, 2], "20000": [1]}


def fixture_path(name):
    return os.path.join(FIXTURES, name)


def fixture_bytes(name):
    with open(fixture_path(name), "rb") as f:
        return f.read()


def install(name, slot="main"):
    """Put a fixture where the game looks for the save."""
    os.makedirs(save.paths.saves_dir(), exist_ok=True)
    shutil.copyfile(fixture_path(name), save.path_for(slot))


def put(text, slot="main"):
    os.makedirs(save.paths.saves_dir(), exist_ok=True)
    with open(save.path_for(slot), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def file_bytes(slot="main", suffix=""):
    with open(save.path_for(slot)[:-5] + suffix + ".json", "rb") as f:
        return f.read()


def saves_listing():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(save.paths.saves_dir(), "*")))


def reset_gear():
    """Like a fresh process: no forged items registered, id counter at zero."""
    for k in [k for k in ITEMS if re.fullmatch(r"g\d+", k)]:
        del ITEMS[k]
    gear._counter[0] = 0


def play(script, fn, *args):
    """Run fn with scripted answers; returns (result, everything printed)."""
    quiet_ui()
    ui.io.script = list(script)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = fn(*args)
    return result, out.getvalue()


class RegistryTests(unittest.TestCase):
    def test_version_and_migrations_agree(self):
        save.check_registry()
        self.assertEqual(save.SAVE_VERSION, max(save.MIGRATIONS) + 1)
        self.assertEqual(sorted(save.MIGRATIONS), list(range(save.SAVE_VERSION)))

    def test_check_registry_fails_when_a_version_is_bumped_without_its_migration(self):
        old = save.SAVE_VERSION
        try:
            save.SAVE_VERSION = old + 1
            with self.assertRaises(save.SaveError):
                save.check_registry()
        finally:
            save.SAVE_VERSION = old

    def test_check_registry_fails_when_a_step_is_missing(self):
        old = dict(save.MIGRATIONS)
        try:
            del save.MIGRATIONS[0]
            with self.assertRaises(save.SaveError):
                save.check_registry()
        finally:
            save.MIGRATIONS.clear()
            save.MIGRATIONS.update(old)

    def test_every_fixture_format_is_covered(self):
        versions = {json.loads(fixture_bytes(n)).get("save_version", 0) for n in
                    ("v0_prototype.json", "v1_pre_m5.json", "v2_current.json")}
        self.assertEqual(versions, {0, 1, 2})
        self.assertEqual(max(versions), save.SAVE_VERSION,
                         "a new save format needs a new fixture (tools/make_save_fixtures.py) and a test here")


class MigrationFunctionTests(unittest.TestCase):
    def test_1_to_2_moves_the_dealer_flags(self):
        d = save._migrate_1_to_2({"flags": {"dealer_bought": {"5": [1]}, "dealer_salt": 4, "x": 1}})
        self.assertEqual(d["dealers"], {"salt": 4, "bought": {"5": [1]}, "restocks": {}})
        self.assertEqual(d["flags"], {"x": 1})

    def test_1_to_2_survives_odd_input(self):
        odd_flags = [None, [], "x", 5, {}, {"dealer_bought": None}, {"dealer_bought": []}, {"dealer_bought": [1, 2]},
                     {"dealer_bought": "no"}, {"dealer_bought": {"3": "x", "4": [1, "a", None, True]}},
                     {"dealer_salt": None}, {"dealer_salt": "7"}, {"dealer_salt": True}, {"dealer_salt": 2.5}]
        odd_dealers = [None, [], "x", 3, {}, {"salt": "s"}, {"bought": []}, {"bought": {"1": [0]}, "restocks": 5},
                       {"salt": 9, "bought": {"1": [0]}, "restocks": {"1": 2}}]
        for fl in odd_flags:
            for dl in odd_dealers:
                d = {"flags": copy.deepcopy(fl)}
                if dl is not None:
                    d["dealers"] = copy.deepcopy(dl)
                before = copy.deepcopy(d)
                out = save._migrate_1_to_2(d)
                self.assertEqual(d, before, "the input must not be changed")
                dealers = out["dealers"]
                self.assertEqual(set(dealers) >= {"salt", "bought", "restocks"}, True)
                self.assertIsInstance(dealers["salt"], int)
                self.assertIsInstance(dealers["bought"], dict)
                self.assertTrue(all(isinstance(k, str) and isinstance(v, list) for k, v in dealers["bought"].items()))
                self.assertNotIn("dealer_bought", out["flags"])
                self.assertNotIn("dealer_salt", out["flags"])
                self.assertEqual(save._migrate_1_to_2(out), out, "running it twice must change nothing more")

    def test_1_to_2_keeps_an_existing_dealers_block_and_merges_old_purchases(self):
        d = save._migrate_1_to_2({"flags": {"dealer_bought": {"1": [0, 1], "2": [2]}, "dealer_salt": 8},
                                  "dealers": {"salt": 5, "bought": {"1": [1, 2]}, "restocks": {"1": 1}, "extra": True}})
        self.assertEqual(d["dealers"]["salt"], 5)
        self.assertEqual(d["dealers"]["bought"], {"1": [1, 2, 0], "2": [2]})
        self.assertEqual(d["dealers"]["restocks"], {"1": 1})
        self.assertTrue(d["dealers"]["extra"])

    def test_1_to_2_with_no_flags_at_all(self):
        out = save._migrate_1_to_2({})
        self.assertEqual(out["dealers"], {"salt": 0, "bought": {}, "restocks": {}})
        self.assertEqual(out["flags"], {})

    def test_1_to_2_given_something_that_is_not_a_save(self):
        for junk in (None, [], "x", 5):
            self.assertEqual(save._migrate_1_to_2(junk)["dealers"]["bought"], {})

    def test_0_to_1_survives_odd_input_and_keeps_what_is_there(self):
        d = {"flags": {"a": 1}, "stats": {"kills": 3}, "moves": 40, "player": {"name": "X"}}
        out = save._migrate_0_to_1(d)
        self.assertEqual(out["flags"], {"a": 1})
        self.assertEqual(out["stats"], {"kills": 3})
        self.assertEqual(out["moves"], 40)
        self.assertEqual(out["player"], {"name": "X"})
        for junk in (None, [], "x", 5, {"flags": [], "stats": None, "visited": "no", "moves": "7", "difficulty": "hard"}):
            out = save._migrate_0_to_1(junk)
            self.assertIsInstance(out["flags"], dict)
            self.assertIsInstance(out["stats"], dict)
            self.assertIsInstance(out["visited"], list)
            self.assertIsInstance(out["moves"], int)
            self.assertEqual(save._migrate_0_to_1(out), out)

    def test_migrating_random_junk_never_raises(self):
        rng = random.Random(3)

        def junk(depth=0):
            kinds = ["int", "str", "none", "bool", "float"] + (["list", "dict"] if depth < 3 else [])
            k = rng.choice(kinds)
            if k == "int":
                return rng.randint(-5, 50)
            if k == "str":
                return rng.choice(["", "x", "5"])
            if k == "none":
                return None
            if k == "bool":
                return rng.random() < 0.5
            if k == "float":
                return rng.random()
            if k == "list":
                return [junk(depth + 1) for _ in range(rng.randint(0, 3))]
            keys = ["flags", "stats", "dealers", "dealer_bought", "dealer_salt", "bought", "salt", "restocks", "visited", "5"]
            return {rng.choice(keys): junk(depth + 1) for _ in range(rng.randint(0, 5))}

        for _ in range(600):
            d = junk()
            if isinstance(d, dict) and rng.random() < 0.5:
                d["flags"] = {rng.choice(["dealer_bought", "dealer_salt"]): junk(2)}
            for step in (0, 1):
                try:
                    out = save.MIGRATIONS[step](d)
                except Exception as e:  # pragma: no cover - the failure message is the point
                    self.fail("migration %d raised %r on %r" % (step, e, d))
                self.assertIsInstance(out, dict)

    def test_migrate_refuses_a_save_that_is_not_a_dict_or_has_a_bad_version(self):
        for data in ([], None, "x", {"save_version": "2"}, {"save_version": -1}, {"save_version": 1.5}, {"save_version": True}):
            with self.assertRaises(save.SaveDamaged):
                save.migrate(data)


class FixtureLoadTests(unittest.TestCase):
    def setUp(self):
        reset_gear()

    def load(self, name):
        with temp_home():
            install(name)
            quiet_ui()
            return Game.load()

    def check_current_shape(self, g):
        """What every fixture from M0-M4 on must come back as."""
        p = g.player
        self.assertEqual((p.name, p.cls, p.level, p.xp, p.points), ("Fixture", "wayfarer", 4, 31, 2))
        self.assertEqual((p.gold, p.gems), (245, 9))
        self.assertEqual(g.room_id, "tavern")
        self.assertEqual(g.quests, {"main": 1, "lamps": 2})
        self.assertEqual(g.stats, {"kills": 14, "battles": 9, "deaths": 1})
        self.assertEqual(g.moves, 87)
        self.assertTrue(g.flags["met_orrin"])
        self.assertEqual(g.flags["visited_regions"], ["Hollowmere"])
        self.assertNotIn("dealer_bought", g.flags)
        self.assertNotIn("dealer_salt", g.flags)
        self.assertEqual(g.dealers["salt"], 3)
        self.assertEqual(g.dealers["bought"], DEALER_BOUGHT)
        self.assertEqual(g.town["invited"], ["market", "home"])
        self.assertEqual(g.town["stash_level"], 2)
        self.assertEqual(g.forge["heat"], {"gear:epic": 2})
        self.assertEqual(len(g.forge["jobs"]), 1)
        self.assertEqual(g.forge["jobs"][0]["item"], "g2")
        self.assertEqual(g.forge["jobs"][0]["loaner"], "g6")

    def check_gear(self, g):
        p = g.player
        self.assertEqual(sorted(p.gear), ["g2", "g3", "g4", "g5", "g6"])
        for iid in p.gear:
            self.assertIs(ITEMS[iid], p.gear[iid], "%s must be registered as an item" % iid)
        self.assertEqual(ITEMS["g2"]["rarity"], "epic")
        self.assertEqual(ITEMS["g3"]["rarity"], "ultra")
        self.assertEqual(ITEMS["g5"]["rarity"], "legendary")
        self.assertEqual(p.equipment["armor"], "g3")
        self.assertEqual(p.equipment["weapon"], "g6")
        self.assertTrue(p.has_item("homecoming_charm"))
        # the id counter must clear every saved id, or the next forged item would overwrite one
        self.assertGreaterEqual(gear._counter[0], 6)
        fresh = gear.make("hunting_spear", "epic", random.Random(1))
        self.assertNotIn(fresh["id"], p.gear)
        self.assertGreater(int(fresh["id"][1:]), 6)
        for iid in p.gear:
            self.assertIs(ITEMS[iid], p.gear[iid], "making a new item must not replace a saved one")

    def test_v2_current(self):
        g = self.load("v2_current.json")
        self.check_current_shape(g)
        self.check_gear(g)
        self.assertEqual(g.dealers["restocks"], {"20000": 1})
        self.assertEqual(g.load_note, "")

    def test_v1_pre_m5(self):
        g = self.load("v1_pre_m5.json")
        self.check_current_shape(g)
        self.check_gear(g)
        self.assertEqual(g.dealers["restocks"], {})
        self.assertIn("older version", g.load_note)

    def test_v0_prototype(self):
        g = self.load("v0_prototype.json")
        p = g.player
        self.assertEqual((p.name, p.cls, p.level, p.xp), ("Fixture", "wayfarer", 4, 31))
        self.assertEqual(p.gold, json.loads(fixture_bytes("v0_prototype.json"))["player"]["gold"])
        self.assertEqual(p.equipment, {"weapon": "hook", "armor": "oilskin", "trinket": None})
        self.assertEqual(p.inventory, {"draught": 3, "oil": 1, "homecoming_charm": 1})   # the charm is added below
        self.assertEqual((p.gems, p.gear, p.stash, p.spells, p.dread), (0, {}, {}, [], 0))
        self.assertEqual(p.lantern["trim"], False)
        self.assertEqual(g.room_id, "tavern")
        self.assertEqual(g.visited, {"hall", "square", "tavern"})
        self.assertEqual(g.last_rest, "hall")
        self.assertEqual(g.quests, {"main": 1})
        self.assertTrue(g.flags["met_orrin"])
        self.assertEqual(g.moves, 87)
        self.assertEqual(g.stats["kills"], 14)
        # everything added since starts as in a new game
        self.assertEqual(g.town, Game().town)
        self.assertEqual(g.forge, Game().forge)
        self.assertEqual(g.dealers, {"salt": 0, "bought": {}, "restocks": {}})
        self.assertEqual(g.anchors, [])
        self.assertIn("older version", g.load_note)
        self.assertIn("will be upgraded the next time you save", g.load_note)
        # a main quest past the start gets the charm a save from before it never had
        self.assertTrue(p.has_item("homecoming_charm"))

    def test_loading_does_not_change_the_save_file(self):
        for name in ("v0_prototype.json", "v1_pre_m5.json", "v2_current.json"):
            with temp_home():
                install(name)
                quiet_ui()
                Game.load()
                self.assertEqual(file_bytes(), fixture_bytes(name), name)

    def test_the_game_after_loading_still_plays(self):
        for name in ("v0_prototype.json", "v1_pre_m5.json"):
            with temp_home():
                install(name)
                quiet_ui()
                g = Game.load()
                out = run(g, "look", "stats", "i")
                self.assertTrue(out.strip())
                run(g, "save")
                self.assertEqual(json.loads(file_bytes())["save_version"], save.SAVE_VERSION)


class BackupBeforeMigrateTests(unittest.TestCase):
    def setUp(self):
        reset_gear()

    def test_an_old_save_is_copied_once_before_it_is_upgraded(self):
        for n, name in ((0, "v0_prototype.json"), (1, "v1_pre_m5.json")):
            with temp_home():
                install(name)
                quiet_ui()
                g = Game.load()
                keep = save.path_for()[:-5] + ".v%d.bak.json" % n
                self.assertTrue(os.path.exists(keep), keep)
                self.assertEqual(file_bytes(suffix=".v%d.bak" % n), fixture_bytes(name))
                self.assertIn(keep, g.load_note)
                self.assertIn("format %d" % n, g.load_note)
                self.assertNotIn("\n", g.load_note)

    def test_a_current_save_makes_no_copy(self):
        with temp_home():
            install("v2_current.json")
            quiet_ui()
            Game.load()
            self.assertEqual(saves_listing(), ["main.json"])

    def test_an_existing_backup_is_never_overwritten(self):
        with temp_home():
            install("v1_pre_m5.json")
            put("the first copy, which must survive", "main.v1.bak")
            quiet_ui()
            g = Game.load()
            self.assertEqual(file_bytes(suffix=".v1.bak"), b"the first copy, which must survive")
            # the real original must not be claimed as kept by a file that is something else
            self.assertEqual(file_bytes(suffix=".v1.bak.2"), fixture_bytes("v1_pre_m5.json"))
            self.assertIn("main.v1.bak.2.json", g.load_note)
            self.assertNotIn("already kept", g.load_note)
            g2 = Game.load()
            self.assertIn("already kept at", g2.load_note)          # now the copy really is there
            self.assertIn("main.v1.bak.2.json", g2.load_note)

    def test_loading_twice_before_saving_keeps_the_first_copy(self):
        with temp_home():
            install("v1_pre_m5.json")
            quiet_ui()
            Game.load()
            Game.load()
            self.assertEqual(file_bytes(suffix=".v1.bak"), fixture_bytes("v1_pre_m5.json"))

    def test_after_saving_the_file_is_current_and_loading_makes_no_new_copy(self):
        with temp_home():
            install("v1_pre_m5.json")
            quiet_ui()
            g = Game.load()
            g.save(quiet=True)
            self.assertEqual(json.loads(file_bytes())["save_version"], save.SAVE_VERSION)
            before = saves_listing()
            g2 = Game.load()
            self.assertEqual(saves_listing(), before)
            self.assertEqual(g2.load_note, "")
            # the original is still there, byte for byte
            self.assertEqual(file_bytes(suffix=".v1.bak"), fixture_bytes("v1_pre_m5.json"))

    def test_a_copy_that_cannot_be_made_is_reported_but_the_save_still_loads(self):
        with temp_home():
            install("v1_pre_m5.json")
            quiet_ui()
            with mock.patch("lamplighter.save.shutil.copyfile", side_effect=OSError("disk full")):
                g = Game.load()
            self.assertIn("could not be made", g.load_note)
            self.assertIn("disk full", g.load_note)
            self.assertEqual(g.player.name, "Fixture")
            self.assertEqual(file_bytes(), fixture_bytes("v1_pre_m5.json"))

    def test_reading_without_a_copy(self):
        with temp_home():
            install("v1_pre_m5.json")
            data, note = save.read_info(keep_copy=False)
            self.assertEqual(note, "")
            self.assertEqual(data["save_version"], save.SAVE_VERSION)
            self.assertEqual(saves_listing(), ["main.json"])


class NewerSaveTests(unittest.TestCase):
    def newer(self):
        d = json.loads(fixture_bytes("v2_current.json"))
        d["save_version"] = save.SAVE_VERSION + 3
        d["something_new"] = {"a": [1, 2]}
        return json.dumps(d, indent=1)

    def test_error_says_what_to_do_and_the_file_is_untouched(self):
        with temp_home():
            put(self.newer())
            before = file_bytes()
            with self.assertRaises(save.SaveTooNew) as ctx:
                save.read()
            msg = str(ctx.exception)
            self.assertIn("newer version", msg)
            self.assertIn("save format %d" % (save.SAVE_VERSION + 3), msg)
            self.assertIn("Update the game", msg)
            self.assertIn("has not been changed", msg)
            with self.assertRaises(save.SaveTooNew):
                Game.load()
            self.assertEqual(file_bytes(), before)
            self.assertEqual(saves_listing(), ["main.json"])

    def test_continue_leaves_it_alone_and_does_not_offer_a_new_game_over_it(self):
        with temp_home():
            put(self.newer())
            before = file_bytes()
            g, out = play([], main_script.continue_game)
            self.assertIsNone(g)
            self.assertIn("newer version", out)
            self.assertEqual(file_bytes(), before)
            self.assertEqual(saves_listing(), ["main.json"])

    def test_an_older_game_that_saves_anyway_keeps_a_copy_of_the_newer_save(self):
        with temp_home():
            put(self.newer())
            before = file_bytes()
            g = new_game()
            g.save(quiet=True)
            self.assertEqual(file_bytes(suffix=".v%d.bak" % (save.SAVE_VERSION + 3)), before)
            self.assertEqual(json.loads(file_bytes())["save_version"], save.SAVE_VERSION)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        reset_gear()

    def good_previous(self):
        install("v2_current.json", save.backup_slot("main"))

    def test_unreadable_save_offers_the_previous_one(self):
        with temp_home():
            put("{not json")
            self.good_previous()
            g, out = play(["y"], main_script.continue_game)
            self.assertIsNotNone(g)
            self.assertEqual(g.player.name, "Fixture")
            self.assertIn("could not be read", out)
            self.assertIn("main.damaged.json", out)
            self.assertIn("Fixture, level 4", out)
            self.assertTrue(any("Welcome back, Fixture" in n for n in g.notices))
            self.assertEqual(file_bytes(suffix=".damaged"), b"{not json")           # kept, not deleted
            self.assertEqual(file_bytes(), fixture_bytes("v2_current.json"))        # the previous save is now the save
            self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"))

    def test_truncated_save(self):
        with temp_home():
            whole = fixture_bytes("v2_current.json").decode("utf-8")
            put(whole[:len(whole) // 2])
            self.good_previous()
            g, out = play(["yes"], main_script.continue_game)
            self.assertIsNotNone(g)
            self.assertEqual(file_bytes(suffix=".damaged"), whole[:len(whole) // 2].encode("utf-8"))

    def test_declining_changes_nothing_and_asks_again_next_time(self):
        with temp_home():
            put("{not json")
            self.good_previous()
            before = saves_listing()
            g, out = play(["n"], main_script.continue_game)
            self.assertIsNone(g)
            self.assertIn("Nothing has been changed", out)
            self.assertEqual(saves_listing(), before)                      # not even a rename
            self.assertEqual(file_bytes(), b"{not json")
            self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"))
            g, out = play(["y"], main_script.continue_game)                # asked again; this time it is accepted
            self.assertEqual(g.player.name, "Fixture")
            self.assertEqual(file_bytes(suffix=".damaged"), b"{not json")

    def test_declining_an_old_format_previous_save_leaves_no_stray_copy(self):
        with temp_home():
            put("{not json")
            install("v1_pre_m5.json", save.backup_slot("main"))
            g, out = play(["n"], main_script.continue_game)
            self.assertIsNone(g)
            self.assertEqual(saves_listing(), ["main.bak.json", "main.json"])   # looking at it made no .v1.bak copy

    def test_accepting_an_old_format_previous_save_upgrades_it_with_a_copy(self):
        with temp_home():
            put("{not json")
            install("v1_pre_m5.json", save.backup_slot("main"))
            g, out = play(["y"], main_script.continue_game)
            self.assertEqual(g.player.name, "Fixture")
            self.assertEqual(file_bytes(suffix=".v1.bak"), fixture_bytes("v1_pre_m5.json"))
            self.assertIn("older version", out)

    def test_the_player_is_not_shown_parser_jargon(self):
        with temp_home():
            put('{"save_version": 2, "player": ')
            g, out = play([], main_script.continue_game)
            for jargon in ("Expecting", "char ", "JSON", "line 1"):
                self.assertNotIn(jargon, out)
            self.assertIn("damaged", out)

    def test_a_previous_save_from_a_newer_game_is_explained(self):
        with temp_home():
            put("{not json")
            newer = json.loads(fixture_bytes("v2_current.json"))
            newer["save_version"] = save.SAVE_VERSION + 1
            put(json.dumps(newer), save.backup_slot("main"))
            g, out = play([], main_script.continue_game)
            self.assertIsNone(g)
            self.assertIn("previous save is from a newer version", out)
            self.assertNotIn("no earlier save", out)
            self.assertEqual(file_bytes(suffix=".damaged"), b"{not json")

    def test_no_previous_save(self):
        with temp_home():
            put("{not json")
            g, out = play([], main_script.continue_game)
            self.assertIsNone(g)
            self.assertIn("no earlier save", out)
            self.assertEqual(file_bytes(suffix=".damaged"), b"{not json")

    def test_previous_save_damaged_too(self):
        with temp_home():
            put("{not json")
            put("also {broken", save.backup_slot("main"))
            g, out = play([], main_script.continue_game)
            self.assertIsNone(g)
            self.assertIn("no earlier save", out)
            self.assertEqual(file_bytes(suffix=".bak"), b"also {broken")           # left alone

    def test_empty_file_and_wrong_shapes_count_as_damaged(self):
        for text in ("", "[]", "null", '{"save_version": 2}', '{"save_version": 2, "player": 5}',
                     '{"save_version": "two"}'):
            with temp_home():
                put(text)
                self.good_previous()
                g, out = play(["y"], main_script.continue_game)
                self.assertIsNotNone(g, text)
                self.assertEqual(file_bytes(suffix=".damaged"), text.encode("utf-8"), text)

    def test_a_save_with_the_wrong_kind_of_player_is_damaged_not_a_crash(self):
        with temp_home():
            d = json.loads(fixture_bytes("v2_current.json"))
            d["player"]["inventory"] = 7
            d["player"]["gear"] = "x"
            put(json.dumps(d))
            with self.assertRaises(save.SaveDamaged):
                Game.load()

    def test_missing_main_with_a_previous_save(self):
        with temp_home():
            self.good_previous()
            g, out = play(["y"], main_script.continue_game)
            self.assertEqual(g.player.name, "Fixture")
            self.assertIn("missing", out)
            self.assertNotIn("damaged.json", out)

    def test_title_screen_offers_continue_when_only_the_previous_save_is_left(self):
        with temp_home():
            self.good_previous()
            g, out = play(["1", "y"], main_script.title_screen)
            self.assertEqual(g.player.name, "Fixture")

    def test_a_second_damaged_file_does_not_replace_the_first(self):
        with temp_home():
            put("first")
            self.assertTrue(save.set_aside().endswith("main.damaged.json"))
            put("second")
            self.assertTrue(save.set_aside().endswith("main.damaged.2.json"))
            self.assertEqual(file_bytes(suffix=".damaged"), b"first")
            self.assertEqual(file_bytes(suffix=".damaged.2"), b"second")
            self.assertIsNone(save.set_aside())

    def test_saving_over_a_damaged_file_does_not_wreck_the_good_previous_save(self):
        with temp_home():
            put("{not json")
            self.good_previous()
            new_game().save(quiet=True)
            self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"))
            self.assertEqual(file_bytes(suffix=".damaged"), b"{not json")

    def test_restore_will_not_replace_a_live_save(self):
        with temp_home():
            install("v2_current.json")
            self.good_previous()
            with self.assertRaises(save.SaveError):
                save.restore_backup()

    def test_in_game_load_of_a_damaged_save_reports_and_changes_nothing(self):
        with temp_home():
            put("{not json")
            g = new_game()
            g.player.gold = 777
            _, out = play(["y"], g.handle, "load")
            self.assertIn("could not be read", out)
            self.assertEqual(g.player.gold, 777)
            self.assertEqual(file_bytes(), b"{not json")

    def test_in_game_load_shows_the_upgrade_line(self):
        with temp_home():
            install("v1_pre_m5.json")
            g = new_game()
            _, out = play(["y"], g.handle, "load")
            self.assertEqual(g.player.name, "Fixture")
            ui.io.script = []
            out = "\n".join(re.sub(r"\x1b\[[0-9;]*m", "", n) for n in g.notices) if isinstance(g.notices, list) else ""
            self.assertIn("older version", out)


class StabilityTests(unittest.TestCase):
    def setUp(self):
        reset_gear()

    def dumped(self, g):
        return json.dumps(g.to_dict(), sort_keys=True)

    def test_load_save_load_is_stable_for_every_fixture(self):
        for name in ("v0_prototype.json", "v1_pre_m5.json", "v2_current.json"):
            with temp_home():
                install(name)
                quiet_ui()
                g1 = Game.load()
                g1.save(quiet=True)
                g2 = Game.load()
                self.assertEqual(self.dumped(g1), self.dumped(g2), name)
                g2.save(quiet=True)
                g3 = Game.load()
                self.assertEqual(self.dumped(g2), self.dumped(g3), name)
                # and the file the game wrote is exactly what loading it again would write
                self.assertEqual(json.loads(file_bytes())["save_version"], save.SAVE_VERSION)

    def test_a_current_save_survives_loading_unchanged(self):
        with temp_home():
            install("v2_current.json")
            quiet_ui()
            g = Game.load()
            expected = json.loads(fixture_bytes("v2_current.json"))
            actual = json.loads(json.dumps(g.to_dict()))
            for key in expected:
                if key in ("settings", "save_version", "game_version"):
                    continue                                    # settings come from the UI; the versions are stamped on write
                if key == "room_items":
                    # rooms added after the save was made get their floor items filled in on load (core C9)
                    for rid, items in expected[key].items():
                        self.assertEqual(actual[key][rid], items, rid)
                    self.assertTrue(set(actual[key]) >= set(expected[key]))
                    continue
                self.assertEqual(actual[key], expected[key], key)
            self.assertEqual(set(actual) - set(expected), set())

    def test_v1_and_v2_fixtures_describe_the_same_game(self):
        with temp_home():
            install("v1_pre_m5.json")
            quiet_ui()
            a = Game.load().to_dict()
            install("v2_current.json")
            reset_gear()
            b = Game.load().to_dict()
        a["dealers"]["restocks"] = b["dealers"]["restocks"]     # v1 never recorded restocks
        for d in (a, b):
            d.pop("game_version", None)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class SandboxTests(unittest.TestCase):
    def test_the_tests_never_use_the_players_real_save_folder(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("LAMPLIGHTER_HOME", None)
            real = os.path.abspath(save.paths.saves_dir())
        here = os.path.abspath(save.paths.saves_dir())
        self.assertNotEqual(here, real)
        self.assertFalse(here.startswith(os.path.dirname(real) + os.sep), "tests would write to %s" % real)
        self.assertTrue(here.startswith(os.path.abspath(tempfile.gettempdir())), here)


class MigrationDefaultsTests(unittest.TestCase):
    def test_0_to_1_gives_a_bare_prototype_save_the_starting_values_of_a_new_game(self):
        out = save._migrate_0_to_1({})
        self.assertEqual((out["last_rest"], out["difficulty"], out["diff_name"], out["moves"]), ("hall", 1.0, "Normal", 0))
        self.assertEqual((out["visited"], out["flags"], out["stats"], out["quests"], out["room_items"]), ([], {}, {}, {}, {}))

    def test_0_to_1_keeps_what_a_prototype_save_has(self):
        d = {"visited": ["hall", "inn"], "last_rest": "inn", "difficulty": 1.3, "diff_name": "Hard", "moves": 9}
        out = save._migrate_0_to_1(d)
        for k, v in d.items():
            self.assertEqual(out[k], v, k)


class ShapeCheckTests(unittest.TestCase):
    """save.read_info must refuse a save of the wrong shape by itself, not rely on Game.load to trip over it."""

    def damaged(self, change):
        d = json.loads(fixture_bytes("v2_current.json"))
        change(d)
        with temp_home():
            put(json.dumps(d))
            with self.assertRaises(save.SaveDamaged):
                save.read_info()

    def test_wrong_kinds_of_data_are_damaged(self):
        for key, bad in (("moves", "lots"), ("moves", True), ("moves", 2.5), ("stats", []), ("player", 5), ("room", 7),
                         ("flags", None), ("quests", []), ("visited", {}), ("room_items", []), ("last_rest", 1),
                         ("diff_name", 3), ("difficulty", "hard"), ("difficulty", None)):
            self.damaged(lambda d, key=key, bad=bad: d.__setitem__(key, bad))

    def test_a_missing_piece_is_damaged(self):
        for key in save.REQUIRED:
            self.damaged(lambda d, key=key: d.pop(key))

    def test_nan_and_infinity_anywhere_make_a_save_damaged(self):
        # even in free-form parts like flags: write() refuses them, so a save holding one could never be saved again
        text = fixture_bytes("v2_current.json").decode("utf-8")
        for bad in ("NaN", "Infinity", "-Infinity"):
            with temp_home():
                put(text.replace('"met_orrin": true', '"met_orrin": %s' % bad))
                self.assertIn(bad, file_bytes().decode("utf-8"))
                with self.assertRaises(save.SaveDamaged):
                    save.read_info()
                with self.assertRaises(save.SaveDamaged):
                    Game.load()

    def test_a_good_save_passes_and_a_whole_number_in_a_float_slot_is_fine(self):
        d = json.loads(fixture_bytes("v2_current.json"))
        d["difficulty"] = 1
        with temp_home():
            put(json.dumps(d))
            self.assertEqual(save.read_info()[0]["difficulty"], 1)

    def test_a_migration_that_blows_up_means_damaged_not_a_crash(self):
        with temp_home():
            install("v1_pre_m5.json")
            boom = mock.Mock(side_effect=RuntimeError("surprise"))
            with mock.patch.dict(save.MIGRATIONS, {1: boom}):
                with self.assertRaises(save.SaveDamaged):
                    save.read_info()
                with self.assertRaises(save.SaveDamaged):
                    Game.load()

    def test_a_byte_order_mark_is_not_damage(self):
        with temp_home():
            put("")
            with open(save.path_for(), "wb") as f:
                f.write(b"\xef\xbb\xbf" + fixture_bytes("v2_current.json"))
            quiet_ui()
            self.assertEqual(Game.load().player.name, "Fixture")
            before = file_bytes()
            new_game().save(quiet=True)
            self.assertEqual(file_bytes(suffix=".bak"), before)           # rotated as a good save, not set aside
            self.assertEqual(saves_listing(), ["main.bak.json", "main.json"])


class WriteTests(unittest.TestCase):
    def test_a_save_goes_through_a_temp_file_and_leaves_nothing_behind(self):
        with temp_home():
            real = os.replace
            calls = []

            def spy(src, dst):
                calls.append((os.path.basename(src), os.path.basename(dst)))
                return real(src, dst)
            with mock.patch("lamplighter.save.os.replace", spy):
                new_game().save(quiet=True)
                new_game().save(quiet=True)
            self.assertEqual(calls, [("main.json.tmp", "main.json"), ("main.json.tmp", "main.json")])
            self.assertEqual(saves_listing(), ["main.bak.json", "main.json"])

    def test_a_failed_save_leaves_the_old_one_whole_and_no_temp_file(self):
        with temp_home():
            install("v2_current.json")
            before = file_bytes()
            with mock.patch("lamplighter.save.os.replace", side_effect=OSError("disk full")):
                g = new_game()
                _, out = play([], g.save)
            self.assertIn("Could not save", out)
            self.assertEqual(file_bytes(), before)
            self.assertNotIn("main.json.tmp", saves_listing())

    def test_a_value_the_game_could_not_read_back_is_not_written(self):
        with temp_home():
            install("v2_current.json")
            before = file_bytes()
            g = new_game()
            g.stats["deaths"] = float("nan")
            _, out = play([], g.save)
            self.assertIn("Could not save", out)
            self.assertEqual(file_bytes(), before)
            self.assertEqual(saves_listing(), ["main.json"])

    def test_the_current_save_is_never_missing_while_a_save_is_written(self):
        with temp_home():
            install("v2_current.json")
            seen = []
            real = os.replace

            def spy(src, dst):
                seen.append(os.path.exists(save.path_for()))
                return real(src, dst)
            with mock.patch("lamplighter.save.os.replace", spy):
                new_game().save(quiet=True)
            self.assertEqual(seen, [True])

    def test_a_save_that_cannot_be_opened_is_not_called_damaged_or_touched(self):
        with temp_home():
            os.makedirs(save.path_for())            # opening a folder as a file fails with an OSError of some kind
            g, out = play([], main_script.continue_game)
            self.assertIsNone(g)
            self.assertIn("could not be opened", out)
            self.assertIn("Nothing has been changed", " ".join(out.split()))
            _, out = play([], new_game().save)
            self.assertIn("Could not save", out)
            self.assertTrue(os.path.isdir(save.path_for()))
            self.assertEqual(saves_listing(), ["main.json"])

    def test_a_save_wrong_in_shape_does_not_replace_the_good_previous_save(self):
        for text in ("{}", '{"save_version": 2, "player": 5}', "[]", "null", "", '{"save_version": 2}'):
            with temp_home():
                put(text)
                install("v2_current.json", save.backup_slot("main"))
                new_game().save(quiet=True)
                self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"), text)
                self.assertEqual(file_bytes(suffix=".damaged"), text.encode("utf-8"), text)
                self.assertEqual(json.loads(file_bytes())["save_version"], save.SAVE_VERSION)

    def test_a_deeply_nested_file_is_damaged_not_a_traceback(self):
        deep = "[" * 100000 + "]" * 100000
        deep_obj = '{"a":' * 100000 + "1" + "}" * 100000
        for text in (deep, deep_obj):
            with temp_home():
                put(text)
                install("v2_current.json", save.backup_slot("main"))
                g, out = play(["n"], main_script.continue_game)             # no traceback
                self.assertIsNone(g)
                self.assertIn("damaged", out)
                self.assertEqual(file_bytes(), text.encode("utf-8"))
                _, out = play([], new_game().save)                          # and saving over it sets it aside
                self.assertIn("Game saved", out)
                self.assertEqual(file_bytes(suffix=".damaged"), text.encode("utf-8"))
                self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"))
                self.assertEqual(saves_listing(), ["main.bak.json", "main.damaged.json", "main.json"])


class NeverLoseASaveTests(unittest.TestCase):
    """Whatever is overwritten has been copied somewhere first, and a copy is never overwritten."""

    def setUp(self):
        reset_gear()

    def newer(self, marker, version=None):
        d = json.loads(fixture_bytes("v2_current.json"))
        d["save_version"] = version or save.SAVE_VERSION + 1
        d["marker"] = marker
        return json.dumps(d, indent=1)

    def all_bytes(self):
        out = []
        for name in saves_listing():
            with open(os.path.join(save.paths.saves_dir(), name), "rb") as f:
                out.append(f.read())
        return out

    def test_a_second_newer_save_is_kept_too(self):
        with temp_home():
            a, b = self.newer("A"), self.newer("B")
            put(a)
            new_game().save(quiet=True)
            new_game().save(quiet=True)
            put(b)                                                      # a different newer save appears
            new_game().save(quiet=True)
            new_game().save(quiet=True)
            blobs = self.all_bytes()
            self.assertIn(a.encode("utf-8"), blobs)
            self.assertIn(b.encode("utf-8"), blobs)
            self.assertEqual(file_bytes(suffix=".v%d.bak" % (save.SAVE_VERSION + 1)), a.encode("utf-8"))

    def test_the_same_newer_save_is_not_copied_again_and_again(self):
        with temp_home():
            put(self.newer("A"))
            for _ in range(3):
                put(self.newer("A"))
                new_game().save(quiet=True)
            self.assertEqual([n for n in saves_listing() if ".v" in n], ["main.v%d.bak.json" % (save.SAVE_VERSION + 1)])

    def test_a_newer_save_does_not_push_out_the_good_previous_save(self):
        with temp_home():
            install("v2_current.json", save.backup_slot("main"))
            newer = self.newer("A")
            put(newer)
            new_game().save(quiet=True)
            self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"))
            self.assertEqual(file_bytes(suffix=".v%d.bak" % (save.SAVE_VERSION + 1)), newer.encode("utf-8"))

    def test_a_newer_previous_save_is_copied_before_it_is_rotated_over(self):
        with temp_home():
            newer = self.newer("P")
            put(newer, save.backup_slot("main"))
            install("v2_current.json")
            new_game().save(quiet=True)
            self.assertEqual(json.loads(file_bytes(suffix=".bak"))["save_version"], save.SAVE_VERSION)
            self.assertEqual(file_bytes(slot="main.bak", suffix=".v%d.bak" % (save.SAVE_VERSION + 1)), newer.encode("utf-8"))

    def test_an_old_format_file_written_over_without_being_loaded_first_is_still_kept(self):
        # New game over a v1 file never goes through Continue, so nothing has copied the original yet
        with temp_home():
            install("v1_pre_m5.json")
            new_game().save(quiet=True)
            new_game().save(quiet=True)
            self.assertIn(fixture_bytes("v1_pre_m5.json"), self.all_bytes())
            self.assertEqual(file_bytes(suffix=".v1.bak"), fixture_bytes("v1_pre_m5.json"))

    def test_an_old_format_previous_save_is_kept_before_it_is_rotated_over(self):
        with temp_home():
            install("v0_prototype.json", save.backup_slot("main"))
            install("v2_current.json")
            new_game().save(quiet=True)
            self.assertEqual(file_bytes(slot="main.bak", suffix=".v0.bak"), fixture_bytes("v0_prototype.json"))
            self.assertEqual(json.loads(file_bytes(suffix=".bak"))["save_version"], save.SAVE_VERSION)

    def test_a_damaged_previous_save_is_set_aside_not_rotated_over(self):
        with temp_home():
            put("garbage {", save.backup_slot("main"))
            install("v2_current.json")
            new_game().save(quiet=True)
            self.assertEqual(file_bytes(slot="main.bak", suffix=".damaged"), b"garbage {")
            self.assertEqual(file_bytes(suffix=".bak"), fixture_bytes("v2_current.json"))

    def test_a_second_different_old_save_is_kept_in_its_original_format(self):
        with temp_home():
            quiet_ui()
            first = json.loads(fixture_bytes("v1_pre_m5.json"))
            first["player"]["gold"] = 111
            second = json.loads(fixture_bytes("v1_pre_m5.json"))
            second["player"]["gold"] = 999
            put(json.dumps(first))
            Game.load().save(quiet=True)
            put(json.dumps(second))                                    # the player restored an older backup
            g = Game.load()
            self.assertIn("main.v1.bak.2.json", g.load_note)
            g.save(quiet=True)
            g.save(quiet=True)
            kept = [json.loads(b) for b in self.all_bytes()]
            golds = sorted((k["save_version"], k["player"]["gold"]) for k in kept)
            self.assertIn((1, 111), golds)
            self.assertIn((1, 999), golds)

    def test_a_stale_file_in_the_backup_name_is_not_taken_for_the_original(self):
        with temp_home():
            install("v1_pre_m5.json")
            put("something else", "main.v1.bak")
            quiet_ui()
            g = Game.load()
            g.save(quiet=True)
            g.save(quiet=True)
            self.assertIn(fixture_bytes("v1_pre_m5.json"), self.all_bytes())
            self.assertEqual(file_bytes(suffix=".v1.bak"), b"something else")

    def test_keep_a_copy_reuses_an_identical_copy_and_numbers_a_different_one(self):
        with temp_home():
            put("one")
            path, already = save.keep_a_copy("main", ".x")
            self.assertEqual((os.path.basename(path), already), ("main.x.json", False))
            self.assertEqual(save.keep_a_copy("main", ".x"), (path, True))
            put("two")
            path2, already = save.keep_a_copy("main", ".x")
            self.assertEqual((os.path.basename(path2), already), ("main.x.2.json", False))
            put("three")
            self.assertEqual(os.path.basename(save.keep_a_copy("main", ".x")[0]), "main.x.3.json")
            put("two")
            self.assertEqual(save.keep_a_copy("main", ".x"), (path2, True))
            self.assertEqual(file_bytes(suffix=".x"), b"one")


class SaveCheckTests(unittest.TestCase):
    """A save that is the right shape but means something this game cannot use must not load and then crash."""

    def setUp(self):
        reset_gear()

    def fixture(self):
        return json.loads(fixture_bytes("v2_current.json"))

    def load_dict(self, d):
        with temp_home():
            put(json.dumps(d))
            quiet_ui()
            return Game.load()

    def test_an_unknown_room_is_damaged_and_the_previous_save_is_offered(self):
        d = self.fixture()
        d["room"] = "nowhere_land"
        with temp_home():
            put(json.dumps(d))
            install("v2_current.json", save.backup_slot("main"))
            g, out = play(["y"], main_script.continue_game)
            self.assertEqual(g.room_id, "tavern")
            self.assertEqual(file_bytes(suffix=".damaged"), json.dumps(d).encode("utf-8"))

    def test_things_that_cannot_be_made_sense_of_are_damaged(self):
        def room(d): d["room"] = "nowhere_land"
        def rest(d): d["last_rest"] = "nowhere_land"
        def cls(d): d["player"]["cls"] = "bard"
        def hp(d): d["player"]["hp"] = "lots"
        def agi(d): d["player"]["agi"] = None
        def inf(d): d["player"]["gold"] = float("inf")
        def nan(d): d["stats"]["deaths"] = float("nan")
        def name(d): d["player"]["name"] = 5
        def lantern(d): d["player"]["lantern"] = []
        def gear(d): d["player"]["gear"] = {"g2": {"id": "g9", "base": "hauberk", "rarity": "rare"}}
        def gear_base(d): d["player"]["gear"]["g2"]["base"] = "no_such_item"
        def count(d): d["player"]["inventory"]["oil"] = "many"
        def diff(d): d["difficulty"] = float("nan")
        def diff0(d): d["difficulty"] = 0
        def regions(d): d["flags"]["visited_regions"] = -1
        def town(d): d["town"] = "x"
        def forge(d): d["forge"] = 7
        def anchors(d): d["anchors"] = 3
        def settings(d): d["settings"] = []
        def visited(d): d["visited"] = [1, 2]
        def job_item(d): d["forge"]["jobs"][0]["item"] = "g404"
        def job_loaner(d): d["forge"]["jobs"][0]["loaner"] = "g404"
        def job_time(d): d["forge"]["jobs"][0]["ready_at"] = "soon"
        def job_list(d): d["forge"]["jobs"] = {}
        def slots(d): d["forge"]["slots"] = "many"
        def heat(d): d["forge"]["heat"] = {"gear:epic": "hot"}
        def queue(d): d["town"]["queue"] = [{"id": "strongroom"}]
        def stash_level(d): d["town"]["stash_level"] = 9
        def rent(d): d["town"]["rent_banked"] = "lots"
        for change in (room, rest, cls, hp, agi, inf, nan, name, lantern, gear, gear_base, count, diff, diff0, regions,
                       town, forge, anchors, settings, visited, job_item, job_loaner, job_time, job_list, slots, heat, queue,
                       stash_level, rent):
            d = self.fixture()
            change(d)
            with self.assertRaises(save.SaveDamaged, msg=change.__name__):
                self.load_dict(d)

    def test_an_item_this_version_does_not_have_is_left_out_and_the_original_kept(self):
        d = self.fixture()
        d["player"]["inventory"]["removed_item"] = 2
        d["player"]["stash"]["removed_item"] = 1
        d["player"]["equipment"]["trinket"] = "removed_charm"
        d["player"]["spells"] = ["g404"]
        with temp_home():
            put(json.dumps(d))
            quiet_ui()
            g = Game.load()
            p = g.player
            self.assertNotIn("removed_item", p.inventory)
            self.assertNotIn("removed_item", p.stash)
            self.assertIsNone(p.equipment["trinket"])
            self.assertEqual(p.spells, [])
            self.assertEqual(p.inventory["oil"], 1)                    # everything else is untouched
            self.assertEqual(p.equipment["weapon"], "g6")
            for word in ("removed_item", "removed_charm", "g404", "left out"):
                self.assertIn(word, g.load_note)
            kept = file_bytes(suffix=".trimmed.bak")
            self.assertEqual(json.loads(kept)["player"]["inventory"]["removed_item"], 2)
            self.assertIn("main.trimmed.bak.json", g.load_note)
            out = run(g, "i", "stats", "look", "save")
            self.assertTrue(out.strip())
            self.assertEqual(Game.load().load_note, "")                # once saved there is nothing more to say

    def test_a_forged_item_the_save_does_not_carry_is_left_out(self):
        d = self.fixture()
        d["player"]["inventory"]["g26"] = 1
        d["player"]["equipment"]["trinket"] = "g27"
        ITEMS["g26"] = {"id": "g26", "instance": True, "name": "left over from another game", "kind": "trinket", "base": "moth_charm"}
        try:
            g = self.load_dict(d)
        finally:
            ITEMS.pop("g26", None)
        self.assertNotIn("g26", g.player.inventory)
        self.assertIsNone(g.player.equipment["trinket"])
        self.assertIn("g26", g.load_note)

    def test_a_count_of_zero_is_kept_as_the_game_keeps_it(self):
        d = self.fixture()
        d["player"]["inventory"]["slag"] = 0
        g = self.load_dict(d)
        self.assertEqual(g.player.inventory["slag"], 0)
        self.assertEqual(g.load_note, "")

    def test_rooms_the_game_no_longer_has_are_quietly_forgotten(self):
        d = self.fixture()
        d["visited"].append("old_room")
        d["room_items"]["old_room"] = ["oil"]
        g = self.load_dict(d)
        self.assertNotIn("old_room", g.visited)
        self.assertNotIn("old_room", g.room_items)
        self.assertEqual(g.load_note, "")

    def test_every_fixture_passes_the_check_without_a_word(self):
        for name in ("v0_prototype.json", "v1_pre_m5.json", "v2_current.json"):
            with temp_home():
                install(name)
                quiet_ui()
                note = Game.load().load_note
                self.assertNotIn("left out", note, name)

    def test_one_wrong_value_anywhere_never_loads_into_a_game_that_then_crashes(self):
        """The game either refuses the save (SaveError) or plays on it; it never loads and then dies."""
        rng = random.Random(11)
        base = self.fixture()
        junk = [None, "x", -1, [], {}, 10 ** 30, 2.5, True, "g404", float("nan"), float("inf")]

        def paths_in(node, path=()):
            yield path
            if isinstance(node, dict):
                for k, v in node.items():
                    yield from paths_in(v, path + (k,))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    yield from paths_in(v, path + (i,))
        every = [p for p in paths_in(base) if p]
        loaded = refused = 0
        for _ in range(500):
            d = copy.deepcopy(base)
            path = rng.choice(every)
            node = d
            for k in path[:-1]:
                node = node[k]
            node[path[-1]] = rng.choice(junk)
            reset_gear()
            with temp_home():
                put(json.dumps(d))
                quiet_ui()
                try:
                    g = Game.load()
                except save.SaveError:
                    refused += 1
                    continue
                loaded += 1
                try:
                    out = run(g, "look", "i", "stats", "status", "quests", "map", "journal", "town", "forge")
                    g.save(quiet=True)
                except Exception as e:      # pragma: no cover - the message is the point
                    self.fail("loaded %s = %r but then %s: %s" % (".".join(map(str, path)), node.get(path[-1]) if isinstance(node, dict) else "", type(e).__name__, e))
        self.assertGreater(loaded, 100)
        self.assertGreater(refused, 50)

    def test_a_save_that_exhausts_the_stack_while_the_game_is_built_is_damaged(self):
        for exc in (RecursionError("deep"), OverflowError("big"), KeyError("x")):
            with temp_home():
                install("v2_current.json")
                with mock.patch.object(Game, "from_dict", side_effect=exc):
                    with self.assertRaises(save.SaveDamaged):
                        Game.load()

    def test_game_load_does_not_copy_when_told_not_to(self):
        with temp_home():
            install("v1_pre_m5.json")
            quiet_ui()
            g = Game.load(keep_copy=False)
            self.assertEqual(g.load_note, "")
            self.assertEqual(saves_listing(), ["main.json"])
        d = self.fixture()
        d["player"]["inventory"]["removed_item"] = 1
        with temp_home():
            put(json.dumps(d))
            quiet_ui()
            Game.load(keep_copy=False)
            self.assertEqual(saves_listing(), ["main.json"])


class UpdateDryRunTests(unittest.TestCase):
    """`update` loads a copy of every save with the new code; the files the recovery flow sets aside must not stop it."""

    def test_set_aside_files_are_not_saves(self):
        for name in ("main.damaged.json", "main.damaged.2.json", "slot2.damaged.12.json", "main.bak.damaged.json"):
            self.assertTrue(save.is_set_aside(name), name)
        for name in ("main.json", "main.bak.json", "main.v1.bak.json", "main.v1.bak.2.json", "main.trimmed.bak.json",
                     "damaged.json", "main.json.tmp"):
            self.assertFalse(save.is_set_aside(name), name)

    def test_the_migration_dry_run_skips_them_and_still_checks_everything_else(self):
        import subprocess
        import sys
        from lamplighter import update
        with temp_home() as home:
            folder = save.paths.saves_dir()
            install("v2_current.json")
            install("v1_pre_m5.json", save.backup_slot("main"))
            put("{not json", "main.damaged")
            put("also {broken", "main.damaged.2")
            files = update._save_files(folder)
            self.assertEqual([os.path.basename(f) for f in files], ["main.bak.json", "main.json"])

            def dry_run(paths):
                return subprocess.run([sys.executable, "-c", update._DRY_RUN] + paths, cwd=save.paths.game_root(),
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=dict(os.environ, LAMPLIGHTER_HOME=home))
            r = dry_run(files)
            self.assertEqual(r.returncode, 0, r.stdout.decode("utf-8", "replace"))
            # a real broken save is still caught
            put("{not json", "slot2")
            r = dry_run(update._save_files(folder))
            self.assertEqual(r.returncode, 1)
            self.assertIn("slot2.json", r.stdout.decode("utf-8", "replace"))


class WholeStateRoundTripTests(unittest.TestCase):
    """Every part of a rich game comes back from a save, including the parts that are usually empty."""

    def test_town_queue_forge_dealers_anchors_and_flags_survive(self):
        reset_gear()
        d = json.loads(fixture_bytes("v2_current.json"))
        d["town"]["queue"] = [{"id": "strongroom", "ready_at": 123456, "steps": 40}]
        d["town"]["built"] = ["hearth_stall"]
        d["town"]["rent_since"] = 99
        d["town"]["rent_banked"] = 12
        d["anchors"] = ["hall", "tavern"]
        d["flags"]["some_new_flag"] = {"deep": [1, 2, {"x": None}]}
        d["dealers"]["restocks"] = {"20000": 3, "20001": 1}
        d["forge"]["slots"] = 2
        d["forge"]["heat"] = {"gear:epic": 2, "relic:rare": 1}
        d["room_items"]["tavern"] = ["oil", "draught"]
        d["quests"]["extra"] = "done"
        d["stats"]["kills"] = 99
        d["difficulty"], d["diff_name"] = 1.3, "Hard"
        d["moves"], d["last_rest"] = 4321, "tavern"
        with temp_home():
            put(json.dumps(d))
            quiet_ui()
            g1 = Game.load()
            g1.save(quiet=True)
            reset_gear()                                            # a new process
            g2 = Game.load()
            a, b = (json.loads(json.dumps(g.to_dict())) for g in (g1, g2))
            self.assertEqual(a, b)
            for key in ("town", "forge", "dealers", "anchors", "flags", "quests", "stats"):
                self.assertEqual(b[key], d[key], key)
            for rid, items in d["room_items"].items():          # rooms new since the fixture gain floor items on load (core C9)
                self.assertEqual(b["room_items"][rid], items, rid)
            self.assertEqual((b["difficulty"], b["diff_name"], b["moves"], b["last_rest"]), (1.3, "Hard", 4321, "tavern"))
            self.assertEqual(sorted(b["player"]["gear"]), sorted(d["player"]["gear"]))
            for iid in b["player"]["gear"]:
                self.assertIs(ITEMS[iid], g2.player.gear[iid])


if __name__ == "__main__":
    unittest.main()
