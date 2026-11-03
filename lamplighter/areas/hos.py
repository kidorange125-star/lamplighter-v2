"""The Moth-Saint's Hospice (Weeping Wood extension): a pilgrims' house behind the Shrine of the Moth.

Aldric borrowed the Hospice's waylamp fifty years ago. Corvin was the lay-brother who held the ladder.
The Almoner keeps the belfry key; the Vesper Moth waits in the belfry. See docs/M6-SPEC.md section 6.

Imports of the game's own modules are lazy: npcs imports every area module while it is still being imported.
"""

REGION = "The Moth-Saint's Hospice"


# ============================================================================ fixed fights
def almoner_dead(g):
    from .. import events
    from ..ui import narrate, say
    narrate("The Almoner sets down his bowl. 'Dismissed,' he says, to nobody, and the fifty bowls go cold at once.")
    events.give_once(g, "hos_belfry_key")
    say("{grey}(The belfry key. The scriptorium bolt has slid back.){/}")
    if not g.flags.get("hos_gems_almoner"):
        g.flags["hos_gems_almoner"] = True
        g.player.gems += 2
        say("{sky}+2 gems{/} {grey}(first time you have sent the Almoner's guests home){/}")


def vesper_dead(g):
    from .. import areas
    from ..ui import narrate
    narrate("{moss}The great moth settles on your lantern, light as a hand. For a moment it is only a moth, and your "
            "flame is only a flame. Then it opens its wings and goes up through the belfry roof, and does not come "
            "back, and the sky behind it is very slightly less grey.{/}")
    areas.give_first(g, "hos_waylamp")


AFTER_FIXED = {
    "hos_almoner_dead": almoner_dead,
    "hos_vesper_dead": vesper_dead,
}

BOSS_TIPS = {
    "hos_belfry": "She is a Hollow, so flares do double and blind her. She drinks oil with Drink the Flame: keep 30 "
                  "or more in the lantern. Guard Dusk.",
}


# ============================================================================ Corvin
def _corvin_told(g):
    from .. import npcs
    npcs.line("Corvin", "I don't walk it. I used to sweep it. I was the Hospice's lay-brother, and when the pilgrims "
                        "stopped coming I went deeper in, and the wood took the rest of me.", "moss")
    npcs.line("Corvin", "But the night the Keeper came for the lamp, I held the ladder. He was so polite. Nobody warned "
                        "us that polite men can be wrong.", "moss")
    g.flags["hos_corvin_told"] = True


def _corvin_vesper(g):
    from .. import npcs
    from ..ui import say
    npcs.line("Corvin", "She came to your lantern? Of course she did.", "moss")
    npcs.line("Corvin", "...You'll think me a sentimental old fool. The raven is her great-grandson.", "moss")
    g.flags["hos_corvin_vesper"] = True
    if not g.flags.get("got_hos_corvin_gift"):
        g.flags["got_hos_corvin_gift"] = True
        npcs.line("Corvin", "Here. Take these. Pears and honey, the Hospice way. She would have wanted somebody fed.",
                  "moss")
        g.give("honeycake", 3)
    else:
        say("{grey}Corvin nods, and looks past you, east, for a while.{/}")


def _corvin_receipt(g):
    from .. import npcs
    from ..ui import say
    say("{grey}Corvin holds the receipt at arm's length, then close. He reads it twice. The raven, on the lintel, "
        "shifts its feet.{/}")
    npcs.line("Corvin", "He minds. He does mind.", "moss")
    say("{grey}A long silence.{/}")
    npcs.line("Corvin", "Thank you for writing that down.", "moss")
    g.flags["hos_corvin_receipt"] = True


def corvin_topics(g):
    out = []
    if g.flags.get("lit_moth_shrine") and not g.flags.get("hos_corvin_told"):
        out.append(("Ask about the road behind the shrine", _corvin_told))
    if g.flags.get("hos_vesper_dead") and not g.flags.get("hos_corvin_vesper"):
        out.append(("Tell Corvin about the Vesper Moth", _corvin_vesper))
    if g.player.has_item("hos_receipt") and not g.flags.get("hos_corvin_receipt"):
        out.append(("Show Corvin the receipt", _corvin_receipt))
    return out


TOPICS = {"corvin": corvin_topics}


def RUMOURS(g):
    if g.flags.get("hos_corvin_told"):
        return ["Corvin's started sweeping the path behind the shrine. Says he's spring-cleaning. It's October."]
    return []


# ============================================================================ objectives
def OBJECTIVES(g, add):
    f = g.flags
    if "moth_shrine" in g.visited and not f.get("lit_moth_shrine"):
        add("Behind the Shrine of the Moth, a road runs east. Light the waypost to see it", "moth_shrine", True)
    if "hos_path" in g.visited and not f.get("hos_almoner_dead"):
        add("The Hospice: the Almoner keeps the belfry key in the refectory", "hos_refectory", True)
    if f.get("hos_almoner_dead") and not f.get("hos_vesper_dead"):
        add("The Vesper Moth waits in the belfry", "hos_belfry", True)


# ============================================================================ validator
def CHECK():
    """Flares double against hollows, so no hollow in this area may list light as a weakness."""
    from ..content import ENEMIES
    errs = []
    for eid, e in ENEMIES.items():
        if eid.startswith("hos_") and "hollow" in e.get("tags", []) and "light" in e.get("weak", []):
            errs.append("enemy %s is a hollow weak to light" % eid)
    return errs
