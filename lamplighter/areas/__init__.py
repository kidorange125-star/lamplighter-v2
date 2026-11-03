"""Area modules: new places add their scripted bits here, in their own file, without touching the core.

Every module in this package is imported on first use. Each may define any of these (all optional):

  ENTER         {room_id: fn(g, first) -> bool}     entering a room; return True if the event took over the room
  UNLOCK        {(room_id, direction): fn(g)}       a lock was just opened
  LEAVE         {(src, dest): fn(g)}                walking from src to dest
  AFTER_FIXED   {flag: fn(g)}                       a fixed fight that sets this flag was just won
  AFTER_BEACON  {region_id: fn(g)}                  a region's beacon was just lit
  ON_REST       fn(g)                               the player rested
  NPCS          {npc_id: {"name", "aliases", "desc", "shop"?, "where"?}}   people, same shape as npcs.NPCS
  talk_<npc_id> fn(g)                               what an NPC says (module-level function)
  STOCK         {npc_id: [item ids]}                a shop's wares
  PRESENT       {npc_id: fn(g) -> bool}             is this person at the place the room data puts them?
  NEWS          {npc_id: fn(g) -> bool}             do they have something new to say?
  OBJECTIVES    fn(game, add)                       call add(text, room_id, side=False) for each objective
  BOSS_TIPS     {room_id: str}                      the hint for a boss room
  CHECK         fn() -> [error strings]             extra validator checks for this module

Hooks added for the M6 areas (see docs/M6-SPEC.md section 17):
  TOPICS        {npc_id: fn(g) -> [(label, handler(g))]}   extra talk topics for an EXISTING npc; merged across modules
  EXTRA_NEWS    {npc_id: fn(g) -> bool}                    an EXISTING npc also has news; OR-ed with the core rule
  SELLS         {npc_id: fn(g) -> [item ids]}              extra wares for an existing shop; merged across modules
  RUMOURS       fn(g) -> [str]                             lines for Maeve's rumour pool
  PRICES        {item_id: gold}                            shop price overrides (a duplicate key is an error)
  AFTER_GAIN    {item_id: fn(g)}                           an item was just received (a duplicate key is an error)
Unlike NPCS/STOCK/NEWS, the first four add to what the core already has and never replace it.

Rooms, enemies, items and buildings are plain JSON: rooms/*.json, enemies/*.json, items/*.json, buildings/*.json
and regions/*.json in lamplighter/data. Keep one file per area.
"""
import importlib
import pkgutil

_mods = []
_loaded = [False]


def modules():
    if not _loaded[0]:
        _loaded[0] = True
        for info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
            _mods.append(importlib.import_module("%s.%s" % (__name__, info.name)))
    return _mods


def collect(attr):
    """All the dicts called `attr` from every module, merged. A duplicate key is an error."""
    out = {}
    for m in modules():
        for k, v in getattr(m, attr, {}).items():
            if k in out:
                raise ValueError("%s: %r is defined by two area modules (%s)" % (attr, k, m.__name__))
            out[k] = v
    return out


def call_each(attr, *args):
    for m in modules():
        fn = getattr(m, attr, None)
        if fn:
            fn(*args)


def lookup(attr, key, *args):
    """Run the hook registered under `key` in any module. Returns (found, result)."""
    for m in modules():
        fn = getattr(m, attr, {}).get(key)
        if fn:
            return True, fn(*args)
    return False, None


def check():
    errs = []
    for m in modules():
        fn = getattr(m, "CHECK", None)
        if fn:
            errs.extend("%s: %s" % (m.__name__.rsplit(".", 1)[-1], e) for e in fn())
    return errs


# ---------------------------------------------------------------------------- merged hooks
def merged(attr):
    """{key: [value, ...]} from every module's dict called `attr`. Unlike `collect`, the same key may repeat."""
    out = {}
    for m in modules():
        for k, v in getattr(m, attr, {}).items():
            out.setdefault(k, []).append(v)
    return out


def topics(g, nid):
    """Extra talk topics for an existing NPC: [(label, handler)] from every module, in module order."""
    out = []
    for fn in merged("TOPICS").get(nid, []):
        out.extend(fn(g))
    return out


def extra_news(g, nid):
    return any(fn(g) for fn in merged("EXTRA_NEWS").get(nid, []))


def sells(g, nid):
    out = []
    for fn in merged("SELLS").get(nid, []):
        for iid in fn(g):
            if iid not in out:
                out.append(iid)
    return out


def rumours(g):
    out = []
    for m in modules():
        fn = getattr(m, "RUMOURS", None)
        if fn:
            out.extend(fn(g))
    return out


def give_first(g, iid, n=1):
    """Hand over a piece of named gear once ever (a boss call-back must not duplicate it). True if it was given."""
    if g.flags.get("got_" + iid):
        return False
    g.flags["got_" + iid] = True
    g.give(iid, n)
    return True
