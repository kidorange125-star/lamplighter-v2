"""The `update` command: fetch a newer copy of the game's code from GitHub and swap it in safely.

Nothing here runs unless the player types `update` (or runs `python main.py --update`): no background
checks, no telemetry. The flow, each step able to stop the whole thing before anything is changed:

    1. read <repo>/<branch>/version.json, compare versions, show "What's new", ask
    2. make the staging folder (so a read-only game folder stops things before anything is spent), then
       back up the saves folder; a backup made for an install that then fails is removed again
    3. download the repo zip (https, fixed host list, size caps)
    4. extract it into the staging folder, rejecting anything dodgy, keeping only the code paths
    5. check the new tree: version, layout, the content validator, a save-migration dry run (subprocess)
    6. swap the old code paths for the new ones, rolling back completely on any error; only after the
       swap works are the oldest backups tidied (the last 5 are kept)

A swap that is cut short by a power loss or a kill leaves a marker file (SWAP_MARKER); main.py puts the
old files back from .update_old on the next start (see recover_interrupted_update there).

Saves and settings live in the data folder (see paths.py), never in the game folder, so replacing the
game folder's code cannot touch them. All network access goes through a transport object with one
method, get(url, max_bytes) -> bytes, so tests can serve an in-memory zip and never touch the network.
"""
import io
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.parse
import ssl
import zipfile
import zlib
import http.client

from . import paths

# ----------------------------------------------------------------------------- limits and names

ALLOWED_HOSTS = ("raw.githubusercontent.com", "codeload.github.com", "github.com")
USER_AGENT = "Lamplighter-Updater"
DEFAULT_BRANCH = "main"

MAX_VERSION_BYTES = 256 * 1024
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_MEMBERS = 3000
MAX_UNCOMPRESSED = 30 * 1024 * 1024     # the whole game is about 1.5 MB of code, docs and tests
MAX_MEMBER_BYTES = 5 * 1024 * 1024
MAX_RATIO = 100           # a file of RATIO_FREE_BYTES or more may not shrink more than this when zipped
RATIO_FREE_BYTES = 256 * 1024
MAX_NAME_LEN = 200
MAX_PART_LEN = 100
MAX_DEPTH = 12
NET_TIMEOUT = 10          # seconds for each network wait
DOWNLOAD_DEADLINE = 300   # seconds for a whole download
CHECK_TIMEOUT = 120       # seconds for each verification subprocess
BACKUPS_KEEP = 5
CHANGELOG_SHOWN = 25

# The only paths an update ever installs (relative to the game folder).
ALLOWED_DIRS = ("lamplighter", "tools", "tests", "docs")
ALLOWED_FILES = ("main.py", "version.json", "README.md")
ALLOWED_NAMES = ALLOWED_DIRS + ALLOWED_FILES
# Anything else in the archive (saves, config, .github, scratch files...) is ignored, never installed.
OLD_DIR = ".update_old"
STAGE_DIR = ".update_new"
SWAP_MARKER = ".update_swap"

_WINDOWS_DEVICES = {"con", "prn", "aux", "nul", "conin$", "conout$"}
_WINDOWS_DEVICES |= {"com%d" % i for i in range(0, 10)} | {"lpt%d" % i for i in range(0, 10)}
_WINDOWS_DEVICES |= {"com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"}
_BAD_NAME_CHARS = set('<>:"|?*')


class UpdateError(Exception):
    """Any reason the update stops. `touched` is True only if game files may be left changed."""

    def __init__(self, message, touched=False):
        Exception.__init__(self, message)
        self.touched = touched


# ----------------------------------------------------------------------------- text safety

def clean_text(value, limit=300):
    """Make text from a remote file safe to print: no control characters, no colour-tag braces."""
    s = "".join(" " if unicodedata.category(ch)[0] == "C" else ch for ch in str(value))
    s = " ".join(s.replace("{", "(").replace("}", ")").split())
    return s if len(s) <= limit else s[:limit - 3] + "..."


def why(e, limit=200):
    """The plain reason an exception happened, for a message. str(OSError) repeats paths with doubled
    backslashes, and shutil.Error holds a list of failures, so both are unpacked by hand."""
    if isinstance(e, shutil.Error) and e.args and isinstance(e.args[0], list) and e.args[0]:
        first = e.args[0][0]
        if isinstance(first, tuple) and len(first) == 3:
            return clean_text("%s (%s)" % (first[2], os.path.basename(str(first[0]))), limit)
    if isinstance(e, OSError) and e.strerror:
        names = [os.path.basename(str(n)) for n in (e.filename, e.filename2) if n]
        return clean_text(e.strerror + (" (%s)" % ", ".join(names) if names else ""), limit)
    return clean_text("%s: %s" % (type(e).__name__, e) if str(e) else type(e).__name__, limit)


# ----------------------------------------------------------------------------- versions

_VERSION_RE = re.compile(r"(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})"
                         r"(?:-([0-9A-Za-z.-]{1,64}))?(?:\+[0-9A-Za-z.-]{1,64})?")


def version_key(text):
    """A sortable key for a version like 2.0.0-dev.6. Raises UpdateError for anything unrecognised.

    Pre-release versions sort below the release (2.0.0-dev.6 < 2.0.0); pre-release parts compare
    number-to-number (dev.9 < dev.10), numbers below words, a shorter list below a longer one."""
    if not isinstance(text, str) or not _VERSION_RE.fullmatch(text):
        raise UpdateError("I do not understand the version %s. A version looks like 2.0.0 or 2.0.0-dev.6." %
                          clean_text(repr(text), 44))
    m = _VERSION_RE.fullmatch(text)
    core = tuple(int(m.group(i)) for i in (1, 2, 3))
    pre = m.group(4)
    if pre is None:
        return core + (1, ())
    ids = []
    for part in pre.split("."):
        if not part:
            raise UpdateError("I do not understand the version %s (empty pre-release part)." % clean_text(repr(text), 44))
        if part.isdigit():
            if len(part) > 9 or (len(part) > 1 and part[0] == "0"):
                raise UpdateError("I do not understand the version %s (bad number %r)." % (clean_text(repr(text), 44), part))
            ids.append((0, int(part), ""))
        else:
            ids.append((1, 0, part))
    return core + (0, tuple(ids))


def compare_versions(a, b):
    """-1, 0 or 1 as version a is older than, equal to, or newer than b."""
    ka, kb = version_key(a), version_key(b)
    return (ka > kb) - (ka < kb)


# ----------------------------------------------------------------------------- configuration

_OWNER_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
_REPO_NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")
_BRANCH_PART_RE = re.compile(r"[A-Za-z0-9._-]+")


def valid_repo(text):
    """True for owner/name with GitHub's allowed characters."""
    if not isinstance(text, str) or text.count("/") != 1:
        return False
    owner, name = text.split("/")
    return (bool(_OWNER_RE.fullmatch(owner)) and len(owner) <= 39 and bool(_REPO_NAME_RE.fullmatch(name))
            and name not in (".", ".."))


def valid_branch(text):
    if not isinstance(text, str) or not text or len(text) > 100 or text.startswith("-"):
        return False
    for part in text.split("/"):
        if (not _BRANCH_PART_RE.fullmatch(part) or part in (".", "..") or part.startswith(".")
                or part.endswith(".lock")):
            return False
    return ".." not in text


class Source:
    """Where updates come from: repo and branch, and which setting each came from."""

    def __init__(self, repo, branch, repo_from, branch_from):
        self.repo, self.branch, self.repo_from, self.branch_from = repo, branch, repo_from, branch_from

    def raw_version_url(self):
        return "https://raw.githubusercontent.com/%s/%s/version.json" % (self.repo, self.branch)

    def zip_url(self):
        return "https://codeload.github.com/%s/zip/refs/heads/%s" % (self.repo, self.branch)


def _read_json_object(path, what):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, RecursionError) as e:
        raise UpdateError("I could not read %s (%s). Fix it or delete it." % (what, clean_text(e, 100)))
    if not isinstance(data, dict):
        raise UpdateError("%s should hold a JSON object like {\"repo\": \"owner/name\"}." % what)
    return data


def config_path(data_dir):
    return os.path.join(data_dir, "config.json")


def load_source(data_dir, game_root, env):
    """Repo and branch: environment, then <data_dir>/config.json, then the game's version.json.

    The repo is empty ("") until the owner sets one. Each key is looked up on its own. A bad value in the
    player's own settings (environment, config.json) is an error that names it; a bad value in version.json
    is skipped, because that file arrives with an update and the player could otherwise never fix it."""
    cfg = _read_json_object(config_path(data_dir), "config.json in " + data_dir)
    ver = _read_json_object(os.path.join(game_root, "version.json"), "this game's version.json")
    candidates = {
        "repo": [("LAMPLIGHTER_REPO", (env.get("LAMPLIGHTER_REPO") or "").strip()),
                 ("config.json", cfg.get("repo")), ("version.json", ver.get("repo"))],
        "branch": [("LAMPLIGHTER_BRANCH", (env.get("LAMPLIGHTER_BRANCH") or "").strip()),
                   ("config.json", cfg.get("branch")), ("version.json", ver.get("branch"))],
    }
    picked = {}
    for key, options in candidates.items():
        picked[key] = ("", "")
        for where, value in options:
            if value is None or value == "":
                continue
            ok = valid_repo(value) if key == "repo" else valid_branch(value)
            if not ok and where == "version.json":
                continue
            if not ok:
                hint = ("a repo looks like owner/name, for example octocat/lamplighter" if key == "repo"
                        else "a branch is a name like main or release/1.0")
                raise UpdateError("The %s in %s (%r) is not valid: %s." % (key, where, clean_text(value, 60), hint))
            picked[key] = (value, where)
            break
    branch, branch_from = picked["branch"]
    if not branch:
        branch, branch_from = DEFAULT_BRANCH, "default"
    return Source(picked["repo"][0], branch, picked["repo"][1], branch_from)


def save_repo(data_dir, repo):
    save_config(data_dir, repo=repo)


def save_config(data_dir, **values):
    """Write keys into config.json, keeping any other keys. Atomic."""
    cfg = _read_json_object(config_path(data_dir), "config.json in " + data_dir)
    cfg.update(values)
    os.makedirs(data_dir, exist_ok=True)
    final = config_path(data_dir)
    tmp = final + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)
    os.replace(tmp, final)


# ----------------------------------------------------------------------------- network

def check_url(url):
    """Raise UpdateError unless url is https to exactly one of ALLOWED_HOSTS. Pure; no network."""
    shown = clean_text(url, 80)
    if not isinstance(url, str) or any(ch in url for ch in "\\ \t\r\n\x00") or any(ord(ch) < 32 for ch in url):
        raise UpdateError("Refusing the address %r." % shown)
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        raise UpdateError("Refusing the address %r." % shown)
    if parts.scheme != "https":
        raise UpdateError("Refusing %r: updates only use https." % shown)
    host = (parts.hostname or "")
    if host not in ALLOWED_HOSTS or parts.username is not None or parts.password is not None \
            or parts.netloc.lower() not in (host, host + ":443") or port not in (None, 443):
        raise UpdateError("Refusing %r: updates only talk to %s." % (shown, ", ".join(ALLOWED_HOSTS)))
    return url


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if it stays on the allowed hosts over https."""
    max_redirections = 4

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)


class HttpsTransport:
    """The real transport: https only, a fixed host list, a fixed User-Agent and nothing else sent."""

    def __init__(self, timeout=None, deadline=None):
        self.timeout = NET_TIMEOUT if timeout is None else timeout
        self.deadline = DOWNLOAD_DEADLINE if deadline is None else deadline

    def get(self, url, max_bytes):
        check_url(url)
        opener = urllib.request.build_opener(_SafeRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        shown = clean_text(url, 80)
        started = time.monotonic()
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                check_url(resp.geturl())
                length = resp.headers.get("Content-Length")
                if length and length.isdigit() and int(length) > max_bytes:
                    raise UpdateError("%s is larger than the %d byte limit." % (shown, max_bytes))
                # read1 hands back whatever has arrived (at least one byte), so a connection that trickles
                # in a byte at a time still reaches the deadline check below; read(n) would sit until n
                # bytes had come.
                read = getattr(resp, "read1", None) or resp.read
                chunks, total = [], 0
                while True:
                    chunk = read(min(65536, max_bytes + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise UpdateError("%s is larger than the %d byte limit." % (shown, max_bytes))
                    if time.monotonic() - started > self.deadline:
                        raise UpdateError("Downloading %s took too long." % shown)
                    chunks.append(chunk)
                return b"".join(chunks)
        except UpdateError:
            raise
        except urllib.error.HTTPError as e:
            e.close()
            raise UpdateError("%s answered HTTP %d." % (shown, e.code))
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as e:
            reason = getattr(e, "reason", e)
            raise UpdateError("Could not reach %s (%s)." % (shown, clean_text(reason, 100)))


# ----------------------------------------------------------------------------- remote version.json

def parse_remote_version(raw):
    """Validate the bytes of a version.json. Returns {"version", "released", "changelog"}."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError, AttributeError):
        raise UpdateError("version.json is not valid JSON.")
    if not isinstance(data, dict):
        raise UpdateError("version.json should be a JSON object.")
    version = data.get("version")
    version_key(version)
    changelog = data.get("changelog", [])
    if not isinstance(changelog, list) or len(changelog) > 500 or not all(isinstance(x, str) for x in changelog):
        raise UpdateError("version.json has a changelog that is not a list of text lines.")
    released = data.get("released")
    return {"version": version, "released": released if isinstance(released, str) else "", "changelog": changelog,
            "repo": data.get("repo"), "branch": data.get("branch")}


# ----------------------------------------------------------------------------- zip handling

def _member_parts(info):
    """Validate one zip member's name and type, whatever it is. Returns (parts, is_dir). Raises UpdateError.

    These are the checks that apply to every member, installed or not: anything that could escape a folder,
    or be a link, a device or an encrypted file, stops the whole update."""
    name = info.filename
    shown = clean_text(name, 60)
    if not name:
        raise UpdateError("The download has a file name that is empty.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name) or "\\" in name:
        raise UpdateError("The download has a suspicious file name (%r)." % shown)
    if name.startswith("/") or re.match(r"[A-Za-z]:", name):
        raise UpdateError("The download has an absolute path (%r)." % shown)
    if info.flag_bits & 0x1:
        raise UpdateError("The download has an encrypted file (%r)." % shown)
    mode = info.external_attr >> 16
    kind = stat.S_IFMT(mode)
    if kind == stat.S_IFLNK:
        raise UpdateError("The download has a symbolic link (%r)." % shown)
    if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or info.external_attr & 0x400:
        raise UpdateError("The download has a special file (%r)." % shown)
    is_dir = name.endswith("/")
    parts = (name[:-1] if is_dir else name).split("/")
    for part in parts:
        if part in ("", ".", ".."):
            raise UpdateError("The download has a path that climbs out of its folder (%r)." % shown)
    return parts, is_dir


def _check_installable(info, parts):
    """The checks only for members that will really be written: a name Windows could misread, a path that is
    too long or deep, a file that is huge or unpacks to far more than it weighs zipped. Files the update
    ignores (a .github folder, an assets folder) are never written, so they cannot trip these."""
    name = info.filename
    shown = clean_text(name, 60)
    if len(name) > MAX_NAME_LEN:
        raise UpdateError("The download has a file name that is too long (%r)." % shown)
    if len(parts) > MAX_DEPTH:
        raise UpdateError("The download has a path that is nested too deeply (%r)." % shown)
    for part in parts:
        if len(part) > MAX_PART_LEN or _BAD_NAME_CHARS & set(part) or part[-1] in ". ":
            raise UpdateError("The download has a file name Windows would misread (%r)." % shown)
        if part.split(".")[0].rstrip(" ").casefold() in _WINDOWS_DEVICES:
            raise UpdateError("The download has a device name (%r)." % shown)
    if info.file_size > MAX_MEMBER_BYTES:
        raise UpdateError("The download would unpack to far more data than the game's code ever needs (%r)." % shown)
    if info.file_size >= RATIO_FREE_BYTES and info.file_size > MAX_RATIO * max(info.compress_size, 1):
        raise UpdateError("The download has a file that unpacks to far more data than it takes to send (%r)." % shown)


def plan_archive(zf):
    """Check every member and work out what to install. Returns [(rel_parts, info, is_dir)].

    The one wrapper folder GitHub adds is stripped exactly once; only ALLOWED_NAMES are kept. Size and name
    limits are applied to what is kept, not to the rest of the repo."""
    infos = zf.infolist()
    if not infos:
        raise UpdateError("The download is an empty zip file.")
    if len(infos) > MAX_MEMBERS:
        raise UpdateError("The download has too many files (%d; the limit is %d)." % (len(infos), MAX_MEMBERS))
    entries = [(_member_parts(i), i) for i in infos]
    wrappers = {parts[0] for (parts, _), _ in entries}
    if len(wrappers) != 1 or any(len(parts) == 1 and not is_dir for (parts, is_dir), _ in entries):
        raise UpdateError("The download does not have the single wrapper folder that GitHub's zip files have.")
    plan, seen, total = [], set(), 0
    for (parts, is_dir), info in entries:
        rel = parts[1:]
        if not rel or "__pycache__" in rel:
            continue
        top = rel[0]
        if top in ALLOWED_DIRS:
            if len(rel) == 1 and not is_dir:
                continue
        elif top in ALLOWED_FILES:
            if len(rel) != 1 or is_dir:
                continue
        else:
            continue
        _check_installable(info, parts)
        total += info.file_size
        if total > MAX_UNCOMPRESSED:
            raise UpdateError("The download would unpack to far more data than the game's code ever needs.")
        key = "/".join(rel).casefold()
        if key in seen:
            raise UpdateError("The download lists %r twice." % clean_text("/".join(rel), 60))
        seen.add(key)
        plan.append((rel, info, is_dir))
    return plan


def extract_plan(zf, plan, dest):
    """Write the planned members under dest, re-checking containment as each one is written."""
    base = os.path.realpath(dest)
    total = 0
    for rel, info, is_dir in plan:
        target = os.path.normpath(os.path.join(base, *rel))
        if os.path.commonpath([base, target]) != base or target == base:
            raise UpdateError("The download has a path that escapes its folder (%r)." % clean_text("/".join(rel), 60))
        if is_dir:
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.commonpath([base, os.path.realpath(os.path.dirname(target))]) != base:
            raise UpdateError("The download has a path that escapes its folder (%r)." % clean_text("/".join(rel), 60))
        written = 0
        with zf.open(info) as src, open(target, "xb") as dst:
            while True:
                chunk = src.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                total += len(chunk)
                if written > MAX_MEMBER_BYTES or total > MAX_UNCOMPRESSED:
                    raise UpdateError("The download unpacks to more data than it declared.")
                dst.write(chunk)


# ----------------------------------------------------------------------------- filesystem helpers

def _rmtree(path):
    """Delete a folder, clearing read-only flags first (Windows refuses otherwise)."""
    def fix(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


_BACKUP_RE = re.compile(r"\d{8}-\d{6}-[0-9A-Za-z._+-]+")

_DRY_RUN = r"""
import json, os, sys
sys.path.insert(0, os.getcwd())
from lamplighter import save
bad = []
for path in sys.argv[1:]:
    try:
        with open(path, encoding="utf-8-sig") as f:   # the same as save.py, so a Notepad-edited save is fine
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a save (expected a JSON object)")
        save.migrate(data)
    except Exception as e:
        bad.append("%s: %s: %s" % (os.path.basename(path), type(e).__name__, e))
if bad:
    print("\n".join(bad))
    sys.exit(1)
"""


# <slot>.damaged.json and <slot>.damaged.2.json are unreadable on purpose: the game sets a damaged save aside there
# instead of deleting it. <slot>.v1.bak.json is the copy the game keeps of an older (or newer) save before it
# changes it. None of these is a save the game loads, so the migration dry run must not try to load them.
_SET_ASIDE_RE = re.compile(r"\.damaged(\.\d+)?\.json$|\.v\d+\.bak(\.\d+)?\.json$")


def _save_files(folder):
    """The save files in a folder (every .json except the damaged ones the game has set aside), sorted."""
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if n.endswith(".json") and not _SET_ASIDE_RE.search(n) and os.path.isfile(os.path.join(folder, n)))


# ----------------------------------------------------------------------------- the updater

def _default_confirm(question):
    try:
        return input(question + " [y/n] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


class Updater:
    """Everything the `update` command does. Paths, transport and clock are all injectable for tests."""

    def __init__(self, out=print, confirm=None, transport=None, game_root=None, data_dir=None, env=None,
                 now=None, run_checks=None, cli=False):
        self.out = out
        self.confirm = confirm or _default_confirm
        self.transport = transport
        self.game_root = os.path.abspath(game_root or paths.game_root())
        self.data_dir = os.path.abspath(data_dir or paths.data_dir())
        self.env = os.environ if env is None else env
        self.now = now or (lambda: time.strftime("%Y%m%d-%H%M%S"))
        self.run_checks = run_checks or self._subprocess_checks
        self.cli = cli           # True for `python main.py --update`: wording that makes sense with no game running
        self.swapped = False     # True once the new files are all in place
        self._move = os.rename   # forward moves during the swap; tests replace it to inject failures

    # ------------------------------------------------------------------ small things
    def _net(self):
        if self.transport is None:
            self.transport = HttpsTransport()
        return self.transport

    def _fetch(self, url, max_bytes):
        try:
            data = self._net().get(url, max_bytes)
        except UpdateError:
            raise
        except OSError as e:
            raise UpdateError("Could not reach the server (%s)." % why(e, 100))
        if not isinstance(data, (bytes, bytearray)):
            raise UpdateError("The server sent something that is not data.")
        if len(data) > max_bytes:
            raise UpdateError("The download is larger than the %d byte limit." % max_bytes)
        return bytes(data)

    def source(self):
        return load_source(self.data_dir, self.game_root, self.env)

    def current_version(self):
        raw = _read_json_object(os.path.join(self.game_root, "version.json"), "this game's version.json")
        v = raw.get("version")
        return v if isinstance(v, str) else "unknown"

    def _no_repo(self, checking=True):
        how = "python main.py --update repo owner/name" if self.cli else "update repo owner/name"
        lines = ["No update repo is set, so there is nothing to check." if checking else "No update repo is set.",
                 "To set one, %s: %s" % ("run" if self.cli else "type", how),
                 "For example: %s" % how.replace("owner/name", "octocat/lamplighter"),
                 "You can also set the LAMPLIGHTER_REPO environment variable."]
        if checking:
            lines.append("Nothing is contacted until you %s." % ("run update" if self.cli else "type update"))
        for line in lines:
            self.out(line)

    # ------------------------------------------------------------------ commands
    def show_repo(self):
        src = self.source()
        if not src.repo:
            self._no_repo(checking=False)
            return
        self.out("Updates come from %s, branch %s (repo from %s, branch from %s)." %
                 (src.repo, src.branch, src.repo_from, src.branch_from))

    def set_repo(self, text):
        if not valid_repo(text):
            raise UpdateError("%r is not a repo. A repo looks like owner/name, for example octocat/lamplighter." %
                              clean_text(text, 60))
        save_repo(self.data_dir, text)
        self.out("Update repo saved: %s (in %s)." % (text, config_path(self.data_dir)))
        env_repo = (self.env.get("LAMPLIGHTER_REPO") or "").strip()
        if env_repo and env_repo != text:
            self.out("Note: the LAMPLIGHTER_REPO environment variable (%s) still takes priority over this setting." %
                     clean_text(env_repo, 60))
        self.out("%s to look for a new version." % ("Run python main.py --update check" if self.cli else "Type update check"))

    def check(self):
        return self._run(check_only=True, force=False)

    def update(self, force=False):
        return self._run(check_only=False, force=force)

    # ------------------------------------------------------------------ the flow
    def _run(self, check_only, force):
        src = self.source()
        if not src.repo:
            self._no_repo()
            return False
        cur = self.current_version()
        self.out("Checking %s (branch %s)..." % (src.repo, src.branch))
        info = parse_remote_version(self._fetch(src.raw_version_url(), MAX_VERSION_BYTES))
        new = info["version"]
        try:
            rel = compare_versions(new, cur)
        except UpdateError:
            if not force:
                raise UpdateError("I cannot read this copy's own version (%s), so I cannot tell whether %s is newer. "
                                  "Type update force to install it anyway." % (clean_text(repr(cur), 44), new))
            rel = 1
        if rel <= 0 and not (force and not check_only):
            self.out("You are up to date (version %s)." % cur)
            if rel < 0:
                self.out("The repository lists an older version (%s). Type update force to install it anyway." % new)
            return False
        if rel > 0:
            self.out("Version %s is available. You have %s." % (new, cur))
        else:
            self.out("Forced: the repository lists version %s and you have %s." % (new, cur))
        self._show_changelog(info)
        if check_only:
            self.out("Type update to install it.")
            return False
        if self.cli:
            self.out("Your saves are backed up first.")
        else:
            self.out("Your saves are backed up first. Progress since your last save is not in the backup, "
                     "so type save first if you want it kept.")
        if not self.confirm("Install version %s now?" % new):
            self.out("Okay. Nothing was changed.")
            return False
        self._install(src, cur, info, force)
        return True

    def _show_changelog(self, info):
        lines = info["changelog"]
        if not lines:
            return
        self.out("What's new in %s%s:" % (info["version"], " (%s)" % clean_text(info["released"], 30) if info["released"] else ""))
        for line in lines[:CHANGELOG_SHOWN]:
            self.out("  - " + clean_text(line))
        if len(lines) > CHANGELOG_SHOWN:
            self.out("  ...and %d more." % (len(lines) - CHANGELOG_SHOWN))

    def _install(self, src, cur, info, force):
        root = self.game_root
        stage = os.path.join(root, STAGE_DIR)
        new = info["version"]
        if os.path.exists(os.path.join(root, SWAP_MARKER)):
            raise UpdateError("An earlier update was cut short and has not been put right yet. Close the game and "
                              "start it again: it puts your earlier game files back first.")
        try:
            if os.path.lexists(stage):
                _rmtree(stage)
        except OSError as e:
            raise UpdateError("I could not clear an old temporary folder (%s): %s." % (stage, why(e)))
        backup, new_info, keep_stage, done = None, None, False, False
        try:
            try:   # first, so a game folder that cannot be written to stops things before a backup is spent
                os.mkdir(stage)
                tree = os.path.join(stage, "tree")
                os.mkdir(tree)
            except OSError as e:
                raise UpdateError("I could not make a temporary folder inside the game folder (%s). Is the game folder "
                                  "read-only? It needs to be writable to update." % why(e))
            self.out("Backing up your saves...")
            backup = self._backup_saves(cur)
            self.out("Downloading version %s..." % new)
            data = self._fetch(src.zip_url(), MAX_ZIP_BYTES)
            self.out("Unpacking and checking it...")
            try:
                self._unpack(data, tree)
                new_info = self._verify_tree(tree, cur, info, force)
                self.run_checks(tree, stage)
            except OSError as e:
                raise UpdateError("I could not prepare the new files (%s)." % why(e))
            self.out("Installing...")
            self._swap(tree, stage)
            done = True
        except UpdateError as e:
            keep_stage = e.touched      # the old files may be in there: do not delete the only copy
            raise
        finally:
            if not done and not keep_stage and backup:
                try:    # nothing was installed, so this attempt's backup is a copy of saves that never changed
                    _rmtree(backup)
                except OSError:
                    pass
            try:
                if not keep_stage and os.path.lexists(stage):
                    _rmtree(stage)
            except OSError:
                self.out("I could not remove the temporary folder %s. It is safe to delete." % stage)
        self.out("Updated: version %s -> version %s." % (cur, new))
        try:
            if backup:
                self._rotate_backups(os.path.dirname(backup), keep=backup)
            self._keep_source(src, new_info)
        except Exception as e:   # the update itself is done; never report these as a failure
            self.out("Note: %s" % why(e))
        if backup and os.path.isdir(backup):
            self.out("Your saves were not touched. A backup of them is in %s" % backup)
        else:
            self.out("Your saves were not touched. There were none to back up yet.")
        self.out("The previous game files are kept in %s until the next update." % os.path.join(root, OLD_DIR))
        self.out("Restart the game to use version %s. This session is still running the old code." % new)

    def _keep_source(self, src, new_info):
        """The new version.json arrived over the network, so it must not quietly redirect later updates.

        If it names a different repo or branch than this update used, say so, and when version.json (or the
        default) was what chose the source, save the one that was used into config.json, which wins."""
        differs, pin = [], {}
        for key, mine, mine_from, theirs in (("repo", src.repo, src.repo_from, new_info.get("repo")),
                                             ("branch", src.branch, src.branch_from, new_info.get("branch"))):
            if isinstance(theirs, str) and theirs and theirs.casefold() != mine.casefold():
                differs.append("%s %s" % (key, clean_text(theirs, 60)))
                if mine_from in ("version.json", "default"):
                    pin[key] = mine
        if not differs:
            return
        self.out("Note: the new version.json points updates at a different %s. This update came from %s, branch %s." %
                 (" and ".join(differs), src.repo, src.branch))
        if pin:
            save_config(self.data_dir, **pin)
            self.out("I saved %s in %s so later updates keep coming from there. To change that, %s: update repo "
                     "owner/name" % (" and ".join("%s %s" % kv for kv in pin.items()), config_path(self.data_dir),
                                     "run python main.py --update repo owner/name" if self.cli else "type"))
        else:
            self.out("Your own setting (the environment variable or config.json) still decides where updates come from.")

    # ------------------------------------------------------------------ step: backup
    def _backup_saves(self, old_version):
        """Copy the saves folder to backups/<time>-<version>. Does not tidy old backups: that waits until the
        update has worked, so a failed attempt can never push a good older backup out."""
        saves = os.path.join(self.data_dir, "saves")
        if not os.path.isdir(saves):
            return None
        base = os.path.join(self.data_dir, "backups")
        label = "%s-%s" % (self.now(), re.sub(r"[^0-9A-Za-z._+-]", "_", old_version)[:40])
        dest, n = os.path.join(base, label), 1
        while os.path.lexists(dest):
            n += 1
            dest = os.path.join(base, "%s-%d" % (label, n))
        try:
            os.makedirs(base, exist_ok=True)
            shutil.copytree(saves, dest)
        except BaseException as e:    # including Ctrl-C: never leave a half-copied backup that looks like a real one
            try:
                if os.path.isdir(dest):
                    _rmtree(dest)
            except OSError:
                pass
            if isinstance(e, (OSError, shutil.Error)):
                raise UpdateError("I could not back up your saves (%s), so I stopped." % why(e))
            raise
        return dest

    def _rotate_backups(self, base, keep=None):
        """Delete the oldest backups beyond BACKUPS_KEEP. The backup named by `keep` (the one just made) is
        never deleted, whatever the clock said when it was named."""
        try:
            names = [n for n in os.listdir(base) if _BACKUP_RE.fullmatch(n)
                     and os.path.isdir(os.path.join(base, n)) and not os.path.islink(os.path.join(base, n))]
            names.sort(key=lambda n: (n[:15], os.path.getmtime(os.path.join(base, n)), n))
            keep_name = os.path.basename(keep) if keep else None
            surplus = len(names) - BACKUPS_KEEP
            for n in [n for n in names if n != keep_name][:max(surplus, 0)]:
                _rmtree(os.path.join(base, n))
        except OSError as e:
            self.out("Note: I could not tidy old backups (%s)." % why(e))

    # ------------------------------------------------------------------ step: unpack and verify
    def _unpack(self, data, tree):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except (zipfile.BadZipFile, ValueError, OSError):
            raise UpdateError("The download is not a valid zip file.")
        try:
            with zf:
                plan = plan_archive(zf)
                extract_plan(zf, plan, tree)
        except (zipfile.BadZipFile, NotImplementedError, EOFError, RuntimeError, zlib.error) as e:
            raise UpdateError("The download is damaged or uses something I do not support (%s)." % clean_text(e, 100))

    def _verify_tree(self, tree, cur, info, force):
        """Check the unpacked tree. Returns its parsed version.json."""
        vpath = os.path.join(tree, "version.json")
        if not os.path.isfile(vpath):
            raise UpdateError("The new version has no version.json.")
        with open(vpath, "rb") as f:
            new_info = parse_remote_version(f.read(MAX_VERSION_BYTES + 1))
        new = new_info["version"]
        if new != info["version"]:
            raise UpdateError("The download is version %s but the repository announced %s. Try again in a minute." %
                              (new, info["version"]))
        try:
            newer = compare_versions(new, cur) > 0
        except UpdateError:
            newer = False
        if not newer and not force:
            raise UpdateError("The download (version %s) is not newer than yours (%s). Type update force to install it "
                              "anyway." % (new, cur))
        # A repo or branch that is written but not valid would leave this game unable to update at all.
        for key, check in (("repo", valid_repo), ("branch", valid_branch)):
            value = new_info.get(key)
            if value not in (None, "") and not check(value):
                raise UpdateError("The new version's version.json has a %s (%s) that is not valid, so installing it "
                                  "would stop updates from working." % (key, clean_text(repr(value), 64)))
        if not os.path.isfile(os.path.join(tree, "main.py")):
            raise UpdateError("The new version has no main.py.")
        if not os.path.isfile(os.path.join(tree, "lamplighter", "__init__.py")):
            raise UpdateError("The new version has no lamplighter folder.")
        if not os.path.isfile(os.path.join(tree, "tools", "validate_content.py")):
            raise UpdateError("The new version has no content checker (tools/validate_content.py), so I cannot verify it.")
        return new_info

    def _subprocess_env(self, home):
        env = {k: v for k, v in os.environ.items() if k not in ("LAMPLIGHTER_REPO", "LAMPLIGHTER_BRANCH")}
        env["LAMPLIGHTER_HOME"] = home
        return env

    def _run_python(self, args, tree, home, what, tidy=None):
        """Run python -I -B on the new tree and raise UpdateError if it fails or runs too long.

        Output goes to a temporary file, not a pipe: a pipe that a leftover child process still holds open
        would make the timeout wait for that child. On a timeout the whole process tree is killed."""
        popen = {"start_new_session": True} if os.name != "nt" else {}
        try:
            with tempfile.TemporaryFile() as log:
                proc = subprocess.Popen([sys.executable, "-I", "-B"] + args, cwd=tree, env=self._subprocess_env(home),
                                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **popen)
                try:
                    proc.wait(timeout=CHECK_TIMEOUT)
                except subprocess.TimeoutExpired:
                    _kill_tree(proc)
                    raise UpdateError("%s did not finish within %d seconds." % (what, CHECK_TIMEOUT))
                except BaseException:      # Ctrl-C: do not leave the checker running
                    _kill_tree(proc)
                    raise
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 65536))
                text = log.read().decode("utf-8", "replace")
        except OSError as e:
            raise UpdateError("I could not run %s (%s)." % (what, why(e, 100)))
        if proc.returncode != 0:
            lines = [clean_text(l, 300) for l in text.splitlines() if l.strip()]
            if tidy:
                lines = tidy(lines)
            detail = " | ".join(lines[-6:]) if lines else "no details (exit code %d)" % proc.returncode
            raise UpdateError("%s failed: %s" % (what, detail))

    def _subprocess_checks(self, tree, stage):
        """The content validator, then a migration dry run of the new code against copies of the saves."""
        home = os.path.join(stage, "home")
        os.makedirs(home, exist_ok=True)
        self._run_python([os.path.join(tree, "tools", "validate_content.py")], tree, home,
                         "The new version's content check")
        saves = os.path.join(self.data_dir, "saves")
        if not os.path.isdir(saves):
            return
        copy = os.path.join(stage, "saves_copy")
        shutil.copytree(saves, copy)
        files = _save_files(copy)
        if files:
            self._run_python(["-c", _DRY_RUN] + files, tree, home,
                             "Loading your saves with the new version", tidy=_tidy_save_errors)

    # ------------------------------------------------------------------ step: swap with rollback
    def _swap(self, tree, stage):
        root = self.game_root
        old_dir = os.path.join(root, OLD_DIR)
        marker = os.path.join(root, SWAP_MARKER)
        prev = os.path.join(stage, "previous_old")
        incoming = [n for n in ALLOWED_NAMES if os.path.lexists(os.path.join(tree, n))]
        existing = [n for n in ALLOWED_NAMES if os.path.lexists(os.path.join(root, n))]
        undo = []        # closures that reverse each step done so far
        current = [""]   # the file or folder being moved, for the message

        def move(src, dst):
            current[0] = os.path.basename(src)
            self._move(src, dst)
            undo.append(lambda: os.rename(dst, src))

        # If the power goes or the process is killed part way, this file is how main.py knows, on the next
        # start, that the old files in .update_old must be put back before anything is imported.
        try:   # written whole or not at all, so main.py never meets half a marker
            with open(marker + ".tmp", "w", encoding="utf-8") as f:
                json.dump({"incoming": incoming, "existing": existing, "had_old": os.path.lexists(old_dir)}, f)
            os.replace(marker + ".tmp", marker)
        except OSError as e:
            _remove_quietly(marker + ".tmp")
            raise UpdateError("I could not write to the game folder (%s)." % why(e))
        try:
            if os.path.lexists(old_dir):
                move(old_dir, prev)
            os.mkdir(old_dir)
            undo.append(lambda: os.rmdir(old_dir))
            for name in ALLOWED_NAMES:
                here = os.path.join(root, name)
                if os.path.lexists(here):
                    move(here, os.path.join(old_dir, name))
                if name in incoming:
                    move(os.path.join(tree, name), here)
        except BaseException as e:
            problems = []
            for step in reversed(undo):
                try:
                    step()
                except OSError as e2:
                    problems.append(why(e2))
            if problems:   # the marker stays, so the next start of the game tries again
                try:
                    left = ", ".join(sorted(os.listdir(old_dir))) or "nothing"
                except OSError:
                    left = "unknown"
                raise UpdateError("The update failed (%s) and I could not put everything back (%s). Your previous "
                                  "files are in %s (%s) and an older copy may be in %s. Starting the game again tries "
                                  "to put them back; or copy them back into %s yourself." %
                                  (why(e), "; ".join(problems), old_dir, left, prev, root), touched=True)
            _remove_quietly(marker)
            if not isinstance(e, Exception):
                raise
            raise UpdateError("The update failed while moving %s (%s). Everything was put back as it was. If this "
                              "keeps happening, close anything that has the game folder open (an editor, antivirus, "
                              "another copy of the game) and try again." % (current[0] or "files", why(e)))
        _remove_quietly(marker)
        self.swapped = True


def _tidy_save_errors(lines):
    """Make the dry run's complaints something a player can act on."""
    out = []
    for line in lines:
        # save.py's too-new message says to update the game, which is no use while we are installing it
        line = re.sub(r"\s*Update the game(?: \([^)]*\))?[^.]*\.", "", line)
        out.append(line)
    if any("JSONDecodeError" in l or "UnicodeDecodeError" in l for l in out):
        out.append("If that file is a broken save, start the game and choose Continue (it sets broken saves aside), "
                   "or move the file out of the saves folder, then run update again.")
    return out


def _kill_tree(proc):
    """Kill a process and anything it started. Best effort; never raises."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.kill()
        proc.wait(timeout=10)
    except Exception:
        pass


def _remove_quietly(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ----------------------------------------------------------------------------- entry point for the game and main.py

def usage(cli=False):
    pre = "python main.py --update" if cli else "update"
    return [pre + "            check for a new version and install it",
            "%s check      only look, change nothing" % pre,
            "%s force      install even if the version is not newer" % pre,
            "%s repo       show where updates come from" % pre,
            "%s repo owner/name   set where updates come from" % pre]


def run_command(noun, out, confirm, cli=False, **kw):
    """Run `update <noun>`. Returns a process exit code: 0 fine (including up to date), 1 stopped."""
    words = noun.split()

    def ask(question):
        try:
            return confirm(question)
        except EOFError:     # input has run out (a pipe, a closed terminal): that is a no
            return False
    u = Updater(out=out, confirm=ask, cli=cli, **kw)
    try:
        if not words:
            u.update()
        elif words == ["check"]:
            u.check()
        elif words == ["force"]:
            u.update(force=True)
        elif words[0] == "repo" and len(words) == 1:
            u.show_repo()
        elif words[0] == "repo" and len(words) == 2:
            u.set_repo(words[1])
        else:
            for line in usage(cli):
                out(line)
            return 1
        return 0
    except UpdateError as e:
        out("Update stopped: %s" % e)
        out("Some of your game files may have been changed; see above." if e.touched
            else "Your game files and saves were not changed.")
        return 1
    except KeyboardInterrupt:
        # an interrupted swap has already put everything back by the time this arrives
        if u.swapped:
            out("Interrupted, but the new files were already in place. Restart the game to use them.")
            return 0
        out("Update cancelled. Your game files and saves were not changed.")
        return 1
    except Exception as e:   # never let an updater bug crash the game
        out("Update stopped by an unexpected problem (%s: %s). Your game files and saves were not changed." %
            (type(e).__name__, clean_text(e, 120)))
        return 1
