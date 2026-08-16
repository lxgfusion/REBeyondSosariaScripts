"""
Resource order filler.
======================

Runs the whole resource-order circuit unattended:

    Start Fill  ->  RO  ->  Deposit items  ->  Deposit PS  ->  Start Fill

repeated until a lap can fill nothing, or MAX_CYCLES laps have run. All four
runes live in the RO folder of the account runebook.

Works everything the book asks for, pooled across every chest in CHESTS.
RESOURCES holds all 79 names the book uses, harvested from all 540 pages by
diag_order_names.py and ordered by how many orders each has.

Reserves are per resource: peerless ingredients keep nothing, because the
obelisks refill them, and everything else keeps KEEP_PER_TYPE back.

    0. Bin last lap's reward forges: anything in TRASH_ITEM_IDS goes from the
       pack into the trash bag. An allowlist - that bag deletes what it holds.
    1. Tidy EVERY chest in CHESTS, then census them as one pool. Ingots and
       gems are identified by ItemID + hue, never by name - an ingot stack is
       called "<amount> ingots" and says nothing about the metal. Peerless
       ingredients are the other way round: they carry their own name and their
       graphics are unknown, so they match by name.
    2. Work out a budget per resource. Ingots and gems leave KEEP_PER_TYPE
       behind; peerless ingredients carry "keep": 0 and are spendable to the
       last one, because the obelisks refill them.
    3. For each resource, filter the order book to its exact name and pick an
       order that fits the budget. Resources are worked round-robin, and each
       lap RESUMES where the last stopped - the cap is on withdrawals, so
       without that rotation nothing past position MAX_ORDERS_PER_RUN would
       ever get a turn.
    4. Withdraw it, then fill it by targeting the stack WHERE IT SITS IN THE
       CHEST - nothing is carried - and verify the deed reads as fulfilled.
    5. Recall to RO, find the Resource Gatherer, drag the deeds onto them, then
       sweep the pack for any FULFILLED deed that got missed and hand that in
       too. Unfilled deeds are named and left alone.
    6. Empty the rewards: the carried Runecrafting Storage, then Deposit items
       (the Armory) and Deposit PS (the Ultimate Power Scroll Book), each
       single-clicked and answered with "Refill From Stock".
    7. Back to Start Fill and round again.

The order list's columns are Name | Amt To Gather | Amt Gathered | Value Per |
Completed.

Start it anywhere - the first thing it does is recall to Start Fill.

Confirmed working in game on 2026-07-27: one order withdrawn, filled, handed to
the Resource Gatherer, and back home. `MAX_ORDERS_PER_RUN` now defaults to 5 -
all of them are filled at the chest and carried on a single recall trip.

WHAT IS VERIFIED RATHER THAN ASSUMED
------------------------------------
Both of these were guesses before the first live run, and both are still checked
against game state rather than trusted, because a wrong assumption here costs
spent ingots:

    withdrawing   pressing an order's row button puts a deed in the pack. The
                  pack is diffed before and after; no new deed, no progress.
    filling       double-clicking the deed and targeting the ingots raises its
                  progress. The tooltip is re-read after every attempt, and if
                  targeting does nothing the drag method is tried instead.

The book's list is LIVE. Rather than build a shortlist and work through it, the
book is re-scanned for every single order - a row remembered from an earlier
scan can be a different order by the time it is pressed.

WHAT IT NEVER TOUCHES
---------------------
The book's `Withdrawal Amount` box and its button 3, plus `Add`, `Purge` and
`Rename Book`. Orders come out through the row buttons only.

The order data is LIVE - other players fill the same orders, and amounts were
seen changing between two reads seconds apart. Every deed's real requirement is
read from the deed itself after withdrawal, never from the row that named it.

Journal note: this clears the journal around the fill step, because it reads the
result of an action from it.

See docs/resource-order-book-gump.md for the gump map this is built on.
"""

import re
import time


# Printed at startup. Bump it with every change that goes out, so the first
# line in the journal says which copy is actually loaded - two separate
# debugging rounds were spent on a bug that was already fixed on disk but not
# in the Scripts folder.
SCRIPT_VERSION = "2026-08-11.28"


# =============================================================================
# CONFIG - SHARD TABLE. Fill this in first.
# =============================================================================
# Both containers are locked down on the ground at the house - Container and
# RootContainer are None, Ground is Yes - so they are found with a WORLD search.
# The exact serial is tried first; id+hue is the fallback for the day one of
# them is replaced.

# "Resource Order Book", ItemID 0x2259, hue 0x04F7, at (1282, 1192, -85).
BOOK_SERIAL = 0x404AC332
BOOK_ID = 0x2259
BOOK_HUE = 0x04F7

# ---------------------------------------------------------------------------
# THE CHESTS. Every enabled entry is searched, so stock can be spread over as
# many containers as you like.
#
#   label    Name used in the log.
#   enabled  False keeps the entry without using it - fill the serial in later.
#   serial   Exact serial, tried first. Most reliable when it never moves.
#   id/hue   Fallback lookup if the serial is gone (hue -1 = any).
#
# All of these are locked down on the ground, so they are found with a WORLD
# search and never a backpack search.
CHESTS = [
    {
        # "a glimmering chest of belongings", at (1281, 1192, -88).
        "label": "ingots and gems",
        "enabled": True,
        "serial": 0x400CEF90,
        "id": 0x0E41,
        "hue": 0x089F,
    },
    {
        # "a glimmering chest of belongings", at (1280, 1192, -88) - right
        # beside the first one, so both are inside WORLD_RANGE from the book.
        # Same graphic as the other chest but a different hue, which is what
        # keeps the id/hue fallback able to tell them apart.
        "label": "peerless ingredients",
        "enabled": True,
        "serial": 0x400463FB,
        "id": 0x0E41,
        "hue": 0x047E,
    },
]

WORLD_RANGE = 4

# ---------------------------------------------------------------------------
# THE HAND-IN
#
# Inspected: "Davin the Resource Gatherer", serial 0x00002A74, body 0x0190,
# hue 0x8419, at (1413, 1720, 20), notoriety 7 (invulnerable).
#
# Matched on the NAME because this shard puts the title in the name field
# rather than the tooltip - the Attributes panel was empty on inspection. The
# serial is kept as a fast path but is not relied on: NPC serials change if the
# shard respawns them.
HANDIN_NPC_SERIAL = 0x00002A74
HANDIN_NPC_WORDS = ["resource gatherer"]
HANDIN_NPC_RANGE = 12

# `[AR` path to the hand-in: folder "RO", rune "RO".
HANDIN_FOLDER = ["RO"]
HANDIN_POINT = "RO"

# ---------------------------------------------------------------------------
# THE CIRCUIT
#
#     Start Fill  ->  RO  ->  Deposit items  ->  Deposit PS  ->  Start Fill
#
# repeated until no more orders can be filled. All four runes live in the RO
# folder of the account runebook.
#
# Start Fill is where the book and the chests are; the hand-in is at RO; the
# two deposit stops empty the rewards.
START_FOLDER = ["RO"]
START_POINT = "Start Fill"

# Ceiling on laps. Each one is a full circuit of four recalls, so this is the
# real bound on a run - a lap that fills nothing ends it early anyway.
MAX_CYCLES = 20

# Deposit stops, visited in this order after every hand-in. Each is a recall
# followed by a single-click and one context entry.
#
#   serial   Exact serial, tried first.
#   id/hue   Fallback if the serial is gone (hue -1 = any).
#   context  Menu entries to look for, best first. Exact match is preferred;
#            the substring fallback still refuses CONTEXT_NEVER.
STATIONS = [
    {
        # Inspected: "Armory", 0x4024AAE8, ItemID 0x151A, hue 0x0000,
        # locked down at (1274, 1164, -83). Takes the order rewards.
        "label": "Deposit items",
        "enabled": True,
        "folder": ["RO"],
        "point": "Deposit items",
        "serial": 0x4024AAE8,
        "id": 0x151A,
        "hue": 0x0000,
        "context": ["Refill From Stock"],
    },
    {
        # Inspected: "Ultimate Power Scroll Book", 0x4093D482, ItemID 0x2259,
        # hue 0x0481, locked down at (1265, 1167, -75). Takes power scrolls.
        #
        # NOTE the graphic clash: 0x2259 is also the Resource Order Book's, and
        # harvest_runner.py's BOD book. The serial is what tells them apart, so
        # the id/hue fallback is only safe because the hue differs (0x0481 here
        # against the order book's 0x04F7).
        "label": "Deposit PS",
        "enabled": True,
        "folder": ["RO"],
        "point": "Deposit PS",
        "serial": 0x4093D482,
        "id": 0x2259,
        "hue": 0x0481,
        "context": ["Refill From Stock"],
    },
]

# Where to go when the whole run ends. Empty = stay at Start Fill.
RETURN_FOLDER = []
RETURN_POINT = ""

# ---------------------------------------------------------------------------
# RUNECRAFTING STORAGE - emptied once the hand-in is done.
#
# Inspected: "Runecrafting Storage", serial 0x411CCD22, ItemID 0x2254, Blessed,
# 1 stone. Container 1093902999 with Root Container 1104416600 (the backpack),
# so it is CARRIED inside a bag in the pack, not on the ground.
#
# It is single-clicked and answered with "Refill from stock" - the same entry
# harvest_runner.py uses on the house order books.
# After handing in the deeds it carried, the pack is re-read and any FULFILLED
# deed still in it is handed in too - deeds do get missed when a snapshot is
# stale or a drag is refused. Repeated while it makes progress, up to this many
# passes.
HANDIN_SWEEP_PASSES = 3

# ---------------------------------------------------------------------------
# TRASH - run at the START of every lap, before any order is filled.
#
# Inspected:
#   "Portable Forge", ItemID 0x0FB1, hue 0x0000, 1 stone, in the backpack.
#   "Trash Bag (Deletes Items In 30 Seconds)", 0x4226C3E4, ItemID 0x09B2,
#   hue 0x07EA, in the backpack, 0/125 items.
#
# TRASH_ITEM_IDS is an ALLOWLIST and nothing else is ever moved. The bag deletes
# what goes in after 30 seconds, so a graphic must not be added here without
# being certain - a mistake here is not recoverable.
#
# Matched by GRAPHIC, not serial: every reward forge is a new item, so the
# serial in the inspector is only ever one of them.
TRASH_ENABLED = True

TRASH_BAG_SERIAL = 0x4226C3E4
TRASH_BAG_ID = 0x09B2
TRASH_BAG_HUE = 0x07EA

TRASH_ITEM_IDS = [
    0x0FB1,     # Portable Forge
]

# Ceiling per lap, so a move that never takes effect cannot spin.
TRASH_MAX_PER_LAP = 25

RUNECRAFT_ENABLED = True
RUNECRAFT_SERIAL = 0x411CCD22
RUNECRAFT_ID = 0x2254
RUNECRAFT_CONTEXT = ["Refill from stock"]

# Context entries that must NEVER be chosen by a loose substring match. A
# storage item's menu can carry something that spends or destroys stock right
# next to the entry wanted, so an exact label is tried first and a substring
# fallback refuses anything on this list.
CONTEXT_NEVER = ["buy", "sell", "bribe", "open bankbox", "train ", "empty",
                 "destroy", "delete", "discard", "drop", "release"]

CONTEXT_TIMEOUT_MS = 3000


# =============================================================================
# CONFIG - WHAT TO FILL
# =============================================================================

# Left in the chest for every resource, gems as well as ingots. Only the
# surplus above this is spendable.
#
# Per-resource override: give a RESOURCES entry its own "keep". The peerless
# ingredients all use "keep": 0 - see the PEERLESS block.
KEEP_PER_TYPE = 0

# Orders filled before the run recalls to hand them in. One trip covers all of
# them, so raising this costs little beyond time at the chest.
#
# Was 1 while the withdraw and fill mechanics were unproven. Confirmed working
# in game on 2026-07-27 - one order withdrawn, filled, handed in, returned home.
MAX_ORDERS_PER_RUN = 15

# Pages of the filtered list to search per resource before giving up. Each page
# is 15 rows.
MAX_PAGES_PER_METAL = 4

# Pages to search when the resource's name is a SUBSTRING of another one.
#
# The book's Name filter is a substring match, so searching "Copper Ingots" also
# returns every "Dull Copper Ingots" row. Those are rejected correctly by the
# exact check - but they fill the pages, so a short scan can walk four pages of
# somebody else's orders and report "no Copper Ingots orders" with plenty of
# them waiting further in. Known collisions: Copper/Dull Copper,
# Leather/Barbed+Horned+Spined, Taint/Tainted Blade, Blight/Blighted Cotton.
MAX_PAGES_WHEN_DILUTED = 20

# Presses of Previous Page allowed when rewinding a filtered list back to page
# 1. Past this it is cheaper to reopen the book, which lands on page 1 anyway.
#
# See rewind_to_first_page: submitting a new Name filter does NOT reset the page
# position, so every resource after the first would otherwise start its scan
# wherever the previous one stopped.
MAX_REWIND_PRESSES = 4

# Refuse an order asking for more than this, whatever the budget says.
#
# Raised from 5000 after seeing the real book: Shadow Ingots orders run
# 5478-6540 each, so 5000 rejected almost every one of them and the resource
# looked skipped. This is only a sanity ceiling - the per-resource budget
# (stock minus KEEP_PER_TYPE) is what actually protects the chest.
MAX_ORDER_SIZE = 25000

# Fill passes per deed. One target usually does the whole amount; the extra
# passes cover a shard that consumes one stack at a time.
MAX_FILL_ATTEMPTS = 6


# =============================================================================
# CONFIG - THE BOOK'S GUMPS
# =============================================================================
# Mapped from live dumps - see docs/resource-order-book-gump.md.

BOOK_GUMP = 0x06ABCE12
BOOK_ORDERS_BUTTON = 1          # "Resource Orders..." -> opens the list
BOOK_FILL_BUTTON = 5            # "Fill from backpack" -> deposits deeds held


# =============================================================================
# CONFIG - COLLECTING A NEW ORDER AT THE HAND-IN
#
# Handing a filled order in CLEARS THE COOLDOWN on taking a new one, so the
# moment after a hand-in is the one moment a replacement is free. One new order
# is collected per deed handed in.
# =============================================================================

NEW_ORDER_ENABLED = True

# Single-click the Resource Gatherer and answer this entry. EXACT match first,
# then a guarded substring - CONTEXT_NEVER refuses anything that spends gold,
# because an NPC menu carries Buy, Sell, Bribe and Train beside the real entry.
NEW_ORDER_CONTEXT = ["Talk"]

# How long to wait for the new deed to land in the pack after answering.
NEW_ORDER_SETTLE_MS = 1200

# Ceiling per trip, so a menu that answers without ever producing a deed cannot
# spin. One per hand-in means this only bites if MAX_ORDERS_PER_RUN is raised.
NEW_ORDER_MAX_PER_TRIP = 30

# Where new orders are parked for the trip home.
#
# Kept out of the top level of the pack on purpose: an unfilled deed sitting
# loose there is indistinguishable from one the run failed to fill, so it would
# be reported as a leftover every lap and re-examined by the filler.
#
# "a loot bag", inspected 2026-08-11: ItemID 0x0E76, hue 0x04F2, in the pack.
ORDER_BAG_SERIAL = 0x42385515
ORDER_BAG_ID = 0x0E76
ORDER_BAG_HUE = 0x04F2

ORDERS_GUMP = 0xB2F21F1A
ORDERS_NEXT_BUTTON = 5          # "Next Page"
ORDERS_PREV_BUTTON = 4          # absent on page 1, where a static image sits
ORDERS_TEXT_IDS = [0, 1, 2, 3, 4]
ORDERS_SEARCH_ENTRY = 0         # the Name column's filter box
ORDERS_FILTER_SUBMIT = 12       # its submit button

# Row buttons run continuously across pages, 15 to a page:
#     first row button of page N = ROW_BUTTON_BASE + (N - 1) * ROWS_PER_PAGE
# Confirmed against live pages 1-4. Derived from the layout at runtime anyway;
# these are only the sanity check.
ROW_BUTTON_BASE = 100
ROWS_PER_PAGE = 15

# The Name filter is a SUBSTRING match, so the term is the resource's full name
# and every row is still checked EXACTLY afterwards. Filtering "Valorite"
# returns "Valorite Granite"; filtering "Iron Ingots" also returns
# "Shadow Iron Ingots".


# =============================================================================
# CONFIG - RESOURCES. The table the book's orders are matched against.
# =============================================================================
# `name` is EXACTLY what the ORDER BOOK calls it, because that string does three
# jobs: it is typed into the Name filter, matched against the row, and matched
# against the withdrawn deed.
#
# THE BOOK'S NAME IS NOT ALWAYS THE METAL'S NAME. Shadow Iron is listed as
# "Shadow Ingots". A name that does not match returns an empty filter, and the
# resource silently looks skipped rather than reporting an error - so take these
# from the book itself, never from ServUO or from the item's own tooltip.
# `diag_resource_orders.py` prints the book's real vocabulary; run it after any
# change here.
#
# `id` + `hue` identify the stack in the chest.
#
#   Ingots  all nine share ItemID 0x1BF2 and are told apart ONLY by hue - every
#           stack is named "<amount> ingots", so the name carries the count and
#           not the metal. Hues verified against ServUO
#           Scripts/Misc/ResourceInfo.cs.
#   Gems    each has its own graphic and no meaningful hue, so hue is -1 (any).
#
# Anything not listed here is ignored, whatever the book asks for.

# EVERY NAME HERE CAME FROM THE BOOK ITSELF, harvested by diag_order_names.py
# across all 540 pages on 2026-07-28. Do not edit them from memory, from ServUO
# or from an item's own tooltip - a name that is not the book's returns an empty
# filter, and the resource looks skipped rather than erroring.
#
# The previous table was largely wrong: 38 entries the book never asks for
# (transcribed from a screenshot of the CHEST, not the book) and 48 the book
# wants that had no entry at all.
#
# Note the book's own typo: "Star Saphhire" has 144 orders against 15 for the
# correct spelling, so both are listed. `item_name` is what to look for in the
# chest when it differs from the book's spelling.
#
# `id`/`hue` are for identifying the STACK, and are only filled in where they
# have been verified. `id: 0` with `"by": "name"` matches the item by its own
# name instead, which is right for anything that carries its name (Taint, Bone)
# and wrong for anything that does not (an ingot stack is "<amount> ingots").
#
# The comment on each line is how many orders the book held for it.

RESOURCES = [
    {"name": "Agapite Granite",            "id": 0, "hue": -1, "by": "name",}, # 179 orders
    {"name": "Magewood Boards",            "id": 0, "hue": -1, "by": "name",}, # 169 orders
    {"name": "Amber",                      "id": 0, "hue": -1, "by": "name",}, # 167 orders
    {"name": "Muculent",                   "id": 0, "hue": -1, "by": "name",}, # 165 orders
    {"name": "Frostwood Boards",           "id": 0, "hue": -1, "by": "name",}, # 162 orders
    {"name": "Bloodwood Boards",           "id": 0, "hue": -1, "by": "name",}, # 161 orders
    {"name": "Taint",                      "id": 0, "hue": -1, "by": "name",}, # 160 orders
    {"name": "Darkwood Boards",            "id": 0, "hue": -1, "by": "name",}, # 159 orders
    {"name": "Regular Leather",            "id": 0x1081, "hue": 0x0000},  # 159 orders
    {"name": "Amethyst",                   "id": 0, "hue": -1, "by": "name",}, # 155 orders
    {"name": "Dark Medusa Scales",         "id": 0, "hue": -1, "by": "name",}, # 154 orders
    {"name": "Bone",                       "id": 0, "hue": -1, "by": "name",}, # 153 orders
    {"name": "Corruption",                 "id": 0, "hue": -1, "by": "name",}, # 152 orders
    {"name": "Bronze Granite",             "id": 0, "hue": -1, "by": "name",}, # 150 orders
    {"name": "Barbed Leather",             "id": 0x1081, "hue": [0x0851, 0x01C1]}, # 149 orders
    {"name": "Sand",                       "id": 0, "hue": -1, "by": "name",}, # 149 orders
    {"name": "Verite Granite",             "id": 0, "hue": -1, "by": "name",}, # 149 orders
    {"name": "Brilliant Amber",            "id": 0x3199, "hue": -1},      # 148 orders
    {"name": "Copper Granite",             "id": 0, "hue": -1, "by": "name",}, # 148 orders
    {"name": "Light Medusa Scales",        "id": 0, "hue": -1, "by": "name",}, # 148 orders
    {"name": "Mythril Ingots",             "id": 0, "hue": -1, "by": "name",}, # 146 orders
    {"name": "Ruby",                       "id": 0, "hue": -1, "by": "name",}, # 145 orders
    {"name": "Spined Leather",             "id": 0x1081, "hue": [0x08AC, 0x0283]}, # 145 orders
    {"name": "Fertile Dirt",               "id": 0, "hue": -1, "by": "name",}, # 144 orders
    {"name": "Star Saphhire",              "id": 0, "hue": -1, "by": "name", "item_name": "Star Sapphire",}, # 144 orders
    {"name": "Valorite Granite",           "id": 0, "hue": -1, "by": "name",}, # 144 orders
    {"name": "White Pearl",                "id": 0x3196, "hue": -1},      # 143 orders
    {"name": "Dread Horn Mane",            "id": 0, "hue": -1, "by": "name",}, # 142 orders
    {"name": "Citrine",                    "id": 0, "hue": -1, "by": "name",}, # 141 orders
    {"name": "Diamond",                    "id": 0, "hue": -1, "by": "name",}, # 138 orders
    {"name": "Emerald",                    "id": 0, "hue": -1, "by": "name",}, # 137 orders
    {"name": "Lard of Paroxysmus",         "id": 0, "hue": -1, "by": "name",}, # 136 orders
    {"name": "Scourge",                    "id": 0, "hue": -1, "by": "name",}, # 135 orders
    {"name": "Yew Boards",                 "id": 0, "hue": -1, "by": "name",}, # 134 orders
    {"name": "Blight",                     "id": 0, "hue": -1, "by": "name",}, # 132 orders
    {"name": "Gold Granite",               "id": 0, "hue": -1, "by": "name",}, # 132 orders
    {"name": "Grizzled Bones",             "id": 0, "hue": -1, "by": "name",}, # 126 orders
    {"name": "Horned Leather",             "id": 0x1081, "hue": [0x0845, 0x0227]}, # 126 orders
    {"name": "Putrefaction",               "id": 0, "hue": -1, "by": "name",}, # 126 orders
    {"name": "Dull Copper Granite",        "id": 0, "hue": -1, "by": "name",}, # 123 orders
    {"name": "Sapphire",                   "id": 0, "hue": -1, "by": "name",}, # 122 orders
    {"name": "Heartwood Boards",           "id": 0, "hue": -1, "by": "name",}, # 120 orders
    {"name": "Tourmaline",                 "id": 0, "hue": -1, "by": "name",}, # 120 orders
    {"name": "Captured Essence",           "id": 0, "hue": -1, "by": "name",}, # 116 orders
    {"name": "Eye of the Travesty",        "id": 0, "hue": -1, "by": "name",}, # 116 orders
    {"name": "Shadow Granite",             "id": 0, "hue": -1, "by": "name",}, # 115 orders
    {"name": "Dull Copper Ingots",         "id": 0x1BF2, "hue": 0x0973},  # 101 orders
    {"name": "Shadow Ingots",              "id": 0x1BF2, "hue": 0x0966},  # 84 orders
    {"name": "Ash Boards",                 "id": 0, "hue": -1, "by": "name",}, # 77 orders
    {"name": "Diseased Bark",              "id": 0x318B, "hue": -1},      # 71 orders
    {"name": "Valorite Ingots",            "id": 0x1BF2, "hue": 0x08AB},  # 66 orders
    {"name": "High Quality Granite",       "id": 0, "hue": -1, "by": "name",}, # 62 orders
    {"name": "Agapite Ingots",             "id": 0x1BF2, "hue": 0x0979},  # 61 orders
    {"name": "Bronze Ingots",              "id": 0x1BF2, "hue": 0x0972},  # 60 orders
    {"name": "Oak Boards",                 "id": 0, "hue": -1, "by": "name",}, # 38 orders
    {"name": "Verite Ingots",              "id": 0x1BF2, "hue": 0x089F},  # 37 orders
    {"name": "Copper Ingots",              "id": 0x1BF2, "hue": 0x096D},  # 31 orders
    {"name": "Gold Ingots",                "id": 0x1BF2, "hue": 0x08A5},  # 29 orders
    {"name": "Regular Boards",             "id": 0, "hue": -1, "by": "name",}, # 25 orders
    {"name": "Luminescent Fungi",          "id": 0x3191, "hue": -1},      # 21 orders
    {"name": "Black Scales",               "id": 0, "hue": -1, "by": "name",}, # 19 orders
    {"name": "Switch",                     "id": 0, "hue": -1, "by": "name",}, # 19 orders
    {"name": "Delicate Scales",            "id": 0, "hue": -1, "by": "name",}, # 17 orders
    {"name": "Small Piece of Blackrock",   "id": 0x0F28, "hue": -1},      # 17 orders
    {"name": "Yellow Scales",              "id": 0, "hue": -1, "by": "name",}, # 17 orders
    {"name": "Green Scales",               "id": 0, "hue": -1, "by": "name",}, # 16 orders
    {"name": "Parasitic Plant",            "id": 0, "hue": -1, "by": "name",}, # 16 orders
    {"name": "Star Sapphire",              "id": 0, "hue": -1, "by": "name",}, # 15 orders
    {"name": "Bark Fragment",              "id": 0x318F, "hue": -1},      # 14 orders
    {"name": "Raw Fish Steak",             "id": 0, "hue": -1, "by": "name",}, # 13 orders
    {"name": "Blue Scales",                "id": 0, "hue": -1, "by": "name",}, # 12 orders
    {"name": "Red Scales",                 "id": 0, "hue": -1, "by": "name",}, # 11 orders
    {"name": "White Scales",               "id": 0, "hue": -1, "by": "name",}, # 8 orders
    {"name": "Blue Diamond",               "id": 0x3198, "hue": -1},      # 1 orders
    {"name": "Dark Sapphire",              "id": 0x3192, "hue": -1},      # 1 orders
    {"name": "Ecru Citrine",               "id": 0x3195, "hue": -1},      # 1 orders
    {"name": "Fire Ruby",                  "id": 0x3197, "hue": -1},      # 1 orders
    {"name": "Iron Ingots",                "id": 0x1BF2, "hue": 0x0000},  # 1 orders
    {"name": "Turquoise",                  "id": 0x3193, "hue": -1},      # 1 orders
]

# Peerless ingredients are spendable to the last one - the obelisks refill them
# and more can be added by hand. Everything else keeps KEEP_PER_TYPE back.
#
# Only the ingredients from the peerless chest are listed. General resources the
# book also asks for (Bone, Sand, Fertile Dirt, Switch, Raw Fish Steak,
# Parasitic Plant, blackrock, scales, granite, boards) keep their reserve.
KEEP_NOTHING = [
    "Taint", "Blight", "Corruption", "Scourge", "Putrefaction", "Muculent",
    "Dread Horn Mane", "Captured Essence", "Eye of the Travesty",
    "Grizzled Bones", "Lard of Paroxysmus", "Diseased Bark",
    "Luminescent Fungi", "Bark Fragment",
]

for _entry in RESOURCES:
    if _entry["name"] in KEEP_NOTHING:
        _entry["keep"] = 0


# =============================================================================
# CONFIG - WOOD BOARDS
#
# Boards go loose in one of the CHESTS above, the same as the ingots, so the
# census finds them with no extra plumbing. The ONLY thing that has to work is
# telling one wood from another.
# =============================================================================

# The board graphic. 0x1BD9 is deliberately NOT here: that is the Wood Storage
# key's own graphic (harvest_runner's WOOD_STORAGE_ID), and including it would
# have the runner count the key itself as a stack of boards.
BOARD_IDS = [0x1BD7]

# hue -> the name the BOOK uses for it. EMPTY until filled from a real stack.
#
# Boards are told apart by HUE, not by name, for the same reason ingots are: a
# stack is called "<amount> boards" and says nothing about the wood. Until a
# hue is listed here the runner cannot tell one wood from another, and it will
# NOT guess - pouring Oak into a Magewood order cannot be undone.
#
# HOW TO FILL THIS IN: put a stack of each wood in the chest and run the script
# once. The stock report names every board stack whose hue it does not know,
# with the exact line to paste in here. Nothing else is needed.
#
# Note the vocabularies differ, exactly as they do for ingots ("golden" on the
# stack, "Gold" in the book): the storage window says "Plain", the book calls
# the same wood "Regular Boards". The name on the LEFT here must be the book's.
# Confirmed from a live chest dump on 2026-08-03 by diag_chest_contents.py.
# Eight of the nine name their wood on the stack's third tooltip line, exactly
# as ingots name their metal:
#
#     20060 board / Weight: 20060 stones / ash
#
# Note "Magewood" and "Darkwood" arrive capitalised where the other six are
# lower case - they are this shard's own woods and are in no ServUO table, so
# the dump is the ONLY source for them.
BOARD_HUES = {
    # Hue 0x0000 carries NO wood line at all, which is how the default wood
    # renders - the same way plain iron is the one ingot with no third line
    # (see docs/resource-order-book-gump.md). Nothing else in the chest uses
    # 0x1BD7, so there is no other candidate. The book calls it "Regular
    # Boards"; the wood storage window calls the same wood "Plain".
    "Regular Boards":   0x0000,      # 91,715 on hand
    "Oak Boards":       0x07DA,      # 189,690
    "Ash Boards":       0x04A7,      # 20,060
    "Yew Boards":       0x04A8,      # 8,400
    "Heartwood Boards": 0x04A9,      # 5,460
    "Bloodwood Boards": 0x04AA,      # 3,085
    "Frostwood Boards": 0x047F,      # 1,840
    "Magewood Boards":  0x0AAC,      # 90
    "Darkwood Boards":  0x078C,      # 80
}

# Give the board entries a graphic to match on. An entry with no hue yet keeps
# its "by": "name" match, which is harmless - it simply will not match a stack
# called "<amount> boards", which is the state everything is in today.
for _entry in RESOURCES:
    _hue = BOARD_HUES.get(_entry["name"])
    if _hue is not None:
        _entry["id"] = BOARD_IDS[0]
        _entry["hue"] = _hue
        _entry.pop("by", None)


# Which of the above to work, in order. Empty = every entry in RESOURCES.
WORK_RESOURCES = []

# Merge a metal's stacks into one when the biggest cannot cover what an order
# still needs. The chest holds a dozen iron stacks and several of most other
# metals; without this, a nearly-spent metal ends up spread across scraps that
# no single target can satisfy.
CONSOLIDATE_STACKS = True

# Tidy the chest before doing anything else: every metal merged down to one
# stack. Costs one drag per surplus stack (about a second each), once per run,
# and after the first pass there is usually nothing left to do.
#
# Worth it beyond neatness - the chest is capped at 125 items, and one stack per
# metal means one target fills any order.
ORGANIZE_CHEST = True

# Most a single stack can hold. Iron runs to 840,000, so it can never be one
# stack - consolidation fills stacks to this and leaves at most one partial.
MAX_STACK = 60000

# Ceiling on merge moves per resource. Iron across a dozen stacks needs about
# that many; the bound is only there so a merge that never takes effect cannot
# spin.
MAX_MERGE_MOVES = 40


# =============================================================================
# CONFIG - THE ACCOUNT RUNEBOOK
# =============================================================================
# Same values harvest_runner.py and diag_bods.py use. Server-side paging.

AR_COMMAND = "[ar"
AR_GUMPID = 0xC395ADB4
AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON = 5
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 500, 503, 504]
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
AR_GATE_OFFSET = 30000
AR_MAX_PAGES = 20
MIN_MANA_TO_TRAVEL = 20


# =============================================================================
# CONFIG - TIMINGS (ms unless named otherwise)
# =============================================================================

# =============================================================================
# CONFIG - WORLD SAVE, AND STRAY WINDOWS
# =============================================================================

# Stop working while the shard saves. Everything freezes during a save, so an
# action sent into one is simply lost - the gump never answers, the target
# never lands, and the step is scored as a failure it did not deserve.
WORLD_SAVE_PAUSE = True

# Matched case-insensitively against NEW journal lines only, via a timestamp
# cursor - never Search, which scans the whole buffer and would re-fire on the
# same warning every time it was called.
#
#     System: The world will save in 30 seconds
WORLD_SAVE_PHRASES = [
    "the world will save in",
    "world save in",
]

# How long to sit still, measured from WHEN THE WARNING WAS SEEN - not from
# when the pause starts. The warning gives 30 seconds' notice, so 45 covers the
# countdown plus the save itself. If the warning is noticed late the remaining
# wait shrinks to match, which is correct: that time has already passed.
WORLD_SAVE_PAUSE_MS = 45000

# How often to look at the journal while waiting one out.
WORLD_SAVE_POLL_MS = 500

# Close windows the script is finished with, instead of leaving them stacked up
# on screen. A lap opens the book, the order list, two chests, the runecrafting
# storage and one gump per deposit stop; before this, only the book and the
# order list were ever closed, and only when the lap had filled something.
CLOSE_STRAY_GUMPS = True

GUMP_TIMEOUT_MS = 10000
CONTENTS_TIMEOUT_MS = 4000
PROPS_TIMEOUT_MS = 1500
TARGET_TIMEOUT_MS = 4000
TARGET_SETTLE_MS = 400          # confirmed necessary on this shard
SETTLE_MS = 600
MOVE_PAUSE_MS = 900             # drag rate limit
RECALL_SETTLE_MS = 2500
MEDITATE_TIMEOUT_S = 90


# =============================================================================
# SERVER MESSAGES
# =============================================================================
# Checked against the shard as they are confirmed. Annotate with the cliloc
# number once known.

MSG_NO_MANA = ["you don't have enough mana", "insufficient mana"]
MSG_CANNOT_SEE = ["you cannot see", "that is too far away"]
MSG_ORDER_FULL = ["the order is complete", "order has been filled"]


# =============================================================================

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[RO] " + str(text), hue, False)


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


# ---------------------------------------------------------------------------
# Compatibility shims - these signatures have changed between builds.
# ---------------------------------------------------------------------------

def chat_say(text):
    try:
        Player.ChatSay(0, text)
    except TypeError:
        Player.ChatSay(text)


def gump_lines(gump_id, data_only=False):
    try:
        return list(Gumps.GetLineList(gump_id, data_only))
    except TypeError:
        return list(Gumps.GetLineList(gump_id))


def has_gump(gump_id):
    try:
        return bool(Gumps.HasGump(gump_id))
    except TypeError:
        return bool(Gumps.HasGump()) and Gumps.CurrentGump() == gump_id


def raw_layout(gump_id):
    try:
        return Gumps.GetGumpRawLayout(gump_id) or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Stray windows
# ---------------------------------------------------------------------------

def tidy_gumps(keep=(), why=""):
    """Close every open gump except the ids in `keep`. Returns how many.

    A lap opens the book, the order list, both chests, the runecrafting storage
    and one gump per deposit stop. Only the book and the order list were ever
    closed, and only on the path where the lap had filled something - so an
    unattended run came back to a screen stacked with windows, and every one of
    them is a chance for Gumps.WaitForGump to answer the wrong one, since it
    returns True for a gump that is ALREADY open.
    """
    if not CLOSE_STRAY_GUMPS:
        return 0
    keep_ids = set(int(k) for k in keep)
    try:
        open_ids = [int(g) for g in (Gumps.AllGumpIDs() or [])]
    except Exception as err:
        log("could not list open gumps: %s" % err, HUE_WARN)
        return 0

    closed = []
    for gump_id in open_ids:
        if gump_id in keep_ids:
            continue
        try:
            Gumps.CloseGump(gump_id)
            closed.append(gump_id)
        except Exception:
            pass

    if closed:
        Misc.Pause(SETTLE_MS)
        log("closed %d stray window(s)%s: %s"
            % (len(closed), " (%s)" % why if why else "",
               ", ".join("0x%X" % g for g in closed[:8])))
    return len(closed)


# ---------------------------------------------------------------------------
# World save
#
# A timestamp cursor, not Search + Clear. Search scans the whole buffer, so one
# warning would re-fire on every call for the rest of the run; and travel_to
# calls Journal.Clear() for its own mana check, which would throw the warning
# away before it was ever seen.
# ---------------------------------------------------------------------------

_journal_cursor = [0.0]
_save_seen_at = [0.0]


def prime_journal_cursor():
    """Start the cursor at NOW, so lines from before the run are ignored."""
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            stamp = float(getattr(entry, "Timestamp", 0.0) or 0.0)
            if stamp > _journal_cursor[0]:
                _journal_cursor[0] = stamp
    except Exception:
        _journal_cursor[0] = 0.0


def new_journal_entries():
    """Journal lines that have appeared since the last call."""
    try:
        entries = Journal.GetJournalEntry(_journal_cursor[0])
    except Exception:
        return []
    fresh = []
    for entry in entries or []:
        stamp = float(getattr(entry, "Timestamp", 0.0) or 0.0)
        if stamp > _journal_cursor[0]:
            _journal_cursor[0] = stamp
        fresh.append(entry)
    return fresh


def poll_world_save():
    """Note a world-save warning. Safe to call anywhere, including in waits.

    Detection only - it never sleeps. Acting on it from inside a wait would
    recurse through whatever was already waiting; the caller decides when it is
    safe to stand still. Returns True if a NEW warning was seen.
    """
    if not WORLD_SAVE_PAUSE:
        return False
    seen = False
    for entry in new_journal_entries():
        text = str(getattr(entry, "Text", "") or "").lower()
        if not text:
            continue
        for phrase in WORLD_SAVE_PHRASES:
            if phrase.strip().lower() in text:
                _save_seen_at[0] = time.time()
                log("world save announced: %s" % text.strip()[:60], HUE_WARN)
                seen = True
                break
    return seen


def wait_out_world_save():
    """Sit still if a save was announced. True if it actually waited.

    Called at SAFE POINTS only - between orders, between stops, before a
    recall - never in the middle of one. The deadline is measured from when the
    warning was seen, so noticing it late shortens the wait instead of adding
    to it.
    """
    poll_world_save()
    if not _save_seen_at[0]:
        return False

    deadline = _save_seen_at[0] + (WORLD_SAVE_PAUSE_MS / 1000.0)
    _save_seen_at[0] = 0.0
    if time.time() >= deadline:
        return False        # the warning was old news; nothing left to wait

    log("pausing %.0fs for the world save" % (deadline - time.time()),
        HUE_WARN)
    while time.time() < deadline:
        Misc.Pause(WORLD_SAVE_POLL_MS)
        if poll_world_save():
            # A second warning during the pause - push the deadline out rather
            # than resuming into the save it is announcing.
            deadline = _save_seen_at[0] + (WORLD_SAVE_PAUSE_MS / 1000.0)
            _save_seen_at[0] = 0.0
    log("world save over - resuming", HUE_GOOD)
    return True


def checkpoint(keep=(), why=""):
    """A safe point: wait out any save, then clear stray windows.

    In that order. Closing windows first would just have the save freeze the
    close packets.
    """
    waited = wait_out_world_save()
    tidy_gumps(keep, why)
    return waited


# ---------------------------------------------------------------------------
# Target cursor. Everything that needs a cursor goes through here.
#
# A leaked cursor silently eats the NEXT TargetExecute, and WaitForTarget
# returns True for a cursor that is already open, so the queue is cleared and
# the absence of a cursor asserted before every request.
# ---------------------------------------------------------------------------

def clear_cursor():
    try:
        Target.Cancel()
        Target.ClearQueue()
        Target.ClearLast()
    except Exception:
        pass
    Misc.Pause(120)
    return not Target.HasTarget()


def use_and_target(item, target_serial, what):
    """UseItem -> WaitForTarget -> settle -> TargetExecute.

    The docs warn the built-in Items.UseItem(item, target) "may not work on some
    free shards", and the manual sequence is what is confirmed working here.
    Both the settle pause and the cursor cancel are required; do not remove
    either.
    """
    if not clear_cursor():
        log("A target cursor is stuck open, cannot %s." % what, HUE_BAD)
        return False

    Items.UseItem(item)
    if not Target.WaitForTarget(TARGET_TIMEOUT_MS, False):
        log("No target cursor appeared for %s." % what, HUE_WARN)
        clear_cursor()
        return False

    Misc.Pause(TARGET_SETTLE_MS)
    Target.TargetExecute(target_serial)
    Misc.Pause(SETTLE_MS)
    return True


# ---------------------------------------------------------------------------
# Items
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


def props(item):
    try:
        Items.WaitForProps(item, PROPS_TIMEOUT_MS)
        return [str(p) for p in Items.GetPropStringList(item)]
    except Exception:
        return []


def spaced(raw):
    """Insert a space at each lower/digit -> upper seam.

    Tooltip properties arrive concatenated - "Level: 2Resource Type: Iron
    IngotsFilled: 24/500" - so lowercasing gives "ingotsfilled" and any regex
    ending in \\b silently fails to match.
    """
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw or "")


def open_container(item, label):
    try:
        Items.UseItem(item)
        ok = Items.WaitForContents(item, CONTENTS_TIMEOUT_MS)
    except Exception as err:
        log("%s: could not open: %s" % (label, err), HUE_WARN)
        return False
    Misc.Pause(SETTLE_MS)
    return bool(ok)


def worked_resources():
    """The RESOURCES entries to work, in order."""
    if not WORK_RESOURCES:
        return list(RESOURCES)
    by_name = dict((r["name"].lower(), r) for r in RESOURCES)
    out = []
    for name in WORK_RESOURCES:
        entry = by_name.get(name.strip().lower())
        if entry is None:
            log("WORK_RESOURCES names %r, which is not in RESOURCES - skipped."
                % name, HUE_BAD)
            continue
        out.append(entry)
    return out


def entry_hues(entry):
    """The hues a RESOURCES entry accepts, always as a list.

    Leather needs several: ServUO keeps two leather tables and chooses between
    them at runtime, so both hue sets are listed and either matches.
    """
    hue = entry.get("hue", -1)
    if isinstance(hue, (list, tuple)):
        return [int(h) for h in hue]
    return [int(hue)]


def strip_amount(name):
    """"60000 ingots" -> "ingots", "36 Taint" -> "Taint".

    A stack's name carries its own count, so the count has to come off before
    the name can be compared to anything.
    """
    return re.sub(r"^\s*[\d,]+\s+", "", name or "").strip()


def resource_of(item):
    """The resource name a stack is, or None.

    Two ways to identify one, because the two families of resource are not
    alike:

      by graphic  ingots and gems. ItemID plus hue, NEVER the item's own name -
                  an ingot stack is called "<amount> ingots" and says nothing
                  about the metal. hue -1 matches any, which is how gems work.
      by name     peerless ingredients. These carry their own name ("Taint") and
                  their graphics are unknown, so the name is all there is.

    Graphic entries are tried first: they are the stricter test, and a name
    comparison should never get the chance to claim an ingot stack.
    """
    try:
        item_id = int(item.ItemID)
        hue = int(item.Hue)
    except Exception:
        return None

    for entry in RESOURCES:
        if entry.get("by") == "name":
            continue
        if entry["id"] != item_id:
            continue
        if -1 in entry_hues(entry) or hue in entry_hues(entry):
            return entry["name"]

    bare = strip_amount(getattr(item, "Name", "") or "").lower()
    if not bare:
        return None
    for entry in RESOURCES:
        if entry.get("by") != "name":
            continue
        # `item_name` is what the ITEM is called when that differs from what
        # the BOOK calls it - the book has "Star Saphhire" where the gem is a
        # Star Sapphire.
        wanted = entry.get("item_name", entry["name"]).strip().lower()
        if bare == wanted:
            return entry["name"]
    return None


def as_list(value):
    """One chest or many - callers should not have to care."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [v for v in value if v is not None]
    return [value]


def find_chests():
    """Every enabled chest that could be found, as (item, label) pairs.

    A missing chest is reported and skipped rather than fatal: the peerless
    chest is expected to be absent until it has been placed.
    """
    found = []
    for entry in CHESTS:
        if not entry.get("enabled"):
            log("chest %r is disabled - skipped" % entry.get("label", "?"))
            continue
        item = find_world_item(entry.get("serial", 0), entry["id"],
                               entry.get("hue", -1), entry.get("label", "chest"))
        if item is None:
            log("chest %r not found within %d tiles - its resources will show "
                "no stock." % (entry.get("label", "?"), WORLD_RANGE), HUE_WARN)
            continue
        log("chest %r found, %d tiles away"
            % (entry.get("label", "?"), Player.DistanceTo(item)), HUE_GOOD)
        found.append(item)
    return found


def chest_of(stack, chests):
    """Which chest a stack sits in, for merges that must stay in one container."""
    serial = int(getattr(stack, "Container", 0) or 0)
    for chest in as_list(chests):
        if int(chest.Serial) == serial:
            return chest
    return None


def refresh_chest(chest, tries=3):
    """Re-open the chest so its Contains list is current. Returns the Item.

    `Contains` is the ONLY way to see inside a container, and it is a snapshot
    taken when the container was opened - so it goes stale as stacks are spent
    or merged.

    Asking a different way does NOT help: Items.FindAllByID with a container
    serial does not query the item index, it iterates that exact same Contains
    list. Confirmed in Razor/RazorEnhanced/Item.cs at v1.0.0.14:

        // else just search in container
        Item cont = FindBySerial(container);
        foreach (Item i in cont.Contains)

    An earlier version of this script unioned the two and believed it had a
    second opinion. It had the same one twice. Reopening the container is the
    only real refresh.
    """
    serial = int(chest.Serial)
    for _ in range(max(1, tries)):
        item = Items.FindBySerial(serial)
        if item is None:
            return None
        try:
            Items.UseItem(item)
            Items.WaitForContents(item, CONTENTS_TIMEOUT_MS)
        except Exception:
            pass
        Misc.Pause(SETTLE_MS)
        fresh = Items.FindBySerial(serial)
        if list(getattr(fresh, "Contains", None) or []):
            return fresh
    return Items.FindBySerial(serial)


def all_resource_stacks(chests):
    """{resource: [stacks, largest first]} across EVERY chest.

    Takes a list, so stock spread over several containers is one pool - the
    peerless ingredients live in their own chest and still have to be counted
    with the rest.

    Reads each `Contains`, which is a snapshot - see refresh_chest for why there
    is no second source and how to make it current.
    """
    seen = {}
    for chest in as_list(chests):
        for item in list(getattr(chest, "Contains", None) or []):
            seen[int(item.Serial)] = item

    out = {}
    for item in seen.values():
        resource = resource_of(item)
        if resource is None:
            continue
        out.setdefault(resource, []).append(item)
    for resource in out:
        out[resource].sort(key=lambda s: -int(getattr(s, "Amount", 0) or 0))
    return out


def only_live(stacks):
    """Drop stacks that no longer exist, and refresh the Amount of those that do.

    `Contains` keeps listing a stack after it has been merged away or spent, so
    a census taken straight off it counts ghosts. Items.FindBySerial goes to the
    world list instead, which is what tells the two apart.
    """
    out = []
    for stack in stacks:
        fresh = Items.FindBySerial(int(stack.Serial))
        if fresh is None:
            continue
        if int(getattr(fresh, "Amount", 0) or 0) <= 0:
            continue
        out.append(fresh)
    out.sort(key=lambda s: -int(getattr(s, "Amount", 0) or 0))
    return out


def unknown_board_stacks(chests):
    """Board stacks whose hue is not in BOARD_HUES: {hue: {amount, stacks}}.

    This is what makes BOARD_HUES fillable without guessing. A board stack is
    called "<amount> boards" and says nothing about the wood, so an unlisted
    hue is invisible to resource_of and the wood silently has no stock - the
    same silent failure the ingot hue table was written to end.
    """
    known = set(int(h) for h in BOARD_HUES.values())
    out = {}
    for chest in as_list(chests):
        for item in list(getattr(chest, "Contains", None) or []):
            try:
                if int(item.ItemID) not in BOARD_IDS:
                    continue
                hue = int(item.Hue)
            except Exception:
                continue
            if hue in known:
                continue
            record = out.setdefault(hue, {"amount": 0, "stacks": 0})
            record["amount"] += int(getattr(item, "Amount", 0) or 0)
            record["stacks"] += 1
    return out


def report_unknown_boards(chests):
    """Name every board hue the runner cannot identify, with the line to paste.

    Printed as part of the stock report rather than buried: a wood with no hue
    listed has NO stock as far as the budget is concerned, so its orders are
    passed over exactly as if the chest were empty. That is indistinguishable
    from "the book has no orders for it" unless it is said out loud.
    """
    unknown = unknown_board_stacks(chests)
    if not unknown:
        return

    log("%d board hue(s) in the chest are not in BOARD_HUES, so the runner "
        "cannot tell which wood they are and will not spend them:"
        % len(unknown), HUE_WARN)
    for hue, record in sorted(unknown.items(), key=lambda kv: -kv[1]["amount"]):
        log("    hue 0x%04X  %d board(s) in %d stack(s)"
            % (hue, record["amount"], record["stacks"]), HUE_WARN)
    log("  Match each hue to a wood in the storage window, then paste into "
        "BOARD_HUES at the top of this script:", HUE_WARN)
    for hue in sorted(unknown):
        log('      "<Wood> Boards": 0x%04X,' % hue, HUE_WARN)
    log("  Use the BOOK's name on the left - plain boards are "
        "\"Regular Boards\" there, not \"Plain\".", HUE_WARN)


def validate_board_hues():
    """Refuse a BOARD_HUES that cannot work, loudly, at startup."""
    ok = True
    by_name = dict((r["name"].strip().lower(), r) for r in RESOURCES)

    for name, hue in BOARD_HUES.items():
        if name.strip().lower() not in by_name:
            log("BOARD_HUES names %r, which is not in RESOURCES - it will "
                "never match an order. Check the spelling against the book."
                % name, HUE_BAD)
            ok = False

    seen = {}
    for name, hue in BOARD_HUES.items():
        if int(hue) in seen:
            log("BOARD_HUES gives hue 0x%04X to both %r and %r - one of them "
                "would be filled with the other's wood."
                % (int(hue), seen[int(hue)], name), HUE_BAD)
            ok = False
        seen[int(hue)] = name

    if BOARD_HUES:
        log("boards: %d wood(s) identified by hue" % len(BOARD_HUES),
            HUE_GOOD if ok else HUE_BAD)
    else:
        log("boards: BOARD_HUES is empty, so no wood can be identified yet. "
            "Put a stack of each in the chest and the stock report below will "
            "print the table to paste in.", HUE_WARN)
    return ok


def census(chests):
    """{resource: {"amount", "stacks"}} for everything workable, all chests.

    Counts only stacks that still exist. Organizing merges stacks away, so a
    census taken off the raw snapshot afterwards double-counts the ones that
    were poured out - and a resource can end up with a budget that does not
    match what is really there.
    """
    stock = {}
    for resource, stacks in all_resource_stacks(chests).items():
        live = only_live(stacks)
        if not live:
            continue
        stock[resource] = {
            "amount": sum(int(getattr(s, "Amount", 0) or 0) for s in live),
            "stacks": live,
        }
    return stock


def keep_for(resource):
    """How much of `resource` stays in the chest.

    Per resource, not global: peerless ingredients carry "keep": 0 because the
    obelisks refill them, while ingots and gems hold KEEP_PER_TYPE back.
    """
    target = (resource or "").strip().lower()
    for entry in RESOURCES:
        if entry["name"].strip().lower() == target:
            return int(entry.get("keep", KEEP_PER_TYPE))
    return KEEP_PER_TYPE


def fill_budget(stock, keep=None):
    """Spendable amount per resource, reserve off the TOTAL not each stack.

    `keep=None` uses each resource's own reserve; pass a number to override the
    lot (the tests do).
    """
    out = {}
    for res, data in stock.items():
        reserve = keep_for(res) if keep is None else keep
        out[res] = max(0, data["amount"] - reserve)
    return out


# ---------------------------------------------------------------------------
# Order deeds
# ---------------------------------------------------------------------------

# A real deed, from the Item Inspector on 2026-07-27:
#
#   Name:   A Resource Order Deed      ItemID: 0x14F0    Blessed, 1 stone
#   Container / Root Container: 1104416600 (= 0x41D40F58, the backpack)
#   Tooltip:
#       A Resource Order Deed
#       Blessed
#       Weight: 1 Stone
#       0 / 132 Valorite Granite ObtainedValued At: 400 Gold Each
#
# It carries NO "Resource Type:" or "Filled:" labels - those belong to taming
# orders. An earlier version of this parser looked for them, inferred from a
# comment in harvest_runner.py, and would have failed to read a single deed.
#
# Note the "ObtainedValued" seam: tooltip properties arrive concatenated, so
# spaced() has to run before any of this matches.
# A COMPLETED deed reads differently again - inspected 2026-07-27, serial
# 0x40565AF7, still ItemID 0x14F0 and still in the backpack (it is NOT consumed
# on completion, so it can be carried to the hand-in):
#
#       A Resource Order Deed
#       Blessed
#       Weight: 1 Stone
#       Order Fulfilled [1038 Copper Ingots]Valued At: 25 Gold Each
#
# So there are two shapes, and neither shares a single label with the other.
DEED_ID = 0x14F0

DEED_PROGRESS_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s+(.+?)\s+Obtained\b", re.I)
DEED_DONE_RE = re.compile(
    r"Order\s+Fulfilled\s*\[\s*([\d,]+)\s+([^\]]+?)\s*\]", re.I)
DEED_VALUE_RE = re.compile(r"Valued\s+At:\s*([\d,]+)\s*Gold", re.I)


def parse_deed(raw):
    """{"filled", "needed", "resource", "gold_each", "complete"} from a tooltip.

    Handles both shapes. In progress, the resource is whatever sits between the
    "N / M" and the word "Obtained"; once fulfilled it is inside the brackets
    after the amount. Either way it comes out whole - "Shadow Iron Ingots" needs
    no catalogue to match against.

    A fulfilled deed reports filled == needed, so callers testing progress do
    not need to know about the second shape at all.
    """
    text = spaced(raw)
    found = {}

    done = DEED_DONE_RE.search(text)
    if done:
        amount = int(done.group(1).replace(",", ""))
        found["complete"] = True
        found["filled"] = amount
        found["needed"] = amount
        found["resource"] = re.sub(r"\s+", " ", done.group(2)).strip()
    else:
        match = DEED_PROGRESS_RE.search(text)
        if match:
            found["complete"] = False
            found["filled"] = int(match.group(1))
            found["needed"] = int(match.group(2))
            found["resource"] = re.sub(r"\s+", " ", match.group(3)).strip()

    value = DEED_VALUE_RE.search(text)
    if value:
        found["gold_each"] = int(value.group(1).replace(",", ""))
    return found


def deed_progress(fields):
    if "needed" not in fields:
        return None, None
    return fields.get("filled", 0), fields["needed"]


def read_deed(item):
    """(fields, filled, needed) for a deed, freshly re-read from the server."""
    tooltip = props(item)
    fields = parse_deed(" ".join(tooltip))
    filled, needed = deed_progress(fields)
    return fields, filled, needed


def reread_deed(serial, tries=3):
    """Re-read a deed by serial after it has changed.

    Returns (filled, needed, item, tooltip). `item` is None when the deed is no
    longer in the pack, which is how a completed order can disappear; `needed`
    is None when the tooltip is there but no longer carries a
    "N / M <resource> Obtained" line.

    The retry matters: a tooltip can come back empty for a moment right after
    the server updates the item, and a single read then parses to nothing. That
    is what crashed the first live run - the fill worked, the re-read returned
    None, and the progress line tried to format it with %d.
    """
    item = None
    tooltip = []
    for _ in range(max(1, tries)):
        item = Items.FindBySerial(int(serial))
        if item is None:
            return None, None, None, []
        tooltip = props(item)
        fields = parse_deed(" ".join(tooltip))
        filled, needed = deed_progress(fields)
        if needed is not None:
            return filled, needed, item, tooltip
        Misc.Pause(SETTLE_MS)
    return None, None, item, tooltip


def progress_text(filled, needed):
    """"24/500", or "?" - never a %d against None."""
    if filled is None or needed is None:
        return "?"
    return "%d/%d" % (filled, needed)


def is_order_deed(item):
    """Recognised by its text, not its graphic.

    0x14F0 is the generic deed/writ graphic and other deeds share it, so the
    ItemID alone would sweep up anything else in the pack.
    """
    blob = " ".join([item.Name or ""] + props(item))
    if "resource order" in blob.lower():
        return True
    text = spaced(blob)
    return bool(DEED_PROGRESS_RE.search(text) or DEED_DONE_RE.search(text))


def deed_matches_resource(fields, resource):
    """True only if the deed asks for exactly `resource`.

    EXACT, because every looser test has already gone wrong here:

    The book carries granite and ore orders under the same metal names - a run
    after Valorite ingots came back with a Valorite GRANITE deed.

    And a substring test is no better: "Iron Ingots" is inside "Shadow Iron
    Ingots", so an Iron run would accept a Shadow Iron order and pour the wrong
    metal at it forever. Gems have the same shape of problem waiting in
    "Perfect Emerald" against any future "Emerald".
    """
    want = (fields.get("resource") or "").strip().lower()
    if not want:
        return False
    # Tolerate a trailing plural difference only ("Iron Ingot" / "Iron Ingots").
    target = resource.strip().lower()
    return want == target or want == target.rstrip("s") or want + "s" == target


def pack_items(also_id=-1):
    """Everything in the backpack, from a REFRESHED snapshot.

    The pack is reopened first. Contains is a snapshot and goes stale, and an
    item missing from it is exactly how a deed gets left behind at the hand-in.
    `also_id` adds a direct query for one graphic on top, for the same reason.
    """
    backpack = Player.Backpack
    if backpack is None:
        return []
    try:
        Items.UseItem(backpack)
        Items.WaitForContents(backpack, CONTENTS_TIMEOUT_MS)
    except Exception:
        pass
    Misc.Pause(SETTLE_MS)

    backpack = Player.Backpack
    if backpack is None:
        return []
    seen = {}
    for item in list(getattr(backpack, "Contains", None) or []):
        seen[int(item.Serial)] = item
    if also_id != -1:
        try:
            found = Items.FindAllByID(also_id, -1, int(backpack.Serial), -1,
                                      False)
            for item in list(found or []):
                seen[int(item.Serial)] = item
        except Exception:
            pass
    return list(seen.values())


def pack_deeds():
    """Every order deed in the pack."""
    return [i for i in pack_items(DEED_ID) if is_order_deed(i)]


def deed_is_complete(item):
    """True only if this deed is fulfilled and worth handing in.

    A deed that was declined, or filled part way before something stopped, must
    NOT be handed in - it would be spent for nothing.
    """
    fields, filled, needed = read_deed(item)
    if fields.get("complete"):
        return True
    return (filled is not None and needed is not None and filled >= needed)


def pack_serials():
    """Serials in the backpack, for diffing across a withdrawal.

    Backpack.Contains is a snapshot with the same staleness as any container's,
    so it is unioned with a direct query for the deed graphic. Without that, a
    freshly withdrawn deed could be missing from the diff and the withdrawal
    would look like it had failed - which is what stopped the run after its
    first order.
    """
    backpack = Player.Backpack
    if backpack is None:
        return set()
    seen = set()
    for item in list(getattr(backpack, "Contains", None) or []):
        seen.add(int(item.Serial))
    try:
        found = Items.FindAllByID(DEED_ID, -1, int(backpack.Serial), -1, False)
        for item in list(found or []):
            seen.add(int(item.Serial))
    except Exception:
        pass
    return seen


# ---------------------------------------------------------------------------
# The order list
# ---------------------------------------------------------------------------

ROW_FLAGS = ("yes", "no", "none", "")

# The header line, confirmed from the rendered gump:
#     Name | Amt To Gather | Amt Gathered | Value Per | Completed
# Rows start after whichever of these appears LAST in the string list, not after
# a single hard-coded label - "Value Per" is the fourth of five, so anchoring on
# it alone leaves "Completed" sitting in the row region.
HEADER_LABELS = ("name", "amt to gather", "amt gathered", "value per",
                 "completed")
FOOTER_FIRST = ("previous page", "next page")


def layout_elements(layout):
    out = []
    for piece in re.findall(r"\{([^{}]*)\}", layout or ""):
        piece = piece.strip()
        if not piece:
            continue
        out.append({"kind": piece.split()[0].lower(),
                    "nums": [int(n) for n in re.findall(r"-?\d+", piece)]})
    return out


def row_buttons(layout, x_max=60, y_min=80, y_max=400):
    """The 15 per-row buttons, top to bottom.

    Taken from the left margin between the header and the filter row, which
    excludes the column sorters at y=70 and the page nav at y=440.
    """
    found = []
    for el in layout_elements(layout):
        if el["kind"] != "button" or len(el["nums"]) < 3:
            continue
        x, y, button = el["nums"][0], el["nums"][1], el["nums"][-1]
        if x <= x_max and y_min <= y <= y_max:
            found.append((y, button))
    return [b for _y, b in sorted(found)]


def parse_order_rows(strings, anchor=None):
    """[{"name", "amount"}] per row, in display order.

    Matched by SHAPE, not position. Razor drops empty strings out of a gump's
    string table without leaving a gap, so layout text ids do not index the
    string list - and a fulfilled order renders three cells where a live one
    renders five, so counting cells walks off by one for the rest of the page.

    `anchor` is a lowercase substring every row's NAME cell must contain, and
    passing it is what makes this reliable on a filtered page. Without it a row
    starts at any cell with letters that is not a known flag - which counted a
    Runics column holding an actual runic name as an extra order (17 rows
    against 14 buttons), and on a page with no matches swept up the footer's
    "Add"/"Purge" labels (2 rows against 0 buttons). Either way the page was
    thrown out and its real orders went unfilled.

    The first numeric cell after a name is Amt To Gather.
    """
    lowered = [(s or "").strip().lower() for s in strings]
    start = 0
    for label in HEADER_LABELS:
        if label in lowered:
            start = max(start, lowered.index(label) + 1)
    end = len(strings)
    for footer in FOOTER_FIRST:
        if footer in lowered:
            end = min(end, lowered.index(footer))

    rows = []
    for value in strings[start:end]:
        text = (value or "").strip()
        low = text.lower()

        if anchor is not None:
            starts_row = anchor in low
        else:
            starts_row = (low not in ROW_FLAGS
                          and not re.match(r"^-?[\d,]+$", text)
                          and bool(re.search(r"[A-Za-z]", text)))

        if starts_row:
            rows.append({"name": re.sub(r"\s+", " ", text), "amount": None})
            continue
        if re.match(r"^-?[\d,]+$", text) and rows and rows[-1]["amount"] is None:
            rows[-1]["amount"] = int(text.replace(",", ""))
    return rows


def parse_header(strings):
    """Counters from the top of the order list.

    "Contents: 8191/100000" is what the book holds; "Displayed: 125" is how many
    rows the current filter matched. Displayed == 0 means the filter term is not
    a name the book uses.
    """
    info = {}
    for line in strings:
        match = re.search(r"Contents:\s*(\d+)\s*/\s*(\d+)", line or "")
        if match:
            info["stored"] = int(match.group(1))
            info["capacity"] = int(match.group(2))
        match = re.search(r"Displayed:\s*(\d+)", line or "")
        if match:
            info["displayed"] = int(match.group(1))
    return info


def page_counter(strings):
    for value in strings:
        match = re.search(r"\((\d+)\s*/\s*(\d+)\)", value or "")
        if match:
            return int(match.group(1)), int(match.group(2))
    return None, None


def open_book():
    book = find_world_item(BOOK_SERIAL, BOOK_ID, BOOK_HUE, "book")
    if book is None:
        log("Resource Order Book not found within %d tiles." % WORLD_RANGE,
            HUE_BAD)
        return False

    # WaitForGump returns True for a gump that is already open, so any leftover
    # window has to go before the one we want is requested.
    Gumps.CloseGump(BOOK_GUMP)
    Gumps.CloseGump(ORDERS_GUMP)
    Misc.Pause(SETTLE_MS)

    Items.UseItem(book)
    Gumps.WaitForGump(BOOK_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    if not has_gump(BOOK_GUMP):
        log("The book's window never opened.", HUE_BAD)
        return False

    Gumps.SendAction(BOOK_GUMP, BOOK_ORDERS_BUTTON)
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    if not has_gump(ORDERS_GUMP):
        log("The order list never opened.", HUE_BAD)
        return False
    return True


def orders_action(button, filter_text=None):
    """Press a button on the order list, restating the filter.

    A plain SendAction submits the gump's text entries EMPTY, which wipes the
    Name filter and silently throws you back to the unfiltered list.
    """
    if filter_text is None:
        Gumps.SendAction(ORDERS_GUMP, button)
    else:
        ids = list(ORDERS_TEXT_IDS)
        values = [filter_text if i == ORDERS_SEARCH_ENTRY else "" for i in ids]
        try:
            Gumps.SendAdvancedAction(ORDERS_GUMP, button, [], ids, values)
        except Exception as err:
            log("SendAdvancedAction failed (%s); the filter will be lost." % err,
                HUE_WARN)
            Gumps.SendAction(ORDERS_GUMP, button)
    Gumps.WaitForGump(ORDERS_GUMP, GUMP_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)
    return has_gump(ORDERS_GUMP)


def colliding_names(resource):
    """Other worked resources whose name CONTAINS this one.

    The book's Name filter is a substring match, so "Copper Ingots" also brings
    back every "Dull Copper Ingots" row. Those are rejected by the exact check,
    but they take up the pages - which is why a collision earns a deeper scan.
    """
    target = (resource or "").strip().lower()
    if not target:
        return []
    return [r["name"] for r in RESOURCES
            if r["name"].strip().lower() != target
            and target in r["name"].strip().lower()]


def rewind_to_first_page(filter_text):
    """Put the filtered list back on page 1. False means it could not be done.

    A NEW FILTER DOES NOT RESET THE PAGE. Confirmed in game 2026-07-30 by
    diag_copper_pages.py: the list was on page 4 of the previous resource's
    result, "Copper Ingots" was submitted, and the list came back showing
    page 4 OF THAT result - the same page 4 the scan had already read, byte for
    byte.

    That is what hid Copper Ingots. work_one_order only calls open_book() when
    the gump is CLOSED, so every resource after the first begins its scan
    wherever the last one stopped, and a resource whose scan found nothing
    leaves the list on the LAST page. Copper has all 26 of its orders on pages
    1-2 of 10, so unless the previous resource happened to stop on page 1 or 2
    it was never seen - and it was reported, correctly by its own lights, as
    having no orders that fit.

    Previous Page is button 4 and is ABSENT on page 1 - a static gumppic sits
    there instead - so it is only ever pressed while the counter says the list
    is past page 1. If it will not converge, the book is reopened, which lands
    on page 1 and needs the filter applied again.
    """
    current, _total = page_counter(gump_lines(ORDERS_GUMP))
    if current is None:
        # No counter to trust. Reading what is there is no worse than the
        # behaviour this replaced.
        return True

    for _ in range(MAX_REWIND_PRESSES):
        if current <= 1:
            return True
        if not orders_action(ORDERS_PREV_BUTTON, filter_text):
            log("The list closed while rewinding to page 1.", HUE_WARN)
            return False
        before = current
        current, _total = page_counter(gump_lines(ORDERS_GUMP))
        if current is None or current >= before:
            break               # not moving - stop pressing and reopen instead

    if current is not None and current <= 1:
        return True

    log("could not rewind to page 1 (stuck on page %s) - reopening the book."
        % current, HUE_WARN)
    if not open_book():
        return False
    return orders_action(ORDERS_FILTER_SUBMIT, filter_text)


def find_first_order(resource, budget):
    """The first order for `resource` that fits `budget`, or None.

    Returns {"button", "name", "amount"} and LEAVES THE GUMP ON THAT PAGE, so
    the caller presses the button straight away with no navigation in between.

    That is deliberate. An earlier version scanned every page, returned a
    shortlist tagged with page numbers, and walked back to each one with
    Previous/Next. The list is live - other players fill these orders while you
    read them - so by the time it navigated back, the page contents could have
    shifted and the remembered button pointed at a different order. Re-opening
    the book to start a second order also cleared the Name filter, which made
    the remembered page numbers meaningless.

    The row's amount is still only a shortlist filter: the real requirement is
    read off the deed once it is out of the book.
    """
    term = resource
    if not orders_action(ORDERS_FILTER_SUBMIT, term):
        log("The list closed while filtering for %r." % term, HUE_BAD)
        return None

    # THE FILTER LEAVES THE LIST ON WHATEVER PAGE IT WAS ALREADY SHOWING, so
    # without this the scan starts wherever the previous resource stopped and
    # walks past everything before it. See rewind_to_first_page.
    if not rewind_to_first_page(term):
        return None

    # Rows are anchored on the filter term, which is what the book matched on,
    # so the count lines up with the buttons even when a page also holds
    # another resource's orders.
    anchor = term.strip().lower()

    # Selection is EXACT, because the filter is a substring match and
    # "Iron Ingots" is inside "Shadow Iron Ingots" - an Iron search was
    # accepting Shadow Iron rows, withdrawing one, and then throwing the deed
    # away at the deed_matches_resource check.
    exact = re.compile(r"^%ss?$" % re.escape(anchor.rstrip("s")), re.I)

    # A name that is not the book's own returns an empty list, which otherwise
    # looks exactly like "this resource has no orders right now". The book calls
    # Shadow Iron "Shadow Ingots"; that mismatch cost a debugging round.
    header = parse_header(gump_lines(ORDERS_GUMP))
    if header.get("displayed") == 0:
        log("%r matched NOTHING in the book. If you expect orders for it, the "
            "book's name is different - run diag_resource_orders.py, which "
            "prints the names it really uses." % term, HUE_WARN)
        return None

    # A name that is a substring of another resource's brings that one back too
    # - "Copper Ingots" also matches every "Dull Copper Ingots" row. Those are
    # rejected below, but they fill the pages, so the search has to look
    # further before it can honestly say "none".
    collisions = colliding_names(resource)
    pages_to_scan = MAX_PAGES_WHEN_DILUTED if collisions else MAX_PAGES_PER_METAL
    if collisions:
        log("%r also matches %s - scanning up to %d pages"
            % (term, ", ".join(collisions), pages_to_scan))

    rejected = 0
    for page in range(1, pages_to_scan + 1):
        strings = gump_lines(ORDERS_GUMP)
        rows = parse_order_rows(strings, anchor)
        buttons = row_buttons(raw_layout(ORDERS_GUMP))

        if len(rows) != len(buttons):
            log("%s page %d: %d rows but %d buttons - skipping this page rather "
                "than risk pressing the wrong one."
                % (resource, page, len(rows), len(buttons)), HUE_BAD)
            log("  rows:    %s" % ", ".join(
                "%s x%s" % (r["name"][:18], r["amount"]) for r in rows[:8]))
            log("  buttons: %s" % ", ".join(str(b) for b in buttons[:8]))
        else:
            for row, button in zip(rows, buttons):
                amount = row["amount"]
                if not amount:
                    continue          # the amt-0 row every page opens with
                if not exact.match(row["name"].strip()):
                    rejected += 1
                    continue          # another resource the filter let in
                if amount > budget or amount > MAX_ORDER_SIZE:
                    continue
                return {"button": button, "name": row["name"],
                        "amount": amount, "term": term}

        current, total = page_counter(strings)
        if total is None or current is None or current >= total:
            break
        if page >= pages_to_scan:
            if total > pages_to_scan:
                log("gave up after %d of %d pages for %r%s"
                    % (pages_to_scan, total, term,
                       " (%d row(s) were another resource)" % rejected
                       if rejected else ""), HUE_WARN)
            break
        if not orders_action(ORDERS_NEXT_BUTTON, term):
            break

    if rejected:
        log("%r: %d row(s) belonged to another resource" % (term, rejected))
    return None


def withdraw(order, filter_text):
    """Press an order's row button and return the deed that appeared.

    The row button is the only candidate for "take this order" and nothing in
    the gump proves it, so the pack is diffed rather than assumed.
    """
    before = pack_serials()
    if not orders_action(order["button"], filter_text):
        log("The list closed when row button %d was pressed." % order["button"],
            HUE_WARN)

    backpack = Player.Backpack
    if backpack is not None:
        Items.WaitForContents(backpack, CONTENTS_TIMEOUT_MS)
    Misc.Pause(SETTLE_MS)

    new = [s for s in pack_serials() if s not in before]
    for serial in new:
        item = Items.FindBySerial(serial)
        if item is not None and is_order_deed(item):
            return item

    if new:
        log("Row button %d put %d new item(s) in the pack but none of them is "
            "an order deed." % (order["button"], len(new)), HUE_BAD)
    else:
        log("Row button %d put nothing in the pack. That button does not "
            "withdraw an order - stopping before anything else is pressed."
            % order["button"], HUE_BAD)
    return None


# ---------------------------------------------------------------------------
# Filling
# ---------------------------------------------------------------------------

def live_stacks(chests, resource):
    """Stacks of `resource` that still exist server-side, largest first.

    `Contains` keeps listing a stack after it has been merged away, and
    Items.Move resolves BOTH ends through Assistant.World by serial - so a
    move aimed at a stale entry fails with "Move: Source Item not found".
    That is exactly what a run of merges produced: the first move worked and
    every one after it fired at a dead serial.

    Items.FindBySerial goes to the world item list rather than the container
    snapshot, so anything it cannot resolve is gone. It also hands back a fresh
    object, which is where the current Amount comes from.
    """
    return only_live(all_resource_stacks(chests).get(resource, []))


def chest_stacks(chests, resource):
    """Stacks of `resource` across all chests, largest first.

    The deed targets a stack where it lies - nothing is carried. Largest first
    so a single target usually covers the whole order instead of walking
    several stacks.
    """
    stacks = live_stacks(chests, resource)
    if stacks:
        return stacks
    # Empty can mean "spent" or "the snapshot is stale". Reopen every chest once
    # before believing it - the difference decides whether the run stops.
    fresh = [refresh_chest(c) for c in as_list(chests)]
    fresh = [c for c in fresh if c is not None]
    if not fresh:
        return []
    return live_stacks(fresh, resource)


def consolidate_stacks(chests, resource):
    """Pack a resource into as few stacks as possible. Returns the new list.

    ONE MOVE PER PASS, re-reading the chest each time. Batching the moves from a
    single snapshot does not work: Items.Move resolves both ends by serial
    through Assistant.World, and the first merge deletes the source server-side,
    so every later move in the batch fires at a dead serial and the client fills
    with "Move: Source Item not found".

    A stack cannot hold more than MAX_STACK either - iron runs to 840,000, which
    is fifteen full stacks and can never be one - so this fills the largest
    stack that still has room and leaves at most one partial behind.
    """
    stacks = chest_stacks(chests, resource)
    if len(stacks) < 2:
        return stacks

    def amount_of(stack):
        return int(getattr(stack, "Amount", 0) or 0)

    started = len(stacks)
    moves = 0
    for _ in range(MAX_MERGE_MOVES):
        stacks = chest_stacks(chests, resource)
        if len(stacks) < 2:
            break

        # Only a move that ENTIRELY absorbs a stack is worth making, because
        # only that reduces the stack count. A partial pour just shuffles
        # ingots between two stacks that both survive - with one full stack and
        # one half stack left, topping up the half from the full leaves two
        # stacks again and the loop never ends.
        #
        # Smallest gives, and the largest target that can swallow it takes.
        target = None
        source = None
        for candidate in reversed(stacks):          # smallest first
            need = amount_of(candidate)
            if need <= 0:
                continue
            for holder in stacks:                   # largest first
                if int(holder.Serial) == int(candidate.Serial):
                    continue
                # Merge only WITHIN one container - moving between chests would
                # relocate stock the user deliberately filed somewhere.
                if int(getattr(holder, "Container", 0) or 0) !=                         int(getattr(candidate, "Container", 0) or 0):
                    continue
                if MAX_STACK - amount_of(holder) >= need:
                    source, target = candidate, holder
                    break
            if target is not None:
                break

        if target is None:
            break        # nothing left that fits anywhere

        move = amount_of(source)

        before = (len(stacks), amount_of(target))
        Items.Move(source, target, move)
        Misc.Pause(MOVE_PAUSE_MS)

        after = chest_stacks(chests, resource)
        grew = False
        for stack in after:
            if int(stack.Serial) == int(target.Serial):
                grew = amount_of(stack) > before[1]
                break
        if len(after) >= before[0] and not grew:
            # Nothing changed - keep going and it loops forever moving a stack
            # onto itself.
            log("%s: merge had no effect, leaving it at %d stack(s)"
                % (resource, len(after)), HUE_WARN)
            break
        moves += 1

    final = chest_stacks(chests, resource)
    log("%s: %d move(s), %d stack(s) -> %d, largest now %d"
        % (resource, moves, started, len(final),
           amount_of(final[0]) if final else 0))
    return final


def organize_chests(chests):
    """Pack every resource into as few stacks as possible. Returns stacks saved.

    Run once at the start. Keeps the chest's 125-item limit clear and leaves the
    largest stack of each resource as large as it can be, which is the one a
    fill then targets.
    """
    rule("organizing the chest")

    # Re-open first. Contains is only populated once the server has sent the
    # container, and organizing used to run against an empty snapshot and
    # report nothing to do while the chest was full.
    refreshed = []
    for chest in as_list(chests):
        fresh = refresh_chest(chest)
        refreshed.append(fresh if fresh is not None else chest)
    chests = refreshed

    stacks_by_resource = all_resource_stacks(chests)
    if not stacks_by_resource:
        log("Found NOTHING workable in any chest. Either they are not open or "
            "nothing in them is listed in RESOURCES.", HUE_BAD)
        for chest in as_list(chests):
            contents = list(getattr(chest, "Contains", None) or [])
            log("chest 0x%X reports %d item(s)"
                % (int(chest.Serial), len(contents)), HUE_WARN)
            for item in contents[:12]:
                log("  id=0x%04X hue=0x%04X x%-6s %s"
                    % (int(item.ItemID), int(item.Hue),
                       getattr(item, "Amount", "?"),
                       strip_amount(getattr(item, "Name", "") or "")), HUE_WARN)
        return 0

    log("found %d resource(s): %s"
        % (len(stacks_by_resource),
           ", ".join("%s x%d" % (res, len(stacks))
                     for res, stacks in sorted(stacks_by_resource.items()))))

    untidy = dict((res, stacks) for res, stacks in stacks_by_resource.items()
                  if len(stacks) > 1)
    if not untidy:
        log("already one stack each - nothing to merge", HUE_GOOD)
        return 0

    merged = 0
    for res in sorted(untidy):
        before = len(untidy[res])
        after = consolidate_stacks(chests, res)
        merged += max(0, before - len(after))
    log("%d stack(s) merged away" % merged, HUE_GOOD)
    return merged


def fill_deed(deed, chests, resource):
    """Fill a deed by targeting the ingots in the chest. True only when done.

    The deed reaches into the chest, so nothing is moved to the backpack and
    back - confirmed in game. The drag fallback below stays as a hedge in case
    targeting is ever refused, and drags straight from the chest too.

    The deed's own tooltip decides whether it worked. Nothing is spent on faith:
    if the count does not move, the script stops and says so.
    """
    fields, filled, needed = read_deed(deed)
    if needed is None:
        log("Deed 0x%X has no 'N / M <resource> Obtained' - cannot tell when it "
            "is done." % deed.Serial, HUE_BAD)
        return False
    if not deed_matches_resource(fields, resource):
        log("Refusing to fill a %r order with %r."
            % (fields.get("resource"), resource), HUE_BAD)
        return False

    serial = int(deed.Serial)
    on_hand = chest_stacks(chests, resource)
    log("filling %s: %s - %d in %d stack(s), largest %d"
        % (resource, progress_text(filled, needed),
           sum(int(getattr(s, "Amount", 0) or 0) for s in on_hand),
           len(on_hand),
           int(getattr(on_hand[0], "Amount", 0) or 0) if on_hand else 0))

    for attempt in range(MAX_FILL_ATTEMPTS):
        short = needed - filled
        if short <= 0:
            return True

        # Straight at the stack in the chest. Nothing is carried: the deed
        # reaches into the container, so the whole move-to-pack-and-back round
        # trip that used to sit here is gone, along with its drag pauses.
        stacks = chest_stacks(chests, resource)
        if not stacks:
            log("No %s left in the chests." % resource, HUE_BAD)
            return False

        # If the biggest stack cannot cover what is still short, merge them.
        # Filling from scraps otherwise burns one attempt per stack, and can
        # run out of attempts with plenty of the metal still in the chest.
        biggest = int(getattr(stacks[0], "Amount", 0) or 0)
        if CONSOLIDATE_STACKS and len(stacks) > 1 and biggest < short:
            total = sum(int(getattr(s, "Amount", 0) or 0) for s in stacks)
            log("%s: biggest stack %d < %d needed, across %d stacks (%d total) "
                "- merging" % (resource, biggest, short, len(stacks), total))
            stacks = consolidate_stacks(chests, resource)
            if not stacks:
                log("No %s left after merging." % resource, HUE_BAD)
                return False

        item = Items.FindBySerial(serial)
        if item is None:
            log("The deed left the pack before it could be filled.", HUE_WARN)
            return False

        Journal.Clear()
        before = filled

        if use_and_target(item, stacks[0].Serial, "fill the order"):
            filled, needed, item, tooltip = reread_deed(serial)

        if item is None:
            # A completed order can be consumed outright. It advanced, so this
            # is success, not a failure to read it.
            log("the deed left the pack after filling - order complete",
                HUE_GOOD)
            return True

        if needed is None:
            # It is still here but no longer reads as an order in progress.
            # Dump the tooltip: that IS the completed-deed format, and it is
            # worth capturing rather than guessing at.
            log("deed 0x%X no longer reads as in-progress. Tooltip now:"
                % serial, HUE_WARN)
            for line in tooltip:
                log("  | %s" % spaced(line))
            return True

        if filled == before:
            # Targeting did not move it; try dragging the ingots onto the deed.
            log("targeting did not register, trying the drag method", HUE_WARN)
            Items.Move(stacks[0], item, min(needed - filled,
                                            int(stacks[0].Amount)))
            Misc.Pause(MOVE_PAUSE_MS)
            filled, needed, item, tooltip = reread_deed(serial)
            if item is None:
                log("the deed left the pack after the drag - order complete",
                    HUE_GOOD)
                return True
            if needed is None:
                log("deed 0x%X stopped reading as in-progress after the drag."
                    % serial, HUE_WARN)
                for line in tooltip:
                    log("  | %s" % spaced(line))
                return True

        if filled == before:
            log("Deed 0x%X did not advance past %s after attempt %d. Neither "
                "targeting nor dragging fills it - stopping."
                % (serial, progress_text(filled, needed), attempt + 1), HUE_BAD)
            return False

        log("  %s" % progress_text(filled, needed))

    if filled is not None and needed is not None and filled >= needed:
        return True
    log("Deed 0x%X still at %s after %d attempts - stopping."
        % (serial, progress_text(filled, needed), MAX_FILL_ATTEMPTS), HUE_BAD)
    return False




# ---------------------------------------------------------------------------
# Account runebook. Duplicated from harvest_runner.py per the one-file rule.
# ---------------------------------------------------------------------------

def openAR():
    if has_gump(AR_GUMPID):
        Misc.Pause(250)
        return True
    chat_say(AR_COMMAND)
    ret = Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
    Misc.Pause(250)
    return bool(ret) or has_gump(AR_GUMPID)


def getARButtons():
    if not openAR():
        return []
    out = []
    for el in layout_elements(raw_layout(AR_GUMPID)):
        if el["kind"] == "button" and el["nums"]:
            out.append(el["nums"][-1])
    return out


def ar_page_info():
    for line in reversed(list(gump_lines(AR_GUMPID) or [])):
        found = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", line or "", re.I)
        if found:
            return int(found.group(1)), int(found.group(2))
    return (1, 1)


def parse_ar_page():
    """Folders and runes on the current page.

    Entries are matched by their own "N. Name" pattern and zipped with the
    page's sorted entry buttons - counting lines does not survive the headers
    and coordinate lines mixed in among them.
    """
    if not openAR():
        return {}, {}
    buttons = getARButtons()
    entry_buttons = sorted(b for b in buttons
                           if AR_ENTRY_BUTTON_MIN <= b <= AR_ENTRY_BUTTON_MAX
                           and b not in AR_CONTROL_BUTTONS)
    entries = []
    for line in gump_lines(AR_GUMPID) or []:
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
            destinations[button] = {"name": entry["label"]}
        else:
            folders[button] = entry["label"]
    return folders, destinations


def ar_page_step(button):
    if button not in getARButtons():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
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
    """An exact name beats a substring, and the whole book is searched first."""
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
            Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
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
    Gumps.WaitForGump(AR_GUMPID, GUMP_TIMEOUT_MS)
    Misc.Pause(250)
    return True


def ensure_mana():
    if Player.Mana >= MIN_MANA_TO_TRAVEL:
        return True
    log("Mana %d - meditating." % Player.Mana, HUE_WARN)
    deadline = time.time() + MEDITATE_TIMEOUT_S
    while time.time() < deadline and Player.Mana < MIN_MANA_TO_TRAVEL:
        Player.UseSkill("Meditation")
        Misc.Pause(3000)
    return Player.Mana >= MIN_MANA_TO_TRAVEL


def travel_to(folder_path, point):
    if not point:
        return True, "no destination configured"

    # BEFORE the recall, and before this function's own Journal.Clear() below,
    # which would otherwise throw an unseen save warning away. Every window is
    # closed here: recalling with them open is what left them stacked up, and
    # the runebook gump has to be the one this answers.
    checkpoint(why="before recalling")

    if not ensure_mana():
        return False, "not enough mana to recall"

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

    Journal.Clear()
    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(RECALL_SETTLE_MS)
    if any(Journal.Search(m) for m in MSG_NO_MANA):
        return False, "the recall was refused for mana"
    return True, name


# ---------------------------------------------------------------------------
# The hand-in
# ---------------------------------------------------------------------------

def context_labels(item):
    """The item's context menu as a list of labels, or []."""
    try:
        entries = Misc.WaitForContext(item, CONTEXT_TIMEOUT_MS, False)
    except Exception as err:
        log("context menu failed: %s" % err, HUE_WARN)
        return []
    out = []
    for entry in list(entries or []):
        text = str(getattr(entry, "Entry", entry) or "").strip()
        if text:
            out.append(text)
    return out


def pick_context(labels, wanted):
    """Choose a menu label. Exact match first, guarded substring second.

    An exact hit is always honoured - it was configured deliberately. A
    substring fallback exists because shards rename entries, but it refuses
    anything matching CONTEXT_NEVER: these menus put things that spend or
    destroy stock beside the entry you actually want.

    Returns the REAL label, never the search string - ContextReply has to be
    given what the menu says.
    """
    lowered = [(l, l.strip().lower()) for l in labels]

    for want in wanted:
        target = want.strip().lower()
        for real, low in lowered:
            if low == target:
                return real

    for want in wanted:
        target = want.strip().lower()
        for real, low in lowered:
            if target in low and not any(bad in low for bad in CONTEXT_NEVER):
                log("no exact %r - falling back to %r" % (want, real), HUE_WARN)
                return real
    return None


def refill_runecraft():
    """Single-click the Runecrafting Storage and answer "Refill from stock"."""
    if not RUNECRAFT_ENABLED:
        return False

    rule("runecrafting storage")

    item = Items.FindBySerial(RUNECRAFT_SERIAL) if RUNECRAFT_SERIAL else None
    if item is None:
        # Carried inside a bag in the pack, so a graphic search of the backpack
        # is the fallback when the serial has changed.
        backpack = Player.Backpack
        found = []
        if backpack is not None:
            try:
                found = list(Items.FindAllByID(RUNECRAFT_ID, -1,
                                               int(backpack.Serial), -1,
                                               False) or [])
            except Exception:
                found = []
        if not found:
            log("Runecrafting Storage not found (serial 0x%X, id 0x%04X). "
                "Nothing was clicked." % (RUNECRAFT_SERIAL, RUNECRAFT_ID),
                HUE_WARN)
            return False
        item = found[0]

    return use_context_item(item, RUNECRAFT_CONTEXT, "Runecrafting Storage")


def find_trash_bag():
    """The trash bag in the pack - serial first, then graphic + hue."""
    if TRASH_BAG_SERIAL:
        bag = Items.FindBySerial(TRASH_BAG_SERIAL)
        if bag is not None:
            return bag
        log("trash bag serial 0x%X did not resolve, falling back to id/hue."
            % TRASH_BAG_SERIAL, HUE_WARN)
    for item in pack_items(TRASH_BAG_ID):
        if int(item.ItemID) != TRASH_BAG_ID:
            continue
        if TRASH_BAG_HUE != -1 and int(item.Hue) != TRASH_BAG_HUE:
            continue
        return item
    return None


def trash_junk():
    """Move the configured junk out of the pack and into the trash bag.

    Only graphics in TRASH_ITEM_IDS are touched - the bag deletes its contents
    after 30 seconds, so this is an allowlist and never a "move everything that
    is not wanted" sweep.

    Matched by graphic because every reward forge is a new item with a new
    serial. Each move is verified: an item that did not actually change
    container stops the loop rather than being counted.
    """
    if not TRASH_ENABLED or not TRASH_ITEM_IDS:
        return 0

    bag = find_trash_bag()
    if bag is None:
        log("Trash bag not found (serial 0x%X, id 0x%04X) - nothing binned."
            % (TRASH_BAG_SERIAL, TRASH_BAG_ID), HUE_WARN)
        return 0
    bag_serial = int(bag.Serial)

    binned = 0
    for _ in range(TRASH_MAX_PER_LAP):
        junk = None
        for item in pack_items():
            if int(item.Serial) == bag_serial:
                continue                       # never bin the bag itself
            if int(item.ItemID) not in TRASH_ITEM_IDS:
                continue
            if int(getattr(item, "Container", 0) or 0) == bag_serial:
                continue                       # already inside it
            junk = item
            break
        if junk is None:
            break

        serial = int(junk.Serial)
        name = strip_amount(getattr(junk, "Name", "") or "") or "0x%04X" % junk.ItemID
        Items.Move(junk, bag, -1)
        Misc.Pause(MOVE_PAUSE_MS)

        moved = Items.FindBySerial(serial)
        still_out = (moved is not None and
                     int(getattr(moved, "Container", 0) or 0) != bag_serial)
        if still_out:
            log("  %s would not go into the trash bag - stopping." % name,
                HUE_WARN)
            break
        binned += 1
        log("  binned %s (0x%X)" % (name, serial), HUE_GOOD)

    if binned:
        log("%d item(s) sent to the trash bag" % binned, HUE_GOOD)
    return binned


def use_context_item(item, wanted, label):
    """Single-click an item and answer one entry from its context menu."""
    Items.SingleClick(item)
    Misc.Pause(SETTLE_MS)

    labels = context_labels(item)
    if not labels:
        log("%s showed no context menu." % label, HUE_WARN)
        return False
    log("  menu: %s" % " | ".join(labels))

    choice = pick_context(labels, wanted)
    if choice is None:
        log("None of %s is on %s's menu - nothing selected."
            % (wanted, label), HUE_WARN)
        return False

    log("  selecting %r" % choice, HUE_GOOD)
    Misc.ContextReply(item, choice)
    Misc.Pause(SETTLE_MS)
    return True


def use_context_mobile(mob, wanted, label):
    """Single-click an NPC and answer one entry from its context menu.

    The mobile twin of use_context_item, and it goes through the same
    pick_context - exact label first, then a substring that refuses anything on
    CONTEXT_NEVER. A Resource Gatherer's menu sits next to entries that spend
    gold, so the guarded path matters as much here as on a vendor.
    """
    try:
        Mobiles.SingleClick(mob)
    except Exception as err:
        log("could not click %s: %s" % (label, err), HUE_WARN)
        return False
    Misc.Pause(SETTLE_MS)

    labels = context_labels(mob)
    if not labels:
        log("%s showed no context menu." % label, HUE_WARN)
        return False
    log("  menu: %s" % " | ".join(labels))

    choice = pick_context(labels, wanted)
    if choice is None:
        log("None of %s is on %s's menu - nothing selected."
            % (wanted, label), HUE_WARN)
        return False

    log("  selecting %r" % choice, HUE_GOOD)
    Misc.ContextReply(mob, choice)      # the real label, not the search string
    Misc.Pause(SETTLE_MS)
    return True


def find_order_bag():
    """The bag new orders are parked in, by serial then by graphic and hue."""
    if ORDER_BAG_SERIAL:
        bag = Items.FindBySerial(ORDER_BAG_SERIAL)
        if bag is not None:
            return bag
        log("order bag serial 0x%X did not resolve - trying id/hue."
            % ORDER_BAG_SERIAL, HUE_WARN)
    backpack = Player.Backpack
    for item in list(getattr(backpack, "Contains", None) or []):
        try:
            if int(item.ItemID) != ORDER_BAG_ID:
                continue
            if ORDER_BAG_HUE >= 0 and int(item.Hue) != ORDER_BAG_HUE:
                continue
        except Exception:
            continue
        return item
    return None


def request_new_order(npc):
    """Ask for a replacement order. The new deed, or None.

    Which deed is new is decided by DIFFING THE PACK, never by assuming the
    menu worked: the entry can be answered and produce nothing at all, and a
    deed that is not really there would then be "stashed" into thin air.
    """
    before = pack_serials()
    if not use_context_mobile(npc, NEW_ORDER_CONTEXT, "the Resource Gatherer"):
        return None

    backpack = Player.Backpack
    if backpack is not None:
        try:
            Items.WaitForContents(backpack, CONTENTS_TIMEOUT_MS)
        except Exception:
            pass
    Misc.Pause(NEW_ORDER_SETTLE_MS)

    for serial in [s for s in pack_serials() if s not in before]:
        item = Items.FindBySerial(serial)
        if item is not None and is_order_deed(item):
            return item
    return None


def stash_order(deed, bag):
    """Move a new order into the order bag. True only if it really moved."""
    if bag is None:
        return False
    serial = int(deed.Serial)
    bag_serial = int(bag.Serial)
    Items.Move(deed, bag, -1)
    Misc.Pause(MOVE_PAUSE_MS)

    moved = Items.FindBySerial(serial)
    if moved is None:
        return False
    if int(getattr(moved, "Container", 0) or 0) != bag_serial:
        log("  new order 0x%X would not go into the order bag - it is loose "
            "in your pack." % serial, HUE_WARN)
        return False
    return True


def bag_deeds(bag):
    """Order deeds sitting inside the order bag."""
    if bag is None:
        return []
    fresh = Items.FindBySerial(int(bag.Serial)) or bag
    return [i for i in list(getattr(fresh, "Contains", None) or [])
            if is_order_deed(i)]


def deposit_new_orders():
    """Open the book at the start and press "Fill from backpack".

    Called once the run is back at Start Fill, so the orders collected on the
    trip go into the book before the lap's filling begins.

    Whether "from backpack" reaches INTO a bag is not assumed. The button is
    pressed, the bag is re-counted, and only if deeds are still sitting in it
    are they tipped out into the top level of the pack and the button pressed
    again. That way the common case costs nothing and the other case still
    works.
    """
    if not NEW_ORDER_ENABLED:
        return 0

    bag = find_order_bag()
    held = bag_deeds(bag)
    loose = [d for d in pack_deeds() if not deed_is_complete(d)]
    if not held and not loose:
        return 0

    rule("depositing %d new order(s)" % (len(held) + len(loose)))

    book = find_world_item(BOOK_SERIAL, BOOK_ID, BOOK_HUE, "book")
    if book is None:
        log("Resource Order Book not found - the new orders stay in the bag.",
            HUE_WARN)
        return 0

    def press_fill(book_item):
        # WaitForGump returns True for a gump that is already open, so any
        # leftover window has to go before this one is asked for.
        Gumps.CloseGump(BOOK_GUMP)
        Gumps.CloseGump(ORDERS_GUMP)
        Misc.Pause(SETTLE_MS)
        Items.UseItem(book_item)
        Gumps.WaitForGump(BOOK_GUMP, GUMP_TIMEOUT_MS)
        Misc.Pause(SETTLE_MS)
        if not has_gump(BOOK_GUMP):
            log("The book's window never opened.", HUE_BAD)
            return False
        Gumps.SendAction(BOOK_GUMP, BOOK_FILL_BUTTON)
        Misc.Pause(SETTLE_MS)
        return True

    if not press_fill(book):
        return 0

    remaining = bag_deeds(find_order_bag())
    if remaining:
        log("%d order(s) are still in the bag - 'Fill from backpack' does not "
            "reach inside it. Tipping them out and pressing it again."
            % len(remaining), HUE_WARN)
        backpack = Player.Backpack
        for deed in remaining:
            Items.Move(deed, backpack, -1)
            Misc.Pause(MOVE_PAUSE_MS)
        press_fill(book)
        remaining = bag_deeds(find_order_bag())

    left = len(remaining) + len([d for d in pack_deeds()
                                 if not deed_is_complete(d)])
    deposited = (len(held) + len(loose)) - left
    if deposited > 0:
        log("%d new order(s) deposited into the book" % deposited, HUE_GOOD)
    if left:
        log("%d order(s) could not be deposited and are still held." % left,
            HUE_WARN)
    Gumps.CloseGump(BOOK_GUMP)
    return deposited


def visit_station(station):
    """Recall to a deposit stop and empty into it. True if the entry was sent."""
    if not station.get("enabled", True):
        return False

    label = station.get("label", "station")
    rule(label)

    ok, detail = travel_to(station.get("folder", []), station.get("point", ""))
    if not ok:
        log("Could not reach %s: %s" % (label, detail), HUE_BAD)
        return False
    log("recalled to %s" % detail, HUE_GOOD)
    Misc.Pause(SETTLE_MS)

    item = find_world_item(station.get("serial", 0), station["id"],
                           station.get("hue", -1), label)
    if item is None:
        log("%s not found within %d tiles - nothing deposited."
            % (label, WORLD_RANGE), HUE_WARN)
        return False

    sent = use_context_item(item, station.get("context", []), label)

    # The deposit stop leaves its own window open. One per stop, every lap,
    # is most of what was piling up.
    tidy_gumps(why="after %s" % label)
    return sent


def find_gatherer():
    """The Resource Gatherer, by serial first then by name.

    This shard puts the title in the NAME - "Davin the Resource Gatherer" - and
    the tooltip was empty on inspection, so the name is what gets matched. NPC
    serials change when the shard respawns them, hence the fallback.
    """
    if HANDIN_NPC_SERIAL:
        mob = Mobiles.FindBySerial(HANDIN_NPC_SERIAL)
        if mob is not None and Player.DistanceTo(mob) <= HANDIN_NPC_RANGE:
            return mob

    scan = Mobiles.Filter()
    scan.Enabled = True
    scan.RangeMax = HANDIN_NPC_RANGE        # never leave this unset
    candidates = list(Mobiles.ApplyFilter(scan) or [])

    for mob in sorted(candidates, key=lambda m: Player.DistanceTo(m)):
        name = (mob.Name or "").lower()
        if any(word in name for word in HANDIN_NPC_WORDS):
            return mob

    log("No NPC matching %s within %d tiles. Saw:"
        % (HANDIN_NPC_WORDS, HANDIN_NPC_RANGE), HUE_BAD)
    for mob in candidates[:12]:
        log("  %-28s 0x%X %d tiles"
            % ((mob.Name or "?")[:28], mob.Serial, Player.DistanceTo(mob)))
    return None


def give_deed(npc, deed):
    """Drag one deed onto the NPC. True only if it actually left the pack."""
    serial = int(deed.Serial)
    item = Items.FindBySerial(serial)
    if item is None:
        return False
    Items.Move(item, npc, 1)
    Misc.Pause(MOVE_PAUSE_MS)
    if Items.FindBySerial(serial) is None:
        log("  handed in 0x%X" % serial, HUE_GOOD)
        return True
    log("  0x%X is still in the pack - the drag was refused." % serial,
        HUE_WARN)
    return False


def collect_replacement(npc, order_bag, collected):
    """Take the free order a hand-in just unlocked, and park it in the bag.

    `collected` is a one-element list used as a counter, so the cap is shared
    across the main pass and the sweep that follows it.

    Module level rather than nested inside hand_in: a closure reads its
    enclosing scope, and the guard test in this suite - written after an
    UnboundLocalError reached a live run - cannot tell that apart from a name
    nothing ever set.
    """
    if not NEW_ORDER_ENABLED:
        return False
    if collected[0] >= NEW_ORDER_MAX_PER_TRIP:
        log("  NEW_ORDER_MAX_PER_TRIP (%d) reached - not asking again."
            % NEW_ORDER_MAX_PER_TRIP, HUE_WARN)
        return False

    new_deed = request_new_order(npc)
    if new_deed is None:
        log("  no new order came back from that one.", HUE_WARN)
        return False

    collected[0] += 1
    fields, _filled, needed = read_deed(new_deed)
    log("  collected a new order: %s x%s"
        % (fields.get("resource", "?"), needed if needed else "?"), HUE_GOOD)
    stash_order(new_deed, order_bag)
    return True


def hand_in(deeds):
    """Drag each completed deed onto the Resource Gatherer."""
    if not deeds:
        return 0

    ok, detail = travel_to(HANDIN_FOLDER, HANDIN_POINT)
    if not ok:
        log("Could not reach the hand-in: %s" % detail, HUE_BAD)
        return 0
    log("recalled to %s" % detail, HUE_GOOD)
    Misc.Pause(SETTLE_MS)

    npc = find_gatherer()
    if npc is None:
        log("The deeds are still in your pack - nothing was lost.", HUE_WARN)
        return 0
    log("handing in to %s (0x%X)" % (npc.Name, npc.Serial), HUE_GOOD)

    handed = 0
    given = set()
    collected = [0]
    order_bag = find_order_bag() if NEW_ORDER_ENABLED else None
    if NEW_ORDER_ENABLED and order_bag is None:
        log("Order bag not found (serial 0x%X, id 0x%04X) - new orders will "
            "be left loose in the pack." % (ORDER_BAG_SERIAL, ORDER_BAG_ID),
            HUE_WARN)

    for deed in deeds:
        if give_deed(npc, deed):
            handed += 1
            given.add(int(deed.Serial))
            # Straight away, while the cooldown this hand-in just cleared is
            # the thing being spent.
            collect_replacement(npc, order_bag, collected)

    # SWEEP. Deeds do get missed - a stale pack snapshot, a refused drag - so
    # the pack is re-read and any FULFILLED deed still in it is handed in too.
    # Repeated while it makes progress, because each pass re-reads the pack and
    # a drag that was refused once may go through next time.
    for _pass in range(1, HANDIN_SWEEP_PASSES + 1):
        leftovers = [d for d in pack_deeds()
                     if int(d.Serial) not in given and deed_is_complete(d)]
        if not leftovers:
            break
        log("sweep %d: %d completed deed(s) still in the pack"
            % (_pass, len(leftovers)), HUE_WARN)
        progress = False
        for deed in leftovers:
            if give_deed(npc, deed):
                handed += 1
                given.add(int(deed.Serial))
                progress = True
                collect_replacement(npc, order_bag, collected)
        if not progress:
            log("none of them would go across - leaving them alone.", HUE_WARN)
            break

    if NEW_ORDER_ENABLED:
        log("%d new order(s) collected against %d hand-in(s)"
            % (collected[0], handed),
            HUE_GOOD if collected[0] else HUE_WARN)

    # Anything unfilled stays, and is named so it is not a mystery later.
    # A new order that would not go into the bag shows up here, which is
    # correct - it really is loose in the pack.
    unfilled = [d for d in pack_deeds() if not deed_is_complete(d)]
    if unfilled:
        log("%d unfilled deed(s) left in your pack, NOT handed in:"
            % len(unfilled), HUE_WARN)
        for deed in unfilled:
            fields, filled, needed = read_deed(deed)
            log("  0x%X %s %s" % (deed.Serial, fields.get("resource", "?"),
                                  progress_text(filled, needed)), HUE_WARN)
    return handed


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------

def work_one_order(resource, chests, budget, completed, withdrawn):
    """Take and fill ONE order for `resource`. Returns why it stopped.

        "filled"    an order was completed and is held for the hand-in
        "declined"  a deed came out but was not filled - it is in the pack
        "none"      no order for this resource fits; do not ask again
        "stop"      something is wrong; the caller must end the run

    Pulled out of main so the outer loop can round-robin across resources
    instead of working one to exhaustion and starving the rest.
    """
    if not has_gump(ORDERS_GUMP) and not open_book():
        log("Could not reopen the order list - stopping %s." % resource,
            HUE_WARN)
        return "none"

    # Between orders is a safe point: nothing is half-withdrawn here. The book
    # and the order list stay open - the scan is about to use them.
    wait_out_world_save()

    order = find_first_order(resource, budget.get(resource, 0))
    if order is None:
        return "none"
    term = order["term"]

    log("taking %s x%d (row button %d)"
        % (order["name"], order["amount"], order["button"]))
    deed = withdraw(order, term)
    if deed is None:
        return "stop"               # withdraw() has already said why
    withdrawn[0] += 1

    fields, filled, needed = read_deed(deed)
    if needed is None:
        log("Cannot read deed 0x%X - no 'N / M <resource> Obtained' in its "
            "tooltip. It is in your pack; stopping." % deed.Serial, HUE_BAD)
        return "stop"
    log("deed 0x%X: %s %s at %s gold each"
        % (deed.Serial, progress_text(filled, needed),
           fields.get("resource", "?"), fields.get("gold_each", "?")))

    if not deed_matches_resource(fields, resource):
        # Should not happen once the Name filter is doing its job, but the book
        # mixes granite and ore orders under the same resource names, so this
        # is the last line of defence.
        #
        # The deed is left in the pack rather than returned: the only bulk way
        # back is the book's "Fill from backpack", which would swallow any
        # COMPLETED deeds being carried to the hand-in.
        log("That deed wants %r, not %r. Left in your pack - return it with "
            "the book's 'Fill from backpack' once you are not carrying "
            "completed orders." % (fields.get("resource"), resource), HUE_WARN)
        return "declined"

    short = needed - (filled or 0)
    if short > budget.get(resource, 0):
        log("The deed wants %d but only %d is spendable - it stays in your "
            "pack unfilled." % (short, budget.get(resource, 0)), HUE_WARN)
        return "declined"

    if not fill_deed(deed, chests, resource):
        return "stop"               # fill_deed has already said why

    budget[resource] = budget.get(resource, 0) - short
    # A completed order may be consumed on the spot rather than left to carry,
    # so only keep the ones still in the pack - otherwise the hand-in reports a
    # failure for a deed that was never there to hand in.
    if Items.FindBySerial(int(deed.Serial)) is not None:
        completed.append(deed)
        log("order complete, deed held for hand-in", HUE_GOOD)
    else:
        log("order complete, the deed was consumed on filling - nothing to "
            "hand in for it", HUE_GOOD)
    return "filled"


def validate():
    """Check the config and print what loaded. A silent no-op is undiagnosable
    from in game, so every rejected entry is named."""
    ok = True
    rule("resource order filler %s" % SCRIPT_VERSION)

    if not RESOURCES:
        log("RESOURCES is empty - nothing to do.", HUE_BAD)
        ok = False

    seen = {}
    for entry in RESOURCES:
        for field in ("name", "id", "hue"):
            if field not in entry:
                log("RESOURCES entry %r has no %r - it will be skipped."
                    % (entry.get("name", entry), field), HUE_BAD)
                ok = False
        key = str(entry.get("name", "")).strip().lower()
        if not key:
            log("A RESOURCES entry has a blank name.", HUE_BAD)
            ok = False
        elif key in seen:
            log("RESOURCES lists %r twice - the second is unreachable."
                % entry["name"], HUE_WARN)
        seen[key] = True

    work = worked_resources()
    if not work:
        log("Nothing to work - RESOURCES and WORK_RESOURCES do not overlap.",
            HUE_BAD)
        ok = False

    if MAX_ORDERS_PER_RUN < 1:
        log("MAX_ORDERS_PER_RUN is %d - nothing to do." % MAX_ORDERS_PER_RUN,
            HUE_BAD)
        ok = False

    if not HANDIN_POINT:
        log("HANDIN_POINT is empty - orders will be filled but not handed in.",
            HUE_WARN)

    log("working %d resource(s): %s"
        % (len(work), ", ".join(r["name"] for r in work)))
    zero_keep = [r["name"] for r in RESOURCES if int(r.get("keep",
                 KEEP_PER_TYPE)) == 0]
    log("keep %d of each (except %d spendable to zero), at most %d order(s) "
        "this run, up to %d per order"
        % (KEEP_PER_TYPE, len(zero_keep), MAX_ORDERS_PER_RUN, MAX_ORDER_SIZE))
    if not validate_board_hues():
        ok = False
    log("hand-in: %s > %s, drag to %s"
        % ("/".join(HANDIN_FOLDER) or "(root)", HANDIN_POINT,
           " or ".join(HANDIN_NPC_WORDS)))

    circuit = [START_POINT or "(here)", HANDIN_POINT]
    for station in STATIONS:
        if station.get("enabled", True):
            circuit.append(station.get("point", "?"))
    circuit.append(START_POINT or "(here)")
    log("circuit: %s, up to %d lap(s)" % (" > ".join(circuit), MAX_CYCLES))
    if TRASH_ENABLED:
        log("binning at the start of each lap: %s"
            % ", ".join("0x%04X" % i for i in TRASH_ITEM_IDS))

    for station in STATIONS:
        if not station.get("enabled", True):
            log("station %r is disabled" % station.get("label", "?"), HUE_WARN)
            continue
        if not station.get("point"):
            log("station %r has no rune - it will be skipped."
                % station.get("label", "?"), HUE_BAD)
            ok = False
    return ok


# ---------------------------------------------------------------------------

def rotated(items, offset):
    """`items` rotated so it starts at `offset`."""
    if not items:
        return []
    cut = offset % len(items)
    return list(items[cut:]) + list(items[:cut])


def fill_orders(chests, offset=0):
    """Withdraw and fill what the budget and the cap allow.

    Returns (completed, stop, next_offset). `stop` means something is wrong
    enough that the whole run should end rather than move to the next lap.

    `offset` rotates the resource order, and the returned one resumes after
    whatever this lap got through. WITHOUT IT nothing past position
    MAX_ORDERS_PER_RUN is ever worked: the cap is on withdrawals, the order is
    fixed, so the same leading resources win every lap forever. With 69
    resources and a cap of 15, Copper Ingots at position 16 was never once
    reached - a chest holding 30,654 of them, and orders waiting for them.
    """
    stock = census(chests)
    budget = fill_budget(stock)

    rule("stock")
    for entry_def in worked_resources():
        listed = entry_def["name"]
        entry = stock.get(listed, {"amount": 0, "stacks": []})
        stacks = entry["stacks"]
        biggest = max([int(getattr(s, "Amount", 0) or 0) for s in stacks] or [0])
        if not entry["amount"] and budget.get(listed, 0) <= 0:
            continue          # nothing of it anywhere; keep the report readable
        log("  %-28s have %-8d keep %-5d spend %-8d in %d stack(s), biggest %d"
            % (listed, entry["amount"], keep_for(listed),
               budget.get(listed, 0), len(stacks), biggest),
            HUE_GOOD if budget.get(listed, 0) > 0 else HUE_WARN)

    # Boards the runner can SEE but cannot name. Reported here, beside the
    # stock it did recognise, because an unidentified wood looks exactly like
    # an empty chest from every other angle.
    report_unknown_boards(chests)

    if not any(budget.get(r["name"], 0) > 0 for r in worked_resources()):
        log("Nothing above the reserves. Nothing to fill.", HUE_WARN)
        return [], False, offset

    if not open_book():
        return [], True, offset

    completed = []
    withdrawn = [0]        # deeds taken out of the book, filled or not
    exhausted = set()      # resources with nothing left to take
    examined = []          # resources this lap got as far as considering

    order = rotated(worked_resources(), offset)
    if offset:
        log("resuming at %s (offset %d)" % (order[0]["name"], offset))

    # ROUND ROBIN: one order per resource per pass.
    #
    # Working each resource to exhaustion before moving on meant the first few
    # ate the whole lap. With gems listed first and a cap of 15, Iron Ingots
    # sits at position 9 and was never reached - the lap simply ended before its
    # turn, which reads in game as "it skips iron".
    for _round in range(1, MAX_ORDERS_PER_RUN + 1):
        if withdrawn[0] >= MAX_ORDERS_PER_RUN:
            break

        took_any = False
        for entry_def in order:
            resource = entry_def["name"]

            if withdrawn[0] >= MAX_ORDERS_PER_RUN:
                break
            if resource not in examined:
                examined.append(resource)
            if resource in exhausted:
                continue
            if budget.get(resource, 0) <= 0:
                exhausted.add(resource)
                continue

            outcome = work_one_order(resource, chests, budget, completed,
                                     withdrawn)
            if outcome == "stop":
                return completed, True, offset      # the helper has said why
            if outcome == "none":
                exhausted.add(resource)
                continue
            took_any = True

        if not took_any:
            log("nothing left to take from any resource")
            break

    if withdrawn[0] >= MAX_ORDERS_PER_RUN:
        log("stopped at MAX_ORDERS_PER_RUN (%d): %d withdrawn, %d filled"
            % (MAX_ORDERS_PER_RUN, withdrawn[0], len(completed)))

    missed = [r["name"] for r in order[len(examined):]]
    if missed:
        log("%d resource(s) got no turn this lap - the next one starts with "
            "%s" % (len(missed), missed[0]), HUE_WARN)

    return completed, False, offset + len(examined)


def run_lap(lap, offset=0):
    """One circuit: Start Fill -> fill -> RO -> Deposit items -> Deposit PS.

    Returns (handed, stop, next_offset). `handed` of 0 with stop False means
    there was nothing left to fill.
    """
    rule("lap %d of %d" % (lap, MAX_CYCLES))

    # Start every lap on a clean screen and on the far side of any save. Not
    # left to travel_to's checkpoint: that one is skipped when START_POINT is
    # empty, which is exactly the setup that ran unattended for hours.
    checkpoint(why="lap start")

    if START_POINT:
        ok, detail = travel_to(START_FOLDER, START_POINT)
        if not ok:
            log("Could not reach the start: %s" % detail, HUE_BAD)
            return 0, True, offset
        log("recalled to %s" % detail, HUE_GOOD)
        Misc.Pause(SETTLE_MS)

    # Clear last lap's junk out of the pack BEFORE anything is filled, so the
    # rewards from the previous circuit do not sit there taking up space.
    if TRASH_ENABLED:
        rule("trash")
        trash_junk()

    # Put last trip's collected orders into the book before the census, so this
    # lap can fill them rather than carrying them round again.
    deposit_new_orders()

    rule("chests")
    chests = find_chests()
    if not chests:
        log("No chest found within %d tiles of the start." % WORLD_RANGE,
            HUE_BAD)
        return 0, True, offset
    for chest in chests:
        if not open_container(chest, "chest 0x%X" % int(chest.Serial)):
            log("chest 0x%X did not report its contents." % int(chest.Serial),
                HUE_WARN)

    # Tidy first, so the census counts merged stacks rather than the scraps.
    if ORGANIZE_CHEST:
        organize_chests(chests)

    completed, stop, next_offset = fill_orders(chests, offset)

    # The fill phase is finished with the book, the order list and both chest
    # windows whatever happened next - so close them on EVERY exit, not just
    # the one where something was filled. That asymmetry is what left a lap's
    # worth of windows on screen each time a lap filled nothing.
    tidy_gumps(why="fill done")

    if stop:
        return 0, True, next_offset

    rule("%d order(s) to hand in" % len(completed))
    if not completed:
        return 0, False, next_offset    # nothing filled - may end the run

    handed = hand_in(completed)
    log("%d of %d handed in" % (handed, len(completed)),
        HUE_GOOD if handed == len(completed) else HUE_WARN)

    # The storage is carried, so this needs no particular spot.
    refill_runecraft()

    # Then the deposit stops, in the order they are listed.
    for station in STATIONS:
        visit_station(station)

    return handed, False, next_offset


def main():
    if not validate():
        return

    # Start the journal cursor at NOW. Without this the first poll would read
    # the whole existing buffer and a save warning from before the run started
    # would pause it immediately, for a save that finished long ago.
    prime_journal_cursor()
    if WORLD_SAVE_PAUSE:
        log("world-save pause on: %ds from the warning"
            % (WORLD_SAVE_PAUSE_MS / 1000))

    started = time.time()
    total = 0
    laps = 0
    offset = 0
    barren = 0
    resources = max(1, len(worked_resources()))
    # Laps needed to walk the whole table once at MAX_ORDERS_PER_RUN a lap.
    sweep = max(1, (resources + MAX_ORDERS_PER_RUN - 1) // MAX_ORDERS_PER_RUN)

    for lap in range(1, MAX_CYCLES + 1):
        laps = lap
        handed, stop, offset = run_lap(lap, offset)
        total += handed
        if stop:
            log("stopping - see the message above.", HUE_BAD)
            break

        if handed:
            barren = 0
            continue

        # A lap that fills nothing is NOT the end - the rotation may simply have
        # been on a stretch of resources with no orders. Only stop once a full
        # sweep of the table has come back empty.
        barren += 1
        log("lap %d filled nothing (%d in a row, need %d to stop)"
            % (lap, barren, sweep), HUE_WARN)
        if barren >= sweep:
            log("a full pass over every resource filled nothing - done.",
                HUE_GOOD)
            break
    else:
        log("reached MAX_CYCLES (%d)." % MAX_CYCLES, HUE_WARN)

    rule("%d order(s) handed in over %d lap(s) in %.1f min"
         % (total, laps, (time.time() - started) / 60.0))

    if RETURN_POINT:
        ok, detail = travel_to(RETURN_FOLDER, RETURN_POINT)
        log("return trip: %s" % detail, HUE_GOOD if ok else HUE_WARN)


main()
