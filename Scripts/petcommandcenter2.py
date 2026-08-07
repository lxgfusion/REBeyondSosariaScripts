"""
Pet Command Center 2 - deploy and shrink your pets by speaking a phrase.
========================================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

Say one phrase and every pet statue in your pack is released and told to guard.
Say another and the pets around you are shrunk back into your pack.

    #########################################################################
    ##  NEW HERE? SET  SETUP_MODE = True  BELOW AND RUN THE SCRIPT ONCE.   ##
    ##  It asks you to click each of your pet statues and your shrink      ##
    ##  tool, then prints a finished config block for you to paste in.     ##
    ##  You never have to read an item ID out of the inspector by hand.    ##
    #########################################################################

Everything you need to change is in the CONFIG block below, ordered by how
likely you are to change it. Nothing below "END OF CONFIG" needs editing.

What it does
------------
* DEPLOY phrase  - releases each configured pet statue from your backpack,
                   optionally saying something before each one, then issues a
                   single "all guard me" style command.
* RECALL phrase  - finds your tamed/bonded pets nearby and shrinks them with
                   your shrink tool, closest first.

Notes
-----
* Your journal is NOT wiped. This watches for new lines using a timestamp
  cursor, so it reacts once per phrase, ignores anything said before it
  started, and leaves other scripts' journal state alone.
* By default only YOUR OWN speech triggers it, so a passer-by cannot deploy
  your pets by repeating the phrase.
* Shrinking is done with a proper target cursor handshake. A leaked cursor
  silently eats the next target, which is why the tool is re-found and the
  cursor cleared before every single shrink.
"""

import math


SCRIPT_VERSION = "2.0.0"


# #############################################################################
# ##                                                                         ##
# ##                            C O N F I G                                  ##
# ##                                                                         ##
# ##  Section 1 is the only part most people need to touch.                  ##
# ##                                                                         ##
# #############################################################################

# =============================================================================
# 1. FIRST-TIME SETUP  -  turn this on, run once, paste what it prints.
# =============================================================================
#
# With this True the script does NOT listen for commands. Instead it asks you
# to target each pet statue in turn (and then your shrink tool), reads the ID
# and hue off them for you, and prints a ready-made PET_STATUES block.
#
# Copy that block over the one in section 3, set this back to False, and you
# are done. It also writes the same text to a file so you can copy-paste it.

SETUP_MODE = False


# =============================================================================
# 2. YOUR TRIGGER PHRASES  -  what you type in game to set things off.
# =============================================================================
#
# Matching is case-insensitive and matches anywhere in the line, so "Pets Go!"
# and "pets go!" both work. Pick something you will not say by accident.

DEPLOY_PHRASE = "anal demons unite!"     # release the statues, then guard
RECALL_PHRASE = "anal demons return!"    # shrink the pets back into the pack

# Only react to phrases YOU say. Leave True unless you want a guildmate to be
# able to trigger your pets - anyone repeating your phrase would set them off.
ONLY_MY_OWN_SPEECH = True


# =============================================================================
# 3. YOUR PET STATUES  -  the list SETUP_MODE writes for you.
# =============================================================================
#
#   label     Anything you like. It is what shows in the log, so make it
#             recognisable - it is what you see when a statue is missing.
#   id        The statue's Item ID.
#   hue       The statue's hue, or None for "any hue". Use None if you are not
#             sure: it still matches, it is just less specific. Only set a hue
#             when you carry two different statues that share an ID.
#   enabled   False parks an entry without deleting it.
#
# Add as many as you like - there is no five-pet limit.

PET_STATUES = [
    {"enabled": True, "label": "Pet 1", "id": 0x25AD, "hue": 0x0AB0},
    {"enabled": True, "label": "Pet 2", "id": 0x984A, "hue": 0x0776},
    {"enabled": True, "label": "Pet 3", "id": 0x25A5, "hue": 0x0481},
    {"enabled": True, "label": "Pet 4", "id": 0x429E, "hue": 0x0480},
    {"enabled": True, "label": "Pet 5", "id": 0x25B7, "hue": 0x0AB0},
]


# =============================================================================
# 4. YOUR SHRINK TOOL
# =============================================================================

SHRINK_TOOL_ID = 0x1374
SHRINK_TOOL_HUE = None       # None = any hue. Set one only if you carry two.

# How many pets to shrink per command, and how far to look for them.
SHRINK_MAX_PETS = 5
SHRINK_RANGE = 15            # tiles

# Optional safety net. Leave EMPTY to shrink any tamed/bonded pet nearby.
# Put names in it - matched case-insensitively, as substrings - and ONLY those
# are shrunk. Useful in a crowd, where the closest tamed creature may well be
# somebody else's pet standing between you and yours.
SHRINK_ONLY_THESE_NAMES = []


# =============================================================================
# 5. WHAT TO SAY  -  shard-specific commands. Set to "" to say nothing.
# =============================================================================

# Said once before EACH statue is used. On this shard "[e fart" is an emote;
# on yours it may be nothing at all. Blank it out if you do not want it.
SAY_BEFORE_EACH_RELEASE = "[e fart"

# Said once after every statue has been released.
SAY_AFTER_DEPLOY = "all guard me"

SPEECH_HUE = 33              # colour of the above, and of on-screen messages


# =============================================================================
# 6. TIMING  -  raise these if your shard lags. All values are milliseconds.
# =============================================================================

LISTEN_POLL_MS = 200         # how often to check for your phrase
RELEASE_PAUSE_MS = 800       # after using a statue, before the next
SHRINK_CURSOR_TIMEOUT = 3000 # how long to wait for the shrink target cursor
SHRINK_SETTLE_MS = 400       # after the cursor opens, before answering it
SHRINK_RESULT_MS = 1200      # after answering, before the next pet
PACK_REFRESH_MS = 1000       # how long to wait for backpack contents to reload

# Print extra detail about what is being found and skipped.
DEBUG = True


# #############################################################################
# ##                          END OF CONFIG                                  ##
# ##            Nothing below here needs editing to use the script.          ##
# #############################################################################

import os

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

SETUP_DUMP_PATH = os.path.join(os.environ.get("TEMP", "."),
                               "petcommandcenter_setup.txt")

_journal_cursor = 0.0
_setup_lines = []


# =============================================================================
# LOGGING
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Pets] " + text, hue, False)


def debug(text, hue=HUE_INFO):
    if DEBUG:
        log(text, hue)


def notify(text, hue=None):
    """On-screen message over the character, plus the journal."""
    try:
        Player.HeadMessage(SPEECH_HUE if hue is None else hue, text)
    except Exception:
        pass
    log(text, HUE_INFO)


def say(text):
    if not text:
        return
    try:
        Player.ChatSay(SPEECH_HUE, text)
    except TypeError:
        # Older builds only take ChatSay(msg).
        Player.ChatSay(text)


# =============================================================================
# CONFIG VALIDATION - a bad entry is named and skipped LOUDLY, never silently.
# =============================================================================

def valid_statues():
    """The usable PET_STATUES entries. Anything wrong is reported by name."""
    out = []
    seen = {}
    for index, entry in enumerate(PET_STATUES):
        where = entry.get("label") or "entry %d" % (index + 1)

        if not entry.get("enabled", True):
            debug("%s: disabled, skipping." % where, HUE_WARN)
            continue

        item_id = entry.get("id")
        if item_id is None:
            log("%s has no \"id\" - skipping it. Run SETUP_MODE to get one."
                % where, HUE_BAD)
            continue
        if not isinstance(item_id, int) or item_id <= 0:
            log("%s has a bad \"id\" (%r) - skipping it." % (where, item_id),
                HUE_BAD)
            continue

        hue = entry.get("hue")
        key = (item_id, hue)
        if key in seen:
            log("%s is a duplicate of %s (same id and hue) - skipping it."
                % (where, seen[key]), HUE_WARN)
            continue
        seen[key] = where

        out.append({"label": where, "id": item_id, "hue": hue})
    return out


def describe_hue(hue):
    return "any hue" if hue is None else "hue 0x%04X" % hue


def preflight():
    log("Pet Command Center v%s" % SCRIPT_VERSION, HUE_STEP)

    if Player.Backpack is None:
        log("No backpack found - cannot do anything.", HUE_BAD)
        return None

    statues = valid_statues()
    if not statues:
        log("No usable pet statues configured.", HUE_BAD)
        log("Set SETUP_MODE = True and run this again to build the list.",
            HUE_WARN)
        return None

    log("%d pet statue(s) configured:" % len(statues), HUE_GOOD)
    for entry in statues:
        log("   %-16s id 0x%04X, %s"
            % (entry["label"], entry["id"], describe_hue(entry["hue"])))

    log("Shrink tool: id 0x%04X, %s   (up to %d pet(s) within %d tiles)"
        % (SHRINK_TOOL_ID, describe_hue(SHRINK_TOOL_HUE),
           SHRINK_MAX_PETS, SHRINK_RANGE))
    if SHRINK_ONLY_THESE_NAMES:
        log("Only shrinking pets named: %s"
            % ", ".join(SHRINK_ONLY_THESE_NAMES), HUE_INFO)

    log("Say \"%s\" to deploy, \"%s\" to recall."
        % (DEPLOY_PHRASE, RECALL_PHRASE), HUE_GOOD)
    if ONLY_MY_OWN_SPEECH:
        log("Only your own speech will trigger this.", HUE_INFO)
    else:
        log("ONLY_MY_OWN_SPEECH is off - anyone saying the phrase can trigger "
            "your pets.", HUE_WARN)
    return statues


# =============================================================================
# BACKPACK LOOKUPS
#
# Item.Contains is a snapshot taken when the container was opened, and a
# container-scoped Items.FindByID walks that same snapshot. Once a statue is
# consumed the snapshot is stale, so the next lookup can miss an item that is
# genuinely there. Re-opening the pack and re-reading is the fix.
# =============================================================================

def refresh_pack():
    backpack = Player.Backpack
    if backpack is None:
        return None
    try:
        Items.WaitForContents(backpack, PACK_REFRESH_MS)
    except Exception:
        pass
    return backpack


def find_in_pack(item_id, hue, retry=True):
    """One item from the backpack by id and optional hue."""
    backpack = Player.Backpack
    if backpack is None:
        return None

    wanted_hue = -1 if hue is None else hue
    try:
        found = Items.FindByID(item_id, wanted_hue, backpack.Serial)
    except Exception as exc:
        debug("Lookup of 0x%04X failed: %s" % (item_id, exc), HUE_WARN)
        found = None

    if found is None and retry:
        # Could be a stale Contains snapshot rather than a missing item.
        refresh_pack()
        return find_in_pack(item_id, hue, retry=False)
    return found


# =============================================================================
# PET DISCOVERY
# =============================================================================

def distance_to(mobile):
    if not mobile:
        return float("inf")
    dx = Player.Position.X - mobile.Position.X
    dy = Player.Position.Y - mobile.Position.Y
    return math.sqrt(dx * dx + dy * dy)


def is_wanted_name(name):
    if not SHRINK_ONLY_THESE_NAMES:
        return True
    low = (name or "").lower()
    for wanted in SHRINK_ONLY_THESE_NAMES:
        wanted = wanted.strip().lower()
        if wanted and wanted in low:
            return True
    return False


def nearby_pets():
    """Tamed/bonded creatures in range, closest first."""
    found = []
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = SHRINK_RANGE        # never leave this unset
    f.IsHuman = False
    f.IsGhost = False
    f.CheckIgnoreObject = False

    for mob in Mobiles.ApplyFilter(f) or []:
        try:
            bonded = Mobiles.GetPropValue(mob, "bonded")
            tamed = Mobiles.GetPropValue(mob, "tamed")
        except Exception:
            continue
        if not (bonded or tamed):
            continue
        if not is_wanted_name(mob.Name):
            debug("Skipping %s - not in SHRINK_ONLY_THESE_NAMES."
                  % (mob.Name or "0x%X" % mob.Serial), HUE_WARN)
            continue
        found.append(mob)

    found.sort(key=distance_to)
    return found


# =============================================================================
# TARGET CURSOR
# =============================================================================

def clear_cursor():
    """Drop any stale target cursor.

    Target.WaitForTarget returns True for a cursor that is ALREADY open, so a
    leftover one silently swallows the next TargetExecute and the shrink looks
    like it simply did nothing.
    """
    try:
        Target.ClearQueue()
        if Target.HasTarget():
            Target.Cancel()
            Misc.Pause(200)
            Target.ClearQueue()
        return not Target.HasTarget()
    except Exception:
        return False


# =============================================================================
# ACTIONS
# =============================================================================

def deploy(statues):
    """Release every configured statue, then issue the guard command."""
    notify("Deploying pets...")
    refresh_pack()

    released = 0
    missing = []
    for entry in statues:
        statue = find_in_pack(entry["id"], entry["hue"])
        if statue is None:
            missing.append(entry["label"])
            continue

        say(SAY_BEFORE_EACH_RELEASE)
        try:
            Items.UseItem(statue.Serial)
        except Exception as exc:
            log("%s: could not use the statue (%s)." % (entry["label"], exc),
                HUE_BAD)
            continue
        released += 1
        debug("%s released." % entry["label"], HUE_GOOD)
        Misc.Pause(RELEASE_PAUSE_MS)

    if missing:
        log("Not in your pack: %s" % ", ".join(missing), HUE_WARN)

    if released:
        say(SAY_AFTER_DEPLOY)
        notify("Deployed %d pet(s)." % released, HUE_GOOD)
    else:
        notify("No pet statues found in your pack!", HUE_BAD)
        log("Check section 3, or set SETUP_MODE = True to rebuild the list.",
            HUE_WARN)
    return released


def shrink_one(pet):
    """One tool-use plus target handshake. True if it was sent."""
    tool = find_in_pack(SHRINK_TOOL_ID, SHRINK_TOOL_HUE)
    if tool is None:
        return None                  # caller reports the missing tool once

    if not clear_cursor():
        log("A target cursor is stuck open - cannot shrink cleanly.", HUE_BAD)
        return False

    try:
        Items.UseItem(tool.Serial)
    except Exception as exc:
        log("Could not use the shrink tool (%s)." % exc, HUE_BAD)
        return False

    if not Target.WaitForTarget(SHRINK_CURSOR_TIMEOUT, False):
        log("The shrink tool did not ask for a target.", HUE_WARN)
        clear_cursor()               # or it survives into the next attempt
        return False

    Misc.Pause(SHRINK_SETTLE_MS)
    Target.TargetExecute(pet.Serial)
    Misc.Pause(SHRINK_RESULT_MS)
    return True


def recall():
    """Shrink the nearest pets back into the pack."""
    notify("Recalling pets...")
    refresh_pack()

    if find_in_pack(SHRINK_TOOL_ID, SHRINK_TOOL_HUE) is None:
        notify("Shrink tool not found in your pack!", HUE_BAD)
        log("Expected id 0x%04X, %s. Set SETUP_MODE = True to re-read it."
            % (SHRINK_TOOL_ID, describe_hue(SHRINK_TOOL_HUE)), HUE_WARN)
        return 0

    pets = nearby_pets()
    if not pets:
        notify("No tamed pets found within %d tiles!" % SHRINK_RANGE, HUE_WARN)
        return 0

    debug("%d pet(s) in range; shrinking up to %d."
          % (len(pets), SHRINK_MAX_PETS))

    shrunk = 0
    for pet in pets[:SHRINK_MAX_PETS]:
        label = pet.Name or "0x%X" % pet.Serial
        result = shrink_one(pet)
        if result is None:
            log("Ran out of shrink tool after %d pet(s)." % shrunk, HUE_WARN)
            break
        if result:
            shrunk += 1
            debug("Shrank %s." % label, HUE_GOOD)
        else:
            log("Could not shrink %s." % label, HUE_WARN)

    notify("Shrunk %d pet(s)!" % shrunk, HUE_GOOD if shrunk else HUE_WARN)
    return shrunk


# =============================================================================
# SETUP MODE - builds the config for you so nobody has to read hex by hand.
# =============================================================================

def setup_line(text, hue=HUE_INFO):
    log(text, hue)
    _setup_lines.append(text)


def ask_for_item(prompt):
    """Prompt for one item. None if the user cancelled."""
    log(prompt, HUE_STEP)
    try:
        serial = Target.PromptTarget(prompt, SPEECH_HUE)
    except Exception as exc:
        log("Targeting failed: %s" % exc, HUE_BAD)
        return None
    if not serial or serial <= 0:
        return None
    item = Items.FindBySerial(serial)
    if item is None:
        log("That was not an item Razor can read - try again.", HUE_WARN)
        return None
    return item


def run_setup():
    log("SETUP MODE - nothing will be deployed or shrunk.", HUE_STEP)
    log("Click each PET STATUE in your pack, one at a time.", HUE_INFO)
    log("Press ESC (cancel the target) when you have done them all.", HUE_INFO)

    entries = []
    while True:
        item = ask_for_item("Target pet statue #%d (ESC when finished)"
                            % (len(entries) + 1))
        if item is None:
            break
        label = item.Name or "Pet %d" % (len(entries) + 1)
        entries.append((label, item.ItemID, item.Hue))
        log("   got %s - id 0x%04X, hue 0x%04X"
            % (label, item.ItemID, item.Hue), HUE_GOOD)

    if not entries:
        log("No statues targeted, so there is nothing to write.", HUE_WARN)

    log("", HUE_INFO)
    tool = ask_for_item("Now target your SHRINK TOOL (ESC to skip)")

    # Build the paste-ready block.
    del _setup_lines[:]
    setup_line("", HUE_INFO)
    setup_line("=" * 60, HUE_STEP)
    setup_line("COPY THE LINES BELOW INTO SECTION 3 AND 4, THEN SET "
               "SETUP_MODE = False", HUE_STEP)
    setup_line("=" * 60, HUE_STEP)
    setup_line("")
    setup_line("PET_STATUES = [")
    for label, item_id, hue in entries:
        safe = (label or "").replace('"', "'")
        setup_line('    {"enabled": True, "label": "%s", '
                   '"id": 0x%04X, "hue": 0x%04X},' % (safe, item_id, hue))
    setup_line("]")
    setup_line("")
    if tool is not None:
        setup_line("SHRINK_TOOL_ID = 0x%04X" % tool.ItemID)
        setup_line("SHRINK_TOOL_HUE = 0x%04X" % tool.Hue)
        setup_line("")
        setup_line("# If the tool is not found later, try SHRINK_TOOL_HUE = "
                   "None (any hue).")
    else:
        setup_line("# Shrink tool skipped - section 4 left as it was.")
    setup_line("")
    setup_line("=" * 60, HUE_STEP)

    try:
        with open(SETUP_DUMP_PATH, "w") as fh:
            fh.write("\n".join(_setup_lines))
        log("Also written to %s" % SETUP_DUMP_PATH, HUE_GOOD)
        log("Open that file and copy from there - easier than the journal.",
            HUE_INFO)
    except Exception as exc:
        log("Could not write %s (%s) - copy from the journal instead."
            % (SETUP_DUMP_PATH, exc), HUE_WARN)


# =============================================================================
# LISTENING
#
# A timestamp cursor, not Journal.Search + Journal.Clear. Search scans the whole
# buffer, so a phrase said an hour ago keeps matching until the journal is
# wiped - and wiping it breaks every other script the user is running. Reading
# only entries newer than a cursor fires once per phrase and touches nothing.
# =============================================================================

def start_listening():
    """Set the cursor past everything already in the journal."""
    global _journal_cursor
    newest = 0.0
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            if entry.Timestamp > newest:
                newest = entry.Timestamp
    except Exception:
        pass
    _journal_cursor = newest


def spoken_by_me(entry):
    if not ONLY_MY_OWN_SPEECH:
        return True
    try:
        return (entry.Name or "").strip().lower() == \
               (Player.Name or "").strip().lower()
    except Exception:
        return False


def poll_phrases():
    """Which trigger phrases appeared since the last poll.

    Only raises flags - it never acts. Safe to call from anywhere, including
    inside a long pause.
    """
    global _journal_cursor
    hits = []
    try:
        entries = Journal.GetJournalEntry(_journal_cursor) or []
    except Exception:
        return hits

    for entry in entries:
        try:
            stamp = entry.Timestamp
        except Exception:
            continue
        if stamp <= _journal_cursor:
            continue
        _journal_cursor = max(_journal_cursor, stamp)

        text = (entry.Text or "").lower()
        if not text or not spoken_by_me(entry):
            continue

        # A human types a phrase differently every time, so match loosely.
        if DEPLOY_PHRASE and DEPLOY_PHRASE.strip().lower() in text:
            hits.append("deploy")
        elif RECALL_PHRASE and RECALL_PHRASE.strip().lower() in text:
            hits.append("recall")
    return hits


# =============================================================================
# MAIN
# =============================================================================

def main():
    if SETUP_MODE:
        log("Pet Command Center v%s" % SCRIPT_VERSION, HUE_STEP)
        run_setup()
        return

    statues = preflight()
    if statues is None:
        return

    start_listening()
    log("Listening. Say your phrase in game.", HUE_GOOD)

    while True:
        Misc.Pause(LISTEN_POLL_MS)      # never busy-wait

        if Player.Backpack is None:
            continue

        for hit in poll_phrases():
            if hit == "deploy":
                deploy(statues)
            elif hit == "recall":
                recall()


main()
