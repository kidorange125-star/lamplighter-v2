# The Last Lamplighter (v2, in development)

A text RPG for the terminal. Pure Python 3, no installs.

```
python main.py            play
python main.py --fast     no typewriter text
python main.py --no-color plain text
```

Saves go in your user data folder (`%APPDATA%\Lamplighter` on Windows), never in the game folder, so updating the game cannot touch them.

## Updating

Type `update` in the game (or run `python main.py --update`; the same words follow it, such as `python main.py --update check` or `python main.py --update repo owner/name`). It only ever contacts the network when you do this: no background checks, nothing sent about you.

```
update                     look for a newer version, show what's new, ask, then install it
update check               only look
update force               install even if the version is not newer (a reinstall or a downgrade)
update repo owner/name     choose where updates come from (saved in config.json in your data folder)
```

- Before anything changes, your saves are copied to `backups/<date>-<old version>/` in your data folder. The last 5 are kept, and the oldest are only tidied away once an update has worked, so a failed attempt never costs you a backup.
- It downloads the repo over https from github.com hosts only, unpacks it into a temporary `.update_new/` folder inside the game folder (removed afterwards), and installs only `lamplighter/`, `tools/`, `tests/`, `docs/`, `main.py`, `version.json` and `README.md`. Saves and settings are never touched.
- Before swapping, the new version must pass its own content check and load a copy of every one of your saves (damaged-save and `.vN.bak` copies the game keeps for you are skipped). If anything fails, nothing is changed and it says why. Ctrl-C at any point also leaves everything as it was.
- If the power goes or the game is killed in the middle of the swap itself, the next `python main.py` notices and puts your earlier files back from `.update_old/` before doing anything else.
- The replaced files are kept in `.update_old/` inside the game folder until the next update. The game keeps running on the old code; restart it to use the new version.
- The repo comes from the `LAMPLIGHTER_REPO` environment variable, else `config.json`, else the `repo` in `version.json` (empty until a repo exists). `update repo` lowercases what you type, which is fine because GitHub names are not case sensitive. The branch comes the same way (`LAMPLIGHTER_BRANCH`, `config.json`, `version.json`) and defaults to `main`. A new version cannot quietly point later updates somewhere else: if its `version.json` names a different repo or branch, you are told, and the one you used is kept in `config.json`. A `version.json` with a repo or branch that is not valid is refused.

## For developers

```
python -m unittest discover -s . -t . -p "test_*.py"   run the tests
python tools/validate_content.py                       check every reference in the game data
python tools/sim_power.py                              win rate by gear tier against stronger and stronger bosses
python tools/sim_report.py                             balance report: win rates for each fight
python tools/sim_court.py                              Ember Court fights and the Queen at each power roll, by gear tier
python tools/sim_ring5.py --area all --check          ring 5 and the extensions: every group, mini-boss and boss by build and kit
python tools/sim_ring5.py --area ff --lane             the right books vs the wrong books vs none (also --classes, --standin)
python tools/sim_economy.py --check                    gold, Rime, Vigil Glass and Hearts an hour, the forge bill, the ledger
python tools/sim_smith.py                              the Long Quench: outcomes, expected gold and days
python tools/sim_fights.py antlered_mother --class wayfarer --level 3 --weapon hunting_spear
python tools/bot.py wayfarer 1                         play the whole game to an ending
python tools/fuzz.py 200 2000 0                        play random games to find crashes (reaches all 111 rooms)
python tools/make_code.py CODE 25 "label"               add a gem code
```

- Content (rooms, items, enemies, classes, journal pages, regions) lives in `lamplighter/data/*.json`. Edit those, then run the validator.
- `lamplighter/data/` holds one file per area in `rooms/`, `enemies/`, `items/`, `regions/`, `buildings/`, and `attach/` (doors added to existing rooms). An area's scripted bits live in `lamplighter/areas/<slug>.py`; `lamplighter/areas/__init__.py` lists every hook.
- **M6, "The Lending"** (`docs/M6-SPEC.md`) was built as nine packages, each owning its own files: `core` (plumbing: attach files, lock kinds, damage fields, rotating weaknesses, merged hooks), `hos`, `rl` and `lw` (the three area extensions), `ff` (the Frostfair) and `vg` (the Vigil), the two ring-5 areas with their annexes, `late` (the Third Quench, two-slot Godlike forging, the Long Quench), `arc` (the apex unlock, Hearts, the Grand Binding) and `fin` (the ring-5 Dealer, gem codes, the Roll of Lenders, the simulators, these docs and the integration test).
- Tests: 1,298 in all (632 before M6; `tests/test_fin.py` holds the id register, the gem budget, the rules every package obeys, the integration fixes and a scripted playthrough from the Court's beacon to the apex unlock). The full suite runs in about 60 seconds. `python tools/validate_content.py`, `python tools/fuzz.py 200 2000 0` (0 crashes, all 111 rooms) and the 18 bot runs on seeds 30 to 35 (17 finish; the warden dies to the Drowned Bishop on seed 34, as before) are the other gates.
- After changing any ring-5 number run `tools/sim_ring5.py --check` and `tools/sim_economy.py --check`: they compare the data with the pinned cells of the spec. `sim_ring5.py --check` honours `--area`, `--kit`, `--powers` and `--level`, prints its warnings (per-class floors) after the failures and fails on them with `--strict`; `sim_economy.py` counts only group gold plus junk as gold an hour and prints the forge materials in their own column. As shipped, the economy check passes 25 of 26 figures (the days to the first Godlike, 13.7 against the spec's 9 to 11, is left red on purpose) and the ring-5 check leaves 22 of 335 cells outside their bands (structural residuals listed in `docs/V2-PLAN.md` 5f). The three extensions are inside their bands.
- `docs/V2-PLAN.md` is the plan: design decisions, milestones, progress and open questions.
