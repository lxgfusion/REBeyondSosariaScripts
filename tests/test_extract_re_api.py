"""Regression tests for tools/extract_re_api.py.

Every case here is a shape that actually appears in the Razor Enhanced source
and that an earlier version of the parser got wrong. The failures were all
silent — the class or member simply vanished from the generated reference — so
they are worth an assertion each.

    python tests/test_extract_re_api.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

import extract_re_api as api


SAMPLE = """
using System;

namespace RazorEnhanced
{
    /// <summary>
    /// The Sample class is a stand-in for Player/Items/etc.
    /// </summary>
    public class Sample
    {
        /// <summary>
        /// A static property whose getter brace sits on the next line.
        /// </summary>
        public static int Hits
        { get { return World.Player.Hits; } }

        public static Item Backpack
        {
            get { return null; }
        }

        public static bool Run(string direction)    // trailing comment
        {
            return Move(direction, true);
        }

        public static void ClearCorpseList() { Corpses.Clear(); }

        public static void Message(int serial, int hue, string message, bool wait = true)
        {
        }

        private static int Hidden { get { return 1; } }
        internal static void AlsoHidden() { }

        public class Filter
        {
            public bool Enabled = true;
            public List<int> Bodies = new();
            public List<byte> Notorieties = new();
            public double RangeMax = -1;
        }

        public enum GumpButtonType
        {
            Page = 0,
            Reply = 1
        }

        public string InstanceMethod(int x)
        {
            return "";
        }
    }
}
"""


def parse_sample():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "Sample.cs")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE)
    return api.parse(path)


def names(members):
    return [m["name"] for m in members]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_nested_class_is_not_popped_before_its_brace():
    """A class declaration whose `{` is on the next line used to be popped from
    the scope stack immediately, so every member landed nowhere."""
    classes = parse_sample()
    check("Sample" in classes, "outer class Sample was not captured")
    check("Sample.Filter" in classes,
          "nested class Filter was not captured as Sample.Filter; got %s" % list(classes))


def test_static_properties_are_captured():
    """Player exposes all its state as `public static int Hits { get {...} }`,
    with the brace usually on the following line."""
    props = names(parse_sample()["Sample"]["props"])
    check("Hits" in props, "static property Hits missing; got %s" % props)
    check("Backpack" in props, "static property Backpack missing; got %s" % props)


def test_field_initialiser_containing_parens_is_captured():
    """`public List<int> Bodies = new();` contains a `(`, which an earlier
    version treated as proof the line was a method."""
    props = names(parse_sample()["Sample.Filter"]["props"])
    for expected in ("Enabled", "Bodies", "Notorieties", "RangeMax"):
        check(expected in props, "filter field %s missing; got %s" % (expected, props))


def test_single_line_method_body_is_not_swallowed():
    """`public static void ClearCorpseList() { Corpses.Clear(); }` — a greedy
    `\\((.*)\\)` ran to the last `)` on the line and captured the body."""
    methods = parse_sample()["Sample"]["methods"]
    match = [m for m in methods if m["name"] == "ClearCorpseList"]
    check(match, "ClearCorpseList missing; got %s" % names(methods))
    check(match[0]["args"] == "",
          "ClearCorpseList should take no arguments, got %r" % match[0]["args"])


def test_optional_arguments_are_preserved():
    methods = parse_sample()["Sample"]["methods"]
    match = [m for m in methods if m["name"] == "Message"]
    check(match, "Message missing")
    check("bool wait = true" in match[0]["args"],
          "default argument lost from Message: %r" % match[0]["args"])


def test_instance_methods_are_captured():
    """Journal is bound into the python globals as an *instance*, and all of its
    methods are instance methods — restricting to `public static` lost the whole
    class."""
    check("InstanceMethod" in names(parse_sample()["Sample"]["methods"]),
          "instance methods are being dropped")


def test_enum_is_not_reported_as_a_property():
    props = names(parse_sample()["Sample"]["props"])
    check("GumpButtonType" not in props,
          "`public enum GumpButtonType` was misread as a property")


def test_non_public_members_are_excluded():
    data = parse_sample()["Sample"]
    check("Hidden" not in names(data["props"]), "private member leaked into the reference")
    check("AlsoHidden" not in names(data["methods"]), "internal member leaked into the reference")


def test_doc_comment_is_attached():
    classes = parse_sample()
    check("stand-in" in classes["Sample"]["doc"], "class summary not picked up")
    hits = [p for p in classes["Sample"]["props"] if p["name"] == "Hits"][0]
    check("next line" in hits["doc"], "member summary not picked up: %r" % hits["doc"])


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print("PASS %s" % test.__name__)
        except AssertionError as exc:
            failures += 1
            print("FAIL %s: %s" % (test.__name__, exc))
    print("\n%d passed, %d failed" % (len(tests) - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
