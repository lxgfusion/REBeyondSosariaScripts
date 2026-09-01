"""Work out which TAMEABLE species attack on sight, from ServUO source.

Run from the repo root with a ServUO checkout on hand:

    git clone --depth 1 --filter=blob:none --sparse \\
        https://github.com/ServUO/ServUO.git
    git -C ServUO sparse-checkout set Scripts/Mobiles
    python tools/extract_aggressive.py ServUO

WHY THIS EXISTS. PEACE_AGGRESSIVE_WORDS decides which creatures get played to
before a taming attempt. Getting it from memory is exactly the mistake
CLAUDE.md warns about for bodies and taming skills, and it fails the same way:
quietly, on the species nobody thought of.

THE SIGNAL. BaseCreature's constructor takes a FightMode, and it is the whole
answer:

    FightMode.Aggressor   fights back only once attacked  -> PASSIVE
    FightMode.Closest     attacks whatever is nearest     -> AGGRESSIVE
    FightMode.Weakest     picks off the weakest           -> AGGRESSIVE
    FightMode.Strongest                                   -> AGGRESSIVE
    FightMode.Good / Evil  attacks by karma               -> AGGRESSIVE

So "hostile" is not a judgement call about what a dragon is like. It is a
field, and it is in the source.

Only creatures that are BOTH tameable and aggressive matter here - a passive
tameable does not need calming, and an untameable one is never approached.
"""
import os
import re
import sys

# Anything that is not Aggressor attacks without being provoked.
PASSIVE_MODES = ("Aggressor",)

TAMEABLE = re.compile(r"Tamable\s*=\s*true", re.I)
FIGHTMODE = re.compile(r"FightMode\.(\w+)")
# NOT just ": BaseCreature". Mounts extend BaseMount, and a first cut of this
# matched only BaseCreature - which silently dropped every rideable species,
# hiryu included, from a list whose whole job is to say what will bite you.
# Same shape as the ternary-body gap CLAUDE.md records for the catalogue: the
# extraction looked right and was quietly incomplete.
CLASSNAME = re.compile(
    r"public\s+(?:abstract\s+|sealed\s+)?class\s+(\w+)\s*:\s*"
    r"(?:Base\w+|\w*Creature\w*)")
CORPSENAME = re.compile(r'CorpseNameAttribute\s*\(\s*"([^"]+)"')
NAMEASSIGN = re.compile(r'Name\s*=\s*"([^"]+)"')


def species_name(text, klass):
    """The in-game name, from the corpse attribute or a Name assignment.

    Falls back to the class name split on capitals, which is right often
    enough to be worth offering and is always shown for checking.
    """
    m = CORPSENAME.search(text)
    if m:
        return m.group(1).replace("a ", "", 1).replace("an ", "", 1).strip()
    m = NAMEASSIGN.search(text)
    if m and not m.group(1).startswith("#"):
        return m.group(1).strip()
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", klass).lower()


def scan(root):
    """[(class, name, fightmode, tameable)] for every BaseCreature found."""
    out = []
    for base, _dirs, files in os.walk(root):
        for fname in files:
            if not fname.endswith(".cs"):
                continue
            path = os.path.join(base, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except Exception:
                continue
            # Gate on the FIELD, not on a base-class name: BaseMount files
            # do not necessarily mention BaseCreature at all, and gating on it
            # is what dropped the mounts in the first place.
            if "Tamable" not in text and "FightMode" not in text:
                continue
            for klass in CLASSNAME.findall(text):
                # The file may hold several classes; the tameable flag and the
                # fight mode are read from the file as a whole, which is right
                # for the one-class-per-file layout ServUO uses and is reported
                # so a multi-class file can be spotted.
                modes = FIGHTMODE.findall(text)
                out.append((klass, species_name(text, klass),
                            modes[0] if modes else None,
                            bool(TAMEABLE.search(text))))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "ServUO"
    mobiles = os.path.join(root, "Scripts", "Mobiles")
    if not os.path.isdir(mobiles):
        print("No %s - clone ServUO first (see the docstring)." % mobiles)
        return 1

    found = scan(mobiles)
    tameable = [row for row in found if row[3]]
    aggressive = [row for row in tameable
                  if row[2] and row[2] not in PASSIVE_MODES]
    passive = [row for row in tameable if row[2] in PASSIVE_MODES]
    unknown = [row for row in tameable if not row[2]]

    print("%d BaseCreature class(es) scanned" % len(found))
    print("  %d tameable" % len(tameable))
    print("     %d AGGRESSIVE (FightMode is not Aggressor)" % len(aggressive))
    print("     %d passive" % len(passive))
    print("     %d with no FightMode found" % len(unknown))
    print()

    modes = {}
    for _k, _n, mode, _t in aggressive:
        modes[mode] = modes.get(mode, 0) + 1
    print("aggressive by mode: %s"
          % ", ".join("%s=%d" % kv for kv in sorted(modes.items())))
    print()

    print("--- tameable AND aggressive, by name ---")
    for _klass, name, mode, _t in sorted(aggressive, key=lambda r: r[1]):
        print("    %-34s %s" % (name, mode))

    if unknown:
        print()
        print("--- tameable, NO FightMode in the file (inherits a default) ---")
        for _klass, name, _m, _t in sorted(unknown, key=lambda r: r[1]):
            print("    %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
