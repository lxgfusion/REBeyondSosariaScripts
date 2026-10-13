"""
MIB Opener - open every Message in a Bottle, then put the maps away.
====================================================================

For Razor Enhanced (IronPython 3.4). Target: the UOAlive / Beyond Sosaria
freeshard.

WHAT IT DOES
------------
    open every Message in a Bottle in the BACKPACK, one at a time
    stop the moment there are none left
    hand what came out to your storage key(s)

WHAT IT REPLACES
----------------
    Items.UseItemByID(0x099F)
    Misc.Pause(400)

in a loop that never ended. The other thing wrong with it: nothing checked
that a bottle actually opened, so a refusal looked exactly like success.

THE BACKPACK ONLY, BY DEFAULT
-----------------------------
Bottles sitting loose in the pack are opened; bags inside it are left shut.
SEARCH_BAGS turns the deeper search on, and it is OFF because of what it
costs: a container's contents are only current just after it is opened, so
searching bags means re-opening every one of them on every count - and the
count runs twice per bottle. That is a bag window flapping open over and over
for the whole run, which is exactly how it behaved when it shipped on.

WHAT COMES OUT
--------------
Confirmed in game 2026-10-12: the bottle is CONSUMED and leaves behind an SOS
- "a waterstained SOS" (ItemID 0x14EE, 1 stone) or "an Ancient SOS", whose
graphic has not been inspected yet and so is matched by name.

That is why counting works: the bottle really does leave the pack. If a shard
ever left the bottle in place, the count would not move and the run would stop
after RETRY_PASSES saying so, rather than spinning.

HOW IT KNOWS WHEN TO STOP
-------------------------
It counts. Every pass re-reads the pack, counts the bottles, opens ONE, and
checks the count went down. No bottles left ends it; a count that does not
move ends it too, after RETRY_PASSES tries - because "use it again" has
already been proven not to work at that point, and that is exactly the loop
this is replacing.

CONTAINERS ARE A SNAPSHOT
-------------------------
`Item.Contains` is filled in when the container is opened and does not update
on its own, so every bag is re-opened before it is read. Without that a bottle
that arrived after the bag was last opened is invisible, and the script would
report "none left" with a pack full of them. See CLAUDE.md.

WHAT IT NEVER DOES
------------------
It does not press a storage key's menu on a guess. An exact match on
FILL_ENTRIES is taken first; a loose match has to get past CONTEXT_NEVER,
which refuses the entries sitting on the same menu that empty or destroy what
the key is holding.
"""

import time


# Printed as the first line at startup. Razor CACHES the loaded script even
# after the file on disk changes - if this line is not what you expect, hit
# Reload in the Scripting tab.
SCRIPT_VERSION = "2026-10-12.3"


# =============================================================================
# CONFIG - THE THINGS YOU SET
# =============================================================================

# WHERE WHAT COMES OUT GOES. Press order, top to bottom.
#
# Each entry is tried by SERIAL first, then by graphic and hue, so a key that
# gets replaced is still found. Set "enabled": False to skip one without
# deleting it.
#
#   serial  the exact item. 0 means "find it by graphic".
#   id/hue  the fallback. hue -1 means any hue.
#
# IF YOUR KEY LIVES IN A BAG, SET ITS SERIAL. The graphic fallback searches
# the same place everything else does, which with SEARCH_BAGS off is the
# backpack's top level - a key in a pouch is found by serial or not at all.
#
# A MASTER KEY takes everything in one press, so if that is all you carry,
# leave the treasure key disabled - a second press on a key that already took
# the lot is a wasted context menu.
DEPOSIT_KEYS = [
    {
        "enabled": True,
        "label": "Master Key",
        "serial": 0,            # e.g. 0x4335A205
        "id": 0x176B,
        "hue": 0x0481,
    },
    {
        "enabled": False,
        "label": "Treasure Hunter's Storage",
        "serial": 0,
        "id": 0xA321,
        "hue": -1,
    },
]

# Deposit after this many bottles as well as at the end, so a long run does
# not fill the pack. 0 means "only at the end".
DEPOSIT_EVERY = 25

# The bottle. 0x099F is the Message in a Bottle on this shard - the graphic the
# original one-liner used. Add more ids here if your shard has others; the hue
# is not pinned because it has never needed to be.
MIB_IDS = [0x099F]
MIB_HUE = -1                    # -1 = any

# WHAT COMES OUT, so the run can say how many it got and whether the key
# actually took them.
#
# Inspected 2026-10-12: "a waterstained SOS", ItemID 0x14EE, hue 0x0000, 1
# stone, in the backpack. There is also "an Ancient SOS" whose graphic has not
# been inspected - hence the NAME list, which catches it whatever it is drawn
# as. Either test is enough; neither is required for the opening to work.
SOS_IDS = [0x14EE]
SOS_NAMES = ["sos"]

# LOOK INSIDE BAGS? Off.
#
# A container only reports what is in it just after it has been opened, so
# searching bags means RE-OPENING every bag on every count - and the count
# runs twice for every bottle. On a pack with a few bags that is a window
# flapping open continuously for the whole run, which is what it did when
# this shipped on.
#
# Leave it False and bottles have to be loose in the backpack. Turn it on
# only if you keep them in a bag and would rather have the churn.
SEARCH_BAGS = False

# How deep to look WHEN SEARCH_BAGS IS ON. The backpack is depth 0, a bag in
# it is 1, a bag in that is 2.
MAX_BAG_DEPTH = 3

# Ceiling on bottles opened in one run, so nothing can spin forever even if
# every guard below is wrong at once.
MAX_OPENS = 200

# How many times to re-try when the count does not go down. One retry covers a
# slow server; more than that and something is actually wrong.
RETRY_PASSES = 2


# =============================================================================
# CONFIG - MENUS
# =============================================================================

# Menu entries that empty the pack into a key, tried in this order. The menu
# is printed the first time each key is used, so the real wording ends up in
# the journal rather than being guessed at.
FILL_ENTRIES = ["Refill from stock", "Fill from backpack"]

# Never answered, however well they match. These sit on the same menus and do
# not put anything away - several of them take things OUT or destroy them.
CONTEXT_NEVER = [
    "empty", "destroy", "delete", "discard", "release", "purge", "drop",
    "rename", "dye", "sell", "buy", "bribe", "open bankbox", "train ",
]


# =============================================================================
# CONFIG - TIMING
# =============================================================================

USE_PAUSE_MS = 400          # after opening a bottle - the original's pause
SETTLE_MS = 300             # after the pack changes, before reading it again
CONTENTS_WAIT_MS = 3000     # for a container to report what is in it
CONTEXT_TIMEOUT_MS = 10000  # for a right-click menu
CONTEXT_PAUSE_MS = 600      # after answering one

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

_menu_shown = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[MIB] " + text, hue, False)


def open_container(item):
    """Re-open a container so its Contains list is current.

    Contains is a SNAPSHOT taken when the container was opened. A bottle that
    arrived since then is invisible until it is re-opened, and asking a
    different way does not help: Items.FindAllByID with a container serial
    walks that same list. See CLAUDE.md.
    """
    if item is None:
        return
    try:
        Items.UseItem(item)
        Items.WaitForContents(item, CONTENTS_WAIT_MS)
    except Exception:
        pass
    Misc.Pause(SETTLE_MS)


def contents_of(item):
    try:
        return list(getattr(item, "Contains", None) or [])
    except Exception:
        return []


def is_container(item):
    try:
        return bool(item.IsContainer)
    except Exception:
        return False


def walk_pack():
    """Everything this script can see. The BACKPACK'S TOP LEVEL by default.

    With SEARCH_BAGS off nothing but the pack is ever opened - no bag window
    opens at all, which is the whole point of the flag.

    With it on, breadth first with a visited set: a bag that somehow contains
    itself would otherwise be walked until the recursion limit, and "it hung"
    is a worse failure than "it missed one".
    """
    pack = Player.Backpack
    if pack is None:
        return []

    open_container(pack)
    if not SEARCH_BAGS:
        return contents_of(pack)

    found = []
    seen = set([int(pack.Serial)])
    level = [(pack, 0)]

    while level:
        container, depth = level.pop(0)
        for item in contents_of(container):
            try:
                serial = int(item.Serial)
            except Exception:
                continue
            found.append(item)
            if not is_container(item) or depth >= MAX_BAG_DEPTH:
                continue
            if serial in seen:
                continue
            seen.add(serial)
            open_container(item)
            level.append((item, depth + 1))
    return found


def is_mib(item):
    try:
        if int(item.ItemID) not in MIB_IDS:
            return False
        if MIB_HUE >= 0 and int(item.Hue) != MIB_HUE:
            return False
    except Exception:
        return False
    return True


def amount_of(item):
    try:
        return int(item.Amount or 1)
    except Exception:
        return 1


def is_sos(item):
    """Something a bottle turned into. Graphic OR name.

    The name is what catches the Ancient SOS, whose graphic nobody has
    inspected. Item.Name can be empty until the properties load, which only
    costs this a nicer count - nothing hangs on it.
    """
    try:
        if int(item.ItemID) in SOS_IDS:
            return True
    except Exception:
        pass
    try:
        name = (item.Name or "").strip().lower()
    except Exception:
        return False
    if not name:
        return False
    for want in SOS_NAMES:
        if want.strip().lower() in name:
            return True
    return False


def sos_on_hand():
    """How many SOS are in the pack and its bags right now."""
    return sum(amount_of(i) for i in walk_pack() if is_sos(i))


def find_bottles():
    """(total, [items]) - every bottle anywhere in the pack.

    The total counts STACKS by their amount: one item holding three bottles is
    three bottles, and three is what has to come off the count before this
    says it is finished.
    """
    bottles = [i for i in walk_pack() if is_mib(i)]
    return sum(amount_of(i) for i in bottles), bottles


def open_one(item):
    """Open a single bottle. True if the use was sent.

    Whether it WORKED is judged by the caller, from the count: a refusal is
    silent, and the server deciding you cannot open it right now looks exactly
    like success from here.
    """
    try:
        Items.UseItem(item)
    except Exception as err:
        log("could not open the bottle: %r" % err, HUE_BAD)
        return False
    Misc.Pause(USE_PAUSE_MS)
    return True


# =============================================================================
# THE STORAGE KEYS
# =============================================================================

def find_key(entry):
    """A deposit key, by serial first then by graphic and hue."""
    serial = int(entry.get("serial") or 0)
    if serial:
        item = Items.FindBySerial(serial)
        if item is not None:
            return item
        log("%s 0x%X did not resolve - looking by graphic."
            % (entry.get("label", "key"), serial), HUE_WARN)

    want_id = entry.get("id")
    want_hue = entry.get("hue", -1)
    if not want_id:
        return None
    for item in walk_pack():
        try:
            if int(item.ItemID) != int(want_id):
                continue
            if want_hue is not None and want_hue >= 0 \
                    and int(item.Hue) != int(want_hue):
                continue
        except Exception:
            continue
        return item
    return None


def context_labels(item):
    """The item's right-click menu as plain labels, or []."""
    try:
        entries = Misc.WaitForContext(item, CONTEXT_TIMEOUT_MS, False)
    except TypeError:
        entries = Misc.WaitForContext(item, CONTEXT_TIMEOUT_MS)
    except Exception as err:
        log("could not read the menu: %r" % err, HUE_WARN)
        return []
    out = []
    for entry in list(entries or []):
        text = str(getattr(entry, "Entry", entry) or "").strip()
        if text:
            out.append(text)
    return out


def is_blocked(label):
    low = (label or "").lower()
    for banned in CONTEXT_NEVER:
        if banned.strip().lower() in low:
            return True
    return False


def pick_entry(labels):
    """Which menu label to answer. EXACT first, guarded loose match second.

    An exact hit is always honoured - it was configured deliberately. The
    loose match exists because shards reword things, and it refuses anything
    on CONTEXT_NEVER: "Empty the key" sits on the same menu as the entry you
    want and does the opposite.
    """
    for want in FILL_ENTRIES:
        target = want.strip().lower()
        for label in labels:
            if label.strip().lower() == target:
                return label
    for want in FILL_ENTRIES:
        target = want.strip().lower()
        if not target:
            continue
        for label in labels:
            if target in label.lower():
                if is_blocked(label):
                    log("  refusing %r - it matches CONTEXT_NEVER." % label,
                        HUE_WARN)
                    continue
                return label
    return None


def deposit(reason=""):
    """Press every enabled key once. How many were actually answered."""
    pressed = 0
    for entry in DEPOSIT_KEYS:
        if not entry.get("enabled", True):
            continue
        label = entry.get("label", "key")

        key = find_key(entry)
        if key is None:
            log("%s not found (serial 0x%X, id 0x%04X) - nothing stored."
                % (label, int(entry.get("serial") or 0),
                   int(entry.get("id") or 0)), HUE_WARN)
            continue

        labels = context_labels(key)
        if not labels:
            log("%s showed no menu - is it in your pack?" % label, HUE_WARN)
            continue
        if label not in _menu_shown:
            _menu_shown.append(label)
            log("%s menu: %s" % (label, " | ".join(labels)))

        choice = pick_entry(labels)
        if choice is None:
            log("None of %s is on %s's menu, so NOTHING was pressed. Add the "
                "right wording to FILL_ENTRIES - it offers: %s"
                % (FILL_ENTRIES, label, " | ".join(labels)), HUE_BAD)
            continue

        log("  %s: %r%s" % (label, choice, " (%s)" % reason if reason else ""))
        Misc.ContextReply(key, choice)
        Misc.Pause(CONTEXT_PAUSE_MS)
        pressed += 1
    return pressed


# =============================================================================
# THE RUN
# =============================================================================

def preflight():
    """Say what will happen. False to stop before anything is opened."""
    log("MIB Opener v%s" % SCRIPT_VERSION, HUE_GOOD)

    if Player.Backpack is None:
        log("No backpack - nothing to search.", HUE_BAD)
        return False

    enabled = [e for e in DEPOSIT_KEYS if e.get("enabled", True)]
    if not enabled:
        log("No deposit key is enabled - bottles will be opened and whatever "
            "comes out will stay in your pack.", HUE_WARN)
    else:
        log("  storing into: %s"
            % ", ".join(e.get("label", "key") for e in enabled))

    total, _ = find_bottles()
    log("  %d bottle(s) found (graphic %s, %s)"
        % (total, ", ".join("0x%04X" % i for i in MIB_IDS),
           "bags searched %d deep" % MAX_BAG_DEPTH if SEARCH_BAGS
           else "backpack only - bags are left shut"),
        HUE_GOOD if total else HUE_WARN)
    if not total:
        log("Nothing to open. Bottles have to be loose in the backpack unless "
            "you set SEARCH_BAGS = True.", HUE_WARN)
        return False
    return True


def main():
    if not preflight():
        return

    # What was already on you, so the run reports what IT produced rather than
    # what happens to be in the pack.
    sos_before = sos_on_hand()

    opened = 0
    stalled = 0
    since_deposit = 0

    while opened < MAX_OPENS:
        total, bottles = find_bottles()
        if not bottles:
            log("No bottles left.", HUE_GOOD)
            break

        if not open_one(bottles[0]):
            break

        after, _ = find_bottles()
        if after >= total:
            # The use went out and the count did not move. Retried once or
            # twice for a slow server, then stopped - carrying on is the
            # endless loop this script was written to replace.
            stalled += 1
            if stalled >= RETRY_PASSES:
                log("A bottle would not open - %d left and the count has not "
                    "moved in %d tries. Stopping." % (after, stalled), HUE_BAD)
                break
            log("  the count did not move - trying once more.", HUE_WARN)
            continue

        stalled = 0
        opened += 1
        since_deposit += 1
        log("opened %d, %d left" % (opened, after))

        if DEPOSIT_EVERY and since_deposit >= DEPOSIT_EVERY:
            deposit("every %d" % DEPOSIT_EVERY)
            since_deposit = 0
    else:
        log("Stopped at the MAX_OPENS ceiling of %d." % MAX_OPENS, HUE_WARN)

    produced = max(0, sos_on_hand() - sos_before)
    if opened:
        log("%d bottle(s) opened, %d SOS on you." % (opened, produced),
            HUE_GOOD)
        deposit("end of run")

        # VERIFIED BY RESULT. The menu entry can be answered and store
        # nothing, and "the reply was sent" is not evidence that anything
        # moved - so the pack is counted again rather than trusted.
        left = sos_on_hand()
        if left:
            log("%d SOS still in your pack - the key did not take them. Check "
                "it is the right key and that it accepts maps." % left,
                HUE_WARN)
        else:
            log("every SOS went into storage.", HUE_GOOD)
    else:
        log("No bottles were opened.", HUE_WARN)


main()
