# Sandmaker handoff

State as of **2026-09-18**. `CLAUDE.md` carries the conventions and the API
gotchas and loads automatically; this file is only the state of *this* task.

## The job

Convert Plain granite to sand in batches of 50, from one spot:

```
50 times:  withdraw ONE Plain granite from the Stone Storage
           drop it in the converter            (conversion is instant)
say "[grab"                                    (the shard collects the sand)
deposit the sand in the Reagent Keys           (its context menu, not a drag)
repeat until stopped, or the Plain granite runs out
```

**The character stands still.** The user found one spot that can both reach
the converter and collect with `[grab`; `STAND_STILL = True` makes anything
out of reach a refusal with the distance in it, rather than a walk that leaves
that spot. `STAND_STILL = False` restores the old walking behaviour.

**The stones go in one at a time** — the converter does not take a stack.

### Where things actually live — both optional

| | |
|---|---|
| `[grab` fills | **a loot bag** `0x407D25FC`, ItemID `0x0E76`, hue `0x04F2`, inside the pack |
| the keys live in | **a pouch** `0x4133A297`, ItemID `0x0E79`, inside the pack |

**The grab does not fill the backpack.** The first version counted the pack's
top level and saw nothing, every time. Counting now re-opens the loot bag and
reads that, plus the pack's top level so a stack dragged out by hand is still
found — and with no separate bag the pack is counted **once**, not twice.

**The keys are not loose in the pack either**, so the pouch is opened before
they are looked for: a container that has never been opened has no contents to
search, and `FindBySerial` on something inside one can come back empty for the
same reason.

Neither layout is compulsory. `SAND_IN_SEPARATE_BAG` and `KEY_IN_SEPARATE_BAG`
default to **True** for this character; set either False and that bag is
ignored entirely — nothing is opened, nothing is demanded at startup, and the
pack is searched instead.

**The sand is dragged into the pack before the deposit**
(`SAND_TO_PACK_BEFORE_STORE`, on by default, ignored when there is no separate
bag). Nothing has established that `Refill from stock` reaches into a
sub-container, and if it does not the failure is silent: the sand stays in the
bag, the deposit looks like it did nothing, and the run stops. One drag per
stack — and sand stacks, so it is normally one drag however big the batch.

### The Reagent Keys — `Container: No`

```
Name "Reagent Keys", 0x404D69CE, ItemID 0x18DE, hue 0x0021, Blessed, 1 stone
Container: NO      Movable: Yes      in the backpack
```

That one line decided the design: **nothing can be dragged into it.** The sand
goes in through the key's **context menu** — `Refill from stock`, the same
entry `harvest_runner.py` has emptied packs into for months. Exact label match
first and always honoured, guarded substring after, `CONTEXT_NEVER` refusing
anything that spends gold, and the real label sent back to `ContextReply`.

**That entry deposits every reagent in the pack, not only the sand.** Said in
the config, because it is the one surprise in the flow.

### A refused drag is not the end of the run

**2026-09-30, first real run: 186 stones converted and stored across 4
batches, then it stopped** on

```
[Sand] the granite did not move - it is 2394 tiles away and still in your pack.
```

Two faults in one line. The **2394** was the player's map coordinate measured
against an item inside a bag, which has no position of its own — a number
nobody can act on. And a *single* refused drag ended a run that had just done
186 of them; nothing was wrong with the setup.

| | |
|---|---|
| `MOVE_RETRIES = 3` | a drag is retried before it counts as failed, with `MOVE_RETRY_PAUSE_MS` between |
| `has_moved()` | re-opens the pack before declaring failure — `FindBySerial` can hand back an item still carrying the container it had when the snapshot was taken |
| `BATCH_FAILURE_LIMIT = 3` | only stones failing **in a row** stop the batch, so an isolated refusal costs one stone |
| leftover stone | reused instead of withdrawing another on top of it — but **only after a failure**, so Plain granite you are carrying for something else is left alone |
| `where_is()` | says "still in a container" or "on the ground N tiles away", never tiles for something in a bag |

The batch loop walks a bounded `range`, not a `while True`: every pass either
converts a stone or counts a failure, and both are capped.

What actually refused that drag is still unknown — the crate was in reach and
the next stone would have gone in. If it turns out to be systematic (a full
crate, a rate limit), the "3 in a row" message will name it.

### What it is verified by

| Step | Proof it worked |
|---|---|
| withdraw | granite arrives in the pack (re-opened, not a stale snapshot) |
| drop | the stone left the pack, or was consumed on arrival |
| `[grab` | the sand count **in the loot bag** stops rising — not "reaches 50", which would burn the whole timeout on every batch |
| deposit | the pack is counted again; nothing moved means **stop**, rather than piling another 50 on top |

If `[grab` picks up nothing, sand still on the ground within reach is dragged
in as a fallback, and being out of reach is reported rather than walked to.

Timing: a withdraw re-opens the storage window every time, so a stone costs
roughly four seconds and a batch of 50 about three and a half minutes.

| | |
|---|---|
| Repo | `Scripts/Sandmaker.py` |
| Live | `E:\uoclients\RazorEnhanced\Scripts\sandmaker.py` (lower-case) |
| Version | `2026-09-30.4` |
| Tests | `tests/test_sandmaker.py` — 200 checks; `tests/test_diag_storage_gump.py` — 20 |
| Diagnostic | `Scripts/diag_storage_gump.py`, live as `diag_storage_gump.py` since 2026-09-18 |

## The disconnect — CAUSE FOUND, fix untested in game

**Running it disconnected the client on 2026-09-18.** The cause is now known
from a live dump plus ServUO source. Version `2026-09-18.3` fixes it; it has
**not** been run in game yet.

What happened:

```
[Sand]   the 'Plain' row is button 6, 59998 in stock
[Sand]   CHECK THIS: the Gump Inspector said 1. The rows have moved.
[Sand] withdrawing 1 Plain (button 6)
[Sand] Nothing that looks like granite (0x1779) arrived in the pack.
        ... disconnect ...
```

### Why it dropped: a text entry the window does not have

The press was `Gumps.SendAdvancedAction(0x6ABCE12, 6, [], [0], ["1"])` — one
text entry. The dump (`docs/stone-storage-gump-dump-2026-09-18.txt`) shows the
Stone Storage draws **zero** `textentry` elements: the `1` beside
`Withdrawal Amount:` is a plain `{ text 150 305 1153 22 }`. ServUO's
`DisplayGumpResponse` disconnects any reply carrying **more text entries than
the gump drew**. That was the drop, and **button 1 would have dropped just the
same.** The recorded macro's first line, `SendAdvancedAction(0x6abce12, 21,
[], [0], ["1"])`, is the identical mistake.

That also answers "why did a drawn button disconnect": it wasn't the button.

### Why the search said 6: two columns, buttons on the left

```
button 1 @x35   Plain @x75   59998 @x215   button 6 @x275   Gold @x315
button 2 @x35   Dull  @x75   0     @x215   button 7 @x275   Agapite @x315
...                                         ...
button 5 @x35   Bronze        0             button 10        Mythril
button 21 @225,308 (arrow beside the amount)   22 Add   23 Fill from backpack
```

`find_stone_row()` preferred the button to the **right** of the label, walked
past Plain's own button (left) and took Gold's. The five-row offset is the
column width. The label/count pairing was always right.

### What 2026-09-18.3 changed

| | |
|---|---|
| the press | `Gumps.SendAction(STASH_GUMP, button)` — **no text entry, no switches** |
| before the press | refuses if the window now draws any text entry (`text_entry_count`) |
| the amount | `check_amount()` **refuses** unless the window already reads `1`, and refuses when it can't read it. Nothing is sent with the press, so what the window says is what comes out. |
| `find_stone_row()` | nearest button to the label's **left**, and after the previous cell on the row — so a row missing its own button gets none, not its neighbour's. Still a cross-check only; the Inspector's `1` is what is pressed. It now agrees. |
| button parsing | id is the 7th number of `button` and `buttontileart` (was: the last) |

Every guard was mutation-tested; putting the old right-hand search back
reproduces `(6, '59998')` for Plain on the live layout.

**If the amount ever needs changing**, button 21 is the arrow beside it — it
probably opens a prompt. Not investigated; set it by hand.

### What the source says (checked 2026-09-18, second session)

*Written before the dump arrived. The "one of these is true" list below was answered by the dump: rule 3, text entries.*

**What stock ServUO disconnects for.** `Server/Network/PacketHandlers.cs`,
`DisplayGumpResponse`, has exactly four drops, all checked against the gump
instance the reply names (serial *and* type id):

1. a button id not drawn on that gump — `GumpButton` or `GumpImageTileButton`;
   0 (close) always passes
2. more switches than the gump has
3. more text entries than the gump has
4. a text entry longer than 239 characters

A reply naming a gump the server **no longer holds matches nothing and is
ignored.** It is not a drop. So the recorded macro's second press was a press
that did nothing, and the claim here and in the scripts that "answering a
window that closed disconnects you" was wrong for stock ServUO. Corrected.

**What Razor sent for button 6.** `Gumps.SendAdvancedAction` at `v1.0.0.12`:
closes the gump client-side (`0xBF/0x04` with button 0), then sends one `0xB1`
reply with the gump's last-seen serial, button 6, zero switches and one text
entry (id 0, `"1"`). Against a gump with one text entry and a drawn button 6,
**none of the four rules fires.**

So one of these is true, and the report below cannot tell them apart:

- the shard's core is **not stock** here
- button 6's **own handler** did it — an unhandled exception in
  `gump.OnResponse` is not caught anywhere in `DisplayGumpResponse` or
  `MessagePump`, and would take the server down, dropping *everyone*
- the drop came **after** the press and was not caused by it

Two questions for the user settle most of that: did anybody else drop at the
same moment, and did `Stopping after 0 stone(s)` print before the disconnect?

**A real parser bug, fixed.** Both `drawn_buttons()` and `layout_buttons()`
took the **last** number of any element starting with `button`. The id is the
**seventh** (`GumpButton.cs`, `GumpImageTileButton.cs`); for a `buttontileart`
the last number is its **height**. So a tile-art button's real id was missing
from the drawn set and its height was in it. Not proven to be *this* failure —
the window may draw no tile-art buttons at all — but a guard built on it was
guarding the wrong numbers. The diagnostic skipped `buttontileart` entirely.

**A hypothesis for the five-row offset — NOT acted on.** On the Resource Order
Book, the only live dump of this gump class in the repo, **every button sits to
the LEFT of its label** (`docs/resource-order-book-gump.md`: button 1 at x=35,
label at x=75; the rest at x=250, labels at x=270). `find_stone_row()` prefers
a button to the **right**. If the Stone Storage is drawn in two columns of
five, Plain's own button is to its left and the first button to its right is
the second column's first row — **Gold, row 6.** That fits every number seen.
It is a prediction the dump will confirm or kill: Plain's button left of the
`Plain` label, button 6 on the same y, labelled `Gold` on its right. The
search's preference is deliberately **unchanged** until then.

**Why the dump never arrived.** The live copy was `diag_storage_gump,py.py` —
the *first* version, which printed the buttons **first**, so they had scrolled
away by the end. The buttons-last version was only ever in the repo. The new
one is deployed as `diag_storage_gump.py`, shows the label on **both** sides of
every button, lists text cells with their x,y, and writes the whole report plus
the raw layout to `%TEMP%\storage_gump_dump.txt`. The stale comma-named copy
is still in the live folder.

## What IS confirmed

All from the Item Inspector / Gump Inspector, 2026-09-18.

| Thing | Value |
|---|---|
| Stone Storage | `0x4017817A`, stash gump `0x06ABCE12` |
| Granite Crate (the converter) | `0x402452BA`, ItemID `0x0E3D`, at **(2071, 2506, 2)**, **Container: Yes** |
| platform (where sand appears) | `0x402452B1`, ItemID `0x07BD`, at **(2073, 2504, 3)**, **Container: No** |
| Plain granite | ItemID `0x1779`, hue `0x0000` |
| sand | ItemID `0x423A`, hue `0x096D`, weight 1 stone |
| Withdraw button for granite | **1** |
| Withdrawal Amount | reads `1`, at string index 22 |

The crate and the platform are **2 tiles apart**.

### The Stone Storage's string table

```
 0  Stone Storage
 1  Plain      2  59999        11 Gold      12 0
 3  Dull       4  0            13 Agapite   14 0
 5  Shadow     6  0            15 Verite    16 0
 7  Copper     8  0            17 Valorite  18 0
 9  Bronze    10  0            19 Mythril   20 0
21  Withdrawal Amount:        22  1
23  Add                       24  Maximum Storage:
25  999999                    26  Fill from backpack
```

**"Plain" is high quality granite.** The order book calls the same stone
*High Quality Granite* and the stack itself is named *high quality granite*.
Three names, one stone — see `docs/resource-order-handoff.md`.

## Why the original recording disconnected

Kept because two of the three are invisible in a recording:

```python
Gumps.SendAdvancedAction(0x6abce12, 21, [], [0], ["1"])
Gumps.WaitForGump(0x6abce12, 10000)      # the window is GONE by now
Gumps.SendAction(0x6abce12, 1)           # answering a window that closed
```

1. **A gump response closes the gump.** The third line answers a window the
   server no longer holds — which stock ServUO **ignores** rather than drops
   (see above), so this made the press useless, not necessarily fatal. The `WaitForGump` does not help — nothing reads its
   return value.
2. **Four `Player.Run`/`Walk` with no delay**, against fastwalk protection.
3. **Three `Items.Move` with no pause**, against a ~900ms drag limit.

That macro also tells us **1 was the withdraw all along** — it sent 21 *with
the amount* and then 1. So 21 is whatever commits the amount box.

The item serials in it (`0x40BB6349` granite, `0x40BB64E1` sand) are **new
items every run** and must never be config. Only containers are stable.

## Next steps, in order

1. **Test one small batch first.** Set `BATCH_SIZE = 3` and `BATCHES = 1`,
   stand on the spot, and run it. The journal should say
   `Sandmaker v2026-09-30.4` first — Razor caches scripts, so Reload in the
   Scripting tab if it does not — then `Withdrawal Amount reads 1.`,
   `withdrawing 1 Plain (button 1)` three times, the grab, and
   `stored 3 sand.`
2. Then set `BATCH_SIZE = 50`, `BATCHES = 0` and leave it running.
3. Delete the stale `diag_storage_gump,py.py` from the live folder.

**Proven in game 2026-09-30:** the no-text-entry press, the batch flow, the
grab, the loot bag and the deposit into the Reagent Keys — 186 stones, 186
sand, 4 batches, no disconnect. **Untested:** the retry and failure-limit
handling added after that run.

## The rest of the script

These parts have not failed and are covered by tests:

- **One press per window.** Nothing is pressed on the stash window after the
  withdraw; the response closed it.
- **Walking is `PathFinding`**, clock-bounded. No replayed keystrokes.
- **One drag each**, with `MOVE_PAUSE_MS = 900` after, verified by result.
- **The sand** is found by graphic `0x423A`, on the platform, and new since the
  drop. Hue is deliberately unpinned — `0x096D` is also Copper Granite's hue in
  the order book, so it may be the sand's colour or the stone's.
- Once `SAND_ID` is known it is the **whole** answer: the name fallback and the
  lone-candidate fallback are both gated on it being unset. Both used to
  outlive it, which meant anything appearing on the platform got picked up.
