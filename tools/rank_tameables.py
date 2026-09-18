"""Rank every tameable species by the difficulty ServUO gives it.

    python tools/rank_tameables.py            # the ranked table
    python tools/rank_tameables.py --bands    # how the skill values cluster

The MIN TAMING SKILL is real data - extracted from ServUO source into
Scripts/TameAndFill.py's ANIMAL_CATALOGUE, and re-read here rather than
retyped. The ORDER LEVEL is not: it lives on the shard's own taming order
deeds ("Level: 2Creature Type: Kirin...") and nothing in this repo has ever
read one.

So this ranks, and it BANDS, and it is careful to say which is which. Two
levels are known from the user: sheep is 1, dragon is 3. Two points do not
determine 112, and CLAUDE.md is explicit that shard data comes from source or
a live dump and never from memory - which is why the band column below is
labelled as a guess everywhere it appears.

Scripts/diag_taming_levels.py reads the real numbers off the deeds in your
pack and prints rows to paste in, the same way the granite hue table filled
itself.
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.path.join(HERE, os.pardir, "Scripts", "TameAndFill.py")

# The two levels that are actually known, from the user, 2026-09-18.
CONFIRMED = {"sheep": 1, "dragon": 3}

# The band boundaries this file guesses at, in min taming skill. Chosen to put
# the two confirmed species in their confirmed bands and to fall in the widest
# empty gaps in the data - see --bands. NOT confirmed against the shard.
BANDS = [(0.0, 1, "level 1 (guess)"),
         (50.0, 2, "level 2 (guess)"),
         (90.0, 3, "level 3 (guess)")]


def catalogue():
    """[(name, [bodies], min_skill)] read out of the script's own table.

    Scoped to the ANIMAL_CATALOGUE list and COMMENT LINES DROPPED. Reading the
    whole file matched the worked examples in the HARVEST_BODIES comment too,
    which put a second "goat" in the table - a reminder that a regex over a
    source file reads the prose as happily as the data.
    """
    src = io.open(CATALOGUE, encoding="utf-8").read()
    start = src.index("ANIMAL_CATALOGUE = [")
    end = src.index(chr(10) + "]", start)
    body = chr(10).join(line for line in src[start:end].splitlines()
                        if not line.lstrip().startswith("#"))

    rows, seen = [], set()
    for name, bodies, skill in re.findall(
            r'\("([a-z][^"]*)",\s*\[([^\]]*)\],\s*([\d.]+)\)', body):
        if name in seen:
            raise SystemExit("%s is listed twice in ANIMAL_CATALOGUE" % name)
        seen.add(name)
        ids = [int(b, 16) for b in re.findall(r"0x[0-9A-Fa-f]+", bodies)]
        rows.append((name, ids, float(skill)))
    return rows


def band_of(skill):
    """(level, label) this file would guess for a species at `skill`."""
    chosen = BANDS[0]
    for floor, level, label in BANDS:
        if skill >= floor:
            chosen = (floor, level, label)
    return chosen[1], chosen[2]


def show_bands(rows):
    """Where the skill values actually cluster, so the guess is inspectable."""
    values = sorted(set(s for _n, _b, s in rows))
    print("%d distinct min-skill values across %d species\n"
          % (len(values), len(rows)))
    print("the widest gaps - a band boundary is least wrong inside one:")
    gaps = []
    for a, b in zip(values, values[1:]):
        gaps.append((b - a, a, b))
    for size, a, b in sorted(gaps, reverse=True)[:8]:
        print("    %5.1f wide: nothing between %.1f and %.1f" % (size, a, b))
    print()
    for floor, level, _label in BANDS:
        here = [n for n, _b, s in rows if band_of(s)[0] == level]
        print("  level %d (>= %5.1f skill): %3d species" % (level, floor,
                                                            len(here)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", action="store_true",
                    help="show how the skill values cluster")
    ap.add_argument("--markdown", action="store_true",
                    help="emit the docs table")
    args = ap.parse_args()

    rows = catalogue()
    if args.bands:
        show_bands(rows)
        return 0

    ranked = sorted(rows, key=lambda r: (r[2], r[0]))

    if args.markdown:
        print("| # | Species | Min taming | Band | Bodies |")
        print("|--:|---|--:|:--:|---|")
        for i, (name, ids, skill) in enumerate(ranked, 1):
            level, _label = band_of(skill)
            mark = "**%d**" % CONFIRMED[name] if name in CONFIRMED else str(level)
            if name in CONFIRMED:
                mark += " (confirmed)"
            print("| %d | %s | %.1f | %s | %s |"
                  % (i, name, skill, mark,
                     ", ".join("`0x%X`" % b for b in ids)))
        return 0

    for i, (name, ids, skill) in enumerate(ranked, 1):
        level, _label = band_of(skill)
        flag = "  <- CONFIRMED level %d" % CONFIRMED[name] \
            if name in CONFIRMED else ""
        print("%3d  %-24s skill %5.1f   band %d%s" % (i, name, skill, level,
                                                      flag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
