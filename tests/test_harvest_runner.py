"""
Offline tests for harvest_runner.py's runebook parsing.
======================================================

    python tests/test_harvest_runner.py

Loads the real script with stub Razor globals and a fake account runebook whose
pages are the verbatim text captured from the Enhanced Gump Inspector, then
exercises the actual parsing and page-walking functions.

The thing under test is entry->button pairing. The shard could number entry
buttons per-page (page 2 starts again at 10) or continuously (page 2 starts at
19); the inspector shows text, not button ids, so both are tested and both must
work.
"""

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "harvest_runner.py")

FAILURES = []

CONTROLS = [1, 2, 3, 4, 5, 503, 504]

# --- verbatim from the Enhanced Gump Inspector ------------------------------

MINING_P1 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "Mining", "New Rune", "New Runebook", "Organize",
    "1. Mining (Malas)", "(1118, 1464, -95)",
    "2. Mining (Malas)", "(1122, 1456, -95)",
    "3. Mining (Malas)", "(1125, 1462, -95)",
    "4. Mining (Malas)", "(1127, 1469, -95)",
    "5. Mining (Malas)", "(1130, 1448, -95)",
    "6. Mining (Malas)", "(1134, 1458, -95)",
    "7. Mining (Malas)", "(1137, 1466, -95)",
    "8. Mining (Malas)", "(1143, 1458, -95)",
    "9. Mining (Malas)", "(1137, 1452, -95)",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/3",
]

MINING_P2 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "Mining", "New Rune", "New Runebook", "Organize",
    "10. Mining (Malas)", "(1150, 1460, -95)",
    "11. Mining (Malas)", "(1155, 1462, -95)",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 2/3",
]

MINING_P3 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "Mining", "New Rune", "New Runebook", "Organize",
    "12. Mining (Malas)", "(1160, 1470, -95)",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 3/3",
]

# --- THE SCRIPT CHARACTER'S runebook, verbatim from the Gump Inspector -------
# This is the book harvest_runner.py's config targets. Arcane is entry 10, on
# page 2 - the entry that was unreachable before pages were walked.
ROOT_P1 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "New Rune", "New Runebook", "Organize",
    "1. Trammel", "2. Ilshenar", "3. Tokuno", "4. TerMur", "5. Mining",
    "6. Homes", "7. RO", "8. TamingDeed", "9. Inscription",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/2",
]

ROOT_P2 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "New Rune", "New Runebook", "Organize",
    "10. Arcane",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 2/2",
]

ROOT_PAGES = [ROOT_P1, ROOT_P2]

# --- A DIFFERENT character's runebook, also verbatim ------------------------
# Not the script character - its folder names are NOT what the config targets.
# It is kept only to prove the navigation code is generic: three pages instead
# of two, eighteen-plus folders, and a genuine name collision between
# "Taming Locations" (page 1) and "TamingDeed" (page 2).
ALT_ROOT_P1 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "New Rune", "New Runebook", "Organize",
    "1. Trammel", "2. Ilshenar", "3. Malas", "4. Tokuno", "5. TerMur",
    "6. Homes", "7. Taming Locations", "8. Mining", "9. RO",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/3",
]

ALT_ROOT_P2 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "New Rune", "New Runebook", "Organize",
    "10. TamingDeed", "11. Farming", "12. TMAP Spots", "13. Champ Spawns",
    "14. Overlords", "15. Town Vendors", "16. IDOC", "17. population control",
    "18. Eodon",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 2/3",
]

# Page 3 of that book was not captured; this stands in so a 3-page walk is
# exercised. Its contents are invented, not observed.
ALT_ROOT_P3 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "New Rune", "New Runebook", "Organize",
    "19. Arcane", "20. Inscription",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 3/3",
]

ALT_ROOT_PAGES = [ALT_ROOT_P1, ALT_ROOT_P2, ALT_ROOT_P3]


def count_entries(lines):
    return len([l for l in lines if re.match(r"^\d+\.\s", l)])


def has_coords(lines):
    return any(re.match(r"^\(\s*[-+]?\d", l) for l in lines)


def make_layout(lines, first_button=10, gates=False):
    """Build a plausible raw layout for a page: controls + one button per entry."""
    pieces = ["{ page 0 }"]
    for control in CONTROLS:
        pieces.append("{ button 10 10 4005 4007 1 0 %d }" % control)
    n = count_entries(lines)
    for i in range(n):
        bid = first_button + i
        pieces.append("{ button 60 %d 4005 4007 1 0 %d }" % (40 + i * 20, bid))
        if gates:
            pieces.append("{ button 90 %d 4005 4007 1 0 %d }"
                          % (40 + i * 20, bid + 30000))
    return "".join(pieces)


class FakeBook(object):
    """A multi-page runebook that responds to 503/504/5 like the real one."""

    def __init__(self, pages, first_button=10, continuous=False):
        self.pages = pages
        self.index = 0
        self.first_button = first_button
        self.continuous = continuous
        self.clicks = []

    def lines(self):
        return list(self.pages[self.index])

    def base_button(self):
        if not self.continuous:
            return self.first_button
        seen = 0
        for page in self.pages[:self.index]:
            seen += count_entries(page)
        return self.first_button + seen

    def layout(self):
        page = self.pages[self.index]
        return make_layout(page, self.base_button(), gates=has_coords(page))

    def click(self, button):
        self.clicks.append(button)
        if button == 504 and self.index < len(self.pages) - 1:
            self.index += 1
        elif button == 503 and self.index > 0:
            self.index -= 1


BOOK = None


class StubGumps(object):
    def HasGump(self, gump_id=None):
        return True

    def CurrentGump(self):
        return 0xc395adb4

    def WaitForGump(self, gump_id, delay):
        return True

    def GetGumpRawLayout(self, gump_id):
        return BOOK.layout()

    def GetLineList(self, gump_id, data_only=False):
        return BOOK.lines()

    def SendAction(self, gump_id, button):
        BOOK.click(button)

    def CloseGump(self, gump_id):
        pass


class StubMisc(object):
    def SendMessage(self, *a):
        pass

    def Pause(self, ms):
        pass


class StubItem(object):
    Serial = 0x41D40F58
    Name = "Backpack"
    ItemID = 0x0E75


class StubPlayer(object):
    Serial = 0x0001A2B3
    Backpack = StubItem()
    Mana = 100
    ManaMax = 100
    IsGhost = False
    WarMode = False
    Name = "Minerbot"

    def ChatSay(self, colour, msg=None):
        pass

    def GetSkillValue(self, name):
        return 100.0

    def GetItemOnLayer(self, layer):
        return None


class StubWorldItem(object):
    def __init__(self, serial, item_id, hue, name=""):
        self.Serial = serial
        self.ItemID = item_id
        self.Hue = hue
        self.Name = name
        self.Amount = 1
        self.Container = None        # None = out in the world
        self.RootContainer = None


class StubItems(object):
    def __init__(self):
        self.by_serial = {}
        self.world = []          # items on the ground
        self.pack = []           # items in the backpack
        # "Contents: 5/125, 30/400 stones" -> plenty of room by default.
        self.contents = "Contents: 5/125 items, 30/400 stones"

    def register(self, item, where="world"):
        self.by_serial[item.Serial] = item
        (self.world if where == "world" else self.pack).append(item)
        return item

    def reset(self):
        self.by_serial = {}
        self.world = []
        self.pack = []
        self.contents = "Contents: 5/125 items, 30/400 stones"

    def FindBySerial(self, serial):
        return self.by_serial.get(serial)

    def FindByID(self, *a):
        return None

    def FindAllByID(self, item_id, hue, container, rng, ignore):
        pool = self.world if container == -1 else self.pack
        ids = item_id if isinstance(item_id, (list, tuple)) else [item_id]
        return [i for i in pool
                if i.ItemID in ids and (hue == -1 or i.Hue == hue)]

    def GetPropStringList(self, item):
        return [self.contents]

    def GetPropStringByIndex(self, serial, index):
        return self.contents

    def WaitForProps(self, *a):
        pass

    def Move(self, *a):
        pass


class StubMob(object):
    def __init__(self, name, props=None, serial=0x1000, body=0x0191,
                 notoriety=7):
        self.Name = name
        self.Serial = serial
        self.Body = body
        self.Notoriety = notoriety
        self._props = props or []


class StubMobiles(object):
    def __init__(self):
        self.nearby = []

    def Filter(self):
        class F(object):
            Enabled = True
            RangeMax = 0
            Name = ""

            def __init__(self):
                self.Notorieties = []
        return F()

    def ApplyFilter(self, f):
        return list(self.nearby)

    def WaitForProps(self, mob, delay):
        pass

    def GetPropStringList(self, mob):
        return list(mob._props)


class StubEntry(object):
    def __init__(self, text, name="", ts=1.0, etype="Regular", serial=0, color=0):
        self.Text = text
        self.Name = name
        self.Timestamp = ts
        self.Type = etype
        self.Serial = serial
        self.Color = color


class StubJournal(object):
    def __init__(self):
        self.entries = []

    def say(self, text, name="Someone", ts=None):
        if ts is None:
            ts = (max((e.Timestamp for e in self.entries), default=0.0)) + 1.0
        self.entries.append(StubEntry(text, name=name, ts=ts))

    def Search(self, text):
        return False

    def Clear(self, text=None):
        pass

    def GetJournalEntry(self, after):
        return [e for e in self.entries if e.Timestamp > after]


class StubTimer(object):
    def Remaining(self, name):
        return 0

    def Check(self, name):
        return False

    def Create(self, *a):
        pass


JOURNAL = StubJournal()
MOBILES = StubMobiles()
ITEMS = StubItems()

# The Wood Storage, verbatim from the Enhanced Item Inspector: locked down on
# the ground at the house, Container and RootContainer both None.
WOOD_STORAGE_SERIAL = 0x4290200A

# The three vendors, verbatim from the Enhanced Mobile Inspector. Note that two
# of the three carry their title in the TOOLTIP, not the name.
DAVIN = StubMob("Davin the Resource Gatherer", [], serial=0x00002A74,
                body=0x0190)
SHERRI = StubMob("Sherri", ["Animal Trainer", "Quest Giver"], serial=0x000A1F45)
EDIE = StubMob("Edie", ["Scribe"], serial=0x000A1F46)
BYSTANDER = StubMob("Bob", ["a wandering healer"], serial=0x000A1F99)


def load_script():
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    env = {
        "__name__": "harvest_runner_under_test",
        "Misc": StubMisc(), "Player": StubPlayer(), "Items": ITEMS,
        "Gumps": StubGumps(), "Journal": JOURNAL, "Timer": StubTimer(),
        "Mobiles": MOBILES, "Target": None, "PathFinding": None,
    }
    exec(compile(source, SCRIPT, "exec"), env)
    return env


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-52s got=%-26r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


def test_page_info(m):
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    check("page info page 1", m["ar_page_info"](), (1, 3))
    BOOK.index = 2
    check("page info page 3", m["ar_page_info"](), (3, 3))


def test_mining_page_parse(m):
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    folders, destinations = m["parse_ar_page"]()
    check("mining p1 destinations", len(destinations), 9)
    check("mining p1 folders", len(folders), 0)
    check("mining p1 buttons", sorted(destinations), list(range(10, 19)))
    first = destinations[10]
    check("mining p1 first name", first["name"], "Mining (Malas)")
    check("mining p1 first coord", first["coord"], [1118, 1464, -95])
    check("mining p1 last coord", destinations[18]["coord"], [1137, 1452, -95])


def test_root_page_parse(m):
    global BOOK
    BOOK = FakeBook(ROOT_PAGES)
    folders, destinations = m["parse_ar_page"]()
    check("root p1 folders", len(folders), 9)
    check("root p1 destinations", len(destinations), 0)
    check("root p1 names", [folders[k] for k in sorted(folders)],
          ["Trammel", "Ilshenar", "Tokuno", "TerMur", "Mining",
           "Homes", "RO", "TamingDeed", "Inscription"])


def test_root_page2_both_numbering(m):
    """Page 2 must parse whether buttons restart at 10 or continue at 19."""
    global BOOK
    for continuous in (False, True):
        BOOK = FakeBook(ROOT_PAGES, continuous=continuous)
        BOOK.index = 1
        folders, _destinations = m["parse_ar_page"]()
        label = "continuous" if continuous else "per-page"
        check("root p2 (%s) folders" % label, len(folders), 1)
        check("root p2 (%s) name" % label, list(folders.values()), ["Arcane"])
        check("root p2 (%s) button" % label, list(folders),
              [19 if continuous else 10])


def test_find_folder_across_pages(m):
    """The original bug: Arcane is on page 2 and was never found."""
    global BOOK
    BOOK = FakeBook(ROOT_PAGES)
    check("goDir finds Mining on page 1", m["goDir"]("Mining"), True)

    BOOK = FakeBook(ROOT_PAGES)
    check("goDir finds Arcane on page 2", m["goDir"]("Arcane"), True)
    check("goDir used the next-page button", 504 in BOOK.clicks, True)

    BOOK = FakeBook(ROOT_PAGES)
    check("goDir reports a missing folder", m["goDir"]("Nonexistent"), False)


def test_generic_across_a_different_book(m):
    """Navigation must not be tuned to one character's runebook.

    ALT_ROOT_* is a different character's book: three pages, eighteen-plus
    folders, and a "Taming Locations" / "TamingDeed" name collision.
    """
    global BOOK

    BOOK = FakeBook(ALT_ROOT_PAGES)
    folders, _d = m["parse_ar_page"]()
    check("alt p1 folders", len(folders), 9)
    check("alt p1 has Taming Locations",
          "Taming Locations" in folders.values(), True)

    BOOK = FakeBook(ALT_ROOT_PAGES)
    BOOK.index = 1
    folders, _d = m["parse_ar_page"]()
    check("alt p2 folders", len(folders), 9)
    check("alt p2 last", folders[sorted(folders)[-1]], "Eodon")

    BOOK = FakeBook(ALT_ROOT_PAGES)
    check("alt: reaches page 2", m["goDir"]("Farming"), True)

    BOOK = FakeBook(ALT_ROOT_PAGES)
    check("alt: reaches page 3", m["goDir"]("Inscription"), True)


def test_exact_match_beats_substring(m):
    """"Taming Locations" (page 1) must not steal "TamingDeed" (page 2)."""
    global BOOK

    BOOK = FakeBook(ALT_ROOT_PAGES)
    hit = m["ar_find"]("TamingDeed", False)
    check("TamingDeed resolves to page 2", (hit[0], hit[2]), (2, "TamingDeed"))

    BOOK = FakeBook(ALT_ROOT_PAGES)
    hit = m["ar_find"]("Taming Locations", False)
    check("Taming Locations resolves to page 1",
          (hit[0], hit[2]), (1, "Taming Locations"))

    # An ambiguous prefix falls back to the first substring hit.
    BOOK = FakeBook(ALT_ROOT_PAGES)
    hit = m["ar_find"]("Taming", False)
    check("ambiguous 'Taming' takes the first substring hit",
          hit[2], "Taming Locations")

    # Exact match wins even against a substring hit on an earlier page.
    BOOK = FakeBook(ALT_ROOT_PAGES)
    hit = m["ar_find"]("Malas", False)
    check("exact Malas on page 1", (hit[0], hit[2]), (1, "Malas"))


def test_never_sends_close_button(m):
    """Button 0 closes the gump - it must never be treated as an entry."""
    global BOOK
    BOOK = FakeBook(ROOT_PAGES)
    m["goDir"]("Arcane")
    check("never sent button 0", 0 in BOOK.clicks, False)

    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    reset_job(m, MINING_JOB)
    m["goNext"](MINING_JOB)
    check("goNext never sent button 0", 0 in BOOK.clicks, False)


MINING_JOB = {"enabled": True, "name": "Mining", "folder": ["Mining"],
              "task": "mine"}
LUMBER_JOB = {"enabled": True, "name": "Lumberjacking", "folder": ["Lumber"],
              "task": "lumber"}


def reset_job(m, job):
    m["_routes"].pop(job["name"], None)
    m["_waypoint"][job["name"]] = 0


def test_routes_span_pages(m):
    """12 runes across 3 pages, not just the 9 on page 1."""
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    reset_job(m, MINING_JOB)
    routes = m["build_routes"](MINING_JOB)
    check("route length", len(routes), 12)
    check("route pages", sorted(set(p for p, _b, _n in routes)), [1, 2, 3])
    check("route page 1 count", len([r for r in routes if r[0] == 1]), 9)
    check("route page 3 count", len([r for r in routes if r[0] == 3]), 1)


def test_routes_are_per_job(m):
    """Mining and lumber must not share a route or a waypoint position."""
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    reset_job(m, MINING_JOB)
    reset_job(m, LUMBER_JOB)

    m["build_routes"](MINING_JOB)
    check("mining route stored", len(m["_routes"]["Mining"]), 12)
    check("lumber route absent", "Lumberjacking" in m["_routes"], False)

    # A smaller "lumber" folder. Note this fixture's footer still says
    # "Page 1/3" while only one page exists - a deliberate lie, so the walk's
    # did-the-page-actually-advance guard is exercised. Without it the same 9
    # runes would be counted three times.
    BOOK = FakeBook([MINING_P1])
    m["build_routes"](LUMBER_JOB)
    check("lumber route stored (no duplicate pages)",
          len(m["_routes"]["Lumberjacking"]), 9)
    check("mining route untouched", len(m["_routes"]["Mining"]), 12)

    m["_waypoint"]["Mining"] = 7
    m["_waypoint"]["Lumberjacking"] = 2
    check("waypoints independent",
          (m["_waypoint"]["Mining"], m["_waypoint"]["Lumberjacking"]), (7, 2))


def test_goto_page(m):
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    check("goto page 3", m["ar_goto_page"](3), True)
    check("landed on page 3", m["ar_page_info"]()[0], 3)
    check("goto page 1 again", m["ar_goto_page"](1), True)
    check("landed on page 1", m["ar_page_info"]()[0], 1)
    check("clamped past the end", m["ar_goto_page"](99), True)
    check("clamp landed on last", m["ar_page_info"]()[0], 3)


def test_goNext_visits_every_rune(m):
    """The reported bug: goNext looped the 9 runes on page 1 forever.

    Drives the real goNext 12 times and checks it recalls to all 12 runes across
    all 3 pages, then wraps.
    """
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    reset_job(m, MINING_JOB)

    recalled = []
    for _ in range(12):
        before = len(BOOK.clicks)
        m["goNext"](MINING_JOB)
        # The recall is the last non-navigation click of this call.
        for button in reversed(BOOK.clicks[before:]):
            if button not in CONTROLS:
                recalled.append((BOOK.index + 1, button))
                break

    check("goNext recalled 12 times", len(recalled), 12)
    check("goNext visited 12 distinct runes", len(set(recalled)), 12)
    check("goNext reached every page",
          sorted(set(page for page, _b in recalled)), [1, 2, 3])

    # One more call must wrap back to the first rune.
    before = len(BOOK.clicks)
    m["goNext"](MINING_JOB)
    wrapped = None
    for button in reversed(BOOK.clicks[before:]):
        if button not in CONTROLS:
            wrapped = (BOOK.index + 1, button)
            break
    check("goNext wraps to the first rune", wrapped, recalled[0])


def reset_greyskull(m):
    JOURNAL.entries = []
    m["_journal_cursor"] = 0.0
    m["_greyskull_pending"] = False
    m["_greyskull_active"] = False


# The real journal line, as captured in-game.
REAL_LINE = "System: <Public> Fred Kruger: By The Power Of Greyskull!"


def test_chat_line_parsing(m):
    """Global chat buries the speaker in the text; entry.Name is just System."""
    cases = [
        (REAL_LINE,
         ("Public", "Fred Kruger", "By The Power Of Greyskull!")),
        ("System: <Public> Alice: by the power of greyskull",
         ("Public", "Alice", "by the power of greyskull")),
        ("<Guild> Bob: By The Power Of Greyskull!",
         ("Guild", "Bob", "By The Power Of Greyskull!")),
        ("Fred Kruger: By The Power Of Greyskull!",
         (None, "Fred Kruger", "By The Power Of Greyskull!")),
        ("By The Power Of Greyskull!",
         (None, None, "By The Power Of Greyskull!")),
    ]
    for raw, want in cases:
        check("parse %r" % raw[:38], m["parse_chat_line"](raw), want)


def test_greyskull_case_insensitive(m):
    """The reported bug: the old exact match missed any typed variation."""
    variants = [
        REAL_LINE,
        "System: <Public> Fred Kruger: by the power of greyskull!",
        "System: <Public> fred kruger: BY THE POWER OF GREYSKULL",
        "By The Power Of Greyskull!",
        "  by the power of greyskull  ",
    ]
    for said in variants:
        reset_greyskull(m)
        JOURNAL.say(said)
        check("hears %r" % said.strip()[:38], m["greyskull_heard"](), True)

    for ignored in ["System: <Public> Fred Kruger: by the power of grayskull",
                    "System: <Public> Fred Kruger: power of greyskull",
                    "I have the power!",
                    "You have found some iron ore"]:
        reset_greyskull(m)
        JOURNAL.say(ignored)
        check("ignores %r" % ignored[:38], m["greyskull_heard"](), False)


def test_greyskull_anyone_can_call(m):
    """Default must be: ANY caller triggers it, not just the script owner."""
    original = list(m["GREYSKULL_ALLOWED_CALLERS"])
    try:
        m["GREYSKULL_ALLOWED_CALLERS"][:] = []
        for who in ["Fred Kruger", "Alice", "Minerbot", "Some Random Person"]:
            reset_greyskull(m)
            JOURNAL.say("System: <Public> %s: By The Power Of Greyskull!" % who)
            check("anyone: %s triggers it" % who, m["greyskull_heard"](), True)

        # Own character must work too, since IGNORE_SELF is off by default.
        reset_greyskull(m)
        JOURNAL.say("System: <Public> Minerbot: By The Power Of Greyskull!")
        check("own call-out triggers it", m["greyskull_heard"](), True)

        # An allow-list, when set, restricts it.
        m["GREYSKULL_ALLOWED_CALLERS"][:] = ["Fred Kruger"]
        reset_greyskull(m)
        JOURNAL.say(REAL_LINE)
        check("allow-list admits Fred", m["greyskull_heard"](), True)
        reset_greyskull(m)
        JOURNAL.say("System: <Public> Mallory: By The Power Of Greyskull!")
        check("allow-list rejects Mallory", m["greyskull_heard"](), False)
    finally:
        m["GREYSKULL_ALLOWED_CALLERS"][:] = original


def test_greyskull_channel_filter(m):
    original = m["GREYSKULL_REQUIRE_CHANNEL"]
    try:
        m["GREYSKULL_REQUIRE_CHANNEL"] = "Public"
        reset_greyskull(m)
        JOURNAL.say(REAL_LINE)
        check("channel filter admits Public", m["greyskull_heard"](), True)
        reset_greyskull(m)
        JOURNAL.say("<Guild> Bob: By The Power Of Greyskull!")
        check("channel filter rejects Guild", m["greyskull_heard"](), False)
    finally:
        m["GREYSKULL_REQUIRE_CHANNEL"] = original


def test_greyskull_does_not_retrigger(m):
    """A single chant must fire once, not on every poll afterwards."""
    reset_greyskull(m)
    JOURNAL.say("by the power of greyskull!")
    check("first poll hears it", m["greyskull_heard"](), True)
    check("second poll does not", m["greyskull_heard"](), False)
    check("third poll does not", m["greyskull_heard"](), False)

    JOURNAL.say("by the power of greyskull!")
    check("a new chant is heard again", m["greyskull_heard"](), True)


def test_greyskull_primes_cursor(m):
    """Chants said before the script started must not fire on startup."""
    reset_greyskull(m)
    JOURNAL.say("by the power of greyskull!")     # said before we start
    m["prime_journal_cursor"]()
    check("old chant ignored after priming", m["greyskull_heard"](), False)
    JOURNAL.say("by the power of greyskull!")     # said after
    check("new chant still heard", m["greyskull_heard"](), True)


def test_greyskull_poll_flag(m):
    """poll_greyskull only raises a flag - it must never travel."""
    reset_greyskull(m)
    check("no flag initially", m["poll_greyskull"](), False)
    JOURNAL.say("by the power of greyskull!")
    check("poll raises the flag", m["poll_greyskull"](), True)
    check("flag stays raised", m["poll_greyskull"](), True)
    check("flag is the module global", m["_greyskull_pending"], True)

    # While responding, polling must not re-arm - that would recurse.
    m["_greyskull_active"] = True
    m["_greyskull_pending"] = False
    JOURNAL.say("by the power of greyskull!")
    check("suppressed while responding", m["poll_greyskull"](), False)
    m["_greyskull_active"] = False


def test_interruptible_pause_listens(m):
    """The regression: long meditation pauses swallowed the chant entirely."""
    reset_greyskull(m)
    JOURNAL.say("by the power of greyskull!")
    m["interruptible_pause"](1000)
    check("pause noticed the chant", m["_greyskull_pending"], True)


def test_mana_goal_shortcut(m):
    """With a chant pending, meditate only to the travel floor, not to full."""
    reset_greyskull(m)
    minimum = m["MIN_MANA_TO_TRAVEL"]
    m["_greyskull_pending"] = False
    check("normal goal is full mana", m["mana_goal"](minimum),
          StubPlayer.ManaMax)
    m["_greyskull_pending"] = True
    check("pending goal is the floor", m["mana_goal"](minimum), minimum)
    reset_greyskull(m)


def test_vendor_validation(m):
    """A stop with no NPC names must be rejected loudly, not skipped silently."""
    good = {"enabled": True, "label": "Good", "folder": ["RO"], "point": "RO",
            "names": ["Resource Gatherer"], "context": ["Talk"], "gump": None}
    no_names = {"enabled": True, "label": "NoNames", "folder": ["X"],
                "point": "X", "names": [], "context": ["Talk"], "gump": None}
    missing_names = {"enabled": True, "label": "Missing", "folder": ["Y"],
                     "point": "Y", "context": ["Talk"], "gump": None}
    no_point = {"enabled": True, "label": "NoPoint", "folder": ["Z"],
                "point": "", "names": ["Someone"], "context": ["Talk"],
                "gump": None}
    disabled = {"enabled": False, "label": "Off", "folder": ["W"], "point": "W",
                "names": ["Someone"], "context": ["Talk"], "gump": None}

    original = list(m["VENDORS"])      # copy - slicing the live list aliases it
    try:
        m["VENDORS"][:] = [good, no_names, missing_names, no_point, disabled]
        usable = m["validate_vendors"](m["VENDORS"])
        check("validate keeps only usable stops",
              [v["label"] for v in usable], ["Good"])

        m["VENDORS"][:] = [good]
        check("validate accepts a complete stop",
              [v["label"] for v in m["validate_vendors"](m["VENDORS"])], ["Good"])

        m["VENDORS"][:] = [no_names]
        check("validate rejects an all-bad table",
              m["validate_vendors"](m["VENDORS"]), [])
    finally:
        m["VENDORS"][:] = original


def test_job_validation(m):
    """A job with no folder or an unknown task must be rejected loudly."""
    original = list(m["JOBS"])
    try:
        m["JOBS"][:] = [
            MINING_JOB,
            LUMBER_JOB,
            {"enabled": True, "name": "NoFolder", "folder": [], "task": "mine"},
            {"enabled": True, "name": "BadTask", "folder": ["X"],
             "task": "smelting"},
            {"enabled": False, "name": "Off", "folder": ["Y"], "task": "mine"},
        ]
        usable = m["active_jobs"]()
        check("active_jobs keeps only valid jobs",
              [j["name"] for j in usable], ["Mining", "Lumberjacking"])

        m["JOBS"][:] = [LUMBER_JOB]
        check("single job runs alone",
              [j["name"] for j in m["active_jobs"]()], ["Lumberjacking"])

        m["JOBS"][:] = [{"enabled": True, "name": "Bad", "folder": [],
                         "task": "nope"}]
        check("all-bad job table", m["active_jobs"](), [])
    finally:
        m["JOBS"][:] = original


def test_shipped_jobs(m):
    """The shipped JOBS table must itself be complete."""
    for job in m["JOBS"]:
        name = job.get("name", "?")
        check("shipped job %s has folder" % name, bool(job.get("folder")), True)
        check("shipped job %s task is known" % name,
              job.get("task") in m["TASKS"], True)


def test_task_registry(m):
    """Both harvesters must be registered and callable."""
    check("tasks registered", sorted(m["TASKS"]), ["lumber", "mine"])


def test_hostile_filter_is_bounded(m):
    """Without RangeMax the check was permanently true and ate the whole route."""
    seen = {}

    class NetList(list):
        """.NET List[Byte] exposes Add(), not append()."""
        def Add(self, value):
            self.append(value)

    class F(object):
        Enabled = True
        RangeMax = None
        CheckLineOfSight = False

        def __init__(self):
            self.Notorieties = NetList()

    class MobFilter(object):
        def __init__(self, result):
            self.result = result

        def Filter(self):
            return F()

        def ApplyFilter(self, f):
            seen["range"] = f.RangeMax
            seen["notor"] = list(f.Notorieties)
            seen["los"] = f.CheckLineOfSight
            return self.result

        def WaitForProps(self, *a):
            pass

        def GetPropStringList(self, mob):
            return []

    original = m["Mobiles"]
    try:
        m["Mobiles"] = MobFilter([])
        check("no hostiles", m["hostiles_near"](), False)
        check("RangeMax is set", seen["range"], m["HOSTILE_RANGE"])
        check("range is bounded", 0 < seen["range"] <= 12, True)
        check("notorieties", seen["notor"], m["HOSTILE_NOTORIETIES"])
        check("line of sight on", seen["los"], True)

        m["Mobiles"] = MobFilter([StubMob("a ratman", [], serial=0x999)])
        check("hostile detected", m["hostiles_near"](), True)

        # The switch must actually disable it.
        original_flag = m["ABORT_ON_HOSTILES"]
        m["ABORT_ON_HOSTILES"] = False
        check("disabled by config", m["hostiles_near"](), False)
        m["ABORT_ON_HOSTILES"] = original_flag
    finally:
        m["Mobiles"] = original


def test_axe_by_graphic(m):
    """The axe must be findable without relying on item names.

    After meditation stows it, Name is often empty until props load - a
    name-only search returns None and the lumber task aborts the whole job.
    """
    class Fake(object):
        def __init__(self, item_id, name=None):
            self.ItemID = item_id
            self.Name = name
            self.Serial = 0x40000000 + item_id

    check("hatchet by graphic", m["is_axe"](Fake(0x0F43)), True)
    check("axe by graphic", m["is_axe"](Fake(0x0F49)), True)
    check("double axe by graphic", m["is_axe"](Fake(0x0F4C)), True)
    check("two handed axe by graphic", m["is_axe"](Fake(0x1443)), True)
    check("pickaxe by graphic", m["is_axe"](Fake(0x0E86)), True)
    check("unnamed axe still matches", m["is_axe"](Fake(0x0F49, None)), True)

    check("war axe not in the list", 0x13B0 in m["AXE_IDS"], False)
    check("a dagger graphic is not an axe", m["is_axe"](Fake(0x0F51)), False)
    check("still matches by name when graphic is unknown",
          m["is_axe"](Fake(0x9999, "a shard-custom hatchet")), True)
    check("None is not an axe", m["is_axe"](None), False)

    # Every id must be a plausible graphic and unique.
    ids = m["AXE_IDS"]
    check("axe ids are unique", len(ids), len(set(ids)))
    check("axe ids in range", all(0 < i < 0x10000 for i in ids), True)


def test_meditation_does_not_predisarm(m):
    """Stowing the axe before meditating cost the harvest tool every time."""
    import inspect
    src = inspect.getsource(m["ensure_mana"])
    check("no pre-emptive free_hands in ensure_mana",
          "free_hands()" in src.split("MED_HANDS")[0], False)


def test_axe_matching(m):
    """Axe detection must skip war axes and survive null names."""
    class Fake(object):
        def __init__(self, name):
            self.Name = name

    cases = [
        ("a hatchet", True),
        ("an axe", True),
        ("a double axe", True),
        ("a war axe", False),          # excluded
        ("a large battle axe", True),  # not a "war" axe
        ("a pickaxe", True),
        ("a dagger", False),
        ("", False),
        (None, False),                 # null name crashed the original
    ]
    for name, want in cases:
        check("axe match %r" % name, m["looks_like_axe"](Fake(name)), want)
    check("axe match None item", m["looks_like_axe"](None), False)


def test_vendor_lookup_by_tooltip(m):
    """The reported bug: two of three vendors carry their title in the tooltip.

    "Sherri" is the Animal Trainer and "Edie" is the Scribe - neither name
    contains the title, so a name-only match could never find them.
    """
    MOBILES.nearby = [DAVIN, SHERRI, EDIE, BYSTANDER]

    found = m["find_vendors"](["Resource Gatherer"])
    check("Davin found by name", [f.Name for f in found],
          ["Davin the Resource Gatherer"])

    found = m["find_vendors"](["Animal Trainer"])
    check("Sherri found by tooltip", [f.Name for f in found], ["Sherri"])

    found = m["find_vendors"](["Scribe"])
    check("Edie found by tooltip", [f.Name for f in found], ["Edie"])

    # Regression: name-only matching finds neither.
    for title, who in [("Animal Trainer", "Sherri"), ("Scribe", "Edie")]:
        in_name = title.lower() in who.lower()
        check("regression: %r not in name %r" % (title, who), in_name, False)

    check("no false positive", m["find_vendors"](["Blacksmith"]), [])
    check("empty names match nothing", m["find_vendors"]([]), [])

    # A vendor with no tooltip at all must still work off its name.
    MOBILES.nearby = [DAVIN]
    check("tooltip-less NPC still found by name",
          len(m["find_vendors"](["Resource Gatherer"])), 1)

    MOBILES.nearby = []


def test_shipped_vendor_names_match_real_npcs(m):
    """The shipped VENDORS table must find the three observed NPCs."""
    MOBILES.nearby = [DAVIN, SHERRI, EDIE, BYSTANDER]
    expected = {
        "Resource Orders": "Davin the Resource Gatherer",
        "Taming Deeds": "Sherri",
        "Inscription Orders": "Edie",
    }
    for vendor in m["VENDORS"]:
        want = expected.get(vendor["label"])
        if want is None:
            continue
        found = m["find_vendors"](vendor["names"])
        check("%s finds %s" % (vendor["label"], want),
              [f.Name for f in found], [want])
    MOBILES.nearby = []


# Context menus verbatim from diag_vendors.py.
SHERRI_MENU = ["Open Paperdoll", "Stable Pet", "Talk", "Buy", "Sell",
               "Train Animal Lore", "Train Animal Taming", "Train Veterinary"]
EDIE_MENU = ["Open Paperdoll", "Bulk Order Info", "Bribe", "Claim Rewards",
             "Buy", "Sell", "Train Evaluating Intelligence", "Train Inscription"]
AMSDEN_MENU = ["Open Paperdoll", "Open Bankbox", "Buy", "Sell"]


class StubCtxEntry(object):
    def __init__(self, response, entry):
        self.Response = response
        self.Entry = entry


def install_menu(m, labels):
    """Point the stubbed context system at a menu and record what is picked."""
    picked = []

    def wait_context(entity, delay=None, show=None):
        return [StubCtxEntry(i, label) for i, label in enumerate(labels)]

    class Ctx(object):
        def ContextReply(self, mob, label):
            picked.append(label)

        def SendMessage(self, *a):
            pass

        def Pause(self, ms):
            pass

        def WaitForContext(self, entity, delay=None, show=None):
            return wait_context(entity)

    m["wait_context"] = wait_context
    m["Misc"] = Ctx()
    return picked


def test_context_selection(m):
    """The real menus: Sherri wants Talk, Edie wants Bulk Order Info."""
    original_misc = m["Misc"]
    original_wait = m["wait_context"]
    try:
        picked = install_menu(m, SHERRI_MENU)
        m["talk_to"](SHERRI, ["Talk"])
        check("Sherri: picks Talk", picked, ["Talk"])

        picked = install_menu(m, EDIE_MENU)
        m["talk_to"](EDIE, ["Bulk Order Info", "Bulk Order", "Talk"])
        check("Edie: picks Bulk Order Info", picked, ["Bulk Order Info"])

        # Falls through to a later configured entry when the first is absent.
        picked = install_menu(m, SHERRI_MENU)
        m["talk_to"](SHERRI, ["Bulk Order Info", "Talk"])
        check("falls back to Talk", picked, ["Talk"])

        picked = install_menu(m, AMSDEN_MENU)
        m["talk_to"](DAVIN, ["Talk"])
        check("no match picks nothing", picked, [])
    finally:
        m["Misc"] = original_misc
        m["wait_context"] = original_wait


def test_context_never_blocks_costly_entries(m):
    """These menus sit next to Buy, Sell, Bribe and Train <skill>."""
    original_misc = m["Misc"]
    original_wait = m["wait_context"]
    try:
        # A sloppy config value that substring-matches "Train Animal Taming".
        picked = install_menu(m, SHERRI_MENU)
        m["talk_to"](SHERRI, ["Taming"])
        check("blocks Train Animal Taming", picked, [])

        # A partial that would substring-hit "Bribe".
        picked = install_menu(m, EDIE_MENU)
        m["talk_to"](EDIE, ["Brib"])
        check("blocks a partial hit on Bribe", picked, [])

        picked = install_menu(m, AMSDEN_MENU)
        m["talk_to"](DAVIN, ["Bank"])
        check("blocks Open Bankbox", picked, [])

        # Configuring the exact label is always honoured, even for a blocked
        # word - that is a deliberate choice, not an oversight.
        picked = install_menu(m, EDIE_MENU)
        m["talk_to"](EDIE, ["Bribe"])
        check("exact Bribe is honoured", picked, ["Bribe"])

        # An exact configured match is always honoured - it was meant.
        picked = install_menu(m, SHERRI_MENU)
        m["talk_to"](SHERRI, ["Train Animal Taming"])
        check("exact match overrides the block", picked, ["Train Animal Taming"])

        # Exact match wins over an earlier substring hit.
        picked = install_menu(m, EDIE_MENU)
        m["talk_to"](EDIE, ["Claim Rewards"])
        check("exact Claim Rewards", picked, ["Claim Rewards"])
    finally:
        m["Misc"] = original_misc
        m["wait_context"] = original_wait


def test_wood_storage_config(m):
    """The entry must be wired to the WOOD_STORAGE_* settings.

    `where` is a user choice - carried in the pack or locked down at the house -
    so this asserts it is a VALID choice and that it tracks the setting, not
    which one is currently selected.
    """
    wood = [k for k in m["RESTOCK_KEYS"]
            if k.get("label") == "Wood Storage"]
    check("wood storage is configured", len(wood), 1)
    wood = wood[0]
    check("wood storage serial", wood.get("serial"), WOOD_STORAGE_SERIAL)
    check("wood storage fallback id", wood.get("id"), 0x1BD9)
    check("wood storage fallback hue", wood.get("hue"), 0x0058)
    check("where is a valid choice",
          wood.get("where") in ("world", "pack"), True)
    check("where tracks WOOD_STORAGE_WHERE",
          wood.get("where"), m["WOOD_STORAGE_WHERE"])


def test_find_restock(m):
    """Serial first, then id/hue in the right place."""
    ITEMS.reset()
    storage = StubWorldItem(WOOD_STORAGE_SERIAL, 0x1BD9, 0x0058, "Wood Storage")
    ITEMS.register(storage, "world")

    wood = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Wood Storage"][0]
    found = m["find_restock"](wood)
    check("found by serial", [i.Serial for i in found], [WOOD_STORAGE_SERIAL])

    # Serial gone (item replaced) - must fall back to id/hue, in whichever
    # place the spec says. Both directions are checked explicitly rather than
    # relying on however WOOD_STORAGE_WHERE happens to be set.
    for where, register_as in (("world", "world"), ("pack", "pack")):
        ITEMS.reset()
        replaced = StubWorldItem(0x4290FFFF, 0x1BD9, 0x0058, "Wood Storage")
        ITEMS.register(replaced, register_as)
        spec = dict(wood)
        spec["serial"] = 0
        spec["where"] = where
        check("falls back to id/hue in %s" % where,
              [i.Serial for i in m["find_restock"](spec)], [0x4290FFFF])

    # ...and must NOT find it in the other place.
    ITEMS.reset()
    ITEMS.register(StubWorldItem(0x4290FFFF, 0x1BD9, 0x0058), "world")
    spec = dict(wood)
    spec["serial"] = 0
    spec["where"] = "pack"
    check("pack spec ignores a ground item", m["find_restock"](spec), [])

    # A pack-only key must not match a ground item.
    ITEMS.reset()
    ITEMS.register(StubWorldItem(0x50000001, 0x176B, 0x0481, "master"), "world")
    master = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Master key"][0]
    check("pack key ignores ground items", m["find_restock"](master), [])

    ITEMS.reset()


def test_refill_keys_uses_storage(m):
    """refill_keys must single-click the storage and pick Refill from stock."""
    original_misc = m["Misc"]
    original_wait = m["wait_context"]
    try:
        ITEMS.reset()
        ITEMS.register(
            StubWorldItem(WOOD_STORAGE_SERIAL, 0x1BD9, 0x0058, "Wood Storage"),
            "world")
        ITEMS.contents = "Contents: 120/125 items, 390/400 stones"   # full

        picked = install_menu(m, ["Open", "Refill from stock", "Rename"])
        # The pack frees up once the storage has taken the load.
        def freeing_reply(mob, label):
            picked.append(label)
            ITEMS.contents = "Contents: 5/125 items, 30/400 stones"
        m["Misc"].ContextReply = freeing_reply

        ok = m["refill_keys"]()
        check("refill picked the right entry", picked, ["Refill from stock"])
        check("refill reports success", ok, True)

        # Nothing in reach: must report failure rather than claim success.
        ITEMS.reset()
        ITEMS.contents = "Contents: 120/125 items, 390/400 stones"
        install_menu(m, [])
        check("no storage in reach", m["refill_keys"](), False)
    finally:
        m["Misc"] = original_misc
        m["wait_context"] = original_wait
        ITEMS.reset()


def test_pack_usage_parsing(m):
    ITEMS.reset()
    ITEMS.contents = "Contents: 5/125 items, 30/400 stones"
    check("pack usage parsed", m["pack_usage"](), (5, 125, 30, 400))
    check("pack has room", m["pack_has_room"](), True)

    ITEMS.contents = "Contents: 120/125 items, 30/400 stones"
    check("full by item count", m["pack_has_room"](), False)

    ITEMS.contents = "Contents: 5/125 items, 390/400 stones"
    check("full by weight", m["pack_has_room"](), False)
    ITEMS.reset()


def test_carried_key_skips_dropoff(m):
    """A key in the pack must empty on the spot, never trigger a trip home."""
    original_misc = m["Misc"]
    original_wait = m["wait_context"]
    try:
        # Storage carried in the backpack.
        ITEMS.reset()
        carried = StubWorldItem(WOOD_STORAGE_SERIAL, 0x1BD9, 0x0058,
                                "Wood Storage")
        carried.Container = StubItem.Serial          # the backpack
        carried.RootContainer = StubItem.Serial
        ITEMS.register(carried, "pack")
        ITEMS.contents = "Contents: 120/125 items, 390/400 stones"

        picked = install_menu(m, ["Refill from stock"])

        def freeing_reply(mob, label):
            picked.append(label)
            ITEMS.contents = "Contents: 5/125 items, 30/400 stones"
        m["Misc"].ContextReply = freeing_reply

        check("carried key is recognised", m["item_is_on_player"](carried), True)
        check("carried key empties on the spot",
              m["refill_keys"](on_player_only=True), True)
        check("and it used the right entry", picked, ["Refill from stock"])

        # Same storage out in the world: must be skipped in on-player mode, so
        # the caller falls through to the drop-off run.
        ITEMS.reset()
        remote = StubWorldItem(WOOD_STORAGE_SERIAL, 0x1BD9, 0x0058,
                               "Wood Storage")
        remote.Container = None
        remote.RootContainer = None
        ITEMS.register(remote, "world")
        ITEMS.contents = "Contents: 120/125 items, 390/400 stones"

        picked = install_menu(m, ["Refill from stock"])
        check("world storage is not on the player",
              m["item_is_on_player"](remote), False)
        check("world storage skipped on the spot",
              m["refill_keys"](on_player_only=True), False)
        check("nothing was clicked", picked, [])

        # But it is used during the drop-off run.
        picked = install_menu(m, ["Refill from stock"])
        m["Misc"].ContextReply = freeing_reply
        check("world storage used at the drop-off", m["refill_keys"](), True)
    finally:
        m["Misc"] = original_misc
        m["wait_context"] = original_wait
        ITEMS.reset()


def test_route_survives_dropoff(m):
    """The reported bug: lumber did one spot, went home, then switched jobs.

    A trip home must not reset or advance the route - the same waypoint is
    resumed, and the lap only completes after every rune has been worked.
    """
    global BOOK
    BOOK = FakeBook([MINING_P1, MINING_P2, MINING_P3])
    reset_job(m, MINING_JOB)
    m["_lap_done"][MINING_JOB["name"]] = False

    m["build_routes"](MINING_JOB)
    total = len(m["_routes"]["Mining"])
    check("route has 12 runes", total, 12)

    # Work three waypoints.
    for _ in range(3):
        m["goNext"](MINING_JOB)
    check("position after 3", m["_waypoint"]["Mining"], 3)
    check("no lap yet", m["_lap_done"].get("Mining"), False)

    # A trip home: goJobDir must not wipe the route or the position.
    m["goJobDir"](MINING_JOB)
    check("route survives goJobDir", len(m["_routes"].get("Mining") or []), 12)
    check("position survives goJobDir", m["_waypoint"]["Mining"], 3)

    # Resuming returns to the same spot without advancing.
    m["goCurrent"](MINING_JOB)
    check("goCurrent does not advance", m["_waypoint"]["Mining"], 3)

    # Finish the lap.
    for _ in range(total - 3):
        m["goNext"](MINING_JOB)
    check("position at end of lap", m["_waypoint"]["Mining"], total)
    check("still no lap flag", m["_lap_done"].get("Mining"), False)

    m["goNext"](MINING_JOB)
    check("lap completes on wrap", m["_lap_done"].get("Mining"), True)
    check("wrapped to first rune", m["_waypoint"]["Mining"], 1)


def test_rotation_default(m):
    check("rotation defaults to route", m["JOB_ROTATION"], "route")


def test_wood_storage_where_is_config_driven(m):
    """The pack/world choice must come from the top-of-file setting."""
    wood = [k for k in m["RESTOCK_KEYS"]
            if k.get("label") == "Wood Storage"][0]
    check("where follows WOOD_STORAGE_WHERE",
          wood["where"], m["WOOD_STORAGE_WHERE"])
    check("serial follows config", wood["serial"], m["WOOD_STORAGE_SERIAL"])
    check("valid where value", m["WOOD_STORAGE_WHERE"] in ("world", "pack"),
          True)


def test_vendor_gump_list(m):
    """Large and small bulk orders may use different gump ids."""
    scribe = [v for v in m["all_vendors"]()
              if "Scribe" in v["names"]][0]
    check("scribe gump is a list", isinstance(scribe["gump"], list), True)
    # Small bulk orders open 0x9BADE6EA, large ones 0xBE0DAD1E - both confirmed
    # in-game, which is why this is a list at all.
    check("gump_ids reads a list", m["gump_ids"](scribe),
          [0x9BADE6EA, 0xBE0DAD1E])
    check("gump_ids reads a bare tuple",
          m["gump_ids"]({"gump": (0x1234, 1)}), [0x1234])
    check("gump_ids handles None", m["gump_ids"]({"gump": None}), [])
    check("gump_ids handles missing", m["gump_ids"]({}), [])


def test_vendor_gump_answering(m):
    """Tries each candidate, and reports the id that actually opened."""
    calls = []
    opened = {"id": 0x9bade6ea}

    class G(object):
        def HasGump(self, gid=None):
            return opened["id"] is not None

        def CurrentGump(self):
            return opened["id"] or 0

        def WaitForGump(self, gid, delay):
            return gid == opened["id"]

        def SendAction(self, gid, button):
            calls.append((gid, button))

        def CloseGump(self, gid):
            opened["id"] = None

        def ResetGump(self):
            pass

        def GetGumpRawLayout(self, gid):
            return ""

        def GetLineList(self, gid, data_only=False):
            return []

    original = m["Gumps"]
    try:
        m["Gumps"] = G()
        scribe = [v for v in m["all_vendors"]()
                  if "Scribe" in v["names"]][0]

        check("answers the expected gump", m["answer_vendor_gump"](scribe), True)
        check("sent the right button", calls, [(0x9bade6ea, 1)])

        # A different gump opens - must fail rather than answer blindly.
        del calls[:]
        opened["id"] = 0xDEADBEEF
        check("unknown gump is not answered",
              m["answer_vendor_gump"](scribe), False)
        check("nothing was sent", calls, [])

        # Multiple candidates: the second one matches.
        del calls[:]
        opened["id"] = 0xDEADBEEF
        two = {"label": "Two", "gump": [(0x9bade6ea, 1), (0xDEADBEEF, 4)]}
        check("second candidate matches", m["answer_vendor_gump"](two), True)
        check("used the second button", calls, [(0xDEADBEEF, 4)])

        # No gump configured at all is a success, not a failure.
        check("no gump configured", m["answer_vendor_gump"]({"label": "x"}), True)
    finally:
        m["Gumps"] = original


def test_vendor_stops_group_by_rune(m):
    """NPCs sharing a rune must be one trip, not one trip each."""
    def v(label, folder, point):
        return {"enabled": True, "label": label, "folder": folder,
                "point": point, "names": ["x"], "context": ["Talk"],
                "gump": None}

    vendors = [
        v("Resource Orders", ["RO"], "RO"),
        v("Taming Deeds", ["BOD"], "tameinscribe"),
        v("Inscription Orders", ["BOD"], "tameinscribe"),
        v("Blacksmith Orders", ["BOD"], "Blacksmith"),
    ]
    stops = m["vendor_stops"](vendors)

    check("four vendors become three stops", len(stops), 3)
    check("taming and inscription share a stop",
          sorted(x["label"] for x in stops[1]["vendors"]),
          ["Inscription Orders", "Taming Deeds"])
    check("blacksmith is its own stop",
          [x["label"] for x in stops[2]["vendors"]], ["Blacksmith Orders"])
    check("every vendor is kept",
          sum(len(s["vendors"]) for s in stops), 4)
    check("stop order follows the table",
          [s["point"] for s in stops], ["RO", "tameinscribe", "Blacksmith"])

    # Matching is case and spacing insensitive.
    stops = m["vendor_stops"]([
        v("A", ["BOD"], "tameinscribe"),
        v("B", ["bod"], " TameInscribe "),
    ])
    check("rune matching ignores case and spaces", len(stops), 1)

    check("no vendors, no stops", m["vendor_stops"]([]), [])


def test_shipped_vendor_runes(m):
    """The shipped table must point each vendor at a plausible rune."""
    by_point = {}
    for vendor in m["VENDORS"]:
        by_point.setdefault(vendor["point"].strip().lower(), []).append(
            vendor["label"])
    # Blacksmith has its own rune - Cara is ~240 tiles from tameinscribe.
    smith = [v for v in m["all_vendors"]() if "Blacksmith" in v["names"]]
    if smith:
        check("blacksmith does not share tameinscribe",
              smith[0]["point"].strip().lower() == "tameinscribe", False)


def test_vendor_scheduling(m):
    """Beyond Sosaria: 3 per profession per 6h, resource gatherer 1 per 30m.

    The vendor round runs every 30 minutes, so without a budget the script
    would recall to every bulk order NPC twelve times per refresh.
    """
    smith = {"label": "smith @ test", "names": ["Blacksmith"],
             "context": ["Talk"], "gump": None,
             "folder": ["BOD"], "point": "Blacksmith"}

    m["_vendor_history"].clear()
    m["_vendor_ready_at"].clear()

    check("defaults match the shard", (m["BOD_REQUESTS_PER_WINDOW"],
                                       m["BOD_WINDOW_MS"]),
          (3, 360 * 60 * 1000))
    check("a fresh vendor is due", m["vendor_due"](smith), True)

    # Three collections fill the window, the fourth must wait.
    for i in range(3):
        m["note_vendor_collected"](smith)
        expected = i < 2
        check("due after %d collection(s)" % (i + 1),
              m["vendor_due"](smith), expected)
    check("wait is reported in hours", m["vendor_wait_text"](smith).endswith("h"),
          True)

    # An expired window frees it again.
    m["_vendor_history"]["smith @ test"] = [time.time() - 7 * 3600] * 3
    check("window expiry frees it", m["vendor_due"](smith), True)

    # The resource gatherer has its own budget.
    gatherer = [v for v in m["VENDORS"] if "Resource Gatherer" in v["names"]][0]
    check("gatherer allows 1", m["vendor_limit"](gatherer), 1)
    check("gatherer window is 30m", m["vendor_window"](gatherer), 1800.0)

    m["_vendor_history"].clear()
    m["_vendor_ready_at"].clear()


def test_reported_wait_is_believed(m):
    """The NPC states the wait - use it rather than guessing."""
    class E(object):
        def __init__(self, text):
            self.Text = text
            self.Timestamp = 1.0

    original = m["Journal"]

    class J(object):
        lines = []

        def GetJournalEntry(self, after):
            return [E(t) for t in J.lines]

        def Search(self, text):
            return any(text in l for l in J.lines)

        def Clear(self, text=None):
            pass

    try:
        m["Journal"] = J()

        J.lines = ["An offer may be available in about 45 minutes."]
        check("minutes parsed", m["parse_reported_wait"](), 45 * 60)

        J.lines = ["An offer may be available in about 6 hours."]
        check("hours parsed", m["parse_reported_wait"](), 6 * 3600)

        J.lines = ["Sherri: Good day to you."]
        check("unrelated line ignored", m["parse_reported_wait"](), None)

        # A parsed wait must actually park the vendor.
        smith = {"label": "smith @ wait", "names": ["x"], "context": ["Talk"],
                 "gump": None, "folder": ["BOD"], "point": "Blacksmith"}
        m["_vendor_history"].clear()
        m["_vendor_ready_at"].clear()
        J.lines = ["An offer may be available in about 45 minutes."]
        m["note_vendor_cooldown"](smith, m["parse_reported_wait"]())
        check("parked after a reported wait", m["vendor_due"](smith), False)
        check("wait shown in minutes",
              m["vendor_wait_text"](smith).endswith("m"), True)
        m["_vendor_ready_at"].clear()
    finally:
        m["Journal"] = original


def test_vendor_defaults(m):
    """The shipped table must itself be complete - no missing NPC names."""
    for vendor in m["VENDORS"]:
        label = vendor.get("label", "?")
        check("shipped %s has names" % label, bool(vendor.get("names")), True)
        check("shipped %s has point" % label, bool(vendor.get("point")), True)
        check("shipped %s has context" % label, bool(vendor.get("context")), True)


def main():
    module = load_script()
    test_page_info(module)
    test_mining_page_parse(module)
    test_root_page_parse(module)
    test_root_page2_both_numbering(module)
    test_find_folder_across_pages(module)
    test_generic_across_a_different_book(module)
    test_exact_match_beats_substring(module)
    test_never_sends_close_button(module)
    test_routes_span_pages(module)
    test_routes_are_per_job(module)
    test_goto_page(module)
    test_goNext_visits_every_rune(module)
    test_chat_line_parsing(module)
    test_greyskull_case_insensitive(module)
    test_greyskull_anyone_can_call(module)
    test_greyskull_channel_filter(module)
    test_greyskull_does_not_retrigger(module)
    test_greyskull_primes_cursor(module)
    test_greyskull_poll_flag(module)
    test_interruptible_pause_listens(module)
    test_mana_goal_shortcut(module)
    test_vendor_validation(module)
    test_vendor_lookup_by_tooltip(module)
    test_shipped_vendor_names_match_real_npcs(module)
    test_context_selection(module)
    test_context_never_blocks_costly_entries(module)
    test_wood_storage_config(module)
    test_find_restock(module)
    test_refill_keys_uses_storage(module)
    test_pack_usage_parsing(module)
    test_carried_key_skips_dropoff(module)
    test_route_survives_dropoff(module)
    test_rotation_default(module)
    test_wood_storage_where_is_config_driven(module)
    test_vendor_gump_list(module)
    test_vendor_gump_answering(module)
    test_vendor_stops_group_by_rune(module)
    test_shipped_vendor_runes(module)
    test_vendor_scheduling(module)
    test_reported_wait_is_believed(module)
    test_vendor_defaults(module)
    test_job_validation(module)
    test_shipped_jobs(module)
    test_task_registry(module)
    test_hostile_filter_is_bounded(module)
    test_axe_by_graphic(module)
    test_meditation_does_not_predisarm(module)
    test_axe_matching(module)

    print()
    if FAILURES:
        print("FAILED (%d):" % len(FAILURES))
        for name in FAILURES:
            print("  -", name)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
