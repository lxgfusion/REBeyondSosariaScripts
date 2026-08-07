"""
Chest contents - every item, every hue, with tooltips.
======================================================

READ-ONLY apart from opening containers. Nothing is moved, no gump button is
pressed, no context menu is answered.

WHY THIS EXISTS
---------------
resource_order_runner.py identifies ingots and boards by GRAPHIC + HUE, never by
name: a stack is called "<amount> ingots" or "<amount> boards" and says nothing
about the metal or the wood. Its BOARD_HUES table is empty, so no wood can be
identified yet and board orders are passed over as if the chest were empty.

This prints what is actually in the chests, grouped by (ItemID, Hue), with the
full tooltip of one stack from each group - because that is where the type name
lives. The ingot hue table was confirmed exactly this way: the metal is named on
the stack's third tooltip line, in lower case.

It then emits ready-to-paste BOARD_HUES lines for every board group whose wood
it could name.

NAMES
-----
The book spells them "Ash Boards", "Magewood Boards" - confirmed from the order
list. Plain boards are "Regular Boards" in the book, though the wood storage
window calls that wood "Plain"; the two vocabularies differ the same way the
ingot tooltip says "golden" where the book says "Gold". The BOOK's name is what
BOARD_HUES needs.

OUTPUT
------
The journal, and %TEMP%\\ro_chest_contents.txt - which is the one to send on,
since a full chest is far more than the journal will hold.
"""

import os
import re
import time


SCRIPT_VERSION = "2026-07-31.1"


# =============================================================================
# CONFIG
# =============================================================================

# The same chests resource_order_runner.py searches.
CHESTS = [
    {
        "label": "ingots and gems",
        "enabled": True,
        "serial": 0x400CEF90,
        "id": 0x0E41,
        "hue": 0x089F,
    },
    {
        "label": "peerless ingredients",
        "enabled": True,
        "serial": 0x400463FB,
        "id": 0x0E41,
        "hue": 0x047E,
    },
]

# Also walk your backpack. Boards may be sitting there rather than in a chest.
INCLUDE_BACKPACK = True

WORLD_RANGE = 4

# Graphics reported in the BOARD section. 0x1BD9 is included ONLY so that the
# Wood Storage key shows up and can be told apart - it is NOT a board, and
# resource_order_runner.py excludes it from BOARD_IDS for that reason.
BOARD_IDS = [0x1BD7]
BOARD_LOOKALIKE_IDS = [0x1BD9, 0x1BDD]      # storage key, logs

# Wood names as the storage window lists them, mapped to the BOOK's name.
# Matching a tooltip against these is what turns a hue into a usable entry.
WOOD_NAMES = {
    "plain": "Regular Boards",
    "regular": "Regular Boards",
    "oak": "Oak Boards",
    "ash": "Ash Boards",
    "yew": "Yew Boards",
    "heartwood": "Heartwood Boards",
    "bloodwood": "Bloodwood Boards",
    "frostwood": "Frostwood Boards",
    "darkwood": "Darkwood Boards",
    "magewood": "Magewood Boards",
}

# How deep to walk bags inside a chest.
SEARCH_DEPTH = 3

# Tooltip lines printed per group. The type name is usually on line 2 or 3.
TOOLTIP_LINES = 6

CONTENTS_TIMEOUT_MS = 4000
PROPS_TIMEOUT_MS = 1500
SETTLE_MS = 600
OPEN_TRIES = 3

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "ro_chest_contents.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

REPORT = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[CHEST] " + str(text), hue, False)
    REPORT.append(str(text))


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def spaced(text):
    """Split the lower/digit -> upper seam in a concatenated tooltip."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text or "")


def strip_amount(name):
    return re.sub(r"^\s*[\d,]+\s+", "", name or "").strip()


def safe_name(item):
    try:
        return str(getattr(item, "Name", "") or "")
    except Exception:
        return ""


def tooltip(item):
    try:
        Items.WaitForProps(item, PROPS_TIMEOUT_MS)
        return [str(l or "") for l in (Items.GetPropStringList(item) or [])]
    except Exception:
        return []


def wood_from_text(text):
    """The BOOK's board name for a tooltip, or None.

    Longest name first, so "bloodwood" is not claimed by "wood" and
    "heartwood" is not claimed by a bare "wood". The \\b anchors keep "ash"
    from matching inside "ashes".
    """
    blob = spaced(text or "").lower()
    for wood in sorted(WOOD_NAMES, key=len, reverse=True):
        if re.search(r"\b%s\b" % re.escape(wood), blob):
            return WOOD_NAMES[wood]
    return None


# ---------------------------------------------------------------------------
# Finding and walking
# ---------------------------------------------------------------------------

def find_world_item(serial, item_id, hue, label):
    if serial:
        item = Items.FindBySerial(serial)
        if item is not None:
            return item
        log("%s: serial 0x%X did not resolve, trying id/hue." % (label, serial),
            HUE_WARN)
    try:
        found = list(Items.FindAllByID(item_id, hue, -1, WORLD_RANGE, False) or [])
    except Exception as err:
        log("%s: FindAllByID failed: %s" % (label, err), HUE_BAD)
        return None
    if not found:
        return None
    found.sort(key=lambda it: Player.DistanceTo(it))
    return found[0]


def open_container(item):
    """Re-open a container so its Contains list is current.

    Contains is a snapshot taken when the container was opened - re-opening is
    the only real refresh.
    """
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


def walk(container, depth, path, out):
    fresh = open_container(container)
    if fresh is None:
        log("%s could not be read." % path, HUE_BAD)
        return
    contents = list(getattr(fresh, "Contains", None) or [])
    log("%s: %d item(s)" % (path, len(contents)))

    for item in contents:
        out.append({"item": item, "depth": depth, "path": path})
        is_container = bool(getattr(item, "IsContainer", False))
        has_contents = bool(list(getattr(item, "Contains", None) or []))
        if (is_container or has_contents) and depth < SEARCH_DEPTH:
            name = strip_amount(safe_name(item)) or "bag"
            walk(item, depth + 1, "%s > %s" % (path, name[:16]), out)


# ---------------------------------------------------------------------------

def group_key(item):
    try:
        return (int(item.ItemID), int(item.Hue))
    except Exception:
        return (0, 0)


def build_groups(records):
    """{(id, hue): {amount, stacks, name, tooltip, paths}}"""
    groups = {}
    for record in records:
        item = record["item"]
        key = group_key(item)
        group = groups.get(key)
        if group is None:
            group = groups[key] = {
                "amount": 0, "stacks": 0,
                "name": strip_amount(safe_name(item)),
                "tooltip": tooltip(item),      # read once per group, not per item
                "paths": set(),
            }
        try:
            group["amount"] += int(getattr(item, "Amount", 0) or 0)
        except Exception:
            pass
        group["stacks"] += 1
        group["paths"].add(record["path"])
    return groups


def write_file(lines):
    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(lines))
        return True
    except Exception as err:
        log("could not write %s: %s" % (DUMP_PATH, err), HUE_BAD)
        return False


def main():
    started = time.time()
    rule("chest contents - v%s" % SCRIPT_VERSION)
    log("read-only: opens containers, moves nothing, presses nothing.")

    records = []

    for entry in CHESTS:
        if not entry.get("enabled"):
            log("chest %r disabled - skipped" % entry.get("label", "?"))
            continue
        chest = find_world_item(entry.get("serial", 0), entry["id"],
                                entry.get("hue", -1), entry.get("label", "chest"))
        if chest is None:
            log("chest %r NOT FOUND within %d tiles - stand next to it."
                % (entry.get("label", "?"), WORLD_RANGE), HUE_BAD)
            continue
        log("chest %r at 0x%08X, %d tiles away"
            % (entry.get("label", "?"), int(chest.Serial),
               Player.DistanceTo(chest)), HUE_GOOD)
        walk(chest, 1, entry.get("label", "chest"), records)

    if INCLUDE_BACKPACK:
        pack = Player.Backpack
        if pack is not None:
            walk(pack, 1, "backpack", records)

    if not records:
        log("Nothing was found in any chest. Stand next to them and re-run.",
            HUE_BAD)
        return

    groups = build_groups(records)
    log("%d item(s) in %d distinct (ItemID, Hue) group(s)"
        % (len(records), len(groups)))

    # --- boards first, since that is what this is for ----------------------
    rule("boards")
    board_groups = [(k, g) for k, g in groups.items() if k[0] in BOARD_IDS]
    lookalikes = [(k, g) for k, g in groups.items()
                  if k[0] in BOARD_LOOKALIKE_IDS]

    paste = []
    if not board_groups:
        log("No stack with a board graphic (%s) is in the chests or pack."
            % ", ".join("0x%04X" % i for i in BOARD_IDS), HUE_WARN)
        log("Put a stack of each wood in a chest and run this again.", HUE_WARN)
    else:
        for key, group in sorted(board_groups, key=lambda kv: -kv[1]["amount"]):
            item_id, hue = key
            blob = " | ".join([group["name"]] + group["tooltip"])
            wood = wood_from_text(blob)
            log("  hue 0x%04X  %-7d board(s) in %d stack(s)  ->  %s"
                % (hue, group["amount"], group["stacks"],
                   wood if wood else "WOOD NOT NAMED IN THE TOOLTIP"),
                HUE_GOOD if wood else HUE_WARN)
            for line in group["tooltip"][:TOOLTIP_LINES]:
                log("      %s" % spaced(line)[:70])
            if wood:
                paste.append('    "%s": 0x%04X,' % (wood, hue))
            else:
                paste.append('    # "<Wood> Boards": 0x%04X,   <- name it by eye'
                             % hue)

    if lookalikes:
        log("  (also present, NOT boards:)")
        for key, group in lookalikes:
            log("    id 0x%04X hue 0x%04X  %s x%d"
                % (key[0], key[1], group["name"][:24], group["amount"]))

    if paste:
        rule("paste into BOARD_HUES in resource_order_runner.py")
        log("BOARD_HUES = {")
        for line in paste:
            log(line, HUE_GOOD)
        log("}")
        unnamed = len([p for p in paste if p.strip().startswith("#")])
        if unnamed:
            log("%d hue(s) could not be named from the tooltip - match those "
                "against the wood storage window by eye." % unnamed, HUE_WARN)

    # --- then everything else ----------------------------------------------
    rule("everything in the chests, by graphic and hue")
    log("  %-8s %-8s %-9s %-7s %s"
        % ("ItemID", "Hue", "total", "stacks", "name"))
    for key, group in sorted(groups.items(),
                             key=lambda kv: (kv[0][0], kv[0][1])):
        log("  0x%04X   0x%04X   %-9d %-7d %s"
            % (key[0], key[1], group["amount"], group["stacks"],
               group["name"][:28]))

    out = ["Chest contents - every item, every hue",
           "=" * 55, "",
           "version : %s" % SCRIPT_VERSION,
           "run at  : %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
           "items   : %d in %d group(s)" % (len(records), len(groups)),
           "", "-- journal, verbatim ---------------------------------"]
    out.extend(REPORT)
    out.append("")
    out.append("-- every group, with its full tooltip ----------------")
    for key, group in sorted(groups.items(),
                             key=lambda kv: (kv[0][0], kv[0][1])):
        out.append("")
        out.append("  ItemID 0x%04X  Hue 0x%04X  total %d  in %d stack(s)"
                   % (key[0], key[1], group["amount"], group["stacks"]))
        out.append("    name : %s" % group["name"])
        out.append("    where: %s" % ", ".join(sorted(group["paths"]))[:70])
        for line in group["tooltip"]:
            out.append("    | %s" % spaced(line))

    if write_file(out):
        log("written to %s" % DUMP_PATH, HUE_GOOD)
    log("done in %.1fs" % (time.time() - started))


main()
