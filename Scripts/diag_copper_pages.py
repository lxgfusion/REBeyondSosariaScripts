"""
Resource Order Book - why Copper Ingots never fills.
====================================================

READ-ONLY. It filters the order list and pages through the result, recording
what the runner would have seen at each step. Nothing is withdrawn.

WHAT IT CLICKS
--------------
Book button 1 ("Resource Orders..."), list button 12 (submit the Name filter)
and list button 5 (Next Page). Nothing else, and `press()` refuses any other id
outside that allowlist - button 2 on that gump is PURGE and button 3 is "Fill
from backpack", both of which sit next to the ones used here.

THE QUESTION
------------
`resource_order_runner.py` reports "no Copper Ingots orders that fit" every run,
with 31 of them in the book and copper in the chest. Three explanations survive
a reading of the code and they need different fixes, so this tells them apart:

  A. NEXT PAGE RESETS TO PAGE 1. The runner presses Next with the Name filter
     text re-submitted (SendAdvancedAction). If the server reads any submission
     carrying filter text as "apply the filter", Next returns page 1 again and
     the scan reads the same page over and over. That would be invisible for
     every resource whose own rows land on page 1 and fatal only for Copper
     Ingots, whose 31 rows sit behind 101 "Dull Copper Ingots" ones.

  B. THE PAGE IS READ BEFORE IT ARRIVES. Gumps.WaitForGump returns True at once
     for a gump that is already open, and the server answers these buttons by
     replacing the list under the SAME id. The runner waits on the id plus a
     flat 600ms, so under lag it can read the PREVIOUS page. Phase 1 measures
     this directly: it takes a fingerprint at the moment the runner would read,
     and again afterwards.

  C. NEITHER - the pages are walked correctly and the orders are simply being
     rejected. Then the cause is the budget or the lap order, not the gump, and
     the amounts printed here say which.

Phase 2 runs ONLY if phase 1 gets stuck on page 1. It re-filters and presses
Next as a plain SendAction, which submits the text entries empty. If the counter
then advances, the filter text on the press was what reset it - hypothesis A,
confirmed. If it still sticks, Next itself is not working the way the runner
assumes.

OUTPUT
------
The journal, and %TEMP%\\ro_copper_pages.txt with the full per-page detail. The
verdict is printed at the end of both.

HOW LONG
--------
Under a minute. Copper's filtered result should be about nine pages.
"""

import os
import re
import time


# Printed as the first log line. If the journal does not show this, Razor is
# running a cached copy - Reload in the Scripting tab.
SCRIPT_VERSION = "2026-07-30.2"


# =============================================================================
# CONFIG
# =============================================================================

# The resource to investigate, spelled as the BOOK spells it, and the name that
# dilutes it. Both are only defaults - point them at any colliding pair.
TERM = "Copper Ingots"
COLLIDES_WITH = "Dull Copper Ingots"

# PHASE 3. The runner does not reopen the book between resources - it re-submits
# the Name filter on a list that is still sitting on page N of the PREVIOUS
# resource's result. Phase 3 reproduces that: filter for DECOY, page in
# DECOY_PAGES times, then filter for TERM and see which page it lands on.
DECOY_TERM = "Dull Copper Ingots"
DECOY_PAGES = 3

# "Resource Order Book", ItemID 0x2259, hue 0x04F7, locked down on the ground.
BOOK_SERIAL = 0x404AC332
BOOK_ID = 0x2259
BOOK_HUE = 0x04F7
WORLD_RANGE = 4

BOOK_GUMP = 0x06ABCE12
BOOK_ORDERS_BUTTON = 1          # "Resource Orders..."

ORDERS_GUMP = 0xB2F21F1A
ORDERS_NEXT_BUTTON = 5          # "Next Page"
ORDERS_TEXT_IDS = [0, 1, 2, 3, 4]
ORDERS_SEARCH_ENTRY = 0
ORDERS_FILTER_SUBMIT = 12

# Nothing else may be pressed. Button 2 is Purge and 3 is "Fill from backpack";
# 100+ are the row buttons, which WITHDRAW an order.
PRESSABLE = (BOOK_ORDERS_BUTTON, ORDERS_NEXT_BUTTON, ORDERS_FILTER_SUBMIT)

# Safety ceiling. Copper's result should be ~9 pages; the deepest collision in
# the table (Amber + Brilliant Amber) is ~21.
MAX_PAGES = 30

# Stop early once this many consecutive pages have come back identical. That is
# hypothesis A and there is no point walking thirty of them.
STUCK_PAGES_BEFORE_GIVING_UP = 3

GUMP_TIMEOUT_MS = 10000

# The runner's own wait, reproduced exactly - this is the point at which it
# reads the page, and moving it would hide hypothesis B.
SETTLE_MS = 600

# How much LONGER to watch for the page to change after that read, and how
# often to look. Purely diagnostic: it measures how late the page was.
LATE_TIMEOUT_MS = 4000
POLL_MS = 100

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "ro_copper_pages.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

REPORT = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[COPPER] " + str(text), hue, False)
    REPORT.append(str(text))


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Compatibility shims - same as the runner's
# ---------------------------------------------------------------------------

def gump_lines(gump_id, data_only=False):
    try:
        return list(Gumps.GetLineList(gump_id, data_only))
    except TypeError:
        return list(Gumps.GetLineList(gump_id))


def has_gump(gump_id):
    try:
        return bool(Gumps.HasGump(gump_id))
    except TypeError:
        return bool(Gumps.HasGump()) and Gumps.CurrentGump() == gump_id


def raw_layout(gump_id):
    try:
        return Gumps.GetGumpRawLayout(gump_id) or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Parsing - copied from resource_order_runner.py so this reads the page EXACTLY
# as the runner does. Do not "improve" these here; a difference would make the
# diagnosis describe a script nobody is running.
# ---------------------------------------------------------------------------

ROW_FLAGS = ("yes", "no", "none", "")
HEADER_LABELS = ("name", "amt to gather", "amt gathered", "value per",
                 "completed")
FOOTER_FIRST = ("previous page", "next page")


def layout_elements(layout):
    out = []
    for piece in re.findall(r"\{([^{}]*)\}", layout or ""):
        piece = piece.strip()
        if not piece:
            continue
        out.append({"kind": piece.split()[0].lower(),
                    "nums": [int(n) for n in re.findall(r"-?\d+", piece)]})
    return out


def row_buttons(layout, x_max=60, y_min=80, y_max=400):
    found = []
    for el in layout_elements(layout):
        if el["kind"] != "button" or len(el["nums"]) < 3:
            continue
        x, y, button = el["nums"][0], el["nums"][1], el["nums"][-1]
        if x <= x_max and y_min <= y <= y_max:
            found.append((y, button))
    return [b for _y, b in sorted(found)]


def parse_order_rows(strings, anchor=None):
    lowered = [(s or "").strip().lower() for s in strings]
    start = 0
    for label in HEADER_LABELS:
        if label in lowered:
            start = max(start, lowered.index(label) + 1)
    end = len(strings)
    for footer in FOOTER_FIRST:
        if footer in lowered:
            end = min(end, lowered.index(footer))

    rows = []
    for value in strings[start:end]:
        text = (value or "").strip()
        low = text.lower()

        if anchor is not None:
            starts_row = anchor in low
        else:
            starts_row = (low not in ROW_FLAGS
                          and not re.match(r"^-?[\d,]+$", text)
                          and bool(re.search(r"[A-Za-z]", text)))

        if starts_row:
            rows.append({"name": re.sub(r"\s+", " ", text), "amount": None})
            continue
        if re.match(r"^-?[\d,]+$", text) and rows and rows[-1]["amount"] is None:
            rows[-1]["amount"] = int(text.replace(",", ""))
    return rows


def page_counter(strings):
    for value in strings:
        match = re.search(r"\((\d+)\s*/\s*(\d+)\)", value or "")
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def parse_header(strings):
    info = {}
    for line in strings:
        match = re.search(r"Contents:\s*(\d+)\s*/\s*(\d+)", line or "")
        if match:
            info["stored"] = int(match.group(1))
            info["capacity"] = int(match.group(2))
        match = re.search(r"Displayed:\s*(\d+)", line or "")
        if match:
            info["displayed"] = int(match.group(1))
    return info


# ---------------------------------------------------------------------------
# The book
# ---------------------------------------------------------------------------

def find_book():
    if BOOK_SERIAL:
        item = Items.FindBySerial(BOOK_SERIAL)
        if item is not None:
            return item
        log("serial 0x%X did not resolve, trying id/hue." % BOOK_SERIAL,
            HUE_WARN)
    try:
        found = list(Items.FindAllByID(BOOK_ID, BOOK_HUE, -1, WORLD_RANGE,
                                       False) or [])
    except Exception as err:
        log("FindAllByID failed: %s" % err, HUE_BAD)
        return None
    if not found:
        return None
    found.sort(key=lambda it: Player.DistanceTo(it))
    return found[0]


def open_list():
    book = find_book()
    if book is None:
        log("Resource Order Book not found within %d tiles - stand next to it."
            % WORLD_RANGE, HUE_BAD)
        return False

    # WaitForGump returns True for a gump that is already open, so any leftover
    # window has to go before the one we want is requested.
    Gumps.CloseGump(BOOK_GUMP)
    Gumps.CloseGump(ORDERS_GUMP)
    Misc.Pause(SETTLE_MS)

    Items.UseItem(book)
    Gumps.WaitForGump(BOOK_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    if not has_gump(BOOK_GUMP):
        log("The book's window never opened.", HUE_BAD)
        return False

    Gumps.SendAction(BOOK_GUMP, BOOK_ORDERS_BUTTON)
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    if not has_gump(ORDERS_GUMP):
        log("The order list never opened.", HUE_BAD)
        return False
    return True


def fingerprint():
    """Something about the list that changes when the server replaces it."""
    try:
        return tuple(gump_lines(ORDERS_GUMP))
    except Exception:
        return ()


def digest(fp):
    """A short, stable label for a fingerprint, for reading in the journal."""
    return "%05d" % (abs(hash(fp)) % 100000) if fp else "-----"


def press(button, filter_text=None):
    """Press a button and report what the runner would have seen.

    Returns a dict:
        "ok"        the list is still open
        "stale"     the content had NOT changed by the time the runner reads
        "late_ms"   how much longer it took to change after that (None = never)

    `filter_text=None` sends a plain SendAction, which submits the text entries
    EMPTY and therefore clears the Name filter. That is phase 2's experiment,
    never phase 1's.
    """
    if button not in PRESSABLE:
        log("REFUSING to press button %d - not in the allowlist %s."
            % (button, list(PRESSABLE)), HUE_BAD)
        return {"ok": False, "stale": False, "late_ms": None}

    before = fingerprint()

    if filter_text is None:
        Gumps.SendAction(ORDERS_GUMP, button)
    else:
        ids = list(ORDERS_TEXT_IDS)
        values = [filter_text if i == ORDERS_SEARCH_ENTRY else "" for i in ids]
        try:
            Gumps.SendAdvancedAction(ORDERS_GUMP, button, [], ids, values)
        except Exception as err:
            log("SendAdvancedAction failed (%s) - the filter would be lost."
                % err, HUE_BAD)
            Gumps.SendAction(ORDERS_GUMP, button)

    # The runner's wait, exactly. It reads the page at the end of this.
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)

    stale = has_gump(ORDERS_GUMP) and fingerprint() == before
    late_ms = 0 if not stale else None

    if stale:
        waited = 0
        while waited < LATE_TIMEOUT_MS:
            Misc.Pause(POLL_MS)
            waited += POLL_MS
            if not has_gump(ORDERS_GUMP):
                break
            if fingerprint() != before:
                late_ms = waited
                break

    return {"ok": has_gump(ORDERS_GUMP), "stale": stale, "late_ms": late_ms}


# ---------------------------------------------------------------------------
# Phase 1 - walk the filtered result the way the runner does
# ---------------------------------------------------------------------------

def describe_page(page, strings, layout, anchor, exact):
    """Log one page and return what was found on it."""
    rows = parse_order_rows(strings, anchor)
    buttons = row_buttons(layout)
    current, total = page_counter(strings)

    matches = []
    others = {}
    if len(rows) == len(buttons):
        for row, button in zip(rows, buttons):
            name = row["name"].strip()
            if exact.match(name):
                if row["amount"]:
                    matches.append({"name": name, "amount": row["amount"],
                                    "button": button})
            else:
                others[name] = others.get(name, 0) + 1

    log("page %s/%s  fp %s  %d row(s), %d button(s)%s"
        % (current if current is not None else "?",
           total if total is not None else "?",
           digest(tuple(strings)), len(rows), len(buttons),
           "  <-- ROWS AND BUTTONS DISAGREE" if len(rows) != len(buttons)
           else ""),
        HUE_BAD if len(rows) != len(buttons) else HUE_INFO)

    if len(rows) != len(buttons):
        # This is what the runner logs before throwing the page away. Naming
        # what is actually on it is the difference between "skipped a page" and
        # "was reading somebody else's list".
        loose = parse_order_rows(strings)
        log("    the page really holds: %s"
            % (", ".join(sorted(set(r["name"] for r in loose))[:6])
               or "nothing readable"), HUE_BAD)
    else:
        if matches:
            log("    %d %s order(s): %s" % (
                len(matches), TERM,
                ", ".join("x%d (button %d)" % (m["amount"], m["button"])
                          for m in matches[:6])), HUE_GOOD)
        if others:
            log("    also on the page: %s"
                % ", ".join("%s x%d" % (n, c)
                            for n, c in sorted(others.items(),
                                               key=lambda kv: -kv[1])[:4]))

    return {"page": page, "current": current, "total": total,
            "rows": len(rows), "buttons": len(buttons),
            "matches": matches, "others": others,
            "fp": tuple(strings)}


def walk(anchor, exact, restate_filter):
    """Page through the filtered list. Returns (pages, stuck, stale_reads).

    `restate_filter` False presses Next as a plain SendAction, which clears the
    Name filter - phase 2 only.
    """
    pages = []
    stuck = 0
    stale_reads = 0
    seen = {}

    for page in range(1, MAX_PAGES + 1):
        strings = gump_lines(ORDERS_GUMP)
        layout = raw_layout(ORDERS_GUMP)
        info = describe_page(page, strings, layout, anchor, exact)
        pages.append(info)

        fp = info["fp"]
        if fp in seen:
            stuck += 1
            log("    IDENTICAL to page %d - the list did not move."
                % seen[fp], HUE_BAD)
            if stuck >= STUCK_PAGES_BEFORE_GIVING_UP:
                log("%d identical pages in a row. Stopping." % stuck, HUE_BAD)
                break
        else:
            stuck = 0
            seen[fp] = page

        current, total = info["current"], info["total"]
        if total is None or current is None:
            log("no page counter on this page - cannot tell where we are.",
                HUE_WARN)
            break
        if current >= total:
            log("that was the last page (%d of %d)." % (current, total),
                HUE_GOOD)
            break

        result = press(ORDERS_NEXT_BUTTON, TERM if restate_filter else None)
        if not result["ok"]:
            log("the list closed while paging.", HUE_BAD)
            break
        if result["stale"]:
            stale_reads += 1
            if result["late_ms"] is None:
                log("    the page never changed within %dms of pressing Next."
                    % LATE_TIMEOUT_MS, HUE_BAD)
            else:
                log("    STALE READ: the page was still the old one when the "
                    "runner would have read it, and changed %dms later."
                    % result["late_ms"], HUE_BAD)
    else:
        log("hit MAX_PAGES (%d)." % MAX_PAGES, HUE_WARN)

    return pages, stuck, stale_reads


# ---------------------------------------------------------------------------
# Phase 3 - re-filtering in place, the way the runner actually does it
# ---------------------------------------------------------------------------

def phase3(anchor, exact):
    """Does submitting a new filter reset the list to page 1?

    work_one_order only calls open_book() when the gump is CLOSED, so between
    resources the runner re-submits the Name filter on a list still showing
    page N of the previous resource's result. Phase 1 opened the book fresh and
    started at page 1 - which is not what the runner does.

    Returns {"landed", "total", "matches"} or None if it could not be set up.
    """
    rule("phase 3 - re-filtering without reopening the book")
    log("filtering for the decoy %r first" % DECOY_TERM)
    if not press(ORDERS_FILTER_SUBMIT, DECOY_TERM)["ok"]:
        log("the list closed while applying the decoy filter.", HUE_BAD)
        return None

    current, total = page_counter(gump_lines(ORDERS_GUMP))
    log("decoy filtered: page %s of %s" % (current, total))

    for step in range(DECOY_PAGES):
        if not press(ORDERS_NEXT_BUTTON, DECOY_TERM)["ok"]:
            log("the list closed while paging into the decoy.", HUE_BAD)
            return None
        current, total = page_counter(gump_lines(ORDERS_GUMP))
        log("  paged in: now on page %s of %s" % (current, total))

    before, _total = page_counter(gump_lines(ORDERS_GUMP))
    log("now re-filtering for %r WITHOUT reopening the book - exactly what "
        "work_one_order does" % TERM)
    if not press(ORDERS_FILTER_SUBMIT, TERM)["ok"]:
        log("the list closed while re-filtering.", HUE_BAD)
        return None

    strings = gump_lines(ORDERS_GUMP)
    layout = raw_layout(ORDERS_GUMP)
    landed, total = page_counter(strings)
    info = describe_page(1, strings, layout, anchor, exact)

    log("was on page %s, after re-filtering the list shows page %s of %s"
        % (before, landed, total),
        HUE_BAD if (landed or 1) > 1 else HUE_GOOD)

    return {"landed": landed, "total": total, "matches": info["matches"],
            "before": before}


# ---------------------------------------------------------------------------

def write_file(text_lines):
    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(text_lines))
        return True
    except Exception as err:
        log("could not write %s: %s" % (DUMP_PATH, err), HUE_BAD)
        return False


def main():
    started = time.time()
    rule("why %r never fills - v%s" % (TERM, SCRIPT_VERSION))
    log("read-only: presses only %s. No row button, no Purge, no Fill."
        % list(PRESSABLE))

    if not open_list():
        return

    anchor = TERM.strip().lower()
    # The runner's own selection test, character for character.
    exact = re.compile(r"^%ss?$" % re.escape(anchor.rstrip("s")), re.I)

    unfiltered = parse_header(gump_lines(ORDERS_GUMP))
    log("unfiltered: contents %s, displayed %s"
        % (unfiltered.get("stored", "?"), unfiltered.get("displayed", "?")))

    rule("phase 1 - the runner's own paging")
    log("applying the %r filter" % TERM)
    result = press(ORDERS_FILTER_SUBMIT, TERM)
    if not result["ok"]:
        log("The list closed while filtering.", HUE_BAD)
        return
    if result["stale"]:
        log("THE FILTER RESULT WAS LATE: the list still held the unfiltered "
            "page when the runner would have read it%s."
            % ("" if result["late_ms"] is None
               else ", and changed %dms later" % result["late_ms"]), HUE_BAD)

    header = parse_header(gump_lines(ORDERS_GUMP))
    _cur, total_pages = page_counter(gump_lines(ORDERS_GUMP))
    displayed = header.get("displayed")
    log("filtered: displayed %s over %s page(s)"
        % (displayed if displayed is not None else "?",
           total_pages if total_pages is not None else "?"))
    if displayed == 0:
        log("%r matched NOTHING. The book spells it differently - run "
            "diag_order_names.py." % TERM, HUE_BAD)
        return

    pages, stuck, stale_reads = walk(anchor, exact, True)

    walked = len(pages)
    matches = [m for p in pages for m in p["matches"]]
    rejected = sum(sum(p["others"].values()) for p in pages)
    broken = [p for p in pages if p["rows"] != p["buttons"]]
    reached = max([p["current"] for p in pages
                   if p["current"] is not None] or [0])

    rule("phase 1 result")
    log("walked %d page(s), reached page %d of %s"
        % (walked, reached, total_pages if total_pages is not None else "?"))
    log("%d %r order(s) found, %d row(s) belonged to %s or another resource"
        % (len(matches), TERM, rejected, COLLIDES_WITH))
    if matches:
        amounts = sorted(m["amount"] for m in matches)
        log("amounts: smallest %d, largest %d" % (amounts[0], amounts[-1]),
            HUE_GOOD)
    if broken:
        log("%d page(s) had rows and buttons disagree - the runner throws "
            "those away." % len(broken), HUE_BAD)
    if stale_reads:
        log("%d page turn(s) were read before the new page arrived."
            % stale_reads, HUE_BAD)

    # --- phase 2, only if it got stuck -------------------------------------
    phase2 = None
    if stuck >= STUCK_PAGES_BEFORE_GIVING_UP:
        rule("phase 2 - is it the filter text on the Next press?")
        log("re-filtering, then pressing Next WITHOUT restating the filter. "
            "That clears the Name filter, so seeing another resource's rows on "
            "page 2 is expected - what matters is whether the counter moves.")
        if not open_list():
            log("could not reopen the list for phase 2.", HUE_BAD)
        elif not press(ORDERS_FILTER_SUBMIT, TERM)["ok"]:
            log("the list closed while re-filtering.", HUE_BAD)
        else:
            p2_pages, p2_stuck, _stale = walk(anchor, exact, False)
            p2_reached = max([p["current"] for p in p2_pages
                              if p["current"] is not None] or [0])
            phase2 = {"reached": p2_reached, "stuck": p2_stuck}
            log("plain Next reached page %d" % p2_reached,
                HUE_GOOD if p2_reached > 1 else HUE_BAD)

    # --- phase 3, whenever phase 1 walked cleanly ---------------------------
    #
    # Phase 1 opens the book fresh and starts on page 1. The runner does not:
    # it re-filters a list already sitting deep in the previous resource's
    # result. If that page position survives the filter, the runner starts its
    # scan past the orders it wants - and Copper's are only on pages 1-2.
    p3 = None
    if stuck < STUCK_PAGES_BEFORE_GIVING_UP and matches:
        if not open_list():
            log("could not reopen the list for phase 3.", HUE_BAD)
        else:
            p3 = phase3(anchor, exact)

    # --- verdict ------------------------------------------------------------
    #
    # Order matters. D is decisive and explains everything, so it comes first.
    # A concrete paging fault (A/A'/B) outranks phase 3's NEGATIVE result -
    # "re-filtering resets correctly" is not a finding, and must not be printed
    # in place of stale reads that are.
    rule("verdict")
    if p3 is not None and (p3["landed"] or 1) > 1:
        log("D - THE PAGE POSITION SURVIVES A NEW FILTER. The list was on page "
            "%s, and after re-filtering for %r it is on page %s of %s - not "
            "page 1." % (p3["before"], TERM, p3["landed"], p3["total"]), HUE_BAD)
        log("The runner never reopens the book between resources, so it starts "
            "%s's scan wherever the previous resource left off. All %d %s "
            "orders are on pages 1-2, so it walks straight past them and "
            "reports none." % (TERM, len(matches), TERM), HUE_BAD)
        log("FIX: reset to page 1 after applying a filter - press Previous "
            "until the counter reads 1, or reopen the list - before scanning.",
            HUE_WARN)
    elif stuck >= STUCK_PAGES_BEFORE_GIVING_UP and phase2 is not None \
            and phase2["reached"] > 1:
        log("A - NEXT PAGE RESETS THE LIST when the filter text is restated. "
            "Pressing Next with the filter re-submitted stays on page 1; "
            "pressing it plain advances. The runner can never see past page 1 "
            "of a filtered result, so any resource whose orders are not on "
            "page 1 is invisible to it.", HUE_BAD)
        log("FIX: re-apply the filter and page in one press some other way - "
            "or press Next plain and re-filter after, which costs one extra "
            "round trip per page.", HUE_WARN)
    elif stuck >= STUCK_PAGES_BEFORE_GIVING_UP:
        log("A' - NEXT PAGE DOES NOT ADVANCE AT ALL on a filtered list, with "
            "or without the filter text. Paging a filtered result is not "
            "possible the way the runner does it.", HUE_BAD)
    elif broken or stale_reads:
        log("B - THE PAGES ARRIVE LATE. %d stale read(s) and %d page(s) whose "
            "rows and buttons disagreed. The runner reads the previous page, "
            "throws it away, and reports no orders."
            % (stale_reads, len(broken)), HUE_BAD)
        log("FIX: the .19 content-change wait and the .21 atomic read, both "
            "already written in the .23 snapshot.", HUE_WARN)
    elif matches and p3 is not None:
        log("C - THE PAGING IS FINE and re-filtering DOES reset to page 1 "
            "(landed on page %s). %d %s order(s) found, from %d to %d. The "
            "runner sees them, starts at page 1 and has the budget - so "
            "capture its journal around %s's turn, because nothing left in "
            "the gump explains it."
            % (p3["landed"], len(matches), TERM,
               min(m["amount"] for m in matches),
               max(m["amount"] for m in matches), TERM), HUE_WARN)
    elif matches:
        log("C - THE PAGING IS FINE. %d %s order(s) were found, from %d to %d. "
            "The runner is not failing to SEE them, so it is rejecting them - "
            "check the budget for %s in the runner's stock report, and whether "
            "%s gets a turn before MAX_ORDERS_PER_RUN is spent."
            % (len(matches), TERM, min(m["amount"] for m in matches),
               max(m["amount"] for m in matches), TERM, TERM), HUE_WARN)
    else:
        log("C' - the whole result was walked cleanly and there is genuinely "
            "no %r order in the book right now. Re-run when there is one - "
            "the book is live." % TERM, HUE_WARN)

    log("%d page(s) in %.1fs" % (walked, time.time() - started))

    out = ["Resource Order Book - %r page walk" % TERM,
           "=" * 55, "",
           "version     : %s" % SCRIPT_VERSION,
           "run at      : %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
           "filter      : %r" % TERM,
           "collides    : %r" % COLLIDES_WITH,
           "displayed   : %s over %s page(s)" % (displayed, total_pages),
           "", "-- journal, verbatim ---------------------------------"]
    out.extend(REPORT)
    out.append("")
    out.append("-- per page ------------------------------------------")
    for p in pages:
        out.append("  page %s/%s  rows %d  buttons %d  matched %d  other %d"
                   % (p["current"], p["total"], p["rows"], p["buttons"],
                      len(p["matches"]), sum(p["others"].values())))
        for m in p["matches"]:
            out.append("      %s x%d  button %d"
                       % (m["name"], m["amount"], m["button"]))
        for name, count in sorted(p["others"].items(), key=lambda kv: -kv[1]):
            out.append("      (other) %-32s x%d" % (name, count))

    if write_file(out):
        log("written to %s" % DUMP_PATH, HUE_GOOD)


main()
