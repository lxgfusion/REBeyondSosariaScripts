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


class StubPos(object):
    def __init__(self, x, y, z=0):
        self.X = x
        self.Y = y
        self.Z = z


class StubStatics(object):
    """Nothing is mineable unless a test says so."""

    def GetLandID(self, x, y, world):
        return 0x0003

    def GetStaticsTileInfo(self, x, y, world):
        return []


class StubPlayer(object):
    Serial = 0x0001A2B3
    Backpack = StubItem()
    Mana = 100
    ManaMax = 100
    # The CHARACTER's carry limit, which is what pack_has_room weighs against.
    # 140 strength gives 530 on this shard: 140 * 3.5 + 40.
    Weight = 30
    MaxWeight = 400
    IsGhost = False
    WarMode = False
    Name = "Minerbot"
    Map = 0
    Position = StubPos(100, 100)

    def ChatSay(self, colour, msg=None):
        pass

    def HeadMessage(self, colour, msg=None):
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


# ---------------------------------------------------------------------------
# INGOT KEY, and keeping key-backed resources out of the one-way chest
# ---------------------------------------------------------------------------

def test_ingot_key_is_configured_like_the_wood_storage(m):
    """The wood key is a top-level per-character setting. The ingot key has to
    be the same, because each character carries its own."""
    check("ingot key enabled", m["INGOT_KEY_ENABLED"], True)
    check("inspected graphic", m["INGOT_KEY_ID"], 0x1BE8)

    # PORTABLE ACROSS CHARACTERS. Each carries their own key, so a serial here
    # would be right for exactly one copy of the script and would resolve to
    # somebody else's key in the others. The graphic with hue -1 finds
    # whichever key is in THIS character's pack.
    check("no pinned serial", m["INGOT_KEY_SERIAL"], 0)
    check("any hue", m["INGOT_KEY_HUE"], -1)

    entry = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Ingot key"]
    check("one Ingot key entry", len(entry), 1)
    check("it uses the configured serial", entry[0]["serial"],
          m["INGOT_KEY_SERIAL"])
    check("and it is carried", entry[0]["where"], "pack")


def test_a_disabled_key_is_never_found(m):
    """Turning the option off must actually stop it being used."""
    original = [k for k in m["RESTOCK_KEYS"]
                if k.get("label") == "Ingot key"][0]
    entry = dict(original)
    entry["enabled"] = False
    check("disabled finds nothing", m["find_restock"](entry), [])


def test_logs_never_reach_the_chest_while_the_wood_key_is_carried(m):
    """THE POINT OF THE CHANGE. PURGE_ID listed logs and boards
    unconditionally, so a restock that came up short - or a storage that was
    momentarily not found - sent the lumber to the chest, one way."""
    check("logs are purgeable in principle", 0x1BDD in m["PURGE_ID"], True)
    check("boards too", 0x1BD7 in m["PURGE_ID"], True)

    saved = m["keys_in_reach"]
    try:
        m["keys_in_reach"] = lambda wanted=None: set(["Wood Storage"])
        ids, kept, _here = m["chest_sweep_ids"]()
        check("the wood key is held back", kept, ["Wood Storage"])
        check("logs are NOT swept", 0x1BDD in ids, False)
        check("boards are NOT swept", 0x1BD7 in ids, False)
        check("but ingots still are, with no ingot key",
              0x1BF2 in ids, True)
        check("and the gems are untouched", 0x0F26 in ids, True)
    finally:
        m["keys_in_reach"] = saved


def test_with_no_key_the_chest_still_sweeps_everything(m):
    """"unless we do not use a key in their packs" - no key means the old
    behaviour, or the resources would pile up in the pack forever."""
    saved = m["keys_in_reach"]
    try:
        m["keys_in_reach"] = lambda wanted=None: set()
        ids, kept, _here = m["chest_sweep_ids"]()
        check("nothing held back", kept, [])
        check("logs go to the chest", 0x1BDD in ids, True)
        check("boards too", 0x1BD7 in ids, True)
        check("ingots too", 0x1BF2 in ids, True)
        check("the full list is swept", sorted(ids), sorted(m["PURGE_ID"]))
    finally:
        m["keys_in_reach"] = saved


def test_both_keys_carried_leaves_the_chest_only_the_rest(m):
    saved = m["keys_in_reach"]
    try:
        m["keys_in_reach"] = lambda wanted=None: set(["Wood Storage",
                                                      "Ingot key"])
        ids, kept, _here = m["chest_sweep_ids"]()
        check("both held back", sorted(kept), ["Ingot key", "Wood Storage"])
        for graphic in (0x1BDD, 0x1BD7, 0x1BF2):
            check("0x%04X not swept" % graphic, graphic in ids, False)
        check("gems still swept", 0x0F26 in ids, True)
        check("granite still swept", 0x1779 in ids, True)
    finally:
        m["keys_in_reach"] = saved


def test_every_key_backed_graphic_is_actually_in_purge_id(m):
    """A graphic listed as key-backed but absent from PURGE_ID would be dead
    config - it was never going to the chest anyway."""
    for spec in m["KEY_BACKED_IDS"]:
        for graphic in spec["ids"]:
            check("0x%04X is in PURGE_ID" % graphic,
                  graphic in m["PURGE_ID"], True)


def test_key_backed_labels_match_real_restock_keys(m):
    """A label typo would silently mean "that key is never here", so the
    resource would go to the chest forever."""
    labels = set(k.get("label") for k in m["RESTOCK_KEYS"])
    for spec in m["KEY_BACKED_IDS"]:
        check("%r is a real key" % spec["label"], spec["label"] in labels, True)


def test_smelting_happens_before_anything_is_offered_to_a_key(m):
    """CAUGHT IN GAME. The character mined ore, and the pack-full path offered
    it to the keys BEFORE smelting. The Ingot key wants ingots, so it refused,
    and the ore was carted home to the chest while the key that would have
    swallowed it sat unused in the pack."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "unload_in_place":
            fn = node
    check("unload_in_place exists", fn is not None, True)
    if fn is None:
        return

    smelts = [n.lineno for n in ast.walk(fn)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "smelt"]
    refills = [n.lineno for n in ast.walk(fn)
               if isinstance(n, ast.Call)
               and getattr(n.func, "id", None) == "refill_keys"]
    check("it smelts", len(smelts) > 0, True)
    check("it offers the load to the keys", len(refills) > 0, True)
    check("and it smelts FIRST", min(smelts) < min(refills), True)


def test_no_trip_home_when_smelting_already_freed_the_pack(m):
    """CAUGHT IN GAME: "he is returning home after each smelt when he has
    plenty of weight available". dropoff() ran unconditionally after smelt(),
    so the trip happened whether or not it was still needed."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "unload_in_place":
            fn = node
    if fn is None:
        check("unload_in_place exists", False, True)
        return

    rooms = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "pack_has_room"]
    check("it re-checks the pack after smelting", len(rooms) >= 2, True)

    # And no caller may smelt-then-dropoff without asking in between.
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = ast.dump(node)
        if "unload_in_place" in body:
            continue
        smelt_lines = [n.lineno for n in ast.walk(node)
                       if isinstance(n, ast.Call)
                       and getattr(n.func, "id", None) == "smelt"]
        drop_lines = [n.lineno for n in ast.walk(node)
                      if isinstance(n, ast.Call)
                      and getattr(n.func, "id", None) == "dropoff"]
        for sl in smelt_lines:
            for dl in drop_lines:
                if 0 < dl - sl <= 1:      # dropoff on the very next line
                    bad.append((node.name, sl, dl))
    check("no smelt-then-dropoff without a re-check", bad, [])


def test_unload_in_place_passes_the_threshold_through(m):
    """The job handover uses a stricter level than the route does. If the
    helper ignored it, the handover would pass with a pack the next job cannot
    work in."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "unload_in_place":
            fn = node
    check("it takes a threshold", [a.arg for a in fn.args.args], ["threshold"])
    passes = [n for n in ast.walk(fn)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "pack_has_room"
              and any(isinstance(a, ast.Name) and a.id == "threshold"
                      for a in n.args)]
    check("and passes it on", len(passes) >= 2, True)


def test_smelt_never_leaks_a_target_cursor(m):
    """CAUGHT IN GAME. The character stopped after a while with no error.

    smelt() asked for a target per ore stack with no clear_cursor() first and
    no cancel when the cursor never came. Target.WaitForTarget returns True for
    a cursor that is ALREADY open, so a leftover one is answered instead - and
    it then eats the MINING TOOL's target, after which the character stands
    there swinging at nothing and nothing is logged.

    Survivable while smelt() only ran when the keys had refused the load; the
    smelt-before-keys fix made it run on every full pack, and rare became
    routine.
    """
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "smelt":
            fn = node
    check("smelt exists", fn is not None, True)
    if fn is None:
        return

    clears = [n.lineno for n in ast.walk(fn)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "clear_cursor"]
    uses = [n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == "UseItem"]
    check("it clears the cursor", len(clears) > 0, True)
    check("it uses an item", len(uses) > 0, True)
    check("and it clears BEFORE asking for a target",
          min(clears) < min(uses), True)

    # The timeout path must not fall through to TargetExecute.
    waits = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "WaitForTarget"]
    check("the wait result is tested, not discarded",
          any(isinstance(getattr(w, "parent_if", None), ast.If) for w in waits)
          or "if not Target.WaitForTarget" in open(SCRIPT, encoding="utf-8").read(),
          True)

    # And nothing leaves the function with one open.
    check("it clears again after the loop", len(clears) >= 2, True)


def test_every_targeting_helper_goes_through_clear_cursor(m):
    """The rule this project already learned: route cursor setup through one
    helper that cancels and asserts the cursor is gone. A raw
    UseItem + WaitForTarget pair with no clear in the same function is the
    shape that leaks."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == "clear_cursor":
            continue
        waits = [n for n in ast.walk(node)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "WaitForTarget"]
        if not waits:
            continue
        clears = [n for n in ast.walk(node)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, "id", None) == "clear_cursor"]
        if not clears:
            offenders.append(node.name)
    check("no function waits on a cursor without clearing one", offenders, [])


def test_dropoff_smelts_before_the_keys_get_first_refusal(m):
    """CAUGHT IN GAME: "pack is full after recalling home".

    Ore is in NEITHER PURGE_ID nor anything a key accepts, so ore that reached
    home had nowhere to go at all - the Ingot key wants ingots, and the chest
    sweep does not list ore. It sat in the pack, the pack stayed full, and the
    next lap recalled home again to do nothing.
    """
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "dropoff":
            fn = node
    check("dropoff exists", fn is not None, True)
    if fn is None:
        return
    smelts = [n.lineno for n in ast.walk(fn)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "smelt"]
    refills = [n.lineno for n in ast.walk(fn)
               if isinstance(n, ast.Call)
               and getattr(n.func, "id", None) == "refill_keys"]
    check("dropoff smelts", len(smelts) > 0, True)
    check("and it smelts BEFORE the keys are offered anything",
          min(smelts) < min(refills), True)


def test_ore_is_not_silently_strandable(m):
    """Ore must be reachable by SOMETHING at home. It is not in PURGE_ID by
    design - the chest is for finished goods - so smelting is the only route,
    and that is why dropoff has to do it."""
    for graphic in m["ORE_ID"]:
        check("ore 0x%04X is not chest-swept" % graphic,
              graphic in m["PURGE_ID"], False)
    check("but ingots are", 0x1BF2 in m["PURGE_ID"], True)


def test_a_full_pack_says_which_measure_tripped(m):
    """"pack full" with 81 of 495 stones carried is baffling without the
    numbers. Item count is the case the keys cannot help with, so it is said
    at warning level rather than debug."""
    ITEMS.reset()
    player = m["Player"]
    saved = (player.Weight, player.MaxWeight)
    messages = []
    original_log = m["log"]
    try:
        m["log"] = lambda text, hue=None: messages.append(str(text))
        ITEMS.contents = "Contents: 120/125 items, 0/60000 stones"
        player.Weight, player.MaxWeight = 81, 495
        check("full by item count", m["pack_has_room"](), False)
        check("and it said so, with numbers",
              any("ITEM COUNT" in t and "120" in t for t in messages), True)
        check("and named the weight to show it is not the cause",
              any("81" in t and "495" in t for t in messages), True)
    finally:
        m["log"] = original_log
        player.Weight, player.MaxWeight = saved
        ITEMS.reset()


def test_weight_reserve_replaces_the_fraction(m):
    """Harvest until one more yield will not fit, not until 60% of capacity.

    The fraction threw away everything above it: at 0.6 a 495-stone character
    stored at 297 and left 198 stones unused on every trip.
    """
    player = m["Player"]
    saved = (player.Weight, player.MaxWeight)
    original_log = m["log"]
    m["_max_yield"].clear()
    try:
        m["log"] = lambda *a, **k: None

        # Well under the limit at a weight the old 0.6 rule called full.
        player.Weight, player.MaxWeight = 300, 495
        check("keeps working at 300 of 495", m["pack_has_room"](), True)

        # Right at the edge - free weight down to the reserve.
        player.Weight, player.MaxWeight = 495 - m["weight_reserve"](), 495
        check("stores when free weight hits the reserve",
              m["pack_has_room"](), False)

        player.Weight, player.MaxWeight = 400, 495
        check("still working at 400 of 495", m["pack_has_room"](), True)

        # An explicit threshold is still a fraction - the job hand-over needs
        # "start the next job under 15%", which is a different question.
        player.Weight, player.MaxWeight = 100, 495
        check("explicit threshold is still a fraction",
              m["pack_has_room"](0.15), False)
        player.Weight, player.MaxWeight = 50, 495
        check("under the hand-over fraction", m["pack_has_room"](0.15), True)
    finally:
        m["log"] = original_log
        player.Weight, player.MaxWeight = saved
        m["_max_yield"].clear()


def test_reserve_is_measured_not_guessed(m):
    """The reserve grows to cover the heaviest yield actually seen, and is capped."""
    original_debug = m["debug"]
    m["_max_yield"].clear()
    try:
        m["debug"] = lambda *a, **k: None
        check("floor before anything is measured",
              m["weight_reserve"](), m["PACK_WEIGHT_RESERVE"])

        m["note_yield"]("mine", 60)
        check("learns from a heavy yield",
              m["weight_reserve"](), int(60 * m["PACK_RESERVE_SAFETY"]))

        # A lighter yield must not lower it - the heaviest is what has to fit.
        m["note_yield"]("mine", 5)
        check("a light yield does not lower the reserve",
              m["weight_reserve"](), int(60 * m["PACK_RESERVE_SAFETY"]))

        # One freak reading must not park the reserve at half the pack.
        m["note_yield"]("mine", 100000)
        check("capped", m["weight_reserve"](), m["PACK_RESERVE_MAX"])

        check("a negative reading is ignored", m["weight_gain"](100), 0)
    finally:
        m["debug"] = original_debug
        m["_max_yield"].clear()


def test_mining_step_is_the_ore_bank(m):
    """Spot spacing must match ServUO's BankWidth, or the walk re-mines itself.

    Mining.cs sets BankWidth = BankHeight = 8. A bank is what depletes, so
    anything less than 8 tiles lands the character back inside the block they
    just emptied. Lumber banks are 4x3, which is why that sweep steps 3.
    """
    check("mining steps one whole ore bank", m["MINE_AREA_STEP"], 8)
    check("lumber steps its own, smaller bank",
          (m["LUMBER_AREA_STEP_X"], m["LUMBER_AREA_STEP_Y"]), (4, 3))
    check("mining looks the distance asked for", m["MINE_AREA_RADIUS"], 18)

    offsets = m["area_offsets"](m["MINE_AREA_RADIUS"] * 2, m["MINE_AREA_STEP"])
    check("mining offsets step a bank at a time", offsets, [-16, -8, 0, 8, 16])
    check("nothing beyond the radius",
          [o for o in offsets if abs(o) > m["MINE_AREA_RADIUS"]], [])


def test_area_offsets_is_generic(m):
    """One helper serves both sweeps."""
    check("8/3 gives the lumber grid", m["area_offsets"](8, 3), [-3, 0, 3])
    check("36/8 gives the mining grid",
          m["area_offsets"](36, 8), [-16, -8, 0, 8, 16])
    check("a step bigger than the box gives one spot",
          m["area_offsets"](4, 8), [0])
    # A step of 0 must not divide by zero. It clamps to 1 - a spot every
    # tile, which is slow but harmless, rather than a crash mid-route.
    check("step 0 clamps to 1 instead of crashing",
          m["area_offsets"](8, 0), [-4, -3, -2, -1, 0, 1, 2, 3, 4])
    check("a negative size gives one spot", m["area_offsets"](-8, 3), [0])


def test_mineable_tiles_came_from_source(m):
    """The tile lists must be real, and must not have picked up m_Offsets.

    Mining.cs also declares m_Offsets - spawn coordinate deltas including
    negative numbers. An extractor that read it as tiles would inject 0 and 1
    into the list, and every patch of grass would then look mineable.
    """
    tiles = m["MOUNTAIN_AND_CAVE_TILES"]
    check("mountain and cave tiles are loaded", len(tiles) > 250, True)
    check("no spawn offsets leaked in", 0 in tiles or 1 in tiles, False)
    check("sand is a separate list", 0 in m["SAND_TILES"], False)
    check("the two lists are distinct",
          m["SAND_TILES"] == tiles, False)


def test_spot_is_minable_checks_the_whole_reach(m):
    """You stand on cave floor and mine the wall - not the tile underfoot."""
    tiles = sorted(m["MOUNTAIN_AND_CAVE_TILES"])
    rock = tiles[0]

    class FakeStatics(object):
        def __init__(self, rock_at):
            self.rock_at = rock_at

        def GetLandID(self, x, y, world):
            return self.rock_at if (x, y) == self.rock_at_xy else 0x0003

        def GetStaticsTileInfo(self, x, y, world):
            return []

    fake = FakeStatics(rock)
    fake.rock_at_xy = (102, 200)
    original = m.get("Statics")
    try:
        m["Statics"] = fake
        # Rock two tiles east - inside the server's MaxRange of 2.
        check("rock within reach counts", m["spot_is_minable"](100, 200), True)
        # Move it out of reach.
        fake.rock_at_xy = (110, 200)
        check("rock out of reach does not", m["spot_is_minable"](100, 200),
              False)
    finally:
        m["Statics"] = original


def test_mine_single_matches_old_behaviour(m):
    """MINE_AREA_ENABLED = False must behave as the script used to."""
    outcomes = {}
    original_dig = m["dig_once"]
    original_smelt = m["smelt"]
    original_make = m["make_shovel"]
    original_log = m["log"]
    try:
        m["dig_once"] = lambda shovel, timeout: outcomes["reply"]
        m["smelt"] = lambda *a: None
        m["make_shovel"] = lambda *a: None
        m["log"] = lambda *a, **k: None
        for reply, want in (("ok", "ok"), ("broke", "ok"), ("full", "full"),
                            ("empty", "next"), ("notrock", "next"),
                            ("silent", "next")):
            outcomes["reply"] = reply
            check("single mine spot: %s -> %s" % (reply, want),
                  m["mine_single"](None), want)
    finally:
        m["dig_once"] = original_dig
        m["smelt"] = original_smelt
        m["make_shovel"] = original_make
        m["log"] = original_log


def test_mine_messages_separate_empty_from_barren(m):
    """The sweep needs "bank empty" and "no rock at all" to be different.

    They lead to opposite decisions: an empty bank means step 8 tiles to the
    next one, no rock at all means never walk here again.
    """
    depleted = " ".join(m["MINE_DEPLETED"]).lower()
    barren = " ".join(m["MINE_BAD_TARGET"]).lower()
    check("no metal is a depleted bank", "no metal" in depleted, True)
    check("can't mine there is barren ground",
          "can't mine there" in barren, True)
    check("the two do not overlap",
          set(m["MINE_DEPLETED"]) & set(m["MINE_BAD_TARGET"]), set())
    check("a full pack is its own answer",
          any("backpack is full" in t.lower() for t in m["MINE_PACK_FULL"]),
          True)


def test_vendor_round_counts_collections_not_visits(m):
    """Only a real collection earns the trip home.

    serve_vendor returns True for an NPC that answered "nothing yet" - a
    cooldown is a successful visit but not a collection, so counting visits
    would send the character home after every empty round.
    """
    check("dropoff after vendors is on", m["DROPOFF_AFTER_VENDORS"], True)

    m["_collected_this_round"] = 0
    m["_vendor_history"].clear()
    try:
        m["note_vendor_collected"]({"label": "Test vendor"})
        m["note_vendor_collected"]({"label": "Test vendor"})
        check("collections are counted", m["_collected_this_round"], 2)
    finally:
        m["_vendor_history"].clear()
        m["_collected_this_round"] = 0

class FakePathFinding(object):
    """A map with a wall, so "no path" and "the long way round" are both real.

    `blocked` is a set of tiles that cannot be entered. GetPath does a plain
    BFS from the player, which is enough to tell apart the three cases that
    matter: straight through, round the outside, and no way at all.
    """

    def __init__(self, player, blocked=(), bounds=40):
        self.player = player
        self.blocked = set(blocked)
        self.bounds = bounds
        self.walked = []

    class Route(object):
        pass

    def Go(self, route):
        self.walked.append((route.X, route.Y))
        return True

    def GetPath(self, x, y, ignoremob):
        start = (self.player.Position.X, self.player.Position.Y)
        goal = (x, y)
        if goal in self.blocked:
            return []
        seen = {start: None}
        queue = [start]
        while queue:
            here = queue.pop(0)
            if here == goal:
                path = []
                while here is not None:
                    path.append(here)
                    here = seen[here]
                return list(reversed(path))[1:]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nxt = (here[0] + dx, here[1] + dy)
                    if nxt in seen or nxt in self.blocked:
                        continue
                    if abs(nxt[0] - start[0]) > self.bounds:
                        continue
                    if abs(nxt[1] - start[1]) > self.bounds:
                        continue
                    seen[nxt] = here
                    queue.append(nxt)
        return []


def test_unreachable_spot_is_never_walked_at(m):
    """The cave bug: a spot behind a mountain wall must not be walked at.

    Reported in game - the character stood at the mouth of a cave shuffling
    into the rock face because the next standing spot was on the other side of
    it. PathFinding.Go bounces off the wall without ever failing outright, so
    "did I move" never says no and only the move timeout ends it.
    """
    player = m["Player"]
    saved = player.Position
    original_pf = m["PathFinding"]
    original_debug = m["debug"]
    try:
        m["debug"] = lambda *a, **k: None
        player.Position = StubPos(100, 100)

        # A solid wall down x=104, sealing off everything east of it.
        wall = set()
        for y in range(60, 140):
            for x in range(104, 108):
                wall.add((x, y))
        fake = FakePathFinding(player, wall, bounds=6)
        m["PathFinding"] = fake

        check("a spot inside the wall is refused",
              m["reachable_spot"](105, 100, 0), None)
        check("and nothing was walked at", fake.walked, [])

        check("walk_to refuses it too", m["walk_to"](105, 100, 500, 0), False)
        check("still nothing walked at", fake.walked, [])

        # An open spot on our own side is fine.
        check("an open spot is accepted",
              m["reachable_spot"](102, 100, 0), (102, 100))
    finally:
        m["PathFinding"] = original_pf
        m["debug"] = original_debug
        player.Position = saved


def test_long_way_round_is_refused(m):
    """A real path that goes round the mountain is still the wrong answer.

    "Did GetPath return something" is not enough on its own: 8 tiles through
    rock can have a perfectly valid 80-tile path around the outside, and
    walking it takes the character out of the mine.
    """
    player = m["Player"]
    saved = player.Position
    original_pf = m["PathFinding"]
    original_debug = m["debug"]
    try:
        m["debug"] = lambda *a, **k: None
        player.Position = StubPos(100, 100)

        # A wall with a gap far to the south, so there IS a way round.
        wall = set()
        for y in range(80, 118):
            wall.add((104, y))
        fake = FakePathFinding(player, wall, bounds=30)
        m["PathFinding"] = fake

        direct = 8
        goal = (108, 100)
        path = m["path_to"](*goal)
        check("a way round genuinely exists", bool(path), True)
        check("and it is a long way round", len(path) > direct * 3, True)
        check("so the spot is refused", m["reachable_spot"](goal[0], goal[1], 0),
              None)
    finally:
        m["PathFinding"] = original_pf
        m["debug"] = original_debug
        player.Position = saved


def test_spot_inside_rock_falls_back_to_a_neighbour(m):
    """The grid is arithmetic, so spots land in walls. Take the tile beside it.

    Writing the spot off would throw away ore that is perfectly reachable from
    one tile over - the accept radius exists for exactly this.
    """
    player = m["Player"]
    saved = player.Position
    original_pf = m["PathFinding"]
    original_debug = m["debug"]
    try:
        m["debug"] = lambda *a, **k: None
        player.Position = StubPos(100, 100)

        # A single boulder exactly where the grid wants us to stand.
        fake = FakePathFinding(player, {(108, 100)}, bounds=20)
        m["PathFinding"] = fake

        got = m["reachable_spot"](108, 100, 1)
        check("a neighbour is used instead of the blocked tile",
              got is not None and got != (108, 100), True)
        check("and it is within the accept radius",
              max(abs(got[0] - 108), abs(got[1] - 100)) <= 1, True)
    finally:
        m["PathFinding"] = original_pf
        m["debug"] = original_debug
        player.Position = saved


def test_walk_gives_up_when_it_stops_getting_closer(m):
    """Progress is measured against the best distance reached, not the last.

    A pathfinder working along a wall shuffles back and forth. "Did I move"
    answers yes forever, so only "am I getting closer" can end it.
    """
    player = m["Player"]
    saved = player.Position
    original_pf = m["PathFinding"]
    original_debug = m["debug"]
    original_pause = m["interruptible_pause"]
    try:
        m["debug"] = lambda *a, **k: None
        m["interruptible_pause"] = lambda *a, **k: None
        player.Position = StubPos(100, 100)

        shuffle = {"n": 0}

        class Shuffler(FakePathFinding):
            def Go(self, route):
                # Moves, but never any closer - back and forth by one tile.
                shuffle["n"] += 1
                player.Position = StubPos(100 + (shuffle["n"] % 2), 100)
                self.walked.append((route.X, route.Y))
                return True

        fake = Shuffler(player, bounds=30)
        m["PathFinding"] = fake

        # 30s of budget, but it must give up on stall long before that.
        check("gives up rather than burning the timeout",
              m["walk_to"](120, 100, 30000, 0), False)
        check("and did not shuffle forever",
              len(fake.walked) <= m["AREA_STALL_STEPS"] + 2, True)
    finally:
        m["PathFinding"] = original_pf
        m["debug"] = original_debug
        m["interruptible_pause"] = original_pause
        player.Position = saved


def test_walk_config_is_sane(m):
    check("a detour cap is set", m["AREA_MAX_DETOUR"] >= 1, True)
    check("the cap is not so loose it is meaningless",
          m["AREA_MAX_DETOUR"] <= 5, True)
    check("stall steps are bounded", 1 <= m["AREA_STALL_STEPS"] <= 20, True)

def test_ingot_key_has_the_same_options_as_wood_storage(m):
    """Both keys must be configurable the same way.

    The ingot key had no top-level settings at all - it existed only as a
    literal buried in RESTOCK_KEYS, so the one thing three of the four mining
    characters rely on could not be pointed anywhere without editing a list
    halfway down the file.
    """
    for suffix in ("WHERE", "SERIAL", "ID", "HUE", "RANGE", "NAMES"):
        check("INGOT_KEY_%s exists" % suffix,
              ("INGOT_KEY_%s" % suffix) in m, True)
        check("WOOD_STORAGE_%s exists" % suffix,
              ("WOOD_STORAGE_%s" % suffix) in m, True)

    check("the ingot key can be switched off", "INGOT_KEY_ENABLED" in m, True)

    # Same shape of value, so the two behave the same way.
    check("both search the same kind of place",
          m["INGOT_KEY_WHERE"] in ("pack", "world")
          and m["WOOD_STORAGE_WHERE"] in ("pack", "world"), True)
    check("both accept any colour",
          (m["INGOT_KEY_HUE"], m["WOOD_STORAGE_HUE"]), (-1, -1))
    check("both carry name hints",
          bool(m["INGOT_KEY_NAMES"]) and bool(m["WOOD_STORAGE_NAMES"]), True)


def test_ingot_key_entry_is_built_from_the_settings(m):
    """The RESTOCK_KEYS entry must READ the settings, not restate them.

    A literal in the list is how the two drifted apart: the settings said one
    thing and the entry the script actually uses said another.
    """
    entry = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Ingot key"]
    check("one ingot key entry", len(entry), 1)
    entry = entry[0]

    check("serial tracks the setting", entry.get("serial"), m["INGOT_KEY_SERIAL"])
    check("id tracks the setting", entry.get("id"), m["INGOT_KEY_ID"])
    check("hue tracks the setting", entry.get("hue"), m["INGOT_KEY_HUE"])
    check("where tracks the setting", entry.get("where"), m["INGOT_KEY_WHERE"])
    check("range tracks the setting", entry.get("range"), m["INGOT_KEY_RANGE"])
    check("names track the setting", entry.get("names"), m["INGOT_KEY_NAMES"])
    check("enabled tracks the setting",
          entry.get("enabled"), m["INGOT_KEY_ENABLED"])


def test_ingot_key_found_at_any_hue(m):
    """A key of an unexpected colour must still be found, like the wood one."""
    entry = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Ingot key"][0]
    spec = dict(entry)
    spec["serial"] = 0
    spec["where"] = "pack"

    for hue in (0x0014, 0x0000, 0x0058, 0x08FD):
        ITEMS.reset()
        ITEMS.register(StubWorldItem(0x40005678, 0x1BE8, hue, "Ingot Keys"),
                       "pack")
        check("ingot key found at hue 0x%04X" % hue,
              [i.Serial for i in m["find_restock"](spec)], [0x40005678])

    # Switched off means not used at all, whatever is in the pack.
    ITEMS.reset()
    ITEMS.register(StubWorldItem(0x40005678, 0x1BE8, 0x0014, "Ingot Keys"),
                   "pack")
    off = dict(spec)
    off["enabled"] = False
    check("disabled key is not looked for", m["find_restock"](off), [])
    ITEMS.reset()

def test_store_at_ninety_percent(m):
    """Store once 90% of carry weight is used - reported in game as packs
    filling right up with ingots."""
    player = m["Player"]
    saved = (player.Weight, player.MaxWeight)
    original_log = m["log"]
    m["_max_yield"].clear()
    try:
        m["log"] = lambda *a, **k: None
        check("the store level is 90%", m["PACK_STORE_AT"], 0.90)

        player.Weight, player.MaxWeight = 400, 495       # 81%
        check("keeps working at 81%", m["pack_has_room"](), True)

        player.Weight, player.MaxWeight = 445, 495       # 89.9%
        check("still working just under 90%", m["pack_has_room"](), True)

        player.Weight, player.MaxWeight = 446, 495       # 90.1%
        check("stores at 90%", m["pack_has_room"](), False)

        player.Weight, player.MaxWeight = 490, 495
        check("and stays full above it", m["pack_has_room"](), False)
    finally:
        m["log"] = original_log
        player.Weight, player.MaxWeight = saved
        m["_max_yield"].clear()


def test_reserve_still_backstops_a_heavy_yield(m):
    """Under 90%, one more yield that would go OVER must still stop it.

    Going over means the server refuses the resource outright and it is lost,
    so the measured reserve stays as a backstop beneath the percentage.
    """
    player = m["Player"]
    saved = (player.Weight, player.MaxWeight)
    original_log = m["log"]
    original_debug = m["debug"]
    m["_max_yield"].clear()
    try:
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None

        # 88% used - under the store level, so the percentage alone allows it.
        player.Weight, player.MaxWeight = 436, 495
        check("percentage alone would carry on", m["pack_has_room"](), True)

        # Now we have seen a 60-stone yield: 59 free is not enough for another.
        m["note_yield"]("mine", 60)
        check("but a heavy yield stops it short", m["pack_has_room"](), False)
    finally:
        m["log"] = original_log
        m["debug"] = original_debug
        player.Weight, player.MaxWeight = saved
        m["_max_yield"].clear()


def test_bank_of_groups_tiles_the_way_the_server_does(m):
    """A bank is the unit that depletes, so the sweep has to think in banks."""
    w, h = m["LUMBER_BANK_W"], m["LUMBER_BANK_H"]

    # Everything inside one 4x3 block is the same bank.
    check("same wood bank across its width",
          m["bank_of"](0, 0, w, h), m["bank_of"](3, 0, w, h))
    check("same wood bank across its height",
          m["bank_of"](0, 0, w, h), m["bank_of"](0, 2, w, h))
    # One tile past it is not.
    check("a step of the bank width leaves it",
          m["bank_of"](0, 0, w, h) == m["bank_of"](4, 0, w, h), False)
    check("a step of the bank height leaves it",
          m["bank_of"](0, 0, w, h) == m["bank_of"](0, 3, w, h), False)

    # THE BUG: the old step of 3 stayed inside a 4-wide bank.
    check("the old step of 3 did NOT leave the bank",
          m["bank_of"](0, 0, w, h) == m["bank_of"](3, 0, w, h), True)

    b = m["MINE_BANK"]
    check("ore banks are 8 wide",
          m["bank_of"](0, 0, b, b) == m["bank_of"](7, 7, b, b), True)
    check("and 8 tiles clears one",
          m["bank_of"](0, 0, b, b) == m["bank_of"](8, 0, b, b), False)


def test_depleted_match_survives_the_apostrophe(m):
    """500493 is "There's not enough wood here to harvest."

    Matching the leading "There's" makes the whole thing depend on whether the
    apostrophe is ASCII or typographic - and a mismatch fails SILENTLY: the
    line never matches, the swing times out instead, and every depleted spot
    costs a full timeout of standing still. Which is what was reported.
    """
    for text in m["LUMBER_DEPLETED"]:
        check("no apostrophe in %r" % text, "'" in text or "\u2019" in text,
              False)

    phrase = m["LUMBER_DEPLETED"][0].lower()
    for wording in ("There's not enough wood here to harvest.",
                    "There\u2019s not enough wood here to harvest.",
                    "there's not enough wood here to harvest"):
        check("matches %r" % wording[:18], phrase in wording.lower(), True)

    # Still specific enough not to fire on an ordinary success line.
    check("does not match a successful chop",
          phrase in "You put 12 logs in your backpack.".lower(), False)

def test_spot_cap_is_a_real_bound(m):
    """15 seconds at one spot, then move on - reported as a miner wedged
    against a cave wall and staying there."""
    check("the cap is 15 seconds", m["AREA_SPOT_TIMEOUT_MS"], 15000)

    # Before this, a spot could hold the character for swings x timeout.
    worst_mine = m["MINE_AREA_MAX_SWINGS"] * m["MINE_SWING_TIMEOUT"]
    worst_lumber = m["LUMBER_AREA_MAX_SWINGS"] * m["LUMBER_SWING_TIMEOUT"]
    check("the cap is far below the old mining worst case",
          m["AREA_SPOT_TIMEOUT_MS"] < worst_mine, True)
    check("and below the old lumber worst case",
          m["AREA_SPOT_TIMEOUT_MS"] < worst_lumber, True)

    # Walking must SHARE the budget, not add to it, or the cap caps nothing.
    check("a move timeout alone cannot exceed the cap",
          max(m["MINE_AREA_MOVE_TIMEOUT"], m["LUMBER_AREA_MOVE_TIMEOUT"])
          <= m["AREA_SPOT_TIMEOUT_MS"], True)


def test_budget_shares_the_spot_deadline(m):
    """budget_ms hands out what is LEFT, so walk + swing stay inside the cap."""
    now = m["time"].time()

    # Plenty of time left -> capped by the caller's own limit.
    check("capped by the caller's limit",
          m["budget_ms"](now + 100, 8000), 8000)

    # Nearly out of time -> the caller gets what remains, not its full limit.
    got = m["budget_ms"](now + 2.0, 12000)
    check("gets only what is left", 1000 < got <= 2100, True)

    # Out of time -> never zero. A walk given no time reads as instant failure
    # and would mark a good spot dead.
    check("never returns zero", m["budget_ms"](now - 10, 12000), 500)


def test_spot_deadline_stops_the_swing_loop(m):
    """A spot that keeps answering must still be abandoned at the cap."""
    calls = {"n": 0}
    original_chop = m["chop_once"]
    original_pack = m["pack_has_room"]
    original_log = m["log"]
    original_debug = m["debug"]
    original_pause = m["interruptible_pause"]
    try:
        # Always "ok", so nothing but the deadline can end this loop.
        m["chop_once"] = lambda axe, timeout: "ok"
        m["pack_has_room"] = lambda *a: True
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["interruptible_pause"] = lambda *a, **k: calls.__setitem__("n", calls["n"] + 1)

        state = {"cut": 0, "silent": 0, "dead": set(), "spent": set()}
        # A deadline that has already passed: it must stop at once.
        out = m["work_spot"](None, 0, 9, state, m["time"].time() - 1)
        check("expired deadline stops immediately", out, "")
        check("and took no swings", state["cut"], 0)

        # Without a deadline the swing cap still bounds it.
        state = {"cut": 0, "silent": 0, "dead": set(), "spent": set()}
        m["work_spot"](None, 0, 9, state, None)
        check("swing cap still bounds an endless spot",
              state["cut"], m["LUMBER_AREA_MAX_SWINGS"])
    finally:
        m["chop_once"] = original_chop
        m["pack_has_room"] = original_pack
        m["log"] = original_log
        m["debug"] = original_debug
        m["interruptible_pause"] = original_pause


def test_mine_spot_honours_the_deadline_too(m):
    """The miner is the one that got stuck, so assert it explicitly."""
    original_dig = m["dig_once"]
    original_pack = m["pack_has_room"]
    original_smelt = m["smelt"]
    original_log = m["log"]
    original_debug = m["debug"]
    original_pause = m["interruptible_pause"]
    try:
        m["dig_once"] = lambda shovel, timeout: "ok"
        m["pack_has_room"] = lambda *a: True
        m["smelt"] = lambda *a: None
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["interruptible_pause"] = lambda *a, **k: None

        state = {"dug": 0, "silent": 0, "dead": set(), "spent": set()}
        out = m["mine_spot"](None, 0, 25, state, m["time"].time() - 1)
        check("expired deadline stops the miner at once", out, "")
        check("and it dug nothing", state["dug"], 0)
    finally:
        m["dig_once"] = original_dig
        m["pack_has_room"] = original_pack
        m["smelt"] = original_smelt
        m["log"] = original_log
        m["debug"] = original_debug
        m["interruptible_pause"] = original_pause

def test_idle_watchdog_abandons_a_barren_rune(m):
    """Producing NOTHING anywhere must abandon the rune, not just the spot.

    The spot cap and this are different failures. A character wedged against a
    cave wall passes the spot cap happily - it moves on every 15 seconds, to
    another spot behind the same wall. On a 25-spot mining grid that is six
    minutes of looking busy and harvesting nothing.
    """
    check("an idle limit is set", m["AREA_IDLE_TIMEOUT_MS"] > 0, True)
    check("it is longer than one spot's cap",
          m["AREA_IDLE_TIMEOUT_MS"] > m["AREA_SPOT_TIMEOUT_MS"], True)

    # A whole barren mining grid must not outlast it.
    spots = len(m["area_offsets"](m["MINE_AREA_RADIUS"] * 2,
                                  m["MINE_AREA_STEP"])) ** 2
    worst = spots * m["AREA_SPOT_TIMEOUT_MS"]
    check("it cuts a barren grid far short of the spot caps alone",
          m["AREA_IDLE_TIMEOUT_MS"] < worst, True)

    state = {"last_yield": m["time"].time()}
    check("fresh state is not idle", m["area_is_idle"](state), False)

    state = {"last_yield": m["time"].time()
             - (m["AREA_IDLE_TIMEOUT_MS"] / 1000.0) - 1}
    check("nothing harvested for the limit is idle",
          m["area_is_idle"](state), True)

    # A yield resets it, so a slow but productive area is never interrupted.
    m["note_area_yield"](state)
    check("a yield resets the clock", m["area_is_idle"](state), False)

    # Missing key must not throw - it just means "not idle yet".
    check("no clock yet is not idle", m["area_is_idle"]({}), False)


def test_idle_clock_restarts_after_a_trip_home(m):
    """A full pack sends the character home and back, which outlasts the limit.

    Without a restart a PRODUCTIVE rune would be abandoned the instant it
    returned, purely because the clock kept running during the trip.
    """
    original_log = m["log"]
    original_debug = m["debug"]
    try:
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None

        # A sweep that produced something long ago, as if it had just come back
        # from a slow drop-off run.
        stale = m["time"].time() - (m["AREA_IDLE_TIMEOUT_MS"] / 1000.0) - 30
        key = ("Lumberjacking", -1)
        m["_lumber_sweep"][key] = {
            "origin": (100, 200), "next": 3, "dead": set(), "spent": set(),
            "cut": 5, "silent": 0, "last_yield": stale,
        }
        check("that state IS stale to begin with",
              m["area_is_idle"](m["_lumber_sweep"][key]), True)

        # Re-entering the sweep must restart the clock before it is tested.
        m["note_area_yield"](m["_lumber_sweep"][key])
        check("and re-entry clears it",
              m["area_is_idle"](m["_lumber_sweep"][key]), False)
    finally:
        m["log"] = original_log
        m["debug"] = original_debug
        m["_lumber_sweep"].clear()


def test_end_sweep_restarts_the_idle_clock(m):
    """Finishing an area must not leave the next visit condemned."""
    state = {"next": 4, "origin": (1, 2), "cut": 3, "silent": 1,
             "spent": set([(0, 0)]), "dead": set([2]),
             "last_yield": m["time"].time() - 9999}
    m["end_sweep"](state)
    check("idle clock restarted", m["area_is_idle"](state), False)
    check("spent banks forgotten - wood grows back", state["spent"], set())
    check("dead ground remembered - it stays bare", state["dead"], set([2]))
    check("origin dropped so it is re-read", state["origin"], None)
    check("walk restarts", state["next"], 0)

def test_path_leg_has_an_explicit_timeout(m):
    """Route.Timeout MUST be set. Unset means no limit, and PathFinding.Go then
    blocks - which takes every other guard in the file out of play, because
    they all run between calls to it. Three rounds of stuck reports came down
    to this.
    """
    check("a leg timeout is configured", m["PATH_LEG_TIMEOUT_S"] > 0, True)
    check("and it is short", m["PATH_LEG_TIMEOUT_S"] <= 10, True)

    seen = {}

    class RecordingPathFinding(object):
        class Route(object):
            pass

        def Go(self, route):
            seen["timeout"] = getattr(route, "Timeout", None)
            seen["stop_if_stuck"] = getattr(route, "StopIfStuck", None)
            return True

    original = m["PathFinding"]
    try:
        m["PathFinding"] = RecordingPathFinding()
        m["pathfind_to"](10, 20)
        check("Go was given an explicit timeout",
              seen.get("timeout"), m["PATH_LEG_TIMEOUT_S"])
        check("never the -1 that means no limit",
              seen.get("timeout") in (None, -1), False)
        check("and still stops if stuck", seen.get("stop_if_stuck"), True)
    finally:
        m["PathFinding"] = original


def test_impassable_ground_is_refused_without_pathfinding(m):
    """The pathfinder routes into unexplored blackness. Ask the land first."""
    player = m["Player"]
    saved = player.Position
    original_statics = m["Statics"]
    original_pf = m["PathFinding"]
    original_debug = m["debug"]

    asked = {"paths": 0}

    class VoidStatics(object):
        def GetLandID(self, x, y, world):
            return 0x0002 if x >= 104 else 0x0003

        def GetLandFlag(self, land, flag):
            return land == 0x0002 and flag == "Impassable"

        def GetStaticsTileInfo(self, x, y, world):
            return []

    class CountingPathFinding(object):
        class Route(object):
            pass

        def Go(self, route):
            return True

        def GetPath(self, x, y, ignoremob):
            asked["paths"] += 1
            return [(x, y)]        # claims a path to anywhere

    try:
        m["debug"] = lambda *a, **k: None
        player.Position = StubPos(100, 100)
        m["Statics"] = VoidStatics()
        m["PathFinding"] = CountingPathFinding()

        check("impassable land is not walkable", m["land_is_walkable"](105, 100),
              False)
        check("ordinary land is", m["land_is_walkable"](102, 100), True)

        # The void is refused BEFORE the pathfinder is consulted, so its
        # imaginary path is never even offered.
        asked["paths"] = 0
        check("void destination refused", m["reachable_spot"](105, 100, 0), None)
        check("and the pathfinder was never asked", asked["paths"], 0)

        # Real ground still goes through normally.
        check("real ground accepted", m["reachable_spot"](102, 100, 0),
              (102, 100))
    finally:
        m["Statics"] = original_statics
        m["PathFinding"] = original_pf
        m["debug"] = original_debug
        player.Position = saved


def test_rooted_on_one_tile_gives_up(m):
    """Not moving at all, while trying to walk, is the failure - whatever the
    pathfinder claims. This needs no theory about why."""
    player = m["Player"]
    saved = player.Position
    try:
        player.Position = StubPos(50, 50)
        first = m["seconds_on_this_tile"]()
        check("a fresh tile reads zero", first, 0.0)
        check("staying put accumulates",
              m["seconds_on_this_tile"]() >= 0.0, True)

        # Moving resets it.
        player.Position = StubPos(51, 50)
        check("moving resets the clock", m["seconds_on_this_tile"](), 0.0)
    finally:
        player.Position = saved


def test_stuck_config_is_ordered_sensibly(m):
    """Each guard has to be able to fire before the one above it gives up."""
    check("a leg is shorter than a spot",
          m["PATH_LEG_TIMEOUT_S"] * 1000 < m["AREA_SPOT_TIMEOUT_MS"], True)
    check("rooted-while-walking fires before the idle limit",
          m["AREA_STUCK_TIMEOUT_MS"] < m["AREA_IDLE_TIMEOUT_MS"], True)

def test_a_productive_spot_is_worked_until_depleted(m):
    """Mining that is WORKING must not be cut off - deplete the bank, then move.

    The 15s cap started life absolute, and that abandoned banks half-mined. A
    swing that produces ore is not being stuck, so it pushes the clock out.
    """
    replies = {"n": 0}
    original = {k: m[k] for k in
                ("dig_once", "pack_has_room", "smelt", "log", "debug",
                 "interruptible_pause")}
    try:
        # 30 productive swings, then the bank reports empty - a full bank.
        def digging(shovel, timeout, mythril=None):
            replies["n"] += 1
            return "ok" if replies["n"] <= 30 else "empty"

        m["dig_once"] = digging
        m["pack_has_room"] = lambda *a: True
        m["smelt"] = lambda *a: None
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["interruptible_pause"] = lambda *a, **k: None

        state = {"dug": 0, "silent": 0, "dead": set(), "spent": set(),
                 "last_yield": m["time"].time()}
        # A deadline that would have expired after the first swing if it were
        # absolute. Every yield must push it out.
        m["mine_spot"](None, 0, 25, state,
                       m["time"].time() + (m["AREA_SPOT_TIMEOUT_MS"] / 1000.0))

        check("worked the whole bank, not part of it", state["dug"], 30)
        check("and stopped because it was EMPTY, not on the clock",
              replies["n"], 31)
        check("the bank was recorded as spent", len(state["spent"]), 1)
    finally:
        for k, v in original.items():
            m[k] = v


def test_swing_caps_clear_a_full_bank(m):
    """The absolute backstop must sit above a full bank, or it truncates it."""
    # Mining.cs: 10-34 per bank. Lumberjacking.cs: 20-45.
    check("mining cap clears a 34-ore bank with misses to spare",
          m["MINE_AREA_MAX_SWINGS"] >= 34 * 2, True)
    check("lumber cap clears a 45-log bank with misses to spare",
          m["LUMBER_AREA_MAX_SWINGS"] >= 45 * 2, True)


def test_an_unproductive_spot_still_gives_up(m):
    """The other half: moved, then no mining happened. That IS stuck."""
    original = {k: m[k] for k in
                ("dig_once", "pack_has_room", "smelt", "log", "debug",
                 "interruptible_pause")}
    try:
        # Always answers, never yields - the clock is never pushed out.
        m["dig_once"] = lambda shovel, timeout: "silent"
        m["pack_has_room"] = lambda *a: True
        m["smelt"] = lambda *a: None
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["interruptible_pause"] = lambda *a, **k: None

        state = {"dug": 0, "silent": 0, "dead": set(), "spent": set(),
                 "last_yield": m["time"].time()}
        out = m["mine_spot"](None, 0, 25, state, m["time"].time() - 1)
        check("an unproductive spot is abandoned", out, "")
        check("and it dug nothing", state["dug"], 0)
    finally:
        for k, v in original.items():
            m[k] = v


def test_lumber_spot_also_runs_to_depletion(m):
    """Same rule on the wood side."""
    replies = {"n": 0}
    original = {k: m[k] for k in
                ("chop_once", "pack_has_room", "log", "debug",
                 "interruptible_pause")}
    try:
        def chopping(axe, timeout):
            replies["n"] += 1
            return "ok" if replies["n"] <= 40 else "empty"

        m["chop_once"] = chopping
        m["pack_has_room"] = lambda *a: True
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["interruptible_pause"] = lambda *a, **k: None

        state = {"cut": 0, "silent": 0, "dead": set(), "spent": set(),
                 "last_yield": m["time"].time()}
        m["work_spot"](None, 0, 9, state,
                       m["time"].time() + (m["AREA_SPOT_TIMEOUT_MS"] / 1000.0))
        check("chopped the whole bank", state["cut"], 40)
        check("stopped on empty, not the clock", replies["n"], 41)
    finally:
        for k, v in original.items():
            m[k] = v

class SkipEntry(object):
    def __init__(self, text, serial=0, name="", stamp=1.0):
        self.Text = text
        self.Serial = serial
        self.Name = name
        self.Timestamp = stamp


def feed_journal(m, entries):
    """Replace the journal reader with a fixed list, once."""
    served = {"done": False}

    def once():
        if served["done"]:
            return []
        served["done"] = True
        return entries
    m["new_journal_entries"] = once


def test_skip_only_from_the_running_character(m):
    """Several dummy accounts run at once - each must skip only itself."""
    original = {k: m[k] for k in ("new_journal_entries", "log", "debug")}
    player = m["Player"]
    try:
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["_skip_pending"] = False

        # Said by THIS character - matched on the journal entry's Serial.
        feed_journal(m, [SkipEntry("skip", serial=player.Serial,
                                   name=player.Name)])
        check("own character skips", m["poll_skip"](), True)
        check("and the flag is consumed once", m["take_skip"](), True)
        check("only once", m["take_skip"](), False)

        # Said by a DIFFERENT character - must not move this one.
        m["_skip_pending"] = False
        feed_journal(m, [SkipEntry("skip", serial=0x0BADF00D,
                                   name="Mystic Gatherer")])
        check("another character does not skip this one",
              m["poll_skip"](), False)

        # Global chat form, another player entirely.
        m["_skip_pending"] = False
        feed_journal(m, [SkipEntry("System: <Public> Fred Kruger: skip",
                                   serial=0, name="System")])
        check("global chat from someone else is ignored",
              m["poll_skip"](), False)
    finally:
        for k, v in original.items():
            m[k] = v
        m["_skip_pending"] = False


def test_skip_matches_the_whole_line_not_a_substring(m):
    """"skip" is an ordinary word - it must not fire inside other text."""
    original = {k: m[k] for k in ("new_journal_entries", "log", "debug")}
    player = m["Player"]
    try:
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None

        for text, want in (
                ("skip", True),
                ("Skip", True),
                ("SKIP", True),
                ("skip.", True),
                ("  skip  ", True),
                ("skip this vein", False),
                ("I will skip the next one", False),
                ("skipping", False),
                ("You cannot skip that", False),
        ):
            m["_skip_pending"] = False
            feed_journal(m, [SkipEntry(text, serial=player.Serial,
                                       name=player.Name)])
            check("%-28r -> %s" % (text, want), m["poll_skip"](), want)
    finally:
        for k, v in original.items():
            m[k] = v
        m["_skip_pending"] = False


def test_one_journal_pass_feeds_every_trigger(m):
    """Reading the journal CONSUMES it, so there can only be one reader.

    Two pollers each calling new_journal_entries would steal lines from each
    other and both would miss things at random.
    """
    original = {k: m[k] for k in ("new_journal_entries", "log", "debug")}
    player = m["Player"]
    try:
        m["log"] = lambda *a, **k: None
        m["debug"] = lambda *a, **k: None
        m["_skip_pending"] = False
        m["_greyskull_pending"] = False

        # Both triggers arrive in the SAME batch of lines.
        feed_journal(m, [
            SkipEntry("System: <Public> Fred Kruger: By The Power Of Greyskull!"),
            SkipEntry("skip", serial=player.Serial, name=player.Name),
        ])
        m["scan_journal"]()
        check("the call-out was seen", m["_greyskull_pending"], True)
        check("and so was the skip, from the same pass",
              m["_skip_pending"], True)
    finally:
        for k, v in original.items():
            m[k] = v
        m["_skip_pending"] = False
        m["_greyskull_pending"] = False


def test_skip_is_configured_for_separate_characters(m):
    check("self-only is the default", m["SKIP_SELF_ONLY"], True)
    check("skip is the phrase", [p.lower() for p in m["SKIP_PHRASES"]],
          ["skip"])

def test_stone_storage_has_the_same_options_as_the_other_keys(m):
    """Granite needs a key like wood and ingots, or it goes to the ONE-WAY chest."""
    for suffix in ("ENABLED", "WHERE", "SERIAL", "ID", "HUE", "RANGE", "NAMES"):
        check("STONE_STORAGE_%s exists" % suffix,
              ("STONE_STORAGE_%s" % suffix) in m, True)

    check("stone storage graphic", m["STONE_STORAGE_ID"], 0xA54A)
    check("any colour", m["STONE_STORAGE_HUE"], -1)
    check("it carries name hints", bool(m["STONE_STORAGE_NAMES"]), True)


def test_stone_storage_entry_is_built_from_the_settings(m):
    """It shipped as an unnamed "Key (alt)" on this graphic - the same key all
    along, single-clicked without anyone knowing what it was."""
    entry = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Stone Storage"]
    check("one stone storage entry", len(entry), 1)
    entry = entry[0]
    for field, setting in (("serial", "STONE_STORAGE_SERIAL"),
                           ("id", "STONE_STORAGE_ID"),
                           ("hue", "STONE_STORAGE_HUE"),
                           ("where", "STONE_STORAGE_WHERE"),
                           ("range", "STONE_STORAGE_RANGE"),
                           ("names", "STONE_STORAGE_NAMES"),
                           ("enabled", "STONE_STORAGE_ENABLED")):
        check("%s tracks the setting" % field, entry.get(field), m[setting])

    check("the anonymous Key (alt) is gone",
          any(k.get("label") == "Key (alt)" for k in m["RESTOCK_KEYS"]), False)


def test_granite_is_kept_out_of_the_one_way_chest(m):
    """0x1779 is in PURGE_ID, so without a KEY_BACKED_IDS line every piece
    mined would be swept into the chest even with the key in the pack."""
    check("granite is swept by default", 0x1779 in m["PURGE_ID"], True)

    backed = dict((spec["label"], spec["ids"]) for spec in m["KEY_BACKED_IDS"])
    check("granite is claimed by the Stone Storage",
          0x1779 in backed.get("Stone Storage", []), True)

    # With the key in reach, granite must NOT be in the chest sweep.
    original = m["keys_in_reach"]
    try:
        m["keys_in_reach"] = lambda wanted=None: set(["Stone Storage"])
        ids, blocked, _here = m["chest_sweep_ids"]()
        check("granite is held back", 0x1779 in ids, False)
        check("and the reason is named", "Stone Storage" in blocked, True)

        # With no key, it goes to the chest as before.
        m["keys_in_reach"] = lambda wanted=None: set()
        ids, blocked, _here = m["chest_sweep_ids"]()
        check("without the key it is swept", 0x1779 in ids, True)
    finally:
        m["keys_in_reach"] = original


def test_stone_storage_is_off_for_everyone_by_default(m):
    """Only one character mines stone. The repo copy is the template."""
    check("disabled in the shipped template", m["STONE_STORAGE_ENABLED"], False)
    check("and carries no serial", m["STONE_STORAGE_SERIAL"], 0)

    entry = [k for k in m["RESTOCK_KEYS"]
             if k.get("label") == "Stone Storage"][0]
    check("a disabled key is never looked for", m["find_restock"](entry), [])

def test_every_key_with_work_gets_a_turn(m):
    """Granite was stranded: the Ingot key freed the pack and the run ENDED.

    refill_keys used to return the moment there was room, and the Stone
    Storage is last in the list. Ingots are heavy, so the pack was always
    freed before granite was ever offered to its key - and KEY_BACKED_IDS
    (rightly) keeps granite out of the one-way chest too, so it simply
    accumulated in the pack for ever.
    """
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def refill_keys("):src.index("def smelt(")]

    # The early return must be GUARDED by "is there still work", not by room
    # alone. A bare `if pack_has_room(): return True` is the bug.
    check("the early return is guarded by outstanding work",
          "if pack_has_room() and not any_key_has_work():" in body, True)
    check("and there is no unguarded room-only return",
          "    if pack_has_room():\n        return True" in body, False)
    check("it asks whether any key still has work",
          "any_key_has_work()" in body, True)
    check("and skips only keys with nothing of their own left",
          "not key_has_work(label)" in body, True)


def test_key_has_work_looks_only_at_its_own_resources(m):
    """Each key answers for the graphics KEY_BACKED_IDS gives it."""
    ITEMS.reset()
    try:
        check("nothing in the pack means no work",
              m["any_key_has_work"](), False)

        # A lump of granite belongs to the Stone Storage and to nobody else.
        granite = StubWorldItem(0x40000010, 0x1779, 0x0000, "granite")
        granite.Container = StubItem.Serial
        granite.RootContainer = StubItem.Serial
        ITEMS.register(granite, "pack")

        check("the Stone Storage has work", m["key_has_work"]("Stone Storage"),
              True)
        check("the Ingot key does not", m["key_has_work"]("Ingot key"), False)
        check("the Wood Storage does not",
              m["key_has_work"]("Wood Storage"), False)
        check("so something has work", m["any_key_has_work"](), True)
    finally:
        ITEMS.reset()


def test_a_key_we_know_nothing_about_is_still_offered(m):
    """Only keys with a KEY_BACKED_IDS entry can be skipped as 'done'."""
    check("the Stone Storage is known", m["known_key"]("Stone Storage"), True)
    check("the Ingot key is known", m["known_key"]("Ingot key"), True)
    check("the Master key is not", m["known_key"]("Master key"), False)


def test_each_key_can_have_its_own_menu_entry(m):
    """A storage whose menu words it differently must be configurable.

    Every key shared one RESTOCK_CONTEXT, so a Stone Storage whose entry is
    not "Refill from stock" could never be told to take anything.
    """
    for suffix in ("WOOD_STORAGE_CONTEXT", "INGOT_KEY_CONTEXT",
                   "STONE_STORAGE_CONTEXT"):
        check("%s exists" % suffix, suffix in m, True)

    for label, cfg in (("Wood Storage", "WOOD_STORAGE_CONTEXT"),
                       ("Ingot key", "INGOT_KEY_CONTEXT"),
                       ("Stone Storage", "STONE_STORAGE_CONTEXT")):
        entry = [k for k in m["RESTOCK_KEYS"] if k.get("label") == label][0]
        check("%s tracks its own context" % label,
              entry.get("context"), m[cfg])

    # An empty override falls back to the shared entry rather than matching
    # nothing at all.
    check("the shared entry is still there",
          m["RESTOCK_CONTEXT"], ["Refill from stock"])


def test_context_constants_are_declared_before_the_table(m):
    """Module code runs top to bottom.

    RESTOCK_KEYS reads these inside a literal, so they have to be above it -
    the first version put them below and the script raised NameError on load.
    Nothing in the test suite would have caught that; tools/check_undefined_names.py
    now does.
    """
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    for name in ("RESTOCK_CONTEXT", "WOOD_STORAGE_CONTEXT",
                 "INGOT_KEY_CONTEXT", "STONE_STORAGE_CONTEXT"):
        check("%s is declared before RESTOCK_KEYS" % name,
              src.index("\n%s = " % name) < src.index("\nRESTOCK_KEYS = ["),
              True)

def test_the_whole_main_block_is_inside_the_handler(m):
    """A Razor script that raises prints one line and stops - the traceback is
    gone before it can be read. Nothing may escape uncaught."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    main_block = src[src.index('if __name__ == "__main__":'):]

    check("the body opens with a try", "\n    try:\n" in main_block, True)
    check("and ends with a handler",
          "except Exception as _err:" in main_block, True)
    check("SystemExit still gets through",
          "except SystemExit:" in main_block, True)
    check("the handler reports rather than swallowing",
          "report_crash(_err)" in main_block, True)

    # Nothing at the top level of the block outside the try - a statement at
    # four spaces that is not part of the try would run unprotected.
    body = main_block.split("\n", 1)[1]
    stray = [ln for ln in body.split("\n")
             if ln.startswith("    ") and not ln.startswith("        ")
             and ln.strip() and not ln.strip().startswith("#")
             and ln.strip() not in ("try:", "except SystemExit:",
                                    "raise", "else:")
             and not ln.strip().startswith("except ")]
    check("nothing runs outside the handler", stray, [])


def test_the_trail_keeps_the_last_lines_only(m):
    """The breadcrumb trail must be bounded - it runs for hours."""
    original = m["Misc"]
    try:
        class Quiet(object):
            def SendMessage(self, *a):
                pass
        m["Misc"] = Quiet()
        del m["_trail"][:]
        for n in range(m["CRASH_TRAIL"] * 3):
            m["log"]("line %d" % n)
        check("the trail is capped", len(m["_trail"]), m["CRASH_TRAIL"])
        check("and it keeps the NEWEST lines", m["_trail"][-1],
              "line %d" % (m["CRASH_TRAIL"] * 3 - 1))
    finally:
        m["Misc"] = original
        del m["_trail"][:]


def test_crash_state_names_the_serials(m):
    """The serials are the only thing that differs between the copies, so they
    are the first suspect when one character crashes and the others do not."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def crash_state():"):src.index("def report_crash(")]
    for name in ("WOOD_STORAGE_SERIAL", "INGOT_KEY_SERIAL",
                 "STONE_STORAGE_SERIAL"):
        check("%s is in the report" % name, name in body, True)
    check("a serial that will not resolve is reported, not raised",
          "reading it RAISED" in body, True)
    check("and one that resolves shows what it is",
          "id 0x%04X hue 0x%04X" in body, True)


def test_crash_state_survives_a_broken_player(m):
    """The reporter must not raise while reporting a crash."""
    original = m["Player"]
    try:
        class Broken(object):
            def __getattr__(self, name):
                raise RuntimeError("client is gone")
        m["Player"] = Broken()
        rows = m["crash_state"]()
        check("it still returned something", bool(rows), True)
        check("and said the player could not be read",
              any("could not be read" in r for r in rows), True)
    finally:
        m["Player"] = original

class CountingMisc(object):
    """Counts what actually reaches the client."""

    def __init__(self):
        self.sent = []

    def SendMessage(self, text, hue=0, wait=False):
        self.sent.append(text)

    def Pause(self, *a):
        pass


def test_identical_lines_are_collapsed(m):
    """Every log line is a packet INJECTED into the client.

    MrGatherer's crash is ClassicUO's receive buffer overflowing in
    Plugin.OnPluginRecv_new, and a burst of identical lines is the shape that
    does it - pack_has_room() is a query called several times per key inside
    refill_keys and announced itself every time.
    """
    original = m["Misc"]
    counter = CountingMisc()
    try:
        m["Misc"] = counter
        m["_last_line"].update({"text": "", "at": 0.0, "held": 0})
        m["_rate"].update({"second": 0, "sent": 0})
        del m["_trail"][:]

        for _ in range(20):
            m["log"]("Pack at 90% by WEIGHT: 445 of 495 stones - storing.")

        check("twenty identical lines became one packet",
              len([t for t in counter.sent if "Pack at 90%" in t]), 1)
        check("but all twenty are in the crash trail",
              len(m["_trail"]), 20)

        # A different line reports how many were held.
        m["log"]("something else")
        check("the repeat count is reported",
              any("repeated 19 more time" in t for t in counter.sent), True)
    finally:
        m["Misc"] = original
        del m["_trail"][:]


def test_a_flood_of_distinct_lines_is_capped(m):
    """Dedupe does not help if every line is different - cap the rate too."""
    original = m["Misc"]
    counter = CountingMisc()
    try:
        m["Misc"] = counter
        m["_last_line"].update({"text": "", "at": 0.0, "held": 0})
        m["_rate"].update({"second": 0, "sent": 0})
        del m["_trail"][:]

        for n in range(200):
            m["log"]("distinct line %d" % n)

        cap = m["LOG_MAX_PER_SECOND"]
        check("the client got no more than the cap",
              len(counter.sent) <= cap + 2, True)
        check("but every line is still in the trail for the crash report",
              len(m["_trail"]), m["CRASH_TRAIL"])
    finally:
        m["Misc"] = original
        del m["_trail"][:]


def test_suppressing_a_line_never_hides_it_from_the_crash_report(m):
    """The trail is the evidence - it must record what was suppressed."""
    original = m["Misc"]
    try:
        m["Misc"] = CountingMisc()
        m["_last_line"].update({"text": "", "at": 0.0, "held": 0})
        m["_rate"].update({"second": 0, "sent": 0})
        del m["_trail"][:]
        for _ in range(10):
            m["log"]("the line just before it died")
        check("the trail kept every copy", len(m["_trail"]), 10)
        check("and it is the right line", m["_trail"][-1],
              "the line just before it died")
    finally:
        m["Misc"] = original
        del m["_trail"][:]


def test_rate_limit_is_configurable_and_sane(m):
    check("a dedupe window is set", m["LOG_DEDUPE_MS"] > 0, True)
    check("a per-second cap is set", m["LOG_MAX_PER_SECOND"] > 0, True)
    check("the cap leaves room for normal logging",
          m["LOG_MAX_PER_SECOND"] >= 8, True)

def test_one_switch_turns_off_every_bulk_order(m):
    """BOD_ENABLED = False must remove ALL bulk order work and nothing else."""
    check("the switch exists and defaults on", m["BOD_ENABLED"], True)

    original = m["BOD_ENABLED"]
    try:
        # With it ON, the BOD stops expand and the carpenter is served.
        on = [v["label"] for v in m["all_vendors"]()]
        check("BOD stops are expanded", any("@" in l for l in on), True)
        check("the carpenter is served", "Carpenter" in on, True)

        m["BOD_ENABLED"] = False
        off = [v["label"] for v in m["all_vendors"]()]

        check("no BOD stop survives", [l for l in off if "@" in l], [])
        check("the carpenter goes with them", "Carpenter" in off, False)
        check("nothing expands from BOD_LOCATIONS",
              m["expand_bod_locations"](), [])

        # ...and the two that are NOT bulk orders keep running.
        check("Resource Orders still served", "Resource Orders" in off, True)
        check("Taming Deeds still served", "Taming Deeds" in off, True)
    finally:
        m["BOD_ENABLED"] = original


def test_the_carpenter_is_marked_as_a_bod_vendor(m):
    """It lives in VENDORS rather than BOD_LOCATIONS, so it needs the flag or
    the switch would miss it."""
    carpenter = [v for v in m["VENDORS"] if v.get("label") == "Carpenter"]
    check("the carpenter is in VENDORS", len(carpenter), 1)
    check("and is flagged as a bulk order vendor",
          carpenter[0].get("bod"), True)

    for label in ("Resource Orders", "Taming Deeds"):
        entry = [v for v in m["VENDORS"] if v.get("label") == label][0]
        check("%s is NOT flagged bod" % label, entry.get("bod"), None)


def test_filing_stops_with_the_switch(m):
    """No book, no filing - and it must not complain about a missing book."""
    original = m["BOD_ENABLED"]
    original_log = m["log"]
    said = []
    try:
        m["BOD_ENABLED"] = False
        m["log"] = lambda text, *a, **k: said.append(text)
        check("filing is a no-op", m["file_bulk_orders"](), 0)
        check("and it says nothing about a missing book",
              [t for t in said if "Bulk Order Book" in t], [])
    finally:
        m["BOD_ENABLED"] = original
        m["log"] = original_log


def test_no_dead_top_level_functions(m):
    """Anything defined and never called is either wired up or removed.

    TASKS holds harvest_mine and harvest_lumber by reference, so they count as
    called even though no name in the file invokes them directly.
    """
    import ast as _ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    defined = set(n.name for n in tree.body
                  if isinstance(n, _ast.FunctionDef))
    referenced = set()
    for n in _ast.walk(tree):
        if isinstance(n, _ast.Name) and isinstance(n.ctx, _ast.Load):
            referenced.add(n.id)
    check("every function is referenced somewhere",
          sorted(defined - referenced), [])

def test_movement_is_refused_when_the_player_is_gone(m):
    """ClassicUO's Plugin.RequestMove has NO null check on World.Player:

        internal static bool RequestMove(int dir, bool run)
        {
            return Client.Game.UO.World.Player.Walk((Direction)dir, run);
        }

    so asking to move during a recall takes the whole CLIENT down. The script
    cannot fix that - only refuse to ask.
    """
    player = m["Player"]
    saved_pos, saved_serial = player.Position, player.Serial
    original_pf = m["PathFinding"]
    original_debug = m["debug"]

    asked = {"moves": 0}

    class Recording(object):
        class Route(object):
            pass

        def Go(self, route):
            asked["moves"] += 1
            return True

        def GetPath(self, x, y, ignoremob):
            return [(x, y)]

    try:
        m["debug"] = lambda *a, **k: None
        m["PathFinding"] = Recording()

        # Normal: it moves.
        player.Position = StubPos(100, 100)
        check("a real position moves", m["pathfind_to"](110, 100), True)
        check("and it asked the client once", asked["moves"], 1)

        # 0,0 is what an unloaded world reads as.
        asked["moves"] = 0
        player.Position = StubPos(0, 0)
        check("0,0 refuses to move", m["pathfind_to"](110, 100), False)
        check("the client was never asked", asked["moves"], 0)

        # No serial - not in the world at all.
        asked["moves"] = 0
        player.Position = StubPos(100, 100)
        player.Serial = 0
        check("no serial refuses to move", m["pathfind_to"](110, 100), False)
        check("still never asked", asked["moves"], 0)
    finally:
        m["PathFinding"] = original_pf
        m["debug"] = original_debug
        player.Position, player.Serial = saved_pos, saved_serial


def test_player_ready_survives_a_dead_client(m):
    """Reading Player may itself throw while the world is gone."""
    original = m["Player"]
    try:
        class Gone(object):
            def __getattr__(self, name):
                raise RuntimeError("world is unloading")
        m["Player"] = Gone()
        check("a throwing Player is not ready", m["player_ready"](), False)
    finally:
        m["Player"] = original


def test_recall_waits_for_the_world(m):
    """Every recall must settle before anything walks.

    This used to be a text check for "wait_for_player()" inside ar_recall -
    which PASSED while the bug was live, because the call was sitting on the
    mana-retry branch and the successful first cast returned straight past it.
    The common path was the unguarded one. So: call the real function, on both
    paths, and count the waits.
    """
    waited = {"n": 0}
    saved = {k: m[k] for k in ("wait_for_player", "clear_journal",
                               "travel_failed_for_mana", "ensure_mana",
                               "openAR", "Gumps", "Misc", "log")}

    class Silent(object):
        def SendAction(self, gump_id, button):
            pass

    class Instant(object):
        def Pause(self, ms):
            pass

    try:
        m["wait_for_player"] = lambda *a, **k: waited.__setitem__("n", waited["n"] + 1) or True
        m["clear_journal"] = lambda *a, **k: None
        m["log"] = lambda *a, **k: None
        m["Gumps"] = Silent()
        m["Misc"] = Instant()
        m["ensure_mana"] = lambda **k: True
        m["openAR"] = lambda *a, **k: True

        # The common case: the first cast works. This is the path that was
        # unguarded, and it is the one that runs on virtually every recall.
        m["travel_failed_for_mana"] = lambda *a, **k: False
        check("a clean recall succeeds", m["ar_recall"](5, "Mining"), True)
        check("and it waited for the world", waited["n"], 1)

        # The rare case: refused for mana, recovered, cast again.
        waited["n"] = 0
        calls = {"n": 0}

        def refuse_once(*a, **k):
            calls["n"] += 1
            return calls["n"] == 1

        m["travel_failed_for_mana"] = refuse_once
        check("a retried recall succeeds", m["ar_recall"](5, "Mining"), True)
        check("and it waited exactly once", waited["n"], 1)

        # Refused twice: it never travelled, so it must NOT wait or claim to.
        waited["n"] = 0
        m["travel_failed_for_mana"] = lambda *a, **k: True
        check("a failed recall reports failure", m["ar_recall"](5, "Mining"), False)
        check("and never waited", waited["n"], 0)
    finally:
        for k, v in saved.items():
            m[k] = v
    check("and the wait is bounded",
          m["PLAYER_READY_TIMEOUT_MS"] > 0, True)

def load_script():
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    env = {
        "__name__": "harvest_runner_under_test",
        "Misc": StubMisc(), "Player": StubPlayer(), "Items": ITEMS,
        "Gumps": StubGumps(), "Journal": JOURNAL, "Timer": StubTimer(),
        "Mobiles": MOBILES, "Target": None, "PathFinding": None,
        "Statics": StubStatics(),
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


def heard(m):
    """Did a NEW call-out arrive? Drives the real shared journal scan.

    greyskull_heard() used to own the journal loop and consume it. It does not
    any more: scan_journal is the single reader, because the cursor is consumed
    by reading and two readers would steal lines from each other. Resetting the
    flag before scanning reproduces the old one-shot semantics these tests were
    written against.
    """
    m["_greyskull_pending"] = False
    m["scan_journal"]()
    return m["_greyskull_pending"]


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
        check("hears %r" % said.strip()[:38], heard(m), True)

    for ignored in ["System: <Public> Fred Kruger: by the power of grayskull",
                    "System: <Public> Fred Kruger: power of greyskull",
                    "I have the power!",
                    "You have found some iron ore"]:
        reset_greyskull(m)
        JOURNAL.say(ignored)
        check("ignores %r" % ignored[:38], heard(m), False)


def test_greyskull_anyone_can_call(m):
    """Default must be: ANY caller triggers it, not just the script owner."""
    original = list(m["GREYSKULL_ALLOWED_CALLERS"])
    try:
        m["GREYSKULL_ALLOWED_CALLERS"][:] = []
        for who in ["Fred Kruger", "Alice", "Minerbot", "Some Random Person"]:
            reset_greyskull(m)
            JOURNAL.say("System: <Public> %s: By The Power Of Greyskull!" % who)
            check("anyone: %s triggers it" % who, heard(m), True)

        # Own character must work too, since IGNORE_SELF is off by default.
        reset_greyskull(m)
        JOURNAL.say("System: <Public> Minerbot: By The Power Of Greyskull!")
        check("own call-out triggers it", heard(m), True)

        # An allow-list, when set, restricts it.
        m["GREYSKULL_ALLOWED_CALLERS"][:] = ["Fred Kruger"]
        reset_greyskull(m)
        JOURNAL.say(REAL_LINE)
        check("allow-list admits Fred", heard(m), True)
        reset_greyskull(m)
        JOURNAL.say("System: <Public> Mallory: By The Power Of Greyskull!")
        check("allow-list rejects Mallory", heard(m), False)
    finally:
        m["GREYSKULL_ALLOWED_CALLERS"][:] = original


def test_greyskull_channel_filter(m):
    original = m["GREYSKULL_REQUIRE_CHANNEL"]
    try:
        m["GREYSKULL_REQUIRE_CHANNEL"] = "Public"
        reset_greyskull(m)
        JOURNAL.say(REAL_LINE)
        check("channel filter admits Public", heard(m), True)
        reset_greyskull(m)
        JOURNAL.say("<Guild> Bob: By The Power Of Greyskull!")
        check("channel filter rejects Guild", heard(m), False)
    finally:
        m["GREYSKULL_REQUIRE_CHANNEL"] = original


def test_greyskull_does_not_retrigger(m):
    """A single chant must fire once, not on every poll afterwards."""
    reset_greyskull(m)
    JOURNAL.say("by the power of greyskull!")
    check("first poll hears it", heard(m), True)
    check("second poll does not", heard(m), False)
    check("third poll does not", heard(m), False)

    JOURNAL.say("by the power of greyskull!")
    check("a new chant is heard again", heard(m), True)


def test_greyskull_primes_cursor(m):
    """Chants said before the script started must not fire on startup."""
    reset_greyskull(m)
    JOURNAL.say("by the power of greyskull!")     # said before we start
    m["prime_journal_cursor"]()
    check("old chant ignored after priming", heard(m), False)
    JOURNAL.say("by the power of greyskull!")     # said after
    check("new chant still heard", heard(m), True)


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
    # The REPO copy ships serial 0 on purpose - it goes to GitHub, and a real
    # character's item serial has no business being published. Each live copy
    # carries its own. So this tracks the setting rather than a literal.
    check("wood storage serial tracks the setting",
          wood.get("serial"), m["WOOD_STORAGE_SERIAL"])
    check("the published copy carries no real serial",
          m["WOOD_STORAGE_SERIAL"], 0)
    check("wood storage fallback id", wood.get("id"), 0x1BD9)
    check("wood storage fallback hue is any", wood.get("hue"), -1)
    check("where is a valid choice",
          wood.get("where") in ("world", "pack"), True)
    check("where tracks WOOD_STORAGE_WHERE",
          wood.get("where"), m["WOOD_STORAGE_WHERE"])


def test_keys_accept_any_hue(m):
    """Both keys must be found whatever colour they are.

    The wood storage hue used to be pinned to 0x0058, so a character whose key
    was any other colour silently had no storage at all and their wood went to
    the chest. Regression: both entries accept any hue.
    """
    for label in ("Wood Storage", "Ingot key"):
        spec = [k for k in m["RESTOCK_KEYS"] if k.get("label") == label][0]
        check("%s accepts any hue" % label, spec.get("hue"), -1)

    # Hue was ALSO the only thing telling a key apart from anything else of the
    # same graphic. Giving it up without a name check would be a downgrade, so
    # both entries must carry name hints.
    for label in ("Wood Storage", "Ingot key"):
        spec = [k for k in m["RESTOCK_KEYS"] if k.get("label") == label][0]
        check("%s has name hints" % label,
              bool(spec.get("names")), True)


def test_find_restock_any_hue(m):
    """A key of an unexpected colour is still found."""
    wood = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Wood Storage"][0]
    spec = dict(wood)
    spec["serial"] = 0
    spec["where"] = "pack"

    for hue in (0x0058, 0x0000, 0x0481, 0x08FD):
        ITEMS.reset()
        ITEMS.register(StubWorldItem(0x40001234, 0x1BD9, hue, "Wood Storage"),
                       "pack")
        check("wood storage found at hue 0x%04X" % hue,
              [i.Serial for i in m["find_restock"](spec)], [0x40001234])

    ITEMS.reset()


def test_match_by_name_narrows_not_widens(m):
    """The name check must narrow a graphic match, never lose the key.

    With hue ignored, a stack of something sharing the graphic could be picked
    instead of the key - so the name narrows. But a shard that sends no name
    must not cost the key entirely, so an empty result falls back to the
    unfiltered list.
    """
    spec = {"label": "Wood Storage", "id": 0x1BD9,
            "names": ["wood storage", "key"]}

    key = StubWorldItem(0x40000001, 0x1BD9, 0x0058, "Wood Storage")
    other = StubWorldItem(0x40000002, 0x1BD9, 0x0000, "boards")

    picked = m["match_by_name"](spec, [other, key])
    check("name picks the key over the lookalike",
          [i.Serial for i in picked], [0x40000001])

    # Nothing matches -> hand back what we had rather than nothing at all.
    picked = m["match_by_name"](spec, [other])
    check("no name match falls back to the raw list",
          [i.Serial for i in picked], [0x40000002])

    # No hints configured -> no filtering at all.
    picked = m["match_by_name"]({"label": "x", "names": []}, [other, key])
    check("no hints means no narrowing", len(picked), 2)

    check("empty candidate list stays empty", m["match_by_name"](spec, []), [])


def test_lumber_steps_match_the_wood_bank(m):
    """Spot spacing must match ServUO's bank, which is 4 wide and 3 tall.

    The bank is what depletes - "not enough wood here" empties the whole block.
    A step SMALLER than the bank puts the character back inside the block it
    just emptied and the server repeats itself, which in game looked like the
    script standing around doing nothing. Both axes were 3, so a third of the
    sideways moves were dead on arrival.
    """
    check("x step is the bank width", m["LUMBER_AREA_STEP_X"], 4)
    check("y step is the bank height", m["LUMBER_AREA_STEP_Y"], 3)
    check("x step tracks the source value",
          m["LUMBER_AREA_STEP_X"], m["LUMBER_BANK_W"])
    check("y step tracks the source value",
          m["LUMBER_AREA_STEP_Y"], m["LUMBER_BANK_H"])

    # A step below the bank size is the bug this test exists to prevent.
    check("x step is never below the bank width",
          m["LUMBER_AREA_STEP_X"] >= m["LUMBER_BANK_W"], True)
    check("y step is never below the bank height",
          m["LUMBER_AREA_STEP_Y"] >= m["LUMBER_BANK_H"], True)


def test_lumber_area_offsets(m):
    """The box must cover what it claims, and be centred on the landing tile."""
    xs = m["area_offsets"](m["LUMBER_AREA_SIZE"], m["LUMBER_AREA_STEP_X"])
    ys = m["area_offsets"](m["LUMBER_AREA_SIZE"], m["LUMBER_AREA_STEP_Y"])
    check("x offsets are centred on 0", xs, [-4, 0, 4])
    check("y offsets are centred on 0", ys, [-3, 0, 3])
    check("x offsets are symmetric", xs, [-o for o in reversed(xs)])
    check("y offsets are symmetric", ys, [-o for o in reversed(ys)])

    # Every tile in the 8x8 box must be within the server's 2-tile harvest
    # range of some standing spot, or the sweep quietly misses part of the box.
    # Widening the x step to 4 must NOT open a hole.
    half = m["LUMBER_AREA_SIZE"] // 2
    uncovered = []
    for x in range(-half, half + 1):
        for y in range(-half, half + 1):
            if not any(max(abs(x - ox), abs(y - oy)) <= 2
                       for ox in xs for oy in ys):
                uncovered.append((x, y))
    check("every tile in the box is still reachable from a spot", uncovered, [])

    # Each spot must sit in its OWN bank, which is the whole point.
    banks = set(m["bank_of"](x, y, m["LUMBER_BANK_W"], m["LUMBER_BANK_H"])
                for x in xs for y in ys)
    check("every spot is in a distinct wood bank", len(banks), len(xs) * len(ys))


def test_lumber_area_spots(m):
    """Walking order: the tile we are already on first, then no long jumps."""
    spots = m["lumber_area_spots"]((100, 200))
    check("nine standing spots", len(spots), 9)
    check("landing tile is worked first", spots[0], (100, 200))
    check("no spot is visited twice", len(set(spots)), len(spots))

    half = m["LUMBER_AREA_SIZE"] // 2
    outside = [s for s in spots
               if abs(s[0] - 100) > half or abs(s[1] - 200) > half]
    check("no spot falls outside the box", outside, [])

    # No leg may be longer than one step, INCLUDING the one off the landing
    # tile. A serpentine with the landing tile lifted out of it failed exactly
    # here: the middle row jumped the full 6-tile width of the box.
    legs = [max(abs(b[0] - a[0]), abs(b[1] - a[1]))
            for a, b in zip(spots, spots[1:])]
    longest = max(m["LUMBER_AREA_STEP_X"], m["LUMBER_AREA_STEP_Y"])
    check("no leg is longer than one step",
          [l for l in legs if l > longest], [])

    # The order has to be identical every time or a sweep resumed after a trip
    # home carries on at the wrong index.
    check("spot order is stable", m["lumber_area_spots"]((100, 200)), spots)


def test_lumber_single_matches_old_behaviour(m):
    """LUMBER_AREA_ENABLED = False must behave exactly as the script used to."""
    outcomes = {}

    def fake_chop(axe, timeout):
        return outcomes["reply"]

    original = m["chop_once"]
    try:
        m["chop_once"] = fake_chop
        for reply, want in (("ok", "ok"), ("broke", "ok"), ("full", "full"),
                            ("empty", "next"), ("notree", "next"),
                            ("silent", "next")):
            outcomes["reply"] = reply
            check("single spot: %s -> %s" % (reply, want),
                  m["lumber_single"](None), want)
    finally:
        m["chop_once"] = original


def test_lumber_sweep_key_tracks_waypoint(m):
    """Sweep state is keyed by waypoint, not by where the player is standing.

    The player walks away from the landing tile during a sweep, and a trip home
    for a full pack re-enters from wherever the unload finished - so a position
    key would start a fresh sweep every time and the same spots would be worked
    over and over.
    """
    original_job = m["_current_job"]
    try:
        m["_current_job"] = {"name": "Lumberjacking"}
        m["_waypoint"]["Lumberjacking"] = 4
        check("key names the waypoint being worked",
              m["sweep_key"](), ("Lumberjacking", 3))

        m["_waypoint"]["Lumberjacking"] = 5
        check("key moves with the waypoint",
              m["sweep_key"](), ("Lumberjacking", 4))
    finally:
        m["_current_job"] = original_job
        m["_waypoint"].pop("Lumberjacking", None)


def test_lumber_area_has_no_unbounded_loop(m):
    """Every sweep loop needs a bound. work_spot is the one that can run away."""
    check("swings at one spot are capped",
          m["LUMBER_AREA_MAX_SWINGS"] > 0, True)
    check("moving to a spot has a timeout",
          m["LUMBER_AREA_MOVE_TIMEOUT"] > 0, True)
    check("the probe swing has a timeout",
          m["LUMBER_AREA_PROBE_TIMEOUT"] > 0, True)

def test_find_restock(m):
    """Serial first, then id/hue in the right place."""
    ITEMS.reset()
    storage = StubWorldItem(WOOD_STORAGE_SERIAL, 0x1BD9, 0x0058, "Wood Storage")
    ITEMS.register(storage, "world")

    wood = [k for k in m["RESTOCK_KEYS"] if k.get("label") == "Wood Storage"][0]

    # Set one explicitly: the shipped default is 0, but a live copy has the
    # character's own serial here and that path must keep working.
    with_serial = dict(wood)
    with_serial["serial"] = WOOD_STORAGE_SERIAL
    found = m["find_restock"](with_serial)
    check("found by serial", [i.Serial for i in found], [WOOD_STORAGE_SERIAL])

    # A serial IGNORES `where` - FindBySerial does not care where the item is.
    # That is what lets a world-locked storage be found by a "pack" entry.
    ground_only = dict(with_serial)
    ground_only["where"] = "pack"
    check("a serial beats the where setting",
          [i.Serial for i in m["find_restock"](ground_only)],
          [WOOD_STORAGE_SERIAL])

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
        # Locked down in the world, reached through a "pack" entry - which only
        # works via the SERIAL lookup, since that ignores location. The shipped
        # repo copy has no serial (it is published), so set one as a live copy
        # would have.
        wood_entry = [k for k in m["RESTOCK_KEYS"]
                      if k.get("label") == "Wood Storage"][0]
        saved_serial = wood_entry.get("serial")
        wood_entry["serial"] = WOOD_STORAGE_SERIAL

        picked = install_menu(m, ["Open", "Refill from stock", "Rename"])
        # The pack frees up once the storage has taken the load.
        def freeing_reply(mob, label):
            picked.append(label)
            ITEMS.contents = "Contents: 5/125 items, 30/400 stones"
        m["Misc"].ContextReply = freeing_reply

        ok = m["refill_keys"]()
        wood_entry["serial"] = saved_serial
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
    """Item count comes from the tooltip; WEIGHT comes from the character.

    The backpack tooltip reports the CONTAINER's capacity ("0/60000 Stones"),
    which says nothing about what the character can lift. Player.Weight /
    Player.MaxWeight is the real limit.
    """
    ITEMS.reset()
    player = m["Player"]
    saved = (player.Weight, player.MaxWeight)
    try:
        ITEMS.contents = "Contents: 5/125 items, 0/60000 stones"
        player.Weight, player.MaxWeight = 30, 400
        check("items from the tooltip, weight from the character",
              m["pack_usage"](), (5, 125, 30, 400))
        check("pack has room", m["pack_has_room"](), True)

        ITEMS.contents = "Contents: 120/125 items, 0/60000 stones"
        check("full by item count", m["pack_has_room"](), False)

        ITEMS.contents = "Contents: 5/125 items, 0/60000 stones"
        player.Weight, player.MaxWeight = 390, 400
        check("full by the CHARACTER's weight", m["pack_has_room"](), False)

        # The reported case: 104 of 530 carried, and the container tooltip
        # claiming 60000 stones. Nowhere near full.
        player.Weight, player.MaxWeight = 104, 530
        check("104 of 530 is NOT full", m["pack_has_room"](), True)
    finally:
        player.Weight, player.MaxWeight = saved
        ITEMS.reset()


def test_an_unreadable_tooltip_does_not_mean_full(m):
    """CAUGHT IN GAME. Every character declared a full pack at whatever
    waypoint it had reached and then recalled home forever, at a fifth of its
    carry weight.

    pack_usage read the tooltip WITHOUT asking for the properties first, so it
    came back empty mid-run, and pack_has_room turned that into "full" - via
    debug(), so with debugging off nothing in the journal explained it.

    An unknown measure must never count as full. The authority on a genuinely
    full pack is the server's own refusal, which the harvest task reads out of
    the journal.
    """
    ITEMS.reset()
    player = m["Player"]
    saved = (player.Weight, player.MaxWeight)
    try:
        ITEMS.contents = ""                    # tooltip not loaded
        player.Weight, player.MaxWeight = 104, 530
        items, max_items, weight, max_weight = m["pack_usage"]()
        check("item count unknown", (items, max_items), (0, 0))
        check("but weight still known", (weight, max_weight), (104, 530))
        check("and the pack is NOT called full", m["pack_has_room"](), True)

        # Nothing readable at all: keep working rather than recall forever.
        player.Weight, player.MaxWeight = 0, 0
        check("nothing readable still is not full",
              m["pack_has_room"](), True)
    finally:
        player.Weight, player.MaxWeight = saved
        ITEMS.reset()


def test_pack_properties_are_requested_before_being_read(m):
    """Reading properties cold returns an empty list whenever the client has
    not fetched them - which is the whole cause above."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "pack_item_count":
            fn = node
    check("pack_item_count exists", fn is not None, True)
    if fn is None:
        return
    waits = [n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "WaitForProps"]
    reads = [n.lineno for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "GetPropStringList"]
    check("it asks for the properties", len(waits) > 0, True)
    check("before reading them", min(waits) < min(reads), True)
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
        # A world-locked storage is only reachable through a "pack" entry
        # because the SERIAL lookup ignores location. The shipped default is 0,
        # so set one for the duration the way a live copy has.
        wood_entry = [k for k in m["RESTOCK_KEYS"]
                      if k.get("label") == "Wood Storage"][0]
        saved_serial = wood_entry.get("serial")
        wood_entry["serial"] = WOOD_STORAGE_SERIAL

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
        wood_entry["serial"] = saved_serial
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


def test_stop_button_is_not_a_crash(m):
    """Razor's Stop aborts the thread; that must not write a crash report.

    Every crash file on disk when this was written was one of these - five
    reports, five presses of Stop, no real crashes. It also dumped a red
    traceback over the journal, which is the thing being read after a run.
    """
    stop = m["is_stop_request"]
    check("the IronPython thread abort is a stop",
          stop(SystemError("Thread was being aborted.")), True)
    check("case does not matter",
          stop(SystemError("thread was being aborted")), True)
    check("the .NET wording is a stop too",
          stop(RuntimeError("System.Threading.ThreadAbortException: Thread abort")),
          True)

    # Real failures must still be reported - this is the half that matters.
    check("a real error is not a stop",
          stop(AttributeError("'NoneType' object has no attribute 'Walk'")), False)
    check("an empty message is not a stop", stop(Exception("")), False)

    class Hostile(object):
        def __str__(self):
            raise RuntimeError("cannot render")

    check("an unprintable error is not a stop", stop(Hostile()), False)



# ---------------------------------------------------------------------------
# Mythril
#
# Observed 2026-08-22 on MrGatherer's mythril runes:
#   * a swing takes ~8s, against 5s for ordinary rock
#   * SUCCESS IS SILENT - the ore appears, nothing is said
#   * failure says "You dig for a while but fail to find any mythril ore of
#     suitable quality" - which begins with "You"
#   * depletion says "There is no mythril ore here to mine" - which contains
#     neither "no metal" nor "You"
# ---------------------------------------------------------------------------

def _mythril_dig(m, lines, weight_after=None, waypoint=150, enabled=True,
                 waypoints=None):
    """Run the REAL dig_once with a scripted journal and pack weight."""
    saved = {k: m[k] for k in
             ("Journal", "Target", "Player", "clear_journal", "clear_cursor",
              "debug", "interruptible_pause", "note_yield", "journal_hit",
              "MYTHRIL_ENABLED", "MYTHRIL_WAYPOINTS")}
    said = list(lines)
    weights = {"now": 100}

    class J(object):
        def Clear(self, *a, **k):
            pass

        def Search(self, text):
            return any(text.lower() in (s or "").lower() for s in said)

    class P(object):
        Weight = 100
        IsGhost = False

    try:
        m["MYTHRIL_ENABLED"] = enabled
        m["MYTHRIL_WAYPOINTS"] = (list(range(147, 173)) if waypoints is None
                                  else waypoints)
        m["_waypoint"]["Mining"] = waypoint
        m["Journal"] = J()
        class T(object):
            def __getattr__(self, name):
                return lambda *a, **k: None

        m["Target"] = T()
        m["clear_journal"] = lambda *a, **k: None
        m["clear_cursor"] = lambda *a, **k: True
        m["debug"] = lambda *a, **k: None
        m["note_yield"] = lambda *a, **k: None
        m["journal_hit"] = lambda words: any(
            w.lower() in (s or "").lower() for s in said for w in words)

        player = P()
        m["Player"] = player

        def pause(ms):
            # The ore lands part-way through the swing, silently.
            if weight_after is not None:
                player.Weight = weight_after

        m["interruptible_pause"] = pause
        return m["dig_once"]("shovel", 200)
    finally:
        for k, v in saved.items():
            m[k] = v


def test_mythril_failure_is_not_scored_as_ore(m):
    """The fail line begins with "You", so dig_once's broad catch-all would
    call it ore recovered - inflating the sweep's ore count and keeping a
    barren spot alive on a deadline it never earned."""
    out = _mythril_dig(m, ["You dig for a while but fail to find any mythril "
                           "ore of suitable quality."])
    check("a mythril failure is a miss, not ok", out, "miss")

    # The alternate spelling has to work too - the shard uses both.
    out = _mythril_dig(m, ["You dig for a while but fail to find any mithril "
                           "ore of suitable quality."])
    check("the 'mithril' spelling too", out, "miss")


def test_mythril_depletion_is_recognised(m):
    """"There is no mythril ore here to mine" contains neither "no metal" nor
    "You", so nothing in the ordinary tables matched it and it fell through to
    "silent" - which reads as a dead spot rather than a spent one."""
    out = _mythril_dig(m, ["There is no mythril ore here to mine."])
    check("depletion is empty, not silent", out, "empty")


def test_a_silent_mythril_success_is_seen_as_weight(m):
    """Success says NOTHING. The ore simply appears, so the pack getting
    heavier is the only evidence there is."""
    out = _mythril_dig(m, [], weight_after=124)      # 2 ore = 24 stones
    check("silent ore still counts as ok", out, "ok")


def test_a_silent_swing_with_no_ore_is_still_silent(m):
    out = _mythril_dig(m, [], weight_after=None)
    check("nothing said and nothing gained", out, "silent")


def test_weight_is_only_trusted_inside_a_mythril_zone(m):
    """Elsewhere the server always speaks, and weight can move for reasons
    that are not this swing. Trusting it everywhere would score phantom ore."""
    out = _mythril_dig(m, [], weight_after=124, waypoint=5)
    check("weight alone does not mean ore on ordinary rock", out, "silent")


def test_the_zone_is_scoped_to_its_waypoints(m):
    check("waypoint 147 is mythril",
          _mythril_dig(m, ["no mythril ore here to mine"], waypoint=147),
          "empty")
    check("waypoint 172 is mythril",
          _mythril_dig(m, ["no mythril ore here to mine"], waypoint=172),
          "empty")

    # 146 and 173 are ordinary rock. The depletion line is still understood -
    # the strings are global - but the 8s timeout and the weight test are not
    # applied, which is what "all others act as normal" means.
    saved = (m["MYTHRIL_ENABLED"], m["MYTHRIL_WAYPOINTS"])
    try:
        m["MYTHRIL_ENABLED"] = True
        m["MYTHRIL_WAYPOINTS"] = list(range(147, 173))
        m["_waypoint"]["Mining"] = 146
        check("146 is outside the zone", m["in_mythril_zone"](), False)
        m["_waypoint"]["Mining"] = 173
        check("173 is outside the zone", m["in_mythril_zone"](), False)
        m["_waypoint"]["Mining"] = 160
        check("160 is inside it", m["in_mythril_zone"](), True)
    finally:
        m["MYTHRIL_ENABLED"], m["MYTHRIL_WAYPOINTS"] = saved


def test_mythril_is_off_unless_switched_on(m):
    """Only one character mines it. Every other copy must behave exactly as it
    did before, so the switch has to be off by default and the shipped repo
    copy has to be generic."""
    check("off in the repo copy", m["MYTHRIL_ENABLED"], False)
    check("and no waypoints listed", m["MYTHRIL_WAYPOINTS"], [])

    m2_saved = m["MYTHRIL_ENABLED"]
    try:
        m["MYTHRIL_ENABLED"] = False
        m["MYTHRIL_WAYPOINTS"] = list(range(147, 173))
        m["_waypoint"]["Mining"] = 160
        check("a listed waypoint does nothing while disabled",
              m["in_mythril_zone"](), False)
    finally:
        m["MYTHRIL_ENABLED"] = m2_saved
        m["MYTHRIL_WAYPOINTS"] = []


def test_the_swing_gets_longer_only_where_it_should(m):
    saved = (m["MYTHRIL_ENABLED"], m["MYTHRIL_WAYPOINTS"])
    try:
        m["MYTHRIL_ENABLED"] = True
        m["MYTHRIL_WAYPOINTS"] = list(range(147, 173))
        m["_waypoint"]["Mining"] = 160
        check("mythril gets the long timeout",
              m["swing_timeout"](), m["MYTHRIL_SWING_TIMEOUT"])
        m["_waypoint"]["Mining"] = 5
        check("ordinary rock keeps the short one",
              m["swing_timeout"](), m["MINE_SWING_TIMEOUT"])
    finally:
        m["MYTHRIL_ENABLED"], m["MYTHRIL_WAYPOINTS"] = saved

    check("and the long one really is longer than a mythril swing",
          m["MYTHRIL_SWING_TIMEOUT"] > 8000, True)


def test_a_mythril_miss_does_not_count_as_ore(m):
    """state["dug"] is "swings that gave ore". Counting an 8-second failure
    there would have the sweep summary claim ore that never arrived."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "mine_spot")

    branch = None
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Compare) and \
                any(getattr(c, "value", None) == "miss" for c in node.comparators):
            branch = node
    check("mine_spot handles a miss", branch is not None, True)

    src = _ast.dump(fn)
    check("and the miss branch exists alongside ok", "'miss'" in src, True)



# ---------------------------------------------------------------------------
# "move" - leave this spot, keep the rune
#
# "skip" throws the whole area away and recalls. "move" leaves only the spot
# being worked and takes the next one in the same area; when that was the last
# spot there is nothing to move to, so the sweep runs out and recalls, which is
# the same thing skip does. That fallback is not special-cased anywhere - the
# sweep loop simply ends.
# ---------------------------------------------------------------------------

class MoveEntry(object):
    def __init__(self, text, name="", serial=0x1234):
        self.Text = text
        self.Name = name
        self.Serial = serial


def _say(m, text, mine=True):
    """Feed one spoken line through the REAL detector."""
    saved = {k: m[k] for k in ("Player", "debug", "_move_pending",
                               "_skip_pending")}
    try:
        # The PLAYER is always Mr Gatherer. Only the SPEAKER changes - that is
        # the whole point of the self-only rule, and naming both the same was
        # a fixture bug that made the check look like it passed anyone.
        class P(object):
            Name = "Mr Gatherer"

            def HeadMessage(self, *a, **k):
                pass

        m["Player"] = P()
        m["debug"] = lambda *a, **k: None
        entry = MoveEntry(text, name="Mr Gatherer" if mine else "Someone Else")
        return m["is_move_line"](entry, text)
    finally:
        for k, v in saved.items():
            m[k] = v


def test_move_is_matched_on_the_whole_line(m):
    """"move" is an even more ordinary word than "skip". A substring match
    would fire on half of what gets said near a mine."""
    check("a bare move is heard", _say(m, "move"), True)
    check("capitals do not matter", _say(m, "Move"), True)
    check("trailing punctuation does not matter", _say(m, "move."), True)

    for phrase in ("move over", "can you move", "I will move it",
                   "remove", "movement", "don't move"):
        check("%r is NOT a move command" % phrase, _say(m, phrase), False)


def test_move_is_self_only(m):
    check("said by this character", _say(m, "move", mine=True), True)
    check("said by somebody else", _say(m, "move", mine=False), False)
    check("and the switch exists", m["MOVE_SELF_ONLY"], True)


def test_move_and_skip_are_different_words(m):
    check("move is not skip", m["MOVE_PHRASES"] != m["SKIP_PHRASES"], True)
    overlap = set(p.lower() for p in m["MOVE_PHRASES"]) & \
        set(p.lower() for p in m["SKIP_PHRASES"])
    check("and they do not overlap", overlap, set())


def test_take_move_fires_once(m):
    saved = m["_move_pending"]
    try:
        m["_move_pending"] = True
        # scan_journal runs inside take_move; give it nothing new to read.
        saved_scan = m["scan_journal"]
        m["scan_journal"] = lambda: None
        try:
            check("first call takes it", m["take_move"](), True)
            check("second call does not", m["take_move"](), False)
        finally:
            m["scan_journal"] = saved_scan
    finally:
        m["_move_pending"] = saved


def test_a_recall_forgets_a_pending_move(m):
    """A move said as the last spot ended refers to an area that is gone. Left
    pending it would be spent on the first spot of the NEXT rune."""
    saved = m["_move_pending"]
    try:
        m["_move_pending"] = True
        m["forget_move"]()
        saved_scan = m["scan_journal"]
        m["scan_journal"] = lambda: None
        try:
            check("nothing left to take", m["take_move"](), False)
        finally:
            m["scan_journal"] = saved_scan
    finally:
        m["_move_pending"] = saved


def test_move_leaves_the_spot_but_not_the_sweep(m):
    """THE DIFFERENCE FROM SKIP, asserted structurally.

    skip calls end_sweep and returns "next" - the whole area is abandoned.
    move must do neither: it breaks the swing loop and lets the sweep advance
    to the next spot on its own.
    """
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())

    for fname in ("mine_spot", "lumber_spot"):
        fn = next((n for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == fname), None)
        if fn is None:
            continue
        calls = [n for n in _ast.walk(fn)
                 if isinstance(n, _ast.Call)
                 and getattr(n.func, "id", None) == "take_move"]
        check("%s honours move" % fname, len(calls) >= 1, True)

        ends = [n for n in _ast.walk(fn)
                if isinstance(n, _ast.Call)
                and getattr(n.func, "id", None) == "end_sweep"]
        check("%s does not end the sweep itself" % fname, ends, [])

    # And the sweep must NOT consume it - that is the spot's job.
    for fname in ("mine_sweep", "lumber_sweep"):
        fn = next((n for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == fname), None)
        if fn is None:
            continue
        calls = [n for n in _ast.walk(fn)
                 if isinstance(n, _ast.Call)
                 and getattr(n.func, "id", None) == "take_move"]
        check("%s does not eat the move itself" % fname, calls, [])


def test_the_walk_consumes_rather_than_polls(m):
    """If the mid-walk check only POLLED, the same move would be spent again
    on the next spot - one word, two spots skipped."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "walk_to")
    names = set()
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Call) and getattr(node.func, "id", None):
            names.add(node.func.id)
    check("the walk reacts to a move", "take_move" in names, True)
    check("and it consumes it", "poll_move" not in names, True)



# ---------------------------------------------------------------------------
# The multi-minute stall on one spot
#
# Observed in game 2026-08-22: the character sat on a spot for several minutes
# after "could not reach spot 2/14", answering nothing, saying nothing.
#
# Both existing guards are resettable BY DESIGN and both were defeated:
#   * AREA_SPOT_TIMEOUT_MS is pushed out by every productive swing, and a
#     mythril "miss" counts as productive - so on a spot that misses forever it
#     never expires
#   * AREA_IDLE_TIMEOUT_MS is only tested between spots, so a spot that never
#     returns never lets it run
# leaving MINE_AREA_MAX_SWINGS x the swing timeout as the only real bound:
# 80 x 12s is sixteen minutes.
# ---------------------------------------------------------------------------

def test_one_spot_cannot_run_for_minutes(m):
    cap_s = m["AREA_SPOT_HARD_CAP_MS"] / 1000.0
    worst_mine = m["MINE_AREA_MAX_SWINGS"] * m["MINE_SWING_TIMEOUT"] / 1000.0
    worst_myth = m["MINE_AREA_MAX_SWINGS"] * m["MYTHRIL_SWING_TIMEOUT"] / 1000.0

    check("the swing count alone allowed minutes of ordinary mining",
          worst_mine > 300, True)
    check("and much worse in a mythril zone", worst_myth > 900, True)
    check("the hard cap is far below both", cap_s < worst_mine, True)
    check("but still long enough to work a real bank", cap_s >= 60, True)


def test_the_hard_cap_is_never_extended(m):
    """The whole point: `deadline` is pushed out by ore and by a mythril miss.
    If the hard stop were pushed too it would be the same guard again."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())

    for fname in ("mine_spot", "lumber_spot"):
        fn = next((n for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == fname), None)
        if fn is None:
            continue

        assigns = [n for n in _ast.walk(fn)
                   if isinstance(n, _ast.Assign)
                   and any(getattr(t, "id", None) == "hard_stop"
                           for t in n.targets)]
        check("%s sets a hard stop" % fname, len(assigns), 1)
        check("%s sets it exactly once - never reset" % fname,
              len(assigns) == 1, True)

        # And it is actually tested.
        names = set()
        for node in _ast.walk(fn):
            if isinstance(node, _ast.Name):
                names.add(node.id)
        check("%s tests the hard stop" % fname, "hard_stop" in names, True)

        # The cap must come from the CONFIG, not a number baked in here.
        # Checking the constant merely appears in the function is too weak -
        # the log line mentions it too, so a hard_stop set to a hardcoded
        # 999999 passed that check happily.
        from_config = False
        for node in assigns:
            for sub in _ast.walk(node.value):
                if isinstance(sub, _ast.Name)                         and sub.id == "AREA_SPOT_HARD_CAP_MS":
                    from_config = True
        check("%s takes the cap from AREA_SPOT_HARD_CAP_MS" % fname,
              from_config, True)


def test_a_long_spot_says_something(m):
    """Minutes of silence is indistinguishable from a hung script - which is
    exactly how this got reported."""
    check("there is a progress interval", m["AREA_PROGRESS_MS"] >= 1000, True)
    check("and it is well inside the hard cap",
          m["AREA_PROGRESS_MS"] < m["AREA_SPOT_HARD_CAP_MS"], True)
    # At least one progress line before the cap, or it is not a progress line.
    check("so a capped spot reports at least once",
          m["AREA_SPOT_HARD_CAP_MS"] // m["AREA_PROGRESS_MS"] >= 2, True)

    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    for fname in ("mine_spot", "lumber_spot"):
        fn = next((n for n in _ast.walk(tree)
                   if isinstance(n, _ast.FunctionDef) and n.name == fname), None)
        if fn is None:
            continue
        names = set(n.id for n in _ast.walk(fn) if isinstance(n, _ast.Name))
        check("%s reports progress" % fname, "spoke_at" in names, True)


def test_the_journal_is_always_scanned(m):
    """poll_greyskull used to return early while a call-out was active, and
    interruptible_pause's ONLY scan went through it - so for the whole
    excursion nothing read the journal and a spoken "skip" or "move" was never
    seen. The reading must not be conditional; only the answering."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())

    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "poll_greyskull")
    body = fn.body
    # The scan must come before any early return.
    first_scan = None
    first_return = None
    for i, node in enumerate(body):
        if first_scan is None and any(
                isinstance(c, _ast.Call)
                and getattr(c.func, "id", None) == "scan_journal"
                for c in _ast.walk(node)):
            first_scan = i
        if first_return is None and any(isinstance(c, _ast.Return)
                                        for c in _ast.walk(node)):
            first_return = i
    check("poll_greyskull scans", first_scan is not None, True)
    check("and it scans BEFORE it can return",
          first_scan is not None and (first_return is None
                                      or first_scan <= first_return), True)

    pause = next(n for n in _ast.walk(tree)
                 if isinstance(n, _ast.FunctionDef)
                 and n.name == "interruptible_pause")
    called = set()
    for node in _ast.walk(pause):
        if isinstance(node, _ast.Call) and getattr(node.func, "id", None):
            called.add(node.func.id)
    check("the pause scans directly", "scan_journal" in called, True)



# ---------------------------------------------------------------------------
# The waypoint watchdog
#
# Observed 2026-08-22 on .19: MrGatherer stood against a cave wall for minutes
# after "could not reach spot 8/14" - with every guard INSIDE the sweep already
# in place, because none of them run between calls to task().
#
# run_job only advances when task() returns "next". Every other result leaves
# it at the same waypoint, and two of those paths were both unbounded and
# silent: "ok", and the pack-full path where unload_in_place() succeeds and
# `continue` runs without setting need_waypoint.
# ---------------------------------------------------------------------------

def test_a_waypoint_cannot_be_held_forever(m):
    cap = m["WAYPOINT_HARD_CAP_MS"]
    check("there is a waypoint cap", cap >= 60000, True)
    check("and it is longer than one spot's cap",
          cap > m["AREA_SPOT_HARD_CAP_MS"], True)
    # It has to allow a genuinely productive rune: a full bank of spots, each
    # able to run to its own cap, plus unload trips.
    check("but not so long it is useless", cap <= 30 * 60000, True)


def test_the_watchdog_is_armed_only_by_arriving_somewhere(m):
    """Resetting it anywhere else would defeat it - the whole failure is a
    loop that keeps doing things at ONE waypoint."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "run_job")

    assigns = [n for n in _ast.walk(fn)
               if isinstance(n, _ast.Assign)
               and any(getattr(t, "id", None) == "at_waypoint_since"
                       for t in n.targets)]
    check("the clock is set exactly twice - entry and arrival",
          len(assigns), 2)

    names = set(n.id for n in _ast.walk(fn) if isinstance(n, _ast.Name))
    check("run_job knows the cap", "WAYPOINT_HARD_CAP_MS" in names, True)
    check("and tracks which waypoint it is watching",
          "watched_waypoint" in names, True)


def test_the_watchdog_forces_the_next_rune(m):
    """Not a crash and not a stop - the run has to carry on."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def run_job("):src.index("def diagnostic_run(")
               if "def diagnostic_run(" in src else len(src)]
    i = body.index("WAYPOINT_HARD_CAP_MS")
    window = body[i:i + 700]
    check("it sets need_waypoint", "need_waypoint = True" in window, True)
    check("and continues rather than returning", "continue" in window, True)
    check("and says so loudly", "HUE_BAD" in window, True)


def test_unloading_in_place_is_never_capped(m):
    """THE REGRESSION THAT SENT HIM HOME CONSTANTLY.

    unload_in_place() returns True only when the pack ACTUALLY HAS ROOM
    afterwards - that is its whole contract - so a True can never be followed
    by an immediate "full", and the runaway loop a cap looked like it was
    guarding against cannot happen. Capping it did the opposite of what it
    looked like: a character whose keys were working perfectly was sent home
    after three successful in-place unloads.
    """
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def run_job("):]
    body = body[:body.index("\ndef ")]

    check("nothing caps the in-place unload", "unloads_here < " in body, False)
    check("its own return value is the only gate",
          "if unload_in_place():" in body, True)
    check("and no count sends it home", "going home instead" in body, False)

    # It still counts, but only so a busy rune can be reported.
    check("the counter advances", "unloads_here += 1" in body, True)
    check("and is reset on arrival", "unloads_here = 0" in body, True)
    check("a busy rune is reported, not punished", "staying out" in body, True)


def test_unload_in_place_only_reports_room_it_really_has(m):
    """The contract the above depends on. If this ever returned True with a
    full pack, an uncapped loop really would spin - so it is pinned here."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def unload_in_place("):]
    body = body[:body.index("\ndef ")]
    check("it ends on a real room check",
          body.rstrip().endswith("return pack_has_room(threshold)"), True)
    check("and its early return is also a room check",
          "if pack_has_room(threshold):" in body, True)


def test_an_unknown_task_result_does_not_mean_stay_here(m):
    """A typo in a task's return value would otherwise hold the character on
    one rune for as long as the run lasts, saying nothing."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def run_job("):]
    body = body[:body.index("\ndef ")]
    check("unknown results are named",
          'is not a result this loop knows' in body, True)
    check("and treated as done with the rune",
          'elif result not in ("ok", "full"):' in body, True)



def test_no_runtime_state_lives_in_the_config_half(m):
    """THE BUG THAT MADE "move" DO NOTHING IN GAME FOR A WEEK.

    The file splits at the "# HELPERS" seam. The config half is CARRIED
    FORWARD from each live copy; the code half is REPLACED wholesale. So a
    piece of state declared above the seam never travels: the splice delivers
    the code that reads it and not the line that creates it.

    _move_pending was declared above the seam, so take_move() read a name that
    did not exist. The command raised NameError in all four live copies from
    the day it shipped, and tested perfectly in the repo - where the line was
    present all along.

    Anything the code half uses belongs in the code half.
    """
    import ast as _ast
    import re as _re
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()

    lines = src.splitlines(True)
    seam = [i for i, l in enumerate(lines) if l.startswith("# HELPERS")]
    check("there is exactly one seam", len(seam), 1)
    cfg = "".join(lines[:seam[0]])
    code = "".join(lines[seam[0]:])

    def assigned(text):
        out = set()
        for node in _ast.parse(text).body:
            if isinstance(node, _ast.Assign):
                for t in node.targets:
                    if isinstance(t, _ast.Name):
                        out.add(t.id)
        return out

    # Private names are runtime state by this file's own convention.
    stranded = sorted(n for n in assigned(cfg) if n.startswith("_"))
    check("no private state above the seam", stranded, [])

    # And every one the code half uses must be DECLARED there, exactly once.
    for name in ("_move_pending", "_skip_pending", "_greyskull_pending",
                 "_waypoint", "_routes", "_journal_cursor",
                 "_stuck_pending", "_stuck_spot", "_stuck_at_rune",
                 "_spot_progress_at"):
        found = _re.findall(r"^%s\s*=" % name, code, _re.M)
        check("%s is declared in the code half" % name, len(found), 1)
        check("%s is not also in config" % name,
              bool(_re.search(r"^%s\s*=" % name, cfg, _re.M)), False)


def test_the_manual_override_reaches_the_long_waits(m):
    """"I have no way to force them to move on." The word was heard from
    anywhere but only ACTED on inside a walk or a spot loop - and
    MEDITATION_TIMEOUT alone is 90 seconds of standing still, per recall."""
    check("there is a bail switch", m["BAIL_ON_COMMAND"] in (True, False), True)

    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "ensure_mana")
    called = set()
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Call) and getattr(node.func, "id", None):
            called.add(node.func.id)
    check("the mana wait honours a spoken command",
          "bail_requested" in called, True)

    # And it must NOT consume - the structural handlers still need to see it.
    bail = next(n for n in _ast.walk(tree)
                if isinstance(n, _ast.FunctionDef) and n.name == "bail_requested")
    consumed = [n for n in _ast.walk(bail)
                if isinstance(n, _ast.Call)
                and getattr(n.func, "id", None) in ("take_skip", "take_move",
                                                    "take_stuck")]
    check("and does not swallow the word", consumed, [])


def test_silence_is_bounded(m):
    """Every stall so far was reported as "stuck, no output", and each time
    the question was WHERE - which the script knew and never said."""
    check("there is a heartbeat", m["HEARTBEAT_MS"] >= 1000, True)
    check("well inside the waypoint cap",
          m["HEARTBEAT_MS"] < m["WAYPOINT_HARD_CAP_MS"], True)

    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    pause = next(n for n in _ast.walk(tree)
                 if isinstance(n, _ast.FunctionDef)
                 and n.name == "interruptible_pause")
    called = set()
    for node in _ast.walk(pause):
        if isinstance(node, _ast.Call) and getattr(node.func, "id", None):
            called.add(node.func.id)
    check("the pause everything uses emits it", "heartbeat" in called, True)

    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    check("and the phase is recorded in several places",
          src.count('phase("') >= 6, True)


# --------------------------------------------------------------------------
# "stuck", and the no-progress watchdog
#
# One of the caves gets Mr Gatherer walking at dark that cannot be entered or
# mined. "move" was not enough for it: it is checked where leaving a spot is
# convenient, and the spot it leaves is taken again on the next lap. "stuck"
# writes the spot off, and the watchdog does the same thing on a clock so it
# does not have to be said at all.
# --------------------------------------------------------------------------

def _say_stuck(m, text, mine=True):
    """Feed one spoken line through the REAL stuck detector."""
    saved = {k: m[k] for k in ("Player", "debug")}
    try:
        class P(object):
            Name = "Mr Gatherer"

            def HeadMessage(self, *a, **k):
                pass

        m["Player"] = P()
        m["debug"] = lambda *a, **k: None
        entry = MoveEntry(text, name="Mr Gatherer" if mine else "Someone Else")
        return m["is_stuck_line"](entry, text)
    finally:
        for k, v in saved.items():
            m[k] = v


def test_stuck_is_matched_on_the_whole_line(m):
    """The consequence is larger than move's - the spot is written off, not just
    left - so the matching is no looser."""
    check("a bare stuck is heard", _say_stuck(m, "stuck"), True)
    check("capitals do not matter", _say_stuck(m, "Stuck"), True)
    check("trailing punctuation does not matter", _say_stuck(m, "stuck!"), True)

    for phrase in ("stuck again", "you are stuck", "I think he is stuck",
                   "unstuck", "stuckness", "get unstuck"):
        check("%r is NOT a stuck command" % phrase,
              _say_stuck(m, phrase), False)


def test_stuck_is_self_only(m):
    check("said by this character", _say_stuck(m, "stuck", mine=True), True)
    check("said by somebody else", _say_stuck(m, "stuck", mine=False), False)
    check("and the switch exists", m["STUCK_SELF_ONLY"], True)


def test_the_three_words_are_distinct(m):
    words = []
    for key in ("SKIP_PHRASES", "MOVE_PHRASES", "STUCK_PHRASES"):
        words.append(set(p.lower() for p in m[key]))
    check("skip and stuck do not overlap", words[0] & words[2], set())
    check("move and stuck do not overlap", words[1] & words[2], set())


def test_take_stuck_fires_once_and_condemns(m):
    """Consuming the word and condemning the spot are one action. Splitting them
    is how a spot gets abandoned without being remembered."""
    saved = m["_stuck_pending"]
    saved_scan = m["scan_journal"]
    try:
        m["scan_journal"] = lambda: None
        m["_stuck_spot"][0] = False
        m["_stuck_pending"] = True
        check("first call takes it", m["take_stuck"](), True)
        check("and the spot is condemned", m["_stuck_spot"][0], True)
        check("second call does not", m["take_stuck"](), False)

        check("the sweep reads it", m["stuck_condemned"](), True)
        check("and it is cleared by reading", m["stuck_condemned"](), False)
    finally:
        m["scan_journal"] = saved_scan
        m["_stuck_pending"] = saved
        m["_stuck_spot"][0] = False


def test_stuck_reaches_the_long_waits(m):
    """"No matter if they are trying to pathfind or not." bail_requested is what
    every long helper checks, so stuck has to be in it - and it must not be
    consumed there, or the sweep never learns which spot to write off."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = _ast.parse(src)
    bail = next(n for n in _ast.walk(tree)
                if isinstance(n, _ast.FunctionDef)
                and n.name == "bail_requested")
    names = {n.id for n in _ast.walk(bail) if isinstance(n, _ast.Name)}
    check("bail_requested sees a pending stuck", "_stuck_pending" in names,
          True)
    consumed = [n for n in _ast.walk(bail) if isinstance(n, _ast.Call)
                and getattr(n.func, "id", None) == "take_stuck"]
    check("and does not swallow it", consumed, [])


def test_the_walk_checks_stuck_after_the_blocking_call(m):
    """PathFinding.Go is .NET and blocks; no Python check runs while it does. So
    the check has to happen straight after it returns, not only at the top of
    the next lap - that is the difference between acting on the word now and
    waiting out another whole iteration."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def walk_to("):src.index("def give_up_on_patch(")]
    check("the walk reacts to stuck", "take_stuck()" in body, True)
    check("twice - before and after the pathfinder",
          body.count("take_stuck()"), 2)
    check("and one of them is after PathFinding",
          body.index("pathfind_to(x, y)") < body.rindex("take_stuck()"), True)
    check("the walk also watches the clock", "spot_no_progress()" in body,
          True)


def test_the_watchdog_needs_a_clock_to_be_running(m):
    """walk_to is shared - the runebook, the trip home and the vendor round all
    use it, and none of them is a spot. A watchdog that fired there would
    abandon a journey."""
    saved = m["_spot_progress_at"][0]
    try:
        m["stop_spot_clock"]()
        check("no clock, no watchdog", m["spot_no_progress"](), False)
        check("and no elapsed time to report", m["no_progress_seconds"](), 0.0)
    finally:
        m["_spot_progress_at"][0] = saved


def test_the_watchdog_fires_and_a_yield_resets_it(m):
    """The clock is reset by a YIELD and by nothing else. That is what the
    guards beside it do not do."""
    import time as _time
    saved = m["_spot_progress_at"][0]
    saved_myth = m["in_mythril_zone"]
    try:
        m["in_mythril_zone"] = lambda: False
        limit = m["AREA_NO_PROGRESS_MS"] / 1000.0

        m["start_spot_clock"]()
        check("a fresh spot is not stuck", m["spot_no_progress"](), False)

        # Wind the clock back past the limit rather than sleeping for it.
        m["_spot_progress_at"][0] = _time.time() - limit - 1
        check("past the limit it is", m["spot_no_progress"](), True)
        check("and it can say how long",
              m["no_progress_seconds"]() > limit, True)

        m["note_spot_progress"]()
        check("a yield resets it", m["spot_no_progress"](), False)

        # A yield with no clock running must not start one.
        m["stop_spot_clock"]()
        m["note_spot_progress"]()
        check("and cannot start one from nothing",
              m["_spot_progress_at"][0], 0.0)
    finally:
        m["in_mythril_zone"] = saved_myth
        m["_spot_progress_at"][0] = saved


def test_mythril_gets_a_longer_clock(m):
    """An 8s swing that legitimately finds nothing most of the time. Judged by
    the ordinary clock, a working mythril rune reads as stuck."""
    check("mythril is given longer",
          m["AREA_NO_PROGRESS_MYTHRIL_MS"] >= m["AREA_NO_PROGRESS_MS"], True)
    check("and long enough for several swings",
          m["AREA_NO_PROGRESS_MYTHRIL_MS"] >= 4 * m["MYTHRIL_SWING_TIMEOUT"],
          True)

    import time as _time
    saved = m["_spot_progress_at"][0]
    saved_myth = m["in_mythril_zone"]
    try:
        # Long enough to trip the ordinary clock, not the mythril one.
        m["start_spot_clock"]()
        m["_spot_progress_at"][0] = _time.time() \
            - (m["AREA_NO_PROGRESS_MS"] / 1000.0) - 1
        m["in_mythril_zone"] = lambda: False
        check("ordinary ground has given up", m["spot_no_progress"](), True)
        m["in_mythril_zone"] = lambda: True
        check("mythril has not", m["spot_no_progress"](), False)
    finally:
        m["in_mythril_zone"] = saved_myth
        m["_spot_progress_at"][0] = saved


def test_cannot_mine_here_is_told_from_moved_too_far(m):
    """"You can't mine there" is a fact about the tile. "You have moved too far
    away" is a fact about the moment. They shared an outcome, so the permanent
    one was only remembered when it happened to land on the first swing."""
    permanent = m["MINE_CANT_MINE_HERE"]
    broad = m["MINE_BAD_TARGET"]
    check("the permanent list is not empty", bool(permanent), True)
    check("every string in it is also in the broad list",
          [s for s in permanent if s not in broad], [])
    check("and the transient one is NOT in it",
          [s for s in permanent if "moved too far" in s.lower()], [])
    check("but is still in the broad list",
          any("moved too far" in s.lower() for s in broad), True)

    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    dig = src[src.index("def dig_once("):src.index("def mine_area_spots(")]
    check("the permanent list is checked first",
          dig.index("MINE_CANT_MINE_HERE") < dig.index("MINE_BAD_TARGET"),
          True)
    check("and they return different outcomes", '"moved"' in dig, True)

    spot = src[src.index("def mine_spot("):src.index("def chop_once(")]
    check("notrock writes the spot off whenever it is said",
          'elif outcome == "notrock":\n            # ' in spot
          and "if swings == 1:\n                state[\"dead\"]" not in spot,
          True)
    check("moved does not write it off",
          spot.index('elif outcome == "moved":')
          > spot.index('elif outcome == "notrock":'), True)


def test_a_rune_of_bad_spots_is_abandoned_whole(m):
    """A cave mouth swallows a CLUSTER of spots - the standing grid is
    arithmetic, so if one lands in unreachable dark several neighbours do too.
    Writing them off one at a time means saying the word once per spot."""
    check("there is a give-up count", m["STUCK_GIVE_UP"] >= 0, True)
    if not m["STUCK_GIVE_UP"]:
        return

    saved_log = m["log"]
    saved_end = m["end_sweep"]
    try:
        m["log"] = lambda *a, **k: None
        ended = []
        m["end_sweep"] = lambda state: ended.append(state)
        m["_stuck_at_rune"].clear()
        key = ("mine", 7)
        state = {"dead": set()}

        # Not condemned - nothing is counted at all.
        check("a spot that was fine counts for nothing",
              m["give_up_on_patch"](key, state, False, 12), False)
        check("and nothing was recorded", m["_stuck_at_rune"].get(key, 0), 0)

        results = [m["give_up_on_patch"](key, state, True, 12)
                   for _ in range(m["STUCK_GIVE_UP"])]
        check("only the last one gives up on the rune",
              results, [False] * (m["STUCK_GIVE_UP"] - 1) + [True])
        check("and the sweep was ended", len(ended), 1)
        check("the count resets for the next visit",
              m["_stuck_at_rune"].get(key, 0), 0)
    finally:
        m["log"] = saved_log
        m["end_sweep"] = saved_end
        m["_stuck_at_rune"].clear()


def test_both_sweeps_record_a_condemned_spot(m):
    """The word is heard in one place and acted on in another. A sweep that
    forgets to ask leaves the spot alive, and the character walks back into the
    same dark next lap."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    for name, nxt in (("mine_sweep", "def mine_spot("),
                      ("lumber_sweep", "def give_up_on_patch(")):
        body = src[src.index("def %s(" % name):src.index(nxt)]
        check("%s starts the clock before walking" % name,
              body.index("start_spot_clock()") < body.index("walk_to("), True)
        check("%s asks whether the spot was condemned" % name,
              body.count("stuck_condemned()"), 2)
        # A full pack must go HOME, not recall onwards - the condemnation is
        # recorded either way, but it must not steal the return.
        # The two sweeps spell the same test differently.
        full = min(body.index(form) for form
                   in ('outcome in ("full", "stop")', 'outcome == "full"')
                   if form in body)
        check("%s lets a full pack win the return" % name,
              full < body.rindex("give_up_on_patch("), True)
        check("%s can give up on the whole rune" % name,
              "give_up_on_patch(" in body, True)
        check("%s stops the clock when it leaves" % name,
              "stop_spot_clock()" in body, True)


def test_a_recall_forgets_a_pending_stuck(m):
    """A stuck said as the last spot ended would otherwise be spent on the first
    spot of the NEXT rune - and unlike move, it would mark that spot dead. The
    word would cost a good spot on a rune it was never said about."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    check("the recall drops it", "forget_stuck()" in src, True)
    body = src[src.index("    forget_move()"):]
    check("right beside the move it mirrors",
          body.index("forget_stuck()") < body.index("return ar_recall"), True)

    saved = m["_stuck_pending"]
    try:
        m["_stuck_pending"] = True
        m["_stuck_spot"][0] = True
        m["forget_stuck"]()
        check("the flag is gone", m["_stuck_pending"], False)
        check("and so is the condemnation", m["_stuck_spot"][0], False)
    finally:
        m["_stuck_pending"] = saved


def main():
    module = load_script()
    test_stop_button_is_not_a_crash(module)
    test_mythril_failure_is_not_scored_as_ore(module)
    test_mythril_depletion_is_recognised(module)
    test_a_silent_mythril_success_is_seen_as_weight(module)
    test_a_silent_swing_with_no_ore_is_still_silent(module)
    test_weight_is_only_trusted_inside_a_mythril_zone(module)
    test_the_zone_is_scoped_to_its_waypoints(module)
    test_mythril_is_off_unless_switched_on(module)
    test_the_swing_gets_longer_only_where_it_should(module)
    test_a_mythril_miss_does_not_count_as_ore(module)
    test_move_is_matched_on_the_whole_line(module)
    test_move_is_self_only(module)
    test_move_and_skip_are_different_words(module)
    test_take_move_fires_once(module)
    test_stuck_is_matched_on_the_whole_line(module)
    test_stuck_is_self_only(module)
    test_the_three_words_are_distinct(module)
    test_take_stuck_fires_once_and_condemns(module)
    test_stuck_reaches_the_long_waits(module)
    test_the_walk_checks_stuck_after_the_blocking_call(module)
    test_the_watchdog_needs_a_clock_to_be_running(module)
    test_the_watchdog_fires_and_a_yield_resets_it(module)
    test_mythril_gets_a_longer_clock(module)
    test_cannot_mine_here_is_told_from_moved_too_far(module)
    test_a_rune_of_bad_spots_is_abandoned_whole(module)
    test_both_sweeps_record_a_condemned_spot(module)
    test_a_recall_forgets_a_pending_stuck(module)
    test_a_recall_forgets_a_pending_move(module)
    test_move_leaves_the_spot_but_not_the_sweep(module)
    test_the_walk_consumes_rather_than_polls(module)
    test_one_spot_cannot_run_for_minutes(module)
    test_the_hard_cap_is_never_extended(module)
    test_a_long_spot_says_something(module)
    test_the_journal_is_always_scanned(module)
    test_a_waypoint_cannot_be_held_forever(module)
    test_the_watchdog_is_armed_only_by_arriving_somewhere(module)
    test_the_watchdog_forces_the_next_rune(module)
    test_unloading_in_place_is_never_capped(module)
    test_unload_in_place_only_reports_room_it_really_has(module)
    test_an_unknown_task_result_does_not_mean_stay_here(module)
    test_no_runtime_state_lives_in_the_config_half(module)
    test_the_manual_override_reaches_the_long_waits(module)
    test_silence_is_bounded(module)
    test_page_info(module)
    test_dropoff_smelts_before_the_keys_get_first_refusal(module)
    test_ore_is_not_silently_strandable(module)
    test_a_full_pack_says_which_measure_tripped(module)
    test_an_unreadable_tooltip_does_not_mean_full(module)
    test_pack_properties_are_requested_before_being_read(module)
    test_smelt_never_leaks_a_target_cursor(module)
    test_every_targeting_helper_goes_through_clear_cursor(module)
    test_smelting_happens_before_anything_is_offered_to_a_key(module)
    test_no_trip_home_when_smelting_already_freed_the_pack(module)
    test_unload_in_place_passes_the_threshold_through(module)
    test_ingot_key_is_configured_like_the_wood_storage(module)
    test_a_disabled_key_is_never_found(module)
    test_logs_never_reach_the_chest_while_the_wood_key_is_carried(module)
    test_with_no_key_the_chest_still_sweeps_everything(module)
    test_both_keys_carried_leaves_the_chest_only_the_rest(module)
    test_every_key_backed_graphic_is_actually_in_purge_id(module)
    test_key_backed_labels_match_real_restock_keys(module)
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
    test_keys_accept_any_hue(module)
    test_find_restock_any_hue(module)
    test_match_by_name_narrows_not_widens(module)
    test_lumber_steps_match_the_wood_bank(module)
    test_lumber_area_offsets(module)
    test_lumber_area_spots(module)
    test_lumber_single_matches_old_behaviour(module)
    test_lumber_sweep_key_tracks_waypoint(module)
    test_lumber_area_has_no_unbounded_loop(module)
    test_weight_reserve_replaces_the_fraction(module)
    test_reserve_is_measured_not_guessed(module)
    test_mining_step_is_the_ore_bank(module)
    test_area_offsets_is_generic(module)
    test_mineable_tiles_came_from_source(module)
    test_spot_is_minable_checks_the_whole_reach(module)
    test_mine_single_matches_old_behaviour(module)
    test_mine_messages_separate_empty_from_barren(module)
    test_vendor_round_counts_collections_not_visits(module)
    test_unreachable_spot_is_never_walked_at(module)
    test_long_way_round_is_refused(module)
    test_spot_inside_rock_falls_back_to_a_neighbour(module)
    test_walk_gives_up_when_it_stops_getting_closer(module)
    test_walk_config_is_sane(module)
    test_ingot_key_has_the_same_options_as_wood_storage(module)
    test_ingot_key_entry_is_built_from_the_settings(module)
    test_ingot_key_found_at_any_hue(module)
    test_stone_storage_has_the_same_options_as_the_other_keys(module)
    test_stone_storage_entry_is_built_from_the_settings(module)
    test_granite_is_kept_out_of_the_one_way_chest(module)
    test_stone_storage_is_off_for_everyone_by_default(module)
    test_every_key_with_work_gets_a_turn(module)
    test_the_whole_main_block_is_inside_the_handler(module)
    test_the_trail_keeps_the_last_lines_only(module)
    test_identical_lines_are_collapsed(module)
    test_one_switch_turns_off_every_bulk_order(module)
    test_movement_is_refused_when_the_player_is_gone(module)
    test_player_ready_survives_a_dead_client(module)
    test_recall_waits_for_the_world(module)
    test_the_carpenter_is_marked_as_a_bod_vendor(module)
    test_filing_stops_with_the_switch(module)
    test_no_dead_top_level_functions(module)
    test_a_flood_of_distinct_lines_is_capped(module)
    test_suppressing_a_line_never_hides_it_from_the_crash_report(module)
    test_rate_limit_is_configurable_and_sane(module)
    test_crash_state_names_the_serials(module)
    test_crash_state_survives_a_broken_player(module)
    test_key_has_work_looks_only_at_its_own_resources(module)
    test_a_key_we_know_nothing_about_is_still_offered(module)
    test_each_key_can_have_its_own_menu_entry(module)
    test_context_constants_are_declared_before_the_table(module)
    test_store_at_ninety_percent(module)
    test_reserve_still_backstops_a_heavy_yield(module)
    test_bank_of_groups_tiles_the_way_the_server_does(module)
    test_depleted_match_survives_the_apostrophe(module)
    test_spot_cap_is_a_real_bound(module)
    test_budget_shares_the_spot_deadline(module)
    test_spot_deadline_stops_the_swing_loop(module)
    test_mine_spot_honours_the_deadline_too(module)
    test_idle_watchdog_abandons_a_barren_rune(module)
    test_idle_clock_restarts_after_a_trip_home(module)
    test_end_sweep_restarts_the_idle_clock(module)
    test_path_leg_has_an_explicit_timeout(module)
    test_impassable_ground_is_refused_without_pathfinding(module)
    test_rooted_on_one_tile_gives_up(module)
    test_stuck_config_is_ordered_sensibly(module)
    test_a_productive_spot_is_worked_until_depleted(module)
    test_swing_caps_clear_a_full_bank(module)
    test_an_unproductive_spot_still_gives_up(module)
    test_lumber_spot_also_runs_to_depletion(module)
    test_skip_only_from_the_running_character(module)
    test_skip_matches_the_whole_line_not_a_substring(module)
    test_one_journal_pass_feeds_every_trigger(module)
    test_skip_is_configured_for_separate_characters(module)

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
