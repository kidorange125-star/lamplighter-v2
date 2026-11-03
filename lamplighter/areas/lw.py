"""The Lampwrights' Deep (M6, package lw): the Guild's workshop under the mines, and Corm's last foreman.

The door in the Crypt Stair, the Last Foreman's end, Brann's grandfather, and a hint for the boss room. The rooms,
enemies and items are plain JSON (rooms/lw.json and friends). Imports are lazy: npcs imports this module while it is
itself still being imported.
"""


# ---------------------------------------------------------------------------- hooks
def after_foreman(g):
    from .. import ui
    ui.narrate("The Foreman puts down his hammer, as carefully as a man putting down a child. 'Shift's over,' he says, "
               "in Corm's voice, and lowers himself to the floor with his back against the bench, and does not move again.")
    ui.say("{grey}(The key he wore on his apron lies on the bench. The rack-room door to the south will open.){/}")


def door_opens(g):
    from .. import ui
    ui.narrate("{amber}The lens-seats take the light of your relic, one after another, and the bronze folds back "
               "like a flower.{/}")


AFTER_FIXED = {"lw_foreman_dead": after_foreman}
UNLOCK = {("crypt_stair", "s"): door_opens}
BOSS_TIPS = {"lw_workshop": "Water and Ice hurt him, Fire does not. Guard Pour the Crucible: he charges first, "
                            "so you have a turn to brace."}


# ---------------------------------------------------------------------------- Brann
def tell_brann(g):
    from .. import npcs, ui
    line, narrate = npcs.line, ui.narrate
    g.flags["lw_brann_told"] = True
    narrate("You tell him: Corm's workshop, under the mines, behind a door in the Crypt Stair; the long rooms of lamps "
            "with nobody to collect them; the Foreman at the bench. Brann stops mid-swing. Then he puts the hammer "
            "down, which you have never seen him do.")
    if g.flags.get("late_notes_shown"):         # he has already read Corm's notes: he knows the name
        line("Brann", "Corm's workshop. ...So that is where the notes were written. They told me he went down the mine and "
                      "didn't come up. They didn't say he went down to make a lamp for the sun.", "ember")
    else:
        line("Brann", "Corm. My grandfather. ...They told me he went down the mine and didn't come up. They didn't say "
                      "he went down to make a lamp for the sun.", "ember")
    if g.player.has_item("lw_receipt"):
        narrate("He holds out a hand, and you give him the receipt. He reads it standing, then again, slower, with "
                "his thumb under the words. For a while there is only the sound of the forge settling. Then he folds "
                "it along its old creases and gives it back.")
        line("Brann", "Nothing anyone need pay for. ...He'd have said the same.", "ember")
    narrate("Brann picks the hammer up again, and weighs it, and does not strike anything with it.")
    line("Brann", "Mind the edge.", "ember")


def brann_topics(g):
    if g.flags.get("lw_foreman_dead") and not g.flags.get("lw_brann_told"):
        return [("Tell Brann about the Lampwrights' Deep", tell_brann)]
    return []


TOPICS = {"brann": brann_topics}


# ---------------------------------------------------------------------------- objectives
def OBJECTIVES(game, add):
    if "mine_hall" in game.visited and "lw_mess" not in game.visited and not game.flags.get("lw_door_open"):
        add("A bronze door with a ring of lenses is set in the wall of the Crypt Stair. A Lamp Relic, socketed into "
            "worn gear, would open it", "crypt_stair", side=True)
    if "lw_mess" in game.visited and not game.flags.get("lw_foreman_dead"):
        add("Corm's Workshop: the Last Foreman keeps the rack-room key", "lw_workshop", side=True)


# ---------------------------------------------------------------------------- validator
def CHECK():
    """No hollow of ours may be weak to Light (Light is already strong against hollows), and no bare rooms."""
    from ..content import ENEMIES, ROOMS
    errs = []
    for eid, e in ENEMIES.items():
        if eid.startswith("lw_") and "hollow" in e.get("tags", []) and "light" in e.get("weak", []):
            errs.append("enemy %s is hollow and weak to light" % eid)
    for rid, r in ROOMS.items():
        if rid.startswith("lw_") and not (r.get("desc") and r.get("features")):
            errs.append("room %s needs a desc and features" % rid)
    return errs
