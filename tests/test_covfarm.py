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
SAID = []
MOVES = []


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


PACK = []


class Bag(object):
    """A container in the backpack. `Contains` is the only window into one."""
    def __init__(self, serial, item_id, hue, name="bag"):
        self.Serial, self.ItemID, self.Hue, self.Name = serial, item_id, hue, name
        self.Contains = []
        self.Container = 0x41D40F58


class PackItem(object):
    def __init__(self, serial, item_id, hue, name, props=None):
        self.Serial, self.ItemID, self.Hue, self.Name = serial, item_id, hue, name
        self.Container = 0x41D40F58          # the backpack, as on this shard
        self.Props = props or []
        self.Contains = []


class Backpack(object):
    Serial = 0x41D40F58

    @property
    def Contains(self):
        return list(PACK)


class StubPlayer(object):
    Name = "Testchar"
    Serial = 0x0001A2B3
    IsGhost = False
    Hits = 100
    HitsMax = 100
    Mana = 100
    ManaMax = 100

    Backpack = Backpack()

    def __init__(self):
        self.Position = Point(741, 477, -17)

    def DistanceTo(self, mob):
        return max(abs(self.Position.X - mob.Position.X),
                   abs(self.Position.Y - mob.Position.Y))

    def ChatSay(self, a, b=None):
        SAID.append(b if b is not None else a)

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
                 item_id=0x2006, amount=0x02E5, x=741, y=477, z=-17):
        self.Serial = serial
        self.Name = name
        self.ItemID = item_id
        self.Amount = amount
        self.IsCorpse = True
        self.Position = Point(x, y, z)


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

    def FindBySerial(self, serial):
        for it in GROUND:
            if it.Serial == serial:
                return it
        for it in PACK:
            if it.Serial == serial:
                return it
        for it in PACK:
            for sub in getattr(it, "Contains", []):
                if sub.Serial == serial:
                    return sub
        return None

    def WaitForContents(self, bag, delay):
        return True

    def WaitForProps(self, item, delay):
        return True

    def GetPropStringList(self, item):
        return list(getattr(item, "Props", []) or [])

    def Move(self, source, dest, amount):
        MOVES.append((source.Serial, dest.Serial))
        if source in PACK:
            PACK.remove(source)
        dest.Contains.append(source)
        source.Container = dest.Serial


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


class StubPathFinding(object):
    """Walks the player straight to the tile, as a working pathfinder would."""

    class Route(object):
        def __init__(self):
            self.X = 0
            self.Y = 0
            self.MaxRetry = 0
            self.StopIfStuck = False
            self.IgnoreMobile = False
            self.UseResync = False
            self.DebugMessage = False

    def __init__(self):
        self.player = None

    def Go(self, route):
        if self.player is not None:
            self.player.Position.X = route.X
            self.player.Position.Y = route.Y
        return True


JOURNAL = StubJournal()
TARGET = StubTarget()
SPELLS = StubSpells()


def load():
    src = open(SCRIPT, encoding="utf-8").read()
    src = re.sub(r"^main\(\)\s*$", "", src, flags=re.M)
    env = {"__name__": "covfarm_under_test", "Misc": StubMisc(),
           "Player": StubPlayer(), "Mobiles": StubMobiles(),
           "Journal": JOURNAL, "Target": TARGET, "Spells": SPELLS,
           "Items": StubItems(),  "Gumps": None, "PathFinding": StubPathFinding(), "Timer": None}
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
print("9. LOOTING - walk to the corpse, say the grab command, confirm it went")
print("=" * 100)

m = load()
m["PathFinding"].player = m["Player"]
del GROUND[:]
corpse = Corpse(x=741, y=477)
GROUND.append(corpse)
m["Player"].Position = Point(720, 460)           # well away from it


class Grabber(object):
    """Player whose grab command removes the corpse after `after` says."""

    def __init__(self, player, after=1):
        self.player = player
        self.after = after
        self.says = 0

    def ChatSay(self, a, b=None):
        text = b if b is not None else a
        SAID.append(text)
        self.says += 1
        if self.says >= self.after and corpse in GROUND:
            GROUND.remove(corpse)

    def __getattr__(self, name):
        return getattr(self.player, name)


del SAID[:]
grabber = Grabber(m["Player"])
m["Player"] = grabber
m["PathFinding"].player = grabber.player

ok = m["loot_corpse"](corpse)
check("loot reported success", ok, True)
check("walked to within LOOT_DISTANCE of the corpse",
      max(abs(grabber.player.Position.X - 741),
          abs(grabber.player.Position.Y - 477)) <= m["LOOT_DISTANCE"], True)
check("said the grab command", SAID, ["[grab"])
check("corpse is gone", m["Items"].FindBySerial(corpse.Serial), None)

print()
print("   -- a corpse that will not empty is reported, not hung on --")
m2 = load()
m2["PathFinding"].player = m2["Player"]
del GROUND[:]
stubborn = Corpse(serial=0xAAAA, x=741, y=477)
GROUND.append(stubborn)
m2["Player"].Position = Point(741, 477)
del SAID[:]; del MSGS[:]
ok = m2["loot_corpse"](stubborn)
check("reports failure rather than looping forever", ok, False)
check("tried exactly LOOT_RETRIES times", len(SAID), m2["LOOT_RETRIES"])
check("explains why", any("not on your grab list" in x for x in MSGS), True)

print()
print("   -- LOOT_CORPSE off skips the whole thing --")
m3 = load()
m3["LOOT_CORPSE"] = False
del SAID[:]
check("does nothing when disabled", m3["loot_corpse"](corpse), False)
check("says nothing", SAID, [])

print()
print("   -- THE REPORTED BUG: the command must ALWAYS be said --")
m4 = load()
m4["PathFinding"].player = m4["Player"]
del GROUND[:]                                    # serial lookup finds nothing
ghost_corpse = Corpse(serial=0xBBBB, x=741, y=477)
m4["Player"].Position = Point(741, 477)
del SAID[:]
ok = m4["loot_corpse"](ghost_corpse)
check("still says the grab command, lookup miss or not", SAID, ["[grab"])
check("and reports the corpse gone afterwards", ok, True)
print("        (it used to check first and return without speaking - which")
print("         is why [grab was never said)")

print()
print("   -- falling short of the corpse still says it --")
m4b = load()
del GROUND[:]
far = Corpse(serial=0xCCCC, x=900, y=900)        # unreachable, no pathfinder
GROUND.append(far)
m4b["Player"].Position = Point(741, 477)
m4b["LOOT_APPROACH_TIMEOUT"] = 1
del SAID[:]; del MSGS[:]
m4b["loot_corpse"](far)
check("grab said from wherever we got to", "[grab" in SAID, True)
check("and it says it fell short",
      any("anyway" in x for x in MSGS), True)

print()
print("   -- returning to camp --")
m5 = load()
m5["PathFinding"].player = m5["Player"]
m5["_camp"] = (700, 700)
m5["Player"].Position = Point(741, 477)
ok = m5["return_to_camp"]()
check("walked back to camp", ok, True)
check("within CAMP_TOLERANCE of the start",
      m5["distance_to_point"](700, 700) <= m5["CAMP_TOLERANCE"], True)

print()
print("   -- already at camp: no pointless walking --")
m6 = load()
m6["PathFinding"].player = m6["Player"]
m6["_camp"] = (741, 477)
m6["Player"].Position = Point(742, 477)          # 1 tile, inside tolerance
del MSGS[:]
check("counts as home", m6["return_to_camp"](), True)
check("did not announce a walk",
      any("Returning to camp" in x for x in MSGS), False)

print()
print("   -- RETURN_TO_CAMP off leaves you where you are --")
m7 = load()
m7["RETURN_TO_CAMP"] = False
m7["_camp"] = (700, 700)
m7["Player"].Position = Point(741, 477)
check("skipped", m7["return_to_camp"](), True)
check("did not move", (m7["Player"].Position.X, m7["Player"].Position.Y),
      (741, 477))



print()
print("=" * 100)
print("TRASHING - the reward chests go to the bag, and NOTHING else does")
print("=" * 100)


def fresh_pack(module):
    del PACK[:]
    del MOVES[:]
    bag = Bag(module["TRASH_BAG_SERIAL"], module["TRASH_BAG_ID"],
              module["TRASH_BAG_HUE"], "Trash Bag (Deletes Items In 30 Seconds)")
    PACK.append(bag)
    return bag


# The three reward-chest variants seen in game, all Level 1. Three different
# graphics AND three different hues - which is why the sweep no longer pins the
# graphic. The first version listed 0x09AB only: that one was binned and these
# other two were left sitting in the pack.
CHEST_VARIANTS = [
    (0x09AB, 0x047E),
    (0x0E7C, 0x089F),
    (0x0E40, 0x0979),
]


def chest(serial, hue=0x047E, level=1, item_id=0x09AB, with_level=True):
    """A lootable reward chest, as the Item Inspector showed it."""
    props = ["A Glimmering Chest Of Belongings", "Weight: 18 Stones",
             "Contents: 5/125 Items, 17 Stones"]
    if with_level:
        props.append("Level %d" % level)
    return PackItem(serial, item_id, hue, "a glimmering chest of belongings",
                    props)


m8 = load()
bag = fresh_pack(m8)
PACK.append(chest(0x40988235))
check("the bag is found", m8["find_trash_bag"]().Serial,
      m8["TRASH_BAG_SERIAL"])
check("one chest binned", m8["trash_junk"](), 1)
check("it went to the bag", MOVES, [(0x40988235, m8["TRASH_BAG_SERIAL"])])
check("and it is in the bag now", [i.Serial for i in bag.Contains],
      [0x40988235])

print()
print("   -- levels 1 to 5 all go, whatever hue they carry --")
m9 = load()
bag = fresh_pack(m9)
for i, lvl in enumerate([1, 2, 3, 4, 5]):
    # Deliberately different hues AND graphics: only Level 1 was ever
    # inspected, so keying on either would silently skip the rest.
    PACK.append(chest(0x40990000 + i, hue=0x047E + i * 0x10, level=lvl,
                      item_id=0x0E70 + i))
check("all five binned", m9["trash_junk"](), 5)
check("five moves", len(MOVES), 5)
check("pack has only the bag left", [i.Serial for i in PACK],
      [m9["TRASH_BAG_SERIAL"]])

print()
print("   -- THE DANGEROUS ONE: the order runner's storage chests --")
print("      same name, one shares the hue, different graphic (0x0E41)")
m10 = load()
bag = fresh_pack(m10)
storage_a = PackItem(0x400CEF90, 0x0E41, 0x089F,
                     "a glimmering chest of belongings")
storage_b = PackItem(0x400463FB, 0x0E41, 0x047E,
                     "a glimmering chest of belongings")
PACK.extend([storage_a, storage_b])
check("neither storage chest is binned", m10["trash_junk"](), 0)
check("nothing moved at all", MOVES, [])
check("both still in the pack",
      sorted(i.Serial for i in PACK if i.ItemID == 0x0E41),
      sorted([0x400463FB, 0x400CEF90]))

print()
print("   -- THE REPORTED MISS: all three real variants must go --")
m18 = load()
bag = fresh_pack(m18)
for i, (gid, hue) in enumerate(CHEST_VARIANTS):
    PACK.append(chest(0x45550000 + i, hue=hue, item_id=gid))
check("all three binned", m18["trash_junk"](), 3)
check("none left in the pack",
      [i.Serial for i in PACK], [m18["TRASH_BAG_SERIAL"]])

print()
print("   -- 0x0E41 IS ALSO A REWARD CHEST, and must be binned --")
print("      it was on TRASH_NEVER_IDS to protect the storage chests, which")
print("      blocked a real drop: serial 0x4031D6E1, hue 0x08A5, Level 1")
m19 = load()
bag = fresh_pack(m19)
PACK.append(chest(0x4031D6E1, hue=0x08A5, item_id=0x0E41))
check("no graphic is excluded any more", m19["TRASH_NEVER_IDS"], [])
check("the 0x0E41 reward chest is binned", m19["trash_junk"](), 1)
check("it went to the bag", MOVES, [(0x4031D6E1, m19["TRASH_BAG_SERIAL"])])

print()
print("   -- and the storage chests are STILL safe, by serial --")
print("      which is now the only lock besides being backpack-only")
m19b = load()
bag = fresh_pack(m19b)
for serial in m19b["TRASH_NEVER_SERIALS"]:
    PACK.append(PackItem(serial, 0x0E41, 0x089F,
                         "a glimmering chest of belongings",
                         ["A Glimmering Chest Of Belongings", "Level 1"]))
check("both storage chests refused", m19b["trash_junk"](), 0)
check("nothing moved", MOVES, [])
check("both still in the pack",
      sorted(i.Serial for i in PACK if i.ItemID == 0x0E41),
      sorted(m19b["TRASH_NEVER_SERIALS"]))

print()
print("   -- THE NAME ALONE DECIDES: no 'Level N' needed --")
m20 = load()
bag = fresh_pack(m20)
PACK.append(chest(0x47770001, with_level=False))
check("binned on the name alone", m20["trash_junk"](), 1)
check("it went to the bag", MOVES, [(0x47770001, m20["TRASH_BAG_SERIAL"])])

print()
print("   -- Level 5, a fourth hue, still just goes --")
m21 = load()
bag = fresh_pack(m21)
# Inspected 2026-08-11: 0x0E40 hue 0x04F2, Level 5, Contents 16/125.
PACK.append(chest(0x4030A3C2, hue=0x04F2, level=5, item_id=0x0E40))
check("binned", m21["trash_junk"](), 1)
check("it went to the bag", MOVES, [(0x4030A3C2, m21["TRASH_BAG_SERIAL"])])

print()
print("   -- require_level True still gates, for whoever turns it back on --")
m22 = load()
bag = fresh_pack(m22)
del MSGS[:]
for e in m22["TRASH_ITEMS"]:
    e["require_level"] = True
PACK.append(chest(0x48880001, with_level=False))
PACK.append(chest(0x48880002, hue=0x089F, item_id=0x0E7C))
check("the levelless one is held back", m22["trash_junk"](), 1)
check("and it was the one WITH a level",
      MOVES, [(0x48880002, m22["TRASH_BAG_SERIAL"])])
check("and it said why", any("no 'Level N'" in x for x in MSGS), True)

print()
print("   -- THE STALE SNAPSHOT: the pack must be RE-OPENED, not just read --")
print("      Player.Backpack.Contains is a snapshot taken when the container")
print("      was opened. It does not update as things drop in, so the sweep")
print("      kept reading the pre-kill contents and found nothing to do.")


class StaleBackpack(object):
    """Contains only reflects reality after UseItem re-opens the container."""
    Serial = 0x41D40F58

    def __init__(self):
        self.opened = 0
        self.visible = []          # what a read returns right now

    def reopen(self):
        self.opened += 1
        self.visible = list(PACK)  # NOW it sees what is really there

    @property
    def Contains(self):
        return list(self.visible)


m23 = load()
stale = StaleBackpack()
del PACK[:]
del MOVES[:]
bag = Bag(m23["TRASH_BAG_SERIAL"], m23["TRASH_BAG_ID"], m23["TRASH_BAG_HUE"],
          "Trash Bag (Deletes Items In 30 Seconds)")
PACK.append(bag)
stale.reopen()                      # the pack as it was BEFORE the kill

# The kill drops a chest in. The snapshot does not know about it yet.
PACK.append(chest(0x49990001))
check("the stale snapshot cannot see it",
      [i.Serial for i in stale.Contains], [bag.Serial])

m23["Player"].Backpack = stale


def use_item(serial):
    if serial == stale.Serial:
        stale.reopen()


m23["Items"].UseItem = use_item
m23["Items"].FindBySerial = lambda s: stale if s == stale.Serial else None

check("it is binned anyway, because the pack is re-opened",
      m23["trash_junk"](), 1)
check("the pack WAS re-opened", stale.opened > 1, True)
check("it went to the bag", MOVES, [(0x49990001, m23["TRASH_BAG_SERIAL"])])

print()
print("   -- the polled sweep is rate-limited, not run every tick --")
m24 = load()
fresh_pack(m24)
calls = []
m24["trash_junk"] = lambda announce=True: calls.append(announce) or 0
m24["_last_trash_sweep"][0] = 0.0
m24["maybe_trash"]()
check("the first tick sweeps", len(calls), 1)
check("and quietly", calls, [False])
m24["maybe_trash"]()
check("the very next tick does not", len(calls), 1)

print()
print("   -- the graphic alone is not enough either: the name must match --")
m11 = load()
bag = fresh_pack(m11)
impostor = PackItem(0x41110001, 0x09AB, 0x047E, "a rusty bucket")
PACK.append(impostor)
check("right graphic, wrong name -> left alone", m11["trash_junk"](), 0)
check("nothing moved", MOVES, [])

print()
print("   -- the blocklist holds even if a serial somehow matches --")
m12 = load()
bag = fresh_pack(m12)
# A storage serial wearing the lootable graphic AND name - belt and braces.
trap = PackItem(0x400CEF90, 0x09AB, 0x047E,
                "a glimmering chest of belongings")
PACK.append(trap)
check("TRASH_NEVER_SERIALS refuses it", m12["trash_junk"](), 0)
check("nothing moved", MOVES, [])

print()
print("   -- the bag never bins itself --")
m13 = load()
bag = fresh_pack(m13)
check("nothing to do", m13["trash_junk"](), 0)
check("the bag is untouched", MOVES, [])

print()
print("   -- ordinary loot is never touched --")
m14 = load()
bag = fresh_pack(m14)
PACK.append(PackItem(0x42220001, 0x0EED, 0x0000, "gold coins"))
PACK.append(PackItem(0x42220002, 0x1BF2, 0x096D, "43694 ingots"))
PACK.append(chest(0x42220003))
check("only the chest goes", m14["trash_junk"](), 1)
check("and it was the chest", MOVES, [(0x42220003, m14["TRASH_BAG_SERIAL"])])

print()
print("   -- a move the server refuses stops the sweep, it does not spin --")
m15 = load()
bag = fresh_pack(m15)
stuck = chest(0x43330001)
PACK.append(stuck)


def refuse(source, dest, amount):
    MOVES.append((source.Serial, dest.Serial))     # asked, but nothing happens


m15["Items"].Move = refuse
check("gives up rather than looping", m15["trash_junk"](), 0)
check("asked exactly once", len(MOVES), 1)

print()
print("   -- a missing bag bins nothing --")
m16 = load()
del PACK[:]
del MOVES[:]
check("no bag -> no moves", m16["trash_junk"](), 0)
check("nothing moved", MOVES, [])

print()
print("   -- TRASH_ENABLED off does nothing --")
m17 = load()
fresh_pack(m17)
PACK.append(chest(0x44440001))
m17["TRASH_ENABLED"] = False
check("disabled", m17["trash_junk"](), 0)
check("nothing moved", MOVES, [])

print()
print("   -- THE REAL BUG: a chest whose Name has not loaded yet --")
print("      Item.Name is empty until the properties are asked for, so a")
print("      name-only match skipped exactly the chest that just dropped.")
m25 = load()
bag = fresh_pack(m25)
unnamed = chest(0x4A0A0001, hue=0x08A5, item_id=0x0E41)
unnamed.Name = ""                      # not loaded yet - the tooltip has it
PACK.append(unnamed)
check("the Name really is empty", unnamed.Name, "")
check("the tooltip still names it",
      any("Glimmering" in p for p in unnamed.Props), True)
check("binned from the tooltip", m25["trash_junk"](), 1)
check("it went to the bag", MOVES, [(0x4A0A0001, m25["TRASH_BAG_SERIAL"])])

print()
print("   -- concatenated tooltip text still matches --")
m26 = load()
bag = fresh_pack(m26)
seam = chest(0x4B0B0001)
seam.Name = ""
seam.Props = ["A Glimmering Chest Of BelongingsWeight: 8 Stones",
              "Contents: 5/125 Items, 7 StonesLevel 1"]
PACK.append(seam)
check("binned through the seam", m26["trash_junk"](), 1)

print()
print("   -- ordinary unnamed loot is still left alone --")
m27 = load()
bag = fresh_pack(m27)
mystery = PackItem(0x4C0C0001, 0x0EED, 0x0000, "", ["a pile of gold coins"])
PACK.append(mystery)
check("not binned", m27["trash_junk"](), 0)
check("nothing moved", MOVES, [])

print()
print("   -- a sweep that bins nothing says what IS in the pack --")
m28 = load()
bag = fresh_pack(m28)
del MSGS[:]
PACK.append(PackItem(0x4D0D0001, 0x0EED, 0x0000, "gold coins"))
check("nothing binned", m28["trash_junk"](), 0)
check("but it reported the contents",
      any("nothing binned" in x for x in MSGS), True)
check("and listed the item",
      any("0x0EED" in x for x in MSGS), True)

print()
print("=" * 100)
print("CAMP - a fixed configured spot, not wherever the script started")
print("=" * 100)
m29 = load()
check("CAMP_POINT is the configured spot", m29["CAMP_POINT"], (750, 475))
m29["_camp"] = (m29["CAMP_POINT"][0], m29["CAMP_POINT"][1])
m29["Player"].Position = Point(750, 475)
check("already there -> no walk", m29["return_to_camp"](), True)

m30 = load()
m30["_camp"] = (750, 475)
m30["Player"].Position = Point(741, 477)
del MSGS[:]
m30["return_to_camp"]()
check("walks back to 750, 475",
      any("750, 475" in x for x in MSGS), True)

print()
print("=" * 100)
print("CHEST_ACTION - trash, hand to the master key, or leave alone")
print("=" * 100)


class Ctx(object):
    def __init__(self, entry):
        self.Entry = entry


def with_master_key(module, menu, key_id=None, key_hue=None):
    """Put a master key in the pack and stub its context menu."""
    key = PackItem(0x4F0F0001,
                   module["MASTER_KEY_ID"] if key_id is None else key_id,
                   module["MASTER_KEY_HUE"] if key_hue is None else key_hue,
                   "a master key")
    PACK.append(key)
    replied = []
    module["Misc"].WaitForContext = lambda i, d, sc=None: [Ctx(e) for e in menu]
    module["Misc"].ContextReply = lambda i, label: replied.append(label)
    return key, replied


m40 = load()
bag = fresh_pack(m40)
PACK.append(chest(0x50000001))
m40["CHEST_ACTION"] = "trash"
check("trash mode bins it", m40["handle_chests"](), 1)
check("it went to the bag", MOVES, [(0x50000001, m40["TRASH_BAG_SERIAL"])])

print()
print("   -- 'keep' touches nothing at all --")
m41 = load()
bag = fresh_pack(m41)
PACK.append(chest(0x50000002))
m41["CHEST_ACTION"] = "keep"
check("nothing handled", m41["handle_chests"](), 0)
check("nothing moved", MOVES, [])
check("the chest is still in the pack",
      0x50000002 in [i.Serial for i in PACK], True)

print()
print("   -- a misspelled mode destroys nothing --")
m42 = load()
bag = fresh_pack(m42)
PACK.append(chest(0x50000003))
m42["CHEST_ACTION"] = "trashh"
check("unknown mode does nothing", m42["handle_chests"](), 0)
check("nothing moved", MOVES, [])

print()
print("   -- 'key' hands them over, and nothing is deleted --")
m43 = load()
bag = fresh_pack(m43)
PACK.append(chest(0x50000004))
m43["CHEST_ACTION"] = "key"
key, replied = with_master_key(m43, ["Open", "Add", "Fill from backpack"])
# The key swallows them: emulate by emptying the chests from the pack.
original_reply = m43["Misc"].ContextReply
def swallow(item, label):
    original_reply(item, label)
    for it in list(PACK):
        if it.Name == "a glimmering chest of belongings":
            PACK.remove(it)
m43["Misc"].ContextReply = swallow
check("one chest handed over", m43["handle_chests"](), 1)
check("the exact menu label was sent", replied, ["Fill from backpack"])
check("nothing went to the trash bag", MOVES, [])

print()
print("   -- the fallback wording is accepted too --")
m44 = load()
bag = fresh_pack(m44)
PACK.append(chest(0x50000005))
m44["CHEST_ACTION"] = "key"
key, replied = with_master_key(m44, ["Open", "Add", "Refill from stock"])
orig = m44["Misc"].ContextReply
def swallow2(item, label):
    orig(item, label)
    for it in list(PACK):
        if it.Name == "a glimmering chest of belongings":
            PACK.remove(it)
m44["Misc"].ContextReply = swallow2
check("handed over", m44["handle_chests"](), 1)
check("sent the real label", replied, ["Refill from stock"])

print()
print("   -- an unrecognised menu presses NOTHING --")
m45 = load()
bag = fresh_pack(m45)
PACK.append(chest(0x50000006))
m45["CHEST_ACTION"] = "key"
key, replied = with_master_key(m45, ["Open", "Add", "Empty the key"])
check("nothing handed over", m45["handle_chests"](), 0)
check("and nothing was pressed", replied, [])
check("the chest is untouched",
      0x50000006 in [i.Serial for i in PACK], True)

print()
print("   -- CONTEXT_NEVER blocks a destructive entry on the fallback --")
m46 = load()
check("'Empty contents' is refused",
      m46["context_is_blocked"]("Empty contents"), True)
check("'Destroy all' is refused", m46["context_is_blocked"]("Destroy all"), True)
check("'Fill from backpack' is fine",
      m46["context_is_blocked"]("Fill from backpack"), False)
for label in m46["MASTER_KEY_CONTEXT"]:
    check("configured %r is usable" % label,
          m46["context_is_blocked"](label), False)

print()
print("   -- no master key: nothing is trashed as a consolation --")
m47 = load()
bag = fresh_pack(m47)
PACK.append(chest(0x50000007))
m47["CHEST_ACTION"] = "key"
m47["Misc"].WaitForContext = lambda i, d, sc=None: []
check("nothing handled", m47["handle_chests"](), 0)
check("and NOT quietly binned instead", MOVES, [])

print()
print("=" * 100)
if FAILURES:
    print("%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("all checks passed")
