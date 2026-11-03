"""Quest definitions. Stage text may be a function of the game for live counts.
Stage "done" is the completed state; -1 / missing means not yet started."""


def _shards(g):
    return sum(g.player.has_item(s) for s in ("ember_wood", "ember_tide", "ember_ash"))


def _petals(g):
    return g.player.inventory.get("moonpetal", 0)


def _wayposts(g):
    return sum(1 for r in ("wood_path", "thicket", "moth_shrine") if g.flags.get("lit_" + r))


# Aldric's six receipts (see areas/late.py): one from each place he borrowed a flame
LATE_RECEIPTS = ("hos_receipt", "rl_receipt", "lw_receipt", "ff_receipt", "vg_receipt", "late_receipt_court")


def _receipts(g):
    return sum(1 for r in LATE_RECEIPTS if g.player.has_item(r))


QUESTS = {
    "main": {
        "name": "The Long Night", "main": True,
        "stages": {
            0: "Speak to Guildmaster Orrin in the Lamplighters' Hall.",
            1: lambda g: "Recover the three Ember Shards (%d/3). One in the Weeping Wood (north gate), one in the "
                         "drowned chapel across the Saltmarsh (docks), one beneath the hill." % _shards(g),
            2: "You hold all three Embers. Open the way to the Lightwell, through the Old Well in the square "
               "or the black glass door in the Underdeep.",
            3: "Face what waits in the Lightwell.",
            "done": "The long night is over, one way or another.",
        },
    },
    "wren": {
        "name": "Maeve's Daughter",
        "stages": {
            0: "Wren went into the Weeping Wood looking for her father's trap-lines and never came back. Find her.",
            1: "You found Wren's ribbon caught on the thorns of the Briar Thicket. She came this way.",
            2: "Wren is caged in the White Grove. Bring her home safe to Maeve at the Drowned Moth.",
            "done": "Wren is home. Maeve has stopped crying, mostly.",
        },
    },
    "petals": {
        "name": "Petals for the Flame",
        "stages": {
            0: lambda g: "Sister Ilse needs three Moonpetals from the Saltmarsh to feed the chapel flame (%d/3)." % _petals(g),
            "done": "The chapel flame burns steady again. Ilse blessed you.",
        },
    },
    "starsteel": {
        "name": "A Smith's Last Work",
        "stages": {
            0: "Brann wants Starsteel Ore from the old mines under the hill to forge one last great blade.",
            1: "You have the Starsteel Ore. Take it to Brann.",
            "done": "Brann forged the Starsteel Blade.",
        },
    },
    "wayposts": {
        "name": "Relight the Tollroad",
        "stages": {
            0: lambda g: "Relight the three guild wayposts in the Weeping Wood (%d/3). Lit wayposts keep Hollows "
                         "away and let you rest and refill your lantern." % _wayposts(g),
            "done": "The Tollroad is lit again. Travellers can reach Hollowmere safely.",
        },
    },
    "bounty": {
        "name": "Cull the Hollows",
        "stages": {
            0: lambda g: "The council pays 3 gold for each Hollow destroyed. Claim at the bounty board in the "
                         "square. (Unclaimed: %d)" % g.flags.get("bounty_unclaimed", 0),
        },
    },
    "corvin": {
        "name": "The Hermit's Raven",
        "stages": {
            0: "Corvin the hermit wants a Gloam Pelt to line his raven's nest. Wolves in the wood carry them.",
            "done": "Corvin's raven sleeps warm. He taught you an old trick with lantern wicks.",
        },
    },
    "late_lending": {
        "name": "Held in Trust",
        "stages": {
            0: lambda g: "Aldric left receipts for six borrowed flames. Orrin can read what you have (%d of 6 found)." % _receipts(g),
            1: "Aldric's letter says the third quench needs a flame that someone chose to give you. Corm's notes (the "
               "Lampwrights' Deep), Marit's flame (the Frostfair) and Hale's flame (the Vigil) go to Brann and Tamsin in "
               "the Ember Smithy.",
            "done": "Brann and Tamsin quenched a blade in a flame that was given. The third quench is known.",
        },
    },
}
