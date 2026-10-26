"""
FillTameDeeds - recall round the taming spots and fill every deed you carry.
===========================================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

Built from TameAndFill.py, keeping its deed reading, species matching, taming,
peacemaking and deed filling unchanged. The cow/goat butchering round is gone.

The round
---------
    open the Account Runebook ([ar) and go into the RUNEBOOK_FOLDER folder
    for every rune in it, on every page:
        recall, and check we landed on the rune's own coordinates
        kill anything hostile that is not a species you hold a deed for
        tame every deed species in range and put it in its deed
        move on once the spot has been quiet for SPOT_IDLE_MS
    wait LAP_PAUSE_MS for the spawn to come back, and go round again
    stop once there is no unfilled deed left in the pack

What gets killed
----------------
A creature is attacked only when ALL of these hold:

  * it is hostile by the tables below: HOSTILE_HITS / HOSTILE_BODIES came out
    of ServUO's own FightMode (tools/extract_hostiles.py), and
    OFFICIAL_HOSTILE_NAMES adds UOGuide's monster list for anything ServUO
    does not ship
  * its notoriety is attackable (grey, criminal, orange or red) - never blue
    or green, which is how players and other people's pets are kept out
  * it is not a species you hold an unfilled deed for - that is quarry
  * its tooltip does not say tame, bonded or summoned

Small things get Magic Arrow (the spell UO players call "magic missile");
anything with SPELL_BIG_HITS hit points or more, or anything the tables cannot
size, gets Energy Bolt. A Magic Arrow fight that is not getting anywhere is
upgraded to Energy Bolt mid-fight.

If your hit points drop below ESCAPE_HITS_PCT the script leaves through
ESCAPE_COMMAND, waits to heal, and carries on from the next rune.

How it decides what to tame
---------------------------
It reads the taming order deeds in your backpack, works out which species each
one is for, and hunts ONLY those. No deed for unicorns means unicorns are never
approached, never targeted, never tamed.

1. Scan the pack. For each deed, match its name/tooltip against a catalogue of
   112 tameable species (body values pulled from ServUO source).
2. Build the search filter from just those species' body values.
3. Chase the nearest match, tame it, and put it in that species' deed.
4. Rescan the pack after every success and every DEED_RESCAN_MS, so a deed that
   fills up drops out of the hunt list and a newly added one joins it.

Some bodies are shared by two species - a nightmare and a dread warhorse are
both body 0x74. For those the script also checks the creature's name before
touching it, and walks away if it cannot tell them apart. See AMBIGUOUS_BODIES.

Setup
-----
Put your taming order deeds in your backpack and run it. There are no prompts.

If nothing is found, the likely cause is DEED_NAME_HINTS: an item only counts as
a deed if its name or tooltip contains one of those words. Run
Scripts/diag_deeds.py to see exactly what the script reads from your pack.

Notes
-----
- Journal.Clear() runs before each taming attempt so stale messages cannot be
  read as the current result. Your journal gets wiped repeatedly.
- Creatures ruled out (already tame, owner cap, gender lock, unidentifiable) go
  on Razor's global ignore list. Misc.ClearIgnore() or a restart resets it.

TameAndFill.py stays as it is; this is a separate script, not a replacement.
"""

import re
import time


# Printed as the first line at startup. Bump it with every change that goes
# out, so the journal says which copy Razor actually loaded - Razor caches the
# loaded script even after the file on disk changes, and two debugging rounds
# have already been spent on a bug that was fixed on disk but not in the folder
# Razor reads. If this line does not say what you expect, hit Reload.
SCRIPT_VERSION = "2026-10-25.7"


# =============================================================================
# CONFIG - THE ACCOUNT RUNEBOOK  (the part you set)
# =============================================================================

# The [ar folder holding the taming spots, outermost first. Every rune inside
# is visited, on every page. Matched case-insensitively.
#
# The root listing captured 2026-07 had a folder called "TamingDeed"; you said
# FillTameDeeds, so that is what this looks for. If it is not found, every
# folder name in the book is printed so the real spelling is one glance away.
RUNEBOOK_FOLDER = ["FillTameDeeds"]

# Only visit runes whose name contains one of these. [] = every rune.
RUNE_MUST_MATCH = []

# How long to stay at one spot, at most, and how long it must have been quiet
# - nothing to tame, nothing to kill - before moving on early.
SPOT_MAX_MS = 5 * 60 * 1000
SPOT_IDLE_MS = 20000

# Between laps of the whole folder, for the spawn to come back. Waited where
# the last rune left you, in slices so Stop is noticed.
LAP_PAUSE_MS = 60000

# 0 = keep going until every deed is full or you stop it.
MAX_LAPS = 0

# NO-RECALL ZONES - places the server will not let you recall from, with a
# spot just outside to walk to first. Checked before EVERY recall, the
# escape included: standing inside one, the script walks to "walk_to" and
# recalls from there.
#
#   near / radius   the zone: within `radius` tiles of `near`
#   walk_to         where recalling works again
#   map             Player.Map number, or None for any facet
#
# Champion spawns are the usual cause. If a recall fails somewhere not
# listed here, the log prints where you were standing so a row can be added.
NO_RECALL_ZONES = [
    # Reported 2026-10-25: the third rune in the folder, by the Lord Oaks
    # champion spawn. No recall at 1646,1152; it works from 1634,1164 on.
    # Radius 11, not 12: walk_to must lie OUTSIDE its own zone, and
    # 1634,1164 is exactly 12 tiles out. Preflight checks every row.
    {"label": "Lord Oaks champion spawn", "near": (1646, 1152), "radius": 11,
     "walk_to": (1634, 1164), "map": None},
]

# Walk to "walk_to" itself, not merely near it - near it can still be in.
ZONE_EXIT_TOLERANCE = 0
ZONE_EXIT_TIMEOUT_MS = 30000


# =============================================================================
# CONFIG - DEED DISCOVERY
# =============================================================================

# An item only counts as a deed if its name or tooltip contains one of these.
# Set to [] to accept ANY item that names a species (riskier - a unicorn
# statuette would register as a unicorn deed).
DEED_NAME_HINTS = ["order", "deed", "contract"]

# Tooltip fields that state which species the deed is for, most specific first.
# A real deed reads "Level: 2Creature Type: KirinFilled: 24/60Gold: 100%", so
# reading the field is far safer than scanning the whole tooltip for a name.
DEED_SPECIES_FIELDS = ["creature type", "animal type", "species", "type"]

# Tooltip fields holding "24/60" style progress.
DEED_PROGRESS_FIELDS = ["filled", "progress", "amount"]

# Ignore deeds that are already full - they cannot take another animal.
SKIP_FULL_DEEDS = True

# How far up the container chain to look when deciding if an item is yours.
MAX_CONTAINER_DEPTH = 6

# Restrict the pack scan to these item graphics. Leave empty to scan everything
# once; the graphics of whatever matches are learned and reused after that.
DEED_GRAPHICS = []

# Re-read the pack this often (ms), so filled deeds drop out of the hunt list.
DEED_RESCAN_MS = 60000

# After the first successful scan, only re-check items whose graphic already
# matched. Much faster. Turn off if you swap in deeds of a different graphic
# mid-run without restarting.
NARROW_RESCAN = True

# Safety net for very full packs - stop reading tooltips after this many items.
MAX_PACK_SCAN = 300


# =============================================================================
# CONFIG - WHAT TO HUNT
# =============================================================================

# Restrict to these species even if you hold other deeds. Empty = every deed
# found is honoured. Names must match the catalogue below.
ONLY_ANIMALS = []

# Never hunt these, even holding a deed.
NEVER_ANIMALS = []

# Species your shard added that are not in the catalogue.
# Format: ("name", [body, ...], min_tame_skill)
EXTRA_ANIMALS = []

# Skip species whose minimum taming skill you do not have.
SKIP_ABOVE_SKILL = True


# =============================================================================
# CONFIG - SAFETY
# =============================================================================
# Body values are only a cheap pre-filter for the scan. Before anything is
# targeted, the creature's NAME must match the species we hold a deed for.
#
# This exists because body values are not trustworthy on their own: two species
# share one, shards reuse them, and a wrong catalogue entry invents one. A stray
# 0x3 in the sheep entry - which is the ZOMBIE body - is how this script came to
# target zombies while hunting.
#
# Leave this True. Setting it False falls back to trusting the body when a name
# will not load, which is what caused that bug.
REQUIRE_NAME_MATCH = True

# Never approach anything whose name contains one of these, whatever its body
# says. A backstop, not the main guard.
NEVER_TAME_WORDS = [
    "zombie", "skeleton", "skeletal", "lich", "wraith", "spectre", "specter",
    "ghoul", "mummy", "bone ", "corpser", "revenant", "shade",
    "golem", "elemental", "daemon", "demon", "gargoyle warrior",
    "ogre", "troll", "ettin", "orc", "ratman", "lizardman", "harpy",
    "titan", "cyclops", "juka", "meer", "solen", "terathan", "ophidian",
]


# =============================================================================
# CONFIG - THREATS
# =============================================================================
#
# HOW A THREAT IS RECOGNISED. UO has no "who is targeting me" - nothing in the
# protocol says it - so it is inferred from the two things that are visible: a
# creature that has locked on turns GREY and MOVES TOWARDS YOU.
#
# Grey on its own is not enough, and this is the part that matters: the animal
# you are TAMING is grey too, and so is every other harmless wild animal
# standing around. Acting on colour alone would have the script attack the very
# creature it is trying to tame.
#
# So a threat has to be BOTH:
#
#   * a hostile notoriety (below), and
#   * getting CLOSER across successive checks - it has to actually be coming
#     for you, not just standing there being grey.
#
# and it is never the creature currently being tamed, whatever it looks like.
THREAT_DETECTION = True

# SELF-DEFENCE. Anything that is closing on you and is NOT a species you hold
# a taming deed for gets fought off, then the tame resumes.
#
# The gate is deliberately narrow, and it is the detection above that makes it
# so: a hostile notoriety AND closing distance. This is not "clear the zoo" -
# it is answering something that has locked on and is walking at you. Quarry
# is never attacked however grey it looks, and neither is anything named in
# THREAT_NEVER_WORDS.
THREAT_ATTACK = True

# MID-TAME, anything on the kill list this close is fought as well, closing or
# not - a monster standing three tiles off is not one to tame beside. Further
# out it is left until the tame finishes and the spot is cleared properly.
#
# The fight itself is kill(): the same spells, limits and escape as clearing
# a spot (see CONFIG - KILLING). The old DEFEND_* spell picker, which chose
# from the resistance table, is not used here - you asked for Magic Arrow and
# Energy Bolt.
DEFEND_RANGE = 10                 # = SPELL_RANGE: shoot it before it arrives

# Notorieties that can count as a threat.
#   3 attackable/grey   4 criminal   5 enemy/orange   6 murderer/red
# Wild animals sit at 3, which is exactly why "closing in" is required as well.
THREAT_NOTORIETY = [3, 4, 5, 6]

# How close something has to be before it is worth caring about.
THREAT_RANGE = 10

# It must have closed by at least this many tiles since the last check to count
# as coming for you. 1 is enough; wandering animals drift both ways.
THREAT_CLOSING_TILES = 1

# Names that are NEVER treated as a threat, however they behave - your own
# pets, summons, and anything else you would rather not shoot at.
THREAT_NEVER_WORDS = []


# =============================================================================
# CONFIG - BEHAVIOUR
# =============================================================================

SCAN_RANGE = 18          # tiles; how far out to look for candidates

# Stay glued to the target. The server re-checks range on every taming tick and
# also wants line of sight, so being adjacent is the only reliably safe distance
# - trailing at 3-4 tiles loses attempts to terrain and to the creature bolting.
STAY_DIST = 1            # distance to hold while taming (1 = adjacent)
TAME_START_DIST = 2      # open/continue an attempt from here without
                         # re-approaching (the server itself allows 3)
LEASH_DIST = 7           # server aborts the attempt past this (502795)

PATHFIND_MIN_DIST = 8    # A* beyond this, single-steps inside it

MAX_TAME_ATTEMPTS = 25   # attempts per creature before giving up on it

# "You do not have a clear path to the animal you are taming" this many times
# and the creature is left. ServUO's taming cursor does NOT check line of
# sight, so a pet standing just inside a house wall is accepted as a target
# from outside; the server only stops the tame a few seconds in. Walking
# closer cannot fix a wall - before this, the script tried 25 times.
TAME_MAX_BLOCKED = 2

# Hard ceiling on one creature, whatever else happens.
TAME_CREATURE_MAX_MS = 180000

# WHO IS SOMEBODY'S PET - the TOOLTIP decides, not the colour.
#
# ServUO BaseCreature.GetProperties tags every controlled creature "(tame)",
# "(bonded)" or "(summoned)", without exception, and identify() refuses any
# of those. Colour cannot do that job on its own: a pet takes its owner's
# notoriety (blue for most players), but so do two WILD species -
#
#   ServUO marks ki-rin and unicorn InitialInnocent (Kirin.cs, Unicorn.cs;
#   the only two tameables that are), which makes them BLUE while wild.
#   2026-10-25.4 used colour alone and refused every wild unicorn and
#   ki-rin as "somebody's pet".
#
# So colour is only a cheap first cut and a fallback:
#
#   TAME_NEVER_NOTORIETY   never quarry, whatever the tooltip says:
#                          2 ally (a guildmate's pet), 7 invulnerable
#                          (vendors, mannequins)
#   TAME_NOTORIETY         what an ordinary wild creature is: 3 grey, or 6
#                          red for a murderer type (ServUO Notoriety.cs)
#   INNOCENT_WILD_SPECIES  species that are wild AND blue
#
# A creature outside TAME_NOTORIETY is quarry only when it is one of the
# INNOCENT_WILD_SPECIES and its tooltip carries no pet tag. A blue horse is
# somebody's horse.
TAME_NEVER_NOTORIETY = [2, 7]
TAME_NOTORIETY = [3, 6]
INNOCENT_WILD_SPECIES = ["ki-rin", "unicorn"]
TAME_ATTEMPT_TIMEOUT = 30000   # ms for one attempt to resolve
TARGET_CURSOR_TIMEOUT = 3000   # ms to wait for the taming target cursor
APPROACH_TIMEOUT = 30000       # ms to spend walking to a creature
DEED_TARGET_TIMEOUT = 4000     # ms to wait for the deed's target cursor
DEED_SETTLE_MS = 400           # ms after the cursor opens before answering it
DEED_RESULT_MS = 1500          # ms to wait for the deed to react
DEED_RETRIES = 3               # deed double-click + target attempts
PROPS_TIMEOUT = 1500           # ms to wait for a tooltip

POLL_MS = 150            # journal / position poll interval; also how often we
                         # re-close on the target during an attempt
MOVE_PAUSE = 250         # pause between movement steps
IDLE_PAUSE = 1000        # pause when there is nothing to do
STUCK_LIMIT = 8          # identical-position steps before declaring unreachable
SETTLE_STEPS = 6         # steps at the fallback distance before accepting it
STALL_STEPS = 40         # steps without getting any closer before giving up
CONTESTED_BACKOFF = 5000 # ms to wait when another tamer has the same beast

# Print what the pack scan sees and every journal line the deed produces.
DEBUG = True

# Optional shard-specific confirmations for the deed step. Leave empty and
# success is judged by the pet disappearing.
MSG_DEED_SUCCESS = []
MSG_DEED_REJECT = []

HUE_INFO = 0x03B2        # pale grey
HUE_GOOD = 0x0044        # green
HUE_WARN = 0x0035        # orange
HUE_BAD = 0x0021         # red


# =============================================================================
# CONFIG - PEACEMAKING
# =============================================================================
#
# Aggressive animals fight back while you tame them. Peacemaking calms one for
# 10-120 seconds (ServUO scales it by the creature's difficulty), which is
# usually long enough to get the tame in.
#
# YOU NEED AN INSTRUMENT IN YOUR PACK. Without one the skill fails SILENTLY -
# ServUO sends no message at all - so the script checks for one up front and
# says so rather than letting you wonder why nothing happens.
#
# WHEN to play it:
#   "aggressive"  only at species named in PEACE_AGGRESSIVE_WORDS below. This
#                 is the default: unicorns and ki-rin are peaceful and calming
#                 them is wasted time, while a dragon will chew on you for the
#                 whole tame.
#   "always"      before every taming attempt, whatever it is. Simplest, and
#                 wasted on a chicken - a failed peace on a passive animal
#                 costs a few seconds and nothing else.
#   "fighting"    only when the creature is already in war mode. Faster, but an
#                 aggressive that has not closed on you YET is not in war mode,
#                 so the first taming attempt is still taken unprotected.
#   "never"       off. Same behaviour as before this existed.
PEACE_ENABLED = True
PEACE_WHEN = "fighting"

# Which species count as naturally aggressive. Matched case-insensitively as a
# SUBSTRING of the creature's name, so "dragon" covers the greater, frost,
# serpentine, swamp and dragon wolf variants in one word.
#
# Err towards including things. A peace played at something docile costs a few
# seconds; one NOT played at something aggressive costs the tame and some hit
# points. Nothing here is ever refused a tame - the word list only decides
# whether music gets played first.
#
# "wyvern" is listed for shards that have a tameable one; ServUO does not, so
# it simply never matches there.
# ---------------------------------------------------------------------------
# WHICH SPECIES ARE HOSTILE
#
# EXTRACTED FROM SERVUO, not written from memory - tools/extract_aggressive.py
# rebuilds it. The signal is the FightMode each creature passes to its base
# constructor, which is the game's own answer to "does this attack me":
#
#     FightMode.Aggressor   fights back only once attacked   -> passive
#     FightMode.Closest     attacks whatever is nearest      -> HOSTILE
#     FightMode.Evil/Good   attacks by the PLAYER's karma    -> conditional
#
# Looked up BY SPECIES, not by substring. That matters: "dragon" is a substring
# of "swamp dragon", and the swamp dragon is FightMode.Aggressor - passive. The
# old five-word list said otherwise in its own comment. Names go through
# match_species first, which resolves longest-first with word boundaries, so a
# swamp dragon resolves to "swamp dragon" and is left alone.
#
# 54 of the catalogue's 112 species. The old list had five words, so around
# forty hostile species were being tamed with no peace played at all.
AGGRESSIVE_SPECIES = [
    "alligator", "bake kitsune", "blood fox", "cold drake",
    "corrosive slime", "crimson drake", "dire wolf", "dragon",
    "dragon wolf", "drake", "dread spider", "dread warhorse", "fire beetle",
    "fire steed", "frenzied ostard", "frost dragon", "frost mite",
    "frost spider", "gargoyle pet", "giant ice worm", "giant rat",
    "giant spider", "giant toad", "greater dragon", "greater mongbat",
    "hell cat", "hell hound", "hiryu", "ice hound", "imp", "iron beetle",
    "lava lizard", "lion", "mongbat", "nightmare", "ossein ram",
    "platinum drake", "predator hellcat", "reptalon", "rune beetle",
    "scorpion", "sewer rat", "shadow wyrm", "skree", "slime", "slith",
    "snake", "stone slith", "stygian drake", "triceratops", "tsuki wolf",
    "white wyrm", "wild tiger", "wolf spider",
]

# FightMode.Evil - these attack players of EVIL karma and ignore everyone else.
# For a good or neutral character they never open hostilities, which is why the
# old comment called unicorns and ki-rin peaceful; that was right for most
# people and wrong for some.
#
# Peaced anyway by default. The config's own rule applies: a peace played at
# something docile costs a few seconds, one NOT played at something hostile
# costs the tame and some hit points. Set this False if your karma is good and
# you would rather save the time.
PEACE_KARMA_AGGRESSIVE = False
KARMA_AGGRESSIVE_SPECIES = [
    "ki-rin", "serpentine dragon", "unicorn",
]

# EXTRA names, yours to add, matched as a plain substring the way the old list
# was. The species table above is the authority; this is for anything it does
# not know about - a shard's own creature, or something renamed.
#
# Left EMPTY on purpose. It used to hold "dragon"/"drake"/"wyvern"/"wyrm"/
# "hiryu", every one of which the species table now covers properly, and
# "dragon" was actively wrong: it caught the passive swamp dragon too.
PEACE_AGGRESSIVE_WORDS = []

# ---------------------------------------------------------------------------
# KILL ON SIGHT
#
# Species with no taming order to fill, which are worth clearing out of the way
# rather than walking around. Matched as a substring, like the list above.
#
# "lesser hiryu" is the case this exists for: there is no taming order for one,
# only for the full hiryu, and the catalogue confirms it - `hiryu` is in it and
# `lesser hiryu` is not.
#
# STILL NOT ACTED ON. THREAT_ATTACK now defends you against things that close
# on you, but that is self-defence and it is gated on a creature actually
# coming for you - it is not a hunting list. Nothing seeks these out.
KILL_ON_SIGHT_WORDS = [
    "lesser hiryu",
]

# Tries per creature before taming is attempted anyway. A failed peace is not
# fatal - it just means the tame happens the hard way.
PEACE_ATTEMPTS = 2

# Re-play if a tame is still running after this long, since the calm wears off.
# 0 disables re-playing.
PEACE_REFRESH_MS = 45000

PEACE_RESULT_MS = 3000            # how long to wait for the result message
PEACE_RETRY_MS = 1200             # between attempts
PEACE_SETTLE_MS = 600

# Instrument graphics, from ServUO Scripts/Items/Equipment/Instruments. Any one
# of these in the pack is enough. The server remembers which instrument you
# used and only asks again if it leaves your backpack.
INSTRUMENT_IDS = [
    0x0E9C,     # drums
    0x0E9D,     # tambourine
    0x0EB1,     # harp
    0x0EB2,     # lap harp
    0x0EB3,     # lute
    0x2805,     # bamboo flute
    0x403B,     # aud char
    0x4C3E,     # cello
    0x4C5A,     # cowbell
]


# ---------------------------------------------------------------------------
# KILLING - what stands between you and the quarry
#
# Anything hostile at a spot that is NOT a species you hold a deed for is
# killed before taming starts, and again whenever it shows up mid-tame. See
# "What gets killed" at the top for the full gate.
KILL_ENABLED = True

# How far to LOOK for things to kill - further than the spell reaches, so
# something walking in is seen before it is in range and is shot the moment
# it crosses SPELL_RANGE, not when it is already swinging at you.
KILL_RANGE = 14

# How far the spells reach. ServUO: Magic Arrow and Energy Bolt both target
# at 10 tiles (Core.ML ? 10 : 12 in MagicArrow.cs / EnergyBolt.cs). Casting
# happens from here and NEVER closer by choice: the old version walked in to
# 8 tiles first, which is how monsters got close enough to hit you and break
# the cast.
SPELL_RANGE = 10

# Something hostile outside SPELL_RANGE that is COMING is waited for rather
# than walked to - it does the closing and you get the first shot. Up to this
# long; after that it is approached, a step at a time, only to KITE_HOLD.
KILL_WAIT_FOR_MS = 4000

# ---------------------------------------------------------------------------
# KEEPING YOUR DISTANCE - the band COVFarm holds, at spell range
#
# The same scheme as COVFarm.py's POSITIONING section, with the band moved
# out to where these spells reach:
#
#   closer than KITE_MIN  -> step AWAY before anything else, no casting
#   further than KITE_HOLD -> step TOWARD it, one step at a time
#   KITE_HOLD is where you STAND: the far edge, one tile inside SPELL_RANGE
#
# Holding the far edge rather than reacting at the floor is COVFarm's lesson:
# against something as fast as you, waiting until the floor is breached
# leaves the gap a tile inside it for the whole fight. And it is held all the
# time - while the cast's cursor is coming, during the settle, between casts,
# waiting for mana - in KITE_TICK_MS slices, never one long blocking wait.
#
# NEVER the pathfinder. PathFinding.Go walks to the tile NEXT TO the creature
# and does not stop on the way; that is what ran the tamer straight into
# whatever it was meant to be shooting (2026-10-25.5 and before).
KITE_HOLD = 9
KITE_MIN = 6
KITE_TICK_MS = 150

# The two spells. Magic Arrow is what UO calls "magic missile".
SPELL_SMALL = "Magic Arrow"
SPELL_SMALL_MANA = 4
SPELL_BIG = "Energy Bolt"
SPELL_BIG_MANA = 20
SPELL_SCHOOL = "magery"

# The line between the two, in hit points from the tables below.
#
# 500 ON THIS SHARD, not the 150 a stock server would want. The shard is
# customised and this character carries 3,467 Spell Damage Increase, so a
# Magic Arrow kills anything under 500 safely (your call, 2026-10-25). That
# puts dragons (486), drakes, daemons, trolls and elementals under it, and
# ogre lords (514), balrons (651), ancient wyrms (684) and the champion-sized
# things over it. A stock 150 would be Energy Bolting things an arrow kills.
SPELL_BIG_HITS = 500

# For a creature that is hostile but whose hit points are not known (the
# UOGuide-only names). Unknown is treated as big: an Energy Bolt too many
# costs mana, a Magic Arrow fight against something large costs the tamer.
SPELL_UNKNOWN_IS_BIG = True

# If this many Magic Arrows have landed and it is still above this much
# health, it was bigger than the table said - switch to Energy Bolt.
SPELL_UPGRADE_AFTER = 4
SPELL_UPGRADE_HEALTH_PCT = 60

KILL_MAX_CASTS = 20               # per creature

# After a spell is aimed, how long to let it land before deciding whether a
# second is needed. The cast itself is already over by then - cast_at waits
# for the target cursor - so this is only travel and damage. Short on
# purpose: if the first arrow did not kill it, the second goes straight out.
KILL_LAND_MS = 700

# A cast BROKEN by a hit ("Your concentration is disturbed") is recast at
# once and does not count as a failure. This many in a row and the creature
# is left - something is beating on you and the escape is the better answer.
KILL_MAX_INTERRUPTS = 6

# "You have not yet recovered from casting a spell" - wait this long, recast.
KILL_RECOVER_MS = 400
KILL_TIMEOUT_MS = 60000           # give up on one creature after this long
KILL_MANA_WAIT_MS = 30000         # longest to stand waiting for mana

# Notorieties that may be attacked:
#   3 attackable/grey   4 criminal   5 enemy/orange   6 murderer/red
# 1 (innocent, blue) and 2 (ally, green) are never on this list. That is the
# guard that keeps players and other people's pets out of it.
KILL_NOTORIETY = [3, 4, 5, 6]

# Bodies matched through HOSTILE_BODIES (random-named monsters - orcs,
# lizardmen, daemons) are acted on only at these notorieties. Their name
# cannot be checked, so the red flag has to agree with the body.
KILL_BODY_NOTORIETY = [6]

# A RED NAME IS AN ENEMY - killed whatever it is called. Your rule,
# 2026-10-25: savages showed red names and were left alone, because they
# are human-bodied with random personal names ("Kuruk"), so neither the name
# tables nor the body table can place them.
#
# "Red" is the NAME colour - notoriety 6, murderer - not the creature's hue.
# Still spared: a species you hold an unfilled deed for (a wild dragon is red
# too, and it is quarry), anything tagged tame/bonded/summoned, and
# KILL_NEVER_WORDS. NOTE this includes red PLAYERS - murderers - who are
# fair game under the rules; set False if you would rather they were not.
KILL_ALL_RED = True

# PARAGONS ARE NEVER TAMED - they cannot be. Some spawns roll one now and
# then; recognised by "(Paragon)" in the tooltip or the paragon hue.
#
# A paragon of a HOSTILE species is killed like any other hostile, with its
# hit points counted x PARAGON_HITS_MULT - ServUO's own multiplier - before
# the spell is picked. Against the 500 line that keeps a harpy paragon (325)
# on Magic Arrow and puts a dragon paragon (2430) on Energy Bolt. A paragon
# of anything NOT on the hostile list - a paragon hind, say - is ignored.
PARAGON_IGNORE = True
PARAGON_HUE = 0x0501              # ServUO Scripts/Mobiles/Special/Paragon.cs
PARAGON_HITS_MULT = 5             # Paragon.HitsBuff in the same file

# Never attacked, whatever the tables say. Matched in the name and tooltip.
KILL_NEVER_WORDS = ["(tame)", "(bonded)", "(summoned)", "guard", "vendor",
                    "healer", "town crier"]

# ---------------------------------------------------------------------------
# ESCAPE - when the fight is going badly
#
# "[ar RO RO" opens the Account Runebook already inside the RO folder, and any
# rune in it is somewhere safe (confirmed for ReagentBuyer, 2026-10-24). The
# first entry is pressed; the next ones are tried if it does not land.
ESCAPE_ENABLED = True
ESCAPE_HITS_PCT = 35              # leave below this much of your own health
ESCAPE_COMMAND = "[ar RO RO"
ESCAPE_MAX_TRIES = 3
ESCAPE_SETTLE_MS = 2500

# After escaping, wait here until health is back to this before carrying on
# with the next rune - going straight back is how a tamer dies twice.
RESUME_HITS_PCT = 90
RESUME_WAIT_MS = 120000


# =============================================================================
# ANIMAL CATALOGUE
# =============================================================================
# Name, body values, minimum taming skill. Extracted from ServUO
# Scripts/Mobiles (every class with Tamable = true). Bodies come from both
# `Body = ...` assignments and BaseMount `base(name, body, mount, ...)` args.
# See docs/tameable-animals.md.

ANIMAL_CATALOGUE = [
    # name                   bodies                    min tame
    ("alligator",             [0xCA],                   47.1),
    ("bake kitsune",          [0xF6],                   80.7),
    ("battle chicken lizard", [0x2CC],                   0.0),
    ("bird",                  [0x6],                     0.0),
    ("black bear",            [0xD3],                   35.1),
    ("blood fox",             [0x58F],                  72.0),
    ("boar",                  [0x122],                  29.1),
    ("brown bear",            [0xA7],                   41.1),
    ("bull",                  [0xE8, 0xE9],             71.1),
    ("bull frog",             [0x51],                   23.1),
    ("cat",                   [0xC9],                    0.0),
    ("chicken",               [0xD0],                    0.0),
    ("chicken lizard",        [0x2CC],                   0.0),
    ("cold drake",            [0x3C, 0x3D],             96.0),
    ("corrosive slime",       [0x33],                   23.1),
    ("cougar",                [0x3F],                   41.1),
    ("cow",                   [0xD8, 0xE7],             11.1),
    ("crimson drake",         [0x58B, 0x58C],           85.0),
    ("cu sidhe",              [0x115],                 101.1),
    ("deathwatch beetle",     [0xF2],                   41.1),
    ("desert ostard",         [0xD2],                   29.1),
    ("dire wolf",             [0x17],                   83.1),
    ("dog",                   [0xD9],                    0.0),
    ("dragon",                [0xC, 0x3B],              93.9),
    ("dragon wolf",           [0x2CF],                 102.0),
    ("drake",                 [0x3C, 0x3D],             84.3),
    ("dread spider",          [0xB],                    96.0),
    ("dread warhorse",        [0x74],                  108.0),
    ("eagle",                 [0x5],                    17.1),
    ("ferret",                [0x117],                   0.0),
    ("fire beetle",           [0xA9],                   93.9),
    ("fire steed",            [0xBE],                  106.0),
    ("forest ostard",         [0xDB],                   29.1),
    ("frenzied ostard",       [0xDA],                   77.1),
    ("frost dragon",          [0xC, 0x3B],             105.0),
    ("frost mite",            [0x590],                 102.0),
    ("frost spider",          [0x14],                   74.7),
    ("gaman",                 [0xF8],                   68.7),
    ("gargoyle pet",          [0x2DA],                  65.1),
    ("giant beetle",          [0x317],                  29.1),
    ("giant ice worm",        [0x59],                   71.1),
    ("giant rat",             [0xD7],                   29.1),
    ("giant spider",          [0x1C],                   59.1),
    ("giant toad",            [0x50],                   77.1),
    ("goat",                  [0xD1],                   11.1),
    ("gorilla",               [0x1D],                    0.0),
    ("great hart",            [0xEA],                   59.1),
    ("greater dragon",        [0xC, 0x3B],             104.7),
    ("greater mongbat",       [0x27],                   71.1),
    ("grey wolf",             [0x19, 0x1B],             53.1),
    ("grizzly bear",          [0xD4],                   59.1),
    ("hell cat",              [0xC9],                   71.1),
    ("hell hound",            [0x62],                   85.5),
    ("high plains boura",     [0x2CB],                  47.1),
    ("hind",                  [0xED],                   23.1),
    ("hiryu",                 [0xF3],                   98.7),
    ("horse",                 [0x2, 0xE2, 0x580],       29.1),
    ("ice hound",             [0x62],                   85.5),
    ("imp",                   [0x4A],                   83.1),
    ("iron beetle",           [0x2CA],                  71.1),
    ("jack rabbit",           [0xCD],                    0.0),
    ("ki-rin",                [0x84],                   95.1),
    ("lava lizard",           [0xCE],                   80.7),
    ("lion",                  [0x592],                  96.0),
    ("llama",                 [0xDC],                   35.1),
    ("lowland boura",         [0x2CB],                  19.1),
    ("mongbat",               [0x27],                   71.1),
    ("mountain goat",         [0x58],                    0.0),
    ("nightmare",             [0x74, 0xB1, 0xB2, 0xB3],  95.1),
    ("ossein ram",            [0x591],                  72.0),
    ("pack horse",            [0x123],                  29.1),
    ("pack llama",            [0x124],                  29.1),
    ("panther",               [0xD6],                   53.1),
    ("parrot",                [0x33F],                   0.0),
    ("phoenix",               [0x340],                 102.0),
    ("pig",                   [0xCB],                   11.1),
    ("platinum drake",        [0x589, 0x58A],           85.0),
    ("polar bear",            [0xD5],                   35.1),
    ("predator hellcat",      [0x7F],                   90.0),
    ("rabbit",                [0xCD],                    0.0),
    ("rat",                   [0xEE],                    0.0),
    ("reptalon",              [0x114],                 101.1),
    ("ridable llama",         [0xDC],                   29.1),
    ("ridgeback",             [0xBB],                   83.1),
    ("ruddy boura",           [0x2CB],                  19.1),
    ("rune beetle",           [0xF4],                   93.9),
    ("saber-toothed tiger",   [0x588],                 102.0),
    ("savage ridgeback",      [0xBC],                   83.1),
    ("scorpion",              [0x30],                   47.1),
    ("serpentine dragon",     [0x67],                  108.0),
    ("sewer rat",             [0xEE],                    0.0),
    ("shadow wyrm",           [0x6A],                  105.0),
    # 0x3 was here and is WRONG - it is the zombie body. It came from a bad
    # extraction: ServUO's Sheep.cs has `return (Body == 0xCF ? 3 : 0);` and the
    # regex read the `==` comparison as an assignment, harvesting the 3.
    ("sheep",                 [0xCF, 0xDF],             11.1),
    ("skittering hopper",     [0x12E],                   0.0),
    ("skree",                 [0x2DD],                  95.1),
    ("slime",                 [0x33],                   23.1),
    ("slith",                 [0x2DE],                  80.7),
    ("snake",                 [0x34],                   59.1),
    ("snow leopard",          [0x40, 0x41],             53.1),
    ("squirrel",              [0x116],                   0.0),
    ("stone slith",           [0x2DE],                  65.1),
    ("stygian drake",         [0x58E],                  85.0),
    ("swamp dragon",          [0x31A, 0x31F],           93.9),
    ("timber wolf",           [0xE1],                   23.1),
    ("triceratops",           [0x587],                 102.0),
    ("tsuki wolf",            [0xFA],                   96.0),
    ("unicorn",               [0x7A],                   95.1),
    ("walrus",                [0xDD],                   35.1),
    ("white wolf",            [0x22, 0x25],             65.1),
    ("white wyrm",            [0x31, 0xB4],             96.3),
    # base(name, Utility.RandomBool() ? 1254 : 1255, ...) - both, not just one.
    ("wild tiger",            [0x4E6, 0x4E7],           95.1),
    ("wolf spider",           [0x2E0],                  59.1),
]

# Bodies shared by more than one species. Seeing one of these is not enough to
# identify the animal - the creature's name has to be checked too.
AMBIGUOUS_BODIES = {
    0xC:   ["dragon", "frost dragon", "greater dragon"],
    0x27:  ["greater mongbat", "mongbat"],
    0x33:  ["corrosive slime", "slime"],
    0x3B:  ["dragon", "frost dragon", "greater dragon"],
    0x3C:  ["cold drake", "drake"],
    0x3D:  ["cold drake", "drake"],
    0x62:  ["hell hound", "ice hound"],
    0x74:  ["dread warhorse", "nightmare"],
    0xC9:  ["cat", "hell cat"],
    0xCD:  ["jack rabbit", "rabbit"],
    0xDC:  ["llama", "ridable llama"],
    0xEE:  ["rat", "sewer rat"],
    0x2CB: ["high plains boura", "lowland boura", "ruddy boura"],
    0x2CC: ["battle chicken lizard", "chicken lizard"],
    0x2DE: ["slith", "stone slith"],
}


# =============================================================================
# RESISTANCES
# =============================================================================
#
# Extracted from ServUO Scripts/Mobiles by tools/extract_resistances.py - the
# same source the animal catalogue came from, and authoritative for a
# ServUO-derived shard in a way an OSI wiki is not.
#
# Order is (PHYSICAL, FIRE, COLD, POISON, ENERGY).
#
# ServUO declares each as a RANGE - SetResistance(Type, min, max) - because
# every creature rolls its own within it. These are the MIDPOINTS, which is
# what an average specimen has.
#
# A resistance ServUO never sets is 0, and that is real rather than missing:
# a chicken declares Physical and nothing else. An early version of the
# extractor required all five and silently dropped every low-level animal.
#
# The table is NOT limited to tameable species. What gets shot at is by
# definition the stuff you are NOT taming - "lesser hiryu" is here for exactly
# that reason - so anything worth attacking needs a row whether or not it can
# be tamed. Add more with the extractor.
#
# 109 of the 112 catalogue species are here. Bird, parrot and giant beetle are
# absent - bird declares no resistances at all and randomises its name into
# crow/raven/magpie, and the other two are not in Scripts/Mobiles in this
# ServUO version. All three are harmless, and weakest_damage_type() returns
# None for anything it does not know rather than guessing.
SPECIES_RESISTANCES = {
    "alligator":             ( 30,   7,   0,   7,   0),
    "bake kitsune":          ( 50,  80,  50,  50,  50),
    "battle chicken lizard": ( 17,  10,   0,   0,   0),
    "black bear":            ( 22,   0,  12,   7,   0),
    "blood fox":             ( 55,  25,  60,  30,  35),
    "boar":                  ( 12,   7,   0,   7,   0),
    "brown bear":            ( 25,   0,  17,  12,   0),
    "bull":                  ( 27,   0,  12,   0,   0),
    "bull frog":             (  7,   0,   0,   0,   0),
    "cat":                   (  7,   0,   0,   0,   0),
    "chicken":               (  3,   0,   0,   0,   0),
    "chicken lizard":        ( 17,  10,   0,   0,   0),
    "cold drake":            ( 57,  35,  82,  45,  45),
    "corrosive slime":       (  7,   0,   0,  17,   0),
    "cougar":                ( 22,   7,  12,   7,   0),
    "cow":                   ( 10,   0,   0,   0,   0),
    "crimson drake":         ( 40,  35,  35,  45,  40),
    "cu sidhe":              ( 57,  35,  77,  40,  77),
    "deathwatch beetle":     ( 37,  22,  22,  65,  27),
    "desert ostard":         ( 17,  10,   0,   0,   0),
    "dire wolf":             ( 22,  15,   7,   7,  12),
    "dog":                   ( 12,   0,   0,   0,   0),
    "dragon":                ( 60,  65,  35,  30,  40),
    "dragon wolf":           ( 50,  35,  35,  45,  45),
    "drake":                 ( 47,  55,  45,  25,  35),
    "dread spider":          ( 45,  25,  25, 100,  25),
    "dread warhorse":        ( 70,  30,  30,  55,  45),
    "eagle":                 ( 22,  12,  22,   7,   7),
    "ferret":                ( 47,  12,  35,  23,  22),
    "fire beetle":           ( 40,  72,  10,  30,  30),
    "fire steed":            ( 35,  75,  25,  35,  35),
    "forest ostard":         ( 17,   0,   0,   0,   0),
    "frenzied ostard":       ( 27,  12,   0,  22,  22),
    "frost dragon":          ( 88,  62,  90,  67,  70),
    "frost mite":            ( 65,  20,  95,  60,  42),
    "frost spider":          ( 27,   7,  45,  25,  15),
    "gaman":                 ( 60,  40,  40,  50,  40),
    "gargoyle pet":          ( 60,  40,  40,  40,  40),
    "giant ice worm":        ( 32,   0,  85,  20,  15),
    "giant rat":             ( 17,   7,   0,  30,   0),
    "giant spider":          ( 17,   0,   0,  30,   0),
    "giant toad":            ( 22,   7,   0,   0,   7),
    "goat":                  ( 10,   0,   0,   0,   0),
    "gorilla":               ( 22,   7,  12,   0,   0),
    "great hart":            ( 22,   0,   7,   0,   0),
    "greater dragon":        ( 72,  77,  47,  50,  62),
    "greater mongbat":       ( 20,   0,   0,   0,   0),
    "grey wolf":             ( 17,  12,  22,  12,  12),
    "grizzly bear":          ( 30,   0,  20,   7,   7),
    "hell cat":              ( 30,  85,   0,   0,  17),
    "hell hound":            ( 28,  35,   0,  15,  15),
    "high plains boura":     ( 55,  37,  15,  35,  35),
    "hind":                  ( 10,   0,   5,   0,   0),
    "hiryu":                 ( 62,  80,  20,  45,  45),
    "horse":                 ( 17,   0,   0,   0,   0),
    "ice hound":             ( 30,   0,  45,  15,  15),
    "imp":                   ( 30,  45,  25,  35,  35),
    "iron beetle":           ( 57,  25,  25,  35,  50),
    "jack rabbit":           (  3,   0,   0,   0,   0),
    "ki-rin":                ( 60,  40,  30,  30,  30),
    "lesser hiryu":          ( 57,  70,  10,  35,  35),   # kill on sight - not tameable
    "lava lizard":           ( 40,  37,   0,  30,  30),
    "lion":                  ( 45,  40,  35,  35,  30),
    "llama":                 ( 17,   0,   0,   0,   0),
    "lowland boura":         ( 55,  37,  15,  35,  35),
    "mongbat":               (  7,   0,   0,   0,   0),
    "mountain goat":         ( 15,   7,  15,  12,  12),
    "nightmare":             ( 60,  35,  35,  35,  25),
    "ossein ram":            ( 55,  15,  45,  35,  45),
    "pack horse":            ( 22,  12,  22,  12,  12),
    "pack llama":            ( 30,  12,  12,  12,  12),
    "panther":               ( 22,   7,  12,   7,   0),
    "phoenix":               ( 50,  65,   0,  30,  45),
    "pig":                   ( 12,   0,   0,   0,   0),
    "platinum drake":        ( 40,  40,  40,  45,  40),
    "polar bear":            ( 30,   0,  70,  20,  12),
    "predator hellcat":      ( 30,  35,   0,   0,  10),
    "rabbit":                (  7,   0,   0,   0,   0),
    "rat":                   (  7,   0,   0,   7,   0),
    "reptalon":              ( 58,  40,  40,  57,  77),
    "ridable llama":         ( 12,   7,   7,   7,   7),
    "ridgeback":             ( 20,   7,   7,   7,   7),
    "ruddy boura":           ( 55,  37,  15,  35,  35),
    "rune beetle":           ( 52,  42,  42,  85,  50),
    "saber-toothed tiger":   ( 45,  35,  55,  35,  45),
    "savage ridgeback":      ( 17,  12,  17,  12,  12),
    "scorpion":              ( 22,  12,  22,  45,  12),
    "serpentine dragon":     ( 37,  30,  30,  30,  30),
    "sewer rat":             (  7,   0,   0,  20,   7),
    "shadow wyrm":           ( 70,  55,  50,  25,  55),
    "sheep":                 (  7,   0,   0,   0,   0),
    "skittering hopper":     (  7,   0,  15,   0,   7),
    "skree":                 ( 60,  50,  32,  60,  32),
    "slime":                 (  7,   0,   0,  15,   0),
    "slith":                 ( 37,  40,   0,  30,  27),
    "snake":                 ( 17,   0,   0,  25,   0),
    "snow leopard":          ( 22,   7,  35,  15,  25),
    "squirrel":              ( 32,  12,  32,  22,  22),
    "stone slith":           ( 52,  25,  15,  35,  35),
    "stygian drake":         ( 60,  65,  35,  35,  65),
    "swamp dragon":          ( 37,  25,  30,  25,  35),
    "timber wolf":           ( 17,   7,  12,   7,   7),
    "triceratops":           ( 75,  45,  45,  35,  45),
    "tsuki wolf":            ( 50,  60,  60,  60,  60),
    "unicorn":               ( 60,  32,  32,  60,  32),
    "walrus":                ( 22,   7,  22,   7,   7),
    "white wolf":            ( 17,  12,  22,  12,  12),
    "white wyrm":            ( 62,  20,  85,  45,  45),
    "wild tiger":            ( 65,  30,  59,  35,  30),
    "wolf spider":           ( 32,  25,  30, 100,  30),
}

# =============================================================================
# HOSTILE CREATURES
# =============================================================================
#
# HOSTILE_HITS and HOSTILE_BODIES are EXTRACTED FROM SERVUO by
# tools/extract_hostiles.py - every creature whose FightMode is anything but
# Aggressor or None, i.e. that attacks without being attacked first. The
# number is the midpoint of its SetHits(min, max), and it is what picks the
# spell: the client only sees other mobiles' health as a percentage, so a
# monster's real size has to come from the source.
#
# HOSTILE_BODIES is for monsters ServUO gives a RANDOM PERSONAL NAME - an orc
# is "Grak", a lizardman "Sssik", a daemon "Zorlak" - which no name table can
# match. Those are acted on by body, and only when notoriety is red as well
# (KILL_BODY_NOTORIETY). Human, elf and gargoyle bodies are kept out: those
# are what players wear.
#
# OFFICIAL_HOSTILE_NAMES is the cross-reference: UOGuide's Category:Monsters
# (565 names, 2026-10-25) less everything already above, less the tameable
# catalogue, less pages that are not a creature at all ("Goblins",
# "Champion", "Wandering Healer"). Their hit points are not known, so they are
# sized by SPELL_UNKNOWN_IS_BIG.
#
# Tameable species appear here too where ServUO makes them hostile - a dire
# wolf is quarry when you hold a dire wolf deed and a threat when you do not.
# A species you hold an unfilled deed for is NEVER attacked.

HOSTILE_HITS = {
    "abscess":                        7505,
    "abyssal abomination":             675,
    "abyssmal horror":                6000,
    "acid elemental":                  204,
    "acid slug":                       351,
    "adrian":                        60000,
    "agapite elemental":               144,
    "air elemental":                   150,
    "alligator":                        53,
    "ancient wyrm":                    684,
    "andros":                        60000,
    "anlorlem":                        575,
    "anlorvaglem":                    3205,
    "anlorzen":                        350,
    "ant lion":                        156,
    "anzuanord":                       180,
    "arcane daemon":                   108,
    "arch deamon":                     651,
    "arctic ogre lord":                514,
    "ballem":                          550,
    "betballem":                        95,
    "betrayer":                        270,
    "black order assassin":            470,
    "black order mage":                607,
    "black order thief":               807,
    "black solen infiltrator":         156,
    "black solen queen":               156,
    "black solen warrior":             101,
    "black solen worker":               65,
    "blackthorn juggernaut":           210,
    "blood elemental":                 342,
    "blood fox":                       195,
    "bloodworm":                       398,
    "bog thing":                       510,
    "bogle":                            53,
    "bogling":                          65,
    "bone demon":                     3600,
    "bone knight":                     134,
    "bone mage":                        53,
    "bronze elemental":                144,
    "bulbous putrification":          1221,
    "chaos daemon":                    100,
    "chaos dragoon":                   200,
    "chaos dragoon elite":             313,
    "chief paroxysmus":              50000,
    "clan chitter assistant":          132,
    "clan ribbon courtier":           2077,
    "clan ribbon plague rat":           92,
    "clan ribbon supplicant":          127,
    "clan scratch henchrat":          2065,
    "clan scratch savage wolf":         65,
    "clan scratch scrounger":          135,
    "clan scratch tinkerer":          2046,
    "clockwork scorpion":              180,
    "cold drake":                      475,
    "copper elemental":                144,
    "coral snake":                     166,
    "corporeal brume":                1200,
    "corpser":                         101,
    "corrosive slime":                  17,
    "corrupted soul":                   65,
    "crimson dragon":                25000,
    "crimson drake":                   249,
    "crystal daemon":                  210,
    "crystal elemental":               150,
    "crystal hydra":                  1475,
    "crystal lattice seeker":          450,
    "crystal vortex":                  375,
    "cyclopean warrior":               216,
    "dark guardian":                   165,
    "deep sea serpent":                203,
    "devourer of souls":               650,
    "dire wolf":                        65,
    "doppleganger":                    110,
    "dragon":                          486,
    "dragon wolf":                     830,
    "drake":                           249,
    "dread horn":                    50000,
    "dread spider":                    125,
    "dream wraith":                    600,
    "drelgor the impaler":             133,
    "dryad":                           312,
    "dull copper elemental":           144,
    "earth elemental":                 180,
    "effete putrid gargoyle":          110,
    "effete undead gargoyle":           67,
    "efreet":                          204,
    "elder gazer":                     186,
    "elite ninja":                     300,
    "enraged earth elemental":         525,
    "enslaved gargoyle":               199,
    "enslaved goblin keeper":          174,
    "enslaved goblin mage":            174,
    "enslaved goblin scout":           182,
    "enslaved gray goblin":            179,
    "enslaved green goblin":           184,
    "ettin":                            90,
    "exodus minion":                   540,
    "exodus overseer":                 360,
    "fairy dragon":                    400,
    "fan dancer":                      390,
    "fetid essence":                   600,
    "fire ant":                        299,
    "fire beetle":                     200,
    "fire daemon":                    1100,
    "fire elemental":                   84,
    "flesh golem":                     113,
    "fleshrenderer":                  4500,
    "flurry":                          475,
    "frost dragon":                   2150,
    "frost mite":                      900,
    "frost ooze":                       15,
    "frost spider":                     53,
    "frost troll":                     148,
    "gargoyle":                         96,
    "gargoyle destroyer":              483,
    "gargoyle enforcer":               483,
    "gargoyle pet":                    306,
    "gargoyle shade":                   62,
    "gazer":                            66,
    "gazer larva":                      41,
    "ghoul":                            53,
    "giant black widow":                53,
    "giant ice serpent":               138,
    "giant ice worm":                  138,
    "giant rat":                        32,
    "giant serpent":                   120,
    "giant spider":                     53,
    "giant toad":                       53,
    "gibberling":                       92,
    "golden elemental":                144,
    "golem":                           180,
    "gore fiend":                      104,
    "gray goblin":                     176,
    "gray goblin keeper":              186,
    "gray goblin mage":                140,
    "greater dragon":                 1500,
    "greater mongbat":                  41,
    "greater poison elemental":        676,
    "green goblin":                    185,
    "green goblin alchemist":          196,
    "green goblin scout":              186,
    "gremlin":                          70,
    "grimmoch drummel":                193,
    "grobu":                          1267,
    "harpy":                            65,
    "headless one":                     23,
    "hell cat":                         57,
    "hell hound":                      215,
    "hiryu":                          1000,
    "horde minion":                     17,
    "hungry coconut crab":              12,
    "hydra":                          1492,
    "ice elemental":                   102,
    "ice fiend":                       234,
    "ice hound":                        95,
    "imp":                              62,
    "interred grizzle":               1500,
    "iron beetle":                     796,
    "juka lord":                       270,
    "juka mage":                       150,
    "juka warrior":                    180,
    "kappa":                           165,
    "kaze kemono":                     290,
    "kepetch":                         350,
    "kepetch ambusher":                538,
    "killer pumpkin":                  500,
    "korpre":                           55,
    "kraken":                          461,
    "lady melisande":                100000,
    "lady of the snow":                610,
    "lava elemental":                  280,
    "lava lizard":                      83,
    "lava serpent":                    240,
    "lava snake":                       30,
    "leather wolf":                     95,
    "lesser hiryu":                    500,
    "leviathan":                      1500,
    "lich":                            111,
    "lich lord":                       276,
    "lifestealer":                    4625,
    "lion":                            360,
    "lord oaks":                     12000,
    "lysander gathenwale":             193,
    "maddening horror":                660,
    "mantra effervescence":            200,
    "medusa":                        60000,
    "meer captain":                     62,
    "mimic":                           543,
    "minion of scelestus":           30000,
    "minotaur":                        320,
    "minotaur captain":                420,
    "minotaur scout":                  368,
    "mistral":                         497,
    "moloch":                          185,
    "mongbat":                           5,
    "monstrous interred grizzle":    50000,
    "morg bergen":                     193,
    "mummy":                           215,
    "navrey night-eyes":             32500,
    "night terror":                  50000,
    "niporailem":                    10250,
    "ogre":                            108,
    "ogre lord":                       514,
    "oni":                             465,
    "ophidian matriarch":              276,
    "orc bomber":                      109,
    "orc brute":                       514,
    "orc chopper":                     118,
    "orc scout":                        65,
    "orcish lord":                     109,
    "orcish mage":                      80,
    "ortanord":                        100,
    "ossein ram":                      500,
    "patchwork skeleton":               65,
    "pestilent bandage":               430,
    "pit fiend":                       234,
    "plague beast":                    361,
    "plague beast lord":              1800,
    "plague spawn":                    150,
    "platinum drake":                  249,
    "poison elemental":                282,
    "predator hellcat":                114,
    "primeval lich":                 30000,
    "protector":                       400,
    "putrid undead gargoyle":          662,
    "putrid undead guardian":          553,
    "pyre":                           1861,
    "quagmire":                         98,
    "rai-ju":                          240,
    "raptor":                          371,
    "ravager":                         168,
    "reaper":                           84,
    "red death":                      1572,
    "red solen infiltrator":           156,
    "red solen queen":                 156,
    "red solen warrior":               101,
    "red solen worker":                 65,
    "relanord":                        450,
    "reptalon":                        882,
    "restless soul":                    20,
    "revenant":                        270,
    "revenant lion":                   265,
    "ronin":                           350,
    "rotting corpse":                 1200,
    "rotworm":                         225,
    "rune beetle":                     330,
    "sand vortex":                      56,
    "scorpion":                         56,
    "sea serpent":                     118,
    "sentinel spider":                 262,
    "serpentine dragon":               480,
    "sewer rat":                         6,
    "shade":                            53,
    "shadow dweller":                  111,
    "shadow iron elemental":           144,
    "shadow wyrm":                     578,
    "shimmering effusion":           20000,
    "silvani":                         600,
    "silver serpent":                  156,
    "skeletal dragon":                 578,
    "skeletal drake":                  350,
    "skeletal knight":                 134,
    "skeletal lich":                  1200,
    "skeletal mage":                    53,
    "skeleton":                         41,
    "skree":                           252,
    "slasher of veils":              57500,
    "slime":                            17,
    "slith":                            84,
    "snake":                            17,
    "snow elemental":                  204,
    "spectral armour":                 189,
    "spectre":                          53,
    "stone gargoyle":                  156,
    "stone harpy":                     185,
    "stone monster":                   141,
    "stone slith":                     160,
    "stygian dragon":                30000,
    "stygian drake":                   495,
    "succubus":                        332,
    "swamp tentacle":                   65,
    "tangling root":                   238,
    "tavara sewel":                    193,
    "tempest":                         602,
    "tentacles of the harrower":       570,
    "terathan avenger":                334,
    "terathan drone":                   30,
    "terathan matriarch":              216,
    "terathan warrior":                114,
    "thrasher":                        622,
    "titan":                           336,
    "tormented minotaur":             4100,
    "toxic slith":                     206,
    "trapdoor spider":                 134,
    "travesty":                      35000,
    "treefellow":                      125,
    "treefellow guardian":             812,
    "triceratops":                    1150,
    "triton":                          675,
    "troglodyte":                      321,
    "troll":                           114,
    "tsuki wolf":                      413,
    "twaulo":                         7500,
    "undead gargoyle":                 250,
    "undead guardian":                 138,
    "unfrozen mummy":                 1500,
    "usagrallem ballem":              2100,
    "valorite elemental":              144,
    "vampire bat":                      60,
    "vasanord":                       5100,
    "verite elemental":                144,
    "vicious macaw":                   750,
    "virulent":                        678,
    "viscera":                         215,
    "void manifestation":             2400,
    "vollem":                          307,
    "wailing banshee":                  83,
    "wanderer of the void":            375,
    "water elemental":                 165,
    "white wyrm":                      444,
    "wight":                           200,
    "wisp":                            126,
    "wolf spider":                     155,
    "wraith":                           53,
    "wyvern":                          133,
    "yamandon":                       1700,
    "yomotsu elder":                   850,
    "yomotsu priest":                  508,
    "yomotsu warrior":                 508,
    "zealot of khaldun":               459,
    "zombie":                           35,
}

HOSTILE_BODIES = {
    0x7:    ("orc", 77),
    0x9:    ("daemon", 294),
    0x11:   ("orc", 65),
    0x23:   ("lizardman", 65),
    0x24:   ("lizardman", 65),
    0x28:   ("balron", 651),
    0x2A:   ("ratman", 65),
    0x4E:   ("ancient lich", 577),
    0x7B:   ("ethereal warrior", 411),
    0x7C:   ("evil mage", 56),
    0x7D:   ("evil mage lord", 56),
    0x7E:   ("evil mage lord", 56),
    0x80:   ("pixie", 15),
    0x82:   ("fire gargoyle", 225),
    0x8E:   ("ratman", 98),
    0x8F:   ("ratman", 98),
    0x132:  ("impaler", 5000),
    0x137:  ("shadow knight", 5000),
    0x139:  ("darknight creeper", 4000),
    0x13E:  ("demon knight", 30000),
}

OFFICIAL_HOSTILE_NAMES = [
    "abyssal infernal", "acid slime", "adrian the glorious lord",
    "allosaurus", "anchisaur", "ancient hellhound", "andros the dread lord",
    "angered spirit", "archaeosaurus", "archmage", "bane chosen dragon rider",
    "bane chosen guard", "bane chosen hound master", "bane chosen recruit",
    "barracoon the piper", "birling blades", "black order grand mage",
    "black order high executioner", "black order master thief",
    "blackrock elemental", "blackrock golem", "blightborn slime",
    "blood witch", "bone daemon", "bone magi", "bone swordslinger",
    "boneweaver", "bound soul", "brigand", "cave troll", "centaur",
    "chaos vortex", "charybdis", "chest guardian", "chiikkaha the toothed",
    "chikkaha the toothed", "clan chitter tinkerer", "clay golem", "coil",
    "controller", "corgul the soulbinder", "corrupted wisp",
    "corrupted wyvern", "covetous revenant", "covetous wyrm",
    "crystal sea serpent", "crystal wisp", "daemon berserker",
    "daemon mongbat", "dark father", "dark knight", "dark wisp", "darkmane",
    "dazzled harpy", "deathwatch beetle hatchling", "dendrite",
    "diabolical seaweed", "dimetrosaur", "diseased blood elemental",
    "diseased lich", "dragon turtle", "dread pirate", "echidnite",
    "enraged colossus", "enslaved goblin alchemist", "ensorcled wisp",
    "eternal gazer", "executioner", "exodus drone", "exodus juggernaut",
    "exodus minion lord", "exodus sentinel", "exodus zealot",
    "fallen warrior", "feral treefellow", "fezzik the ogre cook",
    "flame elemental", "gallusaurus", "gargoyle assassin", "giant tentacle",
    "gnaw", "greater earth elemental", "greater phoenix", "grim reaper",
    "grizzled mare", "grubber", "guile", "harbinger", "headless miner",
    "hellion", "hellsteed", "hungry ogre", "hydros", "ilhenir the stained",
    "infernus", "insane dryad", "irk", "khal ankur", "lady jennifyr",
    "lady lissith", "lady marai", "lady sabrix", "large ogre lord",
    "lesser oni", "light daemon", "lithos", "lizardman defender",
    "lizardman squatter", "lizardman witchdoctor", "lurg", "magma lizard",
    "malefic", "master jonath", "master mikael", "master theophilus",
    "meer eternal", "meer mage", "meer warrior", "mephitis", "miasma",
    "minotaur general", "molten earth elemental", "moug-guur",
    "mud elemental", "myrmidex drone", "myrmidex larvae", "myxkion", "naba",
    "najasaurus", "neira the necromancer", "nether vortex",
    "ogre bonecrusher", "ophidian apprentice mage", "ophidian avenger",
    "ophidian berserker", "ophidian brood queen", "ophidian enforcer",
    "ophidian healer", "ophidian justicar", "ophidian knight-errant",
    "ophidian shaman", "ophidian warrior", "ophidian zealot",
    "orc footsoldier", "osiredon the scalis enforcer", "paralithode",
    "parasitic eel", "paroxysmus' swamp dragon", "pestilent bandages",
    "phantom", "pirate", "plague beast spawn", "priest of mondain",
    "prometheoid", "purifying blood elemental", "putrefier",
    "putrid swamp bog", "pyros", "quartz elemental", "rakktavi",
    "ratman archer", "ratman assassin", "ratman mage", "rend",
    "renegade changeling", "rift guardian", "rikktor", "rock mite",
    "sagittarri", "saliva", "satyr", "saurosaurus", "savage (female)",
    "savage (male)", "savage rider", "savage shaman",
    "savage warrior (female)", "savage warrior (male)", "searing elemental",
    "semidar", "shadow fiend", "shadow hound", "shadow wisp", "silenii",
    "silver serpent (small)", "silverback gorilla", "sir patrick",
    "skeletal mare", "skeletal steed", "skeletrex",
    "solen infiltrator (queen)", "solen infiltrator (warrior)", "solen queen",
    "solen warrior", "solen worker", "soulbound apprentice mage",
    "soulbound battle mage", "soulbound pirate captain",
    "soulbound pirate raider", "soulbound spell slinger",
    "soulbound swashbuckler", "speckled scorpion", "spectral armor",
    "spectral spellbinder", "sphynx", "spite", "stone elemental",
    "strange gazer", "stratos", "sudiva", "swoop", "szavetra", "tangle",
    "tangling roots", "the harrower", "tikitavi", "titan rockhurler",
    "toxic ooze", "twaulo of the glade", "tyball's shadow",
    "unbound energy vortex", "ursadane", "usagralem ballem",
    "vampire mongbat", "venom elemental", "vicious drake", "vile cadaver",
    "vitavi", "void daemon", "void shadow", "vortex elemental",
    "war alligator", "whipping vine", "wind elemental", "winter reaper",
    "yukki onna", "zealot of khaldun knight", "zealot of khaldun summoner",
    "zipactriotl", "zombie skeleton",
]


# ---------------------------------------------------------------------------
# SPELLS
#
# Which schools you actually have. A spell from a school not listed here is
# never chosen, so trimming this is how you stop it reaching for something you
# cannot cast.
#
# Note WILDFIRE IS SPELLWEAVING, not Mysticism - checked in ServUO, it lives in
# Scripts/Spells/Spellweaving/Wildfire.cs. Casting it as the wrong school just
# fails.
AVAILABLE_SCHOOLS = ["magery", "necromancy", "spellweaving", "mysticism"]

# Damage spells, from ServUO Scripts/Spells. `base` is the first argument to
# GetNewAosDamage, which is the spell's base damage before resistances.
#
#     (name, school, damage type, base damage, is area)
#
# Area spells are listed for completeness but are excluded from single-target
# choices by ALLOW_AREA_SPELLS below - they hit everything nearby, including
# the animal you are trying to tame.
#
# Spells whose damage is not a simple GetNewAosDamage call are deliberately
# absent rather than guessed at: Poison Strike and Wither (Necromancy),
# Wildfire, Thunderstorm and Essence of Wind (Spellweaving), and Earthquake
# (Magery) all compute damage differently. They can be added once measured.
SPELL_TABLE = [
    ("Bombard",            "mysticism",     "physical", 40, False),
    ("Chain Lightning",    "magery",        "energy", 51, True ),
    ("Eagle Strike",       "mysticism",     "energy", 19, False),
    ("Energy Bolt",        "magery",        "energy", 40, False),
    ("Explosion",          "magery",        "fire", 40, False),
    ("Fireball",           "magery",        "fire", 19, False),
    ("Flame Strike",       "magery",        "fire", 48, False),
    ("Hail Storm",         "mysticism",     "cold", 51, True ),
    ("Harm",               "magery",        "cold", 17, False),
    ("Lightning",          "magery",        "energy", 23, False),
    ("Magic Arrow",        "magery",        "fire", 10, False),
    ("Meteor Swarm",       "magery",        "fire", 51, True ),
]

# Area spells hit everything around them, which during a tame includes your own
# target. Off by default for that reason.
ALLOW_AREA_SPELLS = False

_RESIST_ORDER = ["physical", "fire", "cold", "poison", "energy"]


def species_resistances(name):
    """{type: value} for a species, or None if it is not in the table."""
    low = (name or "").strip().lower()
    row = SPECIES_RESISTANCES.get(low)
    if row is None:
        # The catalogue name and the creature's own name can differ in
        # punctuation - "ki-rin" against "ki rin" - so try it loosely too.
        squashed = re.sub(r"[^a-z0-9]+", "", low)
        for key, value in SPECIES_RESISTANCES.items():
            if re.sub(r"[^a-z0-9]+", "", key) == squashed:
                row = value
                break
    if row is None:
        return None
    return dict(zip(_RESIST_ORDER, row))


def usable_spells(allow_area=None):
    """The spells you can actually cast, as (name, school, type, base)."""
    if allow_area is None:
        allow_area = ALLOW_AREA_SPELLS
    out = []
    for name, school, kind, base, area in SPELL_TABLE:
        if school not in AVAILABLE_SCHOOLS:
            continue
        if area and not allow_area:
            continue
        out.append((name, school, kind, base))
    return out


def expected_damage(base, resistance):
    """What a spell of `base` damage lands after `resistance` per cent."""
    return base * max(0, 100 - int(resistance)) / 100.0


def best_spell_against(name, allow_area=None):
    """The spell that lands hardest on this species, or None if unknown.

    NOT simply "lowest resistance". Base damage matters just as much, and the
    two disagree often enough to matter:

        a hiryu resists cold 20 and energy 45, so the lowest resistance says
        Harm - but Harm is base 17 against Energy Bolt's 40, so the bolt lands
        22 where Harm lands 13.6. Energy Bolt wins, which is what actually
        happens in game.

    Returns (spell, school, type, expected damage), or None for a creature not
    in the table - an unknown one should be fought with whatever you would
    normally use rather than a choice made from no information.
    """
    resistances = species_resistances(name)
    if not resistances:
        return None

    best = None
    for spell, school, kind, base in usable_spells(allow_area):
        if kind not in resistances:
            continue
        landed = expected_damage(base, resistances[kind])
        if best is None or landed > best[3]:
            best = (spell, school, kind, landed)
    return best


def weakest_damage_type(name, among=None):
    """The damage type this species resists least, or None if unknown.

    Kept for reporting - it answers "what is it soft against", which is not
    the same question as "what should I cast". Use best_spell_against for that.
    """
    resistances = species_resistances(name)
    if not resistances:
        return None
    if among is None:
        among = sorted(set(kind for _n, _s, kind, _b in usable_spells()))
    usable = dict((t, resistances[t]) for t in among if t in resistances)
    if not usable:
        return None
    return min(usable, key=lambda t: usable[t])


# =============================================================================
# SERVER MESSAGES  (ServUO/RunUO Scripts/Skills/AnimalTaming.cs)
# =============================================================================

MSG_SUCCESS = [
    "It seems to accept you as master.",              # 502799
    # ALSO A SUCCESS. ServUO AnimalTaming.cs sends this INSTEAD of 502799
    # when you have owned the creature before - and then makes it your pet
    # exactly the same. It used to sit in MSG_SKIP, so a re-tamed creature
    # was written off as "cannot be tamed by you", ignored, and left
    # following you with no deed. Confirmed in source 2026-10-25.
    "That wasn't even challenging.",                  # 502797
]

MSG_RETRY = [
    "You fail to tame the creature.",                 # 502798
    "You seem to anger the beast!",                   # 502805
    "The animal is too angry to continue taming.",    # 502794
    "You must wait a few moments to use another skill.",
]

MSG_REPOSITION = [
    "You are too far away to continue taming.",       # 502795
    "That is too far away.",
]

# Its own outcome now, not a reposition: getting closer does not get you
# round a wall. Counted against TAME_MAX_BLOCKED.
MSG_BLOCKED = [
    "You do not have a clear path to the animal you are taming",  # 1049654
]

MSG_SKIP = [
    # Not always a skip: if the tame landed while its message was missed,
    # the creature IS ours. tame() checks is_our_pet before writing it off.
    "That animal looks tame already.",                # 502804
    "That creature cannot be tamed.",                 # 1049655
    "You can't tame that!",                           # 502801
    "You have no chance of taming this creature.",    # 502806
    "This animal has had too many owners and is too upset for you to tame.",
    "That creature can only be tamed by males.",      # 1049653
    "That creature can only be tamed by females.",    # 1049652
    "You must subdue this creature before you can tame it!",  # 1054025
]

MSG_CONTESTED = [
    "Someone else is already taming this.",           # 502802
]

MSG_ABORT = [
    "You have too many followers to tame that creature.",  # 1049611
    "You are dead, and cannot continue taming.",           # 502796
]


# ---------------------------------------------------------------------------
# Casting - ServUO Scripts/Spells/Base/Spell.cs and the two spells, verbatim.
#
# Read with a journal TIMESTAMP, never after Journal.Clear(): a cast happens
# in the middle of a taming attempt, and clearing the journal there is
# exactly how a tame's success message got thrown away.
# ---------------------------------------------------------------------------

SPELL_DISTURBED = ("Your concentration is disturbed, thus ruining thy "
                   "spell.")                                   # 500641
SPELL_NOT_RECOVERED = "You have not yet recovered from casting a spell."  # 502644
SPELL_ALREADY_CASTING = "You are already casting a spell."    # 502642
SPELL_NO_REAGENTS = "More reagents are needed for this spell."  # 502630
SPELL_NO_MANA = "Insufficient mana"                           # 502625, prefix
SPELL_NOT_SEEN = "Target can not be seen."                    # 500237
SPELL_TOO_FAR = "That is too far away."                       # 500446


# ---------------------------------------------------------------------------
# Peacemaking - ServUO Scripts/Skills/Peacemaking.cs, verbatim.
#
# Note there is NO message for "you have no instrument": the skill simply does
# nothing. That silence is why find_instrument() is checked first.
# ---------------------------------------------------------------------------

PEACE_PROMPT = "Whom do you wish to calm?"
PEACE_PICK_INSTRUMENT = "What instrument shall you play?"      # 500617

PEACE_SUCCESS = "You play hypnotic music, calming your target."
PEACE_ALREADY = "That creature is already being calmed."
PEACE_HOPELESS = "You have no chance of calming that creature."
PEACE_FAILED = "You attempt to calm your target, but fail."
PEACE_PLAYED_POORLY = "You play poorly, and there is no effect."
PEACE_NO_INSTRUMENT = ("The instrument you are trying to play is no longer in "
                       "your backpack!")

PEACE_ALL = [PEACE_SUCCESS, PEACE_ALREADY, PEACE_HOPELESS, PEACE_FAILED,
             PEACE_PLAYED_POORLY, PEACE_NO_INSTRUMENT]


# =============================================================================
# RUNTIME STATE
# =============================================================================

_species = {}            # name -> {"name", "bodies", "min_tame"}
_patterns = []           # [(species, compiled regex)] longest name first
_active = {}             # name -> {"species", "deed": serial}
_body_owners = {}        # body -> [species name, ...] for active species only
_deed_graphics = list(DEED_GRAPHICS)
_scanned_once = False
_last_scan = 0.0


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[FillDeeds] " + text, hue, False)


def debug(text, hue=HUE_INFO):
    if DEBUG:
        log(text, hue)


def journal_hit(messages):
    for text in messages:
        if Journal.Search(text):
            return True
    return False


def journal_lines():
    try:
        return [e.Text for e in Journal.GetJournalEntry(0.0)]
    except Exception:
        return []


def dump_journal(prefix):
    if not DEBUG:
        return
    lines = journal_lines()
    if not lines:
        log("%s: journal was silent." % prefix, HUE_WARN)
        return
    for line in lines:
        log("%s: %s" % (prefix, line), HUE_INFO)


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

def build_species():
    """Load the catalogue, apply the overrides, compile the name patterns."""
    _species.clear()
    del _patterns[:]

    rows = list(ANIMAL_CATALOGUE) + list(EXTRA_ANIMALS)
    only = set(n.strip().lower() for n in ONLY_ANIMALS if n.strip())
    never = set(n.strip().lower() for n in NEVER_ANIMALS if n.strip())

    for name, bodies, min_tame in rows:
        key = name.strip().lower()
        if not key or not bodies:
            continue
        if only and key not in only:
            continue
        if key in never:
            continue
        _species[key] = {"name": key, "bodies": list(bodies),
                         "min_tame": float(min_tame)}

    for key, species in _species.items():
        # "ki-rin" also matches "ki rin" and "kirin"; \b stops "rat" matching
        # inside a longer word.
        parts = [p for p in re.split(r"[^a-z0-9]+", key) if p]
        if not parts:
            continue
        pattern = r"\b" + r"[^a-z0-9]*".join(re.escape(p) for p in parts) + r"\b"
        _patterns.append((species, re.compile(pattern)))

    # Longest name first so "hell cat" wins over "cat" and
    # "dread warhorse" over "horse".
    _patterns.sort(key=lambda pair: -len(pair[0]["name"]))

    # The hostility tables are keyed on the same species names, so they are
    # built here - after ONLY_ANIMALS/NEVER_ANIMALS have decided what exists.
    build_aggression()

    # Anything EXTRA_ANIMALS adds may collide with a catalogue body. Fold those
    # collisions into AMBIGUOUS_BODIES so they get name-verified too. The
    # hardcoded entries stay regardless of what ONLY_ANIMALS filtered out.
    owners = {}
    for key, species in _species.items():
        for body in species["bodies"]:
            owners.setdefault(body, []).append(key)
    for body, names in owners.items():
        if len(names) > 1:
            merged = set(AMBIGUOUS_BODIES.get(body, [])) | set(names)
            AMBIGUOUS_BODIES[body] = sorted(merged)

    if only:
        missing = only - set(_species)
        if missing:
            log("ONLY_ANIMALS names not in the catalogue: %s"
                % ", ".join(sorted(missing)), HUE_WARN)

    return len(_species) > 0


def match_species(text):
    """First (longest) catalogue species named in `text`, or None."""
    if not text:
        return None
    low = text.lower()
    for species, pattern in _patterns:
        if pattern.search(low):
            return species
    return None


# =============================================================================
# DEED SCANNING
# =============================================================================

def split_runtogether(raw):
    """Separate tooltip properties that arrive concatenated.

    Real deed text: "Level: 2Creature Type: KirinFilled: 24/60Gold: 100%".
    Lowercasing that gives "kirinfilled", where the trailing \\b in a species
    pattern can never match. Inserting a space at each lower/digit -> upper seam
    turns it into "kirin filled".
    """
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw)


def item_text(item):
    """Name + tooltip of an item: de-concatenated and lowercased."""
    Items.WaitForProps(item, PROPS_TIMEOUT)
    parts = []
    if item.Name:
        parts.append(item.Name)
    try:
        parts.extend(Items.GetPropStringList(item))
    except Exception:
        pass
    return split_runtogether(" ".join(parts)).lower()


def field_value(text, label):
    """Value of a "label: value" tooltip field, or None.

    Fields run into each other, so the value ends at the next field's label:
    "creature type: kirin filled: 24/60" -> "kirin".
    """
    marker = label + ":"
    idx = text.find(marker)
    if idx < 0:
        return None
    rest = text[idx + len(marker):]
    colon = rest.find(":")
    if colon < 0:
        return rest.strip()
    words = rest[:colon].split()
    if len(words) > 1:
        words = words[:-1]        # the trailing word is the next field's label
    return " ".join(words).strip()


def species_from_deed(text):
    """Which species a deed is for. Explicit type field wins over free text."""
    for label in DEED_SPECIES_FIELDS:
        value = field_value(text, label.strip().lower())
        if value:
            species = match_species(value)
            if species is not None:
                return species
    return match_species(text)


def deed_progress(text):
    """(filled, capacity) from a progress field, or None if not stated."""
    for label in DEED_PROGRESS_FIELDS:
        value = field_value(text, label.strip().lower())
        if not value:
            continue
        found = re.search(r"(\d+)\s*/\s*(\d+)", value)
        if found:
            return (int(found.group(1)), int(found.group(2)))
    return None


def is_held(item):
    """Is this item inside the player's own containers?

    Do NOT compare RootContainer to Player.Serial: on this shard RootContainer
    reports the backpack's *item* serial (0x41D40F58), not the player's mobile
    serial, so that test rejects every deed you own.
    """
    roots = [Player.Serial]
    backpack = Player.Backpack
    if backpack is not None:
        roots.append(backpack.Serial)

    if item.RootContainer in roots:
        return True

    # RootContainer may have stopped at a sub-bag; walk up the chain.
    parent = item.Container
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


def looks_like_deed(text):
    if not DEED_NAME_HINTS:
        return True
    for hint in DEED_NAME_HINTS:
        if hint.strip().lower() in text:
            return True
    return False


def pack_items(graphics):
    """Items held by the player, optionally narrowed to certain graphics."""
    f = Items.Filter()
    f.Enabled = True
    f.OnGround = 0
    for graphic in graphics or []:
        f.Graphics.Add(graphic)
    found = Items.ApplyFilter(f)
    if not found:
        return []
    return [i for i in found if is_held(i)]


def scan_deeds(full=False):
    """Rebuild the hunt list from the deeds in the pack. Returns species count."""
    global _scanned_once

    graphics = None if full or not NARROW_RESCAN else _deed_graphics
    items = pack_items(graphics if graphics else None)

    if len(items) > MAX_PACK_SCAN:
        log("Pack has %d items; only reading the first %d."
            % (len(items), MAX_PACK_SCAN), HUE_WARN)
        items = items[:MAX_PACK_SCAN]

    skill = Player.GetSkillValue("Animal Taming")
    found = {}
    skipped_skill = []

    for item in items:
        text = item_text(item)
        if not looks_like_deed(text):
            continue
        species = species_from_deed(text)
        if species is None:
            debug("Deed-like item names no known species: %s"
                  % (item.Name or "0x%X" % item.ItemID), HUE_WARN)
            continue

        progress = deed_progress(text)
        if progress and SKIP_FULL_DEEDS and progress[0] >= progress[1]:
            debug("%s deed is full (%d/%d) - skipping it."
                  % (species["name"], progress[0], progress[1]), HUE_WARN)
            continue

        if SKIP_ABOVE_SKILL and species["min_tame"] > skill:
            if species["name"] not in skipped_skill:
                skipped_skill.append(species["name"])
            continue
        if species["name"] in found:
            continue        # already have a deed for it; this one is a spare

        found[species["name"]] = {"species": species, "deed": item.Serial}
        if item.ItemID not in _deed_graphics:
            _deed_graphics.append(item.ItemID)
        where = "" if not progress else " [%d/%d]" % (progress[0], progress[1])
        debug("Deed: %s -> %s%s" % (item.Name or "0x%X" % item.ItemID,
                                    species["name"], where), HUE_GOOD)

    if not found and not full and NARROW_RESCAN and _scanned_once:
        # Narrow scan came up empty - the deeds may have a new graphic.
        return scan_deeds(full=True)

    _active.clear()
    _active.update(found)

    _body_owners.clear()
    for entry in _active.values():
        for body in entry["species"]["bodies"]:
            _body_owners.setdefault(body, []).append(entry["species"]["name"])

    if skipped_skill:
        log("Skipping (taming %.1f too low): %s"
            % (skill, ", ".join(sorted(skipped_skill))), HUE_WARN)

    _scanned_once = True
    return len(_active)


def rescan(reason):
    global _last_scan
    _last_scan = time.time()
    before = sorted(_active)
    count = scan_deeds()
    after = sorted(_active)
    if after != before:
        if after:
            log("Hunting (%s): %s" % (reason, ", ".join(after)), HUE_GOOD)
        else:
            log("No usable taming order deeds in your pack (%s)." % reason, HUE_WARN)
    return count


# =============================================================================
# IDENTIFYING A CREATURE
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


def is_never_tameable(name):
    """Obviously untameable things, matched on the creature's own name.

    A backstop for when a body value is wrong or a shard reuses one. The name
    check below is the real guard; this catches the case where something scores
    a species match it should not.
    """
    low = (name or "").lower()
    for word in NEVER_TAME_WORDS:
        word = word.strip().lower()
        if word and word in low:
            return word
    return None


def identify(mob):
    """Which species with a deed is this? None means do not touch it.

    THE CREATURE'S NAME DECIDES, not its body.

    Body is only a cheap pre-filter for the scan. It is not proof: two species
    can share one, a shard can reuse one, and a bad catalogue entry can invent
    one - a stray 0x3 in the sheep entry, which is the ZOMBIE body, is exactly
    how this script came to target zombies. So every candidate has its name read
    and matched before anything is targeted, and anything whose name cannot be
    read is left alone. A missed tame costs nothing; taming the wrong thing, or
    swinging at an untameable monster, costs a lot.
    """
    owners = _body_owners.get(mob.Body)
    contenders = AMBIGUOUS_BODIES.get(mob.Body)
    if not owners and not contenders:
        return None

    # A guildmate's pet, or a vendor or mannequin. Checked before the name -
    # it costs nothing. Everything else goes on to the tooltip check at the
    # end; see TAME_NEVER_NOTORIETY for why colour alone is not enough.
    try:
        notoriety = int(mob.Notoriety)
    except Exception:
        notoriety = 0
    if notoriety in TAME_NEVER_NOTORIETY:
        debug("Body 0x%X at notoriety %d is a guildmate's pet or "
              "invulnerable - not quarry." % (mob.Body, notoriety))
        return None

    name = mob_name(mob)
    if not name:
        if REQUIRE_NAME_MATCH:
            debug("Body 0x%X: name will not load - leaving it alone."
                  % mob.Body, HUE_WARN)
            return None
        # Opt-out path: trust the body, but only when it is unambiguous.
        if contenders:
            return None
        return _active[owners[0]]["species"]

    banned = is_never_tameable(name)
    if banned:
        debug("'%s' matches NEVER_TAME_WORDS (%r) - ignoring." % (name, banned),
              HUE_WARN)
        return None

    species = match_species(name)
    if species is None:
        debug("'%s' (body 0x%X) is not a species in the catalogue - ignoring."
              % (name, mob.Body), HUE_WARN)
        return None
    if species["name"] not in _active:
        debug("'%s' is a %s - no deed for that." % (name, species["name"]),
              HUE_INFO)
        return None

    # The name says one thing and the body another: distrust it.
    if mob.Body not in species["bodies"]:
        debug("'%s' reads as %s but its body 0x%X is not one of that species' "
              "bodies %s - ignoring."
              % (name, species["name"], mob.Body,
                 ["0x%X" % b for b in species["bodies"]]), HUE_WARN)
        return None

    # Checked LAST, because it costs a tooltip read and only matters for a
    # creature that is otherwise exactly what we are after.
    text = mobile_tooltip(mob)
    for word in ("(tame)", "(bonded)", "(summoned)"):
        if word in text:
            debug("'%s' is %s - somebody's already." % (name, word), HUE_INFO)
            return None
    # Blue (or orange, criminal) with no pet tag: wild only for the species
    # that are blue in the wild. Anything else at that colour is a pet whose
    # tooltip has not loaded - left alone rather than walked to.
    innocent_wild = set(n.strip().lower() for n in INNOCENT_WILD_SPECIES)
    if notoriety not in TAME_NOTORIETY             and species["name"] not in innocent_wild:
        debug("'%s' is notoriety %d with no pet tag - a %s is never that "
              "colour wild, so it is somebody's." % (name, notoriety,
                                                    species["name"]))
        return None
    if is_paragon(mob, text):
        log("'%s' is a PARAGON - it cannot be tamed. Leaving it." % name,
            HUE_WARN)
        return None

    return species


def is_paragon(mob, text=None):
    """Whether this creature spawned as a paragon. `text`: its tooltip, if
    already read.

    ServUO (Scripts/Mobiles/Special/Paragon.cs) marks one twice: its tooltip
    carries "(Paragon)" (cliloc 1049646) and it is hued PARAGON_HUE. Either
    is enough. A paragon cannot be tamed, and it has several times the
    normal hit points, so it is neither quarry nor something to stand and
    trade Magic Arrows with.
    """
    if not PARAGON_IGNORE:
        return False
    try:
        if int(mob.Color) == PARAGON_HUE:
            return True
    except Exception:
        pass
    if text is None:
        text = mobile_tooltip(mob)
    return "paragon" in text


# =============================================================================
# SEARCH
# =============================================================================

def find_candidates():
    """Deed-backed species in range, nearest first, ignore-list respected."""
    if not _body_owners:
        return []

    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = SCAN_RANGE
    f.CheckIgnoreObject = True
    for body in _body_owners:
        f.Bodies.Add(body)

    found = Mobiles.ApplyFilter(f)
    if not found:
        return []

    nearest = list(found)
    nearest.sort(key=lambda m: Player.DistanceTo(m))
    return nearest


# =============================================================================
# MOVEMENT
# =============================================================================

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
# THREATS
# =============================================================================

# serial -> distance at the previous check. How "is it getting closer?" is
# answered without the protocol telling us anything.
_threat_distance = {}


def forget_threats():
    """Drop the distance history. Call when a tame ends or the target changes."""
    _threat_distance.clear()


def threat_candidates(exclude_serial=None):
    """Hostile-looking mobiles in range, nearest first.

    `exclude_serial` is the creature being tamed. It is grey and it is right
    next to you, so without this it would look exactly like something attacking
    you - and it is the one thing that must never be treated as a threat.
    """
    try:
        scan = Mobiles.Filter()
        scan.Enabled = True
        scan.RangeMax = THREAT_RANGE      # never leave this unset
        found = list(Mobiles.ApplyFilter(scan) or [])
    except Exception as err:
        log("threat scan failed: %s" % err, HUE_WARN)
        return []

    out = []
    for mob in found:
        try:
            serial = int(mob.Serial)
        except Exception:
            continue
        if serial == int(Player.Serial):
            continue
        if exclude_serial is not None and serial == int(exclude_serial):
            continue                       # the creature being tamed
        try:
            if int(mob.Notoriety) not in THREAT_NOTORIETY:
                continue
        except Exception:
            continue

        name = (mob_name(mob) or "").lower()
        if any(word.strip().lower() in name
               for word in THREAT_NEVER_WORDS if word.strip()):
            continue
        out.append(mob)

    out.sort(key=lambda m: Player.DistanceTo(m))
    return out


def closing_threats(exclude_serial=None):
    """Those that have moved TOWARDS you since the last check.

    Grey alone means nothing - every wild animal is grey. Closing distance is
    what separates something that has locked on from scenery.

    The first sighting of a mobile only records its distance; it can only be
    judged once there are two readings to compare. That is deliberate - it
    costs one poll and avoids calling every animal that wanders into range an
    attacker.
    """
    coming = []
    seen = set()
    for mob in threat_candidates(exclude_serial):
        try:
            serial = int(mob.Serial)
            distance = Player.DistanceTo(mob)
        except Exception:
            continue
        seen.add(serial)

        previous = _threat_distance.get(serial)
        _threat_distance[serial] = distance
        if previous is None:
            continue                      # first sighting - nothing to compare
        if previous - distance >= THREAT_CLOSING_TILES:
            coming.append((mob, previous, distance))

    for serial in list(_threat_distance):
        if serial not in seen:
            del _threat_distance[serial]  # out of range; forget it
    return coming


def report_threats(exclude_serial=None):
    """Name anything closing on you. Returns how many.

    Detection only. Nothing is attacked - THREAT_ATTACK is not implemented -
    so this is here to be checked against what you can see on screen before it
    is trusted to pick targets.
    """
    if not THREAT_DETECTION:
        return 0
    coming = closing_threats(exclude_serial)
    for mob, previous, distance in coming:
        try:
            log("  THREAT: %s (notoriety %s) closed %d -> %d tiles"
                % (mob_name(mob) or "0x%X" % int(mob.Serial),
                   mob.Notoriety, previous, distance), HUE_WARN)
        except Exception:
            continue
    return len(coming)


def worth_defending_against(mob):
    """Whether this is something to fight rather than walk away from.

    "Anything not on my list" - the list being the species you hold taming
    deeds for. Those are the whole point of the run and are never attacked,
    however grey they look.

    The gate is deliberately narrow. threat_candidates has already required a
    hostile notoriety AND closing distance, so this is not "clear the zoo": it
    is something that has locked on and is walking at you.
    """
    name = mob_name(mob)
    if not name:
        # Refusing to act on a creature that will not name itself is the same
        # rule the taming half uses. A missed defence costs hit points; the
        # wrong target costs a pet or a murder count.
        debug("A threat would not name itself - not attacking it.", HUE_WARN)
        return False

    if is_never_threat(name):
        return False

    species = match_species(name)
    if species is not None and species["name"] in _active             and not is_paragon(mob):
        # We hold a deed for it. It is quarry, not a threat.
        debug("%s is on the deed list - not attacking it." % name)
        return False

    # A paragon is fought only when it is on the hostile list. A paragon of
    # something passive is left alone even if it wanders closer.
    if is_paragon(mob) and hostile_verdict(mob) is None:
        debug("%s is a paragon of a passive species - ignoring it." % name)
        return False

    return True


def is_never_threat(name):
    low = (name or "").strip().lower()
    if not low:
        return False
    for word in THREAT_NEVER_WORDS:
        word = word.strip().lower()
        if word and word in low:
            return True
    return False


def journal_mark():
    """The newest journal timestamp now. Lines after it are "new"."""
    newest = 0.0
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            if entry.Timestamp > newest:
                newest = entry.Timestamp
    except Exception:
        pass
    return newest


def journal_since(mark):
    """Text of every journal line newer than `mark`. Does not clear."""
    try:
        return [str(e.Text or "") for e in (Journal.GetJournalEntry(mark) or [])
                if e.Timestamp > mark]
    except Exception:
        return []


def _said(lines, message):
    low = message.lower()
    return any(low in (line or "").lower() for line in lines)


def cast_at(serial, spell, school):
    """One cast at one creature. What happened, as a word:

        "cast"         aimed and sent
        "interrupted"  a hit broke it before the cursor came - recast now
        "recovering"   too soon after the last spell - recast in a moment
        "reagents" / "mana"   cannot cast it at all
        "unseen" / "far"      aimed, refused: no line of sight / out of range
        "nocursor"     no cursor and no reason given

    THE one cast helper - defending and clearing a spot both come through
    here. TameAndFill once had two copies and only one got the cursor fix.

    The manual sequence, and the cursor is cleared first: a leaked cursor is
    silently answered by the next TargetExecute. The result is read from the
    journal by TIMESTAMP - this runs mid-tame, and clearing the journal here
    would throw away the tame's own success message.
    """
    if not clear_cursor():
        debug("Target cursor would not clear before casting.", HUE_WARN)
    mark = journal_mark()
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
            return "nocursor"
    except Exception as err:
        log("Casting %s failed: %r" % (spell, err), HUE_BAD)
        return "nocursor"

    # noshow is FALSE deliberately. True hides the cursor from the client, so
    # a cursor the server refuses stays open where the player cannot see it,
    # and every target they click afterwards is silently eaten by it.
    # Sliced, holding the distance between slices - the creature keeps
    # walking while the spell is being cast.
    if not wait_for_cursor(serial, 3000):
        Target.Cancel()
        said = journal_since(mark)
        if _said(said, SPELL_DISTURBED):
            return "interrupted"
        if _said(said, SPELL_NOT_RECOVERED) or _said(said, SPELL_ALREADY_CASTING):
            return "recovering"
        if _said(said, SPELL_NO_REAGENTS):
            return "reagents"
        if _said(said, SPELL_NO_MANA):
            return "mana"
        return "nocursor"
    # The settle the deed and cast sequences both need (CLAUDE.md), kept -
    # but held at distance rather than stood still for.
    kite_pause(serial, 400)
    Target.TargetExecute(serial)

    # The creature can die between the cursor arriving and this landing, in
    # which case the server refuses the target and the cursor stays open.
    Misc.Pause(150)
    if Target.HasTarget():
        debug("Cast cursor was not consumed - cancelling it.", HUE_WARN)
        Target.Cancel()
        Target.ClearQueue()
    said = journal_since(mark)
    if _said(said, SPELL_NOT_SEEN):
        return "unseen"
    if _said(said, SPELL_TOO_FAR):
        return "far"
    return "cast"


def threat_is_dead(mob):
    """Whether a threat we can still see is actually dead.

    Hits alone is NOT the test. A mobile the client has never queried reports
    Hits = 0 AND HitsMax = 0, and 0 there means "nobody asked", not "no health
    left" - reading that as death makes the fight end before it starts.
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


def defend(exclude_serial=None):
    """Fight off a threat while taming. True if it fought.

    Two triggers, either is enough:
      * something closing on you that is not quarry (the original rule), or
      * anything on the kill list within DEFEND_RANGE, closing or not.

    The fight is kill() - Magic Arrow or Energy Bolt by size, bounded by
    casts and clock, and it hands back "escape" when your health is low.
    """
    if not THREAT_ATTACK:
        return False

    target = None
    coming = closing_threats(exclude_serial)
    for mob, _p, _d in coming:
        if worth_defending_against(mob):
            verdict = hostile_verdict(mob)
            target = (mob, verdict[0] if verdict else None,
                      verdict[1] if verdict else None)
            break
    if target is None:
        near = hostiles_near(DEFEND_RANGE, exclude_serial)
        if near:
            target = near[0]
    if target is None:
        return False

    mob, label, hits = target
    serial = int(mob.Serial)
    if not label:
        label = mob_name(mob) or "0x%X" % serial
    log("DEFENDING against %s." % label, HUE_WARN)
    kill(serial, label, hits)
    clear_cursor()
    return True


# =============================================================================
# PEACEMAKING
# =============================================================================

def find_instrument():
    """An instrument in the pack, or None.

    Checked BEFORE the skill is used, because a missing instrument makes
    Peacemaking fail with no message whatsoever - the script would otherwise
    play, wait, see nothing, and report a plain failure forever.
    """
    backpack = Player.Backpack
    if backpack is None:
        return None
    for item in list(getattr(backpack, "Contains", None) or []):
        try:
            if int(item.ItemID) in INSTRUMENT_IDS:
                return item
        except Exception:
            continue
    return None


def is_kill_on_sight(name):
    """Whether this species is one to clear rather than tame.

    Careful with ordering: "lesser hiryu" contains "hiryu", so anything asking
    both questions has to ask THIS one first, or a lesser hiryu reads as a
    tameable hiryu.
    """
    low = (name or "").strip().lower()
    if not low:
        return False
    for word in KILL_ON_SIGHT_WORDS:
        word = word.strip().lower()
        if word and word in low:
            return True
    return False


# Built once by build_species(), so the lookup is a set test rather than a
# scan of 57 names on every creature.
_aggressive = set()
_karma_aggressive = set()


def build_aggression():
    """Load the hostility tables. Called from build_species()."""
    _aggressive.clear()
    _karma_aggressive.clear()
    for n in AGGRESSIVE_SPECIES:
        key = (n or "").strip().lower()
        if key:
            _aggressive.add(key)
    for n in KARMA_AGGRESSIVE_SPECIES:
        key = (n or "").strip().lower()
        if key:
            _karma_aggressive.add(key)

    # A name here that is not a real catalogue species would never match, and
    # would do it silently - which is how a peace list quietly covers nothing.
    unknown = sorted((_aggressive | _karma_aggressive) - set(_species))
    if unknown:
        log("Hostility list names %d species not in the catalogue, which will "
            "never match: %s" % (len(unknown), ", ".join(unknown)), HUE_WARN)


def is_aggressive_species(name):
    """Whether this creature attacks without being provoked.

    BY SPECIES, not by substring. match_species resolves longest-first with
    word boundaries, so "swamp dragon" resolves to the swamp dragon - which is
    FightMode.Aggressor, passive - instead of being caught by a bare "dragon".
    The old word list did exactly that, and said so in its own comment.

    PEACE_AGGRESSIVE_WORDS is still honoured afterwards, for anything the
    catalogue does not know about.
    """
    low = (name or "").strip().lower()
    if not low:
        return False

    species = match_species(low)
    if species is not None:
        key = species["name"]
        if key in _aggressive:
            return True
        if key in _karma_aggressive:
            # FightMode.Evil - hostile only to players of evil karma.
            return bool(PEACE_KARMA_AGGRESSIVE)
        # A species the catalogue KNOWS and did not list is passive. Do not
        # fall through to the substring list and let "dragon" claim it.
        return _substring_aggressive(low)

    return _substring_aggressive(low)


def _substring_aggressive(low):
    """The old behaviour, for names the catalogue cannot resolve."""
    for word in PEACE_AGGRESSIVE_WORDS:
        word = word.strip().lower()
        if word and word in low:
            return True
    return False


def should_peace(mob, name=None):
    """Whether to play at this creature before taming it."""
    if not PEACE_ENABLED or PEACE_WHEN == "never":
        return False
    if PEACE_WHEN == "always":
        return True
    if PEACE_WHEN == "fighting":
        try:
            return bool(mob.WarMode)
        except Exception:
            return False
    if PEACE_WHEN == "aggressive":
        if name is None:
            name = mob_name(mob)
        # A creature already swinging gets calmed whatever it is called - the
        # word list is about temperament, not about what is happening now.
        try:
            if bool(mob.WarMode):
                return True
        except Exception:
            pass
        return is_aggressive_species(name)
    return False


def peacemake(serial, label):
    """Play Peacemaking at one creature. What happened, as a word.

        "calmed"      it worked, or it was already calm
        "hopeless"    it can never be calmed - do not try again
        "failed"      the attempt failed; trying again may work
        "noinstrument" nothing to play
        "lost"        the creature is gone

    Two target cursors are possible. The server remembers your instrument and
    only asks "What instrument shall you play?" when it is not in your pack, so
    that prompt is answered if it appears and ignored when it does not.
    """
    if find_instrument() is None:
        return "noinstrument"

    mob = Mobiles.FindBySerial(serial)
    if mob is None:
        return "lost"

    Journal.Clear()
    clear_cursor()
    Player.UseSkill("Peacemaking")

    # noshow is FALSE everywhere in this script now. True hides the cursor
    # from the client, so one the server never consumes sits there unseen
    # and eats whatever the player clicks next. Nothing is gained by
    # hiding it, and an invisible leak cannot be diagnosed from in game.
    if not Target.WaitForTarget(TARGET_CURSOR_TIMEOUT, False):
        Misc.Pause(300)
        clear_cursor()
        return "failed"

    # If this cursor is the instrument picker, answer it with the instrument
    # and wait for the SECOND cursor - the one that asks who to calm.
    if Journal.Search(PEACE_PICK_INSTRUMENT):
        instrument = find_instrument()
        if instrument is None:
            clear_cursor()
            return "noinstrument"
        Target.TargetExecute(int(instrument.Serial))
        Misc.Pause(PEACE_SETTLE_MS)
        if not Target.WaitForTarget(TARGET_CURSOR_TIMEOUT, False):
            clear_cursor()
            return "failed"

    Target.TargetExecute(serial)

    deadline = time.time() + (PEACE_RESULT_MS / 1000.0)
    while time.time() < deadline:
        Misc.Pause(200)
        if Journal.Search(PEACE_SUCCESS):
            return "calmed"
        if Journal.Search(PEACE_ALREADY):
            return "calmed"
        if Journal.Search(PEACE_HOPELESS):
            return "hopeless"
        if Journal.Search(PEACE_NO_INSTRUMENT):
            return "noinstrument"
        if Journal.Search(PEACE_FAILED) or Journal.Search(PEACE_PLAYED_POORLY):
            return "failed"
        if Mobiles.FindBySerial(serial) is None:
            return "lost"

    clear_cursor()
    return "failed"


def calm_before_taming(serial, label):
    """Try to calm a creature before taming it. True if it is calm.

    A failure is NOT fatal - taming goes ahead anyway, just the hard way. The
    point is to improve the odds on an aggressive, not to gate the whole run
    behind a bard skill.
    """
    mob = Mobiles.FindBySerial(serial)
    if mob is None or not should_peace(mob, label):
        return False

    for attempt in range(1, max(1, PEACE_ATTEMPTS) + 1):
        result = peacemake(serial, label)

        if result == "calmed":
            log("  %s is calm." % label, HUE_GOOD)
            return True
        if result == "hopeless":
            log("  %s can never be calmed - taming it as it is." % label,
                HUE_WARN)
            return False
        if result == "noinstrument":
            log("  No instrument in your pack, so Peacemaking does nothing - "
                "it fails silently without one. Carry a lute or drums, or set "
                "PEACE_ENABLED = False.", HUE_BAD)
            return False
        if result == "lost":
            return False

        if attempt < PEACE_ATTEMPTS:
            Misc.Pause(PEACE_RETRY_MS)

    log("  Could not calm %s - taming it anyway." % label, HUE_WARN)
    return False


# =============================================================================
# TAMING
# =============================================================================

def watch_attempt(serial):
    """Poll the journal until this taming attempt resolves.

    Stays glued to the creature the whole time - it wanders while being tamed,
    and drifting costs the attempt to either the range re-check or the line of
    sight check. Caller must Journal.Clear() first.
    """
    deadline = time.time() + TAME_ATTEMPT_TIMEOUT / 1000.0
    next_threat_check = 0.0

    while time.time() < deadline:
        # While standing still taming is exactly when something gets to walk
        # up on you unnoticed. The creature being tamed is excluded by serial:
        # it is grey and adjacent, so it would otherwise look like the threat.
        if THREAT_DETECTION and time.time() >= next_threat_check:
            next_threat_check = time.time() + 1.0
            report_threats(exclude_serial=serial)
            # Fighting back RESETS the taming clock: the time spent defending
            # is not time the tame was failing, and charging it against the
            # attempt would abandon a tame that was going fine.
            if defend(exclude_serial=serial):
                # The tame keeps running on the server while we fight, so
                # its result may be sitting in the journal right now. Read it
                # BEFORE clearing - clearing first is how a finished tame
                # was lost and the pet left following you with no deed.
                if journal_hit(MSG_SUCCESS):
                    return "success"
                deadline = time.time() + TAME_ATTEMPT_TIMEOUT / 1000.0
                Journal.Clear()

        if too_hurt():
            return "flee"

        if journal_hit(MSG_SUCCESS):
            return "success"
        if journal_hit(MSG_ABORT):
            return "abort"
        if journal_hit(MSG_SKIP):
            return "skip"
        if journal_hit(MSG_CONTESTED):
            return "contested"
        if journal_hit(MSG_BLOCKED):
            return "blocked"
        if journal_hit(MSG_REPOSITION):
            return "reposition"
        if journal_hit(MSG_RETRY):
            return "retry"

        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            return "lost"

        gap = Player.DistanceTo(mob)
        if gap > LEASH_DIST:
            # Already past the server's cutoff - stop flailing and let the
            # caller do a proper pathfound approach.
            return "reposition"
        if gap > STAY_DIST:
            step_toward(mob)

        Misc.Pause(POLL_MS)

    return "timeout"


def tame(serial, label):
    """Work one creature until tamed or ruled out.

    Returns "success", "skip", "lost", "unreachable", "exhausted",
    "abort" or "flee" (your health is low - leave).
    """
    attempts = 0
    blocked = 0
    started = time.time()

    calmed_at = [0.0]
    forget_threats()      # distances from the last creature mean nothing here

    while attempts < MAX_TAME_ATTEMPTS:
        if (time.time() - started) * 1000.0 >= TAME_CREATURE_MAX_MS:
            log("%s: %d minute(s) on one creature - leaving it."
                % (label, TAME_CREATURE_MAX_MS / 60000), HUE_WARN)
            return "exhausted"
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            return "lost"

        # Calm it before the first attempt, and again once the calm has had
        # time to wear off - ServUO gives 10-120 seconds depending on how hard
        # the creature is, so a long tame outlives it.
        stale = (PEACE_REFRESH_MS > 0 and calmed_at[0] > 0 and
                 (time.time() - calmed_at[0]) * 1000 >= PEACE_REFRESH_MS)
        if calmed_at[0] == 0.0 or stale:
            if calm_before_taming(serial, label):
                calmed_at[0] = time.time()
            else:
                # Do not re-play at something that cannot be calmed, or with no
                # instrument - it would retry every single attempt.
                calmed_at[0] = time.time() if PEACE_ENABLED else 0.0

        if Player.DistanceTo(mob) > STAY_DIST:
            # Aim for adjacent, settle for TAME_START_DIST if terrain will not
            # let us touch it - the server allows 3 to start an attempt.
            approach(serial, STAY_DIST, TAME_START_DIST)
            mob = Mobiles.FindBySerial(serial)
            if mob is None:
                return "lost"
            if Player.DistanceTo(mob) > TAME_START_DIST:
                return "unreachable"

        attempts += 1
        log("Taming %s (attempt %d/%d)" % (label, attempts, MAX_TAME_ATTEMPTS))

        Journal.Clear()
        clear_cursor()
        Player.UseSkill("Animal Taming")

        if not Target.WaitForTarget(TARGET_CURSOR_TIMEOUT, False):
            # Cancel a cursor that shows up late, or it survives into the next
            # iteration and swallows a later TargetExecute - including the deed's.
            Misc.Pause(500)
            clear_cursor()
            continue

        Target.TargetExecute(serial)
        result = watch_attempt(serial)

        if result == "success":
            log("%s tamed." % label, HUE_GOOD)
            return "success"
        if result == "skip":
            # "Looks tame already" is also what you hear when the tame went
            # through and its own message was missed. If it is OURS, it is a
            # success, and it must go in the deed before we move on.
            if is_our_pet(serial):
                log("%s is already your pet - counting it as tamed." % label,
                    HUE_GOOD)
                return "success"
            log("%s cannot be tamed by you - ignoring." % label, HUE_WARN)
            return "skip"
        if result == "abort":
            return "abort"
        if result == "flee":
            return "flee"
        if result == "lost":
            return "lost"
        if result == "contested":
            log("%s is being tamed by someone else - backing off." % label, HUE_WARN)
            Misc.Pause(CONTESTED_BACKOFF)
        elif result == "blocked":
            blocked += 1
            if blocked >= TAME_MAX_BLOCKED:
                log("%s: no clear path, %d times - it is behind a wall or in "
                    "a house. Leaving it." % (label, blocked), HUE_WARN)
                return "unreachable"
            approach(serial, STAY_DIST, TAME_START_DIST)
        elif result == "reposition":
            before = Player.DistanceTo(mob)
            approach(serial, STAY_DIST, TAME_START_DIST)
            mob = Mobiles.FindBySerial(serial)
            # Told to get closer while already as close as walking gets us:
            # that is a wall too, just reported differently.
            if mob is not None and Player.DistanceTo(mob) >= before \
                    and before <= TAME_START_DIST:
                blocked += 1
                if blocked >= TAME_MAX_BLOCKED:
                    log("%s: cannot get any closer - leaving it." % label,
                        HUE_WARN)
                    return "unreachable"
        elif result == "timeout":
            log("Attempt timed out, retrying.", HUE_WARN)

        Misc.Pause(500)

    return "exhausted"


# =============================================================================
# DEED USE
# =============================================================================

def pet_is_gone(pet_serial):
    return Mobiles.FindBySerial(pet_serial) is None


def deed_attempt(deed_serial, pet_serial):
    """One double-click + target cycle. "ok", "nocursor" or "rejected".

    This exact sequence - drop stale cursor, double-click, wait for a fresh
    cursor, settle, TargetExecute(serial) - is confirmed working in-game
    (diag_deed_target.py sequence 1). Do not "simplify" the clear_cursor call or
    the settle pause away; both are load-bearing. See docs.
    """
    if not clear_cursor():
        log("A target cursor is stuck open; cannot use the deed cleanly.", HUE_BAD)
        return "nocursor"

    Journal.Clear()
    Items.UseItem(deed_serial)

    if not Target.WaitForTarget(DEED_TARGET_TIMEOUT, False):
        log("Deed did not ask for a target.", HUE_BAD)
        dump_journal("deed")
        return "nocursor"

    Misc.Pause(DEED_SETTLE_MS)
    Target.TargetExecute(pet_serial)
    Misc.Pause(DEED_RESULT_MS)

    dump_journal("deed")

    if pet_is_gone(pet_serial):
        return "ok"
    if MSG_DEED_SUCCESS and journal_hit(MSG_DEED_SUCCESS):
        return "ok"
    if MSG_DEED_REJECT and journal_hit(MSG_DEED_REJECT):
        return "rejected"

    if Target.HasTarget():
        log("Target cursor still open after answering it.", HUE_WARN)
        Target.Cancel()

    return "rejected"


def add_to_deed(species_name, pet_serial):
    """Put the freshly tamed pet into that species' deed."""
    entry = _active.get(species_name)
    if entry is None:
        log("No deed registered for %s any more." % species_name, HUE_BAD)
        return False

    deed = Items.FindBySerial(entry["deed"])
    if deed is None or not is_held(deed):
        log("The %s deed left your pack - rescanning." % species_name, HUE_WARN)
        rescan("deed vanished")
        entry = _active.get(species_name)
        if entry is None:
            return False
        deed = Items.FindBySerial(entry["deed"])
        if deed is None:
            return False

    # Final guard: the deed must still name this species.
    text = item_text(deed)
    matched = species_from_deed(text)
    if matched is None or matched["name"] != species_name:
        log("Refusing to use %s for %s - it reads as %s."
            % (deed.Name or "deed", species_name,
               matched["name"] if matched else "no known species"), HUE_BAD)
        return False

    debug("Deed 0x%X (%s) <- pet 0x%X"
          % (deed.Serial, deed.Name or "?", pet_serial))

    for attempt in range(1, DEED_RETRIES + 1):
        if pet_is_gone(pet_serial):
            log("%s added to its taming order." % species_name, HUE_GOOD)
            return True

        result = deed_attempt(deed.Serial, pet_serial)
        if result == "ok":
            log("%s added to its taming order." % species_name, HUE_GOOD)
            return True

        log("Deed attempt %d/%d did not take (%s)."
            % (attempt, DEED_RETRIES, result), HUE_WARN)
        Misc.Pause(800)

        # The deed may have completed and been consumed.
        rescan("mid-deed retry")
        entry = _active.get(species_name)
        if entry is None:
            log("No %s deed left to retry with." % species_name, HUE_BAD)
            return False
        fresh = Items.FindBySerial(entry["deed"])
        if fresh is not None:
            deed = fresh

    log("Could not add %s to a deed after %d attempts. Run "
        "Scripts/diag_deed_target.py to find the working sequence."
        % (species_name, DEED_RETRIES), HUE_BAD)
    return False


# =============================================================================
# HOSTILE IDENTIFICATION
# =============================================================================

# [(name, hits or None, is_hostile, compiled regex)], longest name first.
#
# The TAMEABLE CATALOGUE goes in too, tagged by whether it is hostile, and
# that is the point: "dragon" is hostile and "swamp dragon" is not, and with
# both in one longest-first list a swamp dragon resolves to the swamp dragon
# and is left alone - the same trap AGGRESSIVE_SPECIES documents.
_hostile_patterns = []

# serial -> (label, hits) or None. A verdict costs a tooltip read, so it is
# made once per creature per spot. Cleared on every recall.
_hostile_verdict = {}


def name_pattern(name):
    """Regex for a creature name: flexible separators, whole words."""
    parts = [p for p in re.split(r"[^a-z0-9]+", name) if p]
    if not parts:
        return None
    return re.compile(r"\b" + r"[^a-z0-9]*".join(re.escape(p) for p in parts)
                      + r"\b")


def build_hostiles():
    """Compile the hostile tables. Returns how many hostile names there are."""
    del _hostile_patterns[:]
    rows = {}
    for name, hits in HOSTILE_HITS.items():
        rows[name.strip().lower()] = (int(hits), True)

    def add(name, hostile):
        # "Savage (Female)" is a UOGuide page title; in game it is "a savage".
        key = re.sub(r"\s*\([^)]*\)", "", (name or "")).strip().lower()
        if key and key not in rows:
            rows[key] = (None, hostile)

    for name in OFFICIAL_HOSTILE_NAMES:
        add(name, True)
    for name in AGGRESSIVE_SPECIES:
        add(name, True)
    for name in KILL_ON_SIGHT_WORDS:
        add(name, True)
    # Every catalogue species not already tagged hostile is PASSIVE - it is
    # in the list only so that it wins the longest-match against a shorter
    # hostile name it contains.
    for name, _bodies, _skill in list(ANIMAL_CATALOGUE) + list(EXTRA_ANIMALS):
        add(name, False)

    for key, (hits, hostile) in rows.items():
        pattern = name_pattern(key)
        if pattern is not None:
            _hostile_patterns.append((key, hits, hostile, pattern))
    _hostile_patterns.sort(key=lambda row: -len(row[0]))
    return sum(1 for row in _hostile_patterns if row[2])


def hostile_by_name(name):
    """(label, hits) when this name is a hostile creature, else None.

    The LONGEST matching name decides, hostile or not. A first hit that is a
    passive species ends the search - that is what keeps "dragon" from
    claiming a swamp dragon.
    """
    low = split_runtogether(name or "").lower()
    if not low:
        return None
    for key, hits, hostile, pattern in _hostile_patterns:
        if pattern.search(low):
            return (key, hits) if hostile else None
    return None


def mobile_tooltip(mob):
    """Name and tooltip of a mobile, lowercased. "" if it will not load."""
    try:
        Mobiles.WaitForProps(mob, PROPS_TIMEOUT)
        lines = list(Mobiles.GetPropStringList(mob) or [])
    except Exception:
        lines = []
    name = ""
    try:
        name = mob.Name or ""
    except Exception:
        pass
    return split_runtogether(name + " " + " ".join(str(l or "") for l in lines)
                             ).lower()


def is_quarry(name):
    """Is this a species we hold an unfilled deed for? Never attacked."""
    species = match_species(name or "")
    return species is not None and species["name"] in _active


def hostile_verdict(mob):
    """(label, hits) when this mobile is to be killed, else None.

    The gate, every part of which has to pass:
      notoriety attackable  ->  not a player-shaped innocent  ->  not quarry
      ->  hostile by name, or by body AND red  ->  tooltip not tame/summoned
    """
    try:
        serial = int(mob.Serial)
    except Exception:
        return None
    if serial in _hostile_verdict:
        return _hostile_verdict[serial]

    verdict = None
    try:
        notoriety = int(mob.Notoriety)
    except Exception:
        notoriety = 0

    if notoriety in KILL_NOTORIETY and not bool(getattr(mob, "IsGhost", False)):
        # A human body is what every player wears. Only a red one is fair
        # game, and only when its name says it is a brigand or the like.
        human = bool(getattr(mob, "IsHuman", False))
        if not human or notoriety == 6:
            name = mob_name(mob) or ""
            # Quarry is never attacked - UNLESS it is a paragon, which cannot
            # be tamed and so is not quarry at all. A dire wolf paragon is a
            # hostile dire wolf with five times the hit points.
            if not is_quarry(name) or is_paragon(mob):
                verdict = hostile_by_name(name)
                if verdict is None and not human:
                    entry = HOSTILE_BODIES.get(int(mob.Body))
                    if entry is not None and notoriety in KILL_BODY_NOTORIETY:
                        verdict = (entry[0], entry[1])
                if verdict is None and KILL_ALL_RED and notoriety == 6:
                    # Red name, nothing else known about it. Size unknown,
                    # so SPELL_UNKNOWN_IS_BIG picks the spell.
                    verdict = (name or "red 0x%X" % int(mob.Body), None)
                if verdict is not None and is_paragon(mob):
                    # Hostile AND a paragon: still killed, but sized up first
                    # so the spell is picked for what it really is.
                    hits = verdict[1]
                    verdict = ("%s (paragon)" % verdict[0],
                               SPELL_BIG_HITS if hits is None
                               else int(hits) * PARAGON_HITS_MULT)
                if verdict is not None:
                    text = mobile_tooltip(mob)
                    for word in KILL_NEVER_WORDS:
                        if word.strip().lower() in text:
                            debug("%s matches KILL_NEVER_WORDS (%r) - leaving "
                                  "it." % (name or verdict[0], word), HUE_INFO)
                            verdict = None
                            break
                if verdict is not None and is_never_threat(name):
                    verdict = None

    _hostile_verdict[serial] = verdict
    return verdict


def hostiles_near(range_tiles, exclude_serial=None):
    """[(mob, label, hits)] to be killed, nearest first."""
    if not KILL_ENABLED:
        return []
    try:
        f = Mobiles.Filter()
        f.Enabled = True
        f.RangeMax = range_tiles          # never leave this unset
        f.CheckIgnoreObject = True
        f.IgnorePets = True
        found = list(Mobiles.ApplyFilter(f) or [])
    except Exception as err:
        log("hostile scan failed: %r" % (err,), HUE_WARN)
        return []

    out = []
    for mob in found:
        try:
            serial = int(mob.Serial)
        except Exception:
            continue
        if serial == int(Player.Serial):
            continue
        if exclude_serial is not None and serial == int(exclude_serial):
            continue
        verdict = hostile_verdict(mob)
        if verdict is not None:
            out.append((mob, verdict[0], verdict[1]))
    out.sort(key=lambda row: Player.DistanceTo(row[0]))
    return out


# =============================================================================
# KILLING
# =============================================================================

def is_big(hits):
    """Whether a creature of this many hit points gets the big spell."""
    if hits is None:
        return bool(SPELL_UNKNOWN_IS_BIG)
    return int(hits) >= SPELL_BIG_HITS


def pick_spell(hits):
    """(spell, mana) for a creature of `hits` hit points."""
    if is_big(hits):
        return SPELL_BIG, SPELL_BIG_MANA
    return SPELL_SMALL, SPELL_SMALL_MANA


def health_pct(mob):
    """Health as a percentage, or None when the client does not know it.

    Other mobiles' health arrives as a fraction (out of 25 on most shards),
    which is exactly enough for this. HitsMax 0 means nobody asked - see
    threat_is_dead.
    """
    try:
        hits = int(mob.Hits or 0)
        hits_max = int(mob.HitsMax or 0)
    except Exception:
        return None
    if hits_max <= 0:
        return None
    return hits * 100.0 / hits_max


def player_health_pct():
    try:
        hits_max = int(Player.HitsMax or 0)
        if hits_max <= 0:
            return 100.0
        return int(Player.Hits or 0) * 100.0 / hits_max
    except Exception:
        return 100.0


def too_hurt():
    """True when it is time to leave."""
    return ESCAPE_ENABLED and player_health_pct() < ESCAPE_HITS_PCT


_DIRECTIONS = ["North", "Right", "East", "Down", "South", "Left", "West",
               "Up"]


def step_away_from(mob):
    """One step directly away from it - or, if that is blocked, either side of
    directly away. True if we moved.

    The side steps matter: backing straight into a wall or a tree is the
    usual way a kite stops working, and the tile at 45 degrees is nearly as
    good for distance.
    """
    dx = Player.Position.X - mob.Position.X
    dy = Player.Position.Y - mob.Position.Y
    if dx == 0 and dy == 0:
        dx = 1                          # standing on it; any way out will do
    first = direction_to(dx, dy)
    i = _DIRECTIONS.index(first)
    for direction in (first, _DIRECTIONS[(i + 1) % 8],
                      _DIRECTIONS[(i - 1) % 8]):
        # TWO tries per direction. A move you are not FACING only turns you
        # - the step needs a second one. One try each turned the character
        # three ways on the spot, read every turn as a wall, and then cast
        # with the monster still beside you (2026-10-25.6).
        for _ in range(2):
            before = (Player.Position.X, Player.Position.Y)
            move(direction)
            if (Player.Position.X, Player.Position.Y) != before:
                return True
            Misc.Pause(100)         # the position can trail the move
            if (Player.Position.X, Player.Position.Y) != before:
                return True
    return False


def enforce_distance(serial):
    """One correction step towards KITE_HOLD. False if it is gone or we died.

    COVFarm's enforce_distance: safe to call in the middle of anything - it
    only ever takes a single step, and does nothing once the gap is right.
    """
    if Player.IsGhost:
        return False
    mob = Mobiles.FindBySerial(serial)
    if mob is None:
        return False
    gap = Player.DistanceTo(mob)
    if gap < KITE_HOLD:
        step_away_from(mob)
    elif gap > KITE_HOLD:
        step_toward(mob)
    return True


def kite_pause(serial, milliseconds):
    """Wait, holding the distance the whole time. False if it is gone."""
    deadline = time.time() + max(0, milliseconds) / 1000.0
    while time.time() < deadline:
        if not enforce_distance(serial):
            return False
        Misc.Pause(KITE_TICK_MS)
    return True


def wait_for_cursor(serial, timeout_ms):
    """Wait for the target cursor WITHOUT standing still for it.

    Target.WaitForTarget blocks, so asking it for the whole timeout at once
    leaves the distance unmanaged for seconds. Short slices, a correction
    between each - straight from COVFarm.
    """
    deadline = time.time() + max(0, timeout_ms) / 1000.0
    while time.time() < deadline:
        if Target.WaitForTarget(KITE_TICK_MS, False):
            return True
        enforce_distance(serial)
    return bool(Target.HasTarget())


def close_in(serial, timeout_ms=None):
    """Step towards it until it is within KITE_HOLD. One step at a time, so
    it stops the moment it is close enough - never the pathfinder."""
    if timeout_ms is None:
        timeout_ms = APPROACH_TIMEOUT
    deadline = time.time() + timeout_ms / 1000.0
    stuck = 0
    while time.time() < deadline:
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            return False
        if Player.DistanceTo(mob) <= KITE_HOLD:
            return True
        before = (Player.Position.X, Player.Position.Y)
        step_toward(mob)
        Misc.Pause(MOVE_PAUSE)
        if (Player.Position.X, Player.Position.Y) == before:
            stuck += 1
            if stuck >= STUCK_LIMIT:
                return False
        else:
            stuck = 0
    return False


def wait_for_mana(need, timeout_ms=None, serial=None):
    """Wait until there is mana for one cast. False if it never comes.

    With `serial`, the distance to that creature is held while waiting -
    standing still for mana is exactly when something walks up and hits you.
    """
    if timeout_ms is None:
        timeout_ms = KILL_MANA_WAIT_MS
    deadline = time.time() + timeout_ms / 1000.0
    said = False
    while time.time() < deadline:
        try:
            if int(Player.Mana or 0) >= int(need):
                return True
        except Exception:
            return True         # cannot read it - do not block on that
        if too_hurt():
            return False
        if not said:
            said = True
            log("Waiting for mana (%s of %s needed)." % (Player.Mana, need))
        if serial is not None:
            kite_pause(serial, 500)
        else:
            Misc.Pause(500)
    log("Still no mana after %ds." % (timeout_ms / 1000), HUE_WARN)
    return False


def get_in_range(serial, label):
    """Be within SPELL_RANGE of it, without walking in further. True if so.

    Something coming at you is WAITED FOR - it closes the gap and you get the
    first shot. Only something that is staying put is walked to, a step at a
    time and only to KITE_HOLD (close_in). This used to call approach(),
    whose pathfinder walks to the tile beside the creature: the tamer ran
    straight into what it was meant to shoot.
    """
    mob = Mobiles.FindBySerial(serial)
    if mob is None:
        return False
    gap = Player.DistanceTo(mob)
    if gap <= SPELL_RANGE:
        return True

    deadline = time.time() + KILL_WAIT_FOR_MS / 1000.0
    last = gap
    while time.time() < deadline:
        Misc.Pause(POLL_MS)
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            return False
        gap = Player.DistanceTo(mob)
        if gap <= SPELL_RANGE:
            return True
        if gap >= last:
            break                   # not coming - go to it
        last = gap

    close_in(serial)
    mob = Mobiles.FindBySerial(serial)
    return mob is not None and Player.DistanceTo(mob) <= SPELL_RANGE


def kill(serial, label, hits):
    """Cast at one creature until it dies. What happened, as a word.

        "dead"     it died or vanished
        "escape"   your own health went under ESCAPE_HITS_PCT - leave now
        "gone"     it ran off out of reach
        "gave up"  out of casts, time, mana, or casts that would not go out

    FROM FULL SPELL RANGE. get_in_range never walks in past SPELL_RANGE.

    TWICE IF NEEDED, AND STRAIGHT AWAY. After a cast lands there is only
    KILL_LAND_MS before the next decision, so a creature the first arrow did
    not finish gets the second at once. A cast BROKEN by a hit is recast
    immediately and is not counted against the creature - before this, three
    broken casts read as "check your reagents" and the monster hitting you
    was given up on and ignored.
    """
    spell, mana = pick_spell(hits)
    log("Killing %s (%s hits) with %s."
        % (label, "?" if hits is None else hits, spell), HUE_WARN)

    # Ask for the status before reading it - see threat_is_dead.
    try:
        Mobiles.WaitForStats(serial, 1500)
    except Exception:
        pass

    deadline = time.time() + KILL_TIMEOUT_MS / 1000.0
    casts = 0
    small_casts = 0
    misses = 0
    interrupts = 0
    while casts < KILL_MAX_CASTS and time.time() < deadline:
        if too_hurt():
            return "escape"
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            log("%s is gone after %d cast(s)." % (label, casts), HUE_GOOD)
            return "dead"
        if threat_is_dead(mob):
            log("%s is down after %d cast(s)." % (label, casts), HUE_GOOD)
            return "dead"

        # TOO CLOSE: back off before anything else. A cast started with it
        # beside you is a cast its first swing breaks.
        if Player.DistanceTo(mob) < KITE_MIN:
            if not step_away_from(mob):
                debug("%s is close and there is nowhere to back off to - "
                      "casting anyway." % label, HUE_WARN)
            else:
                Misc.Pause(MOVE_PAUSE)
                continue

        if Player.DistanceTo(mob) > SPELL_RANGE:
            if not get_in_range(serial, label):
                if Mobiles.FindBySerial(serial) is None:
                    return "dead"
                log("%s is out of reach - leaving it." % label, HUE_WARN)
                Misc.IgnoreObject(serial)
                return "gone"
            mob = Mobiles.FindBySerial(serial)
            if mob is None:
                return "dead"

        # It was bigger than the table said: four arrows in and still mostly
        # healthy. Up to the bolt for the rest of the fight.
        if spell == SPELL_SMALL and small_casts >= SPELL_UPGRADE_AFTER:
            pct = health_pct(mob)
            if pct is not None and pct >= SPELL_UPGRADE_HEALTH_PCT:
                log("%s is still at %d%% after %d %s - switching to %s."
                    % (label, pct, small_casts, SPELL_SMALL, SPELL_BIG),
                    HUE_WARN)
                spell, mana = SPELL_BIG, SPELL_BIG_MANA

        if not wait_for_mana(mana, serial=serial):
            if too_hurt():
                return "escape"
            Misc.IgnoreObject(serial)
            return "gave up"

        outcome = cast_at(serial, spell, SPELL_SCHOOL)
        if outcome == "cast":
            casts += 1
            misses = 0
            interrupts = 0
            if spell == SPELL_SMALL:
                small_casts += 1
            kite_pause(serial, KILL_LAND_MS)
            continue
        if outcome == "interrupted":
            interrupts += 1
            debug("%s: cast broken by a hit (%d) - again." % (label, interrupts),
                  HUE_WARN)
            if interrupts >= KILL_MAX_INTERRUPTS:
                log("%d casts in a row broken by hits - leaving %s."
                    % (interrupts, label), HUE_BAD)
                return "gave up"
            continue                        # no pause: recast now
        if outcome == "recovering":
            kite_pause(serial, KILL_RECOVER_MS)
            continue
        if outcome in ("unseen", "far"):
            # Aimed and refused. Step in a little - but no closer than the
            # spell needs, so this cannot become walking into its reach.
            debug("%s: %s - closing a little." % (
                label, "no line of sight" if outcome == "unseen"
                else "out of range"), HUE_WARN)
            misses += 1
            if misses >= 3:
                log("%s cannot be hit from here - leaving it." % label,
                    HUE_WARN)
                Misc.IgnoreObject(serial)
                return "gave up"
            mob = Mobiles.FindBySerial(serial)
            if mob is not None:
                for _ in range(2):
                    step_toward(mob)
                    Misc.Pause(MOVE_PAUSE)
            continue
        if outcome == "reagents":
            log("Out of reagents for %s - stopping the fight." % spell,
                HUE_BAD)
            return "gave up"
        if outcome == "mana":
            continue                        # wait_for_mana handles it

        misses += 1
        if misses >= 3:
            log("Three casts in a row did not go out and the server said "
                "nothing - leaving %s." % label, HUE_BAD)
            Misc.IgnoreObject(serial)
            return "gave up"
        Misc.Pause(KILL_RECOVER_MS)

    if Mobiles.FindBySerial(serial) is None:
        return "dead"
    log("%s is still up after %d cast(s) - leaving it." % (label, casts),
        HUE_WARN)
    Misc.IgnoreObject(serial)
    return "gave up"


def clear_hostiles(exclude_serial=None, range_tiles=None):
    """Kill the nearest hostile in range. Its outcome, or None if none."""
    if range_tiles is None:
        range_tiles = KILL_RANGE
    found = hostiles_near(range_tiles, exclude_serial)
    if not found:
        return None
    mob, label, hits = found[0]
    outcome = kill(int(mob.Serial), label, hits)
    clear_cursor()
    return outcome


# =============================================================================
# THE ACCOUNT RUNEBOOK
#
# Lifted from ReagentBuyer.py, which walks this book for its vendor round.
# Button numbers were read off the Gump Inspector - see
# docs/account-runebook-gump.md. They are not tunables.
# =============================================================================

AR_COMMAND = "[ar"
AR_GUMPID = 0xC395ADB4
AR_NEXT_PAGE_BUTTON = 504
AR_PREV_PAGE_BUTTON = 503
AR_ROOT_BUTTON = 5
AR_ENTRY_BUTTON_MIN = 10
AR_ENTRY_BUTTON_MAX = 499
AR_GATE_OFFSET = 30000
# THE THIRD BUTTON ON EVERY RUNE ROW IS DELETE (entry + 60000). The entry
# range above is what keeps it out of the pairing. Nothing here presses one.
AR_DELETE_OFFSET = 60000
AR_CONTROL_BUTTONS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 500, 503, 504]
AR_MAX_PAGES = 20
AR_GUMP_TIMEOUT_MS = 10000
RECALL_SETTLE_MS = 2500
ARRIVE_TOLERANCE = 3
RUNE_MATCH_MIN_PREFIX = 4
SLEEP_SLICE_MS = 1000


def has_gump(gump_id):
    try:
        return bool(Gumps.HasGump(gump_id))
    except Exception:
        return False


def gump_lines(gump_id):
    try:
        raw = Gumps.GetLineList(gump_id, False)
    except TypeError:
        try:
            raw = Gumps.GetLineList(gump_id)
        except Exception:
            return []
    except Exception:
        return []
    return list(raw or [])


def chat_say(phrase):
    """ChatSay takes (msg) and (colour, msg) on every build. Both tried."""
    try:
        Player.ChatSay(phrase)
        return True
    except TypeError:
        pass
    except Exception as err:
        log("could not say %r: %r" % (phrase, err), HUE_BAD)
        return False
    try:
        Player.ChatSay(HUE_INFO, phrase)
        return True
    except Exception as err:
        log("could not say %r: %r" % (phrase, err), HUE_BAD)
        return False


def sleep_ms(total):
    """Pause in slices, so Stop is noticed."""
    end = time.time() + max(0, int(total)) / 1000.0
    while time.time() < end:
        Misc.Pause(min(SLEEP_SLICE_MS, max(1, int((end - time.time()) * 1000))))


def openAR():
    if has_gump(AR_GUMPID):
        Misc.Pause(250)
        return True
    chat_say(AR_COMMAND)
    ret = Gumps.WaitForGump(AR_GUMPID, AR_GUMP_TIMEOUT_MS)
    Misc.Pause(250)
    return bool(ret) or has_gump(AR_GUMPID)


def ar_buttons(ensure_open=True):
    """Every button on the open runebook page (the 7th number of each)."""
    if ensure_open and not openAR():
        return []
    try:
        layout = Gumps.GetGumpRawLayout(AR_GUMPID) or ""
    except Exception:
        return []
    buttons = []
    for piece in re.split(r"\}\s*\{", layout):
        if "button" in piece.lower():
            data = re.findall(r"\d+", piece)
            if data:
                buttons.append(int(data[-1]))
    return buttons


def ar_page_info():
    """(current, total) from the "Page 1/3" footer. (1, 1) if there is none."""
    for line in reversed(list(gump_lines(AR_GUMPID))):
        found = re.search(r"Page\s+(\d+)\s*/\s*(\d+)", line or "", re.I)
        if found:
            return int(found.group(1)), int(found.group(2))
    return (1, 1)


def parse_ar_page(ensure_open=True):
    """({button: folder}, {button: {"name", "coord"}}) on the CURRENT page.

    Entries are picked out by their "N. Name" text and paired with the
    page's entry buttons IN DISPLAY ORDER - never by text id, which Razor's
    empty-string drop shifts. A rune is followed by a coordinate line; a
    folder is not.
    """
    if ensure_open and not openAR():
        return {}, {}

    lines = gump_lines(AR_GUMPID)
    buttons = ar_buttons(ensure_open=ensure_open)
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

    folders = {}
    runes = {}
    for entry, button in zip(entries, entry_buttons):
        if entry["coord"] is not None or (button + AR_GATE_OFFSET) in buttons:
            runes[button] = {"name": entry["label"], "coord": entry["coord"]}
        else:
            folders[button] = entry["label"]

    if len(entries) != len(entry_buttons):
        log("  AR page: %d entries but %d entry buttons - the pairing may be "
            "off." % (len(entries), len(entry_buttons)), HUE_WARN)
    return folders, runes


def ar_page_step(button):
    if button not in ar_buttons():
        return False
    Gumps.SendAction(AR_GUMPID, button)
    Gumps.WaitForGump(AR_GUMPID, AR_GUMP_TIMEOUT_MS)
    Misc.Pause(250)
    return True


def ar_goto_page(target):
    current, total = ar_page_info()
    target = max(1, min(int(target), total))
    for _ in range(AR_MAX_PAGES * 2):
        if current == target:
            return True
        step = AR_NEXT_PAGE_BUTTON if current < target else AR_PREV_PAGE_BUTTON
        if not ar_page_step(step):
            return False
        current, _total = ar_page_info()
    return current == target


def ar_root():
    if AR_ROOT_BUTTON in ar_buttons():
        Gumps.SendAction(AR_GUMPID, AR_ROOT_BUTTON)
        Gumps.WaitForGump(AR_GUMPID, AR_GUMP_TIMEOUT_MS)
        Misc.Pause(250)
    return True


def ar_enter_folder(name):
    """Step into a folder by name, looking on every page.

    On a miss every folder seen is listed, so a spelling difference is one
    glance away rather than another round trip.
    """
    if not openAR():
        log("The Account Runebook did not open (%r)." % AR_COMMAND, HUE_BAD)
        return False
    if not ar_goto_page(1):
        log("Could not rewind the runebook to page 1.", HUE_WARN)

    wanted = (name or "").strip().lower()
    seen = []
    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        folders, _runes = parse_ar_page()
        for button in sorted(folders):
            label = (folders[button] or "").strip().lower()
            seen.append(folders[button])
            if label == wanted or wanted in label:
                Gumps.SendAction(AR_GUMPID, button)
                Gumps.WaitForGump(AR_GUMPID, AR_GUMP_TIMEOUT_MS)
                Misc.Pause(250)
                return True
        if current >= total or not ar_page_step(AR_NEXT_PAGE_BUTTON):
            break
    log("Folder %r is not in the runebook. Folders seen: %s"
        % (name, ", ".join(seen) or "none"), HUE_BAD)
    return False


def go_to_spot_folder():
    if not openAR():
        return False
    ar_root()
    for folder in RUNEBOOK_FOLDER:
        if folder and not ar_enter_folder(folder):
            return False
    return True


def wanted_rune(name, phrases=None):
    """Is this rune one to visit? RUNE_MUST_MATCH, or everything if empty.

    Truncation-tolerant: the gump cuts long names mid-word, so a phrase also
    matches when the name ENDS with the start of it. See ReagentBuyer.py.
    """
    wanted = RUNE_MUST_MATCH if phrases is None else phrases
    if not wanted:
        return True
    low = " ".join((name or "").split()).lower()
    visible = low.rstrip(" .")
    for want in wanted:
        target = " ".join((want or "").split()).lower()
        if not target:
            continue
        if target in low:
            return True
        longest = min(len(target) - 1, len(visible))
        for cut in range(longest, RUNE_MATCH_MIN_PREFIX - 1, -1):
            if visible.endswith(target[:cut]):
                return True
    return False


def collect_runes():
    """[(page, button, name, coord)] for every rune in the open folder.

    Collected in one sweep BEFORE recalling, because a recall closes the
    book and reopening it lands back at the root.
    """
    out = []
    if not ar_goto_page(1):
        log("Could not rewind to page 1 of the folder.", HUE_WARN)
    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        _folders, runes = parse_ar_page()
        for button in sorted(runes):
            name = runes[button]["name"]
            if wanted_rune(name):
                out.append((current, button, name, runes[button]["coord"]))
        if current >= total or not ar_page_step(AR_NEXT_PAGE_BUTTON):
            break
        moved, _t = ar_page_info()
        if moved <= current:
            log("The runebook did not advance past page %d." % current,
                HUE_WARN)
            break
    return out


def arrived_at(coord):
    """Did the recall land where the rune says? None = cannot tell."""
    if not coord or len(coord) < 2:
        return None
    try:
        gap = max(abs(Player.Position.X - int(coord[0])),
                  abs(Player.Position.Y - int(coord[1])))
    except Exception:
        return None
    return gap <= ARRIVE_TOLERANCE


def same_rune(a, b):
    return " ".join(str(a or "").split()).lower() \
        == " ".join(str(b or "").split()).lower()


def find_rune(name):
    """(page, button, coord) for the rune called `name` in the open folder."""
    if not ar_goto_page(1):
        return None
    for _ in range(AR_MAX_PAGES):
        current, total = ar_page_info()
        _folders, runes = parse_ar_page(ensure_open=False)
        for button in sorted(runes):
            if same_rune(runes[button]["name"], name):
                return current, button, runes[button]["coord"]
        if current >= total or not ar_page_step(AR_NEXT_PAGE_BUTTON):
            return None
    return None


def no_recall_zone_here():
    """The NO_RECALL_ZONES row we are standing in, or None."""
    try:
        x, y = int(Player.Position.X), int(Player.Position.Y)
        facet = int(Player.Map)
    except Exception:
        return None
    for zone in NO_RECALL_ZONES:
        if zone.get("map") is not None and int(zone["map"]) != facet:
            continue
        nx, ny = zone["near"]
        if max(abs(x - nx), abs(y - ny)) <= int(zone.get("radius", 10)):
            return zone
    return None


def walk_to_point(x, y, tolerance, timeout_ms):
    """Walk to a map point. True once within `tolerance` tiles.

    Pathfinder first - this is open ground, not a creature, so walking
    right up to it is the point - then single steps for the last stretch
    or if the pathfinder gives up.
    """
    deadline = time.time() + timeout_ms / 1000.0
    pathfound = False
    stuck = 0
    while time.time() < deadline:
        gap = max(abs(Player.Position.X - x), abs(Player.Position.Y - y))
        if gap <= tolerance:
            return True
        if not pathfound and gap > PATHFIND_MIN_DIST:
            pathfound = True
            pathfind_to(x, y)
            continue
        before = (Player.Position.X, Player.Position.Y)
        move(direction_to(x - Player.Position.X, y - Player.Position.Y))
        Misc.Pause(MOVE_PAUSE)
        if (Player.Position.X, Player.Position.Y) == before:
            stuck += 1
            if stuck >= STUCK_LIMIT * 2:      # a turn costs a move too
                return False
        else:
            stuck = 0
    return False


def leave_no_recall_zone():
    """If we are standing where recall is refused, walk out. True when it is
    safe to recall (we were never in one, or we got out)."""
    zone = no_recall_zone_here()
    if zone is None:
        return True
    wx, wy = zone["walk_to"]
    log("In a no-recall zone (%s) at %d,%d - walking to %d,%d first."
        % (zone.get("label", "?"), Player.Position.X, Player.Position.Y,
           wx, wy), HUE_WARN)
    walk_to_point(wx, wy, ZONE_EXIT_TOLERANCE, ZONE_EXIT_TIMEOUT_MS)
    # OUT is what matters, not the exact tile: terrain may stop us a step
    # short of walk_to but already past the edge.
    if no_recall_zone_here() is None:
        return True
    log("  could not get to %d,%d - still at %d,%d. Trying the recall anyway."
        % (wx, wy, Player.Position.X, Player.Position.Y), HUE_BAD)
    return False


def recall_to(page, button, name, coord):
    """Recall to one rune. True once standing there (or unverifiable).

    THE BUTTON IS CHECKED AGAINST THE NAME BEFORE IT IS PRESSED. Buttons are
    per page, and after an escape the book was last used in the RO folder,
    where the same number is a different rune.

    Walks out of a NO_RECALL_ZONES area first - pressing the rune from
    inside one does nothing but cost the attempt.
    """
    leave_no_recall_zone()
    if not openAR():
        return False
    if not ar_goto_page(page):
        log("Could not get back to page %d for %s." % (page, name), HUE_WARN)
        return False

    _folders, showing = parse_ar_page(ensure_open=False)
    here = showing.get(button)
    if here is None or not same_rune(here["name"], name):
        debug("  the book is not showing %s where it was - finding it again."
              % name, HUE_WARN)
        if not go_to_spot_folder():
            return False
        hit = find_rune(name)
        if hit is None:
            log("  %s is not in the folder any more - skipping it." % name,
                HUE_BAD)
            return False
        page, button, coord = hit
        if not ar_goto_page(page):
            return False

    Gumps.SendAction(AR_GUMPID, button)
    Misc.Pause(RECALL_SETTLE_MS)

    where = arrived_at(coord)
    if where is False:
        log("Recall to %s did not land - still at %d,%d (map %s), wanted "
            "%d,%d." % (name, Player.Position.X, Player.Position.Y,
                        getattr(Player, "Map", "?"), coord[0], coord[1]),
            HUE_WARN)
        if no_recall_zone_here() is None:
            log("  If recall is refused here, add this spot to "
                "NO_RECALL_ZONES with a walk_to point where it works.",
                HUE_WARN)
        return False
    if where is None:
        log("  %s has no coordinates in the book - cannot confirm the recall."
            % name, HUE_WARN)
    return True


def emergency_escape():
    """Get out NOW through ESCAPE_COMMAND. True if a recall landed.

    No searching: the command opens the book already in the escape folder,
    and the page is read WITHOUT reopening it - "[ar" would land back at the
    root and undo what the command did.
    """
    log("ESCAPE at %d%% health: %r" % (player_health_pct(), ESCAPE_COMMAND),
        HUE_BAD)
    clear_cursor()
    # Pressing a rune inside a no-recall zone does nothing, and doing nothing
    # is the worst thing to do here. Walking out is at least moving away.
    leave_no_recall_zone()
    if not chat_say(ESCAPE_COMMAND):
        return False
    Gumps.WaitForGump(AR_GUMPID, 5000)
    Misc.Pause(300)

    options = []
    _folders, runes = parse_ar_page(ensure_open=False)
    for button in sorted(runes):
        options.append((button, runes[button]["name"], runes[button]["coord"]))
    if not options:
        # The text may not have arrived; the buttons are enough to leave on.
        for button in sorted(b for b in ar_buttons(ensure_open=False)
                             if AR_ENTRY_BUTTON_MIN <= b <= AR_ENTRY_BUTTON_MAX
                             and b not in AR_CONTROL_BUTTONS):
            options.append((button, "rune %d" % button, None))
    if not options:
        log("  the escape book did not open - nothing pressed.", HUE_BAD)
        return False

    for button, name, coord in options[:max(1, int(ESCAPE_MAX_TRIES))]:
        log("  recalling to %s." % name, HUE_WARN)
        Gumps.SendAction(AR_GUMPID, button)
        Misc.Pause(ESCAPE_SETTLE_MS)
        if arrived_at(coord) is not False:
            return True
        log("  %s did not land - trying the next one." % name, HUE_WARN)
        if not openAR():
            return False
    log("  could not get out through %s." % ESCAPE_COMMAND, HUE_BAD)
    return False


def escape_and_recover():
    """Leave, then wait to heal before the round carries on."""
    emergency_escape()
    deadline = time.time() + RESUME_WAIT_MS / 1000.0
    said = False
    while time.time() < deadline:
        if Player.IsGhost:
            return
        if player_health_pct() >= RESUME_HITS_PCT:
            log("Health back to %d%% - carrying on." % player_health_pct(),
                HUE_GOOD)
            return
        if not said:
            said = True
            log("Waiting to heal to %d%%." % RESUME_HITS_PCT)
        Misc.Pause(1000)
    log("Still at %d%% after %ds - carrying on anyway."
        % (player_health_pct(), RESUME_WAIT_MS / 1000), HUE_WARN)


# =============================================================================
# STRAY PETS - tamed, but not in a deed
# =============================================================================
#
# Every creature this run has tried to tame, by serial. A pet that is one of
# these and is still following you was tamed and NOT deeded - its success
# message was missed, or the deed would not take - and it is put in its deed
# before anything else happens. Before the spot is left above all: pets do
# not recall with you, so one left behind is a follower slot gone for good.
#
# ONLY these serials. A pet you brought with you is never touched, even if
# you hold a deed for its species.
_our_tames = {}          # serial -> {"species": name, "tries": int}

# Deed attempts per stray before it is reported and left alone.
STRAY_MAX_TRIES = 3


def is_our_pet(serial):
    """Is this creature our pet now? Player.Pets first, then the tooltip."""
    try:
        for pet in list(Player.Pets or []):
            if int(pet.Serial) == int(serial):
                return True
    except Exception:
        pass
    mob = Mobiles.FindBySerial(serial)
    if mob is None:
        return False
    # ServUO adds "(tame)" to a controlled creature's name properties. Only
    # trusted for creatures WE tried to tame - see _our_tames.
    return "(tame)" in mobile_tooltip(mob)


def remember_tame(serial, species_name):
    _our_tames.setdefault(int(serial), {"species": species_name, "tries": 0})


def sweep_strays():
    """Deed every pet we tamed that is still following. How many were deeded."""
    deeded = 0
    for serial, rec in list(_our_tames.items()):
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            # Gone: deeded, died, or out of sight. If it was ours and is out
            # of sight it is lost to this spot anyway.
            del _our_tames[serial]
            continue
        if rec["tries"] >= STRAY_MAX_TRIES:
            continue                # reported already; no tooltip churn
        if not is_our_pet(serial):
            continue
        if rec["species"] not in _active:
            rescan("stray %s" % rec["species"])
            if rec["species"] not in _active:
                continue            # no deed left for it - it stays a pet
        rec["tries"] += 1
        log("%s is following you but is NOT in its deed - adding it now "
            "(try %d/%d)." % (rec["species"], rec["tries"], STRAY_MAX_TRIES),
            HUE_WARN)
        if Player.DistanceTo(mob) > 2:
            approach(serial, 1, 2)
        if add_to_deed(rec["species"], serial):
            del _our_tames[serial]
            deeded += 1
        elif rec["tries"] >= STRAY_MAX_TRIES:
            log("Could not get %s into its deed after %d tries. It is still "
                "following you - deed it by hand." % (rec["species"],
                                                       STRAY_MAX_TRIES),
                HUE_BAD)
    return deeded


# =============================================================================
# ONE SPOT
# =============================================================================

def work_spot(rune_name):
    """Clear and tame at the spot we are standing on. What ended it:

        "quiet"     nothing to tame or kill for SPOT_IDLE_MS - move on
        "timeout"   SPOT_MAX_MS used up
        "fled"      health dropped, escaped - move on
        "nodeeds"   every deed is full
        "dead" / "abort"   stop the run
    """
    _hostile_verdict.clear()
    forget_threats()
    deadline = time.time() + SPOT_MAX_MS / 1000.0
    quiet_since = time.time()
    tamed = 0
    killed = 0

    while time.time() < deadline:
        if Player.IsGhost:
            return "dead"
        if too_hurt():
            if _our_tames:
                log("Leaving with %d tamed pet(s) not yet deeded - they stay "
                    "here." % len(_our_tames), HUE_WARN)
            escape_and_recover()
            return "fled"

        if (time.time() - _last_scan) * 1000.0 >= DEED_RESCAN_MS:
            rescan("periodic")
        if not _active:
            return "nodeeds"

        # KILL FIRST. Taming is a long time standing still, and whatever is
        # hostile here gets that time to walk up on you.
        outcome = clear_hostiles()
        if outcome is not None:
            if outcome == "escape":
                escape_and_recover()
                return "fled"
            if outcome == "dead":
                killed += 1
            quiet_since = time.time()
            continue

        # A pet we tamed that never made it into its deed goes in now.
        if _our_tames and sweep_strays():
            rescan("stray deeded")
            quiet_since = time.time()
            continue

        if Player.Followers >= Player.FollowersMax:
            log("Follower slots are full (%d/%d) - nothing can be tamed. "
                "Stable or release a pet." % (Player.Followers,
                                              Player.FollowersMax), HUE_BAD)
            return "abort"

        species = None
        serial = None
        for mob in find_candidates():
            species = identify(mob)
            if species is not None:
                serial = mob.Serial
                break
            # Not something we hold a deed for, or not identifiable. Ignored -
            # UNLESS it is on the kill list: the kill scan respects the
            # ignore list too, so ignoring a hostile still out of KILL_RANGE
            # here would mean it is never fought when it walks up.
            if hostile_verdict(mob) is None:
                Misc.IgnoreObject(mob.Serial)

        if species is None:
            if (time.time() - quiet_since) * 1000.0 >= SPOT_IDLE_MS:
                log("%s: quiet - %d tamed, %d killed here."
                    % (rune_name, tamed, killed), HUE_INFO)
                # Last look before recalling: pets do not come with you.
                sweep_strays()
                return "quiet"
            Misc.Pause(IDLE_PAUSE)
            continue

        label = species["name"]
        log("Found %s at %d tiles." % (label, Player.DistanceTo(mob)))
        remember_tame(serial, label)
        result = tame(serial, label)
        quiet_since = time.time()

        # Whatever tame() concluded, if the creature is our pet now the tame
        # went through - its message was missed somewhere - and it is
        # handled as the success it is. Anything else is dropped from the
        # stray list, so sweep_strays never re-reads it.
        if result in ("skip", "unreachable", "exhausted", "lost"):
            if Mobiles.FindBySerial(serial) is not None and is_our_pet(serial):
                log("%s turned out to be tamed after all." % label, HUE_GOOD)
                result = "success"
            else:
                _our_tames.pop(int(serial), None)

        if result == "success":
            if add_to_deed(label, serial):
                _our_tames.pop(int(serial), None)
            # If it did not take, it stays in _our_tames and sweep_strays
            # tries again before the spot is left.
            tamed += 1
            Misc.IgnoreObject(serial)
            rescan("after tame")
        elif result == "flee":
            escape_and_recover()
            return "fled"
        elif result == "abort":
            return "abort"
        elif result in ("skip", "unreachable", "exhausted"):
            log("Giving up on %s (%s)." % (label, result), HUE_WARN)
            Misc.IgnoreObject(serial)
        Misc.Pause(500)

    log("%s: %d minute(s) up - %d tamed, %d killed here."
        % (rune_name, SPOT_MAX_MS / 60000, tamed, killed), HUE_INFO)
    sweep_strays()
    return "timeout"


# =============================================================================
# MAIN
# =============================================================================

def preflight():
    log("FillTameDeeds v%s" % SCRIPT_VERSION, HUE_GOOD)

    if not build_species():
        log("No species available - check ONLY_ANIMALS / NEVER_ANIMALS.", HUE_BAD)
        return False
    hostile = build_hostiles()
    log("Kill list: %d hostile names, %d hostile bodies. %s under %d hits, "
        "%s at or over it%s."
        % (hostile, len(HOSTILE_BODIES), SPELL_SMALL, SPELL_BIG_HITS,
           SPELL_BIG, " or unknown" if SPELL_UNKNOWN_IS_BIG else ""),
        HUE_GOOD if KILL_ENABLED else HUE_WARN)
    if not KILL_ENABLED:
        log("  KILL_ENABLED is False - nothing will be attacked except in "
            "self-defence.", HUE_WARN)

    if Player.Backpack is None:
        log("No backpack found.", HUE_BAD)
        return False

    magery = Player.GetSkillValue("Magery")
    if magery < 60:
        log("  Magery is %.1f - Energy Bolt will fizzle a lot below about 70."
            % magery, HUE_WARN)

    if PEACE_ENABLED and PEACE_WHEN != "never":
        instrument = find_instrument()
        if instrument is None:
            log("Peacemaking is ON but there is NO INSTRUMENT in your pack. "
                "The skill fails silently without one - carry a lute, drums "
                "or a harp, or set PEACE_ENABLED = False.", HUE_BAD)
        else:
            log("Peacemaking: on (%s), playing 0x%04X"
                % (PEACE_WHEN, int(instrument.ItemID)), HUE_GOOD)
    else:
        log("Peacemaking: off")

    if ESCAPE_ENABLED:
        log("Escape below %d%% health through %r."
            % (ESCAPE_HITS_PCT, ESCAPE_COMMAND))

    for zone in NO_RECALL_ZONES:
        nx, ny = zone["near"]
        wx, wy = zone["walk_to"]
        if max(abs(wx - nx), abs(wy - ny)) <= int(zone.get("radius", 10)):
            log("NO_RECALL_ZONES %r: walk_to %d,%d is INSIDE its own radius "
                "%d - the walk-out would never count as out. Lower the "
                "radius or move walk_to." % (zone.get("label", "?"), wx, wy,
                                             zone.get("radius", 10)), HUE_BAD)
    if NO_RECALL_ZONES:
        log("No-recall zones: %s" % ", ".join(z.get("label", "?")
                                              for z in NO_RECALL_ZONES))

    if Player.WarMode:
        log("Dropping war mode.", HUE_WARN)
        Player.SetWarMode(False)

    log("Reading taming order deeds from your pack...", HUE_INFO)
    if rescan("startup") == 0:
        log("Found no unfilled taming order deeds - nothing to do. If you are "
            "holding deeds, DEED_NAME_HINTS is probably wrong; run "
            "Scripts/diag_deeds.py.", HUE_BAD)
        return False
    log("Taming: %s" % ", ".join(sorted(_active)), HUE_GOOD)

    if not go_to_spot_folder():
        return False
    runes = collect_runes()
    if not runes:
        log("No runes in %s." % " / ".join(RUNEBOOK_FOLDER), HUE_BAD)
        return False
    log("%d spot(s) in %s: %s"
        % (len(runes), " / ".join(RUNEBOOK_FOLDER),
           ", ".join(r[2] for r in runes[:6])
           + (" ..." if len(runes) > 6 else "")), HUE_GOOD)
    return True


def one_lap(lap):
    """Visit every spot once. "continue", or why the run should stop."""
    log("--- lap %d ---" % lap, HUE_GOOD)
    # A fresh look at every spot. What was unreachable or out-fought last lap
    # may not be this time. This resets Razor's whole ignore list.
    if lap > 1:
        Misc.ClearIgnore()
    if not go_to_spot_folder():
        return "nobook"
    runes = collect_runes()
    if not runes:
        log("No runes in %s this lap." % " / ".join(RUNEBOOK_FOLDER), HUE_BAD)
        return "nobook"

    for page, button, name, coord in runes:
        if Player.IsGhost:
            return "dead"
        log("recalling to %s" % name)
        if not recall_to(page, button, name, coord):
            continue
        result = work_spot(name)
        if result in ("dead", "abort", "nodeeds"):
            return result
    return "continue"


def main():
    if not preflight():
        return
    try:
        lap = 0
        while True:
            lap += 1
            if MAX_LAPS and lap > MAX_LAPS:
                log("%d lap(s) done, which is MAX_LAPS." % (lap - 1), HUE_GOOD)
                break
            result = one_lap(lap)
            if result == "nodeeds":
                log("Every deed is full - done.", HUE_GOOD)
                break
            if result == "dead":
                log("You are dead. Stopping.", HUE_BAD)
                break
            if result in ("abort", "nobook"):
                log("Stopping.", HUE_BAD)
                break
            log("Lap %d done. Waiting %ds for the spawn."
                % (lap, LAP_PAUSE_MS / 1000))
            sleep_ms(LAP_PAUSE_MS)
    finally:
        # However this ends - the Stop button, an exception, the player dying -
        # do not walk away holding a target cursor.
        try:
            Target.Cancel()
            Target.ClearQueue()
            Target.ClearLastandQueue()
        except Exception:
            pass
        log("Stopped. Target cursor released.", HUE_INFO)


main()
