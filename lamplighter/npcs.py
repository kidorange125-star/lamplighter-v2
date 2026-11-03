"""People of Hollowmere and below: who they are, what they say, what they sell."""
from . import areas, dealer, forge_ui, magic_ui, postgame, rarity, spells, town, ui
from .ui import say, blank, narrate
from .content import BUILDINGS, ITEMS


def line(who, text, color="sky"):
    say('{%s}%s:{/} "%s"' % (color, who, text))


def present_wren(g):
    if g.flags.get("wren_home"):
        return "tavern"
    return None


NPCS = {
    "orrin": {"name": "Guildmaster Orrin", "aliases": ["guildmaster", "master", "old man"],
              "desc": "Orrin taught you to trim a wick when you were six. He is very old now, and since the sun went "
                      "out he has not left his bed. His eyes are still sharp."},
    "maeve": {"name": "Old Maeve", "aliases": ["barkeep", "innkeeper"], "shop": True,
              "desc": "Maeve runs the Drowned Moth and has done since before you were born. She is wiping a clean "
                      "glass over and over and watching the door."},
    "hesk": {"name": "Hesk the gatekeeper", "aliases": ["gatekeeper", "guard"],
             "desc": "Broad, grey-haired, a boar-spear on her shoulder. She has held this gate alone for a month."},
    "ilse": {"name": "Sister Ilse", "aliases": ["sister", "nun", "priest"], "shop": True,
             "desc": "A young woman in an ash-grey habit, with dark rings under her eyes and oil on her fingers."},
    "brann": {"name": "Brann the smith", "aliases": ["smith", "blacksmith"], "shop": True,
              "desc": "Brann is enormous and gentle. He talks to his hammer more than to people."},
    "oskar": {"name": "Oskar the ferryman", "aliases": ["ferryman", "boatman"],
              "desc": "A thin man in a sou'wester, so wrapped in oilcloth you can barely see his face."},
    "mirelle": {"name": "Mirelle the magician", "aliases": ["magician", "mirelle", "mage"],
                "desc": "A young woman with ink on her cuffs and a pencil through her hair, in a coat with too many "
                        "pockets. Something in one of them is humming."},
    "joss": {"name": "Joss the builder", "aliases": ["builder"],
             "desc": "A broad, patient man in a leather apron, with a pencil behind each ear and a third in his hand. "
                     "He measures everything twice and says so."},
    "odo": {"name": "Odo the netmaker", "aliases": ["netmaker", "salvager"], "shop": True,
            "where": lambda g: "salvage_stall" if town.is_built(g, "salvage_stall") else None,
            "desc": "A wiry man with a net-needle behind his ear and the careful eyes of someone who has hidden in a "
                    "loft for a long time."},
    "dagna": {"name": "Dagna the miner", "aliases": ["miner"],
              "where": lambda g: "strongroom" if town.is_built(g, "strongroom") else None,
              "desc": "Square, grey-haired and soot-streaked, with a pick-hammer she hasn't put down in a week."},
    "wizard": {"name": "Ysolde the wizard", "aliases": ["wizard", "magician", "ysolde"],
               "desc": "A tall, narrow woman in a coat of faded star-charts, with ink to the elbow and the patient "
                       "expression of someone who has already seen how this goes."},
    "corvin": {"name": "Corvin the hermit", "aliases": ["hermit", "old man"], "shop": True,
               "where": lambda g: "hearth_stall" if town.is_built(g, "hearth_stall") else None,
               "desc": "An old man in a coat sewn from black feathers. He has lived in the wood for forty years and "
                       "seems mildly surprised the dark bothers anyone."},
    "tallow": {"name": "Tallow", "aliases": ["merchant", "candle", "wax"], "shop": True,
               "desc": "A merchant made of candle-wax, with a lit wick for hair. Their face is soft and slightly "
                       "melted, and their smile is genuine."},
    "pell": {"name": "Pell the doorward", "aliases": ["doorward", "gatekeeper", "pell", "keeper"], "shop": True,
             "desc": "A lean, tired woman in the Court's livery, a ring of keys at her hip and a ledger under her arm. "
                     "She has been standing at this door for a long time, and has not been told she can stop."},
    "tamsin": {"name": "Tamsin the smith", "aliases": ["smith", "tamsin"],
               "where": lambda g: "ember_smithy" if town.is_built(g, "ember_smithy") else None,
               "desc": "A young woman with soot to the elbow and a burn-scarred forearm, holding a hammer the way "
                       "other people hold a rail on a ship."},
    "dealer": {"name": "The Darkness Dealer", "aliases": ["dealer", "darkness dealer", "trader"],
               "where": dealer.where,
               "desc": "A shape in a black coat with its hood pulled low, sitting behind a folding table. You have "
                       "never seen its face, and it seems to find that restful."},
    "wren": {"name": "Wren", "aliases": ["girl", "daughter"], "where": present_wren,
             "desc": "Maeve's daughter, twelve years old, wrapped in a blanket by the fire. There is a yellow ribbon "
                     "in her hair again. She watches your lantern the way you used to watch Orrin's."},
}


def is_present(g, nid):
    """Is this person at the place the room data puts them? Residents leave when their building is finished."""
    fn = _AREA_PRESENT.get(nid)
    if fn:
        return bool(fn(g))
    if nid == "corvin":
        return not town.is_built(g, "hearth_stall")
    if nid == "odo":
        return bool(g.flags.get("reeve_dead")) and not town.is_built(g, "salvage_stall")
    if nid == "dagna":
        return bool(g.flags.get("golem_dead")) and not town.is_built(g, "strongroom")
    if nid == "tamsin":
        return bool(g.flags.get("steward_dead")) and not town.is_built(g, "ember_smithy")
    return True


_speaker = [None]
_speaker_g = [None]


def talk_header():
    ui.rule("Talking with %s" % NPCS[_speaker[0]]["name"], color="sky")


def talk(g, nid):
    _speaker[0] = nid
    _speaker_g[0] = g
    talk_header()
    globals()["talk_" + nid](g)
    g.flags["talked_" + nid] = True


def has_news(g, nid):
    """True when this person has something new to say, so the area screen can suggest talking."""
    fn = _AREA_NEWS.get(nid)
    if fn:
        return bool(fn(g))
    return _core_news(g, nid) or areas.extra_news(g, nid)


def _core_news(g, nid):
    f = g.flags
    if nid == "orrin":
        return (g.quest("main") in (-1, 0) or (g.shards() == 3 and not f.get("orrin_ring"))
                or (any(f.get("read_" + x) for x in ("page4", "page5")) and not f.get("orrin_aldric")))
    if nid == "maeve":
        return g.quest("wren") == -1
    if nid == "hesk":
        return not f.get("hesk_met")
    if nid == "ilse":
        return g.quest("petals") == -1 or (g.quest("petals") == 0 and g.player.inventory.get("moonpetal", 0) >= 3)
    if nid == "brann":
        return not f.get("brann_met") or g.quest("starsteel") in (-1, 1)
    if nid == "oskar":
        return not f.get("talked_oskar")
    if nid == "corvin":
        return (not f.get("corvin_met") or (g.quest("corvin") == 0 and g.player.has_item("wolf_pelt"))
                or (f.get("mother_dead") and not town.is_invited(g, "hearth_stall") and not town.is_built(g, "hearth_stall")))
    if nid == "joss":
        return bool(town.available(g))
    if nid == "odo":
        return bool(f.get("reeve_dead")) and not town.is_invited(g, "salvage_stall") and not town.is_built(g, "salvage_stall")
    if nid == "dagna":
        return bool(f.get("golem_dead")) and not town.is_invited(g, "strongroom") and not town.is_built(g, "strongroom")
    if nid == "pell":
        return not f.get("pell_met") or (f.get("queen_dead") and not f.get("pell_after"))
    if nid == "tamsin":
        return bool(f.get("steward_dead")) and not town.is_invited(g, "ember_smithy") and not town.is_built(g, "ember_smithy")
    if nid == "dealer":
        return not f.get("dealer_met")
    if nid == "wizard":
        return not f.get("wizard_met")
    if nid == "mirelle":
        return not f.get("mirelle_met")
    if nid == "tallow":
        return not f.get("tallow_met")
    if nid == "wren":
        return not f.get("talked_wren") or (g.quest("wayposts") == "done" and not f.get("wren_ready"))
    return False


# ---------------------------------------------------------------------------- helpers
def topic_menu(options):
    """options: list of (label, key). Returns key or None. Each answer gets a fresh screen.

    Area modules can add topics to any speaker (areas.topics); choosing one runs its handler on the same screen
    and shows the menu again, so the caller only ever sees its own keys."""
    g = _speaker_g[0]
    while True:
        extra = areas.topics(g, _speaker[0]) if g is not None and _speaker[0] else []
        labels = [o[0] for o in options] + [e[0] for e in extra]
        blank()
        i = ui.menu(labels, prompt="Say", cancel_label="Leave")
        if i is None:
            return None
        ui.clear()
        talk_header()
        say("{grey}You: %s{/}" % ui._TAG.sub("", labels[i]))
        blank()
        if i < len(options):
            return options[i][1]
        extra[i - len(options)][1](g)


# ---------------------------------------------------------------------------- Orrin
def talk_orrin(g):
    p = g.player
    if g.quest("main") in (-1, 0):
        narrate("Orrin opens his eyes when your lantern comes near.")
        line("Orrin", "There you are. My last apprentice. Sit. No, don't fuss with the blankets. Listen.", "amber")
        line("Orrin", "Forty days without a sunrise. You know why, though nobody says it. The Lightwell under the "
                      "hill is dying, and when it goes out, the sun goes with it. For good.", "amber")
        line("Orrin", "The Well is sealed. The first Keeper split its key into three Embers and gave them to three "
                      "guardians: the Antlered Mother in the Weeping Wood, the Bishop of the drowned chapel past the "
                      "marsh, and a Choir somewhere below the hill. They have gone Hollow, all of them. I can feel it.",
             "amber")
        line("Orrin", "Bring the Embers back. Set them in the grate of the Old Well, and go down, and rekindle it. "
                      "I'd go myself, but my legs gave out before the sun did.", "amber")
        line("Orrin", "And %s, light the wayposts on the Tollroad if you can. A lit road brings people "
                      "home." % p.name, "amber")
        g.set_quest("main", 1)
        g.set_quest("wayposts", 0)
        say("{grey}Orrin presses two flasks of oil into your hands.{/}")
        g.give("oil", 2)
        line("Orrin", "And take this. A homecoming charm: brass, warm as a hearthstone. Hold it and think of home, and it "
                      "will bring you back to the square. It will take you back to the last warm place you slept, too. "
                      "It needs a night's rest to catch its breath, so use it when you must, not when you merely can.",
             "amber")
        g.give("homecoming_charm")
        say("{grey}(Type 'recall' to go home, 'return' to go back to where you last rested. 'stats' shows its charges. "
            "'journal' shows your quests, 'map' where you've been, 'help' everything else.){/}")
        return
    while True:
        opts = [("Ask about the Embers", "embers"), ("Ask about the Hollows", "hollows"),
                ("Ask how he is", "health")]
        if any(g.flags.get("read_" + x) for x in ("page4", "page5")) and not g.flags.get("orrin_aldric"):
            opts.append(("{gold}Ask about Aldric{/}", "aldric"))
        if g.shards() == 3 and not g.flags.get("orrin_ring"):
            opts.append(("{gold}Show him the three Embers{/}", "ring"))
        k = topic_menu(opts)
        if k is None:
            line("Orrin", "Mind your oil.", "amber")
            return
        if k == "embers":
            n = g.shards()
            line("Orrin", ["None yet. The wood is nearest: north gate. The chapel is over the water: ask Oskar at "
                           "the docks. The Choir... the drowned chapel's crypt goes down into the old mines.",
                           "One. Good. I felt it come home. Two more.",
                           "Two. The last is deep. Under the chapel, under the hill.",
                           "All three. Then go down. Through the Old Well, in the square."][n], "amber")
        elif k == "hollows":
            line("Orrin", "A Hollow is anything whose light has been put out. They fear flame and they want it. "
                          "Throw your lantern open in their faces, a flare, and they'll burn and go blind. "
                          "But every flare costs oil, and oil is life down there.", "amber")
        elif k == "health":
            line("Orrin", ["I'm dying, child, but slowly, and I've had practice.",
                           "Better for seeing you. Go on now."][g.rng.randint(0, 1)], "amber")
        elif k == "aldric":
            g.flags["orrin_aldric"] = True
            narrate("Orrin is quiet for a long time.")
            line("Orrin", "Aldric was the Keeper before me. My teacher. He was supposed to give his flame to the "
                          "Well when it began to fade. Every Keeper does, in the end. He went down... and the Well "
                          "dimmed instead of brightening, and he never came up.", "amber")
            line("Orrin", "And I was supposed to go after him, and give mine. I was afraid too. I've been afraid for "
                          "fifty years. That's why the Well is dying. Not the Hollows. Us.", "amber")
        elif k == "ring":
            g.flags["orrin_ring"] = True
            narrate("Orrin looks at the three Embers glowing in your palm, and his face is wet.")
            line("Orrin", "Take this. It was Aldric's, then mine. A Keeper's ring. It keeps the flame from wasting.",
                 "amber")
            g.give("orrins_ring")
            line("Orrin", "Whatever is down there, it will offer you an easier way. There isn't one.", "amber")


# ---------------------------------------------------------------------------- Maeve
RUMOURS = [
    "The wolves in the wood have no shadows now. Hesk swears it.",
    "Oskar says the marsh lights have been coming closer to town every night.",
    "Brann's been asking everyone if they've seen starsteel. He's dreaming of the old mines again.",
    "There's a merchant under the hill, they say. Sells candles to the dead.",
    "The Bishop of the Tide drowned his own chapel rather than let the sea take it. Mad as a fish.",
    "Sister Ilse's flame is all that's keeping the chapel from going Hollow. She needs those marsh flowers.",
    "If your lantern goes out down there, they say you can't even see what's coming at you.",
    "Old Corvin lives in the deepwood. Feeds his raven on wolf-meat. Knows everything, tells nothing.",
]


def talk_maeve(g):
    if g.quest("wren") == -1:
        line("Maeve", "Lamplighter. Good. You're going out there? Then I'm begging you.", "gold")
        line("Maeve", "My Wren went into the Weeping Wood nine days ago. Her father's trap-lines, she said, as if "
                      "he'd want them checked, him three years in the ground. She took a candle. Just a candle.",
             "gold")
        line("Maeve", "Find her. Bring her home. I'll give you everything I have.", "gold")
        g.set_quest("wren", 0)
        return
    while True:
        opts = [("Hear the rumours", "rumour"), ("Trade (food, draughts, oil)", "trade")]
        if g.quest("wren") in (0, 1, 2):
            opts.insert(0, ("Ask about Wren", "wren"))
        k = topic_menu(opts)
        if k is None:
            line("Maeve", "Come back in one piece.", "gold")
            return
        if k == "rumour":
            line("Maeve", g.rng.choice(RUMOURS + areas.rumours(g)), "gold")
        elif k == "trade":
            trade(g, "maeve")
        elif k == "wren":
            st = g.quest("wren")
            if st == 1:
                line("Maeve", "Her ribbon? On the briars? Then she went north, past the fork. Oh, the fool girl.", "gold")
            elif st == 2:
                line("Maeve", "You found her? Then why isn't she here? Bring her home!", "gold")
            else:
                line("Maeve", "She's yellow-haired, twelve, small for it. Wears a ribbon. Please.", "gold")


# ---------------------------------------------------------------------------- Hesk
def talk_hesk(g):
    if not g.flags.get("hesk_met"):
        g.flags["hesk_met"] = True
        line("Hesk", "Going out? Then you're braver than me, or dafter. The wolves come up to the braziers now. "
                     "Big grey things with no shadows.", "bone")
        line("Hesk", "Here. Smoke pellet. Smash it if you need to run. Not that running helps much against a wolf.",
             "bone")
        g.give("smokebomb")
        line("Hesk", "And if you've never held a hook in anger, I've a straw man out back. Hit it as much as you like. "
                     "It won't mind, and it costs nothing.", "bone")
    tips = [
        "The road forks under the hanging oak. West is the hunters' old camp, east the thicket, north the deepwood.",
        "Light the wayposts. When they burn, the Hollows keep away from the road.",
        "Watch for a wolf dropping low. That's the lunge coming. Brace for it, or hit it first.",
        "Flares. Your old master always said: when in doubt, open the shutters. But the lantern needs a breath between.",
        "There's an old hermit up past the deepwood. Corvin. If he's alive, he'll know what took the Maeve girl.",
    ]
    while True:
        k = topic_menu([("Ask for advice", "tips"), ("Practise fighting on the straw man {grey}(free, nothing is lost){/}", "spar")])
        if k is None:
            line("Hesk", "Stay lit.", "bone")
            return
        if k == "tips":
            line("Hesk", g.rng.choice(tips), "bone")
        else:
            blank()
            g.practice_fight(intro="Hesk drags a straw-stuffed scarecrow into the lamplight. 'Hit it. Watch what it does "
                                   "next. It always tells you.'")
            blank()
            line("Hesk", "Not bad. Come back whenever you want another go.", "bone")


# ---------------------------------------------------------------------------- Ilse
def talk_ilse(g):
    p = g.player
    if g.quest("petals") == -1:
        line("Ilse", "Forgive me, I can't take my eyes off it. If this flame goes out, the chapel goes Hollow, and "
                     "everyone who sleeps under its roof.", "bone")
        line("Ilse", "There are flowers in the Saltmarsh, moonpetals. They glow with a light of their own. Three would "
                     "keep this flame alive for a year. Would you bring them? I'll give you what blessing I have.", "bone")
        g.set_quest("petals", 0)
        return
    while True:
        opts = [("Trade (salts, draughts)", "trade"), ("Ask for healing", "heal")]
        if g.quest("petals") == 0 and p.inventory.get("moonpetal", 0) >= 3:
            opts.insert(0, ("{gold}Give her three Moonpetals{/}", "petals"))
        if g.quest("petals") == 0:
            opts.append(("Ask about the moonpetals", "about"))
        k = topic_menu(opts)
        if k is None:
            line("Ilse", "The Ember keep you.", "bone")
            return
        if k == "trade":
            trade(g, "ilse")
        elif k == "heal":
            if p.hp >= p.max_hp:
                line("Ilse", "You're whole. Save my prayers for when you're not.", "bone")
            else:
                p.hp = p.max_hp
                line("Ilse", "Hold still.", "bone")
                say("{bgreen}A warmth spreads through you. Your wounds close.{/}")
        elif k == "about":
            n = p.inventory.get("moonpetal", 0)
            line("Ilse", "Pale flowers that glow in black water. In the Saltmarsh, past the ferry. You have %d." % n, "bone")
        elif k == "petals":
            p.remove_item("moonpetal", 3)
            narrate("Ilse crushes the petals over the brazier. The tiny flame drinks them in and rises, white and "
                    "strong, until it lights every corner of the chapel. Ilse laughs out loud, then covers her mouth.")
            line("Ilse", "Thank you. Kneel.", "bone")
            narrate("She marks your forehead with warm oil. You feel sturdier, as if something inside you set like mortar.")
            p.bonus_hp += 15
            p.hp = p.max_hp
            say("{bgreen}Blessing of the Ember: +15 maximum health.{/}")
            g.give("saints_tooth")
            g.set_quest("petals", "done")
            g.award_xp(30)


# ---------------------------------------------------------------------------- Brann
def talk_brann(g):
    p = g.player
    if not g.flags.get("brann_met"):
        g.flags["brann_met"] = True
        line("Brann", "Lamplighter. Need an edge? Everything on the wall's for sale. Cheap, too. Nobody's buying.", "ember")
        line("Brann", "And I can fit your lantern with a brass shroud, if you've the coin. Holds more oil, "
                      "burns slower.", "ember")
    while True:
        opts = [("Use the forge {grey}(raise Rare gear to Epic and beyond, socket relics){/}", "forge"),
                ("Trade (weapons, armour)", "trade")]
        if not p.lantern.get("shroud"):
            opts.append(("Fit a Brass Shroud to your lantern {gold}(80g){/}", "shroud"))
        if g.quest("starsteel") == -1:
            opts.append(("Ask what he's working on", "starsteel"))
        if g.quest("starsteel") == 1:
            opts.insert(0, ("{gold}Give him the Starsteel Ore{/}", "ore"))
        k = topic_menu(opts)
        if k is None:
            line("Brann", "Mind the edge.", "ember")
            return
        if k == "forge":
            forge_ui.menu(g)
        elif k == "trade":
            trade(g, "brann")
        elif k == "shroud":
            if p.gold < 80:
                line("Brann", "Eighty. I'd do it for less, but brass is brass.", "ember")
                continue
            p.gold -= 80
            p.lantern["shroud"] = True
            p.add_oil(30)
            narrate("Brann fits a ring of hammered brass around your lantern's chimney. It sits heavier in your hand, "
                    "and the flame burns quieter and steadier.")
            say("{amber}Lantern upgraded: +30 oil capacity, and it burns less oil in the dark.{/}")
        elif k == "starsteel":
            line("Brann", "Nothing. Same as always. Hatchets.", "ember")
            line("Brann", "...My grandfather worked the old mines under the hill. There's a seam down there, starsteel, "
                          "metal that fell from the sky. Never got to forge it. If you ever find yourself under the "
                          "hill, and you see the stars in the rock, bring me a piece. I'd make you a blade that'd "
                          "cut a Hollow in half just by being near it.", "ember")
            g.set_quest("starsteel", 0)
        elif k == "ore":
            p.remove_item("starsteel_ore")
            narrate("Brann turns the ore over in his hands like a holy thing. He doesn't speak. He just goes to the "
                    "forge, and for a long time there is only the roar of the bellows and the ring of the hammer.")
            narrate("When he is done, he lays a blade across your hands. It is black, and full of tiny lights.")
            line("Brann", "Best thing I'll ever make. Go and use it.", "ember")
            g.give("starsteel_blade")
            g.set_quest("starsteel", "done")
            say("{grey}('equip starsteel' to wield it){/}")
            g.award_xp(40)


# ---------------------------------------------------------------------------- Oskar
def talk_oskar(g):
    if not g.flags.get("oskar_met"):
        g.flags["oskar_met"] = True
        line("Oskar", "Across? To the marsh? Nobody goes to the marsh.", "brine")
        line("Oskar", "...Fine. It's free. Nobody to charge. Just walk east off the end of the dock and I'll pole you "
                      "over. Come back to the landing and shout, and I'll come for you.", "brine")
        return
    tips = [
        "The chapel doors are locked. The old Reeve kept the key. Lives in the big house on stilts. Lived.",
        "Don't follow the lights in the bog. Unless you want moonpetals. Then follow them very carefully.",
        "The Bishop drowned his chapel himself, they say, when the sea began to take it. Said if it must sink, it "
        "would sink holy. He's still down there, preaching to the fish.",
        "Fire's what the Bishop hates. Dries out the brine in him. Brann sells firepots, if you've the coin.",
    ]
    while True:
        k = topic_menu([("Ask for advice about the marsh", "tips")])
        if k is None:
            line("Oskar", "Mind the water.", "brine")
            return
        line("Oskar", g.rng.choice(tips), "brine")


# ---------------------------------------------------------------------------- Corvin
def talk_corvin(g):
    p = g.player
    if not g.flags.get("corvin_met"):
        g.flags["corvin_met"] = True
        line("Corvin", "A lamplighter. In my wood. With a lantern. Well, well. Sit down, you're letting the dark in.", "moss")
        line("Corvin", "You'll be wanting the Mother, I expect. North, through the white trees. She was the gentlest "
                       "thing in this forest once. Now she's caged a little girl in the roots. Keeps her the way a "
                       "child keeps a firefly in a jar.", "moss")
        if g.quest("wren") in (-1, 0, 1):
            if g.quest("wren") == -1:
                g.quests["wren"] = 0
            g.set_quest("wren", 1)
        line("Corvin", "My raven's nest is cold. Bring me a wolf pelt and I'll show you a trick with lantern wicks "
                       "your old master never knew.", "moss")
        g.set_quest("corvin", 0)
        return
    while True:
        opts = [("Ask about the Antlered Mother", "mother"), ("Trade", "trade")]
        if g.quest("corvin") == 0 and p.has_item("wolf_pelt"):
            opts.insert(0, ("{gold}Give him a Gloam Pelt{/}", "pelt"))
        if town.is_built(g, "hearth_stall"):
            opts.append(("Eat a hot meal {grey}(25 gold: heals 20, Dread -20){/}", "meal"))
        elif g.flags.get("mother_dead"):
            opts.append(("Ask him to move to Hollowmere", "invite"))
        k = topic_menu(opts)
        if k is None:
            line("Corvin", "Off you go. Don't feed the moths." if not town.is_built(g, "hearth_stall")
                 else "Mind the market, it's busier than it looks.", "moss")
            return
        if k == "invite":
            if town.is_invited(g, "hearth_stall"):
                line("Corvin", "Joss, the builder fellow, in the yard on Market Row. Tell him I want a hob and a roof. "
                               "The raven's coming too, so tell him that as well.", "moss")
            else:
                line("Corvin", "Leave the hut? Forty years I've fed ravens in the dark. ...But there's a market, you say. "
                               "People. A hearth that isn't mine alone. Fine. Fine! Tell the builder fellow, Joss, in the "
                               "yard on Market Row. I'll cook for the lot of you.", "moss")
                town.invite(g, "hearth_stall")
                say("{gold}Corvin will move to Hollowmere once Joss has built the Hearth Stall.{/} "
                    "{grey}(Joss is in the Builder's Yard, north of Market Row.){/}")
        elif k == "meal":
            if p.gold < 25:
                line("Corvin", "Twenty-five gold, lamplighter. The onions don't grow themselves.", "moss")
            else:
                p.gold -= 25
                healed = p.heal(20)
                p.dread = max(0, p.dread - 20)
                line("Corvin", "Eat. Slowly. The dark can wait for a bowl of soup.", "moss")
                say("{bgreen}A hot meal. (+%d health, Dread %d){/}" % (healed, p.dread))
            continue
        if k == "mother":
            line("Corvin", "She's big and she's angry and she hits like a falling tree. When she rears up, brace or "
                           "be flattened. When she calls her brood, deal with the fawns quick or you'll be swamped. "
                           "And she's Hollow, so your lantern's your best friend.", "moss")
        elif k == "trade":
            trade(g, "corvin")
        elif k == "pelt":
            p.remove_item("wolf_pelt")
            narrate("Corvin tucks the pelt into the raven's nest. The raven settles into it and closes its eyes. "
                    "Then Corvin takes your lantern, and with his thumbnail splits and twists the wick in a way you've "
                    "never seen.")
            line("Corvin", "There. Flares'll cost you less now. Don't tell the guild.", "moss")
            p.lantern["trim"] = True
            say("{amber}Lantern improved: flares cost 3 less oil.{/}")
            g.set_quest("corvin", "done")
            g.award_xp(20)


# ---------------------------------------------------------------------------- Tallow
def talk_tallow(g):
    if not g.flags.get("tallow_met"):
        g.flags["tallow_met"] = True
        line("Tallow", "Oh! A customer! A warm one! Come in, come in, mind the candles, they're mostly friends.", "amber")
        line("Tallow", "I sell to everyone. The dead, the Hollow, the merely lost. I buy too. Hollow dust especially. "
                       "Don't ask what for. And I'll give you a fair price for anything shiny.", "amber")
        line("Tallow", "You may rest here, if you like. Nothing comes near my candles. They know better.", "amber")
    while True:
        opts = [("Trade", "trade"), ("Ask about the Choir", "choir"), ("Ask about the King", "king")]
        k = topic_menu(opts)
        if k is None:
            line("Tallow", "Stay lit!", "amber")
            return
        if k == "trade":
            trade(g, "tallow")
        elif k == "choir":
            line("Tallow", "Three singers, east of here. They've been holding the same chord for fifty years. "
                           "The high one heals the others; the low one winds up something dreadful, a great "
                           "chord. Silence the healer first, I'd say. And they grieve. Kill one and the others "
                           "sing harder.", "amber")
        elif k == "king":
            line("Tallow", "He sits by the Well and he waits. Wraps himself in the dark so nothing can touch him. "
                           "Nothing but light, of course. Light is rude like that. Keep a flare in reserve, my "
                           "warm friend, or you'll be hitting shadows all day.", "amber")


# ---------------------------------------------------------------------------- Wren
def talk_wren(g):
    if g.quest("wayposts") == "done":
        line("Wren", "I saw the wayposts burning all the way up the road. You did that.", "gold")
        line("Wren", "When you go down to the Well... I want to come. Don't argue. Orrin says two hands on a wick "
                     "is better than one. I'll be there when you need me.", "gold")
        g.flags["wren_ready"] = True
    else:
        line("Wren", "I'm sorry. I thought I could find Da's traps and bring back meat. I thought my candle was "
                     "enough.", "gold")
        line("Wren", "Will you light the road? The wayposts? Then nobody else gets lost like I did.", "gold")


# ---------------------------------------------------------------------------- Mirelle, the Magician
STARTER_BOOK = {"ashblade": "fire", "warden": "earth", "wayfarer": "shadow"}


def talk_mirelle(g):
    p = g.player
    if not g.flags.get("mirelle_met"):
        g.flags["mirelle_met"] = True
        el = STARTER_BOOK[p.cls]
        narrate("Something in her pocket stops humming as you come in.")
        line("Mirelle", "A lamplighter! Finally. Everyone else wants oil. I want to talk about magic.", "hollow")
        line("Mirelle", "Here is the whole idea. A spell is a book. Anyone can read one. The art is in what you bring "
                        "to it: essences from the things you beat, and the nerve to put two books together and see "
                        "what comes out.", "hollow")
        line("Mirelle", "Take this one on loan. No, keep it. I have a hundred.", "hollow")
        book = spells.make_book(g, el, "common")
        say("{bgreen}Mirelle gives you %s.{/}" % rarity.label(book))
        ok, _ = spells.equip(p, book)
        if ok:
            say("{grey}It is already equipped. In a fight, cast it with S1. Weaknesses show on each enemy. Type 'spells' "
                "any time to change your books.{/}")
    magic_ui.menu(g)
    line("Mirelle", "Bring me essences. And something worth combining.", "hollow")


# ---------------------------------------------------------------------------- Joss, the Builder
def talk_joss(g):
    if not g.flags.get("joss_met"):
        g.flags["joss_met"] = True
        line("Joss", "Joss. I build. You're the lamplighter, then. Good. This town has more plots than people, and I'd "
                     "like that the other way round.", "bone")
        line("Joss", "Here's how it goes. Out in the dark there are folk who'd sooner live somewhere lit. Find them, ask "
                     "them to come, and send them to me. Bring me gold and materials, rootwood from the wood, saltstone "
                     "from the marsh, slag from the mines, and I'll raise their place.", "bone")
        line("Joss", "It takes a little while: some minutes by the clock, or some steps of walking, whichever comes first. "
                     "Then they open for business, and they pay you rent. Up to eight hours' worth builds up while you're "
                     "away. I count it out here, or you can collect it at home. Type 'collect'.", "bone")
    while True:
        st = town.state(g)
        opts = []
        for bid in town.available(g):
            b = BUILDINGS[bid]
            opts.append(("Build the %s {grey}(%s){/}" % (b["name"], town.cost_lines(bid)), ("build", bid)))
        for entry in st["queue"]:
            b = BUILDINGS[entry["id"]]
            opts.append(("Hurry the %s {grey}(%d gems; about %d minutes or %d steps left){/}" % (
                b["name"], town.speed_up_cost(entry), town.minutes_left(entry), max(0, entry["steps"])), ("hurry", entry["id"])))
        due = town.rent_due(g)
        if town.rent_rate(g):
            opts.append(("Collect rent {grey}(%d gold waiting){/}" % due, ("rent", None)))
        opts.append(("How is the town doing?", ("status", None)))
        k = topic_menu(opts)
        if k is None:
            line("Joss", "Measure twice.", "bone")
            return
        kind, bid = k
        if kind == "build":
            lacking = town.missing(g, bid)
            if lacking:
                line("Joss", "You're short: %s. Come back when you've got it." % ", ".join(lacking), "bone")
            elif town.start_build(g, bid):
                line("Joss", "Right. I'll start at once. It'll be ready in about %d minutes, or %d steps of walking."
                     % (BUILDINGS[bid]["minutes"], BUILDINGS[bid]["steps"]), "bone")
        elif kind == "hurry":
            entry = town.queued(g, bid)
            cost = town.speed_up_cost(entry)
            if g.player.gems < cost:
                line("Joss", "That's %d gems to hurry it, and you've %d. I don't take promises." % (cost, g.player.gems), "bone")
            elif ui.confirm("Spend %d gems to finish the %s now?" % (cost, BUILDINGS[bid]["name"])):
                town.speed_up(g, bid)
                line("Joss", "Ha. Done. I'd rather it were honest work, but a gem is a gem.", "bone")
        elif kind == "rent":
            got = town.collect_rent(g)
            line("Joss", "Rent's in. %d gold." % got if got else "Nothing yet. Give it time.", "bone")
        else:
            for text in town.summary_lines(g):
                say(text)
            say("{grey}Rent: %d gold an hour, up to %d hours at a time.{/}" % (town.rent_rate(g), town.RENT_CAP_HOURS))


# ---------------------------------------------------------------------------- Odo, the netmaker
def _invite_scene(g, bid, who, ask, yes, again):
    """A survivor in the field agrees to move to Hollowmere."""
    if town.is_invited(g, bid):
        line(who, again, "bone")
        return
    line(who, ask, "bone")
    town.invite(g, bid)
    say("{gold}%s will move to Hollowmere once Joss has built the %s.{/} {grey}(Joss is in the Builder's Yard, north "
        "of Market Row.){/}" % (who, BUILDINGS[bid]["name"]))


def talk_odo(g):
    if town.is_built(g, "salvage_stall"):
        while True:
            k = topic_menu([("Trade {grey}(he buys parts, sells building materials){/}", "trade"),
                            ("Ask about the marsh", "marsh")])
            if k is None:
                line("Odo", "Mind the scale.", "brine")
                return
            if k == "trade":
                trade(g, "odo")
            else:
                line("Odo", "Eight months in that loft. You learn what a Hollow sounds like when it's thinking. "
                            "It sounds like a man holding his breath.", "brine")
    if not g.flags.get("odo_met"):
        g.flags["odo_met"] = True
        narrate("A trapdoor opens in the ceiling. A thin face looks down at you, and then at the Reeve's empty chair.")
        line("Odo", "Is he gone? Truly gone? ...I'm Odo. I mend nets. Mended. The whole village used to bring me their "
                    "nets, and then the whole village walked into the water, one by one, and I climbed into the loft "
                    "and held my breath.", "brine")
    while True:
        k = topic_menu([("Ask him to come to Hollowmere", "invite"), ("Ask what he can do", "skills")])
        if k is None:
            line("Odo", "I'll be here. I'm good at being here.", "brine")
            return
        if k == "invite":
            _invite_scene(g, "salvage_stall", "Odo",
                          "Hollowmere? With lamps? ...I sort things, you know. Bone, hide, scrap, what's worth keeping "
                          "and what isn't. A stall with a scale. I'd like that. Tell the builder, Joss, in the yard on "
                          "Market Row. I'll come when there's a roof.", "",
                          "Tell Joss, the builder, in the yard on Market Row. I'll come when there's a roof.")
        else:
            line("Odo", "I buy what the Hollows leave behind, and I sell what the Builder needs. Rootwood, saltstone, slag, "
                        "if you're ever short.", "brine")


# ---------------------------------------------------------------------------- Dagna, the miner
UPGRADES = {
    "stash": {2: (150, {"slag": 4}), 3: (300, {"slag": 8})},
    "relic": {2: (200, {"slag": 5}), 3: (400, {"slag": 10})},
}


def _upgrade_option(g, kind):
    level = town.state(g)["stash_level"] if kind == "stash" else g.player.relic_level
    nxt = level + 1
    if nxt not in UPGRADES[kind]:
        return None
    gold, mats = UPGRADES[kind][nxt]
    cost = "%d gold" % gold + "".join(", %d %s" % (n, ITEMS[i]["name"]) for i, n in mats.items())
    return nxt, gold, mats, cost


def _do_upgrade(g, kind):
    opt = _upgrade_option(g, kind)
    p = g.player
    nxt, gold, mats, cost = opt
    if p.gold < gold or any(p.inventory.get(i, 0) < n for i, n in mats.items()):
        line("Dagna", "That's %s. You haven't got it yet." % cost, "bone")
        return
    p.gold -= gold
    for i, n in mats.items():
        p.remove_item(i, n)
    if kind == "stash":
        town.state(g)["stash_level"] = nxt
        line("Dagna", "Deeper shelves, thicker boxes. Your chest holds %d things now." % town.stash_capacity(g), "bone")
    else:
        p.relic_level = nxt
        p.relic_charges = p.relic_max_charges
        line("Dagna", "I've set a tighter spring in it. It'll catch its breath faster. It holds %d uses now." %
             p.relic_max_charges, "bone")


def talk_dagna(g):
    if town.is_built(g, "strongroom"):
        while True:
            opts = []
            s_opt = _upgrade_option(g, "stash")
            r_opt = _upgrade_option(g, "relic")
            if s_opt:
                opts.append(("Enlarge your stash to %d {grey}(%s){/}" % (town.STASH_CAPACITY[s_opt[0]], s_opt[3]), "stash"))
            if r_opt:
                opts.append(("Strengthen the Homecoming Charm to %d uses {grey}(%s){/}" % (1 + r_opt[0], r_opt[3]), "relic"))
            opts.append(("Ask about the mines", "mines"))
            k = topic_menu(opts)
            if k is None:
                line("Dagna", "Keep your boxes shut.", "bone")
                return
            if k in ("stash", "relic"):
                _do_upgrade(g, k)
            else:
                line("Dagna", "Three generations my family dug that seam. It takes a particular kind of stubborn to "
                              "get trapped under it and still be annoyed about the schedule.", "bone")
    if not g.flags.get("dagna_met"):
        g.flags["dagna_met"] = True
        narrate("A figure is wedged in the rock at the back of the cavern, one arm pinned by a fallen block, "
                "the other still holding a pick-hammer. She has been there long enough to be irritated about it.")
        line("Dagna", "Took your time. I'm Dagna. My family's dug this seam for three generations. The Warden was ours: "
                      "we built it to guard the ore. Then the dark got into it. Thank you for putting it down.", "bone")
        narrate("You shift the block together, and she wriggles free, rubbing her shoulder.")
    while True:
        k = topic_menu([("Ask her to come to Hollowmere", "invite"), ("Ask what she can do", "skills")])
        if k is None:
            line("Dagna", "I've an arm to rub. Go on.", "bone")
            return
        if k == "invite":
            _invite_scene(g, "strongroom", "Dagna",
                          "A town that's lit? I'll build you something that lasts: a strongroom, a proper vault, thick "
                          "walls, and I can make your chest hold more and your charm hold a spring. Tell the builder, "
                          "Joss, on Market Row.", "",
                          "Tell Joss, in the yard on Market Row. I'll want stone and slag. Plenty of slag.")
        else:
            line("Dagna", "Vaults. Boxes. Springs and clasps. I can make your stash bigger and your homecoming charm "
                          "catch its breath faster. It's mostly slag and patience.", "bone")


# ---------------------------------------------------------------------------- the Wizard
def talk_wizard(g):
    p = g.player
    if not g.flags.get("wizard_met"):
        g.flags["wizard_met"] = True
        narrate("The bell over the door is a brass moth, and it rings backwards.")
        line("Ysolde", "Ah. You've finished. Sit, sit. I opened the moment the long night ended. I keep a shop for what "
                       "comes after.", "hollow")
        line("Ysolde", "People think a story ends. It only stops being told. I can tell it again, for a fee. Or I can fetch "
                       "back one of the things you've beaten, if you've a mind to beat it twice. You'll keep what you've "
                       "earned: your gear, your level, your town. Only the story comes undone.", "hollow")
        line("Ysolde", "And the dark is not finished, you know. There are other places. They'll want a lamplighter.", "hollow")
    while True:
        k = topic_menu([("Call back a defeated boss", "boss"), ("Rewind the story", "rewind"),
                        ("Ask about the other places", "more")])
        if k is None:
            line("Ysolde", "Come back whenever you like. I'll be here. Or I'll have been.", "hollow")
            return
        if k == "more":
            line("Ysolde", "Harder dark than this, further out. And older places, nearer, that you passed too quickly. "
                           "I can feel them, like a draught under a door. Not yet. But soon.", "hollow")
        elif k == "boss":
            bosses = postgame.defeated_bosses(g)
            if not bosses:
                line("Ysolde", "You haven't beaten anything worth calling back.", "hollow")
                continue
            i = ui.menu(["%s {grey}(%d gold){/}" % (name, fee) for _, name, fee in bosses], prompt="Call back",
                        cancel_label="Never mind")
            if i is None:
                continue
            rid, name, fee = bosses[i]
            if p.gold < fee:
                line("Ysolde", "That's %d gold. You haven't got it." % fee, "hollow")
            elif ui.confirm("Pay %d gold to call back %s?" % (fee, name)):
                postgame.call_back(g, rid)
                line("Ysolde", "Done. It will be waiting where you left it. It will not be in a good mood.", "hollow")
        elif k == "rewind":
            labels = []
            for i, (chapter, _, _) in enumerate(postgame.LAYERS):
                labels.append("Undo everything from %s on {grey}(%d gold){/}" % (chapter, postgame.rewind_cost(g, i)))
            i = ui.menu(labels, prompt="Rewind to", cancel_label="Never mind")
            if i is None:
                continue
            fee = postgame.rewind_cost(g, i)
            if p.gold < fee:
                line("Ysolde", "That's %d gold. You haven't got it." % fee, "hollow")
                continue
            say("{grey}You keep your gear, level, gold (less the fee) and everything you have built. Bosses, the Embers "
                "you carry, and the doors they opened come undone. A backup of your game is saved first.{/}")
            if ui.confirm("Rewind the story from %s on, for %d gold?" % (postgame.LAYERS[i][0], fee)):
                postgame.rewind(g, i)
                line("Ysolde", "There. Tidy. Go and do it better, or differently, or just again.", "hollow")


# ---------------------------------------------------------------------------- shops
STOCK = {
    "maeve": ["stew", "draught", "oil", "honeycake"],
    "ilse": ["salts", "draught", "strong_draught"],
    "brann": ["hatchet", "ashwood_rod", "gutting_knife", "jerkin", "hauberk", "wardenplate", "firepot"],
    "corvin": ["honeycake", "salts", "oil", "wolf_fang"],
    "tallow": ["strong_draught", "firepot", "tonic", "smokebomb", "oil", "moth_charm", "lens",
               "relic_ember", "relic_lamp", "relic_edge", "relic_heart", "relic_pulse"],
    "odo": ["rootwood", "saltstone", "slag"],
    "pell": ["oil", "strong_draught", "honeycake", "stew", "firepot", "tonic", "smokebomb"],
}
PRICES_RELIC = 60
PRICES = {"lens": 140, "rootwood": 12, "saltstone": 15, "slag": 18, "relic_ember": 60, "relic_lamp": 60,
          "relic_edge": 60, "relic_heart": 60, "relic_pulse": 60}


def stock_for(g, nid):
    items = list(STOCK[nid])
    if nid == "brann" and "Saltmarsh" in g.flags.get("visited_regions", []):
        items.insert(3, "saltsteel_saber")
    if nid == "tallow" and g.player.lantern.get("lens"):
        items.remove("lens")
    items.extend(i for i in areas.sells(g, nid) if i not in items)
    return items


def price(iid):
    if iid in PRICES:
        return PRICES[iid]
    area = areas.collect("PRICES")
    if iid in area:
        return area[iid]
    return ITEMS[iid]["value"]


def shop_screen(g, nid, note):
    ui.clear()
    ui.rule("%s's wares  ·  you have %d gold" % (NPCS[nid]["name"], g.player.gold), color="gold")
    if note:
        say(note)
        blank()


def trade(g, nid):
    note = ""
    while True:
        shop_screen(g, nid, note)
        i = ui.menu(["Buy", "Sell"], prompt="Trade", cancel_label="Done")
        if i is None:
            return
        note = buy(g, nid) if i == 0 else sell(g, nid)


def buy(g, nid):
    p = g.player
    note = ""
    while True:
        shop_screen(g, nid, note)
        items = stock_for(g, nid)
        labels = []
        for iid in items:
            it = ITEMS[iid]
            pr = price(iid)
            afford = p.gold >= pr
            have = p.count(iid)
            extra = g.stat_text(iid) if it["kind"] in ("weapon", "armor", "trinket") else it["desc"]
            if iid == "lens":
                extra = "Lantern fitting: stronger flares that cost 5 less oil."
            shown = rarity.label(iid)
            labels.append("%s%s{/} {gold}%4dg{/}  {grey}%s%s{/}" % (
                "{bwhite}" if afford else "{grey}", shown + " " * max(0, 28 - ui.visible_len(shown)), pr, extra,
                ("  (have %d)" % have) if have else ""))
        idx = ui.menu(labels, prompt="Buy")
        if idx is None:
            return note
        iid = items[idx]
        pr = price(iid)
        if p.gold < pr:
            note = "{grey}You can't afford the %s.{/}" % ITEMS[iid]["name"]
            continue
        p.gold -= pr
        if iid == "lens":
            p.lantern["lens"] = True
            note = "{amber}Tallow fits the polished lens into your lantern with soft waxy fingers. The light sharpens.{/}"
            continue
        p.add_item(iid)
        note = "{bgreen}Bought: %s.{/}" % ITEMS[iid]["name"]
        if ITEMS[iid]["kind"] in ("weapon", "armor", "trinket"):
            blank()
            if ui.confirm("Equip the %s now?" % ITEMS[iid]["name"]):
                g.cmd_equip(ITEMS[iid]["name"].lower())
                note = "{bgreen}Bought and equipped: %s.{/}" % ITEMS[iid]["name"]


def sell(g, nid):
    p = g.player
    note = ""
    while True:
        shop_screen(g, nid, note)
        hidden = ("key", "page") + (() if nid == "odo" else ("material",))
        items = [iid for iid in p.inventory if ITEMS[iid]["kind"] not in hidden and ITEMS[iid]["value"] > 0]
        if not items:
            return note or "{grey}You have nothing to sell.{/}"
        labels = []
        offers = []
        for iid in items:
            v = ITEMS[iid]["value"]
            full = (nid == "tallow" and ITEMS[iid]["kind"] == "junk") or (nid == "odo" and ITEMS[iid]["kind"] in ("junk", "material"))
            offer = v if full else max(1, v // 2)
            offers.append(offer)
            labels.append("%s x%d {gold}%dg each{/}" % (rarity.label(iid), p.inventory[iid], offer))
        idx = ui.menu(labels, prompt="Sell")
        if idx is None:
            return note
        iid = items[idx]
        n = p.inventory[iid]
        qty = 1
        if n > 1 and ui.confirm("Sell all %d?" % n):
            qty = n
        p.remove_item(iid, qty)
        p.gold += offers[idx] * qty
        note = "{gold}Sold %s%s for %d gold.{/}" % (ITEMS[iid]["name"], " x%d" % qty if qty > 1 else "", offers[idx] * qty)


# ---------------------------------------------------------------------------- the Ember Court
def talk_pell(g):
    f = g.flags
    if not f.get("pell_met"):
        f["pell_met"] = True
        narrate("The gatehouse is small, tidy and warm in a way nothing else here is. A woman looks up from a ledger "
                "with the face of someone who has been rehearsing a sentence for a hundred years.")
        line("Pell", "You're the first to come in the front way. Everyone else comes over the wall, or not at all. "
                     "Pell. I keep the door.", "ember")
        line("Pell", "The Court never stopped dancing, you understand. The fire took the house and the music didn't "
                     "notice. I stayed because someone had to write down who went in.", "ember")
        say("{grey}(Pell lets you rest here, and sells what she can. The Court Gate is a safe place.){/}")
    while True:
        opts = [("Trade {grey}(she sells supplies){/}", "trade"), ("Ask about the Court", "court"),
                ("Ask how the Queen is today", "queen")]
        k = topic_menu(opts)
        if k is None:
            line("Pell", "Mind the tiles. The glowing ones.", "ember")
            break
        if k == "trade":
            trade(g, "pell")
        elif k == "court":
            line("Pell", "The Steward keeps the Crown Key, in his hall, east of the Grand Hall. Nobody gets to the throne "
                         "without it. He counts guests. He has not been able to stop.", "ember")
            line("Pell", "And the cellar stair under the Great Kitchens is shut behind a door of molten iron. Something "
                         "cold would set it: a Water or Ice book, equipped, not just carried. Everything worth saving "
                         "was taken down there.", "ember")
        else:
            if f.get("queen_dead"):
                line("Pell", "Quiet. For the first time in my life. I do not know what to do with my hands.", "ember")
            else:
                line("Pell", "She is never the same twice. When you step into the throne room you will see how strong "
                             "she is before you decide, and you can always step back out. The stronger she is, the more "
                             "she pays. That is the only fair thing about her.", "ember")
    f["pell_after"] = bool(f.get("queen_dead"))


def talk_tamsin(g):
    f = g.flags
    if town.is_built(g, "ember_smithy"):
        while True:
            k = topic_menu([("Ask about her forge", "forge"), ("Ask about the Court", "court")])
            if k is None:
                line("Tamsin", "Come by when you've something worth hitting.", "ember")
                return
            if k == "forge":
                line("Tamsin", "A second anvil. Your forge can run one more job at the same time now: Brann has his hands "
                               "full, and I have mine. Type 'forge' here, in the smithy behind the Drowned Moth.", "ember")
            else:
                line("Tamsin", "I grew up in the Court forge. I thought it was the whole world. It was a small world, "
                               "and a hot one.", "ember")
    if not f.get("tamsin_met"):
        f["tamsin_met"] = True
        narrate("Behind the cold anvil, something moves. A young woman rises from where she has been hiding among the "
                "tools, a hammer held in both hands, and does not lower it.")
        line("Tamsin", "Is he gone? The Steward? I heard the bell stop. I heard it stop and I didn't believe it.", "ember")
        line("Tamsin", "Tamsin. I'm the forge's. Was. I hid when the music didn't stop. I've been very quiet.", "ember")
    while True:
        k = topic_menu([("Ask her to come to Hollowmere", "invite"), ("Ask what she can do", "skills")])
        if k is None:
            line("Tamsin", "I'll be here. I'm very good at being here.", "ember")
            return
        if k == "invite":
            _invite_scene(g, "ember_smithy", "Tamsin",
                          "A town? With a forge? ...with a second forge, you mean, because Brann has one? Fine. Two "
                          "anvils is better than one. Tell the builder. I'll bring my own hammers.", "",
                          "Tell Joss, the builder, in the yard on Market Row. A plot behind the Drowned Moth, he said.")
        else:
            line("Tamsin", "I can run a fire as hot as you can stand. If I'm in Hollowmere, your forge takes one more job "
                           "at a time. Brann can't do everything at once, and he knows it.", "ember")


def talk_dealer(g):
    f = g.flags
    if not f.get("dealer_met"):
        f["dealer_met"] = True
        narrate("You were not looking for anyone. But the dark is thicker here than it should be, and in it there is a "
                "folding table covered with black cloth, and four things laid out on the cloth. You find, when you "
                "look at them, that you are already thinking about what you would pay.")
        line("The Dealer", "No names. I trade in what you'd rather not carry, and in what you would. Gems only, and "
                           "only in the dark. Light this place and I'll be gone before you've put your match away.", "night")
        line("The Dealer", "There is one of me in every ring, and none of us stays put for long. "
                           "Four wares a day, and I will tell you the truth about every one of them.", "night")
        line("The Dealer", "Some are fair. Some are cursed, and cheap for it. I do not hide the curse. A curse you "
                           "can see is just a price.", "night")
        line("The Dealer", "And if a whole ring is lit, by a beacon, there is no dark left for me to sit in. "
                           "Buy what you want from me before then.", "night")
    else:
        line("The Dealer", ["Back again. The cloth is where I left it.", "You found me. Few do twice.",
                            "Look all you like. Nothing on the cloth lies.",
                            "The dark brought you here, as it does."][dealer.today() % 4], "night")
    dealer.menu(g)


# ---------------------------------------------------------------------------- people from the area modules
def _register_areas():
    import sys
    me = sys.modules[__name__]
    NPCS.update(areas.collect("NPCS"))
    STOCK.update(areas.collect("STOCK"))
    _AREA_PRESENT.update(areas.collect("PRESENT"))
    _AREA_NEWS.update(areas.collect("NEWS"))
    for m in areas.modules():
        for name in dir(m):
            if name.startswith("talk_") and callable(getattr(m, name)):
                if hasattr(me, name):
                    raise ValueError("%s is defined twice (area %s)" % (name, m.__name__))
                setattr(me, name, getattr(m, name))


_AREA_PRESENT = {}
_AREA_NEWS = {}
_register_areas()
