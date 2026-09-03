"""
Harvest runner - mining and lumberjacking on one script.
========================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

Original mining and lumberjacking scripts by Cral, modified by the user. This
merges them so both run from one script, sharing the account-runebook travel,
mana management, drop-off runs, vendor round and Greyskull call-out.

How it works
------------
JOBS lists the harvesting jobs. Each names a runebook folder and a task
("mine" or "lumber"). The script works a job until the pack fills, drops off,
then moves to the next job. Everything else - travel, meditation, vendors, the
Greyskull response - is shared and happens around whichever job is running.

Set a job's "enabled" to False to run only the other one; the script behaves
exactly like the single-purpose version it came from.

What changed from the two originals
-----------------------------------
* One runebook navigator, page-aware, shared by both jobs. Confirmed buttons:
  504 next page, 503 previous, 5 root, 0 close.
* Route and waypoint state is per-job, so mining and lumber keep their own
  positions in their own folders.
* One weight check. The lumberjack version (find the "Contents" tooltip line)
  is more robust than indexing tooltip line 2, and is used for both, with the
  old index-2 method as a fallback.
* One key-restock routine covering both scripts' key types.
* Player.UnEquipItemByLayer's second argument is a BOOLEAN (wait), not a
  timeout - the original passed 5000.
* Item names can be null; the original axe search would throw on those.

Diagnostics: diag_ar_gump.py, diag_vendors.py, diag_journal.py.
"""

import os
import re
import time

Misc.Pause(5000)


# Printed as the first line at startup. Bump it with every change that goes
# out, so the journal says which copy Razor actually loaded - Razor caches the
# loaded script even after the file on disk changes. If this line does not say
# what you expect, hit Reload in the Scripting tab.
#
# This script has FOUR copies that differ on purpose (repo, main character,
# MrGatherer, Mystic Gatherer). Give each a distinct SCRIPT_TAG so the banner
# also says which copy is running, not just which version.
SCRIPT_VERSION = "2026-08-29.22"
SCRIPT_TAG = "repo"


# #############################################################################
# ##   DIAGNOSTIC MODE                                                       ##
# #############################################################################
# Set True to walk every job's whole route once, harvesting one swing at each
# rune and printing exactly what the server replies, then stop. Nothing rotates,
# no vendor round, no drop-off. Use it to find where a job is failing; set back
# to False for normal running.
#
# The trace is written to %TEMP%\harvest_diag.txt and the path is printed at the
# end - send that file back.
DIAGNOSTIC_MODE = False
DIAGNOSTIC_DUMP = os.path.join(os.environ.get("TEMP", "."), "harvest_diag.txt")

# Crash reporting. A Razor script that raises prints one line and stops, and
# the traceback is gone before you can read it - which is why "it crashes
# sometimes" has been impossible to act on.
#
# Everything below the HELPERS banner is wrapped in a handler that writes the
# FULL traceback, the last CRASH_TRAIL log lines, and the state that matters,
# to this file AND to the journal. The file is per character, so several
# running at once do not overwrite each other.
CRASH_REPORT = True
CRASH_TRAIL = 40

# Collapse identical log lines repeated inside this window, and cap how many
# lines a second may be sent at all.
#
# THIS IS NOT ABOUT TIDINESS. Misc.SendMessage is delivered by INJECTING a
# packet into the client through the plugin receive path, so every log line is
# network pressure on ClassicUO's receive buffer. MrGatherer's crash log is:
#
#   System.ArgumentException: Argument_DestinationTooShort
#     ClassicUO.Network.CircularBuffer.Enqueue
#     ClassicUO.Network.PacketHandlers.Append
#     ClassicUO.Network.Plugin.OnPluginRecv_new
#
# - the plugin handing the client more than its buffer could take. A burst of
# identical lines is the shape that does it: pack_has_room() is a QUERY called
# several times per key inside refill_keys and once per swing in the sweeps,
# and it announced itself every single time.
#
# Set LOG_DEDUPE_MS = 0 to see every line again.
LOG_DEDUPE_MS = 4000
LOG_MAX_PER_SECOND = 12


# #############################################################################
# ##                                                                         ##
# ##                         C O N F I G U R A T I O N                       ##
# ##                                                                         ##
# ##  EVERYTHING you need to set is between here and the HELPERS banner.     ##
# ##  Nothing below HELPERS needs editing to run the script.                 ##
# ##                                                                         ##
# ##  Headings below, in the order they appear - search for the one you want:##
# ##                                                                         ##
# ##    JOBS ................ which jobs run, their runebook folders and     ##
# ##                          how they rotate                                ##
# ##    WOOD STORAGE ........ the key that swallows logs and boards          ##
# ##    INGOT KEY ........... the same thing for ingots                      ##
# ##    VENDORS ............. every NPC the script talks to                  ##
# ##    GREYSKULL CALL-OUT .. the chat phrase that summons you               ##
# ##    DROP-OFF ............ home chest, and how often to go                ##
# ##    HOUSE DEPOSITS ...... order books emptied on every drop-off          ##
# ##    BULK ORDER DEEDS .... the BOD book and what may go in it             ##
# ##    MINING .............. shovel, tinker tools, forge, ore               ##
# ##    LUMBERJACKING ....... axes                                           ##
# ##    TRAVEL AND MANA ..... runebook buttons, recall, meditation           ##
# ##    LOGGING AND PACING .. debug output and journal colours               ##
# ##    SERVER MESSAGES ..... shard text the script reads. Change only if    ##
# ##                          your shard words things differently            ##
# ##                                                                         ##
# ##  PER-CHARACTER SETTINGS - the ones that differ between copies of this   ##
# ##  script, and the first things to check when a copy misbehaves:          ##
# ##                                                                         ##
# ##      WOOD_STORAGE_SERIAL     each character carries their own key       ##
# ##      DROP_CHEST_SERIAL       whose house the drop-off is at             ##
# ##      BOD_BOOK_SERIAL         or BOD_BOOK_BY_CHARACTER, keyed by name    ##
# ##      the runebook folder and rune names in JOBS, DROP_FOLDER,           ##
# ##      ARCANE_FOLDER and the VENDORS entries                              ##
# ##                                                                         ##
# ##  INGOT_KEY_SERIAL is deliberately 0 so that one copy works for every    ##
# ##  character - it finds whichever ingot key is in that character's pack.  ##
# ##                                                                         ##
# #############################################################################


# #############################################################################
# ##                                                                         ##
# ##   EDIT THIS FIRST - JOBS AND VENDORS                                    ##
# ##                                                                         ##
# #############################################################################
#
# JOBS - what to harvest, in the order it should be worked.
#
#   enabled  False skips the job entirely.
#   name     Label used in the log.
#   folder   Runebook folder holding that job's runes, e.g. ['Mining'].
#            Use ['Outer', 'Inner'] for a nested folder.
#   task     "mine" or "lumber" - which harvesting routine to run.

JOBS = [
    {
        "enabled": True,
        "name":    "Mining",
        "folder":  ['Mining'],
        "task":    "mine",
    },
    {
        "enabled": True,
        "name":    "Lumberjacking",
        "folder":  ['Lumber'],
        "task":    "lumber",
    },
]

# When to move to the next job:
#   "route"    after working every rune in the job's folder once (DEFAULT)
#   "dropoff"  after each drop-off run
#   "timer"    every JOB_TIME_MS
#   "never"    stay on the first enabled job forever
#
# Use "route". Wood is far heavier than ore, so a lumber run fills the pack after
# one or two trees; with "dropoff" the job rotated away after a single waypoint
# and the rest of the route was never visited. With "route" the script goes home,
# unloads, comes back to the SAME spot and carries on, however many trips that
# takes, and only moves to the next job once the whole route is done.
JOB_ROTATION = "route"
JOB_TIME_MS = 30 * 60 * 1000

# Unload before switching jobs.
#
# Leave this on. Mining finishes its route with a couple of hundred stones of
# ore still in the pack, and the wood storage only takes wood - so lumberjacking
# inherited that dead weight, had barely two chops of headroom before hitting
# the threshold, and spent the whole route in a full/unload cycle instead of
# actually chopping.
DROPOFF_BETWEEN_JOBS = True


# -----------------------------------------------------------------------------
# WOOD STORAGE - where the thing that swallows your wood actually is.
#
#   "world"  locked down somewhere at the drop-off house.
#   "pack"   carried in your backpack.
#
# This only controls how it is SEARCHED FOR when the serial lookup fails. Where
# it actually is decides behaviour: if the script finds the storage in your
# pack it empties there and then and never travels to the drop-off, whatever
# this is set to. Carry the key and lumber runs go start to finish in one trip.
#
# Serial is used first; the id/hue below are the fallback if it is replaced.
WOOD_STORAGE_WHERE = "pack"
# ZERO in the repo copy ON PURPOSE - this is the copy that goes to GitHub, and
# a real character's item serial has no business being published. Each live
# copy carries its own character's serial, set by hand; do not copy one here.
#
# Zero is also a working default: the graphic plus any hue plus the name check
# finds whichever wood storage is in that character's pack.
WOOD_STORAGE_SERIAL = 0
WOOD_STORAGE_ID = 0x1BD9         # graphic, used when the serial is gone
WOOD_STORAGE_HUE = -1            # -1 accepts ANY colour; see the note below
WOOD_STORAGE_RANGE = 12          # tiles, only used when "world"

# The hue used to be pinned to 0x0058, which meant a key of any other colour
# was simply not found and the wood went to the chest instead. It is -1 now, so
# colour is ignored - but hue was also the only thing separating the key from
# an ordinary item of the same graphic, so NAMES takes over that job. An item
# only counts as the storage if its name or tooltip contains one of these.
#
# Leave it [] to accept anything of the right graphic whatever it is called.
WOOD_STORAGE_NAMES = ["wood storage", "storage", "key"]

# -----------------------------------------------------------------------------
# INGOT KEY - the mining equivalent of the Wood Storage, and the same options.
#
#   "world"  locked down somewhere at the drop-off house.
#   "pack"   carried in your backpack.
#
# As with the Wood Storage this only controls how it is SEARCHED FOR. Where it
# actually is decides behaviour: found in your pack, the ingots go into it on
# the spot and the character never travels to the drop-off. Carry the key and a
# mining run goes start to finish in one trip - which matters more than it used
# to, now that a rune is worked as a whole area rather than a single spot.
#
# Smelting happens first either way: the key takes INGOTS, not ore.
#
# ENABLED False sends ingots to the drop chest instead, as the original did.
INGOT_KEY_ENABLED = True

# Serial is used first; the id/hue below are the fallback if it is replaced.
INGOT_KEY_WHERE = "pack"
# Left EMPTY on purpose, exactly like WOOD_STORAGE_SERIAL. Each character
# carries their OWN key, so a serial here would be right for one copy of this
# script and would resolve to somebody else's key - or to nothing - in every
# other. The graphic with any hue plus the name check below finds whichever
# ingot key is in THIS character's pack, and needs no per-character editing.
# Inspected 2026-08-11: "Ingot Keys", 0x405B2105, ItemID 0x1BE8, hue 0x0014,
# Blessed, carried in the pack.
INGOT_KEY_SERIAL = 0
INGOT_KEY_ID = 0x1BE8
INGOT_KEY_HUE = -1               # -1 accepts ANY colour; see the note below
INGOT_KEY_RANGE = 12             # tiles, only used when "world"

# The same job WOOD_STORAGE_NAMES does. Hue used to be what told a key apart
# from anything else sharing its graphic; with hue ignored so that a key of any
# colour is found, the NAME takes that job over. An item only counts as the
# ingot key if its name or tooltip contains one of these.
#
# Leave it [] to accept anything of the right graphic whatever it is called.
INGOT_KEY_NAMES = ["ingot key", "ingot keys", "key"]

# -----------------------------------------------------------------------------
# STONE STORAGE - the granite equivalent, and the same options again.
#
# Granite is what mining gives you besides ore, and it is HEAVY. Without this
# it goes to the drop chest, which is a ONE-WAY trip - see KEY_BACKED_IDS.
#
# Inspected 2026-08-18: "Stone Storage", ItemID 0xA54A, hue 0x0000, Blessed,
# carried in the pack. The serial is per-character and is set live, not here -
# this copy is published, so it ships zeroed like every other serial in it.
#
# This graphic was already in RESTOCK_KEYS as an unlabelled "Key (alt)" entry,
# so it was being single-clicked without anyone knowing what it was - and
# without granite being protected from the chest sweep.
#
# ONLY ONE CHARACTER MINES STONE. Everyone else ships ENABLED = False with no
# serial: the key is theirs alone, and a graphic lookup on somebody else's
# copy would find nothing anyway.
STONE_STORAGE_ENABLED = False

# Serial is used first; the id/hue below are the fallback if it is replaced.
STONE_STORAGE_WHERE = "pack"
STONE_STORAGE_SERIAL = 0
STONE_STORAGE_ID = 0xA54A
STONE_STORAGE_HUE = -1           # -1 accepts ANY colour
STONE_STORAGE_RANGE = 12         # tiles, only used when "world"

# The same job the other two NAMES lists do - with the hue ignored, the name
# is what tells this key apart from anything else of its graphic.
STONE_STORAGE_NAMES = ["stone storage", "storage", "key"]

# Break off and move to the next rune if something hostile is close.
#
# HOSTILE_RANGE is not optional. Leaving it unbounded meant any wandering spawn
# anywhere in view counted, so the check was permanently true and the script
# skipped straight through every remaining rune on the route.
ABORT_ON_HOSTILES = True
HOSTILE_RANGE = 8                          # tiles
HOSTILE_NOTORIETIES = [4, 5, 6]            # criminal, enemy, murderer

# After this many waypoints skipped back-to-back for hostiles, harvest anyway.
# Otherwise a permanently populated area burns through the whole route without
# a single swing and the job "finishes" having done nothing.
HOSTILE_SKIP_LIMIT = 3


# -----------------------------------------------------------------------------
# VENDORS - every NPC the script talks to. If a vendor is being skipped, this
# table is almost always why.
#
#   label    Name used in the log.
#   folder   Runebook folder path to the rune.
#   point    Rune name, matched case-insensitively as a substring.
#   names    Matched case-insensitively as SUBSTRINGS against the NPC's name
#            AND its tooltip properties. Vendor titles usually live in the
#            tooltip, not the name - "Sherri" is the Animal Trainer, "Edie" is
#            the Scribe - so matching on the title is more durable than on a
#            given name the shard may change. List several; first match wins.
#   context  Context-menu entries tried in order until one is accepted.
#   gump     Optional gump to answer after the menu. Either (gumpid, buttonid)
#            or a LIST of them tried in order - large and small bulk orders can
#            use different gump ids. None if the NPC opens no gump.
#
# Run Scripts/diag_vendors.py beside an NPC for its real name and entries.
# Set "enabled": False to skip a stop without deleting it.

# =============================================================================
# ONE SWITCH FOR ALL BULK ORDER DEEDS
# =============================================================================
# False turns off EVERYTHING to do with bulk orders and nothing else:
#
#   * every BOD_LOCATIONS x BOD_PROFESSIONS stop (smith, scribe, tailor,
#     tinker, carpenter)
#   * the "Carpenter" entry in VENDORS below, which is a BOD vendor that
#     happens to live in this table rather than the BOD one
#   * filing deeds into the Bulk Order Book, and the book's startup report
#
# Resource Orders and Taming Deeds are NOT bulk orders and keep running. They
# are the two entries below without "bod": True.
#
# Turning this off is a real saving: the BOD tables expand to five stops, each
# one a recall, a walk and a context menu, on every vendor round.
BOD_ENABLED = True


VENDORS = [
    {
        "enabled": True,
        "label":   "Resource Orders",
        "folder":  ['RO'],
        "point":   'RO',
        # Inspected: name "Davin the Resource Gatherer", no tooltip.
        "names":   ["Resource Gatherer"],
        "context": ["Talk"],
        "gump":    None,
        # Measured: one order every 30 minutes, not the 3-per-6-hours the bulk
        # order professions use.
        "per_window": 1,
        "window_ms":  30 * 60 * 1000,
    },
    {
        "enabled": True,
        "label":   "Taming Deeds",
        "folder":  ['BOD'],
        "point":   'tameinscribe',          # rune at 1479, 1790
        # Inspected: name "Sherri", tooltip "Animal Trainer" / "Quest Giver".
        "names":   ["Animal Trainer"],
        "context": ["Talk"],
        "gump":    None,
    },
    # The carpenter is served from HERE, not from the BOD tables below - see the
    # disabled "Carpenter rune" entry in BOD_LOCATIONS for why. This is the copy
    # with inspected data, so it is the one that survived de-duplication.
    {
        "enabled": True,
        # A BULK ORDER vendor, so BOD_ENABLED = False removes it with the rest
        # even though it is listed here rather than in BOD_LOCATIONS.
        "bod":     True,
        "label":   "Carpenter",
        "folder":  ['BOD'],
        "point":   'carpenter',          # rune at 1479, 1790
        # Inspected: name "Mallory", tooltip "Carpenter" / "Quest Giver".
        "names":   ["Carpenter"],
        # Only "Bulk Order Info" - no "Talk" fallback, unlike the smith and
        # scribe. That is deliberate, from the inspector dump.
        "context": ["Bulk Order Info"],
        # NOT YET VERIFIED IN GAME: this says the carpenter opens no gump at
        # all, unlike the smith and scribe which both open one. If it turns out
        # a bulk order window DOES open, this must become
        #     [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)]
        # like BOD_PROFESSIONS["carpenter"] has - because with None the script
        # reports "collected" without answering anything, and leaves the window
        # open for the next vendor to trip over.
        "gump":    None,
    },
]


# #############################################################################
# ##   BULK ORDER ROUNDS - WHO to ask, and WHERE they stand                  ##
# #############################################################################
#
# Bulk order NPCs are listed as two small tables instead of one long list,
# because the same four or five professions appear at every town. Write a
# profession ONCE, then just name the runes it can be found at.
#
# The script expands these into stops, travels to each rune once, and asks
# every profession standing there - one order from each NPC per visit.

# WHO. The key is your own shorthand; only the values matter.
#   names    Matched against the NPC's name AND tooltip, case-insensitive.
#            Use the TOOLTIP TITLE from the Enhanced Mobile Inspector.
#   context  Menu entries, tried in order. Exact wording from diag_bods.py.
#   gump     [(gump id, button), ...] the NPC opens. None if it opens none.
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
        # Inspected: "Mallory", tooltip "Carpenter" / "Quest Giver".
        # NOT REACHED from here - the carpenter is served by the VENDORS entry,
        # and the "Carpenter rune" location below is disabled. Left in place so
        # a "*" rune can still pick a carpenter up. Note this keeps the gump
        # list the VENDORS entry drops to None; see the note there.
        "names":   ["Carpenter"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
    "tinker": {
        # NOT INSPECTED YET - "Tinker" is a guess at the tooltip title.
        "names":   ["Tinker"],
        "context": ["Bulk Order Info", "Bulk Order", "Talk"],
        "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
    },
}

# WHERE. One entry per rune in the runebook.
#
#   folder / point   Exactly as [ar shows them, same rules as VENDORS.
#   who              Which professions to ask for at that rune. Either a list
#                    of BOD_PROFESSIONS keys, or the string "*".
#
#                    A LIST means "these should be here" - if one is missing
#                    the log calls it out, because that is probably a bad rune.
#
#                    "*" means "ask whoever happens to be here" - every
#                    profession is tried and anyone absent is skipped QUIETLY.
#                    Use it for town runes where you have not catalogued who
#                    stands where. It costs nothing extra: the NPC scan runs
#                    once per rune, not once per profession.
BOD_LOCATIONS = [
    {"enabled": True,  "label": "Smith rune",     "folder": ['BOD'],
     "point": 'Blacksmith',   "who": ["blacksmith"]},          # 1418, 1548

    {"enabled": True,  "label": "Tame+Inscribe",  "folder": ['BOD'],
     "point": 'tameinscribe', "who": ["scribe"]},               # 1479, 1790

    {"enabled": True,  "label": "Tailor rune",    "folder": ['BOD'],
     "point": 'Tailor',       "who": ["tailor"]},               # 1470, 1688

    {"enabled": True,  "label": "Tinker rune",    "folder": ['BOD'],
     "point": 'tinker',       "who": ["tinker"]},               # 1434, 1659
    #                          ^ the tailor and tinker tooltip titles are still
    #                            guesses (see BOD_PROFESSIONS). Both are live
    #                            anyway: a wrong title just means "No NPC
    #                            matching [...]" in the log plus a dump of who
    #                            IS standing there, which is how to confirm it.

    # Carpenter is served by the "Carpenter" entry in VENDORS instead, which
    # carries the inspected name/tooltip and its own context list. Kept here,
    # disabled, so the rune is on record - do not enable both, or Mallory gets
    # asked twice every round off one 3-per-6-hours budget.
    #
    # The casing below is already corrected: BOD_PROFESSIONS keys are lowercase,
    # so the "Carpenter" this shipped with matched nothing and the stop was
    # silently dead.
    {"enabled": False, "label": "Carpenter rune", "folder": ['BOD'],
     "point": 'carpenter',    "who": ["carpenter"]},            # 1479, 1790

    # To cover a whole town without cataloguing it, add the rune with "*":
    # {"enabled": True, "label": "Britain", "folder": ['BOD'],
    #  "point": 'Britain', "who": "*"},
]

# The NPC is on its per-order timer. Not an error, and not worth retrying -
# ServUO says 1072058 / 1049039 "An offer may be available in about N ...".
BOD_COOLDOWN_MESSAGES = [
    "An offer may be available in about",
    "You'll have to wait a few seconds",     # 1079976, still inspecting
]

# HOW OFTEN A VENDOR IS WORTH VISITING.
#
# Measured on Beyond Sosaria: 3 orders per profession per 360 minutes, and the
# resource gatherer gives 1 per 30 minutes. The vendor round itself runs every
# VENDOR_INTERVAL_MS (30 min), so without this the script would recall to every
# bulk order NPC twelve times per refresh and be turned away eleven times.
#
# A stop is skipped entirely when nothing standing there is due, so the travel
# is skipped too - not just the conversation.
#
# These are the defaults; a profession or a VENDORS entry can override them with
# its own "per_window" and "window_ms".
BOD_REQUESTS_PER_WINDOW = 3
BOD_WINDOW_MS = 360 * 60 * 1000          # 6 hours

# When an NPC says "An offer may be available in about 45 minutes", believe it -
# that beats any hardcoded guess and adapts to whatever the shard uses. Turn off
# only if the wording is being misread.
BOD_TRUST_REPORTED_WAIT = True

# Everything is forgotten when the script restarts. That is fine: the first
# round asks, the server reports the real wait, and scheduling resumes from
# there.

# -----------------------------------------------------------------------------
# ADDING A VENDOR - copy this block into VENDORS above and fill it in.
#
#     {
#         "enabled": True,
#         "label":   "Carpenter Orders",
#         "folder":  ['BOD'],
#         "point":   'Carpenter',
#         "names":   ["Carpenter"],
#         "context": ["Bulk Order Info", "Bulk Order", "Talk"],
#         "gump":    [(0x9BADE6EA, 1), (0xBE0DAD1E, 1)],
#     },
#
# WHERE EACH VALUE COMES FROM
#
# "enabled"  True to visit it. False parks the entry without deleting it -
#            use this while a new stop is still unverified.
#
# "label"    Anything you like. It is only used in the log, so make it
#            recognisable: it is what you will see when a stop fails.
#
# "folder"   The runebook FOLDER, exactly as the [ar gump shows it.
#            Type [ar in game, and read the folder list on the root page.
#            Ours are: Trammel, Ilshenar, Malas, Tokuno, TerMur, Homes,
#            Taming Locations, Mining, RO, BOD, Lumber, ...
#            Nested folders are a list: ['Work', 'BOD'].
#            Matching is case-insensitive, and an EXACT name always beats a
#            partial one - so 'BOD' will not accidentally open 'BODs Old'.
#
# "point"    The RUNE inside that folder, again exactly as [ar shows it.
#            Open the folder in [ar and read the numbered list. Ours in BOD:
#                1. Tailor        (1470, 1688, 0)
#                2. Blacksmith    (1418, 1548, 30)
#                3. tameinscribe  (1479, 1790, 2)
#            CHECK THE COORDINATES against where the NPC actually stands -
#            that is how the blacksmith stop was found to be pointing at the
#            wrong rune, 240 tiles from Cara. VENDOR_RANGE is only 12 tiles.
#            Two vendors CAN share a rune: give them the same folder+point and
#            the script travels there once and serves both.
#
# "names"    How to recognise the NPC. Matched case-insensitively as a
#            SUBSTRING against the NPC's name AND its tooltip.
#            Use Razor's Enhanced Mobile Inspector on the NPC:
#                Name:       Cara            <- often just a first name
#                Attributes: Blacksmith      <- THE TITLE. USE THIS.
#            Prefer the title. Names get changed by the shard - "Sahale the
#            scribe" became "Edie" - but the title stays. Avoid short generic
#            words: "Cara" could match another NPC's name or tooltip.
#            A list is allowed; the first match wins.
#
# "context"  The right-click menu entries to try, in order, until one is
#            accepted. Get the exact wording from diag_bods.py or
#            diag_vendors.py, which print the whole menu:
#                Sherri: Open Paperdoll | Stable Pet | Talk | Buy | Sell | ...
#                Edie:   Open Paperdoll | Bulk Order Info | Bribe | ...
#            USE THE EXACT LABEL. An exact match is always honoured; a partial
#            one is refused if it hits CONTEXT_NEVER (buy, sell, bribe,
#            open bankbox, train ) - those all cost gold and sit on the same
#            menu.
#
# "gump"     What the NPC opens afterwards, as a list of (gump id, button).
#            None if it opens nothing - the resource gatherer and the animal
#            trainer do not.
#            Get the id from diag_bods.py, which reports every gump that
#            opens, or from Razor's Enhanced Gump Inspector: the "Gump ID"
#            line when the window appears, and "Gump Button" when you click
#            Accept by hand.
#            It is a LIST because one NPC can open different windows - a SMALL
#            bulk order gives 0x9BADE6EA and a LARGE one 0xBE0DAD1E. If an
#            unexpected id shows up the log names it so you can add it.
#
# AFTER ADDING ONE
#     1. Run diag_bods.py with ANSWER_GUMP = False. It travels to every stop,
#        lists the NPCs actually in range with their titles and distances, and
#        reports which gump opened - without accepting anything.
#     2. Fix anything it flags, then set ANSWER_GUMP = True and rerun.
#     3. Copy the finished VENDORS block to your other characters.
# -----------------------------------------------------------------------------

# How long to wait for a vendor's follow-up gump, and how many times to redo the
# whole context-menu interaction if it never shows.
VENDOR_GUMP_TIMEOUT = 8000
VENDOR_RETRIES = 2

# Tiles to search for a vendor once the rune lands. Bounded on purpose: an
# unset range means every mobile the client knows about, roughly 18-25 tiles.
VENDOR_RANGE = 12

# ms to wait for an NPC's right-click menu to arrive.
CONTEXT_TIMEOUT = 10000

# How often the vendor round comes due. The run breaks off whatever job it is
# on, does the round, and resumes the same lap at the same waypoint.
VENDOR_INTERVAL_MS = 30 * 60 * 1000

# Go home and store straight after a vendor round that actually collected
# something. Resource orders, bulk order deeds and taming deeds are all handed
# over at the NPC and then ride around in the pack for the rest of the lap -
# taking up item slots, and at risk if the character dies. The drop-off already
# knows where each of them goes (HOUSE_DEPOSITS for the order books, the BOD
# book for bulk orders), so this just makes it happen at the right moment.
#
# Nothing was collected means no trip: a round where every NPC was still on
# cooldown does not earn a recall home.
DROPOFF_AFTER_VENDORS = True

# ms to wait for an item or mobile TOOLTIP. Vendor titles and the backpack's
# Contents line both come from tooltips, and reading one before it has arrived
# gives an empty string rather than an error.
PROPS_TIMEOUT = 1500

# Context entries that must never be selected by a loose substring match.
# These NPCs also offer, on the same menu:
#     Buy   Sell   Bribe   Open Bankbox   Train Animal Taming   Train Inscription
# so a sloppy `context` value like "Taming" would spend gold on skill training,
# and "Order" could hit something unintended. A configured entry that matches a
# label EXACTLY is always honoured - this only blocks accidental partial hits.
CONTEXT_NEVER = ["buy", "sell", "bribe", "open bankbox", "train "]


# =============================================================================
# CONFIG - GREYSKULL CALL-OUT
# =============================================================================
# Global chat reaches the journal as:
#     System: <Public> Fred Kruger: By The Power Of Greyskull!
# so the speaker is inside the text and entry.Name is just "System".
# Phrases match CASE-INSENSITIVELY as substrings.

GREYSKULL_PHRASES = [
    "by the power of greyskull",
]

# Empty = ANYONE may call it, which is the point. Add names only to restrict.
GREYSKULL_ALLOWED_CALLERS = []
GREYSKULL_REQUIRE_CHANNEL = ""       # e.g. "Public" to accept only <Public>
GREYSKULL_IGNORE_SELF = False
# How long to stand at the circle once it has been reached, before going back
# to work.
GREYSKULL_HOLD_MS = 20000

# =============================================================================
# CONFIG - SKIP COMMAND
# =============================================================================
# Say one of these in game and the script abandons the spot it is working and
# recalls to the next rune on the route. Useful when you can see it is stuck
# somewhere the guards have not noticed yet, or when a rune has turned out to
# be somewhere you would rather it did not stand.
#
# Matched on the WHOLE spoken line, not as a substring: "skip" is an ordinary
# word and a vendor or another player saying it in passing must not send the
# character off. Case and trailing punctuation are ignored, because a phrase a
# human types varies in both every time.
SKIP_PHRASES = ["skip"]

# Only the character running THIS copy of the script may say it. Confirmed on
# the journal entry's Serial, which is the speaker's mobile - names are not
# unique and global chat puts "System" in the Name field.
#
# False lets anyone skip your character, which is almost never what you want.
SKIP_SELF_ONLY = True

# The smaller version of the same idea. "skip" abandons the WHOLE area and
# recalls; "move" leaves only the spot being worked and walks to the next spot
# in the same area - so a rune you are happy with does not have to be thrown
# away because one tile in it is bad.
#
# When the spot being left was the LAST one in the area there is nothing to
# move on to, so it falls through to the same thing skip does and recalls to
# the next rune. That is not a special case in the code: the sweep loop simply
# runs out of spots and returns "next" on its own.
#
# Matched the same way as SKIP_PHRASES - whole line, self only. "move" is an
# even more ordinary word than "skip", so the whole-line rule matters more
# here, not less.
MOVE_PHRASES = ["move"]
MOVE_SELF_ONLY = True

# Where the call sends you: the runebook folder and the rune inside it.
ARCANE_FOLDER = ['Arcane']
ARCANE_POINT = 'Circle'


# =============================================================================
# CONFIG - DROP-OFF
# =============================================================================

# The chest everything not claimed by a key is swept into. One-way: whatever
# lands here has to be fetched out by hand.
DROP_CHEST_SERIAL = 0x400CEF90

# Runebook folder and rune that get you home.
DROP_FOLDER = ['Homes']
DROP_POINT = 'HOME'

# A drop-off comes due this often even if the pack never fills, so the order
# books and the BOD book get emptied on a schedule rather than only when full.
DROP_INTERVAL_MS = 60 * 60 * 1000

# -----------------------------------------------------------------------------
# HOUSE DEPOSITS - order books emptied on every drop-off run, whatever the pack
# weight. These are separate from RESTOCK_KEYS because those are only used when
# the pack is actually full, whereas orders should always be handed in.
#
# These books use the SAME "Refill from stock" entry as every other key, and
# pressing it deposits everything of that type at once.
#
# NOTE ON THE RECORDED MACRO. The recording ended with:
#     Gumps.SendAdvancedAction(0x6abce12, 0, [], [0], ["100"])
# That amount is deliberately NOT reproduced. The deposit happens on the context
# reply; the gump is just the book's window, and its text field is for
# WITHDRAWING. Sending "100" into it risks pulling 100 items back out. The gump
# is closed instead.

HOUSE_DEPOSITS = [
    {"enabled": True, "label": "Taming orders",   "serial": 0x4057CC3A},
    {"enabled": True, "label": "Resource orders", "serial": 0x404AC332},
]

# Same entry as the keys. Matched exact-first, then guarded substring.
HOUSE_DEPOSIT_CONTEXT = ["Refill from stock"]


# -----------------------------------------------------------------------------
# BULK ORDER DEEDS - dragged into a carried Bulk Order Book.
#
# Inspected: the book is ItemID 0x2259, serial 0x413F54D6, carried in the pack,
# tooltip "Deeds In Book: 0 / Book Name: Hattori Hanzo".
#
# CAREFUL. A bulk order deed is ItemID 0x2258 - and so is "A Taming Order"
# (0x2258, tooltip "Creature Type: Kirin ... Filled: 24/60"). The order books and
# the BOD book therefore compete for the same graphic, and filing purely by
# ItemID would post taming and resource orders into the BOD book.
#
# Two things prevent that:
#   1. HOUSE_DEPOSITS runs FIRST, so "Refill from stock" has already taken the
#      taming and resource orders out of the pack.
#   2. BOD_EXCLUDE_TEXT skips anything whose tooltip marks it as one of those,
#      in case a deposit failed or a new order type appears.
#
# Every deed moved is logged with its name, so a mis-file is visible.

# WHICH BOOK. Three characters run this script and each carries their own book,
# so the default is to find it automatically - no per-character editing needed.
#
#   BOD_BOOK_BY_CHARACTER  wins if your character is listed
#   BOD_BOOK_SERIAL        used next, if set
#   otherwise              the first BOD_BOOK_ID in your backpack
#
# Auto-detection is the recommended setting. Fill a serial in only if you carry
# more than one book and need a specific one.
BOD_BOOK_BY_CHARACTER = {
    # "Hattori Hanzo": 0x413F54D6,
}
BOD_BOOK_SERIAL = 0
BOD_BOOK_ID = 0x2259

# The graphic a bulk order deed uses. Anything else in the pack is ignored.
BOD_DEED_IDS = [0x2258]

# Tooltip text that must be present to file a deed. Empty = no requirement.
BOD_REQUIRE_TEXT = []

# Tooltip text that disqualifies a deed. The BOD book refuses taming and
# resource orders itself, so this is only to avoid pointless drag attempts and
# the log noise they cause - an empty list is safe, just noisier.
BOD_EXCLUDE_TEXT = ["creature type", "resource type"]

# ms between drags into the book. Dragging faster than the server accepts
# silently loses deeds.
BOD_MOVE_PAUSE = 900

# Ceiling on deeds filed per drop-off, so a book that refuses every deed
# cannot hold the run up indefinitely.
BOD_MAX_PER_RUN = 30

# The window the books open, closed after depositing. Both books share this id,
# so a stale one is cleared first. Set to 0 if they open nothing.
HOUSE_DEPOSIT_GUMP = 0x06ABCE12
HOUSE_DEPOSIT_PAUSE = 1200

# Items moved to the drop chest. Ingots (0x1BF2, hue 0) keep 20 behind.
PURGE_ID = [0x1BF2, 0x1726, 0x1779, 0x0F0F, 0x0F10, 0x0F11, 0x0F12, 0x0F13,
            0x0F14, 0x0F15, 0x0F16, 0x0F17, 0x0F18, 0x0F19, 0x0F1A, 0x0F1B,
            0x0F1C, 0x0F1D, 0x0F1E, 0x0F1F, 0x0F20, 0x0F21, 0x0F22, 0x0F23,
            0x0F24, 0x0F25, 0x0F26, 0x0F27, 0x0F28, 0x3192, 0x3193, 0x3194,
            0x3195, 0x3196, 0x3197, 0x3198, 0x5732,
            # Lumber output, as a sweep for anything the Wood Storage did not
            # take. Restock runs first, so normally these never reach the chest.
            0x1BD7,     # board
            0x1BDD,     # log
            0x318F,     # bark fragment
            0x3191]     # luminescent fungi

# Ingots left in the pack when the chest sweep runs, so there is always
# something to hand for a tinker repair. Only applies to plain iron (hue 0).
KEEP_INGOTS = 20

# Graphics that BELONG to a key, and which key takes them.
#
# The chest sweep is a one-way trip: anything it takes has to be fetched back
# out by hand. So a resource listed here is only ever swept into the chest when
# its key could NOT be found - if the key is in the pack, the resource stays
# put and goes into the key on the next restock instead.
#
# Before this, PURGE_ID listed logs and boards unconditionally as "a sweep for
# anything the Wood Storage did not take", so a restock that came up a little
# short, or a storage that was momentarily not found, sent the lumber to the
# chest anyway.
KEY_BACKED_IDS = [
    {"label": "Wood Storage", "ids": [0x1BD7, 0x1BDD]},   # boards, logs
    {"label": "Ingot key",    "ids": [0x1BF2]},           # ingots
    # Granite. 0x1779 is in PURGE_ID, so without this line every piece mined
    # would be swept into the chest even with the Stone Storage in the pack -
    # and the chest is one-way.
    {"label": "Stone Storage", "ids": [0x1779]},          # granite
]

# Storage containers and keys that swallow harvested resources. Each is
# single-clicked and answered with RESTOCK_CONTEXT.
#
#   label    Name used in the log.
#   serial   Exact serial, tried first. Most reliable when the thing never moves.
#   id/hue   Fallback lookup if the serial is gone (item replaced, hue -1 = any).
#   where    "pack"  - inside your backpack
#            "world" - on the ground nearby, e.g. locked down in a house
#   range    Tiles to search for "world" entries.
RESTOCK_CONTEXT = ["Refill from stock"]

# Per-key overrides, for a storage whose menu words it differently. Each is
# tried BEFORE the shared RESTOCK_CONTEXT above, and an empty list just means
# "use the shared one".
#
# Menu entries are matched exactly first and only then by a guarded substring,
# because a context menu carries Buy, Sell, Bribe and Open Bankbox right next
# to the entry you want.
WOOD_STORAGE_CONTEXT = []
INGOT_KEY_CONTEXT = []
STONE_STORAGE_CONTEXT = []

RESTOCK_KEYS = [
    {
        # Built from the WOOD_STORAGE_* settings at the top of the file.
        # As inspected it is locked down at the house - Container and
        # RootContainer both None, Ground yes - so a backpack search, which is
        # what the original did, could never find it.
        "label": "Wood Storage",
        "context": WOOD_STORAGE_CONTEXT,
        "serial": WOOD_STORAGE_SERIAL,
        "id": WOOD_STORAGE_ID, "hue": WOOD_STORAGE_HUE,
        "names": WOOD_STORAGE_NAMES,
        "where": WOOD_STORAGE_WHERE, "range": WOOD_STORAGE_RANGE,
    },
    {"label": "Master key",  "id": 0x176B, "hue": 0x0481, "where": "pack"},
    {
        # Built from the INGOT_KEY_* settings at the top of the file, the same
        # way the Wood Storage entry is.
        "label": "Ingot key",
        "context": INGOT_KEY_CONTEXT,
        "enabled": INGOT_KEY_ENABLED,
        "serial": INGOT_KEY_SERIAL,
        "id": INGOT_KEY_ID, "hue": INGOT_KEY_HUE,
        "names": INGOT_KEY_NAMES,
        "where": INGOT_KEY_WHERE, "range": INGOT_KEY_RANGE,
    },
    {
        # Built from the STONE_STORAGE_* settings at the top of the file. This
        # shipped as an unnamed "Key (alt)" on the same graphic, which is what
        # it always was.
        "label": "Stone Storage",
        "context": STONE_STORAGE_CONTEXT,
        "enabled": STONE_STORAGE_ENABLED,
        "serial": STONE_STORAGE_SERIAL,
        "id": STONE_STORAGE_ID, "hue": STONE_STORAGE_HUE,
        "names": STONE_STORAGE_NAMES,
        "where": STONE_STORAGE_WHERE, "range": STONE_STORAGE_RANGE,
    },
    # 0x2259 is the Bulk Order Book graphic. Carried books are handled by
    # BOD_BOOK_SERIAL below (deeds are dragged in); this entry is inherited from
    # the original script and only matches one sitting on the ground nearby.
    {"label": "Stock book (ground)", "id": 0x2259, "hue": -1, "where": "world",
     "range": 3},
]

# Context entry that pushes the pack's resources into the storage. Matched the
# same way as vendor entries: exact label first, then a guarded substring.

# -----------------------------------------------------------------------------
# WHEN THE PACK COUNTS AS FULL
#
# Harvesting runs until there is no longer room for one more yield, NOT until
# some fraction of the pack is used. A fraction throws away everything above
# it: at 0.6 a 495-stone character stored at 297 stones and left 198 on the
# table, every single trip.
#
# So the rule is a RESERVE, in stones, measured against real carry weight
# (Player.MaxWeight - Player.Weight). Keep harvesting while the free weight is
# above the reserve; store when it is not.
#
# The reserve has to cover one more yield, and how heavy that is depends on the
# resource - so it is not guessed. The script watches how much each swing
# actually adds and keeps the largest it has seen, times a safety margin. The
# floor below is only what it uses before it has seen anything.
# Store once this fraction of carry weight is used. This is the rule that
# decides when to stop and empty into the keys, and it is deliberately a plain
# percentage because that is the thing that is easy to reason about in game:
# 0.90 on a 495-stone character means storing at 445 stones.
PACK_STORE_AT = 0.90

# Backstop under the percentage. If ONE more yield would take the pack past its
# limit, stop now even though the percentage has not been reached - going over
# means the server refuses the ore and it is simply lost. The reserve is
# measured, not guessed: see note_yield below.
PACK_WEIGHT_RESERVE = 30          # stones, floor for the reserve
PACK_RESERVE_SAFETY = 1.5         # multiplier on the heaviest observed swing

# Ceiling on the learned reserve, so one freak measurement - picking up a full
# chest, a pet handing something over - cannot park the reserve so high that
# the character stores at half weight forever.
PACK_RESERVE_MAX = 200            # stones

# Pack is "full" past this fraction of ITEM COUNT. Weight is handled by the
# reserve above; this is the separate problem of a pack full of gems, tools and
# deeds while barely carrying any weight, which no key can fix.
PACK_THRESHOLD = 0.9

# A job may only start with the pack below this fraction. Anything heavier and
# the next job gets unloaded first - measured in the real trace, mining handed
# lumberjacking 225 of its 297 usable stones, leaving room for two chops.
PACK_HANDOVER_LEVEL = 0.15

# How far up the container chain to look when deciding whether an item is on
# the player. RootContainer can report the backpack's serial rather than the
# player's, so the chain has to be walked.
MAX_CONTAINER_DEPTH = 6


# =============================================================================
# CONFIG - MINING
# =============================================================================

SHOVEL_ID = 0x0F39                # the digging tool
TINKER_ID = 0x1EB8                # tinker's tools, used to make a new shovel

# The window the tinker's tools open. Button 15 on it is the shovel.
TINKER_GUMP = 0x38920abd

# Portable forge. Ore is smelted against this, and with no forge in the pack
# smelting is skipped entirely - so ore would be carried home uselessly.
FORGE_ID = 0x0FB1

# Every ore graphic, small piles through large. Ore is NOT in PURGE_ID: the
# chest is for finished goods, so smelting is the only route out of the pack.
ORE_ID = [0x19BA, 0x19B9, 0x19B8, 0x19B7]

# ms for one swing to resolve. The server's mining MaxRange is 2 tiles.
MINE_SWING_TIMEOUT = 5000

# -----------------------------------------------------------------------------
# MYTHRIL - this shard's own metal, and it does not behave like the others.
#
# Observed in game 2026-08-22 on the mythril runes:
#
#   * A swing takes about EIGHT seconds, against five for ordinary rock. At
#     MINE_SWING_TIMEOUT the swing is still running when the timeout expires,
#     so dig_once returns "silent", mine_spot breaks after one swing and the
#     whole spot is abandoned. That alone is why these runes produce nothing.
#
#   * SUCCESS IS SILENT. There is no "You dig some ore" line at all - the ore
#     simply appears in the pack. So a successful mythril swing cannot be
#     recognised from the journal, and has to be seen as weight arriving.
#
#   * Failure DOES speak: "You dig for a while but fail to find any mythril
#     ore of suitable quality." Note that starts with "You", so dig_once's
#     broad catch-all would score it as ore recovered - which is why the
#     mythril strings are tested BEFORE that catch-all.
#
#   * Depletion speaks too, but differently: "There is no mythril ore here to
#     mine." That contains neither "no metal" nor "You", so nothing in the
#     ordinary tables matches it and it also fell through to "silent".
#
#   * Ordinary ore still comes out of these spots as normal.
#
# WAYPOINTS ONLY. Nothing here applies anywhere else - a 12s timeout on
# ordinary rock would make every normal swing three times slower to give up.
# Numbers are the 1-based waypoint index the journal prints, the N in
# "Mining waypoint N/M".
MYTHRIL_ENABLED = False
MYTHRIL_WAYPOINTS = []

# Generous: the swing is ~8s and a laggy server is slower still. It only ever
# applies inside MYTHRIL_WAYPOINTS, so being generous costs nothing elsewhere.
MYTHRIL_SWING_TIMEOUT = 12000

# How long to keep watching for silently-arriving ore after the server has said
# nothing. Inspected: "2 ore", ItemID 0x19B9, hue 0x0057, tooltip line
# "Mythril", 24 stones for two.
MYTHRIL_ORE_ID = 0x19B9
MYTHRIL_ORE_HUE = 0x0057

# -----------------------------------------------------------------------------
# MINING AREA SWEEP - move to the next patch of rock instead of recalling.
#
# A resource BANK is the unit that runs out. ServUO
# Scripts/Services/Harvest/Mining.cs sets BankWidth = 8 and BankHeight = 8, so
# once "there is no metal here" comes back, everything within that whole 8x8
# block is spent and standing anywhere inside it is wasted effort. Eight tiles
# is therefore the SHORTEST move that can reach fresh ore, which is why STEP
# defaults to exactly that. (Lumber banks are only 4x3 - that is why the lumber
# sweep steps 3 and this one steps 8.)
#
# RADIUS is how far out to look for the next patch, in tiles. 18 reaches two
# banks in every direction.
#
# Spots are not walked blindly: each candidate is checked against the mountain,
# cave and sand tile lists below FIRST, so the character only walks to ground
# that can actually be mined.
MINE_AREA_ENABLED = True
MINE_AREA_RADIUS = 18
MINE_BANK = 8                    # = Mining.cs BankWidth AND BankHeight
MINE_AREA_STEP = MINE_BANK       # do not lower: a smaller step re-mines a
                                 # bank that has already said it is empty

# Include sand tiles as somewhere worth standing. Off by default: mining sand
# needs the sand-mining skill/quest on most shards, and a shovel on sand just
# reports failure over and over.
MINE_AREA_INCLUDE_SAND = False

# ms to reach one mining spot before giving up on it.
MINE_AREA_MOVE_TIMEOUT = 12000

# ms to wait for the reply to the first swing at a new spot.
MINE_AREA_PROBE_TIMEOUT = 5000

# Absolute backstop on swings at one spot. The real guard is the no-ore clock
# above; this only stops a runaway loop.
#
# It must be comfortably ABOVE a full bank or it truncates depletion, which is
# the thing it must not do. Mining.cs gives a bank 10-34 ore, one per swing,
# and misses ("you loosen some rocks but fail") cost a swing without yielding -
# so 34 is the floor, not the target. 80 leaves room for a bad run of misses.
MINE_AREA_MAX_SWINGS = 80


# -----------------------------------------------------------------------------
# MINEABLE GROUND - which land and static tiles count as mountain, cave or sand.
#
# From ServUO Scripts/Services/Harvest/Mining.cs (m_MountainAndCaveTiles and
# m_SandTiles), extracted by tools/extract_harvest_tiles.py. Regenerate with:
#
#     python tools/extract_harvest_tiles.py --fetch
#
# Do not hand-edit. A tile is checked as BOTH a land id and a static id,
# because mountains come as either depending on the map.
MOUNTAIN_AND_CAVE_TILES = frozenset([
    0x00DC, 0x00DD, 0x00DE, 0x00DF, 0x00E0, 0x00E1, 0x00E2, 0x00E3, 0x00E4, 0x00E5,
    0x00E6, 0x00E7, 0x00EC, 0x00ED, 0x00EE, 0x00EF, 0x00F0, 0x00F1, 0x00F2, 0x00F3,
    0x00F4, 0x00F5, 0x00F6, 0x00F7, 0x00FC, 0x00FD, 0x00FE, 0x00FF, 0x0100, 0x0101,
    0x0102, 0x0103, 0x0104, 0x0105, 0x0106, 0x0107, 0x010C, 0x010D, 0x010E, 0x010F,
    0x0110, 0x0111, 0x0112, 0x0113, 0x0114, 0x0115, 0x0116, 0x0117, 0x011E, 0x011F,
    0x0120, 0x0121, 0x0122, 0x0123, 0x0124, 0x0125, 0x0126, 0x0127, 0x0128, 0x0129,
    0x0141, 0x0142, 0x0143, 0x0144, 0x01D3, 0x01D4, 0x01D5, 0x01D6, 0x01D7, 0x01D8,
    0x01D9, 0x01DA, 0x01DC, 0x01DD, 0x01DE, 0x01DF, 0x01E0, 0x01E1, 0x01E2, 0x01E3,
    0x01E4, 0x01E5, 0x01E6, 0x01E7, 0x01EC, 0x01ED, 0x01EE, 0x01EF, 0x021F, 0x0220,
    0x0221, 0x0222, 0x0223, 0x0224, 0x0225, 0x0226, 0x0227, 0x0228, 0x0229, 0x022A,
    0x022B, 0x022C, 0x022D, 0x022E, 0x022F, 0x0230, 0x0231, 0x0232, 0x0233, 0x0234,
    0x0235, 0x0236, 0x0237, 0x0238, 0x0239, 0x023A, 0x023B, 0x023C, 0x023D, 0x023E,
    0x023F, 0x0240, 0x0241, 0x0242, 0x0243, 0x0245, 0x0246, 0x0247, 0x0248, 0x0249,
    0x024A, 0x024B, 0x024C, 0x024D, 0x024E, 0x024F, 0x0250, 0x0251, 0x0252, 0x0253,
    0x0254, 0x0255, 0x0256, 0x0257, 0x0258, 0x0259, 0x0262, 0x0263, 0x0264, 0x0265,
    0x03F2, 0x06CD, 0x06CE, 0x06CF, 0x06D0, 0x06D1, 0x06D2, 0x06D3, 0x06D4, 0x06D5,
    0x06D6, 0x06D7, 0x06D8, 0x06D9, 0x06DA, 0x06DB, 0x06DC, 0x06DD, 0x06EB, 0x06EC,
    0x06ED, 0x06EE, 0x06EF, 0x06F0, 0x06F1, 0x06F2, 0x06F3, 0x06F4, 0x06F5, 0x06F6,
    0x06F7, 0x06F8, 0x06F9, 0x06FA, 0x06FB, 0x06FC, 0x06FD, 0x06FE, 0x0709, 0x070A,
    0x070B, 0x070C, 0x070D, 0x070E, 0x070F, 0x0710, 0x0711, 0x0713, 0x0714, 0x0715,
    0x0716, 0x0717, 0x0718, 0x0719, 0x071A, 0x071B, 0x071C, 0x071D, 0x071E, 0x071F,
    0x0720, 0x0727, 0x0728, 0x0729, 0x072A, 0x072B, 0x072C, 0x072D, 0x072E, 0x072F,
    0x0730, 0x0731, 0x0732, 0x0733, 0x0734, 0x0735, 0x0736, 0x0737, 0x0738, 0x0739,
    0x073A, 0x073B, 0x073C, 0x073D, 0x073E, 0x0745, 0x0746, 0x0747, 0x0748, 0x0749,
    0x074A, 0x074B, 0x074C, 0x074D, 0x074E, 0x074F, 0x0750, 0x0751, 0x0752, 0x0753,
    0x0754, 0x0755, 0x0756, 0x0757, 0x0758, 0x0759, 0x075A, 0x075B, 0x075C, 0x07BD,
    0x07BE, 0x07BF, 0x07C0, 0x07C1, 0x07C2, 0x07C3, 0x07C4, 0x07C5, 0x07C6, 0x07C7,
    0x07C8, 0x07C9, 0x07CA, 0x07CB, 0x07CC, 0x07CD, 0x07CE, 0x07CF, 0x07D0, 0x07D1,
    0x07D2, 0x07D3, 0x07D4, 0x07EC, 0x07ED, 0x07EE, 0x07EF, 0x07F0, 0x07F1, 0x0834,
    0x0835, 0x0836, 0x0837, 0x0838, 0x0839, 0x453B, 0x453C, 0x453D, 0x453E, 0x453F,
    0x4540, 0x4541, 0x4542, 0x4543, 0x4544, 0x4545, 0x4546, 0x4547, 0x4548, 0x4549,
    0x454A, 0x454B, 0x454C, 0x454D, 0x454E, 0x454F,
])

SAND_TILES = frozenset([
    0x0016, 0x0017, 0x0018, 0x0019, 0x001A, 0x001B, 0x001C, 0x001D, 0x001E, 0x001F,
    0x0020, 0x0021, 0x0022, 0x0023, 0x0024, 0x0025, 0x0026, 0x0027, 0x0028, 0x0029,
    0x002A, 0x002B, 0x002C, 0x002D, 0x002E, 0x002F, 0x0030, 0x0031, 0x0032, 0x0033,
    0x0034, 0x0035, 0x0036, 0x0037, 0x0038, 0x0039, 0x003A, 0x003B, 0x003C, 0x003D,
    0x003E, 0x0044, 0x0045, 0x0046, 0x0047, 0x0048, 0x0049, 0x004A, 0x004B, 0x011E,
    0x011F, 0x0120, 0x0121, 0x0122, 0x0123, 0x0124, 0x0125, 0x0126, 0x0127, 0x0128,
    0x0129, 0x012A, 0x012B, 0x012C, 0x012D, 0x0192, 0x01A8, 0x01A9, 0x01AA, 0x01AB,
    0x01B9, 0x01BA, 0x01BB, 0x01BC, 0x01BD, 0x01BE, 0x01BF, 0x01C0, 0x01C1, 0x01C2,
    0x01C3, 0x01C4, 0x01C5, 0x01C6, 0x01C7, 0x01C8, 0x01C9, 0x01CA, 0x01CB, 0x01CC,
    0x01CD, 0x01CE, 0x01CF, 0x01D0, 0x01D1, 0x0282, 0x0283, 0x0284, 0x0285, 0x028A,
    0x028B, 0x028C, 0x028D, 0x028E, 0x028F, 0x0290, 0x0291, 0x0335, 0x0336, 0x0337,
    0x0338, 0x0339, 0x033A, 0x033B, 0x033C, 0x0341, 0x0342, 0x0343, 0x0344, 0x034D,
    0x034E, 0x034F, 0x0350, 0x0351, 0x0352, 0x0353, 0x0354, 0x0359, 0x035A, 0x035B,
    0x035C, 0x03B7, 0x03B8, 0x03B9, 0x03BA, 0x03BB, 0x03BC, 0x03BD, 0x03BE, 0x03C7,
    0x03C8, 0x03C9, 0x03CA, 0x05A7, 0x05A8, 0x05A9, 0x05AA, 0x05AB, 0x05AC, 0x05AD,
    0x05AE, 0x05AF, 0x05B0, 0x05B1, 0x05B2, 0x064B, 0x064C, 0x064D, 0x064E, 0x064F,
    0x0650, 0x0651, 0x0652, 0x0657, 0x0658, 0x0659, 0x065A, 0x0663, 0x0664, 0x0665,
    0x0666, 0x0667, 0x0668, 0x0669, 0x066A, 0x066F, 0x0670, 0x0671, 0x0672,
])


# =============================================================================
# CONFIG - LUMBERJACKING
# =============================================================================

# Axe graphics, from ServUO Scripts/Items/Equipment/Weapons. Each weapon has a
# mirrored variant one id away, so both are listed. Searching by ItemID does not
# depend on item names being loaded, which is what makes the lookup reliable
# after the axe has been stowed and has to be recovered from the pack.
#
# War axe is deliberately absent: it is a valid lumberjacking tool on the server
# but the original script excluded it, presumably to avoid wearing out a weapon.
# Pickaxe is last so a real axe is always preferred.
AXE_IDS = [
    0x0F43, 0x0F44,     # hatchet
    0x0F49, 0x0F4A,     # axe
    0x0F4B, 0x0F4C,     # double axe
    0x0F47, 0x0F48,     # battle axe
    0x13FB, 0x13FA,     # large battle axe
    0x1443, 0x1444,     # two handed axe
    0x0F45, 0x0F46,     # executioner's axe
    0x48B2, 0x48B3,     # gargish axe
    0x48B0, 0x48B1,     # gargish battle axe
    0x0E86, 0x0E85,     # pickaxe
]

# Name matching, used as a fallback and for anything shard-custom. An item
# matching any AXE_WORDS but also any AXE_EXCLUDE is rejected.
AXE_WORDS = ["axe", "hatchet"]
AXE_EXCLUDE = ["war"]

# ms for one chop to resolve. The server's lumberjacking MaxRange is 2 tiles,
# so a rune has to land within 2 of the tree.
LUMBER_SWING_TIMEOUT = 6000

# -----------------------------------------------------------------------------
# LUMBER AREA SWEEP - work a whole patch at each rune, not just the one tree.
#
# A rune drops you beside one tree and the server's harvest range is 2 tiles,
# so from a single standing spot that one tree is all you can ever reach. With
# this on, the script walks a grid of standing spots around the landing point
# and chops at each before recalling on, which is worth several trees per
# recall instead of one.
#
# SIZE is the edge of the box in tiles, centred on where the rune lands - 8
# means 4 tiles in every direction. STEP is the gap between standing spots:
# the harvest range is 2, so a step of 4 just barely touches and a step of 3
# overlaps, which is far more forgiving of trees the pathfinder cannot reach
# head-on. Raising STEP walks less and misses more.
#
# 8 with a step of 3 gives 9 standing spots covering 5 tiles out in each
# direction. Set ENABLED = False for the old one-spot behaviour.
LUMBER_AREA_ENABLED = True
LUMBER_AREA_SIZE = 8
# Tiles between standing spots, PER AXIS, because a lumber bank is not square.
#
# ServUO Scripts/Services/Harvest/Lumberjacking.cs sets BankWidth = 4 and
# BankHeight = 3. A bank is the unit that DEPLETES - "there's not enough wood
# here" means that whole bank is spent - so a step smaller than the bank lands
# the character back in the block they just emptied and the server says the
# same thing again.
#
# This was set to 3 on both axes, which is why a depleted patch looked like the
# script standing around doing nothing: a third of the sideways moves stayed
# inside the same 4-wide bank and were dead on arrival.
LUMBER_BANK_W = 4                # = Lumberjacking.cs BankWidth
LUMBER_BANK_H = 3                # = Lumberjacking.cs BankHeight
LUMBER_AREA_STEP_X = LUMBER_BANK_W
LUMBER_AREA_STEP_Y = LUMBER_BANK_H

# ms to reach one standing spot before giving up on it and trying the next.
LUMBER_AREA_MOVE_TIMEOUT = 8000

# How far off an intended standing spot still counts as arrived. The harvest
# range is 2, so being a tile short reaches nearly the same trees - settling
# there beats burning the whole move timeout on a tile the pathfinder cannot
# stand on. Same idea as the taming script's approach fallback.
LUMBER_AREA_ARRIVE_ACCEPT = 1

# ms to wait for the server's reply to the FIRST swing at a new spot.
#
# A spot with no tree in reach normally answers at once with "You can't use an
# axe on that". If your shard answers with silence instead, that spot costs a
# full timeout every visit, so this is kept separate from LUMBER_SWING_TIMEOUT
# and can be cut right down. The sweep reports how many spots went silent, so
# the journal says whether this is worth touching at all.
LUMBER_AREA_PROBE_TIMEOUT = 6000

# Absolute backstop on chops at one spot, matching MINE_AREA_MAX_SWINGS. A
# wood bank holds 20-45 (Lumberjacking.cs MinTotal/MaxTotal) and misses cost a
# swing, so anything near 40 would abandon a full bank half-cut.
LUMBER_AREA_MAX_SWINGS = 100

# -----------------------------------------------------------------------------
# WALKING BETWEEN SPOTS - shared by both sweeps.
#
# The standing grid is laid out by ARITHMETIC, so underground it regularly puts
# the next spot inside a mountain or on the far side of one. Walking at those
# just bounces off the rock until the move timeout, which is what left a
# character shuffling against a cliff face instead of mining.
#
# So every spot is PATH-CHECKED before a step is taken. PathFinding.GetPath
# runs the search without moving anyone, so asking costs nothing.

# Refuse a spot whose path is more than this many times the direct distance.
#
# "Is there a path" is not on its own the right question. Inside a cave the
# next ore bank is often 8 tiles away through solid rock with a perfectly real
# 80-tile path around the outside of the mountain - and walking it leaves the
# mine entirely, which is worse than skipping the spot. 3.0 allows a normal
# detour around a wall and refuses a trip around the mountain.
AREA_MAX_DETOUR = 3.0

# Give up after this many moves that got no closer. Measured against the BEST
# distance reached, not the previous one: a pathfinder bouncing off a wall
# shuffles back and forth, so "did I move" says yes forever while "am I getting
# closer" says no - and only the second is the truth.
AREA_STALL_STEPS = 4

# HARD CAP on the time spent at one standing spot - walking to it AND swinging
# there. When it runs out the sweep moves to the next spot regardless of what
# is happening.
#
# This is the backstop that guarantees the character keeps moving. Everything
# else here is a diagnosis of a particular way of getting stuck; this one does
# not care why. Before it existed a mining spot could hold the character for
# MINE_AREA_MAX_SWINGS * MINE_SWING_TIMEOUT - 40 swings at 5s, over three
# minutes - and a character wedged against a cave wall looked exactly like one
# working a rich vein.
#
# NOTE this cuts off a PRODUCTIVE spot too. An 8x8 ore bank holds 10-34 ore
# (Mining.cs MinTotal/MaxTotal), which is more than 15 seconds of swinging, so
# some is left behind - the sweep comes back to it on the next visit. If the
# journal shows spots being cut off while still yielding, this is the number to
# raise.
# Measured from the last swing that PRODUCED something, not from arriving. A
# spot that is yielding keeps resetting it and is worked until the bank is
# empty; only a spot producing nothing runs the clock down.
#
# This started as a hard cap and that was wrong: it cut productive spots off
# part-way, so banks were abandoned half-mined. The right reading of "stuck" is
# the one that matches what a person sees - the character moved, and then no
# mining happened. Time spent actually mining is not stuck.
AREA_SPOT_TIMEOUT_MS = 15000

# HARD LIMIT on getting NOTHING. If no swing anywhere in the area has produced
# anything for this long, abandon the rune and recall to the next one.
#
# The spot cap above bounds one spot; this bounds the whole visit. They are
# different failures. A character wedged against a cave wall passes the spot
# cap perfectly happily - it moves on every 15 seconds, to another spot behind
# the same wall, and on a 25-spot mining grid that is six minutes of looking
# busy and producing nothing. This is the one that says "you are not actually
# harvesting, leave".
#
# The clock resets on every swing that yields, so a productive area is never
# interrupted however long it takes.
AREA_IDLE_TIMEOUT_MS = 45000

# ABSOLUTE ceiling on one spot. NOTHING extends this - not ore, not a mythril
# miss, not anything.
#
# Both guards above are resettable by design, and that is what let a character
# sit on one tile for several minutes with neither of them firing:
#
#   * AREA_SPOT_TIMEOUT_MS is pushed out again by every productive swing, and
#     a mythril "miss" counts as productive because eight seconds of digging
#     IS work. On a spot that misses forever, it never expires.
#   * AREA_IDLE_TIMEOUT_MS is only tested in the sweep, BETWEEN spots. A spot
#     that never returns never gives it a turn.
#
# So the only real bound was MINE_AREA_MAX_SWINGS x the swing timeout: 80 x 5s
# is nearly seven minutes, and 80 x 12s in a mythril zone is SIXTEEN. Observed
# in game 2026-08-22 - the character stopped for minutes and answered neither
# "move" nor "skip" quickly, because both are only read between swings.
#
# This one is measured from entering the spot and is never reset.
AREA_SPOT_HARD_CAP_MS = 120000

# ABSOLUTE ceiling on ONE WAYPOINT, enforced by run_job rather than by the
# sweep - because the sweep is not always the thing that is stuck.
#
# run_job re-enters task() and only moves to the next rune when task() returns
# "next". EVERY OTHER RESULT leaves it at the same waypoint: "ok" does, and so
# does the pack-full path when unload_in_place() succeeds and `continue` runs
# without setting need_waypoint. Neither is bounded and neither logs, so a
# task that keeps returning one of them holds the character on one rune
# indefinitely, saying nothing.
#
# Observed 2026-08-22: MrGatherer stood against a cave wall for minutes after
# "could not reach spot 8/14", on .19, with every guard inside the sweep
# already in place - because none of them run between calls to task().
#
# This one is measured from arriving at a waypoint and is reset ONLY when the
# waypoint actually changes. Generous: a productive rune with a full 8x8 bank
# and a couple of unload trips is legitimately long.
# Was 420000 (seven minutes). Too long to sit watching a character that has
# clearly stopped - by the time it fires you have already come to look.
WAYPOINT_HARD_CAP_MS = 180000

# A HEARTBEAT. If nothing at all has been logged for this long, say what the
# script thinks it is doing.
#
# THIS IS THE ONE THAT WOULD HAVE SAVED THREE ROUNDS OF GUESSING. Every stall
# so far has been reported as "stuck, no output", and each time the question
# was WHERE - which the script knew and never said. The phase breadcrumb below
# is set at the top of every long operation, so a heartbeat names it.
HEARTBEAT_MS = 20000

# Long helpers - mana, the runebook, the trip home, the keys - check for a
# spoken "skip"/"move" and give up when they see one.
#
# WITHOUT THIS THERE IS NO MANUAL OVERRIDE. The word is heard from anywhere
# (interruptible_pause scans the journal every 250ms) but it was only ACTED on
# inside a walk or a spot loop. Everywhere else - and MEDITATION_TIMEOUT alone
# is 90 seconds of standing still, per recall - it did nothing at all, which is
# exactly "I have no way to force them to move on".
BAIL_ON_COMMAND = True

# How many in-place unloads at one waypoint before it is worth SAYING so. Not
# a limit - going home is not triggered by this - just the point at which a
# rune that keeps filling the pack is worth a line in the journal.
UNLOAD_IN_PLACE_NOTE = 6

# Say something while a spot is still being worked, this often. A spot that
# takes minutes in complete silence is indistinguishable from a hung script -
# which is exactly how the stall above got reported as "nothing is happening".
AREA_PROGRESS_MS = 30000

# Seconds PathFinding.Go is allowed for ONE leg of a walk.
#
# THIS IS THE ONE THAT MATTERED. Route.Timeout was never set, and Razor's
# related calls document their timeout as `-1` - no limit. PathFinding.Go
# therefore blocks for as long as it likes, and while it is blocked NONE of the
# guards above run: the spot cap, the idle watchdog and the stall detection are
# all Python checks BETWEEN calls, and control never comes back to make them.
# That is why a character could sit against a cave wall through three separate
# rounds of "add a timeout" - every timeout added was on the wrong side of a
# blocking call.
#
# Keep it short. It is one leg of a walk, not the whole journey; walk_to calls
# it repeatedly and applies its own budget between legs.
PATH_LEG_TIMEOUT_S = 5.0

# Give up on a walk after this long on the EXACT same tile. Movement is the
# thing being attempted, so not moving at all is the failure - unlike swinging,
# where standing still is normal and AREA_IDLE_TIMEOUT_MS is the right test.
AREA_STUCK_TIMEOUT_MS = 20000

# How long to wait for the character to exist in the world before moving, and
# how often to check. See player_ready() - ClassicUO's Plugin.RequestMove has
# no null check on World.Player, so asking to move during a recall takes the
# whole CLIENT down, not just the script.
PLAYER_READY_TIMEOUT_MS = 15000
PLAYER_READY_POLL_MS = 250


# =============================================================================
# CONFIG - TRAVEL AND MANA
# =============================================================================

AR_COMMAND = "[ar"
AR_GUMPID = 0xc395adb4

# Confirmed by gump inspection on two different runebooks.
AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON = 5
# 0 is "close gump" (a right-click) and must never be sent deliberately.
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 500, 503, 504]
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
# A runebook entry that also has (button + this) present is a DESTINATION
# rather than a folder - that second button is its "open a gate" twin. This is
# how a rune is told apart from a folder without clicking either.
AR_GATE_OFFSET = 30000

# Ceiling on runebook pages walked while searching. A safety bound, not a
# target - it stops a book that never reports a last page from spinning.
AR_MAX_PAGES = 20

# ---------------------------------------------------------------------------
# MANA AND MEDITATION
# ---------------------------------------------------------------------------

# Do not attempt a recall below this much mana; meditate first.
MIN_MANA_TO_TRAVEL = 20

# Mana to meditate up to. 0 means full.
MANA_TARGET = 0

# Give up on a meditation attempt after this long.
MEDITATION_TIMEOUT = 90000

# How often to re-read mana while meditating.
MEDITATION_POLL = 500

# Consecutive polls with NO mana gained before the attempt is abandoned and
# restarted. Meditation breaks silently, so waiting out the full timeout on a
# trance that already ended wastes a minute and a half.
MEDITATION_STALL = 8

# Pause before trying to meditate again after a failed attempt.
MEDITATION_RETRY_MS = 1500

# Stow what is in hand before meditating. Holding a weapon blocks it outright
# on most shards.
DISARM_FOR_MEDITATION = True

# ms to let a hand slot settle after stowing or re-equipping.
HAND_MOVE_PAUSE = 800

# ---------------------------------------------------------------------------
# LOGGING AND PACING
# ---------------------------------------------------------------------------

# Pause between harvest swings. Interruptible, so the Greyskull call and the
# vendor timer are still noticed during it.
HARVEST_PAUSE = 250

# True prints the verbose debug() lines as well as the normal log() ones. Turn
# it off for a quieter journal; anything that matters is logged either way.
DEBUG = True

# Journal text colours: ordinary, good news, warning, failure, section banner.
HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


# =============================================================================
# SERVER MESSAGES
#
# Text the SHARD sends, matched against the journal to work out what happened.
# Touch these only if your shard words things differently: if a job seems to
# ignore an outcome - never noticing a depleted vein, say - this is the first
# place to look.
#
# Each is annotated with the ServUO source file and cliloc number it came from,
# so it can be checked against the server rather than guessed at.
# =============================================================================
# Meditation - ServUO Scripts/Skills/Meditation.cs. The "Regenative"
# misspelling is in the server source; do not correct it.

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

# Lumberjacking - ServUO Scripts/Services/Harvest/Lumberjacking.cs, plus the
# shard's own "You chop" success line which the original script relied on.
LUMBER_SUCCESS = [
    "You chop",
    "You put",
]
LUMBER_RETRY = [
    "You hack at the tree for a while",     # 500495, a failed swing - keep going
]
LUMBER_DEPLETED = [
    # 500493 is "There's not enough wood here to harvest." - matched WITHOUT
    # the leading "There's" on purpose. Shards and clients differ on whether
    # that apostrophe is ASCII ' or a typographic one, and a mismatch there
    # fails silently: the line never matches, the swing times out instead, and
    # every depleted spot costs a full timeout of standing still.
    "not enough wood here",                 # 500493
]
LUMBER_BAD_TARGET = [
    "You can't use an axe on that",         # 500489
    "That is too far away",                 # 500446
]
LUMBER_PACK_FULL = [
    "You can't place any wood into your backpack",   # 500497
]
LUMBER_TOOL_BROKE = [
    "You broke your axe",                   # 500499
]

LUMBER_ALL = (LUMBER_SUCCESS + LUMBER_RETRY + LUMBER_DEPLETED +
              LUMBER_BAD_TARGET + LUMBER_PACK_FULL + LUMBER_TOOL_BROKE)

# Mining. The original matched a broad "You" with "You can't mine there" and
# "no metal" as the negative cases, and that WORKED - it is still the last
# resort in dig_once(). These specific strings are checked first only because
# the area sweep has to tell two things apart that the broad match cannot:
# "this bank is mined out, move one bank over" and "there is no rock here at
# all, never walk back". Verified ServUO clilocs.
MINE_SUCCESS = [
    "You dig some",                         # the ore line
    "You loosen some rocks but fail",       # 503043, a miss - keep swinging
    "You put",
]
MINE_DEPLETED = [
    "There is no metal here to mine",       # 503040
    "no metal",                             # the original's broad negative
    "Someone has gotten to the metal before you",   # 503042
]
MINE_BAD_TARGET = [
    "You can't mine there",                 # 501862
    "You can't mine that",                  # 501863
    "You have moved too far away",          # 503041
]
MINE_PACK_FULL = [
    "Your backpack is full",                # 1010481
]
MINE_TOOL_BROKE = ["You have worn out your tool"]       # 1044038

# Mythril, from the journal 2026-08-22. Both spellings are matched because the
# shard is not consistent about them and a missed match here reads as "silent".
#
# The FAIL line begins with "You", so it is tested before dig_once's broad
# `Journal.Search("You")` catch-all - otherwise a failed mythril swing scores
# as ore recovered.
MINE_MYTHRIL_FAIL = [
    "fail to find any mythril ore",
    "fail to find any mithril ore",
]
# "There is no mythril ore here to mine." Contains neither "no metal" nor
# "You", so none of the tables above match it.
MINE_MYTHRIL_DEPLETED = [
    "no mythril ore here to mine",
    "no mithril ore here to mine",
]

MINE_ALL = (MINE_SUCCESS + MINE_DEPLETED + MINE_BAD_TARGET +
            MINE_PACK_FULL + MINE_TOOL_BROKE +
            MINE_MYTHRIL_FAIL + MINE_MYTHRIL_DEPLETED)


# =============================================================================
# RUNTIME STATE
# =============================================================================



# Deeds actually handed over during the current vendor round. Counted here
# rather than from visit_stop's return value, which reports True for an NPC
# that answered "nothing yet" - a cooldown is a successful visit but not a
# collection, and only a collection is worth a trip home.





# =============================================================================
# HELPERS
# =============================================================================

# ---------------------------------------------------------------
# RUNTIME STATE
#
# BELOW THE SEAM ON PURPOSE. Everything above it is CONFIG, which is
# carried forward from each live copy rather than replaced; everything
# here is CODE, replaced wholesale. State that the code half uses must
# therefore live here, or a splice that adds a new one delivers the
# code that reads it and not the line that creates it.
#
# That is not hypothetical: _move_pending was declared above the seam,
# so the "move" command raised NameError in every live copy from the
# day it shipped while testing perfectly in the repo.
# ---------------------------------------------------------------
_armor_blocks_meditation = False
_passive_notice_shown = False
_vendor_history = {}      # vendor label -> [unix times an order was collected]
_vendor_ready_at = {}     # vendor label -> unix time it is worth asking again
_collected_this_round = 0
_routes = {}              # job name -> [(page, button, rune name)]
_waypoint = {}            # job name -> next index into that route
_lap_done = {}            # job name -> True once the route has wrapped
_current_job = None
_journal_cursor = 0.0
_greyskull_pending = False
_skip_pending = False
_greyskull_active = False
_axe_serial = None        # the axe last used, so it can be recovered by serial


# "move" - leave this spot, stay on this rune.
#
# DECLARED BELOW THE SEAM ON PURPOSE. It lived above it, in the config half,
# which is carried forward from each live copy rather than replaced - so the
# splice that added the "move" command never delivered this line, and
# take_move() read a name that did not exist. The command raised NameError in
# every live copy from the day it shipped and worked perfectly in the repo,
# which is why it tested clean and did nothing in game.
#
# check_undefined_names caught it. Anything the code half USES belongs in the
# code half.
_move_pending = False

_transcript = []


# The last CRASH_TRAIL log lines. This is the breadcrumb trail: every log call
# already sits at a point that meant something, so the tail of it says what the
# script was doing when it died - which a bare traceback does not.
_trail = []


# What the last line was, when, and how many copies of it were held back.
_last_line = {"text": "", "at": 0.0, "held": 0}
# Wall-clock second we are counting in, and how many lines went out in it.
_rate = {"second": 0, "sent": 0}


def log(text, hue=HUE_INFO):
    now = time.time()

    # The crash trail and the diagnostic transcript record EVERY line, whether
    # it reaches the client or not - suppressing a line must not blind the
    # crash report.
    if DIAGNOSTIC_MODE:
        _transcript.append(text)
    if CRASH_REPORT:
        _trail.append(text)
        if len(_trail) > CRASH_TRAIL:
            del _trail[:len(_trail) - CRASH_TRAIL]

    # Identical line, again, straight away: hold it.
    if (LOG_DEDUPE_MS and text == _last_line["text"]
            and (now - _last_line["at"]) * 1000.0 < LOG_DEDUPE_MS):
        _last_line["held"] += 1
        return

    held = _last_line["held"]
    _last_line["text"] = text
    _last_line["at"] = now
    _last_line["held"] = 0

    # Hard cap per second, so no path can flood the client however novel each
    # line is. The count is reported once the second turns over.
    second = int(now)
    if second != _rate["second"]:
        dropped = _rate["sent"] - LOG_MAX_PER_SECOND
        _rate["second"] = second
        _rate["sent"] = 0
        if dropped > 0:
            Misc.SendMessage("[Harvest] (%d line(s) dropped - logging faster "
                             "than the client can take)" % dropped,
                             HUE_WARN, False)
    _rate["sent"] += 1
    if _rate["sent"] > LOG_MAX_PER_SECOND:
        return

    if held:
        Misc.SendMessage("[Harvest] (previous line repeated %d more time(s))"
                         % held, HUE_INFO, False)
    Misc.SendMessage("[Harvest] " + text, hue, False)


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


def safe_name(obj):
    """Item and Mobile names can be null; the originals threw on those."""
    try:
        return (obj.Name or "") if obj is not None else ""
    except Exception:
        return ""


# --- Razor Enhanced signature shims -----------------------------------------

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


def clear_cursor():
    """Drop a stale target cursor.

    Target.WaitForTarget returns True for a cursor that is already open, so a
    leftover one silently swallows the next TargetExecute.
    """
    Target.ClearQueue()
    if Target.HasTarget():
        Target.Cancel()
        Misc.Pause(200)
        Target.ClearQueue()
    return not Target.HasTarget()


# =============================================================================
# GREYSKULL - detection is split from the response so it is safe to poll from
# inside long waits without recursing through travel.
# =============================================================================

def prime_journal_cursor():
    global _journal_cursor
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            stamp = getattr(entry, "Timestamp", 0.0) or 0.0
            if stamp > _journal_cursor:
                _journal_cursor = stamp
    except Exception:
        _journal_cursor = 0.0


def new_journal_entries():
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
CHAT_LINE = re.compile(
    r"^\s*(?:System\s*:\s*)?"
    r"(?:[<\[](?P<channel>[^>\]]+)[>\]]\s*)?"
    r"(?:(?P<caller>[^:]{1,40})\s*:\s*)?"
    r"(?P<said>.*)$")


def parse_chat_line(text):
    """(channel, caller, said). Any part may be None."""
    if not text:
        return (None, None, "")
    found = CHAT_LINE.match(text)
    if not found:
        return (None, None, text)
    said = found.group("said") or ""
    if not said:
        return (found.group("channel"), None, text)
    caller = found.group("caller")
    return (found.group("channel"),
            caller.strip() if caller else None,
            said.strip())


def caller_allowed(caller):
    if GREYSKULL_IGNORE_SELF and caller and Player.Name:
        if Player.Name.strip().lower() in caller.lower():
            return False
    if not GREYSKULL_ALLOWED_CALLERS:
        return True
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


def said_by_me(entry, said):
    """Did the character running THIS script say it?

    The journal entry's Serial is the speaker's mobile, which is the only
    reliable answer: names are not unique, and global chat arrives with
    "System" in the Name field and the real speaker buried in the text. Name
    matching is kept as a fallback for shards that do not fill Serial in.
    """
    try:
        if int(getattr(entry, "Serial", 0) or 0) == int(Player.Serial):
            return True
    except Exception:
        pass

    me = (Player.Name or "").strip().lower()
    if not me:
        return False
    if (getattr(entry, "Name", "") or "").strip().lower() == me:
        return True
    _channel, caller, _ = parse_chat_line(getattr(entry, "Text", "") or "")
    return bool(caller) and me in caller.lower()


def is_skip_line(entry, raw):
    """True for a bare "skip" from whoever is allowed to say it.

    Matched against the WHOLE spoken line rather than as a substring - "skip"
    is an ordinary word, and a vendor or a passer-by using it must not send the
    character off. Case and trailing punctuation are ignored.
    """
    _channel, _caller, said = parse_chat_line(raw)
    spoken = (said or raw).strip().strip(".,!?;:'\"").lower()
    if spoken not in [p.strip().lower() for p in SKIP_PHRASES if p.strip()]:
        return False
    if SKIP_SELF_ONLY and not said_by_me(entry, said):
        debug("Skip ignored - not said by this character.")
        return False
    return True


def is_move_line(entry, raw):
    """True for a bare "move" from whoever is allowed to say it.

    Same whole-line rule as is_skip_line, and for a stronger reason: "move" is
    a word that turns up in ordinary conversation far more often than "skip"
    does, so a substring match here would fire on half the things said near a
    boat or a mine.
    """
    _channel, _caller, said = parse_chat_line(raw)
    spoken = (said or raw).strip().strip(".,!?;:'\"").lower()
    if spoken not in [p.strip().lower() for p in MOVE_PHRASES if p.strip()]:
        return False
    if MOVE_SELF_ONLY and not said_by_me(entry, said):
        debug("Move ignored - not said by this character.")
        return False
    return True


def scan_journal():
    """One pass over the new journal lines, feeding EVERY passive trigger.

    Reading the journal CONSUMES it - new_journal_entries advances the cursor -
    so there can only ever be one reader. Two pollers each calling it would
    steal lines from one another and both would miss things at random, which is
    exactly the sort of fault that shows up once a week and cannot be
    reproduced. Every trigger is checked here, on the same line, in one place.
    """
    global _greyskull_pending, _skip_pending, _move_pending
    for entry in new_journal_entries():
        raw = getattr(entry, "Text", "") or ""
        if not raw:
            continue
        if not _greyskull_active and is_greyskull_line(raw):
            _greyskull_pending = True
        if is_skip_line(entry, raw):
            log("SKIP heard - leaving this spot for the next rune.", HUE_GOOD)
            Player.HeadMessage(HUE_GOOD, "Skipping...")
            _skip_pending = True
        elif is_move_line(entry, raw):
            # elif: one line cannot be both, and skip is the bigger hammer.
            log("MOVE heard - on to the next spot in this area.", HUE_GOOD)
            Player.HeadMessage(HUE_GOOD, "Moving on...")
            _move_pending = True


def poll_skip():
    """Raise the flag only. Safe from anywhere, including travel waits."""
    scan_journal()
    return _skip_pending


def take_skip():
    """Consume the flag. True once per time it was said."""
    global _skip_pending
    if not _skip_pending:
        return False
    _skip_pending = False
    return True


def take_move():
    """Scan, then consume the move flag. True once per time it was said.

    Unlike skip, there is no separate poller: a move is spent by whoever
    leaves the spot, and nobody else needs to know it is pending. Scanning
    here keeps it as safe to call from a travel wait as poll_skip is.
    """
    global _move_pending
    scan_journal()
    if not _move_pending:
        return False
    _move_pending = False
    return True


# What the script believes it is doing, for the heartbeat. A stall that says
# "mining area spot 3/14" is a different bug from one that says "waiting for
# mana", and until now neither said anything.
_phase = ["starting up"]


def phase(text):
    """Record what is happening. Cheap - no logging, just a breadcrumb."""
    _phase[0] = text


def heartbeat():
    """Say what we are doing if nothing has been said for a while.

    Hooked into interruptible_pause, which nearly every wait goes through, so
    silence is bounded even inside an operation that logs nothing of its own.
    """
    if not HEARTBEAT_MS:
        return
    quiet = (time.time() - _last_line["at"]) * 1000.0
    if quiet >= HEARTBEAT_MS:
        log("still working: %s (%ds without a word)"
            % (_phase[0], quiet / 1000.0), HUE_INFO)


def bail_requested():
    """Has a "skip" or "move" been said? Does NOT consume it.

    Long helpers call this so a spoken command is honoured from ANYWHERE, not
    only from a walk or a spot loop. Consumption stays with the code that acts
    on it structurally - mine_sweep for skip, the spot loops for move - so
    checking here cannot swallow the word before that code sees it.
    """
    if not BAIL_ON_COMMAND:
        return False
    scan_journal()
    return bool(_skip_pending or _move_pending)


def forget_move():
    """Drop a pending move. Called when the route recalls anyway, so a move
    said just as a rune ended does not eat the first spot of the next one."""
    global _move_pending
    _move_pending = False


def is_greyskull_line(raw):
    """True for a call-out line from an allowed caller on an allowed channel.

    One line at a time. This used to own the journal loop; it does not any
    more, because the cursor can only be read once and every trigger has to
    share that one pass. See scan_journal.
    """
    low = raw.lower()
    matched = None
    for phrase in GREYSKULL_PHRASES:
        phrase = phrase.strip().lower()
        if phrase and phrase in low:
            matched = phrase
            break
    if matched is None:
        return False

    channel, caller, _said = parse_chat_line(raw)
    if not channel_allowed(channel):
        debug("Greyskull ignored - wrong channel (%s)." % (channel or "none"))
        return False
    if not caller_allowed(caller):
        debug("Greyskull ignored - caller not allowed (%s)."
              % (caller or "unknown"))
        return False

    log("Greyskull called by %s%s."
        % (caller or "someone", " in %s" % channel if channel else ""),
        HUE_GOOD)
    return True


def poll_greyskull():
    """Raise the flag only. Safe to call from anywhere, including travel waits.

    THE SCAN IS UNCONDITIONAL. It used to return early while a Greyskull call
    was active - and since interruptible_pause's only scan went through here,
    that meant nothing read the journal for the whole excursion, so a spoken
    "skip" or "move" during one was never seen at all. Only the greyskull
    ANSWER is suppressed while one is already running; the reading is not.
    """
    scan_journal()
    if _greyskull_active:
        return False
    return _greyskull_pending


def interruptible_pause(total_ms, slice_ms=250):
    """Misc.Pause that keeps listening for the call-out."""
    remaining = int(total_ms)
    while remaining > 0:
        step = min(slice_ms, remaining)
        Misc.Pause(step)
        remaining -= step
        # Scan DIRECTLY rather than through poll_greyskull. One pass feeds
        # every trigger - the call-out, "skip" and "move" - and routing it
        # through a poller that can decline to scan is what hid them.
        scan_journal()
        heartbeat()


def checkGreyskull():
    """Act on the flag. Never call from inside a travel routine."""
    global _greyskull_pending, _greyskull_active

    if not poll_greyskull():
        return False

    _greyskull_pending = False
    _greyskull_active = True
    try:
        log("Greyskull - interrupting harvest and recalling to the Arcane "
            "Circle.", HUE_GOOD)
        Player.HeadMessage(55, "Pausing all harvesting...")
        Target.Cancel()
        Misc.Pause(600)

        if not goFolders(ARCANE_FOLDER):
            log("Could not reach the Arcane folder in the runebook.", HUE_BAD)
        elif not goDest(ARCANE_POINT):
            log("Could not recall to '%s' in the Arcane folder." % ARCANE_POINT,
                HUE_BAD)
        else:
            log("At the Arcane Circle - holding.", HUE_GOOD)
            Misc.Pause(GREYSKULL_HOLD_MS)
    finally:
        _greyskull_active = False
    return True


# =============================================================================
# MANA / MEDITATION
# =============================================================================

def hands_are_free():
    return (Player.GetItemOnLayer("RightHand") is None and
            Player.GetItemOnLayer("LeftHand") is None)


def free_hands():
    """Stow anything held. True if hands end up free."""
    for layer in ("RightHand", "LeftHand"):
        item = Player.GetItemOnLayer(layer)
        if item is not None:
            debug("Stowing %s to free hands." % (safe_name(item) or "an item"))
            Items.Move(item.Serial, Player.Backpack.Serial, -1)
            Misc.Pause(HAND_MOVE_PAUSE)
    return hands_are_free()


def mana_goal(minimum):
    if _greyskull_pending:
        return minimum
    if MANA_TARGET > 0:
        return max(minimum, min(MANA_TARGET, Player.ManaMax))
    return max(minimum, Player.ManaMax)


def passive_regen(deadline, minimum):
    global _passive_notice_shown
    if not _passive_notice_shown:
        log("Waiting on passive mana regeneration.", HUE_WARN)
        _passive_notice_shown = True
    while time.time() < deadline and Player.Mana < minimum:
        if Player.IsGhost:
            return False
        interruptible_pause(MEDITATION_POLL)
    return Player.Mana >= minimum


def ensure_mana(minimum=None, reason="travel"):
    """Meditate until there is enough mana. True if the threshold was reached."""
    phase("waiting for mana")
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

    # Deliberately NOT disarming up front. Meditation usually starts fine with a
    # tool in hand, and stowing the axe pre-emptively meant every low-mana moment
    # put the harvesting tool back in the pack. Hands are only freed if the
    # server actually complains (MED_HANDS), below.

    while time.time() < deadline and Player.Mana < goal:
        # MEDITATION_TIMEOUT is 90 seconds, and this is reached on every
        # recall. Standing here uninterruptibly is most of what "he is stuck
        # and I cannot make him move on" turned out to mean.
        if bail_requested():
            log("Mana wait cut short - a command was said.", HUE_WARN)
            return False
        if Player.IsGhost:
            return False

        clear_journal(MED_ALL)
        Player.UseSkill("Meditation")
        interruptible_pause(1200)

        if Journal.Search(MED_ARMOR):
            log("Armour blocks meditation - passive regeneration only.", HUE_WARN)
            _armor_blocks_meditation = True
            return passive_regen(deadline, minimum)

        if Journal.Search(MED_HANDS):
            if DISARM_FOR_MEDITATION and free_hands():
                continue
            log("Hands are not free and cannot be emptied.", HUE_WARN)
            return passive_regen(deadline, minimum)

        if Journal.Search(MED_AT_PEACE):
            break

        if Journal.Search(MED_TRANCE):
            last = Player.Mana
            stalled = 0
            while time.time() < deadline and Player.Mana < goal:
                if bail_requested():
                    log("Meditation cut short - a command was said.", HUE_WARN)
                    return False
                interruptible_pause(MEDITATION_POLL)
                if Player.Mana > last:
                    last = Player.Mana
                    stalled = 0
                else:
                    stalled += 1
                    if stalled >= MEDITATION_STALL:
                        break
            continue

        interruptible_pause(MEDITATION_RETRY_MS)

    ok = Player.Mana >= minimum
    if ok:
        log("Mana %d/%d - continuing." % (Player.Mana, Player.ManaMax), HUE_GOOD)
    else:
        log("Gave up recovering mana at %d/%d." % (Player.Mana, Player.ManaMax),
            HUE_BAD)
    return ok


def travel_failed_for_mana():
    return journal_hit(MSG_NO_MANA)


# =============================================================================
# ACCOUNT RUNEBOOK
# =============================================================================

def openAR():
    phase("opening the runebook")
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
    buttons = []
    for piece in re.split(r"\}\s*\{", layout):
        if "button" in piece.lower():
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

    Entries are found by their "N. Name" text and paired with the page's entry
    buttons in display order, which works whether the shard numbers buttons
    per-page or continuously. A rune is followed by a coordinate line; a folder
    is not - that is the discriminator.
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
            continue
        if re.match(r"^\(\s*[-+]?\d", text):
            if entries:
                entries[-1]["coord"] = [int(x) for x in
                                        re.findall(r"[-+]?\d+", text)]
            continue
        found = re.match(r"^(\d+)\.\s*(.+)$", text)
        if found:
            entries.append({"index": int(found.group(1)),
                            "label": found.group(2).strip(),
                            "coord": None})

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
    """Yield (page, folders, destinations) for every page, from page 1.

    The page number is re-read after each step and the walk stops if it did not
    actually advance. Without that, a footer claiming more pages than the next
    button can deliver would re-parse the same page and duplicate every rune on
    it in the route.
    """
    if not openAR():
        return
    if not ar_goto_page(1):
        debug("Could not rewind the runebook to page 1.", HUE_WARN)

    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        folders, destinations = parse_ar_page()
        yield current, folders, destinations

        if current >= total:
            return
        if not ar_next_page():
            return
        moved, _total = ar_page_info()
        if moved <= current:
            debug("Runebook did not advance past page %d - stopping." % current,
                  HUE_WARN)
            return


def ar_find(target, want_dest):
    """Locate a folder or rune across every page. (page, button, name) or None.

    An exact case-insensitive match beats a substring match, and the whole book
    is searched before choosing - a book holding both "Taming Locations" and
    "TamingDeed" would otherwise resolve the wrong one.
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
    return exact or partial


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


def goFolders(folders):
    """Walk from the root into a folder path."""
    goDir()
    for folder in folders:
        if folder == '':
            continue
        if not goDir(folder):
            return False
    return True


def ar_recall(button, what):
    """Click a rune's entry button, recovering mana if the cast is refused."""
    clear_journal(MSG_NO_MANA)
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(1000)
    if not travel_failed_for_mana():
        return arrived()

    log("Recall to %s refused for mana - recovering and retrying." % what,
        HUE_WARN)
    clear_journal(MSG_NO_MANA)
    if not ensure_mana(reason="retry recall"):
        return False
    if not openAR():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(1000)
    if travel_failed_for_mana():
        return False
    return arrived()


def goDest(dest=None):
    """Recall to a named rune, searching every page."""
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


# --- per-job routes ---------------------------------------------------------

def goJobDir(job):
    """Enter a job's folder.

    The cached route is deliberately NOT cleared: a job returns here after every
    trip home, and the folder's contents have not changed. Keeping it preserves
    the waypoint position so the route resumes instead of restarting.
    """
    global _current_job
    _current_job = job
    return goFolders(job["folder"])


def build_routes(job):
    """Every rune in the job's folder, as (page, button, name), all pages."""
    routes = []
    for page, _folders, destinations in iter_ar_pages():
        for button in sorted(destinations):
            routes.append((page, button, destinations[button]['name']))
    _routes[job["name"]] = routes
    log("%s route: %d runes." % (job["name"], len(routes)),
        HUE_GOOD if routes else HUE_BAD)
    return routes


def ensure_route_view(job):
    """Make sure the gump shows the job's folder, not the root.

    Deliberately cheap - it reads the current page only. Walking every page here
    doubled the page-flipping on every single waypoint, because build_routes
    then walks them all again.
    """
    _folders, destinations = parse_ar_page()
    if destinations:
        return True
    debug("Runebook is not showing runes - re-entering %s." % job["name"])
    return goJobDir(job)


def ensure_routes(job):
    """The job's rune list, built once and cached."""
    routes = _routes.get(job["name"])
    if routes:
        return routes
    if not openAR():
        return []
    if not ensure_route_view(job):
        return []
    return build_routes(job)


def route_complete(job):
    """True once every rune in the job's folder has been worked this lap."""
    routes = _routes.get(job["name"]) or []
    if not routes:
        return False
    return _waypoint.get(job["name"], 0) >= len(routes)


def goNext(job):
    """Recall to the job's next waypoint, walking pages as needed."""
    if not ensure_mana(reason="recall to next %s waypoint" % job["name"]):
        return False
    if not openAR():
        return False
    if not ensure_route_view(job):
        return False

    routes = ensure_routes(job)
    if not routes:
        log("No runes in the %s folder. Run diag_ar_gump.py." % job["name"],
            HUE_BAD)
        return False

    # Said ONCE, the first time the mining route is known. MYTHRIL_WAYPOINTS is
    # written in runebook positions, and a number past the end of the book is a
    # silent no-op - the mythril runes would simply behave as ordinary rock and
    # look exactly like this feature was never switched on.
    if (job["name"] == "Mining" and MYTHRIL_ENABLED and MYTHRIL_WAYPOINTS
            and not _mythril_checked):
        _mythril_checked.append(True)
        highest = max(MYTHRIL_WAYPOINTS)
        if highest > len(routes):
            log("MYTHRIL_WAYPOINTS goes up to %d but the Mining folder only "
                "has %d rune(s) - everything past %d is ignored. Check the "
                "numbers against the 'Mining waypoint N/M' lines."
                % (highest, len(routes), len(routes)), HUE_BAD)
        else:
            log("Mythril: waypoints %s of %d, %ds per swing."
                % (mythril_range_text(), len(routes),
                   MYTHRIL_SWING_TIMEOUT / 1000), HUE_GOOD)

    index = _waypoint.get(job["name"], 0)
    if index >= len(routes):
        index = 0
        _lap_done[job["name"]] = True       # a full lap of the route is done
    page, button, name = routes[index]
    _waypoint[job["name"]] = index + 1

    if not ar_goto_page(page):
        log("Could not reach page %d of the %s folder." % (page, job["name"]),
            HUE_WARN)
        _routes.pop(job["name"], None)
        return False

    # Always logged, not debug: this is the line that shows whether a route is
    # actually progressing.
    log("%s waypoint %d/%d: %s"
        % (job["name"], index + 1, len(routes), name), HUE_INFO)

    # A "move" said as the last spot was ending has nothing left to act on
    # here - the area it referred to is gone. Left pending it would be spent
    # on the first spot of the NEXT rune, which is not what was asked for.
    forget_move()

    return ar_recall(button, name)


def goCurrent(job):
    """Recall to the waypoint already being worked, without advancing.

    Used after a trip home: the spot probably still has resources, so returning
    to it rather than skipping ahead is what keeps a heavy-resource route
    progressing properly.
    """
    if not ensure_mana(reason="return to the %s spot" % job["name"]):
        return False
    if not openAR():
        return False
    if not ensure_route_view(job):
        return False

    routes = _routes.get(job["name"])
    index = _waypoint.get(job["name"], 0) - 1
    if not routes or index < 0 or index >= len(routes):
        return goNext(job)

    page, button, name = routes[index]
    if not ar_goto_page(page):
        _routes.pop(job["name"], None)
        return False

    debug("%s resuming waypoint %d/%d: %s"
          % (job["name"], index + 1, len(routes), name))
    return ar_recall(button, name)


# =============================================================================
# PACK / WEIGHT
# =============================================================================

def pack_item_count():
    """(items, max_items) from the backpack's "Contents" line, or (0, 0).

    The properties are ASKED FOR first. Reading them cold returns an empty list
    whenever the client has not fetched them yet, which is what made this
    unreadable mid-run.
    """
    backpack = Player.Backpack
    if backpack is None:
        return 0, 0
    for _ in range(3):
        try:
            Items.WaitForProps(backpack, PROPS_TIMEOUT)
            props = Items.GetPropStringList(backpack)
        except Exception:
            props = []
        for prop in props or []:
            if "Contents" in prop:
                nums = [int(x) for x in re.findall(r"\d+", prop)]
                if len(nums) >= 2:
                    return nums[0], nums[1]
        Misc.Pause(200)
    return 0, 0


def pack_usage():
    """(items, max_items, weight, max_weight). Weight is never unknown.

    WEIGHT COMES FROM THE CHARACTER, not the backpack tooltip. Player.Weight /
    Player.MaxWeight is the real carry limit - 104 of 530 on a 140-strength
    character - whereas the backpack's own tooltip reports the CONTAINER's
    capacity, which reads "0/60000 Stones" and says nothing about what the
    character can lift.

    The tooltip is still used, but only for the item count, and it no longer
    decides anything on its own: a tooltip that has not loaded returns (0, 0)
    and the item check is simply skipped rather than being read as "full".
    """
    items, max_items = pack_item_count()
    try:
        weight = int(Player.Weight or 0)
        max_weight = int(Player.MaxWeight or 0)
    except Exception:
        weight, max_weight = 0, 0
    return items, max_items, weight, max_weight


# The heaviest single yield actually seen, per task. This is how the reserve
# stops being a guess: ore and logs weigh different amounts, shards change item
# weights, and a mining swing that hands over five ore is nothing like one that
# hands over one. Watching it costs a subtraction per swing.
_max_yield = {}


def note_yield(task, gained):
    """Record how much one swing added, in stones."""
    if gained <= 0:
        return
    if gained > _max_yield.get(task, 0):
        _max_yield[task] = gained
        debug("%s: heaviest yield so far is %d stone(s) - reserve now %d."
              % (task, gained, weight_reserve()))


def weight_reserve():
    """Stones of free carry weight to stop harvesting at.

    Big enough for one more yield of the heaviest thing seen, with a margin.
    Before anything has been measured this is just the configured floor.
    """
    seen = max(_max_yield.values()) if _max_yield else 0
    reserve = max(PACK_WEIGHT_RESERVE, int(seen * PACK_RESERVE_SAFETY))
    return min(reserve, PACK_RESERVE_MAX)


def weight_headroom():
    """(free stones, weight, max weight). Free is 0 when it cannot be read."""
    _items, _max_items, weight, max_weight = pack_usage()
    if not max_weight:
        return 0, weight, max_weight
    return max_weight - weight, weight, max_weight


def pack_has_room(threshold=None):
    """True while there is room to keep harvesting.

    Two different questions, answered two different ways:

    WEIGHT is a reserve, not a fraction. Harvesting should run until there is
    no room for one more yield - a fraction throws away everything above it,
    and at 0.6 a 495-stone character stored at 297 and left 198 stones of
    capacity unused on every single trip. `threshold` is still honoured when a
    caller passes one explicitly, because the job hand-over genuinely does want
    "start the next job under 15%", which is a fraction question.

    ITEM COUNT stays a fraction. It is a different failure - a pack full of
    gems, tools and deeds - and no key can fix it.

    An UNKNOWN measure never counts as full. Treating "I could not read it" as
    "the pack is full" is what had every character declaring a full pack at
    whatever waypoint it had reached and then recalling home forever, at a
    fifth of its carry weight - and it said so through debug(), so with
    debugging off there was nothing in the journal to explain it.

    The authority on a genuinely full pack is the SERVER: the harvest task
    reads its refusal out of the journal and returns "full". This is only for
    deciding whether unloading achieved anything.
    """
    items, max_items, weight, max_weight = pack_usage()

    if threshold is None:
        # The rule: store once PACK_STORE_AT of carry weight is used.
        if max_weight and weight >= max_weight * PACK_STORE_AT:
            log("Pack at %d%% by WEIGHT: %d of %d stones - storing."
                % (round(100.0 * weight / max_weight), weight, max_weight),
                HUE_INFO)
            return False
        # Backstop: one more yield would go over the top even though the
        # percentage has not been reached. Going over means the server refuses
        # the resource outright and it is lost, so this stops short.
        reserve = weight_reserve()
        if max_weight and (max_weight - weight) <= reserve:
            log("Pack full by WEIGHT: %d of %d stones, %d free, one more "
                "yield needs %d." % (weight, max_weight, max_weight - weight,
                                     reserve), HUE_INFO)
            return False
    elif max_weight and weight > max_weight * threshold:
        debug("pack over %d%% by WEIGHT: %d of %d"
              % (int(threshold * 100), weight, max_weight), HUE_WARN)
        return False

    count_limit = PACK_THRESHOLD if threshold is None else threshold
    if max_items and items > max_items * count_limit:
        # Said at WARNING level, not debug. A pack that is full on item count
        # while barely carrying any weight is the confusing case - it looks
        # like nothing is wrong - and the keys cannot help with it, because
        # what fills the count is gems, deeds and tools rather than resources.
        log("pack full by ITEM COUNT: %d of %d items (limit %d). Weight is "
            "only %d of %d, so the keys cannot fix this - it needs the chest."
            % (items, max_items, int(max_items * count_limit),
               weight, max_weight), HUE_WARN)
        return False

    if not max_weight and not max_items:
        log("Could not read pack weight OR item count - carrying on rather "
            "than recalling. If this repeats, say so.", HUE_WARN)
    return True


def hostiles_near():
    """Anything hostile within HOSTILE_RANGE tiles.

    RangeMax is essential here. Without it the filter reports every criminal,
    enemy or murderer anywhere the client can see - roughly 18-25 tiles - so a
    single wandering spawn kept the answer permanently True, and the caller
    skipped waypoint after waypoint until the route ran out.
    """
    if not ABORT_ON_HOSTILES:
        return False
    flt = Mobiles.Filter()
    flt.Enabled = True
    flt.RangeMax = HOSTILE_RANGE
    for notoriety in HOSTILE_NOTORIETIES:
        flt.Notorieties.Add(notoriety)
    flt.CheckLineOfSight = True
    found = Mobiles.ApplyFilter(flt)
    if not found:
        return False
    names = ", ".join(safe_name(m) or "0x%X" % m.Serial for m in found[:4])
    log("Hostile within %d tiles: %s" % (HOSTILE_RANGE, names), HUE_WARN)
    return True


# =============================================================================
# TOOLS
# =============================================================================

def find_shovel():
    return Items.FindByID(SHOVEL_ID, -1, Player.Backpack.Serial, False, False)


def tool_uses(item_id):
    total = 0
    for itm in Items.FindAllByID(item_id, -1, Player.Backpack.Serial, False, False):
        try:
            total += int(Items.GetPropValue(itm, "Uses Remaining"))
        except Exception:
            pass
    return total


def make_shovel():
    Items.UseItemByID(TINKER_ID, -1)
    Gumps.WaitForGump(TINKER_GUMP, 10000)
    Misc.Pause(10)
    Gumps.SendAction(TINKER_GUMP, 15)
    Misc.Pause(100)
    Gumps.WaitForGump(TINKER_GUMP, 10000)
    Misc.Pause(10)
    if tool_uses(TINKER_ID) < 10:
        Gumps.SendAction(TINKER_GUMP, 23)
        Misc.Pause(100)
        Gumps.WaitForGump(TINKER_GUMP, 10000)
        Misc.Pause(10)
    Gumps.SendAction(TINKER_GUMP, 72)
    Misc.Pause(100)
    Gumps.WaitForGump(TINKER_GUMP, 10000)
    Misc.Pause(10)
    Gumps.CloseGump(TINKER_GUMP)


def looks_like_axe(item):
    name = safe_name(item).lower()
    if not name:
        return False
    if not any(word in name for word in AXE_WORDS):
        return False
    if any(word in name for word in AXE_EXCLUDE):
        return False
    return True


def equip_to_hand(item):
    """Equip an item to a hand layer. True if it ended up equipped."""
    if item is None:
        return False
    held = Player.GetItemOnLayer("LeftHand")
    if held is not None and held.Serial == item.Serial:
        return True
    held = Player.GetItemOnLayer("RightHand")
    if held is not None and held.Serial == item.Serial:
        return True

    # NOTE: the second argument is a BOOLEAN (wait), not a timeout. The original
    # script passed 5000 here.
    Player.UnEquipItemByLayer("LeftHand", True)
    Player.UnEquipItemByLayer("RightHand", True)
    Misc.Pause(750)
    Player.EquipItem(item.Serial)
    Misc.Pause(750)

    for layer in ("LeftHand", "RightHand"):
        held = Player.GetItemOnLayer(layer)
        if held is not None and held.Serial == item.Serial:
            return True
    return False


def is_axe(item):
    """By graphic first, then by name. Graphics do not need props loaded."""
    if item is None:
        return False
    if getattr(item, "ItemID", None) in AXE_IDS:
        return True
    return looks_like_axe(item)


def find_axe():
    """An equipped axe, or one recovered from the pack and equipped.

    Four passes, cheapest and most reliable first. The name scan is LAST because
    an item's Name is often empty until its properties load - relying on it is
    what made this fail after meditation stowed the axe.
    """
    global _axe_serial

    # 1. Already in hand.
    for layer in ("LeftHand", "RightHand"):
        held = Player.GetItemOnLayer(layer)
        if held is not None and (is_axe(held) or held.Serial == _axe_serial):
            _axe_serial = held.Serial
            return held

    # 2. The exact axe used last time, wherever it ended up. Survives being
    #    stowed by free_hands() during meditation.
    if _axe_serial:
        item = Items.FindBySerial(_axe_serial)
        if item is not None and equip_to_hand(item):
            return item

    # 3. By graphic, in the pack. No dependence on names or Contains.
    for axe_id in AXE_IDS:
        item = Items.FindByID(axe_id, -1, Player.Backpack.Serial, False, False)
        if item is not None and equip_to_hand(item):
            _axe_serial = item.Serial
            return item

    # 4. Name scan, for anything shard-custom the graphic list misses.
    try:
        Items.WaitForContents(Player.Backpack, 3500)
    except Exception:
        pass
    try:
        contents = list(Player.Backpack.Contains or [])
    except Exception:
        contents = []
    for item in contents:
        if looks_like_axe(item) and equip_to_hand(item):
            _axe_serial = item.Serial
            return item

    log("No axe found. Pack holds: %s"
        % (", ".join(safe_name(i) or "0x%X" % i.ItemID
                     for i in contents[:15]) or "(could not read contents)"),
        HUE_BAD)
    return None


# =============================================================================
# RESTOCK / DROP-OFF
# =============================================================================

def find_restock(key):
    """Locate one storage entry. Serial first, then id/hue in pack or world."""
    if not key.get("enabled", True):
        return []
    serial = key.get("serial")
    if serial:
        item = Items.FindBySerial(serial)
        if item is not None:
            return [item]

    item_id = key.get("id")
    if not item_id:
        return []
    hue = key.get("hue", -1)

    if key.get("where") == "world":
        found = Items.FindAllByID(item_id, hue, -1, key.get("range", 3), False)
    else:
        found = Items.FindAllByID(item_id, hue, Player.Backpack.Serial,
                                  False, False)
    found = list(found or [])
    return match_by_name(key, found)


def match_by_name(key, found):
    """Narrow an id/hue match down by name, now that hue is not doing it.

    The hue used to be what told a key apart from anything else sharing its
    graphic. With hue -1 that guard is gone, so the name takes over. It is a
    NARROWING, never a widening: if the names reject everything, the unfiltered
    list is handed back rather than the key going missing - a shard that does
    not send a name must not cost you the key entirely.
    """
    names = [n.lower() for n in (key.get("names") or []) if n]
    if not names or len(found) <= 0:
        return found

    matched = []
    for item in found:
        text = item_text(item)
        if any(n in text for n in names):
            matched.append(item)

    if not matched:
        if len(found) > 1:
            log("%s: %d item(s) of graphic 0x%X but none named %s - using the "
                "first anyway. Check %s_NAMES."
                % (key.get("label", "?"), len(found), key.get("id", 0),
                   "/".join(names), key.get("label", "?").upper()), HUE_WARN)
        return found

    if len(matched) < len(found):
        debug("%s: %d of %d candidates matched by name."
              % (key.get("label", "?"), len(matched), len(found)))
    return matched


def item_is_on_player(item):
    """Is this item in the player's own containers rather than out in the world?

    Note RootContainer can report the backpack's item serial rather than the
    player's mobile serial, so both are accepted and the chain is walked.
    """
    if item is None:
        return False
    roots = [Player.Serial]
    backpack = Player.Backpack
    if backpack is not None:
        roots.append(backpack.Serial)

    if getattr(item, "RootContainer", None) in roots:
        return True

    parent = getattr(item, "Container", None)
    for _ in range(MAX_CONTAINER_DEPTH):
        if parent in roots:
            return True
        if not parent or parent <= 0:
            return False
        holder = Items.FindBySerial(parent)
        if holder is None:
            return False
        parent = holder.Container
    return False


def report_restock_keys():
    """Say at startup which key each entry actually resolved to.

    Colour is no longer part of the lookup, so this is the line that proves the
    right item was picked - it names the serial, the graphic and the hue of
    whatever was found, and says outright when an entry found nothing.
    """
    log("Storage keys:", HUE_INFO)
    for key in RESTOCK_KEYS:
        label = key.get("label", "?")
        if not key.get("enabled", True):
            log("  %-18s disabled" % label, HUE_INFO)
            continue
        found = find_restock(key)
        if not found:
            log("  %-18s NOT FOUND (graphic 0x%X, %s)"
                % (label, key.get("id", 0), key.get("where", "pack")), HUE_WARN)
            continue
        item = found[0]
        log("  %-18s 0x%X  graphic 0x%X  hue 0x%04X  %s%s"
            % (label, item.Serial, item.ItemID, item.Hue,
               safe_name(item) or "(no name)",
               "" if len(found) == 1 else "   (+%d more)" % (len(found) - 1)),
            HUE_GOOD)


def known_key(label):
    """Do we know which resources this key takes?"""
    return any(spec["label"] == label for spec in KEY_BACKED_IDS)


def key_has_work(label):
    """Is anything this key takes still in the backpack?

    A key that has already swallowed its resource does not need clicking
    again; one that has not is the reason the pack is still holding granite.
    """
    backpack = Player.Backpack
    if backpack is None:
        return False
    for spec in KEY_BACKED_IDS:
        if spec["label"] != label:
            continue
        for item_id in spec["ids"]:
            try:
                found = Items.FindAllByID(item_id, -1, backpack.Serial,
                                          False, False)
            except Exception:
                continue
            if found:
                return True
    return False


def any_key_has_work():
    """Is any key-backed resource still sitting in the pack?"""
    for spec in KEY_BACKED_IDS:
        if key_has_work(spec["label"]):
            return True
    return False


def keys_in_reach(wanted=None):
    """Labels of the RESTOCK_KEYS entries whose item can actually be found.

    This is what decides whether the chest is allowed to sweep a resource. A
    key in the pack means that resource has somewhere better to go, and the
    chest is a one-way trip - so "is the key here" has to be answered before
    anything is moved, not inferred from whether the restock emptied the pack.

    A restock can legitimately leave things behind: it stops as soon as the
    pack has room, so the last key never runs if an earlier one freed enough.
    """
    found = set()
    for key in RESTOCK_KEYS:
        label = key.get("label")
        if wanted is not None and label not in wanted:
            continue
        if label in found:
            continue
        for item in find_restock(key):
            if key.get("where") == "world" or item_is_on_player(item):
                found.add(label)
            break
    return found


def chest_sweep_ids():
    """PURGE_ID minus anything whose key is here to take it.

    Returns (ids, blocked_labels) so the caller can say what it is holding
    back and why - a resource quietly not going to the chest looks exactly
    like a resource that was missed.
    """
    here = keys_in_reach(set(spec["label"] for spec in KEY_BACKED_IDS))
    blocked = set()
    kept = []
    for spec in KEY_BACKED_IDS:
        if spec["label"] in here:
            blocked.update(spec["ids"])
            kept.append(spec["label"])
    return [i for i in PURGE_ID if i not in blocked], kept, here


def refill_keys(on_player_only=False):
    """Push harvested resources into any storage in reach.

    `on_player_only` restricts this to storage actually carried in the pack, so
    a key in your pocket empties on the spot and no trip to the drop-off is
    made. Where the item really is decides this, not the WOOD_STORAGE_WHERE
    setting - carry the key and it just works.

    True once the pack has room again.
    """
    phase("emptying into the keys")
    # NOT "return True if the pack has room". Every key with something of its
    # own still in the pack gets a turn.
    #
    # This used to stop at the first key that freed enough space, and the
    # Stone Storage is last in the list. Ingots are heavy, so the Ingot key
    # emptied the pack and the run ended - granite was never offered to its
    # key at all. It then sat in the pack for ever, because KEY_BACKED_IDS
    # (rightly) keeps it out of the one-way chest as well. Stranded either way.
    if pack_has_room() and not any_key_has_work():
        return True

    used = False
    for key in RESTOCK_KEYS:
        for item in find_restock(key):
            label = key.get("label") or "0x%X" % item.Serial
            carried = item_is_on_player(item)
            if on_player_only and not carried:
                debug("%s is not in the pack - leaving it for the drop-off."
                      % label)
                continue
            # Once there is room, only keys that still have their OWN resource
            # in the pack are worth clicking. A key we know nothing about is
            # offered anyway, exactly as before.
            if pack_has_room() and known_key(label) and not key_has_work(label):
                continue
            wanted = list(key.get("context") or []) + list(RESTOCK_CONTEXT)
            if context_select(item, wanted, label):
                used = True
                Misc.Pause(1200)
                if not key_has_work(label):
                    log("%s took the load%s." %
                        (label, " (carried - no trip home)" if carried else ""),
                        HUE_GOOD)
                else:
                    log("%s still has %s in the pack after restocking - check "
                        "its menu entry (%s)."
                        % (label, label.lower(), "/".join(wanted)), HUE_WARN)
    if not used:
        # This was silent before, and silence here looks exactly like a script
        # that is working: the pack simply fills up and nothing says why.
        labels = ", ".join(k.get("label", "?") for k in RESTOCK_KEYS
                           if k.get("enabled", True))
        log("NOTHING took the load - no storage %s. Tried: %s. Check the "
            "'Storage keys:' lines printed at startup."
            % ("in the pack" if on_player_only else "in reach", labels),
            HUE_WARN)
    elif not pack_has_room():
        log("A key was used but the pack is STILL full - it may be full "
            "itself, or the '%s' entry may be the wrong menu item."
            % "/".join(RESTOCK_CONTEXT), HUE_WARN)
    return pack_has_room()


def smelt():
    phase("smelting")
    forge = Items.FindByID(FORGE_ID, -1, Player.Backpack.Serial, False, False)
    if forge is None:
        return
    leftovers = {}
    for ore in Items.FindAllByID(ORE_ID, -1, Player.Backpack.Serial, False, False):
        try:
            weight = int(Items.GetPropValue(ore, "Weight"))
        except Exception:
            continue
        if ore.ItemID == 0x19B7 and weight < 3:
            leftovers.setdefault(ore.Hue, []).append(ore.Serial)
        if weight >= 3:
            # EVERY cursor goes through clear_cursor first. Target.WaitForTarget
            # returns True for a cursor that is ALREADY open, so one left over
            # from the previous ore is answered instead of this one - and the
            # leaked cursor then eats the MINING TOOL's target, after which the
            # character stands there swinging at nothing and nothing is logged.
            #
            # This was survivable while smelt() only ran when the keys had
            # refused the load. It runs on every full pack now, so the leak
            # went from rare to routine.
            clear_cursor()
            Items.UseItem(ore)
            if not Target.WaitForTarget(5000, True):
                log("Smelt: no target cursor for ore 0x%X - skipped."
                    % ore.Serial, HUE_WARN)
                clear_cursor()
                continue
            Misc.Pause(250)
            Target.TargetExecute(forge)
            Misc.Pause(250)

    # Never leave this function with a cursor open, whatever happened above.
    clear_cursor()

    for hue in leftovers:
        if len(leftovers[hue]) > 1:
            Items.Move(leftovers[hue][0], Player.Backpack.Serial, -1)
            Misc.Pause(750)


def unload_in_place(threshold=None):
    """Empty the pack where you stand, if that is possible at all.

    ORDER MATTERS, and getting it wrong caused two separate complaints.

    1. SMELT FIRST. Ore is not what the keys take - the Ingot key wants
       ingots - so offering a pack of ore to the keys gets it refused, and the
       ore is then carted home to the chest while the key that would have
       swallowed it sits unused in the pack.

    2. THEN ASK AGAIN. Once the ore is ingots the pack is far lighter, so
       whether a trip home is needed at all has to be re-checked. Calling
       dropoff() unconditionally after a smelt is what sent the character home
       with a nearly empty pack after every single smelt.

    `threshold` is passed through to pack_has_room, so the stricter job
    handover level can use the same sequence.

    True if the pack has room and the caller can carry on where it stands.
    """
    smelt()
    if pack_has_room(threshold):
        return True

    # Now there are ingots for the Ingot key to take.
    refill_keys(on_player_only=True)
    return pack_has_room(threshold)


def house_deposit(spec):
    """Empty one order book.

    The context entry does all the work - it takes everything of that type at
    once, exactly like every other key. No amount is sent: the book's text field
    is for withdrawing, so writing to it could pull items back out.
    """
    label = spec.get("label") or "0x%X" % spec.get("serial", 0)
    serial = spec.get("serial")
    if not serial:
        log("%s: no serial configured." % label, HUE_BAD)
        return False

    item = Items.FindBySerial(serial)
    if item is None:
        log("%s: book 0x%X is not in range of %s."
            % (label, serial, DROP_POINT), HUE_BAD)
        return False

    # Both books share one gump id, so a window left open by the previous
    # deposit has to go before this one is answered.
    if HOUSE_DEPOSIT_GUMP:
        clear_stale_gumps([HOUSE_DEPOSIT_GUMP])

    if not context_select(item, HOUSE_DEPOSIT_CONTEXT, label):
        return False

    Misc.Pause(HOUSE_DEPOSIT_PAUSE)

    # Put the book's window away rather than answering it.
    if HOUSE_DEPOSIT_GUMP:
        try:
            if has_gump(HOUSE_DEPOSIT_GUMP):
                Gumps.CloseGump(HOUSE_DEPOSIT_GUMP)
                Misc.Pause(300)
        except Exception:
            pass

    log("%s: handed in." % label, HUE_GOOD)
    return True


def house_deposits():
    """Every enabled order book. Returns how many succeeded."""
    done = 0
    for spec in HOUSE_DEPOSITS:
        if not spec.get("enabled", True):
            continue
        if house_deposit(spec):
            done += 1
    return done


def item_text(item):
    """Name + tooltip of an item, lowercased."""
    parts = []
    name = safe_name(item)
    if name:
        parts.append(name)
    try:
        Items.WaitForProps(item, PROPS_TIMEOUT)
        props = Items.GetPropStringList(item)
        parts.extend(p for p in (props or []) if p)
    except Exception:
        pass
    return " ".join(parts).lower()


def deeds_in_book(book):
    """The "Deeds In Book: N" count, or None if the tooltip does not say."""
    found = re.search(r"deeds in book\s*:\s*(\d+)", item_text(book))
    return int(found.group(1)) if found else None


def is_bulk_order(item):
    """Is this a bulk order deed rather than a taming or resource order?

    They share ItemID 0x2258, so the tooltip decides.
    """
    text = item_text(item)
    for banned in BOD_EXCLUDE_TEXT:
        if banned.strip().lower() in text:
            debug("Skipping %s - tooltip says %r, that belongs in an order book."
                  % (safe_name(item) or "0x%X" % item.Serial, banned))
            return False
    if not BOD_REQUIRE_TEXT:
        return True
    for wanted in BOD_REQUIRE_TEXT:
        if wanted.strip().lower() in text:
            return True
    debug("Skipping %s - tooltip matches none of %s."
          % (safe_name(item) or "0x%X" % item.Serial, BOD_REQUIRE_TEXT))
    return False


def find_bod_book():
    """(book, how) - the character's Bulk Order Book, or (None, reason).

    Per-character map first, then an explicit serial, then whatever book is in
    the pack. The last one is what lets several characters share one script
    unedited.
    """
    name = (Player.Name or "").strip().lower()
    for who, serial in BOD_BOOK_BY_CHARACTER.items():
        if who.strip().lower() == name:
            book = Items.FindBySerial(serial)
            if book is not None:
                return book, "configured for %s" % Player.Name
            return None, ("book 0x%X configured for %s is not in your pack"
                          % (serial, Player.Name))

    if BOD_BOOK_SERIAL:
        book = Items.FindBySerial(BOD_BOOK_SERIAL)
        if book is not None:
            return book, "BOD_BOOK_SERIAL"
        return None, "BOD_BOOK_SERIAL 0x%X is not in your pack" % BOD_BOOK_SERIAL

    if BOD_BOOK_ID:
        book = Items.FindByID(BOD_BOOK_ID, -1, Player.Backpack.Serial,
                              False, False)
        if book is not None:
            return book, "found in your pack by graphic 0x%X" % BOD_BOOK_ID
        return None, ("no item of graphic 0x%X in your pack" % BOD_BOOK_ID)

    return None, "no book configured"


def file_bulk_orders():
    """Drag loose bulk order deeds into the carried Bulk Order Book.

    Runs after HOUSE_DEPOSITS so the taming and resource orders have already
    been taken out of the pack by "Refill from stock".
    """
    if not BOD_ENABLED:
        return 0

    book, how = find_bod_book()
    if book is None:
        log("No Bulk Order Book: %s." % how, HUE_BAD)
        return 0
    debug("Bulk Order Book 0x%X (%s)." % (book.Serial, how))

    deeds = Items.FindAllByID(BOD_DEED_IDS, -1, Player.Backpack.Serial,
                              False, False)
    if not deeds:
        debug("No loose bulk order deeds in the pack.")
        return 0

    before = deeds_in_book(book)
    filed = 0

    for deed in list(deeds)[:BOD_MAX_PER_RUN]:
        if deed.Serial == book.Serial:
            continue
        if not is_bulk_order(deed):
            continue
        log("Filing %s into the Bulk Order Book."
            % (safe_name(deed) or "0x%X" % deed.Serial), HUE_INFO)
        Items.Move(deed.Serial, book.Serial, -1)
        Misc.Pause(BOD_MOVE_PAUSE)
        filed += 1

    if filed:
        after = deeds_in_book(book)
        if before is not None and after is not None:
            log("Bulk Order Book: %d -> %d deeds (%d filed)."
                % (before, after, filed),
                HUE_GOOD if after > before else HUE_WARN)
            if after == before:
                log("The count did not change - the book may be full or may "
                    "have rejected them.", HUE_WARN)
        else:
            log("Filed %d deed(s) into the Bulk Order Book." % filed, HUE_GOOD)
    return filed


def dropoff():
    phase("trip home to unload")
    log("Drop-off run.", HUE_INFO)
    if not goFolders(DROP_FOLDER):
        log("Could not reach the drop-off folder.", HUE_BAD)
        return False
    if not goDest(DROP_POINT):
        log("Could not recall to the drop-off point.", HUE_BAD)
        return False

    # SMELT FIRST. Ore is in neither PURGE_ID nor anything a key accepts, so
    # ore that reaches home has nowhere to go at all: the Ingot key wants
    # ingots and the chest sweep does not list ore. It then sits in the pack,
    # the pack stays full, and the next lap recalls home again to do nothing.
    smelt()

    # Specific consumers get first refusal, the chest sweeps what is left.
    # The Wood Storage is locked down here and is meant to take the wood, and
    # PURGE_ID also lists logs and boards - running the chest first would sweep
    # them away before the storage ever saw them. Same for the order books.
    refill_keys()
    house_deposits()
    # After the order books have taken theirs - what is left on 0x2258 is a
    # genuine bulk order deed.
    file_bulk_orders()

    # What the chest is allowed to take. Anything with a key here to hold it
    # is left alone: the chest is one-way, and the key is where it belongs.
    sweep_ids, kept_by_keys, keys_here = chest_sweep_ids()
    for spec in KEY_BACKED_IDS:
        if spec["label"] in kept_by_keys:
            log("%s is here - its resources stay OUT of the chest."
                % spec["label"], HUE_GOOD)
        else:
            log("%s not found - its resources will go to the chest instead."
                % spec["label"], HUE_WARN)

    if not sweep_ids:
        log("Every purgeable resource has a key - nothing for the chest.")
    for itm in Items.FindAllByID(sweep_ids, -1, Player.Backpack.Serial,
                                 False, False):
        if itm.ItemID == 0x1BF2 and itm.Hue == 0:
            move = max(0, itm.Amount - KEEP_INGOTS)
            if move > 0:
                Items.Move(itm.Serial, DROP_CHEST_SERIAL, move)
        else:
            Items.Move(itm.Serial, DROP_CHEST_SERIAL, -1)
        Misc.Pause(1000)

    Timer.Create("harvest drop", DROP_INTERVAL_MS)
    if not pack_has_room():
        log("Pack is still full after the drop-off run.", HUE_WARN)
    return True


# =============================================================================
# VENDORS
# =============================================================================

def mobile_props(mob):
    """A mobile's tooltip lines, lowercased and joined. May be empty.

    Vendor titles live here rather than in the name: "Sherri" has the tooltip
    "Animal Trainer", "Edie" has "Scribe". Only the name is cheap to read, so
    this is called as a fallback.
    """
    try:
        Mobiles.WaitForProps(mob, PROPS_TIMEOUT)
        props = Mobiles.GetPropStringList(mob)
    except Exception:
        return ""
    return " ".join(p for p in (props or []) if p).lower()


def find_vendors(names, rng=VENDOR_RANGE):
    """Mobiles matching any of `names` by NAME or by TOOLTIP, case-insensitively.

    Two things the original got wrong:
      * Mobiles.Filter().Name is an exact match, so any renamed NPC vanished.
      * Matching only the name misses every vendor whose title is in the
        tooltip - which is most of them.
    """
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = rng
    found = Mobiles.ApplyFilter(f)
    if not found:
        return []

    wanted = [w.strip().lower() for w in names if w and w.strip()]
    if not wanted:
        return []

    out = []
    for mob in found:
        low = safe_name(mob).lower()
        if low and any(w in low for w in wanted):
            out.append(mob)
            continue
        props = mobile_props(mob)
        if props and any(w in props for w in wanted):
            debug("Matched %s by tooltip: %s"
                  % (safe_name(mob) or "0x%X" % mob.Serial, props[:60]))
            out.append(mob)

    # Nearest first, so the closest match is dealt with before any duplicate.
    try:
        out.sort(key=lambda m: Player.DistanceTo(m))
    except Exception:
        pass
    return out


def report_nearby_npcs(rng=VENDOR_RANGE):
    """List who is actually standing here, with their tooltips.

    Printed whenever a vendor lookup fails, so the real name and title are in
    the log without having to run a separate diagnostic.
    """
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = rng
    found = Mobiles.ApplyFilter(f)
    if not found:
        log("  nothing at all within %d tiles." % rng, HUE_WARN)
        return
    log("  who is here:", HUE_WARN)
    for mob in found:
        name = safe_name(mob) or "(unnamed)"
        props = mobile_props(mob)
        log("    %-28s %s" % (name, props[:70] or "(no tooltip)"), HUE_INFO)


def context_is_blocked(label):
    low = (label or "").lower()
    for banned in CONTEXT_NEVER:
        if banned.strip().lower() in low:
            return True
    return False


def context_select(entity, wanted, label_for_log=None):
    """Open an entity's context menu and pick the first configured entry.

    Used for both NPCs and storage containers.

    An EXACT label match is taken first and is always allowed - if it was
    configured verbatim, it was meant. Only then is a substring match tried, and
    that one refuses anything on CONTEXT_NEVER: vendor menus sit right next to
    Buy, Sell, Bribe and Train <skill>, all of which cost gold.
    """
    who = label_for_log or safe_name(entity) or "entity"

    entries = wait_context(entity)
    if not entries:
        log("%s gave no context menu." % who, HUE_WARN)
        return False

    labels = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        labels.append(text if text is not None else str(entry))
    debug("%s menu: %s" % (who, " | ".join(labels)))

    def reply(label):
        Misc.Pause(100)
        Misc.ContextReply(entity, label)   # send the real label, not our search
        Misc.Pause(600)
        return True

    for want in wanted:
        target = want.strip().lower()
        for label in labels:
            if (label or "").strip().lower() == target:
                return reply(label)

    for want in wanted:
        target = want.strip().lower()
        for label in labels:
            if target and target in (label or "").lower():
                if context_is_blocked(label):
                    debug("Refusing '%s' - it matches CONTEXT_NEVER." % label,
                          HUE_WARN)
                    continue
                return reply(label)

    log("%s has no entry matching %s - it offers: %s"
        % (who, wanted, " | ".join(labels)), HUE_BAD)
    return False


def talk_to(mob, wanted):
    return context_select(mob, wanted, safe_name(mob) or "vendor")


def gump_ids(vendor):
    spec = vendor.get("gump")
    if not spec:
        return []
    pairs = spec if isinstance(spec, list) else [spec]
    return [pair[0] for pair in pairs]


def clear_stale_gumps(ids):
    """Close any of these gumps that is already open.

    Gumps.WaitForGump returns True for a gump that is ALREADY open - the same
    trap as Target.WaitForTarget. A window left over from the previous vendor
    makes the script answer the wrong one, which is exactly the sort of
    intermittent failure that looks random.
    """
    for gump_id in ids:
        try:
            if has_gump(gump_id):
                debug("Closing a stale gump 0x%X before talking." % gump_id,
                      HUE_WARN)
                Gumps.CloseGump(gump_id)
                Misc.Pause(300)
        except Exception:
            pass
    try:
        Gumps.ResetGump()
    except Exception:
        pass


def answer_vendor_gump(vendor):
    """Answer the gump a vendor opens. True if there was nothing to do, or it
    was answered."""
    spec = vendor.get("gump")
    if not spec:
        return True

    pairs = spec if isinstance(spec, list) else [spec]
    for gump_id, button in pairs:
        if Gumps.WaitForGump(gump_id, VENDOR_GUMP_TIMEOUT):
            debug("%s: answering gump 0x%X button %d."
                  % (vendor["label"], gump_id, button))
            Gumps.SendAction(gump_id, button)
            Misc.Pause(700)
            return True

    # Report whatever DID open, so an unknown variant can be added to the list
    # without needing a separate diagnostic run.
    current = 0
    try:
        current = Gumps.CurrentGump()
    except Exception:
        pass
    expected = ", ".join("0x%X" % g for g, _b in pairs)
    if current and current not in [g for g, _b in pairs]:
        log("%s: expected gump %s but 0x%X opened instead. Add "
            "(0x%X, <button>) to this vendor's \"gump\" list."
            % (vendor["label"], expected, current, current), HUE_BAD)
    else:
        log("%s: expected gump %s - none appeared."
            % (vendor["label"], expected), HUE_BAD)
    return False


def vendor_window(vendor):
    return (vendor.get("window_ms", BOD_WINDOW_MS) or BOD_WINDOW_MS) / 1000.0


def vendor_limit(vendor):
    return vendor.get("per_window", BOD_REQUESTS_PER_WINDOW)


def vendor_due(vendor):
    """Is this NPC worth walking to right now?"""
    label = vendor["label"]
    now = time.time()

    ready_at = _vendor_ready_at.get(label)
    if ready_at and now < ready_at:
        return False

    window = vendor_window(vendor)
    history = [t for t in _vendor_history.get(label, []) if now - t < window]
    _vendor_history[label] = history
    return len(history) < vendor_limit(vendor)


def vendor_wait_text(vendor):
    """How long until this NPC is due, as something readable."""
    label = vendor["label"]
    now = time.time()

    waits = []
    ready_at = _vendor_ready_at.get(label)
    if ready_at and now < ready_at:
        waits.append(ready_at - now)

    window = vendor_window(vendor)
    history = sorted(t for t in _vendor_history.get(label, [])
                     if now - t < window)
    if len(history) >= vendor_limit(vendor):
        waits.append(history[0] + window - now)

    if not waits:
        return "due"
    seconds = max(waits)
    if seconds < 90:
        return "%ds" % int(seconds)
    if seconds < 5400:
        return "%dm" % int(seconds / 60)
    return "%.1fh" % (seconds / 3600.0)


def note_vendor_collected(vendor):
    """Record a successful order against this NPC's window budget."""
    global _collected_this_round
    _vendor_history.setdefault(vendor["label"], []).append(time.time())
    _vendor_ready_at.pop(vendor["label"], None)
    _collected_this_round += 1


def parse_reported_wait():
    """Seconds from an "available in about N minutes/hours" line, or None."""
    if not BOD_TRUST_REPORTED_WAIT:
        return None
    try:
        lines = [getattr(e, "Text", "") or ""
                 for e in (Journal.GetJournalEntry(0.0) or [])]
    except Exception:
        return None
    for line in lines:
        found = re.search(r"available in about\s+(\d+)\s*(minute|hour|second)",
                          line, re.I)
        if not found:
            continue
        amount = int(found.group(1))
        unit = found.group(2).lower()
        if unit.startswith("hour"):
            return amount * 3600
        if unit.startswith("minute"):
            return amount * 60
        return amount
    return None


def note_vendor_cooldown(vendor, seconds=None):
    """Park this NPC until it is worth asking again."""
    label = vendor["label"]
    if seconds is None:
        seconds = vendor_window(vendor)
    _vendor_ready_at[label] = time.time() + seconds
    return seconds


def expand_bod_locations():
    """Turn BOD_PROFESSIONS x BOD_LOCATIONS into vendor entries.

    A location listing professions explicitly marks them "required", so a
    missing one is reported. A location using "*" marks them optional, so the
    professions that are not there are skipped without noise.
    """
    if not BOD_ENABLED:
        return []

    out = []
    for loc in BOD_LOCATIONS:
        if not loc.get("enabled", True):
            continue
        where = loc.get("label") or loc.get("point") or "?"
        who = loc.get("who", "*")
        wildcard = (who == "*" or not who)
        wanted = sorted(BOD_PROFESSIONS) if wildcard else list(who)

        for key in wanted:
            spec = BOD_PROFESSIONS.get(key)
            if spec is None:
                log("BOD location %s lists unknown profession %r. Known: %s"
                    % (where, key, ", ".join(sorted(BOD_PROFESSIONS))), HUE_BAD)
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
    """The plain VENDORS table plus everything the BOD tables expand to.

    Entries marked "bod" drop out with BOD_ENABLED, wherever they are listed.
    """
    plain = [v for v in VENDORS if BOD_ENABLED or not v.get("bod")]
    return plain + expand_bod_locations()


def vendor_stops(vendors):
    """Group vendors by rune so each location is travelled to ONCE.

    Several NPCs commonly stand at one rune - the taming trainer and the scribe
    share "tameinscribe" - and visiting per-NPC meant recalling to the same spot
    two or three times per round.
    """
    stops = []
    for vendor in vendors:
        key = ("/".join(vendor["folder"]).strip().lower(),
               (vendor["point"] or "").strip().lower())
        for stop in stops:
            if stop["key"] == key:
                stop["vendors"].append(vendor)
                break
        else:
            stops.append({"key": key,
                          "folder": vendor["folder"],
                          "point": vendor["point"],
                          "vendors": [vendor]})
    return stops


def visit_stop(stop):
    """Travel to one rune and serve every vendor standing there."""
    labels = ", ".join(v["label"] for v in stop["vendors"])
    log("Stop %s -> %s: %s"
        % ("/".join(stop["folder"]) or "(root)", stop["point"], labels),
        HUE_INFO)

    if not goFolders(stop["folder"]):
        log("Could not reach folder %s." % "/".join(stop["folder"]), HUE_BAD)
        return False
    if not goDest(stop["point"]):
        log("Could not recall to '%s'." % stop["point"], HUE_BAD)
        return False
    Misc.Pause(500)

    served = 0
    for vendor in stop["vendors"]:
        if serve_vendor(vendor):
            served += 1
        poll_greyskull()
    return served > 0


def serve_vendor(vendor):
    """Deal with one NPC. Assumes we are already standing at its rune."""
    mobs = find_vendors(vendor["names"])
    if not mobs:
        if vendor.get("required", True):
            log("No NPC matching %s within %d tiles of %s."
                % (vendor["names"], VENDOR_RANGE, vendor["point"]), HUE_BAD)
            report_nearby_npcs()
        else:
            # A "*" location asks for everyone; most will not be here.
            debug("%s: not at this rune." % vendor["label"])
        return False

    ok = False
    for mob in mobs:
        for attempt in range(1, VENDOR_RETRIES + 1):
            clear_stale_gumps(gump_ids(vendor))
            clear_journal(BOD_COOLDOWN_MESSAGES)

            if not talk_to(mob, vendor["context"]):
                break

            # Being on the per-order timer is a normal answer, not a failure.
            # Retrying it just wastes a round trip.
            if journal_hit(BOD_COOLDOWN_MESSAGES):
                waited = note_vendor_cooldown(vendor, parse_reported_wait())
                log("%s: nothing yet, asking again in %s."
                    % (vendor["label"], vendor_wait_text(vendor)
                       if waited else "a while"), HUE_INFO)
                ok = True
                break

            if answer_vendor_gump(vendor):
                note_vendor_collected(vendor)
                log("%s: collected (%d/%d this window)."
                    % (vendor["label"],
                       len(_vendor_history.get(vendor["label"], [])),
                       vendor_limit(vendor)), HUE_GOOD)
                ok = True
                break
            log("%s: retrying (%d/%d)."
                % (vendor["label"], attempt, VENDOR_RETRIES), HUE_WARN)
            Misc.Pause(1200)

    if ok:
        log("%s: done." % vendor["label"], HUE_GOOD)
    return ok


def validate_vendors(vendors=None):
    """Report the vendor table and reject unusable entries."""
    if vendors is None:
        vendors = all_vendors()
    usable = []
    for index, vendor in enumerate(vendors):
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

        log("  %-22s %s -> %s   NPC: %s"
            % (label, "/".join(vendor["folder"]) or "(root)", vendor["point"],
               ", ".join(vendor["names"])), HUE_GOOD)
        usable.append(vendor)

    if not usable:
        log("No usable vendor stops - the vendor round will do nothing.", HUE_BAD)
    return usable


def vendor_round():
    """Visit every vendor that is due. Returns how many deeds were collected."""
    phase("vendor round")
    global _collected_this_round
    _collected_this_round = 0
    stops = vendor_stops(validate_vendors(all_vendors()))

    due_stops = []
    skipped = []
    for stop in stops:
        due = [v for v in stop["vendors"] if vendor_due(v)]
        if due:
            stop = dict(stop)
            stop["vendors"] = due
            due_stops.append(stop)
        else:
            skipped.append(stop)

    log("Vendor round: %d of %d stop(s) due."
        % (len(due_stops), len(stops)), HUE_INFO)
    for stop in skipped:
        # Not travelling is the whole point - these NPCs have nothing yet.
        debug("  skip %s/%s: %s" % ("/".join(stop["folder"]), stop["point"],
                                    ", ".join("%s in %s" % (v["label"],
                                                            vendor_wait_text(v))
                                              for v in stop["vendors"])))

    for stop in due_stops:
        visit_stop(stop)
        poll_greyskull()
    # Deeds are handed over here, so file them now rather than leaving them
    # loose in the pack until the next drop-off. The book is carried.
    file_bulk_orders()

    log("Vendor round collected %d deed(s)." % _collected_this_round,
        HUE_GOOD if _collected_this_round else HUE_INFO)
    return _collected_this_round


# =============================================================================
# HARVEST TASKS
#
# Each returns one of:
#   "ok"    something was harvested; stay on this spot
#   "next"  this spot is exhausted or unusable; move to the next waypoint
#   "full"  the pack is full
#   "stop"  cannot continue (no tool)
# =============================================================================

_mythril_checked = []     # one-shot latch for the route-length warning


def mythril_range_text():
    """"147-172" rather than twenty-six numbers, when they are contiguous."""
    nums = sorted(set(int(n) for n in MYTHRIL_WAYPOINTS))
    if not nums:
        return "(none)"
    if nums == list(range(nums[0], nums[-1] + 1)):
        return "%d-%d" % (nums[0], nums[-1])
    return ", ".join(str(n) for n in nums)


def in_mythril_zone():
    """Is the mining route currently on one of the mythril runes?

    _waypoint holds the NEXT index, and goNext sets it to index + 1 right
    before recalling - so it already equals the 1-based number printed in the
    "Mining waypoint N/M" line, which is what MYTHRIL_WAYPOINTS is written in.
    """
    if not MYTHRIL_ENABLED or not MYTHRIL_WAYPOINTS:
        return False
    return _waypoint.get("Mining", 0) in MYTHRIL_WAYPOINTS


def swing_timeout(mythril=None):
    """How long one swing gets. Mythril takes about 8s against 5s for rock."""
    if mythril is None:
        mythril = in_mythril_zone()
    return MYTHRIL_SWING_TIMEOUT if mythril else MINE_SWING_TIMEOUT


def dig_once(shovel, timeout_ms, mythril=None):
    """One swing at whatever rock is in reach. Returns what the SERVER said.

      "ok"       ore came out, or the swing missed and is worth repeating
      "miss"     the swing finished and produced nothing - mythril only, where
                 that is normal and must not read as "this spot is dead"
      "empty"    this 8x8 bank is mined out
      "notrock"  nothing mineable in reach at all
      "full"     the pack would not take it
      "broke"    the shovel wore out
      "silent"   no reply inside the timeout

    The original script matched a bare "You" and treated "You can't mine there"
    and "no metal" as the negative cases, and that crude test WORKED - so it is
    still here as the last resort. The specific strings are checked first only
    because the sweep needs to tell "this bank is empty, move one bank over"
    apart from "there is no rock here at all, never come back".
    """
    if mythril is None:
        mythril = in_mythril_zone()

    before = 0
    try:
        before = int(Player.Weight or 0)
    except Exception:
        pass

    clear_journal(MINE_ALL)
    Journal.Clear("You")
    if not clear_cursor():
        debug("Target cursor would not clear before mining.", HUE_WARN)
    Target.TargetResource(shovel, 0)

    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if journal_hit(MINE_TOOL_BROKE):
            return "broke"
        if journal_hit(MINE_PACK_FULL):
            return "full"
        if journal_hit(MINE_BAD_TARGET):
            return "notrock"

        # MYTHRIL FIRST, and specifically before the "You" catch-all below:
        # the failure line begins with "You", so the catch-all would score a
        # failed mythril swing as ore recovered and keep the spot alive on a
        # deadline it never earned.
        if journal_hit(MINE_MYTHRIL_DEPLETED):
            return "empty"
        if journal_hit(MINE_MYTHRIL_FAIL):
            return "miss"

        if journal_hit(MINE_DEPLETED):
            return "empty"
        if journal_hit(MINE_SUCCESS):
            note_yield("mine", weight_gain(before))
            return "ok"

        # A SUCCESSFUL MYTHRIL SWING SAYS NOTHING AT ALL - the ore just turns
        # up. So the pack getting heavier is the only evidence there is, and
        # without this the swing runs to the timeout and reports "silent".
        # Only trusted in a mythril zone: elsewhere the server always speaks,
        # and weight can move for reasons that are not this swing.
        if mythril and weight_gain(before) > 0:
            note_yield("mine", weight_gain(before))
            return "ok"

        if Journal.Search("You"):
            # The original catch-all. Anything else the server says starting
            # with "You" is a swing that happened.
            note_yield("mine", weight_gain(before))
            return "ok"
        interruptible_pause(100)

    # Last look before giving up. The ore can land in the same tick the
    # timeout expires, and calling that "silent" throws the swing away.
    if mythril and weight_gain(before) > 0:
        note_yield("mine", weight_gain(before))
        return "ok"
    return "silent"


def weight_gain(before):
    """Stones added since `before`. Negative readings are noise, not a yield."""
    try:
        return max(0, int(Player.Weight or 0) - int(before or 0))
    except Exception:
        return 0


def harvest_mine():
    """Mining. Works out from the rune a bank at a time, not one spot."""
    if not pack_has_room():
        return "full"

    shovel = find_shovel()
    if shovel is None:
        log("No shovel - making one.", HUE_WARN)
        make_shovel()
        shovel = find_shovel()
        if shovel is None:
            log("Still no shovel.", HUE_BAD)
            return "stop"

    if not MINE_AREA_ENABLED:
        return mine_single(shovel)
    return mine_sweep(shovel)


def mine_single(shovel):
    """The original one-spot behaviour, kept for MINE_AREA_ENABLED = False."""
    outcome = dig_once(shovel, swing_timeout())
    smelt()
    if outcome == "broke":
        log("Shovel worn out - making another.", HUE_WARN)
        make_shovel()
        return "ok"
    if outcome == "full":
        return "full"
    if outcome == "ok":
        return "ok"
    return "next"


def mineable_tile(x, y):
    """Is the tile at (x, y) mountain, cave or (optionally) sand?

    Checked as BOTH a land id and a static id. Mountains are land tiles on the
    overworld and statics inside dungeons, so asking only one of the two misses
    half the mines - and it misses them silently, as an empty candidate list.
    """
    tiles = MOUNTAIN_AND_CAVE_TILES
    try:
        world = Player.Map
        if Statics.GetLandID(x, y, world) in tiles:
            return True
        if MINE_AREA_INCLUDE_SAND and Statics.GetLandID(x, y, world) in SAND_TILES:
            return True
        for info in Statics.GetStaticsTileInfo(x, y, world) or []:
            static = getattr(info, "StaticID", None)
            if static in tiles:
                return True
            if MINE_AREA_INCLUDE_SAND and static in SAND_TILES:
                return True
    except Exception:
        # A tile lookup that throws must not stop the sweep - fall back to
        # "worth a try", which costs one probe swing and no more.
        return True
    return False


def spot_is_minable(x, y, reach=2):
    """Is there anything to mine within harvest range of standing at (x, y)?

    `reach` is the server's MaxRange for mining - 2, from Mining.cs. Checking
    the whole reachable square rather than the tile underfoot matters: you
    stand on cave FLOOR and mine the wall beside you, so the tile you are on is
    usually not itself a mountain tile.
    """
    for dx in range(-reach, reach + 1):
        for dy in range(-reach, reach + 1):
            if mineable_tile(x + dx, y + dy):
                return True
    return False


def mine_area_spots(origin):
    """Candidate mining spots around the landing point, nearest first.

    Only spots with mineable ground in reach are returned, so the character
    never walks 16 tiles to stand in an empty field. The landing tile is always
    first and is never filtered out - the rune was put there for a reason, and
    the server is the better judge of it than a tile list.
    """
    spots = area_spots(origin, MINE_AREA_RADIUS * 2, MINE_AREA_STEP)
    keep = [spots[0]]
    for spot in spots[1:]:
        if spot_is_minable(spot[0], spot[1]):
            keep.append(spot)
    return keep


def mine_sweep(shovel):
    """Work the current rock, then move a bank at a time to the next.

    Answers on the job runner's own terms - "ok" to be called again at this
    same waypoint, "next" when there is nothing left within MINE_AREA_RADIUS.
    """
    job_label = "Mining area"
    key = sweep_key()
    state = _mine_sweep.get(key)

    if state is None or state.get("origin") is None:
        origin = (Player.Position.X, Player.Position.Y)
        spots = mine_area_spots(origin)
        state = {"origin": origin, "spots": spots, "next": 0, "dead": set(),
                 "spent": set(), "dug": 0, "silent": 0,
                 "last_yield": time.time()}
        _mine_sweep[key] = state
        log("Mining area: %d spot(s) with mineable ground within %d tiles of "
            "%d,%d, %d apart." % (len(spots), MINE_AREA_RADIUS,
                                  origin[0], origin[1], MINE_AREA_STEP),
            HUE_STEP)
        if len(spots) == 1:
            log("  Only the landing tile looks mineable. If this rune is in a "
                "mine, MINE_AREA_INCLUDE_SAND or the tile lists may need a "
                "look - run with DEBUG on and report it.", HUE_WARN)
    else:
        spots = state["spots"]
        # Same as the lumber sweep: a trip home outlasts the idle limit, so the
        # clock restarts on re-entry rather than condemning the rune.
        note_area_yield(state)

    while state["next"] < len(spots):
        if poll_greyskull():
            return "ok"
        if hostiles_near():
            log("Mining area: something hostile turned up at spot %d/%d - "
                "leaving the rest." % (state["next"] + 1, len(spots)), HUE_WARN)
            end_sweep(state)
            return "next"

        if take_skip():
            log("Skipping the rest of this patch - on to the next rune.",
                HUE_GOOD)
            end_sweep(state)
            return "next"

        if area_is_idle(state):
            log("Mining area: nothing mined here in %ds - giving up on this "
                "rune and moving on. (%d of %d spots tried.)"
                % (AREA_IDLE_TIMEOUT_MS / 1000, state["next"], len(spots)),
                HUE_WARN)
            end_sweep(state)
            return "next"

        index = state["next"]
        spot = spots[index]
        phase("%s spot %d/%d at %d,%d"
              % (job_label, index + 1, len(spots), spot[0], spot[1]))

        if index in state["dead"]:
            state["next"] += 1
            continue

        if bank_of(spot[0], spot[1], MINE_BANK, MINE_BANK) in state["spent"]:
            debug("Mining area: spot %d/%d is in a bank already emptied - "
                  "skipping." % (index + 1, len(spots)))
            state["next"] += 1
            continue

        spot_deadline = time.time() + AREA_SPOT_TIMEOUT_MS / 1000.0

        if index > 0 and not walk_to(spot[0], spot[1],
                                     budget_ms(spot_deadline,
                                               MINE_AREA_MOVE_TIMEOUT)):
            debug("Mining area: could not reach spot %d/%d at %d,%d."
                  % (index + 1, len(spots), spot[0], spot[1]), HUE_WARN)
            state["dead"].add(index)
            state["next"] += 1
            continue

        outcome = mine_spot(shovel, index, len(spots), state, spot_deadline)
        if outcome in ("full", "stop"):
            return outcome
        state["next"] += 1

    log("Mining area done: %d swing%s gave ore, %d spot%s walked, %d barren%s."
        % (state["dug"], "" if state["dug"] == 1 else "s",
           state["next"], "" if state["next"] == 1 else "s",
           len(state["dead"]),
           "" if not state["silent"]
           else ", %d silent (see MINE_AREA_PROBE_TIMEOUT)" % state["silent"]),
        HUE_GOOD)
    end_sweep(state)
    state["spots"] = None
    return "next"


def mine_spot(shovel, index, total, state, deadline=None):
    """Dig at one spot until the bank is empty. "" / "full" / "stop"."""
    swings = 0
    got = 0

    # Measured from arrival and NEVER extended - see AREA_SPOT_HARD_CAP_MS.
    # `deadline` is the soft one and every productive swing pushes it out,
    # which is correct and is also why it cannot be the only bound.
    started = time.time()
    hard_stop = started + AREA_SPOT_HARD_CAP_MS / 1000.0
    spoke_at = started

    while swings < MINE_AREA_MAX_SWINGS:
        now = time.time()
        if now >= hard_stop:
            log("Mining area: %ds on spot %d/%d (%d swing(s), %d gave ore) - "
                "that is the hard cap, moving on."
                % (AREA_SPOT_HARD_CAP_MS / 1000, index + 1, total, swings, got),
                HUE_WARN)
            break
        if now - spoke_at >= AREA_PROGRESS_MS / 1000.0:
            spoke_at = now
            log("Mining area: still on spot %d/%d - %d swing(s), %d gave ore, "
                "%ds so far." % (index + 1, total, swings, got, now - started))
        if poll_skip():
            break
        if take_move():
            # Leave THIS spot only. The sweep advances to the next one; if
            # this was the last, the sweep runs out and recalls by itself.
            log("Mining area: moving on from spot %d/%d." % (index + 1, total))
            break
        if deadline is not None and time.time() >= deadline:
            log("Mining area: no ore from spot %d/%d in %ds - moving on."
                % (index + 1, total, AREA_SPOT_TIMEOUT_MS / 1000), HUE_WARN)
            break
        if not pack_has_room():
            return "full"

        mythril = in_mythril_zone()
        if mythril:
            # The probe timeout is tuned for a 5s swing and would cut an 8s
            # mythril swing off before it finished - which is the whole reason
            # these runes looked barren.
            timeout = MYTHRIL_SWING_TIMEOUT
        else:
            timeout = (MINE_AREA_PROBE_TIMEOUT if swings == 0
                       else MINE_SWING_TIMEOUT)
        outcome = dig_once(shovel, timeout, mythril=mythril)
        swings += 1

        if outcome == "ok":
            got += 1
            state["dug"] += 1
            note_area_yield(state)
            # Producing ore is not being stuck. Push the deadline out so the
            # bank is worked until the server says it is empty.
            if deadline is not None:
                deadline = time.time() + AREA_SPOT_TIMEOUT_MS / 1000.0
        elif outcome == "miss":
            # A mythril swing that finished and found nothing. That is the
            # NORMAL case there, not a dead spot - so keep swinging, and push
            # the deadline out because eight seconds of digging is real work.
            # Deliberately NOT counted in state["dug"]: that number is "swings
            # that gave ore" and the sweep summary would otherwise claim ore
            # that never arrived.
            if deadline is not None:
                deadline = time.time() + AREA_SPOT_TIMEOUT_MS / 1000.0
        elif outcome == "full":
            return "full"
        elif outcome == "broke":
            log("Shovel worn out - making another.", HUE_WARN)
            make_shovel()
            shovel = find_shovel()
            if shovel is None:
                log("Still no shovel.", HUE_BAD)
                return "stop"
            continue
        elif outcome == "empty":
            # The 8x8 bank is spent. Nothing else in it is worth a swing.
            state["spent"].add(bank_of(Player.Position.X, Player.Position.Y,
                                       MINE_BANK, MINE_BANK))
            break
        elif outcome == "notrock":
            if swings == 1:
                state["dead"].add(index)
            break
        elif outcome == "silent":
            if swings == 1:
                state["silent"] += 1
                debug("Mining area: spot %d/%d said nothing at all."
                      % (index + 1, total), HUE_WARN)
            break

        interruptible_pause(HARVEST_PAUSE)

    if got:
        debug("Mining area: spot %d/%d gave ore on %d swing(s)."
              % (index + 1, total, got))
    # Smelt where we stand. Ore is what fills the pack, and the forge is
    # carried - so turning it into ingots here is what keeps the sweep going
    # instead of ending it on a full pack.
    smelt()
    return ""


def chop_once(axe, timeout_ms):
    """One swing at whatever wood is in reach of where you are standing.

    Returns what the SERVER said, not what the job runner should do - the
    caller maps that, because a sweep and a single spot want different things
    out of the same answers:

      "ok"      wood came out, or the swing missed and is worth repeating
      "empty"   this tile is harvested out
      "notree"  nothing choppable in reach at all
      "full"    the pack would not take it
      "broke"   the axe broke
      "silent"  no reply inside the timeout
    """
    before = 0
    try:
        before = int(Player.Weight or 0)
    except Exception:
        pass

    clear_journal(LUMBER_ALL)
    if not clear_cursor():
        debug("Target cursor would not clear before chopping.", HUE_WARN)
    Target.TargetResource(axe, "wood")

    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if journal_hit(LUMBER_TOOL_BROKE):
            return "broke"
        if journal_hit(LUMBER_PACK_FULL):
            return "full"
        if journal_hit(LUMBER_DEPLETED):
            return "empty"
        if journal_hit(LUMBER_BAD_TARGET):
            return "notree"
        if journal_hit(LUMBER_SUCCESS) or journal_hit(LUMBER_RETRY):
            note_yield("lumber", weight_gain(before))
            return "ok"
        interruptible_pause(100)
    return "silent"


def area_offsets(size, step):
    """Standing-spot offsets along one axis, centred on 0.

    `size` is the whole edge of the box, so half of it is the reach in each
    direction; `step` is how far apart the spots sit. 8 and 3 give -3, 0, 3;
    36 and 8 give -16, -8, 0, 8, 16.
    """
    half = max(0, int(size) // 2)
    step = max(1, int(step))
    count = half // step
    return [k * step for k in range(-count, count + 1)]


def bank_of(x, y, width, height):
    """Which resource bank a tile belongs to.

    The bank is the unit the SERVER depletes: "there's not enough wood here"
    means every tile in that block is spent, not just the one targeted. Knowing
    the block lets the sweep walk straight past the rest of it instead of
    swinging at each tile in turn and being told the same thing every time.
    """
    return (int(x) // int(width), int(y) // int(height))


def spot_gap(a, b):
    """Tiles between two spots, the way UO measures range."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def lumber_area_spots(origin):
    """Every standing spot in the box, in walking order.

    The landing tile comes first - we are already on it, so that costs no
    walking and it keeps the tree the rune was placed for as the first thing
    cut, exactly as before this sweep existed.

    The rest are ordered nearest-first from wherever the walk has reached. A
    plain serpentine looks tidier but is wrong here: lifting the landing tile
    out of the middle of it leaves a hole, and the row it came from then jumps
    the full width of the box - 6 tiles on the default settings, which is two
    wasted walks per visit. Nearest-first has no hole to fall into and keeps
    every leg down to one LUMBER_AREA_STEP.
    """
    return area_spots(origin, LUMBER_AREA_SIZE,
                      LUMBER_AREA_STEP_X, LUMBER_AREA_STEP_Y)


def area_spots(origin, size, step_x, step_y=None):
    """The generic version. See lumber_area_spots for why the order is this.

    The two axes step separately because resource banks are not square: mining
    banks are 8x8, but lumber banks are 4 wide and only 3 tall.
    """
    if step_y is None:
        step_y = step_x
    ox, oy = origin
    xs = area_offsets(size, step_x)
    ys = area_offsets(size, step_y)
    grid = [(ox + dx, oy + dy) for dy in ys for dx in xs]

    spots = [origin]
    left = [s for s in grid if s != origin]
    here = origin
    while left:
        # Ties broken by straight-line distance then by position, so the order
        # is the same every visit - a sweep resumed after a trip home has to
        # pick up the list it left off in.
        left.sort(key=lambda s: (spot_gap(here, s),
                                 abs(s[0] - here[0]) + abs(s[1] - here[1]),
                                 s[1], s[0]))
        here = left.pop(0)
        spots.append(here)
    return spots


def player_ready():
    """Is the character actually IN the world right now?

    This exists because of a real ClassicUO bug. Its plugin entry point for
    movement has no null check:

        internal static bool RequestMove(int dir, bool run)
        {
            return Client.Game.UO.World.Player.Walk((Direction)dir, run);
        }

    - src/ClassicUO.Client/Network/Plugin.cs. The method right below it,
    GetPlayerPosition, DOES check `World.Player != null` first; RequestMove
    simply does not. So any plugin asking to move while the player object is
    momentarily gone takes the whole client down with

        System.NullReferenceException at ClassicUO.Network.Plugin.RequestMove

    World.Player is null across recalls, gate travel and world reloads, and
    this script recalls constantly and starts walking the moment it lands.
    That is the crash.

    It cannot be fixed from here - only avoided, by not asking to move until
    the character is really there.
    """
    try:
        if Player is None or int(Player.Serial or 0) == 0:
            return False
        spot = Player.Position
        if spot is None:
            return False
        # 0,0 is what an unloaded world reads as, not a real place to stand.
        return not (int(spot.X or 0) == 0 and int(spot.Y or 0) == 0)
    except Exception:
        return False


def wait_for_player(timeout_ms=PLAYER_READY_TIMEOUT_MS):
    """Block until the character is in the world again, or give up.

    Called after every recall. Walking into the gap between "the recall fired"
    and "the world finished loading" is what crashes the client.
    """
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if player_ready():
            return True
        Misc.Pause(PLAYER_READY_POLL_MS)
    log("The character is still not in the world after %dms - not moving."
        % timeout_ms, HUE_WARN)
    return False


def arrived():
    """Call this on EVERY path out of a recall that actually travelled.

    Always returns True - "the recall happened" - after blocking for the world
    to come back. It exists as its own function because the wait used to live
    on one branch of ar_recall and the successful first cast returned straight
    past it, so the guard covered only the rare mana-retry. That is the common
    case left unprotected, which is exactly the case that crashes.

    See player_ready() for why walking too early kills the client.
    """
    wait_for_player()
    return True


def pathfind_to(x, y):
    """Walk one leg towards a tile.

    Route.Timeout is set EXPLICITLY. Left unset it means no limit, and
    PathFinding.Go then blocks for as long as it wants - taking every guard in
    this file out of play, because they all run between calls to this function.
    A short leg timeout is what lets those guards exist at all.
    """
    # NEVER ask to move when the player object may be gone - see player_ready.
    if not player_ready():
        debug("Not in the world yet - holding off the move.", HUE_WARN)
        return False

    route = PathFinding.Route()
    route.X = x
    route.Y = y
    route.MaxRetry = 2
    route.StopIfStuck = True
    route.IgnoreMobile = True
    route.UseResync = True
    route.DebugMessage = False

    # Setting an attribute Razor's Route does not have raises, and this one is
    # NEW and unverified in game. A .NET-backed object also rejects a value of
    # the wrong type outright. Neither is worth taking the whole script down
    # for - without the timeout the guards are weaker, not broken.
    try:
        route.Timeout = PATH_LEG_TIMEOUT_S
    except Exception as err:
        global _timeout_warned
        if not _timeout_warned:
            _timeout_warned = True
            log("PathFinding.Route has no usable Timeout on this build (%s). "
                "Walking still works, but a stuck walk relies on the position "
                "watchdog rather than the leg timeout." % err, HUE_WARN)

    try:
        return PathFinding.Go(route)
    except Exception as err:
        # A pathfinder that throws must not end the run. It happens against
        # bad destinations, and the caller already treats "did not get there"
        # as an ordinary outcome.
        debug("PathFinding.Go failed for %d,%d: %s" % (x, y, err), HUE_WARN)
        return False


def land_is_walkable(x, y):
    """Is (x, y) real ground, or the black nothing beyond the map edge?

    The pathfinder will happily route THROUGH unexplored blackness - it reports
    a way that does not exist, the character walks into it and stops. Asking
    the land tile whether it is impassable is the cheap way to refuse those
    before committing to the walk.

    Unknown answers count as walkable: this is here to reject the obviously
    impossible, not to second-guess terrain the client does know about.
    """
    try:
        land = Statics.GetLandID(int(x), int(y), Player.Map)
        if land is None:
            return True
        if Statics.GetLandFlag(land, "Impassable"):
            return False
    except Exception:
        return True
    return True


# The tile the character was last seen on, and when. Movement is the only
# thing that proves a walk is working; a stuck one keeps issuing steps forever.
_timeout_warned = False
_stand_tile = None
_stand_since = 0.0


def seconds_on_this_tile():
    """How long the character has been on the exact same tile."""
    global _stand_tile, _stand_since
    here = (Player.Position.X, Player.Position.Y)
    now = time.time()
    if here != _stand_tile:
        _stand_tile = here
        _stand_since = now
        return 0.0
    return now - _stand_since


def tile_gap(x, y):
    """Tiles from the player to (x, y), the way UO measures range."""
    return max(abs(Player.Position.X - x), abs(Player.Position.Y - y))


def area_is_idle(state):
    """True once nothing has been harvested for AREA_IDLE_TIMEOUT_MS.

    Measured from the last swing that actually produced something, not from
    the start of the sweep, so a slow but productive area is never cut off.
    """
    last = state.get("last_yield")
    if not last:
        return False
    return (time.time() - last) * 1000.0 >= AREA_IDLE_TIMEOUT_MS


def note_area_yield(state):
    """Reset the idle clock. Called for every swing that produced something."""
    state["last_yield"] = time.time()


def budget_ms(deadline, most_ms):
    """Milliseconds left before `deadline`, capped at `most_ms`.

    Walking shares the spot's 15-second budget with swinging rather than having
    its own. Without this the two add up and the cap does not actually cap
    anything - the whole point is that the character is moving on 15 seconds
    after it commits to a spot, whatever it spent them doing.

    Never returns zero: a walk given no time at all reads as an instant
    failure, which would mark a perfectly good spot dead.
    """
    left = int((deadline - time.time()) * 1000.0)
    return max(500, min(int(most_ms), left))


def path_to(x, y):
    """The walkable path to a tile, or None if there is not one.

    PathFinding.GetPath runs the search WITHOUT moving the character, so this
    is the cheap question to ask before committing to a walk. Mobiles are
    ignored: something standing in the way is a moment's problem, not a reason
    to write the spot off.
    """
    try:
        path = PathFinding.GetPath(int(x), int(y), True)
    except Exception:
        return None
    if not path:
        return None
    try:
        return list(path)
    except Exception:
        return None


def reachable_spot(x, y, accept=None):
    """A tile at or near (x, y) that can actually be walked to, or None.

    Two separate ways a spot can be unreachable, both of them normal
    underground:

      * The spot itself is INSIDE the rock. The standing grid is arithmetic,
        so in a cave a good number of spots land in a wall. A tile beside it
        is usually open floor, which is why the accept radius is searched too
        rather than the spot being written off.

      * There is no sane way through. The next ore bank is 8 tiles off through
        solid mountain and the only path is 80 tiles around the outside. That
        is a REAL path, which is why "did GetPath return something" is not on
        its own the right question - anything past AREA_MAX_DETOUR times the
        direct distance is refused, because walking it leaves the mine.
    """
    if accept is None:
        accept = LUMBER_AREA_ARRIVE_ACCEPT

    candidates = [(int(x), int(y))]
    for radius in range(1, max(0, int(accept)) + 1):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) == radius:
                    candidates.append((int(x) + dx, int(y) + dy))

    for cx, cy in candidates:
        # Refuse the black nothing before asking the pathfinder, because the
        # pathfinder will cheerfully route into it.
        if not land_is_walkable(cx, cy):
            continue
        direct = tile_gap(cx, cy)
        path = path_to(cx, cy)
        if not path:
            continue
        if direct and len(path) > direct * AREA_MAX_DETOUR:
            debug("Path to %d,%d is %d steps for %d tiles - that is round the "
                  "mountain, not through it. Skipping."
                  % (cx, cy, len(path), direct))
            continue
        return (cx, cy)
    return None


def walk_to(x, y, timeout_ms=None, accept=None):
    """Walk to a tile, settling for `accept` tiles short of it.

    The destination is PATH-CHECKED before a single step is taken. Underground
    the standing grid regularly puts the next spot on the far side of a
    mountain wall, and walking at it just bounces off the rock until the
    timeout expires - which is what left a character shuffling against a cliff
    face instead of mining.

    PathFinding.Go also fails outright against a tile something is standing on,
    and a tree or a rock stops it a tile out, so "close enough" has to be an
    accepted outcome or every awkward spot costs the whole timeout.
    """
    if timeout_ms is None:
        timeout_ms = LUMBER_AREA_MOVE_TIMEOUT
    if accept is None:
        accept = LUMBER_AREA_ARRIVE_ACCEPT

    if tile_gap(x, y) <= accept:
        return True

    goal = reachable_spot(x, y, accept)
    if goal is None:
        debug("No way through to %d,%d - not attempting it." % (x, y))
        return False
    x, y = goal

    deadline = time.time() + timeout_ms / 1000.0
    best = None
    stalled = 0
    last = None
    stuck = 0

    while time.time() < deadline:
        if poll_skip():
            debug("Skip heard mid-walk - stopping.")
            return False
        if take_move():
            # Consumed, not polled. Leaving it set would have the move spent a
            # second time on the next spot - one word, two spots skipped.
            # A walk that returns False marks this spot dead and moves on,
            # which is exactly what was asked for.
            debug("Move heard mid-walk - abandoning this spot.")
            return False
        gap = tile_gap(x, y)
        if gap <= accept:
            return True

        # Progress is measured against the BEST distance reached, not the
        # previous one. A pathfinder working along a wall shuffles back and
        # forth, so "did I move" answers yes forever while "am I getting
        # closer" answers no - and only the second one is the truth.
        if best is None or gap < best:
            best = gap
            stalled = 0
        else:
            stalled += 1
            if stalled >= AREA_STALL_STEPS:
                debug("Stopped getting closer to %d,%d - stuck at %d tiles."
                      % (x, y, gap))
                return gap <= accept

        pathfind_to(x, y)

        # Rooted to one tile for this long while TRYING to walk means stuck,
        # whatever the pathfinder claims. This is the check that catches a
        # character wedged against terrain: it needs no theory about why.
        if seconds_on_this_tile() * 1000.0 >= AREA_STUCK_TIMEOUT_MS:
            log("Stuck on %d,%d for %ds while walking to %d,%d - giving up on "
                "that spot." % (Player.Position.X, Player.Position.Y,
                                AREA_STUCK_TIMEOUT_MS / 1000, x, y), HUE_WARN)
            return False

        here = (Player.Position.X, Player.Position.Y)
        if here == last:
            stuck += 1
            if stuck >= 2:
                return tile_gap(x, y) <= accept
        else:
            stuck = 0
            last = here
        interruptible_pause(200)

    return tile_gap(x, y) <= accept


# Sweep progress, keyed by (job name, waypoint index) rather than by position -
# the player walks away from the landing tile during a sweep, and a trip home
# for a full pack re-enters this function from wherever the unload left them.
#
# "dead" remembers the spots that answered "nothing choppable here", which is a
# property of the ground and will not change. A spot that was merely harvested
# out is NOT remembered: that grows back, and skipping it forever would quietly
# shrink the route.
_lumber_sweep = {}
_mine_sweep = {}


def sweep_key():
    """Identify the waypoint being worked, not the tile being stood on."""
    job = _current_job if isinstance(_current_job, dict) else {}
    name = job.get("name", "lumber")
    return (name, _waypoint.get(name, 0) - 1)


def forget_sweeps():
    """Drop all sweep memory, both jobs."""
    _lumber_sweep.clear()
    _mine_sweep.clear()


def harvest_lumber():
    """Lumberjacking. Works the whole area around the rune, not one tree."""
    if not pack_has_room():
        return "full"

    axe = find_axe()
    if axe is None:
        log("No axe or hatchet found in hand or pack.", HUE_BAD)
        return "stop"

    if not LUMBER_AREA_ENABLED:
        return lumber_single(axe)
    return lumber_sweep(axe)


def lumber_single(axe):
    """The original one-spot behaviour, kept for LUMBER_AREA_ENABLED = False."""
    outcome = chop_once(axe, LUMBER_SWING_TIMEOUT)
    if outcome == "broke":
        log("Axe broke - looking for another.", HUE_WARN)
        return "ok"
    if outcome == "full":
        return "full"
    if outcome == "ok":
        return "ok"
    if outcome == "notree":
        debug("Not a usable tree here.")
    elif outcome == "silent":
        debug("Chop timed out - moving on.")
    return "next"


def lumber_sweep(axe):
    """Walk the box around the landing tile, chopping at every standing spot.

    Answers on the job runner's own terms:
      "ok"    stopped part-way - come back to this same waypoint and carry on
      "next"  the whole area is worked out, recall onwards
      "full"  the pack is full
      "stop"  no axe left
    """
    job_label = "Lumber area"
    key = sweep_key()
    state = _lumber_sweep.get(key)

    if state is None or state.get("origin") is None:
        origin = (Player.Position.X, Player.Position.Y)
        state = {"origin": origin, "next": 0, "dead": set(), "spent": set(),
                 "cut": 0, "silent": 0, "last_yield": time.time()}
        _lumber_sweep[key] = state
        spots = lumber_area_spots(origin)
        log("Lumber area: %d standing spot(s) in a %dx%d box around %d,%d."
            % (len(spots), LUMBER_AREA_SIZE, LUMBER_AREA_SIZE,
               origin[0], origin[1]), HUE_STEP)
    else:
        spots = lumber_area_spots(state["origin"])
        # Restart the idle clock on every re-entry. A full pack sends the
        # character home and back, which takes far longer than the idle limit -
        # without this a PRODUCTIVE rune would be abandoned the moment it
        # returned, purely because the clock kept running during the trip.
        note_area_yield(state)
        if state["next"]:
            debug("Lumber area: resuming at spot %d/%d."
                  % (state["next"] + 1, len(spots)))

    while state["next"] < len(spots):
        # Polled, never acted on. This runs from inside walking, and the
        # call-out response travels; the job runner acts on the flag once we
        # have handed control back to it.
        if poll_greyskull():
            return "ok"
        if hostiles_near():
            log("Lumber area: something hostile turned up at spot %d/%d - "
                "leaving the rest of this patch."
                % (state["next"] + 1, len(spots)), HUE_WARN)
            end_sweep(state)
            return "next"

        if take_skip():
            log("Skipping the rest of this patch - on to the next rune.",
                HUE_GOOD)
            end_sweep(state)
            return "next"

        if area_is_idle(state):
            log("Lumber area: nothing harvested here in %ds - giving up on "
                "this rune and moving on. (%d of %d spots tried.)"
                % (AREA_IDLE_TIMEOUT_MS / 1000, state["next"], len(spots)),
                HUE_WARN)
            end_sweep(state)
            return "next"

        index = state["next"]
        spot = spots[index]
        phase("%s spot %d/%d at %d,%d"
              % (job_label, index + 1, len(spots), spot[0], spot[1]))

        if index in state["dead"]:
            state["next"] += 1
            continue

        # The server already said this block is empty. Walking into it to be
        # told again is exactly the standing-around this sweep was meant to
        # avoid - a lumber bank is 4x3, so several spots can share one.
        if bank_of(spot[0], spot[1],
                   LUMBER_BANK_W, LUMBER_BANK_H) in state["spent"]:
            debug("Lumber area: spot %d/%d is in a bank already emptied - "
                  "skipping." % (index + 1, len(spots)))
            state["next"] += 1
            continue

        # One budget covers walking there AND working it, so a spot can never
        # hold the character longer than this however it goes wrong.
        spot_deadline = time.time() + AREA_SPOT_TIMEOUT_MS / 1000.0

        if index > 0 and not walk_to(spot[0], spot[1],
                                     budget_ms(spot_deadline,
                                               LUMBER_AREA_MOVE_TIMEOUT)):
            debug("Lumber area: could not reach spot %d/%d at %d,%d."
                  % (index + 1, len(spots), spot[0], spot[1]), HUE_WARN)
            state["dead"].add(index)
            state["next"] += 1
            continue

        outcome = work_spot(axe, index, len(spots), state, spot_deadline)

        if outcome == "full":
            return "full"
        if outcome == "stop":
            return "stop"

        state["next"] += 1

    log("Lumber area done: %d swing%s gave wood, %d spot%s walked, %d barren%s."
        % (state["cut"], "" if state["cut"] == 1 else "s",
           state["next"], "" if state["next"] == 1 else "s",
           len(state["dead"]),
           "" if not state["silent"]
           else ", %d silent (see LUMBER_AREA_PROBE_TIMEOUT)" % state["silent"]),
        HUE_GOOD)
    end_sweep(state)
    return "next"


def end_sweep(state):
    """Close a sweep off, however it ended.

    The dead-spot memory is KEPT - barren ground stays barren, and skipping it
    is the whole point of remembering. Everything else restarts, and the origin
    is dropped so it is re-read on arrival: a rune can be moved, and the next
    recall may not land on the same tile.
    """
    state["next"] = 0
    state["origin"] = None
    for counter in ("cut", "dug", "silent"):
        if counter in state:
            state[counter] = 0
    # Spent banks are forgotten between visits - a bank refills. "dead" is NOT
    # forgotten: ground with no tree or rock on it stays that way.
    if "spent" in state:
        state["spent"] = set()
    # The idle clock restarts with the next visit, or the sweep would give up
    # instantly on arriving somewhere after a long trip home.
    state["last_yield"] = time.time()


def work_spot(axe, index, total, state, deadline=None):
    """Chop at one standing spot until it stops giving.

    Returns "" when the spot is done, or "full" / "stop" for the caller.
    """
    swings = 0
    got = 0

    started = time.time()
    hard_stop = started + AREA_SPOT_HARD_CAP_MS / 1000.0
    spoke_at = started

    while swings < LUMBER_AREA_MAX_SWINGS:
        now = time.time()
        if now >= hard_stop:
            log("Lumber area: %ds on spot %d/%d (%d swing(s), %d gave wood) - "
                "that is the hard cap, moving on."
                % (AREA_SPOT_HARD_CAP_MS / 1000, index + 1, total, swings, got),
                HUE_WARN)
            break
        if now - spoke_at >= AREA_PROGRESS_MS / 1000.0:
            spoke_at = now
            log("Lumber area: still on spot %d/%d - %d swing(s), %d gave wood, "
                "%ds so far." % (index + 1, total, swings, got, now - started))
        if poll_skip():
            break
        if take_move():
            log("Lumber area: moving on from spot %d/%d." % (index + 1, total))
            break
        if deadline is not None and time.time() >= deadline:
            log("Lumber area: no wood from spot %d/%d in %ds - moving on."
                % (index + 1, total, AREA_SPOT_TIMEOUT_MS / 1000), HUE_WARN)
            break
        if not pack_has_room():
            return "full"

        # The first swing at a spot is the probe - it answers "is there
        # anything here at all", and it is the one that costs a full timeout
        # on a shard that replies with silence.
        timeout = LUMBER_AREA_PROBE_TIMEOUT if swings == 0 else LUMBER_SWING_TIMEOUT
        outcome = chop_once(axe, timeout)
        swings += 1

        if outcome == "ok":
            got += 1
            state["cut"] += 1
            note_area_yield(state)
            # Producing wood is not being stuck - see mine_spot.
            if deadline is not None:
                deadline = time.time() + AREA_SPOT_TIMEOUT_MS / 1000.0
        elif outcome == "full":
            return "full"
        elif outcome == "broke":
            log("Axe broke - looking for another.", HUE_WARN)
            axe = find_axe()
            if axe is None:
                log("No axe or hatchet left.", HUE_BAD)
                return "stop"
            continue
        elif outcome == "empty":
            # That whole 4x3 bank is spent, not just this tile. Recorded from
            # where we are ACTUALLY standing, which may be a tile off the
            # intended spot.
            state["spent"].add(bank_of(Player.Position.X, Player.Position.Y,
                                       LUMBER_BANK_W, LUMBER_BANK_H))
            break
        elif outcome == "notree":
            if swings == 1:
                # Nothing choppable in reach, and that stays true next visit.
                # Remembered so later trips walk straight past it.
                state["dead"].add(index)
            break
        elif outcome == "silent":
            if swings == 1:
                state["silent"] += 1
                debug("Lumber area: spot %d/%d said nothing at all."
                      % (index + 1, total), HUE_WARN)
            break

        interruptible_pause(HARVEST_PAUSE)

    if got:
        debug("Lumber area: spot %d/%d gave wood on %d swing(s)."
              % (index + 1, total, got))
    return ""


TASKS = {
    "mine": harvest_mine,
    "lumber": harvest_lumber,
}


# =============================================================================
# JOB RUNNER
# =============================================================================

def active_jobs():
    usable = []
    for index, job in enumerate(JOBS):
        name = job.get("name") or "job %d" % (index + 1)
        if not job.get("enabled", True):
            log("  %-16s disabled" % name, HUE_INFO)
            continue
        problems = []
        if not job.get("folder"):
            problems.append("no runebook folder")
        if job.get("task") not in TASKS:
            problems.append("task must be one of %s" % ", ".join(sorted(TASKS)))
        if problems:
            log("  %-16s SKIPPED - %s" % (name, ", ".join(problems)), HUE_BAD)
            continue
        log("  %-16s %s -> %s" % (name, "/".join(job["folder"]), job["task"]),
            HUE_GOOD)
        usable.append(job)
    return usable


def run_job(job, resume=False):
    """Work a job's whole rune route.

    Unloading happens inside this loop, not outside it. A full pack means a trip
    home and back to the same spot - it does not end the job. Only finishing the
    route (or a timer, vendor round or Greyskull call) hands control back.

    `resume` continues an interrupted lap instead of starting a new one. The
    caller re-enters this function after a vendor round or a Greyskull call, and
    without it the waypoint reset below sent the route back to rune 1 every
    time - so a job with a vendor round in the middle never got past its
    opening waypoints.
    """
    name = job["name"]
    log("Job: %s%s" % (name, " (resuming)" if resume else ""), HUE_GOOD)
    if not goJobDir(job):
        log("Could not reach the %s folder - skipping." % name, HUE_BAD)
        return "skip"

    task = TASKS[job["task"]]

    if not resume:
        # Start a clean lap. Without this the index left over from the previous
        # visit carries in, and the route restarts part-way through.
        _waypoint[name] = 0
        _lap_done[name] = False

    routes = ensure_routes(job)
    if not routes:
        log("%s: no runes found in folder %s. Run diag_ar_gump.py."
            % (name, "/".join(job["folder"])), HUE_BAD)
        return "skip"

    total = len(routes)
    log("%s: %d rune%s to work%s."
        % (name, total, "" if total == 1 else "s",
           ", resuming at %d" % (_waypoint.get(name, 0) + 1) if resume else ""),
        HUE_GOOD)
    if total == 1:
        log("%s has only ONE rune in its folder - if you expected more, the "
            "others are not being read. Run diag_ar_gump.py inside that "
            "folder." % name, HUE_WARN)

    deadline = None
    if JOB_ROTATION == "timer":
        deadline = time.time() + JOB_TIME_MS / 1000.0

    need_waypoint = True
    hostile_skips = 0
    at_waypoint_since = time.time()
    watched_waypoint = None
    unloads_here = 0

    while not Player.IsGhost:
        if checkGreyskull():
            return "interrupted"
        if deadline is not None and time.time() >= deadline:
            return "timer"
        if not Timer.Check("harvest vendors"):
            return "vendors"

        if need_waypoint:
            # Checked BEFORE recalling. Doing it after meant the final goNext
            # wrapped to rune 0, wasted a recall, and left the index at 1 so the
            # next lap skipped that rune.
            if route_complete(job):
                log("%s: route complete, all %d runes worked." % (name, total),
                    HUE_GOOD)
                return "route"
            if not goNext(job):
                log("Could not reach a %s waypoint." % name, HUE_BAD)
                return "skip"
            need_waypoint = False
            # The watchdog is armed HERE and nowhere else - arriving somewhere
            # new is the only thing that counts as progress.
            at_waypoint_since = time.time()
            watched_waypoint = _waypoint.get(name, 0)
            unloads_here = 0

        # THE WAYPOINT WATCHDOG. Nothing inside task() can be trusted to end,
        # because "stay here" is what every unhandled result means.
        if watched_waypoint is not None and                 (time.time() - at_waypoint_since) * 1000.0 >= WAYPOINT_HARD_CAP_MS:
            log("%s: %d minute(s) on waypoint %d without moving on - forcing "
                "the next rune. If this repeats, the last few lines above say "
                "what it was retrying."
                % (name, int(WAYPOINT_HARD_CAP_MS / 60000), watched_waypoint),
                HUE_BAD)
            need_waypoint = True
            continue

        if hostiles_near():
            hostile_skips += 1
            if hostile_skips < HOSTILE_SKIP_LIMIT:
                log("%s: moving on (%d in a row)." % (name, hostile_skips),
                    HUE_WARN)
                need_waypoint = True
                continue
            log("%s: %d waypoints skipped for hostiles - harvesting anyway. "
                "Lower HOSTILE_RANGE or set ABORT_ON_HOSTILES = False if this "
                "area is always busy." % (name, hostile_skips), HUE_WARN)
            hostile_skips = 0
        else:
            hostile_skips = 0

        result = task()

        if take_skip():
            log("%s: skipping to the next rune." % name, HUE_GOOD)
            need_waypoint = True
            interruptible_pause(HARVEST_PAUSE)
            continue

        if result == "full":
            # Smelt, then let anything carried take the load. Only if the pack
            # is STILL full has a trip home earned itself.
            #
            # NO COUNT ON THIS. unload_in_place() returns True only when the
            # pack ACTUALLY HAS ROOM afterwards - that is its whole contract -
            # so a True can never be followed by an immediate "full", and the
            # runaway loop this looked like it needed guarding against cannot
            # happen. A count here does the opposite of what it looks like: it
            # sends a character whose keys are working perfectly home after
            # three successful in-place unloads, which is what "he recalls home
            # constantly" turned out to be. The waypoint watchdog is the
            # backstop for anything genuinely stuck.
            if unload_in_place():
                unloads_here += 1
                if unloads_here == UNLOAD_IN_PLACE_NOTE:
                    log("%s: %d in-place unloads at this waypoint - the keys "
                        "are keeping up, staying out."
                        % (name, unloads_here), HUE_INFO)
                continue

            index = _waypoint.get(name, 0)
            total = len(_routes.get(name) or [])
            log("%s: pack full at waypoint %d/%d - unloading and coming back."
                % (name, index, total), HUE_INFO)
            dropoff()

            if JOB_ROTATION == "dropoff":
                return "full"

            if not goJobDir(job):
                return "skip"
            if not goCurrent(job):        # same spot, not the next one
                need_waypoint = True
            continue

        if result == "stop":
            log("%s: the task cannot continue (no tool?)." % name, HUE_BAD)
            return "stop"
        if result == "next":
            need_waypoint = True
        elif result not in ("ok", "full"):
            # An unrecognised result silently means "stay at this waypoint",
            # which is how a typo in a task's return value becomes a character
            # standing still for an hour. Name it and move on.
            log("%s: task returned %r, which is not a result this loop knows. "
                "Treating it as done with this rune." % (name, result),
                HUE_WARN)
            need_waypoint = True

        interruptible_pause(HARVEST_PAUSE)

    return "dead"


# =============================================================================
# DIAGNOSTIC RUN
# =============================================================================

LUMBER_BUCKETS = [
    ("SUCCESS", "keep chopping"),
    ("RETRY", "failed swing, keep chopping"),
    ("DEPLETED", "move to the next rune"),
    ("BAD_TARGET", "move to the next rune"),
    ("PACK_FULL", "unload"),
    ("TOOL_BROKE", "find another axe"),
]


def diag_rule(text):
    log("=" * 8 + " " + text + " " + "=" * 8, HUE_STEP)


def all_journal_lines():
    try:
        return [getattr(e, "Text", "") or ""
                for e in (Journal.GetJournalEntry(0.0) or [])]
    except Exception:
        return []


def classify_lumber():
    """Which message bucket the current journal matches, if any."""
    lookup = {
        "SUCCESS": LUMBER_SUCCESS, "RETRY": LUMBER_RETRY,
        "DEPLETED": LUMBER_DEPLETED, "BAD_TARGET": LUMBER_BAD_TARGET,
        "PACK_FULL": LUMBER_PACK_FULL, "TOOL_BROKE": LUMBER_TOOL_BROKE,
    }
    return [name for name, _why in LUMBER_BUCKETS if journal_hit(lookup[name])]


def diag_swing(job, waypoint):
    """One harvest attempt, with the raw server reply."""
    usage = pack_usage()
    axe = None
    if job["task"] == "lumber":
        axe = find_axe()
        log("   axe: %s" % (("%s (0x%X, id 0x%X)"
                             % (safe_name(axe) or "?", axe.Serial, axe.ItemID))
                            if axe else "NONE FOUND"),
            HUE_INFO if axe else HUE_BAD)
    log("   pack: %s   mana: %d/%d"
        % ("%d/%d items, %d/%d stones" % usage if usage else "UNREADABLE",
           Player.Mana, Player.ManaMax), HUE_INFO)

    Journal.Clear()
    result = TASKS[job["task"]]()

    # A full pack returns before the tool is ever used, so the trace would show
    # nothing about harvesting from here on. Unload and take the real swing.
    if result == "full":
        log("   pack full - unloading so the trace keeps meaning something.",
            HUE_WARN)
        if not unload_in_place():
            dropoff()
            goJobDir(job)
            goCurrent(job)
        Journal.Clear()
        result = TASKS[job["task"]]()

    lines = all_journal_lines()

    log("   task returned: %s" % result,
        HUE_GOOD if result in ("ok", "next") else HUE_WARN)

    if lines:
        for line in lines:
            log("   journal: %s" % line, HUE_INFO)
    else:
        log("   journal: SILENT - the server said nothing at all.", HUE_BAD)

    if job["task"] == "lumber":
        matched = classify_lumber()
        if matched:
            log("   matched: %s" % ", ".join(matched), HUE_GOOD)
        else:
            log("   matched: NOTHING. None of the LUMBER_* message lists match "
                "what the server said - that is the bug. Copy a line above into "
                "the right list.", HUE_BAD)
    return result


def diag_job(job):
    name = job["name"]
    diag_rule("JOB: %s  (folder %s, task %s)"
              % (name, "/".join(job["folder"]), job["task"]))

    if not goJobDir(job):
        log("FAILED to enter the folder. Nothing else can work.", HUE_BAD)
        return

    routes = ensure_routes(job)
    log("route: %d rune(s)" % len(routes),
        HUE_GOOD if routes else HUE_BAD)
    for i, (page, button, rune) in enumerate(routes, 1):
        log("  %2d. page %d  button %d  %s" % (i, page, button, rune))
    if not routes:
        log("No runes read from this folder - run diag_ar_gump.py inside it.",
            HUE_BAD)
        return

    _waypoint[name] = 0
    _lap_done[name] = False
    outcomes = []

    for step in range(len(routes)):
        if Player.IsGhost:
            log("Dead - stopping.", HUE_BAD)
            return
        diag_rule("%s waypoint %d of %d" % (name, step + 1, len(routes)))

        if not goNext(job):
            log("   RECALL FAILED - could not reach this waypoint.", HUE_BAD)
            outcomes.append((step + 1, "recall failed"))
            continue

        if hostiles_near():
            log("   hostiles in range here (would be skipped in a real run)",
                HUE_WARN)

        result = diag_swing(job, step + 1)
        outcomes.append((step + 1, result))
        Misc.Pause(500)

    diag_rule("%s SUMMARY" % name)
    for step, result in outcomes:
        hue = HUE_GOOD if result in ("ok", "next") else HUE_BAD
        log("  waypoint %2d -> %s" % (step, result), hue)
    bad = [s for s, r in outcomes if r not in ("ok", "next", "full")]
    if bad:
        log("  PROBLEM at waypoint(s): %s"
            % ", ".join(str(s) for s in bad), HUE_BAD)
    else:
        log("  all %d waypoints reachable and harvestable." % len(outcomes),
            HUE_GOOD)


def diagnostic_run(jobs):
    diag_rule("DIAGNOSTIC RUN - no rotation, no vendors, no drop-off")
    log("Meditation %.1f | mana %d/%d | rotation %s"
        % (Player.GetSkillValue("Meditation"), Player.Mana, Player.ManaMax,
           JOB_ROTATION))
    for job in jobs:
        diag_job(job)

    diag_rule("END")
    try:
        with open(DIAGNOSTIC_DUMP, "w") as fh:
            fh.write("\n".join(_transcript))
        Misc.SendMessage("[Harvest] Trace written to %s" % DIAGNOSTIC_DUMP,
                         HUE_GOOD, False)
    except Exception as err:
        Misc.SendMessage("[Harvest] Could not write the trace: %s" % err,
                         HUE_BAD, False)


# =============================================================================
# MAIN
# =============================================================================

def crash_state():
    """Everything worth knowing about where the script was when it died."""
    rows = []

    def add(label, value):
        rows.append("  %-22s %s" % (label, value))

    add("script", "%s [%s]" % (SCRIPT_VERSION, SCRIPT_TAG))
    try:
        add("character", "%s, serial 0x%X" % (Player.Name, Player.Serial))
        add("position", "%d,%d  map %s"
            % (Player.Position.X, Player.Position.Y, Player.Map))
        add("weight", "%d of %d" % (Player.Weight, Player.MaxWeight))
        add("ghost", Player.IsGhost)
    except Exception as err:
        add("player", "could not be read: %r" % (err,))

    try:
        job = _current_job if isinstance(_current_job, dict) else {}
        name = job.get("name", "(none)")
        routes = _routes.get(name) or []
        add("job", "%s, waypoint %s of %d"
            % (name, _waypoint.get(name, "?"), len(routes)))
    except Exception as err:
        add("job", "could not be read: %r" % (err,))

    # The serials are the ONLY thing that differs between the copies, so they
    # are the first suspect when one character crashes and the others do not.
    for label, serial in (("WOOD_STORAGE_SERIAL", WOOD_STORAGE_SERIAL),
                          ("INGOT_KEY_SERIAL", INGOT_KEY_SERIAL),
                          ("STONE_STORAGE_SERIAL", STONE_STORAGE_SERIAL)):
        if not serial:
            add(label, "0 (graphic lookup)")
            continue
        try:
            item = Items.FindBySerial(serial)
            if item is None:
                add(label, "0x%X -> NOT FOUND" % serial)
            else:
                add(label, "0x%X -> id 0x%04X hue 0x%04X %r"
                    % (serial, int(item.ItemID), int(item.Hue),
                       safe_name(item)))
        except Exception as err:
            add(label, "0x%X -> reading it RAISED %r" % (serial, err))

    return rows


def is_stop_request(err):
    """Did the user press Stop, rather than the script actually failing?

    Razor stops a script by aborting its thread. IronPython surfaces that
    .NET ThreadAbortException to Python as

        SystemError: Thread was being aborted.

    which is an ordinary Exception subclass, so a blanket `except Exception`
    catches it and writes a CRASHED report for a completely normal stop. Every
    crash file on disk at the time this was written was one of these - five
    reports, five presses of the Stop button, no real crashes at all. Worse,
    it dumps a red traceback over the journal you were about to read.

    Matched on the message rather than the type: the exception reaches Python
    as SystemError here, but the type is an implementation detail of the
    IronPython build and the message is what Razor's users actually see.
    """
    try:
        text = str(err).lower()
    except Exception:
        return False
    return "thread was being aborted" in text or "thread abort" in text


def report_crash(err):
    """Write the traceback, the breadcrumb trail and the state, and say where.

    Both to the journal and to a file, because the journal scrolls and a crash
    that happens while you are not watching is exactly the one that matters.
    """
    try:
        import traceback
        tb = traceback.format_exc()
    except Exception:
        tb = "%r (traceback module unavailable)" % (err,)

    lines = ["=" * 70,
             "harvest_runner CRASHED",
             "=" * 70,
             ""]
    lines.extend(crash_state())
    lines.append("")
    lines.append("Last %d log line(s), oldest first:" % len(_trail))
    lines.extend("    %s" % t for t in _trail)
    lines.append("")
    lines.append(tb)

    for line in lines[:8]:
        log(line, HUE_BAD)
    log("...full report follows in the file.", HUE_BAD)
    for line in tb.strip().splitlines():
        log(line, HUE_BAD)

    path = ""
    try:
        who = "".join(c for c in (Player.Name or "unknown")
                      if c.isalnum() or c in "-_") or "unknown"
        path = os.path.join(os.environ.get("TEMP", "."),
                            "harvest_crash_%s.txt" % who)
        with open(path, "a") as handle:
            handle.write(os.linesep.join(lines) + os.linesep + os.linesep)
        log("Crash report appended to %s - send that file." % path, HUE_BAD)
    except Exception as write_err:
        log("Could not write the crash file (%r). The traceback above is all "
            "there is - copy it out of the journal." % (write_err,), HUE_BAD)


if __name__ == "__main__":
    # EVERYTHING is inside this handler. A Razor script that raises prints one
    # line and stops, and the traceback is gone before it can be read - which
    # is why "it crashes sometimes" was impossible to act on. This writes the
    # traceback, the last CRASH_TRAIL log lines and the state to a file named
    # after the character.
    try:
        log("harvest_runner v%s [%s]" % (SCRIPT_VERSION, SCRIPT_TAG), HUE_STEP)
        if Player.GetSkillValue("Meditation") <= 0:
            log("No Meditation skill - mana recovery will be passive only.", HUE_WARN)

        log("Jobs:", HUE_INFO)
        jobs = active_jobs()
        if not jobs:
            log("No usable jobs configured. Edit JOBS at the top.", HUE_BAD)
            raise SystemExit

        log("Vendor round:", HUE_INFO)
        _usable = validate_vendors(all_vendors())
        _stops = vendor_stops(_usable)
        log("  -> %d stop(s), %d NPC request(s) per round."
            % (len(_stops), len(_usable)), HUE_GOOD)
        for _stop in _stops:
            log("     %s/%s : %s"
                % ("/".join(_stop["folder"]) or "(root)", _stop["point"],
                   ", ".join(v["label"] for v in _stop["vendors"])), HUE_INFO)

        log("House deposits at %s (via %s):"
            % (DROP_POINT, ", ".join(HOUSE_DEPOSIT_CONTEXT)), HUE_INFO)
        for spec in HOUSE_DEPOSITS:
            state = "" if spec.get("enabled", True) else "  (disabled)"
            log("  %-18s book 0x%X%s"
                % (spec.get("label", "?"), spec.get("serial", 0), state), HUE_INFO)

        if not BOD_ENABLED:
            log("Bulk orders: OFF. No BOD stops, no filing, no book. Resource "
                "Orders and Taming Deeds are unaffected.", HUE_WARN)
        else:
            bod_book, how = find_bod_book()
            if bod_book is None:
                log("Bulk Order Book: NOT FOUND (%s) - deeds will pile up in "
                    "your pack." % how, HUE_BAD)
            else:
                count = deeds_in_book(bod_book)
                log("Bulk Order Book: 0x%X, %s deed(s) in it (%s)."
                    % (bod_book.Serial, "?" if count is None else count, how),
                    HUE_GOOD)

        report_restock_keys()

        if LUMBER_AREA_ENABLED:
            log("Lumber area: %dx%d box, %d standing spot(s) per rune, %dx%d "
                "apart (= the wood bank)."
                % (LUMBER_AREA_SIZE, LUMBER_AREA_SIZE,
                   len(area_offsets(LUMBER_AREA_SIZE, LUMBER_AREA_STEP_X))
                   * len(area_offsets(LUMBER_AREA_SIZE, LUMBER_AREA_STEP_Y)),
                   LUMBER_AREA_STEP_X, LUMBER_AREA_STEP_Y), HUE_INFO)
        else:
            log("Lumber area: OFF - one spot per rune.", HUE_INFO)

        if MINE_AREA_ENABLED:
            log("Mining area: %d tiles out, spots %d apart (= the 8x8 ore bank), "
                "up to %d per rune."
                % (MINE_AREA_RADIUS, MINE_AREA_STEP,
                   len(area_offsets(MINE_AREA_RADIUS * 2, MINE_AREA_STEP)) ** 2),
                HUE_INFO)
            log("  Mineable ground: %d mountain/cave tiles%s."
                % (len(MOUNTAIN_AND_CAVE_TILES),
                   ", plus %d sand" % len(SAND_TILES)
                   if MINE_AREA_INCLUDE_SAND else ""), HUE_INFO)
        else:
            log("Mining area: OFF - one spot per rune.", HUE_INFO)

        log("Stuck guards: %ds per spot, %ds rooted while walking, %ds producing "
            "nothing abandons the rune. Path legs cut off at %ss."
            % (AREA_SPOT_TIMEOUT_MS / 1000, AREA_STUCK_TIMEOUT_MS / 1000,
               AREA_IDLE_TIMEOUT_MS / 1000, PATH_LEG_TIMEOUT_S), HUE_INFO)

        _free, _w, _mw = weight_headroom()
        log("Pack: %d of %d stones, %d free. Storing at %d%% (%d stones), or "
            "sooner if one more yield would go over."
            % (_w, _mw, _free, round(PACK_STORE_AT * 100),
               int(_mw * PACK_STORE_AT)), HUE_INFO)
        if DROPOFF_AFTER_VENDORS:
            log("Deeds are stored at home right after any vendor round that "
                "collects.", HUE_INFO)

        log("Listening for: %s" % ", ".join(GREYSKULL_PHRASES), HUE_INFO)
        log('Say "%s" as %s to skip to the next rune%s.'
            % ("/".join(SKIP_PHRASES), Player.Name or "this character",
               " (this character only)" if SKIP_SELF_ONLY else ""), HUE_INFO)
        log('Say "%s" to leave just this spot and take the next one in the '
            'same area - or recall, if it was the last%s.'
            % ("/".join(MOVE_PHRASES),
               " (this character only)" if MOVE_SELF_ONLY else ""), HUE_INFO)

        # Razor keeps a script loaded between runs, so this state can outlive
        # a Reload - and resuming last run's sweep position would put the
        # character back at a spot it is nowhere near.
        forget_sweeps()

        Journal.Clear()
        prime_journal_cursor()
        Timer.Create("harvest vendors", VENDOR_INTERVAL_MS)
        Timer.Create("harvest drop", DROP_INTERVAL_MS)

        if DIAGNOSTIC_MODE:
            diagnostic_run(jobs)
            raise SystemExit

        job_index = 0
        resume_job = False

        while not Player.IsGhost:
            if checkGreyskull():
                continue

            job = jobs[job_index]
            outcome = run_job(job, resume=resume_job)
            resume_job = False
            log("%s finished: %s" % (job["name"], outcome), HUE_INFO)

            # These do not end the job - come back to the same lap, same waypoint.
            if outcome == "vendors":
                collected = vendor_round()
                Timer.Create("harvest vendors", VENDOR_INTERVAL_MS)
                if DROPOFF_AFTER_VENDORS and collected:
                    log("Storing %d collected deed(s) before going back to work."
                        % collected, HUE_INFO)
                    dropoff()
                    Timer.Create("harvest drop", DROP_INTERVAL_MS)
                resume_job = True
                continue
            if outcome == "interrupted":
                resume_job = True
                continue

            if outcome == "stop":
                smelt()
                dropoff()

            if JOB_ROTATION != "never" and len(jobs) > 1:
                # Hand the next job an empty pack. Ore left over from mining is
                # dead weight the wood storage will not take.
                if DROPOFF_BETWEEN_JOBS and not pack_has_room(PACK_HANDOVER_LEVEL):
                    log("Unloading before switching jobs.", HUE_INFO)
                    if not unload_in_place(PACK_HANDOVER_LEVEL):
                        dropoff()
                job_index = (job_index + 1) % len(jobs)
                _lap_done[job["name"]] = False

        log("You are dead. Stopping.", HUE_BAD)
        while Player.IsGhost:
            Misc.Beep()
            Misc.Pause(1500)

    except SystemExit:
        raise
    except KeyboardInterrupt:
        log("Stopped.", HUE_INFO)
        raise
    except Exception as _err:
        # Pressing Stop is not a crash. Let it through untouched so it does not
        # append a bogus report or bury the journal under a red traceback.
        if is_stop_request(_err):
            log("Stopped.", HUE_INFO)
            raise
        if CRASH_REPORT:
            report_crash(_err)
        else:
            raise
