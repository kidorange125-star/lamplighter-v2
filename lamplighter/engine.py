"""The game loop, command parser and world rules."""
import collections
import copy
import difflib
import json
import os
import random
import time

from . import ui
from .ui import say, blank, narrate
from .combat import Combat
from .content import CLASSES, SKILLS
from .content import ITEMS, PAGES
from .quests import QUESTS
from .content import REGION_INFO, ROOMS, REGION_NAMES as REGIONS
from .entities import DREAD_COLOUR, Player
from . import areas, codes, dealer, events, forge, forge_ui, gear, magic_ui, maps, navigation, npcs, powerroll, rarity, save, savecheck, spells, town, update
from .version import VERSION


DIRS = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down"}
DIR_ALIASES = {"n": "n", "north": "n", "s": "s", "south": "s", "e": "e", "east": "e", "w": "w", "west": "w",
               "u": "u", "up": "u", "climb": "u", "upstairs": "u", "d": "d", "down": "d", "descend": "d",
               "downstairs": "d"}

VERBS = {
    "look": ["look", "l"],
    "go": ["go", "walk", "move", "head", "travel", "run"],
    "take": ["take", "get", "grab", "pick", "loot"],
    "drop": ["drop", "discard"],
    "inventory": ["inventory", "inv", "i", "bag", "items"],
    "equip": ["equip", "wear", "wield", "hold"],
    "unequip": ["unequip", "remove", "unwield"],
    "use": ["use", "drink", "eat", "quaff", "apply"],
    "examine": ["examine", "x", "inspect", "check", "study", "search"],
    "read": ["read"],
    "talk": ["talk", "speak", "ask", "chat", "greet"],
    "trade": ["trade", "shop", "buy", "sell", "browse"],
    "rest": ["rest", "sleep", "camp"],
    "light": ["light", "relight", "ignite"],
    "map": ["map", "m"],
    "collect": ["collect"],
    "stash": ["stash", "chest", "store"],
    "recall": ["recall"],
    "return": ["return"],
    "redeem": ["redeem", "code"],
    "update": ["update"],
    "town": ["town", "residents"],
    "forge": ["forge"],
    "spells": ["spells", "spell", "magic", "books"],
    "hint": ["hint", "hints", "objective", "goal", "where", "guide"],
    "travel": ["travel", "goto", "walk"],
    "journal": ["journal", "j", "quests", "quest", "q", "log"],
    "stats": ["stats", "status", "char", "character", "c", "sheet", "me"],
    "skills": ["skills", "abilities", "sk"],
    "train": ["train", "points", "allocate", "spend"],
    "lantern": ["lantern", "lamp", "oil"],
    "save": ["save"],
    "load": ["load", "restore"],
    "help": ["help", "h", "?", "commands"],
    "quit": ["quit", "exit"],
    "settings": ["settings", "options", "config"],
    "bounty": ["bounty", "claim"],
    "wait": ["wait", "z"],
    "pages": ["pages", "lore"],
}
VERB_LOOKUP = {alias: verb for verb, aliases in VERBS.items() for alias in aliases}
FILLER = {"the", "a", "an", "to", "at", "with", "on", "into", "in", "up", "from", "of", "my", "some"}


WOOD_WAYPOSTS = ("wood_path", "thicket", "moth_shrine")


def _as_list(x):
    return list(x) if isinstance(x, (list, tuple)) else [x]


class QuitGame(Exception):
    pass


class Game:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.player = None
        self.room_id = "hall"
        self.flags = {}
        self.quests = {}
        self.visited = set()
        self.room_items = {rid: list(r.get("items", [])) for rid, r in ROOMS.items()}
        self.cooldown = {}
        self.stats = {"kills": 0, "deaths": 0, "battles": 0}
        self.moves = 0
        self.last_rest = "hall"
        self.difficulty = 1.0
        self.diff_name = "Normal"
        self.started = time.time()
        self.over = False
        self.notices = []
        self.choices = []
        self.town = town.new_state()
        self.forge = forge.new_state()
        self.dealers = dealer.new_state()
        self.anchors = []
        self.interrupted = False

    # ================================================================== state helpers
    @property
    def room(self):
        return ROOMS[self.room_id]

    def is_dark(self, rid=None):
        rid = rid or self.room_id
        return ROOMS[rid]["dark"] and not self.flags.get("lit_" + rid)

    def benighted(self):
        return self.is_dark() and self.player.oil <= 0

    def shards(self):
        return sum(self.player.has_item(s) for s in ("ember_wood", "ember_tide", "ember_ash"))

    def quest(self, qid):
        return self.quests.get(qid, -1)

    def set_quest(self, qid, stage, quiet=False):
        old = self.quests.get(qid, -1)
        if old == stage:
            return
        self.quests[qid] = stage
        if quiet:
            return
        name = QUESTS[qid]["name"]
        if stage == "done":
            say("{gold}✦ Quest complete: %s{/}" % name)
        elif old == -1:
            say("{gold}✦ New quest: %s{/} {grey}(type 'journal'){/}" % name)
        else:
            say("{gold}✦ Journal updated: %s{/}" % name)

    def give(self, iid, n=1, quiet=False):
        self.player.add_item(iid, n)
        if not quiet:
            say("{bone}Received: %s%s{/}" % (ITEMS[iid]["name"], " x%d" % n if n > 1 else ""))
        self.after_gain(iid)

    def after_gain(self, iid):
        """Hooks that fire when an item is picked up."""
        if iid == "wren_ribbon" and self.quest("wren") in (-1, 0):
            self.set_quest("wren", 1)
        if iid == "starsteel_ore" and self.quest("starsteel") == 0:
            self.set_quest("starsteel", 1)
        if iid in ("ember_wood", "ember_tide", "ember_ash"):
            n = self.shards()
            say("{amber}You hold %d of the three Ember Shards.{/}" % n)
            if n == 3 and self.quest("main") == 1:
                self.set_quest("main", 2)
        if ITEMS[iid]["kind"] == "page":
            n = sum(1 for p in PAGES if self.player.has_item(p))
            say("{grey}(Journal pages found: %d/6. Type 'read %s' to read it.){/}" % (n, ITEMS[iid]["name"].split("(")[1][:-1].lower()
                                                                                     if "(" in ITEMS[iid]["name"] else "page"))
        areas.lookup("AFTER_GAIN", iid, self)

    def practice_fight(self, enemy_id="straw_hollow", intro=None):
        """A fight that costs nothing and changes nothing: health, oil, items, gold and stats are put back."""
        p = self.player
        keep = (p.hp, p.oil, dict(p.inventory), p.gold, p.xp, p.level, dict(self.stats), dict(p.equipment))
        self.interrupted = True
        Combat(self, [enemy_id], intro=intro).run()
        p.hp, p.oil, p.inventory, p.gold, p.xp, p.level = keep[0], keep[1], keep[2], keep[3], keep[4], keep[5]
        self.stats = keep[6]
        p.equipment = keep[7]
        p.statuses = {}
        p.shield = 0
        self.flags["practised"] = True

    def on_kill(self, enemy):
        if "practice" in enemy.tags:
            return
        base = powerroll.base_id(enemy.id)
        if "boss" in enemy.tags and not self.flags.get("gems_" + base):
            self.flags["gems_" + base] = True
            self.player.gems += 3
            say("{sky}+3 gems{/} {grey}(first time you have beaten %s){/}" % enemy.name.split(",")[0])
        self.stats["kills"] = self.stats.get("kills", 0) + 1
        if enemy.hollow:
            self.flags["bounty_unclaimed"] = self.flags.get("bounty_unclaimed", 0) + 1
            if self.quest("bounty") == -1:
                self.quests["bounty"] = 0

    # ================================================================== main loop
    def run(self):
        """Area screen -> pick an action -> the action gets its own screen -> Enter -> area screen."""
        ui.io.escape_words = set(VERB_LOOKUP) | set(DIR_ALIASES)
        self.tip("screens", "Type a number to take an action, or type any command. Enter brings you back here. Type {gold}hint{/} any time to be told what to do next.")
        while not self.over:
            if ui.io.pending:
                raw, ui.io.pending = ui.io.pending, None
            else:
                town.update(self)
                forge.update(self)
                self.render_room()
                try:
                    raw = ui.ask("What will you do? > ")
                except EOFError:
                    raise QuitGame()
            raw = raw.strip()
            if raw.isdigit():
                n = int(raw)
                if 1 <= n <= len(self.choices):
                    raw = self.choices[n - 1]
                else:
                    self.notice("There's no action %d. Pick a number from the list, or type a command." % n)
                    continue
            if not raw:
                continue
            ui.clear()
            mark = ui.io.written
            for part in raw.split(" then "):
                self.handle(part.strip())
                if self.over:
                    break
            if self.over:
                break
            if ui.io.written > mark and not ui.io.pending:
                ui.pause()

    def add_dread(self, n, in_combat=False):
        """Change the player's Dread. Companions steady the nerves; outside a fight it stops short of 100."""
        p = self.player
        if n > 0 and self.flags.get("wren_following"):
            n = max(1, int(n * 0.75))
        before = p.dread_tier
        p.dread = max(0, min(100 if in_combat else 99, p.dread + n))
        after = p.dread_tier
        if not in_combat and n > 0 and after != before:
            words = {"Uneasy": "A chill settles on you. You feel Uneasy.",
                     "Afraid": "Your hands will not stay steady. You are Afraid.",
                     "Terrified": "The dark presses in. You are Terrified."}
            if after in words:
                self.notice("{%s}%s{/} {grey}(Dread %d. Light and rest calm you.){/}" % (
                    DREAD_COLOUR[after], words[after], p.dread))
        if p.dread >= 25:
            self.tip("dread", "Dread rises in the dark. A little makes you hit harder, but it also makes you easier to hit, "
                              "and a lot is dangerous. Lit places, resting, and hot meals bring it down.")

    def tip(self, key, text):
        """Show a one-time tip on the next area screen."""
        if not self.flags.get("tip_" + key):
            self.flags["tip_" + key] = True
            self.notices.append("{sky}Tip:{/} " + text)

    def notice(self, text):
        """A short message shown on the area screen instead of on a screen of its own."""
        self.notices.append(text)

    def handle(self, raw):
        words = [w for w in raw.lower().replace(",", " ").split() if w]
        if not words:
            return
        first = words[0]
        if first in DIR_ALIASES and len(words) == 1:
            return self.move(DIR_ALIASES[first])
        if first in ("talk", "speak") and len(words) > 1 and words[1] in ("to", "with"):
            words = [first] + words[2:]
        if first == "pick" and len(words) > 1 and words[1] == "up":
            words = ["take"] + words[2:]
        if first == "look" and len(words) > 1 and words[1] in ("at", "in"):
            words = ["examine"] + words[2:]
        verb = VERB_LOOKUP.get(first)
        if not verb:
            # 'north' etc. as a two word 'go north'? or a bare noun like 'orrin'
            options = list(VERB_LOOKUP) + list(DIR_ALIASES)
            close = difflib.get_close_matches(first, options, n=1, cutoff=0.75)
            if close:
                self.notice("I don't know '%s'. Did you mean '%s'?" % (first, close[0]))
            else:
                self.notice("I don't know how to '%s'. Type 'help' for a list of commands." % first)
            return
        rest = [w for w in words[1:] if w not in FILLER]
        noun = " ".join(rest)
        getattr(self, "cmd_" + verb)(noun)

    # ================================================================== area screen
    def render_room(self):
        p = self.player
        r = self.room
        ui.clear()
        col = ui.hp_color(p.hp, p.max_hp)
        oil_col = "amber" if p.oil > 25 else ("bred" if p.oil <= 0 else "ember")
        say("{b}%s{/} {grey}the %s · level %d{/}    HP %s {%s}%d/%d{/}    Oil %s {%s}%d/%d{/}    {gold}%dg{/}%s%s" % (
            p.name, p.cls_name, p.level, ui.bar(p.hp, p.max_hp, 10, full=col), col, p.hp, p.max_hp,
            ui.bar(p.oil, p.max_oil, 10, full=oil_col), oil_col, p.oil, p.max_oil, p.gold,
            ("    {sky}%d gems{/}" % p.gems if p.gems else ""),
            ("    {%s}Dread %d %s{/}" % (DREAD_COLOUR[p.dread_tier], p.dread, p.dread_tier) if p.dread >= 25 else "") +
            ("    {bgreen}%d points to spend{/}" % p.points if p.points else "")), wrap=False)
        light = "{grey}dark{/}" if self.is_dark() else "{amber}lit{/}"
        ui.rule("%s {grey}·{/} {ash}%s{/} {grey}·{/} %s" % (r["name"], r["region"], light))
        if self.benighted():
            say("{night}It is pitch black. Your lantern is dry. You can feel cold air, wet stone, the sense of "
                "things moving nearby. You could find your way out by touch, but not much else.{/}")
        else:
            say(r["desc"])
            if r.get("waypost"):
                if self.flags.get("lit_" + self.room_id):
                    say("{amber}The guild waypost burns bright and steady. Hollows won't come near it.{/}")
                else:
                    say("{grey}The guild waypost here is cold.{/}")
            items = self.room_items.get(self.room_id, [])
            if items:
                say("{bone}You see: %s.{/}" % ", ".join(ITEMS[i]["name"] for i in items))
            people = [npcs.NPCS[n]["name"] for n in self.present_npcs()]
            if people:
                say("{sky}Here: %s.{/}" % ", ".join(people))
        line = navigation.objective_line(self)
        if line:
            blank()
            say("{gold}\u25c6{/} " + line)
        if self.notices:
            blank()
            for n in self.notices:
                say("{amber}»{/} %s" % n)
            self.notices = []
        blank()
        self.choices = []
        for i, (label, cmd, star) in enumerate(self.suggestions()[:9], 1):
            self.choices.append(cmd)
            if star:
                say("{gold}★ [%d] %s{/}  {grey}(suggested){/}" % (i, label))
            else:
                say("  {gold}[%d]{/} %s" % (i, label))
        blank()
        say("{grey}Or type any command:  hint · map · travel · i pack · j journal · c character · lantern · help{/}")

    def suggestions(self):
        """Numbered actions for the area screen. The first is the suggested next move."""
        p = self.player
        r = self.room
        here_items = self.room_items.get(self.room_id, [])
        people = [] if self.benighted() else self.present_npcs()
        safe = self.safe_here()
        out = []

        def add(label, cmd):
            if cmd not in [c for _, c, _ in out]:
                out.append((label, cmd, False))

        star = None
        spare_oil = "oil" if p.inventory.get("oil") else ("tallow" if p.inventory.get("tallow") else None)
        if p.points:
            star = ("Spend your %d level-up points" % p.points, "train")
        elif self.benighted() and spare_oil:
            star = ("Refill your lantern. You can't see a thing", "use " + spare_oil)
        elif self.is_dark() and p.oil < 25 and spare_oil:
            star = ("Refill your lantern (oil is low)", "use " + spare_oil)
        elif p.hp < p.max_hp * 0.4 and not safe and (p.inventory.get("draught") or p.inventory.get("strong_draught")):
            star = ("Drink a healing draught", "use draught" if p.inventory.get("draught") else "use strong draught")
        elif self.room_id in ("smithy", "ember_smithy") and forge.ready_jobs(self):
            star = ("Collect your finished forging", "forge")
        elif (navigation.main_objective(self) or {}).get("room") == self.room_id and any(
                npcs.has_news(self, n) for n in people):
            n = next(n for n in people if npcs.has_news(self, n))
            star = ("Talk to %s" % npcs.NPCS[n]["name"], "talk " + n)
        elif here_items and not self.benighted():
            star = ("Take everything here", "take all")
        elif any(npcs.has_news(self, n) for n in people):
            n = next(n for n in people if npcs.has_news(self, n))
            star = ("Talk to %s" % npcs.NPCS[n]["name"], "talk " + n)
        elif (r.get("beacon") and self.flags.get(r.get("boss", "")) and not self.flags.get("beacon_" + r["region"])
              and p.oil >= r.get("beacon_oil", 25)):
            star = ("Light the beacon (%d oil)" % r.get("beacon_oil", 25), "light")
        elif r.get("waypost") and not self.flags.get("lit_" + self.room_id) and p.oil >= 10:
            star = ("Relight the waypost (10 oil)", "light")
        elif safe and (p.hp < p.max_hp * 0.7 or p.oil < p.max_oil * 0.5):
            star = ("Rest and refill your lantern", "rest")
        elif self.room_id in ("home", "yard") and town.rent_due(self) >= 10:
            star = ("Collect your rent (%d gold)" % town.rent_due(self), "collect")
        elif self.room_id == "square" and self.flags.get("bounty_unclaimed"):
            star = ("Claim your Hollow bounty (%d)" % self.flags["bounty_unclaimed"], "bounty")
        else:
            step = navigation.first_step(self)
            if step:
                d, why = step
                star = ("Go %s: %s" % (DIRS[d], why), DIRS[d])
        if star:
            out.append((star[0], star[1], True))

        for n in people:
            add("Talk to %s" % npcs.NPCS[n]["name"], "talk " + n)
        for n in people:
            if npcs.NPCS[n].get("shop"):
                add("Trade with %s" % npcs.NPCS[n]["name"].split(" the ")[0], "trade")
        if here_items and not self.benighted():
            add("Take %s" % (ITEMS[here_items[0]]["name"] if len(here_items) == 1 else "everything here"), "take all")
        if r.get("waypost") and not self.flags.get("lit_" + self.room_id):
            add("Relight the waypost (10 oil)", "light")
        if r.get("beacon") and self.flags.get(r.get("boss", "")) and not self.flags.get("beacon_" + r["region"]):
            add("Light the beacon (%d oil)" % r.get("beacon_oil", 25), "light")
        if safe:
            add("Rest", "rest")
        if self.room_id in ("smithy", "ember_smithy"):
            add("Use the forge", "forge")
        if self.room_id == "home":
            add("Open your stash (%d/%d)" % (town.stash_used(self), town.stash_capacity(self)), "stash")
        if self.room_id in ("home", "yard") and town.rent_rate(self):
            add("Collect rent (%d gold waiting)" % town.rent_due(self), "collect")
        if (REGION_INFO[r["region"]]["ring"] > 0 and p.has_item("homecoming_charm") and p.relic_charges > 0
                and (p.hp < p.max_hp * 0.5 or p.oil < 30)):
            add("Recall to Hollowmere (%d charge%s left)" % (p.relic_charges, "" if p.relic_charges == 1 else "s"), "recall")
        for d in ["n", "s", "e", "w", "u", "d"]:
            if d not in r["exits"]:
                continue
            lock = r.get("locks", {}).get(d)
            if lock and not self.unlocked(lock):
                continue
            dest = r["exits"][d]
            where = ROOMS[dest]["name"] if dest in self.visited and not self.benighted() else "unexplored"
            add("Go %s {grey}- %s{/}" % (DIRS[d], where), DIRS[d])
        return out

    def present_npcs(self):
        out = []
        for n in self.room.get("npcs", []):
            if npcs.is_present(self, n):
                out.append(n)
        # some people move: Wren sits in the tavern once she is home
        for n, spec in npcs.NPCS.items():
            where = spec.get("where")
            if where and where(self) == self.room_id and n not in out:
                out.append(n)
        return out

    # ================================================================== movement
    def unlocked(self, lock):
        if lock.get("remember") and self.flags.get(lock["remember"]):
            return True
        if "element" in lock:
            return any(spells.element_of(b) in lock["element"] for b in self.player.spells)
        if "item" in lock:
            return self.player.has_item(lock["item"])
        if "flag" in lock:
            return bool(self.flags.get(lock["flag"]))
        if "shards" in lock:
            return self.shards() >= lock["shards"]
        if "building" in lock:
            return town.is_built(self, lock["building"])
        if "flags" in lock:
            return all(self.flags.get(f) for f in lock["flags"])
        if "relic" in lock:
            return any(t in _as_list(lock["relic"]) for t, _ in self.worn_relics())
        if "dread" in lock:
            d = lock["dread"]
            return d.get("min", 0) <= self.player.dread <= d.get("max", 100)
        if "all" in lock:
            return all(self.unlocked(sub) for sub in lock["all"])
        return True

    def worn_relics(self):
        """[(relic type, rarity)] for every relic socketed into the gear the player has on."""
        out = []
        for iid in self.player.equipment.values():
            if iid and gear.is_instance(iid):
                for rel in gear.socketed(iid):
                    out.append((ITEMS[rel["base"]]["relic"], rel.get("rarity", "common")))
        return out

    def lock_status(self, lock):
        """One grey line saying where the player stands against a lock (empty for plain item/flag/building locks)."""
        parts = []
        if "element" in lock:
            have = [spells.element_of(b).title() for b in self.player.spells]
            parts.append("Equipped books: %s" % (", ".join(have) if have else "none"))
        if "relic" in lock:
            worn = ["%s (%s)" % (t.title(), r) for t, r in self.worn_relics()]
            parts.append("Worn relics: %s" % (", ".join(worn) if worn else "none"))
        if "dread" in lock:
            parts.append("Dread is %d now." % self.player.dread)
        if "flags" in lock:
            done = sum(1 for f in lock["flags"] if self.flags.get(f))
            parts.append("%d of %d done." % (done, len(lock["flags"])))
        for sub in lock.get("all", []):
            text = self.lock_status(sub)
            if text:
                parts.append(text)
        return " ".join(parts)

    def cmd_go(self, noun):
        if not noun:
            self.notice("Go where? (north, south, east, west, up, down), or 'travel' to walk to a place you know.")
            return
        d = DIR_ALIASES.get(noun.split()[0])
        if not d:
            return self.cmd_travel(noun)  # "go chapel" works like "travel chapel"
        self.move(d)

    def move(self, d):
        r = self.room
        if d not in r["exits"]:
            self.notice("You can't go %s from here." % DIRS[d])
            return
        lock = r.get("locks", {}).get(d)
        if lock and not self.unlocked(lock):
            self.notice(lock["msg"])
            status = self.lock_status(lock)
            if status:
                self.notice("{grey}%s{/}" % status)
            return
        if lock:
            key = "opened_%s_%s" % (self.room_id, d)
            if lock.get("remember"):
                self.flags[lock["remember"]] = True
            if not self.flags.get(key):
                self.flags[key] = True
                events.on_unlock(self, self.room_id, d)
        dest = r["exits"][d]
        problems = self.boss_warning(dest)
        if problems:
            ui.rule("DANGER AHEAD", color="blood")
            say("Something dangerous waits in {b}%s{/}. Before you go in:" % ROOMS[dest]["name"])
            for text in problems:
                say("  {ember}-{/} %s" % text)
            tip = navigation.boss_tip(dest)
            if tip:
                say("{grey}Tip: %s{/}" % tip)
            blank()
            if not ui.confirm("Go in anyway?"):
                return
        events.on_leave(self, self.room_id, dest)
        self.room_id = dest
        self.moves += 1
        town.on_step(self)
        forge.on_step(self)
        p = self.player
        if self.is_dark():
            before = p.oil
            p.oil = max(0, p.oil - p.move_cost)
            self.tip("dark", "This place is dark. Every step into the dark burns lantern oil (see the top line). "
                             "{gold}use oil{/} refills it. If it runs dry you cannot see what enemies will do.")
            if before > 0 and p.oil == 0:
                self.interrupted = True
                self.notice("{bred}Your lantern gutters and goes out. You are in the dark.{/} "
                            "{grey}Refill it with oil, or find light. Hollows grow bold in the dark.{/}")
            elif before > 25 >= p.oil:
                self.interrupted = True
                self.notice("{ember}Your lantern is running low on oil (%d).{/}" % p.oil)
        ring = REGION_INFO[ROOMS[dest]["region"]]["ring"]
        if ring == 0:
            p.calm()                       # the town is safe
        elif self.is_dark():
            self.add_dread((ring + 1) * (2 if self.benighted() else 1))
        else:
            self.add_dread(-3)
        first = dest not in self.visited
        self.visited.add(dest)
        if first:
            self.flags["visited_regions"] = sorted(set(self.flags.get("visited_regions", [])) | {self.room["region"]})
        if self.room.get("rest") or self.room.get("waypost"):
            self.tip("rest", "You can {gold}rest{/} in a safe lit place like this to heal, refill your lantern and save the game.")
        if events.on_enter(self, dest, first):
            self.interrupted = True
            return
        if self.over or self.room_id != dest:
            return
        fixed = self.room.get("fixed")
        if fixed and not self.flags.get(fixed["flag"]):
            outcome = self.fight(fixed["enemies"], intro=fixed.get("intro"))
            if outcome == "win":
                self.flags[fixed["flag"]] = True
                events.after_fixed(self, fixed["flag"])
            return
        self.maybe_encounter()

    def boss_warning(self, dest):
        """Reasons the player is poorly prepared to enter an unbeaten boss room (empty list or None if fine)."""
        flag = ROOMS[dest].get("boss")
        if not flag or flag == "ending" or self.flags.get(flag):
            return None
        p = self.player
        problems = []
        flasks = p.inventory.get("oil", 0)
        if p.oil < min(60, p.max_oil * 0.5):
            problems.append("your lantern is low (%d/%d oil)%s. Flares are your best weapon." % (
                p.oil, p.max_oil, ", but you have %d flask%s: type {gold}use oil{/}" % (flasks, "" if flasks == 1 else "s")
                if flasks else ""))
        heals = sum(p.inventory.get(i, 0) for i in ("draught", "strong_draught", "honeycake", "stew"))
        if heals < 2:
            problems.append("you carry only %d healing item%s." % (heals, "" if heals == 1 else "s"))
        if p.hp < p.max_hp * 0.7:
            problems.append("you are hurt (%d/%d health). Rest first if you can." % (p.hp, p.max_hp))
        return problems

    def maybe_encounter(self):
        r = self.room
        enc = r.get("enc")
        if not enc or not self.is_dark():
            return
        if self.cooldown.get(self.room_id, 0) > self.moves:
            return
        chance = enc["chance"]
        if r["region"] == "Weeping Wood" and self.quest("wayposts") == "done":
            chance *= 0.5
        if self.benighted():
            chance += 0.2
        if self.rng.random() >= chance:
            return
        groups = [g for g, _ in enc["groups"]]
        weights = [w for _, w in enc["groups"]]
        group = self.rng.choices(groups, weights=weights)[0]
        ambush = self.benighted() or self.rng.random() < 0.08
        self.cooldown[self.room_id] = self.moves + 4
        self.fight(group, ambush=ambush)

    # ================================================================== combat glue
    def fight(self, enemy_ids, intro=None, ambush=False, on_phase=None):
        self.interrupted = True
        outcome = Combat(self, enemy_ids, ambush=ambush, intro=intro, on_phase=on_phase).run()
        if outcome == "dead":
            self.death()
        elif outcome == "fled":
            # fall back to the previous safe-ish room: just stay, but cool down encounters here
            self.cooldown[self.room_id] = self.moves + 3
            say("{grey}You catch your breath. They have lost your trail, for now.{/}")
        return outcome

    def death(self):
        p = self.player
        blank()
        ui.rule("THE DARK TAKES YOU", color="blood")
        narrate("{night}Your lantern rolls from your hand. The last thing you see is its flame, very small, "
                "and then even that is gone.{/}")
        self.stats["deaths"] = self.stats.get("deaths", 0) + 1
        lost = p.gold // 2
        p.gold -= lost
        p.hp = p.max_hp
        p.oil = max(p.oil, p.max_oil // 2)
        p.statuses = {}
        self.room_id = self.last_rest
        blank()
        if self.last_rest == "hall":
            narrate("You wake in your bunk in the Lamplighters' Hall, aching all over. Hesk found you and carried "
                    "you home. Your purse is lighter by %d gold. Someone had to pay for the carrying." % lost)
        elif self.last_rest == "home":
            narrate("You wake in your own bed, and the slate by the door is one stroke longer. Someone carried you home. "
                    "Your purse is lighter by %d gold." % lost)
        elif self.last_rest == "court_gate":
            narrate("You wake on a cot in the Court Gate, under a blanket that smells of smoke. Pell is sitting by the "
                    "hearth, not looking at you. Your purse is lighter by %d gold." % lost)
        elif self.last_rest == "tallow_camp":
            narrate("You wake among Tallow's candles. 'Found you,' says the merchant, 'floating. Lucky I like "
                    "customers.' Your purse is lighter by %d gold." % lost)
        elif ROOMS[self.last_rest].get("wake"):
            w = ROOMS[self.last_rest]["wake"]
            narrate(w % lost if "%d" in w else w)
        else:
            narrate("You wake beside the waypost's steady flame. Something dragged you here, into the light. "
                    "Your purse is lighter by %d gold." % lost)

    def award_xp(self, n):
        say("{gold}+%d xp{/}" % n)
        levels = self.player.gain_xp(n)
        if levels:
            self.level_up_ceremony(levels)

    def level_up_ceremony(self, levels):
        p = self.player
        blank()
        ui.rule("LEVEL UP", color="gold")
        say("{gold}{b}You are now level %d.{/}{/} Health restored. {grey}(+2 points to spend per level){/}" % p.level)
        grow = CLASSES[p.cls]["grow"]
        say("{grey}Your training as a %s grants +%d %s automatically.{/}" % (p.cls_name, levels, grow.upper()))
        for s in CLASSES[p.cls]["skills"]:
            lvl = SKILLS[s]["level"]
            if p.level - levels < lvl <= p.level:
                say("{bgreen}New skill: %s{/} {grey}- %s{/}" % (SKILLS[s]["name"], SKILLS[s]["desc"]))
        self.cmd_train("")

    # ================================================================== commands
    def cmd_look(self, noun):
        if noun:
            return self.cmd_examine(noun)

    def cmd_wait(self, noun):
        say("{grey}You wait. The dark waits with you.{/}")
        self.moves += 1
        self.maybe_encounter()

    def cmd_help(self, noun):
        blank()
        ui.rule("HOW TO PLAY")
        rows = [
            ("n / s / e / w / u / d", "move (or 'go north')"),
            ("look  (l)", "describe the room again"),
            ("examine <thing>  (x)", "look closely at an item, person or feature"),
            ("take <item> / take all", "pick things up"),
            ("talk <person>", "talk to someone here"),
            ("trade", "buy and sell with a merchant here"),
            ("inventory  (i)", "your bag and equipment"),
            ("equip / unequip <item>", "change weapon, armour or trinket"),
            ("use <item>", "drink a draught, refill your lantern..."),
            ("read <page>", "read a journal page you have found"),
            ("light", "relight a guild waypost (10 oil)"),
            ("spells", "equip your spell books (cast them in a fight with S1, S2...)"),
            ("recall / return", "Homecoming Charm: go home / go back to where you last rested"),
            ("stash  /  collect", "your chest (at home)  /  collect rent (home or Builder's Yard)"),
            ("town", "your residents, buildings and rent"),
            ("redeem <code>", "enter a gem code"),
            ("update", "look for a newer version and install it (update check, update repo owner/name)"),
            ("rest", "recover fully in a safe, lit place (also saves)"),
            ("stats (c) / skills / train", "character sheet, skills, spend level points"),
            ("lantern", "check your lantern and oil"),
            ("hint", "what to do next, with the exact route to type"),
            ("map (m) / map world", "the labelled map of this region / every region"),
            ("travel <place>", "walk to a place you have been (or 'travel objective')"),
            ("journal (j)", "your quests"),
            ("bounty", "claim Hollow bounties at the square"),
            ("save / load / settings / quit", ""),
        ]
        for a, b in rows:
            say("{gold}%-28s{/} {grey}%s{/}" % (a, b))
        blank()
        say("{amber}Your lantern{/} burns oil each time you enter a dark place. When it runs dry you are "
            "{night}benighted{/}: you cannot see what enemies are about to do, Hollows ambush you and hit "
            "harder. Keep it fed. Relit wayposts, the Hall, and other safe places refill it when you rest.")
        say("{grey}You can chain commands: 'n then take all then e'.{/}")

    # ---------------------------------------------------------------- items
    def resolve(self, noun, scopes=("room", "inv", "equip", "npc"), quiet=False):
        """Find things matching `noun`. Returns list of (kind, id)."""
        noun = noun.strip()
        if not noun:
            return []
        cands = []
        if "room" in scopes:
            for iid in dict.fromkeys(self.room_items.get(self.room_id, [])):
                cands.append(("room", iid, ITEMS[iid]["name"]))
        if "inv" in scopes:
            for iid in self.player.inventory:
                cands.append(("inv", iid, ITEMS[iid]["name"]))
        if "equip" in scopes:
            for slot, iid in self.player.equipment.items():
                if iid:
                    cands.append(("equip", iid, ITEMS[iid]["name"]))
        if "npc" in scopes:
            for nid in self.present_npcs():
                spec = npcs.NPCS[nid]
                cands.append(("npc", nid, spec["name"] + " " + " ".join(spec.get("aliases", []))))
        exact, partial = [], []
        nw = noun.split()
        for kind, iid, name in cands:
            name_l = name.lower().replace("'", "").replace("(", "").replace(")", "")
            words = name_l.split()
            if noun == name_l or noun == iid:
                exact.append((kind, iid))
            elif all(any(w.startswith(x.replace("'", "")) for w in words) for x in nw):
                partial.append((kind, iid))
        return exact or partial

    def choose_one(self, matches, what="Which one"):
        if len(matches) == 1:
            return matches[0]
        uniq = list(dict.fromkeys(matches))
        if len({m[1] for m in uniq}) == 1:
            return uniq[0]
        labels = []
        for kind, iid in uniq:
            if kind == "npc":
                labels.append(npcs.NPCS[iid]["name"])
            else:
                labels.append("%s {grey}(%s){/}" % (ITEMS[iid]["name"],
                                                     {"room": "here", "inv": "in your bag", "equip": "equipped"}[kind]))
        say("%s?" % what)
        i = ui.menu(labels, prompt=what)
        return None if i is None else uniq[i]

    def cmd_take(self, noun):
        if self.benighted():
            say("{night}You grope around in the dark and find nothing but cold stone.{/}")
            return
        here = self.room_items.get(self.room_id, [])
        if not noun:
            say("Take what?")
            return
        if noun in ("all", "everything"):
            if not here:
                say("{grey}There is nothing here to take.{/}")
                return
            for iid in list(here):
                self._take(iid)
            return
        m = self.resolve(noun, scopes=("room",))
        if not m:
            if self.resolve(noun, scopes=("npc",)):
                say("{grey}They would object.{/}")
            elif self.resolve(noun, scopes=("inv", "equip")):
                say("{grey}You already have that.{/}")
            else:
                say("{grey}You don't see any '%s' here.{/}" % noun)
            return
        pick = self.choose_one(m, "Take which")
        if pick:
            self._take(pick[1])

    def _take(self, iid):
        self.room_items[self.room_id].remove(iid)
        say("You take the {bone}%s{/}." % ITEMS[iid]["name"])
        self.player.add_item(iid)
        self.after_gain(iid)

    def cmd_drop(self, noun):
        m = self.resolve(noun, scopes=("inv",))
        if not m:
            say("{grey}You aren't carrying that.{/}")
            return
        pick = self.choose_one(m, "Drop which")
        if not pick:
            return
        iid = pick[1]
        if ITEMS[iid]["kind"] in ("key", "page"):
            say("{grey}You'd better hold on to that.{/}")
            return
        self.player.remove_item(iid)
        self.room_items.setdefault(self.room_id, []).append(iid)
        say("You drop the %s." % ITEMS[iid]["name"])

    def cmd_inventory(self, noun):
        p = self.player
        blank()
        ui.rule("PACK")
        for slot in ("weapon", "armor", "trinket"):
            iid = p.equipment[slot]
            if iid:
                say("{grey}%-8s{/} %s {grey}%s{/}" % (slot.title(), rarity.label(iid), self.stat_text(iid)))
            else:
                say("{grey}%-8s -{/}" % slot.title())
        blank()
        groups = {"consumable": "Supplies", "weapon": "Weapons", "armor": "Armour", "trinket": "Trinkets",
                  "key": "Keepsakes", "page": "Journal Pages", "junk": "Valuables", "material": "Building materials",
                  "relic": "Relics", "book": "Spell books"}
        any_items = False
        for kind, label in groups.items():
            items = [(iid, n) for iid, n in p.inventory.items() if ITEMS[iid]["kind"] == kind]
            if not items:
                continue
            any_items = True
            say("{amber}%s{/}" % label)
            for iid, n in sorted(items, key=lambda x: ITEMS[x[0]]["name"]):
                extra = self.stat_text(iid) if kind in ("weapon", "armor", "trinket") else ""
                say("  %s%s {grey}%s{/}" % (rarity.label(iid), " x%d" % n if n > 1 else "", extra))
        if not any_items:
            say("{grey}Your pack is empty.{/}")
        blank()
        say("{gold}%d gold{/}   {sky}%d gems{/}   {amber}Lantern oil %d/%d{/}" % (p.gold, p.gems, p.oil, p.max_oil))

    def stat_text(self, iid):
        st = ITEMS[iid].get("stats", {})
        names = {"atk": "ATK", "def": "DEF", "wil": "WIL", "agi": "AGI", "str": "STR", "hp": "HP",
                 "crit": "CRIT%", "dodge": "DODGE%", "regen": "REGEN", "oil_save": "OIL"}
        parts = []
        for k, v in st.items():
            if k == "oil_save":
                parts.append("-%d oil per step" % v)
            else:
                parts.append("%s%+d" % (names.get(k, k), v))
        names = {"dmg": "all damage", "phys": "weapon damage", "fire": "fire damage", "light": "flare damage", "heal": "healing"}
        for k, v in ITEMS[iid].get("mult", {}).items():
            parts.append("x%.2f %s" % (v, names.get(k, k)))
        return "(" + ", ".join(parts) + ")" if parts else ""

    def cmd_equip(self, noun):
        p = self.player
        m = [x for x in self.resolve(noun, scopes=("inv", "room"))
             if ITEMS[x[1]]["kind"] in ("weapon", "armor", "trinket")]
        if not m:
            say("{grey}You have nothing like that to equip.{/}")
            return
        pick = self.choose_one(m, "Equip which")
        if not pick:
            return
        kind, iid = pick
        if kind == "room":
            self._take(iid)
        slot = ITEMS[iid]["kind"]
        old = p.equipment[slot]
        p.remove_item(iid)
        if old:
            p.add_item(old)
        p.equipment[slot] = iid
        p.hp = min(p.hp, p.max_hp)
        say("You equip the {bwhite}%s{/}. {grey}%s{/}" % (ITEMS[iid]["name"], self.stat_text(iid)))
        if old:
            say("{grey}(%s goes back in your pack.){/}" % ITEMS[old]["name"])

    def cmd_unequip(self, noun):
        p = self.player
        m = self.resolve(noun, scopes=("equip",))
        if not m:
            say("{grey}You aren't wearing that.{/}")
            return
        iid = m[0][1]
        slot = ITEMS[iid]["kind"]
        if slot == "weapon":
            say("{grey}You'd be mad to walk out there unarmed.{/}")
            return
        p.equipment[slot] = None
        p.add_item(iid)
        p.hp = min(p.hp, p.max_hp)
        say("You take off the %s." % ITEMS[iid]["name"])

    def cmd_use(self, noun):
        p = self.player
        if not noun:
            say("Use what?")
            return
        m = self.resolve(noun, scopes=("inv",))
        if not m:
            say("{grey}You don't have that.{/}")
            return
        pick = self.choose_one(m, "Use which")
        if not pick:
            return
        iid = pick[1]
        it = ITEMS[iid]
        if it["kind"] in ("weapon", "armor", "trinket"):
            return self.cmd_equip(noun)
        if it["kind"] == "page":
            return self.read_page(iid)
        if iid == "tide_key" and self.room_id == "chapel_steps":
            return self.move("n")
        if it["kind"] != "consumable":
            say("{grey}You can't think how to use that here.{/}")
            return
        use = it["use"]
        if use.get("firepot") or use.get("smoke") or (use.get("focus") and len(use) == 1):
            say("{grey}Save that for a fight.{/}")
            return
        calms = use.get("dread", 0) < 0 and p.dread > 0              # a hot meal at full health still settles a frightened heart
        if "heal" in use and p.hp >= p.max_hp and "oil" not in use and not use.get("cleanse") and not calms:
            say("{grey}You're already at full health.{/}")
            return
        if "oil" in use and p.oil >= p.max_oil and "heal" not in use:
            say("{grey}Your lantern is already full.{/}")
            return
        p.remove_item(iid)
        if "heal" in use:
            say("{bgreen}You use the %s. (+%d health){/}" % (it["name"], p.heal(int(use["heal"] * p.mult("heal")))))
        if "oil" in use:
            say("{amber}You pour it into your lantern. The flame stands up taller. (+%d oil){/}" % p.add_oil(use["oil"]))
        if use.get("cleanse"):
            say("{bone}Your head clears.{/}")
        if use.get("dread"):
            p.dread = max(0, p.dread + use["dread"])
            say("{sky}You feel calmer. (Dread %d){/}" % p.dread)

    def cmd_examine(self, noun):
        if not noun:
            return
        if noun in ("me", "self", "myself"):
            return self.cmd_stats("")
        if noun in ("lantern", "lamp"):
            return self.cmd_lantern("")
        if self.benighted():
            say("{night}You can't see anything in this dark.{/}")
            return
        m = self.resolve(noun)
        if m:
            pick = self.choose_one(m, "Examine which")
            if not pick:
                return
            kind, iid = pick
            if kind == "npc":
                say(npcs.NPCS[iid]["desc"])
                return
            it = ITEMS[iid]
            say("%s  {grey}%s{/}" % (rarity.label(iid), self.stat_text(iid)))
            say("{grey}Rarity:{/} " + rarity.describe(iid))
            say(it["desc"])
            if it["kind"] == "page" and kind != "room":
                say("{grey}(Type 'read' to read it.){/}")
            return
        for keys, text in self.room.get("features", {}).items():
            for k in keys.split("|"):
                if noun == k or noun in k.split() or k.startswith(noun):
                    say(text)
                    events.on_examine(self, self.room_id, k)
                    return
        say("{grey}You see nothing special about that.{/}")

    def cmd_read(self, noun):
        p = self.player
        pages = [pid for pid in PAGES if p.has_item(pid)]
        if not noun or noun in ("page", "pages", "journal"):
            if not pages:
                say("{grey}You have nothing to read.{/}")
                return
            if len(pages) == 1:
                return self.read_page(pages[0])
            return self.cmd_pages("")
        numerals = {"1": "page1", "i": "page1", "2": "page2", "ii": "page2", "3": "page3", "iii": "page3",
                    "4": "page4", "iv": "page4", "5": "page5", "v": "page5", "6": "page6", "vi": "page6"}
        key = noun.replace("page", "").strip()
        if key in numerals:
            pid = numerals[key]
            if p.has_item(pid):
                return self.read_page(pid)
            say("{grey}You haven't found that page yet.{/}")
            return
        m = self.resolve(noun, scopes=("inv", "room"))
        if m:
            iid = m[0][1]
            if ITEMS[iid]["kind"] == "page":
                if m[0][0] == "room":
                    self._take(iid)
                return self.read_page(iid)
        self.cmd_examine(noun)

    def read_page(self, pid):
        title, text = PAGES[pid]["title"], PAGES[pid]["text"]
        blank()
        ui.rule("Orrin's Journal: %s" % title, color="bone")
        narrate("{bone}%s{/}" % text)
        self.flags["read_" + pid] = True

    def cmd_pages(self, noun):
        p = self.player
        pages = [pid for pid in PAGES if p.has_item(pid)]
        if not pages:
            say("{grey}You haven't found any journal pages yet.{/}")
            return
        labels = ["%s: %s%s" % (ITEMS[pid]["name"], PAGES[pid]["title"],
                                "" if self.flags.get("read_" + pid) else " {gold}(unread){/}") for pid in pages]
        say("{grey}Pages found: %d/6{/}" % len(pages))
        i = ui.menu(labels, prompt="Read")
        if i is not None:
            self.read_page(pages[i])

    # ---------------------------------------------------------------- people
    def cmd_talk(self, noun):
        here = self.present_npcs()
        if not here:
            say("{grey}There is no one here to talk to. You talk to your lantern a bit. It doesn't answer.{/}")
            return
        if not noun:
            if len(here) == 1:
                return npcs.talk(self, here[0])
            noun = ""
        m = self.resolve(noun, scopes=("npc",)) if noun else [("npc", n) for n in here]
        if not m:
            say("{grey}There is no '%s' here.{/}" % noun)
            return
        pick = self.choose_one(m, "Talk to whom")
        if pick:
            npcs.talk(self, pick[1])

    def cmd_trade(self, noun):
        for n in self.present_npcs():
            if npcs.NPCS[n].get("shop"):
                return npcs.trade(self, n)
        say("{grey}There is no one here to trade with.{/}")

    # ---------------------------------------------------------------- lantern & rest
    def cmd_lantern(self, noun):
        p = self.player
        blank()
        ui.rule("YOUR LANTERN")
        say("Oil  %s {amber}%d/%d{/}" % (ui.bar(p.oil, p.max_oil, 20), p.oil, p.max_oil))
        say("Burns {amber}%d{/} oil for each step into the dark.   Flare costs {amber}%d{/} oil, sears for ~{byellow}%d{/} "
            "(double against Hollows)." % (p.move_cost, p.flare_cost, p.flare_power))
        ups = []
        if p.lantern.get("shroud"):
            ups.append("Brass Shroud (+30 capacity, burns slower)")
        if p.lantern.get("lens"):
            ups.append("Polished Lens (stronger, cheaper flares)")
        if p.lantern.get("trim"):
            ups.append("Corvin's wick-trim (cheaper flares)")
        say("Fittings: %s" % (", ".join(ups) if ups else "{grey}none{/}"))
        flasks = p.inventory.get("oil", 0)
        tallow = p.inventory.get("tallow", 0)
        say("Spare oil: %d flask%s, %d tallow. {grey}('use oil' to refill){/}" % (flasks, "" if flasks == 1 else "s", tallow))
        if self.benighted():
            say("{bred}It is out. You are benighted.{/}")

    def safe_here(self):
        r = self.room
        return (r.get("rest") or (r.get("waypost") and self.flags.get("lit_" + self.room_id))
                or self.flags.get("beacon_" + r["region"]))

    def cmd_rest(self, noun):
        p = self.player
        if not self.safe_here():
            if self.is_dark():
                say("{grey}You can't rest in the dark. Find a lit waypost, or somewhere safe.{/}")
            else:
                say("{grey}This isn't a place to sleep. The Lamplighters' Hall is.{/}")
            return
        p.hp = p.max_hp
        p.calm()
        filled = p.add_oil(p.max_oil)
        self.last_rest = self.room_id
        self.add_anchor()
        p.relic_charges = p.relic_max_charges
        self.cooldown = {}
        narrate("{amber}You rest a while in the light. Your wounds close and your lantern is refilled%s.{/}" % (
            " (+%d oil)" % filled if filled else ""))
        events.on_rest(self)
        self.save(quiet=True)
        say("{grey}(Game saved.){/}")

    def cmd_light(self, noun):
        r = self.room
        p = self.player
        if r.get("beacon"):
            return self.light_beacon()
        if not r.get("waypost"):
            say("{grey}There's nothing here that needs lighting.{/}")
            return
        if self.flags.get("lit_" + self.room_id):
            say("{grey}The waypost is already burning.{/}")
            return
        if p.oil < 10:
            say("{grey}You need at least 10 oil to light the waypost.{/}")
            return
        p.oil -= 10
        self.flags["lit_" + self.room_id] = True
        self.add_anchor()
        narrate(r.get("waypost_text") or
                "{amber}You open the waypost's little door, trim the old wick, and touch your flame to it. "
                "It catches. The light spreads in a warm circle and the dark draws back to the treeline.{/}")
        say("{grey}(A lit waypost is safe: no ambushes here, and you can 'rest' to heal and refill.){/}")
        if self.room_id not in WOOD_WAYPOSTS:
            return
        if self.quest("wayposts") == -1:
            self.set_quest("wayposts", 0)
        lit = sum(1 for x in WOOD_WAYPOSTS if self.flags.get("lit_" + x))
        if lit == 3:
            narrate("{gold}Far off through the trees you see the other wayposts burning too, a line of small "
                    "steady lights all the way back to Hollowmere. The Tollroad is lit.{/}")
            self.set_quest("wayposts", "done")
            self.award_xp(40)
        else:
            say("{gold}Wayposts lit: %d/3{/}" % lit)

    def light_beacon(self):
        """Relight a region's beacon (after its boss is gone). Every room of the region becomes lit and safe."""
        r, p = self.room, self.player
        region = r["region"]
        if self.flags.get("beacon_" + region):
            say("{grey}The beacon is already burning.{/}")
            return
        if not self.flags.get(r.get("boss", "")):
            say("{grey}You cannot light it yet. %s still holds the room.{/}" % r.get("boss_name", "Something"))
            return
        cost = r.get("beacon_oil", 25)
        if p.oil < cost:
            say("{grey}It takes %d oil to start a beacon this big. You have %d.{/}" % (cost, p.oil))
            return
        p.oil -= cost
        self.flags["beacon_" + region] = True
        for rid, room in ROOMS.items():
            if room["region"] == region:
                self.flags["lit_" + rid] = True
        self.add_anchor()
        self.last_rest = self.room_id
        narrate(r.get("beacon_text") or
                "{amber}You pour the oil into the great iron bowl and touch your flame to it. For a moment nothing "
                "happens. Then the bowl catches, and the light climbs, and every window in the house turns gold at once.{/}")
        events.after_beacon(self, region)
        self.award_xp(120)

    def cmd_bounty(self, noun):
        if self.room_id != "square":
            say("{grey}The bounty board is in Hollowmere Square.{/}")
            return
        n = self.flags.get("bounty_unclaimed", 0)
        if n <= 0:
            say("{grey}You have no Hollow kills to claim. The board waits.{/}")
            return
        pay = n * 3
        self.player.gold += pay
        total = self.flags.get("bounty_total", 0) + n
        self.flags["bounty_total"] = total
        self.flags["bounty_unclaimed"] = 0
        say("{gold}You tally %d Hollows on the board and take %d gold from the council's box.{/}" % (n, pay))
        rewards = [(10, "tonic", "A note pinned to the box: 'For the lamplighter. Keep going.'"),
                   (25, "firepot", "Brann has left a firepot in the box, wrapped in a rag that says THANKS."),
                   (50, "moth_charm", "The schoolteacher has left you a folded paper moth. For luck."),
                   (80, "strong_draught", "Ilse has left a strong draught. 'You are in our prayers.'")]
        for need, iid, text in rewards:
            key = "bounty_reward_%d" % need
            if total >= need and not self.flags.get(key):
                self.flags[key] = True
                say(text)
                self.give(iid)
        say("{grey}Hollows put down in total: %d{/}" % total)

    # ---------------------------------------------------------------- character
    def cmd_stats(self, noun):
        p = self.player
        blank()
        ui.rule("%s the %s" % (p.name, p.cls_name), color=CLASSES[p.cls]["color"])
        col = ui.hp_color(p.hp, p.max_hp)
        say("Level {gold}%d{/}   XP %s %d/%d   {gold}%d gold{/}   %s" % (
            p.level, ui.bar(p.xp, p.xp_next, 12, full="gold"), p.xp, p.xp_next, p.gold,
            "{bgreen}%d points to spend ('train'){/}" % p.points if p.points else ""))
        say("Health %s {%s}%d/%d{/}   Oil %s {amber}%d/%d{/}" % (
            ui.bar(p.hp, p.max_hp, 12, full=col), col, p.hp, p.max_hp, ui.bar(p.oil, p.max_oil, 12), p.oil, p.max_oil))
        say("Dread %s {%s}%d %s{/}%s   {sky}%d gems{/}   Homecoming Charm %d/%d" % (
            ui.bar(p.dread, 100, 12, full="flame"), DREAD_COLOUR[p.dread_tier], p.dread, p.dread_tier,
            " {grey}(Shaken){/}" if p.shaken else "", p.gems, p.relic_charges, p.relic_max_charges))
        blank()
        say("{b}STR{/} %-3d {grey}physical damage{/}      {b}Attack{/} %d    {b}Defense{/} %d" % (p.STR, p.attack, p.defense))
        say("{b}WIL{/} %-3d {grey}fire and flare power{/}  {b}Spell{/}  %d    {b}Flare{/}   %d" % (p.WIL, p.spell, p.flare_power))
        say("{b}AGI{/} %-3d {grey}crits and dodging{/}     {b}Crit{/}   %d%%   {b}Dodge{/}   %d%%" % (p.AGI, p.crit, p.dodge))
        say("{b}VIT{/} %-3d {grey}health and toughness{/}" % p.vit)
        blank()
        say("{grey}Difficulty: %s.  Hollows slain: %d.  Deaths: %d.{/}" % (
            self.diff_name, self.stats.get("kills", 0), self.stats.get("deaths", 0)))

    def cmd_skills(self, noun):
        p = self.player
        blank()
        ui.rule("SKILLS")
        for s in CLASSES[p.cls]["skills"]:
            d = SKILLS[s]
            if d["level"] <= p.level:
                say("{bgreen}%s{/} {grey}(%d focus){/} - %s" % (d["name"], d["cost"], d["desc"]))
            else:
                say("{grey}%s (unlocks at level %d){/}" % (d["name"], d["level"]))
        blank()
        say("{grey}Every class can also: Attack, Guard (halve damage, +2 focus), Flare (burn oil to sear all "
            "enemies), and use Items.{/}")

    def cmd_train(self, noun):
        p = self.player
        if p.points <= 0:
            if noun is not None and noun != "":
                pass
            say("{grey}You have no points to spend. You earn 2 each level.{/}")
            return
        while p.points > 0:
            say("{gold}%d point%s to spend.{/}" % (p.points, "" if p.points == 1 else "s"))
            opts = ["STR %d -> %d {grey}(physical damage){/}" % (p.str, p.str + 1),
                    "WIL %d -> %d {grey}(fire skills, flare power){/}" % (p.wil, p.wil + 1),
                    "AGI %d -> %d {grey}(crit, dodge){/}" % (p.agi, p.agi + 1),
                    "VIT %d -> %d {grey}(+5 health, toughness){/}" % (p.vit, p.vit + 1)]
            i = ui.menu(opts, prompt="Train", cancel_label="Save points for later")
            if i is None:
                return
            stat = ["str", "wil", "agi", "vit"][i]
            setattr(p, stat, getattr(p, stat) + 1)
            p.points -= 1
            if stat == "vit":
                p.hp += 5
            say("{bgreen}%s increased.{/}" % stat.upper())

    # ---------------------------------------------------------------- journal & map
    def cmd_journal(self, noun):
        blank()
        ui.rule("JOURNAL")
        active, done = [], []
        order = ["main", "wren", "wayposts", "petals", "starsteel", "corvin", "bounty", "late_lending"]
        for qid in order:
            if qid not in self.quests:
                continue
            st = self.quests[qid]
            q = QUESTS[qid]
            text = q["stages"].get(st, "")
            if callable(text):
                text = text(self)
            (done if st == "done" else active).append((q, text))
        if not active and not done:
            say("{grey}Nothing yet.{/}")
        for q, text in active:
            mark = "{amber}◆{/}" if q.get("main") else "{gold}◇{/}"
            say("%s {b}%s{/}" % (mark, q["name"]))
            say("   " + text, indent=2)
        if done:
            blank()
            for q, text in done:
                say("{grey}✓ %s{/}" % q["name"])
        pages = sum(1 for p in PAGES if self.player.has_item(p))
        blank()
        say("{grey}Journal pages found: %d/6 ('pages' to read them){/}" % pages)

    def cmd_hint(self, noun):
        ui.rule("HINT", color="gold")
        for line in navigation.hint_lines(self):
            say(line.strip(), indent=4 if line.startswith("  ") else 2)

    def cmd_travel(self, noun):
        noun = noun.strip()
        if not noun:
            targets = navigation.travel_targets(self)
            if not targets:
                say("{grey}You do not know anywhere to travel to yet. Explore first.{/}")
                return
            targets = targets[:20]
            labels = ["%s {grey}- %s, %d step%s{/}" % (ROOMS[rid]["name"], ROOMS[rid]["region"], len(path),
                                                      "" if len(path) == 1 else "s") for rid, path in targets]
            ui.rule("TRAVEL", color="gold")
            say("{grey}Nearest known places. You can also type: travel <name>, or travel objective.{/}")
            idx = ui.menu(labels, prompt="Travel to", cancel_label="Stay here")
            if idx is None:
                return
            rid, path = targets[idx]
        else:
            matches = [m for m in navigation.match_place(self, noun) if m != self.room_id]
            if not matches:
                if navigation.match_place(self, noun):
                    say("{grey}You are already there.{/}")
                else:
                    say("{grey}You do not know a place called '%s'. Type 'travel' to see where you can go.{/}" % noun)
                return
            if len(matches) > 1:
                ui.rule("TRAVEL", color="gold")
                idx = ui.menu(["%s {grey}- %s{/}" % (ROOMS[m]["name"], ROOMS[m]["region"]) for m in matches],
                              prompt="Which one", cancel_label="Stay here")
                if idx is None:
                    return
                rid = matches[idx]
            else:
                rid = matches[0]
            objective = noun.lower() in ("objective", "goal", "main")
            path = navigation.find_path(self, self.room_id, rid, known_only=not objective)
            if not path:
                say("{grey}You cannot see a way to %s from here (it may be locked, or you have not found the route).{/}"
                    % ROOMS[rid]["name"])
                return
        self.walk(path)

    def walk(self, path):
        """Follow a route one step at a time, stopping if anything happens."""
        p = self.player
        dark = sum(1 for _, rid in path if self.is_dark(rid))
        need = dark * p.move_cost
        if dark and need >= p.oil:
            say("{ember}This trip needs about %d oil in the dark and you have %d.{/}" % (need, p.oil))
            if not ui.confirm("Go anyway?"):
                return
        dest = path[-1][1]
        say("{grey}Travelling to %s (%d step%s): %s{/}" % (ROOMS[dest]["name"], len(path), "" if len(path) == 1 else "s",
                                                           navigation.route_text(path)))
        for d, rid in path:
            if d not in self.room["exits"]:
                break
            self.interrupted = False
            self.move(d)
            if self.over:
                return
            if self.interrupted or self.room_id != rid or ui.io.pending:
                say("{ember}You stop in %s.{/}" % self.room["name"])
                return
        say("{bgreen}You arrive at %s.{/}" % self.room["name"])

    def cmd_map(self, noun):
        noun = noun.strip().lower()
        if noun in ("world", "all", "w", "overview"):
            ui.rule("THE WORLD", color="gold")
            for line in maps.render_world(self):
                say(line, wrap=False)
            say("{grey}'map' shows the region you are in. 'map <region>' shows another.{/}")
            return
        region = self.room["region"]
        if noun:
            hits = [r for r in REGIONS if noun in r.lower() or r.lower().startswith(noun)]
            if not hits:
                say("{grey}No region called '%s'. Regions: %s. Or 'map world'.{/}" % (noun, ", ".join(REGIONS)))
                return
            region = hits[0]
        lines, legend = maps.render_region(self, region)
        if lines is None:
            say("{grey}You have not explored %s yet.{/}" % region)
            return
        info = maps.REGION_INFO[region]
        seen, total, beaten, bosses = maps.region_summary(self, region)
        ui.rule("MAP: %s" % region, color="gold")
        say("{grey}%s · levels %s · explored %d/%d%s{/}" % (
            "home" if info["ring"] == 0 else "ring %d" % info["ring"], info["levels"], seen, total,
            " · bosses %d/%d" % (beaten, bosses) if bosses else ""))
        blank()
        for line in lines:
            say(line, wrap=False)
        blank()
        for line in legend:
            say(line)
        blank()
        say("{grey}map world · map <region> · travel (walk to a known place) · hint (what to do next){/}")

    # ---------------------------------------------------------------- system
    def cmd_settings(self, noun):
        player = self.player if self is not None else None
        while True:
            opts = ["Typewriter text: %s" % ("on" if ui.settings.typewriter else "off"),
                    "Colour: %s" % ("on" if ui.settings.color else "off"),
                    "Text speed: %s" % {0.006: "fast", 0.012: "normal", 0.022: "slow"}.get(ui.settings.speed, "custom")]
            if player is not None:
                opts.append("Dread: %s" % ("affects play" if player.dread_effects else "cosmetic only (no effects)"))
            i = ui.menu(opts, prompt="Settings")
            if i is None:
                return
            if i == 0:
                ui.settings.typewriter = not ui.settings.typewriter
            elif i == 1:
                ui.settings.color = not ui.settings.color
            elif i == 2:
                cycle = [0.006, 0.012, 0.022]
                cur = cycle.index(ui.settings.speed) if ui.settings.speed in cycle else 1
                ui.settings.speed = cycle[(cur + 1) % 3]
            else:
                player.dread_effects = not player.dread_effects

    # ---------------------------------------------------------------- the town: rent, stash, relic, codes
    def add_anchor(self):
        """Remember a safe place in the field, so the Homecoming Charm can bring you back to it."""
        if REGION_INFO[self.room["region"]]["ring"] > 0 and self.room_id not in self.anchors:
            self.anchors.append(self.room_id)

    def cmd_spells(self, noun):
        magic_ui.equip_menu(self)

    def cmd_forge(self, noun):
        if self.room_id not in ("smithy", "ember_smithy"):
            say("{grey}The forge is Brann's, in the forge east of Candle Lane.{/}")
            return
        forge_ui.menu(self)

    def cmd_town(self, noun):
        ui.rule("HOLLOWMERE", color="gold")
        for line in town.summary_lines(self):
            say(line)
        due = town.rent_due(self)
        blank()
        say("Rent: {gold}%d gold{/} waiting {grey}(%d an hour, up to %d hours; collect at home or the Builder's Yard){/}" % (
            due, town.rent_rate(self), town.RENT_CAP_HOURS))
        say("Stash: %d/%d {grey}(at home){/}" % (town.stash_used(self), town.stash_capacity(self)))

    def cmd_collect(self, noun):
        if self.room_id not in ("home", "yard"):
            say("{grey}Rent is counted out at your home or in the Builder's Yard.{/}")
            return
        if not town.rent_rate(self):
            say("{grey}No one pays you rent yet. Ask survivors to move to Hollowmere and ask Joss to build for them.{/}")
            return
        got = town.collect_rent(self)
        say("{gold}You collect %d gold in rent.{/}" % got if got else "{grey}Nothing has built up yet.{/}")

    def cmd_stash(self, noun):
        p = self.player
        if self.room_id != "home":
            say("{grey}Your stash is the chest at home (west of the Guild Hall).{/}")
            return
        while True:
            ui.rule("YOUR STASH", color="gold")
            say("{grey}%d of %d spaces used. Nothing stored here can be lost.{/}" % (town.stash_used(self), town.stash_capacity(self)))
            for iid, n in sorted(p.stash.items(), key=lambda x: ITEMS[x[0]]["name"]):
                say("  %s x%d" % (rarity.label(iid), n))
            blank()
            i = ui.menu(["Put things in", "Take things out"], prompt="Stash", cancel_label="Done")
            if i is None:
                return
            if i == 0:
                keep = [iid for iid in p.inventory if ITEMS[iid]["kind"] not in ("key", "page")]
                src, dst = p.inventory, p.stash
            else:
                keep = list(p.stash)
                src, dst = p.stash, p.inventory
            if not keep:
                say("{grey}There is nothing to move.{/}")
                continue
            j = ui.menu(["%s x%d" % (rarity.label(iid), src[iid]) for iid in keep], prompt="Which")
            if j is None:
                continue
            iid = keep[j]
            qty = src[iid]
            if qty > 1:
                raw = ui.ask("How many? (Enter = all %d) > " % qty)
                if raw.isdigit() and 1 <= int(raw) <= qty:
                    qty = int(raw)
            if i == 0:
                room_left = town.stash_capacity(self) - town.stash_used(self)
                if room_left <= 0:
                    say("{grey}The chest is full. Dagna can enlarge it once she has a Strongroom.{/}")
                    continue
                qty = min(qty, room_left)
            src[iid] -= qty
            if src[iid] <= 0:
                del src[iid]
            dst[iid] = dst.get(iid, 0) + qty
            say("{bgreen}%s %d x %s.{/}" % ("Stored" if i == 0 else "Took", qty, ITEMS[iid]["name"]))

    def _teleport(self, rid, text):
        p = self.player
        narrate(text)
        self.room_id = rid
        self.visited.add(rid)
        self.interrupted = True
        if REGION_INFO[ROOMS[rid]["region"]]["ring"] == 0:
            p.calm()

    def _charm_ready(self):
        p = self.player
        if not p.has_item("homecoming_charm"):
            say("{grey}You do not have a Homecoming Charm. Orrin gives you one when you first speak to him.{/}")
            return False
        if p.relic_charges <= 0:
            say("{grey}The charm is cold. It needs a night's rest to catch its breath. (Rest at a safe place to recharge it.){/}")
            return False
        return True

    def cmd_recall(self, noun):
        if REGION_INFO[self.room["region"]]["ring"] == 0:
            say("{grey}You are already in Hollowmere.{/}")
            return
        if not self._charm_ready():
            return
        self.player.relic_charges -= 1
        self._teleport("square", "{amber}You close your hand around the brass moth and think of home. The dark folds up "
                                 "like a page, and you are standing in the square, under the lamps.{/}")
        say("{grey}(Charm uses left: %d/%d. Resting recharges it. 'return' takes you back to where you rested.){/}" % (
            self.player.relic_charges, self.player.relic_max_charges))

    def cmd_return(self, noun):
        if REGION_INFO[self.room["region"]]["ring"] != 0:
            say("{grey}You can only 'return' from Hollowmere. Use 'recall' to come home first.{/}")
            return
        if not self.anchors:
            say("{grey}You have no place to return to yet. Rest, or relight a waypost, somewhere out in the dark first.{/}")
            return
        if not self._charm_ready():
            return
        if len(self.anchors) == 1:
            rid = self.anchors[0]
        else:
            i = ui.menu(["%s {grey}- %s{/}" % (ROOMS[a]["name"], ROOMS[a]["region"]) for a in self.anchors],
                        prompt="Return to", cancel_label="Stay home")
            if i is None:
                return
            rid = self.anchors[i]
        self.player.relic_charges -= 1
        self._teleport(rid, "{amber}You hold the brass moth and think of the last warm place you slept. The square "
                            "dims, and the warmth of the waypost is around you again.{/}")
        say("{grey}(Charm uses left: %d/%d.){/}" % (self.player.relic_charges, self.player.relic_max_charges))

    def cmd_redeem(self, noun):
        if not noun:
            say("{grey}Type 'redeem' followed by a code, for example: redeem NEW{/}")
            return
        ok, message = codes.redeem(self, noun)
        say(("{sky}%s{/}" if ok else "{grey}%s{/}") % message)

    def finish_story(self):
        """After an ending the world stays open: you wake at home, the Wizard's Shop opens, and play continues."""
        p = self.player
        self.flags["completed"] = True
        self.flags["endings_seen"] = sorted(set(self.flags.get("endings_seen", [])) | {self.flags.get("ending", "")} - {""})
        self.room_id = "square"
        self.visited.add("square")
        p.hp = p.max_hp
        p.statuses = {}
        p.calm()
        p.relic_charges = p.relic_max_charges
        self.notice("{gold}The story is told, and the world remains.{/} The door north of the Guild Hall is open: "
                    "the Wizard's Shop.")

    def cmd_update(self, noun):
        if ui.io.in_combat:
            say("{grey}You cannot update in the middle of a fight.{/}")
            return
        update.run_command(noun, say, ui.confirm)

    def cmd_quit(self, noun):
        if ui.confirm("Quit the game? Unsaved progress since your last rest will be lost. Save first?"):
            self.save()
        raise QuitGame()

    def cmd_save(self, noun):
        self.save()

    def cmd_load(self, noun):
        if not save.exists():
            say("{grey}There is no saved game.{/}")
            return
        if ui.confirm("Load your saved game? Current progress since then will be lost."):
            try:
                g = Game.load()
            except save.SaveError as e:
                say("{bred}%s{/}" % e)
                if isinstance(e, save.SaveDamaged):
                    say("{grey}Your current game is untouched. To try your previous save, quit and choose Continue.{/}")
                return
            note = g.load_note
            self.__dict__.update(g.__dict__)
            self.notice("{bgreen}Game loaded.{/}")
            if note:
                self.notice("{grey}%s{/}" % note)

    # ---------------------------------------------------------------- save/load
    def to_dict(self):
        return {
            "player": self.player.to_dict(), "room": self.room_id, "flags": self.flags,
            "quests": self.quests, "visited": sorted(self.visited), "room_items": self.room_items,
            "stats": self.stats, "moves": self.moves, "last_rest": self.last_rest,
            "difficulty": self.difficulty, "diff_name": self.diff_name,
            "game_version": VERSION, "town": self.town, "forge": self.forge, "dealers": self.dealers, "anchors": self.anchors,
            "settings": {"typewriter": ui.settings.typewriter, "speed": ui.settings.speed},
        }

    def save(self, quiet=False, slot="main"):
        try:
            save.write(self.to_dict(), slot)
            if not quiet:
                say("{bgreen}Game saved.{/}")
        except OSError as e:
            say("{bred}Could not save: %s{/}" % e)

    @classmethod
    def load(cls, slot="main", keep_copy=True):
        """Read a save. g.load_note says (in one line) if the save had to be upgraded and where the original is kept."""
        d, note = save.read_info(slot, keep_copy)
        try:
            dropped = savecheck.check(d)
            g = cls.from_dict(d)
        except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError, RecursionError) as e:
            raise save.SaveDamaged("This save has data the game cannot use (%s: %s)." % (type(e).__name__, e))
        if dropped:
            note = (note + " " if note else "") + savecheck.left_out_line(dropped, slot, keep_copy)
        g.load_note = note
        return g

    @classmethod
    def from_dict(cls, d):
        g = cls()
        g.player = Player.from_dict(d["player"])
        g.player.lantern.setdefault("trim", False)
        g.room_id = d["room"]
        g.flags = d["flags"]
        g.quests = dict(d["quests"])
        g.visited = set(d["visited"])
        g.room_items = d["room_items"]
        for rid in ROOMS:
            g.room_items.setdefault(rid, list(ROOMS[rid].get("items", [])))   # rooms added since the save get their loot
        g.stats = d["stats"]
        g.moves = d["moves"]
        g.last_rest = d["last_rest"]
        g.difficulty = d["difficulty"]
        g.diff_name = d["diff_name"]
        g.town = d.get("town") or town.new_state()
        g.forge = d.get("forge") or forge.new_state()
        g.dealers = dealer.load_state(d.get("dealers"))
        if g.quest("main") not in (-1, 0) and not g.player.has_item("homecoming_charm"):
            g.player.add_item("homecoming_charm")   # a save from before the charm existed
        g.anchors = list(d.get("anchors", []))
        s = d.get("settings", {})
        ui.settings.typewriter = s.get("typewriter", ui.settings.typewriter)
        ui.settings.speed = s.get("speed", ui.settings.speed)
        return g
