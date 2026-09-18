"""
Dump a storage key's gump: every button it DREW, and what sits beside it.
========================================================================

For Razor Enhanced (IronPython 3.4). It opens the container and reads. It does
NOT press anything, move anything or type anything.

WHY THIS EXISTS
---------------
A recorded macro for withdrawing one granite disconnected the client
immediately:

    Items.UseItem(0x4017817A)
    Gumps.WaitForGump(0x6abce12, 10000)
    Gumps.SendAdvancedAction(0x6abce12, 21, [], [0], ["1"])
    Gumps.WaitForGump(0x6abce12, 10000)      <- the gump is GONE by now
    Gumps.SendAction(0x6abce12, 1)           <- answering a window that closed

Answering a gump the client no longer has open is one of the reliable ways to
be dropped, and so is pressing a button the server did not draw. The recorder
captures what you clicked, not whether the window was still there when the next
line ran - so a macro that worked by hand can be fatal on replay.

Gump 0x6ABCE12 is not new here either. resource_order_runner.py calls it
BOOK_GUMP and harvest_runner.py calls it HOUSE_DEPOSIT_GUMP: it is the shared
"stash" window every storage key on this shard opens. On the Resource Order
Book the buttons are 1, 3, 4, 5 and 8 - so a granite key drawing a button 21
means it draws MORE of them, and which ones is exactly what nobody has written
down.

This writes it down.

USAGE
-----
Run it and target the storage key. Read the report, then tell it to the script
you are building - do not guess a button from this list's neighbours, because
the numbering is per-container and this only proves what THIS one drew.
"""

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

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
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


def buttons(gump_id):
    """(x, y, id) for every button the server DREW."""
    out = []
    for el in elements(raw_layout(gump_id)):
        if el["kind"] == "button" and len(el["nums"]) >= 3:
            out.append((el["nums"][0], el["nums"][1], el["nums"][-1]))
    return out


def entries(gump_id):
    """(x, y, entry_id) for every text entry - one per thing you can type in."""
    out = []
    for el in elements(raw_layout(gump_id)):
        if el["kind"] == "textentry" and len(el["nums"]) >= 6:
            out.append((el["nums"][0], el["nums"][1], el["nums"][5]))
    return out


def nearest_label(cells, x, y):
    """The text on this button's row, preferring whatever sits to its right."""
    row = [(cx, text) for cx, cy, text in cells
           if abs(cy - y) <= LABEL_ROW_TOLERANCE and text]
    if not row:
        return ""
    right = sorted((cx, t) for cx, t in row if cx >= x)
    if right:
        return right[0][1]
    return sorted(row)[-1][1]


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
    log("BUTTONS THE SERVER DREW - pressing any other one disconnects you:",
        HUE_GOOD)
    for x, y, bid in sorted(btns, key=lambda b: (b[1], b[0])):
        label = nearest_label(cells, x, y)
        log("  button %-6d at %4d,%-4d  %s" % (bid, x, y, label[:40]))

    log("", HUE_INFO)
    if ents:
        log("TEXT ENTRIES - what you can type into:", HUE_GOOD)
        for x, y, eid in sorted(ents, key=lambda e: (e[1], e[0])):
            label = nearest_label(cells, x, y)
            log("  entry %-4d at %4d,%-4d  %s" % (eid, x, y, label[:40]))
        log("  On this window entry 0 has always been the WITHDRAWAL AMOUNT. "
            "A number typed there plus a button pulls that many OUT.", HUE_WARN)
    else:
        log("No text entries - nothing on this window takes a typed amount.",
            HUE_WARN)

    log("", HUE_INFO)
    log("EVERY STRING, in layout order:", HUE_GOOD)
    for i, text in enumerate(strings[:40]):
        text = str(text or "").strip()
        if text:
            log("  %2d  %s" % (i, text[:60]))

    log("", HUE_INFO)
    log("Leaving the window open and untouched. Close it yourself.", HUE_GOOD)


main()
