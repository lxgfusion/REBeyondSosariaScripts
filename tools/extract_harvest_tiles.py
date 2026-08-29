"""Pull the harvest definitions out of ServUO source.

What the scripts need from it:

  * BankWidth / BankHeight - the size of a resource bank. A bank is the unit
    that DEPLETES, so it is also the distance between two spots worth standing
    on. Mining banks are 8x8; lumber banks are only 4x3. That single number is
    why a mining sweep has to walk much further between spots than a lumber
    one, and guessing it wrong means walking a long way to re-mine ground you
    just emptied.

  * MaxRange - how far the server lets you harvest. 2 tiles for both.

  * The tile-ID lists - which land and static tiles are mountain, cave or sand.
    Used to pick candidate spots without walking to them first.

Run it against the live ServUO tree on GitHub:

    python tools/extract_harvest_tiles.py --fetch

or against files already downloaded:

    python tools/extract_harvest_tiles.py path/to/Mining.cs path/to/Lumberjacking.cs

It writes docs/harvest-banks-and-tiles.md and prints a paste-ready Python block.
"""
from __future__ import print_function

import os
import re
import sys

RAW = "https://raw.githubusercontent.com/ServUO/ServUO/master/Scripts/Services/Harvest/%s"
FILES = ["Mining.cs", "Lumberjacking.cs"]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "harvest-banks-and-tiles.md")


def fetch(name):
    try:
        from urllib.request import urlopen
    except ImportError:                                  # Python 2
        from urllib2 import urlopen
    return urlopen(RAW % name).read().decode("utf-8", "replace")


def read(path):
    with open(path, "r") as handle:
        return handle.read()


def find_settings(src):
    """Every BankWidth / BankHeight / MaxRange / MinTotal / MaxTotal.

    Both the `x.Field = N;` and the object-initialiser `Field = N,` forms are
    used in ServUO - Mining.cs writes the first, Lumberjacking.cs the second -
    so both have to be matched or one of the two files silently yields nothing.
    """
    wanted = ["BankWidth", "BankHeight", "MaxRange", "MinTotal", "MaxTotal"]
    out = {}
    for field in wanted:
        found = re.findall(r"\b%s\s*=\s*(\d+)\s*[;,]" % field, src)
        if found:
            out[field] = [int(v) for v in found]
    return out


def find_tile_arrays(src):
    """Named int/static arrays of tile ids, as {name: [ids]}.

    Values are a mix of decimal and hex in the same array, so each is parsed on
    its own base rather than assuming one for the whole list.
    """
    arrays = {}
    pattern = re.compile(
        r"(?:private|public|internal)?\s*static\s+(?:readonly\s+)?int\[\]\s+"
        r"(\w+)\s*=\s*(?:new\s+int\[\]\s*)?\{(.*?)\}\s*;",
        re.S)
    for name, body in pattern.findall(src):
        # Only the tile lists. Mining.cs also declares m_Offsets, which is
        # SPAWN COORDINATE DELTAS - it holds negative numbers, so a tile parser
        # reads "-1, -1" as two tiles called 1 and quietly poisons the list.
        if not name.lower().endswith("tiles"):
            continue
        body = re.sub(r"//[^\n]*", "", body)
        values = []
        for token in re.findall(r"0[xX][0-9a-fA-F]+|\d+", body):
            values.append(int(token, 16) if token[:2].lower() == "0x"
                          else int(token))
        if values:
            arrays[name] = values
    return arrays


def as_python(name, ids, per_line=10):
    lines = ["%s = [" % name]
    for start in range(0, len(ids), per_line):
        chunk = ids[start:start + per_line]
        lines.append("    " + " ".join("0x%04X," % v for v in chunk))
    lines.append("]")
    return "\n".join(lines)


def main(argv):
    if "--fetch" in argv:
        sources = dict((name, fetch(name)) for name in FILES)
    else:
        paths = [a for a in argv if a.endswith(".cs")]
        if not paths:
            print(__doc__)
            return 2
        sources = dict((os.path.basename(p), read(p)) for p in paths)

    report = ["# Harvest banks and tiles",
              "",
              "Extracted from ServUO `Scripts/Services/Harvest/` by",
              "`tools/extract_harvest_tiles.py`. Do not edit by hand.",
              ""]
    blocks = []

    for name in sorted(sources):
        src = sources[name]
        settings = find_settings(src)
        arrays = find_tile_arrays(src)

        report.append("## %s" % name)
        report.append("")
        for field in ["BankWidth", "BankHeight", "MaxRange",
                      "MinTotal", "MaxTotal"]:
            if field in settings:
                values = settings[field]
                shown = values[0] if len(set(values)) == 1 else values
                report.append("- `%s` = %s" % (field, shown))
        report.append("")
        for array, ids in sorted(arrays.items()):
            report.append("- `%s`: %d tile ids, 0x%04X to 0x%04X"
                          % (array, len(ids), min(ids), max(ids)))
            blocks.append(as_python(array.lstrip("m_").upper(), sorted(set(ids))))
        report.append("")

    with open(OUT, "w") as handle:
        handle.write("\n".join(report))
    print("wrote %s" % OUT)
    print()
    for block in blocks:
        print(block)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
