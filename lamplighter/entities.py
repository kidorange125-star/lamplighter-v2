"""Player and enemy state. Pure data plus derived stats; no printing here."""
import copy
import random

from . import gear as gearlib
from .content import CLASSES, SKILLS
from .content import ITEMS

# statuses that are applied by the owner on their own turn get one extra tick so
# they cover the expected number of enemy actions (durations tick at end of turn)
STATUS_INFO = {
    "burn": ("burning", "flame"),
    "bleed": ("bleeding", "blood"),
    "poison": ("brine-sick", "brine"),
    "stun": ("stunned", "byellow"),
    "weak": ("weakened", "ash"),
    "exposed": ("exposed", "bred"),
    "blind": ("blinded", "bone"),
    "regen": ("regenerating", "bgreen"),
    "bulwark": ("braced", "sky"),
    "shadow": ("in shadow", "night"),
    "kindled": ("kindled", "amber"),
    "cinder": ("cinder wall", "ember"),
    "shroud": ("shrouded", "hollow"),
    "enraged": ("enraged", "bred"),
    "ward": ("warded", "moss"),
}

DOTS = ("burn", "bleed", "poison")

LEVEL_CAP = 12

# Dread: 0-100. See docs/V2-PLAN.md section 2.9.
DREAD_TIERS = [(100, "Consumed"), (75, "Terrified"), (50, "Afraid"), (25, "Uneasy"), (0, "Steady")]
DREAD_COLOUR = {"Steady": "grey", "Uneasy": "byellow", "Afraid": "flame", "Terrified": "bred", "Consumed": "bmagenta"}
DREAD_DAMAGE = {"Uneasy": 1.05, "Afraid": 1.12, "Terrified": 1.20, "Consumed": 1.20}
DREAD_DODGE_PENALTY = {"Uneasy": 5, "Afraid": 10, "Terrified": 10, "Consumed": 10}
DREAD_TAKEN = {"Afraid": 1.10, "Terrified": 1.20, "Consumed": 1.20}   # fear makes you easier to hurt


class Combatant:
    name = "?"

    def __init__(self):
        self.statuses = {}  # name -> [turns, power]
        self.shield = 0

    # ---- statuses
    def has(self, s):
        return s in self.statuses

    def power_of(self, s):
        return self.statuses.get(s, [0, 0])[1]

    def apply(self, s, turns, power=0, self_cast=False):
        if self_cast:
            turns += 1
        if s in self.statuses:
            old_t, old_p = self.statuses[s]
            if s == "bleed":  # bleeding stacks, up to three wounds' worth
                self.statuses[s] = [max(old_t, turns), min(old_p + power, power * 3)]
            else:
                self.statuses[s] = [max(old_t, turns), max(old_p, power)]
        else:
            self.statuses[s] = [turns, power]

    def remove(self, s):
        self.statuses.pop(s, None)

    def cleanse(self):
        for s in ("burn", "bleed", "poison", "weak", "blind", "exposed", "stun"):
            self.remove(s)

    def tick_end(self):
        """Decrement durations at end of own turn. Returns list of expired names."""
        expired = []
        for s in list(self.statuses):
            if s in ("stun",):
                continue
            self.statuses[s][0] -= 1
            if self.statuses[s][0] <= 0:
                del self.statuses[s]
                expired.append(s)
        if "cinder" not in self.statuses and "ward" not in self.statuses:
            self.shield = 0
        return expired

    def status_line(self):
        parts = []
        for s, (t, p) in self.statuses.items():
            label, col = STATUS_INFO.get(s, (s, "grey"))
            extra = (" %d" % p) if s in DOTS else ""
            parts.append("{%s}%s%s{/}" % (col, label, extra))
        if self.shield > 0:
            parts.append("{ember}shield %d{/}" % self.shield)
        return "  ".join(parts)

    @property
    def dead(self):
        return self.hp <= 0


# =============================================================================
class Player(Combatant):
    def __init__(self, name="Wick", cls="warden"):
        super().__init__()
        self.name = name
        self.cls = cls
        b = CLASSES[cls]["base"]
        self.base_hp = b["hp"]
        self.str, self.wil, self.agi, self.vit = b["str"], b["wil"], b["agi"], b["vit"]
        self.level = 1
        self.xp = 0
        self.points = 0
        self.gold = 15
        self.bonus_hp = 0
        self.inventory = {}
        self.equipment = {"weapon": None, "armor": None, "trinket": None}
        self.oil = 100
        self.lantern = {"shroud": False, "lens": False, "trim": False}
        self.focus = 0
        self.gems = 0
        self.gear = {}            # forged and rolled item instances, by id (see gear.py)
        self.spells = []          # equipped spell books (see spells.py)
        self.stash = {}
        self.dread = 0
        self.dread_effects = True   # False = Dread is shown but changes nothing
        self.shaken = False         # after a collapse, until you rest
        self.hollowing = 0          # rounds of Hollowing left (combat only)
        self.relic_level = 1
        self.relic_charges = 2
        self.add_item("hook")
        self.equipment["weapon"] = "hook"
        self.inventory.pop("hook", None)
        for g in CLASSES[cls]["gear"]:
            kind = ITEMS[g]["kind"]
            self.equipment[kind] = g
        self.add_item("draught", 3)
        self.add_item("oil", 1)
        self.hp = self.max_hp

    # ---- equipment stats
    def gear_stat(self, k):
        total = 0
        for slot, iid in self.equipment.items():
            if iid:
                total += ITEMS[iid].get("stats", {}).get(k, 0)
        return total

    def mult(self, kind):
        """Product of every equipped multiplier that applies to this kind of damage (or "heal").

        Keys on an item's `mult`: dmg (all damage), phys, fire, light (flares), heal (healing items).
        They multiply with each other, so stacking several is far stronger than having one.
        """
        total = 1.0
        for iid in self.equipment.values():
            if not iid:
                continue
            m = ITEMS[iid].get("mult")
            if not m:
                continue
            if kind != "heal":
                total *= m.get("dmg", 1.0)
            total *= m.get(kind, 1.0)
        return total

    @property
    def STR(self):
        return self.str + self.gear_stat("str")

    @property
    def WIL(self):
        return self.wil + self.gear_stat("wil")

    @property
    def AGI(self):
        return max(0, self.agi + self.gear_stat("agi"))

    @property
    def max_hp(self):
        return self.base_hp + (self.level - 1) * 6 + self.vit * 5 + self.gear_stat("hp") + self.bonus_hp

    @property
    def attack(self):
        return 4 + self.STR + self.gear_stat("atk")

    @property
    def spell(self):
        return 4 + int(self.WIL * 1.6)

    @property
    def magic(self):
        """Raw strength of a spell. Grows with Will and level, so every class can cast, casters cast best."""
        return int(5 + self.WIL * 1.5 + self.level * 1.5)

    @property
    def defense(self):
        return self.gear_stat("def") + self.vit // 2

    @property
    def crit(self):
        return 5 + self.AGI * 1.5 + self.gear_stat("crit") + self.dread_crit()

    @property
    def dodge(self):
        return max(0, min(35, self.AGI * 1.0 + self.gear_stat("dodge")) - self.dread_dodge_penalty())

    # ---- dread
    @property
    def dread_tier(self):
        for floor, name in DREAD_TIERS:
            if self.dread >= floor:
                return name
        return "Steady"

    def dread_damage_mult(self):
        if not self.dread_effects:
            return 1.0
        m = 1.4 if self.hollowing else DREAD_DAMAGE.get(self.dread_tier, 1.0)
        return m * (0.8 if self.shaken else 1.0)

    def dread_taken_mult(self):
        return DREAD_TAKEN.get(self.dread_tier, 1.0) if self.dread_effects else 1.0

    def dread_crit(self):
        return 10 if self.dread_effects and self.dread_tier in ("Afraid", "Terrified", "Consumed") else 0

    def dread_dodge_penalty(self):
        return DREAD_DODGE_PENALTY.get(self.dread_tier, 0) if self.dread_effects else 0

    def calm(self):
        """Resting, or reaching town: all fear and its aftermath end."""
        self.dread = 0
        self.shaken = False
        self.hollowing = 0

    @property
    def relic_max_charges(self):
        return 1 + self.relic_level

    @property
    def regen(self):
        return self.gear_stat("regen")

    # ---- lantern
    @property
    def max_oil(self):
        return 130 if self.lantern["shroud"] else 100

    @property
    def move_cost(self):
        return max(1, 3 - (1 if self.lantern["shroud"] else 0) - self.gear_stat("oil_save"))

    @property
    def flare_cost(self):
        return 20 - (5 if self.lantern["lens"] else 0) - (3 if self.lantern.get("trim") else 0)

    @property
    def flare_power(self):
        return 6 + int(self.WIL * 0.7) + (5 if self.lantern["lens"] else 0) + self.level

    @property
    def lantern_level(self):
        return 1 + int(self.lantern["shroud"]) + int(self.lantern["lens"])

    def add_oil(self, n):
        before = self.oil
        self.oil = max(0, min(self.max_oil, self.oil + n))
        return self.oil - before

    # ---- inventory
    def add_item(self, iid, n=1):
        self.inventory[iid] = self.inventory.get(iid, 0) + n

    def remove_item(self, iid, n=1):
        if self.inventory.get(iid, 0) < n:
            return False
        self.inventory[iid] -= n
        if self.inventory[iid] <= 0:
            del self.inventory[iid]
        return True

    def count(self, iid):
        n = self.inventory.get(iid, 0)
        if iid in self.equipment.values():
            n += 1
        return n

    def has_item(self, iid):
        return self.count(iid) > 0

    # ---- progression
    @property
    def xp_next(self):
        return int(20 * self.level ** 1.55)

    def gain_xp(self, n):
        """Returns number of levels gained."""
        self.xp += n
        gained = 0
        while self.level < LEVEL_CAP and self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.points += 2
            grow = CLASSES[self.cls]["grow"]
            setattr(self, grow, getattr(self, grow) + 1)
            gained += 1
        if gained:
            self.hp = self.max_hp
        return gained

    @property
    def skills(self):
        return [s for s in CLASSES[self.cls]["skills"] if SKILLS[s]["level"] <= self.level]

    @property
    def cls_name(self):
        return CLASSES[self.cls]["name"]

    def heal(self, n):
        if self.dread_effects and self.dread_tier in ("Terrified", "Consumed"):
            n = int(n * 0.75)
        before = self.hp
        self.hp = min(self.max_hp, self.hp + n)
        return self.hp - before

    # ---- save
    def to_dict(self):
        return {
            "name": self.name, "cls": self.cls, "base_hp": self.base_hp,
            "str": self.str, "wil": self.wil, "agi": self.agi, "vit": self.vit,
            "level": self.level, "xp": self.xp, "points": self.points, "gold": self.gold,
            "bonus_hp": self.bonus_hp, "inventory": self.inventory, "equipment": self.equipment,
            "oil": self.oil, "lantern": self.lantern, "hp": self.hp,
            "gems": self.gems, "gear": self.gear, "spells": self.spells, "stash": self.stash, "dread": self.dread, "dread_effects": self.dread_effects,
            "shaken": self.shaken, "relic_level": self.relic_level, "relic_charges": self.relic_charges,
        }

    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls)
        Combatant.__init__(p)
        # fields added after the first saves existed
        p.gems, p.stash, p.dread, p.dread_effects, p.gear, p.spells = 0, {}, 0, True, {}, []
        p.shaken, p.hollowing, p.relic_level, p.relic_charges = False, 0, 1, 2
        for k, v in d.items():
            setattr(p, k, copy.deepcopy(v))
        p.focus = 0
        p.hollowing = 0
        gearlib.register_all(p.gear)
        return p


# =============================================================================
class Enemy(Combatant):
    def __init__(self, eid, template, scale=1.0):
        super().__init__()
        t = copy.deepcopy(template)
        self.id = eid
        self.t = t
        self.name = t["name"]
        self.max_hp = int(t["hp"] * scale)
        self.hp = self.max_hp
        self.atk = t["atk"]
        self.defense = t.get("def", 0)
        self.dodge = t.get("dodge", 0)
        self.tags = set(t.get("tags", []))
        self.weak = list(t.get("weak", []))
        self.resist = list(t.get("resist", []))
        self.attune = t.get("attune")      # rotating weakness: {"every": n, "stances": [...]}
        self.stance = None                 # index into attune["stances"] once the fight has set one
        self.moves = t["moves"]
        self.phases = t.get("phases", [])
        self.phase = 0
        self.intent = None
        self.boss = "boss" in self.tags
        self.guarding = False
        self.turn = 0

    @property
    def hollow(self):
        return "hollow" in self.tags

    def stance_for(self, rnd):
        """Index of the attune stance in force during round `rnd` (rounds count from 1)."""
        a = self.attune
        return ((max(rnd, 1) - 1) // a["every"]) % len(a["stances"])

    def rounds_to_shift(self, rnd):
        """Rounds from `rnd` until the next stance begins."""
        every = self.attune["every"]
        return every - (max(rnd, 1) - 1) % every

    def set_stance(self, rnd):
        """Take the stance for round `rnd`, replacing weak/resist. Returns True if it differs from the last one."""
        if not self.attune:
            return False
        idx = self.stance_for(rnd)
        if idx == self.stance:
            return False
        st = self.attune["stances"][idx]
        self.weak = list(st.get("weak", []))
        self.resist = list(st.get("resist", []))
        changed = self.stance is not None
        self.stance = idx
        return changed

    def choose_intent(self, rng, allies):
        """Pick next move by weight, honouring 'only_if' conditions."""
        options = []
        for m in self.moves:
            cond = m.get("only_if")
            if cond == "hurt_ally" and not any(a.hp < a.max_hp * 0.6 for a in allies if not a.dead):
                continue
            if cond == "hurt_self" and self.hp > self.max_hp * 0.5:
                continue
            if cond == "can_summon" and len([a for a in allies if not a.dead]) >= 3:
                continue
            if cond == "no_shroud" and self.has("shroud"):
                continue
            if m.get("every") and (self.turn % m["every"]) != m.get("offset", 0):
                continue
            options.append(m)
        if not options:
            options = [m for m in self.moves if not m.get("only_if")] or self.moves
        # don't repeat a heavy move twice in a row
        if self.intent and self.intent.get("kind") == "heavy":
            light = [m for m in options if m.get("kind") != "heavy"]
            if light:
                options = light
        weights = [m.get("weight", 1) for m in options]
        self.intent = rng.choices(options, weights=weights)[0]
        return self.intent
