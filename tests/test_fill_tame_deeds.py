"""
Offline tests for FillTameDeeds.py.
==================================

Run with CPython 3 from the repo root:

    python tests/test_fill_tame_deeds.py

Same approach as test_tame_animals.py: the real script is exec'd with the
trailing main() stripped and stub Razor globals injected, and the real
functions are called. The taming half is TameAndFill's and is covered there;
this covers what is new - who gets killed, with what, paragons, and the
Account Runebook walk.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "FillTameDeeds.py")

FAILURES = []


def check(label, got, want):
    if got != want:
        FAILURES.append("%s: got %r, want %r" % (label, got, want))


# --------------------------------------------------------------------------
# Stubs
# --------------------------------------------------------------------------

class StubMisc(object):
    def __init__(self):
        self.ignored = []

    def SendMessage(self, *args):
        pass

    def Pause(self, ms):
        pass

    def IgnoreObject(self, serial):
        self.ignored.append(serial)


class StubPlayer(object):
    Serial = 0x0001A2B3
    Backpack = None
    Hits = 100
    HitsMax = 100
    Mana = 100


class Mob(object):
    def __init__(self, serial, name, notoriety=3, body=0x17, props=None,
                 human=False, color=0, hits=25, hits_max=25):
        self.Serial = serial
        self.Name = name
        self.Notoriety = notoriety
        self.Body = body
        self.IsHuman = human
        self.IsGhost = False
        self.Color = color
        self.Hits = hits
        self.HitsMax = hits_max
        self._props = props or []


class StubMobiles(object):
    def __init__(self):
        self.by_serial = {}

    def WaitForProps(self, mob, delay):
        pass

    def WaitForStats(self, serial, delay):
        pass

    def FindBySerial(self, serial):
        return self.by_serial.get(serial)

    def SingleClick(self, mob):
        pass

    def GetPropStringList(self, mob):
        return list(mob._props)


class StubGumps(object):
    def __init__(self):
        self.lines = []
        self.layout = ""

    def HasGump(self, gid):
        return True

    def GetLineList(self, gid, data_only=False):
        return list(self.lines)

    def GetGumpRawLayout(self, gid):
        return self.layout


def load_script():
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    env = {
        "__name__": "fill_tame_deeds_under_test",
        "Misc": StubMisc(),
        "Player": StubPlayer(),
        "Items": None,
        "Mobiles": StubMobiles(),
        "Journal": None,
        "Target": None,
        "PathFinding": None,
        "Gumps": StubGumps(),
        "Spells": None,
    }
    exec(compile(source, SCRIPT, "exec"), env)
    return env


def hold_deeds(m, *names):
    """Pretend the pack holds unfilled deeds for these species."""
    m["_active"].clear()
    for name in names:
        m["_active"][name] = {"species": m["_species"][name], "deed": 1}
    m["_hostile_verdict"].clear()


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_no_harvest_left(m):
    with open(SCRIPT, encoding="utf-8") as fh:
        text = fh.read()
    check("no HARVEST_ config or code", "HARVEST_" in text, False)
    check("no dagger/carving", "find_dagger" in text, False)
    check("banner names this script", "FillTameDeeds v%s" in text, True)


def test_tables_are_sane(m):
    bodies = m["HOSTILE_BODIES"]
    for human in (0x190, 0x191, 0x25D, 0x25E, 0x29A, 0x29B):
        check("player body 0x%X is not a kill body" % human,
              human in bodies, False)
    check("orc body is there", bodies.get(0x11, ("", 0))[0], "orc")
    check("daemon body is there (below 0x10)", bodies.get(0x9, ("", 0))[0],
          "daemon")
    hits = m["HOSTILE_HITS"]
    for passive in ("swamp dragon", "grey wolf", "timber wolf", "cow",
                    "white wolf", "hind", "horse"):
        check("%s is not hostile" % passive, passive in hits, False)
    for hostile in ("harpy", "ettin", "lesser hiryu", "dire wolf", "troll"):
        check("%s is hostile" % hostile, hostile in hits, True)


def test_longest_name_decides(m):
    hold_deeds(m)
    hb = m["hostile_by_name"]
    check("a dragon is hostile", (hb("a dragon") or ("",))[0], "dragon")
    check("a swamp dragon is NOT claimed by 'dragon'", hb("a swamp dragon"),
          None)
    check("frost troll beats troll", (hb("a frost troll") or ("",))[0],
          "frost troll")
    check("lesser hiryu, not hiryu", (hb("a lesser hiryu") or ("",))[0],
          "lesser hiryu")
    check("a grey wolf is passive", hb("a grey wolf"), None)
    check("official-only name, no hits",
          hb("an ophidian warrior"), ("ophidian warrior", None))
    check("UOGuide parenthetical dropped", (hb("a savage") or ("",))[0],
          "savage")


def test_kill_gate(m):
    hold_deeds(m, "dire wolf")
    v = m["hostile_verdict"]
    check("harpy, grey -> killed",
          (v(Mob(1, "a harpy", 3, 0x1E)) or ("",))[0], "harpy")
    check("blue harpy (someone's pet) -> left", v(Mob(2, "a harpy", 1)), None)
    check("green -> left", v(Mob(3, "an ettin", 2)), None)
    check("dire wolf with a deed held -> quarry, left",
          v(Mob(4, "a dire wolf", 3, 0x17)), None)
    check("tooltip says tame -> left",
          v(Mob(5, "a harpy", 3, 0x1E, props=["a harpy", "(tame)"])), None)
    check("grey human player named Troll -> left",
          v(Mob(6, "Troll", 3, 0x190, human=True)), None)
    check("red brigand -> killed",
          (v(Mob(7, "a brigand", 6, 0x190, human=True)) or ("",))[0],
          "brigand")
    check("random-named orc, red, by body",
          (v(Mob(8, "Grak", 6, 0x11)) or ("",))[0], "orc")
    check("random-named orc body but grey -> left (body alone is not enough)",
          v(Mob(9, "Grak", 3, 0x11)), None)
    check("a passive hind -> left", v(Mob(10, "a hind", 3, 0xED)), None)


def test_paragons(m):
    hold_deeds(m, "dire wolf", "hind")
    v = m["hostile_verdict"]
    para = ["a harpy", "(Paragon)"]
    got = v(Mob(20, "a harpy", 3, 0x1E, props=para))
    check("hostile paragon is killed", got is not None, True)
    check("...and sized x5", got and got[1],
          m["HOSTILE_HITS"]["harpy"] * m["PARAGON_HITS_MULT"])
    # 65 x5 = 325 is still under the shard's 500, so an arrow does it.
    check("...a harpy paragon is still an arrow job",
          m["pick_spell"](got[1])[0], m["SPELL_SMALL"])
    big = v(Mob(26, "a dragon", 3, 0x3B, props=["a dragon", "(Paragon)"]))
    check("a dragon paragon (486 x5) gets the big spell",
          m["pick_spell"](big[1])[0], m["SPELL_BIG"])
    check("paragon by hue alone",
          v(Mob(21, "a harpy", 3, 0x1E, color=0x501)) is not None, True)
    check("paragon of a passive species -> ignored",
          v(Mob(22, "a hind", 3, 0xED, props=["a hind", "(Paragon)"])), None)
    check("paragon dire wolf (a deed species) is NOT quarry - killed",
          v(Mob(23, "a dire wolf", 3, 0x17,
                props=["a dire wolf", "(Paragon)"])) is not None, True)

    # identify() must never hand a paragon to the tamer.
    m["_body_owners"].clear()
    m["_body_owners"][0x17] = ["dire wolf"]
    check("normal dire wolf is tameable",
          (m["identify"](Mob(24, "a dire wolf", 3, 0x17)) or {}).get("name"),
          "dire wolf")
    check("paragon dire wolf is not",
          m["identify"](Mob(25, "a dire wolf", 3, 0x17,
                            props=["a dire wolf", "(Paragon)"])), None)


def test_spell_choice(m):
    ps = m["pick_spell"]
    # The line is 500 on this shard: 3,467 Spell Damage Increase makes a
    # Magic Arrow enough for anything under it (user, 2026-10-25).
    check("the shard's line is 500", m["SPELL_BIG_HITS"], 500)
    check("orc-sized -> Magic Arrow", ps(65)[0], "Magic Arrow")
    check("dragon (486) -> Magic Arrow on this shard", ps(486)[0],
          "Magic Arrow")
    check("one under the line -> Magic Arrow", ps(499)[0], "Magic Arrow")
    check("at the line -> Energy Bolt", ps(500)[0], "Energy Bolt")
    check("ogre lord (514) -> Energy Bolt", ps(514)[0], "Energy Bolt")
    check("unknown -> Energy Bolt", ps(None)[0], "Energy Bolt")


def test_kill_upgrades_a_stubborn_arrow_fight(m):
    """Four Magic Arrows and still above 60% -> it was bigger than the table
    said; the rest of the fight is Energy Bolts."""
    casts = []
    mob = Mob(30, "an ettin", 3, 0x12, hits=24, hits_max=25)
    m["Mobiles"].by_serial[30] = mob
    m["approach"] = lambda *a, **k: True
    m["clear_cursor"] = lambda: True
    m["Player"].DistanceTo = staticmethod(lambda target: 3)

    def fake_cast(serial, spell, school):
        casts.append(spell)
        if len(casts) >= 7:
            del m["Mobiles"].by_serial[30]       # dies
        return True
    m["cast_at"] = fake_cast
    out = m["kill"](30, "ettin", 90)
    check("fight ends dead", out, "dead")
    check("first four are arrows", casts[:4], ["Magic Arrow"] * 4)
    check("then bolts", set(casts[4:]), set(["Energy Bolt"]))


def test_kill_escapes_when_hurt(m):
    mob = Mob(31, "an ettin", 3, 0x12)
    m["Mobiles"].by_serial[31] = mob
    m["Player"].Hits = 20
    try:
        check("low health -> escape", m["kill"](31, "ettin", 90), "escape")
    finally:
        m["Player"].Hits = 100


def test_runebook_page_pairing(m):
    """Folder page with three buttons per rune - recall, gate, DELETE. The
    delete button (+60000) must never be paired as an entry."""
    g = m["Gumps"]
    g.lines = [
        "<CENTER>Account Runebook</CENTER>", "FillTameDeeds", "New Rune",
        "New Runebook", "Organize",
        "1. Dire Wolves (Felucca)", "(1200, 300, 0)",
        "2. Hiryu Spot", "(2300, 400, 5)",
        "<BASEFONT>Page 1/1",
    ]
    def b(i):
        return "{ button 10 10 1 2 1 0 %d }" % i
    g.layout = "".join(b(i) for i in (1, 2, 3, 5, 10, 11, 30010, 30011,
                                      60010, 60011))
    folders, runes = m["parse_ar_page"](ensure_open=False)
    check("no folders here", folders, {})
    check("two runes on 10 and 11", sorted(runes), [10, 11])
    check("names", runes[10]["name"], "Dire Wolves (Felucca)")
    check("coords", runes[11]["coord"], [2300, 400, 5])
    check("page footer", m["ar_page_info"](), (1, 1))


def test_root_folder_is_found_by_name(m):
    g = m["Gumps"]
    g.lines = ["1. Trammel", "2. FillTameDeeds", "<BASEFONT>Page 1/1"]
    g.layout = "{ button 1 1 1 1 1 0 10 }{ button 1 1 1 1 1 0 11 }"
    folders, runes = m["parse_ar_page"](ensure_open=False)
    check("both are folders", sorted(folders.values()),
          ["FillTameDeeds", "Trammel"])
    check("the config names it", m["RUNEBOOK_FOLDER"], ["FillTameDeeds"])


def test_every_rune_by_default(m):
    check("empty filter -> visit all", m["wanted_rune"]("Anything at all"),
          True)
    check("truncated name still matches",
          m["wanted_rune"]("Serpents Hold Dire Wo...", ["Dire Wolf"]), True)


def main():
    m = load_script()
    m["build_species"]()
    m["build_hostiles"]()
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn(m)
        except Exception as err:
            FAILURES.append("%s raised %r" % (name, err))
    if FAILURES:
        print("FAILED (%d):" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        return 1
    print("OK - %d tests" % len(tests))
    return 0


if __name__ == "__main__":
    sys.exit(main())
