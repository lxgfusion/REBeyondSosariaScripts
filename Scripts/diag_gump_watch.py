"""
Watch what Razor thinks is open, while you watch the screen.
============================================================

For Razor Enhanced (IronPython 3.4). It reads. It NEVER presses, closes,
types or moves anything - which matters here, because the thing being
investigated is windows that will not close.

WHY THIS EXISTS
---------------
The resource order runner leaves a screen stacked with windows: the order
list piles up while paging, and a client restart clears it. Two different
things could produce that, and they need different fixes:

  A. THE CLIENT still has windows the script believes it closed.
  B. RAZOR still lists gumps that are no longer on screen - "ghosts" - and
     the script talks to one of those instead of the real window.

B is real and provable from Razor's own source (v1.0.0.12):

  * `Gumps.HasGump(id)` and `Gumps.AllGumpIDs()` both just ask whether the
    id is a key in `m_incomingData`. Three things remove a key: the script
    pressing that gump, the client sending a gump response (which is what a
    right-click close does), and the SERVER's close-gump packet.
  * That last one is broken. `ExtendedPacket` in `Razor/Network/Handlers.cs`
    is the server-to-client viewer for 0xBF, and its close-gump case reads
    the dialog id and button with `ReadUInt16()` - but the packet carries
    two 32-bit fields. It removes a key built from half of the wrong field,
    so the real entry stays for the rest of the session.

So a window YOU close should vanish from Razor's list, while one the SERVER
closes or replaces should linger. Both are worth seeing, and the difference
is the answer.

WHAT TO DO
----------
1. Start this.
2. While it runs:
     - open a window (a storage key, [AR, the order book)
     - close it BY HAND
     - then run whatever is misbehaving, e.g. the order runner
3. Stop it, or let it run out, and send the file it names on its last line.

WHAT THE ANSWER LOOKS LIKE
--------------------------
    a hand-closed window still listed
        -> ghosts on every path; a script cannot trust HasGump at all

    a hand-closed window drops, but ids pile up while paging and never go
        -> the server-close path is the leak, which is (B) and is ours to
           work around: the runner caches the order list's id and only
           re-finds it when HasGump says it has gone, which it never does

    ids come and go cleanly, one window at a time, while the screen still
    fills up
        -> Razor is right and the windows are the client's or the shard's (A)
"""

import os
import re
import time


SCRIPT_VERSION = "2026-09-30.1"


# =============================================================================
# CONFIG
# =============================================================================

# How long to watch, and how often to look. 0 seconds means "until you stop
# the script" - the report is written as it goes, so stopping loses nothing.
WATCH_SECONDS = 600
POLL_MS = 1000

# A census line every so often, even when nothing changed, so the log shows
# the count growing rather than only the individual events.
CENSUS_EVERY_S = 30

# Where the report goes. Overwritten every run.
REPORT_FILE = os.path.join(os.environ.get("TEMP", "."), "gump_watch.txt")

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

_report = []
_started = [0.0]


def stamp():
    return "%6.1fs" % (time.time() - _started[0])


def log(text, hue=HUE_INFO):
    line = "%s  %s" % (stamp(), text)
    _report.append(line)
    Misc.SendMessage("[GumpWatch] " + text, hue, False)
    flush()


def flush():
    """Write after every line. A script that is stopped by hand - which is how
    this one is meant to end - never reaches a tidy finish."""
    try:
        with open(REPORT_FILE, "w") as fh:
            fh.write("\n".join(_report) + "\n")
    except Exception:
        pass


def gump_lines(gump_id):
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


def open_ids():
    try:
        return [int(g) for g in (Gumps.AllGumpIDs() or [])]
    except Exception as err:
        log("could not list gumps: %r" % err, HUE_BAD)
        return []


def describe(gump_id):
    """A one-line fingerprint: the first couple of strings, and any "(n/m)"
    page marker, which is what tells two pages of one list apart."""
    lines = [str(l or "").strip() for l in gump_lines(gump_id)]
    lines = [l for l in lines if l]
    page = ""
    for line in lines:
        found = re.search(r"\(\s*\d+\s*/\s*\d+\s*\)", line)
        if found:
            page = "  page " + found.group(0)
            break
    return (" | ".join(lines[:3]))[:70] + page


def main():
    _started[0] = time.time()
    log("gump watch v%s - reading only, nothing is pressed or closed."
        % SCRIPT_VERSION, HUE_GOOD)
    log("open a window and CLOSE IT BY HAND. If this does not report it gone, "
        "Razor is keeping ghosts and a script cannot trust HasGump.", HUE_WARN)

    known = {}
    for gump_id in open_ids():
        known[gump_id] = describe(gump_id)
        log("already open  0x%X  %s" % (gump_id, known[gump_id]))
    log("%d gump(s) open to start with." % len(known), HUE_GOOD)

    ever = set(known)
    deadline = time.time() + WATCH_SECONDS if WATCH_SECONDS else 0
    next_census = time.time() + CENSUS_EVERY_S

    while True:
        if deadline and time.time() >= deadline:
            break
        Misc.Pause(POLL_MS)

        now = {}
        for gump_id in open_ids():
            now[gump_id] = known.get(gump_id) or describe(gump_id)

        for gump_id in sorted(now):
            if gump_id not in known:
                ever.add(gump_id)
                log("APPEARED  0x%X  %s" % (gump_id, now[gump_id]), HUE_WARN)
        for gump_id in sorted(known):
            if gump_id not in now:
                log("gone      0x%X  %s" % (gump_id, known[gump_id]), HUE_GOOD)
        known = now

        if time.time() >= next_census:
            next_census = time.time() + CENSUS_EVERY_S
            log("census: Razor lists %d gump(s); %d different id(s) seen so "
                "far. %s" % (len(known), len(ever),
                             ", ".join("0x%X" % g for g in sorted(known))[:90]))

    log("", HUE_INFO)
    log("watched %d gump id(s) in total; Razor still lists %d."
        % (len(ever), len(known)), HUE_GOOD)
    log("If a window you closed by hand is still in that list, Razor is "
        "keeping ghosts - HasGump means 'seen', not 'on screen'.", HUE_WARN)
    log("REPORT: %s" % REPORT_FILE, HUE_GOOD)
    flush()


main()
