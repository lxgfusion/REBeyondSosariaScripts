"""Offline tests for Scripts/diag_gump_watch.py.

    python tests/test_diag_gump_watch.py

Loads the real script with the trailing main() call stripped and stub Razor
globals injected, then calls the actual functions.

This one runs while something is misbehaving, so the two things it must never
do are press anything and run forever.
"""
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "diag_gump_watch.py")

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
    env = {"__name__": "watch_under_test",
           "Misc": _Stub(), "Gumps": _Stub()}
    exec(compile(source, SCRIPT, "exec"), env)
    return env


def test_it_presses_nothing(m):
    """It is run BECAUSE windows will not close. A watcher that closes one
    destroys the evidence it was started to collect."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(l.split("#")[0] for l in code.splitlines())
    for call in ("Gumps.CloseGump(", "Gumps.SendAction(",
                 "Gumps.SendAdvancedAction(", "Gumps.ResetGump(",
                 "Items.Move(", "Items.UseItem("):
        check("no %s" % call, call in code, False)


def test_the_page_marker_is_what_tells_two_pages_apart(m):
    """Two pages of the order list carry the same title. "(1/44)" is the only
    thing in the text that says which page a window is showing."""
    saved = m["gump_lines"]
    try:
        m["gump_lines"] = lambda gid: [
            "Resource Orders Contents: 31781/100000 Displayed: 5",
            "Item", "Amt To Gather", "", "(3/44)"]
        got = m["describe"](0x1234)
        check("the page marker is carried", "page (3/44)" in got, True)
        check("and the title with it", got.startswith("Resource Orders"), True)

        m["gump_lines"] = lambda gid: ["Stone Storage", "Plain", "59998"]
        check("a window with no page marker just reads",
              m["describe"](0x1234), "Stone Storage | Plain | 59998")

        m["gump_lines"] = lambda gid: []
        check("and an empty one says nothing", m["describe"](0x1234), "")
    finally:
        m["gump_lines"] = saved


def test_the_log_is_written_as_it_goes(m):
    """It is meant to be stopped by hand mid-run - Razor just kills the
    thread - so a report written only at the end is a report that never
    arrives."""
    path = os.path.join(tempfile.mkdtemp(), "watch.txt")
    saved = (m["REPORT_FILE"], m["_started"][0])
    try:
        m["REPORT_FILE"] = path
        m["_started"][0] = 0.0
        del m["_report"][:]
        m["log"]("APPEARED  0xC5F60B43  Resource Orders")
        body = open(path).read() if os.path.exists(path) else ""
        check("the line is on disk before the run ends",
              "APPEARED  0xC5F60B43" in body, True)

        m["log"]("gone      0xC5F60B43  Resource Orders")
        body = open(path).read() if os.path.exists(path) else ""
        check("and so is the next one", body.count("0xC5F60B43"), 2)

        # REPORTED, never raised: a log() that throws would take down the
        # whole watch mid-run, and a traceback here would hide every check
        # after it.
        m["REPORT_FILE"] = os.path.join(path, "no", "such", "file.txt")
        survived = True
        try:
            m["log"]("an unwritable path must not raise")
        except Exception:
            survived = False
        check("an unwritable path is survived", survived, True)
    finally:
        m["REPORT_FILE"], m["_started"][0] = saved


def test_the_watch_is_bounded_and_never_busy_waits(m):
    """Every polling loop here gets a Misc.Pause and a wall-clock deadline."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def main("):]
    check("it pauses between looks", "Misc.Pause(POLL_MS)" in body, True)
    check("and the loop has a deadline",
          "deadline and time.time() >= deadline" in body, True)
    check("WATCH_SECONDS is a real bound by default",
          m["WATCH_SECONDS"] > 0, True)
    check("and the poll is not a spin", m["POLL_MS"] >= 250, True)


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
