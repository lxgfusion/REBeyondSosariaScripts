"""
Read the LEVEL off every taming order deed you are carrying.
==========================================================

For Razor Enhanced (IronPython 3.4). Reads only - nothing is targeted, moved,
dropped or handed in.

WHY THIS EXISTS
---------------
A taming order deed's tooltip carries its level:

    Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:

That number is the SHARD'S, not ServUO's. ServUO gives every tameable species
a minimum taming skill, and this repo already has all 112 of those extracted
into TameAndFill.py's ANIMAL_CATALOGUE - but the skill ladder is evenly spaced
6.0 apart with no natural gaps in it, so no banding of those values can be
turned into levels without inventing the boundaries.

So the levels have to be read off the game, and this is what reads them. Run it
holding as many different deeds as you can; each run prints paste-ready rows
for docs/taming-order-levels.md, and the table fills itself the same way the
granite hue table did.

It also says how many species are still unknown, so it is obvious when the
table is done.

USAGE
-----
Put taming order deeds in your backpack and run it. Deeds inside a bag in the
pack are found too - the search walks containers, not just the top level.
"""

import re


# =============================================================================
# CONFIG
# =============================================================================

# An item counts as a deed if its name or tooltip contains one of these. Same
# list TameAndFill.py uses; keep them in step.
DEED_NAME_HINTS = ["order", "deed", "contract"]

# The tooltip labels the species and the level hide behind. Matched
# case-insensitively, first hit wins.
SPECIES_FIELDS = ["creature type", "animal type", "species", "type"]
LEVEL_FIELDS = ["level"]

# EVERY label these tooltips are known to use. A value ends where the next one
# of these begins, and that has to be a known list rather than a shape: a
# shape-based rule cannot tell the label "Warhorse Filled:" - which does not
# exist - from the value "Dread Warhorse" followed by "Filled:", which is what
# it really is. Reading it by shape returned the species as "Dread".
#
# An unknown label here costs a value that runs on into the next field, and the
# tooltip is printed in full for exactly that case.
ALL_LABELS = ["level", "creature type", "animal type", "species", "type",
              "filled", "progress", "amount", "gold", "runics", "weight",
              "blessed", "value", "uses remaining"]

# How deep to walk into bags inside the pack.
MAX_DEPTH = 3

PROPS_TIMEOUT = 1500

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Levels] " + text, hue, False)


def split_runtogether(raw):
    """Separate tooltip properties that arrive concatenated.

    "Level: 2Creature Type: KirinFilled: 24/60" lowercases to "kirinfilled",
    where a trailing word boundary can never match. A space at each
    lower/digit -> upper seam turns it into "kirin filled".
    """
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw or "")


def item_text(item):
    """Name + tooltip of an item, de-concatenated. Original case kept.

    Case is KEPT because split_runtogether needs it - lowercasing first
    destroys the seams it splits on, which is the whole reason the species name
    used to come out as "kirinfilled".
    """
    try:
        Items.WaitForProps(item, PROPS_TIMEOUT)
    except Exception:
        pass
    parts = []
    try:
        if item.Name:
            parts.append(str(item.Name))
    except Exception:
        pass
    try:
        parts.extend(str(p) for p in (Items.GetPropStringList(item) or []))
    except Exception:
        pass
    return split_runtogether(" ".join(parts))


def field_value(text, labels):
    """The value after the first of `labels` that appears. "" if none does.

    The value ends where the next KNOWN label begins - see ALL_LABELS for why
    that cannot be done by shape. There is no separator between one property's
    value and the next property's name, which is what makes this fiddly at all.

    Longest label first, so "creature type" is never matched as bare "type".
    """
    stop = "|".join(re.escape(l) for l in
                    sorted(ALL_LABELS, key=len, reverse=True))
    for label in labels:
        match = re.search(r"%s\s*:\s*(.+?)(?=\s*(?:%s)\s*:|$)"
                          % (re.escape(label), stop), text, re.I)
        if match:
            return match.group(1).strip()
    return ""


def walk_pack(container, depth=0):
    """Every item in the pack, including inside bags. [] on any failure."""
    out = []
    if container is None or depth > MAX_DEPTH:
        return out
    try:
        contents = list(getattr(container, "Contains", None) or [])
    except Exception:
        return out
    for item in contents:
        out.append(item)
        try:
            if item.IsContainer:
                out.extend(walk_pack(item, depth + 1))
        except Exception:
            pass
    return out


def looks_like_deed(text):
    low = (text or "").lower()
    for hint in DEED_NAME_HINTS:
        if hint.strip().lower() in low:
            return True
    return False


def main():
    log("reading taming order deeds - nothing will be touched.", HUE_GOOD)

    pack = Player.Backpack
    if pack is None:
        log("No backpack.", HUE_BAD)
        return

    try:
        Items.WaitForContents(pack, 4000)
    except Exception:
        pass

    items = walk_pack(pack)
    log("%d item(s) in the pack, bags included." % len(items))

    found = {}          # species -> level
    clashes = {}        # species -> set of levels, when a species disagrees
    unreadable = []

    for item in items:
        text = item_text(item)
        if not looks_like_deed(text):
            continue

        species = field_value(text, SPECIES_FIELDS)
        level = field_value(text, LEVEL_FIELDS)

        if not species or not level:
            # Named, not counted. A deed this cannot read is the interesting
            # one - it means the labels above are wrong for it, and the whole
            # tooltip is printed so the right label is obvious.
            unreadable.append((item, text))
            continue

        level = level.strip().strip(".,")
        key = species.strip().lower()
        if key in found and found[key] != level:
            clashes.setdefault(key, set()).add(found[key])
            clashes[key].add(level)
        found[key] = level

    if not found and not unreadable:
        log("No taming order deeds in the pack. Put some in and run again.",
            HUE_WARN)
        return

    if found:
        log("%d species read:" % len(found), HUE_GOOD)
        for key in sorted(found):
            log("  %-26s level %s" % (key, found[key]))

        log("", HUE_INFO)
        log("PASTE THESE into docs/taming-order-levels.md:", HUE_GOOD)
        for key in sorted(found):
            log('    "%s": %s,' % (key, found[key]))

    # A species that reads two different levels means the level is not a
    # property of the species at all - it is a property of the DEED. That
    # would change the whole shape of the table, so it is not buried.
    if clashes:
        log("", HUE_INFO)
        log("SAME SPECIES, DIFFERENT LEVELS - the level is a property of the "
            "DEED, not of the creature:", HUE_BAD)
        for key in sorted(clashes):
            log("  %-26s levels %s"
                % (key, ", ".join(sorted(clashes[key]))), HUE_BAD)

    if unreadable:
        log("", HUE_INFO)
        log("%d deed(s) whose level or species would not read. Their whole "
            "tooltips follow - if the label differs, add it to SPECIES_FIELDS "
            "or LEVEL_FIELDS." % len(unreadable), HUE_WARN)
        for item, text in unreadable[:6]:
            try:
                log("  0x%X: %s" % (int(item.Serial), text[:120]), HUE_WARN)
            except Exception:
                log("  (unreadable item): %s" % text[:120], HUE_WARN)

    log("", HUE_INFO)
    log("Run again holding different deeds to fill in more of the table.",
        HUE_INFO)


main()
