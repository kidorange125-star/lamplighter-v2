"""Player and enemy state. Pure data plus derived stats; no printing here."""
import copy
import random

from .data.classes import CLASSES, SKILLS
from .data.items import ITEMS

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
}

DOTS = ("burn", "bleed", "poison")


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
        if "cinder" not in self.statuses:
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
    def defense(self):
        return self.gear_stat("def") + self.vit // 2

    @property
    def crit(self):
        return 5 + self.AGI * 1.5 + self.gear_stat("crit")

    @property
    def dodge(self):
        return min(35, self.AGI * 1.0 + self.gear_stat("dodge"))

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
        while self.level < 12 and self.xp >= self.xp_next:
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
        }

    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls)
        Combatant.__init__(p)
        for k, v in d.items():
            setattr(p, k, copy.deepcopy(v))
        p.focus = 0
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
