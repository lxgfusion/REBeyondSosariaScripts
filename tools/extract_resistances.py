"""Extract creature resistances from ServUO source into a pasteable table.

Run from a directory holding a ServUO checkout:

    git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/ServUO/ServUO.git
    git -C ServUO sparse-checkout set Scripts/Mobiles
    python tools/extract_resistances.py

Writes resists.json. Authoritative for a ServUO-derived freeshard in a way an
OSI wiki is not - the same reasoning as docs/tameable-animals.md.
"""
import os, re, sys, json

ROOT = "ServUO/Scripts/Mobiles"
TYPES = ["Physical", "Fire", "Cold", "Poison", "Energy"]

CLASS_RE = re.compile(r"public\s+class\s+(\w+)\s*:\s*(\w+)")
NAME_RE = re.compile(r'Name\s*=\s*"([^"]+)"')
BASE_NAME_RE = re.compile(r'base\(\s*"([^"]+)"')
RES_RE = re.compile(
    r"SetResistance\(\s*ResistanceType\.(\w+)\s*,\s*(\d+)\s*(?:,\s*(\d+))?\s*\)")

def clean(name):
    n = name.strip().lower()
    n = re.sub(r"^(a|an|the)\s+", "", n)
    return n.strip()

out = {}
for base, _dirs, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".cs"):
            continue
        path = os.path.join(base, fn)
        try:
            src = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if "SetResistance" not in src:
            continue

        res = {}
        for m in RES_RE.finditer(src):
            kind, lo, hi = m.group(1), int(m.group(2)), m.group(3)
            if kind not in TYPES:
                continue
            hi = int(hi) if hi is not None else lo
            res.setdefault(kind, (lo + hi) // 2)      # midpoint
        # An UNDECLARED resistance is 0 - ServUO only calls SetResistance for
        # the types a creature actually resists. Requiring all five dropped
        # every low-level animal: a chicken declares Physical and nothing else.
        if not res:
            continue
        for kind in TYPES:
            res.setdefault(kind, 0)

        names = set()
        for m in NAME_RE.finditer(src):
            names.add(clean(m.group(1)))
        for m in BASE_NAME_RE.finditer(src):
            names.add(clean(m.group(1)))
        # Fall back to the class name split into words.
        cm = CLASS_RE.search(src)
        if cm:
            words = re.sub(r"(?<!^)(?=[A-Z])", " ", cm.group(1)).lower()
            names.add(clean(words))

        for n in names:
            if not n or n in ("#", ""):
                continue
            # First file wins; ServUO has variants that reuse names.
            out.setdefault(n, {k: res[k] for k in TYPES})

json.dump(out, open("resists.json", "w"), indent=0, sort_keys=True)
print("species with a full resistance set: %d" % len(out))
for probe in ("hiryu", "lesser hiryu", "dragon", "greater dragon", "drake",
              "white wyrm", "unicorn", "ki-rin"):
    r = out.get(probe)
    if r:
        low = min(r, key=lambda k: r[k])
        print("  %-15s %s   weakest: %s" %
              (probe, " ".join("%s=%d" % (k[:4], r[k]) for k in TYPES), low))
    else:
        print("  %-15s NOT FOUND" % probe)
