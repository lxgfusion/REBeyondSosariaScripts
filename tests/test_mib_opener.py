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

    def __init__(self, pack, menu=("Open", "Add", "Refill from stock")):
        self.pack = pack
        self.menu = list(menu)
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

def test_a_bottle_inside_a_bag_is_found(m_world):
    """UseItemByID searches the pack's TOP LEVEL only, so a bottle in a bag was
    never opened by the one-liner this replaces."""
    inner = Item(0x4000BBBB, 0x0E76, contains=[bottle(0x40000003)],
                 container=True)
    outer = Item(0x4000AAAA, 0x0E76, contains=[bottle(0x40000002), inner],
                 container=True)
    world = World(pack_with(bottle(0x40000001), outer))
    m = load(world)

    total, found = m["find_bottles"]()
    check("all three found, two of them in bags", total, 3)
    check("including the one two bags deep",
          sorted(int(i.Serial) for i in found),
          [0x40000001, 0x40000002, 0x40000003])
    check("and every bag was RE-OPENED to read it",
          sorted(set(world.opened)),
          sorted([0x41D40F58, 0x4000AAAA, 0x4000BBBB]))

    # Depth is capped, and the cap is honoured.
    m["MAX_BAG_DEPTH"] = 1
    total, _ = m["find_bottles"]()
    check("a depth cap of 1 leaves the deepest one alone", total, 2)


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
