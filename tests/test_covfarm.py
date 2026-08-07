"""
Offline tests for COVFarm.py.

    python tests/test_covfarm.py

Execs the REAL script with stub Razor globals and calls the real functions, so
there is no copied logic to drift. No Razor runtime needed.

The cases that matter most, all built from the Enhanced Mobile Inspector dump
of a live Slasher of Veils:

  * Hits 0/0 means the tooltip has not loaded, NOT that it died. The dump
    showed exactly that on a living monster, so reading it as death would end
    every fight on the first tick.
  * A matching body is not enough - the NAME decides what gets attacked.
  * The kiting band: step away when too close, follow when too far, cast only
    while inside it.
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "COVFarm.py")

FAILURES = []
MSGS = []
STEPS = []
CASTS = []
TARGETED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-54s got=%-24r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


class Point(object):
    def __init__(self, x, y, z=0):
        self.X = x
        self.Y = y
        self.Z = z


class Mob(object):
    """Defaults are the real dump: The Slasher of Veils, 0x02E5, noto 6."""

    def __init__(self, serial=0x0003FE1B, name="The Slasher of Veils",
                 body=0x02E5, x=741, y=477, z=-17, noto=6,
                 hits=0, hits_max=0):
        self.Serial = serial
        self.Name = name
        self.Body = body
        self.Notoriety = noto
        self.Hits = hits
        self.HitsMax = hits_max
        self.Position = Point(x, y, z)


MOBS = []


class StubMisc(object):
    def SendMessage(self, msg, color=0, wait=False):
        MSGS.append(msg)

    def Pause(self, ms):
        pass


class StubPlayer(object):
    Name = "Testchar"
    Serial = 0x0001A2B3
    IsGhost = False
    Hits = 100
    HitsMax = 100
    Mana = 100
    ManaMax = 100

    def __init__(self):
        self.Position = Point(741, 477, -17)

    def DistanceTo(self, mob):
        return max(abs(self.Position.X - mob.Position.X),
                   abs(self.Position.Y - mob.Position.Y))

    def Run(self, direction):
        STEPS.append(direction)
        # Actually move, so kiting converges instead of looping forever.
        dx, dy = DIRECTION_DELTA[direction]
        self.Position.X += dx
        self.Position.Y += dy
        return True


DIRECTION_DELTA = {
    "North": (0, -1), "Right": (1, -1), "East": (1, 0), "Down": (1, 1),
    "South": (0, 1), "Left": (-1, 1), "West": (-1, 0), "Up": (-1, -1),
}


class NetList(list):
    """Razor's Bodies is a .NET List<int> - it takes .Add, not append."""

    def Add(self, v):
        self.append(v)


class StubMobiles(object):
    class Filter(object):
        def __init__(self):
            self.Enabled = False
            self.RangeMax = None
            self.CheckIgnoreObject = None
            self.Bodies = NetList()

    def ApplyFilter(self, f):
        assert f.RangeMax is not None, "RangeMax must always be set"
        out = list(MOBS)
        if f.Bodies:
            out = [m for m in out if m.Body in f.Bodies]
        return out

    def FindBySerial(self, serial):
        for m in MOBS:
            if m.Serial == serial:
                return m
        return None

    def WaitForProps(self, mob, delay):
        pass


class Entry(object):
    def __init__(self, text, ts):
        self.Text = text
        self.Timestamp = ts
        self.Name = "System"


class StubJournal(object):
    def __init__(self):
        self.entries = []

    def GetJournalEntry(self, after):
        return [e for e in self.entries if e.Timestamp > after]


class StubTarget(object):
    def __init__(self):
        self.has = False
        self.opens = True

    def ClearQueue(self):
        pass

    def HasTarget(self, flag="Any"):
        return self.has

    def Cancel(self):
        self.has = False

    def WaitForTarget(self, delay, noshow=False):
        if self.opens:
            self.has = True
        return self.has

    def TargetExecute(self, *args):
        TARGETED.append(args)
        self.has = False


class StubSpells(object):
    def __init__(self):
        self.fail = False

    def _record(self, school, name):
        if self.fail:
            raise Exception("no such spell")
        CASTS.append((school, name))

    def Cast(self, name, *a, **k):
        self._record("auto", name)

    def CastMysticism(self, name, *a, **k):
        self._record("mysticism", name)

    def CastSpellweaving(self, name, *a, **k):
        self._record("spellweaving", name)


JOURNAL = StubJournal()
TARGET = StubTarget()
SPELLS = StubSpells()


def load():
    src = open(SCRIPT, encoding="utf-8").read()
    src = re.sub(r"^main\(\)\s*$", "", src, flags=re.M)
    env = {"__name__": "covfarm_under_test", "Misc": StubMisc(),
           "Player": StubPlayer(), "Mobiles": StubMobiles(),
           "Journal": JOURNAL, "Target": TARGET, "Spells": SPELLS,
           "Items": None, "Gumps": None, "PathFinding": None, "Timer": None}
    exec(compile(src, SCRIPT, "exec"), env)
    return env


print("=" * 100)
print("1. DEATH DETECTION - the Hits 0/0 trap from the real dump")
print("=" * 100)
m = load()
del MOBS[:]

alive_unloaded = Mob(hits=0, hits_max=0)        # verbatim from the dump
MOBS.append(alive_unloaded)
check("living monster with UNLOADED props (0/0) is NOT dead",
      m["is_dead"](alive_unloaded.Serial), False)

alive_unloaded.Hits, alive_unloaded.HitsMax = 45000, 60000
check("wounded monster is not dead", m["is_dead"](alive_unloaded.Serial), False)

alive_unloaded.Hits, alive_unloaded.HitsMax = 0, 60000
check("zero hits WITH a known max is dead",
      m["is_dead"](alive_unloaded.Serial), True)

del MOBS[:]
check("monster gone from the world is dead",
      m["is_dead"](0x0003FE1B), True)

print()
print("=" * 100)
print("2. TARGET IDENTIFICATION - the name decides, not the body")
print("=" * 100)
m = load()
del MOBS[:]
MOBS.append(Mob())
found = m["find_target"]()
check("the real Slasher is found", found is not None and found.Name,
      "The Slasher of Veils")

del MOBS[:]
MOBS.append(Mob(name="a summoned daemon"))       # right body, wrong name
check("right body but wrong name is IGNORED", m["find_target"](), None)

del MOBS[:]
MOBS.append(Mob(body=0x0190))                    # right name, wrong body
check("wrong body is not scanned (body is the pre-filter)",
      m["find_target"](), None)

del MOBS[:]
MOBS.append(Mob(noto=1))                         # innocent, not the boss
check("wrong notoriety is ignored", m["find_target"](), None)

del MOBS[:]
MOBS.append(Mob(name=None))
check("name that will not load is ignored", m["find_target"](), None)

print()
print("=" * 100)
print("3. KITING - hold the band, step away when close, follow when far")
print("=" * 100)
m = load()
mob = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob)

# KEEP_DISTANCE 5, slack 1 -> 4..6 is the band.
m["Player"].Position = Point(741, 477)           # on top of it, gap 0
del STEPS[:]
ok = m["hold_distance"](mob)
check("too close -> does not cast", ok, False)
check("too close -> a step was taken", len(STEPS), 1)

m["Player"].Position = Point(746, 477)           # gap 5, dead centre
del STEPS[:]
ok = m["hold_distance"](mob)
check("in the band -> casts", ok, True)
check("in the band -> does NOT jitter", STEPS, [])

m["Player"].Position = Point(745, 477)           # gap 4, edge of band
del STEPS[:]
check("gap 4 is inside the band", m["hold_distance"](mob), True)
check("gap 4 -> no step", STEPS, [])

m["Player"].Position = Point(747, 477)           # gap 6, other edge
del STEPS[:]
check("gap 6 is inside the band", m["hold_distance"](mob), True)

m["Player"].Position = Point(760, 477)           # gap 19, far away
del STEPS[:]
ok = m["hold_distance"](mob)
check("too far -> does not cast", ok, False)
check("too far -> steps toward it", STEPS, ["West"])

# Kite until settled, proving it converges rather than oscillating.
m["Player"].Position = Point(741, 477)
for _ in range(30):
    if m["hold_distance"](mob):
        break
gap = m["Player"].DistanceTo(mob)
check("kiting converges into the band", 4 <= gap <= 6, True)

print()
print("=" * 100)
print("4. DIRECTIONS - X grows east, Y grows south")
print("=" * 100)
m = load()
check("east", m["direction_name"](1, 0), "East")
check("west", m["direction_name"](-1, 0), "West")
check("south", m["direction_name"](0, 1), "South")
check("north", m["direction_name"](0, -1), "North")
check("south-east is Down", m["direction_name"](1, 1), "Down")
check("north-west is Up", m["direction_name"](-1, -1), "Up")

print()
print("=" * 100)
print("5. CASTING")
print("=" * 100)
m = load()
mob = Mob(x=741, y=477, z=-17)
del MOBS[:]
MOBS.append(mob)
m["Player"].Position = Point(746, 477)

del CASTS[:]; del TARGETED[:]
TARGET.has = False
TARGET.opens = True
res = m["cast_at"](m["SPELL_ATTACK"], mob)
check("attack spell cast", res, "ok")
check("cast by name", CASTS, [("auto", "Nether Blast")])
check("targeted the MOBILE by serial", TARGETED, [(0x0003FE1B,)])

del CASTS[:]; del TARGETED[:]
res = m["cast_at"](m["SPELL_OPENER"], mob)
check("opener cast", res, "ok")
check("targeted the LOCATION (x, y, z)", TARGETED, [(741, 477, -17)])

print()
print("   -- a leaked cursor must not eat the cast --")
del TARGETED[:]
TARGET.has = True
res = m["cast_at"](m["SPELL_ATTACK"], mob)
check("stale cursor cleared, cast still lands", TARGETED, [(0x0003FE1B,)])

print()
print("   -- no mana --")
m["Player"].Mana = 5
del CASTS[:]
res = m["cast_at"](m["SPELL_ATTACK"], mob)
check("refuses to cast below the mana floor", res, "mana")
check("nothing was cast", CASTS, [])
m["Player"].Mana = 100

print()
print("   -- server says out of range --")
JOURNAL.entries = []
m2 = load()
m2["reset_journal"]()
TARGET.has = False


def _range_cast(name, *a, **k):
    CASTS.append(("auto", name))
    JOURNAL.entries.append(Entry("That is too far away.", 100.0))


SPELLS.Cast = _range_cast
del CASTS[:]
res = m2["cast_at"](m2["SPELL_ATTACK"], mob)
check("out-of-range reply is detected", res, "range")
SPELLS.Cast = StubSpells.Cast.__get__(SPELLS, StubSpells)

print()
print("   -- an unknown spell name is reported, not swallowed --")
m3 = load()
SPELLS.fail = True
del MSGS[:]
res = m3["cast_at"](m3["SPELL_ATTACK"], mob)
check("unknown spell returns fail", res, "fail")
check("tells you to check the school",
      any("school" in x for x in MSGS), True)
SPELLS.fail = False

print()
print("=" * 100)
print("6. SAFETY")
print("=" * 100)
m = load()
m["Player"].Hits = 100
m["Player"].HitsMax = 100
check("full health does not flee", m["should_flee"](), False)
m["Player"].Hits = 39                      # below FLEE_AT_HITS_PERCENT 40
check("below the flee threshold does flee", m["should_flee"](), True)
m["Player"].Hits = 41
check("just above the threshold holds", m["should_flee"](), False)

m4 = load()
m4["FLEE_AT_HITS_PERCENT"] = 0
m4["Player"].Hits = 1
check("threshold 0 disables fleeing entirely", m4["should_flee"](), False)

print()
print("   -- fleeing actually opens the gap --")
m = load()
mob = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob)
m["Player"].Position = Point(742, 477)
m["flee_from"](mob)
check("ran to FLEE_DISTANCE", m["Player"].DistanceTo(mob) >= 15, True)

print()
print("=" * 100)
print("7. JOURNAL CURSOR - never wipes, never replays")
print("=" * 100)
m = load()
JOURNAL.entries = [Entry("old line", 10.0)]
m["reset_journal"]()
check("pre-existing lines are not replayed", m["new_lines"](), [])
JOURNAL.entries.append(Entry("The spell fizzles.", 20.0))
check("new line is read once", m["new_lines"](), ["the spell fizzles."])
check("and not a second time", m["new_lines"](), [])

print()
print("=" * 100)
if FAILURES:
    print("%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("all checks passed")
