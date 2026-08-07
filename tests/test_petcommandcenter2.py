"""
Offline tests for petcommandcenter2.py.

    python tests/test_petcommandcenter2.py

Execs the REAL script with stub Razor globals and calls the real functions, so
there is no copied logic to drift. No Razor runtime needed.

Carries a regression case for each thing that was wrong in the v1 script:
  * config validation NAMES and skips a bad entry instead of dropping it
  * the journal timestamp cursor fires once per phrase, ignores pre-startup
    lines, is case-insensitive, and refuses another player's speech
  * deploy only issues the guard command when something was actually released
  * shrink survives a leaked target cursor, and leaves the cursor clean when
    the tool never opens one
  * SETUP_MODE emits a block that is valid Python AND passes the real validator
"""
import ast
import re
import sys

import os
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts",
                      "petcommandcenter2.py")
NL = chr(10)

FAILURES = []
MSGS = []
SAID = []
USED = []
TARGETED = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-52s got=%-30r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


class Entry(object):
    def __init__(self, text, name, ts):
        self.Text = text
        self.Name = name
        self.Timestamp = ts
        self.Type = "Regular"


class StubJournal(object):
    def __init__(self):
        self.entries = []

    def GetJournalEntry(self, after):
        return [e for e in self.entries if e.Timestamp > after]


class StubMisc(object):
    def SendMessage(self, msg, color=0, wait=False):
        MSGS.append(msg)

    def Pause(self, ms):
        pass


class Item(object):
    def __init__(self, serial, item_id, hue, name="", props=None):
        self.Serial = serial
        self.ItemID = item_id
        self.Hue = hue
        self.Name = name
        self._props = props or []


class Backpack(object):
    Serial = 0x41D40F58


class StubPlayer(object):
    Name = "Testchar"
    Serial = 0x0001A2B3
    Backpack = Backpack()

    class Position(object):
        X = 100
        Y = 100

    def ChatSay(self, a, b=None):
        SAID.append(b if b is not None else a)

    def HeadMessage(self, hue, msg):
        MSGS.append("HEAD:" + msg)


PACK = []


class StubItems(object):
    def FindByID(self, item_id, hue, container):
        for it in PACK:
            if it.ItemID == item_id and (hue == -1 or it.Hue == hue):
                return it
        return None

    def FindBySerial(self, s):
        for it in PACK:
            if it.Serial == s:
                return it
        return None

    def FindAllByID(self, item_id, hue, container, range=0):
        return [it for it in PACK
                if it.ItemID == item_id and (hue == -1 or it.Hue == hue)]

    def WaitForProps(self, item, delay):
        pass

    def GetPropStringList(self, item):
        return list(item._props)

    def UseItem(self, serial):
        USED.append(serial)

    def WaitForContents(self, bag, delay):
        return True


class Mob(object):
    def __init__(self, serial, name, x, y, tamed=1, bonded=0, body=0xC9,
                 props=None):
        self.Serial = serial
        self.Name = name
        self.tamed = tamed
        self.bonded = bonded
        self.Body = body
        self._props = props or []

        class P(object):
            pass
        self.Position = P()
        self.Position.X = x
        self.Position.Y = y


MOBS = []


class StubMobiles(object):
    class Filter(object):
        def __init__(self):
            self.Enabled = False
            self.RangeMax = None
            self.IsHuman = None
            self.IsGhost = None
            self.CheckIgnoreObject = None

    def ApplyFilter(self, f):
        assert f.RangeMax is not None, "RangeMax must always be set"
        out = list(MOBS)
        # Razor drops human-bodied mobiles when IsHuman is False.
        if getattr(f, "IsHuman", None) is False:
            out = [m for m in out if m.Body not in (0x190, 0x191)]
        return out

    def GetPropValue(self, mob, name):
        return getattr(mob, name, 0)

    def WaitForProps(self, mob, delay):
        pass

    def GetPropStringList(self, mob):
        return list(mob._props)


class StubTarget(object):
    def __init__(self):
        self.has = False
        self.prompt_queue = []
        self.cursor_opens = True

    def ClearQueue(self):
        pass

    def HasTarget(self, flag="Any"):
        return self.has

    def Cancel(self):
        self.has = False

    def WaitForTarget(self, delay, noshow=False):
        if self.cursor_opens:
            self.has = True
        return self.has

    def TargetExecute(self, serial):
        TARGETED.append(serial)
        self.has = False

    def PromptTarget(self, msg="", color=0):
        if not self.prompt_queue:
            return 0
        return self.prompt_queue.pop(0)


JOURNAL = StubJournal()
TARGET = StubTarget()


def load(**overrides):
    src = open(SCRIPT, encoding="utf-8").read()
    src = re.sub(r"^main\(\)\s*$", "", src, flags=re.M)
    env = {"__name__": "pcc_under_test", "Misc": StubMisc(),
           "Player": StubPlayer(), "Items": StubItems(),
           "Mobiles": StubMobiles(), "Journal": JOURNAL, "Target": TARGET,
           "PathFinding": None, "Gumps": None, "Timer": None}
    exec(compile(src, SCRIPT, "exec"), env)
    env.update(overrides)
    return env


print("=" * 100)
print("1. CONFIG VALIDATION - bad entries must be named and skipped, not "
      "silently dropped")
print("=" * 100)
m = load()
m["PET_STATUES"] = [
    {"enabled": True,  "label": "Good",      "id": 0x25AD, "hue": 0x0AB0},
    {"enabled": True,  "label": "No id"},
    {"enabled": False, "label": "Parked",    "id": 0x1111, "hue": None},
    {"enabled": True,  "label": "Dupe",      "id": 0x25AD, "hue": 0x0AB0},
    {"enabled": True,  "label": "Any hue",   "id": 0x4242, "hue": None},
    {"enabled": True,  "label": "Bad id",    "id": "0x99", "hue": None},
]
del MSGS[:]
got = m["valid_statues"]()
check("only usable entries survive", [e["label"] for e in got],
      ["Good", "Any hue"])
check("missing id reported", any("No id" in x and "no \"id\"" in x
                                 for x in MSGS), True)
check("identical entry explained, not silently dropped",
      any("Dupe" in x and "identical to" in x for x in MSGS), True)
check("bad id type reported", any("Bad id" in x for x in MSGS), True)
check("hue None means any hue", m["describe_hue"](None), "any hue")

print()
print("=" * 100)
print("2. JOURNAL CURSOR - fire once, ignore history, case-insensitive, "
      "own speech only")
print("=" * 100)
m = load()
JOURNAL.entries = [Entry("anal demons unite!", "Testchar", 10.0)]
m["start_listening"]()
check("pre-existing line is NOT replayed", m["poll_phrases"](), [])

JOURNAL.entries.append(Entry("ANAL Demons Unite!", "Testchar", 20.0))
check("new line fires (case-insensitive)", m["poll_phrases"](), ["deploy"])
check("same line does not fire twice", m["poll_phrases"](), [])

JOURNAL.entries.append(Entry("anal demons return!", "Someone Else", 30.0))
check("other player's speech ignored", m["poll_phrases"](), [])

JOURNAL.entries.append(Entry("hey anal demons return! now", "Testchar", 40.0))
check("recall matches mid-sentence", m["poll_phrases"](), ["recall"])

m2 = load()
m2["ONLY_MY_OWN_SPEECH"] = False
JOURNAL.entries = [Entry("anal demons unite!", "Someone Else", 50.0)]
m2["start_listening"]()
JOURNAL.entries.append(Entry("anal demons unite!", "Someone Else", 60.0))
check("ONLY_MY_OWN_SPEECH=False lets others trigger",
      m2["poll_phrases"](), ["deploy"])

print()
print("=" * 100)
print("3. DEPLOY")
print("=" * 100)
m = load()
del PACK[:]
PACK.extend([Item(0x900, 0x25AD, 0x0AB0, "Statue A"),
             Item(0x901, 0x984A, 0x0776, "Statue B")])
m["PET_STATUES"] = [
    {"enabled": True, "label": "A", "id": 0x25AD, "hue": 0x0AB0},
    {"enabled": True, "label": "B", "id": 0x984A, "hue": 0x0776},
    {"enabled": True, "label": "Missing", "id": 0xDEAD, "hue": None},
]
del MSGS[:]; del SAID[:]; del USED[:]
n = m["deploy"](m["valid_statues"]())
check("released the two present statues", n, 2)
check("used both serials", USED, [0x900, 0x901])
check("emote said once per statue", SAID.count("[e fart"), 2)
check("guard command said once", SAID.count("all guard me"), 1)
check("missing statue named in log",
      any("Missing" in x and "Not in your pack" in x for x in MSGS), True)

print()
print("   -- no statues at all --")
del PACK[:]
del MSGS[:]; del SAID[:]; del USED[:]
n = m["deploy"](m["valid_statues"]())
check("nothing released", n, 0)
check("does NOT issue guard command", SAID.count("all guard me"), 0)
check("tells the user how to fix it",
      any("SETUP_MODE" in x for x in MSGS), True)

print()
print("=" * 100)
print("4. RECALL / SHRINK")
print("=" * 100)
m = load()
del PACK[:]
PACK.append(Item(0x950, 0x1374, 0x0000, "shrink tool"))
del MOBS[:]
MOBS.extend([Mob(0xB01, "Rex", 110, 100),          # 10 away
             Mob(0xB02, "Fluffy", 102, 100),       # 2 away  - closest
             Mob(0xB03, "Spot", 105, 100)])        # 5 away
del MSGS[:]; del TARGETED[:]
TARGET.has = False
n = m["recall"]()
check("shrank all three", n, 3)
check("closest first", TARGETED, [0xB02, 0xB03, 0xB01])

print()
print("   -- SHRINK_MAX_PETS caps it --")
m["SHRINK_MAX_PETS"] = 2
del TARGETED[:]
m["recall"]()
check("respects the cap", TARGETED, [0xB02, 0xB03])

print()
print("   -- name allowlist --")
m["SHRINK_MAX_PETS"] = 5
m["SHRINK_ONLY_THESE_NAMES"] = ["fluffy"]
del TARGETED[:]
m["recall"]()
check("only the named pet is shrunk", TARGETED, [0xB02])

print()
print("   -- no shrink tool --")
m["SHRINK_ONLY_THESE_NAMES"] = []
del PACK[:]
del MSGS[:]; del TARGETED[:]
n = m["recall"]()
check("shrinks nothing", n, 0)
check("nothing targeted", TARGETED, [])
check("says the tool is missing",
      any("Shrink tool not found" in x for x in MSGS), True)

print()
print("   -- a leaked cursor must not eat the target --")
m = load()
del PACK[:]
PACK.append(Item(0x950, 0x1374, 0x0000, "shrink tool"))
del MOBS[:]
MOBS.append(Mob(0xB01, "Rex", 101, 100))
del TARGETED[:]
TARGET.has = True                     # stale cursor left open by something else
m["recall"]()
check("stale cursor cleared, shrink still lands", TARGETED, [0xB01])

print()
print("   -- tool never opens a cursor --")
del TARGETED[:]; del MSGS[:]
TARGET.cursor_opens = False
TARGET.has = False
n = m["recall"]()
check("nothing targeted when no cursor", TARGETED, [])
check("reports the missing cursor",
      any("did not ask for a target" in x for x in MSGS), True)
check("cursor left clean for the next action", TARGET.HasTarget(), False)
TARGET.cursor_opens = True

print()
print("=" * 100)
print("5. SETUP MODE - the generated block must be valid, re-loadable config")
print("=" * 100)
m = load()
del PACK[:]
PACK.extend([Item(0x900, 0x25AD, 0x0AB0, "Fire Steed Statue"),
             Item(0x901, 0x984A, 0x0776, 'A "Quoted" Statue'),
             Item(0x950, 0x1374, 0x0000, "shrink tool")])
TARGET.prompt_queue = [0x900, 0x901, 0, 0x950]   # two statues, ESC, then tool
del MSGS[:]
m["run_setup"]()
block = "\n".join(m["_setup_lines"])
print(block)

code = "\n".join(l for l in m["_setup_lines"]
                 if l.startswith(("PET_STATUES", "    {", "]",
                                  "SHRINK_TOOL_ID", "SHRINK_TOOL_HUE")))
ns = {}
try:
    exec(compile(code, "<generated>", "exec"), ns)
    ok = True
except Exception as exc:
    ok = False
    print("EXEC FAILED: %s" % exc)
check("generated block is valid Python", ok, True)
check("two statues captured", len(ns.get("PET_STATUES", [])), 2)
check("ids read off the items",
      [e["id"] for e in ns.get("PET_STATUES", [])], [0x25AD, 0x984A])
check("hues read off the items",
      [e["hue"] for e in ns.get("PET_STATUES", [])], [0x0AB0, 0x0776])
check("shrink tool captured", ns.get("SHRINK_TOOL_ID"), 0x1374)
check("quotes in a pet name do not break the block",
      ns["PET_STATUES"][1]["label"], "A 'Quoted' Statue")

# The generated block must survive being fed back into the real validator.
m3 = load()
m3["PET_STATUES"] = ns["PET_STATUES"]
check("generated block passes the real validator",
      [e["label"] for e in m3["valid_statues"]()],
      ["Fire Steed Statue", "A 'Quoted' Statue"])


print()
print("=" * 100)
print("6. SHRUNKEN PETS - all share ItemID 0x2107 hue 0x0000 (from a real")
print("   Enhanced Item Inspector dump). Regression: one went missing.")
print("=" * 100)

# Verbatim shape of the real tooltip, fields concatenated as they arrive.
def shrunk(serial, pet_name, breed="TownInvader"):
    return Item(serial, 0x2107, 0x0000, "a shrunken pet", [
        "A Shrunken Pet", "Blessed", "Weight: 10 Stones",
        "Name: %sBreed: %sGender: Male" % (pet_name, breed),
        "Owner: Fred Kruger",
    ])

m = load()
del PACK[:]
PACK.extend([shrunk(0x1, "Mike Hawk"), shrunk(0x2, "Rex"), shrunk(0x3, "Spot")])

check("pet name parsed out of concatenated tooltip, casing kept",
      m["pet_label"](PACK[0]), "Mike Hawk")
check("breed does not bleed into the name",
      m["tooltip_field"](m["item_tooltip_raw"](PACK[0]), "breed"),
      "Town Invader")

m["PET_STATUES"] = [{"enabled": True, "label": "Shrunken pets", "id": 0x2107}]
entries = m["valid_statues"]()
del USED[:]
n = m["deploy"](entries)
check("ONE entry releases ALL identical shrunken pets", n, 3)
check("every serial used", sorted(USED), [0x1, 0x2, 0x3])

print()
print("   -- identical entries are no longer dropped as duplicates --")
m["PET_STATUES"] = [
    {"enabled": True, "label": "Mike Hawk", "id": 0x2107, "name": "Mike Hawk"},
    {"enabled": True, "label": "Rex", "id": 0x2107, "name": "Rex"},
]
del MSGS[:]
kept = m["valid_statues"]()
check("name-qualified entries both survive",
      [e["label"] for e in kept], ["Mike Hawk", "Rex"])
del USED[:]
n = m["deploy"](kept)
check("each releases only its own pet", n, 2)
check("correct serials, not the same one twice", sorted(USED), [0x1, 0x2])

print()
print("   -- a pet is never released twice by two entries --")
m["PET_STATUES"] = [
    {"enabled": True, "label": "Mike Hawk", "id": 0x2107, "name": "Mike Hawk"},
    {"enabled": True, "label": "All the rest", "id": 0x2107},
]
del USED[:]
n = m["deploy"](m["valid_statues"]())
check("three pets, three releases, no double-use", n, 3)
check("no serial used twice", len(set(USED)), 3)

print()
print("   -- count caps an entry --")
m["PET_STATUES"] = [{"enabled": True, "label": "Two only", "id": 0x2107,
                     "count": 2}]
del USED[:]
n = m["deploy"](m["valid_statues"]())
check("count respected", n, 2)

print()
print("   -- statues and shrunken pets together --")
del PACK[:]
PACK.extend([Item(0x900, 0x25AD, 0x0AB0, "Statue A"),
             shrunk(0x1, "Mike Hawk"), shrunk(0x2, "Rex")])
m["PET_STATUES"] = [
    {"enabled": True, "label": "Pet 1", "id": 0x25AD, "hue": 0x0AB0},
    {"enabled": True, "label": "Shrunken pets", "id": 0x2107},
]
del USED[:]
n = m["deploy"](m["valid_statues"]())
check("mixed pack fully deployed", n, 3)
check("statue and both shrunken pets", sorted(USED), [0x1, 0x2, 0x900])

print()
print("   -- SETUP_MODE emits the name-qualified form for identical items --")
m = load()
del PACK[:]
PACK.extend([shrunk(0x1, "Mike Hawk"), shrunk(0x2, "Rex"),
             Item(0x950, 0x1374, 0x0000, "shrink tool")])
TARGET.prompt_queue = [0x1, 0x2, 0, 0x950]
m["run_setup"]()
block = NL.join(m["_setup_lines"])
print(block)
code = NL.join(l for l in m["_setup_lines"]
                 if l.startswith(("PET_STATUES", "    {", "]",
                                  "SHRINK_TOOL_ID", "SHRINK_TOOL_HUE")))
ns = {}
exec(compile(code, "<generated>", "exec"), ns)
check("setup emitted two distinct entries", len(ns["PET_STATUES"]), 2)
check("labels keep their capitalisation",
      [e["label"] for e in ns["PET_STATUES"]], ["Mike Hawk", "Rex"])
check("both carry a name filter",
      all(e.get("name") for e in ns["PET_STATUES"]), True)

m4 = load()
m4["PET_STATUES"] = ns["PET_STATUES"]
del PACK[:]
PACK.extend([shrunk(0x1, "Mike Hawk"), shrunk(0x2, "Rex")])
del USED[:]
n = m4["deploy"](m4["valid_statues"]())
check("generated config deploys BOTH pets", n, 2)
check("no pet missed", sorted(USED), [0x1, 0x2])


print()
print("=" * 100)
print("7. HUMAN-BODIED PETS - Bioengineered pet, body 0x0191, status is the")
print("   bare tooltip line \"(bonded)\" (real Enhanced Mobile Inspector dump)")
print("=" * 100)

# Verbatim from the dump: no numeric bonded/tamed, human body.
MIKE = Mob(0x0001A75A, "Mike Hawk", 101, 100, tamed=0, bonded=0, body=0x0191,
           props=["Undead Town Invader",
                  "Bioengineered PetGeneration: 1Level: 81Gender: MalePow",
                  "guarding", "(bonded)"])
DOG = Mob(0xB01, "Rex", 103, 100, tamed=1, bonded=0, body=0xD9)
STRANGER = Mob(0xC01, "Random Player", 102, 100, tamed=0, bonded=0, body=0x190,
               props=["a wandering healer"])

m = load()
check("bare '(bonded)' tooltip is recognised", m["looks_like_pet"](MIKE), True)
check("numeric tamed still recognised", m["looks_like_pet"](DOG), True)
check("a plain human is NOT a pet", m["looks_like_pet"](STRANGER), False)

del MOBS[:]
MOBS.extend([MIKE, DOG, STRANGER])
del PACK[:]
PACK.append(Item(0x950, 0x1374, 0x0000, "shrink tool"))
del TARGETED[:]
TARGET.has = False
n = m["recall"]()
check("human-bodied pet IS shrunk", 0x0001A75A in TARGETED, True)
check("shrank both pets, not the stranger", n, 2)
check("stranger never targeted", 0xC01 in TARGETED, False)

print()
print("   -- regression: the old IsHuman=False filter dropped it --")
m2 = load()
m2["SHRINK_INCLUDE_HUMAN_BODIES"] = False
del TARGETED[:]
m2["recall"]()
check("with human bodies excluded, Mike Hawk is missed (the old bug)",
      0x0001A75A in TARGETED, False)

print()
print("   -- the player is never targeted --")
m3 = load()
ME = Mob(StubPlayer.Serial if hasattr(StubPlayer, "Serial") else 0xDEAD,
         "Testchar", 100, 100, tamed=0, bonded=1, body=0x190)
del MOBS[:]
MOBS.extend([ME, DOG])
del TARGETED[:]
m3["recall"]()
check("self excluded from shrink", ME.Serial in TARGETED, False)

print()
print("=" * 100)
if FAILURES:
    print("%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("all checks passed")
