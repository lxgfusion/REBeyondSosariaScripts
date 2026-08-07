"""
Mining runner with account-runebook travel, vendor rounds and mana management.
==============================================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

This is the original mining script with three fixes:

1. TRAVEL / PAGE SWITCHING
   Two Razor Enhanced signatures changed under the script, which is why it
   "just broke" without being edited:
       Player.ChatSay(msg)          ->  Player.ChatSay(colour, msg)
       Gumps.GetLineList(gumpId)    ->  Gumps.GetLineList(gumpId, dataOnly)
   Both are now called through shims that try the current form and fall back to
   the old one, so this runs on either build. Folder and destination lookups
   also walk every page of the runebook gump instead of only the first.

2. VENDORS
   Mobiles.Filter().Name is an EXACT match - one renamed NPC and the loop
   silently does nothing. Vendors are now matched as case-insensitive
   substrings, listed in the VENDORS table, and every failure is logged instead
   of passing quietly.

3. MANA
   Nothing recalls on an empty mana pool any more. ensure_mana() meditates back
   up before any travel, and retries a travel that failed for insufficient mana.

Diagnostics
-----------
If travel still misbehaves, run Scripts/diag_ar_gump.py - it dumps the runebook
gump and identifies the real page-advance button.
If a vendor is skipped, run Scripts/diag_vendors.py next to it - it prints the
exact name and context entries.
"""

import re
import time

Misc.Pause(5000)


# #############################################################################
# ##                                                                         ##
# ##   EDIT THIS FIRST - THE VENDOR ROUND                                    ##
# ##                                                                         ##
# ##   Every NPC the script talks to is listed here, and nothing else needs  ##
# ##   changing to add, remove or rename one. If a vendor is being skipped,  ##
# ##   this table is almost always why.                                      ##
# ##                                                                         ##
# #############################################################################
#
# One entry per stop on the round. Fields:
#
#   label    Name used in the log. Anything you like.
#   folder   Runebook folder path to the rune, e.g. ['RO'] or ['Work', 'RO']
#            for a nested folder. Must match the folder text in the runebook.
#   point    Rune name to recall to, matched as a case-insensitive substring.
#   names    NPC names to look for, matched as case-insensitive SUBSTRINGS.
#            List several - the first that matches wins. "Sahale" is enough for
#            "Sahale the scribe". THIS IS THE FIELD THAT USUALLY NEEDS FIXING.
#   context  Context-menu entries to try, in order, until one is accepted.
#   gump     Optional (gumpid, buttonid) to answer after the menu. None if the
#            NPC does not open a gump.
#
# Run Scripts/diag_vendors.py standing next to an NPC to get the exact name and
# context entries it actually offers - it prints them verbatim.
#
# Set "enabled": False to skip a stop without deleting it.

VENDORS = [
    {
        "enabled": True,
        "label":   "Resource Orders",
        "folder":  ['RO'],
        "point":   'RO',
        "names":   ["Resource Gatherer", "Resource"],
        "context": ["Talk"],
        "gump":    None,
    },
    {
        "enabled": True,
        "label":   "Taming Deeds",
        "folder":  ['TamingDeed'],
        "point":   'TamingDeed',
        "names":   ["Animal Trainer", "Trainer"],
        "context": ["Talk"],
        "gump":    None,
    },
    {
        "enabled": True,
        "label":   "Inscription Orders",
        "folder":  ['Inscription'],
        "point":   'Inscription',
        "names":   ["Sahale the scribe", "Sahale", "scribe"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    (0x9bade6ea, 1),
    },
]

# How far from the rune to look for the NPC, and how long to wait for its menu.
VENDOR_RANGE = 12
CONTEXT_TIMEOUT = 10000


# =============================================================================
# CONFIG - GREYSKULL CALL-OUT
# =============================================================================
# Global chat arrives in the journal looking like this:
#
#     System: <Public> Fred Kruger: By The Power Of Greyskull!
#
# so the speaker is buried in the text and entry.Name is just "System". The
# script parses the channel and the caller out of the line itself.
#
# Phrases are matched CASE-INSENSITIVELY as substrings, so capitalisation and
# punctuation do not have to be typed exactly. The old code did an exact,
# case-sensitive match on "By The Power Of Greyskull!" - typing it in any other
# case missed entirely.
#
# Keep phrases distinctive; a short one will trigger on ordinary conversation.
GREYSKULL_PHRASES = [
    "by the power of greyskull",
]

# WHO MAY CALL IT. Empty list = ANYONE, which is the point of a group call-out.
# Put names here only if you want to restrict it, e.g. ["Fred Kruger", "Alice"].
# Matched case-insensitively as substrings against the parsed caller name.
GREYSKULL_ALLOWED_CALLERS = []

# Restrict to one chat channel, e.g. "Public" to accept only <Public> lines.
# Empty = any channel, including ordinary speech.
GREYSKULL_REQUIRE_CHANNEL = ""

# Ignore the chant when you are the one who said it. Off by default so that
# calling it out yourself still works.
GREYSKULL_IGNORE_SELF = False

# How long to hold at the circle before returning to the route.
GREYSKULL_HOLD_MS = 20000


# =============================================================================
# CONFIG - TRAVEL AND DROP-OFF
# =============================================================================

# The chest you drop mining spoils into.
DROP_CHEST_SERIAL = 0x400CEF90

# Runebook folder holding the mining runes. Every rune in it is worked in turn.
MINING_FOLDER = ['Mining']

# Where to unload.
DROP_FOLDER = ['Homes']
DROP_POINT  = 'HOME'

# Arcane Circle - for responding to the global chant.
ARCANE_FOLDER = ['Arcane']
ARCANE_POINT  = 'Circle'

AR_COMMAND = "[ar"
AR_GUMPID  = 0xc395adb4


# =============================================================================
# CONFIG - MANA / MEDITATION
# =============================================================================

# Recall costs 11 mana on stock RunUO. Leave headroom for a failed cast.
MIN_MANA_TO_TRAVEL = 20

# Meditate up to this before setting off. 0 means "to full".
MANA_TARGET = 0

MEDITATION_TIMEOUT   = 90000   # ms to spend trying to recover mana
MEDITATION_POLL      = 500     # ms between mana checks
MEDITATION_STALL     = 8       # polls without mana gain before re-meditating
MEDITATION_RETRY_MS  = 1500    # pause after a failed meditation roll

# Meditation needs empty hands. Stow anything held, then carry on.
DISARM_FOR_MEDITATION = True
HAND_MOVE_PAUSE = 800

# Metal armour blocks meditation entirely. When that happens the script falls
# back to standing still for passive regeneration.
PASSIVE_REGEN_NOTICE_ONCE = True


# =============================================================================
# CONFIG - RUNEBOOK PAGES
# =============================================================================

# Control buttons, confirmed from a live gump inspection of this runebook:
#
#   Response Received -> Gump Button: 504   (page forward)
#   Response Received -> Gump Button: 503   (page back)
#   Response Received -> Gump Button: 5     (back to root)
#
# Paging is SERVER-SIDE: each click returns a fresh gump with the same gump id
# and a new sequence number, carrying only that page's entries. There are no
# client-side { page N } markers, so pages genuinely have to be walked.
AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON      = 5

# Buttons that are controls rather than runebook entries, excluded when pairing
# entry text to buttons. Button 0 is "close gump" (what a right-click sends) and
# must never be sent deliberately.
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 503, 504]

# Entry buttons observed starting at 10. Recalls use the entry button; a rune
# also publishes a "gate" button at entry + 30000.
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
AR_GATE_OFFSET = 30000

# Safety cap on page walking; the Page X/Y footer normally bounds it first.
AR_MAX_PAGES = 20


# =============================================================================
# CONFIG - MINING
# =============================================================================

PORTABLE_FORGE_SER = Items.FindByID(0x0FB1, -1, Player.Backpack.Serial, False, False)
ORE_ID = [0x19BA, 0x19B9, 0x19B8, 0x19B7]
PURGE_ID = [0x1BF2, 0x1726, 0x1779, 0x0F0F, 0x0F10, 0x0F11, 0x0F12, 0x0F13,
            0x0F14, 0x0F15, 0x0F16, 0x0F17, 0x0F18, 0x0F19, 0x0F1A, 0x0F1B,
            0x0F1C, 0x0F1D, 0x0F1E, 0x0F1F, 0x0F20, 0x0F21, 0x0F22, 0x0F23,
            0x0F24, 0x0F25, 0x0F26, 0x0F27, 0x0F28, 0x3192, 0x3193, 0x3194,
            0x3195, 0x3196, 0x3197, 0x3198, 0x5732]

WAYPOINT = None

DEBUG = True

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD  = 0x0021


# =============================================================================
# SERVER MESSAGES
# =============================================================================
# Meditation, from ServUO Scripts/Skills/Meditation.cs. The "Regenative"
# misspelling is in the server source - do not correct it.

MED_TRANCE   = "You enter a meditative trance."                        # 501851
MED_AT_PEACE = "You are at peace."                                     # 501846
MED_NO_FOCUS = "You cannot focus your concentration."                  # 501850
MED_BUSY     = "You are busy doing something else and cannot focus."   # 501845
MED_WEAK     = "The mind is strong but the body is weak."              # 501849
MED_ARMOR    = "Regenative forces cannot penetrate your armor!"        # 500135
MED_HANDS    = "Your hands must be free to cast spells or meditate."   # 502626

MED_ALL = [MED_TRANCE, MED_AT_PEACE, MED_NO_FOCUS, MED_BUSY, MED_WEAK,
           MED_ARMOR, MED_HANDS]

MSG_NO_MANA = [
    "Insufficient mana",                    # 502625
    "You don't have enough mana",
]


# =============================================================================
# RUNTIME STATE
# =============================================================================

_armor_blocks_meditation = False
_passive_notice_shown = False

_routes = []              # [(page, entry button, rune name)] for the mining folder
_routes_valid = False

_journal_cursor = 0.0     # unix timestamp of the newest journal line consumed
_greyskull_pending = False
_greyskull_active = False


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Mine] " + text, hue, False)


def debug(text, hue=HUE_INFO):
    if DEBUG:
        log(text, hue)


def journal_hit(messages):
    for text in messages:
        if Journal.Search(text):
            return True
    return False


def clear_journal(messages):
    for text in messages:
        Journal.Clear(text)


# --- Razor Enhanced signature shims -----------------------------------------
# Both of these changed and silently broke the original script.

def chat_say(text):
    """Player.ChatSay(colour, msg) is current; older builds took just msg."""
    try:
        Player.ChatSay(0, text)
    except TypeError:
        Player.ChatSay(text)


def gump_lines(gump_id, data_only=False):
    """Gumps.GetLineList(gumpId, dataOnly) is current; older builds took 1 arg."""
    try:
        return Gumps.GetLineList(gump_id, data_only)
    except TypeError:
        return Gumps.GetLineList(gump_id)


def has_gump(gump_id):
    try:
        return Gumps.HasGump(gump_id)
    except TypeError:
        return Gumps.HasGump() and Gumps.CurrentGump() == gump_id


def wait_context(entity, delay=CONTEXT_TIMEOUT, show=False):
    try:
        return Misc.WaitForContext(entity, delay, show)
    except TypeError:
        return Misc.WaitForContext(entity, delay)


# =============================================================================
# MANA / MEDITATION
# =============================================================================

def hands_are_free():
    return (Player.GetItemOnLayer("RightHand") is None and
            Player.GetItemOnLayer("LeftHand") is None)


def free_hands():
    """Stow anything held so meditation can start. True if hands end up free."""
    for layer in ("RightHand", "LeftHand"):
        item = Player.GetItemOnLayer(layer)
        if item is not None:
            debug("Stowing %s to free hands for meditation."
                  % (item.Name or "0x%X" % item.ItemID))
            Items.Move(item.Serial, Player.Backpack.Serial, -1)
            Misc.Pause(HAND_MOVE_PAUSE)
    return hands_are_free()


def mana_goal(minimum):
    """How much mana to actually meditate up to."""
    if _greyskull_pending:
        return minimum          # someone is calling - set off as soon as we can
    if MANA_TARGET > 0:
        return max(minimum, min(MANA_TARGET, Player.ManaMax))
    return max(minimum, Player.ManaMax)


def passive_regen(deadline, minimum):
    """Stand still and let mana tick back. Used when meditation is blocked."""
    global _passive_notice_shown
    if not _passive_notice_shown or not PASSIVE_REGEN_NOTICE_ONCE:
        log("Waiting on passive mana regeneration.", HUE_WARN)
        _passive_notice_shown = True
    while time.time() < deadline and Player.Mana < minimum:
        if Player.IsGhost:
            return False
        interruptible_pause(MEDITATION_POLL)
    return Player.Mana >= minimum


def ensure_mana(minimum=None, reason="travel"):
    """Meditate until there is enough mana. True if the threshold was reached."""
    global _armor_blocks_meditation

    if minimum is None:
        minimum = MIN_MANA_TO_TRAVEL
    if Player.Mana >= minimum:
        return True

    goal = mana_goal(minimum)
    log("Mana %d/%d, need %d to %s - recovering."
        % (Player.Mana, Player.ManaMax, minimum, reason), HUE_WARN)

    deadline = time.time() + MEDITATION_TIMEOUT / 1000.0

    if _armor_blocks_meditation:
        return passive_regen(deadline, minimum)

    if DISARM_FOR_MEDITATION and not hands_are_free():
        free_hands()

    while time.time() < deadline and Player.Mana < goal:
        if Player.IsGhost:
            return False
        if Player.Mana >= minimum and Player.Mana >= goal:
            break

        clear_journal(MED_ALL)
        Player.UseSkill("Meditation")
        interruptible_pause(1200)

        if Journal.Search(MED_ARMOR):
            log("Armour blocks meditation - passive regeneration only from "
                "here on.", HUE_WARN)
            _armor_blocks_meditation = True
            return passive_regen(deadline, minimum)

        if Journal.Search(MED_HANDS):
            if DISARM_FOR_MEDITATION and free_hands():
                continue
            log("Hands are not free and cannot be emptied.", HUE_WARN)
            return passive_regen(deadline, minimum)

        if Journal.Search(MED_AT_PEACE):
            break                       # already at full mana

        if Journal.Search(MED_TRANCE):
            # In trance: sit still until mana stops climbing, then re-issue.
            last = Player.Mana
            stalled = 0
            while time.time() < deadline and Player.Mana < goal:
                interruptible_pause(MEDITATION_POLL)
                if Player.Mana > last:
                    last = Player.Mana
                    stalled = 0
                else:
                    stalled += 1
                    if stalled >= MEDITATION_STALL:
                        break           # trance ended
            continue

        # MED_NO_FOCUS / MED_BUSY / MED_WEAK, or no message at all.
        interruptible_pause(MEDITATION_RETRY_MS)

    ok = Player.Mana >= minimum
    if ok:
        log("Mana %d/%d - continuing." % (Player.Mana, Player.ManaMax), HUE_GOOD)
    else:
        log("Gave up recovering mana at %d/%d." % (Player.Mana, Player.ManaMax),
            HUE_BAD)
    return ok


def travel_failed_for_mana():
    """Did the last travel attempt bounce off an empty mana pool?"""
    return journal_hit(MSG_NO_MANA)


# =============================================================================
# ACCOUNT RUNEBOOK
# =============================================================================

def openAR():
    if has_gump(AR_GUMPID):
        Misc.Pause(250)
        return True
    chat_say(AR_COMMAND)
    ret = Gumps.WaitForGump(AR_GUMPID, 10000)
    Misc.Pause(250)
    return bool(ret) or has_gump(AR_GUMPID)


def getARButtons():
    """Every button id defined in the current gump's layout."""
    if not openAR():
        return []
    layout = Gumps.GetGumpRawLayout(AR_GUMPID)
    if not layout:
        return []
    buttons = []
    for piece in re.split(r"\}\s*\{", layout):
        if "button" in piece.lower():
            # { button X Y NormalID PressedID Type Param ButtonID }
            data = re.findall(r"\d+", piece)
            if data:
                buttons.append(int(data[-1]))
    return buttons


def ar_page_info():
    """(current, total) from the "Page 1/3" footer. (1, 1) if absent."""
    lines = gump_lines(AR_GUMPID) or []
    for line in reversed(list(lines)):
        found = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", line, re.I)
        if found:
            return int(found.group(1)), int(found.group(2))
    return (1, 1)


def parse_ar_page():
    """Folders and destinations on the CURRENT page.

    Entries are identified by their "N. Name" text rather than by counting
    lines, and paired with the page's entry buttons in display order. That works
    whether the shard numbers buttons per-page or continuously across pages.

    A rune is followed by a coordinate line - "1. Mining (Malas)" then
    "(1118, 1464, -95)". A folder is not. That is the discriminator; the
    entry+30000 gate button is used as a secondary signal.
    """
    if not openAR():
        return {}, {}

    lines = gump_lines(AR_GUMPID) or []
    buttons = getARButtons()
    entry_buttons = sorted(b for b in buttons
                           if AR_ENTRY_BUTTON_MIN <= b <= AR_ENTRY_BUTTON_MAX
                           and b not in AR_CONTROL_BUTTONS)

    entries = []
    for line in lines:
        text = (line or "").strip()
        if not text or text.startswith("<"):
            continue                      # header and the Page X/Y footer
        if re.match(r"^\(\s*[-+]?\d", text):
            if entries:                   # coordinates belong to the entry above
                entries[-1]["coord"] = [int(x) for x in
                                        re.findall(r"[-+]?\d+", text)]
            continue
        found = re.match(r"^(\d+)\.\s*(.+)$", text)
        if found:
            entries.append({"index": int(found.group(1)),
                            "label": found.group(2).strip(),
                            "coord": None})
        # Anything else - "New Rune", "New Runebook", "Organize", the folder
        # name - is not an entry and has no entry button.

    folders = {}
    destinations = {}
    for entry, button in zip(entries, entry_buttons):
        is_dest = (entry["coord"] is not None or
                   (button + AR_GATE_OFFSET) in buttons)
        if is_dest:
            destinations[button] = {"name": entry["label"],
                                    "coord": entry["coord"]}
        else:
            folders[button] = entry["label"]

    if len(entries) != len(entry_buttons):
        debug("AR page: %d entries but %d entry buttons - pairing may be off."
              % (len(entries), len(entry_buttons)), HUE_WARN)

    return folders, destinations


# Kept under the original name so nothing else has to change.
def mapARPage():
    return parse_ar_page()


def ar_page_step(button):
    if button not in getARButtons():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, 10000)
    Misc.Pause(250)
    return True


def ar_next_page():
    return ar_page_step(AR_NEXT_PAGE_BUTTON)


def ar_prev_page():
    return ar_page_step(AR_PREV_PAGE_BUTTON)


def ar_goto_page(target):
    """Move to a specific page of the current folder."""
    current, total = ar_page_info()
    target = max(1, min(target, total))
    for _ in range(AR_MAX_PAGES * 2):
        if current == target:
            return True
        moved = ar_next_page() if current < target else ar_prev_page()
        if not moved:
            return False
        current, total = ar_page_info()
    return current == target


def iter_ar_pages():
    """Yield (page_number, folders, destinations) for every page, from page 1.

    The Page X/Y footer gives an exact page count, so this does not have to
    guess at when it has wrapped.
    """
    if not openAR():
        return
    if not ar_goto_page(1):
        debug("Could not rewind the runebook to page 1.", HUE_WARN)

    current, total = ar_page_info()
    total = min(total, AR_MAX_PAGES)

    for page in range(current, total + 1):
        folders, destinations = parse_ar_page()
        yield page, folders, destinations
        if page >= total:
            return
        if not ar_next_page():
            return


def ar_find(target, want_dest):
    """Locate a folder (or rune) by name across every page.

    Returns (page, button, name) or None.

    An EXACT case-insensitive name match always beats a substring match, and the
    whole book is searched before choosing. That matters because this runebook
    holds both "Taming Locations" (page 1) and "TamingDeed" (page 2) - a
    first-substring-wins search would take the wrong one and never look further.
    """
    wanted = (target or "").strip().lower()
    if not wanted:
        return None

    exact = None
    partial = None

    for page, folders, destinations in iter_ar_pages():
        pool = destinations if want_dest else folders
        for button in sorted(pool):
            name = pool[button]["name"] if want_dest else pool[button]
            low = (name or "").strip().lower()
            if low == wanted:
                exact = (page, button, name)
                break
            if partial is None and wanted in low:
                partial = (page, button, name)
        if exact:
            break

    hit = exact or partial
    if hit and partial and not exact:
        debug("'%s' matched '%s' by substring on page %d."
              % (target, hit[2], hit[0]))
    return hit


def goDir(dir=None):
    """Enter a folder by name, searching every page. None = back to root."""
    if dir is None:
        if AR_ROOT_BUTTON in getARButtons():
            Misc.Pause(250)
            Gumps.SendAction(AR_GUMPID, AR_ROOT_BUTTON)
            Gumps.WaitForGump(AR_GUMPID, 10000)
            Misc.Pause(250)
        return True

    if not openAR():
        log("Could not open the account runebook.", HUE_BAD)
        return False

    hit = ar_find(dir, want_dest=False)
    if hit is None:
        log("Folder '%s' not found on any page. Run diag_ar_gump.py." % dir,
            HUE_BAD)
        return False

    page, button, name = hit
    if not ar_goto_page(page):
        log("Found '%s' on page %d but could not get back to it." % (name, page),
            HUE_BAD)
        return False

    Misc.Pause(250)
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, 10000)
    Misc.Pause(250)
    return True


def ar_recall(button, what):
    """Click a rune's entry button, recovering mana if the cast is refused."""
    clear_journal(MSG_NO_MANA)
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(1000)
    if not travel_failed_for_mana():
        return True

    log("Recall to %s refused for mana - recovering and retrying." % what,
        HUE_WARN)
    clear_journal(MSG_NO_MANA)
    if not ensure_mana(reason="retry recall"):
        return False
    if not openAR():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(1000)
    return not travel_failed_for_mana()


def goDest(dest=None):
    """Recall to a named destination, searching every page."""
    if dest is None:
        return False
    if not ensure_mana(reason="recall to %s" % dest):
        return False
    if not openAR():
        return False

    hit = ar_find(dest, want_dest=True)
    if hit is None:
        log("Destination '%s' not found on any page. Run diag_ar_gump.py." % dest,
            HUE_BAD)
        return False

    page, button, name = hit
    if not ar_goto_page(page):
        log("Found rune '%s' on page %d but could not get back to it."
            % (name, page), HUE_BAD)
        return False

    return ar_recall(button, name)


def build_routes():
    """Every rune in the current folder, as (page, button), across all pages.

    The old code only ever saw page 1, so a mining folder of 3 pages ran the
    same 9 runes forever.
    """
    global _routes, _routes_valid
    _routes = []
    for page, _folders, destinations in iter_ar_pages():
        for button in sorted(destinations):
            _routes.append((page, button, destinations[button]['name']))
    _routes_valid = True
    log("Route: %d runes across the mining folder." % len(_routes),
        HUE_GOOD if _routes else HUE_BAD)
    return _routes


def ensure_route_view():
    """Make sure the gump is showing the mining folder, not the root."""
    _folders, destinations = parse_ar_page()
    if destinations:
        return True
    _page, total = ar_page_info()
    if total > 1:
        # Runes might just be on another page of this folder.
        for _p, _f, dests in iter_ar_pages():
            if dests:
                return True
    debug("Runebook is not showing runes - re-entering the mining folder.")
    return goMiningDir()


def goNext():
    """Recall to the next mining waypoint, walking pages as needed."""
    global WAYPOINT, _routes_valid
    if WAYPOINT is None:
        WAYPOINT = 0
    if not ensure_mana(reason="recall to next waypoint"):
        return
    if not openAR():
        return
    if not ensure_route_view():
        return

    if not _routes_valid or not _routes:
        build_routes()
    if not _routes:
        log("No runes found in the mining folder. Run diag_ar_gump.py.", HUE_BAD)
        return

    if WAYPOINT >= len(_routes):
        WAYPOINT = 0
    page, button, name = _routes[WAYPOINT]
    WAYPOINT += 1

    if not ar_goto_page(page):
        log("Could not reach page %d of the mining folder." % page, HUE_WARN)
        _routes_valid = False
        return

    debug("Waypoint %d/%d: %s (page %d, button %d)"
          % (WAYPOINT, len(_routes), name, page, button))
    ar_recall(button, name)
    Misc.Pause(max(1000, Timer.Remaining("202506282021 Go Next")))


def goFolders(folders):
    """Walk from the root into a folder path."""
    goDir()
    for folder in folders:
        if folder == '':
            continue
        if not goDir(folder):
            return False
    return True


def goMiningDir():
    global _routes_valid
    _routes_valid = False          # folder changed; the cached route is stale
    return goFolders(MINING_FOLDER)


def goDropDir():
    return goFolders(DROP_FOLDER)


def goArcaneDir():
    return goFolders(ARCANE_FOLDER)


# =============================================================================
# GREYSKULL
# =============================================================================

def prime_journal_cursor():
    """Start the cursor at 'now' so old lines cannot trigger on startup."""
    global _journal_cursor
    try:
        entries = Journal.GetJournalEntry(0.0)
        for entry in entries or []:
            stamp = getattr(entry, "Timestamp", 0.0) or 0.0
            if stamp > _journal_cursor:
                _journal_cursor = stamp
    except Exception:
        _journal_cursor = 0.0


def new_journal_entries():
    """Journal lines that have arrived since the last call.

    A timestamp cursor is used rather than Search + Clear, so this reads the
    chant without disturbing the mining and meditation journal checks, and can
    match case-insensitively.
    """
    global _journal_cursor
    try:
        entries = Journal.GetJournalEntry(_journal_cursor)
    except Exception:
        return []
    fresh = []
    for entry in entries or []:
        stamp = getattr(entry, "Timestamp", 0.0) or 0.0
        if stamp > _journal_cursor:
            _journal_cursor = stamp
        fresh.append(entry)
    return fresh


# "System: <Public> Fred Kruger: By The Power Of Greyskull!"
#  \_ optional  \_ optional     \_ caller    \_ what was said
CHAT_LINE = re.compile(
    r"^\s*(?:System\s*:\s*)?"
    r"(?:[<\[](?P<channel>[^>\]]+)[>\]]\s*)?"
    r"(?:(?P<caller>[^:]{1,40})\s*:\s*)?"
    r"(?P<said>.*)$")


def parse_chat_line(text):
    """(channel, caller, said) from a journal line. Any part may be None."""
    if not text:
        return (None, None, "")
    found = CHAT_LINE.match(text)
    if not found:
        return (None, None, text)
    channel = found.group("channel")
    caller = found.group("caller")
    said = found.group("said") or ""
    if not said:                       # nothing after the colon - take it whole
        return (channel, None, text)
    return (channel,
            caller.strip() if caller else None,
            said.strip())


def caller_allowed(caller):
    if GREYSKULL_IGNORE_SELF and caller and Player.Name:
        if Player.Name.strip().lower() in caller.lower():
            return False
    if not GREYSKULL_ALLOWED_CALLERS:
        return True                    # anyone may call it - the default
    if not caller:
        return False
    low = caller.lower()
    for allowed in GREYSKULL_ALLOWED_CALLERS:
        if allowed.strip().lower() in low:
            return True
    return False


def channel_allowed(channel):
    want = GREYSKULL_REQUIRE_CHANNEL.strip().lower()
    if not want:
        return True
    return bool(channel) and want in channel.lower()


def greyskull_heard():
    """True if a fresh journal line is the call-out, from an accepted caller."""
    for entry in new_journal_entries():
        raw = getattr(entry, "Text", "") or ""
        if not raw:
            continue

        # Match against the whole line: the phrase is in the spoken part, but
        # matching the raw text too keeps this working if the shard changes the
        # prefix format.
        low = raw.lower()
        matched = None
        for phrase in GREYSKULL_PHRASES:
            phrase = phrase.strip().lower()
            if phrase and phrase in low:
                matched = phrase
                break
        if matched is None:
            continue

        channel, caller, _said = parse_chat_line(raw)

        if not channel_allowed(channel):
            debug("Greyskull ignored - wrong channel (%s): %s"
                  % (channel or "none", raw))
            continue
        if not caller_allowed(caller):
            debug("Greyskull ignored - caller not allowed (%s): %s"
                  % (caller or "unknown", raw))
            continue

        log("Greyskull called by %s%s." % (caller or "someone",
                                           " in %s" % channel if channel else ""),
            HUE_GOOD)
        debug("Greyskull line: %s" % raw)
        return True
    return False


def poll_greyskull():
    """Detect the chant. Safe to call from anywhere - only raises a flag.

    Detection is separated from the response because the response travels, and
    travel waits poll for the chant. Acting here would recurse.
    """
    global _greyskull_pending
    if _greyskull_active:
        return False
    if _greyskull_pending:
        return True
    if greyskull_heard():
        _greyskull_pending = True
        log("Greyskull heard - responding at the next safe point.", HUE_GOOD)
    return _greyskull_pending


def interruptible_pause(total_ms, slice_ms=250):
    """Misc.Pause, but keeps listening for the chant while it waits.

    Long blocking pauses - meditation especially - used to swallow the call-out
    entirely.
    """
    remaining = int(total_ms)
    while remaining > 0:
        step = min(slice_ms, remaining)
        Misc.Pause(step)
        remaining -= step
        poll_greyskull()


def checkGreyskull():
    """Respond to the chant. Never call this from inside a travel routine."""
    global _greyskull_pending, _greyskull_active

    if not poll_greyskull():
        return False

    _greyskull_pending = False
    _greyskull_active = True
    try:
        log("Greyskull - interrupting mining and recalling to the Arcane "
            "Circle.", HUE_GOOD)
        Player.HeadMessage(55, "Pausing all mining activity...")
        Target.Cancel()
        Misc.Pause(600)

        if not goArcaneDir():
            log("Could not reach the Arcane folder in the runebook.", HUE_BAD)
        elif not goDest(ARCANE_POINT):
            log("Could not recall to '%s' in the Arcane folder." % ARCANE_POINT,
                HUE_BAD)
        else:
            log("At the Arcane Circle - holding.", HUE_GOOD)
            Misc.Pause(GREYSKULL_HOLD_MS)

        log("Returning to the mining route.", HUE_INFO)
        goMiningDir()
        goNext()
        Misc.Pause(5000)
    finally:
        _greyskull_active = False
    return True


# =============================================================================
# VENDORS
# =============================================================================

def find_vendors(names, rng=VENDOR_RANGE):
    """Mobiles whose name contains any of `names`, case-insensitively.

    Mobiles.Filter().Name is an exact match, which is why the original
    findNameMobile() stopped finding renamed NPCs.
    """
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = rng
    found = Mobiles.ApplyFilter(f)
    if not found:
        return []

    out = []
    for mob in found:
        name = mob.Name or ""
        if not name:
            continue
        low = name.lower()
        for want in names:
            if want.strip().lower() in low:
                out.append(mob)
                break
    return out


def context_labels(entries):
    labels = []
    for entry in entries or []:
        label = getattr(entry, "Entry", None)
        labels.append(label if label is not None else str(entry))
    return labels


def talk_to(mob, wanted):
    """Open the context menu and pick the first matching entry."""
    entries = wait_context(mob)
    if not entries:
        log("%s gave no context menu." % (mob.Name or "vendor"), HUE_WARN)
        return False

    labels = context_labels(entries)
    debug("%s menu: %s" % (mob.Name or "vendor", " | ".join(labels)))

    for want in wanted:
        for label in labels:
            if want.strip().lower() in (label or "").lower():
                Misc.Pause(100)
                Misc.ContextReply(mob, label)
                Misc.Pause(600)
                return True

    log("%s has no entry matching %s - it offers: %s"
        % (mob.Name or "vendor", wanted, " | ".join(labels)), HUE_BAD)
    return False


def visit_vendor(vendor):
    if not goFolders(vendor["folder"]):
        return False
    if not goDest(vendor["point"]):
        return False
    Misc.Pause(500)

    mobs = find_vendors(vendor["names"])
    if not mobs:
        log("No NPC matching %s within %d tiles of %s. Run diag_vendors.py."
            % (vendor["names"], VENDOR_RANGE, vendor["point"]), HUE_BAD)
        return False

    ok = False
    for mob in mobs:
        if talk_to(mob, vendor["context"]):
            ok = True
            if vendor.get("gump"):
                gump_id, button = vendor["gump"]
                if Gumps.WaitForGump(gump_id, 10000):
                    Gumps.SendAction(gump_id, button)
                    Misc.Pause(500)
                else:
                    log("%s: expected gump 0x%X never appeared."
                        % (vendor["label"], gump_id), HUE_WARN)
    if ok:
        log("%s: done." % vendor["label"], HUE_GOOD)
    return ok


def validate_vendors():
    """Report the vendor table at startup and reject unusable entries.

    A stop with no `names` can never match an NPC, and the old code failed
    silently when that happened. Now it is called out before the first run.
    """
    usable = []
    for index, vendor in enumerate(VENDORS):
        label = vendor.get("label") or "vendor %d" % (index + 1)

        if not vendor.get("enabled", True):
            log("  %-22s disabled" % label, HUE_INFO)
            continue

        problems = []
        if not vendor.get("names"):
            problems.append("no NPC names")
        if not vendor.get("point"):
            problems.append("no rune name")
        if not vendor.get("context"):
            problems.append("no context entries")

        if problems:
            log("  %-22s SKIPPED - %s" % (label, ", ".join(problems)), HUE_BAD)
            log("      Fill it in at the top of this script, or set "
                "\"enabled\": False.", HUE_WARN)
            continue

        log("  %-22s %s -> %s   NPC: %s" %
            (label, "/".join(vendor["folder"]) or "(root)", vendor["point"],
             ", ".join(vendor["names"])), HUE_GOOD)
        usable.append(vendor)

    if not usable:
        log("No usable vendor stops configured - the vendor round will do "
            "nothing.", HUE_BAD)
    return usable


def checkDeeds():
    for vendor in validate_vendors():
        debug("Vendor round: %s" % vendor["label"])
        visit_vendor(vendor)
        poll_greyskull()        # heard during the round, acted on afterwards


# =============================================================================
# MINING
# =============================================================================

def mine(shovel=None):
    if shovel is None:
        shovel = Items.FindByID(0x0F39, -1, Player.Backpack.Serial, False, False)
        Misc.Pause(150)
    if shovel is None:
        Timer.Create("202506281920 Shovel Needed", 1000)
        return False
    Journal.Clear("You")
    Journal.Clear("No Metal")
    Target.TargetResource(shovel, 0)
    TOGGLE = True
    ret = False
    Timer.Create("202506282344 Timeout", 5000)
    while TOGGLE and Timer.Check("202506282344 Timeout"):
        if checkGreyskull():
            return False
        if not bagcheck():
            log("Too heavy - returning to drop-off.", HUE_WARN)
            smelt()
            dropoff()
            goMiningDir()
            return False
        if Journal.Search("You"):
            if Journal.Search("You can't mine there"):
                ret = False
            else:
                ret = True
            TOGGLE = False
        elif Journal.Search("no metal"):
            Timer.Create("202506282021 Go Next", 2500)
            TOGGLE = False
            ret = False
            Journal.Clear("no metal")
        Misc.Pause(100)
    Journal.Clear("You")
    return ret


def uses(itemID=None):
    if itemID is None:
        return 0
    itms = Items.FindAllByID(itemID, -1, Player.Backpack.Serial, False, False)
    total = 0
    for itm in itms:
        total += int(Items.GetPropValue(itm, "Uses Remaining"))
    return total


def makeshovel():
    TINK_ID = 0x1EB8
    Items.UseItemByID(TINK_ID, -1)
    Gumps.WaitForGump(0x38920abd, 10000)
    Misc.Pause(10)
    Gumps.SendAction(0x38920abd, 15)
    Misc.Pause(100)
    Gumps.WaitForGump(0x38920abd, 10000)
    Misc.Pause(10)
    if uses(TINK_ID) < 10:
        Gumps.SendAction(0x38920abd, 23)
        Misc.Pause(100)
        Gumps.WaitForGump(0x38920abd, 10000)
        Misc.Pause(10)
    Gumps.SendAction(0x38920abd, 72)
    Misc.Pause(100)
    Gumps.WaitForGump(0x38920abd, 10000)
    Misc.Pause(10)
    Gumps.CloseGump(0x38920abd)


def bagcheck():
    ITEM_COUNT = 0.6
    WEIGHT_LIMIT = 0.6
    nums = [float(x) for x in
            re.findall("[0-9]+", Items.GetPropStringByIndex(Player.Backpack.Serial, 2))]
    if len(nums) == 4:
        if ITEM_COUNT < nums[0] / nums[1]:
            Timer.Create("202506281947 Bagcheck", 1000)
            return False
        if WEIGHT_LIMIT < nums[2] / nums[3]:
            Timer.Create("202506281947 Bagcheck", 1000)
            return False
        return True
    return False


def dumpkeys():
    ret = False
    for key in Items.FindAllByID([0x1BE8, 0xA54A], -1, Player.Backpack.Serial,
                                 False, False):
        wait_context(key)
        Misc.Pause(300)
        Misc.ContextReply(key, "Refill from stock")
        Misc.Pause(2000)
        ret = bagcheck()
    for key in Items.FindAllByID(0x2259, -1, -1, 2, False):
        wait_context(key)
        Misc.Pause(300)
        Misc.ContextReply(key, "Refill from stock")
        Misc.Pause(2000)
        ret = bagcheck()
    return ret


def smelt():
    check = {}
    for ore in Items.FindAllByID(ORE_ID, -1, Player.Backpack.Serial, False, False):
        if ore.ItemID == 0x19B7 and int(Items.GetPropValue(ore, "Weight")) < 3:
            if ore.Hue in check:
                check[ore.Hue].append(ore.Serial)
            else:
                check[ore.Hue] = [ore.Serial]
        if int(Items.GetPropValue(ore, "Weight")) >= 3:
            Items.UseItem(ore)
            Target.WaitForTarget(5000, True)
            Misc.Pause(250)
            Target.TargetExecute(PORTABLE_FORGE_SER)
            Misc.Pause(250)
    for hue in check:
        if len(check[hue]) > 1:
            Timer.Create("202506281920 Shovel Needed",
                         Timer.Remaining("202506281920 Shovel Needed") + 601)
            Items.Move(check[hue][0], Player.Backpack.Serial, -1)
            Misc.Pause(750)


def dropoff():
    goDropDir()
    goDest(DROP_POINT)
    for itm in Items.FindAllByID(PURGE_ID, -1, Player.Backpack.Serial, False, False):
        if itm.ItemID == 0x1BF2 and itm.Hue == 0:
            move_ingot = max(0, itm.Amount - 20)
            if move_ingot > 0:
                Items.Move(itm.Serial, DROP_CHEST_SERIAL, move_ingot)
        else:
            Items.Move(itm.Serial, DROP_CHEST_SERIAL, -1)
        Misc.Pause(1000)
    dumpkeys()
    Timer.Create("202506282242 Drop", 60 * 60 * 1000)


def mineComplete():
    CONTINUE = bagcheck()
    while CONTINUE:
        if checkGreyskull():
            return
        CONTINUE = mine()
        smelt()
        Misc.Pause(250)
        if Timer.Check("202506281920 Shovel Needed"):
            log("Making a shovel.")
            CONTINUE = True
            makeshovel()
            Misc.Pause(Timer.Remaining("202506281920 Shovel Needed"))
    if Timer.Check("202506281947 Bagcheck"):
        debug("Bagcheck")
        smelt()
        if not dumpkeys():
            dropoff()
            goMiningDir()
        Misc.Pause(Timer.Remaining("202506281947 Bagcheck"))


# =============================================================================
# MAIN LOOP
# =============================================================================

if __name__ == "__main__":
    log("Starting. Mana floor for travel: %d." % MIN_MANA_TO_TRAVEL, HUE_GOOD)
    if Player.GetSkillValue("Meditation") <= 0:
        log("No Meditation skill - mana recovery will be passive only.", HUE_WARN)

    log("Vendor round:", HUE_INFO)
    validate_vendors()

    log("Listening for: %s" % ", ".join(GREYSKULL_PHRASES), HUE_INFO)

    goMiningDir()
    smelt()
    Journal.Clear()
    prime_journal_cursor()      # ignore anything said before the script started

    while not Player.IsGhost:
        # Top of the loop, so a chant heard anywhere - mid-meditation, mid-vendor
        # round, mid-travel - is acted on at the first safe moment.
        if checkGreyskull():
            continue

        if not Timer.Check("202506282047 Resource Orders"):
            checkDeeds()
            Misc.Pause(1000)
            goMiningDir()
            goNext()
            Timer.Create("202506282047 Resource Orders", 30 * 60 * 1000)
        elif not Timer.Check("202506282242 Drop"):
            dropoff()
            goMiningDir()
            Timer.Create("202506282242 Drop", 60 * 60 * 1000)
        else:
            goNext()
            if checkGreyskull():
                continue
            mineComplete()
            Misc.Pause(25)
