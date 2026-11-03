"""The `update` command (docs section 2.13). Everything here is offline.

The network is replaced by an in-memory transport serving a real zip built in the test; the game
root and data folder are temp folders, so the real game is never touched. Setup also makes any real
socket use fail the test, which proves the offline claim rather than assuming it.
"""
import codecs
import hashlib
import io
import json
import os
import socket
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import zipfile
from unittest import mock

from lamplighter import paths, update
from lamplighter.update import UpdateError
from tests.helpers import new_game, run, temp_home

OLD = "2.0.0-dev.6"
NEW = "2.0.0-dev.7"
REPO = "owner/game"
VERSION_URL = "https://raw.githubusercontent.com/owner/game/main/version.json"
ZIP_URL = "https://codeload.github.com/owner/game/zip/refs/heads/main"
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------- builders

def stub_files(version, validator_ok=True, changelog=("A new thing.",)):
    """A tiny game: just enough for the real validator subprocess and migration dry run to run."""
    validator = ("import sys\nprint('stub validator')\nsys.exit(0)\n" if validator_ok else
                 "import sys\nprint('1 problem(s):')\nprint('  - room x points at nothing')\nsys.exit(1)\n")
    return {
        "main.py": b"print('new game')\n",
        "version.json": json.dumps({"version": version, "changelog": list(changelog)}).encode(),
        "README.md": b"new readme\n",
        "lamplighter/__init__.py": b"",
        "lamplighter/new_only.py": b"X = 1\n",
        "lamplighter/save.py": (b"class SaveError(Exception):\n    pass\n\n\ndef migrate(data):\n"
                                b"    if data.get('poison'):\n        raise SaveError('poisoned save')\n"
                                b"    return data\n"),
        "tools/validate_content.py": validator.encode(),
        "tests/test_new.py": b"# new tests\n",
        "docs/new.md": b"new docs\n",
    }


def make_zip(files, wrapper="game-main", extra=(), dirs=True):
    """A zip like GitHub's: one wrapper folder around everything. extra = [(name, bytes, external_attr)]."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if wrapper and dirs:
            zf.writestr(zipfile.ZipInfo(wrapper + "/"), b"")
        for path, data in files.items():
            info = zipfile.ZipInfo((wrapper + "/" if wrapper else "") + path)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
        for name, data, attr in extra:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = attr if attr is not None else 0o100644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def write_tree(root, files):
    for rel, data in files.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


def make_old_root(root, version=OLD):
    write_tree(root, {
        "main.py": b"print('old game')\n",
        "version.json": json.dumps({"version": version, "repo": "", "branch": "main", "changelog": []}).encode(),
        "README.md": b"old readme\n",
        "lamplighter/__init__.py": b"",
        "lamplighter/old_only.py": b"OLD = 1\n",
        "tools/validate_content.py": b"# old validator\n",
        "tests/test_old.py": b"# old test\n",
        "docs/old.md": b"old docs\n",
        "notes.txt": b"the player's own file, not part of the game\n",
    })


def snapshot(root):
    """{relative path: sha256 or '<dir>'} for everything under root."""
    snap = {}
    for here, dirs, files in os.walk(root):
        for d in dirs:
            snap[os.path.relpath(os.path.join(here, d), root)] = "<dir>"
        for f in files:
            with open(os.path.join(here, f), "rb") as fh:
                snap[os.path.relpath(os.path.join(here, f), root)] = hashlib.sha256(fh.read()).hexdigest()
    return snap


class FakeTransport:
    """Serves bytes by URL, records every request, and enforces max_bytes like the real transport."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, max_bytes):
        self.calls.append(url)
        got = self.routes.get(url)
        if got is None:
            raise UpdateError("%s answered HTTP 404." % url)
        if isinstance(got, BaseException):
            raise got
        if len(got) > max_bytes:
            raise UpdateError("%s is larger than the %d byte limit." % (url, max_bytes))
        return got


class Env:
    """A temp game root + data folder + fake server, and a way to run `update` against them."""

    def __init__(self, tmp, tag="a", new_version=NEW, files=None, zip_bytes=None, announce=None, saves=True,
                 old_version=OLD, **stub_kw):
        self.root = os.path.join(tmp, "game_" + tag)
        self.home = os.path.join(tmp, "home_" + tag)
        os.makedirs(self.home)
        make_old_root(self.root, old_version)
        if saves:
            write_tree(self.home, {"saves/main.json": b'{"save_version": 1, "hp": 9}',
                                   "saves/main.bak.json": b'{"save_version": 1, "hp": 8}'})
        files = files if files is not None else stub_files(new_version, **stub_kw)
        self.zip = zip_bytes if zip_bytes is not None else make_zip(files)
        announced = {"version": announce or new_version, "released": "2026-11-02",
                     "changelog": ["A new thing.", "Another {red}thing{/}."]}
        self.transport = FakeTransport({VERSION_URL: json.dumps(announced).encode(), ZIP_URL: self.zip})
        self.lines = []
        self.questions = []
        self._tick = 0

    def clock(self):
        self._tick += 1
        return "20261101-1200%02d" % self._tick

    def updater(self, answer=True, **kw):
        def confirm(question):
            self.questions.append(question)
            return answer
        args = dict(out=self.lines.append, confirm=confirm, transport=self.transport, game_root=self.root,
                    data_dir=self.home, env={"LAMPLIGHTER_REPO": REPO}, now=self.clock)
        args.update(kw)
        return update.Updater(**args)

    def run(self, noun="", answer=True, **kw):
        """Run `update <noun>` through the same entry point the game uses. Returns the exit code."""
        args = dict(transport=self.transport, game_root=self.root, data_dir=self.home,
                    env={"LAMPLIGHTER_REPO": REPO}, now=self.clock)
        args.update(kw)

        def confirm(question):
            self.questions.append(question)
            return answer
        return update.run_command(noun, self.lines.append, confirm, **args)

    @property
    def text(self):
        return "\n".join(self.lines)

    def read(self, rel, root=None):
        with open(os.path.join(root or self.root, *rel.split("/")), "rb") as f:
            return f.read()


class OfflineCase(unittest.TestCase):
    """Base: a temp folder, and any real network use fails the test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        for target in ("socket.getaddrinfo", "socket.create_connection"):
            p = mock.patch(target, side_effect=AssertionError("the network was touched"))
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(socket.socket, "connect", side_effect=AssertionError("the network was touched"))
        p.start()
        self.addCleanup(p.stop)

    def tearDown(self):
        update_dirs = []
        for here, dirs, _ in os.walk(self.tmp):
            update_dirs += [os.path.join(here, d) for d in dirs if d in (update.OLD_DIR, update.STAGE_DIR)]
        for d in update_dirs:
            update._rmtree(d)
        self._tmp.cleanup()

    def env(self, tag="a", **kw):
        return Env(self.tmp, tag, **kw)

    def assertUntouched(self, env, before):
        self.assertEqual(snapshot(env.root), before, "the game folder changed")
        self.assertFalse(os.path.exists(os.path.join(env.root, update.STAGE_DIR)))
        self.assertFalse(os.path.exists(os.path.join(env.root, update.OLD_DIR)))


# --------------------------------------------------------------------------- versions

class VersionTests(unittest.TestCase):
    ORDER = [
        "1.9.9", "2.0.0-0", "2.0.0-1", "2.0.0-alpha", "2.0.0-alpha.1", "2.0.0-alpha.beta", "2.0.0-beta",
        "2.0.0-beta.2", "2.0.0-beta.11", "2.0.0-dev.1", "2.0.0-dev.6", "2.0.0-dev.9", "2.0.0-dev.10",
        "2.0.0-rc.1", "2.0.0", "2.0.1-dev.1", "2.0.1", "2.0.10", "2.1.0", "10.0.0",
    ]

    def test_strictly_increasing_table(self):
        for i, a in enumerate(self.ORDER):
            for b in self.ORDER[i + 1:]:
                self.assertEqual(update.compare_versions(a, b), -1, "%s should be older than %s" % (a, b))
                self.assertEqual(update.compare_versions(b, a), 1, "%s should be newer than %s" % (b, a))
            self.assertEqual(update.compare_versions(a, a), 0)

    def test_the_cases_the_brief_names(self):
        self.assertEqual(update.compare_versions("2.0.0-dev.6", "2.0.0"), -1)    # pre-release below the release
        self.assertEqual(update.compare_versions("2.0.0-dev.10", "2.0.0-dev.9"), 1)
        self.assertEqual(update.compare_versions("2.0.0-dev.7", "2.0.0-dev.6"), 1)

    def test_build_metadata_is_ignored(self):
        self.assertEqual(update.compare_versions("2.0.0+build5", "2.0.0"), 0)
        self.assertEqual(update.compare_versions("2.0.0-dev.6+abc", "2.0.0-dev.6"), 0)

    def test_unknown_formats_are_errors_not_crashes(self):
        for bad in ["", "unknown", "2", "2.0", "v2.0.0", "2.0.0-", "2.0.0-dev..1", "2.0.0-01", "01.0.0", "2.0.0.0",
                    "2.0.0 ", " 2.0.0", "2.0.0\n", "2.0.0-dev.6\n", "2.0.0-d_v", "-1.0.0", "2.0.0-" + "a" * 70,
                    "9999999999.0.0", "\u0662.0.0", None, 5, 2.0, ["2.0.0"], b"2.0.0"]:
            with self.assertRaises(UpdateError, msg=repr(bad)):
                update.version_key(bad)
            with self.assertRaises(UpdateError, msg=repr(bad)):
                update.compare_versions(bad, "2.0.0")

    def test_parse_remote_version_validates(self):
        ok = update.parse_remote_version(b'{"version": "2.0.0", "changelog": ["a", "b"], "released": "2026-01-01"}')
        self.assertEqual(ok["version"], "2.0.0")
        self.assertEqual(ok["changelog"], ["a", "b"])
        self.assertEqual(update.parse_remote_version(b'{"version": "2.0.0"}')["changelog"], [])
        for bad in [b"", b"nope", b"[]", b'"2.0.0"', b"{}", b'{"version": 2}', b'{"version": "banana"}',
                    b'{"version": "2.0.0", "changelog": "x"}', b'{"version": "2.0.0", "changelog": [1]}',
                    b'{"version": "2.0.0", "changelog": ' + b"[" * 100000 + b"}", b"\xff\xfe\x00"]:
            with self.assertRaises(UpdateError, msg=repr(bad[:40])):
                update.parse_remote_version(bad)


# --------------------------------------------------------------------------- configuration

class ConfigTests(OfflineCase):
    def dirs(self):
        home, root = os.path.join(self.tmp, "home"), os.path.join(self.tmp, "root")
        os.makedirs(home)
        os.makedirs(root)
        return home, root

    def test_empty_by_default_and_main_branch(self):
        home, root = self.dirs()
        write_tree(root, {"version.json": b'{"version": "2.0.0", "repo": "", "branch": "main"}'})
        src = update.load_source(home, root, {})
        self.assertEqual((src.repo, src.branch), ("", "main"))

    def test_precedence_env_then_config_then_version_json(self):
        home, root = self.dirs()
        write_tree(root, {"version.json": b'{"version": "2.0.0", "repo": "v/json", "branch": "vbranch"}'})
        src = update.load_source(home, root, {})
        self.assertEqual((src.repo, src.repo_from, src.branch), ("v/json", "version.json", "vbranch"))
        write_tree(home, {"config.json": b'{"repo": "c/config", "branch": "cbranch"}'})
        src = update.load_source(home, root, {})
        self.assertEqual((src.repo, src.repo_from, src.branch, src.branch_from), ("c/config", "config.json", "cbranch", "config.json"))
        src = update.load_source(home, root, {"LAMPLIGHTER_REPO": "e/env", "LAMPLIGHTER_BRANCH": "ebranch"})
        self.assertEqual((src.repo, src.repo_from, src.branch), ("e/env", "LAMPLIGHTER_REPO", "ebranch"))

    def test_each_key_falls_through_on_its_own(self):
        home, root = self.dirs()
        write_tree(root, {"version.json": b'{"version": "2.0.0", "repo": "v/json", "branch": "vbranch"}'})
        write_tree(home, {"config.json": b'{"repo": "c/config"}'})
        src = update.load_source(home, root, {"LAMPLIGHTER_REPO": "  "})
        self.assertEqual((src.repo, src.branch), ("c/config", "vbranch"))

    def test_repo_must_match_owner_slash_name(self):
        for ok in ["octocat/Hello-World", "a/b", "A1/.github", "x-y/a.b_c-d", "a" * 39 + "/" + "b" * 100]:
            self.assertTrue(update.valid_repo(ok), ok)
        for bad in ["", "a", "a/", "/b", "a/b/c", "-a/b", "a-/b", "a--b/c", "a b/c", "a/b c", "a/..", "a/.", "../x",
                    "a/b?x=1", "a@evil.com/b", "a/b\n", "a/b#frag", "https://github.com/a/b", "a\\b", "a/b:80",
                    "a" * 40 + "/b", "a/" + "b" * 101, "\u00e9/b", None, 5]:
            self.assertFalse(update.valid_repo(bad), repr(bad))

    def test_branch_validation(self):
        for ok in ["main", "release/1.0", "v2.x", "feature/a-b_c"]:
            self.assertTrue(update.valid_branch(ok), ok)
        for bad in ["", "-x", "a b", "..", "a/../b", "a//b", "/a", "a/", ".hidden", "x.lock", "a\\b", "a?b", "a#b", None]:
            self.assertFalse(update.valid_branch(bad), repr(bad))

    def test_invalid_setting_is_an_error_that_names_where_it_came_from(self):
        home, root = self.dirs()
        write_tree(root, {"version.json": b'{"version": "2.0.0"}'})
        with self.assertRaises(UpdateError) as cm:
            update.load_source(home, root, {"LAMPLIGHTER_REPO": "not a repo"})
        self.assertIn("LAMPLIGHTER_REPO", str(cm.exception))
        write_tree(home, {"config.json": b'{"branch": "../x"}'})
        with self.assertRaises(UpdateError) as cm:
            update.load_source(home, root, {})
        self.assertIn("config.json", str(cm.exception))

    def test_broken_config_json_is_a_clear_error(self):
        home, root = self.dirs()
        write_tree(root, {"version.json": b'{"version": "2.0.0"}'})
        for junk in (b"{nope", b"[]", b"\xff"):
            write_tree(home, {"config.json": junk})
            with self.assertRaises(UpdateError):
                update.load_source(home, root, {})

    def test_update_repo_saves_to_config_json_and_keeps_other_keys(self):
        e = self.env()
        write_tree(e.home, {"config.json": b'{"branch": "dev", "other": 1}'})
        self.assertEqual(e.run("repo octocat/lamplighter", env={}), 0)
        with open(os.path.join(e.home, "config.json")) as f:
            cfg = json.load(f)
        self.assertEqual(cfg, {"branch": "dev", "other": 1, "repo": "octocat/lamplighter"})
        self.assertEqual(e.transport.calls, [])
        e.lines.clear()
        e.run("repo", env={})
        self.assertIn("octocat/lamplighter", e.text)
        self.assertIn("branch dev", e.text)

    def test_update_repo_rejects_junk_and_saves_nothing(self):
        e = self.env()
        for junk in ("nonsense", "a/b/c", "https://github.com/a/b"):
            self.assertEqual(e.run("repo " + junk, env={}), 1)
        self.assertFalse(os.path.exists(os.path.join(e.home, "config.json")))
        self.assertEqual(e.run("repo a/b c", env={}), 1)    # extra words: usage text, not a crash
        self.assertIn("update repo owner/name", e.text)

    def test_env_variable_still_wins_and_the_player_is_told(self):
        e = self.env()
        e.run("repo me/mine", env={"LAMPLIGHTER_REPO": "other/thing"})
        self.assertIn("LAMPLIGHTER_REPO", e.text)
        self.assertIn("takes priority", e.text)


# --------------------------------------------------------------------------- commands without installing

class CheckTests(OfflineCase):
    def test_no_repo_says_exactly_how_to_set_one_and_does_not_touch_the_network(self):
        e = self.env()
        for noun in ("", "check", "force"):
            e.lines.clear()
            self.assertEqual(e.run(noun, env={}), 0)
            self.assertIn("update repo owner/name", e.text)
            self.assertIn("LAMPLIGHTER_REPO", e.text)
        self.assertEqual(e.transport.calls, [])

    def test_check_only_fetches_version_json_and_never_the_zip(self):
        e = self.env()
        before = snapshot(e.root)
        self.assertEqual(e.run("check"), 0)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertIn("Version %s is available. You have %s." % (NEW, OLD), e.text)
        self.assertIn("What's new in %s" % NEW, e.text)
        self.assertIn("A new thing.", e.text)
        self.assertIn("Type update to install it.", e.text)
        self.assertEqual(e.questions, [])
        self.assertEqual(snapshot(e.root), before)
        self.assertFalse(os.path.exists(os.path.join(e.home, "backups")))

    def test_changelog_is_printed_safely(self):
        e = self.env()
        evil = {"version": NEW, "changelog": ["bad \x1b[31mred\x1b[0m {red}tag{/} line\nbreak", "x" * 1000]}
        e.transport.routes[VERSION_URL] = json.dumps(evil).encode()
        e.run("check")
        self.assertNotIn("\x1b", e.text)
        self.assertNotIn("{red}", e.text)
        self.assertNotIn("{/}", e.text)
        self.assertNotIn("x" * 400, e.text)

    def test_long_changelog_is_trimmed(self):
        e = self.env()
        e.transport.routes[VERSION_URL] = json.dumps({"version": NEW, "changelog": ["line %d" % i for i in range(40)]}).encode()
        e.run("check")
        self.assertIn("line 24", e.text)
        self.assertNotIn("line 25", e.text)
        self.assertIn("and 15 more", e.text)

    def test_up_to_date(self):
        e = self.env(new_version=OLD)
        self.assertEqual(e.run(""), 0)
        self.assertIn("You are up to date (version %s)." % OLD, e.text)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertEqual(e.questions, [])

    def test_older_remote_is_not_installed_without_force(self):
        e = self.env(new_version="2.0.0-dev.5")
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 0)
        self.assertIn("You are up to date (version %s)." % OLD, e.text)
        self.assertIn("older version (2.0.0-dev.5)", e.text)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertEqual(snapshot(e.root), before)

    def test_release_beats_its_own_dev_build(self):
        e = self.env(new_version="2.0.0")
        e.run("check")
        self.assertIn("Version 2.0.0 is available", e.text)

    def test_bad_remote_version_json_is_an_error_and_changes_nothing(self):
        for label, body in [("not json", b"<html>404</html>"), ("not an object", b"[1]"), ("no version", b"{}"),
                            ("bad version", b'{"version": "latest"}'), ("bad changelog", b'{"version": "9.0.0", "changelog": 4}'),
                            ("too big", b'{"version": "9.0.0", "pad": "' + b"x" * (300 * 1024) + b'"}')]:
            with self.subTest(label):
                e = self.env(tag=label.replace(" ", "_"))
                e.transport.routes[VERSION_URL] = body
                before = snapshot(e.root)
                self.assertEqual(e.run(""), 1)
                self.assertIn("Update stopped", e.text)
                self.assertIn("not changed", e.text)
                self.assertEqual(e.transport.calls, [VERSION_URL])
                self.assertEqual(snapshot(e.root), before)

    def test_unreachable_server_is_a_plain_message(self):
        e = self.env()
        e.transport.routes[VERSION_URL] = UpdateError("Could not reach the server (timed out).")
        self.assertEqual(e.run(""), 1)
        self.assertIn("timed out", e.text)

    def test_an_unexpected_exception_never_crashes_the_game(self):
        e = self.env()
        e.transport.routes[VERSION_URL] = RuntimeError("boom")
        self.assertEqual(e.run(""), 1)
        self.assertIn("unexpected problem", e.text)

    def test_unreadable_own_version_needs_force(self):
        e = self.env(old_version="whatever")
        self.assertEqual(e.run(""), 1)
        self.assertIn("update force", e.text)

    def test_usage_for_unknown_words(self):
        e = self.env()
        self.assertEqual(e.run("banana"), 1)
        self.assertIn("update check", e.text)
        self.assertEqual(e.transport.calls, [])


# --------------------------------------------------------------------------- the real install

class InstallTests(OfflineCase):
    def test_successful_update_swaps_the_code_and_leaves_saves_alone(self):
        e = self.env()
        saves_before = snapshot(os.path.join(e.home, "saves"))
        self.assertEqual(e.run(""), 0, e.text)
        # the new code is in place, byte for byte
        for rel, data in stub_files(NEW).items():
            self.assertEqual(e.read(rel), data, rel)
        # old code that the new version no longer has is gone from the live tree, kept in .update_old
        self.assertFalse(os.path.exists(os.path.join(e.root, "lamplighter", "old_only.py")))
        self.assertEqual(e.read(update.OLD_DIR + "/lamplighter/old_only.py"), b"OLD = 1\n")
        self.assertEqual(e.read(update.OLD_DIR + "/main.py"), b"print('old game')\n")
        # files the update does not own are untouched, and no temp folder is left behind
        self.assertEqual(e.read("notes.txt"), b"the player's own file, not part of the game\n")
        self.assertFalse(os.path.exists(os.path.join(e.root, update.STAGE_DIR)))
        # saves are intact and backed up
        self.assertEqual(snapshot(os.path.join(e.home, "saves")), saves_before)
        backups = os.listdir(os.path.join(e.home, "backups"))
        self.assertEqual(backups, ["20261101-120001-" + OLD])
        self.assertEqual(snapshot(os.path.join(e.home, "backups", backups[0])), saves_before)
        # the closing message
        self.assertEqual(e.transport.calls, [VERSION_URL, ZIP_URL])
        for needle in (OLD, NEW, os.path.join(e.home, "backups", backups[0]), "Restart the game"):
            self.assertIn(needle, e.text)
        self.assertEqual(len(e.questions), 1)

    def test_declining_changes_nothing_and_downloads_nothing(self):
        e = self.env()
        before = snapshot(e.root)
        self.assertEqual(e.run("", answer=False), 0)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertEqual(snapshot(e.root), before)
        self.assertFalse(os.path.exists(os.path.join(e.home, "backups")))
        self.assertIn("Nothing was changed", e.text)

    def test_update_without_any_saves_still_works(self):
        e = self.env(saves=False)
        self.assertEqual(e.run(""), 0, e.text)
        self.assertEqual(e.read("main.py"), b"print('new game')\n")
        self.assertIn("none to back up", e.text)
        self.assertFalse(os.path.exists(os.path.join(e.home, "backups")))

    def test_only_the_allowed_top_level_paths_are_installed(self):
        files = stub_files(NEW)
        files.update({"saves/main.json": b"EVIL", "config.json": b"EVIL", ".github/workflow.yml": b"EVIL",
                      "evil.py": b"EVIL", "backups/x": b"EVIL", "lamplighter/__pycache__/x.pyc": b"EVIL",
                      "docs": b"a file where a folder belongs is ignored"})
        e = self.env(files=files)
        files_before = set(snapshot(e.root))
        self.assertEqual(e.run(""), 0, e.text)
        for name in ("saves", "config.json", ".github", "evil.py", "backups"):
            self.assertFalse(os.path.exists(os.path.join(e.root, name)), name)
        self.assertFalse(os.path.exists(os.path.join(e.root, "lamplighter", "__pycache__")))
        self.assertEqual(e.read("docs/new.md"), b"new docs\n")
        new_names = set(snapshot(e.root)) - files_before
        self.assertFalse([n for n in new_names if not n.startswith((update.OLD_DIR, "lamplighter", "docs", "tools", "tests"))])

    def test_a_second_update_replaces_the_previous_old_folder(self):
        e = self.env()
        e.run("")
        e.transport.routes[VERSION_URL] = json.dumps({"version": "2.0.0-dev.8"}).encode()
        e.transport.routes[ZIP_URL] = make_zip(stub_files("2.0.0-dev.8"))
        e.lines.clear()
        self.assertEqual(e.run(""), 0, e.text)
        self.assertEqual(json.loads(e.read("version.json"))["version"], "2.0.0-dev.8")
        self.assertEqual(json.loads(e.read(update.OLD_DIR + "/version.json"))["version"], NEW)
        self.assertFalse(os.path.exists(os.path.join(e.root, update.OLD_DIR, "lamplighter", "old_only.py")))

    def test_stale_staging_folder_from_a_crash_is_cleared(self):
        e = self.env()
        write_tree(e.root, {update.STAGE_DIR + "/junk.txt": b"left by a crash"})
        self.assertEqual(e.run(""), 0, e.text)
        self.assertFalse(os.path.exists(os.path.join(e.root, update.STAGE_DIR)))

    def test_same_version_needs_force(self):
        e = self.env(new_version=OLD)
        e.run("")
        self.assertIn("up to date", e.text)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        e.lines.clear()
        self.assertEqual(e.run("force"), 0, e.text)
        self.assertEqual(e.transport.calls[-1], ZIP_URL)
        self.assertEqual(e.read("main.py"), b"print('new game')\n")
        self.assertIn("Forced", e.text)

    def test_downgrade_needs_force(self):
        e = self.env(new_version="2.0.0-dev.2")
        before = snapshot(e.root)
        e.run("")
        self.assertEqual(snapshot(e.root), before)
        self.assertEqual(e.run("force"), 0, e.text)
        self.assertEqual(json.loads(e.read("version.json"))["version"], "2.0.0-dev.2")

    def test_archive_that_is_not_newer_than_the_announcement_is_refused_even_though_it_was_announced_newer(self):
        # the announcement says NEW, but the zip's own version.json is older: a downgrade in disguise
        e = self.env(files=stub_files("2.0.0-dev.2"), announce=NEW)
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1)
        self.assertIn("announced", e.text)
        self.assertUntouched(e, before)

    def test_archive_version_must_match_the_announcement(self):
        e = self.env(files=stub_files("2.0.0-dev.9"), announce=NEW)
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1)
        self.assertIn("announced", e.text)
        self.assertUntouched(e, before)


class AbortTests(OfflineCase):
    """Every way an update can be refused must leave the game folder byte-identical."""

    def abort(self, env, expect, noun=""):
        before = snapshot(env.root)
        saves_before = snapshot(os.path.join(env.home, "saves")) if os.path.isdir(os.path.join(env.home, "saves")) else None
        rc = env.run(noun)
        self.assertEqual(rc, 1, env.text)
        self.assertIn("Update stopped", env.text)
        self.assertIn(expect.lower(), env.text.lower())
        self.assertIn("were not changed", env.text)
        self.assertUntouched(env, before)
        if saves_before is not None:
            self.assertEqual(snapshot(os.path.join(env.home, "saves")), saves_before)

    def test_not_a_zip(self):
        self.abort(self.env(zip_bytes=b"this is not a zip"), "not a valid zip")

    def test_download_failures(self):
        e = self.env()
        e.transport.routes[ZIP_URL] = UpdateError("Could not reach codeload.github.com (timed out).")
        self.abort(e, "timed out")

    def test_bad_members(self):
        base = stub_files(NEW)
        cases = [
            ("dot dot", [("game-main/../evil.py", b"x", None)], "climbs out"),
            ("deep dot dot", [("game-main/lamplighter/../../evil.py", b"x", None)], "climbs out"),
            ("backslash dot dot", [("game-main/..\\evil.py", b"x", None)], "climbs out|suspicious"),
            ("absolute", [("/etc/evil.py", b"x", None)], "absolute"),
            ("drive letter", [("C:/evil.py", b"x", None)], "absolute"),
            ("drive relative", [("C:evil.py", b"x", None)], "absolute"),
            ("alternate stream", [("game-main/docs/a:b.txt", b"x", None)], "windows"),
            ("trailing dot", [("game-main/docs/x.", b"x", None)], "windows"),
            ("empty part", [("game-main//evil.py", b"x", None)], "climbs out"),
            ("control character", [("game-main/docs/a\x01b", b"x", None)], "suspicious"),
            ("symlink", [("game-main/lamplighter/link", b"/etc/passwd", 0o120777 << 16)], "symbolic link"),
            ("symlink outside allowed", [("game-main/other/link", b"x", 0o120777 << 16)], "symbolic link"),
            ("device node", [("game-main/lamplighter/dev", b"", 0o020666 << 16)], "special file"),
            ("device name", [("game-main/lamplighter/nul.py", b"x", None)], "device name"),
            ("device name upper", [("game-main/tools/COM1", b"x", None)], "device name"),
            ("device name docs", [("game-main/docs/con.txt", b"x", None)], "device name"),
            ("second wrapper", [("other-main/x.py", b"x", None)], "wrapper"),
            ("top level file beside wrapper", [("stray.py", b"x", None)], "wrapper"),
            ("duplicate by case", [("game-main/docs/a.md", b"x", None), ("game-main/docs/A.MD", b"y", None)], "twice"),
            ("too deep", [("game-main/docs/" + "/".join(["d"] * 20) + "/x.md", b"x", None)], "nested too deeply"),
        ]
        for label, extra, expect in cases:
            with self.subTest(label):
                e = self.env(tag=label.replace(" ", "_"), zip_bytes=make_zip(base, extra=extra))
                before = snapshot(e.root)
                self.assertEqual(e.run(""), 1, e.text)
                self.assertTrue(any(x in e.text.lower() for x in expect.split("|")), e.text)
                self.assertIn("were not changed", e.text)
                self.assertUntouched(e, before)
                # nothing escaped into the folders around the game either
                self.assertEqual(sorted(os.listdir(self.tmp)).count("evil.py"), 0)
                self.assertFalse(os.path.exists(os.path.join(os.path.dirname(e.root), "evil.py")))

    def test_the_wrapper_is_stripped_exactly_once(self):
        e = self.env(zip_bytes=make_zip({"game-main/" + k: v for k, v in stub_files(NEW).items()}))
        self.abort(e, "no version.json")      # everything sits one folder too deep, so nothing is accepted

    def test_no_wrapper_at_all(self):
        e = self.env(zip_bytes=make_zip(stub_files(NEW), wrapper=""))
        self.abort(e, "wrapper")

    def test_empty_zip(self):
        e = self.env(zip_bytes=make_zip({}, wrapper=""))
        self.abort(e, "empty")

    def test_oversized_download(self):
        e = self.env()
        with mock.patch.object(update, "MAX_ZIP_BYTES", 100):
            self.abort(e, "larger than")

    def test_a_transport_that_ignores_the_limit_is_still_caught(self):
        e = self.env()
        e.transport.get = lambda url, max_bytes: (e.transport.calls.append(url) or
                                                   (e.zip if url == ZIP_URL else e.transport.routes[VERSION_URL]))
        with mock.patch.object(update, "MAX_ZIP_BYTES", 100):
            self.abort(e, "larger than")

    def test_too_many_members(self):
        e = self.env()
        with mock.patch.object(update, "MAX_MEMBERS", 5):
            self.abort(e, "too many files")

    def test_zip_bomb_total_size(self):
        files = stub_files(NEW)
        files["docs/bomb.txt"] = b"\0" * (5 * 1024 * 1024)
        e = self.env(files=files)
        self.assertLess(len(e.zip), 100 * 1024)    # tiny download...
        with mock.patch.object(update, "MAX_UNCOMPRESSED", 1024 * 1024), \
                mock.patch.object(update, "MAX_RATIO", 10 ** 9):
            self.abort(e, "far more data")         # ...refused for what it unpacks to

    def test_single_huge_member(self):
        files = stub_files(NEW)
        files["docs/bomb.txt"] = b"\0" * (3 * 1024 * 1024)
        e = self.env(files=files)
        with mock.patch.object(update, "MAX_MEMBER_BYTES", 1024 * 1024), \
                mock.patch.object(update, "MAX_RATIO", 10 ** 9):
            self.abort(e, "far more data")

    def test_member_that_lies_about_its_size_is_stopped_while_unpacking(self):
        e = self.env(new_version=NEW)
        files = stub_files(NEW)
        files["docs/liar.txt"] = b"a" * 4096
        raw = bytearray(make_zip(files))
        # shrink the declared uncompressed size in the central directory only; the data still inflates to 4096
        first = raw.find(b"docs/liar.txt")
        second = raw.find(b"docs/liar.txt", first + 1)
        start = raw.rfind(b"PK\x01\x02", 0, second)
        self.assertGreater(start, 0)
        struct.pack_into("<I", raw, start + 24, 100)
        e.transport.routes[ZIP_URL] = bytes(raw)
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1, e.text)
        self.assertIn("damaged", e.text)
        self.assertUntouched(e, before)

    def test_wrong_host_and_http_are_refused_before_any_request(self):
        for label, url in [("http", "http://raw.githubusercontent.com/a/b/main/version.json"),
                           ("suffix host", "https://raw.githubusercontent.com.evil.com/a/b/main/version.json"),
                           ("other host", "https://evil.com/a/b/main/version.json")]:
            with self.subTest(label):
                e = self.env(tag=label.replace(" ", "_"))
                e.transport.routes[VERSION_URL] = UpdateError("Refusing %r: updates only use https." % url)
                before = snapshot(e.root)
                self.assertEqual(e.run(""), 1)
                self.assertUntouched(e, before)

    def test_redirect_to_http_during_download_aborts_cleanly(self):
        e = self.env()
        e.transport.routes[ZIP_URL] = UpdateError("Refusing 'http://codeload.github.com/x': updates only use https.")
        self.abort(e, "only use https")

    def test_missing_pieces_in_the_new_tree(self):
        for label, drop in [("main.py", "main.py"), ("version.json", "version.json"),
                            ("lamplighter", "lamplighter/__init__.py"), ("validator", "tools/validate_content.py")]:
            with self.subTest(label):
                files = stub_files(NEW)
                del files[drop]
                e = self.env(tag=label, files=files)
                before = snapshot(e.root)
                self.assertEqual(e.run(""), 1, e.text)
                self.assertUntouched(e, before)

    def test_new_version_json_that_is_broken(self):
        files = stub_files(NEW)
        files["version.json"] = b'{"version": "banana"}'
        self.abort(self.env(files=files), "banana")

    def test_validator_failure_aborts_with_the_reason(self):
        e = self.env(validator_ok=False)
        self.abort(e, "room x points at nothing")
        self.assertIn("content check failed", e.text)

    def test_migration_dry_run_failure_aborts_with_the_file_name(self):
        e = self.env()
        write_tree(e.home, {"saves/main.bak.json": b'{"save_version": 1, "poison": true}'})
        self.abort(e, "main.bak.json")
        self.assertIn("poisoned save", e.text)

    def test_unreadable_save_file_aborts_the_dry_run(self):
        e = self.env()
        write_tree(e.home, {"saves/slot2.json": b"{ not json"})
        self.abort(e, "slot2.json")

    def test_dry_run_checks_copies_not_the_real_saves(self):
        e = self.env()
        write_tree(e.home, {"saves/main.json": b'{"save_version": 1, "poison": true}'})
        before = snapshot(os.path.join(e.home, "saves"))
        self.assertEqual(e.run(""), 1)
        self.assertEqual(snapshot(os.path.join(e.home, "saves")), before)

    def test_injected_check_failure_aborts(self):
        e = self.env()

        def boom(tree, stage):
            raise UpdateError("injected failure")
        before = snapshot(e.root)
        self.assertEqual(e.run("", run_checks=boom), 1)
        self.assertIn("injected failure", e.text)
        self.assertUntouched(e, before)

    def test_checks_run_in_isolated_subprocesses_in_the_new_tree(self):
        e = self.env()
        seen = []
        real = subprocess.Popen

        def spy(cmd, **kw):
            seen.append((cmd, kw))
            return real(cmd, **kw)
        # the player's own environment is full of settings the checks must not see
        with mock.patch.dict(os.environ, {"LAMPLIGHTER_REPO": "x/y", "LAMPLIGHTER_BRANCH": "b",
                                          "LAMPLIGHTER_HOME": e.home}),                 mock.patch.object(update.subprocess, "Popen", spy):
            self.assertEqual(e.run(""), 0, e.text)
        self.assertEqual(len(seen), 2)       # the validator and the migration dry run
        for cmd, kw in seen:
            self.assertEqual(cmd[:3], [sys.executable, "-I", "-B"])
            self.assertTrue(os.path.basename(kw["cwd"]) == "tree")
            self.assertEqual(os.path.basename(os.path.dirname(kw["cwd"])), update.STAGE_DIR)
            self.assertEqual(kw["stdin"], subprocess.DEVNULL)
            env = kw["env"]
            self.assertNotIn("LAMPLIGHTER_REPO", env)
            self.assertNotIn("LAMPLIGHTER_BRANCH", env)
            # the checks get a scratch home inside the staging folder, never the player's data folder
            self.assertNotEqual(os.path.normcase(env["LAMPLIGHTER_HOME"]), os.path.normcase(e.home))
            self.assertEqual(os.path.basename(os.path.dirname(env["LAMPLIGHTER_HOME"])), update.STAGE_DIR)

    def test_the_migration_dry_run_is_given_copies_of_the_saves_never_the_real_ones(self):
        e = self.env()
        seen = []
        real = subprocess.Popen

        def spy(cmd, **kw):
            seen.append(cmd)
            return real(cmd, **kw)
        with mock.patch.object(update.subprocess, "Popen", spy):
            self.assertEqual(e.run(""), 0, e.text)
        dry = [c for c in seen if "-c" in c][0]
        paths_given = dry[dry.index("-c") + 2:]
        self.assertEqual(sorted(os.path.basename(p) for p in paths_given), ["main.bak.json", "main.json"])
        real_saves = os.path.normcase(os.path.join(e.home, "saves"))
        for p in paths_given:
            self.assertFalse(os.path.normcase(p).startswith(real_saves), p)
            self.assertIn(update.STAGE_DIR, p)

    def test_a_hung_check_is_stopped(self):
        e = self.env()
        files = stub_files(NEW)
        files["tools/validate_content.py"] = b"import time\ntime.sleep(60)\n"
        e = self.env(tag="slow", files=files)
        before = snapshot(e.root)
        with mock.patch.object(update, "CHECK_TIMEOUT", 1):
            self.assertEqual(e.run(""), 1)
        self.assertIn("did not finish", e.text)
        self.assertUntouched(e, before)


class SwapTests(OfflineCase):
    def test_rollback_after_a_failure_at_every_point_in_the_swap(self):
        # First learn how many moves a clean swap makes, then fail each one in turn.
        probe = self.env(tag="probe")
        moves = []
        up = probe.updater(run_checks=lambda tree, stage: None)
        real_move = up._move

        def counting(src, dst):
            moves.append((src, dst))
            return real_move(src, dst)
        up._move = counting
        up.update()
        total = len(moves)
        self.assertGreaterEqual(total, 9)
        for n in range(1, total + 1):
            with self.subTest(failing_move=n):
                e = self.env(tag="fail%d" % n)
                before = snapshot(e.root)
                calls = []
                up = e.updater(run_checks=lambda tree, stage: None)
                real = up._move

                def flaky(src, dst, real=real, calls=calls, n=n):
                    calls.append(1)
                    if len(calls) == n:
                        raise OSError("injected failure on move %d" % n)
                    return real(src, dst)
                up._move = flaky
                rc = update.run_command  # same entry point, with the injected updater below
                with mock.patch.object(update, "Updater", lambda **kw: up):
                    self.assertEqual(rc("", e.lines.append, lambda q: True), 1, e.text)
                self.assertIn("put back as it was", e.text)
                self.assertIn("were not changed", e.text)
                self.assertUntouched(e, before)

    def test_rollback_with_a_previous_update_old_folder_restores_it(self):
        e = self.env()
        write_tree(e.root, {update.OLD_DIR + "/lamplighter/ancient.py": b"ANCIENT\n"})
        before = snapshot(e.root)
        up = e.updater(run_checks=lambda tree, stage: None)
        real = up._move
        count = []

        def flaky(src, dst):
            count.append(1)
            if len(count) == 6:
                raise OSError("injected")
            return real(src, dst)
        up._move = flaky
        with mock.patch.object(update, "Updater", lambda **kw: up):
            self.assertEqual(update.run_command("", e.lines.append, lambda q: True), 1)
        self.assertEqual(snapshot(e.root), before)

    def test_failed_rollback_says_where_the_old_files_are(self):
        e = self.env()
        up = e.updater(run_checks=lambda tree, stage: None)
        real = up._move
        count = []

        def flaky(src, dst):
            count.append(1)
            if len(count) == 5:
                raise OSError("injected")
            return real(src, dst)
        up._move = flaky
        with mock.patch.object(update, "Updater", lambda **kw: up), \
                mock.patch.object(update.os, "rename", side_effect=OSError("disk gone")):
            self.assertEqual(update.run_command("", e.lines.append, lambda q: True), 1)
        self.assertIn(update.OLD_DIR, e.text)
        self.assertIn("could not put everything back", e.text)
        self.assertNotIn("were not changed", e.text)
        mock.patch.stopall()
        update._rmtree(os.path.join(e.root, update.OLD_DIR))

    def test_keyboard_interrupt_during_the_swap_still_rolls_back(self):
        e = self.env()
        before = snapshot(e.root)
        up = e.updater(run_checks=lambda tree, stage: None)
        real = up._move
        count = []

        def flaky(src, dst):
            count.append(1)
            if len(count) == 4:
                raise KeyboardInterrupt()
            return real(src, dst)
        up._move = flaky
        with self.assertRaises(KeyboardInterrupt):
            up.update()
        self.assertUntouched(e, before)


def backup_and_rotate(up, version):
    """What a successful install does with the backups: make one, then tidy the old ones."""
    path = up._backup_saves(version)
    up._rotate_backups(os.path.dirname(path), keep=path)
    return path


class BackupTests(OfflineCase):
    def test_keeps_only_the_last_five(self):
        e = self.env()
        up = e.updater()
        names = []
        for i in range(8):
            up.now = lambda i=i: "20261101-1200%02d" % i
            names.append(os.path.basename(backup_and_rotate(up, "1.0.%d" % i)))
        left = sorted(os.listdir(os.path.join(e.home, "backups")))
        self.assertEqual(left, sorted(names[-5:]))
        for n in left:
            self.assertTrue(os.path.exists(os.path.join(e.home, "backups", n, "main.json")))

    def test_rotation_only_touches_folders_it_made(self):
        e = self.env()
        base = os.path.join(e.home, "backups")
        for name in ("keepme", "20260101-000000", "notes.txt", "20260101-000000-hand-made"):
            path = os.path.join(base, name)
            os.makedirs(base, exist_ok=True)
            if name.endswith(".txt"):
                write_tree(base, {name: b"x"})
            else:
                os.makedirs(path)
        up = e.updater()
        for i in range(7):
            up.now = lambda i=i: "20261101-1200%02d" % i
            backup_and_rotate(up, "1.0.0")
        left = set(os.listdir(base))
        self.assertTrue({"keepme", "20260101-000000", "notes.txt"} <= left)
        self.assertEqual(len([n for n in left if n.startswith("20261101")]), 5)
        self.assertNotIn("20260101-000000-hand-made", left)   # matches the pattern and is the oldest, so it rotates out

    def test_two_backups_in_the_same_second_do_not_collide(self):
        e = self.env()
        up = e.updater(now=lambda: "20261101-120000")
        a, b, c = (up._backup_saves(OLD) for _ in range(3))
        self.assertEqual(len({a, b, c}), 3)
        self.assertEqual(len(os.listdir(os.path.join(e.home, "backups"))), 3)

    def test_backup_name_is_safe_for_odd_versions(self):
        e = self.env()
        up = e.updater()
        path = up._backup_saves("we/ird:ver sion")
        self.assertEqual(os.path.dirname(path), os.path.join(e.home, "backups"))

    def test_backup_failure_aborts_before_anything_else(self):
        e = self.env()
        before = snapshot(e.root)
        with mock.patch.object(update.shutil, "copytree", side_effect=OSError("disk full")):
            self.assertEqual(e.run(""), 1)
        self.assertIn("could not back up your saves", e.text)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertUntouched(e, before)


# --------------------------------------------------------------------------- hosts and the real transport

class FakeResponse:
    def __init__(self, body=b"", url=VERSION_URL, headers=None):
        self._body, self._url = io.BytesIO(body), url
        self.headers = headers or {}

    def geturl(self):
        return self._url

    def read(self, n=-1):
        return self._body.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TransportTests(unittest.TestCase):
    """The real transport, with the network cut: it must refuse bad URLs before any request is made."""

    def setUp(self):
        for target in ("socket.getaddrinfo", "socket.create_connection"):
            p = mock.patch(target, side_effect=AssertionError("the network was touched"))
            p.start()
            self.addCleanup(p.stop)
        self.opened = []

        def fake_open(opener, req, *a, **kw):
            self.opened.append(req)
            return self.response
        p = mock.patch.object(urllib.request.OpenerDirector, "open", fake_open)
        p.start()
        self.addCleanup(p.stop)
        self.response = FakeResponse(b'{"version": "2.0.0"}')

    GOOD = ["https://raw.githubusercontent.com/a/b/main/version.json",
            "https://codeload.github.com/a/b/zip/refs/heads/main",
            "https://github.com/a/b/archive/refs/heads/main.zip",
            "https://github.com:443/a/b", "https://GitHub.com/a/b"]
    BAD = ["http://raw.githubusercontent.com/a/b/main/version.json",
           "http://github.com/a/b",
           "https://github.com.evil.com/a/b",
           "https://raw.githubusercontent.com.evil.com/a/b",
           "https://evilgithub.com/a/b",
           "https://notgithub.com/a/b",
           "https://sub.github.com/a/b",
           "https://api.github.com/repos/a/b",
           "https://github.com@evil.com/a/b",
           "https://evil.com@github.com/a/b",
           "https://evil.com\\@github.com/a/b",
           "https://github.com:8443/a/b",
           "https://github.com:80/a/b",
           "https://github.com./a/b",
           "https://github.com /a/b",
           "https://github.com\n.evil.com/",
           "https://localhost/a", "https://127.0.0.1/a", "https://[::1]/a",
           "ftp://github.com/a", "file:///etc/passwd", "data:text/plain,hi", "//github.com/a", "github.com/a",
           "javascript:alert(1)", "", "https://", "https:///a", None, 5]

    def test_check_url_table(self):
        for url in self.GOOD:
            update.check_url(url)
        for url in self.BAD:
            with self.assertRaises(UpdateError, msg=repr(url)):
                update.check_url(url)

    def test_real_transport_refuses_before_making_any_request(self):
        t = update.HttpsTransport()
        for url in self.BAD:
            with self.assertRaises(UpdateError, msg=repr(url)):
                t.get(url, 1000)
        self.assertEqual(self.opened, [])

    def test_redirects_to_other_hosts_or_http_are_refused(self):
        h = update._SafeRedirect()
        req = urllib.request.Request("https://github.com/a/b/archive/refs/heads/main.zip")
        for target in ["http://codeload.github.com/a/b/zip", "https://evil.com/x", "https://codeload.github.com.evil.com/x",
                       "ftp://github.com/x", "file:///etc/passwd", "https://github.com@evil.com/"]:
            with self.assertRaises(UpdateError, msg=target):
                h.redirect_request(req, None, 302, "Found", {}, target)
        again = h.redirect_request(req, None, 302, "Found", {}, "https://codeload.github.com/a/b/zip/refs/heads/main")
        self.assertEqual(again.full_url, "https://codeload.github.com/a/b/zip/refs/heads/main")

    def test_redirect_handler_is_the_one_the_transport_uses(self):
        built = []
        real = urllib.request.build_opener

        def spy(*handlers):
            built.append(handlers)
            return real(*handlers)
        with mock.patch.object(urllib.request, "build_opener", spy):
            update.HttpsTransport().get(VERSION_URL, 1000)
        self.assertIn(update._SafeRedirect, built[0])

    def test_sends_only_a_fixed_user_agent_and_nothing_about_the_player(self):
        body = update.HttpsTransport().get(VERSION_URL, 1000)
        self.assertEqual(body, b'{"version": "2.0.0"}')
        req = self.opened[0]
        self.assertEqual(req.full_url, VERSION_URL)
        self.assertEqual(dict(req.header_items()), {"User-agent": update.USER_AGENT})
        self.assertIsNone(req.data)
        self.assertEqual(req.get_method(), "GET")

    def test_size_cap_is_enforced_while_reading(self):
        self.response = FakeResponse(b"x" * 5000)
        with self.assertRaises(UpdateError) as cm:
            update.HttpsTransport().get(VERSION_URL, 1000)
        self.assertIn("larger than", str(cm.exception))
        self.response = FakeResponse(b"x" * 1000)
        self.assertEqual(len(update.HttpsTransport().get(VERSION_URL, 1000)), 1000)

    def test_declared_content_length_over_the_cap_is_refused_early(self):
        self.response = FakeResponse(b"x", headers={"Content-Length": "999999999"})
        with self.assertRaises(UpdateError):
            update.HttpsTransport().get(VERSION_URL, 1000)

    def test_a_final_url_on_another_host_is_refused(self):
        self.response = FakeResponse(b"x", url="https://evil.com/x")
        with self.assertRaises(UpdateError):
            update.HttpsTransport().get(VERSION_URL, 1000)
        self.response = FakeResponse(b"x", url="http://github.com/x")
        with self.assertRaises(UpdateError):
            update.HttpsTransport().get(VERSION_URL, 1000)

    def test_http_errors_and_timeouts_become_plain_messages(self):
        import urllib.error

        def raise_404(opener, req, *a, **kw):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(b""))
        with mock.patch.object(urllib.request.OpenerDirector, "open", raise_404):
            with self.assertRaises(UpdateError) as cm:
                update.HttpsTransport().get(VERSION_URL, 1000)
        self.assertIn("404", str(cm.exception))

        def raise_timeout(opener, req, *a, **kw):
            raise socket.timeout("timed out")
        with mock.patch.object(urllib.request.OpenerDirector, "open", raise_timeout):
            with self.assertRaises(UpdateError) as cm:
                update.HttpsTransport().get(VERSION_URL, 1000)
        self.assertIn("timed out", str(cm.exception))

    def test_urls_are_built_from_validated_settings(self):
        src = update.Source("octo/cat", "release/1.0", "x", "x")
        self.assertEqual(src.raw_version_url(), "https://raw.githubusercontent.com/octo/cat/release/1.0/version.json")
        self.assertEqual(src.zip_url(), "https://codeload.github.com/octo/cat/zip/refs/heads/release/1.0")
        update.check_url(src.raw_version_url())
        update.check_url(src.zip_url())


# --------------------------------------------------------------------------- in the game and on the command line

class GameIntegrationTests(OfflineCase):
    def setUp(self):
        OfflineCase.setUp(self)
        self.env_ = Env(self.tmp, "game")
        # the engine builds its own Updater, so point its defaults at the temp game root and server
        for target, value in ((update.paths, ("game_root", lambda: self.env_.root)),):
            p = mock.patch.object(target, value[0], value[1])
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(update, "HttpsTransport", lambda: self.env_.transport)
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {}, clear=False)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("LAMPLIGHTER_REPO", None)
        os.environ.pop("LAMPLIGHTER_BRANCH", None)

    def test_update_is_a_command_and_in_help(self):
        from lamplighter.engine import VERB_LOOKUP
        self.assertEqual(VERB_LOOKUP["update"], "update")
        with temp_home():
            g = new_game()
            self.assertIn("update", run(g, "help"))

    def test_in_game_flow_set_repo_check_then_install(self):
        with temp_home() as home:
            g = new_game()
            out = run(g, "update")
            self.assertIn("update repo owner/name", out)
            self.assertEqual(self.env_.transport.calls, [])
            out = run(g, "update repo Owner/Game")
            self.assertIn("Update repo saved: owner/game", out)
            with open(os.path.join(home, "config.json")) as f:
                self.assertEqual(json.load(f)["repo"], "owner/game")
            out = run(g, "update check")
            self.assertIn("Version %s is available" % NEW, out)
            self.assertEqual(self.env_.transport.calls, [VERSION_URL])
            write_tree(home, {"saves/main.json": b'{"save_version": 1}'})
            out = run(g, "update", answers=["y"])
            self.assertIn("Restart the game", out)
            self.assertEqual(self.env_.read("main.py"), b"print('new game')\n")
            self.assertTrue(os.listdir(os.path.join(home, "backups")))

    def test_declining_in_game(self):
        with temp_home():
            g = new_game()
            run(g, "update repo owner/game")
            out = run(g, "update", answers=["n"])
            self.assertIn("Nothing was changed", out)
            self.assertEqual(self.env_.read("main.py"), b"print('old game')\n")

    def test_not_while_fighting(self):
        from lamplighter import ui
        with temp_home():
            g = new_game()
            ui.io.in_combat = True
            try:
                out = run(g, "update check")
            finally:
                ui.io.in_combat = False
            self.assertIn("middle of a fight", out)
            self.assertEqual(self.env_.transport.calls, [])

    def test_the_game_keeps_running_on_the_old_code_after_an_update(self):
        with temp_home():
            g = new_game()
            run(g, "update repo owner/game")
            run(g, "update", answers=["y"])
            self.assertIn("lamplighter", g.render_room.__module__)
            self.assertIn("Test", run(g, "stats"))       # still alive and answering


class CommandLineTests(unittest.TestCase):
    def test_update_flag_is_wired_and_offline_for_a_bad_repo(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, LAMPLIGHTER_HOME=home, LAMPLIGHTER_REPO="not a repo")
            r = subprocess.run([sys.executable, os.path.join(PROJECT, "main.py"), "--update", "check"], env=env,
                               capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
            out = r.stdout.decode("utf-8", "replace")
            self.assertEqual(r.returncode, 1, out + r.stderr.decode("utf-8", "replace"))
            self.assertIn("LAMPLIGHTER_REPO", out)
            self.assertIn("not valid", out)

    def test_update_flag_with_no_repo_explains_how_to_set_one(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as root:
            # run a copy of main.py next to an empty-repo version.json so this never depends on the real repo setting
            write_tree(root, {"version.json": b'{"version": "2.0.0", "repo": ""}'})
            code = ("import sys; sys.path.insert(0, %r)\n"
                    "from lamplighter import update, paths\n"
                    "paths.game_root = lambda: %r\n"
                    "sys.exit(update.run_command('', print, lambda q: False))\n") % (PROJECT, root)
            env = dict(os.environ, LAMPLIGHTER_HOME=home)
            env.pop("LAMPLIGHTER_REPO", None)
            r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
            self.assertIn("update repo owner/name", r.stdout.decode("utf-8", "replace"))


# --------------------------------------------------------------------------- the real code, end to end

class RealTreeTests(OfflineCase):
    """Zip up this very game (as a newer version) and install it: the real validator and the real
    save migrations run against the real fixture saves, in a temp game folder."""

    def real_zip(self, version="9.9.9"):
        files = {}
        for name in update.ALLOWED_NAMES:
            path = os.path.join(PROJECT, name)
            if os.path.isdir(path):
                for here, dirs, fs in os.walk(path):
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    for f in fs:
                        if f.endswith(".pyc"):
                            continue
                        full = os.path.join(here, f)
                        with open(full, "rb") as fh:
                            files[os.path.relpath(full, PROJECT).replace(os.sep, "/")] = fh.read()
            elif os.path.isfile(path):
                with open(path, "rb") as fh:
                    files[name] = fh.read()
        data = json.loads(files["version.json"])
        data["version"] = version
        files["version.json"] = json.dumps(data).encode()
        return make_zip(files), files

    def test_real_validator_and_real_migrations_accept_the_real_tree(self):
        blob, files = self.real_zip()
        e = self.env(tag="real", zip_bytes=blob, new_version="9.9.9", saves=False)
        fixtures = os.path.join(PROJECT, "tests", "fixtures", "saves")
        os.makedirs(os.path.join(e.home, "saves"))
        for name in os.listdir(fixtures):
            with open(os.path.join(fixtures, name), "rb") as src, \
                    open(os.path.join(e.home, "saves", name), "wb") as dst:
                dst.write(src.read())
            with open(os.path.join(fixtures, name), "rb") as src, \
                    open(os.path.join(e.home, "saves", name.replace(".json", ".bak.json")), "wb") as dst:
                dst.write(src.read())
        self.assertEqual(e.run(""), 0, e.text)
        self.assertEqual(e.read("lamplighter/update.py"), files["lamplighter/update.py"])
        self.assertEqual(json.loads(e.read("version.json"))["version"], "9.9.9")
        self.assertEqual(len(os.listdir(os.path.join(e.home, "backups"))), 1)

    def test_the_real_tree_is_refused_if_a_save_cannot_be_migrated(self):
        blob, _ = self.real_zip()
        e = self.env(tag="realbad", zip_bytes=blob, new_version="9.9.9", saves=False)
        write_tree(e.home, {"saves/main.json": b'{"save_version": 99}'})   # a save from the future
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1)
        self.assertIn("main.json", e.text)
        self.assertIn("newer version", e.text)
        self.assertUntouched(e, before)


# --------------------------------------------------------------------------- review fixes: the settings an update can change

class SourceTests(OfflineCase):
    """A version.json arrives with an update, so it must never be able to cut off or redirect later updates."""

    def dirs(self):
        home, root = os.path.join(self.tmp, "home"), os.path.join(self.tmp, "root")
        os.makedirs(home)
        os.makedirs(root)
        return home, root

    def test_a_bad_branch_or_repo_in_version_json_is_skipped_not_fatal(self):
        home, root = self.dirs()
        write_tree(root, {"version.json": b'{"version": "2.0.0", "branch": "../x", "repo": 123}'})
        src = update.load_source(home, root, {"LAMPLIGHTER_REPO": "owner/game"})
        self.assertEqual((src.repo, src.branch, src.branch_from), ("owner/game", "main", "default"))
        # and with nothing else set the game just has no repo yet, which `update repo` can fix
        src = update.load_source(home, root, {})
        self.assertEqual(src.repo, "")
        # the player's own settings are still errors, because the player can fix those
        with self.assertRaises(UpdateError):
            update.load_source(home, root, {"LAMPLIGHTER_BRANCH": "../x"})

    def test_a_new_version_json_with_a_bad_repo_or_branch_is_refused_and_nothing_changes(self):
        for label, extra in [("branch", {"branch": "../x"}), ("repo", {"repo": "not a repo"}),
                             ("repo number", {"repo": 123}), ("branch list", {"branch": ["main"]})]:
            with self.subTest(label):
                files = stub_files(NEW)
                files["version.json"] = json.dumps(dict(version=NEW, **extra)).encode()
                e = self.env(tag=label.replace(" ", "_"), files=files)
                before = snapshot(e.root)
                self.assertEqual(e.run(""), 1, e.text)
                self.assertIn("not valid", e.text)
                self.assertIn("were not changed", e.text)
                self.assertUntouched(e, before)

    def test_a_new_version_json_with_a_good_or_empty_repo_and_branch_installs(self):
        for i, extra in enumerate(({}, {"repo": "", "branch": ""}, {"repo": "owner/game", "branch": "release/1.0"})):
            files = stub_files(NEW)
            files["version.json"] = json.dumps(dict(version=NEW, **extra)).encode()
            e = self.env(tag="ok%d" % i, files=files)
            self.assertEqual(e.run("", env={"LAMPLIGHTER_REPO": REPO, "LAMPLIGHTER_BRANCH": "main"}), 0, e.text)

    def test_a_release_cannot_quietly_redirect_later_updates(self):
        e = self.env()
        write_tree(e.root, {"version.json": json.dumps({"version": OLD, "repo": REPO, "branch": "main"}).encode()})
        files = stub_files(NEW)
        files["version.json"] = json.dumps({"version": NEW, "repo": "evil/evil", "branch": "evilbranch"}).encode()
        e.transport.routes[ZIP_URL] = make_zip(files)
        self.assertEqual(e.run("", env={}), 0, e.text)
        self.assertIn("evil/evil", e.text)           # the player is told the new file names another source
        self.assertIn("points updates at a different", e.text)
        with open(os.path.join(e.home, "config.json")) as f:
            self.assertEqual(json.load(f), {"repo": REPO, "branch": "main"})
        e.lines.clear()
        self.assertEqual(e.run("repo", env={}), 0)
        self.assertIn("%s, branch main" % REPO, e.text)
        self.assertIn("repo from config.json", e.text)
        e.transport.calls.clear()
        e.run("check", env={})
        self.assertEqual(e.transport.calls, [VERSION_URL])      # still the repo the player started with

    def test_a_players_own_setting_is_left_alone_when_the_release_names_another_source(self):
        e = self.env()
        files = stub_files(NEW)
        files["version.json"] = json.dumps({"version": NEW, "repo": "other/place"}).encode()
        e.transport.routes[ZIP_URL] = make_zip(files)
        self.assertEqual(e.run(""), 0, e.text)       # REPO comes from the environment here
        self.assertIn("still decides", e.text)
        self.assertFalse(os.path.exists(os.path.join(e.home, "config.json")))

    def test_the_same_repo_in_the_new_version_json_says_nothing(self):
        e = self.env()
        files = stub_files(NEW)
        files["version.json"] = json.dumps({"version": NEW, "repo": REPO.upper(), "branch": "main"}).encode()
        e.transport.routes[ZIP_URL] = make_zip(files)
        self.assertEqual(e.run(""), 0, e.text)
        self.assertNotIn("different", e.text)


class WhyTests(unittest.TestCase):
    def test_reasons_are_the_real_reason_not_a_repr(self):
        import errno
        import shutil
        e = shutil.Error([("C:\\a\\b.json", "C:\\c\\d.json", "No space left on device")])
        self.assertIn("No space left on device", update.why(e))
        self.assertNotIn("[(", update.why(e))
        e = OSError(errno.EACCES, "Access is denied", os.path.join("C:", os.sep, "Users", "x", "game", "tools"))
        self.assertEqual(update.why(e), "Access is denied (tools)")
        self.assertNotIn("\\\\", update.why(e))
        self.assertEqual(update.why(ValueError("odd")), "ValueError: odd")

    def test_a_version_with_trailing_whitespace_shows_its_whitespace(self):
        with self.assertRaises(UpdateError) as cm:
            update.version_key("2.0.0\n")
        self.assertIn("\\n", str(cm.exception))


# --------------------------------------------------------------------------- review fixes: backups

class BackupOrderTests(OfflineCase):
    def seed(self, e, n=5):
        base = os.path.join(e.home, "backups")
        names = ["2026110%d-120000-2.0.0-dev.%d" % (i + 1, i) for i in range(n)]
        for i, name in enumerate(names):
            write_tree(base, {name + "/main.json": b'{"save_version": 1, "hp": %d}' % (100 + i)})
        return base, names

    def test_the_backup_the_player_is_told_about_survives_even_if_the_clock_was_reset(self):
        e = self.env()
        base, names = self.seed(e)
        self.assertEqual(e.run("", now=lambda: "20000101-000000"), 0, e.text)
        made = [n for n in os.listdir(base) if n not in names]
        self.assertEqual(made, ["20000101-000000-" + OLD])
        self.assertIn(os.path.join(base, made[0]), e.text)
        self.assertTrue(os.path.isfile(os.path.join(base, made[0], "main.json")))
        self.assertEqual(len(os.listdir(base)), 5)                  # tidied to five, oldest first
        self.assertNotIn(names[0], os.listdir(base))

    def test_failed_installs_never_push_older_backups_out(self):
        def broken_zip(e):
            e.transport.routes[ZIP_URL] = UpdateError("Could not reach codeload.github.com (timed out).")

        def not_a_zip(e):
            e.transport.routes[ZIP_URL] = b"no"

        def bad_validator(e):
            e.transport.routes[ZIP_URL] = make_zip(stub_files(NEW, validator_ok=False))

        for label, breaker in (("download", broken_zip), ("zip", not_a_zip), ("validator", bad_validator)):
            with self.subTest(label):
                e = self.env(tag=label)
                base, names = self.seed(e)
                breaker(e)
                for _ in range(3):
                    self.assertEqual(e.run(""), 1)
                self.assertEqual(sorted(os.listdir(base)), sorted(names), "a failed install changed the backups")
                self.assertEqual(e.read("main.py"), b"print('old game')\n")

    def test_a_failed_swap_that_was_rolled_back_removes_its_own_backup(self):
        e = self.env()
        base, names = self.seed(e)
        up = e.updater(run_checks=lambda tree, stage: None)
        real, count = up._move, []

        def flaky(src, dst):
            count.append(1)
            if len(count) == 4:
                raise OSError("injected")
            return real(src, dst)
        up._move = flaky
        with mock.patch.object(update, "Updater", lambda **kw: up):
            self.assertEqual(update.run_command("", e.lines.append, lambda q: True), 1)
        self.assertEqual(sorted(os.listdir(base)), sorted(names))

    def test_a_game_folder_that_cannot_be_written_stops_before_a_backup_or_a_download(self):
        e = self.env()
        real = os.mkdir

        def refuse(path, *a, **kw):
            if os.path.basename(path) == update.STAGE_DIR:
                raise PermissionError(5, "Access is denied", path)
            return real(path, *a, **kw)
        before = snapshot(e.root)
        with mock.patch.object(update.os, "mkdir", refuse):
            self.assertEqual(e.run(""), 1)
        self.assertIn("read-only", e.text)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertFalse(os.path.exists(os.path.join(e.home, "backups")))
        self.assertEqual(snapshot(e.root), before)

    def test_a_full_disk_during_the_backup_says_so(self):
        import shutil
        e = self.env()
        err = shutil.Error([("a.json", "b.json", "No space left on device")])
        with mock.patch.object(update.shutil, "copytree", side_effect=err):
            self.assertEqual(e.run(""), 1)
        self.assertIn("No space left on device", e.text)
        self.assertNotIn("[(", e.text)


# --------------------------------------------------------------------------- review fixes: saves in the dry run

class DryRunSaveFileTests(OfflineCase):
    def test_files_the_game_set_aside_or_archived_do_not_block_an_update(self):
        e = self.env()
        write_tree(e.home, {"saves/main.damaged.json": b"{this save got cut off",
                            "saves/main.damaged.2.json": b"\xff\xfe nope",
                            "saves/main.v1.bak.json": b"{ not json either",
                            "saves/main.v99.bak.json": b'{"save_version": 99, "poison": true}'})
        self.assertEqual(e.run(""), 0, e.text)
        self.assertEqual(e.read("main.py"), b"print('new game')\n")
        # all of them are still there, and in the backup
        for name in ("main.damaged.json", "main.damaged.2.json", "main.v1.bak.json", "main.v99.bak.json"):
            self.assertTrue(os.path.exists(os.path.join(e.home, "saves", name)), name)

    def test_force_is_not_needed_for_them_either(self):
        e = self.env(new_version=OLD)
        write_tree(e.home, {"saves/main.damaged.json": b"{"})
        self.assertEqual(e.run("force"), 0, e.text)

    def test_a_save_with_a_byte_order_mark_loads_in_the_dry_run_as_it_does_in_the_game(self):
        e = self.env()
        write_tree(e.home, {"saves/main.json": b"\xef\xbb\xbf" + b'{"save_version": 1, "hp": 9}'})
        from lamplighter import save
        with open(os.path.join(PROJECT, "tests", "fixtures", "saves", "v2_current.json"), "rb") as f:
            real_save = f.read()
        with temp_home() as game_home:      # the game itself reads a save with a BOM without complaint
            write_tree(game_home, {"saves/main.json": codecs.BOM_UTF8 + real_save})
            self.assertIsInstance(save.read_info("main", keep_copy=False)[0], dict)
        self.assertEqual(e.run(""), 0, e.text)

    def test_a_live_save_that_cannot_be_read_still_blocks_and_says_what_to_do(self):
        e = self.env()
        write_tree(e.home, {"saves/main.json": b"{ cut off"})
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1)
        self.assertIn("main.json", e.text)
        self.assertIn("Continue", e.text)
        self.assertIn("move the file out of the saves folder", e.text)
        self.assertUntouched(e, before)

    def test_advice_to_update_is_not_given_while_updating(self):
        files = stub_files(NEW)
        files["lamplighter/save.py"] = (
            b"class SaveError(Exception):\n    pass\n\n\ndef migrate(data):\n"
            b"    raise SaveError('This save is from a newer version of the game. Your save file has not been "
            b"changed. Update the game (run: python main.py --update), then try again.')\n")
        e = self.env(files=files)
        self.assertEqual(e.run(""), 1)
        self.assertIn("newer version of the game", e.text)
        self.assertNotIn("Update the game", e.text)
        self.assertNotIn("then try again", e.text)

    def test_real_tree_ignores_archived_and_set_aside_saves(self):
        blob, _ = RealTreeTests.real_zip(self)
        e = self.env(tag="real2", zip_bytes=blob, new_version="9.9.9", saves=False)
        fixtures = os.path.join(PROJECT, "tests", "fixtures", "saves")
        os.makedirs(os.path.join(e.home, "saves"))
        for name in os.listdir(fixtures):
            with open(os.path.join(fixtures, name), "rb") as src:
                data = src.read()
            with open(os.path.join(e.home, "saves", name), "wb") as dst:
                dst.write(b"\xef\xbb\xbf" + data)      # a BOM, as Notepad writes
        write_tree(e.home, {"saves/main.damaged.json": b"{", "saves/main.v99.bak.json": b'{"save_version": 99}'})
        self.assertEqual(e.run(""), 0, e.text)


# --------------------------------------------------------------------------- review fixes: the archive

class ArchiveLimitTests(OfflineCase):
    def test_the_shipped_limits_are_what_the_docs_say(self):
        self.assertEqual(update.ALLOWED_HOSTS, ("raw.githubusercontent.com", "codeload.github.com", "github.com"))
        self.assertEqual(update.MAX_VERSION_BYTES, 256 * 1024)
        self.assertEqual(update.MAX_ZIP_BYTES, 50 * 1024 * 1024)
        self.assertEqual(update.MAX_MEMBERS, 3000)
        self.assertEqual(update.MAX_UNCOMPRESSED, 30 * 1024 * 1024)
        self.assertEqual(update.MAX_MEMBER_BYTES, 5 * 1024 * 1024)
        self.assertEqual(update.MAX_RATIO, 100)
        self.assertEqual(update.NET_TIMEOUT, 10)
        self.assertEqual(update.DOWNLOAD_DEADLINE, 300)
        self.assertEqual(update.CHECK_TIMEOUT, 120)
        self.assertEqual(update.BACKUPS_KEEP, 5)
        self.assertEqual(update.ALLOWED_NAMES, ("lamplighter", "tools", "tests", "docs", "main.py", "version.json",
                                                "README.md"))
        # the real game must fit comfortably under the caps, or the first update would refuse itself
        total = biggest = 0
        for name in update.ALLOWED_NAMES:
            path = os.path.join(PROJECT, name)
            sizes = []
            if os.path.isfile(path):
                sizes.append(os.path.getsize(path))
            for here, dirs, fs in os.walk(path):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                sizes += [os.path.getsize(os.path.join(here, f)) for f in fs if not f.endswith(".pyc")]
            total += sum(sizes)
            biggest = max([biggest] + sizes)
        self.assertLess(total * 4, update.MAX_UNCOMPRESSED)
        self.assertLess(biggest * 4, update.MAX_MEMBER_BYTES)

    def test_a_tiny_download_that_unpacks_to_a_huge_file_is_refused(self):
        files = stub_files(NEW)
        files["docs/zeros.bin"] = b"\0" * (4 * 1024 * 1024)       # under the per-file cap, but 4000:1
        e = self.env(files=files)
        self.assertLess(len(e.zip), 64 * 1024)
        self.abort(e, "takes to send")

    def abort(self, e, expect):
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1, e.text)
        self.assertIn(expect, e.text)
        self.assertUntouched(e, before)

    def test_a_big_file_that_is_really_big_is_fine_if_it_does_not_balloon(self):
        files = stub_files(NEW)
        files["docs/big.bin"] = os.urandom(1024 * 1024)          # 1 MB that does not compress
        e = self.env(files=files)
        self.assertEqual(e.run(""), 0, e.text)
        self.assertEqual(len(e.read("docs/big.bin")), 1024 * 1024)

    def test_many_installed_files_that_add_up_to_too_much_are_refused(self):
        files = stub_files(NEW)
        for i in range(8):
            files["docs/part%d.bin" % i] = os.urandom(200 * 1024)
        e = self.env(files=files)
        with mock.patch.object(update, "MAX_UNCOMPRESSED", 1024 * 1024):
            self.abort(e, "far more data")

    def test_repo_housekeeping_that_is_never_installed_cannot_block_an_update(self):
        files = stub_files(NEW)
        files.update({".github/aux.txt": b"x", "assets/a:b.png": b"x", "assets/trailing.": b"x",
                      "assets/" + "/".join(["d"] * 20) + "/x.png": b"x",
                      "assets/huge.bin": b"\0" * (8 * 1024 * 1024)})
        e = self.env(files=files)
        self.assertEqual(e.run(""), 0, e.text)
        self.assertFalse(os.path.exists(os.path.join(e.root, "assets")))
        self.assertFalse(os.path.exists(os.path.join(e.root, ".github")))
        # but the same names inside an installed folder are still refused
        files = stub_files(NEW)
        files["docs/aux.txt"] = b"x"
        e = self.env(tag="b", files=files)
        self.assertEqual(e.run(""), 1)
        self.assertIn("device name", e.text)

    def test_links_and_escapes_are_refused_wherever_they_are(self):
        for label, extra, expect in [
                ("link outside", [("game-main/assets/link", b"x", 0o120777 << 16)], "symbolic link"),
                ("escape outside", [("game-main/assets/../../evil", b"x", None)], "climbs out"),
                ("control character outside", [("game-main/assets/a\x01b", b"x", None)], "suspicious")]:
            with self.subTest(label):
                e = self.env(tag=label.replace(" ", "_"), zip_bytes=make_zip(stub_files(NEW), extra=extra))
                before = snapshot(e.root)
                self.assertEqual(e.run(""), 1, e.text)
                self.assertIn(expect, e.text)
                self.assertUntouched(e, before)


# --------------------------------------------------------------------------- review fixes: the real transport

class SlowResponse(FakeResponse):
    """A connection that trickles: read1 returns one byte, the way a real socket does after a short wait."""

    def __init__(self):
        FakeResponse.__init__(self, b"", headers={})
        self.reads = 0

    def read1(self, n=-1):
        self.reads += 1
        return b"x"

    def read(self, n=-1):
        raise AssertionError("read(n) waits for n bytes, so it cannot be used to enforce a deadline")


class TransportDeadlineTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.getaddrinfo", "socket.create_connection"):
            p = mock.patch(target, side_effect=AssertionError("the network was touched"))
            p.start()
            self.addCleanup(p.stop)
        self.response = FakeResponse(b'{"version": "2.0.0"}')

        def fake_open(opener, req, *a, **kw):
            return self.response
        p = mock.patch.object(urllib.request.OpenerDirector, "open", fake_open)
        p.start()
        self.addCleanup(p.stop)

    def test_the_download_deadline_is_enforced_for_a_connection_that_trickles(self):
        self.response = SlowResponse()
        clock = [0.0]

        def monotonic():
            clock[0] += 1.0
            return clock[0]
        fake_time = mock.Mock(monotonic=monotonic)
        with mock.patch.object(update, "time", fake_time):
            with self.assertRaises(UpdateError) as cm:
                update.HttpsTransport(deadline=5).get(VERSION_URL, 10 ** 6)
        self.assertIn("took too long", str(cm.exception))
        self.assertLess(self.response.reads, 20)

    def test_the_deadline_clock_starts_before_the_connection_is_opened(self):
        times = iter([0.0, 400.0, 401.0, 402.0])
        self.response = FakeResponse(b"x" * 10)
        with mock.patch.object(update, "time", mock.Mock(monotonic=lambda: next(times))):
            with self.assertRaises(UpdateError) as cm:
                update.HttpsTransport(deadline=300).get(VERSION_URL, 1000)
        self.assertIn("took too long", str(cm.exception))

    def test_every_request_has_a_network_timeout(self):
        seen = []

        def recording_open(opener, req, *a, **kw):
            seen.append(kw)
            return self.response
        with mock.patch.object(urllib.request.OpenerDirector, "open", recording_open):
            update.HttpsTransport().get(VERSION_URL, 1000)
            update.HttpsTransport(timeout=3).get(VERSION_URL, 1000)
        self.assertEqual([kw.get("timeout") for kw in seen], [update.NET_TIMEOUT, 3])


class TrickleServerTests(unittest.TestCase):
    """The deadline against a real socket: a server that sends one byte every fifth of a second forever."""

    def test_a_trickling_server_is_cut_off_at_the_deadline(self):
        import http.server
        import threading
        import time
        stop = threading.Event()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "1000000")
                self.end_headers()
                try:
                    while not stop.is_set():
                        self.wfile.write(b"x")
                        self.wfile.flush()
                        time.sleep(0.2)
                except OSError:
                    pass

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d/zip" % server.server_address[1]
        result = []

        def fetch():
            started = time.monotonic()
            try:
                update.HttpsTransport(timeout=5, deadline=1).get(url, 10 ** 7)
                result.append(("returned", time.monotonic() - started))
            except UpdateError as e:
                result.append((str(e), time.monotonic() - started))

        try:
            with mock.patch.object(update, "check_url", lambda u: u), \
                    mock.patch.dict(os.environ, {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}):
                t = threading.Thread(target=fetch, daemon=True)
                t.start()
                t.join(25)
        finally:
            stop.set()
            server.shutdown()
            server.server_close()
        self.assertFalse(t.is_alive(), "the download was still running long after its deadline")
        self.assertIn("took too long", result[0][0])
        self.assertLess(result[0][1], 8)


# --------------------------------------------------------------------------- review fixes: checks and interrupts

class CheckProcessTests(OfflineCase):
    def test_a_check_that_leaves_a_child_behind_still_times_out_on_time_and_the_child_is_stopped(self):
        import time
        beat = os.path.join(self.tmp, "heartbeat.txt")
        files = stub_files(NEW)
        # the child writes a byte every fifth of a second for at most 10 seconds, then gives up on its own
        child = "import time\nfor _ in range(50):\n    open(%r, 'a').write('x')\n    time.sleep(0.2)\n" % beat
        files["tools/validate_content.py"] = (
            "import subprocess, sys, tempfile, time\n"
            "subprocess.Popen([sys.executable, '-c', %r], cwd=tempfile.gettempdir())\n"
            "time.sleep(60)\n" % child).encode()
        e = self.env(files=files)
        before = snapshot(e.root)
        started = time.monotonic()
        with mock.patch.object(update, "CHECK_TIMEOUT", 2):
            self.assertEqual(e.run(""), 1)
        self.assertLess(time.monotonic() - started, 20)
        self.assertIn("did not finish", e.text)
        self.assertUntouched(e, before)
        self.assertTrue(os.path.exists(beat), "the child never started")
        size = os.path.getsize(beat)
        time.sleep(1.5)
        self.assertEqual(os.path.getsize(beat), size, "the check's child process was left running")

    def test_check_output_does_not_need_a_pipe_and_is_still_reported(self):
        e = self.env(validator_ok=False)
        self.assertEqual(e.run(""), 1)
        self.assertIn("room x points at nothing", e.text)

    def test_runaway_output_is_trimmed(self):
        files = stub_files(NEW)
        files["tools/validate_content.py"] = b"import sys\nprint('x' * 5000000)\nprint('the end')\nsys.exit(1)\n"
        e = self.env(files=files)
        self.assertEqual(e.run(""), 1)
        self.assertIn("the end", e.text)
        self.assertLess(len(e.text), 5000)


class InterruptTests(OfflineCase):
    def test_ctrl_c_while_downloading_cancels_cleanly(self):
        e = self.env()
        e.transport.routes[ZIP_URL] = KeyboardInterrupt()
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1)
        self.assertIn("cancelled", e.text)
        self.assertIn("were not changed", e.text)
        self.assertNotIn("Traceback", e.text)
        self.assertUntouched(e, before)
        self.assertEqual(os.listdir(os.path.join(e.home, "backups")), [])      # the attempt's backup is gone too

    def test_ctrl_c_while_copying_the_saves_leaves_no_half_made_backup(self):
        e = self.env()
        real = shutil.copytree

        def cut_short(src, dst, *a, **kw):
            real(src, dst, *a, **kw)
            raise KeyboardInterrupt()
        before = snapshot(e.root)
        with mock.patch.object(update.shutil, "copytree", cut_short):
            self.assertEqual(e.run(""), 1)
        self.assertEqual(os.listdir(os.path.join(e.home, "backups")), [])
        self.assertIn("cancelled", e.text)
        self.assertUntouched(e, before)

    def test_ctrl_c_during_the_checks_kills_them_and_cancels(self):
        e = self.env()
        before = snapshot(e.root)

        def interrupted(tree, stage):
            raise KeyboardInterrupt()
        self.assertEqual(e.run("", run_checks=interrupted), 1)
        self.assertIn("cancelled", e.text)
        self.assertUntouched(e, before)

    def test_ctrl_c_in_the_swap_is_rolled_back_and_reported_as_cancelled(self):
        e = self.env()
        before = snapshot(e.root)
        up = e.updater(run_checks=lambda tree, stage: None)
        real, count = up._move, []

        def flaky(src, dst):
            count.append(1)
            if len(count) == 5:
                raise KeyboardInterrupt()
            return real(src, dst)
        up._move = flaky
        with mock.patch.object(update, "Updater", lambda **kw: up):
            self.assertEqual(update.run_command("", e.lines.append, lambda q: True), 1)
        self.assertIn("cancelled", e.text)
        self.assertUntouched(e, before)

    def test_input_that_has_run_out_is_a_no_not_a_crash(self):
        e = self.env()
        before = snapshot(e.root)

        def confirm(question):
            raise EOFError()
        rc = update.run_command("", e.lines.append, confirm, transport=e.transport, game_root=e.root,
                                data_dir=e.home, env={"LAMPLIGHTER_REPO": REPO}, now=e.clock)
        self.assertEqual(rc, 0)
        self.assertIn("Nothing was changed", e.text)
        self.assertNotIn("unexpected", e.text)
        self.assertEqual(snapshot(e.root), before)


# --------------------------------------------------------------------------- review fixes: wording on the command line

class CommandLineWordingTests(OfflineCase):
    def test_no_repo_on_the_command_line_says_how_to_set_it_there(self):
        e = self.env()
        self.assertEqual(e.run("check", env={}, cli=True), 0)
        self.assertIn("python main.py --update repo owner/name", e.text)
        self.assertNotIn("type update", e.text.lower())
        e.lines.clear()
        e.run("check", env={})
        self.assertIn("type: update repo owner/name", e.text)
        self.assertNotIn("python main.py", e.text)

    def test_asking_where_updates_come_from_with_no_repo_does_not_say_there_is_nothing_to_check(self):
        e = self.env()
        e.run("repo", env={})
        self.assertIn("No update repo is set.", e.text)
        self.assertNotIn("nothing to check", e.text)
        self.assertIn("update repo owner/name", e.text)

    def test_the_install_question_does_not_tell_a_command_line_user_to_type_save(self):
        e = self.env()
        e.run("", cli=True)
        self.assertNotIn("type save", e.text)
        other = self.env(tag="b")
        other.run("")
        self.assertIn("type save first", other.text)

    def test_usage_on_the_command_line_uses_the_command_line_words(self):
        e = self.env()
        self.assertEqual(e.run("banana", cli=True), 1)
        self.assertIn("python main.py --update repo owner/name", e.text)

    def run_main(self, *args, **extra):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, LAMPLIGHTER_HOME=home)
            env.pop("LAMPLIGHTER_REPO", None)
            env.update(extra)
            r = subprocess.run([sys.executable, os.path.join(PROJECT, "main.py"), "--update"] + list(args), env=env,
                               capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
            cfg = os.path.join(home, "config.json")
            saved = None
            if os.path.exists(cfg):
                with open(cfg) as f:
                    saved = json.load(f)
            return r.returncode, r.stdout.decode("utf-8", "replace"), saved

    def test_repo_can_be_set_with_the_words_main_py_advertises(self):
        rc, out, saved = self.run_main("repo", "me/game")
        self.assertEqual((rc, saved), (0, {"repo": "me/game"}), out)
        rc, out, saved = self.run_main("repo me/game")            # or all in one quoted argument
        self.assertEqual(saved, {"repo": "me/game"}, out)

    def test_unknown_words_on_the_command_line_exit_nonzero(self):
        rc, out, _ = self.run_main("bogus")
        self.assertEqual(rc, 1, out)
        self.assertIn("python main.py --update check", out)


# --------------------------------------------------------------------------- review fixes: messages

class MessageTests(OfflineCase):
    def test_a_locked_file_is_named_and_the_advice_is_given(self):
        import errno
        e = self.env()
        up = e.updater(run_checks=lambda tree, stage: None)
        real, count = up._move, []

        def locked(src, dst):
            count.append(1)
            if len(count) == 4:
                raise OSError(errno.EACCES, "Access is denied", src)
            return real(src, dst)
        up._move = locked
        before = snapshot(e.root)
        with mock.patch.object(update, "Updater", lambda **kw: up):
            self.assertEqual(update.run_command("", e.lines.append, lambda q: True), 1)
        self.assertIn("Access is denied", e.text)
        self.assertIn("close anything that has the game folder open", e.text)
        self.assertIn("put back as it was", e.text)
        self.assertNotIn("\\\\", e.text)
        self.assertUntouched(e, before)

    def test_a_failed_rollback_lists_what_is_in_update_old_and_keeps_the_older_copy(self):
        e = self.env()
        write_tree(e.root, {update.OLD_DIR + "/lamplighter/ancient.py": b"ANCIENT\n"})
        up = e.updater(run_checks=lambda tree, stage: None)
        real, count = up._move, []

        def flaky(src, dst):
            count.append(1)
            if len(count) == 6:
                raise OSError("injected")
            return real(src, dst)
        up._move = flaky
        try:
            with mock.patch.object(update, "Updater", lambda **kw: up), \
                    mock.patch.object(update.os, "rename", side_effect=OSError("disk gone")):
                self.assertEqual(update.run_command("", e.lines.append, lambda q: True), 1)
            self.assertIn("could not put everything back", e.text)
            self.assertRegex(e.text, r"files are in .*\(.*lamplighter.*\)")
            self.assertIn("Starting the game again tries", e.text)
            # the copy of the code from before the last update must survive: it is the only extra one
            self.assertEqual(e.read(update.STAGE_DIR + "/previous_old/lamplighter/ancient.py"), b"ANCIENT\n")
            # and the marker stays, so the next start puts things right
            self.assertTrue(os.path.exists(os.path.join(e.root, update.SWAP_MARKER)))
        finally:
            for name in (update.OLD_DIR, update.STAGE_DIR):
                if os.path.exists(os.path.join(e.root, name)):
                    update._rmtree(os.path.join(e.root, name))


# --------------------------------------------------------------------------- review fixes: a swap that is cut short

def load_main():
    """main.py as a module (its game start-up is under `if __name__ == '__main__'`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("lamplighter_main_for_tests", os.path.join(PROJECT, "main.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CRASH_SCRIPT = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from lamplighter import update
root, home, tree, stage, crash_at = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6])
u = update.Updater(out=print, confirm=lambda q: True, game_root=root, data_dir=home, env={})
real, calls = os.rename, [0]
def move(src, dst):
    calls[0] += 1
    if calls[0] == crash_at:
        os._exit(9)          # the power goes: no except blocks, no finally blocks
    real(src, dst)
u._move = move
if crash_at < 0:
    update._remove_quietly = lambda path: None
u._swap(tree, stage)
os._exit(0)
"""


class InterruptedSwapTests(OfflineCase):
    def build(self, tag, previous_old=False, no_readme=False):
        e = self.env(tag=tag)
        if no_readme:
            os.remove(os.path.join(e.root, "README.md"))           # the old game had none
        if previous_old:
            write_tree(e.root, {update.OLD_DIR + "/lamplighter/ancient.py": b"ANCIENT\n"})
        before = snapshot(e.root)
        stage = os.path.join(e.root, update.STAGE_DIR)
        tree = os.path.join(stage, "tree")
        write_tree(tree, stub_files(NEW))
        return e, before, stage, tree

    def crash(self, e, tree, stage, crash_at):
        r = subprocess.run([sys.executable, "-I", "-c", CRASH_SCRIPT, PROJECT, e.root, e.home, tree, stage,
                            str(crash_at)], capture_output=True, timeout=60)
        return r.returncode

    def test_the_marker_is_there_during_the_swap_and_gone_after_success_or_a_clean_rollback(self):
        e, before, stage, tree = self.build("marker")
        marker = os.path.join(e.root, update.SWAP_MARKER)
        up = e.updater(run_checks=lambda t, s: None)
        real, seen = up._move, []

        def watching(src, dst):
            seen.append(os.path.exists(marker))
            return real(src, dst)
        up._move = watching
        up._swap(tree, stage)
        self.assertTrue(seen and all(seen), "the marker must exist before the first file moves")
        self.assertFalse(os.path.exists(marker))
        update._rmtree(stage)
        update._rmtree(os.path.join(e.root, update.OLD_DIR))
        # a rollback that works leaves no marker either
        e2, before2, stage2, tree2 = self.build("marker2")
        up2 = e2.updater()
        real2, n = up2._move, []

        def flaky(src, dst):
            n.append(1)
            if len(n) == 5:
                raise OSError("injected")
            return real2(src, dst)
        up2._move = flaky
        with self.assertRaises(UpdateError):
            up2._swap(tree2, stage2)
        self.assertFalse(os.path.exists(os.path.join(e2.root, update.SWAP_MARKER)))
        update._rmtree(stage2)
        self.assertEqual(snapshot(e2.root), before2)

    def test_a_kill_at_every_point_in_the_swap_is_put_right_on_the_next_start(self):
        main = load_main()
        for previous_old in (False, True):
            # 7 names that exist and 7 that come in, 14 moves, plus one if an old .update_old is moved aside
            for crash_at in range(1, (15 if previous_old else 14) + 1):
                with self.subTest(previous_old=previous_old, crash_at=crash_at):
                    e, before, stage, tree = self.build("k%d%d" % (previous_old, crash_at), previous_old)
                    self.assertEqual(self.crash(e, tree, stage, crash_at), 9)
                    self.assertTrue(os.path.exists(os.path.join(e.root, update.SWAP_MARKER)))
                    import contextlib
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        main.recover_interrupted_update(e.root)
                    self.assertIn("cut short", out.getvalue())
                    self.assertEqual(snapshot(e.root), before, "the game folder is not back as it was")
                    # and a second start finds nothing to do
                    with contextlib.redirect_stdout(io.StringIO()) as quiet:
                        main.recover_interrupted_update(e.root)
                    self.assertEqual(quiet.getvalue(), "")

    def test_nothing_happens_when_there_is_no_marker(self):
        main = load_main()
        e = self.env()
        before = snapshot(e.root)
        write_tree(e.root, {update.OLD_DIR + "/lamplighter/ancient.py": b"ANCIENT\n"})
        before = snapshot(e.root)
        main.recover_interrupted_update(e.root)
        self.assertEqual(snapshot(e.root), before)

    def test_an_unreadable_marker_means_no_move_was_made_and_touches_no_game_file(self):
        main = load_main()
        e, before, stage, tree = self.build("badmarker", previous_old=True)
        write_tree(e.root, {update.SWAP_MARKER: b"{ half a marker"})
        with mock.patch("sys.stdout", new=io.StringIO()):
            main.recover_interrupted_update(e.root)
        self.assertEqual(snapshot(e.root), before)      # the older .update_old was not mistaken for the one to restore

    def test_an_update_will_not_start_while_an_earlier_one_is_waiting_to_be_put_right(self):
        e = self.env()
        write_tree(e.root, {update.SWAP_MARKER: b"{}"})
        before = snapshot(e.root)
        self.assertEqual(e.run(""), 1)
        self.assertIn("cut short", e.text)
        self.assertEqual(e.transport.calls, [VERSION_URL])
        self.assertEqual(snapshot(e.root), before)

    def test_a_file_the_update_added_is_removed_again(self):
        main = load_main()
        e, before, stage, tree = self.build("newonly", no_readme=True)
        # killed after the very last move, before the marker was deleted: everything new is in place
        self.assertEqual(self.crash(e, tree, stage, -1), 0)
        self.assertTrue(os.path.exists(os.path.join(e.root, update.SWAP_MARKER)))
        self.assertEqual(e.read("README.md"), b"new readme\n")
        with mock.patch("sys.stdout", new=io.StringIO()):
            main.recover_interrupted_update(e.root)
        self.assertEqual(snapshot(e.root), before)

    def test_the_real_main_py_puts_a_killed_update_right_before_it_imports_the_game(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as home:
            for name in update.ALLOWED_NAMES:
                src = os.path.join(PROJECT, name)
                dst = os.path.join(root, name)
                if os.path.isdir(src):
                    shutil_copy(src, dst)
                elif os.path.isfile(src):
                    shutil_copy(src, dst)
            with open(os.path.join(root, "version.json")) as f:
                vj = json.load(f)
            vj.pop("repo", None)         # whatever the project says, this test must never reach for the network
            vj.pop("branch", None)
            with open(os.path.join(root, "version.json"), "w") as f:
                json.dump(vj, f)
            before = snapshot(root)
            # the state after a kill: the game's package has been moved aside and the new one is not in yet
            os.makedirs(os.path.join(root, update.OLD_DIR))
            os.rename(os.path.join(root, "lamplighter"), os.path.join(root, update.OLD_DIR, "lamplighter"))
            os.makedirs(os.path.join(root, update.STAGE_DIR, "tree"))
            with open(os.path.join(root, update.SWAP_MARKER), "w") as f:
                json.dump({"incoming": list(update.ALLOWED_NAMES), "existing": list(update.ALLOWED_NAMES),
                           "had_old": False}, f)
            env = dict(os.environ, LAMPLIGHTER_HOME=home)
            env.pop("LAMPLIGHTER_REPO", None)
            r = subprocess.run([sys.executable, os.path.join(root, "main.py"), "--update", "check"], env=env,
                               capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
            out = r.stdout.decode("utf-8", "replace")
            self.assertEqual(r.returncode, 0, out + r.stderr.decode("utf-8", "replace"))
            self.assertIn("cut short", out)
            self.assertIn("No update repo is set", out)         # and then it carried on as normal
            after = {k: v for k, v in snapshot(root).items() if "__pycache__" not in k and not k.endswith(".pyc")}
            before = {k: v for k, v in before.items() if "__pycache__" not in k and not k.endswith(".pyc")}
            self.assertEqual(after, before)


def shutil_copy(src, dst):
    import shutil
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copyfile(src, dst)


if __name__ == "__main__":
    unittest.main()
