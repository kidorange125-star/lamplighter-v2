"""Brann's forge, as a menu: start a forging, collect finished work, socket relics, hurry with gems."""
from . import forge, gear, quench, rarity, ui
from .content import ITEMS
from .rarity import INFO, RARITIES
from .ui import blank, say

LINE = {"ember": "Brann"}


def _brann(text):
    say('{ember}Brann:{/} "%s"' % text)


def _stops():
    return [(INFO[r]["name"], INFO[r]["colour"]) for r in RARITIES]


def reveal(result):
    """The colour sweep, then what you got."""
    blank()
    if result["success"]:
        say("{b}The metal takes the heat...{/}")
    else:
        say("{b}The metal takes the heat... and holds.{/}")
    ui.sweep(_stops(), RARITIES.index(result["after"]))
    if result["success"]:
        say("{bgreen}It took!{/} %s is now %s." % (result["name"], rarity.describe(result["item"])))
        _show_item(result["item"])
    else:
        say("{grey}The forging did not take. %s stays %s. The fire remembers: your next attempt is more likely to "
            "succeed (heat %d). Half the materials come back.{/}" % (result["name"], result["after"], result["heat"]))


TEMPER_STOPS = [("x2.0", "bgreen"), ("x2.5", "gold"), ("x3.0", "bcyan")]


def reveal_temper(result):
    """The Long Quench: a three-stop sweep (x2.0, x2.5, x3.0) instead of the rarity sweep, then what the blade kept."""
    blank()
    say("{b}Seven days in the Ember Smithy. Brann lifts the blade from the light, and Tamsin turns it to the window...{/}")
    mults = [m for m, _ in quench.outcomes()]
    stops = [(("x%.1f" % m), TEMPER_STOPS[min(i, len(TEMPER_STOPS) - 1)][1]) for i, m in enumerate(mults)]
    ui.sweep(stops, mults.index(result["rolled"]))
    if result["improved"]:
        say("{bgreen}It took!{/} %s: all damage x%.1f." % (result["name"], result["after"]))
        _show_item(result["item"])
    else:
        say("{grey}This quench came to x%.1f, and the blade already holds x%.1f. It keeps the better. Nothing is lost.{/}" % (
            result["rolled"], result["before"]))
    if result["after"] >= quench.best_mult():
        say("{grey}Nothing more can be asked of this blade. It is as tempered as the third quench goes.{/}")
    elif result["rolled"] < quench.best_mult():
        say("{grey}The fire remembers: your next quench is likelier to reach x%.1f.{/}" % quench.best_mult())


def _show_item(iid):
    it = ITEMS[iid]
    parts = ["%s %+d" % (k.upper(), v) for k, v in it.get("stats", {}).items()]
    names = {"dmg": "all damage", "phys": "weapon damage", "fire": "fire damage", "light": "flare damage", "heal": "healing"}
    parts += ["x%.2f %s" % (v, names.get(k, k)) for k, v in it.get("mult", {}).items()]
    if parts:
        say("{grey}%s{/}" % ", ".join(parts), indent=6)
    if it.get("sockets"):
        say("{grey}Relic sockets: %d{/}" % it["sockets"], indent=6)


def _job_lines(g):
    st = forge.state(g)
    say("{grey}Forge slots in use: %d of %d.   Gems: %d{/}" % (st["slots"] - forge.free_slots(g), st["slots"], g.player.gems))
    for j in st["jobs"]:
        if j.get("kind") == "temper":
            if j["done"]:
                say("  {bgreen}ready{/}  %s  {grey}(Long Quench){/}" % rarity.label(j["item"]))
            else:
                say("  {amber}working{/} %s  {grey}Long Quench: %s left, or %d steps{/}" % (
                    rarity.label(j["item"]), quench.time_left_text(j), max(0, j["steps"])))
            if j.get("loaner"):
                say("    {grey}You carry a loaner in its place (weaker; it goes back when the real one is done).{/}")
            continue
        t = forge.info(j["item"]) or {}
        if j["done"]:
            say("  {bgreen}ready{/}  %s  {grey}(to %s){/}" % (rarity.label(j["item"]), t.get("to", "?")))
        else:
            say("  {amber}working{/} %s  {grey}about %d min or %d steps left{/}" % (
                rarity.label(j["item"]), forge.minutes_left(j), max(0, j["steps"])))
        if j.get("slots", 1) > 1:
            say("    {grey}It holds both anvils until it is done.{/}")
        if j.get("loaner"):
            say("    {grey}You carry a loaner in its place (weaker; it goes back when the real one is done).{/}")


def menu(g):
    p = g.player
    note = ""
    while True:
        ui.clear()
        ui.rule("TAMSIN'S FORGE" if g.room_id == "ember_smithy" else "BRANN'S FORGE", color="ember")
        if note:
            say(note)
            blank()
        _job_lines(g)
        blank()
        opts = []
        ready = forge.ready_jobs(g)
        if ready:
            opts.append(("{bgreen}Collect finished work (%d){/}" % len(ready), "collect"))
        opts.append(("Forge something better {grey}(Rare and up; gear and relics){/}", "start"))
        opts.append(("Socket a relic into gear, or take one out", "socket"))
        if quench.unlocked(g):
            opts.append(("The Long Quench {grey}(a week at the anvil, Godlike weapons){/}", "quench"))
        if any(not j["done"] for j in forge.state(g)["jobs"]):
            opts.append(("Hurry a job with gems", "hurry"))
        opts.append(("How forging works", "help"))
        i = ui.menu([o[0] for o in opts], prompt="Forge", cancel_label="Leave the forge")
        if i is None:
            return
        k = opts[i][1]
        note = ""
        if k == "help":
            ui.clear()
            ui.rule("HOW FORGING WORKS", color="ember")
            say("Take Rare or better gear (or a relic) to the forge and Brann tries to raise it one tier. It costs gold and "
                "materials, and takes time: some minutes of real time or some steps of walking, whichever comes first.")
            say("It is {b}never guaranteed{/}. The odds are shown first. Every failure adds {b}heat{/}, which raises "
                "the next chance, and a full heat bar is a sure thing. A failed forging destroys nothing; the item comes back "
                "and half the materials with it.")
            say("If you hand over the weapon you are holding, you carry a {b}loaner{/} of the same weapon, %d%% weaker, "
                "until the real one is done." % round((1 - forge_penalty()) * 100))
            say("A {b}Godlike{/} forging is the hardest of all: it takes both anvils (Brann's and Tamsin's, so the Ember "
                "Smithy must be built), and the knowledge of the third quench.")
            say("Better gear has more sockets. Relics fit the sockets and multiply your damage. Hollow Cores, dropped by "
                "bosses, are needed from Epic upward and to improve relics.")
            ui.pause()
        elif k == "start":
            note = _start(g)
        elif k == "collect":
            for idx in sorted(forge.ready_jobs(g), reverse=True):
                result = forge.collect(g, idx)
                ui.clear()
                ui.rule("FROM THE FORGE", color="ember")
                if result.get("kind") == "temper":
                    reveal_temper(result)
                else:
                    reveal(result)
                blank()
                ui.pause()
        elif k == "hurry":
            note = _hurry(g)
        elif k == "socket":
            note = _socket(g)
        elif k == "quench":
            note = quench.menu(g)


def forge_penalty():
    from .content import FORGE
    return FORGE["loaner_penalty"]


def _start(g):
    cands = forge.candidates(g)
    if not cands:
        return "{grey}You have nothing to forge. Rare or better gear and relics can be improved; plain gear cannot.{/}"
    if forge.free_slots(g) <= 0:
        return "{grey}Every forge slot is busy. Collect or wait.{/}"
    labels = []
    for iid, where in cands:
        t = forge.info(iid)
        labels.append("%s {grey}(%s) to %s: %d%% chance, %s{/}" % (
            rarity.label(iid), where, t["to"], round(100 * forge.chance(g, iid)), forge.cost_text(iid)))
    idx = ui.menu(labels, prompt="Forge which", cancel_label="Back")
    if idx is None:
        return ""
    iid, where = cands[idx]
    t = forge.info(iid)
    h = forge.heat(g, iid)
    ui.clear()
    ui.rule("A FORGING", color="ember")
    say("%s  {grey}%s to %s{/}" % (rarity.label(iid), rarity.describe(iid), rarity.describe_name(t["to"])))
    say("Chance: {b}%d%%{/}   Heat: %d of %d {grey}(a full heat bar is a sure thing){/}" % (
        round(100 * forge.chance(g, iid)), h, t["pity"]))
    say("Cost: %s" % forge.cost_text(iid))
    say("Time: about %d minutes of real time, or %d steps of walking." % (t["minutes"], t["steps"]))
    if forge.slots_needed(iid) > 1:
        say("{grey}This takes both anvils at once: two hands on the wick.{/}")
    block = forge.slot_block(g, iid)
    if block:
        return "{grey}%s{/}" % block
    lack = forge.missing(g, iid)
    if lack:
        return "{grey}You still need %s.{/}" % ", ".join(lack)
    if where == "worn" and ITEMS[iid]["kind"] == "weapon":
        say("{grey}You will carry a loaner while it works (%d%% weaker).{/}" % round((1 - forge_penalty()) * 100))
    if not ui.confirm("Hand it to Brann?"):
        return ""
    ok, msg = forge.start(g, iid)
    if not ok:
        return "{grey}%s{/}" % msg
    _brann("I'll see what the fire says.")
    return "{bgreen}Brann takes the %s to the fire.{/}" % ITEMS[iid]["name"]


def _hurry(g):
    jobs = [(i, j) for i, j in enumerate(forge.state(g)["jobs"]) if not j["done"]]
    labels = []
    for _, j in jobs:
        if j.get("kind") == "temper":
            labels.append("%s {grey}(Long Quench: skip one day for %d gems, %d left to skip){/}" % (
                rarity.label(j["item"]), forge.hurry_cost(j), quench.hurry_left(j)))
        else:
            labels.append("%s {grey}(%d gems){/}" % (rarity.label(j["item"]), forge.hurry_cost(j)))
    idx = ui.menu(labels, prompt="Hurry which", cancel_label="Back")
    if idx is None:
        return ""
    i, j = jobs[idx]
    cost = forge.hurry_cost(j)
    if j.get("kind") == "temper":
        if quench.hurry_left(j) <= 0:
            return "{grey}Gems can skip two days of the week, no more. The rest is real time.{/}"
        if g.player.gems < cost:
            return "{grey}That takes %d gems and you have %d.{/}" % (cost, g.player.gems)
        if ui.confirm("Spend %d gems to skip a day?" % cost):
            forge.hurry(g, i)
            return "{bgreen}A day goes by in an afternoon. %s left.{/}" % quench.time_left_text(j).capitalize()
        return ""
    if g.player.gems < cost:
        return "{grey}That takes %d gems and you have %d.{/}" % (cost, g.player.gems)
    if ui.confirm("Spend %d gems to finish it now?" % cost):
        forge.hurry(g, i)
        return "{bgreen}The fire roars and the work is done.{/}"
    return ""


def _socket(g):
    p = g.player
    opts = ["Put a relic in", "Take a relic out"]
    i = ui.menu(opts, prompt="Sockets", cancel_label="Back")
    if i is None:
        return ""
    if i == 0:
        hosts = [h for h in forge.socketable_hosts(g) if len(gear.socketed(h)) < gear.sockets_of(h)]
        relics = forge.relics_in_pack(g)
        if not hosts:
            return "{grey}Nothing you own has a free socket. Rare and better gear has them; better rarity has more.{/}"
        if not relics:
            return "{grey}You have no relics. Tallow sells common ones, and Hollow Cores improve them at the forge.{/}"
        a = ui.menu(["%s {grey}(%d of %d sockets used){/}" % (rarity.label(h), len(gear.socketed(h)), gear.sockets_of(h))
                     for h in hosts], prompt="Into which", cancel_label="Back")
        if a is None:
            return ""
        b = ui.menu(["%s {grey}%s{/}" % (rarity.label(r), ITEMS[r].get("desc", "")[:60]) for r in relics],
                    prompt="Which relic", cancel_label="Back")
        if b is None:
            return ""
        new = forge.socket_in(g, hosts[a], relics[b])
        if not new:
            return "{grey}No free socket.{/}"
        _brann("There. Seated and snug.")
        return "{bgreen}%s now carries it.{/}" % rarity.label(new)
    hosts = [h for h in forge.socketable_hosts(g) if gear.socketed(h)]
    if not hosts:
        return "{grey}No relics are socketed in anything you own.{/}"
    a = ui.menu([rarity.label(h) for h in hosts], prompt="From which", cancel_label="Back")
    if a is None:
        return ""
    host = hosts[a]
    rels = gear.socketed(host)
    b = ui.menu(["%s relic: %s" % (r["rarity"], ITEMS[r["base"]]["name"]) for r in rels], prompt="Which", cancel_label="Back")
    if b is None:
        return ""
    back = forge.take_out(g, host, b)
    return "{bgreen}Brann pries it loose. You get your %s back, unharmed.{/}" % rarity.label(back)
