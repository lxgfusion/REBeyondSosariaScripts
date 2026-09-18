"""
Dump a storage key's gump: every button it DREW, and what sits beside it.
========================================================================

For Razor Enhanced (IronPython 3.4). It opens the container and reads. It does
NOT press anything, move anything or type anything.

WHY THIS EXISTS
---------------
Sandmaker pressed button 6 on the Stone Storage believing it was the "Plain"
row, and the client dropped. The Gump Inspector says Plain is 1. Nobody has yet
seen where the buttons on that window actually sit relative to their labels,
and that is what this prints.

What stock ServUO disconnects for, from Server/Network/PacketHandlers.cs
(DisplayGumpResponse) - the ONLY four reasons:

  * a button id the server did not draw on that gump (0, close, is always ok)
  * more switches than the gump has
  * more text entries than the gump has
  * a text entry longer than 239 characters

A reply to a gump the server no longer holds is IGNORED, not a drop - it only
matches gumps it still has. The button that dropped the client WAS drawn, so
either this shard's core differs from stock or something other than that
check did it.

Gump 0x6ABCE12 is the shared "stash" window every storage key on this shard
opens - resource_order_runner.py calls it BOOK_GUMP, harvest_runner.py calls it
HOUSE_DEPOSIT_GUMP. On the Resource Order Book the buttons are 1, 3, 4, 5 and 8
and every one sits to the LEFT of its label.

USAGE
-----
Run it and target the storage key. The whole report, plus the raw layout, is
written to a file whose path is the LAST line printed. Send that file - it
does not scroll away.
"""

import os
import re


# =============================================================================
# CONFIG
# =============================================================================

# Fill this in to skip the target prompt. 0 asks every run.
STORAGE_SERIAL = 0

# The shared stash gump. Left as config because a shard can change it and
# because this script should be usable on any of these windows.
STASH_GUMP = 0x06ABCE12

# Wait for the window, and settle after it opens.
GUMP_TIMEOUT_MS = 10000
SETTLE_MS = 700

# How close a string has to be to a button, vertically, to be called its label.
LABEL_ROW_TOLERANCE = 12

# Where the report goes. Overwritten every run.
REPORT_FILE = os.path.join(os.environ.get("TEMP", "."), "storage_gump_dump.txt")

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

# Everything log() says, so it can be written to REPORT_FILE at the end.
_report = []


def log(text, hue=HUE_INFO):
    _report.append(text)
    Misc.SendMessage("[Gump] " + text, hue, False)


def raw_layout(gump_id):
    try:
        return Gumps.GetGumpRawLayout(gump_id) or ""
    except Exception:
        return ""


def gump_lines(gump_id):
    """The gump's strings, in layout order. [] when there is no gump.

    A NULL return means "no such window", not an error - list(None) would
    surface as a TypeError about iteration from somewhere far away.
    """
    try:
        raw = Gumps.GetLineList(gump_id, False)
    except TypeError:
        try:
            raw = Gumps.GetLineList(gump_id)
        except Exception:
            return []
    except Exception:
        return []
    return list(raw or [])


def elements(layout):
    """[{kind, nums}] for every { ... } element, in layout order."""
    out = []
    for piece in re.findall(r"\{([^{}]*)\}", layout or ""):
        piece = piece.strip()
        if not piece:
            continue
        out.append({"kind": piece.split()[0].lower(),
                    "nums": [int(n) for n in re.findall(r"-?\d+", piece)]})
    return out


def text_cells(gump_id):
    """(x, y, text) for every text cell, paired BY ORDER.

    NOT by the text id in the layout. Razor drops empty strings out of a gump's
    string table without leaving a gap, so one blank cell shifts every later id
    down by one - see CLAUDE.md. Pairing by element order is the only safe
    reading, and it is still only safe while the counts agree, which the report
    checks and says.
    """
    lines = gump_lines(gump_id)
    cells, index = [], 0
    for el in elements(raw_layout(gump_id)):
        if el["kind"] not in ("text", "croppedtext"):
            continue
        text = lines[index] if index < len(lines) else ""
        index += 1
        if len(el["nums"]) >= 2:
            cells.append((el["nums"][0], el["nums"][1],
                          str(text or "").strip()))
    return cells


# The two kinds of element a server answers to, and where each carries its id.
# From ServUO Server/Gumps/GumpButton.cs and GumpImageTileButton.cs:
#
#     { button        x y normal pressed type param ID }
#     { buttontileart x y normal pressed type param ID itemid hue width height }
#
# The id is the SEVENTH number in both - for a buttontileart the last number
# is its height. DisplayGumpResponse accepts a press on either kind.
BUTTON_KINDS = ("button", "buttontileart")
BUTTON_ID_INDEX = 6


def buttons(gump_id):
    """(x, y, id, kind) for every button the server DREW."""
    out = []
    for el in elements(raw_layout(gump_id)):
        if el["kind"] in BUTTON_KINDS and len(el["nums"]) > BUTTON_ID_INDEX:
            out.append((el["nums"][0], el["nums"][1],
                        el["nums"][BUTTON_ID_INDEX], el["kind"]))
    return out


def entries(gump_id):
    """(x, y, entry_id) for every text entry - one per thing you can type in."""
    out = []
    for el in elements(raw_layout(gump_id)):
        if el["kind"] == "textentry" and len(el["nums"]) >= 6:
            out.append((el["nums"][0], el["nums"][1], el["nums"][5]))
    return out


def labels_beside(cells, x, y):
    """((left_text, left_x), (right_text, right_x)) on this button's row.

    BOTH sides, with no preference. Sandmaker's row search preferred the
    right and was five rows out; on the only other dump of this gump class
    the buttons sit to the LEFT of their labels. Printing both lets the
    reader see which it is instead of the report deciding for them.
    (None, None) on a side with nothing there.
    """
    row = [(cx, text) for cx, cy, text in cells
           if abs(cy - y) <= LABEL_ROW_TOLERANCE and text]
    left = sorted((cx, t) for cx, t in row if cx < x)
    right = sorted((cx, t) for cx, t in row if cx >= x)
    lft = (left[-1][1], left[-1][0]) if left else (None, None)
    rgt = (right[0][1], right[0][0]) if right else (None, None)
    return lft, rgt


def nearest_label(cells, x, y):
    """The nearer of the two labels beside (x, y), for text entries."""
    (lt, lx), (rt, rx) = labels_beside(cells, x, y)
    if lt is None:
        return rt or ""
    if rt is None:
        return lt
    return lt if (x - lx) < (rx - x) else rt


def describe_side(text, cx):
    if text is None:
        return "-"
    return "%s @x%d" % (text[:24], cx)


def withdrawal_amount(strings, ents, cells):
    """What the Withdrawal Amount box currently holds, and how it was read.

    Read POSITIONALLY - the string straight after the "Withdrawal Amount:"
    label - because that is what a live dump of the Stone Storage showed:

        21  Withdrawal Amount:
        22  1

    The textentry element carries an InitialTextID that should point at the
    same string, and it is reported too, but it is NOT trusted as an index:
    Razor drops empty strings out of the table without leaving a gap, so every
    id past the first blank is off by one. See CLAUDE.md.

    Returns (value, how). value is "" when it could not be read at all.
    """
    for i, text in enumerate(strings):
        if "withdrawal amount" in str(text or "").strip().lower():
            if i + 1 < len(strings):
                return str(strings[i + 1]).strip(), "the string after the label"
            return "", "the label is the last string - nothing after it"
    return "", "no 'Withdrawal Amount:' label on this window"


def write_report(layout, strings):
    """Everything said, then the raw layout and string table, to REPORT_FILE.

    True if it was written. The journal scrolls and has to be copied by hand;
    three requests for the button block never produced it. A file does not
    scroll.
    """
    try:
        with open(REPORT_FILE, "w") as fh:
            for line in _report:
                fh.write(line + "\n")
            fh.write("\n==== RAW LAYOUT ====\n")
            for piece in re.findall(r"\{[^{}]*\}", layout or ""):
                fh.write(piece + "\n")
            fh.write("\n==== STRING TABLE (GetLineList) ====\n")
            for i, text in enumerate(strings):
                fh.write("%3d  %r\n" % (i, text))
        return True
    except Exception as err:
        log("could not write %s: %r" % (REPORT_FILE, err), HUE_BAD)
        return False


def pick_storage():
    if STORAGE_SERIAL:
        item = Items.FindBySerial(STORAGE_SERIAL)
        if item is not None:
            return item
        log("STORAGE_SERIAL 0x%X did not resolve - asking instead."
            % STORAGE_SERIAL, HUE_WARN)
    log("Target the storage key.", HUE_GOOD)
    try:
        serial = Target.PromptTarget("Target the storage key to inspect", 945)
    except Exception as err:
        log("Could not prompt: %s" % err, HUE_BAD)
        return None
    if not serial:
        log("Nothing targeted.", HUE_WARN)
        return None
    return Items.FindBySerial(int(serial))


def main():
    del _report[:]
    log("read-only - nothing will be pressed, typed or moved.", HUE_GOOD)

    item = pick_storage()
    if item is None:
        log("No storage key to inspect.", HUE_BAD)
        return

    try:
        log("inspecting 0x%X, ItemID 0x%04X, hue 0x%04X"
            % (int(item.Serial), int(item.ItemID), int(item.Hue)))
    except Exception:
        pass

    # Close it first. WaitForGump returns True for a window that is ALREADY
    # open, so a leftover one would be reported instead of this key's.
    try:
        Gumps.CloseGump(STASH_GUMP)
    except Exception:
        pass
    Misc.Pause(SETTLE_MS)

    Items.UseItem(item)
    Gumps.WaitForGump(STASH_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)

    try:
        open_now = Gumps.HasGump(STASH_GUMP)
    except Exception:
        open_now = False
    if not open_now:
        log("Gump 0x%X never opened. Open windows right now:" % STASH_GUMP,
            HUE_BAD)
        try:
            for gid in (Gumps.AllGumpIDs() or []):
                first = [t for t in gump_lines(int(gid)) if str(t).strip()][:2]
                log("  0x%X  %s" % (int(gid), " | ".join(str(f) for f in first)),
                    HUE_WARN)
        except Exception:
            pass
        log("If one of those is this key's window, set STASH_GUMP to its id.",
            HUE_WARN)
        return

    layout = raw_layout(STASH_GUMP)
    cells = text_cells(STASH_GUMP)
    btns = buttons(STASH_GUMP)
    ents = entries(STASH_GUMP)
    strings = gump_lines(STASH_GUMP)

    log("gump 0x%X: %d button(s), %d text entr(y/ies), %d text cell(s), "
        "%d string(s)" % (STASH_GUMP, len(btns), len(ents), len(cells),
                          len(strings)), HUE_GOOD)

    # The pairing above is only sound while these agree. Say so either way -
    # a label read off a shifted table is worse than no label at all.
    if len(strings) != len(cells):
        log("  WARNING: %d text cells but %d strings. The table is short, so "
            "every label below may belong to the cell before it. Trust the "
            "BUTTON IDS, not the labels."
            % (len(cells), len(strings)), HUE_BAD)

    log("", HUE_INFO)
    log("TEXT CELLS, top to bottom, with where they sit:", HUE_GOOD)
    for x, y, text in sorted(cells, key=lambda c: (c[1], c[0])):
        if text:
            log("  at %4d,%-4d  %s" % (x, y, text[:40]))

    log("", HUE_INFO)
    if ents:
        log("TEXT ENTRIES - what you can type into:", HUE_GOOD)
        for x, y, eid in sorted(ents, key=lambda e: (e[1], e[0])):
            label = nearest_label(cells, x, y)
            log("  entry %-4d at %4d,%-4d  %s" % (eid, x, y, label[:40]))
    else:
        log("No text entries - nothing on this window takes a typed amount.",
            HUE_WARN)

    amount, how = withdrawal_amount(strings, ents, cells)
    if amount:
        log("WITHDRAWAL AMOUNT reads %r (%s)." % (amount, how),
            HUE_GOOD if amount == "1" else HUE_WARN)
        if amount != "1":
            log("  Not 1. Anything that takes one stone at a time needs this "
                "set to 1 first.", HUE_WARN)
    else:
        log("WITHDRAWAL AMOUNT could not be read: %s" % how, HUE_WARN)

    # LAST, deliberately. The journal scrolls, and the buttons are the part
    # that matters - printing them first is how they end up off the top of the
    # screen by the time anyone reads the report.
    log("", HUE_INFO)
    log("BUTTONS THE SERVER DREW - the label on EACH side, nearest first:",
        HUE_GOOD)
    for x, y, bid, kind in sorted(btns, key=lambda b: (b[1], b[0])):
        (lt, lx), (rt, rx) = labels_beside(cells, x, y)
        log("  button %-6d at %4d,%-4d %s  left: %s   right: %s"
            % (bid, x, y, "tile" if kind == "buttontileart" else "    ",
               describe_side(lt, lx), describe_side(rt, rx)))

    log("", HUE_INFO)
    log("Window left open and untouched. Close it yourself.", HUE_GOOD)
    if write_report(layout, strings):
        log("FULL REPORT + RAW LAYOUT: %s" % REPORT_FILE, HUE_GOOD)


main()
