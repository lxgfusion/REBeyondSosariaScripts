"""
Manual tamer's deed filler.
===========================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

YOU TAME. IT FILLS. That is the whole script.

It does not hunt, walk, chase, cast, peacemake, defend, attack, loot or butcher,
and it never targets a wild animal. It stands still and reads your journal. When
YOU tame something, it works out which species it was, finds the taming order
deed in your pack for that species, and puts the animal in it.

A fork of TameAndFill.py with everything that moves your character or targets a
creature taken out. What is left is the deed half: the pack scan, the species
catalogue, and the double-click-and-target sequence that fills a deed.

How it decides what to fill
---------------------------
1. A taming-success line arrives in your journal ("It seems to accept you as
   master."). That banks one CREDIT.
2. The animal is found - from the client's own pet list, or, when that has not
   caught up yet, by reading the tooltips of controlled creatures within
   TAME_SCAN_RANGE.
3. Its NAME is matched against the catalogue of tameable species IN FULL, not
   as a substring - "a lesser hiryu" is not a hiryu, and since the two share
   the body value 0xF3 the name is the only thing that can tell them apart -
   and its body value has to agree with the name.
4. That species' deed is read out of your pack, double-clicked, and the animal
   targeted. The credit is spent.

NOTHING IS FILLED WITHOUT A CREDIT. That is what stops this script eating a pet
you have had for a year: the taming line for that animal was spoken and spent
long ago. See REQUIRE_TAME_CREDIT.

What it says, and how to ask it something
-----------------------------------------
It is QUIET. At startup you get three lines - which copy is loaded, how many
pets of yours are already out of its reach, and the deeds you are holding -
and after that one line per animal it deeds, plus anything you have to act on.
Nothing it prints is load-bearing, so the quiet costs nothing: see TALK.

SAY "deeds" IN GAME and it answers with every deed in your pack and how far
along each one is. It also says that by itself within STATUS_EVERY_MS of the
answer changing, and never repeats an answer that has not changed.

TALK = 1 puts back what it is about to do and why it left an animal alone;
TALK = 2 adds every journal line a deed produced, which is what it used to do
and is the setting to put back when something has gone wrong.

What it will never touch
------------------------
- Anything that was already yours, or already tame and standing near you, when
  the script started. It snapshots all of that before reading a journal line.
- Your mount.
- Anything named in KEEP_NAME_WORDS, or listed in NEVER_FILL_SERIALS.
- Anything whose name does not match a species you hold a deed for IN FULL.
  A name that merely contains one is named and refused - "'lesser hiryu' is
  not a 'hiryu'" - with a paste-ready EXTRA_ANIMALS row, body included, if
  your shard really does deed it.
- A DEED whose "Creature Type:" names a species the catalogue does not know is
  skipped the same way, rather than filed under the nearest substring.
- Anything whose name and body value disagree.

SETUP
-----
Nothing is required. There are no serials to fill in and no prompts.

Worth setting before a long session:

  KEEP_NAME_WORDS   Rename the pets you ride and fight with - "Keeper", say -
                    and put that word here. It is the only guard that survives a
                    restart, so it is the one to use for animals you would be
                    upset to lose.
  MAX_FILL_DIST     How close the animal has to be before it is deeded. 3 tiles.
  SKIP_FULL_DEEDS   Leave True. A full deed cannot take another animal.

USE
---
1. Put your taming order deeds in your backpack.
2. Run the script. It should say:

     [ManualTamer] ManualTameAndFill 2026-11-09.1 - you tame, it fills.
     [ManualTamer] 4 animal(s) already yours are out of reach of this script.
     [ManualTamer] Your mount (0x40012AB3) will never be deeded.
     [ManualTamer] Filling (startup): hind, llama, timber wolf

3. Tame something. By hand, however you like - that half is yours.
4. It says what it heard and what it did:

     [ManualTamer] Tame heard: It seems to accept you as master.
     [ManualTamer] Filling the hind deed [23/60].
     [ManualTamer] hind is in its taming order [24/60]. 1 filled this run.

5. Add and remove deeds while it runs. The pack is re-read after every fill and
   every DEED_RESCAN_MS, so a deed that fills up drops out of the list and a
   newly added one joins it.

If it hears the tame and then does nothing, it says why, once per animal and per
reason: no deed for that species, too far away, the name will not load, or a
KEEP word matched.

Notes
-----
- The deed step runs Journal.Clear(), so your journal is wiped on every fill.
  New lines are read immediately before each one, so a tame that lands mid-fill
  is still counted.
- A creature's name is read before anything is targeted, and one whose name will
  not load is left alone. A missed fill costs one animal; the alternative is
  trusting a body value, which is how the parent script once came to target
  zombies.
- An animal the shard refuses FILL_ATTEMPTS times over is given up on rather
  than offered again every lap. A deed is refused for reasons that do not
  change by asking again.
- Nothing is put on Razor's ignore list. This script does not search for
  creatures, so it has nothing to ignore.
"""

import re
import time


# Printed as the first line at startup. Bump it with every change that goes out,
# so the journal says which copy Razor actually loaded - Razor caches the loaded
# script even after the file on disk changes, and two debugging rounds have
# already been spent on a bug that was fixed on disk but not in the folder Razor
# reads. If this line does not say what you expect, hit Reload.
SCRIPT_VERSION = "2026-11-10.1"
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
# CONFIG - WHAT TO FILL
# =============================================================================

# Restrict to these species even if you hold other deeds. Empty = every deed
# found is honoured. Names must match the catalogue below.
ONLY_ANIMALS = []

# Never fill deeds for these, even holding one.
NEVER_ANIMALS = []

# Species your shard added that are not in the catalogue. This is the seam for
# shard data: ANIMAL_CATALOGUE below is extracted from ServUO source and stays
# that way, and anything the shard invented goes here.
# Format: ("name", [body, ...], min_tame_skill)
EXTRA_ANIMALS = [
    # BeyondSosaria added a taming order for these, 2026-11-09. The body is
    # read off the Enhanced Mobile Inspector on a live one (MobileID 0x00F3) -
    # THE SAME BODY AS A HIRYU, so the body guard cannot tell the two apart and
    # the name is the only thing that can. See species_from_name().
    #
    # The 0.0 is NOT shard data: the minimum taming skill has not been read
    # from anywhere. It costs nothing here because this fork sets
    # SKIP_ABOVE_SKILL = False, so the figure is never consulted - but do not
    # copy this row into TameAndFill.py, where it is.
    ("lesser hiryu",          [0xF3],                    0.0),
]

# FALSE HERE, AND True IN TameAndFill.py. That script skips species it has not
# the skill to tame, because it is the one doing the taming and would otherwise
# spend the round walking at something it cannot hold. You are doing the taming.
# If an animal is standing in front of you already tamed, the question of
# whether a skill table thinks you could have tamed it is settled - refusing to
# fill its deed on the strength of that table would just lose you the animal.
SKIP_ABOVE_SKILL = False
# =============================================================================
# CONFIG - SAFETY
# =============================================================================
# Body values are only a cheap pre-filter. Before an animal goes into a deed,
# its NAME must match the species that deed is for.
#
# This exists because body values are not trustworthy on their own: two species
# share one, shards reuse them, and a wrong catalogue entry invents one. A stray
# 0x3 in the sheep entry - which is the ZOMBIE body - is how the parent script
# came to target zombies while hunting. The catalogue is inherited here, so the
# guard is too.
#
# Leave this True. Setting it False falls back to trusting the body when a name
# will not load, which is what caused that bug.
REQUIRE_NAME_MATCH = True

# Never put anything whose name contains one of these into a deed, whatever its
# body says. A backstop, not the main guard.
NEVER_TAME_WORDS = [
    "zombie", "skeleton", "skeletal", "lich", "wraith", "spectre", "specter",
    "ghoul", "mummy", "bone ", "corpser", "revenant", "shade",
    "golem", "elemental", "daemon", "demon", "gargoyle warrior",
    "ogre", "troll", "ettin", "orc", "ratman", "lizardman", "harpy",
    "titan", "cyclops", "juka", "meer", "solen", "terathan", "ophidian",
]

# Pets you want to KEEP. Anything whose name contains one of these is never put
# in a deed, however well it matches. Rename a keeper and it is safe for good:
# this is the only guard here that survives a restart, so it is the one to use
# for the animals you actually ride and fight with.
KEEP_NAME_WORDS = []

# The same thing by serial, for a pet you would rather not rename.
NEVER_FILL_SERIALS = []

# Your mount is never deeded. There is no good reason to turn this on; it is a
# named constant so that the rule is visible instead of buried in the code.
FILL_MOUNT = False

# THE RULE THAT MATTERS, and the reason this script cannot eat the dragon you
# have had for a year.
#
# Nothing is filled just because the client says it is your pet. A fill needs a
# CREDIT: a taming-success line in your journal that has not been spent yet. You
# tame something, the shard says so, that line is worth one fill, and the fill
# spends it.
#
# So an animal that was already yours cannot be deeded - its taming line was
# spoken and spent long ago. That includes the pet which was out of range at
# startup and wanders back to you an hour later, which is exactly the case a
# plain "is it new in Player.Pets" test gets wrong, and the way to get it wrong
# costs you the animal.
#
# Leave this True. False fills on client pet state alone and will eventually
# deed something you meant to keep.
REQUIRE_TAME_CREDIT = True

# How long a credit is good for (ms). Long enough to outlast an animal that
# bolted mid-tame and has to be chased down, and the deed's own retries; short
# enough that it is not still sitting unspent when an old pet strolls into view.
TAME_CREDIT_MS = 45000

# An animal you have just tamed is standing next to you. Past this many tiles
# the fill waits instead of reaching across the screen for something that may
# not be the animal you tamed at all.
MAX_FILL_DIST = 3

# Words that may sit in FRONT of a creature's name without changing which
# species it is. Everything after them is part of the species, which is what
# keeps "a lesser hiryu" from reading as a hiryu - see species_from_name().
NAME_NOISE_WORDS = ["a", "an", "the"]

# How far out to look for the animal you just tamed when the client's own pet
# list has not caught up with it. Tooltips are only read inside this range, and
# only while a credit is waiting to be spent, so this costs nothing at all when
# you are not taming.
TAME_SCAN_RANGE = 6

# =============================================================================
# CONFIG - BEHAVIOUR
# =============================================================================

DEED_TARGET_TIMEOUT = 4000     # ms to wait for the deed's target cursor
DEED_SETTLE_MS = 400           # ms after the cursor opens before answering it
DEED_RESULT_MS = 1500          # ms to wait for the deed to react
DEED_RETRIES = 3               # cursor attempts within ONE fill
FILL_ATTEMPTS = 2              # fills to try on one animal before giving up on
                               # it altogether. This is what stops an animal
                               # the shard will never accept being offered
                               # again every lap until its credit expires.
PROPS_TIMEOUT = 1500           # ms to wait for a tooltip

POLL_MS = 250            # journal poll interval. All the idle loop does is read
                         # new journal lines, so this can afford to be tight.
IDLE_PAUSE = 1000        # pause when there is no deed in the pack to fill

# HOW MUCH IT SAYS (2026-11-10), per the user: "we have alot of journal
# information coming up ... I would like it to where it does not spam the left
# of my screen all the time, and give me an update on what animals i have deeds
# for to tame, but still operate the same way."
#
# NONE OF IT IS LOAD-BEARING, which is what makes this safe. Every line this
# script prints goes through log(), and log() is one Misc.SendMessage and
# nothing else - no decision anywhere reads back something that was printed,
# and the journal work this script does (poll_tames, dump_journal) is reading,
# never printing. So the quietest setting changes what you see and nothing
# whatsoever about what it does.
#
#   0 QUIET  - the deed report, one line per animal deeded, and the problems
#              you have to act on. The default.
#   1 NORMAL - and what it is about to do, and why it left an animal alone.
#   2 LOUD   - and every journal line a deed produced. What it used to do, and
#              the setting to put back when something has gone wrong.
TALK = 0

# DERIVED, NOT SET. Every debug() and dump_journal() call carried over from
# TameAndFill.py reads DEBUG, so deriving it from TALK means the one dial
# drives those too and there is no second switch to forget.
DEBUG = TALK >= 2

# How often to check whether the deed report has changed, in ms. A report
# identical to the last one is never repeated, so this is not "a line every
# five minutes" - it is "tell me within five minutes of a deed appearing,
# filling up, or being taken out of the pack". 0 turns the check off; asking by
# name below always answers regardless.
STATUS_EVERY_MS = 300000

# SAY ANY OF THESE IN GAME AND IT REPORTS what deeds you are holding and how
# far along each one is. This is the other half of going quiet: a script that
# says little has to answer when it is asked.
#
# NOT RESTRICTED TO YOUR OWN SPEECH, deliberately. A JournalEntry carries a
# Serial, so this could require entry.Serial == Player.Serial - but what that
# field holds for a spoken line is not described in
# docs/api-reference-generated.md and has not been read off a live dump, and
# guessing it wrong would make the command a silent dud that looks like a
# broken script. Matching the text alone cannot fail to work. The cost is that
# a passer-by saying "deeds" also gets you one status line.
STATUS_COMMANDS = ["deeds"]

# Optional shard-specific confirmations for the deed step. Leave empty and
# success is judged by the animal disappearing.
MSG_DEED_SUCCESS = []
MSG_DEED_REJECT = []

HUE_INFO = 0x03B2        # pale grey
HUE_GOOD = 0x0044        # green
HUE_WARN = 0x0035        # orange
HUE_BAD = 0x0021         # red


# =============================================================================
# SERVER MESSAGES  (ServUO/RunUO Scripts/Skills/AnimalTaming.cs)
# =============================================================================
#
# THE ONLY MESSAGES THIS SCRIPT CARES ABOUT. TameAndFill.py reads eight groups
# of them, because it is running the taming attempt and has to decide whether to
# retry, step closer, or give up. You are doing all of that. The one thing this
# script has to know is that a tame LANDED.

MSG_TAMED = [
    "It seems to accept you as master.",              # 502799
    # ALSO A SUCCESS. ServUO AnimalTaming.cs sends this INSTEAD of 502799 when
    # you have owned the creature before - and then makes it your pet exactly
    # the same. It used to sit in the parent's skip list, so a re-tamed animal
    # was written off and left following you with no deed. Confirmed in source
    # 2026-10-25.
    "That wasn't even challenging.",                  # 502797
]

# ServUO puts this on the tooltip of every controlled creature. It is how the
# animal you just tamed is found when Player.Pets has not caught up with it.
TAME_TOOLTIP_MARK = "(tame)"
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
# RUNTIME STATE
# =============================================================================

_species = {}            # name -> {"name", "bodies", "min_tame"}
_patterns = []           # [(species, compiled regex)] longest name first
_active = {}             # name -> {"species", "deed": serial}
_deed_graphics = list(DEED_GRAPHICS)
_scanned_once = False
_last_scan = 0.0

# Lists rather than bare floats so the helpers below can write to them without a
# global statement in every one.
_cursor = [0.0]          # newest journal stamp read, on RAZOR's clock
_filled = [0]            # animals deeded this run, for the stop line

_credits = []            # one time.time() per unspent taming-success line
_known = set()           # serials already ruled on; never looked at again
_tries = {}              # serial -> fills attempted, to stop retrying forever
_exact = {}              # species name -> anchored pattern, built on demand
_unknown_said = set()    # deed species already complained about, said once
_said = set()            # (serial, text) already explained, so it is said once
_reported = [""]         # the last deed report, so an unchanged one is not repeated
_status_at = [0.0]       # when the periodic report last ran, on time.time()
# =============================================================================
# HELPERS
# =============================================================================
def log(text, hue=HUE_INFO):
    Misc.SendMessage("[ManualTamer] " + text, hue, False)


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

def chat(text, hue=HUE_INFO):
    """Say it only at TALK 1 or more. The fork's own; see TALK for the levels.

    THIS IS THE WHOLE OF HOW IT WENT QUIET. Every line that narrated what the
    script was about to do, or why it left an animal alone, goes through here
    instead of log(). Nothing load-bearing passes through either of them -
    both end at one Misc.SendMessage - so turning this off changes what you
    see and nothing else.

    BESIDE debug() RATHER THAN INSIDE IT. debug() is the carried-over switch
    for the journal dumps and the pack scan, which are for when something has
    gone wrong; these lines are ordinary narration, and wanting one is not
    wanting the other.
    """
    if TALK >= 1:
        log(text, hue)

# =============================================================================
# THE JOURNAL - HEARING A TAME LAND
# =============================================================================

def newest_journal_stamp():
    """The newest stamp in RazorEnhanced's journal, or 0.0 when it is empty.

    BY RAZOR'S CLOCK, NEVER BY COUNTING (CLAUDE.md). RazorEnhanced keeps the
    last 100 journal lines, OLDEST first, so a line count taken before an event
    stops growing once the buffer is full and every new line lands outside a
    slice taken from it. Stamps keep climbing, and a Journal.Clear() between two
    reads does not reset them.
    """
    try:
        stamps = [getattr(e, "Timestamp", None)
                  for e in (Journal.GetJournalEntry(None) or [])]
        stamps = [s for s in stamps if s is not None]
        return max(stamps) if stamps else 0.0
    except Exception:
        return 0.0


def poll_tames():
    """Read the new journal lines and bank a credit for each tame that landed.

    CALL THIS EVERY LAP, AND IMMEDIATELY BEFORE EVERY Journal.Clear(). The
    journal holds 100 lines and a Clear throws the lot away: a success line not
    yet read when one fires is not read late, it is gone, and the animal it
    belonged to is left standing there undeeded.

    A timestamp cursor, not Search + Clear, because this is a passive trigger -
    one tame fires once, lines from before startup are ignored, and the player's
    own journal is left alone (CLAUDE.md).
    """
    newest = _cursor[0]
    try:
        entries = list(Journal.GetJournalEntry(_cursor[0]) or [])
    except Exception:
        return
    for entry in entries:
        stamp = float(getattr(entry, "Timestamp", 0.0) or 0.0)
        if stamp <= _cursor[0]:
            continue
        if stamp > newest:
            newest = stamp
        text = str(getattr(entry, "Text", "") or "").lower()
        # ASKED FOR A REPORT, and handled HERE on purpose - this is the one
        # place the journal is drained, and deed_attempt() calls poll_tames()
        # immediately before every Journal.Clear(). A listener anywhere else
        # would lose any word said in the window before a clear, and a word
        # lost that way is not read late, it is gone (CLAUDE.md).
        if STATUS_COMMANDS and text.strip(" .,!?") in STATUS_COMMANDS:
            deed_report("you asked", force=True)
            _status_at[0] = time.time()
            continue
        for message in MSG_TAMED:
            if message.lower() in text:
                # time.time() HERE, not the journal stamp. Razor stamps in local
                # time and that stamp is only good for ordering lines against
                # each other; the AGE of a credit is measured on our clock,
                # which is the one TAME_CREDIT_MS is written in. The line is
                # read within POLL_MS of arriving, so the two agree closely
                # enough for a 45-second window.
                _credits.append(time.time())
                # chat(), NOT log(). The fill line that follows a second later
                # is the one worth seeing, and it says strictly more.
                chat("Tame heard: %s" % (getattr(entry, "Text", "") or ""),
                     HUE_GOOD)
                break
    _cursor[0] = newest


def prune_credits():
    """Forget taming lines too old to belong to anything standing here."""
    cutoff = time.time() - (TAME_CREDIT_MS / 1000.0)
    while _credits and _credits[0] < cutoff:
        _credits.pop(0)
        # log(), NOT debug() (2026-11-10). THE ONE THING A QUIET SCRIPT STILL
        # HAS TO SAY: you tamed something and nothing was deeded. The
        # per-animal reasons go through chat() now, so without this line a
        # tame with no matching deed in the pack passed in complete silence -
        # found by rendering the transcript, where a lesser hiryu tamed with
        # no lesser hiryu deed produced nothing at all on screen.
        #
        # HERE RATHER THAN AT THE REFUSAL, because this fires once per wasted
        # tame while a refusal fires once per animal per reason and multiplies
        # with the pets standing around you. The cost is that it arrives
        # TAME_CREDIT_MS after the tame; TALK = 1 says why at once.
        #
        # THE ADVICE IS ONLY FOR SOMEBODY WHO HAS NOT TAKEN IT. At TALK 1 the
        # reason was already printed at the time, so telling them to turn
        # TALK up reads as the script not knowing what it is doing.
        log("A tame went undeeded -- nothing in reach matched a deed in your "
            "pack. Say '%s' to see what you are holding.%s"
            % ((STATUS_COMMANDS or ["deeds"])[0],
               "" if TALK >= 1 else " TALK = 1 says why at the time."),
            HUE_WARN)


def have_credit():
    prune_credits()
    if not REQUIRE_TAME_CREDIT:
        return True
    return bool(_credits)


def spend_credit():
    """Spend one credit. Called only after a fill has actually gone through.

    Deliberately NOT spent up front: a deed attempt that fails leaves the credit
    in place so the next lap can try again, which is what you want when the
    animal wandered a tile too far or the cursor was busy.
    """
    if _credits:
        _credits.pop(0)
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
    """(species, stated) for a deed. The type field wins over free text.

    THE FIELD IS MATCHED IN FULL. It arrives clean - "creature type: lesser
    hiryu" yields exactly "lesser hiryu" - so there is nothing to search
    inside it, and searching inside it is what filed a LESSER HIRYU deed as a
    hiryu deed on 2026-11-09. `stated` carries the value back even when
    nothing matched, so the caller can name it and hand over the row that
    would fix it.

    The free-text fallback stays loose. A deed with no type field has its
    species buried in other words, and a substring is the only thing to go on.
    """
    for label in DEED_SPECIES_FIELDS:
        value = field_value(text, label.strip().lower())
        if value:
            species, cleaned, _loose = species_from_name(value)
            if species is not None:
                return species, cleaned
            return None, cleaned
    return match_species(text), ""


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
        species, stated = species_from_deed(text)
        if species is None:
            if stated and stated not in _unknown_said:
                # LOUD, NOT debug(). This deed is real and it is being
                # skipped, and the alternative - filing it under the nearest
                # substring - is what put a lesser hiryu deed in the hiryu
                # slot and had the script offering animals to the wrong one.
                #
                # ONCE PER SPECIES, THOUGH. This runs at startup, after every
                # fill and every DEED_RESCAN_MS, and a warning that repeats
                # forever gets scrolled past, which is the same as not saying
                # it at all.
                _unknown_said.add(stated)
                log("A deed says 'Creature Type: %s', which is not a species "
                    "in the catalogue -- SKIPPING IT, so nothing is put in "
                    "the wrong deed." % stated, HUE_BAD)
                log("   If your shard really does deed one, add this to "
                    "EXTRA_ANIMALS (the body is printed when you tame one):",
                    HUE_WARN)
                log("   %s" % unknown_species_line(stated), HUE_WARN)
            elif not stated:
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
    # NO BODY INDEX. The parent builds one here to drive its mobile filter;
    # this script never searches for a creature, so there is nothing to index.
    _active.update(found)

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
    # ONE STATUS LINE, and only when the SET of species changed. A deed
    # merely moving on (24/60 -> 25/60) is reported by the fill line that
    # moved it, so reporting it here as well would put two lines on screen for
    # every animal - which is the spam this round was asked to remove.
    #
    # FORCED, because the set changing is news whether or not the rendered
    # text happens to differ: a deed swapped for another at the same progress
    # reads the same and is not the same.
    if after != before:
        deed_report(reason, force=True)
    return count
# =============================================================================
# READING A CREATURE
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

# =============================================================================
# THE ANIMAL YOU JUST TAMED
# =============================================================================

def client_pets():
    """Serials the client says are ours, from Player.Pets."""
    out = []
    try:
        for pet in list(Player.Pets or []):
            out.append(int(pet.Serial))
    except Exception:
        pass
    return out


def mount_serial():
    """Your mount's serial, or 0.

    Player.Mount is not used anywhere else in this repo, so it is unverified on
    this build and read defensively: no mount, a build without the property, and
    a property that returns something with no Serial all come out as 0. The
    caller then loses one belt-and-braces guard rather than falling over - the
    startup snapshot has the mount anyway, since it is already yours.
    """
    try:
        mount = Player.Mount
    except Exception:
        return 0
    if mount is None:
        return 0
    try:
        return int(getattr(mount, "Serial", 0) or 0)
    except Exception:
        return 0


def nearby_tame_creatures():
    """Serials of controlled creatures within TAME_SCAN_RANGE, ours or not.

    THE FALLBACK, AND ONLY WITH A CREDIT IN HAND. Player.Pets is the right
    answer when it has the animal, but it is the client's own bookkeeping and
    there is no guarantee it has caught up a second after the tame landed. The
    tooltip is the server talking: ServUO marks every controlled creature.

    It cannot tell YOUR pet from another tamer's - both read "(tame)" - which is
    why the range is short, why the startup snapshot takes in everything already
    tame and standing around, and why a credit has to be waiting before this is
    called at all. The server refuses a deed aimed at someone else's pet in any
    case; the point is not to try.
    """
    out = []
    try:
        f = Mobiles.Filter()
        f.Enabled = True
        f.RangeMax = TAME_SCAN_RANGE
        found = Mobiles.ApplyFilter(f)
    except Exception:
        return out
    for mob in (found or []):
        try:
            serial = int(mob.Serial)
        except Exception:
            continue
        if serial == int(Player.Serial) or serial in _known:
            continue
        try:
            Mobiles.WaitForProps(mob, PROPS_TIMEOUT)
            lines = list(Mobiles.GetPropStringList(mob) or [])
        except Exception:
            continue
        if any(TAME_TOOLTIP_MARK in str(line or "").lower() for line in lines):
            out.append(serial)
    return out


def snapshot():
    """Everything already ours, or already tame and standing here, at startup.

    THESE ARE YOUR KEEPERS. Nothing in this set is ever looked at again, so the
    animal you are riding and the three following you are out of this script's
    reach before it has read a single journal line. The credit rule would hold
    them back on its own; this is the belt to its braces, and it is also what
    stops the tooltip scan re-reading the same animals every lap.
    """
    for serial in client_pets():
        _known.add(serial)
    mount = mount_serial()
    if mount:
        _known.add(mount)
    # After the two above, so already-known serials are skipped by the scan.
    for serial in nearby_tame_creatures():
        _known.add(serial)
    return len(_known)


def exact_name_pattern(name):
    """An anchored pattern for one species name, built once and kept.

    Lazily, and cached on the name, deliberately: building these inside
    build_species() would add one more thing that has to happen before a name
    can be read, and an ordering that can be got wrong silently is worse than
    a dictionary lookup per creature.
    """
    found = _exact.get(name)
    if found is None:
        parts = [p for p in re.split(r"[^a-z0-9]+", name) if p]
        found = re.compile(r"\A" + r"[^a-z0-9]*".join(
            re.escape(p) for p in parts) + r"\Z")
        _exact[name] = found
    return found


def species_from_name(raw):
    """(species, cleaned, loose) for a name that IS a species and nothing else.

    THE NAME HAS TO MATCH IN FULL. That is the difference between this and the
    free-text match_species(), and it is used for the two places where the name
    arrives clean: a creature's own name, and a deed's "Creature Type:" field.

    "a lesser hiryu" CONTAINS "hiryu", and on 2026-11-09 that is exactly what
    went wrong in game. The animal read as a hiryu and was offered to the hiryu
    deed over and over, which the shard refused every time; and the lesser
    hiryu DEED, whose field says "Creature Type: Lesser Hiryu", was itself
    registered as a hiryu deed by the same substring match.

    Sorting the patterns longest-first does not save it. That only picks the
    best of the names the catalogue HAS, and the problem is a species it has
    not got. Nor can the body: a live lesser hiryu reads MobileID 0x00F3, the
    same as a hiryu, so the name is the only discriminator there is.

    `loose` is what the substring match WOULD have answered, so the caller can
    name the species it was about to be mistaken for instead of just refusing
    and leaving you to guess why.
    """
    words = [w for w in re.split(r"[^a-z0-9]+", (raw or "").lower()) if w]
    while words and words[0] in NAME_NOISE_WORDS:
        words.pop(0)
    cleaned = " ".join(words)
    if not cleaned:
        return None, "", None
    for species, _loose in _patterns:
        if exact_name_pattern(species["name"]).match(cleaned):
            return species, cleaned, species
    return None, cleaned, match_species(cleaned)


def unknown_species_line(cleaned, body=None):
    """A paste-ready EXTRA_ANIMALS row for a species the catalogue lacks.

    Printed rather than guessed at. CLAUDE.md is explicit that shard data comes
    from source or a live dump and never from memory, and the live creature in
    front of you is a dump: its body is exact. The skill is left at 0.0 and
    said to be unread, which costs nothing here because this fork sets
    SKIP_ABOVE_SKILL = False.
    """
    where = "0x%X" % body if body is not None else "body"
    return ('    ("%s", [%s], 0.0),    # skill not read from the shard'
            % (cleaned, where))


def pet_species(mob):
    """(species, why, retry) for one animal. species None means leave it alone.

    `retry` says whether the refusal could change: "no deed for that species"
    could, once you put the deed in your pack, so it is asked again next lap.
    "Its name is on NEVER_TAME_WORDS" could not, so the animal is dropped.

    THE CREATURE'S NAME DECIDES, not its body. Lifted from TameAndFill.py's
    identify(), and the reasoning is unchanged: body values are not proof. Two
    species share one, shards reuse them, and a bad catalogue entry invents one -
    a stray 0x3 in the sheep entry, which is the ZOMBIE body, is how the parent
    came to target zombies. Here the body is not used to FIND anything, only to
    contradict a name that does not fit it.
    """
    name = mob_name(mob)
    if not name:
        return None, "its name will not load", True

    banned = is_never_tameable(name)
    if banned:
        return None, "the name matches NEVER_TAME_WORDS (%r)" % banned, False

    low = name.lower()
    for word in KEEP_NAME_WORDS:
        word = word.strip().lower()
        if word and word in low:
            return None, ("the name matches KEEP_NAME_WORDS (%r), so it is a "
                          "keeper" % word), False

    species, cleaned, loose = species_from_name(name)
    if species is None:
        if loose is not None:
            # The substring match would have called this a `loose` and offered
            # it that species' deed - the lesser hiryu bug. Name both, so the
            # cause is obvious from the journal alone, and hand over the row
            # that fixes it with the body read off this very animal.
            return None, ("'%s' is not a '%s' -- its name has more in it than "
                          "that, and '%s' is not in the catalogue. If your "
                          "shard deeds one, add to EXTRA_ANIMALS:  %s"
                          % (cleaned, loose["name"], cleaned,
                             unknown_species_line(cleaned, mob.Body))), False
        return None, ("'%s' is not a species in the catalogue. If your shard "
                      "deeds one, add to EXTRA_ANIMALS:  %s"
                      % (cleaned, unknown_species_line(cleaned, mob.Body))), False
    if species["name"] not in _active:
        return None, "there is no %s deed in your pack" % species["name"], True
    if mob.Body not in species["bodies"]:
        return None, ("it reads as %s but its body 0x%X is not one of that "
                      "species' bodies %s"
                      % (species["name"], mob.Body,
                         ["0x%X" % b for b in species["bodies"]])), False
    return species, "", False
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

    # DRAIN BEFORE THE CLEAR. The journal holds 100 lines and Clear() throws
    # them all away: a taming-success line still unread when this fires is not
    # read late, it is gone, and the animal it belonged to is left undeeded.
    # poll_tames() is cheap and banks it first.
    poll_tames()
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
    matched, _stated = species_from_deed(text)
    if matched is None or matched["name"] != species_name:
        log("Refusing to use %s for %s - it reads as %s."
            % (deed.Name or "deed", species_name,
               matched["name"] if matched else "no known species"), HUE_BAD)
        return False

    debug("Deed 0x%X (%s) <- pet 0x%X"
          % (deed.Serial, deed.Name or "?", pet_serial))

    for attempt in range(1, DEED_RETRIES + 1):
        if pet_is_gone(pet_serial):
            # chat(), NOT log(). consider() prints one line per animal, with
            # the deed's progress and the running count in it; this one said
            # the same event with less in it.
            chat("%s added to its taming order." % species_name, HUE_GOOD)
            return True

        result = deed_attempt(deed.Serial, pet_serial)
        if result == "ok":
            chat("%s added to its taming order." % species_name, HUE_GOOD)
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

    log("Could not add %s to a deed after %d attempts. The sequence itself is\n"
        "known good - run Scripts/diag_deed_target.py if it has stopped working."
        % (species_name, DEED_RETRIES), HUE_BAD)
    return False

# =============================================================================
# FILLING
# =============================================================================

def deed_status(species_name):
    """ " [24/60]" for that species' deed, or "" when it cannot be read."""
    entry = _active.get(species_name)
    if entry is None:
        return ""
    deed = Items.FindBySerial(entry["deed"])
    if deed is None:
        return ""
    progress = deed_progress(item_text(deed))
    if not progress:
        return ""
    return " [%d/%d]" % (progress[0], progress[1])


def deed_line():
    """Every deed in the pack and how far along it is, as one string."""
    if not _active:
        return "none in your pack - put some in and it will pick them up."
    return ", ".join("%s%s" % (name, deed_status(name))
                     for name in sorted(_active))


def deed_report(reason, force=False):
    """Say which deeds are in the pack. True if it said anything.

    THE SCRIPT'S ONE STATUS LINE, and the reason the rest of it could go
    quiet: asked for by the user along with the quiet, as the thing they
    actually wanted on screen.

    NOT REPEATED UNLESS IT CHANGED, which is what stops it becoming the spam
    it replaced. The heartbeat in run() calls this every STATUS_EVERY_MS, so
    an untouched pack answers once at startup and then says nothing until a
    deed appears, fills up or leaves. force=True is for the three cases where
    the answer is wanted whether or not it has changed: startup, being asked
    by name, and the species set changing.
    """
    body = deed_line()
    if not force and body == _reported[0]:
        return False
    _reported[0] = body
    log("Deeds (%s): %s" % (reason, body), HUE_GOOD if _active else HUE_WARN)
    return True


def explain(serial, text, hue=HUE_INFO):
    """Say it once per animal per reason. These are reached every lap.

    THROUGH chat(), so TALK 0 drops them. There is one of these for every
    animal standing near you that it is correctly ignoring - an old pet of
    yours reads as "I did not hear you tame it" every time the script starts -
    and a screenful of lines about animals it is right to leave alone was most
    of what made this script shout.
    """
    key = (serial, text)
    if key in _said:
        return
    _said.add(key)
    chat(text, hue)


def consider(serial):
    """What to do about one creature: "filled", "keep" or "wait".

    "keep" means never look at it again. "wait" means ask again next lap - the
    animal may still be walking back to you, or its deed may not be in your pack
    yet.
    """
    if serial in NEVER_FILL_SERIALS:
        explain(serial, "0x%X is in NEVER_FILL_SERIALS - leaving it." % serial)
        return "keep"
    if not FILL_MOUNT and serial == mount_serial():
        explain(serial, "That is your mount - leaving it.", HUE_WARN)
        return "keep"

    mob = Mobiles.FindBySerial(serial)
    if mob is None:
        explain(serial, "0x%X is yours but not in range - waiting for it."
                % serial)
        return "wait"

    label = mob.Name or "0x%X" % serial
    species, why, retry = pet_species(mob)
    if species is None:
        explain(serial, "Leaving %s alone: %s." % (label, why), HUE_WARN)
        return "wait" if retry else "keep"

    name = species["name"]
    if not have_credit():
        # Its tooltip or the client says it is ours, but no taming line of ours
        # is unspent - so it was tamed before this script started, or long
        # enough ago that the credit has expired. This is the guard that keeps
        # an old pet wandering into range from being deeded. See
        # REQUIRE_TAME_CREDIT.
        explain(serial, "%s is yours, but I did not hear you tame it - leaving "
                "it alone." % label, HUE_WARN)
        return "wait"

    try:
        dist = Player.DistanceTo(mob)
    except Exception:
        dist = 99
    if dist > MAX_FILL_DIST:
        explain(serial, "%s is %d tiles away - waiting for it to come to you "
                "(MAX_FILL_DIST is %d)." % (label, dist, MAX_FILL_DIST),
                HUE_WARN)
        return "wait"

    chat("Filling the %s deed%s." % (name, deed_status(name)))
    if not add_to_deed(name, serial):
        _tries[serial] = _tries.get(serial, 0) + 1
        if _tries[serial] < FILL_ATTEMPTS:
            return "wait"
        # OTHERWISE IT KEEPS TRYING, which is what the lesser hiryu looked like
        # in game: refused, retried, refused again until the credit expired. A
        # deed is refused for reasons that do not change by asking again - it
        # is not for this species, or the animal is not ours to give.
        log("The shard has refused %s %d times -- giving up on it. If it "
            "should fit that deed, then its name and the deed's do not agree."
            % (label, _tries[serial]), HUE_BAD)
        return "keep"

    spend_credit()
    _filled[0] += 1
    rescan("after a fill")
    # THE ONE LINE PER ANIMAL, at every talk level, because this is the thing
    # you are watching for. add_to_deed() used to say "added to its taming
    # order" as well and now says that through chat(), so at TALK 0 a fill is
    # exactly this line and nothing else.
    if name in _active:
        log("%s -> its taming order%s. %d deeded this run."
            % (name, deed_status(name), _filled[0]), HUE_GOOD)
    else:
        # It dropped out of the list in that rescan, so it is full now or the
        # shard consumed it. Worth saying, rather than showing as a blank.
        log("%s -> its taming order, which is now done. %d deeded this run."
            % (name, _filled[0]), HUE_GOOD)
    # THE REPORT COUNTS AS SAID, without saying it. The line above already
    # carries this species and its progress, and without this the heartbeat
    # would notice the change and print the whole report straight after every
    # single fill.
    _reported[0] = deed_line()
    return "filled"

# =============================================================================
# PREFLIGHT AND MAIN
# =============================================================================

def preflight():
    log("ManualTameAndFill %s - you tame, it fills. Say '%s' any time for a "
        "deed report." % (SCRIPT_VERSION, (STATUS_COMMANDS or ["?"])[0]),
        HUE_GOOD)

    if not build_species():
        log("The animal catalogue came out empty - check ONLY_ANIMALS and "
            "NEVER_ANIMALS.", HUE_BAD)
        return False
    debug("Catalogue: %d species." % len(_species))

    # BEFORE THE JOURNAL CURSOR IS SET, and before anything else: whatever is
    # already yours has to be out of reach first.
    kept = snapshot()
    log("%d animal(s) already yours are out of reach of this script." % kept,
        HUE_GOOD)
    mount = mount_serial()
    if mount:
        # chat(): the snapshot line above already covers the mount, and
        # FILL_MOUNT being ON is shouted separately below.
        chat("Your mount (0x%X) will never be deeded." % mount, HUE_GOOD)
    else:
        debug("No mount read from Player.Mount (or this build has no such "
              "property). The snapshot covers it either way.")

    # Nothing said before this moment can bank a credit, so a tame from ten
    # minutes ago cannot fill a deed the second this starts.
    _cursor[0] = newest_journal_stamp()
    debug("Journal cursor set at %r." % _cursor[0])

    # rescan() reports when the SET changed, which at startup it always has
    # when there is anything to find. An EMPTY pack is the one case it says
    # nothing about - empty to empty is not a change - and startup must still
    # state what it is going to do, even when that is "nothing yet".
    rescan("startup")
    if not _active:
        deed_report("startup", force=True)
    _status_at[0] = time.time()

    if not REQUIRE_TAME_CREDIT:
        log("REQUIRE_TAME_CREDIT is OFF: any pet of yours this script did not "
            "see at startup can be deeded. Turn it back on.", HUE_BAD)
    if FILL_MOUNT:
        log("FILL_MOUNT is ON. Your mount can be deeded.", HUE_BAD)

    # chat(). The first line said which copy loaded and the deed report said
    # what it will fill; a third line saying it is running is the kind of
    # thing this round was asked to take away.
    chat("Ready. Tame something.", HUE_GOOD)
    return True


def run():
    while True:
        if Player.IsGhost:
            log("You are dead. Stopping.", HUE_BAD)
            return

        # FIRST, EVERY LAP. Nothing below this line may run before the journal
        # has been read - see poll_tames() on why a line read late is a line
        # lost.
        poll_tames()
        prune_credits()

        if (time.time() - _last_scan) * 1000.0 >= DEED_RESCAN_MS:
            rescan("periodic")

        # THE HEARTBEAT, and a quiet one: deed_report() says nothing unless
        # the answer has changed since it last spoke. So this is not a line
        # every five minutes, it is "tell me within five minutes of a deed
        # appearing, filling up or being taken out".
        if (STATUS_EVERY_MS > 0
                and (time.time() - _status_at[0]) * 1000.0 >= STATUS_EVERY_MS):
            _status_at[0] = time.time()
            deed_report("latest")

        if not _active:
            # NOTHING SAID HERE ANY MORE. The old line repeated "no taming
            # order deeds in your pack" once a minute for as long as the
            # script ran. The report above says it once, and says it again
            # the moment it stops being true.
            Misc.Pause(IDLE_PAUSE)
            continue

        pending = [s for s in client_pets() if s not in _known]
        if _credits and not pending:
            # A tame landed and the client's pet list has not caught up with it.
            # Ask the server instead. Only in this branch: the tooltip reads are
            # the one expensive thing here, and with no credit waiting there is
            # nothing they could usefully find.
            pending = [s for s in nearby_tame_creatures() if s not in _known]

        if not pending:
            Misc.Pause(POLL_MS)
            continue

        for serial in pending:
            verdict = consider(serial)
            if verdict in ("filled", "keep"):
                # Filled animals are gone; kept ones are never asked about
                # again. Either way, stop looking at this serial.
                _known.add(serial)
            Misc.Pause(100)


def main():
    if not preflight():
        return
    try:
        run()
    finally:
        # However this ends - the Stop button, an exception, dying - do not walk
        # away holding a target cursor. One left open is answered by whatever
        # you click next, and a deed's cursor answered by accident puts an
        # animal in the wrong deed.
        try:
            Target.Cancel()
            Target.ClearQueue()
            Target.ClearLastandQueue()
        except Exception:
            pass
        log("Stopped. %d animal(s) deeded this run. Target cursor released."
            % _filled[0], HUE_INFO)


main()
