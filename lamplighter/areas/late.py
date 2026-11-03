"""The Third Quench: Aldric's receipts, his letter, and the Godlike recipe (docs/M6-SPEC.md section 11.4).

No rooms and no new people. Four existing people (Pell, Brann, Orrin, Tamsin) gain topics, the six receipts start the
journal quest `late_lending`, and when a flame from each of the three places is brought to the Ember Smithy, Brann and
Tamsin quench a blade together and the flag `godlike_recipe` is set (forge.json asks for it).

The chain: Pell's receipt (the Court) -> five receipts from the five lenders -> Orrin opens Aldric's letter -> Corm's
notes to Brann -> Marit's and Hale's Given Flames (the `ff` and `vg` packages) -> Tamsin in the Ember Smithy.
Nothing here is in postgame.LAYERS, so a Wizard rewind clears none of it. Imports are lazy (npcs imports this module).
"""
from .. import quests
from ..content import ITEMS

RECEIPTS = quests.LATE_RECEIPTS
FLAMES = ("ff_given_flame", "vg_given_flame")
NOTES = "lw_quench_notes"
LETTER = "late_aldrics_letter"

# what Orrin says about each hand he recognises (never where it came from)
RECOGNISED = {
    "hos_receipt": "A waylamp, to guide him home. He got lost in his own garden once. He never let anyone mention it.",
    "rl_receipt": "A lens, to see the Well from far off. He had a poor eye and too much pride for spectacles.",
    "lw_receipt": "A copy of someone's notes. He was forever borrowing paper. He always meant to give it back.",
    "ff_receipt": "A flame held until the thaw, and a name in a book of lenders. Someone there wrote a better hand than his. "
                  "He noticed everything about other people.",
    "vg_receipt": "A promise to watch until word was sent. He never sent it. Oh, Aldric.",
    "late_receipt_court": "The last coal of the last dance. He went alone to that one. He came back smelling of smoke and "
                          "would not say why.",
}


def receipts_held(g):
    return [r for r in RECEIPTS if g.player.has_item(r)]


def _have(g, iid):
    return g.player.has_item(iid)


def _say():
    from .. import ui
    return ui.say


def _line(who, text, color="amber"):
    from .. import npcs
    npcs.line(who, text, color)


def _narrate(text):
    from .. import ui
    ui.narrate(text)


# ---------------------------------------------------------------------------- the receipts
def _receipt_gained(g):
    if g.quest("late_lending") == -1:
        g.set_quest("late_lending", 0)
    _say()("{grey}(Receipts: %d of 6. Orrin can read what you have.){/}" % len(receipts_held(g)))


AFTER_GAIN = {r: _receipt_gained for r in RECEIPTS}


# ---------------------------------------------------------------------------- Pell: the Court's receipt
def _pell_receipt(g):
    from .. import events
    _narrate("Pell turns to the back of her ledger and takes out a folded square of paper gone soft as cloth. She holds "
             "it a moment before she lets it go, the way you hold a thing you have been meaning to hand over for a "
             "very long time.")
    _line("Pell", "The Queen kept it under her sceptre. 'Hold this for him,' she said. I've held it a hundred years. "
                  "Now you.", "ember")
    events.give_once(g, "late_receipt_court")
    _line("Pell", "It's signed with one letter. I never did learn the rest of his name. It was not my place to ask.",
          "ember")


def pell_topics(g):
    if g.flags.get("queen_dead") and not _have(g, "late_receipt_court"):
        return [("Ask for the Court's receipt", _pell_receipt)]
    return []


# ---------------------------------------------------------------------------- Brann: Corm's notes
def _brann_notes(g):
    g.flags["late_notes_shown"] = True
    _narrate("Brann reads the notes the way he reads a blade: from the tang outward, slowly, and without blinking.")
    if g.flags.get("lw_brann_told"):
        _line("Brann", "That's his hand. My grandfather's. He never wrote down a thing he could say with a hammer, so "
                       "I know this mattered to him.", "ember")
    else:
        _line("Brann", "I know this hand. I have seen it scratched inside the handle of a hammer I was not allowed to "
                       "use. ...Corm's. He never wrote down a thing he could say with a hammer, so I know this "
                       "mattered to him.", "ember")
    _line("Brann", "Two quenches I know. Water takes the heat, oil takes the brittle. The third was always a rumour. My "
                   "father used to say it when I was small and sulking at the anvil. He had it from Corm: 'There's a "
                   "third, boy, and nobody has paid for it yet.'", "ember")
    _line("Brann", "'It wants fire, and not any fire.' ...A flame that's given. How do you make a smith give a flame? "
                   "We sell. It is nearly the whole of the trade.", "ember")
    _line("Brann", "A quench wants two pairs of hands, anyway. Water in one, oil in the other. I have been too proud to "
                   "ask for the second pair for a good many years.", "ember")
    _checklist(g, "Brann")


def missing_pieces(g):
    """What the third quench still lacks, as plain phrases: [(key, text)]."""
    f = g.flags
    out = []
    if not f.get("late_notes_shown"):
        if _have(g, NOTES):
            out.append(("notes", "Corm's notes have not been shown to Brann yet"))
        else:
            out.append(("notes", "Corm's notes on the quench, left in the Lampwrights' Deep"))
    if not f.get("late_letter_read"):
        out.append(("letter", "whatever Aldric left with Orrin (%d of 6 receipts found)" % len(receipts_held(g))))
    if not _have(g, "ff_given_flame"):
        out.append(("ff", "the flame Marit gives, in the Frostfair, once the Fair has thawed"))
    if not _have(g, "vg_given_flame"):
        out.append(("vg", "the flame Hale gives, in the Vigil, once the Signal is sent"))
    return out


def _checklist(g, who):
    say = _say()
    if g.flags.get("godlike_recipe"):
        _line(who, "We have it. A flame shared is not a flame halved. Bring a Legendary blade and a deep purse.",
              "ember")
        return
    miss = missing_pieces(g)
    if not miss:
        _line(who, "Everything is here. Tamsin will want to see it, in the Ember Smithy.", "ember")
        return
    _line(who, "Here is what we still lack:", "ember")
    for _, text in miss:
        say("{grey}   - %s{/}" % text)


def _brann_needs(g):
    _checklist(g, "Brann")


def brann_topics(g):
    out = []
    if _have(g, NOTES) and not g.flags.get("late_notes_shown"):
        out.append(("Show him Corm's notes", _brann_notes))
    if g.flags.get("late_notes_shown"):
        out.append(("Ask what the third quench needs", _brann_needs))
    return out


# ---------------------------------------------------------------------------- Orrin: the receipts and the letter
def _read_the_letter(g):
    say = _say()
    say("{grey}The letter, in Aldric's hand:{/}")
    _narrate(ITEMS[LETTER]["desc"])


def _orrin_receipts(g):
    say = _say()
    held = receipts_held(g)
    f = g.flags
    if len(held) < len(RECEIPTS):
        _narrate("Orrin takes the papers one at a time and holds each close to his eyes. His thumb stops on the signature.")
        for r in held:
            _line("Orrin", RECOGNISED[r], "amber")
        _line("Orrin", "That is %d. There were six. I counted them once, a long time ago, from the other side of a "
                       "table. I won't tell you where the rest are. I never knew; he never said." % len(held), "amber")
        _line("Orrin", "Bring me what you find. Whatever it was he borrowed, he meant to return.", "amber")
        return
    _narrate("Orrin turns the receipts over one by one and says nothing. Then he asks you to open the drawer under his "
             "bed, and in it is a letter sealed with wax gone brittle.")
    _line("Orrin", "He left it with me the night he went down. 'Open it when someone brings back everything I "
                   "borrowed.' Fifty years. I am a coward, but I can keep a promise.", "amber")
    _narrate("He breaks the seal with a thumbnail that has not been steady in years, and reads it aloud.")
    f["late_letter_read"] = True
    from .. import events
    events.give_once(g, LETTER)
    _read_the_letter(g)
    _line("Orrin", "'The wick was always his to trim.' ...He knew I would be the one. Of course he knew.", "amber")
    _line("Orrin", "Corm's notes, and the smiths. Take it to Brann and to Tamsin. They will know what to do with a "
                   "letter, even if they do not know what to do with each other.", "amber")
    g.set_quest("late_lending", 1)
    from .. import ui
    ui.pause()


def _orrin_letter_again(g):
    _narrate("Orrin does not need the page. He has had it by heart for as long as it has been in the drawer.")
    _read_the_letter(g)
    from .. import ui
    ui.pause()


def orrin_topics(g):
    out = []
    if receipts_held(g) and not g.flags.get("late_letter_read"):
        out.append(("Show him the receipts", _orrin_receipts))
    if g.flags.get("late_letter_read"):
        out.append(("Ask him to read Aldric's letter again", _orrin_letter_again))
    return out


# ---------------------------------------------------------------------------- Tamsin: the third quench
def _scene_ready(g):
    from .. import town
    f = g.flags
    return (town.is_built(g, "ember_smithy") and f.get("late_notes_shown") and f.get("late_letter_read")
            and all(_have(g, fl) for fl in FLAMES) and not f.get("godlike_recipe"))


def _tamsin_quench(g):
    f = g.flags
    if f.get("godlike_recipe"):
        _line("Tamsin", "It's known now. It cannot be unknown. Bring me a Legendary blade and I'll show you what two "
                        "anvils are for.", "ember")
        return
    if not _scene_ready(g):
        miss = missing_pieces(g)
        if f.get("late_notes_shown"):
            _line("Tamsin", "Not yet. Brann has told me a little of it, and I have thought of nothing else. Here is "
                            "what we do not have:", "ember")
        else:
            _line("Tamsin", "Brann says there is a third quench. I want to hear it. Here is what we do not have:",
                  "ember")
        say = _say()
        for _, text in miss:
            say("{grey}   - %s{/}" % text)
        return
    p = g.player
    say = _say()
    _narrate("Brann comes through the back door of the Ember Smithy with his hammer, and Tamsin meets him at the anvil, "
             "and for the first time in either of their lives they are not each the other's rival. You hold the lantern. "
             "You hold, in your two hands, two small flames that were given.")
    _line("Brann", "Water.", "ember")
    _line("Tamsin", "Oil.", "ember")
    _narrate("And then the two of them, together, lower the blade into the light you are holding, and it does not hiss, "
             "and it does not burn: it sings. When they lift it out it is a plain grey blade, and it is the most "
             "beautiful thing you have ever seen.")
    _line("Tamsin", "Orrin's page said a flame shared is not a flame halved. I thought it was a saying. It's a "
                    "method.", "ember")
    for fl in FLAMES:
        p.remove_item(fl)
    f["godlike_recipe"] = True
    f["late_quench_done"] = True
    g.set_quest("late_lending", "done")
    say("{bgreen}The third quench is known.{/} {grey}The forge can now raise a Legendary piece to Godlike (it takes both "
        "anvils, Rime and Vigil Glass), and a Godlike weapon can be Long-Quenched.{/}")
    from .. import ui
    ui.pause()


def _tamsin_long_quench(g):
    from .. import quench
    _line("Tamsin", "A week at the anvil, for a Godlike blade. Brann holds the water and I hold the oil, and the "
                    "flame is yours. It does not break what it works on; it is only slow.", "ember")
    _line("Tamsin", "Ask at the forge, here or at Brann's. It never destroys the blade, and it never sends it back "
                    "weaker than it came. (The odds now: %s.)" % quench.odds_text(g), "ember")


def tamsin_topics(g):
    from .. import town
    f = g.flags
    out = []
    if town.is_built(g, "ember_smithy") and not f.get("godlike_recipe"):
        out.append(("Ask about the third quench", _tamsin_quench))
    if f.get("godlike_recipe"):
        out.append(("Ask about the Long Quench", _tamsin_long_quench))
    return out


# ---------------------------------------------------------------------------- hooks
TOPICS = {"pell": pell_topics, "brann": brann_topics, "orrin": orrin_topics, "tamsin": tamsin_topics}


def _orrin_news(g):
    return len(receipts_held(g)) == len(RECEIPTS) and not g.flags.get("late_letter_read")


def _pell_news(g):
    """Pell kept the Court's receipt; nothing else points a player back at her once she has said her piece."""
    return bool(g.flags.get("queen_dead")) and not _have(g, "late_receipt_court")


def _brann_news(g):
    return _have(g, NOTES) and not g.flags.get("late_notes_shown")


EXTRA_NEWS = {"pell": _pell_news, "orrin": _orrin_news, "brann": _brann_news, "tamsin": _scene_ready}


def OBJECTIVES(game, add):
    f = game.flags
    n = len(receipts_held(game))
    if n >= 1 and not f.get("late_letter_read"):
        add("Aldric's receipts: %d of 6 found. Orrin can read what you have" % n, "hall", True)
        if _pell_news(game):
            add("The Court Gate: Pell kept a paper for someone who would come back", "court_gate", True)
    if f.get("late_letter_read") and not f.get("godlike_recipe"):
        add("The third quench: Corm's notes, Marit's flame, Hale's flame, then Tamsin in the Ember Smithy",
            "ember_smithy", True)
    if f.get("godlike_recipe"):
        from .. import quench
        if quench.candidates(game) and not quench.running(game):
            add("A Godlike weapon can be Long-Quenched at the forge", "smithy", True)


def CHECK():
    errs = []
    for iid in (LETTER, "late_receipt_court"):
        if iid not in ITEMS:
            errs.append("missing item %s" % iid)
        elif ITEMS[iid]["kind"] != "key":
            errs.append("%s must be a key item" % iid)
    from ..quests import QUESTS
    if "late_lending" not in QUESTS:
        errs.append("quest late_lending is not defined")
    for r in RECOGNISED:
        if r not in RECEIPTS:
            errs.append("Orrin recognises %s, which is not a receipt" % r)
    return errs
