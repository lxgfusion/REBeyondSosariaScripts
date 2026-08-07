"""
Resource Order Book - name harvester.
=====================================

Walks every page of the order book and records the EXACT name of every resource
it asks for, with how many orders want each. Run it once and the guessing about
names is over.

Why this exists: `resource_order_runner.py` matches a resource by the book's own
name, and the book does not always agree with the item or with ServUO. Shadow
Iron is listed as "Shadow Ingots". Six peerless names were transcribed from a
column too narrow to show them whole. Every wrong name fails the same silent
way - the filter returns nothing, and the resource looks skipped rather than
erroring.

Output: %TEMP%\\ro_order_names.txt, containing

    * every distinct name, sorted by how many orders want it
    * ready-to-paste RESOURCES lines for resource_order_runner.py

WHAT IT CLICKS
--------------
Book button 1 (opens the list) and list button 5 (next page). Nothing else - no
row button, no filter submit, nothing that spends or withdraws. The book is
Blessed and locked down.

HOW LONG
--------
The book is around 540 pages at 15 rows each. Expect roughly ten minutes. It
writes the file every WRITE_EVERY pages, so stopping the script early still
leaves usable results.

Set STOP_AFTER_QUIET_PAGES if you want it to finish as soon as the names stop
being new - much faster, at the risk of missing something rare.
"""

import os
import re
import time


# =============================================================================
# CONFIG
# =============================================================================

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

# Empty walks the whole book. Set a term to harvest one slice instead, which is
# far quicker when you only want to confirm a handful of names.
FILTER_TERM = ""

# The book is about 540 pages; this is the ceiling, not the expectation.
MAX_PAGES = 700

# Stop once this many pages in a row have produced no NEW name. 0 walks the lot.
# 40 is a reasonable compromise if you do not want to wait for all of it.
STOP_AFTER_QUIET_PAGES = 0

# Progress line every this many pages, and a file write every WRITE_EVERY.
PROGRESS_EVERY = 20
WRITE_EVERY = 25

GUMP_TIMEOUT_MS = 10000
SETTLE_MS = 450

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "ro_order_names.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[NAMES] " + str(text), hue, False)


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Compatibility shims
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


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Confirmed from the rendered gump:
#     Name | Amt To Gather | Amt Gathered | Value Per | Completed
HEADER_LABELS = ("name", "amt to gather", "amt gathered", "value per",
                 "completed")
FOOTER_FIRST = ("previous page", "next page")
ROW_FLAGS = ("yes", "no", "none", "")

NUMERIC = re.compile(r"^-?[\d,]+$")


def row_region(strings):
    """The slice of `strings` holding the order rows."""
    lowered = [(s or "").strip().lower() for s in strings]
    start = 0
    for label in HEADER_LABELS:
        if label in lowered:
            start = max(start, lowered.index(label) + 1)
    end = len(strings)
    for footer in FOOTER_FIRST:
        if footer in lowered:
            end = min(end, lowered.index(footer))
    return strings[start:end]


def names_on_page(strings):
    """Every resource name on this page.

    A name is a cell that has letters, is not a flag, and is IMMEDIATELY
    FOLLOWED BY A NUMBER - the Amt To Gather beside it. That last part is what
    makes this reliable without a filter to anchor on: the Runics column can
    hold a runic's name, which has letters too, but nothing numeric follows it.

    Razor drops empty strings out of a gump's string table without leaving a
    gap, so cells shift and a fulfilled order renders fewer of them. Reading a
    name by its RELATIONSHIP to the next cell survives both.
    """
    cells = [(s or "").strip() for s in row_region(strings)]
    found = []
    for i, text in enumerate(cells):
        if not text or text.lower() in ROW_FLAGS:
            continue
        if NUMERIC.match(text):
            continue
        if not re.search(r"[A-Za-z]", text):
            continue
        if i + 1 >= len(cells) or not NUMERIC.match(cells[i + 1]):
            continue
        found.append(re.sub(r"\s+", " ", text))
    return found


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
        log("Resource Order Book not found within %d tiles." % WORLD_RANGE,
            HUE_BAD)
        return False

    # WaitForGump returns True for a gump that is already open, so a leftover
    # window would be read instead of the real one.
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


def orders_action(button):
    """Press a button, restating the filter.

    A plain SendAction submits the gump's text entries EMPTY, which would clear
    the filter mid-walk and silently change what is being read.
    """
    ids = list(ORDERS_TEXT_IDS)
    values = [FILTER_TERM if i == ORDERS_SEARCH_ENTRY else "" for i in ids]
    try:
        Gumps.SendAdvancedAction(ORDERS_GUMP, button, [], ids, values)
    except Exception:
        Gumps.SendAction(ORDERS_GUMP, button)
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    return has_gump(ORDERS_GUMP)


# ---------------------------------------------------------------------------

def write_file(counts, pages, total_pages, elapsed, finished):
    lines = []
    lines.append("Resource Order Book - names as the book writes them")
    lines.append("=" * 55)
    lines.append("")
    lines.append("filter      : %r" % (FILTER_TERM or "(none - whole book)"))
    lines.append("pages read  : %d of %s" % (pages, total_pages or "?"))
    lines.append("distinct    : %d" % len(counts))
    lines.append("orders seen : %d" % sum(counts.values()))
    lines.append("elapsed     : %.1f min" % (elapsed / 60.0))
    lines.append("status      : %s" % ("complete" if finished
                                       else "PARTIAL - stopped early"))
    lines.append("")
    lines.append("-- by how many orders want it -------------------------")
    for name in sorted(counts, key=lambda n: (-counts[n], n.lower())):
        lines.append("  %-40s %d" % (name, counts[name]))

    lines.append("")
    lines.append("-- RESOURCES lines, ready to paste --------------------")
    lines.append("-- id/hue still have to come from the Item Inspector;")
    lines.append("-- what is authoritative here is the NAME.")
    for name in sorted(counts, key=lambda n: n.lower()):
        lines.append('    {"name": "%s", "id": 0x0000, "hue": -1, '
                     '"by": "name"},' % name)

    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(lines))
        return True
    except Exception as err:
        log("could not write %s: %s" % (DUMP_PATH, err), HUE_BAD)
        return False


def main():
    started = time.time()
    rule("order book name harvester")
    log("filter: %r" % (FILTER_TERM or "(none - whole book)"))

    if not open_list():
        return

    if FILTER_TERM:
        log("applying the filter")
        if not orders_action(ORDERS_FILTER_SUBMIT):
            log("The list closed while filtering.", HUE_BAD)
            return

    strings = gump_lines(ORDERS_GUMP)
    header = parse_header(strings)
    _page, total_pages = page_counter(strings)
    log("contents %s/%s, displayed %s, %s page(s)"
        % (header.get("stored", "?"), header.get("capacity", "?"),
           header.get("displayed", "?"), total_pages or "?"))

    counts = {}
    quiet_pages = 0
    pages = 0
    finished = False

    for page in range(1, MAX_PAGES + 1):
        strings = gump_lines(ORDERS_GUMP)
        pages = page

        before = len(counts)
        for name in names_on_page(strings):
            counts[name] = counts.get(name, 0) + 1
        new = len(counts) - before

        if new:
            quiet_pages = 0
        else:
            quiet_pages += 1

        if page % PROGRESS_EVERY == 0 or new:
            current, total = page_counter(strings)
            log("page %s/%s - %d distinct name(s)%s"
                % (current or page, total or total_pages or "?", len(counts),
                   ", %d new" % new if new else ""),
                HUE_GOOD if new else HUE_INFO)

        if page % WRITE_EVERY == 0:
            write_file(counts, pages, total_pages, time.time() - started, False)

        if STOP_AFTER_QUIET_PAGES and quiet_pages >= STOP_AFTER_QUIET_PAGES:
            log("no new names for %d pages - stopping early."
                % quiet_pages, HUE_WARN)
            break

        current, total = page_counter(strings)
        if current is not None and total is not None and current >= total:
            finished = True
            log("reached the last page (%d)." % total, HUE_GOOD)
            break

        if not orders_action(ORDERS_NEXT_BUTTON):
            log("The list closed while paging - stopping.", HUE_WARN)
            break
    else:
        log("hit MAX_PAGES (%d)." % MAX_PAGES, HUE_WARN)

    rule("%d distinct name(s) over %d page(s) in %.1f min"
         % (len(counts), pages, (time.time() - started) / 60.0))

    for name in sorted(counts, key=lambda n: (-counts[n], n.lower()))[:25]:
        log("  %-38s %d" % (name, counts[name]))
    if len(counts) > 25:
        log("  ... %d more, see the file." % (len(counts) - 25))

    if write_file(counts, pages, total_pages, time.time() - started, finished):
        log("written to %s" % DUMP_PATH, HUE_GOOD)


main()
