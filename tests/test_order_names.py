"""Tests for Scripts/diag_order_names.py.

Reads the script, strips the trailing main() call, execs it against stub Razor
objects and calls the REAL functions. Fixtures are verbatim captures.

    python tests/test_order_names.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "Scripts", "diag_order_names.py")

_checks = []


def check(label, got, want):
    _checks.append((label, got, want, got == want))


class _Stub(object):
    def __getattr__(self, name):
        return lambda *a, **k: None


def load():
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        source = fh.read()
    source = re.sub(r"^main\(\)\s*$", "", source, flags=re.M)
    module = {
        "__name__": "diag_order_names",
        "Misc": _Stub(), "Player": _Stub(), "Items": _Stub(),
        "Gumps": _Stub(), "Mobiles": _Stub(), "Target": _Stub(),
        "Journal": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), module)
    return module


# A real page, verbatim. Note the first order renders THREE cells because its
# Amt To Gather is 0, where the rest render five.
REAL_PAGE = [
    "Resource Orders", "Contents: 8658/100000", "Displayed: 230",
    "Name", "Amt To Gather", "Value Per",
    "Valorite Granite", "0", "No",
    "Valorite Granite", "155", "0", "400", "No",
    "Valorite Granite", "156", "0", "400", "No",
    "Previous Page", "Next Page", "(1/16)", "Add", "Purge",
    "Fill from backpack", "", "None", "None", "None",
]


def test_names_from_a_real_page(m):
    names = m["names_on_page"](REAL_PAGE)
    check("three orders found", len(names), 3)
    check("all the same resource", set(names), set(["Valorite Granite"]))


def test_short_zero_row_still_counts(m):
    """The first row of every page has Amt To Gather 0 and renders fewer cells.
    It is still an order and its name still counts."""
    names = m["names_on_page"](REAL_PAGE)
    check("the amt-0 row was not dropped", names.count("Valorite Granite"), 3)


def test_header_and_footer_are_excluded(m):
    names = m["names_on_page"](REAL_PAGE)
    for junk in ("Name", "Amt To Gather", "Value Per", "Previous Page",
                 "Next Page", "Add", "Purge", "Fill from backpack",
                 "Resource Orders"):
        check("%r excluded" % junk, junk in names, False)


def test_five_column_header_is_handled(m):
    """The rendered gump shows five headers. Anchoring on "Value Per" alone -
    the fourth of five - would leave "Completed" in the row region."""
    page = ["Name", "Amt To Gather", "Amt Gathered", "Value Per", "Completed",
            "Fire Ruby", "26", "0", "3000", "No",
            "Previous Page", "Next Page", "(1/2)"]
    check("one order", m["names_on_page"](page), ["Fire Ruby"])


def test_runic_column_is_not_mistaken_for_a_name(m):
    """THE REASON FOR THE 'FOLLOWED BY A NUMBER' RULE. The Runics column can
    hold an actual runic's name, which has letters like any resource. Nothing
    numeric follows it, which is what tells them apart - and matters here
    because an unfiltered walk has no filter term to anchor on."""
    page = [
        "Name", "Amt To Gather", "Value Per",
        "Iron Ingots", "500", "0", "100", "Dull Copper Runic",
        "Iron Ingots", "600", "0", "100", "Valorite Runic",
        "Previous Page", "Next Page", "(1/3)",
    ]
    names = m["names_on_page"](page)
    check("only the real orders", names, ["Iron Ingots", "Iron Ingots"])
    check("runic name rejected", "Dull Copper Runic" in names, False)
    check("second runic rejected", "Valorite Runic" in names, False)


def test_multi_word_names_survive(m):
    page = ["Name", "Amt To Gather", "Value Per",
            "Spleen Of The Putrefier", "11", "0", "3000", "No",
            "Essence Of Raging Storms", "16", "0", "3000", "No",
            "Previous Page"]
    check("both kept whole", m["names_on_page"](page),
          ["Spleen Of The Putrefier", "Essence Of Raging Storms"])


def test_commas_in_amounts_are_still_numeric(m):
    page = ["Name", "Amt To Gather", "Value Per",
            "Iron Ingots", "1,932", "0", "30", "No", "Previous Page"]
    check("comma amount recognised", m["names_on_page"](page), ["Iron Ingots"])


def test_page_counter(m):
    check("counter read", m["page_counter"](REAL_PAGE), (1, 16))
    check("absent", m["page_counter"](["nothing"]), (None, None))


def test_header_counts(m):
    info = m["parse_header"](REAL_PAGE)
    check("stored", info.get("stored"), 8658)
    check("displayed", info.get("displayed"), 230)


def test_page_ceiling_covers_the_book(m):
    """The book is 540 pages / 8085 deeds at 15 a page."""
    check("ceiling clears 540 pages", m["MAX_PAGES"] >= 540, True)
    check("walks the whole book by default", m["STOP_AFTER_QUIET_PAGES"], 0)
    check("no filter by default", m["FILTER_TERM"], "")


def test_writes_periodically(m):
    """540 pages is about ten minutes; stopping early must still leave results."""
    check("writes during the walk", 1 <= m["WRITE_EVERY"] <= 100, True)


def main():
    module = load()
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-46s got=%-24s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:24], repr(want)[:34]))
        if not ok:
            failed += 1
    print("\n%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
