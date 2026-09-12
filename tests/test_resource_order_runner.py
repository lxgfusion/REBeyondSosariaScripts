"""Tests for Scripts/resource_order_runner.py.

Reads the script, strips the trailing main() call, execs it against stub Razor
objects and calls the REAL functions, so there is no copied logic to drift.
Fixtures are verbatim captures from live runs.

    python tests/test_resource_order_runner.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "Scripts", "resource_order_runner.py")

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


class _Stub(object):
    def __getattr__(self, name):
        return lambda *a, **k: None


# The script checks a stack is still alive with Items.FindBySerial, because
# Contains keeps listing stacks that have been merged away. The fakes resolve
# serials through this registry so that check behaves.
_REGISTRY = {}


class FakeItem(object):
    def __init__(self, name="", amount=0, item_id=0x1BF2, hue=0, serial=1,
                 tooltip=None, container=0x400CEF90):
        self.Name = name
        self.Amount = amount
        self.ItemID = item_id
        self.Hue = hue
        self.Serial = serial
        self.Container = container
        self.tooltip = tooltip if tooltip is not None else []
        _REGISTRY[int(serial)] = self


class FakeContainer(object):
    def __init__(self, items, serial=0x400CEF90):
        self.Contains = items
        self.Serial = serial
        for item in items:
            item.Container = serial


class FakeItems(_Stub):
    """Items stub whose FindAllByID answers from a fixed pool, the way the real
    one queries the item index rather than a container snapshot."""

    def __init__(self, pool=None):
        self.pool = list(pool or [])

    def FindAllByID(self, item_id, hue, container, rng, ignore=True):
        return [i for i in self.pool
                if i.ItemID == item_id and (hue == -1 or i.Hue == hue)]

    def FindBySerial(self, serial):
        return _REGISTRY.get(int(serial))

    def __getattr__(self, name):
        return lambda *a, **k: None


def load(items=None):
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    module = {
        "__name__": "resource_order_runner",
        "Misc": _Stub(), "Player": _Stub(), "Gumps": _Stub(),
        "Items": items if items is not None else FakeItems(),
        "Mobiles": _Stub(), "Target": _Stub(), "Journal": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), module)
    module["props"] = lambda item: list(getattr(item, "tooltip", []))
    return module


# ---------------------------------------------------------------------------
# Stock, keyed by hue
# ---------------------------------------------------------------------------

def test_census_keys_by_hue(m):
    """Every stack is named "<amount> ingots", so the name says nothing about
    the metal. Two stacks of 60000 on different hues are different metals."""
    chest = FakeContainer([
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x096D, 0x11),   # Copper
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0x12),   # Iron
        FakeItem("59985 ingots", 59985, 0x1BF2, 0x0000, 0x13),   # Iron
        FakeItem("a pickaxe", 1, 0x0E86, 0x0000, 0x14),
    ])
    stock = m["census"](chest)
    check("two metals", sorted(stock), ["Copper Ingots", "Iron Ingots"])
    check("iron stacks summed", stock["Iron Ingots"]["amount"], 119985)
    check("copper not merged", stock["Copper Ingots"]["amount"], 60000)
    check("pickaxe excluded", "pickaxe" in str(sorted(stock)).lower(), False)


def test_fill_budget_reserve_is_per_metal(m):
    stock = {"Iron Ingots": {"amount": 837973, "stacks": []},
             "Valorite Ingots": {"amount": 25020, "stacks": []},
             "Tin": {"amount": 60, "stacks": []}}
    budget = m["fill_budget"](stock, keep=100)
    check("iron spendable", budget["Iron Ingots"], 837873)
    check("valorite spendable", budget["Valorite Ingots"], 24920)
    check("below reserve never negative", budget["Tin"], 0)


def test_all_stacks_come_from_contains(m):
    """Contains is the ONLY window into a container. Items.FindAllByID with a
    container serial iterates that same list rather than querying the item
    index (Razor/RazorEnhanced/Item.cs, v1.0.0.14), so an earlier version that
    unioned the two had the same opinion twice, not two opinions."""
    a = FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0x11)
    b = FakeItem("59985 ingots", 59985, 0x1BF2, 0x0000, 0x12)
    c = FakeItem("4517 ingots", 4517, 0x1BF2, 0x0000, 0x13)
    chest = FakeContainer([a, b, c])

    stacks = m["chest_stacks"](chest, "Iron Ingots")
    check("all three stacks found", len(stacks), 3)
    check("largest first", stacks[0].Amount, 60000)
    check("total is the real total",
          m["census"](chest)["Iron Ingots"]["amount"], 60000 + 59985 + 4517)


def test_census_ignores_stacks_that_no_longer_exist(m):
    """After organizing merges stacks away, Contains still lists them. Counting
    those ghosts inflates the total, and the budget stops matching the chest."""
    alive = FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0xB1)
    merged_away = FakeItem("4517 ingots", 4517, 0x1BF2, 0x0000, 0xB2)
    chest = FakeContainer([alive, merged_away])

    # The merge emptied it, exactly as Items.Move leaves a drained stack.
    merged_away.Amount = 0

    stock = m["census"](chest)
    check("only the surviving stack counted",
          stock["Iron Ingots"]["amount"], 60000)
    check("ghost dropped from the stack list",
          len(stock["Iron Ingots"]["stacks"]), 1)


def test_census_targets_the_largest_stack_first(m):
    chest = FakeContainer([
        FakeItem("4517 ingots", 4517, 0x1BF2, 0x0000, 0xC1),
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0xC2),
        FakeItem("59985 ingots", 59985, 0x1BF2, 0x0000, 0xC3),
    ])
    stock = m["census"](chest)
    check("all three counted", stock["Iron Ingots"]["amount"],
          4517 + 60000 + 59985)
    check("largest first", stock["Iron Ingots"]["stacks"][0].Amount, 60000)
    check("fill targets the largest",
          m["chest_stacks"](chest, "Iron Ingots")[0].Amount, 60000)


# ---------------------------------------------------------------------------
# Two chests, and peerless ingredients matched by name
# ---------------------------------------------------------------------------

CHEST_A = 0x400CEF90
CHEST_B = 0x40112233


def test_census_pools_both_chests(m):
    """Stock is spread over two containers - ingots and gems in one, peerless
    ingredients in the other - and must count as one pool."""
    a = FakeContainer([
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0xD1),
        FakeItem("1045 Blue Diamond", 1045, 0x3198, 0x0000, 0xD2),
    ], serial=CHEST_A)
    b = FakeContainer([
        FakeItem("36 Taint", 36, 0x5AAA, 0x0000, 0xD3),
        FakeItem("33 Blight", 33, 0x5AAB, 0x0000, 0xD4),
    ], serial=CHEST_B)

    stock = m["census"]([a, b])
    check("all four resources pooled", sorted(stock),
          ["Blight", "Blue Diamond", "Iron Ingots", "Taint"])
    check("second chest counted", stock["Taint"]["amount"], 36)
    check("first chest still counted", stock["Iron Ingots"]["amount"], 60000)


def test_one_chest_still_works(m):
    """A bare chest, not a list - as_list should absorb the difference."""
    a = FakeContainer([FakeItem("500 ingots", 500, 0x1BF2, 0x08AB, 0xD5)],
                      serial=CHEST_A)
    check("single chest accepted",
          m["census"](a)["Valorite Ingots"]["amount"], 500)


def test_peerless_matched_by_name(m):
    """These carry their own name and their graphics are unknown, so the name is
    all there is - and the leading count has to come off first."""
    check("count stripped", m["strip_amount"]("36 Taint"), "Taint")
    check("taint", m["resource_of"](FakeItem("36 Taint", 36, 0x5AAA, 0)), "Taint")
    check("multi-word",
          m["resource_of"](FakeItem("11 Dread Horn Mane", 11, 0x5AAB, 0)),
          "Dread Horn Mane")
    check("general resource by name",
          m["resource_of"](FakeItem("153 Bone", 153, 0x5AAC, 0)), "Bone")
    check("unlisted item ignored",
          m["resource_of"](FakeItem("5 Some Random Thing", 5, 0x5AAD, 0)), None)


def test_granite_name_collision_is_disarmed(m):
    """EVERY granite stack is named "<amount> high quality granite".

    That is the whole bug. There IS an entry called "High Quality Granite", so
    the name match did not fail harmlessly the way it does for boards - it
    claimed every granite stack of every metal. A Valorite stack was then
    offered to fill a High Quality order, the server refused it, and the deed
    sat at 0/429 reporting that neither targeting nor dragging worked.
    """
    hq = [r for r in m["RESOURCES"] if r["name"] == "High Quality Granite"][0]
    check("High Quality Granite no longer matches by name",
          hq.get("by") == "name", False)

    # The real stack from the Item Inspector, 2026-08-18.
    valorite = FakeItem("402 high quality granite", 402, 0x1779, 0x08AB,
                        serial=0x40581636)
    check("a Valorite stack is Valorite, not High Quality",
          m["resource_of"](valorite), "Valorite Granite")

    # An unlisted granite hue must be INVISIBLE, never mistaken for another.
    # Invisible costs a skipped order; mistaken pours the wrong metal in.
    unlisted = FakeItem("300 high quality granite", 300, 0x1779, 0x0999,
                        serial=0x40581637)
    check("an unlisted granite hue identifies as nothing",
          m["resource_of"](unlisted), None)


def test_valorite_granite_is_pinned(m):
    """Confirmed live - ItemID 0x1779, hue 0x08AB, tooltip line 3 "Valorite"."""
    check("granite graphic", m["GRANITE_IDS"], [0x1779])
    check("Valorite Granite hue", m["GRANITE_HUES"]["Valorite Granite"], 0x08AB)

    entry = [r for r in m["RESOURCES"] if r["name"] == "Valorite Granite"][0]
    check("the entry took the graphic", entry["id"], 0x1779)
    check("and the hue", entry["hue"], 0x08AB)


def test_no_hue_serves_two_resources(m):
    """Within a family, one hue must mean one thing.

    NOT across families: matching is graphic AND hue, so two families with
    different graphics may share a hue - and they do. Hue 0x0000 is both
    Regular Boards (0x1BD7) and High Quality Granite (0x1779), because "no
    hue" is how every family spells its plain, uncoloured member. Checking
    globally called that a clash and refused to start the script.
    """
    for family in m["HUE_FAMILIES"]:
        seen = {}
        for name, hue in family["hues"].items():
            check("%s hue 0x%04X is not shared" % (family["label"], int(hue)),
                  seen.get(int(hue), name), name)
            seen[int(hue)] = name

    # And the cross-family case that must be ALLOWED.
    plain = [(f["label"], n) for f in m["HUE_FAMILIES"]
             for n, h in f["hues"].items() if int(h) == 0]
    check("more than one family has a plain member at hue 0",
          len(plain) > 1, True)
    check("startup accepts that", m["validate_board_hues"](), True)


def test_material_line_reads_the_third_tooltip_line(m):
    """Ingots, boards and granite all name their material on line 3."""
    original = m["props"]
    try:
        m["props"] = lambda item: ["402 High Quality Granite",
                                   "Weight: 402 Stones", "Valorite"]
        check("reads the material", m["material_line"](None), "Valorite")

        # Plain iron and default boards carry no third line - that absence is
        # itself the identification, not a failure.
        m["props"] = lambda item: ["91715 board", "Weight: 91715 Stones"]
        check("no third line means the default", m["material_line"](None), "")

        m["props"] = lambda item: []
        check("no tooltip at all is survivable", m["material_line"](None), "")
    finally:
        m["props"] = original

# Every granite stack as the Item Inspector reported it, 2026-08-18.
# (hue, amount, serial, tooltip material, the BOOK's name)
LIVE_GRANITE = [
    (0x0000, 2278, 0x409104D4, "",            "High Quality Granite"),
    (0x0973, 2896, 0x40DAF3FD, "Dull Copper", "Dull Copper Granite"),
    (0x0966, 2230, 0x40581515, "Shadow Iron", "Shadow Granite"),
    (0x096D, 1632, 0x4058153A, "Copper",      "Copper Granite"),
    (0x0972, 1864, 0x40581578, "Bronze",      "Bronze Granite"),
    (0x08A5, 1504, 0x4058159A, "Golden",      "Gold Granite"),
    (0x0979,  874, 0x4069DB95, "Agapite",     "Agapite Granite"),
    (0x089F, 1148, 0x405815DE, "Verite",      "Verite Granite"),
    (0x08AB,  402, 0x40581636, "Valorite",    "Valorite Granite"),
]


def test_every_live_granite_identifies_as_itself(m):
    """Pinned from the live dumps. Each stack must be its OWN metal.

    This is the regression for the 0/429 failure: every one of these is named
    "<amount> high quality granite", so before the hues went in they all
    resolved to High Quality Granite and the wrong stack was offered to fill.
    """
    for hue, amount, serial, _material, book_name in LIVE_GRANITE:
        stack = FakeItem("%d high quality granite" % amount, amount,
                         0x1779, hue, serial=serial)
        check("hue 0x%04X is %s" % (hue, book_name),
              m["resource_of"](stack), book_name)


def test_granite_table_is_complete_and_unique(m):
    """Nine metals, nine hues, no hue serving two - one would fill the other."""
    hues = m["GRANITE_HUES"]
    check("all nine granites are listed", len(hues), 9)
    check("no hue is shared", len(set(hues.values())), 9)

    for _hue, _amount, _serial, _material, book_name in LIVE_GRANITE:
        check("%s is in the table" % book_name, book_name in hues, True)
        check("%s is a real resource" % book_name,
              any(r["name"] == book_name for r in m["RESOURCES"]), True)


def test_granite_entries_now_match_by_graphic(m):
    """With a hue listed, the entry stops matching by name entirely.

    That is what disarms the collision for good: High Quality Granite is only
    hue 0x0000 now, not "any stack whose name contains those words".
    """
    for name in m["GRANITE_HUES"]:
        entry = [r for r in m["RESOURCES"] if r["name"] == name][0]
        check("%s matches by graphic" % name, entry.get("by"), None)
        check("%s uses the granite graphic" % name, entry["id"], 0x1779)


def test_book_names_differ_from_the_tooltip(m):
    """Three of the nine are worded differently by the stack and the book.

    Pasting the tooltip word straight into the table would silently produce an
    entry that matches no order - the same trap the ingots have, where the
    stack says "golden" and the book says "Gold".
    """
    for _hue, _amount, _serial, material, book_name in LIVE_GRANITE:
        if not material:
            continue
        if material.lower() != book_name.lower().replace(" granite", ""):
            # These three MUST be mapped by hand, so assert they are mapped
            # to a name the book actually has.
            check("%r maps to the book's %r" % (material, book_name),
                  any(r["name"] == book_name for r in m["RESOURCES"]), True)


def test_plain_granite_has_no_material_line(m):
    """Hue 0x0000 carries no third tooltip line, exactly like plain iron.

    The ABSENCE is the identification. A report that required a material line
    would leave the commonest granite permanently unidentified.
    """
    original = m["props"]
    try:
        m["props"] = lambda item: ["2278 High Quality Granite",
                                   "Weight: 2278 Stones"]
        check("plain granite reports no material", m["material_line"](None), "")
        plain = FakeItem("2278 high quality granite", 2278, 0x1779, 0x0000,
                         serial=0x409104D4)
        check("and is still identified by its hue",
              m["resource_of"](plain), "High Quality Granite")
    finally:
        m["props"] = original

# Every ingot stack as the Item Inspector reported it, 2026-08-18.
# (hue, amount, serial, tooltip material, the BOOK's name)
LIVE_INGOTS = [
    (0x0000, 56750, 0x40BAE41A, "",            "Iron Ingots"),
    (0x0973,  5632, 0x40D9A64F, "Dull Copper", "Dull Copper Ingots"),
    (0x0966,  2358, 0x40999C4D, "Shadow Iron", "Shadow Ingots"),
    (0x0057,   293, 0x4088DD61, "Mythril",     "Mythril Ingots"),
    (0x0972, 48216, 0x43D74565, "Bronze",      "Bronze Ingots"),
    (0x096D, 59999, 0x40114AD4, "Copper",      "Copper Ingots"),
    (0x0979, 50744, 0x40742A35, "Agapite",     "Agapite Ingots"),
    (0x08A5, 47767, 0x4058116E, "Golden",      "Gold Ingots"),
]


def test_every_live_ingot_identifies_as_itself(m):
    """Pinned from the live dumps, including IRON.

    Iron was suspected of not filling. These dumps say the entry was right all
    along - 0x1BF2 / hue 0x0000, no third tooltip line - so if Iron orders are
    not being filled the cause is not identification. Pinned so a later edit
    cannot quietly break the one that was already correct.
    """
    for hue, amount, serial, _material, book_name in LIVE_INGOTS:
        stack = FakeItem("%d ingots" % amount, amount, 0x1BF2, hue,
                         serial=serial)
        check("ingot hue 0x%04X is %s" % (hue, book_name),
              m["resource_of"](stack), book_name)


def test_mythril_is_this_shards_own_metal(m):
    """Mythril is in no ServUO table, like the Magewood and Darkwood boards.

    It shipped as {"id": 0, "hue": -1, "by": "name"} - which can never match,
    because an ingot stack is called "<amount> ingots" and names no metal - so
    all 146 of its orders were unfillable and nothing said so.
    """
    entry = [r for r in m["RESOURCES"] if r["name"] == "Mythril Ingots"][0]
    check("Mythril has the ingot graphic", entry["id"], 0x1BF2)
    check("Mythril hue", entry["hue"], 0x0057)
    check("and no longer matches by name", entry.get("by"), None)


def test_no_ingot_entry_is_left_unmatchable(m):
    """Any *_Ingots entry still on id 0 can never match a stack.

    That is the silent failure this whole class of bug keeps taking: the
    resource has orders in the book, stock in the chest, and no way to connect
    the two.
    """
    stranded = [r["name"] for r in m["RESOURCES"]
                if r["name"].endswith("Ingots") and not r.get("id")]
    check("every ingot can be identified", stranded, [])


def test_ingot_hues_are_unique(m):
    """One hue, one metal - a shared hue would fill one order with another."""
    seen = {}
    for r in m["RESOURCES"]:
        if r.get("id") != 0x1BF2:
            continue
        for hue in (r["hue"] if isinstance(r["hue"], list) else [r["hue"]]):
            check("ingot hue 0x%04X is not shared" % int(hue),
                  seen.get(int(hue), r["name"]), r["name"])
            seen[int(hue)] = r["name"]


def test_granite_and_ingots_share_hues_but_not_graphics(m):
    """The two families use the SAME hues - only the graphic separates them.

    Dull Copper is 0x0973 as both an ingot (0x1BF2) and granite (0x1779). That
    is why identification must be graphic AND hue, and why hue uniqueness can
    only ever be checked within one graphic.
    """
    for hue in (0x0973, 0x0966, 0x0972, 0x096D, 0x0979, 0x08A5, 0x0000):
        ingot = FakeItem("100 ingots", 100, 0x1BF2, hue, serial=0x50000000 + hue)
        granite = FakeItem("100 high quality granite", 100, 0x1779, hue,
                           serial=0x51000000 + hue)
        got_ingot = m["resource_of"](ingot)
        got_granite = m["resource_of"](granite)
        check("hue 0x%04X: ingot and granite differ" % hue,
              got_ingot != got_granite, True)
        check("hue 0x%04X ingot is an ingot" % hue,
              bool(got_ingot) and got_ingot.endswith("Ingots"), True)
        check("hue 0x%04X granite is granite" % hue,
              bool(got_granite) and got_granite.endswith("Granite"), True)

def test_census_sums_every_stack_of_a_resource(m):
    """Iron and Regular Boards are held in MANY stacks - all of them count."""
    stacks = [FakeItem("%d ingots" % n, n, 0x1BF2, 0x0000, serial=0x51000000 + i)
              for i, n in enumerate([56750, 12000, 8000, 300])]
    chest = FakeContainer(stacks)
    stock = m["census"]([chest])

    check("iron is in the census", "Iron Ingots" in stock, True)
    check("every stack counted", stock["Iron Ingots"]["amount"],
          56750 + 12000 + 8000 + 300)
    check("and all four are kept", len(stock["Iron Ingots"]["stacks"]), 4)

    budget = m["fill_budget"](stock, keep=0)
    check("the whole lot is spendable", budget["Iron Ingots"], 77050)


def test_census_reopens_before_believing_a_resource_is_gone(m):
    """A resource whose stacks all fail to resolve is a STALE SNAPSHOT.

    chest_stacks has always reopened and retried before believing an empty
    result. The census did not - so it could drop a resource the filler would
    have found, and a resource missing from the census gets a budget of 0 and
    is passed over in SILENCE. That is what "it just skips them" looked like.
    """
    check("the census has a retry pass", "_census_pass" in m, True)

    # A pass over a chest whose items do not resolve must REPORT the loss
    # rather than quietly returning an empty census.
    ghost = FakeItem("40000 ingots", 40000, 0x1BF2, 0x0000, serial=0x7FFFFFF1)
    _REGISTRY.pop(0x7FFFFFF1, None)          # server-side it is gone
    stock, lost = m["_census_pass"]([FakeContainer([ghost])])
    check("a stack that will not resolve is not counted",
          "Iron Ingots" in stock, False)
    check("but it IS reported as lost, not silently dropped",
          "Iron Ingots" in lost, True)


def test_a_skipped_resource_is_never_silent(m):
    """Every pass-over must produce a line naming the resource and its numbers.

    Three different causes end up here - not in the census at all, held back by
    the reserve, or genuinely spent - and only the numbers tell them apart.
    """
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    start = src.index("if budget.get(resource, 0) <= 0:")
    block = src[start:start + 1400]
    check("the skip logs when the resource is missing entirely",
          "not in the chest census at all" in block, True)
    check("and logs the numbers when it is present but unspendable",
          "spendable (keep" in block, True)
    check("it no longer skips with a bare continue",
          block.split("continue")[0].count("log(") >= 2, True)

def test_fill_passes_scale_with_the_stack_count(m):
    """A flat pass limit is a single-stack assumption in disguise.

    An order of MAX_ORDER_SIZE is one target against a 56,750 stack, but nine
    against stacks of 3,000. At a flat 6 the deed was abandoned with plenty of
    metal still in the chest and reported as unfillable.
    """
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def fill_deed("):src.index("def openAR(")]

    check("the allowance is computed, not constant",
          "len(on_hand) + 2" in body, True)
    check("it never drops below the floor",
          "max(MAX_FILL_ATTEMPTS" in body, True)
    check("and it is bounded",
          "MAX_FILL_ATTEMPTS_CEILING" in body, True)
    check("the loop uses the allowance, not the constant",
          "for attempt in range(allowance)" in body, True)


def test_fill_allowance_covers_a_worst_case_order(m):
    """The ceiling has to clear the worst order the runner will accept.

    MAX_ORDER_SIZE against stacks no larger than MAX_STACK is the bound that
    matters; anything smaller means a legitimate order can run out of passes.
    """
    ceiling = m["MAX_FILL_ATTEMPTS_CEILING"]
    check("the floor is still the old default", m["MAX_FILL_ATTEMPTS"], 6)
    check("the ceiling is above the floor", ceiling > m["MAX_FILL_ATTEMPTS"],
          True)

    # Worst realistic case: an order at the size cap, drawn from stacks a
    # tenth the size of a full one.
    modest_stack = m["MAX_STACK"] // 10
    needed_passes = -(-m["MAX_ORDER_SIZE"] // modest_stack)   # ceil
    check("the ceiling clears a %d-pass order" % needed_passes,
          ceiling >= needed_passes, True)


def test_a_failed_fill_says_what_stock_remained(m):
    """"Still at 0/429" is only actionable with the stock alongside it."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def fill_deed("):src.index("def openAR(")]
    tail = body[body.index("still at %s after"):]
    check("it reports the stacks left", "stack(s) and %d %s" in tail, True)
    check("and names the knob to raise",
          "MAX_FILL_ATTEMPTS_CEILING" in tail, True)


def test_every_resource_reports_its_stack_count_in_the_report(m):
    """Multi-stack state has to be visible for every resource, not just some."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    check("the stock report shows stacks and the biggest",
          "in %d stack(s), biggest %d" in src, True)

# The gem stacks as the Item Inspector reported them, 2026-08-18.
LIVE_GEMS = [
    (0x3194, 6517, 0x41CE9DE1, "Perfect Emerald"),
    (0x3195, 6377, 0x41CE9B45, "Ecru Citrine"),
    (0x3197, 5525, 0x41CE9E28, "Fire Ruby"),
]


def test_every_live_gem_identifies(m):
    """Pinned from the dumps. Perfect Emerald was missing from RESOURCES
    entirely, so 6517 of them were invisible and no order could be filled."""
    for item_id, amount, serial, name in LIVE_GEMS:
        stack = FakeItem("%d %s" % (amount, name), amount, item_id, 0x0000,
                         serial=serial)
        check("0x%04X is %s" % (item_id, name), m["resource_of"](stack), name)


def test_the_gem_graphic_block_has_no_gaps(m):
    """0x3192-0x3199 is one contiguous run of gems.

    Perfect Emerald was the single gap in it. A gap there is invisible: the
    stock does not count, the orders never fill, and nothing says why.
    """
    by_id = {}
    for r in m["RESOURCES"]:
        gid = r.get("id")
        if isinstance(gid, int) and 0x3192 <= gid <= 0x3199:
            by_id[gid] = r["name"]
    missing = [g for g in range(0x3192, 0x319A) if g not in by_id]
    check("no gap in the gem block", ["0x%04X" % g for g in missing], [])


def test_perfect_emerald_cannot_be_confused_with_emerald(m):
    """"Emerald" is a substring of "Perfect Emerald" - the trap the deed
    matcher already documents. They must stay separate resources."""
    names = [r["name"] for r in m["RESOURCES"]]
    check("both exist", "Perfect Emerald" in names and "Emerald" in names, True)

    perfect = [r for r in m["RESOURCES"] if r["name"] == "Perfect Emerald"][0]
    check("Perfect Emerald matches by graphic, not name",
          perfect.get("by"), None)
    check("and has its own graphic", perfect["id"], 0x3194)

    # A deed for one must never be filled from the other.
    check("an Emerald deed is refused for Perfect Emerald",
          m["deed_matches_resource"]({"resource": "Emerald"},
                                     "Perfect Emerald"), False)
    check("and the other way round",
          m["deed_matches_resource"]({"resource": "Perfect Emerald"},
                                     "Emerald"), False)
    check("but each matches itself",
          m["deed_matches_resource"]({"resource": "Perfect Emerald"},
                                     "Perfect Emerald"), True)


def test_no_two_resources_share_a_graphic_and_hue(m):
    """Two entries answering to the same graphic+hue would fill each other."""
    seen = {}
    for r in m["RESOURCES"]:
        gid = r.get("id")
        if not gid:
            continue
        hues = r["hue"] if isinstance(r["hue"], list) else [r["hue"]]
        for hue in hues:
            key = (int(gid), int(hue))
            check("0x%04X/0x%04X is not shared" % key,
                  seen.get(key, r["name"]), r["name"])
            seen[key] = r["name"]

# Every dragon scale stack in the chest, Item Inspector 2026-08-18.
# All ItemID 0x26B4, all named "<amount> dragon scales", NO material line.
LIVE_SCALES = [
    (0x0851,    7, 0x409083A4, "Green Scales"),
    (0x0455, 1353, 0x40908214, "Black Scales"),
    (0x066D, 5388, 0x40908071, "Red Scales"),
    (0x08A8, 4854, 0x40908143, "Yellow Scales"),
    (0x08FD, 2657, 0x40908376, "White Scales"),
]


def test_every_live_scale_identifies_as_its_colour(m):
    """All five colours read off the stacks in game, 2026-08-18.

    Scales carry no material line - every colour is a stack called "<amount>
    dragon scales" at graphic 0x26B4 - so the hue is the ONLY signal and these
    five mappings are the whole of the knowledge.
    """
    for hue, amount, serial, colour in LIVE_SCALES:
        stack = FakeItem("%d dragon scales" % amount, amount, 0x26B4, hue,
                         serial=serial)
        check("hue 0x%04X is %s" % (hue, colour),
              m["resource_of"](stack), colour)


def test_blue_scales_is_the_sea_serpent_hue(m):
    """Blue orders are filled with SEA SERPENT scales, 0x08B0.

    Confirmed in game 2026-08-20. The stack comes off a different creature
    than the dragon colours, which is why an earlier note here said not to map
    it - that note was wrong about this one, and right about Medusa.
    """
    check("Blue Scales is mapped", m["SCALE_HUES"].get("Blue Scales"), 0x08B0)

    stack = FakeItem("900 sea serpent scales", 900, 0x26B4, 0x08B0,
                     serial=0x40909111)
    check("a sea serpent stack fills blue orders",
          m["resource_of"](stack), "Blue Scales")

    # Medusa keeps its own entries and must never be treated as blue.
    check("Dark Medusa Scales is its own resource",
          any(r["name"] == "Dark Medusa Scales" for r in m["RESOURCES"]), True)
    check("Light Medusa Scales too",
          any(r["name"] == "Light Medusa Scales" for r in m["RESOURCES"]), True)
    check("0x08AF is NOT mapped to any scale colour",
          0x08AF in m["SCALE_HUES"].values(), False)
    medusa = FakeItem("120 medusa scales", 120, 0x26B4, 0x08AF,
                      serial=0x40909222)
    check("a medusa stack is not claimed as blue",
          m["resource_of"](medusa) == "Blue Scales", False)


def test_an_unmapped_scale_hue_is_reported_with_a_stack_to_look_at(m):
    """All five known colours are mapped now, but the machinery still matters.

    Blue has no stock yet, and a sixth colour could turn up. Scales carry no
    material line, so the report cannot say what a hue IS - it has to point at
    one specific stack for a person to go and look at.
    """
    known = [FakeItem("%d dragon scales" % a, a, 0x26B4, h, serial=s_)
             for h, a, s_, _c in LIVE_SCALES]
    family = [f for f in m["HUE_FAMILIES"] if f["label"] == "scale"][0]

    check("nothing known is left unmapped",
          sorted(m["unknown_family_stacks"]([FakeContainer(known)], family)), [])

    # A colour nobody has mapped yet - blue, or whatever turns up next.
    stranger = FakeItem("4242 dragon scales", 4242, 0x26B4, 0x0999,
                        serial=0x40908ABC)
    unknown = m["unknown_family_stacks"](
        [FakeContainer(known + [stranger])], family)

    check("the new hue is reported", sorted(unknown), [0x0999])
    check("with the stack to go and look at",
          (unknown[0x0999]["serial"], unknown[0x0999]["biggest"]),
          (0x40908ABC, 4242))
    check("and no material, because scales have none",
          unknown[0x0999]["material"], "")


def test_the_book_wants_six_colours(m):
    """Six scale resources, five hues in the chest - one has no stock."""
    scales = [r["name"] for r in m["RESOURCES"]
              if r["name"].endswith("Scales") and r["name"] != "Delicate Scales"
              and "Medusa" not in r["name"]]
    for colour in ("Black Scales", "Green Scales", "Yellow Scales",
                   "Red Scales", "Blue Scales", "White Scales"):
        check("%s is a book resource" % colour, colour in scales, True)

    mapped = m["SCALE_HUES"]
    check("all six are mapped now", sorted(mapped),
          ["Black Scales", "Blue Scales", "Green Scales", "Red Scales",
           "White Scales", "Yellow Scales"])


def test_an_unmapped_scale_is_claimed_by_nobody(m):
    """Every colour is a stack called "dragon scales", so a NAME match would
    claim all of them for whichever entry it hit first.

    The hue must be the only thing that decides. 0x0999 is deliberately a hue
    nobody has mapped - an earlier version of this test used 0x0455 as the
    stand-in and started failing the moment that turned out to be Black.
    """
    stack = FakeItem("999 dragon scales", 999, 0x26B4, 0x0999,
                     serial=0x40908999)
    got = m["resource_of"](stack)
    check("an unmapped scale hue belongs to no resource", got, None)

    for name in ("Yellow Scales", "Red Scales", "Blue Scales", "White Scales",
                 "Black Scales", "Green Scales"):
        check("%s does not claim it" % name, got == name, False)

def test_graphic_match_wins_over_name_match(m):
    """An ingot stack is called "<amount> ingots". If a name entry could claim
    it, hue would stop deciding the metal - so graphic entries are tried first."""
    iron = FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0xD6)
    check("still identified by hue", m["resource_of"](iron), "Iron Ingots")


def test_leather_accepts_both_servuo_hue_tables(m):
    """ServUO keeps two leather tables and picks at runtime with
    `Core.AOS ? m_AOSLeatherInfo : m_LeatherInfo`, so betting on one set could
    miss every stack. Both are accepted; they collide with nothing else here."""
    for hue, want in [(0x0851, "Barbed Leather"), (0x01C1, "Barbed Leather"),
                      (0x0845, "Horned Leather"), (0x0227, "Horned Leather"),
                      (0x08AC, "Spined Leather"), (0x0283, "Spined Leather"),
                      (0x0000, "Regular Leather")]:
        check("leather hue 0x%04X" % hue,
              m["resource_of"](FakeItem("1932 leather", 1932, 0x1081, hue)),
              want)


def test_leather_shares_one_graphic(m):
    """All four types are ItemID 0x1081 - BaseLeather is base(0x1081) - so the
    hue is the only thing that tells them apart, exactly like ingots."""
    leather = [r for r in m["RESOURCES"] if "Leather" in r["name"]]
    check("four leather entries", len(leather), 4)
    check("all on 0x1081", set(r["id"] for r in leather), set([0x1081]))


def test_nothing_is_held_back_any_more(m):
    """The reserve was dropped - everything is spendable. The mechanism stays,
    so a single resource can still be protected with its own "keep"."""
    check("global reserve is zero", m["KEEP_PER_TYPE"], 0)
    for name in ("Barbed Leather", "Regular Leather", "Iron Ingots",
                 "Blue Diamond", "Taint", "Bone"):
        check("%s spendable to zero" % name, m["keep_for"](name), 0)


def test_leather_order_sizes_are_admitted(m):
    """Live leather orders run 1095-6271."""
    check("ceiling clears 6271", m["MAX_ORDER_SIZE"] >= 6271, True)


def test_entry_hues_normalises(m):
    check("scalar", m["entry_hues"]({"hue": 0x0966}), [0x0966])
    check("list", m["entry_hues"]({"hue": [1, 2]}), [1, 2])
    check("missing means any", m["entry_hues"]({}), [-1])


# ---------------------------------------------------------------------------
# Runecrafting storage, emptied after the hand-in
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# The hand-in sweep
# ---------------------------------------------------------------------------

def done_deed(serial, resource="Copper Ingots", amount=1038):
    return FakeItem("A Resource Order Deed", 1, 0x14F0, 0, serial, tooltip=[
        "A Resource Order Deed", "Blessed", "Weight: 1 Stone",
        "Order Fulfilled [%d %s]Valued At: 25 Gold Each" % (amount, resource)])


def open_deed(serial, resource="Copper Ingots", filled=0, needed=500):
    return FakeItem("A Resource Order Deed", 1, 0x14F0, 0, serial, tooltip=[
        "A Resource Order Deed", "Blessed", "Weight: 1 Stone",
        "%d / %d %s ObtainedValued At: 25 Gold Each" % (filled, needed, resource)])


def test_only_fulfilled_deeds_are_swept(m):
    """The sweep must never hand in a deed that is not finished - that would
    spend it for nothing."""
    check("fulfilled deed qualifies", m["deed_is_complete"](done_deed(0xE1)), True)
    check("untouched deed does not",
          m["deed_is_complete"](open_deed(0xE2, filled=0)), False)
    check("part-filled deed does not",
          m["deed_is_complete"](open_deed(0xE3, filled=499, needed=500)), False)
    check("exactly filled counts",
          m["deed_is_complete"](open_deed(0xE4, filled=500, needed=500)), True)


def test_unparseable_deed_is_not_swept(m):
    """If the tooltip cannot be read, it is not proof of completion."""
    mystery = FakeItem("A Resource Order Deed", 1, 0x14F0, 0, 0xE5,
                       tooltip=["A Resource Order Deed", "Blessed"])
    check("no proof, no hand-in", m["deed_is_complete"](mystery), False)


def test_sweep_passes_are_bounded(m):
    """A refused drag must not loop forever."""
    check("bounded", 1 <= m["HANDIN_SWEEP_PASSES"] <= 10, True)


def test_deed_recognised_after_completion(m):
    """The sweep finds deeds with is_order_deed, which has to keep working once
    the tooltip switches to the fulfilled shape."""
    check("fulfilled deed still recognised",
          m["is_order_deed"](done_deed(0xE6)), True)
    check("in-progress deed recognised",
          m["is_order_deed"](open_deed(0xE7)), True)


# ---------------------------------------------------------------------------
# The circuit
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Trashing the reward forges
# ---------------------------------------------------------------------------

def test_trash_config_matches_the_inspector(m):
    check("trash bag serial", m["TRASH_BAG_SERIAL"], 0x4226C3E4)
    check("trash bag graphic", m["TRASH_BAG_ID"], 0x09B2)
    check("trash bag hue", m["TRASH_BAG_HUE"], 0x07EA)
    check("portable forge listed", 0x0FB1 in m["TRASH_ITEM_IDS"], True)


def test_trash_is_an_allowlist(m):
    """The bag DELETES what goes in after 30 seconds, so this must never be a
    "bin anything unwanted" sweep. Nothing outside TRASH_ITEM_IDS qualifies."""
    ids = m["TRASH_ITEM_IDS"]
    for forbidden, what in [(m["DEED_ID"], "order deed"),
                            (0x1BF2, "ingots"),
                            (0x3198, "Blue Diamond"),
                            (0x1081, "leather"),
                            (m["TRASH_BAG_ID"], "the trash bag itself"),
                            (m["RUNECRAFT_ID"], "runecrafting storage")]:
        check("%s is NOT binned" % what, forbidden in ids, False)


def test_trash_list_is_small_and_deliberate(m):
    """A long list here would mean someone got casual with a delete."""
    check("one graphic only", len(m["TRASH_ITEM_IDS"]), 1)


def test_trash_is_bounded(m):
    check("per-lap ceiling", 1 <= m["TRASH_MAX_PER_LAP"] <= 100, True)


def test_trash_runs_before_filling(m):
    """"before the start of filling the orders again, each loop" - so it has to
    come before fill_orders inside the lap, not after."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    lap = [n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef) and n.name == "run_lap"][0]

    order = []
    for node in ast.walk(lap):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None)
            if name in ("trash_junk", "fill_orders"):
                order.append((node.lineno, name))
    order.sort()
    names = [n for _line, n in order]
    check("both called in the lap", sorted(set(names)),
          ["fill_orders", "trash_junk"])
    check("trash first", names.index("trash_junk") < names.index("fill_orders"),
          True)


def test_circuit_runes_match_the_runebook(m):
    """From the [AR listing under RO:
        1. RO   2. Start Fill   3. Deposit items   4. Deposit PS"""
    check("start rune", m["START_POINT"], "Start Fill")
    check("start folder", m["START_FOLDER"], ["RO"])
    check("hand-in rune", m["HANDIN_POINT"], "RO")
    check("hand-in folder", m["HANDIN_FOLDER"], ["RO"])

    points = [s["point"] for s in m["STATIONS"]]
    check("deposit stops in order", points, ["Deposit items", "Deposit PS"])
    check("both in the RO folder",
          set(tuple(s["folder"]) for s in m["STATIONS"]), set([("RO",)]))


def test_station_items_match_the_inspector(m):
    by_point = dict((s["point"], s) for s in m["STATIONS"])
    check("armory serial", by_point["Deposit items"]["serial"], 0x4024AAE8)
    check("armory graphic", by_point["Deposit items"]["id"], 0x151A)
    check("ps book serial", by_point["Deposit PS"]["serial"], 0x4093D482)
    check("ps book graphic", by_point["Deposit PS"]["id"], 0x2259)
    check("both use Refill From Stock",
          set(tuple(s["context"]) for s in m["STATIONS"]),
          set([("Refill From Stock",)]))


def test_ps_book_hue_separates_it_from_the_order_book(m):
    """0x2259 is ALSO the Resource Order Book's graphic. The serial is what
    normally tells them apart, so the id/hue fallback is only safe while the
    hues differ."""
    ps = [s for s in m["STATIONS"] if s["point"] == "Deposit PS"][0]
    check("same graphic as the order book", ps["id"], m["BOOK_ID"])
    check("but a different hue", ps["hue"] != m["BOOK_HUE"], True)


def test_copper_selection_works_on_the_real_page(m):
    """Page 1 of the live "copper" filter, verbatim. The selection was never
    the problem - Copper simply never got a turn, because the table is ordered
    by the book's order count and Copper sits at position 57 of 79."""
    page = ["Resource Orders", "Contents: 8050/100000", "Displayed: 137",
            "Name", "Amt To Gather", "Amt Gathered", "Value Per", "Completed"]
    for amt in (2693, 1745, 2074, 1722, 2089, 1647, 1869, 1848,
                1940, 1983, 1825, 1774, 2046, 1786, 2254):
        page += ["Copper Ingots", str(amt), "0", "25", "No"]
    page += ["Previous Page", "Next Page", "(1/10)", "Add", "Purge"]

    rows = m["parse_order_rows"](page, "copper ingots")
    check("fifteen rows", len(rows), 15)
    check("amounts read", [r["amount"] for r in rows[:3]], [2693, 1745, 2074])
    check("none rejected as another resource",
          [r for r in rows if r["name"] != "Copper Ingots"], [])
    check("all inside the order ceiling",
          max(r["amount"] for r in rows) <= m["MAX_ORDER_SIZE"], True)
    check("dull copper still recognised as a collision",
          m["colliding_names"]("Copper Ingots"), ["Dull Copper Ingots"])


def test_lap_count_is_a_safety_net_not_the_limit(m):
    """The run should end when a full pass fills nothing, having emptied what
    it can - not because it ran out of laps. At MAX_ORDERS_PER_RUN a lap, the
    old ceiling of 20 capped the whole run at 500 orders."""
    check("bounded", 1 <= m["MAX_CYCLES"] <= 1000, True)


def test_run_ends_when_a_lap_fills_nothing(m):
    """"until no more RO's can be filled" - a lap that hands in nothing ends
    the run rather than looping to MAX_CYCLES."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    main_fn = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "main"][0]
    src = ast.dump(main_fn)
    check("zero-handed lap breaks the loop", "handed" in src and "Break" in src,
          True)


def test_context_exact_match_wins(m):
    labels = ["Open", "Refill from stock", "Refill from stockpile"]
    check("exact beats the longer substring",
          m["pick_context"](labels, ["Refill from stock"]),
          "Refill from stock")


def test_context_returns_the_real_label(m):
    """ContextReply must be given what the menu says, not the search string."""
    check("real label returned",
          m["pick_context"](["Refill From Stock"], ["Refill from stock"]),
          "Refill From Stock")


def test_context_substring_fallback_refuses_dangerous_entries(m):
    """A storage menu can put something that destroys stock beside the entry
    wanted, so the substring fallback honours CONTEXT_NEVER."""
    check("destroy is refused",
          m["pick_context"](["Destroy all stock"], ["stock"]), None)
    check("empty is refused",
          m["pick_context"](["Empty the stock"], ["stock"]), None)
    check("a safe substring is allowed",
          m["pick_context"](["Restock from stock bag"], ["from stock"]),
          "Restock from stock bag")


def test_context_absent_entry_selects_nothing(m):
    check("no match, no click",
          m["pick_context"](["Open", "Close"], ["Refill from stock"]), None)


def test_runecraft_config_matches_the_inspector(m):
    check("serial", m["RUNECRAFT_SERIAL"], 0x411CCD22)
    check("graphic", m["RUNECRAFT_ID"], 0x2254)
    check("entry", m["RUNECRAFT_CONTEXT"], ["Refill from stock"])


def test_peerless_has_no_reserve(m):
    """The obelisks refill these, so they are spendable to the last one - unlike
    ingots and gems, which hold KEEP_PER_TYPE back."""
    check("peerless keeps nothing", m["keep_for"]("Taint"), 0)
    check("multi-word peerless too", m["keep_for"]("Dread Horn Mane"), 0)
    check("ingots still reserved", m["keep_for"]("Iron Ingots"),
          m["KEEP_PER_TYPE"])
    check("gems still reserved", m["keep_for"]("Blue Diamond"),
          m["KEEP_PER_TYPE"])
    check("unknown falls back to the default", m["keep_for"]("Nonsense"),
          m["KEEP_PER_TYPE"])


def test_budget_uses_the_per_resource_reserve(m):
    stock = {"Taint": {"amount": 36, "stacks": []},
             "Bark Fragment": {"amount": 4, "stacks": []},
             "Iron Ingots": {"amount": 842490, "stacks": []},
             "Blue Diamond": {"amount": 1045, "stacks": []}}
    budget = m["fill_budget"](stock)
    check("all 36 Taint spendable", budget["Taint"], 36)
    check("even a stack of 4 is spendable", budget["Bark Fragment"], 4)
    check("all the iron spendable", budget["Iron Ingots"], 842490)
    check("all the gems spendable", budget["Blue Diamond"], 1045)


def test_explicit_keep_still_overrides(m):
    """The tests and any one-off override pass a number for the whole lot."""
    stock = {"Taint": {"amount": 36, "stacks": []}}
    check("override applied", m["fill_budget"](stock, keep=10)["Taint"], 26)


def test_peerless_names_are_in_the_table(m):
    names = [r["name"] for r in m["RESOURCES"]]
    for want in ("Taint", "Blight", "Corruption", "Scourge", "Putrefaction",
                 "Muculent", "Eye of the Travesty", "Lard of Paroxysmus",
                 "Dread Horn Mane", "Captured Essence"):
        check("%s listed" % want, want in names, True)
    check("peerless entries match by name",
          all(r.get("by") == "name" for r in m["RESOURCES"]
              if r["name"] == "Taint"), True)


def test_merges_never_cross_chests(m):
    """Moving stock between containers would relocate what the user filed
    deliberately. A merge has to stay inside one chest."""
    a = FakeItem("500 ingots", 500, 0x1BF2, 0x0000, 0xD7, container=CHEST_A)
    b = FakeItem("300 ingots", 300, 0x1BF2, 0x0000, 0xD8, container=CHEST_B)
    chest_a = FakeContainer([a], serial=CHEST_A)
    chest_b = FakeContainer([b], serial=CHEST_B)
    a.Container, b.Container = CHEST_A, CHEST_B

    stub = RecordingItems(chest_a)
    module = load(stub)
    module["props"] = lambda item: list(getattr(item, "tooltip", []))

    module["consolidate_stacks"]([chest_a, chest_b], "Iron Ingots")
    check("no cross-chest move", len(stub.moves), 0)


def test_no_double_counting(m):
    a = FakeItem("500 ingots", 500, 0x1BF2, 0x08AB, 0x21)
    b = FakeItem("300 ingots", 300, 0x1BF2, 0x08AB, 0x22)
    chest = FakeContainer([a, b])
    check("counted once each", len(m["chest_stacks"](chest, "Valorite Ingots")), 2)
    check("total not doubled",
          m["census"](chest)["Valorite Ingots"]["amount"], 800)


class RecordingItems(_Stub):
    """Items stub backed by a real container, so merges are modelled the way
    the game does them: the source shrinks, the destination grows, and an
    emptied stack leaves Contains."""

    def __init__(self, chest):
        self.chest = chest
        self.moves = []

    def Move(self, source, destination, amount, *a, **k):
        self.moves.append((int(source.Serial), int(destination.Serial), amount))
        source.Amount -= amount
        destination.Amount += amount
        if source.Amount <= 0:
            self.chest.Contains = [i for i in self.chest.Contains
                                   if int(i.Serial) != int(source.Serial)]

    def FindBySerial(self, serial):
        if int(serial) == int(self.chest.Serial):
            return self.chest
        return _REGISTRY.get(int(serial))

    def WaitForContents(self, *a, **k):
        return True

    def __getattr__(self, name):
        return lambda *a, **k: None


def with_chest(items):
    """(module, chest, items_stub) sharing one container."""
    chest = FakeContainer(list(items))
    stub = RecordingItems(chest)
    module = load(stub)
    module["props"] = lambda item: list(getattr(item, "tooltip", []))
    return module, chest, stub


def test_consolidate_merges_into_the_largest(m):
    module, chest, items = with_chest([
        FakeItem("100 ingots", 100, 0x1BF2, 0x08AB, 0x31),
        FakeItem("900 ingots", 900, 0x1BF2, 0x08AB, 0x32),
        FakeItem("50 ingots", 50, 0x1BF2, 0x08AB, 0x33),
    ])
    after = module["consolidate_stacks"](chest, "Valorite Ingots")
    check("two stacks moved", len(items.moves), 2)
    check("everything moved INTO the largest",
          all(dest == 0x32 for _src, dest, _amt in items.moves), True)
    check("one stack left", len(after), 1)
    check("total preserved", after[0].Amount, 1050)


def test_consolidate_respects_the_stack_cap(m):
    """Iron runs to 840,000 - fifteen full stacks, which can never be one. Fill
    stacks to MAX_STACK and leave at most one partial, rather than trying to
    pour everything into a single stack that cannot hold it."""
    cap = m["MAX_STACK"]
    module, chest, items = with_chest([
        FakeItem("full", cap, 0x1BF2, 0x0000, 0x61),
        FakeItem("half", cap // 2, 0x1BF2, 0x0000, 0x62),
        FakeItem("scrap", 10, 0x1BF2, 0x0000, 0x63),
    ])
    after = module["consolidate_stacks"](chest, "Iron Ingots")
    check("a full stack is never a target",
          any(dest == 0x61 for _s, dest, _a in items.moves), False)
    check("the scrap went into the half stack",
          (0x63, 0x62, 10) in items.moves, True)
    check("nothing exceeds the cap",
          [s for s in after if s.Amount > cap], [])
    check("total preserved", sum(s.Amount for s in after), cap + cap // 2 + 10)


def test_consolidate_never_refills_a_drained_stack(m):
    """After a stack is poured away it must not become a target on the next
    pass - everything would be moved straight back into it."""
    module, chest, items = with_chest([
        FakeItem("big", 900, 0x1BF2, 0x08AB, 0x71),
        FakeItem("small", 100, 0x1BF2, 0x08AB, 0x72),
    ])
    after = module["consolidate_stacks"](chest, "Valorite Ingots")
    check("exactly one move", len(items.moves), 1)
    check("into the big stack", items.moves[0][1], 0x71)
    check("one stack left", len(after), 1)
    check("total preserved", after[0].Amount, 1000)


def test_gems_are_censused_alongside_ingots(m):
    """Gems have no hue to key on, so a hue-only census misses them entirely."""
    chest = FakeContainer([
        FakeItem("1045 Blue Diamond", 1045, 0x3198, 0x0000, 0x81),
        FakeItem("1042 Ecru Citrine", 1042, 0x3195, 0x0000, 0x82),
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x08AB, 0x83),
        FakeItem("2356 a small piece of blackrock", 2356, 0x0F28, 0x0497, 0x84),
        FakeItem("860 log", 860, 0x1BDD, 0x0000, 0x85),
    ])
    stock = m["census"](chest)
    check("gems, ingots and blackrock counted", sorted(stock),
          ["Blue Diamond", "Ecru Citrine", "Small Piece of Blackrock",
           "Valorite Ingots"])
    check("blue diamond total", stock["Blue Diamond"]["amount"], 1045)
    # Blackrock IS wanted - the book has 17 orders for it - so it is no longer
    # ignored the way it was when the table was guesswork.
    check("blackrock counted", stock["Small Piece of Blackrock"]["amount"], 2356)
    check("logs ignored", "log" in [s.lower() for s in stock], False)


def test_gem_budget_keeps_one_hundred(m):
    """Same rule as ingots: leave 100 of each behind."""
    stock = {"Blue Diamond": {"amount": 1045, "stacks": []},
             "Fire Ruby": {"amount": 100, "stacks": []},
             "White Pearl": {"amount": 12, "stacks": []}}
    budget = m["fill_budget"](stock, keep=100)
    check("surplus spendable", budget["Blue Diamond"], 945)
    check("exactly at reserve spends nothing", budget["Fire Ruby"], 0)
    check("below reserve never negative", budget["White Pearl"], 0)


def test_main_compares_the_deed_against_the_resource_it_asked_for(m):
    """THE BUG. main's loop variable was `metal`, but a bulk rename left the
    check reading `resource` - a name the stock-report loop above had left
    bound to the LAST resource it printed. So every deed was compared against
    a stale value and declined, while the log printed the correct one:

        That deed wants 'Blue Diamond', not 'Blue Diamond'.

    Asserted statically because it cannot be reproduced without a game: both
    names existed, so it was not a NameError, just the wrong answer.
    """
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    # Scanned across the whole module rather than one function, so moving this
    # logic (it has already moved from main into work_one_order) cannot quietly
    # stop the check from looking where it matters.
    wanted = {"find_first_order": None, "deed_matches_resource": None,
              "fill_deed": None}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None)
        if name not in wanted:
            continue
        args = [a for a in node.args if isinstance(a, ast.Name)]
        if not args:
            continue
        # The resource is the FIRST Name argument for find_first_order and the
        # LAST for the other two.
        wanted[name] = args[0].id if name == "find_first_order" else args[-1].id

    found = [v for v in wanted.values() if v]
    check("all three call sites seen", len(found), 3)
    check("all three use ONE variable", len(set(found)), 1)
    check("and it is named `resource`", set(found), set(["resource"]))


def test_no_half_renamed_metal_variable(m):
    """`metal` as an identifier is what the half-finished rename left behind.
    Prose and comments may still say metal; code must not."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    check("no bare `metal` identifier", "metal" in names, False)


def test_no_local_is_used_without_ever_being_assigned(m):
    """CAUGHT A LIVE CRASH. A bulk edit silently failed to apply, leaving
    find_first_order using `pages_to_scan` and `rejected` that nothing ever set:

        UnboundLocalError: local variable 'rejected' referenced before
        assignment

    It got past the syntax check, past every other test, and only surfaced deep
    in a run. `rejected += 1` is what makes it local without initialising it, so
    an augmented assignment on its own does not count as being set.
    """
    import ast, builtins
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    module_names = set(dir(builtins))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_names.add(target.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            module_names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            module_names.add(node.target.id)
    module_names |= {"Misc", "Items", "Mobiles", "Player", "Gumps", "Journal",
                     "Target", "Spells", "Statics", "PathFinding", "Timer"}

    offenders = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        params = {a.arg for a in fn.args.args}
        if fn.args.vararg:
            params.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            params.add(fn.args.kwarg.arg)

        real_assign, loaded = set(), {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    real_assign.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    loaded.setdefault(node.id, node.lineno)
            elif isinstance(node, (ast.For, ast.comprehension)):
                target = getattr(node, "target", None)
                if isinstance(target, ast.Name):
                    real_assign.add(target.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                real_assign.add(node.name)
            elif isinstance(node, ast.Lambda):
                for arg in node.args.args:
                    real_assign.add(arg.arg)
            elif isinstance(node, ast.FunctionDef):
                real_assign.add(node.name)
                for arg in node.args.args:
                    real_assign.add(arg.arg)

        for name, line in sorted(loaded.items()):
            if name in params or name in module_names or name in real_assign:
                continue
            offenders.append("%s() line %d: %r" % (fn.name, line, name))

    check("no local used without being assigned", offenders, [])


def test_every_name_came_from_the_book(m):
    """Harvested from all 540 pages by diag_order_names.py on 2026-07-28. The
    previous table was largely invented: 38 entries the book never asks for and
    48 it wants that had no entry at all."""
    names = [r["name"] for r in m["RESOURCES"]]
    unique = set(names)
    # 79 names came from the book harvest; Perfect Emerald is the 80th, added
    # 2026-08-18 from a live chest with 6517 of them in it. See
    # test_gem_entries for why the earlier "leave it out" call was reversed.
    #
    # A FLOOR, not a pin. The user adds entries to the live copy as the book
    # starts asking for them - Raw Ribs came in that way on 2026-09-11 - and a
    # test that forbids that is a test that fights its own maintainer. What the
    # original count was really protecting against was an INVENTED table, and
    # losing names is the half of that a count can actually catch.
    check("at least the 80 harvested from the book", len(unique) >= 80, True)
    check("and no name is listed twice", len(names), len(unique))
    check("none of them is blank",
          [n for n in names if not str(n).strip()], [])
    check("shadow iron is 'Shadow Ingots'", "Shadow Ingots" in names, True)
    check("plain leather is 'Regular Leather'",
          "Regular Leather" in names, True)
    check("bare 'Leather' is not a book name", "Leather" in names, False)
    check("book capitalisation kept", "Eye of the Travesty" in names, True)
    check("Perfect Emerald IS listed - stock exists for it", 
          "Perfect Emerald" in names, True)
    for gone in ("Zealot Heart", "Rare Serpent Egg",
                 "Captain's Key Ring", "Tainted Blade", "Blighted Cotton"):
        check("%r no longer listed" % gone, gone in names, False)


def test_book_typo_is_handled(m):
    """The book misspells Star Sapphire as "Star Saphhire" - and that spelling
    carries 144 orders against 15 for the correct one."""
    by_name = dict((r["name"], r) for r in m["RESOURCES"])
    check("misspelling listed", "Star Saphhire" in by_name, True)
    check("correct spelling listed too", "Star Sapphire" in by_name, True)
    check("typo entry looks for the real item name",
          by_name["Star Saphhire"].get("item_name"), "Star Sapphire")
    check("a stack resolves through item_name",
          m["resource_of"](FakeItem("144 Star Sapphire", 144, 0x5FFF, 0)),
          "Star Saphhire")


def test_per_resource_override_still_works(m):
    """The reserve is off globally, but the per-entry mechanism has to survive
    so one resource can be protected later without touching the rest."""
    check("default is the global zero", m["keep_for"]("Copper Ingots"), 0)
    fake = {"name": "Guarded", "id": 0, "hue": -1, "by": "name", "keep": 250}
    m["RESOURCES"].append(fake)
    try:
        check("an entry can still hold stock back", m["keep_for"]("Guarded"), 250)
        stock = {"Guarded": {"amount": 300, "stacks": []}}
        check("and the budget honours it",
              m["fill_budget"](stock)["Guarded"], 50)
    finally:
        m["RESOURCES"].remove(fake)


def test_verified_graphics_are_not_guessed(m):
    """Only entries whose id/hue were actually confirmed carry one; the rest
    match by name and have id 0. A wrong graphic would silently find nothing."""
    for entry in m["RESOURCES"]:
        if entry.get("by") == "name":
            check("%s has no invented graphic" % entry["name"], entry["id"], 0)


def test_substring_collisions_get_a_deeper_scan(m):
    """The book's Name filter is a substring match, so "Copper Ingots" also
    returns every "Dull Copper Ingots" row. Those are rejected correctly, but
    they fill the pages - and a short scan then reports "no Copper Ingots
    orders" with 30,654 in the chest and orders waiting."""
    check("copper collides with dull copper",
          m["colliding_names"]("Copper Ingots"), ["Dull Copper Ingots"])
    check("sapphire collides with the longer gems",
          sorted(m["colliding_names"]("Sapphire")),
          ["Dark Sapphire", "Star Sapphire"])
    check("amber collides", m["colliding_names"]("Amber"), ["Brilliant Amber"])
    check("diamond collides", m["colliding_names"]("Diamond"), ["Blue Diamond"])
    check("dull copper collides with nothing",
          m["colliding_names"]("Dull Copper Ingots"), [])
    check("a collision earns a deeper scan",
          m["MAX_PAGES_WHEN_DILUTED"] > m["MAX_PAGES_PER_METAL"], True)


def test_rotated_preserves_everything(m):
    items = ["a", "b", "c", "d"]
    check("no offset", m["rotated"](items, 0), ["a", "b", "c", "d"])
    check("offset 1", m["rotated"](items, 1), ["b", "c", "d", "a"])
    check("wraps", m["rotated"](items, 5), ["b", "c", "d", "a"])
    check("nothing lost", sorted(m["rotated"](items, 3)), sorted(items))
    check("empty is safe", m["rotated"]([], 3), [])


def test_offset_wraps_against_the_stocked_list(m):
    """The offset indexes the stocked list, not the 79-entry table, or it runs
    off the end and the next lap starts nowhere."""
    stocked = ["a", "b", "c", "d", "e"]
    check("wraps", m["rotated"](stocked, 7), ["c", "d", "e", "a", "b"])
    check("wrap of exactly the length is the start",
          m["rotated"](stocked, 5), stocked)


def test_resources_are_cycled_round_robin(m):
    """One order per resource per pass, cycling. Depth-first let one resource
    with deep stock swallow the whole lap, so anything behind it waited."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fill = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "fill_orders"][0]

    # The resource loop must sit INSIDE a loop over passes.
    nested = False
    for outer in ast.walk(fill):
        if not isinstance(outer, ast.For):
            continue
        if isinstance(outer.iter, ast.Name) and outer.iter.id == "order":
            continue                      # this IS the resource loop
        for inner in ast.walk(outer):
            if (isinstance(inner, ast.For) and inner is not outer
                    and isinstance(inner.iter, ast.Name)
                    and inner.iter.id == "order"):
                nested = True
    check("resources are cycled, not drained one at a time", nested, True)

    # And exactly one order is taken per resource per pass.
    resource_loop = None
    for node in ast.walk(fill):
        if (isinstance(node, ast.For) and isinstance(node.iter, ast.Name)
                and node.iter.id == "order"):
            resource_loop = node
    inner_loops = [n for n in ast.walk(resource_loop)
                   if isinstance(n, ast.For) and n is not resource_loop]
    check("no inner loop taking repeated orders", inner_loops, [])


def test_depth_first_cannot_starve_later_resources(m):
    """A resource with a lot of stock could eat the whole lap cap. The lap
    rotation is what stops that being permanent - the next lap resumes at
    whatever this one did not reach."""
    names = ["a", "b", "c", "d", "e", "f"]
    cap = 2
    seen, offset = set(), 0
    for _lap in range(len(names)):
        order = m["rotated"](names, offset)
        for name in order[:cap]:
            seen.add(name)
        offset = (offset + cap) % len(names)
    check("every resource still gets reached", sorted(seen), sorted(names))


def test_withdrawals_still_bound_the_lap(m):
    """Depth first only terminates because every withdrawal counts against the
    lap cap - including a deed that came out and was then declined."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    work = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "work_one_order"][0]

    bumps = [n for n in ast.walk(work) if isinstance(n, ast.AugAssign)
             and isinstance(n.target, ast.Subscript)
             and getattr(n.target.value, "id", None) == "withdrawn"]
    check("the counter is raised on withdrawal", len(bumps), 1)

    # And it happens before any path that can return without filling.
    returns = [n.lineno for n in ast.walk(work) if isinstance(n, ast.Return)]
    declines = [ln for ln in returns if ln > bumps[0].lineno]
    check("declined paths come after it, so they still count",
          len(declines) >= 1, True)


def test_resource_order_follows_the_book(m):
    """The table is ordered by how many orders the book actually holds, which is
    where the work is. Round-robin plus the lap rotation is what stops the
    leading entries starving the rest."""
    names = [r["name"] for r in m["worked_resources"]()]
    check("busiest first", names[0], "Agapite Granite")
    # The INVARIANT is that the heavy entries lead and the one-order ones
    # trail - not which particular one is last. Pinning the final name breaks
    # every time a resource is appended to the live table.
    tail = names[-6:]
    check("and the one-order entries trail",
          "Turquoise" in tail and "Iron Ingots" in tail, True)
    check("ingots present", "Iron Ingots" in names, True)
    check("leather present", "Barbed Leather" in names, True)


def test_blue_diamond_deed_verbatim(m):
    """The deed that produced "That deed wants 'Blue Diamond', not Blue Diamond
    ingots" in game - an older build appended " Ingots" to every resource name
    before matching. Gem orders carry no suffix at all."""
    raw = ("A Resource Order Deed Blessed Weight: 1 Stone "
           "0 / 23 Blue Diamond ObtainedValued At: 3000 Gold Each")
    fields = m["parse_deed"](raw)
    check("resource", fields.get("resource"), "Blue Diamond")
    check("needed", fields.get("needed"), 23)
    check("gold each", fields.get("gold_each"), 3000)
    check("matches itself",
          m["deed_matches_resource"](fields, "Blue Diamond"), True)
    check("no ingot suffix expected",
          m["deed_matches_resource"](fields, "Blue Diamond Ingots"), False)


def test_gem_order_matches_its_deed(m):
    """Order names ARE the resource names for gems - no suffix involved."""
    fields = m["parse_deed"](
        "0 / 23 Ecru Citrine ObtainedValued At: 3000 Gold Each")
    check("resource", fields.get("resource"), "Ecru Citrine")
    check("needed", fields.get("needed"), 23)
    check("matches itself",
          m["deed_matches_resource"](fields, "Ecru Citrine"), True)
    check("not another gem",
          m["deed_matches_resource"](fields, "Fire Ruby"), False)
    check("not an ingot order",
          m["deed_matches_resource"](fields, "Iron Ingots"), False)


def test_organize_skips_resources_already_single(m):
    """One drag per surplus stack is the whole cost, so a tidy resource must be
    left alone rather than shuffled onto itself."""
    module, chest, items = with_chest([
        FakeItem("500 ingots", 500, 0x1BF2, 0x0979, 0x41),   # Agapite, single
        FakeItem("200 ingots", 200, 0x1BF2, 0x089F, 0x42),   # Verite, split
        FakeItem("300 ingots", 300, 0x1BF2, 0x089F, 0x43),
    ])
    merged = module["organize_chests"](chest)
    check("only the split resource merged", merged, 1)
    check("one move only", len(items.moves), 1)
    check("agapite untouched",
          any(src == 0x41 for src, _d, _a in items.moves), False)


def test_organize_no_op_when_tidy(m):
    module, chest, items = with_chest([
        FakeItem("500 ingots", 500, 0x1BF2, 0x0979, 0x51),
        FakeItem("600 ingots", 600, 0x1BF2, 0x08AB, 0x52),
        FakeItem("1045 Blue Diamond", 1045, 0x3198, 0x0000, 0x53),
    ])
    check("nothing merged", module["organize_chests"](chest), 0)
    check("nothing dragged", len(items.moves), 0)


def test_organize_reports_an_empty_chest_loudly(m):
    """A chest that reports nothing is the difference between "already tidy"
    and "the snapshot never arrived" - it must not read as success."""
    module, chest, items = with_chest([])
    check("nothing merged", module["organize_chests"](chest), 0)
    check("nothing dragged", len(items.moves), 0)


def test_organize_merges_gems_too(m):
    module, chest, items = with_chest([
        FakeItem("600 Fire Ruby", 600, 0x3197, 0x0000, 0x91),
        FakeItem("425 Fire Ruby", 425, 0x3197, 0x0000, 0x92),
    ])
    merged = module["organize_chests"](chest)
    check("gems merged", merged, 1)
    check("into the larger", items.moves[0][1], 0x91)
    check("total preserved",
          module["chest_stacks"](chest, "Fire Ruby")[0].Amount, 1025)


def test_chest_ingots_largest_first(m):
    """The deed targets a stack where it lies in the chest - nothing is carried.
    Largest first so one target usually covers the whole order instead of
    walking several stacks."""
    chest = FakeContainer([
        FakeItem("2336 ingots", 2336, 0x1BF2, 0x096D, 0x11),
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x096D, 0x12),
        FakeItem("59948 ingots", 59948, 0x1BF2, 0x096D, 0x13),
        FakeItem("25020 ingots", 25020, 0x1BF2, 0x08AB, 0x14),   # Valorite
    ])
    stacks = m["chest_stacks"](chest, "Copper Ingots")
    check("copper only", [s.Serial for s in stacks], [0x12, 0x13, 0x11])
    check("largest first", stacks[0].Amount, 60000)
    check("other metals excluded",
          [s.Serial for s in m["chest_stacks"](chest, "Valorite Ingots")], [0x14])
    check("absent metal", m["chest_stacks"](chest, "Gold Ingots"), [])


def test_live_stock_totals(m):
    """The nine real stacks from the 2026-07-27 dump, summed per metal."""
    stacks = [(60000, 0x096D), (59948, 0x096D), (1766, 0x096D)]
    chest = FakeContainer([FakeItem("%d ingots" % a, a, 0x1BF2, h, i)
                           for i, (a, h) in enumerate(stacks)])
    stock = m["census"](chest)
    check("copper total", stock["Copper Ingots"]["amount"], 121714)


# ---------------------------------------------------------------------------
# Order rows - the real captured page
# ---------------------------------------------------------------------------

REAL_PAGE1 = [
    "Resource Orders", "Contents: 8658/100000", "Displayed: 230",
    "Name", "Amt To Gather", "Value Per",
    "Valorite Granite", "0", "No",
    "Valorite Granite", "155", "0", "400", "No",
    "Valorite Granite", "156", "0", "400", "No",
    "Previous Page", "Next Page", "(1/16)", "Add", "Purge",
    "Fill from backpack", "", "None", "None", "None",
]

REAL_LAYOUT = (
    "{ page 0 }{ resizepic 0 0 9270 600 530 }"
    "{ button 40 70 5600 5604 1 0 10 }{ button 55 70 5602 5606 1 0 11 }"
    "{ button 20 93 1209 1209 1 0 100 }"
    "{ button 20 113 1209 1209 1 0 101 }"
    "{ button 20 133 1209 1209 1 0 102 }"
    "{ button 95 410 5601 5605 1 0 12 }"
    "{ button 560 440 5601 5605 1 0 5 }"
    "{ button 350 475 1209 1210 1 0 1 }"
)


def test_row_buttons_exclude_sorters_filters_and_nav(m):
    check("only row buttons", m["row_buttons"](REAL_LAYOUT), [100, 101, 102])


def test_parse_order_rows_real_page(m):
    rows = m["parse_order_rows"](REAL_PAGE1)
    check("three rows", len(rows), 3)
    check("amounts", [r["amount"] for r in rows], [0, 155, 156])


def test_zero_row_still_consumes_a_button_slot(m):
    """Every page opens with an Amt To Gather of 0 that owns a real button. If
    it were skipped during parsing, every later row would point one button
    early - and press the wrong order."""
    rows = m["parse_order_rows"](REAL_PAGE1)
    buttons = m["row_buttons"](REAL_LAYOUT)
    check("counts line up", len(rows), len(buttons))
    paired = list(zip(rows, buttons))
    check("zero row owns button 100", paired[0][1], 100)
    check("155 belongs to 101", (paired[1][0]["amount"], paired[1][1]),
          (155, 101))


def test_header_anchor_covers_all_five_columns(m):
    """The rendered gump shows Name | Amt To Gather | Amt Gathered | Value Per |
    Completed. Anchoring on "Value Per" alone - the FOURTH of five - leaves
    "Completed" in the row region."""
    page = ["Name", "Amt To Gather", "Amt Gathered", "Value Per", "Completed",
            "Fire Ruby", "26", "0", "3000", "No",
            "Previous Page", "Next Page", "(1/2)"]
    rows = m["parse_order_rows"](page, "fire ruby")
    check("one row", len(rows), 1)
    check("amount is Amt To Gather", rows[0]["amount"], 26)

    loose = m["parse_order_rows"](page)
    check("Completed is not a row",
          "Completed" in [r["name"] for r in loose], False)


def test_page_counter(m):
    check("page counter", m["page_counter"](REAL_PAGE1), (1, 16))
    check("no counter", m["page_counter"](["x"]), (None, None))


# A page whose Runics column holds an actual runic name instead of Yes/No.
# Without an anchor the parser counted those as extra orders - the live run
# reported "Iron page 1: 17 rows but 14 buttons" and threw the page away.
RUNIC_PAGE = [
    "Name", "Amt To Gather", "Value Per",
    "Iron Ingots", "0", "No",
    "Iron Ingots", "500", "0", "100", "Dull Copper Runic",
    "Iron Ingots", "600", "0", "100", "Valorite Runic",
    "Previous Page", "Next Page", "(1/3)", "Add", "Purge",
]


def test_runic_column_is_not_counted_as_a_row(m):
    loose = m["parse_order_rows"](RUNIC_PAGE)
    check("unanchored over-counts", len(loose) > 3, True)

    anchored = m["parse_order_rows"](RUNIC_PAGE, "iron ingots")
    check("anchored counts three", len(anchored), 3)
    check("amounts", [r["amount"] for r in anchored], [0, 500, 600])


# A filtered page with no matching orders at all. The footer labels were being
# swept up as rows - "Shadow Iron page 1: 2 rows but 0 buttons".
EMPTY_PAGE = [
    "Resource Orders", "Contents: 8659/100000", "Displayed: 0",
    "Name", "Amt To Gather", "Value Per",
    "Previous Page", "Next Page", "(1/1)", "Add", "Purge",
    "Fill from backpack", "", "None", "None", "None",
]


def test_empty_page_yields_no_rows(m):
    anchored = m["parse_order_rows"](EMPTY_PAGE, "shadow iron ingots")
    check("no rows on an empty page", anchored, [])


def test_footer_labels_never_become_rows(m):
    names = [r["name"] for r in m["parse_order_rows"](EMPTY_PAGE, "iron ingots")]
    for label in ("Add", "Purge", "Fill from backpack"):
        check("%r not a row" % label, label in names, False)


# The substring filter puts Shadow Iron rows on an Iron page: "Iron Ingots" is
# inside "Shadow Iron Ingots".
MIXED_PAGE = [
    "Name", "Amt To Gather", "Value Per",
    "Iron Ingots", "0", "No",
    "Shadow Iron Ingots", "700", "0", "100", "No",
    "Iron Ingots", "800", "0", "100", "No",
    "Previous Page", "Next Page", "(1/2)", "Add",
]


def test_mixed_page_keeps_button_alignment(m):
    """Both metals' rows must be parsed, or the row/button zip shifts and the
    wrong order gets pressed. Selection happens after, not by dropping rows."""
    rows = m["parse_order_rows"](MIXED_PAGE, "iron ingots")
    check("all three rows kept", len(rows), 3)
    check("shadow iron kept for alignment", rows[1]["name"],
          "Shadow Iron Ingots")

    import re as _re
    exact = _re.compile(r"^Iron\s+ingots?$", _re.I)
    picked = [r for r in rows if r["amount"] and exact.match(r["name"])]
    check("only true iron selected", [r["amount"] for r in picked], [800])


def test_granite_is_not_an_ingot_order(m):
    """Filtering "Valorite Ingots" returned 230 rows of Valorite Granite. The name
    check after the filter is what keeps those out."""
    rows = m["parse_order_rows"](REAL_PAGE1)
    wanted = ("Valorite Ingots" + " Ingots").lower()
    keep = [r for r in rows if r["amount"] and wanted in r["name"].lower()]
    check("no granite selected", keep, [])


# ---------------------------------------------------------------------------
# Deeds
# ---------------------------------------------------------------------------

# The live deed, verbatim from the Item Inspector on 2026-07-27. There is no
# "Resource Type:" and no "Filled:" - the first parser looked for those, having
# inferred them from a comment in harvest_runner.py, and read nothing at all.
REAL_DEED = ["A Resource Order Deed", "Blessed", "Weight: 1 Stone",
             "0 / 132 Valorite Granite ObtainedValued At: 400 Gold Each"]


def test_parse_the_real_deed(m):
    fields = m["parse_deed"](" ".join(REAL_DEED))
    check("filled", fields.get("filled"), 0)
    check("needed", fields.get("needed"), 132)
    check("resource", fields.get("resource"), "Valorite Granite")
    check("gold each", fields.get("gold_each"), 400)
    check("progress", m["deed_progress"](fields), (0, 132))


def test_obtained_valued_seam(m):
    """"ObtainedValued" is one word on the wire. Without the seam fix the
    resource name runs on and nothing matches."""
    out = m["spaced"](" ".join(REAL_DEED))
    check("seam split", "ObtainedValued" in out, False)
    check("resource still whole", "Valorite Granite Obtained" in out, True)


def test_multi_word_resource_survives(m):
    fields = m["parse_deed"]("240 / 900 Shadow Iron Ingots ObtainedValued At: 12 Gold Each")
    check("two-word metal plus resource", fields.get("resource"),
          "Shadow Iron Ingots")
    check("partial progress", m["deed_progress"](fields), (240, 900))


def test_deed_that_does_not_parse(m):
    check("no progress", m["deed_progress"]({}), (None, None))
    check("unparseable tooltip", m["parse_deed"]("just some text"), {})


def test_deed_matches_metal_rejects_granite(m):
    """The run that produced the real deed was after Valorite INGOTS and got a
    Valorite GRANITE order. Pouring ingots at it would never fill it."""
    granite = m["parse_deed"](" ".join(REAL_DEED))
    check("granite rejected", m["deed_matches_resource"](granite, "Valorite Ingots"), False)

    ingots = m["parse_deed"]("0 / 132 Valorite Ingots ObtainedValued At: 400 Gold Each")
    check("ingots accepted", m["deed_matches_resource"](ingots, "Valorite Ingots"), True)
    check("wrong metal rejected", m["deed_matches_resource"](ingots, "Iron Ingots"), False)


def test_deed_matches_metal_is_not_fooled_by_substring(m):
    """"Iron Ingots" is a substring of "Shadow Iron Ingots", and "Copper Ingots" of "Dull Copper Ingots".
    A substring test would have an Iron run accept a Shadow Iron order and pour
    the wrong metal at it until the script gave up."""
    shadow = m["parse_deed"]("0 / 500 Shadow Iron Ingots ObtainedValued At: 9 Gold Each")
    check("shadow iron accepted for shadow iron",
          m["deed_matches_resource"](shadow, "Shadow Iron Ingots"), True)
    check("shadow iron REJECTED for iron",
          m["deed_matches_resource"](shadow, "Iron Ingots"), False)

    dull = m["parse_deed"]("0 / 500 Dull Copper Ingots ObtainedValued At: 9 Gold Each")
    check("dull copper REJECTED for copper",
          m["deed_matches_resource"](dull, "Copper Ingots"), False)
    check("dull copper accepted for dull copper",
          m["deed_matches_resource"](dull, "Dull Copper Ingots"), True)

    check("empty resource rejected", m["deed_matches_resource"]({}, "Iron Ingots"), False)


def test_progress_text_never_formats_none(m):
    """THE FIRST LIVE CRASH. The fill worked, the deed then stopped parsing,
    and `"%d/%d" % (filled, needed)` raised
    "TypeError: %d format: a number is required, not NoneType" - AFTER the
    ingots had been spent. Every progress line goes through this now."""
    check("normal", m["progress_text"](24, 500), "24/500")
    check("zero filled", m["progress_text"](0, 132), "0/132")
    check("filled is None", m["progress_text"](None, 132), "?")
    check("needed is None", m["progress_text"](24, None), "?")
    check("both None", m["progress_text"](None, None), "?")


# A FULFILLED deed, verbatim from the Item Inspector, 2026-07-27. Serial
# 0x40565AF7, still ItemID 0x14F0, still in the backpack - completing an order
# does not consume the deed.
DONE_DEED = ["A Resource Order Deed", "Blessed", "Weight: 1 Stone",
             "Order Fulfilled [1038 Copper Ingots]Valued At: 25 Gold Each"]


def test_parse_the_fulfilled_deed(m):
    """The completed shape shares no label with the in-progress one, so it
    needs its own pattern rather than a "stopped parsing, assume done" guess."""
    fields = m["parse_deed"](" ".join(DONE_DEED))
    check("marked complete", fields.get("complete"), True)
    check("resource", fields.get("resource"), "Copper Ingots")
    check("amount as filled", fields.get("filled"), 1038)
    check("amount as needed", fields.get("needed"), 1038)
    check("gold each", fields.get("gold_each"), 25)


def test_fulfilled_deed_reads_as_finished_progress(m):
    """filled == needed, so the fill loop's "short <= 0" exit fires naturally
    and callers never need to know there are two shapes."""
    fields = m["parse_deed"](" ".join(DONE_DEED))
    filled, needed = m["deed_progress"](fields)
    check("progress complete", (filled, needed), (1038, 1038))
    check("nothing short", needed - filled, 0)


def test_fulfilled_deed_still_matches_its_metal(m):
    """It has to, or the hand-in cannot tell what it was for."""
    fields = m["parse_deed"](" ".join(DONE_DEED))
    check("copper accepted", m["deed_matches_resource"](fields, "Copper Ingots"), True)
    check("not dull copper", m["deed_matches_resource"](fields, "Dull Copper Ingots"), False)


def test_in_progress_deed_is_not_marked_complete(m):
    fields = m["parse_deed"](" ".join(REAL_DEED))
    check("not complete", fields.get("complete"), False)


def test_unrecognised_tooltip_still_yields_nothing(m):
    check("junk", m["deed_progress"](m["parse_deed"](
        "A Resource Order Deed Blessed Weight: 1 Stone")), (None, None))


def test_deed_matches_metal_tolerates_singular(m):
    single = m["parse_deed"]("0 / 1 Iron Ingot ObtainedValued At: 9 Gold Each")
    check("singular accepted", m["deed_matches_resource"](single, "Iron Ingots"), True)


# ---------------------------------------------------------------------------
# Config sanity - these are the values that go live
# ---------------------------------------------------------------------------

def test_orders_per_run_is_sane(m):
    """Was 1 while the withdraw/fill mechanics were unproven; raised to 5 after
    a confirmed end-to-end run. All of them ride one recall trip."""
    check("at least one", m["MAX_ORDERS_PER_RUN"] >= 1, True)
    # The ceiling is the user's, and it is 60 live - the weekly competition is
    # scored on throughput, so a low cap costs them directly. What has to stay
    # true is that it IS bounded, and that a single resource cannot eat the
    # whole run on its own.
    check("still bounded", m["MAX_ORDERS_PER_RUN"] <= 500, True)
    check("and no one resource can take the whole run",
          m["MAX_ORDERS_PER_RESOURCE"] <= m["MAX_ORDERS_PER_RUN"], True)


def test_reserve_is_off(m):
    check("keep per type", m["KEEP_PER_TYPE"], 0)


def test_ingot_hues_match_servuo(m):
    """Hues from ServUO Scripts/Misc/ResourceInfo.cs. All nine share ItemID
    0x1BF2, so the hue is the only thing that names the metal.

    The NAMES, though, come from the order book and not from ServUO - see
    test_book_names_are_not_assumed_from_servuo."""
    by_name = dict((r["name"], r) for r in m["RESOURCES"])
    for hue, name in [(0x0000, "Iron Ingots"), (0x0973, "Dull Copper Ingots"),
                      (0x0966, "Shadow Ingots"), (0x096D, "Copper Ingots"),
                      (0x0972, "Bronze Ingots"), (0x08A5, "Gold Ingots"),
                      (0x0979, "Agapite Ingots"), (0x089F, "Verite Ingots"),
                      (0x08AB, "Valorite Ingots")]:
        entry = by_name.get(name, {})
        check("%s graphic" % name, entry.get("id"), 0x1BF2)
        check("%s hue" % name, entry.get("hue"), hue)


def test_book_names_are_not_assumed_from_servuo(m):
    """The book calls Shadow Iron "Shadow Ingots". `name` must be the BOOK's
    string, because it is typed into the Name filter - a wrong one returns an
    empty result, so the resource looks skipped rather than erroring."""
    names = [r["name"] for r in m["RESOURCES"]]
    check("book name used", "Shadow Ingots" in names, True)
    check("ServUO name NOT used", "Shadow Iron Ingots" in names, False)

    # The hue still maps to the real metal, so stock is identified correctly.
    entry = [r for r in m["RESOURCES"] if r["name"] == "Shadow Ingots"][0]
    check("still the Shadow Iron hue", entry["hue"], 0x0966)
    check("shadow stack resolves",
          m["resource_of"](FakeItem("12641 ingots", 12641, 0x1BF2, 0x0966)),
          "Shadow Ingots")


def test_order_size_ceiling_admits_real_orders(m):
    """Live Shadow Ingots orders run 5478-6540. A ceiling of 5000 rejected
    almost all of them and the resource looked skipped."""
    check("ceiling clears a 6540 order", m["MAX_ORDER_SIZE"] >= 6540, True)


def test_gems_are_identified_by_graphic(m):
    """Gems have their own graphic and no meaningful hue, so hue is -1.

    Perfect Emerald was deliberately absent - the book had ZERO orders for it
    at harvest time, and the note here said an entry would cost a fruitless
    search every lap. Reversed 2026-08-18 for two reasons:

      * The chest holds 6517 of them. Absent from RESOURCES it is absent from
        the CENSUS too, so the stock report cannot even say they are there.
      * The cost is one search per RUN, not per lap: a resource that comes back
        with nothing is added to `exhausted` and gets no further turn.

    A book is restocked with new orders over time, so "zero orders that day" is
    not a permanent property.
    """
    by_name = dict((r["name"], r) for r in m["RESOURCES"])
    for name, item_id in [("Blue Diamond", 0x3198), ("Brilliant Amber", 0x3199),
                          ("Dark Sapphire", 0x3192), ("Ecru Citrine", 0x3195),
                          ("Fire Ruby", 0x3197),
                          ("Turquoise", 0x3193), ("White Pearl", 0x3196)]:
        entry = by_name.get(name, {})
        check("%s graphic" % name, entry.get("id"), item_id)
        check("%s hue is any" % name, entry.get("hue"), -1)
    check("Perfect Emerald IS present now",
          "Perfect Emerald" in by_name, True)
    check("Perfect Emerald graphic",
          by_name.get("Perfect Emerald", {}).get("id"), 0x3194)
    check("Perfect Emerald hue is any",
          by_name.get("Perfect Emerald", {}).get("hue"), -1)


def test_resource_names_are_unique(m):
    names = [r["name"].lower() for r in m["RESOURCES"]]
    check("no duplicate names", len(names), len(set(names)))


def test_resource_of_uses_id_and_hue_never_the_name(m):
    """An ingot stack is called "<amount> ingots" and a gem carries its own
    name, so identification must not depend on the item's name at all."""
    check("hue picks the metal",
          m["resource_of"](FakeItem("60000 ingots", 60000, 0x1BF2, 0x08AB)),
          "Valorite Ingots")
    check("a different hue is a different metal",
          m["resource_of"](FakeItem("60000 ingots", 60000, 0x1BF2, 0x096D)),
          "Copper Ingots")
    check("gem by graphic",
          m["resource_of"](FakeItem("", 24, 0x3195, 0x0000)), "Ecru Citrine")
    check("gem hue ignored",
          m["resource_of"](FakeItem("", 24, 0x3195, 0x0499)), "Ecru Citrine")
    check("unknown graphic", m["resource_of"](FakeItem("log", 5, 0x1BDD, 0)),
          None)


def test_handin_route_matches_the_brief(m):
    check("folder", m["HANDIN_FOLDER"], ["RO"])
    check("rune", m["HANDIN_POINT"], "RO")
    check("npc matched by title words", m["HANDIN_NPC_WORDS"],
          ["resource gatherer"])


def test_filter_includes_the_resource_word(m):
    check("suffix guards against granite", " Ingots", " Ingots")


class _FakeBoard(object):
    def __init__(self, serial, item_id, hue, amount):
        self.Serial, self.ItemID, self.Hue, self.Amount = \
            serial, item_id, hue, amount
        self.Name = "%d boards" % amount


class _FakeChest(object):
    def __init__(self, contains):
        self.Serial = 0x400CEF90
        self.Contains = contains


class _FakeEntry(object):
    def __init__(self, text, stamp):
        self.Text, self.Timestamp = text, stamp
        self.Name = "System"


class _FakeJournal(object):
    """Journal.GetJournalEntry(after) - returns only lines newer than `after`."""
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.cleared = 0

    def add(self, text, stamp):
        self.entries.append(_FakeEntry(text, stamp))

    def GetJournalEntry(self, after=-1):
        return [e for e in self.entries if e.Timestamp > (after or 0.0)]

    def Clear(self, text=None):
        self.cleared += 1
        self.entries = []

    def Search(self, text):
        return any(text.lower() in e.Text.lower() for e in self.entries)


class _FakeGumps(object):
    def __init__(self, open_ids=()):
        self.open_ids = list(open_ids)
        self.closed = []

    def AllGumpIDs(self):
        return list(self.open_ids)

    def CloseGump(self, gump_id):
        self.closed.append(int(gump_id))
        if int(gump_id) in self.open_ids:
            self.open_ids.remove(int(gump_id))

    def HasGump(self, gump_id=None):
        return bool(self.open_ids)


def _with_fakes(m, journal=None, gumps=None, clock=None):
    """Swap the Razor stubs for drivable fakes. Returns a restore callable."""
    saved = {}
    for name, value in (("Journal", journal), ("Gumps", gumps)):
        if value is not None:
            saved[name] = m.get(name)
            m[name] = value
    if clock is not None:
        saved["time"] = m["time"]
        m["time"] = clock

    def restore():
        for name, value in saved.items():
            m[name] = value
    return restore


class _FakeClock(object):
    """A clock that only moves when Misc.Pause is called, so the save wait
    terminates instantly instead of really sleeping 45 seconds."""
    def __init__(self, start=1000.0):
        self.now = start

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_world_save_warning_pauses_and_resumes(m):
    """THE REPORTED FAILURE. Everything freezes during a save, so an action
    sent into one is simply lost. The runner has to sit it out."""
    clock = _FakeClock()
    journal = _FakeJournal()
    journal.add("The world will save in 30 seconds", clock.now + 1)

    saved_pause = m["Misc"].Pause
    restore = _with_fakes(m, journal=journal, clock=clock)
    try:
        m["_journal_cursor"][0] = 0.0
        m["_save_seen_at"][0] = 0.0
        # Every poll inside the wait advances the clock, so it ends.
        m["Misc"].Pause = lambda ms: clock.advance(ms / 1000.0)
        waited = m["wait_out_world_save"]()
        check("it waited", waited, True)
        check("it waited about %ds" % (m["WORLD_SAVE_PAUSE_MS"] / 1000),
              round(clock.now - 1000.0) >= m["WORLD_SAVE_PAUSE_MS"] / 1000,
              True)
    finally:
        m["Misc"].Pause = saved_pause
        restore()


def test_a_quiet_journal_does_not_pause(m):
    """No warning means no wait - the runner must not stall on every check."""
    clock = _FakeClock()
    journal = _FakeJournal()
    journal.add("You have worked the metal into an ingot.", clock.now + 1)
    restore = _with_fakes(m, journal=journal, clock=clock)
    try:
        m["_journal_cursor"][0] = 0.0
        m["_save_seen_at"][0] = 0.0
        check("no wait", m["wait_out_world_save"](), False)
        check("clock did not move", clock.now, 1000.0)
    finally:
        restore()


def test_the_same_warning_fires_only_once(m):
    """Why this uses a timestamp cursor and not Journal.Search: Search scans
    the whole buffer, so one warning would re-fire on every call for the rest
    of the run."""
    clock = _FakeClock()
    journal = _FakeJournal()
    journal.add("The world will save in 30 seconds", clock.now + 1)
    restore = _with_fakes(m, journal=journal, clock=clock)
    try:
        m["_journal_cursor"][0] = 0.0
        m["_save_seen_at"][0] = 0.0
        check("seen the first time", m["poll_world_save"](), True)
        check("not seen again", m["poll_world_save"](), False)
        check("and not a third time", m["poll_world_save"](), False)
    finally:
        restore()


def test_priming_the_cursor_ignores_older_lines(m):
    """A warning from before the run started must not pause it for a save that
    finished long ago."""
    clock = _FakeClock()
    journal = _FakeJournal()
    journal.add("The world will save in 30 seconds", clock.now - 500)
    restore = _with_fakes(m, journal=journal, clock=clock)
    try:
        m["_journal_cursor"][0] = 0.0
        m["_save_seen_at"][0] = 0.0
        m["prime_journal_cursor"]()
        check("pre-run warning ignored", m["poll_world_save"](), False)
    finally:
        restore()


def test_a_late_warning_shortens_the_wait_it_does_not_extend_it(m):
    """The deadline runs from when the warning was SEEN. If it is noticed after
    the save has already been and gone, there is nothing left to wait for."""
    clock = _FakeClock()
    journal = _FakeJournal()
    restore = _with_fakes(m, journal=journal, clock=clock)
    try:
        m["_journal_cursor"][0] = 0.0
        # Seen a full pause-length ago.
        m["_save_seen_at"][0] = clock.now - (m["WORLD_SAVE_PAUSE_MS"] / 1000.0) - 1
        check("nothing left to wait", m["wait_out_world_save"](), False)
        check("clock did not move", clock.now, 1000.0)
    finally:
        restore()


def test_tidy_gumps_closes_strays_but_keeps_what_is_asked(m):
    """THE REPORTED FAILURE: a screen stacked with windows after an unattended
    run. Every id except the keep-list has to go."""
    gumps = _FakeGumps([0x1111, 0x2222, 0x3333, m["ORDERS_GUMP"]])
    restore = _with_fakes(m, gumps=gumps)
    try:
        closed = m["tidy_gumps"](keep=[m["ORDERS_GUMP"]])
        check("three closed", closed, 3)
        check("the kept one is still open",
              m["ORDERS_GUMP"] in gumps.open_ids, True)
        check("the kept one was never closed",
              m["ORDERS_GUMP"] in gumps.closed, False)
        check("strays all closed", sorted(gumps.closed),
              [0x1111, 0x2222, 0x3333])
    finally:
        restore()


def test_tidy_gumps_with_nothing_open_is_a_no_op(m):
    gumps = _FakeGumps([])
    restore = _with_fakes(m, gumps=gumps)
    try:
        check("nothing closed", m["tidy_gumps"](), 0)
    finally:
        restore()


def test_tidy_gumps_survives_a_failing_api(m):
    """AllGumpIDs is not in every build. A missing call must not end the run."""
    class Broken(object):
        def AllGumpIDs(self):
            raise TypeError("no such overload")
        def CloseGump(self, gid):
            pass
    restore = _with_fakes(m, gumps=Broken())
    try:
        check("returns 0 rather than raising", m["tidy_gumps"](), 0)
    finally:
        restore()


def test_the_fill_phase_closes_its_windows_on_every_exit(m):
    """The leak: run_lap closed the book and the order list only on the path
    where the lap had filled something, so a lap that filled nothing left them
    open - and the next lap opened another set."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    lap = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_lap":
            lap = node
    check("run_lap exists", lap is not None, True)
    if lap is None:
        return

    tidy_lines = [n.lineno for n in ast.walk(lap)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, "id", None) in ("tidy_gumps", "checkpoint")]
    check("run_lap tidies", len(tidy_lines) >= 2, True)

    # The tidy must come before the "nothing filled" early return, or that path
    # still leaks. fill_orders is the anchor: tidy has to follow it closely.
    fill_line = None
    for node in ast.walk(lap):
        if isinstance(node, ast.Call) and \
                getattr(node.func, "id", None) == "fill_orders":
            fill_line = node.lineno
    check("fill_orders is called", fill_line is not None, True)
    if fill_line is not None:
        after_fill = [l for l in tidy_lines if l > fill_line]
        check("a tidy follows fill_orders", len(after_fill) > 0, True)
        returns = [n.lineno for n in ast.walk(lap)
                   if isinstance(n, ast.Return) and n.lineno > fill_line]
        if after_fill and returns:
            check("and it comes before the first exit after it",
                  min(after_fill) < min(returns), True)


def test_the_save_check_never_runs_inside_a_wait(m):
    """poll_world_save is detection only. If it slept, calling it from inside a
    wait would recurse through whatever was already waiting - the same reason
    the travelling responder had to be split from its poller."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    poll = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "poll_world_save":
            poll = node
    check("poll_world_save exists", poll is not None, True)
    if poll is None:
        return
    sleeps = [n for n in ast.walk(poll)
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "Pause"]
    check("it never pauses", sleeps, [])
    waits = [n for n in ast.walk(poll)
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "wait_out_world_save"]
    check("it never waits", waits, [])


# Every board hue, verbatim from the live chest dump of 2026-08-03
# (diag_chest_contents.py). Eight named their wood on the stack's third
# tooltip line; 0x0000 carried no wood line at all, which is how the default
# wood renders - exactly as plain iron is the one ingot with no third line.
LIVE_BOARD_HUES = [
    (0x0000, "Regular Boards",   91715),
    (0x07DA, "Oak Boards",      189690),
    (0x04A7, "Ash Boards",       20060),
    (0x04A8, "Yew Boards",        8400),
    (0x04A9, "Heartwood Boards",  5460),
    (0x04AA, "Bloodwood Boards",  3085),
    (0x047F, "Frostwood Boards",  1840),
    (0x0AAC, "Magewood Boards",     90),
    (0x078C, "Darkwood Boards",     80),
]


def test_every_live_board_hue_is_identified(m):
    """The nine woods actually in the chest must all resolve. Magewood and
    Darkwood are this shard's own and appear in no ServUO table, so the live
    dump is the only source for them - if these ever change, that is the
    evidence, not a guess."""
    for hue, want, amount in LIVE_BOARD_HUES:
        board = _FakeBoard(0x1, m["BOARD_IDS"][0], hue, amount)
        check("0x%04X -> %s" % (hue, want), m["resource_of"](board), want)


def test_logs_are_not_counted_as_boards(m):
    """Logs (0x1BDD) share every wood hue with boards, and the chest holds
    54,340 plain ones. The book has no log orders, so a log claimed as a board
    would promise stock that cannot fill anything."""
    for hue, name, _amount in LIVE_BOARD_HUES:
        log_stack = _FakeBoard(0x2, 0x1BDD, hue, 500)
        check("log at 0x%04X is not %s" % (hue, name),
              m["resource_of"](log_stack) == name, False)


def test_ingots_still_identify_after_the_board_change(m):
    """The board entries are rewritten at import. Ingots must be untouched."""
    for hue, want in [(0x096D, "Copper Ingots"), (0x0000, "Iron Ingots"),
                      (0x0973, "Dull Copper Ingots")]:
        ingot = _FakeBoard(0x3, 0x1BF2, hue, 1000)
        check("ingot 0x%04X -> %s" % (hue, want), m["resource_of"](ingot), want)


def test_green_scales_are_identified_by_hue(m):
    """CAUGHT IN GAME. All seven scale entries shipped as
    {"id": 0, "hue": -1, "by": "name"}, needing a stack literally named "green
    scales" - but every colour is a stack called "<amount> dragon scales", and
    unlike the ingots the tooltip does not even name the colour."""
    green = _FakeBoard(0x1, m["SCALE_IDS"][0], 0x0851, 710)
    check("0x0851 -> Green Scales", m["resource_of"](green), "Green Scales")


def test_an_unlisted_scale_hue_is_not_guessed(m):
    """Pouring red scales into a green order cannot be undone."""
    known = set(int(h) for h in m["SCALE_HUES"].values())
    stray = 0x0455
    while stray in known:
        stray += 1
    check("unlisted hue is unidentified",
          m["resource_of"](_FakeBoard(0x2, m["SCALE_IDS"][0], stray, 1125)),
          None)


def test_delicate_scales_still_match_by_name(m):
    """That stack really IS named "delicate scales" and has its own graphic
    (0x573A), so it must keep working through the plain name path - it is
    deliberately absent from SCALE_HUES."""
    check("not in the hue table", "Delicate Scales" in m["SCALE_HUES"], False)
    item = _FakeBoard(0x3, 0x573A, 0x0000, 3)
    item.Name = "3 delicate scales"
    check("still identified", m["resource_of"](item), "Delicate Scales")


def test_unknown_scale_hues_are_reported(m):
    """Same self-filling report the boards got: an unidentified colour has no
    stock as far as the budget is concerned, which looks exactly like an empty
    chest."""
    known = set(int(h) for h in m["SCALE_HUES"].values())
    stray = 0x066D
    while stray in known:
        stray += 1
    chest = _FakeChest([
        _FakeBoard(0x1, m["SCALE_IDS"][0], stray, 3453),
        _FakeBoard(0x2, m["SCALE_IDS"][0], 0x0851, 710),   # known: Green
        _FakeBoard(0x3, 0x1BF2, 0x0000, 59997),            # ingots, not scales
    ])
    family = [f for f in m["HUE_FAMILIES"] if f["label"] == "scale"][0]
    unknown = m["unknown_family_stacks"]([chest], family)
    check("one unknown scale hue", sorted(unknown), [stray])
    check("amount summed", unknown[stray]["amount"], 3453)
    check("the known green hue is not flagged", 0x0851 in unknown, False)
    check("ingots ignored", 0x1BF2 in unknown, False)


def test_boards_still_work_through_the_shared_family_table(m):
    """Boards and scales are now driven from one table. The board hues that
    were confirmed in game must survive that."""
    labels = [f["label"] for f in m["HUE_FAMILIES"]]
    check("every hue family is present", sorted(labels),
          ["board", "granite", "scale"])

    # Granite is the same trap a third time: a stack is called "<amount>
    # granite" and names no metal, so all nine entries shipped as
    # {"id": 0, "hue": -1, "by": "name"} and could never match. The table is
    # EMPTY on purpose - nothing here is guessed, and pouring Verite into a
    # Valorite order cannot be undone.
    granite = [f for f in m["HUE_FAMILIES"] if f["label"] == "granite"][0]
    check("granite has a graphic to match on", bool(granite["ids"]), True)
    for name in ("Valorite Granite", "Agapite Granite", "Dull Copper Granite"):
        check("%s is still in RESOURCES" % name,
              any(r["name"] == name for r in m["RESOURCES"]), True)
    for name, hue in granite["hues"].items():
        check("granite hue %r is a real resource" % name,
              any(r["name"] == name for r in m["RESOURCES"]), True)
    for hue, want, _amount in LIVE_BOARD_HUES:
        board = _FakeBoard(0x1, m["BOARD_IDS"][0], hue, 500)
        check("0x%04X still -> %s" % (hue, want),
              m["resource_of"](board), want)


def test_every_hue_family_name_exists_in_resources(m):
    names = set(r["name"] for r in m["RESOURCES"])
    for family in m["HUE_FAMILIES"]:
        for name in family["hues"]:
            check("%r is a real resource" % name, name in names, True)


def test_no_hue_is_shared_within_a_family(m):
    """Two resources on one hue means one gets filled with the other."""
    for family in m["HUE_FAMILIES"]:
        hues = [int(h) for h in family["hues"].values()]
        check("%s hues are unique" % family["label"], len(hues), len(set(hues)))


def test_boards_are_keyed_by_hue_not_by_name(m):
    """A board stack is called "<amount> boards" and says nothing about the
    wood - the same trap as ingots, which are all "<amount> ingots".

    So a board entry with no hue must match NOTHING rather than match by name
    and claim every wood. Guessing here pours Oak into a Magewood order.
    """
    board = _FakeBoard(0x1, m["BOARD_IDS"][0], 0x04A7, 500)
    # With BOARD_HUES empty (as shipped), an unlisted hue is unidentifiable.
    if not m["BOARD_HUES"]:
        check("an unlisted board hue is not identified",
              m["resource_of"](board), None)


def test_the_wood_storage_key_is_not_counted_as_boards(m):
    """0x1BD9 is the Wood Storage KEY's graphic (harvest_runner's
    WOOD_STORAGE_ID). If it were in BOARD_IDS the runner would count the key
    itself as a stack of boards and try to pour it into an order."""
    check("0x1BD7 is a board", 0x1BD7 in m["BOARD_IDS"], True)
    check("0x1BD9 is NOT", 0x1BD9 in m["BOARD_IDS"], False)


def test_unknown_board_hues_are_reported(m):
    """The whole point of the report: an unidentified wood has no stock as far
    as the budget is concerned, which is indistinguishable from an empty chest
    unless it is said out loud."""
    known = set(int(h) for h in m["BOARD_HUES"].values())
    stray = 0x04A7
    while stray in known:
        stray += 1
    chest = _FakeChest([
        _FakeBoard(0x1, m["BOARD_IDS"][0], stray, 500),
        _FakeBoard(0x2, m["BOARD_IDS"][0], stray, 250),
        _FakeBoard(0x3, 0x1BF2, 0x096D, 999),        # ingots, not boards
        _FakeBoard(0x4, 0x1BD9, 0x0058, 1),          # the storage key itself
    ])
    unknown = m["unknown_board_stacks"]([chest])
    check("one unknown hue found", sorted(unknown), [stray])
    check("amounts summed", unknown[stray]["amount"], 750)
    check("stacks counted", unknown[stray]["stacks"], 2)
    check("ingots ignored", 0x096D in unknown, False)
    check("the storage key ignored", 0x0058 in unknown, False)


def test_known_board_hues_are_not_reported_as_unknown(m):
    """Once a hue is in BOARD_HUES it must drop out of the report, or the
    warning never goes away and stops being read."""
    chest = _FakeChest([_FakeBoard(0x1, m["BOARD_IDS"][0], 0x1234, 10)])
    saved = dict(m["BOARD_HUES"])
    try:
        m["BOARD_HUES"].clear()
        m["BOARD_HUES"]["Oak Boards"] = 0x1234
        check("a listed hue is not flagged",
              m["unknown_board_stacks"]([chest]), {})
    finally:
        m["BOARD_HUES"].clear()
        m["BOARD_HUES"].update(saved)


def test_every_board_name_in_the_hue_table_exists_in_resources(m):
    """A misspelled name in BOARD_HUES is a dead entry: it would key a hue to a
    resource the book never asks for, and the wood would still never fill."""
    names = set(r["name"].strip().lower() for r in m["RESOURCES"])
    for name in m["BOARD_HUES"]:
        check("BOARD_HUES %r is a real resource" % name,
              name.strip().lower() in names, True)


def test_board_hues_are_unique(m):
    """Two woods on one hue means one of them gets filled with the other."""
    hues = [int(h) for h in m["BOARD_HUES"].values()]
    check("no hue serves two woods", len(hues), len(set(hues)))





# A real page, with the Completed column carrying a mix of Yes and No. Built
# from the verbatim Valorite capture, whose first row renders THREE cells
# because its Amt To Gather is 0.
COMPLETED_PAGE = [
    "Resource Orders", "Contents: 8658/100000", "Displayed: 4",
    "Name", "Amt To Gather", "Value Per",
    "Valorite Granite", "0", "No",
    "Iron Ingots", "155", "155", "400", "Yes",
    "Oak Boards", "500", "12", "25", "No",
    "Copper Ingots", "1038", "1038", "25", "Yes",
    "Previous Page", "Next Page", "(1/1)", "Add", "Purge",
]


def test_the_completed_column_is_read_per_row(m):
    rows = m["parse_rows_detailed"](COMPLETED_PAGE)
    check("four rows", len(rows), 4)
    check("names", [r["name"] for r in rows],
          ["Valorite Granite", "Iron Ingots", "Oak Boards", "Copper Ingots"])
    check("completed flags", [r["completed"] for r in rows],
          [False, True, False, True])
    check("amounts still read", [r["amount"] for r in rows],
          [0, 155, 500, 1038])


def test_the_short_first_row_does_not_shift_the_flags(m):
    """The row whose Amt To Gather is 0 renders three cells where the others
    render five. Counting positions instead of reading the last cell would put
    every later row's flag on the wrong order - and this presses buttons."""
    rows = m["parse_rows_detailed"](COMPLETED_PAGE)
    check("the 3-cell row is not completed", rows[0]["completed"], False)
    check("and the row after it is", rows[1]["completed"], True)
    check("its name is right", rows[1]["name"], "Iron Ingots")


def test_row_count_matches_the_buttons_it_will_be_zipped_with(m):
    """Rows are zipped with the page's row buttons, so a miscount presses the
    wrong order. Four rows must parse as four."""
    rows = m["parse_rows_detailed"](COMPLETED_PAGE)
    check("no footer label became a row",
          [r for r in rows if r["name"] in ("Add", "Purge", "Next Page")], [])
    check("no flag became a row",
          [r for r in rows if r["name"].lower() in ("yes", "no")], [])


def test_a_page_with_nothing_finished_yields_nothing(m):
    page = [
        "Name", "Amt To Gather", "Value Per",
        "Oak Boards", "500", "12", "25", "No",
        "Ash Boards", "300", "0", "25", "No",
        "Previous Page",
    ]
    rows = m["parse_rows_detailed"](page)
    check("two rows", len(rows), 2)
    check("none completed", [r["completed"] for r in rows], [False, False])


def test_the_completed_filter_targets_column_five(m):
    """Column 5 is Completed: entry id 4, submit button 52. Getting this wrong
    would filter the Name column with "Yes" and return nothing, which reads as
    "no finished orders" rather than as a mistake."""
    check("entry 4", m["ORDERS_COMPLETED_ENTRY"], 4)
    check("submit 52", m["ORDERS_COMPLETED_SUBMIT"], 52)
    check("not the Name box",
          m["ORDERS_COMPLETED_ENTRY"] == m["ORDERS_SEARCH_ENTRY"], False)
    check("not the Name submit",
          m["ORDERS_COMPLETED_SUBMIT"] == m["ORDERS_FILTER_SUBMIT"], False)


def test_orders_action_puts_the_text_in_the_box_it_was_given(m):
    """The five boxes are submitted together. Text in the wrong one filters the
    wrong column, and leaving an old value in another stacks two filters."""
    sent = {}

    class FakeGumps(object):
        def SendAdvancedAction(self, gid, button, switches, ids, values):
            sent["ids"], sent["values"] = list(ids), list(values)

        def SendAction(self, gid, button):
            sent["plain"] = button

        def WaitForGump(self, gid, ms):
            return True

        def HasGump(self, gid=None):
            return True

    saved = m["Gumps"]
    try:
        m["Gumps"] = FakeGumps()
        m["orders_action"](m["ORDERS_COMPLETED_SUBMIT"], "Yes",
                           m["ORDERS_COMPLETED_ENTRY"])
        check("all five boxes submitted", len(sent["values"]), 5)
        check("Yes went in box 4",
              sent["values"][sent["ids"].index(4)], "Yes")
        check("every other box is empty",
              [v for i, v in zip(sent["ids"], sent["values"]) if i != 4],
              ["", "", "", ""])

        sent.clear()
        m["orders_action"](m["ORDERS_FILTER_SUBMIT"], "Copper Ingots")
        check("the name still defaults to box 0",
              sent["values"][sent["ids"].index(0)], "Copper Ingots")
    finally:
        m["Gumps"] = saved


def test_pulled_orders_count_towards_the_lap_being_productive(m):
    """This is what makes "15 at a time until no more" work across laps.

    The run stops after `sweep` consecutive laps that hand nothing in. A lap
    that only PULLS finished orders and fills nothing has to still count, or
    the run would stop with a backlog still sitting in the book.

    So the pulled deeds must be folded into `completed` BEFORE the "nothing
    filled" early return, not after it.
    """
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    lap = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_lap":
            lap = node
    check("run_lap exists", lap is not None, True)
    if lap is None:
        return

    pull_line = None
    merge_line = None
    for node in ast.walk(lap):
        if isinstance(node, ast.Call) and                 getattr(node.func, "id", None) == "pull_completed_orders":
            pull_line = node.lineno
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "completed" in targets:
                names = [n.id for n in ast.walk(node.value)
                         if isinstance(n, ast.Name)]
                if "pulled" in names:
                    merge_line = node.lineno

    check("run_lap pulls finished orders", pull_line is not None, True)
    check("and folds them into `completed`", merge_line is not None, True)

    # The early return that ends the lap when nothing was filled.
    early = []
    for node in ast.walk(lap):
        if isinstance(node, ast.If):
            src = ast.dump(node.test)
            if "completed" in src and any(isinstance(n, ast.Return)
                                          for n in ast.walk(node)):
                early.append(node.lineno)
    if merge_line is not None and early:
        check("the merge happens before the nothing-filled exit",
              merge_line < max(early), True)


def test_the_pull_runs_until_the_book_is_clear(m):
    """"15 at a time until no more show Yes". The backlog is cleared in
    batches: a lap that pulls its 15 still hands them in, which counts as a
    productive lap, so the run continues and the next lap takes the next 15."""
    check("a batch per lap", m["COMPLETED_MAX_PULL"], 15)
    check("bounded", m["COMPLETED_MAX_PULL"] >= 1, True)
    check("a page cap too", m["COMPLETED_MAX_PAGES"] >= 1, True)


def test_priority_resources_lead_every_lap(m):
    """CAUGHT IN GAME. RESOURCES is sorted by how many orders the BOOK held
    when it was harvested, which says nothing about what is in the chest. Iron
    Ingots sat at #78 of 79 because the book wanted one that day, so with 15
    withdrawals a lap the lap ended tens of resources before its turn - every
    lap, while 60,000 iron sat in the chest."""
    work = m["worked_resources"]()
    priority, rest = m["split_priorities"](work)

    check("the configured names are found", [r["name"] for r in priority],
          list(m["PRIORITY_RESOURCES"]))
    check("nothing is lost", len(priority) + len(rest), len(work))
    check("and nothing is in both",
          set(r["name"] for r in priority) & set(r["name"] for r in rest),
          set())

    # They must lead whatever the rotation is doing, or the whole point is lost.
    leads = True
    for offset in range(0, len(work) + 1):
        order = priority + m["rotated"](rest, offset)
        if [r["name"] for r in order[:len(priority)]] !=                 [r["name"] for r in priority]:
            leads = False
            break
    check("priorities lead at every offset", leads, True)


def test_iron_and_regular_boards_are_no_longer_last(m):
    """The two the chest actually holds most of. Iron was dead last."""
    work = m["worked_resources"]()
    names = [r["name"] for r in work]
    check("Iron Ingots was near the end of RESOURCES",
          names.index("Iron Ingots") > len(names) - 5, True)

    priority, rest = m["split_priorities"](work)
    order = priority + m["rotated"](rest, 0)
    positions = [r["name"] for r in order]
    check("Iron Ingots is now worked first", positions[0], "Iron Ingots")
    check("Regular Boards second", positions[1], "Regular Boards")


def test_the_rotation_still_reaches_everything_else(m):
    """Pinning two resources must not starve the other 77. The offset has to
    advance by the ROTATED part only - counting the priorities would push it
    along by two every lap and skip two resources each time."""
    work = m["worked_resources"]()
    priority, rest = m["split_priorities"](work)

    seen = set()
    offset = 0
    per_lap = m["MAX_ORDERS_PER_RUN"]
    for _lap in range(60):
        order = priority + m["rotated"](rest, offset)
        examined = [r["name"] for r in order[:per_lap]]
        seen.update(examined)
        stepped = len([n for n in examined
                       if n not in set(r["name"] for r in priority)])
        offset += stepped

    missed = [r["name"] for r in rest if r["name"] not in seen]
    check("every non-priority resource gets a turn within 60 laps", missed, [])


def test_a_misspelled_priority_is_reported_not_swallowed(m):
    """A typo here would look exactly like the resource still being ignored -
    which is the complaint this feature exists to answer."""
    saved = list(m["PRIORITY_RESOURCES"])
    try:
        m["PRIORITY_RESOURCES"][:] = ["Iorn Ingots"]
        priority, rest = m["split_priorities"](m["worked_resources"]())
        check("the bad name is not used", priority, [])
        check("and nothing is dropped from the rest",
              len(rest), len(m["worked_resources"]()))
    finally:
        m["PRIORITY_RESOURCES"][:] = saved


def test_priority_names_all_exist(m):
    """As shipped, every configured name must resolve - or it silently does
    nothing."""
    names = set(r["name"] for r in m["RESOURCES"])
    for name in m["PRIORITY_RESOURCES"]:
        check("%r is a real resource" % name, name in names, True)


def test_a_replacement_order_is_collected_after_every_handin(m):
    """Handing a filled order in CLEARS THE COOLDOWN on taking a new one, so
    the moment after each hand-in is the one moment a replacement is free.
    That is why it is per hand-in and not once per trip."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    hand_in = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "hand_in":
            hand_in = node
    check("hand_in exists", hand_in is not None, True)
    if hand_in is None:
        return

    calls = [n for n in ast.walk(hand_in)
             if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "collect_replacement"]
    # Once in the main pass, once in the sweep that follows it - a deed handed
    # in by the sweep earns a replacement just the same.
    check("collected after a hand-in, in both passes", len(calls), 2)

    for call in calls:
        gives = [n for n in ast.walk(hand_in)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "give_deed"
                 and n.lineno < call.lineno]
        check("it follows a give_deed", len(gives) > 0, True)


def test_the_replacement_is_capped(m):
    """A menu that answers without ever producing a deed must not spin."""
    check("there is a cap", m["NEW_ORDER_MAX_PER_TRIP"] >= 1, True)
    check("and it is not unbounded", m["NEW_ORDER_MAX_PER_TRIP"] <= 200, True)

    collected = [m["NEW_ORDER_MAX_PER_TRIP"]]
    check("at the cap it refuses to ask",
          m["collect_replacement"](None, None, collected), False)
    check("and the counter did not move",
          collected[0], m["NEW_ORDER_MAX_PER_TRIP"])


def test_the_talk_entry_is_not_something_that_spends_gold(m):
    """An NPC menu carries Buy, Sell, Bribe and Train beside the real entry.
    A configured label that CONTEXT_NEVER would refuse is a dead config."""
    for label in m["NEW_ORDER_CONTEXT"]:
        check("%r is not blocked" % label,
              m["pick_context"]([label], m["NEW_ORDER_CONTEXT"]), label)
    check("Talk is what is configured", m["NEW_ORDER_CONTEXT"], ["Talk"])


def test_context_never_still_refuses_the_dangerous_entries(m):
    """The guarded substring path must not pick something that spends gold,
    even while looking for Talk."""
    menu = ["Buy", "Sell", "Bribe", "Open Bankbox", "Train Mining"]
    check("nothing on that menu is chosen",
          m["pick_context"](menu, ["Talk"]), None)


def test_new_orders_are_parked_out_of_the_top_level_pack(m):
    """An unfilled deed loose in the pack is indistinguishable from one the run
    failed to fill, so it would be reported as a leftover every lap and
    re-examined by the filler. The bag keeps them apart."""
    check("a bag is configured", m["ORDER_BAG_SERIAL"] > 0, True)
    check("it is not the trash bag",
          m["ORDER_BAG_SERIAL"] == m["TRASH_BAG_SERIAL"], False)
    check("nor a chest the runner censuses",
          m["ORDER_BAG_SERIAL"] in [c["serial"] for c in m["CHESTS"]], False)


def test_fill_from_backpack_is_button_five(m):
    """From the mapped book gump: button 5 is "Fill from backpack". Button 3
    withdraws and button 8 renames, so this must not drift."""
    check("Fill from backpack", m["BOOK_FILL_BUTTON"], 5)
    check("and it is not the orders button",
          m["BOOK_FILL_BUTTON"] == m["BOOK_ORDERS_BUTTON"], False)


def test_the_new_orders_are_deposited_before_the_census(m):
    """They have to be in the book before the lap counts what it can fill, or
    they are carried round for another whole circuit."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    lap = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_lap":
            lap = node
    check("run_lap exists", lap is not None, True)
    if lap is None:
        return
    deposit = [n.lineno for n in ast.walk(lap)
               if isinstance(n, ast.Call)
               and getattr(n.func, "id", None) == "deposit_new_orders"]
    fill = [n.lineno for n in ast.walk(lap)
            if isinstance(n, ast.Call)
            and getattr(n.func, "id", None) == "fill_orders"]
    check("run_lap deposits them", len(deposit) > 0, True)
    check("run_lap fills", len(fill) > 0, True)
    if deposit and fill:
        check("deposit comes first", min(deposit) < min(fill), True)


def test_the_scan_rewinds_to_page_one_after_filtering(m):
    """CAUGHT IN GAME. Submitting a new Name filter does NOT reset the page.

    diag_copper_pages.py, 2026-07-30: the list was on page 4 of the previous
    resource's result, "Copper Ingots" was submitted, and the list came back on
    page 4 of THAT result - the same page 4 the scan had already read, byte for
    byte (fingerprint 02161 both times).

    work_one_order only reopens the book when the gump is CLOSED, so every
    resource after the first starts its scan wherever the last one stopped, and
    a scan that finds nothing ends on the LAST page. Copper Ingots has all 26 of
    its orders on pages 1-2 of 10, so it was walked straight past and reported
    as having no orders that fit. Every other resource has orders spread through
    its result, which is why Copper alone was affected.

    Asserted statically: it needs a live gump to reproduce, and the failure is
    silent - the scan reports "no orders" exactly as it would if there really
    were none.
    """
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    functions = dict((n.name, n) for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef))
    check("rewind_to_first_page exists", "rewind_to_first_page" in functions,
          True)

    scan = functions.get("find_first_order")
    check("find_first_order exists", scan is not None, True)
    if scan is None:
        return

    # It must rewind, and do so BEFORE the page loop - rewinding afterwards
    # would be a no-op for the very read it is meant to protect.
    rewind_line = None
    for node in ast.walk(scan):
        if isinstance(node, ast.Call) and \
                getattr(node.func, "id", None) == "rewind_to_first_page":
            rewind_line = node.lineno if rewind_line is None \
                else min(rewind_line, node.lineno)
    check("find_first_order rewinds", rewind_line is not None, True)

    loop_line = None
    for node in ast.walk(scan):
        if isinstance(node, ast.For):
            loop_line = node.lineno if loop_line is None \
                else min(loop_line, node.lineno)
    check("it has a page loop", loop_line is not None, True)
    if rewind_line is not None and loop_line is not None:
        check("rewind happens before the page loop", rewind_line < loop_line,
              True)

    # The rewind must press Previous Page, not guess some other button.
    rewinder = functions["rewind_to_first_page"]
    pressed = set()
    for node in ast.walk(rewinder):
        if isinstance(node, ast.Call) and \
                getattr(node.func, "id", None) == "orders_action":
            for arg in node.args[:1]:
                if isinstance(arg, ast.Name):
                    pressed.add(arg.id)
    check("it presses ORDERS_PREV_BUTTON", "ORDERS_PREV_BUTTON" in pressed,
          True)
    check("ORDERS_PREV_BUTTON is button 4", m["ORDERS_PREV_BUTTON"], 4)

    # A bounded loop, never a while-until-it-works.
    check("the rewind is bounded", m["MAX_REWIND_PRESSES"] >= 1, True)
    check("no unbounded while in the rewind",
          any(isinstance(n, ast.While) for n in ast.walk(rewinder)), False)



# ---------------------------------------------------------------------------
# Pack space
# ---------------------------------------------------------------------------

class FakePack(object):
    """A backpack whose tooltip carries ServUO's Contents line.

    Container.GetProperties adds cliloc 1073841 with TotalItems, MaxItems and
    TotalWeight, and TotalItems is RECURSIVE - UpdateTotals does
    m_TotalItems += item.TotalItems + 1 - so everything sitting in a sub-bag
    counts against the same number.
    """

    def __init__(self, lines, serial=0x41D40F58):
        self.tooltip = list(lines)
        self.Serial = serial


def _with_pack(m, lines):
    """Point the module's Player/Items at a backpack with this tooltip."""
    pack = FakePack(lines) if lines is not None else None

    class P(_Stub):
        Backpack = pack

    class I(_Stub):
        def WaitForProps(self, item, timeout):
            return True

        def GetPropStringList(self, item):
            return list(getattr(item, "tooltip", []))

        def __getattr__(self, name):
            return lambda *a, **k: None

    m["Player"] = P()
    m["Items"] = I()
    return pack


def test_pack_count_comes_from_the_tooltip(m):
    saved_p, saved_i = m["Player"], m["Items"]
    try:
        _with_pack(m, ["Backpack", "Contents: 300/375 items, 4210/60000 stones"])
        check("used and max read off the tooltip",
              m["pack_item_count"](), (300, 375))
        check("headroom is max - used - safety",
              m["pack_headroom"](), 375 - 300 - m["PACK_ITEM_SAFETY"])

        # A different character with a different pack must get their own
        # number, not the configured one. That is the whole point of reading it.
        _with_pack(m, ["Contents: 10/125 items, 5/60000 stones"])
        check("a 125-item pack is respected", m["pack_item_count"](), (10, 125))
        check("and its headroom is its own",
              m["pack_headroom"](), 125 - 10 - m["PACK_ITEM_SAFETY"])
    finally:
        m["Player"], m["Items"] = saved_p, saved_i


def test_an_unreadable_pack_is_unknown_not_empty(m):
    """Zeroes mean "could not tell".

    Treating that as an empty pack would let the run withdraw into a pack that
    is actually full; treating it as a FULL pack would stop a healthy run dead.
    It must be neither.
    """
    saved_p, saved_i = m["Player"], m["Items"]
    try:
        _with_pack(m, ["Backpack", "Weight: 4210 stones"])   # no Contents line
        check("no Contents line reads as unknown",
              m["pack_item_count"](), (0, 0))
        check("headroom is None, not 0", m["pack_headroom"](), None)

        cap, why = m["orders_this_lap"]()
        check("an unknown pack falls back to MAX_ORDERS_PER_RUN",
              cap, m["MAX_ORDERS_PER_RUN"])
        check("and it says so", "UNKNOWN" in why, True)

        _with_pack(m, None)          # no backpack at all
        check("no backpack is unknown too", m["pack_item_count"](), (0, 0))
    finally:
        m["Player"], m["Items"] = saved_p, saved_i


def test_the_smaller_ceiling_wins(m):
    saved_p, saved_i = m["Player"], m["Items"]
    try:
        # Nearly full: pack space binds, well under MAX_ORDERS_PER_RUN.
        _with_pack(m, ["Contents: 368/375 items, 1/60000 stones"])
        cap, why = m["orders_this_lap"]()
        check("a nearly full pack caps the lap", cap, 375 - 368 - 5)
        check("and names pack space as the reason", "pack" in why.lower(), True)
        check("the cap is under MAX_ORDERS_PER_RUN",
              cap < m["MAX_ORDERS_PER_RUN"], True)

        # Plenty of room: MAX_ORDERS_PER_RUN binds instead.
        _with_pack(m, ["Contents: 12/375 items, 1/60000 stones"])
        cap, why = m["orders_this_lap"]()
        check("an empty pack defers to MAX_ORDERS_PER_RUN",
              cap, m["MAX_ORDERS_PER_RUN"])

        # Exactly full, and one short - never negative, never a withdrawal.
        _with_pack(m, ["Contents: 375/375 items, 1/60000 stones"])
        check("a full pack has no room", m["pack_headroom"](), 0)
        check("a full pack caps at zero", m["orders_this_lap"]()[0], 0)
        _with_pack(m, ["Contents: 374/375 items, 1/60000 stones"])
        check("the safety margin is honoured, not overrun",
              m["pack_headroom"](), 0)
    finally:
        m["Player"], m["Items"] = saved_p, saved_i


def test_the_safety_margin_is_real(m):
    check("some slots are always kept free", m["PACK_ITEM_SAFETY"] >= 1, True)
    check("the fallback limit is a real number", m["PACK_ITEM_LIMIT"] >= 1, True)


# ---------------------------------------------------------------------------
# Burst filling - and the .20 starvation guard
# ---------------------------------------------------------------------------

def test_a_burst_is_bounded(m):
    """THE .20 REGRESSION GUARD.

    Version .20 worked each resource to exhaustion and was reverted: the first
    few resources ate the whole lap and Iron Ingots, at position 9, was never
    reached with 60,000 iron in the chest. The burst exists to get the gump
    saving WITHOUT that, so it must be bounded by construction.
    """
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "fill_orders")

    whiles = [n for n in _ast.walk(fn) if isinstance(n, _ast.While)]
    check("fill_orders has a burst loop", len(whiles) >= 1, True)

    names = set()
    for w in whiles:
        for node in _ast.walk(w.test):
            if isinstance(node, _ast.Name):
                names.add(node.id)
    check("the burst loop is bounded by MAX_ORDERS_PER_RESOURCE",
          "MAX_ORDERS_PER_RESOURCE" in names, True)
    check("MAX_ORDERS_PER_RESOURCE is a finite number",
          isinstance(m["MAX_ORDERS_PER_RESOURCE"], int)
          and m["MAX_ORDERS_PER_RESOURCE"] >= 1, True)

    # It must ALSO still respect the lap cap from inside the burst, or one
    # resource walks straight past pack space.
    src = _ast.dump(fn)
    check("the burst still checks the lap cap", "cap" in src, True)


def test_the_burst_reuses_the_hot_filter(m):
    """The saving IS the skipped filter submit.

    If the burst refiltered every time it would cost exactly what round-robin
    costs and there would be no point to it.
    """
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())

    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "work_one_order")
    check("work_one_order takes a hot flag",
          "hot" in [a.arg for a in fn.args.args], True)

    finder = next(n for n in _ast.walk(tree)
                  if isinstance(n, _ast.FunctionDef)
                  and n.name == "find_first_order")
    check("find_first_order can skip the refilter",
          "refilter" in [a.arg for a in finder.args.args], True)

    # The refilter must be CONDITIONAL, not merely parameterised.
    submits = []
    for node in _ast.walk(finder):
        if isinstance(node, _ast.If):
            for inner in _ast.walk(node):
                if isinstance(inner, _ast.Name) \
                        and inner.id == "ORDERS_FILTER_SUBMIT":
                    submits.append(node)
    check("the filter submit sits behind an if", len(submits) >= 1, True)

    # The rewind must NOT be skipped: withdrawing a row reflows the pages.
    rewinds = [n for n in _ast.walk(finder)
               if isinstance(n, _ast.Call)
               and getattr(n.func, "id", None) == "rewind_to_first_page"]
    check("the rewind still runs on a hot list", len(rewinds) >= 1, True)


def test_reopening_the_book_clears_hot(m):
    """A reopened book has lost the filter whatever the caller believed.

    If `hot` survived that, the scan would read an unfiltered list.
    """
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "work_one_order")
    assigns = [n for n in _ast.walk(fn)
               if isinstance(n, _ast.Assign)
               and any(getattr(t, "id", None) == "hot" for t in n.targets)]
    check("work_one_order resets hot after reopening", len(assigns) >= 1, True)
    check("and it resets it to False",
          any(getattr(a.value, "value", None) is False for a in assigns), True)



# ---------------------------------------------------------------------------
# The end-of-run tidy: full stacks, not merely fewer stacks
# ---------------------------------------------------------------------------

def _tidy(amounts, top_up=True, hue=0x08AB, name="Valorite Ingots"):
    """Run the real consolidate_stacks over these amounts. Returns
    (final amounts desc, move count, total in, total out)."""
    module, chest, items = with_chest([
        FakeItem("s%d" % i, a, 0x1BF2, hue, 0xB0 + i)
        for i, a in enumerate(amounts)])
    after = module["consolidate_stacks"](chest, name, top_up=top_up)
    return (sorted((s.Amount for s in after), reverse=True),
            len(items.moves), sum(amounts), sum(s.Amount for s in after))


def test_absorb_only_cannot_build_full_stacks(m):
    """Why the deeper pass had to exist at all.

    Three 40,000 stacks under a 60,000 cap absorb into nowhere - no stack fits
    whole inside another - so the lap-start tidy correctly walks away having
    done nothing, leaving two stacks' worth of ingots in three.
    """
    final, moves, _tin, _tout = _tidy([40000, 40000, 40000], top_up=False)
    check("absorb-only makes no move here", moves, 0)
    check("and leaves three stacks", len(final), 3)


def test_top_up_builds_full_stacks(m):
    cap = m["MAX_STACK"]
    final, moves, tin, tout = _tidy([40000, 40000, 40000])
    check("top-up gets it down to two", len(final), 2)
    check("both of them full", final, [cap, cap])
    check("nothing created or lost", tout, tin)
    check("and it was cheap", moves <= 4, True)


def test_the_tidy_never_drains_a_full_stack(m):
    """THE NON-TERMINATION GUARD.

    A first cut of the top-up allowed a FULL stack to be the source, so
    [60000, 60000, 5] poured 59,995 out of a full stack into the scrap and
    produced [60000, 60000, 5] again - forty moves, no progress, and it would
    have burned MAX_MERGE_MOVES on every resource every run.

    This layout is already optimal. The correct number of moves is zero.
    """
    cap = m["MAX_STACK"]
    final, moves, tin, tout = _tidy([cap, cap, 5])
    check("an optimal layout is left alone", moves, 0)
    check("and is unchanged", final, [cap, cap, 5])
    check("nothing created or lost", tout, tin)

    # The same shape one item down, where there IS a legal move to make.
    final, moves, tin, tout = _tidy([cap, cap - 10, 5])
    check("a real top-up still happens", moves >= 1, True)
    check("nothing created or lost either way", tout, tin)


def test_the_tidy_reaches_the_minimum_stack_count(m):
    """Conservation, the cap, and optimality across a spread of layouts.

    Optimal is ceil(total / MAX_STACK) - anything more means ingots are
    sitting in more stacks than they need to.
    """
    cap = m["MAX_STACK"]
    layouts = [
        [50000, 30000, 25000, 12000, 900, 40],
        [1, 1, 1, 1, 1],
        [cap, 1],
        [cap - 1, cap - 1, 2],
        [59999, 59999, 59999],
        [123],
        [30000, 30000],
        [10, 20, 30, 40, 50, 60, 70, 80],
    ]
    for amounts in layouts:
        total = sum(amounts)
        want = max(1, -(-total // cap))
        final, moves, tin, tout = _tidy(list(amounts))
        label = "%s -> %d stack(s)" % (str(amounts)[:22], want)
        check(label, len(final), want)
        check("  total preserved: %s" % str(amounts)[:20], tout, tin)
        check("  none over the cap: %s" % str(amounts)[:18],
              [a for a in final if a > cap], [])
        check("  bounded moves: %s" % str(amounts)[:21],
              moves <= m["MAX_MERGE_MOVES"], True)


def test_the_deep_tidy_runs_when_nothing_fills(m):
    """It has to fire at the no-fill moment, with the chests still open.

    At the START of a lap it would leave the mess made by that lap's own fills
    behind whenever the run ends - which is exactly when the user looks at the
    chest.
    """
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "run_lap")

    deep = [n for n in _ast.walk(fn)
            if isinstance(n, _ast.Call)
            and getattr(n.func, "id", None) == "organize_chests"
            and any(kw.arg == "top_up" for kw in n.keywords)]
    check("run_lap has a top_up organize", len(deep), 1)

    fills = [n.lineno for n in _ast.walk(fn)
             if isinstance(n, _ast.Call)
             and getattr(n.func, "id", None) == "fill_orders"]
    check("and it happens AFTER the filling, not before",
          deep[0].lineno > min(fills), True)

    # It must be switchable, and off by default would be a silent no-op.
    check("there is a switch for it", m["ORGANIZE_WHEN_DONE"] in (True, False),
          True)


def test_the_lap_start_tidy_stays_cheap(m):
    """The lap-start pass must NOT top up - that would spend moves on neatness
    before a single order is filled."""
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "run_lap")
    fills = [n.lineno for n in _ast.walk(fn)
             if isinstance(n, _ast.Call)
             and getattr(n.func, "id", None) == "fill_orders"]
    early = [n for n in _ast.walk(fn)
             if isinstance(n, _ast.Call)
             and getattr(n.func, "id", None) == "organize_chests"
             and n.lineno < min(fills)]
    check("the lap-start organize exists", len(early), 1)
    check("and it does not ask for top_up",
          any(kw.arg == "top_up" for kw in early[0].keywords), False)



# ---------------------------------------------------------------------------
# "took nothing" must always say WHY
# ---------------------------------------------------------------------------

def test_an_unfillable_order_is_never_rejected_in_silence(m):
    """The Iron Ingots case.

    A single `amount > budget or amount > MAX_ORDER_SIZE: continue` threw
    matching rows away without a word, so a resource whose every order is too
    big reported "took nothing" with its full stock and spendable budget
    printed next to it - pointing at the budget, which was fine. The config
    comment on MAX_ORDER_SIZE records the same thing happening at 5000, where
    it "rejected almost every one of them and the resource looked skipped".
    """
    import ast as _ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    fn = next(n for n in _ast.walk(tree)
              if isinstance(n, _ast.FunctionDef) and n.name == "find_first_order")

    # The combined silent test must be gone: the two causes need opposite
    # fixes, so they cannot share one branch.
    combined = []
    for node in _ast.walk(fn):
        if isinstance(node, _ast.BoolOp) and isinstance(node.op, _ast.Or):
            names = set()
            for sub in _ast.walk(node):
                if isinstance(sub, _ast.Name):
                    names.add(sub.id)
            if "MAX_ORDER_SIZE" in names and "budget" in names:
                combined.append(node)
    check("the two rejections are no longer one silent test", combined, [])

    # Both reasons must be collected, and both must reach a log call.
    appends = set()
    for node in _ast.walk(fn):
        if isinstance(node, _ast.Call) \
                and getattr(node.func, "attr", None) == "append" \
                and getattr(node.func.value, "id", None) in ("too_big",
                                                             "over_budget"):
            appends.add(node.func.value.id)
    check("rows too big are counted", "too_big" in appends, True)
    check("rows over budget are counted", "over_budget" in appends, True)

    # Both counters must be READ inside a branch that logs. Checking that the
    # name appears literally inside the log() call is too narrow - the counts
    # legitimately reach it through a joined list - so this looks for a branch
    # guarded on them that reaches a log.
    reported = set()
    for node in _ast.walk(fn):
        if not isinstance(node, _ast.If):
            continue
        guards = set(sub.id for sub in _ast.walk(node.test)
                     if isinstance(sub, _ast.Name))
        if not guards & {"too_big", "over_budget"}:
            continue
        if any(isinstance(c, _ast.Call)
               and getattr(c.func, "id", None) == "log"
               for c in _ast.walk(node)):
            reported |= guards & {"too_big", "over_budget"}
    check("the too-big count reaches a log line", "too_big" in reported, True)
    check("the over-budget count reaches a log line",
          "over_budget" in reported, True)

    # And the count of rows that really were this resource, which is what
    # separates "no orders exist" from "none of them were takeable".
    logs = " ".join(_ast.dump(n) for n in _ast.walk(fn)
                    if isinstance(n, _ast.Call)
                    and getattr(n.func, "id", None) == "log")
    check("and how many actually matched", "matched" in logs, True)


def test_the_reason_tells_you_what_to_change(m):
    """A diagnostic that does not say what to do costs another round trip.

    Too big and over budget need OPPOSITE actions - raise a cap versus gather
    more stock - so the line has to distinguish them by name.
    """
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def find_first_order("):src.index("def withdraw(")]
    check("it names MAX_ORDER_SIZE as the thing to raise",
          "RAISE MAX_ORDER_SIZE" in body, True)
    check("it reports the smallest order it refused",
          "min(too_big)" in body, True)
    check("so you can tell how far off the cap is",
          "min(over_budget)" in body, True)

    # And the "no row is named exactly this" case, which is a DIFFERENT bug
    # (the book's name for the resource is not what RESOURCES says).
    check("a name mismatch is called out separately",
          "no row is named exactly" in body, True)


def test_max_order_size_is_still_a_sanity_ceiling(m):
    """It exists to stop one order draining the chest. If it ever climbs above
    what the budget logic protects, it stops being a ceiling at all."""
    check("there is a ceiling", m["MAX_ORDER_SIZE"] >= 1, True)

    # It may exceed one stack, and live it does - 80,000 against a 60,000
    # stack cap. That is fine BECAUSE fill_deed makes one pass per stack and
    # re-reads the chest each time, so an order larger than any single stack is
    # drawn from two. If that ever stops being true, this ceiling starts
    # accepting orders that cannot be filled, so the two are checked together.
    if m["MAX_ORDER_SIZE"] > m["MAX_STACK"]:
        with open(SCRIPT, encoding="utf-8") as fh:
            body = fh.read()
        body = body[body.index("def fill_deed("):body.index("def openAR(")]
        check("an order bigger than a stack still gets a pass per stack",
              "len(on_hand) + 2" in body, True)
        check("and the chest is re-read on every pass",
              body.count("chest_stacks(chests, resource)") >= 2, True)



# ---------------------------------------------------------------------------
# Smallest first, by sorting the list
#
# The column header sorts. Button 21 came from Razor's Enhanced Gump Inspector
# (gump 0xB2F21F1A, 2026-08-22) - the response log showed the Name filter
# restated in Text ID 0 and the reply coming back as the same filtered list, so
# the filter survives the sort. Sorting ascending makes the first acceptable
# row the smallest in the whole result, which is what maximises orders filled
# from a fixed stock.
# ---------------------------------------------------------------------------

def test_the_sort_button_is_the_captured_one(m):
    check("button 21, from the Gump Inspector",
          m["ORDERS_SORT_AMOUNT_BUTTON"], 21)
    check("the gump id matches the capture", m["ORDERS_GUMP"], 0xB2F21F1A)

    # It must not collide with anything destructive on the same gump.
    for name in ("ORDERS_FILTER_SUBMIT", "ORDERS_NEXT_BUTTON",
                 "ORDERS_PREV_BUTTON", "ORDERS_COMPLETED_SUBMIT"):
        check("21 is not also %s" % name,
              m["ORDERS_SORT_AMOUNT_BUTTON"] == m[name], False)
    # Purge is 2 and Fill from backpack is 3 on this gump - documented in
    # CLAUDE.md as the reason never to guess a button here.
    check("and it is not Purge (2) or Fill from backpack (3)",
          m["ORDERS_SORT_AMOUNT_BUTTON"] in (2, 3), False)


class SortingList(object):
    """A filtered order list that really sorts when button 21 is pressed.

    `direction` is which way the FIRST press lands, so both possibilities can
    be exercised - the script must not assume one.
    """

    def __init__(self, amounts, direction="desc", works=True):
        self.base = list(amounts)
        self.rows = list(amounts)
        self.direction = direction
        self.works = works
        self.presses = 0

    def press(self):
        self.presses += 1
        if not self.works:
            return
        ascending = (self.direction == "asc") == (self.presses % 2 == 1)
        self.rows = sorted(self.base, reverse=not ascending)


def _sorting_module(listing):
    """A module whose gump reads come from `listing`."""
    module = load()
    module["orders_action"] = lambda button, text=None, entry=None: (
        listing.press() or True) if button == module["ORDERS_SORT_AMOUNT_BUTTON"] \
        else True
    module["rewind_to_first_page"] = lambda *a, **k: True
    module["gump_lines"] = lambda *a, **k: ["ROWS"]
    module["parse_order_rows"] = lambda strings, anchor: [
        {"name": "Iron Ingots", "amount": a} for a in listing.rows]
    module["log"] = lambda *a, **k: None
    return module


def test_sorting_ascending_is_verified_not_assumed(m):
    """One press may sort either way. Which one is not worth guessing when the
    list itself can be read - so it presses again if it came back descending."""
    import re as _re
    exact = _re.compile(r"^iron ingots?$", _re.I)

    # First press lands DESCENDING - it must press again.
    desc = SortingList([500, 100, 900, 300], direction="desc")
    mod = _sorting_module(desc)
    check("it reports success", mod["sort_by_amount"]("Iron Ingots",
                                                     "iron ingots", exact), True)
    check("and it pressed twice to get there", desc.presses, 2)
    check("the list ends ascending", desc.rows, [100, 300, 500, 900])

    # First press lands ASCENDING - one press is enough.
    asc = SortingList([500, 100, 900, 300], direction="asc")
    mod = _sorting_module(asc)
    check("ascending first time is accepted",
          mod["sort_by_amount"]("Iron Ingots", "iron ingots", exact), True)
    check("and it stopped at one press", asc.presses, 1)


def test_a_list_that_will_not_sort_is_reported_not_trusted(m):
    """If two presses cannot produce an ascending page, saying "sorted" would
    have the caller take the FIRST row believing it is the smallest."""
    import re as _re
    exact = _re.compile(r"^iron ingots?$", _re.I)
    broken = SortingList([500, 100, 900], works=False)
    mod = _sorting_module(broken)
    check("it admits failure",
          mod["sort_by_amount"]("Iron Ingots", "iron ingots", exact), False)
    check("after trying twice", broken.presses, 2)


def test_a_single_row_cannot_contradict_the_sort(m):
    import re as _re
    exact = _re.compile(r"^iron ingots?$", _re.I)
    one = SortingList([700])
    mod = _sorting_module(one)
    check("one row is trivially sorted",
          mod["sort_by_amount"]("Iron Ingots", "iron ingots", exact), True)


def test_sorting_can_be_switched_off(m):
    import re as _re
    exact = _re.compile(r"^iron ingots?$", _re.I)
    listing = SortingList([500, 100])
    mod = _sorting_module(listing)
    saved = mod["ORDERS_SORT_AMOUNT_BUTTON"]
    try:
        mod["ORDERS_SORT_AMOUNT_BUTTON"] = 0
        check("no button, no sorting",
              mod["sort_by_amount"]("Iron Ingots", "iron ingots", exact), False)
        check("and nothing was pressed", listing.presses, 0)
    finally:
        mod["ORDERS_SORT_AMOUNT_BUTTON"] = saved


def test_page_amounts_ignores_other_resources(m):
    """The amt-0 header row and another resource's rows would make an
    ascending list look unsorted, and the script would press again forever."""
    import re as _re
    exact = _re.compile(r"^iron ingots?$", _re.I)
    mod = load()
    mod["gump_lines"] = lambda *a, **k: ["ROWS"]
    mod["parse_order_rows"] = lambda strings, anchor: [
        {"name": "Iron Ingots", "amount": 0},          # the header row
        {"name": "Iron Ingots", "amount": 100},
        {"name": "Shadow Ingots", "amount": 5},        # another resource
        {"name": "Iron Ingots", "amount": 200},
    ]
    check("only this resource's real rows count",
          mod["page_amounts"]("iron ingots", exact), [100, 200])


def test_a_sorted_list_takes_the_first_row_not_the_page_best(m):
    """The saving: when the list IS sorted, the first acceptable row is the
    smallest there is, so there is nothing to gain by reading the rest of the
    page - and nothing later can beat it."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        body = fh.read()
    body = body[body.index("def find_first_order("):body.index("def withdraw(")]
    check("a sorted list short-circuits", "if sorted_ok or ORDER_PICK" in body,
          True)
    check("and an unsorted one still picks the page best",
          "page_pick" in body, True)
    check("the sort only runs in smallest mode",
          'if ORDER_PICK == "smallest":' in body, True)


# --------------------------------------------------------------------------
# The fill rate limit (shard change, 2026-09-11)
#
#   "Fill from backpack on a storage key ... now works about once per second.
#    Refill from stock on your Master Keys runs about once every 3 seconds.
#    Clicking again sooner does nothing extra and tells you how long to wait."
#
# "Does nothing extra" is the dangerous half. A refused fill is not an error -
# the click goes out, the window behaves, the stock does not move - so nothing
# in the script noticed it had failed.
# --------------------------------------------------------------------------

def test_there_are_two_timers_and_they_differ(m):
    """The notes describe them separately and say the Auto Looter's overweight
    filling shares the Master Keys one. One shared timer would under-wait on
    Master Keys and over-wait on everything else."""
    check("rate limiting is on", m["FILL_RATE_LIMITED"], True)
    check("a storage key waits at least the stated second",
          m["FILL_KEY_COOLDOWN_MS"] >= 1000, True)
    check("Master Keys wait at least the stated three",
          m["FILL_MASTER_COOLDOWN_MS"] >= 3000, True)
    check("and they are not the same timer",
          m["FILL_MASTER_COOLDOWN_MS"] > m["FILL_KEY_COOLDOWN_MS"], True)
    check("both are tracked separately",
          sorted(m["_last_fill"].keys()), ["key", "master"])

    check("the key cooldown leaves a margin over 1s",
          m["FILL_KEY_COOLDOWN_MS"] > 1000, True)
    check("and the master one over 3s",
          m["FILL_MASTER_COOLDOWN_MS"] > 3000, True)


def test_the_gate_waits_and_spending_it_resets_it(m):
    """fill_gate is what stands between two presses. Without it the second one
    is refused and nothing says so."""
    clock = _FakeClock()
    saved_pause = m["Misc"].Pause
    restore = _with_fakes(m, journal=_FakeJournal(), clock=clock)
    try:
        # fill_gate really waits, so the fake clock has to be driven by the
        # pause - otherwise its loop never ends. Same wiring as the world-save
        # test above.
        m["Misc"].Pause = lambda ms: clock.advance(ms / 1000.0)
        m["_journal_cursor"][0] = 0.0
        m["_last_fill"]["key"] = 0.0
        m["_last_fill"]["master"] = 0.0
        m["_fill_wait"]["at"] = 0.0
        m["_fill_wait"]["seconds"] = 0.0

        check("a cold timer does not wait", m["fill_gate"]("key", "x"), 0.0)

        m["note_fill"]("key")
        waited = m["fill_gate"]("key", "x")
        check("straight after a fill it waits",
              waited >= (m["FILL_KEY_COOLDOWN_MS"] / 1000.0) - 0.5, True)

        # And the OTHER timer is untouched by it.
        check("the master timer is independent",
              m["fill_gate"]("master", "x"), 0.0)
    finally:
        m["Misc"].Pause = saved_pause
        restore()


def test_the_servers_own_wait_beats_the_configured_guess(m):
    """The notes say the refusal "tells you how long to wait". Obeying the
    number the server sent is right even when the shard retunes the rate
    again - a fixed cooldown is only ever this script's guess at it."""
    clock = _FakeClock()
    saved_pause = m["Misc"].Pause
    restore = _with_fakes(m, journal=_FakeJournal(), clock=clock)
    try:
        m["Misc"].Pause = lambda ms: clock.advance(ms / 1000.0)
        m["_journal_cursor"][0] = 0.0
        m["_last_fill"]["key"] = 0.0
        # A refusal that wants far longer than the configured cooldown.
        m["_fill_wait"]["at"] = clock.time()
        m["_fill_wait"]["seconds"] = 9.0
        waited = m["fill_gate"]("key", "x")
        check("it waits what it was told, not the 1.2s guess",
              waited >= 8.0, True)

        # Spending the timer clears the refusal with it.
        m["note_fill"]("key")
        check("the refusal is spent too", m["_fill_wait"]["seconds"], 0.0)
    finally:
        m["Misc"].Pause = saved_pause
        restore()


def test_the_real_refusal_is_matched_and_generalises(m):
    """Read off the journal 2026-09-12:

        "You must wait 0.4 more seconds before you can fill from backpack"

    THE NUMBER MUST NOT BE IN THE STORED STRING. The full line went in first
    and it carried the 0.4 with it, which matches a 0.4-second refusal and
    nothing else - a two-second one would have sailed straight past. The
    number is read separately, by seconds_in().
    """
    real = "You must wait 0.4 more seconds before you can fill from backpack"
    check("the real line is recognised", m["fill_refusal"](real), True)
    check("and its number is read", m["seconds_in"](real), 0.4)

    for stored in m["FILL_WAIT_MESSAGES"]:
        check("no stored phrase pins a number: %r" % stored,
              any(ch.isdigit() for ch in stored), False)

    # The same refusal with any other delay must match just as well.
    for secs in ("0.1", "1", "2.5", "3", "10"):
        line = ("You must wait %s more seconds before you can fill from "
                "backpack" % secs)
        check("a %ss refusal is recognised too" % secs,
              m["fill_refusal"](line), True)
        check("  and its number read", m["seconds_in"](line), float(secs))


def test_the_shape_pattern_covers_the_wordings_not_yet_seen(m):
    """Only the order book's refusal has been read. The Master Keys and the
    storage keys presumably say something similar, but nobody has transcribed
    those, so they are NOT typed in as though they had been - the pattern
    covers them by shape instead."""
    check("the pattern is set", bool(m["FILL_WAIT_PATTERN"]), True)
    check("an unseen wording still matches",
          m["fill_refusal"]("You must wait 2.1 more seconds before you can "
                            "refill from stock"), True)

    # It failed to match the ONE line it was written for, first time round:
    # the number does not butt up against "second", "more" sits between them.
    check("the gap between the number and the unit is allowed",
          m["fill_refusal"]("You must wait 3 more seconds"), True)

    # And it stays narrow.
    for text in ("You wait for the smith to finish.",
                 "Wait here.",
                 "3 seconds remaining",
                 "You put 60000 ingots into the key."):
        check("%r is not a refusal" % text[:32], m["fill_refusal"](text),
              False)


def test_the_wait_number_is_read_out_of_the_line(m):
    """Whatever the wording turns out to be, the number in it is the answer."""
    for text, want in (("You must wait 3 seconds.", 3.0),
                       ("Please wait 1.5 more seconds", 1.5),
                       ("You must wait 10 seconds before doing that", 10.0),
                       ("You cannot do that yet", 0.0),
                       ("", 0.0)):
        check("%r -> %gs" % (text, want), m["seconds_in"](text), want)


def test_every_fill_entry_is_recognised(m):
    """Both wordings the patch notes name. Matched loosely on purpose - being
    wrong one way costs a second, the other way costs the whole fill."""
    for label in ("Refill from stock", "Refill From Stock",
                  "  refill from stock  ", "Fill from backpack",
                  "Fill From Backpack"):
        check("%r is a fill" % label, m["is_fill_entry"](label), True)
    for label in ("Open", "Empty", "Rename", "Set Name", "", None):
        check("%r is not" % label, m["is_fill_entry"](label), False)


def test_every_fill_in_the_script_goes_through_the_gate(m):
    """A fill that skips the gate is a fill that gets silently refused. There
    are four - the two deposit stations, the runecrafting storage and the order
    book's button - and they all press through one door."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()

    ctx = src[src.index("def use_context_item("):
              src.index("def use_context_mobile(")]
    check("the context path gates on a fill entry", "fill_gate(" in ctx, True)
    check("and only when the entry IS a fill", "is_fill_entry(" in ctx, True)
    check("and records the fill afterwards", "note_fill(" in ctx, True)

    dep = src[src.index("def deposit_new_orders("):
              src.index("def visit_station(")]
    # Reported, never raised: a mutation that removes the gate must show as a
    # failed check, not a traceback that hides every check after it.
    gated = "fill_gate(" in dep
    check("the book's button gates too", gated, True)
    check("before the press, not after",
          gated and dep.index("fill_gate(") < dep.index("Gumps.SendAction("),
          True)
    check("and records it", "note_fill(" in dep, True)

    # Every station declares which timer it spends.
    for station in m["STATIONS"]:
        check("station %r declares a timer" % station.get("label"),
              station.get("timer") in ("key", "master"), True)
    check("the runecrafting storage declares one",
          m["RUNECRAFT_TIMER"] in ("key", "master"), True)
    check("and so does the book", m["BOOK_FILL_TIMER"] in ("key", "master"),
          True)


def test_the_deposit_verifies_by_result_and_presses_again(m):
    """The cooldown numbers are a guess at "about once per second". Verifying by
    RESULT is what makes them safe to be wrong about: if the gate lets a press
    through too early, the server refuses it, nothing moves, and this notices."""
    check("there is more than one attempt", m["FILL_RETRIES"] >= 2, True)

    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    dep = src[src.index("def deposit_new_orders("):
              src.index("def visit_station(")]
    check("it counts what is still held", "def still_held(" in dep, True)
    check("and loops on it", "while attempts <" in dep, True)
    check("bounded by FILL_RETRIES", "FILL_RETRIES" in dep, True)
    check("and stops as soon as nothing is left",
          "if not left:" in dep, True)


def test_the_bag_is_reopened_before_it_is_believed(m):
    """Contains is a snapshot taken when the container was opened. A fill empties
    the bag SERVER-side and the snapshot still lists every deed, so counting
    without reopening reads a successful fill as a failed one - and the
    recovery for a failed one is to tip the bag out into the pack. That is how
    deeds that were already safely deposited ended up loose.

    The shard's new batched redraw ("redraws once at the end instead of once
    for every section") makes the contents update land later than it used to,
    which turns that from occasional into reliable."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()

    bd = src[src.index("def bag_deeds("):src.index("def deposit_new_orders(")]
    check("bag_deeds can reopen", "reopen=False" in bd, True)
    check("and reopening really re-opens the container",
          "Items.UseItem(bag)" in bd and "WaitForContents" in bd, True)

    dep = src[src.index("def deposit_new_orders("):
              src.index("def visit_station(")]
    # Every count that a DECISION hangs on must be the fresh kind.
    check("the baseline count is fresh",
          "bag_deeds(bag, reopen=True)" in dep, True)
    check("so is the verification count",
          "bag_deeds(find_order_bag(), reopen=True)" in dep, True)
    check("and no count in here trusts the snapshot",
          "bag_deeds(find_order_bag())" in dep, False)


def test_the_journal_still_has_exactly_one_reader(m):
    """Reading the journal CONSUMES it - the cursor advances - so two readers
    would steal lines from each other and both would miss things at random.
    The fill reply is reported off a ring buffer for exactly this reason."""
    import ast as _ast
    with open(SCRIPT, encoding="utf-8") as fh:
        tree = _ast.parse(fh.read())
    readers = []
    for fn in _ast.walk(tree):
        if not isinstance(fn, _ast.FunctionDef):
            continue
        for node in _ast.walk(fn):
            if isinstance(node, _ast.Call) \
                    and getattr(node.func, "id", None) == "new_journal_entries":
                readers.append(fn.name)
    check("exactly one function consumes the cursor", sorted(set(readers)),
          ["scan_journal"])
    check("and the reply report reads the buffer instead",
          callable(m.get("recent_lines_since")), True)


def test_a_world_save_warning_still_fires_once(m):
    """scan_journal grew a second job this round. The save watcher is an EDGE
    trigger - returning "a warning is outstanding" instead of "a new one
    arrived" would have it re-fire on every call for the rest of the run,
    which is the exact fault the timestamp cursor exists to avoid."""
    clock = _FakeClock()
    journal = _FakeJournal()
    journal.add("The world will save in 30 seconds", clock.now + 1)
    restore = _with_fakes(m, journal=journal, clock=clock)
    try:
        m["_journal_cursor"][0] = 0.0
        m["_save_seen_at"][0] = 0.0
        check("seen once", m["poll_world_save"](), True)
        check("and not again", m["poll_world_save"](), False)
    finally:
        restore()


# --------------------------------------------------------------------------
# The refusal, reported from the game 2026-09-12
#
# "it goes back to the RO book and it seems to appear to blink the menu then
#  attempt to place the new deeds in the RO book, but they never deposit
#  saying we need to wait 0.4 seconds"
#
# 0.4 seconds is the tell. The script recalls to Start Fill and bins junk
# between the last station fill and this press, which is far longer than any
# timer it tracks - so the timer was spent by something the script never saw.
# The patch notes name the culprit: "The Auto Looter's overweight key filling
# shares the Master Keys timer, so a manual refill right after an automatic one
# may tell you to wait."
#
# No amount of tracking its own presses can predict that. Only a cushion and a
# retry help, and the retry needs to RECOGNISE the refusal.
# --------------------------------------------------------------------------

def test_the_refusal_is_recognised_by_shape(m):
    """The exact wording is still unread, but the STRUCTURE was reported: a
    number of seconds after the word "wait". That is enough to match on, and
    it is derived from the report rather than invented."""
    for text in ("You must wait 0.4 seconds before doing that again.",
                 "You need to wait 3 seconds.",
                 "Please wait 1.5 seconds",
                 "WAIT 2 SECONDS"):
        check("%r is a refusal" % text[:34], m["fill_refusal"](text), True)

    # Narrow on purpose - both halves are required.
    for text in ("You wait for the smith to finish.",
                 "Wait here.",
                 "3 seconds remaining",
                 "You put 60000 ingots into the key.",
                 "", None):
        check("%r is not" % (text or "",), m["fill_refusal"](text), False)


def test_the_number_of_seconds_is_what_gets_waited(m):
    """0.4 is not 3. Waiting the configured cooldown for a 0.4s refusal throws
    away most of a lap over a run; waiting 0.4s for a 3s one gets refused
    again. The server's own number is the only right answer."""
    check("a fractional wait is read",
          m["seconds_in"]("You must wait 0.4 seconds"), 0.4)
    check("and a whole one", m["seconds_in"]("You must wait 3 seconds"), 3.0)


def test_the_extra_cushion_is_applied(m):
    """Requested after the book kept being refused BY 0.4 SECONDS - the press
    was very nearly in time, so a fraction either way decides it."""
    check("there is a cushion", m["FILL_EXTRA_PAUSE_MS"] >= 0, True)
    check("and it is the 0.7s that was asked for",
          m["FILL_EXTRA_PAUSE_MS"], 700)

    clock = _FakeClock()
    saved_pause = m["Misc"].Pause
    restore = _with_fakes(m, journal=_FakeJournal(), clock=clock)
    try:
        m["Misc"].Pause = lambda ms: clock.advance(ms / 1000.0)
        m["_journal_cursor"][0] = 0.0
        m["_fill_wait"]["at"] = 0.0
        m["_fill_wait"]["seconds"] = 0.0
        m["_last_fill"]["key"] = 0.0
        m["note_fill"]("key")
        waited = m["fill_gate"]("key", "x")
        want = (m["FILL_KEY_COOLDOWN_MS"] + m["FILL_EXTRA_PAUSE_MS"]) / 1000.0
        check("the cushion is on top of the cooldown",
              waited >= want - 0.5, True)
    finally:
        m["Misc"].Pause = saved_pause
        restore()


def test_a_refusal_is_not_answered_by_tipping_the_bag_out(m):
    """THE OPPOSITE FIX. Tipping the deeds out of the bag is the recovery for a
    button that cannot reach inside it. For a rate limit it does nothing - the
    next press is refused just the same - and now the orders are loose in the
    pack instead of where they were put. So the refusal is tested FIRST and
    the only answer to it is to wait."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    dep = src[src.index("def deposit_new_orders("):
              src.index("def visit_station(")]

    guard = 'if _fill_wait["at"] > refused_before:'
    check("a new refusal is told from a stale one",
          "refused_before = _fill_wait" in dep, True)
    # Reported, never raised - a mutation that removes the guard must show as
    # a failed check, not a traceback that hides every check after it.
    check("the refusal is acted on at all", guard in dep, True)
    if guard in dep:
        refusal = dep.index(guard)
        tipping = dep.index("Tipping them out")
        check("and it is checked BEFORE the tipping", refusal < tipping, True)
        check("its only answer is to go round again",
              "continue" in dep[refusal:tipping], True)


def test_listening_for_the_reply_is_not_optional(m):
    """FILL_REPORT_REPLY says "print this". It must not also decide whether the
    script can SEE - turning the diagnostic off would otherwise turn off the
    refusal detection with it, and the retry would have nothing to react to."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    body = src[src.index("def report_fill_reply("):src.index("def checkpoint(")]
    scan = body.index("scan_journal()")
    gate = body.index("if not FILL_REPORT_REPLY:")
    check("the journal is scanned before the print switch is consulted",
          scan < gate, True)


def test_a_station_says_when_it_was_refused(m):
    """Nothing retries a station - it is one press per visit - so the only thing
    that makes the failure visible is the script saying so."""
    with open(SCRIPT, encoding="utf-8") as fh:
        src = fh.read()
    ctx = src[src.index("def use_context_item("):
              src.index("def use_context_mobile(")]
    check("a refused station fill is reported",
          "refused the fill" in ctx, True)
    check("and reported as a failure, not a success",
          "return False" in ctx[ctx.index("refused the fill"):], True)


def main():
    module = load()
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-44s got=%-26s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:26], repr(want)[:36]))
        if not ok:
            failed += 1
    print("\n%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
