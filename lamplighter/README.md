# The Last Lamplighter

A text RPG in pure Python (3.8+, no installs).

Forty days ago the sun set over Hollowmere and never rose. The Lightwell under the hill, the fire that feeds the sun, is dying. You are the last apprentice of the Guild of Lamplighters. Recover three Ember Shards from three fallen guardians, go down into the dark, and decide what to give the Well.

```
python main.py
```

Options: `--fast` (no typewriter text), `--no-color`, `--seed N`, `--script FILE` (replay commands, used for testing).

## What's in it

- **Your lantern is the core mechanic.** Every step into a dark place burns oil. When it runs dry you are *benighted*: you can't see what enemies are about to do, Hollows ambush you and hit 25% harder. In combat, a **Flare** burns oil to sear every enemy (double against Hollows, blinding them). The final boss can only be hurt after a flare tears his shroud away.
- **Telegraphed combat.** Every enemy shows its next move before you act, with estimated damage. Guard the heavy hits, stun the wind-ups, kill the healer first.
- **Three classes:** Warden (stuns, braces, outlasts), Ashblade (burns, fire walls, stronger flares), Wayfarer (bleeds, dodges, executes). Four skills each, plus stat points every level.
- **35 rooms** across Hollowmere, the Weeping Wood, the Saltmarsh and the Underdeep, with an auto-map.
- **5 bosses and elites with phases**: the Antlered Mother, the Drowned Bishop (who regenerates unless you keep him burning), the Ash Choir (three singers who grieve and grow stronger when one falls), the Ore-Warden, and the Hollow King.
- **8 characters**, 7 quests, 6 journal pages that reveal the backstory and unlock a way to weaken the final boss.
- **4 endings**, and which you can reach depends on what you did along the way.
- Shops, lantern upgrades, wayposts you can relight as safe rest points, a bounty board, Story/Normal/Hard difficulty, and saving.

## How it plays

Every area has a home screen: your status, the room, and a numbered list of things to do, with a ★ suggested next step. Type a number, or any command. Whatever you do gets its own clean screen; press Enter and you're back at the area. Fights redraw each round, showing only what just happened and the state of the battle.

## Commands

`help` in game lists everything. The basics: `n s e w u d`, `look`, `examine <thing>`, `take all`, `talk <person>`, `trade`, `inventory`, `equip <item>`, `use <item>`, `light`, `rest`, `map`, `journal`, `stats`, `lantern`, `save`. Chain commands with `then`: `n then take all then e`.
