import unittest

from tests.helpers import new_game, run


class SmokeTests(unittest.TestCase):
    def test_walk_the_town(self):
        g = new_game()
        run(g, "e")
        self.assertEqual(g.room_id, "square")
        run(g, "w")
        self.assertEqual(g.room_id, "hall")

    def test_take_and_read(self):
        g = new_game()
        out = run(g, "take all", "read page 1")
        self.assertTrue(g.player.has_item("page1"))
        self.assertIn("Guild of Lamplighters", out)

    def test_locked_exit_is_refused(self):
        g = new_game()
        run(g, "e", "d")
        self.assertEqual(g.room_id, "square")  # the Old Well is sealed without the Embers

    def test_dark_rooms_burn_oil(self):
        g = new_game()
        g.room_id = "gate"
        g.cooldown["wood_path"] = 10**6  # no random fight while we measure oil
        before = g.player.oil
        run(g, "n")
        self.assertEqual(g.room_id, "wood_path")
        self.assertEqual(g.player.oil, before - g.player.move_cost)

    def test_unknown_command_does_not_crash(self):
        g = new_game()
        run(g, "dance wildly")


if __name__ == "__main__":
    unittest.main()
