"""
Deed-driven auto-tamer.
=======================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

How it decides what to hunt
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
"""

import re
import time


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
# SERVER MESSAGES  (ServUO/RunUO Scripts/Skills/AnimalTaming.cs)
# =============================================================================

MSG_SUCCESS = [
    "It seems to accept you as master.",              # 502799
]

MSG_RETRY = [
    "You fail to tame the creature.",                 # 502798
    "You seem to anger the beast!",                   # 502805
    "The animal is too angry to continue taming.",    # 502794
    "You must wait a few moments to use another skill.",
]

MSG_REPOSITION = [
    "You are too far away to continue taming.",       # 502795
    "You do not have a clear path to the animal you are taming",  # 1049654
    "That is too far away.",
]

MSG_SKIP = [
    "That animal looks tame already.",                # 502804
    "That wasn't even challenging.",                  # 502797
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
    Misc.SendMessage("[Tamer] " + text, hue, False)


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

    return species


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
# TAMING
# =============================================================================

def watch_attempt(serial):
    """Poll the journal until this taming attempt resolves.

    Stays glued to the creature the whole time - it wanders while being tamed,
    and drifting costs the attempt to either the range re-check or the line of
    sight check. Caller must Journal.Clear() first.
    """
    deadline = time.time() + TAME_ATTEMPT_TIMEOUT / 1000.0

    while time.time() < deadline:
        if journal_hit(MSG_SUCCESS):
            return "success"
        if journal_hit(MSG_ABORT):
            return "abort"
        if journal_hit(MSG_SKIP):
            return "skip"
        if journal_hit(MSG_CONTESTED):
            return "contested"
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

    Returns "success", "skip", "lost", "unreachable", "exhausted" or "abort".
    """
    attempts = 0

    while attempts < MAX_TAME_ATTEMPTS:
        mob = Mobiles.FindBySerial(serial)
        if mob is None:
            return "lost"

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

        if not Target.WaitForTarget(TARGET_CURSOR_TIMEOUT, True):
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
            log("%s cannot be tamed by you - ignoring." % label, HUE_WARN)
            return "skip"
        if result == "abort":
            return "abort"
        if result == "lost":
            return "lost"
        if result == "contested":
            log("%s is being tamed by someone else - backing off." % label, HUE_WARN)
            Misc.Pause(CONTESTED_BACKOFF)
        elif result == "reposition":
            approach(serial, STAY_DIST, TAME_START_DIST)
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
# MAIN
# =============================================================================

def preflight():
    if not build_species():
        log("No species available - check ONLY_ANIMALS / NEVER_ANIMALS.", HUE_BAD)
        return False

    if Player.Backpack is None:
        log("No backpack found.", HUE_BAD)
        return False

    if Player.WarMode:
        log("Dropping war mode.", HUE_WARN)
        Player.SetWarMode(False)

    log("Reading taming order deeds from your pack...", HUE_INFO)
    if rescan("startup") == 0:
        log("Found no taming order deeds. Nothing will be tamed.", HUE_BAD)
        log("If you are holding deeds, DEED_NAME_HINTS is probably wrong - run "
            "Scripts/diag_deeds.py to see what the script reads.", HUE_WARN)
        return False

    log("Hunting: %s" % ", ".join(sorted(_active)), HUE_GOOD)
    return True


def main():
    if not preflight():
        return

    while True:
        if Player.IsGhost:
            log("You are dead. Stopping.", HUE_BAD)
            return

        if (time.time() - _last_scan) * 1000.0 >= DEED_RESCAN_MS:
            rescan("periodic")

        if not _active:
            Misc.Pause(IDLE_PAUSE * 5)
            rescan("waiting for deeds")
            continue

        if Player.Followers >= Player.FollowersMax:
            log("Follower slots are full. Waiting.", HUE_WARN)
            Misc.Pause(IDLE_PAUSE * 5)
            continue

        candidates = find_candidates()
        if not candidates:
            Misc.Pause(IDLE_PAUSE)
            continue

        mob = candidates[0]
        serial = mob.Serial

        species = identify(mob)
        if species is None:
            # Not something we hold a deed for, or not identifiable. Leave it.
            Misc.IgnoreObject(serial)
            continue

        label = species["name"]
        log("Found %s at %d tiles." % (label, Player.DistanceTo(mob)))
        result = tame(serial, label)

        if result == "success":
            add_to_deed(label, serial)
            Misc.IgnoreObject(serial)
            rescan("after tame")
        elif result == "abort":
            log("Stopping.", HUE_BAD)
            return
        elif result in ("skip", "unreachable", "exhausted"):
            log("Giving up on %s (%s)." % (label, result), HUE_WARN)
            Misc.IgnoreObject(serial)
        # "lost" - despawned or out of range; just rescan.

        Misc.Pause(500)


main()
