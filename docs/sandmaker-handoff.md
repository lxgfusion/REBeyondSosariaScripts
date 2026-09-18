# Sandmaker handoff

State as of **2026-09-18**. `CLAUDE.md` carries the conventions and the API
gotchas and loads automatically; this file is only the state of *this* task.

## The job

Convert Plain granite to sand, one stone at a time:

```
withdraw ONE Plain granite from the Stone Storage
walk to the Granite Crate and drop it in      (conversion is instant)
walk to the platform and pick up the sand
```

| | |
|---|---|
| Repo | `Scripts/Sandmaker.py` |
| Live | `E:\uoclients\RazorEnhanced\Scripts\sandmaker.py` (lower-case) |
| Tests | `tests/test_sandmaker.py` — 74 checks |
| Diagnostic | `Scripts/diag_storage_gump.py` |

## STILL BROKEN — read this first

**Running it disconnected the client on 2026-09-18.** The fix shipped in the
same session has NOT been tested in game.

What happened:

```
[Sand]   the 'Plain' row is button 6, 59998 in stock
[Sand]   CHECK THIS: the Gump Inspector said 1. The rows have moved.
[Sand] withdrawing 1 Plain (button 6)
[Sand] Nothing that looks like granite (0x1779) arrived in the pack.
        ... disconnect ...
```

`find_stone_row()` inferred **button 6** for the `Plain` row. The Gump
Inspector had said **1**. The search was believed, 6 was pressed, and the
client dropped.

### What was changed in response

`choose_button()` precedence is now **inverted**:

| | |
|---|---|
| `WITHDRAW_BUTTON` | an explicit override, if set. Usually 0. |
| `WITHDRAW_BUTTON_CONFIRMED = 1` | **wins.** Read off a real click in the Gump Inspector. |
| `find_stone_row()` | a **cross-check only**. Decides nothing. |
| neither set | nothing is pressed. |

The reasoning, which is the thing to keep: the search infers a button from
**geometry** — a label's Y, a tolerance, a preference for whatever sits to its
right. Every one of those is a guess about how the window is drawn. A Gump
Inspector reading is the id the server received when a human clicked the thing
they meant. `CLAUDE.md` says shard data comes from source or a live dump; the
Inspector *is* the live dump.

### What is NOT known

- **Why pressing 6 disconnected.** It was in the drawn set — `drawn_buttons()`
  did not object. So a drawn button on this window can still drop you, which
  means "verify it was drawn" is necessary and not sufficient.
- **What button 6 actually is.** If the ten stones are buttons 1–10 in listed
  order (Plain, Dull, Shadow, Copper, Bronze, Gold, Agapite, Verite, Valorite,
  Mythril) then 6 is *Gold* — a five-row offset, which would point at a
  systematic error in the label→button pairing rather than a near miss.
- **Why the search was five rows out.** The label/count pairing was RIGHT
  (`Plain` / `59998` came back correctly), so the text-cell reading is sound.
  It is the button-to-row step that is wrong. Most likely the withdraw buttons
  are not drawn on the same Y as their labels.

**The user reports this has bitten other keys too** and that those needed
fixing as well — so whatever is wrong here is probably not specific to the
Stone Storage.

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
   client no longer has. The `WaitForGump` does not help — nothing reads its
   return value.
2. **Four `Player.Run`/`Walk` with no delay**, against fastwalk protection.
3. **Three `Items.Move` with no pause**, against a ~900ms drag limit.

That macro also tells us **1 was the withdraw all along** — it sent 21 *with
the amount* and then 1. So 21 is whatever commits the amount box.

The item serials in it (`0x40BB6349` granite, `0x40BB64E1` sand) are **new
items every run** and must never be config. Only containers are stable.

## Next steps, in order

1. **Find out why a drawn button dropped the client.** Run
   `diag_storage_gump.py` and capture the full `BUTTONS THE SERVER DREW`
   block — every id with its x,y and row label. That is the block that has
   never arrived, and it is what settles whether the buttons sit on their
   labels' rows at all.
2. **Then fix `find_stone_row()`** — or delete it. It has been wrong once on a
   window where wrong means disconnected, and a cross-check that cannot be
   trusted is worth less than no cross-check.
3. **Then test one round** with `RUNS = 1`.
4. Only then raise `RUNS`.

Do **not** re-enable the search as the decider without evidence that the
button/label pairing is sound.

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
