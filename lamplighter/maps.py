"""The map: a labelled picture of each region, and an overview of the whole world.

Region view draws every room you have visited as a named box, plus a dotted box for each exit you
have not taken yet. Icons in a box's top edge say what is there. Wide regions scroll to keep you in view.
"""
from . import navigation, npcs, ui
from .content import REGION_INFO, REGION_NAMES, ROOMS

BW, BH = 17, 4          # box width and height, including borders
GAPX, GAPY = 3, 1       # space between boxes, where the connectors go
STRIDE_X, STRIDE_Y = BW + GAPX, BH + GAPY

ICON_ORDER = ["@", "★", "☠", "!", "$", "+", "•"]
ICON_STYLE = {"@": "bgreen", "★": "gold", "☠": "bred", "!": "sky", "$": "gold", "+": "amber", "•": "bone"}
DIRECTIONS = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


class Canvas:
    def __init__(self):
        self.cells = {}

    def put(self, row, col, text, style=None):
        for i, ch in enumerate(text):
            self.cells[(row, col + i)] = (ch, style)

    def lines(self, rows, col_from, col_to):
        out = []
        for r in range(rows):
            parts, cur_style, cur = [], object(), ""
            for c in range(col_from, col_to):
                ch, style = self.cells.get((r, c), (" ", None))
                if style != cur_style:
                    if cur:
                        parts.append(_wrap(cur, cur_style))
                    cur, cur_style = "", style
                cur += ch
            if cur:
                parts.append(_wrap(cur, cur_style))
            out.append("".join(parts).rstrip())
        return out


def _wrap(text, style):
    return "{%s}%s{/}" % (style, text) if style and text.strip() else text


def _name_lines(name):
    """Fit a room name into two lines of the box."""
    width = BW - 4
    words, lines, cur = name.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lines = [l for l in lines if l]
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return [(l if len(l) <= width else l[:width - 1] + "…") for l in lines][:2]


def room_icons(game, rid):
    r = ROOMS[rid]
    have = set()
    if rid == game.room_id:
        have.add("@")
    obj = navigation.main_objective(game)
    if obj and obj["room"] == rid:
        have.add("★")
    if r.get("boss") and not game.flags.get(r["boss"]):
        have.add("☠")
    people = r.get("npcs", [])
    if any(npcs.has_news(game, n) for n in people):
        have.add("!")
    if any(npcs.NPCS[n].get("shop") for n in people):
        have.add("$")
    if r.get("rest") or (r.get("waypost") and game.flags.get("lit_" + rid)):
        have.add("+")
    if game.room_items.get(rid):
        have.add("•")
    return [i for i in ICON_ORDER if i in have][:3]


def _border_style(game, rid):
    if rid == game.room_id:
        return "bgreen"
    obj = navigation.main_objective(game)
    if obj and obj["room"] == rid:
        return "gold"
    return "ash" if game.is_dark(rid) else "amber"


def _draw_box(canvas, row, col, name_lines, border, icons=(), stairs=(), dotted=False, text_style=None):
    h, v = ("┄", "┆") if dotted else ("─", "│")
    top = "┌" + h * (BW - 2) + "┐"
    bottom = "└" + h * (BW - 2) + "┘"
    canvas.put(row, col, top, border)
    canvas.put(row + BH - 1, col, bottom, border)
    for i in range(BH - 2):
        text = name_lines[i] if i < len(name_lines) else ""
        canvas.put(row + 1 + i, col, v, border)
        canvas.put(row + 1 + i, col + BW - 1, v, border)
        canvas.put(row + 1 + i, col + 1, text.center(BW - 2), text_style)
    # icons sit in the top edge, right aligned
    x = col + BW - 2
    for ic in reversed(list(icons)):
        canvas.put(row, x, ic, ICON_STYLE[ic])
        x -= 2
    # stairs sit in the bottom edge
    for k, s in enumerate(stairs):
        canvas.put(row + BH - 1, col + 3 + 2 * k, s, "grey")


def region_rooms(region):
    return [rid for rid, r in ROOMS.items() if r["region"] == region]


def render_region(game, region=None):
    """Returns (lines, legend_lines). `region` defaults to where the player stands."""
    region = region or game.room["region"]
    shown = [rid for rid in region_rooms(region) if rid in game.visited]
    if not shown:
        return None, None
    stubs = {}
    for rid in shown:
        r = ROOMS[rid]
        for d, dest in r["exits"].items():
            if d in DIRECTIONS and dest not in game.visited and ROOMS[dest]["region"] == region:
                lock = r.get("locks", {}).get(d)
                sealed = bool(lock and not game.unlocked(lock))
                stubs[dest] = "sealed" if sealed else "unexplored"
    cells = shown + [s for s in stubs]
    xs = [ROOMS[r]["pos"][0] for r in cells]
    ys = [ROOMS[r]["pos"][1] for r in cells]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    cols, rows = maxx - minx + 1, maxy - miny + 1
    canvas = Canvas()

    def origin(rid):
        x, y = ROOMS[rid]["pos"]
        return (y - miny) * STRIDE_Y, (x - minx) * STRIDE_X

    for rid in shown:
        r = ROOMS[rid]
        row, col = origin(rid)
        stairs = ("▲" if "u" in r["exits"] else "", "▼" if "d" in r["exits"] else "")
        _draw_box(canvas, row, col, _name_lines(r["name"]), _border_style(game, rid), room_icons(game, rid),
                  [s for s in stairs if s])
    for rid, label in stubs.items():
        row, col = origin(rid)
        _draw_box(canvas, row, col, ["?"] + [label], "grey", dotted=True, text_style="grey")

    # connectors between boxes that are next to each other (drawn from each visited room, all four ways)
    present = set(shown) | set(stubs)
    for rid in shown:
        r = ROOMS[rid]
        row, col = origin(rid)
        for d in DIRECTIONS:
            dest = r["exits"].get(d)
            if not dest or dest not in present or ROOMS[dest]["region"] != region:
                continue
            lock = r.get("locks", {}).get(d)
            sealed = bool(lock and not game.unlocked(lock))
            style = "bred" if sealed else "ash"
            if d == "e":
                canvas.put(row + 1, col + BW, "─#─" if sealed else "───", style)
            elif d == "w":
                canvas.put(row + 1, col - GAPX, "─#─" if sealed else "───", style)
            elif d == "s":
                canvas.put(row + BH, col + BW // 2, "#" if sealed else "│", style)
            else:
                canvas.put(row - GAPY, col + BW // 2, "#" if sealed else "│", style)

    width = ui.width() - 2
    fit = max(1, (width + GAPX) // STRIDE_X)
    start = 0
    notes = []
    if cols > fit:
        pcol = None
        for rid in shown:
            if rid == game.room_id:
                pcol = ROOMS[rid]["pos"][0] - minx
        if pcol is None:
            pcol = 0
        start = max(0, min(pcol - fit // 2, cols - fit))
        if start > 0:
            notes.append("◄ the map continues west (%d more column%s)" % (start, "" if start == 1 else "s"))
        if start + fit < cols:
            notes.append("► the map continues east (%d more column%s)" % (cols - start - fit, "" if cols - start - fit == 1 else "s"))
    shown_cols = min(cols, fit)
    col_from = start * STRIDE_X
    col_to = col_from + shown_cols * STRIDE_X - GAPX
    total_rows = rows * STRIDE_Y - GAPY
    lines = canvas.lines(total_rows, col_from, col_to)

    # exits that lead out of this region
    leaves = []
    for rid in shown:
        r = ROOMS[rid]
        for d, dest in r["exits"].items():
            if ROOMS[dest]["region"] != region:
                lock = r.get("locks", {}).get(d)
                sealed = lock and not game.unlocked(lock)
                leaves.append("%s (%s) leads to %s%s" % (r["name"], navigation.DIR_NAMES[d], ROOMS[dest]["region"],
                                                        " {bred}[sealed]{/}" if sealed else ""))
    legend = [
        "{bgreen}@{/} you   {gold}★{/} objective   {bred}☠{/} unbeaten boss   {sky}!{/} someone has news   "
        "{gold}${/} shop   {amber}+{/} safe to rest   {bone}•{/} items to pick up",
        "{amber}amber{/} lit · {ash}grey{/} dark · {grey}dotted{/} not explored yet · {bred}#{/} sealed · "
        "{grey}▲▼{/} stairs up or down",
    ]
    legend += ["{grey}%s{/}" % n for n in notes]
    legend += ["{grey}Exit: %s{/}" % l for l in leaves]
    return lines, legend


def region_summary(game, region):
    rooms = region_rooms(region)
    seen = sum(1 for r in rooms if r in game.visited)
    bosses = [ROOMS[r]["boss"] for r in rooms if ROOMS[r].get("boss")]
    beaten = sum(1 for flag in bosses if game.flags.get(flag))
    return seen, len(rooms), beaten, len(bosses)


def render_world(game):
    lines = []
    cross = {}
    for rid, r in ROOMS.items():
        for d, dest in r["exits"].items():
            a, b = r["region"], ROOMS[dest]["region"]
            if a != b:
                cross.setdefault((a, b), []).append("%s (%s)" % (r["name"], navigation.DIR_NAMES[d]))
    for name in sorted(REGION_NAMES, key=lambda n: REGION_INFO[n]["ring"]):
        info = REGION_INFO[name]
        seen, total, beaten, bosses = region_summary(game, name)
        here = "  {bgreen}<- you are here{/}" if game.room["region"] == name else ""
        ring = "home" if info["ring"] == 0 else "ring %d" % info["ring"]
        lines.append("{b}%s{/}  {grey}%s · levels %s · gear %s{/}%s" % (name, ring, info["levels"], info["gear"], here))
        lines.append("  %s" % info["blurb"])
        bar = ui.bar(seen, total, 14, full="amber")
        lines.append("  explored %s %d/%d%s" % (bar, seen, total,
                                                "     bosses beaten %d/%d" % (beaten, bosses) if bosses else ""))
        links = [(b, w) for (a, b), w in cross.items() if a == name]
        for b, where in sorted(links):
            lines.append("  {grey}-> %s from %s{/}" % (b, where[0]))
        lines.append("")
    return lines
