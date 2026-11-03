"""Drives the real combat menu with keystrokes, the way a player does."""
import contextlib
import io
import unittest

from lamplighter import sim, ui
from lamplighter.combat import Combat
from tests.helpers import new_game


def play(enemy_ids, keys, cls="wayfarer", level=3, no_flee=False, setup=None, seed=1):
    """Run a fight feeding `keys` as the player's input. Returns (outcome, printed text, unused keys, game)."""
    g = new_game(cls, seed=seed)
    g.player = sim.build_player(cls=cls, level=level)
    g.room_id = "wood_path"
    if setup:
        setup(g)
    c = Combat(g, enemy_ids, no_flee=no_flee)
    ui.io.script = ["#"] + list(keys)   # first line answers "(press Enter to fight)"
    ui.io.since_clear = 1
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            outcome = c.run()
        except EOFError:
            outcome = "keys ran out"   # the fight was still going when the script ended
    return outcome, out.getvalue(), list(ui.io.script), g


class CombatMenuTests(unittest.TestCase):
    def test_enter_takes_the_suggestion_and_wins(self):
        outcome, out, left, _ = play(["hollow_fawn"], [""] * 12)
        self.assertEqual(outcome, "win")
        self.assertIn("Suggested", out)

    def test_letter_keys_attack_and_guard(self):
        outcome, out, left, _ = play(["hollow_fawn"], ["g", "a", "a", "a", "a", "a"])
        self.assertEqual(outcome, "win")
        self.assertIn("raise your guard", out)

    def test_skill_slot_numbers_are_stable(self):
        # slot 1 is always the class's first skill, even at level 1 with only two unlocked
        outcome, out, left, _ = play(["rootwight"], ["1", "1", "1", "a", "a", "a", "a", "a", "a"], level=1)
        self.assertIn("You cut", out)   # Twin Cut

    def test_locked_skill_is_refused_with_a_reason(self):
        outcome, out, left, _ = play(["hollow_fawn"], ["4", "a", "a", "a", "a", "a"], level=1)
        self.assertIn("unlocks at level", out)

    def test_not_enough_focus_is_refused(self):
        # Twin Cut (3) leaves 1 focus, +2 per turn = 3, so Hamstring (4) is not affordable yet
        outcome, out, left, _ = play(["antlered_mother"], ["1", "3", "a", "a"], level=3)
        self.assertIn("Not enough focus", out)

    def test_target_number_picks_the_enemy(self):
        outcome, out, left, _ = play(["hollow_fawn", "hollow_fawn"], ["a 2", "a 2", "a 1", "a 1", "a", "a", "a", "a"])
        self.assertEqual(outcome, "win")
        self.assertNotIn("Pick a number", out)

    def test_target_prompt_defaults_on_enter(self):
        outcome, out, left, _ = play(["hollow_fawn", "hollow_fawn"], ["a", "", "a", "", "a", "", "a", "", "a", ""])
        self.assertEqual(outcome, "win")
        self.assertIn("target (Enter =", out)

    def test_flare_then_cooldown_message(self):
        outcome, out, left, _ = play(["antlered_mother"], ["f", "f", "a"], level=3)
        self.assertIn("(recharging)", out)
        self.assertIn("needs a moment", out)

    def test_items_menu_uses_an_item(self):
        def hurt(g):
            g.player.hp = 20
        outcome, out, left, g = play(["rootwight"], ["i", "1", "a", "a", "a", "a", "a", "a", "a", "a"], setup=hurt)
        self.assertIn("You drink the Healing Draught", out)

    def test_flee_works_or_fails_but_never_crashes(self):
        outcome, out, left, _ = play(["gloam_wolf"], ["r"] * 30)
        self.assertIn(outcome, ("fled", "win", "dead"))

    def test_boss_cannot_be_fled_and_menu_says_so(self):
        outcome, out, left, _ = play(["antlered_mother"], ["r", "a"], level=1, no_flee=True)
        self.assertNotIn("[R] Flee", out)
        self.assertIn("Not an action", out)   # R is not accepted in a fight you cannot run from

    def test_help_and_garbage_do_not_use_a_turn(self):
        outcome, out, left, _ = play(["hollow_fawn"], ["help", "zzz", "???", "a", "a", "a", "a", "a"])
        self.assertIn("Reading a fight", out)
        self.assertIn("Not an action", out)
        self.assertEqual(outcome, "win")

    def test_whole_menu_renders_for_every_class(self):
        for cls in ("warden", "ashblade", "wayfarer"):
            outcome, out, left, _ = play(["gloam_wolf"], [""] * 20, cls=cls, level=5)
            self.assertIn("Skills", out)
            self.assertIn("Actions", out)


if __name__ == "__main__":
    unittest.main()
