"""Offline tests for Scripts/diag_storage_gump.py.

    python tests/test_diag_storage_gump.py

Loads the real script with the trailing main() call stripped and stub Razor
globals injected, then calls the actual functions - no copied logic to drift.

This report is the evidence the Sandmaker disconnect is waiting on. It was
asked for three times and never arrived; the tests pin the three things that
make it useful: every pressable element is listed with its REAL id, both
sides of each button are shown, and the whole thing lands in a file.
"""
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "diag_storage_gump.py")

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
    env = {"__name__": "diag_under_test",
           "Misc": _Stub(), "Items": _Stub(), "Gumps": _Stub(),
           "Target": _Stub()}
    exec(compile(source, SCRIPT, "exec"), env)
    return env


# Two columns of rows, buttons LEFT of their labels - the shape the Resource
# Order Book dump shows for this gump class. Invented numbers, real shape.
TWO_COLUMNS = ("{ page 0 }"
               "{ button 20 40 4005 4007 1 0 1 }"
               "{ croppedtext 45 40 80 20 0 1 }"          # Plain
               "{ croppedtext 130 40 60 20 0 2 }"         # 59998
               "{ button 220 40 4005 4007 1 0 6 }"
               "{ croppedtext 245 40 80 20 0 3 }"         # Gold
               "{ buttontileart 20 70 4005 4007 1 0 2 6009 0 44 21 }"
               "{ tooltip 1044095 }"
               "{ croppedtext 45 70 80 20 0 4 }"          # Dull
               "{ textentry 152 118 60 20 0 0 5 }"
               "{ button 10 10 4005 }")                   # too short
TWO_COLUMN_STRINGS = ["Plain", "59998", "Gold", "Dull"]


def _with_window(m, layout, strings):
    saved = {k: m[k] for k in ("raw_layout", "gump_lines")}
    m["raw_layout"] = lambda gid: layout
    m["gump_lines"] = lambda gid: list(strings)
    return lambda: [m.__setitem__(k, v) for k, v in saved.items()]


def test_every_pressable_element_is_listed_with_its_real_id(m):
    """{ buttontileart x y n p type param ID itemid hue width height } - the id
    is the SEVENTH number. The old report skipped this kind entirely, so a
    window drawn with tile-art buttons looked like it had none."""
    restore = _with_window(m, TWO_COLUMNS, TWO_COLUMN_STRINGS)
    try:
        got = m["buttons"](0x6ABCE12)
        ids = sorted(b[2] for b in got)
        check("plain and tile-art buttons, by their real ids", ids, [1, 2, 6])
        check("not the tile-art's height", 21 in ids, False)
        check("the kind is carried",
              [b[3] for b in got if b[2] == 2], ["buttontileart"])
        check("the text entry is not a button", 5 in ids, False)
    finally:
        restore()


def test_both_sides_of_a_button_are_shown(m):
    """Sandmaker's search preferred the label to the RIGHT and was five rows
    out. The report must not make that choice for the reader."""
    restore = _with_window(m, TWO_COLUMNS, TWO_COLUMN_STRINGS)
    try:
        cells = m["text_cells"](0x6ABCE12)
        left, right = m["labels_beside"](cells, 20, 40)
        check("Plain's button: nothing to its left", left, (None, None))
        check("Plain's button: Plain to its right", right, ("Plain", 45))

        left, right = m["labels_beside"](cells, 220, 40)
        check("Gold's button: the count of Plain to its left",
              left, ("59998", 130))
        check("Gold's button: Gold to its right", right, ("Gold", 245))

        check("off every row: nothing either side",
              m["labels_beside"](cells, 20, 300), ((None, None), (None, None)))
    finally:
        restore()


def test_the_report_lands_in_a_file(m):
    """The journal scrolls and has to be copied by hand. The raw layout goes in
    the file too, so nothing has to be inferred from the summary."""
    path = os.path.join(tempfile.mkdtemp(), "dump.txt")
    saved = m["REPORT_FILE"]
    try:
        m["REPORT_FILE"] = path
        del m["_report"][:]
        m["log"]("button 1      at   20,40   left: -   right: Plain @x45")
        ok = m["write_report"](TWO_COLUMNS, TWO_COLUMN_STRINGS)
        check("it says it was written", ok, True)
        body = open(path).read() if os.path.exists(path) else ""
        check("the logged lines are in it", "right: Plain @x45" in body, True)
        check("the raw layout is in it, whole",
              "{ buttontileart 20 70 4005 4007 1 0 2 6009 0 44 21 }" in body,
              True)
        check("and the string table, indexed", "  2  'Gold'" in body, True)

        m["REPORT_FILE"] = os.path.join(path, "no", "such", "dir.txt")
        check("an unwritable path says so rather than raising",
              m["write_report"]("", []), False)
    finally:
        m["REPORT_FILE"] = saved


def test_the_buttons_are_printed_last(m):
    """Printed first, they were off the top of the journal by the time anyone
    read it - and that is the block that never arrived."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def main("):]
    marks = ["TEXT CELLS", "TEXT ENTRIES", "WITHDRAWAL AMOUNT",
             "BUTTONS THE SERVER DREW", "FULL REPORT"]
    where = [body.find(k) for k in marks]
    check("every section is there", all(w >= 0 for w in where), True)
    check("in that order, buttons then the file path last",
          where == sorted(where), True)


def test_it_presses_nothing(m):
    """Read-only is the whole point. A diagnostic that presses a button on the
    window that disconnected us is not a diagnostic."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(l.split("#")[0] for l in code.splitlines())
    # CALLS, not words - the report itself warns about SendAdvancedAction.
    for call in ("Gumps.SendAction(", "Gumps.SendAdvancedAction(",
                 "Items.Move(", "Target.TargetExecute("):
        check("no %s" % call, call in code, False)


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
