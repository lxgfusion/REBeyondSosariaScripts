"""
Full-loop simulation of harvest_runner.py.
==========================================

    python tests/sim_harvest_runner.py            # summary
    python tests/sim_harvest_runner.py -v         # every script log line

The other test file checks functions in isolation. This one builds a fake world
- a paged account runebook, a backpack that fills up, a wood key, trees that
run out - and then runs the REAL run_job() against it, start to finish, for
both mining and lumberjacking.

The question it answers: does a job actually work all of its runes, or does it
hand back early? Every recall, harvest, unload and job hand-off is recorded, so
an early exit shows exactly which waypoint it died on and why.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "harvest_runner.py")

VERBOSE = "-v" in sys.argv

FAILURES = []
LOG = []
EVENTS = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-52s got=%-22r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


# =============================================================================
# FAKE ACCOUNT RUNEBOOK
# =============================================================================

PER_PAGE = 9


class Book(object):
    """A paged runebook. Root lists folders; a folder lists runes.

    Recalling closes the gump, and reopening lands back at the root - which is
    what the real book does and is the awkward case for route tracking.
    """

    def __init__(self, layout):
        self.layout_def = layout          # {folder: [rune names]}
        self.view = None                  # None = root
        self.page = 1
        self.is_open = False
        self.recalls = []                 # (folder, rune) in order

    # -- structure ---------------------------------------------------------
    def folder_names(self):
        return list(self.layout_def.keys())

    def entries(self):
        if self.view is None:
            return [(n, False) for n in self.folder_names()]
        return [(n, True) for n in self.layout_def[self.view]]

    def total_pages(self):
        n = len(self.entries())
        return max(1, (n + PER_PAGE - 1) // PER_PAGE)

    def page_entries(self):
        start = (self.page - 1) * PER_PAGE
        return self.entries()[start:start + PER_PAGE], start

    # -- what Razor sees ---------------------------------------------------
    def lines(self):
        out = ["<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>"]
        if self.view is not None:
            out.append(self.view)
        out += ["New Rune", "New Runebook", "Organize"]
        entries, start = self.page_entries()
        for i, (label, is_rune) in enumerate(entries):
            out.append("%d. %s" % (start + i + 1, label))
            if is_rune:
                out.append("(%d, %d, -95)" % (1100 + start + i, 1400 + start + i))
        out.append("<BASEFONT COLOR=#FFFFFF><CENTER>Page %d/%d"
                   % (self.page, self.total_pages()))
        return out

    def raw_layout(self):
        pieces = ["{ page 0 }"]
        for control in (5, 503, 504):
            pieces.append("{ button 10 10 4005 4007 1 0 %d }" % control)
        entries, _start = self.page_entries()
        for i, (_label, is_rune) in enumerate(entries):
            bid = 10 + i
            pieces.append("{ button 60 %d 4005 4007 1 0 %d }" % (40 + i * 20, bid))
            if is_rune:
                pieces.append("{ button 90 %d 4005 4007 1 0 %d }"
                              % (40 + i * 20, bid + 30000))
        return "".join(pieces)

    # -- interaction -------------------------------------------------------
    def click(self, button):
        if button == 5:
            self.view, self.page = None, 1
            return
        if button == 504:
            if self.page < self.total_pages():
                self.page += 1
            return
        if button == 503:
            if self.page > 1:
                self.page -= 1
            return
        if 10 <= button < 10 + PER_PAGE:
            entries, start = self.page_entries()
            idx = button - 10
            if idx >= len(entries):
                return
            label, is_rune = entries[idx]
            if is_rune:
                EVENTS.append(("recall", self.view, label))
                self.recalls.append((self.view, label))
                WORLD.arrive(self.view, label)
                self.is_open = False          # recalling closes the gump
                self.view, self.page = None, 1
            else:
                self.view, self.page = label, 1


# =============================================================================
# FAKE WORLD
# =============================================================================

WOOD_KEY_SERIAL = 0x4290200A
BOD_BOOK_SERIAL = 0x413F54D6
AXE_SERIAL = 0x402119CB
BACKPACK_SERIAL = 0x41D40F58
PLAYER_SERIAL = 0x000CA4F7

SWINGS_PER_SPOT = 3         # harvests before a spot is exhausted
LOAD_PER_SWING = 40         # stones added per harvest
MAX_WEIGHT = 400


class World(object):
    def __init__(self, wood_key_in_pack=True):
        self.location = (None, None)
        self.weight = 0
        self.spot_swings = 0
        self.wood_key_in_pack = wood_key_in_pack
        self.harvests = []                # (folder, rune)
        self.unloads = 0

    def arrive(self, folder, rune):
        self.location = (folder, rune)
        self.spot_swings = 0

    def harvest(self):
        """Returns the journal line the server would send."""
        folder, rune = self.location
        if self.spot_swings >= SWINGS_PER_SPOT:
            return "There's not enough wood here to harvest."
        self.spot_swings += 1
        self.weight += LOAD_PER_SWING
        self.harvests.append((folder, rune))
        EVENTS.append(("harvest", folder, rune))
        return "You chop some logs and put them in your pack."

    def unload(self):
        self.weight = 0
        self.unloads += 1
        EVENTS.append(("unload", None, None))


WORLD = World()
BOOK = Book({})


# =============================================================================
# RAZOR API STUBS
# =============================================================================

class Item(object):
    def __init__(self, serial, item_id, hue=0, name="", container=None,
                 root=None):
        self.Serial = serial
        self.ItemID = item_id
        self.Hue = hue
        self.Name = name
        self.Amount = 1
        self.Container = container
        self.RootContainer = root
        self.props = []


BACKPACK = Item(BACKPACK_SERIAL, 0x0E75, name="Backpack",
                container=PLAYER_SERIAL, root=PLAYER_SERIAL)
AXE = Item(AXE_SERIAL, 0x48B2, name="gargish axe",
           container=PLAYER_SERIAL, root=PLAYER_SERIAL)
SHOVEL = Item(0x40001111, 0x0F39, name="a shovel",
              container=BACKPACK_SERIAL, root=BACKPACK_SERIAL)
WOOD_KEY = Item(WOOD_KEY_SERIAL, 0x1BD9, hue=0x0058, name="Wood Storage",
                container=BACKPACK_SERIAL, root=BACKPACK_SERIAL)
BOD_BOOK = Item(BOD_BOOK_SERIAL, 0x2259, name="Bulk Order Book",
                container=BACKPACK_SERIAL, root=BACKPACK_SERIAL)
BOD_BOOK.props = ["Bulk Order Book", "Blessed", "Deeds In Book: 0",
                  "Book Name: Hattori Hanzo"]

ITEMS_ALL = [BACKPACK, AXE, SHOVEL, WOOD_KEY, BOD_BOOK]


class Misc(object):
    def SendMessage(self, msg, colour=None, wait=None):
        LOG.append(str(msg))
        if VERBOSE:
            print("      | %s" % msg)

    def Pause(self, ms):
        pass

    def WaitForContext(self, entity, delay=None, show=None):
        # Every key and book offers the same menu; "Refill from stock" is at 2.
        return [Ctx(0, "Open"), Ctx(1, "Add"), Ctx(2, "Refill from stock")]

    def ContextReply(self, entity, label):
        serial = getattr(entity, "Serial", entity)
        if label != "Refill from stock":
            return
        if serial in (TAMING_BOOK_SERIAL, RO_BOOK_SERIAL):
            # Deposits on the reply alone, then shows the book's window.
            DEPOSITS.append(serial)
            GUMPS.open(BOOK_GUMP)
            return
        WORLD.unload()


class Ctx(object):
    def __init__(self, response, entry):
        self.Response = response
        self.Entry = entry


class Player(object):
    Serial = PLAYER_SERIAL
    Backpack = BACKPACK
    ManaMax = 100
    IsGhost = False
    WarMode = False
    Name = "Minerbot"
    _hands = {"LeftHand": AXE, "RightHand": None}

    @property
    def Mana(self):
        return 100

    def ChatSay(self, colour, msg=None):
        BOOK.is_open = True

    def GetSkillValue(self, name):
        return 100.0

    def GetItemOnLayer(self, layer):
        return Player._hands.get(layer)

    def EquipItem(self, serial):
        Player._hands["LeftHand"] = AXE

    def UnEquipItemByLayer(self, layer, wait=True):
        Player._hands[layer] = None

    def HeadMessage(self, colour, msg):
        pass

    def SetWarMode(self, flag):
        pass


PLAYER = Player()


class Items(object):
    loose = []      # extra items sitting in the pack
    moves = []      # (source, destination, amount)

    def FindBySerial(self, serial):
        for item in list(ITEMS_ALL) + list(Items.loose):
            if item.Serial == serial:
                return item
        return None

    def _candidates(self, ids, hue, container):
        """Generic lookup over everything the fake world holds."""
        out = []
        for item in list(ITEMS_ALL) + list(Items.loose):
            if item.ItemID not in ids:
                continue
            if hue != -1 and item.Hue != hue:
                continue
            # The wood key is the one item that can be in the pack or out in
            # the world, depending on the scenario.
            if item is WOOD_KEY:
                in_pack = container == BACKPACK_SERIAL
                if WORLD.wood_key_in_pack and not in_pack:
                    continue
                if not WORLD.wood_key_in_pack and container != -1:
                    continue
            elif container == -1:
                continue          # everything else is carried, not on the ground
            out.append(item)
        return out

    def FindByID(self, item_id, hue, container, rng, ignore):
        ids = item_id if isinstance(item_id, (list, tuple)) else [item_id]
        found = self._candidates(ids, hue, container)
        return found[0] if found else None

    def FindAllByID(self, item_id, hue, container, rng, ignore):
        ids = item_id if isinstance(item_id, (list, tuple)) else [item_id]
        return self._candidates(ids, hue, container)

    def GetPropStringList(self, item):
        props = getattr(item, "props", None)
        if props:
            return list(props)
        return ["Contents: 5/125 items, %d/%d stones"
                % (WORLD.weight, MAX_WEIGHT)]

    def GetPropStringByIndex(self, serial, index):
        return self.GetPropStringList(None)[0]

    def GetPropValue(self, item, name):
        return 0

    def WaitForProps(self, *a):
        pass

    def WaitForContents(self, *a):
        pass

    def UseItem(self, *a):
        pass

    def UseItemByID(self, *a):
        return False

    def Move(self, source, destination, amount=-1, *rest):
        Items.moves.append((source, destination, amount))
        Items.loose[:] = [i for i in Items.loose if i.Serial != source]


class JEntry(object):
    def __init__(self, text, stamp):
        self.Text = text
        self.Name = "System"
        self.Type = "Regular"
        self.Serial = 0
        self.Color = 0
        self.Timestamp = stamp


class Journal(object):
    def __init__(self):
        self.lines = []
        self.stamp = 0.0

    def add(self, text):
        self.stamp += 1.0
        self.lines.append(JEntry(text, self.stamp))

    def Search(self, text):
        return any(text in e.Text for e in self.lines)

    def Clear(self, text=None):
        if text is None:
            self.lines = []
        else:
            self.lines = [e for e in self.lines if text not in e.Text]

    def GetJournalEntry(self, after):
        return [e for e in self.lines if e.Timestamp > after]


JOURNAL = Journal()


class Target(object):
    def ClearQueue(self):
        pass

    def HasTarget(self):
        return False

    def Cancel(self):
        pass

    def WaitForTarget(self, delay, noshow):
        return True

    def TargetExecute(self, *a):
        pass

    def TargetResource(self, tool, kind):
        line = WORLD.harvest()
        if kind == 0 and "not enough wood" in line:
            line = "There is no metal here to mine."   # mining's wording
        elif kind == 0:
            line = "You dig some ore and put it in your pack."
        JOURNAL.add(line)


BOOK_GUMP = 0x06ABCE12
TAMING_BOOK_SERIAL = 0x4057CC3A
RO_BOOK_SERIAL = 0x404AC332

TAMING_BOOK = Item(TAMING_BOOK_SERIAL, 0xFF0, name="Taming Order Book")
RO_BOOK = Item(RO_BOOK_SERIAL, 0xFF0, name="Resource Order Book")
ITEMS_ALL.extend([TAMING_BOOK, RO_BOOK])


class GumpState(object):
    """Tracks the shared order-book gump so the stale-window trap is testable."""

    def __init__(self):
        self.open_id = None
        self.advanced = []          # (gumpid, button, switches, ids, values)
        self.opened_count = 0

    def open(self, gump_id):
        self.open_id = gump_id
        self.opened_count += 1

    def reset(self):
        self.open_id = None
        self.advanced = []
        self.opened_count = 0


GUMPS = GumpState()
DEPOSITS = []      # book serials that received a deposit


class Gumps(object):
    def HasGump(self, gump_id=None):
        if gump_id == BOOK_GUMP:
            return GUMPS.open_id == BOOK_GUMP
        return BOOK.is_open

    def CurrentGump(self):
        return 0xc395adb4

    def WaitForGump(self, gump_id, delay):
        if gump_id == BOOK_GUMP:
            # True only if the book actually opened it. Mirrors the real trap:
            # an already-open gump satisfies this immediately.
            return GUMPS.open_id == BOOK_GUMP
        BOOK.is_open = True
        return True

    def SendAdvancedAction(self, gump_id, button, switches, text_ids, text_vals):
        GUMPS.advanced.append((gump_id, button, list(switches),
                               list(text_ids), list(text_vals)))
        GUMPS.open_id = None        # answering it closes it

    def GetGumpRawLayout(self, gump_id):
        return BOOK.raw_layout()

    def GetLineList(self, gump_id, data_only=False):
        return BOOK.lines()

    def SendAction(self, gump_id, button):
        BOOK.click(button)

    def CloseGump(self, gump_id):
        if gump_id == BOOK_GUMP:
            GUMPS.open_id = None
            return
        BOOK.is_open = False

    def ResetGump(self):
        pass


class Mobiles(object):
    """No hostiles, no vendors."""
    hostiles = []

    def Filter(self):
        class NetList(list):
            def Add(self, v):
                self.append(v)

        class F(object):
            def __init__(self):
                self.Enabled = True
                self.RangeMax = -1
                self.CheckLineOfSight = False
                self.Notorieties = NetList()
                self.Bodies = NetList()
                self.Name = ""
        return F()

    def ApplyFilter(self, f):
        return list(Mobiles.hostiles)

    def WaitForProps(self, *a):
        pass

    def GetPropStringList(self, mob):
        return []


class Timer(object):
    def __init__(self):
        self.timers = {}

    def Create(self, name, ms):
        self.timers[name] = ms

    def Check(self, name):
        # True == still running. Everything created stays running for the sim.
        return name in self.timers

    def Remaining(self, name):
        return 0


# =============================================================================
# LOADER
# =============================================================================

def load(book_layout, wood_key_in_pack=True, hostiles=None):
    global BOOK, WORLD
    BOOK = Book(book_layout)
    WORLD = World(wood_key_in_pack=wood_key_in_pack)
    Mobiles.hostiles = hostiles or []
    Player._hands = {"LeftHand": AXE, "RightHand": None}
    JOURNAL.lines = []
    JOURNAL.stamp = 0.0
    GUMPS.reset()
    del DEPOSITS[:]
    del LOG[:]
    del EVENTS[:]

    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()

    env = {
        "__name__": "harvest_runner_sim",
        "Misc": Misc(), "Player": PLAYER, "Items": Items(),
        "Gumps": Gumps(), "Journal": JOURNAL, "Timer": Timer(),
        "Mobiles": Mobiles(), "Target": Target(), "PathFinding": None,
    }
    exec(compile(source, SCRIPT, "exec"), env)

    # The sim has no vendor stop and no drop-off rune; make the drop-off a
    # no-op that just empties the pack, so job flow is what is under test.
    def fake_dropoff():
        WORLD.unload()
        return True
    env["dropoff"] = fake_dropoff
    env["smelt"] = lambda: None
    env["vendor_round"] = lambda: None
    env["Timer"].Create("harvest vendors", 999999)
    env["Timer"].Create("harvest drop", 999999)
    return env


BOOK_LAYOUT = {
    "Mining": ["Mining (Malas) %d" % i for i in range(1, 10)],
    "Lumber": ["Lumber (Malas) %d" % i for i in range(1, 10)],
    "Homes": ["HOME"],
}

MINING_JOB = {"enabled": True, "name": "Mining", "folder": ["Mining"],
              "task": "mine"}
LUMBER_JOB = {"enabled": True, "name": "Lumberjacking", "folder": ["Lumber"],
              "task": "lumber"}


def runes_visited(folder):
    return [r for f, r in WORLD.harvests if f == folder]


def distinct_runes(folder):
    seen = []
    for rune in runes_visited(folder):
        if rune not in seen:
            seen.append(rune)
    return seen


def show_tail(n=14):
    print("      last log lines:")
    for line in LOG[-n:]:
        print("        %s" % line)


# =============================================================================
# SCENARIOS
# =============================================================================

def sim_lumber_full_route():
    print("\n--- lumberjacking, wood key carried, no hostiles ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    outcome = env["run_job"](LUMBER_JOB)
    visited = distinct_runes("Lumber")
    check("lumber outcome", outcome, "route")
    check("lumber worked all 9 runes", len(visited), 9)
    check("lumber never left for a drop-off", WORLD.unloads > 0, True)
    if len(visited) != 9:
        print("      visited: %s" % visited)
        show_tail()


def sim_mining_full_route():
    print("\n--- mining, 9 runes ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    outcome = env["run_job"](MINING_JOB)
    visited = distinct_runes("Mining")
    check("mining outcome", outcome, "route")
    check("mining worked all 9 runes", len(visited), 9)
    if len(visited) != 9:
        print("      visited: %s" % visited)
        show_tail()


def sim_lumber_key_at_house():
    print("\n--- lumberjacking, wood key at the house (trips home) ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=False)
    outcome = env["run_job"](LUMBER_JOB)
    visited = distinct_runes("Lumber")
    check("outcome with trips home", outcome, "route")
    check("all 9 runes despite unloading", len(visited), 9)
    check("did unload at least once", WORLD.unloads > 0, True)
    if len(visited) != 9:
        print("      visited: %s" % visited)
        show_tail()


def sim_rotation():
    print("\n--- both jobs in rotation ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    order = []
    for _ in range(2):
        for job in (MINING_JOB, LUMBER_JOB):
            order.append((job["name"], env["run_job"](job)))
    check("every job completed its route",
          [o for _n, o in order], ["route"] * 4)
    check("mining runes over two laps", len(distinct_runes("Mining")), 9)
    check("lumber runes over two laps", len(distinct_runes("Lumber")), 9)
    if [o for _n, o in order] != ["route"] * 4:
        print("      order: %s" % order)
        show_tail()


def sim_hostiles_everywhere():
    print("\n--- a hostile permanently in range ---")
    class Mob(object):
        Name = "a ratman"
        Serial = 0x999
        Body = 0x190
        Notoriety = 6
    env = load(BOOK_LAYOUT, wood_key_in_pack=True, hostiles=[Mob()])
    outcome = env["run_job"](LUMBER_JOB)
    visited = distinct_runes("Lumber")
    check("still finishes the route", outcome, "route")
    check("harvests despite hostiles", len(visited) > 0, True)
    if not visited:
        show_tail()


def sim_vendor_interrupt_resumes():
    """A vendor round mid-route must resume, not restart at waypoint 1.

    This is what the real trace exposed: run_job() reset the waypoint on entry,
    and main re-entered it after every vendor round.
    """
    print("\n--- vendor round interrupts a lumber route ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)

    # Work four waypoints, then pretend a vendor round happened.
    env["_waypoint"]["Lumberjacking"] = 4
    env["_routes"]["Lumberjacking"] = [(1, 10 + i, "Lumber (Malas) %d" % (i + 1))
                                       for i in range(9)]

    # Resuming must keep the position...
    env["run_job"](LUMBER_JOB, resume=True)
    visited = distinct_runes("Lumber")
    check("resume finishes the remaining runes", len(visited), 5)
    check("resume did not restart at rune 1",
          "Lumber (Malas) 1" in visited, False)

    # ...while a fresh start must reset it.
    env2 = load(BOOK_LAYOUT, wood_key_in_pack=True)
    env2["_waypoint"]["Lumberjacking"] = 4
    env2["run_job"](LUMBER_JOB, resume=False)
    check("fresh start works all 9", len(distinct_runes("Lumber")), 9)


def sim_pack_handover():
    """A job must not inherit the previous job's dead weight."""
    print("\n--- pack handover between jobs ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)

    check("handover level is stricter than full",
          env["PACK_HANDOVER_LEVEL"] < env["PACK_THRESHOLD"], True)
    check("dropoff between jobs is on", env["DROPOFF_BETWEEN_JOBS"], True)

    # Mining's leftovers: 225 of 495 stones, as measured in the real trace.
    WORLD.weight = 225
    check("225 stones counts as too heavy to hand over",
          env["pack_has_room"](env["PACK_HANDOVER_LEVEL"]), False)
    check("225 stones is NOT yet 'full'", env["pack_has_room"](), True)

    WORLD.weight = 40
    check("a light pack hands over fine",
          env["pack_has_room"](env["PACK_HANDOVER_LEVEL"]), True)


def sim_house_deposits():
    """The recorded order-book deposits, including the shared-gump trap."""
    print("\n--- house deposits (order books) ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)

    done = env["house_deposits"]()
    check("both books deposited", done, 2)
    check("both books received the deposit", sorted(DEPOSITS),
          sorted([TAMING_BOOK_SERIAL, RO_BOOK_SERIAL]))

    # The whole point: the deposit happens on the context reply. No amount is
    # sent, because the book's text field is for WITHDRAWING - writing to it
    # could pull items back out.
    check("no advanced action sent at all", GUMPS.advanced, [])
    check("each book opened its own window", GUMPS.opened_count, 2)
    check("the window was closed, not answered", GUMPS.open_id, None)

    text = "\n".join(LOG)
    check("uses Refill from stock", "Refill from stock" in text, True)

    # A stale window from something else must be closed, not answered.
    GUMPS.reset()
    del DEPOSITS[:]
    GUMPS.open(BOOK_GUMP)
    del LOG[:]
    done = env["house_deposits"]()
    check("still deposits with a stale gump open", done, 2)
    check("stale gump was closed first",
          "Closing a stale gump" in "\n".join(LOG), True)

    # A missing book must be reported, not silently skipped.
    GUMPS.reset()
    del DEPOSITS[:]
    del LOG[:]
    original = env["HOUSE_DEPOSITS"][0]["serial"]
    env["HOUSE_DEPOSITS"][0]["serial"] = 0x4FFFFFFF
    done = env["house_deposits"]()
    check("missing book is not counted", done, 1)
    check("missing book is reported",
          "is not in range" in "\n".join(LOG), True)
    env["HOUSE_DEPOSITS"][0]["serial"] = original


def sim_deposit_never_withdraws():
    """No code path may send an amount to an order book.

    The recorded macro ended with SendAdvancedAction(..., ["100"]). That field is
    for WITHDRAWING, so reproducing it risked pulling 100 items back out.
    """
    print("\n--- deposits never send an amount ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)

    env["house_deposits"]()
    env["refill_keys"]()
    check("no advanced action during a drop-off", GUMPS.advanced, [])

    src = open(SCRIPT, encoding="utf-8").read()
    body = src.split("def house_deposit(")[1].split("\ndef ")[0]
    check("house_deposit sends no advanced action",
          "SendAdvancedAction" in body, False)


def sim_deposit_entry_missing():
    """If the entry is gone the book is reported, not silently skipped."""
    print("\n--- order book menu changed ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    env["HOUSE_DEPOSIT_CONTEXT"][:] = ["Hand In Orders"]   # not on the menu
    done = env["house_deposits"]()
    text = "\n".join(LOG)
    check("unknown entry deposits nothing", done, 0)
    check("reports what the book offers", "has no entry matching" in text, True)
    env["HOUSE_DEPOSIT_CONTEXT"][:] = ["Refill from stock"]


def sim_bulk_order_filing():
    """Deeds go in the book - but taming orders must not.

    A bulk order deed and "A Taming Order" are both ItemID 0x2258, so filing by
    graphic alone would post the taming orders into the wrong book.
    """
    print("\n--- filing bulk order deeds ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)

    check("deed graphic is 0x2258", env["BOD_DEED_IDS"], [0x2258])

    # Auto-detection is the default so three characters share one script.
    check("no hardcoded serial", env["BOD_BOOK_SERIAL"], 0)
    check("no per-character entries by default",
          env["BOD_BOOK_BY_CHARACTER"], {})
    book, how = env["find_bod_book"]()
    check("book found by graphic", book.Serial, BOD_BOOK_SERIAL)
    check("and says how", "by graphic" in how, True)

    # An explicit serial overrides the graphic search.
    env["BOD_BOOK_SERIAL"] = BOD_BOOK_SERIAL
    book, how = env["find_bod_book"]()
    check("explicit serial used", how, "BOD_BOOK_SERIAL")
    env["BOD_BOOK_SERIAL"] = 0

    # A per-character entry wins over both.
    env["BOD_BOOK_BY_CHARACTER"]["Minerbot"] = BOD_BOOK_SERIAL
    book, how = env["find_bod_book"]()
    check("per-character entry wins", "configured for Minerbot" in how, True)
    env["BOD_BOOK_BY_CHARACTER"].clear()

    # A real bulk order, and a taming order sharing the graphic.
    bod = Item(0x40005001, 0x2258, name="a bulk order deed")
    bod.props = ["a bulk order deed", "Amount to make: 10",
                 "Item requested: ingots"]
    taming = Item(0x40005002, 0x2258, name="A Taming Order")
    taming.props = ["A Taming Order",
                    "Level: 2Creature Type: KirinFilled: 24/60"]
    Items.loose[:] = [bod, taming]
    Items.moves[:] = []

    check("bulk order recognised", env["is_bulk_order"](bod), True)
    check("taming order rejected", env["is_bulk_order"](taming), False)

    filed = env["file_bulk_orders"]()
    check("filed exactly one deed", filed, 1)
    check("the bulk order was moved", [m[0] for m in Items.moves],
          [bod.Serial])
    check("the taming order was left alone",
          taming.Serial in [m[0] for m in Items.moves], False)
    check("it went into the book", Items.moves[0][1], BOD_BOOK_SERIAL)

    text = "\n".join(LOG)
    check("logs what it filed", "a bulk order deed" in text, True)
    check("reports the book count", "Bulk Order Book:" in text, True)

    # Missing book must be reported, and nothing moved.
    Items.moves[:] = []
    del LOG[:]
    env["BOD_BOOK_SERIAL"] = 0x4FFFFFFF
    check("missing book files nothing", env["file_bulk_orders"](), 0)
    check("nothing was moved", Items.moves, [])
    check("missing book reported",
          "No Bulk Order Book" in "\n".join(LOG), True)
    env["BOD_BOOK_SERIAL"] = 0

    Items.loose[:] = []
    Items.moves[:] = []


def sim_large_bulk_order_gump():
    """Large and small bulk orders use different gump ids."""
    print("\n--- large vs small bulk order gump ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    scribe = [v for v in env["all_vendors"]()
              if "Scribe" in v["names"]][0]
    ids = env["gump_ids"](scribe)
    check("small bulk order gump listed", 0x9BADE6EA in ids, True)
    check("large bulk order gump listed", 0xBE0DAD1E in ids, True)
    check("both take button 1",
          sorted(set(b for _g, b in scribe["gump"])), [1])


def sim_diagnostic_mode():
    """The diagnostic must itself run cleanly - a broken one wastes a test run."""
    print("\n--- diagnostic mode ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    env["DIAGNOSTIC_MODE"] = True
    try:
        env["diagnostic_run"]([MINING_JOB, LUMBER_JOB])
        crashed = None
    except Exception as err:
        crashed = "%s: %s" % (type(err).__name__, err)

    check("diagnostic run does not crash", crashed, None)
    text = "\n".join(LOG)
    check("traces both jobs",
          ("JOB: Mining" in text and "JOB: Lumberjacking" in text), True)
    check("lists the routes", "route: 9 rune(s)" in text, True)
    check("walks every lumber waypoint",
          "Lumberjacking waypoint 9 of 9" in text, True)
    check("reports what the server said", "journal:" in text, True)
    check("classifies lumber messages", "matched: SUCCESS" in text, True)
    check("prints a summary", "SUMMARY" in text, True)
    if crashed:
        show_tail(20)


def sim_unrecognised_lumber_message():
    """If the shard's wording is unknown the diagnostic must say so loudly."""
    print("\n--- diagnostic with an unrecognised harvest message ---")
    env = load(BOOK_LAYOUT, wood_key_in_pack=True)
    env["DIAGNOSTIC_MODE"] = True
    # Pretend the shard says something the LUMBER_* lists do not cover.
    original = WORLD.harvest

    def odd_message():
        original()
        return "You swing your axe and gather timber."
    WORLD.harvest = odd_message

    env["diagnostic_run"]([LUMBER_JOB])
    text = "\n".join(LOG)
    check("flags the unrecognised message",
          "matched: NOTHING" in text, True)
    check("shows the raw line",
          "You swing your axe and gather timber" in text, True)


def main():
    sim_mining_full_route()
    sim_lumber_full_route()
    sim_lumber_key_at_house()
    sim_rotation()
    sim_hostiles_everywhere()
    sim_vendor_interrupt_resumes()
    sim_pack_handover()
    sim_house_deposits()
    sim_bulk_order_filing()
    sim_large_bulk_order_gump()
    sim_deposit_never_withdraws()
    sim_deposit_entry_missing()
    sim_diagnostic_mode()
    sim_unrecognised_lumber_message()

    print()
    if FAILURES:
        print("FAILED (%d):" % len(FAILURES))
        for name in FAILURES:
            print("  -", name)
        return 1
    print("simulation clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
