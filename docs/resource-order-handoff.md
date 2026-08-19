# Resource order handoff

## Granite — DONE in `.33`, and it was the 0/429 bug

All nine granite hues are confirmed from live Item Inspector dumps
(2026-08-18). `GRANITE_IDS = [0x1779]`.

| Hue | Book name | Stack tooltip says |
|---|---|---|
| `0x0000` | `High Quality Granite` | *(no third line at all)* |
| `0x0973` | `Dull Copper Granite` | Dull Copper |
| `0x0966` | `Shadow Granite` | **Shadow Iron** |
| `0x096D` | `Copper Granite` | Copper |
| `0x0972` | `Bronze Granite` | Bronze |
| `0x08A5` | `Gold Granite` | **Golden** |
| `0x0979` | `Agapite Granite` | Agapite |
| `0x089F` | `Verite Granite` | Verite |
| `0x08AB` | `Valorite Granite` | Valorite |

Three are worded differently by the stack and the book, exactly like the ingots
(`golden` on the stack, `Gold` in the book). The left-hand name must be the
BOOK's or the entry matches no order.

### Why orders sat at 0/429

**Every granite stack is named `<amount> high quality granite`**, whatever metal
it is — the metal is only on the third tooltip line. And there is a resource
called *High Quality Granite*. So the `by: "name"` fallback did not fail
harmlessly the way it does for boards: it claimed **every** granite stack of
every metal as High Quality Granite. A Valorite stack was then offered to fill a
High Quality order, the server refused it, and the deed never moved.

The code comment had asserted the opposite — *"an entry with no hue keeps its
`by: name` match, which is harmless"*. True of boards and scales, false here.

Two guards came out of it:

- A family member with no hue listed is marked `UNMATCHABLE` rather than left
  matching by name. **Unidentified must mean invisible, never mistaken for
  something else** — invisible costs a skipped order, mistaken pours the wrong
  metal into a deed and cannot be undone. The disarming is surgical: only the
  entry whose name the generic stack name would claim. A blunter "anything
  ending in Scales" rule broke `Delicate Scales`, which is a genuinely
  differently-named item (`0x573A`).
- Hue uniqueness is validated **per family, not globally**. Matching is graphic
  AND hue, so `0x0000` is legitimately both `Regular Boards` (`0x1BD7`) and
  `High Quality Granite` (`0x1779`) — "no hue" is how every family spells its
  plain member. The global check called that a clash and **refused to start**.

### Reading a hue table off the game

`report_unknown_families` now prints each unknown hue **with the material from
the stack's tooltip**, so the table fills itself:

```
    hue 0x0979  874 granite(s) in 1 stack(s)   tooltip says: Agapite
      "Agapite": 0x0979,
```

Change the left-hand name to the book's wording before pasting.

`report_unidentified_stacks` is the wider net: every stack in the chests that
`resource_of()` cannot name at all, grouped by graphic and hue. That is the one
that catches a family whose GRAPHIC is wrong, which no per-family report can.

### Still open

`SCALE_HUES` — five of six still unknown (`Yellow`, `Blue`, `Red`, `White`,
`Black`). Only `Green Scales` (`0x0851`) is confirmed. The same report prints
them; note scale stacks may carry no material line, in which case they still
need matching by eye.

---

State as of 2026-07-30. `CLAUDE.md` carries the conventions and the API gotchas
and loads automatically; this file is only the state of *this* task.

## Wood boards — DONE in `.26`

`BOARD_HUES` is filled from a live chest dump (`diag_chest_contents.py`,
2026-08-03). All nine woods identify; 320,420 boards came into stock at once:

| Hue | Book name | On hand |
|---|---|---:|
| `0x0000` | `Regular Boards` | 91,715 |
| `0x07DA` | `Oak Boards` | 189,690 |
| `0x04A7` | `Ash Boards` | 20,060 |
| `0x04A8` | `Yew Boards` | 8,400 |
| `0x04A9` | `Heartwood Boards` | 5,460 |
| `0x04AA` | `Bloodwood Boards` | 3,085 |
| `0x047F` | `Frostwood Boards` | 1,840 |
| `0x0AAC` | `Magewood Boards` | 90 |
| `0x078C` | `Darkwood Boards` | 80 |

Eight name their wood on the stack's **third tooltip line**, exactly as ingots
name their metal (`20060 board / Weight: 20060 stones / ash`). `0x0000` carries
no wood line at all — which is how the default wood renders, the same way plain
iron is the one ingot with no third line. Nothing else in the chest uses
`0x1BD7`, so there was no other candidate.

**Magewood and Darkwood are this shard's own woods**, in no ServUO table, and
they arrive capitalised where the other six are lower case. The live dump is the
only source for them — do not "correct" these from ServUO.

Pinned by `LIVE_BOARD_HUES` in the test suite, with regressions for logs
(`0x1BDD` shares every wood hue and the book has **no** log orders) and for
ingots still identifying after the board entries are rewritten at import.

### The earlier state, for context

Boards go **loose in one of the two `CHESTS`**, same as the ingots — the user
confirmed that on 2026-07-31. So there is no wood-storage gump to read and
nothing to withdraw; the census finds them with no extra plumbing. The only
thing that has to work is telling one wood from another.

All nine woods were already in `RESOURCES`, but as
`{"id": 0, "hue": -1, "by": "name"}` — which matches nothing, because a board
stack is called `"<amount> boards"` and says nothing about the wood. Exactly the
ingot trap.

`.25` adds:

- `BOARD_IDS = [0x1BD7]`. **`0x1BD9` is deliberately excluded** — that is the
  Wood Storage key's own graphic (`harvest_runner`'s `WOOD_STORAGE_ID`), and
  including it would count the key itself as a stack of boards.
- `BOARD_HUES`, **empty**, with all nine names commented in. A hue pasted here
  converts that entry to graphic matching; anything unlisted stays
  unidentifiable rather than being guessed. Pouring Oak into a Magewood order
  cannot be undone.
- `report_unknown_boards()` in the stock report: it names every board hue in the
  chest it cannot identify and prints the exact line to paste. **This is how the
  table gets filled** — no separate diagnostic, no ServUO lookup. Darkwood and
  Magewood are custom to this shard and are not in ServUO at all, so there is no
  other source for them.
- `validate_board_hues()` at startup: refuses a name that is not in `RESOURCES`
  and refuses two woods sharing one hue.

**Next step:** put a stack of each wood in the chest, run once, paste the printed
lines into `BOARD_HUES`. Round trip verified offline — pasting a hue identifies
that wood and only that wood.

Note the vocabularies differ, as they do for ingots (`golden` on the stack,
`Gold` in the book): the storage window says **Plain**, the book says
**`Regular Boards`**. The left-hand name in `BOARD_HUES` must be the book's.

## Where things stand

`Scripts/resource_order_runner.py` is at **`2026-07-31.25`**, deployed and
byte-identical to the live copy. It is `.15r` plus the Copper Ingots fix
(`rewind_to_first_page`) and nothing else — none of `.16`–`.23` was pulled in,
and `MAX_ORDERS_PER_RUN` 15 / `MAX_CYCLES` 20 / `KEEP_PER_TYPE` 0 are untouched.

**Awaiting confirmation in game as of 2026-07-30.** If it works, Copper should
appear in the journal as a normal `taking Copper Ingots x<N>` line.

It runs the whole circuit unattended:

```
Start Fill → fill orders → RO (hand in) → Deposit items → Deposit PS → Start Fill
```

repeating until a lap fills nothing. Before each lap it bins Portable Forges
into the trash bag; after each hand-in it empties the Runecrafting Storage and
both deposit stops.

**The user reverted to `.15` deliberately** after a run of changes they felt had
made things worse. `.15r` is that snapshot plus one carried-forward instruction:
`KEEP_PER_TYPE = 0`, because they said explicitly that the reserve no longer
applies to anything.

## THE COPPER INGOTS BUG — found and fixed in `.24`

**Cause: submitting a new Name filter does not reset the page position.**

Confirmed in game 2026-07-30 by `diag_copper_pages.py` phase 3. The list was on
page 4 of the decoy's result, `Copper Ingots` was submitted, and the list came
back on **page 4 of that result** — the same page 4 phase 1 had already read,
byte for byte (fingerprint `02161` both times).

`work_one_order` only calls `open_book()` when the gump is **closed**, so every
resource after the first begins its scan wherever the last one stopped, and a
scan that finds nothing ends on the **last** page. Copper has all 26 of its
orders on **pages 1–2 of 10**, so unless the previous resource happened to stop
on page 1 or 2 it was never seen. Every other resource has orders spread through
its result, which is why Copper alone was affected.

**Fix (`.24`):** `rewind_to_first_page()` presses Previous Page (button 4, which
is absent on page 1) until the counter reads 1, bounded by `MAX_REWIND_PRESSES`,
falling back to reopening the book and re-applying the filter. Called from
`find_first_order` immediately after the filter submit, before the page loop.

Cost is near zero in the common case: the scan returns as soon as it finds an
order, so the list is usually already on page 1.

Guarded by `test_the_scan_rewinds_to_page_one_after_filtering`, which asserts
statically that the rewind exists, runs **before** the page loop, presses
`ORDERS_PREV_BUTTON`, and is bounded. Verified to fail when the call is removed.

### How three earlier diagnoses were wrong

Worth keeping, because each looked confirmed at the time:

1. **"The page cap is too low."** It was not: Copper collides, so the diluted
   branch already allowed 20 pages against a 9-page result.
2. **"The budget is too low."** It was not: `diag_copper_stock.py` returned
   `THE CENSUS SEES IT: 31487 Copper`, against orders of 1460–2402.
3. **"Copper never gets a turn."** It does: simulating the real rotation put
   Copper (#57 of 79) in reach by lap 4 at worst, every lap at best.

The lesson: each explained "Copper never fills", none was tested against the
live gump until a diagnostic did it, and the real cause was in how the runner
*arrives* at the filter — not in anything the scan itself does.

### What is ruled out: the page cap

`colliding_names("Copper Ingots")` returns `["Dull Copper Ingots"]`, so
[`resource_order_runner.py:1421`](../Scripts/resource_order_runner.py) already
takes the diluted branch and allows **20** pages, not 4. Copper's filtered
result is 31 + 101 = **132 rows ≈ 9 pages**. The cap is not the binding
constraint, and raising `MAX_PAGES_WHEN_DILUTED` changes nothing for Copper.

The page counter is trustworthy here: a captured Valorite page showed
`Displayed: 230` against `(1/16)`, so the footer reflects the *filtered*
result and the `current >= total` break works. (That capture lived in
`tests/test_resource_orders.py`, removed on 2026-08-06 with the `diag_*`
scripts it covered — it is still in git history.)

### What the collision table actually says

Order counts from the `RESOURCES` comments (harvested 2026-07-28):

| Searching | own | also returns | rows | pages | within cap 20? |
|---|---:|---|---:|---:|---|
| `Amber` | 167 | `Brilliant Amber` 148 | 315 | **21** | **no** |
| `Bone` | 153 | `Grizzled Bones` 126 | 279 | 19 | just |
| `Copper Granite` | 148 | `Dull Copper Granite` 123 | 271 | 19 | just |
| `Ruby` | 145 | `Fire Ruby` 1 | 146 | 10 | yes |
| `Citrine` | 141 | `Ecru Citrine` 1 | 142 | 10 | yes |
| `Diamond` | 138 | `Blue Diamond` 1 | 139 | 10 | yes |
| `Sapphire` | 122 | `Star Sapphire` 15, `Dark Sapphire` 1 | 138 | 10 | yes |
| `Copper Ingots` | **31** | `Dull Copper Ingots` **101** | 132 | 9 | yes |

Two things fall out. The cap binds for **Amber**, not Copper — so raising it is
still worth doing, just not as the Copper fix. And Copper is the only collision
where the intruder *outnumbers* the target, which is why it alone fails: every
other target is dense enough to put its own rows on page 1.

### The diagnostic, and what it returned

`diag_copper_pages.py` (deployed 2026-07-30) walks the filtered result
the way the runner does and names the cause. Read-only: it presses book button
1, list button 12 (filter) and 5 (Next) and nothing else, enforced by a
`PRESSABLE` allowlist — button 2 on that gump is **Purge** and 3 is **Fill from
backpack**. The parsers are copied from the runner and the `WaitForGump` +
600 ms wait is deliberately unchanged, so it sees what the runner sees. Full
output goes to `%TEMP%\ro_copper_pages.txt`.

**Run of 2026-07-30 19:09 — verdict C, the paging is fine.** 10 pages walked
cleanly to the last, no stale reads, rows and buttons agreed on every page:

```
displayed 137 over 10 page(s)
page 1/10  15 rows, 15 buttons   14 Copper Ingots orders
page 2/10  15 rows, 15 buttons   12 Copper Ingots orders, 2 Dull Copper
page 3..10                        Dull Copper Ingots only
26 'Copper Ingots' order(s) found, amounts 1460 - 2402
```

The Copper orders are on **pages 1 and 2**. The runner allows 20 pages, so it
sees all 26 of them. The dilution theory was wrong twice over: the collision
does not even push Copper off page 1.

### Eliminated

- **Scan depth / the page cap.** Orders are on pages 1–2 of 10.
- **Paging bugs (`.19`, `.21`).** Zero stale reads, zero row/button mismatches
  in a clean 10-page walk. Worth applying on their merits; not this bug.
- **Name matching.** The diag uses the runner's exact regex and matched 26.
- **Identification by hue.** Every ingot has its own hue in `RESOURCES`, no
  wildcard on `0x1BF2`, so `resource_of` cannot confuse Copper with Dull Copper.
- **`MAX_ORDER_SIZE`.** 2402 is well under 25,000.
- **Lap starvation.** Simulating `fill_orders`' real rotation over the 79-entry
  table at `MAX_ORDERS_PER_RUN = 15`: Copper (#57) gets a turn by lap 4 in the
  worst scenario and on **every lap** if only the nine ingot metals have stock.

### Ruled out: the census (2026-07-30)

`diag_copper_stock.py` returned **`THE CENSUS SEES IT: 31487 Copper`**. The
stack is at the top level of the chest, hue `0x096D`, counted correctly. Budget
is ~31,487 against orders of 1460–2402. So the budget is not it either, and the
elimination chain below has a hole in it.

### What is left: how the runner ARRIVES at the filter

`work_one_order` only calls `open_book()` when the gump is **closed**
([`:2297`](../Scripts/resource_order_runner.py)). Between resources the runner
therefore re-submits the Name filter on a list still sitting on page N of the
*previous* resource's result — it never returns to page 1.

`diag_copper_pages.py` phase 1 opened the book fresh and started on page 1,
which is why it found the orders and the runner does not. **If the page position
survives a new filter, the runner starts Copper's scan mid-list — and all 26
Copper orders are on pages 1–2 of 10.** That fits every observation, including
why Copper alone fails: it is the most page-position-sensitive resource in the
book.

`diag_copper_pages.py` **v2026-07-30.2** adds **phase 3** to test exactly this:
filter for a decoy (`Dull Copper Ingots`), page in three, then re-filter for
`Copper Ingots` without reopening, and report which page the list lands on.

- lands past page 1 → **verdict D**, confirmed; fix is to reset to page 1 after
  applying a filter, before scanning.
- lands on page 1 → verdict C, and nothing left in the gump explains it; capture
  the runner's journal around Copper's turn.

Both diags now print a `SCRIPT_VERSION` banner on their first log line — check
it, or Razor may be running a cached copy.

### The four census failure modes (kept for reference)

`amount > budget` is the only remaining rejection, so the budget for Copper
Ingots is under 1,460 — the smallest order in the book. But the user showed an
item tooltip on 2026-07-30 reading **`31487 Ingots / Weight: 3149 Stones /
Copper`**, one stack, sitting in the chest area. 31,487 against orders of
1460–2402.

So **`census()` is not counting the copper that is there.** That is the bug.

`census()` → `all_resource_stacks()` reads `chest.Contains` for each chest in
`CHESTS`, **one level deep**, and identifies a stack by ItemID + Hue. Four ways
to miss a stack, and they need different fixes:

1. **In a sub-bag.** A bag inside the chest is one entry in `Contains`; nothing
   walks into it. Everything in it is invisible.
2. **Wrong hue.** If this shard's copper is not `0x096D`, `resource_of` returns
   `None` and the stack is not copper as far as the runner is concerned.
3. **Outside the chests.** Locked down on the ground, or in a container not in
   `CHESTS`. House storage is locked down on the ground with `Container: None`,
   so a chest search never finds it.
4. **Stale snapshot.** `Contains` is taken when the container is opened.

`diag_copper_stock.py` (deployed 2026-07-30) tells them apart. It walks
both chests to depth 3, does a world search for every `0x1BF2` stack in range,
and prints one table:

```
  metal          runner       chests(all)  world
  Copper         0            31487        31487   <-- MISSED
```

The `runner` column is what `census()` counts (depth 1 only); the gap is the
bug. It then names the cause — `IN A SUB-BAG`, `WRONG HUE`, `OUTSIDE THE
CHESTS`, or `THE CENSUS SEES IT` — with the fix for each. Read-only apart from
opening containers: no gump button, no move, no target. Output also goes to
`%TEMP%\ro_copper_stock.txt`.

All four verdicts are covered by an offline simulation of the four chest
layouts; that harness is not in `tests/` because it drives a diag, not the
runner.

## Version history, and what is in the snapshots

`.snapshots/` holds `.15`, `.15r` (current) and `.23`, plus `.23`'s test file.
Anything below can be cherry-picked from the `.23` snapshot as a diff.

| Ver | Added | In `.15r`? |
|---|---|---|
| `.11` | The circuit: Start Fill / RO / Deposit items / Deposit PS | yes |
| `.12` | Portable Forge → trash bag at lap start | yes |
| `.13` | Lap rotation; census drops merged-away "ghost" stacks | yes |
| `.14` | Deeper scan on name collision; the name harvester | yes |
| `.15` | `RESOURCES` rebuilt from the 540-page book harvest | yes |
| `.16` | `UnboundLocalError` fix + the static guard test | n/a¹ |
| `.17` | `KEEP_PER_TYPE = 0`; lap order built from stocked resources only | partly² |
| `.18` | Final Deposit-items stop when the run ends | **no** |
| `.19` | Stale-gump fix — wait for content to change, not the gump id | **no** |
| `.20` | Depth-first per resource (later reverted) | no |
| `.21` | Atomic page read — rows and buttons from one snapshot | **no** |
| `.22` | Biggest order on the page; `MAX_CYCLES` 20 → 200 | **no** |
| `.23` | Round-robin restored; scan every page of a filtered result | **no** |

¹ The crash was introduced in `.14`'s edit and `.15` happens not to carry it —
verified by the static scan. The guard test itself is still in the suite.
² `KEEP_PER_TYPE = 0` carried forward; the stocked-only lap order was not.

### The three worth considering re-applying

- **`.19` stale-gump fix.** `Gumps.WaitForGump` returns `True` for a gump that
  is *already open*, and the server answers a button by replacing the list with
  a new gump under the **same id**. `.15r` waits on the id and a 600 ms pause,
  so under lag it can read the **previous** page. When that happened after a
  filter, rows and buttons disagreed and the page was skipped.
- **`.21` atomic page read.** Rows come from `GetLineList`, buttons from
  `GetGumpRawLayout` — two calls. A page arriving between them gives rows from
  one page and buttons from another, and since both carry 15 rows the count
  check *passes* and the wrong order gets pressed.
- **`.23` full page scan.** Scans to the last page the gump reports instead of a
  fixed cap. Worth having regardless — the cap genuinely binds for Amber — but
  it is *not* the Copper fix, whatever the earlier note here claimed.

## Config the user tunes — do not overwrite these

| Setting | Live value | Note |
|---|---|---|
| `MAX_ORDERS_PER_RUN` | 15 | they set 25 at one point, then reverted |
| `MAX_CYCLES` | 20 | `.22` had 200 |
| `KEEP_PER_TYPE` | 0 | they asked for this explicitly |

**Always diff live against the repo before deploying.** A blind repo → live copy
has already reset their `MAX_ORDERS_PER_RUN` once.

## Ground truth already established

- **Resource names come from the book**, harvested by `diag_order_names.py`
  across all 540 pages (8,085 deeds, 79 distinct names). Never from ServUO,
  never from the item's own tooltip. The book calls Shadow Iron
  **`Shadow Ingots`** and plain leather **`Regular Leather`**, and misspells
  **`Star Saphhire`** (144 orders, against 15 for the correct spelling).
- **Deeds have two tooltip shapes** sharing no label — see
  `docs/resource-order-book-gump.md`.
- The full gump map, the row-button numbering, the ore/leather hue tables and
  the Razor empty-string bug are all in `docs/resource-order-book-gump.md`.

## Verifying and deploying

```bash
cd "G:/programming projects/Razor Enhanced Scripts"
for t in tests/test_*.py; do printf "%-38s " "$t"; python "$t" 2>&1 | tail -1; done
```

All six suites must be green. Then, after diffing:

```bash
cp Scripts/resource_order_runner.py "/e/uoclients/RazorEnhanced/Scripts/"
```

Snapshot before overwriting:

```bash
cp Scripts/resource_order_runner.py ".snapshots/resource_order_runner_<version>.py"
```

Bump `SCRIPT_VERSION` on every change that ships — it is the first line in the
journal and the only way to tell which copy Razor actually loaded. Razor caches
the script, so **Reload** in the Scripting tab is required even after the file
changes on disk.

## Off limits

`harvest_runner.py` and its four diverging copies are the user's own work in
progress. Do not sync or edit them unasked — see `CLAUDE.md`.
