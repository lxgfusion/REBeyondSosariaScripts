"""
Resource order diagnostic.
==========================

Read-only groundwork for the resource-order filler. It answers the four things
that script needs to know and cannot be guessed, and it does the ingot census
for real - that part is finished work, not a probe.

What it reports:

    1. INGOT CENSUS. Opens the chest beside the book, lists every stack in it
       with ItemID, hue, amount and tooltip, works out which are ingots, and
       prints the fill budget - the amount of each type that may be spent once
       KEEP_PER_TYPE is left behind.
    2. THE BOOK'S OWN WINDOW (gump 0x06ABCE12). Raw layout, every text line,
       every button id with its screen position.
    3. THE ORDER LIST (gump 0xB2F21F1A). Same dump, for as many pages as
       PAGES_TO_DUMP, pairing each order row to the button on its own line by
       Y coordinate rather than by counting lines.
    4. ANY RESOURCE ORDER DEED already in your pack, with the raw tooltip, the
       de-concatenated tooltip and the parsed fields.

Everything lands in %TEMP%\\resource_orders_diag.txt. Paste that back.

WHAT IT CLICKS, AND WHY THAT IS SAFE
------------------------------------
Only two buttons, both of which you demonstrated in the Gump Inspector:

    book gump  0x06ABCE12  button 1  -> opens the Resource Orders list
    order list 0xB2F21F1A  button 5  -> next page

Nothing else is pressed. In particular it never presses a button on an order
ROW, because withdrawing an order is exactly the unknown this is meant to
identify, and it never sends a number into the book's text field - that field
withdraws stock from the book, and harvest_runner.py deliberately avoids it.

The book is Blessed and locked down, so nothing here can lose it.

NOTE ON THE SEARCH BOX
----------------------
The order list carries five text entries. In your capture, entry 0 held
"ingots" and the header read "Displayed: 980" against "Contents: 8653/100000",
so entry 0 is the name filter. Set SEARCH_TEXT to drive it; leave it None to
page through whatever the book opens with.

Sending a plain button press to a gump that has text entries submits those
entries EMPTY, which clears the filter. So when SEARCH_TEXT is set, paging goes
through SendAdvancedAction and carries the filter along.

This does not read the journal, so it does not touch Journal.Clear().
"""

import os
import re
import time


# =============================================================================
# CONFIG - SHARD TABLE. Fill this in first; everything else is timings.
# =============================================================================
# Both serials were taken from the Enhanced Item Inspector and both are locked
# down on the ground at the house - Container: None, Root Container: None,
# Ground: Yes - so they are found with a WORLD search, never a backpack search.
# The id/hue pair is the fallback for the day one of them is replaced.

# "Resource Order Book", ItemID 0x2259, hue 0x04F7, at (1282, 1192, -85).
BOOK_SERIAL = 0x404AC332
BOOK_ID = 0x2259
BOOK_HUE = 0x04F7

# "a glimmering chest of belongings", ItemID 0x0E41, hue 0x089F,
# at (1281, 1192, -88). Tooltip: Locked Down & Secure, 44/125 items.
CHEST_SERIAL = 0x400CEF90
CHEST_ID = 0x0E41
CHEST_HUE = 0x089F

# Second chest, for the stackable peerless ingredients. Inspected:
# "a glimmering chest of belongings", 0x400463FB, ItemID 0x0E41, hue 0x047E,
# at (1280, 1192, -88) - beside the first. Set to 0 to skip it.
CHEST2_SERIAL = 0x400463FB
CHEST2_ID = 0x0E41
CHEST2_HUE = 0x047E

# Tiles to search for either of them. They sit next to each other, so standing
# at the book puts you within 2 of the chest.
WORLD_RANGE = 4

# The window double-clicking the book opens. Shared with harvest_runner.py,
# where it is HOUSE_DEPOSIT_GUMP.
BOOK_GUMP = 0x06ABCE12

# The order list reached from it. Both ids confirmed in the Gump Inspector.
ORDERS_GUMP = 0xB2F21F1A

# Confirmed by your response log:
#   Gump ID: 0x6abce12   Gump Button: 1   -> Resource Orders opened
BOOK_ORDERS_BUTTON = 1

# Confirmed by your response log:
#   Gump ID: 0xb2f21f1a  Gump Button: 5   -> next page
ORDERS_NEXT_BUTTON = 5

# The five per-column filter boxes at y=412, one under each column. Entry 0 is
# under the Name column; button 12 is its submit, sitting immediately to its
# right at (95, 410). The other columns are 1/22, 2/32, 3/42, 4/52.
ORDERS_TEXT_IDS = [0, 1, 2, 3, 4]
ORDERS_SEARCH_ENTRY = 0
ORDERS_FILTER_SUBMIT = 12

# What to type into the Name filter. None = leave the book's own default view.
#
# The default view is worth nothing here: all 8656 orders it pages through are
# for Mythril Ingots, and there is no Mythril in the chest.
#
# The filter is a SUBSTRING match on the Name column, which matters more than it
# sounds: filtering "Valorite" returned 230 rows of "Valorite Granite" and not
# one ingot order. Always include the resource word.
SEARCH_TEXT = "Valorite Ingots"

# The survey. For each of these the Name filter is applied and the result
# counted, which is the only way to find out what is actually fillable - the
# book holds 8658 orders and the unfiltered view shows none of the ones that
# matter. Set to [] to skip.
#
# "<Metal> Ingots" rather than "<Metal>" so granite and ore orders stay out.
SURVEY_SUFFIX = " Ingots"

# Broad terms used to discover the book's real vocabulary. Deliberately short
# and generic - the point is to find out what the book calls things, not to
# assume. "Shadow" was what revealed that Shadow Iron is listed as
# "Shadow Ingots".
VOCABULARY_TERMS = ["Ingot", "Iron", "Shadow", "Copper", "Bronze", "Gold",
                    "Agapite", "Verite", "Valorite", "Diamond", "Pearl",
                    "Amber", "Citrine", "Ruby", "Emerald", "Sapphire",
                    "Turquoise"]
VOCABULARY_PAGES = 2
SURVEY_METALS = ["Iron", "Dull Copper", "Shadow Iron", "Copper", "Bronze",
                 "Gold", "Agapite", "Verite", "Valorite"]

# How many pages of the order list to walk before the survey. The page
# structure and the row-button numbering are both confirmed now, so 2 is plenty.
PAGES_TO_DUMP = 2


# =============================================================================
# CONFIG - INGOT CENSUS
# =============================================================================
# What the filler would be allowed to spend. The chest keeps this many of every
# ingot type; only the surplus above it is available to fill orders.
KEEP_PER_TYPE = 100

# An item counts as an ingot if its name or tooltip contains one of these.
# Matching on TEXT rather than ItemID is deliberate: a shard-custom metal may be
# given its own graphic rather than a hue of 0x1BF2, and a text match catches
# both. The TYPE, though, comes from the hue - see below.
INGOT_WORDS = ["ingot"]

# Vanilla ingot graphic. Every metal shares it - ServUO
# Scripts/Items/Resource/Ingots.cs has all nine deriving from BaseIngot(0x1BF2).
VANILLA_INGOT_ID = 0x1BF2

# HUE IS THE ONLY THING THAT NAMES A METAL.
#
# Every stack in the chest is called "<amount> ingots" - "60000 ingots",
# "59994 ingots". The name carries the COUNT, not the metal. Keying stock by
# name therefore does two wrong things at once: it merges different metals that
# happen to hold the same amount, and it splits one metal across stacks of
# different sizes. The first dump did exactly that, reporting a phantom type
# called "60000 ingots" holding 300000 across five different hues.
#
# Hues verified against ServUO Scripts/Misc/ResourceInfo.cs (CraftResourceInfo).
METAL_HUES = {
    0x0000: "Iron",
    0x0973: "Dull Copper",
    0x0966: "Shadow Iron",
    0x096D: "Copper",
    0x0972: "Bronze",
    0x08A5: "Gold",
    0x0979: "Agapite",
    0x089F: "Verite",
    0x08AB: "Valorite",
}


# =============================================================================
# CONFIG - ROW BUTTON PROBE. OFF, AND DELIBERATELY SO.
# =============================================================================
# The order rows carry buttons 115-129 on page 2, 130-144 on page 3 and so on.
# They are the obvious candidate for "withdraw this order" - but nothing in the
# dump proves it, and the same gump also carries Add, Purge and
# "Fill from backpack", any of which would be a bad thing to hit by accident.
#
# With this True the script presses ONE row button - the first one on the page,
# whose row it prints first - and then reports what changed: which gump is open,
# and what appeared in your backpack. It stops there.
#
# Turn it on only when you are ready to have one order withdrawn, and read the
# row it names before you do.
PROBE_ROW_BUTTON = False


# =============================================================================
# CONFIG - TIMINGS
# =============================================================================

GUMP_TIMEOUT_MS = 10000
CONTENTS_TIMEOUT_MS = 4000
PROPS_TIMEOUT_MS = 1500
SETTLE_MS = 600


# =============================================================================

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "resource_orders_diag.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

_lines = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[RO] " + str(text), hue, False)
    _lines.append(str(text))


def quiet(text):
    """File only. Used for the bulk dumps that would flood the message window."""
    _lines.append(str(text))


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Compatibility shims. Razor Enhanced has changed these signatures before; the
# script picks whichever the running build accepts.
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
    except Exception as err:
        log("GetGumpRawLayout(0x%X) failed: %s" % (gump_id, err), HUE_BAD)
        return ""


# ---------------------------------------------------------------------------
# Finding the two containers
# ---------------------------------------------------------------------------

def find_world_item(serial, item_id, hue, label):
    """Exact serial first, id/hue in the world as the fallback.

    Both of these are locked down on the ground, so Container and RootContainer
    are None and a backpack search can never see them - the world search passes
    container -1.
    """
    if serial:
        item = Items.FindBySerial(serial)
        if item is not None:
            return item, "serial 0x%X" % serial
        log("%s: serial 0x%X did not resolve, falling back to id/hue."
            % (label, serial), HUE_WARN)

    try:
        found = Items.FindAllByID(item_id, hue, -1, WORLD_RANGE, False)
    except Exception as err:
        log("%s: FindAllByID failed: %s" % (label, err), HUE_BAD)
        return None, "not found"

    found = list(found or [])
    if not found:
        return None, "not found"
    if len(found) > 1:
        log("%s: %d candidates matched id 0x%X hue 0x%X - taking the nearest."
            % (label, len(found), item_id, hue), HUE_WARN)
        found.sort(key=lambda it: Player.DistanceTo(it))
    return found[0], "id 0x%X hue 0x%X" % (item_id, hue)


def props(item):
    """Tooltip lines, with the props request that makes them load."""
    try:
        Items.WaitForProps(item, PROPS_TIMEOUT_MS)
        return [str(p) for p in Items.GetPropStringList(item)]
    except Exception:
        return []


def open_container(item, label):
    """Double-click and wait for the contents to arrive."""
    try:
        Items.UseItem(item)
    except Exception as err:
        log("%s: UseItem failed: %s" % (label, err), HUE_BAD)
        return False
    try:
        ok = Items.WaitForContents(item, CONTENTS_TIMEOUT_MS)
    except Exception as err:
        log("%s: WaitForContents failed: %s" % (label, err), HUE_WARN)
        ok = False
    Misc.Pause(SETTLE_MS)
    return bool(ok)


# ---------------------------------------------------------------------------
# Ingot census. These are the real thing, not a probe - the filler uses exactly
# this logic to decide how much of each type it may spend.
# ---------------------------------------------------------------------------

def spaced(raw):
    """Insert a space at each lower/digit -> upper seam.

    Tooltip properties arrive concatenated: a taming deed reads
    "Level: 2Creature Type: KirinFilled: 24/60Gold: 100%". Lowercasing that
    gives "kirinfilled", so any regex ending in \\b silently fails to match.
    """
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw or "")


def describe(item):
    """Best available name for an item, tooltip first, then Name."""
    lines = props(item)
    if lines:
        return spaced(lines[0]).strip(), lines
    return (item.Name or "").strip(), []


def is_ingot(name, tooltip_lines):
    haystack = " ".join([name] + list(tooltip_lines)).lower()
    return any(word in haystack for word in INGOT_WORDS)


def metal_name(item_id, hue):
    """The metal a stack is, from its hue. Never from its name.

    An unknown hue is reported as "Unknown (hue 0x____)" rather than guessed at,
    so a shard-custom metal shows up as a named gap instead of being silently
    folded into iron.
    """
    if hue in METAL_HUES:
        return METAL_HUES[hue]
    return "Unknown (hue 0x%04X)" % hue


def strip_amount(name):
    """"60000 ingots" -> "ingots". The stack name carries its own count."""
    return re.sub(r"^\s*[\d,]+\s+", "", name or "").strip()


def census(container):
    """Every stack in the container, and the ingot subset keyed by metal.

    Returns (all_rows, ingots) where ingots maps a lowercased metal name to
    {"name", "amount", "ids", "hues"}. Amounts are summed per METAL, so the same
    metal split across several stacks is counted once and the reserve comes off
    the total rather than off each stack.
    """
    rows = []
    ingots = {}
    contents = list(container.Contains or [])
    for item in contents:
        name, tooltip = describe(item)
        amount = int(getattr(item, "Amount", 0) or 0)
        item_id = int(item.ItemID)
        hue = int(item.Hue)
        ingot = is_ingot(name, tooltip)
        row = {
            "name": name,
            "bare": strip_amount(name),
            "amount": amount,
            "id": item_id,
            "hue": hue,
            "serial": int(item.Serial),
            "tooltip": tooltip,
            "ingot": ingot,
            "metal": metal_name(item_id, hue) if ingot else "",
        }
        rows.append(row)
        if not ingot:
            continue
        key = row["metal"].lower()
        entry = ingots.setdefault(
            key, {"name": row["metal"], "amount": 0, "ids": set(), "hues": set()})
        entry["amount"] += amount
        entry["ids"].add(item_id)
        entry["hues"].add(hue)
    return rows, ingots


def fill_budget(ingots, keep=KEEP_PER_TYPE):
    """How much of each type may be spent, leaving `keep` behind.

    The reserve is per TYPE, not per stack, so two stacks of the same ingot are
    counted together before the reserve comes off.
    """
    budget = {}
    for key, entry in ingots.items():
        budget[key] = {
            "name": entry["name"],
            "have": entry["amount"],
            "keep": keep,
            "available": max(0, entry["amount"] - keep),
        }
    return budget


# ---------------------------------------------------------------------------
# Gump layout parsing.
#
# GetGumpRawLayout returns the server's layout string, e.g.
#     { gumppic 0 0 5170 }{ text 60 90 0 12 }{ button 20 90 4005 4007 1 0 7 }
# Each element carries its X and Y, which is what lets a row's text be paired
# with the button on the SAME LINE. Counting lines does not survive a gump that
# renders a different number of cells for some rows - which this one does.
# ---------------------------------------------------------------------------

def layout_elements(layout):
    """Every { ... } element as {"kind", "nums", "raw"}."""
    out = []
    for piece in re.findall(r"\{([^{}]*)\}", layout or ""):
        piece = piece.strip()
        if not piece:
            continue
        parts = piece.split()
        kind = parts[0].lower()
        nums = [int(n) for n in re.findall(r"-?\d+", piece)]
        out.append({"kind": kind, "nums": nums, "raw": piece})
    return out


def layout_buttons(layout):
    """(y, x, button_id, raw) for each button.

    Layout is { button X Y NORMAL PRESSED TYPE PARAM BUTTONID }, so X and Y are
    the first two numbers and the id is the last.
    """
    out = []
    for el in layout_elements(layout):
        if el["kind"] != "button" or len(el["nums"]) < 3:
            continue
        nums = el["nums"]
        out.append((nums[1], nums[0], nums[-1], el["raw"]))
    return sorted(out)


def layout_texts_in_order(layout):
    """(y, x, text_id, raw) for each text-bearing element, IN LAYOUT ORDER.

    { text X Y HUE TEXTID } and { croppedtext X Y W H HUE TEXTID } both end in
    the string-table index. `textentry` is excluded: its trailing id points at
    an initial value that is usually blank, and blanks are exactly what Razor
    loses, so counting them would reintroduce the shift.

    Order is preserved deliberately - it is the only reliable way to line these
    up with GetLineList.
    """
    out = []
    for el in layout_elements(layout):
        if el["kind"] not in ("text", "croppedtext") or len(el["nums"]) < 3:
            continue
        nums = el["nums"]
        out.append((nums[1], nums[0], nums[-1], el["raw"]))
    return out


def layout_texts(layout):
    """Same elements, sorted top-to-bottom. Only safe where order does not
    matter - use layout_texts_in_order to pair with strings."""
    return sorted(layout_texts_in_order(layout))


def pair_rows(layout, strings, tolerance=6):
    """Group layout text by Y and attach the button sharing that line.

    POSITIONS ONLY. The text is matched to elements by ORDER, never by the text
    id in the layout, because Razor Enhanced drops empty strings out of the
    gump's string table without leaving a gap - see the note on the index shift
    below - so the ids stop lining up the moment a gump contains a blank cell.

    Element order and string order do still agree, because both come from the
    same left-to-right, top-to-bottom walk of the layout.
    """
    rows = []

    def bucket(y):
        for row in rows:
            if abs(row["y"] - y) <= tolerance:
                return row
        row = {"y": y, "cells": [], "buttons": []}
        rows.append(row)
        return row

    texts = layout_texts_in_order(layout)
    for position, (y, x, _text_id, _raw) in enumerate(texts):
        value = strings[position] if position < len(strings) else "<no string>"
        bucket(y)["cells"].append((x, value))
    for y, x, button_id, _raw in layout_buttons(layout):
        bucket(y)["buttons"].append((x, button_id))

    for row in rows:
        row["cells"].sort()
        row["buttons"].sort()
    rows.sort(key=lambda r: r["y"])
    return rows


def string_index_shift(layout, strings, anchor="previous page"):
    """How many strings Razor lost before `anchor`, or None if it is absent.

    Counting text elements against the string list does NOT work: the elements
    that get dropped are usually `textentry` initial values, which this parser
    already excludes, so the two counts agree while the data is still shifted.
    The first version reported a shift of 0 on a page that had lost nine.

    Anchoring on a literal instead is exact. `anchor` is a footer label whose
    element position in the layout is known, so the gap between where it should
    be and where it actually is IS the number of dropped strings.
    """
    lowered = [(s or "").strip().lower() for s in strings]
    if anchor not in lowered:
        return None

    actual = lowered.index(anchor)
    texts = layout_texts_in_order(layout)
    expected = None
    for position, (y, x, _text_id, _raw) in enumerate(texts):
        # The footer label sits at the bottom left, below the order rows.
        if y >= 430 and x <= 100:
            expected = position
            break
    if expected is None:
        return None
    return expected - actual


# ---------------------------------------------------------------------------
# Order rows.
#
# Parsed by SHAPE rather than by position, then zipped with the page's sorted
# row buttons. A fulfilled order renders three cells where a live one renders
# five, so any scheme that assumes a fixed cell count - or counts lines - walks
# off by one for the whole rest of the page.
# ---------------------------------------------------------------------------

# Cells that carry a flag rather than a resource name, so they never start a row.
ROW_FLAGS = ("yes", "no", "none", "")

HEADER_LAST = "value per"
FOOTER_FIRST = ("previous page", "next page")


def order_row_region(strings):
    """The slice of `strings` holding the order rows, by literal anchors."""
    lowered = [(s or "").strip().lower() for s in strings]

    start = 0
    if HEADER_LAST in lowered:
        start = lowered.index(HEADER_LAST) + 1

    end = len(strings)
    for anchor in FOOTER_FIRST:
        if anchor in lowered:
            end = min(end, lowered.index(anchor))
    return start, end


def parse_order_rows(strings):
    """[{"name", "amount"}] for each order row, in display order.

    A row begins at any cell that contains a letter and is not a flag; the first
    numeric cell after it is Amt To Gather. A row whose amount cell is missing
    reports None rather than guessing.
    """
    start, end = order_row_region(strings)
    rows = []
    for value in strings[start:end]:
        text = (value or "").strip()
        low = text.lower()
        if low in ROW_FLAGS:
            continue
        if re.match(r"^-?[\d,]+$", text):
            if rows and rows[-1]["amount"] is None:
                rows[-1]["amount"] = int(text.replace(",", ""))
            continue
        if re.search(r"[A-Za-z]", text):
            rows.append({"name": re.sub(r"\s+", " ", text), "amount": None})
    return rows


def row_buttons(layout, x_max=60, y_min=80, y_max=400):
    """The 15 per-row buttons, top to bottom.

    They are the ones in the left margin between the header and the filter row,
    which excludes the column sorters at y=70 and the footer nav at y=440.
    """
    return [button for y, x, button, _raw in layout_buttons(layout)
            if x <= x_max and y_min <= y <= y_max]


def page_counter(strings):
    """(page, total) from the "(2/66)" footer, or (None, None)."""
    for value in strings:
        match = re.search(r"\((\d+)\s*/\s*(\d+)\)", value or "")
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


# ---------------------------------------------------------------------------
# Order deed tooltips.
#
# harvest_runner.py excludes "creature type" and "resource type" from the BOD
# book, so a resource order deed carries a "Resource Type:" field exactly the
# way a taming order carries "Creature Type:". Same concatenation problem, so
# the same seam fix applies, and the value ends where the next label begins.
# ---------------------------------------------------------------------------

# Confirmed from a live deed, Item Inspector 2026-07-27:
#
#   Name: A Resource Order Deed   ItemID: 0x14F0   Blessed, 1 stone
#   "0 / 132 Valorite Granite ObtainedValued At: 400 Gold Each"
#
# There is no "Resource Type:" and no "Filled:" - those are TAMING order fields.
# The first version of this looked for them and reported "no order deeds in the
# pack" while one was sitting in it.
# A COMPLETED deed uses a different shape again - inspected 2026-07-27,
# serial 0x40565AF7, still 0x14F0 and still in the pack (not consumed):
#       "Order Fulfilled [1038 Copper Ingots]Valued At: 25 Gold Each"
DEED_ID = 0x14F0

DEED_PROGRESS_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s+(.+?)\s+Obtained\b", re.I)
DEED_DONE_RE = re.compile(
    r"Order\s+Fulfilled\s*\[\s*([\d,]+)\s+([^\]]+?)\s*\]", re.I)
DEED_VALUE_RE = re.compile(r"Valued\s+At:\s*([\d,]+)\s*Gold", re.I)


def parse_deed(raw):
    """{"filled", "needed", "resource", "gold_each", "complete"} from a tooltip.

    Both shapes. A fulfilled deed reports filled == needed so that anything
    testing progress does not have to know there are two.
    """
    text = spaced(raw)
    found = {}

    done = DEED_DONE_RE.search(text)
    if done:
        amount = int(done.group(1).replace(",", ""))
        found["complete"] = True
        found["filled"] = amount
        found["needed"] = amount
        found["resource"] = re.sub(r"\s+", " ", done.group(2)).strip()
    else:
        match = DEED_PROGRESS_RE.search(text)
        if match:
            found["complete"] = False
            found["filled"] = int(match.group(1))
            found["needed"] = int(match.group(2))
            found["resource"] = re.sub(r"\s+", " ", match.group(3)).strip()

    value = DEED_VALUE_RE.search(text)
    if value:
        found["gold_each"] = int(value.group(1).replace(",", ""))
    return found


def deed_progress(fields):
    """(filled, needed), or (None, None) if the tooltip did not parse."""
    if "needed" not in fields:
        return None, None
    return fields.get("filled", 0), fields["needed"]


# ---------------------------------------------------------------------------
# Order list rows
# ---------------------------------------------------------------------------

def parse_header(strings):
    """Contents / Displayed counters from the top of the order list."""
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
# Gump interaction
# ---------------------------------------------------------------------------

def send_orders_action(button):
    """Press a button on the order list, carrying the filter text along.

    A plain SendAction on a gump with text entries submits them EMPTY, which
    would wipe the name filter and change what the next page contains. When a
    filter is configured the press goes through SendAdvancedAction with the
    text restated.
    """
    if SEARCH_TEXT is None:
        Gumps.SendAction(ORDERS_GUMP, button)
        return "SendAction"

    ids = list(ORDERS_TEXT_IDS)
    values = [SEARCH_TEXT if i == ORDERS_SEARCH_ENTRY else "" for i in ids]
    try:
        Gumps.SendAdvancedAction(ORDERS_GUMP, button, [], ids, values)
        return "SendAdvancedAction(filter=%r)" % SEARCH_TEXT
    except Exception as err:
        log("SendAdvancedAction failed (%s) - falling back to SendAction, "
            "which will clear the filter." % err, HUE_WARN)
        Gumps.SendAction(ORDERS_GUMP, button)
        return "SendAction (fallback)"


def dump_gump(gump_id, title):
    """Layout, strings and row pairing for one gump. Returns (strings, rows)."""
    rule(title)
    if not has_gump(gump_id):
        log("gump 0x%X is not open." % gump_id, HUE_BAD)
        return [], []

    layout = raw_layout(gump_id)
    strings = gump_lines(gump_id)
    data = gump_lines(gump_id, True)

    log("layout: %d chars, %d elements" % (len(layout), len(layout_elements(layout))))
    log("strings: %d   dataOnly: %d" % (len(strings), len(data)))

    shift = string_index_shift(layout, strings)
    if shift:
        log("%d empty string(s) dropped by Razor - the 'rows paired by Y' dump "
            "below is shifted by that much and is APPROXIMATE. The parsed "
            "orders are not: they are matched by shape." % shift, HUE_WARN)

    pages = re.findall(r"\{\s*page\s+(\d+)\s*\}", layout, re.I)
    if pages:
        log("PAGE MARKERS: %s -> client-side paging, every page is already here."
            % ", ".join(pages), HUE_GOOD)
    else:
        log("no { page N } markers -> server-side paging, or a single page.",
            HUE_WARN)

    buttons = layout_buttons(layout)
    log("buttons: %s" % (", ".join(str(b[2]) for b in buttons) or "none"))

    quiet("--- full layout: %s ---" % title)
    quiet(layout)

    quiet("--- strings ---")
    for i, line in enumerate(strings):
        quiet("  [%3d] %s" % (i, line))

    quiet("--- dataOnly ---")
    for i, line in enumerate(data):
        quiet("  [%3d] %s" % (i, line))

    rows = pair_rows(layout, strings)
    quiet("--- rows paired by Y ---")
    for row in rows:
        cells = " | ".join(str(v) for _x, v in row["cells"])
        btns = ",".join(str(b) for _x, b in row["buttons"]) or "-"
        quiet("  y=%-5d buttons=%-10s %s" % (row["y"], btns, cells))
    return strings, rows


def report_rows(rows, limit=14):
    """Show the paired rows in-game too - this is the answer we most need."""
    shown = 0
    for row in rows:
        cells = [str(v) for _x, v in row["cells"] if str(v).strip()]
        if not cells:
            continue
        btns = ",".join(str(b) for _x, b in row["buttons"]) or "-"
        log("  btn %-8s %s" % (btns, " | ".join(cells)[:110]))
        shown += 1
        if shown >= limit:
            log("  ... %d more rows, see the file." % (len(rows) - shown))
            break


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def section_chest2():
    """Dump the peerless chest verbatim - every name exactly as the item has it.

    This is the ground truth for the runner's name-matched entries: the order
    book truncates long names in its column, so several were transcribed with a
    guessed tail. Whatever this prints is what should be in RESOURCES.
    """
    rule("1b. peerless chest contents")
    if not CHEST2_SERIAL:
        log("CHEST2_SERIAL is 0 - skipped.")
        return None

    chest, how = find_world_item(CHEST2_SERIAL, CHEST2_ID, CHEST2_HUE, "chest 2")
    if chest is None:
        log("Second chest not found within %d tiles." % WORLD_RANGE, HUE_BAD)
        return None
    log("found via %s, %d tiles away" % (how, Player.DistanceTo(chest)), HUE_GOOD)
    for line in props(chest):
        log("  tooltip: %s" % spaced(line))

    if not open_container(chest, "chest 2"):
        log("Contents did not arrive - the list below may be short.", HUE_WARN)

    rows = list(chest.Contains or [])
    log("%d stack(s) inside" % len(rows))
    quiet("--- peerless chest, EXACT names ---")
    for item in sorted(rows, key=lambda i: strip_amount(i.Name or "")):
        bare = strip_amount(item.Name or "")
        amount = int(getattr(item, "Amount", 0) or 0)
        log("  %-34s x%-6d id=0x%04X hue=0x%04X"
            % (bare[:34], amount, int(item.ItemID), int(item.Hue)))
        quiet('    {"name": "%s", "id": 0x%04X, "hue": -1, "by": "name"},'
              % (bare, int(item.ItemID)))
        for line in props(item):
            quiet("        | %s" % spaced(line))
    log("The quiet log holds RESOURCES lines ready to paste.", HUE_INFO)
    return chest


def section_chest():
    rule("1. ingot census")

    chest, how = find_world_item(CHEST_SERIAL, CHEST_ID, CHEST_HUE, "chest")
    if chest is None:
        log("Chest not found within %d tiles. Stand next to it and rerun."
            % WORLD_RANGE, HUE_BAD)
        return None
    log("chest found via %s, %d tiles away" % (how, Player.DistanceTo(chest)),
        HUE_GOOD)
    for line in props(chest):
        log("  tooltip: %s" % spaced(line))

    if not open_container(chest, "chest"):
        log("Contents did not arrive - the census below may be short.", HUE_WARN)

    rows, ingots = census(chest)
    log("%d stacks in the chest, %d ingot types" % (len(rows), len(ingots)))

    quiet("--- every stack, with its full tooltip ---")
    for row in sorted(rows, key=lambda r: (-r["amount"], r["name"])):
        quiet("  %-30s x%-7d id=0x%04X hue=0x%04X %s"
              % (row["bare"][:30], row["amount"], row["id"], row["hue"],
                 row["metal"] if row["ingot"] else ""))
        for line in row["tooltip"]:
            quiet("        | %s" % spaced(line))

    if not ingots:
        log("No ingots matched %s. Check the tooltips in the file - the filler "
            "keys orders to stock by name." % INGOT_WORDS, HUE_WARN)
        return chest

    rule("fill budget (keep %d of each)" % KEEP_PER_TYPE)
    budget = fill_budget(ingots)
    for key in sorted(budget, key=lambda k: -budget[k]["have"]):
        entry = budget[key]
        detail = ingots[key]
        hue = HUE_GOOD if entry["available"] > 0 else HUE_WARN
        log("  %-30s have %-7d keep %-5d spend %-7d  ids=%s hues=%s"
            % (entry["name"][:30], entry["have"], entry["keep"],
               entry["available"],
               ",".join("0x%04X" % i for i in sorted(detail["ids"])),
               ",".join("0x%04X" % h for h in sorted(detail["hues"]))), hue)

    vanilla = [r for r in rows if r["id"] == VANILLA_INGOT_ID]
    log("stacks on the vanilla ingot graphic 0x%04X: %d of %d ingot stacks"
        % (VANILLA_INGOT_ID, len(vanilla),
           len([r for r in rows if r["ingot"]])))

    unknown = [k for k in ingots if k.startswith("unknown")]
    if unknown:
        log("%d stack(s) sit on a hue not in METAL_HUES: %s. Add them to the "
            "table - the filler cannot match an order to an unnamed metal."
            % (len(unknown), ", ".join(ingots[k]["name"] for k in unknown)),
            HUE_WARN)
    return chest


def section_deeds():
    rule("4. resource order deeds in the pack")
    backpack = Player.Backpack
    if backpack is None:
        log("No backpack.", HUE_BAD)
        return

    if not open_container(backpack, "backpack"):
        log("Backpack contents did not arrive.", HUE_WARN)

    hits = 0
    for item in list(backpack.Contains or []):
        tooltip = props(item)
        blob = " ".join([item.Name or ""] + tooltip)
        text = spaced(blob)
        if ("resource order" not in blob.lower()
                and "creature type" not in blob.lower()
                and not DEED_PROGRESS_RE.search(text)
                and not DEED_DONE_RE.search(text)):
            continue
        hits += 1
        raw = " ".join(tooltip)
        fields = parse_deed(raw)
        filled, needed = deed_progress(fields)
        log("deed 0x%X id=0x%04X" % (item.Serial, item.ItemID), HUE_GOOD)
        log("  raw:    %s" % raw[:160])
        log("  spaced: %s" % spaced(raw)[:160])
        log("  fields: %s" % ", ".join("%s=%r" % kv for kv in sorted(fields.items())))
        if filled is not None:
            log("  %s: %d/%d, %d to go"
                % (fields.get("resource", "?"), filled, needed, needed - filled),
                HUE_GOOD)
        else:
            log("  DID NOT PARSE - the tooltip above does not match "
                "'N / M <resource> Obtained'.", HUE_BAD)
        quiet("--- deed 0x%X full tooltip ---" % item.Serial)
        for line in tooltip:
            quiet("  %s" % line)

    if not hits:
        log("No order deeds in the pack. Withdraw one by hand and rerun this - "
            "the deed's real tooltip is what tells the filler how to fill it.",
            HUE_WARN)


def section_book():
    rule("2. the book's own window")

    book, how = find_world_item(BOOK_SERIAL, BOOK_ID, BOOK_HUE, "book")
    if book is None:
        log("Book not found within %d tiles." % WORLD_RANGE, HUE_BAD)
        return False
    log("book found via %s, %d tiles away" % (how, Player.DistanceTo(book)),
        HUE_GOOD)
    for line in props(book):
        log("  tooltip: %s" % spaced(line))

    # WaitForGump returns True for a gump that is ALREADY open, so anything
    # left over from a previous run would be dumped instead of the real thing.
    Gumps.CloseGump(BOOK_GUMP)
    Gumps.CloseGump(ORDERS_GUMP)
    Misc.Pause(SETTLE_MS)

    Items.UseItem(book)
    Gumps.WaitForGump(BOOK_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)

    if not has_gump(BOOK_GUMP):
        log("Book gump 0x%X never opened. Open gumps now: %s"
            % (BOOK_GUMP, [hex(g) for g in Gumps.AllGumpIDs()]), HUE_BAD)
        return False

    strings, rows = dump_gump(BOOK_GUMP, "book gump 0x%X" % BOOK_GUMP)
    report_rows(rows)
    log("The button that WITHDRAWS an order is in the list above and is not "
        "pressed by this script - that is the thing to identify.", HUE_WARN)
    return True


def section_orders():
    rule("3. the order list")

    if not has_gump(BOOK_GUMP):
        log("Book gump is gone, cannot reach the order list.", HUE_BAD)
        return

    log("pressing button %d on 0x%X (confirmed: opens Resource Orders)"
        % (BOOK_ORDERS_BUTTON, BOOK_GUMP))
    Gumps.SendAction(BOOK_GUMP, BOOK_ORDERS_BUTTON)
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)

    if not has_gump(ORDERS_GUMP):
        log("Order list 0x%X never opened. Open gumps now: %s"
            % (ORDERS_GUMP, [hex(g) for g in Gumps.AllGumpIDs()]), HUE_BAD)
        return

    if SEARCH_TEXT is not None:
        # Submit through the Name column's OWN button (12), not the next-page
        # button. The first run applied the filter via next-page, which worked
        # but also skipped a page - the filter and the paging are separate
        # controls and conflating them loses a page of orders every time.
        log("applying the Name filter %r via text entry %d, submit button %d"
            % (SEARCH_TEXT, ORDERS_SEARCH_ENTRY, ORDERS_FILTER_SUBMIT))
        how = send_orders_action(ORDERS_FILTER_SUBMIT)
        Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
        Misc.Pause(SETTLE_MS)
        log("  via %s" % how)
        if not has_gump(ORDERS_GUMP):
            log("The list closed when the filter was submitted - button %d is "
                "not the Name filter submit." % ORDERS_FILTER_SUBMIT, HUE_BAD)
            return

    seen = []
    last_page_rows = []
    for page in range(1, PAGES_TO_DUMP + 1):
        strings, rows = dump_gump(
            ORDERS_GUMP, "order list 0x%X page %d" % (ORDERS_GUMP, page))
        if not strings:
            break

        header = parse_header(strings)
        if header:
            log("header: stored %s/%s, displayed %s"
                % (header.get("stored"), header.get("capacity"),
                   header.get("displayed")))

        current, total = page_counter(strings)
        if current:
            log("page %s of %s" % (current, total))

        orders = parse_order_rows(strings)
        buttons = row_buttons(raw_layout(ORDERS_GUMP))
        log("parsed %d order rows against %d row buttons"
            % (len(orders), len(buttons)),
            HUE_GOOD if len(orders) == len(buttons) else HUE_BAD)
        if len(orders) != len(buttons):
            log("MISMATCH - the row parser and the layout disagree, so nothing "
                "below can be trusted to name the right button.", HUE_BAD)

        quiet("--- orders zipped to buttons ---")
        for order, button in zip(orders, buttons):
            line = "  btn %-5s %-28s amt %s" % (
                button, order["name"][:28],
                "?" if order["amount"] is None else order["amount"])
            quiet(line)
        for order, button in list(zip(orders, buttons))[:6]:
            log("  btn %-5s %-24s amt %s"
                % (button, order["name"][:24],
                   "?" if order["amount"] is None else order["amount"]))
        if len(orders) > 6:
            log("  ... %d more, see the file." % (len(orders) - 6))

        last_page_rows = list(zip(orders, buttons))

        fingerprint = tuple(strings)
        if fingerprint in seen:
            log("This page repeats an earlier one - paging has wrapped or "
                "button %d is not next-page." % ORDERS_NEXT_BUTTON, HUE_WARN)
            break
        seen.append(fingerprint)

        if page == PAGES_TO_DUMP:
            break

        how = send_orders_action(ORDERS_NEXT_BUTTON)
        Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
        Misc.Pause(SETTLE_MS)
        if not has_gump(ORDERS_GUMP):
            log("The list closed after pressing %d (%s)."
                % (ORDERS_NEXT_BUTTON, how), HUE_WARN)
            break

    section_vocabulary()
    section_survey()
    section_probe(last_page_rows)


def apply_name_filter(text):
    """Type `text` into the Name column filter and submit it.

    Returns the refreshed (strings, layout) or (None, None) if the list closed.
    """
    ids = list(ORDERS_TEXT_IDS)
    values = [text if i == ORDERS_SEARCH_ENTRY else "" for i in ids]
    try:
        Gumps.SendAdvancedAction(ORDERS_GUMP, ORDERS_FILTER_SUBMIT, [], ids, values)
    except Exception as err:
        log("filter %r failed: %s" % (text, err), HUE_BAD)
        return None, None
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    if not has_gump(ORDERS_GUMP):
        return None, None
    return gump_lines(ORDERS_GUMP), raw_layout(ORDERS_GUMP)


def section_vocabulary():
    """List the names the book ACTUALLY uses, per broad term.

    The runner matches a resource by the book's exact name, and the book does
    not always use the metal's real name - Shadow Iron is listed as "Shadow
    Ingots". A wrong name returns an empty filter, so the resource looks
    skipped instead of erroring. This dumps the real vocabulary so the
    RESOURCES table can be set from it rather than guessed.
    """
    rule("7. the book's own names")
    if not has_gump(ORDERS_GUMP):
        log("Order list is not open.", HUE_BAD)
        return

    for term in VOCABULARY_TERMS:
        strings, layout = apply_name_filter(term)
        if strings is None:
            log("%-12s list closed while filtering" % term, HUE_BAD)
            break

        header = parse_header(strings)
        displayed = header.get("displayed")
        _page, pages = page_counter(strings)

        names = {}
        for page in range(1, VOCABULARY_PAGES + 1):
            for row in parse_order_rows(strings):
                name = row["name"].strip()
                if not name or not row["amount"]:
                    continue
                names[name] = names.get(name, 0) + 1
            if pages is None or page >= min(pages, VOCABULARY_PAGES):
                break
            if not orders_action(ORDERS_NEXT_BUTTON, term):
                break
            strings = gump_lines(ORDERS_GUMP)

        log("%-12s displayed %-5s pages %-4s -> %s"
            % (term, displayed if displayed is not None else "?",
               pages if pages is not None else "?",
               ", ".join("%s (x%d)" % (n, c)
                         for n, c in sorted(names.items())) or "nothing"),
            HUE_GOOD if names else HUE_WARN)

        quiet("--- vocabulary: %r ---" % term)
        for name, count in sorted(names.items()):
            quiet("    %-30s seen %d" % (name, count))

    log("Copy these EXACT names into RESOURCES in resource_order_runner.py.",
        HUE_INFO)


def section_survey():
    """Count the orders for each metal's ingots. This is the shopping list."""
    rule("6. what is actually fillable")
    if not SURVEY_METALS:
        log("SURVEY_METALS is empty, skipped.")
        return
    if not has_gump(ORDERS_GUMP):
        log("Order list is not open, cannot survey.", HUE_BAD)
        return

    log("filtering the Name column once per metal - the book holds thousands "
        "of orders and only these are worth paging through.")

    results = []
    for metal in SURVEY_METALS:
        term = metal + SURVEY_SUFFIX
        strings, layout = apply_name_filter(term)
        if strings is None:
            log("%-14s list closed while filtering - stopping the survey."
                % metal, HUE_BAD)
            break

        header = parse_header(strings)
        displayed = header.get("displayed")
        _page, pages = page_counter(strings)
        orders = [o for o in parse_order_rows(strings) if o["amount"]]

        # Every row shares the filter term, so a result naming something else
        # means the substring matched a resource we did not mean.
        names = set(o["name"].lower() for o in orders)
        stray = [n for n in names if term.lower() not in n]

        results.append({"metal": metal, "term": term, "displayed": displayed,
                        "pages": pages, "sample": orders[:3], "stray": stray})

        hue = HUE_GOOD if displayed else HUE_WARN
        log("%-14s displayed %-6s pages %-4s  %s"
            % (metal, displayed if displayed is not None else "?",
               pages if pages is not None else "?",
               ", ".join("%s x%s" % (o["name"], o["amount"])
                         for o in orders[:2]) or "nothing"), hue)
        if stray:
            log("   filter also matched: %s" % ", ".join(sorted(stray)), HUE_WARN)

        quiet("--- survey: %s ---" % term)
        for order in orders:
            quiet("    %-28s amt %s" % (order["name"], order["amount"]))

    fillable = [r for r in results if r["displayed"]]
    if fillable:
        log("%d of %d metals have ingot orders waiting."
            % (len(fillable), len(results)), HUE_GOOD)
    else:
        log("NO ingot orders for any metal in stock. Everything in the book is "
            "for other resources - there is nothing for the filler to do yet.",
            HUE_WARN)


def pack_snapshot():
    """{serial: amount} for the backpack, to diff across an action."""
    backpack = Player.Backpack
    if backpack is None:
        return {}
    return dict((int(i.Serial), int(getattr(i, "Amount", 0) or 0))
                for i in list(backpack.Contains or []))


def section_probe(page_rows):
    """Press ONE row button and report what it did. Opt-in, see PROBE_ROW_BUTTON."""
    rule("5. row button probe")
    if not PROBE_ROW_BUTTON:
        log("PROBE_ROW_BUTTON is off. The row buttons are the likely "
            "'withdraw this order' control but nothing proves it, and Add / "
            "Purge / Fill from backpack sit on the same gump.", HUE_INFO)
        log("Set PROBE_ROW_BUTTON = True to press the FIRST row on the last "
            "page dumped, and rerun.", HUE_INFO)
        return
    if not page_rows:
        log("No parsed rows to probe.", HUE_BAD)
        return
    if not has_gump(ORDERS_GUMP):
        log("Order list is not open, nothing to probe.", HUE_BAD)
        return

    order, button = page_rows[0]
    log("PRESSING row button %d - order '%s', amt %s"
        % (button, order["name"], order["amount"]), HUE_WARN)

    before = pack_snapshot()
    before_gumps = [hex(g) for g in Gumps.AllGumpIDs()]

    send_orders_action(button)
    Misc.Pause(GUMP_TIMEOUT_MS // 5)

    after_gumps = [hex(g) for g in Gumps.AllGumpIDs()]
    log("gumps before: %s" % before_gumps)
    log("gumps after:  %s" % after_gumps)
    new_gumps = [g for g in after_gumps if g not in before_gumps]
    if new_gumps:
        log("NEW GUMP(S): %s - dump these next." % new_gumps, HUE_GOOD)

    backpack = Player.Backpack
    if backpack is not None:
        Items.WaitForContents(backpack, CONTENTS_TIMEOUT_MS)
        Misc.Pause(SETTLE_MS)
    after = pack_snapshot()
    added = [s for s in after if s not in before]
    changed = [s for s in after if s in before and after[s] != before[s]]

    if added:
        log("%d new item(s) in the pack:" % len(added), HUE_GOOD)
        for serial in added:
            item = Items.FindBySerial(serial)
            if item is None:
                continue
            name, tooltip = describe(item)
            log("  0x%X id=0x%04X x%d  %s" % (serial, item.ItemID,
                                              after[serial], name))
            for line in tooltip:
                log("    | %s" % spaced(line))
            fields = parse_deed(" ".join(tooltip))
            if fields:
                log("    parsed: %s"
                    % ", ".join("%s=%r" % kv for kv in sorted(fields.items())))
    elif changed:
        log("no new items, but %d stack(s) changed amount: %s"
            % (len(changed), ", ".join("0x%X" % s for s in changed)), HUE_WARN)
    else:
        log("Nothing appeared in the pack. The row button does something other "
            "than withdraw - check the gump list above.", HUE_WARN)


def write_file():
    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(_lines))
        Misc.SendMessage("[RO] Written to %s" % DUMP_PATH, HUE_GOOD, False)
    except Exception as err:
        Misc.SendMessage("[RO] Could not write the dump: %s" % err, HUE_BAD, False)


def main():
    started = time.time()
    rule("resource order diagnostic")
    log("%s at (%d, %d, %d)"
        % (Player.Name, Player.Position.X, Player.Position.Y, Player.Position.Z))
    log("read-only: it presses book button %d and list button %d, nothing else."
        % (BOOK_ORDERS_BUTTON, ORDERS_NEXT_BUTTON))

    try:
        section_chest()
        section_chest2()
        if section_book():
            section_orders()
        section_deeds()
    except Exception as err:
        log("ABORTED: %s" % err, HUE_BAD)

    rule("done in %.1fs" % (time.time() - started))
    write_file()


main()
