import unittest

from lamplighter import sim, ui
from lamplighter.combat import Action, Combat
from lamplighter.entities import Player
from tests.helpers import new_game, run


def dread_game(dread=0, cls="warden", **kw):
    g = new_game(cls)
    g.player = sim.build_player(cls=cls, level=3, dread=dread, **kw)
    return g


class DreadTests(unittest.TestCase):
    def test_tier_boundaries(self):
        p = dread_game().player
        for value, tier in [(0, "Steady"), (24, "Steady"), (25, "Uneasy"), (49, "Uneasy"), (50, "Afraid"),
                            (74, "Afraid"), (75, "Terrified"), (99, "Terrified"), (100, "Consumed")]:
            p.dread = value
            self.assertEqual(p.dread_tier, tier, value)

    def test_damage_rises_with_dread_and_falls_when_shaken(self):
        p = dread_game().player
        mult = {}
        for d in (0, 30, 60, 80):
            p.dread = d
            mult[d] = p.dread_damage_mult()
        self.assertEqual(mult, {0: 1.0, 30: 1.05, 60: 1.12, 80: 1.20})
        p.shaken = True
        self.assertAlmostEqual(p.dread_damage_mult(), 0.96)

    def test_dread_makes_you_easier_to_hit_and_crit_more(self):
        p = dread_game().player
        base_dodge, base_crit = p.dodge, p.crit
        p.dread = 60
        self.assertLess(p.dodge, base_dodge)
        self.assertEqual(p.crit, base_crit + 10)

    def test_fear_makes_you_easier_to_hurt(self):
        p = dread_game().player
        taken = {}
        for d in (0, 30, 60, 80, 100):
            p.dread = d
            taken[d] = p.dread_taken_mult()
        self.assertEqual(taken, {0: 1.0, 30: 1.0, 60: 1.10, 80: 1.20, 100: 1.20})
        p.dread_effects = False
        self.assertEqual(p.dread_taken_mult(), 1.0)

    def test_cosmetic_mode_changes_nothing(self):
        p = dread_game(dread=90).player
        p.dread_effects = False
        self.assertEqual(p.dread_damage_mult(), 1.0)
        self.assertEqual(p.crit, dread_game().player.crit)

    def test_terror_weakens_healing(self):
        p = dread_game().player
        p.hp = 1
        p.dread = 80
        self.assertLessEqual(p.heal(100), 75)

    def test_dark_rooms_raise_dread_and_lit_ones_lower_it(self):
        g = dread_game()
        g.room_id = "gate"
        g.cooldown["wood_path"] = 10 ** 6
        run(g, "n")                                  # the Tollroad is ring 1: +2
        self.assertEqual(g.player.dread, 2)
        g.player.dread = 20
        g.flags["lit_wood_path"] = True
        g.room_id = "gate"
        run(g, "n")                                  # now lit: -3
        self.assertEqual(g.player.dread, 17)

    def test_benighted_doubles_the_gain(self):
        g = dread_game()
        g.room_id = "gate"
        g.cooldown["wood_path"] = 10 ** 6
        g.player.oil = 0
        run(g, "n")
        self.assertEqual(g.player.dread, 4)

    def test_town_and_rest_calm_you(self):
        g = dread_game(dread=70)
        g.player.shaken = True
        g.room_id = "gate"
        run(g, "s")                                  # into the square
        self.assertEqual(g.player.dread, 0)
        g.player.dread = 70
        g.player.shaken = True
        g.room_id = "hall"                           # a place you can sleep
        run(g, "rest")
        self.assertEqual((g.player.dread, g.player.shaken), (0, False))

    def test_a_companion_steadies_the_nerves(self):
        g = dread_game()
        g.flags["wren_following"] = True
        g.add_dread(8)
        self.assertEqual(g.player.dread, 6)

    def test_meals_lower_dread(self):
        g = dread_game(dread=40)
        g.player.add_item("honeycake")
        g.player.hp = 5
        run(g, "use honeycake")
        self.assertEqual(g.player.dread, 25)

    def test_outside_a_fight_dread_stops_short_of_consumed(self):
        g = dread_game(dread=98)
        g.add_dread(10)
        self.assertEqual(g.player.dread, 99)

    def test_consumed_hollows_you_for_three_rounds_then_collapses(self):
        ui.io.mute = True
        try:
            g = dread_game(dread=99)
            g.room_id = "deepwood"                   # dark, so each round adds dread
            c = Combat(g, ["antlered_mother"], policy=lambda cmb: Action("guard"), no_flee=True)
            states = []
            real = c.dread_tick

            def spy():
                real()
                states.append((g.player.hollowing, g.player.shaken))
            c.dread_tick = spy
            c.run()
        finally:
            ui.io.mute = False
        self.assertIn((3, False), states)            # Hollowing began with 3 rounds
        self.assertTrue(any(s for h, s in states))   # and ended in a collapse (Shaken)

    def test_ordinary_enemy_moves_are_hidden_when_terrified(self):
        g = dread_game(dread=80)
        c = Combat(g, ["gloam_wolf"], policy=lambda cmb: Action("guard"))
        self.assertFalse(c.sees(c.enemies[0]))
        g.player.dread = 10
        self.assertTrue(c.sees(c.enemies[0]))
        boss = Combat(g, ["antlered_mother"], policy=lambda cmb: Action("guard"))
        g.player.dread = 80
        self.assertTrue(boss.sees(boss.enemies[0]))  # bosses stay readable

    def test_damage_actually_uses_the_dread_multiplier(self):
        def hit(dread):
            g = dread_game(dread=dread)
            c = Combat(g, ["hollow_fawn"], policy=lambda cmb: None, no_flee=True)
            e = c.enemies[0]
            e.dodge, e.defense, e.max_hp, e.hp = 0, 0, 10 ** 6, 10 ** 6
            ui.io.mute = True
            try:
                return c.hit(e, 1000, "phys", can_crit=False, quiet=True)
            finally:
                ui.io.mute = False
        calm, scared = hit(0), hit(80)
        self.assertAlmostEqual(scared / calm, 1.2, delta=0.03)

    def test_old_saves_without_dread_still_load(self):
        d = dread_game().player.to_dict()
        for k in ("gems", "stash", "dread", "dread_effects", "shaken", "relic_level", "relic_charges"):
            d.pop(k)
        p = Player.from_dict(d)
        self.assertEqual((p.dread, p.gems, p.relic_charges, p.dread_effects), (0, 0, 2, True))


if __name__ == "__main__":
    unittest.main()
