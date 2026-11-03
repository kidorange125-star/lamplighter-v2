"""Rooms. Each region has its own map grid (pos = (x, y), y grows southward).

Room keys:
  name, region, pos, dark, desc, exits {dir: room}
  locks     {dir: {"item"|"flag"|"shards": ..., "msg": str}}
  items     item ids lying here at the start
  npcs      npc ids present
  features  {keyword(s): text} for `examine`
  enc       random encounters: {"chance": float, "groups": [([enemy ids], weight), ...]}
  fixed     one-time fight on entry: {"flag", "enemies", "intro"}
  waypost   True if a guild waypost stands here that can be relit
  rest      True if you can rest here
  event     name of an on-enter hook in events.py
"""

REGIONS = ["Hollowmere", "Weeping Wood", "Saltmarsh", "Underdeep"]

ROOMS = {
    # =================================================================== HOLLOWMERE
    "hall": {
        "name": "Lamplighters' Hall", "region": "Hollowmere", "pos": (0, 0), "dark": False, "rest": True,
        "desc": "The guild hall smells of oil and old wool. Rows of empty bunks line the walls; you are the "
                "only apprentice who stayed. The Great Lantern hangs dead from the rafters. In the corner bed, "
                "under a heap of blankets, Guildmaster Orrin breathes slow and shallow. A desk sits by the "
                "door, and the guild's records lie on it.",
        "exits": {"e": "square"},
        "npcs": ["orrin"],
        "items": ["page1"],
        "features": {
            "great lantern|lantern|rafters": "A brass lantern as big as a barrel. It was lit from the Lightwell "
                                             "itself. Forty days ago it went out, and the sun went with it.",
            "bunks|beds": "Twelve bunks. Eleven are stripped bare. The others left when the dark came.",
            "desk|records": "Ledgers of lamps lit and oil spent, going back three hundred years. Orrin's journal "
                            "should be here, but most of it is missing. Only a single page remains.",
        },
    },
    "square": {
        "name": "Hollowmere Square", "region": "Hollowmere", "pos": (1, 0), "dark": False,
        "desc": "The town square, ringed with iron lampposts that you light by hand every evening, though "
                "evening never ends now. Their small yellow circles are the only thing holding the dark back. "
                "In the centre stands the Old Well under an iron grate. A bounty board leans against it.",
        "exits": {"w": "hall", "e": "tavern", "n": "gate", "s": "lane", "d": "well_bottom"},
        "locks": {"d": {"shards": 3, "msg": "The Old Well's iron grate is sealed. Three empty sockets, each "
                                           "shaped like a flame, are set into the lock."}},
        "features": {
            "well|old well|grate": "Cold air rises from the well. Far, far below, something glows faintly, "
                                   "like a coal about to go out. The grate has three flame-shaped sockets.",
            "lampposts|lamps": "You lit every one of these yourself. They burn a little dimmer every day.",
            "board|bounty board|bounty": "BOUNTY: The town council will pay for every Hollow put down. Report "
                                         "to the board. (Type 'bounty' here to claim rewards.)",
        },
    },
    "tavern": {
        "name": "The Drowned Moth", "region": "Hollowmere", "pos": (2, 0), "dark": False,
        "desc": "Low beams, a fire kept too high, and nearly every candle in town burning on the tables. "
                "The few folk left in Hollowmere drink here because it is the brightest room on the hill. "
                "Old Maeve works the bar with red eyes.",
        "exits": {"w": "square"},
        "npcs": ["maeve"],
        "features": {
            "fire|hearth": "Maeve keeps it roaring. Nobody complains about the heat.",
            "patrons|folk|drinkers": "A fisherman, two carters, and the old schoolteacher. None of them talk much.",
        },
    },
    "gate": {
        "name": "North Gate", "region": "Hollowmere", "pos": (1, -1), "dark": False,
        "desc": "The town's north gate, barred with a beam and lit by two big braziers. Beyond it the Tollroad "
                "runs into the Weeping Wood, where nothing has been lit for forty days. The gatekeeper, "
                "a broad woman named Hesk, lifts the bar when she sees your lantern.",
        "exits": {"s": "square", "n": "wood_path"},
        "npcs": ["hesk"],
        "features": {"braziers": "Hesk feeds them broken furniture now. The wood ran out a week ago."},
    },
    "lane": {
        "name": "Candle Lane", "region": "Hollowmere", "pos": (1, 1), "dark": False,
        "desc": "A narrow street of shuttered shops. Candles burn in every window, set there by people who "
                "are too afraid to come outside. West is the Chapel of the Ember; east, the ring of a hammer "
                "from Brann's forge. The lane slopes south toward the docks.",
        "exits": {"n": "square", "w": "chapel", "e": "smithy", "s": "docks"},
        "features": {"candles|windows": "Hundreds of them. The town is spending its last tallow on hope."},
    },
    "chapel": {
        "name": "Chapel of the Ember", "region": "Hollowmere", "pos": (0, 1), "dark": False,
        "desc": "A small round chapel built around a stone brazier, where a flame from the Lightwell burns. "
                "It is no bigger than a candle now. Sister Ilse kneels beside it, feeding it a drop of oil at a time.",
        "exits": {"e": "lane"},
        "npcs": ["ilse"],
        "features": {"brazier|flame|ember": "The holy flame gutters and recovers, gutters and recovers. "
                                            "Ilse has not slept in days."},
    },
    "smithy": {
        "name": "Brann's Forge", "region": "Hollowmere", "pos": (2, 1), "dark": False,
        "desc": "A forge glowing red, and the heat is good after the cold streets. Weapons hang on every "
                "wall. Brann, a huge bald man with burn-scarred forearms, is hammering at something that "
                "doesn't need hammering.",
        "exits": {"w": "lane"},
        "npcs": ["brann"],
        "features": {"forge": "Brann burns coal he dug himself. 'Fire's fire,' he says.",
                     "weapons|walls": "Hatchets, rods, knives, a few good blades. Brann shows them if you ask to trade."},
    },
    "docks": {
        "name": "The Black Docks", "region": "Hollowmere", "pos": (1, 2), "dark": False,
        "desc": "Wet planks over black water. Most of the boats have been dragged up and turned over. "
                "Only Oskar the ferryman still works, though nobody wants to cross. East, across the water, "
                "lies the Saltmarsh, and beyond it the spire of a drowned chapel.",
        "exits": {"n": "lane", "e": "marsh_edge"},
        "npcs": ["oskar"],
        "features": {"water|lake": "Black and still. Sometimes something rises, looks at the light, and sinks again.",
                     "spire|chapel": "The Chapel of the Tide. It sank into the marsh a century ago, they say, "
                                     "and its bishop with it."},
    },
    # =================================================================== WEEPING WOOD
    "wood_path": {
        "name": "The Tollroad", "region": "Weeping Wood", "pos": (1, -2), "dark": True, "waypost": True,
        "desc": "The old road north, rutted and overgrown. Willows lean over it from both sides, dripping "
                "though it isn't raining. A guild waypost stands at the roadside, its lamp cold.",
        "exits": {"s": "gate", "n": "wood_fork"},
        "enc": {"chance": 0.25, "groups": [(["gloam_wolf"], 3), (["hollow_fawn", "hollow_fawn"], 1)]},
        "features": {"willows|trees": "They weep sap the colour of tea. The wood was named for them long before the dark.",
                     "waypost|lamp": "A guild waypost. Light it (type 'light') and it will burn on its own again, "
                                     "keeping Hollows away and letting you rest and refill here."},
    },
    "wood_fork": {
        "name": "The Hanged Fork", "region": "Weeping Wood", "pos": (1, -3), "dark": True,
        "desc": "The road splits under a huge dead oak. Someone has nailed signs to it: WEST, CAMP. EAST, "
                "SHRINE. NORTH, DON'T. Old ropes hang from the lower branches, thankfully empty.",
        "exits": {"s": "wood_path", "w": "hunters_camp", "e": "thicket", "n": "deepwood"},
        "enc": {"chance": 0.3, "groups": [(["gloam_wolf"], 2), (["gloam_wolf", "gloam_wolf"], 2), (["moth_swarm"], 1)]},
        "features": {"signs|oak": "NORTH, DON'T has been carved over an older sign. The older one says MOTHER."},
    },
    "hunters_camp": {
        "name": "Abandoned Hunters' Camp", "region": "Weeping Wood", "pos": (0, -3), "dark": True,
        "desc": "Three tents, slashed and sagging. A cold firepit full of grey ash. Drying racks with nothing "
                "on them. Whatever happened here happened fast.",
        "exits": {"e": "wood_fork"},
        "items": ["hunting_spear", "oil", "page2"],
        "fixed": {"flag": "camp_wight", "enemies": ["rootwight"],
                  "intro": "One of the drying racks unfolds itself, stands up, and turns toward your light."},
        "features": {"tents": "Bedrolls, a boot, a child's carved wooden bird. You put the bird back.",
                     "firepit|ash": "Cold for weeks. There are moth wings in the ash, hundreds of them."},
    },
    "thicket": {
        "name": "Briar Thicket", "region": "Weeping Wood", "pos": (2, -3), "dark": True, "waypost": True,
        "desc": "Thorns as long as fingers, woven into tunnels. The path winds through them toward a "
                "clearing where a second guild waypost stands, leaning.",
        "exits": {"w": "wood_fork"},
        "items": ["wren_ribbon"],
        "enc": {"chance": 0.3, "groups": [(["moth_swarm"], 2), (["moth_swarm", "moth_swarm"], 1), (["gloam_wolf"], 1)]},
        "features": {"thorns|briars": "Something small came through here, and recently. There are threads caught on the thorns.",
                     "waypost": "The second waypost. Its glass is cracked but the wick is good."},
    },
    "deepwood": {
        "name": "The Deepwood", "region": "Weeping Wood", "pos": (1, -4), "dark": True,
        "desc": "The trees close overhead. Even with your lantern the dark here feels thick, like water. "
                "To the west, a thread of real woodsmoke. To the east, a soft grey shimmer. To the north, "
                "the trees are white, and something enormous has broken a path through them.",
        "exits": {"s": "wood_fork", "w": "hermit_hut", "e": "moth_shrine", "n": "mother_grove"},
        "enc": {"chance": 0.35, "groups": [(["rootwight"], 2), (["gloam_wolf", "gloam_wolf"], 2),
                                          (["rootwight", "gloam_wolf"], 1)]},
        "features": {"path|white trees": "The trunks are scored with antler marks higher than your head."},
    },
    "hermit_hut": {
        "name": "Corvin's Hut", "region": "Weeping Wood", "pos": (0, -4), "dark": False, "rest": True,
        "desc": "A crooked hut, half dug into a hillside, with a real fire burning in a real hearth. Bundles of "
                "herbs hang from the ceiling and a raven watches you from a perch. An old man in a coat of "
                "feathers squints at your lantern.",
        "exits": {"e": "deepwood"},
        "npcs": ["corvin"],
        "features": {"raven": "It watches the lantern, not you.",
                     "herbs": "Hemlock, feverfew, moonwort. And things you don't recognise."},
    },
    "moth_shrine": {
        "name": "Shrine of the Moth", "region": "Weeping Wood", "pos": (2, -4), "dark": True, "waypost": True,
        "desc": "A mossy stone shrine to some forgotten saint of travellers, carved with moth wings. "
                "The third guild waypost stands beside it, smothered in grey moths.",
        "exits": {"w": "deepwood"},
        "items": ["honeycake"],
        "fixed": {"flag": "shrine_moths", "enemies": ["moth_swarm", "moth_swarm"],
                  "intro": "The moths on the waypost rise all at once, a grey cloud, and come for your lantern."},
        "features": {"shrine|saint": "The saint's face is worn away. Someone has left a honeycake as an offering. "
                                     "Old, but still good.",
                     "waypost": "The third waypost. Light it and the whole Tollroad will be guarded again."},
    },
    "mother_grove": {
        "name": "The White Grove", "region": "Weeping Wood", "pos": (1, -5), "dark": True,
        "desc": "A clearing of white birches around a pool as still as glass. Bones lie in heaps between the "
                "roots, picked clean. At the far side, a great cage of living roots has grown up from the earth.",
        "exits": {"s": "deepwood"},
        "event": "mother_grove",
        "features": {"pool": "It reflects your lantern perfectly, but not you.",
                     "cage|roots": "Woven roots, thick as your arm, grown into a dome."},
    },
    # =================================================================== SALTMARSH
    "marsh_edge": {
        "name": "Ferry Landing", "region": "Saltmarsh", "pos": (2, 2), "dark": True,
        "desc": "A rotten jetty at the edge of the Saltmarsh. Oskar's ferry bobs behind you. Ahead, reeds taller "
                "than a man, hissing in a wind you can't feel. The air tastes of salt and rot.",
        "exits": {"w": "docks", "e": "reedways"},
        "features": {"ferry": "Oskar will wait. 'Shout if you need me,' he said. 'I'll pretend I didn't hear.'"},
    },
    "reedways": {
        "name": "The Reedways", "region": "Saltmarsh", "pos": (3, 2), "dark": True,
        "desc": "Paths of half-sunk planks wind through the reeds. Every step squelches. Pale flowers glow "
                "faintly in the black water, and you hear something large moving just out of sight.",
        "exits": {"w": "marsh_edge", "s": "bog_lights", "e": "sunken_village"},
        "items": ["moonpetal"],
        "enc": {"chance": 0.3, "groups": [(["bog_lurker"], 2), (["wisp"], 2), (["wisp", "wisp"], 1)]},
        "features": {"flowers|petals": "Moonpetals. Sister Ilse wants these."},
    },
    "bog_lights": {
        "name": "The Bog Lights", "region": "Saltmarsh", "pos": (3, 3), "dark": True,
        "desc": "Open bog, dotted with cold blue lights that drift and bob just above the water. Travellers "
                "used to follow them and drown. One of the lights is a moonpetal. The rest are not.",
        "exits": {"n": "reedways"},
        "items": ["moonpetal", "page3", "oil"],
        "enc": {"chance": 0.4, "groups": [(["wisp"], 2), (["wisp", "wisp"], 2), (["bog_lurker", "wisp"], 1)]},
        "features": {"lights|wisps": "They drift toward your lantern, curious and hateful."},
    },
    "sunken_village": {
        "name": "Sunken Village", "region": "Saltmarsh", "pos": (4, 2), "dark": True,
        "desc": "The roofs of a drowned village stick up out of the marsh like the backs of whales. A walkway "
                "of doors laid flat runs between them. Shapes stand in the water, up to their waists, quite "
                "still, facing the chapel spire to the east. A larger house sits on stilts to the south.",
        "exits": {"w": "reedways", "e": "chapel_steps", "s": "reeve_house"},
        "items": ["moonpetal"],
        "enc": {"chance": 0.35, "groups": [(["drowned_villager"], 2), (["drowned_villager", "drowned_villager"], 2),
                                          (["drowned_villager", "wisp"], 1)]},
        "features": {"shapes|villagers": "Drowned villagers, waiting for a service that never ends.",
                     "house|stilts": "The reeve's house. A light burns in the window, green as old copper."},
    },
    "reeve_house": {
        "name": "The Reeve's House", "region": "Saltmarsh", "pos": (4, 3), "dark": True,
        "desc": "A council room on stilts, ankle-deep in seawater. Ledgers float. A chair at the head of the "
                "long table faces the door.",
        "exits": {"n": "sunken_village"},
        "items": ["pearl", "silver_icon"],
        "event": "reeve_house",
        "features": {"ledgers": "Tithe records. The village paid the chapel in fish, then in silver, then in children."},
    },
    "chapel_steps": {
        "name": "Chapel Steps", "region": "Saltmarsh", "pos": (5, 2), "dark": True,
        "desc": "Broad stone steps rise out of the water to the doors of the Chapel of the Tide. The doors are "
                "green bronze, carved with waves, and sealed by a lock shaped like a breaking wave.",
        "exits": {"w": "sunken_village", "n": "chapel_nave"},
        "locks": {"n": {"item": "tide_key", "msg": "The bronze doors are locked. The keyhole is shaped like a wave."}},
        "enc": {"chance": 0.25, "groups": [(["drowned_villager", "drowned_villager"], 1), (["salt_knight"], 1)]},
        "features": {"doors|lock": "The lock is shaped like a breaking wave. The Reeve would have the key."},
    },
    "chapel_nave": {
        "name": "Nave of the Tide", "region": "Saltmarsh", "pos": (5, 1), "dark": True,
        "desc": "The chapel nave, flooded to the knee. Pews float in rows. Salt has grown over everything in "
                "white crusts like frost. Steps lead up to the altar to the north. In the floor, a slab of "
                "stone covers a stair going down.",
        "exits": {"s": "chapel_steps", "n": "bishop_altar", "d": "crypt_stair"},
        "locks": {"d": {"flag": "bishop_dead", "msg": "The slab over the crypt stair won't move. Salt has fused "
                                                     "it to the floor, and the salt is coming from the altar."}},
        "items": ["page4"],
        "fixed": {"flag": "nave_guard", "enemies": ["salt_knight", "drowned_acolyte"],
                  "intro": "A Salt Knight rises from the water between the pews, and an acolyte begins to chant."},
        "features": {"pews": "Each pew has a drowned brass nameplate. Generations of Hollowmere families.",
                     "slab|stair": "Salt crusts the slab. It seals the way down."},
    },
    "bishop_altar": {
        "name": "The Drowned Altar", "region": "Saltmarsh", "pos": (5, 0), "dark": True,
        "desc": "The altar stands on a dais above the floodwater. Behind it, a great window of green glass "
                "shows a picture of the sun rising from the sea. Someone has scratched out the sun.",
        "exits": {"s": "chapel_nave"},
        "event": "bishop_altar",
        "features": {"window|glass": "The scratches are deep. They were made with fingernails."},
    },
    # =================================================================== UNDERDEEP
    "crypt_stair": {
        "name": "Crypt Stair", "region": "Underdeep", "pos": (0, 0), "dark": True,
        "desc": "The stair below the chapel goes down much further than any crypt should. The salt gives way "
                "to old stone, then to tunnels, timbered and propped. You are in the old tallow mines "
                "under the hill.",
        "exits": {"u": "chapel_nave", "e": "mine_hall"},
        "features": {"timbers": "Miners' marks: arrows, tally scratches, and here and there a little flame symbol."},
    },
    "mine_hall": {
        "name": "The Long Gallery", "region": "Underdeep", "pos": (1, 0), "dark": True,
        "desc": "A long mine gallery with rails running down the middle and carts tipped over. The walls are "
                "streaked with grey fat that drips in the warmth of your lantern. East, a faint starry glitter. "
                "South, candlelight, warm and steady.",
        "exits": {"w": "crypt_stair", "e": "ore_vein", "s": "tallow_camp"},
        "enc": {"chance": 0.35, "groups": [(["tallow_ghoul"], 2), (["crawler"], 2), (["tallow_ghoul", "crawler"], 1)]},
        "features": {"carts|rails": "The carts are full of tallow, rendered from something you'd rather not think about."},
    },
    "ore_vein": {
        "name": "The Starsteel Seam", "region": "Underdeep", "pos": (2, 0), "dark": True,
        "desc": "The tunnel opens into a cavern whose walls glitter with points of light, like a night sky "
                "from before the dark. A seam of black, starry metal runs through the rock.",
        "exits": {"w": "mine_hall"},
        "fixed": {"flag": "golem_dead", "enemies": ["starsteel_golem"],
                  "intro": "Part of the wall turns its head. Stone grinds on stone. The Ore-Warden steps out of the rock."},
        "event": "ore_vein",
        "features": {"seam|ore|metal": "Starsteel. Brann would give his right arm for a lump of it."},
    },
    "tallow_camp": {
        "name": "Tallow's Camp", "region": "Underdeep", "pos": (1, 1), "dark": False, "rest": True,
        "desc": "A cave crowded with candles: on ledges, in niches, on the floor, stuck to the walls, hundreds "
                "of them, all lit. In the middle sits a merchant's cart, and beside it a figure made entirely of "
                "candle-wax, with a wick for hair that burns a little blue flame.",
        "exits": {"n": "mine_hall", "w": "hollow_nest", "e": "choir_gallery", "s": "deep_lake"},
        "npcs": ["tallow"],
        "features": {"candles": "Every one is a different colour. Some of them smell of flowers. Some smell of people.",
                     "cart": "Tallow's wares. Ask to trade."},
    },
    "hollow_nest": {
        "name": "The Brood Pit", "region": "Underdeep", "pos": (0, 1), "dark": True,
        "desc": "A round pit lined with grey, papery egg cases. The smell is unbearable. Something pale and "
                "huge shifts at the bottom.",
        "exits": {"e": "tallow_camp"},
        "items": ["page5", "strong_draught", "firepot"],
        "fixed": {"flag": "brood_dead", "enemies": ["brood_queen", "crawler"],
                  "intro": "The Brood Queen lifts her swollen body out of the egg cases, and her children come with her."},
        "features": {"eggs|cases": "Some of them are moving."},
    },
    "choir_gallery": {
        "name": "The Whispering Gallery", "region": "Underdeep", "pos": (2, 1), "dark": True,
        "desc": "A curved tunnel where every sound comes back to you a moment late, and changed. Your footsteps "
                "return as singing. Ash falls softly from the ceiling like grey snow.",
        "exits": {"w": "tallow_camp", "e": "ash_choir"},
        "items": ["oil"],
        "enc": {"chance": 0.3, "groups": [(["tallow_ghoul"], 1), (["crawler", "crawler"], 1)]},
        "features": {"ash": "Warm. It came from something that burned for a very long time."},
    },
    "ash_choir": {
        "name": "The Ash Choir", "region": "Underdeep", "pos": (3, 1), "dark": True,
        "desc": "A vast cavern shaped like the inside of a bell. Three figures of glowing cinder stand on a ledge "
                "of rock, singing a chord that never resolves. Between them hangs a light like a coal.",
        "exits": {"w": "choir_gallery"},
        "event": "ash_choir",
        "features": {"ledge|singers": "Their song is beautiful and it makes your teeth hurt."},
    },
    "deep_lake": {
        "name": "The Underlake", "region": "Underdeep", "pos": (1, 2), "dark": True,
        "desc": "A black lake under the hill, flat as slate. A narrow shore runs east around it. On the shore "
                "lies a skeleton in a lamplighter's coat, its lantern smashed beside it.",
        "exits": {"n": "tallow_camp", "e": "well_bottom"},
        "items": ["page6", "strong_draught"],
        "enc": {"chance": 0.3, "groups": [(["crawler"], 2), (["tallow_ghoul", "tallow_ghoul"], 1)]},
        "features": {"skeleton|coat|lamplighter": "One of the apprentices who left. He didn't leave. He came down here. "
                                                  "He was carrying a page of Orrin's journal.",
                     "lake": "Nothing reflects in it. Not even your lantern."},
    },
    "well_bottom": {
        "name": "Bottom of the Old Well", "region": "Underdeep", "pos": (2, 2), "dark": True,
        "desc": "A round chamber at the bottom of the town well. Far above, a tiny grey circle of sky. "
                "A rope hangs down the shaft. East stands a door of black glass with three flame-shaped "
                "sockets, and warmth breathes from beneath it.",
        "exits": {"w": "deep_lake", "u": "square", "e": "lightwell_gate"},
        "locks": {"u": {"shards": 3, "msg": "The grate at the top of the shaft is sealed. The rope is no use until it opens."},
                  "e": {"shards": 3, "msg": "The black glass door won't move. Three flame-shaped sockets wait for embers."}},
        "features": {"door|glass|sockets": "Three sockets, shaped like flames. The door to the Lightwell.",
                     "rope|shaft": "The well rope. With the grate open, you could climb straight up to the square."},
    },
    "lightwell_gate": {
        "name": "The Usher's Hall", "region": "Underdeep", "pos": (3, 2), "dark": True,
        "desc": "A long hall of black glass. Your lantern makes a hundred lanterns in the walls. At the far end, "
                "steps lead down into a light the colour of a dying ember.",
        "exits": {"w": "well_bottom", "e": "lightwell"},
        "fixed": {"flag": "usher_dead", "enemies": ["pale_usher"],
                  "intro": "A tall, thin shape unfolds from the reflections. It carries an iron snuffer as long as a "
                           "scythe, and it is looking at your flame."},
        "features": {"walls|reflections": "In the reflections, your lantern is lit. In some of them, it isn't."},
    },
    "lightwell": {
        "name": "The Lightwell", "region": "Underdeep", "pos": (4, 2), "dark": True,
        "desc": "A great round cistern of stone, and at its heart a well of fire, almost gone out, glowing "
                "like the last coal in a grate. Steps spiral down to it. Before it, on a throne of black glass, "
                "sits a man in a lamplighter's coat.",
        "exits": {"w": "lightwell_gate"},
        "event": "lightwell",
        "features": {"well|fire": "The fire that feeds the sun. It is very nearly out."},
    },
}
