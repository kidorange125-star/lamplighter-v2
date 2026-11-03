"""Turn-based combat with telegraphed enemy intents.

Round order: player acts -> each enemy carries out the intent it showed ->
enemies pick (and show) their next intent. Damage-over-time ticks at the start
of the owner's turn; durations count down at the end of it.
"""
from . import elements, rarity, spells, ui
from .ui import say, blank
from .content import CLASSES, ENEMIES, ITEMS, SKILLS, SPELLS, SPELL_RULES
from .entities import DREAD_COLOUR, Enemy

# ---- tunables (set by simulation, see tools/sim_fights.py)
FLARE_COOLDOWN = 2      # player turns between flares: 2 means "not on two turns in a row"
BLIND_MISS = 0.30       # chance a blinded creature's attack misses

ICONS = {
    "attack": ("⚔", "bred"), "heavy": ("‼", "blood"), "defend": ("⛨", "sky"),
    "heal": ("✚", "bgreen"), "buff": ("▲", "byellow"), "debuff": ("▼", "hollow"),
    "summon": ("✦", "magenta"), "drain": ("☾", "night"), "shroud": ("◐", "hollow"),
    "charge": ("…", "gold"),
}


class Action:
    """One thing the player does on their turn. Built by the menu for a person, or by a policy for a bot."""
    __slots__ = ("kind", "skill", "item", "target")

    def __init__(self, kind, skill=None, item=None, target=None):
        self.kind = kind          # attack | guard | flare | skill | item | flee
        self.skill = skill        # skill id, for kind == "skill"
        self.item = item          # item id, for kind == "item"
        self.target = target      # an Enemy, when the action needs one

    def __repr__(self):
        return "Action(%s)" % ", ".join(str(x) for x in (self.kind, self.skill, self.item) if x)


class Combat:
    def __init__(self, game, enemy_ids, ambush=False, on_phase=None, intro=None, no_flee=False, policy=None):
        self.policy = policy      # callable(combat) -> Action; when set the fight runs with no UI at all
        self.silent = policy is not None
        self.practice = all("practice" in ENEMIES[eid].get("tags", []) for eid in enemy_ids)
        self.spell_cd = {}        # book id -> rounds until it can be cast again
        self.last_flare_round = -9
        self.shadow_target = None
        self.g = game
        self.p = game.player
        self.rng = game.rng
        self.enemies = [Enemy(eid, ENEMIES[eid]) for eid in enemy_ids]
        self._dedupe_names()
        self.ambush = ambush
        self.on_phase = on_phase
        self.intro = intro
        self.no_flee = no_flee or any((e.boss and "roll" not in e.t) or "elite" in e.tags for e in self.enemies)
        self.round = 0
        self.guarding = False
        self.xp = 0
        self.gold = 0
        self.loot = []
        self.log = []

    # ------------------------------------------------------------------ helpers
    def _dedupe_names(self):
        by_id = {}
        for e in self.enemies:
            by_id.setdefault(e.id, []).append(e)
        for eid, group in by_id.items():
            if len(group) > 1:
                for i, e in enumerate(group):
                    e.name = "%s %s" % (ENEMIES[eid]["name"], "ABCDEFGHIJ"[i % 10])

    @property
    def alive(self):
        return [e for e in self.enemies if not e.dead]

    def benighted(self):
        return self.g.benighted()

    def msg(self, text):
        say(text)

    # ------------------------------------------------------------------ main loop
    def run(self):
        ui.io.in_combat = True
        try:
            return self._run()
        finally:
            ui.io.in_combat = False

    def _run(self):
        p = self.p
        p.statuses = {}
        p.shield = 0
        p.focus = 4
        if ui.io.since_clear > 0 and not self.silent:
            # let the player read whatever led up to the fight before the battle screen takes over
            ui.pause("(press Enter to fight)")
        self.last_log = ""
        ui.io.start_capture()
        if self.intro:
            say(self.intro)
        if not self.silent and not self.g.flags.get("tip_combat"):
            self.g.flags["tip_combat"] = True
            say("{sky}Tip:{/} each enemy shows what it will do next. Press {gold}Enter{/} to take the {gold}★ suggested{/} "
                "move, or use the keys shown. Type {gold}help{/} in a fight to learn the symbols.")
        for e in self.enemies:
            say("{bred}%s{/} {grey}- %s{/}" % (e.name, e.t.get("desc", "")))
        self.announce_field()
        self.shift_stances(announce=False)
        if self.benighted():
            say("{night}Your lantern is dry. In the dark you cannot read their movements, "
                "and the Hollows grow bolder.{/}")
        for e in self.enemies:
            e.choose_intent(self.rng, self.enemies)
            self._prepare_intent(e)
        if any("boss" in e.tags for e in self.enemies) and not self.practice:
            self.g.add_dread(5, in_combat=True)
        elif any("elite" in e.tags for e in self.enemies) and not self.practice:
            self.g.add_dread(3, in_combat=True)
        if self.ambush:
            say("{bred}Ambush!{/} They are on you before you can raise your lantern.")
            self.enemy_phase()
            if p.dead:
                return self.finish("dead")
            self.next_intents()
        while True:
            self.round += 1
            self.shift_stances()
            outcome = self.player_phase()
            if outcome:
                return self.finish(outcome)
            if not self.alive:
                return self.finish("win")
            self.enemy_phase()
            if p.dead:
                return self.finish("dead")
            if not self.alive:
                return self.finish("win")
            self.next_intents()

    def announce_field(self):
        """Name the room's damage field when a fight begins; its flavour line is told only the first time."""
        f = self.g.room.get("field")
        if not f:
            return
        parts = ["%s x%g" % (elements.INFO[k]["name"], v) for k, v in f.items() if k in elements.INFO]
        say("{sky}Field:{/} %s {grey}(%s){/}" % (f.get("name", "Field"), ", ".join(parts)))
        key = "field_seen_%s" % self.g.room_id
        if f.get("msg") and not self.g.flags.get(key):
            self.g.flags[key] = True
            say("{grey}%s{/}" % f["msg"])

    def shift_stances(self, announce=True):
        """Put every living attuned enemy into the stance for the current round, telling the player of a change."""
        for e in self.alive:
            if e.attune and e.set_stance(self.round) and announce:
                st = e.attune["stances"][e.stance]
                say(st["msg"] if st.get("msg") else "{hollow}%s shifts: %s.{/}" % (e.name, st["name"]))

    def next_intents(self):
        for e in self.alive:
            e.turn += 1
            forced = getattr(e, "forced", None)
            if forced:
                e.intent = e.t["extra_moves"][forced]
                e.forced = None
            else:
                e.choose_intent(self.rng, self.enemies)
            self._prepare_intent(e)

    def _prepare_intent(self, e):
        e.guarding = e.intent.get("kind") == "defend"

    # ------------------------------------------------------------------ rendering
    def render(self):
        """A fresh screen each round: what just happened, then the state of the fight."""
        log = ui.io.take_capture()
        if log.strip():
            self.last_log = log
        ui.clear()
        ui.rule("BATTLE {grey}·{/} %s" % self.g.room["name"], color="blood")
        if self.last_log.strip():
            ui.io.write(self.last_log.strip("\n") + "\n")
        blank()
        ui.rule("Round %d" % self.round, color="blood", char="┄")
        dark = self.benighted()
        for i, e in enumerate(self.alive, 1):
            col = ui.hp_color(e.hp, e.max_hp)
            name = ("{grey}%d{/} " % i if len(self.alive) > 1 else "") + "{bred}%s{/}" % e.name
            say("%s  %s {%s}%d/%d{/}  %s" % (
                name, ui.bar(e.hp, e.max_hp, 16, full=col), col, e.hp, e.max_hp, e.status_line()))
            if e.weak or e.resist:
                say("   {grey}weak to{/} %s%s" % (elements.tags(e.weak) or "{grey}nothing{/}",
                                                   ("  {grey}resists{/} " + elements.tags(e.resist)) if e.resist else ""))
            if e.attune:
                n = e.rounds_to_shift(self.round)
                say("   {grey}stance: %s, next: %s in %d round%s{/}" % (
                    e.attune["stances"][e.stance]["name"],
                    e.attune["stances"][(e.stance + 1) % len(e.attune["stances"])]["name"], n, "" if n == 1 else "s"))
            if not self.sees(e):
                say("   {grey}next: ??? (%s){/}" % ("too dark to see" if dark else "dread clouds your mind"))
            else:
                icon, icol = ICONS.get(e.intent["kind"], ("?", "grey"))
                label = e.intent["name"]
                detail = self._intent_detail(e)
                say("   {grey}next:{/} {%s}%s %s{/}{grey} - %s %s%s{/}" % (
                    icol, icon, label, e.name.split(",")[0], e.intent.get("tell", ""), detail))
        p = self.p
        col = ui.hp_color(p.hp, p.max_hp)
        focus = "{sky}%s{/}{grey}%s{/}" % ("●" * p.focus, "○" * (10 - p.focus))
        say("")
        dread = ""
        if p.dread >= 25 or p.hollowing:
            dread = "  {%s}Dread %d %s{/}" % (DREAD_COLOUR[p.dread_tier], p.dread, p.dread_tier)
        say("{b}%s{/}  HP %s {%s}%d/%d{/}  Focus %s  {amber}Oil %d{/}%s  %s" % (
            p.name, ui.bar(p.hp, p.max_hp, 14, full=col), col, p.hp, p.max_hp, focus, p.oil, dread,
            p.status_line()))
        ui.io.start_capture()

    def _intent_detail(self, e):
        m = e.intent
        k = m["kind"]
        if k in ("attack", "heavy", "drain"):
            est = int(e.atk * m.get("power", 1) * m.get("hits", 1) * self._enemy_mult(e))
            est = max(1, est - int(self.p.defense * 0.6))
            hits = " x%d" % m["hits"] if m.get("hits", 1) > 1 else ""
            return " {/}{bred}(~%d dmg%s){/}{grey}" % (est, hits)
        return ""

    # ------------------------------------------------------------------ player
    def player_phase(self):
        p = self.p
        self.guarding = False
        self.dread_tick()
        # start-of-turn effects
        self.tick_dots(p, is_player=True)
        if p.dead:
            return "dead"
        if p.regen:
            healed = p.heal(p.regen)
            if healed:
                say("{bgreen}The Saint's Tooth knits your wounds (+%d).{/}" % healed)
        self._king_lifeline()
        if p.has("stun"):
            p.remove("stun")
            if not self.silent:
                self.render()
            say("{byellow}You are stunned and lose your turn!{/}")
            p.tick_end()
            return None
        while True:
            if not self.silent:
                self.render()
            action = self.decide()
            if p.hollowing and action and self.rng.random() < 0.25:
                action = Action("attack", target=self.rng.choice(self.alive))
                say("{bmagenta}The dread takes over. You lash out!{/}")
            result = self.execute(action) if action else False
            if self.silent and result is False:
                result = self.execute(Action("attack"))  # a bot must always spend its turn
            if result == "fled":
                return "fled"
            if result is not False:
                break
        self.check_deaths()
        p.tick_end()
        gain = 2 + (2 if self.guarding else 0)
        p.focus = min(10, p.focus + gain)
        for book in list(self.spell_cd):
            self.spell_cd[book] -= 1
            if self.spell_cd[book] <= 0:
                del self.spell_cd[book]
        if p.hollowing:
            p.hollowing -= 1
            if p.hollowing == 0:
                self.collapse()
        return None

    def dread_tick(self):
        g, p = self.g, self.p
        if self.practice or p.hollowing:
            return
        if g.is_dark():
            g.add_dread(2 if g.benighted() else 1, in_combat=True)
        if p.dread >= 100 and p.dread_effects:
            p.hollowing = 3
            say("{bmagenta}{b}Dread floods you. You are Consumed.{/}{/} {grey}For 3 rounds you hit far harder, "
                "and sometimes you strike wildly.{/}")

    def collapse(self):
        p = self.p
        p.dread = 60
        p.shaken = True
        say("{bmagenta}The dread drains out of you and leaves you shaking. (Shaken: -20%% damage until you rest.){/}")

    def sees(self, e):
        """Can the player read this enemy's next move? Darkness and terror hide the moves of ordinary enemies."""
        if self.benighted():
            return False
        p = self.p
        if p.dread_effects and p.dread_tier in ("Terrified", "Consumed") and "boss" not in e.tags and "elite" not in e.tags:
            return False
        return True

    def _king_lifeline(self):
        # never let the final fight soft-lock: the Well itself feeds the lantern
        king = next((e for e in self.alive if "king" in e.tags), None)
        if king and king.has("shroud") and self.p.oil < self.p.flare_cost and not self.p.has_item("oil") \
                and not self.p.has_item("tallow"):
            self.p.add_oil(self.p.flare_cost)
            say("{amber}The Lightwell stirs beneath your feet. A thread of fire climbs into your lantern. "
                "(+%d oil){/}" % self.p.flare_cost)

    # ------------------------------------------------------------------ deciding what to do
    def decide(self):
        if self.policy:
            return self.policy(self)
        with ui.held():
            return self._decide_ui()

    def flare_ready(self):
        p = self.p
        return p.oil >= p.flare_cost and self.round - self.last_flare_round >= FLARE_COOLDOWN

    def skill_ready(self, sid):
        d = SKILLS[sid]
        return sid in self.p.skills and self.p.focus >= d["cost"]

    def estimate(self, e):
        """Rough damage the enemy's shown move does to the player, for the on-screen hint."""
        m = e.intent
        if m["kind"] not in ("attack", "heavy", "drain"):
            return 0
        est = int(e.atk * m.get("power", 1) * m.get("hits", 1) * self._enemy_mult(e))
        return max(1, est - int(self.p.defense * 0.6))

    def best_target(self):
        """Healers first, then whoever is closest to dying."""
        alive = self.alive
        healers = [e for e in alive if e.intent and e.intent["kind"] == "heal"]
        pool = healers or alive
        return min(pool, key=lambda e: e.hp)

    def suggest(self):
        """The move the game recommends right now, as (Action, reason). Also the default bot policy."""
        p = self.p
        alive = self.alive
        dark = self.benighted()
        target = self.best_target()

        if p.hp < p.max_hp * 0.32:
            for iid in ("strong_draught", "draught", "honeycake", "stew"):
                if p.inventory.get(iid):
                    return Action("item", item=iid), "You are badly hurt. Drink a %s." % ITEMS[iid]["name"]

        if not dark:
            heavy = [e for e in alive if self.sees(e) and e.intent["kind"] == "heavy" and not e.has("stun")]
            if heavy:
                big = max(heavy, key=self.estimate)
                if self.estimate(big) >= p.hp * 0.25 or big.boss:
                    why = "%s is about to use %s (~%d damage)." % (big.name.split(",")[0], big.intent["name"], self.estimate(big))
                    if p.cls == "wayfarer" and self.skill_ready("shadowstep") and not p.has("shadow"):
                        return Action("skill", skill="shadowstep"), why + " Dodge it."
                    if p.cls == "warden":
                        if self.skill_ready("bash"):
                            return Action("skill", skill="bash", target=big), why + " Try to stun it."
                        if self.skill_ready("bulwark"):
                            return Action("skill", skill="bulwark"), why + " Brace."
                    if p.cls == "ashblade" and self.skill_ready("cinder_wall"):
                        return Action("skill", skill="cinder_wall"), why + " Put up a wall."
                    return Action("guard"), why + " Guard to halve it."

        shrouded = [e for e in alive if e.has("shroud")]
        healing = [e for e in alive if e.has("regen") and not e.has("burn")]
        if shrouded or healing:
            why = ("%s is wrapped in shadow. Only light can reach him." % shrouded[0].name if shrouded else
                   "%s heals every turn unless he is burning. Burn him." % healing[0].name.split(",")[0])
            if self.flare_ready():
                return Action("flare"), why
            if healing and p.inventory.get("firepot"):
                return Action("item", item="firepot"), why
            if healing and self.skill_ready("ember_strike"):
                return Action("skill", skill="ember_strike", target=healing[0]), why
            if p.oil < p.flare_cost:
                for iid in ("oil", "tallow"):
                    if p.inventory.get(iid):
                        return Action("item", item=iid), "Your lantern is too low for a flare. Refill it."
        if self.flare_ready():
            lit = [e for e in alive if e.hollow and not e.has("blind")]
            if len(lit) >= 2 or (lit and (lit[0].boss or lit[0].max_hp >= 60) and p.oil >= p.flare_cost + 25):
                return Action("flare"), "Hollows take double from a flare, and it blinds them."

        if target.hp < target.max_hp * 0.35:
            for sid in ("coup", "judgement"):
                if self.skill_ready(sid) and (sid == "coup" or target.has("stun") or target.has("weak")):
                    return Action("skill", skill=sid, target=target), "%s is nearly finished." % target.name.split(",")[0]

        cast = self.best_spell(alive)
        if cast:
            return cast
        if p.cls == "wayfarer":
            if self.skill_ready("hamstring") and not target.has("weak") and target.max_hp >= 60:
                return Action("skill", skill="hamstring", target=target), "Weaken it and make it bleed."
            if self.skill_ready("twin_cut"):
                return Action("skill", skill="twin_cut", target=target), "Two quick cuts, each may cause bleeding."
        elif p.cls == "warden":
            if self.skill_ready("judgement") and (target.has("stun") or target.has("weak")):
                return Action("skill", skill="judgement", target=target), "It is open. Hit it hard."
            if self.skill_ready("bash") and p.focus >= 5:
                return Action("skill", skill="bash", target=target), "A solid hit that may stun."
        elif p.cls == "ashblade":
            if len(alive) >= 2 and self.skill_ready("immolate"):
                return Action("skill", skill="immolate"), "Burn them all."
            fresh = [e for e in alive if not e.has("burn")]
            if self.skill_ready("ember_strike") and fresh:
                return Action("skill", skill="ember_strike", target=fresh[0]), "Set it alight."
        return Action("attack", target=target), "Nothing special is needed. Strike."

    def element_mult(self, element, e):
        if element == "all":
            return 1.0
        if element in e.weak:
            return SPELL_RULES["weak_mult"]
        if element in e.resist:
            return SPELL_RULES["resist_mult"]
        return 1.0

    def field_mult(self, element):
        """What the room's damage field does to a spell of this element (1.0 for none, all, or an unnamed one)."""
        return self.g.room.get("field", {}).get(element, 1.0) if element != "all" else 1.0

    def best_spell(self, alive):
        """The spell worth casting right now, as (Action, reason), or None. Never suggests into a resistance.
        The room's field only changes the ranking: a spell it dims can still beat having no spell at all."""
        best = None
        for book in self.p.spells:
            if not self.spell_ready(book):
                continue
            sp = SPELLS[spells.spell_id(book)]
            if sp["target"] == "all":
                if len(alive) < 2 and sp["element"] != "all":
                    continue
                m = sum(self.element_mult(sp["element"], e) for e in alive) / len(alive)
                score = sp["power"] * spells.power_mult(book) * m * self.field_mult(sp["element"]) * (len(alive) ** 0.5)
                tgt = None
            else:
                tgt = max(alive, key=lambda e: (self.element_mult(sp["element"], e), -e.hp))
                m = self.element_mult(sp["element"], tgt)
                score = sp["power"] * spells.power_mult(book) * m * self.field_mult(sp["element"])
            if m < 1.0:
                continue
            if best is None or score > best[0]:
                best = (score, book, tgt, m, sp)
        if not best:
            return None
        _, book, tgt, m, sp = best
        why = ("%s is weak to %s. Cast %s." % (tgt.name.split(",")[0], elements.INFO[sp["element"]]["name"], sp["name"])
               if m > 1.0 and tgt else "Cast %s." % sp["name"])
        return Action("spell", item=book, target=tgt), why

    def action_label(self, a):
        if a.kind == "skill":
            slot = CLASSES[self.p.cls]["skills"].index(a.skill) + 1
            return "[%d] %s" % (slot, SKILLS[a.skill]["name"])
        if a.kind == "item":
            return "[I] %s" % ITEMS[a.item]["name"]
        if a.kind == "spell":
            return "[S%d] %s" % (self.p.spells.index(a.item) + 1, SPELLS[spells.spell_id(a.item)]["name"])
        return {"attack": "[A] Attack", "guard": "[G] Guard", "flare": "[F] Flare", "flee": "[R] Flee"}[a.kind]

    def _decide_ui(self):
        p = self.p
        sug, reason = self.suggest()
        say("")
        say("{gold}★ Suggested:{/} {b}%s{/}  {grey}%s{/}" % (self.action_label(sug), reason))
        flare = "{gold}[F]{/} Flare {grey}%d oil{/}" % p.flare_cost
        if p.oil < p.flare_cost:
            flare = "{grey}[F] Flare (not enough oil){/}"
        elif not self.flare_ready():
            flare = "{grey}[F] Flare (recharging){/}"
        acts = ["{gold}[A]{/} Attack", "{gold}[G]{/} Guard", flare, "{gold}[I]{/} Items"]
        if not self.no_flee:
            acts.append("{gold}[R]{/} Flee")
        say("Actions   " + "    ".join(acts), wrap=False)
        slots = []
        for i, sid in enumerate(CLASSES[p.cls]["skills"], 1):
            d = SKILLS[sid]
            if d["level"] > p.level:
                slots.append("{grey}[%d] %s (level %d){/}" % (i, d["name"], d["level"]))
            elif p.focus < d["cost"]:
                slots.append("{grey}[%d] %s %d{/}" % (i, d["name"], d["cost"]))
            else:
                slots.append("{gold}[%d]{/} %s {grey}%d{/}" % (i, d["name"], d["cost"]))
        say("Skills    " + "    ".join(slots) + "   {grey}(cost in focus){/}", wrap=False)
        spell_names = {}
        if p.spells:
            row = []
            for i, book in enumerate(p.spells, 1):
                sp = SPELLS[spells.spell_id(book)]
                col = elements.INFO[sp["element"]]["colour"]
                shown = "%s%s" % (sp["name"], (" " + rarity.INFO[spells.rarity_of(book)]["symbol"]).rstrip())
                spell_names["s%d" % i] = book
                spell_names[sp["name"].lower()] = book
                if self.spell_cd.get(book, 0) > 0:
                    row.append("{grey}[S%d] %s (back in %d){/}" % (i, shown, self.spell_cd[book]))
                elif p.focus < sp["focus"]:
                    row.append("{grey}[S%d] %s %d{/}" % (i, shown, sp["focus"]))
                else:
                    row.append("{gold}[S%d]{/} {%s}%s{/} {grey}%d{/}" % (i, col, shown, sp["focus"]))
            say("Spells    " + "    ".join(row), wrap=False)
        say("{grey}Enter = take the suggestion · add a target number like '1 2' · 'help' explains the symbols{/}")
        names = {}
        for i, sid in enumerate(CLASSES[p.cls]["skills"], 1):
            names[str(i)] = sid
            names[SKILLS[sid]["name"].lower()] = sid
            names[sid] = sid
            names[sid.replace("_", " ")] = sid
        while True:
            raw = ui.ask("action > ").lower().strip()
            if not raw:
                return sug
            if raw in ("help", "?", "h"):
                self.combat_help()
                continue
            if raw in ("quit", "exit"):
                if ui.confirm("Quit the game? Progress since your last save will be lost."):
                    from .engine import QuitGame
                    raise QuitGame()
                continue
            words = raw.split()
            num = int(words[-1]) if len(words) > 1 and words[-1].isdigit() else None
            head = " ".join(words[:-1]) if num is not None else raw
            if head in names:
                sid = names[head]
                d = SKILLS[sid]
                if d["level"] > p.level:
                    say("{grey}%s unlocks at level %d.{/}" % (d["name"], d["level"]))
                    continue
                if p.focus < d["cost"]:
                    say("{grey}Not enough focus for %s (%d needed, you have %d).{/}" % (d["name"], d["cost"], p.focus))
                    continue
                target = None
                if d["target"] == "enemy":
                    target = self.pick_target(num, sug.target if sug.kind == "skill" and sug.skill == sid else None)
                    if target is None:
                        continue
                return Action("skill", skill=sid, target=target)
            if head in spell_names:
                book = spell_names[head]
                sp = SPELLS[spells.spell_id(book)]
                if p.focus < sp["focus"]:
                    say("{grey}Not enough focus for %s (%d needed, you have %d).{/}" % (sp["name"], sp["focus"], p.focus))
                    continue
                if self.spell_cd.get(book, 0) > 0:
                    say("{grey}%s is still recharging.{/}" % sp["name"])
                    continue
                target = None
                if sp["target"] == "enemy":
                    target = self.pick_target(num, sug.target if sug.kind == "spell" and sug.item == book else None)
                    if target is None:
                        continue
                return Action("spell", item=book, target=target)
            if head in ("a", "attack", "strike", "hit"):
                target = self.pick_target(num, sug.target if sug.kind == "attack" else None)
                if target is None:
                    continue
                return Action("attack", target=target)
            if head in ("g", "guard", "d", "defend", "block"):
                return Action("guard")
            if head in ("f", "flare", "light"):
                if p.oil < p.flare_cost:
                    say("{grey}Your lantern sputters. A flare needs %d oil.{/}" % p.flare_cost)
                    continue
                if not self.flare_ready():
                    say("{grey}The lantern needs a moment to recover. Flare again next turn.{/}")
                    continue
                return Action("flare")
            if head in ("i", "item", "items", "use"):
                iid = self.pick_item()
                if iid is None:
                    continue
                return Action("item", item=iid)
            if head in ("r", "run", "flee", "escape") and not self.no_flee:
                return Action("flee")
            say("{grey}Not an action. Use A, G, F, I%s, a skill number 1-4, or press Enter for the suggestion.{/}" %
                ("" if self.no_flee else ", R"))

    def combat_help(self):
        say("{amber}Reading a fight:{/} each enemy shows its {b}next move{/} before you act.")
        say("  {bred}⚔{/} attack   {blood}‼{/} heavy hit   {sky}⛨{/} defending (takes half damage)   "
            "{bgreen}✚{/} healing   {byellow}▲{/} buff")
        say("  {hollow}▼{/} curse   {magenta}✦{/} summon   {night}☾{/} drains oil   {gold}…{/} winding up a big move")
        say("{amber}Guard{/} halves the damage you take this round and gives +2 extra focus.")
        say("{amber}Focus{/} refills by 2 each turn (4 when you Guard) and pays for skills. Skill keys never move.")
        say("{amber}Flare{/} burns oil to sear every enemy. Hollows take double and are blinded. "
            "The lantern needs a turn to recover.")
        say("{amber}Stun{/} cancels whatever the enemy was about to do.")
        say("{amber}Spells{/} (keys S1, S2...) cost focus and need a few rounds to recharge. An enemy shows what it is "
            "{b}weak to{/} (spells hit 50%% harder) and what it {b}resists{/} (half as hard).")

    def pick_target(self, num=None, default=None):
        """Resolve which enemy an action hits. Returns None if the player backed out."""
        alive = self.alive
        if len(alive) == 1:
            return alive[0]
        if num is not None and 1 <= num <= len(alive):
            return alive[num - 1]
        default = default if default in alive else self.best_target()
        for i, e in enumerate(alive, 1):
            say("  {gold}[%d]{/} %s {grey}(%d/%d){/}" % (i, e.name, e.hp, e.max_hp), indent=4)
        while True:
            raw = ui.ask("target (Enter = %s, 0 = back) > " % default.name.split(",")[0]).strip()
            if not raw:
                return default
            if raw in ("0", "back", "b"):
                return None
            if raw.isdigit() and 1 <= int(raw) <= len(alive):
                return alive[int(raw) - 1]
            say("{grey}Pick a number from the list.{/}")

    def pick_item(self):
        p = self.p
        usable = [iid for iid in p.inventory if ITEMS[iid]["kind"] == "consumable"]
        if not usable:
            say("{grey}You have nothing useful to hand.{/}")
            return None
        labels = ["%s x%d {grey}- %s{/}" % (ITEMS[i]["name"], p.inventory[i], ITEMS[i]["desc"]) for i in usable]
        idx = ui.menu(labels, prompt="Use")
        return None if idx is None else usable[idx]

    # ------------------------------------------------------------------ doing it
    def execute(self, a):
        """Carry out an Action. Returns True (turn spent), False (nothing happened), or "fled"."""
        p = self.p
        if a.kind == "attack":
            t = a.target if a.target in self.alive else self.best_target()
            self.hit(t, p.attack, "phys", verb="strike")
            return True
        if a.kind == "guard":
            self.guarding = True
            say("{sky}You set your feet and raise your guard.{/}")
            return True
        if a.kind == "flare":
            return self.flare()
        if a.kind == "item":
            return self.exec_item(a.item)
        if a.kind == "skill":
            return self.exec_skill(a.skill, a.target)
        if a.kind == "spell":
            return self.exec_spell(a.item, a.target)
        if a.kind == "flee":
            if self.no_flee:
                say("{grey}There is no escaping this fight.{/}")
                return False
            chance = 0.45 + p.AGI * 0.02
            if self.rng.random() < chance:
                say("{grey}You break away and run, lantern swinging.{/}")
                return "fled"
            say("{bred}You try to run, but they cut you off!{/}")
            return True
        return False

    # ------------------------------------------------------------------ damage
    def wound(self, e, dmg):
        """Apply damage to an enemy. A blow that crosses a boss phase stops at it, so every phase is fought."""
        new = e.hp - dmg
        if e.phase < len(e.phases):
            floor = max(1, int(e.max_hp * e.phases[e.phase]["at"]))
            if e.hp > floor:
                new = max(new, floor)
        e.hp = max(0, new)
        self.check_phase(e)

    def _enemy_mult(self, e):
        m = 1.0
        if e.has("weak"):
            m *= 0.65
        if e.has("enraged"):
            m *= 1.3
        if self.benighted() and e.hollow:
            m *= 1.25
        return m * self.g.difficulty

    def hit(self, e, base, kind="phys", mult=1.0, verb="hit", can_crit=True, quiet=False, force_crit=False, spell=False):
        """Player damages enemy. kind: phys | an element | true. Returns damage dealt.

        Spells (spell=True) are also boosted by an enemy's weakness and cut by its resistance."""
        p = self.p
        if e.dead:
            return 0
        if e.has("shroud") and kind != "true":
            say("{hollow}Your %s passes through %s like smoke. Nothing is there to hurt.{/}" % (
                "blow" if kind == "phys" else "fire", e.name))
            return 0
        if kind == "phys":
            miss = e.dodge / 100.0
            if p.has("blind"):
                miss += 0.4
            if p.has("shadow"):
                miss = 0
            if self.rng.random() < miss:
                say("{grey}You %s at %s and miss.{/}" % (verb, e.name))
                return 0
        dmg = base * mult * self.rng.uniform(0.88, 1.12)
        crit = False
        if can_crit and kind == "phys":
            if force_crit or p.has("shadow") or self.rng.random() < p.crit / 100.0:
                crit = True
                dmg *= 1.75
                p.remove("shadow")
        if kind in ("fire", "light"):
            dmg *= e.t.get("fire", 1.0)
            if p.has("kindled"):
                dmg *= 1.4
        if kind == "light" and e.hollow:
            dmg *= 2
        if kind == "phys" and p.equipment.get("weapon") == "starsteel_blade" and e.hollow:
            dmg *= 1.2
        dmg *= p.mult(kind) * p.dread_damage_mult()
        if kind not in ("phys", "true"):
            dmg *= self.g.room.get("field", {}).get(kind, 1.0)
        note = ""
        if spell:
            dmg *= p.mult("spell")
            if kind in e.weak:
                dmg *= SPELL_RULES["weak_mult"]
                note = " {bgreen}(weak!){/}"
            elif kind in e.resist:
                dmg *= SPELL_RULES["resist_mult"]
                note = " {grey}(resisted){/}"
        if p.has("weak"):
            dmg *= 0.65
        if e.has("exposed"):
            dmg *= 1.3
        if e.guarding:
            dmg *= 0.5
        if kind == "phys":
            dmg -= e.defense * 0.6
        elif kind not in ("light", "true"):
            dmg -= e.defense * 0.3
        dmg = max(1, int(round(dmg)))
        self.g.stats["damage_dealt"] = self.g.stats.get("damage_dealt", 0) + dmg
        if not quiet:
            colour = elements.INFO[kind]["colour"] if kind in elements.INFO else "bwhite"
            say("You %s %s for {%s}{b}%d{/}{/}%s%s%s" % (
                verb, e.name, colour, dmg,
                " {gold}CRITICAL!{/}" if crit else "", note,
                " {grey}(guarded){/}" if e.guarding else ""))
        self.wound(e, dmg)
        return dmg

    def hurt_player(self, e, base, label):
        p = self.p
        if p.has("shadow") and e is self.shadow_target:
            say("{night}You melt into the shadows; %s's %s finds nothing.{/}" % (e.name, label))
            return 0
        miss = p.dodge / 100.0 + (BLIND_MISS if e.has("blind") else 0)
        if self.rng.random() < miss:
            say("{grey}You twist aside from %s's %s.{/}" % (e.name, label))
            return 0
        dmg = base * self.rng.uniform(0.88, 1.12) * self._enemy_mult(e)
        if p.has("exposed"):
            dmg *= 1.3
        dmg *= p.dread_taken_mult()
        if self.guarding:
            dmg *= 0.5
        braced = p.has("bulwark")
        if braced:
            dmg *= 0.4
        dmg -= p.defense * 0.6
        dmg = max(1, int(round(dmg)))
        absorbed = 0
        if p.shield > 0:
            absorbed = min(p.shield, dmg)
            p.shield -= absorbed
            dmg -= absorbed
        p.hp = max(0, p.hp - dmg)
        self.g.stats["damage_taken"] = self.g.stats.get("damage_taken", 0) + dmg
        extra = ""
        if absorbed:
            extra += " {ember}(cinder wall absorbs %d){/}" % absorbed
        if self.guarding or braced:
            extra += " {sky}(guarded){/}"
        say("%s's %s hits you for {bred}{b}%d{/}{/}.%s" % (e.name, label, dmg, extra))
        if braced and not e.dead:
            back = max(1, int(base * 0.35))
            say("{sky}Your braced shield bites back: %s takes %d.{/}" % (e.name, back))
            self.wound(e, back)
        if p.has("cinder") and not e.dead:
            e.apply("burn", 2, 3 + p.WIL // 3)
            say("{ember}%s is scorched by your cinder wall.{/}" % e.name)
        return dmg

    def tick_dots(self, who, is_player=False):
        for s in ("burn", "bleed", "poison"):
            if who.has(s) and not who.dead:
                if who.has("shroud"):
                    continue
                dmg = who.power_of(s)
                if is_player:
                    who.hp = max(0, who.hp - dmg)
                label = {"burn": "burns", "bleed": "bleeds", "poison": "chokes on brine"}[s]
                if is_player:
                    say("{%s}You %s for %d.{/}" % ({"burn": "flame", "bleed": "blood", "poison": "brine"}[s],
                                                   "burn" if s == "burn" else ("bleed" if s == "bleed" else "choke on brine"),
                                                   dmg))
                else:
                    say("{%s}%s %s for %d.{/}" % ({"burn": "flame", "bleed": "blood", "poison": "brine"}[s],
                                                  who.name, label, dmg))
                    self.wound(who, dmg)
        if who.has("regen") and not who.dead:
            if who.has("burn") and not is_player:
                say("{flame}The fire dries the brine. %s cannot heal while burning.{/}" % who.name)
            else:
                healed = min(who.power_of("regen"), who.max_hp - who.hp)
                if healed > 0:
                    who.hp += healed
                    say("{bgreen}%s %d.{/}" % ("You recover" if is_player else who.name + " recovers", healed))

    # ------------------------------------------------------------------ flare
    def flare(self):
        p = self.p
        if p.oil < p.flare_cost:
            say("{grey}Your lantern sputters. Not enough oil for a flare (%d needed).{/}" % p.flare_cost)
            return False
        if not self.flare_ready():
            say("{grey}The lantern needs a moment to recover.{/}")
            return False
        self.last_flare_round = self.round
        p.oil -= p.flare_cost
        ui.narrate("{byellow}You throw open the lantern's shutters. Light floods out, white and furious!{/}")
        for e in list(self.alive):
            had_shroud = e.has("shroud")
            if had_shroud:
                e.remove("shroud")
                e.apply("exposed", 2)
                say("{byellow}The shroud tears away from %s! It stands exposed in the light.{/}" % e.name)
            self.hit(e, p.flare_power, "light", verb="sear")
            if not e.dead and not e.has("shroud"):
                e.apply("burn", 2, 3)
                if e.hollow:
                    e.apply("blind", 2)
        p.remove("kindled")
        self.check_deaths()
        return True

    # ------------------------------------------------------------------ items
    def exec_item(self, iid):
        p = self.p
        if iid not in p.inventory or ITEMS[iid]["kind"] != "consumable":
            return False
        use = ITEMS[iid]["use"]
        if use.get("smoke"):
            if self.no_flee:
                say("{grey}There is no escaping this fight.{/}")
                return False
            p.remove_item(iid)
            say("{grey}You smash the pellet. Grey smoke fills the air and you slip away.{/}")
            return "fled"
        p.remove_item(iid)
        if "heal" in use:
            say("{bgreen}You drink the %s. (+%d health){/}" % (ITEMS[iid]["name"], p.heal(int(use["heal"] * p.mult("heal")))))
        if "oil" in use:
            say("{amber}You top up your lantern. (+%d oil){/}" % p.add_oil(use["oil"]))
        if "focus" in use:
            p.focus = min(10, p.focus + use["focus"])
            say("{sky}Your mind sharpens. (Focus %d){/}" % p.focus)
        if use.get("cleanse"):
            p.cleanse()
            say("{bone}Your head clears.{/}")
        if use.get("dread"):
            p.dread = max(0, p.dread + use["dread"])
            say("{sky}You feel calmer. (Dread %d){/}" % p.dread)
        if "regen" in use:
            p.apply("regen", 3, use["regen"], self_cast=True)
        if "firepot" in use:
            say("{flame}You hurl the firepot. It bursts in a sheet of flame!{/}")
            for e in list(self.alive):
                self.hit(e, use["firepot"] + p.WIL // 2, "fire", verb="scorch")
                e.apply("burn", 3, 4)
            self.check_deaths()
        return True

    def spell_ready(self, book):
        sp = SPELLS[spells.spell_id(book)]
        return book in self.p.spells and self.p.focus >= sp["focus"] and self.spell_cd.get(book, 0) <= 0

    def exec_spell(self, book, target=None):
        p = self.p
        if book not in p.spells:
            return False
        sp = SPELLS[spells.spell_id(book)]
        if p.focus < sp["focus"]:
            say("{grey}Not enough focus for %s.{/}" % sp["name"])
            return False
        if self.spell_cd.get(book, 0) > 0:
            say("{grey}%s is still recharging (%d more round%s).{/}" % (
                sp["name"], self.spell_cd[book], "" if self.spell_cd[book] == 1 else "s"))
            return False
        p.focus -= sp["focus"]
        self.spell_cd[book] = sp["cooldown"]
        mult = spells.power_mult(book)
        base = p.magic * sp["power"] * mult
        el = sp["element"]
        kind = "true" if el == "all" else el
        say("{%s}You cast %s!{/}" % (elements.INFO[el]["colour"], sp["name"]))
        if sp["target"] == "all":
            targets = list(self.alive)
        else:
            targets = [target if target in self.alive else self.best_target()]
        dealt = 0
        for e in targets:
            d = self.hit(e, base, kind=kind, spell=True, verb="blast")
            dealt += d
            if d and not e.dead and not e.has("shroud"):
                for fx in sp["effects"]:
                    if fx["type"] == "status":
                        power = int(fx.get("power", 0) * mult ** 0.5)
                        e.apply(fx["status"], fx["turns"], power)
                        if fx["status"] == "burn":
                            say("{flame}%s catches fire.{/}" % e.name)
                        elif fx["status"] == "weak":
                            say("{sky}%s is chilled and hits softer.{/}" % e.name)
                        elif fx["status"] == "blind":
                            say("{byellow}%s is blinded.{/}" % e.name)
        for fx in sp["effects"]:
            if fx["type"] == "drain" and dealt:
                got = p.heal(int(dealt * fx["fraction"]))
                if got:
                    say("{hollow}You draw %d health from it.{/}" % got)
            elif fx["type"] == "shield":
                p.shield += int(p.WIL * fx["per_wil"] * mult) + int(6 * mult)
                p.apply("ward", 2, self_cast=True)
                say("{moss}Rock closes around you. (shield %d){/}" % p.shield)
            elif fx["type"] == "cleanse_self":
                p.cleanse()
                say("{bblue}The water washes your ailments away.{/}")
        self.check_deaths()
        return True

    def exec_skill(self, sid, target=None):
        p = self.p
        if sid not in SKILLS or sid not in p.skills:
            return False
        d = SKILLS[sid]
        if p.focus < d["cost"]:
            say("{grey}Not enough focus.{/}")
            return False
        if d["target"] == "enemy" and target not in self.alive:
            target = self.best_target()
        p.focus -= d["cost"]
        getattr(self, "skill_" + sid)(target)
        self.check_deaths()
        return True

    def _fire_bonus_used(self):
        self.p.remove("kindled")

    # Warden
    def skill_bash(self, t):
        dmg = self.hit(t, self.p.attack, "phys", 1.1, verb="slam")
        if dmg and not t.dead:
            chance = 0.3 if t.boss else 0.45
            if self.rng.random() < chance:
                t.apply("stun", 1)
                say("{byellow}%s is stunned! Its next move is cancelled.{/}" % t.name)

    def skill_bulwark(self, t):
        self.p.apply("bulwark", 2, self_cast=True)
        say("{sky}You plant your shield. Let them come.{/}")

    def skill_rally(self, t):
        p = self.p
        healed = p.heal(int(p.max_hp * 0.3))
        p.cleanse()
        say("{bgreen}You grit your teeth and rally. (+%d health, ailments cleared){/}" % healed)

    def skill_judgement(self, t):
        mult = 1.15
        if t.has("stun") or t.has("weak"):
            mult *= 2.0 if t.boss else 2.5
            say("{gold}You see the opening.{/}")
        self.hit(t, self.p.attack, "phys", mult, verb="bring judgement down on")

    # Ashblade
    def skill_ember_strike(self, t):
        p = self.p
        dmg = self.hit(t, p.spell, "fire", 1.0, verb="sear")
        self._fire_bonus_used()
        if not t.dead and not t.has("shroud"):
            t.apply("burn", 3, 4 + p.WIL // 2)
            say("{flame}%s catches fire.{/}" % t.name)

    def skill_kindle(self, t):
        p = self.p
        p.apply("kindled", 4, self_cast=True)
        got = p.add_oil(12)
        say("{amber}You breathe on the wick. The flame leans toward your enemies. (+%d oil){/}" % got)

    def skill_cinder_wall(self, t):
        p = self.p
        p.shield = p.WIL * 3
        p.apply("cinder", 2, self_cast=True)
        say("{ember}Embers swirl up into a wall around you. (shield %d){/}" % p.shield)

    def skill_immolate(self, t):
        p = self.p
        say("{flame}You open your hands and the fire goes everywhere.{/}")
        for e in list(self.alive):
            bonus = 0
            if e.has("burn"):
                turns, power = e.statuses["burn"]
                bonus = turns * power
                e.remove("burn")
            self.hit(e, p.spell * 0.9 + bonus, "fire", verb="immolate")
            if not e.dead and not e.has("shroud"):
                e.apply("burn", 2, 4 + p.WIL // 2)
        self._fire_bonus_used()

    # Wayfarer
    def skill_twin_cut(self, t):
        p = self.p
        for _ in range(2):
            if t.dead:
                break
            dmg = self.hit(t, p.attack, "phys", 0.65, verb="cut")
            if dmg and not t.dead and self.rng.random() < 0.5:
                t.apply("bleed", 3, 3 + p.AGI // 3)
                say("{blood}%s is bleeding.{/}" % t.name)

    def skill_shadowstep(self, t):
        self.p.apply("shadow", 3, self_cast=True)
        say("{night}You step sideways into your own shadow.{/}")

    def skill_hamstring(self, t):
        p = self.p
        dmg = self.hit(t, p.attack, "phys", 0.8, verb="hamstring")
        if dmg and not t.dead:
            t.apply("bleed", 4, 4 + p.AGI // 2)
            t.apply("weak", 2)
            say("{blood}%s staggers, bleeding and weakened.{/}" % t.name)

    def skill_coup(self, t):
        mult = 1.2
        if t.hp < t.max_hp * 0.35:
            mult *= 2.5 if t.boss else 3.5
            say("{gold}You see the killing line.{/}")
        self.hit(t, self.p.attack, "phys", mult, verb="finish")

    # ------------------------------------------------------------------ enemies
    def enemy_phase(self):
        # Shadowstep dodges the single biggest attack this round, not whichever enemy happens to act first.
        self.shadow_target = None
        if self.p.has("shadow"):
            attackers = [e for e in self.alive if e.intent["kind"] in ("attack", "heavy", "drain") and not e.has("stun")]
            if attackers:
                self.shadow_target = max(attackers, key=self.estimate)
        for e in list(self.alive):
            if e.dead or self.p.dead:
                continue
            self.tick_dots(e)
            if e.dead:
                self.check_deaths()
                continue
            if e.has("stun"):
                e.remove("stun")
                if e.intent and e.intent.get("kind") == "charge":
                    e.forced = None
                say("{byellow}%s is stunned. Its %s never comes.{/}" % (e.name, e.intent["name"]))
                e.tick_end()
                continue
            self.act(e)
            if e is self.shadow_target:
                self.p.remove("shadow")
                self.shadow_target = None
            e.guarding = False
            e.tick_end()
            self.check_deaths()

    def act(self, e):
        m = e.intent
        k = m["kind"]
        p = self.p
        if k in ("attack", "heavy", "drain"):
            for _ in range(m.get("hits", 1)):
                if p.dead:
                    break
                label = m["name"] if k != "heavy" else "{blood}%s{/}" % m["name"].upper()
                dmg = self.hurt_player(e, e.atk * m.get("power", 1.0), label)
                if dmg and m.get("status"):
                    s, turns, power = m["status"]
                    p.apply(s, turns, power)
                    lbl = {"bleed": "You are bleeding.", "burn": "You are burning!", "poison": "Brine fills your lungs.",
                           "weak": "Your strength drains away.", "blind": "You are blinded!",
                           "exposed": "You are left exposed."}.get(s, "")
                    if lbl:
                        say("{grey}%s{/}" % lbl)
                if dmg and m.get("steal"):
                    took = min(p.gold, m["steal"])
                    p.gold -= took
                    if took:
                        say("{gold}%s snatches %d gold from your purse.{/}" % (e.name, took))
                if k == "drain":
                    lost = min(p.oil, m.get("drain", 10))
                    p.oil -= lost
                    say("{night}Your lantern gutters. (-%d oil){/}" % lost)
        elif k == "defend":
            say("{sky}%s holds its guard.{/}" % e.name)
        elif k == "heal":
            allies = [a for a in self.alive]
            target = min(allies, key=lambda a: a.hp / a.max_hp)
            amt = int(e.max_hp * m.get("power", 0.2))
            target.hp = min(target.max_hp, target.hp + amt)
            who = "itself" if target is e else target.name
            say("{bgreen}%s uses %s, healing %s for %d.{/}" % (e.name, m["name"], who, amt))
        elif k == "buff":
            s, turns, power = m["status"]
            targets = self.alive if m.get("allies") else [e]
            for a in targets:
                a.apply(s, turns + (1 if a is e else 0), power)
            if m.get("allies"):
                say("{byellow}%s uses %s. Its allies grow furious.{/}" % (e.name, m["name"]))
            else:
                say("{byellow}%s uses %s and grows furious.{/}" % (e.name, m["name"]))
        elif k == "debuff":
            s, turns, power = m["status"]
            if self.rng.random() < p.dodge / 200.0:
                say("{grey}%s uses %s, but you shake it off.{/}" % (e.name, m["name"]))
            else:
                p.apply(s, turns, power)
                say("{hollow}%s uses %s. You are %s.{/}" % (
                    e.name, m["name"], {"weak": "weakened", "blind": "blinded", "exposed": "exposed",
                                        "stun": "stunned"}.get(s, s)))
        elif k == "summon":
            if len(self.alive) < 3:
                new = Enemy(m["summon"], ENEMIES[m["summon"]])
                self.enemies.append(new)
                new.set_stance(self.round)
                self._dedupe_names()
                new.choose_intent(self.rng, self.enemies)
                self._prepare_intent(new)
                say("{magenta}%s uses %s. %s joins the fight!{/}" % (e.name, m["name"], new.name))
        elif k == "shroud":
            e.apply("shroud", 99)
            say("{hollow}%s pulls the darkness back around himself. Your blows will not land.{/}" % e.name)
        elif k == "charge":
            e.forced = m["then"]
            say("{gold}%s %s.{/}" % (e.name, m.get("tell", "winds up")))

    # ------------------------------------------------------------------ phases / deaths
    def check_phase(self, e):
        while e.phase < len(e.phases) and not e.dead and e.hp <= e.max_hp * e.phases[e.phase]["at"]:
            ph = e.phases[e.phase]
            e.phase += 1
            blank()
            ui.narrate("{bmagenta}%s{/}" % ph["msg"])
            e.moves = ph["moves"]
            for s in ph.get("clear", []):
                e.remove(s)
            if ph.get("status"):
                s, turns, power = ph["status"]
                e.apply(s, turns, power)
            e.choose_intent(self.rng, self.enemies)
            self._prepare_intent(e)
            if self.on_phase:
                self.on_phase(self, e, e.phase)

    def check_deaths(self):
        for e in self.enemies:
            if e.dead and not getattr(e, "counted", False):
                e.counted = True
                say("{gold}%s falls.{/}" % e.name)
                self.xp += e.t.get("xp", 0)
                lo, hi = e.t.get("gold", (0, 0))
                self.gold += self.rng.randint(lo, hi)
                for iid, chance in e.t.get("drops", []):
                    if self.rng.random() < chance:
                        self.loot.append(iid)
                self.g.on_kill(e)
                # the choir grieves
                if "choir" in e.tags:
                    for a in self.alive:
                        if "choir" in a.tags:
                            a.apply("enraged", 3)
                            say("{byellow}%s sings louder, grieving. (enraged){/}" % a.name)

    def finish(self, outcome):
        p = self.p
        p.statuses = {}
        p.shield = 0
        if p.hollowing:
            p.hollowing = 0
            p.dread, p.shaken = 60, True
        ui.io.take_capture()
        blank()
        if all("practice" in e.tags for e in self.enemies):
            ui.rule("PRACTICE OVER", color="grey")
            say("{grey}Nothing was won or lost.{/}")
            return outcome
        if outcome == "win":
            ui.rule("VICTORY", color="gold")
            self.g.stats["battles"] = self.g.stats.get("battles", 0) + 1
            p.gold += self.gold
            say("{gold}+%d xp   +%d gold{/}" % (self.xp, self.gold))
            for iid in self.loot:
                p.add_item(iid)
                say("{bone}You take: %s{/}" % ITEMS[iid]["name"])
            levels = p.gain_xp(self.xp)
            if levels and not self.silent:
                self.g.level_up_ceremony(levels)
        elif outcome == "fled":
            ui.rule(color="grey")
        return outcome
