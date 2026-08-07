"""
Resource Order Book - why the census does not see the copper.
=============================================================

READ-ONLY apart from opening containers. It presses no gump button, moves
nothing and targets nothing.

WHY THIS EXISTS
---------------
`diag_copper_pages.py` proved the runner SEES the Copper Ingots orders - 26 of
them on pages 1 and 2, wanting 1460 to 2402 each. The only rejection left is
`amount > budget`, and the chest visibly holds a stack of 31,487 copper. So
`census()` is not counting it.

`census()` reads `chest.Contains` for each chest in CHESTS, ONE LEVEL DEEP, and
identifies a stack by ItemID plus Hue. That gives four ways to miss a stack, and
this tells them apart:

  1. IN A SUB-BAG. A bag inside the chest is one entry in Contains; the runner
     never looks inside it, so everything in it is invisible.
  2. WRONG HUE. If this shard's copper is not 0x096D, resource_of returns None
     and the stack is not copper as far as the runner is concerned.
  3. OUTSIDE THE CHESTS. Locked down on the ground, or in a container that is
     not in CHESTS. House storage is locked down on the ground and has
     Container: None - a chest search never finds it.
  4. STALE SNAPSHOT. Contains is taken when the container is opened. This
     re-opens each chest first, the same way the runner's refresh_chest does.

WHAT IT DOES
------------
Walks both chests to a depth of SEARCH_DEPTH, then does a WORLD search for every
ingot stack in range, and compares the two. Whatever the world search finds that
the chest walk does not is exactly what the runner is blind to.

OUTPUT
------
The journal, and %TEMP%\\ro_copper_stock.txt.
"""

import os
import re
import time


# =============================================================================
# CONFIG
# =============================================================================

# The metal under investigation. "" reports every ingot without singling one out.
FOCUS = "Copper"

# Same chests the runner searches, copied from resource_order_runner.py.
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

WORLD_RANGE = 4

# All nine ingots share this graphic and are told apart ONLY by hue.
INGOT_ID = 0x1BF2

# From docs/resource-order-book-gump.md, verified against ServUO ResourceInfo.cs.
# If the shard disagrees, this diag is what will show it.
INGOT_HUES = {
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

# How deep to walk containers inside the chests. The runner walks exactly 1 -
# anything this finds below that is invisible to it. 3 is plenty for a bag in a
# bag in a chest.
SEARCH_DEPTH = 3

CONTENTS_TIMEOUT_MS = 4000
SETTLE_MS = 600
OPEN_TRIES = 3

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "ro_copper_stock.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

REPORT = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[STOCK] " + str(text), hue, False)
    REPORT.append(str(text))


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


def metal_of(item):
    """The metal name for an ingot stack, or None if it is not ingots."""
    try:
        if int(item.ItemID) != INGOT_ID:
            return None
        return INGOT_HUES.get(int(item.Hue))
    except Exception:
        return None


def amount_of(item):
    try:
        return int(getattr(item, "Amount", 0) or 0)
    except Exception:
        return 0


def describe(item, note=""):
    try:
        name = re.sub(r"^\s*[\d,]+\s+", "", (getattr(item, "Name", "") or ""))
    except Exception:
        name = ""
    try:
        container = int(getattr(item, "Container", 0) or 0)
    except Exception:
        container = 0
    try:
        root = int(getattr(item, "RootContainer", 0) or 0)
    except Exception:
        root = 0
    return ("0x%08X  id 0x%04X  hue 0x%04X  x%-7d  %-18s "
            "container 0x%08X  root 0x%08X  ground %s%s"
            % (int(item.Serial), int(item.ItemID), int(item.Hue),
               amount_of(item), name[:18], container, root,
               "yes" if getattr(item, "OnGround", False) else "no",
               "  " + note if note else ""))


# ---------------------------------------------------------------------------
# Finding things
# ---------------------------------------------------------------------------

def find_world_item(serial, item_id, hue, label):
    if serial:
        item = Items.FindBySerial(serial)
        if item is not None:
            return item
        log("%s: serial 0x%X did not resolve, falling back to id/hue."
            % (label, serial), HUE_WARN)
    try:
        found = list(Items.FindAllByID(item_id, hue, -1, WORLD_RANGE, False) or [])
    except Exception as err:
        log("%s: FindAllByID failed: %s" % (label, err), HUE_BAD)
        return None
    if not found:
        return None
    found.sort(key=lambda it: Player.DistanceTo(it))
    return found[0]


def open_container(item, tries=OPEN_TRIES):
    """Re-open a container so its Contains list is current.

    Same shape as the runner's refresh_chest: Contains is a snapshot taken when
    the container was opened, and re-opening is the only real refresh.
    """
    serial = int(item.Serial)
    for _ in range(max(1, tries)):
        fresh = Items.FindBySerial(serial)
        if fresh is None:
            return None
        try:
            Items.UseItem(fresh)
            Items.WaitForContents(fresh, CONTENTS_TIMEOUT_MS)
        except Exception as err:
            log("could not open 0x%08X: %s" % (serial, err), HUE_WARN)
        Misc.Pause(SETTLE_MS)
        fresh = Items.FindBySerial(serial)
        if list(getattr(fresh, "Contains", None) or []):
            return fresh
    return Items.FindBySerial(serial)


def walk(container, depth, path, out):
    """Record every item under `container`, remembering how deep it sits.

    depth 1 is what the runner's census sees. Anything deeper is invisible to it.
    """
    fresh = open_container(container)
    if fresh is None:
        log("%s vanished while being read." % path, HUE_BAD)
        return
    contents = list(getattr(fresh, "Contains", None) or [])
    log("%s: %d item(s) at depth %d" % (path, len(contents), depth))

    for item in contents:
        out.append({"item": item, "depth": depth, "path": path})
        is_container = bool(getattr(item, "IsContainer", False))
        has_contents = bool(list(getattr(item, "Contains", None) or []))
        if (is_container or has_contents) and depth < SEARCH_DEPTH:
            name = re.sub(r"^\s*[\d,]+\s+",
                          "", (getattr(item, "Name", "") or "")) or "bag"
            log("  -> 0x%08X %r is a CONTAINER, going inside"
                % (int(item.Serial), name[:24]), HUE_WARN)
            walk(item, depth + 1, "%s > %s" % (path, name[:16]), out)


# ---------------------------------------------------------------------------

def totals(entries):
    """{metal: amount} for the ingot stacks in `entries`."""
    out = {}
    for rec in entries:
        metal = metal_of(rec["item"])
        if metal is None:
            continue
        out[metal] = out.get(metal, 0) + amount_of(rec["item"])
    return out


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
    rule("where is the %s?" % (FOCUS or "stock"))
    log("read-only: opens containers, presses no button, moves nothing.")

    # --- 1. walk the chests the way the runner does, but deeper --------------
    rule("1. the chests in CHESTS")
    found = []
    for entry in CHESTS:
        if not entry.get("enabled"):
            log("chest %r is disabled - skipped" % entry.get("label", "?"))
            continue
        chest = find_world_item(entry.get("serial", 0), entry["id"],
                                entry.get("hue", -1), entry.get("label", "chest"))
        if chest is None:
            log("chest %r NOT FOUND within %d tiles - stand next to it."
                % (entry.get("label", "?"), WORLD_RANGE), HUE_BAD)
            continue
        log("chest %r found at 0x%08X, %d tiles away"
            % (entry.get("label", "?"), int(chest.Serial),
               Player.DistanceTo(chest)), HUE_GOOD)
        found.append((chest, entry.get("label", "chest")))

    if not found:
        log("No chest could be found. Stand next to them and run this again.",
            HUE_BAD)
        return

    entries = []
    chest_serials = set()
    for chest, label in found:
        chest_serials.add(int(chest.Serial))
        walk(chest, 1, label, entries)

    shallow = [e for e in entries if e["depth"] == 1]
    deep = [e for e in entries if e["depth"] > 1]

    rule("2. ingots the chest walk found")
    for rec in sorted(entries, key=lambda r: -amount_of(r["item"])):
        metal = metal_of(rec["item"])
        if metal is None:
            continue
        log("  %-12s depth %d  %s" % (metal, rec["depth"],
                                      describe(rec["item"])),
            HUE_BAD if rec["depth"] > 1 else HUE_INFO)

    # Ingot-graphic stacks whose hue is not in the table at all.
    unknown = [r for r in entries
               if int(r["item"].ItemID) == INGOT_ID and metal_of(r["item"]) is None]
    for rec in unknown:
        log("  UNKNOWN HUE  depth %d  %s" % (rec["depth"], describe(rec["item"])),
            HUE_BAD)

    census_totals = totals(shallow)          # what the runner would count
    all_totals = totals(entries)             # what is really in the chests

    # --- 3. world search, to catch anything outside the chests --------------
    rule("3. every ingot stack in range, from the world index")
    world = []
    try:
        world = list(Items.FindAllByID(INGOT_ID, -1, -1, WORLD_RANGE, False) or [])
    except Exception as err:
        log("world FindAllByID failed: %s" % err, HUE_BAD)

    seen_in_chests = set(int(r["item"].Serial) for r in entries)
    outside = []
    for item in sorted(world, key=lambda i: -amount_of(i)):
        serial = int(item.Serial)
        note = ""
        if serial not in seen_in_chests:
            note = "<-- NOT FOUND BY THE CHEST WALK"
            outside.append(item)
        log("  %-12s %s" % (metal_of(item) or "unknown-hue", describe(item, note)),
            HUE_BAD if note else HUE_INFO)
    if not world:
        log("  the world search returned nothing - ingots may be out of range "
            "(WORLD_RANGE is %d)." % WORLD_RANGE, HUE_WARN)

    # --- 4. the comparison that answers the question ------------------------
    rule("4. what the runner counts vs what is there")
    metals = sorted(set(list(census_totals) + list(all_totals)
                        + [metal_of(i) for i in world if metal_of(i)]))
    world_totals = {}
    for item in world:
        metal = metal_of(item)
        if metal:
            world_totals[metal] = world_totals.get(metal, 0) + amount_of(item)

    log("  %-14s %-12s %-12s %-12s" % ("metal", "runner", "chests(all)", "world"))
    for metal in metals:
        counted = census_totals.get(metal, 0)
        real = max(all_totals.get(metal, 0), world_totals.get(metal, 0))
        log("  %-14s %-12d %-12d %-12d%s"
            % (metal, counted, all_totals.get(metal, 0),
               world_totals.get(metal, 0),
               "   <-- MISSED" if real > counted else ""),
            HUE_BAD if real > counted else HUE_GOOD)

    # --- verdict ------------------------------------------------------------
    rule("verdict")
    focus = (FOCUS or "").strip().lower()
    counted = 0
    real = 0
    for metal in metals:
        if focus and metal.strip().lower() != focus:
            continue
        counted = max(counted, census_totals.get(metal, 0))
        real = max(real, all_totals.get(metal, 0), world_totals.get(metal, 0))

    focus_deep = [r for r in deep
                  if focus and (metal_of(r["item"]) or "").lower() == focus]
    focus_outside = [i for i in outside
                     if focus and (metal_of(i) or "").lower() == focus]

    if focus and real == 0 and not unknown:
        log("NOT FOUND AT ALL. No %s stack is in the chests or within %d tiles. "
            "Either it is somewhere else entirely, or its hue is not 0x096D - "
            "check the UNKNOWN HUE lines above." % (FOCUS, WORLD_RANGE), HUE_BAD)
    elif unknown:
        log("WRONG HUE. %d ingot stack(s) carry a hue that is not in the table, "
            "so resource_of returns None and the runner does not know what they "
            "are. Add the hue above to RESOURCES." % len(unknown), HUE_BAD)
    elif focus_deep:
        log("IN A SUB-BAG. %d %s stack(s) sit BELOW the top level of the chest, "
            "and census() only reads chest.Contains one level deep - so it "
            "counts none of them." % (len(focus_deep), FOCUS), HUE_BAD)
        for rec in focus_deep:
            log("   depth %d at %s: x%d"
                % (rec["depth"], rec["path"], amount_of(rec["item"])), HUE_BAD)
        log("FIX: walk containers inside the chest in all_resource_stacks(), or "
            "move the stack to the top level of the chest.", HUE_WARN)
    elif focus_outside:
        log("OUTSIDE THE CHESTS. %d %s stack(s) are in range but in no chest "
            "in CHESTS - locked down on the ground, or in a container the "
            "runner does not know about." % (len(focus_outside), FOCUS), HUE_BAD)
        for item in focus_outside:
            log("   %s" % describe(item), HUE_BAD)
        log("FIX: add that container to CHESTS, or move the stack into one.",
            HUE_WARN)
    elif focus and counted >= real and real > 0:
        log("THE CENSUS SEES IT: %d %s. If the runner still will not fill a "
            "Copper order, the budget is not the problem after all - capture "
            "its ==== stock ==== block and the journal around Copper's turn."
            % (counted, FOCUS), HUE_WARN)
    else:
        log("Nothing conclusive. The table above is the evidence - send it "
            "over.", HUE_WARN)

    log("done in %.1fs" % (time.time() - started))

    out = ["Resource Order Book - stock census check",
           "=" * 55, "",
           "run at   : %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
           "focus    : %r" % FOCUS,
           "depth    : %d (the runner walks 1)" % SEARCH_DEPTH,
           "", "-- journal, verbatim ---------------------------------"]
    out.extend(REPORT)
    out.append("")
    out.append("-- every item found in the chests --------------------")
    for rec in entries:
        out.append("  depth %d  %-28s %s"
                   % (rec["depth"], rec["path"][:28], describe(rec["item"])))
    if write_file(out):
        log("written to %s" % DUMP_PATH, HUE_GOOD)


main()
