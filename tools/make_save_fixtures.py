"""Builds the save fixtures in tests/fixtures/saves/ from a real, played-in game.

usage: python tools/make_save_fixtures.py

  v2_current.json     what the game writes today (Game.to_dict of a played-in game)
  v1_pre_m5.json      the same game as it was written before M5: the Darkness Dealer's state lives in the story
                      flags (dealer_bought, dealer_salt) and there is no `dealers` block
  v0_prototype.json   the pre-versioning shape: no save_version, none of the later blocks, a bare player

The fixtures are committed; run this again only when the format changes on purpose, and then ADD a new fixture
for the new format rather than replacing the old ones. Old fixtures must keep loading.
"""
import json
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LAMPLIGHTER_HOME"] = tempfile.mkdtemp(prefix="ll_fixtures_")

from lamplighter import clock, forge, gear, save, town  # noqa: E402
from lamplighter.engine import Game  # noqa: E402
from tests.helpers import new_game, run  # noqa: E402

OUT = os.path.join(ROOT, "tests", "fixtures", "saves")
NOON = 20000 * 86400 + 43200   # a fixed day, so the Dealer's day key is stable


def played_in_game():
    clock.set_clock(lambda: NOON)
    gear._counter[0] = 0
    g = new_game("wayfarer", seed=11)
    g.player.name = "Fixture"
    run(g, "e", "e", "look")
    g.player.gold = 245
    g.player.gems = 9
    g.player.level = 4
    g.player.xp = 31
    g.player.points = 2
    g.flags["met_orrin"] = True
    g.flags["visited_regions"] = ["Hollowmere"]
    g.flags["wren_home"] = True
    g.quests["main"] = 1
    g.quests["lamps"] = 2
    g.player.add_item("homecoming_charm")
    g.last_rest = "hall"
    rng = random.Random(5)
    gear.make("hunting_spear", "epic", rng)                   # g1: bought and thrown away again, so ids have a gap
    gear.discard(g.player, "g1")
    spear = gear.make("saltsteel_saber", "epic", rng)          # g2
    mail = gear.make("hauberk", "ultra", rng)                  # g3
    charm = gear.make("moth_charm", "rare", rng)               # g4
    rod = gear.make("ashwood_rod", "legendary", rng)           # g5
    for inst in (spear, mail, charm, rod):
        gear.give(g.player, inst)
    g.player.equipment["weapon"] = spear["id"]
    g.player.equipment["armor"] = mail["id"]
    town.invite(g, "market")
    town.invite(g, "home")
    g.town["stash_level"] = 2
    g.forge["heat"]["gear:epic"] = 2
    # a job in the forge for the equipped sabre: leaves a loaner weapon (another one-of-a-kind id) behind
    tier = forge.info(spear["id"])
    g.player.gold += tier["gold"]
    for mid, n in tier["items"].items():
        g.player.add_item(mid, n)
    ok, why = forge.start(g, spear["id"])
    assert ok, why
    # the Dealer: a salt and a ware bought today
    g.dealers["salt"] = 3
    g.dealers["bought"][str(int(NOON // 86400))] = [1]
    g.dealers["bought"]["19990"] = [0, 2]
    g.dealers["restocks"][str(int(NOON // 86400))] = 1
    g.stats.update({"kills": 14, "battles": 9, "deaths": 1})
    g.moves = 87
    return g


def to_v1(d):
    d = json.loads(json.dumps(d))
    dealers = d.pop("dealers")
    d["flags"]["dealer_bought"] = dealers["bought"]
    d["flags"]["dealer_salt"] = dealers["salt"]
    d["save_version"] = 1
    d["game_version"] = "2.0.0-dev.5"
    return d


def to_v0(d):
    """The v1 prototype's save: no version, no later blocks, an older player."""
    d = to_v1(d)
    del d["save_version"]
    for k in ("game_version", "town", "forge", "anchors", "settings", "room_items"):
        d.pop(k, None)
    for k in ("dealer_bought", "dealer_salt", "wren_home"):
        d["flags"].pop(k, None)
    d["quests"] = {"main": 1}
    p = d["player"]
    for k in ("gems", "gear", "spells", "stash", "dread", "dread_effects", "shaken", "relic_level", "relic_charges"):
        p.pop(k, None)
    p["inventory"] = {"draught": 3, "oil": 1}
    p["equipment"] = {"weapon": "hook", "armor": "oilskin", "trinket": None}
    p["lantern"].pop("trim", None)
    return d


def dump(name, d):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote", path)


def main():
    g = played_in_game()
    d = g.to_dict()
    d["save_version"] = save.SAVE_VERSION
    json.dumps(d)   # must be plain JSON
    dump("v2_current.json", d)
    dump("v1_pre_m5.json", to_v1(d))
    dump("v0_prototype.json", to_v0(d))
    clock.set_clock(None)


main()
