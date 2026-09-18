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
| Version | `2026-09-18.2` |
| Tests | `tests/test_sandmaker.py` — 86 checks; `tests/test_diag_storage_gump.py` — 20 |
| Diagnostic | `Scripts/diag_storage_gump.py`, live as `diag_storage_gump.py` since 2026-09-18 |

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

### What the source says (checked 2026-09-18, second session)

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

1. **Get the dump.** Run `diag_storage_gump.py` (NOT the comma-named copy),
   target the Stone Storage, and send `%TEMP%\storage_gump_dump.txt` — its
   path is the last line printed. It settles whether the buttons sit on their
   labels' rows, which side of the label, and whether any are `buttontileart`.
   Also ask: did anyone else drop at the same moment, and did
   `Stopping after 0 stone(s)` print before the disconnect?
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
