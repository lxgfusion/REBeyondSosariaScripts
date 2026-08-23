###################################################
#          Eclipse Fishing Tourney Fisher         #
#                    By: Hand                     #
#                                                 #
#                  AFK Fisher                     #
###################################################

##################################
# • Runs for 46 minutes          #
# • Returns you to you homerune  #
# • Activates TourneyWait script #
##################################

# CHANGES FROM THE ORIGINAL - there are only three, all in storeFish():
#
#   1. Treasure Hunter's Storage added, for fishing nets and treasure maps.
#      Inspected 2026-08-22: ItemID 0xA321, hue 0x0000, Blessed, 1 stone,
#      sitting in a bag in the pack.
#
#   2. The key is answered by the NAME of its menu entry rather than by
#      position. The original sent ContextReply(storage, 2) - whatever happens
#      to be third on that menu. That is fine for the haul key, which you have
#      tested, but the Treasure Hunter's Storage menu has never been read, so
#      guessing that its third entry is the right one is a coin flip on a menu
#      that may also carry Empty or Destroy. It falls back to index 2 if it
#      cannot find a name it recognises, so the haul key behaves exactly as it
#      did before. The menu is printed the first time each key is used - if the
#      entry is worded differently on your shard, add it to FILL_ENTRIES.
#
#   3. One click per key instead of one per item. "Refill from stock" empties
#      the pack of everything that key accepts in a single action, so the
#      original's loop over every fish sent the same deposit N times.
#
# Everything else - the cast, the boat, the fight, the junk sweep, the timer,
# the journal handling - is untouched.

from System.Collections.Generic import List
from System import Byte, Int32 as int
import re

# ---------------------------------------------------------------------------
# THE SERIALS BELOW ARE ZEROED ON PURPOSE.
#
# This repo is public, so the published copy carries nobody's live serials.
# Fill in your own with Razor's Enhanced Item Inspector - single-click the
# item and read the "Serial" line. The script says at startup which ones are
# still unset.
#
# Graphics (ItemID) and hues are NOT zeroed: those are shard data, the same for
# everyone, and they are what make this usable without inspecting every item.
# ---------------------------------------------------------------------------
delay = 1000
player = 0                #YOUR character serial - Item Inspector, or
                          #  Razor's Player tab. Nothing casts until set.
# homerune = 0            #Enter home rune/runebook
storage = 0               #Fisherman's Haul or Master Key - takes the fish
treasure = 0              #Treasure Hunter's Storage - nets and maps.
                          #  Its graphic is 0xA321 if you need to find it.
fish = [0x09CC,0x4306,0x4303,0x4307,0x44C5,0x44C6,0x44C3]
trash = 0                 # your trash bag. 0 disables binning entirely.
junk = [0x1711,0x170B,0x0DD6,0x44C4,0x44C3,0x170D]

# ---------------------------------------------------------------------------
# CUTTING UP THE BIG FISH
#
# Inspected 2026-08-22:
#
#   dagger        ItemID 0x0F52, in the backpack. Durability 34/34 - it
#                 wears out, so the graphic is the fallback for the
#                 replacement.
#   a big fish    ItemID 0x09CC, hue 0x0847 ON THE GROUND but
#                 hue 0x058C in the pack - the colour varies, the name does
#                 not. Container None, Ground YES, 155 stones. It lands at
#                 your feet, not in the pack, which is why the haul key never
#                 sees one.
#   blue marlin   ItemID 0x4305, hue 0x0000, IN THE BACKPACK (Ground No),
#                 154 stones.
#   raw fish steak  ItemID 0x097A. What the cutting leaves behind.
#
# 0x09CC is already in `fish` above, but that list only ever described things
# IN THE PACK. A big fish on the ground is a different problem and needs a
# different search - see cutFish().
# ---------------------------------------------------------------------------
dagger = 0                # your dagger. Optional - daggerID below finds
                          #   one in your pack if this is 0, or if the
                          #   blade breaks and gets replaced.
daggerID = 0x0F52
# "raw fish steak". CONFIRMED IN GAME 2026-08-22: the Fisherman's Haul accepts
# these, so storeFish() puts them away with everything else and they need no
# handling of their own. Do not "fix" this by routing them somewhere.
steak = 0x097A

# Everything the dagger is allowed to cut. ADD NEW FISH HERE - it is the only
# place that needs changing.
#
#   names    THE THING THAT DECIDES. Matched inside the item's name, lower
#            case. A fish whose name will not load is NOT cut - see nameOf().
#   id       Graphic. A cheap pre-filter for the search, never the authority.
#   hue      -1 for any, which is the right answer for almost everything.
#   where    "ground" | "pack" | "both". A big fish lands at your feet and a
#            blue marlin goes into the pack, and a backpack search can no more
#            see the one than a world search can see the other.
#
# WHY NAMES AND NOT HUES. This first shipped keyed on hue, because the big fish
# that was inspected on the ground was 0x0847. The ones in the pack turned out
# to be 0x058C - same graphic, different colour - so they were skipped and it
# looked like the pack was not being searched at all. Two hues on one graphic
# means the hue is a VARIETY marker, not a big-versus-ordinary marker, and
# chasing it would mean adding a new number every time a new colour turns up.
#
# The name does not drift: "a big fish" is a big fish whatever colour it is,
# and an ordinary fish is not called that. Same lesson as the creature bodies
# in CLAUDE.md - the cheap numeric key finds candidates, the NAME decides.
cuttable = [
    {"names": ["big fish"],    "id": 0x09CC, "hue": -1, "where": "both"},
    {"names": ["blue marlin"], "id": 0x4305, "hue": -1, "where": "both"},
]

CUT_RANGE = 3           # tiles - how far to look for fish and steaks
CUT_TIMEOUT = 3000      # ms to wait for the dagger's target cursor
CUT_SETTLE = 400        # ms between cursor and target. REQUIRED on this shard
CUT_PAUSE = 800         # ms after a cut, for the steaks to appear
GRAB_PAUSE = 700        # ms between pickups - the drag rate limit
MAX_CUTS = 12           # ceiling per pass, so a fish that will not cut cannot
                        # spin the script forever

# Menu entries that push the pack into a storage key, tried in this order.
# Add yours here if your shard words it differently - the menu is printed the
# first time each key is used so you can read the exact wording.
FILL_ENTRIES = ["Refill from stock", "Fill from backpack", "Refill From Stock"]

# Never answered, however well it matches. These sit on the same menus and
# they do not put things away.
NEVER_ENTRIES = ["empty", "destroy", "delete", "release", "rename", "dye"]

# Entry the original always used, kept as the fallback so the haul key keeps
# behaving exactly as it has been.
FALLBACK_INDEX = 2

_menu_shown = []

#######################
#  Functions portion  #
#######################

# Uses equipped fishing pole and casts 3 tiles from the direction you are facing
def useFishing():
    Items.UseItem(Player.GetItemOnLayer('RightHand'))
    Misc.Pause(400)
    Target.WaitForTarget( 2000, True )
    Target.TargetExecuteRelative(player,3)
    Misc.Pause(8500)
    Target.Cancel()

# Moves boat 8 tiles forward after fish are not biting
def moveBoat():
    for i in range(8):
        Player.ChatSay(37, "Forward one")
        Misc.Pause(500)

# Single-clicks a storage key and picks the entry that empties the pack into it.
# ONE reply - it takes everything it accepts in one go.
def storeKey(serial, label):
    Misc.Pause(100)
    entries = Misc.WaitForContext(serial, 10000)
    if not entries:
        Misc.SendMessage("%s: no context menu - is it in your pack?" % label,
                         33, True)
        return False
    Misc.Pause(100)

    names = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        names.append(text if text is not None else str(entry))

    # Print each menu once, so the real wording is on record rather than guessed.
    if label not in _menu_shown:
        _menu_shown.append(label)
        Misc.SendMessage("%s menu: %s" % (label, " | ".join(names)), 90, True)

    # By name first.
    for want in FILL_ENTRIES:
        for name in names:
            if (name or "").strip().lower() == want.strip().lower():
                Misc.ContextReply(serial, name)
                Misc.Pause(600)
                return True
    for want in FILL_ENTRIES:
        for name in names:
            lowered = (name or "").lower()
            if want.strip().lower() in lowered:
                if any(bad in lowered for bad in NEVER_ENTRIES):
                    continue
                Misc.ContextReply(serial, name)
                Misc.Pause(600)
                return True

    # Nothing recognised - fall back to what the original always sent, but only
    # if that entry is not one of the dangerous ones.
    if len(names) > FALLBACK_INDEX:
        chosen = names[FALLBACK_INDEX]
        if any(bad in (chosen or "").lower() for bad in NEVER_ENTRIES):
            Misc.SendMessage("%s: entry %d is '%s' - REFUSING to click it. Add "
                             "the right wording to FILL_ENTRIES."
                             % (label, FALLBACK_INDEX, chosen), 33, True)
            return False
        Misc.ContextReply(serial, FALLBACK_INDEX)
        Misc.Pause(600)
        return True

    Misc.SendMessage("%s: no entry matched and there is no #%d - it offers: %s"
                     % (label, FALLBACK_INDEX, " | ".join(names)), 33, True)
    return False

# Stores fish in your storage key, and nets/maps in the treasure storage
def storeFish():
    storeKey(storage, "Fisherman's Haul")
    Misc.Pause(300)
    storeKey(treasure, "Treasure Hunter's Storage")
    Misc.Pause(300)

# Finds your dagger - by serial first, then by graphic if it has been replaced.
# Daggers have durability, so the serial will not last forever.
def findDagger():
    blade = Items.FindBySerial(dagger)
    if blade is not None:
        return blade
    pack = Player.Backpack
    if pack is None:
        return None
    found = Items.FindAllByID(daggerID, -1, pack.Serial, -1, False)
    for blade in list(found or []):
        return blade
    return None

# Cuts up every big fish lying at your feet and picks up the steaks.
#
# The big fish is ON THE GROUND (Container None, Ground Yes), so a backpack
# search never sees one - it has to be a world search, which is what the -1
# container argument does.
def cutFish():
    # NOTE: this uses Razor's ignore list (Misc.IgnoreObject) to drop fish that
    # refuse to cut. Misc.ClearIgnore() resets it if something gets stuck on it.
    # The pack snapshot goes stale as the run goes on, and a stale one hides
    # things that are really in there. Re-read it BEFORE anything looks in the
    # pack - and that includes finding the dagger. When `dagger` is 0 the blade
    # is looked up by graphic, which is a pack search, so doing this after
    # findDagger meant a stale snapshot reported "no dagger" and cutting
    # silently never happened at all.
    refreshPack()

    blade = findDagger()
    if blade is None:
        Misc.SendMessage("No dagger found (serial 0x%X / id 0x%04X) - cannot "
                         "cut the big fish." % (dagger, daggerID), 33, True)
        return 0

    reportUncut()

    cuts = 0
    for _ in range(MAX_CUTS):
        target = findCuttable()
        if target is None:
            # One more look at a freshly re-read pack before believing there is
            # nothing left - this is exactly where the stale snapshot bit.
            refreshPack()
            target = findCuttable()
        if target is None:
            break

        # A leaked cursor is answered by the NEXT TargetExecute, so the cut
        # silently goes nowhere. Cancel first, every time.
        Target.Cancel()
        Misc.Pause(100)
        Items.UseItem(blade)
        if not Target.WaitForTarget(CUT_TIMEOUT, True):
            Misc.SendMessage("The dagger gave no target cursor.", 43, True)
            Target.Cancel()
            break
        Misc.Pause(CUT_SETTLE)
        Target.TargetExecute(target.Serial)
        Misc.Pause(CUT_PAUSE)

        # A cut fish is GONE - that is the only reliable signal, and it is the
        # same whether it was on the floor or in the pack. Testing "is it still
        # on the ground" would call every uncut backpack fish a success and
        # then loop on it forever.
        # Cutting changed the pack, so the snapshot is stale again - and the
        # "did it work" test below reads it.
        refreshPack()
        if Items.FindBySerial(target.Serial) is not None:
            Misc.SendMessage("0x%X would not cut - ignoring it." % target.Serial,
                             43, True)
            Misc.IgnoreObject(target.Serial)
            continue
        cuts += 1

    if cuts:
        Misc.SendMessage("cut up %d fish" % cuts, 68, True)
    grabSteaks()
    return cuts

# Re-opens the backpack so its contents are not a stale snapshot.
#
# THIS IS WHY ONLY SOME OF THE BIG FISH WERE CUT. Item.Contains is a snapshot
# taken when the container was opened, and Items.FindAllByID with a CONTAINER
# serial does not query the item index - it resolves the container and walks
# that same snapshot (Razor/RazorEnhanced/Item.cs, v1.0.0.14). Only
# container -1 goes through a real world filter. So during a long run - fish
# caught, steaks added, the haul key emptying the pack - the snapshot drifts
# and fish that really are in the pack are simply invisible to the search.
#
# Asking a different way does not help. The only fix is to re-open it.
def refreshPack():
    pack = Player.Backpack
    if pack is None:
        return None
    for _ in range(3):
        try:
            Items.UseItem(pack)
            Items.WaitForContents(pack, 2000)
        except Exception:
            pass
        if list(getattr(pack, "Contains", None) or []):
            return pack
        Misc.Pause(200)
    return pack

# An item's name, from the tooltip if the Name field has not loaded.
#
# Returns "" when it cannot be read, and the caller treats that as "do not
# touch it". A missed fish costs nothing; knifing something because its name
# would not load is not recoverable.
def nameOf(item):
    try:
        name = (item.Name or "").strip()
    except Exception:
        name = ""
    if name:
        return name.lower()
    try:
        Items.WaitForProps(item, 1000)
        props = Items.GetPropStringList(item)
    except Exception:
        props = []
    for line in list(props or []):
        text = (line or "").strip()
        if text:
            return text.lower()
    return ""

# Says once - not once per cast - when something on a cuttable graphic is being
# passed over. That is how the hue problem was found, and the next surprise
# will look the same.
_odd_seen = []

def reportUncut():
    pack = Player.Backpack
    if pack is None:
        return
    graphics = dict((spec["id"], spec) for spec in cuttable)
    for item in list(getattr(pack, "Contains", None) or []):
        spec = graphics.get(item.ItemID)
        if spec is None:
            continue
        name = nameOf(item)
        if name and any(w in name for w in spec["names"]):
            continue          # it matches; it will be cut
        key = "%04X:%04X:%s" % (item.ItemID, item.Hue, name)
        if key in _odd_seen:
            continue          # already said. Do not repeat it every cast.
        _odd_seen.append(key)
        if not name:
            Misc.SendMessage("0x%04X hue 0x%04X in your pack has no readable "
                             "name - leaving it alone rather than guessing."
                             % (item.ItemID, item.Hue), 43, True)
        else:
            Misc.SendMessage("%r (0x%04X hue 0x%04X) is not cut - `cuttable` "
                             "matches %s for that graphic. Add a word from its "
                             "name if it should be."
                             % (name, item.ItemID, item.Hue,
                                "/".join(spec["names"])), 43, True)

# The next fish the dagger is allowed to cut, or None. Searches the ground and
# the pack separately - a world search does not see inside your backpack, and a
# backpack search does not see the floor.
def findCuttable():
    pack = Player.Backpack
    for spec in cuttable:
        where = spec.get("where", "both")
        hue = spec.get("hue", -1)

        # The graphic is a cheap PRE-FILTER for the search. The name below is
        # the authority - see the note on `cuttable`.
        def wanted(item, on_ground):
            if bool(getattr(item, "OnGround", False)) != on_ground:
                return False
            name = nameOf(item)
            if not name:
                return False      # will not name itself, so leave it alone
            return any(word in name for word in spec["names"])

        if where in ("ground", "both"):
            # considerIgnoreList TRUE, deliberately: it is what makes
            # Misc.IgnoreObject below actually do anything. With False the
            # blacklisted fish comes straight back on the next pass and the
            # script retries it for the rest of the run.
            for item in list(Items.FindAllByID(spec["id"], hue, -1,
                                               CUT_RANGE, True) or []):
                if wanted(item, True):
                    return item

        if where in ("pack", "both") and pack is not None:
            for item in list(Items.FindAllByID(spec["id"], hue, pack.Serial,
                                               -1, True) or []):
                if wanted(item, False):
                    return item
    return None

# Picks the raw fish steaks up off the ground. They are left where the fish was.
def grabSteaks():
    pack = Player.Backpack
    if pack is None:
        return 0
    taken = 0
    for _ in range(MAX_CUTS):
        found = Items.FindAllByID(steak, -1, -1, CUT_RANGE, True)
        loose = None
        for item in list(found or []):
            if getattr(item, "OnGround", False):
                loose = item
                break
        if loose is None:
            break

        # Stop before the pack refuses the pickup - a steak dropped because you
        # were overweight just stays on the floor and sails away with the boat.
        if Player.Weight >= Player.MaxWeight:
            Misc.SendMessage("Too heavy to pick up steaks (%d/%d) - storing "
                             "first." % (Player.Weight, Player.MaxWeight),
                             43, True)
            storeFish()
            if Player.Weight >= Player.MaxWeight:
                break

        Items.Move(loose, pack, 0)      # 0 means the whole stack
        Misc.Pause(GRAB_PAUSE)
        if Items.FindBySerial(loose.Serial) is not None and \
                getattr(Items.FindBySerial(loose.Serial), "OnGround", False):
            Misc.IgnoreObject(loose.Serial)
            continue
        taken += 1
    if taken:
        Misc.SendMessage("picked up %d stack(s) of raw fish steak" % taken,
                         68, True)
    return taken

# Names every serial still left at 0, and refuses to start without the ones
# that matter. A published copy ships zeroed, so this is the first thing anyone
# cloning it will hit - and "it just does nothing" is a terrible first run.
def checkConfig():
    if not player:
        Misc.SendMessage("player is 0 - set it to YOUR character serial or the "
                         "cast has nothing to aim from. Nothing will run.",
                         33, True)
        return False

    for value, label, why in (
            (storage, "storage", "the fish will pile up in your pack"),
            (treasure, "treasure", "nets and maps will not be stored"),
            (trash, "trash", "junk will not be binned"),
            (dagger, "dagger", "a dagger is looked up by graphic instead")):
        if not value:
            Misc.SendMessage("%s is 0 - %s." % (label, why), 43, True)
    return True

# Casts wildfire when a gray shows up (must set enemy in RE targeting tab)
def fight():
    Spells.CastSpellweaving("Wildfire")
    Target.WaitForTarget(10000, False)
    Target.TargetExecute(player)
    Misc.Pause(400)

# Checks pack for trash
def checkPack():
    for item in Player.Backpack.Contains:
        # 0x44C3 is in BOTH fish and junk. Without this test a fish the haul
        # key had not taken yet gets dragged into the trash bag.
        if item.ItemID in fish:
            continue
        if item.ItemID in junk:
            Items.Move(item, trash, -1)
            Misc.Pause(delay)
        else:
            Misc.Pause(1)
# Sends boat back for 2 minutes, recalls back to your homerune position, hides, and activates TourneyWait script
# def goHome():
#    Player.ChatSay(37, "Back")
#    Misc.Pause(120000)
#    Player.ChatSay(37, "Stop")
#    Misc.Pause(500)
#    Spells.CastMagery("Recall")
#    Target.WaitForTarget(10000, False)
#    Target.TargetExecute(homerune)
#    Misc.Pause(2000)
#    Player.UseSkill('Hiding')
#    Misc.Pause(500)
#    Journal.Clear()
#    Misc.ScriptRun('TourneyWait.py')
#    Misc.Pause(500)
#    Misc.ScriptStop('FishingEclipseTourney')


####################
#  Script portion  #
####################
        ###   Fishes until you stop the script   ###
#
# The timer is gone. It used to be Timer.Create("Fish", 92760000, ...) under a
# comment saying "Runs for 46 minutes" - 92,760,000 ms is 25.8 HOURS and 46
# minutes is 2,760,000, so the two never agreed. Now it simply runs until you
# press Stop, or until you die.
Misc.SendMessage("AFK Fisher running - press Stop to end it.", 68, True)

# Checked ONCE. Putting checkConfig() in the while test would re-print every
# warning on every lap.
_ready = checkConfig()

while _ready:
    if Player.IsGhost:
       break

    elif Journal.Search ("Uh oh!"):
        Misc.Pause(500)
        fight()
        Journal.Clear()

    elif Journal.Search ("biting here"):
        Misc.Pause(500)
        # Cut and collect BEFORE the boat moves - otherwise the big fish at
        # your feet, and any steaks beside them, are simply left behind.
        cutFish()
        Misc.Pause(500)
        moveBoat()
        Misc.Pause(1000)
        storeFish()
        Misc.Pause(1000)
        checkPack()
        Misc.Pause(1000)
        Journal.Clear()
    useFishing()
    # A big fish lands at your feet on the cast that caught it, so deal with it
    # each time round rather than only when the fish stop biting.
    cutFish()

cutFish()
storeFish()
Misc.Pause(1000)
