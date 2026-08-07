"""Tests for Scripts/diag_chest_contents.py.

The logic worth testing is wood_from_text: it turns a stack's tooltip into the
BOOK's board name, and everything pasted into BOARD_HUES comes out of it. A
wrong answer here puts the wrong wood against a hue, which is the one mistake
that cannot be undone in the runner.

    python tests/test_chest_contents.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "Scripts", "diag_chest_contents.py")

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
        "__name__": "diag_chest_contents",
        "Misc": _Stub(), "Player": _Stub(), "Items": _Stub(),
        "Gumps": _Stub(), "Mobiles": _Stub(), "Target": _Stub(),
        "Journal": _Stub(),
    }
    exec(compile(source, SCRIPT, "exec"), module)
    return module


def test_each_wood_is_recognised(m):
    for text, want in [
            ("120 boards | ash", "Ash Boards"),
            ("120 boards | oak", "Oak Boards"),
            ("120 boards | yew", "Yew Boards"),
            ("120 boards | heartwood", "Heartwood Boards"),
            ("120 boards | bloodwood", "Bloodwood Boards"),
            ("120 boards | frostwood", "Frostwood Boards"),
            ("120 boards | darkwood", "Darkwood Boards"),
            ("120 boards | magewood", "Magewood Boards"),
            ("120 boards | plain", "Regular Boards"),
            ("120 boards | regular", "Regular Boards")]:
        check("%r" % text.split("| ")[-1], m["wood_from_text"](text), want)


def test_longest_name_wins(m):
    """"bloodwood" and "heartwood" both end in "wood". Sorting shortest-first
    would let a bare "wood" - or "oak" inside "oaken" - claim them. Same trap as
    "cat" claiming "hell cat" in the taming tables."""
    check("bloodwood not claimed by wood",
          m["wood_from_text"]("bloodwood"), "Bloodwood Boards")
    check("heartwood not claimed by wood",
          m["wood_from_text"]("heartwood"), "Heartwood Boards")
    check("frostwood not claimed by wood",
          m["wood_from_text"]("frostwood"), "Frostwood Boards")
    check("darkwood not claimed by wood",
          m["wood_from_text"]("darkwood"), "Darkwood Boards")
    check("magewood not claimed by wood",
          m["wood_from_text"]("magewood"), "Magewood Boards")


def test_word_boundaries_hold(m):
    """Without \\b, "ash" matches inside "ashes" and "oak" inside "cloak"."""
    check("ashes is not ash", m["wood_from_text"]("a pile of ashes"), None)
    check("cloak is not oak", m["wood_from_text"]("a leather cloak"), None)
    check("nothing at all", m["wood_from_text"]("120 boards"), None)
    check("empty", m["wood_from_text"](""), None)


def test_concatenated_tooltip_is_split_first(m):
    """Tooltip properties arrive with no separator - "...BoardsAshWeight: 12".
    Without the seam fix that lowercases to "boardsash" and nothing matches."""
    raw = "120 BoardsAshWeight: 12 Stones"
    check("raw does not match", re.search(r"\bash\b", raw.lower()) is not None,
          False)
    check("wood_from_text splits it", m["wood_from_text"](raw), "Ash Boards")


def test_plain_maps_to_the_books_name(m):
    """The storage window says "Plain"; the book says "Regular Boards". The
    BOOK's name is what BOARD_HUES needs, or the entry matches no order."""
    check("plain -> Regular Boards",
          m["wood_from_text"]("plain"), "Regular Boards")
    check("every mapped name ends in Boards",
          all(v.endswith("Boards") for v in m["WOOD_NAMES"].values()), True)


def test_the_storage_key_graphic_is_not_a_board(m):
    """0x1BD9 is the Wood Storage key. It must be reported as a lookalike, not
    counted as boards - resource_order_runner.py excludes it for that reason."""
    check("0x1BD7 is a board", 0x1BD7 in m["BOARD_IDS"], True)
    check("0x1BD9 is not", 0x1BD9 in m["BOARD_IDS"], False)
    check("0x1BD9 is flagged as a lookalike",
          0x1BD9 in m["BOARD_LOOKALIKE_IDS"], True)


def test_all_nine_woods_are_covered(m):
    """The storage window lists nine. Missing one means its hue comes back
    unnamed and has to be matched by eye."""
    wanted = ["Regular Boards", "Ash Boards", "Bloodwood Boards",
              "Frostwood Boards", "Heartwood Boards", "Oak Boards",
              "Yew Boards", "Darkwood Boards", "Magewood Boards"]
    have = set(m["WOOD_NAMES"].values())
    for name in wanted:
        check("%s covered" % name, name in have, True)


def main():
    module = load()
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test(module)

    failed = 0
    for label, got, want, ok in _checks:
        print("%-4s %-46s got=%-24s want=%s"
              % ("ok" if ok else "FAIL", label, repr(got)[:24], repr(want)[:28]))
        if not ok:
            failed += 1
    print("\n%d checks, %d failed" % (len(_checks), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
