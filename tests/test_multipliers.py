import unittest

from lamplighter import gear, ui
from lamplighter.combat import Combat
from lamplighter.content import ENEMIES, ITEMS
from lamplighter.entities import Enemy
from tests.helpers import new_game


def damage_with(equipment, kind="phys", seed=7):
    g = new_game("warden", seed=seed)
    g.player.equipment.update(equipment)
    c = Combat(g, ["hollow_fawn"], policy=lambda cmb: None, no_flee=True)
    e = c.enemies[0]
    e.dodge = 0
    e.defense = 0
    e.max_hp = e.hp = 10 ** 6
    ui.io.mute = True
    try:
        return c.hit(e, 1000, kind, can_crit=False, quiet=True)
    finally:
        ui.io.mute = False


class MultiplierTests(unittest.TestCase):
    def test_no_multiplier_is_neutral(self):
        g = new_game()
        self.assertEqual(g.player.mult("phys"), 1.0)
        self.assertEqual(g.player.mult("heal"), 1.0)

    def test_weapon_multiplier_raises_damage_by_that_factor(self):
        base = damage_with({"weapon": "hook"})
        boosted = damage_with({"weapon": "starsteel_blade"})  # x1.2 weapon damage, plus x1.2 vs Hollows
        self.assertGreater(boosted, base * 1.2 * 1.2 * 0.97)
        self.assertLess(boosted, base * 1.2 * 1.2 * 1.03)

    def test_multipliers_stack_by_multiplying(self):
        g = new_game()
        g.player.equipment.update({"weapon": "censer_flail", "trinket": "orrins_ring"})
        # censer: light x1.15, fire x1.15; ring: all damage x1.05
        self.assertAlmostEqual(g.player.mult("light"), 1.15 * 1.05)
        self.assertAlmostEqual(g.player.mult("fire"), 1.15 * 1.05)
        self.assertAlmostEqual(g.player.mult("phys"), 1.05)

    def test_healing_multiplier_applies_to_heal_only(self):
        g = new_game()
        g.player.equipment["trinket"] = "saints_tooth"
        self.assertAlmostEqual(g.player.mult("heal"), 1.15)
        self.assertEqual(g.player.mult("phys"), 1.0)

    def test_every_item_multiplier_is_well_formed(self):
        for iid, it in list(ITEMS.items()):
            if gear.is_instance(iid):
                continue                                        # forged pieces (Godlike, Long-Quenched) pass through ITEMS in other tests
            for k, v in it.get("mult", {}).items():
                self.assertIn(k, {"dmg", "phys", "fire", "light", "heal", "ice", "water", "shadow", "earth", "spell"}, iid)
                self.assertTrue(0.5 <= v <= 5, iid)


if __name__ == "__main__":
    unittest.main()
