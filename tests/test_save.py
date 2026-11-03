import json
import os
import unittest

from lamplighter import paths, save
from lamplighter.engine import Game
from tests.helpers import new_game, run, temp_home


class SaveTests(unittest.TestCase):
    def test_round_trip_keeps_everything(self):
        with temp_home():
            g = new_game()
            run(g, "e", "e")
            g.player.gold = 123
            g.flags["x"] = True
            g.save(quiet=True)
            g2 = Game.load()
            a, b = g.to_dict(), g2.to_dict()
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_saves_live_in_the_user_data_folder_not_the_game_folder(self):
        with temp_home() as home:
            g = new_game()
            g.save(quiet=True)
            self.assertTrue(save.path_for().startswith(home))
            self.assertFalse(save.path_for().startswith(paths.game_root()))

    def test_second_save_keeps_a_backup(self):
        with temp_home():
            g = new_game()
            g.save(quiet=True)
            g.player.gold = 77
            g.save(quiet=True)
            self.assertTrue(os.path.exists(save.path_for()[:-5] + ".bak.json"))

    def test_unversioned_save_migrates(self):
        with temp_home():
            g = new_game()
            d = g.to_dict()
            os.makedirs(paths.saves_dir())
            with open(save.path_for(), "w", encoding="utf-8") as f:
                json.dump(d, f)  # no save_version field, like the v1 prototype
            loaded = save.read()
            self.assertEqual(loaded["save_version"], save.SAVE_VERSION)

    def test_save_from_a_newer_game_is_refused_with_a_clear_message(self):
        with temp_home():
            os.makedirs(paths.saves_dir())
            with open(save.path_for(), "w", encoding="utf-8") as f:
                json.dump({"save_version": save.SAVE_VERSION + 5}, f)
            with self.assertRaises(save.SaveError) as ctx:
                save.read()
            self.assertIn("newer version", str(ctx.exception))

    def test_corrupt_save_is_reported_not_crashed(self):
        with temp_home():
            os.makedirs(paths.saves_dir())
            with open(save.path_for(), "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(save.SaveError):
                save.read()


if __name__ == "__main__":
    unittest.main()
