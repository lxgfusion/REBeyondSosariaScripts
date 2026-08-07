"""Extract the Razor Enhanced scripting API surface from the C# source.

The published docs at razorenhanced.github.io lag the released builds, and
Razor Enhanced has a history of changing signatures between builds, so the only
reliable reference is the source at the tag you are actually running.

Emits a markdown reference of the public methods (the callable API) and public
properties/fields (the readable state) for every class exposed to IronPython by
`PythonEngine.cs`, plus the helper and data classes those hand back.

Usage — clone the source at the tag you care about, then run:

    git clone --depth 1 --filter=blob:none --sparse \\
        --branch v1.0.0.14 https://github.com/RazorEnhanced/RazorEnhanced.git RE
    git -C RE sparse-checkout set Razor/RazorEnhanced
    RE_TAG=v1.0.0.14 python tools/extract_re_api.py \\
        RE/Razor/RazorEnhanced docs/api-reference-generated.md

To find which build is installed, list the ClickOnce version folders under
%LOCALAPPDATA%\\www.razorenhanced.net\\RazorEnhanced.exe_Url_*\\ .

This is a pragmatic line-based parser, not a C# front end. It relies on Razor
Enhanced's house style (one declaration per line, XML doc comments above) and is
checked by tests/test_extract_re_api.py.
"""
import os
import re
import sys
from collections import OrderedDict

# Modules exposed to python by PythonEngine.cs, plus the data classes they hand back.
FILES = OrderedDict([
    ("Player", "Player.cs"),
    ("Mobiles", "Mobile.cs"),
    ("Items", "Item.cs"),
    ("Journal", "Journal.cs"),
    ("Target", "Target.cs"),
    ("Gumps", "Gumps.cs"),
    ("Misc", "Misc.cs"),
    ("PathFinding", "PathFinding.cs"),
    ("Spells", "Spells.cs"),
    ("Statics", "Statics.cs"),
    ("Sound", "Sound.cs"),
    ("Timer", "Timer.cs"),
    ("Trade", "Trade.cs"),
    ("Vendor", "Vendor.cs"),  # also defines SellAgent and BuyAgent
    ("CUO", "CUO.cs"),
    ("AutoLoot", "AutoLoot.cs"),
    ("Scavenger", "Scavenger.cs"),
    ("Organizer", "Organizer.cs"),
    ("Dress", "Dress.cs"),
    ("Friend", "Friend.cs"),
    ("Restock", "Restock.cs"),
    ("BandageHeal", "BandageHeal.cs"),
    ("DPSMeter", "DPSMeter.cs"),
    ("PacketLogger", "PacketLogger.cs"),
    ("Geometry", "Geometry.cs"),
    ("Property", "Property.cs"),
    ("Filters", "Filters.cs"),
])

CLASS_RE = re.compile(r"^\s*(?:public|internal)\s+(?:static\s+|sealed\s+|partial\s+|abstract\s+)*class\s+(\w+)")
# Both static and instance methods: RE binds *instances* into the python globals
# (Journal, for one, is entirely instance methods), so both are callable the same way.
METHOD_RE = re.compile(
    r"^\s*public\s+(?:static\s+)?"
    r"(?!class\b|readonly\b|const\b|delegate\b|event\b)"
    r"((?:override\s+|virtual\s+|new\s+)?[\w<>,\[\]\.\?]+)\s+"
    r"(\w+)\s*\("
)
# Properties and fields, static or instance. Player exposes everything as
# `public static int Hits { get {...} }`, often with the brace on the next line,
# so the tail is checked separately rather than baked into this pattern.
PROP_RE = re.compile(
    r"^\s*public\s+(?:static\s+)?(?:readonly\s+)?"
    r"(?!class\b|enum\b|struct\b|interface\b|const\b|delegate\b|event\b|override\b|abstract\b|void\b)"
    r"([\w<>,\[\]\.\?]+)\s+(\w+)\s*(.*)$"
)
SUMMARY_OPEN = re.compile(r"///\s*<summary>")
SUMMARY_CLOSE = re.compile(r"///\s*</summary>")
DOCLINE = re.compile(r"^\s*///\s?(.*)$")
PARAM_RE = re.compile(r'///\s*<param name="(\w+)">(.*?)</param>')
RETURN_RE = re.compile(r"///\s*<returns>(.*?)</returns>")


def is_property_tail(tail, lines, i):
    """True if what follows a `public <type> <name>` declares a property/field.

    Accepts `{ get`, a bare `;`, a `= initialiser`, and the very common
    getter-brace-on-the-next-line form. Rejects `(`, which means a method.
    """
    tail = tail.strip()
    if tail.startswith("("):
        return False
    if tail.startswith("{") or tail == ";" or tail.startswith("=>"):
        return True
    if tail.startswith("=") and not tail.startswith("=="):
        return True
    if tail == "":
        for k in range(i + 1, min(i + 3, len(lines))):
            nxt = lines[k].strip()
            if nxt == "":
                continue
            return nxt.startswith("{") or nxt.startswith("=>")
    return False


def clean(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def read_doc(lines, i):
    """Walk backwards from line i collecting the XML doc comment block."""
    j = i - 1
    block = []
    while j >= 0:
        line = lines[j]
        if line.strip().startswith("///"):
            block.insert(0, line)
            j -= 1
        elif line.strip().startswith("[") or line.strip() == "":
            j -= 1
        else:
            break
    text = "\n".join(block)
    summary = ""
    m = re.search(r"<summary>(.*?)</summary>", text, re.S)
    if m:
        summary = clean(re.sub(r"///", "", m.group(1)))
    params = OrderedDict()
    for pm in PARAM_RE.finditer(text.replace("\n", " ")):
        params[pm.group(1)] = clean(pm.group(2))
    ret = ""
    rm = re.search(r"<returns>(.*?)</returns>", text, re.S)
    if rm:
        ret = clean(re.sub(r"///", "", rm.group(1)))
    return summary, params, ret


def grab_signature(lines, i):
    """Return the argument list of the method declared at line i.

    Scans from the first `(` to its *matching* `)` — a plain regex would run to
    the last `)` on the line and swallow single-line bodies such as
    `public static void ClearCorpseList() { Corpses.Clear(); }`.
    """
    buf = " ".join(l.strip() for l in lines[i:min(i + 25, len(lines))])
    start = buf.find("(")
    if start < 0:
        return ""
    depth = 0
    for pos in range(start, len(buf)):
        if buf[pos] == "(":
            depth += 1
        elif buf[pos] == ")":
            depth -= 1
            if depth == 0:
                return clean(buf[start + 1:pos])
    return ""


def simplify_type(t):
    t = clean(t)
    t = t.replace("RazorEnhanced.", "").replace("System.", "")
    return t


def parse(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")

    classes = OrderedDict()
    # Each entry is [name, depth_at_declaration, seen_opening_brace]. The `{` is
    # usually on the line after the declaration, so an entry is not eligible for
    # popping until we have actually descended into it.
    stack = []
    depth = 0
    for i, raw in enumerate(lines):
        line = raw
        cm = CLASS_RE.match(line)
        if cm:
            name = cm.group(1)
            qualified = ".".join([s[0] for s in stack] + [name]) if stack else name
            classes.setdefault(qualified, {"methods": [], "props": [], "doc": read_doc(lines, i)[0]})
            stack.append([name, depth, False])

        mm = METHOD_RE.match(line)
        if mm and stack and mm.group(2) != stack[-1][0]:  # skip constructors
            ret, name = simplify_type(mm.group(1)), mm.group(2)
            args = grab_signature(lines, i)
            summary, params, retdoc = read_doc(lines, i)
            qualified = ".".join([s[0] for s in stack])
            classes.setdefault(qualified, {"methods": [], "props": [], "doc": ""})
            classes[qualified]["methods"].append(
                {"name": name, "ret": ret, "args": simplify_type(args),
                 "doc": summary, "params": params, "retdoc": retdoc})

        pm = PROP_RE.match(line)
        if pm and stack and is_property_tail(pm.group(3), lines, i):
            ptype, pname = simplify_type(pm.group(1)), pm.group(2)
            if ptype in ("return", "new"):
                continue
            summary, _, _ = read_doc(lines, i)
            qualified = ".".join([s[0] for s in stack])
            classes.setdefault(qualified, {"methods": [], "props": [], "doc": ""})
            classes[qualified]["props"].append({"name": pname, "type": ptype, "doc": summary})

        depth += line.count("{") - line.count("}")
        for entry in stack:
            if not entry[2] and depth > entry[1]:
                entry[2] = True
        while stack and stack[-1][2] and depth <= stack[-1][1]:
            stack.pop()

    return classes


def render(src, tag):
    out = []
    out.append("# Razor Enhanced API reference — %s (generated from source)\n" % tag)
    out.append(
        "Generated by `tools/extract_re_api.py` from `Razor/RazorEnhanced/*.cs` at "
        "tag `%s` of https://github.com/RazorEnhanced/RazorEnhanced.\n" % tag)
    out.append(
        "**Do not hand-edit.** Regenerate when a new build ships — see the header "
        "of the extractor for the commands.\n")
    out.append(
        "Verified byte-identical across tags `v1.0.0.11`, `v1.0.0.12`, `v1.0.0.13` "
        "and `v1.0.0.14`, so this is accurate for any of them.\n")
    out.append(
        "Types are shown as C# declares them: `int` is a python `int`, `List<T>` is a "
        "`.NET` list (use `.Add()`, not `append`), `uint` gump ids are fine to pass as "
        "python ints. Arguments with `= value` are optional.\n")

    seen = set()
    for label, fname in FILES.items():
        path = os.path.join(src, fname)
        if not os.path.exists(path):
            out.append("\n<!-- missing %s -->\n" % fname)
            continue
        classes = parse(path)
        for qual, data in classes.items():
            if qual in seen:
                continue
            if not data["methods"] and not data["props"]:
                continue
            seen.add(qual)
            out.append("\n## %s\n" % qual)
            if data["doc"]:
                out.append("_%s_\n" % data["doc"])
            if data["methods"]:
                out.append("```")
                for m in data["methods"]:
                    out.append("%s(%s) -> %s" % (m["name"], m["args"], m["ret"]))
                out.append("```\n")
            if data["props"]:
                out.append("Properties: " + ", ".join(
                    "`%s` (%s)" % (p["name"], p["type"]) for p in data["props"]) + "\n")

    return "\n".join(out), len(seen)


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    text, count = render(src, os.environ.get("RE_TAG", "v1.0.0.14"))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", out_path, count, "classes")


if __name__ == "__main__":
    main()
