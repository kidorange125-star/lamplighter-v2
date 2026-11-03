"""The Vigil (ring 5, area B): the Order of the Open Eye, awake for fifty years.

Aldric borrowed the Signal itself. The Order promised to watch the east until he sent word that it was done, and then
they might close their eyes. He never sent it. The wrongness here is watching: not hollow, over-lit, light with no
night in it. The player's tools are Shadow and Earth books, and a Shadow book is also the key to the one dark room.
Night is a kindness when it ends in morning. See docs/M6-SPEC.md section 10.

Imports of the game's own modules are lazy: npcs imports every area module while it is still being imported.
"""

REGION = "The Vigil"
ANNEX = "The Waking Cellars"
ALMANAC = "vg_almanac"


# ============================================================================ small helpers
def _built(g):
    from .. import town
    return town.is_built(g, ALMANAC)


def _invited(g):
    from .. import town
    return town.is_invited(g, ALMANAC)


def _gems(g, n, why):
    from ..ui import say
    g.player.gems += n
    say("{sky}+%d gem%s{/} {grey}(%s){/}" % (n, "" if n == 1 else "s", why))


# ============================================================================ entering rooms
def enter_ladder(g, first):
    from ..ui import narrate
    if first:
        narrate("A thousand steps. At the top, the cloud ends. And above it, fifty years of daylight with no night at "
                "all. You find, climbing, that you are looking at the sky and can't stop.")
    return False


def enter_lodge(g, first):
    from .. import npcs
    from ..ui import narrate
    if first:
        narrate("Something small and brass unfolds from behind the desk, felt-footed, a ring of keys at its belt. It "
                "inclines its head exactly as far as courtesy requires.")
        npcs.line("Tick", "Welcome to the Vigil. Do not close your eyes. ...(a pause) That is a joke. I was told jokes "
                          "were permitted after the fiftieth year.", "amber")
    return False


def enter_dormitory(g, first):
    from ..ui import narrate
    if first:
        narrate("Two hundred beds, every one made. Hospital corners. Each pillow has a dent from the one night, fifty "
                "years ago, when they lay down and could not close their eyes.")
    return False


# ---------------------------------------------------------------------------- the Chapel of Closed Eyes (mercy)
# the chapel's features follow the story (spec 10.5): the room is shared content, so the text is derived from the
# flags each time the chapel is entered or the Brother sleeps, never stored as state of its own
_CHAPEL_SLEPT = {"altar": "Worn hollow where hands have pressed down eyelids for centuries. Nobody kneels at it now.",
                 "steps|habit": "A grey habit on the altar steps, folded as if slept in."}
_chapel_awake = {}


def _sync_chapel(g):
    from ..content import ROOMS
    feats = ROOMS["vg_chapel"]["features"]
    if not _chapel_awake:
        _chapel_awake.update({k: feats[k] for k in _CHAPEL_SLEPT})
    feats.update(_CHAPEL_SLEPT if g.flags.get("vg_brother_slept") else _chapel_awake)


def enter_chapel(g, first):
    from .. import ui
    from ..ui import blank, narrate, say
    f = g.flags
    _sync_chapel(g)
    if f.get("vg_chapel_done"):
        if f.get("vg_brother_slept"):
            say("{grey}A grey habit on the altar steps, folded as if slept in.{/}")
        return False
    blank()
    narrate("A Brother kneels at the altar in the grey habit of the Order, pressing his own eyelids shut with two "
            "thumbs. They spring open. He does it again.")
    opts = ["Sit with him until he sleeps", "{bred}Raise your lantern and fight{/}", "Leave him be"]
    k = ui.menu(opts, prompt="Choose", allow_cancel=False)
    if k == 0:
        _sit_with_him(g)
    elif k == 1:
        _chapel_fight(g)
    else:
        say("{grey}You step back from the altar. Behind you, very softly, the thumbs go to his eyes again.{/}")
        say("{grey}(He will still be kneeling here when you come back.){/}")
    return True


def _sit_with_him(g):
    from ..content import ENEMIES
    from ..ui import blank, narrate, say
    f = g.flags
    narrate("You sit on the bottom step beside him, not touching, and hum the lamplighters' dusk-song, the one you "
            "learned before you could read. He stops pressing at his eyes. His hands come down into his lap. After a "
            "long while he lies back on the cold stones.")
    narrate("{moss}His breathing slows, and for the first time in fifty years something in this building is "
            "asleep.{/}")
    f["vg_brother_slept"] = True
    f["vg_chapel_done"] = True
    _sync_chapel(g)
    before = g.player.dread
    g.add_dread(-50)
    if g.player.dread != before:
        say("{moss}Dread -%d{/}" % (before - g.player.dread))
    g.player.gold += 180
    say("{gold}+180 gold{/} {grey}(a purse of unspent wages beside the altar){/}")
    g.give("vg_star_plate")                               # give() announces the plate itself
    g.award_xp(2 * ENEMIES["vg_brother"]["xp"])           # the mercy path pays what the two-Brother fight would
    if not f.get("vg_gems_chapel"):
        f["vg_gems_chapel"] = True
        _gems(g, 1, "the first closed eyes in the Vigil")
    blank()


def _chapel_fight(g):
    from ..ui import say
    outcome = g.fight(["vg_brother", "vg_brother"],
                      intro="The Brothers rise from the benches, staffs level. 'Do not close your eyes,' they say, "
                            "together, almost kindly.")
    if outcome == "win":
        g.flags["vg_chapel_done"] = True
        say("{grey}The chapel is quiet. Nobody is kneeling at the altar.{/}")


# ---------------------------------------------------------------------------- the Eye
def enter_eye(g, first):
    from .. import npcs, powerroll
    from ..ui import blank, narrate
    if g.flags.get("vg_eye_dead"):
        return False

    def prologue():
        blank()
        if not g.flags.get("vg_met_eye"):
            g.flags["vg_met_eye"] = True
            narrate("The Chamber is a drum of brass and glass. In the middle, on a mount that has not moved in fifty "
                    "years, the Eye looks at you without any eyelid. A Prior's chain hangs from the mount.")
            npcs.line("The Eye", "Do not close your eyes.", "amber")
        else:
            narrate("The Eye is open, and has not blinked since you left.")
            npcs.line("The Eye", "Do not close your eyes. Not yet. Is it time? Is it time?", "amber")

    return powerroll.boss_scene(g, "vg_prior_eye", "vg_eye_dead", "vg_lens_stair", _won,
                                intro="The Dome fills with white, and the whole Eye turns to look at you.",
                                prologue=prologue)


def _won(g, power):
    from .. import npcs, powerroll
    from ..ui import blank, narrate, say
    blank()
    narrate("The Eye clouds, and clears, and in the glass a man's tired face.")
    npcs.line("The Prior", "Is it dark? Is it dark outside?", "amber")
    say("{grey}You say it is.{/}")
    npcs.line("The Prior", "Oh. Oh, that's what it was supposed to look like.", "amber")
    narrate("Overhead, for the first time in fifty years, the shutters of the Dome roll slowly closed. In the silence "
            "you can hear a hundred pairs of eyes shut in the corridors below. The beacon brazier at the foot of the "
            "mount is cold.")
    gems = {3: 1, 4: 2}.get(powerroll.band_index(power), 0)
    if gems and not g.flags.get("vg_gems_band"):
        g.flags["vg_gems_band"] = True
        _gems(g, gems, "it was " + powerroll.band(power)[0].lower())
    say("{grey}(Type {gold}light{/}{grey} to send the signal.){/}")


ENTER = {
    "vg_ladder": enter_ladder,
    "vg_porters_lodge": enter_lodge,
    "vg_dormitory": enter_dormitory,
    "vg_chapel": enter_chapel,
    "vg_eye": enter_eye,
}


# ============================================================================ fixed fights, locks and the beacon
def orrery_dead(g):
    from .. import events
    from ..ui import narrate, say
    narrate("The Orrery slows, ring by ring, to a stop. The planets settle on their wires. Somewhere above, in the "
            "Dome, a sound like a held breath being let go by a hundred people at once.")
    events.give_once(g, "vg_lens_key")
    say("{grey}(The Orrery's key. The iris at the east end of the Orrery Hall will turn for it.){/}")
    if not g.flags.get("vg_gems_orrery"):
        g.flags["vg_gems_orrery"] = True
        _gems(g, 2, "the first time the sky has stood still")


AFTER_FIXED = {
    "vg_orrery_dead": orrery_dead,
}


def _obscura_opened(g):
    from ..ui import narrate
    narrate("The felt door sighs open. Inside, a darkness so complete it feels like being forgiven.")


UNLOCK = {
    ("vg_mirror_gallery", "s"): _obscura_opened,
}


def vigil_beacon(g):
    from ..ui import narrate
    g.flags["vg_signal_sent"] = True
    narrate("{gold}The Eye's shutters roll open one last time, and the brazier's light goes up through the lens, "
            "enormous and steady, and out across the dark. Far to the south-east, in the valley, a small light "
            "answers. Then another. Then a third: three flashes, the Hollowmere lamplighters' dusk signal, the one "
            "the Order was told to wait for fifty years ago. The Vigil is released.{/}")


AFTER_BEACON = {
    REGION: vigil_beacon,
}

BOSS_TIPS = {
    "vg_eye": "You see its strength before you decide; step back or run for free. It is not a Hollow, so flares do "
              "nothing special: use Shadow and Earth books. It is weak to them; Light and Fire are resisted, and the "
              "Noon field thins Shadow and thickens Light. Kill the Stars it calls. Guard Noon and Noon at Midnight.",
    "vg_orrery_hall": "An elite: no running. It changes alignment every two rounds (the board shows the next one): "
                      "cast what the next alignment is weak to. Guard Great Conjunction. Kill the Stars it calls "
                      "first.",
}


# ============================================================================ objectives
def OBJECTIVES(g, add):
    f = g.flags
    if f.get("beacon_The Frostfair") and not f.get("beacon_" + REGION):
        if "vg_ladder" not in g.visited:
            add("The Signal Stair is open. Climb to the Vigil", "vg_ladder")
        elif not f.get("vg_orrery_dead"):
            add("Find the Orrery's key: the Great Orrery turns in the Orrery Hall", "vg_orrery_hall")
        elif not f.get("vg_eye_dead"):
            add("Face the Unsleeping Eye", "vg_eye")
        else:
            add("Send the signal: light the brazier", "vg_eye")
    if not f.get("vg_chapel_done") and "vg_reckoning_room" in g.visited:
        add("A Brother kneels in the Chapel of Closed Eyes. Sit with him?", "vg_chapel", True)
    if "vg_mirror_gallery" in g.visited and not f.get("vg_obscura_open"):
        add("The Camera Obscura: a Shadow book, equipped, opens the felt door", "vg_mirror_gallery", True)
    if f.get("vg_orrery_dead") and not _built(g):
        if _invited(g):
            add("Hale Teasel will move to Hollowmere once Joss has built his loft", "yard", True)
        else:
            add("Hale Teasel is hiding in the Lens-Cleaner's Cupboard. Ask him, then see Joss",
                "vg_lens_cupboard", True)


# ============================================================================ Hollowmere reacts
def _hesk_nights(g):
    from .. import npcs
    f = g.flags
    if f.get("vg_signal_sent"):
        npcs.line("Hesk", "First proper dusk in a month. Half the town fell asleep in the square. I let them.", "bone")
        f["vg_hesk_slept"] = True
    else:
        npcs.line("Hesk", "Nobody's sleeping on the east lanes. They say it's as if someone's looking at the town "
                          "through a window left open. Everybody's lamps burn too bright; I've half a drum of oil I "
                          "never used.", "bone")
    f["vg_hesk_told"] = True


def hesk_topics(g):
    f = g.flags
    if not f.get("beacon_The Frostfair"):
        return []
    if not f.get("vg_hesk_told") or (f.get("vg_signal_sent") and not f.get("vg_hesk_slept")):
        return [("Ask about the nights", _hesk_nights)]
    return []


def _orrin_signal(g):
    from .. import npcs
    from ..ui import say
    npcs.line("Orrin", "Three flashes from the Hall, I gave the order myself. They were still waiting. They were all "
                       "still waiting.", "amber")
    say("{grey}Orrin looks at the ceiling for a while.{/}")
    npcs.line("Orrin", "...Aldric, you wretched, wonderful man.", "amber")
    g.flags["vg_orrin_told"] = True


def orrin_topics(g):
    f = g.flags
    if f.get("vg_signal_sent") and not f.get("vg_orrin_told"):
        return [("Tell Orrin the signal was answered", _orrin_signal)]
    return []


TOPICS = {"hesk": hesk_topics, "orrin": orrin_topics}
EXTRA_NEWS = {"hesk": lambda g: bool(g.flags.get("beacon_The Frostfair") and not g.flags.get("vg_hesk_told"))}


def RUMOURS(g):
    f = g.flags
    out = []
    if f.get("beacon_The Frostfair") and not f.get("vg_signal_sent"):
        out.append("There's a woman in my back room who hasn't slept in a week and keeps thanking me for the beds.")
    if f.get("vg_signal_sent"):
        out.append("Slept ten hours. Ten! Now I'm cross at all the hours I've lost.")
    return out


SELLS = {"odo": lambda g: ["vg_starglass"] if g.flags.get("vg_eye_dead") else []}
PRICES = {"vg_starglass": 90}


# ============================================================================ people
NPCS = {
    "vg_tick": {"name": "Tick the porter", "aliases": ["tick", "porter", "clockwork", "clockwork porter"],
                "shop": True,
                "desc": "A clockwork porter of brass and felt, a little too formal, with a ring of keys that has not "
                        "been used since the first year of the Vigil."},
    "vg_hale": {"name": "Hale Teasel", "aliases": ["hale", "teasel", "novice", "old man"],
                "where": lambda g: "vg_loft" if _built(g) else None,
                "desc": "A very old man with a creased, sleep-marked face and a candle-end in one hand, peering round "
                        "the edge of a door as though expecting to be shouted at."},
}

STOCK = {
    "vg_tick": ["oil", "strong_draught", "vg_nightcap", "vg_clear_draught", "tonic", "firepot", "smokebomb"],
}

PRESENT = {"vg_hale": lambda g: bool(g.flags.get("vg_orrery_dead")) and not _built(g)}


def _hale_news(g):
    f = g.flags
    if not f.get("vg_orrery_dead"):          # he is hiding until the Orrery falls: the map must not point at him
        return False
    if not f.get("vg_hale_met"):
        return True
    if f.get("vg_signal_sent") and not f.get("vg_flame_given"):
        return True
    return bool(not _invited(g) and not _built(g))


NEWS = {"vg_hale": _hale_news}


def talk_vg_tick(g):
    from .. import npcs
    line, f = npcs.line, g.flags
    if f.get("beacon_" + REGION):
        line("Tick", "I will turn down the beds. All of them. It will take eleven years. That is acceptable.", "amber")
    elif f.get("vg_eye_dead"):
        line("Tick", "The lights may go out now. Would you like the lights out?", "amber")
    elif not f.get("talked_vg_tick"):
        line("Tick", "You are speaking to me directly. That is permitted. How may the Vigil be of service?", "amber")
    else:
        line("Tick", "Eight thousand slippers. Warm. The Brothers do not use them. The slippers are for emergencies.",
             "amber")
    while True:
        k = npcs.topic_menu([("Trade {grey}(supplies for the Vigil){/}", "trade"), ("Ask about the Order", "order"),
                             ("Ask about the fiftieth year", "year")])
        if k is None:
            line("Tick", "Rest well. I will keep the bell." if f.get("vg_eye_dead") else "Do not close your eyes.",
                 "amber")
            return
        if k == "trade":
            npcs.trade(g, "vg_tick")
        elif k == "order":
            line("Tick", "The Order of the Open Eye. We kept the Signal Watch: the dawn pulse of the Lightwell, caught "
                         "on the Heliograph Terrace and relayed by mirror across the north. Three hundred years "
                         "without a missed morning. The Prior was very proud of the record.", "amber")
            line("Tick", "He has not rested since. (a pause) That is also a joke. I am told it is a poor one.",
                 "amber")
        else:
            line("Tick", "Every year, on the night, I knock at the cupboard in the south of the Dormitory and ask "
                         "whether the occupant would like to come out. For forty-nine years he said: Not yet, thank "
                         "you, Tick.", "amber")
            line("Tick", "This year he did not answer. I did not open the door. A porter does not open a door that "
                         "was latched with such care. ...But I have kept the slippers warm.", "amber")


def _hale_first(g):
    from .. import npcs, ui
    from ..ui import narrate, say
    g.flags["vg_hale_met"] = True
    narrate("A face at the crack of a cupboard door, creased with sleep. 'Are they very angry?' he says.")
    npcs.line("Hale", "I fell asleep. The third night of the Vigil. Behind the lens-cleaning rags. Nobody noticed. They "
                      "locked the door to spare me the shame and watched on without me, for fifty years, and I let "
                      "them.", "bone")
    answers = ["\"You were nineteen.\"", "\"Sleep isn't a sin.\"", "\"You're the only one who can tell them it "
                                                                 "ended.\""]
    k = ui.menu(answers, prompt="Say", allow_cancel=False)
    say("{grey}You: %s{/}" % ui._TAG.sub("", answers[k]))
    npcs.line("Hale", "Ah. So I'm the Order's last witness, and I'm a sleeper. The universe has a sense of humour.",
              "bone")


def _hale_flame(g):
    from .. import events, npcs
    from ..ui import narrate
    narrate("He weeps, and thanks you, and does not apologise for either. Then he lights his tiny cupboard-candle "
            "from the Signal and offers you the flame.")
    npcs.line("Hale", "I kept this one for emergencies. This is one. It isn't a loan.", "bone")
    events.give_once(g, "vg_given_flame")
    g.flags["vg_flame_given"] = True


def _hale_chapel(g):
    from .. import npcs
    npcs.line("Hale", "You made one of them close his eyes? ...I'd like to see that. Is it possible to be forgiven by "
                      "a man in his sleep?", "bone")
    g.flags["vg_hale_slept"] = True


def _hale_order(g):
    from .. import npcs
    npcs.line("Hale", "We were such a cheerful lot, you know, for people who never slept. Brother Anselm kept a "
                      "kettle going in the library, and swore the tea was a watch in itself. The Prior had a laugh "
                      "like a door in the wind. I was the youngest. I cleaned the lenses. I was so proud of how clean "
                      "they were.", "bone")


def _hale_chart(g):
    from .. import npcs
    npcs.line("Hale", "This is not a star-map. It's a recipe: the six lights in the order they must be held. Take it "
                      "to the Magician. She'll need me to read the order aloud.", "bone")
    g.flags["vg_chart_read"] = True


def talk_vg_hale(g):
    from .. import npcs
    line, f = npcs.line, g.flags
    if not f.get("vg_hale_met"):
        _hale_first(g)
    elif _built(g):
        line("Hale", "Mind the telescope. It is pointed at nothing in particular. I am out of practice.", "bone")
    else:
        line("Hale", "Is it quiet out there? ...No, don't tell me. I like to imagine.", "bone")
    if f.get("vg_signal_sent") and not f.get("vg_flame_given"):
        _hale_flame(g)
    while True:
        opts = []
        if not _built(g):
            opts.append(("Ask him to come to Hollowmere", "invite"))
        if f.get("vg_brother_slept") and not f.get("vg_hale_slept"):
            opts.append(("Tell him about the Brother in the chapel", "chapel"))
        opts.append(("Ask about the Order", "order"))
        if _built(g):
            opts.append(("Read the almanac", "almanac"))
            if g.player.has_item("vg_sixfold_chart") and not f.get("vg_chart_read"):
                opts.append(("Show him the Sixfold Chart", "chart"))
        k = npcs.topic_menu(opts)
        if k is None:
            line("Hale", "Sleep well. I intend to.", "bone")
            return
        if k == "invite":
            npcs._invite_scene(g, ALMANAC, "Hale",
                               "A town with an east-facing window? ...Yes. Yes, I believe I'd like to see the "
                               "morning. For the first time in my life I won't be too tired to enjoy it.", "",
                               "Tell Joss, in the yard on Market Row. An east window, please.")
        elif k == "chapel":
            _hale_chapel(g)
        elif k == "order":
            _hale_order(g)
        elif k == "almanac":
            almanac(g)
        else:
            _hale_chart(g)


# ============================================================================ the almanac
def almanac(g):
    """Where each Dealer sits today and tomorrow. Free, any number of times."""
    from .. import dealer, navigation
    from ..content import ROOMS
    from ..ui import blank, say
    today = dealer.today()
    for label, day in (("Today", today), ("Tomorrow", today + 1)):
        blank()
        say("{amber}%s{/}" % label)
        for ring in range(1, 6):
            rid = dealer.room_for(g, ring, day)
            if rid is None:
                where = "nowhere (the ring is lit)"
            else:
                where = ROOMS[rid]["name"]
                if day == today and navigation.find_path(g, g.room_id, rid) is None:
                    where += " (you cannot reach it yet)"
            say("  Ring %d: %s" % (ring, where))
    blank()


# ============================================================================ validator
def CHECK():
    """The rules every area obeys (docs/M6-SPEC.md 2.3), asserted for this area's own data."""
    from ..content import ENEMIES, ROOMS
    errs = []
    for eid, e in ENEMIES.items():
        if not eid.startswith("vg_") or "@" in eid:
            continue
        weak = list(e.get("weak", []))
        for st in e.get("attune", {}).get("stances", []):
            weak += st.get("weak", [])
        if "hollow" in e.get("tags", []) and "light" in weak:
            errs.append("enemy %s is a hollow weak to light" % eid)
        if not e.get("desc"):
            errs.append("enemy %s has no desc" % eid)
        moves = list(e.get("moves", [])) + list(e.get("extra_moves", {}).values())
        for ph in e.get("phases", []):
            moves += ph.get("moves", [])
        for m in moves:
            if m.get("kind") in ("heavy", "charge") and not m.get("tell"):
                errs.append("enemy %s: move %s has no tell" % (eid, m.get("name")))
        if "roll" in e and len(e["roll"].get("flavour", [])) != 5:
            errs.append("enemy %s: a rolled boss needs 5 lines of flavour" % eid)
    for rid, r in ROOMS.items():
        if not rid.startswith("vg_"):
            continue
        if not r.get("desc") or not r.get("features"):
            errs.append("room %s needs a desc and features" % rid)
        groups = r.get("enc", {}).get("groups", [])
        if groups:
            total = sum(w for _, w in groups)
            single = sum(w for grp, w in groups if len(grp) == 1)
            if any(len(grp) > 2 for grp, _ in groups):
                errs.append("room %s: a group is bigger than two" % rid)
            if r["region"] in (REGION, ANNEX) and single * 100 < 55 * total:
                errs.append("room %s: single-enemy groups are under 55%% of the weight" % rid)
    return errs
