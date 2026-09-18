"""Offline tests for Scripts/Sandmaker.py.

    python tests/test_sandmaker.py

Loads the real script with the trailing main() call stripped and stub Razor
globals injected, then calls the actual functions - no copied logic to drift.

Carries the three things that made the RECORDED macro disconnect the client,
because a rewrite that quietly reintroduces any of them is the failure this
script exists to avoid:

  * a second press sent to a gump the first press already closed
  * replayed movement with no delay
  * a button pressed without checking the server drew it
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "Sandmaker.py")

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


class _Stub(object):
    def __getattr__(self, name):
        return lambda *a, **k: None


def load():
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    env = {"__name__": "sandmaker_under_test",
           "Misc": _Stub(), "Player": _Stub(), "Items": _Stub(),
           "Gumps": _Stub(), "PathFinding": _Stub(), "Target": _Stub()}
    exec(compile(source, SCRIPT, "exec"), env)
    return env


# The live dump of the Stone Storage, 2026-09-18.
STONE_STRINGS = ["Stone Storage", "Plain", "59999", "Dull", "0", "Shadow", "0",
                 "Copper", "0", "Bronze", "0", "Gold", "0", "Agapite", "0",
                 "Verite", "0", "Valorite", "0", "Mythril", "0",
                 "Withdrawal Amount:", "1", "Add", "Maximum Storage:",
                 "999999", "Fill from backpack"]


def test_the_withdrawal_amount_is_read_off_the_window(m):
    """From the live dump:

        21  Withdrawal Amount:
        22  1

    Read positionally, not through the text entry's InitialTextID: Razor drops
    empty strings out of the table without leaving a gap, so every id past the
    first blank is off by one.
    """
    check("it reads 1", m["label_after"](STONE_STRINGS, "Withdrawal Amount"),
          "1")

    other = list(STONE_STRINGS)
    other[22] = "50"
    check("and 50 when it is 50", m["label_after"](other, "Withdrawal Amount"),
          "50")

    check("a window without the label gives nothing",
          m["label_after"](["Stone Storage", "Plain"], "Withdrawal Amount"), "")
    check("nor does a label with nothing after it",
          m["label_after"](["Withdrawal Amount:"], "Withdrawal Amount"), "")

    # The label is matched loosely, the value is not guessed.
    check("the colon is not required",
          m["label_after"](["withdrawal amount", "7"], "Withdrawal Amount"),
          "7")


def test_the_converter_takes_one_at_a_time(m):
    check("one stone per press", m["WITHDRAW_AMOUNT"], 1)


def test_the_button_must_be_drawn_before_it_is_pressed(m):
    """Pressing one the server did not draw disconnects you. The Stone Storage
    lists TEN granite types, so the wrong row is a real possibility too."""
    layout = ("{ page 0 }"
              "{ button 250 150 4005 4007 1 0 21 }"
              "{ button 250 180 4005 4007 1 0 27 }"
              "{ textentry 152 118 60 20 0 0 2 }"
              "{ croppedtext 45 150 180 20 0 3 }")
    saved = m["raw_layout"]
    try:
        m["raw_layout"] = lambda gid: layout
        drawn = m["drawn_buttons"](0x6ABCE12)
        check("both buttons found", sorted(drawn), [21, 27])
        check("the text entry is not one", 2 in drawn, False)
        check("nor the text cell", 3 in drawn, False)

        m["raw_layout"] = lambda gid: ""
        check("an unreadable layout claims nothing is drawn",
              m["drawn_buttons"](0x6ABCE12), set())
    finally:
        m["raw_layout"] = saved

    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def withdraw_one("):src.index("def find_sand(")]
    # Reported, never raised - a change that removes the guard must show as a
    # failed check, not as a traceback that hides every check after it.
    guarded = "drawn_buttons(" in body
    check("the press is guarded by what was drawn", guarded, True)
    check("and the guard comes BEFORE the press",
          guarded and body.index("drawn_buttons(")
          < body.index("SendAdvancedAction"), True)
    check("and the guard actually refuses",
          "WITHDRAW_BUTTON not in drawn" in body, True)


def test_it_refuses_to_run_without_the_button(m):
    """Never guess a button id in a consequential gump. The default is 0 and
    the script stops rather than pressing something."""
    check("it ships unset", m["WITHDRAW_BUTTON"], 0)
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    pre = src[src.index("def preflight("):src.index("def main(")]
    check("preflight checks it", "if not WITHDRAW_BUTTON:" in pre, True)
    check("and stops", "return False" in pre, True)
    check("naming the diagnostic that finds it",
          "diag_storage_gump.py" in pre, True)


def test_only_one_press_goes_to_that_window(m):
    """THE DISCONNECT. A gump response closes the gump, so the recorded
    macro's second press - SendAction(0x6abce12, 1) - was answering a window
    the client no longer had."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def withdraw_one("):src.index("def find_sand(")]
    presses = body.count("Gumps.SendAdvancedAction") + body.count(
        "Gumps.SendAction")
    check("exactly one press per withdrawal", presses, 1)
    check("and it says why there is only one",
          "no longer has" in body or "NOTHING is pressed" in body, True)


def test_the_stone_moves_once(m):
    """The recording dragged twice because the first was out of range. The fix
    is the walk, not a second drag."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def one_round("):src.index("def preflight(")]
    check("one drag for the granite",
          body.count('move_one(granite'), 1)
    check("after walking to the box",
          body.index("walk_to_item(box") < body.index("move_one(granite"),
          True)
    check("and one for the sand", body.count("move_one(sand"), 1)
    check("after walking to it",
          body.index("walk_to_item(sand") < body.index("move_one(sand"), True)


def test_nothing_replays_keystrokes(m):
    """Four Player.Run/Walk calls with no delay is the other way that macro
    could have been dropped. Walking goes through PathFinding."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    code = src[src.index("# HELPERS"):]
    check("no Player.Run", "Player.Run(" in code, False)
    check("no Player.Walk", "Player.Walk(" in code, False)
    check("PathFinding instead", "PathFinding.Go(" in code, True)

    walk = src[src.index("def walk_to("):src.index("def walk_to_item(")]
    check("the walk is bounded by a clock", "deadline" in walk, True)
    check("and pauses between attempts", "Misc.Pause" in walk, True)


def test_every_drag_waits_out_the_rate_limit(m):
    check("the drag pause is at least the shard's limit",
          m["MOVE_PAUSE_MS"] >= 900, True)
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def move_one("):src.index("def open_storage(")]
    check("the move pauses", "Misc.Pause(MOVE_PAUSE_MS)" in body, True)
    check("and is verified by result rather than assumed",
          "Items.FindBySerial(serial)" in body, True)


def test_no_item_serial_from_the_recording_is_reused(m):
    """0x40BB6349 was that one withdrawal's granite and 0x40BB64E1 that one
    piece of sand. Both are new items every run. Only CONTAINERS are stable."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    code = src[src.index("# CONFIG"):]
    for dead in ("0x40BB6349", "0x40BB64E1"):
        check("%s is not used as config" % dead,
              re.search(r"=\s*%s" % dead, code, re.I) is not None, False)
    check("the granite is found by graphic", m["GRANITE_ID"], 0x1779)
    check("and Plain is hue 0", m["GRANITE_HUE"], 0x0000)


def test_the_sand_is_found_without_knowing_its_graphic(m):
    """SAND_ID is unknown and that costs nothing: the sand is whatever is on
    the ground after the drop that was not on it before."""
    check("it ships unknown", m["SAND_ID"], 0)

    class Item(object):
        def __init__(self, serial, name, item_id):
            self.Serial = serial
            self.Name = name
            self.ItemID = item_id

    table = {1: Item(1, "sand", 0x11EA),
             2: Item(2, "a pile of rocks", 0x1363),
             3: Item(3, "", 0x11EA)}
    saved = m["Items"]
    try:
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(lambda s: table.get(s)),
            "WaitForProps": staticmethod(lambda *a: None),
            "GetPropStringList": staticmethod(lambda *a: [])})()

        check("by name, among several", m["find_sand"]([1, 2]).Serial, 1)
        check("name wins over order", m["find_sand"]([2, 1]).Serial, 1)

        # One new thing and nothing else IS the sand, whatever it is called.
        check("a single unnamed new item is taken",
              m["find_sand"]([3]).Serial, 3)
        # Several new things, none named sand: refuse rather than guess.
        check("several unnamed ones are refused",
              m["find_sand"]([2, 3]), None)
        check("and nothing new is nothing", m["find_sand"]([]), None)
    finally:
        m["Items"] = saved


def test_the_learned_graphic_is_reported(m):
    """So SAND_ID can be filled in, the same way every other unknown in this
    repo has been."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def one_round("):src.index("def preflight(")]
    check("the graphic is printed", "sand.ItemID" in body, True)
    check("with the line to paste", "set SAND_ID" in body, True)


def main():
    module = load()
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-52s got=%-22s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:22], repr(want)[:26]))
        if not ok:
            failed += 1
    print("")
    print("%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
