"""The Reedlight (M6, docs/M6-SPEC.md section 7): the marsh lighthouse south of the Bog Lights.

Ansel Tolliver kept the great lens; Aldric borrowed it for a winter. Oskar the ferryman is Ansel's brother. The heron
that fished at the tower swallowed the stray lens-glass and stands in the lamp room now, where the keeper stood.

Imports of the game's own modules happen inside the functions: npcs imports every area module while it is still
being imported, so a module-level `from ..npcs import line` here would fail.
"""

# ---------------------------------------------------------------------------- scripted moments
def rl_oilhouse_won(g):
    from .. import events, ui
    ui.narrate("The last lampman sets down his hook and sits on a barrel as if his shift were done. In his apron "
               "pocket, a key.")
    events.give_once(g, "rl_tower_key")
    ui.say("{grey}(The tower key. The tower door is at the Tower Foot, east of the Sluice Works.){/}")


def rl_heron_won(g):
    from .. import areas, ui
    ui.narrate("{brine}The heron lowers her head, and the lens slips from her eye into your palm, warm as a swallowed "
               "coal. She looks, for a long breath, at the ruined lamp-cradle. Then she turns and wades out into the "
               "marsh and stands there, grey on grey, like a woman at a window.{/}")
    if areas.give_first(g, "rl_lens_shard"):
        ui.say("{grey}(A shard of the great lens. The heron kept it fifty years for someone to ask.){/}")
    # The nest gear is handed over here, not left on the floor: a fled fight leaves you in the room, and the
    # spec's promise is that it is never reachable early.
    coat = areas.give_first(g, "rl_heronplume_coat")
    pole = areas.give_first(g, "rl_keepers_pole")
    if coat or pole:
        ui.say("{grey}(Under the plumes of her bed: a coat sewn from her own moulted feathers, and the keeper's "
               "snuffing pole, laid by like something she meant to give back.){/}")


def rl_fog_parted(g):
    from .. import ui
    ui.narrate("{brine}You open the book and let the light out. The fog does not lift, it parts, as a curtain parts "
               "for someone it recognises.{/}")


AFTER_FIXED = {
    "rl_oilhouse_dead": rl_oilhouse_won,
    "rl_heron_dead": rl_heron_won,
}

UNLOCK = {
    ("bog_lights", "s"): rl_fog_parted,
}

BOSS_TIPS = {
    "rl_lantern_room": "She is weak to Earth and Shadow, not fire. Flares work (she is Hollow). Guard Gulp; Lens Flare "
                       "blinds, so cleanse with Smelling Salts.",
}


# ---------------------------------------------------------------------------- Oskar
def rl_oskar_topics(g):
    """Oskar will talk about the lighthouse once the heron is down, or once you carry his brother's receipt."""
    if g.flags.get("rl_heron_dead") or g.player.has_item("rl_receipt"):
        return [("Ask about the Reedlight", rl_ask_oskar)]
    return []


def rl_ask_oskar(g):
    from .. import ui
    from ..npcs import line
    f = g.flags
    has_receipt = g.player.has_item("rl_receipt")
    if not f.get("rl_oskar_spoke"):
        f["rl_oskar_spoke"] = True
        ui.narrate("Oskar pushes back his sou'wester for the first time. He is not the face you imagined. He is a man who "
                   "looks like someone who has been waiting at a window.")
        line("Oskar", "Ansel.", "brine")
        ui.narrate("The water slaps the jetty twice before he goes on.")
        line("Oskar", "My brother. I pole the same line every night in case the light comes back. It's not for the "
                      "boats. ...It's so I'll know where I am.", "brine")
    else:
        line("Oskar", "The line is the same. I pole it anyway.", "brine")
    if has_receipt and not f.get("rl_oskar_receipt"):
        f["rl_oskar_receipt"] = True
        ui.say("{grey}You hold out the receipt. He reads it by your lantern, his lips moving over the last line.{/}")
        line("Oskar", "Held in trust. He always did like a good receipt.", "brine")


def rl_rumours(g):
    if g.flags.get("rl_oskar_spoke"):
        return ["Oskar said his brother's name to a customer yesterday. The whole tavern went quiet."]
    return []


def rl_oskar_news(g):
    """The '!' marker over Oskar: the heron is down or the receipt is in hand, and he has not yet been asked."""
    f = g.flags
    return bool((f.get("rl_heron_dead") or g.player.has_item("rl_receipt")) and not f.get("rl_oskar_spoke"))


TOPICS = {
    "oskar": rl_oskar_topics,
}

EXTRA_NEWS = {"oskar": rl_oskar_news}

RUMOURS = rl_rumours


# ---------------------------------------------------------------------------- the journal
def rl_objectives(g, add):
    f = g.flags
    if "reedways" in g.visited and not f.get("rl_fog_burned"):
        add("South of the Bog Lights a fog bank hides something. A Fire or Light book, equipped, would burn it off",
            "bog_lights", True)
    if f.get("rl_fog_burned") and not f.get("rl_oilhouse_dead"):
        add("The Reedlight: find the tower key in the oil-house", "rl_oilhouse", True)
    if f.get("rl_oilhouse_dead") and not f.get("rl_heron_dead"):
        add("The Lens-Eyed Heron waits in the lamp room", "rl_lantern_room", True)


OBJECTIVES = rl_objectives


# ---------------------------------------------------------------------------- checks
def rl_check():
    """The Reedlight's own rules: nothing hollow is weak to light, every heavy move has a tell."""
    from ..content import ENEMIES, ROOMS
    errs = []
    for eid, e in ENEMIES.items():
        if not eid.startswith("rl_"):
            continue
        if "hollow" in e.get("tags", []) and "light" in e.get("weak", []):
            errs.append("%s is hollow and weak to light" % eid)
        for m in list(e.get("moves", [])) + [m for ph in e.get("phases", []) for m in ph.get("moves", [])]:
            if m.get("kind") in ("heavy", "charge") and not m.get("tell"):
                errs.append("%s: %s has no tell" % (eid, m.get("name")))
    for rid, r in ROOMS.items():
        if r["region"] == "The Reedlight" and not (r.get("desc") and r.get("features")):
            errs.append("room %s needs a desc and features" % rid)
    return errs


CHECK = rl_check
