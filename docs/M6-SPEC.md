# M6 Spec: "The Lending"

New rings, area extensions, the late spells and upgrades. Written for builders: every package below can be built from this page alone, in parallel, without asking the designer anything. Where a number says TUNE it is a starting value to be set with the simulators in section 15; moves, elements, themes, locks and text are not tunable.

Status: synthesis of three designs ("lore", "mechanics", "retention") after two judging rounds. The base is the lore design (best story fit, cleanest package split). Mechanics' damage fields, rotating-weakness mini-boss and Dread door, and retention's economy ledger, unlit annexes, apex supply and "never stalls" rules are grafted in. Every number in the calibration tables was measured on this codebase on 2026-11-01 with `lamplighter.sim` (see section 15), not inherited.

---

## 0. What changed from the winning design (audit list)

| # | Problem found | Resolution in this spec |
|---|---|---|
| 1 | Godlike forging costs 12,000 gold x 6.42 expected tries = 77k gold, but a ring-5 clear pays ~4k; "three clears" was false | Forge gold retuned (section 11.1); Godlike takes 2 forge slots; full gold ledger (section 16); Odo sells ring-5 materials after the matching boss is dead |
| 2 | Level cap 12 to 14 and a 7th spell slot (`spells.json` `slot_levels` has exactly six entries) | Dropped. Cap stays 12. Ring-5 levels are "10-12". Core only adds a `LEVEL_CAP` constant |
| 3 | Hollow enemies weak to Light (`combat.py` `hit`: Light on a Hollow is x2, plus weak x1.5 for Radiance = x3) | No enemy tagged `hollow` lists `light` in `weak` (rule + per-package test). Light is strong on hollows already |
| 4 | `dealer.check` builds `ring_ids` without de-duplicating (two ring-5 regions, and every extension region, fail "one entry per ring"); `tests/test_dealer.py` `RING_REGION` collapses same-ring regions; `seats()` is cached so a flag cannot gate it | Core fixes all three; `dealer:false`, `dealer_after`, `no_dealer` applied dynamically in `room_for` (section 4, C6) |
| 5 | Validator only accepts a boss room whose flag comes from a fixed fight or `events.enter_<rid>`; area ENTER bosses fail | C4 accepts `rid in areas.collect("ENTER")` |
| 6 | `navigation.objectives` puts "The story is told" ahead of area objectives, so no ring-5 objective could ever be the main one | C7 |
| 7 | `Game.from_dict` does `room_items.setdefault(rid, [])` for rooms missing from a save, so every new room's floor items (receipts, vault loot) are EMPTY for any existing save | C9 (found while verifying; this would soft-lock the Godlike chain for the owner's current save) |
| 8 | `cmd_light` runs the Weeping Wood "Tollroad is lit" block for ANY waypost: after the wood is done every new waypost re-narrates the Tollroad and awards 40 xp again | C8 scopes it to the three wood wayposts and adds `waypost_text` |
| 9 | `engine.light_beacon` narrates "great iron bowl... every window in the house" for every region; `events.after_beacon` runs the area hook BEFORE the Court's own text | C8 adds `beacon_text` and fixes the order |
| 10 | Two affixes share the id `of_ruin` (the curse overwrites the real +5% damage affix, so it can never roll) | C10: positive one becomes `of_havoc` |
| 11 | Rolled-boss text hardcodes "she" and "The Court" | C5: `roll.pron`, `roll.place` |
| 12 | Leftover drafting noise (Count the Hours "buff kindled? no", Gloam-pelt gift, Oskar "grade keepsake", gender in Chart Library, duplicate key flows) | Rewritten; each fixed in the package text |
| 13 | Boss-tag flags `gems_<id>` are engine-reserved (first-kill gems); lore named hook flags `gems_ff_ringmaster` | All hook flags are `<slug>_gems_<x>` |
| 14 | ff/vg both owned the `ff_signal_stair` `u` exit | `vg` owns it (`data/attach/vg.json`); `ff` validates alone (section 2.4) |
| 15 | Fuzz room count quoted as 105/119 | Recomputed from the final tables: 111 (section 5) |
| 16 | Gem inflation (~130 new vs ~93 in the whole old game) | New total ~76 (section 13.3) and band-bonus gems are once per boss |
| 17 | Vigil mobs Court x1.7 hp / x1.65 atk (sim: Legendary loses ordinary pairs); Boss x2.0 | Mobs Court x1.3 (A) / x1.45 (B); bosses Queen x1.45 (A) / x1.8 (B); max two per group (section 14) |
| 18 | Honed/Tempered certain rungs compress the Legendary-to-Godlike gap; Long Quench 20,000 gold | Rungs dropped; Long Quench is Godlike-only, 9,000 gold, keep-the-better, pity (section 11) |
| 19 | Apex needs six Godlike books (~25 Legendary books each by combining): unreachable | Elemental Hearts, a Grand Binding craft tier and apex heat (section 12) |
| 20 | After a beacon the region has no fights, so the faucet dies and the shared Dealer leaves | Two unlit annex regions (`The Fair Below`, `The Waking Cellars`), own regions, `dealer:false`, opened by the beacon |
| 21 | Mirelle's menu is not a `topic_menu`; Ysolde's key is `"wizard"`; `talk_oskar` has no menu | Spec uses `magic_ui.menu` for Mirelle, key `"wizard"`, and C3 rewrites Oskar's talk as a menu |
| 22 | `_AREA_NEWS` REPLACES core `has_news` for that id | `NEWS` only for new NPCs; `EXTRA_NEWS` (OR-ed) for existing ones |
| 23 | Corvin timeline: he is a hermit of 40 years; Aldric went down 50 years ago | Corvin swept the Hospice road for ten years after the lamp left, then went deeper in (section 6) |

**Checked mechanically before this spec was released** (script in the synthesis session, results reproduced by `tests/test_fin.py`): all 54 new rooms parse from the graph tables; every exit has its opposite; same-region exits go to the neighbouring map square; no two rooms of a region share a position; all new rooms are reachable from `hall` ignoring locks; none of the 7 attach exits collides with an existing exit; all JSON snippets parse; every slug-prefixed id used in the text is in the register of section 18; no hollow-tagged enemy lists light as a weakness; every ff/vg encounter table meets the single-enemy share rule. Every existing id, flag and function the spec cites was confirmed present in the code (section 18 lists them).

---

## 1. The idea (answers OPEN DECISION 4)

**What threatens Hollowmere next is a debt.** Before he went down the Well, Aldric (the Keeper before Orrin, Orrin's teacher) did not simply flee. He first walked the edge of the dark and **borrowed a flame from six places**, on one promise written on every receipt: *Held in trust. To be returned lit.* He believed many small lights, lent and not given, could feed the Well so that no Keeper would ever be swallowed. He never came back. Fifty years later every lender is still keeping the promise, because the promise was all that kept them going, and a place that cannot stop becomes a Hollow.

| Lender | What was lent | What they are still doing | Where (slug) |
|---|---|---|---|
| The Hospice of the Moth-Saint | the waylamp | wandering, waiting for a lamp to guide to | Weeping Wood extension (`hos`) |
| The Reedlight | the great lens | guiding boats nobody sends | Saltmarsh extension (`rl`) |
| The Lampwrights' Deep | Corm's pit-lamp and a copy of his quench notes | making, forever | Underdeep extension (`lw`) |
| The Frostfair | the Great Lantern's flame | holding the Fair until spring | ring 5, area A (`ff`) |
| The Vigil | the Signal | watching, without sleep | ring 5, area B (`vg`) |
| The Ember Court | the last coal | dancing | built (Pell's ledger) |

When the Court's beacon is relit it is a signal fire, and the others answer it. The answer reaches Hollowmere as small human things: frost on Hesk's gate and the pump at the Drowned Moth frozen solid (Frostfair), then a town that cannot sleep and lamps that burn too bright (Vigil). Not an army: a debt coming due, aimed at the one place everyone believes holds their lights.

**The player's job is release, not conquest.** The beacon at each place is the return of the loan: it will not feed the Well, it feeds the people. Every place gives the player the same sentence in a different mouth (*I let him*: Corvin held the ladder, Ansel gave the lens proudly, Marit signed, Hale slept, Pell kept the ledger). The recurring answer is forgiveness: *you lent, he took the risk.*

**Light and dark.** The Court's wrongness is dancing, the Frostfair's is waiting, the Vigil's is watching. The Vigil's revelation is the one that matters: night is not the enemy, *endless anything* is. The Hollow King lied that "the dark is gentle". The Vigil teaches that the dark is gentle only when it ends in morning.

**Timeline rule (all copy).** Aldric went down **fifty years** ago (Orrin: "afraid for fifty years"; the Hollow King: "another fifty years"; Tallow's singers: "fifty years"). Every new place counts fifty years. The Court's existing "a hundred years" lines (Pell, the Steward, Cinder Queen) are left alone: the Court is simply older than the Round; do not harmonise.

**The mechanical spine of the through-line.** Six *receipts* (key items) go to Orrin, who opens Aldric's sealed *letter*. The letter says a flame must be *given* or it is only fire, and the Godlike "third quench" is a flame someone chose to give you. Marit (Frostfair) and Hale (Vigil) each *give* the player a coal (the Given Flames). With Corm's notes (Lampwrights' Deep), Brann and Tamsin quench together in the Ember Smithy, which sets `godlike_recipe`. The same two smiths later offer the Long Quench (week-long weapon upgrade). The Vigil's vault holds the Sixfold Chart (apex spell unlock).

**Tone rules for every line of copy.** Melancholy, warm, small human objects (a lunch-pail with a child's name, a skate with the lace still tied, a polished empty hook, a purser's neat sums). Light versus dark, never good versus evil. Humour only from small, kind people. No emoji. No one is a monster; both ring-5 bosses are people the player has already met in the area before the fight.

**Ending-agnostic.** Dawn, Keeper and Thief endings all return the player to `square` with `completed` set. Nothing in M6 may assume which ending was reached (the Crown ending is a true end and never reaches M6 content). Orrin is alive and in bed in the Guild Hall in every post-story state.

---

## 2. Build packages

### 2.1 The package table

Nine packages. Each owns exactly the files listed and edits only the existing files listed. A package never edits another package's files. All new ids start with the package slug (section 3.1).

| Slug | Scope | New files it owns | Existing files it edits (and the edit) | Rooms |
|---|---|---|---|---|
| `core` | Plumbing (section 4). Two phases: core-a (blocking), core-b (fields, attune) | `lamplighter/data/items/core.json`, `tests/test_core_m6.py` | `content.py`, `engine.py`, `validate.py`, `dealer.py`, `powerroll.py`, `entities.py`, `navigation.py`, `npcs.py`, `events.py`, `town.py`, `combat.py`, `areas/__init__.py`, `data/affixes.json`, `tests/test_dealer.py` (helper only) | 0 |
| `hos` | Weeping Wood extension: the Moth-Saint's Hospice | `areas/hos.py`, `data/rooms/hos.json`, `data/enemies/hos.json`, `data/items/hos.json`, `data/regions/hos.json`, `data/attach/hos.json`, `tests/test_hos.py` | none | 7 |
| `rl` | Saltmarsh extension: the Reedlight | same pattern with slug `rl` | none | 6 |
| `lw` | Underdeep extension: the Lampwrights' Deep | same pattern with slug `lw` | none | 6 |
| `ff` | Ring 5 area A: the Frostfair, its annex and Marit's stall | the `ff` set above plus `data/buildings/ff.json` | none | 13 + 3 annex + 1 town |
| `vg` | Ring 5 area B: the Vigil, its annex and Hale's loft | the `vg` set plus `data/buildings/vg.json` | none | 14 + 3 annex + 1 town |
| `late` | The Third Quench (Godlike recipe), two-slot forging, the Long Quench, Orrin/Brann/Tamsin/Pell scenes, journal quest | `areas/late.py`, `lamplighter/quench.py`, `data/items/late.json`, `data/smith.json`, `tests/test_late.py`, `tools/sim_smith.py` | `forge.py`, `forge_ui.py`, `gear.py`, `savecheck.py`, `quests.py`, `data/forge.json` | 0 |
| `arc` | Apex: Sixfold Chart unlock, Hearts, Grand Binding, apex heat | `areas/arc.py`, `tests/test_arc.py` | `spells.py`, `magic_ui.py`, `data/spells.json` | 0 |
| `fin` | Ring-5 Dealer, gem codes, Ysolde's Roll of Lenders, sims, docs, integration tests | `areas/fin.py`, `tools/sim_ring5.py`, `tools/sim_economy.py`, `tests/test_fin.py` | `data/dealer.json`, `data/codes.json` (via `tools/make_code.py`), `docs/V2-PLAN.md`, `README.md`, `version.json` | 0 |

New files under `data/` are loaded automatically (`rooms/*.json`, `enemies/*.json`, `items/*.json`, `buildings/*.json`, `regions/*.json` already; `attach/*.json` is added by core C1). `areas/<slug>.py` is imported automatically by `areas.modules()`.

### 2.2 Order and what can run when

1. **core-a** first. It is small and fully specified in section 4, so area packages code against the contract in parallel. **No area package can run its tests until core-a has landed** (attach files, new lock kinds, the validator fixes and the hook plumbing are needed to load and validate anything). Until then they may write data and code but not test it.
2. `hos`, `rl`, `lw`, `ff` in parallel (each validates alone once core-a is in).
3. `vg` after `ff` (its `vg_ladder` exit `d` points at `ff_signal_stair`, and its attach file adds the matching `u` exit and lock to that room).
4. core-b (fields, attune) lands any time before `ff`/`vg` combat tests; their data may use `field`/`attune` keys earlier (the engine ignores unknown keys).
5. `late`, `arc` after the area packages' item files exist (they read their ids). `late` and `arc` can be built and unit-tested earlier against stub items created in their own tests.
6. `fin` last: dealer.json, codes, docs and the integration playthrough need every id.

### 2.3 Rules every package obeys

- **Imports in `areas/<slug>.py`.** `npcs._register_areas()` imports every area module while `npcs.py` is still being imported. So an area module must NOT do `from ..npcs import line` / `from ..events import give_once` at module level. Import modules lazily inside functions (`def talk_x(g): from .. import npcs, events, town, ui`). Module-level imports are limited to `json`, `random` and other leaf modules.
- **No duplicate hook keys.** `areas.collect` raises on a duplicate key. Every `ENTER`, `AFTER_FIXED`, `UNLOCK`, `AFTER_BEACON`, `PRESENT`, `NEWS`, `STOCK`, `NPCS`, `BOSS_TIPS` key is a room, flag, npc or item id of the owning slug (so unique by construction). The merged hooks (`TOPICS`, `EXTRA_NEWS`, `SELLS`, `RUMOURS`) are keyed by EXISTING npc ids and merge across modules (section 4, C3).
- **Locks state exactly what they need** and name where to get it. A lock whose flag can be re-cleared (a Wizard call-back pops a boss flag) carries `remember`.
- **Key items** (`kind: "key"`) cannot be dropped, sold or stashed, so they are safe once taken. Quest items that must never be missable are either on the floor of a room behind no lock the player can lose, or `give_once` from a guaranteed event. Never from a bonus-drop roll.
- **Gear rewards** from a boss use `areas.give_first(g, iid)` (core C3: gives it once ever, flag `got_<iid>`), so call-backs do not duplicate named gear. Key items use `events.give_once` (already exists).
- **No `hollow`-tagged enemy lists `light` in `weak`.** Each area test asserts this for its own enemy file.
- **Free retreat on rolled bosses** (`powerroll.boss_scene`), mercy as built, no destroyed items on forge failure, gems never buy Godlike, curses only from Dealers.
- **NPCs.** Every new NPC id needs a `NPCS` entry (`name`, `aliases` = lowercase first name plus role words, `desc`, optional `shop: True`, optional `where` lambda for residents) and a module-level `talk_<id>(g)` (the validator checks both). Talk menus use `npcs.topic_menu`; residents are listed in a field room's `npcs`, hidden by `PRESENT` once their building is built, and found in their Hollowmere room through `where`.
- **Group size** in any random encounter table: at most 2 enemies. Ring 5 (`ff`, `vg`): at least 40% of weight on single-enemy groups in A, 55% in B.
- **Every room has a `desc` and at least one `features` entry.** Every heavy or charge move has a `tell`. Every rolled boss has exactly 5 flavour lines.
- **Text:** plain ASCII quotes, no emoji, no markup the existing `ui` does not support (`{gold}`, `{grey}`, `{amber}`, `{sky}`, `{ember}`, `{brine}`, `{moss}`, `{bone}`, `{hollow}`, `{night}`, `{bgreen}`, `{bred}`, `{/}` are used by existing code). A `wake` string may contain exactly one `%d` and no other `%`.

### 2.4 The cross-region exits (exactly who owns what)

| Exit | Declared by | Where |
|---|---|---|
| `moth_shrine` e to `hos_path` | `hos` | `data/attach/hos.json`; `hos_path` declares `w` back |
| `bog_lights` s to `rl_causeway` | `rl` | `data/attach/rl.json` |
| `crypt_stair` s to `lw_door` | `lw` | `data/attach/lw.json` |
| `gate` w to `ff_frost_road` | `ff` | `data/attach/ff.json` |
| `hearth_stall` e to `ff_stall` | `ff` | `data/attach/ff.json` |
| `ff_ice_cellars` d to `ff_below_stair` | `ff` | `rooms/ff.json` (same package) |
| `ff_signal_stair` u to `vg_ladder` (with its lock) | **`vg`** | `data/attach/vg.json`; `vg_ladder` declares `d` back to `ff_signal_stair` |
| `tower` w to `vg_loft` | `vg` | `data/attach/vg.json` |
| `vg_great_court` d to `vg_cellar_stair` | `vg` | `rooms/vg.json` (same package) |

`ff_stall` and `vg_loft` are rooms of region `Hollowmere` defined in `ff`'s and `vg`'s room files.

---

## 3. Conventions

### 3.1 Ids, slugs and the register

Every id introduced by a package starts with its slug and an underscore: rooms, enemies, items, npcs, buildings, flags, quest ids, function names (`talk_<npc_id>`). Region *display* names are exempt. Engine-reserved flag families (never reuse): `lit_<room>`, `beacon_<region>`, `opened_<room>_<dir>`, `gems_<enemy>`, `deaths_<enemy>`, `power_<enemy>`, `talked_<npc>`, `got_<item>` (core C3), `codes_used`. Flags set by hooks that mean "gems already granted" are `<slug>_gems_<x>`.

Slug to region:

| Slug | Region id(s) | ring | levels | gear |
|---|---|---|---|---|
| `hos` | The Moth-Saint's Hospice | 1 | 3-5 | Common - Rare |
| `rl` | The Reedlight | 2 | 5-6 | Uncommon - Rare |
| `lw` | The Lampwrights' Deep | 3 | 7-8 | Rare |
| `ff` | The Frostfair; The Fair Below (annex) | 5 | 10-11; 11-12 | Ultra - Legendary; Legendary |
| `vg` | The Vigil; The Waking Cellars (annex) | 5 | 11-12; 12 | Legendary - Godlike; Godlike |

Both ring-5 areas are `ring: 5` (rings are difficulty bands; ring 5 has two spokes).

### 3.2 Data shapes (all existing; examples from the Court)

- `data/rooms/<slug>.json`: object keyed by room id. Keys: `name`, `region`, `pos` [x, y], `dark`, `desc`, `exits` {dir: id}, optional `locks` {dir: lock}, `enc` {"chance": f, "groups": [[[enemy ids], weight], ...]}, `items` [ids, repeats allowed], `npcs` [ids], `features` {"kw|kw2": text}, `rest`, `outpost`, `waypost`, `fixed` {"flag", "enemies", "intro"}, `boss` (flag), `boss_name`, `beacon`, `beacon_oil`. **New optional keys (core):** `wake`, `beacon_text`, `waypost_text`, `field`, `no_dealer`. Same-region compass exits must go to the neighbouring map square (validator); `u`/`d` and cross-region exits are free.
- `data/enemies/<slug>.json`: object keyed by id: `name`, `hp`, `atk`, `def`, `dodge`, `fire` (flare/fire intake multiplier, optional), `xp`, `gold` [lo, hi], `tags`, `weak`, `resist`, `desc`, `moves` [{name, kind, power, weight, tell, status [name, turns, amount], hits, drain, summon, only_if, then}], `extra_moves` {name: move} (for `charge`), `phases` [{at, msg, moves, status}], `drops` [[id, chance]], optional `roll` {story, flavour [5], bonus [{item, from, to, count}], pron, place}, optional `attune` (core C14).
- `data/items/<slug>.json`: `name`, `kind`, `value`, `desc`, `rarity`, `stats`, `mult`, `stack`, `use`. Usable consumable keys: `heal`, `oil`, `regen`, `dread` (either sign), `cleanse`, `focus`. Mult keys: `dmg phys fire light heal ice water shadow earth spell` (0.5 to 5).
- `data/regions/<slug>.json`: a JSON **list** of `{id, ring, levels, gear, blurb}` plus optional `dealer` (bool, default true) and `dealer_after` (flag name).
- `data/buildings/<slug>.json`: `{id: {name, room, resident, cost {gold, items}, minutes, steps, rent, blurb}}`. Needs a vacant-plot lock in some room.
- `data/attach/<slug>.json` (new, core C1): `{existing_room_id: {"exits": {dir: room}, "locks": {dir: lock}, "npcs": [..], "items": [..]}}`.

Move notation used in the tables below: `Name (kind P wW; extras; "tell")` = `{"name", "kind", "power": P, "weight": W, "tell"}`; `hits N`, `status burn 3,5` = `["burn", 3, 5]`, `drain N`, `summon ID`, `only_if can_summon`, `charge->Y` = a `charge` move with `then: Y` and `Y` in `extra_moves`. Statuses that exist: burn bleed poison stun weak exposed blind regen enraged (and shroud).

### 3.3 Reading the room tables

`Graph` tables list id, name, grid pos (x, y), exits (dir to id), locks (dir: requirement and the exact message), specials. `Contents` tables list `desc` (seed text; builders may expand but keep the facts), `features` keywords with text, items, encounters. Encounter groups are written `[a,b]xW` meaning a group of those enemy ids with weight W.

### 3.4 The six receipts, the letter and the notes (final copy, paste verbatim)

Receipts are `kind: "key"`; the text below is the item `desc` (read with `examine`). All are signed "A." and share the phrase *Held in trust. To be returned lit.*

- `hos_receipt` "Receipt: the Moth-Saint's Hospice": *Received of the Hospice of the Moth-Saint, one waylamp, brass, wick trimmed, to guide the Keeper home. Held in trust. To be returned lit. Brother Corvin held the ladder. He says he does not mind. He minds. -A.*
- `rl_receipt` "Receipt: the Reedlight": *Received of the Reedlight, the great lens, to see the Well from far off. Ansel says the boats will find their own way for a winter. Held in trust. To be returned lit by spring. The kettle was on. -A.*
- `lw_receipt` "Receipt: the Lampwrights' Deep": *Received of the Lampwrights, Corm's pit-lamp, and a copy (a copy, not the book) of his notes on the quench. He asked what I intend. I said: nothing anyone need pay for. He did not believe me. He lent it anyway. Held in trust. -A.*
- `ff_receipt` "Receipt: the Fair at Wintering": *Received of the Fair at Wintering, the flame of the Great Lantern, in trust until the first thaw. The Lamp-Master swore to hold the Fair until it came home. Marit Ostrand wrote my name in the book of lenders herself. She has a steadier hand than mine. -A.*
- `vg_receipt` "Receipt: the Vigil": *Received of the Vigil, the Signal. The Order will watch the east until I send word that it is done, and then they may close their eyes. I have never asked anyone for a longer promise. Held in trust. -A.*
- `late_receipt_court` "Receipt: the Ember Court" (Pell gives it, section 11): *Received of the Ember Court, the last coal of the last dance. The Queen would not be parted from the music, so I took the fire and left the music. I do not think that was a fair trade. Held in trust. -A.*

`late_aldrics_letter` "Aldric's Letter" (Orrin opens it; `late` owns the item): *To the one who comes after, whoever lights the lamps now. I thought a great many small lights, lent and not given, could feed the Well so that no Keeper need ever be swallowed. I was wrong. A lent flame is a debt, and a debt warms no one. The Well wants a flame given freely, or it wants nothing. I did not have the courage to give mine. So I took theirs, and wrote it down, so that someone could return it. Return it. Light each of them again where it belongs, with your own oil if you must. They will not feed the Well. They will feed the people, which I should have known was the same thing. And if the smiths ask how a blade is made that can outlast the dark, tell them what Corm knew: water takes the heat, oil takes the brittleness, and the third quench is a flame that someone chose to give you. I am sorry. I am so very sorry. -Aldric. (Tell Orrin the wick was always his to trim.)*

`lw_quench_notes` "Corm's Notes on the Quench": *Two quenches I know: water for the heat, oil for the brittle. A third was in the book Aldric took, and he copied it back to me wrong, or I read it wrong. It said the third wants fire, and not any fire. I have tried every fire in the Deep. They all take the edge off. -Corm.*

---

## 4. Package `core`: plumbing (existing files, exact contracts)

Everything here is an extension: no existing behaviour changes except where a row says "fixes". `python -m unittest discover` (632 tests, ~45 s today) must still pass after every row, with the Court's output byte-identical.

**Phase core-a (blocks every other package):** C1 to C12. **Phase core-b:** C13, C14.

| # | File / function | Exact behaviour |
|---|---|---|
| C1 | `content.py` after the ROOMS loop | **Attach patches.** For each `data/attach/*.json` in sorted order: `{room_id: {"exits": {dir: room}, "locks": {dir: lock}, "npcs": [..], "items": [..]}}`. Unknown `room_id`: `ValueError`. An `exits` or `locks` key that already exists on the room: `ValueError` naming the file. `npcs`/`items` are appended (`setdefault` the lists). The patched `ROOMS` is what everything else sees (validator, `Game.__init__` `room_items`, dealer seats). |
| C2 | `engine.Game.unlocked`, `Game.move` | **Lock kinds.** Keep the `remember` check first, then add (order after the existing branches is irrelevant, each is a separate key): `"flags": [names]` true when every flag is truthy; `"relic": "lamp"` (a type, or a list of types) true when any item in `player.equipment.values()` is a gear instance (`gear.is_instance`) with a socketed relic (`gear.socketed(iid)`) whose `ITEMS[rel["base"]]["relic"]` is in the list; `"dread": {"min": a, "max": b}` true when `a <= player.dread <= b` (missing bound = 0 / 100); `"all": [sub-locks]` true when every sub-lock is `unlocked`. When a move is refused, after printing `lock["msg"]`, print one grey status line built by `Game.lock_status(lock)`: element lock: `Equipped books: Fire, Earth` (or `none`); relic lock: `Worn relics: Lamp (epic)` (or `none`); dread lock: `Dread is 31 now.`; flags lock: `n of m done.`; recurse into `all`; item/flag/building/shards: no line. Existing tests that assert the lock message still pass (the status line is an extra line). |
| C3 | `areas/__init__.py`, `npcs.py` | **Merged hooks.** New helpers in `areas`: `merged(attr)` = `{key: [value, ...]}` across modules (no duplicate error); `topics(g, nid)` = concatenated `[(label, handler)]` from every `TOPICS[nid]` fn; `extra_news(g, nid)`; `sells(g, nid)`; `rumours(g)` (every module's `RUMOURS(g) -> [str]`); `give_first(g, iid, n=1)` (if `g.flags.get("got_"+iid)` return False; else set it, `g.give(iid, n)`, return True). Hook definitions: `TOPICS = {npc_id: fn(g) -> [(label, handler(g))]}`, `EXTRA_NEWS = {npc_id: fn(g) -> bool}`, `SELLS = {npc_id: fn(g) -> [item ids]}`, `RUMOURS = fn(g) -> [str]`, `PRICES = {item_id: gold}` (via `collect`, duplicate = error), `AFTER_GAIN = {item_id: fn(g)}` (via `collect`). **npcs changes:** `talk(g, nid)` also stores `_speaker_g[0] = g`; `topic_menu(options)` becomes a loop that appends `areas.topics(g, _speaker[0])` after the caller's options; choosing an area topic runs `handler(g)` (inside the same cleared "You: ..." screen) and shows the menu again; choosing a caller option returns its key exactly as before. `has_news` = old logic OR `areas.extra_news(g, nid)` (the `_AREA_NEWS` REPLACE rule stays for NEW npcs only). `stock_for` appends `areas.sells(g, nid)`. `price()` consults `areas.collect("PRICES")` after the local `PRICES`. `talk_maeve`'s rumour pool becomes `RUMOURS + areas.rumours(g)`. **`talk_oskar`** keeps its first-meeting branch and otherwise becomes a menu loop: `topic_menu([("Ask for advice about the marsh", "tips")])`; `tips` prints a random existing tip; leaving prints `Mind the water.` (so Oskar can have topics). Every NPC that uses `topic_menu` today (orrin, maeve, hesk, brann, corvin, pell, tamsin, wizard, joss, odo) gains area topics automatically. **Mirelle does not use `topic_menu`** (`talk_mirelle` calls `magic_ui.menu`); her M6 option lives in `magic_ui.menu` (package `arc`). |
| C4 | `validate.py` | (a) A boss room is valid if its flag is set by a `fixed` fight, an `events.enter_<rid>`, **or** `rid in areas.collect("ENTER")`. (b) Lock requirement kinds are `item flag flags shards building element relic dread all`; `flags` is a non-empty list of strings; `relic` is a type (or list) present in `RELIC_INFO["types"]`; `dread` has int `min` and/or `max` in 0..100; `all` is a non-empty list of valid sub-locks (sub-locks need no `msg`, the top lock does); `remember` is a string. (c) `roll.pron` has all of `subj obj poss`; `roll.place` is a string. (d) Room `field` (C13) and enemy `attune` (C14) validation. (e) Every item id named in `forge.json` (`tiers[*].items`, `relic_tiers[*].items`) and `smith.json` (`items`) exists. (f) Region keys `dealer` (bool) and `dealer_after` (a string; if it starts with `beacon_` the rest is a real region id). (g) `AFTER_GAIN` keys are item ids; `TOPICS`/`EXTRA_NEWS`/`SELLS` keys are npc ids (`npcs.NPCS`); `PRICES` keys are item ids. (h) `wake` contains at most one `%d` and no other `%`. (i) Room key `no_dealer`, if present, is a bool. (j) `dealer.check` de-duplicates (C6). |
| C5 | `powerroll.py` | **Roll text is not gendered.** `roll.pron` = `{"subj","obj","poss"}` (default she/her/her) and `roll.place` (default `"The Court"`). `show()` prints `The stronger <subj> is, the more <subj> pays.` and `(<place> holds back. Your bad luck so far has lowered the ceiling to N.)`; `boss_scene` prints `<Subj> does not follow.` on a flee. With defaults the Queen's output is byte-identical. `subj: "it"` is allowed. |
| C6 | `dealer.py` | (a) `check()`: `ring_ids = sorted({str(i["ring"]) for ... if i["ring"] >= 1})` (set, de-duplicated). (b) `seats(ring)` (still cached) also excludes rooms of regions with `"dealer": false` and rooms with `"no_dealer": true`. (c) `room_for(g, ring, day)` filters the shuffled seats to those whose region has no `dealer_after` flag, or whose flag is set: `info.get("dealer_after")` -> `g.flags.get(flag)`. The seats cache stays static; the flag is read live. (d) Almanac-style callers use `room_for` unchanged. (e) `tests/test_dealer.py`: `RING_REGION` becomes first-region-wins (`setdefault`) so the base region of each ring is used: `for rid, i in REGION_INFO.items(): RING_REGION.setdefault(i["ring"], rid)`. |
| C7 | `navigation.py`, `engine.move` | **Objectives.** In `objectives()` the `q == "done"` ladder's final `else` (the "The story is told..." line) is added only if no area adds a non-side objective: probe with `areas.call_each("OBJECTIVES", game, probe)` where `probe(text, room, side=False)` records `side`; if every recorded entry is a side objective (or none), add the old line. The normal `areas.call_each("OBJECTIVES", game, add)` at the end stays. **Boss tips.** New `navigation.boss_tip(room_id)` = `BOSS_TIPS.get(rid) or areas.collect("BOSS_TIPS").get(rid)`; `hint_lines` and `engine.move`'s DANGER AHEAD block both call it (today `move` reads `navigation.BOSS_TIPS` directly and ignores area tips). |
| C8 | `engine.py`, `events.py` | **Text hooks.** `death()`: before the generic fallback, `w = ROOMS[self.last_rest].get("wake")`; if present `narrate(w % lost if "%d" in w else w)`. `light_beacon()`: use `r.get("beacon_text")` instead of the hard-coded "great iron bowl" narration. `cmd_light()`: waypost narration uses `r.get("waypost_text")` when present; **fix:** the Weeping Wood block (`wayposts` quest start, `lit == 3`, "The Tollroad is lit", 40 xp) runs only when `self.room_id in ("wood_path", "thicket", "moth_shrine")`. `events.after_beacon`: print the built-in Court narration first, THEN call `areas.lookup("AFTER_BEACON", region, g)`. |
| C9 | `engine.Game.from_dict` | **Fixes the old-save item bug.** `g.room_items.setdefault(rid, list(ROOMS[rid].get("items", [])))` instead of `[]`, so rooms added after a save was made get their floor items (receipts, vault loot). Test: load a save whose `room_items` lacks every `hos_*` room and assert `hos_receipt` is on the floor of `hos_scriptorium`. |
| C10 | `data/affixes.json` | Rename the positive weapon affix `of_ruin` (+5% dmg) to `of_havoc`, name "of Havoc". The curse keeps `of_ruin` (saved Dealer bargains reference it). Test: both ids exist and the roll pool contains `of_havoc`. |
| C11 | `engine.after_gain`, `engine.cmd_journal` | `after_gain(iid)` also calls `areas.lookup("AFTER_GAIN", iid, self)`. The journal `order` list gains `"late_lending"` (quest defined by `late`). |
| C12 | `entities.py`, `town.py` | `entities.LEVEL_CAP = 12` replaces the literal in `gain_xp` (cap NOT raised). `town.summary_lines` shows the resident's display name (`npcs.NPCS[b["resident"]]["name"]`, lazy import) instead of `b["resident"].title()` (which prints `Ff_Marit`). |
| C13 | `combat.py` (core-b) | **Room damage fields.** Room key `"field": {"name": "Black Ice", "fire": 0.75, "earth": 1.25, "msg": "..."}`. In `Combat.hit`, directly after `dmg *= p.mult(kind) * p.dread_damage_mult()`: `if kind not in ("phys", "true"): dmg *= self.g.room.get("field", {}).get(kind, 1.0)`. So it applies to spells, flares (`light`) and fire items (firepot), never to weapon blows. At the start of a fight in such a room print `Field: Black Ice (Fire x0.75, Earth x1.25)` and, the first time only (flag `field_seen_<room>`), the field's `msg`. Validator: keys limited to the six elements plus `name` and `msg`; values 0.5 to 1.5. `sim.fight(room=...)` sets `game.room_id`, so the simulators see fields. |
| C14 | `combat.py`, `entities.py` (core-b) | **Rotating weakness.** Enemy key `"attune": {"every": 2, "stances": [{"name", "weak": [..], "resist": [..], "msg"?}, ...]}` (2 to 4 stances). In `Combat._run`, once before the first round and again after every `self.round += 1`, each living enemy with `attune` takes stance `((round - 1) // every) % len(stances)`: its `weak`/`resist` lists are replaced; when the stance changes after round 1 print `{hollow}<name> shifts: <stance name>.{/}` (or the stance `msg`). `render()` adds a grey line for such an enemy: `stance: <name>, next: <name> in N round(s)`. `best_spell` and `suggest` already read `e.weak`/`e.resist` live. Validator: each stance has 1 to 2 weak, 0 to 2 resist, no overlap, valid elements; an `attune` enemy must not be tagged `hollow` with `light` in any `weak` (the general rule). |

### 4.1 Core tests (`tests/test_core_m6.py`)

Attach merge, conflict error, unknown-room error; each lock kind open / shut / status line / `all`; `TOPICS`, `EXTRA_NEWS`, `SELLS`, `RUMOURS`, `AFTER_GAIN`, `PRICES` merging across two stub modules (inject stub modules into `areas._mods`); `topic_menu` runs an area handler and redraws; Oskar topics; validator accepts an ENTER boss room and rejects a bad lock, bad `wake`, bad `field`, bad `attune`; pronoun defaults leave the Queen's text unchanged and `he`/`it` render; `wake` text used for a room with it; `beacon_text`; waypost outside the wood does not re-narrate the Tollroad; `after_beacon` order; `from_dict` fills missing rooms' items; `of_havoc`; `LEVEL_CAP == 12`; dealer: `room_for` honours `dealer:false`, `no_dealer`, `dealer_after`; `check` passes with two same-ring regions; field math (spell vs phys vs flare vs true); attune cycling, telegraph and `best_spell` following it.

### 4.2 Core sample for stubs

Packages test against the contract before `fin` lands by calling `python tools/validate_content.py` (must be clean for their own files plus core) and their own `tests/test_<slug>.py`. A package whose data references another package's ids (only `late`, `arc`, `fin`, and `vg` -> `ff_signal_stair`) declares those ids in a test fixture and says so.

---

## 5. Room, region and id totals (for the fuzzer and the validator)

| Package | New rooms | Regions |
|---|---|---|
| `hos` | 7 | The Moth-Saint's Hospice |
| `rl` | 6 | The Reedlight |
| `lw` | 6 | The Lampwrights' Deep |
| `ff` | 13 field + 1 Hollowmere (`ff_stall`) + 3 annex = 17 | The Frostfair, The Fair Below |
| `vg` | 14 field + 1 Hollowmere (`vg_loft`) + 3 annex = 18 | The Vigil, The Waking Cellars |
| total | **54** | 7 new regions |

Existing rooms: 57 (Court 13, Hollowmere 17, Saltmarsh 8, Underdeep 11, Weeping Wood 8). **New total 111.** `tools/fuzz.py` prints `len(ROOMS)` itself, so nothing hard-coded changes; the acceptance run is `python tools/fuzz.py 200 2000 0` reaching 111/111.

---

## 6. Package `hos`: The Moth-Saint's Hospice (Weeping Wood extension)

**Story.** Behind the Shrine of the Moth stood the pilgrims' house the shrine belonged to. A brass **waylamp** hung over its gate so no traveller was lost in the wood. Aldric borrowed it. The grey moths that plague the wood are the saint's own, bound to the lamp, hunting a lamp that is not there. **Corvin** was the Hospice's lay-brother: he held the ladder the night the lamp came down, swept the empty road for ten years after, and then went deeper into the wood and became the hermit the player knows (forty years). Optional; reachable the moment the Shrine of the Moth waypost is lit (levels 3 to 5), 40 to 50 minutes.

**Region** (`data/regions/hos.json`): `[{"id": "The Moth-Saint's Hospice", "ring": 1, "levels": "3-5", "gear": "Common - Rare", "blurb": "A pilgrims' house behind the Moth Shrine, where a lamp used to hang.", "dealer": false}]`

**Attach** (`data/attach/hos.json`):
```json
{"moth_shrine": {"exits": {"e": "hos_path"},
  "locks": {"e": {"flag": "lit_moth_shrine", "msg": "A narrow path runs east behind the saint's worn statue, but the dark there is thick as felt and your lantern will not push into it. Light the waypost at this shrine (type 'light') and the saint's road will show."}}}}
```

### 6.1 Graph

| Room id | Name | Pos | Exits | Locks / specials |
|---|---|---|---|---|
| `hos_path` | The Saint's Road | 0,0 | w `moth_shrine`, e `hos_gate`, s `hos_orchard` | |
| `hos_gate` | The Lych-Gate | 1,0 | w `hos_path`, e `hos_belfry`, s `hos_cloister` | e: `{"item": "hos_belfry_key", "msg": "The belfry door is barred from inside, and the bar has a keyhole of its own. The Almoner keeps the belfry key. He keeps it in the refectory, where he is still laying places for guests who will never come."}`; `waypost`; `wake` |
| `hos_belfry` | The Belfry | 2,0 | w `hos_gate` | `fixed` {flag `hos_vesper_dead`, enemies [`hos_vesper`]}, `boss` `hos_vesper_dead`, `boss_name` "The Vesper Moth" |
| `hos_orchard` | The Pilgrims' Orchard | 0,1 | n `hos_path`, e `hos_cloister` | |
| `hos_cloister` | The Cloister | 1,1 | n `hos_gate`, w `hos_orchard`, e `hos_refectory`, s `hos_scriptorium` | s: `{"flag": "hos_almoner_dead", "remember": "hos_scriptorium_open", "msg": "The scriptorium is bolted from within. The bolt is the Almoner's, and the Almoner is in the refectory, east of the cloister. Defeat him and the door will open."}` |
| `hos_refectory` | The Refectory | 2,1 | w `hos_cloister` | `fixed` {flag `hos_almoner_dead`, enemies [`hos_almoner`], intro "The Almoner looks up from the long table. 'Are you expected?' he asks, and does not wait for the answer."}, `boss` `hos_almoner_dead`, `boss_name` "Brother Odran the Almoner" |
| `hos_scriptorium` | The Scriptorium | 1,2 | n `hos_cloister` | |

### 6.2 Contents

| Room | desc seed | features | items | enc (chance; groups) |
|---|---|---|---|---|
| `hos_path` | Milestones eaten by moths line a road the wood has almost taken back. Each is carved with a lamp. | `milestones`: "Every one says HOSPICE, and a number counting down. The last says 0." | | .30; [`hos_waymoth`]x3, [`hos_waymoth`,`hos_waymoth`]x1, [`hos_pilgrim`]x1 |
| `hos_gate` | A lych-gate of grey timber. Over the arch an empty brass hook, and beneath it the old waypost, cold. | `hook`: "Polished by hand. Not a speck of rust. Somebody still comes here to wipe it." | | none |
| `hos_belfry` | A small bell-tower, the bell wrapped in felt so it cannot wake what sleeps in the rafters. | `bell`: "Felt, tied with a hundred careful knots. Someone did not want it rung." | | none (fixed) |
| `hos_orchard` | Pears and apples hang ripe on trees nobody tends. The grass between them is worn into paths that go in circles. | `pears`: "They taste of nothing. They settle the stomach all the same." | `hos_windfall` x2, `honeycake` | .35; [`hos_pilgrim`]x3, [`hos_pilgrim`,`hos_waymoth`]x2 |
| `hos_cloister` | A square of arches round a fountain full of moth wings. Pilgrims walk the square in circles, carrying lamps with no flame. | `fountain`: "Full of grey wings. The water underneath is still clear." | `oil` | .30; [`hos_pilgrim`]x2, [`hos_pilgrim`,`hos_pilgrim`]x1, [`hos_waymoth`,`hos_pilgrim`]x1 |
| `hos_refectory` | Long tables laid for fifty guests, a bowl at each place. | `tables`: "Fifty places set. Fifty bowls of the same grey soup, each still steaming." | | none (fixed) |
| `hos_scriptorium` | Shelves of guest-books and a lockbox with its lid up. | `guestbook`: "The last entry, in a steady hand: The Keeper thanks the house for its lamp. Will return it lit. -A." | `hos_receipt`, `hos_pilgrims_staff`, `hos_moth_mantle`, `strong_draught` | none |

`wake` (`hos_gate`): "You wake under the Hospice gate, beside the polished hook, with someone's old cloak over you. Your purse is lighter by %d gold. The cloak is gone when you look again."

### 6.3 Enemies (`data/enemies/hos.json`; scale = Weeping Wood x1.3, bosses by sim)

| id | Name | tags | hp/atk/def/dodge | xp | gold | weak | resist | Moves | Drops |
|---|---|---|---|---|---|---|---|---|---|
| `hos_pilgrim` | Hollow Pilgrim | hollow | 50/11/4/0 | 22 | 7-18 | fire, earth | water | Staff Rap (attack 1.0 w3); Plod On (defend w1); Penance (heavy 1.8 w1; "kneels, then lunges") | `hollow_dust` .5, `rootwood` .4, `essence_light` .3 |
| `hos_waymoth` | Waylamp Moth | hollow, beast, swarm | 30/9/0/22 | 16 | 0-7 | fire, ice | earth | Flutter (attack 0.7 hits 2 w3); Scale Dust (debuff blind 2 w1) | `hollow_dust` .4, `essence_light` .35 |
| `hos_almoner` | Brother Odran the Almoner | hollow, undead, elite | 175/14/7/0 | 85 | 25-35 | fire, shadow | water | Alms Bowl (attack 1.0 w3); Distribute (summon `hos_pilgrim`, only_if can_summon, w1; "ladles out another guest"); Tithe (heavy 2.1 w2; "holds out the bowl"). Phase none | `strong_draught` 1.0, `hollow_core` 1.0, `essence_light` 1.0 (key by hook) |
| `hos_vesper` | The Vesper Moth | hollow, beast, boss | 288/15/6/8 | 130 | 70-90 | fire, ice | earth, shadow | Wingbeat (attack 1.0 w3); Scale Dust (debuff blind 2 w2); Drink the Flame (drain 0.8 drain 12 w2; "turns her face to your lantern"); Dusk (heavy 2.2 w2; "folds her wings back"). **Phase 0.5**, msg "She is looking, not at you, but at the empty hook above the gate she can see through the wall.": Wingbeat 1.1 w3, Scale Dust w2, Drink the Flame drain 14 w2, Dusk 2.4 w2, Beat of Longing (attack 0.7 status weak 2,0 w1) | `hollow_core` 1.0, `essence_light` 1.0 x2, `strong_draught` 1.0 |

Calibration (side boss, section 14.4): Vesper is Mother x1.8 hp / x1.4 atk. Target for a level-4 player in the wood's best gear: 90 to 97% first-attempt win, 40 to 50% health left.

### 6.4 Hooks (`areas/hos.py`)

- `AFTER_FIXED["hos_almoner_dead"]`: narrate "The Almoner sets down his bowl. 'Dismissed,' he says, to nobody, and the fifty bowls go cold at once." `events.give_once(g, "hos_belfry_key")`; grey hint "(The belfry key. The scriptorium bolt has slid back.)"; once (`hos_gems_almoner`) +2 gems.
- `AFTER_FIXED["hos_vesper_dead"]`: narrate "The great moth settles on your lantern, light as a hand. For a moment it is only a moth, and your flame is only a flame. Then it opens its wings and goes up through the belfry roof, and does not come back, and the sky behind it is very slightly less grey." `areas.give_first(g, "hos_waylamp")`.
- `BOSS_TIPS["hos_belfry"]`: "She is a Hollow, so flares do double and blind her. She drinks oil with Drink the Flame: keep 30 or more in the lantern. Guard Dusk."
- `TOPICS["corvin"]` (any of the three, each shown only when it applies):
  - after `lit_moth_shrine`, not `hos_corvin_told`: "Ask about the road behind the shrine" (sets `hos_corvin_told`): *"I don't walk it. I used to sweep it. I was the Hospice's lay-brother, and when the pilgrims stopped coming I went deeper in, and the wood took the rest of me. But the night the Keeper came for the lamp, I held the ladder. He was so polite. Nobody warned us that polite men can be wrong."*
  - after `hos_vesper_dead`, not `hos_corvin_vesper`: "Tell Corvin about the Vesper Moth" (sets `hos_corvin_vesper`): *"She came to your lantern? Of course she did. ...You'll think me a sentimental old fool. The raven is her great-grandson."* Then he hands over three honeycakes (once, `areas.give_first`-style flag `got_hos_corvin_gift`).
  - holding `hos_receipt`, not `hos_corvin_receipt`: "Show Corvin the receipt" (sets `hos_corvin_receipt`): he reads it, long silence: *"He minds. He does mind. Thank you for writing that down."*
- `RUMOURS`: after `hos_corvin_told`: "Corvin's started sweeping the path behind the shrine. Says he's spring-cleaning. It's October."
- `UNLOCK`: none needed (the lock message is the teaching).
- `OBJECTIVES` (all side): room `moth_shrine`, text "Behind the Shrine of the Moth, a road runs east. Light the waypost to see it", when `moth_shrine` visited and not `lit_moth_shrine`; room `hos_refectory`, "The Hospice: the Almoner keeps the belfry key in the refectory", when `hos_path` visited and not `hos_almoner_dead`; room `hos_belfry`, "The Vesper Moth waits in the belfry", when `hos_almoner_dead` and not `hos_vesper_dead`.

### 6.5 Items (`data/items/hos.json`)

| id | kind | rarity | value | stats / mult / use | desc |
|---|---|---|---|---|---|
| `hos_pilgrims_staff` | weapon | rare | 140 | atk 8, wil 5; mult light 1.12 | A walking staff worn smooth by a thousand hands, still faintly warm. |
| `hos_moth_mantle` | armor | rare | 130 | def 6, agi 2, dodge 3 | A grey cloak that other things find hard to see. |
| `hos_waylamp` | trinket | rare | 150 | wil 3, hp 12, oil_save 1 | The Hospice's second lamp, kept for the lay-brother who held the ladder. It lights the way home. |
| `hos_windfall` | consumable | common | 14 | use heal 25, dread -10 | A pear that tastes of nothing and settles the stomach. |
| `hos_belfry_key` | key | common | 0 | | A small iron key on a moth-shaped fob. |
| `hos_receipt` | key | common | 0 | | (section 3.4) |

### 6.6 Tests (`tests/test_hos.py`)

Attach lock text and both state transitions; `hos_gate` e and `hos_cloister` s locks with exact messages; scriptorium stays open after a call-back pops `hos_almoner_dead` (`remember`); Almoner then Vesper with a strong scripted player; key given once (second win does not duplicate); `hos_waylamp` once only; `hos_receipt` on the scriptorium floor of a fresh game AND of a save made before the package existed (core C9); Corvin topics gated; no `hollow` enemy weak to `light`; validator clean; fuzz reaches all 7 rooms.

---

## 7. Package `rl`: The Reedlight (Saltmarsh extension)

**Story.** The marsh lighthouse. Its keeper, **Ansel Tolliver**, lit the great lens every dusk so the ferries could cross; Aldric borrowed the lens "for a winter" and Ansel, proud to be asked, said yes. Ansel is **Oskar the ferryman's brother**. Oskar still poles the same line every night by a light that went out fifty years ago, which is why he never speaks and wears oilcloth to the eyes. A grey heron that fished at the tower swallowed the stray lens-glass; the Lens-Eyed Heron stands in the lamp-room where the keeper stood, and every wisp in the marsh is its dead lamplight. Levels 5 to 6, 40 to 50 minutes.

**Region:** `[{"id": "The Reedlight", "ring": 2, "levels": "5-6", "gear": "Uncommon - Rare", "blurb": "A marsh lighthouse with no lamp, and a heron that stands where the keeper stood.", "dealer": false}]`

**Attach** (`data/attach/rl.json`):
```json
{"bog_lights": {"exits": {"s": "rl_causeway"},
  "locks": {"s": {"element": ["fire", "light"], "remember": "rl_fog_burned", "msg": "South of the Bog Lights a wall of white fog stands on the water, thick enough to lean on. Fog burns off in light. Equip a Fire or Light spell book (type 'spells') and try again. Mirelle, in the Magician's Tower, sells Common books for gold."}}}}
```
`UNLOCK[("bog_lights", "s")]`: "You open the book and let the light out. The fog does not lift, it parts, as a curtain parts for someone it recognises."

### 7.1 Graph

| Room id | Name | Pos | Exits | Locks / specials |
|---|---|---|---|---|
| `rl_causeway` | The Causeway | 0,0 | n `bog_lights`, e `rl_sluice`, s `rl_cottage` | |
| `rl_sluice` | The Sluice Works | 1,0 | w `rl_causeway`, e `rl_tower_foot`, s `rl_oilhouse` | |
| `rl_tower_foot` | The Tower Foot | 2,0 | w `rl_sluice`, n `rl_lantern_room` | n: `{"item": "rl_tower_key", "msg": "The tower door is locked. The keeper kept his key where he kept the oil, in the oil-house south of the sluice, and the oil-house has guests."}` |
| `rl_lantern_room` | The Lamp Room | 2,-1 | s `rl_tower_foot` | `fixed` {flag `rl_heron_dead`, enemies [`rl_heron`]}, `boss` `rl_heron_dead`, `boss_name` "The Lens-Eyed Heron" |
| `rl_cottage` | The Keeper's Cottage | 0,1 | n `rl_causeway`, e `rl_oilhouse` | `waypost`; `wake` |
| `rl_oilhouse` | The Oil-House | 1,1 | n `rl_sluice`, w `rl_cottage` | `fixed` {flag `rl_oilhouse_dead`, enemies [`rl_lampman`,`rl_lampman`], intro "The keeper's drowned assistants look up from the barrels, lamp-hooks in their hands. They are still on shift."} |

### 7.2 Contents

| Room | desc seed | features | items | enc |
|---|---|---|---|---|
| `rl_causeway` | A line of posts, each with a lamp-hook, leads across the black water to a tower: the keeper's last mile. | `posts`: "Every hook is polished by years of someone's hand. Every lamp is gone." | | .35; [`wisp`]x2, [`rl_heronling`]x2, [`wisp`,`rl_heronling`]x1 |
| `rl_sluice` | Gears and a rusted wheel: the tide-gate that made the ferry channel. | `wheel`: "It turns a quarter-turn when the tide moves, as it was built to." | | .30; [`rl_lampman`]x2, [`rl_lampman`,`wisp`]x1 |
| `rl_tower_foot` | Two hundred steps spiral up a wall of white-washed stone, each with a chalk tally. | `tally`: "Ansel counted his own steps. The last tally is dated the night he came down for the Keeper." | | .25; [`rl_heronling`,`rl_lampman`]x1, [`rl_heronling`]x2 |
| `rl_lantern_room` | A room of glass, open to the sky. The great lens-cradle is empty, and the heron stands in it. | `cradle`: "Brass, bent at one corner where something heavy was lifted out in a hurry." | `rl_heronplume_coat`, `rl_keepers_pole` | none (fixed) |
| `rl_cottage` | A keeper's cottage, tidy, cold. A kettle on the stove. | `kettle`: "Two cups. One is clean. One has a ring of tea gone to stone." | `rl_receipt`, `strong_draught`, `honeycake` | none |
| `rl_oilhouse` | Barrels of whale oil, still sweet. | `barrels`: "Stamped REEDLIGHT. Not one has leaked in fifty years." | `oil` x2, `firepot` | none (fixed) |

`wake` (`rl_cottage`): "You wake on the keeper's cot with the kettle singing. Nobody is there. Your purse is lighter by %d gold. The second cup has been moved an inch toward you."

### 7.3 Enemies (`data/enemies/rl.json`; Saltmarsh x1.3)

| id | Name | tags | hp/atk/def/dodge | xp | gold | weak | resist | Moves | Drops |
|---|---|---|---|---|---|---|---|---|---|
| `rl_lampman` | Drowned Lampman | hollow, undead | 85/17/6/0 | 34 | 14-25 | earth, shadow | water, ice | Hook (attack 1.0 w3); Snuff (drain 0.7 drain 8 w2; "reaches for your lantern"); Soaked Embrace (heavy 1.8 w1; "opens his arms"; the lampman is he everywhere) | `hollow_dust` .4, `saltstone` .4, `essence_water` .3 |
| `rl_heronling` | Heronling | beast | 70/18/3/15 | 30 | 5-14 | earth, shadow | water | Jab (attack 1.0 w3); Gulp (attack 0.6 status bleed 3,3 w1); Screech (debuff blind 1 w1) | `saltstone` .3, `essence_water` .3 |
| `rl_heron` | The Lens-Eyed Heron | hollow, beast, boss | 340/23/6/10 | 190 | 110-140 | earth, shadow | water, ice | Spear Beak (attack 1.0 w3); Wing Slap (attack 0.7 w2); Gulp (heavy 2.2 w2; "draws back its head and opens its throat"); Lens Flare (debuff blind 2 w1; "turns its eye to the lantern"). **Phase 0.5**, msg "The lens in her eye catches your lantern and holds it, like a lighthouse seeing its first ship in fifty years.": same moves plus Beacon Stare (drain 1.0 drain 14 w2) | `essence_water` 1.0 x2, `essence_shadow` 1.0, `hollow_core` 1.0, `saltstone` 1.0 |

Calibration: Heron is Bishop x1.7 / x1.4 (target for a level-6 player in saltsteel gear: 88 to 95%). **As built:** the Heron is 340 / 23 (the stand-in's 20 ran easy once the phase's Beacon Stare was in), and the two ordinary mobs were raised to 85 / 17 and 70 / 18 (and their gold 14-25 and 5-14) in the integration pass so an ordinary group costs about a fifth of a player's health, not a tenth.

### 7.4 Hooks (`areas/rl.py`)

- `AFTER_FIXED["rl_oilhouse_dead"]`: narrate "The last lampman sets down his hook and sits on a barrel as if his shift were done. In his apron pocket, a key." `events.give_once(g, "rl_tower_key")`.
- `AFTER_FIXED["rl_heron_dead"]`: narrate "The heron lowers her head, and the lens slips from her eye into your palm, warm as a swallowed coal. She looks, for a long breath, at the ruined lamp-cradle. Then she turns and wades out into the marsh and stands there, grey on grey, like a woman at a window." `areas.give_first(g, "rl_lens_shard")`.
- `BOSS_TIPS["rl_lantern_room"]`: "She is weak to Earth and Shadow, not fire. Flares work (she is Hollow). Guard Gulp; Lens Flare blinds, so cleanse with Smelling Salts."
- `TOPICS["oskar"]`, shown when `rl_heron_dead` or the player holds `rl_receipt`: "Ask about the Reedlight". First time (sets `rl_oskar_spoke`): narrate "Oskar pushes back his sou'wester for the first time. He is not the face you imagined. He is a man who looks like someone who has been waiting at a window." Oskar: *"Ansel."* (a long pause) *"My brother. I pole the same line every night in case the light comes back. It's not for the boats. ...It's so I'll know where I am."* If the receipt is shown: *"Held in trust. He always did like a good receipt."* Later visits: *"The line is the same. I pole it anyway."*
- `RUMOURS` (after `rl_oskar_spoke`): "Oskar said his brother's name to a customer yesterday. The whole tavern went quiet." Shown the first time only after Oskar's own first talk; the receipt line fires once (`rl_oskar_receipt`).
- `OBJECTIVES` (all side): room `bog_lights`, "South of the Bog Lights a fog bank hides something. A Fire or Light book, equipped, would burn it off", when `reedways` visited and not `rl_fog_burned`; room `rl_oilhouse`, "The Reedlight: find the tower key in the oil-house", when `rl_fog_burned` and not `rl_oilhouse_dead`; room `rl_lantern_room`, "The Lens-Eyed Heron waits in the lamp room", when `rl_oilhouse_dead` and not `rl_heron_dead`.

### 7.5 Items (`data/items/rl.json`)

| id | kind | rarity | value | stats / mult | desc |
|---|---|---|---|---|---|
| `rl_heronplume_coat` | armor | rare | 135 | def 7, agi 2, dodge 5 | A coat of heron plumes sewn over oilskin. Water sheds off it, and so do blows. |
| `rl_keepers_pole` | weapon | rare | 140 | atk 11, agi 2; mult phys 1.1 | The keeper's long snuffing-pole, brass-tipped, balanced for climbing. |
| `rl_lens_shard` | trinket | rare | 150 | wil 3, hp 8; mult light 1.12 | A shard of the great lens. Held to the light it shows a lamp, lit, far away. |
| `rl_tower_key` | key | common | 0 | | A brass key on a loop of tarred twine. |
| `rl_receipt` | key | common | 0 | | (section 3.4) |

`rl_heronplume_coat` and `rl_keepers_pole` are **handed over by the `AFTER_FIXED["rl_heron_dead"]` hook** ("Under the plumes of her bed: a coat sewn from her own moulted feathers, and the keeper's snuffing pole"), not left on the floor: a fled fight leaves the player in the room, so a floor pile would be reachable early.

### 7.6 Tests (`tests/test_rl.py`)

Element lock with and without an equipped Fire/Light book, and `remember` after the book is swapped out; tower key given once; Oskar topic gating and first/second wording; call-back of the Heron does not re-lock anything; `rl_receipt` present on a fresh game and on a pre-package save; no hollow+light weakness; validator clean; fuzz reaches all 6 rooms.

---

## 8. Package `lw`: The Lampwrights' Deep (Underdeep extension)

**Story.** Under the tallow mines is the Guild's workshop, where the lamps for the whole north were made. **Corm Vaskel**, Brann's grandfather, was Master Lampwright; he and Aldric worked here on the thing meant to make a Keeper's sacrifice unnecessary, a rack of glass in which the lent lights would burn together. Corm lent his pit-lamp and copied his notes. The Foreman he built to mind the workshop is still minding it, and has started talking in Corm's voice. Levels 7 to 8, 50 to 60 minutes. This is where Brann learns what his grandfather did.

**Region:** `[{"id": "The Lampwrights' Deep", "ring": 3, "levels": "7-8", "gear": "Rare", "blurb": "The Guild's lamp workshops under the mines, and Corm's unfinished work.", "dealer": false}]`

**Attach** (`data/attach/lw.json`):
```json
{"crypt_stair": {"exits": {"s": "lw_door"},
  "locks": {"s": {"relic": "lamp", "remember": "lw_door_open", "msg": "In the crypt wall there is a bronze door with no handle and a ring of empty lens-seats where a lock should be. A Lamp Relic socketed into something you wear would fill the lenses. (Tallow sells Lamp Relics; Brann will socket one into Rare gear or better.)"}}}}
```
`UNLOCK[("crypt_stair", "s")]`: "The lens-seats take the light of your relic, one after another, and the bronze folds back like a flower."
(Reachable before the ending: Tallow's camp is two rooms past `crypt_stair`; `recall` and `return` make the round trip to Brann cheap.)

### 8.1 Graph

| Room id | Name | Pos | Exits | Locks / specials |
|---|---|---|---|---|
| `lw_door` | The Lamp-Lock | 0,0 | n `crypt_stair`, e `lw_mess`, s `lw_gallery` | |
| `lw_mess` | The Mess | 1,0 | w `lw_door`, e `lw_workshop`, s `lw_glassworks` | `waypost`; `wake` |
| `lw_workshop` | Corm's Workshop | 2,0 | w `lw_mess`, s `lw_rack_room` | `fixed` {flag `lw_foreman_dead`, enemies [`lw_foreman`], intro "The Foreman straightens from the bench. 'Mind the edge, lad,' he says, in a voice that is not his."}, `boss` `lw_foreman_dead`, `boss_name` "The Last Foreman"; s: `{"flag": "lw_foreman_dead", "remember": "lw_rack_open", "msg": "The rack-room door is shut with Corm's own bolts, and the Foreman wears the key on his apron. Defeat the Last Foreman in the workshop."}` |
| `lw_gallery` | The Lampwrights' Gallery | 0,1 | n `lw_door`, e `lw_glassworks` | |
| `lw_glassworks` | The Glassworks | 1,1 | n `lw_mess`, w `lw_gallery` | |
| `lw_rack_room` | The Rack Room | 2,1 | n `lw_workshop` | |

### 8.2 Contents

| Room | desc seed | features | items | enc |
|---|---|---|---|---|
| `lw_door` | A vaulted lock-room hung with the first lamps ever made, a welcome. | `welcome`: "Brass tags: GOOD LUCK. GOOD LIGHT. GO HOME TO YOUR SUPPER." | | .25; [`lw_glass_ghoul`]x1, [`lw_lampling`]x2 |
| `lw_mess` | Tin cups on a long bench, a kettle, a child's drawing pinned to a beam. | `drawing`: "A smith with a very large hammer. Under it, in a child's hand: DADA CORM'S BOY. It is Brann's father, aged six." | | none |
| `lw_workshop` | A bench with a half-built rack of glass, an apron on a nail, a stool pushed back as though he just stood. | `apron`: "Scorched at the hem. A man wiped his hands on it every working day for forty years." | | none (fixed) |
| `lw_gallery` | Finished lamps by the hundred, none lit. They watch you pass. | `lamps`: "Each has a maker's mark and a name tag. Not one has been collected." | `oil`, `lw_lamp_blank` x2 | .35; [`lw_lampling`]x2, [`lw_lampling`,`lw_glass_ghoul`]x1, [`tallow_ghoul`]x2 |
| `lw_glassworks` | The furnace is cold but the glass is still soft. | `furnace`: "Warm to the palm. Fifty years cold and still warm." | `slag` x2, `firepot` | .35; [`lw_glass_ghoul`]x2, [`lw_glass_ghoul`,`lw_lampling`]x1, [`crawler`]x1 |
| `lw_rack_room` | Six glass vials on a rack, labelled in two hands. Five are dark. | `rack|vials`: "Six vials, labelled in two hands: five say FROM THE LENDERS. The sixth says, in Aldric's script: this one is for you to give, not me to take." | `lw_receipt`, `lw_quench_notes`, `lw_lampwright_hammer`, `lw_apron`, `lw_pit_lamp`, `hollow_core`, `strong_draught` x2 | none |

`wake` (`lw_mess`): "You wake on a long bench under a coat that smells of lamp-oil and pipe smoke. Your purse is lighter by %d gold. Somebody has tucked a tin cup of cold tea beside your hand."

### 8.3 Enemies (`data/enemies/lw.json`; Underdeep x1.3)

| id | Name | tags | hp/atk/def/dodge | xp | gold | weak | resist | Moves | Drops |
|---|---|---|---|---|---|---|---|---|---|
| `lw_glass_ghoul` | Glass Ghoul | hollow, undead | 78/17/9/0 | 46 | 22-36 | ice, earth | fire | Shard Claw (attack 1.0 status bleed 3,4 w3); Molten Spit (attack 0.8 status burn 3,5 w2); Brittle Roar (debuff exposed 2 w1; "throws back its head") | `slag` .4, `essence_ice` .3 |
| `lw_lampling` | Lampling | construct | 60/18/5/18 | 42 | 14-29 | water, earth | fire, light | Swing (attack 1.0 w3); Gutter (drain 0.7 drain 8 w2); Flare Up (heavy 1.8 status burn 3,5 w1; "swells with light") | `slag` .5, `essence_fire` .3 |
| `lw_foreman` | The Last Foreman | construct, boss | 420/21/14/0 | 260 | 160-200 | water, ice | fire, earth | Hammer Blow (attack 1.0 w3); Tighten Up (defend w1); Spark Shower (attack 0.7 status burn 3,6 w2); Gather Heat (charge->Pour the Crucible w2; "is glowing white. POUR THE CRUCIBLE is coming") with `extra_moves` Pour the Crucible (heavy 3.0). **Phase 0.5**, msg "Corm's apron smoulders. The Foreman straightens, and speaks in a voice that is not his: 'Mind the edge, lad.'": same plus Careful Now (defend w1) | `slag` 1.0 x3, `hollow_core` 1.0, `essence_earth` 1.0 x2 |

Calibration: Foreman is the Ore-Warden x2.8 hp / x1.4 atk (level-7 player in saltsteel gear: 85 to 92%).

### 8.4 Hooks (`areas/lw.py`)

- `AFTER_FIXED["lw_foreman_dead"]`: narrate "The Foreman puts down his hammer, as carefully as a man putting down a child. 'Shift's over,' he says, in Corm's voice, and sits on the stool, and does not move again."
- `BOSS_TIPS["lw_workshop"]`: "Water and Ice hurt him, Fire does not. Guard Pour the Crucible: he charges first, so you have a turn to brace."
- `TOPICS["brann"]` (after `lw_foreman_dead`, not `lw_brann_told`): "Tell Brann about the Lampwrights' Deep" (sets `lw_brann_told`): narrate "Brann stops mid-swing. Then he puts the hammer down, which you have never seen him do." Brann: *"Corm. My grandfather. ...They told me he went down the mine and didn't come up. They didn't say he went down to make a lamp for the sun."* If `lw_receipt` is held he asks to see it, reads it, and is silent: *"Nothing anyone need pay for. ...He'd have said the same."* (The notes scene belongs to `late`, section 11.)
- `OBJECTIVES` (all side): room `crypt_stair`, "A bronze door with a ring of lenses is set in the wall of the Crypt Stair. A Lamp Relic, socketed into worn gear, would open it", when `mine_hall` visited and `lw_mess` not visited; room `lw_workshop`, "Corm's Workshop: the Last Foreman keeps the rack-room key", when `lw_mess` visited and not `lw_foreman_dead`.

### 8.5 Items (`data/items/lw.json`)

| id | kind | rarity | value | stats / mult | desc |
|---|---|---|---|---|---|
| `lw_lampwright_hammer` | weapon | rare | 145 | atk 11, str 2 | A lampwright's peening hammer, worn to the shape of a hand. |
| `lw_apron` | armor | rare | 140 | def 8, hp 8 | A smith's leather apron, scorched and mended and scorched again. |
| `lw_pit_lamp` | trinket | rare | 150 | wil 2, oil_save 2; mult fire 1.1 | Corm's own pit-lamp, lent and never missed. Its flame was never lit; it just does not go out. |
| `lw_lamp_blank` | junk | common | 30 | stack | An unfinished lamp, glass and brass, waiting for a wick. |
| `lw_receipt` | key | common | 0 | | (section 3.4) |
| `lw_quench_notes` | key | common | 0 | | (section 3.4) |

### 8.6 Tests (`tests/test_lw.py`)

Relic lock: shut with no relic; shut with a relic that is in the pack but not socketed; shut with an Ember relic socketed; open with a Lamp relic socketed into worn armour, weapon and trinket in turn (3 cases); before the first pass it is a live check (assert the message and the `Worn relics:` status line); after the first pass `lw_door_open` keeps it open; rack room shut until the Foreman dies and stays open after a call-back; Foreman charge and extra move wired; Brann topic gating; receipt and notes present on a pre-package save; validator clean; fuzz reaches all 6 rooms.

---

## 9. Package `ff`: The Frostfair (ring 5, area A)

**Concept.** Wintering held a Midwinter *Lending Fair*: every household hung its lamp on the Fair's poles, the **Great Lantern** lit them all at dusk, and at dawn each family took its lamp home lit. Aldric borrowed the Great Lantern's flame "for a winter". Lamp-Master **Hobb Ardent** swore on his own flame to hold the Fair until it came home. He held it for fifty years. The town froze into the Fair, mid-sale, mid-skate, mid-sentence. The wrongness here is **waiting**: nothing is evil, everything is *held*. Cold is the symptom, not the cause, and the player's tool is warmth: relight three Lending Posts and the gate to the Great Lantern opens. Warm and melancholy: **Dunmore** (still selling tickets), **Marit** (the Fairwarden, Hobb's wife, who kept one small lamp lit in a booth for fifty years because someone had to be there when he came back), and Hobb.

**Lane.** Fire and Earth carry (Ashblade's and Warden's home); Shadow is neutral; **Ice and Water are resisted by every hollow in the roster**. Light is not a weakness anywhere (rule, section 2.3) because Radiance and flares already double on Hollows. Two fields tax the lane (Black Ice, Midwinter), so a Fire-only loadout is a worse tool in the pond and at the boss.

**Regions** (`data/regions/ff.json`):
```json
[{"id": "The Frostfair", "ring": 5, "levels": "10-11", "gear": "Ultra - Legendary",
  "blurb": "A midwinter fair on the road west of the North Gate, held in a breath that never let go.",
  "dealer": true, "dealer_after": "beacon_Ember Court"},
 {"id": "The Fair Below", "ring": 5, "levels": "11-12", "gear": "Legendary",
  "blurb": "The Fair's undercroft, where the unsold stock was laid for the winter. Nothing ever lights it.",
  "dealer": false}]
```

**Attach** (`data/attach/ff.json`):
```json
{"gate": {"exits": {"w": "ff_frost_road"},
   "locks": {"w": {"flag": "beacon_Ember Court", "msg": "A road of white frost runs west from the gate and ends at a wall of hard-packed snow that Hesk says has grown a hand's breadth a day for a week. It will not be dug. It is waiting for an answer: relight the Ember Court's beacon in its throne room, and something out there will answer."}}},
 "hearth_stall": {"exits": {"e": "ff_stall"},
   "locks": {"e": {"building": "ff_fair_stall", "msg": "A vacant plot beyond the Hearth Stall, strung with paper lanterns nobody has lit. Joss can build a stall here once the Fairwarden, Marit Ostrand, has agreed to move in."}}}}
```

### 9.1 Map

The Fair lies **west** of the North Gate (`gate` w), so the map runs right to left:

```
                                             booth
                                             |
signal_stair - wintering    - great_gate   - lamp_row#    - midway#      - fair_gate    - frost_road - [gate]
                              |              |              |              |
                              sculptors#   - carousel     - skate_pond   - tent
                                                            |
                                                            cellars  --d--> annex: below_stair - below_hall - (s) below_pool
```
`#` = a Lending Post (waypost). Hollowmere: `hearth_stall` (4,0) e to `ff_stall` (5,0).

### 9.2 Graph

| Room id | Name | Region | Pos | Exits | Locks / specials |
|---|---|---|---|---|---|
| `ff_frost_road` | The Frost Road | Frostfair | 0,0 | e `gate`, w `ff_fair_gate` | |
| `ff_fair_gate` | The Fair Gate | Frostfair | -1,0 | e `ff_frost_road`, w `ff_midway`, s `ff_lending_tent` | `rest`, `outpost`, `wake`; NPC `ff_dunmore` |
| `ff_lending_tent` | The Lending Tent | Frostfair | -1,1 | n `ff_fair_gate`, w `ff_skate_pond` | |
| `ff_midway` | The Midway | Frostfair | -2,0 | e `ff_fair_gate`, w `ff_lamp_row`, s `ff_skate_pond` | `waypost` (the Cider Post) |
| `ff_skate_pond` | The Skating Pond | Frostfair | -2,1 | n `ff_midway`, e `ff_lending_tent`, w `ff_carousel`, s `ff_ice_cellars` | s: `{"all": [{"item": "ff_cellar_key"}, {"dread": {"max": 24}}], "msg": "A trapdoor of black ice, locked, set in the bank of the pond. It wants two things: the Fair's cellar-key, which hangs round the neck of the Fairwarden in the Warden's Booth north of Lantern Row, and a steady heart. The sleepers below stir if yours is racing: come with Dread under 25 (Steady). Rest at the toll-booth, or drink cider, a Fairlight or a honeycake first."}`; field Black Ice |
| `ff_ice_cellars` | The Ice Cellars | Frostfair | -2,2 | n `ff_skate_pond`, d `ff_below_stair` | d: `{"flag": "beacon_The Frostfair", "msg": "The hatch beneath the oil casks is frozen shut. It will give when the Fair thaws: light the Great Lantern in the Wintering Square and come back."}` |
| `ff_lamp_row` | Lantern Row | Frostfair | -3,0 | e `ff_midway`, w `ff_great_gate`, s `ff_carousel`, n `ff_wardens_booth` | n: `{"item": "ff_wardens_key", "msg": "The Warden's Booth door is padlocked from outside with a brass padlock stamped FAIRWARDEN. The Ringmaster of Rime wears the key on his watch-chain. Defeat him in the carousel."}`; `waypost` (the Row Post) |
| `ff_wardens_booth` | The Warden's Booth | Frostfair | -3,-1 | s `ff_lamp_row` | NPC `ff_marit` |
| `ff_carousel` | The Carousel | Frostfair | -3,1 | n `ff_lamp_row`, e `ff_skate_pond`, w `ff_sculptors_row` | `fixed` {flag `ff_ringmaster_dead`, enemies [`ff_ringmaster`], intro "The music box under the carousel starts to play. A man in a ringmaster's coat tips his hat. 'Admission,' he says, 'is one story or one coin.'"}, `boss` `ff_ringmaster_dead`, `boss_name` "The Ringmaster of Rime" |
| `ff_sculptors_row` | Sculptors' Row | Frostfair | -4,1 | e `ff_carousel`, n `ff_great_gate` | `waypost` (the Sculptors' Post) |
| `ff_great_gate` | The Lych-Gate of Lamps | Frostfair | -4,0 | e `ff_lamp_row`, s `ff_sculptors_row`, w `ff_wintering` | w: `{"flags": ["lit_ff_midway", "lit_ff_lamp_row", "lit_ff_sculptors_row"], "msg": "The Great Lantern's gate is a lych-gate hung with lamps, and every one is dark. It opens when the Fair has been lent light again: relight all three Lending Posts, the Cider Post on the Midway, the Row Post on Lantern Row and the Sculptors' Post (type 'light' at each; 10 oil apiece)."}` |
| `ff_wintering` | The Wintering Square | Frostfair | -5,0 | e `ff_great_gate`, w `ff_signal_stair` | `boss` `ff_lampmaster_dead`, `boss_name` "Lamp-Master Hobb", `beacon`, `beacon_oil` 30; field Midwinter; boss via ENTER |
| `ff_signal_stair` | The Signal Stair | Frostfair | -6,0 | e `ff_wintering` | `no_dealer` (only reachable through the boss room); the `u` exit to `vg_ladder` and its lock are added by `vg`'s attach (section 10) |
| `ff_stall` | The Fairwarden's Stall | Hollowmere | 5,0 | w `hearth_stall` | building room, `dark` false |
| `ff_below_stair` | The Cellar Stair | Fair Below | 0,0 | u `ff_ice_cellars`, w `ff_below_hall` | `waypost` |
| `ff_below_hall` | The Unsold Stock | Fair Below | -1,0 | e `ff_below_stair`, s `ff_below_pool` | |
| `ff_below_pool` | The Cold Pool | Fair Below | -1,1 | n `ff_below_hall` | |

The vault is `ff_ice_cellars`. Bypass check (verified on the graph): `ff_wardens_booth` and `ff_ice_cellars` have exactly one entrance each, both locked; `ff_wintering` only via `ff_great_gate` w; `ff_signal_stair` only via `ff_wintering`.

### 9.3 Contents

| Room | desc seed | features | items | enc (chance; groups) |
|---|---|---|---|---|
| `ff_frost_road` | Cart tracks frozen in rime, a hand-lantern hung on every post. Not one is lit. | `tracks`: "A hundred carts, all arriving." `lanterns`: "Each is tagged with a family's name, in a child's careful hand." | | .30; [`ff_hawker`]x3, [`ff_hawker`,`ff_hawker`]x1, [`ff_skater`]x2 |
| `ff_fair_gate` | A toll-booth with a stove fed on the booth's own furniture: the only warm place for miles. | `stove`: "Fed with a chair, a table, and a bookcase. The bookcase is nearly gone." `book|ledger`: "ADMIT ONE, ADMIT ONE, ADMIT ONE, in the same cheerful hand, for fifty years." | | none |
| `ff_lending_tent` | A long trestle where families signed in their lamps. | `book`: "The book of lenders. The last name in it is a Keeper's, in a nervous hand. Under it, in a steady one: Marit Ostrand, witness." | `ff_receipt`, `honeycake`, `oil` | .20; [`ff_hawker`]x3, [`ff_lamp`,`ff_hawker`]x1 |
| `ff_midway` | Stalls frozen mid-sale, a coconut-shy of ice. Every hawker has their mouth open on a word. | `hawkers`: "One is holding out a candied apple. The apple is real." `post`: "The Cider Post: a lamp-post with a little brass door." | `ff_fair_token`, `strong_draught` | .35; [`ff_hawker`,`ff_skater`]x3, [`ff_hawker`]x3, [`ff_lamp`]x2 |
| `ff_skate_pond` | A round pond of black ice. Skaters turn under it, still in step. | `skaters`: "Beneath the surface they are waltzing. They look up at you and smile; their breath doesn't fog." | `ff_fair_token` | .35; [`ff_skater`]x2, [`ff_skater`,`ff_skater`]x2, [`ff_ice_figure`]x1 |
| `ff_ice_cellars` | Where the Fair stored its oil for the Lending. Casks to the ceiling, frost on every hoop. | `casks`: "Stamped with the Lamp-Master's mark. The oil inside is sweet as the day it was pressed." | `ff_greatcoat`, `hollow_core` x2, `ff_rime` x4, `strong_draught` x2, `ff_fair_token` x3, `relic_pulse`, `core_heart_ice`, `core_heart_earth` | .25; [`ff_ice_figure`]x2, [`ff_ice_figure`,`ff_hawker`]x1, [`ff_lamp`,`ff_lamp`]x1 |
| `ff_lamp_row` | Six hundred empty lamps hung on poles, each tagged with a family's name. They flicker when you pass. | `lamps`: "The one nearest you is tagged with your own surname. That's impossible. You check anyway." `post`: "The Row Post." | | .40; [`ff_lamp`]x3, [`ff_lamp`,`ff_lamp`]x2, [`ff_lamp`,`ff_ice_figure`]x1, [`ff_lamp`,`ff_skater`]x1 |
| `ff_wardens_booth` | A stove, a cot, a kettle, a hand-lamp the size of a thumb, and fifty years of tally-marks on the wall. | `tally`: "Five bars and a slash, five bars and a slash, to the ceiling. The last has today's date." `lamp`: "No bigger than a thimble. Burning." | | none |
| `ff_carousel` | The carousel still turns, slowly, to a music box playing one verse. The horses are not wood. | `music`: "One verse, over and over. The last note is a kind one that never arrives." | | none (fixed) |
| `ff_sculptors_row` | Ice figures of every family, carved for the Fair: the best likenesses the Fair ever had. | `figures`: "Each is posed as if about to say something. You recognise none, and all of them." `post`: "The Sculptors' Post." | | .40; [`ff_ice_figure`]x3, [`ff_ice_figure`,`ff_ice_figure`]x1, [`ff_ice_figure`,`ff_horse`]x1, [`ff_ice_figure`,`ff_lamp`]x1 |
| `ff_great_gate` | A lych-gate hung with lamps, where the families lined up to lend. | `gate|lamps`: "Every lamp is dark. They lean a little toward your lantern." | | .30; [`ff_horse`]x3, [`ff_ice_figure`,`ff_lamp`]x2, [`ff_horse`,`ff_skater`]x1 |
| `ff_wintering` | The square opens like an indrawn breath. In its centre a lamp-post as tall as a church, and a lantern the size of a cottage, dead. | `lantern`: "The Great Lantern. Its base is a bowl, empty and cold." `bowl|beacon`: "The beacon is the Lantern's base-bowl. When Hobb is gone, light it (type 'light')." | | none (boss) |
| `ff_signal_stair` | A stair cut into the ridge. At its foot a half-size signal brazier waits for the Fair's answer. | `brazier`: "A little brother of the Great Lantern's bowl. Cold." | | .25; [`ff_horse`]x1, [`ff_skater`,`ff_lamp`]x1 |
| `ff_stall` | A trestle stall under a canvas awning painted with a lantern, paper lanterns strung along it. | `awning`: "Painted by someone with a steady hand." | | none |
| `ff_below_stair` | Steps down into a long cold room, the Fair's undercroft. | `casks`: "Smaller casks than upstairs. These were kept for the dead of winter." | | .40; [`ff_hawker`]x2, [`ff_skater`]x2, [`ff_ice_figure`]x1 |
| `ff_below_hall` | Rows of unsold stock under dust-sheets: lanterns, ribbons, carved horses. | `stock`: "Never opened. Every ribbon still smells of the shop." | `ff_fair_token` x2, `strong_draught` | .45; [`ff_hawker`,`ff_skater`]x2, [`ff_below_sleeper`]x2, [`ff_ice_figure`]x1 |
| `ff_below_pool` | A pool of still black water, frozen only on top. | `pool`: "Things lie under the ice, laid out neatly, as if put away for the winter." | | .45; [`ff_below_sleeper`]x2, [`ff_ice_figure`,`ff_lamp`]x2, [`ff_horse`]x1 |

`wake` (`ff_fair_gate`): "You wake on a cot by the toll-booth stove. Dunmore is warming his hands over it. 'Third night of the Fair,' he says kindly. 'You fell over. It happens.' Your purse is lighter by %d gold."
`waypost_text` (all three posts): "You open the little brass door and touch your flame to a wick that has waited fifty years. It catches. Nearby, a frozen mouth finishes its word, very quietly, and the word is: warm."
`beacon_text` (`ff_wintering`): "You pour your oil into the base of the Great Lantern and touch your flame to it. For a moment nothing happens."
Fields: `ff_skate_pond` `{"name": "Black Ice", "fire": 0.75, "earth": 1.25, "msg": "The ice drinks heat and cracks under stone: fire is weaker here, earth stronger."}`; `ff_wintering` `{"name": "Midwinter", "fire": 0.8, "light": 0.85, "msg": "The dead Lantern drinks flame: fire and flares burn lower in this square."}`.
`no_dealer`: `ff_signal_stair` (it can only be reached through the boss room, and `dealer._behind_a_lock` cannot see that because the room has a return exit from its own neighbour). Seats then are `ff_frost_road`, `ff_lending_tent`, `ff_skate_pond`, `ff_great_gate` = **4** (the rest are waypost, outpost, fixed, boss, or entered only through a locked exit: the booth and the cellars). Note `_behind_a_lock` only excludes a room when EVERY exit leading into it is locked, counting the neighbour's own exit back into it; that is why dead-end rooms beyond a door need `no_dealer` when they have a way back out.

### 9.4 Enemies (`data/enemies/ff.json`; ordinary mobs = Court x1.3 hp and atk)

*Integration pass (2026-11-03): the gold columns of the ordinary mobs below and of the Vigil's are the values after the economy retune of `sim_economy.py --check` (the first-draft ranges ran 12 to 35 percent under the section 16.1 bands); the Sleeper Below and the Cellar Dead carry the annexes' extra gold. The boss and mini-boss hp / atk marked **built** are the values after the sim_ring5 retune, all inside the +-30% of section 14.1.*

| id | Name | tags | hp/atk/def/dodge | xp | gold | weak | resist | Moves | Drops |
|---|---|---|---|---|---|---|---|---|---|
| `ff_hawker` | Frostbound Hawker | hollow, undead | 300/47/6/0 | 125 | 44-68 | fire, earth | ice, water | Sales Pitch (attack 1.0 w3; "leans in, selling something nobody wants"); Haggle (debuff exposed 2 w1; "names a price"); Last Bargain (heavy 2.0 w2; "slams the counter") | `ff_rime` .45, `ff_fair_token` .35, `essence_ice` .25, `core_heart_ice` .04 |
| `ff_skater` | Phantom Skater | hollow | 235/47/5/28 | 135 | 48-75 | shadow, earth | ice, water | Blade Pass (attack 0.6 hits 2 w3); Figure Eight (attack 0.9 status bleed 3,6 w2); Double Axel (heavy 2.0 w1; "pushes off hard") | `ff_rime` .4, `essence_water` .3, `ff_fair_token` .3, `core_heart_water` .04 |
| `ff_horse` | Carousel Horse | construct | 550/57/13/0 | 160 | 51-85 | fire, shadow | ice, earth | Gallop (attack 1.0 w3); Round and Round (attack 0.5 hits 3 w2); Brass Pole (heavy 2.0 w1; "lowers its brass pole"); Music Box Gutter (defend w1) | `ff_rime` .5, `essence_shadow` .3, `ff_fair_token` .3, `core_heart_earth` .05 |
| `ff_ice_figure` | Ice Figure | hollow | 390/47/17/0 | 145 | 48-71 | fire, shadow | ice, water | Brittle Embrace (attack 1.0 status weak 2,0 w3); Hold the Pose (defend w2); Shatter (heavy 2.2 w1; "cracks run across it; it is about to come apart and take you with it") | `ff_rime` .55, `essence_ice` .3, `core_heart_ice` .04 |
| `ff_lamp` | Hung Lamp | hollow | 200/46/3/25 | 130 | 42-68 | water, earth | fire, light | Gutter (drain 0.8 drain 12 w3); Dim (debuff blind 2 w2); Swing (attack 1.0 w2) | `ff_rime` .35, `essence_fire` .35, `ff_fair_token` .3, `core_heart_fire` .04 |
| `ff_below_sleeper` | Sleeper Below | hollow, undead | 520/52/14/0 | 150 | 144-216 | fire, earth | ice, water | Dream Strike (attack 1.0 w3); Cold Sleep (heavy 2.1 w2; "sighs, and the air gets heavier"); Lullaby (drain 0.7 drain 12 w1) | `ff_rime` .6, `core_heart_ice` .08, `core_heart_water` .06, `core_heart_earth` .06 |
| `ff_ringmaster` | The Ringmaster of Rime | hollow, undead, elite | 720/51/14/5 (**built 640/46**) | 480 | 130-170 | fire, shadow | ice, water | Whip Crack (attack 1.0 w3); Roll Up! (summon `ff_skater`, only_if can_summon, w1; "tips his hat and the carousel answers"); Grand Finale (heavy 2.3 w2; "takes a bow"); Spotlight (debuff exposed 2 w1). **Phase 0.5**, msg "The music box under the carousel starts to play, and the horses begin, slowly, to go around.": same plus Merry-Go-Round (attack 0.5 hits 4 w3) | `hollow_core` 1.0 x2, `ff_rime` 1.0 x3, `essence_light` 1.0, `core_heart_light` 1.0 (booth key by hook) |
| `ff_lampmaster` | Lamp-Master Hobb | hollow, boss | **1115/67/14/0** at power 50 (Queen x1.45; **built 1200/57**) | 1500 | 600-750 | fire, earth | ice, water | below | below |

**Hobb's moves.** Lamp-Pole Sweep (attack 1.0 w3); Hoarfrost Breath (attack 0.7 status weak 2,0 w2); Lend Me Yours (drain 1.0 drain 14 w2; "holds out a hand for your flame"); Hang the Lamps (summon `ff_lamp`, only_if can_summon, w1; "claps, and the poles above him light with faces"); Midwinter Toll (heavy 2.3 w2; "lifts the Lantern; the frost on the walls begins to ring").
- **Phase 0.66**, msg "Hobb lifts the dead Great Lantern. Six hundred empty lamps flicker on their poles, and every one of them has a face in it.": Sweep 1.1 w3, Hoarfrost Breath w2, Lend Me Yours drain 16 w2, Whiteout (debuff blind 2 w1), Midwinter Toll 2.4 w2, Hang the Lamps w1.
- **Phase 0.33**, msg "The Lamp-Master sees your lantern properly, for the first time. 'Did he send you? Is it spring?' ... 'Then hold the Fair. HOLD IT.'": Hold the Fair (buff status enraged 2,0 w1), Frozen Hour (heavy 2.7 w2; "stands perfectly still, and the cold stands with him"), Lend Me Yours drain 18 w2, Sweep 1.2 w2.

**Hobb's `roll`:** `{"story": false, "pron": {"subj": "he", "obj": "him", "poss": "his"}, "place": "The Fair", "flavour": [...5...], "bonus": [{"item": "ff_wintering_flame", "from": 10, "to": 60}, {"item": "hollow_core", "from": 1, "to": 100, "count": 3}, {"item": "ff_rime", "from": 1, "to": 100, "count": 3}, {"item": "essence_fire", "from": 20, "to": 100, "count": 2}]}`. Flavour, one per band (Faltering to Ablaze):
1. "He stands very still, one hand on the cold post. The lamps hang quiet. He looks, for once, tired."
2. "He moves like a man who has held a tray for fifty years and is thinking of putting it down."
3. "He stands exactly as the Fair remembers him: the coat of lamps, the long pole, the patient smile."
4. "Every dark lamp in the square has begun to glow, a faint and hungry blue, and the frost on your sleeve crackles."
5. "The Great Lantern in his arms blazes white with borrowed cold. The whole Fair is holding its breath behind him."

Base drops (every win): `hollow_core` x2, `ff_rime` x3, `essence_light` x2, `core_heart_ice`, `core_heart_fire`, `core_heart_light` (all 1.0).

### 9.5 Hooks (`areas/ff.py`)

- `AFTER_BEACON["Ember Court"]`: set `ff_signal_seen`; narrate "Far to the west, across the dark, a second light answers the Court's. It is blue-white and cold, and it is not a beacon. It is a lantern held up very high by someone who has been waiting a long time to see another one." then grey "(Hesk will want to know about the frost at the North Gate.)"
- `ENTER["ff_frost_road"]` (first visit, return False): "The air stops being air. It is the stillness of a held breath. A hand-lantern hangs on every post, each tagged with a family's name. Not one is lit."
- `ENTER["ff_great_gate"]` (first visit when the three post flags are set, return False): "The lamps on the gate do not light. They lean toward your lantern, and for one moment each of them holds a small, steady, borrowed gold."
- `AFTER_FIXED["ff_ringmaster_dead"]`: narrate "The Ringmaster takes off his hat. 'And that,' he says, 'is the show.' The carousel coasts to a stop for the first time in fifty years. In the silence you can hear the music box wind down to its last note, and the last note is a kind one." `events.give_once(g, "ff_wardens_key")`; once (`ff_gems_ringmaster`) +2 gems.
- `ENTER["ff_wintering"]`: if `ff_lampmaster_dead` return False; else `powerroll.boss_scene(g, "ff_lampmaster", "ff_lampmaster_dead", "ff_great_gate", _won, intro="Somewhere, a music box begins.", prologue=...)`. First-time prologue (`ff_met_hobb`): narrate "The square opens like an indrawn breath. At its centre stands a lamp-post as tall as a church, and at the foot of it a man in a coat made of hung lamps, with a long pole across his shoulders, holding the Great Lantern in his arms like a child." Hobb: *"Admission is one story or one coin. Which is it, friend? The Fair is open until spring."* Later prologue: narrate "Hobb sets his lamp-pole across his shoulders." Hobb: *"Still open, friend. Still open."*
- `_won(g, power)`: narrate "Hobb sets the Great Lantern down, very gently, the way you set down something that is finally allowed to sleep. 'Is it spring?' he asks. And he looks at you, and it is Hobb for one breath, and it is the kindest face in the world. 'Oh. Tell Marit I held it. Tell her I held it as long as I could.' He is frost on the cobbles, and then he is not even that. The Great Lantern stands in the square, empty and clear as glass. The beacon bowl is cold." Band gems `{3: 1, 4: 2}` **once** (flag `ff_gems_band`). Grey "(Type light to relight it.)" The first-kill 3 gems come from the `boss` tag.
- `AFTER_BEACON["The Frostfair"]`: set `ff_thaw`; narrate "Then, one by one, the six hundred lamps on Lantern Row ignite. Not with ghost-fire: with plain yellow flame, each its own small colour. All over the Fair, frozen hawkers and skaters and sculptors set down what they are holding and begin, slowly and with great dignity, to walk home. The frost on the stones turns to dew. You hear someone laugh. It is spring." then "In Hollowmere, three streets from the gate, the ice on Maeve's pump cracks and runs."
- `BOSS_TIPS["ff_wintering"]`: "You see his strength before you decide, and you can step back or run for free. Fire and Earth are strong, Ice and Water useless, and the Midwinter field dims fire and flares. Kill the Hung Lamps he calls (they steal oil) and guard Midwinter Toll and Frozen Hour. Keep 40 or more oil: Lend Me Yours drains it."
- `BOSS_TIPS["ff_carousel"]`: "Fire and Shadow hurt him. Kill the skaters he calls first. He is an elite: no running."
- `OBJECTIVES`: main chain (emitted only while `beacon_Ember Court` is set and `beacon_The Frostfair` is not): not `ff_frost_road` visited: room `ff_frost_road`, "A cold light answered the Court's beacon, west of the North Gate. Open the frost road"; else if posts lit < 3: room = the first unlit of `ff_midway`, `ff_lamp_row`, `ff_sculptors_row`, "Relight the Lending Posts (n of 3): the Midway, Lantern Row, Sculptors' Row"; else if not `ff_lampmaster_dead`: room `ff_wintering`, "Face the Lamp-Master Hobb in the Wintering Square"; else room `ff_wintering`, "Light the Great Lantern". Side: room `ff_carousel`, "The Ringmaster of Rime wears the Warden's Booth key in the carousel" (when `ff_fair_gate` visited, not `ff_ringmaster_dead`); room `ff_wardens_booth`, "Marit Ostrand in the Warden's Booth would move to Hollowmere. Ask her, then see Joss" (when `ff_lampmaster_dead`, stall not built); room `ff_skate_pond`, "The Ice Cellars: Marit gave you a key, and the sleepers want you calm" (when `ff_cellar_key` held and cellars not visited).

**Hollowmere reactions** (all in `ff.py`):
- `TOPICS["hesk"]`, when `ff_signal_seen`, not yet `ff_hesk_told`: "Ask about the frost on the gate" (sets `ff_hesk_told`): *"A hand's breadth a day. It's not winter, it's wanting. Whatever's out there, it's looking at us. I can feel it looking at the back of my neck."* After `ff_thaw` the same topic reads: *"The snow's gone. There's a smell of woodsmoke where the drift was. I almost cried at my own gate."* `EXTRA_NEWS["hesk"]`: `ff_signal_seen and not ff_hesk_told`.
- `RUMOURS`: `ff_signal_seen` and not `ff_thaw`: "The pump froze solid last night. In October. Then it cracked, and it ran hot for an hour."; after `ff_thaw` and `ff_fair_stall` not built: "Somebody's been hanging paper lanterns on the Hearth Stall. I don't know who. I like it."
- `SELLS["odo"]`: `["ff_rime"]` once `ff_lampmaster_dead`; `PRICES["ff_rime"] = 70`.

### 9.6 NPCs

**Dunmore Pike** (`ff_dunmore`, `NPCS` desc: "A round man in a toll-keeper's coat, cheerful, a little glassy-eyed, writing in a book that is mostly the same line."). In `fair_gate`. Shop `STOCK`: `oil`, `strong_draught`, `honeycake`, `ff_cider`, `ff_fairlight`, `firepot`, `smokebomb`, `tonic`. Convinced it is the third night of the Fair. Admission is "one coin or one story"; he accepts either and writes it in a book. Opening: *"Two coins, or one story. Mind the pond, the skaters are very good, and very cold."* Topics (`topic_menu`):
- "Ask about the Fair": the Lending (every family hangs its lamp; the Lamp-Master lights them at dusk; "this year the Great Lantern's gone on a little holiday, but he'll be back by spring").
- "Ask what is still going on": *"There were three Lending Posts, where folk hung their lamps for the Lantern to light from. The Cider Post, the Row Post, and the Sculptors'. I don't go that far. My knees."* (This is the in-world statement of the gate's requirement.)
- "Ask about the Warden's Booth": *"Someone's keeping a stove lit up there, I'd swear to it. Nobody lights a stove in fifty years by accident."*
- After `ff_thaw`: *"Closing time, is it? ...Well. I'll sweep up."* He stays: *"Someone has to be here to say it's over. I think I'll keep the booth. It's a good booth."*

**Marit Ostrand** (`ff_marit`, about 82, sharp, dry, brave; `NPCS` desc: "A small, upright old woman with a boat-hook held like a pike and a hand-lamp the size of a thimble on a cord round her neck."). `NPCS["ff_marit"]["where"]` returns `ff_stall` when `ff_fair_stall` is built; `PRESENT["ff_marit"]` returns `not town.is_built(g, "ff_fair_stall")`; she is listed in `ff_wardens_booth`'s `npcs`. `NEWS["ff_marit"]`: not yet met, or `ff_lampmaster_dead` and not invited/built, or `ff_thaw` and `ff_flame_given` unset.
- First talk (`ff_marit_met`): narrate "Behind a cold stove, an old woman rises with a boat-hook held like a pike. 'Hobb?' she says, and then, seeing you: 'No. No, of course not. He'd have knocked.'" She gives `ff_cellar_key` (`give_once`): *"The cellars have the Fair's oil. It's been fifty years; it'll be sweet as the day. Take what you need and leave the barrels square."*
- "Tell her what happened to Aldric" (until `ff_marit_told`): a two-way menu. **"The truth"**: *"Dead. Or what was left of him, and then not even that."* She: *"Then he never came back for the lantern because he couldn't. ...Fifty years I've been angry at a man for being rude, and he was only gone."* **"That he is still walking"** (the kind lie): *"Good. Let him walk. It's the only thing he was ever good at."* Both set `ff_marit_told`.
- "Ask about Hobb": *"My husband. He couldn't put a thing down once he'd picked it up. It's the best thing about him and it's what did for him."*
- "Ask about the Great Lantern": it burned the lamps of six hundred households; she wrote their names.
- After `ff_lampmaster_dead`, until `ff_marit_hobb`: "Tell her Hobb held it": narrate "She walks out into the square, puts her palm flat on the cold base of the Great Lantern, and says, quietly, 'You can go home, love.' Her hand glows."
- After `ff_thaw`, until `ff_flame_given` (offered automatically at the start of her next talk): narrate "She opens her tiny hand-lamp's shutter, touches your lantern's wick, and the flame that climbs onto it is smaller and warmer than yours." Marit: *"That's not a loan. Write it down, if you must. I'm told it matters."* `events.give_once(g, "ff_given_flame")`, set `ff_flame_given`.
- "Ask her to come to Hollowmere" (after `ff_lampmaster_dead`): `npcs._invite_scene(g, "ff_fair_stall", "Marit", "A market? With stalls? ...Hobb would have loved a market. Tell your builder I'll want a counter I can lean on.", "", "Tell Joss, in the yard on Market Row. I'll want a counter I can lean on.")`.
- When the stall is built: "Trade" (shop `STOCK["ff_marit"]`: `ff_fairlight`, `ff_cider`, `oil`, `essence_ice`, `essence_light`, `honeycake`) and the **market-day gift**: once per real day (flag `ff_gift_day` = `dealer.today()`) she hands over a free `ff_fairlight`: *"Day's candle. Don't tell me you don't need it. Everyone needs it."*

### 9.7 Building and Hollowmere room

`data/buildings/ff.json`: `{"ff_fair_stall": {"name": "Fairwarden's Stall", "room": "ff_stall", "resident": "ff_marit", "cost": {"gold": 1200, "items": {"ff_rime": 8, "cinder": 6}}, "minutes": 40, "steps": 60, "rent": 14, "blurb": "Marit sells fair-lights and cider, and hands you a free candle every day."}}`. Room `ff_stall`: region `Hollowmere`, pos [5,0], `dark` false, exits `{"w": "hearth_stall"}`.

### 9.8 Items (`data/items/ff.json`)

| id | kind | rarity | value | stats / use / mult | desc |
|---|---|---|---|---|---|
| `ff_rime` | material | uncommon | 18 | stack | Fair Rime: white crust from the Frostfair, harder than salt. The Builder and the forge use it. |
| `ff_fair_token` | junk | common | 60 | stack | A brass token stamped ADMIT ONE. Sells well to collectors. |
| `ff_cider` | consumable | common | 40 | use heal 80, regen 4, dread -20 | Hot cider with a clove stuck in every cup. |
| `ff_fairlight` | consumable | common | 55 | use oil 30, dread -40, heal 20 | A fair-candle in a paper lantern. It remembers every festival. |
| `ff_wardens_key` | key | common | 0 | | A brass key stamped FAIRWARDEN. |
| `ff_cellar_key` | key | common | 0 | | A key on a string that has been round a neck for fifty years. |
| `ff_receipt` | key | common | 0 | | (section 3.4) |
| `ff_given_flame` | key | common | 0 | | A coal the size of a thumbnail in a glass no bigger. It is warm in a way the lantern is not. It was given. |
| `ff_wintering_flame` | trinket | ultra | 1500 | wil 8, hp 24; mult light 1.18, dmg 1.05 | The coal left in the Great Lantern's base. Cold fire has gone out of it; it is only warm. |
| `ff_greatcoat` | armor | ultra | 900 | def 14, hp 16; mult heal 1.1 | The Fairwarden's greatcoat, lined with fifty winters' wool. |
| `ff_lamp_pole` | weapon | rare | 150 | atk 10, wil 3; mult light 1.1 | A lamp-lighter's long pole, brass-hooked. For the Dealer's pool and the forge. |

### 9.9 Tests (`tests/test_ff.py`)

Every lock with its exact message and (for `all`/`flags`) its status line; the three-post flag lock opened by `cmd_light` at each post; the Dread door shut at Dread 25, open at 24, with and without the key; booth key given once from the mini; Marit invite -> Joss -> built -> she is in `ff_stall`, no longer in the booth; daily candle once per `dealer.today()`; Odo valve; the boss path (step back, flee, die twice -> mercy ceiling 55, win) copied from `test_court`; band gems once; beacon lights all 13 Frostfair rooms and none of the annex; annex hatch locked until the beacon; Dealer: `ff` rooms are seats only after `beacon_Ember Court`, 4 seats (compute with `dealer.seats(5)` filtered by region); `wake`; `ff_given_flame` given once across a call-back; no hollow+light weakness; validator clean; fuzz reaches all 17 rooms.

---

## 10. Package `vg`: The Vigil (ring 5, area B)

**Concept.** The Order of the Open Eye kept the **Signal Watch**: observatory-monks who watched for the Lightwell's dawn pulse and relayed it by mirror across the north. Aldric borrowed the Signal itself: the Order would keep watching the east until he sent word that it was done, and then they might close their eyes. Fifty years later (18,262 days; the counters in the Reckoning Room say so) they are still awake. The wrongness is **watching**: not hollow, **over-lit**. Light with no night. The Unsleeping are light-sick, lucid and hopeless; their machines keep counting. These are mostly **not Hollows**, so a flare does no extra: this is where spells and gear matter and flare-spam does not. The revelation: night is a kindness when it ends in morning.

**Lane.** **Shadow and Earth carry** (Wayfarer's and Warden's home); **Light and Fire are resisted** by almost everything. Exactly one roster, the Blind Spots, is Hollow, so a Light book is not dead weight (Radiance doubles on them) but flares are no longer the answer. Two fields tax the lane (Hall of Mirrors, Noon). The rotating-weakness Orrery makes a three-book loadout the answer.

**Regions** (`data/regions/vg.json`):
```json
[{"id": "The Vigil", "ring": 5, "levels": "11-12", "gear": "Legendary - Godlike",
  "blurb": "A ridge-top observatory whose watchers have not closed their eyes in fifty years.",
  "dealer": true, "dealer_after": "beacon_The Frostfair"},
 {"id": "The Waking Cellars", "ring": 5, "levels": "12", "gear": "Godlike",
  "blurb": "The Order's sleeping-cells, below the Court of Dials. Those who died awake are still on watch.",
  "dealer": false}]
```

**Attach** (`data/attach/vg.json`):
```json
{"ff_signal_stair": {"exits": {"u": "vg_ladder"},
   "locks": {"u": {"flag": "beacon_The Frostfair", "msg": "The Signal Stair climbs into cloud, but its first step is a plate of ice that will not give. The Fair's Great Lantern lights this stair from below: relight the Great Lantern (the beacon in the Wintering Square) and the ice will go."}}},
 "tower": {"exits": {"w": "vg_loft"},
   "locks": {"w": {"building": "vg_almanac", "msg": "A vacant plot beside the Magician's Tower, with a roof-ladder already leaning against it. Joss can build a loft here once a star-reader is willing to move in."}}}}
```
This is the only place that edits `ff_signal_stair`; `vg` cannot validate until `ff`'s files exist (section 2.2). `ff` validates alone (its stair is a dead end until `vg` lands).

### 10.1 Map

```
                      (2,-1)library - (3,-1)heliograph#
 (0,0)ladder - (1,0)lodge - (2,0)great_court - (3,0)orrery_hall - (4,0)lens_stair - (5,0)eye
                  |             |   \d            |
             (1,1)dormitory-(2,1)reckoning -(3,1)mirror_gallery
                  |             |                 |
             (1,2)cupboard - (2,2)chapel      (3,2)camera_obscura
 annex: (0,0)cellar_stair - (1,0)cellar_hall
                                 |
                            (1,1)cellar_cells
```

### 10.2 Graph

| Room id | Name | Region | Pos | Exits | Locks / specials |
|---|---|---|---|---|---|
| `vg_ladder` | The Long Ladder | Vigil | 0,0 | d `ff_signal_stair`, e `vg_porters_lodge` | |
| `vg_porters_lodge` | The Porters' Lodge | Vigil | 1,0 | w `vg_ladder`, e `vg_great_court`, s `vg_dormitory` | `rest`, `outpost`, `wake`; NPC `vg_tick` |
| `vg_great_court` | The Court of Dials | Vigil | 2,0 | w `vg_porters_lodge`, n `vg_library`, e `vg_orrery_hall`, s `vg_reckoning_room`, d `vg_cellar_stair` | d: `{"flag": "beacon_The Vigil", "msg": "A trapdoor under the Court's great sundial, bolted. The Order's sleeping-cells lie below, and the bolt only slides once the Signal is sent: light the brazier under the Eye."}` |
| `vg_library` | The Chart Library | Vigil | 2,-1 | s `vg_great_court`, e `vg_heliograph` | |
| `vg_heliograph` | The Heliograph Terrace | Vigil | 3,-1 | w `vg_library`, s `vg_orrery_hall` | `waypost` |
| `vg_orrery_hall` | The Orrery Hall | Vigil | 3,0 | w `vg_great_court`, n `vg_heliograph`, s `vg_mirror_gallery`, e `vg_lens_stair` | `fixed` {flag `vg_orrery_dead`, enemies [`vg_orrery`], intro "The Orrery turns, and the whole sky turns with it. 'Visitors are not on the chart,' it hums."}, `boss` `vg_orrery_dead`, `boss_name` "The Great Orrery"; e: `{"item": "vg_lens_key", "msg": "The Lens Stair is shut behind a bronze iris that turns only for the Orrery's key. The Great Orrery wears it, and it is turning in this room. Defeat it."}` |
| `vg_dormitory` | The Dormitory | Vigil | 1,1 | n `vg_porters_lodge`, e `vg_reckoning_room`, s `vg_lens_cupboard` | |
| `vg_reckoning_room` | The Reckoning Room | Vigil | 2,1 | n `vg_great_court`, w `vg_dormitory`, e `vg_mirror_gallery`, s `vg_chapel` | |
| `vg_mirror_gallery` | The Mirror Gallery | Vigil | 3,1 | n `vg_orrery_hall`, w `vg_reckoning_room`, s `vg_camera_obscura` | s: `{"element": ["shadow"], "remember": "vg_obscura_open", "msg": "The Camera Obscura has no lamp and no window and a door of black felt-lined oak. It lets in only someone who carries a night of their own: equip a Shadow spell book (type 'spells') and try again."}`; field Hall of Mirrors |
| `vg_camera_obscura` | The Camera Obscura | Vigil | 3,2 | n `vg_mirror_gallery` | `no_dealer` |
| `vg_chapel` | The Chapel of Closed Eyes | Vigil | 2,2 | n `vg_reckoning_room`, w `vg_lens_cupboard` | `no_dealer`; mercy scene (ENTER) |
| `vg_lens_cupboard` | The Lens-Cleaner's Cupboard | Vigil | 1,2 | n `vg_dormitory`, e `vg_chapel` | `no_dealer`; NPC `vg_hale` |
| `vg_lens_stair` | The Lens Stair | Vigil | 4,0 | w `vg_orrery_hall`, e `vg_eye` | `no_dealer` (behind the Orrery's key; `_behind_a_lock` cannot see it because the Eye has an exit back into it) |
| `vg_eye` | The Great Lens Chamber | Vigil | 5,0 | w `vg_lens_stair` | `boss` `vg_eye_dead`, `boss_name` "The Unsleeping Eye", `beacon`, `beacon_oil` 35; field Noon; boss via ENTER |
| `vg_loft` | The Almanac Loft | Hollowmere | -2,1 | e `tower` | building room, `dark` false |
| `vg_cellar_stair` | The Cellar Stair | Waking Cellars | 0,0 | u `vg_great_court`, e `vg_cellar_hall` | `waypost` |
| `vg_cellar_hall` | The Long Dormitory Below | Waking Cellars | 1,0 | w `vg_cellar_stair`, s `vg_cellar_cells` | |
| `vg_cellar_cells` | The Cells | Waking Cellars | 1,1 | n `vg_cellar_hall` | |

Bypass check: `vg_lens_stair` only via `vg_orrery_hall` e (item); `vg_eye` only via `vg_lens_stair`; `vg_camera_obscura` only via `vg_mirror_gallery` s (element). Dealer seats (dark, ordinary, not `no_dealer`, and `dealer._behind_a_lock` false): `vg_ladder`, `vg_great_court`, `vg_library`, `vg_dormitory`, `vg_reckoning_room`, `vg_mirror_gallery` = **6**, active only after `beacon_The Frostfair`. (`vg_ladder` counts: `vg_porters_lodge` has an unlocked exit into it.)

### 10.3 Contents

| Room | desc seed | features | items | enc (chance; groups) |
|---|---|---|---|---|
| `vg_ladder` | A thousand steps cut in the ridge, the cloud falling away below. Above, daylight with no night in it. | `steps`: "Fifty years of tallies. The last mark is today's." | | .30; [`vg_brother`]x3, [`vg_brother`,`vg_star`]x1, [`vg_glare`]x1 |
| `vg_porters_lodge` | A clockwork porter's lodge, a row of warm slippers by the door, a bell, a hundred beds' worth of folded blankets. | `slippers`: "Eight thousand slippers. Warm. The Brothers do not use them." | | none |
| `vg_great_court` | Sundials, astrolabes, the whole sky in brass. All of them point at the same spot. | `dials`: "Every shadow falls to the same patch of floor. There is a worn place there, as if someone has been standing in it." | | .35; [`vg_sentinel`]x2, [`vg_brother`]x2, [`vg_star`]x1, [`vg_brother`,`vg_sentinel`]x1 |
| `vg_library` | Star-charts on every wall, annotated in a tall narrow hand. | `charts`: "In the margin of the Great Chart, in tiny script: Ysolde, N.B. the Eye must not be left unwatched. She underlined it twice." | `vg_receipt`, `vg_star_plate` x2, `strong_draught` | .30; [`vg_brother`]x2, [`vg_glare`]x1, [`vg_brother`,`vg_brother`]x1, [`vg_star`,`vg_glare`]x1 |
| `vg_heliograph` | A terrace of relay mirrors that carried the dawn to the next ridge. | `mirrors`: "Facing east, every one. Lighting the waypost is the first flash in fifty years." | | .30; [`vg_glare`]x2, [`vg_glare`,`vg_star`]x1 |
| `vg_orrery_hall` | A brass model of the sky as big as a chapel, its planets still wandering. | `orrery`: "The Earth is a pearl on a wire. The Sun is a lamp that has been turned down." | | none (fixed) |
| `vg_dormitory` | Two hundred beds, every one made. | `beds`: "Hospital corners. Each pillow has a dent from the one night, fifty years ago, when they lay down and could not close their eyes." | | .30; [`vg_brother`]x2, [`vg_blind_spot`]x1, [`vg_brother`,`vg_blind_spot`]x1 |
| `vg_reckoning_room` | Brass counters tallying days awake. | `counters`: "DAY 18,262 OF THE VIGIL. The number turns while you watch." | | .35; [`vg_blind_spot`]x2, [`vg_sentinel`]x1, [`vg_sentinel`,`vg_star`]x1, [`vg_blind_spot`,`vg_brother`]x1 |
| `vg_mirror_gallery` | A hall of mirrors that never reflects the same thing twice. | `mirrors`: "One shows the room. One shows the room fifty years ago, full. One shows you, asleep." | | .40; [`vg_glare`]x3, [`vg_glare`,`vg_glare`]x1, [`vg_glare`,`vg_sentinel`]x1, [`vg_star`]x1 |
| `vg_camera_obscura` | A dark room. The only dark room in the Vigil. | `plates`: "Glass plates of the night sky, stacked to the ceiling. Nobody has looked at them in fifty years." | `vg_sixfold_chart`, `vg_astrolabe_rod`, `vg_nightcloak`, `hollow_core` x2, `vg_starglass` x4, `relic_pulse`, `core_heart_shadow`, `core_heart_light` | none |
| `vg_chapel` | Where the Order closed the eyes of their dead. A grey habit kneels at the altar. | `altar`: "Worn hollow where hands have pressed down eyelids for centuries." | | none (event) |
| `vg_lens_cupboard` | A cupboard with a cot, a dented pillow and the only dust in the Vigil. | `dust`: "Real dust. Soft, grey, undisturbed. It is the most restful thing you have seen in this building." | | none |
| `vg_lens_stair` | The last steps before the Eye. The light is so bright the stone has no shadows. | `stair`: "Dread peaks here. Count the steps and breathe." | | .30; [`vg_sentinel`]x2, [`vg_brother`,`vg_sentinel`]x1, [`vg_star`]x1 |
| `vg_eye` | A drum of brass and glass. In the middle, on a mount that has not moved in fifty years, a lens thirty feet across. | `lens|eye`: "The Eye. Inside it, if you look, a shape that might be a face." `brazier|beacon`: "The Signal Brazier under the Eye. When it is done, light it (type 'light')." | | none (boss) |
| `vg_loft` | A loft with a window facing east, a ladder, a desk of charts. | `window`: "East-facing. The first thing it will ever see is the morning." | | none |
| `vg_cellar_stair` | Steps down into cool, honest dark. The first night the Vigil has had. | `dark`: "Dark. Real dark. It takes a moment to remember it is not an enemy." | | .40; [`vg_brother`]x2, [`vg_blind_spot`]x2, [`vg_sentinel`]x1 |
| `vg_cellar_hall` | Rows of narrow cots, and on each a Brother lying with open eyes. | `cots`: "They are not breathing. They are not blinking either." | `vg_star_plate` x2, `strong_draught` | .45; [`vg_cellar_dead`]x2, [`vg_brother`,`vg_blind_spot`]x2, [`vg_sentinel`]x1 |
| `vg_cellar_cells` | Cells for those who asked to be left alone with the dark. | `cells`: "Doors open, every one. Nobody has been alone with the dark in fifty years." | | .45; [`vg_cellar_dead`]x2, [`vg_sentinel`,`vg_blind_spot`]x2, [`vg_brother`]x1 |

`wake` (`vg_porters_lodge`): "You wake with slippers on your feet that you did not put there. Tick is standing by the bed with its hands folded. 'Rested,' it says. 'Warm.' Your purse is lighter by %d gold."
`waypost_text` (`vg_heliograph`): "You open the relay lamp and touch your flame to its wick. The first mirror throws a flash across the dark, east, the first in fifty years. Nothing answers. Not yet."
`beacon_text` (`vg_eye`): "You pour the oil into the Signal Brazier under the Eye, and touch your flame to it."
Fields: `vg_mirror_gallery` `{"name": "Hall of Mirrors", "light": 1.25, "shadow": 0.8, "msg": "The mirrors fold light back on itself and swallow shadow: flares and Light spells burn brighter, Shadow spells weaker."}`; `vg_eye` `{"name": "Noon", "shadow": 0.75, "light": 1.25, "msg": "It is permanent noon under the Eye: shadow spells are thinner here, light thicker."}`.

### 10.4 Enemies (`data/enemies/vg.json`; ordinary mobs = Court x1.45 hp and atk, min 55% singles)

| id | Name | tags | hp/atk/def/dodge | xp | gold | weak | resist | Moves | Drops |
|---|---|---|---|---|---|---|---|---|---|
| `vg_brother` | Unsleeping Brother | undead | 310/54/8/5 | 185 | 74-108 | shadow, earth | light, fire | Measure (attack 1.0 w3); Unblinking Gaze (debuff blind 2 w2; "does not blink"); Vigil Strike (heavy 2.0 w2; "raises the long staff"); Count the Hours (defend w1) | `vg_starglass` .45, `essence_shadow` .3, `vg_star_plate` .3, `core_heart_shadow` .04 |
| `vg_sentinel` | Armillary Sentinel | construct | 610/64/18/0 | 205 | 84-126 | earth, ice | fire, shadow | Ring Strike (attack 0.6 hits 2 w3); Align (charge->Convergence w2; "its rings begin to align. CONVERGENCE is coming") with `extra_moves` Convergence (heavy 3.0); Spin Up (defend w1) | `vg_starglass` .5, `essence_earth` .3, `core_heart_earth` .05 |
| `vg_glare` | Heliograph Glare | construct | 260/52/4/30 | 190 | 79-116 | shadow, water | light, fire | Flash (debuff blind 2 w3); Burning Beam (attack 1.0 status burn 3,9 w3); Focus (charge->Sunbeam w1; "gathers every mirror into one point. SUNBEAM is coming") with `extra_moves` Sunbeam (heavy 2.8) | `vg_starglass` .4, `essence_light` .3, `core_heart_light` .04 |
| `vg_star` | Fallen Star | star | 330/55/6/12 | 195 | 79-122 | ice, water, shadow | light, fire | Streak (attack 1.0 w3); Nova (heavy 2.0 status burn 3,8 w2; "swells and whitens"); Cold Fire (drain 0.8 drain 12 w1) | `vg_starglass` .35, `essence_ice` .3, `core_heart_fire` .04 |
| `vg_blind_spot` | Blind Spot | hollow | 300/55/0/35 | 190 | 74-116 | fire, ice | shadow, earth | Smother (attack 1.0 status weak 2,0 w3); Swallow Light (drain 0.9 drain 14 w2); Void (heavy 2.2 w1; "the dark inside it opens") | `vg_starglass` .3, `essence_shadow` .3, `core_heart_shadow` .04 |
| `vg_cellar_dead` | Wakeful Dead | undead | 560/64/14/0 | 215 | 143-221 | shadow, earth | light, fire | Grave Measure (attack 1.0 w3); Open Eyes (debuff blind 2 w2); Long Vigil (heavy 2.2 w1; "stares until you feel it") | `vg_starglass` .6, `core_heart_shadow` .06, `core_heart_light` .06, `core_heart_fire` .06 |
| `vg_orrery` | The Great Orrery | construct, elite | 900/57/15/0 (**built 980/57**) | 650 | 220-270 | **attune** | **attune** | Planet Strike (attack 1.0 w3); Wandering Star (summon `vg_star`, only_if can_summon, w1; "a planet slips its wire"); Eclipse (debuff blind 2 w1; "swings one ring between you and the light"); Conjunction (charge->Great Conjunction w2; "its rings begin to align. GREAT CONJUNCTION is coming") with `extra_moves` Great Conjunction (heavy 3.0). **Phase 0.5**, msg "The inner rings spin up. The outer rings counter-spin. The whole sky is going round.": same plus Precession (attack 0.5 hits 3 w3) | `hollow_core` 1.0 x2, `vg_starglass` 1.0 x3, `essence_earth` 1.0, `essence_ice` 1.0, `core_heart_earth` 1.0, `core_heart_water` 1.0 (`vg_lens_key` by hook) |
| `vg_prior_eye` | The Unsleeping Eye | construct, boss | **1386/83/18/0** at power 50 (Queen x1.8; **built 1175/70**) | 2300 | 1100-1400 | shadow, earth | light, fire | below | below |

**Orrery attune** (`attune` on `vg_orrery`; base `weak`/`resist` = stance 1): `{"every": 2, "stances": [{"name": "Sun-line", "weak": ["shadow", "water"], "resist": ["light", "fire"], "msg": "The inner rings lock to the Sun-line."}, {"name": "Moon-line", "weak": ["fire", "earth"], "resist": ["shadow", "ice"], "msg": "The rings swing to the Moon-line."}, {"name": "Star-line", "weak": ["light", "ice"], "resist": ["earth", "water"], "msg": "The rings settle on the Star-line."}]}`. It is not Hollow, so Light as a weakness is legal. A loadout of one of {Shadow, Water} + one of {Fire, Earth} + one of {Light, Ice} has a strong book in every window; a spell fits about once per two rounds, so "cast what the next stance is weak to on the round it opens" is the whole fight. Stun cancels Great Conjunction.

**The Eye's moves.** Gaze (attack 1.0 w3); Burning Focus (attack 0.8 status burn 3,12 w2); Sweep the Sky (attack 0.5 hits 4 w2); Open the Dome (debuff exposed 2 w1; "the Dome shutters roll back"); Count the Stars (summon `vg_star`, only_if can_summon, w1); Noon (heavy 2.4 w2; "the lens whitens. NOON is coming").
- **Phase 0.66**, msg "The shutters of the Dome roll back. Starlight pours in, and the Eye turns it into daylight.": Gaze 1.1 w3, Burning Focus w2, Sweep the Sky 0.55 w2, Daylight (debuff blind 2 w2), Noon at Midnight (heavy 2.6 w2; "the lens whitens. NOON AT MIDNIGHT is coming"), Count the Stars w1.
- **Phase 0.33**, msg "Inside the glass, a face: the Prior, eyelids stitched with starlight. 'How many nights was that? Has the signal come?'": Prior's Vow (buff enraged 2,0 w1), Noon at Midnight 2.8 w2, Unblinking (drain 1.1 drain 16 w2; "will not close"), Gaze 1.2 w2.

**The Eye's `roll`:** `{"story": false, "pron": {"subj": "it", "obj": "it", "poss": "its"}, "place": "The Vigil", "flavour": [...], "bonus": [{"item": "vg_unsleeping_eye", "from": 10, "to": 60}, {"item": "hollow_core", "from": 1, "to": 100, "count": 3}, {"item": "vg_starglass", "from": 1, "to": 100, "count": 3}, {"item": "essence_shadow", "from": 20, "to": 100, "count": 2}]}`. Flavour:
1. "The Dome is half-shuttered, the Eye clouded. Behind the glass something is nodding, very slowly, forward."
2. "The Eye turns sluggishly, and every few seconds it blinks without meaning to."
3. "The Eye is open and bright and exactly as the Order left it: every lens aligned, every ring in place."
4. "Starlight is drawn to it in a hum. The brass rings are moving faster than brass should."
5. "The Eye is white. It is not a light you are looking at; it is a light looking at you."

Base drops (every win): `hollow_core` x2, `vg_starglass` x3, `essence_earth` x2, `essence_shadow` x2, `core_heart_shadow`, `core_heart_light`, `core_heart_water` (all 1.0).

### 10.5 Hooks (`areas/vg.py`)

- `ENTER["vg_ladder"]` (first visit, return False): "A thousand steps. At the top, the cloud ends. And above it, fifty years of daylight with no night at all. You find, climbing, that you are looking at the sky and can't stop."
- `ENTER["vg_porters_lodge"]` (first visit): Tick's introduction (below). `ENTER["vg_dormitory"]` (first visit): the beds feature read aloud.
- **`ENTER["vg_chapel"]` (the mercy scene)**, until `vg_chapel_done`: narrate "A Brother kneels at the altar in the grey habit of the Order, pressing his own eyelids shut with two thumbs. They spring open. He does it again." Menu: **"Sit with him until he sleeps"** / **"Raise your lantern and fight"** / **"Leave him be"**.
  - *Sit*: you hum the lamplighter's dusk-song; he lies down on the stones, the first closed eyes in the Vigil; narrate "His breathing slows, and for the first time in fifty years something in this building is asleep." Rewards: set `vg_brother_slept` and `vg_chapel_done`; Dread -50 (floor 0); once (`vg_gems_chapel`) +1 gem; +100 gold ("a purse of unspent wages beside the altar"); `vg_star_plate`. He is not an enemy again; the room's `features` gain "A grey habit on the altar steps, folded as if slept in." (the `altar` feature text is replaced when `vg_brother_slept`).
  - *Fight*: `g.fight(["vg_brother", "vg_brother"])`; on a win set `vg_chapel_done` (normal xp, gold and drops).
  - *Leave*: nothing; the scene repeats next entry.
  The mercy path is at least as rewarding as the fight (equal gold, plus gem, Dread relief, a plate, and Hale's line).
- `AFTER_FIXED["vg_orrery_dead"]`: narrate "The Orrery slows, ring by ring, to a stop. The planets settle on their wires. Somewhere above, in the Dome, a sound like a held breath being let go by a hundred people at once." `events.give_once(g, "vg_lens_key")`; once (`vg_gems_orrery`) +2 gems.
- `UNLOCK[("vg_mirror_gallery", "s")]`: "The felt door sighs open. Inside, a darkness so complete it feels like being forgiven."
- `ENTER["vg_eye"]`: if `vg_eye_dead` return False; else `powerroll.boss_scene(g, "vg_prior_eye", "vg_eye_dead", "vg_lens_stair", _won, intro=..., prologue=...)`. First prologue (flag `vg_met_eye`): narrate "The Chamber is a drum of brass and glass. In the middle, on a mount that has not moved in fifty years, the Eye looks at you without any eyelid. A Prior's chain hangs from the mount." A voice from inside the lens: *"Do not close your eyes."*
- `_won(g, power)`: narrate "The Eye clouds, and clears, and in the glass a man's tired face." *"Is it dark? Is it dark outside?"* ...You say it is. *"Oh. Oh, that's what it was supposed to look like."* narrate "Overhead, for the first time in fifty years, the shutters of the Dome roll slowly closed. In the silence you can hear a hundred pairs of eyes shut in the corridors below. The beacon brazier at the foot of the mount is cold." Band gems `{3: 1, 4: 2}` once (`vg_gems_band`). Grey "(Type light to send the signal.)"
- `AFTER_BEACON["The Vigil"]`: set `vg_signal_sent`; narrate "The Eye's shutters roll open one last time, and the brazier's light goes up through the lens, enormous and steady, and out across the dark. Far to the south-east, in the valley, a small light answers. Then another. Then a third: three flashes, the Hollowmere lamplighters' dusk signal, the one the Order was told to wait for fifty years ago. The Vigil is released."
- `BOSS_TIPS["vg_eye"]`: "You see its strength before you decide; step back or run for free. It is not a Hollow, so flares do nothing special: use Shadow and Earth books. It is weak to them; Light and Fire are resisted, and the Noon field thins Shadow and thickens Light. Kill the Stars it calls. Guard Noon and Noon at Midnight."
- `BOSS_TIPS["vg_orrery_hall"]`: "An elite: no running. It changes alignment every two rounds (the board shows the next one): cast what the next alignment is weak to. Guard Great Conjunction. Kill the Stars it calls first."
- `OBJECTIVES`: main (while `beacon_The Frostfair` set, `beacon_The Vigil` not): `vg_ladder` not visited: room `vg_ladder`, "The Signal Stair is open. Climb to the Vigil"; else not `vg_orrery_dead`: room `vg_orrery_hall`, "Find the Orrery's key: the Great Orrery turns in the Orrery Hall"; else not `vg_eye_dead`: room `vg_eye`, "Face the Unsleeping Eye"; else room `vg_eye`, "Send the signal: light the brazier". Side: room `vg_chapel`, "A Brother kneels in the Chapel of Closed Eyes. Sit with him?" (unresolved, `vg_reckoning_room` visited); room `vg_mirror_gallery`, "The Camera Obscura: a Shadow book, equipped, opens the felt door" (gallery visited, not `vg_obscura_open`); room `vg_lens_cupboard`, "Hale Teasel is hiding in the Lens-Cleaner's Cupboard. Ask him, then see Joss" (`vg_orrery_dead`, almanac not built).
- `SELLS["odo"]`: `["vg_starglass"]` once `vg_eye_dead`; `PRICES["vg_starglass"] = 90`.

**Hollowmere reactions** (`vg.py`):
- `TOPICS["hesk"]`, when `beacon_The Frostfair` and not `vg_signal_sent`, and until `vg_hesk_told`: "Ask about the nights" (sets `vg_hesk_told`): *"Nobody's sleeping on the east lanes. They say it's as if someone's looking at the town through a window left open. Everybody's lamps burn too bright; I've half a drum of oil I never used."* After `vg_signal_sent`: *"First proper dusk in a month. Half the town fell asleep in the square. I let them."* `EXTRA_NEWS["hesk"]`: `beacon_The Frostfair and not vg_hesk_told`.
- `RUMOURS`: `beacon_The Frostfair` and not `vg_signal_sent`: "There's a woman in my back room who hasn't slept in a week and keeps thanking me for the beds."; after `vg_signal_sent`: "Slept ten hours. Ten! Now I'm cross at all the hours I've lost."
- `TOPICS["orrin"]`, after `vg_signal_sent`, until `vg_orrin_told`: "Tell Orrin the signal was answered" (sets `vg_orrin_told`): *"Three flashes from the Hall, I gave the order myself. They were still waiting. They were all still waiting. ...Aldric, you wretched, wonderful man."*

### 10.6 NPCs

**Tick, the porter** (`vg_tick`, `NPCS` desc: "A clockwork porter of brass and felt, a little too formal, with a ring of keys that has not been used since the first year of the Vigil."). Shop `STOCK`: `oil`, `strong_draught`, `vg_nightcap`, `vg_clear_draught`, `tonic`, `firepot`, `smokebomb`. First entry: *"Welcome to the Vigil. Do not close your eyes. ...(a pause) That is a joke. I was told jokes were permitted after the fiftieth year."* Further: *"Eight thousand slippers. Warm. The Brothers do not use them. The slippers are for emergencies."* After `vg_eye_dead`: *"The lights may go out now. Would you like the lights out?"* After the beacon: *"I will turn down the beds. All of them. It will take eleven years. That is acceptable."* Topics: "Ask about the Order" (the Open Eye, the Signal Watch, the Prior); "Ask about the fiftieth year" (what changed: Hale did not come out of the cupboard).

**Hale Teasel, the novice who slept** (`vg_hale`, about 81, mild, humorous, ashamed; desc: "A very old man with a creased, sleep-marked face and a candle-end in one hand, peering round the edge of a door as though expecting to be shouted at."). Located in `vg_lens_cupboard`'s `npcs`. `PRESENT["vg_hale"]`: `vg_orrery_dead and not town.is_built(g, "vg_almanac")`. `NPCS["vg_hale"]["where"]` returns `vg_loft` when built. `NEWS["vg_hale"]`: not met, or `vg_signal_sent` and not `vg_flame_given`, or `vg_orrery_dead` and not invited/built.
- First talk (`vg_hale_met`): narrate "A face at the crack of a cupboard door, creased with sleep. 'Are they very angry?' he says." Hale: *"I fell asleep. The third night of the Vigil. Behind the lens-cleaning rags. Nobody noticed. They locked the door to spare me the shame and watched on without me, for fifty years, and I let them."* Menu: **"You were nineteen."** / **"Sleep isn't a sin."** / **"You're the only one who can tell them it ended."** Any answer: *"Ah. So I'm the Order's last witness, and I'm a sleeper. The universe has a sense of humour."*
- After `vg_brother_slept`, until `vg_hale_slept`: topic "Tell him about the Brother in the chapel": *"You made one of them close his eyes? ...I'd like to see that. Is it possible to be forgiven by a man in his sleep?"*
- After `vg_signal_sent`, until `vg_flame_given` (offered automatically): he weeps, thanks you; narrate "He lights his tiny cupboard-candle from the Signal and offers you the flame." Hale: *"I kept this one for emergencies. This is one. It isn't a loan."* `events.give_once(g, "vg_given_flame")`, set `vg_flame_given`.
- "Ask him to come to Hollowmere" (after `vg_hale_met`): `npcs._invite_scene(g, "vg_almanac", "Hale", "A town with an east-facing window? ...Yes. Yes, I believe I'd like to see the morning. For the first time in my life I won't be too tired to enjoy it.", "", "Tell Joss, in the yard on Market Row. An east window, please.")`.
- When the loft is built: topic **"Read the almanac"** (the Almanac service) and, when `vg_sixfold_chart` is held and not `vg_chart_read`, **"Show him the Sixfold Chart"**: *"This is not a star-map. It's a recipe: the six lights in the order they must be held. Take it to the Magician. She'll need me to read the order aloud."* Sets `vg_chart_read`.
- **Almanac service** (`vg.almanac(g)`, free, any number of times): for rings 1 to 5 print `Ring N: <room name>` for today and tomorrow, using `dealer.room_for(g, ring, dealer.today())` and `dealer.today() + 1`; `nowhere (the ring is lit)` when `None`; append "(you cannot reach it yet)" when `navigation.find_path(g, g.room_id, room)` is `None` for today's room.

### 10.7 Building and items

`data/buildings/vg.json`: `{"vg_almanac": {"name": "Almanac Loft", "room": "vg_loft", "resident": "vg_hale", "cost": {"gold": 1600, "items": {"vg_starglass": 8, "slag": 10}}, "minutes": 45, "steps": 70, "rent": 18, "blurb": "Hale reads the sky for you: where each Dealer sits today and tomorrow."}}`. Room `vg_loft`: region `Hollowmere`, pos [-2,1], `dark` false, exits `{"e": "tower"}`.

`data/items/vg.json`:

| id | kind | rarity | value | stats / use / mult | desc |
|---|---|---|---|---|---|
| `vg_starglass` | material | uncommon | 25 | stack | Vigil Glass: ground lens-blanks, clear as a held breath. The Builder and the forge use it. |
| `vg_nightcap` | consumable | common | 60 | use dread -60, heal 10 | A knitted cap. Smells of lavender and, faintly, of permission. |
| `vg_clear_draught` | consumable | common | 50 | use heal 60, cleanse true | Cold water drawn through a lens. Clears the head and the eyes. |
| `vg_star_plate` | junk | common | 90 | stack | A glass plate of a star that has since moved. |
| `vg_lens_key` | key | common | 0 | | A bronze iris-key. |
| `vg_receipt` | key | common | 0 | | (section 3.4) |
| `vg_given_flame` | key | common | 0 | | A candle-flame in a thimble of glass, offered, not lent. |
| `vg_sixfold_chart` | key | common | 0 | | A star-chart with six wheels in six colours. Hale says it is a recipe. |
| `vg_unsleeping_eye` | trinket | legendary | 3000 | wil 9, hp 28, crit 6; mult spell 1.2, dmg 1.06 | A flake of the Eye's lens, set in a black ring. It never closes. |
| `vg_astrolabe_rod` | weapon | rare | 160 | atk 9, wil 6; mult spell 1.1 | A brass rod with a star-wheel at the tip; for the Dealer's pool and the forge. |
| `vg_nightcloak` | armor | rare | 150 | def 8, dodge 4, wil 1 | A cloak that drinks light; for the Dealer's pool and the forge. |

### 10.8 Tests (`tests/test_vg.py`)

Both locks and the beacon-gated cellar trapdoor with exact messages; the Shadow lock open with a Shadow book, shut with a Fire book, `remember` after; the mercy chapel (sit rewards at least the fight's; once only; Dread -50; fight path; leave path repeats); Hale presence rules (absent before the Orrery falls, in the cupboard after, in `vg_loft` once the Almanac is built); the almanac output with a Dealer in each ring and a locked-out room; boss scene paths (step back, flee, die twice -> mercy, win) with `it` pronoun and `The Vigil` place text; Orrery attune cycling (stance changes every 2 rounds; `best_spell` follows); beacon lights 14 Vigil rooms and none of the cellars; Dealer moves to the Vigil once the Frostfair is lit and is gone when the Vigil is lit; `wake`; `vg_given_flame` once across a call-back; no hollow+light weakness; validator clean; fuzz reaches all 18 rooms.

---

## 11. Package `late`: the Third Quench, two-slot Godlike forging, the Long Quench

`late` makes `godlike_recipe` obtainable (the flag `forge.json` already requires), makes a Godlike attempt take two anvils, and adds the week-long smith upgrade. It also owns the journal quest `late_lending` and the Orrin/Brann/Tamsin/Pell scenes.

### 11.1 Forge retune (`data/forge.json`; owner decision, section 20)

Expected attempts per tier from the real odds, pity and heat (`chance + 0.04 x heat`, sure at `pity` failures) are **2.48 / 3.56 / 4.82 / 6.42**. At the old prices that is 620 / 3,205 / 14,470 / **77,080** gold expected, against about 4,000 gold per ring-5 clear: Godlike was unreachable. New values (odds, pity, heat and times unchanged except where noted):

| Tier | gold old to new | items old to new | expected gold new |
|---|---|---|---|
| Rare to Epic | 250 (same) | same | 620 |
| Epic to Ultra | 900 to **600** | same | 2,140 |
| Ultra to Legendary | 3,000 to **1,500** | slag 15 to **12**, saltstone 8 to **6**, hollow_core 2 (same) | 7,230 |
| Legendary to Godlike | 12,000 to **3,000** | slag 30 to **20**, saltstone 15 to **10**, hollow_core 4, plus **`ff_rime` 4, `vg_starglass` 4** | **19,260** |

The Godlike tier also gets `"slots": 2` (it needs both anvils: Brann's and Tamsin's; "two hands on the wick") and keeps `needs_flag: godlike_recipe`, `chance` 0.02, `pity` 30, 1,440 minutes, 800 steps. Material demand for one expected Godlike (refund 50% on a failure, so x3.71 the single-attempt list): slag 74, saltstone 37, Hollow Cores 15, Rime 15, Vigil Glass 15. Those are bought, not farmed: Odo sells Rime (70) and Vigil Glass (90) once the matching boss is dead; slag and saltstone are on his shelf already. `forge.json` item ids are validated (C4e).

### 11.2 Forge code changes (`forge.py`, `forge_ui.py`, `savecheck.py`)

- A job gets two optional keys, both defaulting so old saves load unchanged (SAVE_VERSION stays 2): `"slots"` (int, default 1) and `"kind"` (`"forge"` default, or `"temper"`).
- `forge.free_slots(g)` = `slots - sum(j.get("slots", 1) for j in jobs)`. New `forge.slots_needed(iid)` = `info(iid).get("slots", 1)`. `forge.start` requires `free_slots >= slots_needed`; `forge.missing` appends `"a second anvil (build the Ember Smithy)"` when the player's `state["slots"] < slots_needed`, and its `needs_flag` text becomes `"the third quench (ask Orrin about Aldric's receipts, then Brann and Tamsin)"`.
- The loaner hand-over in `start` is factored into `forge._hand_over(g, iid)` (returns `(slot, loaner_id)`), shared with the Long Quench.
- `forge.collect(g, index)` for a job with `kind == "temper"` delegates to `quench.collect(g, job)` and returns `{"kind": "temper", ...}`; `forge_ui` renders that with a three-stop colour sweep (x2.0, x2.5, x3.0) instead of the rarity sweep, and `_job_lines` / `_hurry` handle temper jobs (`Long Quench`, days left, `quench.hurry`).
- `forge_ui` menu: a row "The Long Quench (a week at the anvil)" appears once `godlike_recipe` is set or the pack holds a Godlike weapon; it opens `quench.menu(g)`.
- `savecheck._check_forge` accepts the new job keys (`slots` positive int, `kind` in `{"forge", "temper"}`); `_good_gear` accepts an optional instance number `temper` (1.0 to 3.5) and rebuilds with it.

### 11.3 The Long Quench (`lamplighter/quench.py`, `data/smith.json`)

`data/smith.json` (TUNE with `tools/sim_smith.py`):
```json
{"quench": {"needs_flag": "godlike_recipe", "needs_building": "ember_smithy",
  "gold": 9000, "items": {"hollow_core": 6, "ff_rime": 8, "vg_starglass": 8, "slag": 20},
  "days": 7, "steps": 5000,
  "outcomes": [{"mult": 2.0, "weight": 45}, {"mult": 2.5, "weight": 35}, {"mult": 3.0, "weight": 20}],
  "pity_step": 0.10, "pity_cap": 0.60,
  "hurry": {"gems_per_day": 12, "max_days": 2}}}
```
- **Who and what.** Godlike *weapon instances* only (worn or in the pack, not a loaner), after `godlike_recipe`, with the Ember Smithy built (both smiths: Brann and Tamsin). One slot, 7 real days (10,080 minutes) **or** 5,000 steps, whichever first (5,000 steps is about 20 sessions of walking, so the clock governs). While it works the player carries the existing 20% loaner of the same weapon (stated on the item).
- **Result.** Odds are shown before starting: base 20% x3.0, 35% x2.5, 45% x2.0. **It never destroys and never goes below x2.0.** Pity: flag `late_quench_pity` (int) counts consecutive results below x3.0; the chance of x3.0 is `min(0.60, 0.20 + 0.10 x pity)`, the rest split 45:35; reset on a x3.0.
- **Keep the better.** `inst["temper"]` holds the multiplier. Re-quenching a weapon already at x2.0 or x2.5 is allowed (same cost, same job); the result replaces the stored value only if higher, and the reveal says which it kept. A weapon at x3.0 cannot be re-quenched.
- **`gear.rebuild`.** After affixes and relics: `if inst.get("temper") and not inst.get("loaner"): mult["dmg"] *= inst["temper"]`; the name gets the prefix `Long-Quenched` and the description gains " Long-Quenched: all damage x%.1f." A relic socketed or removed after the quench keeps the multiplier (rebuild recomputes it). `make_loaner` builds a fresh instance and so carries no temper. The multiplier is on `mult["dmg"]`, so it lifts weapon blows, spells and flares alike (the plan's "2x to 3x"). A quenched weapon is tradeable (it is instance data).
- **Hurry.** `quench.hurry(g, index)` skips one day (86,400 s off `ready_at`) for 12 gems, at most twice per job. The last five days are always real time. Gems never replace the week.
- **Why this size.** Measured (section 14.3): damage saturates, survival is the limit. x2.0 alone on a plain Godlike raises the Vigil's boss from 67 to 82 percent; x3.0 adds little more. The quench is the answer to Ablaze rolls and to future rings, not a mandatory step.

### 11.4 The Third Quench: the Godlike recipe quest (`areas/late.py`)

Items (`data/items/late.json`): `late_receipt_court`, `late_aldrics_letter` (kind key, texts in section 3.4). Quest id `late_lending` (`quests.py`): stage 0 `lambda g: "Aldric left receipts for six borrowed flames. Orrin can read what you have (n of 6 found)."`, stage 1 "Aldric's letter says the third quench needs a flame that someone chose to give you. Corm's notes (the Lampwrights' Deep), Marit's flame (the Frostfair) and Hale's flame (the Vigil) go to Brann and Tamsin in the Ember Smithy.", `"done"` "Brann and Tamsin quenched a blade in a flame that was given. The third quench is known."

`AFTER_GAIN` keyed by each receipt id (`hos_receipt`, `rl_receipt`, `lw_receipt`, `ff_receipt`, `vg_receipt`, `late_receipt_court`): start quest `late_lending` at stage 0 if unset and print grey "(Receipts: n of 6. Orrin can read what you have.)".

| Step | Where | Requires | Result |
|---|---|---|---|
| 1. Pell's receipt | `TOPICS["pell"]`: "Ask for the Court's receipt" | `queen_dead`; not yet given | `give_once late_receipt_court`. Pell: *"The Queen kept it under her sceptre. 'Hold this for him,' she said. I've held it a hundred years. Now you."* |
| 2. Corm's notes | `TOPICS["brann"]`: "Show him Corm's notes" | holds `lw_quench_notes`, not `late_notes_shown` | sets `late_notes_shown`. Brann: *"Two quenches I know. The third was always a rumour. ...A flame that's given. How do you make a smith give a flame?"* Then "Ask what the third quench needs" (always, once notes shown) prints the checklist of what is still missing |
| 3. Aldric's letter | `TOPICS["orrin"]`: "Show him the receipts" | holds at least one receipt and the letter is unread | prints which hands Orrin recognises and, with fewer than six, that there were six, never naming where. With all six: narrate "Orrin turns the receipts over one by one and says nothing. Then he asks you to open the drawer under his bed, and in it is a letter sealed with wax gone brittle." Orrin: *"He left it with me the night he went down. 'Open it when someone brings back everything I borrowed.' Fifty years. I am a coward, but I can keep a promise."* He reads it aloud (section 3.4). `give_once late_aldrics_letter`; sets `late_letter_read`; quest `late_lending` stage 1 |
| 4. Two Given Flames | Marit (after `ff_thaw`), Hale (after `vg_signal_sent`) | the beacons | items `ff_given_flame`, `vg_given_flame` (given by `ff`, `vg`) |
| 5. The quench | `TOPICS["tamsin"]` in the Ember Smithy: "Ask about the third quench" | `ember_smithy` built; `late_notes_shown`; `late_letter_read`; holds both Given Flames | scene below |

**The scene.** *Brann comes through the back door of the Ember Smithy with his hammer, and Tamsin meets him at the anvil, and for the first time in either of their lives they are not each the other's rival. You hold the lantern. You hold, in your two hands, two small flames that were given.* Brann: *"Water."* Tamsin: *"Oil."* *And then the two of them, together, lower the blade into the light you are holding, and it does not hiss, and it does not burn: it sings. When they lift it out it is a plain grey blade, and it is the most beautiful thing you have ever seen.* Tamsin: *"Orrin's page said a flame shared is not a flame halved. I thought it was a saying. It's a method."* Result: remove both flame items; set `godlike_recipe` and `late_quench_done`; quest `late_lending` -> `"done"`. When a condition is missing, Tamsin prints exactly what (which flame, which notes, which letter).

`EXTRA_NEWS`: `orrin` when all six receipts are held and the letter unread; `brann` when notes held and not shown; `tamsin` when the scene is ready.
`OBJECTIVES` (side): room `hall`, "Aldric's receipts: n of 6 found. Orrin can read what you have" (n >= 1, letter unread); room `ember_smithy`, "The third quench: Corm's notes, Marit's flame, Hale's flame, then Tamsin in the Ember Smithy" (letter read, recipe not set); room `smithy`, "A Godlike weapon can be Long-Quenched at the forge" (recipe set, a Godlike weapon held, quench not running).

**Rewind safety.** `godlike_recipe`, receipts, letter and flames are never in `postgame.LAYERS`; a Wizard rewind clears none of them. Receipts and notes are key items (cannot be dropped, sold or stashed).
**Pre-ending/discoverability.** The Wizard (Roll of Lenders, `fin`) opens only after the story. Before it, each extension announces itself through its own side objective (see sections 6 to 8) and Hesk/Maeve rumours; Orrin names nothing.

### 11.5 Tests (`tests/test_late.py`)

Forge retune expected values (assert `FORGE` numbers); Godlike start blocked with one slot and succeeds with two; slots accounting with a mixed Godlike + Rare job; old save with jobs lacking `slots`/`kind` loads; the whole chain end to end (six receipts -> letter -> notes -> flames -> Tamsin -> `godlike_recipe`) with items given by the test, and out of order (each missing piece prints the right line); Long Quench in a fake clock: odds shown, loaner during the job, result distribution (seeded, 10,000 draws within 1.5 points of 45/35/20 at pity 0), pity raises x3.0 chance and resets, keep-better, never below 2.0, never destroys, hurry (2 days max, gems spent), save round-trip mid-job, `gear.rebuild` with a relic socketed after the quench, loaner carries no temper, `_good_gear` rejects `temper` 9.9; `AFTER_GAIN` quest counter.

---

## 12. Package `arc`: the apex unlock, Hearts, the Grand Binding, apex heat

Problem measured in the code: the apex needs six Godlike books, and combining gives a Legendary-to-Godlike jump of only 8% x (0.5 + 0.5 x ...) per attempt, which costs at least fifteen Legendary books per Godlike book (and each Legendary book is itself a 15% combine away from Ultra): six is "never". The apex stays a long tail (the owner's "10%" and loss rules are untouched), but M6 delivers the unlock and a supply.

1. **Unlock (`magic_ui.menu`).** A new option (shown only when `apex_unlocked` is not set, the player holds `vg_sixfold_chart`, flag `vg_chart_read` is set and `town.is_built(g, "vg_almanac")`): `{gold}Show her the Sixfold Chart{/}`. Scene: *Mirelle lays the chart over her desk, and Hale, who has climbed her stairs for the first time, reads the order aloud, and her pencil starts to move before he finishes.* Mirelle: *"Six wheels, six lights, and the order they must be held in. It is not a spell. It is a way of asking six spells to sing at once."* Sets `apex_unlocked` (the flag `spells.json` already reads). The chart stays in the pack. The two existing "cannot do it yet" lines (`magic_ui` `_help` and the `locked` option, ~lines 127 and 225) change to "the six wheels need a star-reader's order: ask in the Vigil." `NEWS`/`EXTRA_NEWS`: none (Mirelle has no `topic_menu`; `has_news("mirelle")` gains the unlock condition through `EXTRA_NEWS["mirelle"]`).
2. **Hearts.** Six materials `core_heart_<element>` (core, section 4) drop from ring-5 mobs (4 to 8%), elites (guaranteed), bosses (3 guaranteed per win) and vaults (the tables in sections 9 and 10).
3. **Grand Binding** (`data/spells.json` `craft.grand`): `{"gold": 500, "essence": 5, "cores": 2, "heart": 1, "weights": {"ultra": 0.40, "legendary": 0.45, "godlike": 0.15}}`. `spells.craft_missing/craft` also require and remove one `core_heart_<element>` for the chosen element when `heart` is set; `magic_ui._craft` lists it with the Heart named and the odds shown first. Expected per Godlike book: 6.7 bindings (6.7 Hearts, 33 Essences, 13 Cores, 3,300 gold). Six: 40 Hearts is the cost of the Grand Bindings for one set of six books only; every failed apex attempt loses the books, so **the real expectation is about 146 Hearts** for one success (arc's measurement, apex heat included), not 40. Hearts are the throttle by design (about 12 to 17 from first clears, 3 to 5 per boss call-back, more from the annexes).
4. **Apex heat** (`spells.json` `apex.heat` 0.10; flag `arc_apex_heat`): each failed attempt adds 10 points to the chance, reset on success; `chance = min(1.0, 0.10 + 0.10 x heat)`, so it is a sure thing after 9 failures. `magic_ui._apex` shows `10% + heat = N%` before the attempt. The failure refund (lose all six, get one Legendary back upgraded or downgraded) is the owner's and is NOT changed: see section 20.
5. **Quest.** None needed beyond `late_lending`. The unlock is the last beat of the Vigil's chain.

**Tests (`tests/test_arc.py`):** unlock conditions (each missing one), idempotent, chart stays; Grand Binding missing/consuming a Heart of the right element, odds shown, rarity distribution over 5,000 seeded draws; apex heat persistence and reset; existing apex tests still pass; `validate` clean.

---

## 13. Package `fin`: Dealer ring 5, gem codes, the Roll of Lenders, sims, docs

### 13.1 Dealer (`data/dealer.json`)

Add ring `"5"`: `{"gear_odds": {"epic": 10, "ultra": 40, "legendary": 50}, "relic_odds": {"epic": 15, "ultra": 40, "legendary": 45}, "socket_cap": "legendary", "bargain_cap": "legendary"}`. Append to `gear`: weapons `ff_lamp_pole`, `vg_astrolabe_rod`; armor `vg_nightcloak` (all Rare natives, forge feedstock). Update `notes` (it is validated as non-empty only, but the arithmetic must match the game): gem income over a whole game is now **about 169** (the old 93 plus M6's 76: 15 from five new `boss` first kills, 7 from four hooks, up to 4 from the two rolled bosses' band bonus (once each), 50 from the four codes); "Epic, Ultra, Ultra, Legendary for rings 1 to 4" gains "and Legendary for ring 5"; "a Legendary is only on sale in the last ring" becomes "in rings 4 and 5"; add: "Ring 5 is the first ring where Legendary is more likely than not (50%); the 28-gem price is the brake (a sixth of the whole game's gems). Bargains cap at Legendary because gems never buy Godlike. The ring-5 Dealer sits in the Frostfair once the Court's beacon is lit, moves to the Vigil once the Fair is lit, and is gone when the Vigil is lit."
**Run `tests/test_dealer.py` after the edit.** Adding three bases to the pool changes which base a seeded pick returns; any test that pins a specific ware must be updated to the new deterministic value (and only for that reason).

### 13.2 Codes (`python tools/make_code.py CODE GEMS "label"`)

Placeholders for the owner to rotate before release (do not commit anything but the hashes the tool writes):

| Code | Gems | Label |
|---|---|---|
| `LENDING` | 10 | Three old doors: the Hospice, the Reedlight and the Lampwrights' Deep |
| `THAW` | 15 | The Frostfair thaws |
| `VIGIL` | 15 | The Vigil is released |
| `QUENCH` | 10 | The Third Quench and the Long Quench |

### 13.3 Gem budget (one table, kept in `dealer.json` `notes`, `docs/V2-PLAN.md`, `tests/test_fin.py`)

| Source | Gems |
|---|---|
| First kills with the `boss` tag (engine, 3 each): `hos_vesper`, `rl_heron`, `lw_foreman`, `ff_lampmaster`, `vg_prior_eye` | 15 |
| Hooks: `hos_almoner` 2, `ff_ringmaster` 2, `vg_orrery` 2, `vg_chapel` mercy 1 | 7 |
| Band bonus, once per rolled boss (Roused 1, Ablaze 2): `ff_gems_band`, `vg_gems_band` | up to 4 |
| Codes (placeholders) | 50 |
| **New total** | **76** |

### 13.4 The Roll of Lenders (`areas/fin.py`)

`TOPICS["wizard"]`: "Ask about the Roll of Lenders" (after `completed`, and when the player holds at least one receipt or `ff_signal_seen` is set). Ysolde: *"I held the pen; he held the lamp. I wrote every receipt twice. I never wrote the word 'return'. I'm... not proud of that."* Then six lines, one per lender, each `<Lender>: <status>`, where status is "receipt in hand" when the receipt item is held, otherwise the lock's plain requirement:
- the Hospice: "behind the Shrine of the Moth, east. Light the waypost there."
- the Reedlight: "south of the Bog Lights, behind a fog bank. A Fire or Light book, equipped, will clear it."
- the Lampwrights' Deep: "a bronze door in the Crypt Stair. A Lamp Relic, socketed into something you wear."
- the Frostfair: "west of the North Gate, once the Court's beacon is lit" (lit: "thawed" when `ff_thaw`).
- the Vigil: "up the Signal Stair beyond the Frostfair, once the Great Lantern is lit" (lit: "released" when `vg_signal_sent`).
- the Court: "Pell has held it since. Ask her."
Sets `fin_roll_read`. `EXTRA_NEWS["wizard"]`: `ff_signal_seen and not fin_roll_read`. The old "Ask about the other places" topic is NOT edited.

### 13.5 Tools and docs

- `tools/sim_ring5.py`, `tools/sim_economy.py`: section 15.
- `docs/V2-PLAN.md`: milestones table M6 -> Done with a pointer; new section 5f "M6 as built" (the tables of sections 9 to 14 here); section 2.7 gains "as built"; section 5e "Legendary gear is only ever sold in the Court" -> "in rings 4 and 5"; OPEN DECISION 4 -> closed ("The Debt: see 5f"); section 3 table rows for smith upgrades and top-tier spells.
- `README.md`: the new tools, the package list, test counts. `version.json`: changelog entry (version bump is the owner's call).
- `tests/test_fin.py`: (1) every id in section 18 exists in the game data and no id appears in two kinds; (2) a scripted playthrough with gear granted: Court beacon -> Frostfair (posts, mini, Hobb with a forced roll, beacon) -> Vigil (key, mercy chapel, Eye, beacon) -> receipts -> letter -> flames -> Tamsin -> Godlike forging with a forced seed -> Long Quench in a fake clock -> apex unlock; (3) grep test: every `lock["msg"]` in the new files contains a noun naming where or how to get the requirement (it mentions an item, room, boss, book, building or the word "Dread"); (4) no group of more than two enemies in any new encounter table; every rolled boss has 5 flavour lines and `pron`/`place`; (5) no `hollow` enemy with `light` in `weak` among the new enemies; (6) each new `dealer: true` region has at least 3 seats.

---

## 14. Calibration targets (measured, not guessed)

### 14.1 Method (the contract between the data and `tools/sim_ring5.py`)

All numbers below were produced on 2026-11-01 by `lamplighter.sim` with the game's own suggested play, **three classes averaged** (warden, wayfarer, ashblade; weapon `saltsteel_saber` / `ashwood_rod`, armour `hauberk`, both at the stated rarity), 3 draughts, 3 strong draughts, 3 oil, the full lantern kit (shroud, trim, lens), Dread 0, n = 60 per class. The stand-in for a ring-5 boss is **the Cinder Queen with hp and atk both multiplied by k**, with k = (boss multiplier) x (0.5 + power/100), because the real bosses are Queen-shaped by design (same move kinds, a charge, three phases). Level 11 for area A, level 12 for area B (`ff` is "10-11", `vg` "11-12").

- **Builds:** Epic, Ultra, Legendary, Godlike (weapon + armour at that rarity); "Leg + 3 relics" = Legendary weapon with 3 Legendary relics (Edge for warden and wayfarer, Ember for ashblade); "God + 3" the same on Godlike; "+ armour relics" adds 3 Legendary Heart relics in the armour; "+ Quench x2.0 / x3.0" multiplies the weapon's `mult["dmg"]` by 2.0 / 3.0 (what `gear.rebuild` does with `inst["temper"]`).
- **Kits:** `none` = no spell books (the floor). `kit` = three equipped Epic books, **two on the fight's weak elements and one neutral** (the typical play). A good loadout is worth one to three gear tiers.
- **Boss multipliers (power 50):** area A boss = **Queen x1.45 = hp 1,115 / atk 67**; area B boss = **Queen x1.8 = hp 1,386 / atk 83**. Power scales both by `0.5 + power/100`. Builders tune the real bosses' hp and atk within +-30% (never moves, phases, elements or themes) until the stand-in's cells are reproduced within **+-8 points** on the p50 rows and **+-10** elsewhere, n >= 60.
- **Rules the cells encode:** plain Godlike must fall clearly behind by the Vigil's boss (p50 `kit`: 67%, `none`: 32%); stacking (relics, armour relics) recovers about half the gap (76 to 80%); a Quench of x2.0 recovers the rest (90%); x3.0 adds almost nothing at p50 but matters at Ablaze (p100 `kit`: 59%).

### 14.2 Area A boss (Hobb): Queen x1.45, level 11

**Kit** (Fire and Earth for Hobb, plus one neutral; the stand-in used Water, Ice, Shadow on the Queen):

| Power | k (x Queen) | Epic | Ultra | Legendary | Godlike plain | Leg + 3 relics | God + 3 relics | God + 3 + armour relics | ... + Quench x2.0 | ... + Quench x3.0 | God + Quench x2.0 alone |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 0.74 | 83 | 94 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| p25 | 1.09 | 46 | 71 | 86 | 96 | 91 | 100 | 100 | 99 | 99 | 99 |
| **p50** | 1.45 | **14** | **36** | **53** | **83** | **61** | **88** | **92** | **96** | **96** | **90** |
| p75 | 1.81 | 5 | 6 | 24 | 57 | 28 | 62 | 68 | 85 | 88 | 78 |
| p100 | 2.17 | 1 | 3 | 10 | 38 | 12 | 42 | 50 | 68 | 77 | 50 |

**None** (no spells; the floor):

| Power | k (x Queen) | Epic | Ultra | Legendary | Godlike plain | Leg + 3 relics | God + 3 relics | God + 3 + armour relics | ... + Quench x2.0 | ... + Quench x3.0 | God + Quench x2.0 alone |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 0.74 | 65 | 83 | 93 | 100 | 99 | 100 | 100 | 100 | 100 | 100 |
| p25 | 1.09 | 16 | 28 | 54 | 90 | 72 | 95 | 96 | 96 | 97 | 95 |
| **p50** | 1.45 | **1** | **6** | **16** | **51** | **36** | **69** | **74** | **89** | **89** | **83** |
| p75 | 1.81 | 0 | 1 | 3 | 31 | 12 | 44 | 52 | 73 | 77 | 61 |
| p100 | 2.17 | 0 | 1 | 1 | 15 | 3 | 24 | 29 | 50 | 61 | 33 |

Reading: at p50 with a typical kit plain Godlike wins 83% (the plan's "Godlike easy"), Legendary 53%, Ultra 36%, Epic 14% (the plan's late-boss ladder is 85 / 55-70 / 20-35 / 10 or less; the right books are worth tiers, so Ultra and Epic run a little kind). Faltering (p1) is a win for every Epic-and-up build with a kit. Ablaze needs stacking.

### 14.3 Area B boss (the Eye): Queen x1.8, level 12

**Kit** (Shadow and Earth for the Eye, plus one neutral):

| Power | k (x Queen) | Epic | Ultra | Legendary | Godlike plain | Leg + 3 relics | God + 3 relics | God + 3 + armour relics | ... + Quench x2.0 | ... + Quench x3.0 | God + Quench x2.0 alone |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 0.92 | 76 | 90 | 95 | 100 | 98 | 100 | 100 | 100 | 100 | 100 |
| p25 | 1.35 | 26 | 57 | 67 | 90 | 74 | 95 | 96 | 99 | 99 | 97 |
| **p50** | 1.80 | **7** | **13** | **34** | **67** | **36** | **76** | **80** | **90** | **91** | **82** |
| p75 | 2.25 | 1 | 4 | 9 | 39 | 10 | 44 | 53 | 69 | 79 | 52 |
| p100 | 2.70 | 1 | 2 | 6 | 23 | 6 | 30 | 38 | 46 | 59 | 32 |

**None:**

| Power | k (x Queen) | Epic | Ultra | Legendary | Godlike plain | Leg + 3 relics | God + 3 relics | God + 3 + armour relics | ... + Quench x2.0 | ... + Quench x3.0 | God + Quench x2.0 alone |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 0.92 | 44 | 63 | 83 | 98 | 96 | 99 | 99 | 99 | 99 | 99 |
| p25 | 1.35 | 3 | 15 | 34 | 69 | 49 | 84 | 90 | 92 | 94 | 89 |
| **p50** | 1.80 | **0** | **1** | **6** | **32** | **17** | **51** | **62** | **78** | **78** | **67** |
| p75 | 2.25 | 0 | 1 | 0 | 17 | 2 | 24 | 32 | 57 | 63 | 36 |
| p100 | 2.70 | 0 | 0 | 0 | 5 | 1 | 14 | 18 | 34 | 45 | 24 |

Reading: plain Godlike (67% kit, 32% none at p50) **falls behind**; relics and armour relics recover to 76-80% (51-62% none); Quench x2.0 recovers to 90% (78% none). At Ablaze (p100) only a quenched, stacked build has real hope (46-59% kit). Mercy (ceiling 55 / 35 / 20 after 2 / 3 / 4+ deaths) is unchanged and is what keeps the bottom rows from being a wall.

**Per-class floor.** `sim_ring5.py` also prints the three classes separately; no class may be below half the class mean in any cell with a mean above 30% (the ashblade lane in A is Fire and Earth; the wayfarer lane in B is Shadow and Earth; a class that loses its lane to a field or a resist must still have a second element on its book list).
**Lane test.** `sim_ring5.py --lane` equips, for each area, two Epic books on the area's strong elements (A: Fire, Earth; B: Shadow, Earth) vs two on its resisted elements (A: Ice, Water; B: Light, Fire) vs none, on the p50 boss and on the ordinary pair. Targets: the right lane lifts the mean win rate by **8 points or more**; the wrong lane must not help (never better than +2).

### 14.4 Ordinary fights (Court x1.3 in A, x1.45 in B; no spells; level 11 / 12; win% and, in brackets, health left on a win)

Measured with the Court's own mobs scaled, grouped the way the real tables are:

| Group | Area | Epic | Ultra | Legendary | Godlike |
|---|---|---|---|---|---|
| light pair (courtier + jester) | A x1.3 | 89 (52%) | 99 (61%) | 100 (65%) | 100 (79%) |
| | B x1.45 | 76 (50%) | 92 (58%) | 100 (63%) | 100 (74%) |
| single (gargoyle) | A | 50 (50%) | 63 (52%) | 82 (58%) | 100 (73%) |
| | B | 39 (50%) | 55 (51%) | 74 (56%) | 98 (72%) |
| pair (hound + knight) | A | 29 (43%) | 51 (51%) | 74 (52%) | 97 (67%) |
| | B | 11 (28%) | 33 (47%) | 59 (52%) | 94 (63%) |
| heavy pair (gargoyle + hound) | A | 8 (32%) | 29 (48%) | 57 (51%) | 88 (60%) |
| | B | 5 (34%) | 16 (47%) | 38 (50%) | 79 (55%) |

Targets (+-10): the recommended tier (Ultra in A, Legendary in B) wins an ordinary fight 55-100% with 45-60% health left; a heavy pair is a real cost; Godlike clears everything. With a kit the same table is **15 to 30 points higher** (measured on the Court mobs with Water / Ice / Shadow books: the Ultra pair goes 51 to 74 in A). Group sizes follow section 2.3 (at most 2; A at least 40% singles, B at least 55% singles).

### 14.5 Mini-bosses (Steward-shaped stand-ins; level 11 / 12; Epic / Ultra / Legendary / Godlike / Leg + 3 / God + 3)

| Fight | Stand-in | none | kit |
|---|---|---|---|
| Ringmaster (A) | Steward x1.6 hp / x1.55 atk = 720 / 51 | 22 / 44 / 71 / 92 / 84 / 98 | 56 / 73 / 86 / 97 / 89 / 99 |
| Great Orrery (B), right books | Steward x2.0 / x1.75 = 900 / 57 | 11 / 32 / 59 / 91 / 78 / 97 | 46 / 64 / 83 / 96 / 87 / 99 |

Targets +-10 points. The Orrery is also tested with a *wrong* loadout (Light, Fire and Water only: never the next stance's weakness): it must be 15 to 25 points lower than the right one, which is the point of its rotating weakness.

### 14.6 Extension side bosses (the base game's gear and levels; plan: "older areas get easier extensions")

| Boss | Stand-in | Target (3-class mean) | Measured anchor |
|---|---|---|---|
| `hos_vesper` | Antlered Mother x1.8 hp / x1.4 atk (288 / 15) | level 4, hunting spear: 90-97%, health left 40-50% | 97% (46% left) |
| `rl_heron` | Drowned Bishop x1.7 / x1.4 (340 / 20) | level 6, saltsteel saber: 85-95%, 45-55% left | 90% (50% left) |
| `lw_foreman` | Ore-Warden x2.8 / x1.4 (420 / 24; **built 420 / 21**) | level 7, saltsteel saber: 82-92%, 55-65% left | 89% (61% left) |

Ordinary extension mobs are the parent region's mobs x1.25 to x1.3; a group should cost 20-40% of health for the recommended gear.

### 14.7 Dread

Calibrations are at Dread 0 (as `sim_court.py` is). Ring 5 adds +6 per dark step (benighted +12); a fight adds about 10. The pressure valves in the data: a rest point every 3 to 5 rooms (`ff_fair_gate`, three posts, `vg_porters_lodge`, `vg_heliograph`, the annex waypost), Fairlight (-40), Nightcap (-60), cider (-20), honeycake (-15), the chapel mercy (-50), and lit rooms (-3 a step). Terrified (75+) hides ordinary enemies' next moves, not elites' or bosses'.

---

## 15. Simulators and commands

The new tools live in `tools/`, are pure stdlib, and import `lamplighter.sim` as `sim_court.py` does.

| Command | Output | Owner |
|---|---|---|
| `python tools/sim_ring5.py --area ff or vg or hos or rl or lw or all [--level N] [--n 60] [--kit none or kit or both] [--powers 1,25,50,75,100] [--lane] [--check]` | Every ordinary group of the area, both minis, the boss at each power, for the builds of section 14.1, three classes averaged (and separately with `--classes`). Fields apply (it passes `room=`); attune and rolled bosses use `powerroll.scaled`. `--check` exits 1 if a pinned cell of section 14 is outside its band. | `fin` |
| `python tools/sim_economy.py [--area ...] [--check]` | From the data files and encounter chances: gold, Hollow Cores, Rime / Vigil Glass and Hearts per casual hour (5 moves a minute, 1.7 minutes a fight, 20 fights an hour in A, 18 in B), the time to afford each forge tier, and the section 16 ledger. `--check` fails outside the ranges in 16.1. | `fin` |
| `python tools/sim_smith.py` | 10,000 Long Quench runs with pity: outcome distribution, expected re-quenches to x3.0, expected gold, calendar days (a session every 1.75 days); the expected Godlike gold and days (6.42 attempts, one per 24 h). | `late` |
| `python tools/sim_court.py`, `python tools/sim_power.py` | unchanged; must still run | |

Reference build function (as used for the tables; `sim.maxed` and `sim.win_rate` already exist):
```python
def build(cls, lvl, rarity, nrel=0, arel=0, spells=(), quench=1.0):
    def f():
        p = sim.maxed(cls, lvl, WEAPON[cls], "hauberk", rarity,
                      relics=[(RELIC[cls], "legendary")] * nrel, armor_relics=[("heart", "legendary")] * arel,
                      items={"draught": 3, "strong_draught": 3, "oil": 3},
                      lantern={"shroud": True, "trim": True, "lens": True}, spells=spells)
        if quench != 1.0:
            w = ITEMS[p.equipment["weapon"]]; w["mult"]["dmg"] = w["mult"].get("dmg", 1.0) * quench
        return p
    return f
# boss: powerroll.scaled("ff_lampmaster", p); fight: sim.win_rate([eid], sim.suggested, n=60, builder=build(...), room="ff_wintering")
```

---

## 16. Economy and hours

### 16.1 Gold per casual hour (the ranges `sim_economy.py --check` enforces; a model, to be confirmed by the tool)

Per fight = group gold + expected junk (`ff_fair_token` 60, `vg_star_plate` 90 and the rest sell at full value to Tallow / Odo).

| Place | Fights / h | Gold / h (target range) | Notes |
|---|---|---|---|
| Base rings | 15 | 150 | existing |
| Extensions (3) | 15 | 300 (+ about 0.4k of boss gold in all) | Rare gear, 3 gems per boss |
| Ember Court | 18 | 450 | existing |
| Area A, Frostfair | 20 | **1,600 - 2,100** | plus Hobb 600-750 x reward mult, vault ~0.9k |
| Area B, Vigil | 18 | **1,900 - 2,500** | plus the Eye 1,100-1,400 x reward mult, vault ~0.6k |
| Annexes (Fair Below, Waking Cellars) | 20 | x1.2 of their area | the post-beacon faucet; Hearts 2 to 3 an hour |
| Rent | | 63 / h across all buildings, cap 8 h a collection | about 320 per session |

**Ledger to the first Godlike (typical, about 16 hours to the recipe):** earned about 28k (fights 20k, rent about 8k); spent about 25k (weapon Rare to Legendary expected 10.0k, armour to Ultra 2.7k, trinket and relics 4k, buildings 3.5k, call-back fees 2.5k, materials bought 2k). The Godlike attempts (19.3k expected, one per 24 h because they take both anvils for a day) are paid from the annexes, rent and call-backs in the 9 to 11 days after the recipe. **Gold is the throttle until the first Godlike; Hearts are the throttle after.**

**Hollow Cores** are already cheap: a call-back costs `100 x ring` gold and a boss drops 1 to 3 guaranteed (ring 1: 100 gold per core; ring 5: about 500 gold for a boss with 2 guaranteed plus up to 3 from the roll). Do not add surcharges. A maxed build needs about 125 over its life.

### 16.2 Hours (casual: 4 sessions of 30 minutes a week)

| Stage | Hours | Cumulative |
|---|---|---|
| Base game (Wood, Saltmarsh, Underdeep, Lightwell) | 4.5 | 4.5 |
| Hospice 0.8, Reedlight 1.0, Lampwrights' Deep 1.2 | 3.0 | 7.5 |
| Ember Court | 2.0 | 9.5 |
| Frostfair (13 rooms, 5 locks, 3 posts, mini, Hobb) | 3.0 | 12.5 |
| Vigil (14 rooms, mini, mercy, the Eye) | 3.5 | 16.0 |
| Recipe turn-ins, forge waits, Godlike attempts, Long Quench set-up, Marit's stall and Hale's loft | 3.0 | **19.0** |

Fast player 14.5 h, thorough 22 h. The first Godlike arrives about 9 to 11 calendar days after the recipe (6.42 expected attempts, one a day); the Long Quench is a further 7 days; the apex is the open-ended tail. Knobs when a playtest misses the hours: encounter `chance` per room (+-0.05 is about +-6% of an area's time), the number of Lending Posts the gate needs (3 to 2), the forge gold, the annex chance. **Never tune XP or boss stats to tune hours.** XP is flat per kill and the cap is 12 (reached about the middle of the Frostfair), so ring-5 rewards are gold, materials, Hearts and gems.

### 16.3 "Never stalls" rules (each is a test in `tests/test_fin.py` or a package test)

1. At any moment the player has at least three independent things to do (a lock to open, a forge or quench timer, a shop upgrade, a call-back, a side objective).
2. Every timer is no longer than the gap between sessions except the Long Quench (7 days, opt-in, never blocks play).
3. Every scarce material has a gold-for-material valve (Odo: Rime 70, Vigil Glass 90, once the matching boss is dead).
4. Lighting a beacon never ends income: each ring-5 beacon opens an annex.
5. No gate depends on a lucky drop; quest items are `give_once` or on a floor behind no lost lock.
6. Death never wipes a key item; gold on hand is halved as always (the retention design's Counting-House bank is NOT adopted; section 20).

---

## 17. Cross-package contracts

Everything two packages must agree on. A package may rely on anything in its own row without asking.

### 17.1 Hook signatures (defined by `core`, used by all)

| Hook | Shape | Notes |
|---|---|---|
| `ENTER` | `{room_id: fn(g, first) -> bool}` | True = the event took over the room (no fixed fight, no encounter). Boss rooms return `powerroll.boss_scene(...)` (always True) until the boss flag is set, then False |
| `AFTER_FIXED` | `{flag: fn(g)}` | after a `fixed` fight is won |
| `UNLOCK` | `{(room_id, dir): fn(g)}` | the first time a lock is opened |
| `AFTER_BEACON` | `{region_id: fn(g)}` | runs AFTER the region's built-in text (core C8); keys used: `Ember Court` (ff), `The Frostfair` (ff), `The Vigil` (vg) |
| `AFTER_GAIN` | `{item_id: fn(g)}` | `late` registers the six receipt ids |
| `NPCS`, `STOCK`, `PRESENT`, `NEWS` | as `areas/__init__.py` documents | new NPC ids only |
| `TOPICS` | `{existing_npc_id: fn(g) -> [(label, handler(g))]}` | merged across modules; keys used: `corvin` (hos), `oskar` (rl), `brann` (lw, late), `hesk` (ff, vg), `orrin` (vg, late), `pell` (late), `tamsin` (late), `wizard` (fin) |
| `EXTRA_NEWS` | `{existing_npc_id: fn(g) -> bool}` | keys used: `hesk` (ff, vg), `orrin`, `brann`, `tamsin` (late), `wizard` (fin), `mirelle` (arc) |
| `SELLS` | `{npc_id: fn(g) -> [item ids]}` | `odo` (ff: `ff_rime`; vg: `vg_starglass`) |
| `PRICES` | `{item_id: gold}` | `ff_rime` 70, `vg_starglass` 90 |
| `RUMOURS` | `fn(g) -> [str]` | hos, rl, ff, vg |
| `OBJECTIVES` | `fn(game, add)`; `add(text, room_id, side=False)` | main objectives (`side=False`) only for the active chain stage |
| `BOSS_TIPS` | `{room_id: str}` | |
| `CHECK` | `fn() -> [errors]` | each area's CHECK asserts the no-hollow-light rule for its own enemies |
| `areas.give_first(g, iid, n=1)` | helper | once-ever gear reward, flag `got_<iid>` |
| `events.give_once(g, iid)` | existing | key items |
| `powerroll.boss_scene(g, eid, flag, back, on_win, intro=None, prologue=None, step_back_text=None)` | existing | `on_win(g, power)` |
| `npcs._invite_scene(g, building_id, who, ask, yes, again)` | existing | imported lazily inside functions |

### 17.2 Items shared between packages

| Item | Defined by | Read by | How the player gets it |
|---|---|---|---|
| `hos_receipt`, `rl_receipt`, `lw_receipt`, `ff_receipt`, `vg_receipt` | the area | `late` (Orrin, `AFTER_GAIN`), `fin` (Roll), area NPC topics | floor of the named vault room |
| `late_receipt_court`, `late_aldrics_letter` | `late` | `late`, `fin` | Pell topic; Orrin scene |
| `lw_quench_notes` | `lw` | `late` (Brann) | floor of `lw_rack_room` |
| `ff_given_flame`, `vg_given_flame` | `ff`, `vg` | `late` (Tamsin scene consumes both) | Marit after `ff_thaw`; Hale after `vg_signal_sent` |
| `vg_sixfold_chart` | `vg` | `vg` (Hale), `arc` (Mirelle) | floor of `vg_camera_obscura` |
| `ff_rime`, `vg_starglass` | `ff`, `vg` | `late` (forge.json, smith.json), building costs, `SELLS`/`PRICES` | mob drops, vaults, boss drops, Odo |
| `core_heart_fire/ice/water/light/shadow/earth` | `core` | `ff`, `vg` (drops), `arc` (Grand Binding) | drops, vaults, bosses |
| `ff_lamp_pole`, `vg_astrolabe_rod`, `vg_nightcloak` | `ff`, `vg` | `fin` (dealer.json gear pool) | Dealer, forge feedstock |

### 17.3 Flags: who sets, who reads

| Flag | Set by | Read by |
|---|---|---|
| `beacon_Ember Court` (engine) | existing | `ff` gate lock, `ff` region `dealer_after` |
| `beacon_The Frostfair` (engine) | `engine.light_beacon` | `vg` ladder lock, `vg` region `dealer_after`, `ff` annex hatch, `vg` objectives |
| `beacon_The Vigil` (engine) | `engine.light_beacon` | `vg` annex trapdoor |
| `lit_ff_midway`, `lit_ff_lamp_row`, `lit_ff_sculptors_row` (engine, `cmd_light`) | engine | `ff_great_gate` flags lock |
| `ff_signal_seen` | `ff` (Court beacon hook) | `ff`, `fin` |
| `ff_thaw` / `vg_signal_sent` | `ff` / `vg` `AFTER_BEACON` | Marit and Hale (flames), `fin` Roll, Hesk / Maeve / Orrin lines |
| `ff_lampmaster_dead`, `vg_eye_dead` | the boss scenes | Odo valves, invite topics, objectives |
| `ff_flame_given`, `vg_flame_given` | `ff`, `vg` | their own talk (idempotence) |
| `vg_chart_read` | `vg` (Hale) | `arc` |
| `late_letter_read`, `late_notes_shown`, `late_quench_done`, `late_quench_pity` | `late` | `late` |
| `godlike_recipe` | `late` (the Tamsin scene) | `forge.json` `needs_flag`, `quench.py` |
| `apex_unlocked` | `arc` (Mirelle scene) | `spells.json` `needs_flag` (existing) |
| `arc_apex_heat` | `arc` | `arc` |
| `fin_roll_read` | `fin` | `fin` |
| Town: `vg_almanac` built | `town` | `arc` (unlock), `vg` Hale |

### 17.4 Region and building keys

Region strings (exact, case-sensitive, they form the `beacon_<region>` flags): `The Moth-Saint's Hospice`, `The Reedlight`, `The Lampwrights' Deep`, `The Frostfair`, `The Fair Below`, `The Vigil`, `The Waking Cellars`. Buildings: `ff_fair_stall` (room `ff_stall`, plot lock on `hearth_stall` e, resident `ff_marit`), `vg_almanac` (room `vg_loft`, plot lock on `tower` w, resident `vg_hale`). No new building adds a forge slot.

---

## 18. The id register (all new ids, no collisions)

A test (`tests/test_fin.py`) loads this section's lists from the data and asserts each id exists in exactly one kind (room, enemy, item, npc, building, quest) and starts with its slug.

| Slug | Rooms | Enemies | Items | NPCs | Buildings | Quests | Flags set by this package |
|---|---|---|---|---|---|---|---|
| `core` | none | none | `core_heart_fire`, `core_heart_ice`, `core_heart_water`, `core_heart_light`, `core_heart_shadow`, `core_heart_earth` | none | none | none | `got_<item>`, `field_seen_<room>` |
| `hos` | `hos_path`, `hos_gate`, `hos_belfry`, `hos_orchard`, `hos_cloister`, `hos_refectory`, `hos_scriptorium` | `hos_pilgrim`, `hos_waymoth`, `hos_almoner`, `hos_vesper` | `hos_pilgrims_staff`, `hos_moth_mantle`, `hos_waylamp`, `hos_windfall`, `hos_belfry_key`, `hos_receipt` | none | none | none | `hos_almoner_dead`, `hos_vesper_dead`, `hos_scriptorium_open`, `hos_gems_almoner`, `hos_corvin_told`, `hos_corvin_vesper`, `hos_corvin_receipt`, `got_hos_corvin_gift` |
| `rl` | `rl_causeway`, `rl_sluice`, `rl_tower_foot`, `rl_lantern_room`, `rl_cottage`, `rl_oilhouse` | `rl_lampman`, `rl_heronling`, `rl_heron` | `rl_heronplume_coat`, `rl_keepers_pole`, `rl_lens_shard`, `rl_tower_key`, `rl_receipt` | none | none | none | `rl_fog_burned`, `rl_oilhouse_dead`, `rl_heron_dead`, `rl_oskar_spoke` |
| `lw` | `lw_door`, `lw_mess`, `lw_workshop`, `lw_gallery`, `lw_glassworks`, `lw_rack_room` | `lw_glass_ghoul`, `lw_lampling`, `lw_foreman` | `lw_lampwright_hammer`, `lw_apron`, `lw_pit_lamp`, `lw_lamp_blank`, `lw_receipt`, `lw_quench_notes` | none | none | none | `lw_door_open`, `lw_foreman_dead`, `lw_rack_open`, `lw_brann_told` |
| `ff` | `ff_frost_road`, `ff_fair_gate`, `ff_lending_tent`, `ff_midway`, `ff_skate_pond`, `ff_ice_cellars`, `ff_lamp_row`, `ff_wardens_booth`, `ff_carousel`, `ff_sculptors_row`, `ff_great_gate`, `ff_wintering`, `ff_signal_stair`, `ff_stall`, `ff_below_stair`, `ff_below_hall`, `ff_below_pool` | `ff_hawker`, `ff_skater`, `ff_horse`, `ff_ice_figure`, `ff_lamp`, `ff_below_sleeper`, `ff_ringmaster`, `ff_lampmaster` | `ff_rime`, `ff_fair_token`, `ff_cider`, `ff_fairlight`, `ff_wardens_key`, `ff_cellar_key`, `ff_receipt`, `ff_given_flame`, `ff_wintering_flame`, `ff_greatcoat`, `ff_lamp_pole` | `ff_dunmore`, `ff_marit` | `ff_fair_stall` | none | `ff_signal_seen`, `ff_thaw`, `ff_ringmaster_dead`, `ff_lampmaster_dead`, `ff_gems_ringmaster`, `ff_gems_band`, `ff_met_hobb`, `ff_marit_met`, `ff_marit_told`, `ff_marit_hobb`, `ff_flame_given`, `ff_gift_day`, `ff_hesk_told` |
| `vg` | `vg_ladder`, `vg_porters_lodge`, `vg_great_court`, `vg_library`, `vg_heliograph`, `vg_orrery_hall`, `vg_dormitory`, `vg_reckoning_room`, `vg_mirror_gallery`, `vg_camera_obscura`, `vg_chapel`, `vg_lens_cupboard`, `vg_lens_stair`, `vg_eye`, `vg_loft`, `vg_cellar_stair`, `vg_cellar_hall`, `vg_cellar_cells` | `vg_brother`, `vg_sentinel`, `vg_glare`, `vg_star`, `vg_blind_spot`, `vg_cellar_dead`, `vg_orrery`, `vg_prior_eye` | `vg_starglass`, `vg_nightcap`, `vg_clear_draught`, `vg_star_plate`, `vg_lens_key`, `vg_receipt`, `vg_given_flame`, `vg_sixfold_chart`, `vg_unsleeping_eye`, `vg_astrolabe_rod`, `vg_nightcloak` | `vg_tick`, `vg_hale` | `vg_almanac` | none | `vg_orrery_dead`, `vg_eye_dead`, `vg_obscura_open`, `vg_brother_slept`, `vg_chapel_done`, `vg_gems_chapel`, `vg_gems_orrery`, `vg_gems_band`, `vg_met_eye`, `vg_hale_met`, `vg_hale_slept`, `vg_flame_given`, `vg_chart_read`, `vg_signal_sent`, `vg_hesk_told`, `vg_orrin_told` |
| `late` | none | none | `late_receipt_court`, `late_aldrics_letter` | none | none | `late_lending` | `late_letter_read`, `late_notes_shown`, `late_quench_done`, `late_quench_pity`, `godlike_recipe` (existing name) |
| `arc` | none | none | none | none | none | none | `arc_apex_heat`, `apex_unlocked` (existing name) |
| `fin` | none | none | none | none | none | none | `fin_roll_read` |

Files with new names: `lamplighter/quench.py`, `lamplighter/data/smith.json`, `lamplighter/data/attach/{hos,rl,lw,ff,vg}.json`.

**Existing ids this spec relies on (all verified present in the code as of this date):** rooms `moth_shrine`, `bog_lights`, `crypt_stair`, `mine_hall`, `reedways`, `gate`, `hearth_stall`, `tower`, `hall`, `smithy`, `ember_smithy`; npcs `orrin brann tamsin pell corvin oskar hesk maeve wizard mirelle joss odo tallow`; enemies `wisp tallow_ghoul crawler antlered_mother drowned_bishop starsteel_golem cinder_steward cinder_queen` (as stand-ins and, for the first three, in encounter tables); items `oil honeycake strong_draught firepot smokebomb tonic hollow_core hollow_dust rootwood saltstone slag cinder essence_fire essence_ice essence_water essence_light essence_shadow essence_earth relic_pulse relic_lamp pearl`; flags `queen_dead`, `completed`, `steward_dead`, `lit_moth_shrine`, `beacon_Ember Court`; functions `events.give_once`, `powerroll.boss_scene`, `powerroll.scaled`, `npcs._invite_scene`, `npcs.line`, `town.is_built`, `town.is_invited`, `town.invite`, `dealer.today`, `dealer.room_for`, `navigation.find_path`, `spells.make_book`, `spells.element_of`, `gear.make`, `gear.give`, `gear.is_instance`, `gear.socketed`, `gear.rebuild`, `gear.make_loaner`, `forge.start/collect/update/free_slots`, `ui.menu`, `ui.confirm`, `ui.sweep`, `ui.pause`, `Game.award_xp`, `Game.set_quest`, `Game.give`, `Game.fight`, `Game.add_dread`.

---

## 19. Acceptance (integration gates, after everything merges)

1. `python tools/validate_content.py` is clean, reports 111 rooms, and `areas.check()` is clean.
2. `python -m unittest discover` passes (632 existing + each package's new file), run time within 2x of today's.
3. `python tools/fuzz.py 200 2000 0`: 0 crashes, reaches 111/111 rooms.
4. The bots still finish 17 of 18 on seeds 30 to 35 (ring 5 is optional).
5. `python tools/sim_ring5.py --area all --check` and `python tools/sim_economy.py --check` pass (section 14 and 16.1 bands).
6. The scripted playthrough in `tests/test_fin.py` (section 13.5) passes, including a Long Quench in a fake clock and the apex unlock.
7. Every lock `msg` in the new files names what it needs and where to get it (grep test).
8. Quality parity with the Court: every room has `features`, every new enemy a `desc`, every heavy or charge move a `tell`, every rolled boss 5 flavour lines.
9. A save made before M6 (use `tests/fixtures`) loads, the new rooms have their floor items, and the old story state still opens the Frostfair after the Court's beacon.

---

## 20. Owner-level decisions made here (please review) and risks

**Decisions the owner may want to veto**

1. **Forge prices retuned** (Epic to Ultra 900 to 600; Ultra to Legendary 3,000 to 1,500; Legendary to Godlike 12,000 to 3,000; fewer slag and saltstone). Odds, pity and heat are untouched. Without this a Godlike weapon is 77k gold of expected cost. A Godlike attempt now needs **two forge slots** (Brann's anvil and Tamsin's), so the Ember Smithy becomes load-bearing, and needs Rime and Vigil Glass from both new areas.
2. **Level cap stays 12** (lore's cap 14 and a seventh spell slot were dropped).
3. **One shared ring-5 Dealer.** He sits in the Frostfair once the Court is lit, moves to the Vigil once the Fair is lit, and leaves for good with the Vigil. Ring 5 sells **Legendary 50%** (previously Legendary was only sold in the Court at 20%); gems still never buy Godlike; the 28-gem price is the brake.
4. **`of_ruin` split:** the +5% damage weapon affix is now `of_havoc` (the curse keeps `of_ruin`).
5. **Gems:** about 76 new in the whole game (base game ~93), band bonuses once per boss, four placeholder codes the owner should rotate.
6. **The Long Quench:** Godlike weapons only, 9,000 gold, 7 real days, x2.0 / x2.5 / x3.0 at 45 / 35 / 20 percent with pity, keeps the better result, never destroys. The lore design's cheaper Honed and Tempered rungs were dropped (they compress the Legendary-to-Godlike gap).
7. **Apex supply:** Hearts, a Grand Binding craft tier (15% Godlike book) and apex heat (+10 points per failure). The owner's failure rule (lose all six, get one Legendary back) is **not** changed and is harsh; a softer refund is the next lever if the chase proves too long.
8. **Story canon:** Aldric borrowed six flames fifty years ago; Corvin was the Hospice's lay-brother; Oskar's brother Ansel kept the Reedlight; Corm was Brann's grandfather and a Lampwright; Hobb is Marit's husband; the Court's own "a hundred years" lines are left alone. Both ring-5 bosses are people (Hobb; the Prior inside the Eye) and both fights end in release.
9. **Core scope added beyond the lore design:** room damage `field`, enemy `attune` (rotating weakness), and the lock kinds `all`, `dread`, `flags`, `relic`. They are what make spells matter beyond weak/resist tables; each is a few lines and fully tested in core.
10. **Annexes** (`The Fair Below`, `The Waking Cellars`): small unlit regions opened by each beacon, `dealer:false`, so income and Hearts never die when an area is lit.

**Not adopted (and why):** the retention design's Counting-House bank (death halves gold on hand as designed; not a stall at these balances), a third smith and three-smith Godlike (two anvils is enough and avoids a third resident), its five ledger leaves (the six receipts do the same job with the owner's tone), the Mirror boss and Shadow Peddler / Veil / Prism upgrades (new systems), `quest`/`oil`/`elements`(six) lock kinds (not needed), level-14, and the mechanics design's different story (frozen Keepers, Orrin's shadow) which contradicted Orrin's established arc.

**Risks**

1. **core-a is a hard dependency** for every package. It is small; it should be built first and reviewed first.
2. **Boss move shapes differ from the Queen's**, so the stand-in stats need a sim pass: budget two tuning iterations per boss.
3. **`tests/test_dealer.py` pins:** adding three bases to the Dealer pool and a ring changes seeded picks; update pinned wares only for that reason.
4. **`topic_menu` redraw:** area topic handlers print inside the "You: ..." screen; keep them short or end with `ui.pause()` if they print more than a screen.
5. **Lock bypass:** re-run the reachability check from every entrance after any room edit (the graphs here were checked by script for neighbour squares, two-way exits, unique positions and reachability, and by reading for single locked entrances for `ff_wardens_booth`, `ff_ice_cellars`, `ff_wintering`, `vg_lens_stair`, `vg_eye`, `vg_camera_obscura`).
6. **Saves:** only free-form `flags`, two optional forge-job keys, one optional gear-instance key, and new town buildings; `savecheck` is extended for the first two; core C9 fixes room items for old saves. SAVE_VERSION stays 2.
7. **Old saves and the ring-5 gate:** the Frostfair opens on `beacon_Ember Court`, which a Wizard rewind never clears; the extensions open on `lit_moth_shrine`, an equipped book, and a worn relic, none of which a rewind clears.
8. **The map.** `map world` lists regions by ring, so the two annex regions (and the other new ones) appear there before the player can reach them; this is accepted (the world map already lists the Court from the start).
9. **Dread:** ring-5 areas are calibrated at Dread 0; a player arriving Terrified (+20% damage taken) will find them harder. The rest points and valves in 14.7 are the mitigation; a Dread-aware sim column is a follow-up.
