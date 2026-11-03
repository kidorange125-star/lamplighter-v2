"""The Frostfair (ring 5, area A): a midwinter Lending Fair held in a breath that never let go.

Aldric borrowed the flame of the Great Lantern "for a winter". Lamp-Master Hobb swore to hold the Fair until it came
home, and held it for fifty years. His wife Marit kept one small lamp lit in the Warden's Booth so that someone would be
there when he did. The wrongness here is waiting; the player's tool is warmth. See docs/M6-SPEC.md section 9.

Imports of the game's own modules are lazy: npcs imports every area module while it is still being imported.
"""

REGION = "The Frostfair"
ANNEX = "The Fair Below"
POSTS = ("ff_midway", "ff_lamp_row", "ff_sculptors_row")
STALL = "ff_fair_stall"


# ============================================================================ small helpers
def _built(g):
    from .. import town
    return town.is_built(g, STALL)


def _invited(g):
    from .. import town
    return town.is_invited(g, STALL)


def _signal(g):
    """The Court's answer has been seen: by the beacon itself, or by a save that lit the Court before M6 existed."""
    return bool(g.flags.get("ff_signal_seen") or g.flags.get("beacon_Ember Court"))


def _posts_lit(g):
    return sum(1 for r in POSTS if g.flags.get("lit_" + r))


# ============================================================================ the Court's answer
def court_beacon(g):
    from ..ui import narrate, say
    g.flags["ff_signal_seen"] = True
    narrate("{sky}Far to the west, across the dark, a second light answers the Court's. It is blue-white and cold, and "
            "it is not a beacon. It is a lantern held up very high by someone who has been waiting a long time to "
            "see another one.{/}")
    say("{grey}(Hesk will want to know about the frost at the North Gate.){/}")


def frostfair_beacon(g):
    from ..ui import narrate, say
    g.flags["ff_thaw"] = True
    narrate("{gold}Then, one by one, the six hundred lamps on Lantern Row ignite. Not with ghost-fire: with plain "
            "yellow flame, each its own small colour. All over the Fair, frozen hawkers and skaters and sculptors set "
            "down what they are holding and begin, slowly and with great dignity, to walk home. The frost on the "
            "stones turns to dew. You hear someone laugh. It is spring.{/}")
    narrate("In Hollowmere, three streets from the gate, the ice on Maeve's pump cracks and runs.")
    say("{grey}(The hatch beneath the oil casks in the Ice Cellars has thawed. Marit will want to hear that the Fair "
        "is warm.){/}")


AFTER_BEACON = {
    "Ember Court": court_beacon,
    REGION: frostfair_beacon,
}


# ============================================================================ entering rooms
def enter_frost_road(g, first):
    from ..ui import narrate
    if first:
        narrate("The air stops being air. It is the stillness of a held breath. A hand-lantern hangs on every post, "
                "each tagged with a family's name. Not one is lit.")
    return False


def _gate_opened(g):
    from ..ui import narrate
    narrate("The lamps on the gate do not light. They lean toward your lantern, and for one moment each of them holds "
            "a small, steady, borrowed gold.")


def enter_wintering(g, first):
    from .. import npcs, powerroll
    from ..ui import blank, narrate
    if g.flags.get("ff_lampmaster_dead"):
        return False

    def prologue():
        blank()
        if not g.flags.get("ff_met_hobb"):
            g.flags["ff_met_hobb"] = True
            narrate("The square opens like an indrawn breath. At its centre stands a lamp-post as tall as a church, "
                    "and at the foot of it a man in a coat made of hung lamps, with a long pole across his "
                    "shoulders, holding the Great Lantern in his arms like a child.")
            npcs.line("Hobb", "Admission is one story or one coin. Which is it, friend? The Fair is open until "
                              "spring.", "sky")
        else:
            narrate("Hobb sets his lamp-pole across his shoulders.")
            npcs.line("Hobb", "Still open, friend. Still open.", "sky")

    return powerroll.boss_scene(g, "ff_lampmaster", "ff_lampmaster_dead", "ff_great_gate", _hobb_won,
                                intro="Somewhere, a music box begins.", prologue=prologue)


def _hobb_won(g, power):
    from .. import powerroll
    from ..ui import blank, narrate, say
    blank()
    narrate("Hobb sets the Great Lantern down, very gently, the way you set down something that is finally allowed to "
            "sleep. 'Is it spring?' he asks. And he looks at you, and it is Hobb for one breath, and it is the "
            "kindest face in the world. 'Oh. Tell Marit I held it. Tell her I held it as long as I could.' He is "
            "frost on the cobbles, and then he is not even that. The Great Lantern stands in the square, empty and "
            "clear as glass. The beacon bowl is cold.")
    gems = {3: 1, 4: 2}.get(powerroll.band_index(power), 0)
    if gems and not g.flags.get("ff_gems_band"):
        g.flags["ff_gems_band"] = True
        g.player.gems += gems
        say("{sky}+%d gems{/} {grey}(he was %s){/}" % (gems, powerroll.band(power)[0].lower()))
    say("{grey}(Type {gold}light{/}{grey} to relight it.){/}")


ENTER = {
    "ff_frost_road": enter_frost_road,
    "ff_wintering": enter_wintering,
}

UNLOCK = {
    ("ff_great_gate", "w"): lambda g: _gate_opened(g),
}


def ringmaster_dead(g):
    from .. import events
    from ..ui import narrate, say
    narrate("The Ringmaster takes off his hat. 'And that,' he says, 'is the show.' The carousel coasts to a stop for "
            "the first time in fifty years. In the silence you can hear the music box wind down to its last note, "
            "and the last note is a kind one.")
    events.give_once(g, "ff_wardens_key")
    say("{grey}(The Warden's key was on his watch-chain. The booth north of Lantern Row is open to you.){/}")
    if not g.flags.get("ff_gems_ringmaster"):
        g.flags["ff_gems_ringmaster"] = True
        g.player.gems += 2
        say("{sky}+2 gems{/} {grey}(the first time the show has ended){/}")


AFTER_FIXED = {
    "ff_ringmaster_dead": ringmaster_dead,
}

BOSS_TIPS = {
    "ff_wintering": "You see his strength before you decide, and you can step back or run for free. Fire and Earth are "
                    "strong, Ice and Water useless, and the Midwinter field dims fire and flares. Kill the Hung Lamps "
                    "he calls (they steal oil) and guard Midwinter Toll and Frozen Hour. Keep 40 or more oil: Lend Me "
                    "Yours drains it.",
    "ff_carousel": "Fire and Shadow hurt him. Kill the skaters he calls first. He is an elite: no running.",
}


# ============================================================================ objectives
def OBJECTIVES(g, add):
    f = g.flags
    if f.get("beacon_Ember Court") and not f.get("beacon_" + REGION):
        if "ff_frost_road" not in g.visited:
            add("A cold light answered the Court's beacon, west of the North Gate. Open the frost road",
                "ff_frost_road")
        elif _posts_lit(g) < 3:
            room = next(r for r in POSTS if not f.get("lit_" + r))
            add("Relight the Lending Posts (%d of 3): the Midway, Lantern Row, Sculptors' Row" % _posts_lit(g), room)
        elif not f.get("ff_lampmaster_dead"):
            add("Face the Lamp-Master Hobb in the Wintering Square", "ff_wintering")
        else:
            add("Light the Great Lantern", "ff_wintering")
    if "ff_fair_gate" in g.visited and not f.get("ff_ringmaster_dead"):
        add("The Ringmaster of Rime wears the Warden's Booth key in the carousel", "ff_carousel", True)
    if f.get("ff_lampmaster_dead") and not _built(g):
        if _invited(g):
            add("Marit Ostrand will move to Hollowmere once Joss has built her stall", "yard", True)
        else:
            add("Marit Ostrand in the Warden's Booth would move to Hollowmere. Ask her, then see Joss",
                "ff_wardens_booth", True)
    if g.player.has_item("ff_cellar_key") and "ff_ice_cellars" not in g.visited:
        add("The Ice Cellars: Marit gave you a key, and the sleepers want you calm", "ff_skate_pond", True)


# ============================================================================ Hollowmere reacts
def _hesk_frost(g):
    from .. import npcs
    f = g.flags
    if f.get("ff_thaw"):
        npcs.line("Hesk", "The snow's gone. There's a smell of woodsmoke where the drift was. I almost cried at my own "
                          "gate.", "bone")
        f["ff_hesk_thawed"] = True
    else:
        npcs.line("Hesk", "A hand's breadth a day. It's not winter, it's wanting. Whatever's out there, it's looking at "
                          "us. I can feel it looking at the back of my neck.", "bone")
    f["ff_hesk_told"] = True


def hesk_topics(g):
    f = g.flags
    if not _signal(g):
        return []
    if not f.get("ff_hesk_told") or (f.get("ff_thaw") and not f.get("ff_hesk_thawed")):
        return [("Ask about the frost on the gate", _hesk_frost)]
    return []


TOPICS = {"hesk": hesk_topics}
EXTRA_NEWS = {"hesk": lambda g: bool(_signal(g) and not g.flags.get("ff_hesk_told"))}


def RUMOURS(g):
    f = g.flags
    out = []
    if _signal(g) and not f.get("ff_thaw"):
        out.append("The pump froze solid last night. In October. Then it cracked, and it ran hot for an hour.")
    if f.get("ff_thaw") and not _built(g):
        out.append("Somebody's been hanging paper lanterns on the Hearth Stall. I don't know who. I like it.")
    return out


SELLS = {
    "odo": lambda g: ["ff_rime"] if g.flags.get("ff_lampmaster_dead") else [],
    "ff_marit": lambda g: list(MARIT_WARES) if _built(g) else [],
}
PRICES = {"ff_rime": 70}


# ============================================================================ people
NPCS = {
    "ff_dunmore": {"name": "Dunmore Pike", "aliases": ["dunmore", "pike", "toll-keeper", "tollkeeper", "toll keeper"],
                   "shop": True,
                   "desc": "A round man in a toll-keeper's coat, cheerful, a little glassy-eyed, writing in a book that "
                           "is mostly the same line."},
    "ff_marit": {"name": "Marit Ostrand", "aliases": ["marit", "ostrand", "fairwarden", "old woman"], "shop": True,
                 "where": lambda g: "ff_stall" if _built(g) else None,
                 "desc": "A small, upright old woman with a boat-hook held like a pike and a hand-lamp the size of a "
                         "thimble on a cord round her neck."},
}

STOCK = {
    "ff_dunmore": ["oil", "strong_draught", "honeycake", "ff_cider", "ff_fairlight", "firepot", "smokebomb", "tonic"],
    "ff_marit": [],                  # her wares come with the stall: see SELLS
}

MARIT_WARES = ["ff_fairlight", "ff_cider", "oil", "essence_ice", "essence_light", "honeycake"]

PRESENT = {"ff_marit": lambda g: not _built(g)}


def _marit_news(g):
    f = g.flags
    if not f.get("ff_marit_met"):
        return True
    if f.get("ff_lampmaster_dead") and not _invited(g) and not _built(g):
        return True
    return bool(f.get("ff_thaw") and not f.get("ff_flame_given"))


NEWS = {"ff_marit": _marit_news}


def talk_ff_dunmore(g):
    from .. import npcs
    from ..ui import narrate, say
    line, f = npcs.line, g.flags
    if f.get("ff_thaw"):
        if not f.get("ff_dunmore_closed"):
            f["ff_dunmore_closed"] = True
            line("Dunmore", "Closing time, is it? ...Well. I'll sweep up.", "gold")
            line("Dunmore", "Someone has to be here to say it's over. I think I'll keep the booth. It's a good booth.",
                 "gold")
        else:
            line("Dunmore", "Mind the puddles. There's a lot of thaw about.", "gold")
    elif not f.get("talked_ff_dunmore"):
        narrate("The man in the toll-booth does not look up. His pen is moving. He is writing, in a book that is "
                "mostly the same line, and he is smiling, very slightly, at nothing.")
        line("Dunmore", "Two coins, or one story. Mind the pond, the skaters are very good, and very cold.", "gold")
        say("{grey}(He takes your coins, or your story, and writes it down. He is happy to sell you things as well.){/}")
    else:
        line("Dunmore", "Two coins, or one story. Third night of the Fair, you know. Third night!", "gold")
    while True:
        thawed = f.get("ff_thaw")
        opts = [("Trade {grey}(he sells supplies){/}", "trade"), ("Ask about the Fair", "fair")]
        if not thawed:
            opts += [("Ask what is still going on", "posts"), ("Ask about the Warden's Booth", "booth")]
        k = npcs.topic_menu(opts)
        if k is None:
            line("Dunmore", "Mind the puddles." if thawed else "Mind the pond.", "gold")
            return
        if k == "trade":
            npcs.trade(g, "ff_dunmore")
        elif k == "fair":
            line("Dunmore", "The Lending Fair! Midwinter, every year. Every household hangs its lamp on the poles, and "
                            "at dusk the Lamp-Master lights the Great Lantern, and the Great Lantern lights them all. "
                            "At dawn each family takes its lamp home, lit. Bonniest sight in the north.", "gold")
            if thawed:
                line("Dunmore", "He's off home, then, the Lamp-Master? Good. He never did put his feet up.", "gold")
            else:
                line("Dunmore", "This year the Great Lantern's gone on a little holiday, but he'll be back by spring.",
                     "gold")
        elif k == "posts":
            line("Dunmore", "There were three Lending Posts, where folk hung their lamps for the Lantern to light from. "
                            "The Cider Post, the Row Post, and the Sculptors'. I don't go that far. My knees.", "gold")
        else:
            line("Dunmore", "Someone's keeping a stove lit up there, I'd swear to it. Nobody lights a stove in fifty "
                            "years by accident.", "gold")


def _marit_aldric(g):
    from .. import ui
    from ..npcs import line
    from ..ui import say
    k = ui.menu(["\"Dead. Or what was left of him, and then not even that.\"",
                 "\"He's still walking.\" {grey}(a kindness){/}"], prompt="Say", cancel_label="Say nothing yet")
    if k is None:
        return
    if k == 0:
        say("{grey}You: Dead. Or what was left of him, and then not even that.{/}")
        line("Marit", "Then he never came back for the lantern because he couldn't. ...Fifty years I've been angry at "
                      "a man for being rude, and he was only gone.", "bone")
    else:
        say("{grey}You: He's still walking.{/}")
        line("Marit", "Good. Let him walk. It's the only thing he was ever good at.", "bone")
    g.flags["ff_marit_told"] = True


def _marit_hobb_held(g):
    from ..npcs import line
    from ..ui import narrate
    line("Marit", "He said that. ...Of course he did.", "bone")
    narrate("She walks out into the square, puts her palm flat on the cold base of the Great Lantern, and says, "
            "quietly, 'You can go home, love.' Her hand glows.")
    g.flags["ff_marit_hobb"] = True


def _marit_flame(g):
    from .. import events
    from ..npcs import line
    from ..ui import narrate
    narrate("She opens her tiny hand-lamp's shutter, touches your lantern's wick, and the flame that climbs onto it "
            "is smaller and warmer than yours.")
    line("Marit", "That's not a loan. Write it down, if you must. I'm told it matters.", "bone")
    events.give_once(g, "ff_given_flame")
    g.flags["ff_flame_given"] = True


def talk_ff_marit(g):
    from .. import dealer, events, npcs
    from ..ui import narrate, say
    line, f = npcs.line, g.flags
    if not f.get("ff_marit_met"):
        f["ff_marit_met"] = True
        narrate("Beside a small stove, an old woman rises with a boat-hook held like a pike. 'Hobb?' she says, and "
                "then, seeing you: 'No. No, of course not. He'd have knocked.'")
        line("Marit", "The cellars have the Fair's oil. It's been fifty years; it'll be sweet as the day. Take what "
                      "you need and leave the barrels square.", "bone")
        events.give_once(g, "ff_cellar_key")
        say("{grey}(The key opens the trapdoor in the bank of the Skating Pond. The sleepers below stir if your heart "
            "is racing: come with Dread under 25.){/}")
    elif f.get("ff_thaw") and not f.get("ff_flame_given"):
        pass
    elif _built(g):
        line("Marit", "Mind the step. Kettle's on, and the awning is dry.", "bone")
    else:
        line("Marit", "Kettle's on. The cot is the only chair; I'd sit, if I were you.", "bone")
    if f.get("ff_thaw") and not f.get("ff_flame_given"):
        _marit_flame(g)
    if _built(g) and f.get("ff_gift_day") != dealer.today():
        f["ff_gift_day"] = dealer.today()
        line("Marit", "Day's candle. Don't tell me you don't need it. Everyone needs it.", "bone")
        g.give("ff_fairlight")
    while True:
        opts = []
        if _built(g):
            opts.append(("Trade {grey}(fair-lights, cider, a little oil){/}", "trade"))
        if not f.get("ff_marit_told"):
            opts.append(("Tell her what happened to Aldric", "aldric"))
        opts.append(("Ask about Hobb", "hobb"))
        opts.append(("Ask about the Great Lantern", "lantern"))
        if f.get("ff_lampmaster_dead") and not f.get("ff_marit_hobb"):
            opts.append(("Tell her Hobb held it", "held"))
        if f.get("ff_lampmaster_dead") and not _built(g):
            opts.append(("Ask her to come to Hollowmere", "invite"))
        k = npcs.topic_menu(opts)
        if k is None:
            line("Marit", "Go carefully. Come back warm.", "bone")
            return
        if k == "trade":
            npcs.trade(g, "ff_marit")
        elif k == "aldric":
            _marit_aldric(g)
        elif k == "hobb":
            line("Marit", "My husband. He couldn't put a thing down once he'd picked it up. It's the best thing about "
                          "him and it's what did for him.", "bone")
        elif k == "lantern":
            line("Marit", "It burned the lamps of six hundred households, every winter, and gave each one back at "
                          "dawn. I wrote their names. Every one. In the book in the Lending Tent, if you ever want to "
                          "read them.", "bone")
        elif k == "held":
            _marit_hobb_held(g)
        else:
            npcs._invite_scene(g, STALL, "Marit",
                               "A market? With stalls? ...Hobb would have loved a market. Tell your builder I'll want "
                               "a counter I can lean on.", "",
                               "Tell Joss, in the yard on Market Row. I'll want a counter I can lean on.")


# ============================================================================ validator
def CHECK():
    """The rules every area obeys (docs/M6-SPEC.md 2.3), asserted for this area's own data."""
    from ..content import ENEMIES, ROOMS
    errs = []
    for eid, e in ENEMIES.items():
        if not eid.startswith("ff_") or "@" in eid:
            continue
        if "hollow" in e.get("tags", []) and "light" in e.get("weak", []):
            errs.append("enemy %s is a hollow weak to light" % eid)
        if not e.get("desc"):
            errs.append("enemy %s has no desc" % eid)
        moves = list(e.get("moves", []))
        for ph in e.get("phases", []):
            moves += ph.get("moves", [])
        for m in moves:
            if m.get("kind") in ("heavy", "charge") and not m.get("tell"):
                errs.append("enemy %s: move %s has no tell" % (eid, m.get("name")))
        if "roll" in e and len(e["roll"].get("flavour", [])) != 5:
            errs.append("enemy %s: a rolled boss needs 5 lines of flavour" % eid)
    for rid, r in ROOMS.items():
        if not rid.startswith("ff_"):
            continue
        if not r.get("desc") or not r.get("features"):
            errs.append("room %s needs a desc and features" % rid)
        groups = r.get("enc", {}).get("groups", [])
        if groups:
            total = sum(w for _, w in groups)
            single = sum(w for grp, w in groups if len(grp) == 1)
            if any(len(grp) > 2 for grp, _ in groups):
                errs.append("room %s: a group is bigger than two" % rid)
            if r["region"] in (REGION, ANNEX) and single * 100 < 40 * total:
                errs.append("room %s: single-enemy groups are under 40%% of the weight" % rid)
    return errs
