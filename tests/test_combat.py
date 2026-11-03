import unittest

from lamplighter import combat, sim, ui
from lamplighter.combat import Action, Combat
from lamplighter.engine import Game
from lamplighter.entities import Player
from tests.helpers import quiet_ui


def make(enemy_ids, cls="wayfarer", level=3, **kw):
    quiet_ui()
    g = Game(seed=1)
    g.player = sim.build_player(cls=cls, level=level, **kw)
    g.room_id = "wood_path"
    return g, Combat(g, enemy_ids, policy=lambda c: c.suggest()[0], no_flee=True)


class CombatTests(unittest.TestCase):
    def setUp(self):
        ui.io.mute = True

    def tearDown(self):
        ui.io.mute = False

    def test_silent_fight_finishes_and_pays_out(self):
        g, c = make(["gloam_wolf"])
        self.assertEqual(c.run(), "win")
        self.assertGreater(g.player.xp + (g.player.level - 3) * 100, 0)

    def test_flare_cannot_be_used_two_turns_in_a_row(self):
        g, c = make(["gloam_wolf", "gloam_wolf"], level=3)
        c.round = 1
        self.assertTrue(c.flare_ready())
        self.assertTrue(c.execute(Action("flare")))
        c.round = 2
        self.assertFalse(c.flare_ready())
        self.assertFalse(c.execute(Action("flare")))
        c.round = 3
        self.assertTrue(c.flare_ready())

    def test_flare_needs_oil(self):
        g, c = make(["gloam_wolf"])
        g.player.oil = 0
        c.round = 5
        self.assertFalse(c.flare_ready())

    def test_shadowstep_dodges_the_biggest_attack_not_the_first(self):
        g, c = make(["gloam_wolf", "bog_lurker"], level=4)
        p = g.player
        p.apply("shadow", 3)
        weak, strong = c.enemies
        weak.intent = {"name": "Nip", "kind": "attack", "power": 0.3}
        strong.intent = {"name": "Maul", "kind": "heavy", "power": 2.5}
        before = p.hp
        c.enemy_phase()
        # the weak one hits (shadow is not spent on it), the strong one is dodged
        self.assertFalse(p.has("shadow"))
        self.assertLess(p.hp, before)
        self.assertGreater(p.hp, before - c.estimate(strong))

    def test_item_action_uses_the_item(self):
        g, c = make(["gloam_wolf"])
        p = g.player
        p.hp = 10
        n = p.inventory["draught"]
        self.assertTrue(c.execute(Action("item", item="draught")))
        self.assertEqual(p.inventory["draught"], n - 1)
        self.assertGreater(p.hp, 10)

    def test_skill_without_focus_does_nothing(self):
        g, c = make(["gloam_wolf"])
        g.player.focus = 0
        self.assertFalse(c.execute(Action("skill", skill="twin_cut", target=c.enemies[0])))

    def test_suggestion_dodges_a_heavy_hit(self):
        g, c = make(["antlered_mother"], level=3)
        m = c.enemies[0]
        m.intent = next(x for x in m.moves if x["kind"] == "heavy")
        g.player.focus = 5
        action, reason = c.suggest()
        self.assertEqual((action.kind, action.skill), ("skill", "shadowstep"))
        self.assertIn("Trample", reason)

    def test_boss_phase_cannot_be_skipped_by_one_big_hit(self):
        g, c = make(["hollow_king"], level=7)
        king = c.enemies[0]
        phases = []
        for _ in range(2):
            c.wound(king, 10000)           # a blow far bigger than the boss's whole health bar
            phases.append((king.hp > 0, king.phase))
        self.assertEqual(phases, [(True, 1), (True, 2)])  # each blow stops at the next phase
        c.wound(king, 10000)
        self.assertEqual(king.hp, 0)       # only after both phases have been fought

    def test_simulated_win_rates_are_sane(self):
        r = sim.win_rate(["gloam_wolf"], sim.suggested, n=30, cls="warden", level=2)
        self.assertGreater(r["win"], 0.9)


if __name__ == "__main__":
    unittest.main()
