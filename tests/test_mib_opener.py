"""Offline tests for Scripts/MIBOpener.py.

    python tests/test_mib_opener.py

Execs the real script with stub Razor globals and calls the real functions,
so there is no copied logic to drift.

What this script replaces was two lines in a loop that never stopped, so the
checks that matter are: does it STOP, does it stop for the right reason, and
does it find a bottle that is sitting inside a bag.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "MIBOpener.py")

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


class Item(object):
    def __init__(self, serial, item_id, hue=0, amount=1, contains=None,
                 container=False, name=""):
        self.Serial = serial
        self.ItemID = item_id
        self.Hue = hue
        self.Amount = amount
        self.Contains = list(contains or [])
        self.IsContainer = container or bool(contains)
        self.Name = name


class Entry(object):
    def __init__(self, text):
        self.Entry = text


class World(object):
    """The pack, the stubs, and what the script did to them."""

    def __init__(self, pack, menu=("Open", "Add", "Refill from stock"),
                 produces_sos=True, key_takes=True):
        self.pack = pack
        self.menu = list(menu)
        self.produces_sos = produces_sos
        self.key_takes = key_takes
        self._next_sos = 0x4F050000
        self.opened = []        # containers re-opened
        self.used = []          # bottles used
        self.replied = []       # context menu answers
        self.messages = []

    # --- Items -------------------------------------------------------------
    def UseItem(self, item):
        serial = int(item.Serial)
        if getattr(item, "IsContainer", False):
            self.opened.append(serial)
            return
        self.used.append(serial)
        self._consume(serial)
        if self.produces_sos:
            # CONFIRMED IN GAME: the bottle turns into "a waterstained SOS",
            # ItemID 0x14EE, in the backpack.
            self._next_sos += 1
            self.pack.Contains.append(
                Item(self._next_sos, 0x14EE, name="a waterstained SOS"))

    def _consume(self, serial):
        """A bottle that opens leaves the pack."""
        def strip(container):
            for it in list(container.Contains):
                if int(it.Serial) == serial:
                    if it.Amount > 1:
                        it.Amount -= 1
                    else:
                        container.Contains.remove(it)
                    return True
                if strip(it):
                    return True
            return False
        strip(self.pack)

    def WaitForContents(self, item, delay):
        return True

    def FindBySerial(self, serial):
        def hunt(container):
            for it in container.Contains:
                if int(it.Serial) == int(serial):
                    return it
                found = hunt(it)
                if found is not None:
                    return found
            return None
        if int(serial) == int(self.pack.Serial):
            return self.pack
        return hunt(self.pack)

    # --- Misc --------------------------------------------------------------
    def SendMessage(self, msg, hue=0, wait=False):
        self.messages.append(msg)

    def Pause(self, ms):
        pass

    def WaitForContext(self, item, delay, show=False):
        return [Entry(t) for t in self.menu]

    def ContextReply(self, item, label):
        self.replied.append(label)
        if not self.key_takes:
            return
        # A storage key that works empties the SOS out of the pack.
        def strip(container):
            for it in list(container.Contains):
                if int(getattr(it, "ItemID", 0)) == 0x14EE:
                    container.Contains.remove(it)
                else:
                    strip(it)
        strip(self.pack)

    def __getattr__(self, name):
        return lambda *a, **k: None


def load(world):
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    player = type("P", (), {"Backpack": world.pack})()
    env = {"__name__": "mib_under_test", "Misc": world, "Items": world,
           "Player": player, "Target": world, "Gumps": world}
    exec(compile(source, SCRIPT, "exec"), env)
    return env


def pack_with(*items):
    return Item(0x41D40F58, 0x0E75, contains=list(items), container=True)


def bottle(serial, amount=1):
    return Item(serial, 0x099F, 0x0000, amount, name="a message in a bottle")


# ---------------------------------------------------------------------------

def test_no_bag_is_ever_opened_by_default(m_world):
    """THE REPORTED BUG, 2026-10-12: it opened bags continuously.

    A container only reports what is in it just after it is opened, so
    searching bags meant RE-OPENING every bag on every count - and the count
    runs twice per bottle. The pack itself is still re-read, because that is
    where the bottles are and a stale snapshot hides them.
    """
    inner = Item(0x4000BBBB, 0x0E76, contains=[bottle(0x40000003)],
                 container=True)
    outer = Item(0x4000AAAA, 0x0E76, contains=[bottle(0x40000002), inner],
                 container=True)
    world = World(pack_with(bottle(0x40000001), outer))
    m = load(world)
    check("it ships off", m["SEARCH_BAGS"], False)

    total, found = m["find_bottles"]()
    check("only the loose one is counted", total, 1)
    check("and it is the one in the pack",
          [int(i.Serial) for i in found], [0x40000001])
    check("NO bag was opened - only the pack itself",
          sorted(set(world.opened)), [0x41D40F58])

    # A whole run must not open one either: the count happens over and over.
    del world.opened[:]
    m["main"]()
    check("not during a full run either", sorted(set(world.opened)),
          [0x41D40F58])


def test_search_bags_turns_the_deeper_search_back_on(m_world):
    """For whoever keeps their bottles in a bag and would rather have the
    churn."""
    inner = Item(0x4000BBBB, 0x0E76, contains=[bottle(0x40000003)],
                 container=True)
    outer = Item(0x4000AAAA, 0x0E76, contains=[bottle(0x40000002), inner],
                 container=True)
    world = World(pack_with(bottle(0x40000001), outer))
    m = load(world)
    m["SEARCH_BAGS"] = True

    total, found = m["find_bottles"]()
    check("all three found", total, 3)
    check("including the one two bags deep",
          sorted(int(i.Serial) for i in found),
          [0x40000001, 0x40000002, 0x40000003])
    check("and every bag was re-opened to read it",
          sorted(set(world.opened)),
          sorted([0x41D40F58, 0x4000AAAA, 0x4000BBBB]))

    m["MAX_BAG_DEPTH"] = 1
    check("the depth cap is honoured", m["find_bottles"]()[0], 2)


def test_a_stack_counts_as_its_amount(m_world):
    """One item holding three bottles is three bottles, and three is what has
    to come off the count before the run is finished."""
    world = World(pack_with(bottle(0x40000001, amount=3)))
    m = load(world)
    check("counted by amount", m["find_bottles"]()[0], 3)


def test_it_stops_when_there_are_none_left(m_world):
    """The whole point: the original ran forever."""
    world = World(pack_with(bottle(0x40000001), bottle(0x40000002),
                            bottle(0x40000003)))
    m = load(world)
    m["main"]()
    check("all three opened", len(world.used), 3)
    check("and it said so", any("No bottles left" in x
                                for x in world.messages), True)
    check("the pack really is empty of them", m["find_bottles"]()[0], 0)


def test_a_bottle_that_will_not_open_stops_the_run(m_world):
    """A use that changes nothing is the endless loop. Retried, then stopped -
    pressing again has already been proven not to work by then."""
    world = World(pack_with(bottle(0x40000001)))
    world._consume = lambda serial: None        # the server refuses, silently
    m = load(world)
    m["main"]()
    check("it tried RETRY_PASSES times, not forever",
          len(world.used), m["RETRY_PASSES"])
    check("and said why", any("would not open" in x for x in world.messages),
          True)


def test_nothing_to_do_is_said_and_nothing_is_pressed(m_world):
    world = World(pack_with(Item(0x40000009, 0x0EED, name="gold")))
    m = load(world)
    m["main"]()
    check("no bottle used", world.used, [])
    check("no key pressed", world.replied, [])
    check("and it said there was nothing", any("Nothing to open" in x
                                               for x in world.messages), True)


def test_the_catch_is_deposited_at_the_end(m_world):
    world = World(pack_with(bottle(0x40000001),
                            Item(0x40001111, 0x176B,
                                 0x0481, name="master key")))
    m = load(world)
    m["main"]()
    check("the key was pressed once", world.replied, ["Refill from stock"])


def test_the_key_menu_is_never_pressed_on_a_guess(m_world):
    """"Empty the key" sits on the same menu and does the opposite."""
    world = World(pack_with(bottle(0x40000001),
                            Item(0x40001111, 0x176B, 0x0481)),
                  menu=("Open", "Add", "Empty the key"))
    m = load(world)
    m["main"]()
    check("nothing was pressed", world.replied, [])
    check("the bottle was still opened", len(world.used), 1)
    check("and the menu is printed so the wording can be fixed",
          any("Empty the key" in x for x in world.messages), True)


def test_an_exact_entry_wins_over_an_earlier_loose_one(m_world):
    world = World(pack_with(Item(0x40001111, 0x176B, 0x0481)),
                  menu=("Refill from stockpile", "Refill from stock"))
    m = load(world)
    check("the exact one is chosen",
          m["pick_entry"](list(world.menu)), "Refill from stock")
    # A label that really DOES match loosely and is still refused. The old
    # check used "Empty from stock", which never matched at all - so it passed
    # whether the blocklist worked or not.
    nasty = "Refill from stock and destroy the rest"
    check("the loose match would otherwise take it",
          m["FILL_ENTRIES"][0].lower() in nasty.lower(), True)
    check("but CONTEXT_NEVER refuses it", m["pick_entry"]([nasty]), None)
    check("and a clean loose match is still taken",
          m["pick_entry"](["Refill from stock pile"]), "Refill from stock pile")


def test_what_comes_out_is_counted_and_reported(m_world):
    """Confirmed in game 2026-10-12: the bottle is consumed and leaves "a
    waterstained SOS" (0x14EE) behind."""
    world = World(pack_with(bottle(0x40000001), bottle(0x40000002),
                            Item(0x40001111, 0x176B, 0x0481)))
    m = load(world)
    m["main"]()
    said = " ".join(world.messages)
    check("both opened", len(world.used), 2)
    check("and the yield is reported", "2 SOS on you" in said, True)
    check("the key took them", "every SOS went into storage" in said, True)


def test_an_sos_the_key_refuses_is_called_out(m_world):
    """The menu entry can be answered and store nothing. "The reply was sent"
    is not evidence that anything moved."""
    world = World(pack_with(bottle(0x40000001),
                            Item(0x40001111, 0x176B, 0x0481)),
                  key_takes=False)
    m = load(world)
    m["main"]()
    said = " ".join(world.messages)
    check("the key was pressed", world.replied, ["Refill from stock"])
    check("but it is NOT reported as stored",
          "every SOS went into storage" in said, False)
    check("it says how many are left", "1 SOS still in your pack" in said,
          True)


def test_sos_already_in_the_pack_are_not_counted_as_produced(m_world):
    """The run reports what IT produced, not what happened to be in there."""
    old_one = Item(0x40002222, 0x14EE, name="a waterstained SOS")
    world = World(pack_with(bottle(0x40000001), old_one,
                            Item(0x40001111, 0x176B, 0x0481)),
                  key_takes=False)
    m = load(world)
    check("two on hand before the run", m["sos_on_hand"](), 1)
    m["main"]()
    check("one bottle, one new SOS", "1 SOS on you" in " ".join(world.messages),
          True)


def test_an_ancient_sos_is_matched_by_name(m_world):
    """Its graphic has not been inspected, so the name has to carry it."""
    ancient = Item(0x40003333, 0x1234, name="an Ancient SOS")
    water = Item(0x40004444, 0x14EE, name="")      # name not loaded yet
    junk = Item(0x40005555, 0x0EED, name="gold coins")
    world = World(pack_with(ancient, water, junk))
    m = load(world)
    check("the ancient one, by name", m["is_sos"](ancient), True)
    check("the waterstained one, by graphic alone", m["is_sos"](water), True)
    check("and gold is neither", m["is_sos"](junk), False)
    check("counted together", m["sos_on_hand"](), 2)


def test_the_run_is_capped(m_world):
    """Every loop here gets a ceiling, however wrong the guards are."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def main("):]
    check("the loop is bounded by MAX_OPENS",
          "while opened < MAX_OPENS:" in body, True)
    check("and it is not a while True", "while True" in body, False)


def test_it_deposits_part_way_through_a_long_run(m_world):
    world = World(pack_with(*([bottle(0x40000100 + i) for i in range(5)]
                              + [Item(0x40001111, 0x176B, 0x0481)])))
    m = load(world)
    m["DEPOSIT_EVERY"] = 2
    m["main"]()
    # 5 bottles: deposits after 2 and 4, then once at the end.
    check("it stored part way through, not only at the end",
          len(world.replied), 3)


def main():
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(None)

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
