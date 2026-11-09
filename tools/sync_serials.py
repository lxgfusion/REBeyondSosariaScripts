# -*- coding: utf-8 -*-
"""Deploy a script to its live folder with THIS machine's serials in it.

The shared copy of a script - the one in `Scripts/`, the one that goes to
GitHub - carries EXAMPLE serials. A serial belongs to one item on one shard;
nobody else's would work, and a real one left in a file that gets passed
around only makes the script look configured when it is not.

The real serials live in `.local/<script>.serials.py`, which is gitignored and
never leaves this machine. This tool is what puts the two together:

    python tools/sync_serials.py --check
        Verify every registered script: the shared copy holds no real-looking
        serial, the local block parses, and the live copy differs from the
        shared one ONLY inside the markers. Exit 1 if not.

    python tools/sync_serials.py --deploy combine_ro_books.py
        Write the live copy = shared code + local serial block. Use this
        instead of `cp`, which would overwrite the serials with examples.

    python tools/sync_serials.py --capture combine_ro_books.py
        The other direction, for a script whose serials are currently only in
        the live copy: lift its block into `.local/` and scrub the shared one.
        Run this once per script when adopting the split.

A script opts in by putting these two markers around the assignments:

    # >>> SERIALS
    DEPOSIT_BOOK_SERIAL = 0x00000000
    # <<< SERIALS

Everything between them is replaced wholesale, so the block may hold comments
and multi-line structures - which it does; PULL_STOPS is a list of dicts.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "Scripts")
LOCAL = os.path.join(ROOT, ".local")

OPEN_MARK = "# >>> SERIALS"
CLOSE_MARK = "# <<< SERIALS"

# script name -> the live folder it deploys to. There are two script roots in
# this repo; see CLAUDE.md.
REGISTERED = {
    "combine_ro_books.py": r"E:\uoclients\RazorEnhanced\Scripts",
}

# A serial on this shard is 0x4... or 0x8..., eight hex digits. Item IDs
# (0x2259), hues (0x04F7) and button numbers are shorter, so the length is
# what tells them apart - and the all-zero one is the example.
REAL_SERIAL = re.compile(r"0x[0-9A-Fa-f]{8}")

# Placeholders that are allowed to travel, because they belong to nothing.
# 0x00000000 is "not set yet", which the scripts check for by name and refuse
# to run on. The rest are the made-up serials used in worked examples; keep
# them obviously fake and keep them listed here.
EXAMPLE_SERIALS = set([
    0x00000000,
    # The made-up serials. 0x4000ABCD was the first; the run that follows it
    # was added on 2026-11-08 when Sandmaker's and ReagentBuyer's real ones
    # came out of the shared copies and their tests needed six distinct
    # stand-ins. Consecutive and obviously fake on purpose.
    0x4000ABCD,   # a storage key / the Master Keys
    0x4000ABCE,   # the Reagent Keys
    0x4000ABCF,   # the sand loot bag
    0x4000ABD0,   # the key pouch
    0x4000ABD1,   # the granite crate
    0x4000ABD2,   # the platform
    0x4000ABD3,   # the Stone Storage
])


def read(path):
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def find_mark(text, mark, where):
    """Where `mark` starts, matched AT THE START OF A LINE only.

    Column 0 matters: a script's SETUP_MODE prints these same markers as part
    of the config block it writes out for the user to paste, so the file
    contains them twice over - once as the real block and once as an indented
    string literal. Anchoring on the line start is what tells a marker from a
    script talking about one.
    """
    found = [m.start() for m in
             re.finditer(r"(?m)^" + re.escape(mark), text)]
    if len(found) != 1:
        raise SystemExit(
            "%s: expected exactly one line starting with %r, found %d. A "
            "script opts in to the split by having both markers at column 0."
            % (where, mark, len(found)))
    return found[0]


def split_block(text, where):
    """(before, block, after). Raises if the markers are missing or crossed."""
    start = find_mark(text, OPEN_MARK, where)
    end = find_mark(text, CLOSE_MARK, where) + len(CLOSE_MARK)
    if end <= start:
        raise SystemExit("%s: the markers are the wrong way round." % where)
    return text[:start], text[start:end], text[end:]


def real_serials(block):
    """Eight-digit hex constants in the block that belong to a real item."""
    return [s for s in REAL_SERIAL.findall(block)
            if int(s, 16) not in EXAMPLE_SERIALS]


def leaked_serials(text):
    """Real serials outside the markers that would travel with the script.

    Two kinds of eight-hex constant are NOT item serials and are skipped:

      * gump ids - BOOK_GUMP, ORDERS_GUMP_HINT, AR_GUMPID are all eight hex
        digits, and they are properties of the shard's windows rather than of
        anybody's items. Skipped by name, on the line.
      * anything in a `#` comment - the carried half quotes live item dumps in
        its comments (a deed's serial, the backpack's) as evidence for how a
        tooltip parses. Those came with the code and scrubbing them would
        break the verbatim diff for no gain.

    Docstrings are NOT skipped. A worked example in the module docstring is
    exactly where a real serial hides in plain sight, which is where this
    found one.
    """
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        code = line.split("#", 1)[0]
        if "GUMP" in code.upper():
            continue
        out.extend(real_serials(code))
    return out


def local_path(script):
    return os.path.join(LOCAL, script.replace(".py", "") + ".serials.py")


def live_path(script):
    folder = REGISTERED.get(script)
    if folder is None:
        raise SystemExit("%s is not in REGISTERED - add it with its live "
                         "folder." % script)
    return os.path.join(folder, script)


def do_deploy(script):
    shared = read(os.path.join(SCRIPTS, script))
    before, example, after = split_block(shared, "Scripts/" + script)

    leaked = real_serials(example)
    if leaked:
        raise SystemExit(
            "Scripts/%s still has real serial(s) in its block: %s. The shared "
            "copy must carry examples - run --capture first."
            % (script, ", ".join(sorted(set(leaked)))))

    lp = local_path(script)
    if not os.path.exists(lp):
        raise SystemExit(
            "%s does not exist, so there are no serials to deploy. Either run "
            "--capture on a live copy that already has them, or write that "
            "file with a block between the markers." % lp)
    block = read(lp)
    _b, block, _a = split_block(block, lp)
    if not real_serials(block):
        print("  warning: %s has no real serials in it either." % lp)

    target = live_path(script)
    nl = "\r\n" if "\r\n" in shared else "\n"
    if "\r\n" in shared and "\r\n" not in block:
        block = block.replace("\n", "\r\n")
    write(target, before + block + after)
    print("deployed %s -> %s (%d serial(s) from %s)"
          % (script, target, len(real_serials(block)),
             os.path.relpath(lp, ROOT)))
    return 0


def do_capture(script):
    """Lift the live copy's block into .local/.

    IT DOES NOT TOUCH THE SHARED COPY, whatever this docstring said until
    2026-11-08. Scrubbing Scripts/<script> is a separate, manual step, and
    believing otherwise is how a real serial sits in the shared copy with
    somebody thinking it was handled.
    """
    target = live_path(script)
    if not os.path.exists(target):
        raise SystemExit("%s does not exist." % target)
    live = read(target)
    _b, block, _a = split_block(live, target)
    if not real_serials(block):
        print("  note: the live copy's block has no real serials in it.")

    if not os.path.isdir(LOCAL):
        os.makedirs(LOCAL)
    lp = local_path(script)
    if os.path.exists(lp):
        raise SystemExit("%s already exists - delete it first if you really "
                         "mean to replace it." % lp)
    write(lp, block if block.endswith("\n") else block + "\n")
    print("captured %d serial(s) into %s"
          % (len(real_serials(block)), os.path.relpath(lp, ROOT)))
    return 0


def do_check():
    bad = 0
    for script in sorted(REGISTERED):
        shared_file = os.path.join(SCRIPTS, script)
        if not os.path.exists(shared_file):
            print("FAIL  %s: not in Scripts/" % script)
            bad += 1
            continue
        shared = read(shared_file)
        try:
            s_before, s_block, s_after = split_block(shared,
                                                     "Scripts/" + script)
        except SystemExit as err:
            print("FAIL  %s" % err)
            bad += 1
            continue

        leaked = sorted(set(real_serials(s_block)))
        if leaked:
            print("FAIL  Scripts/%s carries real serial(s): %s"
                  % (script, ", ".join(leaked)))
            bad += 1
        else:
            print("ok    Scripts/%s block is examples only" % script)

        # Outside the block, a real serial is one somebody forgot to move
        # inside the markers - or wrote into a worked example, which is how
        # this check earned its keep.
        outside = sorted(set(leaked_serials(s_before + s_after)))
        if outside:
            print("FAIL  Scripts/%s has serial(s) OUTSIDE the markers: %s"
                  % (script, ", ".join(outside)))
            bad += 1

        target = live_path(script)
        if not os.path.exists(target):
            print("      (no live copy at %s - nothing to compare)" % target)
            continue
        live = read(target)
        try:
            l_before, l_block, l_after = split_block(live, target)
        except SystemExit as err:
            print("FAIL  %s" % err)
            bad += 1
            continue
        if (l_before, l_after) != (s_before, s_after):
            print("FAIL  %s differs from Scripts/%s OUTSIDE the serial block "
                  "- the code has drifted, not just the config."
                  % (target, script))
            bad += 1
        else:
            print("ok    live copy matches outside the block")
        if not real_serials(l_block):
            print("      (the live copy has no real serials either - not set "
                  "up yet?)")

    print("\n%s" % ("all checks passed" if not bad
                    else "%d problem(s)" % bad))
    return 1 if bad else 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "--check":
        return do_check()
    if len(argv) == 3 and argv[1] == "--deploy":
        return do_deploy(argv[2])
    if len(argv) == 3 and argv[1] == "--capture":
        return do_capture(argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
