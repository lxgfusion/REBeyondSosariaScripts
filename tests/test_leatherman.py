"""Offline tests for Scripts/Leatherman.py.

    python tests/test_leatherman.py

Loads the real script with the trailing main() call stripped and stub Razor
globals injected, then calls the actual functions - no copied logic to drift.

Carries the two bugs that were found in game while this round was being built
inside TameAndFill, before it was pulled out into its own script:

  * a mobile nobody has queried reports Hits = 0 AND HitsMax = 0, which means
    UNKNOWN and not dead - reading it as dead made the kill loop return before
    casting once, so it announced a kill, cast nothing, and still ran the
    carve-and-store tail over a live animal
  * carving happens next to the corpse and the kill happens at spell range, so
    the corpse has to be walked to
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "Leatherman.py")

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


class _Stub(object):
    def __getattr__(self, name):
        return lambda *a, **k: None


class StubPlayer(object):
    Serial = 0x0001A2B3
    Backpack = None
    Mana = 100
    IsGhost = False

    def DistanceTo(self, other):
        return 1

    def ChatSay(self, hue, text):
        pass


def load():
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    env = {
        "__name__": "leatherman_under_test",
        "Misc": _Stub(), "Player": StubPlayer(), "Items": _Stub(),
        "Mobiles": _Stub(), "Journal": _Stub(), "Target": _Stub(),
        "PathFinding": _Stub(), "Gumps": _Stub(), "Spells": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), env)
    return env


def test_it_is_a_standalone_script(m):
    """One file, self-contained. Razor runs each .py from its Scripts folder
    and cross-file imports break the moment anyone moves a file."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            check("only stdlib imported: %r" % stripped,
                  stripped in ("import time", "import re", "import os"), True)
    check("it has its own version banner", bool(m["SCRIPT_VERSION"]), True)
    check("and its own main", "def main():" in src, True)


def test_nothing_is_attacked_without_a_name_match(m):
    """The single most important property: a body match alone must never be
    enough. Bodies are shared and have been wrong in extracted data."""
    check("HARVEST_WORDS is what decides",
          m["is_harvest_target"]("a cow"), True)
    check("an unlisted animal is safe", m["is_harvest_target"]("a horse"),
          False)
    check("and something unnamed is safe", m["is_harvest_target"](""), False)

    import ast as _ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef)
              and n.name == "harvest_candidates")
    called = set()
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Call) and getattr(node.func, "id", None):
            called.add(node.func.id)
    check("the candidate search name-checks every hit",
          "is_harvest_target" in called, True)


def test_the_spell_is_required_not_guessed(m):
    """The tamer's spell table did not come across, so a blank spell has no
    fallback - preflight has to refuse rather than cast nothing."""
    check("magic arrow", m["HARVEST_SPELL"], "Magic Arrow")
    check("cast as magery", m["HARVEST_SPELL_SCHOOL"], "magery")
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    check("no dangling reference to the tamer's chooser",
          "best_spell_against" in src, False)




# --------------------------------------------------------------------------
# Cow harvest - kill, carve, loot, store
# --------------------------------------------------------------------------

def test_the_name_decides_what_gets_killed(m):
    """A body match alone must never be enough to attack something. Bodies are
    shared between species and have been wrong in extracted data before - a
    stray 0x3 in the sheep entry once had the tamer walking up to zombies."""
    check("a cow is a target", m["is_harvest_target"]("a cow"), True)
    check("case does not matter", m["is_harvest_target"]("A Cow"), True)

    for name in ("a horse", "a bull", "a sheep", "a dire wolf", ""):
        check("%r is not a target" % name, m["is_harvest_target"](name), False)


def test_the_kill_loop_is_bounded(m):
    check("a cast ceiling", m["HARVEST_MAX_CASTS"] >= 1, True)
    check("and a wall-clock deadline", m["HARVEST_DEATH_MS"] >= 1000, True)
    check("mana waiting is bounded too", m["HARVEST_MANA_WAIT_MS"] >= 1000,
          True)

    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "kill_target")
    names = set(n.id for n in _ast.walk(fn) if isinstance(n, _ast.Name))
    check("the loop tests the cast ceiling", "HARVEST_MAX_CASTS" in names, True)
    check("and the deadline", "deadline" in names, True)


def test_only_our_own_corpses_are_carved(m):
    """Somebody else's corpse is somebody else's loot."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "carve_corpses")
    names = set(n.id for n in _ast.walk(fn) if isinstance(n, _ast.Name))
    check("it checks the recorded kill list", "_harvest_corpses" in names, True)

    # And the recording happens only after a confirmed death.
    fn2 = next(n for n in _ast.walk(tree)
               if isinstance(n, _ast.FunctionDef) and n.name == "harvest_pass")
    src = _ast.dump(fn2)
    check("a corpse is only recorded after a kill", "'dead'" in src, True)


def test_every_cursor_is_cancelled_first(m):
    """A leaked cursor is silently answered by the NEXT TargetExecute, so a
    cast or a carve goes nowhere and nothing says so."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    for fname in ("cast_at", "carve_corpses"):
        fn = next(n for n in _ast.walk(tree)
                  if isinstance(n, _ast.FunctionDef) and n.name == fname)
        called = set()
        for node in _ast.walk(fn):
            if isinstance(node, _ast.Call):
                if getattr(node.func, "id", None):
                    called.add(node.func.id)
                if getattr(node.func, "attr", None):
                    called.add(node.func.attr)
        check("%s clears the cursor first" % fname, "clear_cursor" in called,
              True)
        check("%s waits for the cursor" % fname, "WaitForTarget" in called,
              True)
        check("%s targets by serial" % fname, "TargetExecute" in called, True)


def test_the_storage_keys_are_found_by_serial_first(m):
    """Both keys sit in a BAG inside the pack. Items.FindAllByID with a
    container serial walks that container's own Contains one level deep, so a
    backpack-level search would never see either of them."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def find_stock_key("):src.index("def store_harvest(")]
    check("serial first", body.index("FindBySerial") < body.index("FindAllByID"),
          True)
    check("and the fallback searches the WORLD, not the backpack",
          "FindAllByID(graphic, hue, -1," in body, True)
    check("not the backpack", "Backpack.Serial" in body, False)


def test_the_keys_are_answered_by_label_not_position(m):
    """A menu that gains an entry would otherwise answer something else."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def harvest_context_select("):
               src.index("def find_stock_key(")]
    check("the real label goes back", "Misc.ContextReply(entity, text)" in body,
          True)
    check("exact match is tried first", body.count("strip().lower()") >= 2, True)
    check("and dangerous entries are refused",
          "harvest_context_blocked" in body, True)

    for bad in ("destroy", "empty", "delete"):
        check("%r is on the never list" % bad,
              bad in [w.lower() for w in m["HARVEST_CONTEXT_NEVER"]], True)


def test_the_inspected_key_graphics_are_configured(m):
    by_label = dict((k["label"], k) for k in m["HARVEST_KEYS"])
    check("Tailor Store is configured", "Tailor Store" in by_label, True)
    check("Butcher's Hook is configured", "Butcher's Hook" in by_label, True)
    check("tailor graphic", by_label["Tailor Store"]["id"], 0x0F9D)
    check("tailor hue", by_label["Tailor Store"]["hue"], 0x0044)
    check("butcher graphic", by_label["Butcher's Hook"]["id"], 0x26BB)
    check("butcher hue", by_label["Butcher's Hook"]["hue"], 0x0697)
    for label, spec in by_label.items():
        check("%s has a name check for the graphic fallback" % label,
              bool(spec.get("names")), True)


def test_the_grab_command_is_said_after_carving(m):
    """Loot has to be on the ground before [grab can sweep it up."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def harvest_pass("):]
    body = body[:body.index("\ndef ") if "\ndef " in body else len(body)]
    check("[grab is the phrase", m["HARVEST_GRAB_PHRASE"], "[grab")
    check("carving comes before the grab",
          body.index("carve_corpses()") < body.index("grab_loot()"), True)
    check("and storing comes after it",
          body.index("grab_loot()") < body.index("store_harvest()"), True)


def test_grab_honours_the_three_second_cooldown(m):
    """The shard refuses the loot command if it is said sooner than every
    three seconds, and the refusal is SILENT - the loot stays on the ground.
    Two cows dying close together is enough to hit it."""
    check("the cooldown is at least three seconds",
          m["HARVEST_GRAB_COOLDOWN_MS"] >= 3000, True)

    saved = (m["Misc"], m["Player"], m["debug"])
    paused = []
    said = []

    class P(object):
        def ChatSay(self, hue, text):
            said.append(text)

    class M(object):
        def Pause(self, ms):
            paused.append(ms)

        def __getattr__(self, name):
            return lambda *a, **k: None

    try:
        m["Misc"] = M()
        m["Player"] = P()
        m["debug"] = lambda *a, **k: None

        m["_last_grab"][0] = 0.0
        del paused[:]
        m["grab_loot"]()
        check("it said the loot command", said, [m["HARVEST_GRAB_PHRASE"]])
        check("and owed no cooldown", max(paused) <= m["HARVEST_GRAB_MS"], True)

        import time as _time
        m["_last_grab"][0] = _time.time()
        del paused[:]
        del said[:]
        m["grab_loot"]()
        check("it said it again", said, [m["HARVEST_GRAB_PHRASE"]])
        check("after waiting out the remainder",
              max(paused) >= m["HARVEST_GRAB_COOLDOWN_MS"] - 500, True)
        check("it waits rather than abandoning the loot", len(said), 1)
    finally:
        m["Misc"], m["Player"], m["debug"] = saved


def test_harvest_can_be_switched_off(m):
    check("there is a switch", m["HARVEST_ENABLED"] in (True, False), True)
    saved = m["HARVEST_ENABLED"]
    try:
        m["HARVEST_ENABLED"] = False
        check("off means no candidates", m["harvest_candidates"](), [])
        check("and no pass", m["harvest_pass"](), False)
    finally:
        m["HARVEST_ENABLED"] = saved


def test_an_unqueried_mobile_is_not_dead(m):
    """THE BUG THAT MADE IT DO NOTHING.

    A mobile the client has never asked about reports Hits = 0 AND
    HitsMax = 0. Reading that as death made kill_target return on its first
    pass, before casting once: it logged "Killing a cow", cast nothing, walked
    to no corpse, and still ran the carve-and-store tail - which is why the
    Butcher's Hook fired over an animal standing there unharmed.
    """
    class Mob(object):
        def __init__(self, hits, hits_max, ghost=False):
            self.Hits = hits
            self.HitsMax = hits_max
            self.IsGhost = ghost

    dead = m["creature_is_dead"]
    check("0/0 is UNKNOWN, not dead", dead(Mob(0, 0)), False)
    check("a healthy cow is not dead", dead(Mob(38, 38)), False)
    check("a hurt cow is not dead", dead(Mob(4, 38)), False)
    check("0 of a known maximum IS dead", dead(Mob(0, 38)), True)
    check("a ghost is dead", dead(Mob(10, 38, ghost=True)), True)

    # Nothing readable at all must not read as death either.
    class Silent(object):
        def __getattr__(self, name):
            raise RuntimeError("not loaded")

    check("an unreadable mobile is not dead", dead(Silent()), False)


def test_the_status_is_asked_for_before_it_is_read(m):
    """Hits is 0 until something queries the mobile. Reading it cold is what
    made 0/0 look like a corpse."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "kill_target")
    called = set()
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Call) and getattr(node.func, "attr", None):
            called.add(node.func.attr)
    check("it requests the stats", "WaitForStats" in called, True)


def test_death_is_read_from_disappearance_first(m):
    """The creature vanishing is the reliable signal; Hits is the cross-check
    and only once the client knows it."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def kill_target("):src.index("def find_dagger(")]
    check("absence means dead", "if mob is None:" in body, True)
    check("and Hits goes through the guarded test",
          "creature_is_dead(mob)" in body, True)
    check("the raw Hits test is gone", "int(mob.Hits or 0) <= 0" in body, False)


def test_it_walks_to_the_corpse(m):
    """Carving needs to be next to the corpse, but the kill happens at spell
    range. Searching three tiles from where it killed something ten tiles away
    found nothing, silently."""
    check("the search range is wider than the carve range",
          m["HARVEST_CORPSE_SEARCH"] > m["HARVEST_CORPSE_RANGE"], True)
    check("and wide enough to cover the kill",
          m["HARVEST_CORPSE_SEARCH"] >= m["HARVEST_RANGE"], True)

    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def carve_corpses("):src.index("def harvest_pass(")]
    check("it walks to the corpse", "pathfind_to(" in body, True)
    check("after measuring the distance", "DistanceTo(corpse)" in body, True)
    check("and gives up on one it cannot reach",
          "Could not get to the corpse" in body, True)


def test_it_waits_for_the_corpse_to_appear(m):
    """The corpse does not exist the instant the creature does not."""
    check("there is a wait", m["HARVEST_CORPSE_WAIT_MS"] >= 500, True)
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def harvest_pass("):]
    check("it looks for the corpse before carving",
          "corpse_in_sight()" in body, True)


def test_a_cast_that_never_goes_out_is_loud_and_bounded(m):
    """"It says it is killing but nothing happens" was the whole report. A
    cast that produces no cursor has to say so, and three in a row has to stop
    rather than stand there."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    cast = src[src.index("def cast_at("):src.index("def creature_is_dead(")]
    check("a missing cursor is logged, not debugged",
          "No target cursor for" in cast, True)

    kill = src[src.index("def kill_target("):src.index("def find_dagger(")]
    check("repeated misses stop the loop", "misses[0] >= 3" in kill, True)


def main():
    module = load()
    test_it_is_a_standalone_script(module)
    test_nothing_is_attacked_without_a_name_match(module)
    test_the_spell_is_required_not_guessed(module)
    test_the_name_decides_what_gets_killed(module)
    test_the_kill_loop_is_bounded(module)
    test_only_our_own_corpses_are_carved(module)
    test_every_cursor_is_cancelled_first(module)
    test_the_storage_keys_are_found_by_serial_first(module)
    test_the_keys_are_answered_by_label_not_position(module)
    test_the_inspected_key_graphics_are_configured(module)
    test_the_grab_command_is_said_after_carving(module)
    test_grab_honours_the_three_second_cooldown(module)
    test_harvest_can_be_switched_off(module)
    test_an_unqueried_mobile_is_not_dead(module)
    test_the_status_is_asked_for_before_it_is_read(module)
    test_death_is_read_from_disappearance_first(module)
    test_it_walks_to_the_corpse(module)
    test_it_waits_for_the_corpse_to_appear(module)
    test_a_cast_that_never_goes_out_is_loud_and_bounded(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-52s got=%-22s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:22], repr(want)[:26]))
        if not ok:
            failed += 1
    print("")
    print("%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
