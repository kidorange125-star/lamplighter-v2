"""M6 package hos: the Moth-Saint's Hospice, a Weeping Wood extension behind the Shrine of the Moth."""
import contextlib
import copy
import io
import json
import os
import random
import unittest

from lamplighter import areas, navigation, npcs, sim, ui
from lamplighter.combat import Combat
from lamplighter.content import DATA_DIR, ENEMIES, ITEMS, REGION_INFO, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, run

REGION = "The Moth-Saint's Hospice"
ROOM_IDS = ["hos_path", "hos_gate", "hos_belfry", "hos_orchard", "hos_cloister", "hos_refectory", "hos_scriptorium"]
ENEMY_IDS = ["hos_pilgrim", "hos_waymoth", "hos_almoner", "hos_vesper"]
ITEM_IDS = ["hos_pilgrims_staff", "hos_moth_mantle", "hos_waylamp", "hos_windfall", "hos_belfry_key", "hos_receipt"]

SHRINE_MSG = ("A narrow path runs east behind the saint's worn statue, but the dark there is thick as felt and your "
              "lantern will not push into it. Light the waypost at this shrine (type 'light') and the saint's road will "
              "show.")
BELFRY_MSG = ("The belfry door is barred from inside, and the bar has a keyhole of its own. The Almoner keeps the belfry "
              "key. He keeps it in the refectory, where he is still laying places for guests who will never come.")
SCRIPTORIUM_MSG = ("The scriptorium is bolted from within. The bolt is the Almoner's, and the Almoner is in the "
                   "refectory, east of the cloister. Defeat him and the door will open.")


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def hospice_game(**kw):
    """A game with the wood's waypost lit, in the gate of the Hospice, random ambushes switched off."""
    g = new_game(**kw)
    g.flags["lit_moth_shrine"] = True
    for rid in ROOM_IDS:
        g.cooldown[rid] = 10 ** 6
    return g


def strong(g, cls="warden"):
    """A player who wins any Hospice fight: the real combat runs with the game's own suggested play."""
    g.player = sim.maxed(cls, 12, "saltsteel_saber", "hauberk", "godlike", items={"draught": 3, "oil": 3, "strong_draught": 3})
    g.player.oil = g.player.max_oil

    def fight(ids, intro=None, **kw):
        if intro:
            ui.say(intro)
        return Combat(g, ids, intro=intro, policy=sim.suggested).run()
    g.fight = fight
    return g


def go(g, *dirs, confirm=()):
    """Walk a line of directions through the real move code, answering the DANGER AHEAD prompt if it comes."""
    ui.io.script = list(confirm)
    with quiet():
        for d in dirs:
            g.move(d)


class Content(unittest.TestCase):
    def test_every_package_id_exists(self):
        for rid in ROOM_IDS:
            self.assertIn(rid, ROOMS)
            self.assertEqual(ROOMS[rid]["region"], REGION)
        for eid in ENEMY_IDS:
            self.assertIn(eid, ENEMIES)
        for iid in ITEM_IDS:
            self.assertIn(iid, ITEMS)

    def test_everything_here_starts_with_the_slug(self):
        self.assertEqual(sorted(r for r in ROOMS if r.startswith("hos_")), sorted(ROOM_IDS))
        self.assertEqual(sorted(e for e in ENEMIES if e.startswith("hos_")), sorted(ENEMY_IDS))
        self.assertEqual(sorted(i for i in ITEMS if i.startswith("hos_")), sorted(ITEM_IDS))

    def test_the_region_is_ring_one_levels_three_to_five_and_has_no_dealer(self):
        info = REGION_INFO[REGION]
        self.assertEqual((info["ring"], info["levels"], info["gear"]), (1, "3-5", "Common - Rare"))
        self.assertIs(info["dealer"], False)

    def test_every_room_has_a_description_and_features(self):
        for rid in ROOM_IDS:
            self.assertTrue(ROOMS[rid]["desc"], rid)
            self.assertTrue(ROOMS[rid]["features"], rid)
            self.assertTrue(ROOMS[rid]["dark"], rid)

    def test_every_enemy_has_a_description_and_every_heavy_move_a_tell(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            self.assertTrue(e["desc"], eid)
            moves = list(e["moves"])
            for ph in e.get("phases", []):
                moves += ph["moves"]
            for m in moves:
                self.assertTrue(m.get("tell"), "%s: %s has no tell" % (eid, m["name"]))

    def test_no_hollow_here_is_weak_to_light(self):
        for eid in ENEMY_IDS:
            e = ENEMIES[eid]
            self.assertIn("hollow", e["tags"])
            self.assertNotIn("light", e["weak"], eid)

    def test_the_module_check_is_clean_and_catches_the_mistake(self):
        from lamplighter.areas import hos
        self.assertEqual(hos.CHECK(), [])
        ENEMIES["hos_zz_bad"] = {"name": "Bad", "hp": 1, "atk": 1, "xp": 1, "moves": [], "tags": ["hollow"],
                                 "weak": ["light"]}
        try:
            self.assertEqual(len(hos.CHECK()), 1)
        finally:
            del ENEMIES["hos_zz_bad"]
        self.assertEqual(areas.check(), [])

    def test_the_validator_is_clean_for_this_package(self):
        from lamplighter import validate
        mine = [e for e in validate.validate() if "hos_" in e or "Hospice" in e or "moth_shrine" in e]
        self.assertEqual(mine, [])

    def test_the_boss_rooms_are_flagged_and_fixed(self):
        self.assertEqual(ROOMS["hos_belfry"]["boss"], "hos_vesper_dead")
        self.assertEqual(ROOMS["hos_belfry"]["fixed"]["flag"], "hos_vesper_dead")
        self.assertEqual(ROOMS["hos_belfry"]["fixed"]["enemies"], ["hos_vesper"])
        self.assertEqual(ROOMS["hos_refectory"]["boss"], "hos_almoner_dead")
        self.assertEqual(ROOMS["hos_refectory"]["fixed"]["enemies"], ["hos_almoner"])
        self.assertIn("Are you expected?", ROOMS["hos_refectory"]["fixed"]["intro"])

    def test_random_groups_never_exceed_two_enemies(self):
        for rid in ROOM_IDS:
            for group, weight in ROOMS[rid].get("enc", {}).get("groups", []):
                self.assertLessEqual(len(group), 2, rid)

    def test_room_text_does_not_state_boss_or_waypost_state(self):
        # a desc is printed before and after the fight / the lighting, so it may not claim either state
        stale = ("cold", "steam", "still steaming", "sleeps", "sleeping", ", shut")
        for rid in ROOM_IDS:
            texts = [ROOMS[rid]["desc"]] + list(ROOMS[rid]["features"].values())
            for t in texts:
                for word in stale:
                    self.assertNotIn(word, t.lower(), "%s: %r" % (rid, t[:40]))

    def test_examine_gate_gives_the_lych_gate_and_gatepost_gives_the_waypost(self):
        g = hospice_game()
        g.room_id = "hos_gate"
        self.assertIn("Pilgrims once rested their coffins", run(g, "examine gate"))
        self.assertIn("Pilgrims once rested their coffins", run(g, "examine arch"))
        self.assertIn("A guild waypost", run(g, "examine gatepost"))
        self.assertIn("A guild waypost", run(g, "examine waypost"))

    def test_the_belfry_ladder_leans_toward_the_gate_it_really_is_beside(self):
        exits = ROOMS["hos_belfry"]["exits"]
        self.assertEqual(exits, {"w": "hos_gate"})
        text = next(t for k, t in ROOMS["hos_belfry"]["features"].items() if "ladder" in k.split("|"))
        self.assertIn("west, toward the gate", text)
        self.assertNotIn("east", text)

    def test_no_item_name_starts_with_the_so_equip_text_reads_right(self):
        for iid in ITEM_IDS:
            self.assertFalse(ITEMS[iid]["name"].startswith("The "), iid)
        g = new_game()
        g.player.add_item("hos_waylamp")
        self.assertNotIn("the The", run(g, "equip hos_waylamp"))

    def test_the_vesper_has_two_stages_and_the_phase_message(self):
        v = ENEMIES["hos_vesper"]
        self.assertEqual([p["at"] for p in v["phases"]], [0.5])
        self.assertIn("empty hook", v["phases"][0]["msg"])
        self.assertIn("Beat of Longing", [m["name"] for m in v["phases"][0]["moves"]])

    def test_the_hospice_is_not_tuned_like_a_ring_five_area(self):
        # the side boss is "Antlered Mother x1.8 hp / x1.4 atk" (section 14.6): within 30% of the stand-in
        mother = ENEMIES["antlered_mother"]
        v = ENEMIES["hos_vesper"]
        self.assertAlmostEqual(v["hp"] / (mother["hp"] * 1.8), 1.0, delta=0.3)
        self.assertAlmostEqual(v["atk"] / (mother["atk"] * 1.4), 1.0, delta=0.3)


class Graph(unittest.TestCase):
    def test_exits_match_the_spec_and_come_back(self):
        want = {
            "hos_path": {"w": "moth_shrine", "e": "hos_gate", "s": "hos_orchard"},
            "hos_gate": {"w": "hos_path", "e": "hos_belfry", "s": "hos_cloister"},
            "hos_belfry": {"w": "hos_gate"},
            "hos_orchard": {"n": "hos_path", "e": "hos_cloister"},
            "hos_cloister": {"n": "hos_gate", "w": "hos_orchard", "e": "hos_refectory", "s": "hos_scriptorium"},
            "hos_refectory": {"w": "hos_cloister"},
            "hos_scriptorium": {"n": "hos_cloister"},
        }
        for rid, exits in want.items():
            self.assertEqual(ROOMS[rid]["exits"], exits, rid)
        self.assertEqual(ROOMS["moth_shrine"]["exits"]["e"], "hos_path")
        self.assertEqual(ROOMS["moth_shrine"]["exits"]["w"], "deepwood")        # the old exit is untouched

    def test_the_waypost_and_the_wake_text_belong_to_the_gate(self):
        self.assertTrue(ROOMS["hos_gate"]["waypost"])
        self.assertEqual(ROOMS["hos_gate"]["wake"].count("%d"), 1)
        self.assertEqual([r for r in ROOM_IDS if ROOMS[r].get("waypost")], ["hos_gate"])

    def test_the_attach_file_is_the_only_edit_to_the_wood(self):
        with open(os.path.join(DATA_DIR, "attach", "hos.json"), encoding="utf-8") as f:
            attach = json.load(f)
        self.assertEqual(list(attach), ["moth_shrine"])
        self.assertEqual(attach["moth_shrine"]["exits"], {"e": "hos_path"})
        self.assertEqual(attach["moth_shrine"]["locks"]["e"]["flag"], "lit_moth_shrine")


class Locks(unittest.TestCase):
    def test_the_shrine_lock_text_and_both_states(self):
        g = hospice_game()
        g.flags.pop("lit_moth_shrine")
        g.flags["shrine_moths"] = True               # the moths on the waypost are already dealt with
        g.room_id = "moth_shrine"
        lock = ROOMS["moth_shrine"]["locks"]["e"]
        self.assertEqual(lock["msg"], SHRINE_MSG)
        go(g, "e")
        self.assertEqual(g.room_id, "moth_shrine")
        self.assertEqual(g.notices[-1], SHRINE_MSG)
        g.flags["lit_moth_shrine"] = True
        go(g, "e")
        self.assertEqual(g.room_id, "hos_path")
        go(g, "w")
        self.assertEqual(g.room_id, "moth_shrine")

    def test_lighting_the_waypost_opens_the_road(self):
        g = hospice_game()
        g.flags.pop("lit_moth_shrine")
        g.room_id = "moth_shrine"
        g.flags["shrine_moths"] = True
        g.player.oil = 50
        with quiet():
            g.cmd_light("")
        self.assertTrue(g.flags["lit_moth_shrine"])
        go(g, "e")
        self.assertEqual(g.room_id, "hos_path")

    def test_the_belfry_door_wants_the_key(self):
        g = hospice_game()
        g.room_id = "hos_gate"
        self.assertEqual(ROOMS["hos_gate"]["locks"]["e"]["msg"], BELFRY_MSG)
        go(g, "e")
        self.assertEqual(g.room_id, "hos_gate")
        self.assertEqual(g.notices[-1], BELFRY_MSG)
        g.player.add_item("hos_belfry_key")
        g.fight = lambda ids, intro=None, **kw: "fled"
        go(g, "e", confirm=["y"])
        self.assertEqual(g.room_id, "hos_belfry")

    def test_the_scriptorium_bolt_wants_the_almoner_dead(self):
        g = hospice_game()
        g.room_id = "hos_cloister"
        self.assertEqual(ROOMS["hos_cloister"]["locks"]["s"]["msg"], SCRIPTORIUM_MSG)
        go(g, "s")
        self.assertEqual(g.room_id, "hos_cloister")
        self.assertEqual(g.notices[-1], SCRIPTORIUM_MSG)
        g.flags["hos_almoner_dead"] = True
        go(g, "s")
        self.assertEqual(g.room_id, "hos_scriptorium")

    def test_the_scriptorium_stays_open_after_a_wizard_call_back_pops_the_boss_flag(self):
        g = hospice_game()
        g.room_id = "hos_cloister"
        g.flags["hos_almoner_dead"] = True
        go(g, "s", "n")                                # walking through remembers it
        self.assertTrue(g.flags["hos_scriptorium_open"])
        del g.flags["hos_almoner_dead"]                # the call-back clears the fight, not the open door
        go(g, "s")
        self.assertEqual(g.room_id, "hos_scriptorium")
        self.assertEqual(ROOMS["hos_cloister"]["locks"]["s"]["remember"], "hos_scriptorium_open")

    def test_the_locks_name_what_they_need_and_where_to_get_it(self):
        self.assertIn("waypost", SHRINE_MSG)
        self.assertIn("refectory", BELFRY_MSG)
        self.assertIn("refectory", SCRIPTORIUM_MSG)
        for rid in ("hos_gate", "hos_cloister"):
            for lock in ROOMS[rid]["locks"].values():
                self.assertTrue(lock["msg"])


class Fights(unittest.TestCase):
    def test_the_almoner_then_the_vesper(self):
        g = strong(hospice_game())
        g.room_id = "hos_cloister"
        go(g, "e")
        self.assertEqual(g.room_id, "hos_refectory")
        self.assertTrue(g.flags.get("hos_almoner_dead"))
        self.assertTrue(g.player.has_item("hos_belfry_key"))
        self.assertEqual(g.player.gems, 2)
        go(g, "w", "n")
        self.assertEqual(g.room_id, "hos_gate")
        go(g, "e", confirm=["y"])
        self.assertEqual(g.room_id, "hos_belfry")
        self.assertTrue(g.flags.get("hos_vesper_dead"))
        self.assertTrue(g.player.has_item("hos_waylamp"))

    def test_the_almoner_gives_the_key_and_the_gems_only_once(self):
        g = strong(hospice_game())
        g.room_id = "hos_refectory"
        with quiet():
            areas.lookup("AFTER_FIXED", "hos_almoner_dead", g)
        self.assertEqual(g.player.gems, 2)
        self.assertEqual(g.player.inventory["hos_belfry_key"], 1)
        with quiet():
            areas.lookup("AFTER_FIXED", "hos_almoner_dead", g)
        self.assertEqual(g.player.gems, 2)
        self.assertEqual(g.player.inventory["hos_belfry_key"], 1)

    def test_a_second_win_does_not_duplicate_the_key(self):
        g = strong(hospice_game())
        g.room_id = "hos_cloister"
        go(g, "e")
        self.assertEqual(g.player.inventory["hos_belfry_key"], 1)
        del g.flags["hos_almoner_dead"]                # a call-back pops the flag; the Almoner fights again
        go(g, "w", "e")
        self.assertTrue(g.flags["hos_almoner_dead"])
        self.assertEqual(g.player.inventory["hos_belfry_key"], 1)
        self.assertEqual(g.player.gems, 2)

    def test_the_waylamp_is_given_once_only(self):
        g = strong(hospice_game())
        g.room_id = "hos_belfry"
        with quiet():
            areas.lookup("AFTER_FIXED", "hos_vesper_dead", g)
            areas.lookup("AFTER_FIXED", "hos_vesper_dead", g)
        self.assertEqual(g.player.inventory["hos_waylamp"], 1)
        self.assertTrue(g.flags["got_hos_waylamp"])
        g.player.inventory.pop("hos_waylamp")           # even if it were lost, a call-back does not mint another
        with quiet():
            areas.lookup("AFTER_FIXED", "hos_vesper_dead", g)
        self.assertNotIn("hos_waylamp", g.player.inventory)

    def test_the_vesper_first_kill_gems_are_the_engine_s(self):
        g = strong(hospice_game())
        g.room_id = "hos_refectory"
        g.flags["hos_almoner_dead"] = True
        g.room_id = "hos_gate"
        g.player.add_item("hos_belfry_key")
        go(g, "e", confirm=["y"])
        self.assertTrue(g.flags.get("gems_hos_vesper"))
        self.assertEqual(g.player.gems, 3)

    def test_the_boss_tip_is_shown_before_the_belfry(self):
        self.assertIn("flares do double", navigation.boss_tip("hos_belfry"))
        self.assertIn("30", navigation.boss_tip("hos_belfry"))

    def test_the_vesper_is_fair_for_a_level_four_player_in_the_woods_gear(self):
        rates = {}
        ui.io.mute = True
        try:
            for cls in ("warden", "wayfarer", "ashblade"):
                weapon = "ashwood_rod" if cls == "ashblade" else "hunting_spear"
                wins = 0
                for seed in range(100):
                    outcome, _, _, _ = sim.fight(["hos_vesper"], sim.suggested, seed, cls=cls, level=4, weapon=weapon,
                                                 room="hos_belfry", items={"draught": 3, "oil": 3})
                    wins += outcome == "win"
                rates[cls] = wins / 100
        finally:
            ui.io.mute = False
        for cls, rate in rates.items():                 # the Warden is the hard seat, so it gets the looser floor
            self.assertGreaterEqual(rate, 0.8, cls)
            self.assertLessEqual(rate, 0.99 + 1e-9, cls)
        self.assertGreaterEqual(sum(rates.values()) / 3, 0.9, rates)    # spec 6.3 / 14.5: 90-97% over the classes

    def test_the_vesper_drinks_oil_and_a_blind_player_is_told_to_guard_dusk(self):
        moves = {m["name"]: m for m in ENEMIES["hos_vesper"]["moves"]}
        self.assertEqual((moves["Drink the Flame"]["kind"], moves["Drink the Flame"]["drain"]), ("drain", 12))
        self.assertEqual(moves["Dusk"]["kind"], "heavy")
        self.assertEqual(moves["Scale Dust"]["status"], ["blind", 2, 0])
        late = {m["name"]: m for m in ENEMIES["hos_vesper"]["phases"][0]["moves"]}
        self.assertEqual(late["Drink the Flame"]["drain"], 14)
        self.assertEqual(late["Beat of Longing"]["status"], ["weak", 2, 0])


class Floor(unittest.TestCase):
    def test_the_receipt_waits_on_the_scriptorium_floor_of_a_new_game(self):
        g = new_game()
        self.assertIn("hos_receipt", g.room_items["hos_scriptorium"])
        for iid in ("hos_pilgrims_staff", "hos_moth_mantle", "strong_draught"):
            self.assertIn(iid, g.room_items["hos_scriptorium"])
        self.assertEqual(sorted(g.room_items["hos_orchard"]), sorted(["hos_windfall", "hos_windfall", "honeycake"]))
        self.assertEqual(g.room_items["hos_cloister"], ["oil"])

    def test_a_save_made_before_the_package_existed_still_finds_the_receipt(self):
        g = new_game()
        data = g.to_dict()
        for rid in [r for r in data["room_items"] if r.startswith("hos_")]:
            del data["room_items"][rid]
        h = Game.from_dict(copy.deepcopy(data))
        self.assertIn("hos_receipt", h.room_items["hos_scriptorium"])
        self.assertEqual(h.room_items["hos_orchard"].count("hos_windfall"), 2)

    def test_the_receipt_is_a_key_item_and_cannot_be_dropped(self):
        g = new_game()
        g.room_id = "hos_scriptorium"
        g.flags["hos_scriptorium_open"] = True
        run(g, "take hos_receipt")
        run(g, "take all")
        self.assertTrue(g.player.has_item("hos_receipt"))
        self.assertEqual(ITEMS["hos_receipt"]["kind"], "key")
        self.assertTrue(ITEMS["hos_receipt"]["desc"].startswith("Received of the Hospice of the Moth-Saint"))
        self.assertIn("He minds.", ITEMS["hos_receipt"]["desc"])

    def test_the_gear_matches_the_table(self):
        staff, mantle, lamp = ITEMS["hos_pilgrims_staff"], ITEMS["hos_moth_mantle"], ITEMS["hos_waylamp"]
        self.assertEqual((staff["kind"], staff["rarity"], staff["stats"], staff["mult"]),
                         ("weapon", "rare", {"atk": 8, "wil": 5}, {"light": 1.12}))
        self.assertEqual((mantle["kind"], mantle["stats"]), ("armor", {"def": 6, "agi": 2, "dodge": 3}))
        self.assertEqual((lamp["kind"], lamp["stats"]), ("trinket", {"wil": 3, "hp": 12, "oil_save": 1}))
        self.assertEqual(ITEMS["hos_windfall"]["use"], {"heal": 25, "dread": -10})
        self.assertEqual(ITEMS["hos_belfry_key"]["kind"], "key")

    def test_a_windfall_pear_heals_and_calms(self):
        g = new_game()
        p = g.player
        p.hp, p.dread = 10, 40
        p.add_item("hos_windfall")
        with quiet():
            g.cmd_use("hos_windfall")
        self.assertEqual(p.hp, 35)
        self.assertEqual(p.dread, 30)


class Corvin(unittest.TestCase):
    def labels(self, g):
        return [label for label, _ in areas.topics(g, "corvin")]

    def test_no_topic_before_the_waypost_is_lit(self):
        g = new_game()
        self.assertEqual(self.labels(g), [])

    def test_the_road_topic_comes_with_the_waypost_and_goes_when_told(self):
        g = new_game()
        g.flags["lit_moth_shrine"] = True
        self.assertEqual(self.labels(g), ["Ask about the road behind the shrine"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dict((l, h) for l, h in areas.topics(g, "corvin"))["Ask about the road behind the shrine"](g)
        self.assertIn("I held the ladder", out.getvalue())
        self.assertTrue(g.flags["hos_corvin_told"])
        self.assertEqual(self.labels(g), [])

    def test_the_vesper_topic_needs_the_moth_dead_and_gives_the_cakes_once(self):
        g = new_game()
        self.assertNotIn("Tell Corvin about the Vesper Moth", self.labels(g))
        g.flags["hos_vesper_dead"] = True
        self.assertIn("Tell Corvin about the Vesper Moth", self.labels(g))
        handler = dict(areas.topics(g, "corvin"))["Tell Corvin about the Vesper Moth"]
        before = g.player.inventory.get("honeycake", 0)
        with quiet():
            handler(g)
        self.assertEqual(g.player.inventory["honeycake"], before + 3)
        self.assertTrue(g.flags["hos_corvin_vesper"])
        self.assertTrue(g.flags["got_hos_corvin_gift"])
        self.assertNotIn("Tell Corvin about the Vesper Moth", self.labels(g))
        g.flags["hos_corvin_vesper"] = False            # even asked again, the gift is not repeated
        with quiet():
            handler(g)
        self.assertEqual(g.player.inventory["honeycake"], before + 3)

    def test_the_receipt_topic_needs_the_receipt(self):
        g = new_game()
        self.assertNotIn("Show Corvin the receipt", self.labels(g))
        g.player.add_item("hos_receipt")
        self.assertIn("Show Corvin the receipt", self.labels(g))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dict(areas.topics(g, "corvin"))["Show Corvin the receipt"](g)
        self.assertIn("He minds. He does mind.", out.getvalue())
        self.assertIn("Thank you for writing that down.", out.getvalue())
        self.assertTrue(g.flags["hos_corvin_receipt"])
        self.assertNotIn("Show Corvin the receipt", self.labels(g))
        self.assertTrue(g.player.has_item("hos_receipt"))      # he hands it back; Orrin will want it

    def test_corvin_s_menu_shows_the_topic_and_runs_it(self):
        g = new_game()
        g.flags.update(corvin_met=True, lit_moth_shrine=True)
        g.quests["corvin"] = 1
        ui.io.script = ["3", "0"]               # trade/mother are the caller's two options; ours is third; then leave
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            npcs.talk(g, "corvin")
        self.assertTrue(g.flags["hos_corvin_told"])
        self.assertIn("Ask about the road behind the shrine", out.getvalue())


class Hooks(unittest.TestCase):
    def test_the_rumour_follows_corvin_s_story(self):
        g = new_game()
        self.assertEqual([r for r in areas.rumours(g) if "Corvin" in r], [])
        g.flags["hos_corvin_told"] = True
        self.assertIn("Corvin's started sweeping the path behind the shrine. Says he's spring-cleaning. It's October.",
                      areas.rumours(g))

    def collect(self, g):
        found = []
        areas.call_each("OBJECTIVES", g, lambda text, room, side=False: found.append((text, room, side)))
        return [f for f in found if "Hospice" in f[0] or "Vesper" in f[0] or "Shrine of the Moth" in f[0]]

    def test_objectives_follow_the_chain_and_are_all_side(self):
        g = new_game()
        self.assertEqual(self.collect(g), [])
        g.visited.add("moth_shrine")
        found = self.collect(g)
        self.assertEqual([(r, s) for _, r, s in found], [("moth_shrine", True)])
        g.flags["lit_moth_shrine"] = True
        self.assertEqual(self.collect(g), [])
        g.visited.add("hos_path")
        self.assertEqual([r for _, r, _ in self.collect(g)], ["hos_refectory"])
        g.flags["hos_almoner_dead"] = True
        self.assertEqual([r for _, r, _ in self.collect(g)], ["hos_belfry"])
        g.flags["hos_vesper_dead"] = True
        self.assertEqual(self.collect(g), [])
        for _, _, side in found:
            self.assertTrue(side)

    def test_the_gate_wakes_you_with_the_cloak(self):
        g = hospice_game()
        g.last_rest = "hos_gate"
        g.room_id = "hos_belfry"
        g.player.gold = 100
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            g.death()
        self.assertEqual(g.room_id, "hos_gate")
        self.assertIn("beside the polished hook", out.getvalue())
        self.assertIn("lighter by 50 gold", out.getvalue())

    def test_lighting_the_hospice_waypost_does_not_replay_the_tollroad(self):
        g = hospice_game()
        g.room_id = "hos_gate"
        g.player.oil = 50
        xp = g.player.xp
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            g.cmd_light("")
        self.assertTrue(g.flags["lit_hos_gate"])
        self.assertNotIn("Tollroad", out.getvalue())
        self.assertEqual(g.player.xp, xp)

    def test_no_hook_key_clashes_with_another_package(self):
        # collect() raises on a duplicate key, so this fails if a hos key is not unique
        self.assertIn("hos_vesper_dead", areas.collect("AFTER_FIXED"))
        self.assertIn("hos_belfry", areas.collect("BOSS_TIPS"))
        self.assertIn("corvin", areas.merged("TOPICS"))


class Reachability(unittest.TestCase):
    def test_all_seven_rooms_are_reachable_in_play(self):
        """Walk the real game from the wood: road, orchard, cloister, the Almoner, the scriptorium, the gate, the belfry."""
        g = strong(hospice_game())
        g.room_id = "moth_shrine"
        seen = set()
        for d in ("e", "s", "e", "e", "w", "s", "n", "n", "e"):
            go(g, d, confirm=["y"])
            seen.add(g.room_id)
        self.assertEqual(seen, set(ROOM_IDS))
        self.assertTrue(g.flags["hos_vesper_dead"])

    def test_a_random_walker_finds_every_room(self):
        g = hospice_game(seed=7)
        g.player.hp = 10 ** 6
        g.flags["hos_almoner_dead"] = True
        g.player.add_item("hos_belfry_key")
        g.flags["hos_vesper_dead"] = True
        g.room_id = "hos_path"
        rng = random.Random(3)
        seen = {g.room_id}
        for _ in range(400):
            d = rng.choice(sorted(ROOMS[g.room_id]["exits"]))
            if d == "w" and g.room_id == "hos_path":
                continue
            go(g, d, confirm=["y"])
            seen.add(g.room_id)
        self.assertEqual(seen, set(ROOM_IDS))


if __name__ == "__main__":
    unittest.main()
