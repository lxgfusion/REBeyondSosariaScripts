# =============================================================================
# RUNE CRAFT AND STORE -- stock runes for later, apply nothing   [LOCAL FORK]
# =============================================================================
#
# WHAT THIS IS, IN ONE LINE
#
#   A modified version of Omniwrath's "Omni Runecrafting" that only MAKES
#   AND STORES runes. Pick an equipment slot, fill in the properties and the
#   target values you want on that kind of item, and it works out what FIFTY
#   of them would consume, crafts exactly that many runes, and puts them in
#   the Runecrafting Storage key. Nothing is ever applied to anything you own.
#
#   THE FIFTY IS AN ASSUMPTION, not a search of your backpack. You do not
#   need to own the gear - that is the whole point, you are stocking runes
#   for gear you have not got yet. Change the number at
#   ASSUMED_ITEM_COUNT; the cost is exactly linear in it.
#
# WHOSE WORK THIS IS
#
#   Upstream is Omniwrath's Omni Runecrafting:
#
#       github.com/Omniwrath/beyond-sosaria-runecrafting
#
#   This file is taken from OmniRuneCraftFork.py, which carries the local
#   changes to that, so it is a fork of a fork - and all three files share
#   ~11,000 lines of Omniwrath's work. The crafting, the simulation, the
#   gump handling and the storage keys are theirs. What is ours is the
#   make-and-store behaviour, the assumed gear, the Master Key support and
#   the gump-press guard.
#
#   SO DO NOT REPORT ANYTHING HERE TO UPSTREAM. A fault in this file is this
#   fork's until it is shown to be in a part neither fork touched.
#
# LICENCE -- GNU GPL v3, because upstream is
#
#   Omni Runecrafting is released under the GNU General Public License v3.0,
#   and this is a modified version of it, so this file is GPL v3 as well.
#   You may share it and change it; a changed version you hand out must stay
#   under the same licence and go out with its source.
#
#   The licence text is upstream's, at
#   github.com/Omniwrath/beyond-sosaria-runecrafting/blob/main/LICENSE, and
#   the terms are in full at gnu.org/licenses/gpl-3.0.txt. This repository
#   does not carry its own copy - the notice you are reading is the whole of
#   it, which is this project's choice and not a complete GPL section 4/5
#   conveyance.
#
#   MODIFIED, and GPL v3 section 5(a) asks a changed version to say so:
#   changed from Omni Runecrafting by the Razor Enhanced Scripts project,
#   2026-11-07, as described under WHOSE WORK THIS IS above.
#
#   Nothing else in this repository is GPL. The other scripts here are
#   separate works that happen to share a folder, and are their author's.
#
# WHAT THIS ONE DOES
#
#   Pick a slot, pick the stats and the target values, exactly as before. It
#   runs the same simulation to work out how many runes that gear would
#   consume - then CRAFTS THEM AND PUTS THEM IN THE STORAGE KEY, and stops.
#   Nothing is applied to anything.
#
#   The point is a stocked key: "just to get a storage of crafted runes for
#   use on future runs." Come back later with OmniRuneCraftFork.py and the
#   apply run finds the runes already waiting and spends its Perk Deed hour
#   applying them instead of crafting them.
#
# WHAT IT DELIBERATELY DOES NOT DO
#
#   * It never applies a rune, so no item of yours is ever at risk here.
#   * It never uses a Perk Deed, never checks whether the buff is running,
#     and never shows either on the setup screen. The break-chance perk
#     reduces the chance of breaking an ITEM while applying a rune; nothing
#     is applied here, so none of it changes anything this script does.
#     Crafting has never needed it - upstream says so itself where it
#     removed a deed gate from the craft path: it "made a deed a
#     precondition for CRAFTING, which has never needed one".
#   * It never travels to the perk chest, never offers a cursor to target
#     one, and the Master Key codex is off here as it is in the fork.
#
# THE ONE PERK IT STILL READS, AND WHY
#
#   Infinite Backpack Weight. A different perk doing a different job: it is
#   what tells the crafter whether it has to keep the run inside your weight
#   limit, which matters as much here as anywhere. That is the [perks read
#   you will see go past - one round trip, throttled to once every
#   PERKS_RECHECK_INTERVAL_SECONDS (5 minutes), shared by every caller. It
#   is not the deed being checked.
#
# WHY THE PREVIEW STILL TALKS ABOUT BREAKS AND ODDS
#
#   Because that is where the number comes from. How many runes a set of
#   items needs is exactly "how many applications, including the ones lost
#   to breakage" - so the simulation that estimates breaks IS the thing
#   sizing the batch. The odds on that screen describe the future apply run
#   this is stocking for, not anything this script is about to do.
#
# WHAT IT ALREADY HAS IN STOCK IS COUNTED FIRST
#
#   Runes already in the key, and any in the pack, are subtracted before
#   anything is crafted - so running it twice against the same gear does not
#   craft the batch twice. They are COUNTED, not withdrawn: the apply flow
#   pulls them out because a rune must be in the pack to be used, and this
#   one has no reason to take them out only to put them back.
#
# SETUP, RUNES AND KEYS are identical to the fork's: the same two runebook
# runes in one folder ('Home' and 'Scribe'), the same Reagent Keys and
# Runecrafting Storage. Its settings live in RuneCraftAndStore/ beside this
# file, copied from the fork's so nothing had to be set up twice.
#
# KEEPING THREE COPIES IN STEP IS ON US. A fix made in the fork does not
# reach this file by itself. Anything touched in both should say so.
#
# Crafts Rune Crafting runes from Rough Stone and applies them to your gear until each stat
# reaches the value you asked for. It pulls reagents and stone from your storage key, buys Rune
# Chisels when it runs low, and keeps the break-chance perk up as it goes. Nothing is crafted or
# spent until you have seen the preview screen with the material cost and your odds.
#
# WHAT YOU NEED
#   * This file in your RazorEnhanced Scripts folder. That is the whole thing -- no other files.
#     Rename it if you like; it creates its own data folder named to match.
#   * Two items in your backpack:
#       - 'Reagent Keys'         every craft pulls its reagents from this key
#       - 'Runecrafting Storage' holds your Rough Stone, blank runes, finished runes, chisels
#   * 300 Inscription. This is a hard stop, not a warning.
#   * The 'Better Rune Crafting' perk. The script keeps it active for you off Perk Deeds, so
#     keep a stock of deeds in the chest beside your 'Home' rune.
#   * 'Infinite Backpack Weight' is optional. Without it a run stays inside your weight limit:
#     it stops crafting, or pulling items from a chest, before the next one would go over.
#   * Two runes in one Account Runebook folder, named exactly:
#       - 'Home'    must sit beside your Perk Deed chest
#       - 'Scribe'  must sit beside a scribe who sells Rune Chisels
#
# FIRST RUN
#   A setup screen opens and checks every requirement above. Hover anything red for what it
#   wants; green means ready.
#     1. Open your runebook and press Read, to capture which folder your runes are in.
#     2. Press Target on the Perk Deed Chest row, then click the chest. It is found again by its name,
#        so if other chests near 'Home' share that name (every house chest starts out as
#        "a glimmering chest of belongings"), rename yours first -- it never opens a chest it can't
#        tell apart.
#     3. Set Rune Chisel Target -- the charge balance to keep stocked. 10,000 is a fine default.
#   Your answers are saved, so this is once only.
#
# USING IT
#   Apply Runes -> pick an equipment slot -> type a target value for each rune you want ->
#   Calculate to see the cost and odds -> commit from the preview.
#
#   WORK FEWER ITEMS: when fewer items can still give you a finished one, the preview offers buttons
#   such as "Work 3 -- 95%": they start the run on only that many items, the ones likeliest to
#   finish, with the odds that at least one comes out with every stat.
#
#   TEMPLATES: on that screen, type a name under Templates and press Save Template -- the runes you
#   set and their values are kept. Every slot that has all of those runes shows the template as a
#   button there; press it to fill the screen with it (nothing is spent until you Calculate). The X
#   removes one. Up to 10.
#
#   If the slot you pick is empty in your backpack, it offers a cursor to target a chest holding
#   those items instead. Keep that chest near your 'Home' rune: it works a few at a time out of
#   it and travels back for more as items break.
#
# UPDATES
#   Settings -> Check for updates (off by default). On: each time you start the script it looks for
#   a newer version and, when there is one, shows what changed: Update, Not now (asked again in 6
#   hours) or Skip this version. An update is taken only when its signature checks -- proof the
#   author made it -- and the old version is kept in the data folder. With RazorEnhanced's Auto
#   Script Reload ticked (Scripting tab) the new version starts by itself; without it, press Refresh,
#   then Play.
#
# WORTH KNOWING
#   * Spellbooks are deliberately excluded. This script will not rune a spellbook, so it cannot
#     break yours.
#   * It does NOT check up front that you have enough gold or reagents. If a craft fails because
#     you are short of either, the script simply stops.
#
# =============================================================================
# Everything below this line is development history and implementation notes.
# =============================================================================
#
# Omni_RuneCrafting.py
#
# Crafts property-enhancement runes (SDI, Self Repair, Luck, Mage Armor/Wep, ...) at a Scribe's
# Inscription Menu, AND applies them to equipment up to a target value per stat. Both halves ship
# in this one file -- the "phase 2 is a separate, not-yet-built script" this header used to claim
# was built and is now the Apply Runes half of the mode picker.
#
# Everything below was proven live via ScratchTest.py across many rounds before being folded in
# here -- see the project's own memory notes for the full discovery history. Key confirmed facts,
# summarized:
#   - The Scribe rune is named "Scribe" and lives in whichever Account Runebook folder the player
#     captured at setup -- NOT a fixed folder. (This header said "Chores" for a long time; that
#     was one player's layout, and the same wrong claim was removed from a gump on 2026-09-16.)
#     The NPC is matched on its vendor TITLE, "Scribe", read from its property list -- not on a
#     name and not on a serial, so any scribe works for any player. It matched the single NPC
#     "Sahale" by name until 2026-09-16, which could only ever have worked on one shard layout.
#   - Rune Chisel (ItemID 4327) is bought from her via Vendor.Buy(vendorSerial, itemName, amount,
#     maxPrice) -- a REAL RazorEnhanced API confirmed via .NET reflection (Vendor.GetType().
#     GetMethods()), not a guess. It's a reusable tool, not consumed per craft -- bought once, kept.
#   - Double-clicking the chisel opens a real (non-cliloc-obscured) "INSCRIPTION MENU" gump. Unlike
#     the vendor Buy gump, Gumps.CurrentGump()/LastGump* are UNRELIABLE for finding it (confirmed
#     live, twice, on two different gumps this project touched) -- this always uses
#     Gumps.AllGumpIDs() + a content match instead. See find_inscription_menu_id()'s own docstring.
#   - Crafting is ONE STEP as of the 2026-09-08 shard patch: the Enhancement category applies a
#     property directly, consuming one Rough Stone (or a legacy Blank Rune, used first) plus a
#     reagent, producing a real item named "<Syllable> Rune" (e.g. "Corp Rune" for SDI) -- the
#     wiki's own syllable code, not the full property name. Property button ids are resolved
#     DYNAMICALLY from the gump's own raw layout every time (never hardcoded), since nothing
#     here has confirmed they're stable across a server restart/patch.
#     WAS A TWO-STEP PROCESS until 2026-09-11: a Miscellaneous-category Blank Rune craft came
#     first. The shard removed that recipe ("The separate Blank Rune step is gone. The Blank
#     Rune recipe has been removed from the Rune Chisel"), so Phase 1 was deleted -- it could
#     only ever fail to resolve its button and abort the run before crafting anything.
#   - SAFETY CHECK, per the user: every single craft (blank rune AND every property application)
#     verifies the newly-appeared backpack item's name actually STARTS WITH what was expected, and
#     HALTS THE ENTIRE BATCH immediately on any mismatch (or on no new item appearing at all) --
#     proven live on both the success path and the failure path, including proving a batch of 2
#     correctly stops after item 1's failure without ever attempting item 2.
#   - Reagents come from a carried "Reagent Keys" key (same shared STORAGE_GUMP_ID and withdrawal
#     mechanism already proven in Omni_ResourceOrders.py for its own storage keys) -- reused
#     directly, no new discovery needed there.

import re
import heapq          # simulate_stat_trial()'s min-heap -- see its own comment for why
import datetime
import math
import time
try:
    from Omni_DiskLog import disk_log   # every line to OmniData/Omni_ScriptLog_<day>.txt (2026-09-24)
except ImportError:
    # THE SHARED COPY SHIPS AS ONE FILE (2026-09-26): another player has no disk-log module -- the journal still
    # gets every line, the disk copy is simply skipped.
    def disk_log(text):
        return False
import os
import random

SCRIPT_TITLE = "Omni Runecrafting"
SCRIPT_VERSION = "1.0.0"        # upstream's version. LEFT ALONE: version_tuple() parses it,
                                # and the fork has nothing to say about where
                                # upstream has got to.
# FORK. Bumped by the fork, read by nothing but the log line at startup, so it
# can never be confused with upstream's own version.
FORK_VERSION = "craftandstore-1"

# EVERY WINDOW IS WAITED FOR LIKE THE PREFETCH (owner, 2026-10-02: "It sounds like all gumps should work like prefetch").
# Gumps.WaitForGump() is never used for a server window: RazorEnhanced 1.0.0.14 polls ONE shared "newest window" slot
# that every window event from anyone rewrites (another window arriving, any close, any script's press), so a second
# event in the same instant as ours and it sits out its whole timeout with the window open (the Tamer measured 122 of
# 125 "did not open" that way). Gumps.HasGump(id) reads RazorEnhanced's record of OPEN windows. The same function as
# Omni_Engine.py's; this script ships on its own, so it carries its own copy.
GUMP_PRESENT_POLL_MS = 50


def wait_for_gump_present(gump_id, timeout_ms, is_ours=None):
    """Milliseconds until `gump_id` is on screen -- and, with is_ours, until is_ours() says the window is ours -- or
    None within timeout_ms. 0 is a window already up: callers test `is None`."""
    _t0 = time.time()
    while True:
        try:
            if Gumps.HasGump(gump_id) and (is_ours is None or is_ours()):
                return int((time.time() - _t0) * 1000)
        except Exception:
            pass
        if (time.time() - _t0) * 1000 >= timeout_ms:
            return None
        Misc.Pause(GUMP_PRESENT_POLL_MS)


# BY THE CLOCK, NEVER THE COUNT (2026-10-10, carried from Omni_Engine.py). RazorEnhanced keeps 100 journal lines, OLDEST
# first, so an entry COUNT taken before an action stops growing once the buffer is full, and every reply lands outside a
# slice taken from it. A reply is read by RazorEnhanced's own clock instead: its newest stamp taken BEFORE the action
# (never time.time() -- RazorEnhanced stamps in local time), then the lines stamped after it. A Journal.Clear() between
# the two changes nothing.
def newest_journal_timestamp():
    """The newest stamp in RazorEnhanced's journal, or 0.0 when it is empty."""
    try:
        stamps = [getattr(e, "Timestamp", None) for e in (Journal.GetJournalEntry(None) or [])]
        stamps = [s for s in stamps if s is not None]
        return max(stamps) if stamps else 0.0
    except Exception:
        return 0.0


def journal_lines_after(stamp):
    """The journal lines stamped after `stamp` (newest_journal_timestamp() taken before the action), oldest first."""
    out = []
    try:
        for entry in (Journal.GetJournalEntry(stamp) or []):
            if (getattr(entry, "Timestamp", 0.0) or 0.0) > stamp:
                out.append(entry)
    except Exception:
        pass
    return out


def action_refused_since(stamp):
    """True when the shard said "You must wait to perform another action." since `stamp` -- its item timer."""
    return any("to perform another action" in (getattr(e, "Text", "") or "").lower() for e in journal_lines_after(stamp))


# THE MOVE IS SENT AGAIN (2026-10-10, the Tamer's breeding, item_move_sent()): a move the shard refused for its item
# timer goes again at once, and one that never landed goes again after its wait -- MOVE_TRIES at most. Before, a refused
# chest pull skipped the item for the pass, and a refused Perk Deed withdrawal read as "none in storage".
MOVE_TRIES = 3


def item_move_sent(serial, dest_serial, wait_ms, amount=1, poll_ms=100):
    """One Items.Move of `serial` into `dest_serial` (amount 1 by default), sent again as above. True once it is there."""
    for _try in range(MOVE_TRIES):
        stamp = newest_journal_timestamp()
        Items.Move(serial, dest_serial, amount)
        waited = 0
        while waited < wait_ms:
            it = Items.FindBySerial(serial)
            if it is not None and it.Container == dest_serial:
                return True
            if action_refused_since(stamp):
                break
            Misc.Pause(poll_ms)
            waited += poll_ms
    it = Items.FindBySerial(serial)
    return it is not None and it.Container == dest_serial


# A COPY THAT HOLDS (2026-10-17, the shared panner's lesson -- a player's run died at the banker copying the pack while
# an item moved): RazorEnhanced's Contains is the client's own live list, and walking it while an item arrives or leaves
# -- a crafted rune, a chest pull, an item that breaks -- can throw and end the run. Every container read here takes a
# copy through container_items(), tried again a moment later; [] only when every try fails.
CONTAINER_READ_TRIES = 5


def container_items(container):
    """A container's items, copied -- see A COPY THAT HOLDS."""
    if container is None:
        return []
    for _try in range(CONTAINER_READ_TRIES):
        try:
            return list(getattr(container, "Contains", None) or [])
        except Exception:
            Misc.Pause(50)
    return []


# FOLDED IN 2026-09-16, per the user: "any reason we can't fold runeslotlogic into the script
# for the standalone ship?" There wasn't: 32 top-level names with zero collisions here, no
# imports of its own, and this script was its only consumer. One file to hand someone now.
#
# VERBATIM from RuneSlotLogic.py (only its `# -*- coding` line dropped, inert mid-file). Kept
# byte-faithful so Tests/test_RuneSlotLogic.py can slice this block back out and exec it --
# which means those 229 assertions now test THE SHIPPED CODE, not a copy that could drift.
# Re-syncing from an updated RuneSlotLogic.py is a straight replace between these markers.
#
# COMMENTS ELSEWHERE IN THIS FILE STILL SAY "RuneSlotLogic.classify_item()" and the like. They
# are provenance, left deliberately: they mean the function of that name in THIS block. Only
# real attribute accesses were rewritten to bare names; no comment was touched.
#
# ABOVE EVERY USE, deliberately -- this project has lost scripts on load to a module-level
# table referencing something defined below it. Nothing below depends on anything above it
# here, so straight after the imports is the earliest safe point.
# ----------------------------------------------------------------------------
# ===== BEGIN FOLDED RuneSlotLogic =====
"""WHICH RUNES CAN GO ON WHICH SLOT -- pure logic, no RazorEnhanced imports.

Built 2026-09-11 for the new two-page Rune Crafting UI, per the user: "show the user a list of item
slots organized similar to how they are shown on the advanced paperdoll, and then when they select
that item slot, we will show them a list of runes available specifically for that item slot."

SOURCE OF THE TARGET DATA: the shard wiki's own rune table (beyondsosaria.com/wiki/rune-crafting),
which lists a "Valid Targets" column per rune. That column is the ONLY thing taken from the wiki
here. Deliberately NOT taken from it:
  * the crafting-menu button text. Omni_RuneCrafting.py's PROPERTY_CATALOG learned those
    LIVE after the wiki wording proved wrong at least four separate times -- "Bonus Dex" not
    "Dexterity Bonus", "Cold Resist" not "Cold Resist Bonus", and so on. This module never touches
    line_text; it keys on the SYLLABLE, which is stable and is what the crafted item is named after.
  * reagents and skill ranges -- already in PROPERTY_CATALOG, verified against real crafts.

WHY SYLLABLE IS THE KEY. The crafted item is "<Syllable> Rune" (Corp Rune, Zu Rune), the wiki table
is indexed by syllable, and PROPERTY_CATALOG already carries a "syllable" field on every entry. So
this table joins to the existing one without duplicating anything that was hard to learn.

THE HAND-SLOT PROBLEM, which is genuinely unresolved and is NOT papered over here. Every other
paperdoll slot implies its item category, but a hand holds a weapon, a shield, a spellbook or a
quiver -- four different rune sets, 20 weapon-only runes among them. Omni_RuneCrafting.py
currently has NO weapon slot at all (its own note: "'RightHand' is deliberately EXCLUDED: it's the
one layer that did NOT round-trip cleanly"), so this is the blocking question for the whole feature.
slot_categories() returns the UNION for a hand slot and hand_slot_is_ambiguous() says so out loud,
so a caller can show every possibility and let the ITEM decide -- rather than this module inventing
a rule nobody has verified.
"""

# Target categories exactly as the wiki names them.
WEAPON = "Weapon"
RANGED = "Ranged weapon"      # bala/vel only; a strict subset of WEAPON
ARMOR = "Armor"
SHIELD = "Shield"
CLOTHING = "Clothing"
QUIVER = "Quiver"
SPELLBOOK = "Spellbook"
JEWELRY = "Jewelry"

# The two groupings the wiki table actually uses, spelled out once so the table below stays short
# and so a mistake in one rune cannot silently differ from the same grouping on another.
UNIVERSAL = (WEAPON, ARMOR, SHIELD, CLOTHING, QUIVER, SPELLBOOK, JEWELRY)
GEAR = (WEAPON, ARMOR, SHIELD, CLOTHING)          # no quiver/spellbook/jewelry
RESIST = (WEAPON, ARMOR, SHIELD, JEWELRY)         # the five resist runes' shape
WEAPON_ONLY = (WEAPON,)
RANGED_ONLY = (RANGED,)

# syllable -> valid targets. All 50, transcribed from the wiki's "Valid Targets" column.
RUNE_TARGETS = {
    "aglo": (WEAPON, ARMOR, SHIELD, CLOTHING, JEWELRY),   # Durability Bonus
    "ahm": (WEAPON, ARMOR, SHIELD, CLOTHING, JEWELRY),    # Spell Channeling
    "an": WEAPON_ONLY,                                    # Hit Dispel
    "arma": WEAPON_ONLY,                                  # Use Best Weapon Skill
    "bal": WEAPON_ONLY,                                   # Hit Stamina Leech
    "bala": RANGED_ONLY,                                  # Balanced
    "beh": UNIVERSAL,                                     # Stamina Regen
    "bet": WEAPON_ONLY,                                   # Hit Magic Arrow
    # cah IS NO LONGER OFFERED ON WEAPONS (2026-09-16), per the user: "just hide mage weapon
    # when working on weapons." Reason, from the message before it: "I have a feeling this
    # isn't working as intended, and I don't want us to build a lot of logic around it. I've
    # posted in the bug section on Discord... Theoretically infinite magery skill seems like
    # that is probably not intended." Two real tooltips showed "Mage Weapon --75 Skill" --
    # a +75 Magery bonus -- and "Mage Weapon -10 Skill", with no visible cap between them.
    #
    # SPELLED OUT RATHER THAN EDITING GEAR. GEAR is (WEAPON, ARMOR, SHIELD, CLOTHING) and is
    # shared with "lum" (Lower Stat Req) and "rel" (Self Repair); changing it would pull those
    # two off weapons as well. The grouping is still correct for them -- see this table's own
    # note about a shared grouping not differing silently between runes.
    #
    # ARMOUR IS UNAFFECTED, which is the whole point of doing it here instead of disabling the
    # catalog row: ONE row ("Mage Armor", line_text "Mage Armor/Wep") covers both names, so
    # switching the row off would have taken Mage Armor with it. SHIELD is kept deliberately --
    # a shield is armour, and the Shield cell narrows to SHIELD, not WEAPON.
    #
    # TO RESTORE: put this line back to `"cah": GEAR,` and re-sync RuneSlotLogic.py.
    # RESTORED TO GEAR (2026-09-19), per the user: "let's fix and enable the logic around Mage Weapon."
    # The 09-16 hide ("just hide mage weapon when working on weapons") was about not building logic on a
    # property we did not understand; the catalog now carries the weapon form as its own numeric dump row.
    "cah": GEAR,                                          # Mage Armor (armour) / Mage Weapon (weapons)
    "char": WEAPON_ONLY,                                  # Hit Lower Defense
    "corp": UNIVERSAL,                                    # Spell Damage Increase
    "del": RESIST,                                        # Cold Resist
    "des": WEAPON_ONLY,                                   # Hit Lower Attack
    "dium": RESIST,                                       # Physical Resist
    "ex": UNIVERSAL,                                      # Stamina Increase
    "flam": RESIST,                                       # Fire Resist
    "flamus": WEAPON_ONLY,                                # Hit Fire Area
    "frio": WEAPON_ONLY,                                  # Hit Cold Area
    "furis": WEAPON_ONLY,                                 # Hit Energy Area
    "gra": WEAPON_ONLY,                                   # Hit Life Leech
    "grav": WEAPON_ONLY,                                  # Hit Physical Area
    "hur": RESIST,                                        # Energy Resist
    "in": UNIVERSAL,                                      # Luck
    "jux": WEAPON_ONLY,                                   # Hit Harm
    "kal": WEAPON_ONLY,                                   # Hit Fireball
    "lor": UNIVERSAL,                                     # Night Sight
    "lum": GEAR,                                          # Lower Stat Req
    "malas": WEAPON_ONLY,                                 # Hit Poison Area
    "mani": UNIVERSAL,                                    # Hit Point Increase
    "mu": UNIVERSAL,                                      # Hit Point Regen
    "nox": RESIST,                                        # Poison Resist
    "om": UNIVERSAL,                                      # Mana Regen
    "ort": UNIVERSAL,                                     # Mana Increase
    "pas": UNIVERSAL,                                     # Lower Mana Cost
    "por": UNIVERSAL,                                     # Dexterity Bonus
    "quas": WEAPON_ONLY,                                  # Hit Mana Leech
    "ra": UNIVERSAL,                                      # Defense Chance Increase
    "rel": GEAR,                                          # Self Repair
    "sanct": UNIVERSAL,                                   # Reflect Physical
    "sar": UNIVERSAL,                                     # Weapon Damage
    "summ": UNIVERSAL,                                    # Faster Cast Recovery
    "tym": UNIVERSAL,                                     # Swing Speed Increase
    "um": UNIVERSAL,                                      # Faster Casting
    "uus": UNIVERSAL,                                     # Hit Chance Increase
    "vas": UNIVERSAL,                                     # Strength Bonus
    "vel": RANGED_ONLY,                                   # Velocity
    "wis": UNIVERSAL,                                     # Intelligence Bonus
    "xen": WEAPON_ONLY,                                   # Hit Lightning
    "ylem": UNIVERSAL,                                    # Lower Reagent Cost
    "zu": UNIVERSAL,                                      # Enhance Potions
}

# Paperdoll slot (SLOT_CATALOG's own "layer" value) -> the item categories that slot can hold.
#
# ARMOR *AND* CLOTHING TOGETHER on the body slots is deliberate and not hedging: the same layer
# genuinely holds either (a leather tunic is Armor, a fancy shirt is Clothing), and the rune sets
# differ -- the five resist runes take Armor but not Clothing. A caller that knows the real item
# should narrow with categories_for_item(); a caller drawing a menu shows the union.
SLOT_CATEGORIES = {
    "Head":         (ARMOR, CLOTHING),
    "Neck":         (ARMOR, CLOTHING, JEWELRY),   # JEWELRY ADDED 2026-09-11, per the user
        # ("don't forget necklace"), who had raised the same gap once before -- a necklace sits on
        # this layer and was being offered the Armor/Clothing set instead of Jewelry's. Per the
        # user, jewellery crafting is already proven in practice: "let's assume those work. i've
        # crafted some, mostly using SDI." The OFFERED union is unchanged by this (Jewelry is a
        # subset of Armor+Clothing), so this corrects the model without changing today's menu.
    "Arms":         (ARMOR, CLOTHING),
    "Gloves":       (ARMOR, CLOTHING),
    "InnerTorso":   (ARMOR, CLOTHING),
    "MiddleTorso":  (ARMOR, CLOTHING),
    "Pants":        (ARMOR, CLOTHING),
    "Shoes":        (ARMOR, CLOTHING),
    "Waist":        (ARMOR, CLOTHING),
    "Shirt":        (CLOTHING,),
    # "Cloak" USED TO BE DECLARED HERE TOO as (CLOTHING,) and was DEAD (removed 2026-09-14): the
    # real entry is (CLOTHING, QUIVER) further down with the other ambiguous layers, and a dict
    # literal keeps the LAST binding. Anyone editing the copy up here would have seen no effect.
    "OuterTorso":   (CLOTHING,),   # Robe
    "OuterLegs":    (CLOTHING,),   # Skirt
    "Ring":         (JEWELRY,),
    "Bracelet":     (JEWELRY,),
    "Earrings":     (JEWELRY,),
    # MEASURED LIVE 2026-09-11 (ScratchTest_Equipment.txt / ScratchTest_FirstValid.txt), replacing
    # the guess that a hand holds all four categories. The real layout is NOT hand-shaped at all:
    #   * A WEAPON reports Layer='FirstValid', NOT 'RightHand'. The equipped butcher knife proved
    #     it. Omni_RuneCrafting.py excludes 'RightHand' believing its layer "did not round-trip
    #     cleanly" from one spellbook sample -- the truth is simpler: nothing lives on RightHand.
    #   * SPELLBOOKS also report 'FirstValid' -- all seven in the pack did. So FirstValid is a
    #     catch-all covering two categories with very different rune sets (16 weapon-only runes vs
    #     none), and must be split by inspecting the item. classify_item() does that.
    #   * A SHIELD reports 'LeftHand' and round-trips cleanly.
    #   * A QUIVER reports 'Cloak' -- the same layer as an actual cloak. Another split.
    "FirstValid":   (WEAPON, SPELLBOOK),
    # CORRECTED 2026-09-11 from (SHIELD,) -- that came from a single equipped sample. A full pack
    # dump found a shield AND a two-handed weapon ('Apocalyptic crescent blade', ItemID 0x26C1) both
    # reporting 'LeftHand', while ANOTHER two-handed weapon (0x13B2) reported 'FirstValid'. So it is
    # not about handedness and not about shields: which of the two layers a weapon lands on varies
    # per item, and both layers are mixed.
    "LeftHand":     (SHIELD, WEAPON),
    "Cloak":        (CLOTHING, QUIVER),
}

# Layers that genuinely hold more than one category, so the ITEM decides, not the slot.
AMBIGUOUS_LAYERS = ("FirstValid", "Cloak")

# NARROWER KINDS COME IN TWO FLAVOURS, and this names the difference (2026-09-14). classify_item()
# returns the broad category WITH the narrow one for both -- (WEAPON, RANGED) for a bow,
# (CLOTHING, QUIVER) for a quiver -- per the user's own subset rule: "all quivers count as cloaks
# but not all cloaks are quivers. same for ranged weapons and other weapons."
#
# But the two behave in OPPOSITE directions on the rune table:
#
#   RANGED *ADDS*    -- a bow takes every weapon rune PLUS bala/vel. Union is correct: 50.
#   QUIVER *REMOVES* -- a quiver takes 22 of clothing's 27; aglo/ahm/cah/lum/rel are refused.
#                       Union is WRONG: it offers five runes the item cannot take.
#
# Measured and confirmed by the user 2026-09-11: "there are some 'clothing' options that do not
# work for quiver." Listing the restrictive ones here lets runes_for_categories(exact=True) narrow
# for a REAL item while leaving the empty-slot union alone -- see that function.
RESTRICTIVE_CATEGORIES = (QUIVER,)

# Property-line markers, all verified against real items on 2026-09-11. Matched case-insensitively
# as substrings of a property line. Deliberately NOT name or ItemID matching: that needs a lookup
# table per item and breaks on every new artifact.
WEAPON_MARKERS = ("weapon damage", "weapon speed", "one-handed weapon", "two-handed weapon")
DURABILITY_MARKER = "durability"   # What actually separates a packed SHIELD from a fishing pole
                                   # on the shared LeftHand layer (2026-09-11). MEASURED on three
                                   # real items:
                                   #   Dreaded heater shield     durability 255 / 255
                                   #   Wall of Hungry Mouths     durability 255 / 255   (a shield
                                   #                             with no "shield" in its name)
                                   #   Ugly Stik GX2 (pole)      no durability line at all
                                   # A name test was tried first, per the user, and the user then
                                   # found the counterexample themselves: "Doh. I found a shield
                                   # without the word shield in it."
                                   #
                                   # KEEPS THE PACKED-SHIELD CASE INTACT, which is why this works
                                   # where narrowing by name did not: test_PACKED_shield_still_
                                   # classifies_without_a_parry_line's own sample is
                                   # ["physical resist 14%", "durability 252 / 255"] -- it HAS
                                   # durability, so it still classifies as SHIELD.
SPELLBOOK_COUNT_WORDS = ("spell", "spells")  # A spellbook always carries a bare "<int> Spells" line
                                    # -- MEASURED 2026-09-11 from the user's own Item Inspector
                                    # captures: Hallowed 34, Blood Stained 64, Book Of Bushido 6,
                                    # and Fallen Mystic's ZERO. The zero case is the whole point:
                                    # any test that required a positive count would miss it, and it
                                    # is still very much a spellbook.
SHIELD_MARKERS = ("last parry chance",)
CLOTH_MAX_STRENGTH = 10   # Per the user (2026-09-11): "Cloth items have a strength requirement of
                          # 10." Measured on four cloth items (bandana, bear mask, cloak, shirt),
                          # all exactly 10, against armour at 20 (leather cap) and 60 (chainmail
                          # coif). Used ONLY together with DURABILITY_MARKER -- see
                          # classify_item()'s armour/clothing branch for why agreement is required.
STRENGTH_REQUIREMENT_WORDS = ("strength", "requirement")
QUIVER_MARKERS = ("ammo:", "lower ammo cost")
RANGED_SKILLS = ("archery", "throwing")   # "skill required: swordsmanship" was the melee sample


def hand_slot_is_ambiguous(layer):
    """True for a layer whose rune set cannot be decided from the layer alone -- the caller must
    look at the item. Exists so a UI can SAY so rather than showing a union as if it were a fact."""
    return layer in AMBIGUOUS_LAYERS


def classify_item(property_lines, layer=None):
    """Decide an item's rune categories from its PROPERTY LINES, the way the UI will.

    Returns a tuple of categories, empty if nothing matched. Verified 2026-09-11 against a real
    butcher knife (WEAPON), bronze shield (SHIELD), Quiver of Infinity (QUIVER), fur cape
    (CLOTHING) and seven spellbooks (SPELLBOOK) -- no false positives among them.

    THE SPELLBOOK RULE IS A FALL-THROUGH ON PURPOSE. A spellbook carries no marker of its own; what
    identifies it is sitting on FirstValid WITHOUT any weapon marker. All seven sampled also weighed
    0, but weight is not used as the test -- an artifact spellbook with weight would still be a
    spellbook, whereas "on the weapon layer and not a weapon" stays true."""
    low = [str(p).lower() for p in (property_lines or [])]

    def has(markers):
        return any(m in line for line in low for m in markers)

    def is_spellbook():
        """A bare "<int> Spells" property line. Split rather than regex -- this module is
        deliberately dependency-free, and the observed format has exactly two tokens."""
        for line in low:
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1] in SPELLBOOK_COUNT_WORDS:
                return True
        return False

    # SPELLBOOK FIRST (2026-09-11), per the user: "we need to disable spellbooks as a crafting
    # option ... the spells attribute, even at 0, is valid way to identify them." This USED to be a
    # fall-through at the bottom -- "on FirstValid and carrying no weapon marker, therefore a
    # spellbook" -- which is an argument from absence: any spellbook bearing a weapon-ish line would
    # have been read as a weapon and offered up as a craft target. A positive marker checked BEFORE
    # the weapon markers cannot fail that way.
    if is_spellbook():
        return (SPELLBOOK,)

    # SUBSET RULE, per the user (2026-09-11): "all quivers count as cloaks but not all cloaks are
    # quivers. same for ranged weapons and other weapons." So the narrower kind always carries the
    # broader one WITH it, rather than replacing it -- a quiver is (CLOTHING, QUIVER), a bow is
    # (WEAPON, RANGED). Only the narrow-only runes are exclusive.
    #
    # THE PREDICTION THIS COMMENT USED TO MAKE WAS RIGHT, AND IT RESOLVED 2026-09-11. It read:
    # "the wiki's target column lists five runes as Clothing-but-not-Quiver (aglo, ahm, cah, lum,
    # rel) ... If the shard actually refuses any of those five on a quiver, THIS is the assumption
    # that was wrong, not the table." Per the user: "there are some 'clothing' options that do not
    # work for quiver." So the table was right and the subset shortcut was wrong.
    #
    # THIS FUNCTION IS UNCHANGED REGARDLESS, and that is deliberate: a quiver physically IS a cloak,
    # so (CLOTHING, QUIVER) remains the correct CLASSIFICATION. What was wrong was letting that
    # imply a quiver may take every CLOTHING rune. That is a UI/pool question, and it is answered
    # where it belongs -- Omni_RuneCrafting.py's SLOT_CATALOG now has separate Cloak and
    # Quiver cells, the Cloak one carrying "excludes": "Quiver". runes_for_categories() already
    # gave the right answer to each cell (27 and 22); nothing here needed to move.
    if has(SHIELD_MARKERS):
        return (SHIELD,)
    if has(QUIVER_MARKERS):
        return (CLOTHING, QUIVER)
    if has(WEAPON_MARKERS):
        cats = [WEAPON]
        if any("skill required" in line and any(s in line for s in RANGED_SKILLS) for line in low):
            cats.append(RANGED)
        return tuple(cats)
    # LAYER FALL-THROUGHS, in the order the layers are actually ambiguous.
    #
    # "Last Parry Chance" IS NOT PRESENT ON A PACKED SHIELD (measured 2026-09-11): the same bronze
    # shield showed it while equipped and did NOT while sitting in the pack, where its properties
    # stop at durability. Runes are applied to UNEQUIPPED items, so the packed case is the one that
    # matters and the marker test alone would return "neither" for every real candidate. The layer
    # is the reliable signal there.
    if layer == "LeftHand":
        # DURABILITY IS THE POSITIVE EVIDENCE (2026-09-11). This used to return SHIELD for ANY
        # unmarked LeftHand item -- an argument from absence -- and a fishing pole is also LeftHand,
        # also two-handed and also unmarked, so the Shield cell counted it ("shield is counting it",
        # live). A shield is a durable item and every real sample carries the line; the pole carries
        # none. See DURABILITY_MARKER for the three captures and why this preserves the packed-shield
        # behaviour the marker test alone could not provide.
        if any(DURABILITY_MARKER in line for line in low):
            return (SHIELD,)
        return ()                # unmarked AND not durable -> unknown; claim nothing
    if layer == "FirstValid":
        # Kept as a backstop only. is_spellbook() above is now the real test; this catches an item
        # on the weapon layer with neither a weapon marker nor a spell count -- unknown rather than
        # proven, so the conservative answer (treat it as a spellbook, i.e. NOT a craft target) is
        # the safe one given the user's "I never want this to randomly break those".
        return (SPELLBOOK,)
    if layer == "Cloak":
        return (CLOTHING,)       # a cloak, since a quiver would have shown Ammo:

    # ARMOR vs CLOTHING on the body layers (2026-09-11). These nine layers hold either, and the
    # rune sets differ by exactly the five resists, so the UI had to show the union. No armour or
    # clothing MARKER exists in a tooltip -- measured, classify_item() scored ~2/40 on clothing --
    # so this uses two properties that partition the categories without naming them:
    #
    #   DURABILITY   armour degrades, cloth does not. Already this module's discriminator for a
    #                packed shield vs a fishing pole on LeftHand; same marker, second ambiguity.
    #   STRENGTH     cloth sits at CLOTH_MAX_STRENGTH; the armour samples were 20 and 60.
    #
    # CONFIRMED LIVE ON BOTH SIDES by the shard itself, which is stronger than the property
    # samples alone:
    #   CLOTHING  bandana and Plato's eerie bear mask both REFUSED a Cold Resist rune
    #             ("You cannot enhance that.") -- 2026-09-11.
    #   ARMOR     "Tehron's Convincing Leather Leggings" (durable 255/255, Strength Requirement 20)
    #             ACCEPTED one: Cold Resist 10% -> 18%. And it is a RELIC with Self Repair 10, i.e.
    #             a random drop -- the very class the user warned "can clearly break some rules that
    #             we can't with runecrafting" -- and the rule still read it correctly.
    #
    # BOTH MUST AGREE. Each fails differently -- durability on an indestructible armour piece,
    # strength on very light armour that also requires 10 -- and the samples cannot rule either out.
    # Agreement decides; anything else returns () and the caller shows the union, which is exactly
    # the pre-2026-09-11 behaviour. An undecided answer costs five runes of choice; a silently wrong
    # one costs trust. That fallback is also what protects against an odd random drop: a specimen
    # neither rule can read stays undecided instead of being guessed at.
    cats_here = set(SLOT_CATEGORIES.get(layer, ())) if layer else set()
    # ONE CATEGORY ON THE LAYER MEANS NO AMBIGUITY TO RESOLVE (2026-09-16), per the user on a
    # crafted cloth shirt reading "Showing: [all types]": "this should cleanly fall into the
    # cloth category."
    #
    # THE UNAMBIGUOUS LAYERS WERE THE ONLY ONES THAT FAILED. Everything below is gated on the
    # layer holding BOTH Armor and Clothing, so a layer holding just one fell past every return
    # to the bare `return ()` at the bottom -- undecided. Six layers: Shirt, OuterTorso (Robe)
    # and OuterLegs (Skirt) as Clothing; Ring, Bracelet and Earrings as Jewelry. Measured on the
    # user's own shirt (Strength Requirement 10, no durability, Layer=Shirt): classify_item()
    # answered () on layer "Shirt" and ("Clothing",) on layer "InnerTorso" for the SAME
    # properties. Only the layer differed.
    #
    # No evidence is required here and none is consulted: if SLOT_CATEGORIES says the layer can
    # hold only this one kind of item, an item on it is that kind by the table's own definition.
    # Durability and strength exist to separate Armor from Clothing; with one candidate there is
    # nothing to separate.
    #
    # SAFE BY POSITION. Every positive marker test (spellbook, shield, quiver, weapon) and the
    # LeftHand / FirstValid / Cloak special cases are ABOVE this, so a weapon sitting on an odd
    # layer is still identified by its own marker rather than by its layer. Cloak in particular
    # is (CLOTHING, QUIVER) in its live binding -- two categories -- so it never reaches here.
    #
    # WHAT THIS RESTORES BEYOND THE LABEL: vote_winning_category() groups by classification, so
    # while every Ring and Shirt came back undecided, the "100 helmets and accidentally 1
    # bandana" exclusion could not work on those layers at all. It can now.
    if len(cats_here) == 1:
        return tuple(cats_here)
    if ARMOR in cats_here and CLOTHING in cats_here:
        durable = any(DURABILITY_MARKER in line for line in low)
        light = False
        for line in low:
            parts = line.split()
            if all(w in parts for w in STRENGTH_REQUIREMENT_WORDS):
                for tok in parts:
                    if tok.isdigit():
                        light = int(tok) <= CLOTH_MAX_STRENGTH
                        break
                break
        if durable and not light:
            return (ARMOR,)
        # THE CLOTHING HALF NEEDS JEWELRY RULED OUT (2026-09-11). On Neck the same "light and not
        # durable" evidence fits a necklace just as well as a cloth collar, and their rune sets
        # differ -- Jewelry has the five resists, Clothing does not. Nothing measured yet separates
        # them, so where JEWELRY is also possible this stays undecided rather than guessing
        # CLOTHING and silently withholding five runes from a necklace.
        if light and not durable and JEWELRY not in cats_here:
            return (CLOTHING,)
        return ()                # signals disagree, one is missing, or jewellery is still possible
    return ()


def slot_categories(layer):
    """Item categories a paperdoll layer can hold. Empty tuple for an unknown layer -- callers get
    an empty rune list rather than an exception, which is the right failure for a menu."""
    return SLOT_CATEGORIES.get(layer, ())


def runes_for_categories(categories, include_ranged=True, exact=False):
    """Syllables valid on ANY of `categories`, sorted. RANGED is handled as the strict subset it is:
    a bala/vel rune needs a ranged weapon, so it appears only when RANGED is explicitly among the
    categories -- asking for WEAPON alone does NOT offer them, because applying one to a melee
    weapon is exactly the wasted rune this whole screen exists to prevent.

    exact=True (2026-09-14) says "these categories describe ONE REAL ITEM I have inspected", not
    "this slot could hold any of these". Only then do RESTRICTIVE_CATEGORIES bind, intersecting the
    union down to what that item can actually take. Today that is QUIVER alone: a quiver classifies
    (CLOTHING, QUIVER) and the plain union hands back all 27 clothing runes, five of which the shard
    refuses on it.

    WHY IT IS NOT THE DEFAULT. runes_for_slot() asks about an EMPTY slot, where the union is the
    honest answer -- its own contract is to show "every rune that COULD apply once something is in
    there, rather than silently narrowing on a guess". A bare Cloak slot must still read 27.

    THIS IS WHERE classify_item()'s NOTE SAID IT BELONGED. That function deliberately keeps
    returning (CLOTHING, QUIVER) -- "a quiver physically IS a cloak, so that remains the correct
    CLASSIFICATION. What was wrong was letting that imply a quiver may take every CLOTHING rune."
    It parked the fix in Omni_RuneCrafting.py's separate Cloak/Quiver cells; those cells were
    folded back into one on 2026-09-14, so the narrowing lives here now. classify_item() is
    untouched, exactly as that note intended."""
    wanted = set(categories)
    if not include_ranged:
        wanted.discard(RANGED)
    out = []
    for syllable, targets in RUNE_TARGETS.items():
        if wanted.intersection(targets):
            out.append(syllable)
    if exact:
        # Each restrictive category present is a CEILING, not a contributor: keep only syllables
        # that category itself accepts. Written as a loop over RESTRICTIVE_CATEGORIES rather than a
        # QUIVER special-case so a second one costs a tuple entry instead of another branch.
        for narrow in RESTRICTIVE_CATEGORIES:
            if narrow in wanted:
                out = [s for s in out if narrow in RUNE_TARGETS[s]]
    return sorted(out)


def runes_for_slot(layer, include_ranged=True):
    """Syllables that could validly go on something worn in `layer`, sorted.

    For a hand slot this is the UNION across weapon/shield/spellbook/quiver -- see
    hand_slot_is_ambiguous(). For every other slot the answer is exact."""
    cats = list(slot_categories(layer))
    if include_ranged and WEAPON in cats:
        cats.append(RANGED)
    return runes_for_categories(cats, include_ranged=include_ranged)


def categories_for_item(is_weapon=False, is_ranged=False, is_shield=False,
                        is_spellbook=False, is_quiver=False, is_armor=False,
                        is_clothing=False, is_jewelry=False):
    """Narrow a hand (or body) slot down once the real item is known. Takes booleans rather than an
    item object so this module stays importable without RazorEnhanced -- the caller does the
    property reading. Returns a tuple suitable for runes_for_categories()."""
    cats = []
    if is_weapon:
        cats.append(WEAPON)
        if is_ranged:
            cats.append(RANGED)
    if is_shield:
        cats.append(SHIELD)
    if is_spellbook:
        cats.append(SPELLBOOK)
    if is_quiver:
        cats.append(QUIVER)
    if is_armor:
        cats.append(ARMOR)
    if is_clothing:
        cats.append(CLOTHING)
    if is_jewelry:
        cats.append(JEWELRY)
    return tuple(cats)


def missing_from_catalog(catalog_syllables):
    """Syllables the wiki lists that a given PROPERTY_CATALOG does not carry, sorted.

    Omni_RuneCrafting.py's catalog had 38 entries against the wiki's 50 when this was written
    (2026-09-11), so the new UI would silently offer nothing for a dozen runes. This makes that gap
    a number a test can assert on instead of something noticed later in game."""
    return sorted(set(RUNE_TARGETS) - set(s.lower() for s in catalog_syllables))
# ===== END FOLDED RuneSlotLogic =====

# =============================================================================
# CONFIG
# =============================================================================

PERK_TRACKER_SCRIPT_NAME = "PerkTracker.py"  # Launched alongside this script (see
                                                # ensure_perk_tracker_running()) so break-chance
                                                # perk status is visible on screen throughout.

# THE RUNEBOOK DESTINATIONS ARE DEFAULTS, NOT FACTS (2026-09-14). These are one player's AR
# runebook layout; another player's folders and rune names will differ, which is why the first-run
# setup lets them be edited and saves the answer. The constants below remain the DEFAULTS, so an
# existing installation behaves identically until something is changed.
SETUP_HOME_FOLDER_KEY = "home_folder"
SETUP_HOME_POINT_KEY = "home_point"
SETUP_SCRIBE_FOLDER_KEY = "scribe_folder"
SETUP_SCRIBE_POINT_KEY = "scribe_point"


# _folder_list() LIVED HERE and is gone (2026-09-14). Its docstring claimed "one level is all this
# script has ever used" -- the stored runebook scan disproves it: folders nest at least three deep
# ("[Ilshenar > Cities > Ancient Citadel]"). _folder_path_list() replaces it and splits a full path.


# NO DEFAULTS (2026-09-14), per the user: "it should also be failing me on runes in a new version."
#
# These briefly fell back to HOME_FOLDER/HOME_POINT/SCRIBE_* -- one player's runebook layout, handed
# to every other player as though it had been verified. The setup gump colours its rune rows from
# these values, so an unconfigured install showed BOTH rows GREEN and reported nothing to do; the
# failure surfaced later, mid-run, at the travel call. A default that cannot be correct for anyone
# else is not a default, it is a disguise -- the same reason the hardcoded chest serial went.
#
# Unset returns "", so the rows render red and the player fills them in. Nothing downstream needs a
# guard: ar_go_folders([]) iterates nothing, and ar_go_dest("") already refuses on its own
# `if not dest_name` check, so an unconfigured install fails at the travel call rather than
# wandering off to a rune that happens to share a name.
# A STATED CONVENTION, NOT A HIDDEN DEFAULT (2026-09-14). The setup gump's editable rune fields
# were removed at the user's request in favour of instructions, so these names are expected rather
# than configured -- and that is only acceptable because the gump PRINTS them. The distinction is
# the whole reason the previous hardcoded values were torn out: a default nobody is told about is a
# disguise, while a convention shown on screen is the same contract "Reagent Keys" and "Runecrafting
# Storage" already ask the player to match by renaming.
#
# setup_get() is still consulted first, so a Setup.txt written by an earlier build (or edited by
# hand) continues to win. Nothing writes these keys any more.
# THE FOLDER IS READ FROM THE GUMP, NEVER ASSUMED (2026-09-14), per the user: "you can't assume
# chores you need to read the gump for that info." It was briefly hardcoded to "Chores" -- one
# player's structure. runebook_open_folder_name() takes it from the open book instead.
SETUP_RUNE_FOLDER_KEY = "rune_folder"

# THE RUNE NAMES ARE A FORCED CONSTRAINT, per the user: "we gotta force some constraints, this is one
# of them." Exactly the contract REQUIRED_BACKPACK_ITEMS already imposes -- rename to match or they
# are not found. Detecting arbitrary names would cost a whole pick-list screen to save a rename.
SETUP_HOME_RUNE = "Home"         # Must sit beside the Perk Deed chest.
SETUP_SCRIBE_RUNE = "Scribe"     # Must sit beside a Scribe NPC.


def rune_folder_name():
    """The folder setup captured from the player's own runebook, or "" if never run."""
    return setup_get(SETUP_RUNE_FOLDER_KEY, "")


def _folder_path_list(value):
    """A stored folder path -> the LIST ar_go_folders() expects. "" means the top level."""
    value = (value or "").strip()
    if not value:
        return []
    return [part.strip() for part in value.split(AR_FOLDER_PATH_SEP) if part.strip()]


def home_folder():
    return _folder_path_list(rune_folder_name())


def home_point():
    return SETUP_HOME_RUNE


def scribe_folder():
    return _folder_path_list(rune_folder_name())


def scribe_point():
    return SETUP_SCRIBE_RUNE


# EXAMPLE LAYOUT ONLY -- NOT defaults, and deliberately not reachable from the accessors above.
# This is what one working configuration looked like on the machine this script was written on, kept
# so a reader can see the shape a valid answer takes. The code must never fall back to it: see the
# accessors' own comment for why a default that cannot be right for another player is a disguise
# rather than a convenience.
EXAMPLE_SCRIBE_FOLDER = ['Chores']
EXAMPLE_SCRIBE_POINT = 'Scribe'
# EXAMPLE LAYOUT ONLY -- NOT defaults. Same rule as EXAMPLE_SCRIBE_* above: the accessors must
# never fall back to these, because a runebook layout that is correct here cannot be correct for
# another player, and offering it as a default hides an unconfigured install from setup.
# (Originally added 2026-08-27 for withdraw_perk_deed_from_home_chest() -- the same rune this whole
# script family travels to for storage; Omni_Engine.py and Omni_ResourceOrders.py each have
# their own identical pair.)
EXAMPLE_HOME_FOLDER = ['Chores']
EXAMPLE_HOME_POINT = 'HOME'
SCRIBE_TITLE_MATCH = "scribe"  # THE VENDOR'S TITLE, NOT ONE NPC'S NAME (2026-09-16), per the
                                 # user: "should be easy to detect scribe." CONFIRMED live with
                                 # the Enhanced Mobile Inspector on Sahale: Name "Sahale", and an
                                 # Attributes panel holding exactly one entry -- "Scribe". So the
                                 # class of NPC is directly readable from its property list.
                                 #
                                 # WAS "sahale", which was the last thing in this script that
                                 # could not work for another player: their own Scribe rune puts
                                 # them beside whichever scribe is nearest, and matching one
                                 # individual's name would have found no vendor at all.
VENDOR_SEARCH_RANGE = 12

RUNE_CHISEL_NAME = "Rune Chisel"
CHISEL_STORAGE_ROW = "Rune Chisel"   # the row name in the Runecrafting Storage, which happens
                                     # to match the item name exactly.
# ALWAYS 60,000 (2026-09-15), per the user: "There is only 1 withdrawal amount, that works for
# every item, there's no reason to change it, we'll just use 60,000 and put leftovers back in
# if there are any." The gump has ONE Withdrawal Amount field shared by every row, so there is
# nothing to tune per resource -- the server hands over what it has, up to what is asked.
CHISEL_WITHDRAW_CHARGES = 60000
RUNE_WITHDRAW_AMOUNT = 60000   # ALWAYS THE MAX (2026-09-16), per the user: "just always withdraw
                               # 60000 (which equates to max stack or all we have). no reason to
                               # withdraw less." Same number and same trick as the chisel above --
                               # ask for more than can exist and the shard hands back the max stack,
                               # or the whole row when that is smaller.
# THE PULL FITS THE PACK (owner, 2026-10-18: "do the weight cap"). The max above dates from when Infinite Backpack
# Weight was required. Without it a whole row is a whole row of stones -- 4,458 Weapon Damage runes came out for one
# tunic -- so while the weight limit applies, withdraw_runes_from_storage() asks for what the stat needs, no more
# than the pack can carry at RUNE_STONES_EACH; the mid-batch top-up comes back for more if the breaks run long.
RUNE_STONES_EACH = 1           # one rune's weight -- the step craft_n_runes() measures as THE PACK'S OWN WEIGHT

# RESTOCK TARGET (2026-09-15), per the user: "we'll probably default it to 10k, but move it
# some for testing." This is the STORED charge balance we buy up to -- not a purchase count,
# which is unknowable because chisel yield is random (26/35/66 uses measured live). Held in
# Setup so it is per-player and survives a restart, like every other answer this script keeps.
CHISEL_CHARGE_TARGET_DEFAULT = 10000
SETUP_KEY_CHISEL_TARGET = "chisel_charge_target"
# "0" SKIPS THE CALCULATE PREVIEW ENTIRELY (2026-09-17). Absent/anything else means on, so an
# existing Setup.txt written before this setting existed keeps the old behaviour.
SETUP_KEY_CALCULATIONS = "calculations_enabled"
SETUP_KEY_UPDATES = "check_updates"            # THE SIGNED UPDATE: "1" = look for a newer version at each start
SETUP_KEY_SKIP_UPDATE = "skip_update"          # ... a version the player chose to skip
SETUP_KEY_UPDATE_LATER = "update_later"        # ... "<version>|<epoch>": a "Not now" quiet until then
# THE HOOKS (owner, 2026-10-17: "how much of that could we extract out so we're not shipping code the user isn't using,
# and just build that into a separate script of our own that calls it? I'd rather avoid maintaining two versions"). This
# file is the whole runecrafter and sets none of these. A script that imports it -- one engine, never a copy -- may set
# any of them before calling main(); every one is optional, and one that fails is logged and the run carries on.
HOOKS = {
    "item_action": None,      # fn(): right before and right after every item action a craft or a key use makes
    "rune_crafted": None,     # fn(rune, property_def): a craft just made this rune
    "chisel_arrived": None,   # fn(chisel): a Rune Chisel just came to hand for a batch
    "requests_taker": None,   # fn() -> fn(requests, slot_def) or None: when it returns one, Apply Runes hands the
                              #   chosen runes to it instead of applying them, and no chest is offered
    "setup_rows": None,       # fn(rows): add rows to the setup screen (the 7-field row shape setup_item_rows() builds)
    "setup_button": None,     # fn(clicked) -> True when it handled a press on one of its own rows' buttons
}


def call_hook(name, *args):
    """Run HOOKS[name] when a script set it; None when unset or when it failed (logged, never raised)."""
    fn = HOOKS.get(name)
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception as err:
        log("Warning: the {} hook failed ({!r}) -- carrying on without it.".format(name, err), 33)
        return None


YIELD_PAUSE_MS = 1500   # craft_n_runes(should_pause=): the re-check while its caller asks it to wait

# THE SHARD PUBLISHED THIS RATE, it is not a settle pause. Quoted in Omni_Engine.py from
# the patch notes: "Fill from backpack on a storage key (the Refill from stock menu entry, or
# the Fill from backpack button in a key, stash or list window) now works about once per
# second." 1100 is that second plus the same small cushion the Tamer uses, and the same value,
# so the two scripts cannot drift apart on it.
STORAGE_KEY_FILL_INTERVAL_MS = 1100
last_storage_key_fill_time = 0
# THE FILLS TAKE TURNS (2026-10-10). The shard keeps ONE fill cooldown per character, and every script that fills pays
# into it -- the Tamer's Master Keys absorb, the Resource Order filler, this one. Each used to pace only its own fills, so
# a fill from another script could make ours the refused one. Every fill now waits its turn on one shared clock (a
# shared value: when the last fill was sent, by anyone) and stamps it as it sends. Another player's install without the
# other scripts simply finds only its own stamps there.
KEY_FILL_CLOCK_KEY = "Omni_KeyFillAt"

# The absorb's context entry. NAMED BY THE SHARD'S OWN PATCH NOTES (see above), but this script
# has never called it -- so it is matched by LABEL against these candidates and NOT by a
# position index, the same reasoning this project applies to gump button ids. If none match,
# absorb_backpack_into_key() logs every entry it saw rather than guessing.
STORAGE_FILL_CONTEXT_LABELS = ("refill from stock", "fill from backpack")
# THE FILL COOLDOWN IS EVERY SCRIPT'S (2026-10-10, the Resource Order test: "[I153] Master Keys absorb refused TWICE by the
# fill cooldown"). The shard keeps ONE cooldown for every key fill and the Master Keys absorb -- "You must wait 0.1 more
# seconds before you can fill all keys." -- and a fill from another script (the Tamer's absorb, the Resource Order filler)
# counts, which pace_storage_key_fill() cannot see. A refused fill moved nothing yet read as done. Now the reply is read:
# a refusal waits exactly what the shard names and the fill goes once more; a second refusal is reported, never looped.
FILL_THROTTLE_PATTERN = re.compile(r"you must wait\s+([\d.]+)\s+more seconds?\s+before you can fill", re.IGNORECASE)
FILL_THROTTLE_MARGIN_MS = 200       # the shard names one decimal -- WITHDRAW_THROTTLE_MARGIN_MS's reason


def fill_refused_since(stamp):
    """Seconds the shard said to wait before the next fill, since `stamp` -- or None when it refused nothing."""
    for entry in journal_lines_after(stamp):
        m = FILL_THROTTLE_PATTERN.search(getattr(entry, "Text", "") or "")
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return 0.0
    return None
RUNE_CHISEL_MAX_PRICE = 25000  # Safety cap for Vendor.Buy()'s own maxPrice argument -- CONFIRMED
                                 # live the price was 18200 once; padded above that rather than
                                 # using the exact figure, so a small, ordinary price drift doesn't
                                 # block a purchase outright. Vendor.Buy() itself refuses to
                                 # overpay past whatever it's given, so this is a ceiling, not a
                                 # guess at the real price.

BLANK_RUNE_LINE_TEXT = "blank rune"
BLANK_RUNE_EXPECTED_PREFIX = "blank"
MISCELLANEOUS_CATEGORY_BUTTON = 1  # DEAD as of the shard's 2026-09-08 chisel rework -- referenced
                                   # only from comments now (the Blank Rune phase this drove was
                                   # removed when the recipe left the chisel). KEPT for history, but
                                   # note the value now COLLIDES with Enhancement below: a live menu
                                   # dump (2026-09-11) showed the chisel offering exactly two
                                   # categories, "LAST TEN" (button 28) and "Enhancement" (button 1).
                                   # Do not revive this constant on the assumption 1 still means
                                   # Miscellaneous -- it does not.
ENHANCEMENT_CATEGORY_BUTTON = 1    # CORRECTED from 8 (2026-09-11) via a live Inscription Menu dump.
                                   # The old 8 carried "CONFIRMED live, stable across every test this
                                   # session" -- true when written, stale after the shard's 2026-09-08
                                   # chisel rework (same patch that removed the Blank Rune recipe and
                                   # changed the rune graphic). The dump listed only two categories,
                                   # "LAST TEN" (28) and "Enhancement" (1), so nothing sat at 8 at
                                   # all and the crafting flow could never reach the rune list.
                                   # switch_inscription_category_with_retry() validates a button
                                   # exists before SendAction (see its own comment -- a missing
                                   # button disconnects rather than no-ops), so this failed safe as
                                   # "could not resolve button" instead of killing the connection.

ROUGH_STONE_NAME = "rough stone"

# THE TWO ITEMS THIS SCRIPT CANNOT RUN WITHOUT, named rather than serialled. Per the user
# (2026-09-13): "We should not detect based on serial. When shipping for other players, they will
# have different serials." Both previously carried one player's own instance serials; those are
# gone, not kept as defaults, since another player's pack would silently miss
# them. Identity now lives in REQUIRED_BACKPACK_ITEMS (name + ItemID), resolved to a live serial at
# startup by preflight_required_items() and read back through required_item_serial(). Same reasoning
# this file's own header already applies to the Scribe NPC: "matched by name/tooltip here rather than
# a hardcoded serial, since an NPC respawn could change it".
REAGENT_KEYS_NAME = "Reagent Keys"
RUNECRAFTING_STORAGE_NAME = "Runecrafting Storage"
# MASTER KEYS (2026-09-22). A shard item that ABSORBS storage keys: an absorbed key has no item in the backpack
# any more and is opened from the master's gump instead -- one row per key (its text is whatever the player
# named it there), an OPEN button at x=60 beside the row's text, a WITHDRAW-from-master button at x=300 that
# this script never presses. Matched by the master's name + graphic in the backpack and by row TEXT in the
# gump, so it works for any player who uses one. Rough Stone and reagents are still consumed straight out of
# the absorbed keys while crafting (confirmed live); only the opens (chisel withdraw, balance reads) and the
# end-of-run absorb need the master.
MASTER_KEYS_NAME = "Master Keys"
MASTER_KEYS_ITEM_ID = 0x176B              # CONFIRMED via Enhanced Item Inspector (hue 0x0481 -- not matched)
MASTER_KEYS_GUMP_ID = 0xE13358F7          # captured 2026-09-22 20:58:50; title text "Master Keys"
MASTER_KEYS_OPEN_BUTTON_X = 60            # the OPEN column
MASTER_KEYS_ROW_Y_OFFSET = 17             # a row's buttons sit 17 px ABOVE its text (text y=85 / button y=68) --
                                           # measured live 2026-09-22 21:22 (pairing "below" opened the next row)
MASTER_KEYS_ROW_Y_TOL = 4
MASTER_KEYS_ROW_HINTS = {                 # a row is this key's when its text IS the key's name, else when it
    RUNECRAFTING_STORAGE_NAME: ("rune",),   # contains one of these (the owner's rows read "Rune Key" and
    REAGENT_KEYS_NAME: ("reagent",),        # "Reagent Key")
}
# FORK. Nothing added here. The perk codex is reached by its recorded button
# rather than by a row hint - see the FORK block further down for why.
MASTER_KEYS_ROWS_CACHE = {}               # row text (lower) -> OPEN button id, from the last read this run
_master_keys_rows_logged = False
STORAGE_GUMP_ID = 0x6abce12       # Same shared gump as every storage key in this project.
STORAGE_NEXT_PAGE_BUTTON = 101    # Next Page on this shared gump -- the SAME id Omni_Engine.py uses for the
                                  # Peerless storage (PEERLESS_STORAGE_NEXT_PAGE_BUTTON, confirmed via the user's
                                  # own macro recording). Pressed ONLY when the live layout contains it: on the
                                  # real last page the press disconnects the client (confirmed live 2026-08-17).
STORAGE_MAX_PAGES = 5             # Page cap while reading/searching; 2 real pages on 2026-09-19.
KEY_CONTEXT_WAIT_MS = 5000
GUMP_RESPONSE_SETTLE_MS = 500
PRE_WAIT_SETTLE_MS = 250
STOP_LINE_PATTERN = re.compile(r'^(Previous Page|Next Page|\(\d+/\d+\)|Withdrawal Amount:|Add|Maximum Storage:|Fill from backpack)')

# ROW -> BUTTON BY GEOMETRY (2026-09-15). The storage gump states everything needed:
#     {text   75  50 1158   1}          x, y, hue, LINE-LIST INDEX
#     {button 40  47 2472 2473 1 0 1}   x, y, art-up, art-down, type, page, ID
# A row's button sits immediately LEFT of its name label on the same line. Measured live:
# name x=75 with buttons at x=35/40, name x=315 with buttons at x=275 -- and the Add /
# Fill-from-backpack FOOTER buttons at x=305, only 10px left of the x=315 column, which is
# how the gap band below excludes them.
#
# WHY NOT THE OLD ART FILTER: it harvested art 1209/1210 and zipped positionally, which
# dropped the RED Rune Chisel button (art 2472/2473) and counted both footer buttons as
# rows -- 32 rows against 33 buttons, off by one from the first row. The measurement is in
# OmniData/RunecraftingStorage_GumpDump.txt.
STORAGE_TEXT_PATTERN = re.compile(r'\{\s*text\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*\}')
STORAGE_ANY_BUTTON_PATTERN = re.compile(   # button OR buttontileart: x y up down type param ID (2026-09-19)
    r'\{\s*button[a-z]*\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)')
STORAGE_BUTTON_PATTERN = re.compile(
    r'\{\s*button\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)\s*\}')
STORAGE_ROW_NAME_HUE = 1158        # value cells are 1152; title and footer use others.
STORAGE_ROW_BUTTON_Y_TOL = 8       # the red chisel button sits 3px high, the rest 5px low.
STORAGE_ROW_BUTTON_GAP_MIN = 20    # footer buttons are 10px left of a name -- excluded.
STORAGE_ROW_BUTTON_GAP_MAX = 60    # real row buttons measured at 35-40px.
# THE DATA-ONLY LIST, LINED UP WITH THE LAYOUT (2026-10-01) -- see storage_gump_strings().
STORAGE_CROPPED_TEXT_PATTERN = re.compile(r'\{\s*croppedtext\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+(\d+)\s+(\d+)\s*\}')
STORAGE_HTML_PATTERN = re.compile(r'\{\s*htmlgump\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+(\d+)')
STORAGE_TEXTENTRY_PATTERN = re.compile(r'\{\s*textentry(?:limited)?\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)')
STORAGE_ELEMENT_PATTERN = re.compile(r'\{([^}]*)\}')

# WITHDRAWAL RATE LIMIT (2026-09-08). The shard update that morning gave storage withdrawals their
# own cooldown -- "You must wait 0.3 more seconds before you can withdraw items." -- and it is NOT
# in the published changelog. It broke Overlord skull withdrawal outright in Omni_Engine.py,
# where this same fix is deployed and confirmed working; Harvest.py's board dump got it
# too. Reagent Keys go through the identical shared STORAGE_GUMP_ID path, so they are exposed the
# same way.
WITHDRAW_THROTTLE_PATTERN = re.compile(
    r"you must wait\s+([\d.]+)\s+more seconds?\s+before you can withdraw", re.IGNORECASE)
WITHDRAW_THROTTLE_MARGIN_MS = 200  # The server reports one decimal, so the real remaining time can
                                     # round up slightly.
WITHDRAW_MAX_ATTEMPTS = 3          # Attempts INCLUDING the first. Only a throttle rejection
                                     # consumes one; a confirmed withdrawal or a missing row both
                                     # return immediately, so this cannot spin.

# Every property this script currently knows how to craft. EXPANDED (2026-08-27), per the user, to
# every rune on the wiki's full syllable/property table EXCEPT "Weapon Only"/"Ranged Weapon Only"
# ones -- this script has no weapon slot in SLOT_CATALOG at all (see that catalog's own comment),
# so those runes could never actually be applied to anything here; leaving them out isn't loss of
# coverage, it's just not cataloging the unreachable. Sourced from beyondsosaria.com/wiki/rune-
# crafting (re-fetched 2026-08-27), cross-checked against every already-live-confirmed row (SDI,
# Self Repair, Luck, FCR, FC, LRC, LMC, Mana Regen, Mage Armor) for reagent/syllable/amount/gain --
# all 9 matched the wiki exactly, which is why the rest of the table is trusted here too. List order
# is ALPHABETICAL BY LABEL, per the user, with Mage Armor, Night Sight and Spell Channeling
# pinned at the very top.
#
# THIS ORDER NO LONGER DECIDES THE SCREEN (2026-09-16). ask_runes_for_slot() now sorts the rows
# itself -- all is_boolean rows alphabetically, then all numeric rows alphabetically -- because
# pinning here could not keep the checkboxes in column 1 on a slot with many runes (the Weapon
# slot stranded two of five in column 2). The pinning below is kept because it is harmless and
# PROPERTY_CATALOG is iterated elsewhere, but do not add a row here expecting its POSITION to
# place it on the apply screen: change the sort in ask_runes_for_slot() instead.
#
# (historical) SPELL CHANNELING JOINED THEM
# 2026-09-16, per the user: "move spell channeling over with the other mage armor and night
# sight options, just in a row beneath them" -- it became is_boolean earlier the same day, so
# this finishes the grouping this comment already describes. The column split re-derives from
# len(required) in ask_runes_for_slot(), so Lower Mana Cost moves to column 2 on its own.
#
# Every NEW row below is UNCONFIRMED LIVE, same caution this project already learned the hard way
# with FCR/FC/LRC/LMC: this shard's real in-game Enhancement Menu text and post-application tooltip
# wording have repeatedly diverged from the wiki's own naming (e.g. "Cast Recovery" not "Faster
# Cast Recovery"). line_text below is the wiki's own stated name as a best-guess placeholder --
# expect corrections once each is actually seen live, the same way those four were fixed. prop_
# pattern is likewise an EXTRAPOLATED regex (standard UO tooltip phrasing), not live-verified --
# per read_property_value()'s own documented behavior, a wrong guess just silently reads 0 rather
# than erroring, so this is safe to ship unconfirmed and correct later.
#
# reagent_match is a lowercase SUBSTRING checked against the backpack item's own .Name (may not
# match reagent_storage_row's exact wording/punctuation -- confirmed live for Spider's Silk, whose
# storage row has an apostrophe the backpack item's name might not carry).
#
# prop_pattern is a lowercase regex (one capture group, the numeric value) matched against each
# line of Items.GetPropStringList() -- used by read_property_value() to find an item's CURRENT
# value of that property, for the "always apply to whichever eligible item has the lowest value"
# targeting strategy. CONFIRMED live only for SDI so far. Mage Armor alone is left None -- per the
# user's own DIRECT confirmation ("Mage Armor is a single line property... with no values"), real
# evidence it may not be numeric at all, unlike every other row (including Night Sight, which only
# has the wiki's own "+1" listing to go on, same as every other EXTRAPOLATED row -- is_boolean only
# changes the target_stat INPUT UI, it says nothing about whether prop_pattern should be guessed).
# run_slot_application() refuses to run for a property whose pattern is None rather than silently
# guessing.
#
# gain_range is normally (min, max) -- the wiki's own stated per-application random gain range,
# used for the pre-flight application-count ESTIMATE (estimate_applications_needed(), via its mean)
# AND the Monte Carlo preview simulator (simulate_stat_trial(), via a continuous random.uniform()
# draw across that range). A LONGER tuple (3+ elements) instead means an explicit, equally-likely
# DISCRETE outcome set -- both consumers detect this by length and switch behavior: the mean
# becomes sum(gain_range)/len(gain_range) (still correct for either shape) and the simulator draws
# via random.choice() instead of random.uniform(). Luck (2026-08-27, per the user) is the one
# property that actually needs this: its real gain is exactly one of {15, 30, 45}, never anything
# in between, so a plain (15, 45) pair -- while averaging correctly -- silently understated the
# true variance in the simulator and could produce impossible in-between values. See Luck's own
# entry and simulate_stat_trial()'s own comment for the full reasoning.
#
# Filling in gain_range does NOT unblock prop_pattern -- estimate_applications_needed() and
# run_slot_application() are two SEPARATE gates (pre-flight estimate vs. the actual targeting/apply
# logic); a property still can't run for real until prop_pattern is ALSO confirmed live. Mage
# Armor's stays None (see that entry's own comment -- the wiki's "+1-7" is WEAPON ONLY there, and
# armor/shields/clothing get a flag, not a number, so no single range fits both). Hit Point Regen,
# like Mana Regen before it, has the SAME weapon-vs-else split in the wiki ("+1..3 weapon, else
# +1..2") -- since no weapon slot exists here either, it uses the "else" range (1, 2), not the
# wiki's headline weapon number, exactly like Mana Regen's own fix.
PROPERTY_CATALOG = [
    {
        "label": "Mage Armor",  # Shortened from "Mage Armor/Wep" (2026-08-27), per the user, purely
                              # for display -- line_text below is UNCHANGED, since that has to match
                              # the real Inscription Menu's own line text in-game, not this project's
                              # own gump display choice.
        "line_text": "Mage Armor/Wep",
        "syllable": "cah",
        "reagent_storage_row": "Garlic",
        "reagent_match": "garlic",
        "reagent_amount": 3,
        "prop_pattern": r'^\s*mage (?:armor|weapon)(?:\s+-(?:-\d+|0+)\s+skill)?\s*$',
                              # WIDENED 2026-09-16 from r'^\s*mage (armor|weapon)\s*$' -- that
                              # matched ONLY the bare line, so every penalised form read 0 and a
                              # weapon already PAST the finish line read 0 too.
                              #
                              # TWO REAL TOOLTIPS from the user settled the format. The line is
                              # "Mage Weapon -<penalty> Skill" and the PENALTY ITSELF CAN BE
                              # NEGATIVE, which is why one of them shows a doubled dash:
                              #
                              #   "mage weapon"          penalty   0   no change      satisfied
                              #   "mage weapon --75 skill" penalty -75  +75 Magery     satisfied
                              #   "mage weapon -10 skill"  penalty +10  -10 Magery     NOT yet
                              #
                              # Per the user on the first: "that's minus -75 magery skill, which
                              # works exactly like you'd think. It's +75 magery when equipped."
                              # and on the second: "here is one that is just -10".
                              #
                              # The optional tail admits a penalty of zero or less and nothing
                              # else: after the template's own dash, "-\d+" is the doubled dash
                              # (a bonus) and "0+" is an explicit "-0". A positive penalty puts
                              # a non-zero digit there and matches neither, so "still penalised"
                              # keeps reading 0 and keeps being worked on -- unchanged.
                              #
                              # STAYS BOOLEAN ON PURPOSE. read_property_value() returns 1 on a
                              # match for is_boolean and the checkbox sends target_stat=1, so
                              # "satisfied" is exactly the right shape; read_property_lines()
                              # still handles "-29 -> -22" progress detection separately. The
                              # group is non-capturing now because nothing consumes it and an
                              # unused group invites int("armor").
                              # ORIGINAL NOTE: BINARY, per the user 2026-09-11: "we will
                              # treat it as binary for the sake of UI purposes. There's just no world
                              # in which anybody desiring Mage Weapon would accept anything less than
                              # perfect." The checkbox (is_boolean, below) has existed since
                              # 2026-08-27; this is what makes it actually run.
                              # ANCHORED AT BOTH ENDS so the pattern means DONE, not PRESENT:
                              #   absent                  -> 0   not a mage weapon
                              #   "mage weapon -22 skill" -> 0   in progress, keep applying
                              #   "mage weapon"  (bare)   -> 1   zero penalty, finished
                              #   "mage armor"            -> 1   armour form, binary outright
                              # The completed form is the only one with nothing after the words, so
                              # the regex itself encodes the goal. The other booleans are anchored at
                              # the START only (r'^\s*night sight') -- there a trailing value would be
                              # unexpected but harmless, whereas here it is the whole distinction.
                              # MEASURED 2026-09-11: two Cah Runes on a "Knight's War Cleaver" read
                              # "-29" then "-22", so more cah LOWERS the penalty and the line is
                              # expected to lose its number at 0. Armour was confirmed binary by the
                              # user -- it "allows passive and active mana regeneration for things
                              # like plate armor that typically block it."
                              # THE BARE-LINE END STATE IS THE ONE UNVERIFIED LINK: per the user the
                              # line still reads "Mage Weapon" at zero penalty rather than vanishing.
                              # If it vanishes instead, this reads 0 forever and the detect-fail guard
                              # stops the run -- noisy but safe, and the fix is a one-line pattern
                              # change. Worth confirming on the first live run.
        "gain_range": (1, 1),  # A FLAG LIKE NIGHT SIGHT (2026-10-17, owner's test run: "Stopping: no 'Cah Rune'
                           # left and none could be crafted" -- with no gain the estimate said 0 runes, so nothing
                           # was ever crafted for it). It was None while this row also served weapons, where cah
                           # counts the penalty DOWN (29 -> 22, see Mage Weapon); since 2026-09-19 the weapon form
                           # is its own row with its own (1, 7), and this row is armour's yes/no -- one rune that
                           # lands sets it, as Night Sight, Spell Channeling and Use Best Wep's (1, 1) say.
        "category": "required",  # Default category -- see SDI's own comment. Per the user
                              # (2026-08-27): "Mage Armor is a single line property on an item with
                              # no values" -- CONFIRMS the "flag property, not numeric" note above,
                              # directly from the user rather than just the wiki's own ambiguity.
        "is_boolean": True,  # Per the user: the threshold UI for this one should be a checkbox
                              # (0/1), not a numeric target -- see ask_apply_requests_and_slot()'s
                              # own comment for the gump-side handling.
        "only_categories": (ARMOR, SHIELD, CLOTHING),   # the weapon form is its own row below (2026-09-19):
                              # both wear the "cah" rune, so the syllable alone cannot tell them apart.
    },
    {
        "label": "Mage Weapon",   # NEW ROW (2026-09-19), per the user: "Mage Weapon will move to a dump stat".
                              # Same rune and reagents as Mage Armor -- a different item type and a different
                              # meaning: on a weapon the line carries a Magery penalty that cah works off.
        "line_text": "Mage Armor/Wep",   # the Inscription Menu's own text, shared with the armour row
        "syllable": "cah",
        "reagent_storage_row": "Garlic",
        "reagent_match": "garlic",
        "reagent_amount": 3,
        "prop_pattern": r'^\s*mage weapon(?:\s+(--?\d+)\s+skill)?\s*$',
                              # ONE CAPTURE, SIGNED, OPTIONAL -- see parse_mage_weapon_value():
                              #   "mage weapon -10 skill"  -> -10   still a penalty, keep applying
                              #   "mage weapon"            ->   0   penalty reached zero
                              #   "mage weapon --75 skill" -> +75   the doubled dash IS a bonus
                              # Per the user: "it can convert to -- skill, which should be interpreted as
                              # +skill ... which can scale infinitely" -- so there is no finish line here,
                              # which is exactly what a dump stat is for.
        "gain_range": (1, 7),  # MEASURED 2026-09-11: -29 -> -22 on a Knight's War Cleaver, two runes apart,
                              # i.e. UPWARD in this value. Matches the wiki's own "+1-7".
        "category": "dump",   # per the user, this row only: the armour checkbox above stays "required".
        "signed_penalty": True,
        "only_categories": (WEAPON,),
    },
    {
        "label": "Night Sight",  # NEW (2026-08-27), per the user: pinned second (under Mage Armor)
                              # and given a checkbox, same treatment as Mage Armor -- a classic UO
                              # property that's normally presence/absence, not a stacking value.
        "line_text": "Night Sight",
        "syllable": "lor",
        "reagent_storage_row": "Spider's Silk",
        "reagent_match": "spider",
        "reagent_amount": 3,
        "prop_pattern": r'^\s*night sight',  # CORRECTED 2026-09-11 from r'night sight\s+(\d+)'.
                              # A "Blight Gripped Longbow" the user photographed carries a BARE
                              # "Night Sight" with no number, so the old extrapolated numeric
                              # pattern could never match -- every item read 0 against a
                              # target_stat of 1, so ticking this box would have applied rune
                              # after rune and then hit the FULL STOP blaming property
                              # detection. The 2026-08-27 comment here predicted exactly this
                              # ("expect corrections once each is actually seen live"); this is
                              # that correction, from a real item rather than the wiki's "+1".
                              # Prefix-anchored, no trailing $: '^' stops a substring matching
                              # another line, and leaving the tail open means an item that does
                              # print "night sight 1" still matches instead of failing silently.
        "gain_range": (1, 1),  # CONFIRMED via the wiki (fetched 2026-08-27) -- "+1", no weapon-
                                 # split ambiguity like Mage Armor has.
        "category": "required",
        "is_boolean": True,
    },
    {
        "label": "Spell Channeling",
        "line_text": "Spell Channeling",
        "syllable": "ahm",
        "reagent_storage_row": "Spider's Silk",
        "reagent_match": "spider",
        "reagent_amount": 5,
        "prop_pattern": r'^\s*spell channeling',  # CORRECTED 2026-09-16, exactly as Night Sight
                                # was on 2026-09-11 -- and this row's OWN revisit trigger is what
                                # fired it. The old pattern was r'spell channeling\s+(\d+)', kept
                                # numeric "for consistency" with Night Sight and carrying the note
                                # "Revisit like Mage Armor if a live tooltip shows no value."
                                #
                                # BOTH HALVES OF THAT EXPIRED. Night Sight itself became a
                                # checkbox, so the consistency argument now points the other way;
                                # and OmniData/ScratchTest_Equipment.txt, a real property
                                # capture, holds a BARE "spell channeling" with no number --
                                # beside "spellweaving +5", which does have one, so the capture is
                                # not stripping values.
                                #
                                # The old pattern could therefore NEVER match: every item read 0
                                # against a target of 1, which is rune after rune and then the
                                # FULL STOP blaming property detection -- verbatim the bug Night
                                # Sight had. Prefix-anchored with no trailing $ for the same
                                # reason as Night Sight: '^' stops a substring matching another
                                # line, and the open tail still matches an item that does print
                                # "spell channeling 1".
        "gain_range": (1, 1),
        "category": "required",
        "is_boolean": True,  # Per the user: "Didn't we decide spell channeling should be a
                                # checkbox?" A presence/absence property, same treatment as Mage
                                # Armor and Night Sight -- a numeric box asking for a target of 1
                                # on a flag was always the wrong control.
    },
    {
        "label": "Cold Resist",  # RENAMED (2026-08-27) from "Cold Resist Bonus" -- a real item
                              # screenshot showed the live property line is just "Cold Resist 26%",
                              # no "Bonus" suffix at all (unlike Strength/Dexterity/Intelligence
                              # Bonus, which DO carry "Bonus" in their own confirmed live text --
                              # resists apparently don't get a separate "bonus" line, this rune just
                              # adds to the item's own single existing resist number). This is
                              # SEPARATE from line_text below (the crafting MENU's own button text,
                              # a different thing from tooltip evidence -- see its own comment).
        "line_text": "Resist Cold",  # CONFIRMED live (2026-08-27) via an existing gump dump
                              # (scratch_test_result.txt) that captured the FULL real Enhancement
                              # menu -- was guessed as "Cold Resist Bonus" (wiki wording), but the
                              # real in-game button reads "Resist Cold" (reordered, no "Bonus" at
                              # all in the MENU either -- a separate coincidence from the tooltip's
                              # own lack of "Bonus", not the same evidence).
        "syllable": "del",
        "reagent_storage_row": "Black Pearl",
        "reagent_match": "black pearl",
        "reagent_amount": 5,
        "prop_pattern": r'cold resist(?:ance)?\s+(\d+)%',  # CONFIRMED live (2026-08-27) -- matches
                                # the real tooltip line ("Cold Resist 26%") as-is; already didn't
                                # require the word "Bonus", so no pattern change needed, just status.
        "gain_range": (3, 9),
        "category": "required",
    },
    {
        "label": "Defense Chance Inc",
        "line_text": "Defense Chance Inc",
        "syllable": "ra",
        "reagent_storage_row": "Sulfurous Ash",
        "reagent_match": "sulfurous ash",
        "reagent_amount": 5,
        "prop_pattern": r'defense chance increase\s+(\d+)%',
        "gain_range": (2, 8),
        "category": "required",
    },
    {
        "label": "Dexterity Bonus",
        "line_text": "Bonus Dex",  # CONFIRMED live (2026-08-27) via an existing gump dump
                              # (scratch_test_result.txt) that captured the FULL real Enhancement
                              # menu -- real MENU button is "Bonus Dex" (reordered + abbreviated),
                              # was guessed "Dexterity Bonus" (the wiki's own full name).
        "syllable": "por",
        "reagent_storage_row": "Bat Wing",
        "reagent_match": "bat wing",
        "reagent_amount": 7,
        "prop_pattern": r'dexterity bonus\s+(\d+)',
        "gain_range": (1, 7),
        "category": "required",
    },
    {
        "label": "Durability Bonus",
        "line_text": "Durability Bonus",
        "syllable": "aglo",
        "reagent_storage_row": "Mandrake Root",
        "reagent_match": "mandrake",
        "reagent_amount": 5,
        # THE SHARD SHOWS NO "Durability Bonus N%" LINE (2026-09-24 10:55, owner's tooltip: "Durability 45 / 45").
        # The rune raises MAX durability itself, so the tracked value is the number after the slash and a
        # TARGET IS A MAX DURABILITY, not a percent -- a 45/45 axe at +50% is a target of 68. The wiki-derived
        # percent pattern never matched: 836 applications today read 0 on 21 axes. gain_range is the wiki's
        # per-application figure and is UNMEASURED here; the before/after log lines now say the real gain.
        # ON CLOTH IT IS A PERCENT (2026-10-18, a body sash after one Aglo rune: "durability +20%" and no hit points
        # line at all) -- the second form; read_property_value() takes whichever group matched.
        "prop_pattern": r'durability\s+(?:\d+\s*/\s*(\d+)|\+(\d+)%)',
        "gain_range": (15, 25),
        "category": "required",
    },
    {
        "label": "Energy Resist",  # RENAMED (2026-08-27) -- see Cold Resist's own comment for why
                              # (confirmed live: no "Bonus" suffix on any resist TOOLTIP line).
        "line_text": "Resist Energy",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Cold Resist -- real MENU button is "Resist Energy" (reordered, no
                              # "Bonus"), was guessed "Energy Resist Bonus".
        "syllable": "hur",
        "reagent_storage_row": "Black Pearl",
        "reagent_match": "black pearl",
        "reagent_amount": 5,
        "prop_pattern": r'energy resist(?:ance)?\s+(\d+)%',  # CONFIRMED live (2026-08-27) -- see
                                # Cold Resist's own comment.
        "gain_range": (3, 9),
        "category": "required",
    },
    {
        "label": "Enhance Potions",
        "line_text": "Enhance Potions",
        "syllable": "zu",
        "reagent_storage_row": "Black Pearl",
        "reagent_match": "black pearl",
        "reagent_amount": 3,
        "prop_pattern": r'enhance potions\s+(\d+)%',
        "gain_range": (5, 12),
        "category": "required",
    },
    {
        "label": "Faster Cast Recovery",  # SPELLED OUT (2026-08-27), per the user: the acronym
                              # looked out of place once every other row (added the same session)
                              # got a full name. line_text below is UNCHANGED -- that's the real,
                              # separately-CONFIRMED shard menu text ("Cast Recovery", no "Faster"),
                              # not this project's own display choice, so it stays as-is.
        "line_text": "Cast Recovery",  # CORRECTED TWICE (2026-08-27) -- per the user, live: "I
                                # think this might be searching for the abbreviation?" (right --
                                # the original "FCR" never matched anything, a live FATAL stop) then
                                # "cast speed/recovery are different too" with a real Enhancement
                                # category screenshot -- CONFIRMED verbatim: this shard's menu uses
                                # "Cast Recovery", NOT the standard UO "Faster Cast Recovery" my
                                # first guess assumed. Shard-specific shortened naming, not just a
                                # missing "Faster" -- see prop_pattern below, widened to match
                                # either wording since the TOOLTIP text (post-application) hasn't
                                # been independently confirmed and may follow either convention.
        "syllable": "summ",
        "reagent_storage_row": "Black Pearl",
        "reagent_match": "black pearl",
        "reagent_amount": 5,
        "prop_pattern": r'(?:faster )?cast recovery\s+(\d+)',  # WIDENED (2026-08-27) to match
                                # either "Faster Cast Recovery X" (standard UO tooltip convention)
                                # or "Cast Recovery X" (this shard's own menu wording, CONFIRMED
                                # live) -- since the menu label diverged from standard UO naming,
                                # the tooltip text can no longer be assumed to follow the standard
                                # convention either; still EXTRAPOLATED/unconfirmed until a real
                                # FCR item is read, just hedged against both possibilities now.
        "gain_range": (1, 3),  # CONFIRMED via the wiki (fetched 2026-08-27).
        "category": "required",  # Per the user (2026-08-27): FCR/FC/LRC/LMC are the build-defining
                              # "Required Stats" -- applied even to the very last eligible item,
                              # unlike SDI/Luck's protected-last-copy "Dump Stats" treatment.
    },
    {
        "label": "Faster Casting",  # SPELLED OUT (2026-08-27) -- see FCR's own comment above for
                              # why. line_text below is UNCHANGED (real shard menu text).
        "line_text": "Cast Speed",  # CORRECTED TWICE (2026-08-27) -- CONFIRMED live via a real
                                # Enhancement category screenshot: "Cast Speed", not the standard UO
                                # "Faster Casting" my first guess assumed -- see FCR's own comment
                                # for the same shard-specific-naming story.
        "syllable": "um",
        "reagent_storage_row": "Mandrake Root",
        "reagent_match": "mandrake",
        "reagent_amount": 5,
        "prop_pattern": r'(?:faster casting|cast speed)\s+(\d+)',  # WIDENED (2026-08-27) -- see
                                # FCR's own comment. "Cast Speed" isn't just an abbreviated prefix of
                                # "Faster Casting" (different word structure entirely), so this
                                # matches both phrasings explicitly rather than trying to share a
                                # prefix/suffix pattern. Still EXTRAPOLATED/unconfirmed until a real
                                # FC item is read.
        "gain_range": (1, 1),  # CONFIRMED via the wiki (fetched 2026-08-27) -- always exactly +1
                                 # per application, not a true range, same "tuple that happens to
                                 # still average correctly" shape as Luck's own gain_range.
        "category": "required",
    },
    {
        "label": "Fire Resist",  # RENAMED (2026-08-27) -- see Cold Resist's own comment for why.
        "line_text": "Resist Fire",  # CONFIRMED live (2026-08-27) via the same gump dump as Cold
                              # Resist -- real MENU button is "Resist Fire" (reordered, no
                              # "Bonus"), was guessed "Fire Resist Bonus".
        "syllable": "flam",
        "reagent_storage_row": "Sulfurous Ash",
        "reagent_match": "sulfurous ash",
        "reagent_amount": 5,
        "prop_pattern": r'fire resist(?:ance)?\s+(\d+)%',  # CONFIRMED live (2026-08-27) -- see
                                # Cold Resist's own comment.
        "gain_range": (3, 9),
        "category": "required",
    },
    {
        "label": "Hit Chance Increase",
        "line_text": "Hit Chance Increase",
        "syllable": "uus",
        "reagent_storage_row": "Bloodmoss",
        "reagent_match": "bloodmoss",
        "reagent_amount": 5,
        "prop_pattern": r'hit chance increase\s+(\d+)%',
        "gain_range": (3, 9),
        "category": "required",
    },
    {
        "label": "Hit Point Increase",
        "line_text": "Bonus Hits",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Bonus Hits", was guessed
                              # "Hit Point Increase" (the wiki's own full name).
        "syllable": "mani",
        "reagent_storage_row": "Ginseng",
        "reagent_match": "ginseng",
        "reagent_amount": 7,
        "prop_pattern": r'hit point increase\s+(\d+)',  # CONFIRMED live (2026-08-27, real item
                                # screenshot -- "Hit Point Increase 10", no percent sign).
        "gain_range": (1, 7),
        "category": "required",
    },
    {
        "label": "Hit Point Regen",
        "line_text": "Regen Hits",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Regen Hits" (reordered +
                              # abbreviated), was guessed "Hit Point Regen".
        "syllable": "mu",
        "reagent_storage_row": "Ginseng",
        "reagent_match": "ginseng",
        "reagent_amount": 7,
        "prop_pattern": r'hit point regen(?:eration)?\s+(\d+)',
        "gain_range": (1, 2),  # Wiki's exact text is "+1..3 weapon, else +1..2" -- same weapon-
                                 # split shape as Mana Regen, same fix applied up front this time:
                                 # no weapon slot exists in SLOT_CATALOG, so this uses the "else"
                                 # range, not the wiki's headline weapon number.
        "category": "required",
    },
    {
        "label": "Intelligence Bonus",
        "line_text": "Bonus Int",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Bonus Int" (reordered +
                              # abbreviated), was guessed "Intelligence Bonus".
        "syllable": "wis",
        "reagent_storage_row": "Ginseng",
        "reagent_match": "ginseng",
        "reagent_amount": 5,
        "prop_pattern": r'intelligence bonus\s+(\d+)',
        "gain_range": (1, 7),
        "category": "required",
    },
    {
        "label": "Lower Mana Cost",  # SPELLED OUT (2026-08-27) -- see FCR's own comment for why.
                              # Was "LMC" before this. Unrelated to line_text's own earlier fix
                              # below (that one was about the real in-game menu text, not display).
        "line_text": "Lower Mana Cost",  # FIXED (2026-08-27) -- was still the literal abbreviation
                                # "LMC", which caused the live "FATAL: could not resolve 'LMC's
                                # button" batch stop (174 Blank Runes left unenhanced). The real value
                                # was already CONFIRMED via the first screenshot in this exchange
                                # (Enhancement page showing "Lower Mana Cost" verbatim) but never
                                # actually applied to this entry -- FCR/FC/LRC got fixed in the same
                                # pass, this one was missed until a follow-up grep caught it.
        "syllable": "pas",
        "reagent_storage_row": "Daemon Blood",
        "reagent_match": "daemon blood",
        "reagent_amount": 5,
        "prop_pattern": r'lower mana cost\s+(\d+)%',  # CONFIRMED (2026-08-27) -- "Lower Mana Cost"
                                # is the real menu text verbatim, no shard-specific shortening like
                                # FCR/FC/LRC had, so no widening needed here.
        "gain_range": (3, 8),  # CONFIRMED via the wiki (fetched 2026-08-27).
        "category": "required",
    },
    {
        "label": "Lower Reagent Cost",  # SPELLED OUT (2026-08-27) -- see FCR's own comment for
                              # why. line_text below is UNCHANGED ("Lower Reg Cost", the real,
                              # separately-CONFIRMED shard menu text -- this shard's own
                              # abbreviation for "Reagent", not this project's display choice).
                              # Reordered (2026-08-27) to keep the whole catalog alphabetical by
                              # label -- was "LRC", sorted between "Lower Stat Req" and "Luck";
                              # "Lower Reagent Cost" now sorts before "Lower Stat Req" instead.
        "line_text": "Lower Reg Cost",  # CORRECTED TWICE (2026-08-27) -- CONFIRMED live via a real
                                # Enhancement category screenshot: "Lower Reg Cost", not the standard
                                # UO "Lower Reagent Cost" my first guess assumed -- see FCR's own
                                # comment for the same shard-specific-naming story ("Reg" is this
                                # menu's own abbreviation for "Reagent").
        "syllable": "ylem",
        "reagent_storage_row": "Daemon Blood",
        "reagent_match": "daemon blood",
        "reagent_amount": 7,
        "prop_pattern": r'lower rea?g(?:ent)? cost\s+(\d+)%',  # TRANSPOSITION FIXED 2026-09-16.
                                # This read r'lower reg(?:ent)? cost...', which expands to "reg"
                                # or "regent" -- never "reagent" -- so the widening the comment
                                # below advertises never actually happened. The live capture
                                # (OmniData/ScratchTest_Equipment.txt) shows the real item
                                # line is "lower reagent cost 40%", so this could never match and
                                # LRC read 0 on every item: rune after rune, then the FULL STOP,
                                # the same failure Night Sight and Spell Channeling had.
                                # "rea?g(?:ent)?" covers all three spellings: reg, regent, reagent.
                                # ORIGINAL NOTE FOLLOWS -- WIDENED (2026-08-27) -- see FCR's
                                # own comment. Matches either "Lower Reg Cost X%" or "Lower Reagent
                                # Cost X%" since the tooltip wording is still unconfirmed. Percent
                                # sign included here (unlike FCR/FC) since LRC is conventionally
                                # displayed as a percentage in standard UO tooltips, same convention
                                # SDI's own CONFIRMED pattern already established.
        "gain_range": (3, 10),  # CONFIRMED via the wiki (fetched 2026-08-27).
        "category": "required",
    },
    {
        "label": "Lower Stat Req",
        "line_text": "Lower Stat Req",
        "syllable": "lum",
        "reagent_storage_row": "Ginseng",
        "reagent_match": "ginseng",
        "reagent_amount": 3,
        # the shard's own line is "lower requirements 22%" (2026-10-18, a body sash after one Lum rune)
        "prop_pattern": r'lower (?:stat(?:ute)? req(?:uirements?)?|requirements)\s+(\d+)%',
        "gain_range": (5, 25),
        "category": "required",
    },
    {
        "label": "Luck",
        "line_text": "Luck",
        "syllable": "in",
        "reagent_storage_row": "Garlic",
        "reagent_match": "garlic",
        "reagent_amount": 3,
        "prop_pattern": r'luck\s+(\d+)',  # CONFIRMED live (2026-08-27, real item screenshot --
                                # "Luck 240", no percent sign) -- was EXTRAPOLATED before that, per
                                # the user's own explicit instruction (2026-08-18): the wiki's
                                # rune-name table confirms the property is plainly "Luck" (no
                                # qualifier, unlike SDI's "Spell Damage Increase"), and Luck is one
                                # of the most standard, long-established UO item properties. Matched
                                # lowercase against Items.GetPropStringList() the same way SDI's own
                                # pattern is (see read_property_value()).
        "gain_range": (15, 30, 45),  # CONFIRMED via the wiki (2026-08-18) -- Luck applies a random
                                   # pick of EXACTLY 15, 30, or 45 per application, never any value
                                   # in between. WIRED IN AS A TRUE DISCRETE SET (2026-08-27, per
                                   # the user) rather than a (min, max) pair -- was (15, 45) before,
                                   # which happened to average correctly (30) but understated the
                                   # real variance by half when simulate_stat_trial() drew from it
                                   # via random.uniform(15, 45) (a continuous approximation that can
                                   # produce impossible values like 22 or 38). A 3+ element tuple
                                   # here is the signal both consumers key off: estimate_
                                   # applications_needed()'s sum(gain_range)/len(gain_range) still
                                   # gets the correct mean (30), and simulate_stat_trial() switches
                                   # to random.choice(gain_range) for an exact discrete draw. See
                                   # both functions' own comments and PROPERTY_CATALOG's header.
        "category": "dump",  # Per the user (2026-08-27): the other of the two dump stats. Luck and
                              # SDI qualify for the same single reason -- neither has a maximum
                              # effective value, so surplus runes keep buying real benefit. See the
                              # Spell Damage Increase entry below for the full rule and why it is now
                              # load-bearing (a required stat failing halts the run).
    },
    {
        "label": "Mana Increase",
        "line_text": "Bonus Mana",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Bonus Mana", was guessed
                              # "Mana Increase".
        "syllable": "ort",
        "reagent_storage_row": "Daemon Blood",
        "reagent_match": "daemon blood",
        "reagent_amount": 7,
        "prop_pattern": r'mana increase\s+(\d+)',  # CONFIRMED live (2026-08-27, real item
                                # screenshot -- "Mana Increase 5", no percent sign).
        "gain_range": (1, 7),
        "category": "required",
    },
    {
        "label": "Mana Regen",
        "line_text": "Regen Mana",  # FIXED (2026-08-27) -- was "Mana Regen" (reversed word order),
                                # same missed-fix gap as LMC above. The real menu text was CONFIRMED
                                # via the first screenshot in this exchange ("Regen Mana" verbatim,
                                # same Enhancement page that showed "Lower Mana Cost") but never
                                # actually applied to this entry until now.
        "syllable": "om",
        "reagent_storage_row": "Grave Dust",
        "reagent_match": "grave dust",
        "reagent_amount": 5,
        "prop_pattern": r'mana regen(?:eration)?\s+(\d+)',  # EXTRAPOLATED (2026-08-27) -- same
                                # sourcing/reasoning as FCR/FC/LRC/LMC's own EXTRAPOLATED patterns
                                # (fetched from the wiki, cross-checked against this file's already-
                                # verified rows). Matches either "Mana Regen X" or "Mana
                                # Regeneration X" -- standard UO tooltips commonly spell this
                                # property out in full, unlike the abbreviated in-game rune-crafting
                                # menu label, and this hasn't been read off a live item yet to know
                                # which this shard actually uses.
        "gain_range": (1, 2),  # FIXED (2026-08-27) -- wiki's exact text is "+1..3 weapon, else
                                # +1..2" (re-fetched and confirmed verbatim, per the user's own
                                # catch). Was wrongly set to the WEAPON range (1, 3) despite this
                                # script having no weapon slot in SLOT_CATALOG at all (RightHand is
                                # deliberately excluded -- see that catalog's own comment), so every
                                # reachable Mana Regen target today is non-weapon and should use the
                                # "else" range. Revisit if a weapon slot is ever added.
        "category": "required",  # Per the user (2026-08-27): "let's add another important stat" --
                              # treated as a build-defining stat like FCR/FC/LRC/LMC, not a dump
                              # stat, unless the user says otherwise.
    },
    {
        "label": "Physical Resist",  # RENAMED (2026-08-27) -- see Cold Resist's own comment for why.
        "line_text": "Resist Phys Bonus",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Cold Resist -- real MENU button is "Resist Phys Bonus" (reordered,
                              # abbreviated "Physical"->"Phys", AND keeps "Bonus" -- unlike Cold/
                              # Fire/Energy Resist's own menu text, which drops "Bonus" entirely.
                              # Genuinely inconsistent shard naming, not a typo -- Poison Resist
                              # below has this same "keeps Bonus" shape).
        "syllable": "dium",
        "reagent_storage_row": "Garlic",
        "reagent_match": "garlic",
        "reagent_amount": 5,
        "prop_pattern": r'physical resist(?:ance)?\s+(\d+)%',  # CONFIRMED live (2026-08-27) -- see
                                # Cold Resist's own comment.
        "gain_range": (3, 9),
        "category": "required",
    },
    {
        "label": "Poison Resist",  # RENAMED (2026-08-27) -- see Cold Resist's own comment for why.
        "line_text": "Resist Poison Bonus",  # CONFIRMED live (2026-08-27) via the same gump dump
                              # as Cold Resist -- real MENU button is "Resist Poison Bonus"
                              # (reordered AND keeps "Bonus" -- same shape as Physical Resist's own
                              # menu text). Was guessed "Poison Resist Bonus" (right words, wrong
                              # order).
        "syllable": "nox",
        "reagent_storage_row": "Nox Crystal",
        "reagent_match": "nox crystal",
        "reagent_amount": 5,
        "prop_pattern": r'poison resist(?:ance)?\s+(\d+)%',  # CONFIRMED live (2026-08-27) -- see
                                # Cold Resist's own comment.
        "gain_range": (3, 9),
        "category": "required",
    },
    {
        "label": "Reflect Physical",
        "line_text": "Reflect Physical",
        "syllable": "sanct",
        "reagent_storage_row": "Pig Iron",
        "reagent_match": "pig iron",
        "reagent_amount": 5,
        "prop_pattern": r'reflect physical(?: damage)?\s+(\d+)%',
        "gain_range": (3, 8),
        "category": "required",
    },
    {
        "label": "Spell Damage Increase",  # SPELLED OUT (2026-08-27) -- see FCR's own comment for
                              # why. line_text below is UNCHANGED ("SDI", the real, already-live-
                              # CONFIRMED shard menu text -- unlike FCR/FC/LRC/LMC, this one really
                              # is the bare acronym in-game, not a display choice). PINNED HERE
                              # deliberately (2026-08-27), per the user, OUT of strict alphabetical
                              # order: "SDI is still a dump stat. Move that back please." -- briefly
                              # relocated (right after "Spell Channeling") to sort strictly
                              # alphabetically by its new full label, then moved back HERE to this,
                              # its ORIGINAL position, per the user's own explicit call. Every other
                              # entry in this catalog is still purely alphabetical by label -- this
                              # is the one deliberate exception.
        "line_text": "SDI",
        "syllable": "corp",
        "reagent_storage_row": "Grave Dust",
        "reagent_match": "grave dust",
        "reagent_amount": 7,
        "prop_pattern": r'spell damage increase\s+(\d+)%',
        "gain_range": (1, 7),
        "category": "dump",  # Per the user (2026-08-27): "For now, SDI and Luck are the only dump
                              # stats." Dump stats keep the ORIGINAL floor -- stop once the eligible
                              # pool drops to 1, protecting the last copy of a slot item.
                              #
                              # WHY THESE TWO AND NOTHING ELSE (2026-09-04) -- the actual rule, per
                              # the user, finally written down: "i don't know if any other stats
                              # scale to infinity, i think all of the others have maximum effective
                              # values, so only SDI and Luck make sense as dump stats." That is the
                              # whole test. SDI and Luck have NO effective ceiling, so surplus runes
                              # keep buying real value and are worth dumping into them. Every other
                              # property caps out, and past that cap an application is simply wasted
                              # -- which is why they are "required" (chase the target, then stop)
                              # rather than "dump" (soak up whatever is left over).
                              #
                              # This is now load-bearing beyond ordering: a REQUIRED stat failing
                              # HALTS the whole run (see run_apply_flow()'s own loop), so mislabelling
                              # a capped stat as "dump" would let a genuine failure slide by. Do not
                              # add a stat here unless it genuinely scales without limit.
    },
    {
        "label": "Self Repair",
        "line_text": "Self Repair",
        "syllable": "rel",
        "reagent_storage_row": "Spider's Silk",
        "reagent_match": "spider",
        "reagent_amount": 3,
        "prop_pattern": r'self repair\s+(\d+)',  # CONFIRMED live (2026-08-27, real item screenshot
                                # -- "Self Repair 10", no percent sign) -- was EXTRAPOLATED before
                                # that, on the same reasoning as Luck's own comment.
        "gain_range": (1, 4),  # CONFIRMED via the wiki's syllable table (2026-08-18).
        "category": "required",  # Default -- see SDI's own comment for the dump/required split.
    },
    {
        "label": "Stamina Increase",
        "line_text": "Bonus Stam",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Bonus Stam", was guessed
                              # "Stamina Increase". NOTE: distinct from Stamina Regen's own menu
                              # text ("Regen Stam") -- easy to conflate the two syllables, don't.
        "syllable": "ex",
        "reagent_storage_row": "Mandrake Root",
        "reagent_match": "mandrake",
        "reagent_amount": 7,
        "prop_pattern": r'stamina increase\s+(\d+)',
        "gain_range": (1, 7),
        "category": "required",
    },
    {
        "label": "Stamina Regen",
        "line_text": "Regen Stam",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Regen Stam" (reordered +
                              # abbreviated), was guessed "Stamina Regen".
        "syllable": "beh",
        "reagent_storage_row": "Bloodmoss",
        "reagent_match": "bloodmoss",
        "reagent_amount": 5,
        "prop_pattern": r'stamina regen(?:eration)?\s+(\d+)',
        "gain_range": (1, 3),  # No weapon-vs-else split in the wiki for this one, unlike Mana
                                 # Regen/Hit Point Regen -- flat (1, 3) regardless of item type.
        "category": "required",
    },
    {
        "label": "Strength Bonus",
        "line_text": "Bonus Str",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Bonus Str" (reordered +
                              # abbreviated), was guessed "Strength Bonus".
        "syllable": "vas",
        "reagent_storage_row": "Mandrake Root",
        "reagent_match": "mandrake",
        "reagent_amount": 7,
        "prop_pattern": r'strength bonus\s+(\d+)',  # CONFIRMED live (2026-08-27, real item
                                # screenshot -- "Strength Bonus 5", no percent sign). Unlike the
                                # 5 elemental/physical Resist properties, Bonus stats for the 3
                                # attributes (Str/Dex/Int) DO keep "Bonus" in their real live text
                                # -- confirmed directly, not assumed by analogy.
        "gain_range": (1, 7),
        "category": "required",
    },
    {
        "label": "Swing Speed Increase",
        "line_text": "Swing Speed Inc",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Swing Speed Inc"
                              # (abbreviated "Increase"->"Inc"), was guessed "Swing Speed Increase".
        "syllable": "tym",
        "reagent_storage_row": "Bloodmoss",
        "reagent_match": "bloodmoss",
        "reagent_amount": 5,
        "prop_pattern": r'swing speed increase\s+(\d+)%',  # CONFIRMED live (2026-08-27, real item
                                # screenshot -- "Swing Speed Increase 10%").
        "gain_range": (5, 12),
        "category": "required",
    },
    {
        "label": "Weapon Damage",
        "line_text": "Inc Wep Damage",  # CONFIRMED live (2026-08-27) via the same gump dump as
                              # Dexterity Bonus -- real MENU button is "Inc Wep Damage", was guessed
                              # "Weapon Damage".
        "syllable": "sar",
        "reagent_storage_row": "Bloodmoss",
        "reagent_match": "bloodmoss",
        "reagent_amount": 5,
        "prop_pattern": r'^\s*damage increase\s+(-?\d+)%',  # CORRECTED 2026-09-16 from
                                # r'weapon damage(?: increase)?\s+(\d+)%', which could never
                                # match, for TWO separate reasons -- both visible in the user's
                                # Resonant Staff Of Enlightenment tooltip:
                                #
                                #   "Damage Increase -40%"   <- what this rune actually writes
                                #   "Weapon Damage 11 - 14"  <- BASE damage, different property
                                #
                                # 1. The old prefix "weapon damage" belongs to the base damage
                                #    RANGE, which carries no percent sign and is not what the
                                #    rune changes. This rune's own menu name is "Inc Wep
                                #    Damage" and its property renders as "Damage Increase X%".
                                # 2. (\d+) cannot read "-40". First hard evidence that a
                                #    property here can go BELOW zero -- which also matters for
                                #    targeting, since the apply loop picks the item with the
                                #    LOWEST value and a -40 read as 0 is not the lowest.
                                #
                                # ANCHORED, AND THAT IS LOAD-BEARING: "Spell Damage Increase"
                                # is a separate rune whose line CONTAINS "damage increase 40%",
                                # so an unanchored version would match SDI's line and read one
                                # property's value for the other. Same reason Night Sight is
                                # anchored: "'^' stops a substring matching another line".
                                # Same bug family as Night Sight / Spell Channeling / Lower
                                # Reagent Cost: a read that is always 0 applies runes forever.
        "gain_range": (1, 7),
        "category": "dump",  # FLIPPED required -> dump (2026-09-19), per the user: "flip weapon damage to a dump stat, that is how it works on this server, I learned today." Concentrated on the best item(s) by select_apply_bases(), planned for SUGGEST_TARGET_MIN_ITEMS_REACHED, drawn in the Dump Stats column. One dump stat per batch (find_dump_request()).
    },

    # ==========================================================================================
    # THE 18 WEAPON RUNES (2026-09-11) -- catalog completed from 32 to all 50.
    #
    # EVERY line_text HERE WAS READ OFF THE LIVE MENU, not the wiki. ScratchTest.py drove the
    # chisel to the Enhancement category (proving ENHANCEMENT_CATEGORY_BUTTON = 1 in the same
    # pass) and dumped all 50 rows -- Output/Omni_ChiselMenuDump.txt. Cross-checked against
    # RuneSlotLogic.py's independent wiki-sourced names; FIVE of these eighteen differ from the
    # wiki wording, which is exactly why they could not be filled in from it:
    #     arma  menu "Use Best Wep"     wiki "Use Best Weapon Skill"
    #     bal   menu "Leech Stam"       wiki "Hit Stamina Leech"
    #     char  menu "Hit Lower Def"    wiki "Hit Lower Defense"
    #     gra   menu "Hit Leech Hits"   wiki "Hit Life Leech"
    #     quas  menu "Hit Leech Mana"   wiki "Hit Mana Leech"
    # A wrong line_text is a SILENT no-match, the same failure mode that produced "Bonus Dex",
    # "Cast Recovery" and the three resist corrections above.
    #
    # DELIBERATELY STAGED, NOT FINISHED. prop_pattern is None on every one, which makes
    # run_slot_application() refuse to run it -- "no live-confirmed property-text pattern ...
    # verify it with a scratch diagnostic first" -- exactly the staging state this catalog
    # already uses for an unverified property. That is the correct posture: the SYLLABLE and
    # line_text are proven, the on-item property TEXT is not, and guessing the latter is how the
    # entries above got their corrections. Each needs one real item inspected before it can run.
    #
    # gain_range is None for the same reason (pre-flight estimation skips, application still
    # refuses). The reagent fields are None rather than absent so the crafting flow -- currently
    # unreachable, mode is hardcoded "apply" -- raises nothing on a key that does not exist;
    # they need real per-rune data, which is NOT derivable (the 32 above use eight different
    # reagents at 3/5/7 each with no pattern).
    #
    # is_boolean is omitted throughout: it only drives the threshold UI, .get() defaults it
    # falsy, and it should be set alongside the prop_pattern that verifies it.
    #
    # WHAT THIS UNBLOCKS NOW: the slot -> rune UI can list all 50 runes, since RuneSlotLogic.py
    # joins to this catalog on "syllable" and every syllable is now present.
    # ==========================================================================================
    {
        "label": "Hit Dispel",
        "line_text": "Hit Dispel",
        "syllable": "an",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit dispel\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit dispel 10%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Use Best Wep",
        "line_text": "Use Best Wep",
        "syllable": "arma",
        "is_boolean": True,  # item text is a bare "Use Best Weapon Skill" -- measured 2026-09-11.
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'^\s*use best weapon skill',  # BOOLEAN -- measured 2026-09-11 on a native
                              # roll, "Silvani's Feywood Bow", which carries a bare "Use Best
                              # Weapon Skill" with no value. Note the menu label is the shorter
                              # "Use Best Wep" -- only the ITEM text may become a prop_pattern,
                              # the usual third naming layer this project keeps rediscovering.
        "gain_range": (1, 1),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+1" flag -- same shape as Spell Channeling
        "category": "required",
    },
    {
        "label": "Leech Stam",
        "line_text": "Leech Stam",
        "syllable": "bal",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit stamina leech\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit stamina leech 40%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Balanced",
        "line_text": "Balanced",
        "syllable": "bala",
        "is_boolean": True,  # bare "Balanced", no value -- measured 2026-09-11.
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'^\s*balanced',  # BOOLEAN -- measured 2026-09-11 on a real weapon: the line
                              # is a bare "Balanced" with no value. Readable now that
                              # read_property_value() returns 1 on a match for is_boolean
                              # properties, so no capture group is needed. '^' matters here:
                              # an unanchored r'balanced' would also match "unbalanced".
        "gain_range": (1, 1),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+1" flag -- same shape as Spell Channeling
        "category": "required",
    },
    {
        "label": "Hit Magic Arrow",
        "line_text": "Hit Magic Arrow",
        "syllable": "bet",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit magic arrow\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit magic arrow 25%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Lower Def",
        "line_text": "Hit Lower Def",
        "syllable": "char",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit lower defense\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit lower defense 30%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Lower Attack",
        "line_text": "Hit Lower Attack",
        "syllable": "des",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit lower attack\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit lower attack 50%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Fire Area",
        "line_text": "Hit Fire Area",
        "syllable": "flamus",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit fire area\s+(\d+)%',  # MEASURED LIVE 2026-09-11 17:43:51 -- a Flamus Rune applied to a
                              # "thundering axe" added exactly this line: "hit fire area 12%".
                              # The shard said "The Flamus Rune enhances your weapon."
                              # This one application also settles frio/furis/grav below: the Area
                              # form is one construction with the element word substituted.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Cold Area",
        "line_text": "Hit Cold Area",
        "syllable": "frio",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit cold area\s+(\d+)%',  # CONFIRMED BY FAMILY 2026-09-11 -- not applied directly, but the Area form
                              # was measured live that day (flamus -> "hit fire area 12%") and this differs
                              # from it only in the element/stat word, which matches its own menu label.
                              # The family also has an independently measured sibling (malas "hit poison area 30%"), so the
                              # construction is anchored at both ends rather than extrapolated from one.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Energy Area",
        "line_text": "Hit Energy Area",
        "syllable": "furis",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit energy area\s+(\d+)%',  # CONFIRMED BY FAMILY 2026-09-11 -- not applied directly, but the Area form
                              # was measured live that day (flamus -> "hit fire area 12%") and this differs
                              # from it only in the element/stat word, which matches its own menu label.
                              # The family also has an independently measured sibling (malas "hit poison area 30%"), so the
                              # construction is anchored at both ends rather than extrapolated from one.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Leech Hits",
        "line_text": "Hit Leech Hits",
        "syllable": "gra",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit life leech\s+(\d+)%',  # MEASURED LIVE 2026-09-11 17:48:47 -- a Gra Rune applied to a
                              # "butcher's war cleaver" added exactly this line: "hit life leech 8%".
                              # The shard said "The Gra Rune enhances your weapon."
                              # Settles quas below by the same substitution argument.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Physical Area",
        "line_text": "Hit Physical Area",
        "syllable": "grav",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit physical area\s+(\d+)%',  # CONFIRMED BY FAMILY 2026-09-11 -- not applied directly, but the Area form
                              # was measured live that day (flamus -> "hit fire area 12%") and this differs
                              # from it only in the element/stat word, which matches its own menu label.
                              # The family also has an independently measured sibling (malas "hit poison area 30%"), so the
                              # construction is anchored at both ends rather than extrapolated from one.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Harm",
        "line_text": "Hit Harm",
        "syllable": "jux",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit harm\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit harm 40%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Fireball",
        "line_text": "Hit Fireball",
        "syllable": "kal",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit fireball\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit fireball 60%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Poison Area",
        "line_text": "Hit Poison Area",
        "syllable": "malas",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit poison area\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit poison area 30%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Leech Mana",
        "line_text": "Hit Leech Mana",
        "syllable": "quas",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit mana leech\s+(\d+)%',  # CONFIRMED BY FAMILY 2026-09-11 -- not applied directly, but the Leech form
                              # was measured live that day (gra -> "hit life leech 8%") and this differs
                              # from it only in the element/stat word, which matches its own menu label.
                              # The family also has an independently measured sibling (bal "hit stamina leech 40%"), so the
                              # construction is anchored at both ends rather than extrapolated from one.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Velocity",
        "line_text": "Velocity",
        "syllable": "vel",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'velocity\s+(\d+)%',  # MEASURED 2026-09-11 off a native roll, not an application:
                              # a "Blight Gripped Longbow" reads "Velocity 8%". Same evidence
                              # standard as the nine patterns measured earlier that day -- seen on
                              # a real item, so the wording is the shard's, not a guess.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
    {
        "label": "Hit Lightning",
        "line_text": "Hit Lightning",
        "syllable": "xen",
        "reagent_storage_row": None,
        "reagent_match": None,
        "reagent_amount": None,
        "prop_pattern": r'hit lightning\s+(\d+)%',  # MEASURED 2026-09-11 off a real weapon from the Armory:
                              # "hit lightning 50%". Not the menu label and not the rune tooltip -- both
                              # differ from the item text.
        "gain_range": (5, 12),  # CONFIRMED via the shard wiki (beyondsosaria.com/wiki/rune-crafting, fetched 2026-09-18): "+5..12"
        "category": "required",
    },
]

# Break-chance model, sourced from beyondsosaria.com/wiki/rune-crafting's own formula: roll a
# base destroy chance in [0.0, 1.0), add Inscription*0.001 (if 105.0+), add 0.1 if the Perk Deed
# ("Better Rune Crafting") is active; success requires that roll > 0.40 AND a second independent
# roll > 0.02. At this script's own required operating conditions (300+ effective Inscription,
# deed active -- see REQUIRED_INSCRIPTION_SKILL/PERK_DEED_LABEL), the bonus is
# 300*0.001 + 0.1 = 0.4, which always clears the first roll's ">0.40" requirement -- leaving only
# the flat, un-improvable 2% from the second roll. NOT empirically validated against a real
# observed break (per the user, not worth pursuing a break message) -- this is a wiki-sourced,
# worked-out figure, used only for planning estimates, not a safety-critical value.
BREAK_CHANCE_PER_APPLICATION = 0.02

# How much of the backpack's max item-slot capacity bulk-crafting is allowed to fill, per the
# user ("craft runes to 95% max inventory size"). Applies uniformly to every bulk-craft, both the
# initial pre-flight batch and any later interleaved top-up.
MAX_INVENTORY_FRACTION = 0.95

# Rough throughput estimate (see project memory) used only to give the pre-flight log message a
# human "about how long" figure -- not used for any actual timing/control logic.
ESTIMATED_APPLICATIONS_PER_HOUR = 800

# REVISED (2026-08-27) -- the single shared LAST_TARGET_STAT_FILE this project used to pre-fill
# ONE generic threshold box no longer fits now that every stat has its OWN box (see project
# memory, 2026-08-21 vs. this session's redesign). First replaced with nothing (blank-by-default,
# so an untouched box unambiguously means "not requested" for SELECTION purposes) -- but per the
# user's own live follow-up, after actually seeing the gump: "Let's default each of the threshold
# boxes to 0, or whatever was entered last." Pre-filling with "0" doesn't break the selection
# signal at all (0 is still exactly as "not requested" as blank was -- run_slot_application()'s
# own callers already treat target_stat <= 0 as not-selected), so this is a pure UX improvement,
# not a design conflict with the blank-by-default reasoning above. Per-PROPERTY memory now (keyed
# by label, not one shared value) -- the thresholds file stores every numeric field's own
# last-submitted value (whether that was 0 or a real target), independent of every other field's.
LAST_APPLY_THRESHOLDS_FILENAME = "LastApplyThresholds.txt"
# THE LEGACY FALLBACK IS GONE (2026-09-14), per the user: "every time i open the freshly copied
# version of the script, it's pulling the same old numbers on this screen ... they should be 0 in a
# fresh start."
#
# It read OmniData/Omni_RuneCrafting_LastApplyThresholds.txt whenever the per-script file
# was empty. Worse, that path is built from the script's DIRECTORY plus a fixed filename, so it was
# the same file for every copy in the Scripts folder -- a renamed script got its own data folder and
# then inherited another script's numbers through the back door regardless.
#
# Third instance of this mistake in one evening (after the hardcoded perk-chest serial and the
# hardcoded rune folder/names): a shim added to spare THIS install a reconfiguration, which hid the
# fresh-install state the work existed to expose. Unset now means unset.
#
# The old file is left on disk, simply unread. Deleting a player's data to finish a refactor would
# be its own mistake.


def script_data_dir():
    """<this script's own folder>/<this script's own filename, no extension>/.

    NAMED AFTER THE SCRIPT (2026-09-14), per the user: "can it default to the script name so if
    people rename it Jelly Crafting it'll generate the needed documents to the scripts existing
    directory in a new folder called Jelly Crafting?" Rename the file and the folder follows; the
    old name ("OmniData") meant nothing to anyone who had renamed it.

    __file__-RELATIVE ON PURPOSE, not cwd-relative: RazorEnhanced's working directory is the TazUO
    ROOT, not the Scripts folder, so a plain relative path writes somewhere else entirely. The
    original code already got this right and it is preserved deliberately.

    A FUNCTION RATHER THAN A MODULE-LEVEL CONSTANT so nothing has to be defined above anything
    else -- this project has lost scripts on load to exactly that ordering trap."""
    here = os.path.abspath(__file__)
    return os.path.join(os.path.dirname(here),
                        os.path.splitext(os.path.basename(here))[0])


def script_data_path(filename):
    """Full path to `filename` inside script_data_dir(). Does not touch the disk."""
    return os.path.join(script_data_dir(), filename)


def ensure_script_data_dir():
    """Create script_data_dir() if absent. True when it exists afterwards.

    THE BUG THIS FIXES: the previous save opened its file inside a bare `except: pass` with nothing
    creating the folder. That works on a machine where the folder already exists and fails SILENTLY
    forever on a fresh install -- no error, no log line, a feature that simply never persists for a
    new player. os.makedirs is used without exist_ok= (added in Python 3.2) and guarded by an
    isdir() check instead, so behaviour does not depend on the IronPython build's stdlib level."""
    d = script_data_dir()
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
        return True
    except Exception:
        return False


SETUP_FILENAME = "Setup.txt"
SETUP_CACHE = {}          # key -> value (strings), loaded once per run
SETUP_LOADED = [False]    # a list so setup_get() can flip it without a global statement


def load_setup():
    """{key: value} of everything first-run setup has saved. Strings, unparsed.

    Same plain 'key=value' shape and best-effort posture as the thresholds file beside it: an absent
    or unreadable file means "nothing configured yet", which is the correct state for a fresh
    install rather than an error."""
    SETUP_CACHE.clear()
    try:
        with open(script_data_path(SETUP_FILENAME), "r") as f:
            for line in f:
                if "=" not in line:
                    continue
                key, _sep, value = line.strip().partition("=")
                key = key.strip()
                if key:
                    SETUP_CACHE[key] = value.strip()
    except Exception:
        pass
    SETUP_LOADED[0] = True
    return SETUP_CACHE


def save_setup():
    """Persist SETUP_CACHE. True on success.

    LOGS ON FAILURE rather than swallowing it. A setup step that silently fails to save is worse
    than one that fails loudly: the player only finds out next session, when their answers are
    gone and nothing says why."""
    if not ensure_script_data_dir():
        log("Could not create '{}' -- setup answers will not be remembered."
            .format(script_data_dir()), 33)
        return False
    path = script_data_path(SETUP_FILENAME)
    try:
        with open(path, "w") as f:
            for key in sorted(SETUP_CACHE):
                f.write("{}={}\n".format(key, SETUP_CACHE[key]))
        return True
    except Exception as _err:
        log("Could not save setup to '{}' ({}) -- answers will not be remembered."
            .format(path, _err), 33)
        return False


def setup_get(key, default=""):
    """Saved value for `key`, or `default` when unset or empty. Loads the file on first use."""
    if not SETUP_LOADED[0]:
        load_setup()
    value = SETUP_CACHE.get(key, "")
    return value if value else default


def setup_set(key, value):
    """Set a value in the cache. Call save_setup() to persist."""
    if not SETUP_LOADED[0]:
        load_setup()
    SETUP_CACHE[key] = "" if value is None else str(value)


def load_last_apply_thresholds():
    """Returns {label: value} for every numeric threshold field that has EVER been submitted (see
    save_last_apply_thresholds()) -- missing/unparseable entries are simply absent, not defaulted
    to anything here (ask_apply_requests_and_slot() itself falls back to "0" for any label not
    present).
    Best-effort -- any read/parse failure just returns {} rather than raising.

    THIS SCRIPT'S OWN FILE AND NOTHING ELSE (2026-09-14). A fallback to the old shared location used
    to sit here and meant a freshly copied script opened pre-filled with another copy's numbers --
    see LEGACY_THRESHOLDS_RELPATH's retired comment above. Absent file means empty fields, which is
    what a new player must see."""
    result = {}
    try:
        with open(script_data_path(LAST_APPLY_THRESHOLDS_FILENAME), "r") as f:
            for line in f:
                if "=" not in line:
                    continue
                label, _sep, value = line.strip().partition("=")
                try:
                    result[label] = int(value)
                except ValueError:
                    pass
    except Exception:
        pass
    return result

def save_last_apply_thresholds(values_by_label):
    """Writes {label: value} into script_data_dir(), one 'Label=Value' line per numeric
    field -- called from ask_apply_requests_and_slot() right after parsing every field's raw text, with
    WHATEVER was actually in each box at submission (0 included, not just positive/selected
    values), so next time's pre-fill shows exactly what was there before.

    NO LONGER SILENT ON FAILURE. This used to swallow every error, which meant a fresh install --
    where the folder did not exist -- never persisted anything and never said why. A save that
    cannot happen is worth one line, because the player only finds out otherwise on the next run
    when their settings are gone."""
    if not ensure_script_data_dir():
        log("Could not create the data folder '{}' -- settings will not be remembered between "
            "runs.".format(script_data_dir()), 33)
        return
    path = script_data_path(LAST_APPLY_THRESHOLDS_FILENAME)
    try:
        with open(path, "w") as f:
            for label, value in values_by_label.items():
                f.write("{}={}\n".format(label, value))
    except Exception as _save_err:
        log("Could not save settings to '{}' ({}) -- they will not be remembered between "
            "runs.".format(path, _save_err), 33)

REQUEST_GUMP_ID = 0x52554E52      # "RUNR" -- arbitrary unique tag, same ASCII-tag convention as
                                    # this project's other custom gumps (PERK_TRACKER_GUMP_ID
                                    # "NWPT", DAILY_TASKS_COMPLETE_GUMP_ID "NWDC").
REQUEST_QUANTITY_ENTRY_ID = 1
REQUEST_PROPERTY_BUTTON_BASE = 100  # Property buttons start at 100 -- CONFIRMED live this scheme
                                      # round-trips correctly (button id -> catalog index, plus
                                      # whatever's in the quantity box, both in one response).
REQUEST_GUMP_WAIT_MS = 86400000  # 24 hours (2026-08-27), per the user: "get rid of the 60 second
                                # timeout to make a selection. That's not needed." Gumps.WaitForGump()
                                # requires SOME finite Int32 millisecond delay (no documented "wait
                                # forever" sentinel -- confirmed via RazorEnhanced.xml's own doc
                                # comment: "Maximum wait, in milliseconds"), so this is the practical
                                # stand-in for "no timeout" rather than a real infinite wait -- a
                                # human deciding what to craft/apply/accept should never be rushed by
                                # this project's own arbitrary clock. Well within Int32 range
                                # (2,147,483,647 ms max). This is a genuine "wait for a human to
                                # decide and type something" prompt, not a normal short settle wait,
                                # so this project's usual 5s ceiling never applied here anyway.
MAX_QUANTITY_SANITY_CAP = 50  # Per the user's own "let's try not to be wasteful" guidance -- a
                                # typo (e.g. an extra zero) shouldn't be able to queue up an
                                # enormous, unintended batch. Rejected outright above this, not
                                # silently clamped, so a genuine larger need is obvious to raise.

# Phase 2 (rune application) safety gates. Per the user: applying a rune has a real chance to
# break the target item, minimized two ways -- the "Perk Deed" buff (10% Less Break Chance) must
# be active, AND Inscription must be 300+.
PERKS_COMMAND = "[perks"
PERKS_JOURNAL_WAIT_MS = 2000  # RETIRED (2026-09-16), kept defined per this file's own convention
                              # for superseded machinery (see ask_which_mode()). [perks stopped
                              # broadcasting to the journal on 2026-09-08; there is no journal wait
                              # left to tune. The gump constants below replace it.

# THE SHARD MADE [perks A GUMP on 2026-09-08. Omni_Engine.py was ported that morning,
# PerkTracker.py on 2026-09-13; THIS FILE WAS MISSED and kept scanning a journal line that is no
# longer printed -- so every read returned {} and the gate reported the deed inactive while a real
# one was live. Values copied from those two ports; duplicated rather than imported because this
# script is deliberately free-standing.
PERKS_GUMP_ID = 0xBB4D7BED           # FAST FIRST GUESS ONLY, captured live 2026-09-08 -- handed to
                                     # WaitForGump. Identity is settled by CONTENT below, so a
                                     # shard-side renumber degrades to a scan instead of breaking
                                     # the read, which is exactly the failure being fixed here.
PERKS_GUMP_TITLE = "active perks"    # Matched against the gump's own first line.
PERKS_GUMP_WAIT_MS = 4000            # Ceiling on WaitForGump, NOT a sleep.
PERKS_GUMP_SETTLE_MS = 400           # One settle after it appears, before reading its lines.
PERKS_GUMP_EXPIRES_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*UTC$")
PERKS_GUMP_DURATION_PATTERN = re.compile(r"^(?:\d+\s*[dhms]\s*)+$", re.IGNORECASE)  # "9m 25s"
PERKS_GUMP_NON_LABELS = ("perk", "time left", "expires", "refresh", "close")
PERK_DEED_LABEL = "10% Less Break Chance Applying Rune Crafting Runes To Equipment"
                                # THE DEED ITEM'S OWN TOOLTIP TEXT, and that is now its only job
                                # (2026-09-16). find_perk_deed() matches it against the deed's
                                # Items.GetPropStringList(), which is what tells one deed type from
                                # another in the chest -- per the user, unchanged: "This does not
                                # affect the deeds, so using those won't change."
                                #
                                # It USED to also be looked up in the [perks output, and it was
                                # RIGHT -- "CONFIRMED live, verbatim, against a real [perks read
                                # while the deed was actually active". THE SHARD RENAMED THE PERK
                                # (2026-09-16); the old reading was not a mistake. Per the user,
                                # correcting me when I hedged on this: "i told you it changed, not
                                # that we had it wrong." Worth keeping straight -- a note that
                                # doubts its own confirmed observations is worse than no note.
# THE PACK'S OWN WEIGHT (owner, 2026-10-17: "We can just check for it, and otherwise work within the confines of the
# weight limit."): the perk is read, never required -- see weight_room(). The Active Perks window's own label, compared
# whole and lowercased like the one below.
IBW_PERK_LABEL = "infinite backpack weight"
PERK_ACTIVE_LABELS = (
    "better rune crafting",
    "10% less break chance applying rune crafting runes to equipment",
)                               # WHAT [perks PRINTS while the deed is up, lowercased. Confirmed
                                # 2026-09-16 from the Active Perks gump: "Better Rune Crafting |
                                # 2h 50m 12s | 2026-09-16 11:26:01 UTC". The old label is kept as
                                # an accepted alternative so a revert, or an older client, still
                                # works. Same tuple-of-candidates shape as
                                # STORAGE_FILL_CONTEXT_LABELS, for the same reason.
                                #
                                # FULL LABELS, NEVER SUBSTRINGS: that same gump shows "Better
                                # Loot" and "Better Gameplay Rewards", so a contains-test on
                                # "Better" would confirm the deed off an unrelated buff and let a
                                # batch grind at full break chance believing it was protected.
REQUIRED_INSCRIPTION_SKILL = 300.0

# How the gate's underlying [perks/skill state gets re-verified. Per the user: checking [perks
# fresh (a real ~2s network round trip) before EVERY single application was excessive once the
# deed's own expiration time is already known -- neither Inscription nor the deed's state changes
# that fast. PERKS_RECHECK_INTERVAL_SECONDS throttles how often the ACTUAL server check happens;
# the cached expiration is still compared against the current time on every single gate call
# (cheap, local, no network needed), so an actually-expired deed is still always caught
# immediately even between refreshes -- this is a throttle on re-VERIFYING, not a license to stop
# verifying. DEED_STOP_MARGIN_SECONDS ends the application loop proactively before the deed's
# known expiration, rather than reactively discovering it expired mid-cycle.
PERKS_RECHECK_INTERVAL_SECONDS = 300  # 5 minutes.
DEED_STOP_MARGIN_SECONDS = 60  # 1 minute.


# =============================================================================
# LOGGING
# =============================================================================

RUNECRAFT_DISK_ONLY = ("Crafted ", "Storage read: page", "Reagents come straight", "Crafting ", "Applying '",
                       "Done: crafted all")   # per-rune/per-batch mechanics: disk, not the journal (2026-09-24)
# ONE PROGRESS LINE A MINUTE (2026-09-30). The split above (owner, 2026-09-24: "The journal has way too much spam") left
# a long craft with nothing at all in the journal. At 02:15:43 that night disconnect_watchdog.ahk2 read four minutes of
# journal silence (its JOURNAL_STALL_SECONDS, 240) as a hung client and killed it 307 runes into a 491-rune craft, run
# by hand in General Play where nothing else was writing. The owner: "it used to do that, not sure why we stopped it".
# So a disk-only line still reaches the journal when nothing from this script has for RUNECRAFT_JOURNAL_PULSE_SECONDS
# -- the owner's progress line ("Crafted 120/491: Summ Rune"), and the watchdog's proof the client is alive.
RUNECRAFT_JOURNAL_PULSE_SECONDS = 60
_last_journal_line = [0.0]


# THE END SAYS WHY (2026-10-17: the run's last line read "did not finish (cancelled, stopped or halted)" -- a guess among
# three, when the line that stopped it had already said which). The last stop or warning line said is kept, and the end
# line repeats it.
LAST_STOP_SAID = [""]


def log(msg, hue=68):
    if hue == 33:
        LAST_STOP_SAID[0] = msg
    disk_log("--> " + msg)
    if msg.startswith(RUNECRAFT_DISK_ONLY) and time.time() - _last_journal_line[0] < RUNECRAFT_JOURNAL_PULSE_SECONDS:
        return
    _last_journal_line[0] = time.time()
    Misc.SendMessage("--> " + msg, hue)


# =============================================================================
# WORLD SAVE HANDLING -- CONFIRMED live: a periodic server-wide world save (journal: "The world
# is saving, please wait." ... "World save done in X.X seconds.") froze processing long enough
# mid-craft that craft_and_verify()'s own poll timeout ran out first, producing a FALSE "no new
# item appeared" safety stop even though the craft itself was fine, just delayed by the save.
# Every polling loop in this file that waits on a server-side action's result checks for this and
# waits it out WITHOUT counting that time against its own timeout, rather than needing a padded
# timeout to blindly cover a save that usually isn't even happening.
# =============================================================================

WORLD_SAVE_START_MESSAGE = "the world is saving"  # Lowercase substring match against journal text.
WORLD_SAVE_DONE_MESSAGE = "world save done"
WORLD_SAVE_MAX_WAIT_MS = 15000  # Ceiling for the save itself to finish -- CONFIRMED live one
                                  # real save took 3.3s; padded well above that single
                                  # observation since save duration presumably scales with server
                                  # population/content, not a fixed constant. Only matters if a
                                  # save is ALREADY detected in progress -- doesn't affect the
                                  # common case where no save is happening at all.
WORLD_SAVE_POLL_INTERVAL_MS = 250

def wait_out_world_save():
    """If a world save is currently in progress per the journal, waits for it to finish (up to
    WORLD_SAVE_MAX_WAIT_MS) and returns True. Returns False immediately (no wait) if no save is
    in progress. Meant to be called from inside another function's own poll loop, once per tick,
    right before that loop counts the tick against its own timeout -- so a save's multi-second
    freeze gets its own separate, dedicated wait instead of silently eating into (and likely
    exceeding) an unrelated timeout built for normal server response times."""
    journal_lines = Journal.GetJournalEntry(None) or []
    texts = [(jl.Text or "").lower() for jl in journal_lines]
    if not any(WORLD_SAVE_START_MESSAGE in t for t in texts):
        return False
    if any(WORLD_SAVE_DONE_MESSAGE in t for t in texts):
        return False  # Already finished by the time this was noticed.

    log("World save in progress -- waiting for it to finish...")
    waited_ms = 0
    while waited_ms < WORLD_SAVE_MAX_WAIT_MS:
        Misc.Pause(WORLD_SAVE_POLL_INTERVAL_MS)  # Raw Misc.Pause() deliberately, NOT safe_pause()
                                                    # -- this loop IS wait_out_world_save() itself;
                                                    # calling safe_pause() here would recurse.
        waited_ms += WORLD_SAVE_POLL_INTERVAL_MS
        journal_lines = Journal.GetJournalEntry(None) or []
        if any(WORLD_SAVE_DONE_MESSAGE in (jl.Text or "").lower() for jl in journal_lines):
            log("World save finished -- resuming.")
            return True
    log("Warning: world save didn't report done within {}ms -- resuming anyway.".format(
        WORLD_SAVE_MAX_WAIT_MS), 33)
    return True

def safe_pause(ms):
    """Drop-in replacement for Misc.Pause(ms), used EVERYWHERE in this file instead of the raw
    call (every other Misc.Pause( in this script was replaced with this, except the one inside
    wait_out_world_save() itself, which this wraps and would otherwise recurse into).

    ADDED (2026-08-27), per the user, after a live FATAL: buying a replacement Rune Chisel then
    immediately trying to reopen the Inscription Menu with it (recover_broken_chisel() ->
    open_inscription_menu()) failed outright because a world save was in progress right at that
    moment -- open_inscription_menu()'s own Items.UseItem()+fixed-Misc.Pause() sequence had no
    world-save awareness at all, unlike apply_rune_to_item()/craft_and_verify() which had each
    individually been hardened after their OWN separate live world-save incidents. Per the user:
    "More issues with world saving. We need a way to universally accommodate that" -- rather than
    keep bolting wait_out_world_save() onto one more call site every time a new one gets caught
    live, this makes world-save absorption the DEFAULT behavior of every single pause in the file,
    so a spot that's never been specifically caught yet is already covered.

    Pauses for `ms` first (a save that starts and finishes entirely within that window costs
    nothing extra beyond the check itself), THEN calls wait_out_world_save() -- which reads the
    journal for a save that's CURRENTLY in progress (whether it started before this call, during
    the ms pause, or is somehow still ongoing) and tacks its own full wait onto the end before
    returning. Does not change the CALLER's own polling/timeout bookkeeping (a caller with its own
    explicit `if wait_out_world_save(): continue` pattern around a poll loop still works exactly
    as before -- that check will simply find the save already resolved, a harmless no-op)."""
    Misc.Pause(ms)
    wait_out_world_save()


# =============================================================================
# ACCOUNT RUNEBOOK NAVIGATION -- ported from the same proven pattern already used in
# Harvest.py/Omni_Engine.py for "travel to a rune, then interact with what's
# there". Deliberately the simpler instant-recall variant (no gate/pet-follow complexity) --
# nothing about this trip needs a pet along.
# =============================================================================

AR_GUMPID = 0xc395adb4
AR_COMMAND = "[ar"
AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON = 5
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 500, 503, 504]
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
AR_GATE_OFFSET = 30000
AR_MAX_PAGES = 20
AR_GUMP_WAIT_MS = 5000
AR_FIND_MAX_ATTEMPTS = 3  # Same "reused gump caught mid-update" hardening already proven
                            # necessary elsewhere in this project for this exact gump.
KEY_GUMP_SETTLE_SECONDS = 1.5

def ar_gump_lines(gump_id, data_only=False):
    try:
        return Gumps.GetLineList(gump_id, data_only)
    except TypeError:
        return Gumps.GetLineList(gump_id)

def openAR():
    if Gumps.HasGump(AR_GUMPID):
        return True
    Player.ChatSay(0, AR_COMMAND)
    wait_for_gump_present(AR_GUMPID, AR_GUMP_WAIT_MS)
    safe_pause(250)
    return bool(Gumps.GetGumpRawLayout(AR_GUMPID))

def ar_get_buttons():
    if not openAR():
        return []
    layout = Gumps.GetGumpRawLayout(AR_GUMPID)
    if not layout:
        return []
    buttons = []
    for piece in re.split(r"\}\s*\{", str(layout)):
        if "button" in piece.lower():
            data = re.findall(r"\d+", piece)
            if data:
                buttons.append(int(data[-1]))
    return buttons

def ar_page_info():
    lines = ar_gump_lines(AR_GUMPID) or []
    for line in reversed(list(lines)):
        found = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", line, re.I)
        if found:
            return int(found.group(1)), int(found.group(2))
    return (1, 1)

def ar_parse_page():
    if not openAR():
        return {}, {}
    lines = ar_gump_lines(AR_GUMPID) or []
    buttons = ar_get_buttons()
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
                entries[-1]["coord"] = [int(x) for x in re.findall(r"[-+]?\d+", text)]
            continue
        found = re.match(r"^(\d+)\.\s*(.+)$", text)
        if found:
            entries.append({"index": int(found.group(1)), "label": found.group(2).strip(), "coord": None})
    # Discards this page's read entirely on a mismatch rather than risk a wrong pairing --
    # same fix already proven necessary in Omni_Engine.py's own ar_parse_page().
    if len(entries) != len(entry_buttons):
        return {}, {}
    folders = {}
    destinations = {}
    for entry, button in zip(entries, entry_buttons):
        is_dest = (entry["coord"] is not None or (button + AR_GATE_OFFSET) in buttons)
        if is_dest:
            destinations[button] = {"name": entry["label"], "coord": entry["coord"]}
        else:
            folders[button] = entry["label"]
    return folders, destinations

def ar_page_step(button):
    if button not in ar_get_buttons():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    wait_for_gump_present(AR_GUMPID, AR_GUMP_WAIT_MS)
    safe_pause(250)
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

def ar_iter_pages():
    if not openAR():
        return
    if not ar_goto_page(1):
        log("Warning: could not rewind the Account Runebook to page 1.", 33)
    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        folders, destinations = ar_parse_page()
        yield current, folders, destinations
        if current >= total:
            return
        if not ar_next_page():
            return
        moved, _total = ar_page_info()
        if moved <= current:
            return

def ar_find(target, want_dest):
    wanted = (target or "").strip().lower()
    if not wanted:
        return None
    for attempt in range(AR_FIND_MAX_ATTEMPTS):
        exact = None
        partial = None
        for page, folders, destinations in ar_iter_pages():
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
        result = exact or partial
        if result is not None:
            return result
        if attempt + 1 < AR_FIND_MAX_ATTEMPTS:
            safe_pause(int(KEY_GUMP_SETTLE_SECONDS * 1000))
    return None

def ar_go_dir(folder_name=None):
    if folder_name is None:
        if AR_ROOT_BUTTON in ar_get_buttons():
            safe_pause(250)
            Gumps.SendAction(AR_GUMPID, AR_ROOT_BUTTON)
            wait_for_gump_present(AR_GUMPID, AR_GUMP_WAIT_MS)
            safe_pause(250)
        return True
    if not openAR():
        log("Warning: could not open the Account Runebook.", 33)
        return False
    hit = ar_find(folder_name, want_dest=False)
    if hit is None:
        log("Warning: Account Runebook folder '{}' not found on any page.".format(folder_name), 33)
        return False
    page, button, name = hit
    if not ar_goto_page(page):
        log("Warning: found '{}' on page {} but could not get back to it.".format(name, page), 33)
        return False
    safe_pause(250)
    Gumps.SendAction(AR_GUMPID, button)
    wait_for_gump_present(AR_GUMPID, AR_GUMP_WAIT_MS)
    safe_pause(250)
    return True

def ar_go_folders(folders):
    ar_go_dir()
    for folder in folders:
        if folder == '':
            continue
        if not ar_go_dir(folder):
            return False
    return True

def ar_go_dest(dest_name):
    """Instant recall (no gate) to a named rune -- no pet involved in this trip, so the simpler,
    mana/reagent-free variant is all that's needed here."""
    if not dest_name:
        return False
    if not openAR():
        return False
    hit = ar_find(dest_name, want_dest=True)
    if hit is None:
        log("Warning: Account Runebook rune '{}' not found on any page.".format(dest_name), 33)
        return False
    page, button, name = hit
    if not ar_goto_page(page):
        log("Warning: found rune '{}' on page {} but could not get back to it.".format(name, page), 33)
        return False
    Gumps.SendAction(AR_GUMPID, button)
    safe_pause(1000)
    return True


# =============================================================================
# GUMP INTERACTION -- per the user's own standing direction: never rely on Gumps.CurrentGump()/
# LastGump* for new code (both proven unreliable live, twice, on two different real gumps this
# project touched). Always find by content via AllGumpIDs(), then act using that explicit id.
# =============================================================================

def extract_buttons(layout):
    buttons = []
    if not layout:
        return buttons
    for piece in re.split(r"\}\s*\{", str(layout)):
        if "button" in piece.lower():
            data = re.findall(r"\d+", piece)
            if data:
                buttons.append(int(data[-1]))
    return buttons

def find_gump_by_content(match_fn):
    """match_fn(lines, layout) -- both the data_only line list AND the raw layout are passed
    (2026-08-27 -- previously lines only) so a matcher can verify STRUCTURE (e.g. specific button
    art), not just text content. See is_inscription_menu()'s own docstring for why this mattered:
    a text-only match was too loose and could pick up a completely unrelated gump."""
    ids = Gumps.AllGumpIDs()
    if not ids:
        return None
    for gid in ids:
        try:
            lines = Gumps.GetLineList(gid, True) or []
        except Exception:
            continue
        try:
            layout = Gumps.GetGumpRawLayout(gid)
        except Exception:
            layout = None
        if match_fn(lines, layout):
            return gid
    return None

def read_gump(gump_id):
    lines = Gumps.GetLineList(gump_id, True) or []
    layout = Gumps.GetGumpRawLayout(gump_id)
    buttons = extract_buttons(layout)
    return lines, layout, buttons

def find_button_for_line(lines, layout, target_text):
    """Finds target_text's line index, then pairs it with the raw layout's matching `text`
    element (by textID) and the `button` element on the same row -- CONFIRMED live across
    multiple different properties (SDI -> 72, Self Repair -> 261) that this dynamic resolution
    matches hand-derived values exactly, so it's trustworthy, not just lucky once. Never
    hardcode a button number for a property -- always resolve it fresh, every time."""
    line_index = None
    for i, line in enumerate(lines):
        if (line or "").strip().lower() == target_text.strip().lower():
            line_index = i
            break
    if line_index is None:
        return None, None
    pairs = re.findall(
        r'\{\s*button\s+\d+\s+\d+\s+4005\s+4007\s+1\s+0\s+(\d+)\s*\}\s*\{\s*text\s+\d+\s+\d+\s+\d+\s+(\d+)\s*\}',
        str(layout))
    for select_btn, text_id in pairs:
        if int(text_id) == line_index:
            return line_index, int(select_btn)
    return line_index, None

INSCRIPTION_MENU_BUTTON_ART_PATTERN = re.compile(r'\{\s*button\s+\d+\s+\d+\s+4005\s+4007\s+')

# THE CRAFT-MENU CHROME, which is what actually identifies this gump (2026-09-15). Both headers
# live on PAGE 0 of the layout, so they are present with a category selected, with a different one
# selected, and with none selected at all -- unlike anything GetLineList() can see, which is only
# ever the selections themselves. Confirmed against the raw layout in the 2026-09-11 dump
# (OmniData/ScratchTest_ChiselMenu.txt):
#     { xmfhtmlgumpcolor  10 37 200 22 1044010 0 0 32767 }   CATEGORIES
#     { xmfhtmlgumpcolor 215 37 305 22 1044011 0 0 32767 }   SELECTIONS
# Four coordinate numbers, then the cliloc -- matched positionally rather than by a bare number
# search so an unrelated gump cannot match on a coincidental integer somewhere in its layout.
INSCRIPTION_MENU_CATEGORIES_PATTERN = re.compile(
    r'\{\s*xmfhtmlgumpcolor(?:\s+\d+){4}\s+1044010\b')
INSCRIPTION_MENU_SELECTIONS_PATTERN = re.compile(
    r'\{\s*xmfhtmlgumpcolor(?:\s+\d+){4}\s+1044011\b')

def is_inscription_menu(lines, layout):
    """The Inscription Menu specifically -- CONFIRMED live via a ScratchTest.py gump dump this
    was NOT sufficient before: "any non-empty gump that isn't Daily Tasks" is too loose and
    accidentally matched a completely unrelated gump also open at the time (a "Champion of the
    Peerless II" achievement-tracker gump, zero buttons of its own). extract_buttons() then
    correctly found nothing on THAT gump's layout, and switch_inscription_category() reported
    "category button 1 not found" for a totally different reason than either "stale gump" or
    "wrong button ID" (both already ruled out) -- it was reading the wrong gump entirely.

    Now requires the layout to contain at least one button using the Inscription Menu's own
    proven button art (4005/4007 -- the exact signature find_button_for_line() already hardcodes
    for its own row-button regex, confirmed present on every category/page seen so far), in
    addition to not being Daily Tasks. Structural, not text-based -- survives category-list
    content changes (a new category appearing, existing ones being renamed) the same way the old
    check intended to, without the false-positive risk that check actually had.

    A NON-EMPTY LINE LIST IS NO LONGER REQUIRED (2026-09-15) -- that leftover cost a whole run.
    `if not lines: return False` survived the 2026-08-27 rewrite above from the ORIGINAL text-based
    matcher, keeping a text precondition on a check whose entire purpose was to stop depending on
    text. GetLineList() returns the gump's text array, and the 2026-09-11 dump proves the array
    holds the SELECTIONS and nothing else -- all chrome (CATEGORIES, SELECTIONS, LAST TEN,
    Enhancement, EXIT) is drawn with xmfhtmlgumpcolor clilocs that never enter it. So a menu with
    NO CATEGORY PICKED has an empty array, and an open, healthy Inscription Menu read as "not the
    Inscription Menu" simply because nothing had been chosen in it yet.

    That is exactly the state a FRESHLY BOUGHT CHISEL opens in, and it killed a live run:
    "Bought a Rune Chisel for 18200 gold" at 23:56:03, then three failed opens and a FATAL by
    23:56:14, with the menu on screen throughout. Per the user: "We're never clicking enhancement
    when needed ... on a newly purchased chisel it requires selecting enhancement to access the
    rune list." The Enhancement click was already there; it just sits after this function, which
    never returned a gump for it to act on.

    THE REPLACEMENT IS TIGHTER, NOT LOOSER: the CATEGORIES and SELECTIONS headers are required as
    well, both on page 0 and therefore present under every category and under none. The old
    button-art test passed on the 4005/4007 arrows alone, which many gumps share -- that breadth is
    how the Peerless gump nearly matched. See INSCRIPTION_MENU_CATEGORIES_PATTERN for why those two
    clilocs, and for the next tightening (1116349, Enhancement's own label) if a craft menu from
    some other trade ever manages to be open at the same time."""
    joined = " ".join((l or "") for l in (lines or [])).lower()
    if "daily tasks" in joined:
        return False
    raw = str(layout or "")
    if not INSCRIPTION_MENU_BUTTON_ART_PATTERN.search(raw):
        return False
    return bool(INSCRIPTION_MENU_CATEGORIES_PATTERN.search(raw)
                and INSCRIPTION_MENU_SELECTIONS_PATTERN.search(raw))


# =============================================================================
# VENDOR / RUNE CHISEL
# =============================================================================

def find_scribe():
    fil = Mobiles.Filter()
    fil.Enabled = True
    fil.RangeMax = VENDOR_SEARCH_RANGE
    for mob in (Mobiles.ApplyFilter(fil) or []):
        # THE PROPERTY LIST IS THE AUTHORITY (2026-09-16). The Mobile Inspector shows "Scribe" as
        # an Attributes entry, so that is the vendor title and the thing worth trusting. Asked
        # FIRST, reversing the old order: that order was right when the term was a name, but
        # Mobiles.Filter() returns players as well, and a player's name is player-chosen -- so a
        # name containing "scribe" must not be able to outrank a real vendor title.
        try:
            Mobiles.WaitForProps(mob, 1000)
            props = " ".join(p for p in (Mobiles.GetPropStringList(mob) or []) if p).lower()
        except Exception:
            props = ""
        if SCRIBE_TITLE_MATCH in props:
            return mob
        # FALLBACK for a scribe whose NAME carries the title ("... the Scribe") and whose props
        # did not load in time. Costs nothing and cannot override the check above.
        if SCRIBE_TITLE_MATCH in (mob.Name or "").lower():
            return mob
    return None

# WHAT THE LAST SCAN SAW (2026-09-16), per the user: "we'll need to scan and then close rune
# storage on startup i guess." {key name lower: {row name lower: balance}}.
#
# WHY IT EXISTS: storage_balances() below opens the shared 0x6abce12 gump, parses it and closes it.
# The Apply Preview cannot pay that -- it is itself drawing a gump, and estimate_apply_odds() runs
# 200 whole-batch trials behind it. So the reading is taken once at startup and kept here.
#
# FILLED AT THE SINGLE PARSE POINT, so it cannot drift from the live read: every caller of
# storage_balances() refreshes it, which means the craft path's authoritative gate, every
# withdrawal and the closing absorb all keep it current at no extra cost.
STORAGE_BALANCE_CACHE = {}
STORAGE_BALANCE_SCANNED_AT = {}   # {key name lower: epoch} -- reported, never used for logic


# A STACKED ITEM'S NAME CARRIES ITS COUNT (2026-09-16). Confirmed by the shard itself in the
# 00:44 safety stop: "expected a name starting with 'in', got '3 In Rune' ... Amount=3". Once
# runes started stacking, every exact/prefix name test in this file began failing on its own
# output. No rune or material name legitimately begins with a digit, so a leading count is always
# the stack prefix.
STACK_COUNT_PREFIX = re.compile(r"^\s*\d+\s+")


def bare_item_name(item):
    """An item's Name with any leading stack count stripped: "3 In Rune" -> "In Rune".

    THE ONE DEFINITION. count_runes(), find_blank_runes() and the post-craft safety check each
    compared a raw Name and each broke the same way; three separate strippings would have been
    three chances to disagree about what a name is."""
    return STACK_COUNT_PREFIX.sub("", (getattr(item, "Name", "") or "").strip())


def total_amount(items):
    """How many actual runes/materials a list of items represents -- the sum of Amount, not the
    length of the list.

    len() WAS THE SECOND HALF OF THE STACKING BUG (2026-09-16). Eleven callers asked "how many
    have I got" by taking len() of count_runes() or of find_blank_runes(). A pile of 3 is ONE item,
    so
    even once the names matched again, every one of them would have read 1 -- an undercount that
    makes the batch keep crafting runes it already owns. Amount is absent or 0 on some item reads,
    so a missing value counts as the one item it plainly is."""
    total = 0
    for it in items or []:
        try:
            total += int(getattr(it, "Amount", 1) or 1)
        except (TypeError, ValueError):
            total += 1
    return total


def cached_storage_balance(key_name, row_name):
    """That row's balance as of the last scan, or 0 if this key has never been read.

    0 ON A MISS, NOT None. An unscanned storage must leave every caller reading exactly what it
    read before this cache existed (the backpack alone) rather than having to branch on None."""
    rows = STORAGE_BALANCE_CACHE.get((key_name or "").strip().lower())
    if not rows:
        return 0
    try:
        return int(rows.get((row_name or "").strip().lower(), 0) or 0)
    except (TypeError, ValueError):
        return 0


def available_rough_stone():
    """Rough Stone this batch can actually reach: the pack PLUS the storage.

    THE ONE DEFINITION (2026-09-16). Four sites counted the pack alone and so read a stocked
    storage as empty -- the preview's "(0 on hand)", the odds' 0%, select_apply_bases() and the
    "Luck -> 0 instead of 20" suggestion, all in one screenshot. Per the user, the storage stock
    counts and "they don't need withdrawn"."""
    return (count_material(ROUGH_STONE_NAME)
            + cached_storage_balance(RUNECRAFTING_STORAGE_NAME, ROUGH_STONE_NAME))


def available_blank_runes():
    """Blank Runes this batch can reach: the pack PLUS the storage. Counterpart to
    available_rough_stone(); the simulation drains blanks before stone, so an under-counted blank
    pool shortens every trial exactly the same way."""
    return (count_blank_rune_amount()
            + cached_storage_balance(RUNECRAFTING_STORAGE_NAME, BLANK_RUNE_LINE_TEXT))


def scan_runecrafting_storage():
    """Open the Runecrafting Storage once, read every row, close it. True if anything was read.

    THE STARTUP SCAN the user asked for. storage_balances() does the opening, parsing and closing
    (in a finally) and fills STORAGE_BALANCE_CACHE on the way through, so this is a thin wrapper
    whose only real job is to report what was found -- a silent scan would leave a later "(0 on
    hand)" ambiguous between "the storage is empty" and "the scan never happened".

    FAIL-SOFT. A missing key or a refused gump logs and returns False; the cache stays empty and
    every consumer falls back to the backpack-only count it used before."""
    balances = storage_balances(RUNECRAFTING_STORAGE_NAME)
    if balances is None:
        log("Could not scan {} at startup -- estimates will count the backpack only."
            .format(RUNECRAFTING_STORAGE_NAME), 33)
        return False
    log("Scanned {}: {} Rough Stone, {} Blank Rune(s) in storage (plus {} and {} in the pack)."
        .format(RUNECRAFTING_STORAGE_NAME,
                cached_storage_balance(RUNECRAFTING_STORAGE_NAME, ROUGH_STONE_NAME),
                cached_storage_balance(RUNECRAFTING_STORAGE_NAME, BLANK_RUNE_LINE_TEXT),
                count_material(ROUGH_STONE_NAME), count_blank_rune_amount()))
    return True


# "Uses Remaining" IS THE CHISEL'S CHARGE LINE, measured live (26 / 35 / 66 on freshly bought
# chisels). Unreadable means 0 here, which makes every caller fall back to the stored-only figure
# it used before -- never an invented number.
CHISEL_USES_PATTERN = re.compile(r"uses remaining[:\s]+(\d+)")


def carried_chisel_charges():
    """Charges on the Rune Chisel in the backpack, or 0 if there is none or it cannot be read."""
    chisel = find_rune_chisel()
    if chisel is None:
        return 0
    try:
        Items.WaitForProps(chisel, 1000)
        props = Items.GetPropStringList(chisel) or []
    except Exception:
        return 0
    for p in props:
        m = CHISEL_USES_PATTERN.search((p or "").lower())
        if m:
            try:
                return int(m.group(1))
            except (TypeError, ValueError):
                return 0
    return 0


def available_chisel_charges():
    """Every charge we own: the stored row PLUS the chisel in the pack. None if the row is
    unreadable.

    THE BUG THIS EXISTS FOR (2026-09-16). withdraw_chisel_from_storage() empties the stored row
    into a single carried chisel on purpose -- "Withdrew 60000 'Rune Chisel' (55641 -> 0 left)".
    Nine seconds later the restock check read that row, saw the 0 we had just created, and
    travelled to the Scribe with 55,641 charges in the backpack. Charges in the pack are charges
    we own: the closing absorb puts them straight back."""
    stored = storage_balance(RUNECRAFTING_STORAGE_NAME, CHISEL_STORAGE_ROW)
    if stored is None:
        return None
    return stored + carried_chisel_charges()


def stored_rune_row(property_def):
    """The Runecrafting Storage row holding finished runes for this property, or None.

    BY SYLLABLE PLUS HYPHEN. Rows read "<Syllable>-<Stat>" -- "In-Luck", "Cah-MageArmor",
    "Corp-SDI" -- and the stat half is abbreviated in ways the property labels do not share, so it
    cannot be derived from property_def["label"]. The syllable can, and the hyphen is what keeps it
    unambiguous: "bal-" matches Bal-LeechStam and not Bala-Balance, "flam-" matches
    Flam-ResistFire and not Flamus-FireArea.

    Reads the CACHE, not the gump -- the startup scan already paid for this."""
    syllable = (property_def.get("syllable") or "").strip().lower()
    if not syllable:
        return None
    prefix = syllable + "-"
    rows = STORAGE_BALANCE_CACHE.get(RUNECRAFTING_STORAGE_NAME.strip().lower()) or {}
    for row in rows:
        if row.startswith(prefix):
            return row
    return None


def stored_rune_count(property_def):
    """Finished runes for this property sitting in the Runecrafting Storage, as of the last scan."""
    row = stored_rune_row(property_def)
    if row is None:
        return 0
    return cached_storage_balance(RUNECRAFTING_STORAGE_NAME, row)


def available_rune_amount(property_def):
    """Finished runes this batch can reach: the pack PLUS the Runecrafting Storage, as of the last scan.

    THE ONE DEFINITION FOR PLANNING (2026-09-24 20:4x, owner: "is the rough stone needed here taking already
    crafted runes into account? it should be."). The preview, the odds entries, the working-set sizing and the
    dump estimates counted the pack alone, so the runes the exit absorb had just filed into storage were priced
    as if they had to be crafted again (5755 stone "needed" on a Weapon screen). The apply flow already pulls
    them back out (withdraw_runes_from_storage) before it crafts, so counting them here matches what it does.
    Arrival detection (count_rune_amount before/after a craft) stays pack-only on purpose."""
    return count_rune_amount(property_def) + stored_rune_count(property_def)


def withdraw_runes_from_storage(property_def, wanted):
    """Pull up to `wanted` finished runes for this property out of the storage. Returns how many
    actually arrived in the backpack.

    COUNTING STORAGE STOCK WOULD NOT HAVE BEEN ENOUGH (2026-09-16). A rune has to be in the pack
    to be applied, so treating stored stock as "finished" without pulling it would have skipped
    the craft and then failed at the apply -- one bug for another. Per the user: "we can obviously
    pull the various runes from here if we already have them."

    MEASURED, NOT ASSUMED. The return value is a before/after count of the backpack, not whatever
    the withdrawal reported -- the same rule withdraw_chisel_from_storage() already follows ("what
    this function owes its caller is a chisel in the backpack, so that is what it returns")."""
    if wanted <= 0:
        return 0
    row = stored_rune_row(property_def)
    if row is None:
        return 0
    stored = cached_storage_balance(RUNECRAFTING_STORAGE_NAME, row)
    if stored <= 0:
        return 0
    # THE WHOLE ROW, NOT A COMPUTED SLICE (2026-09-16). This asked for min(wanted, stored), where
    # `wanted` came from estimate_applications_needed() -- an estimate against random breakage,
    # i.e. the least reliable number in the flow, and every rune it left behind is one the
    # mid-batch top-up has to pay another gump cycle to come back for. Runes stack and the closing
    # absorb returns the remainder, so pulling everything costs one pack slot.
    before = count_rune_amount(property_def)
    amount = RUNE_WITHDRAW_AMOUNT
    room = weight_room()
    if room is not None:                 # THE PULL FITS THE PACK
        amount = min(stored, wanted, max(0, room) // RUNE_STONES_EACH)
        if amount <= 0:
            log("Not pulling '{}' runes out of {}: {}.".format(
                property_def["label"], RUNECRAFTING_STORAGE_NAME, weight_stop_line("one more rune")), 33)
            return 0
        log("Pulling {} '{}' rune(s) out of {} (row '{}' holds {}) instead of crafting them -- what the stat "
            "needs, within the pack's weight.".format(amount, property_def["label"], RUNECRAFTING_STORAGE_NAME,
                                                       row, stored))
    else:
        log("Pulling every '{}' rune out of {} (row '{}' holds {}) instead of crafting them."
            .format(property_def["label"], RUNECRAFTING_STORAGE_NAME, row, stored))
    if not withdraw_from_storage_key(RUNECRAFTING_STORAGE_NAME, row, amount):
        # ORDINARY HUE (2026-09-16). Running the row dry is the expected end of a long batch, and
        # crafting is the designed fallback -- withdraw_from_storage_key() has already said which
        # of the two happened, and reserves red for a row that HAD a balance and still did not
        # move. That one is a real surprise; this is not.
        log("Nothing withdrawn from {} for '{}' -- crafting instead."
            .format(RUNECRAFTING_STORAGE_NAME, row))
        return 0
    safe_pause(GUMP_RESPONSE_SETTLE_MS)
    arrived = count_rune_amount(property_def) - before
    if arrived <= 0:
        log("Warning: the '{}' row reported a withdrawal but no rune reached the backpack."
            .format(row), 33)
        return 0
    log("Pulled {} '{}' rune(s) from storage -- {} in the pack now."
        .format(arrived, property_def["label"], before + arrived))
    return arrived


def count_rune_amount(property_def):
    """How many finished runes for this property are in the backpack, counting stacks properly."""
    return total_amount(count_runes(property_def))


def count_blank_rune_amount():
    """How many Blank Runes are in the backpack, counting stacks properly."""
    return total_amount(find_blank_runes())


def storage_layout_button_ids(layout):
    """Every button id in the storage gump's current raw layout (the same pattern the row resolver uses)."""
    return set(int(bid) for _x, _y, bid in STORAGE_BUTTON_PATTERN.findall(str(layout or "")))


def storage_text_pieces(layout):
    """(string index, x, y, hue or None) for every text, croppedtext and htmlgump element, in the order the layout
    draws them -- the order of RazorEnhanced's data-only line list, ONE LINE PER PIECE (see storage_gump_strings())."""
    out = []
    for m in STORAGE_ELEMENT_PATTERN.finditer(str(layout or "")):
        el = "{" + m.group(1) + "}"
        t = STORAGE_TEXT_PATTERN.match(el) or STORAGE_CROPPED_TEXT_PATTERN.match(el)
        if t:
            out.append((int(t.group(4)), int(t.group(1)), int(t.group(2)), int(t.group(3))))
            continue
        h = STORAGE_HTML_PATTERN.match(el)
        if h:
            out.append((int(h.group(3)), int(h.group(1)), int(h.group(2)), None))
    return out


_storage_unmapped_logged = [False]


def storage_gump_strings(lines, layout):
    """{string index: its text} for the texts RazorEnhanced reads TRUE, or None when its list does not line up.

    WHAT Gumps.GetLineList(id, True) IS (measured 2026-10-01 by Omni_Bioengineering.py on the Lab, Reagent, Tool and
    Rune keys, two craft menus and the Lab's DNA page). ONE LINE PER TEXT PIECE -- text, croppedtext, htmlgump -- in
    layout order: a text entry's own string (the 'Withdrawal Amount' box) is never in it, so line k belongs to the k-th
    piece, not to string index k, and every string index past the box is one line early. Reading the list BY STRING
    INDEX ran off its end at 'Fill from backpack' on every one-page key ("Index was out of range" -- a .NET
    ArgumentOutOfRangeException, which IronPython does NOT catch as IndexError, so the whole read failed). And
    RazorEnhanced DROPS EVERY EMPTY STRING before resolving those lines, so each text past an empty one reads as a
    later string; the empty ones are text entries, so only the texts BEFORE the first text entry's string are
    returned -- every row, the title and 'Next Page'. The footer is never needed."""
    pieces = storage_text_pieces(layout)
    if len(pieces) != len(lines):
        if not _storage_unmapped_logged[0]:
            _storage_unmapped_logged[0] = True
            log("Warning: a storage window's text list ({} lines) does not line up with its layout ({} texts) -- "
                "its page links are not read.".format(len(lines), len(pieces)), 33)
        return None
    entries = [int(i) for i in STORAGE_TEXTENTRY_PATTERN.findall(str(layout or ""))]
    first_entry = min(entries) if entries else None
    return dict((p[0], lines[k]) for k, p in enumerate(pieces) if first_entry is None or p[0] < first_entry)


def storage_next_page_button(layout, lines):
    """The Next Page button id resolved from the OPEN gump's own layout, or None when this page has no
    'Next Page' text (the last page). Geometry, like storage_row_buttons(): the button-family token on the
    same line as the 'Next Page' text and to its right, nearest first (2026-09-19 -- id 101 was the Peerless
    storage's and this key does not present it that way). The text is looked up through storage_gump_strings()
    (2026-10-01): reading the line list by string index threw on every one-page key."""
    text = str(layout or "")
    strings = storage_gump_strings(lines, text) or {}
    target = None
    for sx, sy, _hue, idx in STORAGE_TEXT_PATTERN.findall(text):
        if (strings.get(int(idx)) or "").strip().lower() == "next page":
            target = (int(sx), int(sy))
            break
    if target is None:
        return None
    tx, ty = target
    best = None
    for bx, by, bid in STORAGE_ANY_BUTTON_PATTERN.findall(text):
        bx, by, bid = int(bx), int(by), int(bid)
        if abs(by - ty) > STORAGE_ROW_BUTTON_Y_TOL or bx <= tx:
            continue
        if best is None or bx - tx < best[0]:
            best = (bx - tx, bid)
    return best[1] if best else None


def storage_turn_page():
    """Advance the OPEN storage gump one page. False when this is the last page (no 'Next Page' text with a
    button beside it) -- never presses blindly. The id comes from the layout each time."""
    button = storage_next_page_button(Gumps.GetGumpRawLayout(STORAGE_GUMP_ID),
                                      Gumps.GetLineList(STORAGE_GUMP_ID, True) or [])
    if button is None:
        return False
    Gumps.SendAdvancedAction(STORAGE_GUMP_ID, button, [], [0], ["1"])
    wait_and_settle_storage()
    return True


def storage_read_all_pages():
    """(name, balance, line_index) for every row on EVERY page of the OPEN storage gump, first page first.
    TWO PAGES SINCE 2026-09 (2026-09-19): the rune rows added on 09-11 pushed the Runecrafting Storage past
    one page, and a single GetLineList() read only ever saw the page the gump opened on -- Sar's 1,170 runes
    sat unread on page 2 while the run crafted 1,342 more. Same loop shape as the Tamer's
    peerless_storage_read_all_stock() on this gump."""
    rows = []
    seen = set()
    for _page in range(STORAGE_MAX_PAGES):
        page_rows = parse_storage_rows(Gumps.GetLineList(STORAGE_GUMP_ID, True) or [])
        new = [r for r in page_rows if r[0].strip().lower() not in seen]
        for r in new:
            seen.add(r[0].strip().lower())
        rows.extend(new)
        _next_id = storage_next_page_button(Gumps.GetGumpRawLayout(STORAGE_GUMP_ID),
                                            Gumps.GetLineList(STORAGE_GUMP_ID, True) or [])
        _has_next = _next_id is not None
        # WHAT TO CHECK (2026-09-19): one line per page. Two pages with Sar on the second is the expected
        # shape today; a single page with no Next Page button means the button id is not 101 on this key.
        log("Storage read: page {} -- {} row(s), {} new; Next Page button {}.".format(
            _page + 1, len(page_rows), len(new),
            ("id %d (resolved beside its text)" % _next_id) if _has_next else "absent (last page)"))
        if not new or not storage_turn_page():
            break
    return rows


def find_master_keys_item():
    """The Master Keys item at the top level of the backpack, by name + graphic, or None."""
    want = normalize_apostrophes(MASTER_KEYS_NAME.lower())
    try:
        for it in container_items(Player.Backpack):
            if it.ItemID != MASTER_KEYS_ITEM_ID:
                continue
            name = normalize_apostrophes((it.Name or "").strip().lower())
            if not name:
                Items.WaitForProps(it, REQUIRED_ITEM_PROPS_WAIT_MS)
                name = normalize_apostrophes((it.Name or "").strip().lower())
            if name == want or "master key" in name:
                return it
    except Exception:
        pass
    return None


def master_keys_read_rows(close_after):
    """Open the Master Keys gump and read {row text (lower): OPEN button id}. A row is a text cell with a
    button in the OPEN column MASTER_KEYS_ROW_Y_OFFSET px above it -- paired by geometry, never by
    counting (the first row's text read '5993' in the capture). Leaves the gump open unless close_after, so
    a caller can press a row. None when the item is absent or the gump did not open. Caches the rows."""
    global _master_keys_rows_logged
    master = find_master_keys_item()
    if master is None:
        return None
    Items.UseItem(master.Serial)
    safe_pause(PRE_WAIT_SETTLE_MS)
    if wait_for_gump_present(MASTER_KEYS_GUMP_ID, KEY_CONTEXT_WAIT_MS) is None:
        log("Warning: the {} window did not open.".format(MASTER_KEYS_NAME), 33)
        return None
    safe_pause(GUMP_RESPONSE_SETTLE_MS)
    try:
        lines = [str(l) for l in (Gumps.GetLineList(MASTER_KEYS_GUMP_ID, False) or [])]
        layout = str(Gumps.GetGumpRawLayout(MASTER_KEYS_GUMP_ID) or "")
    except Exception as _err:
        log("Warning: could not read the {} window ({}).".format(MASTER_KEYS_NAME, _err), 33)
        lines, layout = [], ""
    buttons = [(int(x), int(y), int(bid)) for x, y, bid in STORAGE_BUTTON_PATTERN.findall(layout)]
    rows = {}
    for sx, sy, _hue, idx in STORAGE_TEXT_PATTERN.findall(layout):
        idx = int(idx)
        if idx >= len(lines):
            continue
        text = (lines[idx] or "").strip().lower()
        if not text:
            continue
        ty = int(sy)
        for bx, by, bid in buttons:
            if bx == MASTER_KEYS_OPEN_BUTTON_X and abs((ty - MASTER_KEYS_ROW_Y_OFFSET) - by) <= MASTER_KEYS_ROW_Y_TOL:
                rows[text] = bid
                break
    if rows:
        MASTER_KEYS_ROWS_CACHE.clear()
        MASTER_KEYS_ROWS_CACHE.update(rows)
        if not _master_keys_rows_logged:
            _master_keys_rows_logged = True
            log("{} holds: {}.".format(MASTER_KEYS_NAME, ", ".join(sorted(rows))))
    if close_after:
        try:
            Gumps.SendAction(MASTER_KEYS_GUMP_ID, 0)
        except Exception:
            pass
    return rows


def master_keys_row_for(key_name, rows):
    """(row text, OPEN button id) for key_name among rows, or (None, None): the row whose text IS the key's
    name first, else the first row containing one of MASTER_KEYS_ROW_HINTS[key_name]."""
    if not rows:
        return None, None
    want = normalize_apostrophes((key_name or "").strip().lower())
    if want in rows:
        return want, rows[want]
    for hint in MASTER_KEYS_ROW_HINTS.get(key_name, ()):
        for text in sorted(rows):
            if hint in text:
                return text, rows[text]
    return None, None


def key_is_in_master(key_name):
    """True when the key is not loose in the backpack but the Master Keys gump has a row for it. Reads the
    gump once per run (the cache answers after that)."""
    if find_master_keys_item() is None:
        return False
    rows = MASTER_KEYS_ROWS_CACHE or master_keys_read_rows(close_after=True)
    if rows is None:
        return None      # (2026-09-24 20:3x) the window did not open: NOT CHECKED, which is not the same as absent
    text, _bid = master_keys_row_for(key_name, rows)
    return text is not None


def open_storage_key(key_name):
    """THE ONE OPEN POINT (2026-09-22): use the key itself when it is loose in the backpack, else open it
    from the Master Keys gump (its row's OPEN button). The caller waits for the key's own STORAGE_GUMP_ID
    afterwards exactly as before. False when neither way is available."""
    serial = RESOLVED_REQUIRED_ITEMS.get(key_name)
    if not serial:
        for spec in REQUIRED_BACKPACK_ITEMS:
            if spec["name"] == key_name:
                it, status = find_required_backpack_item(spec)
                if status == "ok":
                    RESOLVED_REQUIRED_ITEMS[key_name] = it.Serial
                    serial = it.Serial
                break
    if serial:
        call_hook("item_action")   # the key is an item action too (2026-09-24): a script beside us settles against it
        Items.UseItem(serial)
        return True
    rows = master_keys_read_rows(close_after=False)
    if rows is None:
        log("'{}' is not in the backpack and there is no {} to open it from.".format(key_name, MASTER_KEYS_NAME), 33)
        return False
    text, bid = master_keys_row_for(key_name, rows)
    if bid is None:
        log("'{}' is not in the backpack and the {} window has no row for it (rows: {}).".format(
            key_name, MASTER_KEYS_NAME, ", ".join(sorted(rows))), 33)
        try:
            Gumps.SendAction(MASTER_KEYS_GUMP_ID, 0)
        except Exception:
            pass
        return False
    Gumps.SendAction(MASTER_KEYS_GUMP_ID, bid)
    return True


def storage_balances(key_name):
    """{lowercased row name: balance} for every row in that key, or None if unreadable.

    ONE OPEN FOR ALL ROWS (2026-09-15). The craft planner needs Rough Stone AND Blank Rune,
    and opening the storage twice would cost two full gump cycles on the shared 0x6abce12
    gump for one question. storage_balance() is a thin wrapper over this, so the two cannot
    drift apart on how the gump is parsed.

    READ-ONLY: opens, parses, closes in a finally. Never clicks a row button."""
    try:
        if not open_storage_key(key_name):   # loose in the pack, or via the Master Keys gump (2026-09-22)
            raise RuntimeError("could not open '{}'".format(key_name))
        wait_and_settle_storage()
        rows = storage_read_all_pages()   # every page, not just the one it opens on (2026-09-19)
    except Exception as _err:
        log("Warning: could not read '{}' ({}).".format(key_name, _err), 33)
        return None
    finally:
        try:
            Gumps.SendAction(STORAGE_GUMP_ID, 0)
        except Exception:
            pass
    parsed = dict((name.strip().lower(), balance) for name, balance, _li in rows)
    # CACHE IT HERE, the one place this gump is parsed (2026-09-16), so the startup scan and every
    # live read keep the same picture and no second parser can disagree with this one.
    STORAGE_BALANCE_CACHE[(key_name or "").strip().lower()] = parsed
    STORAGE_BALANCE_SCANNED_AT[(key_name or "").strip().lower()] = time.time()
    return parsed


def storage_balance(key_name, row_name):
    """That key's current balance for one row, or None if it could not be read.

    READ-ONLY (2026-09-15): opens the key, parses, closes. Exists so a caller can decide
    whether a withdrawal is worth attempting -- an empty row is the NORMAL state for a fresh
    player and must fall through to whatever the fallback is, not be reported as a failure.

    Uses the same open/parse/close sequence as withdraw_from_storage_key() rather than a
    second one, so the two cannot disagree about how this gump is read."""
    balances = storage_balances(key_name)
    if balances is None:
        return None
    return balances.get(row_name.strip().lower())


def scribe_chisel_listing(scribe):
    """The Scribe's Rune Chisel BuyItem, or None.

    EXTRACTED from ensure_rune_chisel() (2026-09-15) so restock_chisel_charges() can re-read
    the listing on every pass -- BuyItem.Amount is the vendor's live stock and per the user it
    regrows to double about every 5 minutes, so a cached read is always wrong. Body verbatim.

    Vendor.BuyItem exposes Name / Serial / ItemID / Amount / Price -- confirmed by reflecting
    RazorEnhanced.exe, not guessed. Only Name and Price were ever read before; Amount is what
    makes "buy max available" possible at all."""

    # RESOLVE THE LABEL OFF THE LIVE MENU (2026-09-16). This read `buy_label`, which the
    # 2026-09-15 extraction from ensure_rune_chisel() left behind -- an undefined name, one
    # occurrence in the file, NameError on the first restock. compile() and IronPython both pass
    # it; only running it finds it.
    #
    # BY LABEL, NOT BY INDEX, for the reason absorb_backpack_into_key() already gives in its own
    # docstring: an index is a position, and a borrowed position is what put a skull withdrawal
    # into the storage key's window. If "Buy" is not on the menu this returns None and the caller
    # stops -- it must never fall back to a number.
    #
    # EXACT MATCH, NEVER A SUBSTRING. Harvest.py's CONTEXT_NEVER records what these
    # same NPCs offer on one menu -- "Buy  Sell  Bribe  Open Bankbox  Train Animal Taming  Train
    # Inscription" -- and warns that a loose match "would spend gold on skill training". A live
    # capture of this very scribe matched on == "buy"; that is what is used.
    #
    # ONE WaitForContext CALL. It blocks for its own timeout and hands back the entries; it is not
    # a poll and must not be wrapped in one.
    entries = Misc.WaitForContext(scribe, KEY_CONTEXT_WAIT_MS, False)
    if not entries:
        log("Warning: no context menu appeared on {} -- cannot open the buy list."
            .format(scribe.Name or "the Scribe"), 33)
        return None
    buy_label = None
    seen = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        label = text if text is not None else str(entry)
        seen.append(label)
        if (label or "").strip().lower() == "buy":
            buy_label = label
            break
    if buy_label is None:
        log("Warning: no 'Buy' entry on {}'s context menu. It offered: {} -- not guessing an "
            "index.".format(scribe.Name or "the Scribe", seen), 33)
        return None

    before_gump_ids = set(Gumps.AllGumpIDs() or [])
    safe_pause(100)
    Misc.ContextReply(scribe, buy_label)
    safe_pause(1500)

    try:
        buy_list = Vendor.BuyList(scribe.Serial)
    except Exception as e:
        log("Warning: Vendor.BuyList() failed: {}: {}".format(type(e).__name__, e), 33)
        buy_list = None

    # READ Amount AND Price HERE, WHILE THE VENDOR GUMP IS STILL OPEN (2026-09-16). The close
    # below happens before this function returns, so handing a live BuyItem back to the caller
    # means it reads properties off a window that is already gone. Numbers cannot go stale.
    chisel_stock = None
    chisel_price = None
    if buy_list:
        for item in buy_list:
            if (getattr(item, "Name", "") or "").strip().lower() == RUNE_CHISEL_NAME.lower():
                try:
                    chisel_stock = int(getattr(item, "Amount", 0) or 0)
                    chisel_price = int(getattr(item, "Price", 0) or 0)
                except (TypeError, ValueError) as _err:
                    log("Warning: {} lists a Rune Chisel but its stock/price could not be read "
                        "({}) -- not buying on a guess.".format(
                            scribe.Name or "the Scribe", _err), 33)
                    chisel_stock = None
                break

    # FIXED (2026-08-27) -- was Gumps.CurrentGump(), which this file's own header/policy comment
    # (line 688) already documents as unreliable and forbidden for new code. Closing whatever the
    # client claims is "current" risks acting on a gump the user has open manually rather than the
    # vendor's own buy window -- a plausible cause of the live crashes reported "while looking at
    # some gumps manually." Only close gumps that NEWLY appeared as a result of this ContextReply,
    # same snapshot-diff precision open_inscription_menu()/find_gump_by_content() already use.
    new_gump_ids = set(Gumps.AllGumpIDs() or []) - before_gump_ids
    for gid in new_gump_ids:
        Gumps.SendAction(gid, 0)
    safe_pause(500)

    if chisel_stock is None:
        log("Warning: no readable Rune Chisel in {}'s buy list.".format(
            scribe.Name or "the Scribe"), 33)
        return None
    # THE RETURN THAT WAS MISSING (2026-09-16). The old body ended at the `return None` above, so
    # finding the chisel fell off the end of the function and returned None anyway -- every
    # caller read that as "no listing" and gave up without a word. This is why no chisel was ever
    # bought from a vendor, by either the bulk restock or the single-chisel path.
    return (chisel_stock, chisel_price)


def chisel_charge_target():
    """The stored Rune Chisel balance we top up to. Setup value, else the default."""
    try:
        value = int(setup_get(SETUP_KEY_CHISEL_TARGET, "") or CHISEL_CHARGE_TARGET_DEFAULT)
    except (TypeError, ValueError):
        return CHISEL_CHARGE_TARGET_DEFAULT
    return max(0, value)


def calculations_enabled():
    """True when the Calculate preview runs before a craft. Stored setting, DEFAULT ON.

    Defaulted on rather than off because the preview is the only thing that reports cost and
    odds before anything is spent, and a fresh copy of the script should not quietly start
    skipping it. Toggled from the settings screen's Calculations row."""
    return setup_get(SETUP_KEY_CALCULATIONS, "1") != "0"


def pace_storage_key_fill():
    """Waits out only the REMAINDER of STORAGE_KEY_FILL_INTERVAL_MS since the last fill, then
    stamps the clock. Mirrors Omni_Engine.py's function of the same name, including its
    reasoning: a remainder rather than a sleep, so the first fill of a visit waits zero and
    only genuinely back-to-back fills pay anything. Shared clock, because the patch note says
    \"a storage key\" and does not settle whether the limit is per key or global."""
    global last_storage_key_fill_time
    try:
        shared = float(Misc.ReadSharedValue(KEY_FILL_CLOCK_KEY) or 0)
    except Exception:
        shared = 0.0
    remaining_ms = STORAGE_KEY_FILL_INTERVAL_MS - int(
        (time.time() - max(last_storage_key_fill_time, shared)) * 1000)   # THE FILLS TAKE TURNS
    if remaining_ms > 0:
        safe_pause(remaining_ms)
    last_storage_key_fill_time = time.time()
    try:
        Misc.SetSharedValue(KEY_FILL_CLOCK_KEY, "%.3f" % last_storage_key_fill_time)
    except Exception:
        pass


def absorb_backpack_into_key(key_name):
    """Fill the named storage key from the backpack via its context menu. True on success.

    BY LABEL, NOT BY INDEX (2026-09-15). The Tamer reaches this with ContextReply(key, 2), but
    an index is a position -- Omni_ResourceOrders.py uses 4 for the order book's own 'Fill from
    backpack' -- so a borrowed number is exactly the class of assumption that put a skull
    withdrawal into this key's window tonight. The candidate labels come from the shard's
    published patch note; if none of them appear, this logs EVERY entry it saw and returns
    False, so the caller falls back and the next run has the real list."""
    serial = RESOLVED_REQUIRED_ITEMS.get(key_name) or 0
    if not serial:
        for spec in REQUIRED_BACKPACK_ITEMS:
            if spec["name"] == key_name:
                it, status = find_required_backpack_item(spec)
                if status == "ok":
                    RESOLVED_REQUIRED_ITEMS[key_name] = it.Serial
                    serial = it.Serial
                break
    if not serial and key_is_in_master(key_name):
        master = find_master_keys_item()   # (2026-09-22) the master absorbs for every key inside it
        serial = master.Serial if master is not None else 0
        key_name = MASTER_KEYS_NAME
    if not serial:
        log("Warning: '{}' is not in the backpack -- cannot absorb into it.".format(key_name), 33)
        return False
    entries = Misc.WaitForContext(serial, KEY_CONTEXT_WAIT_MS, False)
    if not entries:
        log("Warning: no context menu appeared on '{}'.".format(key_name), 33)
        return False
    seen = []
    chosen = None
    for entry in entries:
        text = getattr(entry, "Entry", None)
        label = text if text is not None else str(entry)
        seen.append(label)
        if (label or "").strip().lower() in STORAGE_FILL_CONTEXT_LABELS:
            chosen = label
            break
    if chosen is None:
        log("Warning: none of {} is on '{}'s context menu. It offered: {} -- not guessing an "
            "index.".format(list(STORAGE_FILL_CONTEXT_LABELS), key_name, seen), 33)
        return False
    pace_storage_key_fill()
    stamp = newest_journal_timestamp()
    Misc.ContextReply(serial, chosen)
    safe_pause(GUMP_RESPONSE_SETTLE_MS)
    left = fill_refused_since(stamp)           # (2026-10-10) THE FILL COOLDOWN IS EVERY SCRIPT'S
    if left is None:
        return True
    log("'{}': the shard's fill cooldown refused it ({:.1f}s left -- another script filled a key) -- sending it once "
        "more.".format(key_name, left), 68)
    safe_pause(int(left * 1000) + FILL_THROTTLE_MARGIN_MS)
    if not Misc.WaitForContext(serial, KEY_CONTEXT_WAIT_MS, False):
        log("Warning: no context menu appeared on '{}' for the second fill -- nothing stored.".format(key_name), 33)
        return False
    pace_storage_key_fill()
    stamp = newest_journal_timestamp()
    Misc.ContextReply(serial, chosen)
    safe_pause(GUMP_RESPONSE_SETTLE_MS)
    if fill_refused_since(stamp) is not None:
        log("Warning: '{}': the fill cooldown refused it TWICE -- nothing stored this time.".format(key_name), 33)
        return False
    return True


def restock_chisel_charges(scribe):
    """Buy chisels a pack-load at a time, absorbing between loads, until the stored balance
    reaches chisel_charge_target() or the vendor runs dry. True if the target is met.

    ONLY WHILE CRAFTING (2026-09-15), per the user -- reached from ensure_rune_chisel(), never
    on a schedule.

    BATCH SIZE IS PACK SPACE, by instruction: \"you can base this entirely on inventory space
    remaining. and buy multiple max inventories per shopping trip if the vendor has more and we
    want more.\" bulk_craft_headroom() already carries the margin, and absorbing empties the
    pack so the loop can take several loads.

    EVERY PASS MUST RAISE THE BALANCE. That is the termination condition rather than an
    iteration cap: it covers a refused purchase, a failed absorb and a silently ignored
    request alike, with no invented retry number.

    maxPrice IS TREATED AS PER-ITEM, the same as today's working amount=1 call. If it turns out
    to be a total, a multi-item buy simply returns False and the no-progress guard stops the
    loop -- watch the first live restock's gold against its purchase count."""
    target = chisel_charge_target()
    # DON'T SHOP FOR WHAT IS ALREADY IN THE PACK (2026-09-16). Checked before the stored-only
    # arithmetic below, which stays as it is: the loop's job is to raise the STORED balance and its
    # no-progress guard depends on measuring exactly that. This is only the "do we need to buy at
    # all" question, and that one has to count the carried chisel -- same reason the travel
    # decision does.
    _available = available_chisel_charges()
    if _available is not None and _available >= target:
        log("Rune Chisel charges {} (stored + carried) already meet the {} target -- not buying."
            .format(_available, target))
        return True
    balance = storage_balance(RUNECRAFTING_STORAGE_NAME, CHISEL_STORAGE_ROW)
    if balance is None:
        log("Cannot read the Rune Chisel balance in {} -- not restocking."
            .format(RUNECRAFTING_STORAGE_NAME), 33)
        return False
    if balance >= target:
        # SAY SO (2026-09-16). This returned True silently, so a trip that bought nothing left no
        # trace at all and the reason had to be read out of the code. Every other exit from this
        # function logs; this was the one that did not.
        log("Rune Chisel charges {} stored already meet the {} target -- nothing to buy."
            .format(balance, target))
        return True
    if scribe is None:
        log("Rune Chisel charges are {} of a {} target, but there is no Scribe here to buy "
            "from.".format(balance, target), 33)
        return False
    log("Rune Chisel charges {} of {} target -- restocking from {}."
        .format(balance, target, scribe.Name or "the Scribe"))
    loads = 0
    while balance < target:
        listing = scribe_chisel_listing(scribe)
        if listing is None:
            # SAY SO (2026-09-16). This break was silent, which is what made a restock that
            # bought nothing leave no trace at all -- see this function's own history.
            log("Could not read {}'s Rune Chisel listing -- stopping the restock."
                .format(scribe.Name or "the Scribe"), 33)
            break
        # A PLAIN (stock, price) TUPLE since 2026-09-16 -- read while the vendor gump was still
        # open, so there is no live object left to parse and no silent parse failure to swallow.
        stock, price = listing
        # WHAT WE ALREADY OWN COUNTS (2026-09-16), per the user: "check storage key and backpack
        # for chisel charges." `balance` below is the STORED row alone, which announced "0 of
        # 60000" while a 54,768-charge chisel sat in the pack -- and would have bought a full
        # 60,000 charges' worth to fill a target we were already most of the way to.
        # available_chisel_charges() is stored + carried, which is what the target means and what
        # the travel decision already used.
        _owned = available_chisel_charges()
        if _owned is not None and _owned >= target:
            log("Rune Chisel charges {} (stored + carried) now meet the {} target -- done "
                "buying.".format(_owned, target))
            return True
        headroom = bulk_craft_headroom()
        count = min(stock, headroom)
        if count <= 0:
            log("Stopping the restock: vendor stock {}, pack headroom {}."
                .format(stock, headroom), 33)
            break
        log("Buying {} Rune Chisel(s) at {} each (stock {}, pack headroom {})."
            .format(count, price, stock, headroom))
        wait_out_world_save()
        bought = Vendor.Buy(scribe.Serial, RUNE_CHISEL_NAME, count,
                            max(RUNE_CHISEL_MAX_PRICE, price))
        if not bought:
            log("Vendor.Buy() refused a batch of {} -- stopping the restock.".format(count), 33)
            break
        safe_pause(GUMP_RESPONSE_SETTLE_MS)
        # NO ABSORB MID-JOB (2026-09-24, owner: "make sure runecrafting only absorbs after it's completely
        # done with a craft, not on little steps along the way"). This used to absorb the whole pack after
        # every load, and the Master Keys absorb takes EVERYTHING a key inside it stores -- the owner's ~100
        # blank axes for the application run would have gone into the enhanced Armory with the chisels. The
        # load now stays in the pack: crafting uses a carried chisel first anyway, and the one closing absorb
        # at the end of the run files what is left. The no-progress rule is unchanged, measured on charges we
        # OWN (stored + carried) instead of the stored row alone.
        after = available_chisel_charges()
        if after is None or after <= balance:
            log("Charges owned did not rise ({} -> {}) after buying {} -- stopping rather "
                "than looping.".format(balance, after, count), 33)
            break
        loads += 1
        log("Bought load {}: Rune Chisel charges owned {} -> {} (target {}) -- kept in the pack, stored by the "
            "closing absorb.".format(loads, balance, after, target))
        balance = after
    if balance >= target:
        log("Restock complete: {} charge(s) owned after {} load(s).".format(balance, loads))
        return True
    log("Restock ended short of the target: {} of {} after {} load(s)."
        .format(balance, target, loads), 33)
    return False


def withdraw_chisel_from_storage():
    """A Rune Chisel out of the carried Runecrafting Storage, or None.

    THE WHOLE POINT OF THE STORAGE (2026-09-15). Docs/TODO.md: "run_craft_flow() does travel to
    the Scribe -> ensure_rune_chisel(scribe) buys one -> craft, and the chisel WEARS OUT
    mid-batch, so the trip recurs. Travel is exactly what the during-combat rule forbids." A
    chisel from a key in the backpack removes the trip, and with it the Scribe-rune dependency
    that stops this script working for anybody else.

    CHECKS THE BALANCE FIRST, deliberately. An empty or absent row is the ordinary state for a
    fresh player, and clicking anyway would spend a gump cycle to be told no. Nothing here is
    fatal -- every path returns None and lets the caller fall back to the Scribe.

    SUCCESS IS THE ITEM ARRIVING, not the withdrawal reporting True. withdraw_from_storage_key()
    already proves the key's balance fell, but what this function owes its caller is a chisel
    in the backpack, so that is what it returns."""
    balance = storage_balance(RUNECRAFTING_STORAGE_NAME, CHISEL_STORAGE_ROW)
    if not balance:
        log("No Rune Chisel charges in {} (row reads {}) -- falling back to the Scribe."
            .format(RUNECRAFTING_STORAGE_NAME,
                    "0" if balance == 0 else "missing"))
        return None
    log("Withdrawing a Rune Chisel from {} ({} charge(s) stored, asking for {})."
        .format(RUNECRAFTING_STORAGE_NAME, balance, CHISEL_WITHDRAW_CHARGES))
    if not withdraw_from_storage_key(RUNECRAFTING_STORAGE_NAME, CHISEL_STORAGE_ROW,
                                     CHISEL_WITHDRAW_CHARGES):
        return None
    safe_pause(GUMP_RESPONSE_SETTLE_MS)
    chisel = find_rune_chisel()
    if chisel is None:
        # The balance fell but nothing landed. Worth saying out loud rather than silently
        # going to the Scribe: charges left the key and we cannot see what they became.
        log("Warning: {} reported the withdrawal but no Rune Chisel is in the backpack."
            .format(RUNECRAFTING_STORAGE_NAME), 33)
    return chisel


def find_rune_chisel():
    for it in container_items(Player.Backpack):
        if it.Name and RUNE_CHISEL_NAME.lower() in it.Name.lower():
            return it
    return None

def ensure_rune_chisel(scribe):
    """Returns the Rune Chisel item, buying one from `scribe` first if the backpack doesn't
    already have one. NOT infinitely reusable -- CONFIRMED live (real batch run, journal:
    "You have worn out your tool!") the chisel wears out after enough uses and is destroyed.
    This function itself doesn't know or care about that -- it just finds/buys one; see
    chisel_still_present()/recover_broken_chisel() for detecting and replacing a worn-out one
    mid-batch, which is the actual fix for that."""
    # TOP UP STORAGE FIRST WHEN WE TRAVELLED TO DO EXACTLY THAT (2026-09-16), per the user: "i'm
    # below, and it went to the scribe, but i don't think it bought any." It did not. This
    # function used to satisfy "get me a chisel" from storage and return, so
    # restock_chisel_charges() below was only ever reachable when storage was EMPTY -- while the
    # trip itself had been made because storage was below TARGET. Storage having charges is what
    # made the restock look unnecessary here, and it is the very thing the caller came to fix.
    #
    # `scribe is not None` IS THE SIGNAL. craft_n_runes() only resolves one when
    # available_chisel_charges() came in under chisel_charge_target(), so a scribe in hand means
    # "we are here on purpose, buy". Every other call passes None and is untouched.
    #
    # BEFORE ANY WITHDRAWAL, not after: restock_chisel_charges() buys into the pack and absorbs
    # into the key, and that absorb takes a carried chisel with it. First gives a clean sequence
    # -- buy, absorb, then withdraw one chisel holding the combined total. After a withdrawal, its
    # own "stored + carried already meet the target" check would see the 60,000 charges just
    # pulled out and decline, which is the same trap from the other side.
    if scribe is not None:
        restock_chisel_charges(scribe)

    existing = find_rune_chisel()
    if existing:
        return existing

    # THE STORAGE BEFORE THE SCRIBE (2026-09-15). Cheapest first: a chisel already in the pack,
    # then the carried key (no travel, no vendor, no gold), then the Scribe. The Scribe is now
    # the LAST resort instead of the only one -- see withdraw_chisel_from_storage() for why
    # that matters well beyond saving a walk.
    #
    # scribe MAY BE None once this is reached from a path that never travelled, which is the
    # point of the split: crafting no longer needs a Scribe to exist.
    from_storage = withdraw_chisel_from_storage()
    if from_storage:
        return from_storage
    if scribe is None:
        log("Warning: no Rune Chisel in the pack or in {}, and no Scribe to buy one from."
            .format(RUNECRAFTING_STORAGE_NAME), 33)
        return None
    # TOP THE STORAGE UP, THEN TAKE A COMBINED CHISEL FROM IT (2026-09-15). This is the whole
    # point of restocking rather than buying one and using it: a single chisel carrying the
    # stored charges does not wear out mid-batch, and a worn-out tool is what made the Scribe
    # trip RECUR. Yield per purchase is random (26/35/66 measured), so the loop buys by pack
    # space and re-reads the stored balance -- see restock_chisel_charges().
    if restock_chisel_charges(scribe):
        # THE LOAD IS IN THE PACK NOW, not in storage (2026-09-24, no mid-job absorb -- see
        # restock_chisel_charges()): use a bought chisel straight from the pack, and only fall back to a
        # withdrawal when the pack holds none.
        restocked = find_rune_chisel() or withdraw_chisel_from_storage()
        if restocked:
            return restocked
    # FALLBACK, DELIBERATELY KEPT. If the restock could not finish -- most likely because the
    # absorb's context label is not one of STORAGE_FILL_CONTEXT_LABELS, which is quoted from
    # the shard's patch notes rather than verified -- buying a single chisel still crafts. A
    # wrong label costs a log line naming every entry it saw, not a stopped batch.
    log("No Rune Chisel in the backpack -- buying one from {}...".format(scribe.Name or "the Scribe"))
    chisel_listing = scribe_chisel_listing(scribe)
    if chisel_listing is None:
        return None
    # (stock, price) SINCE 2026-09-16 -- see scribe_chisel_listing(). This path read .Price off a
    # live BuyItem and, before the missing `return` was found, never ran at all.
    _listing_stock, _listing_price = chisel_listing

    max_price = min(RUNE_CHISEL_MAX_PRICE, _listing_price) if _listing_price else RUNE_CHISEL_MAX_PRICE
    wait_out_world_save()  # Checked BEFORE Vendor.Buy() -- same "proactive, not just safe_pause()'s
                              # after-the-fact absorption" reasoning as open_inscription_menu()'s
                              # own pre-UseItem() check; see safe_pause()'s own docstring.
    ok = Vendor.Buy(scribe.Serial, RUNE_CHISEL_NAME, 1, max(max_price, _listing_price))
    if not ok:
        log("Warning: Vendor.Buy() for Rune Chisel returned False.", 33)
        return None

    safe_pause(1000)
    new_chisel = find_rune_chisel()
    if not new_chisel:
        log("Warning: purchase reported success but no Rune Chisel found in the backpack.", 33)
        return None
    log("Bought a Rune Chisel for {} gold.".format(_listing_price))
    return new_chisel

def chisel_still_present(chisel):
    """Whether `chisel`'s Serial still exists in the backpack -- the worn-out-tool destruction
    doesn't leave any other trace to check, same backpack-presence approach already used
    elsewhere in this project for detecting a broken item."""
    return any(it.Serial == chisel.Serial for it in container_items(Player.Backpack))

def reopen_inscription_menu_for(category_button, line_text):
    """Re-open the Inscription Menu, switch to `category_button`, and resolve `line_text`'s
    button. Returns (gump_id_or_None, button_or_None).

    EXTRACTED from recover_broken_chisel() (2026-09-16), unchanged, because a second caller
    appeared: a craft that produced nothing with no journal message, where the menu itself may
    have gone. Copying it would have made this the third place the open/switch/resolve sequence
    lives -- and the chisel path's own version logs "Rune Chisel broke", which is the wrong
    sentence for a stale gump."""
    gid = open_inscription_menu(force_fresh=True)
    if gid is None:
        log("FATAL: could not reopen the Inscription Menu -- stopping.", 33)
        return None, None
    gid = switch_inscription_category(gid, category_button)
    if gid is None:
        return None, None
    lines, layout, _buttons = read_gump(gid)
    _idx, button = find_button_for_line(lines, layout, line_text)
    if button is None:
        log("FATAL: could not resolve '{}''s button on the reopened Inscription Menu -- "
            "stopping.".format(line_text), 33)
        return gid, None
    return gid, button


def recover_broken_chisel(scribe, category_button, line_text):
    """Called once a chisel_still_present() check comes back False mid-batch. Per the user:
    "look for more tools in bag if one breaks, else buy a new one" -- ensure_rune_chisel()
    already does exactly that sequence (find one already on hand, else buy), so this just calls
    it again and then re-opens the Inscription Menu with whatever chisel results, switches back
    to category_button, and re-resolves line_text's button (a freshly opened gump instance may
    not keep the same button numbering as the one that just broke). Returns
    (chisel, gump_id, button) -- button is None if recovery failed at any step, telling the
    caller to stop."""
    log("Rune Chisel broke -- looking for another.", 33)
    chisel = ensure_rune_chisel(scribe)
    if not chisel:
        log("FATAL: could not obtain a replacement Rune Chisel -- stopping.", 33)
        return None, None, None

    # force_fresh=True (2026-08-27) -- see open_inscription_menu()'s own docstring for the full
    # root cause: the plain reuse path could hand back the just-broken chisel's own stale gump,
    # still showing whatever sub-category it left off on, causing switch_inscription_category()'s
    # own category-button lookup to fail. This forces a genuinely new gump via the new chisel.
    gid, button = reopen_inscription_menu_for(category_button, line_text)
    if button is None:
        return chisel, gid, None

    log("Replacement Rune Chisel ready, resuming.")
    return chisel, gid, button


# =============================================================================
# INSCRIPTION MENU
# =============================================================================

def open_inscription_menu(force_fresh=False):
    """Returns the Inscription Menu's gump id, opening it via the Rune Chisel if it isn't already
    open. force_fresh=True skips the reuse shortcut and always requests a genuinely new gump via
    the chisel, even if a gump is already on screen.

    force_fresh added (2026-08-27), per a live capture: recover_broken_chisel() needs a gump known
    to be at the top-level category-selector state so switch_inscription_category() can find the
    category button afterward -- but is_inscription_menu()'s own content match is deliberately
    loose ("any non-empty gump that isn't Daily Tasks" -- see its own docstring for why: the
    Inscription Menu has no fixed identifying content, it varies by category). That means the plain
    reuse shortcut below can hand back whatever SUB-PAGE the chisel that just broke left the gump
    showing -- e.g. already inside a specific category, where the top-level category buttons (1/8)
    simply don't exist on the current layout -- which is exactly the live "category button 1 not
    found on the Inscription Menu's current layout" FATAL this was caught by. Same root-cause SHAPE
    already fixed once this session for Omni_Engine.py's own find_event_tracker_gump() (reused
    a stale already-open gump instead of resending fresh -- see [[project_event_tracker_stale_gump_reuse]]).
    Kept as an opt-in parameter rather than the new default: every OTHER caller legitimately wants
    the reuse (switch_inscription_category()'s own docstring: "switch ONCE per batch... repeatedly
    re-switching... was needlessly slow"), only the recovery path's state assumption was wrong."""
    if not force_fresh:
        gid = find_gump_by_content(is_inscription_menu)
        if gid is not None:
            return gid
    chisel = find_rune_chisel()
    if not chisel:
        log("Warning: no Rune Chisel available to open the Inscription Menu.", 33)
        return None
    # Checked BEFORE Items.UseItem() (2026-08-27), not just via safe_pause()'s own after-the-fact
    # absorption below -- CONFIRMED live: a save already in progress right at this exact moment
    # (recover_broken_chisel()'s reopen, right after buying a replacement chisel) can eat the
    # whole subsequent open attempt before safe_pause() ever gets a chance to notice, same shape
    # apply_rune_to_item() was hardened for. See safe_pause()'s own docstring for the full incident.
    wait_out_world_save()
    Items.UseItem(chisel.Serial)
    safe_pause(2000)
    safe_pause(500)
    return find_gump_by_content(is_inscription_menu)

CRAFT_VERIFY_POLL_INTERVAL_MS = 200
CRAFT_VERIFY_TIMEOUT_MS = 2000  # Same overall ceiling the old fixed 1500+500 wait had -- polling
                                  # just returns as soon as the new item is actually detected
                                  # instead of always waiting the full amount regardless.

# RETRY-ON-FAIL (2026-08-27), per the user: "the script has proven VERY good at recognizing an
# anomaly and stopping the craft. Let's add some try again functionality to most fail points. The
# only exclusions, inscription under 300, out of perk deeds, and crafted an unexpected rune. Those
# are still a full stop." Applied at the GRANULAR, individual-action level (one specific RE call
# failing) rather than at higher-level orchestration functions (craft_more_runes_if_needed(),
# prepare_and_apply_one_stat()'s own shortfall check) -- those already call INTO the granular,
# now-retrying functions below, so retrying at their level too would stack multiplicatively (each
# outer retry re-running several ALREADY-retried inner steps) rather than adding real resilience.
RUNECRAFTING_FAIL_RETRY_ATTEMPTS = 3
RUNECRAFTING_FAIL_RETRY_PAUSE_MS = 2000  # Long enough for a real transient issue (gump timing, a
                                    # brief server hiccup, a concurrent script topping up a
                                    # resource) to actually resolve before trying again.

def retry_until_truthy(fn, label, attempts=RUNECRAFTING_FAIL_RETRY_ATTEMPTS,
                        pause_ms=RUNECRAFTING_FAIL_RETRY_PAUSE_MS):
    """Calls fn() (a zero-arg callable) up to `attempts` times, pausing pause_ms between tries,
    stopping the moment it returns a truthy result. Returns whatever the LAST call returned
    (truthy on success, whatever falsy value the final failed attempt produced otherwise). Shared
    by every "try again on failure" call site below -- see RUNECRAFTING_FAIL_RETRY_ATTEMPTS' own
    comment for the 3 explicit exclusions this is deliberately never used for."""
    result = fn()
    tried = 1
    while not result and tried < attempts:
        log("'{}' didn't succeed -- retrying ({}/{})...".format(label, tried + 1, attempts), 33)
        safe_pause(pause_ms)
        result = fn()
        tried += 1
    return result

# THE STOP SAYS WHY (2026-10-17, the shared panner's lesson -- every stop names its exact cause): a craft that did not
# come leaves the shard's own words here, and the batch's stop line repeats them -- short of gold, an empty Reagent Keys,
# whatever the shard said -- instead of only "the safety check just caught a problem".
CRAFT_FAIL_SAID = [""]


def craft_and_verify(gump_id, select_button, expected_name_prefix, action_label):
    """Clicks select_button on gump_id, diffs the backpack for a new item, and verifies its name
    STARTS WITH expected_name_prefix. Returns (ok, new_item_or_None). Per the user: a mismatch or
    no new item at all means the CALLER must stop -- this function only reports, it never retries
    or substitutes a different action on its own.

    POLLS for the new item rather than a blind fixed sleep -- per the user, the old 2000ms wait
    was a conservative leftover from initial discovery, never actually tested for a real minimum.
    Checks every CRAFT_VERIFY_POLL_INTERVAL_MS up to CRAFT_VERIFY_TIMEOUT_MS total (same overall
    cap as before), returning the moment a new item actually appears -- same reliability floor as
    before (still waits the full cap before concluding failure), just faster on the typical case.
    Also checks for a world save in progress each tick (see wait_out_world_save()) -- CONFIRMED
    live a real save's multi-second freeze can otherwise burn through this whole timeout and
    trigger a false safety-stop, since a save-time tick doesn't count against CRAFT_VERIFY_TIMEOUT_MS."""
    # SERIAL -> AMOUNT, not a bare set of serials (2026-09-11). Enhancement runes stack as of the
    # 2026-09-08 shard patch, so the second rune of a kind MERGES into the first one's stack and no
    # new serial is ever created. Snapshotting the amount too is what lets a stacked craft be seen
    # at all -- see this patch's own header for why an empty diff used to halt the entire batch.
    before_amounts = {}
    for _it in container_items(Player.Backpack):
        try:
            before_amounts[_it.Serial] = int(getattr(_it, "Amount", 1) or 1)
        except Exception:
            before_amounts[_it.Serial] = 1
    # THE CHISEL CHARGE IS THE SUCCESS SIGNAL THE ABSORB CANNOT REMOVE (2026-09-23 23:41, owner: "we are in fact
    # making the ahm runes" / "the rough stones are not in the backpack"). In passive mode the Tamer's Master
    # Keys absorb can file the new rune into storage inside this window, so "no rune seen" was read as a failed
    # craft, the batch retried, and a second rune was made for one counted -- Rough Stone burned. The stone and
    # the reagents are drawn from storage and the keys, never the pack; the one thing in the pack that a craft
    # consumes is one charge of the carried Rune Chisel (54737 -> 54731 over six crafts tonight). If the rune is
    # not seen but exactly one charge is gone, the craft happened. (A chisel absorbed mid-window reads 0 and the
    # check simply does not fire -- the keyguard keeps it in the pack.)
    try:
        _charges_before = carried_chisel_charges()
    except Exception:
        _charges_before = 0

    def _one_unit_consumed():
        if not _charges_before:
            return False
        try:
            _now = carried_chisel_charges()
        except Exception:
            return False
        return bool(_now) and (_charges_before - _now) == 1
    Journal.Clear()
    Gumps.SendAction(gump_id, select_button)

    def _is_the_expected_item(_it):
        """Cheap enough to run on every candidate on every 200ms tick -- it reads .Name and pays
        for nothing. An item whose properties have not loaded reads as False here; that is why the
        timeout path below re-checks with WaitForProps() before concluding anything."""
        try:
            # bare_item_name() (2026-09-16). This read the RAW name, and a stacked pile is named
            # "131 In Rune" -- which does not start with "in". So this never matched, the loop ran
            # the full CRAFT_VERIFY_TIMEOUT_MS on every single craft (every success in the journal
            # reports exactly "(2000ms)"), and the match only happened below via after_items[0].
            # Over two minutes of dead waiting per 66-rune batch, and it looked like success.
            return bare_item_name(_it).lower().startswith(expected_name_prefix.lower())
        except Exception:
            return False

    after_items = []
    matched_item = None
    stacked_onto = False
    waited_ms = 0
    while waited_ms < CRAFT_VERIFY_TIMEOUT_MS:
        safe_pause(CRAFT_VERIFY_POLL_INTERVAL_MS)
        # A craft shows up as EITHER a brand-new serial (first of its kind, or an unstackable item)
        # OR an existing stack whose Amount went up. Both are the same event; only the shard's
        # bookkeeping differs.
        fresh, grown = [], []
        for _it in container_items(Player.Backpack):
            _prev = before_amounts.get(_it.Serial)
            if _prev is None:
                fresh.append(_it)
                continue
            try:
                if int(getattr(_it, "Amount", 1) or 1) > _prev:
                    grown.append(_it)
            except Exception:
                pass
        # New serials first: on the very first craft of a kind that IS the crafted item, and it
        # carries the name the safety check needs. A grown stack is the fallback, not the default.
        after_items = fresh or grown
        stacked_onto = (not fresh) and bool(grown)
        # WAIT FOR THE RUNE, NOT FOR THE FIRST ARRIVAL (2026-09-15). This used to break on `if
        # after_items:` -- anything new at all. Live, a stack of garlic reached the backpack ahead
        # of the rune, so the poll broke on the garlic, `after_items[0]` WAS the garlic, and the
        # syllable check stopped the whole batch in the same second as the click while the rune was
        # still on its way. (Where that garlic came from is NOT established -- per the user,
        # reagents "come directly from the key on craft" and never enter the pack. This does not
        # depend on the answer: anything that is not the rune is simply not the rune.)
        # `before_amounts` is a fixed snapshot, so `fresh` is cumulative -- the tick that sees the
        # rune still sees whatever else turned up beside it.
        matched_item = None
        for _cand in after_items:
            if _is_the_expected_item(_cand):
                matched_item = _cand
                break
        if matched_item is not None:
            break
        if wait_out_world_save():
            continue
        waited_ms += CRAFT_VERIFY_POLL_INTERVAL_MS

    if not after_items:
        journal_lines = Journal.GetJournalEntry(None) or []
        reason = "; ".join((jl.Text or "") for jl in journal_lines) or "(no journal message)"
        CRAFT_FAIL_SAID[0] = reason             # THE STOP SAYS WHY
        # WAS THE GUMP EVEN THERE? (2026-09-16) The batch stopped at 36 of 66 with three of these
        # in a row and the raw journal held NOTHING from the shard -- the signature of a click
        # that never reached the server. gump_id is captured once and reused for the whole batch,
        # and a button sent to a gump that has gone is a silent no-op. Answering it here means the
        # next occurrence names the cause instead of leaving it to inference.
        try:
            _menu_open = bool(Gumps.HasGump(gump_id))
        except Exception:
            _menu_open = True   # unknown: do not accuse the gump on a failed check
        if _one_unit_consumed():
            log("'{}': the rune was not seen in the pack, but one chisel charge was consumed -- the craft happened "
                "and the Master Keys absorb filed the rune into storage. Counted.".format(action_label), 43)
            return True, None
        log("Safety check: no new item AND no stack grew for '{}' after {}ms -- {} {}".format(
            action_label, waited_ms, reason,
            "The Inscription Menu (0x{:X}) is still open, so the click WAS delivered and the "
            "shard ignored it.".format(gump_id) if _menu_open else
            "The Inscription Menu (0x{:X}) is GONE -- the click went nowhere.".format(gump_id)), 33)
        return False, None

    if matched_item is None:
        # PROPERTIES CAN ARRIVE LATE, and the poll above deliberately never waits for them (ten
        # ticks x N candidates of WaitForProps would exceed the whole 2s budget). So a real rune
        # whose name had not loaded yet reads as a non-match right through the timeout. Pay for the
        # properties ONCE per candidate and look again before calling this a failure -- otherwise
        # this fix would simply trade one false SAFETY STOP for another.
        for _cand in after_items:
            try:
                Items.WaitForProps(_cand, 1000)
            except Exception:
                pass
            if _is_the_expected_item(_cand):
                matched_item = _cand
                break

    new_item = matched_item if matched_item is not None else after_items[0]
    Items.WaitForProps(new_item, 1000)
    raw_name = (new_item.Name or "").strip()
    # COMPARE THE BARE NAME, REPORT THE RAW ONE (2026-09-16). This stopped the 00:44 batch with
    # "expected a name starting with 'in', got '3 In Rune'" -- a correctly crafted rune that had
    # stacked onto an existing pile. The diagnostic added on 2026-08-27 called this exact case in
    # advance ("a stack Amount misread as a name"), which is why the line carried Amount=3 and this
    # took one read. The log below keeps showing raw_name, so the next surprise is still legible.
    name = bare_item_name(new_item)

    if not name.lower().startswith(expected_name_prefix.lower()):
        # DIAGNOSTIC DETAIL (2026-08-27), added after a live, unexplained mismatch: "got '7956'
        # instead" -- a bare name string alone wasn't enough to tell whether that was a genuinely
        # unrelated item, a stack Amount misread as a name, or (if `after_items` had more than one
        # entry) simply the WRONG new item being inspected -- `after_items[0]` has no guaranteed
        # ordering, so if TWO new serials appeared in the same diff window (the real crafted item
        # AND something else, from any source), this could report on the wrong one while the actual
        # craft sat uninspected. Serial/ItemID/Amount, plus how many new items were actually found,
        # should make the NEXT occurrence immediately diagnosable instead of another open question.
        # LOOT IS NOT A WRONG CRAFT (2026-09-23 23:39, passive mode at the Overlord altar): the Tamer's kills drop
        # 'A Set of Overlord Skulls', 'a glimmering chest of belongings', 'A Crystal of Enhancement' into the SAME
        # pack inside this window and the rune itself is absorbed before it is seen -- three of four batches in
        # ten minutes stopped here. First ask the chisel: one charge gone means the craft happened (counted, no
        # item). Otherwise a wrong craft can only be a RUNE of another property (the button resolved to the wrong
        # line), so only a rune name keeps the SAFETY STOP; any other arrival is loot and the caller retries.
        if _one_unit_consumed():
            log("'{}': a new '{}' arrived (something else came into the pack) and the rune was not seen, but one chisel charge was "
                "consumed -- the craft happened and the absorb filed the rune. Counted.".format(action_label, raw_name), 43)
            return True, None
        if "rune" not in name.lower():
            log("'{}': a new '{}' arrived in the pack but no '{}' rune did and no chisel charge was consumed -- "
                "loot, not this craft; retrying.".format(action_label, raw_name, expected_name_prefix), 43)
            return False, None
        log("SAFETY STOP: '{}' expected a name starting with '{}', got '{}' instead "
            "(Serial=0x{:X}, ItemID=0x{:X}, Amount={}, {} new item(s) detected this tick).".format(
                action_label, expected_name_prefix, raw_name,
                new_item.Serial, new_item.ItemID, new_item.Amount, len(after_items)), 33)
        # EVERYTHING THAT ARRIVED, AND WHAT THE SHARD SAID (2026-09-15). The garlic line reported
        # one item and no reason, and it took a code read to establish that the rune was simply
        # later. Journal.Clear() at the top of this function scopes these messages to this single
        # click, and the "no new item at all" branch has always quoted them -- this branch never
        # did. Per the user, the next thing to pin down is "an error we might see if we're out of
        # reagents for the craft": that message lands HERE, and it should arrive already quoted
        # rather than needing a journal dig to recover.
        if len(after_items) > 1:
            log("  everything new in the pack this tick: {}".format(
                ", ".join("'{}' (0x{:X}, ItemID=0x{:X}, Amount={})".format(
                    (_o.Name or "").strip(), _o.Serial, _o.ItemID, _o.Amount)
                    for _o in after_items)), 33)
        _said = "; ".join((_jl.Text or "") for _jl in (Journal.GetJournalEntry(None) or []))
        CRAFT_FAIL_SAID[0] = _said or "nothing at all -- the item that came was not the rune"   # THE STOP SAYS WHY
        log("  what the shard said during the attempt: {}".format(
            _said or "(nothing at all)"), 33)
        return False, new_item

    # SILENT ON SUCCESS (2026-09-16), per the user: "trim that out". This logged
    # "'apply Luck' confirmed: In Rune [stacked onto an existing pile] (1200ms)" for every rune,
    # doubling the journal volume of a 171-rune batch and repeating three things the caller's own
    # one-liner covers: the action label (the batch header already said it), the stack marker (now
    # true on every line, so configuration rather than an event) and the timing (the caller clocks
    # it). Every FAILURE path above keeps its log, so nothing diagnostic was traded away.
    #
    # stacked_onto is still computed -- the poll needs it to tell a grown stack from a new item.
    return True, new_item

def switch_inscription_category(gump_id, category_button):
    """Switches the already-open Inscription Menu to category_button. Returns the (possibly
    re-found) gump id. Callers should switch ONCE per batch, not once per craft -- per the user,
    repeatedly re-switching category for every single rune in a batch was needlessly slow (each
    switch costs a real ~1.5s settle wait). Waits out a world save (see wait_out_world_save())
    BEFORE the settle pause, if one is already in progress when the switch is sent -- there's no
    reliable "category actually changed" signal to poll for here (a still-open Inscription Menu
    gump is found immediately either way, whether or not its content has updated yet), so this
    doesn't fully protect a save that starts mid-settle, but it does stop a save from silently
    eating into the settle window and contributing to a downstream "could not resolve button"
    failure, which is what happened live.

    FIXED (2026-08-27) -- CONFIRMED live to cause a disconnect: MISCELLANEOUS_CATEGORY_BUTTON/
    ENHANCEMENT_CATEGORY_BUTTON are hardcoded (their own comment already hedges "stable across
    every test THIS SESSION", not proven stable in every gump state), and this used to send
    category_button to Gumps.SendAction() with no check that it actually exists on the gump's
    current layout. This project's own confirmed disconnect history (peerless_storage_* clicking
    a "next page" button absent from the real last page) is exactly this failure shape -- a gump
    action referencing something not on the current page doesn't no-op, it kills the connection.
    The chisel-recovery path (recover_broken_chisel(), a freshly re-opened gump instance) is the
    highest-risk trigger, matching the live report. Now validates against extract_buttons()
    first and refuses to send (returns None) rather than guess, same "never guess, halt and
    report" convention find_button_for_line() already established."""
    gump_id = find_gump_by_content(is_inscription_menu) or gump_id
    _lines, layout, buttons = read_gump(gump_id)
    if category_button not in buttons:
        log("FATAL: category button {} not found on the Inscription Menu's current layout -- "
            "not sending it (a blind send here is a confirmed live disconnect cause) -- "
            "stopping.".format(category_button), 33)
        return None
    Gumps.SendAction(gump_id, category_button)
    wait_out_world_save()
    safe_pause(1000)
    safe_pause(500)
    return find_gump_by_content(is_inscription_menu) or gump_id

def switch_inscription_category_with_retry(gump_id, category_button):
    """Wraps switch_inscription_category() with ONE retry against a genuinely fresh gump
    (open_inscription_menu(force_fresh=True)) if the first attempt fails to find category_button
    on the current layout.

    ADDED (2026-08-27), per a live capture: the "FATAL: category button 1 not found" case wasn't
    limited to the chisel-break recovery path recover_broken_chisel() already force-reopens fresh
    for -- it hit the very FIRST switch of a fresh script run (0 of 99 planned runes crafted). A
    gump left open from an earlier session/run (open_inscription_menu()'s own reuse shortcut) can
    be just as stale -- sitting on whatever sub-category it was last showing -- as one left by a
    broken chisel; this covers that case too instead of requiring the specific broken-chisel
    trigger. Returns the gump id switch_inscription_category() itself returns (already confirmed
    successful), or None if even the forced-fresh retry fails."""
    result = switch_inscription_category(gump_id, category_button)
    if result is not None:
        return result
    log("Retrying category switch against a genuinely fresh Inscription Menu instance...", 68)
    fresh_gid = open_inscription_menu(force_fresh=True)
    if fresh_gid is None:
        return None
    return switch_inscription_category(fresh_gid, category_button)


# =============================================================================
# REAGENT KEYS WITHDRAWAL -- same proven pattern as Omni_ResourceOrders.py's own storage keys.
# =============================================================================

def wait_and_settle_storage():
    safe_pause(PRE_WAIT_SETTLE_MS)
    wait_for_gump_present(STORAGE_GUMP_ID, KEY_CONTEXT_WAIT_MS)
    safe_pause(GUMP_RESPONSE_SETTLE_MS)

def count_material(name_substring):
    total = 0
    for it in container_items(Player.Backpack):
        if it.Name and name_substring in it.Name.lower():
            total += it.Amount
    return total

def storage_row_buttons(layout):
    """{line-list index of a row name: that row's button id}, resolved by geometry.

    ART-AGNOSTIC ON PURPOSE (2026-09-15) -- see STORAGE_TEXT_PATTERN's comment for the live
    measurement this replaces. Filtering on a button's art is what dropped the red Rune
    Chisel button and let two footer controls be counted as rows.

    KEYED BY THE PIECE'S POSITION (2026-10-01), not its string index: line k of the data-only list is the k-th text
    piece (see storage_gump_strings()), and that line index is what parse_storage_rows() reports. The two only agreed
    while every row came before the window's text entry -- true of every key measured, and no longer assumed."""
    text = str(layout)
    buttons = [(int(x), int(y), int(bid))
               for x, y, bid in STORAGE_BUTTON_PATTERN.findall(text)]
    out = {}
    for k, (_idx, tx, ty, hue) in enumerate(storage_text_pieces(text)):
        if hue != STORAGE_ROW_NAME_HUE:
            continue        # a value cell, the title, or footer chrome -- not a row name
        best = None
        for bx, by, bid in buttons:
            gap = tx - bx
            if gap < STORAGE_ROW_BUTTON_GAP_MIN or gap > STORAGE_ROW_BUTTON_GAP_MAX:
                continue    # too close (footer column) or too far (the other column)
            if abs(by - ty) > STORAGE_ROW_BUTTON_Y_TOL:
                continue    # a different line
            if best is None or gap < best[0]:
                best = (gap, bid)
        if best is not None:
            out[k] = best[1]
    return out


def parse_storage_rows(lines):
    """(name, balance, line_index) for every resource row in an open storage gump's line list.

    THE LINE INDEX IS THE JOIN KEY (2026-09-15) between this walk and the layout, whose own
    text entries carry it -- that is how storage_row_buttons() maps a row to its button
    without relying on either list's ordering. Both callers are in
    withdraw_from_storage_key(); nothing outside this file uses this function.

    Extracted originally so the balance could be read BEFORE and AFTER a withdrawal without
    duplicating the walk -- unchanged."""
    rows = []
    i = 1
    while i + 1 < len(lines):
        name = (lines[i] or "").strip()
        if not name or STOP_LINE_PATTERN.match(name):
            break
        value = (lines[i + 1] or "").strip()
        if not value.isdigit():
            break
        rows.append((name, int(value), i))
        i += 2
    return rows


def withdraw_from_storage_key(key_name, balance_name, amount):
    """Opens the named storage key, finds balance_name's row/button, withdraws `amount`, and
    returns True ONLY once that key's own balance for the row is confirmed to have gone DOWN.

    ANY KEY (2026-09-15). This was withdraw_from_reagent_keys() and hardcoded the Reagent Keys
    in four places -- the item it opened and three of its own log lines. The Runecrafting
    Storage needs the identical sequence for a Rune Chisel and for stored runes, so the key is
    now an argument. The old name described its one caller rather than what the function does,
    which is precisely why a second key looked like it needed a second copy.

    WHAT MAKES IT WORTH SHARING, rather than the click being trivial: button ids come from the
    LIVE layout every time (a gump button id is a position in this project, never a remembered
    number), success means the key's own balance FELL, and a throttle is waited out for the
    duration the server itself states.

    REWRITTEN 2026-09-08, two defects, one shard-driven and one long-standing:

    1. The new withdrawal rate limit (see WITHDRAW_THROTTLE_PATTERN) silently rejects the click.
       Now detected, and the server's OWN stated wait is honoured before clicking again -- no
       invented duration.
    2. This used to return True whenever the row was found and the click was SENT, and log
       "Withdrew N 'X'" regardless of whether anything moved. That was a false success and a false
       log line. ensure_reagent() does re-count the backpack afterward, so nothing downstream was
       corrupted by it -- but the contract and the log both lied, which is how a throttled
       withdrawal reads as working. Same "verify the real outcome, don't trust a flat pause" gap
       already closed for Peerless Storage in the Tamer.

    Confirmation uses the KEY'S OWN BALANCE rather than a backpack scan: reagents stack, so a
    withdrawal often lands on an existing stack instead of creating a new serial, and this function
    is given a storage ROW NAME (not the reagent's item match) so it cannot count the pack the way
    ensure_reagent() does. The gump re-renders after every button response, so the row is simply
    re-read and compared."""
    for attempt in range(WITHDRAW_MAX_ATTEMPTS):
        if not open_storage_key(key_name):   # loose in the pack, or via the Master Keys gump (2026-09-22)
            return False
        wait_and_settle_storage()

        # PAGE TO THE ROW (2026-09-19): the row may sit on page 2 (Sar does). Read this page; if the row
        # is not on it and a Next Page button exists, turn and read again. The button is then resolved by
        # geometry on the page that actually shows the row, exactly as before.
        lines = Gumps.GetLineList(STORAGE_GUMP_ID, True) or []
        layout = Gumps.GetGumpRawLayout(STORAGE_GUMP_ID)
        row_pairs = parse_storage_rows(lines)
        for _page in range(STORAGE_MAX_PAGES - 1):
            if any(n.strip().lower() == balance_name.strip().lower() for n, _b, _li in row_pairs):
                break
            if not storage_turn_page():
                break
            lines = Gumps.GetLineList(STORAGE_GUMP_ID, True) or []
            layout = Gumps.GetGumpRawLayout(STORAGE_GUMP_ID)
            row_pairs = parse_storage_rows(lines)
        # BY GEOMETRY, NOT BY ORDER (2026-09-15). This used to harvest buttons of art
        # 1209/1210 and zip them against the rows. A live dump of the Runecrafting Storage
        # showed 32 rows against 33 such buttons -- the RED Rune Chisel button (art
        # 2472/2473) excluded by the art filter, and both footer controls (Add / Fill from
        # backpack, at x=305) counted as rows -- so every pairing was off by one from the
        # first row and a withdrawal would have clicked the next resource down.
        row_buttons = storage_row_buttons(layout)
        button = None
        balance_before = None
        row_found = False
        for name, bal, line_index in row_pairs:
            if name.strip().lower() == balance_name.strip().lower():
                row_found = True
                button = row_buttons.get(line_index)
                balance_before = bal
                break

        if button is None:
            # TWO DIFFERENT FAILURES, SAID APART (2026-09-15). This assumed the only way to
            # have no button was a missing row. Geometric resolution adds a second: the row
            # is right there but nothing sits 20-60px left of its label. They want different
            # responses -- a missing row means the caller asked for the wrong resource, an
            # unresolved button means this gump's geometry moved and storage_row_buttons()
            # needs revisiting. Either way we click NOTHING.
            if row_found:
                log("Warning: '{}' IS a row in {}, but no button could be resolved beside "
                    "it -- the gump geometry may have changed. Refusing to click anything."
                    .format(balance_name, key_name), 33)
            else:
                log("Warning: '{}' not found among {}' rows.".format(balance_name, key_name), 33)
            Gumps.SendAction(STORAGE_GUMP_ID, 0)
            return False

        # AN EMPTY ROW IS NOT A FAILURE (2026-09-16), per the user: "these warnings shouldn't
        # show up when we're out of runes in the storage key. It's normal and handled, but it's
        # big and scary for no good reason."
        #
        # DECLINED BEFORE THE CLICK, which is what removes all three noisy lines: the shard's own
        # "you don't have any of that", this function's "could not be confirmed (balance 0 -> 0)"
        # warning, and the caller's "refused the withdrawal". Clicking a row we can already see is
        # empty could only ever produce them.
        #
        # THE PRINCIPLE IS ALREADY WRITTEN DOWN in storage_balance(): "an empty row is the NORMAL
        # state for a fresh player and must fall through to whatever the fallback is, not be
        # reported as a failure." Here the fallback is crafting, and that is what happens.
        if balance_before == 0:
            log("{} has no '{}' left -- nothing to withdraw.".format(key_name, balance_name))
            Gumps.SendAction(STORAGE_GUMP_ID, 0)
            return False

        Journal.Clear()  # So the throttle check below reflects THIS click only.
        Gumps.SendAdvancedAction(STORAGE_GUMP_ID, button, [], [0], [str(amount)])
        wait_and_settle_storage()

        throttle_seconds = None
        for line in (Journal.GetJournalEntry(None) or []):
            throttle_match = WITHDRAW_THROTTLE_PATTERN.search(line.Text or "")
            if throttle_match:
                try:
                    throttle_seconds = float(throttle_match.group(1))
                except ValueError:
                    throttle_seconds = 0.0
                break

        after_rows = dict((n.strip().lower(), b) for n, b, _li in
                          parse_storage_rows(Gumps.GetLineList(STORAGE_GUMP_ID, True) or []))
        balance_after = after_rows.get(balance_name.strip().lower())
        # WRITE IT TO THE CACHE (2026-09-16) -- the fix for the "holds 38" / "balance 0 -> 0"
        # contradiction the user photographed. This function reads the gump directly rather than
        # through storage_balances(), which is the only writer of STORAGE_BALANCE_CACHE, so every
        # withdrawal left the cache claiming a balance it had just spent. `after_rows` is the
        # freshest complete read of this key anywhere in the file, so it is the right thing to
        # trust -- and a drained row now reads as drained, so the pointless attempt that produced
        # those warnings never starts.
        # MERGE, DO NOT REPLACE (2026-09-19): after_rows is ONE page; replacing the cache with it would drop
        # every other page's rows (Rough Stone on page 1 after a page-2 rune withdrawal).
        STORAGE_BALANCE_CACHE.setdefault((key_name or "").strip().lower(), {}).update(after_rows)
        STORAGE_BALANCE_SCANNED_AT[(key_name or "").strip().lower()] = time.time()

        Gumps.SendAction(STORAGE_GUMP_ID, 0)
        safe_pause(500)

        if balance_before is not None and balance_after is not None and balance_after < balance_before:
            # the balance's own fall, not the amount asked for -- a max request read "Withdrew 60000" (2026-10-18)
            log("Withdrew {} '{}' from {} ({} -> {} left).".format(
                balance_before - balance_after, balance_name, key_name, balance_before, balance_after))
            return True

        if throttle_seconds is not None:
            log("{} withdrawal throttled by the server ({:.1f}s) -- waiting it out and "
                "retrying (attempt {} of {}).".format(
                    key_name, throttle_seconds, attempt + 2, WITHDRAW_MAX_ATTEMPTS), 33)
            safe_pause(int(throttle_seconds * 1000) + WITHDRAW_THROTTLE_MARGIN_MS)
            continue

        # Not throttled and the balance did not move. Could not read it back, or the withdrawal
        # genuinely did nothing -- either way do NOT claim success.
        log("Warning: {} withdrawal of {} '{}' could not be confirmed (balance {} -> {}) "
            "-- not counting it as withdrawn.".format(
                key_name, amount, balance_name, balance_before, balance_after), 33)
        return False

    log("Warning: {} withdrawal of '{}' still throttled after {} attempts.".format(
        key_name, balance_name, WITHDRAW_MAX_ATTEMPTS), 33)
    return False

REAGENTS_CONSUMED_FROM_KEY = True   # Per the user (2026-09-11): "I just learned we don't need to
                                    # withdraw reagents at all, they can be consumed from the
                                    # reagent key in our bag." The Reagent Keys item is carried in
                                    # the backpack, so the craft draws straight from it and the
                                    # pre-withdrawal was never needed.
                                    #
                                    # WHAT SKIPPING IT BUYS, beyond the wasted steps: the withdrawal
                                    # is a full storage-gump open/withdraw/close cycle per craft
                                    # batch, on the SHARED 0x6abce12 gump every storage key uses, and
                                    # it competes for the same per-character action throttle the
                                    # craft itself needs.
                                    #
                                    # AND IT UNBLOCKS 18 RUNES. The reagent step was a FATAL gate, and
                                    # the 18 weapon runes added earlier today carry reagent_amount =
                                    # None (the menu dump gave names and buttons, not reagents), so
                                    # `property_def["reagent_amount"] * runes_planned` raised a
                                    # TypeError -- a crash, not a clean refusal. With the withdrawal
                                    # skipped, all 50 are craftable without reagent data at all.
                                    #
                                    # Set False to restore the old withdraw-first behaviour;
                                    # ensure_reagent() below is kept intact for exactly that.


def ensure_reagent(property_def, needed_total):
    have = count_material(property_def["reagent_match"])
    if have >= needed_total:
        return True
    shortfall = needed_total - have
    log("Need {} more '{}' ({} on hand, {} needed) -- withdrawing from Reagent Keys.".format(
        shortfall, property_def["reagent_storage_row"], have, needed_total))
    withdraw_from_storage_key(REAGENT_KEYS_NAME, property_def["reagent_storage_row"], shortfall)
    have_after = count_material(property_def["reagent_match"])
    return have_after >= needed_total


# =============================================================================
# REQUEST GUMP -- combined quantity + property picker, one round trip. Per the user: a short,
# hand-picked catalog for now, more rows added later the same way.
# =============================================================================

def ask_what_to_craft():
    """Shows the request gump and returns (property_def, quantity), or (None, None) if the user
    closed it without choosing, or typed something that didn't parse as a positive integer."""
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    height = 90 + len(PROPERTY_CATALOG) * 30
    Gumps.AddBackground(gd, 0, 0, 300, height, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 300, height)
    Gumps.AddLabel(gd, 20, 15, 68, "How many?")
    Gumps.AddTextEntry(gd, 120, 15, 100, 20, 68, REQUEST_QUANTITY_ENTRY_ID, "1")
    Gumps.AddLabel(gd, 20, 45, 68, "Pick a property:")

    y = 70
    for i, prop in enumerate(PROPERTY_CATALOG):
        button_id = REQUEST_PROPERTY_BUTTON_BASE + i
        Gumps.AddButton(gd, 20, y, 4005, 4007, button_id, 1, 0)
        Gumps.AddTooltip(gd, "Craft %s runes." % prop["label"])
        Gumps.AddLabel(gd, 55, y + 2, 68, prop["label"])
        y += 30

    Gumps.SendGump(REQUEST_GUMP_ID, Player.Serial, 300, 300, gd.gumpDefinition, gd.gumpStrings)
    log("Choose an amount and a property in the request gump...")

    if not Gumps.WaitForGump(REQUEST_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        log("Warning: request gump timed out with no response.", 33)
        return None, None

    response = Gumps.GetGumpData(REQUEST_GUMP_ID)
    if response is None:
        log("Warning: request gump gave no response data.", 33)
        return None, None

    clicked = response.buttonid
    index = clicked - REQUEST_PROPERTY_BUTTON_BASE
    if index < 0 or index >= len(PROPERTY_CATALOG):
        log("Warning: button {} doesn't map to any property in the catalog.".format(clicked), 33)
        return None, None
    property_def = PROPERTY_CATALOG[index]

    try:
        quantity = int(response.text[0]) if response.text else None
    except (ValueError, IndexError, TypeError):
        quantity = None
    if quantity is None or quantity <= 0:
        log("Warning: '{}' isn't a valid positive quantity.".format(
            response.text[0] if response.text else "(empty)"), 33)
        return None, None
    if quantity > MAX_QUANTITY_SANITY_CAP:
        log("Warning: {} exceeds the sanity cap of {} -- refusing rather than guessing you meant "
            "that many. Run again with a smaller amount.".format(quantity, MAX_QUANTITY_SANITY_CAP), 33)
        return None, None

    return property_def, quantity


# =============================================================================
# RUNE APPLICATION (PHASE 2) -- SAFETY GATE
#
# Just the gate itself for now -- the actual "use rune, target item" application flow hasn't been
# discovered/proven live yet and isn't built here. CONFIRMED so far (ScratchTest.py, phase 2
# round 1): Player.GetSkillValue()/GetRealSkillValue() both work and agreed (120.0) on this
# character; [perks + the same regex PerkTracker.py already uses correctly listed the 5 perks
# actually active and correctly found none matching the (not-yet-active) Perk Deed. NOT yet
# confirmed: the deed's exact live [perks label text (PERK_DEED_LABEL above is a reasoned guess,
# not a live-confirmed string) -- re-run this once the deed is active to verify/correct it.
# =============================================================================

def strip_html_tags(text):
    """Strips gump markup (<BASEFONT COLOR=...>, <CENTER>, <BIG>) down to plain text."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def is_perks_gump(lines, layout):
    """find_gump_by_content() matcher: the gump whose first line reads 'Active Perks'."""
    return bool(lines) and PERKS_GUMP_TITLE in strip_html_tags(lines[0]).lower()


def read_active_perks():
    """{label: naive-UTC datetime} for every active perk. None if the gump could not be read.

    READS THE GUMP (ported 2026-09-16). This scanned the journal for 'Label: ... UTC' lines until
    tonight -- a format [perks stopped printing on 2026-09-08, when it became a gump. Every read
    since has come back empty, so the gate reported the deed inactive with a real one live, and
    the run then drove home hunting a deed it did not need. The journal from that run contains no
    line with 'UTC' at all; the activation broadcast now reads "You have a 10% less break chance
    bonus in rune crafting until 9/16/2026 12:26:01 PM" -- US date, 12-hour, no UTC.

    Omni_Engine.py was ported the morning it broke and PerkTracker.py on 2026-09-13. This is
    the same parse, and the old docstring here claimed to be "the same proven regex PerkTracker.py
    ... uses" while that original had been rewritten eight days earlier.

    ROWS ARE FOUND BY ANCHORING ON THE UTC STAMP and walking BACKWARDS to the first line that is
    neither a duration, another stamp, nor a header -- not by assuming perks begin at a fixed
    index. That survives a perk with no "Time Left" cell, a different header count and an added
    footer. The absolute Expires column is what gets parsed, so this dict keeps its exact previous
    shape and every consumer is untouched.

    None VERSUS {}: None means the gump never appeared (retry the read); {} means it appeared and
    nothing is active (go use a deed). Tonight those were indistinguishable and they call for
    opposite responses, so the caller is given the difference."""
    try:
        Player.ChatSay(0, PERKS_COMMAND)
        wait_for_gump_present(PERKS_GUMP_ID, PERKS_GUMP_WAIT_MS)   # fast path; content still decides
        safe_pause(PERKS_GUMP_SETTLE_MS)
        # BY CONTENT, NEVER "the current gump" -- this file's own rule, and the reason a shard-side
        # gump renumber cannot break this the way the journal change did.
        gump_id = find_gump_by_content(is_perks_gump)
    except Exception as _err:
        log("Warning: could not open the Active Perks gump ({}).".format(_err), 33)
        return None
    if gump_id is None:
        log("Warning: sent {} but no Active Perks gump appeared.".format(PERKS_COMMAND), 33)
        return None
    try:
        lines = [strip_html_tags(l) for l in (Gumps.GetLineList(gump_id, True) or [])]
    except Exception:
        return None

    found = {}
    for i, text in enumerate(lines):
        stamp = PERKS_GUMP_EXPIRES_PATTERN.match(text)
        if not stamp:
            continue
        label = None
        j = i - 1
        while j >= 0:
            candidate = (lines[j] or "").strip()
            if (candidate
                    and not PERKS_GUMP_DURATION_PATTERN.match(candidate)
                    and not PERKS_GUMP_EXPIRES_PATTERN.match(candidate)
                    and candidate.lower() not in PERKS_GUMP_NON_LABELS
                    and "active perk" not in candidate.lower()):
                label = candidate
                break
            j -= 1
        if not label:
            continue
        try:
            found[label] = datetime.datetime.strptime(stamp.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    try:
        Gumps.SendAction(gump_id, 0)   # close it behind us; the journal path left nothing on screen
    except Exception:
        pass
    return found

def active_deed_expiration(perks):
    """The rune-crafting perk's expiration from a read_active_perks() dict, or None.

    THE ONE PLACE THAT KNOWS WHAT THE PERK IS CALLED (2026-09-16). Three call sites used to do
    `perks.get(PERK_DEED_LABEL)` with a label that had quietly been renamed to "Better Rune
    Crafting" -- so all three silently reported the deed inactive, and a run would either refuse to
    apply or burn a fresh deed for nothing.

    Compares NORMALISED WHOLE LABELS against PERK_ACTIVE_LABELS -- see that tuple's own note on why
    a substring test is unsafe here."""
    for label, expiration in (perks or {}).items():
        if (label or "").strip().lower() in PERK_ACTIVE_LABELS:
            return expiration
    return None


# Cache backing the gate's underlying [perks/skill check -- see PERKS_RECHECK_INTERVAL_SECONDS's
# own comment above for why this exists. A plain module-level dict is enough here (mutated in
# place, never reassigned, so no `global` needed in the functions below).
# perk_labels_seen: every label the last [perks read returned. Carried purely so the BLOCKED log
# below can name them -- that is what turns the NEXT rename into a one-line fix instead of the
# screenshot it took this time. Costs nothing; the dict was already read.
_gate_cache = {"last_check_time": 0.0, "skill_ok": False, "deed_expiration": None,
               "perk_labels_seen": (), "perks_readable": False, "read_failures": 0,
               "ibw_expiration": None}

def seed_gate_cache_from_perks(perks):
    """Seeds the gate's cache directly from an ALREADY-fetched perks dict -- used by
    use_perk_deed_if_needed(), which already does its own fresh [perks read(s) for its own
    purposes, so the gate doesn't need to immediately redo a redundant ~2s query the moment
    run_slot_application()'s loop starts."""
    _gate_cache["last_check_time"] = time.time()
    skill = Player.GetSkillValue("Inscription")
    _gate_cache["skill_ok"] = skill >= REQUIRED_INSCRIPTION_SKILL
    _gate_cache["deed_expiration"] = active_deed_expiration(perks)
    _gate_cache["perk_labels_seen"] = tuple(sorted(perks or {}))
    _gate_cache["perks_readable"] = perks is not None
    _gate_cache["ibw_expiration"] = None          # THE WEIGHT IS CHECKED
    for _label, _exp in (perks or {}).items():
        if (_label or "").strip().lower() == IBW_PERK_LABEL:
            _gate_cache["ibw_expiration"] = _exp
    # CONSECUTIVE, not cumulative: any successful read clears it, so a single hiccup in a long
    # healthy batch never accumulates toward the stop below.
    if perks is None:
        _gate_cache["read_failures"] += 1
    else:
        _gate_cache["read_failures"] = 0

def refresh_gate_cache(force=False):
    """Refreshes the cached Inscription/deed state, at most once per
    PERKS_RECHECK_INTERVAL_SECONDS unless force=True. This is the only place that does the
    actual, real [perks/skill queries -- everything else reads the cache."""
    now = time.time()
    if not force and (now - _gate_cache["last_check_time"]) < PERKS_RECHECK_INTERVAL_SECONDS:
        return
    perks = read_active_perks()
    seed_gate_cache_from_perks(perks)

def deed_expiration_known():
    """The cached Perk Deed expiration datetime, or None if not known yet. Pure read of the
    cache -- does not itself trigger a check. Used by run_slot_application() to stop the loop
    proactively before the deed actually runs out (see DEED_STOP_MARGIN_SECONDS)."""
    return _gate_cache["deed_expiration"]

def rune_application_gate_ok():
    """Returns True only if BOTH conditions hold: 300+ Inscription AND the Perk Deed's
    break-chance-reduction perk currently active (not expired). The underlying [perks/skill
    query is throttled to once per PERKS_RECHECK_INTERVAL_SECONDS (refresh_gate_cache()) -- per
    the user, re-verifying with a real ~2s network round trip before every single application was
    excessive once the deed's own expiration is already known. The expiration itself is still
    compared against the current time on EVERY call here (cheap, local, no network) so an
    actually-expired deed is always caught immediately even between refreshes -- this throttles
    how often the check is re-VERIFIED, not whether it's verified at all."""
    refresh_gate_cache()
    if not _gate_cache["skill_ok"]:
        log("Rune application BLOCKED: Inscription is below {:.1f}.".format(REQUIRED_INSCRIPTION_SKILL), 33)
        return False

    expiration = _gate_cache["deed_expiration"]
    if expiration is None:
        # NAME WHAT WE LOOKED FOR *AND* WHAT THE SHARD SAID (2026-09-16). This used to print one
        # guessed label and nothing else, so a rename ("Better Rune Crafting") looked exactly like
        # an expired deed and cost a screenshot to spot. Same rule as absorb_backpack_into_key():
        # on a miss, log every entry we actually saw so the next run hands over the real name.
        # THE READ ITSELF VERSUS AN INACTIVE PERK (2026-09-16). These printed identically as
        # "[perks returned: nothing" -- which is what made a BROKEN READER look like an expired
        # deed and sent the run home to fetch one it already had. They need opposite responses,
        # so they get different messages.
        if not _gate_cache["perks_readable"]:
            log("Rune application BLOCKED: the Active Perks gump could not be read, so whether "
                "the deed is active is UNKNOWN -- not fetching a new one on a failed read.", 33)
        else:
            log("Rune application BLOCKED: no active perk matched {}. The Active Perks gump "
                "listed: {}.".format(list(PERK_ACTIVE_LABELS),
                                     list(_gate_cache["perk_labels_seen"]) or "no perks at all"), 33)
        return False
    remaining = (expiration - datetime.datetime.utcnow()).total_seconds()
    if remaining <= 0:
        log("Rune application BLOCKED: the rune-crafting perk expired {} UTC.".format(expiration), 33)
        return False

    return True

PERK_DEED_ITEM_NAME = "perk deed"  # Matched case-insensitively against Item.Name -- read off the
                                     # deed's own tooltip title line, same reasoned-not-yet-live-
                                     # confirmed basis as PERK_DEED_LABEL itself.

# THE PERK DEED CHEST IS NO LONGER A HARDCODED SERIAL (2026-09-14) -- it was the last one in this
# file, and it broke the rule quoted at the top: "We should not detect based on serial. When shipping
# for other players, they will have different serials." The two backpack items were converted then;
# this one was missed because it is a PLACED GROUND CONTAINER, which find_required_backpack_item()'s
# backpack scan cannot reach.
#
# Identity is now NAME + ItemID -- the same two independent facts REQUIRED_BACKPACK_ITEMS uses --
# captured once by the setup's target cursor and saved to Setup.txt. The live serial is re-resolved
# every call, so it also survives the chest being picked up and re-placed.
# =============================================================================
# FORK -- THE PERK DEED COMES OUT OF THE MASTER KEY
# =============================================================================
#
# Upstream travels to 'Home', finds a named chest on the ground and takes a
# deed out of it. The Master Key is in the pack, so this needs no travel, no
# chest to name or target, and nothing to keep other chests away from.
#
# RECORDED BY HAND, 2026-11-07, and this is the only evidence there is for
# the codex window. Verbatim:
#
#     Items.UseItem(0x4000ABCD)                     <- the Master Keys
#                                                    (EXAMPLE serial: the
#                                                    real one was recorded on
#                                                    one machine and is no use
#                                                    to anyone else. The file
#                                                    resolves the key by NAME,
#                                                    MASTER_KEYS_NAME, and
#                                                    never by a serial.)
#     Gumps.WaitForGump(0xe13358f7, 10000)          <- MASTER_KEYS_GUMP_ID
#     Gumps.SendAction(0xe13358f7, 24)              <- a row's OPEN button
#     Gumps.WaitForGump(0x6abce12, 10000)           <- STORAGE_GUMP_ID
#     Gumps.SendAdvancedAction(0x6abce12, 1, [], [0], ["100"])
#     Gumps.WaitForGump(0xb2f21f1a, 10000)          <- the codex window
#     Gumps.SendAdvancedAction(0xb2f21f1a, 22,  [], [0,1,2,3], ["","break","",""])
#     Gumps.SendAdvancedAction(0xb2f21f1a, 100, [], [0,1,2,3], ["","break","",""])
#     Gumps.SendAdvancedAction(0xb2f21f1a, 0,   [], [0,1,2,3], ["","break","",""])
#     Gumps.SendAdvancedAction(0x6abce12, 0, [], [0], ["100"])
#
# WHAT IS KNOWN AND WHAT IS GUESSED, kept apart on purpose:
#
#   KNOWN  The first two steps are this file's own machinery. 0xe13358f7 is
#          already MASTER_KEYS_GUMP_ID and 0x6abce12 is already
#          STORAGE_GUMP_ID, and the file resolves both by ROW NAME rather
#          than by button id. So those steps are done the file's way, and the
#          recorded ids are only the fallback.
#
#   KNOWN  The deed that comes out is the one this file already looks for.
#          Item Inspector, 2026-11-07: Name "Perk Deed", ItemID 0x14F0, hue
#          0x010d, and its third attribute line is "10% Less Break Chance
#          Applying Rune Crafting Runes To Equipment" - PERK_DEED_ITEM_NAME
#          and PERK_DEED_LABEL unchanged. Everything downstream of the
#          withdrawal therefore needs no change at all.
#
#   KNOWN  What the window IS. Screenshot, 2026-11-07:
#
#              Perk Deeds   Contents: 426/100000   Displayed: 34
#              Name        Perk            Qty   Interval
#              Perk Deed   10% Less Br...   2    Hours
#              Perk Deed   10% Less Br...   1    Hours
#              ...
#              [ break ]>          <Previous Page   [1/3]   Next Page>
#              Purge                Add        Fill from backpack
#
#          So it is the SAME stash-window family as every storage key here -
#          rows, a search box, pages, Purge, Add, Fill from backpack - and
#          "break" in text entry 1 is the search box, exactly as the
#          recording suggested. Each column has its own sort arrows.
#
#   KNOWN  QTY IS THE DURATION and Interval is its unit, per the user:
#          "The QTY is the amount of hours or days, the Interval section
#          shows Hours or days on the perk." So a row reading "2 / Hours" is
#          a two-hour deed and "1 / Hours" is a one-hour one. They are not
#          stack counts, which is what "Qty" would normally mean and what a
#          reader - or a later version of this file - would otherwise assume.
#
#   WANTED  THE ONE-HOUR DEEDS, per the user: "maybe we should only use 1
#          hour ones". See PERK_WANT_QTY / PERK_WANT_INTERVAL below. The
#          window sorts by any column, so the honest way to do this is to
#          sort Qty ascending and take the top row rather than to hunt for a
#          button id - but the sort arrows' button ids are not known yet.
#
#   GUESSED  Which button is which. 22 then 100 then 0, and nothing here can
#          say whether 22 was the search arrow, a row, or a sort control.
#          Note 100 is suspicious: on this same gump family upstream has
#          STORAGE_NEXT_PAGE_BUTTON = 101, so 100 may well be Previous Page
#          rather than anything to do with withdrawing. That is exactly why
#          the dump exists, and why the 1-hour rule is NOT yet wired to a
#          button.
#
# SO THE CODEX PRESSES ARE REPLAYED EXACTLY, and the window is DUMPED to the
# data folder every time until PERK_CODEX_CONFIRMED is set True. The dump is
# what turns the guesses above into row names, and it is the only way to add
# "take the 1 hour ones" as a rule rather than as a button number.

# OFF. 2026-11-07, and this is the honest version of why: it never once
# produced a deed.
#
# What DOES work and is all still below: the Master Keys window opens, the
# codex key opens from it, the codex list opens, and the whole thing closes
# cleanly without disconnecting. What never happened is a deed arriving in
# the pack. The row press goes out, the layout confirms the button is real,
# the codex count does not move and nothing lands.
#
# Two things were ruled out along the way. The codex going 426 -> 427 was
# NOT this file depositing - the user had added one by hand. And the
# buttons are not guesses any more: the layout gives rows 100-114, sorts
# 10/20/30/40, searches 12/22/32/42 and a footer of Add, Purge and Fill.
#
# What is left unexplained is why a confirmed row button does nothing. The
# likeliest remaining candidate is the shard's withdrawal cooldown, which
# upstream documents on this exact shared gump ("You must wait 0.3 more
# seconds before you can withdraw items", added 2026-09-08 and not in the
# changelog) - but that is a guess and it is not worth more of the player's
# time to chase. Set this True to pick it up again; everything is here.
PERK_FROM_MASTER_KEY = False

# The upstream behaviour: recall home and open the perk chest. Correct and
# working, and off here because the recall out of a run is what this fork
# set out to avoid.
PERK_FROM_HOME_CHEST = False

# Check the pack for a deed when an apply run starts and say so, rather
# than letting the run discover it halfway through. It only LOOKS.
PERK_CHECK_AT_START = True

# The Master Keys row that holds the codex, matched the way every other key
# in this file is: the row whose text IS this, else one containing a hint
# below. Change it to whatever your row is actually called - and if it is
# wrong, open_storage_key() lists every row it did find.
# NO NAME RESOLUTION HERE, DELIBERATELY. There was: a PERK_KEY_NAME, a pair
# of row hints and a row-name substring, all resolved against the live gumps
# the way the rest of this file resolves its keys. One of them matched
# something that was not the codex, the press landed on a window with no such
# button, and it DISCONNECTED THE PLAYER (2026-11-07).
#
# They are gone rather than merely unused. Leaving a name-resolution path
# sitting here looking ready is an invitation to wire it back in, and the
# recorded buttons below plus perk_press()'s layout check are what is known
# to work. Resolve by name again only once the codex dump has been read.

# THE RECORDED BUTTONS, used as recorded.
#
# These were name-resolved in the first version and that is what caused the
# disconnect: the row hint matched something that was not the codex, and the
# press went to a window with no such button. The recording is the only
# confirmed-working path, so it is followed exactly - and perk_press() checks
# every one of these against the live layout before sending it, which is what
# makes following a recorded number safe.
PERK_KEY_OPEN_BUTTON = 24         # the codex key's OPEN button on the Master Keys
PERK_CODEX_ROW_BUTTON = 1         # the codex row on that key's storage window

# Waits and the settle after each window. "Put a delay and make sure it comes
# up" - the settle is what stops a press landing on a window that is drawn but
# not yet populated.
PERK_MASTER_WAIT_MS = 10000
PERK_STORAGE_WAIT_MS = 10000
PERK_SETTLE_MS = 700

# The amount sent with the storage press. The recording carried "100" in the
# window's single text entry, so that is what is replayed.
#
# THIS IS A TEXT ENTRY BEING WRITTEN TO, which is worth saying out loud: on
# this same gump id, pressing a button with a text payload the window did not
# have is what disconnected the client once before, in another script. The
# value below is the one the recording sent and the window accepted. Do not
# "tidy" this into a plain SendAction, and do not change the number.
PERK_STORAGE_AMOUNT = "100"

# The search box at the bottom left, which the recording had "break" typed
# into. It narrows the list to the break-chance deeds, so it is part of the
# sequence rather than a leftover.
PERK_CODEX_SEARCH = "break"

# The codex window, and the presses recorded against it.
PERK_CODEX_GUMP_ID = 0xB2F21F1A
PERK_CODEX_WAIT_MS = 10000
PERK_CODEX_TEXT_IDS = [0, 1, 2, 3]
PERK_CODEX_TEXTS = ["", PERK_CODEX_SEARCH, "", ""]
# ---------------------------------------------------------------------------
# WHICH ROW TO TAKE: SORT, DO NOT READ.
#
# The columns are confirmed, left to right (user, 2026-11-07):
#
#     Name      always "Perk Deed"; never varies, so it decides nothing
#     Perk      the perk itself - "10% Less Break Chance Applying Rune
#               Crafting Runes To Equipment"
#     QTY       a bare number: how many days or hours
#     Interval  "Hours" or "Days"
#
# And a recording of one press on each column's up arrow pins the sort
# buttons to those columns in order: 10, 20, 30, 40. So 30 is QTY ascending.
#
# WHY SORTING RATHER THAN READING THE ROWS. The cells cannot be read
# reliably on this window - RazorEnhanced drops empty strings and this
# gump's search boxes put their own text into the line list, so every
# attempt to pair a cell to its text came out shifted. Sorting sidesteps
# that completely: press QTY ascending and the smallest number is on top,
# whatever the list holds and however it changes. Nothing has to be parsed,
# so nothing can be parsed wrong.
#
# "Using only 1 hour here is needed as to not waste the perk times" - the
# point is to spend the SHORTEST deed, so ascending is the right direction
# and the top row is the right row.
#
# AND THE RESULT IS CHECKED AGAINST THE DEED ITSELF, not against the gump:
# after the withdrawal the deed's own properties are read and logged. If the
# sort ever runs the other way, or a "1 Days" sorts level with a "1 Hours",
# that shows up in the log as the duration that actually arrived rather than
# as a silent waste.
PERK_CODEX_SORT_QTY_UP = 30       # QTY ascending
PERK_CODEX_TOP_ROW = 100          # the first row, once sorted

# Sort first, then take the top row. Both are checked against the live
# layout, and neither can be Add, Fill or Purge - those are refused by name.
PERK_CODEX_PRESSES = (PERK_CODEX_SORT_QTY_UP, PERK_CODEX_TOP_ROW)

PERK_CODEX_CLOSE_BUTTON = 0

# The gump protocol's cancel. Never drawn, so never in a layout - see
# perk_press(), which exempts it from the layout check for that reason.
PERK_CANCEL_BUTTON = 0

# ---------------------------------------------------------------------------
# THE CODEX WINDOW, DECODED FROM ITS OWN LAYOUT (dump of 2026-11-07 23:11).
#
# Fifteen row buttons down the left at x=20, ids 100..114, one per 20px line
# from y=93 to y=373. Four cells per row at x=40, 190, 290, 390. Per column:
# a header at y=50, a sort pair just under it, a search box at y=412 and a
# search submit beside it.
#
#     column       header  sort up/down  search submit  search entry id
#     x=40                 10 / 11       12             0
#     x=190                20 / 21       22             1
#     x=290                30 / 31       32             2
#     x=390                40 / 41       42             3
#
#     footer: 5 = the gump's own corner button
#             1 = Add            (x=300 y=475)
#             3 = Purge          (x=100 y=475, drawn in RED hue 37)
#             2 = Fill from backpack (x=300 y=505)
#
# SO THE RECORDING WAS A ROW PRESS AFTER ALL. "22" is the search submit for
# the second column and "100" is the FIRST ROW - not Previous Page, which was
# the earlier guess. Pressing 100 should withdraw the top row.
#
# WHICH COLUMN IS WHICH IS STILL NOT SETTLED. The line list cannot be lined up
# with the layout on this window: RazorEnhanced drops empty strings, and this
# gump's search boxes put their own text into the list (upstream's reader
# documents the opposite - "a text entry's own string is never in it"), so
# every attempt to pair cell to text came out shifted by one or more. The
# header row reads "Name" at x=40 and then disagrees with the screenshot about
# the rest.
#
# WHICH IS WHY NOTHING IS ASSUMED BELOW. Only row buttons may be pressed, the
# duration that actually arrives is logged, and the three buttons that can
# lose deeds are refused outright.
# ---------------------------------------------------------------------------

# The only ids on the codex this file will ever press.
PERK_CODEX_ROW_BUTTONS = tuple(range(100, 115))

# NEVER PRESSED, whatever else changes. Add and Fill from backpack put deeds
# IN and Purge destroys them; none of the three is anything a withdrawal
# needs, so they are refused by name rather than merely left out of a list
# somebody might later extend.
#
# NOT BECAUSE THEY WERE EVER PRESSED. A run of this file was blamed for the
# codex going from 426 to 427 - it had pressed two buttons nobody had
# identified yet, and a deposit fitted. It was wrong: the user had added a
# deed by hand, and the count never moved from anything this file did. The
# guard is right on its own merits and the reason it was first written down
# was not, which is worth saying here so nobody reasons from the wrong one.
PERK_CODEX_FORBIDDEN = {1: "Add", 2: "Fill from backpack", 3: "Purge"}


# WHICH DEED TO TAKE. Qty is the duration and Interval is its unit, so this
# pair reads "a one-hour deed".
#
# NOT YET ENFORCED. Reading the rows needs the window's layout - which button
# belongs to which row - and that is what the dump below is for. Until then
# the recorded presses are replayed as they are, and the log says which row
# actually came out so a wrong one is visible rather than silent.
PERK_WANT_QTY = 1
PERK_WANT_INTERVAL = "hours"

# Dump the codex window to the data folder on every withdrawal. Set True once
# its rows are known and the presses above have been replaced by name lookups.
PERK_CODEX_CONFIRMED = False
PERK_CODEX_DUMP_FILE = "PerkCodex_GumpDump.txt"
PERK_CHEST_NAME_KEY = "perk_chest_name"
PERK_CHEST_ID_KEY = "perk_chest_id"
PERK_CHEST_SEARCH_RANGE = 3   # Tiles. This is a container the player is STANDING AT after travelling
                                # home, not something to hunt for -- a wide radius would risk
                                # matching a neighbour's identically-named chest through a wall.
# NO FALLBACK SERIAL (2026-09-14), per the user: "remove the legacy serial fallback, that defeats
# the purpose." One was kept here briefly for compatibility and it was wrong twice over. It MASKED
# THE UNCONFIGURED STATE -- an install with nothing saved still resolved a chest, so the setup row
# came up green and the gump never drew, blinding setup to the one case it exists for. And it could
# only ever have worked on the machine it came from: a serial belonging to one player's chest
# resolves for nobody else, so every other player got None from it anyway, just without being asked
# to fix it. Unconfigured now means None, which means a red row and a setup prompt.
#
# (The chest itself is the "Glimmering Chest Of Belongings" that Omni_Engine.py's
# use_now_perk_deeds() sorts rune-break Perk Deeds INTO during Combat Dropoff; this script pulls
# from the same one, which is why both files once knew its serial.)


def configured_perk_chest():
    """(name, item_id) captured by setup, or ("", None) when never configured."""
    name = setup_get(PERK_CHEST_NAME_KEY, "")
    raw_id = setup_get(PERK_CHEST_ID_KEY, "")
    try:
        item_id = int(raw_id) if raw_id else None
    except ValueError:
        item_id = None
    return name, item_id


def find_perk_deed_chest():
    """The live chest Item, or None. Resolved fresh -- never a remembered serial.

    Searches the GROUND near the player, because this is a placed container at home rather than a
    backpack item. Matches NAME and ItemID together: two independent facts, the same belt-and-braces
    REQUIRED_BACKPACK_ITEMS applies, so a lookalike graphic under a different name is not mistaken
    for it.

    Returns None when nothing has been configured -- that is not a failure, it is the state the
    first-run setup exists to catch, and answering it with a hardcoded serial is what used to keep
    the setup gump from ever appearing."""
    found = perk_deed_chests_here()
    return found[0] if len(found) == 1 else None


def perk_deed_chests_here():
    """Every chest within PERK_CHEST_SEARCH_RANGE matching the configured name and ItemID.

    ONE OR NONE (owner, 2026-10-18: "it opened a random glimmering chest"). Every house chest is "a glimmering chest of
    belongings" until it is renamed, so several can match at home; the first one found was opened. find_perk_deed_chest()
    takes a chest only when it is the one match, and the callers say so when several look alike."""
    name, item_id = configured_perk_chest()
    if not name and item_id is None:
        return []
    wanted = (name or "").strip().lower()
    out = []
    try:
        fil = Items.Filter()
        fil.Enabled = True
        fil.OnGround = True
        fil.RangeMax = PERK_CHEST_SEARCH_RANGE
        for it in (Items.ApplyFilter(fil) or []):
            if wanted and (it.Name or "").strip().lower() != wanted:
                continue
            if item_id is not None and it.ItemID != item_id:
                continue
            out.append(it)
    except Exception:
        pass
    return out


def perk_chest_lookalikes_line(count):
    """The words for ONE OR NONE when several chests match."""
    return ("{} chests here are all called '{}', so which one holds the Perk Deeds can't be told apart. Rename yours "
            "in game, then Target it again in Setup.".format(count, configured_perk_chest()[0]))

def check_recent_action_throttle():
    """Scans recent journal entries for the server's ITEM MANIPULATION throttle message, "you must
    wait to perform another action" -- ported (2026-08-27) from Omni_Engine.py's own proven
    function of the same name, per a live capture: "It withdrew the perk deed, but didn't use it.
    Item manipulation blocking." withdraw_perk_deed_from_home_chest()'s own Items.Move() and the
    immediately-following Items.UseItem() in use_perk_deed_if_needed() are exactly the collision
    shape Omni_Engine.py's own docstring for this function already warns about: "It can
    silently swallow an Items.UseItem() call (e.g. right after a recent Items.Move from trash
    sorting) with no other visible symptom than the expected response never arriving." Match is
    deliberately narrowed to "to perform another action" (not a bare "you must wait" substring) so
    an unrelated Skills/Spells throttle message can't be misread as this specific collision."""
    journal_lines = Journal.GetJournalEntry(None)
    if not journal_lines:
        return False
    for line in journal_lines:
        if "to perform another action" in (line.Text or "").lower():
            Journal.Clear()
            return True
    return False

def find_perk_deed(container=None):
    """The Perk Deed inside `container` (default: the backpack) whose property text matches
    PERK_DEED_LABEL specifically (there could in principle be other, unrelated deed types with the
    same generic item name). Returns the item, or None if not found.

    container parameter ADDED (2026-08-27) so withdraw_perk_deed_from_home_chest() can reuse this
    SAME matching logic against the perk deed chest's own Contains instead of
    duplicating the property-check loop -- per the user: "Instead of stopping when we're out of
    perk deed, go ahead and grab another from the chest they are stored in during combat dropoff
    and use it instead." Previously backpack-only by design ("a possible future addition, not
    built here") -- this is that addition."""
    if container is None:
        container = Player.Backpack
    target_label = PERK_DEED_LABEL.strip().lower()
    for it in container_items(container):
        if (it.Name or "").strip().lower() != PERK_DEED_ITEM_NAME:
            continue
        try:
            Items.WaitForProps(it, 1000)
            props = Items.GetPropStringList(it) or []
        except Exception:
            props = []
        for p in props:
            if target_label in (p or "").strip().lower():
                return it
    return None

def withdraw_perk_deed_from_home_chest():
    """Travels home, opens the perk deed chest (see find_perk_deed_chest()), and withdraws ONE Perk Deed
    into the backpack -- the fetch-from-storage half use_perk_deed_if_needed() used to explicitly
    skip. No return trip needed afterward: applying a rune has never required Scribe proximity (see
    run_application_flow()'s own docstring), so staying home once the deed is in hand is fine.

    Returns the withdrawn Item (re-confirmed via a fresh find_perk_deed() against the backpack
    itself, not just trusting the Move), or None if travel failed, the chest couldn't be found, or
    it genuinely had no matching deed either (real out-of-stock, not just a local shortfall)."""
    log("No Perk Deed on hand -- traveling home to fetch one from storage...", 68)
    if not ar_go_folders(home_folder()) or not ar_go_dest(home_point()):
        log("Warning: could not travel home to fetch a Perk Deed from storage.", 33)
        return None

    # RESOLVE BEFORE OPENING (2026-09-14). This used to UseItem() a hardcoded serial and only then
    # FindBySerial() to check the chest existed -- opening something before confirming it is there.
    # find_perk_deed_chest() matches name + ItemID on the ground here at home; see its docstring.
    chest = find_perk_deed_chest()
    _alike = len(perk_deed_chests_here()) if not chest else 1
    if _alike > 1:                       # ONE OR NONE
        log("Not opening a chest: " + perk_chest_lookalikes_line(_alike), 33)
        return None
    if not chest:
        log("Warning: could not find the Perk Deed storage chest here. If this is a fresh install, "
            "run setup and target it; otherwise it may have moved.", 33)
        return None

    Items.UseItem(chest.Serial)
    safe_pause(GUMP_RESPONSE_SETTLE_MS)

    deed = find_perk_deed(chest)
    if not deed:
        log("Warning: no Perk Deed available in home storage either -- genuinely out of stock.", 33)
        return None

    log("Withdrawing Perk Deed (Serial={}) from home storage...".format(hex(deed.Serial)))
    # (2026-10-10) THE MOVE IS SENT AGAIN: a refused withdrawal no longer reads as "none in storage".
    item_move_sent(deed.Serial, Player.Backpack.Serial, max(PRE_WAIT_SETTLE_MS, 1000))

    withdrawn = find_perk_deed()
    if not withdrawn:
        log("Warning: moved a Perk Deed from storage but it isn't showing in the backpack yet.", 33)
    return withdrawn

def perk_codex_dump(tag):
    """Write the codex window's lines and layout to the data folder.

    FORK. The recorded presses (22, then 100) are button NUMBERS, and the
    rule actually wanted is "take the 1 hour ones" - a name. Nothing here
    can turn one into the other without seeing the window, and the window
    has never been read. So it is written down every time until somebody
    says it has been read.

    Failing to dump is never allowed to fail a withdrawal: the deed matters
    and the diagnostic does not.
    """
    if PERK_CODEX_CONFIRMED:
        return
    try:
        lines = [str(l) for l in
                 (Gumps.GetLineList(PERK_CODEX_GUMP_ID, False) or [])]
        data = [str(l) for l in
                (Gumps.GetLineList(PERK_CODEX_GUMP_ID, True) or [])]
        try:
            # GetGumpRawLayout(gump_id), which is what every other read in
            # this file uses. The first version called LastGumpGetLayout(),
            # which took no id and returned nothing, so the dump that was
            # supposed to answer "which button is which" captured only text.
            layout = str(Gumps.GetGumpRawLayout(PERK_CODEX_GUMP_ID) or "")
        except Exception as err:
            layout = "(layout unreadable: %s)" % err
        if not layout:
            layout = "(layout empty)"
        if not ensure_script_data_dir():
            return
        # open(), not io.open(): this file does not import io, and the
        # dump is not worth an import nobody else needs.
        with open(script_data_path(PERK_CODEX_DUMP_FILE), "a",
                  encoding="utf-8") as fh:
            fh.write("=== %s  %s ===\n"
                     % (tag, datetime.datetime.utcnow().isoformat()))
            fh.write("-- lines (all) --\n")
            for line in lines:
                fh.write("  %s\n" % line)
            fh.write("-- lines (data only) --\n")
            for line in data:
                fh.write("  %s\n" % line)
            fh.write("-- layout --\n%s\n\n" % layout)
        log("Perk codex window written to {} -- send it over and the "
            "button numbers below can become row names."
            .format(PERK_CODEX_DUMP_FILE), 68)
    except Exception as err:
        log("(could not dump the perk codex window: {})".format(err), 68)


def gump_button_ids(gump_id):
    """Every button id in the window AS IT IS ON SCREEN NOW, or an empty set.

    FORK, 2026-11-07. THE GUARD THAT MATTERS: sending a button id a window
    does not have DISCONNECTS THE CLIENT. That is not a theory - it took the
    player off the shard twice, once in this file's perk withdrawal and once
    before that in another script of theirs, on this very gump id.

    AN EMPTY SET MEANS "DO NOT PRESS ANYTHING". It is returned when the
    layout cannot be read at all, which is exactly when guessing is worst.
    Callers must treat empty as a refusal, never as "no restrictions".

    This also stands in for a freshness check, which Razor cannot give us
    directly: Gumps.HasGump() answers True for any id Razor has SEEN this
    session, and 0x6abce12 is shared by every storage key here, so it is
    True from the moment the first key is opened and says nothing about what
    is on screen. A layout carrying the button we want is the closest thing
    to proof available.
    """
    try:
        layout = Gumps.GetGumpRawLayout(gump_id)
    except Exception:
        return set()
    if not layout:
        return set()
    found = set()
    for piece in re.split(r"\}\s*\{", str(layout)):
        if "button" not in piece.lower():
            continue
        numbers = re.findall(r"\d+", piece)
        if numbers:
            found.add(int(numbers[-1]))
    return found


def gump_textentry_ids(gump_id):
    """Every text entry id in the window as it is now, or an empty set.

    FORK. A press carrying a text payload for a field the window does not
    have is the same crash by another route - it is what dropped Sandmaker
    on this gump id - so the payload is filtered against this before it is
    sent, and a window with no fields gets a plain SendAction.
    """
    try:
        layout = Gumps.GetGumpRawLayout(gump_id)
    except Exception:
        return set()
    if not layout:
        return set()
    found = set()
    for piece in re.split(r"\}\s*\{", str(layout)):
        low = piece.lower()
        if "textentry" not in low:
            continue
        numbers = re.findall(r"\d+", piece)
        if len(numbers) >= 6:
            # {textentry x y w h hue entryID initialTextID}: the entry id is
            # the sixth number. Taken positionally because the last number is
            # the INITIAL TEXT id, not the field id.
            found.add(int(numbers[5]))
    return found


def perk_press(gump_id, button, what, text_ids=None, texts=None):
    """Press ONE button, and only once the window is proved to have it.

    FORK. Every press in the perk withdrawal goes through here. True when it
    was sent, False when it was refused - and a refusal is a normal outcome
    that the caller stops on, never something to retry with a guess.
    """
    if not Gumps.HasGump(gump_id):
        log("Perk codex: {} -- 0x{:X} is not open at all.".format(what, gump_id), 33)
        return False

    # BUTTON 0 IS NOT A BUTTON. It is the gump protocol's CANCEL - what the
    # client sends when a window is closed - so it is never drawn and never
    # appears in a layout. Checking it against the layout refused every
    # close this function made, which is why the storage window sat open
    # after a refused row press (2026-11-07). Upstream sends
    # SendAction(id, 0) unguarded in four places for the same reason.
    #
    # NO PAYLOAD WITH IT EITHER. A cancel carrying text for fields the
    # window may not have is the crash this whole guard exists to prevent,
    # and a close has nothing to say.
    if button == PERK_CANCEL_BUTTON:
        try:
            Gumps.SendAction(gump_id, PERK_CANCEL_BUTTON)
            return True
        except Exception as err:
            log("Perk codex: {} -- the close failed ({}).".format(what, err), 33)
            return False

    # THE THREE THAT LOSE DEEDS. Checked before anything else, because a
    # layout check cannot save you from a button that is really there and
    # really does the wrong thing: Add and Fill from backpack deposit, and
    # Purge destroys. A withdrawal never needs any of them.
    if gump_id == PERK_CODEX_GUMP_ID and button in PERK_CODEX_FORBIDDEN:
        log("Perk codex: REFUSING button {} -- that is '{}', and it would "
            "add to or empty the codex rather than take one deed out."
            .format(button, PERK_CODEX_FORBIDDEN[button]), 33)
        return False

    present = gump_button_ids(gump_id)
    if not present:
        log("Perk codex: {} -- could not read 0x{:X}'s layout, so nothing is "
            "pressed. Pressing blind is what disconnects the client."
            .format(what, gump_id), 33)
        return False
    if button not in present:
        log("Perk codex: {} -- button {} is NOT in 0x{:X}. It has: {}. "
            "Refusing to press it."
            .format(what, button, gump_id,
                    ", ".join(str(b) for b in sorted(present))), 33)
        return False

    wanted_ids = list(text_ids or [])
    wanted_texts = list(texts or [])
    if wanted_ids:
        have = gump_textentry_ids(gump_id)
        keep = [(i, t) for i, t in zip(wanted_ids, wanted_texts) if i in have]
        if len(keep) != len(wanted_ids):
            log("Perk codex: 0x{:X} has text fields {} -- sending only those."
                .format(gump_id, ", ".join(str(i) for i in sorted(have))
                        or "none"), 68)
        wanted_ids = [i for i, _t in keep]
        wanted_texts = [t for _i, t in keep]

    try:
        if wanted_ids:
            Gumps.SendAdvancedAction(gump_id, button, [], wanted_ids,
                                     wanted_texts)
        else:
            Gumps.SendAction(gump_id, button)
    except Exception as err:
        log("Perk codex: {} -- the press failed ({}).".format(what, err), 33)
        return False
    return True


def perk_wait_for(gump_id, timeout_ms, what):
    """Wait for a window and settle. True once it is up.

    FORK. `is None` IS THE TEST, not truthiness: wait_for_gump_present()
    answers 0 for a window that is already up, and `if not 0` read that as a
    failure in the first version of this - which is half of how the perk
    withdrawal ended in a disconnect.
    """
    waited = wait_for_gump_present(gump_id, timeout_ms)
    if waited is None:
        log("Perk codex: {} did not appear within {}ms.".format(
            what, timeout_ms), 33)
        return False
    safe_pause(PERK_SETTLE_MS)
    return True


def withdraw_perk_deed_from_master_key():
    """Take ONE Perk Deed out of the Master Key's perk codex. The Item, or None.

    FORK. Rewritten 2026-11-07 after the first version DISCONNECTED the
    player. See perk_press(): nothing here presses a button without first
    reading the window's layout and finding that button in it.

    THE MASTER KEYS WINDOW STAYS OPEN, per the user: "The masterkey stays
    open, so the menu is always up." So this does not open it - it confirms
    it is up and works from there, which is exactly what the second
    recording does:

        Gumps.WaitForGump(0xe13358f7, 10000)
        Gumps.SendAction(0xe13358f7, 24)
        Gumps.WaitForGump(0x6abce12, 10000)
        Gumps.SendAdvancedAction(0x6abce12, 1, [], [0], ["100"])

    THE RECORDED BUTTONS ARE USED AS RECORDED. Resolving the row by name is
    what went wrong the first time: the hint matched something that was not
    the codex, and the press landed on a window that had no such button. The
    recording is the only confirmed-working path there is, so it is followed
    - and every press in it is checked against the live layout first, which
    is what makes following it safe.
    """
    log("No Perk Deed on hand -- taking one from the Master Keys...", 68)

    if not perk_wait_for(MASTER_KEYS_GUMP_ID, PERK_MASTER_WAIT_MS,
                         "the Master Keys window"):
        log("Open your Master Keys and leave it open, then try again.", 33)
        return None

    if not perk_press(MASTER_KEYS_GUMP_ID, PERK_KEY_OPEN_BUTTON,
                      "opening the perk codex key"):
        return None

    if not perk_wait_for(STORAGE_GUMP_ID, PERK_STORAGE_WAIT_MS,
                         "the codex key's storage window"):
        return None

    opened_codex = False
    try:
        if not perk_press(STORAGE_GUMP_ID, PERK_CODEX_ROW_BUTTON,
                          "opening the codex list",
                          [0], [PERK_STORAGE_AMOUNT]):
            return None

        if not perk_wait_for(PERK_CODEX_GUMP_ID, PERK_CODEX_WAIT_MS,
                             "the codex list"):
            return None
        opened_codex = True
        perk_codex_dump("codex opened")
        if not PERK_CODEX_PRESSES:
            log("Perk codex: opened and written to {} -- and NOTHING was "
                "pressed in it, because no press is configured. Send that "
                "file over.".format(PERK_CODEX_DUMP_FILE), 33)

        for press in PERK_CODEX_PRESSES:
            what = ("sorting by QTY, smallest first"
                    if press == PERK_CODEX_SORT_QTY_UP
                    else "taking the top row"
                    if press in PERK_CODEX_ROW_BUTTONS
                    else "codex step %d" % press)
            if not perk_press(PERK_CODEX_GUMP_ID, press, what,
                              list(PERK_CODEX_TEXT_IDS),
                              list(PERK_CODEX_TEXTS)):
                return None
            # The window may close itself on the press that completes the
            # withdrawal, and that is a success, not a failure to wait for.
            if not Gumps.HasGump(PERK_CODEX_GUMP_ID):
                opened_codex = False
                break
            safe_pause(PERK_SETTLE_MS)
            perk_codex_dump("after codex button %d" % press)
    finally:
        # ONLY WHAT IS PROVABLY THERE. perk_press refuses a window it cannot
        # read, so a close sent at nothing is refused rather than sent - and
        # a close sent at nothing is how this disconnected the player once.
        if opened_codex:
            perk_press(PERK_CODEX_GUMP_ID, PERK_CODEX_CLOSE_BUTTON,
                       "closing the codex list",
                       list(PERK_CODEX_TEXT_IDS), list(PERK_CODEX_TEXTS))
            safe_pause(PERK_SETTLE_MS)
        perk_press(STORAGE_GUMP_ID, 0, "closing the storage window",
                   [0], [PERK_STORAGE_AMOUNT])

    withdrawn = find_perk_deed()
    if not withdrawn:
        log("Perk codex: the sequence ran but no Perk Deed is showing in "
            "the backpack. If {} was written, send it over."
            .format(PERK_CODEX_DUMP_FILE), 33)
        return None
    log("Withdrew a Perk Deed from the Master Keys (Serial={}).".format(
        hex(withdrawn.Serial)))
    # WHICH ONE, out loud. PERK_WANT_QTY is not enforced yet (the codex rows
    # cannot be read until its layout is known), so the duration that
    # actually came out has to be visible rather than assumed.
    # CHECKED AGAINST THE DEED, not against the gump. The sort is what
    # picks the row, so the only honest proof it picked the right one is
    # what actually arrived in the pack.
    try:
        Items.WaitForProps(withdrawn, 1000)
        want = "{} {}".format(PERK_WANT_QTY, PERK_WANT_INTERVAL)
        shown = None
        for prop in (Items.GetPropStringList(withdrawn) or []):
            text = (prop or "").strip()
            if text and PERK_WANT_INTERVAL in text.lower():
                shown = text
                break
        if shown is None:
            log("  (its duration is not in the tooltip -- cannot tell which "
                "one this is)", 68)
        elif want.lower() in shown.lower():
            log("  it is a {} deed, which is the one to spend.".format(want))
        else:
            log("  it reads '{}' and a {} one was wanted. The QTY sort may "
                "be running descending -- say so and the arrow is one "
                "number away ({} instead of {}).".format(
                    shown, want, PERK_CODEX_SORT_QTY_UP + 1,
                    PERK_CODEX_SORT_QTY_UP), 33)
    except Exception:
        pass
    return withdrawn


def stock_perk_deed_at_start():
    """FORK. Say at the START whether a Perk Deed is on hand. True if one is.

    IT ONLY LOOKS. Per the user, 2026-11-07: "lets just ignore it and have it
    check the pack, i'll do it myself." Nothing is withdrawn, nothing is
    travelled to - the deed is theirs to put in the pack, and this just says
    early whether it is there instead of letting the run find out halfway
    through.

    Saying it EARLY is the whole value. The gate that spends the deed sits
    inside the apply loop, so without this the first anyone hears of a
    missing deed is after the crafting is done.

    NEVER HALTS THE RUN. Upstream deleted a deed gate from this same spot
    because it "made a deed a precondition for CRAFTING, which has never
    needed one", and that reasoning is untouched here.
    """
    if not PERK_CHECK_AT_START:
        return False
    if find_perk_deed() is not None:
        log("Perk Deed on hand.")
        return True
    log("No Perk Deed in the pack. Crafting runs fine without one; it is "
        "only needed at the moment runes are applied, and the break chance "
        "is higher without it. Drop one in before then.", 33)
    return False


def withdraw_perk_deed():
    """FORK. Where a deed comes from when the pack has none: nowhere, by default.

    BOTH SOURCES ARE OFF. The Master Key codex never worked - see
    PERK_FROM_MASTER_KEY - and the home chest costs a recall out of the run,
    which was the thing this fork set out to avoid. Per the user: "i'll do it
    myself."

    The upstream chest path is still here and still correct; it is one word
    away (PERK_FROM_HOME_CHEST) for anyone who wants it back.
    """
    if PERK_FROM_MASTER_KEY:
        deed = withdraw_perk_deed_from_master_key()
        if deed:
            return deed
    if PERK_FROM_HOME_CHEST:
        return withdraw_perk_deed_from_home_chest()
    log("No Perk Deed in the pack, and this fork does not go looking for "
        "one: the Master Key codex is off and so is the trip to the home "
        "chest. Carry a deed, or set PERK_FROM_HOME_CHEST = True.", 33)
    return None


def use_perk_deed_if_needed():
    """Checks whether the Perk Deed buff is already active via a fresh [perks read; if not, uses
    one from the backpack (if present) and re-checks. Called once, right before an application
    run starts. Seeds the gate's cache from whichever [perks read succeeds here (see
    seed_gate_cache_from_perks()) so run_slot_application()'s first gate check doesn't redo a
    redundant fresh query moments later. Returns True if the buff is confirmed active by the end
    of this call.

    FALLS BACK to withdraw_perk_deed_from_home_chest() (2026-08-27) when the backpack has none --
    per the user: "Instead of stopping when we're out of perk deed, go ahead and grab another from
    the chest they are stored in during combat dropoff and use it instead." Only genuinely stops if
    home storage is ALSO empty."""
    perks = read_active_perks()
    expiration = active_deed_expiration(perks)
    if expiration and (expiration - datetime.datetime.utcnow()).total_seconds() > 0:
        log("Perk Deed buff already active.")
        seed_gate_cache_from_perks(perks)
        return True

    deed = find_perk_deed()
    if not deed:
        deed = withdraw_perk_deed()        # FORK: Master Key, then the chest
    if not deed:
        log("No Perk Deed in the backpack to use, none is currently active, and none is available "
            "in home storage either.", 33)
        return False

    log("Using Perk Deed (Serial={})...".format(hex(deed.Serial)))
    Journal.Clear()  # So check_recent_action_throttle() below only reflects THIS attempt's own
                       # UseItem, not a stale hit from an earlier, unrelated action (e.g. the
                       # Items.Move that may have JUST withdrawn this same deed from home storage).
    Items.UseItem(deed.Serial)
    safe_pause(1000)

    # RETRY on throttle (2026-08-27), per a live capture: "It withdrew the perk deed, but didn't
    # use it. Item manipulation blocking." A deed withdrawn from withdraw_perk_deed_from_home_
    # chest() right before this call is exactly the "UseItem right after a recent Items.Move"
    # collision check_recent_action_throttle()'s own docstring warns about -- the shard's real
    # per-character item-manipulation throttle can silently swallow the UseItem with no symptom
    # other than the buff never showing active. One retry once the throttle clears.
    if check_recent_action_throttle():
        log("Perk Deed use was throttled (recent item manipulation) -- retrying once...", 68)
        Items.UseItem(deed.Serial)
        safe_pause(1000)

    perks = read_active_perks()
    expiration = active_deed_expiration(perks)
    if expiration and (expiration - datetime.datetime.utcnow()).total_seconds() > 0:
        log("Perk Deed is now active.")
        seed_gate_cache_from_perks(perks)
        return True

    log("Warning: used a Perk Deed but the buff still isn't showing as active.", 33)
    return False


# =============================================================================
# RUNE APPLICATION (PHASE 2) -- SLOT CATALOG + PICKER GUMPS
#
# CONFIRMED live (ScratchTest.py, slot-matching round 1): Item.Layer correctly reports an item's
# equip slot even while it's sitting unworn in the backpack -- three "Ranger's Cloak of
# Augmentation" items showed Layer='Cloak' despite not being worn, confirming backpack items can
# be matched to a slot type by Item.Layer alone, no name-substring matching needed.
# Player.GetItemOnLayer(layerName) also works, with exact-case standard layer name strings
# ('Cloak', 'OuterTorso', 'MiddleTorso', 'InnerTorso', 'Shirt', 'Pants', 'Shoes', 'Gloves',
# 'Head', 'Neck', 'Waist', 'Arms', 'Ring', 'Bracelet', 'Earrings', 'LeftHand', 'RightHand') --
# not needed for backpack matching, but useful later if a slot ever needs to check what's
# currently worn. Player.Contains does NOT exist (raises AttributeError) -- not needed either way.
#
# Per the user: there is no per-item completion threshold -- each rune application adds a random
# amount within that property's wiki-listed range, uncapped, so runes can be applied to an item
# indefinitely. The only real constraint is breakage risk, so a slot-crafting run works across
# EVERY eligible item of the chosen slot at once, always applying the next rune to whichever
# eligible item currently has the LOWEST value of the target property (an item with none of that
# property yet counts as lowest) -- spreading risk instead of maxing one item out first. It stops
# only when the eligible item count drops to 1 (protects the last one) or the crafted-rune supply
# for that property runs out. NOT YET BUILT: reading an item's CURRENT value of a given property
# (needs tooltip/property-string parsing, e.g. "Spell Damage Increase X%") and the actual
# use-rune-on-item interaction itself -- both still completely unexplored, so the automation loop
# itself isn't wired up yet. What's here is just the picker gump (stat thresholds AND slot choice,
# COMBINED on one screen -- see ask_apply_requests_and_slot()'s own docstring) and the Layer-based
# item-matching helper.
# =============================================================================

# Every entry below is a layer string CONFIRMED live in slot-matching round 1 --
# Player.GetItemOnLayer(layer) returned a real worn item, AND that item's OWN .Layer property
# matched the string it was looked up by, confirming find_slot_items()'s Item.Layer == layer
# backpack-matching will work correctly for it. 'RightHand' is deliberately EXCLUDED: it's the
# one layer that did NOT round-trip cleanly in that same test -- Player.GetItemOnLayer('RightHand')
# returned a real item (a spellbook), but that item's own .Layer read back as 'FirstValid', not
# 'RightHand'. Since backpack items are matched by their own .Layer value, a RightHand entry
# would risk silently failing to find genuine right-hand items sitting in the backpack. Only one
# data point exists for RightHand (a spellbook, which UO has historically treated specially for
# hand-layer purposes) -- a weapon might behave differently, but that's unconfirmed, so RightHand
# stays out until it's specifically verified rather than assumed either way.
# Sorted alphabetically by label (2026-08-27), per the user -- purely a display-order change, no
# layer values touched.
SLOT_CATALOG = [
    # WEAPON SLOT ADDED (2026-09-11) -- MEASURED, not guessed. An equipped butcher knife reports
    # Layer='FirstValid', and so do all seven spellbooks in the pack; 'RightHand' holds NOTHING.
    # The old note below excluded RightHand believing its layer "did not round-trip cleanly" from
    # a single spellbook sample -- the real answer is that weapons were never on RightHand at all,
    # and that wrong inference is why this script had no weapon slot, and why all 18 runes missing
    # from PROPERTY_CATALOG are weapon-only or ranged-only.
    #
    # 'FirstValid' IS SHARED WITH SPELLBOOKS, so find_slot_items() on this entry returns both.
    # Every rune currently in PROPERTY_CATALOG is valid on a weapon AND on a spellbook (the 16
    # weapon-only runes are precisely the ones still missing), so nothing can be misapplied
    # through this entry today. The moment a weapon-only rune is added this must be narrowed by
    # property line -- RuneSlotLogic.classify_item() already does that, verified against real items.
    # LABELS MATCH THE SHARD'S OWN PAPERDOLL (2026-09-11) -- the user labelled a screenshot of it
    # and these are the names on the cells. Display only: every use is a log line or gump text, and
    # load_last_apply_thresholds() keys on the PROPERTY label, not this one.
    #
    # "categories" (optional, 2026-09-11) OVERRIDES the layer's own RuneSlotLogic lookup. Only the
    # two weapon cells need it, because a melee and a ranged weapon share the 'FirstValid' layer and
    # cannot be told apart by layer at all -- see the Ranged entry below.
    # "requires" (2026-09-11) -- the category an item MUST have to appear on this slot AT ALL,
    # for the icon and for the craft pool alike. Distinct from "categories", which decides which
    # RUNES are offered. Both are needed here and only here: Weapon and Ranged share a layer, so
    # without it find_slot_items() hands both cells the same list. Per the user: "ranged shouldn't
    # show the same scythe as weapon."
    # "layers" (2026-09-11) -- MEASURED, and it is why the Ranged cell showed nothing while a bow
    # sat in the pack. A two-handed weapon reports EITHER layer per-item: the boundary scan found
    # "Dawn composite bow Of Monitor" on LeftHand, and RuneSlotLogic's own note records another
    # two-hander (0x13B2) on FirstValid. So a weapon cell that reads one layer misses half of them.
    # Defaults to ["layer"] for every other slot, which are single-layer and unaffected.
    # RANGED FOLDED BACK IN (2026-09-14), per the user: "can we use that same logic for the
    # weapon slot? ... it could just detect the most common type in the backpack or selected chest."
    #
    # It was split on 2026-09-11 ("show a ranged slot left of the weapon slot") to stop bala/vel
    # being offered on a melee weapon, where they are a wasted rune. That outcome is UNCHANGED --
    # what changed is who decides. "categories" was an explicit override, and an override is exactly
    # what BYPASSES the majority vote: see partition_slot_items(), "an explicit
    # slot_def['categories'] bypasses the vote entirely". Dropping it does NOT union the two sets;
    # it hands the choice to vote_winning_category(), which keeps one winning group and excludes the
    # rest -- the same machinery the Neck cell has always used.
    #
    # NOTHING ELSE WAS NEEDED HERE. classify_item() already returns (WEAPON, RANGED) for a bow and
    # (WEAPON,) for a scythe, and runes_for_categories() already answers 50 and 48. A pack of bows
    # votes ranged and is offered bala/vel; a pack of scythes votes melee and is not. A lone bow
    # among scythes is EXCLUDED rather than mis-offered, per "we just ignore the bandana".
    #
    # "requires": "Weapon" STAYS. It is what keeps shields, fishing poles and spellbooks off this
    # cell, and a bow satisfies it (RANGED always carries WEAPON).
    {"label": "Weapon", "layer": "FirstValid", "layers": ("FirstValid", "LeftHand"),
     "requires": "Weapon", "label_by_category": {"Ranged weapon": "Ranged"}},
    {"label": "Arms", "layer": "Arms"},
    {"label": "Bracelet", "layer": "Bracelet"},
    # RE-MERGED INTO ONE CELL (2026-09-14), per the user: "the only UI change would be to shift
    # what item name is displayed for the cloak/quiver slot based on what is actually detected."
    #
    # These were split on 2026-09-11 ("separate out Quiver from Cloak ... there are some 'clothing'
    # options that do not work for quiver"). CLOTHING offers 27, QUIVER 22, and the five in the gap
    # are aglo/ahm/cah/lum/rel. That measurement still stands and a quiver is still never offered
    # those five -- the vote now decides which of the two the cell is about, and
    # runes_for_categories(exact=True) narrows a voted quiver to its real 22.
    #
    # WHY THIS ONE NEEDED A LOGIC CHANGE AND THE WEAPON FOLD DID NOT. The two narrow kinds run in
    # opposite directions: RANGED *adds* runes, so the union is right for a bow; QUIVER *removes*
    # them, so the union over-offered. The old "excludes": "Quiver" expressed that by filtering the
    # ITEMS out of this cell; with one cell there is nothing to exclude to, so the narrowing moved
    # into RuneSlotLogic.RESTRICTIVE_CATEGORIES where the categories are actually read. That is
    # where classify_item()'s own note always said it belonged.
    #
    # "requires": "Clothing" STAYS and still matches a quiver -- a quiver really IS clothing,
    # classify_item() returns (CLOTHING, QUIVER), and that was never the part that was wrong.
    # "label_undetected" (2026-09-15), per the user: this cell reads "Back" -- the layer's own
    # name -- until the pack is scanned and the vote picks Cloak or Quiver. Before that there is
    # no evidence for either, and defaulting to "Cloak" was quietly asserting one of the two live
    # answers. Optional key: every cell without it keeps falling back to its catalog "label".
    # "covers" (2026-09-16), per the user: "for the Back slot, by default explain that it
    # includes Cloak and Quiver." Read by the slot-grid tooltip. On the slot rather than in a
    # table keyed by label, because it is a fact about this slot like every other key here.
    {"label": "Cloak", "layer": "Cloak", "label_undetected": "Back",
     "covers": "both Cloak and Quiver",
     "requires": "Clothing", "label_by_category": {"Quiver": "Quiver"}},
    {"label": "Earrings", "layer": "Earrings"},
    {"label": "Hands", "layer": "Gloves"},
    {"label": "Head", "layer": "Head"},
    {"label": "Torso", "layer": "InnerTorso"},
    # SHIELD MUST NOT COUNT WEAPONS (2026-09-11), per the user: "Shields do need the same fix as
    # weapon, so it doesn't count bows." LeftHand holds shields AND two-handed weapons, so the bare
    # layer match was handing this cell the composite bow. It was also the worst over-offer in the
    # file: Shield+Weapon = 48 runes, SHIELD alone = 32, so 16 weapon-only runes were on a shield's
    # screen. (SHIELD is a strict subset of WEAPON -- shield-not-weapon is empty -- so this only
    # ever removed options, never added.)
    # "requires_name" ADDED (2026-09-11), per the user: "for now, let's only consider shields with
    # the word 'shield' in their name", and then "it's okay to keep all the requirements, let's add
    # shield, not remove the others." So this is ADDITIVE -- classify_item() is untouched and its
    # existing "requires": "Shield" still applies; this is a second condition on top.
    #
    # WHY IT HAS TO LIVE HERE AND NOT IN classify_item(). LeftHand holds shields, two-handed weapons
    # AND fishing poles, and a PACKED shield carries no "last parry chance" line at all (measured).
    # classify_item() therefore claims SHIELD for any unmarked LeftHand item -- deliberately, and
    # Tests/test_RuneSlotLogic.py's test_PACKED_shield_still_classifies_without_a_parry_line exists
    # to protect exactly that. A fishing pole is also LeftHand, also two-handed, also unmarked, so it
    # inherited the same answer and the Shield cell counted it ("shield is counting it", live).
    # Narrowing classify_item() would have broken the packed-shield case it was built for; narrowing
    # the SLOT costs nothing else.
    #
    # THE NAME TEST IS GONE (2026-09-11) -- the user found its counterexample within minutes:
    # "Doh. I found a shield without the word shield in it." That was "Wall of Hungry Mouths", a
    # real shield on LeftHand with no "shield" in its name, which requires_name would have hidden
    # entirely. Replaced by a DURABILITY test inside RuneSlotLogic.classify_item() -- see
    # RuneSlotLogic.DURABILITY_MARKER. Durability works where the name test could not because it
    # also satisfies the packed-shield case that test_PACKED_shield_still_classifies_without_a_
    # parry_line protects; narrowing by name broke it, narrowing by durability does not.
    #
    # "requires_name" itself is LEFT SUPPORTED in find_slot_items() below, unused -- it is three
    # lines, it is the only tool available if a future slot genuinely can only be told apart by
    # name, and removing it would not simplify anything.
    {"label": "Shield", "layer": "LeftHand", "categories": ("Shield",), "requires": "Shield"},
    {"label": "Tunic", "layer": "MiddleTorso"},
    {"label": "Neck", "layer": "Neck"},
    {"label": "Pants", "layer": "Pants"},
    {"label": "Ring", "layer": "Ring"},
    {"label": "Robe", "layer": "OuterTorso"},
    {"label": "Shirt", "layer": "Shirt"},
    {"label": "Shoes", "layer": "Shoes"},
    {"label": "Skirt", "layer": "OuterLegs"},  # Per the user (2026-08-18): missing from slot-
                                # matching round 1 entirely, not tested either way. "OuterLegs" is
                                # the standard UO client layer name for this slot (skirt/half-apron)
                                # -- unlike RightHand above, no live round-trip mismatch is known or
                                # suspected here, just genuinely untested. If find_slot_items()
                                # ever comes back empty for a real worn Skirt item, that's the
                                # signal this needs the same live check RightHand got.
    {"label": "Waist", "layer": "Waist"},
]

_item_category_cache = {}   # serial -> tuple of RuneSlotLogic categories, for the life of the run.
                            # find_slot_items() is called inside loops and a property read per item
                            # per call would be real overhead; an item's kind cannot change mid-run.


def item_categories(item, layer):
    """RuneSlotLogic.classify_item() for a real backpack item, memoised per serial.

    ONE cache serving BOTH filters below (2026-09-11) -- this began as item_is_spellbook() with its
    own bool cache; the "requires" filter needed the same classification, so the cache now holds the
    category tuple and each filter asks it a different question. One property read per item per run.

    An unreadable item returns (SPELLBOOK,) -- deliberately the one category that is never a craft
    target and never satisfies a "requires". Per the user, "I never want this to randomly break
    those": an item whose properties did not arrive must not become a target by default."""
    # KEYED BY (SERIAL, LAYER), NOT SERIAL ALONE (2026-09-11) -- REAL BUG, found live by the user:
    # "still nada" on the Shield cell with a heater shield in the pack. classify_item()'s answer
    # DEPENDS on the layer it is asked about (its fall-throughs are per-layer), so one cache entry
    # per item silently returned another layer's answer.
    #
    # HOW IT BIT: the Weapon cell now spans FirstValid+LeftHand, so its spellbook filter ran over the
    # shield, and item_is_spellbook() asked about "FirstValid". A PACKED shield carries no
    # "last parry chance" line at all (measured -- see classify_item()'s own note), so it has no
    # markers and hit `if layer == "FirstValid": return (SPELLBOOK,)`. That was cached against the
    # shield's serial, and the Shield cell then read (SPELLBOOK,) and dropped it. The bow was immune
    # because it carries real weapon markers and never reaches a fall-through.
    key = (getattr(item, "Serial", None), layer)
    if key in _item_category_cache:
        return _item_category_cache[key]
    try:
        Items.WaitForProps(item, 1000)
        cats = classify_item(Items.GetPropStringList(item) or [], layer)
    except Exception:
        cats = (SPELLBOOK,)
    _item_category_cache[key] = cats
    return cats


def item_is_spellbook(item):
    """True if `item` classifies as a spellbook -- a bare "<int> Spells" property line, see
    RuneSlotLogic's own SPELLBOOK_COUNT_WORDS comment for the four measured samples including the
    0-spell one. Thin wrapper over item_categories() so both filters share one read.

    ASKS ABOUT THE ITEM'S OWN LAYER (2026-09-11), not a hardcoded "FirstValid". It used to pass
    "FirstValid" unconditionally, which was harmless only while the spellbook filter ran on a
    FirstValid-only slot. Once the Weapon cell spanned both hand layers that filter began asking
    about LeftHand items too, and a marker-less packed shield fell through the FirstValid branch
    straight into (SPELLBOOK,) -- see item_categories()' own comment for the live incident. The real
    spellbook test is the positive "<int> Spells" line, which is layer-independent; passing the true
    layer means a non-FirstValid item can never be mistaken for one by a fall-through."""
    return SPELLBOOK in item_categories(item, str(getattr(item, "Layer", "")))


APPLY_SOURCE_BATCH_SIZE = 10   # The user's number: "pull out 10 items at a time from the chest,
                               # and pull out another one for every item break until none remain."
                               # Both halves are the same rule -- refill the working set to this
                               # many at the top of every pass, and a break is precisely what drops
                               # it below.
APPLY_SOURCE = {"container": None,   # serial of the chest chosen for THIS run, or None for the
                                     # normal backpack-only behaviour.
                "serials": set(),    # the chest items that won the category vote -- the only ones
                                     # this run will ever pull out. The losers (2 necklaces in a
                                     # chest of 40 gorgets) stay where they are.
                "label": ""}         # the chest's own name, purely for log lines.


def source_chest():
    """The chosen source chest as a live Item, or None when there is no source or it is out of
    reach. Out of reach is a real case: use_perk_deed_if_needed() can travel home mid-run."""
    serial = APPLY_SOURCE.get("container")
    if not serial:
        return None
    return Items.FindBySerial(serial)


def source_items_remaining():
    """The reserved items still sitting in the chest. Empty when there is no source."""
    chest = source_chest()
    if chest is None or not APPLY_SOURCE["serials"]:
        return []
    try:
        Items.WaitForContents(chest, SOURCE_CONTENTS_WAIT_MS)
        return [it for it in container_items(chest) if it.Serial in APPLY_SOURCE["serials"]]
    except Exception:
        return []


# WORK FEWER ITEMS (owner, 2026-10-17: "Let's aim for 1, and let's give the player a couple % thresholds to choose from,
# similar to how we already do suggested when the goal is out of reach. Let's suggest working a smaller number of items
# instead of all of them." -- "We can show thresholds down to 80% as long as that lines up with a breakpoint"). The
# preview's simulation counts how often each item survives every stat; items do not share anything there, so the chance
# that at least one of the N likeliest finishes is 1 - the product of their misses. For each of WORK_FEWER_THRESHOLDS
# the fewest such items is offered as a button (a count reached by two thresholds is one button, at its real odds; a
# count needing every item is no button -- Apply already is that). A press starts the craft, as Apply does (owner,
# 2026-10-17: "those should function the same as apply to tunic" -- "it should start the craft"), with find_slot_items()
# -- the one pool every count and the run itself read -- narrowed to those items.
WORK_FEWER_THRESHOLDS = (0.80, 0.90, 0.95, 0.99)
WORK_SET = [None]                        # the serials chosen on the preview, or None: every item in play


def work_fewer_choices(finish_by_item):
    """[(count, odds, serials)] -- see WORK FEWER ITEMS. Empty when no threshold is met short of every item."""
    ranked = sorted(finish_by_item, key=lambda sp: -sp[1])
    out = []
    for thr in WORK_FEWER_THRESHOLDS:
        miss = 1.0
        for n, (_serial, p) in enumerate(ranked, 1):
            miss *= (1.0 - p)
            if 1.0 - miss >= thr:
                if n < len(ranked) and not any(c[0] == n for c in out):
                    out.append((n, 1.0 - miss, [sp[0] for sp in ranked[:n]]))
                break
    return out


def find_slot_items(slot_def, restrict_serials=None, in_pack_only=False):
    """Every item whose Layer matches slot_def -- the pool a slot-crafting run works across.

    INCLUDES THE SOURCE CHEST (2026-09-13) when one has been chosen for this run, because this
    function is what every calculation in the file counts: the preview's expected applications and
    item breaks, the Rough Stone estimate, the odds simulation, the base picker,
    craft_more_runes_if_needed(). Per the user, the calcs are "based on how many of that type are
    in the chest" -- teaching this one function about the chest is what makes that true everywhere
    at once, instead of a chest-aware count in six places.

    in_pack_only=True is for the apply loop alone: a rune can only be used on something actually in
    the backpack, so that loop works the ten-item window top_up_from_source() keeps stocked, while
    everything else plans against the whole reservoir.

    restrict_serials (2026-08-27), if given: an iterable of Serial values -- only items ALSO in that
    set are returned, on top of the normal Layer match. Used by select_apply_bases() to concentrate
    a dump-category stat's whole run onto a small hand-picked subset instead of every eligible item
    of that slot type (see that function's own docstring for why)."""
    # A slot may span more than one layer -- see the Weapon entry's own "layers" comment. Single
    # entry by default, so every other slot behaves exactly as before.
    layers = tuple(slot_def.get("layers") or (slot_def["layer"],))
    pool = container_items(Player.Backpack)
    if not in_pack_only:
        pool.extend(source_items_remaining())
    if WORK_SET[0] is not None:          # (2026-10-17) WORK FEWER ITEMS: only the items chosen on the preview
        pool = [it for it in pool if it.Serial in WORK_SET[0]]
    items = [it for it in pool if str(getattr(it, "Layer", "")) in layers]
    # SPELLBOOKS ARE NEVER A CRAFT TARGET (2026-09-11), per the user: "we need to disable spellbooks
    # as a crafting option. Too often players have various spellbooks in their inventory, and I
    # never want this to randomly break those while trying to craft on a weapon."
    #
    # FILTERED HERE, not in the UI, because THIS is the pool the run itself works across
    # (select_apply_bases()/run_slot_application() both read it). Filtering only the slot-grid icon
    # would have left a real craft free to pick a spellbook as its target.
    #
    # Only for 'FirstValid': that is the one layer a spellbook reports (measured across seven of
    # them), and it is also the layer weapons use, which is exactly why they collide. Every other
    # slot keeps the pure Layer match with no property read at all -- see item_is_spellbook() for
    # the per-serial memoisation that keeps even this path cheap inside a loop.
    if "FirstValid" in layers:
        items = [it for it in items if not item_is_spellbook(it)]
    # SLOTS THAT SHARE A LAYER MUST STILL DIFFER (2026-09-11), per the user: "ranged shouldn't show
    # the same scythe as weapon." Weapon and Ranged are both 'FirstValid', so the Layer match above
    # cannot separate them -- "requires" names the category classify_item() must actually find on
    # the item. This runs for the POOL, not just the icon, so a Ranged run can never target a melee
    # weapon and waste Balanced/Velocity on it.
    # CLASSIFIED AGAINST THE ITEM'S OWN LAYER, not the slot's (2026-09-11): classify_item()'s
    # fall-throughs are layer-specific, and a multi-layer slot would otherwise judge a LeftHand bow
    # as though it were on FirstValid.
    required = slot_def.get("requires")
    if required:
        items = [it for it in items
                 if required in item_categories(it, str(getattr(it, "Layer", "")))]
    # "excludes" (2026-09-11) -- for a NARROWER kind that LOSES options rather than gaining them.
    # NO SLOT USES IT ANY MORE (2026-09-14). It existed for exactly one cell: Cloak's "requires
    # Clothing" matched a quiver, so the cell had to drop quivers OUT OF THE POOL to avoid offering
    # the five runes they cannot take (aglo/ahm/cah/lum/rel). Cloak and Quiver are one folded cell
    # now, so there is no longer a second cell to exclude them TO -- a quiver belongs here, and the
    # narrowing moved to RuneSlotLogic.RESTRICTIVE_CATEGORIES, which cuts the RUNES instead of the
    # ITEMS. That is the better place: it is the item's own classification that makes it restrictive,
    # not which cell it landed in.
    #
    # LEFT SUPPORTED, unused, on the same reasoning as "requires_name" below: four lines, and the
    # only tool available if a future slot must drop a kind from its pool rather than narrow it.
    excluded = slot_def.get("excludes")
    if excluded:
        items = [it for it in items
                 if excluded not in item_categories(it, str(getattr(it, "Layer", "")))]
    # "requires_name" -- a substring the item's NAME must contain, on top of every category test
    # above. Only the Shield cell uses it; see that entry for why a name test is the only thing that
    # can separate a packed shield from a fishing pole on the shared LeftHand layer.
    name_needle = slot_def.get("requires_name")
    if name_needle:
        items = [it for it in items
                 if name_needle in (getattr(it, "Name", "") or "").lower()]
    if restrict_serials is not None:
        items = [it for it in items if it.Serial in restrict_serials]
    return items

APPLY_REQUEST_GUMP_ID = 0x52554E51  # "RUNQ" -- distinct tag from this project's other custom
                                       # gumps (RUNR/RUNA/RUNS/RUNM), same ASCII-tag convention.
                                       # Reused for the combined gump below -- the standalone slot
                                       # gump (RUNS/APPLY_SLOT_GUMP_ID) it used to pair with is gone.
APPLY_REQUEST_COLUMN_WIDTH = 260
APPLY_REQUEST_ROW_HEIGHT = 30
APPLY_REQUEST_CHECK_INACTIVE_ID = 210  # Standard UO on/off checkbox art -- ubiquitous across
                                          # stock UO gumps, not shard-specific, but this project
                                          # has never used Gumps.AddCheck() before now -- treat as
                                          # UNCONFIRMED against this specific gump until live-tested.
APPLY_REQUEST_CHECK_ACTIVE_ID = 211
APPLY_REQUEST_ENTRY_BACKING_TEXTURE = 9354  # Light background tile drawn behind every numeric
                                   # threshold field -- see ask_apply_requests_and_slot()'s own
                                   # "VISIBLE BACKING" docstring note for why (AddTextEntry alone
                                   # rendered invisible against this gump's alpha-region background)
                                   # and the honest confidence label on this specific texture choice.
APPLY_SLOT_COLUMN_WIDTH = 200  # 3rd column (2026-08-27) -- see ask_apply_requests_and_slot()'s own
                                  # "COMBINED SCREEN" docstring note. Narrower than the stat columns
                                  # (260): slot labels are short ("Middle Torso" is the longest) and
                                  # don't need a threshold field's own width alongside them.
APPLY_SLOT_BUTTON_BASE = 100  # Each slot's own button IS the submit action now -- no separate
                                # Submit button exists any more (see the docstring below).

def ask_apply_requests_and_slot_flat():
    """SUPERSEDED 2026-09-11 by the two-page paperdoll grid (ask_apply_requests_and_slot() below,
    which now owns that name). KEPT, not deleted -- same convention ask_which_mode() already uses
    here, and this is the fallback if the grid misbehaves on a live screen. It shows every rune to
    every slot, which is what stopped scaling once PROPERTY_CATALOG reached 50.

    COMBINED SCREEN (2026-08-27) -- per the user, from a live screenshot of the previous two
    SEPARATE sequential gumps (stat thresholds, then slot choice): "let's combine these into a
    single screen. The equipment type can be a 3rd column on the right, and we no longer need the
    original submit button." Replaces the old ask_apply_requests()/ask_which_slot() pair entirely
    -- ONE gump, columns for Required Stats / Dump Stats / equipment slot, and every slot button
    in the equipment column now doubles as the whole gump's submit action (clicking a slot both
    picks it AND reads back whatever thresholds/checkboxes were filled in at that moment) instead
    of a separate Submit button existing alongside the slot list.

    SPLIT TO TWO REQUIRED COLUMNS (2026-08-27) -- per the user, after PROPERTY_CATALOG grew from 4
    Required Stats to ~30 (every non-weapon-restricted rune on the wiki). A single Required column
    at that length would make the gump ~900px tall -- taller than most screens and functionally
    unusable. Required Stats now split into two side-by-side columns (first half / second half of
    required_props, in the catalog's own alphabetical order, so column 1 is roughly A-M and column
    2 the rest) -- see the width/rows math below. Total column count is now 4 (Required 1,
    Required 2, Dump, Equipment); the layout is otherwise unchanged from the 3-column design.

    Required Stats (left column) are every PROPERTY_CATALOG entry whose category isn't "dump"
    (defaults to required when the key is missing); Dump Stats (middle column) are category ==
    "dump" -- see each catalog entry's own comment for why SDI/Luck are the only two dump stats
    for now. Every row gets its OWN threshold field. A value of 0 (or blank, which reads back the
    same as 0) means "not requested" for that stat -- filling in a positive number is what selects
    it for this run, letting one submission request several stats at once. The one EXCEPTION is
    Mage Armor/Wep (is_boolean=True), which gets a real checkbox instead of a text box, per the
    user: "Mage Armor is a single line property on an item with no values, so the threshold box
    for that should accept 0 or 1, unless we can make it a checkbox. That would be awesome." A
    checked box is treated as target_stat=1 in the returned request.

    PRE-FILL (2026-08-27), per the user, after seeing the gump live for the first time: "Let's
    default each of the threshold boxes to 0, or whatever was entered last." Each numeric field
    pre-fills load_last_apply_thresholds().get(label, 0) -- per-PROPERTY memory. Doesn't conflict
    with the "0/blank means not requested" selection rule above -- a field that was 0 last time is
    still 0 (not requested) this time by default, exactly as expected.

    VISIBLE BACKING (2026-08-27), per the user: "Can we also change the shade for the threshold
    boxes so they are visible?" -- an AddTextEntry field has no background of its own, and this
    gump's AddAlphaRegion makes the whole background semi-transparent, so a live test showed the
    boxes as literally invisible (only their green text, once typed, would show at all). Each
    numeric field now gets a light AddImageTiled panel (texture 9354) drawn behind it at the exact
    same position/size -- a common "light text-entry backing" texture from the broader UO gump-
    scripting community, NOT independently confirmed against this specific shard/client before now.

    UNCONFIRMED live: Gumps.AddCheck()'s exact graphic IDs (210/211 -- standard UO checkbox art)
    and which field on the GetGumpData() response reports which checkboxes were ON (assumed here
    to be `.switches`, matching SendAdvancedAction's own switchlist_id parameter naming). The
    checkbox DID render visibly in an earlier live screenshot (unlike the plain text entries), so
    at minimum AddCheck()'s own rendering is confirmed; whether `.switches` correctly reports its
    checked state is still unconfirmed. Read defensively (getattr with a fallback to an empty
    list) so a wrong attribute name fails as "checkbox read as unchecked" -- an obvious, harmless
    symptom -- rather than crashing the whole gump response.

    Returns (requests, slot_def): `requests` is a list of (property_def, target_stat) tuples for
    every row actually filled in/checked (can be empty -- clicking a slot with nothing filled in
    is a valid, if useless, submission, same as the old gump). `slot_def` is a SLOT_CATALOG entry.
    Returns (None, None) if the gump timed out, gave no response data, or the button clicked
    somehow doesn't map to any slot (shouldn't happen -- every button in this gump IS a slot
    button now, there's nothing else to click)."""
    required_props = [p for p in PROPERTY_CATALOG if p.get("category", "required") != "dump"]
    dump_props = [p for p in PROPERTY_CATALOG if p.get("category") == "dump"]
    last_thresholds = load_last_apply_thresholds()

    # Required Stats split across 2 columns (2026-08-27) -- see this function's own docstring for
    # why. required_col1 gets the extra row when the count is odd.
    required_half = (len(required_props) + 1) // 2
    required_col1 = required_props[:required_half]
    required_col2 = required_props[required_half:]

    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    rows = max(len(required_col1), len(required_col2), len(dump_props), len(SLOT_CATALOG))
    width = APPLY_REQUEST_COLUMN_WIDTH * 3 + APPLY_SLOT_COLUMN_WIDTH
    height = 60 + rows * APPLY_REQUEST_ROW_HEIGHT
    Gumps.AddBackground(gd, 0, 0, width, height, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, width, height)
    Gumps.AddLabel(gd, 20, 15, 68, "Required Stats")
    Gumps.AddLabel(gd, 20 + APPLY_REQUEST_COLUMN_WIDTH, 15, 68, "Required Stats (cont.)")
    Gumps.AddLabel(gd, 20 + APPLY_REQUEST_COLUMN_WIDTH * 2, 15, 68, "Dump Stats")
    Gumps.AddLabel(gd, 20 + APPLY_REQUEST_COLUMN_WIDTH * 3, 15, 68, "Equipment")

    # Mutable single-element lists standing in for a writable closure variable -- this project
    # targets IronPython (no `nonlocal` keyword available), same workaround convention as this
    # file's own module-level mutable-dict caches (e.g. _gate_cache) use for a different reason.
    next_entry_id = [1]
    next_switch_id = [1]
    text_rows = []   # [(entry_id, property_def), ...] in the order fields were added.
    check_rows = []  # [(switch_id, property_def), ...] in the order fields were added.

    def add_column(props, base_x):
        y = 45
        for prop in props:
            Gumps.AddLabel(gd, base_x, y + 2, 68, prop["label"])
            if prop.get("is_boolean"):
                switch_id = next_switch_id[0]
                next_switch_id[0] += 1
                Gumps.AddCheck(gd, base_x + 140, y, APPLY_REQUEST_CHECK_INACTIVE_ID,
                                APPLY_REQUEST_CHECK_ACTIVE_ID, False, switch_id)
                check_rows.append((switch_id, prop))
            else:
                entry_id = next_entry_id[0]
                next_entry_id[0] += 1
                Gumps.AddImageTiled(gd, base_x + 140, y, 90, 20, APPLY_REQUEST_ENTRY_BACKING_TEXTURE)
                default_value = str(last_thresholds.get(prop["label"], 0))
                Gumps.AddTextEntry(gd, base_x + 140, y, 90, 20, 68, entry_id, default_value)
                text_rows.append((entry_id, prop))
            y += APPLY_REQUEST_ROW_HEIGHT

    add_column(required_col1, 20)
    add_column(required_col2, 20 + APPLY_REQUEST_COLUMN_WIDTH)
    add_column(dump_props, 20 + APPLY_REQUEST_COLUMN_WIDTH * 2)

    slot_base_x = 20 + APPLY_REQUEST_COLUMN_WIDTH * 3
    y = 45
    for i, slot in enumerate(SLOT_CATALOG):
        button_id = APPLY_SLOT_BUTTON_BASE + i
        Gumps.AddButton(gd, slot_base_x, y, 4005, 4007, button_id, 1, 0)
        Gumps.AddTooltip(gd, "Apply the target values on the left to your %s items."
                             % slot["label"])
        Gumps.AddLabel(gd, slot_base_x + 35, y + 2, 68, slot["label"])
        y += APPLY_REQUEST_ROW_HEIGHT

    Gumps.SendGump(APPLY_REQUEST_GUMP_ID, Player.Serial, 300, 300, gd.gumpDefinition, gd.gumpStrings)
    log("Fill in a target value for every stat you want applied (leave the rest blank), check "
        "Mage Armor if wanted, then click the equipment slot to craft on...")

    if not Gumps.WaitForGump(APPLY_REQUEST_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        log("Warning: apply-request gump timed out with no response.", 33)
        return None, None
    response = Gumps.GetGumpData(APPLY_REQUEST_GUMP_ID)
    if response is None:
        log("Warning: apply-request gump gave no response data.", 33)
        return None, None

    slot_index = response.buttonid - APPLY_SLOT_BUTTON_BASE
    if slot_index < 0 or slot_index >= len(SLOT_CATALOG):
        log("Warning: button {} doesn't map to any slot -- treating as no request.".format(
            response.buttonid), 33)
        return None, None
    slot_def = SLOT_CATALOG[slot_index]

    requests = []
    submitted_thresholds = {}  # Every numeric field's own raw value (0 included) -- saved below
                                 # regardless of whether it ended up selected, so next time's
                                 # pre-fill shows exactly what was there before (see the user's
                                 # "default...to 0, or whatever was entered last").
    response_text = response.text or []
    for entry_id, prop in text_rows:
        try:
            raw = (response_text[entry_id - 1] or "").strip()
        except (IndexError, TypeError):
            raw = ""
        if not raw:
            submitted_thresholds[prop["label"]] = 0
            continue
        try:
            target_stat = int(raw)
        except ValueError:
            log("Warning: '{}' for {} isn't a valid number -- skipping that stat.".format(
                raw, prop["label"]), 33)
            continue
        submitted_thresholds[prop["label"]] = target_stat
        if target_stat <= 0:
            continue
        requests.append((prop, target_stat))
    save_last_apply_thresholds(submitted_thresholds)

    checked_switches = set(getattr(response, "switches", None) or [])
    for switch_id, prop in check_rows:
        if switch_id in checked_switches:
            requests.append((prop, 1))

    return requests, slot_def


# =============================================================================
# RUNE APPLICATION (PHASE 2) -- AUTOMATION LOOP
#
# CONFIRMED live (ScratchTest.py, apply-mechanic rounds 1-3): using a crafted rune
# (Items.UseItem) opens a target cursor ('Select the item to enhance.', no gump); targeting an
# item consumes the rune EITHER WAY and modifies the target IN PLACE (its Serial doesn't change --
# unlike crafting, nothing new is added to the backpack); on success the journal shows "The
# <Syllable> Rune enhances your clothing." and the item's relevant property text increases by a
# random amount (SDI observed: 3% -> 4%, i.e. a +1% application). Item property text is plain
# lowercase-friendly strings via Items.GetPropStringList(), e.g. "spell damage increase 4%".
#
# Per the user: there's no reliable way to detect a break/rejection message, and that's not worth
# pursuing. Instead, breakage is inferred purely from BACKPACK COUNT: after every application,
# whichever item was targeted either still exists in the backpack (survived) or doesn't (broke).
# Every count/eligibility check in this section is scoped to Player.Backpack.Contains ONLY --
# equipped/worn items are never counted or targeted (Player.Backpack.Contains was already
# confirmed, in slot-matching round 1, to exclude worn items entirely).
# =============================================================================

def count_runes(property_def):
    """Every '<Syllable> Rune' item currently in the backpack for property_def."""
    target_name = "{} rune".format(property_def["syllable"]).strip().lower()
    # bare_item_name() (2026-09-16): a stacked pile is named "3 In Rune", so the old exact test
    # against the raw Name returned NOTHING as soon as runes began stacking -- "Out of 'In Rune'"
    # one second after "crafted all 2". Callers wanting a COUNT must use count_rune_amount(), since
    # that pile is one item.
    return [it for it in container_items(Player.Backpack)
            if bare_item_name(it).lower() == target_name]

def parse_mage_weapon_value(raw):
    """The Magery delta a "Mage Weapon" line carries (2026-09-19). The shard writes the line as
    "Mage Weapon -<penalty> Skill", and the penalty itself can be negative -- hence the doubled dash:
        "-10" -> -10 (a penalty)   None/bare -> 0 (no penalty left)   "--75" -> +75 (a bonus, uncapped)
    Per the user, the doubled dash is to be read as a bonus that scales without a cap."""
    if raw is None:
        return 0
    raw = raw.strip()
    if raw.startswith("--"):
        return int(raw[2:])
    if raw.startswith("-"):
        return -int(raw[1:])
    return -int(raw)


def read_property_value(item, property_def):
    """Parses item's CURRENT value of property_def's tracked stat off its live property strings,
    via property_def['prop_pattern'] (a regex with one capture group). An item that doesn't show
    the property at all reads as 0 -- per the user's "always target the lowest" strategy, an
    item with none of the property yet should be picked before one that already has some.
    Returns None (not 0) if prop_pattern itself is None -- the caller must treat that as "can't
    evaluate this property yet", not as a real reading of zero.

    For an is_boolean property the line carries no number, so a MATCH returns 1 and a miss
    returns 0 -- presence is the value. Its prop_pattern therefore needs no capture group."""
    pattern = property_def.get("prop_pattern")
    if pattern is None:
        return None
    # VIA THE CACHE (2026-09-16) -- see property_lines_for(). Outside a preview pass this is the
    # same WaitForProps + GetPropStringList it always was; inside one, the item's lines are
    # fetched once and reused for every stat instead of once per stat.
    props = property_lines_for(item)
    for p in props:
        m = re.search(pattern, (p or "").lower())
        if m:
            # BOOLEAN PROPERTIES (2026-09-11): for these the line's PRESENCE is the whole
            # value -- "Night Sight", "Balanced", "Use Best Weapon Skill" and "Mage Armor"
            # carry no number, so there is no group to capture. Returning 1 here lets the
            # rest of run_slot_application() work unchanged: a ticked checkbox already
            # arrives as target_stat=1, so all(value >= 1) means "every item has it", the
            # lowest-value rule already prefers items lacking it, and a post-apply read of
            # 0 still correctly means the application did not take.
            if property_def.get("is_boolean"):
                return 1
            if property_def.get("signed_penalty"):
                # the group is OPTIONAL on this row -- a bare "Mage Weapon" is zero penalty (2026-09-19)
                return parse_mage_weapon_value(m.group(1) if m.lastindex else None)
            # the first group that matched: a pattern with two forms (Durability Bonus) has one group per form
            return int(next(g for g in m.groups() if g is not None))
    return 0

# ---------------------------------------------------------------------------------------------
# PREVIEW PROPERTY CACHE (2026-09-16). None means OFF: every read hits the live API, exactly as
# before. A dict means a preview pass is open -- item serial -> lowercased property lines.
#
# WHY IT EXISTS. read_property_value() fetches an item's WHOLE property list and then matches
# ONE pattern from it, so N requested stats cost N identical fetches of one list.
# snapshot_property_values() is called once per stat from three places in show_apply_preview(),
# which made the preview O(items x stats x call-sites): 250 items x 19 stats came to ~14,250
# Items.WaitForProps calls before anything was drawn, and every uncached item can burn the full
# 1000ms timeout. A player of the shipped script simply never got the Calculate screen.
#
# WHY IT IS SAFE ONLY THERE. The preview reads items nothing has touched yet, so their values
# cannot change while it computes. run_slot_application() is the opposite: it re-reads a
# property AFTER each application to prove the rune took, and drives the FULL STOP when the
# reading does not move. A cached answer there could call a working apply broken or hide a
# broken one, so the cache is opened for the four computation lines of show_apply_preview() and
# closed in a finally.
_preview_prop_lines = None


def property_lines_for(item):
    """An item's lowercased property lines, served from the preview cache when one is open.

    Failure reads as [] exactly as the inline version did, so a broken read still means "this
    property is not present" rather than raising into the caller."""
    if _preview_prop_lines is None:
        try:
            Items.WaitForProps(item, 1000)
            return [(p or "").lower() for p in (Items.GetPropStringList(item) or [])]
        except Exception:
            return []
    try:
        key = item.Serial
    except Exception:
        key = None          # unreadable serial -- fetch, but do not poison the cache with it
    if key is not None and key in _preview_prop_lines:
        return _preview_prop_lines[key]
    try:
        Items.WaitForProps(item, 1000)
        _lines = [(p or "").lower() for p in (Items.GetPropStringList(item) or [])]
    except Exception:
        _lines = []
    if key is not None:
        _preview_prop_lines[key] = _lines
    return _lines


def read_property_lines(item):
    """The item's raw property strings, lowercased, or [] if they can't be read.

    Used as EVIDENCE THAT AN APPLICATION DID SOMETHING when the tracked value still reads 0 --
    see run_slot_application()'s detect-fail branch. Deliberately the whole line list rather than
    the tracked value: a cah weapon going from "mage weapon -29 skill" to "-22" is real progress
    that read_property_value() reports as 0 both times, because 0 there means "not finished"."""
    try:
        Items.WaitForProps(item, 1000)
        return [(p or "").lower() for p in (Items.GetPropStringList(item) or [])]
    except Exception:
        return []


# A CURSOR LEFT OPEN IS INDISTINGUISHABLE FROM A REFUSED RUNE (2026-11-08).
# Until today nothing in this file cancelled a target cursor - Target.Cancel()
# appeared nowhere, against four Target.WaitForTarget() calls. See
# clear_stale_target() for what that does to an application.
APPLY_CURSOR_SETTLE_MS = 250
APPLY_JOURNAL_DUMP_LINES = 12   # Enough for a refusal plus its context; not a transcript.


def clear_stale_target(why):
    """Cancel a target cursor that is open before this script opened one.

    THE FAILURE IT PREVENTS. Target.WaitForTarget() does not know whose cursor
    it found. With a stale one open it returns True instantly, the following
    Target.TargetExecute() answers THAT cursor, and the cursor the rune itself
    raised is left hanging - so the rune is never consumed, the attempt is
    reported as "may not have gone through", and the retry raises a third
    cursor on top. Every retry makes it worse, and the run ends at
    "application kept not completing as expected after 3 attempts".

    Returns True if one was there and was cancelled, which is worth saying out
    loud: a cursor nobody in this script opened means something else did.
    """
    try:
        if not Target.HasTarget():
            return False
    except Exception:
        return False          # No HasTarget on this build: nothing to clean up safely.
    log("A target cursor was ALREADY OPEN {} -- cancelling it first. It is not this "
        "script's, and answering it instead of the rune's own cursor is how an "
        "application silently does nothing.".format(why), 33)
    try:
        Target.Cancel()
    except Exception:
        pass
    safe_pause(APPLY_CURSOR_SETTLE_MS)
    return True


def attempt_journal_lines():
    """Every distinct line the shard said during the attempt just made.

    SAFE TO READ WITHOUT CLEARING, and only because apply_rune_to_item() calls
    Journal.Clear() immediately before Items.UseItem() - the same guarantee
    application_was_refused() relies on. Collected BEFORE anything is logged,
    so this script's own log lines cannot appear in its own evidence.
    """
    lines = []
    try:
        for entry in (Journal.GetJournalEntry(None) or []):
            text = (getattr(entry, "Text", "") or "").strip()
            if text and text not in lines:
                lines.append(text)
    except Exception:
        pass
    return lines


def say_attempt_journal(what, lines):
    """Print what the shard said, verbatim, when an application did not land.

    ONE SENTENCE WAS BEING READ AND THE REST DISCARDED. application_was_refused()
    tests for "You cannot enhance that." and nothing else, so any other refusal
    wording - or a server that says nothing at all - fell through to the retry
    path and reported only that the stack had not moved. That is the symptom,
    never the cause, and it is why this fault was not diagnosable from the
    script's own output.

    SILENCE IS ITSELF A FINDING, and the most useful one: a server that rejects
    a rune says so. Nothing at all means the target never reached it.
    """
    if not lines:
        log("{} -- and the shard said NOTHING AT ALL during the attempt. A rejected "
            "rune produces a message; silence points at the target never reaching "
            "the server, which is what a cursor that was not ours does."
            .format(what), 33)
        return
    log("{} -- what the shard said during the attempt, verbatim:".format(what), 33)
    for text in lines[:APPLY_JOURNAL_DUMP_LINES]:
        log("    | {}".format(text), 33)
    if len(lines) > APPLY_JOURNAL_DUMP_LINES:
        log("    | ... and {} more line(s).".format(
            len(lines) - APPLY_JOURNAL_DUMP_LINES), 33)


APPLY_CONSUME_POLL_INTERVAL_MS = 150
APPLY_CONSUME_TIMEOUT_MS = 2000  # Same ballpark as the old fixed 1500ms wait -- polling returns
                                   # as soon as the rune is actually consumed instead of always
                                   # waiting the full amount regardless.

APPLY_PROPERTY_SETTLE_POLL_INTERVAL_MS = 150
APPLY_PROPERTY_SETTLE_TIMEOUT_MS = 1000  # Smaller cap than the consume-wait -- this only waits
                                            # for an already-consumed change's property text to
                                            # refresh, not a full server round trip.

def apply_rune_to_item(rune, target_item):
    """Uses `rune` and targets `target_item` with it, then POLLS for the rune to actually be
    consumed -- the stack's Amount FALLING, or its Serial disappearing when the last one goes.
    CONFIRMED live: a rune is consumed EITHER WAY, success or failure, which is why consumption
    and not the "enhances your clothing" message is the signal here -- a rune eaten by a FAILED
    application must count too, or the retry loop burns the supply re-trying a rune that is
    already gone. Returns False if no target cursor appeared, or if the stack never moved at all.

    BY AMOUNT SINCE 2026-09-16. This tested only whether the Serial was still in the backpack,
    which was right when one rune was one item -- using it emptied the slot. A stack keeps the
    SAME SERIAL and decrements Amount, so the poll could never succeed and every application was
    reported as a failure while plainly working: the shard said "The In Rune enhances your
    clothing", the stack went 101 -> 100 -> 99 -> 98, and the target's Luck went 0 -> 15. It
    stopped the batch after three "failures". A stack of one behaves exactly as it did before.

    Also checks for a world
    save in progress each tick (see wait_out_world_save()) so its multi-second freeze doesn't
    count against APPLY_CONSUME_TIMEOUT_MS -- and, since 2026-08-27, checks/retries around the
    initial Items.UseItem()/Target.WaitForTarget() step too (CONFIRMED live: a save already in
    progress can eat the whole fixed 2000ms target-cursor window well before the save itself
    actually finishes, a false "no target cursor" failure that has nothing to do with the rune
    or target item)."""
    # FIXED (2026-08-27) -- CONFIRMED live via journal capture: "The world is saving, please
    # wait." printed, THEN "Applying 'LMC' to Waist..." (this function's own caller log line, a
    # local Python action that isn't blocked by the save), THEN Items.UseItem() fired while the
    # server was still mid-save, THEN "World save done in 7.2 seconds." -- more than 3x the fixed
    # 2000ms Target.WaitForTarget() window below, which had already given up and returned False
    # long before the save actually finished. wait_out_world_save() already protects the
    # consume-poll loop further down in this same function; this blocking call never got the same
    # treatment. Checked BEFORE attempting the use (absorbs a save already in progress, which is
    # exactly what happened here) and retried once after a failed target-wait (covers a save that
    # starts in the narrow gap between the check and Items.UseItem() instead).
    wait_out_world_save()
    # BEFORE THE USE (2026-09-16). `rune` goes stale the moment the server edits the stack, so the
    # baseline has to be taken now and every comparison below re-read live from the backpack.
    try:
        amount_before = int(getattr(rune, "Amount", 1) or 1)
    except (TypeError, ValueError):
        amount_before = 1
    # BEFORE THE JOURNAL CLEAR, so the message naming the stale cursor survives
    # into the log rather than being wiped by the clear that follows it.
    clear_stale_target("before using '{}'".format(bare_item_name(rune)))
    Journal.Clear()
    Items.UseItem(rune.Serial)
    target_appeared = Target.WaitForTarget(2000, False)
    if not target_appeared and wait_out_world_save():
        Items.UseItem(rune.Serial)
        target_appeared = Target.WaitForTarget(2000, False)
    if not target_appeared:
        log("Warning: no target cursor appeared after using '{}'.".format(rune.Name), 33)
        say_attempt_journal("No cursor for '{}'".format(bare_item_name(rune)),
                            attempt_journal_lines())
        return False
    Target.TargetExecute(target_item.Serial)

    waited_ms = 0
    amount_last = amount_before   # what the most recent poll saw, for the warning below
    while waited_ms < APPLY_CONSUME_TIMEOUT_MS:
        safe_pause(APPLY_CONSUME_POLL_INTERVAL_MS)
        live = next((it for it in container_items(Player.Backpack) if it.Serial == rune.Serial), None)
        if live is None:
            return True          # the whole stack is gone -- the last rune in it was used
        try:
            amount_last = int(getattr(live, "Amount", 1) or 1)
        except (TypeError, ValueError):
            amount_last = amount_before
        if amount_last < amount_before:
            return True          # one left the stack: consumed, whatever the outcome was
        if wait_out_world_save():
            continue
        waited_ms += APPLY_CONSUME_POLL_INTERVAL_MS

    # THE COUNT IS THE EVIDENCE, so report BOTH ends of it. The old line printed rune.Name --
    # which on a stack IS the count ("'100 In Rune' was still in the backpack") -- so it was
    # printing the proof of success as the symptom of failure, and nothing in the message said
    # what the number was being compared against.
    # COLLECTED FIRST, LOGGED SECOND. Every log line this script writes goes into
    # the journal too, so reading the evidence after printing the warning would
    # hand back the warning as part of the evidence.
    attempt_lines = attempt_journal_lines()
    log("Warning: the '{}' stack still holds {} after {}ms (it was {} before the attempt) -- "
        "the application may not have gone through."
        .format(bare_item_name(rune), amount_last, waited_ms, amount_before), 33)
    say_attempt_journal(
        "'{}' was not consumed".format(bare_item_name(rune)), attempt_lines)
    # OUR OWN CURSOR, STILL HANGING. If the rune raised a cursor and the target
    # never answered it, it is still open now - and the retry would find it and
    # answer it with the NEXT rune's target. Cancelling here is what keeps one
    # failed application from poisoning the two attempts after it.
    try:
        if Target.HasTarget():
            log("The target cursor from that attempt is still open -- cancelling it so "
                "the retry starts clean.", 33)
            Target.Cancel()
            safe_pause(APPLY_CURSOR_SETTLE_MS)
    except Exception:
        pass
    return False

APPLICATION_REFUSED_PATTERN = re.compile(r"you cannot enhance that", re.I)
    # CAPTURED LIVE 2026-09-11 19:42:44 -- the shard's exact wording when a rune is not legal on
    # the targeted item, verbatim: "You cannot enhance that." Seen six times in eighty seconds
    # while testing Cold Resist runes against freshly tailored cloth, and per the user the rune
    # "was not" consumed on any of them. Matched loosely (case-insensitive substring) because the
    # sentence may well be prefixed or punctuated differently in other refusal contexts, and a
    # missed refusal degrades to the old retry behaviour rather than to something harmful.


def application_was_refused():
    """True if the shard refused the LAST application outright.

    Safe to read without clearing anything: apply_rune_to_item() calls Journal.Clear() immediately
    before Items.UseItem(), so when it returns, the journal holds only that attempt's messages.

    A refusal is PERMANENT information -- this rune cannot go on this class of item, ever -- which
    is why it stops a run instead of retrying. Contrast a skill failure, which consumes the rune
    and simply needs another go."""
    try:
        for line in (Journal.GetJournalEntry(None) or []):
            if APPLICATION_REFUSED_PATTERN.search(getattr(line, "Text", "") or ""):
                return True
    except Exception:
        pass
    return False


# A STOP FOR THE WHOLE RUN (owner, 2026-10-18: "it's spamming errors saying it's stopping but not stopping"). Some of
# run_slot_application()'s stops are about the character, not the stat -- no perk deed to be had, Inscription too low,
# the perks unreadable, item properties unreadable -- and every later stat would meet the same wall after crafting its
# runes and travelling home for a deed again. Those set RUN_HALT to the reason; run_application_flow() ends the run on it.
RUN_HALT = [None]


def run_slot_application(property_def, slot_def, target_stat, restrict_serials=None):
    """The full automation loop. Works across every eligible BACKPACK item of slot_def's type at
    once (or, if restrict_serials is given -- see select_apply_bases() -- only the ones in that
    set), always applying the next available rune of property_def to whichever eligible item
    currently has the LOWEST value of that property -- spreading applications toward an even
    floor rather than maxing one item first. Stops when EVERY eligible item has reached
    target_stat, when the eligible backpack count drops to the category's own protected floor
    (see below), when the rune supply for property_def runs out, or when the Perk Deed is within
    DEED_STOP_MARGIN_SECONDS of its known expiration (stopping proactively rather than reactively
    discovering it expired mid-cycle). The safety gate is called before EVERY single application --
    its underlying [perks/skill query is throttled (PERKS_RECHECK_INTERVAL_SECONDS), but the
    cached expiration is still checked against the current time on every single call, so it never
    blindly trusts a stale result past the point the deed actually ran out.

    FLOOR IS NOW THE SAME FOR EVERY CATEGORY (2026-09-11) -- the run stops once one item is left,
    whether or not the target was reached. It was category-dependent from 2026-08-27 ("The Required
    Stats will be applied, even if it's the last item remaining. The Dump Stats ... only apply
    those until there is only 1 item left unbroken"), and the same user reversed it: "the average
    user will expect to be left with at least one item." See min_eligible below. This function itself
    doesn't know which caller requested it for which reason; it just reads property_def's own
    category to decide.

    FULL STOP, per the user: if a rune application completes and the target item survives, but
    its property value still can't be read off it afterward (still comes back as the same
    "undetected" reading rather than some new nonzero value), that means property detection
    itself can no longer be trusted -- halts the entire run immediately rather than skipping that
    item and continuing, since every other item's "lowest value" comparison depends on the same
    detection working correctly."""
    if property_def.get("prop_pattern") is None:
        log("Refusing to run: no live-confirmed property-text pattern for '{}' yet -- verify it "
            "with a scratch diagnostic first.".format(property_def["label"]), 33)
        return

    # ONE FLOOR FOR EVERY CATEGORY (2026-09-11), per the user: "let's change it so 'required
    # stats' still stops with only 1 item left, even if we don't have all the required stats,
    # because I think the average user will expect to be left with at least one item."
    #
    # REVERSES the 2026-08-27 rule quoted in this function's own docstring ("Required Stats will be
    # applied, even if it's the last item remaining"), from the same user. Recorded so it is not
    # later restored as a bug fix: that was correct policy then, this is correct policy now, and
    # the reason is expectation rather than mechanics -- a batch that eats the last item leaves the
    # operator with nothing to show for a target it may well have met. The dump categories (SDI,
    # Luck) are unaffected; they already used this floor.
    min_eligible = 1
    # RETRY-ON-FAIL counters (2026-08-27) -- see RUNECRAFTING_FAIL_RETRY_ATTEMPTS' own comment.
    # Defined OUTSIDE the loop so they persist across iterations (a genuine "N consecutive fails"
    # count), each reset to 0 the moment that specific step succeeds so an old, unrelated failure
    # from much earlier in a long run can't silently count against a later, different one.
    deed_expiring_retries = 0
    apply_fail_retries = 0
    detect_fail_retries = 0
    # ITEMS THE SHARD REFUSED (2026-09-11). Serial -> name, so the end-of-run summary can name them
    # rather than just counting. Loop-scoped like the counters above: a refusal is a fact about this
    # rune on that item, not a permanent property of the item.
    refused_items = {}
    _value_cache = {}   # serial -> this stat's last read value (2026-09-24). MEASURED: 150-162 applications a
                        # minute on ~10 shirts (09-16), 47 a minute on 94 axes (today), same code -- every pass
                        # re-read every eligible item's property text to find the lowest. Only the item just hit
                        # can have changed, so that is the only one re-read; a break or an unreadable result
                        # drops the entry and the next pass reads it fresh.

    def report_exclusions(where):
        """Say WHICH items were skipped and why -- printed at the start of crafting AND at the end,
        per the user, because a long batch scrolls the first message far out of sight."""
        if not refused_items:
            return
        log("{}: {} item(s) skipped -- the shard refuses '{}' on them (\"You cannot enhance "
            "that.\"). NO runes were spent on them: {}".format(
                where, len(refused_items), property_def["label"],
                ", ".join(sorted(refused_items.values()))), 33)

    # HOW MANY TO HOLD AT ONCE (2026-09-16), per the user: "below the threshold for ~100%, max 10".
    # Worked out ONCE, here: the search costs a read_property_value() per item plus up to
    # APPLY_SOURCE_BATCH_SIZE simulated batches, and top_up_from_source() runs on every pass below.
    # Only when a source chest is in play -- a run working straight out of the backpack pays
    # nothing for this and keeps whatever the player is already carrying.
    #
    # FLOOR OF min_eligible + 1, WHICH IS LOAD-BEARING: the stop below fires on
    # `len(eligible) <= min_eligible`, so a working set of min_eligible would refill the pack and
    # then immediately end the run having applied nothing ("only 1 item(s) left in the backpack").
    # Derived from the variable rather than written as a literal so the two cannot drift.
    if APPLY_SOURCE.get("container"):
        APPLY_SOURCE["working_set"] = source_working_set_size(
            property_def, slot_def, target_stat, min_eligible + 1,
            restrict_serials=restrict_serials)

    while True:
        # REFILL FIRST (2026-09-13) -- no-op unless a source chest was chosen. Done here, at the top
        # of the pass, so the same call serves the opening batch and every later replacement.
        top_up_from_source(slot_def, restrict_serials=restrict_serials)
        # in_pack_only: a rune can only be used on something in the backpack. Every OTHER caller of
        # find_slot_items() deliberately counts the chest as well -- see its own docstring.
        eligible = find_slot_items(slot_def, restrict_serials=restrict_serials, in_pack_only=True)
        # MAJORITY CATEGORY (2026-09-11): never craft on the odd item out. Recomputed each pass
        # rather than cached, for the same reason the counters are -- items break mid-batch, and the
        # winning group can legitimately change when they do.
        _winners, _excl, _cats = partition_slot_items(slot_def)
        if _cats and _excl:
            _keep = set(it.Serial for it in _winners)
            eligible = [it for it in eligible if it.Serial in _keep]
        # Drop anything the shard has already refused this run -- it cannot become legal, and
        # re-offering it would make the loop spin on the same item forever.
        if refused_items:
            eligible = [it for it in eligible if it.Serial not in refused_items]
        if len(eligible) <= min_eligible:
            if min_eligible > 0:
                log("Stopping: only {} '{}' item(s) left in the backpack -- protecting the last "
                    "one ('{}' is a Dump Stat).".format(
                        len(eligible), slot_def["label"], property_def["label"]))
            else:
                log("Stopping: no '{}' item(s) left in the backpack.".format(slot_def["label"]))
            report_exclusions("Finished")
            report_source_leftovers()
            return

        values = []
        for it in eligible:
            if it.Serial not in _value_cache:
                _value_cache[it.Serial] = read_property_value(it, property_def)
            values.append((it, _value_cache[it.Serial]))
        if all(value >= target_stat for _it, value in values):
            log("Stopping: every eligible '{}' item has reached the target stat ({}).".format(
                slot_def["label"], target_stat))
            report_exclusions("Finished")
            report_source_leftovers()
            return

        runes = count_runes(property_def)
        if not runes:
            log("Out of '{} Rune' -- checking whether more should be crafted.".format(
                property_def["syllable"].capitalize()))
            if not craft_more_runes_if_needed(property_def, eligible, target_stat):
                log("Stopping: no '{} Rune' left and none could be crafted.".format(
                    property_def["syllable"].capitalize()))
                return
            continue

        # GATE-REASON SPLIT (2026-08-27) -- rune_application_gate_ok() itself returns a single
        # bool for TWO different failure reasons (skill too low, deed not active), but only the
        # deed reason is fixable by fetching a new one below. Without this explicit split, a
        # sub-300 Inscription skill would fall into that same "fetch a new deed and continue"
        # loop -- use_perk_deed_if_needed() can keep succeeding (deeds ARE available) while the
        # gate keeps failing for the UNRELATED skill reason, burning through Perk Deeds forever
        # instead of the immediate full stop the user explicitly requires for this exact case
        # ("inscription under 300 ... still a full stop").
        refresh_gate_cache()
        if not _gate_cache["skill_ok"]:
            log("Stopping: Inscription is below {:.1f} -- this is a hard requirement a new Perk "
                "Deed can't fix.".format(REQUIRED_INSCRIPTION_SKILL), 33)
            RUN_HALT[0] = "Inscription is below {:.1f}".format(REQUIRED_INSCRIPTION_SKILL)
            return

        if not rune_application_gate_ok():
            # FETCH A NEW DEED INSTEAD OF STOPPING (2026-08-27), per the user, live, from a real
            # mid-batch failure ("'10% Less Break Chance...' perk is not active" -> "Stopping:
            # safety gate failed" -> the whole run ending): "We should be going to get a new deed
            # here instead of ending craft." This gate can fail mid-batch even though the deed WAS
            # confirmed active earlier in the batch -- a long batch can simply outlast the deed's
            # own buff duration. (run_application_flow() used to check once up front; that call was
            # removed 2026-09-14 because it also blocked CRAFTING, which needs no deed. This is now
            # the only deed gate, and the only one that ever needed to exist.) Same
            # philosophy as use_perk_deed_if_needed()'s own home-storage fallback (2026-08-27, per
            # the user: "Instead of stopping when we're out of perk deed, go ahead and grab
            # another... and use it instead") -- applied here to the "it just expired mid-run" case
            # too, not just the "none was ready to use in the first place" case.
            # A FAILED READ IS NOT AN EXPIRED DEED (2026-09-16). Everything below spends a real
            # resource on the belief that the perk is gone, and tonight that belief came from a
            # BROKEN READER: read_active_perks() was still scanning the journal for a format the
            # shard stopped printing on 2026-09-08, so it reported no perks while the deed was
            # live until 12:26:01 PM -- and this drove home hunting a deed it already had.
            #
            # A gump that did not appear is usually transient, so force ONE fresh read and
            # re-loop. RUNECRAFTING_FAIL_RETRY_ATTEMPTS consecutive failures means something is
            # actually wrong with the read, and then stopping is right -- grinding at full break
            # chance while blind to the perk is the one outcome worth refusing.
            if not _gate_cache["perks_readable"]:
                if _gate_cache["read_failures"] < RUNECRAFTING_FAIL_RETRY_ATTEMPTS:
                    log("The Active Perks gump could not be read ({}/{}) -- re-reading rather "
                        "than spending a Perk Deed on a guess."
                        .format(_gate_cache["read_failures"], RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
                    refresh_gate_cache(force=True)
                    continue
                log("Stopping: the Active Perks gump could not be read {} times in a row, so "
                    "whether the break-chance perk is active is unknown. Not applying runes "
                    "blind, and not spending a deed we may not need."
                    .format(_gate_cache["read_failures"]), 33)
                RUN_HALT[0] = "the Active Perks gump could not be read"
                return
            log("Perk Deed buff not active -- fetching/using a new one instead of stopping.", 33)
            if not use_perk_deed_if_needed():
                log("Stopping: safety gate failed, and a new Perk Deed couldn't be obtained/used.", 33)
                RUN_HALT[0] = "no Perk Deed is active and none could be found to use"
                return
            continue  # Re-loop so the gate/eligible-item state is re-read fresh against the new
                       # deed, rather than proceeding on whatever was already computed this pass.

        expiration = deed_expiration_known()
        if expiration is not None:
            remaining_deed_seconds = (expiration - datetime.datetime.utcnow()).total_seconds()
            if remaining_deed_seconds <= DEED_STOP_MARGIN_SECONDS:
                # RETRY-ON-FAIL (2026-08-27) -- not one of the 3 exclusions, so this proactive
                # early-stop now waits a bit and re-checks instead of ending immediately. By the
                # time it's genuinely expired, rune_application_gate_ok()'s own reactive check
                # (above) already fetches/uses a fresh deed and retries -- this bounded wait just
                # gives that a chance to happen naturally instead of stopping preemptively.
                deed_expiring_retries += 1
                if deed_expiring_retries >= RUNECRAFTING_FAIL_RETRY_ATTEMPTS:
                    log("Stopping: Perk Deed still expiring in {:.0f}s after {} wait(s) -- ending "
                        "now, {}s ahead of time, rather than risk an application without it "
                        "active.".format(remaining_deed_seconds, deed_expiring_retries,
                                          DEED_STOP_MARGIN_SECONDS))
                    RUN_HALT[0] = "the Perk Deed is about to run out"
                    return
                log("Perk Deed expires in {:.0f}s -- waiting briefly instead of stopping "
                    "({}/{})...".format(remaining_deed_seconds, deed_expiring_retries,
                                         RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
                safe_pause(RUNECRAFTING_FAIL_RETRY_PAUSE_MS)
                continue
        deed_expiring_retries = 0

        target_item, before_value = min(values, key=lambda pair: pair[1])
        log("Applying '{}' to {} (Serial={}), current value {} (target {}).".format(
            property_def["label"], slot_def["label"], hex(target_item.Serial), before_value, target_stat))

        # Snapshot for the detect-fail branch below: if the tracked value still reads 0
        # afterwards, a CHANGE in this text is what separates real progress (cah -29 -> -22, which
        # reads 0 both times because 0 means "not finished") from a wrong pattern or a failed
        # application, which change nothing at all.
        before_props = read_property_lines(target_item)

        ok = apply_rune_to_item(runes[0], target_item)
        if not ok and application_was_refused():
            # THE SHARD SAID NO -- TO THIS ITEM (2026-09-11). Not a failure of ours and not a bad
            # roll, so retrying is pointless: no number of attempts makes a rune legal. But it is
            # equally not a verdict on the BATCH. A Neck pool legitimately holds a gorget (Armor)
            # and a necklace (Jewelry); a GEAR-only rune belongs on the first and not the second,
            # and stopping everything because of the second would waste the first. So the item
            # leaves the pool and the run carries on.
            #
            # SELF-TERMINATING AND FREE: each exclusion costs exactly one refusal, a refusal
            # consumes no rune (confirmed live), and once every item is excluded the existing
            # "no item(s) left in the backpack" stop fires on the next pass.
            item_name = (getattr(target_item, "Name", "") or "?")
            refused_items[target_item.Serial] = item_name
            log("REFUSED on '{}' (0x{:X}) -- the shard will not put '{}' on that item (\"You "
                "cannot enhance that.\"). No rune was consumed. Skipping it and continuing with "
                "the rest of the {}(s).".format(
                    item_name, target_item.Serial, property_def["label"], slot_def["label"]), 33)
            report_exclusions("So far")
            continue
        if not ok:
            # RETRY-ON-FAIL (2026-08-27) -- not one of the 3 exclusions.
            apply_fail_retries += 1
            if apply_fail_retries >= RUNECRAFTING_FAIL_RETRY_ATTEMPTS:
                log("Stopping: application kept not completing as expected after {} "
                    "attempts.".format(apply_fail_retries), 33)
                return
            log("Application didn't complete as expected -- retrying ({}/{})...".format(
                apply_fail_retries, RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
            safe_pause(RUNECRAFTING_FAIL_RETRY_PAUSE_MS)
            continue
        apply_fail_retries = 0

        # A BREAK IS THE ITEM GONE (2026-10-17): asked of the item itself -- a broken item is deleted from the world --
        # never inferred from a walk of the pack, which a moving item can cut short (A COPY THAT HOLDS)
        _now = Items.FindBySerial(target_item.Serial)
        still_present = _now is not None and _now.Container == Player.Backpack.Serial
        if not still_present:
            log("'{}' (Serial={}) is gone -- it broke.".format(slot_def["label"], hex(target_item.Serial)), 33)
            _value_cache.pop(target_item.Serial, None)
            continue

        # Poll for the property text to actually update rather than a blind settle pause -- same
        # polling-over-fixed-sleep reasoning as craft_and_verify()/apply_rune_to_item(). Small
        # cap: this is only waiting for an ALREADY-consumed change's property text to refresh,
        # not a full server round trip (that's already covered by apply_rune_to_item()'s own
        # consume-poll). Also checks for a world save (see wait_out_world_save()) so its freeze
        # doesn't get misread as a genuine FULL STOP-worthy detection failure below.
        _value_cache.pop(target_item.Serial, None)   # unknown until the read below lands (2026-09-24)
        # EVERY APPLICATION IS MEASURED (owner, 2026-09-24 11:0x: "we measure every rune application, and every
        # application has a required success measurement. if the rune is consumed and success not measured, we
        # stop immediately. that was the plan from day one."). Success = the tracked value READ and MOVED. The poll
        # waits for the CHANGE, not for a non-zero read -- an unchanged number read back instantly and passed as
        # "Survived". The 2026-09-11 "property text changed -- progress, continuing" escape is gone: it counted
        # 836 unread Durability Bonus applications on 21 axes as progress today (130 runes into one axe).
        after_value = before_value
        waited_ms = 0
        while waited_ms < APPLY_PROPERTY_SETTLE_TIMEOUT_MS:
            after_value = read_property_value(target_item, property_def)
            if after_value is not None and after_value != before_value:
                break
            safe_pause(APPLY_PROPERTY_SETTLE_POLL_INTERVAL_MS)
            if wait_out_world_save():
                continue
            waited_ms += APPLY_PROPERTY_SETTLE_POLL_INTERVAL_MS
        if after_value is None or after_value == before_value:
            current = read_property_lines(target_item)
            if not current:
                # THE ONE RETRY: the item's text could not be read AT ALL. Nothing is learned by spending another
                # rune and nothing is lost by asking again -- the rune is already consumed (still_present was True),
                # so "retry" means re-check, never re-apply.
                detect_fail_retries += 1
                if detect_fail_retries >= RUNECRAFTING_FAIL_RETRY_ATTEMPTS:
                    log("FULL STOP: {}'s (Serial={}) properties could not be read at all after {} "
                        "attempts -- detection itself is broken, not safe to continue.".format(
                            slot_def["label"], hex(target_item.Serial), detect_fail_retries), 33)
                    RUN_HALT[0] = "item properties could not be read"
                    return
                log("Couldn't read {}'s (Serial={}) properties -- re-checking ({}/{})...".format(
                    slot_def["label"], hex(target_item.Serial),
                    detect_fail_retries, RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
                safe_pause(RUNECRAFTING_FAIL_RETRY_PAUSE_MS)
                continue
            log("*** STOPPING: a '{} Rune' was CONSUMED on {} (Serial={}) and NO SUCCESS WAS MEASURED -- '{}' "
                "read {} before and {} after. ***".format(
                    property_def["syllable"].capitalize(), slot_def["label"], hex(target_item.Serial),
                    property_def["label"], before_value, after_value), 33)
            # The item's own text tells the causes apart -- a floor the shard will not go past, a pattern that
            # does not match this shard's line, or an application that never took. One rune is the whole cost.
            log("  '{}' reads this right now, matched against {!r}:".format(
                slot_def["label"], property_def.get("prop_pattern")), 33)
            for line in current:
                log("    | {}".format(line), 33)
            return
        detect_fail_retries = 0
        _value_cache[target_item.Serial] = after_value   # the one item that changed (2026-09-24)
        log("Survived: now {} (was {}).".format(after_value, before_value))


# =============================================================================
# TOP-LEVEL MODE PICKER
# =============================================================================

MODE_GUMP_ID = 0x52554E4D  # "RUNM"
MODE_BUTTON_CRAFT = 1
MODE_BUTTON_APPLY = 2


# =============================================================================
# TWO-PAGE APPLY UI (2026-09-11) -- paperdoll slot grid, then that slot's runes.
# =============================================================================

SLOT_GRID_GUMP_ID = 0x52554E47   # "RUNG" -- distinct from APPLY_REQUEST_GUMP_ID ("RUNQ").
SLOT_GRID_TILE = 44              # UO item art is ~44px; one grid cell.
SLOT_GRID_PAD = 26   # WIDENED from 10 (2026-09-11) after the first live screenshot: the cell
                     # pitch is TILE + PAD, and the label is drawn at TILE, so 10px left a ~15px
                     # line of text printing across the next row's tiles ("Earrings"/"Head"/"Neck"
                     # were sitting on top of the row below). The label now has its own band.
# 199, DELIBERATELY BELOW THE BASE (2026-09-15). _ask_which_slot_visual_once() reads a slot as
# `buttonid - SLOT_GRID_BUTTON_BASE` and rejects a negative index, so if the intercept for this
# button were ever removed it degrades to "cancel" instead of selecting the wrong slot.
SLOT_GRID_SETTINGS_BUTTON = 199
# A private sentinel, not None and not a SLOT_CATALOG entry -- those two already mean "closed"
# and "chosen". Identity-compared, so it cannot collide with any real return value.
SLOT_GRID_SETTINGS_CHOSEN = ["settings"]
SLOT_GRID_BUTTON_BASE = 200
# HOW FAR BELOW A CELL'S TOP ITS CAPTION SITS (2026-09-15), per the user: "move all the words
# up under each button. They look more like they are associated with the button below them
# based on their spacing." They were. Measured from the live screenshot -- button top 45,
# label top 89, next button 115 -- with a ~22px arrow and an ~18px label, the gap above each
# caption was 22px and the gap below it 8px. 34 inverts that to 12 above / 18 below.
#
# This used to be SLOT_GRID_TILE (44), which is the ITEM ART size reused as a vertical offset.
# The art is drawn at y+6 and the button under it is only ~22px, so "one tile down" was never
# the same distance as "under the button". Its own constant, so it can be tuned alone.
#
# TRADE-OFF: a populated cell draws art at y+6 and UO equipment art runs up to ~44px, so an
# unusually tall one can touch the caption. Empty cells show the ~22px arrow and have
# clearance. Raise this number if a real item ever clashes.
# 34 -> 26 (2026-09-15), per the user: "move all the item slot labels up further." Measured
# from the second screenshot: the arrow art is ~20px tall, so 34 left 14px above a caption and
# 20px below. 26 gives 6 above and 28 below -- unambiguous rather than merely balanced.
SLOT_GRID_LABEL_DY = 26
# MEASURED, NOT THE FILE'S USUAL 8 (2026-09-15), per the user: "Align settings to the right."
# It was not, because right-aligning with 8px/char over-estimates this font badly -- the title
# (22 chars) renders 139px, i.e. 6.3px/char, and "Settings" renders ~49px against the 64 the
# formula assumed, landing the text 15px left of its anchor. 6 is the measured figure rounded
# DOWN so a right-aligned caption sits flush to the margin instead of short of it.
#
# Used ONLY for the Settings caption. The same 8px/char also mis-centres the title by ~18px,
# but that was not what was asked for and the estimate is used elsewhere for things that
# currently render fine.
SLOT_GRID_CAPTION_CHAR_PX = 6
SLOT_GRID_CAPTION_H = 18        # One caption line. Only the panel height uses it.
SLOT_GRID_BOTTOM_PAD = 25       # Gap under the last caption. Matches SLOT_GRID_ORIGIN_X so the
                                # bottom margin equals the sides -- kept separate from it
                                # because one is a horizontal origin and one a vertical margin.
SLOT_GRID_ORIGIN_X = 25
SLOT_GRID_ORIGIN_Y = 45
SLOT_RUNES_BACK_BUTTON = 1       # Page 2 -> back to the grid. 0 is "closed the gump".
SLOT_RUNES_CLEAR_BUTTON = SLOT_RUNES_BACK_BUTTON + 2   # Page 2 -> zero every field and redraw.
                                 # +1 is Calculate (added inline at its own AddButton), so this
                                 # is 3. Derived rather than written as a literal for the same
                                 # reason Calculate is: renumbering Back must not silently
                                 # collide two buttons onto one id.
SLOT_RUNES_CLEARED = "cleared"   # ask_runes_for_slot()'s THIRD answer (2026-09-16), returned in
                                 # the `back` position. NOT True and NOT False: True means "go
                                 # back to the slot grid", which would throw away the slot the
                                 # player picked, and False means "carry on with these requests".
                                 # A sentinel keeps the caller's existing `if back:` correct for
                                 # the real Back button while letting Clear re-show THIS slot.
# TEMPLATES (owner, 2026-10-17: "From the screen where the player sets all their target thresholds, We could give them a
# text entry box and a Save Template button, then that would add a button to that screen so they could load those same
# thresholds in future runs. Maybe a max of 10 so it can't get ridiculous? it just refreshes the screen with those
# numbers prefilled. It doesn't move to the next screen."). BY THE RUNES, NOT THE SLOT (owner, 2026-10-17: "Don't make
# them per slot. Make them per matching rune set. If a chosen template can work for the selected slot, it should be
# shown."): a template is the runes it sets (a value above 0) and their values, in one list for every screen; a screen
# shows each template whose every rune is a field on it. Loading one sets those runes and zeroes the screen's others.
# Saved under the script's data folder, by name; the same name again replaces it, and the runebook's own X removes one
# -- the way to make room under the cap. Both buttons only rewrite the remembered values and redraw THIS screen (the
# SLOT_RUNES_CLEARED answer Clear All uses).
SLOT_RUNES_SAVE_TEMPLATE_BUTTON = SLOT_RUNES_BACK_BUTTON + 3   # 4: after Back (1), Calculate (2), Clear All (3)
SLOT_RUNES_TEMPLATE_LOAD_BASE = 50       # + the template's place on this screen: fill the screen with it
SLOT_RUNES_TEMPLATE_DELETE_BASE = 70     # + the template's place on this screen: remove it
TEMPLATES_MAX = 10                       # in all, so a screen never shows more than this either
TEMPLATE_NAME_MAX_CHARS = 16             # what fits beside the arrow, the X still inside the column
TEMPLATE_NAME_ENTRY_ID = 999             # its own id, far past the fields' 1..n, and added after them
TEMPLATES_FILENAME = "Templates.txt"     # <name> TAB <label>=<value>|<label>=<value>... (only values above 0)
TEMPLATE_ENTRY_W = 220                   # the name box, inside the column's width
TEMPLATE_HEAD_ROWS = 3                   # the label, the name box, Save Template -- then one row a template


def clean_template_name(raw):
    """The typed name with the file's separators taken out, trimmed to TEMPLATE_NAME_MAX_CHARS; "" when nothing is left."""
    text = "".join(ch for ch in str(raw or "") if ch not in "\t\r\n|=")
    return " ".join(text.split())[:TEMPLATE_NAME_MAX_CHARS].strip()


def load_all_templates():
    """[(name, {label: value})] in file order, only values above 0; an absent or unreadable file is no templates."""
    out = []
    try:
        with open(script_data_path(TEMPLATES_FILENAME), "r") as f:
            for line in f:
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) < 2 or not parts[-2]:
                    continue
                values = {}
                for pair in parts[-1].split("|"):
                    label, _sep, value = pair.partition("=")
                    try:
                        if int(value) > 0:
                            values[label] = int(value)
                    except ValueError:
                        pass
                out.append((parts[-2], values))
    except Exception:
        pass
    return out


def templates_fitting(field_labels):
    """[(name, {label: value})] whose every rune is one of `field_labels` -- the templates a screen can load."""
    fields = set(field_labels)
    return [(n, v) for n, v in load_all_templates() if set(v) <= fields]


def save_all_templates(templates):
    """Rewrites the file with `templates` [(name, {label: value})], values above 0 only. True when written."""
    if not ensure_script_data_dir():
        log("Could not create the data folder '{}' -- the template was not saved.".format(script_data_dir()), 33)
        return False
    path = script_data_path(TEMPLATES_FILENAME)
    try:
        with open(path, "w") as f:
            for name, values in templates:
                f.write("{}\t{}\n".format(name, "|".join(
                    "{}={}".format(k, values[k]) for k in sorted(values) if values[k] > 0)))
        return True
    except Exception as _save_err:
        log("Could not write '{}' ({}) -- the template was not saved.".format(path, _save_err), 33)
        return False


APPLY_REQUEST_CLEAR_ART_UP = 4011     # THE RUNEBOOK'S ORGANIZE BUTTON, measured 2026-09-16 and then
                                 # CORRECTED. Per the user: "dump [ar for the organize button icon
APPLY_REQUEST_CLEAR_ART_DOWN = 4013   # if you can, then use that."
                                 #
                                 # FIRST ANSWER WAS WRONG -- 4008/4010, spotted at once by the user:
                                 # "you got the other button there... You got the one used for
                                 # gates." OmniData/ScratchTest_ARGumpArt.txt (live dump of
                                 # gump 0xC395ADB4) lays the book out as:
                                 #
                                 #   PER RUNE ROW, three buttons:
                                 #     x=330  4005/4007  recall arrow
                                 #     x=360  4008/4010  GATE          <- what was first picked
                                 #     x=390  4017/4019  X, delete
                                 #   BOTTOM ROW at y=379, three buttons, all 4011/4013:
                                 #     x=80   id 1    New Rune
                                 #     x=238  id 3    New Runebook
                                 #     x=385  id 500  ORGANIZE        <- the right one
                                 #
                                 # 4011 appears exactly 3 times and only on that bottom row, which
                                 # is what pins it. THE LESSON FROM THE MISS: "appears only as a
                                 # per-row middle button" did identify a consistent button -- just
                                 # not the right one. Position alone cannot tell gate from organize;
                                 # uniqueness is not identity, and the label beside it settles what
                                 # the coordinates cannot.
                                 #
                                 # Proven to render because the runebook draws it, which is the bar
                                 # this file's "an unverified art draws nothing at all, with no
                                 # error" rule sets. SWAP HERE, nowhere else.

# THE REAL DOLL (2026-09-11) -- transcribed from the user's own labelled screenshot of this
# shard's advanced paperdoll, replacing the head-to-toe guess that stood here. (label, col, row) on
# a 5-wide grid: columns 1-3 are the centre stack, 0 and 4 the side rails, exactly as the doll
# arranges them.
#
# KEYED BY LABEL, NOT LAYER. Weapon and Ranged share the 'FirstValid' layer, so a layer key can no
# longer identify a cell; labels are unique. slot_def_for_label() does the lookup and SLOT_CATALOG
# stays the single source of slot identity -- this table carries geometry and nothing else, which
# is why re-transcribing the doll only ever touches these lines.
#
# TALISMAN sits on the real doll between Shirt and Hands and is deliberately NOT here. That used to
# be caution -- no SLOT_CATALOG entry, no RuneSlotLogic.SLOT_CATEGORIES mapping, so no verified
# answer for which runes it accepts. It is now a MEASURED FACT: per the user, 2026-09-11, "i tried
# SDI on Talisman and it didn't work, so they are out."
#
# THAT ONE TEST SETTLES THE WHOLE SLOT, which is why no follow-up is needed. SDI (corp) is
# UNIVERSAL in RUNE_TARGETS -- legal on every category the table knows. A rune that is valid
# everywhere being refused on a Talisman means no rune reaches it at all, so there is nothing to
# map and no cell to add. Contrast a narrower rune failing, which would only have ruled out its own
# category.
#
# DO NOT RE-OPEN THIS as "untested". The grid skips any label it cannot resolve, so the omission
# costs one gap rather than an error, and the gap is correct.
PAPERDOLL_LAYOUT = [
                            ("Earrings", 1, 0), ("Head",  2, 0), ("Neck",     3, 0),
    # Ranged (0,1) and Quiver (4,2) LEFT THE GRID 2026-09-14 -- folded into Weapon and Cloak, which
    # now name themselves after whatever the vote detected. The cells are simply gone rather than
    # backfilled: this list IS the geometry, holes and all, so nothing reflows.
                            ("Weapon",   1, 1), ("Torso", 2, 1), ("Shield",   3, 1),
                            ("Arms",     1, 2), ("Robe",  2, 2), ("Cloak",    3, 2),
    ("Tunic",  0, 3),       ("Ring",     1, 3), ("Waist", 2, 3), ("Bracelet", 3, 3),
                                                                 ("Skirt",    4, 3),
    ("Shirt",  0, 4),       ("Hands",    1, 4), ("Pants", 2, 4), ("Shoes",    3, 4),
]


def slot_def_for_label(label):
    """The SLOT_CATALOG entry with this label, or None.

    BY LABEL, not layer (2026-09-11): Weapon and Ranged share the 'FirstValid' layer, so a layer
    lookup would return whichever came first and the Ranged cell would silently become a second
    Weapon cell -- offering 48 runes where it promised 50. Labels are unique."""
    for slot in SLOT_CATALOG:
        if slot["label"] == label:
            return slot
    return None


def partition_slot_items(slot_def):
    """(winners, excluded, categories) for a slot -- THE single source of "what is this slot about".

    Groups the slot's backpack items by what classify_item() makes of them and keeps the largest
    group, per the user: "we got 100 helmets and accidentally 1 bandana, we just ignore the bandana,
    don't show cloth runes, and don't try to craft on it."

    TIES GO TO THE CATEGORY OFFERING THE MOST RUNES, also per the user. That is the general form of
    the rule -- the larger rune set can never hide an option the smaller one would have offered, so
    a tie resolved that way costs the operator nothing either way.

    UNDECIDED ITEMS (classify_item() -> ()) DO NOT VOTE, since they support neither side, but they
    STAY IN THE POOL: a refusal costs no rune and says so out loud, so letting the shard rule on
    them beats excluding something that may well be craftable.

    An explicit slot_def["categories"] (the Weapon and Ranged cells) bypasses the vote entirely --
    those two share a layer and naming their categories is the whole reason they are separate
    cells."""
    items = find_slot_items(slot_def)
    override = slot_def.get("categories")
    if override:
        return items, [], tuple(override)
    return vote_winning_category(items)


def vote_winning_category(items):
    """(winners, excluded, categories) for a bare LIST of items -- the vote itself, with no slot.

    EXTRACTED FROM partition_slot_items() (2026-09-13) rather than reimplemented, so a chest full of
    gorgets is judged by exactly the same rule a backpack full of gorgets already was. Everything
    below was partition_slot_items()' own body; its docstring still describes the policy."""
    if not items:
        return [], [], ()

    groups = {}
    undecided = []
    excluded_books = []
    for it in items:
        try:
            Items.WaitForProps(it, 1000)
            lines = Items.GetPropStringList(it) or []
        except Exception:
            lines = []
        cats = tuple(classify_item(lines, str(getattr(it, "Layer", "") or "")))
        # NEVER SPELLBOOKS (2026-09-11), per the user, emphatically: "i never ever want those to
        # craft on spellbooks. I refuse." find_slot_items() already strips them out of any pool
        # whose layers include FirstValid, so this is a SECOND lock on the same door -- an
        # instruction that absolute should not depend on a filter three functions away staying
        # correct, and a spellbook can never become a winning category here regardless.
        if SPELLBOOK in cats:
            excluded_books.append(it)
            continue
        if not cats:
            undecided.append(it)
        else:
            groups.setdefault(cats, []).append(it)

    if not groups:
        # Nothing decidable. Spellbooks still never come back as winners.
        return undecided, excluded_books, ()

    def rank(cats):
        # exact=True (2026-09-14): `cats` here came from classify_item() on a REAL item, so a
        # restrictive category must count at its true size. Without it a group of quivers would
        # rank as 27 rather than 22 and could win a tie against cloaks on a number that is not
        # true of it. Ties still go to the larger REAL set, which is the rule this already had.
        return (len(groups[cats]), len(runes_for_categories(cats, exact=True)))

    best = max(groups, key=rank)
    winners = groups[best] + undecided
    excluded = [it for cats, g in groups.items() if cats != best for it in g] + excluded_books
    return winners, excluded, best


def slot_display_label(slot_def, cats):
    """The name to SHOW for a slot, given what the vote actually found in it.

    ADDED 2026-09-14, per the user: "the only UI change would be to shift what item name is
    displayed for the cloak/quiver slot based on what is actually detected."

    Folding Ranged into Weapon and Quiver into Cloak left two cells whose rune set now depends on
    the pack, so a fixed label would under-report them -- a Cloak cell full of quivers offers 22
    clothing runes, and a Weapon cell full of bows offers bala/vel. The ICON was already honest
    (slot_tile_info() draws the first winning item), which is the user's own reason folding is fine:
    "because we're showing the item icons on the psuedo paper doll we made, it becomes less
    relevant."

    "label_by_category" maps a voted category to the name to use. Falls back to slot["label"], so
    every unfolded cell is unaffected and a slot without the key needs no entry."""
    for cat, name in (slot_def.get("label_by_category") or {}).items():
        if cat in (cats or ()):
            return name
    # NOTHING VOTED (2026-09-15): items are present but produced no categories, so the fold has
    # not been decided and a folded cell must not name one of its halves. Falls through to the
    # catalog label for every cell that declares no placeholder, which is all of them but this one.
    if not cats:
        return slot_def.get("label_undetected") or slot_def["label"]
    return slot_def["label"]


def slot_tile_info(slot_def):
    """(item_id, hue, name, count) for a slot's FIRST backpack item, per the user: "pull item icons
    from the backpack (just the first thing found, if any) to use as an icon for the different
    slots." (None, 0, "", 0) when the slot has nothing.

    Reuses find_slot_items() -- the SAME pool run_slot_application() applies across -- so the icon
    and the count can never disagree with what a run would actually touch. A count of 0 is real
    information, not an empty cell: that slot has nothing to apply a rune to."""
    # THE COUNT MUST MATCH WHAT A RUN WOULD TOUCH (2026-09-11). This used to call
    # find_slot_items() directly, so the grid counted every item on the layer -- the user, with two
    # armour and two cloth head pieces: "I have those same 4 head pieces in my bag, so it should
    # only show 2 there. Even if i remove a cloth head piece from the bag to break the tie, it
    # shows 3 instead of the 2 I'd expect." Partitioning here is what makes the tile honest.
    items, _excluded, cats = partition_slot_items(slot_def)
    if not items:
        # THE EMPTY CELL NAMES THE LAYER, NOT A GUESS (2026-09-15), per the user: "let's change the
        # text for the Cloak/Quiver slot to say 'Back' by default until it has scanned an inventory
        # and determined that Cloak or Quiver is more appropriate." This used to return the catalog
        # name, reasoning that "there is nothing detected to rename it after" -- correct, but that
        # made "Cloak" the pre-scan answer on a layer that just as often holds a quiver. A cell
        # with no placeholder still keeps its catalog name, so nothing else changes.
        return None, 0, "", 0, slot_def.get("label_undetected") or slot_def["label"]
    first = items[0]
    return (getattr(first, "ItemID", None), getattr(first, "Hue", 0) or 0,
            (getattr(first, "Name", "") or ""), len(items),
            slot_display_label(slot_def, cats))


def categories_for_slot_def(slot_def):
    """The item categories this slot is actually working on (2026-09-19): the explicit override, else the REAL
    items' classification, else the layer's own list. Companion to runes_for_slot_def(), for catalog rows valid
    on only some of their rune's targets -- Mage Armor and Mage Weapon share "cah"."""
    override = slot_def.get("categories")
    if override:
        return set(override)
    _winners, _excluded, cats = partition_slot_items(slot_def)
    if cats:
        return set(cats)
    return set(slot_categories(slot_def["layer"]))


def runes_for_slot_def(slot_def):
    """The syllables legal on this slot, narrowed by the REAL item when the layer is ambiguous.

    FirstValid (weapon vs spellbook), LeftHand (shield vs weapon) and Cloak (cloak vs quiver) cannot
    be decided from the layer alone -- see RuneSlotLogic.AMBIGUOUS_LAYERS. With an item present its
    property lines decide, via classify_item(), which is the whole reason that function exists. With
    the slot empty there is nothing to read and the union is correct: it shows every rune that COULD
    apply once something is in there, rather than silently narrowing on a guess."""
    layer = slot_def["layer"]
    # AN EXPLICIT CATEGORY OVERRIDE WINS (2026-09-11). Only the Weapon and Ranged cells set one,
    # because they share a layer and so cannot be distinguished by it -- runes_for_slot('FirstValid')
    # would hand both of them the same union. With the categories named outright, Weapon resolves to
    # 48 (no bala/vel) and Ranged to 50, which is the entire reason the two cells exist.
    override = slot_def.get("categories")
    if override:
        return set(runes_for_categories(tuple(override)))
    syllables = set(runes_for_slot(layer))
    # NARROWED BY THE WHOLE POOL, NOT items[0] (2026-09-11). The old version read the FIRST item and
    # narrowed everything to it, which is wrong two ways: it silently depended on backpack order,
    # and it only ran for hand_slot_is_ambiguous() layers -- a tuple that never included Head, Neck
    # or the other seven body layers, so the armour/clothing work never reached the menu at all.
    winners, excluded, cats = partition_slot_items(slot_def)
    if not cats:
        return syllables
    if excluded:
        log("{}: {} item(s) read as {} -- ignoring {} other item(s) and showing only runes that fit."
            .format(slot_display_label(slot_def, cats), len(winners), "/".join(cats), len(excluded)))
    # exact=True (2026-09-14) -- `cats` is a REAL item's classification, not a layer's list of
    # possibilities, so QUIVER narrows instead of contributing. The `syllables` return above keeps
    # the union deliberately: that is the EMPTY slot, where narrowing would be a guess.
    return set(runes_for_categories(cats, exact=True))


SOURCE_CONTENTS_WAIT_MS = 3000   # Same wait DumpChestContents.py uses for the same call.
SOURCE_MOVE_POLL_MS = 100        # Poll for the item to ACTUALLY land in the pack rather than
SOURCE_MOVE_TIMEOUT_MS = 3000    # sleeping a guessed interval -- this project's standing rule.


APPLY_SOURCE_HOME_TRIP_KEY = "home_trip_fruitless"   # set once a trip home pulls nothing, so the
                                                     # next shortfall does not travel again --
                                                     # progress-or-stop, not a trip count.


def clear_slot_source():
    APPLY_SOURCE["container"] = None
    APPLY_SOURCE["serials"] = set()
    # RESET WITH THE REST OF IT (2026-09-16): a new slot gets a fresh chance at a trip home.
    APPLY_SOURCE[APPLY_SOURCE_HOME_TRIP_KEY] = False
    # 0 = NOT WORKED OUT YET, and top_up_from_source() falls back to the fixed size on 0. Reset
    # with the rest of it so one stat's width cannot leak into the next slot's run.
    APPLY_SOURCE["working_set"] = 0
    APPLY_SOURCE["label"] = ""


def ensure_slot_source(slot_def):
    """The slot to actually run, after offering a chest when the backpack has none of this slot.

    ADDED 2026-09-13, per the user: "If the player selects neck from the first menu, but backpack
    contains no neck items, then offer the player a cursor and prompt them to select a chest with
    the items. We determine armor or jewelry based on the contents of the chest."

    Returns slot_def unchanged when the backpack already has items (and clears any earlier source),
    a DERIVED slot carrying the chest's winning categories when a chest was chosen, or None to send
    the caller back to the grid (cancelled, or the chest holds nothing for this slot).

    THE WINNING CATEGORIES RIDE ON THE SLOT, using slot_def["categories"] -- the same field the
    Weapon and Ranged cells use to name what they are. That makes the rune menu narrow correctly
    from an empty backpack (runes_for_slot_def() would otherwise show the union of everything a
    Neck could ever take), and it stops partition_slot_items() re-reading tooltips for the whole
    chest on every pass of the apply loop."""
    clear_slot_source()
    if find_slot_items(slot_def, in_pack_only=True):
        return slot_def

    # SAY IT MUST BE AT HOME (2026-09-16), per the user: "tell them to select a container near
    # their Home rune." Not a preference -- top_up_from_source() travels to the Home rune to pull
    # replacements when items break, so a chest anywhere else cannot be returned to. Stated at the
    # moment of choosing, where it can still be acted on.
    log("No '{}' items in your backpack -- target the chest holding them. It must be near your "
        "'{}' rune, so more can be fetched when items break."
        .format(slot_def["label"], SETUP_HOME_RUNE))
    serial = Target.PromptTarget(
        "Target the chest holding your '{}' items (must be near your '{}' rune)..."
        .format(slot_def["label"], SETUP_HOME_RUNE), 68)
    if not serial or serial <= 0:
        log("No chest chosen -- back to the slot picker.", 33)
        return None
    chest = Items.FindBySerial(serial)
    if chest is None:
        log("That target isn't an item this client can read -- back to the slot picker.", 33)
        return None

    Items.UseItem(chest.Serial)          # open it, same as withdraw_perk_deed_from_home_chest()
    safe_pause(GUMP_RESPONSE_SETTLE_MS)
    try:
        Items.WaitForContents(chest, SOURCE_CONTENTS_WAIT_MS)
        contents = container_items(chest)
    except Exception:
        contents = []
    layers = tuple(slot_def.get("layers") or (slot_def["layer"],))
    candidates = [it for it in contents if str(getattr(it, "Layer", "")) in layers]
    if not candidates:
        log("'{}' holds {} item(s), but none of them are '{}' -- back to the slot picker.".format(
            (chest.Name or "that container"), len(contents), slot_def["label"]), 33)
        return None

    winners, excluded, cats = vote_winning_category(candidates)
    if not winners:
        log("Nothing in '{}' can be runed as '{}' -- back to the slot picker.".format(
            (chest.Name or "that container"), slot_def["label"]), 33)
        return None

    APPLY_SOURCE["container"] = chest.Serial
    APPLY_SOURCE["serials"] = set(it.Serial for it in winners)
    APPLY_SOURCE["label"] = (chest.Name or "the chest")
    log("Using '{}' as the source: {} '{}' item(s){}, working {} at a time.".format(
        APPLY_SOURCE["label"], len(winners),
        "/".join(cats) if cats else slot_def["label"],
        (" (ignoring {} of a different kind)".format(len(excluded))) if excluded else "",
        APPLY_SOURCE_BATCH_SIZE))
    if not cats:
        return slot_def
    derived = dict(slot_def)
    derived["categories"] = tuple(cats)
    return derived


def source_working_set_size(property_def, slot_def, target_stat, floor,
                            restrict_serials=None):
    """How many items to keep in the backpack at once: the LARGEST count that still simulates
    ~100% resolution, capped at APPLY_SOURCE_BATCH_SIZE and never below `floor`.

    ADDED 2026-09-16, per the user: "instead of below 10, make it 'below the threshold for ~100%,
    max 10'" -- and, on which maths to use, "however you're already calculating that."

    WIDTH IS WHAT IS BEING CHOSEN. run_slot_application() always applies to the LOWEST item, so a
    working set rises in lockstep: ten held on thin material leaves all ten partway to target and
    none finished, where four held finishes four. simulate_stat_trial() models that same
    lowest-first rule, which is what makes this simulation predictive rather than decorative.

    LARGEST, NOT SMALLEST. Fewer items always simulate at least as well, so the size that "gives
    ~100%" is the biggest one still doing it -- hold everything that can genuinely be driven to a
    verdict and nothing past that, since each extra item only spreads the same stone thinner.

    "required", NOT "dump". simulate_batch_trials() judges a dump entry by `reached >=
    min(SUGGEST_TARGET_MIN_ITEMS_REACHED, total_start)` and that constant is now 1 (was 2 -- two of ten
    reaching target is a SUCCESS there, which is the right question for "worth suggesting" and the
    wrong one here (it would clear any bar at the full cap and change nothing). A required entry
    fails on `unresolved > 0`, which happens only when attempts_budget ran out: exactly "is there
    enough material to see this many through". Breakage is not failure, for the reason already
    written into that function -- it is the expected cost, and holding fewer would not avoid it.

    CLOSEST TO TARGET FIRST, matching select_apply_bases()' own ranking -- those need the fewest
    further applications each, so they are the ones a pull would favour.

    RETURNS APPLY_SOURCE_BATCH_SIZE WHENEVER IT CANNOT ANSWER: no gain_range for this stat, or an
    empty pool. The previous fixed behaviour is both the ceiling and the fallback."""
    gain_range = property_def.get("gain_range")
    if gain_range is None:
        return APPLY_SOURCE_BATCH_SIZE
    pool = find_slot_items(slot_def, restrict_serials=restrict_serials)
    if not pool:
        return APPLY_SOURCE_BATCH_SIZE
    cap = min(APPLY_SOURCE_BATCH_SIZE, len(pool))
    # ONE read_property_value() PER ITEM, here and nowhere else -- snapshot_property_values()
    # exists for exactly this, so the trials below stay pure in-memory Python.
    values = sorted(snapshot_property_values(pool, property_def), reverse=True)
    # THIS CALL'S OWN STAT ONLY. prepare_and_apply_one_stat() drives run_slot_application() once
    # per requested stat, so this is the material this pass will actually spend. The pools are the
    # same pack+storage counts estimate_apply_odds() feeds the simulator.
    existing_finished = available_rune_amount(property_def)
    blanks = available_blank_runes()
    stone = available_rough_stone()
    for count in range(cap, floor - 1, -1):
        entry = (property_def["label"], "required", gain_range, target_stat,
                 values[:count], existing_finished)
        probability, _reached, _broken = simulate_batch_trials(
            [entry], blanks, stone, SELECT_BASES_TRIALS_PER_CANDIDATE)
        if probability >= SOURCE_BATCH_CONFIDENCE:
            if count < cap:
                log("Working {} '{}' item(s) at a time -- the most that {} Rough Stone will "
                    "carry to {} {} (would otherwise hold {})."
                    .format(count, slot_def["label"], stone, target_stat,
                            property_def["label"], cap))
            return count
    # Not even `floor` items resolve reliably. Work at the floor anyway rather than spreading
    # wider -- and say so, because this is the run where the stone is the real limit.
    log("Working {} '{}' item(s) at a time -- {} Rough Stone is not enough to carry even that "
        "many to {} {}, so nothing is spread wider.".format(
            floor, slot_def["label"], stone, target_stat, property_def["label"]), 33)
    return floor


def top_up_from_source(slot_def, restrict_serials=None):
    """Refill the backpack working set to APPLY_SOURCE_BATCH_SIZE out of the source chest.

    ONE CALL COVERS BOTH HALVES of the user's request -- "pull out 10 items at a time" is what this
    does on the first pass, and "pull out another one for every item break" is what it does on every
    pass after, because a break is exactly what drops the pack below ten.

    BEST EFFORT BY DESIGN: a chest that has gone out of range (use_perk_deed_if_needed() can travel
    home mid-run) costs one message, not the batch. Whatever is already in the pack is still worth
    working."""
    if not APPLY_SOURCE.get("container"):
        return
    have = len(find_slot_items(slot_def, restrict_serials=restrict_serials, in_pack_only=True))
    # THE SIZE THAT STILL FINISHES, not a flat ten (2026-09-16). run_slot_application() works it
    # out once per stat -- see source_working_set_size() -- because this runs at the top of every
    # pass and the search costs a property read per item. Absent, the old fixed size stands.
    target_set = APPLY_SOURCE.get("working_set") or APPLY_SOURCE_BATCH_SIZE
    want = target_set - have
    if want <= 0:
        return
    # THE PACK'S OWN ROOM (2026-10-17): equipment does not stack, so every pulled item takes a slot, and a pull past the
    # pack's item limit failed one move at a time as "didn't come out". Bounded by the same headroom the crafts use.
    _room = bulk_craft_headroom()
    if _room < want:
        _usage = backpack_item_usage()
        if _room <= 0:
            log("The backpack holds {} -- no room to pull more '{}' out of '{}'; continuing with the {} in the pack."
                .format("{} of its {} items".format(*_usage) if _usage else "an unreadable item count",
                        slot_def["label"], APPLY_SOURCE["label"], have), 33)
            return
        log("The backpack has room for {} more item(s) -- pulling {} of the {} wanted.".format(_room, _room, want))
        want = _room
    waiting = source_items_remaining()
    if restrict_serials is not None:
        waiting = [it for it in waiting if it.Serial in restrict_serials]
    if WORK_SET[0] is not None:          # (2026-10-17) WORK FEWER ITEMS: never an item the preview left out
        waiting = [it for it in waiting if it.Serial in WORK_SET[0]]
    if not waiting and source_chest() is None:
        # GO BACK FOR THEM (2026-09-16), per the user: "return home and restock items from that
        # chest if needed to replace broken items." This used to log and give up, which is exactly
        # the case a 2% break chance over a long batch produces -- items break, the pack drains
        # below the working size, and the chest is at the Home rune while crafting happens
        # elsewhere. The prompt that chose the chest requires it to be near that rune, which is
        # what makes going there a fact rather than a guess.
        #
        # A FRUITLESS TRIP ENDS THEM. No trip cap to invent: if a trip pulls nothing, the flag
        # below stops any further travel this run -- the same progress-or-stop rule
        # restock_chisel_charges() uses.
        if APPLY_SOURCE.get(APPLY_SOURCE_HOME_TRIP_KEY):
            log("Can't reach '{}' and a trip home already came back empty -- continuing with the "
                "{} in the pack.".format(APPLY_SOURCE["label"], have), 33)
            return
        log("Out of '{}' in the pack and '{}' is out of reach -- traveling to '{}' for more."
            .format(slot_def["label"], APPLY_SOURCE["label"], SETUP_HOME_RUNE))
        if not (ar_go_folders(home_folder()) and ar_go_dest(home_point())):
            APPLY_SOURCE[APPLY_SOURCE_HOME_TRIP_KEY] = True
            log("Could not navigate the Account Runebook to '{}' -- continuing with the {} in "
                "the pack.".format(SETUP_HOME_RUNE, have), 33)
            return
        waiting = source_items_remaining()
        if restrict_serials is not None:
            waiting = [it for it in waiting if it.Serial in restrict_serials]
        if not waiting:
            APPLY_SOURCE[APPLY_SOURCE_HOME_TRIP_KEY] = True
            log("Reached '{}' but '{}' has no more '{}' waiting -- continuing with the {} in "
                "the pack.".format(SETUP_HOME_RUNE, APPLY_SOURCE["label"],
                                   slot_def["label"], have), 33)
            return
    elif not waiting:
        # The chest IS in reach and simply has nothing left of this kind.
        log("'{}' has no more '{}' waiting -- continuing with the {} already in the pack."
            .format(APPLY_SOURCE["label"], slot_def["label"], have), 33)
        return
    moved = 0
    for it in waiting[:want]:
        _room = weight_room()                     # THE PACK'S OWN WEIGHT
        if _room is not None and _room < max(1, int(getattr(it, "Weight", 0) or 0)):
            log("Pulled {} of {} -- {}; continuing with what is in the pack.".format(
                moved, want, weight_stop_line("'{}'".format(it.Name or slot_def["label"]))), 33)
            break
        # POLL for it to land rather than sleeping a guessed interval -- sent again when the item timer refused it or it
        # never landed (2026-10-10, THE MOVE IS SENT AGAIN).
        if item_move_sent(it.Serial, Player.Backpack.Serial, SOURCE_MOVE_TIMEOUT_MS, 1, SOURCE_MOVE_POLL_MS):
            moved += 1
        else:
            log("'{}' didn't come out of '{}' after {} tries -- leaving it and carrying on.".format(
                (it.Name or hex(it.Serial)), APPLY_SOURCE["label"], MOVE_TRIES), 33)
    if moved:
        log("Pulled {} '{}' out of '{}' -- {} still waiting there.".format(
            moved, slot_def["label"], APPLY_SOURCE["label"],
            len(source_items_remaining())))


def report_source_leftovers():
    """Say what is still in the chest when a run ends, so an early stop is never silent.

    Finished items are NOT rotated back in, so a working set that all reaches its target while
    nothing breaks ends the run with the chest still holding items. That is worth one honest line
    rather than a quiet exit."""
    if not APPLY_SOURCE.get("container"):
        return
    left = len(source_items_remaining())
    if left:
        log("{} item(s) are still in '{}' -- this run ended before they were needed. Run Apply "
            "again to carry on with them.".format(left, APPLY_SOURCE["label"]), 33)


def ask_which_slot_visual():
    """PAGE 1 -- the paperdoll grid, re-shown after a trip through Settings.

    A LOOP IN FRONT OF THE BUILDER (2026-09-15), rather than wrapping the builder's own ~60
    lines in `while True:` and re-indenting all of them to bury a one-line change. The redraw
    is the reason Settings returns here at all: that screen is where the perk deed chest and
    the storage keys get resolved, and the cells below are a live backpack scan, so coming
    back to a stale grid would misreport what was just fixed."""
    while True:
        choice = _ask_which_slot_visual_once()
        if choice is not SLOT_GRID_SETTINGS_CHOSEN:
            return choice
        # Closing setup comes back to the grid rather than cancelling -- backing out of
        # settings is not the same gesture as declining to pick a slot, and the grid's own
        # close button still means cancel. Its return value is therefore not consulted.
        show_setup_gump(setup_item_rows())


def _ask_which_slot_visual_once():
    """One showing of the paperdoll grid. Returns a SLOT_CATALOG entry, None if the gump was
    closed, or SLOT_GRID_SETTINGS_CHOSEN if the corner button was pressed.

    Every cell is a button whose art is the first matching backpack item (real ItemID and real Hue),
    with the item's name as a tooltip and the match count beside the label. A slot with no items
    still gets a cell -- it is a legal choice, it just has nothing to work on yet, and hiding it
    would make the doll's shape depend on inventory."""
    gd = Gumps.CreateGump(movable=True)
    cols = max(c for _l, c, _r in PAPERDOLL_LAYOUT) + 1
    rows = max(r for _l, _c, r in PAPERDOLL_LAYOUT) + 1
    cell = SLOT_GRID_TILE + SLOT_GRID_PAD
    # WIDTH IS THE GRID, NOT THE HEADER (2026-09-11), per the user: "That text up top can be
    # reduced to just 'Pick an Equipment Slot' hopefully that also pulls in the extra space on the
    # right." It does -- the trailing +90 existed ONLY to fit the old one-line explanation, so
    # shortening the text and dropping the pad are the same change. The widest thing left is the
    # bottom-row label of the rightmost occupied column, which fits inside its own cell plus the
    # origin margin.
    width = SLOT_GRID_ORIGIN_X * 2 + cols * cell
    # MEASURED TO THE LAST CAPTION, NOT THE LAST CELL (2026-09-15), per the user: "we can trim
    # a little off the bottom." This was `rows * cell + 30` -- a full cell pitch for the last
    # row plus a flat 30 -- which was sized when captions sat at y+44. They sit at y+26 now,
    # and the flat constant never tracked SLOT_GRID_LABEL_DY, so the whole 18px of that move
    # became dead space: last caption bottom ~369 against a panel bottom of 425, 56px of
    # nothing beside a 25px side margin.
    #
    # Four full pitches reach the LAST ROW'S TOP, then the caption offset, the caption, the
    # margin. The value of this is not the 31px it saves -- it is that raising SLOT_GRID_LABEL_
    # DY (the escape hatch if a tall item art ever meets a caption) now grows the panel to
    # match instead of quietly eating the margin again.
    height = (SLOT_GRID_ORIGIN_Y + (rows - 1) * cell + SLOT_GRID_LABEL_DY
              + SLOT_GRID_CAPTION_H + SLOT_GRID_BOTTOM_PAD)

    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, width, height, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, width, height)
    # CENTRED (2026-09-11), per the user. Computed from the text rather than AddHtml's
    # DIV ALIGN=CENTER: this project already found that path unreliable for gump labels -- see
    # Omni_Engine.py's perk_row_html(), whose comment records a blurry/off-centre render
    # because <B>/<BIG> swap to a different font resource whose "asymmetric glyph metrics were also
    # throwing off the DIV ALIGN=CENTER math". Same ~8px/char the Apply button's right-alignment
    # uses, so both ends of the UI agree about the font.
    _title = "Pick an Equipment Slot"
    Gumps.AddLabel(gd, max(SLOT_GRID_ORIGIN_X, (width - len(_title) * 8) // 2), 15, 68, _title)

    # SETTINGS, TOP-RIGHT AND ON ITS OWN (2026-09-15), per the user: "Let's get a settings
    # button in the top right here, isolated from the other buttons." It sits outside the
    # grid's origin box; the centred title ends ~56px to its left.
    #
    # 4014/4015, not the cells' 4005/4007: distinct at a glance, and still inside the set this
    # project has actually seen render -- those two pairs are the only ones used anywhere in
    # the suite. The comment on the cell buttons below explains why that matters: an
    # unverified art draws NOTHING, with no error. The meaning rides on a tooltip, because the
    # gap to the title is 56px and "Settings" needs 64 at this file's ~8px/char.
    Gumps.AddButton(gd, width - SLOT_GRID_ORIGIN_X - 31, 12, 4014, 4015,
                    SLOT_GRID_SETTINGS_BUTTON, 1, 0)
    Gumps.AddTooltip(gd, "Settings -- storage keys, perk deed chest, Home/Scribe runes")
    # CAPTIONED TOO (2026-09-15), per the user: "put the word Settings under that button,
    # leave the tooltip". The caption says WHAT it is, the tooltip says what it covers.
    # RIGHT-ALIGNED to the button's right edge -- both end at width - SLOT_GRID_ORIGIN_X --
    # because centring it under the button would start it at x=391, nine pixels from the panel
    # edge. Uses the same SLOT_GRID_LABEL_DY as every grid caption so the corner matches.
    _settings_caption = "Settings"
    Gumps.AddLabel(gd, width - SLOT_GRID_ORIGIN_X
                   - len(_settings_caption) * SLOT_GRID_CAPTION_CHAR_PX,
                   12 + SLOT_GRID_LABEL_DY, 68, _settings_caption)

    for label, col, row in PAPERDOLL_LAYOUT:
        slot = slot_def_for_label(label)
        if slot is None:      # A geometry entry naming a slot SLOT_CATALOG does not offer.
            continue          # Skipped rather than crashing, so a bad edit costs one cell.
        x = SLOT_GRID_ORIGIN_X + col * cell
        y = SLOT_GRID_ORIGIN_Y + row * cell
        button_id = SLOT_GRID_BUTTON_BASE + SLOT_CATALOG.index(slot)
        # 4005/4007 -- the SAME button art every other gump in this file already uses, so it is
        # known to render on this client. A square tile art would look better, but an unverified
        # gump art fails INVISIBLY (no error, just nothing drawn), and an unclickable grid would
        # read as a broken layout rather than a wrong art id. Swap it once one is confirmed live.
        Gumps.AddButton(gd, x, y, 4005, 4007, button_id, 1, 0)
        item_id, hue, name, count, tile_label = slot_tile_info(slot)
        # ON THE BUTTON, AND ALWAYS (2026-09-16), per the user: "make sure every button has a
        # tooltip ... it feels like something is broken when some have tooltips and others
        # don't." This hung off AddItem, so a cell with NOTHING in it had no tooltip -- and an
        # empty cell is exactly the one a player hovers to ask what goes there.
        if name:
            # NO THRESHOLD HERE (2026-09-16), per the user: "there is no threshold handling
            # here, we should remove that text." The empty-cell branch below was corrected
            # earlier for the same reason and this one was missed, so the rejected wording was
            # still showing on every cell that HAD items. Name and count only -- the redundant
            # tooltip the user asked for on every button ("even if it's just the same text
            # already labeling the button").
            _cell_tip = "%s (%d in pack)" % (name, count)
        else:
            # WHAT CLICKING AN EMPTY CELL ACTUALLY DOES (2026-09-16), per the user: "We're not
            # setting a threshold, it should say -- click to set a storage container if it's
            # empty." My own wording described the NEXT screen. ensure_slot_source() prompts with
            # a target cursor for the container holding these items, votes on its contents to
            # settle the category, and works %d at a time out of it.
            _cell_tip = ("Nothing in your pack for this slot -- click and you will be asked to "
                         "target the storage container holding them. Keep that container near "
                         "your '%s' rune: it works a few at a time out of it and travels back "
                         "there for more when items break." % SETUP_HOME_RUNE)
        # THE CELLS THAT WORK OUT WHAT THEY ARE (2026-09-16), per the user: "for the slots that
        # calculate what is being used, offer a short explanation."
        #
        # RECOGNISED FROM VALUES ALREADY IN HAND, not a new scan: a tile_label that differs from
        # the catalog label means the cell RENAMED itself after what partition_slot_items()
        # actually found, and "label_undetected" is this file's own marker for "cannot be known
        # until a pack is scanned". Re-partitioning here to count the excluded items would cost a
        # property read per cell, and widening slot_tile_info() is the change that crashed this
        # script an hour ago.
        # NAME WHAT THE CELL COVERS (2026-09-16), per the user: "For the Back slot, by default
        # explain that it includes Cloak and Quiver." The old text said a cell covered more than
        # one kind of item without ever saying WHICH, which is the part worth knowing.
        _covers = slot.get("covers")
        if tile_label != slot["label"]:
            _cell_tip += (" This cell covers %s; it reads '%s' because that is what your pack "
                          "holds." % (_covers or "more than one kind of item", tile_label))
        elif _covers:
            _cell_tip += (" This cell covers %s -- it names itself after whichever it finds once "
                          "there is something to scan." % _covers)
        Gumps.AddTooltip(gd, _cell_tip)
        if item_id:
            # Centred-ish in the cell. Real hue, so a dyed item reads as itself.
            Gumps.AddItem(gd, x + 6, y + 6, item_id, hue)
            if name:
                Gumps.AddTooltip(gd, _cell_tip)
        # 68 normal / 33 attention -- the only two hues this file uses and has seen render.
        # An empty slot is still selectable; the hue just says there is nothing in it yet.
        # NAMED AFTER WHAT IS IN IT (2026-09-14), not after the catalog entry: the folded Weapon
        # and Cloak cells read "Ranged" / "Quiver" when that is what the vote found, so the label
        # never disagrees with the rune set behind the button. Every other cell is unchanged.
        Gumps.AddLabel(gd, x, y + SLOT_GRID_LABEL_DY, 68 if count else 33,
                       "%s%s" % (tile_label, (" x%d" % count) if count > 1 else ""))

    Gumps.SendGump(SLOT_GRID_GUMP_ID, Player.Serial, 300, 200, gd.gumpDefinition, gd.gumpStrings)
    log("Pick the equipment slot you want to rune.")
    if not Gumps.WaitForGump(SLOT_GRID_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        log("Slot grid timed out with no response.", 33)
        return None
    response = Gumps.GetGumpData(SLOT_GRID_GUMP_ID)
    if response is None:
        return None
    # Checked BEFORE the index arithmetic, so the reserved id never reaches it.
    if response.buttonid == SLOT_GRID_SETTINGS_BUTTON:
        return SLOT_GRID_SETTINGS_CHOSEN
    index = response.buttonid - SLOT_GRID_BUTTON_BASE
    if index < 0 or index >= len(SLOT_CATALOG):
        return None           # 0 = closed, anything else unmapped = treat as cancel.
    return SLOT_CATALOG[index]


def ask_runes_for_slot(slot_def):
    """PAGE 2 -- only the runes legal on slot_def. Returns (requests, back) where `back` True means
    the user asked to return to the grid.

    Interaction is deliberately UNCHANGED from the flat screen it replaces: a threshold field per
    rune (0/blank = not requested), a real checkbox for is_boolean entries, fields pre-filled from
    load_last_apply_thresholds(), and any submit reads back everything at once. Only the SET of rows
    is different. Changing the interaction as well would have made a layout problem and a behaviour
    problem indistinguishable on the first live run."""
    syllables = runes_for_slot_def(slot_def)
    # A ROW MAY BE NARROWER THAN ITS RUNE (2026-09-19): Mage Armor and Mage Weapon both ride "cah".
    _cats = categories_for_slot_def(slot_def)
    props = [p for p in PROPERTY_CATALOG if p.get("syllable") in syllables
             and (not p.get("only_categories") or _cats.intersection(p["only_categories"]))]
    required = [p for p in props if p.get("category", "required") != "dump"]
    dump = [p for p in props if p.get("category") == "dump"]
    last_thresholds = load_last_apply_thresholds()

    # CHECKBOXES FILL COLUMN 1, ALPHABETICALLY (2026-09-16), per the user: "All of the
    # checkboxes should be in the first column, alphabetically. Just make sure to keep the
    # columns balanced."
    #
    # THIS IS THE ONLY PLACE THAT CAN DO IT. Pinning the boolean rows at the top of
    # PROPERTY_CATALOG was tried first and cannot work: the Weapon slot has 48 runes and FIVE
    # is_boolean rows, so `half` fell at 24 and Spell Channeling and Use Best Wep landed in
    # COLUMN 2 while Mage Armor and Night Sight stayed in column 1. Catalog position decides the
    # order within the flat list; only the split decides the column.
    #
    # BALANCE IS UNTOUCHED -- `half` is still ceil(n/2), so column 1 and column 2 are never more
    # than one row apart. Only WHICH rows lead the list changed.
    #
    # ALPHABETICAL BY CONSTRUCTION, not inherited. The order used to come from the catalog's own
    # physical order -- alphabetical by convention, with hand-pinned exceptions. Sorting both
    # groups here makes it true regardless of how the catalog is laid out.
    _checkboxes = sorted((p for p in required if p.get("is_boolean")),
                         key=lambda p: p["label"])
    _numeric = sorted((p for p in required if not p.get("is_boolean")),
                      key=lambda p: p["label"])
    required = _checkboxes + _numeric
    half = (len(required) + 1) // 2
    columns = [required[:half], required[half:], dump]
    rows_per_col = max([len(c) for c in columns] + [1])

    # TEMPLATES (2026-10-17): the ones whose every rune has a field here -- the starred runes get none.
    templates = templates_fitting(p["label"] for p in required + dump if p.get("prop_pattern") is not None)
    # UNDER THE DUMP STATS (owner, 2026-10-17 23:2x: "We have a lot of free space on the right. This is already a tall
    # panel. We should add the template stuff under the Dump Stats."): the third column, one row after its last field
    # -- a stack of rows, never a band across the bottom; the panel grows only where that column runs past the others.
    _tcol_x = 20 + APPLY_REQUEST_COLUMN_WIDTH * 2
    _tcol_row0 = len(dump) + (1 if dump else 0)
    _tcol_rows = _tcol_row0 + TEMPLATE_HEAD_ROWS + max(1, len(templates))
    _band_y = 45 + _tcol_row0 * APPLY_REQUEST_ROW_HEIGHT

    gd = Gumps.CreateGump(movable=True)
    width = 40 + APPLY_REQUEST_COLUMN_WIDTH * len(columns)
    height = 80 + max(rows_per_col, _tcol_rows) * APPLY_REQUEST_ROW_HEIGHT
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, width, height, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, width, height)
    Gumps.AddLabel(gd, 20, 15, 68, "%s -- %d rune(s) valid here" % (slot_def["label"], len(props)))
    # ONE HEADER ROW, THREE COLUMN-ALIGNED PIECES (2026-09-11), per the user: "The top looks crammed
    # with that new text. Let's get all the header text in the same line, with some reasonable
    # spacing." Stacking a second line at y=30 left only 15px before the rows began at y=45, half
    # the gap the single-line design had. Each piece is positioned at its COLUMN's x rather than
    # padded with spaces, so the spacing stays right whatever the text length.
    #
    # SAY WHICH CATEGORIES ARE ON SCREEN, per the user: "let's indicate all categories we're
    # showing. Most might just have one: Showing [Armor], but some might have Showing:
    # [Weapon][Ranged]". Without it the rune count is unexplained -- 32 versus 27 on the same slot
    # looks arbitrary unless the reason is visible.
    #
    # THE EXCLUSION COUNT IS DELIBERATELY NOT HERE, also per the user: "We don't need the ignoring 1
    # item there, I think it could be confusing... if we need to explain it further we'll do it on
    # the last screen." The grid already shows the honest per-slot count, and the preview screen is
    # where it can still be acted on.
    _w, _excl, _cats = partition_slot_items(slot_def)
    showing = "".join("[%s]" % c for c in _cats) or "[all types]"
    Gumps.AddLabel(gd, 20 + APPLY_REQUEST_COLUMN_WIDTH, 15, 68, "Showing: %s" % showing)
    # DUMP STATS GET THEIR COLUMN TITLE BACK, per the user ("let's put Dump Stats up top, not beside
    # Luck"). They already HAD their own third column; what was missing was the heading the retired
    # flat screen used to draw, so the earlier inline "[dump]" suffix was both redundant and in the
    # wrong place.
    if dump:
        Gumps.AddLabel(gd, 20 + APPLY_REQUEST_COLUMN_WIDTH * 2, 15, 68, "Dump Stats")

    next_entry_id = [1]
    next_switch_id = [1]
    text_rows = []
    check_rows = []
    drawn_order = []   # every requestable property in the order the grid draws it (2026-09-18)

    def add_column(column_props, base_x):
        y = 45
        for prop in column_props:
            # UNVERIFIED RUNES ARE MARKED, NOT HIDDEN (2026-09-11). prop_pattern None means
            # run_slot_application() will refuse this rune outright. Drawing a normal field would
            # let a threshold be typed and only THEN report the refusal. Dimmed, starred, no field.
            if prop.get("prop_pattern") is None:
                Gumps.AddLabel(gd, base_x, y + 2, 900, "* " + prop["label"])
                Gumps.AddTooltip(gd, "No live-confirmed property text yet -- verify this rune "
                                     "against a real item before it can be applied.")
                y += APPLY_REQUEST_ROW_HEIGHT
                continue
            Gumps.AddLabel(gd, base_x, y + 2, 68, prop["label"])
            drawn_order.append(prop)
            if prop.get("is_boolean"):
                switch_id = next_switch_id[0]
                next_switch_id[0] += 1
                # STICKY (2026-09-14), per the user: "make the checkboxes sticky too." This was a
                # hardcoded False, so boolean runes reset on every visit while the numeric fields
                # beside them remembered. A checkbox is a threshold that can only be 0 or 1, so it
                # rides the SAME per-label store rather than getting a parallel one of its own.
                Gumps.AddCheck(gd, base_x + 140, y, APPLY_REQUEST_CHECK_INACTIVE_ID,
                                APPLY_REQUEST_CHECK_ACTIVE_ID,
                                bool(last_thresholds.get(prop["label"], 0)), switch_id)
                check_rows.append((switch_id, prop))
            else:
                entry_id = next_entry_id[0]
                next_entry_id[0] += 1
                Gumps.AddImageTiled(gd, base_x + 140, y, 90, 20, APPLY_REQUEST_ENTRY_BACKING_TEXTURE)
                Gumps.AddTextEntry(gd, base_x + 140, y, 90, 20, 68, entry_id,
                                   str(last_thresholds.get(prop["label"], 0)))
                text_rows.append((entry_id, prop))
            y += APPLY_REQUEST_ROW_HEIGHT

    for i, column_props in enumerate(columns):
        add_column(column_props, 20 + APPLY_REQUEST_COLUMN_WIDTH * i)

    # TEMPLATES, UNDER THE DUMP STATS (2026-10-17). The name box is added AFTER every field, so a build that returns
    # the typed text without its ids still pairs the fields by position.
    _rh = APPLY_REQUEST_ROW_HEIGHT
    Gumps.AddLabel(gd, _tcol_x, _band_y + 2, 68, "Templates")
    Gumps.AddImageTiled(gd, _tcol_x, _band_y + _rh, TEMPLATE_ENTRY_W, 20, APPLY_REQUEST_ENTRY_BACKING_TEXTURE)
    Gumps.AddTextEntry(gd, _tcol_x, _band_y + _rh, TEMPLATE_ENTRY_W, 20, 68, TEMPLATE_NAME_ENTRY_ID, "")
    Gumps.AddTooltip(gd, "A name for the template, up to %d characters." % TEMPLATE_NAME_MAX_CHARS)
    Gumps.AddButton(gd, _tcol_x, _band_y + 2 * _rh, 4011, 4013, SLOT_RUNES_SAVE_TEMPLATE_BUTTON, 1, 0)
    Gumps.AddTooltip(gd, "Save the runes set on this screen and their values under the name above. Every slot that "
                         "has all of those runes shows it. Up to %d in all; the same name again replaces that one. "
                         "Nothing is crafted or spent." % TEMPLATES_MAX)
    Gumps.AddLabel(gd, _tcol_x + 35, _band_y + 2 * _rh + 2, 68, "Save Template")
    if not templates:
        Gumps.AddLabel(gd, _tcol_x, _band_y + 3 * _rh + 2, 900, "No saved template fits {}.".format(slot_def["label"]))
    for _i, (_name, _values) in enumerate(templates):
        _tx = _tcol_x
        _ty = _band_y + (TEMPLATE_HEAD_ROWS + _i) * _rh
        Gumps.AddButton(gd, _tx, _ty, 4005, 4007, SLOT_RUNES_TEMPLATE_LOAD_BASE + _i, 1, 0)
        Gumps.AddTooltip(gd, "Fill this screen with '{}': {}, every other rune here at 0. It stays on this screen -- "
                             "nothing is calculated or spent.".format(_name, ", ".join(
                                 "{} {}".format(k, _values[k]) for k in sorted(_values)) or "nothing set"))
        Gumps.AddLabel(gd, _tx + 35, _ty + 2, 68, _name)
        Gumps.AddButton(gd, _tx + 35 + TEMPLATE_NAME_MAX_CHARS * 8, _ty, 4017, 4019,
                        SLOT_RUNES_TEMPLATE_DELETE_BASE + _i, 1, 0)
        Gumps.AddTooltip(gd, "Remove the template '{}'. The values on this screen are left as they are.".format(_name))

    # BOTH ACTIONS ON THE BOTTOM ROW (2026-09-11), per the user: "let's put Apply to * on the
    # bottom right, and Back on the bottom left, I think that is more intuitive." Back used to sit
    # in the top-right corner, diagonally opposite the Apply it is the alternative to.
    Gumps.AddButton(gd, 20, height - 30, 4014, 4015, SLOT_RUNES_BACK_BUTTON, 1, 0)
    Gumps.AddTooltip(gd, "Back to the slot picker. Nothing is spent and the target values you "
                         "typed are remembered.")
    Gumps.AddLabel(gd, 55, height - 28, 68, "Back")

    # Right-aligned from the TEXT, not a fixed offset: the label carries the slot name, so "Apply to
    # Quiver" and "Apply to Middle Torso" differ by ~50px and a fixed x would overhang on the long
    # ones. ~8px per character matches the gump font this file already lays out labels with.
    # "CALCULATE", NOT "APPLY" (2026-09-11), per the user: "Let's change this to 'Calculate' then
    # used that Apply to * text on the last screen." This screen only gathers thresholds and hands
    # them to the estimator -- nothing is spent here. The preview is where runes actually get used,
    # so that is the screen whose button should say Apply.
    apply_text = "Calculate"
    apply_x = max(160, width - 20 - (35 + len(apply_text) * 8))
    Gumps.AddButton(gd, apply_x, height - 30, 4005, 4007, SLOT_RUNES_BACK_BUTTON + 1, 1, 0)
    # "Calculate" SPENDS NOTHING, and the tooltip has to say so -- that distinction is the whole
    # reason this button was renamed from "Apply" on 2026-09-11.
    Gumps.AddTooltip(gd, "Work out how many runes and how much Rough Stone these targets "
                         "need, and show a preview. Nothing is crafted or applied yet -- the "
                         "preview is where you commit.")
    Gumps.AddLabel(gd, apply_x + 35, height - 28, 68, apply_text)

    # CLEAR ALL, BETWEEN BACK AND CALCULATE (2026-09-16), per the user: "Let's also add a clear
    # all fields button to the bottom of that screen."
    #
    # CENTERED UNDER THE MIDDLE COLUMN (2026-09-16), per the user: "center it under the middle
    # column instead of having it to the left."
    #
    # It used to be derived from BACK's geometry -- just past the Back label, clamped short of
    # Calculate -- which sat it under column 1 and made it read as a second Back button. Derived
    # from the column instead: column i starts at 20 + APPLY_REQUEST_COLUMN_WIDTH * i, and the
    # button+label block is 35px of art plus ~8px per label character. Those two figures are the
    # same ones Calculate uses to right-align itself, so both buttons measure the same way.
    _clear_text = "Clear All"
    _clear_block = 35 + len(_clear_text) * 8
    _clear_x = (20 + APPLY_REQUEST_COLUMN_WIDTH
                + max(0, (APPLY_REQUEST_COLUMN_WIDTH - _clear_block) // 2))
    # NON-OVERLAP GUARD, KEPT (and widened to both sides). Centering cannot reach Calculate at
    # today's constant 820px width, but the column count and COLUMN_WIDTH are constants someone
    # may change, and a button drawn underneath another is unclickable with nothing on screen to
    # say so. Checks Back on the left as well as Calculate on the right.
    if (_clear_x > 20 + 35 + len("Back") * 8
            and _clear_x + _clear_block <= apply_x):
        Gumps.AddButton(gd, _clear_x, height - 30, APPLY_REQUEST_CLEAR_ART_UP,
                        APPLY_REQUEST_CLEAR_ART_DOWN, SLOT_RUNES_CLEAR_BUTTON, 1, 0)
        Gumps.AddTooltip(gd, "Set every field on this screen back to 0 and untick every box. "
                             "Nothing is crafted, applied or spent -- and other slots' "
                             "remembered values are left alone.")
        Gumps.AddLabel(gd, _clear_x + 35, height - 28, 68, _clear_text)

    Gumps.SendGump(APPLY_REQUEST_GUMP_ID, Player.Serial, 300, 200, gd.gumpDefinition, gd.gumpStrings)
    log("Fill in a target value for each rune you want on {} (leave the rest at 0), then Apply."
        .format(slot_def["label"]))
    if not Gumps.WaitForGump(APPLY_REQUEST_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        log("Rune list timed out with no response.", 33)
        return None, False
    response = Gumps.GetGumpData(APPLY_REQUEST_GUMP_ID)
    if response is None:
        return None, False
    if response.buttonid == SLOT_RUNES_BACK_BUTTON:
        return None, True
    if response.buttonid == SLOT_RUNES_CLEAR_BUTTON:
        # MERGED, NOT REPLACED -- the same trap the Calculate save documents: save_last_apply_
        # thresholds() opens the file with "w" and writes only what it is handed, and this screen
        # shows one slot's runes, so handing it just these labels would delete every other
        # slot's remembered values.
        #
        # FROM text_rows/check_rows, NOT the property list: those are exactly the rows that got a
        # field. A rune with prop_pattern None is drawn starred with no field at all, and zeroing
        # a value the player was never able to set would be a silent edit of something off-screen.
        _cleared = load_last_apply_thresholds()
        for _eid, _prop in text_rows:
            _cleared[_prop["label"]] = 0
        for _sid, _prop in check_rows:
            _cleared[_prop["label"]] = 0
        save_last_apply_thresholds(_cleared)
        log("Cleared every field on the {} screen -- {} row(s) back to 0.".format(
            slot_def["label"], len(text_rows) + len(check_rows)))
        return None, SLOT_RUNES_CLEARED
    if response.buttonid == 0:
        return None, False
    _load_i = response.buttonid - SLOT_RUNES_TEMPLATE_LOAD_BASE
    if 0 <= _load_i < len(templates):
        # LOAD: the template's values become the remembered ones for this screen's rows, and the screen redraws
        # with them. Merged like Clear All, so other slots' remembered values stay.
        _name, _values = templates[_load_i]
        _remembered = load_last_apply_thresholds()
        for _eid, _prop in text_rows + check_rows:
            _remembered[_prop["label"]] = int(_values.get(_prop["label"], 0))
        save_last_apply_thresholds(_remembered)
        log("Loaded the template '{}' onto the {} screen -- {} rune(s) set.".format(
            _name, slot_def["label"], len([v for v in _values.values() if v > 0])))
        return None, SLOT_RUNES_CLEARED
    _delete_i = response.buttonid - SLOT_RUNES_TEMPLATE_DELETE_BASE
    if 0 <= _delete_i < len(templates):
        _name = templates[_delete_i][0]
        if save_all_templates([tpl for tpl in load_all_templates() if tpl[0] != _name]):
            log("Removed the template '{}' -- no screen shows it now.".format(_name))
        return None, SLOT_RUNES_CLEARED

    # Same defensive read the flat screen documents: a wrong attribute name must surface as
    # "nothing requested", never a crash.
    # THE FIELD IS `text`, NOT `textList` (2026-09-11) -- see this patch's own history. RE's
    # GumpData exposes `text` (the typed values) and `textID` (the entry id each belongs to);
    # `textList` does not exist, so the old read returned [] on every submit and every threshold
    # was discarded. Symptom: "No valid request received -- stopping." with the button working
    # perfectly.
    #
    # PAIRED BY ID rather than by position. text_rows knows each row's entry_id, and textID tells
    # us which id each returned value belongs to, so the pairing no longer assumes the response
    # arrives in the order the fields were added. Positional matching is kept only as a fallback
    # for a build that returns `text` without `textID`.
    texts = list(getattr(response, "text", None) or getattr(response, "textList", None) or [])
    text_ids = list(getattr(response, "textID", None) or [])
    by_id = {}
    if text_ids and len(text_ids) == len(texts):
        for _i, _eid in enumerate(text_ids):
            by_id[_eid] = texts[_i]
    switches = list(getattr(response, "switches", []) or [])
    requests = []
    submitted = {}
    for i, (_entry_id, prop) in enumerate(text_rows):
        if by_id:
            raw = by_id.get(_entry_id, "")
        else:
            raw = texts[i] if i < len(texts) else ""
        try:
            value = int(str(raw).strip() or 0)
        except ValueError:
            value = 0
        # EVERY value, 0 included -- see the save below.
        submitted[prop["label"]] = value
        if value > 0:
            requests.append((prop, value))

    # REMEMBER WHAT WAS TYPED (2026-09-14), per the user: "the values on this page should save when
    # we hit Calculate. otherwise they reset every time if you don't go forward with the craft on
    # the next page."
    #
    # This page already PRE-FILLED from load_last_apply_thresholds() and never wrote back, so
    # anything entered here lasted only as long as the run. Saving here means it survives abandoning
    # the craft on the following page, which was the whole complaint.
    #
    # MERGED, NOT REPLACED, and that distinction matters: save_last_apply_thresholds() opens the
    # file with "w" and writes only what it is handed. The old flat screen could pass its whole
    # dictionary because it showed EVERY rune; this page shows only the ones legal on ONE slot (27
    # for Waist), so writing just those would delete every other slot's remembered values.
    #
    # ZEROS ARE KEPT for the same reason the flat screen kept them -- it stored "WHATEVER was
    # actually in each box at submission (0 included)" -- so a field the player deliberately cleared
    # comes back cleared instead of being repopulated from an older number.
    #
    # Only CALCULATE reaches here; Back and Close return above this point, because those mean "I did
    # not mean this" rather than a submission.
    # CHECK ROWS BEFORE THE SAVE (2026-09-14). The write used to sit above this loop, so the
    # checked set did not exist yet and boolean values would have been persisted a visit late.
    #
    # EVERY check row is recorded, not only the ticked ones: an UNCHECKED box saves as 0 for the
    # same reason a cleared number does, so deliberately un-ticking something is remembered instead
    # of being repopulated from an older state.
    for switch_id, prop in check_rows:
        checked = switch_id in switches
        submitted[prop["label"]] = 1 if checked else 0
        if checked:
            requests.append((prop, 1))

    # THE GRID'S OWN ORDER IS THE APPLY ORDER (2026-09-18), per the user: "they should be applied in the
    # order they are listed on the gump, so Spell Channeling should be first here." text_rows then
    # check_rows put every flag last regardless of where the grid drew it; the preview and the apply
    # loop both walk this list unchanged, so ordering it here orders both.
    _drawn = dict((id(p), i) for i, p in enumerate(drawn_order))
    requests.sort(key=lambda r: _drawn.get(id(r[0]), len(drawn_order)))
    _remembered = load_last_apply_thresholds()
    _remembered.update(submitted)
    save_last_apply_thresholds(_remembered)
    if response.buttonid == SLOT_RUNES_SAVE_TEMPLATE_BUTTON:
        # SAVE: the runes set on the screen now (a value above 0) and their values -- the rune set that decides which
        # screens show it. The typed values were just remembered above, so the redraw shows them whatever happens here.
        _name = clean_template_name(by_id.get(TEMPLATE_NAME_ENTRY_ID, "") if by_id
                                    else (texts[len(text_rows)] if len(texts) > len(text_rows) else ""))
        _set = dict((k, v) for k, v in submitted.items() if v > 0)
        _all = load_all_templates()
        _replaced = any(tpl[0].lower() == _name.lower() for tpl in _all)
        if not _name:
            log("Type a name in the Template name box first -- nothing saved.", 33)
        elif not _set:
            log("Every rune on this screen is at 0 -- set at least one before saving '{}'. Nothing saved.".format(_name), 33)
        elif not _replaced and len(_all) >= TEMPLATES_MAX:
            log("There are already {} templates -- remove one with its X, or save under one of their names to replace "
                "it. Nothing saved.".format(TEMPLATES_MAX), 33)
        else:
            _kept = [tpl if tpl[0].lower() != _name.lower() else (_name, _set) for tpl in _all]
            if not _replaced:
                _kept.append((_name, _set))
            if save_all_templates(_kept):
                log("{} the template '{}' -- {} rune(s): {}. It shows on every slot that has all of them.".format(
                    "Replaced" if _replaced else "Saved", _name, len(_set), ", ".join(sorted(_set))))
        return None, SLOT_RUNES_CLEARED
    return requests, False


def ask_apply_requests_and_slot():
    """The two-page flow, owning the name the flat screen used so run_application_flow() is
    untouched and the return contract is identical: (requests, slot_def), or (None, None).

    Loops rather than nesting: page 2's Back returns here and re-shows the grid, so picking the
    wrong slot costs one click instead of restarting the script."""
    while True:
        slot_def = ask_which_slot_visual()
        if slot_def is None:
            return None, None
        # OFFER A CHEST WHEN THE PACK IS EMPTY (2026-09-13) -- before the rune menu, because the
        # chest is what decides armour vs jewellery and therefore which runes that menu may show.
        # None means "back to the grid", the same answer page 2's Back button gives.
        if call_hook("requests_taker") is not None:
            clear_slot_source()   # a taker never applies here (2026-09-22), so no chest is offered or needed
        else:
            slot_def = ensure_slot_source(slot_def)
        if slot_def is None:
            continue
        # INNER LOOP FOR CLEAR ALL (2026-09-16). Clear has to redraw, and it must redraw THIS
        # slot -- returning the plain `back` True would bounce to the grid and lose the slot the
        # player just picked. So ask_runes_for_slot() answers SLOT_RUNES_CLEARED instead and this
        # loop simply asks again.
        #
        # ensure_slot_source() IS DELIBERATELY ABOVE THIS LOOP: it can prompt for a chest when the
        # pack is empty, and re-running that on every Clear press would re-prompt for something
        # the player already answered.
        #
        # The loop lives HERE rather than inside ask_runes_for_slot() because that function has no
        # loop of its own, and wrapping its body in one would put runes_for_slot_def() --
        # partition_slot_items(), Items.WaitForProps(it, 1000) PER ITEM -- inside the redraw path,
        # plus require every derived value to move in with it or go stale. That last failure is
        # exactly the show_setup_gump() bug fixed earlier today.
        while True:
            requests, back = ask_runes_for_slot(slot_def)
            if back != SLOT_RUNES_CLEARED:
                break
        if back:
            continue
        if not requests:
            return None, None
        return requests, slot_def

def ask_which_mode():
    """Craft Runes (phase 1) or Apply Runes (phase 2). Returns 'craft', 'apply', or None if
    closed without a valid choice."""
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 260, 110, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 260, 110)
    Gumps.AddLabel(gd, 20, 15, 68, "Omni Runecrafting")
    Gumps.AddButton(gd, 20, 45, 4005, 4007, MODE_BUTTON_CRAFT, 1, 0)
    Gumps.AddTooltip(gd, "Only build a stock of runes -- nothing gets applied to your gear.")
    Gumps.AddLabel(gd, 55, 47, 68, "Craft Runes")
    Gumps.AddButton(gd, 20, 75, 4005, 4007, MODE_BUTTON_APPLY, 1, 0)
    Gumps.AddTooltip(gd, "Pick a slot, set target values, and apply runes to it -- crafting "
                         "more along the way if the supply runs short.")
    Gumps.AddLabel(gd, 55, 77, 68, "Apply Runes")

    Gumps.SendGump(MODE_GUMP_ID, Player.Serial, 300, 300, gd.gumpDefinition, gd.gumpStrings)
    log("Choose a mode: Craft Runes or Apply Runes...")

    if not Gumps.WaitForGump(MODE_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        log("Warning: mode picker timed out with no response.", 33)
        return None
    response = Gumps.GetGumpData(MODE_GUMP_ID)
    if response is None:
        log("Warning: mode picker gave no response data.", 33)
        return None
    if response.buttonid == MODE_BUTTON_CRAFT:
        return "craft"
    if response.buttonid == MODE_BUTTON_APPLY:
        return "apply"
    log("Warning: button {} doesn't map to a known mode.".format(response.buttonid), 33)
    return None


# =============================================================================
# CRAFTING FLOW (PHASE 1)
# =============================================================================

def travel_to_scribe_if_needed():
    """Returns the Scribe mobile, traveling there first only if she isn't already nearby -- no
    reason to force an Account Runebook trip when we're already standing next to her (per the
    user: this is the common case, especially for the mid-application top-up)."""
    scribe = find_scribe()
    if scribe:
        return scribe
    if not ar_go_folders(scribe_folder()) or not ar_go_dest(scribe_point()):
        # NOT FATAL SINCE 2026-09-15. This said "FATAL ... stopping", which was true while
        # craft_n_runes() ended the batch on a failed trip. It no longer does: the trip is
        # taken only when chisel charges are below target, and failing it falls through to
        # whatever chisel is in the pack or in the carried key. A log that overstates severity
        # costs a real investigation later, because this project diagnoses from its own
        # journals -- the same reason the Tamer's "unleashing" line was corrected tonight.
        log("Could not navigate the Account Runebook to the Scribe rune -- returning without "
            "her. Whether that matters is the caller's call.", 68)
        return None
    return find_scribe()

def find_blank_runes():
    """Every 'Blank Rune' already sitting in the backpack -- e.g. left over from an earlier batch
    that got interrupted after crafting blanks but before enhancing all of them (a mismatch/
    safety-stop, a broken chisel that couldn't be recovered, etc.)."""
    # bare_item_name() (2026-09-16) -- blanks stack too, and "2 Blank Rune" failed the old exact
    # test exactly like the finished runes did. Use count_blank_rune_amount() for a quantity.
    return [it for it in container_items(Player.Backpack)
            if bare_item_name(it).lower() == "blank rune"]

def craft_n_runes(property_def, count, should_pause=None, allow_travel=True):
    """Full craft sequence for up to `count` runes of property_def: travel to the Scribe only if
    needed, ensure a chisel, ensure enough Rough Stone + reagent, open the Inscription Menu, and
    craft (fewer than `count` if materials run out or the safety check halts it partway). Shared
    by both the manual crafting flow and the automated pre-flight/top-up crafting in phase 2.

    Reuses any Blank Rune(s) ALREADY in the backpack first -- per the user, a prior run may have
    left some behind (crafted but never enhanced), and re-crafting new ones from scratch would
    waste Rough Stone on blanks we already have. Only the shortfall (count minus what's already
    on hand) gets newly crafted; everything on hand, existing plus new, gets enhanced up to
    `count`. Returns the number of FINISHED (enhanced) runes actually completed."""
    if count <= 0:
        return 0

    # RETRY-ON-FAIL (2026-08-27) applied throughout this function -- see RUNECRAFTING_FAIL_RETRY_
    # ATTEMPTS' own comment. None of these individual steps are one of the 3 explicit exclusions
    # (Inscription skill, out of Perk Deed, an unexpected-rune SAFETY STOP), so each gets a bounded
    # retry via retry_until_truthy() before this function finally gives up.
    # TRAVEL ONLY TO RESTOCK (2026-09-15), per the user: "Let's only travel to scribe if we're
    # below the threshold. No reason to craft there otherwise. We can craft anywhere."
    #
    # This used to travel unconditionally and go FATAL if it could not. That made sense only
    # while the Scribe was the sole source of a chisel. She is not: ensure_rune_chisel() goes
    # pack -> carried Runecrafting Storage -> Scribe, and the stones and reagents are consumed
    # from carried keys as well. So unless we are actually buying, there is nothing at the
    # Scribe and the trip is pure cost -- the recurring trip Docs/TODO.md identified as what
    # blocks crafting during combat and what makes this script unusable for anyone without the
    # Scribe rune.
    #
    # THE SAME THRESHOLD AS EVERYTHING ELSE: chisel_charge_target(), which the restock loop
    # honours and the setup field edits, so "below the threshold" cannot mean three things.
    #
    # AN UNREADABLE BALANCE MEANS DO NOT TRAVEL. A failed gump read is not evidence that we
    # need to shop, and the craft below still fails loudly and specifically if there turns out
    # to be no chisel anywhere.
    scribe = None
    # STORED **PLUS CARRIED** (2026-09-16). This read the stored row alone, and
    # withdraw_chisel_from_storage() had already emptied that row into a chisel in our own pack
    # nine seconds earlier -- so it travelled to the Scribe holding 55,641 charges. See
    # available_chisel_charges().
    # allow_travel=False (passive crafting, 2026-09-22): never leave where the Tamer put us. Restocking the
    # chisel at the Scribe stays the interactive run's job; here we use whatever is in the pack or the storage.
    # And no charge read either: available_chisel_charges() opens the shared storage gump for a full two-page
    # read (measured 10:20:08: two scans, ~2 s of gump time per 5-rune batch), on a gump the Tamer's skull
    # cycle also uses. Passive asks only whether a chisel is in the pack; ensure_rune_chisel() withdraws one
    # from the storage when it is not.
    _stored_charges = available_chisel_charges() if allow_travel else None
    if allow_travel and _stored_charges is not None and _stored_charges < chisel_charge_target():
        log("Rune Chisel charges {} (stored + carried) are below the {} target -- going to the "
            "Scribe to restock.".format(_stored_charges, chisel_charge_target()))
        scribe = retry_until_truthy(travel_to_scribe_if_needed, "travel to the Scribe")
        if not scribe:
            # NOT FATAL ANY MORE. Travel was fatal because it was the only way to get a
            # chisel; it is not. ensure_rune_chisel() takes scribe=None and simply skips the
            # vendor step, so a runebook hiccup no longer kills a batch that has charges in
            # the key or a usable chisel already in the pack.
            log("Could not reach the Scribe -- carrying on with whatever chisel we have.", 33)
    chisel = retry_until_truthy(lambda: ensure_rune_chisel(scribe), "obtain a Rune Chisel")
    if chisel:
        # THE MOMENT IT ARRIVES (2026-09-23 23:47): a hook that ran only before/after the batch missed a chisel
        # withdrawn HERE for the whole batch.
        call_hook("chisel_arrived", chisel)
    if not chisel:
        log("FATAL: could not obtain a Rune Chisel after {} attempts -- stopping.".format(
            RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
        return 0

    # INPUT PLANNING (2026-09-11) -- REPLACES the old blank-rune planner. Since the 2026-09-08
    # shard patch there is no intermediate Blank Rune to manufacture: a rune is crafted from one
    # Rough Stone directly, and a legacy Blank Rune is simply an alternative input. So the only
    # question left is how many runes we can make, which is blanks + stones -- blanks counted first
    # because the shard itself states "stored Blank Runes are used before stored Rough Stones".
    #
    # RETRIES FOR THE SAME REASON THE OLD PLANNER DID (2026-08-27): both counts are re-queried
    # fresh on each attempt rather than re-checking a stale value, so a concurrent process topping
    # up Rough Stone (a Resource Order elsewhere) mid-retry actually has a chance to help.
    existing_blanks = 0
    rough_stone = 0
    for attempt in range(RUNECRAFTING_FAIL_RETRY_ATTEMPTS):
        # THE KEY IS WHERE THESE LIVE (2026-09-15), per the user: "you're scanning for rough
        # stone or blank rune in the inventory but you should be scanning for them in the
        # [Runecrafting Storage]" and "they don't need withdrawn." The craft consumes both
        # straight from the carried key, the same arrangement reagents already use
        # (REAGENTS_CONSUMED_FROM_KEY) -- so a backpack-only count reads a full storage as
        # empty and refuses to start. Live, 22:56: the chisel came out of storage fine and
        # then "FATAL: no Blank Runes and no Rough Stone on hand after 3 attempts".
        #
        # ADDED TO THE PACK COUNT, NOT REPLACING IT. find_blank_runes()' own docstring: blanks
        # can be "left over from an earlier batch that got interrupted after crafting blanks
        # but before enhancing all of them". Those are real inputs; dropping them would trade
        # one under-count for another.
        #
        # NOTHING IS WITHDRAWN. One read, no clicks -- see storage_balances().
        # RE-CHECK RIGHT BEFORE THE FIRST ITEM ACTION (2026-09-24 13:0x). The passive loop asked the ladder at the
        # top of its tick, then this function spent up to two seconds getting here; the Tamer's skull claim landed
        # in that gap and this storage read collided with the delivery (5 of today's 7 throttles). Wait it out --
        # a skull delivery holds the ladder for a few seconds -- rather than return 0, which the caller reads as a
        # failed batch and parks on for 30 s.
        if should_pause is not None and attempt == 0:
            _waited = 0
            while should_pause():
                if _waited == 0:
                    log("Holding before the batch -- the caller asked to wait (a higher-priority item action).")
                safe_pause(YIELD_PAUSE_MS)
                _waited += YIELD_PAUSE_MS
        _stored = storage_balances(RUNECRAFTING_STORAGE_NAME) or {}
        _stored_blanks = _stored.get(BLANK_RUNE_LINE_TEXT, 0)
        _stored_stone = _stored.get(ROUGH_STONE_NAME, 0)
        existing_blanks = count_blank_rune_amount() + _stored_blanks
        rough_stone = count_material(ROUGH_STONE_NAME) + _stored_stone
        if existing_blanks + rough_stone > 0:
            break
        log("No Blank Runes and no Rough Stone in the pack OR in {} -- retrying ({}/{})..."
            .format(RUNECRAFTING_STORAGE_NAME, attempt + 1,
                    RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
        safe_pause(RUNECRAFTING_FAIL_RETRY_PAUSE_MS)

    runes_planned = min(count, existing_blanks + rough_stone)
    if runes_planned <= 0:
        log("FATAL: no Blank Runes and no Rough Stone after {} attempts -- neither in the "
            "backpack nor in {}. Top up the key's Rough Stone and run Apply again."
            .format(RUNECRAFTING_FAIL_RETRY_ATTEMPTS, RUNECRAFTING_STORAGE_NAME), 33)
        return 0
    log("Crafting {} rune(s) from {} Blank Rune(s) + {} Rough Stone(s) -- pack and {} "
        "combined.".format(runes_planned, existing_blanks, rough_stone,
                           RUNECRAFTING_STORAGE_NAME))
    # One craft still consumes one reagent set -- that half of the recipe did not change on
    # 2026-09-08, only the Rough-Stone-instead-of-Blank-Rune half did. What DID change (2026-09-11)
    # is where the reagents come from: the carried Reagent Keys, directly, with no withdrawal. See
    # REAGENTS_CONSUMED_FROM_KEY.
    #
    # NOT FATAL ANY MORE even when it does run. The craft itself is the real test -- it fails
    # loudly and per-rune if a reagent is genuinely missing, whereas this gate stopped the whole
    # batch up front on a count it had to guess from catalog data that is absent for 18 runes.
    if REAGENTS_CONSUMED_FROM_KEY:
        log("Reagents come straight from the carried Reagent Keys -- no withdrawal needed.")
    elif property_def.get("reagent_amount") is None:
        log("No reagent data for '{}' -- skipping the withdrawal and letting the craft itself "
            "report any shortage.".format(property_def["label"]), 33)
    else:
        reagent_ok = retry_until_truthy(
            lambda: ensure_reagent(property_def, property_def["reagent_amount"] * runes_planned),
            "ensure '{}'".format(property_def["reagent_storage_row"]))
        if not reagent_ok:
            log("Warning: could not confirm enough '{}' for {} craft(s) -- attempting the craft "
                "anyway; it will report a real shortage itself.".format(
                    property_def["reagent_storage_row"], runes_planned), 33)

    # AND BEFORE THE MENU OPEN (2026-09-24 13:47): the storage read passed its check a moment before the Tamer's
    # skull claim went up, then the batch went straight on to open the Inscription Menu while the delivery's
    # retry was in flight -- the retry hit the same wall. Every item action in the preamble re-asks the ladder.
    if should_pause is not None:
        _waited = 0
        while should_pause():
            if _waited == 0:
                log("Holding before the menu -- the caller asked to wait (a higher-priority item action).")
            safe_pause(YIELD_PAUSE_MS)
            _waited += YIELD_PAUSE_MS
    gid = retry_until_truthy(open_inscription_menu, "open the Inscription Menu")
    if gid is None:
        log("FATAL: could not open the Inscription Menu after {} attempts -- stopping.".format(
            RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
        return 0

    # PHASE 1 IS GONE (2026-09-11). It used to switch to the Miscellaneous category, resolve a
    # button by the text "blank rune", and craft the shortfall of intermediate Blank Runes. The
    # 2026-09-08 shard patch removed that recipe from the chisel entirely -- "The separate Blank
    # Rune step is gone. The Blank Rune recipe has been removed from the Rune Chisel" -- so that
    # whole phase could only ever fail to resolve its button and abort the run before crafting
    # anything. Enhancement now consumes a Rough Stone (or a legacy Blank Rune) directly.
    #
    # MISCELLANEOUS_CATEGORY_BUTTON and BLANK_RUNE_LINE_TEXT/BLANK_RUNE_EXPECTED_PREFIX are left
    # defined but unused here: find_blank_runes() still counts legacy blanks as a valid input, and
    # recover_broken_chisel() takes a category/line pair that other callers still supply.
    inputs_available = runes_planned
    if inputs_available == 0:
        log("FATAL: nothing to craft from -- stopping.", 33)
        return 0

    # Phase 2: apply property_def to whatever blanks are on hand (existing + newly crafted),
    # capped at `count` -- staying in Enhancement the whole time. If this phase stops partway,
    # any un-enhanced Blank Rune(s) are left sitting in the backpack, not lost -- usable, and
    # now automatically reused, in a later batch.
    blanks_to_enhance = min(inputs_available, count)
    gid = switch_inscription_category_with_retry(gid, ENHANCEMENT_CATEGORY_BUTTON)
    if gid is None:
        return 0
    prop_button = None
    for attempt in range(RUNECRAFTING_FAIL_RETRY_ATTEMPTS):
        lines2, layout2, _buttons2 = read_gump(gid)
        _idx2, prop_button = find_button_for_line(lines2, layout2, property_def["line_text"])
        if prop_button is not None:
            break
        log("Could not resolve '{}''s button -- retrying ({}/{})...".format(
            property_def["label"], attempt + 1, RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
        safe_pause(RUNECRAFTING_FAIL_RETRY_PAUSE_MS)
        # RE-OPEN, DO NOT RE-READ (2026-09-23 23:51): the Tamer's skull prefetch opened the Master Keys and storage
        # gumps in the same second this menu opened, and the menu no longer showed the Enhancement page -- three
        # re-reads of the same gump id two seconds apart could never find the line. reopen_inscription_menu_for()
        # is the existing broken-chisel recovery: open fresh, switch the category, resolve the line.
        _gid2, _btn2 = reopen_inscription_menu_for(ENHANCEMENT_CATEGORY_BUTTON, property_def["line_text"])
        if _gid2 is not None:
            gid = _gid2
        if _btn2 is not None:
            prop_button = _btn2
            break
    if prop_button is None:
        log("FATAL: could not resolve '{}''s button after {} attempts -- stopping ({} "
            "input(s) on hand, still unused).".format(
                property_def["label"], RUNECRAFTING_FAIL_RETRY_ATTEMPTS, inputs_available), 33)
        return 0

    log("Applying '{}' to {} Blank Rune(s)...".format(property_def["label"], blanks_to_enhance))
    completed = 0
    _rune_stones = 1                 # THE PACK'S OWN WEIGHT: one rune's weight, the largest step a craft has measured
    for item_number in range(1, blanks_to_enhance + 1):
        _room = weight_room()
        if _room is not None and _room < _rune_stones:
            log("STOPPING after {} of {} -- {}.".format(
                completed, blanks_to_enhance, weight_stop_line("the next rune")), 33)
            break
        # should_pause (passive crafting, 2026-09-22): the caller's "something stronger wants the item timer"
        # test, asked BETWEEN runes so a batch yields within one craft (~1.4 s) instead of holding for all of it.
        # Returns what was finished; the caller keeps the remainder queued.
        if should_pause is not None and item_number > 1 and should_pause():
            log("Pausing after {} of {} -- the caller asked to wait (a higher-priority item action).".format(
                completed, blanks_to_enhance))
            break
        if should_pause is not None and item_number == 1:
            _waited = 0
            while should_pause():          # the first craft waits instead of breaking (2026-09-24)
                if _waited == 0:
                    log("Holding before the first craft -- the caller asked to wait (a higher-priority item action).")
                safe_pause(YIELD_PAUSE_MS)
                _waited += YIELD_PAUSE_MS
        ok = False
        final_item = None
        for attempt in range(RUNECRAFTING_FAIL_RETRY_ATTEMPTS):
            _craft_started = time.time()
            try:
                _weight_before = int(Player.Weight)
            except Exception:
                _weight_before = None
            call_hook("item_action")         # start (2026-09-24): a script beside us waits for it
            ok, final_item = craft_and_verify(gid, prop_button, property_def["syllable"],
                                               "apply {}".format(property_def["label"]))
            call_hook("item_action")         # end: and settles after we finished
            _craft_ms = int((time.time() - _craft_started) * 1000)
            if ok:
                try:
                    if _weight_before is not None:
                        _rune_stones = max(_rune_stones, int(Player.Weight) - _weight_before)
                except Exception:
                    pass
                break
            if final_item is not None:
                # Name-mismatch SAFETY STOP -- the one exclusion, stays a full stop, never retried.
                break
            # THE MENU CAN GO AWAY MID-BATCH (2026-09-16). gid was resolved once, before the first
            # of these 66 crafts. Nothing produced and nothing said by the shard means the click
            # never landed, and a gump that has closed is the way that happens -- so re-open and
            # re-resolve rather than sending the same button at the same dead id three times,
            # which is exactly what stopped the batch at 36 of 66.
            try:
                _menu_open = bool(Gumps.HasGump(gid))
            except Exception:
                _menu_open = True
            if not _menu_open:
                log("The Inscription Menu closed mid-batch after {} rune(s) -- reopening and "
                    "resuming.".format(completed), 33)
                gid, prop_button = reopen_inscription_menu_for(
                    ENHANCEMENT_CATEGORY_BUTTON, property_def["line_text"])
                if prop_button is None:
                    break
                continue
            log("'{}' craft (item {}) didn't produce a new item -- retrying ({}/{})...".format(
                property_def["label"], item_number, attempt + 1, RUNECRAFTING_FAIL_RETRY_ATTEMPTS), 33)
            safe_pause(RUNECRAFTING_FAIL_RETRY_PAUSE_MS)
        if ok and final_item is not None:
            call_hook("rune_crafted", final_item, property_def)
        if not ok:
            # MEASURED, NOT SUBTRACTED (2026-09-16), per the user: "let's also fix that wrong
            # message". This printed `blanks_to_enhance - completed` -- 66 - 36 = 30 -- which is
            # arithmetic wearing the clothes of a measurement: it reads 30 whether the pack holds
            # thirty blanks, none, or a thousand. It cost a wrong inference the night it mattered,
            # being read as evidence the supply was fine. count_blank_rune_amount() is a real read
            # and counts stacks properly.
            log("STOPPING after {} of {} -- the craft of item {} did not come; the shard said: {} "
                "({} unenhanced Blank Rune(s) actually in the backpack; {} of the batch "
                "unstarted).".format(completed, blanks_to_enhance, item_number,
                                     CRAFT_FAIL_SAID[0] or "nothing",
                                     count_blank_rune_amount(),
                                     blanks_to_enhance - completed), 33)
            break
        completed += 1
        # ONE LINE PER RUNE (2026-09-16), per the user: "just the ##/###: In Rune [1200ms] is
        # fine." bare_item_name() drops the stack count -- final_item.Name on a pile reads "165 In
        # Rune", a second running total alongside the "143/171" that already says where we are.
        # The ms is the caller's own clock, so it covers the gump send AND the verify poll: the
        # real per-rune cost, which is what made the old 2000ms-every-craft stall visible.
        log("Crafted {}/{}: {} ({}ms)".format(
            completed, blanks_to_enhance,
            bare_item_name(final_item) if final_item is not None else "(rune filed into storage before it was seen)",
            _craft_ms))

        if not chisel_still_present(chisel):
            chisel, gid, prop_button = recover_broken_chisel(
                scribe, ENHANCEMENT_CATEGORY_BUTTON, property_def["line_text"])
            if chisel:
                call_hook("chisel_arrived", chisel)   # a replacement chisel, as it arrives (2026-09-23)
            if prop_button is None:
                break
    else:
        log("Done: crafted all {} requested '{}' rune(s).".format(completed, property_def["label"]))
    return completed

BACKPACK_PROPS_WAIT_MS = 1000  # Ceiling on the tooltip refresh in backpack_item_usage(), NOT a
                               # sleep -- the same 1000 every other Items.WaitForProps() call in
                               # this file already uses.


def backpack_item_usage():
    """(items, maxItems) parsed from the backpack's own "Contents" tooltip line -- same proven
    approach already used by Omni_Engine.py's combat_pack_item_count()/Harvest.py's
    pack_usage(), duplicated here (not imported) since this is a standalone script. RE doesn't
    expose a max-item-capacity property directly (confirmed live -- dir(Player.Backpack) has
    nothing usable), so this tooltip-text parse is the only real source. Returns None if the
    tooltip didn't parse (all 4 numbers -- items, maxItems, weight, maxWeight -- must be present
    before trusting it).

    REFRESHED FIRST SINCE 2026-09-16. This parsed the CACHED tooltip -- no WaitForProps -- while
    every other property read in this file waits for one (read_property_value(),
    has_relic_property(), carried_chisel_charges(), find_perk_deed()). The backpack was the one
    exception and it is the object whose tooltip changes most, since every item in or out rewrites
    the "Contents" line.

    The damage was worst in restock_chisel_charges(), which reads this immediately after
    absorb_backpack_into_key() has moved a pack-load of chisels OUT: a stale pre-absorb count made
    headroom read near zero and the restock stop with "pack headroom 0" seconds after emptying the
    pack. It also capped every craft batch via craftable_now(), which is why a batch could be
    sized 171 and then 162 while the backpack actually had MORE room -- per the user: "9 more
    slots weren't occupied. i actually had more room in my inventory."

    Same omission still lives in Omni_Engine.py's combat_pack_item_count() and
    Harvest.py's pack_usage(), the two this function claims parity with."""
    try:
        # INSIDE THE try ON PURPOSE: a refresh that raises must leave the old behaviour, not break
        # the caller. An unparseable tooltip still returns None below, which bulk_craft_headroom()
        # reads as "no room" -- the safe direction, unchanged.
        Items.WaitForProps(Player.Backpack, BACKPACK_PROPS_WAIT_MS)
        props = Items.GetPropStringList(Player.Backpack)
    except Exception:
        props = []
    for prop in props or []:
        if "Contents" in prop:
            nums = [int(x) for x in re.findall(r"\d+", prop)]
            if len(nums) >= 4:
                return (nums[0], nums[1])
    return None

def bulk_craft_headroom():
    """How many more items the backpack can hold before hitting MAX_INVENTORY_FRACTION of its
    max item-slot capacity. Treats an unparseable reading as "no room" (0), not "unlimited" --
    safer to under-craft and need one more top-up than to risk overflowing a full backpack."""
    usage = backpack_item_usage()
    if not usage:
        return 0
    items, max_items = usage
    cap = int(max_items * MAX_INVENTORY_FRACTION)
    return max(0, cap - items)

# THE PACK'S OWN WEIGHT (owner, 2026-10-17: "We can just check for it, and otherwise work within the confines of the
# weight limit."). With Infinite Backpack Weight active (the last Active Perks read) no limit applies here. Without it,
# or on a read that failed, every rune crafted and every item pulled out of a chest is fitted to what the pack can still
# carry -- the client's own weight and limit, read at the moment. A craft past the limit would land at our feet.
def weight_limit_applies():
    """True unless the last Active Perks read showed Infinite Backpack Weight still running."""
    refresh_gate_cache()
    expiration = _gate_cache.get("ibw_expiration")
    return expiration is None or expiration <= datetime.datetime.utcnow()


def weight_room():
    """Stones the pack can still take, or None when no weight limit applies -- see THE PACK'S OWN WEIGHT."""
    if not weight_limit_applies():
        return None
    try:
        return int(Player.MaxWeight) - int(Player.Weight)
    except Exception:
        return 0                     # unreadable: the safe direction, as bulk_craft_headroom() reads it


def weight_stop_line(what):
    """The line a stop at the weight limit says, with the pack's own numbers."""
    try:
        carried = "{} of its {} stones".format(int(Player.Weight), int(Player.MaxWeight))
    except Exception:
        carried = "an unreadable weight"
    return "the pack carries {}, and {} would go over -- Infinite Backpack Weight is not active".format(carried, what)


def craftable_now(runes_needed):
    """How many runes could actually be produced right now toward runes_needed, accounting for
    Blank Rune(s) ALREADY in the backpack. Per the user: enhancing an existing blank needs ZERO
    additional backpack space -- it gets consumed and the finished rune takes its place, a
    net-zero item-count change -- unlike crafting a brand-new blank from scratch (net +1 item,
    genuinely headroom-constrained). So a full backpack (bulk_craft_headroom() == 0) should NOT
    by itself mean "nothing more can be made" -- existing blanks can still become finished runes.

    A NEW BLANK ALSO NEEDS A ROUGH STONE (2026-09-16). This bounded new runes by `headroom`
    ALONE, and headroom is how many items the backpack can hold -- it says nothing about whether
    anything can be made. With 0 blanks and 159 free slots it authorised 159 runes against ~31
    Rough Stone in storage; craft_n_runes() then honestly planned 31, crafted all 31, and the
    caller read 31-of-159 as "something interrupted the batch". Space and material are separate
    limits and a new rune needs both, so the new-rune term is min(headroom, stone).

    Stone is counted wherever it lives -- see available_rough_stone(); the storage key feeds the
    craft directly, so backpack-only would under-count exactly as badly as headroom over-counted.

    Returns (craftable, existing_blanks, headroom) -- shape unchanged, and `headroom` still means
    headroom. It simply no longer stands in for supply."""
    existing_blanks = count_blank_rune_amount()
    headroom = bulk_craft_headroom()
    stone = available_rough_stone()
    # SLOTS ARE NOT A PER-RUNE COST (2026-09-16), per the user: "they stack, so it shouldn't do
    # that." This was min(headroom, stone), which made the free SLOT count the limit -- 2142 runes
    # wanted, thousands of stone banked, and it crafted 150 because 150 slots were free.
    #
    # Since runes stack, a new blank joins the Blank Rune stack and a finished rune joins the In
    # Rune stack, so N runes occupy ONE slot. Headroom only answers whether the FIRST stack can be
    # created: with blanks already in hand every further one joins them and slots stop mattering;
    # with none, a single free slot is needed to start. Material is the real bound.
    if existing_blanks > 0 or headroom > 0:
        new_runes_possible = stone
    else:
        new_runes_possible = 0   # pack full AND no blank stack to grow -- nothing can be made
    return (min(runes_needed, existing_blanks + new_runes_possible),
            existing_blanks, headroom)

def run_crafting_flow():
    property_def, quantity = ask_what_to_craft()
    if property_def is None:
        log("No valid request received -- stopping.", 33)
        return False
    return craft_n_runes(property_def, quantity) >= quantity   # True = a FINISHED craft (2026-09-24)


# =============================================================================
# APPLICATION FLOW (PHASE 2)
# =============================================================================

def estimate_applications_needed(eligible_items, property_def, target_stat):
    """Pre-flight estimate: (expected_successful_applications, expected_runes_needed) to bring
    every eligible item's CURRENT value up to target_stat. Model: each item needs
    max(0, target_stat - current_value) worth of gain; round-robin ordering doesn't change how
    much total gain each item needs, only the order applications happen in, so total successes
    needed = sum of those gaps / the property's average per-application gain (gain_range's
    midpoint). Expected total attempts (including expected failures at
    BREAK_CHANCE_PER_APPLICATION) = successes_needed / (1 - BREAK_CHANCE_PER_APPLICATION).
    Deliberately NOT padded with an extra safety margin on top of that -- relies on
    run_slot_application()'s own interleaved top-up (craft_more_runes_if_needed()) to cover any
    shortfall from this being an approximation (see project memory: lockstep approximation,
    unconfirmed gain distribution shape, break-chance formula not empirically validated).
    Returns (0, 0) if property_def has no confirmed gain_range, or nothing is needed."""
    # BREAKS ARE PLANNED FOR (2026-09-19), per the user: "Some of them are expected to break. We shouldn't
    # plan for them to all survive." The closed form below assumed every item survives to target (at ~111
    # applications per shirt that is an 11% chance each) and crafted 1,342 runes for a run that needs a
    # fraction of that. simulate_stat_completion() is the preview's own shrinking-pool model (2026-08-27):
    # an item that breaks stops consuming runes. Returns (successful applications, attempts = runes needed,
    # expected items reached, expected items broken); the old 2-tuple is the first two entries.
    gain_range = property_def.get("gain_range")
    if gain_range is None:
        return 0, 0, 0.0, 0.0
    values = snapshot_property_values(eligible_items, property_def)
    if not values or not any(target_stat - v > 0 for v in values):
        return 0, 0, float(len(values)), 0.0
    attempts, reached, broken = simulate_stat_completion(values, target_stat, gain_range)
    return (int(math.ceil(max(0.0, attempts - broken))), int(math.ceil(attempts)), reached, broken)

def craft_block_reason(existing_blanks, headroom, stone):
    """Why craftable_now() could produce nothing -- the constraint that ACTUALLY binds.

    ADDED 2026-09-16 for the user's pass over the failure messages: "make sure they are relevant
    to what is actually tripping them now." Two sites blamed the backpack capacity ceiling, which
    stopped being the usual cause when runes began stacking (2026-09-08): craftable_now() now
    reads `stone if (blanks > 0 or headroom > 0) else 0`, so with a blank stack or any free slot
    the limit is MATERIAL. Running dry on Rough Stone was being reported as a full backpack --
    the exact confusion the user hit live ("oh no, you're right i think we ran out of rough
    stone").

    ONLY TWO CASES ARE REACHABLE from a caller that asks when the craftable count came out 0 and
    runes were genuinely wanted, because existing_blanks > 0 would make that count at least 1:
      * no stone           -> out of material
      * stone but no room  -> the FIRST blank has nowhere to go; every one after it stacks
    The other two returns are defensive, and say plainly that the count itself was zero rather
    than inventing a constraint to blame."""
    if existing_blanks > 0:
        return ("the amount still needed worked out to zero, with {} Blank Rune(s) already on "
                "hand".format(existing_blanks))
    if stone <= 0:
        return ("there is no Rough Stone left, in the pack or in {}"
                .format(RUNECRAFTING_STORAGE_NAME))
    if headroom <= 0:
        return ("the backpack is at the {}% capacity ceiling, so the first Blank Rune has "
                "nowhere to go (once one exists the rest stack onto it)"
                .format(int(MAX_INVENTORY_FRACTION * 100)))
    return "the amount still needed worked out to zero"


def craft_more_runes_if_needed(property_def, eligible_items, target_stat):
    """Called by run_slot_application() when it runs out of crafted runes mid-batch. Re-estimates
    how many more are needed for the CURRENT state of eligible_items, then checks how many are
    actually craftable right now via craftable_now() -- existing Blank Rune(s) count toward this
    even at zero backpack headroom, per the user (enhancing an existing blank needs no additional
    space). Crafts via craft_n_runes() (which itself only travels to the Scribe if not already
    near her, and itself re-checks existing blanks to avoid re-crafting them). Returns True if at
    least one more rune was crafted."""
    runes_needed = estimate_applications_needed(eligible_items, property_def, target_stat)[1]
    if runes_needed <= 0:
        return False

    # THE MID-BATCH TOP-UP TAKES FROM STOCK TOO (2026-09-16). Same reasoning as the up-front
    # bulk-craft: this is the path that printed "Out of 'In Rune' -- estimate says 2 more needed"
    # while 101 sat in the storage. Returning True here means "supply was replenished", which a
    # withdrawal satisfies just as well as a craft.
    if withdraw_runes_from_storage(property_def, runes_needed) > 0:
        return True

    craft_now, existing_blanks, headroom = craftable_now(runes_needed)
    if craft_now <= 0:
        # NAMES THE CONSTRAINT THAT ACTUALLY BINDS (2026-09-16). This used to blame the capacity
        # ceiling unconditionally, which since runes started stacking is usually not the reason
        # -- see craft_block_reason().
        log("Can't craft more '{} Rune' -- {}.".format(
            property_def["syllable"].capitalize(),
            craft_block_reason(existing_blanks, headroom, available_rough_stone())), 33)
        return False

    # SAME CORRECTION as the bulk-craft line above: the Rough Stone is what bounds this now.
    log("Out of '{} Rune' -- estimate says {} more needed; {} Blank Rune(s) on hand, {} Rough "
        "Stone available -- crafting toward {} now.".format(
            property_def["syllable"].capitalize(), runes_needed, existing_blanks,
            available_rough_stone(), craft_now))
    completed = craft_n_runes(property_def, craft_now)
    return completed > 0

def runes_already_held(property_def):
    """(in the pack, in the storage key) for this property's finished runes.

    COUNTED, NEVER WITHDRAWN. The apply flow pulls stored runes into the
    pack because a rune has to be there to be used; this one is putting
    runes IN, so taking them out first would be a gump cycle spent to undo
    itself. cached_storage_balance() reads the row without touching it.
    """
    in_pack = count_rune_amount(property_def)
    in_store = 0
    row = stored_rune_row(property_def)
    if row is not None:
        try:
            in_store = cached_storage_balance(RUNECRAFTING_STORAGE_NAME,
                                              row) or 0
        except Exception:
            in_store = 0
    return in_pack, in_store


def prepare_and_store_one_stat(property_def, slot_def, target_stat,
                               restrict_serials=None):
    """Work out what this stat would need, craft the shortfall, store it.

    THE STORE-ONLY TWIN of prepare_and_apply_one_stat(). Same estimate, same
    craft, and then absorb_backpack_into_key() instead of the application
    loop. True when a craft was attempted.

    WHAT IT DOES NOT DO, and why each one is deliberate:

      * No application. That is the whole point of this script.
      * No Perk Deed. The perk lowers the chance of breaking an ITEM while
        applying one, and nothing is applied here, so using one would burn
        an hour of it on a craft that never needed it.
      * No withdrawal of stock it is about to add to. See
        runes_already_held().

    NO GAIN RANGE, NO ESTIMATE. prepare_and_apply_one_stat() falls through
    to applying anyway in that case, because applying is still useful
    without a number. Here the number IS the output, so there is nothing to
    fall through to and it says so rather than crafting an arbitrary pile.
    """
    if property_def.get("gain_range") is None:
        log("No live-confirmed gain range for '{}', so there is no way to "
            "work out how many runes the gear would need -- and a count is "
            "the only thing this script produces. Skipping it."
            .format(property_def["label"]), 33)
        return False

    eligible = find_slot_items(slot_def, restrict_serials=restrict_serials)
    _est = estimate_applications_needed(eligible, property_def, target_stat)
    runes_needed, expected_reached, expected_broken = _est[1], _est[2], _est[3]

    if runes_needed <= 0:
        log("'{}' needs no runes for {} {} -- nothing to stock."
            .format(slot_def["label"], target_stat, property_def["label"]))
        return False

    in_pack, in_store = runes_already_held(property_def)
    have = in_pack + in_store
    to_craft = max(0, runes_needed - have)

    log("Stocking for an ASSUMED {} '{}' item(s) at {} {} -- none of them "
        "has to be in your pack. The simulation says ~{} rune(s), counting "
        "the ~{:.1f} expected to break on the way. You already hold {} ({} "
        "in the pack, {} in the key)."
        .format(ASSUMED_ITEM_COUNT, slot_def["label"], target_stat,
                property_def["label"], runes_needed, expected_broken,
                have, in_pack, in_store))

    if to_craft <= 0:
        log("Already stocked for this one -- crafting nothing.")
        # STILL PUT THE PACK AWAY. Runes counted in the pack belong in the
        # key, or the next run counts them again and the pack never clears.
        if in_pack > 0:
            absorb_backpack_into_key(RUNECRAFTING_STORAGE_NAME)
        return False

    made = craft_n_runes(property_def, to_craft)
    log("Crafted {} of the {} '{}' rune(s) wanted."
        .format(made, to_craft, property_def["label"]))
    if made <= 0:
        log("Nothing was crafted -- see the lines above for what stopped "
            "it (materials, a chisel, or the safety check).", 33)
        return True

    # STORED IMMEDIATELY, per stat rather than once at the end. A run that
    # stops partway - out of stone, a broken chisel - has still banked
    # everything it finished, and the next run counts it as stock.
    if absorb_backpack_into_key(RUNECRAFTING_STORAGE_NAME):
        log("Put away into '{}'.".format(RUNECRAFTING_STORAGE_NAME))
    else:
        log("Crafted them, but could not fill '{}' -- they are in the pack."
            .format(RUNECRAFTING_STORAGE_NAME), 33)
    return True


def prepare_and_apply_one_stat(property_def, slot_def, target_stat, restrict_serials=None):
    """The pre-flight-estimate + bulk-craft + apply sequence for ONE requested (property_def,
    target_stat) pair -- extracted (2026-08-27) from the old single-stat run_application_flow()
    so a multi-stat request (see ask_apply_requests_and_slot()) can run this once per requested stat.
    restrict_serials (2026-08-27), if given -- see select_apply_bases() -- confines the WHOLE
    sequence (pre-flight estimate, bulk-craft sizing, and the actual application loop) to that
    small hand-picked subset instead of every eligible item of slot_def's type.
    Returns True if application was attempted (regardless of how far it got -- run_slot_
    application() logs its own stop reason), False if this stat's craft was skipped entirely
    (nothing to craft, or the bulk-craft was interrupted and it isn't safe to apply an incomplete
    supply -- see the CONFIRMED-live incident this guard was built from, below).

    CONFIRMED live (real run) this needs to verify EACH step actually succeeded before spending
    the next one: an interrupted bulk-craft (chisel broke, only 14 of a much larger planned batch
    completed) was followed by using a real Perk Deed anyway, wasting its 1-hour window on a
    supply far short of what was planned. The craft hand-off below checks craft_n_runes()'s own
    completed count against what was requested rather than assuming it worked."""
    if property_def.get("gain_range") is None:
        log("No live-confirmed gain range for '{}' yet -- can't pre-flight estimate, skipping "
            "straight to application (it will still refuse to run without a prop_pattern).".format(
                property_def["label"]), 33)
        run_slot_application(property_def, slot_def, target_stat, restrict_serials=restrict_serials)
        return True

    eligible = find_slot_items(slot_def, restrict_serials=restrict_serials)
    _est = estimate_applications_needed(eligible, property_def, target_stat)
    applications_needed, runes_needed, expected_reached, expected_broken = _est[0], _est[1], _est[2], _est[3]
    if runes_needed > 0:
        est_minutes = (runes_needed / float(ESTIMATED_APPLICATIONS_PER_HOUR)) * 60.0
        log("Pre-flight estimate ({}-trial simulation, ~{}% break per application): ~{} attempt(s) = ~{} "
            "rune(s) -- of the {} eligible '{}' item(s), ~{:.1f} expected to reach {} {} and ~{:.1f} expected "
            "to break first -- roughly {:.0f} minutes at this project's own throughput estimate.".format(
                PREVIEW_COMPLETION_TRIALS, int(BREAK_CHANCE_PER_APPLICATION * 100), runes_needed,
                runes_needed, len(eligible), slot_def["label"], expected_reached, target_stat,
                property_def["label"], expected_broken, est_minutes))

        existing = count_rune_amount(property_def)
        still_needed = max(0, runes_needed - existing)
        # WHAT WE ALREADY OWN, BEFORE CRAFTING ANY (2026-09-16), per the user: "we have all the
        # luck runes we needed to do that craft, so ... it should have never tried to craft more
        # luck runes." The storage held 101 In-Luck and this read "have 0 finished", because
        # count_runes() only ever saw the backpack. Withdrawing rather than merely counting,
        # because a rune has to be in the pack to be applied.
        if still_needed > 0 and withdraw_runes_from_storage(property_def, still_needed) > 0:
            existing = count_rune_amount(property_def)
            still_needed = max(0, runes_needed - existing)
        craft_now, existing_blanks, headroom = craftable_now(still_needed)
        if craft_now > 0:
            # REPORTS THE STONE, NOT THE SLOTS (2026-09-16). Headroom used to BE the cap so
            # printing it explained the number; it no longer governs anything here, and printing
            # it beside a crafting decision would point at the wrong limit.
            log("Bulk-crafting {} '{}' rune(s) up front (have {} finished, want {}; {} Blank "
                "Rune(s) on hand, {} Rough Stone available).".format(
                    craft_now, property_def["label"], existing, runes_needed, existing_blanks,
                    available_rough_stone()))
            crafted = craft_n_runes(property_def, craft_now)
            if crafted < craft_now:
                # STILL DOES NOT INFER A CAUSE -- AND "a real shortfall" WAS ALSO AN INFERENCE.
                # History, so neither wording is restored as a fix: this began as "something
                # interrupted the batch" (asserted, and it fired under "Done: crafted all 31
                # requested" because craftable_now() had authorised 159 runes on headroom with
                # ~31 stone). Fixing that bound led to the note that reaching here "now means a
                # real shortfall", and to a message telling the player to top up.
                #
                # THE 04:56 RUN ON 2026-09-16 DISPROVED THAT: crafted 1008 of 1133 with 1425
                # Rough Stone still in storage, stopped by the safety check on item 1009, and a
                # plain re-run finished the remaining 124 with no topping up at all. The trigger
                # is only "the craft loop stopped early" -- a safety stop, a chisel it could not
                # get, the Inscription menu closing, an unresolvable button, a world save.
                #
                # So: state the shortfall and the figures, point at the reason craft_n_runes()
                # already printed, and prescribe nothing this branch cannot establish.
                log("STOPPING '{}': crafted {} of the {} rune(s) planned, so the supply is "
                    "incomplete and nothing will be applied -- see the message above for what "
                    "stopped it. On hand now: {} Blank Rune(s), {} Rough Stone (pack + storage). "
                    "Run Apply again for this stat once that is sorted."
                    .format(property_def["label"], crafted, craft_now,
                            count_blank_rune_amount(), available_rough_stone()), 33)
                return False
        elif still_needed > 0:
            # SAME CORRECTION as the mid-batch line: the old wording asserted "no backpack
            # headroom", which is only one of the two ways this is reached and no longer the
            # likely one.
            log("Can't craft more '{}' up front -- {}. Starting with the {} finished on hand."
                .format(property_def["label"],
                        craft_block_reason(existing_blanks, headroom, available_rough_stone()),
                        existing), 33)
    else:
        log("Pre-flight estimate: every eligible '{}' item is already at or above {} {} -- "
            "nothing to craft up front.".format(slot_def["label"], target_stat, property_def["label"]))

    run_slot_application(property_def, slot_def, target_stat, restrict_serials=restrict_serials)
    return True

PREVIEW_PROGRESS_GUMP_ID = 0x52554E43   # "RUNC" -- Calculating. Same ASCII-tag convention as
                                    # RUNP/RUNQ/RUNG/RUNM/RUNS, and distinct from all of them so
                                    # closing this one cannot close a screen the player is using.
PREVIEW_PROGRESS_REDRAW_MS = 350    # Ceiling on redraws, not a wait. The computation is blocking,
                                    # so updates can only land between passes anyway; this stops a
                                    # fast pool sending a gump per pass.
PREVIEW_PROGRESS_BAR_CELLS = 20     # Width of the text bar, in characters.

_preview_progress = None            # None = OFF. A dict while a preview pass is running.


def _draw_preview_progress():
    """Redraw the Calculating gump from the current progress state.

    A TEXT BAR, NOT GUMP ART, on purpose: this file's own rule is that "an unverified art draws
    nothing at all, with no error", and an invisible progress bar is worse than none. Labels are
    what this file can draw with certainty."""
    p = _preview_progress
    if p is None:
        return
    total = max(1, p["total"])
    done = min(p["done"], total)
    # SUB-PASS POSITION (2026-09-17). `done` alone advances the bar in WHOLE passes, and total
    # is 3 * len(requests) + 2 -- so one requested stat is 5 passes across a 20-cell bar, i.e.
    # 4-cell jumps with nothing moving in between. Worse, estimate_apply_odds() runs 200 full
    # batch simulations inside a SINGLE pass, so on a big pool the longest stretch of the whole
    # computation drew no change at all and the screen read as hung rather than slow. That is
    # the "not a very smooth progress bar" report, and it only shows up on big crafts.
    pos = min(float(p["done"]) + max(0.0, min(1.0, p.get("sub", 0.0))), float(total))
    filled = int(PREVIEW_PROGRESS_BAR_CELLS * (pos / total))
    bar = ("#" * filled) + ("-" * (PREVIEW_PROGRESS_BAR_CELLS - filled))
    dots = "." * (1 + (p["tick"] % 3))   # the liveness cue the user asked for
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, 360, 132, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, 360, 132)
    Gumps.AddLabel(gd, 20, 14, 68, "Calculating {}{}".format(p["slot"], dots))
    Gumps.AddLabel(gd, 20, 42, 68, "[{}]  {}%".format(bar, int(100.0 * pos / total)))
    Gumps.AddLabel(gd, 20, 68, 68, "{} of {} passes -- {}".format(done, total, p["phase"]))
    Gumps.AddLabel(gd, 20, 94, 68,
                   "{} item(s) in the pool -- nothing is spent yet".format(p["items"]))
    Gumps.SendGump(PREVIEW_PROGRESS_GUMP_ID, Player.Serial, 300, 200,
                   gd.gumpDefinition, gd.gumpStrings)


def preview_progress_begin(requests, item_count, slot_label):
    """Open the Calculating screen. total is the real pass count, not an estimate: three passes
    over the pool per requested stat (rows, odds, other-entries) plus the two whole-phase steps
    (select_apply_bases, suggest_realistic_dump_target)."""
    global _preview_progress
    _preview_progress = {"done": 0, "total": 3 * max(1, len(requests)) + 2, "tick": 0,
                         "phase": "starting", "items": item_count, "slot": slot_label,
                         "last": 0.0, "sub": 0.0}
    _draw_preview_progress()


def preview_progress_step(phase):
    """One pass finished. A NO-OP when no preview is running, so the three inner loops can call
    this unconditionally and nothing changes for any other caller of them."""
    global _preview_progress
    p = _preview_progress
    if p is None:
        return
    p["done"] += 1
    p["phase"] = phase
    p["sub"] = 0.0          # a new pass starts at its own beginning
    _now = time.time()
    if (_now - p["last"]) * 1000.0 < PREVIEW_PROGRESS_REDRAW_MS:
        return                      # counted, just not redrawn yet
    p["last"] = _now
    p["tick"] += 1
    _draw_preview_progress()


def preview_progress_sub(fraction):
    """Progress WITHIN the current pass, 0.0-1.0. A NO-OP when no preview is running, so the
    simulation loops can call it unconditionally and nothing changes for any other caller.

    Same PREVIEW_PROGRESS_REDRAW_MS ceiling as preview_progress_step(), so a 200-trial loop
    calling this every trial still sends at most about three gumps a second. It also advances
    the liveness dots, which is half the point: during a long pass those used to stop moving
    too, and a frozen "Calculating..." reads as a hung script rather than a slow one."""
    global _preview_progress
    p = _preview_progress
    if p is None:
        return
    p["sub"] = fraction
    _now = time.time()
    if (_now - p["last"]) * 1000.0 < PREVIEW_PROGRESS_REDRAW_MS:
        return
    p["last"] = _now
    p["tick"] += 1
    _draw_preview_progress()


def preview_progress_end():
    """Close the Calculating screen and disarm. Called from a finally, so an exception during the
    computation cannot leave it on screen."""
    global _preview_progress
    _preview_progress = None
    try:
        Gumps.CloseGump(PREVIEW_PROGRESS_GUMP_ID)
    except Exception:
        pass                        # already gone, or the player closed it -- nothing to do


APPLY_PREVIEW_GUMP_ID = 0x52554E50  # "RUNP" -- distinct tag from this project's other custom
                                       # gumps (RUNR/RUNQ/RUNS/RUNM), same ASCII-tag convention.
APPLY_PREVIEW_ROW_HEIGHT = 22
APPLY_PREVIEW_ACCEPT_BUTTON = 1
APPLY_PREVIEW_CANCEL_BUTTON = 2
APPLY_PREVIEW_SUGGEST_BUTTON = 3

def build_apply_preview_rows(requests, slot_def, bases=None):
    """Per the user (2026-08-27): "before starting the process, show the expected item breaks,
    the expected rough stone usage, and the odds of hitting target thresholds, then the player
    would click accept from that screen to start." Runs simulate_stat_completion() once per
    requested stat in this batch to get the expected (uncapped) attempts/breaks for FULL
    completion of that stat.

    bases (2026-08-27), if given -- (property_def, restrict_serials) from select_apply_bases() --
    confines THAT ONE property's row to the restricted subset instead of the full eligible pool,
    so the preview accurately reflects what will actually run (see select_apply_bases()'s own
    docstring for why a smaller subset is often dramatically more efficient for a dump stat).

    SWITCHED (2026-08-27) from the old closed-form estimate_applications_needed() to simulate_stat_
    completion() -- per the user, live, spotting a real inconsistency: "it seems like if 75 breaks
    are expected for 600, 30 items wouldn't be enough to get 573 right? Kind of seems like we're
    using different math on those or something." Correct -- the closed form assumes an infinite/
    never-shrinking item pool and could predict more break EVENTS than there are actual items to
    break for a hard-enough target (a physical impossibility, since each item breaks at most once).
    simulate_stat_completion() reuses the SAME simulate_stat_trial() primitive estimate_apply_odds()/
    suggest_realistic_dump_target() already use, just with an UNCAPPED attempts_budget -- every
    number on this screen now comes from ONE consistent, pool-size-correct model.

    Walks the SHARED Blank Rune pool across requests in the same sequential order run_
    application_flow() will actually process them in, so the aggregate Rough Stone total doesn't
    double-count blanks a later stat's own craft would already have consumed by the time it runs.

    ROW vs TOTAL SPLIT (2026-08-27), per the user, live, TWO rounds of correction:
    1. First report: "The expected breaks for 6000 SDI (an absurd number) doesn't behave like I'd
       expect. That section should show estimates assuming infinite resource and items just to
       educate the player." First attempt simulated each row against a synthetic, at-least-100-item
       pool -- but this made EVERY row's numbers scale up with pool size, even an easy target that
       never needed that framing.
    2. Corrected immediately after, per the user: "Something went wrong with the FC line here...
       They should show the expected applications and breaks to get a single item with those
       stats... we can get rid of the rough stone mentioned at the end of the line. That's already
       info given in the applications part of the line." Each row now reports PER-ITEM numbers
       instead -- one representative item (the LOWEST current value among eligible items, matching
       whichever one run_slot_application()'s own greedy rule would actually work on first)
       simulated repeatedly via simulate_stat_completion() with a pool size of exactly 1. At pool
       size 1, that function's own `broken` return value is already a genuine per-item PROBABILITY
       (shown as a percentage), and `attempts` is the average total applications for one item's own
       journey -- since every attempt costs exactly one Rough Stone regardless of outcome, this
       number already covers Rough Stone cost too, so the row no longer shows it separately.

    `totals` (the Total line) is UNCHANGED throughout both rounds -- still strictly the real,
    current-backpack numbers (real eligible pool, feeds the actionable Rough-Stone-on-hand
    comparison), never the per-row per-item figures.

    Returns (rows, totals). "Odds of hitting every target" is NOT computed here -- this reports the
    EXPECTED (average) cost of full completion, not a hit-probability. See estimate_apply_odds()
    below for the actual Monte Carlo odds figure, computed separately."""
    full_eligible = find_slot_items(slot_def)
    restrict_property_def, restrict_serials = bases if bases is not None else (None, None)
    blanks_pool = count_blank_rune_amount()
    rows = []
    total_applications = 0
    total_breaks = 0
    total_stone = 0
    # ONE CHAINED RUN FOR EVERY ROW (2026-09-24) -- see simulate_batch_trials(): the per-stat
    # simulate_stat_completion() calls this replaced each started from the full pool, which is what put 344
    # breaks on a 94-item screen. Unlimited blanks and stone here: these rows are the cost of FULL completion,
    # the same question as before, now bounded by the real, shrinking pool across the whole request.
    _entries = []
    _eligible_by_label = {}
    _seen_labels = set()
    for property_def, target_stat in requests:
        preview_progress_step("rows: {}".format(property_def["label"]))
        if bases is not None and property_def is restrict_property_def:
            eligible = find_slot_items(slot_def, restrict_serials=restrict_serials)
        else:
            eligible = full_eligible
        _eligible_by_label[property_def["label"]] = eligible
        if property_def.get("gain_range") is None or property_def["label"] in _seen_labels:
            continue
        _seen_labels.add(property_def["label"])
        _entries.append((property_def["label"], property_def.get("category"), property_def["gain_range"],
                         target_stat, snapshot_property_values(eligible, property_def), 0))
    _st = {}
    if _entries:
        preview_progress_step("rows: chained run")
        simulate_batch_trials(_entries, float("inf"), float("inf"), PREVIEW_COMPLETION_TRIALS, stats_out=_st)
    for property_def, target_stat in requests:
        eligible = _eligible_by_label[property_def["label"]]
        runes_needed = float(_st.get("attempts", {}).get(property_def["label"], 0.0))
        expected_breaks = float(_st.get("broken", {}).get(property_def["label"], 0.0))
        applications_needed = max(0.0, runes_needed - expected_breaks)
        existing_finished = available_rune_amount(property_def)
        still_needed = max(0.0, runes_needed - existing_finished)
        from_blanks = min(still_needed, blanks_pool)
        blanks_pool -= from_blanks
        stone_needed = still_needed - from_blanks
        rows.append({
            "property_def": property_def,
            "target_stat": target_stat,
            "eligible_count": len(eligible),
            "restricted": bases is not None and property_def is restrict_property_def,
        })
        total_applications += applications_needed
        total_breaks += expected_breaks
        total_stone += stone_needed
    totals = {
        "applications_needed": int(round(total_applications)),
        "expected_breaks": int(round(total_breaks)),
        "stone_needed": int(round(total_stone)),
        "est_minutes": (total_applications / float(ESTIMATED_APPLICATIONS_PER_HOUR)) * 60.0,
        # PACK + STORAGE (2026-09-16) -- this is the "(0 on hand)" the user photographed while the
        # storage held stone. See available_rough_stone().
        "rough_stone_on_hand": available_rough_stone(),
        "eligible_count": len(full_eligible),
        "finished": float(_st.get("finished", 0.0)),          # items expected to survive EVERY stat (2026-09-24)
        "any_finished": float(_st.get("any_finished", 0.0)),  # chance at least one does
        # (2026-10-17) WORK FEWER ITEMS: (serial, chance it survives every stat) for each item in play
        "finish_by_item": (list(zip([it.Serial for it in full_eligible], _st.get("finished_by_item") or []))
                           if len(_st.get("finished_by_item") or []) == len(full_eligible) else []),
    }
    return rows, totals

APPLY_PREVIEW_MONTE_CARLO_TRIALS = 200  # Trial count for estimate_apply_odds() below. UNCONFIRMED
                                          # against live timing in this specific embedded
                                          # interpreter -- each trial is pure Python (no RE calls
                                          # at all once snapshotting is done), so this can be
                                          # raised if 200 proves too coarse, or lowered if the
                                          # preview gump takes noticeably long to appear.

def snapshot_property_values(eligible, property_def):
    """One real read_property_value() call per item -- called ONCE per requested stat, before any
    simulation runs. estimate_apply_odds()'s Monte Carlo loop itself never touches RE's live API
    (Items.WaitForProps/GetPropStringList), only these pre-fetched snapshots -- that's what lets
    hundreds of trials stay cheap, pure in-memory Python."""
    return [read_property_value(it, property_def) or 0 for it in eligible]

# =============================================================================
# ASSUMED GEAR -- this script never needs the items in your pack
# =============================================================================
#
# Per the user, 2026-11-07: "we should not have to have the items in our
# pack ... lets have the craft and store system always think the items are
# present at 20 a piece of each item listed." Raised to 50 the same day,
# for the surplus: see ASSUMED_ITEM_COUNT below.
#
# Which is right, and was an oversight: the whole point of this script is
# stocking runes for gear you have not got yet. Sizing the batch off what
# happens to be in the backpack makes it craft nothing on the one occasion
# it is most wanted - an empty pack.
#
# THREE OVERRIDES, DEFINED HERE BECAUSE HERE IS AFTER the originals. Python
# takes the last definition, and snapshot_property_values() in particular is
# defined further up this file than the store flow that uses it, so a block
# placed any earlier would be the one that got replaced.
#
# ALWAYS ASSUMED_ITEM_COUNT, not "that many when the pack is empty". A rule
# that changes with what you happen to be carrying gives a different answer
# every run and is not worth the surprise; this way the number on the screen
# is the number you asked for, whatever you own.

# FIFTY, raised from 20 on 2026-11-07: "this way i have a surplus no
# matter what i craft on the other script."
#
# THE COST IS EXACTLY LINEAR, which is what makes the choice easy. Measured
# against this file's own simulation (target 100, a 3-9 gain property):
# 14.8 runes per item at every pool size from 1 to 100, and 71% of items
# reach target at every size. Nothing about the model prefers one count, so
# this is a batch-size dial and not a tuning parameter - 50 simply makes
# 2.5x what 20 did, for 2.5x the stone.
#
# RUNNING IT TWICE IS THE SAME AS DOUBLING IT, because the store flow
# subtracts what the key already holds before crafting. So this number is
# "how deep a surplus in one run", not a ceiling.
ASSUMED_ITEM_COUNT = 50
ASSUMED_START_VALUE = 0       # a fresh item has none of the property yet,
                              # which is also the costliest case to stock for


class AssumedItem(object):
    """A stand-in for a piece of gear this script does not have to own.

    It carries only what the preview touches: a Serial, and enough of a name
    and layer that anything reading them incidentally gets a string rather
    than an exception. Nothing ever asks the server about one -- the
    override of snapshot_property_values() below means no tooltip is read
    off these, which is what keeps the fakes harmless.

    THE SERIAL IS NEGATIVE so it can never collide with a real item's, and
    so anything that does manage to look one up fails to find it rather than
    finding somebody else's gear.
    """

    __slots__ = ("Serial", "Name", "ItemID", "Layer")

    def __init__(self, index):
        self.Serial = -(index + 1)
        self.Name = "assumed item %d" % (index + 1)
        self.ItemID = 0
        self.Layer = "Invalid"


def find_slot_items(slot_def, restrict_serials=None, in_pack_only=False):
    """OVERRIDDEN: always ASSUMED_ITEM_COUNT stand-ins, never a real search.

    Every count on the preview then reads ASSUMED_ITEM_COUNT and agrees with
    the costs beside it, which a real search would not: with an empty pack
    the screen would have said "0 items" over a bill for fifty.

    restrict_serials IS IGNORED, and it has to be. It is the preview's
    "Work 3 -- 95%" feature, which picks out particular items of yours by
    serial; there are no particular items here, so narrowing to a few of
    identical assumptions would mean nothing. Stock for the whole
    ASSUMED_ITEM_COUNT or change it.

    THE RUNE MENU STILL SHOWS EVERYTHING THE SLOT CAN TAKE. The stand-ins
    carry no properties, so vote_winning_category() finds nothing to decide
    on and returns no categories - the same path an empty backpack already
    takes upstream, and the right one here: stocking is choosing what you
    want, not discovering what you own.
    """
    return [AssumedItem(i) for i in range(max(1, ASSUMED_ITEM_COUNT))]


def snapshot_property_values(eligible, property_def):
    """OVERRIDDEN: every assumed item starts with none of the property.

    This is the seam the whole thing turns on. The simulation never touches
    the live API - it works entirely from the list this returns - so
    replacing it is enough to make every estimate in the file, the preview's
    rows included, size itself against assumed gear instead of real gear.

    It ignores `eligible` deliberately rather than reading its length: the
    answer must be ASSUMED_ITEM_COUNT even if some other caller hands it a
    pool from somewhere else.
    """
    return [ASSUMED_START_VALUE] * max(1, ASSUMED_ITEM_COUNT)


def ensure_slot_source(slot_def):
    """OVERRIDDEN: never ask for a chest.

    Upstream offers a cursor and asks you to target the container holding
    the items when your backpack has none, because the apply run has to
    fetch replacements as they break. Nothing is applied here and nothing
    breaks, so there is nothing to fetch and no chest to ask for.
    """
    clear_slot_source()
    return slot_def


def _lowest_value_index(values):
    """Index of the smallest value in `values` -- shared by every Monte Carlo random-walk loop in
    this file (a plain linear scan, not min()/key=, to avoid per-call lambda overhead across what
    can be many thousands of calls per trial)."""
    lowest_idx = 0
    lowest_val = values[0]
    for i in range(1, len(values)):
        if values[i] < lowest_val:
            lowest_val = values[i]
            lowest_idx = i
    return lowest_idx

def simulate_stat_trial(values, target_stat, gain_range, attempts_budget, survivors_out=None):
    """One Monte Carlo trial of run_slot_application()'s own random walk for a single requested
    stat, given a starting snapshot of every eligible item's current value (NOT mutated -- a local
    copy is made). Repeatedly applies to whichever SURVIVING item currently has the lowest value
    (same "always target the lowest" selection rule run_slot_application() itself uses) until
    every surviving item reaches target_stat, the whole pool breaks, or attempts_budget runs out
    -- whichever happens first. Each application independently rolls BREAK_CHANCE_PER_APPLICATION
    against the target ITEM (destroying it -- matches run_slot_application()'s own "it broke"
    branch) or, on success, adds a gain drawn from gain_range. A plain 2-tuple (min, max) draws
    UNIFORMLY continuous across that range (a simplification of the real, presumably-integer,
    per-application gain -- same one estimate_applications_needed() makes using the range's plain
    midpoint elsewhere). A longer tuple is treated as an explicit set of equally-likely DISCRETE
    outcomes instead (random.choice) -- Luck's real gain is exactly one of {15, 30, 45}, never
    anything in between, so its own gain_range is (15, 30, 45), not a (min, max) pair; see that
    catalog entry's own comment and PROPERTY_CATALOG's header comment.

    Returns (attempts_used, reached, unresolved). reached is how many of the STARTING items
    actually reached target_stat and survived; unresolved is how many were still below target,
    unbroken, when attempts_budget ran out (always 0 unless the budget itself was the reason the
    loop stopped). The caller derives broken = len(starting values) - reached - unresolved.

    FIXED (2026-08-27), per the user, live: the FIRST version of this function returned a plain
    "survivors"/"finished" pair that treated "every item broke" and "every item reached target" as
    the SAME outcome (both leave the while loop's `values and any(v < target_stat ...)` condition
    False -- one because `values` emptied out, the other because every remaining value cleared the
    bar). A live preview showed "100%" odds for a target so high relative to gain_range/break_chance
    that every item was actually near-certain to break trying, long before reaching it -- the old
    code called that a "success" because the trial technically finished within budget, without
    checking whether anything actually SURVIVED to hit the target. reached/unresolved (below),
    with broken derived by the caller, keeps those three outcomes distinct."""
    # MIN-HEAP, NOT THREE LINEAR SCANS (2026-09-16). This loop used to do O(n) work three times
    # per attempt -- `any(v < target_stat ...)` for the condition, _lowest_value_index() for the
    # pick, and `del values[idx]` for a break, which shifts the whole list. With the attempt
    # count itself growing with the pool that made the preview near-QUADRATIC, and a player of
    # the shipped script simply never got the Calculate screen with 250 items in the pack.
    #
    # Measured, CPython, 19 stats x 200 trials (IronPython 2-5x slower):
    #     250 items  2.5 min -> 19 s (8x)      1000 items  39 min -> 88 s (27x)
    #     500 items  8.9 min -> 43 s (13x)     2000 items 144 min -> 2.6 min (54x)
    #
    # THE CONDITION AND THE PICK ARE THE SAME QUESTION: what is the minimum? If the minimum is
    # at target then every survivor is, so one pop answers both. A break becomes a lazy delete
    # -- simply not pushed back -- instead of a list shift.
    #
    # EXACT, NOT MERELY EQUIVALENT: 0 mismatches over 360 comparisons (6 configurations x 60
    # seeds) against the old loop seeded identically, comparing the whole returned tuple. Three
    # things make that true and all three are load-bearing:
    #   1. The random draws stay in the SAME ORDER -- one random.random() per attempt, then a
    #      gain draw only when it did not break.
    #   2. Ties break identically. _lowest_value_index() scanned with a strict `<` and so kept
    #      the FIRST minimum; a heap of (value, position) pops lowest value then lowest
    #      position -- the same element. Load-bearing because every item starts at 0.0, so the
    #      opening rounds are ALL ties.
    #   3. `del` preserved the relative order of the survivors, so ordering ties by ORIGINAL
    #      position picks the same item as ordering by current index.
    heap = [(v, i) for i, v in enumerate(values)]
    heapq.heapify(heap)
    alive = len(heap)
    attempts = 0
    while alive:
        v, pos = heapq.heappop(heap)
        if v >= target_stat:
            # The smallest survivor is at target, so they all are. Push it back so the count
            # below is honest about what is still in the pool.
            heapq.heappush(heap, (v, pos))
            if survivors_out is not None:
                survivors_out.extend(_p for _v, _p in heap)   # every item still in the heap is alive (2026-09-24)
            return attempts, alive, 0
        if attempts >= attempts_budget:
            heapq.heappush(heap, (v, pos))
            reached = sum(1 for _v, _p in heap if _v >= target_stat)
            if survivors_out is not None:
                survivors_out.extend(_p for _v, _p in heap)
            return attempts, reached, alive - reached
        attempts += 1
        if random.random() < BREAK_CHANCE_PER_APPLICATION:
            alive -= 1          # LAZY DELETE -- not pushing it back is the removal
        else:
            if len(gain_range) > 2:
                v += random.choice(gain_range)
            else:
                v += random.uniform(gain_range[0], gain_range[1])
            heapq.heappush(heap, (v, pos))
    return attempts, 0, 0   # `alive` hit 0: the whole pool broke, so nothing reached target and
                            # nothing is unresolved. The old code returned len(values) here,
                            # which was 0 for the same reason -- the list was empty.

PREVIEW_COMPLETION_TRIALS = 30  # Trials for simulate_stat_completion() below -- fewer than APPLY_
                                   # PREVIEW_MONTE_CARLO_TRIALS (200) since each trial here runs
                                   # UNCAPPED (no attempts_budget ceiling, see that function's own
                                   # docstring) and can take meaningfully longer per trial for a
                                   # hard target; this only needs a rough average for a display
                                   # number, not a precise probability.

def simulate_stat_completion(values, target_stat, gain_range, trials=PREVIEW_COMPLETION_TRIALS):
    """Average (attempts, reached, broken) to bring EVERY item in `values` to target_stat OR have
    it break trying, via simulate_stat_trial() with an UNCAPPED attempts_budget (float('inf')) --
    the TRUE expected resource cost for full completion, correctly bounded by the real, SHRINKING
    item pool (an item that breaks is removed and can never break again, capping total possible
    breaks at len(values)).

    ADDED (2026-08-27), per the user's own live report, spotting a real inconsistency between two
    numbers on the SAME preview screen: "it seems like if 75 breaks are expected for 600, 30 items
    wouldn't be enough to get 573 right? Kind of seems like we're using different math on those or
    something." Exactly right. build_apply_preview_rows()'s old closed-form estimate_applications_
    needed() computes "expected breaks" as total_attempts - total_successes, a formula that
    implicitly treats the item pool as infinite/never-shrinking -- for a target hard enough
    relative to the pool, it can predict MORE break events than there are actual items to break
    (75 predicted breaks against only 30 real items -- a physical impossibility, since each item
    can only break once). suggest_realistic_dump_target()/estimate_apply_odds() already use THIS
    file's own proven simulate_stat_trial() instead, which correctly caps breaks at the real pool
    size because it operates on an actual shrinking Python list, not a closed-form formula. Reusing
    that SAME simulation primitive for the row-level numbers too (this function) means every number
    on the preview screen now comes from ONE consistent model, not two silently disagreeing ones.

    Break EVENTS and ITEMS BROKEN are the same count here (each item breaks at most once), so the
    averaged `broken` return value directly IS "expected item breaks"; `attempts - broken` is the
    count of successful application EVENTS (potentially many per surviving item), matching what
    estimate_applications_needed()'s own "applications_needed" used to mean, just correctly bounded
    now. Returns (0.0, 0.0, 0.0) if `values` is empty."""
    total_start = len(values)
    if total_start == 0:
        return 0.0, 0.0, 0.0
    total_attempts = 0
    total_reached = 0
    total_broken = 0
    for _trial in range(trials):
        preview_progress_sub(float(_trial) / max(1, trials))
        attempts, reached, _unresolved = simulate_stat_trial(values, target_stat, gain_range, float("inf"))
        total_attempts += attempts
        total_reached += reached
        total_broken += (total_start - reached)
    return (total_attempts / float(trials), total_reached / float(trials), total_broken / float(trials))

def simulate_batch_trials(entries, blanks_pool_start, stone_pool_start, trials, stats_out=None):
    """Shared Monte Carlo core -- runs `trials` full-batch simulations over `entries` (a list of
    (label, category, gain_range, target_stat, values, existing_finished) tuples, ALREADY
    snapshotted and in the batch's own real sequential processing order), sharing the SAME
    blanks_pool_start/stone_pool_start budget across every entry within a trial exactly like
    craft_more_runes_if_needed()'s real top-up would.

    Per-entry SUCCESS criterion: a "dump"-category entry needs `reached >= min(SUGGEST_TARGET_MIN_
    ITEMS_REACHED, len(values))`. A "required"-category entry needs `unresolved == 0` -- NOT "zero
    broken" (see the CORRECTION below for why breakage isn't a failure at all for this category).
    A trial counts as an overall SUCCESS only if every entry's own criterion is satisfied.

    CORRECTED (2026-08-27), per the user, live, questioning an earlier framing directly: "We
    shouldn't be thinking about zero losses here. What does that mean?" Right to push on it --
    the ORIGINAL version required `reached == total_start` for a required-category entry (zero
    items broken, zero unresolved) and called that a "success." But run_slot_application()'s own
    ACTUAL behavior for a required stat is "grind on whoever survives until every item either
    reaches target OR breaks -- no protected floor" (see that function's own "FLOOR is category-
    dependent" docstring): losing SOME items along the way to a hard target is a normal, EXPECTED
    part of that grind, not a failure of the required stat -- the category name means "not
    negotiable / no floor protection," not "zero losses tolerated." The genuine failure mode is
    running out of Rough Stone/blanks BEFORE the grind can even finish, leaving an item stuck
    mid-way (neither at target nor broken) -- exactly what simulate_stat_trial()'s own `unresolved`
    return value already tracks. Requiring `unresolved == 0` instead of `reached == total_start`
    fixes a real, previously-unnoticed problem: with the old bar, ANY required stat spanning more
    than a handful of items read as near-impossible to "succeed" even at an easy target, since
    per-item survival probability compounds multiplicatively across the whole pool (p^N) -- purely
    an artifact of the wrong question being asked, not a real reflection of run health.

    ADDED (2026-08-27), extracted from estimate_apply_odds()'s own original body -- per the user,
    live, after spotting that select_apply_bases()/suggest_realistic_dump_target() only ever
    checked the DUMP stat's own ISOLATED probability (against a budget pre-reduced by a CLOSED-
    FORM guess at what required stats would consume): "it looks like our suggestion is faulty if
    we add other required stats. It's still based on only the SDI calculation it seems." Exactly
    right -- both searches now share THIS exact whole-batch simulation (the SAME one estimate_
    apply_odds() itself uses for the final headline number) instead of a separate, narrower,
    less-accurate approximation that never accounted for a required stat also being a blocker.

    Returns (probability, per_label_reached, per_label_broken) -- see estimate_apply_odds()'s own
    docstring for the exact meaning of each."""
    successful_trials = 0
    reached_totals = dict((e[0], 0) for e in entries)
    broken_totals = dict((e[0], 0) for e in entries)
    attempts_totals = dict((e[0], 0) for e in entries)
    finished_total = 0          # survivors of the last chained stat, summed over trials (2026-09-24)
    pool_len = len(entries[0][4]) if entries else 0
    finished_by_item = [0] * pool_len   # (2026-10-17) WORK FEWER ITEMS: how often each item survived every stat
    any_finished_trials = 0     # trials that ended with at least one survivor
    pool_n = len(entries[0][4]) if entries else 0
    for _trial in range(trials):
        preview_progress_sub(float(_trial) / max(1, trials))
        blanks_pool = blanks_pool_start
        stone_pool = stone_pool_start
        trial_success = True
        # THE POOL IS CHAINED (2026-09-24, owner: the two preview screens "need to match"). This used to run every
        # stat on the FULL snapshot, so an item that broke on stat 1 was back in the pool for stat 2 and every stat
        # after -- 17 stats on 94 axes read as 344 expected breaks from 94 items and 16,876 applications. The run
        # itself works each stat on whatever is still in the pack: an item that breaks is gone for the rest. So
        # each stat here runs on the survivors of the stat before it. An entry whose value list is a different
        # size (the base picker's restricted subset) cannot be lined up with the pool and runs on its own values.
        alive_idx = None
        for label, category, gain_range, target_stat, values, existing_finished in entries:
            _chained = (len(values) == pool_n)
            if _chained and alive_idx is not None:
                values = [values[i] for i in alive_idx]
            total_start = len(values)
            free_attempts = existing_finished
            attempts_budget = free_attempts + blanks_pool + stone_pool
            _surv = []
            attempts_used, reached, unresolved = simulate_stat_trial(
                values, target_stat, gain_range, attempts_budget, survivors_out=_surv)
            if _chained:
                alive_idx = [(_pp if alive_idx is None else alive_idx[_pp]) for _pp in _surv]
            attempts_totals[label] += attempts_used
            broken = total_start - reached - unresolved
            reached_totals[label] += reached
            broken_totals[label] += broken
            if category == "dump":
                required_for_this = min(SUGGEST_TARGET_MIN_ITEMS_REACHED, total_start)
                if reached < required_for_this:
                    trial_success = False
            elif unresolved > 0:
                # A required-category entry -- see this function's own CORRECTED docstring note.
                # Breakage is NOT a failure here (it's the normal, expected cost of grinding a
                # hard target with no protected floor); only running out of Rough Stone/blanks
                # before every item's fate is resolved one way or the other counts as failing.
                trial_success = False
            shared_consumed = max(0, attempts_used - free_attempts)
            from_blanks = min(shared_consumed, blanks_pool)
            blanks_pool -= from_blanks
            stone_pool -= (shared_consumed - from_blanks)
        if trial_success:
            successful_trials += 1
        _left = len(alive_idx) if alive_idx is not None else 0
        finished_total += _left
        for _i in (alive_idx or []):
            if 0 <= _i < pool_len:
                finished_by_item[_i] += 1
        if _left:
            any_finished_trials += 1

    probability = successful_trials / float(trials)
    if stats_out is not None:
        stats_out["attempts"] = dict((label, total / float(trials)) for label, total in attempts_totals.items())
        stats_out["broken"] = dict((label, total / float(trials)) for label, total in broken_totals.items())
        stats_out["finished"] = finished_total / float(trials)
        stats_out["any_finished"] = any_finished_trials / float(trials)
        stats_out["finished_by_item"] = [n / float(trials) for n in finished_by_item]
        stats_out["pool"] = pool_n
    per_label_reached = dict((label, total / float(trials)) for label, total in reached_totals.items())
    per_label_broken = dict((label, total / float(trials)) for label, total in broken_totals.items())
    return probability, per_label_reached, per_label_broken

def estimate_apply_odds(requests, slot_def, bases=None):
    """Monte Carlo estimate of "odds of hitting target thresholds" -- per the user (2026-08-27):
    "show... the odds of hitting target thresholds" alongside the expected-value figures build_
    apply_preview_rows() already computes. That function's own model is expected-value only (an
    AVERAGE gain per application), which can't say anything about the actual CHANCE of success
    given a finite Rough Stone supply and genuinely random gains/breaks -- this runs
    APPLY_PREVIEW_MONTE_CARLO_TRIALS full simulated passes of the WHOLE batch instead. Each trial:

      1. Simulates every requested stat's own random walk (simulate_stat_trial(), against a
         PRE-FETCHED value snapshot -- see snapshot_property_values()) in the SAME sequential
         order run_application_flow() will actually process them in, each stat's attempts_budget
         starting at (existing finished runes for that property) + (whatever's left of the shared
         Blank Rune pool) + (whatever's left of Rough Stone on hand) -- draining the shared blanks/
         stone pools as each stat's simulated attempts consume them, exactly like craft_more_
         runes_if_needed()'s real top-up would, so a later stat in the same trial genuinely
         competes with an earlier one for the same finite resources.
      2. Per-stat SUCCESS criterion -- see simulate_batch_trials()'s own docstring for the full,
         CORRECTED reasoning: a REQUIRED-category stat succeeds in a trial if `unresolved == 0`
         (every item's fate got fully resolved -- reached target or broke -- before Rough Stone/
         blanks ran out); breakage itself is NOT a failure for this category, it's the normal,
         expected cost of grinding a hard target with no protected floor. The batch's ONE dump-
         category request (if `bases` restricts it -- see select_apply_bases()) instead only needs
         `reached >= SUGGEST_TARGET_MIN_ITEMS_REACHED` (capped at its own eligible count). A trial
         counts as an overall SUCCESS only if every request's own criterion (required or dump) is
         satisfied.

         FIXED (2026-08-27), per the user, live, BEFORE the criterion above existed: a target set
         far enough beyond what gain_range/BREAK_CHANCE_PER_APPLICATION can realistically sustain
         makes near-certain item destruction the actual likely outcome -- see simulate_stat_
         trial()'s own docstring for the exact live "100%" bug this replaced (the old version
         called a trial where every item broke before reaching target a "success," since the
         random walk still technically finished within budget).

    Returns (probability, per_stat_reached, per_stat_broken) -- probability is the fraction of
    trials that met every request's own success criterion (0.0-1.0, see above); per_stat_reached/
    per_stat_broken are each {property_def['label']: average count across every trial} -- reached
    is how many of that stat's eligible items are expected to actually hit target; broken is how
    many are expected to be destroyed trying. (reached + broken) can fall short of the eligible
    count when Rough Stone ran out before every item resolved either way -- the gap between them is
    the unresolved count.

    CAVEAT, deliberately not modeled: backpack headroom (bulk_craft_headroom()) -- a real run can
    still be blocked by a full backpack even with enough Rough Stone on hand (craftable_now()'s own
    existing_blanks + headroom cap). This only checks the Rough Stone QUANTITY constraint the user
    named, not bag space. Returns (None, {}, {}) if no requested stat has a confirmed gain_range to
    simulate against.

    THIN WRAPPER (2026-08-27) around simulate_batch_trials() -- see that function's own docstring
    for the shared core this now delegates to (extracted so select_apply_bases()/suggest_
    realistic_dump_target() can reuse the exact same whole-batch model instead of their own
    narrower, dump-stat-only approximation)."""
    eligible = find_slot_items(slot_def)
    restrict_property_def, restrict_serials = bases if bases is not None else (None, None)
    simulatable = [(pd, ts) for pd, ts in requests if pd.get("gain_range") is not None]
    if not simulatable:
        return None, {}, {}

    entries = []
    seen_labels = set()
    for property_def, target_stat in simulatable:
        preview_progress_step("odds: {}".format(property_def["label"]))
        label = property_def["label"]
        if label in seen_labels:
            continue
        seen_labels.add(label)
        if bases is not None and property_def is restrict_property_def:
            prop_eligible = find_slot_items(slot_def, restrict_serials=restrict_serials)
        else:
            prop_eligible = eligible
        values = snapshot_property_values(prop_eligible, property_def)
        existing_finished = available_rune_amount(property_def)
        entries.append((label, property_def.get("category"), property_def["gain_range"],
                         target_stat, values, existing_finished))

    # PACK + STORAGE (2026-09-16). These two feed simulate_batch_trials()'s attempts_budget, so a
    # pack-only count made every trial run dry immediately -- which is what produced "Odds this
    # batch succeeds: 0%" and a Suggested target of 0 while the storage was stocked.
    blanks_pool_start = available_blank_runes()
    stone_pool_start = available_rough_stone()
    return simulate_batch_trials(entries, blanks_pool_start, stone_pool_start,
                                  APPLY_PREVIEW_MONTE_CARLO_TRIALS)

def find_dump_request(requests):
    """Returns (index, property_def, target_stat) for the single dump-category request in
    `requests`, or None if there isn't EXACTLY one. Per the user (2026-08-27): "We'd only ever
    suggest decreasing a dump stat, for now let's assume the player only wanted to use one dump
    stat, either SDI or Luck." A batch with zero or 2+ dump-category requests isn't handled yet --
    returns None either way, same as "nothing to suggest.\""""
    dump_rows = [(i, pd, ts) for i, (pd, ts) in enumerate(requests) if pd.get("category") == "dump"]
    if len(dump_rows) != 1:
        return None
    return dump_rows[0]

def _build_other_entries(requests, dump_index, full_eligible):
    """Snapshots every NON-dump request in `requests` (every index except `dump_index`) into the
    entries format simulate_batch_trials() expects -- shared setup for select_apply_bases()'s and
    suggest_realistic_dump_target()'s own whole-batch searches, which both hold these OTHER
    requests fixed (their own targets are never touched, they're always evaluated against the
    FULL eligible pool) while searching over the dump request's own subset-size/target.

    REPLACES the old _dump_stat_attempts_budget() (2026-08-27), per the user, live: "it looks like
    our suggestion is faulty if we add other required stats. It's still based on only the SDI
    calculation it seems." That function reduced the OTHER requests down to a single closed-form
    "how much budget is left over" number -- this instead keeps them as REAL entries, simulated
    alongside the dump request in simulate_batch_trials(), so a required stat's own failure (e.g.
    it independently can't reach 100% survival) correctly drags down the WHOLE batch's probability
    instead of silently vanishing into a budget subtraction. Skips a request with no confirmed
    gain_range entirely (same convention estimate_apply_odds()'s own `simulatable` filter uses)."""
    entries = []
    for i, (property_def, target_stat) in enumerate(requests):
        preview_progress_step("detail: {}".format(property_def["label"]))
        if i == dump_index or property_def.get("gain_range") is None:
            continue
        values = snapshot_property_values(full_eligible, property_def)
        existing_finished = available_rune_amount(property_def)
        entries.append((property_def["label"], property_def.get("category"),
                         property_def["gain_range"], target_stat, values, existing_finished))
    return entries

SELECT_BASES_CONFIDENCE = 0.75  # Probability bar for "at least SUGGEST_TARGET_MIN_ITEMS_REACHED
                                   # of the chosen bases actually reach target" -- same 75%
                                   # ballpark already used for the odds color-coding elsewhere on
                                   # this preview.
SELECT_BASES_TRIALS_PER_CANDIDATE = 40
SOURCE_BATCH_CONFIDENCE = 0.99  # "~100%" for the working-set search (2026-09-16), per the user:
                                # "below the threshold for ~100%, max 10". At
                                # SELECT_BASES_TRIALS_PER_CANDIDATE=40 trials this can only be met
                                # by 40 of 40 -- 39/40 is 0.975 and fails -- so it reads as "no
                                # simulated trial fell short" rather than as a tuning dial.
                                # Stricter than SELECT_BASES_CONFIDENCE (0.75) on purpose: that
                                # one asks "is this worth SUGGESTING", this one asks "will this
                                # many actually finish".

def select_apply_bases(requests, slot_def):
    """Per the user (2026-08-27): "is there a scenario where we should be using less bases to
    craft with to increase odds? Like, if we're just trying to get 2 SDI, we'd probably only craft
    on 1 item. What about 100, or 400?" YES: run_slot_application()'s own "always target the
    LOWEST eligible item" rule advances the WHOLE working pool in lockstep -- with many items tied
    near the same value, every "round" (one full pass across the tied group before any single item
    gets a second hit) costs roughly (pool size) applications, regardless of how many actual
    successes are needed. A big pool (M) chasing a small goal (N successes) burns most of its
    budget on that per-round WIDTH overhead before making much DEPTH progress toward target --
    exactly why the 32-item/target-800 scenario in [[project_runecrafting_apply_preview_gump]]
    only reached ~2 survivors near target 595 despite thousands of Rough Stone spent. Concentrating
    on a small, hand-picked subset removes that width tax: the same budget goes almost entirely
    into depth instead of being divided across items that were never going to matter.

    Returns (property_def, restrict_serials) for the batch's one dump-category request (see
    find_dump_request()) if a SMALLER-than-full subset reliably (SELECT_BASES_CONFIDENCE) still
    delivers at least SUGGEST_TARGET_MIN_ITEMS_REACHED successes at the batch's CURRENT (already
    requested) target -- no need to also lower the target via suggest_realistic_dump_target() if
    concentrating alone solves it. Returns None if there's no single dump-category request, no
    confirmed gain_range, the pool is already small (<= SUGGEST_TARGET_MIN_ITEMS_REACHED, nothing
    to restrict), or even the FULL pool can't reliably deliver enough successes at the current
    target (in which case suggest_realistic_dump_target() -- lowering the target itself -- remains
    the fallback, since no subset of a pool that already fails can do any better than the whole
    thing).

    Bases are chosen as the items ALREADY CLOSEST to target (highest current value first) -- they
    need the fewest further applications each, on top of the width savings above. The subset SIZE
    is found via an EXPONENTIAL search (not a binary search -- success probability is NOT assumed
    monotonic in subset size, since a bigger subset both adds more independent chances at hitting
    the count AND dilutes the SAME shared budget across more competitors, so there's no guarantee
    which effect wins at every size): starting from the bare minimum count, the candidate size is
    doubled until one clears SELECT_BASES_CONFIDENCE (or the full pool size is reached, already
    confirmed to work by the earlier full-pool check) -- accepts that first passing size rather
    than searching for the theoretical smallest one, a reasonable trade for a suggestion feature.

    WHOLE-BATCH AWARE (2026-08-27) -- see _build_other_entries()'s own docstring for the "faulty
    suggestion" bug this fixes: every candidate is checked via simulate_batch_trials() against the
    FULL batch (every required-category request too, each simulated at its own real, unchanged
    target against the full eligible pool), not the dump stat's own probability in isolation. A
    required stat that's independently unreliable now correctly caps this search's own result too,
    rather than being invisible to it."""
    dump = find_dump_request(requests)
    if dump is None:
        return None
    dump_index, dump_property_def, target_stat = dump
    gain_range = dump_property_def.get("gain_range")
    if gain_range is None:
        return None

    full_eligible = find_slot_items(slot_def)
    total_eligible = len(full_eligible)
    min_items_needed = min(SUGGEST_TARGET_MIN_ITEMS_REACHED, total_eligible)
    if total_eligible <= min_items_needed:
        return None  # Already at (or below) the floor -- nothing to restrict.

    other_entries = _build_other_entries(requests, dump_index, full_eligible)
    dump_label = dump_property_def["label"]
    dump_existing_finished = available_rune_amount(dump_property_def)
    # PACK + STORAGE (2026-09-16). These two feed simulate_batch_trials()'s attempts_budget, so a
    # pack-only count made every trial run dry immediately -- which is what produced "Odds this
    # batch succeeds: 0%" and a Suggested target of 0 while the storage was stocked.
    blanks_pool_start = available_blank_runes()
    stone_pool_start = available_rough_stone()

    # Closest-to-target first -- needs the fewest further applications each, on top of the width
    # savings a smaller subset already provides.
    ranked = sorted(full_eligible,
                     key=lambda it: -(read_property_value(it, dump_property_def) or 0))
    ranked_values = [read_property_value(it, dump_property_def) or 0 for it in ranked]

    def success_probability(count):
        dump_entry = (dump_label, "dump", gain_range, target_stat,
                      ranked_values[:count], dump_existing_finished)
        probability, _reached, _broken = simulate_batch_trials(
            other_entries + [dump_entry], blanks_pool_start, stone_pool_start,
            SELECT_BASES_TRIALS_PER_CANDIDATE)
        return probability

    # If even the FULL pool can't reliably hit the count, no smaller subset -- which only ever has
    # LESS raw material to work with -- can do better. Bail out and let suggest_realistic_dump_
    # target() (a lower target instead) be the fallback.
    if success_probability(total_eligible) < SELECT_BASES_CONFIDENCE:
        return None

    count = min_items_needed
    best_count = total_eligible
    while count < total_eligible:
        if success_probability(count) >= SELECT_BASES_CONFIDENCE:
            best_count = count
            break
        count = min(count * 2, total_eligible)

    if best_count >= total_eligible:
        return None  # No smaller subset did any better than the full pool -- nothing to restrict.

    restrict_serials = set(it.Serial for it in ranked[:best_count])
    return dump_property_def, restrict_serials

SUGGEST_TARGET_TRIALS_PER_CANDIDATE = 30  # Per candidate target tried during the binary search
                                             # below -- fewer than APPLY_PREVIEW_MONTE_CARLO_TRIALS
                                             # since this only needs a rough average, repeated
                                             # across ~log2(current_target) candidates.
SUGGEST_TARGET_MIN_ITEMS_REACHED = 1  # LOWERED 2 -> 1 (2026-09-19), per the user: the calculations were
                                         # based on getting 2 items to the target; change that to 1. The
                                         # history of the 2 is kept below.
                                         # A suggested target should let AT LEAST this many items
                                         # reach it, ON AVERAGE -- an ABSOLUTE count, not a
                                         # fraction of the eligible pool. Per the user (2026-08-27),
                                         # correcting a fraction-based first attempt below: "Most of
                                         # them to reach isn't a good metric. That will make us aim
                                         # too low. I think 2 of them reach is a better target." A
                                         # dump stat (SDI/Luck) is already protected down to its
                                         # LAST item by run_slot_application()'s own floor (see that
                                         # function's own "FLOOR is category-dependent" docstring
                                         # note) -- the point of a dump-stat run was never "convert
                                         # the whole pool," just land the stat on a handful of good
                                         # pieces, so a fixed small count is the right bar, not a
                                         # percentage that scales (and gets harder to hit) with pool
                                         # size.

def suggest_realistic_dump_target(requests, slot_def):
    """Per the user: use the preview page to suggest a more realistic (lower) target for the
    batch's one dump-category stat (SDI or Luck), given the Rough Stone actually on hand. Returns
    (property_def, current_target, suggested_target, suggested_probability), or None if there's no
    single dump-category request to adjust (see find_dump_request()), no confirmed gain_range for
    it, or nothing lower is worth suggesting (suggested_target >= current_target already) -- this
    NEVER suggests an INCREASE, per the user ("only ever suggest decreasing a dump stat").
    suggested_probability (2026-08-27) is the whole-batch success probability AT suggested_target,
    freshly re-checked once right before returning -- per the user: "When we're making a
    suggestion, show a new odds line below the suggestion that reflects the suggestion output."

    Model: required-category stats in the same batch are treated as fixed/non-negotiable -- their
    own requested targets are never touched, but (2026-08-27, see WHOLE-BATCH note below) they ARE
    still genuinely simulated alongside the dump stat, not reduced to a budget number. BINARY-
    SEARCHES the dump stat's target_stat (0..current_target) for the LARGEST value where, across
    SUGGEST_TARGET_TRIALS_PER_CANDIDATE runs of simulate_batch_trials(), the WHOLE BATCH succeeds
    (every required stat with zero losses, the dump stat reaching SUGGEST_TARGET_MIN_ITEMS_REACHED)
    at least SELECT_BASES_CONFIDENCE of the time.

    WHOLE-BATCH AWARE (2026-08-27) -- per the user, live, after spotting a real batch where this
    kept suggesting a lower SDI target even though a REQUIRED stat (FC) was independently the
    actual blocker (expected to lose 8 of 24 items on its own, target-20, with zero relation to
    SDI): "it looks like our suggestion is faulty if we add other required stats. It's still based
    on only the SDI calculation it seems." Exactly right -- the old version only ever checked the
    dump stat's own isolated probability against a budget pre-reduced by a closed-form guess at
    what the required stats would consume, so a required stat's own independent unreliability was
    completely invisible to this search. Now shares simulate_batch_trials() (see _build_other_
    entries()'s own docstring) -- the SAME whole-batch model estimate_apply_odds() itself uses --
    so a required stat that can't reliably succeed on its own correctly caps what this search can
    ever report, instead of being ignored. If even DISABLING the dump stat entirely (target 0)
    still can't clear the confidence bar, the real blocker is a required stat, not the dump stat --
    returns None rather than misleadingly suggesting "SDI -> 0" as if that would fix the batch.

    TWO WRONG ATTEMPTS, both caught live the same session before shipping:
    1. The ORIGINAL version ran an UNCAPPED walk (no target at all, just "keep applying to the
       current lowest until the budget runs out") and suggested the low-percentile ENDING MINIMUM
       survivor value across trials -- reasoning that "always target the lowest" keeps every
       survivor's value close together, so that minimum should be a safe floor. Standalone-tested
       against a real scenario (32 items starting at 0, a few thousand attempts of budget): it
       suggested target 0. Root cause: with many items starting tied at the same low value, they
       all compete for the SAME early attention -- a few early losses are close to unavoidable even
       for a trivially low target, so the group's WORST-off single survivor dominated the metric
       and crushed it toward 0.
    2. The SECOND version (this docstring's own prior text) required a FRACTION of the pool
       (SUGGEST_TARGET_MIN_SURVIVAL_FRACTION, 0.75) to reach target on average. Per the user,
       correcting it directly: "Most of them to reach isn't a good metric. That will make us aim
       too low. I think 2 of them reach is a better target." A percentage bar gets HARDER to clear
       as the pool grows (75% of 32 is 24 items, a much higher bar than 75% of 4), even though a
       dump stat (SDI/Luck) is already protected down to its LAST item by run_slot_application()'s
       own floor -- the actual goal was never "convert the whole pool," just land the stat on a
       handful of good pieces. A fixed absolute count doesn't scale against pool size the same
       (wrong) way a percentage does."""
    dump = find_dump_request(requests)
    if dump is None:
        return None
    dump_index, dump_property_def, current_target = dump
    gain_range = dump_property_def.get("gain_range")
    if gain_range is None:
        return None

    eligible = find_slot_items(slot_def)
    if not eligible:
        return None

    starting_values = snapshot_property_values(eligible, dump_property_def)
    total_eligible = len(starting_values)
    if total_eligible == 0:
        return None

    other_entries = _build_other_entries(requests, dump_index, eligible)
    dump_label = dump_property_def["label"]
    dump_existing_finished = available_rune_amount(dump_property_def)
    # PACK + STORAGE (2026-09-16). These two feed simulate_batch_trials()'s attempts_budget, so a
    # pack-only count made every trial run dry immediately -- which is what produced "Odds this
    # batch succeeds: 0%" and a Suggested target of 0 while the storage was stocked.
    blanks_pool_start = available_blank_runes()
    stone_pool_start = available_rough_stone()

    # PROBABILITY-based bar (2026-08-27), NOT a bare average -- FIXED live, per the user, after the
    # Suggested button silently failed to appear for a batch whose own odds line (once THAT bug was
    # also fixed, see estimate_apply_odds()'s own note) was nowhere near reliable. Root cause: this
    # search used to accept "AVERAGE reached >= required_reached" as good enough -- an average of
    # 2.6 successes clears a bar of 2 easily even when the actual PROBABILITY of landing >= 2 is
    # nowhere near reliable (a mean above the bar says nothing about how often a run actually lands
    # below it). select_apply_bases() already used the correct, stricter probability-of-success bar
    # (SELECT_BASES_CONFIDENCE) for the exact same underlying question -- unified here so all three
    # sibling functions (this one, select_apply_bases(), estimate_apply_odds()) agree on what
    # "reliably enough" means for a dump stat, instead of two different bars silently disagreeing.
    def success_probability(target):
        dump_entry = (dump_label, "dump", gain_range, target, starting_values, dump_existing_finished)
        probability, _reached, _broken = simulate_batch_trials(
            other_entries + [dump_entry], blanks_pool_start, stone_pool_start,
            SUGGEST_TARGET_TRIALS_PER_CANDIDATE)
        return probability

    # If even TURNING OFF the dump stat entirely (target 0, an instant, guaranteed-free "success"
    # for that one entry) still can't clear the bar, the batch's real blocker is a required stat,
    # not this one -- see this function's own WHOLE-BATCH docstring note. Suggesting "SDI -> 0"
    # here would look like a fix without actually being one.
    if success_probability(0) < SELECT_BASES_CONFIDENCE:
        return None

    lo, hi = 0, current_target
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if success_probability(mid) >= SELECT_BASES_CONFIDENCE:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if best >= current_target:
        return None
    return dump_property_def, current_target, best, success_probability(best)

APPLY_PREVIEW_CHAR_PX = 6  # TIGHTENED (2026-08-27) from 8, per the user's own live report ("cut
                             # off some of the extra space on the right side to better match the
                             # left side") -- 8px/char left visibly more empty background on the
                             # right than the left margin, since this project's gump font renders
                             # noticeably narrower than that. Still an ESTIMATE (no in-client way
                             # to measure text width directly) -- if text ever spills past the
                             # background again, raise this back up; if there's still excess
                             # padding, lower it further.
APPLY_PREVIEW_MIN_WIDTH = 460
# THE PANEL FITS ITS TEXT (owner, 2026-10-17: "this screen needs to fit the text with the same padding on left and
# right"). A label is drawn in the client's Unicode font 1, whose letters differ in width -- an 'i' is 3 pixels, an 'm' 9,
# a 'W' 12 -- so a flat per-character guess ran long lines past the right edge. LABEL_GLYPH_PX is that font's own advance
# for every printable character, space to '~' (read from the client's unifont1.mul; a space is the client's fixed 8),
# checked against a live screenshot of this panel; anything else counts as a wide letter.
LABEL_GLYPH_PX = (8, 3, 4, 12, 9, 10, 11, 3, 4, 4, 10, 7, 3, 6, 3, 9, 8, 4, 8, 8, 8, 8, 8, 8, 8, 8, 3, 3, 8, 6, 8, 7, 12,
                  8, 8, 8, 8, 7, 7, 8, 8, 3, 8, 8, 7, 10, 8, 8, 8, 9, 8, 8, 7, 8, 8, 12, 8, 9, 8, 4, 9, 5, 10, 8, 3, 6,
                  6, 6, 6, 6, 6, 6, 6, 3, 6, 6, 3, 9, 6, 6, 6, 6, 6, 6, 6, 6, 6, 8, 6, 6, 6, 5, 2, 5, 6)
APPLY_PREVIEW_SIDE_MARGIN = 20  # the same margin left and right of the longest line
APPLY_PREVIEW_HTML_SLACK = 8    # an HTML line's box gets this much more: the client wraps one that measures exactly full


def label_px(text):
    """How wide `text` is drawn as a gump label -- see THE PANEL FITS ITS TEXT."""
    return sum(LABEL_GLYPH_PX[ord(c) - 32] if 32 <= ord(c) <= 126 else 12 for c in (text or ""))
APPLY_PREVIEW_RIGHT_MARGIN = 15  # TIGHTENED (2026-08-27) from an implicit 20 (the old formula was
                                    # `40 + len(text)*PX`, i.e. 20px on each side) -- per the same
                                    # user report, matched down toward the 20px LEFT margin
                                    # (labels start at x=20) rather than kept symmetric-but-loose.
APPLY_PREVIEW_HTML_HUE_COLORS = {68: "#4ae631", 33: "#e6315a", 43: "#FFAA00"}  # ADDED (2026-08-27)
                                    # -- Gumps.AddHtml()'s inline <BASEFONT COLOR=#RRGGBB> tags use
                                    # plain HTML hex, a SEPARATE color system from AddLabel()'s UO
                                    # hue-table IDs (68/33/43 used everywhere else in this gump). 68
                                    # (green)/33 (red) CONFIRMED live, per the user's own exact hex
                                    # picks from two live screenshots (red revised once: #c2294c ->
                                    # #e6315a). 43 (orange) still an unconfirmed approximation --
                                    # not used by anything in HTML mode yet.
APPLY_PREVIEW_HTML_WIDTH_CHAR_PX = 6.5  # ADDED (2026-08-27) at 8 (fixed wrapping), TIGHTENED to 6.5
                                        # (user: "way too much... at least 4x too much"), TIGHTENED
                                        # again to 6.25 (user: "take a little more off the right" --
                                        # a small trim this time, not another 4x-scale correction).
                                        # Used ONLY to size the html line's own width contribution
                                        # (which, being the widest line, directly sets the whole
                                        # gump's width) -- not a positioning estimate, since AddHtml
                                        # handles all internal layout itself.
APPLY_PREVIEW_WORK_BASE = 40             # WORK FEWER ITEMS: + the choice's place -- work that many


def show_apply_preview(requests, slot_def):
    """Preview + confirm gump shown right before run_application_flow() starts spending anything.
    Returns (accepted, final_requests, bases) -- accepted is True only for a real Accept click;
    final_requests is `requests` unchanged UNLESS the Suggested button was used (see below);
    bases is whatever select_apply_bases() found (or None). The caller must use the RETURNED
    requests/bases, not its own original requests, when actually starting the batch.

    WIDTH FIXED (2026-08-27), per the user's own live report ("we need to extend the UI
    background"): every line used to be added at a FIXED width (460) regardless of actual text
    length -- Gumps.AddLabel() has no width parameter and never wraps, so a longer line (a big
    number, a long property label) just renders past the edge of whatever Gumps.AddBackground()/
    AddAlphaRegion() width was chosen, floating outside the dark backing with no readable contrast
    behind it. Every line is now assembled into `lines` FIRST (text, hue), and the background
    width is sized from the actual longest one (see label_px()) before anything is
    drawn, instead of a blind guess.

    CONCENTRATED BASES (2026-08-27), per the user: "is there a scenario where we should be using
    less bases to craft with to increase odds?" select_apply_bases() is tried FIRST, at the
    batch's CURRENT (already requested) target -- if a small subset reliably delivers enough
    successes, the preview/odds below are computed against THAT subset (see build_apply_preview_
    rows()'s/estimate_apply_odds()'s own `bases` parameter), and suggest_realistic_dump_target()
    (lowering the target instead) is skipped entirely, since concentrating alone already solves it.

    SUGGESTED BUTTON (2026-08-27), per the user: "maybe we can then use this page to suggest a
    more realistic goal, and add a new suggested button in addition to the accept and cancel
    buttons." Only appears when select_apply_bases() found NOTHING to concentrate on (bases is
    None) AND suggest_realistic_dump_target() finds a single dump-category request (SDI or Luck --
    see that function's own docstring for the "one dump stat only" scope the user set) whose target
    is genuinely lower than what was requested -- the two features are mutually exclusive fallbacks
    for the SAME underlying problem (a dump-category target that isn't reliably achievable), tried
    in that order. Clicking Suggested swaps that one request's target for the suggested one and
    starts the batch IMMEDIATELY with it -- treated as an Accept, not shown for a second round of
    confirmation. CHANGED (2026-08-27) from an earlier version that recursed into a fresh show_
    apply_preview() call instead: per the user, live, that produced "a weird loop where I select
    the suggested option, it keeps bringing up the final gump again, often offering a new
    suggestion a little lower." Root cause: suggest_realistic_dump_target()'s own Monte Carlo
    search sits right at a confidence BOUNDARY using only SUGGEST_TARGET_TRIALS_PER_CANDIDATE (30)
    trials per candidate -- a fresh 30-trial batch on a re-preview can measure that same boundary a
    few points above or below the bar purely from random sampling noise, so recursing could keep
    landing on a slightly different (usually slightly lower) "suggestion" each time instead of ever
    settling, rather than any actual flaw in the original number. Starting immediately sidesteps
    that noise instead of trying to out-precision it."""
    # CALCULATIONS OFF SKIPS ALL OF IT (2026-09-17), per the user: "add that setting to
    # Runecrafting to skip the calculate phase."
    #
    # HERE RATHER THAN AT THE CALL SITE, so there is one dispatch point and any caller of this
    # function honours the setting. Returns the accept contract unchanged: accepted=True with
    # `requests` exactly as passed.
    #
    # bases=None IS A REAL CONSEQUENCE, NOT A SHORTCUT. select_apply_bases() concentration and
    # suggest_realistic_dump_target() are both computed below, inside the work being skipped,
    # so a run with calculations off genuinely does not get the concentrate-on-fewer-bases
    # improvement. Logged at 33 because it is a capability the player is giving up, not an
    # incidental detail -- and the row's tooltip says the same thing before they choose.
    if not calculations_enabled():
        log("Calculations are off -- starting the craft with no cost/odds preview, and "
            "without base concentration. Turn it back on in Settings.", 33)
        return True, requests, None
    # ONE PROPERTY FETCH PER ITEM FOR THE WHOLE PASS (2026-09-16). These four lines are where
    # every live property read in the preview happens; everything below is layout. Each of them
    # calls snapshot_property_values() once per requested stat, and that is one read per item --
    # so 250 items x 19 stats was ~14,250 Items.WaitForProps calls and the Calculate screen never
    # appeared for a player with a full pack. With the cache open it is one fetch per item.
    #
    # try/finally, NOT a bare pair: an exception in here must not leave the cache armed for
    # run_slot_application(), whose post-apply re-reads MUST be live (see property_lines_for()).
    global _preview_prop_lines
    _preview_prop_lines = {}
    # THE CALCULATING SCREEN (2026-09-16), per the user: a player with 250 items saw the rune
    # screen vanish and nothing come back. Even with the property cache and the heap rewrite a
    # big pool is tens of seconds, and a blocking computation cannot redraw itself -- so the
    # progress gump is opened HERE, stepped from inside the three per-stat loops, and closed in
    # the same finally that disarms the cache.
    #
    # The item count comes from the pool the passes will actually walk, so the number on screen
    # is the one that explains the wait.
    try:
        _pool = len(find_slot_items(slot_def))
    except Exception:
        _pool = 0
    preview_progress_begin(requests, _pool, slot_def["label"])
    try:
        preview_progress_step("choosing bases")
        bases = select_apply_bases(requests, slot_def)
        preview_progress_step("realistic target")
        suggestion = None if bases is not None else suggest_realistic_dump_target(requests, slot_def)
        rows, totals = build_apply_preview_rows(requests, slot_def, bases=bases)
        odds, _per_stat_reached, _per_stat_broken = estimate_apply_odds(requests, slot_def, bases=bases)
        _cached_items = len(_preview_prop_lines)
    finally:
        _preview_prop_lines = None
        preview_progress_end()
    # SAY WHAT IT COST, so the next "the preview never appeared" report is answerable without
    # guessing. One line per preview, and it is the number that used to be multiplied by the
    # requested-stat count three times over.
    log("Preview computed from {} item propert{} read (was {} read(s) before caching)."
        .format(_cached_items, "y" if _cached_items == 1 else "ies",
                _cached_items * max(1, len(requests)) * 3))

    # lines: each entry is EITHER (text, hue) -- a single-hue line -- OR a list of (text, hue)
    # segments to render left-to-right on the SAME row (2026-08-27, for the Total line's per-
    # bottleneck coloring below -- see its own comment). Built first so width/height can be sized
    # off the assembled content before anything is drawn.
    lines = []
    # ONE GOAL PER LINE, INDENTED (2026-09-11), per the user: "Instead of listing all the stats
    # we're going for, let's list each in one line below the first, and indent them to set them
    # apart."
    #
    # They had been packed into the title line since 2026-08-27 ("add the goal stats to the top
    # line since we removed that from the lines after"), which was fine for one or two and became
    # the longest line in the gump for three -- "Apply Preview -- Cloak (Hit Point Increase -> 25,
    # Mana Regen -> 40, Spell Damage Increase -> 400)" ran the full width of the box. That also
    # made it the line the background got sized against, using a 6px-per-character ESTIMATE
    # (APPLY_PREVIEW_CHAR_PX, deliberately tightened by the user from 8), which under-measures
    # exactly when the line is longest. Splitting them fixes the readability the user asked about
    # AND removes the widest line, so the box stops being sized by the least accurate estimate.
    #
    # rows already carries one (property_def, target_stat) pair per request, in order -- reused
    # here rather than re-deriving from `requests`.
    lines.append(("Apply Preview -- {}".format(slot_def["label"]), 68))
    for row in rows:
        lines.append(("    {} -> {}".format(row["property_def"]["label"], row["target_stat"]), 68))

    # PLURALS/ESTIMATE-SYMBOL CLEANUP (2026-08-27), per the user: "Get rid of all the parenthesis
    # around the s for plurals. Just assume plurals. Also get rid of the symbol being used for ~
    # estimated. Estimated is already implied when we use the word expected." Applies to every
    # number/noun pairing rendered below -- "applications"/"breaks"/"items"/"trials"/"minutes"
    # instead of "application(s)"/etc., and no leading "~" on any of them.
    # PER-ROW LINES REMOVED (2026-08-27), per the user, live, from a screenshot of the per-item
    # FC/SDI lines: "Let's just get rid of these lines." Went through three redesigns this session
    # (synthetic pool -> per-item percentage -> per-item applications/breaks) without ever landing;
    # rather than try a 4th, they're gone -- and per the user's own follow-up ("Don't compute data
    # we're not using. That computation is slow"), build_apply_preview_rows() no longer computes the
    # per-item numbers at all (removed its own extra uncapped simulate_stat_completion() call), not
    # just the gump text for them. The "restricted" (concentrating on fewer bases) sub-line below is
    # kept -- different information (which items the batch is using), not the removed figures.
    for row in rows:
        if row.get("restricted"):
            lines.append((
                "  (concentrating on {} of {} eligible items, closest to target already)".format(
                    row["eligible_count"], totals["eligible_count"]), 43))

    # BOTTLENECK COLORING (2026-08-27), per the user: "let's get rid of the 2nd line showing
    # eligible items, and just add that to the Total: line like we've done with the Rough Stone
    # [on hand]. Whichever is the bottleneck between items and rough stone, turn that [on hand]
    # the red color." Stone is the bottleneck if there's a genuine shortfall (needed > on hand,
    # same check as before). Items are inferred as the bottleneck when stone is NOT short but the
    # odds are still poor -- per the earlier conversation this session: once Rough Stone stops
    # being the limiting factor, the only thing left capping the odds is the eligible item COUNT
    # (each item's own survival probability is fixed, independent of how much stone exists, so
    # more stone past that point buys nothing -- see [[project_runecrafting_apply_preview_gump]]).
    # Only one of the two is ever flagged red -- stone is checked first, matching "whichever IS
    # the bottleneck" (singular), not both at once.
    #
    # LAYOUT (2026-08-27), per the user: "insert the [items on hand] count right after # expected
    # breaks, and get rid of the related text at the end of that line" -- the items bracket now
    # sits right after "expected breaks" instead of trailing the whole line, and the old separate
    # "N eligible item(s) (M on hand)" clause at the very end is gone (folded into this one spot).
    stone_short = totals["stone_needed"] > totals["rough_stone_on_hand"]
    items_short = (not stone_short) and (odds is not None) and (odds < 0.75)
    stone_hue = 33 if stone_short else 68
    items_hue = 33 if items_short else 68
    # SPACING FIX (2026-08-27), 7th attempt -- STRUCTURAL, not numeric, per the user: "Do you have a
    # creative solution to make this a lot easier?" after 6 straight rounds of guessing pixel widths
    # never landing right (flat rate, flat junction buffer, literal space, differentiated rate, back
    # to flat rate -- every one of them wrong in some direction because Gumps.AddLabel() gives no way
    # to measure real rendered text width, so ANY numeric estimate for where the NEXT label should
    # start is fundamentally a guess). Gumps.AddHtml() sidesteps that whole problem: it takes ONE
    # string with inline <BASEFONT COLOR=#RRGGBB> spans and lets the CLIENT lay the text out using
    # its own real font metrics -- no manual x-position math for anything INSIDE the line at all.
    # Only the OVERALL box width still needs a rough estimate (to avoid wrapping), and that failure
    # mode (wrap or a little trailing blank space) is far more forgiving than character-level overlap.
    #
    # hue->hex is a SEPARATE color system from AddLabel's UO hue table (AddHtml wants plain HTML hex,
    # not a hue ID) -- green (68)/red (33) CONFIRMED live against the user's own exact hex picks.
    #
    # PROSE COLOR FIX (2026-08-27), per the user's next live report: "make sure the black text is
    # using the green I gave you." Only the two highlighted spans had an explicit <BASEFONT COLOR>
    # tag -- the surrounding prose text had none at all, so AddHtml() fell back to some default
    # (reading as black/dark, not matching this gump's normal green). Every SEGMENT now gets its own
    # explicit <BASEFONT COLOR> tag, including the plain green prose -- built from the SAME (text,
    # hue) segment list this line used before switching to AddHtml, just joined into non-nested
    # <BASEFONT>...</BASEFONT> spans instead of positioned via manual AddLabel() x-offsets (avoids
    # relying on the client's html parser to correctly revert color after a NESTED tag closes, which
    # this minimal UO html dialect is not reliably documented to do).
    total_segments = [
        ("Total: {} applications, {} expected breaks (".format(
            totals["applications_needed"], totals["expected_breaks"]), 68),
        ("{} items on hand".format(totals["eligible_count"]), items_hue),
        ("), {} Rough Stone needed (".format(totals["stone_needed"]), 68),
        ("{} on hand".format(totals["rough_stone_on_hand"]), stone_hue),
        (").", 68),
    ]
    total_html = "".join(
        "<BASEFONT COLOR={}>{}</BASEFONT>".format(APPLY_PREVIEW_HTML_HUE_COLORS[hue], text)
        for text, hue in total_segments)
    # Plain-text twin (tags stripped) used ONLY for the gump's overall width estimate, via the same
    # line_pixel_width() every other line already uses -- the html box itself gets that same width,
    # generous room to avoid wrapping without needing to be pixel-exact.
    total_plain_text = (
        "Total: {applications} applications, {breaks} expected breaks "
        "({items} items on hand), {stone} Rough Stone needed ({on_hand} on hand)."
    ).format(
        applications=totals["applications_needed"], breaks=totals["expected_breaks"],
        items=totals["eligible_count"], stone=totals["stone_needed"],
        on_hand=totals["rough_stone_on_hand"])
    lines.append({"html": total_html, "width_text": total_plain_text})
    _fin_hue = 68 if totals["any_finished"] >= 0.75 else (33 if totals["any_finished"] < 0.4 else 43)
    lines.append((
        "Finished {}(s) expected: {:.1f} of the {} in play -- {:.0f}% chance that at least one survives every "
        "stat.".format(
            slot_def["label"].lower(), totals["finished"], totals["eligible_count"],
            totals["any_finished"] * 100.0), _fin_hue))
    lines.append((
        "Roughly {:.0f} minutes at this project's own throughput estimate.".format(
            totals["est_minutes"]), 68))

    # WORK FEWER ITEMS (2026-10-17)
    work_choices = work_fewer_choices(totals.get("finish_by_item") or [])
    _noun = "{}(s)".format(slot_def["label"].lower())
    if work_choices:
        lines.append(("Fewer {} can still finish one -- the likeliest first: {}.".format(
            _noun, "; ".join("{} for {:.0f}%".format(n, o * 100.0) for n, o, _s in work_choices)), 43))
    if odds is None:
        lines.append(("Odds of hitting every target: unavailable (no confirmed gain range).", 68))
    else:
        odds_hue = 68 if odds >= 0.75 else (33 if odds < 0.4 else 43)
        lines.append((
            "Odds this batch succeeds: {:.0f}% ({} trials).".format(
                odds * 100.0, APPLY_PREVIEW_MONTE_CARLO_TRIALS), odds_hue))

    if suggestion is not None:
        suggest_property_def, suggest_current, suggest_target, suggest_probability = suggestion
        lines.append((
            "Suggested: {} -> {} instead of {} (click Suggested below).".format(
                suggest_property_def["label"], suggest_target, suggest_current), 43))
        # NEW (2026-08-27), per the user: "When we're making a suggestion, show a new odds line
        # below the suggestion that reflects the suggestion output." suggest_probability is the
        # whole-batch probability AT suggest_target, already computed (and freshly re-checked) by
        # suggest_realistic_dump_target() itself -- not re-derived here.
        suggest_odds_hue = 68 if suggest_probability >= 0.75 else (33 if suggest_probability < 0.4 else 43)
        lines.append((
            "  Odds if suggested: {:.0f}% ({} trials).".format(
                suggest_probability * 100.0, SUGGEST_TARGET_TRIALS_PER_CANDIDATE), suggest_odds_hue))

    # Each entry in `lines` is a plain (text, hue) tuple (AddLabel), a list of (text, hue) segments
    # (AddLabel, left-to-right on one row -- no longer used by anything as of this fix, kept for any
    # future multi-color line that doesn't need HTML), or a dict with an "html"/"width_text" pair
    # (AddHtml -- see the Total line above). line_pixel_width() only needs a rough estimate for the
    # html case (sizing the box wide enough to avoid wrapping, not exact internal positioning).
    def line_pixel_width(entry):
        # THE PANEL FITS ITS TEXT (2026-10-17): the font's own widths, not a flat per-character guess
        if isinstance(entry, dict):
            return label_px(entry["width_text"]) + APPLY_PREVIEW_HTML_SLACK
        if isinstance(entry, list):
            return sum(label_px(text) for text, _hue in entry)
        return label_px(entry[0])

    width = APPLY_PREVIEW_MIN_WIDTH
    for entry in lines:
        width = max(width, APPLY_PREVIEW_SIDE_MARGIN + line_pixel_width(entry) + APPLY_PREVIEW_SIDE_MARGIN)

    # THE BUTTON ROW IS MEASURED TOO (2026-09-11). It used to be drawn at fixed x positions and
    # never sized against, which was survivable only while the labels were short -- renaming
    # "Accept" to "Apply to <slot>" made the row wider than anything the box had been sized for.
    # Folding it into the same max() means a long slot name widens the background instead of
    # escaping it.
    btn_cancel_text = "Cancel"
    btn_suggest_text = "Suggested"
    btn_apply_text = "Apply to %s" % slot_def["label"]
    _BTN_LABEL_GAP = 35        # button art + the gap before its own label (matches 20->55 below)
    _BTN_BLOCK_GAP = 20        # breathing room between two button blocks

    def _btn_block(text):
        return _BTN_LABEL_GAP + label_px(text)

    _row = APPLY_PREVIEW_SIDE_MARGIN + _btn_block(btn_cancel_text) + _BTN_BLOCK_GAP + _btn_block(btn_apply_text) \
           + APPLY_PREVIEW_SIDE_MARGIN
    if suggestion is not None:
        _row += _btn_block(btn_suggest_text) + _BTN_BLOCK_GAP
    width = max(width, _row)
    # Extra 2 rows of vertical room below the assembled lines: a blank gap + the button row.
    # WORK FEWER ITEMS: their buttons on a row of their own, above Cancel and Apply
    work_buttons = [(APPLY_PREVIEW_WORK_BASE + i, "Work {} -- {:.0f}%".format(n, o * 100.0),
                     "Start for real on only the {} {} likeliest to finish ({:.0f}% that at least one finishes every "
                     "stat): craft what they need and apply it at the targets above. The rest are left alone.".format(
                         n, _noun, o * 100.0))
                    for i, (n, o, _s) in enumerate(work_choices)]
    if work_buttons:
        width = max(width, APPLY_PREVIEW_SIDE_MARGIN + sum(_btn_block(label) + _BTN_BLOCK_GAP for _b, label, _t in
                                                           work_buttons) - _BTN_BLOCK_GAP + APPLY_PREVIEW_SIDE_MARGIN)
    height = 40 + (len(lines) + 2 + (1 if work_buttons else 0)) * APPLY_PREVIEW_ROW_HEIGHT

    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, width, height, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, width, height)

    y = 15
    for entry in lines:
        if isinstance(entry, dict):
            # background=False (2026-08-27) -- briefly tried True (a shaded panel behind the html
            # text, in place of the shadow/outline AddHtml doesn't expose), per the user, live: "nope"
            # -- rendered as a bright solid panel clashing with the rest of this gump's plain
            # transparent lines. Reverted; the box width itself (APPLY_PREVIEW_HTML_WIDTH_CHAR_PX)
            # was separately confirmed good in that same report ("the right border is good though").
            # THE SAME MARGINS THE WIDTH WAS COMPUTED FROM (2026-09-16). This was `width - 40`
            # while the width came from `20 + text + APPLY_PREVIEW_RIGHT_MARGIN` (=35), so the box
            # was ~5px narrower than the text it had to hold and the LONGEST line lost its last
            # word -- live: "90 Rough Stone needed (3385 on" wrapping mid-clause. Deriving both
            # from the same two constants is what stops it recurring the next time either moves.
            Gumps.AddHtml(gd, 20, y, width - 20 - APPLY_PREVIEW_SIDE_MARGIN + APPLY_PREVIEW_HTML_SLACK,
                          APPLY_PREVIEW_ROW_HEIGHT + 4, entry["html"], False, False)
        elif isinstance(entry, list):
            x = 20
            for text, hue in entry:
                Gumps.AddLabel(gd, x, y, hue, text)
                x += label_px(text)
        else:
            text, hue = entry
            Gumps.AddLabel(gd, 20, y, hue, text)
        y += APPLY_PREVIEW_ROW_HEIGHT
    y += 15
    if work_buttons:
        _wx = APPLY_PREVIEW_SIDE_MARGIN
        for _bid, _label, _tip in work_buttons:
            Gumps.AddButton(gd, _wx, y, 4005, 4007, _bid, 1, 0)
            Gumps.AddTooltip(gd, _tip)
            Gumps.AddLabel(gd, _wx + _BTN_LABEL_GAP, y + 2, 43, _label)
            _wx += _btn_block(_label) + _BTN_BLOCK_GAP
        y += APPLY_PREVIEW_ROW_HEIGHT

    # SAFE LEFT, COMMITTING RIGHT (2026-09-11), per the user -- the same convention they chose for
    # the rune screen ("Apply to * on the bottom right, and Back on the bottom left"), and it
    # matters more here because this is the click that actually spends runes. Every x is DERIVED
    # from the final width rather than hardcoded, so a long slot name moves the buttons instead of
    # pushing them off the background.
    Gumps.AddButton(gd, 20, y, 4005, 4007, APPLY_PREVIEW_CANCEL_BUTTON, 1, 0)
    Gumps.AddTooltip(gd, "Stop here. No runes are crafted and nothing is applied.")
    Gumps.AddLabel(gd, 55, y + 2, 68, btn_cancel_text)
    cancel_end = 20 + _btn_block(btn_cancel_text)

    apply_x = width - APPLY_PREVIEW_SIDE_MARGIN - _btn_block(btn_apply_text)
    apply_x = max(apply_x, cancel_end + _BTN_BLOCK_GAP)     # never overlap Cancel
    Gumps.AddButton(gd, apply_x, y, 4005, 4007, APPLY_PREVIEW_ACCEPT_BUTTON, 1, 0)
    Gumps.AddTooltip(gd, "Start for real: craft what the estimate above needs and apply it at "
                         "the targets you asked for. This is the click that spends Rough Stone "
                         "and can break items.")
    Gumps.AddLabel(gd, apply_x + 35, y + 2, 68, btn_apply_text)

    if suggestion is not None:
        # Centred in whatever gap the other two leave, then clamped to it -- an optional middle
        # path should never crowd either of the two that are always present.
        block = _btn_block(btn_suggest_text)
        mid = (cancel_end + apply_x) // 2 - block // 2
        mid = max(cancel_end + _BTN_BLOCK_GAP, min(mid, apply_x - _BTN_BLOCK_GAP - block))
        Gumps.AddButton(gd, mid, y, 4005, 4007, APPLY_PREVIEW_SUGGEST_BUTTON, 1, 0)
        # WHAT "Suggested" ACTUALLY OFFERS (2026-09-16), per the user. It only appears when the
        # odds line above says the batch you asked for is unlikely, and it is ONE alternative --
        # either a lower target, or the same target concentrated on fewer items. Worth spelling
        # out, because "Suggested" alone does not say what it would change.
        Gumps.AddTooltip(gd, "Take the alternative shown above instead of the target you typed. "
                             "It appears only when your batch is unlikely to succeed, and it is "
                             "either a lower target or the same target on fewer items -- "
                             "whichever the simulation says will actually finish. Cancel and "
                             "Accept both stay available.")
        Gumps.AddLabel(gd, mid + 35, y + 2, 43, btn_suggest_text)

    Gumps.SendGump(APPLY_PREVIEW_GUMP_ID, Player.Serial, 300, 300, gd.gumpDefinition, gd.gumpStrings)
    log("Reviewing apply preview -- click Accept to start, Cancel to abort...")

    if not Gumps.WaitForGump(APPLY_PREVIEW_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        log("Warning: apply-preview gump timed out with no response -- aborting.", 33)
        return False, requests, bases
    response = Gumps.GetGumpData(APPLY_PREVIEW_GUMP_ID)
    if response is None:
        log("Warning: apply-preview gump gave no response data -- aborting.", 33)
        return False, requests, bases

    _work_i = response.buttonid - APPLY_PREVIEW_WORK_BASE
    if 0 <= _work_i < len(work_choices):
        # STARTS THE CRAFT, like Apply (WORK FEWER ITEMS). No bases: they were picked from every item, and the chosen
        # few are already the concentration.
        _n, _odds, _serials = work_choices[_work_i]
        WORK_SET[0] = set(_serials)
        log("Working the {} {} likeliest to finish ({:.0f}% that at least one finishes every stat) -- starting.".format(
            _n, _noun, _odds * 100.0))
        return True, requests, None
    if suggestion is not None and response.buttonid == APPLY_PREVIEW_SUGGEST_BUTTON:
        # STARTS IMMEDIATELY (2026-08-27) -- was a recursive show_apply_preview(new_requests,
        # slot_def) call, re-showing a fresh preview for confirmation. Per the user, live: "I
        # noticed a weird loop where I select the suggested option, it keeps bringing up the final
        # gump again, often offering a new suggestion a little lower... we should just start the
        # crafting session when clicking the suggestion option." ROOT CAUSE of the loop itself: the
        # suggested target is found via a Monte Carlo search (SUGGEST_TARGET_TRIALS_PER_CANDIDATE,
        # just 30 trials per candidate) sitting right at the SELECT_BASES_CONFIDENCE boundary -- a
        # fresh 30-trial batch on a RE-preview can measure that same number a few points above or
        # below the bar purely from random sampling noise, so recursing could keep landing on a
        # slightly different (usually slightly lower) "suggestion" each time rather than ever
        # settling. Treating Suggested as an immediate Accept sidesteps that noise entirely instead
        # of trying to out-precision it -- the player already asked for a more realistic target;
        # there's no reason to re-litigate it through another round of the same noisy search.
        suggest_property_def, _suggest_current, suggest_target, _suggest_probability = suggestion
        new_requests = list(requests)
        for i, (property_def, _target_stat) in enumerate(new_requests):
            if property_def is suggest_property_def:
                new_requests[i] = (property_def, suggest_target)
                break
        log("Using suggested target: '{}' -> {} -- starting.".format(
            suggest_property_def["label"], suggest_target))
        return True, new_requests, bases

    if response.buttonid != APPLY_PREVIEW_ACCEPT_BUTTON:
        log("Apply cancelled from the preview screen.", 33)
        return False, requests, bases
    return True, requests, bases

def run_application_flow():
    """No travel step for applying itself -- unlike crafting, using a rune on an item has never
    been tied to being near the Scribe. Shows show_apply_preview() (expected applications/item
    breaks/Rough Stone usage, see its own docstring) once a slot is chosen, per the user
    (2026-08-27): "before starting the process, show the expected item breaks, the expected rough
    stone usage, and the odds of hitting target thresholds, then the player would click accept
    from that screen to start" -- stops here entirely on Cancel/timeout, before anything (Perk
    Deed, crafting) is spent. The preview may also return a DIFFERENT requests list than what was
    passed in, if the Suggested button was used to lower a dump stat's target, and/or a `bases`
    restriction (select_apply_bases() -- see show_apply_preview()'s own docstring for the
    concentrate-on-fewer-bases feature) -- this function always uses whatever show_apply_preview()
    returns, not its own original `requests`, and threads `bases`'s restrict_serials through to
    ONLY the matching dump-category request's own prepare_and_apply_one_stat() call. Uses a Perk
    Deed ONCE, up front for the whole batch, if the
    buff isn't already active -- from the backpack if one's already on hand, otherwise fetched from
    home storage (see use_perk_deed_if_needed()/withdraw_perk_deed_from_home_chest(), added
    2026-08-27 -- this docstring used to call that "a possible future addition, not built here";
    it's built now, per the user: "Instead of stopping when we're out of perk deed, go ahead and
    grab another from the chest they are stored in during combat dropoff and use it instead") --
    then runs prepare_and_apply_one_stat() once per requested (property_def, target_stat) pair from
    ask_apply_requests_and_slot(), per the
    user (2026-08-27): "I want to be able to request a craft that does multiple stats." Requested
    stats run SEQUENTIALLY (fully finish one, including its own bulk-craft, before starting the
    next) rather than interleaved -- simpler to reason about and verify correctly, and reaches the
    exact same end state either way (every requested stat's items end up at their own target).

    A failed REQUIRED stat HALTS the whole run (2026-09-04, per the user: "this should be a halting
    error. you can't skip required runes and move on to dump runes"). A failed DUMP stat still falls
    through to the next request, which is the case the original rule was actually about -- each
    requested stat has its own reagent/rune supply, so one running short need not block an
    otherwise-fine one. That reasoning holds for supply and breaks down on priority: continuing past
    a short required stat means spending the session on lower-priority work. See the loop below for
    the live incident (Mana Regen short at 38/167, followed immediately by 197 SDI applications)."""
    WORK_SET[0] = None                   # (2026-10-17) WORK FEWER ITEMS: every run starts with every item in play
    requests, slot_def = ask_apply_requests_and_slot()
    if slot_def is None:
        log("No valid request received -- stopping.", 33)
        return
    if not requests:
        log("No stats requested -- stopping.", 33)
        return

    _taker = call_hook("requests_taker")
    if _taker is not None:
        _taker(requests, slot_def)   # (2026-09-22) the chosen runes go to a script beside us, not into an apply here
        return
    accepted, requests, bases = show_apply_preview(requests, slot_def)
    if not accepted:
        log("Apply not started -- preview wasn't accepted.", 33)
        return

    # NO DEED CHECK HERE (2026-09-14), per the user: "there aren't really 2 modes anymore. apply
    # auto calls craft when there are no runes available yet. so check for deeds when we're actually
    # applying."
    #
    # A use_perk_deed_if_needed() gate used to sit on this line, right after the preview was
    # accepted and BEFORE any work began. That made a deed a precondition for CRAFTING, which has
    # never needed one: prepare_and_apply_one_stat() below is "the pre-flight-estimate + bulk-craft
    # + apply sequence", so the craft happens inside it and the old stop landed in front of work the
    # player was entitled to do with no deed at all.
    #
    # IT WAS ALSO REDUNDANT. run_slot_application() already gates the moment of application, and
    # better: it separates an Inscription skill shortfall (a hard stop no deed can fix) from a
    # missing deed (fetch one and re-loop, per the user on 2026-08-27 -- "We should be going to get
    # a new deed here instead of ending craft"). Deleting this one loses no protection; the item is
    # still never touched without the buff.
    # NO DEED CHECK AT ALL in this script. The perk lowers the chance of
    # breaking an item while APPLYING one, nothing is applied here, and
    # saying "no Perk Deed in the pack" before a run that could not use one
    # would be noise that teaches the wrong thing.

    restrict_property_def, restrict_serials = bases if bases is not None else (None, None)
    log("Applying {} requested stat(s) to '{}': {}.".format(
        len(requests), slot_def["label"], ", ".join(
            "{} -> {}".format(p["label"], ts) for p, ts in requests)))
    RUN_HALT[0] = None
    for property_def, target_stat in requests:
        log("=== {} (target {}) ===".format(property_def["label"], target_stat))
        this_restrict = restrict_serials if property_def is restrict_property_def else None
        stat_ok = prepare_and_store_one_stat(
            property_def, slot_def, target_stat, restrict_serials=this_restrict)
        if RUN_HALT[0] is not None:          # A STOP FOR THE WHOLE RUN
            log("HALTING the whole run: {} -- every remaining stat ({} more) would stop on the same thing. Nothing "
                "more is crafted.".format(RUN_HALT[0], len(requests) - requests.index((property_def, target_stat)) - 1),
                33)
            return False
        # A FAILED *REQUIRED* STAT HALTS THE WHOLE RUN (2026-09-04) -- per the user: "this should be
        # a halting error. you can't skip required runes and move on to dump runes." The return value
        # used to be discarded entirely, on the reasoning quoted in this function's own docstring
        # ("each requested stat uses its own separate reagent/rune supply, so there's no reason a
        # problem with one should block an otherwise-fine one"). That reasoning is about SUPPLY, and
        # it misses priority: a required stat is required, so quietly demoting it and spending the
        # session on a dump stat is the wrong outcome no matter how independent the supplies are.
        #
        # Confirmed live 2026-09-04: 'Mana Regen' (required) stopped at 38 of 167 runes, the run moved
        # straight on, and the character then performed 197 'Spell Damage Increase' applications --
        # SDI being one of the only two dump stats. Hours of throughput spent on the lowest-priority
        # stat immediately after the highest-priority one had failed, with nothing halting to say so.
        #
        # Dump stats keep the old behaviour and still fall through to the next request: skipping one
        # of those is exactly the "no reason to block an otherwise-fine stat" case the original
        # docstring described, and it is what the dump category means.
        if not stat_ok and property_def.get("category", "required") != "dump":
            log("HALTING: '{}' is a REQUIRED stat and its batch did not complete -- not moving on to "
                "the remaining {} requested stat(s). Fix whatever stopped it, then run Apply again; "
                "continuing here would spend the run on lower-priority stats while a required one is "
                "still short.".format(property_def["label"], len(requests) - requests.index(
                    (property_def, target_stat)) - 1), 33)
            return False
    log("Apply finished: every requested stat ran to completion.")
    return True   # a FINISHED craft (2026-09-24) -- the only exit that absorbs


def ensure_perk_tracker_running():
    """Launches PerkTracker.py alongside this script, same fire-and-forget convention as
    Omni_Engine.py's start_fishing_script()/start_daily_tame_script() -- no-ops if it's
    already running, so running this script twice (or the user already having it up) never
    spawns a duplicate."""
    if not Misc.ScriptStatus(PERK_TRACKER_SCRIPT_NAME):
        log("Starting Perk Tracker...")
        Misc.ScriptRun(PERK_TRACKER_SCRIPT_NAME)


# =============================================================================
# MAIN
# =============================================================================

PREFLIGHT_GUMP_ID = 0x52554E53   # "RUNS" -- CORRECTED 2026-09-14. This was 0x52554E50 ("RUNP"),
                                 # the SAME value as APPLY_PREVIEW_GUMP_ID, while its own comment
                                 # claimed to be distinct from every other gump in the project. It
                                 # was distinct from all of them except that one. Latent so far
                                 # because preflight runs at startup and the preview much later, but
                                 # a WaitForGump on either could read the other -- the exact trap
                                 # this project's "identify gumps precisely, never 'current'" rule
                                 # exists to prevent.
                                 # ORIGINAL NOTE: distinct from REQUEST ("RUNR"), APPLY ("RUNQ"),
                                 # MODE ("RUNM") and SLOT_GRID ("RUNG"), same ASCII-tag convention.
# THE SETUP GUMP HAS NO DEADLINE (2026-09-14), per the user: "get rid of the setup timer. you know
# how i feel about arbitrary timers." This was 30000ms, and its own comment argued against itself --
# "this is a human reading a problem and going to fix it, not a machine handshake". If that is true,
# no number is right. A player reading the rows, walking to stand at their chest, or checking a rune
# name in their book would lose the screen to "Setup timed out" -- on a first run, at the exact
# moment nothing is configured and they cannot tell what they just lost.
#
# show_setup_gump() now waits in slices and ends only on a real signal: a click, or Gumps.HasGump()
# reporting the window is gone because the player closed it. See its wait loop.

REQUIRED_ITEM_PROPS_WAIT_MS = 1000   # Same 1000ms every Items.WaitForProps() in this project
                                 # uses. Only spent on items whose GRAPHIC already matched and whose
                                 # Name has not loaded yet -- never once per pack item.
APOSTROPHE_VARIANTS = "".join(chr(cp) for cp in (0x2019, 0x2018, 0x02BC, 0x00B4, 0x0060))
                                 # Copied from TrashList.py's own normalizer, including its trick of
                                 # building from bare codepoints via chr() so the source stays ASCII
                                 # -- backslash-u escapes get mangled in transport. Neither name in
                                 # the table below has an apostrophe today, but the next required
                                 # item plausibly does ("Butcher's Hook", "Treasure Hunter's
                                 # Storage"), and a curly-vs-straight mismatch is a silent no-match.

REQUIRED_BACKPACK_ITEMS = (
    {"name": REAGENT_KEYS_NAME,
     "id": 0x18DE,          # hue 0x0021, blessed, 1 stone -- CONFIRMED via Enhanced Item Inspector.
                            # Hue is recorded but NOT matched: a dye would false-negative, and
                            # name + graphic are already two independent facts.
     # "display_hue" (2026-09-14) -- the SAME confirmed hue above, stored instead of only described,
     # so the setup gump can draw the icon in its real colour when the item is MISSING and there is
     # no live Item to read one from. Deliberately named for what it is: nothing matches on it, and
     # the not-matched reasoning directly above is unchanged.
     "display_hue": 0x0021,
     "why": "every craft withdraws its reagents from this key"},
    {"name": RUNECRAFTING_STORAGE_NAME,
     "id": 0x2254,          # The SPELLBOOK graphic -- which is why this cannot be matched on ItemID
                            # alone: a real spellbook in the pack has the same one.
     "display_hue": 0x0000,   # CONFIRMED via Enhanced Item Inspector: Color 0x0000, i.e. undyed.
     "why": "it holds the runes and the Rough Stone every craft consumes"},
)

RESOLVED_REQUIRED_ITEMS = {}     # name -> live serial, filled by the scan below. The script never
                                 # holds a serial it did not see in THIS player's backpack.


def find_required_backpack_item(spec):
    """(item, status) for one REQUIRED_BACKPACK_ITEMS entry: 'ok', 'renamed' or 'missing'.

    IDENTIFIED BY NAME + ItemID, never by serial (2026-09-13) -- serials are per-instance, so a
    hardcoded one only ever works for the character it was captured from.

    'renamed' is the useful third answer, and the user's own caveat: "It might have a slightly
    different name." The graphic matched but the name did not, so the caller can print what the item
    is ACTUALLY called instead of insisting it is absent.

    Scans the TOP LEVEL of the backpack only; the gump says "loose in your backpack" so that reads
    as an instruction rather than a mystery."""
    want = normalize_apostrophes((spec.get("name") or "").strip().lower())
    want_id = spec.get("id")
    graphic_hit = None
    try:
        for it in container_items(Player.Backpack):
            if want_id is not None and it.ItemID != want_id:
                continue          # cheap local field first -- no round trip, no props needed
            name = normalize_apostrophes((it.Name or "").strip().lower())
            if not name:
                Items.WaitForProps(it, REQUIRED_ITEM_PROPS_WAIT_MS)
                name = normalize_apostrophes((it.Name or "").strip().lower())
            if name == want:
                return it, "ok"
            if want_id is not None and graphic_hit is None:
                graphic_hit = it     # right graphic, wrong name -- remember for the 'renamed' report
    except Exception:
        pass
    if graphic_hit is not None:
        return graphic_hit, "renamed"
    _in_master = key_is_in_master(spec.get("name"))
    if _in_master:
        return None, "master"          # (2026-09-22) absorbed into Master Keys -- opened from its gump
    if _in_master is None:
        return None, "unchecked"       # (2026-09-24) the Master Keys window did not open -- it may well be in there
    return None, "missing"


def required_item_serial(name):
    """The live serial of a required item, resolved by NAME at runtime.

    The preflight fills the cache at startup, so this is normally a dict read. It re-scans on a miss
    rather than returning 0, which means the script also survives the item being swapped mid-run
    (a key re-secured, a storage replaced) without a restart."""
    serial = RESOLVED_REQUIRED_ITEMS.get(name)
    if serial:
        return serial
    for spec in REQUIRED_BACKPACK_ITEMS:
        if spec["name"] == name:
            it, status = find_required_backpack_item(spec)
            if status == "ok":
                RESOLVED_REQUIRED_ITEMS[name] = it.Serial
                return it.Serial
            break
    log("'{}' is not in the backpack -- cannot use it.".format(name), 33)
    return 0


def normalize_apostrophes(text):
    """Folds curly/typographic apostrophes to a plain ASCII "'" so a name match cannot fail on a
    character that looks identical. Same helper as TrashList.py's, copied rather than imported --
    this is a standalone hand-run script with no TrashList dependency."""
    if not text:
        return text
    for ch in APOSTROPHE_VARIANTS:
        text = text.replace(ch, "'")
    return text


def preflight_required_items():
    """True if everything the script needs is in the backpack; otherwise shows a gump and False.

    ADDED 2026-09-13, per the user: "auto detect things the script needs and give a warning or
    solution if they do not exist... show a gump advising they are needed in backpack and stop the
    script." A table rather than a pair of checks, because this is where that idea starts, not where
    it ends -- the next requirement is one more entry."""
    rows = setup_item_rows()
    # THE RUNE GATE IS GONE (2026-09-14): the destinations are marked (Optional) and are no longer
    # configurable from here, so there is nothing for the player to fill in and nothing to withhold
    # the script for. The rows themselves still decide whether the gump appears, which keeps an
    # unset Perk Deed chest discoverable -- and "Skip" remains the deliberate way past it.
    # BY INDEX, NEVER DESTRUCTURED (2026-09-16). This read six fields out of each row and crashed
    # the moment they became seven: "ValueError: too many values to unpack (expected 6)". I had
    # claimed the row tuple had one producer and one consumer, having checked the producer and
    # show_setup_gump() without ever searching for the rest. Indexing survives a widened row;
    # destructuring is what breaks.
    #
    # ONLY ROWS THIS GUMP CAN ACT ON GATE IT. row[5] is the action tuple (Target / Read), row[6]
    # the blocks-Continue flag. The other three rows -- Rune Chisel Target, Inscription, Better
    # Rune Crafting -- are pure status: Inscription cannot be raised from here and the buff lapses
    # constantly, so counting them would have opened the "first run setup" screen on EVERY run
    # forever. This keeps the original intent ("an unset Perk Deed chest stays discoverable")
    # without letting a status line hijack the gate.
    global SETUP_LAST_BLOCKERS
    SETUP_LAST_BLOCKERS = [(row[0], row[2]) for row in rows if (row[5] or row[6]) and not row[1]]
    if not SETUP_LAST_BLOCKERS:
        return True
    return show_setup_gump(rows)


SETUP_LAST_BLOCKERS = []   # [(name, detail)] from the last preflight -- the STOPPING line names them (2026-09-24)


# setup_runes_configured() LIVED HERE and is gone (2026-09-14). It existed for the brief window when
# the runebook destinations were editable in the gump and could therefore be left blank. They are now
# a printed convention marked (Optional), so there is nothing for a player to fail to fill in and
# nothing for the check to gate on.


SETUP_BTN_CLOSE = 0
SETUP_BTN_SAVE = 1
SETUP_BTN_CONTINUE = 2
SETUP_BTN_TARGET_CHEST = 10
SETUP_BTN_READ_RUNEBOOK = 11
SETUP_BTN_TOGGLE_CALCULATIONS = 12
SETUP_BTN_TOGGLE_UPDATES = 20         # THE SIGNED UPDATE: the Check for updates row's On/Off
# 13-19: the buttons of rows a script beside us adds (HOOKS["setup_rows"] / ["setup_button"]).
# The setup gump's only text entry, so id 1 and response.text[0]. Ids are their own namespace,
# separate from the SETUP_BTN_* numbers above.
SETUP_CHISEL_TARGET_ENTRY_ID = 1
SETUP_CHISEL_TARGET_LABEL = "Rune Chisel Target:"
# SETUP_ENTRY_* text-entry ids lived here and are gone (2026-09-14) -- the runebook fields they
# numbered became printed instructions, so there is nothing left to read back off the response.
# LAYOUT (2026-09-14). One margin, derived everywhere, so the panel cannot drift out of square:
# icons start at SETUP_MARGIN and the rightmost pixel of the Target and Skip labels lands on
# width - SETUP_MARGIN. Both were previously eyeballed, which is how "Target" ended up hanging off
# the edge.
SETUP_MARGIN = 24
SETUP_CHAR_PX = 8      # Approximate label width per character -- the same ~8px/char this project
                         # already uses to centre gump text (see the Tamer's own slot-grid title).
SETUP_LINE_H = 20      # One line of AddLabel text.
# SHORTENED FOR THE TWO-COLUMN GRID (2026-09-16). A column gives ~25 characters of text; these
# were 48 and 55. The "(Optional)" prefix and the "what it is for" clause both moved into the
# tooltips, which render outside the panel and cost no width -- per the user: "lean on button
# tooltips to give more details."
PERK_CHEST_ROW_LABEL = "Perk Deed Chest"
RUNEBOOK_ROW_LABEL = "Account Runebook"
INSCRIPTION_ROW_LABEL = "Inscription"
PERK_STATUS_ROW_LABEL = "Better Rune Crafting"
IBW_ROW_LABEL = "Infinite Backpack Weight"
UPDATES_ROW_LABEL = "Check for updates"
CHISEL_TARGET_ROW_LABEL = "Rune Chisel Target"
CALCULATIONS_ROW_LABEL = "Calculations"
# TOOLTIPS FOR THE SETUP ROWS (2026-09-16), per the user: "add some tooltips as appropriate."
#
# KEYED BY ROW LABEL, not carried in the row tuple. The tuple has one producer
# (setup_item_rows()) and one consumer (show_setup_gump()), so widening it would have worked --
# but this is display text and it belongs beside the display code, in one place a reader can
# scan. A row with no entry here simply gets no tooltip.
#
# THEY CAN AFFORD TO BE SENTENCES: a tooltip renders OUTSIDE the panel, so it costs no width and
# can say what the row's one-line detail cannot.
SETUP_ROW_TOOLTIPS = {
    REAGENT_KEYS_NAME:
        "Required. Reagents are consumed straight out of this key while crafting -- nothing is "
        "withdrawn, so it just has to be in your backpack and stocked.",
    RUNECRAFTING_STORAGE_NAME:
        "Required. Holds your Rough Stone, Blank Runes, finished runes and Rune Chisel charges. "
        "Runes and stone are used from it directly; the chisel is withdrawn and put back at the "
        "end of every run.",
    PERK_CHEST_ROW_LABEL:
        "Optional. Where spare Perk Deeds are kept, so a run can fetch one when the 10% "
        "less-break-chance buff expires mid-batch. Stand next to the chest and press Target. "
        "Saved by name and graphic, never by serial, so it survives being picked up and re-placed "
        "-- and pressing Target again always replaces whatever is set.",
    RUNEBOOK_ROW_LABEL:
        "Optional. Only needed for trips: Home to fetch a Perk Deed, Scribe to restock chisel "
        "charges. Open your Account Runebook to the page holding both runes and press Read. "
        "Pressing Read again re-reads whatever page is open, so you can change it any time.",
    INSCRIPTION_ROW_LABEL:
        "Applying a rune to an item needs %.0f+ Inscription. CRAFTING runes works at any skill, so "
        "a run below this still builds a supply -- it just stops before applying any of it. "
        "Nothing here can raise it; train the skill." % REQUIRED_INSCRIPTION_SKILL,
    PERK_STATUS_ROW_LABEL:
        "Applying also needs this buff active. It comes from a Perk Deed, and a run fetches and "
        "uses one by itself when the chest on the left is set -- so an expired buff is not "
        "something you have to fix here. Read at most once every few minutes, not live.",
    IBW_ROW_LABEL:
        "Optional. With it active nothing here watches your weight. Without it a run stays inside your "
        "weight limit: it stops crafting, or pulling items from a chest, before the next one would go "
        "over. Read at most once every few minutes, not live.",
    UPDATES_ROW_LABEL:
        "On: at each start the script looks for a newer version and, when there is one, shows what changed -- "
        "Update, Not now or Skip this version. It is taken only when its signature checks, and the old version is "
        "kept in the data folder. X turns it off, the arrow turns it on.",
    CALCULATIONS_ROW_LABEL:
        "On: a Calculate screen works out expected cost, item breaks and odds before anything "
        "is spent, and you accept from it. Off: the craft starts the moment you submit. Off "
        "also gives up the concentrate-on-fewer-bases improvement, which is worked out during "
        "that same calculation. The button shows what pressing it does: X turns it off, the "
        "arrow turns it on.",
    CHISEL_TARGET_ROW_LABEL:
        "How many Rune Chisel charges to keep in the storage on the left. When the stored total "
        "PLUS the chisel you are carrying falls below this, a run buys more from the Scribe. "
        "Saved as you type, on any button.",
}

# WHICH ROW SITS BESIDE WHICH (2026-09-16), per the user: "show them in the column adjacent to the
# relevant counterpart in the first column." Declarative so a pairing can be moved by editing one
# line. None means an empty right cell.
#
# TWO OF THESE ARE REAL RELATIONSHIPS: the chisel target is a setting OF the storage, and the buff
# is what the Perk Deed chest exists to supply. INSCRIPTION IS ARBITRARY -- it has no counterpart
# on the left and sits top-right because that cell was free.
SETUP_ROW_GRID = (
    (REAGENT_KEYS_NAME, INSCRIPTION_ROW_LABEL),
    (RUNECRAFTING_STORAGE_NAME, CHISEL_TARGET_ROW_LABEL),
    # THE PERK ROW IS GONE from this script. "Perk Deed Chest" and "Better
    # Rune Crafting" are both about the break-chance deed, which only does
    # anything when a rune is APPLIED to a piece of gear - and this script
    # never applies one. A chest to target and a buff timer to watch are
    # two things to get wrong in return for nothing.
    #
    # INFINITE BACKPACK WEIGHT STAYS, and is a different perk entirely: it
    # is what tells the crafter whether it has to keep the run inside your
    # weight limit, which matters as much here as anywhere. Its row is
    # further down, beside the updates one.
    (RUNEBOOK_ROW_LABEL, CALCULATIONS_ROW_LABEL),
    (IBW_ROW_LABEL, UPDATES_ROW_LABEL),
)
SETUP_COL_W = 340        # Per column. ~206px of that is text once the icon gutter and the action
                         # slot are taken, which is the ~25 characters the labels were cut to fit.
SETUP_COL_GAP = 16
SETUP_ROW_ICON_W = 52    # Icon gutter: text starts this far into a column.
SETUP_ROW_ACTION_W = 82  # Action slot: 34px button + a 6-character caption ("Target" / "Read").
                         # Also clears the 70px Rune Chisel Target field, which sits in the same
                         # slot on its own row.


def format_remaining_short(seconds):
    """"2d" / "3h" / "47m" / "12s" for a countdown -- largest useful unit only.

    Same shape as PerkTracker.py's format_perk_remaining() minus the colour, since a setup row
    takes its hue from the ok flag it already has. Duplicated rather than imported on this file's
    standing rule that it stays free-standing. The SECONDS branch is added deliberately: a buff
    with 40 seconds left reading "0m" is the one output that would mislead."""
    seconds = int(max(0, seconds))
    if seconds >= 86400:
        return "{}d".format(seconds // 86400)
    if seconds >= 3600:
        return "{}h".format(seconds // 3600)
    if seconds >= 60:
        return "{}m".format(seconds // 60)
    return "{}s".format(seconds)


def setup_item_rows():
    """[(label, ok, detail, item_id, hue, fixable)] for the three requirements that are really FOUND.

    THE HUE IS READ, NOT ASSUMED, whenever there is a live Item -- Item.Hue is the actual dye, which
    is what makes a found Reagent Key draw in its real colour. Only the MISSING case falls back to
    the spec's display_hue, itself a confirmed reading rather than a guess.

    Only these three can be verified: the two backpack items and the perk deed chest all either
    exist in the world right now or do not. The runebook destinations cannot be checked without
    actually travelling, so they are NOT in this list -- see show_setup_gump(), which renders them
    separately as configuration rather than as verified state."""
    # SEVEN-FIELD ROWS SINCE 2026-09-16: (label, ok, detail, icon_id, icon_hue, action, blocks).
    # `blocks` replaces a POSITIONAL gate -- show_setup_gump() used to read
    # `rows[:len(REQUIRED_BACKPACK_ITEMS)]`, so adding the three new rows below would have silently
    # changed which rows can stop Continue.
    #
    # DETAILS ARE SHORT FACTS NOW. A grid cell holds ~25 characters; the sentences moved to
    # SETUP_ROW_TOOLTIPS, which cost no width.
    rows = []
    for spec in REQUIRED_BACKPACK_ITEMS:
        it, status = find_required_backpack_item(spec)
        if status == "ok":
            RESOLVED_REQUIRED_ITEMS[spec["name"]] = it.Serial   # the ONLY place a serial is learned
            rows.append((spec["name"], True, "in your backpack", spec.get("id"),
                         getattr(it, "Hue", 0) or 0, False, True))
        elif status == "master":
            rows.append((spec["name"], True, "inside " + MASTER_KEYS_NAME, spec.get("id"),
                         spec.get("display_hue", 0), False, True))
        elif status == "renamed":
            # A LOOKALIKE, NOT SOMETHING TO RENAME (2026-09-16), per the user: "They aren't
            # renaming anything. they should ensure they have those items in their backpack."
            #
            # 0x2254 IS THE PLAIN SPELLBOOK GRAPHIC -- REQUIRED_BACKPACK_ITEMS says so itself
            # ("a real spellbook in the pack has the same one"). So the old wording told anyone
            # carrying an ordinary spellbook to rename it to "Runecrafting Storage", which is
            # destructive advice for a graphic collision. Report the collision instead.
            actual = (it.Name or "?").strip()
            rows.append((spec["name"], False, "not in your backpack", spec.get("id"),
                         spec.get("display_hue", 0), False, True))
            log("SETUP: '{}' is not in the backpack. A '{}' has the same graphic "
                "(ItemID 0x{:X}) and is not it -- {}."
                .format(spec["name"], actual, spec.get("id") or 0, spec["why"]), 33)
        elif status == "unchecked":
            # BETTER MESSAGING (2026-09-24 20:3x, owner). At 20:26:28 the first Master Keys read after a start got
            # no window, this row said "not in your backpack", and the read one second later listed the key.
            # Say what happened: not loose, and the place it lives could not be read this time.
            rows.append((spec["name"], False, "not loose; the Master Keys window did not open", spec.get("id"),
                         spec.get("display_hue", 0), False, True))
            log("SETUP: '{}' is not loose in the backpack, and the {} window did not open, so it could not be "
                "checked there -- it is probably inside; try again once the window answers.".format(
                    spec["name"], MASTER_KEYS_NAME), 33)
        else:
            rows.append((spec["name"], False, "not in your backpack", spec.get("id"),
                         spec.get("display_hue", 0), False, True))
            log("SETUP: '{}' is not in the backpack -- {}.".format(spec["name"], spec["why"]), 33)

    # NO PERK DEED CHEST ROW. Nothing in this script opens that chest, so
    # offering a cursor to target one would be asking for a setting it can
    # only ignore - and a red row for an unset chest would read as "you are
    # not ready" when you are.

    # THE RUNEBOOK IS A ROW LIKE ANY OTHER (2026-09-14). It was three lines of static instruction,
    # which could never turn green -- so the player had no way to tell whether the script agreed
    # with them. Read, verified and coloured like everything else now.
    _folder = rune_folder_name()
    _rune_action = (SETUP_BTN_READ_RUNEBOOK, "Read")
    if _folder:
        rows.append((RUNEBOOK_ROW_LABEL, True, "folder '{}'".format(_folder[:18]),
                     None, 0, _rune_action, False))
    else:
        rows.append((RUNEBOOK_ROW_LABEL, False, "not set -- press Read",
                     None, 0, _rune_action, False))

    # RUNE CHISEL TARGET, ITS OWN ROW (2026-09-16). It used to share the Runecrafting Storage row,
    # which only worked because the field sat ~430px from that row's label; in a 340px column they
    # collide. Its own cell also stops a SETTING hanging off an unrelated status line. No action
    # tuple -- show_setup_gump() draws the text entry in this row's action slot instead.
    rows.append((CHISEL_TARGET_ROW_LABEL, True, "buy more below this", None, 0, False, False))

    # INSCRIPTION (2026-09-16), per the user: "add an Inscription skill check." The one requirement
    # no button here can solve, hence no action -- its tooltip says so, and says that crafting
    # still works below the threshold while applying does not.
    try:
        _insc = float(Player.GetSkillValue("Inscription") or 0.0)
    except Exception:
        _insc = 0.0
    rows.append((INSCRIPTION_ROW_LABEL, _insc >= REQUIRED_INSCRIPTION_SKILL,
                 "{:.1f} -- enough".format(_insc) if _insc >= REQUIRED_INSCRIPTION_SKILL
                 else "{:.1f} of {:.0f}".format(_insc, REQUIRED_INSCRIPTION_SKILL),
                 None, 0, False, False))

    # BETTER RUNE CRAFTING REMAINING (2026-09-16), per the user: "show remaining time on Better
    # Rune Crafting if it's available."
    #
    # THROUGH THE THROTTLED CACHE, never read_active_perks() directly: refresh_gate_cache() already
    # rate-limits the real [perks round trip to PERKS_RECHECK_INTERVAL_SECONDS and remembers the
    # expiration, so the first draw pays one ~2s read and every redraw after an action is free.
    # NO "Better Rune Crafting" ROW EITHER, and no deed expiry read for it.
    # The buff lowers the chance of breaking an item while applying a rune;
    # nothing is applied here, so whether it is running changes nothing this
    # script does.
    #
    # refresh_gate_cache() IS STILL CALLED, once, right here - the Infinite
    # Backpack Weight row below reads the same throttled [perks result, and
    # it does need it. One ~2s read on the first draw, free on every redraw
    # after that.
    refresh_gate_cache()

    # INFINITE BACKPACK WEIGHT (2026-10-17) -- status only, see weight_room(). From the same throttled read as the row
    # above; never blocks a run.
    _ibw = _gate_cache.get("ibw_expiration")
    _ibw_left = None if _ibw is None else (_ibw - datetime.datetime.utcnow()).total_seconds()
    if not _gate_cache["perks_readable"]:
        rows.append((IBW_ROW_LABEL, False, "unreadable -- weight watched", None, 0, False, False))
    elif _ibw_left is None or _ibw_left <= 0:
        rows.append((IBW_ROW_LABEL, False, "off -- weight watched", None, 0, False, False))
    else:
        rows.append((IBW_ROW_LABEL, True, "{} remaining".format(format_remaining_short(_ibw_left)),
                     None, 0, False, False))

    # CALCULATIONS (2026-09-17), per the user: "Just show Calculations in red or green, and use
    # a button to toggle it. Cooler if we can use the X to turn it off, and the right facing
    # arrow to turn it on, show a different button depending on the current status."
    #
    # A ROW LIKE ANY OTHER, so `ok` does the colouring: show_setup_gump() already renders every
    # row as `68 if ok else 33`, which is green-when-on / red-when-off with no new code. It
    # fills SETUP_ROW_GRID's one free cell, bottom right, where the user pointed.
    #
    # THE BUTTON SAYS WHICH WAY THE PRESS GOES, which is the point of showing two different
    # ones: X (4017/4018) while calculations are ON means "press to turn off", and the forward
    # arrow (4005/4007) while they are OFF means "press to turn on". Four-field action, read by
    # index in the renderer, so every two-field action above is unaffected.
    _calc_on = calculations_enabled()
    _calc_action = ((SETUP_BTN_TOGGLE_CALCULATIONS, "Off", 4017, 4018) if _calc_on
                    else (SETUP_BTN_TOGGLE_CALCULATIONS, "On", 4005, 4007))
    rows.append((CALCULATIONS_ROW_LABEL, _calc_on,
                 "cost and odds first" if _calc_on else "craft starts at once",
                 None, 0, _calc_action, False))
    # CHECK FOR UPDATES (2026-10-17, THE SIGNED UPDATE): Calculations' own four-field toggle
    #
    # FORK. Shown as off and not offered as a toggle: an update would write
    # upstream's file over this one and take the fork's changes with it. The
    # row keeps its place in the grid - SETUP_ROW_GRID is read by label, so
    # dropping a row is a layout change and a bigger risk than a row that
    # simply has nothing to press.
    rows.append((UPDATES_ROW_LABEL, False, "off -- disabled in this fork",
                 None, 0, None, False))
    call_hook("setup_rows", rows)   # rows a script beside us adds (2026-10-17, THE HOOKS)
    return rows


# THE BOOK'S OWN FURNITURE (2026-09-14). Captured live as a bogus folder path -- "New Rune >
# New Runebook > Organize" -- because these captions reach the same line list the breadcrumb is read
# from. A closed set of strings the gump actually shows, not a guess about where they sit.
AR_CHROME_LINES = ("account runebook", "new rune", "new runebook", "organize")

AR_FOLDER_PATH_SEP = " > "     # How the stored runebook scan writes a nested path, e.g.
                                 # "[Ilshenar > Cities > Ancient Citadel]". Reused here so a saved
                                 # path reads the same way a dump does.
# AR_MAX_FOLDER_PROBES lived here and is gone (2026-09-14) -- it bounded a whole-book crawl that no
# longer happens. The open gump shows its own breadcrumb, so there is nothing to walk.


def _view_has_both_runes(destinations):
    """True when this view's destinations include a rune matching each required name.

    SUBSTRING, NOT EQUALITY -- rune names carry a facet suffix. The stored scan
    (OmniData/ScratchTest_RunebookScan.txt) records this very book's entries as
    "HOME (Malas)" and "Scribe (Trammel)", so an exact match would fail on the book this was
    written against. ar_find() already resolves names exact-first-then-substring, which is why the
    old hardcoded 'HOME' ever worked; this matches it rather than inventing a stricter rule."""
    lowered = [((d.get("name") or "").strip().lower()) for d in destinations.values()]
    return all(any(want.lower() in name for name in lowered)
               for want in (SETUP_HOME_RUNE, SETUP_SCRIBE_RUNE))


def runebook_open_folder_path():
    """The FULL path of the folder currently open, as a list. [] at the top level.

    THE GUMP ALREADY SHOWS THE WHOLE BREADCRUMB (2026-09-14), per the user: "we shouldn't have to
    read the whole runebook if they are open to the page already. it shows every subfolder." Open
    inside Chores > Minoc, the book reads:

        Account Runebook        <- title
        Chores                  <- ancestor
        Minoc                   <- the open folder
        10. 10 (Trammel)  (2420, 516, 0)
        Page 2/2

    So the path is every line between the title and the first numbered entry. Nothing between them
    means the top level -- [] -- which ar_go_folders([]) already treats as "stay at the root", so
    the empty case needs no special handling.

    TWO EARLIER ATTEMPTS GOT THIS WRONG in opposite directions: one kept only the LAST header line
    and lost the ancestors, so it could not navigate back into a nested folder; the other crawled
    the entire book breadth-first to rediscover what the open gump was already displaying.

    CHROME IS EXCLUDED BY NAME (2026-09-14). An earlier version assumed the lines ran
    title -> folders -> entries and simply broke at the first numbered entry. Live, that captured
    the book's own footer buttons as a path:

        Runebook folder set to 'New Rune > New Runebook > Organize'
        Warning: Account Runebook folder 'New Rune' not found on any page.

    So the ordering assumption was wrong. AR_CHROME_LINES is the closed set of captions the book
    itself shows -- the title and the three footer buttons -- read off the gump rather than inferred
    from layout, plus the "Page n/m" marker. None of them can ever be a folder.

    Markup lines and coordinate lines are skipped exactly as ar_parse_page() skips them."""
    header = []
    for raw in (ar_gump_lines(AR_GUMPID) or []):
        text = (raw or "").strip()
        if not text or text.startswith("<"):
            continue
        if re.match(r"^\d+\.", text):
            break                     # entries have begun; everything before them is the header
        if re.match(r"^\(\s*[-+]?\d", text):
            continue
        low = text.lower()
        if low in AR_CHROME_LINES or re.match(r"^page\s+\d+\s*/\s*\d+$", low):
            continue                  # the book's own furniture, never a folder
        header.append(text)
    return header


def read_open_runebook_folder():
    """Record the open folder's path once both required runes are found in it. True on success.

    FORK -- EVERY PAGE OF THE OPEN FOLDER, not only the page on screen.

    Upstream reads the visible page and fails if both runes are not on it,
    and that is a deliberate choice of theirs rather than an oversight; its
    own comment says so: "let's just fail the test if it's not there, i
    think that's simpler. i don't wanna start turning pages in another
    players runebook for no reason."

    The objection was about turning pages in somebody else's book to answer
    a question they were already answering by having it open. This fork is
    for one player's own book, where two runes in one folder but on
    different pages is ordinary - a folder holds nine entries a page - and
    failing on it means setup cannot be completed at all.

    THE VIEW IS PUT BACK. ar_iter_pages() rewinds to page 1 and walks
    forward, so it moves the player off whatever they had open; the page
    they were on is noted first and returned to afterwards, whether or not
    the read worked. That answers the half of upstream's objection that
    still stands.

    THE FOLDER IS STILL THE ONE THEY OPENED. This walks pages, never
    folders: the breadcrumb is read before the first page turn and the
    search does not descend. A book-wide crawl is what upstream refused and
    this is not one.
    """
    if not Gumps.HasGump(AR_GUMPID):
        log("Open your Account Runebook to the folder holding your '{}' and '{}' runes, then "
            "press Read.".format(SETUP_HOME_RUNE, SETUP_SCRIBE_RUNE), 33)
        return False

    # BEFORE ANY PAGE TURN. The breadcrumb is the same on every page of a
    # folder, but reading it first means the capture cannot be affected by
    # anything the walk does.
    path = runebook_open_folder_path()
    started_on, _total = ar_page_info()

    found = {}
    pages_read = 0
    try:
        for _page, _folders, destinations in ar_iter_pages():
            pages_read += 1
            found.update(destinations)
    finally:
        # ALWAYS, even if the walk threw: leaving someone's book three pages
        # from where they left it is the rudeness upstream was objecting to.
        if started_on > 1:
            ar_goto_page(started_on)

    if not _view_has_both_runes(found):
        names = sorted((d.get("name") or "").strip() for d in found.values())
        log("'{}' has {} across {} page(s) -- both '{}' and '{}' need to be somewhere in the "
            "folder you have open. Open the right folder (or rename your runes to match), then "
            "press Read."
            .format(AR_FOLDER_PATH_SEP.join(path) or "(top level)",
                    ", ".join(n for n in names if n) or "no runes",
                    pages_read, SETUP_HOME_RUNE, SETUP_SCRIBE_RUNE), 33)
        return False

    setup_set(SETUP_RUNE_FOLDER_KEY, AR_FOLDER_PATH_SEP.join(path))
    if save_setup():
        log("Runebook folder set to '{}' -- found '{}' and '{}' across {} page(s)."
            .format(AR_FOLDER_PATH_SEP.join(path) or "(top level)",
                    SETUP_HOME_RUNE, SETUP_SCRIBE_RUNE, pages_read))
        if path:
            # THE RAW LINES, WHENEVER A PATH WAS CAPTURED. A wrong breadcrumb previously surfaced
            # minutes later as "folder not found on any page" during travel; this makes a bad read
            # visible the moment it happens.
            log("(read from: {})".format(
                " | ".join(l.strip() for l in (ar_gump_lines(AR_GUMPID) or []) if l and l.strip())),
                68)
    return True


def capture_perk_chest():
    """DISARMED in this script: there is no Perk Deed Chest row to press it.

    Left as a stub rather than deleted so a diff against the fork still
    lines up. Nothing reaches it - the row that offered the cursor is gone -
    and if something ever did, saying so beats quietly opening a cursor the
    player did not ask for.
    """
    log("This script never opens the Perk Deed chest, so there is nothing "
        "to target. Use OmniRuneCraftFork.py for applying runes.", 33)
    return False


def show_setup_gump(rows):
    """The first-run setup screen. Returns True only if the player chose to continue.

    Per the user: "Shows the requirements in red if they are missing ... then for deed chest and
    runes, give a button that solves it, then turn the text green. Show relevant icons where
    possible." Red 33 / green 68 are this file's own confirmed pair -- no unverified hue is used,
    because an unverified one can render invisibly and a status screen that lies is worse than none.

    TWO KINDS OF ROW, LABELLED DIFFERENTLY ON PURPOSE. The items above are FOUND or not. The two
    runebook destinations cannot be verified without travelling, so they are shown as what WILL BE
    USED, not as a passed check."""
    # TWO PAIRED COLUMNS (2026-09-16). Seven rows in one column would stand 500px tall; laid out
    # per SETUP_ROW_GRID they fit four rows and the panel is SHORTER than the old four-row one.
    width = SETUP_MARGIN * 2 + SETUP_COL_W * 2 + SETUP_COL_GAP
    col_x = (SETUP_MARGIN, SETUP_MARGIN + SETUP_COL_W + SETUP_COL_GAP)
    row_h = 64            # More air between rows (2026-09-14), per the user.
    top = 52
    # len(SETUP_ROW_GRID), NOT len(grid) (2026-09-16) -- the same number, and now the only one
    # available here: `grid` moved into the redraw loop so Target and Read actually change what
    # is drawn. One grid entry is built per SETUP_ROW_GRID entry unconditionally, so the panel
    # height is unchanged; an empty right cell still occupies its row.
    # height moves into the redraw loop (2026-09-22): a grid row nobody produced is dropped there, so the
    # panel is sized from the rows actually drawn.
    # EVERY ROW ACTION SITS AT THE SAME OFFSET INSIDE ITS OWN COLUMN, so the two columns' buttons
    # line up with each other as well as down the page. Derived, not hardcoded, for the same reason
    # the single-column version derived it: the captions decide the width.
    def _action_x(which_col):
        return col_x[which_col] + SETUP_COL_W - SETUP_ROW_ACTION_W
    # The footer's Continue is right-aligned on the whole panel, so its own caption sets its x.
    continue_x = width - SETUP_MARGIN - (len("Continue") * SETUP_CHAR_PX) - 34

    while True:
        # RE-DERIVED EVERY REDRAW (2026-09-16), per the user: "when we click the target or read
        # buttons and they acquire their new data, they don't update the text to green like they
        # should. i had to hit continue and then come back to settings for that update."
        #
        # THIS WAS THE BUG, not the redraw. These two lines used to sit ABOVE the loop, so every
        # redraw re-rendered the rows as they were when the screen OPENED. Both handlers below
        # already do `rows = setup_item_rows()` -- correctly -- but nothing downstream read
        # `rows` again, so the rebind was dead and the row stayed red until the caller
        # (preflight_required_items) rebuilt the rows on re-entry. That is exactly why leaving
        # and coming back "fixed" it.
        #
        # Cheap: setup_item_rows() is the same work the screen already does once per press, and
        # this runs only when a button was clicked, never in a poll.
        by_label = dict((r[0], r) for r in rows)
        grid = [(by_label.get(_l), by_label.get(_r) if _r else None)
                for _l, _r in SETUP_ROW_GRID]
        grid = [pair for pair in grid if pair[0] is not None or pair[1] is not None]   # a row nobody produced takes no space
        height = top + len(grid) * row_h + 52
        gd = Gumps.CreateGump(movable=True)
        Gumps.AddPage(gd, 0)
        Gumps.AddBackground(gd, 0, 0, width, height, 30546)
        Gumps.AddAlphaRegion(gd, 0, 0, width, height)
        Gumps.AddLabel(gd, 20, 15, 68, "Rune Crafting -- first run setup")

        y = top
        for pair in grid:
            for which, row in enumerate(pair):
                if row is None:
                    continue   # an empty right cell -- SETUP_ROW_GRID says so on purpose
                label, ok, detail, icon_id, icon_hue, action, _blocks = row
                _cx = col_x[which]
                _hue = 68 if ok else 33
                # THE SAME TOOLTIP ON EVERY PART OF THE ROW, so hovering anywhere in the cell
                # explains it. AddTooltip binds to the element added immediately before it, which
                # is why each call sits directly under its own Add.
                _tip = SETUP_ROW_TOOLTIPS.get(label)
                if icon_id:
                    Gumps.AddItem(gd, _cx, y + 2, icon_id, icon_hue)
                    if _tip:
                        Gumps.AddTooltip(gd, _tip)
                Gumps.AddLabel(gd, _cx + SETUP_ROW_ICON_W, y, _hue, label)
                if _tip:
                    Gumps.AddTooltip(gd, _tip)
                Gumps.AddLabel(gd, _cx + SETUP_ROW_ICON_W, y + 20, _hue, detail)
                if action:
                    # BY INDEX, NOT DESTRUCTURED (2026-09-17). An action may now be either
                    # (id, text) -- Target, Read, everything that was here -- or
                    # (id, text, art_up, art_down), which is how the Calculations toggle shows
                    # an X when it will turn something off and an arrow when it will turn it
                    # on. Destructuring would have made adding the art a breaking change to
                    # every existing row.
                    _act_id, _act_text = action[0], action[1]
                    _art_up, _art_down = ((action[2], action[3]) if len(action) >= 4
                                          else (4005, 4007))
                    Gumps.AddButton(gd, _action_x(which), y + 6, _art_up, _art_down,
                                    _act_id, 1, 0)
                    if _tip:
                        Gumps.AddTooltip(gd, _tip)
                    Gumps.AddLabel(gd, _action_x(which) + 34, y + 8, 68, _act_text)
                # THE CHISEL FIELD LIVES IN ITS OWN ROW'S ACTION SLOT (2026-09-16) -- that row
                # carries no action tuple, so the slot is free and the field lines up with the
                # Target/Read buttons in the other column.
                #
                # THE BACKING TILE IS REQUIRED, not decoration -- this file already established
                # that "an AddTextEntry field has no background of its own" (see APPLY_REQUEST_
                # ENTRY_BACKING_TEXTURE), and without it the box is invisible.
                if label == CHISEL_TARGET_ROW_LABEL:
                    Gumps.AddImageTiled(gd, _action_x(which), y + 6, 70, 20,
                                        APPLY_REQUEST_ENTRY_BACKING_TEXTURE)
                    Gumps.AddTextEntry(gd, _action_x(which), y + 6, 70, 20, 68,
                                       SETUP_CHISEL_TARGET_ENTRY_ID,
                                       str(chisel_charge_target()))
                    if _tip:
                        Gumps.AddTooltip(gd, _tip)
            y += row_h

        # CLOSE FAR LEFT, SKIP IN THE ACTION COLUMN so it lines up with Target and Read above it.
        #
        # "SAVE AND RE-CHECK" IS GONE (2026-09-14), per the user: "it doesn't functionally do
        # anything." Correct -- every action already re-reads the rows and redraws, so the button
        # only ever repeated work that had just happened.
        _btn_y = height - 38
        # BACK ARROW ON CLOSE (2026-09-16), per the user: "make it the same one you use for
        # settings later." 4014/4015 is this file's reversed pair -- the Settings button and the
        # slot screen's "Back" both use it -- against 4005/4007 for forward/act. Close is a way
        # out, so the arrows now carry the direction. Both pairs are in the verified set; an
        # unverified art draws nothing at all, with no error, so none is introduced here.
        Gumps.AddButton(gd, SETUP_MARGIN, _btn_y, 4014, 4015, SETUP_BTN_CLOSE, 1, 0)
        Gumps.AddTooltip(gd, "Close without running. Anything you set or typed is already saved.")
        Gumps.AddLabel(gd, SETUP_MARGIN + 34, _btn_y + 2, 68, "Close")

        # "Continue", NOT "Skip" (2026-09-16), per the user. The id was always
        # SETUP_BTN_CONTINUE: this button RUNS the script, re-checking the two mandatory backpack
        # items and refusing if either is missing. "Skip" read as "bypass the setup", which is the
        # one thing it does not do.
        Gumps.AddButton(gd, continue_x, _btn_y, 4005, 4007, SETUP_BTN_CONTINUE, 1, 0)
        Gumps.AddTooltip(gd, "Start the run. The two backpack items above are required; "
                             "everything else is optional and only affects trips.")
        Gumps.AddLabel(gd, continue_x + 34, _btn_y + 2, 68, "Continue")

        Gumps.SendGump(PREFLIGHT_GUMP_ID, Player.Serial, 200, 200,
                       gd.gumpDefinition, gd.gumpStrings)
        # ONE LONG WAIT, the same REQUEST_GUMP_WAIT_MS (24 hours) every other screen in this file
        # uses. See that constant's own comment for why a finite number is unavoidable:
        # Gumps.WaitForGump() requires SOME Int32 millisecond delay and there is no "wait forever"
        # sentinel, so a day is this file's established way of saying "as long as the player needs".
        #
        # A HasGump() POLL LOOP WAS TRIED HERE AND BROKE THE TARGET BUTTON (2026-09-14). Clicking a
        # button CLOSES the gump, so between the click and WaitForGump returning the response there
        # is a window where HasGump() already reads False. The loop took that for "the player closed
        # it" and returned before GetGumpData() ever ran, so the cursor never appeared. A single
        # long wait has no such window.
        if not Gumps.WaitForGump(PREFLIGHT_GUMP_ID, REQUEST_GUMP_WAIT_MS):
            log("Setup closed.")
            return False
        response = Gumps.GetGumpData(PREFLIGHT_GUMP_ID)
        if response is None:
            return False
        # SAVED ON EVERY RESPONSE (2026-09-15), not just on the way out: Target and Read both
        # rebuild this gump and loop, so a value typed before pressing either would be thrown
        # away if it were only read at Continue. Same reason the apply screen's thresholds are
        # sticky.
        #
        # A BAD VALUE IS IGNORED, NOT SAVED. Writing 0 for unparseable input would silently
        # disable restocking -- a setting that quietly means "never" is worse than one that
        # refused and said so.
        _entry_text = list(response.text or [])
        if len(_entry_text) >= SETUP_CHISEL_TARGET_ENTRY_ID:
            _raw = (_entry_text[SETUP_CHISEL_TARGET_ENTRY_ID - 1] or "").strip()
            if _raw:
                try:
                    _wanted = int(_raw.replace(",", ""))
                except ValueError:
                    _wanted = None
                if _wanted is None or _wanted < 0:
                    log("'{}' is not a usable {} -- keeping {}.".format(
                        _raw, SETUP_CHISEL_TARGET_LABEL.rstrip(":"),
                        chisel_charge_target()), 33)
                elif _wanted != chisel_charge_target():
                    # save_setup() WAS MISSING (2026-09-16), per the user: "what button do we
                    # click to change the rune chisel target permanently? Continue ain't doing it
                    # like I'd expect." No button did -- setup_set() only writes the in-memory
                    # cache ("Call save_setup() to persist", per its own docstring), so the value
                    # held for the current run and was gone on restart while this line claimed it
                    # had stuck. The chest and the runebook survive because their own handlers
                    # save; a field read inline here had nothing to do it.
                    #
                    # ON ANY BUTTON, deliberately: the read above already runs on every response
                    # so Target and Read cannot discard a typed value, and Close's own tooltip
                    # promises "anything you set or typed is already saved".
                    setup_set(SETUP_KEY_CHISEL_TARGET, str(_wanted))
                    if save_setup():
                        log("{} set to {} and saved.".format(
                            SETUP_CHISEL_TARGET_LABEL.rstrip(":"), _wanted))
                    else:
                        # save_setup() logs its own reason. Do not claim a write that failed --
                        # the value still applies to THIS run, which is worth saying separately.
                        log("{} is {} for this run, but it could not be saved -- it will be back "
                            "to {} next time.".format(
                                SETUP_CHISEL_TARGET_LABEL.rstrip(":"), _wanted,
                                CHISEL_CHARGE_TARGET_DEFAULT), 33)
        clicked = response.buttonid

        if clicked == SETUP_BTN_TARGET_CHEST:
            capture_perk_chest()
            rows = setup_item_rows()
            continue

        if clicked == SETUP_BTN_READ_RUNEBOOK:
            read_open_runebook_folder()
            rows = setup_item_rows()
            continue

        if clicked == SETUP_BTN_TOGGLE_CALCULATIONS:
            # SAVES IMMEDIATELY, for the reason the chisel field documents above: setup_set()
            # only writes the in-memory cache, so without save_setup() the toggle would hold
            # for this run and silently revert on restart while the screen claimed otherwise.
            _now_on = not calculations_enabled()
            setup_set(SETUP_KEY_CALCULATIONS, "1" if _now_on else "0")
            if save_setup():
                log("Calculations {}.".format("on" if _now_on else "off"),
                    68 if _now_on else 33)
            else:
                # Do not claim a write that failed -- say what actually holds.
                log("Calculations {} for this run, but the setting could not be saved."
                    .format("on" if _now_on else "off"), 33)
            rows = setup_item_rows()
            continue

        if clicked == SETUP_BTN_TOGGLE_UPDATES:
            # FORK. The row no longer renders this button, so this is only
            # reachable from a stale gump still on screen from before the
            # fork was loaded. Say why and change nothing.
            log("Updates are disabled in this fork: taking one would write "
                "the upstream file over it and undo the local changes. "
                "Use omnirunecraft.py for the upstream version.", 33)
            continue      # NOT return: this is the setup screen's own loop,
                          # and returning would close the screen under them.

            _now_on = setup_get(SETUP_KEY_UPDATES, "0") != "1"
            setup_set(SETUP_KEY_UPDATES, "1" if _now_on else "0")
            if save_setup():
                log("Check for updates {}.".format("on -- at the next start" if _now_on else "off"), 68 if _now_on else 33)
            else:
                log("Check for updates {} for this run, but the setting could not be saved."
                    .format("on" if _now_on else "off"), 33)
            rows = setup_item_rows()
            continue
        if call_hook("setup_button", clicked):   # a press on a row a script beside us added (THE HOOKS)
            rows = setup_item_rows()
            continue
        if clicked == SETUP_BTN_CONTINUE:
            # SKIP IS THE ONLY WAY FORWARD NOW that "Save and re-check" is gone -- every action
            # already re-reads and redraws, so there was nothing for Save to do.
            #
            # THE TWO BACKPACK ITEMS STAY MANDATORY. Everything else is optional per player: someone
            # who only crafts never touches the perk-deed or Scribe travel paths and should not be
            # blocked by requirements those paths need.
            rows = setup_item_rows()
            # BY FLAG, NOT BY POSITION (2026-09-16). This read the first len(REQUIRED_BACKPACK_
            # ITEMS) rows, so the three rows added for the two-column grid would have silently
            # changed the gate -- a new row landing in the first two would start blocking Continue
            # and a real backpack item pushed past them would stop. The `blocks` field says it
            # outright, and only the two backpack items set it.
            blockers = ["'{}' {}".format(r[0], r[2]) for r in rows if r[6] and not r[1]]
            if blockers:
                log("Still needed: {}. The script cannot run without those."
                    .format("; ".join(blockers)), 33)
                continue
            return True

        return False


# =============================================================================
# THE SIGNED UPDATE (owner, 2026-10-17: "add the updater" -- the shared panner's, ported). At start, with Check for
# updates on, the newest release of UPDATE_REPO is read from GitHub. One newer than SCRIPT_VERSION, not skipped and not
# put off with "Not now" in the last UPDATE_LATER_S, is shown in a window of its own -- what changed, and Update / Not now
# / Skip this version -- before any other screen: this script is run by a player sitting at it, so the window waits for
# the answer. Update downloads the release's script and its signature and takes it only when the signature checks
# against UPDATE_PUBLIC_KEY (the author signs each release with a key that never leaves the author's machine) and it
# compiles. The old file is kept in the data folder, the new one goes in its place; RazorEnhanced's Auto Script Reload
# starts the new one, and without it the run stops and says what to press -- NEVER A SCRIPT THAT STARTS ITSELF (owner:
# "having a script start itself is a recipe for disaster"). No network, a refused signature or any error: the script
# runs as it is. Lessons from the panner's releases: Docs/SHARED_SCRIPTS_LESSONS.md.
# =============================================================================
UPDATE_REPO = "Omniwrath/beyond-sosaria-runecrafting"
UPDATE_FILE = "Omni_Runecrafting.py"
UPDATE_TIMEOUT_MS = 10000
UPDATE_GUMP_ID = 0x52554E55     # "RUNU"
UPDATE_BUTTONS = (21, 22, 23)   # (update, not now, skip)
UPDATE_LATER_S = 6 * 3600       # "Not now" is quiet this long; a newer release than the one put off is offered at once
UPDATE_RELOAD_WAIT_S = 10
UPDATE_WIDTH, UPDATE_NOTES_HEIGHT = 560, 300
UPDATE_CHAR_PX = 8
VERSION_RE = re.compile(r'^SCRIPT_VERSION = "([0-9.]+)"', re.M)
UPDATE_PUBLIC_KEY = (
    "<RSAKeyValue><Modulus>pNV0Isi3q6bD4XcPuv74fr6NPcoyyFbZU3XErPsuT4RrQ0xKCDZpe6VgruMJCldefm6ZU5ZQDzEsRV"
    "CRnhQzHFnOWWppNfoN2PWRVJPayKmDqpGSapA4MwjAI5RuPsBzOTT5GfqdEH1vpJNSjqQbYyRbyPDbJCkAxzAC1pmxwiFMRA5QCm"
    "i3iJPO0boyKepbzCJEYaXXd92CVixwvo+fPmYrMfe2bX2i87w9DBspCi7fevh0ogViniDZ8CZEPZ0aEAB8UsVJlSbRDzThKxJzN0"
    "J/514mMb0qGi5FWqMZt/ciFInp8A9Xsb7YYPqzy1mau050pzZAdyRHxLf3aIuoD9abbWERZPjlFlo1WOPJnB9q4kRG+HeT0hoBuU"
    "eGawyQpOO3g1PiFwuqCWXhB9Ci3jbGIR0qLRZViJM1lzacVEaL/N0rsUbdn2n0kPpv67k0Wevfrj5hknKiUucpOLxv33nlW7ATz2"
    "wEf67cqxCuyTWJVoTF7y2KzUP9yXDykQpZ</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>"
)


def version_tuple(text):
    return tuple(int(n) for n in re.findall(r"\d+", text or "")[:3])


def http_get(url, binary=False):
    """GET `url`: its bytes (a .NET byte array) with `binary`, else its text. Raises on any failure."""
    from System.IO import MemoryStream
    from System.Net import WebRequest
    from System.Text import Encoding
    # TLS 1.2 ASKED FOR, NEVER REQUIRED (2026-10-17: a player's check failed at once with "Cannot import name
    # SecurityProtocolType" -- on their .NET it is not where this import looked, and the import stopped the whole check).
    # Newer .NET speaks TLS 1.2 by itself; an older one needs the switch, so it is set where it can be.
    try:
        from System.Net import SecurityProtocolType, ServicePointManager
        ServicePointManager.SecurityProtocol = ServicePointManager.SecurityProtocol | SecurityProtocolType.Tls12
    except Exception:
        pass
    req = WebRequest.Create(url)
    req.Timeout = UPDATE_TIMEOUT_MS
    req.UserAgent = "%s/%s" % (SCRIPT_TITLE.replace(" ", "-"), SCRIPT_VERSION)
    resp = req.GetResponse()
    try:
        ms = MemoryStream()
        resp.GetResponseStream().CopyTo(ms)
        data = ms.ToArray()
    finally:
        resp.Close()
    return data if binary else Encoding.UTF8.GetString(data)


def latest_release():
    """(version, notes, script url, signature url) of UPDATE_REPO's newest release, or None. Raises on no network."""
    import json
    rel = json.loads(http_get("https://api.github.com/repos/%s/releases/latest" % UPDATE_REPO))
    urls = dict((a.get("name"), a.get("browser_download_url")) for a in rel.get("assets") or [])
    if UPDATE_FILE not in urls or UPDATE_FILE + ".sig" not in urls:
        return None                     # a release without a signed script is never offered
    return ((rel.get("tag_name") or "").lstrip("vV"), rel.get("body") or "", urls[UPDATE_FILE],
            urls[UPDATE_FILE + ".sig"])


def signature_ok(data, sig_text):
    """True when `sig_text` (base64) is the author's signature of `data`'s exact bytes."""
    from System import Convert
    from System.Security.Cryptography import HashAlgorithmName, RSA, RSASignaturePadding
    try:
        rsa = RSA.Create()
        rsa.FromXmlString(UPDATE_PUBLIC_KEY)
        return bool(rsa.VerifyData(data, Convert.FromBase64String((sig_text or "").strip()), HashAlgorithmName.SHA256,
                                   RSASignaturePadding.Pkcs1))
    except Exception:
        return False


NOTES_TEXT_COLOR = "#E6E6E6"     # THE NOTES READ PLAINLY: light text on the window's dark ground
NOTES_HEAD_COLOR = "#FFD966"     # ... headings in a soft gold, never bold


def notes_html(body):
    """A release's notes (GitHub's Markdown) as the gump's HTML.
    NO ENTITIES (2026-10-17: the 1.0.7 window showed "&nbsp;&nbsp;&bull;" as text -- the client's gump HTML reads no
    entities): a bullet is "- ", a nested one "-- ", and a < or > in the notes becomes ( or ) so no tag is opened.
    THE NOTES READ PLAINLY (owner, 2026-10-17: "the text is a little hard to read, mostly the bold"): no bold or italic --
    the client's bold is heavy at this size -- light text on the dark window, headings in NOTES_HEAD_COLOR, by the
    <BASEFONT COLOR> tag the shard's own event cards use."""
    out = []
    for line in (body or "").replace("\r", "").split("\n"):
        line = line.replace("<", "(").replace(">", ")").rstrip()
        indent = len(line) - len(line.lstrip(" "))
        line = line.strip()
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"(?<![*\w])\*(?!\s)(.+?)\*(?![*\w])", r"\1", line)
        if line.startswith("#"):
            line = "<BASEFONT COLOR=%s>%s</BASEFONT>" % (NOTES_HEAD_COLOR, line.lstrip("#").strip())
        elif line:
            if line.startswith(("- ", "* ")):
                line = ("-- " if indent else "- ") + line[2:]
            line = "<BASEFONT COLOR=%s>%s</BASEFONT>" % (NOTES_TEXT_COLOR, line)
        out.append(line)
    return "<br>".join(out)


def update_window(version, body):
    """The release's notes and Skip this version / Not now / Update -- Update at the bottom right (owner, 10-17: "the
    'continue' option or 'accept' option tends to be on the bottom right"). Waits for the press; the button id, or
    None when closed."""
    upd, later, skip = UPDATE_BUTTONS
    title = "%s %s is available -- you have %s" % (SCRIPT_TITLE, version, SCRIPT_VERSION)
    width = max(UPDATE_WIDTH, 60 + len(title) * UPDATE_CHAR_PX)
    height = 60 + UPDATE_NOTES_HEIGHT + 70
    gd = Gumps.CreateGump(movable=True)
    Gumps.AddPage(gd, 0)
    Gumps.AddBackground(gd, 0, 0, width, height, 30546)
    Gumps.AddAlphaRegion(gd, 0, 0, width, height)
    Gumps.AddLabel(gd, 20, 15, 68, title)
    Gumps.AddHtml(gd, 20, 45, width - 40, UPDATE_NOTES_HEIGHT, notes_html(body) or "No notes came with it.", False,
                  True)                 # THE NOTES READ PLAINLY: no parchment
    row = [(skip, "Skip this version", "Do not ask about %s again." % version),
           (later, "Not now", "Ask again in %d hours." % (UPDATE_LATER_S // 3600)),
           (upd, "Update", "Download it, check its signature, and put it in place of this one.")]
    gap = 24
    x = width - 20 - sum(35 + len(label) * UPDATE_CHAR_PX + gap for _b, label, _t in row) + gap
    for bid, label, tip in row:
        Gumps.AddButton(gd, x, height - 40, 4005, 4007, bid, 1, 0)
        Gumps.AddTooltip(gd, tip)
        Gumps.AddLabel(gd, x + 35, height - 38, 68, label)
        x += 35 + len(label) * UPDATE_CHAR_PX + gap
    Gumps.SendGump(UPDATE_GUMP_ID, Player.Serial, 200, 120, gd.gumpDefinition, gd.gumpStrings)
    if not Gumps.WaitForGump(UPDATE_GUMP_ID, REQUEST_GUMP_WAIT_MS):
        return None
    r = Gumps.GetGumpData(UPDATE_GUMP_ID)
    return getattr(r, "buttonid", None) if r is not None else None


def apply_update(version, data):
    """`data` -- signed and checked -- in place of this file, the old one kept in the data folder. True once written."""
    from System.IO import File
    from System.Text import Encoding
    text = Encoding.UTF8.GetString(data).lstrip(u"\ufeff")
    m = VERSION_RE.search(text)
    if m is None or m.group(1) != version:
        log("The update says it is %s, not %s -- not taken." % (m.group(1) if m else "no version", version), 33)
        return False
    try:
        compile(text, UPDATE_FILE, "exec")
    except SyntaxError as err:
        log("The update does not compile (%s) -- not taken." % err, 33)
        return False
    here = os.path.abspath(__file__)
    if not ensure_script_data_dir():
        log("No data folder for the backup -- the update was not taken.", 33)
        return False
    backup = script_data_path("%s.%s.bak" % (os.path.basename(here), SCRIPT_VERSION))
    File.Copy(here, backup, True)
    # THE RELOAD IS NO FAILURE (the panner, 2026-10-17 17:38): Auto Script Reload ends this run the moment the file
    # changes, so the success is said before the write.
    log("Updated to %s. The old version is kept as %s." % (version, backup), 68)
    File.WriteAllBytes(here, data)
    return True


def update_offer_at_start():
    """THE SIGNED UPDATE at start. OFF IN THIS FORK -- always True.

    FORK. Upstream's updater fetches its own file and writes it over this one,
    which would take the three fork changes with it. The signature check makes
    that safe for upstream and useless for us: a file carrying local changes
    can never be the file the author signed.

    THE WHOLE BODY IS LEFT BELOW, unreachable, rather than deleted. Taking a
    later upstream release means diffing this file against it, and a function
    that has been gutted reads as a conflict every time; one with an early
    return reads as one line.

    The settings row that would turn it on is gone too - see
    SETUP_ROWS - so there is no way to switch this back on by accident from
    inside the game.
    """
    return True

    if setup_get(SETUP_KEY_UPDATES, "0") != "1":
        return True
    try:
        found = latest_release()
    except Exception as err:
        log("Could not check for updates (%s) -- running %s." % (err, SCRIPT_VERSION), 33)
        return True
    if found is None or version_tuple(found[0]) <= version_tuple(SCRIPT_VERSION):
        log("Up to date (%s)." % SCRIPT_VERSION)
        return True
    version, body, script_url, sig_url = found
    if setup_get(SETUP_KEY_SKIP_UPDATE, "") == version:
        return True
    later_version, _sep, later_until = setup_get(SETUP_KEY_UPDATE_LATER, "").partition("|")
    try:
        if later_version == version and time.time() < float(later_until or 0):
            return True
    except ValueError:
        pass
    upd, later, skip = UPDATE_BUTTONS
    pressed = update_window(version, body)
    if pressed == skip:
        setup_set(SETUP_KEY_SKIP_UPDATE, version)
        save_setup()
        log("%s will not be offered again." % version)
        return True
    if pressed != upd:                  # Not now, or the window closed
        setup_set(SETUP_KEY_UPDATE_LATER, "%s|%d" % (version, time.time() + UPDATE_LATER_S))
        save_setup()
        log("Not now -- %s is offered again in %d hours." % (version, UPDATE_LATER_S // 3600))
        return True
    try:
        data = http_get(script_url, binary=True)
        sig = http_get(sig_url)
    except Exception as err:
        log("The update could not be downloaded (%s) -- running %s." % (err, SCRIPT_VERSION), 33)
        return True
    if not signature_ok(data, sig):
        log("The update's signature does not check -- it was NOT taken. Running %s." % SCRIPT_VERSION, 33)
        return True
    # THE RELOAD IS NEVER CAUGHT (the panner, 2026-10-17 18:25): only a file's own errors -- the disk, its permissions --
    # are caught here; Auto Script Reload's stop passes straight through.
    try:
        written = apply_update(version, data)
    except EnvironmentError as err:
        log("The update could not be written (%s) -- running %s." % (err, SCRIPT_VERSION), 33)
        return True
    if not written:
        return True
    Misc.Pause(UPDATE_RELOAD_WAIT_S * 1000)   # Auto Script Reload ends this run here and starts the new one
    log("Updated to %s. Press Refresh (the middle round button on RazorEnhanced's Scripting tab), then Play. To have "
        "updates start by themselves, tick Auto Script Reload there." % version, 33)
    return False


# CLOSE THE STORAGE WINDOW (2026-09-16), per the user: "let's make sure we're closing rune
# storage at the end."
#
# AT THE END, NOT AT THE CULPRIT. Every path that OPENS this gump already closes it:
# storage_balances() in a finally, withdraw_from_storage_key() on both its exits. So whatever
# leaves it on screen happens after the last of those -- most likely the absorb just above, which
# reaches the key through its CONTEXT MENU and has nothing after it to clean up. That is an
# inference from the ordering, NOT a confirmed behaviour of ContextReply, and it is exactly why
# the close belongs here: it does not depend on knowing who left the window open.
#
# OUTSIDE THE `mode is not None` GUARD on purpose -- a run that stopped early (failed safety
# gate, FATAL) still opened the gump during the startup scan, and those are the runs someone is
# about to go stare at the screen for.
#
# PRECISE ID, NEVER "the current gump": HasGump() is a per-ID check (CONFIRMED live, see
# Omni_Engine.py's note on Omni_Diag_HasGump.py), so an unrelated window that happens
# to be open can never receive this button.
def close_storage_window():
    try:
        if Gumps.HasGump(STORAGE_GUMP_ID):
            Gumps.SendAction(STORAGE_GUMP_ID, 0)
            log("Closed the {} window.".format(RUNECRAFTING_STORAGE_NAME))
    except Exception as _close_err:
        log("Warning: could not close the {} window ({}).".format(
            RUNECRAFTING_STORAGE_NAME, _close_err), 33)


def main():
    """The run a Play press starts: the setup check, the storage scan, Apply Runes, the exit absorb, the window close.

    A FUNCTION SINCE THE SPLIT (2026-10-17): a script that imports this file calls it, so nothing here
    may run on an import -- see the `__name__` test at the bottom."""
    log("Omni Runecrafting starting.")
    if not update_offer_at_start():     # THE SIGNED UPDATE: before any screen, while the player is here
        return

    # PERK TRACKER NO LONGER LAUNCHED FROM HERE (2026-09-11), per the user: "looks like Runecrafting is
    # running perk tracker. that's outdated."
    #
    # SAFE TO DROP -- this was a convenience, never a dependency. This script reads perks entirely on
    # its own: read_active_perks() sends [perks fresh and parses the journal with, in its own words,
    # "the same proven regex PerkTracker.py's own parse_all_perk_expirations() uses, duplicated here
    # rather than" imported. use_perk_deed_if_needed()/seed_gate_cache_from_perks() build on that same
    # independent read. Nothing in the crafting or application flow ever asked PerkTracker.py anything.
    #
    # ensure_perk_tracker_running() is left DEFINED but unused, same convention this file already uses
    # for ask_which_mode() ("left defined/unused below rather than deleted, in case ... needs to be
    # reachable again later").
    #
    # NOT TOUCHED: Omni_Engine.py:9217 still launches it at engine start. That is a separate call
    # site and a separate decision -- the user's remark was about running RuneCrafting.

    # MODE PICKER SKIPPED (2026-08-27), per the user: "let's get rid of this menu. Keep the code but
    # have it default to Apply Runes." ask_which_mode() is left defined/unused below rather than
    # deleted, in case Craft Runes needs to be reachable again later.
    mode = "apply"
    # PREFLIGHT (2026-09-13) -- stops BEFORE either flow, so neither has to know about it, and clears
    # `mode` rather than raising, matching every other early stop here so "finished" still prints.
    if not preflight_required_items():
        log("STOPPING: {} -- see the gump.".format(
            "; ".join("'{}' {}".format(_n, _d) for _n, _d in SETUP_LAST_BLOCKERS)
            or "something this script needs is not in the backpack"), 33)
        mode = None
    # SCAN THE STORAGE ONCE, HERE (2026-09-16), per the user: "we'll need to scan and then close rune
    # storage on startup i guess."
    #
    # AFTER THE PREFLIGHT, because that is what resolves the key's serial (required_item_serial() reads
    # the cache it fills), and only when it passed -- a failed preflight means the key may not be in
    # the pack at all, and there is nothing to open.
    #
    # BEFORE EITHER FLOW, because the Apply Preview is the first thing the user sees and its Rough
    # Stone count, its odds and its Suggested target all depend on this reading.
    if mode is not None:
        scan_runecrafting_storage()
    _finished = False   # True only when the mode's run FINISHED (2026-09-24) -- see the exit absorb below
    if mode == "craft":
        _finished = bool(run_crafting_flow())
    elif mode == "apply":
        _finished = bool(run_application_flow())
    else:
        log("No valid mode chosen -- stopping.", 33)

    # THE LAST THING WE DO, ALWAYS (2026-09-15), per the user: "make sure the last thing we do is
    # always absorb with rune storage."
    #
    # WHAT IT PUTS BACK: the withdrawn chisel with its unspent charges (the 60,000 withdrawal was
    # chosen on exactly this basis -- "we'll just use 60000 and put leftovers back in if there are
    # any"), runes crafted but not applied, and anything a restock bought that the batch did not
    # consume. The next run then starts from a clean pack.
    #
    # ON EVERY EXIT, INCLUDING A FAILED ONE. A run that died on a FATAL is the likeliest to have
    # left a chisel and a half-finished pile in the pack, so absorbing only after a success would
    # skip the case that needs it most.
    #
    # FAIL-SOFT BY CONSTRUCTION: absorb_backpack_into_key() logs and returns False on a missing
    # key, no context menu, or an unrecognised label -- never raises. The result is reported, not
    # acted on, because nothing here may turn a finished batch into an error. Its own
    # pace_storage_key_fill() honours the shard's ~1/second fill rate, so no extra wait is added.
    if mode == "apply":
        # NEVER AFTER AN APPLY (2026-09-24 11:53): the product of an apply run is the weapon left in the pack, and the
        # absorb goes through Master Keys, which files it into the Armory. The 11:53:34 run finished every stat, the
        # "finished craft" absorb fired, and the owner's finished axe went into the enhanced Armory. "Finished craft"
        # means finished RUNES (craft and passive modes); an apply run leaves the pack alone whatever its outcome.
        log("Apply run over -- nothing absorbed on exit: the weapons and any spare runes stay in the pack.")
    elif mode is not None:
        if _finished:
            if absorb_backpack_into_key(RUNECRAFTING_STORAGE_NAME):
                log("Finished -- put everything left in the pack back into {}.".format(RUNECRAFTING_STORAGE_NAME))
            else:
                log("Could not absorb into {} on the way out -- anything left is still in the pack."
                    .format(RUNECRAFTING_STORAGE_NAME), 33)
        else:
            log("The run did not finish -- %s -- not absorbing; the pack is left as it is." % (
                LAST_STOP_SAID[0].rstrip(".") or "it ended before its first step"))
    close_storage_window()
    log("Omni Runecrafting finished.")


# RUN ONLY WHEN STARTED, NEVER ON AN IMPORT (2026-10-17, THE SPLIT): RazorEnhanced runs the script it starts as
# "__main__" (Harvest.py has stood on the same test since 2026-09); a script that imports this
# file calls main() itself.
if __name__ == "__main__":
    main()
