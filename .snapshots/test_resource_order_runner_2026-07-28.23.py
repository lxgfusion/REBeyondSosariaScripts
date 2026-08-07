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


def test_final_deposit_runs_when_the_run_ends(m):
    """Asked for: once nothing else can be filled, use the Deposit items rune
    and stop. The last lap's rewards are still in the pack at that point."""
    check("one final stop", m["FINAL_STATIONS"], ["Deposit items"])

    labels = [s["label"] for s in m["STATIONS"]]
    for name in m["FINAL_STATIONS"]:
        check("%r is a real station" % name, name in labels, True)

    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    main_fn = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "main"][0]

    # The final visit has to be AFTER the lap loop, not inside it.
    loop_lines = [n.lineno for n in ast.walk(main_fn) if isinstance(n, ast.For)
                  and isinstance(n.iter, ast.Call)
                  and getattr(n.iter.func, "id", None) == "range"]
    visits = [n.lineno for n in ast.walk(main_fn) if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "visit_station"]
    check("main visits a station at the end", len(visits) >= 1, True)
    check("and it is after the lap loop",
          all(v > max(loop_lines) for v in visits), True)


def test_orders_action_waits_for_the_content_to_change(m):
    """THE COPPER BUG, second cause. Gumps.WaitForGump returns True at once for
    a gump that is already open, and the server answers this button by
    replacing the list with a NEW gump under the SAME id - so waiting on the id
    handed back the OLD page.

    Read after a filter, that stale page holds somebody else's rows: the anchor
    matches none, rows and buttons disagree, the page is skipped, and the
    resource is reported as having no orders."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "orders_action"][0]
    src = ast.dump(fn)

    check("takes a fingerprint first", "gump_fingerprint" in src, True)
    check("polls for a change",
          any(isinstance(n, ast.While) for n in ast.walk(fn)), True)
    check("no longer trusts WaitForGump alone",
          "WaitForGump" in src, False)

    # The fingerprint has to actually reflect the rows, not just the gump id.
    finger = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "gump_fingerprint"][0]
    check("fingerprint reads the lines",
          "gump_lines" in ast.dump(finger), True)


def test_page_is_read_as_one_snapshot(m):
    """Rows come from GetLineList and buttons from GetGumpRawLayout - two
    separate calls. A page landing between them gives rows from one page and
    buttons from another, and because both carry 15 rows the count check passes
    and the WRONG order gets pressed."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    reader = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "read_page"]
    check("there is an atomic reader", len(reader), 1)
    src = ast.dump(reader[0])
    check("it fingerprints either side", src.count("gump_fingerprint") >= 2, True)
    check("and retries when it moved",
          any(isinstance(n, ast.For) for n in ast.walk(reader[0])), True)

    # find_first_order must use it rather than reading the two separately.
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "find_first_order"][0]
    calls = [getattr(c.func, "id", None) for c in ast.walk(fn)
             if isinstance(c, ast.Call)]
    check("the scan reads through it", "read_page" in calls, True)
    check("and not the raw layout directly", "raw_layout" in calls, False)


def test_torn_read_is_bounded(m):
    """It must give up rather than spin if the list never settles."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    reader = [n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "read_page"][0]
    loops = [n for n in ast.walk(reader) if isinstance(n, ast.For)]
    check("the retry loop is a bounded range", len(loops), 1)
    check("bounded by range()",
          any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "range"
              for c in ast.walk(loops[0].iter)) or
          (isinstance(loops[0].iter, ast.Call)
           and getattr(loops[0].iter.func, "id", None) == "range"), True)


def test_change_wait_is_bounded(m):
    """It must not hang when the content legitimately does not change - the
    last page of a filter, or a re-filter with the same term."""
    check("timeout set", 500 <= m["GUMP_CHANGE_TIMEOUT_MS"] <= 15000, True)
    check("poll interval sane", 20 <= m["GUMP_POLL_MS"] <= 1000, True)
    check("polls several times before giving up",
          m["GUMP_CHANGE_TIMEOUT_MS"] // m["GUMP_POLL_MS"] >= 5, True)


def test_biggest_order_on_the_page_is_taken(m):
    """The goal is emptying the chest, so a bigger order is worth more per
    withdrawal - same deed, same trip, more stock spent."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "find_first_order"][0]
    src = ast.dump(fn)
    check("it compares candidates rather than taking the first",
          "best" in src, True)

    # Simulated against a page with mixed amounts.
    page = ["Name", "Amt To Gather", "Amt Gathered", "Value Per", "Completed"]
    for amt in (1647, 2693, 1745):
        page += ["Copper Ingots", str(amt), "0", "25", "No"]
    page += ["Previous Page", "Next Page", "(1/10)"]
    rows = m["parse_order_rows"](page, "copper ingots")
    check("largest is available to choose",
          max(r["amount"] for r in rows), 2693)


def test_every_page_of_a_filtered_result_is_scanned(m):
    """THE COPPER FIX. "Copper Ingots" also returns all 101 "Dull Copper
    Ingots" rows, which fill the early pages. A four-page scan reported no
    Copper orders with 31 waiting further in. The scan now runs to the last
    page the gump reports."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = [n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "find_first_order"][0]
    src = ast.dump(fn)
    check("it reads the page counter", "page_counter" in src, True)
    check("and pages on the next button", "ORDERS_NEXT_BUTTON" in src, True)
    check("cap clears the busiest filter (179 orders / 15 a page)",
          m["MAX_PAGES_PER_RESOURCE"] >= 12, True)
    check("copper's ~10 pages are well within it",
          m["MAX_PAGES_PER_RESOURCE"] >= 10, True)


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
    check("still bounded", 1 <= m["MAX_CYCLES"] <= 1000, True)
    check("room for far more than one lap's worth",
          m["MAX_CYCLES"] * m["MAX_ORDERS_PER_RUN"] >= 2000, True)


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
    names = set(r["name"] for r in m["RESOURCES"])
    check("79 names", len(names), 79)
    check("shadow iron is 'Shadow Ingots'", "Shadow Ingots" in names, True)
    check("plain leather is 'Regular Leather'",
          "Regular Leather" in names, True)
    check("bare 'Leather' is not a book name", "Leather" in names, False)
    check("book capitalisation kept", "Eye of the Travesty" in names, True)
    for gone in ("Perfect Emerald", "Zealot Heart", "Rare Serpent Egg",
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
    check("the scan covers every page of a filtered result",
          m["MAX_PAGES_PER_RESOURCE"] >= 13, True)


def test_lap_order_skips_resources_with_no_stock(m):
    """THE COPPER BUG. The table holds all 79 book names ordered by how many
    orders the book has, so Copper Ingots sits at position 57. Walking the full
    table spends the withdrawal cap on Granite, Boards, Scales and classic gems
    there is no stock for."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fill = [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "fill_orders"][0]

    filtered = False
    for node in ast.walk(fill):
        if not isinstance(node, ast.ListComp):
            continue
        uses_worked = any(isinstance(c, ast.Call)
                          and getattr(c.func, "id", None) == "worked_resources"
                          for c in ast.walk(node))
        uses_budget = any(isinstance(c, ast.Name) and c.id == "budget"
                          for c in ast.walk(node))
        if uses_worked and uses_budget and node.generators[0].ifs:
            filtered = True
    check("lap order is built from what is in stock", filtered, True)


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


def test_a_barren_lap_does_not_end_the_run(m):
    """The rotation can land on a stretch of resources with no orders. Stopping
    on the first empty lap would abandon everything after it."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    main_fn = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "main"][0]
    src = ast.dump(main_fn)
    check("counts consecutive empty laps", "barren" in src, True)
    check("needs a full sweep before stopping", "sweep" in src, True)


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
    check("the single-order gems trail", names[-1], "Turquoise")
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
    check("not an unbounded batch", m["MAX_ORDERS_PER_RUN"] <= 25, True)


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

    Perfect Emerald is deliberately absent: the book has ZERO orders for it,
    so an entry would only cost a fruitless search every lap."""
    by_name = dict((r["name"], r) for r in m["RESOURCES"])
    for name, item_id in [("Blue Diamond", 0x3198), ("Brilliant Amber", 0x3199),
                          ("Dark Sapphire", 0x3192), ("Ecru Citrine", 0x3195),
                          ("Fire Ruby", 0x3197),
                          ("Turquoise", 0x3193), ("White Pearl", 0x3196)]:
        entry = by_name.get(name, {})
        check("%s graphic" % name, entry.get("id"), item_id)
        check("%s hue is any" % name, entry.get("hue"), -1)
    check("Perfect Emerald absent - the book never asks",
          "Perfect Emerald" in by_name, False)


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
