"""Every item in the game. Stats on equipment are flat bonuses.

kinds: weapon, armor, trinket, consumable, key, page, junk
consumable `use` keys are handled in engine.use_item / combat.use_item:
  heal, oil, focus, cleanse, firepot, regen, smoke
"""

ITEMS = {
    # ------------------------------------------------------------------ weapons
    "hook": {
        "name": "Lamplighter's Hook", "kind": "weapon", "value": 5,
        "stats": {"atk": 3},
        "desc": "A long brass pole with a hook for lifting lamp-caps. Every apprentice learns to swing one.",
    },
    "hatchet": {
        "name": "Iron Hatchet", "kind": "weapon", "value": 40,
        "stats": {"atk": 6},
        "desc": "Brann's honest work. Heavy in the head, light in the haft.",
    },
    "ashwood_rod": {
        "name": "Ashwood Rod", "kind": "weapon", "value": 45,
        "stats": {"atk": 2, "wil": 4},
        "desc": "A charred staff that stays warm. Fire comes easier when you hold it.",
    },
    "gutting_knife": {
        "name": "Gutting Knife", "kind": "weapon", "value": 45,
        "stats": {"atk": 4, "agi": 3},
        "desc": "A fisher's knife, thin and wicked. Made for quick work.",
    },
    "hunting_spear": {
        "name": "Hunter's Spear", "kind": "weapon", "value": 60,
        "stats": {"atk": 8},
        "desc": "Found in the abandoned camp. The bloodstains are old. Mostly.",
    },
    "saltsteel_saber": {
        "name": "Saltsteel Saber", "kind": "weapon", "value": 120,
        "stats": {"atk": 10, "agi": 2},
        "desc": "Forged from a drowned knight's blade. It never rusts, and it never stops dripping.",
    },
    "censer_flail": {
        "name": "Bishop's Censer", "kind": "weapon", "value": 140,
        "stats": {"atk": 7, "wil": 7},
        "desc": "The Drowned Bishop's censer. Swing it and it breathes out sparks instead of incense.",
    },
    "starsteel_blade": {
        "name": "Starsteel Blade", "kind": "weapon", "value": 300,
        "stats": {"atk": 15, "wil": 4, "agi": 2},
        "desc": "Brann's masterpiece, forged from ore that fell from the sky before the sky went dark. It hums near Hollows.",
    },
    # ------------------------------------------------------------------ armor
    "oilskin": {
        "name": "Oilskin Coat", "kind": "armor", "value": 8,
        "stats": {"def": 2},
        "desc": "Standard guild issue. Smells of whale oil and old rain.",
    },
    "jerkin": {
        "name": "Boiled-Leather Jerkin", "kind": "armor", "value": 35,
        "stats": {"def": 4, "agi": 1},
        "desc": "Stiff, light, and better than nothing by a good margin.",
    },
    "hauberk": {
        "name": "Chain Hauberk", "kind": "armor", "value": 110,
        "stats": {"def": 7},
        "desc": "Riveted rings, oiled against the damp. It jingles. Hollows hate the sound.",
    },
    "wardenplate": {
        "name": "Wardenplate", "kind": "armor", "value": 240,
        "stats": {"def": 11, "agi": -2, "hp": 10},
        "desc": "Plate from the old Watch, refitted by Brann. Slow, heavy, and very hard to kill.",
    },
    "drowned_mail": {
        "name": "Drowned Mail", "kind": "armor", "value": 150,
        "stats": {"def": 8, "wil": 2},
        "desc": "Scale armour pulled from the Salt Knights. Barnacles in the joints, but it holds.",
    },
    # ------------------------------------------------------------------ trinkets
    "moth_charm": {
        "name": "Moth Charm", "kind": "trinket", "value": 80,
        "stats": {"agi": 3, "dodge": 4},
        "desc": "A paper moth folded around a pinch of lamp-soot. Things find it hard to land a blow on you.",
    },
    "ember_locket": {
        "name": "Ember Locket", "kind": "trinket", "value": 90,
        "stats": {"wil": 4},
        "desc": "A locket with a coal inside that has never gone out.",
    },
    "saints_tooth": {
        "name": "Saint's Tooth", "kind": "trinket", "value": 120,
        "stats": {"hp": 12, "regen": 2},
        "desc": "A relic of the chapel. While you carry it, wounds close a little each turn of battle.",
    },
    "wolf_fang": {
        "name": "Gloam-Wolf Fang", "kind": "trinket", "value": 30,
        "stats": {"str": 2, "crit": 3},
        "desc": "Strung on sinew. Wearing it makes your grip feel surer.",
    },
    "orrins_ring": {
        "name": "Orrin's Signet", "kind": "trinket", "value": 1,
        "stats": {"wil": 3, "str": 2, "oil_save": 1},
        "desc": "The Guildmaster's ring, a little flame cut into a black stone. Your lantern burns slower while you wear it.",
    },
    # ------------------------------------------------------------------ consumables
    "draught": {
        "name": "Healing Draught", "kind": "consumable", "value": 12,
        "use": {"heal": 30},
        "desc": "Red, bitter, and it works. Restores 30 health.",
    },
    "strong_draught": {
        "name": "Strong Draught", "kind": "consumable", "value": 35,
        "use": {"heal": 75},
        "desc": "Thick as treacle. Restores 75 health.",
    },
    "stew": {
        "name": "Bowl of Maeve's Stew", "kind": "consumable", "value": 5,
        "use": {"heal": 15},
        "desc": "Eel, barley, and something Maeve won't name. Restores 15 health.",
    },
    "oil": {
        "name": "Flask of Lamp Oil", "kind": "consumable", "value": 10,
        "use": {"oil": 40},
        "desc": "Refills your lantern by 40.",
    },
    "tallow": {
        "name": "Hollow Tallow", "kind": "consumable", "value": 6,
        "use": {"oil": 15},
        "desc": "Grey fat rendered from a Hollow. It burns, if you don't mind the smell. Refills 15 oil.",
    },
    "tonic": {
        "name": "Focus Tonic", "kind": "consumable", "value": 25,
        "use": {"focus": 6},
        "desc": "Cold, minty, makes your teeth ache. Grants 6 Focus in battle.",
    },
    "salts": {
        "name": "Smelling Salts", "kind": "consumable", "value": 15,
        "use": {"cleanse": True, "heal": 5},
        "desc": "Clears the head. Removes poison, bleeding, burns, blindness and weakness.",
    },
    "firepot": {
        "name": "Firepot", "kind": "consumable", "value": 30,
        "use": {"firepot": 18},
        "desc": "A clay pot of lamp-oil and rag. Throw it in battle to burn every enemy.",
    },
    "honeycake": {
        "name": "Honeycake", "kind": "consumable", "value": 18,
        "use": {"heal": 20, "regen": 4},
        "desc": "Sweet and sticky. Restores 20 health and keeps healing you for a few turns in battle.",
    },
    "smokebomb": {
        "name": "Smoke Pellet", "kind": "consumable", "value": 20,
        "use": {"smoke": True},
        "desc": "Guaranteed escape from any fight that isn't a boss.",
    },
    # ------------------------------------------------------------------ quest / key
    "ember_wood": {
        "name": "Ember Shard (Antler)", "kind": "key", "value": 0,
        "desc": "A splinter of the old sun, pulled from the Antlered Mother's crown. It is warm and it beats like a heart.",
    },
    "ember_tide": {
        "name": "Ember Shard (Tide)", "kind": "key", "value": 0,
        "desc": "A splinter of the old sun, hissing faintly as if it is still being drowned.",
    },
    "ember_ash": {
        "name": "Ember Shard (Ash)", "kind": "key", "value": 0,
        "desc": "A splinter of the old sun. If you hold it to your ear you hear singing.",
    },
    "tide_key": {
        "name": "Tide Key", "kind": "key", "value": 0,
        "desc": "A green bronze key shaped like a wave. The Reeve wore it around his neck.",
    },
    "moonpetal": {
        "name": "Moonpetal", "kind": "key", "value": 0, "stack": True,
        "desc": "A pale marsh flower that glows faintly without any light to reflect. Sister Ilse wants these.",
    },
    "starsteel_ore": {
        "name": "Starsteel Ore", "kind": "key", "value": 0,
        "desc": "A lump of black metal flecked with points of light, like a piece of the night sky from before.",
    },
    "wren_ribbon": {
        "name": "Wren's Ribbon", "kind": "key", "value": 0,
        "desc": "A yellow hair ribbon, snagged on a thorn. Maeve's daughter wore one like it.",
    },
    "brass_shroud": {
        "name": "Brass Shroud", "kind": "key", "value": 0,
        "desc": "A lantern upgrade fitted by Brann. (Already installed.)",
    },
    "lens": {
        "name": "Polished Lens", "kind": "key", "value": 0,
        "desc": "A lantern upgrade. (Already installed.)",
    },
    # ------------------------------------------------------------------ junk / sell
    "hollow_dust": {
        "name": "Hollow Dust", "kind": "junk", "value": 4, "stack": True,
        "desc": "What is left when a Hollow comes apart. Tallow the merchant buys it, for reasons.",
    },
    "wolf_pelt": {
        "name": "Gloam Pelt", "kind": "junk", "value": 8, "stack": True,
        "desc": "Grey fur that is cold to the touch. Sells well.",
    },
    "pearl": {
        "name": "Black Pearl", "kind": "junk", "value": 25, "stack": True,
        "desc": "Pulled from something in the marsh. Valuable to the right buyer.",
    },
    "silver_icon": {
        "name": "Silver Icon", "kind": "junk", "value": 40,
        "desc": "A small saint in tarnished silver from the drowned chapel.",
    },
    # ------------------------------------------------------------------ journal pages
    "page1": {"name": "Journal Page (I)", "kind": "page", "value": 0, "desc": "A page in Orrin's hand."},
    "page2": {"name": "Journal Page (II)", "kind": "page", "value": 0, "desc": "A page in Orrin's hand."},
    "page3": {"name": "Journal Page (III)", "kind": "page", "value": 0, "desc": "A page in Orrin's hand."},
    "page4": {"name": "Journal Page (IV)", "kind": "page", "value": 0, "desc": "A page in Orrin's hand."},
    "page5": {"name": "Journal Page (V)", "kind": "page", "value": 0, "desc": "A page in Orrin's hand."},
    "page6": {"name": "Journal Page (VI)", "kind": "page", "value": 0, "desc": "A page in Orrin's hand."},
}

PAGES = {
    "page1": ("Of the Guild",
              "The Guild of Lamplighters is older than Hollowmere. We were here before the town, "
              "tending the Lightwell, the spring of fire under the hill that feeds the sun. "
              "Every lamp in the town is lit from it, and every lamp we light pays a little light back."),
    "page2": ("Of the Hollows",
              "A Hollow is a thing that has had its light put out. Beast or man, it does not matter. "
              "They are drawn to warmth and they hate it in the same breath. Flame frightens them. "
              "A flare in their faces will blind them and burn them twice over."),
    "page3": ("Of the Three Embers",
              "When the first Keeper sealed the Lightwell, he split the key into three embers and "
              "gave them to three guardians: the Mother of the wood, the Bishop of the tide, and the Choir "
              "beneath the hill. While they kept faith, the embers stayed bright."),
    "page4": ("Of Aldric",
              "There was a Keeper before me. His name was Aldric. He was the best of us, and he was afraid. "
              "A Keeper must one day give his own flame to the Well. Aldric would not. He went down into the "
              "dark with his lantern still lit and he did not come back up."),
    "page5": ("Of the Crown",
              "I have heard a voice in the well at night. It calls itself a king. It promises that no one need "
              "ever give their flame again, that the dark is gentle. It sounds like Aldric. "
              "God help me, it sounds like him."),
    "page6": ("Of the Last Lesson",
              "If you are reading this, apprentice, then I was too old and too afraid, the same as him. "
              "Here is the last lesson. A flame shared is not a flame halved. Two hands on the wick, and "
              "neither of you needs to be swallowed. And if you meet him, say his name. Say Aldric. "
              "He will remember being a man for one breath, and one breath is enough."),
}
