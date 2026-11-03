import contextlib
import io
import unittest

from lamplighter import maps, navigation
from lamplighter.content import ROOMS
from tests.helpers import new_game, run


def visit_all(g, regions):
    for rid, r in ROOMS.items():
        if r["region"] in regions:
            g.visited.add(rid)


class NavigationTests(unittest.TestCase):
    def test_every_room_can_draw_its_area_screen(self):
        g = new_game()
        for rid in ROOMS:
            g.room_id = rid
            g.visited.add(rid)
            with contextlib.redirect_stdout(io.StringIO()):
                g.render_room()  # must not raise, whatever the room, with or without lantern oil
                g.player.oil = 0
                g.render_room()
            g.player.oil = 100

    def test_first_objective_is_orrin(self):
        g = new_game()
        info = navigation.describe(g, navigation.main_objective(g))
        self.assertEqual(info["room"], "hall")
        self.assertTrue(info["here"])

    def test_route_text_and_command(self):
        g = new_game()
        g.room_id = "square"
        path = navigation.find_path(g, "square", "mother_grove")
        self.assertEqual(path[0][0], "n")
        self.assertEqual(len(path), 5)
        self.assertEqual(navigation.route_command(path), "n then n then n then n then n")
        self.assertEqual(navigation.route_text(path), "north x5")

    def test_locked_route_is_blocked_not_wrong(self):
        g = new_game()
        g.room_id = "square"
        self.assertIsNone(navigation.find_path(g, "square", "well_bottom"))
        self.assertIsNotNone(navigation.find_path(g, "square", "well_bottom", respect_locks=False))

    def test_hint_prints_the_exact_command(self):
        g = new_game()
        g.quests["main"] = 1
        g.room_id = "square"
        out = run(g, "hint")
        self.assertIn("n then n then n then n then n", out)
        self.assertIn("Antlered Mother", out)

    def test_travel_walks_to_a_known_place_and_stops_there(self):
        g = new_game()
        visit_all(g, {"Hollowmere"})
        g.cooldown = {}
        run(g, "travel brann")
        self.assertEqual(g.room_id, "smithy")

    def test_go_with_a_place_name_travels(self):
        g = new_game()
        visit_all(g, {"Hollowmere"})
        run(g, "go docks")
        self.assertEqual(g.room_id, "docks")

    def test_travel_refuses_unknown_places(self):
        g = new_game()
        out = run(g, "travel lightwell")
        self.assertEqual(g.room_id, "hall")
        self.assertIn("do not know", out)

    def test_map_draws_every_visited_room_name(self):
        g = new_game()
        visit_all(g, {"Hollowmere"})
        # the town is wider than the terminal now, so the map scrolls: walk the player along it and read every window
        text = ""
        for rid in [r for r, v in ROOMS.items() if v["region"] == "Hollowmere"]:
            g.room_id = rid
            text += "\n".join(maps.render_region(g, "Hollowmere")[0])
        for word in ("Square", "Candle Lane", "Docks", "Forge", "Moth"):
            self.assertIn(word, text)

    def test_map_shows_unexplored_exits_and_locks(self):
        g = new_game()
        g.visited |= {"square"}
        g.room_id = "square"
        text = "\n".join(maps.render_region(g, "Hollowmere")[0])
        self.assertIn("unexplored", text)

    def test_wide_regions_scroll_to_keep_the_player_in_view(self):
        g = new_game()
        visit_all(g, {"Underdeep"})
        g.room_id = "lightwell"
        lines, legend = maps.render_region(g, "Underdeep")
        self.assertIn("Lightwell", "\n".join(lines))
        self.assertTrue(any("continues west" in l for l in legend))

    def test_world_view_lists_all_regions(self):
        g = new_game()
        out = run(g, "map world")
        for name in ("Hollowmere", "Weeping Wood", "Saltmarsh", "Underdeep"):
            self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()
