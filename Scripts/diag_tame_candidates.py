"""
Taming candidate diagnostic - why is a species being ignored?
=============================================================

For Razor Enhanced (IronPython 3.4). Target: RunUO/ServUO-derived freeshard.

Run this standing NEXT TO the creature TameAndFill.py refuses to tame (a cat,
a chicken, whatever it is). Nothing is targeted, tamed, used or moved - it only
looks and reports. Safe to run any time.

WHY THIS EXISTS
---------------
TameAndFill.py builds its creature scan from the BODY VALUES in its catalogue:

    f = Mobiles.Filter(); for body in _body_owners: f.Bodies.Add(body)

So if this shard gives cats or chickens a body the catalogue does not list, they
never come back from the filter at all - identify() is never reached, and NOT
ONE LOG LINE IS PRINTED. The script looks perfectly healthy while walking past
them. That failure is invisible from in-game, which is what this script fixes.

It therefore scans with NO body filter and reports every mobile in range, then
reproduces TameAndFill's decision for each one and names the exact reason.

WHAT IT CHECKS, in the order things actually go wrong
----------------------------------------------------
1. Your deeds. Which species each one resolves to - and, critically, any deed
   whose wording resolves to NOTHING, because such a deed is skipped silently
   and that species is never hunted. ("Cats" plural does not match "cat".)
2. Every mobile in range: name, BODY, distance.
   Any BODY MISMATCH is flagged inline here - name says "a cat" but the body
   is not the catalogued cat body. This is the silent killer described above.
3. The ignore list. Anything ruled out in an earlier run stays ignored until
   Misc.ClearIgnore() or a Razor restart, so a creature can be skipped forever
   for a reason that was fixed days ago. Scanned both ways to show the
   difference.
4. A summary cross-referencing the deeds you hold against what is in range.

Your taming skill and follower slots are reported too - both stop taming dead.

Output goes to the journal and to %TEMP%\\tame_candidates.txt (path printed at
the end) - paste that file back rather than retyping it.

Keep the catalogue below in step with tame_animals.py / TameAndFill.py.
"""

import os
import re


SCRIPT_VERSION = "1.0.0"

# =============================================================================
# CONFIG
# =============================================================================

# How far out to look. Always bounded - an unset RangeMax means everything the
# client knows about, roughly 18-25 tiles.
SCAN_RANGE = 18

# Scan a second time with the ignore list DISABLED, and report what the ignore
# list is hiding. This is read-only; it does not clear anything.
SHOW_IGNORED = True

# Actually clear Razor's global ignore list before scanning. Off by default
# because it affects every other script; turn it on if section 4 reports that
# the creature you care about is being hidden.
CLEAR_IGNORE_FIRST = False

# Deed discovery - keep in step with TameAndFill.py.
DEED_NAME_HINTS = ["order", "deed", "contract"]
DEED_SPECIES_FIELDS = ["creature type", "animal type", "species", "type"]
DEED_PROGRESS_FIELDS = ["filled", "progress", "amount"]
MAX_CONTAINER_DEPTH = 6
MAX_PACK_SCAN = 300
PROPS_TIMEOUT = 1500

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "tame_candidates.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


# =============================================================================
# ANIMAL CATALOGUE - name, bodies, min taming skill.
# Duplicated from tame_animals.py on purpose: Razor runs each script standalone
# and cross-file imports break when files move.
# =============================================================================

ANIMAL_CATALOGUE = [
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
    ("wild tiger",            [0x4E6, 0x4E7],           95.1),
    ("wolf spider",           [0x2E0],                  59.1),
]

NEVER_TAME_WORDS = [
    "zombie", "skeleton", "skeletal", "lich", "wraith", "spectre", "specter",
    "ghoul", "mummy", "bone ", "corpser", "revenant", "shade",
    "golem", "elemental", "daemon", "demon", "gargoyle warrior",
    "ogre", "troll", "ettin", "orc", "ratman", "lizardman", "harpy",
    "titan", "cyclops", "juka", "meer", "solen", "terathan", "ophidian",
]


# =============================================================================
# STATE
# =============================================================================

_lines = []
_species = {}
_patterns = []
_body_index = {}          # body -> [species names] across the WHOLE catalogue
_name_cache = {}          # serial -> name; a miss costs a SingleClick + 600ms,
                          # and the report walks the same mobiles repeatedly


# =============================================================================
# HELPERS
# =============================================================================

def log(text, hue=HUE_INFO):
    Misc.SendMessage("[TameDiag] " + text, hue, False)
    _lines.append(text)


def rule(text):
    log("", HUE_INFO)
    log("---- " + text + " ----", HUE_STEP)


def build_species():
    for name, bodies, min_tame in ANIMAL_CATALOGUE:
        key = name.strip().lower()
        _species[key] = {"name": key, "bodies": list(bodies),
                         "min_tame": float(min_tame)}
        for body in bodies:
            _body_index.setdefault(body, []).append(key)

    for key in _species:
        parts = [p for p in re.split(r"[^a-z0-9]+", key) if p]
        if not parts:
            continue
        pattern = r"\b" + r"[^a-z0-9]*".join(re.escape(p) for p in parts) + r"\b"
        _patterns.append((_species[key], re.compile(pattern)))

    # Longest first so "hell cat" beats "cat".
    _patterns.sort(key=lambda pair: -len(pair[0]["name"]))

    build_never_patterns()


def match_species(text):
    if not text:
        return None
    low = text.lower()
    for species, pattern in _patterns:
        if pattern.search(low):
            return species
    return None


def split_runtogether(raw):
    """Tooltip properties arrive concatenated: "CatFilled" -> "Cat Filled"."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw)


def field_value(text, label):
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
        words = words[:-1]
    return " ".join(words).strip()


def species_from_deed(text):
    for label in DEED_SPECIES_FIELDS:
        value = field_value(text, label.strip().lower())
        if value:
            species = match_species(value)
            if species is not None:
                return species
    return match_species(text)


def deed_progress(text):
    for label in DEED_PROGRESS_FIELDS:
        value = field_value(text, label.strip().lower())
        if not value:
            continue
        found = re.search(r"(\d+)\s*/\s*(\d+)", value)
        if found:
            return (int(found.group(1)), int(found.group(2)))
    return None


def item_text(item):
    Items.WaitForProps(item, PROPS_TIMEOUT)
    parts = []
    if item.Name:
        parts.append(item.Name)
    try:
        parts.extend(Items.GetPropStringList(item))
    except Exception:
        pass
    return split_runtogether(" ".join(parts)).lower()


def is_held(item):
    roots = [Player.Serial]
    backpack = Player.Backpack
    if backpack is not None:
        roots.append(backpack.Serial)
    if item.RootContainer in roots:
        return True
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


def mob_name(mob):
    if mob.Serial in _name_cache:
        return _name_cache[mob.Serial]
    name = _mob_name_uncached(mob)
    _name_cache[mob.Serial] = name
    return name


def _mob_name_uncached(mob):
    if mob.Name:
        return mob.Name
    try:
        Mobiles.WaitForProps(mob, PROPS_TIMEOUT)
        fresh = Mobiles.FindBySerial(mob.Serial)
        if fresh is not None and fresh.Name:
            return fresh.Name
        Mobiles.SingleClick(mob)
        Misc.Pause(600)
        fresh = Mobiles.FindBySerial(mob.Serial)
        if fresh is not None and fresh.Name:
            return fresh.Name
    except Exception:
        pass
    return None


_never_patterns = []


def build_never_patterns():
    """Compile NEVER_TAME_WORDS with a LEADING word boundary.

    A bare substring test matches inside unrelated words: "orc" is in
    "s-orc-eress", so "Vela the sorceress" was reported as untameable. Anchoring
    only the START of the word fixes that while still catching the inflections
    that matter - "orcish" and "orcs" are still blocked, because there the match
    does begin at a word boundary.
    """
    del _never_patterns[:]
    for word in NEVER_TAME_WORDS:
        word = word.strip().lower()
        if word:
            _never_patterns.append((word, re.compile(r"\b" + re.escape(word))))


def is_never_tameable(name):
    low = (name or "").lower()
    for word, pattern in _never_patterns:
        if pattern.search(low):
            return word
    return None


def scan_mobiles(check_ignore):
    """Every mobile in range. NO body filter - that is the entire point."""
    f = Mobiles.Filter()
    f.Enabled = True
    f.RangeMax = SCAN_RANGE          # never leave this unset
    f.CheckIgnoreObject = check_ignore
    found = Mobiles.ApplyFilter(f)
    if not found:
        return []
    out = list(found)
    out.sort(key=lambda mob: Player.DistanceTo(mob))
    return out


# =============================================================================
# REPORT SECTIONS
# =============================================================================

def report_deeds():
    """Section 1 - what the pack scan makes of your deeds."""
    rule("1. TAMING ORDER DEEDS IN YOUR PACK")

    f = Items.Filter()
    f.Enabled = True
    f.OnGround = 0
    found = Items.ApplyFilter(f)
    items = [i for i in (found or []) if is_held(i)][:MAX_PACK_SCAN]

    held = {}
    any_deed = False
    for item in items:
        text = item_text(item)
        if not looks_like_deed(text):
            continue
        any_deed = True
        species = species_from_deed(text)
        progress = deed_progress(text)
        where = "" if not progress else " [%d/%d]" % (progress[0], progress[1])

        if species is None:
            log("DEED NAMES NO KNOWN SPECIES: %s"
                % (item.Name or "0x%X" % item.ItemID), HUE_BAD)
            log("    raw text: %s" % text[:160], HUE_WARN)
            log("    -> this deed is SKIPPED and that species is never hunted.",
                HUE_BAD)
            log("    -> if the type reads plural ('Cats'), that is the bug.",
                HUE_WARN)
            continue

        full = progress and progress[0] >= progress[1]
        held[species["name"]] = True
        log("%s -> %s%s%s"
            % (item.Name or "0x%X" % item.ItemID, species["name"], where,
               "  (FULL - skipped)" if full else ""),
            HUE_WARN if full else HUE_GOOD)

    if not any_deed:
        log("No deed-like items found. DEED_NAME_HINTS = %s" % DEED_NAME_HINTS,
            HUE_BAD)
    return held


def report_mobiles(held):
    """Sections 2-4 - what is standing around you and what would happen."""
    rule("2. EVERY MOBILE IN RANGE (no body filter)")

    visible = scan_mobiles(check_ignore=True)
    log("%d mobile(s) within %d tiles, ignore list APPLIED."
        % (len(visible), SCAN_RANGE))

    seen = {}
    for mob in visible:
        seen[mob.Serial] = True
        describe(mob, held)

    if SHOW_IGNORED:
        rule("3. WHAT THE IGNORE LIST IS HIDING")
        everything = scan_mobiles(check_ignore=False)
        hidden = [m for m in everything if m.Serial not in seen]
        if not hidden:
            log("Nothing is being hidden by the ignore list.", HUE_GOOD)
        else:
            log("%d mobile(s) are hidden by Razor's ignore list:" % len(hidden),
                HUE_BAD)
            for mob in hidden:
                log("  IGNORED: %-24s body 0x%-4X  %d tiles"
                    % (mob_name(mob) or "(name will not load)",
                       mob.Body, Player.DistanceTo(mob)), HUE_BAD)
            log("These were ruled out in an EARLIER run and stay ignored until",
                HUE_WARN)
            log("Misc.ClearIgnore() or a Razor restart - set "
                "CLEAR_IGNORE_FIRST = True and rerun.", HUE_WARN)


def describe(mob, held):
    """Reproduce TameAndFill's verdict for one creature, and say why."""
    name = mob_name(mob)
    body = mob.Body
    dist = Player.DistanceTo(mob)
    shown = name or "(name will not load)"

    log("")
    log("%-26s body 0x%-4X  %d tiles  serial 0x%X"
        % (shown, body, dist, mob.Serial), HUE_INFO)

    if not name:
        log("    -> IGNORED: the name will not load, and REQUIRE_NAME_MATCH "
            "refuses to act on a body alone.", HUE_BAD)
        return

    banned = is_never_tameable(name)
    if banned:
        log("    -> IGNORED: NEVER_TAME_WORDS matched %r." % banned, HUE_WARN)
        return

    species = match_species(name)
    if species is None:
        log("    -> not a catalogue species. Ignored (correctly, unless this "
            "is a shard-custom animal).", HUE_INFO)
        return

    log("    name reads as: %s   (catalogue bodies %s, needs taming %.1f)"
        % (species["name"], ["0x%X" % b for b in species["bodies"]],
           species["min_tame"]), HUE_INFO)

    # THE SILENT KILLER - the body is not what the catalogue says it is.
    if body not in species["bodies"]:
        owners = _body_index.get(body)
        log("    *** BODY MISMATCH ***", HUE_BAD)
        log("    This shard gives %s body 0x%X, but the catalogue lists %s."
            % (species["name"], body,
               ["0x%X" % b for b in species["bodies"]]), HUE_BAD)
        if owners:
            log("    (0x%X is catalogued as: %s)" % (body, ", ".join(owners)),
                HUE_WARN)
        log("    -> TameAndFill NEVER SEES THIS CREATURE: the scan filter is "
            "built from catalogue bodies, so it is not returned at all and no "
            "log line is printed.", HUE_BAD)
        log("    FIX: add 0x%X to the %s row of ANIMAL_CATALOGUE."
            % (body, species["name"]), HUE_GOOD)
        return

    skill = Player.GetSkillValue("Animal Taming")
    if species["min_tame"] > skill:
        log("    -> IGNORED: needs taming %.1f, you have %.1f."
            % (species["min_tame"], skill), HUE_WARN)
        return

    if species["name"] not in held:
        log("    -> not hunted: you hold no usable deed for %s."
            % species["name"], HUE_WARN)
        return

    log("    -> WOULD BE TAMED. Nothing in the config blocks this one.",
        HUE_GOOD)


def report_summary(held):
    """Section 5 - the cross-reference that answers 'why is X ignored'."""
    rule("4. SUMMARY - deeds held vs what is actually around you")

    if not held:
        log("You hold no usable deeds, so nothing would be hunted at all.",
            HUE_BAD)
        return

    everything = scan_mobiles(check_ignore=False)
    for species_name in sorted(held):
        species = _species.get(species_name)
        if species is None:
            continue

        # Split the creatures whose NAME says this species by whether the scan
        # filter could ever return them. Counting bodies alone is not enough:
        # some unrelated mobile may sit on the catalogue body and mask the
        # mismatch, which is exactly what happened while testing this script.
        reachable = []
        unreachable = []
        for mob in everything:
            nm = mob_name(mob)
            if not nm:
                continue
            matched = match_species(nm)
            if matched is None or matched["name"] != species_name:
                continue
            if mob.Body in species["bodies"]:
                reachable.append(mob)
            else:
                unreachable.append(mob)

        total = len(reachable) + len(unreachable)
        log("")
        log("%s: %d here by name - %d reachable by the scan, %d INVISIBLE to it."
            % (species_name, total, len(reachable), len(unreachable)),
            HUE_BAD if unreachable else HUE_GOOD)

        if unreachable:
            bodies = sorted(set(m.Body for m in unreachable))
            log("  *** THIS IS THE BUG for %s ***" % species_name, HUE_BAD)
            log("  %d creature(s) named %s are standing here with body %s, but "
                "the catalogue says %s - so the scan filter never returns them "
                "and nothing is logged."
                % (len(unreachable), species_name,
                   ["0x%X" % b for b in bodies],
                   ["0x%X" % b for b in species["bodies"]]), HUE_BAD)
            log("  FIX: set the %s row's bodies to %s."
                % (species_name,
                   ["0x%X" % b for b in sorted(set(bodies) |
                                               set(species["bodies"]))]),
                HUE_GOOD)
        elif not total:
            log("  None in range, so nothing can be concluded - stand next to "
                "one and rerun.", HUE_WARN)


def report_body_filter(held):
    """Section 5 - run TameAndFill's ACTUAL scan, body filter and all.

    Everything above scans with no body filter, on purpose. That proves what is
    standing there, but it deliberately skips the one call the real script makes
    and this one otherwise does not:

        f = Mobiles.Filter(); for body in _body_owners: f.Bodies.Add(body)

    If the creature is present, correctly named, on the catalogued body, not
    ignored and within skill - and the real script still walks past it - then
    this filter is the only remaining suspect. So run it exactly as
    find_candidates() does and report what comes back.
    """
    rule("5. THE REAL SCAN - Mobiles.Filter with Bodies, as find_candidates()")

    if not held:
        log("No deeds held, so the real scan would be empty regardless.",
            HUE_WARN)
        return

    body_owners = {}
    for species_name in held:
        species = _species.get(species_name)
        if species is None:
            continue
        for body in species["bodies"]:
            body_owners.setdefault(body, []).append(species_name)

    log("Filter bodies: %s"
        % ", ".join("0x%X (%s)" % (b, "/".join(body_owners[b]))
                    for b in sorted(body_owners)))

    try:
        f = Mobiles.Filter()
        f.Enabled = True
        f.RangeMax = SCAN_RANGE
        f.CheckIgnoreObject = True
        for body in body_owners:
            f.Bodies.Add(body)
        found = Mobiles.ApplyFilter(f)
    except Exception as exc:
        log("*** THE BODY FILTER THREW: %s ***" % exc, HUE_BAD)
        log("That is the bug - find_candidates() cannot run at all.", HUE_BAD)
        return

    found = list(found or [])
    log("The real scan returned %d creature(s)." % len(found),
        HUE_GOOD if found else HUE_BAD)
    for mob in found:
        log("  RETURNED: %-22s body 0x%-4X  %d tiles"
            % (mob_name(mob) or "(name will not load)", mob.Body,
               Player.DistanceTo(mob)), HUE_GOOD)

    # Cross-check against the unfiltered scan: anything on a filter body that
    # the plain scan sees but this one does not is the smoking gun.
    plain = [m for m in scan_mobiles(check_ignore=True)
             if m.Body in body_owners]
    missing = [m for m in plain
               if m.Serial not in dict((x.Serial, 1) for x in found)]

    if missing:
        log("*** BODY FILTER IS DROPPING CREATURES ***", HUE_BAD)
        log("%d creature(s) on a filter body are visible to a plain scan but "
            "are NOT returned when Bodies is set:" % len(missing), HUE_BAD)
        for mob in missing:
            log("  DROPPED: %-22s body 0x%-4X  %d tiles"
                % (mob_name(mob) or "(name will not load)", mob.Body,
                   Player.DistanceTo(mob)), HUE_BAD)
        log("This is a Razor Enhanced filter problem, not a config problem - "
            "find_candidates() would have to stop using Bodies.", HUE_WARN)
    elif found:
        log("Body filter agrees with the plain scan - it is NOT the fault.",
            HUE_GOOD)
        log("If TameAndFill still ignores these, it is running a STALE COPY: "
            "hit Reload in the Scripting tab.", HUE_WARN)


def write_dump():
    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(_lines))
        log("")
        log("Written to %s" % DUMP_PATH, HUE_GOOD)
        log("Paste that file back rather than retyping it.", HUE_INFO)
    except Exception as exc:
        log("Could not write %s (%s)" % (DUMP_PATH, exc), HUE_BAD)


# =============================================================================
# MAIN
# =============================================================================

def main():
    log("diag_tame_candidates v%s - read-only, nothing is tamed."
        % SCRIPT_VERSION, HUE_STEP)

    if Player.Backpack is None:
        log("No backpack found.", HUE_BAD)
        return

    build_species()

    if CLEAR_IGNORE_FIRST:
        Misc.ClearIgnore()
        log("Razor's global ignore list has been CLEARED.", HUE_WARN)

    log("Taming skill: %.1f   Followers: %d/%d"
        % (Player.GetSkillValue("Animal Taming"),
           Player.Followers, Player.FollowersMax))
    if Player.Followers >= Player.FollowersMax:
        log("Follower slots are FULL - TameAndFill waits and tames nothing.",
            HUE_BAD)

    held = report_deeds()
    report_mobiles(held)
    report_summary(held)
    report_body_filter(held)
    write_dump()


main()
