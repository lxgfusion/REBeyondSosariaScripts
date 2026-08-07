"""
Bulk order request diagnostic.
==============================

Travels to every stop in the VENDORS table below, reports exactly what is at
each location, requests an order, and records which gump came back.

Run this to verify one character's setup before copying the config to the
others. Everything is written to %TEMP%\\bod_diag.txt.

Per stop it reports:

    the rune it recalled to, and whether it got there
    every NPC in range, with name, TOOLTIP TITLE and distance
    whether the configured `names` matched, and which NPC
    the NPC's full context menu, verbatim
    which entry was chosen
    which gump id opened - the thing you actually need to know
    the Bulk Order Book count before and after

ANSWER_GUMP controls whether the order is actually accepted. Leave it False for
a first pass: you get every gump id without committing to anything.

Keep VENDORS, BOD_* and the runebook settings identical to harvest_runner.py.
"""

import os
import re
import time


# =============================================================================
# CONFIG - keep in step with harvest_runner.py
# =============================================================================

BOD_PROFESSIONS = {
    "blacksmith": {
        # Inspected: "Cara", serial 0x00099CA5, tooltip "Blacksmith".
        "names":   ["Blacksmith"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
    "scribe": {
        # Inspected: "Edie", tooltip "Scribe".
        "names":   ["Scribe"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
    "tailor": {
        # NOT INSPECTED YET - "Tailor" is a guess at the tooltip title.
        "names":   ["Tailor", "Weaver"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
    "carpenter": {
        # NOT INSPECTED YET.
        "names":   ["Carpenter"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
    "tinker": {
        # NOT INSPECTED YET. Disabled by not being listed at any location.
        "names":   ["Tinker"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
}

BOD_LOCATIONS = [
    {"enabled": True,  "label": "Smith rune",     "folder": ['BOD'],
     "point": 'Blacksmith',   "who": ["blacksmith"]},          # 1418, 1548

    {"enabled": True,  "label": "Tame+Inscribe",  "folder": ['BOD'],
     "point": 'tameinscribe', "who": ["scribe"]},               # 1479, 1790

    {"enabled": False, "label": "Tailor rune",    "folder": ['BOD'],
     "point": 'Tailor',       "who": ["tailor"]},               # 1470, 1688
    #                                            ^ enable once the tailor's
    #                                              tooltip title is confirmed.

    # To cover a whole town without cataloguing it, add the rune with "*":
    # {"enabled": True, "label": "Britain", "folder": ['BOD'],
    #  "point": 'Britain', "who": "*"},
]

BOD_COOLDOWN_MESSAGES = [
    "An offer may be available in about",
    "You'll have to wait a few seconds",     # 1079976, still inspecting
]



VENDORS = [
    {
        "enabled": True,
        "label":   "Resource Orders",
        "folder":  ['RO'],
        "point":   'RO',
        "names":   ["Resource Gatherer"],
        "context": ["Talk"],
        "gump":    None,
    },
    {
        "enabled": True,
        "label":   "Taming Deeds",
        "folder":  ['BOD'],
        "point":   'tameinscribe',
        "names":   ["Animal Trainer"],
        "context": ["Talk"],
        "gump":    None,
    },
    # The bulk order NPCs are NOT listed here - they come from the
    # BOD_PROFESSIONS x BOD_LOCATIONS tables above, exactly as in
    # harvest_runner.py, so this diagnostic tests what actually runs.
]


def expand_bod_locations():
    """Same expansion as harvest_runner.py."""
    out = []
    for loc in BOD_LOCATIONS:
        if not loc.get("enabled", True):
            continue
        where = loc.get("label") or loc.get("point") or "?"
        who = loc.get("who", "*")
        wildcard = (who == "*" or not who)
        for key in (sorted(BOD_PROFESSIONS) if wildcard else list(who)):
            spec = BOD_PROFESSIONS.get(key)
            if spec is None:
                continue
            out.append({
                "enabled": True,
                "label":   "%s @ %s" % (key, where),
                "folder":  loc["folder"],
                "point":   loc["point"],
                "names":   spec["names"],
                "context": spec["context"],
                "gump":    spec.get("gump"),
                "required": not wildcard,
            })
    return out


def all_vendors():
    return [v for v in VENDORS if v.get("enabled", True)] + expand_bod_locations()


def vendor_stops(vendors):
    """Group by rune so each location is travelled to once."""
    stops = []
    for vendor in vendors:
        key = ("/".join(vendor["folder"]).strip().lower(),
               (vendor["point"] or "").strip().lower())
        for stop in stops:
            if stop["key"] == key:
                stop["vendors"].append(vendor)
                break
        else:
            stops.append({"key": key, "folder": vendor["folder"],
                          "point": vendor["point"], "vendors": [vendor]})
    return stops

# Actually accept the order. False = look, do not touch.
ANSWER_GUMP = False

# Report every NPC in range, not just matches. Leave on - this is how you find
# the right title to match, and how you spot an NPC standing at the wrong rune.
LIST_ALL_NPCS = True

VENDOR_RANGE = 12
CONTEXT_TIMEOUT = 10000
GUMP_TIMEOUT = 8000
PROPS_TIMEOUT = 1500

BOD_BOOK_ID = 0x2259
BOD_DEED_IDS = [0x2258]

AR_COMMAND = "[ar"
AR_GUMPID = 0xc395adb4
AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON = 5
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 500, 503, 504]
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
AR_GATE_OFFSET = 30000
AR_MAX_PAGES = 20

MIN_MANA_TO_TRAVEL = 20

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "bod_diag.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

_lines = []


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[BOD] " + text, hue, False)
    _lines.append(text)


def rule(text):
    log("=" * 6 + " " + text + " " + "=" * 6, HUE_STEP)


def safe_name(obj):
    try:
        return (obj.Name or "") if obj is not None else ""
    except Exception:
        return ""


def chat_say(text):
    try:
        Player.ChatSay(0, text)
    except TypeError:
        Player.ChatSay(text)


def gump_lines(gump_id, data_only=False):
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
# RUNEBOOK - same navigation as harvest_runner.py
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
    if not openAR():
        return []
    layout = Gumps.GetGumpRawLayout(AR_GUMPID)
    if not layout:
        return []
    out = []
    for piece in re.split(r"\}\s*\{", layout):
        if "button" in piece.lower():
            data = re.findall(r"\d+", piece)
            if data:
                out.append(int(data[-1]))
    return out


def ar_page_info():
    for line in reversed(list(gump_lines(AR_GUMPID) or [])):
        found = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", line, re.I)
        if found:
            return int(found.group(1)), int(found.group(2))
    return (1, 1)


def parse_ar_page():
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
            continue
        if re.match(r"^\(\s*[-+]?\d", text):
            if entries:
                entries[-1]["coord"] = [int(x) for x in
                                        re.findall(r"[-+]?\d+", text)]
            continue
        found = re.match(r"^(\d+)\.\s*(.+)$", text)
        if found:
            entries.append({"label": found.group(2).strip(), "coord": None})

    folders, destinations = {}, {}
    for entry, button in zip(entries, entry_buttons):
        if entry["coord"] is not None or (button + AR_GATE_OFFSET) in buttons:
            destinations[button] = {"name": entry["label"],
                                    "coord": entry["coord"]}
        else:
            folders[button] = entry["label"]
    return folders, destinations


def ar_page_step(button):
    if button not in getARButtons():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, 10000)
    Misc.Pause(250)
    return True


def ar_goto_page(target):
    current, total = ar_page_info()
    target = max(1, min(target, total))
    for _ in range(AR_MAX_PAGES * 2):
        if current == target:
            return True
        if not ar_page_step(AR_NEXT_PAGE_BUTTON if current < target
                            else AR_PREV_PAGE_BUTTON):
            return False
        current, total = ar_page_info()
    return current == target


def iter_ar_pages():
    if not openAR():
        return
    ar_goto_page(1)
    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        folders, destinations = parse_ar_page()
        yield current, folders, destinations
        if current >= total:
            return
        if not ar_page_step(AR_NEXT_PAGE_BUTTON):
            return
        moved, _t = ar_page_info()
        if moved <= current:
            return


def ar_find(target, want_dest):
    wanted = (target or "").strip().lower()
    if not wanted:
        return None
    exact = partial = None
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
    return exact or partial


def goDir(folder=None):
    if folder is None:
        if AR_ROOT_BUTTON in getARButtons():
            Gumps.SendAction(AR_GUMPID, AR_ROOT_BUTTON)
            Gumps.WaitForGump(AR_GUMPID, 10000)
            Misc.Pause(250)
        return True
    if not openAR():
        return False
    hit = ar_find(folder, False)
    if hit is None:
        return False
    page, button, _name = hit
    if not ar_goto_page(page):
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, 10000)
    Misc.Pause(250)
    return True


def travel_to(folder_path, point):
    """Recall to a rune. Returns (ok, detail)."""
    if Player.Mana < MIN_MANA_TO_TRAVEL:
        log("Mana %d/%d - waiting for enough to recall."
            % (Player.Mana, Player.ManaMax), HUE_WARN)
        deadline = time.time() + 90
        while time.time() < deadline and Player.Mana < MIN_MANA_TO_TRAVEL:
            Player.UseSkill("Meditation")
            Misc.Pause(3000)
        if Player.Mana < MIN_MANA_TO_TRAVEL:
            return False, "not enough mana"

    goDir()
    for folder in folder_path:
        if not goDir(folder):
            return False, "folder %r not found in the runebook" % folder

    hit = ar_find(point, True)
    if hit is None:
        return False, "rune %r not found in %s" % (point, "/".join(folder_path))
    page, button, name = hit
    if not ar_goto_page(page):
        return False, "could not get back to page %d" % page
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(2500)
    return True, name


# =============================================================================
# NPCs
# =============================================================================

def mobile_props(mob):
    try:
        Mobiles.WaitForProps(mob, PROPS_TIMEOUT)
        props = Mobiles.GetPropStringList(mob)
    except Exception:
        return []
    return [p for p in (props or []) if p]


def nearby_npcs():
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = VENDOR_RANGE
    found = Mobiles.ApplyFilter(f)
    return list(found) if found else []


def matches(mob, names):
    low = safe_name(mob).lower()
    props = " ".join(mobile_props(mob)).lower()
    for want in names:
        want = want.strip().lower()
        if not want:
            continue
        if (low and want in low) or (props and want in props):
            return True
    return False


# =============================================================================
# BULK ORDER BOOK
# =============================================================================

def find_book():
    return Items.FindByID(BOD_BOOK_ID, -1, Player.Backpack.Serial, False, False)


def book_count():
    book = find_book()
    if book is None:
        return None
    try:
        Items.WaitForProps(book, PROPS_TIMEOUT)
        text = " ".join(Items.GetPropStringList(book) or []).lower()
    except Exception:
        return None
    found = re.search(r"deeds in book\s*:\s*(\d+)", text)
    return int(found.group(1)) if found else None


def loose_deeds():
    found = Items.FindAllByID(BOD_DEED_IDS, -1, Player.Backpack.Serial,
                              False, False)
    return len(found) if found else 0


# =============================================================================
# ONE STOP
# =============================================================================

def test_stop(vendor, travelled=True):
    """Test one NPC. `travelled` False means do the recall first."""
    label = vendor["label"]
    rule(label)

    if not travelled:
        ok, detail = travel_to(vendor["folder"], vendor["point"])
        log("rune %s/%s : %s" % ("/".join(vendor["folder"]), vendor["point"],
                                 detail if ok else "FAILED - %s" % detail),
            HUE_GOOD if ok else HUE_BAD)
        if not ok:
            return (label, "travel failed", None)

    npcs = nearby_npcs()
    if LIST_ALL_NPCS:
        log("NPCs within %d tiles:" % VENDOR_RANGE, HUE_INFO)
        if not npcs:
            log("   (none)", HUE_WARN)
        for mob in npcs:
            props = mobile_props(mob)
            log("   %-22s %-28s dist %d"
                % (safe_name(mob) or "(unnamed)",
                   " / ".join(props)[:28] or "(no tooltip)",
                   Player.DistanceTo(mob)), HUE_INFO)

    hits = [m for m in npcs if matches(m, vendor["names"])]
    if not hits:
        if vendor.get("required", True):
            log("NO MATCH for %s. Either the rune is wrong or the title is."
                % vendor["names"], HUE_BAD)
            return (label, "npc not found", None)
        log("not at this rune (asked for %s) - fine, this is a \"*\" location."
            % vendor["names"], HUE_INFO)
        return (label, "not present", None)

    hits.sort(key=lambda m: Player.DistanceTo(m))
    mob = hits[0]
    log("matched %s (%s) at %d tiles"
        % (safe_name(mob), " / ".join(mobile_props(mob)) or "no tooltip",
           Player.DistanceTo(mob)), HUE_GOOD)

    entries = wait_context(mob)
    if not entries:
        log("no context menu.", HUE_BAD)
        return (label, "no context menu", None)

    labels = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        labels.append(text if text is not None else str(entry))
    log("menu: %s" % " | ".join(labels), HUE_INFO)

    chosen = None
    for want in vendor["context"]:
        for entry_label in labels:
            if want.strip().lower() == (entry_label or "").strip().lower():
                chosen = entry_label
                break
        if chosen:
            break
    if chosen is None:
        for want in vendor["context"]:
            for entry_label in labels:
                if want.strip().lower() in (entry_label or "").lower():
                    chosen = entry_label
                    break
            if chosen:
                break
    if chosen is None:
        log("none of %s is on that menu." % vendor["context"], HUE_BAD)
        return (label, "context entry missing", None)

    before_book = book_count()
    before_loose = loose_deeds()
    log("before: %s deed(s) in book, %d loose in pack"
        % ("?" if before_book is None else before_book, before_loose), HUE_INFO)

    expected = [g for g, _b in (vendor.get("gump") or [])]
    for gump_id in expected:
        try:
            if has_gump(gump_id):
                Gumps.CloseGump(gump_id)
                Misc.Pause(250)
        except Exception:
            pass
    try:
        Gumps.ResetGump()
    except Exception:
        pass

    log("choosing %r" % chosen, HUE_INFO)
    Misc.ContextReply(mob, chosen)
    Misc.Pause(1500)

    opened = None
    for gump_id in expected:
        if Gumps.WaitForGump(gump_id, GUMP_TIMEOUT):
            opened = gump_id
            break
    if opened is None:
        try:
            current = Gumps.CurrentGump()
        except Exception:
            current = 0
        if current:
            log("GUMP 0x%X opened - NOT in this stop's list %s. Add "
                "(0x%X, <button>) to \"gump\"."
                % (current, ["0x%X" % g for g in expected] or "(none)", current),
                HUE_WARN)
            opened = current
            for line in (gump_lines(current) or [])[:12]:
                log("   gump text: %s" % line, HUE_INFO)
        elif expected:
            log("no gump opened at all.", HUE_WARN)
        else:
            log("no gump expected, none opened.", HUE_GOOD)
    else:
        log("gump 0x%X opened as expected." % opened, HUE_GOOD)
        for line in (gump_lines(opened) or [])[:12]:
            log("   gump text: %s" % line, HUE_INFO)

    if opened and ANSWER_GUMP:
        button = 1
        for gump_id, btn in (vendor.get("gump") or []):
            if gump_id == opened:
                button = btn
        log("answering gump 0x%X with button %d" % (opened, button), HUE_WARN)
        Gumps.SendAction(opened, button)
        Misc.Pause(2000)
    elif opened:
        log("ANSWER_GUMP is off - not accepting. Set it True to take the order.",
            HUE_INFO)
        try:
            Gumps.CloseGump(opened)
        except Exception:
            pass

    Misc.Pause(800)
    after_book = book_count()
    after_loose = loose_deeds()
    log("after : %s deed(s) in book, %d loose in pack"
        % ("?" if after_book is None else after_book, after_loose),
        HUE_GOOD if after_loose > before_loose else HUE_INFO)

    return (label, "ok", opened)


# =============================================================================
# MAIN
# =============================================================================

def main():
    rule("bulk order request diagnostic")
    log("Character: %s   ANSWER_GUMP=%s" % (Player.Name, ANSWER_GUMP), HUE_INFO)

    book = find_book()
    if book is None:
        log("No Bulk Order Book (graphic 0x%X) in your pack - deed counts will "
            "read as '?'." % BOD_BOOK_ID, HUE_WARN)
    else:
        log("Bulk Order Book 0x%X, %s deed(s) in it."
            % (book.Serial, "?" if book_count() is None else book_count()),
            HUE_GOOD)

    stops = vendor_stops(all_vendors())
    log("%d stop(s), %d NPC request(s):"
        % (len(stops), sum(len(s["vendors"]) for s in stops)), HUE_INFO)
    for stop in stops:
        log("   %s/%s : %s"
            % ("/".join(stop["folder"]), stop["point"],
               ", ".join(v["label"] for v in stop["vendors"])), HUE_INFO)

    results = []
    for stop in stops:
        rule("TRAVEL -> %s/%s" % ("/".join(stop["folder"]), stop["point"]))
        ok, detail = travel_to(stop["folder"], stop["point"])
        log("rune %s : %s" % (stop["point"],
                              detail if ok else "FAILED - %s" % detail),
            HUE_GOOD if ok else HUE_BAD)
        if not ok:
            for vendor in stop["vendors"]:
                results.append((vendor["label"], "travel failed", None))
            continue

        for vendor in stop["vendors"]:
            try:
                results.append(test_stop(vendor, travelled=True))
            except Exception as err:
                log("%s: raised %s: %s"
                    % (vendor["label"], type(err).__name__, err), HUE_BAD)
                results.append((vendor["label"], "error", None))
            Misc.Pause(800)

    rule("SUMMARY")
    for label, outcome, gump_id in results:
        hue = HUE_GOOD if outcome in ("ok", "not present") else HUE_BAD
        log("  %-22s %-20s %s"
            % (label, outcome, "gump 0x%X" % gump_id if gump_id else ""), hue)

    gumps_seen = sorted(set(g for _l, _o, g in results if g))
    if gumps_seen:
        log("gump ids seen: %s" % ", ".join("0x%X" % g for g in gumps_seen),
            HUE_INFO)
        log("Put these in each vendor's \"gump\" list in harvest_runner.py so "
            "every character behaves the same.", HUE_GOOD)

    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(_lines))
        Misc.SendMessage("[BOD] Written to %s" % DUMP_PATH, HUE_GOOD, False)
    except Exception as err:
        Misc.SendMessage("[BOD] Could not write dump: %s" % err, HUE_BAD, False)


main()
