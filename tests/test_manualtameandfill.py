"""
Offline tests for ManualTameAndFill.py.
=======================================

    python tests/test_manualtameandfill.py

WHAT IS WORTH TESTING HERE. This script's promise is almost entirely a
NEGATIVE one, and it was asked for in those terms: it is 100% manual except
for scanning the pack and putting the animals YOU tame into their deeds. It
must not walk, chase, cast, recall, attack, or target a wild creature, and
above all it must never swallow a pet you meant to keep.

A promise like that is not proved by the happy path working. So:

  1. THE SURFACE is read off the shipped source. The script may only touch a
     fixed allowlist of Razor API calls, there may be exactly one
     Items.UseItem and one Target.TargetExecute in the whole file, and the
     parent's hunting, combat and harvesting functions must be absent by name.
     Adding Player.Run to this file fails this suite.

  2. THE CREDIT RULE is executed. Nothing is deeded without an unspent
     taming-success line from your journal, which is what stops an old pet
     wandering into range from being fed to a deed.

  3. THE REFUSALS are executed, one per reason, because each of them is an
     animal saved.

  4. THE DRAIN is proved behaviourally, not by reading the source: a taming
     line that arrives while a fill is in progress survives the
     Journal.Clear() inside deed_attempt.

The animal catalogue, the deed tooltip parser and deed_attempt's target
sequence are carried over from TameAndFill.py by tools/../build_manual.py and
tested in test_tame_animals.py; they are exercised here only where this fork
leans on them.
"""

import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "ManualTameAndFill.py")

FAILURES = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-62s got=%-26r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


# ---------------------------------------------------------------------------
# Stubs. Only as much Razor as this script actually touches.
# ---------------------------------------------------------------------------

class StubClock(object):
    """A clock we drive, so the credit window is exact and not timing-dependent."""

    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now


class StubEntry(object):
    def __init__(self, text, stamp):
        self.Text = text
        self.Timestamp = stamp
        self.Serial = 0


class StubJournal(object):
    """Returns the WHOLE buffer whatever stamp it is handed.

    Deliberately dumber than the real one: RazorEnhanced's GetJournalEntry
    filters by stamp itself, so a stub that also filtered would hide a bug in
    the script's own `stamp <= cursor` test. Clear() throws the buffer away,
    exactly like the real one.
    """

    def __init__(self):
        self.entries = []
        self.clears = 0

    def say(self, text, stamp):
        self.entries.append(StubEntry(text, stamp))

    def GetJournalEntry(self, stamp):
        return list(self.entries)

    def Clear(self):
        self.clears += 1
        self.entries = []

    def Search(self, text):
        low = text.lower()
        return any(low in e.Text.lower() for e in self.entries)


class StubMobile(object):
    def __init__(self, serial, name, body, props=None):
        self.Serial = serial
        self.Name = name
        self.Body = body
        self._props = list(props or [])


class StubMobiles(object):
    def __init__(self):
        self.by_serial = {}
        self.in_range = []
        self.prop_reads = 0

    def add(self, mob, in_range=True):
        self.by_serial[mob.Serial] = mob
        if in_range:
            self.in_range.append(mob)
        return mob

    def remove(self, serial):
        self.by_serial.pop(serial, None)
        self.in_range = [m for m in self.in_range if m.Serial != serial]

    def FindBySerial(self, serial):
        return self.by_serial.get(serial)

    def WaitForProps(self, mob, delay):
        pass

    def GetPropStringList(self, mob):
        self.prop_reads += 1
        return list(mob._props)

    def SingleClick(self, mob):
        pass

    def Filter(self):
        return StubFilter()

    def ApplyFilter(self, f):
        return list(self.in_range)


class AddList(list):
    """Razor's filter collections are .NET lists: .Add, not .append."""

    def Add(self, value):
        self.append(value)


class StubFilter(object):
    def __init__(self):
        self.Enabled = False
        self.RangeMax = 0
        self.OnGround = None
        self.Graphics = AddList()
        self.Bodies = AddList()


class StubItem(object):
    def __init__(self, serial, name, props, container, item_id=0x14F0):
        self.Serial = serial
        self.Name = name
        self.ItemID = item_id
        self._props = list(props)
        self.Container = container
        self.RootContainer = container


class StubItems(object):
    def __init__(self):
        self.by_serial = {}
        self.pack = []
        self.used = []

    def add(self, item):
        self.by_serial[item.Serial] = item
        self.pack.append(item)
        return item

    def FindBySerial(self, serial):
        return self.by_serial.get(serial)

    def WaitForProps(self, item, delay):
        pass

    def GetPropStringList(self, item):
        return list(item._props)

    def Filter(self):
        return StubFilter()

    def ApplyFilter(self, f):
        return list(self.pack)

    def UseItem(self, serial):
        self.used.append(serial)


class StubTarget(object):
    def __init__(self):
        self.has = False
        self.executed = []
        self.on_execute = None

    def ClearQueue(self):
        pass

    def ClearLastandQueue(self):
        pass

    def HasTarget(self):
        return self.has

    def Cancel(self):
        self.has = False

    def WaitForTarget(self, ms, flag):
        return True

    def TargetExecute(self, serial):
        self.executed.append(serial)
        if self.on_execute is not None:
            self.on_execute(serial)


class StubMisc(object):
    def __init__(self):
        self.messages = []

    def SendMessage(self, text, hue, flag):
        self.messages.append(text)

    def Pause(self, ms):
        pass


class StubPlayer(object):
    Serial = 0x41414141
    IsGhost = False
    Followers = 0
    FollowersMax = 5

    def __init__(self):
        self.Backpack = StubItem(0x40000001, "backpack", [], 0x41414141)
        self.Pets = []
        self.Mount = None
        self.skill = 60.0
        self.distances = {}

    def DistanceTo(self, mob):
        return self.distances.get(mob.Serial, 1)

    def GetSkillValue(self, name):
        return self.skill


def load():
    """Exec the real script with main() removed and our clock in place."""
    with io.open(SCRIPT, encoding="utf-8") as handle:
        source = handle.read()

    # Nothing may run on load, and the credit window must be measured on a
    # clock we control rather than the wall.
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    source = re.sub(r"^import time\s*$", "", source, flags=re.M)

    env = {
        "__name__": "manual_tame_under_test",
        "time": StubClock(),
        "Misc": StubMisc(),
        "Player": StubPlayer(),
        "Items": StubItems(),
        "Mobiles": StubMobiles(),
        "Journal": StubJournal(),
        "Target": StubTarget(),
    }
    exec(compile(source, SCRIPT, "exec"), env)
    env["build_species"]()
    return env


def fresh():
    """A loaded script with a hind deed in the pack and the species built."""
    m = load()
    m["Items"].add(StubItem(0x40005001, "a taming order deed",
                            ["Level: 2", "Creature Type: Hind",
                             "Filled: 23/60", "Gold: 100%"],
                            m["Player"].Backpack.Serial))
    m["rescan"]("test")
    return m


def source_text():
    with io.open(SCRIPT, encoding="utf-8") as handle:
        return handle.read()


def code_only(text):
    """The source with comment lines and docstrings dropped.

    A check that matches its own explanatory comment passes for the wrong
    reason; this file talks about Player.Run in prose precisely so that it
    cannot be called, so the prose has to come out before counting.
    """
    tree = ast.parse(text)
    doc_lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", None) or []
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            first = body[0].value
            for line in range(first.lineno, (first.end_lineno or first.lineno) + 1):
                doc_lines.add(line)
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number in doc_lines:
            continue
        if line.strip().startswith("#"):
            continue
        out.append(line.split("  #")[0])
    return "\n".join(out)


# ===========================================================================
# 1. THE PROMISE: 100% MANUAL EXCEPT SCANNING AND DEEDING
# ===========================================================================

# Everything this script is allowed to say to Razor. It reads the pack, reads
# creatures, reads the journal, prints, pauses, double-clicks ONE deed and
# answers ONE target cursor. Anything that moves the character, throws a
# spell, swings at something, travels, or picks a fight is not on it.
ALLOWED_API = set("""
Items.ApplyFilter Items.Filter Items.FindBySerial Items.GetPropStringList
Items.UseItem Items.WaitForProps
Journal.Clear Journal.GetJournalEntry Journal.Search
Misc.Pause Misc.SendMessage
Mobiles.ApplyFilter Mobiles.Filter Mobiles.FindBySerial
Mobiles.GetPropStringList Mobiles.SingleClick Mobiles.WaitForProps
Player.Backpack Player.DistanceTo Player.GetSkillValue Player.IsGhost
Player.Mount Player.Pets Player.Serial
Target.Cancel Target.ClearLastandQueue Target.ClearQueue Target.HasTarget
Target.TargetExecute Target.WaitForTarget
""".split())

# The parent's names for the work this fork refuses to do. Absent, not merely
# unreachable: a fork that keeps a dead approach() is one edit from using it.
BANNED_FUNCTIONS = [
    "find_candidates", "approach", "approach_tile", "pathfind_to", "move",
    "step_toward", "direction_to", "tame", "watch_attempt",
    "calm_before_taming", "peacemake", "find_instrument", "defend",
    "cast_at", "threat_candidates", "closing_threats", "report_threats",
    "harvest_pass", "kill_target", "carve_corpses", "grab_loot",
    "store_harvest", "claim_corpses", "corpse_scan", "identify",
    "best_spell_against", "wait_for_mana", "recall", "travel_to",
]


def test_the_surface():
    text = source_text()
    code = code_only(text)

    used = set(re.findall(
        r"\b(?:Player|Mobiles|Items|Misc|Target|Journal|Spells|Gumps|"
        r"PathFinding|Timer|Statics|Map)\.[A-Za-z_]+", code))
    check("it calls nothing outside the allowlist",
          sorted(used - ALLOWED_API), [])

    # Named individually as well, so the failure says what went in rather than
    # just "something did".
    for forbidden in ("Player.Run", "Player.Walk", "Player.Attack",
                      "Player.ChatSay", "Misc.IgnoreObject", "Spells.",
                      "PathFinding."):
        check("it never calls %s" % forbidden, forbidden in code, False)

    check("exactly one double-click in the file (the deed)",
          len(re.findall(r"Items\.UseItem\(", code)), 1)
    check("exactly one target answered in the file (the deed's)",
          len(re.findall(r"Target\.TargetExecute\(", code)), 1)

    names = [n.name for n in ast.parse(text).body
             if isinstance(n, ast.FunctionDef)]
    check("none of the parent's hunting or combat work is here",
          sorted(set(names) & set(BANNED_FUNCTIONS)), [])

    # Both of the one-offs have to sit in deed_attempt, which is the carried-
    # over sequence confirmed in game.
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == "deed_attempt":
            inner = ast.dump(node)
            check("the double-click is inside deed_attempt",
                  "UseItem" in inner, True)
            check("the target answer is inside deed_attempt",
                  "TargetExecute" in inner, True)


def test_main_only_scans_and_fills():
    """run() may reach the deed and nothing else of consequence."""
    text = source_text()
    funcs = dict((n.name, n) for n in ast.parse(text).body
                 if isinstance(n, ast.FunctionDef))

    def calls(name):
        out = set()
        for sub in ast.walk(funcs[name]):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                out.add(sub.func.id)
        return out

    seen = set()
    stack = ["main"]
    while stack:
        here = stack.pop()
        if here in seen or here not in funcs:
            continue
        seen.add(here)
        stack.extend(calls(here))

    check("add_to_deed is reachable from main()", "add_to_deed" in seen, True)
    check("and so is the pack scan", "scan_deeds" in seen, True)
    check("and the journal reader", "poll_tames" in seen, True)

    # Everything defined in the file is reachable: no dead code to be revived
    # by a later edit.
    unreached = sorted(set(funcs) - seen - set(["main"]))
    check("nothing in the file is unreachable from main()", unreached, [])

    check("only consider() fills a deed",
          sorted(f for f in funcs if "add_to_deed" in calls(f)), ["consider"])


def test_the_fork_fills_above_your_skill():
    """SKIP_ABOVE_SKILL is False here and True in the parent, on purpose.

    The parent skips what it cannot tame because it is the one doing the
    taming. You are. An animal standing there already tamed settles the
    question, and refusing its deed on a skill table would lose it.
    """
    m = load()
    check("the fork does not skip deeds above your skill",
          m["SKIP_ABOVE_SKILL"], False)

    m["Player"].skill = 60.0            # dread warhorse wants 108
    m["Items"].add(StubItem(0x40005009, "a taming order deed",
                            ["Creature Type: Dread Warhorse", "Filled: 0/60"],
                            m["Player"].Backpack.Serial))
    m["rescan"]("skill")
    check("a dread warhorse deed is honoured at 60 taming",
          "dread warhorse" in m["_active"], True)


# ===========================================================================
# 2. THE CREDIT RULE
# ===========================================================================

def test_a_tame_banks_one_credit():
    m = fresh()
    m["Journal"].say("You see: a hind", 10.0)
    m["Journal"].say("It seems to accept you as master.", 11.0)
    m["poll_tames"]()
    check("a taming line banks one credit", len(m["_credits"]), 1)
    check("and the cursor moved to the newest line", m["_cursor"][0], 11.0)

    # The buffer still holds it. Reading again must not bank it twice.
    m["poll_tames"]()
    check("reading again does not bank it twice", len(m["_credits"]), 1)


def test_the_re_tame_message_counts():
    """ServUO sends 502797 instead of 502799 for a creature you once owned.

    It used to sit in the parent's skip list, which wrote the animal off and
    left it following you with no deed.
    """
    m = fresh()
    m["Journal"].say("That wasn't even challenging.", 5.0)
    m["poll_tames"]()
    check("'that wasn't even challenging' is a success too",
          len(m["_credits"]), 1)


def test_lines_before_startup_do_not_count():
    m = fresh()
    m["Journal"].say("It seems to accept you as master.", 3.0)
    m["_cursor"][0] = m["newest_journal_stamp"]()      # what preflight does
    m["poll_tames"]()
    check("a tame from before the script started banks nothing",
          len(m["_credits"]), 0)


def test_a_credit_expires():
    m = fresh()
    m["Journal"].say("It seems to accept you as master.", 11.0)
    m["poll_tames"]()
    check("banked", m["have_credit"](), True)

    m["time"].now += (m["TAME_CREDIT_MS"] / 1000.0) - 1.0
    check("still good just inside the window", m["have_credit"](), True)
    m["time"].now += 2.0
    check("and gone just outside it", m["have_credit"](), False)
    check("the expired credit is dropped, not kept", len(m["_credits"]), 0)


def test_the_switch_off_is_honoured_and_shouted_about():
    m = fresh()
    check("no credit, no fill", m["have_credit"](), False)
    m["REQUIRE_TAME_CREDIT"] = False
    check("unless REQUIRE_TAME_CREDIT is off", m["have_credit"](), True)
    m["preflight"]()
    check("which preflight says out loud",
          any("REQUIRE_TAME_CREDIT is OFF" in text
              for text in m["Misc"].messages), True)


# ===========================================================================
# 3. WHAT IT REFUSES, ONE REASON AT A TIME
# ===========================================================================

def hind(m, serial=0x50001, name="a hind", body=0xED):
    return m["Mobiles"].add(StubMobile(serial, name, body, ["(tame)"]))


def test_it_reads_a_creature_by_name_not_body():
    m = fresh()

    good, why, retry = m["pet_species"](hind(m))
    check("a hind with a hind's body is a hind",
          (good or {}).get("name"), "hind")

    liar = StubMobile(0x50002, "a hind", 0xE1, [])     # timber wolf's body
    species, why, retry = m["pet_species"](liar)
    check("a hind with a wolf's body is refused", species, None)
    check("and not asked about again", retry, False)

    nameless = StubMobile(0x50003, None, 0xED, [])
    species, why, retry = m["pet_species"](nameless)
    check("a creature whose name will not load is left alone", species, None)
    check("but asked about again, in case the name arrives", retry, True)

    wolf = StubMobile(0x50004, "a timber wolf", 0xE1, [])
    species, why, retry = m["pet_species"](wolf)
    check("no deed for it means no fill", species, None)
    check("and that one IS asked again, once you pocket the deed", retry, True)

    zombie = StubMobile(0x50005, "a zombie hind", 0xED, [])
    species, why, retry = m["pet_species"](zombie)
    check("NEVER_TAME_WORDS still bites", species, None)
    check("and bites for good", retry, False)


def test_a_renamed_keeper_is_safe():
    m = fresh()
    m["KEEP_NAME_WORDS"] = ["keeper"]
    pet = StubMobile(0x50010, "Keeper the hind", 0xED, [])
    species, why, retry = m["pet_species"](pet)
    check("a KEEP_NAME_WORDS match is never deeded", species, None)
    check("whatever else is true of it", retry, False)
    check("and it says which word matched", "keeper" in why, True)


def test_it_will_not_deed_your_mount():
    m = fresh()
    mount = hind(m, serial=0x50020)
    m["Player"].Mount = mount
    m["Journal"].say("It seems to accept you as master.", 11.0)
    m["poll_tames"]()
    check("the mount is refused", m["consider"](0x50020), "keep")
    check("and the credit is not spent on it", len(m["_credits"]), 1)


def test_the_serial_blocklist():
    m = fresh()
    hind(m, serial=0x50030)
    m["NEVER_FILL_SERIALS"] = [0x50030]
    check("NEVER_FILL_SERIALS is refused", m["consider"](0x50030), "keep")


def test_no_credit_no_fill():
    m = fresh()
    hind(m, serial=0x50040)
    check("a pet with no taming line behind it waits",
          m["consider"](0x50040), "wait")
    check("and nothing was double-clicked", m["Items"].used, [])
    check("and it says why",
          any("did not hear you tame it" in t for t in m["Misc"].messages),
          True)


def test_too_far_away_waits():
    m = fresh()
    pet = hind(m, serial=0x50050)
    m["Player"].distances[0x50050] = m["MAX_FILL_DIST"] + 1
    m["Journal"].say("It seems to accept you as master.", 11.0)
    m["poll_tames"]()
    check("an animal past MAX_FILL_DIST waits", m["consider"](0x50050), "wait")
    check("the credit is still there for when it walks back",
          len(m["_credits"]), 1)


def test_out_of_range_waits():
    m = fresh()
    m["Player"].Pets = [StubMobile(0x50060, "a hind", 0xED)]   # not in Mobiles
    check("a pet the client lists but we cannot see waits",
          m["consider"](0x50060), "wait")


def test_the_startup_snapshot_puts_your_pets_out_of_reach():
    m = fresh()
    keeper = StubMobile(0x50070, "a hind", 0xED, ["(tame)"])
    m["Mobiles"].add(keeper)
    m["Player"].Pets = [keeper]
    stranger = m["Mobiles"].add(StubMobile(0x50071, "a hind", 0xED, ["(tame)"]))
    wild = m["Mobiles"].add(StubMobile(0x50072, "a hind", 0xED, []))

    kept = m["snapshot"]()
    check("your existing pet is out of reach", 0x50070 in m["_known"], True)
    check("so is anything already tame standing next to you",
          0x50071 in m["_known"], True)
    check("a wild animal is not snapshotted", 0x50072 in m["_known"], False)
    check("and it counted them", kept, 2)

    # THE CASE THIS EXISTS FOR: the pet that was out of range at startup and
    # wanders back an hour later. The snapshot cannot have it, so the credit
    # rule is what has to hold it - and it does.
    m["Player"].Pets = [StubMobile(0x50073, "a hind", 0xED, ["(tame)"])]
    m["Mobiles"].add(StubMobile(0x50073, "a hind", 0xED, ["(tame)"]))
    check("a pet that strolls in later is not deeded",
          m["consider"](0x50073), "wait")


def test_the_tooltip_scan_is_not_run_for_nothing():
    """It is the one expensive thing here, so it is gated on a credit."""
    m = fresh()
    text = code_only(source_text())
    loop = text.split("def run(")[1]
    guard = loop.split("nearby_tame_creatures")[0]
    check("the fallback scan only runs with a credit in hand",
          "_credits and not pending" in guard, True)


# ===========================================================================
# 4. THE FILL ITSELF
# ===========================================================================

def arm(m, serial=0x50100):
    """A hind standing next to you that you have just been heard to tame."""
    pet = hind(m, serial=serial)
    m["Journal"].say("It seems to accept you as master.", 11.0)
    m["poll_tames"]()
    # The deed consumes the animal, which is how success is judged.
    m["Target"].on_execute = lambda s: m["Mobiles"].remove(s)
    return pet


def test_the_happy_path():
    m = fresh()
    arm(m)
    check("it fills", m["consider"](0x50100), "filled")
    check("the deed was the thing double-clicked",
          m["Items"].used, [0x40005001])
    check("and the animal was the thing targeted",
          m["Target"].executed, [0x50100])
    check("the credit is spent", len(m["_credits"]), 0)
    check("and counted", m["_filled"][0], 1)
    check("and it reports the progress it read off the deed",
          any("[23/60]" in t for t in m["Misc"].messages), True)


def test_a_failed_fill_keeps_the_credit():
    """So the next lap can try again, which is what you want when the cursor
    was busy or the animal shifted a tile. Spending up front would strand it."""
    m = fresh()
    arm(m, serial=0x50110)
    m["Target"].on_execute = None        # the animal does not go in
    check("a fill that does not take waits", m["consider"](0x50110), "wait")
    check("the credit is NOT spent", len(m["_credits"]), 1)
    check("and nothing was counted as filled", m["_filled"][0], 0)


def test_the_journal_is_drained_before_it_is_cleared():
    """THE ONE THAT MATTERS, and it is proved by behaviour, not by reading the
    source.

    deed_attempt runs Journal.Clear(). A tame that lands while a fill is in
    progress has its line in that buffer, and a Clear throws the buffer away:
    not read late, gone, with the animal left standing there undeeded. So a
    line put into the journal just before the clear must still be banked.
    """
    m = fresh()
    arm(m)

    # A second animal is tamed while the first is being deeded.
    def on_execute(serial):
        m["Journal"].say("It seems to accept you as master.", 12.0)
        m["Mobiles"].remove(serial)

    m["Target"].on_execute = on_execute
    m["Journal"].say("It seems to accept you as master.", 12.0)

    before = m["Journal"].clears
    check("it filled the first one", m["consider"](0x50100), "filled")
    check("the deed really did clear the journal",
          m["Journal"].clears > before, True)
    # One banked by arm(), one by the line above, one spent on the fill.
    check("the tame heard just before the clear survived it",
          len(m["_credits"]), 1)


def test_a_full_deed_drops_out():
    m = fresh()
    deed = m["Items"].by_serial[0x40005001]
    deed._props = ["Creature Type: Hind", "Filled: 60/60"]
    m["rescan"]("full")
    check("a full deed is not offered", "hind" in m["_active"], False)
    check("SKIP_FULL_DEEDS is what did it", m["SKIP_FULL_DEEDS"], True)

    arm(m, serial=0x50120)
    check("so the animal waits rather than being lost",
          m["consider"](0x50120), "wait")


def test_it_says_each_thing_once_per_reason():
    m = fresh()
    hind(m, serial=0x50130)
    m["consider"](0x50130)
    first = len(m["Misc"].messages)
    for _ in range(5):
        m["consider"](0x50130)
    check("five more laps say nothing new", len(m["Misc"].messages), first)


# ===========================================================================
# 5. PREFLIGHT
# ===========================================================================

def test_preflight_snapshots_before_it_opens_the_journal():
    """In that order, or a tame heard during startup could be spent on a pet
    that had not been put out of reach yet."""
    m = fresh()
    text = code_only(source_text())
    body = text.split("def preflight(")[1].split("def run(")[0]
    check("the snapshot comes before the journal cursor",
          body.index("snapshot()") < body.index("newest_journal_stamp()"),
          True)


def test_preflight_reports_and_passes():
    # load(), not fresh(): rescan() only announces a CHANGE, so preflight on an
    # env that has already scanned the same pack would correctly say nothing.
    m = load()
    m["Items"].add(StubItem(0x40005001, "a taming order deed",
                            ["Creature Type: Hind", "Filled: 23/60"],
                            m["Player"].Backpack.Serial))
    keeper = StubMobile(0x50200, "a hind", 0xED, ["(tame)"])
    m["Mobiles"].add(keeper)
    m["Player"].Pets = [keeper]
    m["Player"].Mount = StubMobile(0x50201, "a ridable llama", 0xDC, ["(tame)"])

    check("preflight passes", m["preflight"](), True)
    said = " | ".join(m["Misc"].messages)
    check("it names the version", m["SCRIPT_VERSION"] in said, True)
    check("it says how many animals are protected",
          "out of reach of this script" in said, True)
    check("it names the mount", "never be deeded" in said, True)
    check("and the deeds it will fill", "Filling (startup)" in said, True)


def test_preflight_survives_a_build_with_no_player_mount():
    """Player.Mount is used nowhere else in this repo, so it is unverified."""
    m = fresh()

    class NoMount(object):
        """A build where reading Player.Mount throws, wrapping one that works.

        A subclass cannot do this: StubPlayer.__init__ assigns self.Mount, and
        a read-only property on the subclass makes that assignment fail in the
        constructor rather than at the read being tested.
        """

        def __init__(self, real):
            self._real = real

        def __getattr__(self, name):
            if name == "Mount":
                raise AttributeError("this build has no Player.Mount")
            return getattr(self._real, name)

    m["Player"] = NoMount(StubPlayer())
    check("no Player.Mount means serial 0, not a crash", m["mount_serial"](), 0)
    check("and preflight still passes", m["preflight"](), True)


def main():
    tests = [value for key, value in sorted(globals().items())
             if key.startswith("test_") and callable(value)]
    for test in tests:
        print("")
        print("-- %s" % test.__name__)
        # ONE CRASH MUST NOT HIDE THE REST. A mutation run on 2026-11-09 put a
        # Player.Run into consider(); the stub has no such method, so the suite
        # died at the first behavioural test and never reached the structural
        # check that exists to catch exactly that. Exit code was still 1, which
        # is how it went unnoticed. A raising test is a failure and the suite
        # carries on.
        try:
            test()
        except Exception as problem:
            FAILURES.append("%s raised" % test.__name__)
            print("FAIL %-62s %s: %s"
                  % (test.__name__, type(problem).__name__, problem))

    print("")
    if FAILURES:
        print("%d FAILED:" % len(FAILURES))
        for label in FAILURES:
            print("   %s" % label)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
