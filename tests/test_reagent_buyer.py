"""Offline tests for Scripts/ReagentBuyer.py.

    python tests/test_reagent_buyer.py

Execs the real script with stub Razor globals and calls the real functions.

The three faults this script exists to fix are each pinned here:

  * the vendor was matched on Mobiles.Filter().Name, which is an EXACT match
    against a NAME, while "the mage" is a TITLE and lives in the tooltip
  * the Buy Agent was named but never enabled, so every shop bought nothing
  * the runebook's next-page button was guessed as 6; it is 504
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "ReagentBuyer.py")

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


def call(label, fn, want, *args):
    """check() for a real call: an exception is a FAILURE, not a traceback
    that hides every check after it."""
    try:
        got = fn(*args)
    except Exception as err:
        got = "raised %s: %s" % (type(err).__name__, err)
    check(label, got, want)


class Mob(object):
    def __init__(self, serial, name, props=(), distance=1):
        self.Serial = serial
        self.Name = name
        self.Props = list(props)
        self.distance = distance


class Entry(object):
    def __init__(self, text):
        self.Entry = text


class Position(object):
    def __init__(self, x, y, z=0):
        self.X, self.Y, self.Z = x, y, z


class Stub(object):
    """Misc / Items / Gumps / Mobiles / Player, all in one recorder."""

    def __init__(self, menu=(), mobiles=(), gold=1000, pos=(0, 0),
                 layout="", lines=(), buy_agent_on=True):
        self.menu = list(menu)
        self.mobiles = list(mobiles)
        self.Gold = gold
        self.Position = Position(*pos)
        self.layout = layout
        self.lines = list(lines)
        self.buy_agent_on = buy_agent_on
        self.IsGhost = False
        # preflight refuses without one, so the agent setup is never reached.
        self.Backpack = type("B", (), {"Serial": 0x41D40F58, "Contains": []})()

        self.replied = []
        self.said = []
        self.messages = []
        self.actions = []
        self.agent_list = None
        self.agent_enabled = False

    # --- Misc --------------------------------------------------------------
    def SendMessage(self, msg, hue=0, wait=False):
        self.messages.append(msg)

    def Pause(self, ms):
        pass

    def WaitForContext(self, serial, delay, show=False):
        return [Entry(t) for t in self.menu]

    def ContextReply(self, serial, label):
        self.replied.append((int(serial), label))

    # --- Player ------------------------------------------------------------
    def ChatSay(self, *args):
        self.said.append(args[-1])

    def DistanceTo(self, mob):
        return getattr(mob, "distance", 1)

    # --- Mobiles -----------------------------------------------------------
    def Filter(self):
        return type("F", (), {"Enabled": False, "RangeMax": None})()

    def ApplyFilter(self, f):
        self.last_range = getattr(f, "RangeMax", None)
        return list(self.mobiles)

    def WaitForProps(self, mob, delay):
        return True

    def GetPropStringList(self, mob):
        return list(getattr(mob, "Props", []))

    # --- Items -------------------------------------------------------------
    def FindBySerial(self, serial):
        return type("I", (), {"Serial": int(serial)})()

    # --- Gumps -------------------------------------------------------------
    def HasGump(self, gump_id):
        return True

    def WaitForGump(self, gump_id, delay):
        return True

    def GetGumpRawLayout(self, gump_id):
        return self.layout

    def GetLineList(self, gump_id, dataOnly=False):
        return list(self.lines)

    def SendAction(self, gump_id, button):
        self.actions.append(int(button))

    # --- BuyAgent ----------------------------------------------------------
    def ChangeList(self, name):
        self.agent_list = name

    def Enable(self):
        self.agent_enabled = True

    def Status(self):
        return self.buy_agent_on and self.agent_enabled

    def __getattr__(self, name):
        return lambda *a, **k: None


def load(stub):
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    env = {"__name__": "reagent_under_test",
           "Misc": stub, "Items": stub, "Gumps": stub, "Mobiles": stub,
           "Player": stub, "Target": stub, "BuyAgent": stub, "Journal": stub}
    exec(compile(source, SCRIPT, "exec"), env)
    return env


# ---------------------------------------------------------------------------
# THE VENDOR LOOKUP - fault 1
# ---------------------------------------------------------------------------

def test_the_title_is_read_from_the_tooltip_not_the_name():
    """Mobiles.Filter().Name is an EXACT match against the NAME. "the mage" is
    a TITLE and lives in the tooltip, so the old filter matched nothing,
    ever."""
    mage = Mob(1, "Zoe", props=["Zoe", "the mage"])
    alch = Mob(2, "Hali", props=["Hali", "the alchemist"])
    smith = Mob(3, "Gorn", props=["Gorn", "the blacksmith"])
    stub = Stub(mobiles=[mage, alch, smith])
    m = load(stub)

    check("the mage, by tooltip title", m["is_vendor"](mage), True)
    check("the alchemist too", m["is_vendor"](alch), True)
    check("but not the blacksmith", m["is_vendor"](smith), False)
    check("both are returned", [int(x.Serial) for x in m["vendors_in_range"]()],
          [1, 2])


def test_a_guildmaster_is_refused():
    """Their menu charges for training rather than selling reagents."""
    boss = Mob(4, "Lysander", props=["Lysander", "the mage Guildmaster"])
    stub = Stub(mobiles=[boss])
    m = load(stub)
    check("refused even though the title matches", m["is_vendor"](boss), False)
    check("and so never approached", m["vendors_in_range"](), [])


def test_the_range_is_always_set():
    """An unset RangeMax means everything the client knows about - 18-25 tiles
    of other people's vendors. See CLAUDE.md."""
    stub = Stub(mobiles=[Mob(1, "Zoe", props=["the mage"])])
    m = load(stub)
    m["vendors_in_range"]()
    check("RangeMax was set on the filter", stub.last_range, m["VENDOR_RANGE"])


def test_a_vendor_named_outright_still_matches():
    """Cheap first look at the name, so a shard that puts the title in the
    name costs no tooltip wait."""
    plain = Mob(5, "Zoe the mage", props=[])
    stub = Stub(mobiles=[plain])
    m = load(stub)
    check("matched on the name alone", m["is_vendor"](plain), True)


# ---------------------------------------------------------------------------
# THE BUY AGENT - fault 2
# ---------------------------------------------------------------------------

def test_the_buy_agent_is_actually_turned_on():
    """Naming a list is not using one. The old script set BUY_LIST_NAME and
    never told Razor, so every shop window bought nothing."""
    stub = Stub(menu=["Buy", "Sell"], lines=["Page 1/1"])
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britain", [100, 100, 0])]
    m["preflight"]()
    check("the list was selected", stub.agent_list, m["BUY_LIST_NAME"])
    check("and the agent enabled", stub.agent_enabled, True)


def test_it_refuses_to_run_when_the_agent_will_not_come_on():
    """Nothing would be bought, so a run would be a lap of pointless
    recalls."""
    stub = Stub(buy_agent_on=False, lines=["Page 1/1"])
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britain", [100, 100, 0])]
    call("preflight stops the run", m["preflight"], False)
    check("and says why", any("will not turn on" in x for x in stub.messages),
          True)


def test_a_purchase_is_proved_by_gold_spent():
    """The shop window opening is not evidence that anything was bought."""
    mage = Mob(1, "Zoe", props=["the mage"])
    stub = Stub(menu=["Buy", "Sell", "Bribe"], mobiles=[mage], gold=1000)
    m = load(stub)

    def spend(serial, label):
        stub.replied.append((int(serial), label))
        stub.Gold = 820
    stub.ContextReply = spend
    call("the gold difference is returned", m["buy_from"], 180, mage)
    check("and Buy was the entry sent", stub.replied[-1][1], "Buy")

    stub2 = Stub(menu=["Buy", "Sell"], mobiles=[mage], gold=1000)
    m2 = load(stub2)
    call("a vendor that sells nothing reports 0", m2["buy_from"], 0, mage)
    check("and says the list may not match",
          any("may not match" in x for x in stub2.messages), True)


def test_sell_and_bribe_are_never_pressed():
    """They sit on the same menu as Buy and both cost money."""
    stub = Stub(menu=["Sell", "Bribe", "Train Magery"])
    m = load(stub)
    check("nothing matches Buy", m["pick_entry"](list(stub.menu),
                                                 m["BUY_ENTRIES"]), None)
    check("and the blocklist covers them",
          [m["context_is_blocked"](x) for x in stub.menu], [True, True, True])

    # A label that DOES match loosely and is still refused. Without one of
    # these the blocklist is never reached, so the check above passes whether
    # it works or not.
    check("a loose match that is dangerous is refused",
          m["pick_entry"](["Buy/Sell stolen goods"], m["BUY_ENTRIES"]), None)
    check("and the same on a storage key",
          m["pick_entry"](["Refill from stock and destroy the rest"],
                          m["FILL_ENTRIES"]), None)
    check("while a clean loose match is still taken",
          m["pick_entry"](["Buy reagents"], m["BUY_ENTRIES"]), "Buy reagents")


# ---------------------------------------------------------------------------
# THE RUNEBOOK - fault 3
# ---------------------------------------------------------------------------

def test_the_page_buttons_are_the_inspected_ones():
    """goNextPage() pressed 6, which does nothing, so every rune past page 1
    was unreachable. 504/503/5 came off the Gump Inspector - see
    docs/account-runebook-gump.md."""
    stub = Stub()
    m = load(stub)
    check("next page", m["AR_NEXT_PAGE_BUTTON"], 504)
    check("previous page", m["AR_PREV_PAGE_BUTTON"], 503)
    check("back to root", m["AR_ROOT_BUTTON"], 5)
    check("and 6 is not treated as a control",
          6 in m["AR_CONTROL_BUTTONS"], True)


def test_runes_are_told_from_folders_by_their_coordinates():
    """A rune is followed by a coordinate line; a folder is not."""
    layout = ("{ button 20 40 4005 4007 1 0 10 }"
              "{ button 20 70 4005 4007 1 0 11 }"
              "{ button 20 100 4005 4007 1 0 12 }"
              "{ button 500 20 4005 4007 1 0 30010 }"
              "{ button 500 40 4005 4007 1 0 30011 }")
    lines = ["<CENTER>Account Runebook</CENTER>", "Town Vendors",
             "New Rune", "New Runebook", "Organize",
             "1. Britain Mage", "(1430, 1690, 0)",
             "2. Vesper Alchemist", "(2770, 980, 0)",
             "3. More Shops",
             "<CENTER>Page 1/2"]
    stub = Stub(layout=layout, lines=lines)
    m = load(stub)

    folders, runes = m["parse_ar_page"]()
    check("two runes", sorted(runes), [10, 11])
    check("named right", [runes[b]["name"] for b in sorted(runes)],
          ["Britain Mage", "Vesper Alchemist"])
    check("with their coordinates", runes[10]["coord"], [1430, 1690, 0])
    check("and the third is a folder", folders, {12: "More Shops"})
    check("the page footer is read", m["ar_page_info"](), (1, 2))


# The real "Town Vendors" folder, 2026-10-24. Names are TRUNCATED in the gump
# exactly as shown here, and every row draws THREE buttons: recall, gate
# (+30000) and an X that DELETES the rune (+60000).
LIVE_PAGE_1 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "Town Vendors", "New Rune", "New Runebook", "Organize",
    "1. Britt Mage Shop (Tramm...", "(1492, 1544, 35)",
    "2. Vesper Mage Shop (Tra...", "(2916, 675, 0)",
    "3. Papua Mage Shop (Tram...", "(5736, 3196, 10)",
    "4. Delucia Mage Shop (Tra...", "(5293, 3978, 37)",
    "5. Moonglow Mage Shop (Tr...", "(4453, 1084, 0)",
    "6. New Haven Mage Shop (...", "(3497, 2528, 27)",
    "7. Serpents Hold Mage Sho...", "(3007, 3362, 15)",
    "8. Skara Brae Mage Shop ...", "(603, 2179, 0)",
    "9. Trinsic Mage Shop (Tram...", "(1845, 2711, 10)",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/2",
]
LIVE_PAGE_2 = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "Town Vendors", "New Rune", "New Runebook", "Organize",
    "10. Vesper Mage Shop (Tra...", "(2916, 676, 0)",
    "11. Britt Carp Shop (Tramm...", "(1434, 1595, 20)",
    "12. Britt Blasksmith (Tram...", "(1419, 1554, 30)",
    "13. Britt Inscribe (Trammel)", "(1494, 1718, 7)",
    "14. Umbra Mage Shop (Malas)", "(2025, 1383, -8...",
    "15. Zento Mage Shop (Toku...", "(691, 1296, 26)",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 2/2",
]


def live_layout(count):
    """A folder page as the server draws it: recall, gate and DELETE per row."""
    pieces = ["{ button 20 440 4014 4015 1 0 503 }",
              "{ button 400 440 4005 4006 1 0 504 }"]
    for i in range(count):
        entry = 10 + i
        y = 90 + i * 40
        pieces.append("{ button 545 %d 4005 4007 1 0 %d }" % (y, entry))
        pieces.append("{ button 575 %d 4011 4012 1 0 %d }"
                      % (y, entry + 30000))
        pieces.append("{ button 605 %d 4017 4018 1 0 %d }"
                      % (y, entry + 60000))
    return "".join(pieces)


def test_only_the_mage_shops_are_visited():
    """The folder is not all reagent shops: inspected 2026-10-24 it also holds
    Britt Carp Shop, Britt Blasksmith and Britt Inscribe."""
    pages = [(LIVE_PAGE_1, live_layout(9)), (LIVE_PAGE_2, live_layout(6))]
    stub = Stub()
    state = {"page": 0}
    stub.lines = pages[0][0]
    stub.layout = pages[0][1]

    def step(gump_id, button):
        stub.actions.append(int(button))
        if int(button) == 504 and state["page"] + 1 < len(pages):
            state["page"] += 1
        elif int(button) == 503 and state["page"] > 0:
            state["page"] -= 1
        stub.lines = pages[state["page"]][0]
        stub.layout = pages[state["page"]][1]
    stub.SendAction = step

    m = load(stub)
    runes = m["collect_runes"]()
    names = [r[2] for r in runes]
    check("twelve mage shops, both pages", len(runes), 12)
    check("the carpenter is left out",
          any("Carp" in n for n in names), False)
    check("so is the blacksmith", any("Blasksmith" in n for n in names), False)
    check("and the scribe", any("Inscribe" in n for n in names), False)
    check("page 2's mage shops are included",
          any("Umbra" in n for n in names) and any("Zento" in n for n in names),
          True)
    check("and it said what it skipped",
          any("skipping 3 rune(s)" in x for x in stub.messages), True)

    # The truncated coordinate on Umbra's row is still read as a coordinate.
    umbra = [r for r in runes if "Umbra" in r[2]]
    check("a truncated coordinate still parses",
          umbra[0][3][:2] if umbra else None, [2025, 1383])


def test_a_truncated_name_still_matches():
    """The gump cut "Serpents Hold Mage Shop" to "Serpents Hold Mage Sho...".
    A straight substring test drops that rune and says nothing."""
    m = load(Stub())
    w = m["wanted_rune"]
    check("the phrase survives intact", w("Britt Mage Shop (Tramm..."), True)
    check("THE REPORTED CASE: cut through the phrase",
          w("Serpents Hold Mage Sho..."), True)
    check("cut right after it", w("Skara Brae Mage Shop ..."), True)
    check("cut down to just the first word", w("Umbra Mage"), True)

    check("a carpenter is not a mage shop", w("Britt Carp Shop (Tramm..."),
          False)
    check("nor a blacksmith", w("Britt Blasksmith (Tram..."), False)
    check("nor a scribe", w("Britt Inscribe (Trammel)"), False)
    check("and a word that merely starts the same is not enough",
          w("Magery Trainer"), False)

    saved = m["RUNE_MUST_MATCH"]
    try:
        m["RUNE_MUST_MATCH"] = []
        check("an empty list visits everything", w("Britt Carp Shop"), True)
    finally:
        m["RUNE_MUST_MATCH"] = saved


def test_the_delete_button_is_never_paired_or_pressed():
    """Every rune row draws an X at entry + 60000. Pairing one as an entry
    would not misfire a recall - it would DELETE somebody's rune."""
    stub = Stub(lines=LIVE_PAGE_1, layout=live_layout(9))
    m = load(stub)

    _folders, runes = m["parse_ar_page"]()
    check("nine runes, one per row", len(runes), 9)
    check("paired to the RECALL buttons only",
          sorted(runes), list(range(10, 19)))
    check("no gate button was paired",
          any(b >= 30000 for b in runes), False)
    check("and no delete button",
          any(b >= 60000 for b in runes), False)

    # The REAL protection is sorting the buttons and zipping shortest-first -
    # the range cap is belt and braces. But a cap that lets gates and deletes
    # in makes the parser cry "the pairing may be off" on every single page,
    # which is noise that would hide a mismatch that mattered.
    check("and no pairing warning on a perfectly normal page",
          any("pairing may be off" in x for x in stub.messages), False)

    m["collect_runes"]()
    check("nothing in the delete range was ever pressed",
          [b for b in stub.actions if b >= 60000], [])
    check("nor the gate range",
          [b for b in stub.actions if 30000 <= b < 60000], [])


def test_the_folder_is_found_on_a_later_page():
    """"Town Vendors" is entry 16, on page 2/3 of the root - a search that
    reads only the first page never finds it."""
    root1 = ["<CENTER>Account Runebook</CENTER>", "New Rune", "New Runebook",
             "Organize"] + ["%d. Folder%d" % (i, i) for i in range(1, 10)] + [
             "<CENTER>Page 1/3"]
    root2 = ["<CENTER>Account Runebook</CENTER>", "New Rune", "New Runebook",
             "Organize", "10. RO", "11. TamingDeed", "12. Farming",
             "13. TMAP Spots", "14. Champ Spawns", "15. Overlords",
             "16. Town Vendors", "17. IDOC", "18. population control",
             "<CENTER>Page 2/3"]
    # WITH the page buttons: without them ar_page_step cannot turn the page,
    # and the test would fail on its own fixture rather than on the code.
    folder_layout = ("{ button 20 440 4014 4015 1 0 503 }"
                     "{ button 400 440 4005 4006 1 0 504 }") + "".join(
        "{ button 545 %d 4005 4007 1 0 %d }" % (90 + i * 40, 10 + i)
        for i in range(9))

    pages = [root1, root2]
    stub = Stub(lines=root1, layout=folder_layout)
    state = {"page": 0, "entered": None}

    def step(gump_id, button):
        stub.actions.append(int(button))
        if int(button) == 504 and state["page"] + 1 < len(pages):
            state["page"] += 1
            stub.lines = pages[state["page"]]
        elif int(button) == 503 and state["page"] > 0:
            state["page"] -= 1
            stub.lines = pages[state["page"]]
        elif 10 <= int(button) <= 499:
            state["entered"] = int(button)
    stub.SendAction = step

    m = load(stub)
    call("the folder is found", m["ar_enter_folder"], True, "Town Vendors")
    check("by pressing ITS button, the 7th on page 2", state["entered"], 16)


def test_a_recall_is_checked_against_the_runes_own_coordinates():
    """The runebook prints them, so arriving is checkable rather than assumed.
    """
    stub = Stub(pos=(1430, 1690))
    m = load(stub)
    check("standing on it", m["arrived_at"]([1430, 1690, 0]), True)
    check("two tiles off is still there", m["arrived_at"]([1432, 1691, 0]),
          True)
    check("a town away is not", m["arrived_at"]([2770, 980, 0]), False)
    check("no coordinates means it cannot be told",
          m["arrived_at"](None), None)


def test_the_gate_button_is_never_pressed():
    """entry + 30000 opens a gate instead of recalling."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    check("the offset is known", "AR_GATE_OFFSET = 30000" in src, True)
    uses = [l for l in code.splitlines()
            if "AR_GATE_OFFSET" in l and "AR_GATE_OFFSET =" not in l]
    check("used in exactly one place", len(uses), 1)
    check("and that place only IDENTIFIES a rune, never presses it",
          "in buttons" in uses[0] if uses else False, True)


# ---------------------------------------------------------------------------
# STORING
# ---------------------------------------------------------------------------

def test_the_storage_key_is_answered_by_label_not_index():
    """The old script sent context entry 2 - whatever the shard happened to
    put in that slot, and on a key the neighbours take things OUT."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    # The module docstring QUOTES the old buggy call to explain it, so the
    # docstrings have to go before looking - otherwise the explanation fails
    # the very check it is explaining.
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(l.split("#", 1)[0] for l in code.splitlines())
    check("no numeric context reply",
          re.search(r"ContextReply\([^)]*,\s*\d+\s*\)", code) is None, True)

    stub = Stub(menu=["Open", "Add", "Refill from stock"])
    m = load(stub)
    m["pack_count"] = lambda: 5 if not stub.replied else 1
    call("it stores", m["store_haul"], True)
    check("by the real label",
          stub.replied[-1][1] if stub.replied else "(nothing was pressed)",
          "Refill from stock")


class Bag(object):
    def __init__(self, serial, contains=()):
        self.Serial = serial
        self.IsContainer = True
        self.Contains = list(contains)


def key_world(where):
    """A pack holding a bag holding a bag, with the key at `where`.

    The key only resolves by serial once the container it is in has been
    opened - which is the whole trap: an item in a bag the client has never
    looked in can fail to resolve at all.
    """
    inner = Bag(0x42385516)
    outer = Bag(0x42385515, [inner])
    pack = Bag(0x41D40F58, [outer])
    stub = Stub(menu=["Open", "Add", "Refill from stock"])
    stub.Backpack = pack
    opened = []

    def find(serial):
        serial = int(serial)
        if serial == 0x4335A205 and where not in opened and where != "pack":
            return None
        for bag in (pack, outer, inner):
            if int(bag.Serial) == serial:
                return bag
        return type("I", (), {"Serial": serial, "IsContainer": False})()

    stub.FindBySerial = find
    stub.UseItem = lambda item: opened.append(int(item.Serial))
    return stub, opened


def test_the_key_is_found_loose_in_the_pack():
    """The usual case, and it must cost nothing: no bag is opened looking for
    something already in sight."""
    stub, opened = key_world("pack")
    m = load(stub)
    m["STORAGE_KEY_SERIAL"] = 0x4335A205
    check("found straight away", m["find_storage_key"]() is not None, True)
    check("and no bag was opened for it", opened, [])


def test_the_key_is_found_in_a_bag_without_being_told_which():
    """Inspected 2026-10-24: the Master Keys sit in a bag inside the pack.
    KEY_BAG_SERIAL is 0, so the bags get turned out until it appears."""
    stub, opened = key_world(0x42385515)
    m = load(stub)
    m["STORAGE_KEY_SERIAL"] = 0x4335A205
    check("found in the end", m["find_storage_key"]() is not None, True)
    check("by opening the pack and then that bag",
          opened, [0x41D40F58, 0x42385515])


def test_the_key_is_found_in_a_bag_inside_a_bag():
    stub, opened = key_world(0x42385516)
    m = load(stub)
    m["STORAGE_KEY_SERIAL"] = 0x4335A205
    check("found two deep", m["find_storage_key"]() is not None, True)
    check("having opened both bags on the way",
          opened, [0x41D40F58, 0x42385515, 0x42385516])


def test_the_bags_are_turned_out_once_not_before_every_deposit():
    """Opening every bag before each deposit is the churn that made the bottle
    opener flap windows open all run."""
    stub, opened = key_world("nowhere")
    m = load(stub)
    m["STORAGE_KEY_SERIAL"] = 0x4335A205
    check("not found", m["find_storage_key"](), None)
    first = len(opened)
    check("it did look", first > 1, True)

    m["find_storage_key"]()
    m["find_storage_key"]()
    check("and did not look again", len(opened), first)

    # Unless something asks it to, which is what preflight does.
    m["find_storage_key"](True)
    check("force searches again", len(opened) > first, True)


def test_a_configured_bag_skips_the_search():
    stub, opened = key_world(0x42385515)
    m = load(stub)
    m["STORAGE_KEY_SERIAL"] = 0x4335A205
    m["KEY_BAG_SERIAL"] = 0x42385515
    check("found", m["find_storage_key"]() is not None, True)
    check("straight to the bag, no walking", opened, [0x42385515])


def test_either_kind_of_key_works():
    """A Master Key and a reagent key take the same single click and the same
    "Refill from stock" - only the serial differs."""
    stub = Stub(menu=["Open", "Add", "Refill from stock"])
    m = load(stub)
    m["pack_count"] = lambda: 5 if not stub.replied else 1
    for serial in (0x4335A205, 0x404D69CE):
        del stub.replied[:]
        m["STORAGE_KEY_SERIAL"] = serial
        call("0x%X stores" % serial, m["store_haul"], True)
        check("  pressed by label on 0x%X" % serial,
              stub.replied[-1][1] if stub.replied else None,
              "Refill from stock")
        check("  and on the key itself",
              stub.replied[-1][0] if stub.replied else None, serial)


def test_a_key_that_takes_nothing_is_reported():
    stub = Stub(menu=["Open", "Add", "Refill from stock"])
    m = load(stub)
    m["pack_count"] = lambda: 5
    call("it says so", m["store_haul"], False)
    check("out loud", any("took nothing" in x for x in stub.messages), True)


def test_the_lap_is_bounded():
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    check("runes per lap are capped", "MAX_RUNES_PER_LAP" in src, True)
    check("and the long wait is sliced, not one dead pause",
          "def sleep_ms(" in src and "SLEEP_SLICE_MS" in src, True)


def main():
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-54s got=%-22s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:22], repr(want)[:26]))
        if not ok:
            failed += 1
    print("")
    print("%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
