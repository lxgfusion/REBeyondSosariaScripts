# Session handoff — 2026-09-18

Everything touched between 2026-08-29 and 2026-09-18, 22 commits. Per-task
detail lives in the handoffs named below; this file is the map and the state.

`CLAUDE.md` carries the conventions and loads automatically. Read it first.

## State of every script

| Script | Version | Live | Status |
|---|---|---|---|
| `harvest_runner.py` | `2026-09-14.1` | 4 copies, all in step | **untested** — stall watchdog is new |
| `TameAndFill.py` | `2026-09-04.1` | in step | working; Leatherman merged in |
| `Leatherman.py` | `2026-09-04.1` | in step | **superseded** — retire once the merge is confirmed |
| `resource_order_runner.py` | `2026-09-13.5` | in step | partly tested; see below |
| `Sandmaker.py` | `2026-09-18.1` | in step | **DISCONNECTED THE CLIENT** — see its handoff |
| `diag_storage_gump.py` | — | n/a | working |
| `diag_taming_levels.py` | — | n/a | never run |

All nine test suites pass. Live and repo are byte-identical everywhere except
the deliberate serial scrubbing in published copies.

## The three things that still need doing

1. **Sandmaker disconnected the client.** The fix shipped untested.
   → `docs/sandmaker-handoff.md`
2. **`harvest_runner`'s stall watchdog is unproven.** It exists because
   Mr Gatherer sat on one tile for over an hour with every other guard armed;
   nobody has seen it fire.
3. **`resource_order_runner` short-page salvage is unproven.** It takes the
   first row of a page that parses short. Watch for it taking a wrong order.

---

## harvest_runner

Five copies, one code half. Live at `E:\uoclients\UOAlive_Package\razor\Scripts\`
(`main`, `Hanzo\`, `MrGatherer\`, `Mystic Gatherer\`). Only three are ever run:
Hanzo and MrGatherer mine, Mystic Gatherer lumberjacks.

### What changed

**`move` had never worked.** `_move_pending` was declared **above** the
`# HELPERS` seam. The config half is carried forward per copy and the code half
is replaced, so the splice delivered `take_move()` and never delivered the line
that creates the name it reads. It raised `NameError` in every live copy from
the day it shipped, and tested perfectly in the repo. **14 other pieces of
runtime state were in the same position** and only worked because they predated
the convention. All 15 are below the seam now, and a test asserts no private
name sits above it.

> This is the single most important lesson in the file. Anything the code half
> uses belongs in the code half.

**`stuck` added** — a stronger `move`. It writes the spot off rather than
merely leaving it, so the route does not walk back into it. Honoured mid-walk;
the worst case between saying it and acting is one pathfinding leg
(`PATH_LEG_TIMEOUT_S`, 5s), because `PathFinding.Go` blocks and nothing in
Python runs while it does.

**The no-progress watchdog** (`AREA_NO_PROGRESS_MS = 30000`) writes a spot off
after 30s with nothing to show. The clock spans **walking to** the spot as well
as working it, and is reset by a yield and nothing else — which is what the
three guards beside it do not do.

**The stall watchdog** (`STALL_STUCK_MS` 5 min, `STALL_RECALL_MS` 10 min) is
the backstop, and the reason it exists is worth keeping:

> Every other guard is a Python check **between** calls — the waypoint cap
> between `task()` calls, the spot cap between swings, the idle clock at the top
> of a sweep. A stall **inside** any of them is invisible to all of them.
> `interruptible_pause` is the exception: nearly every wait goes through it, so
> it keeps ticking while something else is stuck.

Progress is **moving or harvesting** — neither alone, because mining stands
still and produces while walking moves and produces nothing.

**"You can't mine there" is now told apart from "You have moved too far away".**
They shared an outcome, so the permanent one was only remembered when it landed
on the first swing.

### Unknown

What was actually blocking for an hour at 1185,460. Every recall path, wait and
loop checked is bounded, and there is no unbounded loop in the file. The stall
watchdog names the phase when it fires — **that line is the evidence to catch.**

---

## TameAndFill + Leatherman

**Leatherman was folded into TameAndFill.** Taming has first refusal every lap;
the harvest fallback is reached from all three idle branches (nothing tameable
in range, no deed to fill, no free follower slot).

**A species on both lists is KILLED, not tamed**, and preflight says so at
startup. Of the two ways to be wrong, taming something you meant to butcher
costs a deed slot; butchering something you meant to tame cannot be undone.

**Goats**: body `0xD1`. `"goat"` is a substring of `"mountain goat"` — the
`cat`/`hell cat` trap — so `HARVEST_NEVER_WORDS` is checked first and `0x58` is
kept out of `HARVEST_BODIES`. Excluded twice.

### The two Leatherman bugs, both worth remembering

**A corpse's serial has nothing to do with the mobile's.** The script filed the
creature's serial (and that serial with the high bit cleared) as the corpse to
look for, so it matched none, ever. Confirmed from a live recording: the cow was
`0x004556D6` and its corpse `0x43EC7D6D`. A corpse is now claimed when it was
**not in sight before the kill** AND lies within 4 tiles of where the creature
was last seen alive.

**`noshow=True` hides the target cursor from the client.** When the last cast
lands as the creature dies, the server refuses the target and the cursor stays
open — invisibly — and eats every subsequent click. That was "after I run the
script I can no longer target anything". All cursors are visible now, an
unconsumed one is cancelled, and `main()` releases it in a `finally`.

`Scripts/Leatherman.py` stays in place until the merge is confirmed in game.
**Do not edit both.**

---

## resource_order_runner

→ `docs/resource-order-handoff.md` and `docs/resource-order-book-gump.md`.

Four separate shard changes landed on this script in a fortnight.

**Fill rate limits.** `Fill from backpack` is ~1/second, Master Keys ~1/3s, and
*"clicking again sooner does nothing extra"* — a refused fill is **not an
error**. The real message is now known:

```
You must wait 0.4 more seconds before you can fill from backpack
```

`FILL_WAIT_MESSAGES` stores the part **without the number**; the full line
matches a 0.4-second refusal and nothing else. `FILL_EXTRA_PAUSE_MS` is a
**floor measured from now** — added to the ready time it did nothing at all,
because the first press of a lap is minutes after the last fill the script made.

**The order list's gump id moves.** `0xB2F21F1A` → `0xC5F60B43`. Razor derives
it from what the server sent, so changing the columns changes it. Found by
content now: `["Displayed:", "Contents:"]`, **both** required.

**The button ids are computed, not remembered.** `10 + 6*column + type`. Two
hardcoded ids had become something else and neither failed loudly: the sort
button 21 had become **remove the Completed column**, and the Completed filter
52 had become **withdraw row 12**.

**Four live captures pin this book's layout** (`ORDERS_CONFIRMED`), and they do
**not** match the admin's published order — theirs was their own copy.

**Every row has two buttons** — withdraw at `base + i`, details at
`base + 100000 + i`. Selecting by geometry counted both.

**A short page takes its first row** rather than nothing. Razor drops empty
strings from a gump's table without leaving a gap, so a 15-row page parses as
14. Safe because a dropped string shifts the rows *after* it, and the deed
itself is checked afterwards.

---

## Sandmaker

→ `docs/sandmaker-handoff.md`. **It disconnected the client.** Read that first.

---

## New reference material

| File | What |
|---|---|
| `docs/taming-order-levels.md` | all 112 tameable species ranked by ServUO min taming skill. **The level column is a guess** — the skill ladder is evenly spaced 6.0 apart with no natural bands. |
| `Scripts/diag_taming_levels.py` | reads the real `Level:` off deeds in the pack. **Never run.** |
| `tools/rank_tameables.py` | regenerates the ranking |
| `Scripts/diag_storage_gump.py` | dumps a stash window's drawn buttons, entries and strings |

---

## Patterns worth carrying forward

**Tests that raise instead of reporting hide every check after them.** This bit
four separate times this session — a `body.index(...)` on a string a mutation
had removed. Guard with `x in body and body.index(x) ...`.

**Mutation-test every new guard.** Several "passing" tests turned out to prove
nothing; three mutations survived a first pass in one round alone, and two of
those were real coverage gaps.

**A fallback must not outlive the thing it was a fallback for.** Two bugs of
exactly this shape in Sandmaker: the lone-candidate and name paths both kept
firing after the graphic was known.

**Diagnostics that fill in their own table.** The granite hue table, the fill
refusal message, the sand graphic and the order-list columns were all found
this way. When something is unknown, print what the game says and leave the
config empty — a guessed shard string is worse than none, because it matches
nothing and looks exactly like the message never appeared.

**Print the important part LAST.** The journal scrolls. `diag_storage_gump`
printed its buttons first and they were off the top of the screen by the time
the report finished.
