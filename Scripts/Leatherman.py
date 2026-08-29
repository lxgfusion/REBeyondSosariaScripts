"""
Leatherman - kill cows, carve them, take the leather.
=====================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

Kills the animals you name, butchers the corpses, sweeps up what falls out and
pushes it into your storage keys. Written for cows and leather; the species
list is config, so anything with a name and a body works.

The round
---------
    find a named animal -> walk into spell range -> cast until it dies
    -> walk TO the corpse -> carve it -> say the loot command -> store

What it will not do
-------------------
It never attacks anything whose NAME is not on the list. HARVEST_BODIES is a
cheap filter that finds candidates worth naming; the name is what decides.
Bodies are shared between species and have been wrong in extracted data before
- a stray 0x3 in a sheep entry once had a sister script walking up to zombies.

It never carves a corpse it did not make. Somebody else's corpse is somebody
else's loot.

Two things that are not obvious
-------------------------------
1. A mobile the client has never queried reports Hits = 0 AND HitsMax = 0.
   That means UNKNOWN, not dead. Reading it as dead makes the kill loop return
   before casting once - it logs "Killing a cow", casts nothing, walks to no
   corpse, and still runs the carve-and-store tail, so a storage key fires over
   an animal standing there unharmed. Mobiles.WaitForStats is asked first, and
   Hits is only believed once HitsMax says the status is known.

2. Carving happens NEXT TO the corpse; the kill happens at spell range. They
   are different distances. Searching a few tiles from where something died ten
   tiles away finds nothing, and says nothing.

Notes
-----
- The loot command is rate-limited by the shard. See HARVEST_GRAB_COOLDOWN_MS:
  said sooner it is silently refused and the loot stays on the ground.
- Creatures ruled out go on Razor's global ignore list. Misc.ClearIgnore() or
  a restart resets it.
"""

import time


# Printed as the first line at startup. Bump it with every change that goes
# out - Razor caches the loaded script even after the file on disk changes, so
# if this does not say what you expect, hit Reload in the Scripting tab.
SCRIPT_VERSION = "2026-08-22.1"


# =============================================================================
# CONFIG
# =============================================================================

DEBUG = False                     # extra detail in the journal

HUE_INFO = 90
HUE_GOOD = 68
HUE_WARN = 43
HUE_BAD = 33

# Approach guards, carried over verbatim from the tamer so walking behaves
# identically - these were tuned against this shard, not chosen here.
APPROACH_TIMEOUT = 30000   # ms to spend walking to a creature
MOVE_PAUSE = 250           # pause between movement steps
PATHFIND_MIN_DIST = 8      # A* beyond this, single-steps inside it
SETTLE_STEPS = 6           # steps at the fallback distance before accepting it
STALL_STEPS = 40           # steps without getting any closer before giving up
STAY_DIST = 1              # distance to hold once adjacent
STUCK_LIMIT = 8            # identical-position steps before declaring unreachable
PROPS_TIMEOUT = 1500       # ms to wait for a tooltip

# ---------------------------------------------------------------------------
# COW HARVEST - kill, carve, loot, store
#
# Species listed here are KILLED AND BUTCHERED rather than tamed. This is the
# "attacking half" the KILL_ON_SIGHT note above says was never written; it is
# deliberately scoped to one job rather than made general, because a script
# that decides for itself what to attack is a different and much riskier thing.
#
# The round is: cast at it until it dies -> carve the corpse with a dagger ->
# say the loot command -> push what came out into the two storage keys.
#
# HARVEST TAKES PRECEDENCE OVER TAMING. If you are holding a taming deed for
# something in HARVEST_WORDS, the script kills it instead of taming it and says
# so at startup - it cannot do both, and silently picking one would be worse.
HARVEST_ENABLED = True

# Matched as a substring of the creature's NAME, which is what decides. The
# bodies below are only the cheap filter that finds candidates to name-check -
# see CLAUDE.md: a body value must never be the sole authority.
HARVEST_WORDS = ["cow"]

# From the catalogue above: ("cow", [0xD8, 0xE7], 11.1). Bodies are shared
# between species, which is exactly why the name is checked afterwards.
HARVEST_BODIES = [0xD8, 0xE7]

# How far to look for something to harvest.
HARVEST_RANGE = 12

# How close to stand before casting. Magic Arrow reaches about 10 tiles, so
# this leaves room for a cow to wander a step without walking out of range.
# Kept under HARVEST_RANGE deliberately: that one is the give-up distance.
HARVEST_APPROACH = 8

# The spell. Magic Arrow is in SPELL_TABLE as magery/fire/base 10 - cheap, and
# a cow has 10 physical resist and nothing else, so anything bigger is wasted
# mana. It is REQUIRED - there is no "pick something sensible" fallback here,
# because that lived in the tamer's spell table and did not come across. A
# blank spell is refused at startup rather than silently casting nothing.
HARVEST_SPELL = "Magic Arrow"
HARVEST_SPELL_SCHOOL = "magery"
HARVEST_SPELL_MANA = 4            # Magic Arrow's cost; waited for before casting

HARVEST_MAX_CASTS = 15            # ceiling per creature, so a miss cannot spin
HARVEST_CAST_MS = 2200            # between casts, for the cast plus recovery
HARVEST_DEATH_MS = 20000          # give up on one creature after this long
HARVEST_MANA_WAIT_MS = 30000      # longest to stand waiting for mana

# The knife. Serial first - it is exact - with the graphic as the fallback for
# when the blade wears out and is replaced.
HARVEST_DAGGER_SERIAL = 0
HARVEST_DAGGER_ID = 0x0F52

# Said after carving, to sweep the loot up off the ground.
HARVEST_GRAB_PHRASE = "[grab"
HARVEST_GRAB_HUE = 37
HARVEST_GRAB_MS = 1500            # for the loot to arrive before storing

# THE SHARD RATE-LIMITS [grab TO ONCE EVERY THREE SECONDS. Said sooner it is
# simply refused, and the loot from that kill stays on the ground - silently,
# because nothing in the pack changed to say otherwise. Two cows dying close
# together is enough to hit this, so the wait is enforced here rather than
# hoped for: grab_loot() blocks out the remainder before speaking.
HARVEST_GRAB_COOLDOWN_MS = 3000

# Carving needs to be NEXT TO the corpse, but the kill happens at spell range -
# so the corpse has to be walked to first. These are two different distances
# and conflating them is why the first version silently carved nothing: it
# searched three tiles from where it had killed something ten tiles away.
HARVEST_CORPSE_RANGE = 2          # how close to stand to carve
HARVEST_CORPSE_SEARCH = 16        # how far to LOOK for our own corpse
HARVEST_CORPSE_WAIT_MS = 2500     # for the corpse to appear after the kill
HARVEST_CARVE_MS = 900

# ---------------------------------------------------------------------------
# STORAGE KEYS for what the butchering produces
#
# Both are single-clicked and answered with HARVEST_CONTEXT, the same way every
# other storage key on this shard works.
#
# Inspected 2026-08-22, both Blessed, 1 stone, and both sitting in a BAG inside
# the backpack rather than at its top level. That matters: Items.FindAllByID
# with a container serial walks that container's own Contains list one level
# deep, so a backpack-level search would never see either of them. The SERIAL
# is what finds them reliably (FindBySerial goes to the world item list, at any
# depth); the graphic fallback searches the world by range for the same reason.
#
#   Tailor Store     ItemID 0x0F9D, hue 0x0044 - takes the leather
#   Butcher's Hook   ItemID 0x26BB, hue 0x0697 - takes the meat
#
# Serials ship as 0 in the published copy; fill in your own, or leave 0 and let
# the graphic and name find them.
HARVEST_KEYS = [
    {"label": "Tailor Store", "enabled": True,
     "serial": 0, "id": 0x0F9D, "hue": 0x0044,
     "names": ["tailor"], "context": []},
    {"label": "Butcher's Hook", "enabled": True,
     "serial": 0, "id": 0x26BB, "hue": 0x0697,
     "names": ["butcher"], "context": []},
]

# The menu entry that empties the pack into a key. Exact match first, then a
# guarded substring.
HARVEST_CONTEXT = ["Refill from stock", "Fill from backpack"]

# Never answered, however well it matches. These sit on the same menus and they
# do not put things away.
HARVEST_CONTEXT_NEVER = ["empty", "destroy", "delete", "release", "dye",
                         "rename", "buy", "sell"]


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Tamer] " + text, hue, False)


def debug(text, hue=HUE_INFO):
    if DEBUG:
        log(text, hue)



def clear_cursor():
    """Drop any stale target cursor.

    Target.WaitForTarget returns True for a cursor that is already open, so a
    leftover one silently swallows the next TargetExecute - including the
    deed's.
    """
    Target.ClearQueue()
    if Target.HasTarget():
        Target.Cancel()
        Misc.Pause(200)
        Target.ClearQueue()
    return not Target.HasTarget()


def move(direction):
    """Run one step. Tolerates both the 1-arg and 2-arg Player.Run signatures."""
    try:
        return Player.Run(direction, True)
    except TypeError:
        return Player.Run(direction)


def direction_to(dx, dy):
    """UO Direction names. X grows east, Y grows south."""
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


def step_toward(mob):
    dx = mob.Position.X - Player.Position.X
    dy = mob.Position.Y - Player.Position.Y
    if dx == 0 and dy == 0:
        return False
    return move(direction_to(dx, dy))


def approach_tile(mob):
    """A tile one step short of the creature - its own tile is occupied."""
    dx = mob.Position.X - Player.Position.X
    dy = mob.Position.Y - Player.Position.Y
    ox = 0 if dx == 0 else (-1 if dx > 0 else 1)
    oy = 0 if dy == 0 else (-1 if dy > 0 else 1)
    return (mob.Position.X + ox, mob.Position.Y + oy)


def pathfind_to(x, y):
    route = PathFinding.Route()
    route.X = x
    route.Y = y
    route.MaxRetry = 2
    route.StopIfStuck = True
    route.IgnoreMobile = True
    route.UseResync = True
    route.DebugMessage = False
    return PathFinding.Go(route)


# =============================================================================
# SPECIES NAME MATCHING
# =============================================================================


def mob_name(mob):
    """The creature's name, asking the server for it if Razor has not got it."""
    if mob.Name:
        return mob.Name
    Mobiles.WaitForProps(mob, PROPS_TIMEOUT)
    fresh = Mobiles.FindBySerial(mob.Serial)
    if fresh is not None and fresh.Name:
        return fresh.Name
    Mobiles.SingleClick(mob)
    Misc.Pause(600)
    fresh = Mobiles.FindBySerial(mob.Serial)
    if fresh is not None and fresh.Name:
        return fresh.Name
    return None



def approach(serial, goal=None, accept=None):
    """Walk to within `goal` tiles of a mobile.

    `accept` is the fallback distance: if we get that close but cannot improve
    on it (a tree between us, a doorway, the creature circling), settle there
    rather than burning the whole timeout trying to touch it. Defaults to `goal`,
    i.e. no compromise.
    """
    if goal is None:
        goal = STAY_DIST
    if accept is None:
        accept = goal

    deadline = time.time() + APPROACH_TIMEOUT / 1000.0
    last_pos = None
    stuck = 0
    best = None
    stalled = 0

    while time.time() < deadline:
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            return False

        gap = Player.DistanceTo(mob)
        if gap <= goal:
            return True

        if best is None or gap < best:
            best = gap
            stalled = 0
        else:
            stalled += 1
            if gap <= accept and stalled >= SETTLE_STEPS:
                return True          # close enough, and not getting closer
            if stalled >= STALL_STEPS:
                return False

        if gap > PATHFIND_MIN_DIST:
            tx, ty = approach_tile(mob)
            pathfind_to(tx, ty)
        else:
            step_toward(mob)

        pos = (Player.Position.X, Player.Position.Y)
        if pos == last_pos:
            stuck += 1
            if stuck >= STUCK_LIMIT:
                return gap <= accept
        else:
            stuck = 0
            last_pos = pos

        Misc.Pause(MOVE_PAUSE)

    return False


# =============================================================================
# COW HARVEST
# =============================================================================
# Kill, carve, loot, store. See the HARVEST_* config block for what and why.

# Corpses this script created, so nothing else's kill gets carved. Serials of
# the creatures killed; a corpse is matched to one by its own serial, which UO
# derives from the mobile's.
_harvest_corpses = []

# When [grab was last said, so the shard's three-second limit is honoured.
# 0.0 means "never", which is always far enough in the past.
_last_grab = [0.0]


def is_harvest_target(name):
    """Whether this creature is one to kill and butcher rather than tame.

    The NAME decides. HARVEST_BODIES only narrows the search down to things
    worth naming - bodies are shared between species and have been wrong in
    extracted data before.
    """
    low = (name or "").strip().lower()
    if not low:
        return False
    for word in HARVEST_WORDS:
        word = word.strip().lower()
        if word and word in low:
            return True
    return False


def harvest_candidates():
    """Harvestable creatures in range, nearest first, ignore-list respected."""
    if not HARVEST_ENABLED or not HARVEST_BODIES:
        return []
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = HARVEST_RANGE
    f.CheckIgnoreObject = True
    for body in HARVEST_BODIES:
        f.Bodies.Add(body)
    found = Mobiles.ApplyFilter(f)
    if not found:
        return []

    # Name-checked, always. A body match alone is not enough to kill something.
    named = []
    for mob in list(found):
        if getattr(mob, "IsGhost", False):
            continue
        if is_harvest_target(mob_name(mob)):
            named.append(mob)
    named.sort(key=lambda m: Player.DistanceTo(m))
    return named


def harvest_context_blocked(label):
    low = (label or "").strip().lower()
    return any(bad in low for bad in HARVEST_CONTEXT_NEVER)


def harvest_context_select(entity, wanted, label_for_log):
    """Open a context menu and pick the first configured entry.

    EXACT match first and always honoured - it was configured deliberately.
    Only then a substring match, which refuses anything on
    HARVEST_CONTEXT_NEVER. The REAL label is sent back, never a position: a
    menu that gains an entry would otherwise answer something else entirely.
    """
    try:
        entries = Misc.WaitForContext(entity, 10000, False)
    except Exception as err:
        log("%s: context menu raised %r." % (label_for_log, err), HUE_WARN)
        return False
    if not entries:
        log("%s gave no context menu." % label_for_log, HUE_WARN)
        return False

    labels = []
    for entry in entries:
        text = getattr(entry, "Entry", None)
        labels.append(text if text is not None else str(entry))
    debug("%s menu: %s" % (label_for_log, " | ".join(labels)))

    def reply(text):
        Misc.Pause(100)
        Misc.ContextReply(entity, text)
        Misc.Pause(600)
        return True

    for want in wanted:
        target = want.strip().lower()
        for text in labels:
            if (text or "").strip().lower() == target:
                return reply(text)
    for want in wanted:
        target = want.strip().lower()
        if not target:
            continue
        for text in labels:
            if target in (text or "").lower():
                if harvest_context_blocked(text):
                    debug("Refusing '%s' - it is on HARVEST_CONTEXT_NEVER."
                          % text, HUE_WARN)
                    continue
                return reply(text)

    log("%s has no entry matching %s - it offers: %s"
        % (label_for_log, wanted, " | ".join(labels)), HUE_BAD)
    return False


def find_stock_key(spec):
    """A storage key's item, or None.

    Serial first: FindBySerial goes to the world item list, so it finds the key
    at any depth. Both of these live in a BAG inside the pack, and a
    backpack-level graphic search walks only the pack's own Contains - it would
    never see either of them. That is why the fallback searches the world by
    range instead of the backpack.
    """
    serial = int(spec.get("serial") or 0)
    if serial:
        item = Items.FindBySerial(serial)
        if item is not None:
            return item

    graphic = int(spec.get("id") or 0)
    if not graphic:
        return None
    hue = int(spec.get("hue", -1))
    try:
        found = Items.FindAllByID(graphic, hue, -1, 2, False)
    except Exception:
        found = []

    names = [n.lower() for n in (spec.get("names") or [])]
    for item in list(found or []):
        if not names:
            return item
        label = (getattr(item, "Name", "") or "").strip().lower()
        if any(n in label for n in names):
            return item
    return None


def store_harvest():
    """Offer the pack to every harvest key. Returns how many took a load.

    ONE reply per key - the menu entry empties the pack of everything that key
    accepts in a single action, so clicking once per item would be the same
    deposit repeated.
    """
    used = 0
    for spec in HARVEST_KEYS:
        if not spec.get("enabled", True):
            continue
        label = spec.get("label", "key")
        item = find_stock_key(spec)
        if item is None:
            log("%s NOT FOUND (serial 0x%X, id 0x%04X) - nothing of its will "
                "be stored." % (label, int(spec.get("serial") or 0),
                                int(spec.get("id") or 0)), HUE_WARN)
            continue
        wanted = list(spec.get("context") or []) + list(HARVEST_CONTEXT)
        if harvest_context_select(item, wanted, label):
            used += 1
            log("%s took the load." % label, HUE_GOOD)
    return used


def wait_for_mana(need, timeout_ms=None):
    """Stand still until there is mana for one cast. False if it never comes."""
    if timeout_ms is None:
        timeout_ms = HARVEST_MANA_WAIT_MS
    deadline = time.time() + timeout_ms / 1000.0
    said = False
    while time.time() < deadline:
        try:
            if int(Player.Mana or 0) >= int(need):
                return True
        except Exception:
            return True         # cannot read it - do not block on that
        if not said:
            said = True
            log("Waiting for mana (%s of %s needed)."
                % (Player.Mana, need), HUE_INFO)
        Misc.Pause(500)
    log("Still no mana after %ds - leaving this one." % (timeout_ms / 1000),
        HUE_WARN)
    return False


def cast_at(serial, spell, school):
    """One cast at one creature. False if the cursor never arrived.

    The manual sequence, not the built-in target: cancel any stale cursor,
    cast, wait for the cursor, settle, then target. CLAUDE.md records that the
    settle pause and the cancel are both REQUIRED on this shard, and that a
    leaked cursor is silently answered by the next TargetExecute.
    """
    if not clear_cursor():
        debug("Target cursor would not clear before casting.", HUE_WARN)
    try:
        if school == "magery":
            Spells.CastMagery(spell)
        elif school == "necromancy":
            Spells.CastNecro(spell)
        elif school == "spellweaving":
            Spells.CastSpellweaving(spell)
        elif school == "mysticism":
            Spells.CastMysticism(spell)
        else:
            log("Unknown spell school %r - not casting." % school, HUE_BAD)
            return False
    except Exception as err:
        log("Casting %s failed: %r" % (spell, err), HUE_BAD)
        return False

    if not Target.WaitForTarget(3000, True):
        # LOUD, not debug. Nothing else in the round says the cast never
        # happened, and a silent miss here looks exactly like a creature that
        # will not die - which is how the first version read as "it says it is
        # killing but nothing happens".
        log("No target cursor for %s - the cast did not go out. Check you can "
            "cast it and have the reagents." % spell, HUE_BAD)
        Target.Cancel()
        return False
    Misc.Pause(400)
    Target.TargetExecute(serial)
    return True


def creature_is_dead(mob):
    """Whether a creature we can still see is actually dead.

    Hits alone is NOT the test. A mobile the client has never queried reports
    Hits = 0 and HitsMax = 0, and 0 there means "nobody asked", not "no health
    left" - so this only believes Hits once HitsMax says the status is known.
    Anything else is reported as alive, because the cost of being wrong that
    way is one wasted cast and the cost of being wrong the other way is the
    whole kill silently not happening.
    """
    try:
        if bool(getattr(mob, "IsGhost", False)):
            return True
    except Exception:
        pass
    try:
        hits = int(getattr(mob, "Hits", 0) or 0)
        hits_max = int(getattr(mob, "HitsMax", 0) or 0)
    except Exception:
        return False
    if hits_max <= 0:
        return False        # status unknown - NOT a death
    return hits <= 0


def kill_target(serial, label):
    """Cast until it dies. "dead" / "gave up" / "gone".

    Death is read from the creature DISAPPEARING, not from the journal: the
    kill message varies and a missed match would have the script stand casting
    at a corpse.

    Hits is a cross-check, never the primary test, and only when HitsMax says
    the client actually knows the creature's status. A mobile nobody has
    queried reports Hits = 0, which means UNKNOWN and not dead - reading it as
    dead made this function return before casting a single time, on the very
    first pass. It logged "Killing a cow", cast nothing, walked to no corpse,
    and still ran the carve-and-store tail, which is why the Butcher's Hook
    fired over an animal that was standing there unharmed.
    """
    spell = HARVEST_SPELL
    school = HARVEST_SPELL_SCHOOL
    log("Killing %s with %s." % (label, spell), HUE_INFO)

    # ASK for the status before reading it. Without this the first Hits read is
    # 0 because nothing has ever queried this mobile.
    try:
        Mobiles.WaitForStats(serial, 1500)
    except Exception:
        pass

    deadline = time.time() + HARVEST_DEATH_MS / 1000.0
    casts = 0
    misses = [0]        # casts that never produced a cursor, in a row
    while casts < HARVEST_MAX_CASTS and time.time() < deadline:
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            log("%s is gone after %d cast(s) - dead." % (label, casts),
                HUE_GOOD)
            return "dead"
        if creature_is_dead(mob):
            log("%s is down after %d cast(s)." % (label, casts), HUE_GOOD)
            return "dead"

        if not wait_for_mana(HARVEST_SPELL_MANA):
            return "gave up"
        if Player.DistanceTo(mob) > HARVEST_RANGE:
            return "gone"

        if cast_at(serial, spell, school):
            casts += 1
            hits = getattr(mob, "Hits", "?")
            hits_max = getattr(mob, "HitsMax", "?")
            debug("%s: cast %d, %s/%s hits." % (label, casts, hits, hits_max))
        else:
            misses[0] += 1
            if misses[0] >= 3:
                log("%s: three casts in a row did not go out - stopping rather "
                    "than standing here." % label, HUE_BAD)
                return "gave up"
        Misc.Pause(HARVEST_CAST_MS)

    if Mobiles.FindBySerial(serial) is None:
        return "dead"
    log("%s is still up after %d cast(s) - leaving it." % (label, casts),
        HUE_WARN)
    return "gave up"


def find_dagger():
    """The carving blade, by serial then by graphic. None if there is none."""
    serial = int(HARVEST_DAGGER_SERIAL or 0)
    if serial:
        blade = Items.FindBySerial(serial)
        if blade is not None:
            return blade
    pack = Player.Backpack
    if pack is None:
        return None
    try:
        found = Items.FindAllByID(HARVEST_DAGGER_ID, -1, pack.Serial, -1, False)
    except Exception:
        found = []
    for blade in list(found or []):
        return blade
    return None


def corpse_in_sight():
    """Has one of our corpses appeared yet?"""
    f = Items.Filter()
    f.Enabled = True
    f.RangeMax = HARVEST_CORPSE_SEARCH
    f.IsCorpse = 1
    try:
        for corpse in list(Items.ApplyFilter(f) or []):
            if int(corpse.Serial) in _harvest_corpses:
                return True
    except Exception:
        pass
    return False


def carve_corpses():
    """Carve nearby corpses of things this script killed. Returns how many.

    Only corpses whose serial was recorded at the kill are touched. Somebody
    else's corpse is somebody else's loot, and carving it uninvited is both
    rude and a good way to draw attention.
    """
    if not _harvest_corpses:
        return 0
    blade = find_dagger()
    if blade is None:
        log("No dagger (serial 0x%X / id 0x%04X) - cannot carve."
            % (int(HARVEST_DAGGER_SERIAL or 0), HARVEST_DAGGER_ID), HUE_WARN)
        return 0

    f = Items.Filter()
    f.Enabled = True
    f.RangeMax = HARVEST_CORPSE_SEARCH
    f.IsCorpse = 1
    try:
        corpses = Items.ApplyFilter(f)
    except Exception as err:
        debug("Corpse search failed: %r" % (err,), HUE_WARN)
        return 0

    carved = 0
    for corpse in list(corpses or []):
        if int(corpse.Serial) not in _harvest_corpses:
            continue

        # WALK TO IT. The kill happens at spell range and carving does not
        # reach that far, so without this the dagger is used on something the
        # server says is too far away - and it says so once, quietly.
        if Player.DistanceTo(corpse) > HARVEST_CORPSE_RANGE:
            debug("Walking to the corpse at %d,%d."
                  % (corpse.Position.X, corpse.Position.Y))
            pathfind_to(corpse.Position.X, corpse.Position.Y)
            Misc.Pause(400)
            if Player.DistanceTo(corpse) > HARVEST_CORPSE_RANGE:
                log("Could not get to the corpse (%d tiles) - leaving it."
                    % Player.DistanceTo(corpse), HUE_WARN)
                continue

        if not clear_cursor():
            debug("Cursor would not clear before carving.", HUE_WARN)
        Items.UseItem(blade)
        if not Target.WaitForTarget(3000, True):
            debug("No cursor for the dagger.", HUE_WARN)
            Target.Cancel()
            break
        Misc.Pause(400)
        Target.TargetExecute(int(corpse.Serial))
        Misc.Pause(HARVEST_CARVE_MS)
        carved += 1
        try:
            _harvest_corpses.remove(int(corpse.Serial))
        except ValueError:
            pass
    if carved:
        log("Carved %d corpse(s)." % carved, HUE_GOOD)
    return carved


def grab_loot():
    """Say the loot command, never sooner than the shard allows.

    Waits out the remainder of HARVEST_GRAB_COOLDOWN_MS rather than skipping:
    the loot is already on the ground and skipping would leave it there. The
    wait is normally zero - killing and carving a cow takes longer than three
    seconds on its own - and only bites when two die together.
    """
    if not HARVEST_GRAB_PHRASE:
        return False
    waited = time.time() - _last_grab[0]
    remaining = HARVEST_GRAB_COOLDOWN_MS / 1000.0 - waited
    if remaining > 0:
        debug("Waiting %.1fs for the [grab cooldown." % remaining)
        Misc.Pause(int(remaining * 1000) + 50)
    Player.ChatSay(HARVEST_GRAB_HUE, HARVEST_GRAB_PHRASE)
    _last_grab[0] = time.time()
    Misc.Pause(HARVEST_GRAB_MS)
    return True


def harvest_pass():
    """One kill-carve-loot-store round. True if anything was harvested."""
    if not HARVEST_ENABLED:
        return False
    targets = harvest_candidates()
    if not targets:
        return False

    mob = targets[0]
    serial = int(mob.Serial)
    label = mob_name(mob) or "it"

    if not approach(serial, goal=HARVEST_APPROACH, accept=HARVEST_RANGE):
        debug("Could not get near %s." % label, HUE_WARN)
        Misc.IgnoreObject(serial)
        return False

    outcome = kill_target(serial, label)
    if outcome != "dead":
        Misc.IgnoreObject(serial)
        return False

    # A corpse carries the mobile's serial with the high bit cleared, but that
    # is a client-side convention rather than a promise - so BOTH are recorded
    # and carve_corpses matches on either.
    _harvest_corpses.append(serial)
    _harvest_corpses.append(serial & 0x7FFFFFFF)

    # The corpse does not exist the instant the creature does. Waiting for it
    # to turn up beats carving nothing and calling that done.
    deadline = time.time() + HARVEST_CORPSE_WAIT_MS / 1000.0
    while time.time() < deadline:
        if corpse_in_sight():
            break
        Misc.Pause(250)

    carve_corpses()

    grab_loot()

    store_harvest()
    Misc.IgnoreObject(serial)
    return True


# =============================================================================
# MAIN
# =============================================================================


# =============================================================================
# MAIN
# =============================================================================

def preflight():
    """Say what will happen and whether the pieces are there. False to stop."""
    log("Leatherman v%s" % SCRIPT_VERSION, HUE_GOOD)

    if Player.Backpack is None:
        log("No backpack - cannot run.", HUE_BAD)
        return False

    if not HARVEST_ENABLED:
        log("HARVEST_ENABLED is False - nothing to do.", HUE_BAD)
        return False
    if not HARVEST_WORDS:
        log("HARVEST_WORDS is empty, so nothing is a target. Nothing will be "
            "attacked.", HUE_BAD)
        return False
    if not HARVEST_BODIES:
        log("HARVEST_BODIES is empty, so nothing can be found. Add the body "
            "values for %s." % "/".join(HARVEST_WORDS), HUE_BAD)
        return False
    if not HARVEST_SPELL:
        log("HARVEST_SPELL is empty and there is no fallback in this script - "
            "set it to the spell you want cast.", HUE_BAD)
        return False

    log("Hunting: %s" % ", ".join(HARVEST_WORDS), HUE_INFO)
    log("  %s, carve with 0x%04X, then say %r."
        % (HARVEST_SPELL, HARVEST_DAGGER_ID,
           HARVEST_GRAB_PHRASE), HUE_INFO)

    blade = find_dagger()
    if blade is None:
        log("  No dagger (serial 0x%X / id 0x%04X) - corpses will not be "
            "carved. Put one in your pack."
            % (int(HARVEST_DAGGER_SERIAL or 0), HARVEST_DAGGER_ID), HUE_BAD)
    else:
        log("  Dagger 0x%X." % int(blade.Serial), HUE_GOOD)

    for spec in HARVEST_KEYS:
        if not spec.get("enabled", True):
            continue
        label = spec.get("label", "?")
        item = find_stock_key(spec)
        if item is None:
            log("  %-16s NOT FOUND (serial 0x%X, id 0x%04X) - set its serial."
                % (label, int(spec.get("serial") or 0),
                   int(spec.get("id") or 0)), HUE_BAD)
        else:
            log("  %-16s 0x%X, id 0x%04X hue 0x%04X"
                % (label, int(item.Serial), int(item.ItemID), int(item.Hue)),
                HUE_GOOD)

    log("Say nothing and stand clear - it starts now.", HUE_INFO)
    return True


def main():
    if not preflight():
        return

    killed = 0
    idle = 0
    while True:
        if Player.IsGhost:
            log("You are dead. Stopping.", HUE_BAD)
            return

        if harvest_pass():
            killed += 1
            idle = 0
            log("%d harvested this run." % killed, HUE_GOOD)
        else:
            idle += 1
            if idle % 20 == 0:
                log("Nothing to harvest in range. Still looking.", HUE_INFO)
            Misc.Pause(1000)

        Misc.Pause(500)


main()
