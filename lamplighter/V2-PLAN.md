# The Last Lamplighter v2: Plan

Working title: *The Last Lamplighter: Hollowmere Reborn* (placeholder).
Written after a full playthrough of v1 and a design discussion. Everything marked **TUNE** is a starting number to be set by simulation, not a promise.

---

## 1. Vision

A text RPG big enough to last a couple of months of casual play (30 minutes, 4 times a week, so roughly **15 to 20 hours**).

- **Hollowmere is lit and safe.** The sun is there. It is a free home base that grows as you rescue people.
- **Around it, dark areas in rings by difficulty.** You push the dark outward one area at a time: find the remnants of a place, rescue its survivors, beat its boss, relight its beacon.
- **Loot is a gamble you plan for.** Common to Rare is easy to get. Epic and above come only from the forge, cost gold and waiting time, and are not guaranteed. The result is revealed with a colour sweep.
- **Bosses roll their power (1 to 100)**, so repeat attempts matter.
- **Dread** is the second resource after lantern oil: darkness makes you stronger and shakier.
- v1 problems this fixes: confusing navigation and combat menus, one dominant tactic (flare), too short.

## 2. Locked-in design decisions

### 2.1 Town and survivors
- Hollowmere is always lit and safe. Rest, stash, market, guild board, forge(s), tavern, home.
- Each area contains **remnants** of what was lost there (a cracked anvil, a merchant's cart, a priest's bell) and at least one **survivor** nearby.
- Rescue a survivor and light the area's beacon, and after a wait **they move into town** and open their own business. The town map visibly grows (new buildings, a population count with small perks).
- Specialists: each smith has a style (tide, ash, ...) and adds a **forge queue slot**. **Godlike items need two or three smiths working together.** Other residents: relic-maker (sockets), enchanter, apothecary, cook, trainer, stash-keeper.
- A **second survivor per area stays behind and runs an outpost**: rest point, relic anchor, small shop (supplies and basic gear only). A few survivors give a **choice** ("run a small forge here, or move to Hollowmere and open the Tide Forge?").
- Outposts can be hit by a **Long Night** event and close temporarily (never destroyed). Defending one gives a reward.
- v1 characters carry over: Brann is the first smith. Tallow, Corvin, Oskar, Hesk, Sister Ilse, Maeve and Wren become early residents or outpost keepers.

### 2.2 Areas
- Hub-and-spoke: rings by difficulty around the town. Each area has a recommended gear tier shown on the map.
- **Lighting an area** = beat its boss + relight the beacon. It then becomes safe: no random fights, a rest point, an outpost, a relic anchor.
- Locked areas always say **exactly what they need** on the map (a lock icon and the requirement). Lock types: boss key, riddle phrase (from NPCs or journal pages), relic-attuned door, element door (burn it, light it), timed door (night or market day only), reputation door, companion door (only Wren fits), stat check, vault (optional, guaranteed forge materials).
- v1's three regions become **rings 1 to 3** (Weeping Wood, Saltmarsh, Underdeep), reworked. Rings 4 to 6 are new (names TBD).

### 2.3 Loot and forging
| Tier | Colour and symbol | Source |
|---|---|---|
| Common, Uncommon, Rare | grey, green, blue | Drops, shops, chests |
| Epic | purple ◆ | Forge only |
| Ultra | magenta ◆◆ | Forge only |
| Legendary | gold ✦ | Forge only |
| Godlike | cycling rainbow ✦✦ | Forge only, plus a recipe quest and multiple smiths |

- Each tier also has a **symbol and a word**, so colour-blind players can read it.
- **Odds are shown before you commit.** A **heat meter** (pity) fills on every failed attempt and raises the next chance, with a guaranteed result after enough attempts. A failed attempt **never destroys the base item**; it refunds part of the materials. (TUNE)
- **The reveal:** a bar sweeps through the rarity colours, fast, then slows and lands. Enter skips it. The item's name, stats and abilities appear one line at a time.
- **Wait times:** real-time timers that run while the game is closed, with a journey-based option (steps and fights) as a fallback. **Open decision: real-time, journey-based, or both.** Forge level and extra smiths add queue slots.
- Starting numbers (TUNE): Rare to Epic 35%, Epic to Ultra 20%, Ultra to Legendary 10%, Legendary to Godlike 2%, with pity.
- Items: base type + material + 0 to 3 affixes + 0 to 3 sockets. Legendary and Godlike items are **named, one of a kind**, with lore and a use counter that unlocks more lore. Weapons level up from use.

### 2.4 Relics
- Items have sockets for relics. Types: spell relics (cast a spell), passives, triggers (counter when you dodge), cursed (strong, with a drawback).
- Common relics can be bought. **Rare versions need boss loot plus the forge.** Godlike relics are never sold.
- Fusing two of the same relic upgrades it. Matching relics give set bonuses.
- **The Homecoming Relic** is the first one: recall to town, set anchors at lit beacons and outposts. It costs oil or a charge, so it is a decision. Upgrades: more charges, more anchors, a companion tags along.

### 2.5 Boss power roll
- Late-game and optional bosses roll **power 1 to 100** each time they spawn.
- The roll is **shown as flavour, not a number** ("The air tastes of iron. This one is wrong."), and the player can **retreat for free** before engaging. A higher roll means better rewards (more forge materials and gems).
- Starting bands (TUNE): 1 to 25 Weakened, 26 to 70 Standard, 71 to 90 Empowered, 91 to 100 Mythic. Roughly **25 roll points shifts the fair gear requirement by one tier**.
- **Mercy:** after 2 deaths to the same boss, its next roll's ceiling drops; it resets on a win.
- **Story bosses cap their roll** so the main story cannot soft-lock. Only optional bosses roll the full range.
- Tuning targets for late-game bosses at a mid roll: **Godlike 85%+ first-attempt win, Legendary 55 to 70%, Ultra 20 to 35%, Epic 10% or less.**

### 2.6 Gems, codes, Darkness Dealers
- Gems come from **redeemable codes** released at milestones (a new area, a `NEW` code for new players) and also **trickle in through play** (rare drops, achievements) so players without codes are not locked out.
- Codes are checked locally: stored as hashes, one redemption per save, version-gated. This is a single-player game, so the goal is convenience, not security.
- **Darkness Dealers** appear only in dark areas or at night. They sell strong gear with relics already socketed, and **every item carries a bargain** (power at a cost, often extra Dread). Random stock, restocked after a boss win or for a gem fee.
- Gems also speed up forging and reroll dealer stock. **Gems never buy Godlike.**

### 2.7 Update command
1. `update` reads `version.json` from the project's GitHub repo.
2. It shows the changelog, backs up saves, downloads the new code over HTTPS, replaces code only, and runs save migrations.
- **Saves live outside the game folder** (the user data directory, for example `%APPDATA%\Lamplighter`), so an update can never touch them. Saves carry a version number and migrations.
- The command runs whatever is in the repo, so the repo needs 2FA. Nothing is pushed anywhere without the owner's say-so.

---

## 3. Dread (new resource)

**Idea:** darkness is frightening and dangerous, but fear also sharpens you. Dread trades safety for power, the same bargain the Darkness Dealers offer.

**Meter:** 0 to 100, shown on the HUD with a tier name.

**Gains (TUNE):**
- Each step into a dark room: +2 in ring 1, rising to +5 in ring 6.
- Each combat round in the dark: +1. Benighted (lantern empty): double.
- Entering a boss's presence: +5, or +10 for an Empowered or Mythic roll.
- Dealer bargains and cursed relics can add Dread.

**Losses:**
- Each step in a lit room: -3.
- Resting at a beacon, an outpost or in town: reset to 0.
- A hot meal: -10 to -20. Hearth talk with a resident: -15.
- A companion with you: gains reduced by 25%.

**Tiers and effects (TUNE):**
| Dread | Tier | Effect |
|---|---|---|
| 0 to 24 | Steady | None |
| 25 to 49 | Uneasy | +5% damage, -5% dodge |
| 50 to 74 | Afraid | +12% damage, +10% crit, -10% dodge |
| 75 to 99 | Terrified | +20% damage, healing -25%, enemy tells on normal enemies hidden |
| 100 | **Consumed** | "Hollowing" for 3 rounds: +40% damage, 25% chance each round to lash out at a random target. Then you collapse: Dread drops to 60 and you are "Shaken" (-20% damage) until you rest. |

**Design rules:**
- Dread never kills you. Consumed is a risk, not a death spiral.
- Some relics convert Dread into power ("+1% spell damage per 5 Dread"), and some dealer items require it.
- The typical expedition should end around Afraid. A well-planned run should not hit Consumed by accident.
- **Option:** "Dread: cosmetic only" for players who want no mechanics from it.
- Hunger stays out of the base game: meals are **buffs** (and lower Dread). An optional **Survival** difficulty with hunger can come later.

---

## 4. Technical plan

- **New project, modular and data-driven.** Rooms, enemies, items, spells, NPCs and quests live in data files, validated by a script (like the checker used in v1). The engine stays small.
- Python standard library only, as in v1. Windows ANSI colour support as in v1.
- Content that can be reused from v1: the UI layer (colour, wrapping, menus), the enemy-intent combat idea, rooms and writing for rings 1 to 3, items, bosses, journal pages.
- **Simulation harness from day one:** bots that play fights at each gear tier and report win rates. This is how the boss bands and forge odds get tuned.
- Content scale target: about 20 hub rooms + 6 rings of about 25 to 35 rooms (roughly 200 total), 20+ bosses, 40+ NPCs, a generated-loot system for volume.

## 5. Milestones (each one playable)

| # | Milestone | Done when |
|---|---|---|
| M0 | **Setup:** new folder, git repo, data-driven layout, saves in the user data directory, `version.json`, test and simulation harness | A blank game loads, saves, and passes the content validator |
| M1 | **Clarity and combat:** objective line, `hint`, `travel`, flat combat menu with a suggested action, the better map (local, region, world), a short tutorial, combat rework (flare no longer dominant, Shadowstep fix, tuned fight length) | A new player can finish ring 1 without asking what to do; flare-only wins are no longer near 100% |
| M2 | **Hub and relic:** town districts, home and stash, market, guild board, the Homecoming Relic, Dread v1 | The town map redraws as buildings are added; recall works; Dread tiers play right |
| M3 | **Loot and forge:** item model, rarity ladder, forge UI with sweep reveal and pity, wait timers, sockets and relics, rolled shop stock | An item can go Rare to Legendary through the forge, with odds shown and a real reveal |
| M4 | **Vertical slice:** one full ring-1 area end to end (remnants, survivors, outpost, beacon lighting, a boss with the power roll and mercy, three lock types, a Darkness Dealer prototype) | **Decision gate:** is the loop fun? Fix before building more |
| M5 | **Gems, codes, dealers, `update`, save migrations** | Redeem a code, buy a dealer item, update from a test repo without losing a save |
| M6 to M9 | **Remaining areas** (rings 2 to 6), two per milestone, each with survivors, outpost, vault, boss | Each ring is playable and its boss meets the win-rate targets |
| M10 | **Retention:** contracts, random delves, bestiary and codex, Dark Ranks (harder replays), weekly Nightfall boss, trophy hall, achievements | A week of play has daily goals |
| M11 | **Balance and polish:** simulation sweeps per gear tier, accessibility (colour-blind safe, text speed), in-game manual | Targets in section 2.5 are met |

## 6. Open decisions
1. **Forge timers:** real-time, journey-based, or both. (Default: both.)
2. **Survivor arrival:** short wait vs instant. (Recommended: short wait, real-time or expedition-based.)
3. **Party:** single character, or small party with Wren as a full companion.
4. **More classes?** v1 has three.
5. **Story after the town is lit:** what is the endgame once the areas are relit? Options: a final dungeon under the Lightwell, a rising threat that ends the story, or an open-ended endgame.
6. **Project location:** pick a permanent folder, and a GitHub repo for `update`.
7. **Hunger Survival mode:** in 2.0 or later.

## 7. Risks
| Risk | Mitigation |
|---|---|
| Scope: this is a very large game | Milestones; the vertical slice gate at M4 |
| RNG frustration (forge, boss rolls) | Odds shown, pity meter, no item destruction, free retreat, mercy |
| Too much hand-written content | Data-driven design, generated loot and delves, hand-written story areas only |
| Balance drift | Simulation harness, win-rate targets |
| Save breakage across updates | Versioned saves with migrations, saves outside the game folder |
| Remote code in `update` | Own repo, 2FA, changelog shown, backup first |

## 8. First three sessions
1. M0: set up the project folder and repo, the validator, the harness, and move saves out of the game folder.
2. M1a: objective line, `hint`, `travel`, and the new map.
3. M1b: flat combat menu and the combat rework, checked against simulated win rates.
