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


def run(label, fn, *args):
    """Call something for its side effects; a raise is a FAILED CHECK.

    The suite is a flat script, so one traceback hides every check after it -
    the failure mode CLAUDE.md names.
    """
    try:
        fn(*args)
    except Exception as err:
        check(label, "raised %s: %s" % (type(err).__name__, err), "no error")


def strip_comments(src):
    """Source with docstrings and comments removed.

    Needed because this script QUOTES the old buggy lines to explain them, so
    a search for them in the raw text finds the explanation.
    """
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    return "\n".join(l.split("#", 1)[0] for l in code.splitlines())


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

def test_the_title_is_read_from_the_tooltip_and_has_no_article():
    """Inspected 2026-10-24, from two real vendors:

        Name: Arlinda   tooltip: Arlinda / Alchemist
        Name: Shanata   tooltip: Shanata / Mage

    The title is "Alchemist", not "the alchemist" - the first version looked
    for the article and so saw no vendors anywhere. And it is a TITLE, which
    lives in the tooltip; Mobiles.Filter().Name is an exact match against the
    NAME and never sees it.
    """
    arlinda = Mob(0x000A8FC0, "Arlinda", props=["Arlinda", "Alchemist"])
    shanata = Mob(0x000AA189, "Shanata", props=["Shanata", "Mage"])
    smith = Mob(3, "Gorn", props=["Gorn", "Blacksmith"])
    stub = Stub(mobiles=[arlinda, shanata, smith])
    m = load(stub)

    check("the alchemist", m["is_vendor"](arlinda), True)
    check("the mage", m["is_vendor"](shanata), True)
    check("not the blacksmith", m["is_vendor"](smith), False)
    check("both are returned",
          [int(x.Serial) for x in m["vendors_in_range"]()],
          [0x000A8FC0, 0x000AA189])


def test_a_concatenated_tooltip_still_matches():
    """Tooltip properties arrive run together - "ArlindaAlchemist" - and there
    is no word boundary between "a" and "A", so a whole-word match finds
    nothing on exactly the line that carries the title."""
    squashed = Mob(1, "", props=["ArlindaAlchemist"])
    stub = Stub(mobiles=[squashed])
    m = load(stub)
    check("the seam is opened up first", m["is_vendor"](squashed), True)


def test_the_title_is_matched_as_whole_words():
    """"Mage" must not claim "Magery" or a "Mageblade" somebody is carrying."""
    stub = Stub()
    m = load(stub)
    check("Magery is not Mage",
          m["is_vendor"](Mob(1, "Kell", props=["Kell", "Magery Trainer"])),
          False)
    check("nor is a Mageblade",
          m["is_vendor"](Mob(2, "Kell", props=["Kell", "Mageblade"])), False)
    check("but the bare title is", m["is_vendor"](Mob(3, "Zoe",
                                                     props=["Mage"])), True)


def test_a_guildmaster_is_refused():
    """Their menu charges for training rather than selling reagents."""
    boss = Mob(4, "Lysander", props=["Lysander", "Mage Guildmaster"])
    stub = Stub(mobiles=[boss])
    m = load(stub)
    check("refused even though the title matches", m["is_vendor"](boss), False)
    check("and so never approached", m["vendors_in_range"](), [])


def test_the_range_is_always_set():
    """An unset RangeMax means everything the client knows about - 18-25 tiles
    of other people's vendors. See CLAUDE.md."""
    stub = Stub(mobiles=[Mob(1, "Zoe", props=["Mage"])])
    m = load(stub)
    m["vendors_in_range"]()
    check("RangeMax was set on the filter", stub.last_range, m["VENDOR_RANGE"])


def test_a_vendor_named_outright_still_matches():
    """A shard that puts the title in the NAME works too - the name and the
    tooltip are read as one string."""
    plain = Mob(5, "Zoe the Mage", props=[])
    stub = Stub(mobiles=[plain])
    m = load(stub)
    check("matched on the name", m["is_vendor"](plain), True)


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
    mage = Mob(1, "Zoe", props=["Mage"])
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

class FakeClock(object):
    """A clock the test moves by hand, so 45 minutes costs nothing."""

    def __init__(self):
        self.now = 1000000.0

    def time(self):
        return self.now

    def advance_minutes(self, minutes):
        self.now += minutes * 60.0


def lap_world(rune_list, invader_at=None, menu=("Buy", "Refill from stock")):
    """A round of `rune_list`, with an invader standing at one of them."""
    stub = Stub(menu=list(menu))
    m = load(stub)
    clock = FakeClock()
    m["time"] = clock
    visited = []

    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: list(rune_list)
    m["recall_to"] = lambda page, button, name, coord: (
        visited.append(name) or True)
    m["emergency_escape"] = lambda: True
    m["store_haul"] = lambda: True
    m["vendors_in_range"] = lambda: []
    m["danger_here"] = lambda: ("Grak" if invader_at
                                and visited and invader_at in visited[-1]
                                else "")
    return m, stub, clock, visited


RUNES = [
    (1, 10, "Britt Mage Shop (Tramm...", [100, 100, 0]),
    (1, 11, "Vesper Mage Shop (Tra...", [200, 200, 0]),
    (1, 12, "Trinsic Mage Shop (Tram...", [300, 300, 0]),
    (2, 13, "Vesper Mage Shop (Tra...", [200, 201, 0]),
]


def test_a_rune_is_tied_to_its_town_through_the_runebook_spelling():
    """The runebook writes "Britt Mage Shop"; the town is Britain. Both have
    to mean the same place or the hold is applied to the wrong runes."""
    m = load(Stub())
    check("Britt is Britain", m["town_of"]("Britt Mage Shop (Tramm..."),
          "Britain")
    check("Vesper is Vesper", m["town_of"]("Vesper Mage Shop (Tra..."),
          "Vesper")
    check("Skara Brae is matched whole",
          m["town_of"]("Skara Brae Mage Shop ..."), "Skara Brae")
    check("and in_town agrees",
          m["in_town"]("Britt Mage Shop", "Britain"), True)
    check("without mixing towns up",
          m["in_town"]("Vesper Mage Shop", "Britain"), False)

    # A rune in no known town is held BY NAME - narrower than guessing which
    # other runes might share its town.
    check("an unknown place falls back to the rune itself",
          m["town_of"]("Moonshine Hollow Mage Shop"),
          "Moonshine Hollow Mage Shop")


def test_seeing_an_invader_holds_the_whole_town_not_just_that_shop():
    """The folder holds TWO Vesper runes. Walking into the second after
    escaping the first is walking back into the invasion."""
    m, stub, clock, visited = lap_world(RUNES, invader_at="Vesper")
    run("lap 1", m["one_lap"], 1)
    check("it tried all four", len(visited), 4)
    check("and wrote Vesper off",
          any("Vesper is off the round for 45 minutes" in x
              for x in stub.messages), True)

    # Next lap: BOTH Vesper runes are skipped, the other two are not.
    del visited[:]
    del stub.messages[:]
    clock.advance_minutes(10)
    run("lap 2", m["one_lap"], 2)
    check("neither Vesper rune was visited",
          [v for v in visited if "Vesper" in v], [])
    check("the other two still were", len(visited), 2)
    check("and it said how long is left",
          any("Vesper (35m)" in x for x in stub.messages), True)


def test_the_hold_expires_after_forty_five_minutes():
    m, stub, clock, visited = lap_world(RUNES, invader_at="Vesper")
    check("the hold is 45 minutes", m["INVADER_AVOID_MS"], 45 * 60 * 1000)
    run("lap 1", m["one_lap"], 1)

    clock.advance_minutes(44)
    del visited[:]
    run("lap at 44 minutes", m["one_lap"], 2)
    check("still held at 44 minutes",
          [v for v in visited if "Vesper" in v], [])

    clock.advance_minutes(2)
    del visited[:]
    m["danger_here"] = lambda: ""        # the invasion is over
    run("lap at 46 minutes", m["one_lap"], 3)
    check("visited again at 46 minutes",
          len([v for v in visited if "Vesper" in v]), 2)


def test_a_held_town_does_not_stop_the_rest_of_the_round():
    m, stub, clock, visited = lap_world(RUNES, invader_at="Vesper")
    run("lap 1", m["one_lap"], 1)
    del visited[:]
    run("lap 2", m["one_lap"], 2)
    check("Britain and Trinsic are still shopped",
          sorted(set(m["town_of"](v) for v in visited)),
          ["Britain", "Trinsic"])


def test_every_rune_held_ends_the_lap_quietly():
    one_town = [(1, 10, "Vesper Mage Shop (Tra...", [200, 200, 0])]
    m, stub, clock, visited = lap_world(one_town, invader_at="Vesper")
    run("lap 1", m["one_lap"], 1)
    del visited[:]
    del stub.messages[:]
    run("lap 2", m["one_lap"], 2)
    check("nothing was visited", visited, [])
    check("and it said why",
          any("Every shop is still held" in x for x in stub.messages), True)


def test_nothing_reads_the_events_window_any_more():
    """Scrapped 2026-10-24: it did not read reliably. The escape plus a hold
    on the area replaces it."""
    src = open(SCRIPT, encoding="utf-8").read()
    for gone in ("[events", "EVENTS_GUMPID", "invaded_towns", "strip_tags"):
        check("no %s" % gone, gone in src, False)


def test_a_town_invader_means_leave():
    """Asked 2026-10-24: a shop with one in it is abandoned at once and the
    next rune recalled to."""
    invader = Mob(9, "Grak", props=["Grak", "Town Invader"])
    mage = Mob(1, "Shanata", props=["Shanata", "Mage"])
    stub = Stub(mobiles=[invader, mage])
    m = load(stub)
    check("it is spotted by title", m["danger_here"](), "Grak")
    check("an invader is not mistaken for a vendor", m["is_vendor"](invader),
          False)

    quiet = Stub(mobiles=[mage])
    m2 = load(quiet)
    check("and a quiet shop reports nothing", m2["danger_here"](), "")

    # The whole-word rule applies here too.
    odd = Stub(mobiles=[Mob(9, "Grak", props=["Grak", "Towns Invaders"])])
    m3 = load(odd)
    check("a near-miss title is not a panic", m3["danger_here"](), "")


def test_nothing_is_bought_where_an_invader_stands():
    """The bail-out has to come BEFORE the shopping, not after it."""
    invader = Mob(9, "Grak", props=["Grak", "Town Invader"])
    mage = Mob(1, "Shanata", props=["Shanata", "Mage"])
    stub = Stub(menu=["Buy", "Sell"], mobiles=[invader, mage])
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britt Mage Shop", [100, 100, 0])]
    m["recall_to"] = lambda *a: True
    call("the lap spends nothing", m["one_lap"], 0, 1)
    check("and nobody was asked to trade", stub.replied, [])
    check("it said why", any("getting out of" in x for x in stub.messages),
          True)
    check("and it escaped rather than picking its way to the next rune",
          any("ESCAPE" in x for x in stub.messages), True)


def test_the_wait_happens_at_the_bank_not_in_a_shop():
    """A shop is where the invaders turn up, so the ten minutes are spent
    somewhere else."""
    check_src = open(SCRIPT, encoding="utf-8").read()
    body = check_src[check_src.index("def main("):]
    went = "go_home_and_wait()" in body
    check("it goes home", went, True)
    check("before the wait, not after",
          went and "sleep_ms(CYCLE_PAUSE_MS)" in body
          and body.index("go_home_and_wait()")
          < body.index("sleep_ms(CYCLE_PAUSE_MS)"), True)

    stub = Stub()
    m = load(stub)
    check("ten minutes", m["CYCLE_PAUSE_MS"], 600000)
    check("in Trammel", m["HOME_FOLDER"], ["Trammel"])
    check("at the bank",
          all("bank" in w.lower() for w in m["HOME_RUNE"]), True)
    check("and the spellings are a priority list, not one guess",
          len(m["HOME_RUNE"]) > 1, True)


def test_the_home_rune_lists_what_is_there_when_it_cannot_be_found():
    """A name that does not match is fixed from the journal rather than
    another round trip - the folder's runes are printed."""
    lines = ["<CENTER>Account Runebook</CENTER>", "Trammel", "New Rune",
             "New Runebook", "Organize",
             "1. Britain Bank", "(1434, 1699, 0)",
             "2. Vesper Bank", "(2898, 676, 0)",
             "<CENTER>Page 1/1"]
    layout = ("{ button 545 90 4005 4007 1 0 10 }"
              "{ button 545 130 4005 4007 1 0 11 }")
    stub = Stub(lines=lines, layout=layout)
    m = load(stub)
    m["ar_enter_folder"] = lambda name: True
    m["HOME_RUNE"] = ["Nowhere At All"]
    call("it gives up", m["go_home_and_wait"], False)
    said = " ".join(stub.messages)
    check("and lists what the folder really holds",
          "Britain Bank" in said and "Vesper Bank" in said, True)

    # THE SPELLING IS A LIST, best first. "Brittain" is not "Britain" and
    # fuzzy-matching a name would risk recalling somewhere else entirely - so
    # the second spelling is what finds it.
    recalled = []
    m["recall_to"] = lambda *a: recalled.append(a[2]) or True
    m["HOME_RUNE"] = ["Brittain Bank", "Britain Bank", "Bank"]
    call("the next spelling finds it", m["go_home_and_wait"], True)
    check("and it recalled to the real rune", recalled, ["Britain Bank"])

    # THE CATCH-ALL MUST NOT WIN ON PAGE ORDER. Vesper is listed FIRST here,
    # so a loop that walks the runes and asks "does any wanted name match
    # this one?" recalls to the wrong bank. The names have to be tried in
    # THEIR order, each against the whole folder.
    vesper_first = ["<CENTER>Account Runebook</CENTER>", "Trammel", "New Rune",
                    "New Runebook", "Organize",
                    "1. Vesper Bank", "(2898, 676, 0)",
                    "2. Britain Bank", "(1434, 1699, 0)",
                    "<CENTER>Page 1/1"]
    stub2 = Stub(lines=vesper_first, layout=layout)
    m2 = load(stub2)
    m2["ar_enter_folder"] = lambda name: True
    picked = []
    m2["recall_to"] = lambda *a: picked.append(a[2]) or True
    m2["HOME_RUNE"] = ["Britain Bank", "Bank"]
    call("found", m2["go_home_and_wait"], True)
    check("the specific name beats the catch-all", picked, ["Britain Bank"])


# The page "[ar RO RO" opens on, inspected 2026-10-24.
ESCAPE_PAGE = [
    "<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>",
    "RO", "New Rune", "New Runebook", "Organize",
    "1. RO (Trammel)", "(1412, 1721, 20)",
    "2. Start Fill (Malas)", "(1281, 1193, -90)",
    "3. Deposit items (Malas)", "(1275, 1164, -83)",
    "4. Deposit PS (Malas)", "(1266, 1166, -83)",
    "<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/1",
]
# The entry buttons start at 14, NOT 10: this book numbers continuously
# across pages, and a hardcoded "press 10" would press a button that is not
# even drawn here. The real page's first entry happened to be 10, which made
# reading it and guessing it look identical.
ESCAPE_FIRST_BUTTON = 14
ESCAPE_LAYOUT = ("{ button 20 440 4014 4015 1 0 503 }"
                 "{ button 400 440 4005 4006 1 0 504 }"
                 + "".join(
                     "{ button 545 %d 4005 4007 1 0 %d }"
                     "{ button 575 %d 4011 4012 1 0 %d }"
                     "{ button 605 %d 4017 4018 1 0 %d }"
                     % (90 + i * 40, ESCAPE_FIRST_BUTTON + i,
                        90 + i * 40, 30000 + ESCAPE_FIRST_BUTTON + i,
                        90 + i * 40, 60000 + ESCAPE_FIRST_BUTTON + i)
                     for i in range(4)))


def escape_stub(**kw):
    """A world where the book is NOT already registered open.

    E1 needs that: with HasGump answering True, a stray openAR() returns at
    once without saying "[ar", so reopening-at-the-root was invisible.
    """
    stub = Stub(lines=ESCAPE_PAGE, layout=ESCAPE_LAYOUT, pos=(1412, 1721),
                **kw)
    stub.HasGump = lambda gump_id: False
    return stub


def test_the_escape_is_one_command_and_one_button():
    """Asked 2026-10-24: "[ar RO RO" opens the book already inside the RO
    folder, and the first entry on it is the way out. No paging through runes
    while something is hitting you."""
    stub = escape_stub()
    m = load(stub)
    check("the command is the one that opens the folder",
          m["ESCAPE_COMMAND"], "[ar RO RO")

    call("it gets out", m["emergency_escape"], True)
    check("it said the command once", stub.said, ["[ar RO RO"])
    check("and pressed the FIRST entry, nothing else", stub.actions,
          [ESCAPE_FIRST_BUTTON])
    check("which is NOT the lowest number a page can use",
          ESCAPE_FIRST_BUTTON != 10, True)
    check("naming where it went",
          any("RO (Trammel)" in x for x in stub.messages), True)


def test_the_escape_never_reopens_the_book_at_the_root():
    """Saying "[ar" again lands at the root and throws away the folder the
    escape command just opened - which would leave it pressing the first
    entry of the ROOT page instead."""
    stub = escape_stub()
    m = load(stub)
    run("the escape ran", m["emergency_escape"])
    check("only the escape command was said", stub.said, ["[ar RO RO"])
    check("the plain [ar was never sent",
          any(x.strip() == "[ar" for x in stub.said), False)


def test_the_escape_presses_no_page_or_delete_button():
    """Paging is what it exists to avoid, and the third button on every row
    deletes the rune."""
    stub = escape_stub()
    m = load(stub)
    run("the escape ran", m["emergency_escape"])
    check("no page buttons",
          [b for b in stub.actions if b in (503, 504)], [])
    check("no gate or delete buttons",
          [b for b in stub.actions if b >= 30000], [])


def test_the_escape_works_on_buttons_alone_if_the_text_is_late():
    """The names may not have arrived. The buttons are enough to leave on."""
    stub = escape_stub()
    stub.lines = []
    m = load(stub)
    call("it still goes", m["emergency_escape"], True)
    check("pressing the lowest entry button", stub.actions,
          [ESCAPE_FIRST_BUTTON])


def test_the_escape_says_so_when_the_book_will_not_open():
    stub = escape_stub()
    stub.lines, stub.layout = [], ""
    m = load(stub)
    call("it reports failure", m["emergency_escape"], False)
    check("nothing was pressed", stub.actions, [])
    check("out loud", any("did not open" in x for x in stub.messages), True)


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


def test_every_vendor_is_bought_from_before_the_key_is_pressed():
    """Asked 2026-10-24. The goods all land in the pack - infinite weight - so
    storing between vendors buys nothing and costs a context menu each."""
    sellers = [Mob(1, "Shanata", props=["Mage"]),
               Mob(2, "Arlinda", props=["Alchemist"]),
               Mob(3, "Kell", props=["Mage"])]
    stub = Stub(menu=["Buy", "Sell", "Refill from stock"], mobiles=sellers,
                gold=1000)
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britt Mage Shop", [100, 100, 0])]
    m["recall_to"] = lambda *a: True
    m["pack_count"] = lambda: 9 if len(stub.replied) < 4 else 2

    def spend(serial, label):
        stub.replied.append((int(serial), label))
        if label == "Buy":
            stub.Gold -= 100
    stub.ContextReply = spend

    run("the lap ran", m["one_lap"], 1)
    pressed = [label for _s, label in stub.replied]
    check("all three vendors were bought from", pressed.count("Buy"), 3)
    check("and the key was NOT touched during the round",
          "Refill from stock" in pressed, False)
    check("nothing but buying happened", pressed, ["Buy", "Buy", "Buy"])


def test_a_shop_that_sells_nothing_gets_no_key_press():
    """Pressing a key with nothing to put in it is a context menu and a pause
    for no reason."""
    stub = Stub(menu=["Buy", "Sell", "Refill from stock"],
                mobiles=[Mob(1, "Shanata", props=["Mage"])], gold=1000)
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britt Mage Shop", [100, 100, 0])]
    m["recall_to"] = lambda *a: True
    m["pack_count"] = lambda: 5
    # ContextReply records but never spends: the vendor stocks nothing wanted.
    run("the lap ran", m["one_lap"], 1)
    pressed = [label for _s, label in stub.replied]
    check("the vendor was asked", pressed.count("Buy"), 1)
    check("and the key was left alone",
          "Refill from stock" in pressed, False)


def test_the_pack_is_emptied_at_the_cooldown_stop_not_in_the_shops():
    """Asked 2026-10-24: one press per lap, at the bank, before the next run
    starts. The pack carries everything until then - infinite weight - and a
    shop abandoned to an invader keeps its goods the same way."""
    sellers = [Mob(1, "Shanata", props=["Mage"]),
               Mob(9, "Grak", props=["Town Invader"])]
    stub = Stub(menu=["Buy", "Sell", "Refill from stock"], mobiles=sellers,
                gold=1000)
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britt Mage Shop", [100, 100, 0])]
    m["recall_to"] = lambda *a: True
    m["pack_count"] = lambda: 5

    seen = {"n": 0}
    real_danger = m["danger_here"]

    def danger():
        seen["n"] += 1
        return "" if seen["n"] == 1 else real_danger()
    m["danger_here"] = danger

    def spend(serial, label):
        stub.replied.append((int(serial), label))
        if label == "Buy":
            stub.Gold -= 100
    stub.ContextReply = spend

    run("the lap ran", m["one_lap"], 1)
    pressed = [label for _s, label in stub.replied]
    check("it bought once then left", pressed.count("Buy"), 1)
    check("and stored nothing on the way", pressed, ["Buy"])

    # The press happens in main(), once, after the trip to the bank.
    src = open(SCRIPT, encoding="utf-8").read()
    body = src[src.index("def main("):]
    went = "go_home_and_wait()" in body and "store_haul()" in body
    check("main goes home then empties the pack", went, True)
    check("in that order",
          went and body.index("go_home_and_wait()")
          < body.index("store_haul()"), True)
    check("and before the wait, not after",
          went and "sleep_ms(CYCLE_PAUSE_MS)" in body
          and body.index("store_haul()")
          < body.index("sleep_ms(CYCLE_PAUSE_MS)"), True)
    check("the lap itself never presses the key",
          "store_haul()" in src[src.index("def one_lap("):src.index("def main(")],
          False)


def test_nothing_says_grab_any_more():
    """Infinite backpack weight: bought goods go straight to the pack and
    there is never anything on the floor to pick up."""
    src = open(SCRIPT, encoding="utf-8").read()
    code = strip_comments(src)
    check("no grab command in the code", "grab" in code.lower(), False)
    check("and no leftover helper", "grab_and_store" in src, False)


def test_an_invader_mid_round_leaves_without_stopping_to_key():
    """Standing still to answer a context menu is the last thing to do with
    one of those here - the next shop's key press takes the goods."""
    sellers = [Mob(1, "Shanata", props=["Mage"]),
               Mob(9, "Grak", props=["Town Invader"])]
    stub = Stub(menu=["Buy", "Sell", "Refill from stock"], mobiles=sellers,
                gold=1000)
    m = load(stub)
    m["go_to_reagent_folder"] = lambda: True
    m["collect_runes"] = lambda: [(1, 10, "Britt Mage Shop", [100, 100, 0])]
    m["recall_to"] = lambda *a: True
    m["pack_count"] = lambda: 5

    # Quiet on arrival; the invader walks in after the first purchase.
    seen = {"n": 0}
    real_danger = m["danger_here"]

    def danger():
        seen["n"] += 1
        return "" if seen["n"] == 1 else real_danger()
    m["danger_here"] = danger

    def spend(serial, label):
        stub.replied.append((int(serial), label))
        if label == "Buy":
            stub.Gold -= 100
    stub.ContextReply = spend

    run("the lap ran", m["one_lap"], 1)
    pressed = [label for _s, label in stub.replied]
    check("it bought once before leaving", pressed.count("Buy"), 1)
    check("and never stopped to answer a menu",
          "Refill from stock" in pressed, False)
    check("saying why", any("abandoning" in x for x in stub.messages), True)
    check("and it ESCAPED rather than walking to the next rune",
          any("ESCAPE" in x for x in stub.messages), True)
    # The hold is recorded on the MID-ROUND path too, not just on arrival.
    check("and the town was written off",
          any("off the round for 45 minutes" in x for x in stub.messages),
          True)


def test_the_deposit_waits_before_counting_the_pack_again():
    """IT SAID "the key took nothing" WHILE IT WAS WORKING (2026-10-24),
    because the pack was re-counted the instant the menu was answered - the
    server had not finished moving anything yet."""
    src = open(SCRIPT, encoding="utf-8").read()
    body = src[src.index("def store_haul("):src.index("# ======", src.index("def store_haul("))]
    waited = "Misc.Pause(STORE_SETTLE_MS)" in body
    check("it waits after the press", waited, True)
    check("before counting again",
          waited and body.index("Misc.Pause(STORE_SETTLE_MS)")
          < body.rindex("pack_count()"), True)

    # An unchanged count is REPORTED, not called a failure: there is often
    # nothing in the pack the key wants.
    stub = Stub(menu=["Open", "Add", "Refill from stock"])
    m = load(stub)
    m["pack_count"] = lambda: 5
    call("the press still counts as done", m["store_haul"], True)
    check("and it says what it saw",
          any("still shows 5 item(s)" in x for x in stub.messages), True)
    check("without crying failure",
          any("took nothing" in x for x in stub.messages), False)


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
