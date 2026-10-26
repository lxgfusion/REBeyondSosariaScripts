"""
HouseSignWatch - tell me when a house nearby is falling down.
==============================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

Run it and go about your business. Every few seconds it looks at the house
signs within range and reads each one's condition. A house that is

    Slightly Worn  /  Greatly Worn  /  In Danger Of Collapse

gets an alert: a coloured line in your journal with the house's name,
owner, coordinates and which way it is from you, a marker over the sign
itself, and a beep. The same line is appended to ALERT_LOG_FILE next to this
script, so you can find the house again after you have moved on - that is
the list to add to your Account Runebook from.

Each sign is alerted ONCE per run, and again only if it gets worse.

WHERE THE CONDITION COMES FROM - ServUO Scripts/Multis/HouseSign.cs:

    tooltip      "Condition: This structure is slightly worn."
                 (cliloc 1062028 carrying 1043009 + the decay level)
    single-click "This house is slightly worn."  (an overhead label)

The tooltip is read first. If it carries no condition the sign is
single-clicked and the journal read BY TIMESTAMP for its label - this
script never clears your journal.

SHOP SIGNS USE THE SAME GRAPHICS as house signs, so a sign only counts when
its tooltip says it is a house sign or names an owner.
"""

import os
import re
import time


# Printed as the first line at startup. Razor CACHES the loaded script even
# after the file changes - if this is not the version you expect, hit Reload
# in the Scripting tab.
SCRIPT_VERSION = "2026-10-26.1"


# =============================================================================
# CONFIG - WHAT TO ALERT ON
# =============================================================================

# Each row: (words looked for in the condition text, the label you see, and
# the ServUO cliloc of that condition - Razor sometimes shows a tooltip
# argument as "#1043011" rather than resolving it, so the number is matched
# too). Matched case-insensitively.
#
#   1043009 + DecayLevel, from BaseHouse.cs:
#     ageless 1043009, like new 1043010, slightly 1043011, somewhat 1043012,
#     fairly 1043013, greatly 1043014, in danger of collapsing 1043015
#
# "danger of collaps" catches both the tooltip's "in danger of collapsing"
# and anything a shard rewords to "collapse".
ALERT_CONDITIONS = [
    ("slightly worn",     "Slightly Worn",          1043011),
    ("greatly worn",      "Greatly Worn",           1043014),
    ("danger of collaps", "In Danger Of Collapse",  1043015),
]

# "Demolition Pending" (1062497) is past collapse - the house is already
# going. Off by default; you asked for the three above.
ALERT_DEMOLITION_PENDING = False


# =============================================================================
# CONFIG - SCANNING
# =============================================================================

# How far to look. The server only sends items within about 18 tiles (see
# CLAUDE.md), so a bigger number finds nothing more.
SCAN_RANGE = 18

# How often to look, and how long before a sign already read is read again.
# A house's condition changes over days, not seconds - re-reading every sign
# every scan would be a tooltip storm in a crowded neighbourhood.
SCAN_EVERY_MS = 2000
RECHECK_MS = 10 * 60 * 1000

# Ceiling on tooltip reads per scan, so walking into a dense housing area
# does not stall the script. The rest are picked up on the next scans.
MAX_READS_PER_SCAN = 12

# House sign graphics, from ServUO Scripts/Gumps/HouseGumpAOS.cs: the 54
# standard signs are 2980 + 2*i, plus the library (2966) and beekeeper
# (3140) signs. Both facings of each (the odd id beside it) are included.
# Add to this if your shard has custom signs.
SIGN_GRAPHICS = sorted(set(
    [2980 + 2 * i for i in range(54)] + [2981 + 2 * i for i in range(54)]
    + [2966, 2967, 3140, 3141]))

# What makes a sign a HOUSE sign rather than a shop sign, read from its
# tooltip. ServUO: "A House Sign" (1061638) and "Owner: ..." (1061640).
HOUSE_SIGN_WORDS = ["house sign", "owner:"]

# Single-click the sign when its tooltip carries no condition.
SINGLE_CLICK_FALLBACK = True
SINGLE_CLICK_WAIT_MS = 800

# ---------------------------------------------------------------------------
# HOW YOU ARE TOLD
# ---------------------------------------------------------------------------
ALERT_BEEP = True
ALERT_OVERHEAD = True                # a marker over the sign itself
ALERT_LOG_FILE = "house_alerts.txt"  # next to this script; "" = no file

# Also print signs that are fine, once each - useful to confirm it is reading
# signs at all. Off once you trust it.
REPORT_EVERY_SIGN = False

DEBUG = False

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_ALERT = 0x0026                   # bright red


# =============================================================================
# SERVER STRINGS  (ServUO Scripts/Multis/HouseSign.cs)
# =============================================================================

MSG_CONDITION = "condition:"                      # 1062028, the tooltip line
MSG_CLICK_LABEL = "this house is"                 # OnSingleClick's LabelTo
MSG_DEMOLITION = "demolition pending"             # 1062497
CLILOC_DEMOLITION = 1062497


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Houses] " + text, hue, False)


def debug(text, hue=HUE_INFO):
    if DEBUG:
        log(text, hue)


def tidy(text):
    """Lowered, with tooltip properties that arrive run together split apart.

    Tooltip lines can arrive concatenated - "Owner: BobCondition: This ..."
    - and "bobcondition" has no word boundary. A space at each lower/digit ->
    upper seam first (CLAUDE.md).
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(text or ""))
    return " ".join(spaced.split()).lower()


def journal_mark():
    """Newest journal timestamp now. Lines after it are new."""
    newest = 0.0
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            if entry.Timestamp > newest:
                newest = entry.Timestamp
    except Exception:
        pass
    return newest


def journal_since(mark):
    """[(text, serial)] of journal lines newer than `mark`. Never clears."""
    out = []
    try:
        for entry in Journal.GetJournalEntry(mark) or []:
            if entry.Timestamp > mark:
                out.append((str(entry.Text or ""), int(entry.Serial or 0)))
    except Exception:
        pass
    return out


def compass(dx, dy):
    """Which way a point is from you. X grows east, Y grows south."""
    ns = "N" if dy < 0 else ("S" if dy > 0 else "")
    ew = "E" if dx > 0 else ("W" if dx < 0 else "")
    return (ns + ew) or "here"


# =============================================================================
# READING A SIGN
# =============================================================================

def sign_tooltip(item):
    """The sign's tooltip as one tidy string. "" if it will not load."""
    try:
        Items.WaitForProps(item, 1500)
        lines = list(Items.GetPropStringList(item) or [])
    except Exception:
        lines = []
    name = ""
    try:
        name = item.Name or ""
    except Exception:
        pass
    return tidy(name + " | " + " | ".join(str(l or "") for l in lines))


def is_house_sign(text):
    """A house sign, not a shop sign that shares the graphic."""
    return any(word in text for word in HOUSE_SIGN_WORDS)


def condition_of(text):
    """(label, severity) for an alerting condition in `text`, or None.

    `text` is tidy() output - a tooltip, or a single-click label. Severity is
    the row's place in ALERT_CONDITIONS, so "worse" can be told from
    "different".
    """
    if not text:
        return None
    if ALERT_DEMOLITION_PENDING and (MSG_DEMOLITION in text
                                     or ("#%d" % CLILOC_DEMOLITION) in text):
        return ("Demolition Pending", len(ALERT_CONDITIONS))
    for rank, (words, label, cliloc) in enumerate(ALERT_CONDITIONS):
        if words in text or ("#%d" % cliloc) in text:
            return (label, rank)
    return None


def has_condition_line(text):
    """Did the tooltip say anything about condition at all?

    An "ageless" house has no Condition line (HouseSign.GetProperties skips
    it), so its absence is not proof of anything - it only means the
    single-click is worth asking.
    """
    return MSG_CONDITION in text or MSG_DEMOLITION in text


def field(text, label):
    """The value of "label: value" in a tidy tooltip, or "".

    Lines are joined with " | ", so the value ends at the next bar.
    """
    found = re.search(re.escape(label) + r"\s*:\s*([^|]*)", text)
    if not found:
        return ""
    return found.group(1).strip()


def click_label(item):
    """Single-click the sign and return its overhead label, tidied. "" if
    none came. Read by timestamp; the journal is not cleared."""
    mark = journal_mark()
    try:
        Items.SingleClick(item)
    except Exception:
        return ""
    deadline = time.time() + SINGLE_CLICK_WAIT_MS / 1000.0
    serial = int(item.Serial)
    while time.time() < deadline:
        Misc.Pause(100)
        for text, who in journal_since(mark):
            low = tidy(text)
            if MSG_CLICK_LABEL in low and (who == serial or who == 0):
                return low
    return ""


def read_sign(item):
    """{"house", "name", "owner", "condition", "rank"} for one sign, or None
    when it is not a house sign. condition/rank are None when it is fine."""
    text = sign_tooltip(item)
    if not text or not is_house_sign(text):
        return None
    info = {
        "name": field(text, "name") or "(unnamed)",
        "owner": field(text, "owner") or "?",
        "condition": None,
        "rank": None,
    }
    found = condition_of(text)
    if found is None and not has_condition_line(text) and SINGLE_CLICK_FALLBACK:
        found = condition_of(click_label(item))
    if found is not None:
        info["condition"], info["rank"] = found
    return info


# =============================================================================
# SCANNING
# =============================================================================

# serial -> {"read_at": time, "rank": worst rank alerted, or None}
_seen = {}


def signs_in_range():
    """House-sign-graphic items on the ground within SCAN_RANGE, nearest
    first. Shop signs come back too - read_sign() weeds them out."""
    try:
        f = Items.Filter()
        f.Enabled = True
        f.OnGround = 1
        f.RangeMax = SCAN_RANGE          # never leave this unset
        for graphic in SIGN_GRAPHICS:
            f.Graphics.Add(graphic)
        found = list(Items.ApplyFilter(f) or [])
    except Exception as err:
        log("sign scan failed: %r" % (err,), HUE_WARN)
        return []
    try:
        found.sort(key=lambda i: Player.DistanceTo(i))
    except Exception:
        pass
    return found


def due(serial, now):
    """Is this sign due a (re)read?"""
    rec = _seen.get(serial)
    return rec is None or (now - rec["read_at"]) * 1000.0 >= RECHECK_MS


def should_alert(serial, rank):
    """Alert on a sign at this rank? Once per sign, again only when worse."""
    if rank is None:
        return False
    rec = _seen.get(serial)
    if rec is None or rec.get("rank") is None:
        return True
    return rank > rec["rank"]


def write_log_line(line):
    if not ALERT_LOG_FILE:
        return
    try:
        folder = Misc.CurrentScriptDirectory()
    except Exception:
        folder = ""
    path = os.path.join(folder, ALERT_LOG_FILE) if folder else ALERT_LOG_FILE
    try:
        with open(path, "a") as fh:
            fh.write(line + "\n")
    except Exception as err:
        log("could not write %s: %r" % (path, err), HUE_WARN)


def alert(item, info):
    x, y = int(item.Position.X), int(item.Position.Y)
    dx = x - int(Player.Position.X)
    dy = y - int(Player.Position.Y)
    try:
        gap = int(Player.DistanceTo(item))
    except Exception:
        gap = max(abs(dx), abs(dy))
    try:
        facet = int(Player.Map)
    except Exception:
        facet = -1

    log("*** %s *** '%s' (owner %s) at %d,%d map %d - %d tiles %s of you."
        % (info["condition"].upper(), info["name"], info["owner"], x, y,
           facet, gap, compass(dx, dy)), HUE_ALERT)
    if ALERT_OVERHEAD:
        try:
            Items.Message(item, HUE_ALERT, info["condition"])
        except Exception:
            pass
    if ALERT_BEEP:
        try:
            Misc.Beep()
        except Exception:
            pass
    write_log_line("%s\t%s\t%s\towner %s\t%d,%d\tmap %d"
                   % (time.strftime("%Y-%m-%d %H:%M"), info["condition"],
                      info["name"], info["owner"], x, y, facet))


def scan_once():
    """One pass over the signs in range. How many alerts it raised."""
    now = time.time()
    raised = 0
    reads = 0
    for item in signs_in_range():
        try:
            serial = int(item.Serial)
        except Exception:
            continue
        if not due(serial, now):
            continue
        if reads >= MAX_READS_PER_SCAN:
            break
        reads += 1

        info = read_sign(item)
        if info is None:
            # A shop sign, or a tooltip that would not load. Remember it so
            # it is not re-read every scan.
            _seen[serial] = {"read_at": now,
                             "rank": (_seen.get(serial) or {}).get("rank")}
            debug("0x%X is not a house sign." % serial)
            continue

        if should_alert(serial, info["rank"]):
            alert(item, info)
            raised += 1
        elif info["rank"] is None and REPORT_EVERY_SIGN \
                and serial not in _seen:
            log("  '%s' (owner %s) is fine." % (info["name"], info["owner"]),
                HUE_GOOD)

        prev = (_seen.get(serial) or {}).get("rank")
        worst = info["rank"] if prev is None else max(
            prev, info["rank"] if info["rank"] is not None else prev)
        _seen[serial] = {"read_at": now, "rank": worst}
    return raised


# =============================================================================
# MAIN
# =============================================================================

def main():
    log("HouseSignWatch v%s" % SCRIPT_VERSION, HUE_GOOD)
    wanted = [label for _w, label, _c in ALERT_CONDITIONS]
    if ALERT_DEMOLITION_PENDING:
        wanted.append("Demolition Pending")
    log("Watching house signs within %d tiles for: %s"
        % (SCAN_RANGE, ", ".join(wanted)), HUE_GOOD)
    if ALERT_LOG_FILE:
        log("Alerts are also written to %s next to this script."
            % ALERT_LOG_FILE)

    total = 0
    while True:
        if Player.IsGhost:
            log("You are dead - stopping.", HUE_BAD)
            break
        total += scan_once()
        Misc.Pause(SCAN_EVERY_MS)


main()
