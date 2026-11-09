# -*- coding: utf-8 -*-
"""What real item serials would a push publish?

`tools/sync_serials.py` keeps the real serials out of the shared copy for
scripts that can hold them in one marker block. Some cannot: in
`Sandmaker.py` the six serials sit a hundred lines apart, each under its own
paragraph of Item Inspector evidence, in a config band the owner reads top to
bottom. Gathering them to suit the tool would move six explanations away from
the things they explain.

So those scripts are scrubbed by hand, and this is what stops that being a
one-off. It parses every tracked file and reports module-level constants whose
value looks like an item serial on this shard.

    python tools/check_serials.py
        What is NOT already on origin/main - "would pushing publish a serial
        that is not public yet". Exit 1 if so. THE DEFAULT, because it is the
        question with an answer somebody can act on, and the one that caught
        four serials on 2026-11-08 minutes before a push.

    python tools/check_serials.py --all
        Every real-looking serial in every tracked file, published or not.
        This currently fails on 26 files and that is not a bug: the repo has
        carried real serials since long before the split existed, mostly in
        `.snapshots/` and in test fixtures built from live dumps, and they
        are all already public. Treat it as the retrofit worklist, not as a
        gate.

WHY PARSED AND NOT GREPPED. A serial in a comment or a doc is EVIDENCE - the
Item Inspector dump that explains why a constant holds what it holds - and
scrubbing those would break the record for no gain once the number is already
public. A serial in an assignment is CONFIGURATION, and that is what must not
travel. Only an assignment can tell the two apart, so the file is parsed.

The one case this cannot see is a serial written into a comment that is NOT
already public. Nothing automatic can judge that; what it needs is somebody
reading the diff before the push, which is also true of everything else.
"""
import ast
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A serial on this shard is eight hex digits starting 0x4.. or 0x8..; item ids
# (0x2258), hues (0x04F7) and button numbers are shorter. These eight-digit
# values are NOT item serials:
#
#   * gump ids. A gump id describes a window layout the server sends
#     everybody. Publishing one tells nobody anything about one player's
#     items, and the scripts need the real one to find the window at all.
#   * the placeholders. 0x00000000 is "not set yet", which the scripts check
#     for by name and refuse to run on. The 0x4000ABxx run is the made-up
#     serials used in worked examples and test fixtures; keep them obviously
#     fake and keep them listed here.
NOT_A_SERIAL = set([
    # gump ids, by value, for the cases a name does not give away
    0xE13358F7, 0xB2F21F1A, 0xBB4D7BED, 0xC395ADB4, 0xC5F60B43, 0x06ABCE12,
    0x52554E43, 0x52554E47, 0x52554E4D, 0x52554E50, 0x52554E51, 0x52554E52,
    0x52554E53, 0x52554E55,
    # placeholders and worked-example serials
    0x00000000,
    0x4000AAAA, 0x4000BBBB, 0x4000ABCD, 0x4000ABCE, 0x4000ABCF,
    0x4000ABD0, 0x4000ABD1, 0x4000ABD2, 0x4000ABD3,
    0x40000001, 0x40000002, 0x40000003, 0x40001111,
])

# A constant whose NAME says it is not a serial. Checked on the name rather
# than the value because a new gump id should not have to be added above
# before the check passes.
NOT_SERIAL_NAMES = ("GUMP", "BUTTON", "HUE", "ITEM_ID", "ITEMID", "GRAPHIC",
                    "BODY", "SPELL",
                    # A BOUND IS NOT A SERIAL. SERIAL_LOW and SERIAL_HIGH
                    # below are the range this very check uses, and the
                    # first run of the tool reported them as leaked serials
                    # in its own source - which is the right answer to the
                    # wrong question.
                    "_LOW", "_HIGH", "_MIN", "_MAX", "BOUND", "RANGE")

SERIAL_LOW = 0x10000000
SERIAL_HIGH = 0xFFFFFFFF


def git(*args):
    proc = subprocess.Popen(["git"] + list(args), cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _err = proc.communicate()
    if proc.returncode != 0:
        return None
    return out.decode("utf-8", "replace")


def numbers_in(value):
    """Every int inside a literal, however nested.

    A serial hides in a list of them (`PULL_STOPS`) and in a dict's keys as
    readily as in a bare assignment, so the whole structure is walked. `bool`
    is excluded first: True is an int in Python and 1 is not a serial.
    """
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        yield value
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            for found in numbers_in(item):
                yield found
    elif isinstance(value, dict):
        for key, item in value.items():
            for found in numbers_in(key):
                yield found
            for found in numbers_in(item):
                yield found


def looks_like_a_serial(number):
    return SERIAL_LOW <= number <= SERIAL_HIGH and number not in NOT_A_SERIAL


def serials_in_source(source):
    """{constant name: set of real-looking serials} at module level."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not names:
            continue
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue          # a name, a call, an f-string: not a literal
        for name in names:
            if any(word in name.upper() for word in NOT_SERIAL_NAMES):
                continue
            hits = set(n for n in numbers_in(value)
                       if looks_like_a_serial(n))
            if hits:
                found.setdefault(name, set()).update(hits)
    return found


def tracked_python():
    listing = git("ls-files")
    if listing is None:
        raise SystemExit("not a git repository: %s" % ROOT)
    return sorted(f for f in listing.split("\n") if f.endswith(".py"))


def read_at(ref, path):
    return git("show", "%s:%s" % (ref, path))


def main(argv):
    only_new = "--all" not in argv[1:]
    if only_new and git("rev-parse", "--verify", "origin/main") is None:
        raise SystemExit("this needs origin/main to compare against; run "
                         "`git fetch origin`, or pass --all.")

    bad = 0
    looked = 0
    for path in tracked_python():
        full = os.path.join(ROOT, path.replace("/", os.sep))
        if not os.path.exists(full):
            continue
        with open(full, encoding="utf-8") as handle:
            here = serials_in_source(handle.read())
        if here is None:
            print("?     %s does not parse" % path)
            continue
        looked += 1
        if not here:
            continue

        if only_new:
            published = read_at("origin/main", path)
            already = {}
            if published is not None:
                already = serials_in_source(published) or {}
            here = dict((name, values - already.get(name, set()))
                        for name, values in here.items())
            here = dict((n, v) for n, v in here.items() if v)
            if not here:
                continue

        bad += 1
        print("FAIL  %s" % path)
        for name in sorted(here):
            print("        %-28s %s" % (name, ", ".join(
                "0x%08X" % value for value in sorted(here[name]))))

    print("")
    print("%d tracked python file(s) parsed." % looked)
    if bad:
        print("%d file(s) carry a real-looking serial in a module-level "
              "constant." % bad)
        print("")
        print("The shared copy is supposed to ship 0x00000000 and keep the "
              "real value in")
        print(".local/<script>.serials.py, which is gitignored. See CLAUDE.md.")
        if not only_new:
            print("")
            print("This is --all, so most of these are already public and "
                  "have been for months.")
            print("The retrofit is outstanding work, not a reason to stop a "
                  "push.")
        return 1
    if only_new:
        print("ok    a push would publish no serial that is not already "
              "public.")
    else:
        print("ok    no tracked script ships a real item serial.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
