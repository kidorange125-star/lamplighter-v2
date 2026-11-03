"""M6 package fin (docs/M6-SPEC.md sections 13, 16.3 and 19): the ring-5 Dealer, the gem budget and codes, the Roll of
Lenders, the rules every package obeys, the old-save gate, the tools, and the whole Lending played end to end.

The playthrough is an integration test of the chain (the doors, the rooms, the people, the items and their order), not of
combat: fights are answered "win" and the simulators (tools/sim_ring5.py) own the numbers. Everything else is the real
engine: the movement command, the locks, the beacons, the boss scenes, the talk menus, the forge and the Long Quench
on a fake clock, and Mirelle's apex unlock."""
import contextlib
import io
import json
import os
import random
import subprocess
import sys
import unittest

from lamplighter import (areas, clock, codes, dealer, elements, events, forge, gear, navigation, npcs, quench,
                         spells, town, ui, validate)
from lamplighter.areas import arc, fin, late
from lamplighter.content import (AFFIXES, BUILDINGS, CODES, DEALER, ENEMIES, FORGE, ITEMS, REGION_INFO, ROOMS)
from lamplighter.engine import Game
from lamplighter.quests import LATE_RECEIPTS, QUESTS
from tests.helpers import new_game, run, temp_home

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "lamplighter", "data")

FROSTFAIR, BELOW, VIGIL, CELLARS = "The Frostfair", "The Fair Below", "The Vigil", "The Waking Cellars"
NEW_REGIONS = ["The Moth-Saint's Hospice", "The Reedlight", "The Lampwrights' Deep", FROSTFAIR, BELOW, VIGIL, CELLARS]

# ---------------------------------------------------------------------------- the id register (spec section 18)
REGISTER = {
    "core": dict(items=["core_heart_fire", "core_heart_ice", "core_heart_water", "core_heart_light",
                        "core_heart_shadow", "core_heart_earth"]),
    "hos": dict(rooms=["hos_path", "hos_gate", "hos_belfry", "hos_orchard", "hos_cloister", "hos_refectory",
                       "hos_scriptorium"],
                enemies=["hos_pilgrim", "hos_waymoth", "hos_almoner", "hos_vesper"],
                items=["hos_pilgrims_staff", "hos_moth_mantle", "hos_waylamp", "hos_windfall", "hos_belfry_key",
                       "hos_receipt"]),
    "rl": dict(rooms=["rl_causeway", "rl_sluice", "rl_tower_foot", "rl_lantern_room", "rl_cottage", "rl_oilhouse"],
               enemies=["rl_lampman", "rl_heronling", "rl_heron"],
               items=["rl_heronplume_coat", "rl_keepers_pole", "rl_lens_shard", "rl_tower_key", "rl_receipt"]),
    "lw": dict(rooms=["lw_door", "lw_mess", "lw_workshop", "lw_gallery", "lw_glassworks", "lw_rack_room"],
               enemies=["lw_glass_ghoul", "lw_lampling", "lw_foreman"],
               items=["lw_lampwright_hammer", "lw_apron", "lw_pit_lamp", "lw_lamp_blank", "lw_receipt",
                      "lw_quench_notes"]),
    "ff": dict(rooms=["ff_frost_road", "ff_fair_gate", "ff_lending_tent", "ff_midway", "ff_skate_pond",
                      "ff_ice_cellars", "ff_lamp_row", "ff_wardens_booth", "ff_carousel", "ff_sculptors_row",
                      "ff_great_gate", "ff_wintering", "ff_signal_stair", "ff_stall", "ff_below_stair",
                      "ff_below_hall", "ff_below_pool"],
               enemies=["ff_hawker", "ff_skater", "ff_horse", "ff_ice_figure", "ff_lamp", "ff_below_sleeper",
                        "ff_ringmaster", "ff_lampmaster"],
               items=["ff_rime", "ff_fair_token", "ff_cider", "ff_fairlight", "ff_wardens_key", "ff_cellar_key",
                      "ff_receipt", "ff_given_flame", "ff_wintering_flame", "ff_greatcoat", "ff_lamp_pole"],
               npcs=["ff_dunmore", "ff_marit"], buildings=["ff_fair_stall"]),
    "vg": dict(rooms=["vg_ladder", "vg_porters_lodge", "vg_great_court", "vg_library", "vg_heliograph",
                      "vg_orrery_hall", "vg_dormitory", "vg_reckoning_room", "vg_mirror_gallery",
                      "vg_camera_obscura", "vg_chapel", "vg_lens_cupboard", "vg_lens_stair", "vg_eye", "vg_loft",
                      "vg_cellar_stair", "vg_cellar_hall", "vg_cellar_cells"],
               enemies=["vg_brother", "vg_sentinel", "vg_glare", "vg_star", "vg_blind_spot", "vg_cellar_dead",
                        "vg_orrery", "vg_prior_eye"],
               items=["vg_starglass", "vg_nightcap", "vg_clear_draught", "vg_star_plate", "vg_lens_key", "vg_receipt",
                      "vg_given_flame", "vg_sixfold_chart", "vg_unsleeping_eye", "vg_astrolabe_rod",
                      "vg_nightcloak"],
               npcs=["vg_tick", "vg_hale"], buildings=["vg_almanac"]),
    "late": dict(items=["late_receipt_court", "late_aldrics_letter"], quests=["late_lending"]),
}
KINDS = ("rooms", "enemies", "items", "npcs", "buildings", "quests")
TABLES = {"rooms": ROOMS, "enemies": ENEMIES, "items": ITEMS, "buildings": BUILDINGS, "quests": QUESTS}

# the four placeholder codes of section 13.2: the owner rotates these before release; change this one list then
PLACEHOLDER_CODES = [("LENDING", 10), ("THAW", 15), ("VIGIL", 15), ("QUENCH", 10)]

# section 13.3, the one table of the gem budget
GEM_TABLE = [("first kills with the boss tag (3 each)", 15), ("hooks", 7), ("band bonus (once per rolled boss)", 4),
             ("codes", 50)]
OLD_GAME_GEMS = 93
BOSS_TAGGED = ["hos_vesper", "rl_heron", "lw_foreman", "ff_lampmaster", "vg_prior_eye"]

NEW_ROOM_FILES = ["hos", "rl", "lw", "ff", "vg"]


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def flat(text):
    """Printed text is wrapped to the terminal: compare it as one line."""
    return " ".join(text.split())


def kind_of(table_name, iid):
    if table_name == "npcs":
        return iid in npcs.NPCS
    return iid in TABLES[table_name]


def new_rooms():
    return {rid: r for rid, r in ROOMS.items() if rid.split("_")[0] in NEW_ROOM_FILES}


# ============================================================================ 1. the register
class RegisterTests(unittest.TestCase):
    def test_every_id_exists_in_exactly_one_kind_and_starts_with_its_slug(self):
        for slug, kinds in REGISTER.items():
            for kind, ids in kinds.items():
                for iid in ids:
                    self.assertTrue(kind_of(kind, iid), "%s %s is missing" % (kind, iid))
                    where = [k for k in KINDS if kind_of(k, iid)]
                    self.assertEqual(where, [kind], "%s is in two kinds: %s" % (iid, where))
                    if slug != "core":
                        self.assertTrue(iid.startswith(slug + "_"), "%s does not start with %s_" % (iid, slug))

    def test_no_id_is_registered_twice(self):
        seen = {}
        for slug, kinds in REGISTER.items():
            for kind, ids in kinds.items():
                for iid in ids:
                    self.assertNotIn(iid, seen, "%s is registered by %s and %s" % (iid, seen.get(iid), slug))
                    seen[iid] = slug

    def test_nothing_with_a_slug_prefix_is_missing_from_the_register(self):
        """The reverse: an id that carries a package's slug but is not in the register is a collision waiting."""
        registered = {k: set() for k in KINDS}
        for kinds in REGISTER.values():
            for kind, ids in kinds.items():
                registered[kind].update(ids)
        for table_name, table in TABLES.items():
            for iid in table:
                head = iid.split("_")[0]
                if head in ("hos", "rl", "lw", "ff", "vg", "late") and "@" not in iid:
                    self.assertIn(iid, registered[table_name], "%s %s is not in the register" % (table_name, iid))

    def test_room_and_region_totals(self):
        self.assertEqual(sum(len(k.get("rooms", [])) for k in REGISTER.values()), 54)
        self.assertEqual(len(ROOMS), 111)
        self.assertEqual({r["region"] for rid, r in ROOMS.items() if rid in sum((k.get("rooms", [])
                                                                                for k in REGISTER.values()), [])},
                         set(NEW_REGIONS) | {"Hollowmere"})
        for name in NEW_REGIONS:
            self.assertIn(name, REGION_INFO)

    def test_the_content_validator_has_nothing_to_say(self):
        # (gear instances live in ITEMS while a test runs: one leaked from another module is not this package's)
        errors = [e for e in validate.validate()
                  if not any(gear.is_instance(w) for w in e.split() if w in ITEMS)]
        self.assertEqual(errors, [])
        self.assertEqual(areas.check(), [])


# ============================================================================ 2. the gem budget and the codes
class GemBudgetTests(unittest.TestCase):
    def test_the_table_adds_up(self):
        self.assertEqual(sum(n for _, n in GEM_TABLE), 76)
        self.assertEqual(OLD_GAME_GEMS + 76, 169)

    def test_five_first_kills_pay_three_each(self):
        self.assertEqual(len(BOSS_TAGGED), 5)
        for eid in BOSS_TAGGED:
            self.assertIn("boss", ENEMIES[eid]["tags"], eid)
        # nothing else new is a boss: a stray tag would pay 3 gems nobody budgeted
        new_bosses = [e for e, v in ENEMIES.items() if "@" not in e and "boss" in v["tags"]
                      and e.split("_")[0] in ("hos", "rl", "lw", "ff", "vg")]
        self.assertEqual(sorted(new_bosses), sorted(BOSS_TAGGED))

    def test_the_hooks_pay_what_the_table_says_and_only_once(self):
        g = new_game()
        g.flags["completed"] = True
        before = g.player.gems
        with contextlib.redirect_stdout(io.StringIO()):
            for flag in ("hos_almoner_dead", "ff_ringmaster_dead", "vg_orrery_dead"):
                events.after_fixed(g, flag)
                events.after_fixed(g, flag)
        self.assertEqual(g.player.gems - before, 2 + 2 + 2)

    def test_the_band_bonus_is_once_per_rolled_boss_and_at_most_two_each(self):
        """Roused pays 1 and Ablaze 2, behind a once-only flag per boss (the 4 of the table is two bosses x 2)."""
        enter = areas.collect("ENTER")
        for key, room in (("ff", "ff_wintering"), ("vg", "vg_eye")):
            self.assertEqual(enter[room].__module__.rsplit(".", 1)[-1], key)
            src = read(ROOT, "lamplighter", "areas", key + ".py")
            self.assertIn("{3: 1, 4: 2}", src)
            self.assertIn(key + "_gems_band", src)

    def test_the_four_new_codes_are_worth_fifty_and_the_old_ones_are_untouched(self):
        self.assertEqual(CODES[codes.code_hash("NEW")]["gems"], 30)
        self.assertEqual(len(CODES), 6)
        self.assertEqual(sum(v["gems"] for v in CODES.values()), 30 + 40 + 50)
        self.assertEqual(sum(n for _, n in PLACEHOLDER_CODES), 50)

    def test_the_placeholder_codes_redeem_once_each_and_only_their_hashes_are_stored(self):
        g = new_game()
        for code, n in PLACEHOLDER_CODES:
            before = g.player.gems
            ok, msg = codes.redeem(g, code.lower())
            self.assertTrue(ok, code)
            self.assertEqual(g.player.gems - before, n)
            self.assertFalse(codes.redeem(g, code)[0])
            self.assertEqual(g.player.gems - before, n)
        raw = read(DATA, "codes.json").upper()
        for code, _ in PLACEHOLDER_CODES:
            self.assertNotIn('"%s"' % code, raw)

    def test_the_dealer_notes_carry_the_same_arithmetic(self):
        notes = DEALER["notes"]
        self.assertIn("about 169", notes)
        for phrase in ("93", "76", "15 from five new first boss kills", "7 from four hooks", "50 from the four codes",
                       "in rings 4 and 5", "and Legendary for ring 5", "Godlike is never sold"):
            self.assertIn(phrase, notes)
        self.assertNotIn("only on sale in the last ring", notes)


# ============================================================================ 3. the ring-5 Dealer
class DealerRing5Tests(unittest.TestCase):
    def test_the_ring_is_configured_as_specified(self):
        cfg = DEALER["rings"]["5"]
        self.assertEqual(cfg["gear_odds"], {"epic": 10, "ultra": 40, "legendary": 50})
        self.assertEqual(cfg["relic_odds"], {"epic": 15, "ultra": 40, "legendary": 45})
        self.assertEqual((cfg["socket_cap"], cfg["bargain_cap"]), ("legendary", "legendary"))
        self.assertEqual(DEALER["price"]["legendary"], 28)
        self.assertEqual(dealer.check(DEALER), [])

    def test_the_three_new_bases_are_in_the_pool_and_are_rare_natives(self):
        for kind, base in (("weapon", "ff_lamp_pole"), ("weapon", "vg_astrolabe_rod"), ("armor", "vg_nightcloak")):
            self.assertIn(base, DEALER["gear"][kind])
            self.assertEqual(ITEMS[base]["rarity"], "rare", base)

    def test_legendary_is_the_likeliest_tier_and_godlike_is_never_sold(self):
        g = new_game()
        tiers = {"epic": 0, "ultra": 0, "legendary": 0}
        fair = 0
        for day in range(20000, 20400):
            for w in dealer._wares(g, 5, day, 0):
                self.assertNotEqual(w["rarity"], "godlike")
                for r in w["relics"]:
                    self.assertNotEqual(r["rarity"], "godlike")
                if w["kind"] == "gear" and w["slot"] in (0, 1):
                    tiers[w["rarity"]] += 1
                    fair += 1
        self.assertEqual(fair, 800)
        self.assertGreater(tiers["legendary"], 0.40 * fair)       # 50% by the data: more likely than not is the ask
        self.assertLess(tiers["legendary"], 0.60 * fair)
        self.assertGreater(tiers["legendary"], tiers["ultra"])
        self.assertGreater(tiers["ultra"], tiers["epic"])

    def test_a_bargain_never_goes_above_legendary_and_carries_a_curse(self):
        g = new_game()
        for day in range(20000, 20100):
            bargain = dealer._wares(g, 5, day, 0)[2]
            self.assertEqual(bargain["slot"], 2)
            self.assertIn(bargain["rarity"], ("ultra", "legendary"))
            self.assertTrue(bargain["curse"])
            self.assertTrue(AFFIXES[bargain["curse"]].get("curse"))

    def test_he_sits_in_the_frostfair_then_the_vigil_then_nowhere(self):
        g = new_game()
        days = range(20000, 20120)
        for d in days:
            self.assertIsNone(dealer.room_for(g, 5, d))                       # nobody before the Court is lit
        g.flags["beacon_Ember Court"] = True
        seen = {dealer.room_for(g, 5, d) for d in days}
        self.assertEqual({ROOMS[r]["region"] for r in seen}, {FROSTFAIR})
        g.flags["beacon_" + FROSTFAIR] = True
        g.flags.update({"lit_" + rid: True for rid, r in ROOMS.items() if r["region"] == FROSTFAIR})
        seen = {dealer.room_for(g, 5, d) for d in days}
        self.assertEqual({ROOMS[r]["region"] for r in seen}, {VIGIL})
        g.flags["beacon_" + VIGIL] = True
        g.flags.update({"lit_" + rid: True for rid, r in ROOMS.items() if r["region"] == VIGIL})
        self.assertEqual({dealer.room_for(g, 5, d) for d in days}, {None})

    def test_the_annexes_and_the_extensions_never_seat_him(self):
        for ring in range(1, 6):
            for rid in dealer.seats(ring):
                self.assertNotIn(ROOMS[rid]["region"], (BELOW, CELLARS) + tuple(NEW_REGIONS[:3]), rid)

    def test_every_dealer_region_has_at_least_three_seats(self):
        for name, info in REGION_INFO.items():
            if name in NEW_REGIONS and info.get("dealer", True):
                seats = [r for r in dealer.seats(info["ring"]) if ROOMS[r]["region"] == name]
                self.assertGreaterEqual(len(seats), 3, name)

    def test_the_dealer_flags_are_valid_region_data(self):
        for name in (BELOW, CELLARS, "The Moth-Saint's Hospice", "The Reedlight", "The Lampwrights' Deep"):
            self.assertIs(REGION_INFO[name].get("dealer"), False, name)
        self.assertEqual(REGION_INFO[FROSTFAIR]["dealer_after"], "beacon_Ember Court")
        self.assertEqual(REGION_INFO[VIGIL]["dealer_after"], "beacon_" + FROSTFAIR)


# ============================================================================ 4. the Roll of Lenders
def capture(fn, *args, answers=()):
    ui.io.script = list(answers)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            fn(*args)
    finally:
        ui.io.script = []
    return flat(out.getvalue())


def topic(g, nid, label_start):
    for label, fn in areas.topics(g, nid):
        if label.startswith(label_start):
            return fn
    return None


def run_topic(g, nid, label_start):
    fn = topic(g, nid, label_start)
    assert fn is not None, "%s has no topic %r" % (nid, label_start)
    return capture(fn, g, answers=[""] * 5)


class RollOfLendersTests(unittest.TestCase):
    def test_it_is_not_offered_before_the_story_is_told_or_without_a_reason(self):
        g = new_game()
        self.assertIsNone(topic(g, "wizard", "Ask about the Roll"))
        g.flags["completed"] = True
        self.assertIsNone(topic(g, "wizard", "Ask about the Roll"))              # nothing to ask about yet
        g.player.add_item("hos_receipt")
        self.assertIsNotNone(topic(g, "wizard", "Ask about the Roll of Lenders"))
        g2 = new_game()
        g2.flags.update(completed=True, ff_signal_seen=True)
        self.assertIsNotNone(topic(g2, "wizard", "Ask about the Roll of Lenders"))
        g3 = new_game()
        g3.flags["ff_signal_seen"] = True
        self.assertIsNone(topic(g3, "wizard", "Ask about the Roll"))             # before `completed`

    def test_it_names_six_lenders_with_their_plain_requirements(self):
        g = new_game()
        g.flags.update(completed=True, ff_signal_seen=True)
        out = run_topic(g, "wizard", "Ask about the Roll")
        self.assertIn("I held the pen; he held the lamp. I wrote every receipt twice. I never wrote the word 'return'", out)
        for lender, where in (
                ("The Hospice", "behind the Shrine of the Moth, east. Light the waypost there."),
                ("The Reedlight", "south of the Bog Lights, behind a fog bank. A Fire or Light book, equipped, will clear it."),
                ("The Lampwrights' Deep", "a bronze door in the Crypt Stair. A Lamp Relic, socketed into something you wear."),
                ("The Frostfair", "west of the North Gate, once the Court's beacon is lit."),
                ("The Vigil", "up the Signal Stair beyond the Frostfair, once the Great Lantern is lit."),
                ("The Court", "in the Ember Court. Pell will hand it over once the Queen is dead.")):
            self.assertIn("%s: %s" % (lender, where), out)
        self.assertTrue(g.flags["fin_roll_read"])
        g.flags["queen_dead"] = True                 # Pell has the paper only once the Queen has been ended
        self.assertIn("The Court: Pell has held it since. Ask her.", run_topic(g, "wizard", "Ask about the Roll"))

    def test_a_held_receipt_reads_receipt_in_hand_and_a_lit_place_says_so(self):
        g = new_game()
        g.flags.update(completed=True, ff_signal_seen=True)
        for rec in LATE_RECEIPTS[:2]:
            g.player.add_item(rec)
        out = run_topic(g, "wizard", "Ask about the Roll")
        self.assertIn("The Hospice: receipt in hand", out)
        self.assertIn("The Reedlight: receipt in hand", out)
        self.assertNotIn("The Lampwrights' Deep: receipt in hand", out)
        g.flags.update(ff_thaw=True, vg_signal_sent=True)
        out = run_topic(g, "wizard", "Ask about the Roll")
        self.assertIn("The Frostfair: thawed", out)
        self.assertIn("The Vigil: released", out)

    def test_a_lit_or_open_lender_still_says_where_its_receipt_lies(self):
        """The page is the one place that tells a player who walked past a door where it is: once the lock is gone it
        names the room that holds the receipt (and never keeps telling them to light a waypost that is lit)."""
        g = new_game()
        g.flags.update(completed=True, ff_signal_seen=True, ff_thaw=True, vg_signal_sent=True, lit_moth_shrine=True,
                       rl_fog_burned=True, lw_door_open=True)
        out = run_topic(g, "wizard", "Ask about the Roll")
        for lender, room in (("The Hospice", "the Scriptorium"), ("The Reedlight", "the Keeper's Cottage"),
                             ("The Lampwrights' Deep", "the Rack Room"),
                             ("The Frostfair", "the Lending Tent, south of the Fair Gate"),
                             ("The Vigil", "the Chart Library")):
            self.assertRegex(out, r"%s: [^.]*its receipt is in %s" % (lender, room))
        self.assertNotIn("Light the waypost there", out)
        self.assertNotIn("behind a fog bank", out)
        self.assertNotIn("bronze door in the Crypt Stair", out)
        for rec in LATE_RECEIPTS:                    # and once a receipt is in the pack the line is just that
            g.player.add_item(rec)
        out = run_topic(g, "wizard", "Ask about the Roll")
        self.assertNotIn("its receipt is in", out)
        self.assertEqual(out.count("receipt in hand"), 6)

    def test_a_long_entry_hangs_under_its_own_name(self):
        g = new_game()
        g.flags.update(completed=True, ff_signal_seen=True)
        ui.io.script = [""] * 5
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fin._roll_of_lenders(g)
        ui.io.script = []
        entries = [l for l in buf.getvalue().splitlines() if l.startswith("  The ")]
        self.assertEqual(len(entries), 6)
        hung = [l for l in buf.getvalue().splitlines() if l.startswith("    ")]
        self.assertTrue(hung, "no entry wrapped: the test needs a narrower terminal")
        for l in hung:
            self.assertFalse(l.startswith("     "), repr(l))

    def test_the_wizard_has_news_until_it_is_read_and_the_old_topic_is_untouched(self):
        g = new_game()
        g.flags.update(completed=True)
        self.assertFalse(npcs.has_news(g, "wizard") and fin.EXTRA_NEWS["wizard"](g))
        g.flags["ff_signal_seen"] = True
        self.assertTrue(fin.EXTRA_NEWS["wizard"](g))
        self.assertTrue(npcs.has_news(g, "wizard"))
        run_topic(g, "wizard", "Ask about the Roll")
        self.assertFalse(fin.EXTRA_NEWS["wizard"](g))
        # a menu actually shows it
        g.flags.pop("fin_roll_read")
        ui.io.script = ["0"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            npcs.talk(g, "wizard")
        self.assertIn("Ask about the Roll of Lenders", buf.getvalue())
        self.assertIn("Ask about the other places", buf.getvalue())

    def test_the_roll_lists_the_receipts_in_the_order_quests_and_late_use(self):
        self.assertEqual([row[1] for row in fin.LENDERS], list(LATE_RECEIPTS))
        self.assertEqual(fin.CHECK(), [])


# ============================================================================ 5. rules every package obeys
def lock_requirement_words():
    """Words a lock message may name: what the requirement is, or where to get it."""
    words = {"book", "beacon", "waypost", "relic", "joss", "dread", "building"}
    plain = {"the", "and", "of", "for", "your", "old", "a", "an", "in", "at"}
    for r in ROOMS.values():
        for name in (r["name"], r.get("boss_name", "")):
            words.add(name.lower())
            words.update(w for w in name.lower().replace("'s", "").split() if w not in plain and len(w) >= 3)
    for iid, it in ITEMS.items():
        words.add(it["name"].lower())
    for n in npcs.NPCS.values():
        words.update(w.lower() for w in n["name"].split() if len(w) > 3)
    return words


class RuleTests(unittest.TestCase):
    def locks(self):
        """[(room, dir, lock)] for every lock in the new room files and every attach patch."""
        out = [(rid, d, l) for rid, r in new_rooms().items() for d, l in r.get("locks", {}).items()]
        attach_dir = os.path.join(DATA, "attach")
        for name in sorted(os.listdir(attach_dir)):
            patch = json.loads(read(attach_dir, name))
            for rid, p in patch.items():
                out.extend((rid, d, l) for d, l in p.get("locks", {}).items())
        return out

    def test_every_lock_message_names_where_or_how_to_get_what_it_needs(self):
        words = lock_requirement_words()
        locks = self.locks()
        self.assertGreaterEqual(len(locks), 17)
        for rid, d, lock in locks:
            msg = lock["msg"].lower()
            self.assertTrue(any(w in msg for w in words), "%s %s: %s" % (rid, d, lock["msg"]))

    def test_a_lock_on_a_boss_flag_remembers_so_a_call_back_cannot_shut_a_door_again(self):
        """A Wizard call-back pops a boss flag; a lock that waits on one carries `remember` (section 2.3)."""
        for rid, d, lock in self.locks():
            flag = lock.get("flag", "")
            if flag.endswith("_dead"):
                self.assertTrue(lock.get("remember"), "%s %s" % (rid, d))

    def test_no_encounter_group_has_more_than_two_and_the_singles_share_holds(self):
        share = {"ff": 40, "vg": 55}
        for rid, r in new_rooms().items():
            groups = r.get("enc", {}).get("groups", [])
            for grp, _ in groups:
                self.assertLessEqual(len(grp), 2, rid)
            slug = rid.split("_")[0]
            if groups and slug in share:
                single = sum(w for grp, w in groups if len(grp) == 1)
                self.assertGreaterEqual(single * 100, share[slug] * sum(w for _, w in groups), rid)

    def test_every_rolled_boss_has_five_flavour_lines_and_a_voice(self):
        rolled = [e for e, v in ENEMIES.items() if "@" not in e and v.get("roll") and e.split("_")[0] in ("ff", "vg")]
        self.assertEqual(sorted(rolled), ["ff_lampmaster", "vg_prior_eye"])
        for eid in rolled:
            roll = ENEMIES[eid]["roll"]
            self.assertEqual(len(roll["flavour"]), 5, eid)
            self.assertTrue(all(isinstance(t, str) and t for t in roll["flavour"]), eid)
            self.assertEqual(sorted(roll["pron"]), ["obj", "poss", "subj"], eid)
            self.assertTrue(roll["place"], eid)
            self.assertTrue(roll["story"] is False or "story" in roll, eid)

    def test_no_hollow_is_weak_to_light_in_any_stance_either(self):
        for eid, e in ENEMIES.items():
            if "@" in eid or eid.split("_")[0] not in ("hos", "rl", "lw", "ff", "vg"):
                continue
            if "hollow" not in e.get("tags", []):
                continue
            weak = list(e.get("weak", []))
            for st in e.get("attune", {}).get("stances", []):
                weak += st.get("weak", [])
            self.assertNotIn("light", weak, eid)

    def test_every_room_has_a_description_and_features_and_every_enemy_a_description(self):
        for rid, r in new_rooms().items():
            self.assertTrue(r["desc"].strip(), rid)
            self.assertTrue(r["features"], rid)
        for eid, e in ENEMIES.items():
            if "@" not in eid and eid.split("_")[0] in ("hos", "rl", "lw", "ff", "vg"):
                self.assertTrue(e["desc"].strip(), eid)

    def test_every_heavy_or_charge_move_has_a_tell(self):
        for eid, e in ENEMIES.items():
            if "@" in eid or eid.split("_")[0] not in ("hos", "rl", "lw", "ff", "vg"):
                continue
            moves = list(e["moves"]) + [m for ph in e.get("phases", []) for m in ph["moves"]]
            moves += list(e.get("extra_moves", {}).values())
            for m in moves:
                if m.get("kind") in ("heavy", "charge"):
                    self.assertTrue(m.get("tell"), "%s %s" % (eid, m["name"]))

    def test_the_text_is_plain_ascii(self):
        for name in NEW_ROOM_FILES:
            for sub in ("rooms", "enemies", "items"):
                path = os.path.join(DATA, sub, name + ".json")
                if os.path.exists(path):
                    text = read(path)
                    bad = sorted({c for c in text if ord(c) > 127})
                    self.assertEqual(bad, [], path)
        for f in ("fin.py",):
            text = read(ROOT, "lamplighter", "areas", f)
            self.assertEqual(sorted({c for c in text if ord(c) > 127}), [], f)

    def test_a_wake_string_has_at_most_one_percent_d(self):
        for rid, r in ROOMS.items():
            w = r.get("wake")
            if w:
                self.assertLessEqual(w.count("%d"), 1, rid)
                self.assertEqual(w.replace("%d", "").count("%"), 0, rid)


# ============================================================================ 6. "never stalls" (section 16.3)
class NeverStallsTests(unittest.TestCase):
    def test_no_timer_is_longer_than_the_gap_between_sessions_except_the_long_quench(self):
        gap_minutes = 1.75 * 24 * 60
        for name, t in FORGE["tiers"].items():
            self.assertLessEqual(t["minutes"], gap_minutes, name)
        for name, t in FORGE["relic_tiers"].items():
            self.assertLessEqual(t["minutes"], gap_minutes, name)
        for bid, b in BUILDINGS.items():
            self.assertLessEqual(b["minutes"], gap_minutes, bid)
        smith = json.loads(read(DATA, "smith.json"))["quench"]
        self.assertEqual(smith["days"], 7)                                      # the one opt-in exception
        self.assertEqual(quench.CFG["days"], 7)

    def test_each_scarce_material_has_a_gold_valve_once_its_boss_is_dead(self):
        prices = areas.collect("PRICES")
        self.assertEqual(prices["ff_rime"], 70)
        self.assertEqual(prices["vg_starglass"], 90)
        g = new_game()
        for item, boss in (("ff_rime", "ff_lampmaster_dead"), ("vg_starglass", "vg_eye_dead")):
            self.assertNotIn(item, npcs.stock_for(g, "odo"))
            g.flags[boss] = True
            self.assertIn(item, npcs.stock_for(g, "odo"))
            self.assertEqual(npcs.price(item), prices[item])

    def test_each_ring_five_beacon_opens_an_annex_that_is_not_a_dealer_seat(self):
        for beacon_region, annex, door_room, door in ((FROSTFAIR, BELOW, "ff_ice_cellars", "d"),
                                                      (VIGIL, CELLARS, "vg_great_court", "d")):
            lock = ROOMS[door_room]["locks"][door]
            self.assertEqual(lock["flag"], "beacon_" + beacon_region)
            dest = ROOMS[door_room]["exits"][door]
            self.assertEqual(ROOMS[dest]["region"], annex)
            self.assertTrue(ROOMS[dest]["dark"])
            self.assertIs(REGION_INFO[annex]["dealer"], False)
            self.assertTrue(any(ROOMS[r].get("enc") for r in ROOMS if ROOMS[r]["region"] == annex))

    def test_every_key_item_of_the_chain_is_a_key_and_is_given_or_lies_on_a_floor(self):
        chain = list(LATE_RECEIPTS) + ["late_aldrics_letter", "lw_quench_notes", "ff_given_flame", "vg_given_flame",
                                      "vg_sixfold_chart", "ff_wardens_key", "ff_cellar_key", "vg_lens_key",
                                      "hos_belfry_key", "rl_tower_key"]
        on_floor = {i for r in ROOMS.values() for i in r.get("items", [])}
        src = ""
        for name in os.listdir(os.path.join(ROOT, "lamplighter", "areas")):
            if name.endswith(".py"):
                src += read(ROOT, "lamplighter", "areas", name)
        for iid in chain:
            self.assertEqual(ITEMS[iid]["kind"], "key", iid)
            self.assertTrue(iid in on_floor or ('give_once(g, "%s")' % iid) in src or ('"%s"' % iid) in src, iid)
        for iid in ("hos_receipt", "rl_receipt", "lw_receipt", "ff_receipt", "vg_receipt", "lw_quench_notes",
                    "vg_sixfold_chart"):
            self.assertIn(iid, on_floor, iid)
        self.assertNotIn("late_receipt_court", on_floor)                 # Pell gives it, once

    def test_key_items_cannot_be_dropped(self):
        g = new_game()
        g.player.add_item("ff_receipt")
        run(g, "drop receipt")
        self.assertTrue(g.player.has_item("ff_receipt"))

    def test_death_never_wipes_a_key_item(self):
        g = new_game()
        for iid in ("ff_given_flame", "vg_sixfold_chart", "hos_receipt"):
            g.player.add_item(iid)
        g.flags["completed"] = True
        with contextlib.redirect_stdout(io.StringIO()):
            g.death()
        for iid in ("ff_given_flame", "vg_sixfold_chart", "hos_receipt"):
            self.assertTrue(g.player.has_item(iid), iid)


# ============================================================================ 7. an old save (gate 9)
class OldSaveTests(unittest.TestCase):
    def load_old(self, name="v2_current.json"):
        import shutil
        from lamplighter import save
        src = os.path.join(ROOT, "tests", "fixtures", "saves", name)
        with temp_home():
            os.makedirs(save.paths.saves_dir(), exist_ok=True)
            shutil.copyfile(src, save.path_for("main"))
            with contextlib.redirect_stdout(io.StringIO()):
                return Game.load()

    def test_a_save_made_before_m6_gives_every_new_room_its_floor_items(self):
        g = self.load_old()
        self.assertIsNotNone(g)
        for rid, r in new_rooms().items():
            if r.get("items"):
                self.assertEqual(g.room_items[rid], r["items"], rid)
        for rid, iid in (("hos_scriptorium", "hos_receipt"), ("rl_cottage", "rl_receipt"),
                         ("lw_rack_room", "lw_receipt"), ("ff_lending_tent", "ff_receipt"),
                         ("vg_library", "vg_receipt"), ("vg_camera_obscura", "vg_sixfold_chart")):
            self.assertIn(iid, g.room_items[rid])

    def test_the_old_story_state_opens_the_frostfair_after_the_courts_beacon(self):
        for name in ("v2_current.json", "v1_pre_m5.json"):
            g = self.load_old(name)
            lock = ROOMS["gate"]["locks"]["w"]
            g.flags.pop("beacon_Ember Court", None)
            self.assertFalse(g.unlocked(lock), name)
            g.flags["beacon_Ember Court"] = True
            self.assertTrue(g.unlocked(lock), name)
            self.assertTrue(g.unlocked(ROOMS["gate"]["locks"]["e"]) or not g.flags.get("completed"))

    def test_the_old_save_still_plays_with_the_new_rooms(self):
        g = self.load_old()
        g.flags.update(completed=True, **{"beacon_Ember Court": True})
        g.room_id = "gate"
        g.cooldown = {rid: 10 ** 6 for rid in ROOMS}
        g.player.oil = g.player.max_oil
        run(g, "west")
        self.assertEqual(g.room_id, "ff_frost_road")


# ============================================================================ 8. the tools
class ToolTests(unittest.TestCase):
    def go(self, *args):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", args[0])] + list(args[1:]), cwd=ROOT,
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_sim_ring5_runs_for_each_area_group(self):
        out = self.go("sim_ring5.py", "--area", "ff", "--n", "2", "--powers", "50", "--kit", "none")
        self.assertIn("Boss ff_lampmaster", out)
        self.assertIn("Mini-boss ff_ringmaster", out)
        out = self.go("sim_ring5.py", "--area", "vg", "--n", "2", "--powers", "50", "--kit", "kit")
        self.assertIn("Boss vg_prior_eye", out)
        out = self.go("sim_ring5.py", "--area", "hos", "--n", "2")
        self.assertIn("hos_vesper", out)

    def test_sim_economy_runs_and_its_forge_arithmetic_matches_the_spec(self):
        out = self.go("sim_economy.py")
        self.assertIn("checked", out)
        self.assertIn("materials", out)               # forge inputs have their own column: they are not cash
        self.assertIn("days of casual play", out)

    def test_the_economy_module_agrees_with_the_data(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import sim_economy
        finally:
            sys.path.pop(0)
        tiers = sim_economy.tier_costs()
        self.assertAlmostEqual(tiers["legendary"][1], 6.42, places=1)
        self.assertEqual(sim_economy.rent_rate(), 63)
        self.assertEqual(sim_economy.RANGES, {"ff": (1600, 2100), "vg": (1900, 2500)})

    def ring5(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import sim_ring5
        finally:
            sys.path.pop(0)
        return sim_ring5

    def check_args(self, **kw):
        import argparse
        base = dict(area="all", level=0, n=2, kit="both", powers=[1, 25, 50, 75, 100], strict=False)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_check_prints_its_warnings_and_strict_makes_them_fail(self):
        """The per-class floor of spec 14.3 used to be collected and never shown."""
        r5 = self.ring5()
        ck = r5.Checker()
        ck.warn("ff boss none p100 God+3 per-class floor", False, "ashblade below half the class mean 31")
        ck.warn("fine", True, "never shown")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ck.report(["ff"])
        text = out.getvalue()
        self.assertIn("1 warnings", text)
        self.assertIn("WARN ff boss none p100 God+3 per-class floor: ashblade below half the class mean 31", text)
        self.assertNotIn("never shown", text)
        self.assertEqual(ck.exit_code(), 0)
        self.assertEqual(ck.exit_code(strict=True), 1)
        ck.band("x", 50, 10, 5)
        self.assertEqual(ck.exit_code(), 1)

    def run_check(self, **kw):
        r5 = self.ring5()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ck = r5.check(self.check_args(**kw))
        return ck, out.getvalue()

    def test_check_runs_only_the_area_asked_for(self):
        ck, out = self.run_check(area="hos")
        self.assertIn("(hos)", out)
        self.assertEqual(ck.cells, 2)                     # the boss's win and health only
        for text in ck.fails + ck.warns:
            self.assertTrue(text.startswith("hos_vesper") or text.startswith("hos "), text)
        ck, out = self.run_check(area="vg", kit="none", powers=[50])
        for text in ck.fails + ck.warns:
            self.assertFalse(text.startswith(("ff ", "hos", "rl", "lw")), text)

    def test_check_honours_the_kit_and_the_powers_it_is_given(self):
        r5 = self.ring5()
        seen = []
        real = r5.Checker.band

        def spy(self, label, got, want, tol):
            seen.append(label)
            return real(self, label, got, want, tol)
        r5.Checker.band = spy
        try:
            self.run_check(area="ff", kit="none", powers=[50])
            scoped, seen[:] = list(seen), []
            self.run_check(area="ff")
            full = list(seen)
        finally:
            r5.Checker.band = real
        self.assertEqual(len([l for l in scoped if " boss " in l]), len(r5.BUILDS))
        self.assertTrue(all(l.startswith("ff boss none p50 ") for l in scoped if " boss " in l))
        self.assertEqual([l for l in scoped if " mini " in l], ["ff mini none " + b[0] for b in r5.MINI_BUILDS])
        self.assertEqual(len([l for l in full if " boss " in l]), len(r5.BUILDS) * 2 * 5)
        self.assertEqual(len([l for l in full if " mini " in l]), len(r5.MINI_BUILDS) * 2)
        self.assertFalse([l for l in full if l.startswith("vg ")])

    def economy(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import sim_economy
        finally:
            sys.path.pop(0)
        return sim_economy

    def test_gold_an_hour_is_group_gold_plus_junk_and_never_the_forges_materials(self):
        """Section 16.1 defines a fight as group gold plus junk. Rime, Vigil Glass, essences and Hearts are the forge's
        inputs (a Godlike attempt needs four of each, and Odo charges to buy them), so counting their sale value as
        cash counted them twice: they get their own column."""
        e = self.economy()
        for k in ("ff", "vg", "ff_annex", "vg_annex"):
            label, regions, fights = e.PLACES[k]
            gold = junk = mats = 0.0
            for region in regions:
                for grp, w in e.region_groups(region):
                    for eid in grp:
                        lo, hi = ENEMIES[eid]["gold"]
                        gold += w * (lo + hi) / 2.0 / len(regions)
                        for iid, chance in ENEMIES[eid].get("drops", []):
                            if ITEMS[iid]["kind"] == "junk":
                                junk += w * chance * ITEMS[iid]["value"] / len(regions)
                            elif ITEMS[iid]["kind"] == "material":
                                mats += w * chance * ITEMS[iid]["value"] / len(regions)
            s = e.place_stats(k)
            self.assertAlmostEqual(s["gold_hour"], fights * (gold + junk), places=4, msg=k)
            self.assertAlmostEqual(s["materials_hour"], fights * mats, places=4, msg=k)
            self.assertGreater(s["materials_hour"], 0, k)
        self.assertEqual(e.sale_kind("ff_rime"), "material")
        self.assertEqual(e.sale_kind("vg_starglass"), "material")
        self.assertEqual(e.sale_kind("ff_fair_token"), "junk")
        self.assertEqual(e.sale_kind("vg_star_plate"), "junk")

    def test_check_looks_at_the_annex_ratio_the_days_to_godlike_and_the_single_figure_targets(self):
        e = self.economy()
        labels = [label for label, _, _, _ in e.figures()]
        for part in ("pays x1.2 of its area", "days of casual play to the first Godlike", "Hearts an hour",
                     "gold an hour against the spec's 150", "gold an hour against the spec's 450",
                     "gold an hour against the spec's 300"):
            self.assertTrue(any(part in l for l in labels), part)
        by = {label: (lo, hi) for label, _, lo, hi in e.figures()}
        days = [v for k, v in by.items() if "days of casual play" in k][0]
        self.assertAlmostEqual(days[0], 9 * 0.9)
        self.assertAlmostEqual(days[1], 11 * 1.1)
        hearts = [v for k, v in by.items() if "Hearts an hour" in k][0]
        self.assertAlmostEqual(hearts[0], 2.0 * 0.9)
        self.assertAlmostEqual(hearts[1], 3.0 * 1.1)

    def test_the_rent_figure_the_docs_quote_is_the_one_the_tool_uses(self):
        e = self.economy()
        self.assertEqual(e.rent_per_session(), 63 * town.RENT_CAP_HOURS)
        self.assertEqual(e.rent_per_session(), 504)
        plan = read(ROOT, "docs", "V2-PLAN.md")
        self.assertNotIn("(320 a session at the cap)", plan)
        self.assertIn("504 a session at the cap", plan)

    def test_make_code_adds_a_hash_and_nothing_else(self):
        """make_code.py is the only way codes arrive: run it against a copy and read the file back."""
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "tools"))
            shutil.copy(os.path.join(ROOT, "tools", "make_code.py"), os.path.join(tmp, "tools"))
            shutil.copytree(os.path.join(ROOT, "lamplighter"), os.path.join(tmp, "lamplighter"),
                            ignore=shutil.ignore_patterns("saves", "__pycache__"))
            r = subprocess.run([sys.executable, os.path.join(tmp, "tools", "make_code.py"), "Test Code", "7", "a test"],
                               cwd=tmp, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            data = json.loads(read(tmp, "lamplighter", "data", "codes.json"))
            self.assertEqual(len(data), len(CODES) + 1)
            self.assertEqual(data[codes.code_hash("testcode")], {"gems": 7, "label": "a test"})


# ============================================================================ 9. the whole Lending, played
class IntegrationFixTests(unittest.TestCase):
    """Things found when the nine packages were put together."""

    def test_the_hint_names_the_person_to_talk_to_by_a_word_the_parser_knows(self):
        g = new_game()
        g.flags.update({"completed": True, "queen_dead": True, "steward_dead": True, "beacon_Ember Court": True,
                        "ff_signal_seen": True})
        g.room_id = "hesk_gate" if "hesk_gate" in ROOMS else "gate"
        g.visited.add(g.room_id)
        text = " ".join(navigation.hint_lines(g))
        self.assertNotRegex(text, r"talk (ff|vg|hos|rl|lw)_")

    def test_up_to_five_side_quests_show_and_the_ones_where_you_stand_come_first(self):
        g = new_game()
        g.flags.update({"completed": True, "queen_dead": True, "steward_dead": True, "beacon_Ember Court": True})
        g.room_id = "ff_frost_road"
        g.visited.update(["ff_frost_road", "ff_fair_gate", "ff_lending_tent", "ff_midway"])
        for q in ("petals", "starsteel", "wayposts", "wren"):             # the old side quests that used to crowd the area out
            g.quests[q] = 0
        side = [o for o in navigation.objectives(g) if o["side"]]
        self.assertGreater(len(side), 5)
        text = " ".join(navigation.hint_lines(g))
        shown = [o for o in side if o["text"] in text]
        self.assertEqual(len(shown), min(5, len(side)))
        here = [o for o in side if ROOMS[o["room"]]["region"] == FROSTFAIR]
        for o in here[:5]:
            self.assertIn(o["text"], text)

    def test_brann_does_not_meet_corm_twice(self):
        from lamplighter.areas import lw
        g = new_game()
        g.flags.update(lw_foreman_dead=True, late_notes_shown=True)
        text = capture(lw.tell_brann, g)
        self.assertNotIn("Corm. My grandfather.", text)
        self.assertIn("Corm's workshop", text)

    def test_a_hot_meal_at_full_health_still_settles_a_frightened_heart(self):
        g = new_game()
        g.player.add_item("stew")
        g.player.dread = 30
        text = run(g, "use stew")
        self.assertEqual(g.player.dread, 20)
        self.assertIn("calmer", text)
        g.player.add_item("stew")
        g.player.dread = 0
        self.assertIn("full health", run(g, "use stew"))                        # nothing to settle: still refused

    def test_forged_gear_is_not_a_content_error(self):
        """A Long-Quenched weapon (dmg x6 and more) lives in ITEMS during play; the validator is about the data files."""
        g = new_game()
        inst = gear.make("hunting_spear", "legendary", random.Random(3), affixes=[])
        gear.give(g.player, inst)
        ITEMS[inst["id"]]["mult"]["dmg"] = 6.2
        try:
            self.assertEqual([p for p in validate.validate() if inst["id"] in p], [])
        finally:
            del ITEMS[inst["id"]]


class Fate(random.Random):
    """One rng for the whole playthrough: random() is a dial, and the boss's roll is whatever is dialled."""

    def __init__(self):
        super().__init__(11)
        self.value = 0.99            # high: no ambush, no lucky anything
        self.power = None

    def random(self):
        return self.value

    def randint(self, a, b):
        if self.power is not None:
            return max(a, min(b, self.power))
        return super().randint(a, b)


class Fights:
    """Replace g.fight: every fight is answered `outcome`; the enemies are recorded."""

    def __init__(self, g, outcome="win"):
        self.calls = []
        self.outcome = outcome
        g.fight = self

    def __call__(self, ids, intro=None, **kw):
        self.calls.append(list(ids))
        return self.outcome


class Playthrough(unittest.TestCase):
    def setUp(self):
        self.t = [86400.0 * 20000]
        clock.set_clock(lambda: self.t[0])
        self.items_before = set(ITEMS)

    def tearDown(self):
        clock.set_clock(None)
        ui.io.script = []
        for iid in set(ITEMS) - self.items_before:           # (gear instances live in ITEMS: leave none behind)
            del ITEMS[iid]

    # ---------------------------------------------------------------- helpers
    def game(self):
        g = new_game()
        self.g = g
        g.rng = self.fate = Fate()
        self.fights = Fights(g)
        p = g.player
        p.level = 12
        p.gold = 500
        p.add_item("draught", 3)
        p.add_item("strong_draught", 3)
        g.flags.update(completed=True, queen_dead=True, steward_dead=True)
        self.fresh()
        return g

    def fresh(self):
        """Full health and oil, a steady heart, and no ambush anywhere: the player rests between legs."""
        g, p = self.g, self.g.player
        p.hp, p.oil, p.dread = p.max_hp, p.max_oil, 0
        g.cooldown = {rid: 10 ** 6 for rid in ROOMS}

    def at(self, room):
        self.g.room_id = room
        self.g.visited.add(room)
        self.fresh()

    def go(self, *dirs, answers=()):
        """Walk, one real move at a time, answering prompts from `answers`."""
        ui.io.script = list(answers)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            for d in dirs:
                self.g.handle(d)
        text = flat(out.getvalue() + " " + " ".join(self.g.notices))
        self.g.notices.clear()
        return text

    def walk(self, route, answers=()):
        """route: [(dir, expected room)] ... each step asserts where the player ended up."""
        for d, room in route:
            text = self.go(d, answers=answers)
            self.assertEqual(self.g.room_id, room, "going %s: %s" % (d, text[-300:]))

    def say(self, *commands, answers=()):
        return capture(lambda: [self.g.handle(c) for c in commands], answers=answers) + " " + " ".join(self.g.notices)

    def own(self, iid):
        return self.g.player.has_item(iid)

    # ---------------------------------------------------------------- the legs
    def court_beacon(self):
        g = self.g
        self.assertTrue(g.unlocked(ROOMS["gate"]["locks"]["e"]))
        self.at("gate")
        text = self.go("west")
        self.assertEqual(g.room_id, "gate")                                  # the frost wall: not yet
        self.assertIn("relight the Ember Court's beacon", text)
        self.assertEqual(dealer.room_for(g, 5, 20000), None)
        self.at("throne_room")
        text = self.go("light")
        self.assertTrue(g.flags["beacon_Ember Court"])
        self.assertTrue(g.flags["ff_signal_seen"])
        self.assertLess(text.index("great iron bowl"), text.index("second light answers"))     # the Court's own text first
        self.assertTrue(npcs.has_news(g, "hesk"))
        self.assertTrue(npcs.has_news(g, "wizard"))                          # the Roll of Lenders is on offer
        text = run_topic(g, "wizard", "Ask about the Roll")
        self.assertIn("The Frostfair: west of the North Gate", text)
        seat = dealer.room_for(g, 5, 20000)
        self.assertEqual(ROOMS[seat]["region"], FROSTFAIR)

    def frostfair(self):
        g = self.g
        self.at("gate")
        self.walk([("west", "ff_frost_road"), ("west", "ff_fair_gate"), ("south", "ff_lending_tent")])
        self.go("take all")
        self.assertTrue(self.own("ff_receipt"))                              # (1) Hospice and Reedlight come later
        self.assertEqual(g.quest("late_lending"), 0)                         # the journal quest has started
        self.walk([("west", "ff_skate_pond"), ("west", "ff_carousel")])      # the Ringmaster, the mini-boss
        self.assertEqual(self.fights.calls[-1], ["ff_ringmaster"])
        self.assertTrue(g.flags["ff_ringmaster_dead"])
        self.assertTrue(self.own("ff_wardens_key"))
        self.assertTrue(g.flags["ff_gems_ringmaster"])
        self.walk([("north", "ff_lamp_row")])
        self.go("light")
        self.assertTrue(g.flags["lit_ff_lamp_row"])
        self.walk([("north", "ff_wardens_booth")])
        self.go("talk marit", answers=["0"])
        self.assertTrue(self.own("ff_cellar_key"))
        self.assertTrue(g.flags["ff_marit_met"])
        self.walk([("south", "ff_lamp_row"), ("east", "ff_midway")])
        self.go("light")
        self.assertTrue(g.flags["lit_ff_midway"])
        # the great gate is still shut: one post is missing, and it says how many are done
        self.at("ff_great_gate")
        text = self.go("west")
        self.assertEqual(g.room_id, "ff_great_gate")
        self.assertIn("2 of 3 done.", text)
        # the cellar trapdoor: the key and a steady heart (the lock states both)
        self.at("ff_skate_pond")
        g.player.dread = 40
        text = self.go("south")
        self.assertEqual(g.room_id, "ff_skate_pond")
        self.assertIn("Dread under 25", text)
        g.player.dread = 0
        self.walk([("south", "ff_ice_cellars")])
        self.go("take all")
        for iid in ("ff_rime", "core_heart_ice", "core_heart_earth", "ff_greatcoat"):
            self.assertTrue(self.own(iid), iid)
        self.at("ff_skate_pond")
        self.walk([("west", "ff_carousel"), ("west", "ff_sculptors_row")])
        self.go("light")
        self.assertTrue(g.flags["lit_ff_sculptors_row"])
        self.walk([("north", "ff_great_gate")])
        # Hobb: a forced roll of 90 (Ablaze). Look first, then face him.
        self.fresh()
        self.fate.power = 90
        text = self.go("west", answers=["1"])
        self.assertEqual(g.room_id, "ff_wintering")
        self.assertEqual(self.fights.calls[-1], ["ff_lampmaster@90"])
        self.assertTrue(g.flags["ff_lampmaster_dead"])
        self.assertEqual(g.flags["power_ff_lampmaster"], 90)
        self.assertIn("ABLAZE", text)
        self.assertTrue(g.flags["ff_gems_band"])
        self.assertIn("Tell Marit I held it", text)
        self.fresh()
        text = self.go("light")
        self.assertTrue(g.flags["beacon_" + FROSTFAIR])
        self.assertTrue(g.flags["ff_thaw"])
        self.assertNotIn("great iron bowl", text)
        # Hobb is gone; Marit gives her flame, once
        self.walk([("east", "ff_great_gate"), ("east", "ff_lamp_row"), ("north", "ff_wardens_booth")])
        self.go("talk marit", answers=["0"])
        self.assertTrue(self.own("ff_given_flame"))
        self.assertTrue(g.flags["ff_flame_given"])
        # the annex hatch is open now, and the Dealer has left for the Vigil
        self.at("ff_ice_cellars")
        self.walk([("down", "ff_below_stair")])
        self.assertEqual(g.room_id, "ff_below_stair")
        for d in range(20000, 20040):
            seat = dealer.room_for(g, 5, d)
            self.assertTrue(seat is None or ROOMS[seat]["region"] == VIGIL, seat)
        self.assertIn("ff_rime", npcs.stock_for(g, "odo"))

    def vigil(self):
        g = self.g
        self.at("ff_wintering")
        self.walk([("west", "ff_signal_stair"), ("up", "vg_ladder"), ("east", "vg_porters_lodge"),
                   ("east", "vg_great_court")])
        # the library: the receipt
        self.walk([("north", "vg_library")])
        self.go("take all")
        self.assertTrue(self.own("vg_receipt"))
        self.walk([("south", "vg_great_court"), ("east", "vg_orrery_hall")])        # the Great Orrery
        self.assertEqual(self.fights.calls[-1], ["vg_orrery"])
        self.assertTrue(g.flags["vg_orrery_dead"])
        self.assertTrue(self.own("vg_lens_key"))
        self.assertTrue(g.flags["vg_gems_orrery"])
        # the felt door wants a Shadow book and says so
        self.at("vg_mirror_gallery")
        g.player.spells = ["book_fire"]
        text = self.go("south")
        self.assertEqual(g.room_id, "vg_mirror_gallery")
        self.assertIn("Shadow spell book", text)
        g.player.spells = ["book_light", "book_shadow"]
        self.walk([("south", "vg_camera_obscura")])
        self.go("take all")
        for iid in ("vg_sixfold_chart", "vg_starglass", "core_heart_shadow", "vg_astrolabe_rod"):
            self.assertTrue(self.own(iid), iid)
        # the chapel: the mercy path, not the fight
        self.at("vg_reckoning_room")
        before = g.player.gems
        self.walk([("south", "vg_chapel")], answers=["1"])
        self.assertTrue(g.flags["vg_brother_slept"] and g.flags["vg_chapel_done"])
        self.assertEqual(g.player.gems - before, 1)
        self.assertNotIn(["vg_brother", "vg_brother"], self.fights.calls)
        # Hale, in the lens cupboard
        self.walk([("west", "vg_lens_cupboard")])
        self.assertIn("vg_hale", g.present_npcs())
        self.go("talk hale", answers=["1", "0"])
        self.assertTrue(g.flags["vg_hale_met"])
        self.assertFalse(self.own("vg_given_flame"))                                # no flame before the Signal
        # the Eye: a forced roll of 70 (Roused)
        self.at("vg_lens_stair")
        self.fate.power = 70
        text = self.go("east", answers=["1"])
        self.assertEqual(g.room_id, "vg_eye")
        self.assertEqual(self.fights.calls[-1], ["vg_prior_eye@70"])
        self.assertTrue(g.flags["vg_eye_dead"])
        self.assertTrue(g.flags["vg_gems_band"])
        self.fresh()
        self.go("light")
        self.assertTrue(g.flags["beacon_" + VIGIL])
        self.assertTrue(g.flags["vg_signal_sent"])
        # Hale lights his candle from the Signal and gives the flame
        self.at("vg_lens_cupboard")
        self.go("talk hale", answers=["2", "1", "0"])
        self.assertTrue(self.own("vg_given_flame"))
        self.assertTrue(g.flags["vg_hale_slept"])
        self.assertTrue(town.is_invited(g, "vg_almanac"))
        # the cellars are open, and the Dealer is gone for good
        self.at("vg_great_court")
        self.walk([("down", "vg_cellar_stair")])
        for d in range(20000, 20040):
            self.assertIsNone(dealer.room_for(g, 5, d))
        self.assertIn("vg_starglass", npcs.stock_for(g, "odo"))
        # the budget: five hooks and bands met on this road
        self.assertEqual(g.player.gems - self.gems0, 2 + 2 + 1 + 2 + 1, "gems from the hooks and the two bands")

    def old_doors(self):
        """The three older lenders, each through its own lock, met as the lock says."""
        g = self.g
        p = g.player
        # the Hospice: light the waypost at the shrine, then the Almoner's key, then the scriptorium
        self.at("moth_shrine")
        text = self.go("east")
        self.assertEqual(g.room_id, "moth_shrine")
        self.assertIn("Light the waypost", text)
        self.go("light")
        self.walk([("east", "hos_path"), ("east", "hos_gate"), ("south", "hos_cloister")])
        text = self.go("south")
        self.assertEqual(g.room_id, "hos_cloister")
        self.assertIn("Defeat him", text)
        self.walk([("east", "hos_refectory")])
        self.assertEqual(self.fights.calls[-1], ["hos_almoner"])
        self.assertTrue(self.own("hos_belfry_key"))
        self.walk([("west", "hos_cloister"), ("south", "hos_scriptorium")])
        self.go("take all")
        self.assertTrue(self.own("hos_receipt"))
        # the Reedlight: a fire or light book clears the fog; the oil-house has the tower key
        self.at("bog_lights")
        p.spells = []
        text = self.go("south")
        self.assertEqual(g.room_id, "bog_lights")
        self.assertIn("Equip a Fire or Light spell book", text)
        p.spells = ["book_fire"]
        self.walk([("south", "rl_causeway"), ("south", "rl_cottage")])
        self.go("take all")
        self.assertTrue(self.own("rl_receipt"))
        # the Lampwrights' Deep: a Lamp Relic socketed into something worn opens the bronze door
        self.at("crypt_stair")
        text = self.go("south")
        self.assertEqual(g.room_id, "crypt_stair")
        self.assertIn("Lamp Relic", text)
        inst = gear.make("hauberk", "epic", g.rng, affixes=[], relics=[{"base": "relic_lamp", "rarity": "epic"}])
        gear.give(p, inst)
        p.equipment["armor"] = inst["id"]
        p.inventory.pop(inst["id"], None)
        self.walk([("south", "lw_door"), ("east", "lw_mess"), ("east", "lw_workshop")])
        self.assertTrue(g.flags["lw_foreman_dead"])
        self.walk([("south", "lw_rack_room")])
        self.go("take all")
        self.assertTrue(self.own("lw_receipt"))
        self.assertTrue(self.own("lw_quench_notes"))

    def the_letter_and_the_flames(self):
        g = self.g
        p = g.player
        # Pell holds the Court's receipt
        self.assertTrue(npcs.has_news(g, "pell"))
        run_topic(g, "pell", "Ask for the Court's receipt")
        self.assertTrue(self.own("late_receipt_court"))
        self.assertEqual(len(late.receipts_held(g)), 6)
        # the Roll now reads six receipts in hand
        text = run_topic(g, "wizard", "Ask about the Roll")
        self.assertEqual(text.count("receipt in hand"), 6)
        # Orrin opens the letter only when all six are shown
        self.assertTrue(npcs.has_news(g, "orrin"))
        text = run_topic(g, "orrin", "Show him the receipts")
        self.assertTrue(g.flags["late_letter_read"])
        self.assertTrue(self.own("late_aldrics_letter"))
        self.assertIn("Held in trust", ITEMS["late_receipt_court"]["desc"])
        self.assertEqual(g.quest("late_lending"), 1)
        # Brann reads Corm's notes
        run_topic(g, "brann", "Show him Corm's notes")
        self.assertTrue(g.flags["late_notes_shown"])
        # the Ember Smithy: invite, build, and the second anvil
        self.assertEqual(forge.state(g)["slots"], 1)
        p.gold += 3000
        p.add_item("slag", 40)
        p.add_item("cinder", 12)
        town.invite(g, "ember_smithy")
        self.assertTrue(town.start_build(g, "ember_smithy"))
        self.t[0] += 31 * 60
        town.update(g)
        self.assertTrue(town.is_built(g, "ember_smithy"))
        self.assertEqual(forge.state(g)["slots"], 2)
        # Tamsin: both flames, one quench
        self.assertTrue(npcs.has_news(g, "tamsin"))
        text = run_topic(g, "tamsin", "Ask about the third quench")
        self.assertTrue(g.flags["godlike_recipe"])
        self.assertFalse(self.own("ff_given_flame") or self.own("vg_given_flame"))
        self.assertEqual(g.quest("late_lending"), "done")

    def godlike_and_the_long_quench(self):
        g = self.g
        p = g.player
        p.gold = 20000
        # the valve: Odo sells what a bad run of luck used up
        for item in ("ff_rime", "vg_starglass"):
            self.assertIn(item, npcs.stock_for(g, "odo"))
        p.add_item("ff_rime", 20)
        p.add_item("vg_starglass", 20)
        p.add_item("slag", 80)
        p.add_item("saltstone", 20)
        p.add_item("hollow_core", 20)
        spear = gear.make("hunting_spear", "legendary", random.Random(2), affixes=["keen"])
        gear.give(p, spear)
        iid = spear["id"]
        self.assertEqual(forge.missing(g, iid), [])
        gold = p.gold
        ok, msg = forge.start(g, iid)
        self.assertTrue(ok, msg)
        self.assertEqual(p.gold, gold - FORGE["tiers"]["legendary"]["gold"])
        self.assertEqual(forge.free_slots(g), 0)                             # both anvils, a day
        self.t[0] += 1441 * 60
        forge.update(g)
        self.fate.value = 0.0                                                # the one forced seed: this one takes
        res = forge.collect(g, 0)
        self.fate.value = 0.99
        self.assertTrue(res["success"])
        self.assertEqual(res["after"], "godlike")
        godlike = res["item"]
        self.assertEqual(ITEMS[godlike]["rarity"], "godlike")
        # the Long Quench, a week on the fake clock
        ok, msg = quench.start(g, godlike)
        self.assertTrue(ok, msg)
        self.assertTrue(quench.running(g))
        self.t[0] += 6 * 86400
        forge.update(g)
        self.assertEqual(forge.ready_jobs(g), [])
        self.t[0] += 86400 + 60
        forge.update(g)
        self.assertEqual(len(forge.ready_jobs(g)), 1)
        self.fate.value = 0.95                                               # the top outcome: x3.0
        res = forge.collect(g, 0)
        self.fate.value = 0.99
        self.assertEqual(res["kind"], "temper")
        self.assertEqual(ITEMS[godlike]["temper"], 3.0)
        self.assertGreater(ITEMS[godlike]["mult"]["dmg"], 3.0)
        self.assertFalse(quench.running(g))

    def the_apex(self):
        g = self.g
        p = g.player
        # the almanac: built in Hollowmere, and the loft opens on the east side of the Tower
        p.gold += 2000
        p.add_item("vg_starglass", 8)
        p.add_item("slag", 10)
        self.assertTrue(town.start_build(g, "vg_almanac"))
        self.t[0] += 46 * 60
        town.update(g)
        self.assertTrue(town.is_built(g, "vg_almanac"))
        self.assertEqual(forge.state(g)["slots"], 2)                         # no new building adds a forge slot
        self.at("tower")
        self.walk([("west", "vg_loft")])
        self.assertIn("vg_hale", g.present_npcs())
        self.assertTrue(self.own("vg_sixfold_chart"))
        self.assertFalse(g.flags.get("apex_unlocked"))
        self.go("talk hale", answers=["3", "0"])                             # Order, Almanac, Chart
        self.assertTrue(g.flags["vg_chart_read"])
        self.assertTrue(npcs.has_news(g, "mirelle"))
        self.assertTrue(arc.unlock_ready(g))
        capture(arc.unlock_scene, g, answers=[""])
        self.assertTrue(g.flags["apex_unlocked"])
        self.assertTrue(self.own("vg_sixfold_chart"))                        # the chart stays
        self.assertFalse(arc.unlock_ready(g))
        six = [spells.make_book(g, e, "godlike") for e in elements.ELEMENTS]
        self.assertTrue(spells.apex_ready(g, six))

    # ---------------------------------------------------------------- the test
    def test_the_whole_lending_from_the_courts_beacon_to_the_apex(self):
        g = self.game()
        self.gems0 = g.player.gems
        self.court_beacon()
        self.frostfair()
        self.vigil()
        self.old_doors()
        self.the_letter_and_the_flames()
        self.godlike_and_the_long_quench()
        self.the_apex()
        # the state of the world at the end
        for flag in ("ff_lampmaster_dead", "vg_eye_dead", "ff_thaw", "vg_signal_sent", "godlike_recipe",
                     "apex_unlocked", "fin_roll_read", "late_letter_read"):
            self.assertTrue(g.flags.get(flag), flag)
        self.assertEqual(g.quest("late_lending"), "done")
        # the objective line no longer says the story is told while the chain is open, and the hint works
        self.assertTrue(navigation.objectives(g) is not None)

    def test_a_save_in_the_middle_of_the_chain_round_trips(self):
        """Receipts, flames and the recipe flag are ordinary flags and key items: a save loses none of them."""
        g = self.game()
        for r in LATE_RECEIPTS:
            g.player.add_item(r)
        g.player.add_item("ff_given_flame")
        g.flags.update(ff_thaw=True, godlike_recipe=True)
        data = g.to_dict()
        with contextlib.redirect_stdout(io.StringIO()):
            g2 = Game.from_dict(json.loads(json.dumps(data)))
        for r in LATE_RECEIPTS:
            self.assertTrue(g2.player.has_item(r), r)
        self.assertTrue(g2.player.has_item("ff_given_flame"))
        self.assertTrue(g2.flags["godlike_recipe"])


if __name__ == "__main__":
    unittest.main()
