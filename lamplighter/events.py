"""Scripted story beats: boss rooms, unlocks, the rescue, and the endings."""
import time

from . import areas, powerroll, town, ui
from .ui import say, blank, narrate
from .npcs import line


def give_once(g, iid):
    """Key items are never handed over twice, even when a boss is called back."""
    if not g.player.has_item(iid):
        g.give(iid)


# ============================================================================ hooks
def on_leave(g, src, dest):
    found, _ = areas.lookup("LEAVE", (src, dest), g)
    if found:
        return
    if src == "docks" and dest == "marsh_edge":
        if not g.flags.get("oskar_met"):
            g.flags["oskar_met"] = True
        narrate("{brine}Oskar poles you out across the black water. Nobody speaks. Halfway over, something large "
                "passes under the boat, and Oskar lifts his pole out of the water until it has gone.{/}")
    elif src == "marsh_edge" and dest == "docks":
        narrate("{brine}You shout. After a long while, Oskar's ferry comes out of the dark to fetch you.{/}")


def on_unlock(g, rid, d):
    found, _ = areas.lookup("UNLOCK", (rid, d), g)
    if found:
        return
    if (rid, d) in (("square", "d"), ("well_bottom", "u"), ("well_bottom", "e")):
        if not g.flags.get("embers_set"):
            g.flags["embers_set"] = True
            narrate("{amber}You press the three Embers into the flame-shaped sockets. They flare, one after "
                    "another, and the seal opens with a sound like a long-held breath let out.{/}")
            if g.quest("main") in (1, 2):
                g.set_quest("main", 3)
    elif (rid, d) == ("kitchens", "s"):
        narrate("{brine}You open the book and let the cold out of it. Frost races across the molten door, a hiss, a crack, "
                "and the iron sets like a pond freezing. The stair beyond breathes cool air.{/}")
    elif (rid, d) == ("chapel_steps", "n"):
        narrate("{brine}The Tide Key turns with a grinding of salt. The bronze doors swing inward, and seawater "
                "pours out over your boots.{/}")


def on_examine(g, rid, keyword):
    pass


def on_rest(g):
    areas.call_each("ON_REST", g)
    if g.room_id == "hall" and g.quest("main") not in (-1, 0, "done"):
        lines = ["Orrin mutters in his sleep. 'Aldric... the wick, Aldric...'",
                 "Orrin is awake when you get up. 'Still here,' he says. 'So am I.'",
                 "You dream of a sunrise. You had forgotten what one looked like."]
        say("{grey}%s{/}" % g.rng.choice(lines))


def after_fixed(g, flag):
    found, _ = areas.lookup("AFTER_FIXED", flag, g)
    if found:
        return
    if flag == "golem_dead":
        narrate("The Ore-Warden crumbles into rubble. Behind it, the starsteel seam glitters, and with your hook "
                "you pry loose a lump of black, starry metal.")
        if g.quest("starsteel") != "done":
            give_once(g, "starsteel_ore")
        if g.quest("starsteel") == -1:
            say("{grey}(Brann the smith would want to see this.){/}")
    elif flag == "usher_dead":
        narrate("The Pale Usher folds up like a dropped coat and is gone. The way to the Lightwell is open.")
    elif flag == "steward_dead":
        narrate("The Steward closes his ledger with a small, final sound. 'Departed,' he writes. 'All guests departed.' "
                "He is ash before the ink dries. On the lectern where he stood, a heavy iron key shines.")
        give_once(g, "court_key")
        say("{grey}(The Crown Key opens the throne room, east of this hall. Somewhere in the Court, a smith has heard the "
            "bell stop.){/}")
    elif flag == "nave_guard":
        say("{grey}The nave falls quiet. Up the steps to the north, someone is still preaching.{/}")


def on_enter(g, rid, first):
    """Return True if the event took over the room (so no fixed fight / encounter follows)."""
    fn = globals().get("enter_" + rid)
    if fn:
        return bool(fn(g, first))
    found, result = areas.lookup("ENTER", rid, g, first)
    return bool(result) if found else False


# ============================================================================ rooms
def enter_tavern(g, first):
    if g.flags.get("wren_following") and not g.flags.get("wren_home"):
        g.flags["wren_following"] = False
        g.flags["wren_home"] = True
        blank()
        narrate("Wren slips past you into the warm room. Maeve looks up, and the glass falls out of her hand.")
        narrate("Nobody in the Drowned Moth says anything for a while. The fisherman wipes his eyes and pretends "
                "it's the smoke.")
        line("Maeve", "You brought her home. You brought my girl home.", "gold")
        line("Maeve", "Here. It's not enough. It's all I've got. And you eat free here for as long as I live.", "gold")
        g.player.gold += 60
        say("{gold}+60 gold{/}")
        g.give("draught", 3)
        g.give("honeycake", 2)
        g.set_quest("wren", "done")
        g.award_xp(50)
        if g.quest("wayposts") != "done":
            say("{grey}(Wren seems to want to talk to you.){/}")
    return False


def enter_square(g, first):
    if g.shards() == 3 and not g.flags.get("embers_set") and not g.flags.get("hint_grate"):
        g.flags["hint_grate"] = True
        say("{amber}The Embers in your pack grow hot as you pass the Old Well. The grate is waiting for them. "
            "(Go down.){/}")
    return False


def enter_well_bottom(g, first):
    if first:
        say("{grey}Far above, you can hear the creak of the town's lampposts. You are right under Hollowmere.{/}")
    return False


def enter_mother_grove(g, first):
    if g.flags.get("mother_dead"):
        if g.flags.get("wren_following"):
            say("{grey}Wren stays close behind you, holding on to your coat.{/}")
        return False
    blank()
    narrate("The pool shivers. Out of the white trees steps a doe the size of a cart-horse, pale as bone, with "
            "antlers like a burnt forest. In the cage of roots behind her, a small figure presses against the bars.")
    narrate("{gold}A girl. Yellow hair. A candle stub in her fist, long gone out.{/}")
    narrate("The Antlered Mother lowers her head toward your lantern, and a glow pulses in her crown: an Ember Shard, "
            "set there like a jewel.")
    outcome = g.fight(["antlered_mother"], intro="The Mother screams, and the birches shake.")
    if outcome != "win":
        return True
    g.flags["mother_dead"] = True
    blank()
    narrate("The Antlered Mother sinks down beside the pool. For a moment she is only a white doe, tired and old. "
            "She looks at your lantern without hate. Then she is ash.")
    narrate("{amber}In the ash lies a splinter of warm gold light.{/}")
    give_once(g, "ember_wood")
    narrate("The root cage withers and cracks. The girl stumbles out.")
    line("Wren", "You're a lamplighter. You're a real lamplighter. Is it gone? Can I go home? I want my mam.", "gold")
    if g.quest("wren") != "done":
        g.flags["wren_following"] = True
    if g.quest("wren") == -1:
        g.quests["wren"] = 0
    g.set_quest("wren", 2)
    say("{grey}(Wren will follow you. Take her home to the Drowned Moth in Hollowmere.){/}")
    return True


def enter_reeve_house(g, first):
    if g.flags.get("reeve_dead"):
        return False
    blank()
    narrate("At the head of the table the drowned Reeve lifts his face out of the water. His chain of office clinks. "
            "A green bronze key hangs from it.")
    line("Reeve Haskel", "Visitor. You are behind on your tithe. Everyone is behind on their tithe.", "brine")
    line("Reeve Haskel", "The chapel must be fed. The Bishop must be fed. Pay what you owe.", "brine")
    outcome = g.fight(["reeve_haskel"], intro="The Reeve rises, dragging a boat-hook out of the water.")
    if outcome != "win":
        return True
    g.flags["reeve_dead"] = True
    narrate("The Reeve slumps back into his chair, and is still. You lift the chain from his neck.")
    give_once(g, "tide_key")
    say("{grey}(The Tide Key opens the chapel doors, east of the village.){/}")
    return True


def enter_bishop_altar(g, first):
    if g.flags.get("bishop_dead"):
        return False
    blank()
    narrate("The Drowned Bishop stands at the altar with his back to you, swinging his censer, preaching to the "
            "empty, flooded pews. In the censer a coal of gold light glows.")
    line("The Bishop", "And the sea said, I shall have it all. And I said, then have it holy.", "brine")
    narrate("He turns. Water runs from his eyes like tears that never stop.")
    line("The Bishop", "A light. In my chapel. How dare you be warm here.", "brine")
    outcome = g.fight(["drowned_bishop"], intro="The floodwater begins to rise.")
    if outcome != "win":
        return True
    g.flags["bishop_dead"] = True
    narrate("The Bishop falls to his knees on the altar steps. The water around him goes still, and then drains "
            "away through the cracks, all of it, as if a plug has been pulled from the world.")
    narrate("{amber}His censer rolls to your feet, and the Ember inside it rolls out.{/}")
    give_once(g, "ember_tide")
    narrate("Below, in the nave, you hear stone grind. The salt seal on the crypt stair has cracked open.")
    return True


def enter_ash_choir(g, first):
    if g.flags.get("choir_dead"):
        return False
    blank()
    narrate("The three singers turn as one. Their chord bends toward you, and the coal of light between them "
            "pulses in time with it: the last Ember.")
    narrate("{grey}They are not angry. They are only singing, and they will not stop, and the song wants your flame "
            "to join it.{/}")
    outcome = g.fight(["alto", "tenor", "bass"], intro="The chord rises.")
    if outcome != "win":
        return True
    g.flags["choir_dead"] = True
    narrate("The last note fades. For the first time in fifty years the cavern is silent, and the silence is "
            "enormous. The Ember drifts down into your open hand.")
    give_once(g, "ember_ash")
    return True


# ============================================================================ the Ember Court
def enter_throne_room(g, first):
    if g.flags.get("queen_dead"):
        return False

    def prologue():
        blank()
        if not g.flags.get("met_queen"):
            g.flags["met_queen"] = True
            narrate("The doors open on a hall full of people standing perfectly still. At the far end, on a throne of black "
                    "glass, a queen in a gown of slow fire raises her head. Behind her the cold bowl of the beacon waits.")
            line("The Cinder Queen", "A guest. At last. Do sit. We were only waiting for the music.", "ember")
        else:
            narrate("The dancers part for you without turning their heads. The Queen rises from her throne, and the "
                    "room remembers how to burn.")

    return powerroll.boss_scene(g, "cinder_queen", "queen_dead", "stewards_hall", _queen_won,
                                intro="The music begins, from nowhere.", prologue=prologue)


def _queen_won(g, power):
    blank()
    narrate("The Queen stops mid-step. For a moment she is only a woman in a burnt dress who has been dancing for a very "
            "long time. 'Is it over?' she asks. 'Aldric said he would come back for the last one.'")
    narrate("{amber}She bows, and the fire in her gown goes out, and the dancers sit down one by one on the glass floor "
            "as though a string had been cut.{/}")
    gems = {3: 1, 4: 2}.get(powerroll.band_index(power), 0)
    if gems:
        g.player.gems += gems
        say("{sky}+%d gems{/} {grey}(she was %s){/}" % (gems, powerroll.band(power)[0].lower()))
    say("{grey}(The beacon bowl stands cold at the foot of the dais. Type {gold}light{/}{grey} to relight it.){/}")


def after_beacon(g, region):
    if region == "Ember Court":
        narrate("{gold}The whole Court is lit. You can rest anywhere inside it now, and nothing will ambush you. Down the "
                "corridor you hear Pell's keys, jangling for the first time in a hundred years.{/}")
        if g.flags.get("steward_dead") and not town.is_invited(g, "ember_smithy") and not town.is_built(g, "ember_smithy"):
            say("{grey}(Tamsin, the smith in the Court Forge, has not heard yet.){/}")
    areas.lookup("AFTER_BEACON", region, g)


# ============================================================================ the end
def enter_lightwell(g, first):
    p = g.player
    if g.flags.get("ending"):
        return False
    blank()
    ui.rule("THE LIGHTWELL", color="hollow")
    narrate("The man on the black glass throne lifts his head. His face is grey and kind and very tired. "
            "His lantern is lit, but the flame inside it is black, and it drinks the light around it.")
    line("The Hollow King", "Another one. Did Orrin send you? Of course he did. He never came himself.", "hollow")
    line("The Hollow King", "Sit down, little lamplighter. You've walked such a long way in the dark.", "hollow")
    named = False
    can_name = p.has_item("page6") or g.flags.get("orrin_aldric")
    while True:
        opts = [("\"Who are you?\"", "who"), ("\"What happens if I give my flame to the Well?\"", "flame"),
                ("\"What are you offering?\"", "offer")]
        if can_name and not named:
            opts.append(("{gold}\"Aldric.\"{/}", "name"))
        opts.append(("{bred}Raise your lantern and fight{/}", "fight"))
        k = ui.menu([o[0] for o in opts], prompt="Say", allow_cancel=False)
        k = opts[k][1]
        if k == "who":
            line("The Hollow King", "I am the king of the long night. I am the end of burning. Every Keeper before me "
                                    "gave their flame to that hole in the ground, and every one of them went out. "
                                    "I was the first one clever enough to say no.", "hollow")
        elif k == "flame":
            line("The Hollow King", "It eats you. Your flame goes in, and the sun comes back for another fifty years, "
                                    "and you are gone. Is that fair? Is that a thing to ask of anyone?", "hollow")
        elif k == "offer":
            line("The Hollow King", "Lay your lantern down. Sit with me. The dark is gentle, I promise you. No one "
                                    "will ever have to burn again. Not you. Not the girl. Not anyone.", "hollow")
            if ui.confirm("{hollow}Lay your lantern down?{/}"):
                return ending_crown(g)
            say("{grey}You keep your grip on the lantern.{/}")
        elif k == "name":
            named = True
            g.flags["king_named"] = True
            narrate("You say the name. Aldric.")
            narrate("{gold}The King flinches as if you struck him. For one breath his eyes are clear, and he "
                    "looks at his own black lantern with horror.{/}")
            line("Aldric", "That's... my name. Orrin's boy. Orrin's... no. NO. Don't make me remember.", "hollow")
            narrate("The black flame swells again, but something in him is cracked now. "
                    "{gold}(The King is weakened.){/}")
        elif k == "fight":
            break
    return final_battle(g)


def final_battle(g):
    from .combat import Combat
    p = g.player
    wren_comes = g.flags.get("wren_ready") and g.flags.get("wren_home")

    def on_phase(cmb, enemy, idx):
        if "king" not in enemy.tags:
            return
        if idx == 1 and wren_comes and not g.flags.get("wren_helped"):
            g.flags["wren_helped"] = True
            blank()
            narrate("{gold}Footsteps on the stair behind you. A small light, then a bigger one: Wren, with Maeve's "
                    "best lamp held over her head in both hands.{/}")
            line("Wren", "Two hands on the wick! That's what Orrin said! I'm here!", "gold")
            narrate("{byellow}Her lamp blazes. The dark around the King tears like wet paper.{/}")
            enemy.remove("shroud")
            enemy.apply("exposed", 2)
            healed = p.heal(int(p.max_hp * 0.3))
            p.add_oil(40)
            say("{bgreen}Wren's light warms you. (+%d health, +40 oil){/} {grey}(The shroud is torn away.){/}" % healed)

    cmb = Combat(g, ["hollow_king"], intro="The black flame rises.", on_phase=on_phase)
    king = cmb.enemies[0]
    if g.flags.get("king_named"):
        king.max_hp = int(king.max_hp * 0.85)
        king.hp = king.max_hp
        king.apply("stun", 1)
        say("{gold}Aldric hesitates, staring at his own black lantern. (He loses his first move.){/}")
    outcome = cmb.run()
    if outcome != "win":
        g.death()
        return True
    return victory(g)


def victory(g):
    p = g.player
    blank()
    narrate("The Hollow King falls back onto his throne of black glass, and it shatters under him.")
    if g.flags.get("king_named"):
        line("Aldric", "Orrin's apprentice. You're braver than both of us. Tell him... tell him I'm sorry. "
                       "Tell him it doesn't hurt as much as we thought.", "bone")
        narrate("Aldric's black lantern cracks, and a little ordinary yellow flame flickers inside it for a heartbeat "
                "before it goes out.")
    else:
        narrate("The black lantern rolls from his hand, cracks, and goes dark. He does not say anything else.")
    narrate("Before you, the Lightwell glows like the last coal in a grate. It is waiting.")
    wren_here = g.flags.get("wren_helped")
    opts = [("Give your own flame to the Well", "give")]
    if wren_here:
        opts.insert(0, ("{gold}Take Wren's hand, and give the flame together{/}", "share"))
    opts.append(("Take the Embers and walk away", "leave"))
    blank()
    k = ui.menu([o[0] for o in opts], prompt="Choose", allow_cancel=False)
    k = opts[k][1]
    if k == "share":
        return ending_dawn(g)
    if k == "give":
        return ending_keeper(g)
    return ending_thief(g)


def epilogue_people(g):
    out = []
    if g.quest("wren") == "done":
        out.append("Maeve keeps the brightest tavern in the north, and Wren never forgets a candle again.")
    elif g.flags.get("mother_dead"):
        out.append("Wren followed you as far as the wood's edge, then went home alone. She made it. Barely.")
    else:
        out.append("Wren was never found. Maeve still sets a place for her.")
    if g.quest("starsteel") == "done":
        out.append("Brann hangs up his hammer. He says he has made the one thing he was born to make.")
    else:
        out.append("Brann goes on making hatchets, and dreaming of stars in the rock.")
    if g.quest("petals") == "done":
        out.append("The Chapel of the Ember burns bright, and Sister Ilse finally sleeps through the night.")
    else:
        out.append("Ilse's flame lasts the winter, just.")
    if g.quest("wayposts") == "done":
        out.append("The Tollroad stays lit, and by spring the carts are coming up it again.")
    return out


def finish(g, title, color, paragraphs):
    blank()
    ui.rule(title, color=color, char="═")
    for para in paragraphs:
        narrate(para)
        blank()
    if title != "THE HOLLOW CROWN":
        for t in epilogue_people(g):
            say("{grey}·{/} %s" % t)
        blank()
    s = g.stats
    minutes = int((time.time() - g.started) / 60)
    say("{ash}%s the %s · level %d · %s difficulty{/}" % (g.player.name, g.player.cls_name, g.player.level, g.diff_name))
    say("{ash}Hollows slain: %d · battles won: %d · deaths: %d · steps taken: %d · journal pages: %d/6{/}" % (
        s.get("kills", 0), s.get("battles", 0), s.get("deaths", 0), g.moves,
        sum(1 for i in range(1, 7) if g.player.has_item("page%d" % i))))
    endings = {"dawn": "Dawn", "keeper": "The Last Lamplighter", "thief": "The Long Dark", "crown": "The Hollow Crown"}
    say("{ash}Ending reached: %s. There are four.{/}" % endings[g.flags["ending"]])
    blank()
    say("{b}{amber}THE END{/}{/}", indent=4)
    g.set_quest("main", "done", quiet=True)
    if g.flags["ending"] == "crown":
        g.over = True              # the Crown is a true ending; reload your last rest to carry on
        return True
    blank()
    say("{gold}The story is told, and the world remains. Hollowmere is yours to keep building, and the Wizard's Shop is "
        "open.{/}")
    ui.pause()
    g.finish_story()
    return True


def ending_dawn(g):
    g.flags["ending"] = "dawn"
    return finish(g, "DAWN", "gold", [
        "You kneel at the edge of the Well, and Wren kneels beside you, and you hold the lantern between you, four "
        "hands on the brass.",
        "You tip the flame in together.",
        "{amber}It doesn't take you. It takes half of what you have, and half of what Wren has, and it is enough. "
        "Orrin was right. A flame shared is not a flame halved.{/}",
        "The Lightwell roars up white and gold, and the whole hill shakes, and far above, for the first time in "
        "forty days, the sky over Hollowmere turns grey, then pink, then gold.",
        "You walk up out of the Old Well into the square with Wren beside you, both of you blinking, and the whole "
        "town is standing in the street with their faces turned to the east. Orrin is there too, on Hesk's arm, "
        "out of bed for the first time in a month.",
        "{gold}He looks at the two of you, and at the sunrise, and he laughs. 'Two Keepers,' he says. "
        "'Well. That's new.'{/}",
    ])


def ending_keeper(g):
    g.flags["ending"] = "keeper"
    return finish(g, "THE LAST LAMPLIGHTER", "amber", [
        "You kneel at the edge of the Well. You open your lantern. You think of Orrin, and the Hall, and the empty "
        "bunks, and the square full of little yellow circles you lit by hand.",
        "You tip the flame in.",
        "{amber}It takes you gently. It doesn't hurt. Aldric was right about that much.{/}",
        "The Lightwell roars up white and gold, and far above, the sky over Hollowmere breaks open into the first "
        "sunrise in forty days. In the square, people come out of their houses with their hands over their eyes.",
        "Every evening after, when the lamps in the square are lit, they burn a little brighter than they should. "
        "Old Orrin says that is you. Nobody argues with him.",
    ])


def ending_thief(g):
    g.flags["ending"] = "thief"
    return finish(g, "THE LONG DARK", "night", [
        "You look at the dying Well. You look at your own small, warm flame.",
        "You pick up the three Embers, and you turn, and you climb.",
        "Behind you, the Lightwell sighs, and settles, and goes out.",
        "{night}You walk out of Hollowmere by the Tollroad with the Embers in your pack, and they keep you warm for "
        "a long time. Behind you, the town's lamps go out one by one, and nobody lights them.{/}",
        "Somewhere far to the south, they say, there is still a sun. You hope you are walking toward it.",
    ])


def ending_crown(g):
    g.flags["ending"] = "crown"
    return finish(g, "THE HOLLOW CROWN", "hollow", [
        "You set your lantern down on the black glass. The King smiles, and reaches over, and closes its shutters.",
        "{hollow}It is so quiet. It is so gentle. You can't remember why you were afraid.{/}",
        "Years later, another lamplighter comes down the stair with a little light held up in front of them. "
        "There are two thrones now.",
        "You lean forward, and you smile, and you say: 'Sit down, little lamplighter. You've walked such a long way "
        "in the dark.'",
    ])
