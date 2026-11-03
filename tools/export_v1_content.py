"""One-time helper: export the v1 Python content modules into the v2 JSON data files.

usage: python tools/export_v1_content.py <path to v1 'lamplighter' folder>

Kept in the repo so the conversion is reproducible. Day to day, edit the JSON files directly.
"""
import json
import os
import sys

v1 = sys.argv[1]
sys.path.insert(0, v1)
from game.data import classes, enemies, items, world  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lamplighter", "data")


def dump(name, obj):
    path = os.path.join(DATA, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote", os.path.relpath(path, os.path.dirname(DATA)))


dump("items.json", items.ITEMS)
dump("pages.json", {k: {"title": t, "text": x} for k, (t, x) in items.PAGES.items()})
dump("enemies.json", enemies.ENEMIES)
dump("classes.json", {"classes": classes.CLASSES, "skills": classes.SKILLS})

by_region = {}
for rid, room in world.ROOMS.items():
    by_region.setdefault(room["region"], {})[rid] = room
for region, rooms in by_region.items():
    slug = region.lower().replace(" ", "_")
    dump("rooms/%s.json" % slug, rooms)
