"""M6 core-b (docs/M6-SPEC.md section 4, rows C13 and C14): room damage fields and rotating-weakness enemies."""
import contextlib
import io
import unittest
from unittest import mock

from lamplighter import ui
from lamplighter.combat import Action, Combat
from lamplighter.content import ENEMIES, ROOMS
from lamplighter.engine import Game
from lamplighter import sim, validate
from tests.helpers import quiet_ui

ROOM = "wood_path"
FIELD = {"name": "Black Ice", "fire": 0.75, "earth": 1.25, "msg": "The ice drinks the heat out of everything."}
STANCES = [
    {"name": "Ember", "weak": ["ice"], "resist": ["fire"]},
    {"name": "Tide", "weak": ["fire", "earth"], "resist": ["water"], "msg": "{hollow}It runs like water.{/}"},
    {"name": "Stone", "weak": ["shadow"], "resist": []},
]
DUMMY = {"name": "Dummy", "hp": 5000, "atk": 1, "def": 0, "dodge": 0, "xp": 1, "gold": [0, 0], "tags": ["construct"],
         "desc": "A training dummy.", "moves": [{"name": "Poke", "kind": "attack", "power": 0.1, "tell": "pokes"}],
         "weak": ["light"], "resist": ["shadow"]}


def make(enemy_ids, spells=(), field=None, silent=True, **kw):
    """A fight in ROOM; `field` (or None) is set on the room for as long as the test lives."""
    quiet_ui()
    g = Game(seed=1)
    g.player = sim.build_player(cls="ashblade", level=6, spells=list(spells))
    g.room_id = ROOM
    g.cooldown[ROOM] = 10 ** 6
    policy = (lambda c: c.suggest()[0]) if silent else None
    return g, Combat(g, enemy_ids, policy=policy, no_flee=True, **kw)


class FieldCase(unittest.TestCase):
    def setUp(self):
        ui.io.mute = True
        patch = mock.patch.dict(ENEMIES, {"zz_dummy": DUMMY})
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        ui.io.mute = False

    def set_field(self, field):
        patch = mock.patch.dict(ROOMS[ROOM], {"field": field} if field else {})
        patch.start()
        self.addCleanup(patch.stop)

    def dealt(self, kind, base=100, field=None, spell=False):
        """Damage of one blow of `kind` with the dice fixed, in a room with `field` (or none)."""
        with mock.patch.dict(ROOMS[ROOM], {"field": field} if field else {}):
            g, c = make(["zz_dummy"])
            c.rng.uniform = lambda a, b: 1.0
            c.rng.random = lambda: 0.99       # no misses, no crits
            c.enemies[0].weak = []
            c.enemies[0].resist = []
            return c.hit(c.enemies[0], base, kind=kind, spell=spell)

    # ------------------------------------------------------------------ the maths
    def test_a_field_scales_spells_of_its_elements(self):
        plain = self.dealt("fire", spell=True)
        self.assertAlmostEqual(self.dealt("fire", field=FIELD, spell=True), plain * 0.75, delta=1)
        plain = self.dealt("earth", spell=True)
        self.assertAlmostEqual(self.dealt("earth", field=FIELD, spell=True), plain * 1.25, delta=1)

    def test_an_element_the_field_does_not_name_is_untouched(self):
        self.assertEqual(self.dealt("ice", field=FIELD, spell=True), self.dealt("ice", spell=True))

    def test_weapon_blows_and_true_damage_ignore_the_field(self):
        every = {"name": "Everything", "fire": 0.5, "ice": 0.5, "water": 0.5, "light": 0.5, "shadow": 0.5, "earth": 0.5}
        self.assertEqual(self.dealt("phys", field=every), self.dealt("phys"))
        self.assertEqual(self.dealt("true", field=every), self.dealt("true"))

    def test_the_field_hits_light_which_is_what_a_flare_deals(self):
        dim = {"name": "Dim", "light": 0.5}
        self.assertAlmostEqual(self.dealt("light", field=dim), self.dealt("light") * 0.5, delta=1)

    def test_a_flare_is_scaled(self):
        def flare_damage(field):
            with mock.patch.dict(ROOMS[ROOM], {"field": field} if field else {}):
                g, c = make(["zz_dummy"])
                c.rng.uniform = lambda a, b: 1.0
                c.round = 5
                e = c.enemies[0]
                before = e.hp
                self.assertTrue(c.execute(Action("flare")))
                return before - e.hp
        dim = {"name": "Dim", "light": 0.5}
        self.assertAlmostEqual(flare_damage(dim), flare_damage(None) * 0.5, delta=1)

    def test_a_firepot_is_scaled(self):
        def pot_damage(field):
            with mock.patch.dict(ROOMS[ROOM], {"field": field} if field else {}):
                g, c = make(["zz_dummy"])
                c.rng.uniform = lambda a, b: 1.0
                g.player.add_item("firepot", 1)
                e = c.enemies[0]
                before = e.hp
                self.assertTrue(c.execute(Action("item", item="firepot")))
                return before - e.hp
        self.assertLess(pot_damage(FIELD), pot_damage(None))

    def test_a_room_without_a_field_is_unchanged(self):
        self.assertNotIn("field", ROOMS[ROOM])
        self.assertGreater(self.dealt("fire", spell=True), 0)

    # ------------------------------------------------------------------ the announcement
    def run_loud(self, field):
        """Start a fight with output visible and read what the opening printed."""
        ui.io.mute = False
        with mock.patch.dict(ROOMS[ROOM], {"field": field} if field else {}):
            g, c = make(["zz_dummy"], silent=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                c.announce_field()
            return g, out.getvalue()

    def test_the_fight_names_the_field_and_its_numbers(self):
        g, out = self.run_loud(FIELD)
        self.assertIn("Field: Black Ice (Fire x0.75, Earth x1.25)", out)

    def test_the_flavour_line_is_told_only_once(self):
        ui.io.mute = False
        with mock.patch.dict(ROOMS[ROOM], {"field": FIELD}):
            g, c = make(["zz_dummy"], silent=False)
            first, second = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(first):
                c.announce_field()
            with contextlib.redirect_stdout(second):
                c.announce_field()
        self.assertIn("drinks the heat", first.getvalue())
        self.assertIn("Black Ice", second.getvalue())
        self.assertNotIn("drinks the heat", second.getvalue())
        self.assertTrue(g.flags.get("field_seen_" + ROOM))

    def test_no_field_prints_nothing(self):
        g, out = self.run_loud(None)
        self.assertEqual(out.strip(), "")

    def test_a_whole_fight_in_a_field_runs_and_announces(self):
        with mock.patch.dict(ROOMS[ROOM], {"field": FIELD}):
            g, c = make(["gloam_wolf"], silent=True)
            self.assertEqual(c.run(), "win")

    def test_sim_fight_sees_the_field(self):
        seen = []
        orig = Combat.announce_field

        def spy(self):
            seen.append(self.g.room.get("field", {}).get("name"))
            return orig(self)
        with mock.patch.dict(ROOMS[ROOM], {"field": FIELD}), mock.patch.object(Combat, "announce_field", spy):
            sim.fight(["gloam_wolf"], sim.suggested, 1, room=ROOM, cls="ashblade", level=6)
        self.assertEqual(seen, ["Black Ice"])

    def test_the_suggested_spell_follows_the_field(self):
        field = {"name": "Black Ice", "fire": 0.5, "earth": 1.5}
        for order in ([("fire", "common"), ("earth", "common")], [("earth", "common"), ("fire", "common")]):
            with mock.patch.dict(ROOMS[ROOM], {"field": field}):
                g, c = make(["zz_dummy"], spells=order)
                g.player.focus = 10
                c.enemies[0].weak = []
                c.enemies[0].resist = []
                action, why = c.best_spell(c.alive)
                self.assertEqual(action.item, "book_earth")

    def test_a_field_dimmed_spell_is_still_cast_when_nothing_beats_it(self):
        with mock.patch.dict(ROOMS[ROOM], {"field": {"name": "Dim", "fire": 0.75}}):
            g, c = make(["zz_dummy"], spells=[("fire", "common")])
            g.player.focus = 10
            c.enemies[0].weak = []
            c.enemies[0].resist = []
            self.assertEqual(c.best_spell(c.alive)[0].item, "book_fire")

    def test_a_real_field_validates(self):
        errs = []
        validate.check_field("zz", FIELD, errs.append)
        self.assertEqual(errs, [])


class AttuneCase(unittest.TestCase):
    def setUp(self):
        ui.io.mute = True
        enemy = dict(DUMMY, attune={"every": 2, "stances": STANCES})
        patch = mock.patch.dict(ENEMIES, {"zz_attuned": enemy, "zz_dummy": DUMMY})
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        ui.io.mute = False

    def start(self, spells=()):
        g, c = make(["zz_attuned"], spells=spells)
        return g, c, c.enemies[0]

    def advance(self, c, rounds):
        """Play `rounds` round-starts the way _run does, returning everything printed at the shifts."""
        said = []
        with mock.patch("lamplighter.combat.say", side_effect=lambda t="": said.append(t)):
            for _ in range(rounds):
                c.round += 1
                c.shift_stances()
        return said

    def test_the_first_stance_applies_before_the_first_round(self):
        g, c, e = self.start()
        c.shift_stances(announce=False)
        self.assertEqual((e.weak, e.resist), (["ice"], ["fire"]))
        self.assertEqual(e.stance, 0)

    def test_stances_cycle_every_n_rounds_and_wrap(self):
        g, c, e = self.start()
        c.shift_stances(announce=False)
        seen = []
        for _ in range(14):
            c.round += 1
            c.shift_stances()
            seen.append(e.stance)
        # every 2 over three stances: 0 0 1 1 2 2 0 0 1 1 2 2 0 0
        self.assertEqual(seen, [0, 0, 1, 1, 2, 2, 0, 0, 1, 1, 2, 2, 0, 0])

    def test_weak_and_resist_are_replaced_not_merged(self):
        g, c, e = self.start()
        c.shift_stances(announce=False)
        self.advance(c, 3)
        self.assertEqual((e.weak, e.resist), (["fire", "earth"], ["water"]))
        self.advance(c, 2)
        self.assertEqual((e.weak, e.resist), (["shadow"], []))

    def test_a_shift_is_announced_with_the_stance_name_or_its_msg(self):
        g, c, e = self.start()
        c.shift_stances(announce=False)
        said = self.advance(c, 2)
        self.assertEqual(said, [])                                  # rounds 1 and 2 are the first stance
        said = self.advance(c, 1)                                   # round 3
        self.assertEqual(said, ["{hollow}It runs like water.{/}"])
        said = self.advance(c, 2)                                   # round 5
        self.assertEqual(said, ["{hollow}Dummy shifts: Stone.{/}"])

    def test_the_opening_stance_is_not_announced(self):
        g, c, e = self.start()
        said = []
        with mock.patch("lamplighter.combat.say", side_effect=lambda t="": said.append(t)):
            c.shift_stances(announce=False)
            c.round = 1
            c.shift_stances()
        self.assertFalse([s for s in said if "shifts" in s])

    def test_an_ordinary_enemy_is_left_alone(self):
        g, c = make(["zz_dummy"])
        e = c.enemies[0]
        c.shift_stances(announce=False)
        self.advance(c, 5)
        self.assertEqual((e.weak, e.resist, e.stance), (["light"], ["shadow"], None))

    def test_the_render_shows_the_stance_and_the_countdown(self):
        ui.io.mute = False
        g, c, e = self.start()
        c.shift_stances(announce=False)
        e.choose_intent(c.rng, c.enemies)
        lines = []
        for rnd, expect in ((1, "stance: Ember, next: Tide in 2 rounds"), (2, "stance: Ember, next: Tide in 1 round"),
                            (3, "stance: Tide, next: Stone in 2 rounds")):
            c.round = rnd
            c.shift_stances(announce=False)
            c.last_log = ""
            ui.io.start_capture()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                c.render()
            lines.append(out.getvalue())
            self.assertIn(expect, out.getvalue())
        self.assertNotIn("in 1 rounds", "".join(lines))

    def test_the_spell_suggestion_follows_the_stance(self):
        g, c, e = self.start(spells=[("fire", "common"), ("ice", "common"), ("shadow", "common")])
        g.player.focus = 10
        c.shift_stances(announce=False)
        c.round = 1
        action, why = c.best_spell(c.alive)
        self.assertEqual(action.item, "book_ice")                   # Ember: weak to ice, resists fire
        self.assertIn("weak to Ice", why)
        c.round = 3
        c.shift_stances(announce=False)
        g.player.focus = 10
        c.spell_cd.clear()
        action, why = c.best_spell(c.alive)
        self.assertEqual(action.item, "book_fire")                  # Tide: weak to fire and earth
        c.round = 5
        c.shift_stances(announce=False)
        c.spell_cd.clear()
        action, why = c.best_spell(c.alive)
        self.assertEqual(action.item, "book_shadow")                # Stone: weak to shadow

    def test_a_spell_is_never_suggested_into_the_current_resist(self):
        g, c, e = self.start(spells=[("fire", "common")])
        g.player.focus = 10
        c.shift_stances(announce=False)
        self.assertIsNone(c.best_spell(c.alive))                    # Ember resists fire

    def test_the_damage_changes_with_the_stance(self):
        g, c, e = self.start()
        c.rng.uniform = lambda a, b: 1.0
        c.shift_stances(announce=False)
        resisted = c.hit(e, 100, kind="fire", spell=True, quiet=True)
        c.round = 3
        c.shift_stances(announce=False)
        boosted = c.hit(e, 100, kind="fire", spell=True, quiet=True)
        self.assertGreater(boosted, resisted * 2)

    def test_a_whole_fight_cycles_stances(self):
        g, c = make(["zz_attuned"], spells=[("fire", "common"), ("ice", "common")])
        g.player.hp = 10 ** 6
        with mock.patch.dict(ENEMIES["zz_attuned"], {"hp": 600}):
            c.enemies[0].max_hp = c.enemies[0].hp = 600
            self.assertEqual(c.run(), "win")
        self.assertGreater(c.round, 2)
        self.assertGreater(c.enemies[0].stance, -1)

    def test_a_summoned_attuned_enemy_gets_its_stance(self):
        boss = dict(DUMMY, name="Caller", moves=[{"name": "Call", "kind": "summon", "summon": "zz_attuned",
                                                  "tell": "calls"}])
        with mock.patch.dict(ENEMIES, {"zz_caller": boss}):
            g, c = make(["zz_caller"])
            c.round = 4
            c.enemies[0].intent = boss["moves"][0]
            c.enemy_phase()
        new = [e for e in c.enemies if e.id == "zz_attuned"][0]
        self.assertEqual(new.stance, 1)
        self.assertEqual(new.resist, ["water"])

    def test_the_validator_accepts_these_stances_and_rejects_a_hollow_light_stance(self):
        errs = []
        validate.check_attune("zz", dict(DUMMY, attune={"every": 2, "stances": STANCES}), errs.append)
        self.assertEqual(errs, [])
        bad = dict(DUMMY, tags=["hollow"], attune={"every": 2, "stances": [
            {"name": "A", "weak": ["light"]}, {"name": "B", "weak": ["fire"]}]})
        validate.check_attune("zz", bad, errs.append)
        self.assertTrue(errs)

    def attune_errors(self, stances):
        errs = []
        validate.check_attune("zz", dict(DUMMY, attune={"every": 2, "stances": stances}), errs.append)
        return errs

    def test_the_validator_reports_malformed_elements_instead_of_crashing(self):
        for weak, resist in ((["fire"], [["fire"]]), ([["fire"]], []), ([{}], []), (["fire"], [{}]), ([None], [])):
            errs = self.attune_errors([{"name": "a", "weak": weak, "resist": resist}, {"name": "b", "weak": ["ice"]}])
            self.assertTrue(any("unknown element" in e for e in errs), (weak, resist))

    def test_the_validator_rejects_repeats_and_no_op_rotations(self):
        ok = {"name": "b", "weak": ["ice"]}
        self.assertTrue(any("twice" in e for e in self.attune_errors([{"name": "a", "weak": ["fire", "fire"]}, ok])))
        self.assertTrue(any("twice" in e for e in self.attune_errors(
            [{"name": "a", "weak": ["fire"], "resist": ["ice", "ice"]}, ok])))
        self.assertTrue(any("stance name" in e for e in self.attune_errors([{"name": "b", "weak": ["fire"]}, ok])))
        self.assertTrue(any("same weak" in e for e in self.attune_errors(
            [{"name": "a", "weak": ["ice"]}, {"name": "b", "weak": ["ice"]}])))


if __name__ == "__main__":
    unittest.main()
