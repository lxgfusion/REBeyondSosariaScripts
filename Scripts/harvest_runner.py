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
WOOD_STORAGE_SERIAL = 0x4290200A
WOOD_STORAGE_ID = 0x1BD9         # graphic, used when the serial is gone
WOOD_STORAGE_HUE = 0x0058        # its colour; -1 accepts any
WOOD_STORAGE_RANGE = 12          # tiles, only used when "world"

# -----------------------------------------------------------------------------
# INGOT KEY - the mining equivalent of the Wood Storage.
#
# Same idea and the same "Refill from stock" entry: carry it and the ingots go
# into it on the spot, instead of being carted to the drop chest.
#
# Inspected 2026-08-11: "Ingot Keys", serial 0x405B2105, ItemID 0x1BE8,
# hue 0x0014, Blessed, carried in the pack.
#
# PER CHARACTER, exactly like WOOD_STORAGE_SERIAL - each character has its own
# key, so this serial is only right for the copy it ships in. The id/hue
# fallback below is what keeps the other copies working when the serial is not
# theirs; hue 0x0014 is this key's colour, set it to -1 if another character's
# key is a different one.
#
# False sends ingots to the drop chest as before.
INGOT_KEY_ENABLED = True
INGOT_KEY_WHERE = "pack"
# Serial left EMPTY on purpose. Each character carries their own key, so a
# serial here would be right for exactly one copy and would resolve to somebody
# else's key in the others. The graphic with hue -1 finds whichever key is in
# THIS character's pack. Inspected example: 0x405B2105, hue 0x0014.
INGOT_KEY_SERIAL = 0
INGOT_KEY_ID = 0x1BE8
INGOT_KEY_HUE = -1
INGOT_KEY_RANGE = 12              # tiles, only used when "world"

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
RESTOCK_KEYS = [
    {
        # Built from the WOOD_STORAGE_* settings at the top of the file.
        # As inspected it is locked down at the house - Container and
        # RootContainer both None, Ground yes - so a backpack search, which is
        # what the original did, could never find it.
        "label": "Wood Storage",
        "serial": WOOD_STORAGE_SERIAL,
        "id": WOOD_STORAGE_ID, "hue": WOOD_STORAGE_HUE,
        "where": WOOD_STORAGE_WHERE, "range": WOOD_STORAGE_RANGE,
    },
    {"label": "Master key",  "id": 0x176B, "hue": 0x0481, "where": "pack"},
    {
        # Built from the INGOT_KEY_* settings at the top of the file, the same
        # way the Wood Storage entry is.
        "label": "Ingot key",
        "enabled": INGOT_KEY_ENABLED,
        "serial": INGOT_KEY_SERIAL,
        "id": INGOT_KEY_ID, "hue": INGOT_KEY_HUE,
        "where": INGOT_KEY_WHERE, "range": INGOT_KEY_RANGE,
    },
    {"label": "Key (alt)",   "id": 0xA54A, "hue": -1,     "where": "pack"},
    # 0x2259 is the Bulk Order Book graphic. Carried books are handled by
    # BOD_BOOK_SERIAL below (deeds are dragged in); this entry is inherited from
    # the original script and only matches one sitting on the ground nearby.
    {"label": "Stock book (ground)", "id": 0x2259, "hue": -1, "where": "world",
     "range": 3},
]

# Context entry that pushes the pack's resources into the storage. Matched the
# same way as vendor entries: exact label first, then a guarded substring.
RESTOCK_CONTEXT = ["Refill from stock"]

# Pack is "full" past this fraction of item count or weight.
PACK_THRESHOLD = 0.6

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
    "There's not enough wood here to harvest",   # 500493
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

# Mining detection is left exactly as the working original: a broad "You" match
# with "You can't mine there" and "no metal" as the negative cases. For
# reference if it ever needs tightening, the verified ServUO strings are:
#   503040 There is no metal here to mine.
#   503041 You have moved too far away to continue mining.
#   503042 Someone has gotten to the metal before you.
#   503043 You loosen some rocks but fail to find any useable ore.
#   501862 You can't mine there.      501863 You can't mine that.
#   1010481 Your backpack is full, so the ore you mined is lost.
#   1044038 You have worn out your tool!
MINE_TOOL_BROKE = ["You have worn out your tool"]


# =============================================================================
# RUNTIME STATE
# =============================================================================

_armor_blocks_meditation = False
_passive_notice_shown = False

_vendor_history = {}      # vendor label -> [unix times an order was collected]
_vendor_ready_at = {}     # vendor label -> unix time it is worth asking again

_routes = {}              # job name -> [(page, button, rune name)]
_waypoint = {}            # job name -> next index into that route
_lap_done = {}            # job name -> True once the route has wrapped
_current_job = None

_journal_cursor = 0.0
_greyskull_pending = False
_greyskull_active = False

_axe_serial = None        # the axe last used, so it can be recovered by serial


# =============================================================================
# HELPERS
# =============================================================================

_transcript = []


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Harvest] " + text, hue, False)
    if DIAGNOSTIC_MODE:
        _transcript.append(text)


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


def greyskull_heard():
    for entry in new_journal_entries():
        raw = getattr(entry, "Text", "") or ""
        if not raw:
            continue
        low = raw.lower()
        matched = None
        for phrase in GREYSKULL_PHRASES:
            phrase = phrase.strip().lower()
            if phrase and phrase in low:
                matched = phrase
                break
        if matched is None:
            continue

        channel, caller, _said = parse_chat_line(raw)
        if not channel_allowed(channel):
            debug("Greyskull ignored - wrong channel (%s)." % (channel or "none"))
            continue
        if not caller_allowed(caller):
            debug("Greyskull ignored - caller not allowed (%s)."
                  % (caller or "unknown"))
            continue

        log("Greyskull called by %s%s." % (caller or "someone",
                                           " in %s" % channel if channel else ""),
            HUE_GOOD)
        return True
    return False


def poll_greyskull():
    """Raise the flag only. Safe to call from anywhere, including travel waits."""
    global _greyskull_pending
    if _greyskull_active:
        return False
    if _greyskull_pending:
        return True
    if greyskull_heard():
        _greyskull_pending = True
        log("Greyskull heard - responding at the next safe point.", HUE_GOOD)
    return _greyskull_pending


def interruptible_pause(total_ms, slice_ms=250):
    """Misc.Pause that keeps listening for the call-out."""
    remaining = int(total_ms)
    while remaining > 0:
        step = min(slice_ms, remaining)
        Misc.Pause(step)
        remaining -= step
        poll_greyskull()


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
        return True

    log("Recall to %s refused for mana - recovering and retrying." % what,
        HUE_WARN)
    clear_journal(MSG_NO_MANA)
    if not ensure_mana(reason="retry recall"):
        return False
    if not openAR():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(1000)
    return not travel_failed_for_mana()


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


def pack_has_room(threshold=None):
    """True while there is room to keep harvesting.

    An UNKNOWN measure never counts as full. Treating "I could not read it" as
    "the pack is full" is what had every character declaring a full pack at
    whatever waypoint it had reached and then recalling home forever, at a
    fifth of its carry weight - and it said so through debug(), so with
    debugging off there was nothing in the journal to explain it.

    The authority on a genuinely full pack is the SERVER: the harvest task
    reads its refusal out of the journal and returns "full". This is only for
    deciding whether unloading achieved anything.
    """
    if threshold is None:
        threshold = PACK_THRESHOLD
    items, max_items, weight, max_weight = pack_usage()

    if max_weight and weight > max_weight * threshold:
        debug("pack full by WEIGHT: %d of %d (limit %d)"
              % (weight, max_weight, int(max_weight * threshold)), HUE_WARN)
        return False
    if max_items and items > max_items * threshold:
        # Said at WARNING level, not debug. A pack that is full on item count
        # while barely carrying any weight is the confusing case - it looks
        # like nothing is wrong - and the keys cannot help with it, because
        # what fills the count is gems, deeds and tools rather than resources.
        log("pack full by ITEM COUNT: %d of %d items (limit %d). Weight is "
            "only %d of %d, so the keys cannot fix this - it needs the chest."
            % (items, max_items, int(max_items * threshold),
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
    return list(found or [])


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
    if pack_has_room():
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
            if context_select(item, RESTOCK_CONTEXT, label):
                used = True
                Misc.Pause(1200)
                if pack_has_room():
                    log("%s took the load%s." %
                        (label, " (carried - no trip home)" if carried else ""),
                        HUE_GOOD)
                    return True
    if not used and not on_player_only:
        debug("No restock storage in reach.", HUE_WARN)
    return pack_has_room()


def smelt():
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
    _vendor_history.setdefault(vendor["label"], []).append(time.time())
    _vendor_ready_at.pop(vendor["label"], None)


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
    """The plain VENDORS table plus everything the BOD tables expand to."""
    return list(VENDORS) + expand_bod_locations()


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


def visit_vendor(vendor):
    """Travel to one vendor and serve it. Kept for single-vendor callers."""
    return visit_stop({"folder": vendor["folder"], "point": vendor["point"],
                       "vendors": [vendor]})


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


# =============================================================================
# HARVEST TASKS
#
# Each returns one of:
#   "ok"    something was harvested; stay on this spot
#   "next"  this spot is exhausted or unusable; move to the next waypoint
#   "full"  the pack is full
#   "stop"  cannot continue (no tool)
# =============================================================================

def harvest_mine():
    """Mining. Detection logic kept as the working original."""
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

    Journal.Clear("You")
    Journal.Clear("No Metal")
    clear_cursor()
    Target.TargetResource(shovel, 0)

    result = "next"
    Timer.Create("harvest mine timeout", 5000)
    while Timer.Check("harvest mine timeout"):
        if journal_hit(MINE_TOOL_BROKE):
            log("Shovel worn out - making another.", HUE_WARN)
            make_shovel()
            result = "ok"
            break
        if Journal.Search("You"):
            result = "next" if Journal.Search("You can't mine there") else "ok"
            break
        if Journal.Search("no metal"):
            Journal.Clear("no metal")
            result = "next"
            break
        interruptible_pause(100)

    Journal.Clear("You")
    smelt()
    return result


def harvest_lumber():
    """Lumberjacking."""
    if not pack_has_room():
        return "full"

    axe = find_axe()
    if axe is None:
        log("No axe or hatchet found in hand or pack.", HUE_BAD)
        return "stop"

    clear_journal(LUMBER_ALL)
    clear_cursor()
    Target.TargetResource(axe, "wood")

    deadline = time.time() + LUMBER_SWING_TIMEOUT / 1000.0
    while time.time() < deadline:
        if journal_hit(LUMBER_TOOL_BROKE):
            log("Axe broke - looking for another.", HUE_WARN)
            return "ok"
        if journal_hit(LUMBER_PACK_FULL):
            return "full"
        if journal_hit(LUMBER_DEPLETED):
            return "next"
        if journal_hit(LUMBER_BAD_TARGET):
            debug("Not a usable tree here.")
            return "next"
        if journal_hit(LUMBER_SUCCESS) or journal_hit(LUMBER_RETRY):
            return "ok"
        interruptible_pause(150)

    debug("Chop timed out - moving on.")
    return "next"


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

        if result == "full":
            # Smelt, then let anything carried take the load. Only if the pack
            # is STILL full has a trip home earned itself.
            if unload_in_place():
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

if __name__ == "__main__":
    log("Starting.", HUE_GOOD)
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

    bod_book, how = find_bod_book()
    if bod_book is None:
        log("Bulk Order Book: NOT FOUND (%s) - deeds will pile up in your pack."
            % how, HUE_BAD)
    else:
        count = deeds_in_book(bod_book)
        log("Bulk Order Book: 0x%X, %s deed(s) in it (%s)."
            % (bod_book.Serial, "?" if count is None else count, how), HUE_GOOD)

    log("Listening for: %s" % ", ".join(GREYSKULL_PHRASES), HUE_INFO)

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
            vendor_round()
            Timer.Create("harvest vendors", VENDOR_INTERVAL_MS)
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
