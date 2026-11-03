"""The Darkness Dealers: where they sit, what they sell, what it costs, and that nothing is ever Godlike."""
import contextlib
import copy
import io
import json
import re
import unittest
from unittest import mock

from lamplighter import clock, dealer, gear, npcs, ui, validate
from lamplighter.content import AFFIXES, DEALER, ITEMS, REGION_INFO, ROOMS
from lamplighter.engine import Game
from tests.helpers import new_game, run, temp_home

DAY0 = 20000
RINGS = (1, 2, 3, 4)
RING_REGION = {}
for _rid, _i in REGION_INFO.items():      # the first region of each ring is its base region (extensions come later)
    RING_REGION.setdefault(_i["ring"], _rid)


def region_rooms(ring):
    return [rid for rid, r in ROOMS.items() if r["region"] == RING_REGION[ring]]


class DealerCase(unittest.TestCase):
    def setUp(self):
        self.day = [DAY0]
        clock.set_clock(lambda: self.day[0] * 86400.0 + 3600)

    def tearDown(self):
        clock.set_clock(None)

    def game(self, gems=200, ring=None, salt=0):
        g = new_game()
        g.flags["completed"] = True
        g.player.gems = gems
        g.dealers["salt"] = salt
        if ring:
            g.room_id = dealer.room_for(g, ring)
            self.assertIsNotNone(g.room_id)
        return g

    def seat_all(self, g, ring):
        g.room_id = dealer.room_for(g, ring)
        return g.room_id


class WhereTests(DealerCase):
    def test_there_is_one_dealer_per_ring_each_day_and_none_in_hollowmere(self):
        g = self.game()
        for d in range(DAY0, DAY0 + 30):
            self.day[0] = d
            for ring in RINGS:
                here = []
                for rid in region_rooms(ring):
                    g.room_id = rid
                    if "dealer" in g.present_npcs():
                        here.append(rid)
                self.assertEqual(here, [dealer.room_for(g, ring)], (d, ring))
            for rid in region_rooms(0):
                g.room_id = rid
                self.assertNotIn("dealer", g.present_npcs(), rid)
                self.assertIsNone(dealer.where(g))

    def test_a_dealer_sits_only_in_ordinary_dark_rooms(self):
        g = self.game()
        for ring in RINGS:
            for rid in dealer.seats(ring):
                r = ROOMS[rid]
                self.assertTrue(r["dark"])
                for k in ("boss", "rest", "fixed", "waypost", "outpost", "beacon"):
                    self.assertFalse(r.get(k), (rid, k))
        for d in range(DAY0, DAY0 + 200):
            for ring in RINGS:
                rid = dealer.room_for(g, ring, d)
                self.assertIn(rid, dealer.seats(ring))
                self.assertTrue(g.is_dark(rid))

    def test_boss_rest_waypost_fixed_and_town_rooms_are_never_seats(self):
        g = self.game()
        banned = [rid for rid, r in ROOMS.items() if any(r.get(k) for k in ("boss", "rest", "fixed", "waypost"))]
        self.assertGreaterEqual(len(banned), 15)
        used = {dealer.room_for(g, ring, d) for d in range(DAY0, DAY0 + 300) for ring in RINGS}
        self.assertFalse(used & set(banned))
        self.assertFalse(used & set(region_rooms(0)))

    def test_he_stays_in_one_room_all_day_and_every_look_agrees(self):
        g = self.game()
        for ring in RINGS:
            first = dealer.room_for(g, ring)
            for hour in range(0, 24, 5):
                clock.set_clock(lambda h=hour: DAY0 * 86400.0 + h * 3600)
                self.assertEqual(dealer.room_for(g, ring), first)
                g.room_id = first
                self.assertEqual(dealer.where(g), first)
                self.assertIn("dealer", g.present_npcs())

    def test_he_is_somewhere_else_on_other_days_and_the_salt_moves_him_too(self):
        g = self.game()
        for ring in RINGS:
            rooms = {dealer.room_for(g, ring, d) for d in range(DAY0, DAY0 + 40)}
            self.assertGreater(len(rooms), 1, ring)
            salted = [dealer.room_for(self.game(salt=s), ring) for s in range(12)]
            self.assertGreater(len(set(salted)), 1, ring)

    def test_a_lit_room_moves_him_on_and_a_lit_region_sends_him_away(self):
        g = self.game()
        for ring in RINGS:
            seen = []
            while True:
                rid = dealer.room_for(g, ring)
                if rid is None:
                    break
                seen.append(rid)
                self.assertNotIn(rid, seen[:-1])
                g.flags["lit_" + rid] = True
            self.assertEqual(sorted(seen), sorted(dealer.seats(ring)))
            g.room_id = seen[0]
            self.assertIsNone(dealer.where(g))
            self.assertNotIn("dealer", g.present_npcs())

    def test_lighting_some_other_room_does_not_move_him(self):
        g = self.game()
        for ring in RINGS:
            rid = dealer.room_for(g, ring)
            other = next(x for x in dealer.seats(ring) if x != rid)
            g.flags["lit_" + other] = True
            # he only moves if that room was ahead of him in today's order; otherwise he stays put
            order = list(dealer.seats(ring))
            import random
            random.Random("dealer-room:%d:%d:%d" % (DAY0, 0, ring)).shuffle(order)
            if order.index(other) > order.index(rid):
                self.assertEqual(dealer.room_for(g, ring), rid)
            g.flags.pop("lit_" + other)

    def test_a_beacon_lit_ring_has_no_dealer(self):
        g = self.game()
        for rid in region_rooms(4):
            g.flags["lit_" + rid] = True
        self.assertIsNone(dealer.room_for(g, 4))
        for rid in region_rooms(4):
            g.room_id = rid
            self.assertNotIn("dealer", g.present_npcs())
        self.assertIsNotNone(dealer.room_for(g, 1))

    def test_standing_in_the_room_you_see_him_and_he_has_news(self):
        g = self.game(ring=2)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.render_room()
        self.assertIn("Here: The Darkness Dealer", buf.getvalue())
        self.assertIn("Talk to The Darkness Dealer", buf.getvalue())
        self.assertTrue(npcs.has_news(g, "dealer"))
        run(g, "talk dealer", answers=["0"])
        self.assertFalse(npcs.has_news(g, "dealer"))

    def test_hints_and_travel_do_not_give_his_location_away(self):
        g = self.game()
        seat = dealer.room_for(g, 4)
        g.room_id = "court_gate"
        for cmd in ("hint", "map", "travel"):
            out = run(g, cmd, answers=["0", "", "0"])
            self.assertNotIn("Dealer", out, cmd)
            self.assertNotIn(ROOMS[seat]["name"] + " (", out)

    def test_it_never_raises_anywhere(self):
        g = self.game()
        for rid in ROOMS:
            g.room_id = rid
            g.present_npcs()
            dealer.where(g)


class WaresTests(DealerCase):
    def test_four_wares_two_fair_a_bargain_and_a_relic(self):
        g = self.game(ring=4)
        a, b = dealer.wares(g), dealer.wares(g)
        self.assertEqual(a, b)
        kinds = [(w["kind"], bool(w["curse"])) for _, w in a]
        self.assertEqual(kinds, [("gear", False), ("gear", False), ("gear", True), ("relic", False)])
        self.assertEqual([w["id"] for _, w in a], ["%d:4:0:%d" % (DAY0, i) for i in range(4)])
        self.assertEqual(len({w["base"] for _, w in a[:3]}), 3)

    def test_rarity_follows_the_ring(self):
        g = self.game()
        seen = {r: set() for r in RINGS}
        for d in range(DAY0, DAY0 + 120):
            for ring in RINGS:
                for w in dealer._wares(g, ring, d, 0)[:2]:
                    seen[ring].add(w["rarity"])
        self.assertEqual(seen[1], {"rare", "epic"})
        self.assertEqual(seen[2], {"epic", "ultra"})
        self.assertEqual(seen[3], {"epic", "ultra"})
        self.assertEqual(seen[4], {"epic", "ultra", "legendary"})

    def test_gems_never_buy_godlike_across_many_days_salts_rings_and_restocks(self):
        g = self.game()
        n = 0
        for salt in (0, 1, 7, 99):
            g.dealers["salt"] = salt
            for d in range(DAY0, DAY0 + 150):
                for ring in RINGS:
                    for cloth in range(DEALER["restock"]["max"] + 1):
                        for w in dealer._wares(g, ring, d, cloth):
                            n += 1
                            self.assertNotEqual(w["rarity"], "godlike", w)
                            self.assertLessEqual(gear.RARITY_ORDER.index(w["rarity"]), gear.RARITY_ORDER.index("legendary"))
                            for r in w["relics"]:
                                self.assertNotEqual(r["rarity"], "godlike", w)
                                self.assertLessEqual(gear.RARITY_ORDER.index(r["rarity"]), gear.RARITY_ORDER.index("legendary"))
        self.assertGreater(n, 10000)

    def test_a_bought_item_is_never_godlike_either(self):
        g = self.game(gems=100000)
        for d in range(DAY0, DAY0 + 40):
            self.day[0] = d
            g.room_id = dealer.room_for(g, 4)
            for _, w in dealer.wares(g):
                state, inst = dealer.buy(g, 4, w["id"])
                self.assertEqual(state, "ok")
                self.assertNotEqual(inst["rarity"], "godlike")
                for r in inst.get("relics", []):
                    self.assertNotEqual(r["rarity"], "godlike")

    def test_the_old_prototype_bug_a_legendary_bargain_does_not_go_up_to_godlike(self):
        g = self.game()
        found = 0
        for d in range(DAY0, DAY0 + 400):
            w = dealer._wares(g, 4, d, 0)[2]
            if w["rarity"] == "legendary":
                found += 1
        self.assertGreater(found, 10)

    def test_the_curse_is_only_on_the_bargain_and_is_the_only_one(self):
        g = self.game()
        for d in range(DAY0, DAY0 + 60):
            for ring in RINGS:
                for w in dealer._wares(g, ring, d, 0):
                    inst = dealer.sketch(w)
                    cursed = [a for a in inst.get("affixes", []) if AFFIXES[a].get("curse")]
                    if w["slot"] == 2:
                        self.assertEqual(cursed, [w["curse"]])
                        self.assertIn(inst["kind"], AFFIXES[w["curse"]]["slots"])
                    else:
                        self.assertIsNone(w["curse"])
                        self.assertEqual(cursed, [])

    def test_sockets_come_with_relics_already_in_them(self):
        g = self.game()
        for d in range(DAY0, DAY0 + 40):
            for ring in RINGS:
                for w in dealer._wares(g, ring, d, 0):
                    if w["kind"] == "relic":
                        self.assertEqual(w["relics"], [])
                        self.assertEqual(ITEMS[w["base"]]["kind"], "relic")
                        continue
                    inst = dealer.sketch(w)
                    sockets = gear.SOCKETS[w["rarity"]]
                    self.assertEqual(inst["sockets"], sockets)
                    want = min(sockets, DEALER["bargain"]["relics"] if w["curse"] else DEALER["fair_relics"])
                    self.assertEqual(len(inst["relics"]), want)
                    self.assertGreaterEqual(want, 1)
                    for r in inst["relics"]:
                        self.assertEqual(ITEMS[r["base"]]["kind"], "relic")
                    self.assertIn("Sockets %d/%d" % (want, sockets), inst["desc"])

    def test_relics_in_gear_actually_add_their_multiplier(self):
        g = self.game()
        w = dealer._wares(g, 4, DAY0, 0)[0]
        bare = gear.make(w["base"], w["rarity"], __import__("random").Random(w["seed"]))
        ITEMS.pop(bare["id"])
        full = dealer.sketch(w)
        self.assertNotEqual(bare["mult"], full["mult"])

    def test_the_bargain_is_30_percent_off_the_gear_only_and_prices_climb_with_rarity(self):
        p = DEALER["price"]
        self.assertLess(p["rare"], p["epic"])
        self.assertLess(p["epic"], p["ultra"])
        self.assertLess(p["ultra"], p["legendary"])
        w = {"kind": "gear", "rarity": "legendary", "relics": [], "curse": None}
        full = dealer.price_of(w)
        w["curse"] = "gaunt"
        self.assertEqual(dealer.price_of(w), int(full * 0.7 + 0.5))
        # the discount is on the gear: a relic in a socket is not marked down
        w["relics"] = [{"base": "relic_ember", "rarity": "legendary"}] * 2
        self.assertEqual(dealer.price_of(w), 20 + 2 * 16)
        self.assertGreaterEqual(dealer.price_of(dict(w, rarity="rare", relics=[])), 1)

    def test_everything_is_shown_before_you_pay(self):
        g = self.game(ring=4)
        for _, w in dealer.wares(g):
            head, stats = dealer.preview(w)
            lines = dealer.detail_lines(w)
            self.assertIn(w["rarity"].title(), head.replace("{", " ").replace("}", " "))
            if w["kind"] == "gear":
                self.assertTrue(any(l.startswith("Sockets") for l in lines))
                self.assertEqual(sum(l.startswith("Socketed:") for l in lines), len(w["relics"]))
            if w["curse"]:
                self.assertIn("CURSED", head)
                curse_line = next(l for l in lines if "Curse" in l)
                self.assertIn(AFFIXES[w["curse"]]["name"].title(), curse_line)
                self.assertIn("-", curse_line)
        out = run(g, "talk dealer", answers=["0"])
        for _, w in dealer.wares(g):
            self.assertIn("%d gems" % w["price"], out)
        self.assertIn("Curse", out)
        self.assertIn("Socketed:", out)

    def test_the_curse_numbers_shown_match_the_difference_it_makes(self):
        g = self.game()
        w = dealer._wares(g, 4, DAY0, 0)[2]
        inst = dealer.sketch(w)
        clean = dict(inst, affixes=[a for a in inst["affixes"] if a != w["curse"]])
        gear.rebuild(clean)
        key = next(iter(AFFIXES[w["curse"]]["stats"]))
        diff = inst["stats"].get(key, 0) - clean["stats"].get(key, 0)
        self.assertLess(diff, 0)
        self.assertIn("%s %+d" % (key.upper(), diff), dealer.curse_text(inst, w["curse"]))


class PreviewTests(DealerCase):
    def strip(self, inst):
        return {k: v for k, v in inst.items() if k != "id"}

    def test_the_preview_is_exactly_what_you_get(self):
        g = self.game(gems=100000)
        for d in range(DAY0, DAY0 + 30):
            self.day[0] = d
            g.room_id = dealer.room_for(g, 3)
            for _, w in dealer.wares(g):
                shown = self.strip(copy.deepcopy(dealer.sketch(w)))
                again = self.strip(copy.deepcopy(dealer.sketch(w)))
                state, got = dealer.buy(g, 3, w["id"])
                self.assertEqual(state, "ok")
                self.assertEqual(shown, again)
                self.assertEqual(shown, self.strip(got), w)
                self.assertEqual(dealer.preview(w)[1], dealer.preview(w)[1])

    def test_previewing_leaves_nothing_behind(self):
        g = self.game(ring=4)
        items, counter = set(ITEMS), gear._counter[0]
        for _ in range(3):
            for _, w in dealer.wares(g):
                dealer.preview(w)
                dealer.detail_lines(w)
        run(g, "talk dealer", answers=["0"])
        self.assertEqual(set(ITEMS), items)
        self.assertEqual(gear._counter[0], counter)

    def test_a_purchase_gets_a_fresh_unique_id(self):
        g = self.game(ring=4, gems=1000)
        ids = []
        for _, w in dealer.wares(g):
            dealer.preview(w)
            state, inst = dealer.buy(g, 4, w["id"])
            ids.append(inst["id"])
            self.assertIn(inst["id"], ITEMS)
            self.assertIn(inst["id"], g.player.inventory)
        self.assertEqual(len(set(ids)), 4)


class BuyingTests(DealerCase):
    def test_buying_takes_exactly_the_price(self):
        g = self.game(ring=1, gems=50)
        _, w = dealer.wares(g)[0]
        state, inst = dealer.buy(g, 1, w["id"])
        self.assertEqual((state, g.player.gems), ("ok", 50 - w["price"]))
        self.assertEqual(g.dealers["bought"][str(DAY0)], [w["id"]])
        self.assertEqual(len(dealer.wares(g)), 3)

    def test_not_enough_gems_changes_nothing(self):
        g = self.game(ring=4, gems=3)
        _, w = dealer.wares(g)[0]
        before = copy.deepcopy(g.dealers)
        self.assertEqual(dealer.buy(g, 4, w["id"]), ("poor", w["price"]))
        self.assertEqual(g.player.gems, 3)
        self.assertEqual(g.dealers, before)
        self.assertFalse([i for i in g.player.inventory if gear.is_instance(i)])

    def test_exactly_enough_gems_works_and_leaves_zero(self):
        g = self.game(ring=1)
        _, w = dealer.wares(g)[0]
        g.player.gems = w["price"]
        self.assertEqual(dealer.buy(g, 1, w["id"])[0], "ok")
        self.assertEqual(g.player.gems, 0)

    def test_a_ware_cannot_be_bought_twice(self):
        g = self.game(ring=4)
        _, w = dealer.wares(g)[0]
        dealer.buy(g, 4, w["id"])
        gems = g.player.gems
        self.assertEqual(dealer.buy(g, 4, w["id"]), ("gone", None))
        self.assertEqual(g.player.gems, gems)

    def test_backing_out_costs_nothing(self):
        g = self.game(ring=4, gems=50)
        run(g, "talk dealer", answers=["1", "n", "0"])
        self.assertEqual(g.player.gems, 50)
        self.assertEqual(g.dealers["bought"], {})
        run(g, "talk dealer", answers=["0"])
        self.assertEqual(g.player.gems, 50)

    def test_buying_everything_then_the_table_is_empty_but_you_can_still_turn_the_cloth(self):
        g = self.game(ring=4, gems=500)
        total = sum(w["price"] for _, w in dealer.wares(g))
        run(g, "talk dealer", answers=["1", "y", "", "1", "y", "", "1", "y", "", "1", "y", "", "0"])
        self.assertEqual(g.player.gems, 500 - total)
        self.assertEqual(dealer.wares(g), [])
        out = run(g, "talk dealer", answers=["0"])
        self.assertIn("Nothing left on the cloth", out)
        self.assertIn("Turn the cloth", out)
        run(g, "talk dealer", answers=["1", "y", "", "0"])
        self.assertEqual(len(dealer.wares(g)), 4)

    def test_there_is_no_pack_limit_so_a_big_pack_still_takes_the_purchase(self):
        g = self.game(ring=4, gems=500)
        for i in range(200):
            g.player.inventory["junk%d" % i] = 1
        _, w = dealer.wares(g)[3]
        state, inst = dealer.buy(g, 4, w["id"])
        self.assertEqual(state, "ok")
        self.assertEqual(g.player.inventory[inst["id"]], 1)

    def test_a_relic_can_be_bought_and_is_a_pack_relic(self):
        from lamplighter import forge
        g = self.game(ring=4, gems=500)
        _, w = dealer.wares(g)[3]
        state, inst = dealer.buy(g, 4, w["id"])
        self.assertIn(inst["id"], forge.relics_in_pack(g))

    def test_walking_in_the_wrong_ring_sells_nothing(self):
        g = self.game(ring=4)
        g.room_id = "hall"
        self.assertEqual(dealer.wares(g), [])
        self.assertEqual(dealer.buy(g, 0, "0:0:0"), ("gone", None))


class RestockTests(DealerCase):
    def test_prices_climb_and_it_stops_at_three(self):
        g = self.game(ring=4, gems=100)
        paid = []
        for n in range(3):
            self.assertEqual(dealer.restock_price(g), DEALER["restock"]["prices"][n])
            before = g.player.gems
            state, price = dealer.restock(g)
            self.assertEqual(state, "ok")
            paid.append(before - g.player.gems)
            self.assertEqual(g.dealers["restocks"][str(DAY0)], n + 1)
        self.assertEqual(paid, [3, 6, 12])
        self.assertEqual(dealer.restock(g), ("max", None))
        self.assertIsNone(dealer.restock_price(g))
        self.assertEqual(g.player.gems, 100 - 21)
        self.assertEqual(dealer.restocks_left(g), 0)

    def test_not_enough_gems_to_restock(self):
        g = self.game(ring=4, gems=2)
        self.assertEqual(dealer.restock(g), ("poor", 3))
        self.assertEqual((g.player.gems, g.dealers["restocks"]), (2, {}))

    def test_a_restock_brings_new_wares_in_the_same_room_with_the_same_dealer(self):
        g = self.game(ring=4)
        room = g.room_id
        different = 0
        for n in range(3):
            old = [w["id"] for _, w in dealer.wares(g)]
            seeds = [w["seed"] for _, w in dealer.wares(g)]
            dealer.restock(g)
            new = dealer.wares(g)
            self.assertEqual(dealer.room_for(g, 4), room)
            self.assertEqual(len(new), 4)
            self.assertTrue(set(old).isdisjoint(w["id"] for _, w in new))
            different += seeds != [w["seed"] for _, w in new]
            self.assertEqual(new, dealer.wares(g))
        self.assertEqual(different, 3)

    def test_wares_already_bought_stay_bought_and_the_new_cloth_is_fresh(self):
        g = self.game(ring=4)
        _, w = dealer.wares(g)[0]
        dealer.buy(g, 4, w["id"])
        dealer.restock(g)
        self.assertEqual(len(dealer.wares(g)), 4)
        self.assertEqual(g.dealers["bought"][str(DAY0)], [w["id"]])
        _, w2 = dealer.wares(g)[0]
        self.assertNotEqual(w["id"], w2["id"])
        dealer.buy(g, 4, w2["id"])
        self.assertEqual(len(dealer.wares(g)), 3)
        self.assertEqual(len(g.dealers["bought"][str(DAY0)]), 2)

    def test_tomorrow_starts_with_a_full_cloth_and_no_restocks(self):
        g = self.game(ring=4, gems=100)
        dealer.restock(g)
        _, w = dealer.wares(g)[0]
        dealer.buy(g, 4, w["id"])
        self.day[0] += 1
        g.room_id = dealer.room_for(g, 4)
        self.assertEqual(len(dealer.wares(g)), 4)
        self.assertEqual(dealer.restock_price(g), 3)
        self.assertEqual(dealer.restocks_left(g), 3)
        dealer.restock(g)
        self.assertEqual(list(g.dealers["restocks"]), [str(DAY0 + 1)])
        self.assertEqual(list(g.dealers["bought"]), [])

    def test_state_lives_only_in_game_dealers(self):
        g = self.game(ring=4, gems=100)
        run(g, "talk dealer", answers=["1", "y", "", "0"])
        dealer.restock(g)
        self.assertEqual({k for k in g.flags if "dealer" in k}, {"dealer_met", "talked_dealer"})
        self.assertEqual(set(g.dealers), {"salt", "bought", "restocks"})

    def test_the_restock_menu_flow(self):
        g = self.game(ring=4, gems=100)
        before = [w["id"] for _, w in dealer.wares(g)]
        out = run(g, "talk dealer", answers=["5", "y", "", "0"])
        self.assertEqual(g.player.gems, 97)
        self.assertNotEqual(before, [w["id"] for _, w in dealer.wares(g)])
        self.assertIn("something else on it", out)
        out = run(g, "talk dealer", answers=["5", "n", "0"])
        self.assertEqual(g.player.gems, 97)
        self.assertIn("turn 2 of 3", out)

    def test_after_the_last_restock_the_menu_says_so(self):
        g = self.game(ring=4, gems=100)
        for _ in range(3):
            dealer.restock(g)
        out = run(g, "talk dealer", answers=["0"])
        self.assertIn("will not be turned again", out)
        self.assertNotIn("Turn the cloth for", out)


class SaveTests(DealerCase):
    def test_a_save_in_the_middle_of_a_day_comes_back_the_same(self):
        with temp_home():
            g = self.game(ring=4, gems=100)
            _, w = dealer.wares(g)[1]
            dealer.buy(g, 4, w["id"])
            dealer.restock(g)
            _, w2 = dealer.wares(g)[2]
            dealer.buy(g, 4, w2["id"])
            before = dealer.wares(g)
            gems = g.player.gems
            g.save(quiet=True)
            g2 = Game.load()
            self.assertEqual(g2.player.gems, gems)
            self.assertEqual(g2.dealers, g.dealers)
            g2.room_id = dealer.room_for(g2, 4)
            self.assertEqual(g2.room_id, g.room_id)
            self.assertEqual(dealer.wares(g2), before)
            self.assertEqual(dealer.restock_price(g2), 6)
            for iid in (i for i in g2.player.inventory if gear.is_instance(i)):
                self.assertIn(iid, ITEMS)
            self.assertEqual(sum(gear.is_instance(i) for i in g2.player.inventory), 2)
            json.dumps(g2.dealers)

    def test_new_gear_after_loading_does_not_reuse_an_id(self):
        with temp_home():
            g = self.game(ring=4, gems=500)
            for _, w in dealer.wares(g):
                dealer.buy(g, 4, w["id"])
            top = gear._counter[0]
            g.save(quiet=True)
            gear._counter[0] = 0
            g2 = Game.load()
            self.assertEqual(gear._counter[0], top)
            g2.room_id = dealer.room_for(g2, 4)
            dealer.restock(g2)
            _, w = dealer.wares(g2)[0]
            state, inst = dealer.buy(g2, 4, w["id"])
            self.assertEqual(state, "ok")
            self.assertEqual(sum(1 for i in g2.player.gear if i == inst["id"]), 1)

    def test_a_damaged_dealers_block_does_not_crash(self):
        g = self.game(ring=4)
        for bad in ({}, {"salt": "x", "bought": [], "restocks": 5}, {"salt": True, "bought": {str(DAY0): "no"},
                                                                       "restocks": {str(DAY0): "many"}}):
            g.dealers = copy.deepcopy(bad)
            self.assertIsNotNone(dealer.room_for(g, 4))
            self.assertEqual(len(dealer.wares(g)), 4)
            dealer.restock_price(g)
            run(g, "talk dealer", answers=["0"])

    def test_an_old_prototype_save_keeps_working(self):
        from lamplighter import save
        d = save._migrate_1_to_2({"flags": {"dealer_bought": {str(DAY0): [0, 1]}, "dealer_salt": 3}})
        g = self.game(ring=4)
        g.dealers = d["dealers"]
        self.assertEqual(g.dealers["salt"], 3)
        self.assertEqual(len(dealer.wares(g, 4)), 4)    # the old plain indexes mean nothing to the new cloth


class SeatTests(DealerCase):
    """Where he can sit, and when you can see him."""

    def test_a_room_you_can_only_enter_through_a_locked_door_is_never_a_seat(self):
        self.assertIn("cellars", region_rooms(4))
        self.assertNotIn("cellars", dealer.seats(4))
        for ring in RINGS:
            for rid in dealer.seats(ring):
                ways = [(src, d) for src, r in ROOMS.items() for d, dest in r["exits"].items() if dest == rid]
                self.assertTrue(any(d not in ROOMS[src].get("locks", {}) for src, d in ways), rid)
        g = self.game()
        used = {dealer.room_for(g, 4, d) for d in range(DAY0, DAY0 + 300)}
        self.assertNotIn("cellars", used)
        self.assertGreaterEqual(len(used), 5)

    def test_every_ring_has_enough_seats_to_move_around(self):
        for ring in RINGS:
            self.assertGreaterEqual(len(dealer.seats(ring)), 2, ring)

    def test_with_a_dry_lantern_he_is_not_there_to_talk_to_either(self):
        g = self.game(ring=4)
        self.assertIn("dealer", g.present_npcs())
        g.player.oil = 0
        self.assertTrue(g.benighted())
        self.assertNotIn("dealer", g.present_npcs())
        self.assertIsNone(dealer.where(g))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.render_room()
        self.assertNotIn("Dealer", buf.getvalue())
        out = run(g, "talk dealer", "talk", "examine dealer")
        self.assertNotIn("The Dealer", out)
        self.assertNotIn("Pay", out)
        self.assertEqual(g.dealers["bought"], {})
        g.player.oil = 10
        self.assertIn("dealer", g.present_npcs())

    def test_the_first_meeting_says_a_beacon_ends_him(self):
        g = self.game(ring=4)
        out = run(g, "talk dealer", answers=["0"])
        self.assertIn("beacon", out)

    def test_a_ring_lit_by_its_beacon_has_no_dealer_ever_again(self):
        g = self.game()
        for rid in region_rooms(4):
            g.flags["lit_" + rid] = True
        for d in range(DAY0, DAY0 + 60):
            self.assertIsNone(dealer.room_for(g, 4, d))


class MidnightTests(DealerCase):
    """The menu stays open while the day can change under it. What was shown and paid for is what is taken."""

    def test_a_ware_id_names_one_day_one_ring_one_cloth_and_one_slot(self):
        g = self.game(ring=4)
        for _, w in dealer.wares(g):
            self.assertEqual(w["id"], "%d:4:0:%d" % (DAY0, w["slot"]))
        ids = set()
        for d in range(DAY0, DAY0 + 20):
            ids |= {w["id"] for w in dealer._wares(g, 4, d, 0)}
        self.assertEqual(len(ids), 80)

    def test_yesterdays_id_buys_nothing_after_midnight(self):
        g = self.game(ring=4, gems=500)
        _, shown = dealer.wares(g)[2]
        self.day[0] += 1
        self.assertEqual(dealer.buy(g, 4, shown["id"]), ("gone", None))
        self.assertEqual(g.player.gems, 500)
        self.assertEqual(g.dealers["bought"], {})
        self.assertFalse([i for i in g.player.inventory if gear.is_instance(i)])

    def test_midnight_between_choosing_and_paying_takes_nothing_and_gives_nothing(self):
        g = self.game(ring=4, gems=500)
        room = g.room_id
        before = set(ITEMS)

        def midnight(question):
            self.assertIn("Pay", question)
            self.day[0] += 1
            return True

        with mock.patch.object(dealer.ui, "confirm", side_effect=midnight):
            out = run(g, "talk dealer", answers=["3", "", "", "", "0"])
        self.assertEqual(g.player.gems, 500)
        self.assertEqual(g.dealers["bought"], {})
        self.assertFalse([i for i in g.player.inventory if gear.is_instance(i)])
        self.assertEqual(set(ITEMS), before)
        self.assertIn("The day turned over", out)
        self.assertEqual(g.room_id, room)

    def test_midnight_between_choosing_and_paying_to_turn_the_cloth_takes_nothing(self):
        g = self.game(ring=4, gems=100)

        def midnight(question):
            self.day[0] += 1
            return True

        with mock.patch.object(dealer.ui, "confirm", side_effect=midnight):
            out = run(g, "talk dealer", answers=["5", "", "", "", "0"])
        self.assertEqual(g.player.gems, 100)
        self.assertEqual(g.dealers["restocks"], {})
        self.assertIn("The day turned over", out)

    def test_restock_with_the_day_or_cloth_that_was_priced_refuses_when_they_changed(self):
        g = self.game(ring=4, gems=100)
        self.assertEqual(dealer.restock(g, DAY0, 1), ("stale", None))
        self.assertEqual(dealer.restock(g, DAY0 - 1, 0), ("stale", None))
        self.assertEqual(g.player.gems, 100)
        self.assertEqual(dealer.restock(g, DAY0, 0), ("ok", 3))

    def test_if_he_has_moved_by_the_time_the_menu_comes_round_again_it_closes(self):
        g = self.game(ring=4, gems=500)
        room = g.room_id
        later = next(d for d in range(DAY0 + 1, DAY0 + 60) if dealer.room_for(g, 4, d) != room)

        def midnight(question):
            self.day[0] = later
            return False

        with mock.patch.object(dealer.ui, "confirm", side_effect=midnight):
            out = run(g, "talk dealer", answers=["1", "", "0"])
        self.assertIn("gone from this room", out)
        self.assertEqual(g.player.gems, 500)

    def test_a_clock_that_steps_back_does_not_wipe_what_was_sold_or_turned(self):
        g = self.game(ring=4, gems=500)
        self.day[0] = DAY0 + 1
        g.room_id = dealer.room_for(g, 4)
        _, w = dealer.wares(g)[0]
        dealer.buy(g, 4, w["id"])
        for _ in range(3):
            dealer.restock(g)
        self.day[0] = DAY0
        g.room_id = dealer.room_for(g, 4)
        _, old = dealer.wares(g)[0]
        dealer.buy(g, 4, old["id"])
        dealer.restock(g)
        self.assertEqual(sorted(g.dealers["restocks"]), [str(DAY0), str(DAY0 + 1)])
        self.day[0] = DAY0 + 1
        self.assertEqual(dealer.restocks_left(g), 0)
        self.assertEqual(dealer.restock(g), ("max", None))
        self.assertIn(w["id"], g.dealers["bought"][str(DAY0 + 1)])

    def test_buying_drops_old_days_and_keeps_today_and_later(self):
        g = self.game(ring=4, gems=500)
        g.dealers["bought"] = {str(DAY0 - 3): ["old"], "junk": ["x"], str(DAY0 + 2): ["later"]}
        g.dealers["restocks"] = {str(DAY0 - 1): 2, str(DAY0 + 2): 1}
        _, w = dealer.wares(g)[0]
        dealer.buy(g, 4, w["id"])
        self.assertEqual(sorted(g.dealers["bought"]), [str(DAY0), str(DAY0 + 2)])
        self.assertEqual(sorted(g.dealers["restocks"]), [str(DAY0 + 2)])


class PricingTests(DealerCase):
    """Prices pinned to literals, and the rules the economy rests on."""

    def test_the_price_table(self):
        gear_price = {"rare": 3, "epic": 5, "ultra": 10, "legendary": 28}
        relic_price = {"rare": 2, "epic": 3, "ultra": 6, "legendary": 16}
        self.assertEqual(DEALER["price"], gear_price)
        self.assertEqual(DEALER["relic_price"], relic_price)
        for r, n in gear_price.items():
            self.assertEqual(dealer.price_of({"kind": "gear", "rarity": r, "relics": [], "curse": None}), n)
        for r, n in relic_price.items():
            self.assertEqual(dealer.price_of({"kind": "relic", "rarity": r, "relics": [], "curse": None}), n)
        self.assertEqual(DEALER["restock"], {"prices": [3, 6, 12], "max": 3})

    def test_a_socketed_relic_costs_exactly_what_it_costs_loose(self):
        for r, n in DEALER["relic_price"].items():
            bare = {"kind": "gear", "rarity": "epic", "relics": [], "curse": None}
            held = dict(bare, relics=[{"base": "relic_ember", "rarity": r}])
            self.assertEqual(dealer.price_of(held) - dealer.price_of(bare), n, r)
            self.assertEqual(dealer.price_of({"kind": "relic", "rarity": r, "relics": [], "curse": None}), n)

    def test_the_bargain_discount_is_on_the_gear_and_is_modest(self):
        self.assertLessEqual(DEALER["bargain"]["discount"], 0.35)
        self.assertEqual(DEALER["bargain"]["discount"], 0.3)
        curse = {"kind": "gear", "curse": "gaunt", "relics": []}
        self.assertEqual([dealer.price_of(dict(curse, rarity=r)) for r in ("rare", "epic", "ultra", "legendary")],
                         [2, 4, 7, 20])
        two = [{"base": "relic_ember", "rarity": "ultra"}] * 2
        self.assertEqual(dealer.price_of(dict(curse, rarity="ultra", relics=two)), 7 + 12)

    def test_the_forge_cannot_hand_back_relics_for_less_than_the_dealer_charged(self):
        from lamplighter import forge
        g = self.game(ring=4, gems=10000)
        checked = 0
        for d in range(DAY0, DAY0 + 40):
            self.day[0] = d
            g.room_id = dealer.room_for(g, 4)
            for _, w in dealer.wares(g):
                if w["kind"] != "gear":
                    continue
                paid = w["price"]
                state, inst = dealer.buy(g, 4, w["id"])
                self.assertEqual(state, "ok")
                loose = 0
                for k in range(len(inst["relics"])):
                    loose += DEALER["relic_price"][inst["relics"][0]["rarity"]]
                    forge.take_out(g, inst["id"], 0)
                self.assertGreaterEqual(paid, loose, (w["id"], paid, loose))
                checked += 1
        self.assertGreater(checked, 50)

    def test_relics_in_a_piece_are_the_pieces_rarity_up_to_the_rings_cap(self):
        g = self.game()
        order = gear.RARITY_ORDER
        seen = set()
        for d in range(DAY0, DAY0 + 150):
            for ring in RINGS:
                cap = DEALER["rings"][str(ring)]["socket_cap"]
                for w in dealer._wares(g, ring, d, 0):
                    for r in w["relics"]:
                        want = w["rarity"] if order.index(w["rarity"]) <= order.index(cap) else cap
                        self.assertEqual(r["rarity"], want, (ring, w["rarity"], cap))
                        seen.add((ring, w["rarity"], r["rarity"]))
        self.assertIn((4, "ultra", "ultra"), seen)
        self.assertIn((2, "ultra", "epic"), seen)

    def test_bargain_tiers_climb_one_step_and_stop_at_the_rings_limit(self):
        up = dealer.bargain_tier
        self.assertEqual(up("rare", 1, "epic"), "epic")
        self.assertEqual(up("epic", 1, "epic"), "epic")
        self.assertEqual(up("epic", 1, "ultra"), "ultra")
        self.assertEqual(up("ultra", 1, "ultra"), "ultra")
        self.assertEqual(up("ultra", 1, "legendary"), "legendary")
        self.assertEqual(up("legendary", 1, "legendary"), "legendary")
        self.assertEqual(up("legendary", 4, "godlike"), "legendary")
        self.assertEqual(up("epic", 0, "legendary"), "epic")
        self.assertEqual(up("ultra", 1, "epic"), "ultra")       # a limit never makes a piece weaker than it was rolled

    def test_the_bargain_is_a_tier_up_per_ring_and_only_the_last_ring_sells_legendary_gear(self):
        g = self.game()
        seen = {r: set() for r in RINGS}
        legend = {r: 0 for r in RINGS}
        for salt in (0, 3):
            g.dealers["salt"] = salt
            for d in range(DAY0, DAY0 + 200):
                for ring in RINGS:
                    for cloth in range(2):
                        ws = dealer._wares(g, ring, d, cloth)
                        seen[ring].add(ws[2]["rarity"])
                        legend[ring] += sum(w["rarity"] == "legendary" for w in ws if w["kind"] == "gear")
        self.assertEqual(seen[1], {"epic"})
        self.assertEqual(seen[2], {"ultra"})
        self.assertEqual(seen[3], {"ultra"})
        self.assertEqual(seen[4], {"ultra", "legendary"})
        self.assertEqual(legend[1] + legend[2] + legend[3], 0)
        self.assertGreater(legend[4], 0)

    def test_a_bargain_costs_more_than_a_fair_piece_a_tier_below_it(self):
        g = self.game()
        for ring in RINGS:
            for d in range(DAY0, DAY0 + 60):
                ws = dealer._wares(g, ring, d, 0)
                bargain = ws[2]
                below = gear.RARITY_ORDER[gear.RARITY_ORDER.index(bargain["rarity"]) - 1]
                self.assertGreater(bargain["price"], DEALER["price"][below], (ring, bargain["rarity"]))

    def test_golden_cloth(self):
        """One cloth, pinned. If this moves, the cloth changed for every player on that day.
        (M6 added three bases to the shared gear pool, which moved the picks: re-pinned once, for that reason only.)"""
        g = self.game()
        got = [(w["id"], w["base"], w["rarity"], [r["rarity"] for r in w["relics"]], w["curse"], w["price"])
               for w in dealer._wares(g, 4, DAY0, 0)]
        self.assertEqual(got, [
            ("20000:4:0:0", "drowned_mail", "epic", ["epic"], None, 8),
            ("20000:4:0:1", "ember_locket", "epic", ["epic"], None, 8),
            ("20000:4:0:2", "vg_nightcloak", "ultra", ["ultra", "ultra"], "dimmed", 19),
            ("20000:4:0:3", "relic_pulse", "epic", [], None, 3)])
        self.assertEqual([w["price"] for w in dealer._wares(g, 1, DAY0, 0)], [8, 8, 7, 2])

    def test_the_salt_and_the_ring_both_change_the_cloth(self):
        g = self.game()
        base = [w["seed"] for w in dealer._wares(g, 4, DAY0, 0)]
        g.dealers["salt"] = 5
        self.assertNotEqual(base, [w["seed"] for w in dealer._wares(g, 4, DAY0, 0)])
        g.dealers["salt"] = 0
        seeds = {ring: [w["seed"] for w in dealer._wares(g, ring, DAY0, 0)] for ring in RINGS}
        self.assertEqual(len({tuple(v) for v in seeds.values()}), 4)

    def test_the_cloth_uses_every_kind_of_gear_and_every_base_over_time(self):
        g = self.game()
        kinds, bases = set(), set()
        for d in range(DAY0, DAY0 + 80):
            for w in dealer._wares(g, 4, d, 0)[:3]:
                kinds.add(ITEMS[w["base"]]["kind"])
                bases.add(w["base"])
        self.assertEqual(kinds, {"weapon", "armor", "trinket"})
        self.assertGreaterEqual(len(bases), 10)

    def test_loose_relics_follow_the_rings_relic_odds_not_its_gear_odds(self):
        g = self.game()
        rarities = {r: set() for r in RINGS}
        for d in range(DAY0, DAY0 + 200):
            for ring in RINGS:
                rarities[ring].add(dealer._wares(g, ring, d, 0)[3]["rarity"])
        self.assertEqual(rarities[1], {"rare", "epic"})
        self.assertEqual(rarities[2], {"rare", "epic", "ultra"})
        self.assertEqual(rarities[3], {"epic", "ultra"})
        self.assertEqual(rarities[4], {"epic", "ultra", "legendary"})

    def test_a_piece_is_never_weaker_than_the_base_it_is_made_from(self):
        g = self.game()
        order = gear.RARITY_ORDER
        for d in range(DAY0, DAY0 + 120):
            for ring in RINGS:
                for w in dealer._wares(g, ring, d, 0)[:3]:
                    self.assertLessEqual(order.index(ITEMS[w["base"]].get("rarity", "common")), order.index(w["rarity"]), w)
                    if not w["curse"]:
                        self.assertGreaterEqual(dealer.sketch(w)["mult"].get("dmg", 1.0), 1.0, w)

    def test_the_prompts_say_exactly_what_will_be_charged(self):
        g = self.game(ring=4, gems=100)
        _, w = dealer.wares(g)[2]
        out = run(g, "talk dealer", answers=["3", "n", "5", "n", "0"])
        self.assertIn("Pay %d gems for it and carry the curse?" % w["price"], out)
        self.assertIn("Pay 3 gems to turn the cloth?", out)
        self.assertEqual(g.player.gems, 100)

    def test_exactly_enough_gems_turns_the_cloth(self):
        g = self.game(ring=4, gems=3)
        self.assertEqual(dealer.restock(g), ("ok", 3))
        self.assertEqual(g.player.gems, 0)
        g.player.gems = 5
        self.assertEqual(dealer.restock(g), ("poor", 6))

    def test_a_purchase_makes_exactly_one_item(self):
        g = self.game(ring=4, gems=500)
        for _, w in dealer.wares(g):
            before, counter = set(ITEMS), gear._counter[0]
            state, inst = dealer.buy(g, 4, w["id"])
            self.assertEqual(state, "ok")
            self.assertEqual(set(ITEMS) - before, {inst["id"]})
            self.assertEqual(gear._counter[0], counter + 1)

    def test_a_damaged_restock_count_never_goes_negative(self):
        g = self.game(ring=4)
        for bad in (-3, True, "2", None, 1.5):
            g.dealers["restocks"] = {str(DAY0): bad}
            self.assertEqual(dealer.cloth_no(g), 0, bad)
            self.assertEqual(dealer.restock_price(g), 3)
            self.assertTrue(all(w["id"] == "%d:4:0:%d" % (DAY0, w["slot"]) for _, w in dealer.wares(g)))


class UpgradeTests(DealerCase):
    def test_a_cursed_epic_bargain_still_gains_its_second_affix_in_the_forge(self):
        import random
        g = self.game()
        w = dealer._wares(g, 1, DAY0, 0)[2]
        self.assertEqual((w["rarity"], bool(w["curse"])), ("epic", True))
        inst = dealer._make(w)
        plain = lambda i: [a for a in i["affixes"] if not AFFIXES[a].get("curse")]
        self.assertEqual(len(plain(inst)), gear.AFFIX_COUNT["epic"])
        gear.upgrade(inst, "ultra", random.Random(1))
        self.assertEqual(len(plain(inst)), gear.AFFIX_COUNT["ultra"])
        self.assertIn(w["curse"], inst["affixes"])
        self.assertEqual(len(inst["affixes"]), gear.AFFIX_COUNT["ultra"] + 1)

    def test_an_ordinary_piece_upgrades_as_before(self):
        import random
        inst = gear.make("hauberk", "epic", random.Random(2))
        gear.upgrade(inst, "ultra", random.Random(3))
        self.assertEqual(len(inst["affixes"]), gear.AFFIX_COUNT["ultra"])


class MenuTextTests(DealerCase):
    def test_the_header_counts_the_wares_left(self):
        g = self.game(ring=4, gems=500)
        self.assertIn("Four wares on the cloth", run(g, "talk dealer", answers=["0"]))
        _, w = dealer.wares(g)[0]
        dealer.buy(g, 4, w["id"])
        self.assertIn("Three of the four wares are still on the cloth", run(g, "talk dealer", answers=["0"]))
        for _, w in dealer.wares(g):
            dealer.buy(g, 4, w["id"])
        out = run(g, "talk dealer", answers=["0"])
        self.assertIn("The cloth is bare", out)
        self.assertNotIn("Four wares", out)

    def test_a_bare_cloth_you_can_still_turn_says_to_turn_it(self):
        g = self.game(ring=4, gems=500)
        for _, w in dealer.wares(g):
            dealer.buy(g, 4, w["id"])
        out = run(g, "talk dealer", answers=["0"])
        self.assertIn("Nothing left on the cloth. Turn it, or come back tomorrow.", out)
        self.assertIn("Turn the cloth for new wares", out)

    def test_a_bare_cloth_that_cannot_be_turned_again_does_not_say_to_turn_it(self):
        g = self.game(ring=4, gems=500)
        for _ in range(3):
            dealer.restock(g)
        for _, w in dealer.wares(g):
            dealer.buy(g, 4, w["id"])
        out = run(g, "talk dealer", answers=[""])
        self.assertIn("Nothing left on the cloth. Come back tomorrow.", out)
        self.assertNotIn("Turn it", out)
        self.assertNotIn("Turn the cloth for", out)
        self.assertIn("turned 3 times today", out)
        self.assertIsNone(re.search(r"Four wares on the cloth", out))

    def test_a_poor_player_is_told_before_being_asked_to_confirm_a_restock(self):
        g = self.game(ring=4, gems=2)
        out = run(g, "talk dealer", answers=["5", "", "0"])
        self.assertIn("You have 2 gems. Turning the cloth takes 3.", out)
        self.assertNotIn("Pay 3 gems to turn", out)
        self.assertEqual((g.player.gems, g.dealers["restocks"]), (2, {}))

    def test_the_wares_wait_for_a_blank_line_after_the_turned_cloth_note(self):
        g = self.game(ring=4, gems=500)
        for _ in range(3):
            dealer.restock(g)
        out = run(g, "talk dealer", answers=["0"])
        self.assertIsNotNone(re.search(r"until tomorrow\.\n\n", out))

    def test_wrapped_detail_lines_keep_a_hanging_indent_and_are_not_wrapped_twice(self):
        g = self.game(ring=4, gems=500)
        with mock.patch.object(dealer.ui, "width", return_value=60):
            wrapped = 0
            for _, w in dealer.wares(g):
                lines = dealer._label(w).split("\n")
                self.assertTrue(lines[0] and not lines[0].startswith(" "))
                for l in lines[1:]:
                    if not l:
                        continue
                    self.assertLessEqual(ui.visible_len(l), 60 - 4, l)
                    self.assertTrue(l.startswith("    "), l)
                    if l.startswith("        "):
                        wrapped += 1
            self.assertGreater(wrapped, 0)
            out = run(g, "talk dealer", answers=["0"])
        for l in out.split("\n"):
            if not l.lstrip().startswith(("─", "═")):      # a rule is as wide as the screen
                self.assertLessEqual(ui.visible_len(l), 60, l)
        # a continuation line sits further in than the first line of its detail
        self.assertIn("\n            ", out)


class SavedBlockTests(DealerCase):
    def damaged_save(self, bad):
        from lamplighter import save
        g = self.game(ring=4)
        d = g.to_dict()
        d["dealers"] = bad
        save.write(d, "bad")
        return Game.load("bad")

    def test_a_dealers_block_that_is_not_a_dict_is_replaced_on_load(self):
        with temp_home():
            for bad in ("abc", [1, 2], 7, 0, "", None, [], {}, True):
                g2 = self.damaged_save(bad)
                self.assertEqual(g2.dealers, dealer.new_state(), bad)
                for rid in ROOMS:
                    g2.room_id = rid
                    g2.present_npcs()
                g2.room_id = dealer.room_for(g2, 4)
                self.assertEqual(len(dealer.wares(g2)), 4)

    def test_a_good_block_is_kept_as_it_is(self):
        with temp_home():
            block = {"salt": 4, "bought": {str(DAY0): ["x"]}, "restocks": {str(DAY0): 2}}
            self.assertEqual(self.damaged_save(copy.deepcopy(block)).dealers, block)

    def test_the_dealer_repairs_a_block_that_got_damaged_after_loading(self):
        for bad in ("x", [1], 5, None):
            g = self.game(ring=4)
            g.dealers = bad
            g.present_npcs()
            self.assertEqual(dealer.cloth_no(g), 0)
            self.assertIsInstance(g.dealers, dict)
            self.assertEqual(len(dealer.wares(g, 4)), 4)

    def test_load_state(self):
        self.assertEqual(dealer.load_state(None), dealer.new_state())
        self.assertEqual(dealer.load_state("x"), dealer.new_state())
        self.assertEqual(dealer.load_state({"salt": 2}), {"salt": 2})


class ContentCheckTests(unittest.TestCase):
    def bad(self, mutate):
        d = copy.deepcopy(DEALER)
        mutate(d)
        return dealer.check(d)

    def test_the_shipped_data_is_clean(self):
        self.assertEqual(dealer.check(DEALER), [])
        self.assertEqual([e for e in validate.validate() if "dealer" in e], [])

    def test_the_prices_are_justified_in_writing(self):
        self.assertGreater(len(DEALER["notes"]), 200)
        self.assertTrue(self.bad(lambda d: d.pop("notes")))
        self.assertTrue(self.bad(lambda d: d.update(notes="  ")))

    def test_godlike_anywhere_is_an_error(self):
        self.assertTrue(any("godlike" in e for e in self.bad(lambda d: d["price"].update(godlike=60))))
        self.assertTrue(any("godlike" in e for e in self.bad(lambda d: d["relic_price"].update(godlike=60))))
        self.assertTrue(any("godlike" in e for e in self.bad(lambda d: d["rings"]["4"]["gear_odds"].update(godlike=1))))
        self.assertTrue(any("godlike" in e for e in self.bad(lambda d: d["rings"]["4"]["relic_odds"].update(godlike=1))))
        self.assertTrue(self.bad(lambda d: d["rings"]["4"].update(socket_cap="godlike")))

    def test_unknown_rarities_missing_prices_and_bad_numbers(self):
        self.assertTrue(self.bad(lambda d: d["rings"]["1"]["gear_odds"].update(mythic=5)))
        self.assertTrue(self.bad(lambda d: d["price"].pop("ultra")))
        self.assertTrue(self.bad(lambda d: d["price"].update(epic=0)))
        self.assertTrue(self.bad(lambda d: d["price"].update(epic=2.5)))
        self.assertTrue(self.bad(lambda d: d["rings"]["2"]["gear_odds"].update(epic=-1)))
        self.assertTrue(self.bad(lambda d: d["rings"]["4"]["gear_odds"].clear()))

    def test_a_missing_or_extra_ring(self):
        self.assertTrue(self.bad(lambda d: d["rings"].pop("3")))
        self.assertTrue(self.bad(lambda d: d["rings"].update({"0": copy.deepcopy(d["rings"]["1"])})))

    def test_a_bargain_tier_or_socketed_relic_without_a_price(self):
        self.assertTrue(self.bad(lambda d: d["price"].pop("legendary")))
        self.assertTrue(self.bad(lambda d: d["relic_price"].pop("ultra")))

    def test_restock_rules(self):
        self.assertTrue(self.bad(lambda d: d["restock"].update(prices=[3, 6])))
        self.assertTrue(self.bad(lambda d: d["restock"].update(prices=[12, 6, 3])))
        self.assertTrue(self.bad(lambda d: d["restock"].update(max=0)))
        self.assertTrue(self.bad(lambda d: d["restock"].update(prices=[0, 1, 2])))

    def test_bargain_rules(self):
        self.assertTrue(self.bad(lambda d: d["bargain"].update(discount=1.5)))
        self.assertTrue(self.bad(lambda d: d["bargain"].update(discount=0)))
        self.assertTrue(self.bad(lambda d: d["bargain"].update(uplift=5)))
        self.assertTrue(self.bad(lambda d: d["bargain"].update(relics=9)))

    def test_unknown_or_wrong_kind_items(self):
        self.assertTrue(self.bad(lambda d: d["gear"]["weapon"].append("no_such_thing")))
        self.assertTrue(self.bad(lambda d: d["gear"]["weapon"].append("hauberk")))
        self.assertTrue(self.bad(lambda d: d["relics"].append("hauberk")))
        self.assertTrue(self.bad(lambda d: d["relics"].append("no_such_relic")))
        self.assertTrue(self.bad(lambda d: d["relics"].clear()))
        self.assertTrue(self.bad(lambda d: d["gear"].pop("armor")))

    def test_socketed_relics_may_not_be_cheaper_than_loose_ones(self):
        self.assertTrue(any("socket_share" in e for e in self.bad(lambda d: d.update(socket_share=0.5))))
        self.assertTrue(any("socket_share" in e for e in self.bad(lambda d: d.update(socket_share=3))))
        self.assertFalse(any("socket_share" in e for e in self.bad(lambda d: d.update(socket_share=1.5))))

    def test_socket_cap_and_bargain_cap_are_checked(self):
        self.assertTrue(any("socket_cap must be" in e for e in self.bad(lambda d: d["rings"]["4"].update(socket_cap="godlike"))))
        self.assertTrue(any("socket_cap must be" in e for e in self.bad(lambda d: d["rings"]["4"].update(socket_cap="mythic"))))
        self.assertTrue(any("bargain_cap must be" in e for e in self.bad(lambda d: d["rings"]["4"].update(bargain_cap="godlike"))))
        self.assertTrue(any("bargain_cap must be" in e for e in self.bad(lambda d: d["rings"]["1"].pop("bargain_cap"))))
        self.assertTrue(any("bargain tier" in e for e in self.bad(lambda d: d["price"].pop("ultra"))))

    def test_the_content_validator_reports_dealer_problems(self):
        bad = copy.deepcopy(DEALER)
        bad["price"]["godlike"] = 60
        with mock.patch.object(validate, "DEALER", bad):
            self.assertTrue(any("godlike" in e for e in validate.validate()))


if __name__ == "__main__":
    unittest.main()
