# Resource Order Book gump

Mapped from a live dump on 2026-07-27 (`diag_resource_orders.py`). The book is
`0x404AC332`, ItemID `0x2259`, hue `0x04F7`, locked down and Blessed on the
ground at (1282, 1192, -85). The chest beside it is `0x400CEF90`.

Two gumps are involved.

## 1. The book's own window — gump `0x06ABCE12`

Same id `harvest_runner.py` calls `HOUSE_DEPOSIT_GUMP`. 400x205, one page.

Every button sits at x=250 with its label at x=270, except button 1 (label at
x=75) and button 3 (which belongs to the text entry at x=152).

| Button | Position | Label | Meaning |
|---|---|---|---|
| `1` | (35, 47) | `Resource Orders...` + count `8656` | opens the order list |
| `3` | (225, 118) | — (sits beside the `Withdrawal Amount` box) | **withdraws** the amount typed into text entry 0 |
| `4` | (250, 120) | `Add` | not yet identified |
| `8` | (250, 150) | `Rename Book` | renames the book |
| `5` | (250, 180) | `Fill from backpack` | deposits orders from the pack |

Text entry **0** is `Withdrawal Amount`. `Maximum Storage:` reads `999999`.

`Fill from backpack` is the gump equivalent of the `Refill from stock` context
entry that `harvest_runner.py` already uses on this book.

## 2. The order list — gump `0xB2F21F1A`

600x530, one page marker (`{ page 0 }`) — the paging is **server-side**: each
press of Next Page returns a fresh gump under the same id with new button
numbers.

### Layout

Five columns at x = 40, 190, 290, 390, 490. Read off the rendered gump:

| Column | Header | Example |
|---|---|---|
| 1 | `Name` | `Ecru Citrine` |
| 2 | `Amt To Gather` | `23` |
| 3 | `Amt Gathered` | `0` |
| 4 | `Value Per` | `3000` |
| 5 | `Completed` | `No` |

Anchor the end of the header on whichever of those five labels appears **last**
in the string list. `Value Per` is the fourth of five, so anchoring on it alone
leaves `Completed` sitting in the row region.

Gems are worth far more than ingots: the book values them at **3000 gold each**
against 25 for copper ingots.

Header line at y=50. Fifteen order rows at y = 90, 110, ... 370. Five per-column
filter text entries (entry ids 0–4) at y=412, each with a submit button
(12, 22, 32, 42, 52). Column sort buttons at y=70 (10/11, 20/21, 30/31, 40/41,
50/51 — presumably ascending/descending per column).

### Buttons

| Button | Meaning |
|---|---|
| `4` | Previous Page (x=20, y=440) — **absent on page 1**, where a static `gumppic 9706` is drawn instead |
| `5` | Next Page (x=560, y=440) |
| `12`, `22`, `32`, `42`, `52` | submit the filter box under columns 1–5 |
| `10`/`11` … `50`/`51` | column sort, up/down per column (y=70) |
| `1`, `2`, `3` | footer actions — `Add`, `Purge`, `Fill from backpack` |
| `100`–`114` | the 15 order rows of page 1 |
| `115`–`129` | page 2 |
| `130`–`144` | page 3 |

Row buttons run **continuously across pages**, 15 per page:

    first row button of page N = 100 + (N - 1) * 15

Confirmed against live pages 1, 2, 3 and 4.

**The first row of every page has `Amt To Gather` = 0** and renders only three
cells. It still owns a button and must still consume one slot when rows are
zipped to buttons, or every later row points at the wrong order.

## The Name filter is a substring match

Text entry 0 with submit button `12`. Filtering `Valorite` returned 230 rows —
all of them **`Valorite Granite`**, not one ingot order. The book holds granite,
ore and ingot orders under the same metal name, so a filter must include the
resource word (`Valorite Ingots`), and whatever reads the rows must still check
the name rather than trust the filter.

That check has to be **exact**, not another substring test: `Iron Ingots` is
inside `Shadow Iron Ingots`, so filtering for iron returns shadow iron rows too.
Match `^<metal>\s+ingots?$`.

The two jobs are different and must not be collapsed:

- **Counting** rows on a page — anchor on the filter term, so a mixed page still
  produces one row per button and the zip stays aligned.
- **Selecting** a row to press — match the metal exactly, *after* the zip.

Dropping non-matching rows during the count shifts every later row onto the
wrong button.

## Rows must be anchored on the filter term, not sniffed

The Runics column can hold an actual runic name rather than `Yes`/`No`. A parser
that starts a new row at "any text that is not a known flag" counts those as
extra orders — a live run reported `Iron page 1: 17 rows but 14 buttons` and
discarded the page. On a filtered page with no matches the same parser swept up
the footer's `Add` / `Purge` labels and reported `2 rows but 0 buttons`.

Anchor a row start on the filter term. Everything else on the line is a cell,
never a new row.

The footer shows `(N/66)`; the header shows `Contents: 8656/100000` (orders held
by the book) and `Displayed: 980` (rows the list will page through — 980 / 15 =
66 pages, which is where the page count comes from).

**A row button withdraws that order** as a deed into the backpack — confirmed in
game on 2026-07-27.

Because the list is live, a row button is only safe to press on the page you
just read. Do not build a shortlist of rows and navigate back to them later:
other players fill these orders continuously, and a remembered button can point
at a different order by the time it is pressed. Re-scan per order instead.

## The deed

Confirmed from a live deed via the Enhanced Item Inspector, 2026-07-27:

```
Name:   A Resource Order Deed      ItemID: 0x14F0    Color: 0x0000
Serial: 0x405626A4                 Blessed, Movable, 1 stone
Container / Root Container: 1104416600  (= 0x41D40F58, the backpack)

A Resource Order Deed
Blessed
Weight: 1 Stone
0 / 132 Valorite Granite ObtainedValued At: 400 Gold Each
```

The progress line is `<filled> / <needed> <resource> Obtained`, followed by
`Valued At: <n> Gold Each`. Parse with:

```python
re.compile(r"(\d+)\s*/\s*(\d+)\s+(.+?)\s+Obtained\b", re.I)
```

after the lower/digit → upper seam fix, because `ObtainedValued` arrives as one
word.

### A fulfilled deed uses a different shape

Same item, same `0x14F0`, **still in the backpack** — completing an order does
not consume the deed, which is what makes carrying it to the hand-in possible:

```
A Resource Order Deed
Blessed
Weight: 1 Stone
Order Fulfilled [1038 Copper Ingots]Valued At: 25 Gold Each
```

```python
re.compile(r"Order\s+Fulfilled\s*\[\s*([\d,]+)\s+([^\]]+?)\s*\]", re.I)
```

The two shapes share **no label at all** — there is no `N / M` on a fulfilled
deed and no `Order Fulfilled` on one in progress. Anything reading a deed has to
try both, and should report a fulfilled one as `filled == needed` so callers do
not need to care which shape they got.

Note `]Valued` is not a lower→upper seam, so the seam fix does not split it; the
bracket has to be matched directly.

**There is no `Resource Type:` and no `Filled:`.** Those labels belong to
*taming* orders (`Level: 2Creature Type: KirinFilled: 24/60`), which
`tame_animals.py` handles. `harvest_runner.py`'s
`BOD_EXCLUDE_TEXT = ["creature type", "resource type"]` implies otherwise and is
misleading — the first parser here was written from it and read nothing at all,
reporting "no order deeds in the pack" with one sitting in the pack.

### Counting stacks: `Contains` alone is not enough

The chest holds the same metal across many stacks — a dozen iron ones, several
of most others. `Item.Contains` is a **snapshot** taken when the container was
opened: once stacks are spent or merged it goes stale and a changed stack can
drop out of it, so a metal gets under-counted and the budget comes out lower
than the real stock.

Union two sources, deduped by serial:

```python
chest.Contains                                            # the snapshot
Items.FindAllByID(0x1BF2, hue, chest.Serial, -1, False)   # asked per hue
```

The second queries the item index directly and sees stacks the snapshot has lost
track of. Deduping matters as much as the union — counting a stack twice inflates
the budget and promises ingots that are not there.

### Filling

Double-click the deed, then target the ingot stack **where it lies in the
chest** — confirmed in game. The ingots do not have to be in the backpack, so
there is no move-in/move-out round trip and no weight to manage. Target the
largest stack first and one target usually covers the whole order.

The reserve is still enforced, just earlier: an order is only accepted when its
amount is within `total − KEEP_PER_TYPE`, so filling it straight from the chest
cannot take the total below the reserve.

Two traps when matching a deed to stock:

- The book carries **granite and ore** orders under the same metal names.
  Filtering for Valorite ingots produced a Valorite *Granite* deed. Require the
  word `Ingots`.
- **Substring matching is wrong.** `Iron` is inside `Shadow Iron` and `Copper`
  inside `Dull Copper`, so an Iron run would accept a Shadow Iron order and pour
  the wrong metal at it. Match the whole resource name:
  `^<metal>\s+ingots?$`.

## The trap: empty gump strings shift every later index

**Do not index `Gumps.GetLineList` output by the text id in the raw layout.**

Razor Enhanced drops empty strings while parsing the gump's string table, and
does not leave a gap. From `Razor/Network/Handlers.cs`, still present in
`v1.0.0.14`:

```csharp
len = pComp.ReadInt16();
if (len > 0)
{
    string tempstring = pComp.ReadUnicodeString(len);
    stringlistparse[x1] = tempstring;
    x1++;                          // only advances for a NON-EMPTY string
}
else
{
    stringlistparse[x1] = "";      // written, then overwritten by the next one
}
```

So every empty string in a gump shifts all following indices down by one, and
`GetResolvedStringPieces` inherits the same fault because it indexes the same
table.

This gump has **nine** empty strings on a full page:

- 5 — the per-column filter text entries, all empty
- 2 — the blank headers of columns 4 and 5
- 2 — a fulfilled order's `Value Per` and `Gold` cells (the row whose
  `Amt To Gather` is `0` renders only three cells, not five)

which is why the first dump showed `<id 9?>` and pushed `No` from the end of one
row to the front of the next.

### What to do instead

Parse rows by their own shape, and zip them with the page's sorted row buttons:

1. Cut the row region out with literal anchors — after the `Value Per` header,
   up to `Previous Page`.
2. A row starts at any cell containing letters that is not `Yes`/`No`; the first
   numeric cell after it is `Amt To Gather`.
3. Zip those rows, in order, with the row buttons sorted by Y.

That survives both the index shift and rows that render fewer cells than their
neighbours.

## Ingots are distinguished by hue, not by name

Every ingot stack in the chest is named `<amount> ingots` — the name carries the
count, never the metal. Keying stock by name merges different metals and splits
the same metal across stacks of different sizes.

Key on **hue**. Verified against ServUO `Scripts/Misc/ResourceInfo.cs`; all
ingots share ItemID `0x1BF2` (`Scripts/Items/Resource/Ingots.cs`):

| Hue | Metal |
|---|---|
| `0x0000` | Iron |
| `0x0973` | Dull Copper |
| `0x0966` | Shadow Iron |
| `0x096D` | Copper |
| `0x0972` | Bronze |
| `0x08A5` | Gold |
| `0x0979` | Agapite |
| `0x089F` | Verite |
| `0x08AB` | Valorite |

The metal is also named on the stack's **third tooltip line**, in lower case —
`copper`, `shadow iron`, `bronze`, `golden`, `dull copper`, `agapite`, `verite`,
`valorite`. Iron has no third line at all, being the default. That corroborates
the hue table exactly and is a usable cross-check, but note `golden` where the
order text says `Gold`, so the two vocabularies are not interchangeable.

Live stock as of 2026-07-27, keyed correctly by hue:

| Metal | On hand |
|---|---|
| Iron | 837,973 |
| Copper | 121,714 |
| Shadow Iron | 113,158 |
| Bronze | 105,742 |
| Gold | 99,860 |
| Dull Copper | 78,794 |
| Verite | 61,024 |
| Agapite | 34,635 |
| Valorite | 25,020 |

The chest holds exactly these nine and nothing else. **There is no Mythril at
all** — confirmed by the player — although every order in the book's default
view asks for `Mythril Ingots`.

That has a direct consequence for the filler: the unfiltered list is useless.
All 980 displayed rows across 66 pages are Mythril, so paging through it finds
nothing fillable. **Always drive the Name filter** (text entry 0, submit button
12) with a metal that is actually in stock, and page only within that result.
