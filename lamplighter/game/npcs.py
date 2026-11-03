"""People of Hollowmere and below: who they are, what they say, what they sell."""
from . import ui
from .ui import say, blank, narrate
from .data.items import ITEMS


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
    "corvin": {"name": "Corvin the hermit", "aliases": ["hermit", "old man"], "shop": True,
               "desc": "An old man in a coat sewn from black feathers. He has lived in the wood for forty years and "
                       "seems mildly surprised the dark bothers anyone."},
    "tallow": {"name": "Tallow", "aliases": ["merchant", "candle", "wax"], "shop": True,
               "desc": "A merchant made of candle-wax, with a lit wick for hair. Their face is soft and slightly "
                       "melted, and their smile is genuine."},
    "wren": {"name": "Wren", "aliases": ["girl", "daughter"], "where": present_wren,
             "desc": "Maeve's daughter, twelve years old, wrapped in a blanket by the fire. There is a yellow ribbon "
                     "in her hair again. She watches your lantern the way you used to watch Orrin's."},
}


def is_present(g, nid):
    return True


_speaker = [None]


def talk_header():
    ui.rule("Talking with %s" % NPCS[_speaker[0]]["name"], color="sky")


def talk(g, nid):
    _speaker[0] = nid
    talk_header()
    globals()["talk_" + nid](g)
    g.flags["talked_" + nid] = True


def has_news(g, nid):
    """True when this person has something new to say, so the area screen can suggest talking."""
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
        return not f.get("corvin_met") or (g.quest("corvin") == 0 and g.player.has_item("wolf_pelt"))
    if nid == "tallow":
        return not f.get("tallow_met")
    if nid == "wren":
        return not f.get("talked_wren") or (g.quest("wayposts") == "done" and not f.get("wren_ready"))
    return False


# ---------------------------------------------------------------------------- helpers
def topic_menu(options):
    """options: list of (label, key). Returns key or None. Each answer gets a fresh screen."""
    labels = [o[0] for o in options]
    blank()
    i = ui.menu(labels, prompt="Say", cancel_label="Leave")
    if i is not None:
        ui.clear()
        talk_header()
        say("{grey}You: %s{/}" % ui._TAG.sub("", labels[i]))
        blank()
    return None if i is None else options[i][1]


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
        say("{grey}(Tip: 'journal' shows your quests, 'map' shows where you've been, 'help' lists everything.){/}")
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
            line("Maeve", g.rng.choice(RUMOURS), "gold")
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
        return
    tips = [
        "The road forks under the hanging oak. West is the hunters' old camp, east the thicket, north the deepwood.",
        "Light the wayposts. When they burn, the Hollows keep away from the road.",
        "Watch for a wolf dropping low. That's the lunge coming. Brace for it, or hit it first.",
        "Flares. Your old master always said: when in doubt, open the shutters.",
        "There's an old hermit up past the deepwood. Corvin. If he's alive, he'll know what took the Maeve girl.",
    ]
    line("Hesk", g.rng.choice(tips), "bone")


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
        opts = [("Trade (weapons, armour)", "trade")]
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
        if k == "trade":
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
        k = topic_menu(opts)
        if k is None:
            line("Corvin", "Off you go. Don't feed the moths.", "moss")
            return
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


# ---------------------------------------------------------------------------- shops
STOCK = {
    "maeve": ["stew", "draught", "oil", "honeycake"],
    "ilse": ["salts", "draught", "strong_draught"],
    "brann": ["hatchet", "ashwood_rod", "gutting_knife", "jerkin", "hauberk", "wardenplate", "firepot"],
    "corvin": ["honeycake", "salts", "oil", "wolf_fang"],
    "tallow": ["strong_draught", "firepot", "tonic", "smokebomb", "oil", "moth_charm", "lens"],
}
PRICES = {"lens": 140}


def stock_for(g, nid):
    items = list(STOCK[nid])
    if nid == "brann" and "Saltmarsh" in g.flags.get("visited_regions", []):
        items.insert(3, "saltsteel_saber")
    if nid == "tallow" and g.player.lantern.get("lens"):
        items.remove("lens")
    return items


def price(iid):
    if iid in PRICES:
        return PRICES[iid]
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
            labels.append("%s%-26s{/} {gold}%4dg{/}  {grey}%s%s{/}" % (
                "{bwhite}" if afford else "{grey}", it["name"], pr, extra,
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
        items = [iid for iid in p.inventory if ITEMS[iid]["kind"] not in ("key", "page") and ITEMS[iid]["value"] > 0]
        if not items:
            return note or "{grey}You have nothing to sell.{/}"
        labels = []
        offers = []
        for iid in items:
            v = ITEMS[iid]["value"]
            offer = v if (nid == "tallow" and ITEMS[iid]["kind"] == "junk") else max(1, v // 2)
            offers.append(offer)
            labels.append("%s x%d {gold}%dg each{/}" % (ITEMS[iid]["name"], p.inventory[iid], offer))
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
