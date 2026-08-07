"""
Account Runebook (AR) gump diagnostic.
======================================

Run this when the mining script cannot navigate folders or switch pages.

It opens the AR gump, dumps everything Razor can see about it, and writes the
result to a text file you can paste back. Nothing is clicked except the optional
page-advance probe at the end.

This runebook has already been mapped - see docs/account-runebook-gump.md.
Known good values, which mining_runner.py now uses:

    504  page forward       503  page back       5  back to root
    server-side paging, 9 entries per page, "Page X/Y" footer

Re-run this only if the runebook changes or those stop working.

The question it answers: does the gump use CLIENT-SIDE pages (all pages already
present in one gump, switched without touching the server) or SERVER-SIDE pages
(a button that asks the server for the next page)? `{ page N }` markers in the
raw layout mean client-side. This one is server-side.

Output file: %TEMP%\\ar_gump_dump.txt (path is printed when it finishes).
"""

import os
import re


AR_COMMAND = "[ar"
AR_GUMPID = 0xc395adb4
OPEN_TIMEOUT = 10000

# --------------------------------------------------------------------------
# PAGE PROBE - OFF BY DEFAULT, AND DELIBERATELY SO.
#
# Probing means clicking buttons whose meaning is unknown, in a RUNEBOOK. One of
# them could recall you across the map, drop a rune, or charge a charge. Read the
# layout dump first: if it shows `{ page N }` markers the answer is already
# there and you never need to click anything.
#
# Only set PROBE_PAGES = True if the dump was inconclusive, and do it somewhere
# safe - not mid-route, not carrying a full load.
# --------------------------------------------------------------------------
PROBE_PAGES = False
PROBE_NEXT_BUTTONS = [1, 2, 3, 4, 6, 7, 8, 9]

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "ar_gump_dump.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

_lines = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[AR] " + text, hue, False)
    _lines.append(text)


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Compatibility shims - both of these signatures changed in Razor Enhanced.
# ---------------------------------------------------------------------------

def chat_say(text):
    """Player.ChatSay(colour, msg) is current; older builds took just msg."""
    try:
        Player.ChatSay(0, text)
        return "ChatSay(colour, msg)"
    except TypeError:
        Player.ChatSay(text)
        return "ChatSay(msg)"


def gump_lines(gump_id, data_only=False):
    """Gumps.GetLineList(gumpId, dataOnly) is current; older builds took 1 arg."""
    try:
        return list(Gumps.GetLineList(gump_id, data_only)), "GetLineList(id, bool)"
    except TypeError:
        return list(Gumps.GetLineList(gump_id)), "GetLineList(id)"


def has_gump(gump_id):
    try:
        return Gumps.HasGump(gump_id)
    except TypeError:
        return Gumps.HasGump() and Gumps.CurrentGump() == gump_id


def open_ar():
    if has_gump(AR_GUMPID):
        return True, "already open"
    form = chat_say(AR_COMMAND)
    ok = Gumps.WaitForGump(AR_GUMPID, OPEN_TIMEOUT)
    Misc.Pause(300)
    return bool(ok) or has_gump(AR_GUMPID), form


def buttons_from_layout(layout):
    """Button ids the old parser would find, plus every raw button line."""
    ids = []
    raw = []
    for piece in re.split(r"\}\s*\{", layout or ""):
        if "button" in piece.lower():
            raw.append(piece.strip())
            nums = re.findall(r"-?\d+", piece)
            if nums:
                ids.append(int(nums[-1]))
    return ids, raw


def dump_layout(layout):
    rule("raw layout")
    if not layout:
        log("EMPTY - GetGumpRawLayout returned nothing.", HUE_BAD)
        return
    log("length: %d chars" % len(layout), HUE_INFO)

    pages = re.findall(r"\{\s*page\s+(\d+)\s*\}", layout, re.I)
    if pages:
        log("PAGE MARKERS FOUND: %s" % ", ".join(pages), HUE_GOOD)
        log("-> client-side paging: every page is already in this one gump.",
            HUE_GOOD)
    else:
        log("No { page N } markers -> server-side paging (a button fetches "
            "the next page), or a single-page gump.", HUE_WARN)

    # The message window truncates; the file gets the whole thing.
    _lines.append("--- full layout ---")
    _lines.append(layout)
    for piece in re.split(r"\}\s*\{", layout)[:40]:
        Misc.SendMessage("[AR] layout: %s" % piece.strip()[:150], HUE_INFO, False)


def snapshot():
    """Everything identifying the current page, for change detection."""
    layout = ""
    try:
        layout = Gumps.GetGumpRawLayout(AR_GUMPID)
    except Exception as err:
        log("GetGumpRawLayout failed: %s" % err, HUE_BAD)
    text, _form = gump_lines(AR_GUMPID)
    ids, _raw = buttons_from_layout(layout)
    return layout, text, ids


def main():
    rule("account runebook gump diagnostic")

    ok, form = open_ar()
    log("open: %s (via %s)" % ("yes" if ok else "NO", form),
        HUE_GOOD if ok else HUE_BAD)
    if not ok:
        log("The gump never appeared. If the shim above says ChatSay(colour,msg) "
            "then the command '%s' itself is not opening it." % AR_COMMAND, HUE_BAD)
        write_file()
        return

    log("CurrentGump: 0x%X   expected: 0x%X" % (Gumps.CurrentGump(), AR_GUMPID),
        HUE_INFO)

    layout, text, ids = snapshot()

    dump_layout(layout)

    rule("line list")
    lines, form = gump_lines(AR_GUMPID)
    log("via %s, %d lines" % (form, len(lines)), HUE_INFO)
    for i, line in enumerate(lines):
        log("  [%d] %s" % (i, line), HUE_INFO)

    rule("line list (dataOnly=True)")
    try:
        data, _f = gump_lines(AR_GUMPID, True)
        log("%d entries" % len(data), HUE_INFO)
        for i, line in enumerate(data):
            log("  [%d] %s" % (i, line), HUE_INFO)
    except Exception as err:
        log("not available: %s" % err, HUE_WARN)

    rule("buttons")
    log("ids (last number of each button line): %s"
        % ", ".join(str(b) for b in sorted(set(ids))), HUE_INFO)
    waypoints = sorted(b - 30000 for b in ids if 30000 < b < 60000)
    log("gate/waypoint buttons (id-30000): %s"
        % (", ".join(str(w) for w in waypoints) or "none"), HUE_INFO)

    if not PROBE_PAGES:
        rule("page probe skipped")
        log("PROBE_PAGES is off. If the layout above showed { page N } markers, "
            "paging is client-side and no button is needed.", HUE_INFO)
        log("If it showed none and you have more entries than fit on a page, "
            "set PROBE_PAGES = True and rerun somewhere safe - it clicks unknown "
            "runebook buttons to find the page control.", HUE_WARN)
        write_file()
        return

    rule("page-advance probe")
    log("Clicking candidate buttons to see which one changes the page.", HUE_WARN)
    base_text = list(text)
    for candidate in PROBE_NEXT_BUTTONS:
        if candidate not in ids:
            continue
        Gumps.SendAction(AR_GUMPID, candidate)
        Gumps.WaitForGump(AR_GUMPID, OPEN_TIMEOUT)
        Misc.Pause(400)
        _l, new_text, _i = snapshot()
        if new_text != base_text:
            log("BUTTON %d CHANGED THE PAGE." % candidate, HUE_GOOD)
            log("  new first lines: %s" % " | ".join(new_text[:5]), HUE_INFO)
            log("  -> set AR_NEXT_BUTTONS = [%d] in the mining script."
                % candidate, HUE_GOOD)
            base_text = new_text
        else:
            log("button %d: no change" % candidate, HUE_INFO)

    write_file()


def write_file():
    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(_lines))
        Misc.SendMessage("[AR] Written to %s" % DUMP_PATH, HUE_GOOD, False)
    except Exception as err:
        Misc.SendMessage("[AR] Could not write dump file: %s" % err, HUE_BAD, False)


main()
