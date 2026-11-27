# The Last Lamplighter v2: Plan

Working title: *The Last Lamplighter: Hollowmere Reborn* (placeholder).
Everything marked **TUNE** is a starting number to be set by simulation. This document is the single source of truth. When the owner has a new idea, it goes here.

---

## 1. Vision

A text RPG for the terminal that lasts a couple of months of casual play (30 minutes, 4 times a week: roughly **15 to 20 hours**), and **keeps growing**: new, harder areas arrive over time, older areas get easier extensions, and a finished world stays open to replay.

- **Hollowmere is lit and safe.** It is a free home base, and it **grows** as survivors from the dark areas move in.
- **Around it, dark areas in rings by difficulty.** You push the dark outward: find a place's remnants, rescue its survivors, beat its boss, relight its beacon.
- **Loot is a gamble you plan for.** Common to Rare is easy. Epic and above come from the forge: gold, waiting time, not guaranteed, revealed with a colour sweep.
- **Power compounds.** Damage is multiplied by gear, relics and affixes. The best builds *stack*.
- **Dread** is the second resource after lantern oil.

## 2. Design decisions (the owner's vision, consolidated)

### 2.1 Town, builder and residents
- Hollowmere is always safe. It has a **home** (bed, stash), a **market**, a tavern, a forge and more, and it expands.
- **Survivors** found in the dark areas can be invited to move in. Each opens a business with a real job. A second survivor per area can stay behind and run an **outpost** (rest point, relic anchor, small shop). A few survivors give a choice of where to live.
- **Building costs materials and gold, and takes time.** Materials drop from monsters and bosses. A **Builder** constructs buildings over time, which can be sped up with gems. When a resident moves in, **you get paid**: rent builds up while you are away (capped) and is collected at home.
- Players can trade or gift any item (see 2.12). Later, friends can pay the builder for their own plot (see section 8).

### 2.2 Areas and locks
- Hub and spoke: rings by difficulty around the town. The map shows the **recommended gear tier** for each area.
- **Lighting an area** = beat its boss + relight its beacon. It then becomes safe: no random fights, a rest point, a relic anchor.
- Locks always say **exactly what they need**. Lock types: boss key, riddle phrase, relic-attuned door, element door, timed door, reputation door, companion door, stat check, vault, and **vacant plot** (needs a building).
- v1's three regions become rings 1 to 3. Rings 4 and up are new.

### 2.3 Loot, rarity and the forge
| Tier | Symbol | Colour | Source |
|---|---|---|---|
| Common | (none) | white | Drops, shops |
| Uncommon | ◇ | green | Drops, shops |
| Rare | ◆ | blue | Drops, shops, chests |
| Epic | ◆◆ | purple | Forge (a few unique quest rewards) |
| Ultra | ◈ | magenta | Forge |
| Legendary | ✦ | gold | Forge |
| Godlike | ✦✦ | rainbow | Forge, plus a recipe quest and multiple smiths |

- Every tier has a symbol *and* a word, so colour-blind players can read it.
- Forging: odds shown up front, a **heat meter** (pity) raises the chance after failures, a failed attempt **never destroys** the base item and refunds part of the materials. **The reveal** sweeps through the rarity colours, slows, and lands. Enter skips it.
- Starting odds (TUNE): Rare to Epic 35%, Epic to Ultra 20%, Ultra to Legendary 10%, Legendary to Godlike 2%.
- Waiting time: real-time timers that also tick down with steps taken ("both" is the working default); gems speed them up.
- Items: base type + material + 0 to 3 affixes + 0 to 3 sockets. Legendary and Godlike items are named and one of a kind, with lore and a use counter. Weapons level up from use.

### 2.4 Multipliers and the power curve  *(built)*
- Damage = base x all multipliers. Item `mult` keys: `dmg`, `phys`, `fire`, `light`, `heal`. They multiply with each other.
- **Base game target:** a standard Godlike weapon with no extras beats every boss in the base game.
- **Future areas** get harder until a plain Godlike falls behind. A **maxed weapon is Legendary or Godlike with several Legendary relics and multipliers on top.** Each new area's bosses are tuned to the *stacked* power a player there should have.
- Balance tools must test builds, not single items.

### 2.5 Relics
- Relics socket into gear. Types: spell relics, passives, triggers, cursed (strong with a drawback).
- Common relics can be bought. **Rare versions need boss loot plus the forge.** Godlike relics are never sold. Fusing two of the same relic upgrades it; matching relics give set bonuses.
- **The Homecoming Charm** is the first relic *(built)*: recall to town, return to a place you rested. Uses recharge when you rest. A resident can upgrade it.

### 2.6 Spells  *(later: M3 and on)*
- A **Magician** lives in town. Spells come from **spell books**, which are **crafted** from items dropped by monsters and bosses, or **bought** with gold, gems or from the Darkness Dealers. Books use the rarity ladder and the same kind of chances as weapons.
- **Slots:** one at the start, more as the character levels up (every level or every couple).
- **Combining books** (by chance). Same element and high tier can give a better version (two Ice books can give a Godlike Ice). Mixed elements can give a different element, possibly a lower tier (Legendary Fire + Legendary Ice might give an Ultra Water). Results can be combined again.
- **Top spells must be combined.** The strongest needs one Godlike book of every element and has about a **10%** chance. On failure (about 90%) you get one of the Legendary books back slightly upgraded, or one book returned downgraded to Legendary.
- Built **later**, when areas exist that need the top spells.
- **As built (M6, section 5f):** the apex stays the owner's recipe (six Godlike books, about 10%, the same failure rule) but now has a way in and a supply: the Vigil's Sixfold Chart unlocks it (Hale reads it aloud, Mirelle copies the order), the six **Hearts** are the new material, the **Grand Binding** craft tier (500 gold, 5 Essences, 2 Hollow Cores and one Heart; 40% Ultra, 45% Legendary, 15% Godlike) is how Godlike books are made in numbers, and **apex heat** adds 10 points to the chance after each failed attempt. The honest cost of one success is long: about 146 Hearts counting the books lost to failed attempts (the spec's first estimate, 40, was for one set of six books only), which is the open-ended tail the owner asked for; a softer failure refund is the next lever if it proves too long.
- Rules learned from the Flare: every spell has a cost, cooldown or limit; enemies get **element weaknesses and resistances** so different spells matter; show odds before a combine; keep a recipe log.

### 2.7 Weapon upgrades (the smith)  *(later)*
- A hired smith upgrades weapons. The top tier takes **up to a week** of real time, costs a lot of gold, and adds a **2x to 3x multiplier or more** on a Godlike weapon. The result is **not guaranteed** to be as good as hoped.
- **Loaner weapon:** the same base weapon with a **20% damage penalty**, stated on the item, while the smith works.
- Late-game and game-changing; built when areas demand them.
- **As built (M6, section 5f): the Long Quench.** Godlike weapons only, 9,000 gold plus 6 Hollow Cores, 8 Rime, 8 Vigil Glass and 20 Tallow Slag, seven real days (or 5,000 steps), a 20% loaner meanwhile. The outcome is x2.0 (45%), x2.5 (35%) or x3.0 (20%) on all of the weapon's damage, with pity (+10 points of x3.0 per result below it, capped at 60%); it never destroys and never goes below x2.0, and a re-quench keeps the better result. Gems skip at most two days. It needs the Godlike recipe and both smiths at the anvil (the Ember Smithy).

### 2.8 Boss power roll  *(built in M4, see section 5d)*
- Late and optional bosses roll **power 1 to 100** each spawn. Shown as flavour text; free retreat. Higher roll = better rewards.
- As built: five bands (Faltering, Subdued, Whole, Roused, Ablaze); health and damage scale by 0.5 + power/100, so the whole range is about two tiers of gear.
- **Mercy:** after 2 deaths to a boss its next roll's ceiling drops. **Story bosses cap their roll.**
- Targets for late bosses at a mid roll: Godlike 85%+ first-attempt win, Legendary 55 to 70%, Ultra 20 to 35%, Epic 10% or less.

### 2.9 Dread  *(built in M2)*
A 0 to 100 meter that rises in the dark and falls in light. Fear sharpens you but makes you shaky.
| Dread | Tier | Effect |
|---|---|---|
| 0 to 24 | Steady | none |
| 25 to 49 | Uneasy | +5% damage, -5 dodge |
| 50 to 74 | Afraid | +12% damage, +10 crit, -10 dodge, **you take +10% damage** |
| 75 to 99 | Terrified | +20% damage, **you take +20% damage**, healing -25%, ordinary enemies' next moves hidden |
| 100 (in a fight) | Consumed | Hollowing for 3 rounds: +40% damage, 25% chance each turn to lash out at a random enemy. Then a collapse: Dread falls to 60 and you are Shaken (-20% damage) until you rest. |
- Gains: each step into a dark room (+2 in ring 1, rising with the ring), each combat round in the dark, entering an unbeaten boss's room. Benighted doubles it. A companion cuts gains by 25%.
- Losses: lit rooms -3, a hot meal -15, resting or arriving in town resets it.
- Never kills you. Option: cosmetic only. Hunger only as an optional Survival mode, later.

### 2.10 Gems, codes and Darkness Dealers
- **Gems** come from redeemable codes (`NEW` for new players, milestone codes for new areas) and trickle in through play (first boss kills). Codes are checked locally against hashes, once per save.
- Gems speed up building and forging. **Darkness Dealers** (later, after M3) appear only in the dark and sell strong gear with relics already socketed, each with a **bargain** (power at a cost). They restock by timer or for gems. Gems never buy Godlike. **The gem economy as built:** about 169 gems over a whole game (the base game's 93 plus M6's 76, section 5f).

### 2.11 Longevity and the finished game
- After the ending, **the world stays open**. You return home and can keep playing.
- The **Wizard's Shop** opens after the story. For gold the wizard can **call back a defeated boss** to fight again, or **rewind the story** to an earlier chapter (keeping your gear and level) so the story can be replayed while waiting for updates.
- New harder areas arrive over time, plus extensions to older, easier areas.
- The Crown ending is a true ending: reload your last rest to continue.

### 2.12 Trading and gifting *(owner's decision)*
- **Any item of any rarity can be traded or gifted** if both sides accept. Friends are expected to be at similar levels, and the real endgame is stacking, so a gifted Legendary does not break the game. Safeguards: unique item ids so nothing can be duplicated, and both sides confirm.

### 2.13 Update command  *(M5, built)*
`update` reads a `version.json` from the project's GitHub repo, shows the changelog, backs up saves, downloads the new code over HTTPS, replaces code only, and migrates saves. Saves live outside the game folder.

---

## 3. Built now vs later

| Idea | When | Why |
|---|---|---|
| Multipliers | **Done** | Needed by everything |
| Practice fight, hint, travel, map, suggestions | **Done** | Clarity |
| Dread | **M2 (now)** | Needs only combat and movement |
| Home, stash, Market Row, Homecoming Charm | **M2 (now)** | Pure game logic |
| Builder, materials, timers, rent, residents | **M2 (now)** | Pure game logic; gives the town growth |
| Gems and redeem codes, build speed-ups | **M2 (now)** | Offline; the speed-up gives gems a use |
| Post-game world, Wizard Shop (rewind, call back bosses) | **M2 (now)** | Pure game logic |
| Rarity names and symbols on items | **M2 (now)** | Display only |
| Forge, rarity rolls, colour-sweep reveal, sockets | M3 | Big system; needs items to have rarity first |
| Spell books, Magician, combining | M3 and after | Needs the forge's rarity engine |
| Weapon upgrades with a week-long timer, loaner | M3, **top tier done in M6** | The Long Quench (2.7) arrived with the first area that needs it |
| Boss power rolls | **M4 (done)** | Needs the gear curve |
| Darkness Dealers | Prototype in M4, **done in M5** | Sells rolled gear with relics |
| `update` command | **Done** (updates come from `kidorange125-star/lamplighter-v2`) | Tested offline and against the real repo |
| New rings, area extensions | **M6 (done)**; more later | Three extensions, two ring-5 areas, two annexes (section 5f) |
| Online: friends, trading, co-op, shared plots | Track O, after M5 | Needs a server |
| Top-tier spells, 2-3x smith upgrades | **M6 (done)** | The apex unlock, Hearts, the Grand Binding and the Long Quench (section 5f) |

## 4. Milestones

| # | Milestone | Status |
|---|---|---|
| M0 | Setup: data-driven content, validator, saves outside the game folder, tests, simulators, full-game bot | **Done** |
| M1 | Clarity and combat: objective line, hint, travel, map, suggested-move menu, Flare cooldown, practice fight, multipliers | **Done** |
| M2 | **Hub and town growth:** Dread, home and stash, Market Row, Homecoming Charm, builder with materials and timers, rent, residents, gems and codes, post-game and Wizard's Shop, rarity labels | **Done** (see section 5) |
| M3a | **Loot and forge:** rolled gear instances, the forge with odds, heat (pity) and the colour-sweep reveal, loaner weapon, timers, sockets and relics, Hollow Cores | **Done** (section 5b) |
| M3b | **Spell books and the Magician** | **Done** (section 5c) |
| M4 | Vertical slice: **the Ember Court**, one new area end to end, boss power rolls and mercy, element door, beacon, a resident that adds a forge slot, a Dealer prototype | **Done** (section 5d) |
| M5 | Darkness Dealers in full, `update`, save migrations in practice | **Done** (section 5e) |
| M6 | **The Lending:** the six-lender debt story, three area extensions, two ring-5 areas with annexes, the Third Quench, two-slot Godlike forging, the Long Quench, the apex unlock, the ring-5 Dealer, gem codes, the Roll of Lenders | **Done** (section 5f; spec in `docs/M6-SPEC.md`) |
| M7+ | More rings and areas, further extensions | Not started |
| M10 | Retention: contracts, delves, bestiary, Dark Ranks, weekly boss, trophy hall | Not started |
| M11 | Balance and polish | Not started |
| Track O | Online (see section 8) | Not scheduled |

## 5. M2 progress

**Built** (all tested; 144 tests, and the fuzzer has played 500+ random games with no crash):
- **Dread:** meter, tiers, damage dealt and taken, hidden moves when terrified, Hollowing and the collapse, meals that calm you, a cosmetic-only option. Measured: moderate Dread is a small edge, high Dread costs health.
- **Home and stash** (west of the Guild Hall), **Market Row**, **Builder's Yard**, three **vacant plots**, and the **Wizard's Shop**.
- **Homecoming Charm** (from Orrin): `recall` home, `return` to where you last rested or relit a waypost. Recharges on rest.
- **Builder:** Joss builds Hearth Stall, Salvage Stall and Strongroom for gold and materials. Materials drop from monsters and bosses (rootwood, saltstone, slag). Builds finish by real time or by steps walked, whichever comes first; gems finish them at once.
- **Residents:** Corvin (hot meals, potions), Odo (buys parts, sells materials), Dagna (bigger stash, stronger charm). They are invited out in the field, move in when built, and pay **rent** (up to 8 hours' worth, collected at home or the yard).
- **Gems and codes:** `redeem NEW` (30 gems), `redeem FIRSTLIGHT` (40). First kill of each boss gives 3 gems. New codes are made with `tools/make_code.py`.
- **After the ending the world stays open** (except the Crown ending). The Wizard's Shop can **call back a defeated boss** or **rewind the story** (keeping gear, level and town), with a backup save first.
- **Rarity** names and symbols on items (Common to Godlike), in the pack and shops.

**Not yet (waiting on later milestones):** the forge and the colour-sweep reveal, spell books and the Magician, smith upgrades and loaner weapons, Darkness Dealers, boss power rolls, the `update` command, and online play.

## 5b. M3a: loot and the forge (built)

- **Gear instances** (`lamplighter/gear.py`): a forged item is its own object with a rarity, affixes, sockets and relics. It is registered as an item, so the pack, shops, stash and combat treat it like any other.
- **The forge** (Brann; `forge` command or *Talk to Brann*): raise **Rare and better** gear or a relic one tier. Odds are shown first. **Heat** (pity) adds 4% per failure and a full bar is a sure thing. A failure **destroys nothing** and refunds half the materials. The result is revealed with the **colour sweep**. Cost is gold, materials, and **Hollow Cores** (dropped by every boss) from Epic up. Time is real minutes **or** steps walked, whichever comes first (the owner said either is fine); gems hurry it. Godlike needs a recipe, which cannot be found yet.
- **Loaner:** the weapon you hold is replaced by the same weapon at its current rarity and affixes, 20% weaker (stated on the item), until the forge is done.
- **Relics:** five types (Ember, Lamp, Edge, Heart, Pulse), each a multiplier that scales with rarity (+4% Common to +35% Godlike). Sockets by rarity: Rare 1, Epic 1, Ultra 2, Legendary 3, Godlike 3. Tallow sells Common relics; the forge improves them with Hollow Cores. Taking a relic out loses nothing.

### Calibrated power curve (`python tools/sim_power.py`)
Level-8 Wayfarer, the game's suggested play, win rate against the final boss scaled up. The scale stands in for tougher future areas.

| Build | Final boss x1 | Late boss x2.5 | Future x3 | Future x4 |
|---|---|---|---|---|
| Rare (what the base game gives) | 99% | 1% | 0% | 0% |
| Epic | 100% | 14% | 1% | 0% |
| Ultra | 100% | 34% | 10% | 0% |
| Legendary | 100% | 57% | 28% | 0% |
| Godlike, plain | 100% | 80% | 70% | 26% |
| Legendary + 3 Legendary relics | 100% | 78% | 57% | 16% |
| Godlike + 3 Legendary relics | 100% | 91% | 70% | 42% |
| Godlike + 3 relics + armour relics | 100% | 91% | 72% | 49% |

This matches the design. Against a late boss, Epic is very hard, Ultra hard, Legendary winnable and Godlike easy. A plain Godlike beats the whole base game, then falls behind as areas get tougher, so stacking relics and multipliers is what keeps you ahead. Every tier is 1.4x the stats and 1.2x the weapon multiplier of the one below.

## 5c. M3b: spells (built)

- **Six elements:** Fire, Ice, Water, Light, Shadow, Earth. Every enemy is weak to some and resists others (shown on the combat board). A spell it is weak to hits 50% harder; one it resists, half as hard. The game never suggests casting into a resistance.
- **Spell books are items** with the rarity ladder. Common books are plain stackable items; better ones are one-of-a-kind. Each element has a spell: Firebolt (burns), Frost Lance (chills: the target hits softer), Tide Surge (all enemies, and cleanses you), Radiance (blinds; Hollows take double), Soul Drain (heals you), Stone Ward (a lasting shield).
- **Casting** costs focus and has a cooldown, and scales with Will and level, so every class can cast and casters cast best. Keys `S1`, `S2`... in a fight (or the spell's name). Spell slots: 1 at the start, then at levels 3, 5, 7, 9 and 11. One book per spell may be equipped. `spells` equips books anywhere.
- **The Magician** (Mirelle, west of the Chapel of the Ember): lends you a first book matching your class, equips, **crafts** books (bind 3 Essences for a Common/Uncommon/Rare roll; a refined binding with a Hollow Core can give Epic or Ultra), **sells** books (Common for gold; Uncommon and Rare for gems), **combines** books, and keeps the **recipe log**.
- **Essences** drop from monsters and bosses by theme (wolves: Shadow, plants: Earth, the marsh: Water, tallow things: Fire, and so on).
- **Combining** two books, always with the odds shown first. Same element: it may rise a tier (35% for two Epics, falling as the tier rises, and less if one book is much weaker), stay, or slip one. Two Legendary Ice books can become a Godlike Ice. Different elements make a third (see the log), usually a tier lower; discovering a recipe records it. Both books are always used up.
- **The apex spell, Cataclysm** (all elements, hits everything, ignores weakness): one Godlike book of every element, **10%** chance. On failure all six are lost but you get either a slightly stronger Legendary book (60%) or one book back brought down to Legendary (40%). The recipe is built but **locked** (`apex_unlocked`): it is saved for the areas that need it.
- Simulated balance (`tools/sim_report.py`-style, against the Hollow King at 2x): two Common spells lift an Ashblade from 0% to 52% and a Wayfarer from 32% to 42%; three Legendary spells reach 57% and 65%. Spells help every class, help casters most, and never take over, because focus and cooldowns limit how often you cast.

## 5d. M4: the Ember Court, the vertical slice (built)

The first new area, built end to end as the quality gate before more rings. It sits beyond the North Gate behind a bar of cold iron that opens only when the long night ends (the story is finished): the world stays open afterwards, and this is what it opens onto.

**The place.** 13 rooms (`rooms/ember_court.json`), ring 4, levels 8 to 10, gear Epic to Ultra. A burned noble house whose court never stopped dancing: Cinder Road, the Court Gate (outpost), Watchtower, Ruined Chapel (the Dealer), Grand Hall, Burnt Garden, Ballroom, Portrait Gallery, Steward's Hall, Throne Room (beacon), Great Kitchens, Court Forge, Cellars (the vault). Enemies are built around the elements: hounds, knights, gargoyles and the Steward are weak to Water and Ice and shrug off Fire, so the Ashblade's Firebolt stops being the answer and the spell system has to be used.

**Locks, each stating exactly what it needs.** The road from Hollowmere (story gate: `flag`), the throne room (the Crown Key, dropped by the Steward), the cellar stair (a new **element door**: a Water or Ice book must be *equipped*, not just carried; once opened it stays open via `remember`), and a **vacant plot** behind the Drowned Moth for the Ember Smithy.

**Outpost and beacon.** The Court Gate is a rest point and a shop (Pell the doorward sells supplies). After the Queen falls, `light` at the beacon (25 oil) lights *every* room of the region: no ambushes, rest anywhere, and Dread falls instead of rising as you walk. Beacon state is the flag `beacon_<region>`; the validator checks every beacon has a boss to guard it.

**Boss power roll** (`lamplighter/powerroll.py`, 2.8 as built). Each time you step into the Throne Room the Queen rolls a power 1 to 100, shown as a band and a line of flavour: Faltering, Subdued, Whole, Roused, Ablaze (the number is shown small). Health and damage scale together by `0.5 + power/100` (0.51x to 1.5x), gold and experience by `0.6 + 0.012 x power`, and bonus drops (the Queen's Ember, extra Hollow Cores and Fire Essences) become likelier with power. Leaving is free: choose "step back", or run once the fight has begun (a rolled boss can be fled; ordinary bosses still cannot), and she rolls again when you return. **Mercy:** the second death lowers the roll's ceiling (55), then 35, then 20; a win clears the count. **Story bosses** are capped at 60 (data flag `roll.story`; the Queen is not one). The first-kill gem bonus is given once per boss whatever the roll.

**Residents.** Pell (the Court Gate keeper, a shop and the rules of the Court). Tamsin (hiding in the Court Forge until the Steward falls): ask her to come, and Joss builds the **Ember Smithy** (400 gold, 6 Tallow Slag, 6 Cinder Glass). It adds a **second forge slot**: the forge now runs two jobs at once, and works from either smithy. The slot is added once, when the building is finished.

**Darkness Dealer (the M4 prototype, superseded by 5e).** In the Ruined Chapel. Three wares a day for gems, the same all day and different tomorrow: a fair piece of Epic to Legendary gear, a **bargain** one tier higher with a visible **curse** (a negative affix such as Brittle, Gaunt, Reckless, Dimmed, of Hunger or of Ruin) at about 55% of the price, and a relic. Each ware's affixes are decided by a seed, so the preview is exactly what you receive. Curses never appear on ordinary gear or from the forge. Prices (gems): Epic 6, Ultra 12, Legendary 24, relics 4/8/16. The full Dealer system (restock for gems, relics pre-socketed, only in the dark) is M5.

**Calibration** (`python tools/sim_court.py`, level 9, the game's own suggested play, averaged over the three classes). Ordinary fights: a lone enemy costs a third to half your health with Epic gear and a Rare build struggles with groups. The Steward: Rare 30 to 50%, Epic 54%, Ultra 66%, Legendary 88%, Godlike 99%. **The Queen at the middle roll (50):** Rare 0%, Epic about 11%, Ultra 29%, Legendary 51%, Godlike 91%; at a low roll (25) Epic wins about half the time; at the top roll (100) only Godlike has real hope. This matches the vision: Godlike makes it easy, Legendary makes it winnable, Ultra makes it hard.

**Tests.** `tests/test_court.py`: roll maths and caps, scene flows (step back, flee, die, mercy, win), every lock, the beacon, residents and the forge slot, the Dealer (determinism, curses, bought wares), validator negatives, and a full end-to-end clear by a strong player. The fuzzer reaches all 57 rooms with no crashes and the bots still finish 17 of 18 on their baseline seeds (30 to 35).

**Judgement calls to review:** the Court is post-story (an earlier ring would need the story to hand out its gear sooner); the Dealer's wares are class-blind; the Queen's reward is a trinket (the Queen's Ember) rather than a weapon, to keep weapons for the forge; Aldric is mentioned only in her last line.

### 5e. M5 as built: Darkness Dealers, `update`, save migrations

**Darkness Dealers** (`lamplighter/dealer.py`, tunables in `data/dealer.json`). One Dealer per ring (none in Hollowmere). Each day he sits in one dark, ordinary room of his ring (never a boss, rest, fixed-fight, waypost, outpost or beacon room, and never one behind a locked door), stays all day and is elsewhere tomorrow; light his room and he moves on, and a ring's beacon removes that ring's Dealer for good (he warns you). Nobody sees him with a dry lantern. The cloth has four wares: two fair pieces of gear (each with a relic socketed when its rarity has a socket), a **bargain** (a tier up to the ring's cap, a visible curse, two relics, 30% off the gear only) and a loose relic. A socketed relic costs what it costs loose. **Gems never buy Godlike.** Rings cap bargains at Epic, Ultra, Ultra, Legendary (and, from M6, Legendary for ring 5), so Legendary gear is only sold in rings 4 and 5 (the Court at 20%, ring 5 at 50%). Everything is fixed by a seed, so the preview is exactly what you get; ware ids carry the day, so a menu open past midnight cannot sell tomorrow's stock. Turning the cloth costs gems (3, 6, 12; three a day, shared by all Dealers). State is `game.dealers` (salt, bought, restocks).

**`update`** (`lamplighter/update.py`). Reads `version.json` from a GitHub repo, shows the changelog, backs up saves, downloads over https from github hosts only, verifies the archive (no traversal, links, encrypted members; size and ratio caps), stages it, and swaps code only (`lamplighter/`, `tools/`, `tests/`, `docs/`, `main.py`, `version.json`, `README.md`). A dry run loads every save against the new version first. The swap writes a marker, so a power cut mid-swap is repaired by `main.py` on next start. A failed attempt never costs a backup. Repo and branch come from env, `config.json`, then `version.json`; a new version cannot silently redirect later updates. Updates come from the public GitHub repo `kidorange125-star/lamplighter-v2`; it must stay public, because the updater sends no login.

**Save migrations.** SAVE_VERSION 2 (`dealers` moved out of flags). A damaged `dealers` block is repaired. The test suite now runs against a throwaway `LAMPLIGHTER_HOME`, so tests can never touch a real save.

**Tests.** 632 in all (`test_dealer.py`, `test_update.py`, `test_save_migration.py` new). The fuzzer now drives the Dealer; 200 games, 0 crashes, 57/57 rooms. Bots finish 17 of 18 on seeds 30 to 35 (warden 34 dies to the Drowned Bishop, as before).

**Judgement calls to review:** the beacon removes the ring's Dealer; Legendary gear is sold only in rings 4 and 5 (Court-only until M6 added ring 5); the map does not mark the Dealer yet; raw stat keys (OIL_SAVE) show in ware stat lines.

### 5f. M6 as built: The Lending

The answer to "what threatens Hollowmere next" is **a debt**. Fifty years ago Aldric (the Keeper before Orrin) borrowed a flame from six places, each receipt signed "A." and sharing one promise, *Held in trust. To be returned lit.* He never came back, and every lender kept the promise because the promise was all that kept them going. When the Court's beacon is relit it is a signal fire, and the others answer: frost on Hesk's gate and a frozen pump at the Drowned Moth, then a town that cannot sleep. The job is **release, not conquest**; the beacon at each place is the return of the loan, and the recurring answer is forgiveness (*you lent, he took the risk*). Both ring-5 bosses are people the player has already met. Full text and every number: `docs/M6-SPEC.md`.

| Lender | What was lent | Where | Package |
|---|---|---|---|
| The Moth-Saint's Hospice | the waylamp | Weeping Wood extension, 7 rooms, levels 3-5 (boss: Vesper) | `hos` |
| The Reedlight | the great lens | Saltmarsh extension, 6 rooms, levels 5-6 (the Heron) | `rl` |
| The Lampwrights' Deep | Corm's pit-lamp and his notes on the quench | Underdeep extension, 6 rooms, levels 7-8 (the Last Foreman) | `lw` |
| The Frostfair | the Great Lantern | ring 5, area A, 13 rooms, levels 10-11, plus the Fair Below annex (3) | `ff` |
| The Vigil | the Signal | ring 5, area B, 14 rooms, levels 11-12, plus the Waking Cellars annex (3) | `vg` |
| The Ember Court | the last coal | built in M4 (Pell holds the receipt) | `late` |

**Totals.** 54 new rooms (111 in all), 7 new regions, nine packages (`core hos rl lw ff vg late arc fin`). The extensions open from existing rooms by their own door: the Shrine of the Moth (light its waypost), the Bog Lights (an equipped Fire or Light book clears the fog), the Crypt Stair (a Lamp Relic socketed into something you wear). The Frostfair opens west of the North Gate once the Court's beacon is lit; the Vigil up the Signal Stair once the Great Lantern is lit.

**The two ring-5 areas.** Area A is **waiting** (Fire and Earth carry; Ice and Water are resisted; fields Black Ice and Midwinter; three Lending Posts open the Great Lantern's gate; the Ringmaster is the elite; Hobb is the rolled boss and ends in release; Marit is the Fairwarden). Area B is **watching** (Shadow and Earth carry; Light and Fire are resisted; fields Hall of Mirrors and Noon; the Great Orrery is a rotating-weakness elite; a mercy path in the chapel; the Eye, with the Prior inside it, is the rolled boss; Hale is the last novice, and his loft is the almanac). The annexes keep the faucet running after each beacon (no Dealer there, about 2 Hearts an hour). New plumbing, all in the engine: lock kinds `all`, `dread`, `flags` and `relic`; room damage `field`; enemy `attune` (a rotating weakness); the `TOPICS`, `EXTRA_NEWS`, `SELLS`, `PRICES`, `RUMOURS` and `AFTER_GAIN` hooks; `data/attach/*.json`.

**The chain.** Six receipts (five from the lenders' vaults, one from Pell) -> Orrin opens Aldric's letter -> Corm's notes to Brann -> Marit's and Hale's Given Flames -> Brann and Tamsin quench together in the Ember Smithy, which sets `godlike_recipe`. A Godlike forging now takes **both anvils**, 3,000 gold, 4 Rime and 4 Vigil Glass (the forge retune: Epic to Ultra 600, Ultra to Legendary 1,500, Legendary to Godlike 3,000; odds, pity and heat unchanged; expected attempts 2.48 / 3.56 / 4.82 / 6.42). The Long Quench (2.7) follows. The Vigil's Sixfold Chart, read by Hale and copied by Mirelle, is the apex unlock (2.6). Ysolde's **Roll of Lenders** (a Wizard topic after the story) lists all six lenders and, for each, either "receipt in hand" or the plain requirement of its door. A Wizard rewind clears none of it.

**The ring-5 Dealer.** One shared Dealer (`data/dealer.json` ring `5`: fair gear 10 / 40 / 50 percent Epic / Ultra / Legendary; relics 15 / 40 / 45; bargains and sockets cap at Legendary; gems still never buy Godlike). He sits in the Frostfair once the Court's beacon is lit, moves to the Vigil once the Fair is lit, and is gone when the Vigil is lit. Ring 5 is the first ring where Legendary is more likely than not (50%); the 28-gem price is the brake. The pool gains `ff_lamp_pole`, `vg_astrolabe_rod` and `vg_nightcloak`.

**Gem budget** (kept in `data/dealer.json` `notes`, here, and `tests/test_fin.py`):

| Source | Gems |
|---|---|
| First kills with the `boss` tag (3 each): `hos_vesper`, `rl_heron`, `lw_foreman`, `ff_lampmaster`, `vg_prior_eye` | 15 |
| Hooks: Almoner 2, Ringmaster 2, Orrery 2, the chapel mercy 1 | 7 |
| Band bonus, once per rolled boss (Roused 1, Ablaze 2) | up to 4 |
| Codes (placeholders `LENDING` 10, `THAW` 15, `VIGIL` 15, `QUENCH` 10; the owner rotates them before release) | 50 |
| **New total** | **76** |

The base game's 93 plus 76 is **about 169 over a whole game**.

**Calibration targets** (`python tools/sim_ring5.py`; method in spec 14.1: the game's own suggested play, three classes averaged, 3 draughts, 3 strong draughts, 3 oil, the full lantern kit, Dread 0, level 11 in area A and 12 in area B, weapon and armour at the stated rarity). Win rate against the middle roll (power 50), with a typical kit of three Epic books (two on the fight's weak elements) and with no books:

| Build | A, kit | A, none | B, kit | B, none |
|---|---|---|---|---|
| Epic | 14 | 1 | 7 | 0 |
| Ultra | 36 | 6 | 13 | 1 |
| Legendary | 53 | 16 | 34 | 6 |
| Godlike | 83 | 51 | 67 | 32 |
| Legendary + 3 relics | 61 | 36 | 36 | 17 |
| Godlike + 3 relics | 88 | 69 | 76 | 51 |
| ... + 3 armour relics | 92 | 74 | 80 | 62 |
| ... + Quench x2.0 | 96 | 89 | 90 | 78 |

Plain Godlike falls clearly behind by the Vigil (67% with books, 32% without); stacking recovers about half the gap and a x2.0 quench the rest; x3.0 matters at Ablaze. Ordinary fights: the recommended tier (Ultra in A, Legendary in B) wins 55 to 100 percent with 45 to 60 percent of health left, a heavy pair is a real cost, Godlike clears everything; books are worth 15 to 30 points. The Ringmaster is calibrated against a Steward x1.6 and the Orrery against x2.0 (the Orrery with the wrong books is 15 to 25 points worse than with the right ones). Extension bosses are tuned on the base game's gear: Vesper 90 to 97%, the Heron 85 to 95%, the Foreman 82 to 92%. The mercy ceilings (55, 35, 20) and the free retreat are unchanged. `sim_ring5.py --check` compares the real bosses with these cells (+-8 at power 50, +-10 elsewhere); the tables are the intent taken from the Queen stand-ins, and the real bosses are Queen-shaped, not Queen-equal.

**Calibration, as built (integration pass, 2026-11-03, n = 60 per class, three classes averaged).** The real bosses were retuned inside the +-30% of spec 14.1 with a grid search over hp and atk against the stand-in cells: Hobb 1,200 / 57 (spec stand-in 1,115 / 67), the Eye 1,175 / 70 (1,386 / 83), the Ringmaster 640 / 46 (720 / 51), the Orrery 980 / 57 (900 / 57); `vg_sentinel` 520 / 54; the Reedlight's Lampman and Heronling 85 / 17 and 70 / 18 (the extensions' ordinary groups cost a tenth of a player's health, now a fifth). The three extension bosses are inside their bands (Vesper, the Heron and the Foreman: 0 of 6 cells outside). `python tools/sim_ring5.py --area all --check` reads 335 cells and finds **22 outside their bands** (8 of 166 in the Frostfair, 14 of 163 in the Vigil). They are residuals that no hp or atk value removes, kept here so nobody retunes them again:

- *Quench and none columns of Hobb* (7 cells: `none` p50 God+3 / God+3+arm / God+Q2 and p75-p100 with a quench run 10 to 15 points easy; `kit` p100 +Q2.0 runs 14 hard). The stand-in has no damage field: Midwinter dims fire to 0.8, which taxes the books of the kit, and the suggested play spends turns on books that a x2 weapon would beat. Hp and atk only trade one group of cells for the other (a grid of about 50 hp and atk settings: the floor is 7 cells).
- *Eye*: books carry more weight against the real Eye (weak to Shadow and Earth) than against the Queen: `kit` p25 to p50 low tiers run 12 to 16 easy; the quenched `none` cells run 9 to 19 hard because the ashblade's rod is fire and the Eye resists fire (the ashblade wins 2 to 5% of them). Elements are not tunable (spec 2.3); the cure is a second strong ashblade lane or a lift to the ashwood rod, which is a base-game change.
- *Orrery*: the right-versus-wrong books gap measures 9 against 15 to 25 because every element is weak in some stance, so the spec's "wrong" set (Light, Fire, Water) is itself a good loadout (Water in the Sun-line, Fire in the Moon-line, Light in the Star-line). The mini-boss cells `kit` Ultra (+14) and `none` Leg+3 (+11) are the other two Vigil residuals.
- *Lane tests*: the wrong lane may not help (ceiling +2); in the Frostfair it measures +2 to +3 at the boss (noise), in the Vigil +8 on ordinary pairs (Blind Spot is weak to Fire by the roster table, and Light is already strong against Hollows).

`--check` honours `--area`, `--kit`, `--powers` and `--level`, and prints its warnings after the failures (`--strict` makes them fail). The warnings are the per-class floor of spec 14.3 (no class below half the class mean in any cell above 30%): the hard rule (Godlike with three Epic books) holds, and the others are the ashblade at 0 to 18% in the `none` cells of stacked Godlike builds at p50 to Ablaze in both areas, and the warden at 5 to 20% in a few Epic and Ultra kit cells, as with the Queen stand-in.

**Economy** (`python tools/sim_economy.py [--check]`: a casual hour is 5 moves a minute, 1.7 minutes a fight, 20 fights an hour in A and 18 in B). Gold an hour is group gold plus junk (Fair Tokens, Star Plates): that, and only that, is what every range below is compared with. Materials (Rime, Vigil Glass, essences, Hearts) are the forge's inputs and are never counted as cash; the tool prints them in their own column. Targets: the Frostfair 1,600 to 2,100 gold an hour, the Vigil 1,900 to 2,500, the annexes x1.2 of their area with 2 to 3 Hearts an hour; rent is 63 an hour across all buildings, **504 a session at the cap when every building stands** (8 hours x 63; 320 is the average while buildings are still arriving). The first Godlike recipe is about 16 hours of play (19 with the turn-ins and forge waits; fast 14.5, thorough 22); the planned ledger is earned about 28k (fights 20k, rent 8k) and spent about 25k (weapon Rare to Legendary 10.0k expected, armour 2.7k, trinket and relics 4k, buildings 3.5k, call-backs 2.5k, materials 2k), then the Godlike attempts (19.3k expected, one a day) are paid from the annexes and rent. **Gold is the throttle until the first Godlike; Hearts are the throttle after.**

**Economy, as built (integration pass, 2026-11-03, gold plus junk only).** The first draft ran 12 to 22 percent under the bands, so the mobs' gold was retuned (the bosses' gold, the junk values and the drop chances are pinned by the spec): Frostfair mobs x1.7, the Sleeper Below x3.6 (the Fair Below's faucet), Vigil mobs x1.75, the Cellar Dead x2.6, the three extensions' mobs x1.8 (the chapel's mercy purse became 180 gold so it still pays at least what the two-Brother fight would). Measured now: the Frostfair 2,100 an hour and the Vigil 2,450 (both inside their ranges), the Fair Below x1.17 and the Waking Cellars x1.27 of their area, the three extensions 282, fights, bosses and vaults 21.1k to the recipe and rent 8.1k against 24.7k spent, so the purse is 4.5k ahead at the recipe. `python tools/sim_economy.py --check` passes 25 of 26 figures. The one it fails is the days to the first Godlike: **13.7 days of casual play (4 sessions of 30 minutes a week) against the spec's 9 to 11 (+-10%)**. That figure does not follow from the spec's own inputs: a casual week pays about 7.6k (four half-hour sessions in the annexes plus rent at its cap) against a 14.8k shortfall, and even with the annexes at x1.3 and both ring-5 areas at the very top of their ranges it is still about 12 days. It is left red on purpose: closing it means pushing every income band to its ceiling or cutting the Godlike forging gold below the 18.9k to 19.7k the same tool pins (spec 11.1). The owner's levers are the forge gold (3,000 an attempt; 2,500 gives about 11 days), the annex encounter chance, or accepting two weeks. Knobs when a playtest misses the hours: encounter `chance` per room (0.05 is about 6% of an area's time), the Lending Posts the gate needs, the forge gold, the annex chance. Never tune XP or boss stats to tune hours: the level cap stays 12. An earlier reading of 1,834 and 1,885 an hour came from selling Rime, Vigil Glass, essences and Hearts at the shop price, which counted the Godlike inputs as cash.

**Tests and tools.** `tests/test_fin.py` holds the id register, the gem budget and codes, the ring-5 Dealer, the Roll of Lenders, the rules every package obeys (lock messages, group sizes, rolled-boss shape, no Hollow weak to Light), the "never stalls" rules, an old-save gate, tool smoke tests, the integration fixes (below), and a scripted playthrough: Court beacon -> the Frostfair -> the Vigil -> the three older doors -> receipts -> the letter -> flames -> the third quench -> a Godlike forging -> a Long Quench on a fake clock -> the apex unlock. That playthrough answers every fight "win"; the integration pass also ran it with real combat (each fight played by the game's suggested policy, up to 8 tries, level 12 Godlike gear with three relics and a kit of Epic books chosen for the fight) for the wayfarer, the warden and the ashblade, and again from a late save with every M6 room and flag stripped out and reloaded (all 54 new rooms refilled their floor items): all three classes finish, every fight won on its first try.

**Integration pass (2026-11-03).** Found and fixed when the packages met: the bosses, mobs and gold were retuned as above; the `hint` line named a resident by id (`talk ff_marit`) and now uses the word the parser knows (`talk marit`); the hint's side-quest list showed only three, so the three oldest side quests hid the Frostfair's and the Third Quench's, and it now shows five and puts the ones in the region you stand in first; Brann no longer remembers Corm as a man he met (Corm vanished fifty years ago: his father told him the saying) and no longer meets the name twice if the notes were shown before the Deep was described; the validator no longer reads forged gear instances (a Long Quench pushes damage past x5); the map test, the save-migration expectations (rooms added after a save get floor items), the multiplier allow-list (`ice water shadow earth spell`) and the two forge tests (a Godlike forging needs the third quench, a second anvil, Rime and Vigil Glass) were brought up to M6; the chapel's mercy purse pays 180 gold so it still matches the two-Brother fight.

**Judgement calls to review:** forge prices were retuned (a Godlike was 77k expected gold); the level cap stays 12; one shared ring-5 Dealer at 50% Legendary; the +5% damage affix is now `of_havoc` (the curse keeps `of_ruin`); apex failure is still the owner's harsh rule; story canon (Aldric borrowed six flames; Corvin was the Hospice's lay-brother; Hobb is Marit's husband; the Court's own "a hundred years" lines are left alone). Section 20 of the spec lists the rest.

## 6. Open decisions
1. *(Settled: forge and build timers use real time and steps together; spell elements are Fire, Ice, Water, Light, Shadow, Earth.)*
2. **Single character or party** (Wren as a full companion).
3. **More classes?**
4. *(Closed in M6: the Debt. Before he went down the Well, Aldric borrowed a flame from six places on the promise "Held in trust. To be returned lit." Lighting the Court's beacon is a signal fire and the others answer it. See 5f.)*
5. **GitHub repo** for `update`: settled. `kidorange125-star/lamplighter-v2` (public), set as `repo` in version.json. A release is a push to `main` there with a higher `version` in version.json.
6. **Hunger Survival mode:** later.

## 7. Risks
| Risk | Mitigation |
|---|---|
| Scope | Milestones; the vertical-slice gate at M4 |
| RNG frustration | Odds shown, pity, no destroyed items, free retreat, mercy |
| Too much hand-written content | Data-driven design, generated loot, ultracode for wide independent content |
| Balance drift | Simulators; test builds, not only items |
| Save breakage | Versioned saves with migrations |
| Real-time timers feel like chores | Several slots, gem speed-ups, step-based progress too, caps on rent |
| One dominant tactic | Every spell and skill needs a cost or limit; element weaknesses |

## 8. Future track O: online play with friends *(owner's idea, not scheduled)*
Friends list; invite friends into your world (one-time or standing); gifts and unrestricted trading; co-op quests and team battles; friends buy things in your world or pay the builder for their own plot; view a friend's stats, showcase and (optionally) gold.
- **Phases:** O1 async friends (codes, profile, gifts through a mailbox server); O2 live co-op (relay, host is the authority, 2 to 4 players, invite-only); O3 shared town plots.
- **Prepare now:** keep rules separate from printing; keep player state and world state separate in saves (the stash and gems are on the player); unique item ids; JSON only, never pickle; validate all incoming data against the content files.
- **Rules:** scale bosses with party size (less than linearly) and give each player their own loot rolls; privacy first (invite-only, gold hidden by default, block and mute); "join anytime" needs the host online or a cloud-hosted world; offline play always works.

## 9. Working agreement
- The owner wants steady progress on the base game: fix bugs, make everything work, and add the owner's ideas as soon as they can be built.
- **Ultracode** (multi-agent) is for wide independent jobs, such as the content of rings 2 to 6 once the first vertical slice exists. Tell the owner when that point is reached.
