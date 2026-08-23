"""Tests for Scripts/AFK Fisher.py.

Reads the script, strips the .NET imports and the run loop at the bottom, execs
what is left against stub Razor objects and calls the REAL functions - so there
is no copied logic to drift.

    python tests/test_afk_fisher.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "Scripts", "AFK Fisher.py")

# Everything from here down is the run loop, which would never return.
RUN_MARKER = "###   Fishes until you stop the script   ###"

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


class _Stub(object):
    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeItem(object):
    def __init__(self, item_id=0, hue=0, serial=1, name="", amount=1,
                 on_ground=False):
        self.ItemID = item_id
        self.Hue = hue
        self.Serial = serial
        self.Name = name
        self.Amount = amount
        self.OnGround = on_ground


class FakeBackpack(object):
    def __init__(self, contents=None, serial=0x41D40F58):
        self.Contains = list(contents or [])
        self.Serial = serial


class FakeEntry(object):
    def __init__(self, text):
        self.Entry = text


class FakeMisc(_Stub):
    def __init__(self, menu=None, ignored=None):
        self.menu = list(menu or [])
        self.replies = []
        self.messages = []
        # Shared with FakeItems so IgnoreObject actually hides things, the way
        # Razor does when considerIgnoreList is True. Without this the stub
        # cannot tell a working ignore from one that does nothing.
        self.ignored = ignored if ignored is not None else []

    def WaitForContext(self, serial, delay, show=False):
        return [FakeEntry(t) for t in self.menu]

    def ContextReply(self, serial, which):
        self.replies.append((serial, which))

    def SendMessage(self, msg, hue=0, wait=True):
        self.messages.append(msg)

    def IgnoreObject(self, serial):
        self.ignored.append(int(serial))

    def Pause(self, ms):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeItems(_Stub):
    """World and pack in one pool. `cut` names fish that vanish when targeted,
    which is what a successful cut looks like from the script's side."""

    def __init__(self, pool=None, ignored=None):
        self.pool = list(pool or [])
        self.moves = []
        self.used = []
        self.ignored = ignored if ignored is not None else []

    def FindBySerial(self, serial):
        for item in self.pool:
            if int(item.Serial) == int(serial):
                return item
        return None

    def FindAllByID(self, item_id, hue, container, rng, ignore=True):
        out = []
        for item in self.pool:
            if int(item.ItemID) != int(item_id):
                continue
            if int(hue) != -1 and int(item.Hue) != int(hue):
                continue
            if ignore and int(item.Serial) in self.ignored:
                continue
            # container -1 is the world search; anything else is the pack.
            if int(container) == -1:
                out.append(item)
            elif not item.OnGround:
                out.append(item)
        return out

    def UseItem(self, item, *a):
        self.used.append(int(getattr(item, "Serial", item)))

    def Move(self, source, dest, amount):
        self.moves.append((int(source.Serial), amount))
        source.OnGround = False

    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeTarget(_Stub):
    def __init__(self, items=None, cuts_ok=True):
        self.items = items
        self.cuts_ok = cuts_ok
        self.executed = []
        self.cancels = 0

    def Cancel(self):
        self.cancels += 1

    def WaitForTarget(self, delay, noshow=False):
        return True

    def TargetExecute(self, serial):
        self.executed.append(int(serial))
        if self.cuts_ok and self.items is not None:
            # A cut fish leaves the ground.
            for item in list(self.items.pool):
                if int(item.Serial) == int(serial):
                    self.items.pool.remove(item)

    def __getattr__(self, name):
        return lambda *a, **k: None


def load(items=None, misc=None, target=None, backpack=None, weight=100,
         maxweight=500):
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        source = fh.read()
    assert RUN_MARKER in source, "the run-loop marker moved"
    source = source[:source.index(RUN_MARKER)]
    source = re.sub(r"^from System.*$", "", source, flags=re.M)

    player = _Stub()
    player.Backpack = backpack if backpack is not None else FakeBackpack()
    player.IsGhost = False
    player.Weight = weight
    player.MaxWeight = maxweight

    module = {
        "__name__": "afk_fisher",
        "Misc": misc if misc is not None else FakeMisc(),
        "Items": items if items is not None else FakeItems(),
        "Target": target if target is not None else FakeTarget(),
        "Player": player,
        "Spells": _Stub(), "Journal": _Stub(), "Gumps": _Stub(),
        "Mobiles": _Stub(), "Timer": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), module)
    return module


# ---------------------------------------------------------------------------
# The timer is gone
# ---------------------------------------------------------------------------

def test_it_runs_until_stopped(m):
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    run = src[src.index(RUN_MARKER):]
    # Comments legitimately mention the timer to explain why it went. Strip
    # them - what matters is that no CODE still calls it.
    code = " ".join(line.split("#", 1)[0] for line in run.splitlines())
    check("no Timer.Create", "Timer.Create" in code, False)
    check("no Timer.Check", "Timer.Check" in code, False)
    check("the loop is not time-bounded", "while _ready:" in run, True)
    check("and _ready is evaluated once, not per lap",
          "_ready = checkConfig()" in run, True)
    check("but death still ends it", "Player.IsGhost" in run, True)
    check("and the catch is stored on the way out",
          run.rstrip().count("storeFish()") >= 1, True)
    check("and the last fish is cut before it stops",
          "cutFish()" in run, True)


# ---------------------------------------------------------------------------
# The fish-in-the-trash bug
# ---------------------------------------------------------------------------

def test_a_fish_is_never_trashed(m):
    """0x44C3 ships in BOTH the fish list and the junk list, so checkPack
    dragged a fish into the trash whenever the haul key had not taken it."""
    check("0x44C3 is still in fish", 0x44C3 in m["fish"], True)
    check("and still in junk", 0x44C3 in m["junk"], True)

    a_fish = FakeItem(0x44C3, serial=0x101, name="a fish")
    a_boot = FakeItem(0x1711, serial=0x102, name="a boot")
    items = FakeItems(pool=[a_fish, a_boot])
    mod = load(items=items, backpack=FakeBackpack([a_fish, a_boot]))

    mod["checkPack"]()
    moved = [s for s, _a in items.moves]
    check("the boot was binned", 0x102 in moved, True)
    check("the fish was NOT binned", 0x101 in moved, False)


# ---------------------------------------------------------------------------
# Cutting the big fish
# ---------------------------------------------------------------------------

def test_a_big_fish_on_the_floor_is_cut(m):
    """A big fish lands at your feet - Container None, Ground Yes - so only a
    world search finds it."""
    floor = FakeItem(0x09CC, hue=0x0847, serial=0x201, name="a big fish",
                     on_ground=True)
    items = FakeItems(pool=[floor, FakeItem(0x0F52, serial=0x0DA99E12)])
    target = FakeTarget(items=items)
    mod = load(items=items, target=target, backpack=FakeBackpack([]))
    mod["cutFish"]()
    check("the one on the floor was cut", 0x201 in target.executed, True)


def test_a_blue_marlin_in_the_pack_is_cut(m):
    """The marlin is Ground: No, Container: the backpack - 154 stones sitting
    in your pack. An earlier version skipped anything not on the ground, so it
    would never have been touched."""
    marlin = FakeItem(0x4305, hue=0x0000, serial=0x0FA51100,
                      name="blue marlin", on_ground=False)
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    items = FakeItems(pool=[marlin, blade])
    target = FakeTarget(items=items)
    mod = load(items=items, target=target,
               backpack=FakeBackpack([marlin, blade]))
    mod["cutFish"]()
    check("the marlin was cut", 0x0FA51100 in target.executed, True)


def test_an_ordinary_fish_is_left_for_the_haul_key(m):
    """The hue is what separates the 155-stone big fish from a normal one on
    the same graphic. Knifing every 0x09CC would shred the ordinary catch."""
    plain = FakeItem(0x09CC, hue=0x0000, serial=0x203, name="a fish",
                     on_ground=False)   # named "a fish", not "a big fish"
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    items = FakeItems(pool=[plain, blade])
    target = FakeTarget(items=items)
    mod = load(items=items, target=target, backpack=FakeBackpack([plain, blade]))
    mod["cutFish"]()
    check("a plain fish was not cut", 0x203 in target.executed, False)


def test_an_uncut_pack_fish_is_not_looped_on(m):
    """The success test used to be "is it still on the ground". A pack fish is
    never on the ground, so a marlin that refused to cut would have counted as
    cut - and then been found again on the very next pass, forever."""
    marlin = FakeItem(0x4305, hue=0x0000, serial=0x0FA51100,
                      name="blue marlin", on_ground=False)
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    shared = []
    items = FakeItems(pool=[marlin, blade], ignored=shared)
    target = FakeTarget(items=items, cuts_ok=False)   # never disappears
    misc = FakeMisc(ignored=shared)
    mod = load(items=items, misc=misc, target=target,
               backpack=FakeBackpack([marlin, blade]))
    cuts = mod["cutFish"]()
    check("it was not counted as cut", cuts, 0)
    check("it was ignored instead", 0x0FA51100 in misc.ignored, True)
    check("and tried once, not forever", len(target.executed), 1)


def test_the_inspected_cut_list_is_configured(m):
    by_id = dict((c["id"], c) for c in m["cuttable"])
    check("big fish is cuttable", 0x09CC in by_id, True)
    check("blue marlin is cuttable", 0x4305 in by_id, True)
    # Hue must NOT be the discriminator - 0x0847 and 0x058C are both big fish.
    for graphic, spec in by_id.items():
        check("0x%04X is not keyed on hue" % graphic, spec["hue"], -1)
        check("0x%04X decides on a name" % graphic,
              bool(spec.get("names")), True)
    for graphic, spec in by_id.items():
        check("0x%04X says where to look" % graphic,
              spec.get("where") in ("ground", "pack", "both"), True)


def test_the_cursor_is_cancelled_before_every_cut(m):
    """A leaked cursor is answered by the NEXT TargetExecute, so the cut goes
    nowhere and the script cannot tell."""
    floor = FakeItem(0x09CC, hue=0x0847, serial=0x201, name="a big fish",
                     on_ground=True)
    items = FakeItems(pool=[floor, FakeItem(0x0F52, serial=0x0DA99E12)])
    target = FakeTarget(items=items)
    mod = load(items=items, target=target, backpack=FakeBackpack())
    mod["cutFish"]()
    check("it cancelled first", target.cancels >= 1, True)


def test_a_fish_that_will_not_cut_is_ignored_not_retried(m):
    """Otherwise it is the same fish for the rest of the run."""
    stubborn = FakeItem(0x09CC, hue=0x0847, serial=0x201, name="a big fish",
                        on_ground=True)
    items = FakeItems(pool=[stubborn, FakeItem(0x0F52, serial=0x0DA99E12)])
    target = FakeTarget(items=items, cuts_ok=False)   # never leaves the ground
    misc = FakeMisc()
    mod = load(items=items, misc=misc, target=target, backpack=FakeBackpack())

    mod["cutFish"]()
    check("it gave up on that fish", 0x201 in misc.ignored, True)
    check("and did not try it forever",
          len(target.executed) <= m["MAX_CUTS"], True)


def test_no_dagger_is_reported_not_silent(m):
    items = FakeItems(pool=[FakeItem(0x09CC, hue=0x0847, serial=0x201,
                                     on_ground=True)])
    misc = FakeMisc()
    mod = load(items=items, misc=misc, backpack=FakeBackpack())
    check("it cut nothing", mod["cutFish"](), 0)
    check("and said why", "no dagger" in " ".join(misc.messages).lower(), True)


def test_the_dagger_falls_back_to_its_graphic(m):
    """Daggers have durability - this one is 34/34 - so the serial will not
    last forever. The graphic is the fallback."""
    replacement = FakeItem(0x0F52, serial=0x9999, name="dagger")
    items = FakeItems(pool=[replacement])
    mod = load(items=items, backpack=FakeBackpack([replacement]))
    found = mod["findDagger"]()
    check("a replaced dagger is still found", found is not None, True)
    check("and it is the right one", int(found.Serial), 0x9999)


# ---------------------------------------------------------------------------
# Picking the steaks up
# ---------------------------------------------------------------------------

def test_steaks_are_picked_up_off_the_ground(m):
    loose = FakeItem(0x097A, serial=0x301, name="38 raw fish steak",
                     amount=38, on_ground=True)
    items = FakeItems(pool=[loose])
    mod = load(items=items, backpack=FakeBackpack())
    mod["grabSteaks"]()
    check("the steaks were moved", [s for s, _a in items.moves], [0x301])
    check("and the whole stack, not one",
          [a for _s, a in items.moves], [0])


def test_steaks_already_in_the_pack_are_left_alone(m):
    held = FakeItem(0x097A, serial=0x302, amount=38, on_ground=False)
    items = FakeItems(pool=[held])
    mod = load(items=items, backpack=FakeBackpack([held]))
    mod["grabSteaks"]()
    check("nothing was moved", items.moves, [])


def test_being_overweight_does_not_silently_drop_them(m):
    """A steak you are too heavy to lift stays on the floor and sails away
    with the boat. It has to at least try storing first."""
    loose = FakeItem(0x097A, serial=0x301, name="38 raw fish steak",
                     amount=38, on_ground=True)
    items = FakeItems(pool=[loose])
    misc = FakeMisc(menu=["Open", "Add", "Refill from stock"])
    mod = load(items=items, misc=misc, backpack=FakeBackpack(),
               weight=500, maxweight=500)
    mod["grabSteaks"]()
    said = " ".join(misc.messages).lower()
    check("it said it was too heavy", "too heavy" in said, True)
    check("and tried to empty the pack first", len(misc.replies) >= 1, True)


# ---------------------------------------------------------------------------
# Storage keys
# ---------------------------------------------------------------------------

def test_the_real_label_goes_back_not_an_index(m):
    misc = FakeMisc(menu=["Open", "Add", "Refill from stock"])
    mod = load(misc=misc)
    mod["storeKey"](0x07BE5A00, "Treasure Hunter's Storage")
    check("one reply", len(misc.replies), 1)
    check("and it sent the label", misc.replies[0][1], "Refill from stock")


def test_a_reordered_menu_still_works(m):
    misc = FakeMisc(menu=["Refill from stock", "Open", "Add"])
    mod = load(misc=misc)
    mod["storeKey"](0x0AA01000, "Fisherman's Haul")
    check("position did not matter", misc.replies[0][1], "Refill from stock")


def test_it_falls_back_to_index_two(m):
    """The haul key is proven with ContextReply(storage, 2). If no wording is
    recognised, that behaviour has to survive."""
    misc = FakeMisc(menu=["Open", "Add", "Stow everything"])
    mod = load(misc=misc)
    mod["storeKey"](0x0AA01000, "Fisherman's Haul")
    check("it still answered", len(misc.replies), 1)
    check("with the original index", misc.replies[0][1], m["FALLBACK_INDEX"])


def test_the_fallback_refuses_a_dangerous_entry(m):
    """Index 2 is only safe because it happens to be the right entry today. If
    a menu puts Destroy there, clicking it blindly is unrecoverable."""
    misc = FakeMisc(menu=["Open", "Add", "Destroy all contents"])
    mod = load(misc=misc)
    ok = mod["storeKey"](0x07BE5A00, "Treasure Hunter's Storage")
    check("it refused", ok, False)
    check("and sent nothing", misc.replies, [])
    check("and said why",
          "refusing" in " ".join(misc.messages).lower(), True)


def test_both_keys_are_offered_once_each(m):
    misc = FakeMisc(menu=["Open", "Add", "Refill from stock"])
    mod = load(misc=misc)
    # The published copy ships these zeroed, so the test supplies them.
    mod["storage"] = 0x0AA01000
    mod["treasure"] = 0x07BE5A00
    mod["storeFish"]()
    serials = [s for s, _l in misc.replies]
    check("the haul key once", serials.count(0x0AA01000), 1)
    check("the treasure storage once", serials.count(0x07BE5A00), 1)
    check("two replies, not one per fish", len(misc.replies), 2)


def test_a_key_with_no_menu_is_reported(m):
    misc = FakeMisc(menu=[])
    mod = load(misc=misc)
    check("it returns False", mod["storeKey"](0x07BE5A00, "Treasure"), False)
    check("and says so", "no context menu" in " ".join(misc.messages).lower(),
          True)


def test_the_published_copy_carries_no_live_serials(m):
    """This repo is PUBLIC. The published copy must not ship anybody's
    character or item serials - only shard data, which is the same for
    everyone and is what makes the script usable."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    live = re.findall(r"0x[0-9A-Fa-f]{8}", src)
    check("no 8-digit serials in the script", sorted(set(live)), [])

    for name in ("player", "storage", "treasure", "trash", "dagger"):
        check("%s ships zeroed" % name, m[name], 0)

    # Shard data must SURVIVE the scrubbing - graphics and hues are the point.
    check("the dagger graphic is kept", m["daggerID"], 0x0F52)
    check("the steak graphic is kept", m["steak"], 0x097A)
    by_id = dict((c["id"], c) for c in m["cuttable"])
    check("the big fish graphic is kept", 0x09CC in by_id, True)
    check("the marlin graphic is kept", 0x4305 in by_id, True)


def test_a_zeroed_player_refuses_to_run(m):
    """With player = 0 the cast has nothing to aim from, so it must stop rather
    than fish at nothing. Anyone cloning this hits that on their first run."""
    misc = FakeMisc()
    mod = load(misc=misc)
    check("it refuses", mod["checkConfig"](), False)
    check("and says which value", "player is 0" in " ".join(misc.messages),
          True)


def test_the_other_zeroed_serials_only_warn(m):
    """Missing a trash bag is a downgrade, not a reason to refuse to fish."""
    misc = FakeMisc()
    mod = load(misc=misc)
    mod["player"] = 0x1234
    check("it runs", mod["checkConfig"](), True)
    said = " ".join(misc.messages)
    for name in ("storage", "treasure", "trash", "dagger"):
        check("%s is named as unset" % name, name in said, True)

# ---------------------------------------------------------------------------
# The stale backpack snapshot
# ---------------------------------------------------------------------------

class StalePack(object):
    """A backpack whose Contains is a SNAPSHOT, the way the real one is.

    It starts out wrong - the fish are physically in the pack but not in the
    list - and only tells the truth once the pack is re-opened. That is exactly
    what made only some of the big fish get cut: FindAllByID with a container
    serial walks this list, never the item index.
    """

    def __init__(self, really_holds, serial=0x41D40F58):
        self.really_holds = list(really_holds)
        self.Serial = serial
        self.Contains = []          # stale: the fish are missing
        self.reopened = 0

    def reopen(self, alive=None):
        """Re-reading shows what is REALLY in the pack right now.

        `alive` is what still exists - a cut fish is gone, and a re-opened pack
        must not keep listing it, or the caller cuts the same fish forever.
        """
        self.reopened += 1
        if alive is not None:
            serials = set(int(i.Serial) for i in alive)
            self.really_holds = [i for i in self.really_holds
                                 if int(i.Serial) in serials]
        self.Contains = list(self.really_holds)


class ReopeningItems(FakeItems):
    """UseItem on the backpack refreshes its snapshot, as re-opening does."""

    def __init__(self, pool=None, ignored=None, pack=None):
        FakeItems.__init__(self, pool=pool, ignored=ignored)
        self.pack = pack

    def UseItem(self, item, *a):
        FakeItems.UseItem(self, item, *a)
        if self.pack is not None and \
                int(getattr(item, "Serial", 0)) == int(self.pack.Serial):
            self.pack.reopen(alive=self.pool)

    def FindAllByID(self, item_id, hue, container, rng, ignore=True):
        # A CONTAINER search walks the snapshot. Only container -1 is a real
        # world query. This is the whole bug, modelled.
        if int(container) != -1:
            out = []
            for item in list(getattr(self.pack, "Contains", None) or []):
                if int(item.ItemID) != int(item_id):
                    continue
                if int(hue) != -1 and int(item.Hue) != int(hue):
                    continue
                if ignore and int(item.Serial) in self.ignored:
                    continue
                out.append(item)
            return out
        return FakeItems.FindAllByID(self, item_id, hue, container, rng, ignore)


def test_a_stale_pack_snapshot_does_not_hide_fish(m):
    """THE 'it only cuts some of them' BUG.

    Two big fish are really in the pack, but Contains has not caught up. A
    search that trusts the snapshot finds nothing and the fish sit there for
    the rest of the run.
    """
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    one = FakeItem(0x09CC, hue=0x0847, serial=0x501, name="a big fish")
    two = FakeItem(0x4305, hue=0x0000, serial=0x502, name="blue marlin")
    pack = StalePack(really_holds=[blade, one, two])
    items = ReopeningItems(pool=[blade, one, two], pack=pack)
    target = FakeTarget(items=items)
    mod = load(items=items, target=target, backpack=pack)

    check("the snapshot really is stale to begin with", pack.Contains, [])
    # The dagger is in the pack too. With `dagger` zeroed it is found by
    # graphic - a PACK search - so a stale snapshot hides the blade as well as
    # the fish, and cutFish reports "no dagger" and quietly does nothing.
    cuts = mod["cutFish"]()
    check("it re-opened the pack", pack.reopened >= 1, True)
    check("the big fish was found and cut", 0x501 in target.executed, True)
    check("the marlin too", 0x502 in target.executed, True)
    check("both counted", cuts, 2)


def test_the_pack_is_reread_after_each_cut(m):
    """Cutting changes the pack, so the snapshot is stale again - and the
    did-it-work test reads it. Without a re-read a successful cut can look
    like a failure and get the fish blacklisted."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def cutFish("):src.index("def refreshPack(")]
    check("cutFish refreshes the pack", "refreshPack()" in body, True)
    check("more than once", body.count("refreshPack()") >= 2, True)


def test_any_hue_of_a_named_fish_is_cut(m):
    """THE 0x058C REGRESSION.

    The big fish inspected on the GROUND was hue 0x0847; the ones in the PACK
    are 0x058C. Keyed on hue, the pack ones were silently skipped and it looked
    like the pack was not being searched. Two hues on one graphic means the hue
    is a variety marker, so the name has to be what decides.
    """
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    ground_hue = FakeItem(0x09CC, hue=0x0847, serial=0x701, name="a big fish")
    pack_hue = FakeItem(0x09CC, hue=0x058C, serial=0x702, name="a big fish")
    unheard_of = FakeItem(0x09CC, hue=0x1234, serial=0x703, name="a big fish")

    for label, fishy in (("0x0847", ground_hue), ("0x058C", pack_hue),
                         ("a hue nobody has seen", unheard_of)):
        items = FakeItems(pool=[fishy, blade])
        target = FakeTarget(items=items)
        mod = load(items=items, target=target,
                   backpack=FakeBackpack([fishy, blade]))
        mod["cutFish"]()
        check("a big fish in %s is cut" % label,
              int(fishy.Serial) in target.executed, True)


def test_an_ordinary_fish_is_still_safe_at_any_hue(m):
    """Dropping the hue filter must not turn this into "knife every 0x09CC".
    The name is what keeps the ordinary catch intact."""
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    for hue in (0x0000, 0x0847, 0x058C):
        plain = FakeItem(0x09CC, hue=hue, serial=0x710, name="a fish")
        items = FakeItems(pool=[plain, blade])
        target = FakeTarget(items=items)
        mod = load(items=items, target=target,
                   backpack=FakeBackpack([plain, blade]))
        mod["cutFish"]()
        check("'a fish' at hue 0x%04X is left alone" % hue,
              0x710 in target.executed, False)


def test_a_fish_that_will_not_name_itself_is_left_alone(m):
    """If the name will not load, do nothing. A missed fish costs nothing;
    knifing the wrong item cannot be undone."""
    blade = FakeItem(0x0F52, serial=0x0DA99E12)
    nameless = FakeItem(0x09CC, hue=0x058C, serial=0x720, name="")
    items = FakeItems(pool=[nameless, blade])
    target = FakeTarget(items=items)
    misc = FakeMisc()
    mod = load(items=items, misc=misc, target=target,
               backpack=FakeBackpack([nameless, blade]))
    mod["cutFish"]()
    check("it was not cut", 0x720 in target.executed, False)
    check("and it said why",
          "no readable name" in " ".join(misc.messages).lower(), True)


def test_the_uncut_report_does_not_repeat_every_cast(m):
    """It fired three times in one second in game. cutFish runs after every
    cast, so an unconditional report is a wall of identical lines."""
    odd = FakeItem(0x09CC, hue=0x058C, serial=0x730, name="a curious fish")
    misc = FakeMisc()
    mod = load(items=FakeItems(pool=[odd]), misc=misc,
               backpack=FakeBackpack([odd]))
    for _ in range(5):
        mod["reportUncut"]()
    check("said once, not five times", len(misc.messages), 1)
    check("and named the item", "curious fish" in misc.messages[0], True)


def test_a_matching_fish_is_not_reported_as_uncut(m):
    fine = FakeItem(0x09CC, hue=0x058C, serial=0x740, name="a big fish")
    misc = FakeMisc()
    mod = load(items=FakeItems(pool=[fine]), misc=misc,
               backpack=FakeBackpack([fine]))
    mod["reportUncut"]()
    check("nothing to complain about", misc.messages, [])


def main():
    module = load()
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-50s got=%-22s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:22], repr(want)[:26]))
        if not ok:
            failed += 1
    print("\n%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
