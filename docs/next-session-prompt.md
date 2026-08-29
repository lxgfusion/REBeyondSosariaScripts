# Prompt for the next session

Paste this in to pick up where we left off.

---

Continuing work on the Razor Enhanced scripts.

Read `docs/session-handoff-2026-08-21.md` first. `CLAUDE.md` has the
conventions and API gotchas and loads automatically.

**The important thing: two of the three crashes last session were ClassicUO
bugs, not script bugs.** The handoff has both stack traces and the source that
explains them. Read the ClassicUO source before writing Python — the answers
were in it both times, and one of them is a missing null check I want reported
upstream.

Current versions:

- `harvest_runner.py` — `2026-08-21.15`, five copies, code halves identical
- `resource_order_runner.py` — `2026-08-20.39`, committed and pushed
- `TameAndFill.py` — `2026-08-16.1`
- `COVFarm.py` — `1.6.0`

Almost nothing from last session is confirmed in game.

## What I want to do, roughly in order

1. **I will run each script and paste the journal back.** Help me read it.
   Lines worth watching for:
   - `harvest_runner v2026-08-21.15 [<tag>]` — if the tag or version is wrong,
     Razor is on a cached copy and none of the fixes are loaded
   - `Mining area: N spot(s) with mineable ground within 18 tiles` — if that
     says only 1 spot, the tile lists are not matching this shard's mines
   - `Stone Storage took the load` vs `still has ... check its menu entry`
   - `Lumber area done: … N barren` and any `silent` count
   - the order runner's stock report — granite, Mythril, Perfect Emerald and
     all six scale colours should now identify, and `cannot be identified`
     should be close to empty

2. **Report the `RequestMove` null check to ClassicUO.** It is two lines in
   `src/ClassicUO.Client/Network/Plugin.cs` and it is crashing the client on
   every recall-then-walk race. Help me write that issue.

3. Try a **stable ClassicUO build** on MrGatherer, since he crashes most and
   they are on a DEV_BUILD.

4. Commit the harvest runner work — it is the only script still uncommitted.

## Standing rules that keep paying off

- **Ship a diagnostic before a fix** when the cause is not certain. The Copper
  Ingots bug survived three confident-but-wrong diagnoses; a diagnostic found
  it in one run. The `0/429` granite bug went the same way.
- **Shard data comes from source or a live dump, never memory.** ServUO for
  bank sizes and tile lists; the Item Inspector for hues. Two of this shard's
  resources (Magewood, Darkwood, Mythril) are in no ServUO table at all.
- **Unidentified must mean invisible, never mistaken for something else.**
  Skipping an order costs a lap; pouring the wrong metal into a deed cannot be
  undone.

## Editing the five harvest_runner copies

Read the "HOW TO EDIT THE FIVE COPIES" section of the handoff before touching
them. Short version: **no regex** — splice whole regions at the `# HELPERS`
seam and carry the config forward; **verify values, not text**; and run
`tools/check_undefined_names.py` on every copy afterwards, because a syntax
check is not evidence.
