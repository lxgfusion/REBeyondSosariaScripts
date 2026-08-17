"""Extract damage spells from ServUO source: school, base damage, type.

Run from a directory holding a ServUO checkout:

    git clone --depth 1 --filter=blob:none --sparse \
        https://github.com/ServUO/ServUO.git
    git -C ServUO sparse-checkout set Scripts/Mobiles Scripts/Spells
    python tools/extract_spells.py

Base damage is the first argument to GetNewAosDamage. Spells that compute
damage some other way - Poison Strike, Wither, Wildfire, Thunderstorm,
Essence of Wind, Earthquake - come out with base None and are left out of
the table rather than guessed at.
"""
import os, re, json

ROOT = "ServUO/Scripts/Spells"
MAGERY_DIRS = {"First", "Second", "Third", "Fourth", "Fifth", "Sixth",
               "Seventh", "Eighth"}

DAMAGE_RE = re.compile(
    r"(?:SpellHelper\.Damage|AOS\.Damage)\s*\([^;]*?"
    r"(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*[,)]", re.S)
BASE_RE = re.compile(r"GetNewAosDamage\(\s*(\d+)")
TYPES = ["physical", "fire", "cold", "poison", "energy"]

out = {}
for base, _dirs, files in os.walk(ROOT):
    school = None
    parts = base.replace("\\", "/").split("/")
    for part in parts:
        if part in MAGERY_DIRS:
            school = "magery"
        elif part in ("Necromancy", "Spellweaving", "Mysticism"):
            school = part.lower()
    if school is None:
        continue

    for fn in files:
        if not fn.endswith(".cs"):
            continue
        src = open(os.path.join(base, fn), encoding="utf-8",
                   errors="ignore").read()
        m = DAMAGE_RE.search(src)
        if not m:
            continue
        split = [int(g) for g in m.groups()]
        if sum(split) == 0:
            continue
        dmg = BASE_RE.search(src)
        name = re.sub(r"(?<!^)(?=[A-Z])", " ", fn[:-3]).replace(" Spell", "")
        # The in-game name from the SpellInfo, when present, beats the filename.
        info = re.search(r'new SpellInfo\(\s*"([^"]+)"', src)
        if info:
            name = info.group(1)
        dominant = TYPES[split.index(max(split))]
        out[name.strip()] = {
            "school": school,
            "type": dominant,
            "split": dict(zip(TYPES, split)),
            "base": int(dmg.group(1)) if dmg else None,
            "area": "SpellAOE" in src or "AreaAttack" in src,
        }

json.dump(out, open("spells.json", "w"), indent=0, sort_keys=True)
print("damage spells found: %d\n" % len(out))
print("%-22s %-13s %-9s %5s %s" % ("spell", "school", "type", "base", "area"))
for n in sorted(out, key=lambda k: (out[k]["school"], -(out[k]["base"] or 0))):
    d = out[n]
    if d["base"] is None and not d["area"]:
        continue
    print("%-22s %-13s %-9s %5s %s"
          % (n, d["school"], d["type"], d["base"] if d["base"] else "-",
             "AoE" if d["area"] else ""))
