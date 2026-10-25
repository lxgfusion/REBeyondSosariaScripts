"""Every creature that attacks on sight, with its hit points, from ServUO.

Run from the repo root with a ServUO checkout on hand:

    git clone --depth 1 --filter=blob:none --sparse \\
        https://github.com/ServUO/ServUO.git
    git -C ServUO sparse-checkout set Scripts/Mobiles
    python tools/extract_hostiles.py ServUO

Prints two tables for FillTameDeeds.py: HOSTILE_HITS and HOSTILE_BODIES.

WHY THIS EXISTS. extract_aggressive.py answers "which TAMEABLES bite" - the
peacemaking question. FillTameDeeds also has to answer "what else at this
spawn is going to come for me while I tame", which is mostly NOT tameable:
orcs, harpies, ettins. Same signal, wider net.

THE SIGNAL is the FightMode passed to the base constructor:

    FightMode.Aggressor   fights back only once attacked  -> passive, skipped
    FightMode.None        never fights                    -> skipped
    anything else         attacks unprovoked              -> HOSTILE

HIT POINTS are the midpoint of SetHits(min, max) - the same midpoint rule the
resistance table uses. They decide which spell a creature gets: the client
only sees other mobiles' health as a percentage, so a monster's real size has
to come from the source, not from the game.

THREE WAYS A NAME IS SET, and a first cut of this caught only the first:

    Name = "a harpy";                        a literal - the usual case
    base("a lesser hiryu", 243, ...)         BaseMount takes it as an argument
    Name = NameList.RandomName("orc");       a RANDOM PERSONAL NAME

The third is the trap. An orc in game is called "Grak", a lizardman "Sssik",
a balron "Zorlak" - nothing a name table can match. Those go into
HOSTILE_BODIES instead, keyed by body, and the script only acts on one when
the body AND a murderer-red notoriety agree. Missing them meant the list had
no orcs, lizardmen, ratmen or balrons in it at all.
"""
import os
import re
import sys

PASSIVE_MODES = ("Aggressor", "None")

FIGHTMODE = re.compile(r"FightMode\.(\w+)")
CLASSNAME = re.compile(
    r"public\s+(?:abstract\s+|sealed\s+|partial\s+)*class\s+(\w+)\s*:\s*(\w+)")
NAMEASSIGN = re.compile(r'\bName\s*=\s*"([^"]+)"')
MOUNTNAME = re.compile(r'base\s*\(\s*"([^"]+)"')
RANDOMNAME = re.compile(r'\bName\s*=\s*NameList\.RandomName\s*\(\s*"([^"]+)"')
SETHITS = re.compile(r"SetHits\s*\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\)")
TAMEABLE = re.compile(r"Tamable\s*=\s*true", re.I)
# (?<![=!<>])=(?!=) - see CLAUDE.md: a bare "=" also matches "==", which is
# how body 3 (the zombie) once got into the sheep entry.
BODYASSIGN = re.compile(r"\bBody\s*(?<![=!<>])=(?!=)\s*([^;]+);")
MOUNTBODY = re.compile(r'base\s*\(\s*"[^"]+"\s*,\s*([^,]+),')
NUMBER = re.compile(r"\b(0x[0-9A-Fa-f]+|\d+)\b")

ARTICLE = re.compile(r"^(?:a|an|the)\s+", re.I)

# PLAYER BODIES. Brigands and evil mages draw a random human name on a human
# body - which is the body every PLAYER has too. A body-keyed kill table with
# 0x190 in it is a murder list. Human, elf and gargoyle, both sexes, plus
# their ghosts.
HUMAN_BODIES = set([0x190, 0x191, 0x192, 0x193, 0x25D, 0x25E, 0x25F, 0x260,
                    0x29A, 0x29B, 0x2B6, 0x2B7])

# NameList.RandomName("female") / ("male") is a person's name list, not a
# species - it is what the human-bodied NPCs use.
RANDOM_NAME_NOT_A_SPECIES = set(["female", "male"])


def classes(text):
    """[(class, base, body_text)] - each class's slice of the file."""
    found = list(CLASSNAME.finditer(text))
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append((m.group(1), m.group(2), text[m.start():end]))
    return out


def bodies(body):
    """Every body value a class can take, ternaries and RandomList included."""
    out = set()
    for m in list(BODYASSIGN.finditer(body)) + list(MOUNTBODY.finditer(body)):
        for num in NUMBER.findall(m.group(1)):
            value = int(num, 16) if num.lower().startswith("0x") else int(num)
            # NOT filtered below 0x10 the way the tameable catalogue is. That
            # rule exists because no tameable animal has a body that small;
            # monsters do - a daemon is 9, an earth elemental 14, a zombie 3
            # - and filtering them dropped every random-named daemon.
            if value > 0:
                out.add(value)
    return sorted(out)


def scan(root):
    rows = []
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
            if "FightMode" not in text:
                continue
            for klass, _base, body in classes(text):
                mode = FIGHTMODE.search(body)
                hits = SETHITS.search(body)
                if not (mode and hits):
                    continue
                random_name = RANDOMNAME.search(body)
                name = NAMEASSIGN.search(body) or MOUNTNAME.search(body)
                if random_name:
                    label, is_random = random_name.group(1), True
                elif name:
                    label, is_random = name.group(1), False
                else:
                    continue
                label = label.strip()
                if label.startswith("#") or "{" in label:
                    continue                    # cliloc or formatted - no name
                lo = int(hits.group(1))
                hi = int(hits.group(2) or lo)
                rows.append({
                    "class": klass,
                    "name": ARTICLE.sub("", label).strip().lower(),
                    "random": is_random,
                    "mode": mode.group(1),
                    "hits": (lo + hi) // 2,
                    "bodies": bodies(body),
                    "tameable": bool(TAMEABLE.search(body)),
                })
    return rows


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "ServUO"
    mobiles = os.path.join(root, "Scripts", "Mobiles")
    if not os.path.isdir(mobiles):
        print("No %s - clone ServUO first (see the docstring)." % mobiles)
        return 1

    rows = scan(mobiles)
    hostile = [r for r in rows if r["mode"] not in PASSIVE_MODES]

    # One row per name. Where two classes share a name, keep the BIGGER -
    # over-estimating a monster costs an Energy Bolt's mana, under-estimating
    # it costs the fight.
    by_name = {}
    by_body = {}
    for r in hostile:
        if r["random"]:
            if r["name"] in RANDOM_NAME_NOT_A_SPECIES:
                continue
            for b in r["bodies"]:
                if b in HUMAN_BODIES:
                    continue
                if b not in by_body or r["hits"] > by_body[b]["hits"]:
                    by_body[b] = r
            continue
        if r["name"] not in by_name or r["hits"] > by_name[r["name"]]["hits"]:
            by_name[r["name"]] = r

    print("# %d creature classes scanned, %d hostile: %d named, %d bodies "
          "for random-named ones"
          % (len(rows), len(hostile), len(by_name), len(by_body)))
    print("HOSTILE_HITS = {")
    for name in sorted(by_name):
        r = by_name[name]
        print("    %-30s %5d,%s" % ('"%s":' % name.replace('"', ""), r["hits"],
                                     "   # tameable" if r["tameable"] else ""))
    print("}")
    print()
    print("HOSTILE_BODIES = {")
    for b in sorted(by_body):
        r = by_body[b]
        print('    0x%-4X ("%s", %d),' % (b, r["name"], r["hits"]))
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
