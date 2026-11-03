"""Silent fight simulation, used to tune balance with data instead of guesses.

A fight is run with a policy (a function that returns an Action each turn) and no UI.
"""
import random

from . import gear, ui
from .combat import Action, Combat
from .content import ENEMIES, ITEMS
from .engine import Game
from .entities import Player

# A sensible kit for the point in the story where a fight happens.
DEFAULT_ITEMS = {"draught": 3, "oil": 3}


def build_player(cls="wayfarer", level=3, weapon=None, armor=None, trinket=None, items=None, lantern=None, dread=0,
                 spells=()):
    p = Player("Sim", cls)
    p.dread = dread
    if lantern:
        p.lantern.update(lantern)
    while p.level < level:
        p.gain_xp(p.xp_next)
    # spend the level-up points the way a sensible player would: damage stat and vitality
    dmg_stat = {"warden": "str", "ashblade": "wil", "wayfarer": "str"}[cls]
    for i in range(p.points):
        setattr(p, dmg_stat if i % 2 == 0 else "vit", getattr(p, dmg_stat if i % 2 == 0 else "vit") + 1)
    p.points = 0
    if weapon:
        p.equipment["weapon"] = weapon
    if armor:
        p.equipment["armor"] = armor
    if trinket:
        p.equipment["trinket"] = trinket
    for iid, n in (items if items is not None else DEFAULT_ITEMS).items():
        p.add_item(iid, n)
    for element, rarity in spells:      # [(element, rarity)] equipped as spell books
        if rarity == "common":
            p.spells.append("book_" + element)
        else:
            inst = gear.make("book_" + element, rarity, random.Random(7), affixes=[])
            gear.give(p, inst)
            p.inventory.pop(inst["id"], None)
            p.spells.append(inst["id"])
    p.hp = p.max_hp
    return p


def equip_gear(p, slot, base, rarity, relics=(), rng=None):
    """Put a forged-style item in a slot. relics: [(type, rarity)] socketed into it."""
    rng = rng or random.Random(11)
    inst = gear.make(base, rarity, rng, relics=[{"base": "relic_" + t, "rarity": r} for t, r in relics])
    gear.give(p, inst)
    p.inventory.pop(inst["id"], None)
    p.equipment[slot] = inst["id"]
    return inst


def maxed(cls, level, weapon, armor, rarity, relics=(), armor_relics=(), **kw):
    """A build for the power-curve report: weapon and armour at one rarity, with relics in the weapon (and armour)."""
    p = build_player(cls=cls, level=level, **kw)
    equip_gear(p, "weapon", weapon, rarity, relics)
    equip_gear(p, "armor", armor, rarity, armor_relics)
    p.hp = p.max_hp
    return p


def scaled_enemy(eid, hp=1.0, atk=1.0):
    """Register a stronger copy of an enemy (a stand-in for a future, harder area) and return its id."""
    import copy
    new = "%s_x%g_%g" % (eid, hp, atk)
    t = copy.deepcopy(ENEMIES[eid])
    t["hp"] = int(t["hp"] * hp)
    t["atk"] = int(t["atk"] * atk)
    ENEMIES[new] = t
    return new


# ---------------------------------------------------------------------------- policies
def suggested(cmb):
    """Play exactly what the game's own suggestion says."""
    return cmb.suggest()[0]


def flare_spam(cmb):
    """Flare whenever possible, otherwise attack. Used to check no single tactic dominates."""
    p = cmb.p
    if p.hp < p.max_hp * 0.32:
        for iid in ("strong_draught", "draught"):
            if p.inventory.get(iid):
                return Action("item", item=iid)
    if cmb.flare_ready():
        return Action("flare")
    return Action("attack", target=cmb.best_target())


def no_flare(cmb):
    """Never use the lantern. Takes the suggestion unless it is a flare."""
    a, _ = cmb.suggest()
    if a.kind == "flare":
        return Action("attack", target=cmb.best_target())
    return a


def attack_only(cmb):
    p = cmb.p
    if p.hp < p.max_hp * 0.32:
        for iid in ("strong_draught", "draught"):
            if p.inventory.get(iid):
                return Action("item", item=iid)
    return Action("attack", target=cmb.best_target())


POLICIES = {"suggested": suggested, "flare_spam": flare_spam, "no_flare": no_flare, "attack_only": attack_only}


# ---------------------------------------------------------------------------- running
def fight(enemy_ids, policy, seed, room="wood_path", difficulty=1.0, **player_kwargs):
    """Run one fight. Returns (outcome, rounds, hp_left, oil_left)."""
    game = Game(seed=seed)
    builder = player_kwargs.pop("builder", None)
    game.player = builder() if builder else build_player(**player_kwargs)
    game.room_id = room
    game.difficulty = difficulty
    cmb = Combat(game, enemy_ids, policy=policy, no_flee=True)
    outcome = cmb.run()
    p = game.player
    for iid in list(p.gear):          # simulated gear should not pile up in the global item table
        ITEMS.pop(iid, None)
    return outcome, cmb.round, max(0, p.hp), p.oil


def win_rate(enemy_ids, policy, n=200, **kwargs):
    """Fraction of n seeded fights won, plus average rounds and average HP left on a win."""
    ui.io.mute = True
    old = ui.settings.typewriter
    ui.settings.typewriter = False
    wins = rounds = hp = 0
    try:
        for seed in range(n):
            outcome, r, hp_left, _ = fight(enemy_ids, policy, seed, **kwargs)
            rounds += r
            if outcome == "win":
                wins += 1
                hp += hp_left
    finally:
        ui.io.mute = False
        ui.settings.typewriter = old
    return {"win": wins / n, "rounds": rounds / n, "hp_on_win": (hp / wins) if wins else 0}
