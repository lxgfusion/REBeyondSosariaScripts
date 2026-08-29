"""
Offline tests for tame_animals.py.
==================================

Run with CPython 3 from the repo root:

    python tests/test_tame_animals.py

Razor Enhanced's API is only available inside the client, but none of it is
touched at import time and the parsing logic is pure Python. So this loads the
real script with the trailing main() call stripped and stub Razor globals
injected, then calls the actual functions - no copied logic to drift out of sync.

Covers the two bugs that made the pack scan silently find nothing:
  * tooltip properties arriving concatenated ("Creature Type: KirinFilled: 24/60")
  * RootContainer reporting the backpack's item serial, not Player.Serial
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "TameAndFill.py")

FAILURES = []


# --------------------------------------------------------------------------
# Stub Razor Enhanced API - only what the tested functions actually touch.
# --------------------------------------------------------------------------

class StubMisc(object):
    def SendMessage(self, *args):
        pass

    def Pause(self, ms):
        pass


class StubPlayer(object):
    Serial = 0x0001A2B3          # a mobile serial
    Backpack = None              # set per-test


class StubItem(object):
    def __init__(self, serial, container, root, name="", item_id=0x2258,
                 props=None):
        self.Serial = serial
        self.Container = container
        self.RootContainer = root
        self.Name = name
        self.ItemID = item_id
        self.Amount = 1
        self._props = props or []


class StubItems(object):
    def __init__(self):
        self.by_serial = {}

    def FindBySerial(self, serial):
        return self.by_serial.get(serial)

    def WaitForProps(self, item, delay):
        pass

    def GetPropStringList(self, item):
        return list(item._props)


class StubMobiles(object):
    """Enough for mob_name(): props never add a name the mobile lacks."""

    def WaitForProps(self, mob, delay):
        pass

    def FindBySerial(self, serial):
        return None

    def SingleClick(self, mob):
        pass

    def GetPropStringList(self, mob):
        return []


def load_script():
    """Exec the real script with main() removed and stubs in place."""
    with open(SCRIPT, encoding="utf-8") as fh:
        source = fh.read()

    # Drop the bottom-of-file invocation so nothing runs on load.
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)

    env = {
        "__name__": "tame_animals_under_test",
        "Misc": StubMisc(),
        "Player": StubPlayer(),
        "Items": StubItems(),
        "Mobiles": StubMobiles(),
        "Journal": None,
        "Target": None,
        "PathFinding": None,
        "Gumps": None,
    }
    exec(compile(source, SCRIPT, "exec"), env)
    return env


def test_peace_messages_are_the_servuo_ones(m):
    """Taken verbatim from ServUO Scripts/Skills/Peacemaking.cs. If a shard
    reworded one the script would read every attempt as a failure, so they are
    pinned rather than paraphrased."""
    check("success", m["PEACE_SUCCESS"],
          "You play hypnotic music, calming your target.")
    check("failure", m["PEACE_FAILED"],
          "You attempt to calm your target, but fail.")
    check("hopeless", m["PEACE_HOPELESS"],
          "You have no chance of calming that creature.")
    check("already calm", m["PEACE_ALREADY"],
          "That creature is already being calmed.")
    check("bad musicianship", m["PEACE_PLAYED_POORLY"],
          "You play poorly, and there is no effect.")
    check("the instrument picker", m["PEACE_PICK_INSTRUMENT"],
          "What instrument shall you play?")
    check("all of them are watched for", len(m["PEACE_ALL"]), 6)


def test_instrument_list_is_real_graphics(m):
    """From ServUO Scripts/Items/Equipment/Instruments. A wrong graphic here
    means find_instrument returns None and the script reports "no instrument"
    while one is sitting in the pack."""
    ids = m["INSTRUMENT_IDS"]
    for name, graphic in (("drums", 0x0E9C), ("tambourine", 0x0E9D),
                          ("harp", 0x0EB1), ("lap harp", 0x0EB2),
                          ("lute", 0x0EB3), ("bamboo flute", 0x2805)):
        check("%s listed" % name, graphic in ids, True)
    check("no duplicates", len(ids), len(set(ids)))


def test_find_instrument_only_looks_in_the_pack(m):
    class It(object):
        def __init__(self, item_id):
            self.ItemID = item_id
            self.Serial = 0x1234

    class Pack(object):
        def __init__(self, contents):
            self.Serial = 0x41D40F58
            self.Contains = contents

    player = m["Player"]
    saved = player.Backpack
    try:
        player.Backpack = None
        check("no backpack at all -> none", m["find_instrument"](), None)

        player.Backpack = Pack([])
        check("empty pack -> none", m["find_instrument"](), None)

        player.Backpack = Pack([It(0x0EED)])       # gold, not an instrument
        check("no instrument -> none", m["find_instrument"](), None)

        player.Backpack = Pack([It(0x0EED), It(0x0EB3)])   # a lute
        found = m["find_instrument"]()
        check("lute found", found is not None and found.ItemID, 0x0EB3)
    finally:
        player.Backpack = saved


def test_only_the_aggressive_get_peaced(m):
    """Unicorns and ki-rin are peaceful - playing at them is wasted time.
    Dragons, drakes and their relatives chew on you for the whole tame."""
    for name in ("dragon", "greater dragon", "frost dragon", "swamp dragon",
                 "dragon wolf", "drake", "cold drake", "stygian drake",
                 "white wyrm", "shadow wyrm", "hiryu", "lesser hiryu"):
        check("%r is aggressive" % name, m["is_aggressive_species"](name), True)
    for name in ("unicorn", "ki-rin", "chicken", "horse", "great hart",
                 "polar bear"):
        check("%r is not" % name, m["is_aggressive_species"](name), False)


def test_aggressive_mode_still_calms_anything_already_swinging(m):
    """The word list is about temperament. Something actually fighting gets
    calmed whatever it is called."""
    class Mob(object):
        def __init__(self, war):
            self.WarMode = war

    saved = (m["PEACE_ENABLED"], m["PEACE_WHEN"])
    try:
        m["PEACE_ENABLED"] = True
        m["PEACE_WHEN"] = "aggressive"
        check("a calm unicorn is left alone",
              m["should_peace"](Mob(False), "unicorn"), False)
        check("a unicorn that is fighting is not",
              m["should_peace"](Mob(True), "unicorn"), True)
        check("a calm dragon is still calmed first",
              m["should_peace"](Mob(False), "greater dragon"), True)
    finally:
        m["PEACE_ENABLED"], m["PEACE_WHEN"] = saved


def test_the_default_is_aggressive_only(m):
    check("default mode", m["PEACE_WHEN"], "aggressive")
    check("dragons listed", "dragon" in m["PEACE_AGGRESSIVE_WORDS"], True)
    check("drakes listed", "drake" in m["PEACE_AGGRESSIVE_WORDS"], True)
    check("wyverns listed", "wyvern" in m["PEACE_AGGRESSIVE_WORDS"], True)


def test_should_peace_honours_the_mode(m):
    class Mob(object):
        def __init__(self, war):
            self.WarMode = war

    saved = (m["PEACE_ENABLED"], m["PEACE_WHEN"])
    try:
        m["PEACE_ENABLED"] = True

        m["PEACE_WHEN"] = "always"
        check("always: a calm animal", m["should_peace"](Mob(False)), True)
        check("always: a fighting one", m["should_peace"](Mob(True)), True)

        m["PEACE_WHEN"] = "fighting"
        check("fighting: not engaged", m["should_peace"](Mob(False)), False)
        check("fighting: engaged", m["should_peace"](Mob(True)), True)

        m["PEACE_WHEN"] = "never"
        check("never: not even a fighting one",
              m["should_peace"](Mob(True)), False)

        m["PEACE_ENABLED"] = False
        m["PEACE_WHEN"] = "always"
        check("disabled beats the mode", m["should_peace"](Mob(True)), False)
    finally:
        m["PEACE_ENABLED"], m["PEACE_WHEN"] = saved


def test_peace_failure_never_blocks_taming(m):
    """The point is to improve the odds on an aggressive, not to gate the run
    behind a bard skill. calm_before_taming returns a plain False and the
    caller tames anyway."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "calm_before_taming":
            fn = node
    check("calm_before_taming exists", fn is not None, True)
    if fn is None:
        return
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    check("it only ever returns a bool",
          all(isinstance(r.value, ast.Constant)
              and isinstance(r.value.value, bool) for r in returns), True)
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.Raise)]
    check("and never raises", raises, [])


def test_peace_clears_the_cursor_on_every_bail(m):
    """A leaked target cursor silently eats the NEXT TargetExecute - which
    here would be the taming attempt itself, so the tame would appear to run
    and never reach the server."""
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "peacemake":
            fn = node
    check("peacemake exists", fn is not None, True)
    if fn is None:
        return
    clears = [n for n in ast.walk(fn)
              if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "clear_cursor"]
    waits = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == "WaitForTarget"]
    check("it clears the cursor", len(clears) >= 3, True)
    check("it waits on a cursor", len(waits) >= 1, True)


class ThreatMob(object):
    def __init__(self, serial, notoriety=3, name="a dragon"):
        self.Serial = serial
        self.Notoriety = notoriety
        self.Name = name


def install_threats(m, mobs, distances):
    """Drive Mobiles.ApplyFilter and Player.DistanceTo from a fixture."""
    class F(object):
        def __init__(self):
            self.Enabled = False
            self.RangeMax = None

    class Mob(object):
        Filter = F

        @staticmethod
        def ApplyFilter(f):
            assert f.RangeMax is not None, "RangeMax must always be set"
            return list(mobs)

        @staticmethod
        def FindBySerial(serial):
            for x in mobs:
                if x.Serial == serial:
                    return x
            return None

        @staticmethod
        def WaitForProps(mob, delay):
            return True

        @staticmethod
        def SingleClick(mob):
            return None

    m["Mobiles"] = Mob
    m["Player"].DistanceTo = staticmethod(lambda mob: distances[mob.Serial])


def test_grey_alone_is_not_a_threat(m):
    """THE POINT. Every wild animal is grey, including the one being tamed.
    Something standing still is scenery however grey it is."""
    m["forget_threats"]()
    dragon = ThreatMob(0xA1)
    install_threats(m, [dragon], {0xA1: 6})

    check("first sighting is only recorded", m["closing_threats"](), [])
    check("still at 6 tiles - not closing", m["closing_threats"](), [])


def test_closing_in_is_what_makes_it_a_threat(m):
    m["forget_threats"]()
    dragon = ThreatMob(0xA1)
    distances = {0xA1: 8}
    install_threats(m, [dragon], distances)

    check("first sighting", m["closing_threats"](), [])
    distances[0xA1] = 5
    coming = m["closing_threats"]()
    check("it closed 8 -> 5", len(coming), 1)
    check("and it is the right creature", coming[0][0].Serial, 0xA1)


def test_moving_away_is_never_a_threat(m):
    m["forget_threats"]()
    boar = ThreatMob(0xB2, name="a boar")
    distances = {0xB2: 3}
    install_threats(m, [boar], distances)
    m["closing_threats"]()
    distances[0xB2] = 7
    check("walking off is not an attack", m["closing_threats"](), [])


def test_the_creature_being_tamed_is_never_a_threat(m):
    """It is grey, it is adjacent, and taming keeps you next to it - so it
    looks exactly like something attacking you. Excluding it by serial is the
    whole reason colour cannot be trusted on its own."""
    m["forget_threats"]()
    target = ThreatMob(0xC3, name="a dragon")
    distances = {0xC3: 6}
    install_threats(m, [target], distances)

    m["closing_threats"](exclude_serial=0xC3)
    distances[0xC3] = 1
    check("closing right onto you, still ignored",
          m["closing_threats"](exclude_serial=0xC3), [])

    # Without the exclusion the very same movement IS a threat.
    m["forget_threats"]()
    distances[0xC3] = 6
    m["closing_threats"]()
    distances[0xC3] = 1
    check("and it would have been picked up otherwise",
          len(m["closing_threats"]()), 1)


def test_friendly_notoriety_is_ignored(m):
    m["forget_threats"]()
    blue = ThreatMob(0xD4, notoriety=1, name="a townsperson")
    distances = {0xD4: 9}
    install_threats(m, [blue], distances)
    m["closing_threats"]()
    distances[0xD4] = 2
    check("an innocent charging you is not a threat",
          m["closing_threats"](), [])


def test_never_words_win(m):
    m["forget_threats"]()
    pet = ThreatMob(0xE5, name="Fluffy the hellhound")
    distances = {0xE5: 9}
    saved = list(m["THREAT_NEVER_WORDS"])
    try:
        m["THREAT_NEVER_WORDS"][:] = ["fluffy"]
        install_threats(m, [pet], distances)
        m["closing_threats"]()
        distances[0xE5] = 2
        check("named exception is never a threat", m["closing_threats"](), [])
    finally:
        m["THREAT_NEVER_WORDS"][:] = saved


def test_out_of_range_history_is_forgotten(m):
    """Otherwise a creature that left at 2 tiles and came back at 9 would read
    as having closed 2 -> 9, or worse, a stale entry would linger forever."""
    m["forget_threats"]()
    mob = ThreatMob(0xF6)
    distances = {0xF6: 4}
    install_threats(m, [mob], distances)
    m["closing_threats"]()
    check("it is remembered", 0xF6 in m["_threat_distance"], True)

    install_threats(m, [], {})
    m["closing_threats"]()
    check("gone from range, gone from memory",
          0xF6 in m["_threat_distance"], False)


def test_nothing_is_attacked_yet(m):
    """Detection ships before the attack on purpose - naming the wrong
    creature is cheap, shooting it is not."""
    check("attacking is off", m["THREAT_ATTACK"], False)
    import ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    attacks = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute)
               and n.func.attr in ("Attack", "SetWarMode")
               and getattr(n.func.value, "id", "") == "Player"]
    # SetWarMode(False) at startup is fine; an Attack call is not.
    calls = [n for n in attacks if n.func.attr == "Attack"]
    check("nothing calls Player.Attack", calls, [])


def test_resistances_came_from_servuo_not_a_wiki(m):
    """Spot values against ServUO Scripts/Mobiles. Midpoints of the declared
    ranges, because every creature rolls its own within them."""
    hiryu = m["species_resistances"]("hiryu")
    check("hiryu physical", hiryu["physical"], 62)     # 55-70
    check("hiryu fire", hiryu["fire"], 80)             # 70-90
    check("hiryu cold", hiryu["cold"], 20)             # 15-25
    check("hiryu energy", hiryu["energy"], 45)         # 40-50

    lesser = m["species_resistances"]("lesser hiryu")
    check("lesser hiryu cold", lesser["cold"], 10)


def test_zero_is_a_real_resistance_not_missing_data(m):
    """ServUO only calls SetResistance for what a creature actually resists.
    An extractor that required all five silently dropped every low-level
    animal - a chicken declares Physical and nothing else."""
    chicken = m["species_resistances"]("chicken")
    check("chicken is in the table", chicken is not None, True)
    if chicken:
        check("physical is set", chicken["physical"] > 0, True)
        check("cold is a real zero", chicken["cold"], 0)


def test_weakest_is_chosen_from_what_you_can_cast(m):
    """A dragon's absolute lowest is POISON. Nothing in SPELL_TABLE delivers
    poison - Poison Strike's damage is not a plain GetNewAosDamage call, so it
    was left out rather than guessed at - and picking a type you cannot cast
    would choose a spell you do not have."""
    dragon = m["species_resistances"]("dragon")
    check("poison really is its lowest",
          min(dragon, key=lambda k: dragon[k]), "poison")

    deliverable = set(kind for _n, _s, kind, _b in m["usable_spells"]())
    check("but poison is not deliverable", "poison" in deliverable, False)
    check("so the reported weakness is one we can use",
          m["weakest_damage_type"]("dragon") in deliverable, True)
    check("and the chosen spell is real",
          m["best_spell_against"]("dragon")[0] in
          [row[0] for row in m["SPELL_TABLE"]], True)


def test_known_weaknesses(m):
    check("white wyrm burns", m["weakest_damage_type"]("white wyrm"), "fire")
    check("hiryu feels the cold", m["weakest_damage_type"]("hiryu"), "cold")
    check("lesser hiryu too", m["weakest_damage_type"]("lesser hiryu"), "cold")
    check("drake takes energy", m["weakest_damage_type"]("drake"), "energy")


def test_an_unknown_creature_is_not_guessed_at(m):
    check("no row -> no answer",
          m["weakest_damage_type"]("something that does not exist"), None)
    check("and no resistances either",
          m["species_resistances"]("something that does not exist"), None)


def test_punctuation_does_not_break_the_lookup(m):
    """The catalogue says "ki-rin"; a creature may call itself "Ki Rin"."""
    check("ki-rin", m["species_resistances"]("ki-rin") is not None, True)
    check("ki rin", m["species_resistances"]("Ki Rin") is not None, True)
    check("kirin", m["species_resistances"]("kirin") is not None, True)


def test_lesser_hiryu_is_kill_on_sight_and_hiryu_is_not(m):
    """There is no taming order for a lesser hiryu - the catalogue has `hiryu`
    and not `lesser hiryu`, which is the same fact from the other side."""
    check("lesser hiryu is cleared", m["is_kill_on_sight"]("lesser hiryu"), True)
    check("hiryu is tamed, not killed", m["is_kill_on_sight"]("hiryu"), False)

    species = [row[0] for row in m["ANIMAL_CATALOGUE"]]
    check("hiryu is tameable", "hiryu" in species, True)
    check("lesser hiryu is not", "lesser hiryu" in species, False)


def test_substring_ordering_trap(m):
    """"lesser hiryu" CONTAINS "hiryu". Anything asking both questions has to
    ask kill-on-sight first, or a lesser hiryu reads as a tameable hiryu."""
    check("the trap is real", "hiryu" in "lesser hiryu", True)
    check("kill list catches it first",
          m["is_kill_on_sight"]("a lesser hiryu"), True)


def test_hiryu_is_peaced_before_taming(m):
    check("hiryu counts as aggressive", m["is_aggressive_species"]("hiryu"), True)
    check("listed by word", "hiryu" in m["PEACE_AGGRESSIVE_WORDS"], True)


def test_the_spell_choice_beats_naive_lowest_resistance(m):
    """THE WHOLE POINT of weighing damage. A hiryu resists cold 20 and energy
    45, so "lowest resistance" says Harm - but Harm is base 17 against Energy
    Bolt's 40, so the bolt lands 22 where Harm lands 13.6. The bolt wins, which
    is what actually happens in game."""
    check("naive answer is cold", m["weakest_damage_type"]("hiryu"), "cold")
    best = m["best_spell_against"]("hiryu")
    check("but the chosen spell is Energy Bolt", best[0], "Energy Bolt")
    check("which is energy, not cold", best[2], "energy")
    check("and it lands harder", round(best[3], 1), 22.0)
    check("Harm would land less",
          round(m["expected_damage"](17, 20), 1) < round(best[3], 1), True)


def test_expected_damage_maths(m):
    check("no resistance", m["expected_damage"](40, 0), 40.0)
    check("half resisted", m["expected_damage"](40, 50), 20.0)
    check("fully resisted", m["expected_damage"](40, 100), 0.0)
    check("over-resisted never goes negative",
          m["expected_damage"](40, 150), 0.0)


def test_only_schools_you_have_are_used(m):
    saved = list(m["AVAILABLE_SCHOOLS"])
    try:
        m["AVAILABLE_SCHOOLS"][:] = ["magery"]
        for spell, school, _t, _b in m["usable_spells"]():
            check("%s is magery" % spell, school, "magery")

        m["AVAILABLE_SCHOOLS"][:] = ["mysticism"]
        names = [sp for sp, _s, _t, _b in m["usable_spells"]()]
        check("Bombard is available", "Bombard" in names, True)
        check("Energy Bolt is not", "Energy Bolt" in names, False)

        m["AVAILABLE_SCHOOLS"][:] = []
        check("no schools -> no spells", m["usable_spells"](), [])
        check("and no choice can be made",
              m["best_spell_against"]("hiryu"), None)
    finally:
        m["AVAILABLE_SCHOOLS"][:] = saved


def test_area_spells_are_off_by_default(m):
    """They hit everything nearby, which during a tame includes your target."""
    check("area is off", m["ALLOW_AREA_SPELLS"], False)
    names = [sp for sp, _s, _t, _b in m["usable_spells"]()]
    for area_spell in ("Chain Lightning", "Meteor Swarm", "Hail Storm"):
        check("%s excluded" % area_spell, area_spell in names, False)
    allowed = [sp for sp, _s, _t, _b in m["usable_spells"](allow_area=True)]
    check("but available when asked for",
          "Chain Lightning" in allowed, True)


def test_wildfire_is_spellweaving(m):
    """Checked in ServUO: Scripts/Spells/Spellweaving/Wildfire.cs. Casting it
    as Mysticism simply fails. It is absent from SPELL_TABLE because its damage
    is not a plain GetNewAosDamage call - measured, not guessed."""
    names = [row[0] for row in m["SPELL_TABLE"]]
    check("not in the table", "Wildfire" in names, False)
    src = open(SCRIPT, encoding="utf-8").read()
    check("and the file says where it lives",
          "WILDFIRE IS SPELLWEAVING" in src, True)


def test_every_table_spell_has_a_real_damage_type(m):
    valid = {"physical", "fire", "cold", "poison", "energy"}
    for name, school, kind, base, area in m["SPELL_TABLE"]:
        check("%s type" % name, kind in valid, True)
        check("%s has base damage" % name, base > 0, True)
        check("%s school is one we know" % name,
              school in ("magery", "necromancy", "spellweaving", "mysticism"),
              True)


def test_unknown_creature_gets_no_spell_choice(m):
    check("no data, no choice",
          m["best_spell_against"]("something imaginary"), None)


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-46s got=%-22r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_species_matching(m):
    """Longest-name-first, punctuation-tolerant, boundary-anchored."""
    cases = [
        ("a taming order deed for a unicorn",      "unicorn"),
        ("Taming Order: Ki-Rin",                   "ki-rin"),
        ("taming order: kirin",                    "ki-rin"),
        ("Taming Order: Ki Rin",                   "ki-rin"),
        ("a resource order deed (hell cat)",       "hell cat"),
        ("a resource order deed (cat)",            "cat"),
        ("order deed: dread warhorse",             "dread warhorse"),
        ("order deed: nightmare",                  "nightmare"),
        ("order deed: greater dragon",             "greater dragon"),
        ("order deed: dragon",                     "dragon"),
        ("order deed: saber-toothed tiger",        "saber-toothed tiger"),
        ("order deed: sabertoothed tiger",         "saber-toothed tiger"),
        ("order deed: pack llama",                 "pack llama"),
        ("order deed: llama",                      "llama"),
        ("order deed: sewer rat",                  "sewer rat"),
        ("order deed: rat",                        "rat"),
        # Must not false-positive:
        ("a greater healing potion",               None),
        ("an order deed for iron ingots",          None),
        ("a scroll of alacrity: animal taming",    None),
        ("a decorative rating plaque",             None),
    ]
    for text, want in cases:
        species = m["match_species"](text)
        check("match_species %r" % text[:34],
              species["name"] if species else None, want)


def test_real_deed(m):
    """The exact tooltip from the Enhanced Item Inspector screenshot."""
    lines = [
        "A Taming Order",
        "Weight: 1 Stone",
        "Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:",
    ]
    text = m["split_runtogether"](" ".join(["A Taming Order"] + lines)).lower()
    print("\nparsed: %s\n" % text)

    check("real deed passes hint check", m["looks_like_deed"](text), True)
    species = m["species_from_deed"](text)
    check("real deed species", species["name"] if species else None, "ki-rin")
    check("real deed progress", m["deed_progress"](text), (24, 60))
    check("real deed field read",
          m["field_value"](text, "creature type"), "kirin")

    # Regression: without de-concatenating, ki-rin is invisible. This is the
    # bug the screenshot exposed.
    raw = " ".join(["A Taming Order"] + lines).lower()
    check("regression: concatenated text unmatched",
          m["match_species"](raw), None)


def test_concatenated_species(m):
    for creature, want in [
        ("Unicorn", "unicorn"),
        ("GreatHart", "great hart"),
        ("DreadWarhorse", "dread warhorse"),
        ("Nightmare", "nightmare"),
        ("CuSidhe", "cu sidhe"),
        ("Hiryu", "hiryu"),
        ("SwampDragon", "swamp dragon"),
    ]:
        raw = ("A Taming Order Weight: 1 Stone "
               "Level: 2Creature Type: %sFilled: 3/60Gold: 100%%" % creature)
        text = m["split_runtogether"](raw).lower()
        species = m["species_from_deed"](text)
        check("concatenated %s" % creature,
              species["name"] if species else None, want)


def test_progress(m):
    full = m["split_runtogether"](
        "A Taming Order Level: 2Creature Type: KirinFilled: 60/60Gold: 100%").lower()
    progress = m["deed_progress"](full)
    check("full deed progress", progress, (60, 60))
    check("full deed detected", progress[0] >= progress[1], True)

    none = m["split_runtogether"]("A Taming Order Creature Type: Kirin").lower()
    check("progress absent", m["deed_progress"](none), None)


def test_is_held(m):
    """RootContainer reports the backpack item serial, not Player.Serial."""
    backpack_serial = 0x41D40F58          # from the screenshot
    player_serial = m["Player"].Serial

    m["Player"].Backpack = StubItem(backpack_serial, player_serial,
                                    player_serial, "Backpack")

    # The real deed: Container == RootContainer == backpack serial.
    deed = StubItem(0x4302A461, backpack_serial, backpack_serial,
                    "A Taming Order")
    check("deed in backpack is held", m["is_held"](deed), True)

    # An item whose root is the player mobile (other shards report this).
    other = StubItem(0x4302A462, backpack_serial, player_serial, "thing")
    check("root=player is held", m["is_held"](other), True)

    # Item in a sub-bag: root stops at the bag, chain must be walked.
    bag_serial = 0x41D40F99
    m["Items"].by_serial[bag_serial] = StubItem(bag_serial, backpack_serial,
                                               bag_serial, "a bag")
    nested = StubItem(0x4302A463, bag_serial, bag_serial, "A Taming Order")
    check("deed in sub-bag is held", m["is_held"](nested), True)

    # Something on the ground in a stranger's container is not held.
    world = StubItem(0x4302A464, 0x50000000, 0x50000000, "someone else's")
    check("foreign container not held", m["is_held"](world), False)

    # Regression: the old test would have rejected the real deed outright.
    check("regression: old RootContainer test fails",
          deed.RootContainer == player_serial, False)


class FakeMob(object):
    def __init__(self, name, body, serial=0x1000):
        self.Name = name
        self.Body = body
        self.Serial = serial


def arm_species(m, names):
    """Pretend we hold a deed for each of `names`."""
    m["build_species"]()
    m["_active"].clear()
    m["_body_owners"].clear()
    for key in names:
        species = m["_species"][key]
        m["_active"][key] = {"species": species, "deed": 0x1234}
        for body in species["bodies"]:
            m["_body_owners"].setdefault(body, []).append(key)


def test_zombie_regression(m):
    """The reported bug: hunting animals, the script targeted zombies.

    Cause was a bad catalogue entry - ServUO's Sheep.cs has
    `return (Body == 0xCF ? 3 : 0);` and the extractor read that `==` as an
    assignment, so body 3 (the ZOMBIE body) ended up listed as a sheep.
    """
    catalogue = m["ANIMAL_CATALOGUE"]

    holders = [n for n, bodies, _s in catalogue if 3 in bodies]
    check("nothing claims body 3 (zombie)", holders, [])
    sheep = [b for n, b, _s in catalogue if n == "sheep"][0]
    check("sheep bodies are correct", [hex(b) for b in sheep],
          ["0xcf", "0xdf"])

    # Even if a bad body slipped in, the name must stop it being targeted.
    arm_species(m, ["sheep"])
    m["_body_owners"].setdefault(3, []).append("sheep")   # re-inject the bug
    zombie = FakeMob("a zombie", 3)
    check("a zombie is not identified as prey", m["identify"](zombie), None)

    real_sheep = FakeMob("a sheep", 0xCF)
    got = m["identify"](real_sheep)
    check("a real sheep still is", got["name"] if got else None, "sheep")


def test_name_decides_not_body(m):
    arm_species(m, ["boar"])
    boar_body = m["_species"]["boar"]["bodies"][0]

    good = FakeMob("a boar", boar_body)
    got = m["identify"](good)
    check("boar by name and body", got["name"] if got else None, "boar")

    # Right body, wrong creature - the shard reused the graphic.
    impostor = FakeMob("a zombie", boar_body)
    check("right body but wrong name is refused",
          m["identify"](impostor), None)

    # Right name, wrong body - distrust that too.
    wrong_body = FakeMob("a boar", 0x999)
    check("unknown body is not scanned for", m["identify"](wrong_body), None)

    # A species we hold no deed for.
    arm_species(m, ["boar"])
    check("no deed means no interest",
          m["identify"](FakeMob("a unicorn", 0x7A)), None)

    # Unreadable name must be skipped while REQUIRE_NAME_MATCH is on.
    check("REQUIRE_NAME_MATCH defaults on", m["REQUIRE_NAME_MATCH"], True)
    check("nameless creature is left alone",
          m["identify"](FakeMob("", boar_body)), None)


def test_never_tame_words(m):
    for name in ["a zombie", "a skeletal dragon", "an ancient lich",
                 "a bone knight", "a fire elemental", "an orc brute",
                 "a Terathan warrior", "a ratman archer"]:
        check("blocked: %s" % name, bool(m["is_never_tameable"](name)), True)

    for name in ["a boar", "a unicorn", "a great hart", "a dire wolf",
                 "a hell cat", "a polar bear"]:
        check("allowed: %s" % name, m["is_never_tameable"](name), None)

    # No catalogue species may collide with the blocklist.
    clashes = [n for n, _b, _s in m["ANIMAL_CATALOGUE"]
               if m["is_never_tameable"](n)]
    check("no tameable species is blocklisted", clashes, [])


def test_catalogue_invariants(m):
    catalogue = m["ANIMAL_CATALOGUE"]
    ambiguous = m["AMBIGUOUS_BODIES"]
    names = {n for n, _b, _s in catalogue}

    check("catalogue size", len(catalogue), 112)

    for body, contenders in ambiguous.items():
        for name in contenders:
            if name not in names:
                check("ambiguous 0x%X names known species" % body, name, "known")

    owners = {}
    for name, bodies, _skill in catalogue:
        for body in bodies:
            owners.setdefault(body, []).append(name)
    unlisted = sorted(b for b, who in owners.items()
                      if len(who) > 1 and b not in ambiguous)
    check("every shared body is in AMBIGUOUS_BODIES", unlisted, [])

    # Nightmare and dread warhorse really do collide - the case that motivated
    # name verification.
    check("0x74 shared", sorted(owners[0x74]), ["dread warhorse", "nightmare"])


def main():
    module = load_script()
    module["build_species"]()          # populates the name patterns

    test_species_matching(module)
    test_the_spell_choice_beats_naive_lowest_resistance(module)
    test_expected_damage_maths(module)
    test_only_schools_you_have_are_used(module)
    test_area_spells_are_off_by_default(module)
    test_wildfire_is_spellweaving(module)
    test_every_table_spell_has_a_real_damage_type(module)
    test_unknown_creature_gets_no_spell_choice(module)
    test_resistances_came_from_servuo_not_a_wiki(module)
    test_zero_is_a_real_resistance_not_missing_data(module)
    test_weakest_is_chosen_from_what_you_can_cast(module)
    test_known_weaknesses(module)
    test_an_unknown_creature_is_not_guessed_at(module)
    test_punctuation_does_not_break_the_lookup(module)
    test_lesser_hiryu_is_kill_on_sight_and_hiryu_is_not(module)
    test_substring_ordering_trap(module)
    test_hiryu_is_peaced_before_taming(module)
    test_grey_alone_is_not_a_threat(module)
    test_closing_in_is_what_makes_it_a_threat(module)
    test_moving_away_is_never_a_threat(module)
    test_the_creature_being_tamed_is_never_a_threat(module)
    test_friendly_notoriety_is_ignored(module)
    test_never_words_win(module)
    test_out_of_range_history_is_forgotten(module)
    test_nothing_is_attacked_yet(module)
    test_peace_messages_are_the_servuo_ones(module)
    test_instrument_list_is_real_graphics(module)
    test_find_instrument_only_looks_in_the_pack(module)
    test_should_peace_honours_the_mode(module)
    test_only_the_aggressive_get_peaced(module)
    test_aggressive_mode_still_calms_anything_already_swinging(module)
    test_the_default_is_aggressive_only(module)
    test_peace_failure_never_blocks_taming(module)
    test_peace_clears_the_cursor_on_every_bail(module)
    test_real_deed(module)
    test_concatenated_species(module)
    test_progress(module)
    test_is_held(module)
    test_zombie_regression(module)
    test_name_decides_not_body(module)
    test_never_tame_words(module)
    test_catalogue_invariants(module)

    print()
    if FAILURES:
        print("FAILED (%d):" % len(FAILURES))
        for name in FAILURES:
            print("  -", name)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
