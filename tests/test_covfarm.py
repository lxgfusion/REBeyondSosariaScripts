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


class Corpse(object):
    """From the real dump: a slasher of veils corpse, 0x2006, Amount 0x2E5."""

    def __init__(self, serial=0x40A7E26A, name="a slasher of veils corpse",
                 item_id=0x2006, amount=0x02E5):
        self.Serial = serial
        self.Name = name
        self.ItemID = item_id
        self.Amount = amount
        self.IsCorpse = True


GROUND = []


class StubItems(object):
    class Filter(object):
        def __init__(self):
            self.Enabled = False
            self.RangeMax = None
            self.OnGround = None

    def ApplyFilter(self, f):
        assert f.RangeMax is not None, "RangeMax must always be set"
        return list(GROUND)


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

    def CastMastery(self, name, *a, **k):
        self._record("mastery", name)

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
           "Items": StubItems(), "Gumps": None, "PathFinding": None, "Timer": None}
    exec(compile(src, SCRIPT, "exec"), env)
    return env


print("=" * 100)
print("1. DEATH CONFIRMATION - only a NEW corpse counts as a kill")
print("=" * 100)
m = load()
del MOBS[:]
del GROUND[:]

boss = Mob()
MOBS.append(boss)

check("no corpse -> not dead",
      m["find_new_corpse"]({}, boss.Body) is None, True)
check("monster is present", m["mobile_present"](boss.Serial), True)

GROUND.append(Corpse())
found = m["find_new_corpse"]({}, boss.Body)
check("its corpse IS the proof of death", found is not None, True)

print()
print("   -- the trap: last spawn's corpse must not count --")
del GROUND[:]
stale = Corpse(serial=0xDEAD0001)
GROUND.append(stale)
known = m["snapshot_corpses"]()          # taken at engage, as fight() does
check("the corpse already here is recorded", stale.Serial in known, True)
check("and is NOT read as a fresh kill",
      m["find_new_corpse"](known, boss.Body), None)

fresh = Corpse(serial=0xBEEF0002)
GROUND.append(fresh)
got = m["find_new_corpse"](known, boss.Body)
check("a NEW corpse alongside it does count",
      got is not None and got.Serial, 0xBEEF0002)

print()
print("   -- recognising it by name OR by body value --")
del GROUND[:]
GROUND.append(Corpse(name="a slasher of veils corpse", amount=0))
check("matched on the name alone",
      m["find_new_corpse"]({}, boss.Body) is not None, True)

del GROUND[:]
GROUND.append(Corpse(name="a corpse", amount=0x02E5))
check("matched on Amount = body value (survives a rename)",
      m["find_new_corpse"]({}, boss.Body) is not None, True)

del GROUND[:]
GROUND.append(Corpse(name="a dire wolf corpse", amount=0x0019))
check("somebody else's corpse is ignored",
      m["find_new_corpse"]({}, boss.Body), None)

del GROUND[:]
GROUND.append(Corpse(name="a slasher of veils corpse", item_id=0x1234))
GROUND[0].IsCorpse = False
check("a non-corpse item with the right name is ignored",
      m["find_new_corpse"]({}, boss.Body), None)

print()
print("   -- THE REPORTED BUG: vanishing is not dying --")
del MOBS[:]
del GROUND[:]
check("gone from the mobile list", m["mobile_present"](0x0003FE1B), False)
check("but with NO corpse, that is NOT a kill",
      m["find_new_corpse"]({}, 0x02E5), None)
print("        (it walked out of range or line of sight - the old code")
print("         called this dead and ended the fight with the boss alive)")

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
print("3. THE BAND - DISTANCE_MIN 4 .. DISTANCE_MAX 5, never further than 5")
print("=" * 100)
m = load()
mob = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob)

m["Player"].Position = Point(741, 477)           # on top of it, gap 0
del STEPS[:]
check("too close -> does not cast", m["hold_distance"](mob), False)
check("too close -> a step was taken", len(STEPS), 1)

m["Player"].Position = Point(745, 477)           # gap 4 = DISTANCE_MIN
del STEPS[:]
check("gap 4 is inside the band", m["hold_distance"](mob), True)
check("gap 4 -> no step", STEPS, [])

m["Player"].Position = Point(746, 477)           # gap 5 = DISTANCE_MAX
del STEPS[:]
check("gap 5 is inside the band", m["hold_distance"](mob), True)
check("gap 5 -> no jitter", STEPS, [])

m["Player"].Position = Point(747, 477)           # gap 6 - now TOO FAR
del STEPS[:]
check("gap 6 is OUTSIDE the band (within 5 means within 5)",
      m["hold_distance"](mob), False)
check("gap 6 -> steps back toward it", STEPS, ["West"])

m["Player"].Position = Point(760, 477)           # gap 19
del STEPS[:]
check("far away -> does not cast", m["hold_distance"](mob), False)
check("far away -> steps toward it", STEPS, ["West"])

for start, why in ((Point(741, 477), "from on top of it"),
                   (Point(765, 477), "from far away")):
    m["Player"].Position = start
    for _ in range(40):
        if m["hold_distance"](mob):
            break
    gap = m["Player"].DistanceTo(mob)
    check("converges into 4-5 %s" % why, 4 <= gap <= 5, True)

print()
print("=" * 100)
print("4. CONTINUOUS ENFORCEMENT - the standoff holds DURING a cast, not just")
print("   at the top of the loop")
print("=" * 100)


class Chaser(object):
    """Stub Misc whose Pause also walks the boss one tile toward the player."""

    def __init__(self, mob, player):
        self.mob = mob
        self.player = player
        self.ticks = 0

    def Pause(self, ms):
        self.ticks += 1
        if self.mob.Position.X < self.player.Position.X:
            self.mob.Position.X += 1
        elif self.mob.Position.X > self.player.Position.X:
            self.mob.Position.X -= 1

    def SendMessage(self, msg, color=0, wait=False):
        MSGS.append(msg)


m = load()
mob = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob)
m["Player"].Position = Point(746, 477)           # gap 5, in the band
chaser = Chaser(mob, m["Player"])
m["Misc"] = chaser

del STEPS[:]
m["kite_pause"](mob.Serial, 2000)
gap = m["Player"].DistanceTo(mob)
check("boss chased for the whole pause", chaser.ticks > 5, True)
check("kite_pause answered it - still in the band", 4 <= gap <= 5, True)
check("and it actually moved to do so", len(STEPS) > 0, True)

print()
print("   -- a plain wait would NOT have held (the bug being fixed) --")
m2 = load()
mob2 = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob2)
m2["Player"].Position = Point(746, 477)
chaser2 = Chaser(mob2, m2["Player"])
for _ in range(12):                              # same duration, no correction
    chaser2.Pause(150)
check("unmanaged wait lets it reach melee",
      m2["Player"].DistanceTo(mob2) < 4, True)

print()
print("   -- safe when the monster dies mid-wait --")
m3 = load()
mob3 = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob3)
m3["Player"].Position = Point(746, 477)
check("returns True while it lives", m3["enforce_distance"](mob3.Serial), True)
check("parks at the FAR edge, leaving slack for a chaser",
      m3["Player"].DistanceTo(mob3), 5)
del MOBS[:]
check("returns False once it is gone",
      m3["enforce_distance"](mob3.Serial), False)
check("kite_pause bails out too", m3["kite_pause"](mob3.Serial, 5000), False)

print()
print("   -- and when the player dies mid-wait --")
m4 = load()
mob4 = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob4)
m4["Player"].IsGhost = True
check("stops enforcing when dead", m4["enforce_distance"](mob4.Serial), False)
m4["Player"].IsGhost = False

print()
print("   -- the cursor wait kites instead of standing still --")
m5 = load()
mob5 = Mob(x=741, y=477)
del MOBS[:]
MOBS.append(mob5)
m5["Player"].Position = Point(746, 477)
m5["Misc"] = Chaser(mob5, m5["Player"])
TARGET.has = False
TARGET.opens = False                             # cursor never shows up
m5["wait_for_cursor"](mob5.Serial, 1500)
check("wait_for_cursor kept the band",
      4 <= m5["Player"].DistanceTo(mob5) <= 5, True)
TARGET.opens = True

print()
print("   -- a misconfigured band is refused at startup --")
m6 = load()
m6["DISTANCE_MIN"] = 5
m6["DISTANCE_MAX"] = 5
del MSGS[:]
check("MIN == MAX is rejected", m6["preflight"](), False)
check("and says why", any("jitters" in x for x in MSGS), True)

print()
print("=" * 100)
print("5. DIRECTIONS - X grows east, Y grows south")
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
print("6. CASTING")
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
check("attack cast from the Book of Masteries",
      CASTS, [("mastery", "Nether Blast")])
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
    # The attack spell is a MASTERY, so this is the call that must be
    # intercepted - patching Spells.Cast would silently miss it.
    CASTS.append(("mastery", name))
    JOURNAL.entries.append(Entry("That is too far away.", 100.0))


SPELLS.CastMastery = _range_cast
del CASTS[:]
res = m2["cast_at"](m2["SPELL_ATTACK"], mob)
check("out-of-range reply is detected", res, "range")
check("and it really did go through the mastery book",
      CASTS, [("mastery", "Nether Blast")])
SPELLS.CastMastery = StubSpells.CastMastery.__get__(SPELLS, StubSpells)

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
print("7. SAFETY")
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
print("8. JOURNAL CURSOR - never wipes, never replays")
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
