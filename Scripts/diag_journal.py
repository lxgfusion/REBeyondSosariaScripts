"""
Live journal tap.
=================

Run this, then say the thing that is not being detected - the Greyskull chant,
a vendor line, whatever. Every journal entry that arrives is printed with its
Text, Type, speaker Name, Serial and Colour, and whether it would match the
phrases in WATCH_FOR.

This answers the question that matters: does the message reach Razor's journal
at all, and if so, with what exact text and type?

Some shards route global/world chat through a system that never lands in the
journal. If nothing appears here when you speak, no amount of journal matching
will ever work and the trigger has to come from somewhere else.

Nothing is clicked, targeted or moved. Safe to run any time.

Output file: %TEMP%\\journal_dump.txt (path is printed when it finishes).
"""

import os
import time


# Phrases to test against, matched case-insensitively as substrings.
WATCH_FOR = [
    "by the power of greyskull",
]

# How long to listen, and how often to check.
LISTEN_SECONDS = 90
POLL_MS = 250

# Show every line, or only ones matching WATCH_FOR.
SHOW_EVERYTHING = True

DUMP_PATH = os.path.join(os.environ.get("TEMP", "."), "journal_dump.txt")

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480

_lines = []
_cursor = 0.0


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Jrnl] " + text, hue, False)
    _lines.append(text)


def rule(text):
    log("==== %s ====" % text, HUE_STEP)


def field(entry, name, default=""):
    try:
        value = getattr(entry, name)
    except Exception:
        return default
    return default if value is None else value


def prime():
    """Skip everything already in the buffer."""
    global _cursor
    try:
        for entry in Journal.GetJournalEntry(0.0) or []:
            stamp = field(entry, "Timestamp", 0.0) or 0.0
            if stamp > _cursor:
                _cursor = stamp
    except Exception as err:
        log("GetJournalEntry failed: %s" % err, HUE_BAD)


def fresh_entries():
    global _cursor
    try:
        entries = Journal.GetJournalEntry(_cursor)
    except Exception as err:
        log("GetJournalEntry failed: %s" % err, HUE_BAD)
        return []
    out = []
    for entry in entries or []:
        stamp = field(entry, "Timestamp", 0.0) or 0.0
        if stamp > _cursor:
            _cursor = stamp
        out.append(entry)
    return out


def matches(text):
    low = (text or "").lower()
    for phrase in WATCH_FOR:
        phrase = phrase.strip().lower()
        if phrase and phrase in low:
            return phrase
    return None


def main():
    rule("live journal tap")
    log("Watching for: %s" % ", ".join(WATCH_FOR), HUE_INFO)
    log("Listening for %d seconds. SAY IT NOW - in global chat, and also as "
        "normal speech so the two can be compared." % LISTEN_SECONDS, HUE_WARN)

    prime()

    seen = 0
    hits = 0
    types_seen = {}
    deadline = time.time() + LISTEN_SECONDS

    while time.time() < deadline:
        for entry in fresh_entries():
            text = field(entry, "Text", "")
            if not text:
                continue
            seen += 1

            etype = str(field(entry, "Type", "?"))
            types_seen[etype] = types_seen.get(etype, 0) + 1

            hit = matches(text)
            if hit:
                hits += 1

            if hit or SHOW_EVERYTHING:
                log("%-9s %-18s %s"
                    % (etype, str(field(entry, "Name", ""))[:18], text),
                    HUE_GOOD if hit else HUE_INFO)
                if hit:
                    log("      ^ MATCHES %r  serial=0x%X colour=%s"
                        % (hit, int(field(entry, "Serial", 0) or 0),
                           field(entry, "Color", "?")), HUE_GOOD)

        Misc.Pause(POLL_MS)

    rule("summary")
    log("%d journal lines seen, %d matched." % (seen, hits),
        HUE_GOOD if hits else HUE_WARN)

    if types_seen:
        log("Types observed: %s"
            % ", ".join("%s x%d" % (t, n) for t, n in sorted(types_seen.items())),
            HUE_INFO)

    if seen == 0:
        log("NOTHING reached the journal at all. Either nothing was said during "
            "the window, or this client is not journalling it.", HUE_BAD)
    elif hits == 0:
        log("Lines arrived but none matched. Compare the exact text above with "
            "WATCH_FOR - check spelling, and whether global chat arrives with a "
            "prefix or a different Type to normal speech.", HUE_WARN)
        log("If the chant is absent while normal speech is present, global chat "
            "is not journalled on this shard and needs a different trigger.",
            HUE_WARN)
    else:
        log("Matching works. Copy the matching phrase into GREYSKULL_PHRASES in "
            "mining_runner.py.", HUE_GOOD)

    try:
        with open(DUMP_PATH, "w") as fh:
            fh.write("\n".join(_lines))
        Misc.SendMessage("[Jrnl] Written to %s" % DUMP_PATH, HUE_GOOD, False)
    except Exception as err:
        Misc.SendMessage("[Jrnl] Could not write dump: %s" % err, HUE_BAD, False)


main()
