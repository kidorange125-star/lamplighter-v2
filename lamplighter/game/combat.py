"""Turn-based combat with telegraphed enemy intents.

Round order: player acts -> each enemy carries out the intent it showed ->
enemies pick (and show) their next intent. Damage-over-time ticks at the start
of the owner's turn; durations count down at the end of it.
"""
from . import ui
from .ui import say, blank
from .data.classes import SKILLS
from .data.enemies import ENEMIES
from .data.items import ITEMS
from .entities import Enemy

ICONS = {
    "attack": ("⚔", "bred"), "heavy": ("‼", "blood"), "defend": ("⛨", "sky"),
    "heal": ("✚", "bgreen"), "buff": ("▲", "byellow"), "debuff": ("▼", "hollow"),
    "summon": ("✦", "magenta"), "drain": ("☾", "night"), "shroud": ("◐", "hollow"),
    "charge": ("…", "gold"),
}


class Combat:
    def __init__(self, game, enemy_ids, ambush=False, on_phase=None, intro=None, no_flee=False):
        self.g = game
        self.p = game.player
        self.rng = game.rng
        self.enemies = [Enemy(eid, ENEMIES[eid]) for eid in enemy_ids]
        self._dedupe_names()
        self.ambush = ambush
        self.on_phase = on_phase
        self.intro = intro
        self.no_flee = no_flee or any(e.boss or "elite" in e.tags for e in self.enemies)
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
        if ui.io.since_clear > 0:
            # let the player read whatever led up to the fight before the battle screen takes over
            ui.pause("(press Enter to fight)")
        self.last_log = ""
        ui.io.start_capture()
        if self.intro:
            say(self.intro)
        for e in self.enemies:
            say("{bred}%s{/} {grey}- %s{/}" % (e.name, e.t.get("desc", "")))
        if self.benighted():
            say("{night}Your lantern is dry. In the dark you cannot read their movements, "
                "and the Hollows grow bolder.{/}")
        for e in self.enemies:
            e.choose_intent(self.rng, self.enemies)
            self._prepare_intent(e)
        if self.ambush:
            say("{bred}Ambush!{/} They are on you before you can raise your lantern.")
            self.enemy_phase()
            if p.dead:
                return self.finish("dead")
            self.next_intents()
        while True:
            self.round += 1
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
            name = "{bred}%s{/}" % e.name
            say("%s  %s {%s}%d/%d{/}  %s" % (
                name, ui.bar(e.hp, e.max_hp, 16, full=col), col, e.hp, e.max_hp, e.status_line()))
            if dark:
                say("   {grey}next: ??? (too dark to see){/}")
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
        say("{b}%s{/}  HP %s {%s}%d/%d{/}  Focus %s  {amber}Oil %d{/}  %s" % (
            p.name, ui.bar(p.hp, p.max_hp, 14, full=col), col, p.hp, p.max_hp, focus, p.oil,
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
            self.render()
            say("{byellow}You are stunned and lose your turn!{/}")
            p.tick_end()
            return None
        while True:
            self.render()
            choice = self.choose_action()
            result = self.do_action(choice)
            if result == "fled":
                return "fled"
            if result is not False:
                break
        self.check_deaths()
        p.tick_end()
        gain = 2 + (2 if self.guarding else 0)
        p.focus = min(10, p.focus + gain)
        return None

    def _king_lifeline(self):
        # never let the final fight soft-lock: the Well itself feeds the lantern
        king = next((e for e in self.alive if "king" in e.tags), None)
        if king and king.has("shroud") and self.p.oil < self.p.flare_cost and not self.p.has_item("oil") \
                and not self.p.has_item("tallow"):
            self.p.add_oil(self.p.flare_cost)
            say("{amber}The Lightwell stirs beneath your feet. A thread of fire climbs into your lantern. "
                "(+%d oil){/}" % self.p.flare_cost)

    def choose_action(self):
        with ui.held():
            return self._choose_action()

    def _choose_action(self):
        p = self.p
        opts = [
            ("attack", "Attack"),
            ("skill", "Skills {grey}(%d focus){/}" % p.focus),
            ("guard", "Guard"),
            ("flare", "Flare {grey}(%d oil){/}" % p.flare_cost),
            ("item", "Items"),
        ]
        if not self.no_flee:
            opts.append(("flee", "Flee"))
        line = "  ".join("{gold}[%d]{/} %s" % (i, label) for i, (_, label) in enumerate(opts, 1))
        say(line)
        keys = {"a": "attack", "attack": "attack", "s": "skill", "skill": "skill", "skills": "skill",
                "g": "guard", "guard": "guard", "d": "guard", "defend": "guard", "f": "flare", "flare": "flare",
                "i": "item", "item": "item", "items": "item", "r": "flee", "run": "flee", "flee": "flee"}
        while True:
            raw = ui.ask("action > ").lower()
            if raw.isdigit() and 1 <= int(raw) <= len(opts):
                return opts[int(raw) - 1][0]
            first = raw.split(" ")[0] if raw else ""
            if first in keys and (keys[first] != "flee" or not self.no_flee):
                return keys[first]
            if raw in ("help", "?", "h"):
                self.combat_help()
                continue
            if raw in ("quit", "exit"):
                if ui.confirm("Quit the game? Progress since your last save will be lost."):
                    from .engine import QuitGame
                    raise QuitGame()
                continue
            say("{grey}Choose 1-%d (or attack / skill / guard / flare / item%s, or 'help').{/}" % (
                len(opts), "" if self.no_flee else " / flee"))

    def combat_help(self):
        say("{amber}Reading a fight:{/} each enemy shows its {b}next move{/} before you act.")
        say("  {bred}⚔{/} attack   {blood}‼{/} heavy hit (Guard, stun, or kill it first)   "
            "{sky}⛨{/} defending (takes half damage now)")
        say("  {bgreen}✚{/} healing   {byellow}▲{/} buff   {hollow}▼{/} curse   {magenta}✦{/} summon   "
            "{night}☾{/} drains oil   {gold}…{/} winding up")
        say("{amber}Guard{/} halves the damage you take this round and gives +2 extra focus.")
        say("{amber}Focus{/} refills by 2 each turn (4 when you Guard) and pays for skills.")
        say("{amber}Flare{/} burns lantern oil to sear and scorch every enemy. Hollows take double and are blinded.")
        say("{amber}Stun{/} cancels whatever the enemy was about to do.")

    def pick_target(self):
        alive = self.alive
        if len(alive) == 1:
            return alive[0]
        labels = ["%s {grey}(%d/%d){/}" % (e.name, e.hp, e.max_hp) for e in alive]
        i = ui.menu(labels, prompt="Target")
        return None if i is None else alive[i]

    def do_action(self, choice):
        """Returns False if the action was cancelled (no turn spent)."""
        p = self.p
        if choice == "attack":
            t = self.pick_target()
            if not t:
                return False
            self.hit(t, p.attack, "phys", verb="strike")
            return True
        if choice == "guard":
            self.guarding = True
            say("{sky}You set your feet and raise your guard.{/}")
            return True
        if choice == "flare":
            return self.flare()
        if choice == "item":
            return self.use_item()
        if choice == "skill":
            return self.use_skill()
        if choice == "flee":
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

    def hit(self, e, base, kind="phys", mult=1.0, verb="hit", can_crit=True, quiet=False, force_crit=False):
        """Player damages enemy. kind: phys | fire | light | true. Returns damage dealt."""
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
        if p.has("weak"):
            dmg *= 0.65
        if e.has("exposed"):
            dmg *= 1.3
        if e.guarding:
            dmg *= 0.5
        if kind == "phys":
            dmg -= e.defense * 0.6
        elif kind == "fire":
            dmg -= e.defense * 0.3
        dmg = max(1, int(round(dmg)))
        self.g.stats["damage_dealt"] = self.g.stats.get("damage_dealt", 0) + dmg
        if not quiet:
            colour = {"phys": "bwhite", "fire": "flame", "light": "byellow", "true": "bwhite"}[kind]
            say("You %s %s for {%s}{b}%d{/}{/}%s%s" % (
                verb, e.name, colour, dmg,
                " {gold}CRITICAL!{/}" if crit else "",
                " {grey}(guarded){/}" if e.guarding else ""))
        self.wound(e, dmg)
        return dmg

    def hurt_player(self, e, base, label):
        p = self.p
        if p.has("shadow"):
            p.remove("shadow")
            say("{night}You melt into the shadows; %s's %s finds nothing.{/}" % (e.name, label))
            return 0
        miss = p.dodge / 100.0 + (0.4 if e.has("blind") else 0)
        if self.rng.random() < miss:
            say("{grey}You twist aside from %s's %s.{/}" % (e.name, label))
            return 0
        dmg = base * self.rng.uniform(0.88, 1.12) * self._enemy_mult(e)
        if p.has("exposed"):
            dmg *= 1.3
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
    def use_item(self):
        p = self.p
        usable = [iid for iid in p.inventory if ITEMS[iid]["kind"] == "consumable"]
        if not usable:
            say("{grey}You have nothing useful to hand.{/}")
            return False
        labels = ["%s x%d {grey}- %s{/}" % (ITEMS[i]["name"], p.inventory[i], ITEMS[i]["desc"]) for i in usable]
        idx = ui.menu(labels, prompt="Use")
        if idx is None:
            return False
        iid = usable[idx]
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
            say("{bgreen}You drink the %s. (+%d health){/}" % (ITEMS[iid]["name"], p.heal(use["heal"])))
        if "oil" in use:
            say("{amber}You top up your lantern. (+%d oil){/}" % p.add_oil(use["oil"]))
        if "focus" in use:
            p.focus = min(10, p.focus + use["focus"])
            say("{sky}Your mind sharpens. (Focus %d){/}" % p.focus)
        if use.get("cleanse"):
            p.cleanse()
            say("{bone}Your head clears.{/}")
        if "regen" in use:
            p.apply("regen", 3, use["regen"], self_cast=True)
        if "firepot" in use:
            say("{flame}You hurl the firepot. It bursts in a sheet of flame!{/}")
            for e in list(self.alive):
                self.hit(e, use["firepot"] + p.WIL // 2, "fire", verb="scorch")
                e.apply("burn", 3, 4)
            self.check_deaths()
        return True

    # ------------------------------------------------------------------ skills
    def use_skill(self):
        p = self.p
        skills = p.skills
        labels = []
        for s in skills:
            d = SKILLS[s]
            ok = p.focus >= d["cost"]
            labels.append("%s%s {grey}(%d focus){/} {grey}- %s{/}" % (
                "" if ok else "{grey}", d["name"] + ("" if ok else "{/}"), d["cost"], d["desc"]))
        idx = ui.menu(labels, prompt="Skill")
        if idx is None:
            return False
        sid = skills[idx]
        d = SKILLS[sid]
        if p.focus < d["cost"]:
            say("{grey}Not enough focus.{/}")
            return False
        target = None
        if d["target"] == "enemy":
            target = self.pick_target()
            if not target:
                return False
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
        ui.io.take_capture()
        blank()
        if outcome == "win":
            ui.rule("VICTORY", color="gold")
            self.g.stats["battles"] = self.g.stats.get("battles", 0) + 1
            p.gold += self.gold
            say("{gold}+%d xp   +%d gold{/}" % (self.xp, self.gold))
            for iid in self.loot:
                p.add_item(iid)
                say("{bone}You take: %s{/}" % ITEMS[iid]["name"])
            levels = p.gain_xp(self.xp)
            if levels:
                self.g.level_up_ceremony(levels)
        elif outcome == "fled":
            ui.rule(color="grey")
        return outcome
