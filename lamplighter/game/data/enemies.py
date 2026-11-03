"""Enemy templates.

Move kinds (resolved in combat.py):
  attack  - damage the player (power x atk), optional status / hits
  heavy   - same, but telegraphed as a big hit; guard or stun it
  defend  - halve damage taken until its next turn
  heal    - heal the most hurt ally (or self) by `power` x max hp
  buff    - apply `status` to itself (or all allies with `allies: True`)
  debuff  - apply `status` to the player, no damage
  summon  - call another enemy into the fight
  drain   - attack that also drains lantern oil
  shroud  - wrap itself in darkness (immune until a flare strips it)
  charge  - spend the turn winding up; next move is forced to `then`

`fire` multiplies fire/flare damage taken. `hollow` enemies take double from flares.
"""

ENEMIES = {
    # ================================================================ WEEPING WOOD
    "gloam_wolf": {
        "name": "Gloam Wolf", "hp": 24, "atk": 7, "def": 1, "dodge": 8,
        "xp": 8, "gold": (2, 5), "tags": ["hollow", "beast"],
        "drops": [("wolf_pelt", 0.4), ("tallow", 0.25), ("wolf_fang", 0.03)],
        "desc": "A wolf with no shadow and eyes like two holes in the night.",
        "moves": [
            {"name": "Bite", "kind": "attack", "power": 1.0, "weight": 3, "tell": "circles, snapping"},
            {"name": "Rend", "kind": "attack", "power": 0.8, "status": ("bleed", 3, 2), "weight": 2,
             "tell": "bares long, wet teeth"},
            {"name": "Lunge", "kind": "heavy", "power": 1.9, "weight": 1, "tell": "drops low, ready to lunge"},
        ],
    },
    "hollow_fawn": {
        "name": "Hollow Fawn", "hp": 14, "atk": 5, "dodge": 12,
        "xp": 4, "gold": (0, 2), "tags": ["hollow", "beast"],
        "drops": [("tallow", 0.2)],
        "desc": "Something that was a fawn. It moves like it is being pulled on strings.",
        "moves": [
            {"name": "Kick", "kind": "attack", "power": 1.0, "weight": 3, "tell": "stamps its hooves"},
            {"name": "Bleat", "kind": "buff", "status": ("enraged", 2, 0), "allies": True, "weight": 1,
             "tell": "opens its mouth too wide"},
        ],
    },
    "rootwight": {
        "name": "Rootwight", "hp": 38, "atk": 9, "def": 5, "fire": 1.5,
        "xp": 12, "gold": (3, 7), "tags": ["hollow", "plant"],
        "drops": [("tallow", 0.3), ("draught", 0.15)],
        "desc": "A knot of black roots stood upright, wearing a dead hunter's coat.",
        "moves": [
            {"name": "Lash", "kind": "attack", "power": 1.0, "weight": 3, "tell": "sways, roots whipping"},
            {"name": "Entangle", "kind": "attack", "power": 0.5, "status": ("weak", 2, 0), "weight": 2,
             "tell": "sends roots creeping toward your feet"},
            {"name": "Crush", "kind": "heavy", "power": 2.0, "weight": 1, "tell": "raises a club of knotted wood"},
        ],
    },
    "moth_swarm": {
        "name": "Ash-Moth Swarm", "hp": 16, "atk": 4, "dodge": 25, "fire": 2.0,
        "xp": 6, "gold": (0, 3), "tags": ["hollow", "swarm"],
        "drops": [("hollow_dust", 0.5)],
        "desc": "Grey moths that want your lantern more than anything in the world.",
        "moves": [
            {"name": "Flutter", "kind": "attack", "power": 0.7, "hits": 2, "weight": 3, "tell": "whirls around you"},
            {"name": "Dust", "kind": "debuff", "status": ("blind", 2, 0), "weight": 1,
             "tell": "beats its wings, shedding grey dust"},
        ],
    },
    "antlered_mother": {
        "name": "The Antlered Mother", "hp": 160, "atk": 11, "def": 4, "fire": 1.2,
        "xp": 95, "gold": (55, 70), "tags": ["hollow", "beast", "boss"],
        "drops": [("strong_draught", 1.0)],
        "desc": "A great white doe, taller than a cart-horse, crowned with antlers like a burnt forest. "
                "Something in her crown glows.",
        "moves": [
            {"name": "Gore", "kind": "attack", "power": 1.1, "weight": 3, "tell": "lowers her antlers"},
            {"name": "Trample", "kind": "heavy", "power": 2.2, "weight": 2, "tell": "rears up, hooves high"},
            {"name": "Call the Brood", "kind": "summon", "summon": "hollow_fawn", "only_if": "can_summon",
             "weight": 2, "tell": "calls out into the trees"},
        ],
        "phases": [
            {"at": 0.5, "msg": "The Mother screams. Cold blue fire runs along her antlers like sap catching light.",
             "moves": [
                 {"name": "Gore", "kind": "attack", "power": 1.1, "weight": 3, "tell": "lowers her burning antlers"},
                 {"name": "Moonfire", "kind": "attack", "power": 0.9, "status": ("burn", 3, 4), "weight": 3,
                  "tell": "shakes blue fire from her crown"},
                 {"name": "Bellow", "kind": "debuff", "status": ("weak", 2, 0), "weight": 1,
                  "tell": "fills her lungs"},
                 {"name": "Trample", "kind": "heavy", "power": 2.4, "weight": 2, "tell": "rears up, hooves high"},
                 {"name": "Call the Brood", "kind": "summon", "summon": "hollow_fawn", "only_if": "can_summon",
                  "weight": 1, "tell": "calls out into the trees"},
             ]},
        ],
    },
    # ================================================================ SALTMARSH
    "bog_lurker": {
        "name": "Bog Lurker", "hp": 46, "atk": 10, "def": 3,
        "xp": 16, "gold": (4, 9), "tags": ["beast"],
        "drops": [("pearl", 0.3), ("draught", 0.15)],
        "desc": "All jaw and mud. You only see its eyes until it is already moving.",
        "moves": [
            {"name": "Snap", "kind": "attack", "power": 1.0, "weight": 3, "tell": "sinks low in the water"},
            {"name": "Spit Brine", "kind": "attack", "power": 0.6, "status": ("poison", 3, 3), "weight": 2,
             "tell": "gurgles, cheeks swelling"},
            {"name": "Drag Under", "kind": "heavy", "power": 1.9, "weight": 1, "tell": "coils its whole body"},
        ],
    },
    "drowned_villager": {
        "name": "Drowned Villager", "hp": 40, "atk": 10, "def": 4,
        "xp": 15, "gold": (2, 8), "tags": ["hollow", "undead"],
        "drops": [("hollow_dust", 0.6), ("tallow", 0.3)],
        "desc": "Grey skin, river weed in its hair, still wearing an apron.",
        "moves": [
            {"name": "Grasp", "kind": "attack", "power": 1.0, "weight": 3, "tell": "reaches for you"},
            {"name": "Wail", "kind": "debuff", "status": ("weak", 2, 0), "weight": 1,
             "tell": "opens a mouth full of water"},
            {"name": "Clutch", "kind": "heavy", "power": 1.7, "weight": 1, "tell": "lurches forward, arms wide"},
        ],
    },
    "wisp": {
        "name": "Marsh Wisp", "hp": 22, "atk": 11, "dodge": 30, "fire": 0.5,
        "xp": 14, "gold": (3, 6), "tags": ["hollow"],
        "drops": [("hollow_dust", 0.5), ("oil", 0.2)],
        "desc": "A cold light that is not light at all. It hates your lantern for being real.",
        "moves": [
            {"name": "Flicker", "kind": "attack", "power": 0.9, "status": ("burn", 2, 3), "weight": 3,
             "tell": "brightens, then dims"},
            {"name": "Lure", "kind": "debuff", "status": ("exposed", 2, 0), "weight": 1,
             "tell": "drifts invitingly close"},
            {"name": "Flash", "kind": "attack", "power": 0.8, "status": ("blind", 2, 0), "weight": 1,
             "tell": "gathers itself into a point"},
        ],
    },
    "reeve_haskel": {
        "name": "Reeve Haskel, Drowned", "hp": 115, "atk": 13, "def": 6,
        "xp": 60, "gold": (40, 50), "tags": ["hollow", "undead", "elite"],
        "drops": [("draught", 1.0)],
        "desc": "The village reeve, bloated and grey, still wearing his chain of office. "
                "A green key hangs from it.",
        "moves": [
            {"name": "Hook of Office", "kind": "attack", "power": 1.0, "weight": 3, "tell": "lifts his boat-hook"},
            {"name": "Tithe", "kind": "attack", "power": 0.8, "steal": 8, "weight": 2,
             "tell": "eyes your coin purse"},
            {"name": "Call to Order", "kind": "debuff", "status": ("exposed", 2, 0), "weight": 1,
             "tell": "bangs his hook like a gavel"},
            {"name": "Sentence", "kind": "heavy", "power": 2.0, "weight": 2, "tell": "pronounces sentence"},
        ],
    },
    "drowned_acolyte": {
        "name": "Drowned Acolyte", "hp": 48, "atk": 11, "def": 4,
        "xp": 18, "gold": (4, 10), "tags": ["hollow", "undead"],
        "drops": [("hollow_dust", 0.5), ("salts", 0.2)],
        "desc": "A novice in rotted white, chanting through a mouthful of water.",
        "moves": [
            {"name": "Strike", "kind": "attack", "power": 1.0, "weight": 3, "tell": "raises a candlestick"},
            {"name": "Brine Prayer", "kind": "heal", "power": 0.25, "only_if": "hurt_ally", "weight": 3,
             "tell": "begins to pray"},
            {"name": "Salt Hymn", "kind": "buff", "status": ("enraged", 2, 0), "allies": True, "weight": 1,
             "tell": "starts to sing"},
        ],
    },
    "salt_knight": {
        "name": "Salt Knight", "hp": 72, "atk": 14, "def": 9,
        "xp": 28, "gold": (8, 14), "tags": ["undead"],
        "drops": [("drowned_mail", 0.12), ("saltsteel_saber", 0.1), ("silver_icon", 0.2)],
        "desc": "Armour crusted white with salt, and no one inside but water.",
        "moves": [
            {"name": "Slash", "kind": "attack", "power": 1.0, "weight": 3, "tell": "levels its blade"},
            {"name": "Shield Wall", "kind": "defend", "weight": 1, "tell": "raises its shield"},
            {"name": "Executioner", "kind": "heavy", "power": 2.2, "weight": 2, "tell": "lifts its sword overhead"},
        ],
    },
    "drowned_bishop": {
        "name": "The Drowned Bishop", "hp": 200, "atk": 14, "def": 6,
        "xp": 165, "gold": (110, 130), "tags": ["hollow", "undead", "boss"],
        "drops": [("censer_flail", 1.0), ("strong_draught", 1.0)],
        "desc": "Robes of soaked purple, a mitre crusted with barnacles, and a censer that breathes out sea-fog. "
                "Something in the censer glows.",
        "moves": [
            {"name": "Censer Swing", "kind": "attack", "power": 1.0, "weight": 3, "tell": "swings his censer"},
            {"name": "Sermon of Salt", "kind": "attack", "power": 0.6, "status": ("poison", 3, 4), "weight": 2,
             "tell": "begins a sermon"},
            {"name": "Drown", "kind": "heavy", "power": 2.2, "weight": 2, "tell": "raises both hands; the water rises"},
        ],
        "phases": [
            {"at": 0.5, "msg": "The Bishop laughs, and the floodwater climbs his robes. 'The tide always returns.' "
                               "His wounds begin to close. (Fire dries the brine. Keep him burning: flares, firepots, fire skills.)",
             "status": ("regen", 99, 10),
             "moves": [
                 {"name": "Censer Swing", "kind": "attack", "power": 1.1, "weight": 3, "tell": "swings his censer"},
                 {"name": "Sermon of Salt", "kind": "attack", "power": 0.6, "status": ("poison", 3, 5), "weight": 2,
                  "tell": "begins a sermon"},
                 {"name": "Drown", "kind": "heavy", "power": 2.4, "weight": 2,
                  "tell": "raises both hands; the water rises"},
                 {"name": "Summon Acolyte", "kind": "summon", "summon": "drowned_acolyte", "only_if": "can_summon",
                  "weight": 1, "tell": "rings a drowned bell"},
             ]},
        ],
    },
    # ================================================================ UNDERDEEP
    "tallow_ghoul": {
        "name": "Tallow Ghoul", "hp": 60, "atk": 14, "def": 5, "fire": 1.6,
        "xp": 24, "gold": (6, 12), "tags": ["hollow", "undead"],
        "drops": [("tallow", 0.7), ("oil", 0.25)],
        "desc": "A miner rendered down into candle-fat. It is soft. It is still hungry.",
        "moves": [
            {"name": "Claw", "kind": "attack", "power": 1.0, "weight": 3, "tell": "flexes waxy fingers"},
            {"name": "Gorge", "kind": "heal", "power": 0.2, "only_if": "hurt_self", "weight": 2,
             "tell": "looks at its own wounds hungrily"},
            {"name": "Retch", "kind": "attack", "power": 0.6, "status": ("poison", 3, 4), "weight": 1,
             "tell": "heaves"},
        ],
    },
    "crawler": {
        "name": "Hollow Crawler", "hp": 52, "atk": 13, "def": 6, "dodge": 10,
        "xp": 25, "gold": (5, 11), "tags": ["hollow", "beast"],
        "drops": [("hollow_dust", 0.6), ("tallow", 0.3)],
        "desc": "Too many legs, and something like a face on its back.",
        "moves": [
            {"name": "Rake", "kind": "attack", "power": 0.9, "status": ("bleed", 3, 3), "weight": 3,
             "tell": "clicks its forelegs"},
            {"name": "Skitter", "kind": "defend", "weight": 1, "tell": "scuttles back into shadow"},
            {"name": "Pounce", "kind": "heavy", "power": 1.9, "weight": 1, "tell": "gathers its legs under it"},
        ],
    },
    "brood_queen": {
        "name": "Brood Queen", "hp": 110, "atk": 16, "def": 7,
        "xp": 60, "gold": (20, 30), "tags": ["hollow", "beast", "elite"],
        "drops": [("strong_draught", 1.0), ("moth_charm", 0.5)],
        "desc": "Bloated, pale, and very protective.",
        "moves": [
            {"name": "Sting", "kind": "attack", "power": 1.0, "status": ("poison", 3, 4), "weight": 3,
             "tell": "arches its tail"},
            {"name": "Birth", "kind": "summon", "summon": "crawler", "only_if": "can_summon", "weight": 1,
             "tell": "shudders and splits"},
            {"name": "Crush", "kind": "heavy", "power": 2.0, "weight": 2, "tell": "rears its swollen body"},
        ],
    },
    "starsteel_golem": {
        "name": "Ore-Warden", "hp": 150, "atk": 17, "def": 14,
        "xp": 85, "gold": (25, 35), "tags": ["construct", "elite"],
        "drops": [("strong_draught", 1.0)],
        "desc": "Miners built it to guard the starsteel seam. It still does, though the miners are gone.",
        "moves": [
            {"name": "Slam", "kind": "attack", "power": 1.0, "weight": 3, "tell": "swings a stone fist"},
            {"name": "Harden", "kind": "defend", "weight": 1, "tell": "settles into the rock"},
            {"name": "Gather Stars", "kind": "charge", "then": "Starfall", "weight": 2,
             "tell": "begins to glow from within. It is winding up something terrible"},
        ],
        "extra_moves": {
            "Starfall": {"name": "Starfall", "kind": "heavy", "power": 2.8, "tell": "is blazing. STARFALL is coming"},
        },
    },
    "alto": {
        "name": "Alto of Ash", "hp": 78, "atk": 12, "def": 5,
        "xp": 50, "gold": (15, 20), "tags": ["hollow", "choir", "boss"],
        "desc": "A singer made of cinders, holding one high, mending note.",
        "moves": [
            {"name": "Keen", "kind": "attack", "power": 0.9, "weight": 2, "tell": "sharpens her note"},
            {"name": "Mending Note", "kind": "heal", "power": 0.2, "only_if": "hurt_ally", "weight": 3,
             "tell": "sings a soft, rising note"},
            {"name": "Crescendo", "kind": "buff", "status": ("enraged", 1, 0), "allies": True, "weight": 1,
             "tell": "draws a deep breath"},
        ],
    },
    "tenor": {
        "name": "Tenor of Ash", "hp": 72, "atk": 13, "def": 5,
        "xp": 50, "gold": (15, 20), "tags": ["hollow", "choir", "boss"],
        "desc": "A singer made of cinders. Sparks fall from his mouth when he sings.",
        "moves": [
            {"name": "Searing Aria", "kind": "attack", "power": 0.9, "status": ("burn", 3, 4), "weight": 3,
             "tell": "sings, and the air shimmers"},
            {"name": "Dazzle", "kind": "debuff", "status": ("blind", 2, 0), "weight": 1,
             "tell": "flares bright as a struck match"},
        ],
    },
    "bass": {
        "name": "Bass of Ash", "hp": 92, "atk": 13, "def": 7,
        "xp": 55, "gold": (15, 20), "tags": ["hollow", "choir", "boss"],
        "desc": "A huge singer made of cinders. His voice shakes ash from the ceiling.",
        "moves": [
            {"name": "Rumble", "kind": "attack", "power": 1.0, "weight": 2, "tell": "hums, low and heavy"},
            {"name": "Low Note", "kind": "charge", "then": "Sundering Chord", "weight": 2,
             "tell": "takes the lowest breath you have ever heard. Something huge is coming"},
        ],
        "extra_moves": {
            "Sundering Chord": {"name": "Sundering Chord", "kind": "heavy", "power": 2.3,
                                "tell": "is about to unleash the SUNDERING CHORD"},
        },
    },
    "pale_usher": {
        "name": "The Pale Usher", "hp": 150, "atk": 17, "def": 8,
        "xp": 95, "gold": (30, 40), "tags": ["hollow", "undead", "elite"],
        "drops": [("strong_draught", 1.0)],
        "desc": "Tall and thin as a candle, it holds a long iron snuffer like a scythe.",
        "moves": [
            {"name": "Snuff", "kind": "drain", "power": 0.9, "drain": 12, "weight": 3,
             "tell": "reaches for your lantern with its snuffer"},
            {"name": "Toll", "kind": "debuff", "status": ("exposed", 2, 0), "weight": 1, "tell": "rings a silent bell"},
            {"name": "Reap", "kind": "heavy", "power": 2.2, "weight": 2, "tell": "draws the snuffer back like a scythe"},
        ],
    },
    "hollow_king": {
        "name": "The Hollow King", "hp": 380, "atk": 23, "def": 9, "fire": 1.0,
        "xp": 400, "gold": (0, 0), "tags": ["hollow", "boss", "king"],
        "desc": "A man in a lamplighter's coat, gone grey as old ash, wearing a crown of black glass. "
                "His lantern is still lit, but the flame inside is black.",
        "moves": [
            {"name": "Crown's Weight", "kind": "attack", "power": 1.0, "weight": 3, "tell": "points at you"},
            {"name": "Swallow Light", "kind": "drain", "power": 0.7, "drain": 15, "weight": 2,
             "tell": "opens his black lantern toward yours"},
            {"name": "Black Sun", "kind": "heavy", "power": 2.3, "weight": 2, "tell": "lifts his lantern; the dark gathers"},
        ],
        "phases": [
            {"at": 0.66, "msg": "The King draws the dark around him like a cloak. Your blows pass through nothing. "
                                "(Only a flare from your lantern can tear the shroud away.)",
             "status": ("shroud", 99, 0),
             "moves": [
                 {"name": "Crown's Weight", "kind": "attack", "power": 1.1, "weight": 3, "tell": "points at you"},
                 {"name": "Swallow Light", "kind": "drain", "power": 0.7, "drain": 15, "weight": 2,
                  "tell": "opens his black lantern toward yours"},
                 {"name": "Black Sun", "kind": "heavy", "power": 2.4, "weight": 2,
                  "tell": "lifts his lantern; the dark gathers"},
                 {"name": "Gather the Dark", "kind": "shroud", "only_if": "no_shroud", "weight": 3,
                  "tell": "reaches for the shadows again"},
             ]},
            {"at": 0.33, "msg": "The black glass crown cracks. The King roars, and every shadow in the Lightwell "
                                "leans toward you. 'If I must burn, then let it all go dark!'",
             "clear": ["shroud"],
             "moves": [
                 {"name": "Eclipse", "kind": "drain", "power": 1.1, "drain": 12, "weight": 3,
                  "tell": "becomes an eclipse"},
                 {"name": "Black Sun", "kind": "heavy", "power": 2.6, "weight": 2,
                  "tell": "lifts his lantern; the dark gathers"},
                 {"name": "Crown of Night", "kind": "buff", "status": ("enraged", 2, 0), "weight": 1,
                  "tell": "laughs, the crack in his crown widening"},
             ]},
        ],
    },
}
