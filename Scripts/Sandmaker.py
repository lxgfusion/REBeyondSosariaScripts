"""
Sandmaker - one granite at a time, stone to sand.
=================================================

For Razor Enhanced (IronPython 3.4). Target: the UOAlive / Beyond Sosaria
freeshard.

THE ROUND
---------
    BATCH_SIZE times:
        withdraw ONE Plain granite from the Stone Storage
        drop it in the converter            (the conversion is instant)
    say "[grab"                             (the sand lands in the LOOT BAG)
    move the sand into the backpack
    put the sand in the Reagent Keys        (in the POUCH; context menu, not
                                             a drag - they are not a container)

Repeated until you stop it, or the Plain granite runs out.

YOU STAND STILL. The spot that can reach the converter and still collect with
"[grab" was found by hand, and the script does not wander off it: STAND_STILL
refuses rather than walks when something is out of reach. Set it False to get
the old walking behaviour back.

The stones go in ONE AT A TIME - the converter does not take a stack.

WHAT THIS IS NOT
----------------
It is not the recorded macro. That one disconnected the client on its first
run. Three things in it are wrong, and two of them are invisible in a
recording:

    Gumps.SendAdvancedAction(0x6abce12, 21, [], [0], ["1"])
    Gumps.WaitForGump(0x6abce12, 10000)      <- the window is GONE by now
    Gumps.SendAction(0x6abce12, 1)           <- answering a window that closed

  * THE DISCONNECT: the first line sends a TEXT ENTRY ([0], ["1"]) to a
    window that draws none. ServUO drops any reply carrying more text entries
    than the gump drew. The "1" beside "Withdrawal Amount:" is plain text,
    not a box. Sandmaker made the same mistake on 2026-09-18 and dropped too.
  * A gump response CLOSES the gump, so the third line answers a window the
    server no longer holds. Stock ServUO IGNORES that (DisplayGumpResponse
    only matches gumps it still has) - a press that does nothing, not a drop.
  * Four Player.Run/Walk calls back to back with no delay. Servers have
    fastwalk protection and a recorder replays keystrokes instantly.
  * Three Items.Move with no pause, against a ~900ms drag limit.

And the serials in it cannot be reused. 0x40BB6349 was that one withdrawal's
granite and 0x40BB64E1 was that one piece of sand; both are new items every
time. Only the CONTAINERS are stable, so only containers are configured by
serial here - the stone is found by graphic and the sand by diffing the ground.

THE WITHDRAW
------------
One plain press of the row's button, with NO text entry, and only when the
window's Withdrawal Amount already reads 1. See check_amount() and
docs/sandmaker-handoff.md for the disconnect that taught both. The button is
the Gump Inspector's (WITHDRAW_BUTTON_CONFIRMED); with neither that nor
WITHDRAW_BUTTON set the script REFUSES TO RUN, because the Stone Storage lists
ten granite types and the wrong row is the wrong stone.
"""

import re
import time


# Printed as the first line at startup, like every other script here. Razor
# CACHES the loaded script even after the file on disk changes, and this repo
# has already lost two debugging rounds to a bug that was fixed on disk and not
# in the folder Razor reads. If this line does not say what you expect, hit
# Reload in the Scripting tab.
SCRIPT_VERSION = "2026-09-30.4"


# =============================================================================
# CONFIG - THE THINGS YOU MUST SET
# =============================================================================

# The Stone Storage. From the recording; it is locked down, so the serial is
# stable in a way the stones inside it are not.
STONE_STORAGE_SERIAL = 0x00000000    # the real one is in .local/Sandmaker.serials.py

# The shared stash window every storage key on this shard opens.
# resource_order_runner.py calls it BOOK_GUMP, harvest_runner.py calls it
# HOUSE_DEPOSIT_GUMP.
STASH_GUMP = 0x06ABCE12

# THE BUTTON THAT WITHDRAWS PLAIN GRANITE - an explicit override.
#
# 0, the default, means "use WITHDRAW_BUTTON_CONFIRMED below". Set a number
# here only to force a different one; it is still checked against the drawn
# set before it is pressed.
#
# It does NOT mean "find it". It used to: the button on the row labelled
# STONE_LABEL was read off the live layout, and on 2026-09-18 that search
# returned 6 for Plain's row, 6 was pressed, and the client dropped. The
# search is a cross-check now and decides nothing - see choose_button().
WITHDRAW_BUTTON = 0

# WHAT THE GUMP INSPECTOR SAID, 2026-09-18: button 1 withdraws the granite.
#
# THIS IS WHAT GETS PRESSED. An Inspector reading is the id the server
# received when a human clicked the thing they meant - a live dump, not an
# inference - so it wins any disagreement with the row search. The search
# still runs and a disagreement is said out loud, but it changes nothing.
#
# 0 here, with WITHDRAW_BUTTON also 0, means nothing is pressed at all.
#
# The live dump agrees: button 1 is at 35,55, just left of the "Plain" label.
# The rows are two columns of five, 1-5 down the left (Plain, Dull, Shadow,
# Copper, Bronze) and 6-10 down the right (Gold .. Mythril). 21 is the arrow
# beside the Withdrawal Amount, 22 is Add, 23 is Fill from backpack.
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
BOX_SERIAL = 0x00000000    # the real one is in .local/Sandmaker.serials.py
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
PLATFORM_SERIAL = 0x00000000    # the real one is in .local/Sandmaker.serials.py
PLATFORM_ID = 0x07BD
PLATFORM_SPOT = (2073, 2504)

# How close to the platform a new ground item has to be to be the sand.
# Generous - the exact tile it settles on is the server's business - but not
# so wide that something dropped elsewhere in the room qualifies.
SAND_NEAR_PLATFORM = 3

# HOW MANY STONES PER BATCH, and how many batches.
#
# A batch is: convert BATCH_SIZE stones one at a time, then one "[grab", then
# one deposit into the Reagent Keys. BATCHES = 0 keeps going until you stop
# the script or the Plain granite runs out.
BATCH_SIZE = 50
BATCHES = 0

# A progress line every N stones, so a batch of 50 is not silent for minutes.
# 0 turns it off.
PROGRESS_EVERY = 5

# WHAT PICKS THE SAND UP. The shard command, said in chat. The sand lands on
# the platform out of drag reach from the spot that can feed the converter,
# which is why this exists rather than a walk.
GRAB_PHRASE = "[grab"
SAY_HUE = 90                # only used by the (colour, msg) form of ChatSay

# How long to wait for the pile to arrive, and how it is judged finished: the
# count in the pack has to STOP RISING, not reach any particular number.
GRAB_WAIT_MS = 15000
GRAB_POLL_MS = 400
GRAB_STEADY_POLLS = 3

# THE REAGENT KEYS - where the sand is stored. From the Item Inspector,
# 2026-09-30:
# THE SERIALS IN THE DUMPS BELOW ARE EXAMPLES. 0x4000ABxx is a
# placeholder; the real ones are in .local/Sandmaker.serials.py, which
# is gitignored. Item ids, hues and positions are as inspected.
#     Name "Reagent Keys", 0x4000ABCE, ItemID 0x18DE, hue 0x0021
#     Blessed, Weight 1 Stone, in the backpack
#     Container: NO
#
# CONTAINER: NO IS THE IMPORTANT LINE. Nothing can be dragged into it, so the
# sand goes in through its CONTEXT MENU - the same "Refill from stock" entry
# every storage key on this shard uses, and the one harvest_runner.py has been
# emptying packs with for months.
#
# THAT ENTRY DEPOSITS EVERY REAGENT IN THE PACK, not only the sand. If you are
# carrying reagents you want to keep, take them out first.
# WHERE THE SAND LANDS. From the Item Inspector, 2026-09-30:
#     "a loot bag", 0x4000ABCF, ItemID 0x0E76, hue 0x04F2
#     Container: YES, inside the backpack (0x41D40F58)
#
# "[grab" does NOT put the sand in the backpack itself - it goes in this bag,
# which is why the first version counted the pack and saw nothing. Everything
# that counts sand opens this bag and reads it, and the pack's top level is
# checked as well so a stack dragged out by hand is still found.
#
# SET SAND_IN_SEPARATE_BAG = False if "[grab" drops the sand straight into
# your backpack. Then SAND_BAG_SERIAL is ignored, the pack is what gets
# counted, and nothing is dragged before the deposit.
SAND_IN_SEPARATE_BAG = True
SAND_BAG_SERIAL = 0x00000000    # the real one is in .local/Sandmaker.serials.py
SAND_BAG_ID = 0x0E76
SAND_BAG_HUE = 0x04F2

# WHERE THE REAGENT KEYS LIVE. Inspected the same day:
#     "pouch", 0x4000ABD0, ItemID 0x0E79, hue 0x0000
#     Container: YES, inside the backpack (0x41D40F58)
#
# The keys are NOT carried loose in the pack here, so a top-level search
# misses them. The pouch is opened before the keys are looked for - a
# container's contents only exist once it has been opened.
#
# SET KEY_IN_SEPARATE_BAG = False if you keep your keys loose in the backpack.
# Then KEY_BAG_SERIAL is ignored and nothing opens a pouch. The serial search
# runs either way, so a key that Razor can already see is found regardless.
KEY_IN_SEPARATE_BAG = True
KEY_BAG_SERIAL = 0x00000000    # the real one is in .local/Sandmaker.serials.py
KEY_BAG_ID = 0x0E79
KEY_BAG_HUE = 0x0000

# Move the sand out of the loot bag and into the backpack before depositing.
#
# ON by default because nothing has established that "Refill from stock"
# reaches INTO a sub-container, and the failure if it does not is silent: the
# sand stays in the bag, the deposit looks like it did nothing, and the run
# stops. One drag per stack is cheap certainty. Set False if the keys turn out
# to take it straight from the bag. Ignored when SAND_IN_SEPARATE_BAG is off,
# because then it is already in the pack.
SAND_TO_PACK_BEFORE_STORE = True

REAGENT_KEY_SERIAL = 0x00000000    # the real one is in .local/Sandmaker.serials.py
REAGENT_KEY_ID = 0x18DE
REAGENT_KEY_HUE = 0x0021
REAGENT_KEY_NAMES = ["reagent keys", "reagent key"]
REAGENT_KEY_CONTEXT = ["Refill from stock"]

# Menu entries that are never worth clicking by accident. An EXACT match on
# REAGENT_KEY_CONTEXT is always honoured; only a substring match is checked
# against this. See CLAUDE.md - a context menu carries Buy, Sell and Bribe
# right next to the entry you want.
CONTEXT_NEVER = ["buy", "sell", "bribe", "open bankbox", "train "]
CONTEXT_TIMEOUT_MS = 10000

# How long to let a deposit settle before counting what is left.
STORE_SETTLE_MS = 1200

# Re-opening a container to read it. The short settle is for the polling done
# while waiting for the grab, where the full SETTLE_MS on every look would
# add seconds to every batch.
CONTENTS_WAIT_MS = 4000
CONTENTS_SETTLE_MS = 400

# STAND STILL. True means the script never walks: anything out of reach is
# reported and the run stops, rather than the character wandering off the one
# spot that works. False restores the old walk-to-everything behaviour.
STAND_STILL = True


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

# A REFUSED DRAG IS NOT THE END OF THE RUN.
#
# 2026-09-30, after 186 stones: one drag was refused and the whole run
# stopped. Nothing was wrong with the setup - the next stone would have gone
# in - so a drag is retried before it counts as a failure, and a batch
# survives failures that are not consecutive.
#
# The cap still matters: if the crate is full, or you have been pushed out of
# range, every drag will fail and the run should say so rather than grind.
MOVE_RETRIES = 3                # attempts per drag, including the first
MOVE_RETRY_PAUSE_MS = 1200      # on top of MOVE_PAUSE_MS, before trying again
BATCH_FAILURE_LIMIT = 3         # stones failing IN A ROW before stopping

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


# The two kinds of element a server can answer to, and where each carries its
# id. From ServUO Server/Gumps/GumpButton.cs and GumpImageTileButton.cs:
#
#     { button        x y normal pressed type param ID }
#     { buttontileart x y normal pressed type param ID itemid hue width height }
#
# The id is the SEVENTH number in both. It is not the last: for a
# buttontileart the last number is its HEIGHT. ServUO's DisplayGumpResponse
# accepts a press on either kind, so both count as drawn.
BUTTON_KINDS = ("button", "buttontileart")
BUTTON_ID_INDEX = 6


def layout_buttons(gump_id):
    """(x, y, id) for every button the server drew, with its position.

    An element too short to carry an id is skipped, not guessed at.
    """
    out = []
    for piece in re.findall(r"\{([^{}]*)\}", raw_layout(gump_id)):
        piece = piece.strip()
        kind = piece.split()[0].lower() if piece else ""
        if kind not in BUTTON_KINDS:
            continue
        nums = [int(n) for n in re.findall(r"-?\d+", piece)]
        if len(nums) > BUTTON_ID_INDEX:
            out.append((nums[0], nums[1], nums[BUTTON_ID_INDEX]))
    return out


def find_stone_row(label):
    """(button, count) for the row named `label`. (0, "") if it is not there.

    A CROSS-CHECK ONLY. It decides nothing - choose_button() presses the
    Gump Inspector's number whatever this says.

    THE BUTTON IS TO THE LEFT OF ITS LABEL. From the live dump of the Stone
    Storage, 2026-09-18 - two columns of five rows:

        button 1 @x35   Plain @x75   59998 @x215   button 6 @x275   Gold @x315

    This used to prefer a button to the RIGHT of the label, which walked past
    Plain's own button and took Gold's. That is where "6" came from.

    So: the nearest button to the label's left, and it must sit AFTER the
    previous cell on the row. If Gold's button were missing, the nearest one
    to its left would be Plain's, far across the window - and a button
    belonging to someone else is worse than none. Nothing qualifies, nothing
    is returned.

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
        # The button on that row, between the previous cell and the label.
        floor = max([ox for ox, oy, _t in cells
                     if abs(oy - cy) <= ROW_TOLERANCE and ox < cx] or [-1])
        left = sorted((bx, bid) for bx, by, bid in layout_buttons(STASH_GUMP)
                      if abs(by - cy) <= ROW_TOLERANCE and floor < bx < cx)
        if not left:
            return 0, count
        return left[-1][1], count
    return 0, ""


def drawn_buttons(gump_id):
    """Every button id the server actually drew on this window.

    PRESSING ONE IT DID NOT DRAW DISCONNECTS YOU - that is the first check in
    ServUO's DisplayGumpResponse - so this is checked before every press
    rather than trusted from config.

    Necessary, NOT sufficient. On 2026-09-18 a button in this set was pressed
    and the client still dropped - because the reply also carried a text
    entry and this window draws none. See text_entry_count().
    """
    return set(bid for _x, _y, bid in layout_buttons(gump_id))


def text_entry_count(gump_id):
    """How many text entries the window drew. ServUO's limit on a reply.

    DisplayGumpResponse disconnects a reply carrying more text entries than
    the gump drew. The Stone Storage draws NONE - its "1" is plain text - so
    any press that sends one is a drop. withdraw_one() refuses to press if
    this ever reads non-zero, because then the window is not the one this
    script was written against.
    """
    n = 0
    for piece in re.findall(r"\{([^{}]*)\}", raw_layout(gump_id)):
        piece = piece.strip()
        if piece and piece.split()[0].lower() in ("textentry",
                                                  "textentrylimited"):
            n += 1
    return n


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


def open_container(serial, what, settle=None):
    """Re-open a container so its Contains list is current. The item, or None.

    Contains is a SNAPSHOT taken when the container was opened, and asking a
    different way does not help: Items.FindAllByID with a container serial
    walks that same list. Re-opening is the only real refresh - and a bag that
    has never been opened has no contents at all. See CLAUDE.md.
    """
    item = Items.FindBySerial(int(serial))
    if item is None:
        return None
    try:
        Items.UseItem(item)
        Items.WaitForContents(item, CONTENTS_WAIT_MS)
    except Exception:
        pass
    Misc.Pause(CONTENTS_SETTLE_MS if settle is None else settle)
    return item


def contents_of(container):
    try:
        return list(getattr(container, "Contains", None) or [])
    except Exception:
        return []


def is_sand(item):
    try:
        if int(item.ItemID) != SAND_ID:
            return False
        if SAND_HUE >= 0 and int(item.Hue) != SAND_HUE:
            return False
    except Exception:
        return False
    return True


def amount_of(item):
    try:
        return int(item.Amount or 1)
    except Exception:
        return 1


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


def where_is(item):
    """A description of where an item is. NEVER a tile count for something in
    a container.

    The failure line used to say "it is 2394 tiles away and still in your
    pack", which is the player's map coordinate measured against an item that
    has no position of its own because it is inside a bag. Nonsense in a
    message nobody can act on.
    """
    if item is None:
        return "gone"
    try:
        container = int(getattr(item, "Container", 0) or 0)
    except Exception:
        container = 0
    if container:
        return "still in a container"
    return "on the ground %d tile(s) away" % distance_to(item)


def has_moved(serial, target_serial):
    """Did the item really leave? Asked the expensive way before giving up.

    Three ways it counts as moved:
      * the client no longer has it - which is what the converter does to a
        granite the moment it lands
      * it now reports the target as its container
      * it is no longer in the backpack, asked after RE-OPENING the pack

    That last one matters: Contains is a snapshot, and an item object fetched
    by serial can still be carrying the container it had when the snapshot was
    taken. See CLAUDE.md.
    """
    moved = Items.FindBySerial(serial)
    if moved is None:
        return True
    try:
        if int(getattr(moved, "Container", 0) or 0) == int(target_serial):
            return True
    except Exception:
        pass
    refresh_pack()
    if serial not in pack_serials():
        return True
    return False


def move_one(item, target_serial, what, amount=1, retries=None):
    """Drag `amount` of `item` into `target_serial`. True only if it moved.

    Verified by result and RETRIED. A refused drag is silent - the packet goes
    out, nothing happens, and the next step runs as though it had worked - and
    on this shard a single refusal is usually just the drag limit or a hiccup,
    not a reason to end a run that has already done 186 of these.
    """
    serial = int(item.Serial)
    attempts = max(1, int(MOVE_RETRIES if retries is None else retries))
    for attempt in range(1, attempts + 1):
        try:
            Items.Move(item, int(target_serial), int(amount))
        except Exception as err:
            log("could not drag %s: %r" % (what, err), HUE_BAD)
            return False
        Misc.Pause(MOVE_PAUSE_MS)

        if has_moved(serial, target_serial):
            if attempt > 1:
                log("  %s moved on attempt %d." % (what, attempt), HUE_GOOD)
            return True

        if attempt < attempts:
            log("  %s did not move (attempt %d of %d) - %s. Trying again."
                % (what, attempt, attempts,
                   where_is(Items.FindBySerial(serial))), HUE_WARN)
            Misc.Pause(MOVE_RETRY_PAUSE_MS)

    log("%s did not move after %d attempt(s) - it is %s."
        % (what, attempts, where_is(Items.FindBySerial(serial))), HUE_BAD)
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
    """Does the Withdrawal Amount read WITHDRAW_AMOUNT? False refuses the run.

    THIS IS THE ONLY GUARD ON THE AMOUNT. The window has NO text entry - the
    "1" beside "Withdrawal Amount:" is plain text, set server-side (button 21,
    the arrow beside it, is presumably how it is changed). Nothing can be sent
    WITH the press: a reply carrying a text entry to a window that drew none
    is one of ServUO's four disconnects, and it is what dropped the client on
    2026-09-18. So whatever this reads is what comes out, and 59998 granite
    in the pack is not a recoverable mistake.

    Unreadable is a refusal too.
    """
    shown = label_after(gump_lines(STASH_GUMP), "Withdrawal Amount")
    if not shown:
        log("Could not read the Withdrawal Amount, and it is the only thing "
            "deciding how many come out. Not pressing.", HUE_BAD)
        return False
    if shown == str(WITHDRAW_AMOUNT):
        log("Withdrawal Amount reads %s." % shown, HUE_GOOD)
        return True
    log("Withdrawal Amount reads %r, not %d - that is how many one press would "
        "take out. Set it to %d by hand (the arrow beside it) and run again."
        % (shown, WITHDRAW_AMOUNT, WITHDRAW_AMOUNT), HUE_BAD)
    return False


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

    # The window this was written against draws no text entry. If one has
    # appeared, the amount may now be a box the press would submit EMPTY, or
    # the layout has changed under us - either way, not this script's window.
    entries = text_entry_count(STASH_GUMP)
    if entries:
        log("The Stone Storage now draws %d text entr(y/ies). It drew none when "
            "this was written, and the amount was plain text. Not pressing - "
            "re-run diag_storage_gump.py." % entries, HUE_BAD)
        return None

    before = pack_serials()
    log("withdrawing %d %s (button %d)"
        % (WITHDRAW_AMOUNT, STONE_LABEL, button))
    # A PLAIN PRESS - no switches, NO TEXT ENTRIES. This window draws no text
    # entry, and ServUO disconnects any reply that carries more text entries
    # than the gump drew. SendAdvancedAction(..., [0], ["1"]) is exactly that,
    # and it dropped the client on 2026-09-18 - with button 1 it would have
    # dropped just the same. The amount is whatever check_amount() read.
    try:
        Gumps.SendAction(STASH_GUMP, button)
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

    # The button that was PRESSED, not WITHDRAW_BUTTON - that is 0 unless
    # forced, and on 2026-09-18 this line said "button 0" about a press of 6.
    log("Nothing that looks like granite (0x%04X) arrived in the pack. Either "
        "button %d is not the %s row, or the storage is empty."
        % (GRANITE_ID, button, STONE_LABEL), HUE_BAD)
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


def in_reach(item, what, limit=REACH_DISTANCE):
    """Is `item` close enough to drag to? Says how far when it is not.

    With STAND_STILL the answer is never "walk to it": the spot was chosen by
    hand because it can feed the converter AND collect with "[grab", and a
    script that wanders off it silently stops being able to do either.
    """
    if item is None:
        log("%s is not in range at all." % what, HUE_BAD)
        return False
    gap = distance_to(item)
    if gap <= limit:
        return True
    if not STAND_STILL:
        return walk_to_item(item, what)
    log("%s is %d tiles away and STAND_STILL is on, so nothing will walk to "
        "it. Stand where you can reach it." % (what, gap), HUE_BAD)
    return False


def say(phrase):
    """Say something in game. False if it could not be said at all.

    ChatSay takes (msg) on every build from 0.8.2.245 to 1.0.0.14 and also
    accepts (colour, msg); both are tried rather than one being picked. See
    CLAUDE.md - a signature that moves is how a working script just stops.
    """
    try:
        Player.ChatSay(phrase)
        return True
    except TypeError:
        pass
    except Exception as err:
        log("could not say %r: %r" % (phrase, err), HUE_BAD)
        return False
    try:
        Player.ChatSay(SAY_HUE, phrase)
        return True
    except Exception as err:
        log("could not say %r: %r" % (phrase, err), HUE_BAD)
        return False


def uses_sand_bag():
    return bool(SAND_IN_SEPARATE_BAG and SAND_BAG_SERIAL)


def uses_key_bag():
    return bool(KEY_IN_SEPARATE_BAG and KEY_BAG_SERIAL)


def sand_in_bag():
    """(total, [stacks]) of sand wherever "[grab" drops it.

    The loot bag, or the BACKPACK when SAND_IN_SEPARATE_BAG is off - not
    everyone keeps one, and the grab drops it straight in the pack for them.

    Whichever it is, it is RE-OPENED first. Contents are a snapshot, and a
    stale one reads as "the grab picked nothing up" - the same false negative
    that aborted the order runner after one order, every time.
    """
    if not uses_sand_bag():
        return sand_in_pack()
    bag = open_container(SAND_BAG_SERIAL, "the loot bag")
    if bag is None:
        return 0, []
    stacks = [i for i in contents_of(bag) if is_sand(i)]
    return sum(amount_of(i) for i in stacks), stacks


def sand_in_pack():
    """(total, [stacks]) of sand loose at the top level of the backpack.

    Not where the grab puts it - that is the loot bag - but where it has to
    end up before the keys will take it, and where a stack dragged out by hand
    would be.
    """
    pack = Player.Backpack
    if pack is None:
        return 0, []
    open_container(int(pack.Serial), "the backpack")
    pack = Player.Backpack
    stacks = [i for i in contents_of(pack) if is_sand(i)]
    return sum(amount_of(i) for i in stacks), stacks


def sand_on_hand():
    """(total, [stacks]) of sand anywhere it is expected to be: the loot bag
    the grab fills, and the pack's top level.

    With no separate bag the two are the same place, so the pack is counted
    ONCE - adding them would report double and a deposit would look like it
    left half behind.
    """
    if not uses_sand_bag():
        return sand_in_pack()
    in_bag, bag_stacks = sand_in_bag()
    in_pack, pack_stacks = sand_in_pack()
    return in_bag + in_pack, bag_stacks + pack_stacks


def grab_sand(expected):
    """Say the grab phrase and wait for the sand to reach the pack.

    Returns how many arrived. The wait ends when the count STOPS RISING, not
    when it reaches `expected`: the shard collects the pile in its own time,
    and waiting for a number that never comes would burn the whole timeout on
    every batch.
    """
    before, _ = sand_in_bag()
    log("saying %r for the sand (%d already in the loot bag)"
        % (GRAB_PHRASE, before))
    if not say(GRAB_PHRASE):
        return 0

    deadline = time.time() + GRAB_WAIT_MS / 1000.0
    best, steady = before, 0
    while time.time() < deadline:
        Misc.Pause(GRAB_POLL_MS)
        now, _ = sand_in_bag()
        if now > best:
            best, steady = now, 0
            continue
        if now >= best and best > before:
            steady += 1
            if steady >= GRAB_STEADY_POLLS:
                break

    got = best - before
    if got <= 0:
        log("Nothing arrived in the loot bag 0x%X from %r. Is this the spot "
            "where it works, and is that still the bag it fills?"
            % (SAND_BAG_SERIAL, GRAB_PHRASE), HUE_BAD)
        return 0
    log("picked up %d sand%s." % (got, "" if got >= expected
                                  else " - %d were converted" % expected),
        HUE_GOOD if got >= expected else HUE_WARN)
    return got


def collect_sand_nearby(limit):
    """Fallback: drag sand off the ground into the pack. Returns how many.

    Only used when the grab picked NOTHING up, and only for sand that is
    actually in reach - from the feeding spot the platform usually is not, and
    saying so is more use than walking off it.
    """
    picked = 0
    pack = Player.Backpack
    if pack is None:
        return 0
    for _ in range(max(0, int(limit))):
        sand = find_sand(ground_serials(SAND_RANGE))
        if sand is None:
            break
        if distance_to(sand) > REACH_DISTANCE:
            log("  sand is on the ground %d tiles away - out of drag reach "
                "from here." % distance_to(sand), HUE_WARN)
            break
        if not move_one(sand, int(pack.Serial), "the sand"):
            break
        picked += 1
    if picked:
        log("  dragged %d sand off the ground." % picked, HUE_GOOD)
    return picked


def sand_bag_to_pack():
    """Drag the loot bag's sand into the pack's top level. How many moved.

    One drag per stack, each verified and each waiting out the drag limit.
    Sand stacks, so this is normally a single drag however big the batch was.
    """
    if not uses_sand_bag():
        return 0                      # already where it needs to be
    pack = Player.Backpack
    if pack is None:
        return 0
    moved = 0
    _total, stacks = sand_in_bag()
    for stack in stacks:
        amount = amount_of(stack)
        if move_one(stack, int(pack.Serial), "the sand", amount):
            moved += amount
    return moved


def find_reagent_key():
    """The Reagent Keys. By serial first, then by graphic where they live.

    THEY ARE IN THE POUCH here, not loose in the pack, so the pouch is opened
    first: a container that has never been opened has no contents to search,
    and FindBySerial on something inside it can come back empty for the same
    reason. With KEY_IN_SEPARATE_BAG off, nothing is opened and the pack is
    searched instead.

    The serial is exact and the keys do not move; the graphic is the fallback
    for the day they are replaced. They are NOT a container - Container: No in
    the Item Inspector - so they are only ever looked up to be right-clicked.
    """
    pouch = open_container(KEY_BAG_SERIAL, "the pouch") \
        if uses_key_bag() else None
    item = Items.FindBySerial(REAGENT_KEY_SERIAL)
    if item is not None:
        return item

    where = contents_of(pouch)
    pack = Player.Backpack
    if pack is not None:
        where = where + contents_of(pack)
    if not where:
        return None
    wanted = [n.strip().lower() for n in REAGENT_KEY_NAMES if n.strip()]
    for candidate in where:
        try:
            if int(candidate.ItemID) != REAGENT_KEY_ID:
                continue
            if REAGENT_KEY_HUE >= 0 and int(candidate.Hue) != REAGENT_KEY_HUE:
                continue
        except Exception:
            continue
        name = item_name(candidate).lower()
        if not wanted or any(w in name for w in wanted):
            log("found the Reagent Keys by graphic, not by serial - 0x%X has "
                "been replaced." % REAGENT_KEY_SERIAL, HUE_WARN)
            return candidate
    return None


def context_is_blocked(label):
    low = (label or "").lower()
    for banned in CONTEXT_NEVER:
        if banned.strip().lower() in low:
            return True
    return False


def wait_context(entity):
    try:
        return Misc.WaitForContext(entity, CONTEXT_TIMEOUT_MS, False)
    except TypeError:
        return Misc.WaitForContext(entity, CONTEXT_TIMEOUT_MS)


def context_select(entity, wanted, what):
    """Open a context menu and pick the first configured entry. True if sent.

    An EXACT label match is taken first and always honoured - it was
    configured verbatim, so it was meant. Only then is a substring tried, and
    that one refuses anything on CONTEXT_NEVER. The REAL label goes back to
    ContextReply, never the search string. See CLAUDE.md.
    """
    try:
        entries = wait_context(entity) or []
    except Exception as err:
        log("%s gave no context menu: %r" % (what, err), HUE_BAD)
        return False
    labels = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        labels.append(text if text is not None else str(entry))
    if not labels:
        log("%s has no context menu." % what, HUE_BAD)
        return False

    def reply(label):
        Misc.Pause(100)
        Misc.ContextReply(entity, label)
        Misc.Pause(600)
        return True

    for want in wanted:
        target = str(want or "").strip().lower()
        for label in labels:
            if (label or "").strip().lower() == target:
                return reply(label)
    for want in wanted:
        target = str(want or "").strip().lower()
        for label in labels:
            if target and target in (label or "").lower():
                if context_is_blocked(label):
                    log("  refusing %r - it matches CONTEXT_NEVER." % label,
                        HUE_WARN)
                    continue
                return reply(label)

    log("%s offers no entry matching %s - it has: %s"
        % (what, wanted, " | ".join(labels)), HUE_BAD)
    return False


def store_sand():
    """Put the pack's sand in the Reagent Keys. (stored, keep_going).

    Verified by counting the pack afterwards. A deposit that quietly does
    nothing would otherwise leave the sand there and the next batch would pile
    another 50 on top of it.
    """
    total, _ = sand_on_hand()
    if not total:
        log("no sand to store.", HUE_WARN)
        return 0, True

    # INTO THE PACK FIRST. The grab fills the loot bag, and nothing has
    # established that the keys reach into a sub-container - see
    # SAND_TO_PACK_BEFORE_STORE.
    if SAND_TO_PACK_BEFORE_STORE:
        moved = sand_bag_to_pack()
        if moved:
            log("  moved %d sand out of the loot bag." % moved)

    key = find_reagent_key()
    if key is None:
        log("Reagent Keys 0x%X (graphic 0x%04X) are not in the pack - nowhere "
            "to put %d sand." % (REAGENT_KEY_SERIAL, REAGENT_KEY_ID, total),
            HUE_BAD)
        return 0, False

    log("storing %d sand in the Reagent Keys 0x%X."
        % (total, int(getattr(key, "Serial", REAGENT_KEY_SERIAL))))
    if not context_select(key, REAGENT_KEY_CONTEXT, "the Reagent Keys"):
        return 0, False
    Misc.Pause(STORE_SETTLE_MS)

    left, _ = sand_on_hand()
    stored = total - left
    if left == 0:
        log("stored %d sand." % stored, HUE_GOOD)
        return stored, True
    if stored > 0:
        log("stored %d, but %d sand is still in the pack. Carrying on."
            % (stored, left), HUE_WARN)
        return stored, True
    log("The Reagent Keys took NOTHING - %d sand is still on you. Stopping "
        "rather than converting another batch on top of it." % left, HUE_BAD)
    return 0, False


def granite_on_hand():
    """A Plain granite already loose in the pack, or None.

    A drag that was refused leaves the stone where it was, so the next attempt
    uses THAT one rather than withdrawing another on top of it.
    """
    pack = Player.Backpack
    if pack is None:
        return None
    for item in contents_of(pack):
        try:
            if int(item.ItemID) != GRANITE_ID:
                continue
            if GRANITE_HUE >= 0 and int(item.Hue) != GRANITE_HUE:
                continue
        except Exception:
            continue
        return item
    return None


def run_batch(index):
    """Convert up to BATCH_SIZE stones, one at a time. (converted, keep_going).

    keep_going is False when the withdraw failed - out of Plain granite, or
    something that needs a human. The sand already made is still collected and
    stored before the script stops.
    """
    log("--- batch %d: up to %d stone(s) ---" % (index, BATCH_SIZE), HUE_GOOD)
    converted = 0
    in_a_row = 0

    # Bounded: every pass either converts a stone or counts a failure, and
    # BATCH_FAILURE_LIMIT ends it. The cap on passes is the backstop for a
    # case nobody thought of - no loop here runs without one.
    for _ in range(max(1, int(BATCH_SIZE)) * max(1, int(MOVE_RETRIES)) + 10):
        if converted >= max(1, int(BATCH_SIZE)):
            break

        # A stone left over from a refused drag is used before another is
        # withdrawn - otherwise a failure quietly piles granite in the pack.
        #
        # ONLY AFTER A FAILURE. Looking every pass would feed the converter
        # any Plain granite you happen to be carrying for something else, and
        # nothing here asked to spend that.
        granite = granite_on_hand() if in_a_row else None
        if granite is not None:
            log("  using the granite already in the pack.")
        else:
            granite = withdraw_one()
        if granite is None:
            log("stopped %d of %d into the batch - the line above says why."
                % (converted, BATCH_SIZE), HUE_WARN)
            return converted, False

        box = Items.FindBySerial(BOX_SERIAL)
        if not in_reach(box, "the converter 0x%X" % BOX_SERIAL):
            return converted, False

        if move_one(granite, BOX_SERIAL, "the granite"):
            converted += 1
            in_a_row = 0
            if PROGRESS_EVERY and converted % PROGRESS_EVERY == 0:
                log("  %d of %d converted" % (converted, BATCH_SIZE))
            continue

        in_a_row += 1
        if in_a_row >= max(1, int(BATCH_FAILURE_LIMIT)):
            log("%d stone(s) in a row would not go in. Something is wrong - a "
                "full crate, or you have been moved. Stopping with %d "
                "converted." % (in_a_row, converted), HUE_BAD)
            return converted, False
        log("  that stone would not go in (%d in a row). Carrying on."
            % in_a_row, HUE_WARN)

    return converted, True


def preflight():
    """Say what will happen, and refuse rather than guess. False to stop."""
    log("Sandmaker v%s - %d at a time, then %r, then the Reagent Keys."
        % (SCRIPT_VERSION, BATCH_SIZE, GRAB_PHRASE), HUE_GOOD)

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
                               (BOX_SERIAL, "Granite Crate", BOX_SPOT)):
        if Items.FindBySerial(serial) is not None:
            continue
        where = " It is at %d,%d." % spot if spot else ""
        log("%s 0x%X is not in range.%s" % (what, serial, where), HUE_BAD)
        return False

    # The converter has to be in DRAG reach, not merely in sight, and with
    # STAND_STILL nothing is going to close the gap later.
    if not in_reach(Items.FindBySerial(BOX_SERIAL),
                    "the converter 0x%X" % BOX_SERIAL):
        return False

    # The two bags, by name, because "not found" on either has a different
    # fix and the script cannot tell them apart later.
    if uses_sand_bag() and Items.FindBySerial(SAND_BAG_SERIAL) is None:
        log("The loot bag 0x%X is not on you - that is where %r puts the sand, "
            "and without it nothing can be counted. Set SAND_IN_SEPARATE_BAG "
            "= False if the grab fills your backpack instead."
            % (SAND_BAG_SERIAL, GRAB_PHRASE), HUE_BAD)
        return False
    if uses_key_bag() and Items.FindBySerial(KEY_BAG_SERIAL) is None:
        log("The pouch 0x%X is not on you - that is where the Reagent Keys "
            "live. Set KEY_IN_SEPARATE_BAG = False if you carry them loose "
            "in your pack." % KEY_BAG_SERIAL, HUE_BAD)
        return False

    key = find_reagent_key()
    if key is None:
        log("The Reagent Keys 0x%X are not %s, so there is nowhere to put the "
            "sand." % (REAGENT_KEY_SERIAL,
                       "in the pouch 0x%X or the pack" % KEY_BAG_SERIAL
                       if uses_key_bag() else "in the pack"), HUE_BAD)
        return False

    log("  storage 0x%X, converter 0x%X at %d,%d"
        % (STONE_STORAGE_SERIAL, BOX_SERIAL, BOX_SPOT[0], BOX_SPOT[1]))
    log("  sand lands in %s; keys 0x%X %s"
        % ("the loot bag 0x%X" % SAND_BAG_SERIAL if uses_sand_bag()
           else "the backpack", int(key.Serial),
           "in the pouch 0x%X" % KEY_BAG_SERIAL if uses_key_bag()
           else "in the pack"))
    on_hand, _ = sand_on_hand()
    if on_hand:
        log("  %d sand already on you - it will be stored with the first "
            "batch." % on_hand, HUE_WARN)

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

    log("  %s batch(es) of %d, %d stone per withdraw, %s"
        % (BATCHES or "unlimited", BATCH_SIZE, WITHDRAW_AMOUNT,
           "standing still" if STAND_STILL else "walking to what it needs"))
    log("  sand is 0x%04X%s; %r collects it%s."
        % (SAND_ID, " hue 0x%04X" % SAND_HUE if SAND_HUE >= 0 else " (any hue)",
           GRAB_PHRASE,
           ", and it is moved to the pack before storing"
           if SAND_TO_PACK_BEFORE_STORE and uses_sand_bag() else ""))
    return True


def main():
    if not preflight():
        return

    batch = made = stored = 0
    while True:
        batch += 1
        if BATCHES and batch > BATCHES:
            log("%d batch(es) done, which is BATCHES." % (batch - 1), HUE_GOOD)
            break

        converted, keep_going = run_batch(batch)
        made += converted

        # Collect and store WHATEVER was made, even when the batch stopped
        # early - the sand is on the floor either way, and leaving it there is
        # how a run ends with 40 stones' worth of sand nobody picked up.
        if converted:
            got = grab_sand(converted)
            if not got:
                got = collect_sand_nearby(converted)
            if got or sand_on_hand()[0]:
                put, ok = store_sand()
                stored += put
                if not ok:
                    break

        if not keep_going:
            break

    log("%d stone(s) converted, %d sand stored, in %d batch(es)."
        % (made, stored, batch if made else 0),
        HUE_GOOD if made else HUE_WARN)
    # Nothing is left open. A stray stash window is one more thing for the
    # next WaitForGump to answer by mistake.
    try:
        Gumps.CloseGump(STASH_GUMP)
    except Exception:
        pass


main()
