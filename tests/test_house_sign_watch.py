"""
Offline tests for HouseSignWatch.py.
===================================

Run with CPython 3 from the repo root:

    python tests/test_house_sign_watch.py

Same approach as the other script tests: the real script is exec'd with the
trailing main() stripped and stub Razor globals injected.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "HouseSignWatch.py")

FAILURES = []


def check(label, got, want):
    if got != want:
        FAILURES.append("%s: got %r, want %r" % (label, got, want))


class Point(object):
    def __init__(self, x, y):
        self.X = x
        self.Y = y


class Sign(object):
    def __init__(self, serial, props, x=110, y=95, name="a house sign",
                 item_id=0xBD2):
        self.Serial = serial
        self.Name = name
        self.ItemID = item_id
        self.Position = Point(x, y)
        self._props = props


class StubMisc(object):
    def __init__(self):
        self.messages = []
        self.beeps = 0

    def SendMessage(self, text, *args):
        self.messages.append(text)

    def Pause(self, ms):
        pass

    def Beep(self):
        self.beeps += 1

    def CurrentScriptDirectory(self):
        return ""


class StubItems(object):
    def __init__(self):
        self.signs = []
        self.overhead = []
        self.clicked = []
        self.click_says = {}
        self.journal = None

    def WaitForProps(self, item, ms):
        pass

    def GetPropStringList(self, item):
        return list(item._props)

    def Message(self, item, hue, text):
        self.overhead.append((item.Serial, text))

    def SingleClick(self, item):
        self.clicked.append(item.Serial)
        said = self.click_says.get(item.Serial)
        if said and self.journal is not None:
            self.journal.add(said, item.Serial)

    def ApplyFilter(self, f):
        return list(self.signs)

    def Filter(self):
        class NetList(list):            # Razor's List[Int32] has .Add()
            def Add(self, value):
                self.append(value)

        class F(object):
            def __init__(self):
                self.Graphics = NetList()
        return F()


class StubJournal(object):
    def __init__(self):
        self.entries = []
        self.clock = 50.0

    def add(self, text, serial=0):
        self.clock += 1.0

        class E(object):
            pass
        e = E()
        e.Text = text
        e.Serial = serial
        e.Timestamp = self.clock
        self.entries.append(e)

    def GetJournalEntry(self, after):
        return [e for e in self.entries if e.Timestamp > after]


class StubPlayer(object):
    Position = Point(100, 100)
    Map = 1
    IsGhost = False

    @staticmethod
    def DistanceTo(item):
        return max(abs(item.Position.X - 100), abs(item.Position.Y - 100))


def load_script():
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    journal = StubJournal()
    items = StubItems()
    items.journal = journal
    env = {
        "__name__": "house_sign_watch_under_test",
        "Misc": StubMisc(),
        "Items": items,
        "Journal": journal,
        "Player": StubPlayer(),
    }
    exec(compile(source, SCRIPT, "exec"), env)
    env["ALERT_LOG_FILE"] = ""          # no files from tests
    return env


def fresh(m):
    m["_seen"].clear()
    m["Misc"].messages = []
    m["Misc"].beeps = 0
    m["Items"].overhead = []
    m["Items"].clicked = []


# --------------------------------------------------------------------------

def test_conditions_from_the_tooltip(m):
    c = m["condition_of"]
    t = m["tidy"]
    check("slightly", c(t("Condition: This structure is slightly worn.")),
          ("Slightly Worn", 0))
    check("greatly", c(t("Condition: This structure is greatly worn.")),
          ("Greatly Worn", 1))
    check("collapsing",
          c(t("Condition: This structure is in danger of collapsing.")),
          ("In Danger Of Collapse", 2))
    check("unresolved cliloc argument",
          c(t("Condition: This structure is #1043015")),
          ("In Danger Of Collapse", 2))
    for fine in ("like new", "somewhat worn", "fairly worn", "ageless"):
        check("%s does not alert" % fine,
              c(t("Condition: This structure is %s." % fine)), None)
    check("demolition pending is off by default",
          c(t("Demolition Pending")), None)


def test_run_together_tooltip(m):
    """Properties can arrive concatenated: "Owner: BobCondition: ..."."""
    t = m["tidy"]("Name: Bob's PlaceOwner: BobCondition: This structure is "
                  "greatly worn.")
    check("still found", m["condition_of"](t), ("Greatly Worn", 1))


def test_shop_signs_are_not_houses(m):
    shop = Sign(1, ["Provisioner"], name="a sign")
    check("shop sign rejected", m["read_sign"](shop), None)
    house = Sign(2, ["A House Sign", "Name: Seaside Villa", "Owner: Bob",
                     "This is a Private Home",
                     "Condition: This structure is slightly worn."])
    info = m["read_sign"](house)
    check("house read", info and info["condition"], "Slightly Worn")
    check("name", info and info["name"], "seaside villa")
    check("owner", info and info["owner"], "bob")


def test_sign_graphics(m):
    g = m["SIGN_GRAPHICS"]
    check("default brass sign 0xBD2", 0xBD2 in g, True)
    check("first standard sign 2980", 2980 in g, True)
    check("last standard sign 3086", 3086 in g, True)
    check("library sign 2966", 2966 in g, True)
    check("beekeeper sign 3140", 3140 in g, True)


def test_single_click_fallback(m):
    """No Condition line in the tooltip: the overhead label is read from the
    journal by timestamp."""
    fresh(m)
    sign = Sign(3, ["A House Sign", "Name: Old Shack", "Owner: Ann"])
    m["Items"].click_says[3] = "This house is in danger of collapsing."
    info = m["read_sign"](sign)
    check("clicked", m["Items"].clicked, [3])
    check("label read", info and info["condition"], "In Danger Of Collapse")


def test_alert_once_then_only_when_worse(m):
    fresh(m)
    sign = Sign(4, ["A House Sign", "Name: Hut", "Owner: Cy",
                    "Condition: This structure is slightly worn."])
    m["Items"].signs = [sign]
    check("first scan alerts", m["scan_once"](), 1)
    check("beeped", m["Misc"].beeps, 1)
    check("marker over the sign", m["Items"].overhead, [(4, "Slightly Worn")])
    check("the alert names the house and where it is",
          any("SLIGHTLY WORN" in t and "hut" in t and "110,95" in t
              and "NE" in t for t in m["Misc"].messages), True)

    check("next scan: not due, silent", m["scan_once"](), 0)

    m["_seen"][4]["read_at"] = 0          # due again, same condition
    check("same condition again: silent", m["scan_once"](), 0)

    sign._props[-1] = "Condition: This structure is greatly worn."
    m["_seen"][4]["read_at"] = 0
    check("worse: alerts again", m["scan_once"](), 1)


def test_fine_houses_are_quiet(m):
    fresh(m)
    m["Items"].signs = [Sign(5, ["A House Sign", "Name: Manor", "Owner: Di",
                                 "Condition: This structure is like new."])]
    check("no alert", m["scan_once"](), 0)
    check("no beep", m["Misc"].beeps, 0)


def test_compass(m):
    c = m["compass"]
    check("north-east", c(5, -3), "NE")
    check("south", c(0, 4), "S")
    check("west", c(-2, 0), "W")


def main():
    m = load_script()
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn(m)
        except Exception as err:
            FAILURES.append("%s raised %r" % (name, err))
    if FAILURES:
        print("FAILED (%d):" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        return 1
    print("OK - %d tests" % len(tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
