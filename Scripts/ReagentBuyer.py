"""
Reagent Buyer - recall round the vendor runes, buy, and store what you bought.
=============================================================================

For Razor Enhanced (IronPython 3.4). Target: the UOAlive / Beyond Sosaria
freeshard.

THE ROUND
---------
    walk the Account Runebook into the reagent-shop folder
    for every "Mage Shop" rune in it, on every page:
        recall
        find the mage / alchemist standing there
        open their Buy window, let the Buy Agent fill it
        put what arrived into the storage key
    pause, then do it again

WHY THE OLD ONE DID NOT BUY
---------------------------
Three separate faults, any one of which was enough:

1. THE VENDOR WAS NEVER FOUND.

       filter = Mobiles.Filter()
       filter.Name = "the mage"

   `Mobiles.Filter().Name` is an EXACT match, not a substring, so it only ever
   matches a mobile actually called "the mage". Worse, "the mage" is not a
   name at all - it is the vendor's TITLE, and a title lives in the tooltip,
   not in Name. The filter returned an empty list every time and the script
   reported "No vendor found!" or silently bought nothing. It also set no
   RangeMax, which means everything the client knows about.

   Vendors are matched here on the tooltip title first, with the name as a
   cheap pre-check, and the list is filtered to VENDOR_RANGE tiles.

2. THE BUY AGENT WAS NEVER TURNED ON. The old script named a list in
   BUY_LIST_NAME and then never told Razor to use it, so opening the shop did
   nothing: the Buy Agent only fills a vendor window when it is enabled AND
   pointing at a list. Both happen at startup here, and the run refuses to
   start if the agent will not come on.

3. THE PAGE BUTTON WAS A GUESS. goNextPage() pressed button 6. The real one
   is 504 (503 back, 5 root), read off the Gump Inspector - see
   docs/account-runebook-gump.md. Pressing 6 did nothing, so every rune past
   page 1 was unreachable.

AND ONE THAT WOULD HAVE BITTEN LATER
------------------------------------
    Misc.ContextReply(STORAGE_KEY_SERIAL, 2)

A context menu answered by INDEX. Entry 2 is whatever the shard put there
this week, and on a storage key the neighbours include entries that take
things out. Menus are matched by label here, exactly first, and anything on
CONTEXT_NEVER is refused outright.

WHAT IT VERIFIES
----------------
Nothing here trusts that a click worked:

  * a recall is confirmed against the rune's OWN coordinates, which the
    runebook prints under every entry
  * a purchase is confirmed by GOLD SPENT - the shop window opening is not
    evidence that anything was bought
  * a deposit is confirmed by the pack being lighter afterwards

JOURNAL
-------
This clears the journal when it needs to read the result of something.
"""

import re
import time


# Printed as the first line at startup. Razor CACHES the loaded script even
# after the file on disk changes - if this is not the version you expect, hit
# Reload in the Scripting tab.
SCRIPT_VERSION = "2026-10-24.3"


# =============================================================================
# CONFIG - THE THINGS YOU SET
# =============================================================================

# The storage key the reagents go into. A Master Key takes everything in one
# press. 0 means "do not store at all - leave it in the pack".
STORAGE_KEY_SERIAL = 0x4335A205

# The Razor BUY AGENT list to use, set up in the Razor Enhanced GUI with the
# reagents and amounts you want. The agent is enabled and pointed at this list
# at startup; without it, opening a vendor's Buy window buys nothing.
BUY_LIST_NAME = "reagent purchase"

# ---------------------------------------------------------------------------
# ACCOUNT RUNEBOOK
# ---------------------------------------------------------------------------

# The folder path to the reagent shops, outermost first. Inspected
# 2026-10-24: "Town Vendors" is entry 16, on page 2/3 of the root - which is
# why the folder search walks pages rather than reading the first one.
REAGENT_SHOPS_FOLDER = ["Town Vendors"]

# WHICH RUNES IN THAT FOLDER TO VISIT.
#
# The folder is not all reagent shops. Inspected 2026-10-24, 15 runes over two
# pages: twelve "... Mage Shop ...", plus "Britt Carp Shop", "Britt
# Blasksmith" and "Britt Inscribe", which sell nothing this script wants.
#
# Matched case-insensitively against the rune's name. [] visits every rune in
# the folder.
#
# THE NAMES ARE TRUNCATED IN THE GUMP, and not always in the same place:
#
#     1. Britt Mage Shop (Tramm...      <- the phrase survives
#     7. Serpents Hold Mage Sho...      <- cut THROUGH it
#
# So a plain "is it in there" test drops Serpents Hold, silently. A wanted
# phrase also matches when the name ENDS with the start of it, which is all
# truncation can leave behind - see wanted_rune().
RUNE_MUST_MATCH = ["Mage Shop"]

# How much of a wanted phrase has to survive the truncation to count. Four is
# "Mage"; going lower starts matching things that only begin like it.
RUNE_MATCH_MIN_PREFIX = 4

# NOT WIRED UP YET. The old script carried these and never used them - kept
# because they are the serials-and-names kind of config that turns out to
# matter later, not cruft. Nothing reads them today: the storage key is
# carried, so there is no trip home.
DROP_FOLDER = ["Homes"]
DROP_POINT = "HOME"

# ---------------------------------------------------------------------------
# THE VENDORS
# ---------------------------------------------------------------------------

# Matched against the mobile's TITLE from its tooltip, and against its name as
# a cheap first look. Case-insensitive substring - a title reads like
# "Zoe the mage", so "the mage" has to match inside it.
VENDOR_TITLES = ["the mage", "the alchemist"]

# Never approached, however well the title matches. A Guildmaster's menu
# charges for training rather than selling reagents.
VENDOR_NEVER = ["guildmaster"]

# How far to look for them. ALWAYS set this - an unset RangeMax means
# everything the client knows about, which is 18-25 tiles of other people's
# vendors.
VENDOR_RANGE = 12

# The menu entry that opens their shop. Exact match first, then a guarded
# substring.
BUY_ENTRIES = ["Buy"]

# Entries never answered, whatever matches. These sit on the same menus and
# every one of them costs money or takes things away.
CONTEXT_NEVER = [
    "sell", "bribe", "train", "open bankbox", "empty", "destroy", "delete",
    "release", "discard", "purge", "rename", "dye",
]

# Entries that empty the pack into a storage key, tried in this order.
FILL_ENTRIES = ["Refill from stock", "Fill from backpack"]

# The shard's pick-everything-up command, said after each purchase because
# bought goods that will not fit land on the floor. "" turns it off.
GRAB_PHRASE = "[grab"

# ---------------------------------------------------------------------------
# TIMING
# ---------------------------------------------------------------------------

RECALL_SETTLE_MS = 2500     # after a recall, before checking where you are
ARRIVE_TOLERANCE = 3        # tiles from the rune's own coordinates
BUY_SETTLE_MS = 2500        # for the Buy Agent to fill the vendor window
CONTEXT_TIMEOUT_MS = 10000
CONTEXT_PAUSE_MS = 700
GUMP_TIMEOUT_MS = 10000
SETTLE_MS = 300

# Between laps of the whole book. Slept in slices so stopping the script does
# not mean waiting out the rest of it.
CYCLE_PAUSE_MS = 300000
SLEEP_SLICE_MS = 1000

# Ceilings, so nothing can spin forever.
MAX_LAPS = 0                # 0 = until you stop it
MAX_RUNES_PER_LAP = 60

# =============================================================================
# CONFIG - THE ACCOUNT RUNEBOOK'S BUTTONS
#
# Read off the Gump Inspector, not guessed. See docs/account-runebook-gump.md.
# =============================================================================

AR_COMMAND = "[ar"
AR_GUMPID = 0xC395ADB4

AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON = 5

# Entry buttons start at 10. A rune publishes a second "gate" button at
# entry + 30000, which opens a gate instead of recalling - never pressed here.
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
AR_GATE_OFFSET = 30000

# AND THE THIRD BUTTON ON EVERY ROW IS DELETE. Inside a folder each rune
# draws three: recall, gate, and an X that destroys the rune. The entry range
# above is what keeps both of the others out of the pairing - a delete button
# paired as an entry would not misfire a recall, it would delete somebody's
# rune. Nothing here ever presses one.
AR_DELETE_OFFSET = 60000
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 500, 503, 504]
AR_MAX_PAGES = 20

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Reagents] " + text, hue, False)


def sleep_ms(total):
    """Pause in slices, so a stop is noticed and the wait can be narrated."""
    end = time.time() + max(0, int(total)) / 1000.0
    while time.time() < end:
        Misc.Pause(min(SLEEP_SLICE_MS, max(1, int(
            (end - time.time()) * 1000))))


def has_gump(gump_id):
    try:
        return bool(Gumps.HasGump(gump_id))
    except Exception:
        return False


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


def chat_say(phrase):
    """ChatSay takes (msg) on every build, and (colour, msg) on all of them
    too. Both are tried rather than one being picked - see CLAUDE.md."""
    try:
        Player.ChatSay(phrase)
        return True
    except TypeError:
        pass
    except Exception as err:
        log("could not say %r: %r" % (phrase, err), HUE_BAD)
        return False
    try:
        Player.ChatSay(HUE_INFO, phrase)
        return True
    except Exception as err:
        log("could not say %r: %r" % (phrase, err), HUE_BAD)
        return False


def context_is_blocked(label):
    low = (label or "").lower()
    for banned in CONTEXT_NEVER:
        if banned.strip().lower() in low:
            return True
    return False


def context_labels(serial):
    try:
        entries = Misc.WaitForContext(serial, CONTEXT_TIMEOUT_MS, False)
    except TypeError:
        entries = Misc.WaitForContext(serial, CONTEXT_TIMEOUT_MS)
    except Exception as err:
        log("could not read a context menu: %r" % err, HUE_WARN)
        return []
    out = []
    for entry in list(entries or []):
        text = str(getattr(entry, "Entry", entry) or "").strip()
        if text:
            out.append(text)
    return out


def pick_entry(labels, wanted):
    """Which label to answer. EXACT first, then a guarded substring.

    An exact hit is always honoured - it was configured deliberately. The
    substring fallback exists because shards reword things, and it refuses
    anything on CONTEXT_NEVER: a vendor's menu carries Buy, Sell, Bribe and
    Train <skill> side by side, and three of those spend money.
    """
    for want in wanted:
        target = (want or "").strip().lower()
        for label in labels:
            if (label or "").strip().lower() == target:
                return label
    for want in wanted:
        target = (want or "").strip().lower()
        if not target:
            continue
        for label in labels:
            if target in (label or "").lower():
                if context_is_blocked(label):
                    log("  refusing %r - it matches CONTEXT_NEVER." % label,
                        HUE_WARN)
                    continue
                return label
    return None


def context_select(serial, wanted, what):
    """Open a context menu and answer it by LABEL. True if a reply was sent."""
    labels = context_labels(serial)
    if not labels:
        log("%s showed no context menu." % what, HUE_WARN)
        return False
    choice = pick_entry(labels, wanted)
    if choice is None:
        log("None of %s is on %s's menu, so NOTHING was pressed. It offers: %s"
            % (wanted, what, " | ".join(labels)), HUE_BAD)
        return False
    Misc.ContextReply(serial, choice)       # the real label, not the search
    Misc.Pause(CONTEXT_PAUSE_MS)
    return True


# =============================================================================
# THE ACCOUNT RUNEBOOK
#
# The parsing and the button numbers are lifted from harvest_runner.py, which
# has been walking this book for months. See docs/account-runebook-gump.md.
# =============================================================================

def openAR():
    if has_gump(AR_GUMPID):
        Misc.Pause(250)
        return True
    chat_say(AR_COMMAND)
    ret = Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
    Misc.Pause(250)
    return bool(ret) or has_gump(AR_GUMPID)


def ar_buttons():
    if not openAR():
        return []
    try:
        layout = Gumps.GetGumpRawLayout(AR_GUMPID) or ""
    except Exception:
        return []
    buttons = []
    for piece in re.split(r"\}\s*\{", layout):
        if "button" in piece.lower():
            data = re.findall(r"\d+", piece)
            if data:
                buttons.append(int(data[-1]))
    return buttons


def ar_page_info():
    """(current, total) from the "Page 1/3" footer. (1, 1) if there is none."""
    for line in reversed(list(gump_lines(AR_GUMPID))):
        found = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", line or "", re.I)
        if found:
            return int(found.group(1)), int(found.group(2))
    return (1, 1)


def parse_ar_page():
    """Folders and runes on the CURRENT page.

    Entries are picked out by their "N. Name" text and paired with the page's
    entry buttons IN DISPLAY ORDER, which is right whether the shard numbers
    buttons per page or continuously. Counting lines positionally is not:
    Razor drops empty strings out of a gump's table without leaving a gap.

    A rune is followed by a coordinate line; a folder is not. That is the
    discriminator, with the +30000 gate button as a second opinion.
    """
    if not openAR():
        return {}, {}

    lines = gump_lines(AR_GUMPID)
    buttons = ar_buttons()
    entry_buttons = sorted(b for b in buttons
                           if AR_ENTRY_BUTTON_MIN <= b <= AR_ENTRY_BUTTON_MAX
                           and b not in AR_CONTROL_BUTTONS)

    entries = []
    for line in lines:
        text = (line or "").strip()
        if not text or text.startswith("<"):
            continue
        if re.match(r"^\(\s*[-+]?\d", text):
            if entries:
                entries[-1]["coord"] = [int(x) for x in
                                        re.findall(r"[-+]?\d+", text)]
            continue
        found = re.match(r"^(\d+)\.\s*(.+)$", text)
        if found:
            entries.append({"label": found.group(2).strip(), "coord": None})

    folders = {}
    runes = {}
    for entry, button in zip(entries, entry_buttons):
        if entry["coord"] is not None or (button + AR_GATE_OFFSET) in buttons:
            runes[button] = {"name": entry["label"], "coord": entry["coord"]}
        else:
            folders[button] = entry["label"]

    if len(entries) != len(entry_buttons):
        log("  AR page: %d entries but %d entry buttons - the pairing may be "
            "off." % (len(entries), len(entry_buttons)), HUE_WARN)
    return folders, runes


def ar_page_step(button):
    if button not in ar_buttons():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
    Misc.Pause(250)
    return True


def ar_goto_page(target):
    current, total = ar_page_info()
    target = max(1, min(int(target), total))
    for _ in range(AR_MAX_PAGES * 2):
        if current == target:
            return True
        step = AR_NEXT_PAGE_BUTTON if current < target else AR_PREV_PAGE_BUTTON
        if not ar_page_step(step):
            return False
        current, _total = ar_page_info()
    return current == target


def ar_root():
    if AR_ROOT_BUTTON in ar_buttons():
        Gumps.SendAction(AR_GUMPID, AR_ROOT_BUTTON)
        Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
        Misc.Pause(250)
    return True


def ar_enter_folder(name):
    """Step into a folder by name, looking on every page."""
    if not openAR():
        return False
    if not ar_goto_page(1):
        log("Could not rewind the runebook to page 1.", HUE_WARN)

    wanted = (name or "").strip().lower()
    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        folders, _runes = parse_ar_page()
        for button in sorted(folders):
            label = (folders[button] or "").strip().lower()
            if label == wanted or wanted in label:
                Gumps.SendAction(AR_GUMPID, button)
                Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
                Misc.Pause(250)
                return True
        if current >= total or not ar_page_step(AR_NEXT_PAGE_BUTTON):
            break
    log("Folder %r is not in the runebook." % name, HUE_BAD)
    return False


def go_to_reagent_folder():
    ar_root()
    for folder in REAGENT_SHOPS_FOLDER:
        if not folder:
            continue
        if not ar_enter_folder(folder):
            return False
    return True


def wanted_rune(name):
    """Is this rune one to visit? RUNE_MUST_MATCH, or everything if empty.

    TRUNCATION-TOLERANT. The gump cuts names off wherever the column runs
    out, and it cut "Serpents Hold Mage Shop" to "Serpents Hold Mage Sho...".
    A straight substring test drops that rune and says nothing, which is
    exactly the kind of silent miss that looks like the shop having no vendor.

    So the phrase matches if it is in the name OR the name ends with the
    start of it - the only thing truncation can leave. The tail has to be at
    least RUNE_MATCH_MIN_PREFIX long, so "M" does not qualify everything.
    """
    if not RUNE_MUST_MATCH:
        return True

    low = " ".join((name or "").split()).lower()
    visible = low.rstrip(" .")          # drop the ellipsis the gump adds
    for want in RUNE_MUST_MATCH:
        target = " ".join((want or "").split()).lower()
        if not target:
            continue
        if target in low:
            return True
        longest = min(len(target) - 1, len(visible))
        for cut in range(longest, RUNE_MATCH_MIN_PREFIX - 1, -1):
            if visible.endswith(target[:cut]):
                return True
    return False


def collect_runes():
    """[(page, button, name, coord)] for every rune worth visiting.

    Collected in one sweep BEFORE any recalling, because recalling closes the
    book and re-opening it lands back at the root.

    Runes that do not match RUNE_MUST_MATCH are left out here rather than
    skipped later, so the count printed at startup is the real round.
    """
    out = []
    skipped = []
    if not ar_goto_page(1):
        log("Could not rewind to page 1 of the folder.", HUE_WARN)

    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        _folders, runes = parse_ar_page()
        for button in sorted(runes):
            name = runes[button]["name"]
            if not wanted_rune(name):
                skipped.append(name)
                continue
            out.append((current, button, name, runes[button]["coord"]))
        if current >= total:
            break
        if not ar_page_step(AR_NEXT_PAGE_BUTTON):
            break
        moved, _t = ar_page_info()
        if moved <= current:
            log("The runebook did not advance past page %d." % current,
                HUE_WARN)
            break

    if skipped:
        log("  skipping %d rune(s) that are not %s: %s"
            % (len(skipped), "/".join(RUNE_MUST_MATCH),
               ", ".join(skipped[:6]) + (" ..." if len(skipped) > 6 else "")))
    return out[:MAX_RUNES_PER_LAP]


def arrived_at(coord):
    """Did the recall land where the rune says? None coord = cannot tell."""
    if not coord or len(coord) < 2:
        return None
    try:
        gap = max(abs(Player.Position.X - int(coord[0])),
                  abs(Player.Position.Y - int(coord[1])))
    except Exception:
        return None
    return gap <= ARRIVE_TOLERANCE


def recall_to(page, button, name, coord):
    """Recall to one rune. True once standing there (or unverifiable)."""
    if not openAR():
        return False
    if not ar_goto_page(page):
        log("Could not get back to page %d for %s." % (page, name), HUE_WARN)
        return False

    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(RECALL_SETTLE_MS)

    where = arrived_at(coord)
    if where is False:
        log("Recall to %s did not land - still at %d,%d, wanted %d,%d."
            % (name, Player.Position.X, Player.Position.Y, coord[0], coord[1]),
            HUE_WARN)
        return False
    if where is None:
        log("  %s has no coordinates in the book - cannot confirm the recall."
            % name, HUE_WARN)
    return True


# =============================================================================
# THE VENDORS
# =============================================================================

def mobile_title(mob):
    """A mobile's tooltip as one lowered string.

    THE TITLE IS NOT THE NAME. "the mage" is a title and lives in the tooltip;
    Mobiles.Filter().Name is an exact match against the NAME and never sees
    it. That is why the old script never found a vendor.
    """
    try:
        Mobiles.WaitForProps(mob, 1000)
        lines = list(Mobiles.GetPropStringList(mob) or [])
    except Exception:
        return ""
    return " ".join(str(l or "") for l in lines).lower()


def is_vendor(mob):
    """Does this mobile sell reagents? Name first, tooltip second."""
    try:
        name = (mob.Name or "").strip().lower()
    except Exception:
        name = ""
    for banned in VENDOR_NEVER:
        if banned.strip().lower() in name:
            return False

    blob = name
    if not any(t.strip().lower() in blob for t in VENDOR_TITLES):
        blob = (name + " " + mobile_title(mob)).strip()

    for banned in VENDOR_NEVER:
        if banned.strip().lower() in blob:
            return False
    for title in VENDOR_TITLES:
        if title.strip().lower() in blob:
            return True
    return False


def vendors_in_range():
    """Every reagent vendor standing here, nearest first."""
    try:
        f = Mobiles.Filter()
        f.Enabled = True
        f.RangeMax = VENDOR_RANGE       # ALWAYS set - see CLAUDE.md
        found = list(Mobiles.ApplyFilter(f) or [])
    except Exception as err:
        log("could not look for vendors: %r" % err, HUE_WARN)
        return []

    out = [m for m in found if is_vendor(m)]
    try:
        out.sort(key=lambda m: Player.DistanceTo(m))
    except Exception:
        pass
    return out


def describe(mob):
    try:
        return (mob.Name or "a vendor").strip()
    except Exception:
        return "a vendor"


def buy_from(mob):
    """Open a vendor's shop and let the Buy Agent fill it. Gold spent.

    VERIFIED BY GOLD. The shop window opening is not evidence that anything
    was bought - the agent may have nothing on its list that this vendor
    stocks, or may be switched off. Gold going down is the purchase.
    """
    who = describe(mob)
    try:
        before = int(Player.Gold)
    except Exception:
        before = -1

    if not context_select(int(mob.Serial), BUY_ENTRIES, who):
        return 0
    Misc.Pause(BUY_SETTLE_MS)

    try:
        after = int(Player.Gold)
    except Exception:
        after = -1
    if before < 0 or after < 0:
        log("  bought from %s (gold could not be read)." % who)
        return 0

    spent = before - after
    if spent > 0:
        log("  bought %d gold's worth from %s." % (spent, who), HUE_GOOD)
    else:
        log("  %s sold nothing - the Buy Agent list %r may not match what "
            "they stock." % (who, BUY_LIST_NAME), HUE_WARN)
    return max(0, spent)


# =============================================================================
# STORING
# =============================================================================

def pack_count():
    """How many items are loose in the backpack. -1 when it cannot be read."""
    pack = Player.Backpack
    if pack is None:
        return -1
    try:
        Items.UseItem(pack)
        Items.WaitForContents(pack, 3000)
    except Exception:
        pass
    Misc.Pause(SETTLE_MS)
    try:
        return len(list(getattr(pack, "Contains", None) or []))
    except Exception:
        return -1


def store_haul():
    """Push the pack into the storage key. True if it took anything.

    One press. A Master Key takes the lot in one go, and the key is answered
    by LABEL - the old script sent context entry 2, which is whatever the
    shard happens to have put in that slot.
    """
    if not STORAGE_KEY_SERIAL:
        return False
    key = Items.FindBySerial(STORAGE_KEY_SERIAL)
    if key is None:
        log("Storage key 0x%X is not on you - nothing stored."
            % STORAGE_KEY_SERIAL, HUE_WARN)
        return False

    before = pack_count()
    if not context_select(STORAGE_KEY_SERIAL, FILL_ENTRIES, "the storage key"):
        return False
    after = pack_count()

    if before < 0 or after < 0:
        return True             # it was pressed; the pack could not be read
    if after < before:
        log("  stored %d item(s)." % (before - after), HUE_GOOD)
        return True
    log("  the key took nothing.", HUE_WARN)
    return False


def grab_and_store():
    """Pick up anything that landed on the floor, then store."""
    if GRAB_PHRASE:
        chat_say(GRAB_PHRASE)
        Misc.Pause(CONTEXT_PAUSE_MS)
    store_haul()


# =============================================================================
# THE RUN
# =============================================================================

def preflight():
    """Set the Buy Agent up and say what will happen. False to stop."""
    log("Reagent Buyer v%s" % SCRIPT_VERSION, HUE_GOOD)

    if Player.Backpack is None:
        log("No backpack.", HUE_BAD)
        return False

    # THE BUY AGENT. Naming a list is not the same as using one: the old
    # script set BUY_LIST_NAME and never told Razor about it, so every shop
    # window opened and bought nothing.
    try:
        BuyAgent.ChangeList(BUY_LIST_NAME)
        BuyAgent.Enable()
        on = bool(BuyAgent.Status())
    except Exception as err:
        log("Could not set up the Buy Agent: %r" % err, HUE_BAD)
        return False
    if not on:
        log("The Buy Agent will not turn on. Nothing would be bought, so this "
            "is not starting.", HUE_BAD)
        return False
    log("  Buy Agent on, using the list %r." % BUY_LIST_NAME, HUE_GOOD)
    log("  (if nothing is ever bought, check that list exists in Razor and "
        "holds the reagents you want.)")

    if STORAGE_KEY_SERIAL:
        key = Items.FindBySerial(STORAGE_KEY_SERIAL)
        log("  storage key 0x%X%s" % (STORAGE_KEY_SERIAL,
                                      "" if key is not None
                                      else "  WARNING: not on you right now"),
            HUE_INFO if key is not None else HUE_WARN)
    else:
        log("  no storage key set - reagents stay in your pack.", HUE_WARN)

    if not go_to_reagent_folder():
        return False
    runes = collect_runes()
    if not runes:
        log("No runes in %s. Check the folder name."
            % " / ".join(REAGENT_SHOPS_FOLDER), HUE_BAD)
        return False
    log("  %d rune(s) in %s: %s"
        % (len(runes), " / ".join(REAGENT_SHOPS_FOLDER),
           ", ".join(r[2] for r in runes[:6])
           + (" ..." if len(runes) > 6 else "")), HUE_GOOD)
    return True


def one_lap(lap):
    """Visit every rune once. How much gold was spent."""
    log("--- lap %d ---" % lap, HUE_GOOD)
    if not go_to_reagent_folder():
        return 0
    runes = collect_runes()
    if not runes:
        log("No runes to visit this lap.", HUE_WARN)
        return 0

    spent = 0
    for page, button, name, coord in runes:
        if Player.IsGhost:
            return spent
        log("recalling to %s" % name)
        if not recall_to(page, button, name, coord):
            continue

        sellers = vendors_in_range()
        if not sellers:
            log("  no mage or alchemist within %d tiles of %s."
                % (VENDOR_RANGE, name), HUE_WARN)
            continue

        for mob in sellers:
            spent += buy_from(mob)
            grab_and_store()

        # One more sweep: the last purchase's goods may still have been
        # arriving when the key was pressed.
        grab_and_store()
    return spent


def main():
    if not preflight():
        return

    lap = 0
    total = 0
    while not Player.IsGhost:
        lap += 1
        if MAX_LAPS and lap > MAX_LAPS:
            log("%d lap(s) done, which is MAX_LAPS." % (lap - 1), HUE_GOOD)
            break
        total += one_lap(lap)
        if Player.IsGhost:
            break
        log("lap %d done, %d gold spent in total. Waiting %d second(s)."
            % (lap, total, CYCLE_PAUSE_MS / 1000), HUE_GOOD)
        sleep_ms(CYCLE_PAUSE_MS)

    if Player.IsGhost:
        log("You are dead - stopping.", HUE_BAD)
    log("%d gold spent over %d lap(s)." % (total, lap),
        HUE_GOOD if total else HUE_WARN)


main()
