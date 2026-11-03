"""The apex arc: the Sixfold Chart unlocks the apex recipe, Hearts feed the Grand Binding, and failures warm the apex.

The rules live where they always did: `spells.py` (Grand Binding cost, apex heat), `data/spells.json` (the numbers) and
`magic_ui.py` (the menus). This module owns the one scripted beat, Mirelle reading the chart, and the checks around it.
See docs/M6-SPEC.md section 12.

The unlock is the last beat of the Vigil's chain: the player holds the chart (taken from the camera obscura), Hale has
read it (flag `vg_chart_read`) and his almanac is built in Hollowmere (so he can climb Mirelle's stairs).
"""

CHART = "vg_sixfold_chart"
READ_FLAG = "vg_chart_read"
ALMANAC = "vg_almanac"
UNLOCK_FLAG = "apex_unlocked"          # the flag spells.json `apex.needs_flag` already reads


# ---------------------------------------------------------------------------- the unlock
def unlock_missing(g):
    """What stands between the player and the apex unlock, as short phrases. Empty when Mirelle can be shown the chart."""
    from .. import town
    if g.flags.get(UNLOCK_FLAG):
        return ["already unlocked"]
    out = []
    if not g.player.has_item(CHART):
        out.append("the Sixfold Chart")
    if not g.flags.get(READ_FLAG):
        out.append("Hale to read it")
    if not town.is_built(g, ALMANAC):
        out.append("Hale's almanac built")
    return out


def unlock_ready(g):
    """True when the 'Show her the Sixfold Chart' option belongs in Mirelle's menu."""
    return not unlock_missing(g)


def unlock_scene(g):
    """Mirelle reads the chart. Sets `apex_unlocked`; the chart stays in the pack. Returns the note for the menu."""
    from .. import npcs, ui
    if not unlock_ready(g):
        return ""
    ui.clear()
    ui.rule("THE SIXFOLD CHART", color="hollow")
    ui.narrate("Mirelle sweeps her desk clear with one arm, pencils and all, and spreads the Sixfold Chart across it. "
               "She pins the corners with a teacup, a hollow core and her own elbow.")
    ui.narrate("Hale has climbed her stairs for the first time. He stops on the top step to get his breath, looks "
               "once at the shelves, and then at nothing but the chart. He reads the order aloud, slowly, the way the "
               "Order read it at dusk. Her pencil starts to move before he has finished.")
    npcs.line("Mirelle", "Six wheels, six lights, and the order they must be held in. It is not a spell. It is a way "
                         "of asking six spells to sing at once.", "hollow")
    npcs.line("Hale", "We said it every evening to begin the watch, and every morning to end it. I had forgotten that "
                      "it ends. The order, I mean. It ends in the morning.", "sky")
    npcs.line("Mirelle", "Sit down. No, take the good chair, it has only a little ink on it.", "hollow")
    npcs.line("Mirelle", "Bring me six books as good as a book can be, one for each wheel, and I will ask them. I "
                         "cannot promise they will answer. Nobody has asked a sixfold thing in fifty years. It may "
                         "be shy.", "hollow")
    g.flags[UNLOCK_FLAG] = True
    ui.say("{gold}The apex recipe is open to you.{/} {grey}Six Godlike books, one of every element. The chart stays in "
           "your pack.{/}")
    ui.pause()
    return "{gold}Mirelle copies the order onto the wall above her desk in pencil. The chart stays in your pack.{/}"


# ---------------------------------------------------------------------------- hooks
def _mirelle_news(g):
    return unlock_ready(g)


EXTRA_NEWS = {"mirelle": _mirelle_news}


def CHECK():
    """The data this package leans on: the Grand Binding, the Hearts, the apex heat and the chart's flags."""
    from ..content import ITEMS, SPELL_RULES
    from ..elements import ELEMENTS
    errs = []
    grand = SPELL_RULES["craft"].get("grand")
    if not grand:
        errs.append("spells.json: craft.grand is missing")
    else:
        if grand.get("heart") != 1:
            errs.append("craft.grand: needs \"heart\": 1")
        if abs(sum(grand["weights"].values()) - 1.0) > 0.01:
            errs.append("craft.grand: weights must sum to 1")
        if "godlike" not in grand["weights"]:
            errs.append("craft.grand: must be able to bind a Godlike book")
    for e in ELEMENTS:
        if "core_heart_" + e not in ITEMS:
            errs.append("missing item core_heart_%s" % e)
    heat = SPELL_RULES["apex"].get("heat")
    if not isinstance(heat, (int, float)) or not 0 < heat <= 1:
        errs.append("apex.heat must be a number in (0, 1]")
    return errs
