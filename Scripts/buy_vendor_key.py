"""
Player vendor - find a key in the pack and buy it.
==================================================

Opens a player vendor's shop pack, searches it (including bags inside bags) for
an item whose name or tooltip matches WANTED_PHRASES, and buys the first match
through the item's context menu.

Written for "Keymaster" / Shop Name "Keys Collection", serial 0x0000B090,
inspected 2026-07-30. Player vendors on this shard open a BACKPACK of items
rather than the usual buy-list gump: you click an item and press Buy on its
context menu.

THIS SPENDS GOLD. The safety rails, all deliberate:

  * Buy is taken ONLY on an EXACT context-menu label match against BUY_LABELS.
    There is no substring fallback for the purchase - a vendor menu carries
    Sell, Price, Remove and Open Bankbox right beside Buy, and a loose match
    that lands on one of those cannot be undone. If nothing matches exactly the
    script prints every label the menu offered and stops, so the real wording
    can be added to BUY_LABELS.
  * MAX_BUYS caps the purchases per run. It is 1.
  * MAX_PRICE refuses anything dearer, when the price can be read.
  * The item must match WANTED_PHRASES in its NAME or its TOOLTIP. Nothing is
    bought on position in the pack.
  * The purchase is VERIFIED, not assumed: the backpack is diffed and the
    journal read, so "bought" means an item actually arrived.

Set DRY_RUN = True to do everything except press Buy.

WHAT IT CLICKS
--------------
Double-clicks the vendor (opens the shop pack), double-clicks bags inside it to
read them, and sends ONE context reply - the Buy entry - per purchase. It never
replies to the vendor's own context menu.

NOTE ON THE JOURNAL
-------------------
It calls Journal.Clear() before buying so the result can be read back. That
wipes your journal.
"""

import re
import time


# Printed as the first log line. If the journal does not show this, Razor is
# running a cached copy - Reload in the Scripting tab.
SCRIPT_VERSION = "2026-07-31.1"


# =============================================================================
# CONFIG - THE VENDOR
#
# Filled in from the Mobile Inspector, 2026-07-30. Serial is tried first; the
# name and the shop name are the fallbacks for when the shard respawns it.
# =============================================================================

VENDOR_SERIAL = 0x0000B090
VENDOR_NAME = "Keymaster"

# Matched against the vendor's TOOLTIP, which is where "Shop Name: ..." lives.
# An NPC's title is in the tooltip, not the name - and names get changed by the
# shard far more often than titles do.
VENDOR_SHOP_NAME = "Keys Collection"

VENDOR_RANGE = 12


# =============================================================================
# CONFIG - WHAT TO BUY
# =============================================================================

# Matched against the item's Name AND its tooltip, case-insensitively. The
# separators are flexible, so "wood storage key" also matches "Wood-Storage
# Key" and "WoodStorageKey".
WANTED_PHRASES = [
    "wood storage key",
]

# Context-menu entries that mean "buy this". EXACT match only, case-insensitive
# - see the docstring. Add the real wording here if the menu says something
# else; the script prints what it offered.
BUY_LABELS = ["Buy", "Buy Item", "Purchase"]

# Never selected, ever. Belt and braces: nothing here can be reached anyway,
# because the buy step does not do substring matching.
CONTEXT_NEVER = [
    "sell", "bribe", "open bankbox", "train ", "remove", "delete", "price",
    "empty", "claim", "dismiss", "fire", "collect gold",
]

# Purchases per run. Deliberately 1.
MAX_BUYS = 1

# Refuse an item dearer than this. 0 = no ceiling.
#
# When this is set and the price CANNOT be read from the tooltip, the item is
# refused rather than bought blind.
MAX_PRICE = 0

# True does everything except press Buy - the search, the match, the price, the
# menu labels are all still reported.
DRY_RUN = False

# How deep to look inside bags within the shop pack. 1 is the pack itself.
SEARCH_DEPTH = 4


# =============================================================================
# CONFIG - TIMINGS
# =============================================================================

CONTENTS_TIMEOUT_MS = 4000
PROPS_TIMEOUT_MS = 1500
CONTEXT_TIMEOUT_MS = 2000
SETTLE_MS = 700
OPEN_TRIES = 3

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[KEY] " + str(text), hue, False)


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Compatibility shims
# ---------------------------------------------------------------------------

def wait_context(entity, delay=CONTEXT_TIMEOUT_MS, show=False):
    try:
        return Misc.WaitForContext(entity, delay, show)
    except TypeError:
        return Misc.WaitForContext(entity, delay)


def mobile_props(mob):
    try:
        Mobiles.WaitForProps(mob, PROPS_TIMEOUT_MS)
        return list(Mobiles.GetPropStringList(mob) or [])
    except Exception:
        return []


def item_props(item):
    try:
        Items.WaitForProps(item, PROPS_TIMEOUT_MS)
        return list(Items.GetPropStringList(item) or [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def spaced(text):
    """Split the lower/digit -> upper seam in a concatenated tooltip.

    Tooltip properties arrive with no separator between one property's value
    and the next one's label - "Level: 2Creature Type: Kirin". Without this,
    lowercasing gives "kirinfilled" and any regex ending in \\b fails.
    """
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text or "")


def phrase_regex(phrase):
    """A regex for `phrase` whose separators are flexible.

    "wood storage key" matches "Wood-Storage Key" and "WoodStorageKey" too.
    The \\b anchors stay: without them "key" matches inside "monkey".
    """
    words = [re.escape(w) for w in re.split(r"\s+", (phrase or "").strip()) if w]
    if not words:
        return None
    return re.compile(r"\b" + r"[^a-z0-9]*".join(words) + r"\b", re.I)


WANTED_RES = [r for r in (phrase_regex(p) for p in WANTED_PHRASES) if r]

PRICE_RE = re.compile(r"price[:\s]*([\d,]+)", re.I)


def strip_amount(name):
    """"12 keys" -> "keys". A stack's name carries its count."""
    return re.sub(r"^\s*[\d,]+\s+", "", name or "").strip()


def item_text(item):
    """Everything readable about an item: its name plus its tooltip."""
    parts = []
    try:
        parts.append(str(getattr(item, "Name", "") or ""))
    except Exception:
        pass
    for line in item_props(item):
        parts.append(str(line or ""))
    return spaced(" | ".join(p for p in parts if p))


def price_of(text):
    """The asking price from a tooltip, or None if it does not say."""
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def matches_wanted(text):
    for regex in WANTED_RES:
        if regex.search(text or ""):
            return True
    return False


def safe_name(entity):
    try:
        return str(getattr(entity, "Name", "") or "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# The vendor
# ---------------------------------------------------------------------------

def vendor_candidates():
    """Every mobile in range, nearest first."""
    try:
        filt = Mobiles.Filter()
        filt.Enabled = True
        filt.RangeMax = VENDOR_RANGE      # NEVER leave this unset
        found = list(Mobiles.ApplyFilter(filt) or [])
    except Exception as err:
        log("Mobiles.ApplyFilter failed: %s" % err, HUE_BAD)
        return []
    found.sort(key=lambda m: Player.DistanceTo(m))
    return found


def find_vendor():
    """The vendor, by serial, then name, then shop name. None if not found.

    A lookup that fails dumps every candidate WITH its tooltip, because "not
    found" on its own costs a whole extra round trip to diagnose.
    """
    if VENDOR_SERIAL:
        mob = Mobiles.FindBySerial(VENDOR_SERIAL)
        if mob is not None:
            log("vendor found by serial 0x%X" % VENDOR_SERIAL, HUE_GOOD)
            return mob
        log("serial 0x%X did not resolve - falling back to the name."
            % VENDOR_SERIAL, HUE_WARN)

    candidates = vendor_candidates()

    # Name first: it is cheap. Matched here rather than through Filter().Name,
    # which is an EXACT match and fails silently the moment the shard renames.
    wanted = (VENDOR_NAME or "").strip().lower()
    if wanted:
        for mob in candidates:
            if safe_name(mob).strip().lower() == wanted:
                log("vendor found by name %r" % VENDOR_NAME, HUE_GOOD)
                return mob

    # Then the shop name, which lives in the tooltip.
    shop = (VENDOR_SHOP_NAME or "").strip().lower()
    if shop:
        for mob in candidates:
            blob = spaced(" | ".join(mobile_props(mob))).lower()
            if shop in blob:
                log("vendor found by shop name %r (it is called %r)"
                    % (VENDOR_SHOP_NAME, safe_name(mob)), HUE_GOOD)
                return mob

    log("No vendor matched serial 0x%X, name %r or shop name %r within %d "
        "tiles." % (VENDOR_SERIAL, VENDOR_NAME, VENDOR_SHOP_NAME,
                    VENDOR_RANGE), HUE_BAD)
    log("%d mobile(s) in range:" % len(candidates), HUE_WARN)
    for mob in candidates[:12]:
        props = " / ".join(mobile_props(mob)[:3])
        log("  0x%08X %-22s %s" % (int(mob.Serial), safe_name(mob)[:22],
                                   props[:60]), HUE_WARN)
    return None


def open_pack(vendor):
    """Double-click the vendor and return its shop pack as an Item.

    Contains is a snapshot taken when the container is opened, so this both
    opens it and re-reads it, retrying while it comes back empty.
    """
    for attempt in range(1, OPEN_TRIES + 1):
        try:
            Mobiles.UseMobile(vendor)
        except Exception as err:
            log("could not double-click the vendor: %s" % err, HUE_BAD)
            return None
        Misc.Pause(SETTLE_MS)

        pack = getattr(vendor, "Backpack", None)
        if pack is None:
            fresh = Mobiles.FindBySerial(int(vendor.Serial))
            pack = getattr(fresh, "Backpack", None) if fresh else None
        if pack is None:
            log("attempt %d: the vendor has no readable Backpack yet."
                % attempt, HUE_WARN)
            continue

        try:
            Items.WaitForContents(pack, CONTENTS_TIMEOUT_MS)
        except Exception:
            pass
        Misc.Pause(SETTLE_MS)

        fresh_pack = Items.FindBySerial(int(pack.Serial)) or pack
        if list(getattr(fresh_pack, "Contains", None) or []):
            return fresh_pack
        log("attempt %d: the shop pack read back empty." % attempt, HUE_WARN)

    log("The vendor's pack would not open, or it is genuinely empty.", HUE_BAD)
    return None


def open_bag(item):
    """Open a bag inside the pack so its Contains is populated."""
    serial = int(item.Serial)
    for _ in range(OPEN_TRIES):
        fresh = Items.FindBySerial(serial)
        if fresh is None:
            return None
        try:
            Items.UseItem(fresh)
            Items.WaitForContents(fresh, CONTENTS_TIMEOUT_MS)
        except Exception:
            pass
        Misc.Pause(SETTLE_MS)
        fresh = Items.FindBySerial(serial)
        if list(getattr(fresh, "Contains", None) or []):
            return fresh
    return Items.FindBySerial(serial)


def walk_pack(container, depth, path, out):
    """Collect every item under `container`, remembering where it was."""
    contents = list(getattr(container, "Contains", None) or [])
    for item in contents:
        out.append({"item": item, "depth": depth, "path": path})

        is_container = bool(getattr(item, "IsContainer", False))
        has_contents = bool(list(getattr(item, "Contains", None) or []))
        if (is_container or has_contents) and depth < SEARCH_DEPTH:
            name = strip_amount(safe_name(item)) or "bag"
            opened = open_bag(item)
            if opened is not None:
                walk_pack(opened, depth + 1, "%s > %s" % (path, name[:18]), out)


# ---------------------------------------------------------------------------
# Buying
# ---------------------------------------------------------------------------

def context_labels(entity):
    """Every label on an entity's context menu, in order."""
    entries = wait_context(entity)
    if not entries:
        return []
    labels = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        labels.append(str(text if text is not None else entry))
    return labels


def context_is_blocked(label):
    low = (label or "").lower()
    for banned in CONTEXT_NEVER:
        if banned.strip().lower() in low:
            return True
    return False


def find_buy_label(labels):
    """The EXACT Buy entry, or None.

    Exact only. A vendor menu carries Sell, Price and Remove beside Buy, and a
    substring match that lands on one of those cannot be undone.
    """
    for want in BUY_LABELS:
        target = want.strip().lower()
        for label in labels:
            if (label or "").strip().lower() == target:
                if context_is_blocked(label):
                    log("%r is on CONTEXT_NEVER - refusing it." % label, HUE_BAD)
                    continue
                return label
    return None


def pack_serials():
    backpack = Player.Backpack
    if backpack is None:
        return set()
    return set(int(i.Serial) for i in (getattr(backpack, "Contains", None) or []))


def buy(item, label):
    """Send the Buy reply and prove something arrived. True if it did."""
    before = pack_serials()
    Journal.Clear()

    Misc.Pause(150)
    Misc.ContextReply(item, label)     # the real label, never our search string
    Misc.Pause(SETTLE_MS)

    backpack = Player.Backpack
    if backpack is not None:
        try:
            Items.WaitForContents(backpack, CONTENTS_TIMEOUT_MS)
        except Exception:
            pass
    Misc.Pause(SETTLE_MS)

    for text in ("you cannot afford", "not enough gold", "you must have",
                 "cannot be bought", "no longer for sale", "backpack is full"):
        if Journal.Search(text):
            log("the vendor refused: %r" % text, HUE_BAD)
            return False

    after = pack_serials()
    new = [s for s in after if s not in before]
    if new:
        for serial in new:
            got = Items.FindBySerial(serial)
            log("received 0x%08X %s"
                % (serial, strip_amount(safe_name(got)) if got else "?"),
                HUE_GOOD)
        return True

    log("Buy was sent but nothing new is in your backpack. It may have needed "
        "a confirmation, or the pack diff missed it - check by hand before "
        "running this again.", HUE_WARN)
    try:
        if Gumps.HasGump():
            log("a gump is open (0x%X) - that is probably the confirmation."
                % Gumps.CurrentGump(), HUE_WARN)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------

def main():
    started = time.time()
    rule("vendor key search - v%s" % SCRIPT_VERSION)
    log("looking for: %s" % ", ".join(repr(p) for p in WANTED_PHRASES))
    if DRY_RUN:
        log("DRY_RUN is on - nothing will be bought.", HUE_WARN)

    if not WANTED_RES:
        log("WANTED_PHRASES is empty - nothing to look for.", HUE_BAD)
        return

    vendor = find_vendor()
    if vendor is None:
        return
    log("vendor: %r 0x%08X, %d tiles away"
        % (safe_name(vendor), int(vendor.Serial), Player.DistanceTo(vendor)))

    pack = open_pack(vendor)
    if pack is None:
        return

    rule("searching the shop pack")
    found = []
    walk_pack(pack, 1, "pack", found)
    log("%d item(s) in the pack, to a depth of %d" % (len(found), SEARCH_DEPTH))

    matched = []
    for record in found:
        text = item_text(record["item"])
        if matches_wanted(text):
            record["text"] = text
            record["price"] = price_of(text)
            matched.append(record)

    if not matched:
        log("No item matching %s is in this vendor's pack."
            % ", ".join(repr(p) for p in WANTED_PHRASES), HUE_WARN)
        log("It searched %d item(s). If you can see the key but this cannot, "
            "the name differs - here is what is in there:" % len(found),
            HUE_WARN)
        for record in found[:20]:
            log("  depth %d  %s" % (record["depth"],
                                    strip_amount(safe_name(record["item"]))[:48]))
        if len(found) > 20:
            log("  ... and %d more." % (len(found) - 20))
        return

    rule("%d match(es)" % len(matched))
    for record in matched:
        log("  0x%08X  %-30s  %s  at %s"
            % (int(record["item"].Serial),
               strip_amount(safe_name(record["item"]))[:30],
               record["path"],
               "%d gold" % record["price"] if record["price"] is not None
               else "price not readable"), HUE_GOOD)

    bought = 0
    for record in matched:
        if bought >= MAX_BUYS:
            log("stopping at MAX_BUYS (%d)." % MAX_BUYS)
            break

        item = record["item"]
        name = strip_amount(safe_name(item)) or "the item"
        price = record["price"]

        if MAX_PRICE > 0:
            if price is None:
                log("refusing %s - MAX_PRICE is set but its price cannot be "
                    "read from the tooltip." % name, HUE_BAD)
                continue
            if price > MAX_PRICE:
                log("refusing %s - %d gold is over MAX_PRICE (%d)."
                    % (name, price, MAX_PRICE), HUE_WARN)
                continue

        labels = context_labels(item)
        if not labels:
            log("%s gave no context menu - cannot buy it." % name, HUE_BAD)
            continue
        log("menu: %s" % " | ".join(labels))

        label = find_buy_label(labels)
        if label is None:
            log("None of %s appears on that menu, so nothing was pressed. Add "
                "the real wording above to BUY_LABELS."
                % ", ".join(repr(b) for b in BUY_LABELS), HUE_BAD)
            continue

        if DRY_RUN:
            log("DRY_RUN: would press %r on %s%s"
                % (label, name,
                   " (%d gold)" % price if price is not None else ""), HUE_WARN)
            bought += 1
            continue

        log("buying %s%s - pressing %r"
            % (name, " for %d gold" % price if price is not None else "",
               label), HUE_GOOD)
        if buy(item, label):
            log("bought %s." % name, HUE_GOOD)
            bought += 1
        else:
            log("%s was not bought." % name, HUE_BAD)

    rule("%d bought, %.1fs" % (bought, time.time() - started))


main()
