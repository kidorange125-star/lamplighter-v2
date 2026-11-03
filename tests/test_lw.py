"""M6 package lw: the Lampwrights' Deep (docs/M6-SPEC.md section 8): the relic door, the Last Foreman, the rack room,
Brann's grandfather, and the numbers that make the place fit its ring."""
import contextlib
import copy
import io
import unittest

from lamplighter import areas, dealer, events, gear, navigation, sim, validate
from lamplighter.content import ENEMIES, ITEMS, REGION_INFO, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, run

REGION = "The Lampwrights' Deep"
LW_ROOMS = ["lw_door", "lw_mess", "lw_workshop", "lw_gallery", "lw_glassworks", "lw_rack_room"]
LW_ENEMIES = ["lw_glass_ghoul", "lw_lampling", "lw_foreman"]
LW_ITEMS = ["lw_lampwright_hammer", "lw_apron", "lw_pit_lamp", "lw_lamp_blank", "lw_receipt", "lw_quench_notes"]
DOOR = ROOMS["crypt_stair"]["locks"]["s"]


def at(g, rid):
    g.room_id = rid
    g.visited.add(rid)
    for r in LW_ROOMS:                   # no random ambush in the middle of a lock test
        g.cooldown[r] = 10 ** 6


def wear(g, base, relic, slot, rarity="epic"):
    """Make a piece of gear with a socketed relic and put it on (or just in the pack when slot is None)."""
    inst = gear.make(base, "epic", g.rng, affixes=[], relics=[{"base": relic, "rarity": rarity}])
    gear.give(g.player, inst)
    if slot:
        g.player.equipment[slot] = inst["id"]
    return inst


class DoorTests(unittest.TestCase):
    """The bronze door in the Crypt Stair wants a Lamp Relic socketed into something you wear."""

    def setUp(self):
        self.g = new_game()
        at(self.g, "crypt_stair")

    def test_the_attach_file_put_the_door_in_the_crypt_stair(self):
        self.assertEqual(ROOMS["crypt_stair"]["exits"]["s"], "lw_door")
        self.assertEqual(ROOMS["lw_door"]["exits"]["n"], "crypt_stair")
        self.assertEqual(DOOR["relic"], "lamp")
        self.assertEqual(DOOR["remember"], "lw_door_open")
        self.assertIn("Lamp Relic", DOOR["msg"])
        self.assertIn("Tallow", DOOR["msg"])
        self.assertIn("Brann", DOOR["msg"])

    def shut(self):
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "crypt_stair")

    def test_shut_with_no_relic(self):
        self.shut()
        self.assertEqual(self.g.notices[-2], DOOR["msg"])
        self.assertEqual(self.g.notices[-1], "{grey}Worn relics: none{/}")

    def test_shut_with_a_relic_in_the_pack_but_not_socketed(self):
        self.g.player.add_item("relic_lamp")
        self.shut()
        self.assertEqual(self.g.notices[-1], "{grey}Worn relics: none{/}")

    def test_shut_with_a_lamp_relic_socketed_but_not_worn(self):
        wear(self.g, "hauberk", "relic_lamp", None)
        self.shut()

    def test_shut_with_an_ember_relic_socketed(self):
        wear(self.g, "hunting_spear", "relic_ember", "weapon")
        self.shut()
        self.assertEqual(self.g.notices[-1], "{grey}Worn relics: Ember (epic){/}")

    def test_open_with_a_lamp_relic_in_armour_weapon_and_trinket(self):
        for base, slot in (("hauberk", "armor"), ("hunting_spear", "weapon"), ("saints_tooth", "trinket")):
            self.g = new_game()
            at(self.g, "crypt_stair")
            wear(self.g, base, "relic_lamp", slot)
            out = run(self.g, "s")
            self.assertEqual(self.g.room_id, "lw_door", slot)
            self.assertIn("the bronze folds back like a flower", " ".join(out.split()), slot)
            self.assertTrue(self.g.flags["lw_door_open"], slot)

    def test_before_the_first_pass_it_is_a_live_check(self):
        gear_inst = wear(self.g, "hauberk", "relic_lamp", "armor")
        self.assertTrue(self.g.unlocked(DOOR))
        self.assertEqual(self.g.lock_status(DOOR), "Worn relics: Lamp (epic)")
        self.g.player.equipment.pop("armor")                  # took it off again before walking through
        self.assertFalse(self.g.unlocked(DOOR))
        self.shut()
        self.assertEqual(self.g.notices[-1], "{grey}Worn relics: none{/}")
        self.assertNotIn("lw_door_open", self.g.flags)
        self.g.player.equipment["armor"] = gear_inst["id"]
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "lw_door")

    def test_after_the_first_pass_the_door_stays_open_without_the_relic(self):
        wear(self.g, "hauberk", "relic_lamp", "armor")
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "lw_door")
        self.g.player.equipment.pop("armor")
        self.assertTrue(self.g.unlocked(DOOR))
        run(self.g, "n")
        self.assertEqual(self.g.room_id, "crypt_stair")
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "lw_door")

    def test_the_story_rewind_does_not_shut_it_again(self):
        wear(self.g, "hauberk", "relic_lamp", "armor")
        run(self.g, "s")
        for k in [k for k in self.g.flags if k.startswith("opened_")]:
            self.g.flags.pop(k)                               # what a Wizard rewind does
        self.g.player.equipment.pop("armor")
        self.assertTrue(self.g.unlocked(DOOR))


class RackRoomTests(unittest.TestCase):
    def setUp(self):
        self.g = new_game()
        at(self.g, "lw_workshop")
        self.lock = ROOMS["lw_workshop"]["locks"]["s"]

    def test_shut_until_the_foreman_dies(self):
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "lw_workshop")
        self.assertEqual(self.g.notices[-1], self.lock["msg"])
        self.assertIn("Defeat the Last Foreman", self.lock["msg"])

    def test_open_after_the_foreman_and_open_for_good_after_a_call_back(self):
        self.g.flags["lw_foreman_dead"] = True
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "lw_rack_room")
        self.assertTrue(self.g.flags["lw_rack_open"])
        run(self.g, "n")                                      # back in the workshop while he is still dead
        self.assertEqual(self.g.room_id, "lw_workshop")
        self.g.flags.pop("lw_foreman_dead")                   # the Wizard calls him back
        self.assertTrue(self.g.unlocked(self.lock))
        run(self.g, "s")
        self.assertEqual(self.g.room_id, "lw_rack_room")

    def test_the_foreman_is_a_fixed_boss_fight_in_the_workshop(self):
        room = ROOMS["lw_workshop"]
        self.assertEqual(room["fixed"]["flag"], "lw_foreman_dead")
        self.assertEqual(room["fixed"]["enemies"], ["lw_foreman"])
        self.assertEqual(room["boss"], "lw_foreman_dead")
        self.assertEqual(room["boss_name"], "The Last Foreman")
        self.assertIn("Mind the edge, lad", room["fixed"]["intro"])
        self.assertNotIn("enc", room)

    def test_the_hooks_for_the_foreman_and_the_door(self):
        self.assertIn("lw_foreman_dead", areas.collect("AFTER_FIXED"))
        self.assertIn(("crypt_stair", "s"), areas.collect("UNLOCK"))
        self.assertIn("Pour the Crucible", navigation.boss_tip("lw_workshop"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            events.after_fixed(self.g, "lw_foreman_dead")
        text = " ".join(out.getvalue().split())
        self.assertIn("Shift's over", text)
        self.assertIn("in Corm's voice", text)
        self.assertNotIn("stool", text)      # the room (static) shows the stool empty and the apron on him, not on a nail

    def test_the_workshop_does_not_contradict_the_foreman_scene(self):
        desc = ROOMS["lw_workshop"]["desc"]
        self.assertNotIn("apron on a nail", desc)           # he wears the apron (lock msg, phase msg): the nail is empty
        self.assertIn("empty nail", desc)
        self.assertIn("apron", ROOMS["lw_workshop"]["locks"]["s"]["msg"])

    def test_every_object_the_workshop_text_names_can_be_examined(self):
        at(self.g, "lw_workshop")
        for noun in ("apron", "rack", "glass", "crucible", "bench", "stool", "ledger", "spectacles", "mug", "sums"):
            out = run(self.g, "examine " + noun)
            self.assertNotIn("nothing special", out, noun)

    def test_the_rack_room_holds_the_receipt_notes_and_gear(self):
        self.assertEqual(sorted(ROOMS["lw_rack_room"]["items"]),
                         sorted(["lw_receipt", "lw_quench_notes", "lw_lampwright_hammer", "lw_apron", "lw_pit_lamp",
                                 "hollow_core", "strong_draught", "strong_draught"]))
        for iid in ("lw_receipt", "lw_quench_notes"):
            self.assertEqual(ITEMS[iid]["kind"], "key")
            self.assertEqual(ITEMS[iid]["value"], 0)


class ForemanTests(unittest.TestCase):
    def setUp(self):
        self.f = ENEMIES["lw_foreman"]

    def test_the_numbers_and_the_elements(self):
        self.assertEqual((self.f["hp"], self.f["atk"], self.f["def"], self.f["xp"]), (420, 21, 14, 260))
        self.assertEqual(self.f["gold"], [160, 200])
        self.assertEqual(self.f["weak"], ["water", "ice"])
        self.assertEqual(self.f["resist"], ["fire", "earth"])
        self.assertEqual(set(self.f["tags"]), {"construct", "boss"})

    def test_the_charge_leads_to_a_heavy_extra_move_with_a_tell(self):
        charge = next(m for m in self.f["moves"] if m["kind"] == "charge")
        self.assertEqual(charge["name"], "Gather Heat")
        self.assertEqual(charge["then"], "Pour the Crucible")
        self.assertEqual(charge["weight"], 2)
        self.assertIn("POUR THE CRUCIBLE is coming", charge["tell"])
        heavy = self.f["extra_moves"]["Pour the Crucible"]
        self.assertEqual((heavy["kind"], heavy["power"]), ("heavy", 3.0))
        self.assertTrue(heavy["tell"])

    def test_phase_half_adds_careful_now_and_keeps_the_charge(self):
        (phase,) = self.f["phases"]
        self.assertEqual(phase["at"], 0.5)
        self.assertIn("Corm's apron smoulders", phase["msg"])
        self.assertIn("Mind the edge, lad", phase["msg"])
        before = {m["name"] for m in self.f["moves"]}
        after = {m["name"] for m in phase["moves"]}
        self.assertEqual(after - before, {"Careful Now"})
        self.assertTrue(before <= after)
        careful = next(m for m in phase["moves"] if m["name"] == "Careful Now")
        self.assertEqual((careful["kind"], careful["weight"]), ("defend", 1))

    def test_he_really_charges_and_changes_phase_in_a_fight(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            outcome, rounds, _, _ = sim.fight(["lw_foreman"], sim.suggested, 3, cls="wayfarer", level=7,
                                              weapon="saltsteel_saber", armor="drowned_mail",
                                              items={"draught": 3, "oil": 3})
        text = buf.getvalue()
        self.assertIn("POUR THE CRUCIBLE is coming", text)
        self.assertIn("Corm's apron smoulders", text)
        self.assertGreater(rounds, 3)
        self.assertIn(outcome, ("win", "dead"))

    def test_the_warden_is_not_far_behind_the_other_classes(self):
        """Calibration: the default kit (3 draughts, 3 oil) at level 7 should leave a warden a fair fight."""
        res = sim.win_rate(["lw_foreman"], sim.suggested, n=30, room="lw_workshop", level=7, cls="warden",
                           weapon="saltsteel_saber", armor="hauberk")
        self.assertGreaterEqual(res["win"], 0.4)

    def test_a_level_seven_player_can_win(self):
        items = {"draught": 3, "strong_draught": 3, "oil": 3}
        lantern = {"shroud": True, "trim": True, "lens": True}

        def build():
            return sim.build_player(cls="wayfarer", level=7, weapon="saltsteel_saber", armor="hauberk", items=items,
                                    lantern=lantern)
        res = sim.win_rate(["lw_foreman"], sim.suggested, n=12, builder=build, room="lw_workshop")
        self.assertGreaterEqual(res["win"], 0.6)


class BrannTests(unittest.TestCase):
    def setUp(self):
        self.g = new_game()
        at(self.g, "smithy")
        self.g.flags["brann_met"] = True
        self.g.quests["starsteel"] = "done"
        self.g.player.lantern["shroud"] = True               # leaves Brann just forge, trade and the area topic

    TOPIC = "Tell Brann about the Lampwrights' Deep"

    def labels(self):
        """Our topics only: other packages (late) add their own to Brann's menu."""
        return [label for label, _ in areas.topics(self.g, "brann") if "Lampwrights" in label]

    def menu_number(self):
        """Where our topic sits in Brann's menu: forge, trade, then the area topics in module order."""
        all_labels = [label for label, _ in areas.topics(self.g, "brann")]
        return str(2 + all_labels.index(self.TOPIC) + 1)

    def test_not_offered_before_the_foreman_dies(self):
        self.assertEqual(self.labels(), [])

    def test_offered_after_the_foreman_and_gone_once_told(self):
        self.g.flags["lw_foreman_dead"] = True
        self.assertEqual(self.labels(), [self.TOPIC])
        out = run(self.g, "talk brann", answers=[self.menu_number(), "0"])
        self.assertTrue(self.g.flags["lw_brann_told"])
        self.assertIn("You: Tell Brann about the Lampwrights' Deep", out)
        self.assertIn("puts the hammer down, which you have never seen him do", " ".join(out.split()))
        self.assertIn("a lamp for the sun", out)
        self.assertEqual(self.labels(), [])
        again = run(self.g, "talk brann", answers=["0"])
        self.assertNotIn("Lampwrights' Deep", again)

    def test_with_the_receipt_he_asks_to_read_it(self):
        self.g.flags["lw_foreman_dead"] = True
        self.g.player.add_item("lw_receipt")
        out = run(self.g, "talk brann", answers=[self.menu_number(), "0"])
        self.assertIn("Nothing anyone need pay for. ...He'd have said the same.", out)
        self.assertTrue(self.g.player.has_item("lw_receipt"))    # he gives it back; it is a key item

    def test_the_scene_hands_the_receipt_back_and_names_the_workshop(self):
        self.g.flags["lw_foreman_dead"] = True
        self.g.player.add_item("lw_receipt")
        out = " ".join(run(self.g, "talk brann", answers=[self.menu_number(), "0"]).split())
        self.assertIn("Corm's workshop", out)                # the player says the name before Brann repeats it
        self.assertLess(out.index("you give him the receipt"), out.index("gives it back"))
        self.assertLess(out.index("gives it back"), out.index("picks the hammer up again"))

    def test_without_the_receipt_he_does_not(self):
        self.g.flags["lw_foreman_dead"] = True
        out = run(self.g, "talk brann", answers=[self.menu_number(), "0"])
        self.assertNotIn("Nothing anyone need pay for", out)
        self.assertTrue(self.g.flags["lw_brann_told"])


class WalkAndSaveTests(unittest.TestCase):
    def test_every_room_is_reachable_by_walking(self):
        g = new_game()
        g.flags["lw_foreman_dead"] = True
        wear(g, "hauberk", "relic_lamp", "armor")
        at(g, "crypt_stair")
        for cmd in ("s", "e", "e", "s", "n", "w", "s", "w"):
            run(g, cmd)
        for rid in LW_ROOMS:
            self.assertIn(rid, g.visited)
        self.assertEqual(g.room_id, "lw_gallery")

    def test_a_pre_package_save_finds_the_receipt_and_notes(self):
        g = new_game()
        save = g.to_dict()
        for rid in [r for r in save["room_items"] if r.startswith("lw_")]:
            del save["room_items"][rid]
        h = Game.from_dict(copy.deepcopy(save))
        self.assertIn("lw_receipt", h.room_items["lw_rack_room"])
        self.assertIn("lw_quench_notes", h.room_items["lw_rack_room"])
        self.assertEqual(h.room_items["lw_gallery"].count("lw_lamp_blank"), 2)

    def test_the_mess_is_a_waypost_with_its_own_wake_text(self):
        g = new_game()
        at(g, "lw_mess")
        g.last_rest = "lw_mess"
        g.player.gold = 100
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            g.death()
        text = " ".join(out.getvalue().split())
        self.assertIn("lighter by 50 gold", text)
        self.assertIn("tin cup of cold tea", text)
        self.assertEqual(g.room_id, "lw_mess")
        self.assertTrue(ROOMS["lw_mess"]["waypost"])


class ObjectiveTests(unittest.TestCase):
    def side(self, g):
        return [o for o in navigation.objectives(g) if o["room"] in ("crypt_stair", "lw_workshop") and o["side"]]

    def test_the_door_is_pointed_out_once_the_mine_is_known_and_until_the_mess_is_seen(self):
        g = new_game()
        self.assertEqual(self.side(g), [])
        g.visited.add("mine_hall")
        (obj,) = self.side(g)
        self.assertEqual(obj["room"], "crypt_stair")
        self.assertIn("Lamp Relic", obj["text"])
        g.visited.add("lw_mess")
        self.assertNotEqual([o["room"] for o in self.side(g)], ["crypt_stair"])

    def test_the_door_objective_goes_once_the_door_is_open(self):
        g = new_game()
        g.visited.update({"mine_hall", "crypt_stair", "lw_door"})
        self.assertEqual([o["room"] for o in self.side(g)], ["crypt_stair"])
        g.flags["lw_door_open"] = True
        self.assertEqual(self.side(g), [])

    def test_the_workshop_objective_lasts_until_the_foreman_is_dead(self):
        g = new_game()
        g.visited.update({"mine_hall", "lw_mess"})
        (obj,) = self.side(g)
        self.assertEqual(obj["room"], "lw_workshop")
        self.assertIn("rack-room key", obj["text"])
        g.flags["lw_foreman_dead"] = True
        self.assertEqual(self.side(g), [])

    def test_these_are_side_objectives_only(self):
        g = new_game()
        g.visited.update({"mine_hall"})
        ours = [o for o in navigation.objectives(g) if o["room"] in ("crypt_stair", "lw_workshop")]
        self.assertTrue(ours and all(o["side"] for o in ours))


class ContentTests(unittest.TestCase):
    def test_validator_and_area_checks_are_clean_for_this_package(self):
        errs = validate.validate()
        mine = [e for e in errs if "lw_" in e or REGION in e or "Lampwright" in e]
        self.assertEqual(mine, [])
        self.assertEqual([e for e in areas.check() if e.startswith("lw:")], [])

    def test_six_rooms_one_region(self):
        self.assertEqual(sorted(r for r in ROOMS if r.startswith("lw_")), sorted(LW_ROOMS))
        for rid in LW_ROOMS:
            self.assertEqual(ROOMS[rid]["region"], REGION)
        info = REGION_INFO[REGION]
        self.assertEqual((info["ring"], info["levels"], info["gear"]), (3, "7-8", "Rare"))
        self.assertIs(info["dealer"], False)

    def test_no_dealer_sits_in_the_workshops(self):
        self.assertFalse([r for r in dealer.seats(3) if r.startswith("lw_")])

    def test_every_room_has_a_desc_and_features(self):
        for rid in LW_ROOMS:
            self.assertTrue(len(ROOMS[rid]["desc"]) > 60, rid)
            self.assertTrue(ROOMS[rid]["features"], rid)

    def test_the_graph_matches_the_spec(self):
        want = {"lw_door": {"n": "crypt_stair", "e": "lw_mess", "s": "lw_gallery"},
                "lw_mess": {"w": "lw_door", "e": "lw_workshop", "s": "lw_glassworks"},
                "lw_workshop": {"w": "lw_mess", "s": "lw_rack_room"},
                "lw_gallery": {"n": "lw_door", "e": "lw_glassworks"},
                "lw_glassworks": {"n": "lw_mess", "w": "lw_gallery"},
                "lw_rack_room": {"n": "lw_workshop"}}
        for rid, exits in want.items():
            self.assertEqual(ROOMS[rid]["exits"], exits, rid)
        for rid, pos in {"lw_door": (0, 0), "lw_mess": (1, 0), "lw_workshop": (2, 0), "lw_gallery": (0, 1),
                         "lw_glassworks": (1, 1), "lw_rack_room": (2, 1)}.items():
            self.assertEqual(ROOMS[rid]["pos"], pos, rid)

    def test_encounter_groups_are_at_most_two_and_use_real_enemies(self):
        for rid in LW_ROOMS:
            for group, weight in ROOMS[rid].get("enc", {}).get("groups", []):
                self.assertLessEqual(len(group), 2, rid)
                for eid in group:
                    self.assertIn(eid, ENEMIES, rid)
        self.assertNotIn("enc", ROOMS["lw_mess"])
        self.assertNotIn("enc", ROOMS["lw_rack_room"])

    def test_no_hollow_here_is_weak_to_light(self):
        for eid in LW_ENEMIES:
            e = ENEMIES[eid]
            if "hollow" in e["tags"]:
                self.assertNotIn("light", e["weak"], eid)

    def test_every_heavy_and_charge_move_has_a_tell_and_every_enemy_a_desc(self):
        for eid in LW_ENEMIES:
            e = ENEMIES[eid]
            self.assertTrue(e["desc"], eid)
            moves = list(e["moves"]) + list(e.get("extra_moves", {}).values())
            for ph in e.get("phases", []):
                moves += ph["moves"]
            for m in moves:
                if m["kind"] in ("heavy", "charge"):
                    self.assertTrue(m.get("tell"), (eid, m["name"]))

    def test_ordinary_enemy_stats(self):
        g, l = ENEMIES["lw_glass_ghoul"], ENEMIES["lw_lampling"]
        self.assertEqual((g["hp"], g["atk"], g["def"], g.get("dodge", 0), g["xp"]), (78, 17, 9, 0, 46))
        self.assertEqual((l["hp"], l["atk"], l["def"], l["dodge"], l["xp"]), (60, 18, 5, 18, 42))
        self.assertEqual(g["weak"], ["ice", "earth"])
        self.assertEqual(l["weak"], ["water", "earth"])
        self.assertEqual(l["resist"], ["fire", "light"])
        self.assertEqual(g["tags"], ["hollow", "undead"])
        self.assertEqual(l["tags"], ["construct"])
        drain = next(m for m in l["moves"] if m["name"] == "Gutter")
        self.assertEqual((drain["kind"], drain["drain"]), ("drain", 8))
        flare = next(m for m in l["moves"] if m["name"] == "Flare Up")
        self.assertEqual((flare["kind"], flare["power"], flare["status"]), ("heavy", 1.8, ["burn", 3, 5]))

    def test_the_foreman_drops_what_the_forge_wants(self):
        drops = [d for d, chance in ENEMIES["lw_foreman"]["drops"] if chance == 1.0]
        self.assertEqual(drops.count("slag"), 3)
        self.assertEqual(drops.count("hollow_core"), 1)
        self.assertEqual(drops.count("essence_earth"), 2)

    def test_items(self):
        self.assertEqual(sorted(i for i in ITEMS if i.startswith("lw_")), sorted(LW_ITEMS))
        self.assertEqual(ITEMS["lw_lampwright_hammer"]["stats"], {"atk": 11, "str": 2})
        self.assertEqual(ITEMS["lw_apron"]["stats"], {"def": 8, "hp": 8})
        self.assertEqual(ITEMS["lw_pit_lamp"]["stats"], {"wil": 2, "oil_save": 2})
        self.assertEqual(ITEMS["lw_pit_lamp"]["mult"], {"fire": 1.1})
        self.assertEqual([ITEMS[i]["kind"] for i in ("lw_lampwright_hammer", "lw_apron", "lw_pit_lamp", "lw_lamp_blank")],
                         ["weapon", "armor", "trinket", "junk"])
        self.assertTrue(ITEMS["lw_lamp_blank"]["stack"])
        for iid in LW_ITEMS:
            self.assertEqual(ITEMS[iid]["rarity"], "rare" if ITEMS[iid]["kind"] in ("weapon", "armor", "trinket")
                             else "common", iid)

    def test_the_receipt_and_notes_are_the_final_copy(self):
        r = ITEMS["lw_receipt"]
        self.assertEqual(r["name"], "Receipt: the Lampwrights' Deep")
        self.assertTrue(r["desc"].startswith("Received of the Lampwrights, Corm's pit-lamp"))
        self.assertIn("nothing anyone need pay for", r["desc"])
        self.assertTrue(r["desc"].endswith("Held in trust. -A."))
        n = ITEMS["lw_quench_notes"]
        self.assertEqual(n["name"], "Corm's Notes on the Quench")
        self.assertTrue(n["desc"].startswith("Two quenches I know"))
        self.assertTrue(n["desc"].endswith("They all take the edge off. -Corm."))

    def test_every_lock_message_names_what_it_needs(self):
        self.assertIn("Lamp Relic", DOOR["msg"])
        self.assertIn("Tallow sells Lamp Relics", DOOR["msg"])
        self.assertIn("Last Foreman in the workshop", ROOMS["lw_workshop"]["locks"]["s"]["msg"])

    def test_the_tone_rules_hold_for_our_text(self):
        texts = []
        for rid in LW_ROOMS:
            r = ROOMS[rid]
            texts += [r["desc"], r.get("wake", "")] + list(r["features"].values())
        texts += [ITEMS[i]["desc"] for i in LW_ITEMS] + [ENEMIES[e]["desc"] for e in LW_ENEMIES]
        for t in texts:
            self.assertTrue(t.isascii(), t[:40])
            self.assertNotIn("’", t)
        wake = ROOMS["lw_mess"]["wake"]
        self.assertEqual(wake.count("%d"), 1)
        self.assertEqual(wake.replace("%d", "").count("%"), 0)


if __name__ == "__main__":
    unittest.main()
