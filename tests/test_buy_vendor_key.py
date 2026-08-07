"""Tests for Scripts/buy_vendor_key.py.

Reads the script, strips the trailing main() call, execs it against stub Razor
objects and calls the REAL functions - so there is no copied logic to drift.

The important ones are the SAFETY tests: this script spends gold, and the
failure that matters is pressing the wrong context entry.

    python tests/test_buy_vendor_key.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "Scripts", "buy_vendor_key.py")

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
        "__name__": "buy_vendor_key",
        "Misc": _Stub(), "Player": _Stub(), "Items": _Stub(),
        "Gumps": _Stub(), "Mobiles": _Stub(), "Target": _Stub(),
        "Journal": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), module)
    return module


# ---------------------------------------------------------------------------
# Matching the item
# ---------------------------------------------------------------------------

def test_phrase_matches_the_obvious_spellings(m):
    for text in ["wood storage key", "Wood Storage Key", "WOOD STORAGE KEY",
                 "a wood-storage key", "WoodStorageKey", "Wood  Storage  Key"]:
        check("matches %r" % text, m["matches_wanted"](text), True)


def test_phrase_does_not_match_near_misses(m):
    """The \\b anchors matter: without them "key" matches inside "monkey"."""
    for text in ["wood storage box", "a storage key", "wood key",
                 "iron storage key", "keyring", ""]:
        check("rejects %r" % text, m["matches_wanted"](text), False)


def test_match_is_found_in_a_tooltip_not_just_the_name(m):
    """Keys are often called "a key" with the real description in the tooltip.
    Whenever a lookup by name fails, the tooltip is the next place to look."""
    blob = "a key | Wood Storage Key | Price: 2500 | Blessed"
    check("found in the tooltip blob", m["matches_wanted"](blob), True)


def test_concatenated_tooltip_still_matches(m):
    """Tooltip properties arrive with no separator between one value and the
    next label - "...KeyPrice: 2500". Lowercasing that gives "keyprice", so a
    regex ending in \\b fails unless the seam is split first."""
    raw = "Wood Storage KeyPrice: 2500Blessed"
    check("raw text does NOT match", m["matches_wanted"](raw), False)
    check("spaced() rescues it", m["matches_wanted"](m["spaced"](raw)), True)


def test_price_is_read_from_a_tooltip(m):
    check("plain", m["price_of"]("Price: 2500"), 2500)
    check("with commas", m["price_of"]("Price: 1,250,000"), 1250000)
    check("spaced out", m["price_of"]("Price 400"), 400)
    check("absent", m["price_of"]("Blessed | Weight: 1 Stone"), None)
    check("from a real blob",
          m["price_of"](m["spaced"]("Wood Storage KeyPrice: 2500")), 2500)


def test_strip_amount(m):
    check("count removed", m["strip_amount"]("12 keys"), "keys")
    check("left alone", m["strip_amount"]("a key"), "a key")


# ---------------------------------------------------------------------------
# SAFETY - choosing the context entry
# ---------------------------------------------------------------------------

def test_buy_is_taken_only_on_an_exact_label(m):
    check("exact Buy", m["find_buy_label"](["Buy", "Sell"]), "Buy")
    check("case does not matter", m["find_buy_label"](["buy"]), "buy")
    check("the REAL label is returned, not the search string",
          m["find_buy_label"](["BUY"]), "BUY")


def test_a_menu_without_buy_presses_nothing(m):
    """THE FAILURE THAT MATTERS. A vendor menu carries Sell, Set Price and
    Remove beside Buy. If Buy is not there, nothing may be pressed - a
    substring match landing on Sell cannot be undone."""
    for menu in (["Sell", "Set Price", "Remove Item"],
                 ["Open Bankbox", "Dismiss Vendor"],
                 ["Buyout Everything"],      # contains "buy", is NOT "Buy"
                 ["Rebuy"],                  # ditto
                 []):
        check("nothing pressed for %s" % menu, m["find_buy_label"](menu), None)


def test_context_never_blocks_even_an_exact_hit(m):
    """Belt and braces: if someone puts a dangerous word in BUY_LABELS, the
    blocklist still refuses it."""
    for label in ["Sell", "Bribe", "Open Bankbox", "Train Tailoring",
                  "Set Price", "Remove"]:
        check("%r is blocked" % label, m["context_is_blocked"](label), True)
    check("Buy is not blocked", m["context_is_blocked"]("Buy"), False)


def test_buy_labels_are_not_themselves_blocked(m):
    """A configured label that the blocklist would refuse is a dead config -
    the script could never buy anything. Catch it here rather than in game."""
    for label in m["BUY_LABELS"]:
        check("configured %r is usable" % label,
              m["context_is_blocked"](label), False)


def test_the_purchase_cap_is_sane(m):
    check("MAX_BUYS is at least 1", m["MAX_BUYS"] >= 1, True)
    check("MAX_BUYS is not unbounded", m["MAX_BUYS"] <= 10, True)


# ---------------------------------------------------------------------------
# Static guards
# ---------------------------------------------------------------------------

def test_no_unbounded_loops(m):
    """Every polling loop needs a Misc.Pause and a bound. A while True in a
    script that spends gold is the worst possible shape."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    unbounded = []
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            test = node.test
            if isinstance(test, ast.Constant) and test.value is True:
                unbounded.append(node.lineno)
    check("no `while True`", unbounded, [])


def test_context_reply_is_sent_only_from_buy(m):
    """ContextReply is the irreversible step. It must appear exactly once, and
    inside buy() - never anywhere that could reply to the VENDOR's own menu."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    holders = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "ContextReply":
                holders.append(fn.name)
    check("ContextReply used exactly once", len(holders), 1)
    check("and only inside buy()", set(holders), set(["buy"]))


def test_dry_run_short_circuits_before_buying(m):
    """DRY_RUN must be checked BEFORE buy() is called, not inside it."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source)

    main_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_fn = node
    check("main exists", main_fn is not None, True)
    if main_fn is None:
        return

    dry_lines = [n.lineno for n in ast.walk(main_fn)
                 if isinstance(n, ast.Name) and n.id == "DRY_RUN"]
    buy_lines = [n.lineno for n in ast.walk(main_fn)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", None) == "buy"]
    check("main checks DRY_RUN", len(dry_lines) > 0, True)
    check("main calls buy", len(buy_lines) > 0, True)
    if dry_lines and buy_lines:
        check("DRY_RUN is checked before buy() is called",
              min(dry_lines) < min(buy_lines), True)


def test_journal_is_cleared_before_it_is_read(m):
    """Journal.Search scans the whole buffer, so a stale line reads as a fresh
    result. buy() must Clear before it acts."""
    import ast
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    buy_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "buy":
            buy_fn = node
    check("buy() exists", buy_fn is not None, True)
    if buy_fn is None:
        return
    clears = [n.lineno for n in ast.walk(buy_fn)
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "Clear"]
    searches = [n.lineno for n in ast.walk(buy_fn)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "Search"]
    check("buy() clears the journal", len(clears) > 0, True)
    check("buy() reads the journal", len(searches) > 0, True)
    if clears and searches:
        check("cleared before read", min(clears) < min(searches), True)


def test_mobile_filter_sets_rangemax(m):
    """An unset RangeMax means everything the client knows about - roughly 18-25
    tiles - which makes a proximity check meaningless."""
    with open(SCRIPT, "r", encoding="utf-8") as fh:
        source = fh.read()
    check("Filter() is range-limited", "RangeMax" in source, True)


def main():
    module = load()
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-52s got=%-22s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:22], repr(want)[:30]))
        if not ok:
            failed += 1
    print("\n%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
