"""
Sandmaker - one granite at a time, stone to sand.
=================================================

For Razor Enhanced (IronPython 3.4). Target: the UOAlive / Beyond Sosaria
freeshard.

THE ROUND
---------
    withdraw ONE Plain granite from the Stone Storage
    walk to the converter box and drop it in      (the conversion is instant)
    walk to wherever the sand came out and pick it up

Repeated RUNS times.

WHAT THIS IS NOT
----------------
It is not the recorded macro. That one disconnected the client on its first
run, and it is worth saying exactly why, because two of the three reasons are
invisible in a recording:

    Gumps.SendAdvancedAction(0x6abce12, 21, [], [0], ["1"])
    Gumps.WaitForGump(0x6abce12, 10000)      <- the window is GONE by now
    Gumps.SendAction(0x6abce12, 1)           <- answering a window that closed

  * A gump response CLOSES the gump. By the third line the client no longer
    has that window, and answering a gump you do not have is a drop. The
    WaitForGump between them does not help: nothing reads what it returned.
  * Four Player.Run/Walk calls back to back with no delay. Servers have
    fastwalk protection and a recorder replays keystrokes instantly.
  * Three Items.Move with no pause, against a ~900ms drag limit.

And the serials in it cannot be reused. 0x40BB6349 was that one withdrawal's
granite and 0x40BB64E1 was that one piece of sand; both are new items every
time. Only the CONTAINERS are stable, so only containers are configured by
serial here - the stone is found by graphic and the sand by diffing the ground.

WHAT IS STILL UNKNOWN
---------------------
WITHDRAW_BUTTON. This script REFUSES TO RUN until it is set, and that is
deliberate: the Stone Storage lists ten granite types and pressing the wrong
row withdraws the wrong stone, while pressing a row the server did not draw
disconnects you. Run Scripts/diag_storage_gump.py, read the button on the
"Plain" row, and put it here. Do not guess it from its neighbours - the
numbering is per-container.

SAND_ID is unknown too, but that one costs nothing: the sand is found by
diffing the ground before and after the drop, and the first run PRINTS the
graphic it learned so it can be filled in later.
"""

import re
import time


# Printed as the first line at startup, like every other script here. Razor
# CACHES the loaded script even after the file on disk changes, and this repo
# has already lost two debugging rounds to a bug that was fixed on disk and not
# in the folder Razor reads. If this line does not say what you expect, hit
# Reload in the Scripting tab.
SCRIPT_VERSION = "2026-09-18.1"


# =============================================================================
# CONFIG - THE THINGS YOU MUST SET
# =============================================================================

# The Stone Storage. From the recording; it is locked down, so the serial is
# stable in a way the stones inside it are not.
STONE_STORAGE_SERIAL = 0x4017817A

# The shared stash window every storage key on this shard opens.
# resource_order_runner.py calls it BOOK_GUMP, harvest_runner.py calls it
# HOUSE_DEPOSIT_GUMP.
STASH_GUMP = 0x06ABCE12

# THE BUTTON THAT WITHDRAWS PLAIN GRANITE.
#
# 0 means FIND IT, which is the default and the better answer. The window is
# open in front of us; the button on the row labelled STONE_LABEL is read off
# the live layout every time, so it cannot be stale and it cannot be a button
# the server did not draw - it came FROM what the server drew.
#
# The recorded macro pressed 21, and this window lists ten stones: Plain, Dull,
# Shadow, Copper, Bronze, Gold, Agapite, Verite, Valorite, Mythril. Nothing
# ever confirmed 21 was Plain's row rather than one of the other nine, which is
# why it is not written here as though it had been.
#
# Set a number to override the search - useful if the label ever stops
# matching. It is still checked against the drawn set before it is pressed.
WITHDRAW_BUTTON = 0

# WHAT THE GUMP INSPECTOR SAID, 2026-09-18: button 1 withdraws the granite.
#
# Used two ways, neither of them "instead of looking":
#   * as the FALLBACK when the row cannot be read off the window
#   * as a CROSS-CHECK when it can - a disagreement means the rows have moved
#     and it is said out loud rather than resolved silently
#
# The search wins a disagreement, because it has a guard this number does not:
# it refuses when the string table is short, whereas a number typed here goes
# stale the moment somebody reorders the window and nothing notices.
#
# It also explains the recorded macro. That sent button 21 with the amount and
# THEN button 1 - so 1 was the withdraw all along, and 21 was whatever commits
# the amount box. The macro died on the second press only because the first had
# already closed the window.
WITHDRAW_BUTTON_CONFIRMED = 1

# How far apart, vertically, a label and its button may sit and still be on the
# same row.
ROW_TOLERANCE = 12

# What the withdraw press types into the amount box. The converter takes one
# stone at a time.
WITHDRAW_AMOUNT = 1

# THE CONVERTER. Inspected 2026-09-18:
#     "Granite Crate", 0x402452BA, ItemID 0x0E3D, hue 0x0000
#     at (2071, 2506, 2), locked down, Container: YES
# A granite dropped IN here becomes sand immediately.
BOX_SERIAL = 0x402452BA
BOX_ID = 0x0E3D
BOX_SPOT = (2071, 2506)

# WHERE THE SAND COMES OUT. Inspected the same day:
#     "platform", 0x402452B1, ItemID 0x07BD, hue 0x0000
#     at (2073, 2504, 3), locked down, Container: NO
#
# NOT a container. The sand lands ON it, which makes it a GROUND item at
# roughly the platform's tile - so it is found by looking at the ground, not
# by opening anything. Two tiles from the crate, so one ground snapshot taken
# beside the crate already covers it.
PLATFORM_SERIAL = 0x402452B1
PLATFORM_ID = 0x07BD
PLATFORM_SPOT = (2073, 2504)

# How close to the platform a new ground item has to be to be the sand.
# Generous - the exact tile it settles on is the server's business - but not
# so wide that something dropped elsewhere in the room qualifies.
SAND_NEAR_PLATFORM = 3

# How many stones to convert. 0 means "keep going until the storage runs out
# or something goes wrong".
RUNS = 1


# =============================================================================
# CONFIG - THE THINGS THAT ARE ALREADY KNOWN
# =============================================================================

# Granite, and the hue this shard's windows disagree about the name of:
#   the Stone Storage calls hue 0x0000 "Plain"
#   the Resource Order Book calls it   "High Quality Granite"
#   the stack itself is named          "high quality granite"
# Three names, one stone. See docs/resource-order-handoff.md.
GRANITE_ID = 0x1779
GRANITE_HUE = 0x0000

# What the Stone Storage calls it, for reading the row off the window.
STONE_LABEL = "Plain"

# THE SAND. Inspected 2026-09-18, after a piece had been picked up:
#     Name "sand", ItemID 0x423A, hue 0x096D, Weight 1 Stone
#     Container: the backpack, Movable: Yes
#
# The graphic is what identifies it. The hue is NOT pinned: 0x096D happens to
# be the hue the order book gives Copper Granite, which is either a coincidence
# of palette or a sign that the sand takes its colour from the stone that made
# it. Only Plain granite is ever converted here so it should not vary - but
# 0x423A is distinctive on its own, the search is already anchored on the
# platform, and the item is already known to be NEW. Three filters is enough;
# a fourth that might be wrong is not worth having.
#   -1 = any hue.
SAND_ID = 0x423A
SAND_HUE = -1
SAND_NAMES = ["sand"]

# How far to look for the sand after the drop, and how long to give it. The
# conversion is instant, but the item still has to reach the client.
SAND_RANGE = 8
SAND_WAIT_MS = 3000


# =============================================================================
# CONFIG - TIMING
# =============================================================================

# The drag rate limit on this shard. Every Items.Move waits this long after.
MOVE_PAUSE_MS = 900

GUMP_TIMEOUT_MS = 10000
SETTLE_MS = 700

# Walking. PathFinding, not replayed keystrokes - see the header.
WALK_TIMEOUT_MS = 20000
WALK_POLL_MS = 250
REACH_DISTANCE = 2          # how close to stand before dragging

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Sand] " + text, hue, False)


def raw_layout(gump_id):
    try:
        return Gumps.GetGumpRawLayout(gump_id) or ""
    except Exception:
        return ""


def gump_lines(gump_id):
    """The gump's strings, in layout order. [] when there is no window.

    A NULL return means "not open", not an error - list(None) surfaces as a
    TypeError about iteration from wherever happened to ask.
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


def has_gump(gump_id):
    try:
        return bool(Gumps.HasGump(gump_id))
    except Exception:
        return False


def layout_text_cells(gump_id):
    """(x, y, text) for every text cell, paired BY ORDER.

    NOT by the text id in the layout. Razor drops empty strings out of a gump's
    string table without leaving a gap, so one blank cell shifts every later id
    down by one - see CLAUDE.md. Element order is the only safe pairing, and it
    is only safe while the counts agree, which find_stone_row checks.
    """
    lines = gump_lines(gump_id)
    cells, index = [], 0
    for piece in re.findall(r"\{([^{}]*)\}", raw_layout(gump_id)):
        piece = piece.strip()
        kind = piece.split()[0].lower() if piece else ""
        if kind not in ("text", "croppedtext"):
            continue
        nums = [int(n) for n in re.findall(r"-?\d+", piece)]
        text = lines[index] if index < len(lines) else ""
        index += 1
        if len(nums) >= 2:
            cells.append((nums[0], nums[1], str(text or "").strip()))
    return cells


def layout_buttons(gump_id):
    """(x, y, id) for every button the server drew, with its position."""
    out = []
    for piece in re.findall(r"\{([^{}]*)\}", raw_layout(gump_id)):
        piece = piece.strip()
        if not piece.lower().startswith("button"):
            continue
        nums = [int(n) for n in re.findall(r"-?\d+", piece)]
        if len(nums) >= 3:
            out.append((nums[0], nums[1], nums[-1]))
    return out


def find_stone_row(label):
    """(button, count) for the row named `label`. (0, "") if it is not there.

    THE POINT OF THIS FUNCTION. A button id read off the live window cannot be
    stale and cannot be one the server did not draw, because it came from what
    the server drew. A number typed into config is neither of those things -
    and this window lists ten stones, so a number that is one row out
    withdraws the wrong one in silence.

    Refuses rather than guesses when the string table is short. A shifted table
    puts the wrong label on every row after the gap, which would point this
    straight at a neighbour.
    """
    cells = layout_text_cells(STASH_GUMP)
    strings = gump_lines(STASH_GUMP)
    if not cells:
        return 0, ""
    if len(strings) != len(cells):
        log("%d text cell(s) but %d string(s) on this window - the table is "
            "short, so the labels may belong to the row above. Not choosing a "
            "button from it." % (len(cells), len(strings)), HUE_BAD)
        return 0, ""

    want = str(label or "").strip().lower()
    for i, (cx, cy, text) in enumerate(cells):
        if str(text or "").strip().lower() != want:
            continue
        # The count is the next cell on the same row - "Plain" then "59999".
        count = ""
        if i + 1 < len(cells) and abs(cells[i + 1][1] - cy) <= ROW_TOLERANCE:
            count = cells[i + 1][2]
        # The button on that row, preferring one to the right of the label.
        same_row = [(bx, bid) for bx, by, bid in layout_buttons(STASH_GUMP)
                    if abs(by - cy) <= ROW_TOLERANCE]
        if not same_row:
            continue
        right = sorted((bx, bid) for bx, bid in same_row if bx >= cx)
        button = right[0][1] if right else sorted(same_row)[-1][1]
        return button, count
    return 0, ""


def drawn_buttons(gump_id):
    """Every button id the server actually drew on this window.

    PRESSING ONE IT DID NOT DRAW DISCONNECTS YOU, so this is checked before
    every press rather than trusted from config.
    """
    out = set()
    for piece in re.findall(r"\{([^{}]*)\}", raw_layout(gump_id)):
        piece = piece.strip()
        if not piece.lower().startswith("button"):
            continue
        nums = [int(n) for n in re.findall(r"-?\d+", piece)]
        if len(nums) >= 3:
            out.add(nums[-1])
    return out


def label_after(strings, label):
    """The string straight after `label`. "" when the label is not there.

    How the Withdrawal Amount is read. Positional on purpose: the text entry
    carries an InitialTextID that should point at the same string, but Razor
    drops empty strings out of the table without leaving a gap, so every id
    past the first blank is off by one. See CLAUDE.md.
    """
    low = str(label or "").strip().lower()
    for i, text in enumerate(strings):
        if low in str(text or "").strip().lower():
            if i + 1 < len(strings):
                return str(strings[i + 1]).strip()
            return ""
    return ""


def pack_serials():
    """Serials at the top level of the backpack."""
    out = set()
    pack = Player.Backpack
    if pack is None:
        return out
    try:
        for item in list(getattr(pack, "Contains", None) or []):
            out.add(int(item.Serial))
    except Exception:
        pass
    return out


def refresh_pack():
    """Re-open the backpack so its Contains list is current.

    Contains is a SNAPSHOT taken when the container was opened, and asking a
    different way does not help - Items.FindAllByID with a container serial
    walks that same list. Re-opening is the only real refresh. See CLAUDE.md.
    """
    pack = Player.Backpack
    if pack is None:
        return
    try:
        Items.UseItem(pack)
        Items.WaitForContents(pack, 4000)
    except Exception:
        pass
    Misc.Pause(SETTLE_MS)


def ground_serials(rng):
    """Serials of everything on the ground within `rng` tiles."""
    out = set()
    try:
        f = Items.Filter()
        f.Enabled = True
        f.OnGround = 1
        f.RangeMax = rng
        for item in list(Items.ApplyFilter(f) or []):
            out.add(int(item.Serial))
    except Exception:
        pass
    return out


def item_name(item):
    """An item's name, from the tooltip when the field is blank."""
    try:
        name = (item.Name or "").strip()
    except Exception:
        name = ""
    if name:
        return name
    try:
        Items.WaitForProps(item, 1000)
        for line in list(Items.GetPropStringList(item) or []):
            line = (line or "").strip()
            if line:
                return line
    except Exception:
        pass
    return ""


def distance_to(item):
    try:
        return max(abs(Player.Position.X - item.Position.X),
                   abs(Player.Position.Y - item.Position.Y))
    except Exception:
        return 999


def walk_to(x, y, accept=REACH_DISTANCE):
    """Walk to a tile with PathFinding. True once within `accept`.

    NOT replayed keystrokes. A recorder captures Player.Run/Walk and replays
    them instantly, which is both fragile - it assumes you start where the
    recording started - and a way to be dropped for fastwalk.
    """
    deadline = time.time() + WALK_TIMEOUT_MS / 1000.0
    while time.time() < deadline:
        here = max(abs(Player.Position.X - x), abs(Player.Position.Y - y))
        if here <= accept:
            return True
        route = PathFinding.Route()
        route.X = int(x)
        route.Y = int(y)
        route.MaxRetry = 2
        route.StopIfStuck = True
        route.IgnoreMobile = True
        route.UseResync = True
        route.DebugMessage = False
        try:
            PathFinding.Go(route)
        except Exception as err:
            log("pathfinding to %d,%d raised %r" % (x, y, err), HUE_WARN)
            return False
        Misc.Pause(WALK_POLL_MS)
    return max(abs(Player.Position.X - x),
               abs(Player.Position.Y - y)) <= accept


def walk_to_item(item, what):
    """Get within reach of an item that is out in the world."""
    if item is None:
        return False
    if distance_to(item) <= REACH_DISTANCE:
        return True
    try:
        x, y = int(item.Position.X), int(item.Position.Y)
    except Exception:
        log("%s has no position to walk to." % what, HUE_BAD)
        return False
    log("walking to %s at %d,%d" % (what, x, y))
    if not walk_to(x, y):
        log("Could not reach %s - it is %d tiles away." % (what,
                                                           distance_to(item)),
            HUE_BAD)
        return False
    return True


def move_one(item, target_serial, what):
    """Drag ONE of `item` into `target_serial`. True only if it really moved.

    Verified by result. A refused drag is silent - the packet goes out, nothing
    happens, and the next step runs as though it had worked.
    """
    serial = int(item.Serial)
    try:
        Items.Move(item, int(target_serial), 1)
    except Exception as err:
        log("could not drag %s: %r" % (what, err), HUE_BAD)
        return False
    Misc.Pause(MOVE_PAUSE_MS)

    moved = Items.FindBySerial(serial)
    if moved is None:
        return True             # consumed on arrival, which the box does
    try:
        if int(getattr(moved, "Container", 0) or 0) == int(target_serial):
            return True
    except Exception:
        pass
    # Still where it was. Say the distance, because out of range is the usual
    # reason and it is the one the walk was supposed to have fixed.
    log("%s did not move - it is %d tiles away and still in %s."
        % (what, distance_to(moved),
           "your pack" if int(getattr(moved, "Container", 0) or 0)
           else "the world"), HUE_BAD)
    return False


# =============================================================================
# THE ROUND
# =============================================================================

def open_storage():
    """Open the Stone Storage. Returns its item, or None."""
    storage = Items.FindBySerial(STONE_STORAGE_SERIAL)
    if storage is None:
        log("Stone Storage 0x%X not found." % STONE_STORAGE_SERIAL, HUE_BAD)
        return None

    # WaitForGump returns True for a window that is ALREADY open, so a
    # leftover one has to go before this one is asked for.
    try:
        Gumps.CloseGump(STASH_GUMP)
    except Exception:
        pass
    Misc.Pause(SETTLE_MS)

    Items.UseItem(storage)
    Gumps.WaitForGump(STASH_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    if not has_gump(STASH_GUMP):
        log("The Stone Storage window never opened.", HUE_BAD)
        return None
    return storage


def check_amount():
    """Is the Withdrawal Amount box set to what we are about to send?

    The amount travels WITH the press - SendAdvancedAction carries it - so
    this is a cross-check rather than the mechanism. It is worth having
    because the converter takes one stone at a time, and a box left reading 50
    from a previous session is the kind of thing that empties into the floor.
    """
    shown = label_after(gump_lines(STASH_GUMP), "Withdrawal Amount")
    if not shown:
        log("Could not read the Withdrawal Amount - carrying on, the press "
            "sends %d with it anyway." % WITHDRAW_AMOUNT, HUE_WARN)
        return True
    if shown == str(WITHDRAW_AMOUNT):
        log("Withdrawal Amount reads %s." % shown, HUE_GOOD)
        return True
    log("Withdrawal Amount reads %r, not %d. The press sends %d with it, so "
        "this should still take one - but if more than one comes out, stop "
        "and set the box by hand."
        % (shown, WITHDRAW_AMOUNT, WITHDRAW_AMOUNT), HUE_WARN)
    return True


def withdraw_one():
    """Take one Plain granite out. Returns the granite item, or None."""
    if open_storage() is None:
        return None
    if not check_amount():
        return None

    button = choose_button()
    if not button:
        return None

    drawn = drawn_buttons(STASH_GUMP)
    if drawn and button not in drawn:
        log("The server did NOT draw button %d on this window, and pressing "
            "one it did not draw disconnects you. Drawn: %s"
            % (button, sorted(drawn)[:20]), HUE_BAD)
        return None

    before = pack_serials()
    log("withdrawing %d %s (button %d)"
        % (WITHDRAW_AMOUNT, STONE_LABEL, button))
    try:
        Gumps.SendAdvancedAction(STASH_GUMP, button, [], [0],
                                 [str(WITHDRAW_AMOUNT)])
    except Exception as err:
        log("the withdraw press failed: %r" % err, HUE_BAD)
        return None
    Misc.Pause(SETTLE_MS)

    # NOTHING is pressed on that window again. The response closed it, and a
    # second press would be answering a window the client no longer has.
    refresh_pack()

    for serial in [s for s in pack_serials() if s not in before]:
        item = Items.FindBySerial(serial)
        if item is None:
            continue
        try:
            if int(item.ItemID) == GRANITE_ID:
                log("got %s, serial 0x%X" % (item_name(item) or "granite",
                                             serial), HUE_GOOD)
                return item
        except Exception:
            continue

    log("Nothing that looks like granite (0x%04X) arrived in the pack. Either "
        "button %d is not the %s row, or the storage is empty."
        % (GRANITE_ID, WITHDRAW_BUTTON, STONE_LABEL), HUE_BAD)
    return None


def tiles_between(item, spot):
    """Distance from an item to an (x, y). 999 when it cannot be measured."""
    try:
        return max(abs(int(item.Position.X) - int(spot[0])),
                   abs(int(item.Position.Y) - int(spot[1])))
    except Exception:
        return 999


def platform_spot():
    """Where the sand comes out - the live platform if it is in range.

    Falls back to the inspected coordinates, because a serial that has not
    loaded yet is not the same thing as a platform that has moved. It is
    locked down; it has not moved.
    """
    item = Items.FindBySerial(PLATFORM_SERIAL)
    if item is not None:
        try:
            return (int(item.Position.X), int(item.Position.Y))
        except Exception:
            pass
    return PLATFORM_SPOT


def choose_button():
    """Which button to press for STONE_LABEL. 0 when there is no safe answer.

    THE CONFIRMED NUMBER WINS. This used to be the other way round and it was
    wrong: on 2026-09-18 the row search returned 6 for the "Plain" row, the
    Gump Inspector had said 1, the search was believed, and pressing 6
    disconnected the client.

    Why the search loses: it infers a button from GEOMETRY - the label's Y, a
    tolerance, and a preference for whatever sits to its right. Every one of
    those is a guess about how the window is drawn. A Gump Inspector reading is
    not an inference at all; it is the id the server received when a human
    clicked the thing they meant. This project's rule is that shard data comes
    from source or a live dump, and a live dump is exactly what the Inspector
    produces.

    The search is still run, as a CROSS-CHECK. A disagreement means one of the
    two is stale and it is said loudly - but it no longer decides anything.

    With no confirmed number at all, nothing is pressed. A search that has been
    wrong once does not get to pick a button on a window where the wrong press
    disconnects you.
    """
    if WITHDRAW_BUTTON:
        return WITHDRAW_BUTTON

    found, count = find_stone_row(STONE_LABEL)

    if count and count.strip() in ("0", ""):
        log("The %r row reads %r - there is none left to withdraw."
            % (STONE_LABEL, count), HUE_BAD)
        return 0

    if not WITHDRAW_BUTTON_CONFIRMED:
        log("No confirmed button for %r, and the row search is not trusted to "
            "choose one - it returned 6 for this row once when the answer was "
            "1, and the wrong press disconnects you. Set "
            "WITHDRAW_BUTTON_CONFIRMED from the Gump Inspector."
            % STONE_LABEL, HUE_BAD)
        return 0

    if found and found != WITHDRAW_BUTTON_CONFIRMED:
        log("the row search says button %d, the Gump Inspector says %d. Using "
            "%d - the Inspector read it off a real click, the search only "
            "infers it from where the label sits."
            % (found, WITHDRAW_BUTTON_CONFIRMED, WITHDRAW_BUTTON_CONFIRMED),
            HUE_WARN)

    return WITHDRAW_BUTTON_CONFIRMED


def find_sand(new_serials):
    """The sand, out of the serials that appeared after the drop.

    Anchored on the PLATFORM rather than on the player. The sand lands on it,
    and something else appearing across the room in the same second is not the
    sand however new it is.
    """
    spot = platform_spot()
    candidates = []
    for serial in new_serials:
        item = Items.FindBySerial(serial)
        if item is None:
            continue
        if tiles_between(item, spot) > SAND_NEAR_PLATFORM:
            continue
        candidates.append(item)

    # BY GRAPHIC FIRST, now that it is known. A graphic is a fact about the
    # item; a name has to be read off a tooltip that may not have arrived yet,
    # and item_name falls back to WaitForProps for exactly that reason.
    if SAND_ID:
        for item in candidates:
            try:
                if int(item.ItemID) != SAND_ID:
                    continue
                if SAND_HUE >= 0 and int(item.Hue) != SAND_HUE:
                    continue
                return item
            except Exception:
                continue

    # Then by name - but ONLY while the graphic is unknown. Once SAND_ID is
    # set it is the whole answer: an item that is not that graphic is not the
    # sand, and letting a name overrule it means a pinned SAND_HUE can be
    # walked straight past by anything called "sand".
    if not SAND_ID:
        for item in candidates:
            name = item_name(item).lower()
            for want in SAND_NAMES:
                if want.strip().lower() in name:
                    return item

    # One new thing and nothing else: that is the sand, whatever it is called.
    #
    # ONLY WHILE THE GRAPHIC IS UNKNOWN. Once SAND_ID is set, an item that is
    # not that graphic is not the sand however alone it is - taking it would
    # drag whatever else happened to appear on the platform into the pack, and
    # the whole point of learning the graphic was to stop guessing.
    if not SAND_ID and len(candidates) == 1:
        return candidates[0]
    return None


def one_round(index):
    """Withdraw, convert, collect. True if a piece of sand came back."""
    log("--- stone %d ---" % index, HUE_GOOD)

    granite = withdraw_one()
    if granite is None:
        return False

    box = Items.FindBySerial(BOX_SERIAL)
    if box is None:
        log("Converter box 0x%X not found." % BOX_SERIAL, HUE_BAD)
        return False
    if not walk_to_item(box, "the converter box"):
        return False

    # Snapshot the ground BEFORE the drop. The sand is whatever is on it
    # afterwards that was not on it before - which needs no graphic, and is
    # why SAND_ID being unknown costs nothing.
    ground_before = ground_serials(SAND_RANGE)

    # ONE move. The recording had two because the first was out of range; the
    # walk above is the fix for that, not a second drag.
    if not move_one(granite, BOX_SERIAL, "the granite"):
        return False
    log("granite is in the box - the conversion is instant.", HUE_GOOD)

    # To the platform. Two tiles from the crate, so this is a short walk - but
    # the sand still has to be in REACH to be dragged, not merely in sight.
    spot = platform_spot()
    if not walk_to(spot[0], spot[1]):
        log("Could not reach the platform at %d,%d." % spot, HUE_BAD)
        return False

    deadline = time.time() + SAND_WAIT_MS / 1000.0
    sand = None
    while time.time() < deadline:
        Misc.Pause(WALK_POLL_MS)
        new = [s for s in ground_serials(SAND_RANGE) if s not in ground_before]
        if new:
            sand = find_sand(new)
            if sand is not None:
                break

    if sand is None:
        log("Nothing new appeared within %d tiles of the platform at %d,%d in "
            "%ds. Raise SAND_NEAR_PLATFORM if the sand lands further off than "
            "that, or SAND_RANGE if it is out of sight altogether."
            % (SAND_NEAR_PLATFORM, spot[0], spot[1], SAND_WAIT_MS / 1000),
            HUE_BAD)
        return False

    try:
        log("sand is %s, graphic 0x%04X, hue 0x%04X at %d,%d"
            % (item_name(sand) or "unnamed", int(sand.ItemID), int(sand.Hue),
               sand.Position.X, sand.Position.Y), HUE_GOOD)
        if not SAND_ID:
            log("  set SAND_ID = 0x%04X to find it by graphic next time."
                % int(sand.ItemID), HUE_INFO)
    except Exception:
        pass

    if not walk_to_item(sand, "the sand"):
        return False

    pack = Player.Backpack
    if pack is None:
        log("No backpack to put the sand in.", HUE_BAD)
        return False
    if not move_one(sand, int(pack.Serial), "the sand"):
        return False

    log("sand collected.", HUE_GOOD)
    return True


def preflight():
    """Say what will happen, and refuse rather than guess. False to stop."""
    log("Sandmaker v%s - one stone at a time." % SCRIPT_VERSION, HUE_GOOD)

    if not WITHDRAW_BUTTON and not WITHDRAW_BUTTON_CONFIRMED:
        log("Neither WITHDRAW_BUTTON nor WITHDRAW_BUTTON_CONFIRMED is set, so "
            "nothing will be pressed.", HUE_BAD)
        log("  Run Scripts/diag_storage_gump.py, target the Stone Storage, "
            "and read the button on the %r row off the end of its report."
            % STONE_LABEL, HUE_WARN)
        return False

    if Player.Backpack is None:
        log("No backpack.", HUE_BAD)
        return False

    # Named WITH THEIR COORDINATES. "Not found" on a locked-down item means
    # you are standing somewhere else, and saying where it is turns that from
    # a puzzle into a walk.
    for serial, what, spot in ((STONE_STORAGE_SERIAL, "Stone Storage", None),
                               (BOX_SERIAL, "Granite Crate", BOX_SPOT),
                               (PLATFORM_SERIAL, "platform", PLATFORM_SPOT)):
        if Items.FindBySerial(serial) is not None:
            continue
        where = " It is at %d,%d." % spot if spot else ""
        log("%s 0x%X is not in range.%s" % (what, serial, where), HUE_BAD)
        return False

    log("  storage 0x%X, crate 0x%X at %d,%d, platform 0x%X at %d,%d"
        % (STONE_STORAGE_SERIAL, BOX_SERIAL, BOX_SPOT[0], BOX_SPOT[1],
           PLATFORM_SERIAL, PLATFORM_SPOT[0], PLATFORM_SPOT[1]))
    # Open the window and say what will be pressed, BEFORE anything is. A
    # button chosen silently is a button nobody checked.
    if open_storage() is not None:
        found, count = find_stone_row(STONE_LABEL)
        log("  pressing button %d for %r%s"
            % (WITHDRAW_BUTTON or WITHDRAW_BUTTON_CONFIRMED, STONE_LABEL,
               ", %s in stock" % count if count else ""), HUE_GOOD)
        if found and found != (WITHDRAW_BUTTON or WITHDRAW_BUTTON_CONFIRMED):
            log("  (the row search would have said %d - it is a cross-check "
                "only, and it has been wrong.)" % found, HUE_WARN)
        try:
            Gumps.CloseGump(STASH_GUMP)
        except Exception:
            pass
        Misc.Pause(SETTLE_MS)

    log("  %d at a time, %s run(s)%s"
        % (WITHDRAW_AMOUNT, RUNS or "unlimited",
           ", button %d forced" % WITHDRAW_BUTTON if WITHDRAW_BUTTON else ""))
    if not SAND_ID:
        log("  SAND_ID is unset - the sand is found by diffing the ground, "
            "and the graphic is printed on the first success.", HUE_INFO)
    else:
        log("  sand is 0x%04X%s, on the platform, and new since the drop."
            % (SAND_ID,
               " hue 0x%04X" % SAND_HUE if SAND_HUE >= 0 else " (any hue)"))
    return True


def main():
    if not preflight():
        return

    made = 0
    index = 0
    while True:
        index += 1
        if RUNS and index > RUNS:
            break
        if not one_round(index):
            log("Stopping after %d stone(s) - the message above says why."
                % made, HUE_WARN)
            break
        made += 1

    log("%d stone(s) converted." % made,
        HUE_GOOD if made else HUE_WARN)
    # Nothing is left open. A stray stash window is one more thing for the
    # next WaitForGump to answer by mistake.
    try:
        Gumps.CloseGump(STASH_GUMP)
    except Exception:
        pass


main()
