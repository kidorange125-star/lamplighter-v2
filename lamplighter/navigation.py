"""Where to go next: pathfinding, the current objective, routes, and hints.

Everything here reads game state and returns plain data. The engine decides how to show it.
"""
from collections import deque

from . import areas, npcs, town
from .content import ITEMS, ROOMS

DIR_NAMES = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}


# ---------------------------------------------------------------------------- pathfinding
def open_exits(game, rid, respect_locks=True):
    room = ROOMS[rid]
    for d, dest in room["exits"].items():
        lock = room.get("locks", {}).get(d)
        if respect_locks and lock and not game.unlocked(lock):
            continue
        yield d, dest


def find_path(game, start, goal, respect_locks=True, known_only=False):
    """Shortest route as a list of (direction, room_id), or None.

    goal is a room id or a function room_id -> bool. With known_only, every room on the route
    (including the destination) must already have been visited.
    """
    test = goal if callable(goal) else (lambda rid: rid == goal)
    if test(start):
        return []
    seen = {start}
    queue = deque([(start, [])])
    while queue:
        rid, path = queue.popleft()
        for d, dest in open_exits(game, rid, respect_locks):
            if dest in seen:
                continue
            if known_only and dest not in game.visited:
                continue
            seen.add(dest)
            step = path + [(d, dest)]
            if test(dest):
                return step
            queue.append((dest, step))
    return None


def compress(path):
    """[(e, x), (n, y), (n, z)] -> [("east", 1), ("north", 2)] for reading aloud."""
    out = []
    for d, _ in path:
        if out and out[-1][0] == d:
            out[-1][1] += 1
        else:
            out.append([d, 1])
    return [(DIR_NAMES[d], n) for d, n in out]


def route_text(path):
    return ", ".join(name if n == 1 else "%s x%d" % (name, n) for name, n in compress(path))


def route_command(path):
    """The exact line to type to walk the route, using the game's own 'then' chaining."""
    return " then ".join(d for d, _ in path)


# ---------------------------------------------------------------------------- objectives
def _have(game, iid):
    return game.player.has_item(iid)


def _area_main_objective(game):
    """True when an area module offers a main (non-side) objective, which then stands in for "The story is told"."""
    found = []

    def probe(text, room, side=False):
        found.append(side)

    areas.call_each("OBJECTIVES", game, probe)
    return any(not side for side in found)


def objectives(game):
    """Ordered list of {"text", "room", "side"} the player could be working on. First is the main one."""
    f = game.flags
    out = []

    def add(text, room, side=False):
        out.append({"text": text, "room": room, "side": side})

    if f.get("wren_following") and not f.get("wren_home"):
        add("Take Wren home to Maeve at the Drowned Moth", "tavern")
    q = game.quest("main")
    if q in (-1, 0):
        add("Speak to Guildmaster Orrin", "hall")
    elif q in (1, 2) and not f.get("embers_set"):
        if not f.get("mother_dead"):
            add("Find the Antlered Mother in the White Grove (first Ember)", "mother_grove")
        elif not f.get("bishop_dead"):
            if not _have(game, "tide_key") and not f.get("reeve_dead"):
                add("Take the Tide Key from the drowned Reeve", "reeve_house")
            else:
                add("Open the chapel and face the Drowned Bishop (second Ember)", "bishop_altar")
        elif not f.get("choir_dead"):
            add("Find the Ash Choir under the chapel (third Ember)", "ash_choir")
        else:
            add("Take the three Embers down the Old Well", "well_bottom")
    elif q in (1, 2, 3):
        if not f.get("usher_dead"):
            add("Defeat the Pale Usher in the Usher's Hall", "lightwell_gate")
        else:
            add("Enter the Lightwell and end the long night", "lightwell")
    elif q == "done":
        if not f.get("steward_dead"):
            add("A black road runs east of the North Gate. Face the Steward of the Ember Court", "stewards_hall")
        elif not f.get("queen_dead"):
            add("Take the Crown Key to the throne room and face the Cinder Queen", "throne_room")
        elif not f.get("beacon_Ember Court"):
            add("Light the beacon in the Ember Court's throne room", "throne_room")
        elif not _area_main_objective(game):
            add("The story is told. Keep building Hollowmere, or visit the Wizard's Shop to replay it", "wizard_shop")
    # side objectives
    if game.quest("petals") == 0 and game.player.inventory.get("moonpetal", 0) >= 3:
        add("Bring Sister Ilse the three moonpetals", "chapel", True)
    elif game.quest("petals") == 0:
        add("Find three moonpetals in the Saltmarsh for Sister Ilse", "reedways", True)
    if game.quest("starsteel") == 1:
        add("Bring Brann the Starsteel Ore", "smithy", True)
    elif game.quest("starsteel") == 0 and not f.get("golem_dead"):
        add("Starsteel Ore for Brann is in the mines under the hill", "ore_vein", True)
    if game.quest("wayposts") == 0:
        left = [r for r in ("wood_path", "thicket", "moth_shrine") if not f.get("lit_" + r)]
        if left:
            add("Relight the dark wayposts in the Weeping Wood", left[0], True)
    if game.quest("wren") == -1:
        add("Maeve at the Drowned Moth is looking for someone", "tavern", True)
    if f.get("steward_dead") and not town.is_built(game, "ember_smithy"):
        add("Tamsin in the Court Forge would move to Hollowmere. Ask her, then see Joss", "court_forge", True)
    if (f.get("steward_dead") or "Ember Court" in f.get("visited_regions", [])) and "cellars" not in game.visited:
        add("The cellar stair under the Great Kitchens is shut. A Water or Ice book, equipped, would set it", "kitchens", True)
    areas.call_each("OBJECTIVES", game, add)
    return out


def main_objective(game):
    objs = [o for o in objectives(game) if not o["side"]]
    return objs[0] if objs else None


def describe(game, obj):
    """Add the route to an objective: steps, first direction, whether it is blocked."""
    if obj is None:
        return None
    info = dict(obj)
    room = ROOMS[obj["room"]]
    info["place"] = room["name"]
    path = find_path(game, game.room_id, obj["room"])
    if path is None:
        any_path = find_path(game, game.room_id, obj["room"], respect_locks=False)
        info["blocked"] = any_path is not None
        info["path"] = None
        info["steps"] = None
    else:
        info["blocked"] = False
        info["path"] = path
        info["steps"] = len(path)
    info["here"] = obj["room"] == game.room_id
    return info


def first_step(game):
    """The direction of the first step toward the main objective, or None."""
    info = describe(game, main_objective(game))
    if info and info["path"]:
        return info["path"][0][0], info["text"]
    return None


def objective_line(game):
    """A one-line status for the area screen."""
    info = describe(game, main_objective(game))
    if not info:
        return None
    if info["here"]:
        return "Objective: %s {grey}(you are here){/}" % info["text"]
    if info["path"]:
        return "Objective: %s {grey}- %s, %d step%s: %s{/}" % (
            info["text"], info["place"], info["steps"], "" if info["steps"] == 1 else "s", route_text(info["path"]))
    if info["blocked"]:
        return "Objective: %s {grey}- %s, but the way is sealed{/}" % (info["text"], info["place"])
    return "Objective: %s" % info["text"]


# ---------------------------------------------------------------------------- hints
BOSS_TIPS = {
    "mother_grove": "Go in with a full lantern and healing potions. She is a Hollow, so flares do double damage and blind her. Dodge or guard when ‼ Trample shows. "
                    "Kill the fawns fast, because their Bleat makes her hit harder.",
    "reeve_house": "He cannot be fled from. Flare to blind him so Tithe misses. Dodge or guard ‼ Sentence.",
    "bishop_altar": "Top up your lantern first. Below half health he regenerates, and burning stops it, so keep him "
                    "burning with flares and firepots. "
                    "Guard against ‼ Drown, and cure poison with Smelling Salts.",
    "ash_choir": "Kill Alto first, since she heals. Flare to blind all three. Guard when Bass shows ‼ Sundering Chord. "
                 "When one singer falls the others get angry for a few turns.",
    "stewards_hall": "He summons knights, so kill them first or keep him burning down while you guard. Fire is nothing to him: use Water or Ice books. Guard against Iron Verdict.",
    "throne_room": "You see her strength before you decide, and you can step back or run for free. Water and Ice are strong, fire is weak. Guard Cinder Cascade and Pyre, and kill the hounds she calls at once.",
    "lightwell_gate": "Flare to blind it so Snuff misses; Snuff drains your oil. Dodge or guard ‼ Reap.",
    "lightwell": "Top up your lantern and potions first (the Old Well lets you climb out to rest). In his talk, say \"Aldric\" if you have read page VI. When he wraps himself in shadow only a flare "
                 "can reach him, so keep 40+ oil. Dodge or guard every ‼ Black Sun.",
}


def boss_tip(room_id):
    """The hint for a boss room: the core's tips first, then the area modules'."""
    return BOSS_TIPS.get(room_id) or areas.collect("BOSS_TIPS").get(room_id)


def hint_lines(game):
    p = game.player
    lines = []
    info = describe(game, main_objective(game))
    if info:
        lines.append("{amber}Main goal:{/} %s" % info["text"])
        if info["here"]:
            lines.append("  You are already in the right place.")
        elif info["path"]:
            lines.append("  {b}%s{/}, %d step%s away." % (info["place"], info["steps"], "" if info["steps"] == 1 else "s"))
            lines.append("  Route: %s" % route_text(info["path"]))
            lines.append("  Type: {gold}%s{/}" % route_command(info["path"]))
        elif info["blocked"]:
            lines.append("  The way to %s is sealed. Check the map for the lock and what it needs." % info["place"])
        tip = boss_tip(info["room"])
        if tip:
            lines.append("  {grey}Tip: %s{/}" % tip)
    todo = []
    if p.points:
        todo.append("You have %d level-up point%s to spend. Type {gold}train{/}." % (p.points, "" if p.points == 1 else "s"))
    spare = p.inventory.get("oil", 0) + p.inventory.get("tallow", 0)
    if game.is_dark() and p.oil < 40:
        todo.append("Your lantern is low (%d oil)%s." % (p.oil, ". Type {gold}use oil{/}" if p.inventory.get("oil") else
                                                          ". Find oil, or rest at a lit place"))
    if game.room["region"] != "Hollowmere" and p.has_item("homecoming_charm") and p.relic_charges > 0 and (
            p.hp < p.max_hp * 0.4 or (game.is_dark() and p.oil < 25 and not p.inventory.get("oil"))):
        todo.append("You are in trouble. Type {gold}recall{/} to be home at once (%d charge%s left)." % (
            p.relic_charges, "" if p.relic_charges == 1 else "s"))
    from . import forge as _forge
    ready = _forge.ready_jobs(game)
    if ready:
        todo.append("%d forging%s ready at Brann's forge (east of Candle Lane). Type {gold}forge{/} there." % (
            len(ready), "" if len(ready) == 1 else "s"))
    from . import town as _town
    if _town.rent_due(game) >= 10:
        todo.append("%d gold of rent is waiting. Type {gold}collect{/} at home or the Builder's Yard." % _town.rent_due(game))
    heals = sum(p.inventory.get(i, 0) for i in ("draught", "strong_draught", "honeycake", "stew"))
    if heals < 2:
        todo.append("You are low on healing items. Buy some before a hard fight.")
    if game.flags.get("bounty_unclaimed"):
        todo.append("You have %d Hollow kills to claim at the bounty board in the Square." % game.flags["bounty_unclaimed"])
    room = game.room
    if room.get("waypost") and not game.flags.get("lit_" + game.room_id):
        todo.append("There is a cold waypost here. Type {gold}light{/} to relight it (10 oil).")
    news = [n for n in game.present_npcs() if npcs.has_news(game, n)]
    if news:
        spec = npcs.NPCS[news[0]]
        todo.append("%s has something new to say. Type {gold}talk %s{/}." % (spec["name"], spec.get("aliases", [news[0]])[0]))
    if todo:
        lines.append("")
        lines.append("{amber}Also:{/}")
        lines.extend("  - " + t for t in todo[:4])
    here = game.room["region"]
    side = sorted((o for o in objectives(game) if o["side"]), key=lambda o: ROOMS[o["room"]]["region"] != here)[:5]   # where you stand first
    if side:
        lines.append("")
        lines.append("{amber}Side quests:{/}")
        for o in side:
            lines.append("  - %s {grey}(%s){/}" % (o["text"], ROOMS[o["room"]]["name"]))
    if not lines:
        lines.append("Explore. Type {gold}map{/} to see where you have not been.")
    return lines


# ---------------------------------------------------------------------------- travel
def travel_targets(game):
    """Visited places you can walk to right now: [(room_id, path)] nearest first, excluding where you stand."""
    out = []
    for rid in game.visited:
        if rid == game.room_id or rid not in ROOMS:
            continue
        path = find_path(game, game.room_id, rid, known_only=True)
        if path:
            out.append((rid, path))
    out.sort(key=lambda t: (len(t[1]), ROOMS[t[0]]["name"]))
    return out


def match_place(game, text):
    """Find a visited place by name. Returns the room ids that match (exact name wins)."""
    text = text.lower().strip()
    if text in ("objective", "goal", "main"):
        obj = main_objective(game)
        return [obj["room"]] if obj else []
    names = {rid: ROOMS[rid]["name"].lower() for rid in game.visited if rid in ROOMS}
    exact = [rid for rid, n in names.items() if n == text or rid == text]
    if exact:
        return exact
    return [rid for rid, n in names.items() if text in n or any(w.startswith(text) for w in n.split())]
