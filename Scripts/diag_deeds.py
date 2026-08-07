"""
Deed discovery diagnostic.
==========================

Run this when tame_animals.py says it found no taming order deeds, or when it
misreads which species a deed is for.

It walks every item you are carrying, prints the exact text it can read from
each one, and shows the verdict tame_animals.py would reach:

    HINT?    does the name/tooltip contain one of DEED_NAME_HINTS
    SPECIES  which catalogue species the text names, if any

Nothing is used, moved, or targeted. Safe to run any time.

Keep DEED_NAME_HINTS and MAX_ITEMS in sync with tame_animals.py.
"""

import re


DEED_NAME_HINTS = ["order", "deed", "contract"]
DEED_SPECIES_FIELDS = ["creature type", "animal type", "species", "type"]
DEED_PROGRESS_FIELDS = ["filled", "progress", "amount"]
MAX_ITEMS = 300
PROPS_TIMEOUT = 1500
MAX_CONTAINER_DEPTH = 6

# Only tooltip lines are needed here, so this is the species names from
# tame_animals.py's ANIMAL_CATALOGUE without the body values.
SPECIES_NAMES = [
    "alligator", "bake kitsune", "battle chicken lizard", "bird", "black bear",
    "blood fox", "boar", "brown bear", "bull", "bull frog", "cat", "chicken",
    "chicken lizard", "cold drake", "corrosive slime", "cougar", "cow",
    "crimson drake", "cu sidhe", "deathwatch beetle", "desert ostard",
    "dire wolf", "dog", "dragon", "dragon wolf", "drake", "dread spider",
    "dread warhorse", "eagle", "ferret", "fire beetle", "fire steed",
    "forest ostard", "frenzied ostard", "frost dragon", "frost mite",
    "frost spider", "gaman", "gargoyle pet", "giant beetle", "giant ice worm",
    "giant rat", "giant spider", "giant toad", "goat", "gorilla", "great hart",
    "greater dragon", "greater mongbat", "grey wolf", "grizzly bear",
    "hell cat", "hell hound", "high plains boura", "hind", "hiryu", "horse",
    "ice hound", "imp", "iron beetle", "jack rabbit", "ki-rin", "lava lizard",
    "lion", "llama", "lowland boura", "mongbat", "mountain goat", "nightmare",
    "ossein ram", "pack horse", "pack llama", "panther", "parrot", "phoenix",
    "pig", "platinum drake", "polar bear", "predator hellcat", "rabbit", "rat",
    "reptalon", "ridable llama", "ridgeback", "ruddy boura", "rune beetle",
    "saber-toothed tiger", "savage ridgeback", "scorpion", "serpentine dragon",
    "sewer rat", "shadow wyrm", "sheep", "skittering hopper", "skree", "slime",
    "slith", "snake", "snow leopard", "squirrel", "stone slith", "stygian drake",
    "swamp dragon", "timber wolf", "triceratops", "tsuki wolf", "unicorn",
    "walrus", "white wolf", "white wyrm", "wild tiger", "wolf spider",
]

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Deeds] " + text, hue, False)


def rule(text):
    log("---- " + text + " ----", HUE_STEP)


def build_patterns():
    pairs = []
    for name in SPECIES_NAMES:
        parts = [p for p in re.split(r"[^a-z0-9]+", name.lower()) if p]
        if not parts:
            continue
        pattern = r"\b" + r"[^a-z0-9]*".join(re.escape(p) for p in parts) + r"\b"
        pairs.append((name, re.compile(pattern)))
    pairs.sort(key=lambda pair: -len(pair[0]))
    return pairs


PATTERNS = build_patterns()


def match_species(text):
    low = (text or "").lower()
    for name, pattern in PATTERNS:
        if pattern.search(low):
            return name
    return None


def looks_like_deed(text):
    if not DEED_NAME_HINTS:
        return True
    for hint in DEED_NAME_HINTS:
        if hint.strip().lower() in text:
            return True
    return False


def split_runtogether(raw):
    """Tooltip properties arrive concatenated: "Creature Type: KirinFilled: 24/60"."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw)


def field_value(text, label):
    """Value of a "label: value" field, ending at the next field's label."""
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
    """Returns (species, how_it_was_found)."""
    for label in DEED_SPECIES_FIELDS:
        value = field_value(text, label.strip().lower())
        if value:
            species = match_species(value)
            if species is not None:
                return species, "field '%s: %s'" % (label, value)
    species = match_species(text)
    if species is not None:
        return species, "free-text scan"
    return None, "no match"


def deed_progress(text):
    for label in DEED_PROGRESS_FIELDS:
        value = field_value(text, label.strip().lower())
        if not value:
            continue
        found = re.search(r"(\d+)\s*/\s*(\d+)", value)
        if found:
            return (int(found.group(1)), int(found.group(2)))
    return None


def is_held(item):
    """Is this item in the player's containers?

    RootContainer reports the backpack's item serial on this shard, not
    Player.Serial, so both are accepted and the chain is walked as a fallback.
    """
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


def held_items():
    f = Items.Filter()
    f.Enabled = True
    f.OnGround = 0
    found = Items.ApplyFilter(f)
    if not found:
        return []
    return [i for i in found if is_held(i)]


def item_lines(item):
    Items.WaitForProps(item, PROPS_TIMEOUT)
    lines = []
    try:
        lines = list(Items.GetPropStringList(item))
    except Exception as err:
        log("  tooltip read failed: %s" % err, HUE_BAD)
    return lines


def main():
    rule("deed discovery diagnostic")
    log("Hints in use: %s" % (", ".join(DEED_NAME_HINTS) or "(none - any item)"),
        HUE_INFO)

    items = held_items()
    if not items:
        log("Razor sees no items on you at all. Open your backpack and retry.",
            HUE_BAD)
        return

    log("Reading %d held items..." % len(items), HUE_INFO)
    if len(items) > MAX_ITEMS:
        log("More than MAX_ITEMS (%d) - only the first %d are read."
            % (MAX_ITEMS, MAX_ITEMS), HUE_WARN)
        items = items[:MAX_ITEMS]

    hunt = {}
    deedish = 0

    for item in items:
        lines = item_lines(item)
        name = item.Name or ""
        text = split_runtogether(" ".join([name] + lines)).lower()

        hinted = looks_like_deed(text)
        species, how = species_from_deed(text)

        # Only report items that are interesting: either they pass the hint
        # check, or they name a species (a near miss worth seeing).
        if not hinted and species is None:
            continue

        deedish += 1
        rule(name or "0x%X" % item.ItemID)
        log("serial=0x%X graphic=0x%X amount=%d"
            % (item.Serial, item.ItemID, item.Amount), HUE_INFO)
        for line in lines:
            log("  tooltip: %s" % line, HUE_INFO)
        if not lines:
            log("  tooltip: (empty - matching relies on the item name only)",
                HUE_WARN)
        log("  parsed : %s" % text, HUE_INFO)

        log("  HINT?   %s" % ("yes" if hinted else "NO"),
            HUE_GOOD if hinted else HUE_WARN)
        log("  SPECIES %s  (%s)" % (species or "none matched", how),
            HUE_GOOD if species else HUE_WARN)

        progress = deed_progress(text)
        if progress:
            full = progress[0] >= progress[1]
            log("  FILLED  %d/%d%s" % (progress[0], progress[1],
                                       "  <- FULL, will be skipped" if full else ""),
                HUE_WARN if full else HUE_INFO)

        if hinted and species:
            hunt.setdefault(species, []).append(item.Serial)
        elif species and not hinted:
            log("  -> Ignored: names a species but no hint word. Add a word from "
                "this item to DEED_NAME_HINTS.", HUE_WARN)
        elif hinted and not species:
            log("  -> Ignored: looks like a deed but names no known species. "
                "Add it to EXTRA_ANIMALS if your shard invented it.", HUE_WARN)

    rule("result")
    if not deedish:
        log("Nothing in your pack passed the hint check or named a species.",
            HUE_BAD)
        log("Set DEED_NAME_HINTS = [] in this script and rerun to dump every "
            "item, then pick a word your deeds actually contain.", HUE_WARN)
        return

    if not hunt:
        log("No item both passed the hint check AND named a species. See the "
            "notes above.", HUE_BAD)
        return

    log("tame_animals.py would hunt:", HUE_GOOD)
    for species in sorted(hunt):
        serials = hunt[species]
        extra = "" if len(serials) == 1 else " (+%d spare)" % (len(serials) - 1)
        log("  %s -> deed 0x%X%s" % (species, serials[0], extra), HUE_GOOD)


main()
