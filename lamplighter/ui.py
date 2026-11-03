"""Terminal presentation: colour, wrapping, typewriter text, bars and menus.

All input and output goes through the module-level `io` object so the game can be
driven by a script (for automated playtests) as easily as by a person.
"""
import os
import re
import shutil
import sys
import textwrap
import time

# --------------------------------------------------------------------------- setup

def _enable_windows_ansi():
    if os.name == "nt":
        try:
            os.system("")  # flips the console into VT mode on Windows 10+
        except Exception:
            pass

_enable_windows_ansi()
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import msvcrt  # Windows: lets a keypress skip the typewriter effect
except ImportError:  # pragma: no cover - non-Windows
    msvcrt = None


class Settings:
    color = "NO_COLOR" not in os.environ
    typewriter = True
    speed = 0.012  # seconds per character


settings = Settings()

CODES = {
    "reset": "0", "b": "1", "dim": "2", "i": "3", "u": "4",
    "red": "31", "green": "32", "yellow": "33", "blue": "34", "magenta": "35",
    "cyan": "36", "white": "37", "grey": "90",
    "bred": "91", "bgreen": "92", "byellow": "93", "bblue": "94",
    "bmagenta": "95", "bcyan": "96", "bwhite": "97",
    # semantic names used by game text
    "amber": "38;5;214", "flame": "38;5;208", "ember": "38;5;202",
    "gold": "38;5;220", "ash": "38;5;245", "night": "38;5;61",
    "hollow": "38;5;99", "brine": "38;5;37", "moss": "38;5;107",
    "blood": "38;5;160", "bone": "38;5;230", "sky": "38;5;117",
}

_TAG = re.compile(r"\{(/?)([a-z]*)\}")


def c(text):
    """Render inline colour tags like '{amber}lantern{/}' to ANSI (or strip them)."""
    if not settings.color:
        return _TAG.sub(lambda m: "" if (m.group(1) or m.group(2) in CODES) else m.group(0), text)
    stack = []

    def repl(m):
        closing, name = m.group(1), m.group(2)
        if not closing and not name:
            return m.group(0)
        if closing or name == "reset":
            if stack:
                stack.pop()
            return "\x1b[0m" + "".join("\x1b[%sm" % CODES[n] for n in stack)
        if name not in CODES:
            return m.group(0)
        stack.append(name)
        return "\x1b[%sm" % CODES[name]

    return _TAG.sub(repl, text) + ("\x1b[0m" if stack else "")


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(s):
    return len(_ANSI.sub("", _TAG.sub("", s)))


def width():
    return max(50, min(100, shutil.get_terminal_size((88, 24)).columns - 2))


# --------------------------------------------------------------------------- io

class IO:
    """Swappable input/output. In script mode lines come from a list."""

    def __init__(self):
        self.pending = None  # a command typed inside a menu, run once the menu closes
        self.escape_words = set()
        self.in_combat = False
        self.script = None
        self.echo = False
        self.transcript = None
        self.written = 0       # how many writes have happened (to tell if an action printed anything)
        self.since_clear = 0   # writes since the screen was last cleared
        self.capture = None    # when a list, game text is also recorded here (combat round log)
        self.hold = 0          # >0 while menus/prompts print, so they stay out of the capture
        self.mute = False      # simulations switch all output off

    def write(self, s=""):
        if self.mute:
            return
        sys.stdout.write(s)
        sys.stdout.flush()
        if s:
            self.written += 1
            self.since_clear += 1
            if self.capture is not None and not self.hold:
                self.capture.append(s)
        if self.transcript is not None:
            self.transcript.append(_ANSI.sub("", s))

    def read(self, prompt=""):
        if self.script is not None:
            if not self.script:
                raise EOFError("script exhausted")
            line = self.script.pop(0)
            self.write(prompt + line + "\n")
            return line
        try:
            return input(prompt)
        except KeyboardInterrupt:
            return "quit"

    def start_capture(self):
        self.capture = []

    def take_capture(self):
        text = "".join(self.capture or [])
        self.capture = None
        return text


def _is_tty():
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def clear():
    """Wipe the screen so the next thing shown stands alone."""
    if io.mute:
        return
    if io.script is not None or not _is_tty():
        sys.stdout.write("\n" + "═" * 30 + " [new screen] " + "═" * 30 + "\n")
    else:
        sys.stdout.write("\x1b[2J\x1b[3J\x1b[H")
    sys.stdout.flush()
    io.since_clear = 0


io = IO()


def _keypress_waiting():
    if msvcrt is None:
        return False
    try:
        if msvcrt.kbhit():
            msvcrt.getwch()
            return True
    except Exception:
        pass
    return False


def say(text="", indent=2, wrap=True, slow=False):
    """Print wrapped, colour-tagged text. `slow` uses the typewriter if enabled."""
    if io.mute:
        return
    if text == "":
        io.write("\n")
        return
    lines = []
    for para in text.split("\n"):
        if wrap and visible_len(para) > width() - indent:
            lines.extend(_wrap_tagged(para, width() - indent))
        else:
            lines.append(para)
    pad = " " * indent
    out = "\n".join(pad + c(l) for l in lines) + "\n"
    if slow and settings.typewriter and io.script is None and _is_tty():
        _typewrite(out)
    else:
        io.write(out)


def _wrap_tagged(para, w):
    # wrap on visible text, keeping tags attached to words
    words = para.split(" ")
    lines, cur, cur_len = [], [], 0
    for word in words:
        wl = visible_len(word)
        if cur and cur_len + 1 + wl > w:
            lines.append(" ".join(cur))
            cur, cur_len = [word], wl
        else:
            cur.append(word)
            cur_len += wl + (1 if cur_len else 0)
    if cur:
        lines.append(" ".join(cur))
    # carry open colour tags across line breaks so wrapped text keeps its colour
    fixed, open_tags = [], []
    for line in lines:
        prefix = "".join("{%s}" % t for t in open_tags)
        for m in _TAG.finditer(line):
            if not m.group(1) and not m.group(2):
                continue
            if m.group(1) or m.group(2) == "reset":
                if open_tags:
                    open_tags.pop()
            elif m.group(2) in CODES:
                open_tags.append(m.group(2))
        fixed.append(prefix + line + "{/}" * len(open_tags))
    return fixed


def _typewrite(out):
    i = 0
    while i < len(out):
        if out[i] == "\x1b":
            j = out.index("m", i) + 1
            io.write(out[i:j])
            i = j
            continue
        io.write(out[i])
        if _keypress_waiting():
            io.write(out[i + 1:])
            return
        if out[i] in ".!?":
            time.sleep(settings.speed * 6)
        elif out[i] != " ":
            time.sleep(settings.speed)
        i += 1


def narrate(text):
    say(text, slow=True)


def blank():
    io.write("\n")


def rule(title="", color="amber", char="─"):
    if io.mute:
        return
    w = width()
    if title:
        t = " %s " % title
        left = 3
        right = max(0, w - left - visible_len(t))
        io.write(c("{%s}%s{/}{b}%s{/}{%s}%s{/}" % (color, char * left, t, color, char * right)) + "\n")
    else:
        io.write(c("{%s}%s{/}" % (color, char * w)) + "\n")


def bar(cur, mx, length=14, full="amber", empty="grey", ch="█", ech="░"):
    mx = max(1, mx)
    filled = max(0, min(length, round(length * cur / mx)))
    if cur > 0 and filled == 0:
        filled = 1
    return "{%s}%s{/}{%s}%s{/}" % (full, ch * filled, empty, ech * (length - filled))


def hp_color(cur, mx):
    r = cur / max(1, mx)
    return "bgreen" if r > 0.6 else ("byellow" if r > 0.3 else "bred")


class held:
    """Keep prompts and menus out of the combat round log."""

    def __enter__(self):
        io.hold += 1

    def __exit__(self, *exc):
        io.hold -= 1


def ask(prompt="> "):
    with held():
        blank()
        return io.read(c("{amber}%s{/}" % prompt)).strip()


def pause(msg="(press Enter to continue)"):
    with held():
        blank()
        io.read(c("  {grey}%s{/}" % msg))


def menu(options, prompt="Choose", allow_cancel=True, cancel_label="Back"):
    """Numbered menu. options: list of labels (may contain colour tags).
    Returns the chosen index, or None if cancelled."""
    with held():
        return _menu(options, prompt, allow_cancel, cancel_label)


def _menu(options, prompt, allow_cancel, cancel_label):
    for i, label in enumerate(options, 1):
        say("{gold}[%d]{/} %s" % (i, label), indent=4)
    if allow_cancel:
        say("{grey}[0] %s{/}" % cancel_label, indent=4)
    while True:
        raw = ask("%s > " % prompt).lower()
        if allow_cancel and raw in ("0", "", "back", "b", "cancel", "q", "x"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        # allow typing the start of an option
        plain = [_TAG.sub("", o).lower().lstrip('"') for o in options]
        hits = [i for i, p in enumerate(plain) if raw and p.startswith(raw)]
        if len(hits) == 1:
            return hits[0]
        if allow_cancel and not io.in_combat and raw and raw.split()[0] in io.escape_words:
            io.pending = raw
            return None
        if allow_cancel and raw in ("leave", "bye", "goodbye", "done", "exit", "quit"):
            return None
        say("{grey}Pick a number from the list%s.{/}" % (" (0 to go back)" if allow_cancel else ""))


def confirm(question):
    with held():
        say(question + " {gold}[y/n]{/}")
        while True:
            a = ask("> ").lower()
            if a in ("y", "yes"):
                return True
            if a in ("n", "no", ""):
                return False


def sweep(stops, land, rounds=2):
    """The pack-opening reveal. stops: [(word, colour)], the tiers in order. A highlight races across them,
    slows, and lands on stops[land]. Any key skips. With animation off it just prints the result."""
    word, colour = stops[land]
    animate = (settings.typewriter and not io.mute and io.script is None and _is_tty())
    if animate:
        order = list(range(len(stops))) * rounds + list(range(land + 1))
        n = len(order)
        for k, idx in enumerate(order):
            cells = []
            for j, (w, col) in enumerate(stops):
                cells.append("{b}{%s}[ %s ]{/}{/}" % (col, w.upper()) if j == idx else "{grey}  %s  {/}" % w)
            io.write("\r  " + c(" ".join(cells)) + "   ")
            time.sleep(0.03 + 0.34 * (k / max(1, n - 1)) ** 2.6)
            if _keypress_waiting():
                break
        io.write("\n")
    say("{%s}{b}★ %s ★{/}{/}" % (colour, word.upper()), indent=4)


def title_art():
    art = r"""
         .              {flame})  {/}                                  .
              .        {flame}( ){/}          .                .
                      {amber}|^^|{/}
    .                {amber}/====\{/}        .            .               .
                     {amber}|{/}{byellow} ** {/}{amber}|{/}
                     {amber}|{/}{byellow} ** {/}{amber}|{/}                .        .
         .           {amber}\====/{/}
                       {ash}||{/}                    .
                       {ash}||{/}         .                      .
    {grey}~~~~~~~~~~~~~~~~~~~{/}{ash}||{/}{grey}~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~{/}
"""
    for line in art.split("\n"):
        io.write(c(line) + "\n")
    say("{b}{amber}T H E   L A S T   L A M P L I G H T E R{/}{/}", indent=10)
    say("{ash}a text adventure of oil, ash and the long night{/}", indent=14)
    blank()
