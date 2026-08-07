"""
Vendor / NPC context menu diagnostic.
=====================================

Run this standing next to the NPCs the mining script has stopped talking to.

It lists every mobile in range with the exact name Razor sees, then opens each
one's context menu and prints the entries verbatim. Copy the output back.

Why the mining script stopped working is almost always one of two things:

  * `Mobiles.Filter().Name` is an EXACT match. If the shard renamed
    "Resource Gatherer" to anything else - even adding a title - the filter
    returns nothing and the loop silently does nothing.
  * The context entry text changed ("Talk" -> something else), so ContextReply
    matches nothing.

This script only opens context menus, it never picks an entry.

Output file: %TEMP%\\vendor_dump.txt (path is printed when it finishes).
"""

import os


SEARCH_RANGE = 20

# Names the mining script currently looks for, so the report can say directly
# whether an exact-match filter would still find them.
EXPECTED = [
    "Resource Gatherer",     # observed as the name "Davin the Resource Gatherer"
    "Animal Trainer",        # observed as a TOOLTIP on the NPC named "Sherri"
    "Scribe",                # observed as a TOOLTIP on the NPC named "Edie"
]

CONTEXT_TIMEOUT = 8000
SHOW_CONTEXT_IN_GAME = False

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "vendor_dump.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

_lines = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Vend] " + text, hue, False)
    _lines.append(text)


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


def nearby_mobiles():
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = SEARCH_RANGE
    found = Mobiles.ApplyFilter(f)
    return list(found) if found else []


def mob_name(mob):
    if mob.Name:
        return mob.Name
    Mobiles.WaitForProps(mob, 1500)
    fresh = Mobiles.FindBySerial(mob.Serial)
    if fresh is not None and fresh.Name:
        return fresh.Name
    Mobiles.SingleClick(mob)
    Misc.Pause(600)
    fresh = Mobiles.FindBySerial(mob.Serial)
    return (fresh.Name if fresh is not None else "") or ""


def mob_props(mob):
    """A mobile's tooltip lines. This is where vendor titles live."""
    try:
        Mobiles.WaitForProps(mob, 1500)
        props = Mobiles.GetPropStringList(mob)
    except Exception as err:
        log("    tooltip read failed: %s" % err, HUE_BAD)
        return []
    return [p for p in (props or []) if p]


def context_entries(mob):
    try:
        ctx = Misc.WaitForContext(mob, CONTEXT_TIMEOUT, SHOW_CONTEXT_IN_GAME)
    except TypeError:
        ctx = Misc.WaitForContext(mob, CONTEXT_TIMEOUT)
    if not ctx:
        return None
    out = []
    for entry in ctx:
        label = getattr(entry, "Entry", None)
        response = getattr(entry, "Response", None)
        out.append((response, label if label is not None else str(entry)))
    return out


def exact_filter_finds(name):
    """Would Mobiles.Filter().Name = name still find anything?"""
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = SEARCH_RANGE
    f.Name = name
    found = Mobiles.ApplyFilter(f)
    return len(found) if found else 0


def main():
    rule("vendor / context diagnostic")

    mobs = nearby_mobiles()
    if not mobs:
        log("No mobiles within %d tiles at all." % SEARCH_RANGE, HUE_BAD)
        write_file()
        return

    log("%d mobiles within %d tiles." % (len(mobs), SEARCH_RANGE), HUE_INFO)

    rule("exact-name filter check")
    for want in EXPECTED:
        hits = exact_filter_finds(want)
        log("Mobiles.Filter(Name=%r) -> %d hit(s)%s"
            % (want, hits, "" if hits else "   <- this is why it stopped talking"),
            HUE_GOOD if hits else HUE_BAD)

    rule("every mobile in range")
    log("NOTE: a vendor's TITLE is usually in its tooltip, not its name -"
        " 'Sherri' has the tooltip 'Animal Trainer'. Match on the title.",
        HUE_WARN)
    named = []
    for mob in mobs:
        name = mob_name(mob)
        if not name:
            continue
        named.append((name, mob))
        log("%-30s serial=0x%X body=0x%X notor=%d dist=%d"
            % (name, mob.Serial, mob.Body, mob.Notoriety,
               Player.DistanceTo(mob)), HUE_INFO)
        for line in mob_props(mob):
            log("    tooltip: %s" % line, HUE_GOOD)

    rule("context menus")
    log("Opening the menu for each named mobile. Nothing is selected.", HUE_INFO)
    for name, mob in named:
        if Player.DistanceTo(mob) > 3:
            continue                     # context menus need to be close
        entries = context_entries(mob)
        log("-- %s (0x%X)" % (name, mob.Serial), HUE_STEP)
        if entries is None:
            log("   no context menu returned", HUE_WARN)
            continue
        for response, label in entries:
            log("   [%s] %s" % (response, label), HUE_INFO)
        Misc.Pause(400)

    rule("what to do with this")
    log("Copy the TOOLTIP title (not the given name) into the VENDORS table's "
        "'names', and the exact context entry into 'context'.", HUE_GOOD)
    log("Names match case-insensitively against the name AND the tooltip, so "
        "'Animal Trainer' finds the NPC called Sherri.", HUE_GOOD)
    log("Prefer the EXACT context entry text. A loose value can substring-hit "
        "Buy, Sell, Bribe or Train <skill> on the same menu.", HUE_WARN)

    write_file()


def write_file():
    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(_lines))
        Misc.SendMessage("[Vend] Written to %s" % DUMP_PATH, HUE_GOOD, False)
    except Exception as err:
        Misc.SendMessage("[Vend] Could not write dump file: %s" % err, HUE_BAD, False)


main()
