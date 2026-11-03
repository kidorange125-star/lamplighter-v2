"""The Magician's tower, as a menu: equip spells, craft books, buy books, combine books, the recipe log."""
from . import elements, forge_ui, rarity, spells, ui
from .content import ITEMS, SPELL_RULES, SPELLS
from .rarity import INFO as RARITY_INFO
from .ui import blank, say


def _mirelle(text):
    say('{hollow}Mirelle:{/} "%s"' % text)


def book_line(book, brief=False):
    sp = SPELLS[spells.spell_id(book)]
    el = elements.INFO[sp["element"]]
    sym = RARITY_INFO[spells.rarity_of(book)]["symbol"]
    plus = spells.plus_of(book)
    name = "{%s}%s{/}" % (el["colour"], sp["name"] + (" +%d" % plus if plus else ""))
    r = RARITY_INFO[spells.rarity_of(book)]
    out = "%s {%s}%s%s{/}" % (name, r["colour"], r["name"], (" " + sym) if sym else "")
    if not brief:
        out += " {grey}power x%.1f, %d focus, %d-round recharge{/}" % (
            sp["power"] * spells.power_mult(book), sp["focus"], sp["cooldown"])
    return out


def slots_line(g):
    p = g.player
    nxt = spells.next_slot_level(p.level)
    return "Spell slots: %d of %d used%s." % (
        len(p.spells), spells.slot_count(p.level), (" (another slot at level %d)" % nxt) if nxt else " (all slots unlocked)")


# ---------------------------------------------------------------------------- equipping (also the `spells` command)
def equip_menu(g):
    p = g.player
    note = ""
    while True:
        ui.clear()
        ui.rule("YOUR SPELLS", color="hollow")
        if note:
            say(note)
            blank()
        say("{grey}%s{/}" % slots_line(g))
        for i, b in enumerate(p.spells, 1):
            say("  {gold}[S%d]{/} %s" % (i, book_line(b)))
        if not p.spells:
            say("  {grey}Nothing equipped. Spell books come from the Magician: west of the Chapel of the Ember.{/}")
        blank()
        opts = []
        pack = spells.books_in_pack(p)
        if pack and len(p.spells) < spells.slot_count(p.level):
            opts.append(("Equip a book from your pack", "equip"))
        elif pack:
            opts.append(("{grey}Equip a book (no free slot){/}", "equip"))
        if p.spells:
            opts.append(("Put an equipped book back in your pack", "remove"))
        if not opts:
            say("{grey}You have no spell books.{/}")
            ui.pause()
            return
        i = ui.menu([o[0] for o in opts], prompt="Spells", cancel_label="Done")
        if i is None:
            return
        kind = opts[i][1]
        note = ""
        if kind == "equip":
            j = ui.menu(["%s x%d" % (book_line(b), p.inventory[b]) if p.inventory[b] > 1 else book_line(b) for b in pack],
                        prompt="Equip which", cancel_label="Back")
            if j is not None:
                ok, msg = spells.equip(p, pack[j])
                note = ("{bgreen}Equipped.{/}" if ok else "{grey}%s{/}" % msg)
        else:
            j = ui.menu([book_line(b) for b in p.spells], prompt="Remove which", cancel_label="Back")
            if j is not None:
                spells.unequip(p, j)
                note = "{bgreen}Back in your pack.{/}"


# ---------------------------------------------------------------------------- the tower
def menu(g):
    p = g.player
    note = ""
    while True:
        ui.clear()
        ui.rule("THE MAGICIAN'S TOWER", color="hollow")
        if note:
            say(note)
            blank()
        say("{grey}%s   Gems: %d{/}" % (slots_line(g), p.gems))
        for i, b in enumerate(p.spells, 1):
            say("  {gold}[S%d]{/} %s" % (i, book_line(b)))
        blank()
        opts = [("Equip or remove a spell book", "equip"), ("Craft a book from essences", "craft"),
                ("Buy a book", "buy"), ("Combine two books", "combine"), ("The recipe log", "log"),
                ("How spells work", "help")]
        if _arc().unlock_ready(g):
            opts.insert(0, ("{gold}Show her the Sixfold Chart{/}", "chart"))
        i = ui.menu([o[0] for o in opts], prompt="Magician", cancel_label="Leave")
        if i is None:
            return
        kind = opts[i][1]
        note = ""
        if kind == "chart":
            note = _arc().unlock_scene(g)
        elif kind == "equip":
            equip_menu(g)
        elif kind == "craft":
            note = _craft(g)
        elif kind == "buy":
            note = _buy(g)
        elif kind == "combine":
            note = _combine(g)
        elif kind == "log":
            _log(g)
        else:
            _help(g)


def _arc():
    """The apex-arc area module (the Sixfold Chart unlock). Imported late: area modules load while npcs is importing."""
    from .areas import arc
    return arc


def _help(g):
    ui.clear()
    ui.rule("HOW SPELLS WORK", color="hollow")
    say("A spell is a book. Equip books in your spell slots (you get more as you level), then cast them in a fight "
        "with {gold}S1{/}, {gold}S2{/} and so on. Spells cost focus and need a few rounds to recharge, and they grow with your Will.")
    say("Every enemy is {b}weak{/} to some elements and {b}resists{/} others. A spell it is weak to hits 50% harder; one it "
        "resists, half as hard. The weaknesses are shown on each enemy in a fight.")
    say("Books have rarity like gear: Common up to Godlike. Higher is stronger. {b}Craft{/} one by binding three Essences "
        "(dropped by monsters and bosses): the rarity is a gamble. Or {b}buy{/} one with gold or gems.")
    say("{b}Combine{/} two books and you get one back, by chance. The same element can rise a tier, stay, or slip one. "
        "Two different elements make a third, usually a tier lower. The odds are always shown first. Mirelle keeps a "
        "recipe log of what you have discovered.")
    say("Hearts, the rare cores that ring-5 monsters carry, buy a {b}Grand Binding{/}: the same craft with a real "
        "chance at a Godlike book.")
    if g.flags.get(SPELL_RULES["apex"]["needs_flag"]):
        heat = SPELL_RULES["apex"]
        say("{grey}The apex needs one Godlike book of every element. Mirelle has the order now. It starts at %d%% and each "
            "failed attempt warms the next by %d points.{/}" % (round(100 * heat["chance"]), round(100 * heat["heat"])))
    else:
        say("{grey}There is a sixth recipe, the apex, that needs one Godlike book of every element. Mirelle says the six "
            "wheels need a star-reader's order: ask in the Vigil.{/}")
    ui.pause()


def _log(g):
    ui.clear()
    ui.rule("THE RECIPE LOG", color="hollow")
    known = spells.known_recipes(g)
    keys = spells.all_recipe_keys()
    say("{grey}Two books of the same element make that element. Two different elements make:{/}")
    for k in keys:
        a, b = k.split("+")
        if k in known:
            say("  %s + %s  ->  %s" % (elements.tag(a), elements.tag(b), elements.tag(SPELL_RULES["combos"][k])))
        else:
            say("  {grey}%s + %s  ->  ???{/}" % (elements.INFO[a]["name"], elements.INFO[b]["name"]))
    say("{grey}Discovered %d of %d. Combine two different elements to learn one.{/}" % (len(known), len(keys)))
    ui.pause()


# ---------------------------------------------------------------------------- crafting and buying
def _craft(g):
    p = g.player
    labels = ["%s {grey}(you have %d essence%s){/}" % (
        elements.tag(e), p.inventory.get("essence_" + e, 0),
        (", %d heart" % p.inventory[spells.heart_id(e)]) if p.inventory.get(spells.heart_id(e), 0) else "")
        for e in elements.ELEMENTS]
    i = ui.menu(labels, prompt="Which element", cancel_label="Back")
    if i is None:
        return ""
    el = elements.ELEMENTS[i]
    tiers = list(SPELL_RULES["craft"])
    j = ui.menu([_craft_label(t, el) for t in tiers], prompt="Which binding", cancel_label="Back")
    if j is None:
        return ""
    tier = tiers[j]
    lack = spells.craft_missing(g, el, tier)
    if lack:
        return "{grey}You still need %s.{/}" % ", ".join(lack)
    heart = SPELL_RULES["craft"][tier].get("heart")
    if not ui.confirm(("Spend a %s to bind a %s book?" % (ITEMS[spells.heart_id(el)]["name"], elements.INFO[el]["name"]))
                      if heart else "Bind a %s book?" % elements.INFO[el]["name"]):
        return ""
    book = spells.craft(g, el, tier)
    _reveal(book, "The Heart sinks into the page, and the page goes very quiet..." if heart
            else "The essences swirl into a book...")
    return "{bgreen}Mirelle hands over %s.{/}" % rarity.label(book)


def _craft_label(tier, el):
    """One line of the binding menu. A binding that spends a Heart names it and gives the odds first."""
    c = SPELL_RULES["craft"][tier]
    total = sum(c["weights"].values())
    cost = "%d gold, %d %s Essence%s" % (
        c["gold"], c["essence"], elements.INFO[el]["name"], (", %d Hollow Core" % c["cores"]) if c["cores"] else "")
    if c.get("heart"):
        odds = ", ".join("%s %d%%" % (r.title(), round(100 * w / total))
                         for r, w in sorted(c["weights"].items(), key=lambda kv: -spells.ORDER.index(kv[0])))
        return "%s: %s. %s, %d %s." % (c.get("label", tier.title()), odds, cost, c["heart"],
                                       ITEMS[spells.heart_id(el)]["name"])
    return "%s: %s. %s" % (c.get("label", tier.title()), cost,
                           ", ".join("%s %d%%" % (r, round(100 * w / total)) for r, w in c["weights"].items()))


def _reveal(book, intro):
    ui.clear()
    ui.rule("A NEW BOOK", color="hollow")
    say("{b}%s{/}" % intro)
    r = spells.rarity_of(book)
    ui.sweep(forge_ui._stops(), spells.ORDER.index(r))
    say(book_line(book))
    say("{grey}%s{/}" % ITEMS[book]["desc"])
    blank()
    ui.pause()


def _buy(g):
    p = g.player
    rules = SPELL_RULES["buy"]
    opts = [("A Common book for %d gold" % rules["gold"]["price"], ("gold", "common"))]
    for r, price in rules["gems"].items():
        opts.append(("A %s book for %d gems" % (r.title(), price), ("gems", r)))
    i = ui.menu([o[0] for o in opts], prompt="Buy", cancel_label="Back")
    if i is None:
        return ""
    how, r = opts[i][1]
    price = rules["gold"]["price"] if how == "gold" else rules["gems"][r]
    if (p.gold if how == "gold" else p.gems) < price:
        return "{grey}You cannot afford that.{/}"
    j = ui.menu([elements.tag(e) for e in elements.ELEMENTS], prompt="Which element", cancel_label="Back")
    if j is None:
        return ""
    if how == "gold":
        p.gold -= price
    else:
        p.gems -= price
    book = spells.make_book(g, elements.ELEMENTS[j], r)
    return "{bgreen}You buy %s.{/}" % rarity.label(book)


# ---------------------------------------------------------------------------- combining
def _apex_hint(g):
    """(menu hint, Mirelle's line) for the locked apex recipe, by what the player still lacks (arc.unlock_missing)."""
    from . import town
    lack = _arc().unlock_missing(g)
    if "the Sixfold Chart" in lack:
        return ("ask in the Vigil",
                "Six Godlike tomes, one of every element. I can feel it from here. But the six wheels need a "
                "star-reader's order, and I do not have it. Ask in the Vigil. Keep them safe.")
    loft = " Hale is in the loft next door." if town.is_built(g, _arc().ALMANAC) else ""
    if "Hale to read it" in lack:
        return ("take the chart to whoever reads the stars",
                "That is a star-chart. I cannot read the order. Take it to whoever reads the stars.%s" % loft)
    return ("Hale has read it, but he needs a home in Hollowmere",
            "Hale has read it? Then he knows the order, and he cannot climb my stairs from the Vigil. "
            "Find him a roof in Hollowmere, close enough to walk.")


def _combine(g):
    p = g.player
    ready = spells.godlike_by_element(p)
    pack = spells.books_in_pack(p)
    opts = []
    if len(pack) >= 2 or any(p.inventory[b] >= 2 for b in pack):
        opts.append(("Combine two books", "two"))
    if ready:
        if g.flags.get(SPELL_RULES["apex"]["needs_flag"]):
            opts.append(("{gold}Attempt the apex: six Godlike books into one{/}", "apex"))
        elif _arc().unlock_ready(g):
            opts.append(("{gold}The apex recipe: show her the Sixfold Chart first{/}", "chart"))
        else:
            opts.append(("{grey}The apex recipe (you have the six Godlike books, but the six wheels need a star-reader's "
                         "order: %s){/}" % _apex_hint(g)[0], "locked"))
    if not opts:
        return "{grey}You need two spell books to combine.{/}"
    if len(opts) == 1:
        k = opts[0][1]
    else:
        idx = ui.menu([o[0] for o in opts], prompt="Combine", cancel_label="Back")
        if idx is None:
            return ""
        k = opts[idx][1]
    if k == "locked":
        _mirelle(_apex_hint(g)[1])
        return ""
    if k == "chart":
        return _arc().unlock_scene(g)
    if k == "apex":
        return _apex(g, ready)
    # pick the two books
    labels = ["%s%s" % (book_line(b), (" x%d" % p.inventory[b]) if p.inventory[b] > 1 else "") for b in pack]
    a = ui.menu(labels, prompt="First book", cancel_label="Back")
    if a is None:
        return ""
    b = ui.menu(labels, prompt="Second book", cancel_label="Back")
    if b is None:
        return ""
    A, B = pack[a], pack[b]
    if not spells.can_combine(g, A, B):
        return "{grey}You need two separate books for that.{/}"
    odds = spells.combine_outcomes(A, B)
    if odds is None:
        return "{grey}Those cannot be combined. A Godlike book is as good as that element gets.{/}"
    ui.clear()
    ui.rule("COMBINE", color="hollow")
    say("%s  +  %s" % (book_line(A, True), book_line(B, True)))
    known = spells.known_recipes(g)
    key = "+".join(sorted((spells.element_of(A), spells.element_of(B))))
    if odds["mixed"] and key not in known:
        say("{b}Result:{/} a spell of an element you have not discovered yet {grey}(???){/}")
    else:
        say("{b}Result:{/} a %s book" % elements.tag(odds["element"]))
    for r, prob in odds["outcomes"]:
        say("   %3d%%  %s" % (round(prob * 100), rarity.describe_name(r)))
    say("{grey}Both books are used up whatever happens.{/}")
    if not ui.confirm("Combine them?"):
        return ""
    res = spells.combine(g, A, B)
    _reveal(res["book"], "The two books fold into one...")
    extra = ""
    if res["new_recipe"]:
        extra = " {gold}New recipe discovered!{/}"
    return "{bgreen}You get %s.{/}%s" % (rarity.label(res["book"]), extra)


def _apex(g, books):
    ui.clear()
    ui.rule("THE APEX", color="bmagenta")
    say("Six Godlike books, one of every element, bound into a single spell that holds them all.")
    rules = SPELL_RULES["apex"]
    heat = spells.apex_heat(g)
    if heat:
        say("{b}Chance of success: %d%% + %d%% heat = %d%%.{/}" % (
            round(100 * rules["chance"]), round(100 * rules["heat"] * heat), round(100 * spells.apex_chance(g))))
        say("{grey}Every failure warms the binding by %d points. It keeps the heat until it holds.{/}"
            % round(100 * rules["heat"]))
    else:
        say("{b}Chance of success: %d%%.{/}" % round(100 * rules["chance"]))
        say("{grey}Every failure warms the next attempt by %d points, until one holds.{/}" % round(100 * rules["heat"]))
    say("{grey}If it fails, all six are lost, but not for nothing: you get one Legendary book back, slightly stronger "
        "(%d%% of failures), or one of your books back, brought down to Legendary.{/}" % round(100 * rules["buffed"]))
    if not ui.confirm("Risk all six Godlike books?"):
        return ""
    res = spells.attempt_apex(g, books)
    book = res["book"]
    if res["kind"] == "apex":
        _reveal(book, "The six books burn white, together...")
        return "{gold}It held. You have the apex spell: %s.{/}" % rarity.label(book)
    _reveal(book, "The books burn, and one survives...")
    if res["kind"] == "buffed":
        return "{bgreen}The binding failed, but one book came out stronger: %s.{/}" % rarity.label(book)
    return "{grey}The binding failed. One book comes back, brought down to Legendary: %s.{/}" % rarity.label(book)
