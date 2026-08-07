"""Tests for diag_resource_orders.py.

Same approach as test_tame_animals.py: read the script, strip the trailing
main() call, exec it against stub Razor objects, and call the REAL functions.
Nothing is reimplemented here, so nothing can drift.

    python tests/test_resource_orders.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "Scripts", "diag_resource_orders.py")

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


# ---------------------------------------------------------------------------
# Stubs. The script only touches these at call time, so a bare namespace is
# enough to get the module body executed.
# ---------------------------------------------------------------------------

class _Stub(object):
    def __getattr__(self, name):
        return lambda *a, **k: None


class FakeItem(object):
    def __init__(self, name, amount, item_id, hue, serial=0x1, tooltip=None):
        self.Name = name
        self.Amount = amount
        self.ItemID = item_id
        self.Hue = hue
        self.Serial = serial
        self.tooltip = tooltip if tooltip is not None else [name]


class FakeContainer(object):
    def __init__(self, items):
        self.Contains = items


def load():
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)

    module = {
        "__name__": "diag_resource_orders",
        "Misc": _Stub(), "Player": _Stub(), "Items": _Stub(),
        "Gumps": _Stub(), "Mobiles": _Stub(), "Target": _Stub(),
        "Journal": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), module)

    # census() reads tooltips through props(); point that at the fake item.
    module["props"] = lambda item: list(getattr(item, "tooltip", []))
    return module


# ---------------------------------------------------------------------------
# Tooltip de-concatenation and deed parsing
# ---------------------------------------------------------------------------

def test_spaced(m):
    raw = "Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:"
    out = m["spaced"](raw)
    check("seam inserted before Creature", "2Creature" in out, False)
    check("kirinfilled no longer fused", "KirinFilled" in out, False)
    check("value still readable", "Creature Type: Kirin" in out, True)


# The real deed, verbatim from the Item Inspector on 2026-07-27.
#
# An earlier version of these tests asserted a "Level: / Resource Type: /
# Filled:" shape, inferred from a comment in harvest_runner.py. The live deed
# has none of those labels - that format belongs to TAMING orders, which
# tame_animals.py handles separately. The tests were asserting the guess.
REAL_DEED = ["A Resource Order Deed", "Blessed", "Weight: 1 Stone",
             "0 / 132 Valorite Granite ObtainedValued At: 400 Gold Each"]


def test_parse_the_real_deed(m):
    fields = m["parse_deed"](" ".join(REAL_DEED))
    check("filled parsed", fields.get("filled"), 0)
    check("needed parsed", fields.get("needed"), 132)
    check("resource parsed", fields.get("resource"), "Valorite Granite")
    check("gold each parsed", fields.get("gold_each"), 400)
    check("progress", m["deed_progress"](fields), (0, 132))


def test_obtained_valued_seam(m):
    """"ObtainedValued" arrives as one word; without the seam fix the resource
    name runs into the next property and nothing matches."""
    out = m["spaced"](" ".join(REAL_DEED))
    check("seam split", "ObtainedValued" in out, False)
    check("resource intact", "Valorite Granite Obtained" in out, True)


def test_multi_word_resource(m):
    fields = m["parse_deed"](
        "240 / 900 Shadow Iron Ingots ObtainedValued At: 12 Gold Each")
    check("two-word metal kept whole", fields.get("resource"),
          "Shadow Iron Ingots")
    check("partial progress", m["deed_progress"](fields), (240, 900))


def test_deed_progress_missing(m):
    check("no progress fields", m["deed_progress"]({}), (None, None))
    check("unparseable tooltip", m["parse_deed"]("just some text"), {})


# ---------------------------------------------------------------------------
# Ingot census and the fill budget
# ---------------------------------------------------------------------------

def test_census_keys_metal_by_hue_not_name(m):
    """THE BUG THE FIRST LIVE RUN FOUND. Every stack in the chest is named
    "<amount> ingots" - "60000 ingots", "59994 ingots". Keying by name invented
    a type per stack size AND merged five different metals that happened to
    hold 60000 each into one bucket of 300000."""
    chest = FakeContainer([
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x096D, 0x11),   # Copper
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x0966, 0x12),   # Shadow Iron
        FakeItem("60000 ingots", 60000, 0x1BF2, 0x0000, 0x13),   # Iron
        FakeItem("59994 ingots", 59994, 0x1BF2, 0x0973, 0x14),   # Dull Copper
    ])
    _rows, ingots = m["census"](chest)
    check("four distinct metals", sorted(ingots),
          ["copper", "dull copper", "iron", "shadow iron"])
    check("same-size stacks not merged", ingots["copper"]["amount"], 60000)
    check("no phantom amount-keyed type", "60000 ingots" in ingots, False)


def test_metal_names_match_servuo(m):
    """Hues from ServUO Scripts/Misc/ResourceInfo.cs. All nine share ItemID
    0x1BF2, so the hue is the only thing that names the metal."""
    for hue, want in [(0x0000, "Iron"), (0x0973, "Dull Copper"),
                      (0x0966, "Shadow Iron"), (0x096D, "Copper"),
                      (0x0972, "Bronze"), (0x08A5, "Gold"),
                      (0x0979, "Agapite"), (0x089F, "Verite"),
                      (0x08AB, "Valorite")]:
        check("hue 0x%04X" % hue, m["metal_name"](0x1BF2, hue), want)


def test_unknown_hue_is_named_not_guessed(m):
    """A shard-custom metal must show up as a gap, never be folded into iron."""
    chest = FakeContainer([FakeItem("500 ingots", 500, 0x1BF2, 0x04F7, 0x51)])
    _rows, ingots = m["census"](chest)
    check("unknown hue flagged", "unknown (hue 0x04f7)" in ingots, True)
    check("not silently iron", "iron" in ingots, False)


def test_strip_amount(m):
    check("amount stripped", m["strip_amount"]("60000 ingots"), "ingots")
    check("comma amount stripped", m["strip_amount"]("1,494 ingots"), "ingots")
    check("bare name untouched", m["strip_amount"]("a pickaxe"), "a pickaxe")


def test_census_sums_split_stacks(m):
    """The reserve is per METAL, so two stacks of the same metal are added
    together BEFORE the 100 comes off - otherwise each stack keeps its own 100."""
    chest = FakeContainer([
        FakeItem("60 ingots", 60, 0x1BF2, 0x08AB, 0x21),
        FakeItem("90 ingots", 90, 0x1BF2, 0x08AB, 0x22),
    ])
    _rows, ingots = m["census"](chest)
    check("stacks summed", ingots["valorite"]["amount"], 150)
    budget = m["fill_budget"](ingots, keep=100)
    check("reserve applied once", budget["valorite"]["available"], 50)


def test_non_ingots_excluded(m):
    chest = FakeContainer([
        FakeItem("a pickaxe", 1, 0x0E86, 0x0000, 0x31),
        FakeItem("1040 Blue Diamond", 1040, 0x3198, 0x0000, 0x32),
        FakeItem("840 log", 840, 0x1BDD, 0x0000, 0x33),
    ])
    rows, ingots = m["census"](chest)
    check("all stacks listed", len(rows), 3)
    check("nothing counted as ingots", ingots, {})


def test_fill_budget_keeps_reserve(m):
    ingots = {
        "valorite": {"name": "Valorite", "amount": 672, "ids": set(), "hues": set()},
        "iron": {"name": "Iron", "amount": 100, "ids": set(), "hues": set()},
        "verite": {"name": "Verite", "amount": 12, "ids": set(), "hues": set()},
    }
    budget = m["fill_budget"](ingots, keep=100)
    check("surplus spendable", budget["valorite"]["available"], 572)
    check("exactly at reserve spends nothing", budget["iron"]["available"], 0)
    check("below reserve never negative", budget["verite"]["available"], 0)


def test_census_uses_tooltip_when_name_blank(m):
    """Item.Name is often empty until props load; the tooltip is the fallback."""
    chest = FakeContainer([
        FakeItem("", 300, 0x1BF2, 0x08A5, 0x41, tooltip=["300 ingots"]),
    ])
    _rows, ingots = m["census"](chest)
    check("named from tooltip", ingots["gold"]["amount"], 300)


# ---------------------------------------------------------------------------
# Gump layout parsing
# ---------------------------------------------------------------------------

LAYOUT = (
    "{ page 0 }"
    "{ gumppic 0 0 5170 }"
    "{ text 60 40 0 0 }"
    "{ text 60 60 0 1 }"
    "{ text 60 80 0 2 }"
    "{ text 100 120 0 3 }{ text 300 120 0 4 }{ text 400 120 0 5 }"
    "{ button 40 120 4005 4007 1 0 7 }"
    "{ text 100 140 0 6 }{ text 300 140 0 7 }{ text 400 140 0 8 }"
    "{ button 40 142 4005 4007 1 0 8 }"
)
STRINGS = [
    "Resource Orders", "Contents: 8653/100000", "Displayed: 980",
    "Mythril Ingots", "672", "100",
    "Valorite Ingots", "937", "100",
]


def test_layout_buttons(m):
    ids = [b[2] for b in m["layout_buttons"](LAYOUT)]
    check("button ids found", ids, [7, 8])


def test_layout_texts(m):
    ids = [t[2] for t in m["layout_texts"](LAYOUT)]
    check("text ids found", sorted(ids), list(range(9)))


def test_pair_rows_by_coordinate(m):
    """Pairing by Y, not by counting: the button for row 2 is drawn 2px off its
    baseline, and the header lines carry no button at all."""
    rows = m["pair_rows"](LAYOUT, STRINGS)
    with_buttons = [r for r in rows if r["buttons"]]
    check("two order rows", len(with_buttons), 2)

    first = with_buttons[0]
    check("row 1 button", [b for _x, b in first["buttons"]], [7])
    check("row 1 cells", [v for _x, v in first["cells"]],
          ["Mythril Ingots", "672", "100"])

    second = with_buttons[1]
    check("row 2 button despite 2px offset", [b for _x, b in second["buttons"]], [8])
    check("row 2 cells", [v for _x, v in second["cells"]],
          ["Valorite Ingots", "937", "100"])


def test_header_rows_have_no_button(m):
    rows = m["pair_rows"](LAYOUT, STRINGS)
    header = [r for r in rows if not r["buttons"]]
    values = [v for r in header for _x, v in r["cells"]]
    check("header text kept out of the order rows",
          "Resource Orders" in values, True)
    check("header carries no button",
          all(not r["buttons"] for r in header), True)


def test_pair_rows_ignores_layout_text_ids(m):
    """THE OTHER BUG THE LIVE RUN FOUND. Razor drops empty strings from the
    gump table without leaving a gap (Handlers.cs increments its index only for
    non-empty strings), so layout text ids stop matching the string list. Here
    ids 0 and 3 are absent from `strings`; pairing must go by ORDER."""
    layout = (
        "{ text 100 120 0 1 }{ text 300 120 0 2 }"
        "{ button 40 120 4005 4007 1 0 7 }"
        "{ text 100 140 0 4 }{ text 300 140 0 5 }"
        "{ button 40 140 4005 4007 1 0 8 }"
    )
    strings = ["Mythril Ingots", "671", "Valorite Ingots", "809"]
    rows = [r for r in m["pair_rows"](layout, strings) if r["buttons"]]
    check("row 1 read positionally", [v for _x, v in rows[0]["cells"]],
          ["Mythril Ingots", "671"])
    check("row 2 read positionally", [v for _x, v in rows[1]["cells"]],
          ["Valorite Ingots", "809"])
    check("no <id N?> placeholders",
          any("<" in str(v) for r in rows for _x, v in r["cells"]), False)


def test_string_index_shift_uses_an_anchor_not_a_count(m):
    """The first version compared element count to string count and reported a
    shift of 0 on a page that had lost NINE strings - because the dropped ones
    were textentry values, which the element count already excludes. Anchoring
    on the "Previous Page" label is exact."""
    layout = (
        "{ text 40 50 0 3 }"
        "{ croppedtext 40 90 140 20 1153 13 }"
        "{ croppedtext 190 90 90 20 1153 14 }"
        "{ text 40 440 88 88 }"          # "Previous Page", element index 3
        "{ text 480 440 88 89 }"
    )
    aligned = ["Value Per", "Iron Ingots", "500", "Previous Page", "Next Page"]
    check("no shift when aligned", m["string_index_shift"](layout, aligned), 0)

    shifted = ["Value Per", "Iron Ingots", "Previous Page", "Next Page"]
    check("shift of one detected", m["string_index_shift"](layout, shifted), 1)
    check("absent anchor returns None",
          m["string_index_shift"](layout, ["nothing", "here"]), None)


# Page 1 of the live "Valorite" run, verbatim. Note the FIRST row renders three
# cells because its Amt To Gather is 0, and the two blank column-4/5 headers are
# gone as well - four dropped strings before the rows even start.
REAL_PAGE1 = [
    "Resource Orders", "Contents: 8658/100000", "Displayed: 230",
    "Name", "Amt To Gather", "Value Per",
    "Valorite Granite", "0", "No",
    "Valorite Granite", "155", "0", "400", "No",
    "Valorite Granite", "155", "0", "400", "No",
    "Valorite Granite", "156", "0", "400", "No",
    "Previous Page", "Next Page", "(1/16)", "Add", "Purge",
    "Fill from backpack", "", "None", "None", "None",
]


def test_zero_amount_first_row_does_not_shift_the_rest(m):
    """Every page opens with an Amt To Gather of 0. It must consume exactly one
    row so the remaining orders still line up with their own buttons."""
    rows = m["parse_order_rows"](REAL_PAGE1)
    check("four rows", len(rows), 4)
    check("amounts", [r["amount"] for r in rows], [0, 155, 155, 156])
    check("all named", [r["name"] for r in rows], ["Valorite Granite"] * 4)


def test_substring_filter_trap(m):
    """Filtering "Valorite" returned 230 rows of Valorite GRANITE and not one
    ingot order. Whatever consumes these rows has to check the name, not assume
    the filter did it."""
    rows = m["parse_order_rows"](REAL_PAGE1)
    check("granite is not an ingot order",
          any("ingot" in r["name"].lower() for r in rows), False)


def test_page_counter_reads_sixteen(m):
    check("filtered page count", m["page_counter"](REAL_PAGE1), (1, 16))


# The real page-2 string list, verbatim from the live dump. Note the first order
# renders THREE cells (its Amt To Gather is 0) where every other renders five.
REAL_STRINGS = [
    "Resource Orders", "Contents: 8656/100000", "Displayed: 980",
    "Name", "Amt To Gather", "Value Per",
    "Mythril Ingots", "0", "No",
    "Mythril Ingots", "671", "0", "100", "No",
    "Mythril Ingots", "809", "0", "100", "No",
    "Mythril Ingots", "655", "0", "100", "No",
    "Previous Page", "Next Page", "(2/66)", "Add", "Purge",
    "Fill from backpack", "", "None", "None", "None",
]


def test_parse_order_rows_from_real_capture(m):
    rows = m["parse_order_rows"](REAL_STRINGS)
    check("four orders parsed", len(rows), 4)
    check("names", [r["name"] for r in rows], ["Mythril Ingots"] * 4)
    check("amounts", [r["amount"] for r in rows], [0, 671, 809, 655])


def test_parse_order_rows_excludes_header_and_footer(m):
    names = [r["name"] for r in m["parse_order_rows"](REAL_STRINGS)]
    for unwanted in ("Name", "Amt To Gather", "Value Per", "Previous Page",
                     "Next Page", "Add", "Purge", "Fill from backpack",
                     "Resource Orders"):
        check("%r excluded" % unwanted, unwanted in names, False)


def test_short_row_does_not_shift_later_rows(m):
    """The whole point: the 3-cell first row must not consume the next row's
    name. If it did, every amount after it would belong to the wrong order."""
    rows = m["parse_order_rows"](REAL_STRINGS)
    check("first order amount", rows[0]["amount"], 0)
    check("second order amount", rows[1]["amount"], 671)
    check("last order amount", rows[-1]["amount"], 655)


def test_yes_no_flags_never_start_a_row(m):
    rows = m["parse_order_rows"](
        ["Value Per", "Copper Ingots", "40", "0", "100", "Yes",
         "Iron Ingots", "12", "0", "100", "No", "Previous Page"])
    check("flags skipped", [r["name"] for r in rows],
          ["Copper Ingots", "Iron Ingots"])
    check("amounts still right", [r["amount"] for r in rows], [40, 12])


def test_page_counter(m):
    check("page counter", m["page_counter"](REAL_STRINGS), (2, 66))
    check("absent counter", m["page_counter"](["nothing"]), (None, None))


# The real page-2 layout, trimmed to the row region plus the footer nav.
REAL_LAYOUT = (
    "{ page 0 }{ resizepic 0 0 9270 600 530 }"
    "{ button 40 70 5600 5604 1 0 10 }{ button 55 70 5602 5606 1 0 11 }"
    "{ button 20 93 1209 1209 1 0 115 }"
    "{ button 20 113 1209 1209 1 0 116 }"
    "{ button 20 133 1209 1209 1 0 117 }"
    "{ button 95 410 5601 5605 1 0 12 }"
    "{ button 20 440 5603 5607 1 0 4 }{ button 560 440 5601 5605 1 0 5 }"
    "{ button 350 475 1209 1210 1 0 1 }"
)


def test_row_buttons_exclude_sorters_and_nav(m):
    """115-117 are the row buttons. 10/11 are column sorters at y=70, 12 is a
    filter submit at y=410, 4/5 are page nav at y=440 - none may be returned."""
    check("only row buttons", m["row_buttons"](REAL_LAYOUT), [115, 116, 117])


def test_row_buttons_are_in_display_order(m):
    check("top to bottom", m["row_buttons"](REAL_LAYOUT) ==
          sorted(m["row_buttons"](REAL_LAYOUT)), True)


def test_parse_header(m):
    info = m["parse_header"](STRINGS)
    check("stored", info.get("stored"), 8653)
    check("capacity", info.get("capacity"), 100000)
    check("displayed", info.get("displayed"), 980)


def test_layout_ignores_non_button_elements(m):
    """gumppic and page markers must not be mistaken for buttons."""
    check("gumppic not a button",
          m["layout_buttons"]("{ gumppic 0 0 5170 }{ page 1 }"), [])


def main():
    module = load()
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-46s got=%-28s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:28], repr(want)[:40]))
        if not ok:
            failed += 1

    print("\n%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
