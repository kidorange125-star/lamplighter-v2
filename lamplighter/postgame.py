"""After the story: the Wizard's Shop can call back defeated bosses and rewind the story.

Rewinding resets the story (bosses, locks, the Embers you carry) but keeps your gear, level, gold,
town and everything you have built. A backup save is written first.
"""
from . import save
from .content import REGION_INFO, ROOMS

# Each layer is undone together with every layer after it (the later the chapter, the fewer layers).
# (chapter name, flags to clear, items to take back)
LAYERS = [
    ("The Lightwell", ["ending", "usher_dead"], []),
    ("The Underdeep", ["choir_dead", "golem_dead", "brood_dead", "embers_set"], ["ember_ash"]),
    ("The Saltmarsh", ["bishop_dead", "reeve_dead", "nave_guard"], ["ember_tide", "tide_key"]),
    ("The Weeping Wood", ["mother_dead", "camp_wight", "shrine_moths"], ["ember_wood"]),
]
REWIND_FEE_PER_BOSS = 120
CALLBACK_FEE_PER_RING = 100


def _flags_for(chapter_index):
    flags, items = [], []
    for _, f, i in LAYERS[:chapter_index + 1]:
        flags += f
        items += i
    return flags, items


def rewind_cost(g, chapter_index):
    flags, _ = _flags_for(chapter_index)
    bosses = sum(1 for f in flags if f != "embers_set" and g.flags.get(f))
    return max(1, bosses) * REWIND_FEE_PER_BOSS


def rewind(g, chapter_index):
    """Undo the story from the chapter onward. Returns the fee that was charged."""
    fee = rewind_cost(g, chapter_index)
    save.write(g.to_dict(), slot="before_rewind")
    flags, items = _flags_for(chapter_index)
    for f in flags:
        g.flags.pop(f, None)
    for key in [k for k in g.flags if k.startswith("opened_")]:
        g.flags.pop(key)        # the doors will open with their scenes again
    for iid in items:
        g.player.inventory.pop(iid, None)
    g.set_quest("main", 1, quiet=True)
    g.player.gold -= fee
    return fee


def defeated_bosses(g):
    """[(room_id, boss name, fee)] for every boss that has been beaten and can be called back."""
    out = []
    for rid, r in ROOMS.items():
        flag = r.get("boss")
        if flag and g.flags.get(flag):
            ring = REGION_INFO[r["region"]]["ring"]
            out.append((rid, r.get("boss_name", r["name"]), CALLBACK_FEE_PER_RING * max(1, ring)))
    return out


def call_back(g, room_id):
    r = ROOMS[room_id]
    g.flags.pop(r["boss"], None)
    if r["boss"] == "ending":
        g.flags.pop("ending", None)
    g.player.gold -= CALLBACK_FEE_PER_RING * max(1, REGION_INFO[r["region"]]["ring"])
