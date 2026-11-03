"""Versioned save files.

Every save carries `save_version`. When the format changes, add a function to MIGRATIONS that
upgrades a save from version N to N+1, and bump SAVE_VERSION. Old saves then load cleanly.
(tests/test_save_migration.py fails the moment the version and the migrations disagree.)

What keeps a save safe:
  - Writes are atomic (temp file, then replace) and the previous save is kept as <slot>.bak.json.
  - Before an older save is upgraded, the original file is copied to <slot>.v<N>.bak.json. A copy is never
    overwritten: a different file of the same format gets <slot>.v<N>.bak.2.json, and so on.
  - A save from a newer game is never modified. Nothing here writes to it when it is read, and if an older
    game saves over one, a copy is kept the same way first.
  - A file that is not a usable save (unreadable, truncated, wrong shape) is renamed to <slot>.damaged.json,
    never deleted and never rotated over the good previous save (<slot>.bak.json), which the game can offer
    in its place.
"""
import copy
import json
import os
import re
import shutil

from . import paths

SAVE_VERSION = 2

# What Game.load needs to find in a save, and the type each must have.
REQUIRED = {"player": dict, "room": str, "flags": dict, "quests": dict, "visited": list, "room_items": dict,
            "stats": dict, "moves": int, "last_rest": str, "difficulty": (int, float), "diff_name": str}


class SaveError(Exception):
    pass


class SaveTooNew(SaveError):
    """The save was made by a newer game. It is left exactly as it is."""


class SaveDamaged(SaveError):
    """The save is unreadable, truncated, or missing pieces the game needs."""


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _dict(v):
    return v if isinstance(v, dict) else {}


def _copy(d):
    return copy.deepcopy(d) if isinstance(d, dict) else {}


# ------------------------------------------------------------------ migrations
# Each takes a save (a dict) and returns an upgraded copy. They never raise on odd input and never touch
# their argument, and running one twice changes nothing more.

def _migrate_0_to_1(d):
    # Saves from before versioning (and from the v1 prototype) just gain the field. A prototype save may
    # lack parts the game now expects, so those get the same starting values a new game has.
    d = _copy(d)
    for key in ("flags", "stats", "quests", "room_items"):
        if not isinstance(d.get(key), dict):
            d[key] = {}
    if not isinstance(d.get("visited"), list):
        d["visited"] = []
    if not _is_int(d.get("moves")):
        d["moves"] = 0
    if not isinstance(d.get("last_rest"), str):
        d["last_rest"] = "hall"
    if not isinstance(d.get("difficulty"), (int, float)) or isinstance(d.get("difficulty"), bool):
        d["difficulty"] = 1.0
    if not isinstance(d.get("diff_name"), str):
        d["diff_name"] = "Normal"
    return d


def _day_list(v):
    return [i for i in v if _is_int(i)] if isinstance(v, list) else []


def _day_map(v):
    """{day: [ware indexes]} with text keys, or {} for anything that is not that shape."""
    if not isinstance(v, dict):
        return {}
    return {str(k): _day_list(w) for k, w in v.items() if isinstance(w, list)}


def _migrate_1_to_2(d):
    """Darkness Dealer state moves out of the story flags into its own `dealers` block.

    A `dealers` block that is already there wins; the old flags only fill in what it lacks (what was bought
    on a day is merged, never dropped). The old flags are removed either way."""
    d = _copy(d)
    if not isinstance(d.get("flags"), dict):
        d["flags"] = {}
    flags = d["flags"]
    have = _dict(d.get("dealers"))
    old_bought = _day_map(flags.pop("dealer_bought", None))
    old_salt = flags.pop("dealer_salt", None)

    bought = _day_map(have.get("bought"))
    for day, idx in old_bought.items():
        bought[day] = bought.get(day, []) + [i for i in idx if i not in bought.get(day, [])]
    salt = have.get("salt") if _is_int(have.get("salt")) else (old_salt if _is_int(old_salt) else 0)
    restocks = have.get("restocks")
    restocks = {str(k): v for k, v in restocks.items() if _is_int(v)} if isinstance(restocks, dict) else {}
    out = {k: v for k, v in have.items() if k not in ("salt", "bought", "restocks")}   # keep anything extra
    out.update({"salt": salt, "bought": bought, "restocks": restocks})
    d["dealers"] = out
    return d


# MIGRATIONS[n] upgrades a save from version n to n + 1.
MIGRATIONS = {0: _migrate_0_to_1, 1: _migrate_1_to_2}


def check_registry():
    """Raises if SAVE_VERSION and MIGRATIONS disagree (a version bumped without its migration, or the reverse)."""
    if sorted(MIGRATIONS) != list(range(SAVE_VERSION)) or SAVE_VERSION != max(MIGRATIONS) + 1:
        raise SaveError("SAVE_VERSION is %d but MIGRATIONS has steps %s; every step 0..%d must exist."
                        % (SAVE_VERSION, sorted(MIGRATIONS), SAVE_VERSION - 1))


def version_of(data):
    """The save_version of a loaded save: 0 when absent (pre-versioning), None when it is not a whole number."""
    v = data.get("save_version", 0)
    return v if _is_int(v) and v >= 0 else None


def migrate(data):
    version = version_of(data) if isinstance(data, dict) else None
    if version is None:
        raise SaveDamaged("This save file does not look like a Lamplighter save.")
    if version > SAVE_VERSION:
        raise _too_new(version)
    while version < SAVE_VERSION:
        if version not in MIGRATIONS:
            raise SaveError("No migration from save format %d." % version)
        data = MIGRATIONS[version](data)
        version += 1
        data["save_version"] = version
    data["save_version"] = SAVE_VERSION
    return data


def _too_new(version):
    return SaveTooNew("This save is from a newer version of the game (save format %d; this game reads up to %d). "
                      "Your save file has not been changed. Update the game (run: python main.py --update), then try again." % (version, SAVE_VERSION))


# ------------------------------------------------------------------ files
def path_for(slot="main"):
    return os.path.join(paths.saves_dir(), "%s.json" % slot)


def _base(slot, suffix):
    """The path of <slot><suffix> without its .json, e.g. suffix '.v1.bak' or '.damaged'."""
    return path_for(slot)[:-5] + suffix


def _sibling(slot, suffix):
    return _base(slot, suffix) + ".json"


def backup_slot(slot="main"):
    """The slot name under which the previous save is kept (readable with read(backup_slot()))."""
    return slot + ".bak"


def exists(slot="main"):
    return os.path.exists(path_for(slot))


def is_set_aside(filename):
    """True for the files set_aside() makes (<slot>.damaged.json, <slot>.damaged.2.json ...). They are kept for the
    player, not saves, so anything that loads every save in the folder should skip them."""
    return re.search(r"\.damaged(\.\d+)?\.json$", filename) is not None


def _no_constant(name):
    # json.load accepts NaN, Infinity and -Infinity, which are not numbers the game can use (and write() refuses them)
    raise ValueError("%s is not a number" % name)


def _read_json(path):
    """The parsed file. FileNotFoundError when it is not there, SaveDamaged when it is not JSON (or is nested so
    deeply that the parser gives up). Any other OSError (a locked file, no permission) is passed on: that file is
    not known to be damaged, so nothing may be done to it."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f, parse_constant=_no_constant)
    except OSError:
        raise
    except (ValueError, RecursionError):
        raise SaveDamaged("The save file could not be read; it looks damaged or incomplete.")


def _check_shape(data):
    for key, kind in REQUIRED.items():
        if not isinstance(data.get(key), kind) or (kind is int and isinstance(data.get(key), bool)):
            raise SaveDamaged("This save is missing '%s' or it has the wrong kind of data." % key)


def _upgraded(data):
    """The save brought up to date and checked, or SaveTooNew / SaveDamaged. This is the one test of whether a
    file is a usable save; reading, writing and the title screen all use it."""
    try:
        data = migrate(data)
    except SaveError:
        raise
    except Exception as e:   # a migration meeting something truly unexpected
        raise SaveDamaged("This save could not be upgraded (%s: %s)." % (type(e).__name__, e))
    _check_shape(data)
    return data


def _state(path):
    """What is at path: ('missing'|'damaged'|'newer'|'ok', save_version)."""
    try:
        data = _read_json(path)
    except FileNotFoundError:
        return "missing", None
    except SaveDamaged:
        return "damaged", None
    version = version_of(data) if isinstance(data, dict) else None
    if version is None:
        return "damaged", None
    if version > SAVE_VERSION:
        return "newer", version     # a newer format cannot be checked, but it is somebody's progress
    try:
        _upgraded(data)
    except SaveError:
        return "damaged", None
    return "ok", version


def _same_bytes(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def keep_a_copy(slot, suffix):
    """Copy the slot's file to <slot><suffix>.json, or <slot><suffix>.2.json, .3.json ... Nothing already there is
    ever overwritten; if an identical copy exists it is reused. Returns (path of the copy, was_already_there)."""
    src = path_for(slot)
    base = _base(slot, suffix)
    n = 1
    while True:
        dst = base + (".json" if n == 1 else ".%d.json" % n)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
            return dst, False
        if _same_bytes(src, dst):
            return dst, True
        n += 1


def set_aside(slot="main"):
    """Rename an unreadable save to <slot>.damaged.json (or .damaged.2.json ...). Never overwrites, never deletes.
    Returns the new path, or None if there was no file."""
    src = path_for(slot)
    if not os.path.exists(src):
        return None
    dst = _sibling(slot, ".damaged")
    n = 2
    while os.path.exists(dst):
        dst = _sibling(slot, ".damaged.%d" % n)
        n += 1
    os.replace(src, dst)
    return dst


def restore_backup(slot="main"):
    """Make the previous save the current one, by copy (the .bak.json stays). The slot must have no live file."""
    src, dst = path_for(backup_slot(slot)), path_for(slot)
    if os.path.exists(dst):
        raise SaveError("There is already a save file to protect; it was not replaced.")
    shutil.copyfile(src, dst)
    return dst


def write(data, slot="main"):
    data = dict(data)
    data["save_version"] = SAVE_VERSION
    try:
        text = json.dumps(data, indent=1, allow_nan=False)    # a NaN would make a file this game then refuses to read
    except ValueError as e:
        raise OSError("the game holds a value that cannot be written (%s)" % e)
    os.makedirs(paths.saves_dir(), exist_ok=True)
    final = path_for(slot)
    tmp = final + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        kind, version = _state(final)
        if kind == "damaged":
            set_aside(slot)          # never let a broken file replace the good previous save
        elif kind == "newer":
            # A newer game's save: keep a copy before it is replaced. It is not rotated into .bak.json, which this
            # game could not read, so the previous save kept there stays what it is.
            keep_a_copy(slot, ".v%d.bak" % version)
        elif kind == "ok":
            if version < SAVE_VERSION:       # never reached by Continue (New game over an old file): still keep the original
                keep_a_copy(slot, ".v%d.bak" % version)
            _rotate(slot)
        os.replace(tmp, final)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return final


def _rotate(slot):
    """The current save becomes the previous save. It is copied, so the current file is never missing."""
    prev = backup_slot(slot)
    kind, version = _state(path_for(prev))
    if kind == "damaged":
        set_aside(prev)
    elif kind == "newer":
        keep_a_copy(prev, ".v%d.bak" % version)      # about to be overwritten, and it is a newer game's progress
    elif kind == "ok" and version < SAVE_VERSION:
        keep_a_copy(prev, ".v%d.bak" % version)      # an old-format previous save: keep it in its own format
    shutil.copyfile(path_for(slot), path_for(prev))


def read_info(slot="main", keep_copy=True):
    """Load a save, upgrading it if it is old. Returns (data, note).

    note is '' normally, or one plain line saying the save will be upgraded and where the original copy is.
    The original is copied (never over anything) before anything else happens; the file itself is only ever
    rewritten by write(). keep_copy=False reads without making that copy (for a look-before-you-load)."""
    path = path_for(slot)
    try:
        data = _read_json(path)
    except FileNotFoundError:
        raise SaveDamaged("The save file is missing.")
    version = version_of(data) if isinstance(data, dict) else None
    if version is None:
        raise SaveDamaged("This save file does not look like a Lamplighter save.")
    if version > SAVE_VERSION:
        raise _too_new(version)
    note = ""
    if version < SAVE_VERSION and keep_copy:
        lead = ("Your save was from an older version of the game (save format %d). It will be upgraded the next "
                "time you save." % version)
        try:
            keep, already = keep_a_copy(slot, ".v%d.bak" % version)
            note = "%s A copy of the original %s %s." % (lead, "was already kept at" if already else "was kept at", keep)
        except OSError as e:
            note = "%s A copy of the original could not be made (%s)." % (lead, e)
    return _upgraded(data), note


def read(slot="main"):
    return read_info(slot)[0]
