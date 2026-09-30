"""Offline tests for Scripts/Sandmaker.py.

    python tests/test_sandmaker.py

Loads the real script with the trailing main() call stripped and stub Razor
globals injected, then calls the actual functions - no copied logic to drift.

Carries the three things that made the RECORDED macro disconnect the client,
because a rewrite that quietly reintroduces any of them is the failure this
script exists to avoid:

  * a TEXT ENTRY sent to a window that draws none - the disconnect
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


def between(text, start, end):
    """The slice between two markers, or "" if either is missing.

    A slice that RAISES when a function was renamed or removed takes the whole
    suite down and hides every check after it - the failure mode CLAUDE.md
    names, and one this file has now hit twice.
    """
    if start not in text or end not in text:
        return ""
    return text[text.index(start):text.index(end)]


def call(label, fn, want, *args):
    """check() for a real call: an exception is a failure, not a traceback.

    A mutation that breaks the function under test would otherwise take the
    whole suite down with it and hide every check after this one.
    """
    try:
        got = fn(*args)
    except Exception as err:
        got = "raised %s: %s" % (type(err).__name__, err)
    check(label, got, want)


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


def test_it_has_a_version_banner(m):
    """Every script here prints one on its first log line. Razor caches the
    loaded script even after the file changes, and this repo has lost two
    debugging rounds to a fix that was on disk but not in the folder Razor
    reads."""
    check("there is a version", bool(m["SCRIPT_VERSION"]), True)
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    pre = src[src.index("def preflight("):src.index("def main(")]
    check("and preflight prints it", "SCRIPT_VERSION" in pre, True)


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
          and "Gumps.SendAction(" in body
          and body.index("drawn_buttons(")
          < body.index("Gumps.SendAction("), True)
    check("and the guard actually refuses",
          "button not in drawn" in body, True)


def test_a_buttontileart_id_is_its_seventh_number_not_its_last(m):
    """ServUO's two pressable elements, from GumpButton.cs and
    GumpImageTileButton.cs:

        { button        x y normal pressed type param ID }
        { buttontileart x y normal pressed type param ID itemid hue width height }

    The old parser took the LAST number, which for a buttontileart is its
    HEIGHT - so a tile-art button's real id was missing from the drawn set and
    its height was in it. A press guarded by that set is guarded by nothing.
    """
    layout = ("{ button 35 47 4005 4007 1 0 1 }"
              "{ buttontileart 35 77 4005 4007 1 0 2 6009 0 44 6 }"
              "{ tooltip 1044095 }"
              "{ button 10 10 4005 }")          # too short to carry an id
    saved = m["raw_layout"]
    try:
        m["raw_layout"] = lambda gid: layout
        drawn = m["drawn_buttons"](0x6ABCE12)
        check("a plain button's id", 1 in drawn, True)
        check("a buttontileart's id", 2 in drawn, True)
        check("NOT the buttontileart's height", 6 in drawn, False)
        check("nor its width", 44 in drawn, False)
        check("nor the tooltip's cliloc", 1044095 in drawn, False)
        check("a short element is skipped, not guessed at", 4005 in drawn,
              False)
        check("exactly those two", sorted(drawn), [1, 2])
        check("and the positions come with them",
              sorted(m["layout_buttons"](0x6ABCE12)),
              [(35, 47, 1), (35, 77, 2)])
    finally:
        m["raw_layout"] = saved


def test_the_failure_names_the_button_that_was_pressed(m):
    """2026-09-18: button 6 was pressed and the failure line said "button 0",
    because it printed WITHDRAW_BUTTON - the override, which is 0 - instead
    of the button actually sent."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def withdraw_one("):src.index("def tiles_between(")]
    tail = body[body.index("Nothing that looks like granite"):] \
        if "Nothing that looks like granite" in body else ""
    args = re.search(r"%\s*\(GRANITE_ID,\s*(\w+),", tail)
    check("the failure line is there", bool(tail), True)
    check("and it names the pressed button", args and args.group(1),
          "button")


def test_the_button_is_read_off_the_window_not_configured(m):
    """Asking a human to paste a button id is a design that did not work -
    three rounds of it and the script still would not start. The window is
    open in front of us; the row labelled STONE_LABEL carries the answer.

    A button read off the live layout cannot be stale and cannot be one the
    server did not draw, because it came FROM what the server drew.
    """
    check("nothing is forced by default", m["WITHDRAW_BUTTON"], 0)
    check("the Gump Inspector's reading is kept",
          m["WITHDRAW_BUTTON_CONFIRMED"], 1)
    check("and the row it belongs to is named", m["STONE_LABEL"], "Plain")

    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    pre = src[src.index("def preflight("):src.index("def main(")]
    check("preflight still refuses with no answer at all",
          "not WITHDRAW_BUTTON and not WITHDRAW_BUTTON_CONFIRMED" in pre, True)
    check("and it says what it will press before pressing it",
          "pressing button %d" in pre, True)
    check("and names the diagnostic only as a last resort",
          "diag_storage_gump.py" in pre, True)


# THE LIVE DUMP of the Stone Storage, diag_storage_gump.py, 2026-09-18 -
# the controls, text and buttons exactly as the server drew them. Two columns
# of five rows, every button LEFT of its label, and NO text entry: the "1"
# beside "Withdrawal Amount:" is a plain `text`.
LIVE_STONE_LAYOUT = (
    "{ page 0 }{ resizepic 0 0 9270 510 365 }{ gumppictiled 11 10 487 345 2624 }"
    "{ checkertrans 11 10 488 345 }{ text 20 25 88 0 }"
    "{ text 75 50 1158 1 }{ text 215 50 1152 2 }{ button 35 55 1209 1210 1 0 1 }"
    "{ text 75 90 1158 3 }{ text 215 90 1152 4 }{ button 35 95 1209 1210 1 0 2 }"
    "{ text 75 130 1158 5 }{ text 215 130 1152 6 }{ button 35 135 1209 1210 1 0 3 }"
    "{ text 75 170 1158 7 }{ text 215 170 1152 8 }{ button 35 175 1209 1210 1 0 4 }"
    "{ text 75 210 1158 9 }{ text 215 210 1152 10 }{ button 35 215 1209 1210 1 0 5 }"
    "{ text 315 50 1158 11 }{ text 455 50 1152 12 }{ button 275 55 1209 1210 1 0 6 }"
    "{ text 315 90 1158 13 }{ text 455 90 1152 14 }{ button 275 95 1209 1210 1 0 7 }"
    "{ text 315 130 1158 15 }{ text 455 130 1152 16 }{ button 275 135 1209 1210 1 0 8 }"
    "{ text 315 170 1158 17 }{ text 455 170 1152 18 }{ button 275 175 1209 1210 1 0 9 }"
    "{ text 315 210 1158 19 }{ text 455 210 1152 20 }{ button 275 215 1209 1210 1 0 10 }"
    "{ text 15 305 88 21 }{ text 150 305 1153 22 }"
    "{ button 225 308 11410 11411 1 0 21 }"
    "{ text 325 305 1153 23 }{ button 305 310 1209 1210 1 0 22 }"
    "{ text 15 335 88 24 }{ text 150 335 1152 25 }{ text 325 335 1153 26 }"
    "{ button 305 340 1209 1210 1 0 23 }")
LIVE_STONE_STRINGS = ["Stone Storage", "Plain", "59998", "Dull", "0", "Shadow",
                      "0", "Copper", "0", "Bronze", "0", "Gold", "0", "Agapite",
                      "0", "Verite", "0", "Valorite", "0", "Mythril", "0",
                      "Withdrawal Amount: ", "1", "Add", "Maximum Storage: ",
                      "999999", "Fill from backpack"]


def _live_window(m, layout=LIVE_STONE_LAYOUT, strings=LIVE_STONE_STRINGS):
    saved = {k: m[k] for k in ("raw_layout", "gump_lines", "log")}
    m["log"] = lambda *a, **k: None
    m["raw_layout"] = lambda gid: layout
    m["gump_lines"] = lambda gid, *a: list(strings)
    return lambda: [m.__setitem__(k, v) for k, v in saved.items()]


def test_the_row_is_found_by_its_label(m):
    """THE FIVE-ROW OFFSET. The search preferred a button to the RIGHT of the
    label; on the live window that walks past Plain's own button (x=35, left)
    and takes Gold's (x=275, right of Plain's count). That was the 6."""
    restore = _live_window(m)
    try:
        want = [("Plain", 1, "59998"), ("Dull", 2, "0"), ("Shadow", 3, "0"),
                ("Copper", 4, "0"), ("Bronze", 5, "0"), ("Gold", 6, "0"),
                ("Agapite", 7, "0"), ("Verite", 8, "0"),
                ("Valorite", 9, "0"), ("Mythril", 10, "0")]
        for label, button, count in want:
            check("%s is button %d" % (label, button),
                  m["find_stone_row"](label), (button, count))
        check("THE REPORTED FAILURE: Plain is NOT 6",
              m["find_stone_row"]("Plain")[0] == 6, False)
        check("a stone that is not listed gives nothing",
              m["find_stone_row"]("Iron"), (0, ""))
    finally:
        restore()

    # Gold's button missing: the nearest one to its left is PLAIN's, across
    # the window. Someone else's button is worse than none.
    no_gold = LIVE_STONE_LAYOUT.replace("{ button 275 55 1209 1210 1 0 6 }", "")
    restore = _live_window(m, layout=no_gold)
    try:
        check("a row with no button of its own gives none",
              m["find_stone_row"]("Gold")[0], 0)
        check("and Plain is unaffected", m["find_stone_row"]("Plain")[0], 1)
    finally:
        restore()

    # A SHORT STRING TABLE shifts every label onto the wrong row. Refuse.
    restore = _live_window(m, strings=LIVE_STONE_STRINGS[:-1])
    try:
        check("a short table is refused rather than misread",
              m["find_stone_row"]("Plain"), (0, ""))
    finally:
        restore()

    restore = _live_window(m, layout="")
    try:
        check("an unreadable layout gives nothing",
              m["find_stone_row"]("Plain"), (0, ""))
    finally:
        restore()


def test_the_live_window_draws_no_text_entry(m):
    """ServUO disconnects a reply carrying more text entries than the gump
    drew. This window draws NONE."""
    restore = _live_window(m)
    try:
        check("no text entry on the Stone Storage",
              m["text_entry_count"](0x6ABCE12), 0)
    finally:
        restore()
    restore = _live_window(m, layout=LIVE_STONE_LAYOUT
                           + "{ textentry 150 305 60 20 1153 0 22 }")
    try:
        check("but one is counted when it is there",
              m["text_entry_count"](0x6ABCE12), 1)
    finally:
        restore()


class _PressRecorder(object):
    def __init__(self):
        self.calls = []

    def SendAction(self, gid, button):
        self.calls.append(("SendAction", gid, button))

    def SendAdvancedAction(self, *args):
        self.calls.append(("SendAdvancedAction",) + tuple(args))

    def __getattr__(self, name):
        return lambda *a, **k: None


def _run_withdraw(m, layout=LIVE_STONE_LAYOUT):
    names = ("raw_layout", "gump_lines", "log", "Gumps", "open_storage",
             "refresh_pack", "pack_serials", "find_stone_row")
    saved = {k: m[k] for k in names}
    said, rec = [], _PressRecorder()
    try:
        m["log"] = lambda text, hue=None: said.append(text)
        m["raw_layout"] = lambda gid: layout
        m["gump_lines"] = lambda gid, *a: list(LIVE_STONE_STRINGS)
        m["Gumps"] = rec
        m["open_storage"] = lambda: object()
        m["refresh_pack"] = lambda: None
        m["pack_serials"] = lambda: set()
        m["withdraw_one"]()
    finally:
        for k, v in saved.items():
            m[k] = v
    return rec.calls, said


def test_THE_DISCONNECT_the_press_carries_no_text_entry(m):
    """2026-09-18: SendAdvancedAction(gump, 6, [], [0], ["1"]) - one text
    entry, to a window that draws none. That is ServUO's third disconnect
    rule, and it would have dropped the client with button 1 just the same.
    The recorded macro's first line made the identical mistake."""
    calls, said = _run_withdraw(m)
    check("one press went out", len(calls), 1)
    check("a PLAIN press - no text entry, no switches",
          calls[0][0] if calls else None, "SendAction")
    check("of the Inspector's button, 1",
          calls[0][2] if calls else None, 1)
    check("SendAdvancedAction is never used",
          [c for c in calls if c[0] == "SendAdvancedAction"], [])

    # A window that suddenly draws a text entry is not the one this was
    # written against. Nothing is pressed.
    calls, said = _run_withdraw(
        m, LIVE_STONE_LAYOUT + "{ textentry 150 305 60 20 1153 0 22 }")
    check("a window with a text entry gets no press at all", calls, [])
    check("and it says why", any("text entr" in s for s in said), True)


def test_the_amount_on_the_window_is_the_only_guard(m):
    """Nothing is sent WITH the press, so what the window reads is what comes
    out. 59998 granite in the pack is not a recoverable mistake."""
    restore = _live_window(m)
    try:
        check("1 is accepted", m["check_amount"](), True)
    finally:
        restore()
    fifty = list(LIVE_STONE_STRINGS)
    fifty[22] = "50"
    restore = _live_window(m, strings=fifty)
    try:
        check("50 is REFUSED", m["check_amount"](), False)
    finally:
        restore()
    restore = _live_window(m, strings=LIVE_STONE_STRINGS[:21])
    try:
        check("unreadable is REFUSED", m["check_amount"](), False)
    finally:
        restore()

    names = ("raw_layout", "gump_lines", "log", "Gumps", "open_storage")
    saved = {k: m[k] for k in names}
    rec = _PressRecorder()
    try:
        m["log"] = lambda *a, **k: None
        m["raw_layout"] = lambda gid: LIVE_STONE_LAYOUT
        m["gump_lines"] = lambda gid, *a: list(fifty)
        m["Gumps"] = rec
        m["open_storage"] = lambda: object()
        m["withdraw_one"]()
        check("and a refused amount means no press", rec.calls, [])
    finally:
        for k, v in saved.items():
            m[k] = v


def test_the_confirmed_number_wins_a_disagreement(m):
    """THE DISCONNECT, 2026-09-18. The row search returned 6 for the "Plain"
    row, the Gump Inspector had said 1, the search was believed, and pressing 6
    dropped the client.

    The search infers a button from GEOMETRY - a label's Y, a tolerance, a
    preference for whatever sits to its right. Every one of those is a guess
    about how the window is drawn. A Gump Inspector reading is the id the
    server received when a human clicked the thing they meant: a live dump,
    which is what this project's rules say to trust.

    So the search is a cross-check now and decides nothing.
    """
    said = []
    saved = {k: m[k] for k in ("find_stone_row", "log")}
    try:
        m["log"] = lambda text, hue=None: said.append(text)

        m["find_stone_row"] = lambda label: (1, "59999")
        check("agreement presses the confirmed one", m["choose_button"](), 1)
        check("and says nothing alarming",
              [s for s in said if "row search says" in s], [])

        # THE REPORTED FAILURE, exactly.
        del said[:]
        m["find_stone_row"] = lambda label: (6, "59998")
        check("the confirmed one still wins", m["choose_button"](),
              m["WITHDRAW_BUTTON_CONFIRMED"])
        check("and it is NOT the searched one", m["choose_button"]() == 6,
              False)
        check("the disagreement is said out loud",
              any("row search says" in s for s in said), True)

        # Nothing readable: the confirmed number still carries it.
        del said[:]
        m["find_stone_row"] = lambda label: (0, "")
        check("an unreadable window still presses the confirmed one",
              m["choose_button"](), m["WITHDRAW_BUTTON_CONFIRMED"])

        # An empty row is not worth pressing, whatever the button is.
        del said[:]
        m["find_stone_row"] = lambda label: (1, "0")
        check("an empty row is refused", m["choose_button"](), 0)
        check("saying there is none left",
              any("none left" in s for s in said), True)
    finally:
        for k, v in saved.items():
            m[k] = v


def test_nothing_is_pressed_without_a_confirmed_number(m):
    """A search that has been wrong once does not get to pick a button on a
    window where the wrong press disconnects you."""
    said = []
    saved = {k: m[k] for k in ("find_stone_row", "log",
                               "WITHDRAW_BUTTON_CONFIRMED")}
    try:
        m["log"] = lambda text, hue=None: said.append(text)
        m["WITHDRAW_BUTTON_CONFIRMED"] = 0
        m["find_stone_row"] = lambda label: (6, "59998")
        check("a found row is not enough on its own", m["choose_button"](), 0)
        check("and it says why",
              any("not trusted to choose" in s for s in said), True)
    finally:
        for k, v in saved.items():
            m[k] = v


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
    """The recording dragged twice because the first was out of range. One
    drag, and the reach is CHECKED rather than closed by walking - the spot
    that feeds the converter and still collects with "[grab" was found by
    hand, and wandering off it breaks both halves."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def run_batch("):src.index("def preflight(")]
    check("one drag for the granite", body.count("move_one(granite"), 1)
    reached = "in_reach(box" in body
    check("reach is checked first", reached, True)
    check("and that check comes before the drag",
          reached and "move_one(granite" in body
          and body.index("in_reach(box")
          < body.index("move_one(granite"), True)
    check("the batch does not walk anywhere",
          "walk_to" in body, False)


def test_standing_still_refuses_rather_than_walks(m):
    """STAND_STILL is the whole point of the new flow. Out of reach must be a
    refusal with the distance in it, not a walk."""
    said = []
    saved = {k: m[k] for k in ("log", "distance_to", "walk_to_item",
                               "STAND_STILL")}
    walked = []
    try:
        m["log"] = lambda text, hue=None: said.append(text)
        m["walk_to_item"] = lambda item, what: walked.append(what) or True

        m["distance_to"] = lambda item: 1
        check("in reach is in reach", m["in_reach"](object(), "the crate"),
              True)
        check("and nothing walked", walked, [])

        m["distance_to"] = lambda item: 9
        check("out of reach is refused", m["in_reach"](object(), "the crate"),
              False)
        check("still nothing walked", walked, [])
        check("and the distance is in the message",
              any("9 tiles away" in t for t in said), True)

        check("a missing item is refused too",
              m["in_reach"](None, "the crate"), False)

        # The old behaviour is still there for whoever wants it back.
        m["STAND_STILL"] = False
        m["distance_to"] = lambda item: 9
        check("STAND_STILL off walks again",
              m["in_reach"](object(), "the crate"), True)
        check("and it did walk", walked, ["the crate"])
    finally:
        for k, v in saved.items():
            m[k] = v


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
    the ground after the drop that was not on it before, ON THE PLATFORM.

    Inspected 2026-09-18: the platform is 0x402452B1 at (2073, 2504) and it is
    NOT a container - Container: No - so the sand is a ground item sitting on
    it, not something inside it.
    """
    # Inspected 2026-09-18: Name "sand", ItemID 0x423A, hue 0x096D.
    check("the graphic is known now", m["SAND_ID"], 0x423A)
    check("and the hue ships unpinned", m["SAND_HUE"], -1)
    check("the platform is where it lands", m["PLATFORM_SPOT"], (2073, 2504))
    check("and it is two tiles from the crate",
          max(abs(m["BOX_SPOT"][0] - m["PLATFORM_SPOT"][0]),
              abs(m["BOX_SPOT"][1] - m["PLATFORM_SPOT"][1])), 2)

    class Pos(object):
        def __init__(self, x, y):
            self.X, self.Y = x, y

    class Item(object):
        def __init__(self, serial, name, item_id, x=2073, y=2504, hue=0x096D):
            self.Serial = serial
            self.Name = name
            self.ItemID = item_id
            self.Hue = hue
            self.Position = Pos(x, y)

    def serial_of(item):
        """None rather than an exception, so a change that finds nothing shows
        up as a failed check instead of a traceback."""
        return getattr(item, "Serial", None)

    table = {1: Item(1, "sand", 0x423A),
             2: Item(2, "a pile of rocks", 0x1363),
             3: Item(3, "", 0x423A),
             # Something new that appeared across the room in the same second.
             4: Item(4, "sand", 0x423A, x=2090, y=2520),
             # Right place, right time, WRONG item - and unnamed, so only the
             # graphic tells it apart from the sand.
             5: Item(5, "", 0x1363)}
    saved = {k: m[k] for k in ("Items", "platform_spot")}
    try:
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(lambda s: table.get(s)),
            "WaitForProps": staticmethod(lambda *a: None),
            "GetPropStringList": staticmethod(lambda *a: [])})()
        m["platform_spot"] = lambda: (2073, 2504)

        check("by graphic, among several",
              serial_of(m["find_sand"]([1, 2])), 1)
        check("graphic wins over order",
              serial_of(m["find_sand"]([2, 1])), 1)
        # The graphic is checked BEFORE the name, because a graphic is a fact
        # about the item and a name has to be read off a tooltip that may not
        # have arrived. An unnamed piece of sand is still sand.
        check("an unnamed one is still found by graphic",
              serial_of(m["find_sand"]([3])), 3)
        check("and something else on the platform is not taken",
              m["find_sand"]([5]), None)

        check("nothing new is nothing", m["find_sand"]([]), None)

        # With the graphic unknown it falls back to the name, and then to
        # "one new thing and nothing else" - the path that carried this
        # before the inspection.
        saved_id = m["SAND_ID"]
        try:
            m["SAND_ID"] = 0
            check("without a graphic, by name",
                  serial_of(m["find_sand"]([1, 2])), 1)
            check("a lone unnamed item is taken",
                  serial_of(m["find_sand"]([3])), 3)
            check("several unnamed ones are refused",
                  m["find_sand"]([2, 3]), None)
        finally:
            m["SAND_ID"] = saved_id

        # ANCHORED ON THE PLATFORM. Something new 17 tiles away is not the
        # sand however new it is and however it is named.
        check("a distant new item is not the sand", m["find_sand"]([4]), None)
        check("even beside a real one, only the near one counts",
              serial_of(m["find_sand"]([4, 1])), 1)

        # WHY THE HUE IS NOT PINNED, as a behaviour rather than an opinion.
        # 0x096D is the hue one piece was inspected at, and it happens to be
        # the hue the order book gives Copper Granite - so it may be the sand's
        # own colour or it may be the stone's. Unpinned, a differently-hued
        # piece is still found; pinned, it is not. The graphic, the platform
        # and "new since the drop" are already three filters.
        odd = Item(6, "sand", 0x423A, hue=0x0000)
        table[6] = odd
        check("an unexpected hue is still found while unpinned",
              serial_of(m["find_sand"]([6])), 6)
        saved_hue = m["SAND_HUE"]
        try:
            m["SAND_HUE"] = 0x096D
            check("pinning it would reject that piece",
                  m["find_sand"]([6]), None)
            check("while the inspected hue still matches",
                  serial_of(m["find_sand"]([1])), 1)
        finally:
            m["SAND_HUE"] = saved_hue
    finally:
        for k, v in saved.items():
            m[k] = v


def test_the_platform_spot_falls_back_to_the_inspected_tile(m):
    """A serial that has not loaded is not the same thing as a platform that
    moved. It is locked down; it has not moved."""
    saved = m["Items"]
    try:
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(lambda s: None)})()
        check("out of range still gives the inspected tile",
              m["platform_spot"](), m["PLATFORM_SPOT"])
    finally:
        m["Items"] = saved


def test_the_sand_is_never_dragged_into_the_reagent_keys(m):
    """THE ITEM INSPECTOR SAYS Container: No. Nothing can be dragged into the
    Reagent Keys, so the deposit goes through the context menu every storage
    key on this shard uses. A drag would look like it worked and quietly do
    nothing."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    code = src[src.index("# HELPERS"):]
    check("nothing is moved into the key by serial",
          "move_one(sand, REAGENT_KEY_SERIAL" in code
          or "Items.Move(sand, REAGENT_KEY_SERIAL" in code, False)
    check("nor into the key item",
          "move_one(stack, key" in code or "Items.Move(stack, key" in code,
          False)
    body = between(code, "def store_sand(", "def run_batch(")
    check("the deposit is a context reply",
          "context_select(key, REAGENT_KEY_CONTEXT" in body, True)
    check("and the sand still only ever moves INTO the pack",
          "move_one(sand, int(pack.Serial)" in code, True)


def test_the_sand_is_counted_where_grab_actually_puts_it(m):
    """"[grab" fills a LOOT BAG inside the pack, not the pack itself - the
    first version counted the pack and saw nothing. Both are counted now,
    because a stack dragged out by hand would be loose in the pack.
    """
    check("the loot bag is the one the inspector showed",
          m["SAND_BAG_SERIAL"], 0x407D25FC)
    check("and the pouch holds the keys", m["KEY_BAG_SERIAL"], 0x4133A297)

    opened = []

    class Item(object):
        def __init__(self, serial, item_id, hue=0, amount=1, contains=()):
            self.Serial, self.ItemID, self.Hue = serial, item_id, hue
            self.Amount, self.Contains = amount, list(contains)

    sand_a = Item(1, m["SAND_ID"], 0x096D, 30)
    sand_b = Item(2, m["SAND_ID"], 0x096D, 20)
    loose = Item(3, m["SAND_ID"], 0x096D, 5)
    other = Item(4, 0x1779, 0, 1)
    bag = Item(m["SAND_BAG_SERIAL"], m["SAND_BAG_ID"], m["SAND_BAG_HUE"],
               1, [sand_a, sand_b, other])
    pack = Item(0x41D40F58, 0x0E75, 0, 1, [loose, other, bag])

    saved = {k: m[k] for k in ("Items", "Player", "Misc", "log")}
    try:
        m["log"] = lambda *a, **k: None
        m["Misc"] = type("M", (), {"Pause": staticmethod(lambda ms: None)})()
        m["Player"] = type("P", (), {"Backpack": pack})()
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(
                lambda ser: {m["SAND_BAG_SERIAL"]: bag,
                             0x41D40F58: pack}.get(int(ser))),
            "UseItem": staticmethod(lambda it: opened.append(int(it.Serial))),
            "WaitForContents": staticmethod(lambda it, ms: True)})()

        check("the bag's sand is counted", m["sand_in_bag"]()[0], 50)
        check("and the bag was RE-OPENED to read it",
              m["SAND_BAG_SERIAL"] in opened, True)
        check("the granite in there is not sand", m["sand_in_bag"]()[1],
              [sand_a, sand_b])

        del opened[:]
        check("loose sand in the pack is counted too",
              m["sand_in_pack"]()[0], 5)
        check("and the pack was re-opened for it", 0x41D40F58 in opened, True)

        check("on hand is both", m["sand_on_hand"]()[0], 55)

        # A bag that is not there is 0, not a crash and not the pack's count.
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(lambda ser: None),
            "UseItem": staticmethod(lambda it: None),
            "WaitForContents": staticmethod(lambda it, ms: True)})()
        check("no bag is no sand", m["sand_in_bag"](), (0, []))
    finally:
        for k, v in saved.items():
            m[k] = v


def test_neither_bag_is_compulsory(m):
    """Not everyone keeps a loot bag or a pouch. With the flags off nothing
    extra is opened, and the pack must be counted ONCE - adding it to itself
    would report double and make a clean deposit look like it left half
    behind."""
    opened = []

    class Item(object):
        def __init__(self, serial, item_id, hue=0, amount=1, contains=()):
            self.Serial, self.ItemID, self.Hue = serial, item_id, hue
            self.Amount, self.Contains = amount, list(contains)

    loose = Item(3, m["SAND_ID"], 0x096D, 40)
    keys = Item(9, m["REAGENT_KEY_ID"], m["REAGENT_KEY_HUE"])
    # The pouch and the loot bag EXIST - they are just not in use. If they
    # could not be found at all, "nothing opened them" would pass for the
    # wrong reason.
    pouch = Item(m["KEY_BAG_SERIAL"], m["KEY_BAG_ID"], m["KEY_BAG_HUE"])
    lootbag = Item(m["SAND_BAG_SERIAL"], m["SAND_BAG_ID"], m["SAND_BAG_HUE"])
    pack = Item(0x41D40F58, 0x0E75, 0, 1, [loose, keys, pouch, lootbag])

    saved = {k: m[k] for k in ("Items", "Player", "Misc", "log",
                               "SAND_IN_SEPARATE_BAG", "KEY_IN_SEPARATE_BAG",
                               "item_name")}
    try:
        m["log"] = lambda *a, **k: None
        m["item_name"] = lambda item: "reagent keys"
        m["Misc"] = type("M", (), {"Pause": staticmethod(lambda ms: None)})()
        m["Player"] = type("P", (), {"Backpack": pack})()
        dragged = []
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(
                lambda ser: {0x41D40F58: pack,
                             m["KEY_BAG_SERIAL"]: pouch,
                             m["SAND_BAG_SERIAL"]: lootbag}.get(int(ser))),
            "UseItem": staticmethod(lambda it: opened.append(int(it.Serial))),
            "WaitForContents": staticmethod(lambda it, ms: True),
            # RECORDED, not just counted: move_one swallows a failed drag and
            # returns False, so "it moved nothing" and "it never tried" look
            # identical from the return value alone.
            "Move": staticmethod(
                lambda item, target, amount: dragged.append(int(target)))})()
        m["SAND_IN_SEPARATE_BAG"] = False
        m["KEY_IN_SEPARATE_BAG"] = False

        check("the grab's sand is read from the pack", m["sand_in_bag"]()[0], 40)
        check("counted ONCE, not doubled", m["sand_on_hand"]()[0], 40)
        check("nothing opened the loot bag",
              m["SAND_BAG_SERIAL"] in opened, False)

        call("and nothing is dragged before storing", m["sand_bag_to_pack"], 0)
        check("no drag was even attempted", dragged, [])

        del opened[:]
        check("the keys are found loose in the pack",
              m["find_reagent_key"](), keys)
        check("and no pouch was opened", m["KEY_BAG_SERIAL"] in opened, False)
    finally:
        for k, v in saved.items():
            m[k] = v

    # The flags default to this user's layout, which is what ships.
    check("the loot bag is on by default", m["SAND_IN_SEPARATE_BAG"], True)
    check("and so is the pouch", m["KEY_IN_SEPARATE_BAG"], True)

    # Preflight must not DEMAND a bag that is switched off - that would refuse
    # to start for everyone who does not carry one.
    with open(SCRIPT, encoding="utf-8") as fh:
        pre = fh.read()
    pre = pre[pre.index("def preflight("):pre.index("def main(")]
    check("preflight only wants the pouch when it is in use",
          "if uses_key_bag() and Items.FindBySerial(KEY_BAG_SERIAL) is None:"
          in pre, True)
    check("and the loot bag likewise",
          "if uses_sand_bag() and Items.FindBySerial(SAND_BAG_SERIAL) is None:"
          in pre, True)


def test_the_keys_are_looked_for_in_the_pouch(m):
    """They are not carried loose in the pack. A container that has never been
    opened has no contents to search."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def find_reagent_key("):src.index("def context_is_blocked(")]
    code = re.sub(r'"""[\s\S]*?"""', "", body)
    opened = "open_container(KEY_BAG_SERIAL" in code
    check("the pouch is opened", opened, True)
    check("before the keys are looked up",
          opened and "FindBySerial(REAGENT_KEY_SERIAL" in code
          and code.index("open_container(KEY_BAG_SERIAL")
          < code.index("FindBySerial(REAGENT_KEY_SERIAL"), True)
    check("and the pouch's contents are searched",
          "contents_of(pouch)" in code, True)


def test_the_sand_leaves_the_bag_before_the_keys_are_asked(m):
    """Nothing has established that "Refill from stock" reaches into a
    sub-container, and the failure if it does not is silent: the sand stays
    in the bag and the deposit looks like it did nothing."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def store_sand("):src.index("def run_batch(")]
    moved = "sand_bag_to_pack()" in body
    check("the sand is moved to the pack", moved, True)
    check("before the context reply",
          moved and "context_select(" in body
          and body.index("sand_bag_to_pack()")
          < body.index("context_select("), True)
    check("and it is behind a flag that says why",
          "SAND_TO_PACK_BEFORE_STORE" in body, True)

    # WHOLE STACKS. One drag per stack, not one grain at a time.
    mover = between(src, "def sand_bag_to_pack(", "def find_reagent_key(")
    check("the whole stack moves at once",
          "move_one(stack, int(pack.Serial), \"the sand\", amount)" in mover,
          True)

    moved_now = []
    saved = {k: m[k] for k in ("sand_in_bag", "move_one", "Player", "log")}
    try:
        m["log"] = lambda *a, **k: None
        pack = type("P", (), {"Serial": 0x41D40F58})()
        m["Player"] = type("P", (), {"Backpack": pack})()
        stack = type("S", (), {"Serial": 1, "Amount": 50, "ItemID": m["SAND_ID"],
                               "Hue": 0x096D})()
        m["sand_in_bag"] = lambda: (50, [stack])
        m["move_one"] = lambda item, target, what, amount=1: (
            moved_now.append((int(target), amount)) or True)
        call("it reports how many it moved", m["sand_bag_to_pack"], 50)
        check("as one drag of the whole stack", moved_now,
              [(0x41D40F58, 50)])

        del moved_now[:]
        m["move_one"] = lambda item, target, what, amount=1: False
        call("a refused drag moves nothing", m["sand_bag_to_pack"], 0)
    finally:
        for k, v in saved.items():
            m[k] = v

    # AND IT ACTUALLY RUNS. Checking that the call is in the source only
    # proves the text is there - "if False:" in front of it would pass.
    order = []
    saved = {k: m[k] for k in ("sand_on_hand", "sand_bag_to_pack",
                               "find_reagent_key", "context_select", "log",
                               "Misc")}
    try:
        m["log"] = lambda *a, **k: None
        m["Misc"] = type("M", (), {"Pause": staticmethod(lambda ms: None)})()
        counts = [(50, []), (0, [])]
        m["sand_on_hand"] = lambda: counts.pop(0) if counts else (0, [])
        m["sand_bag_to_pack"] = lambda: order.append("moved") or 50
        m["find_reagent_key"] = lambda: object()
        m["context_select"] = lambda *a, **k: order.append("asked") or True
        call("the deposit still reports what it stored",
             m["store_sand"], (50, True))
        check("and the sand left the bag BEFORE the keys were asked",
              order, ["moved", "asked"])
    finally:
        for k, v in saved.items():
            m[k] = v


def test_the_context_entry_is_matched_exactly_first(m):
    """A key's menu sits next to Buy, Sell and Bribe. Exact first, always
    honoured; substring only after, and never onto CONTEXT_NEVER."""
    sent = []

    class Entry(object):
        def __init__(self, text):
            self.Entry = text

    def run(menu, wanted):
        del sent[:]
        saved = {k: m[k] for k in ("wait_context", "Misc", "log")}
        try:
            m["log"] = lambda *a, **k: None
            m["wait_context"] = lambda entity: [Entry(t) for t in menu]
            m["Misc"] = type("M", (), {
                "Pause": staticmethod(lambda ms: None),
                "ContextReply": staticmethod(
                    lambda entity, label: sent.append(label))})()
            return m["context_select"](object(), wanted, "the keys")
        finally:
            for k, v in saved.items():
                m[k] = v

    ok = run(["Buy", "Sell", "Refill from stock", "Rename"],
             ["Refill from stock"])
    check("the exact entry is taken", (ok, sent), (True, ["Refill from stock"]))

    # The REAL label goes back, not the search string - they differ in case
    # and spacing more often than not.
    ok = run(["Buy", "  refill from Stock  "], ["Refill from stock"])
    check("and the real label is what is sent",
          (ok, sent), (True, ["  refill from Stock  "]))

    # THE ORDER MATTERS. Substring-first would take "Refill from stockpile"
    # here, because it comes first in the menu and contains the search string.
    ok = run(["Refill from stockpile", "Refill from stock"],
             ["Refill from stock"])
    check("exact wins over an earlier substring match",
          (ok, sent), (True, ["Refill from stock"]))

    ok = run(["Buy", "Sell", "Bribe"], ["Refill"])
    check("a menu without it is refused", ok, False)
    check("and nothing was clicked", sent, [])

    # Substring matching must not wander onto something that costs gold.
    ok = run(["Buy something"], ["buy"])
    check("CONTEXT_NEVER blocks a substring match", ok, False)
    check("nothing clicked there either", sent, [])

    ok = run([], ["Refill from stock"])
    check("no menu at all is refused", ok, False)


def test_the_grab_waits_for_the_pile_to_stop_growing(m):
    """The shard collects in its own time. Waiting for an exact number would
    burn the whole timeout every batch; waiting for the count to stop rising
    finishes as soon as it has."""
    counts = [0, 0, 12, 33, 50, 50, 50, 50, 50, 50]
    said, spoke = [], []
    saved = {k: m[k] for k in ("sand_in_bag", "say", "log", "Misc")}
    try:
        m["log"] = lambda text, hue=None: said.append(text)
        m["Misc"] = type("M", (), {"Pause": staticmethod(lambda ms: None)})()
        m["say"] = lambda phrase: spoke.append(phrase) or True
        m["sand_in_bag"] = lambda: (counts.pop(0) if counts else 50, [])
        call("it returns what arrived", m["grab_sand"], 50, 50)
        check("and it said the phrase", spoke, [m["GRAB_PHRASE"]])
    finally:
        for k, v in saved.items():
            m[k] = v

    # Nothing picked up is reported, not treated as success.
    said, spoke = [], []
    saved = {k: m[k] for k in ("sand_in_bag", "say", "log", "Misc",
                               "GRAB_WAIT_MS")}
    try:
        m["log"] = lambda text, hue=None: said.append(text)
        m["Misc"] = type("M", (), {"Pause": staticmethod(lambda ms: None)})()
        m["say"] = lambda phrase: spoke.append(phrase) or True
        # Misc.Pause is a no-op here, so a full GRAB_WAIT_MS would be spent
        # spinning on the real clock. The behaviour under test is what it
        # returns when nothing arrives, not how long it is prepared to wait.
        m["GRAB_WAIT_MS"] = 50
        m["sand_in_bag"] = lambda: (0, [])
        call("an empty grab returns nothing", m["grab_sand"], 0, 50)
        check("and says so",
              any("Nothing arrived in the loot bag" in t for t in said),
              True)
    finally:
        for k, v in saved.items():
            m[k] = v

    # A grab that cannot even be said is not a grab.
    saved = {k: m[k] for k in ("sand_in_bag", "say", "log")}
    try:
        m["log"] = lambda *a, **k: None
        m["say"] = lambda phrase: False
        m["sand_in_bag"] = lambda: (0, [])
        call("an unsayable phrase gives up", m["grab_sand"], 0, 50)
    finally:
        for k, v in saved.items():
            m[k] = v


def test_the_deposit_is_verified_by_counting_the_pack(m):
    """A deposit that quietly does nothing would leave the sand there and the
    next batch would pile another 50 on top of it."""
    saved = {k: m[k] for k in ("sand_on_hand", "sand_bag_to_pack",
                               "find_reagent_key", "context_select",
                               "log", "Misc")}
    try:
        m["log"] = lambda *a, **k: None
        m["Misc"] = type("M", (), {"Pause": staticmethod(lambda ms: None)})()
        m["find_reagent_key"] = lambda: object()
        m["sand_bag_to_pack"] = lambda: 0
        m["context_select"] = lambda *a, **k: True

        counts = [(50, []), (0, [])]
        m["sand_on_hand"] = lambda: counts.pop(0)
        call("a clean deposit stores all of it", m["store_sand"], (50, True))

        counts = [(50, []), (50, [])]
        m["sand_on_hand"] = lambda: counts.pop(0)
        call("a deposit that took NOTHING stops the run",
             m["store_sand"], (0, False))

        counts = [(50, []), (8, [])]
        m["sand_on_hand"] = lambda: counts.pop(0)
        call("a partial deposit carries on", m["store_sand"], (42, True))

        m["sand_on_hand"] = lambda: (0, [])
        call("no sand is not a failure", m["store_sand"], (0, True))

        counts = [(50, []), (50, [])]
        m["sand_on_hand"] = lambda: counts.pop(0)
        m["find_reagent_key"] = lambda: None
        call("no keys means stop, not another batch",
             m["store_sand"], (0, False))
    finally:
        for k, v in saved.items():
            m[k] = v


def test_a_batch_is_fifty_stones_one_at_a_time(m):
    """The converter does not take a stack, so it is one withdraw and one drag
    per stone - BATCH_SIZE times - before anything is collected."""
    check("fifty to a batch", m["BATCH_SIZE"], 50)
    check("and it runs until stopped", m["BATCHES"], 0)
    check("one stone per withdraw", m["WITHDRAW_AMOUNT"], 1)

    drags = []
    saved = {k: m[k] for k in ("withdraw_one", "in_reach", "move_one", "log",
                               "Items")}
    try:
        m["log"] = lambda *a, **k: None
        m["withdraw_one"] = lambda: object()
        m["in_reach"] = lambda item, what: True
        m["move_one"] = lambda item, target, what: drags.append(target) or True
        m["Items"] = type("I", (), {
            "FindBySerial": staticmethod(lambda s: object())})()
        call("a full batch converts BATCH_SIZE", m["run_batch"],
             (m["BATCH_SIZE"], True), 1)
        check("one drag each, all into the converter",
              (len(drags), set(drags)), (m["BATCH_SIZE"], {m["BOX_SERIAL"]}))

        # Out of granite mid-batch: what was made still counts, and the caller
        # is told to stop.
        del drags[:]
        left = [object(), object(), None]
        m["withdraw_one"] = lambda: left.pop(0)
        call("a batch that runs dry reports what it made",
             m["run_batch"], (2, False), 2)
    finally:
        for k, v in saved.items():
            m[k] = v


def test_whatever_was_made_is_collected_even_when_the_batch_stops_early(m):
    """The sand is on the floor either way. A run that ends with 40 stones'
    worth nobody picked up is the failure this guards."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def main("):]
    grabs = "if converted:" in body and "grab_sand(converted)" in body
    check("the collect is gated on what was converted", grabs, True)
    check("and it happens BEFORE the stop is honoured",
          grabs and "if not keep_going:" in body
          and body.index("grab_sand(converted)")
          < body.index("if not keep_going:"), True)
    check("the ground fallback only runs when the grab got nothing",
          "if not got:" in body and "collect_sand_nearby(" in body
          and body.index("if not got:")
          < body.index("collect_sand_nearby("), True)


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
