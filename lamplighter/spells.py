"""Spell books: slots, equipping, crafting from essences, and combining books by chance.

A spell is a book. Books use the same rarity ladder as gear; the higher the rarity the stronger the spell. A common
book is a plain stackable item (`book_fire`); a better one is a gear instance (see gear.py). Spells cost focus and
have a cooldown, scale with Will, and are strong against an enemy's weaknesses and weak against its resistances.

Combining (the Magician): two books become one, by chance. The odds are always shown first.
  - Same element: may rise a tier, may stay, may fall one.
  - Different elements: a different element (see the recipe log), usually one tier lower.
  - The apex spell needs one Godlike book of every element and has a low chance. See SPELL_RULES["apex"].
    Every failed attempt adds heat (`apex_chance`), so the chance climbs until it lands.
  - The Grand Binding (craft tier "grand") also spends one Heart of the book's element and can bind a Godlike book.
"""
from . import elements, gear
from .content import ITEMS, SPELL_RULES, SPELLS

ORDER = gear.RARITY_ORDER
POWER = SPELL_RULES["spell_power"]
MAX_SLOTS = len(SPELL_RULES["slot_levels"])
HEAT_FLAG = "arc_apex_heat"


# ---------------------------------------------------------------------------- reading a book
def spell_id(book):
    return ITEMS[book]["spell"]


def element_of(book):
    return ITEMS[book]["element"]


def rarity_of(book):
    return ITEMS[book].get("rarity", "common")


def plus_of(book):
    return ITEMS[book].get("plus", 0)


def power_mult(book):
    """How much stronger this copy of the spell is than the basic one."""
    return POWER[rarity_of(book)] * (1 + SPELL_RULES["plus_bonus"] * plus_of(book))


def describe(sid, rarity, plus=0):
    sp = SPELLS[sid]
    mult = POWER[rarity] * (1 + SPELL_RULES["plus_bonus"] * plus)
    return "%s Power x%.1f, %d focus, recharges in %d rounds. %s" % (
        sp["blurb"], sp["power"] * mult, sp["focus"], sp["cooldown"],
        "" if sp["element"] == "all" else "Element: %s." % elements.INFO[sp["element"]]["name"])


def is_book(iid):
    return ITEMS.get(iid, {}).get("kind") == "book"


# ---------------------------------------------------------------------------- slots and equipping
def slot_count(level):
    return sum(1 for need in SPELL_RULES["slot_levels"] if level >= need)


def next_slot_level(level):
    for need in SPELL_RULES["slot_levels"]:
        if level < need:
            return need
    return None


def equip(p, book):
    """Move a book from the pack into a spell slot. Returns (ok, message)."""
    if len(p.spells) >= slot_count(p.level):
        return False, "All your spell slots are full."
    if any(spell_id(b) == spell_id(book) for b in p.spells):
        return False, "You already have that spell equipped. Use a different one."
    if p.inventory.get(book, 0) < 1:
        return False, "You do not have that book."
    p.remove_item(book)
    p.spells.append(book)
    return True, "ok"


def unequip(p, index):
    book = p.spells.pop(index)
    p.inventory[book] = p.inventory.get(book, 0) + 1
    return book


def books_in_pack(p):
    return [i for i in p.inventory if is_book(i)]


# ---------------------------------------------------------------------------- making books
def make_book(g, element, rarity, plus=0):
    """Create a book (and put it in the pack). Common, unimproved books are plain stackable items."""
    base = "book_" + element
    p = g.player
    if rarity == "common" and plus == 0:
        p.add_item(base)
        return base
    inst = gear.make(base, rarity, g.rng, affixes=[])
    if plus:
        inst["plus"] = plus
        gear.rebuild(inst)
    gear.give(p, inst)
    return inst["id"]


def _consume(p, book):
    if gear.is_instance(book):
        gear.discard(p, book)
    else:
        p.remove_item(book)


# ---------------------------------------------------------------------------- crafting
def craft_info(tier):
    return SPELL_RULES["craft"][tier]


def craft_missing(g, element, tier):
    c = craft_info(tier)
    p = g.player
    out = []
    if p.gold < c["gold"]:
        out.append("%d more gold" % (c["gold"] - p.gold))
    have = p.inventory.get("essence_" + element, 0)
    if have < c["essence"]:
        out.append("%d more %s Essence" % (c["essence"] - have, elements.INFO[element]["name"]))
    if p.inventory.get("hollow_core", 0) < c["cores"]:
        out.append("%d more Hollow Core" % (c["cores"] - p.inventory.get("hollow_core", 0)))
    if c.get("heart"):
        hid = heart_id(element)
        have = p.inventory.get(hid, 0)
        if have < c["heart"]:
            out.append("%d more %s" % (c["heart"] - have, ITEMS[hid]["name"]))
    return out


def heart_id(element):
    """The Heart (a ring-5 material) the Grand Binding spends for a book of this element."""
    return "core_heart_" + element


def craft(g, element, tier):
    """Bind essences into a book of a random rarity. Returns the new book's id, or None if something is missing."""
    if craft_missing(g, element, tier):
        return None
    c = craft_info(tier)
    p = g.player
    p.gold -= c["gold"]
    p.remove_item("essence_" + element, c["essence"])
    if c["cores"]:
        p.remove_item("hollow_core", c["cores"])
    if c.get("heart"):
        p.remove_item(heart_id(element), c["heart"])
    r = g.rng.random() * sum(c["weights"].values())
    chosen = None
    for rarity, w in c["weights"].items():
        r -= w
        chosen = rarity
        if r <= 0:
            break
    return make_book(g, element, chosen)


# ---------------------------------------------------------------------------- combining
def combo_element(a, b):
    key = "+".join(sorted((a, b)))
    return SPELL_RULES["combos"][key]


def combine_outcomes(a, b):
    """The odds of combining two books: {"element", "mixed", "outcomes": [(rarity, probability)]} or None."""
    ea, eb = element_of(a), element_of(b)
    if "all" in (ea, eb):
        return None
    ra, rb = ORDER.index(rarity_of(a)), ORDER.index(rarity_of(b))
    hi, lo = max(ra, rb), min(ra, rb)
    top = len(ORDER) - 1
    probs = {}

    def add(tier, p):
        tier = max(0, min(top, tier))
        probs[tier] = probs.get(tier, 0.0) + p

    if ea == eb:
        if hi >= top:
            return None                       # a Godlike book of one element cannot be improved this way
        base = SPELL_RULES["tier_up"][ORDER[hi]]
        up = base * (0.5 + 0.5 * (lo + 1) / (hi + 1))
        down = SPELL_RULES["same_down"] if hi > 0 else 0.0
        add(hi + 1, up)
        add(hi - 1, down)
        add(hi, 1.0 - up - down)
        element, mixed = ea, False
    else:
        m = SPELL_RULES["mixed"]
        add(hi + 1, m["up"])
        add(hi, m["same"])
        add(hi - 1, m["down"])
        element, mixed = combo_element(ea, eb), True
    return {"element": element, "mixed": mixed,
            "outcomes": [(ORDER[t], round(p, 4)) for t, p in sorted(probs.items(), reverse=True) if p > 0]}


def known_recipes(g):
    return set(g.flags.get("recipes", []))


def can_combine(g, a, b):
    p = g.player
    if a == b and p.inventory.get(a, 0) < 2:
        return False
    return p.inventory.get(a, 0) >= 1 and p.inventory.get(b, 0) >= 1


def combine(g, a, b):
    """Merge two books from the pack. Returns {"book", "element", "rarity", "before", "mixed", "new_recipe"}."""
    odds = combine_outcomes(a, b)
    if odds is None or not can_combine(g, a, b):
        return None
    before = (rarity_of(a), rarity_of(b))
    r = g.rng.random()
    chosen = odds["outcomes"][-1][0]
    for rarity, prob in odds["outcomes"]:
        r -= prob
        if r <= 0:
            chosen = rarity
            break
    _consume(g.player, a)
    _consume(g.player, b)
    new_recipe = False
    if odds["mixed"]:
        key = "+".join(sorted((element_of(a), element_of(b))))
        recipes = g.flags.setdefault("recipes", [])
        if key not in recipes:
            recipes.append(key)
            new_recipe = True
    book = make_book(g, odds["element"], chosen)
    return {"book": book, "element": odds["element"], "rarity": chosen, "before": before, "mixed": odds["mixed"],
            "new_recipe": new_recipe}


def all_recipe_keys():
    return sorted(SPELL_RULES["combos"])


# ---------------------------------------------------------------------------- the apex spell
def apex_ready(g, books):
    """The apex needs six Godlike books, one of every element, and the apex recipe to be unlocked."""
    if not g.flags.get(SPELL_RULES["apex"]["needs_flag"]):
        return False
    if len(books) != len(elements.ELEMENTS) or len(set(books)) != len(books):
        return False
    if any(rarity_of(b) != "godlike" for b in books):
        return False
    return {element_of(b) for b in books} == set(elements.ELEMENTS)


def godlike_by_element(p):
    """One Godlike book for each element, if the pack has them all: [book ids], else None."""
    found = {}
    for b in books_in_pack(p):
        if rarity_of(b) == "godlike" and element_of(b) in elements.ELEMENTS:
            found.setdefault(element_of(b), b)
    return [found[e] for e in elements.ELEMENTS] if len(found) == len(elements.ELEMENTS) else None


def apex_heat(g):
    """How many attempts have failed since the apex last held (each one warms the next)."""
    return max(0, int(g.flags.get(HEAT_FLAG, 0)))


def apex_chance(g):
    """The chance the next attempt holds: the base chance plus `heat` for every failure so far, never above 1."""
    rules = SPELL_RULES["apex"]
    return min(1.0, round(rules["chance"] + rules.get("heat", 0.0) * apex_heat(g), 4))


def attempt_apex(g, books):
    """combine_apex with heat: the chance is `apex_chance(g)`, a failure adds a point of heat, a success resets it.

    Returns combine_apex's result plus "chance" (what it was rolled at), or None if the apex is not ready."""
    chance = apex_chance(g)
    res = combine_apex(g, books, chance=chance)
    if res is None:
        return None
    if res["kind"] == "apex":
        g.flags[HEAT_FLAG] = 0
    else:
        g.flags[HEAT_FLAG] = apex_heat(g) + 1
    res["chance"] = chance
    return res


def combine_apex(g, books, chance=None):
    """Six Godlike books into the apex spell, rarely. Failing costs you most of them but never everything.

    `chance` defaults to the base chance; the tower passes the heated one (see attempt_apex).
    Returns {"kind": "apex" | "buffed" | "downgraded", "book"}."""
    if not apex_ready(g, books):
        return None
    rules = SPELL_RULES["apex"]
    if chance is None:
        chance = rules["chance"]
    for b in books:
        _consume(g.player, b)
    r = g.rng.random()
    if r < chance:
        inst = gear.make("book_apex", "godlike", g.rng, affixes=[])
        gear.give(g.player, inst)
        return {"kind": "apex", "book": inst["id"]}
    pick = g.rng.choice(elements.ELEMENTS)
    if g.rng.random() < rules["buffed"]:
        return {"kind": "buffed", "book": make_book(g, pick, "legendary", plus=1), "element": pick}
    return {"kind": "downgraded", "book": make_book(g, pick, "legendary"), "element": pick}
