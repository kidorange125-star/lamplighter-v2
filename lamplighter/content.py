"""Loads all game content from the JSON files in lamplighter/data.

Content lives in data, not code: rooms, items, enemies, classes and skills, journal pages and regions.
Add or change content by editing the JSON, then run `python tools/validate_content.py`.
"""
import glob
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_json(*parts):
    with open(os.path.join(DATA_DIR, *parts), encoding="utf-8") as f:
        return json.load(f)




def load_merged(name):
    """data/<name>.json plus every data/<name>/*.json (one file per area), merged. A duplicate id is an error."""
    out = dict(load_json(name + ".json"))
    for path in sorted(glob.glob(os.path.join(DATA_DIR, name, "*.json"))):
        with open(path, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if k in out:
                    raise ValueError("duplicate %s id %r in %s" % (name, k, path))
                out[k] = v
    return out


ITEMS = load_merged("items")
PAGES = load_json("pages.json")
ENEMIES = load_merged("enemies")
_classes = load_json("classes.json")
CLASSES = _classes["classes"]
SKILLS = _classes["skills"]
REGIONS = load_json("regions.json")
for _path in sorted(glob.glob(os.path.join(DATA_DIR, "regions", "*.json"))):
    with open(_path, encoding="utf-8") as _f:
        REGIONS.extend(json.load(_f))
BUILDINGS = load_merged("buildings")
CODES = load_json("codes.json")
AFFIXES = {a["id"]: a for a in load_json("affixes.json")["affixes"]}
RELIC_INFO = load_json("relics.json")
FORGE = load_json("forge.json")
DEALER = load_json("dealer.json")
_spell_data = load_json("spells.json")
SPELLS = _spell_data["spells"]
SPELL_RULES = {k: v for k, v in _spell_data.items() if k != "spells"}
REGION_NAMES = [r["id"] for r in REGIONS]
REGION_INFO = {r["id"]: r for r in REGIONS}

ROOMS = {}
for _path in sorted(glob.glob(os.path.join(DATA_DIR, "rooms", "*.json"))):
    with open(_path, encoding="utf-8") as _f:
        for _rid, _room in json.load(_f).items():
            if _rid in ROOMS:
                raise ValueError("duplicate room id %r in %s" % (_rid, _path))
            _room["pos"] = tuple(_room["pos"])
            ROOMS[_rid] = _room

def apply_attach(rooms, paths):
    """Attach patches: an area that grows an existing region adds its door to the old room from its own file.

    data/attach/<slug>.json  {existing_room_id: {"exits": {dir: room}, "locks": {dir: lock}, "npcs": [..], "items": [..]}}
    An unknown room, or an exit or lock the room already has, is an error naming the file; npcs and items are appended.
    """
    for path in paths:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            patches = json.load(f)
        for rid, patch in patches.items():
            if rid not in rooms:
                raise ValueError("attach %s: unknown room %r" % (name, rid))
            room = rooms[rid]
            for key in ("exits", "locks"):
                if not patch.get(key):
                    continue
                have = room.setdefault(key, {})
                for d, val in patch[key].items():
                    if d in have:
                        raise ValueError("attach %s: room %r already has %s %r" % (name, rid, key[:-1], d))
                    have[d] = val
            for key in ("npcs", "items"):
                if patch.get(key):
                    room.setdefault(key, []).extend(patch[key])


apply_attach(ROOMS, sorted(glob.glob(os.path.join(DATA_DIR, "attach", "*.json"))))
