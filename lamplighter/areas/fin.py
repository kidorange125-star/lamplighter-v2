"""The Roll of Lenders: Ysolde's list of everyone Aldric borrowed from (docs/M6-SPEC.md section 13.4).

No rooms, no people, no items. One extra topic on the Wizard's menu, available after the story and once the player has
a reason to ask (a receipt in the pack, or the cold answer to the Court's beacon seen). It names the six lenders, and
for each either "receipt in hand" or, in plain words, the lock that stands between the player and the place. It is the
one page in the game that says where every door of the Lending is, so a player who walked past one can find it.

Imports of the game's own modules are lazy: npcs imports every area module while it is still being imported.
"""
import textwrap

# (lender, receipt item, the lock's plain requirement, the flag once its door is open, how the page says that, where the
# receipt lies). A lender whose door is open but whose receipt is not in the pack is told as "open; the receipt is in
# <room>", so the Roll still says where to go after the lock is gone. The Court has no lock: Pell holds its receipt.
LENDERS = [
    ("the Hospice", "hos_receipt", "behind the Shrine of the Moth, east. Light the waypost there.",
     "lit_moth_shrine", "the Shrine's waypost is lit", "the Scriptorium"),
    ("the Reedlight", "rl_receipt", "south of the Bog Lights, behind a fog bank. A Fire or Light book, equipped, will "
     "clear it.", "rl_fog_burned", "the fog is burned off", "the Keeper's Cottage"),
    ("the Lampwrights' Deep", "lw_receipt", "a bronze door in the Crypt Stair. A Lamp Relic, socketed into something "
     "you wear.", "lw_door_open", "the bronze door stands open", "the Rack Room"),
    ("the Frostfair", "ff_receipt", "west of the North Gate, once the Court's beacon is lit.", "ff_thaw", "thawed",
     "the Lending Tent, south of the Fair Gate"),
    ("the Vigil", "vg_receipt", "up the Signal Stair beyond the Frostfair, once the Great Lantern is lit.",
     "vg_signal_sent", "released", "the Chart Library"),
    ("the Court", "late_receipt_court", None, None, None, None),
]


def _signal(g):
    """The Court's answer has been seen: by the beacon's hook, or by a save that lit the Court before M6 existed."""
    return bool(g.flags.get("ff_signal_seen") or g.flags.get("beacon_Ember Court"))


def _holds_receipt(g):
    from .. import quests
    return any(g.player.has_item(r) for r in quests.LATE_RECEIPTS)


def status(g, receipt, where, open_flag=None, open_text=None, vault=None):
    """One lender's line: the receipt if the player has it, else (door already open) where it lies, else the plain
    requirement. The Court has no door: Pell has it once the Queen is dead, and nobody has it before."""
    if g.player.has_item(receipt):
        return "receipt in hand"
    if receipt == "late_receipt_court":
        if g.flags.get("queen_dead"):
            return "Pell has held it since. Ask her."
        return "in the Ember Court. Pell will hand it over once the Queen is dead."
    if open_flag and g.flags.get(open_flag):
        return "%s; its receipt is in %s" % (open_text, vault)
    return where


def roll_lines(g):
    """[(Lender, status)] for the six lenders, in the order Aldric visited them."""
    return [(name[0].upper() + name[1:], status(g, rec, where, flag, text, vault))
            for name, rec, where, flag, text, vault in LENDERS]


def _print_entry(name, text):
    """One lender, wrapped with a hanging indent so a long requirement stays under its own name."""
    from .. import ui
    lines = textwrap.wrap("%s: %s" % (name, text), width=max(20, ui.width() - 2), initial_indent="  ",
                          subsequent_indent="    ")
    head = lines[0][2:]
    ui.say("  {amber}%s{/}{grey}%s{/}" % (head[:len(name)], head[len(name):]), indent=0, wrap=False)
    for rest in lines[1:]:
        ui.say("{grey}%s{/}" % rest, indent=0, wrap=False)


def _roll_of_lenders(g):
    from .. import ui
    from ..npcs import line
    from ..ui import say
    line("Ysolde", "I held the pen; he held the lamp. I wrote every receipt twice. I never wrote the word 'return'. "
                   "I'm... not proud of that.", "hollow")
    say("{grey}She turns a page of the Roll toward you. Six names, in two hands.{/}")
    for name, text in roll_lines(g):
        _print_entry(name, text)
    g.flags["fin_roll_read"] = True
    ui.pause()


def wizard_topics(g):
    if g.flags.get("completed") and (_holds_receipt(g) or _signal(g)):
        return [("Ask about the Roll of Lenders", _roll_of_lenders)]
    return []


TOPICS = {"wizard": wizard_topics}
EXTRA_NEWS = {"wizard": lambda g: bool(_signal(g) and not g.flags.get("fin_roll_read"))}


def CHECK():
    from ..content import ITEMS
    from ..quests import LATE_RECEIPTS
    errs = []
    names = [row[1] for row in LENDERS]
    if names != list(LATE_RECEIPTS):
        errs.append("the Roll of Lenders and quests.LATE_RECEIPTS disagree")
    for rec in names:
        if rec not in ITEMS:
            errs.append("the Roll names a receipt that does not exist: %s" % rec)
    return errs
