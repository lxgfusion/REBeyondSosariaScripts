"""
COVFarm - camp the Slasher of Veils and kill it from range.
===========================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

What it does
------------
1. Sits and waits for the monster to spawn.
2. Opens with WILDFIRE on it.
3. Holds 4-5 tiles while spamming NETHER BLAST, stepping back whenever the
   monster closes and following when it drifts off.

   The standoff is enforced CONTINUOUSLY, not once per cast. Every wait in the
   fight - the targeting cursor, the settle, the recovery between casts, even
   waiting for mana - is broken into short slices with a distance correction
   between each. A single cast blocks for several seconds, and the monster
   walks for all of them, so checking only at the top of the loop lets it
   reach melee range unanswered.
4. Confirms the kill by finding its CORPSE.

   Death is never inferred from the monster disappearing. It disappears from
   Razor's mobile list whenever it leaves range or line of sight, so treating
   that as a kill ended fights with the boss still alive. Only a corpse that
   was not already on the ground counts.
5. Walks onto the corpse and says the shard's grab command ([grab) to take the
   loot you have configured in game. The corpse vanishing is how it knows the
   grab worked.
6. Walks back to where you started it, and waits for the next spawn.

Inspected target (Enhanced Mobile Inspector):

    Name:      The Slasher of Veils
    MobileID:  0x02E5
    Serial:    0x0003FE1B      (changes every spawn - NOT used)
    Notoriety: 6

The serial is deliberately not configured: it is different for every spawn.
The script matches on NAME, using the body only as a cheap pre-filter, which is
the rule this project learned the hard way - a body value alone is not proof of
what something is.

BEFORE YOU RUN IT
-----------------
Check SPELL_ATTACK / SPELL_OPENER in section 2. "Wildfire" is a Spellweaving
spell and "Nether Blast" is not one of the stock Mysticism names, so it is
probably custom to this shard. If a cast does nothing, set that spell's
"school" explicitly - the script prints what it tried and what the server said.

Stand where you want to fight BEFORE starting. That spot is recorded as the
camp: the script holds it while waiting, and walks back to it after looting, so
the camp does not creep away over a night of spawns.

Safety
------
* A kill needs a corpse. Corpses lie around for minutes, so the corpses already
  present when the fight starts are recorded and never counted - otherwise the
  previous kill's corpse would mark the next spawn dead the instant it engaged.
* It never attacks anything whose name does not match. A wrong body is not
  enough to make it swing.
* It stops and says so if your health drops below FLEE_AT_HITS_PERCENT, if you
  die, or if you run out of the reagents/mana to keep casting.
* Your journal is not wiped - it reads new lines through a timestamp cursor.
"""

import math
import re
import time


SCRIPT_VERSION = "1.0.0"


# #############################################################################
# ##                            C O N F I G                                  ##
# #############################################################################

# =============================================================================
# 1. THE MONSTER
# =============================================================================
#
#   name       Matched case-insensitively as a SUBSTRING of the creature's
#              name. Mobiles.Filter().Name is an EXACT match and fails silently
#              when a shard renames something, so matching is done here instead.
#   bodies     Cheap pre-filter for the scan. Leave the list EMPTY to scan on
#              name alone, which is slower but survives a body change.
#   notoriety  Optional extra check. 6 is "murderer" (red). None to skip.

TARGET_NAME = "Slasher of Veils"
TARGET_BODIES = [0x02E5]
TARGET_NOTORIETY = 6

# How far out to look for it. Bounded on purpose - an unset RangeMax means
# everything the client knows about.
SCAN_RANGE = 20


# =============================================================================
# 2. THE SPELLS
# =============================================================================
#
#   name    Exactly as the shard names the spell.
#   school  Which Spells.Cast* function to use. "auto" lets Razor work it out
#           from the name, which is right most of the time. If a spell will not
#           fire, set this: "magery", "necro", "chivalry", "bushido",
#           "ninjitsu", "spellweaving", "mysticism", "mastery", "cleric",
#           "druid".
#   target  "mobile"   - target the monster itself.
#           "location" - target the ground under it. Field spells usually want
#                        this. If a cast is refused, try the other one.
#   mana    Do not start the cast below this much mana. 0 to ignore.
#
# Wildfire is a SPELLWEAVING spell in stock UO and lays a field on the ground,
# so it targets a location. Nether Blast is not a stock spell name at all, so
# "auto" is a guess - if it does not fire, that is the first thing to change.

SPELL_OPENER = {
    "name":   "Wildfire",
    "school": "auto",
    "target": "location",
    "mana":   40,
}

SPELL_ATTACK = {
    "name":   "Nether Blast",
    "school": "mastery",          # confirmed: it is in the Book of Masteries
    "target": "mobile",
    "mana":   30,
}

# Recast the opener every this many ms during the fight. Fields expire, so a
# long fight may want it refreshed. 0 = cast it ONCE per spawn, which is what
# was asked for.
OPENER_RECAST_MS = 0


# =============================================================================
# 3. POSITIONING  -  the band is held at ALL times, including mid-cast
# =============================================================================
#
# Written as an explicit band rather than "5 tiles give or take", because
# "within 5 tiles" has to mean never further than 5:
#
#   closer than DISTANCE_MIN  -> step AWAY   (it is getting into melee)
#   further than DISTANCE_MAX -> step TOWARD (you are drifting out of range)
#   in between                -> stand and cast
#
# Keep MIN below MAX by at least one tile. With MIN == MAX the character has
# no band to sit in and jitters back and forth on the spot forever.

DISTANCE_MIN = 4                # never let it get closer than this
DISTANCE_MAX = 5                # never drift further than this

# Absolute ceiling for casting at all. If something drags you past this the
# script closes the gap before it tries to cast again.
MAX_CAST_DISTANCE = 10

# How often the distance is re-checked WHILE waiting - between casts, while
# waiting for the targeting cursor, and while waiting for mana.
#
# This is the setting that makes the standoff hold. Checking distance once per
# cast is not enough: a single cast blocks for the cursor wait plus the settle
# plus the recovery pause, and the monster walks the whole time. Every one of
# those waits is now broken into KITE_TICK_MS slices with a distance
# correction between each, so nothing can close on you unanswered.
KITE_TICK_MS = 150


# =============================================================================
# 4. DEATH CONFIRMATION  -  nothing counts as a kill without a corpse
# =============================================================================
#
# The monster vanishing from Razor's mobile list is NOT proof it died. It also
# vanishes when it walks out of range, breaks line of sight, or the client
# de-syncs for a moment - and calling that a kill ends the fight while the boss
# is still alive and coming for you.
#
# So a corpse has to appear. Inspected (Enhanced Item Inspector):
#
#     Name:   a slasher of veils corpse
#     ItemID: 0x2006      Corpse: Yes      Ground: Yes
#     Amount: 741         <- 0x2E5, the creature's BODY value
#
# Two ways to recognise it, either is enough: the name, or that Amount field,
# which carries the body of whatever died. The body check keeps working if the
# shard renames the creature.

CORPSE_IDS = [0x2006]

# Matched case-insensitively against the corpse's name. Leave empty to rely on
# the body value alone.
CORPSE_NAME_HINT = "slasher of veils"

# Also accept a corpse whose Amount equals the monster's body value.
CORPSE_MATCH_BODY = True

# How far from us to look for it.
CORPSE_SEARCH_RANGE = 8

# CRITICAL: corpses lie around for minutes, so a corpse that was ALREADY on the
# ground when the fight started is not proof of anything - it is last spawn's.
# The script records the corpses present at engage and only accepts a NEW one.
# There is no setting for that; it is not optional.

# If the monster disappears and no corpse shows up within this long, it did not
# die - it went out of sight. The script says so and goes back to waiting
# rather than claiming a kill it did not make.
CORPSE_GRACE_MS = 8000


# =============================================================================
# 5. LOOTING  -  walk to the corpse and let the shard's grab command empty it
# =============================================================================

LOOT_CORPSE = True

# Said once standing over the corpse. This is a SHARD command, not a spell -
# it picks up whatever you have configured in game. Change it if your shard
# uses a different word.
LOOT_COMMAND = "[grab"

# Colour of what the character says.
SPEECH_HUE = 33

# How close to stand before saying it. 1 = right on top of it. Raise it if the
# grab command has a longer reach and you would rather not walk all the way.
LOOT_DISTANCE = 1

# The corpse vanishing is how we know the grab worked. If it is still there
# after LOOT_RESULT_MS the command is said again, up to LOOT_RETRIES times.
#
# A corpse that never disappears is NOT necessarily a failure - it just means
# something in it was not on your grab list. The script says so and carries on
# rather than standing there forever.
LOOT_RETRIES = 3
LOOT_RESULT_MS = 2500

# Give up walking to the corpse after this long.
LOOT_APPROACH_TIMEOUT = 15000

# After looting, walk back to where the script was started.
#
# Worth leaving on. Kiting moves you around during the fight and the corpse is
# somewhere else again, so without this the camp drifts a little further every
# spawn until it is nowhere near where you meant to stand.
RETURN_TO_CAMP = True
CAMP_TOLERANCE = 2              # close enough to the start, do not fuss
CAMP_RETURN_TIMEOUT = 20000


# =============================================================================
# 6. SAFETY
# =============================================================================

# Break off if your health drops below this percentage. 0 disables it.
FLEE_AT_HITS_PERCENT = 40

# Where to run when breaking off: how many tiles to put between you and it.
FLEE_DISTANCE = 15

# Stop the whole script after breaking off, rather than waiting for the next
# spawn. Leave True until you trust it.
STOP_AFTER_FLEE = True

# Wait for mana rather than spamming failed casts. The script pauses until it
# has enough for the next spell.
WAIT_FOR_MANA = True
MANA_WAIT_TIMEOUT_MS = 60000


# =============================================================================
# 7. TIMING  -  all values in milliseconds
# =============================================================================

SPAWN_POLL_MS = 1500            # how often to look for the monster
FIGHT_POLL_MS = 200             # the main fight tick
MOVE_PAUSE_MS = 250             # between movement steps
CAST_TIMEOUT_MS = 5000          # how long to wait for the targeting cursor
CAST_SETTLE_MS = 400            # after the cursor opens, before answering it
AFTER_CAST_MS = 1500            # recovery between casts
TARGET_PROPS_MS = 1000          # how long to wait for a creature's tooltip

# Walking. Beyond PATHFIND_MIN_DIST tiles the pathfinder is used; inside it the
# script single-steps, because PathFinding refuses a tile something is standing
# on - and a corpse tile very often has something on it.
PATHFIND_MIN_DIST = 8           # tiles
STUCK_LIMIT = 8                 # identical positions before calling it stuck

# Give up on a single fight after this long and go back to waiting.
FIGHT_TIMEOUT_MS = 10 * 60 * 1000

DEBUG = True


# #############################################################################
# ##                          END OF CONFIG                                  ##
# #############################################################################

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

# Server replies worth reacting to. Annotated with the cliloc they came from so
# they can be checked against shard source.
MSG_OUT_OF_RANGE = [
    "That is too far away",                       # 500237
    "Target is not in line of sight",             # 500237 / 501943
    "You cannot see that",
]
MSG_NO_MANA = [
    "You do not have enough mana",                # 502625
    "Insufficient mana",
]
MSG_FIZZLE = [
    "The spell fizzles",                          # 502632
    "You have not yet recovered",                 # 502644
]

_journal_cursor = 0.0
_camp = None            # where the script was started
_last_corpse = None     # the corpse that confirmed the kill

SCHOOLS = {
    "magery":       "CastMagery",
    "necro":        "CastNecro",
    "chivalry":     "CastChivalry",
    "bushido":      "CastBushido",
    "ninjitsu":     "CastNinjitsu",
    "spellweaving": "CastSpellweaving",
    "mysticism":    "CastMysticism",
    "mastery":      "CastMastery",
    "cleric":       "CastCleric",
    "druid":        "CastDruid",
}


# =============================================================================
# LOGGING
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[COV] " + text, hue, False)


def debug(text, hue=HUE_INFO):
    if DEBUG:
        log(text, hue)


def say(text):
    """Speak in game - used for the shard's loot command, not for spells."""
    if not text:
        return
    try:
        Player.ChatSay(SPEECH_HUE, text)
    except TypeError:
        # Older builds only accept ChatSay(msg).
        Player.ChatSay(text)
    except Exception as exc:
        log("Could not say %r (%s)." % (text, exc), HUE_BAD)


# =============================================================================
# JOURNAL  -  timestamp cursor, so the journal is never wiped
# =============================================================================

def reset_journal():
    global _journal_cursor
    newest = 0.0
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            if entry.Timestamp > newest:
                newest = entry.Timestamp
    except Exception:
        pass
    _journal_cursor = newest


def new_lines():
    """Journal lines since the last call, lowercased."""
    global _journal_cursor
    out = []
    try:
        entries = Journal.GetJournalEntry(_journal_cursor) or []
    except Exception:
        return out
    for entry in entries:
        try:
            stamp = entry.Timestamp
        except Exception:
            continue
        if stamp <= _journal_cursor:
            continue
        _journal_cursor = max(_journal_cursor, stamp)
        if entry.Text:
            out.append(entry.Text.lower())
    return out


def lines_match(lines, phrases):
    for line in lines:
        for phrase in phrases:
            if phrase.strip().lower() in line:
                return phrase
    return None


# =============================================================================
# GEOMETRY AND MOVEMENT
# =============================================================================

def distance_to(mob):
    if not mob:
        return float("inf")
    try:
        return Player.DistanceTo(mob)
    except Exception:
        dx = Player.Position.X - mob.Position.X
        dy = Player.Position.Y - mob.Position.Y
        return math.sqrt(dx * dx + dy * dy)


def direction_name(dx, dy):
    """UO directions. X grows EAST, Y grows SOUTH."""
    if dx > 0 and dy < 0:
        return "Right"      # NE
    if dx > 0 and dy > 0:
        return "Down"       # SE
    if dx < 0 and dy > 0:
        return "Left"       # SW
    if dx < 0 and dy < 0:
        return "Up"         # NW
    if dx > 0:
        return "East"
    if dx < 0:
        return "West"
    if dy > 0:
        return "South"
    return "North"


def step(direction):
    """One step. Player.Run takes one argument on current builds; older ones
    took two, so tolerate both rather than picking a side."""
    try:
        return Player.Run(direction)
    except TypeError:
        return Player.Run(direction, True)
    except Exception:
        return False


def step_away_from(mob):
    dx = Player.Position.X - mob.Position.X
    dy = Player.Position.Y - mob.Position.Y
    if dx == 0 and dy == 0:
        return step("North")        # standing on it; any direction will do
    return step(direction_name(dx, dy))


def step_toward(mob):
    dx = mob.Position.X - Player.Position.X
    dy = mob.Position.Y - Player.Position.Y
    if dx == 0 and dy == 0:
        return False
    return step(direction_name(dx, dy))


def hold_distance(mob):
    """One correction step. True if we are in the band and can cast."""
    gap = distance_to(mob)

    if gap < DISTANCE_MIN:
        step_away_from(mob)
        Misc.Pause(MOVE_PAUSE_MS)
        return False
    if gap > DISTANCE_MAX:
        step_toward(mob)
        Misc.Pause(MOVE_PAUSE_MS)
        return False
    return gap <= MAX_CAST_DISTANCE


def enforce_distance(serial):
    """Correct the standoff once, wherever we are called from.

    This parks you at DISTANCE_MAX - the FAR edge of the band - rather than
    anywhere inside it, and that matters against something that moves as fast
    as you do. Reacting only once the floor is already breached means the
    monster takes a tile, you take it back, it takes it again: the gap ends up
    sitting a tile INSIDE the floor permanently. Holding the far edge instead
    leaves a full tile of slack for it to eat before DISTANCE_MIN is touched.

    Safe to call in the middle of anything - it only ever takes a single step,
    and it settles once the gap is right rather than jittering. Returns False
    when the monster is gone or we are dead.
    """
    if Player.IsGhost:
        return False
    mob = Mobiles.FindBySerial(serial)
    if mob is None:
        return False
    gap = distance_to(mob)
    if gap < DISTANCE_MAX:
        step_away_from(mob)
    elif gap > DISTANCE_MAX:
        step_toward(mob)
    return True


def kite_pause(serial, milliseconds):
    """Wait, but keep holding the standoff the whole time.

    Every long pause in the fight goes through this. A plain Misc.Pause means
    the monster is free to walk into melee range while the script sits there
    doing nothing about it, which is exactly what "stay 5 tiles away at all
    times" rules out.
    """
    deadline = time.time() + max(0, milliseconds) / 1000.0
    while time.time() < deadline:
        if not enforce_distance(serial):
            return False
        Misc.Pause(KITE_TICK_MS)
    return True


def wait_for_cursor(serial, timeout_ms):
    """Wait for the targeting cursor WITHOUT standing still for it.

    Target.WaitForTarget blocks, so asking it for the whole timeout in one go
    would leave the standoff unmanaged for up to CAST_TIMEOUT_MS. Ask in short
    slices instead and correct the distance between each one.
    """
    deadline = time.time() + max(0, timeout_ms) / 1000.0
    while time.time() < deadline:
        if Target.WaitForTarget(KITE_TICK_MS, False):
            return True
        if not enforce_distance(serial):
            return False
    return Target.HasTarget()


def flee_from(mob):
    """Put real distance between us and it."""
    log("Breaking off - running to %d tiles." % FLEE_DISTANCE, HUE_BAD)
    deadline = time.time() + 20.0
    while time.time() < deadline:
        fresh = Mobiles.FindBySerial(mob.Serial)
        if fresh is None:
            return True
        if distance_to(fresh) >= FLEE_DISTANCE:
            return True
        step_away_from(fresh)
        Misc.Pause(MOVE_PAUSE_MS)
    return False


def distance_to_point(x, y):
    return max(abs(Player.Position.X - x), abs(Player.Position.Y - y))


def step_toward_point(x, y):
    dx = x - Player.Position.X
    dy = y - Player.Position.Y
    if dx == 0 and dy == 0:
        return False
    return step(direction_name(dx, dy))


def pathfind_to(x, y):
    try:
        route = PathFinding.Route()
        route.X = x
        route.Y = y
        route.MaxRetry = 2
        route.StopIfStuck = True
        route.IgnoreMobile = True
        route.UseResync = True
        route.DebugMessage = False
        return PathFinding.Go(route)
    except Exception as exc:
        debug("Pathfinding failed: %s" % exc, HUE_WARN)
        return False


def walk_to_point(x, y, tolerance, timeout_ms, label="destination"):
    """Walk to a tile. True if we got within `tolerance`.

    Pathfinds while far away and single-steps once close, because PathFinding
    refuses a tile that something is standing on - and a corpse tile very often
    has something on it.
    """
    deadline = time.time() + timeout_ms / 1000.0
    last = None
    stuck = 0

    while time.time() < deadline:
        if Player.IsGhost:
            return False
        gap = distance_to_point(x, y)
        if gap <= tolerance:
            return True

        if gap > PATHFIND_MIN_DIST:
            pathfind_to(x, y)
        else:
            step_toward_point(x, y)

        here = (Player.Position.X, Player.Position.Y)
        if here == last:
            stuck += 1
            if stuck >= STUCK_LIMIT:
                debug("Stuck walking to %s at %d tiles." % (label, gap),
                      HUE_WARN)
                return gap <= tolerance + 1
        else:
            stuck = 0
            last = here
        Misc.Pause(MOVE_PAUSE_MS)

    debug("Timed out walking to %s." % label, HUE_WARN)
    return distance_to_point(x, y) <= tolerance


# =============================================================================
# LOOTING
# =============================================================================

def loot_corpse(corpse):
    """Walk onto the corpse and let the shard's grab command empty it.

    The corpse vanishing is the success signal. If it does not vanish that is
    reported but NOT treated as a failure worth stopping for - it usually just
    means something in it was not on the player's grab list.
    """
    if not LOOT_CORPSE:
        return False

    serial = corpse.Serial
    x, y = corpse.Position.X, corpse.Position.Y
    log("Looting the corpse at %d, %d." % (x, y), HUE_INFO)

    if not walk_to_point(x, y, LOOT_DISTANCE, LOOT_APPROACH_TIMEOUT, "corpse"):
        log("Could not reach the corpse - leaving it.", HUE_WARN)
        return False

    for attempt in range(1, LOOT_RETRIES + 1):
        if Items.FindBySerial(serial) is None:
            log("Corpse is gone - loot taken.", HUE_GOOD)
            return True

        say(LOOT_COMMAND)
        Misc.Pause(LOOT_RESULT_MS)

        if Items.FindBySerial(serial) is None:
            log("Corpse is gone - loot taken.", HUE_GOOD)
            return True
        debug("Corpse still there after %r (%d/%d)."
              % (LOOT_COMMAND, attempt, LOOT_RETRIES), HUE_WARN)

    log("Corpse did not disappear. Whatever is left is not on your grab "
        "list - carrying on.", HUE_WARN)
    return False


def return_to_camp():
    """Walk back to where the script was started.

    Kiting moves us during the fight and the corpse is somewhere else again,
    so without this the camp creeps away from the spot the player chose.
    """
    if not RETURN_TO_CAMP or _camp is None:
        return True
    x, y = _camp
    if distance_to_point(x, y) <= CAMP_TOLERANCE:
        return True
    log("Returning to camp at %d, %d." % (x, y), HUE_INFO)
    ok = walk_to_point(x, y, CAMP_TOLERANCE, CAMP_RETURN_TIMEOUT, "camp")
    if not ok:
        log("Could not get back to camp - carrying on from here.", HUE_WARN)
    return ok


# =============================================================================
# FINDING THE MONSTER
# =============================================================================

def name_matches(mob):
    """The NAME decides. A matching body is not enough to act on."""
    name = mob.Name
    if not name:
        try:
            Mobiles.WaitForProps(mob, TARGET_PROPS_MS)
            fresh = Mobiles.FindBySerial(mob.Serial)
            if fresh is not None:
                name = fresh.Name
        except Exception:
            pass
    if not name:
        return False
    return TARGET_NAME.strip().lower() in name.lower()


def find_target():
    """The monster, or None. Nearest first if several are up."""
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = SCAN_RANGE          # never leave this unset
    f.CheckIgnoreObject = False
    for body in TARGET_BODIES:
        f.Bodies.Add(body)

    try:
        found = Mobiles.ApplyFilter(f) or []
    except Exception as exc:
        debug("Scan failed: %s" % exc, HUE_WARN)
        return None

    candidates = []
    for mob in found:
        if TARGET_NOTORIETY is not None:
            try:
                if mob.Notoriety != TARGET_NOTORIETY:
                    continue
            except Exception:
                pass
        if not name_matches(mob):
            continue
        candidates.append(mob)

    if not candidates:
        return None
    candidates.sort(key=distance_to)
    return candidates[0]


def mobile_present(serial):
    """Is the monster still in Razor's mobile list?

    NOT the same question as "is it alive". It also goes missing when it walks
    out of range or line of sight, which is why this is only ever one half of
    the death check.
    """
    return Mobiles.FindBySerial(serial) is not None


def corpses_in_range():
    """Every corpse on the ground near us."""
    out = []
    try:
        f = Items.Filter()
        f.Enabled = True
        f.RangeMax = CORPSE_SEARCH_RANGE      # never leave this unset
        f.OnGround = 1
        found = Items.ApplyFilter(f) or []
    except Exception as exc:
        debug("Corpse scan failed: %s" % exc, HUE_WARN)
        return out

    for item in found:
        try:
            is_corpse = item.ItemID in CORPSE_IDS
            if not is_corpse:
                is_corpse = bool(getattr(item, "IsCorpse", False))
            if is_corpse:
                out.append(item)
        except Exception:
            continue
    return out


def snapshot_corpses():
    """Serials of the corpses already lying here BEFORE the fight starts.

    Without this the script would read the previous kill's corpse - they last
    for minutes - and declare the fresh spawn dead the instant it engaged.
    """
    known = {}
    for corpse in corpses_in_range():
        known[corpse.Serial] = True
    if known:
        debug("%d corpse(s) already here; they will not count as a kill."
              % len(known))
    return known


def corpse_matches(item, body):
    """Is this corpse the monster's? Name or body value, either will do."""
    try:
        name = (item.Name or "").lower()
    except Exception:
        name = ""

    if CORPSE_NAME_HINT and CORPSE_NAME_HINT.strip().lower() in name:
        return True

    # A corpse's Amount carries the body of whatever died - 741 is 0x2E5.
    if CORPSE_MATCH_BODY and body:
        try:
            if item.Amount == body:
                return True
        except Exception:
            pass
    return False


def find_new_corpse(known, body):
    """A corpse that was NOT here when the fight began. The proof of a kill."""
    for corpse in corpses_in_range():
        if corpse.Serial in known:
            continue
        if corpse_matches(corpse, body):
            return corpse
    return None


# =============================================================================
# CASTING
# =============================================================================

def clear_cursor():
    """Drop a stale cursor before every cast.

    Target.WaitForTarget returns True for a cursor that is ALREADY open, so a
    leaked one silently swallows the next TargetExecute and the cast looks like
    it simply did nothing.
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


def start_cast(spell):
    """Begin the cast, no target attached. Returns False if it could not."""
    name = spell["name"]
    school = (spell.get("school") or "auto").strip().lower()

    try:
        if school in SCHOOLS:
            getattr(Spells, SCHOOLS[school])(name)
        else:
            Spells.Cast(name)
        return True
    except Exception as exc:
        log("Could not cast %r (%s)." % (name, exc), HUE_BAD)
        log("Check the spell name and its \"school\" in section 2.", HUE_WARN)
        return False


def cast_at(spell, mob):
    """Cast one spell at the monster. Returns "ok", "range", "mana" or "fail".

    Deliberately casts WITHOUT a target and answers the cursor by hand. The
    built-in one-shot target form is documented as unreliable on free shards,
    and the manual sequence - clear the cursor, cast, wait, settle, answer - is
    the one confirmed working on this shard.
    """
    if spell.get("mana") and Player.Mana < spell["mana"]:
        return "mana"

    if not clear_cursor():
        log("A target cursor is stuck open; cannot cast cleanly.", HUE_BAD)
        return "fail"

    new_lines()                       # start this cast with a clean read
    if not start_cast(spell):
        return "fail"

    # Kites while it waits - the monster keeps walking during the cast.
    if not wait_for_cursor(mob.Serial, CAST_TIMEOUT_MS):
        said = lines_match(new_lines(), MSG_NO_MANA)
        clear_cursor()                # or it survives into the next cast
        if said:
            return "mana"
        debug("%s: no target cursor appeared." % spell["name"], HUE_WARN)
        return "fail"

    kite_pause(mob.Serial, CAST_SETTLE_MS)

    mode = (spell.get("target") or "mobile").strip().lower()
    fresh = Mobiles.FindBySerial(mob.Serial)
    if fresh is None:
        clear_cursor()
        return "ok"                   # it died mid-cast; nothing to aim at

    try:
        if mode == "location":
            Target.TargetExecute(fresh.Position.X, fresh.Position.Y,
                                 fresh.Position.Z)
        else:
            Target.TargetExecute(fresh.Serial)
    except Exception as exc:
        log("Targeting failed (%s)." % exc, HUE_BAD)
        clear_cursor()
        return "fail"

    # Recovery between casts is the longest window of the lot, so it kites too.
    kite_pause(mob.Serial, AFTER_CAST_MS)

    lines = new_lines()
    if lines_match(lines, MSG_OUT_OF_RANGE):
        return "range"
    if lines_match(lines, MSG_NO_MANA):
        return "mana"
    if lines_match(lines, MSG_FIZZLE):
        return "fail"
    return "ok"


def wait_for_mana(spell, mob):
    """Hold position and distance until there is mana for the next cast."""
    need = spell.get("mana") or 0
    if not WAIT_FOR_MANA or Player.Mana >= need:
        return Player.Mana >= need

    log("Out of mana - holding at range until it comes back.", HUE_WARN)
    deadline = time.time() + MANA_WAIT_TIMEOUT_MS / 1000.0
    while time.time() < deadline:
        if Player.IsGhost:
            return False
        fresh = Mobiles.FindBySerial(mob.Serial)
        if fresh is None:
            return False
        hold_distance(fresh)          # keep kiting rather than standing still
        if Player.Mana >= need:
            return True
        Misc.Pause(FIGHT_POLL_MS)
    log("Still no mana after %d seconds." % (MANA_WAIT_TIMEOUT_MS / 1000),
        HUE_BAD)
    return False


# =============================================================================
# THE FIGHT
# =============================================================================

def hits_percent():
    try:
        if Player.HitsMax > 0:
            return 100.0 * Player.Hits / Player.HitsMax
    except Exception:
        pass
    return 100.0


def should_flee():
    return FLEE_AT_HITS_PERCENT > 0 and hits_percent() < FLEE_AT_HITS_PERCENT


def fight(mob):
    """Work one monster until it dies, we break off, or time runs out."""
    serial = mob.Serial
    body = mob.Body
    log("Engaging %s at %d tiles." % (mob.Name or "target", distance_to(mob)),
        HUE_GOOD)

    # Anything already on the floor is last spawn's, and must never be read as
    # proof that THIS one died.
    known_corpses = snapshot_corpses()

    deadline = time.time() + FIGHT_TIMEOUT_MS / 1000.0
    opened = False
    last_opener = 0.0
    missing_since = None

    while time.time() < deadline:
        if Player.IsGhost:
            log("You are dead. Stopping.", HUE_BAD)
            return "dead"

        # A corpse is the ONLY thing that counts as a kill.
        corpse = find_new_corpse(known_corpses, body)
        if corpse is not None:
            global _last_corpse
            _last_corpse = corpse
            log("%s is dead - corpse confirmed (%s)."
                % (TARGET_NAME, corpse.Name or "0x%X" % corpse.Serial),
                HUE_GOOD)
            return "killed"

        current = Mobiles.FindBySerial(serial)
        if current is None:
            # Gone from the mobile list. That is NOT death - it also happens
            # when it steps out of range or behind something. Wait a moment for
            # a corpse to settle the question.
            if missing_since is None:
                missing_since = time.time()
                debug("Lost sight of it - waiting for a corpse to confirm.",
                      HUE_WARN)
            elif (time.time() - missing_since) * 1000.0 >= CORPSE_GRACE_MS:
                log("It vanished and left no corpse - not dead, just out of "
                    "sight. Going back to waiting.", HUE_WARN)
                return "lost"
            Misc.Pause(FIGHT_POLL_MS)
            continue

        missing_since = None

        if should_flee():
            log("Health %.0f%% - below FLEE_AT_HITS_PERCENT." % hits_percent(),
                HUE_BAD)
            flee_from(current)
            return "fled"

        # Position first: there is no point casting from the wrong range.
        if not hold_distance(current):
            continue

        # The opener, then the attack spell on repeat.
        want_opener = not opened or (
            OPENER_RECAST_MS > 0 and
            (time.time() - last_opener) * 1000.0 >= OPENER_RECAST_MS)

        spell = SPELL_OPENER if want_opener else SPELL_ATTACK

        if spell.get("mana") and Player.Mana < spell["mana"]:
            if not wait_for_mana(spell, current):
                if Player.IsGhost or Mobiles.FindBySerial(serial) is None:
                    continue
                log("Cannot keep casting - stopping this fight.", HUE_BAD)
                return "nomana"
            continue

        result = cast_at(spell, current)

        if result == "ok":
            if want_opener:
                opened = True
                last_opener = time.time()
                debug("%s away." % spell["name"], HUE_GOOD)
        elif result == "range":
            debug("Out of range or line of sight - closing.", HUE_WARN)
            fresh = Mobiles.FindBySerial(serial)
            if fresh is not None:
                step_toward(fresh)
                Misc.Pause(MOVE_PAUSE_MS)
        elif result == "mana":
            if not wait_for_mana(spell, current):
                if Player.IsGhost or Mobiles.FindBySerial(serial) is None:
                    continue
                return "nomana"
        else:
            Misc.Pause(FIGHT_POLL_MS)

    log("Fight timed out after %d minutes." % (FIGHT_TIMEOUT_MS / 60000),
        HUE_WARN)
    return "timeout"


# =============================================================================
# MAIN
# =============================================================================

def preflight():
    log("COVFarm v%s" % SCRIPT_VERSION, HUE_STEP)

    if not TARGET_NAME.strip():
        log("TARGET_NAME is empty - nothing to hunt.", HUE_BAD)
        return False

    log("Hunting: %r  bodies %s  notoriety %s"
        % (TARGET_NAME,
           ["0x%X" % b for b in TARGET_BODIES] or "(name only)",
           TARGET_NOTORIETY if TARGET_NOTORIETY is not None else "any"))
    log("Opener: %s (%s, %s)  Attack: %s (%s, %s)"
        % (SPELL_OPENER["name"], SPELL_OPENER["school"],
           SPELL_OPENER["target"],
           SPELL_ATTACK["name"], SPELL_ATTACK["school"],
           SPELL_ATTACK["target"]))
    if DISTANCE_MIN >= DISTANCE_MAX:
        log("DISTANCE_MIN (%d) must be BELOW DISTANCE_MAX (%d) - with no band "
            "to sit in the character jitters on the spot."
            % (DISTANCE_MIN, DISTANCE_MAX), HUE_BAD)
        return False

    log("Holding %d-%d tiles, re-checked every %dms including mid-cast."
        % (DISTANCE_MIN, DISTANCE_MAX, KITE_TICK_MS))
    if FLEE_AT_HITS_PERCENT > 0:
        log("Will break off below %d%% health." % FLEE_AT_HITS_PERCENT)
    else:
        log("FLEE_AT_HITS_PERCENT is 0 - it will NEVER break off.", HUE_WARN)

    if Player.IsGhost:
        log("You are dead. Resurrect first.", HUE_BAD)
        return False
    return True


def main():
    if not preflight():
        return

    reset_journal()

    global _camp
    _camp = (Player.Position.X, Player.Position.Y)
    if RETURN_TO_CAMP:
        log("Camp is %d, %d - will come back here after each kill." % _camp)

    log("Waiting for %s to spawn..." % TARGET_NAME, HUE_INFO)

    waiting_logged = True
    while True:
        Misc.Pause(SPAWN_POLL_MS)      # never busy-wait

        if Player.IsGhost:
            log("You are dead. Stopping.", HUE_BAD)
            return

        mob = find_target()
        if mob is None:
            if not waiting_logged:
                log("Waiting for %s to spawn..." % TARGET_NAME, HUE_INFO)
                waiting_logged = True
            continue

        waiting_logged = False
        outcome = fight(mob)

        if outcome == "killed" and _last_corpse is not None:
            loot_corpse(_last_corpse)
            return_to_camp()

        if outcome in ("dead",):
            return
        if outcome == "fled" and STOP_AFTER_FLEE:
            log("Stopped after breaking off. Set STOP_AFTER_FLEE = False to "
                "keep farming.", HUE_WARN)
            return
        if outcome == "nomana":
            log("Stopping - could not keep casting.", HUE_BAD)
            return
        if outcome == "lost":
            log("Re-acquiring - it may still be up.", HUE_WARN)
        elif outcome == "timeout":
            log("Giving up on that one and looking again.", HUE_WARN)

        Misc.Pause(2000)


main()
