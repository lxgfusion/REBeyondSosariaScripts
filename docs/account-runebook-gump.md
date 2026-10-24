# Account Runebook gump (`[ar`)

Captured from a live session with Razor's Enhanced Gump Inspector. This is the
data behind the navigation code in
[`Scripts/mining_runner.py`](../Scripts/mining_runner.py).

**Gump ID:** `0xc395adb4`

## Paging is server-side

Each page click returns a **new gump** — same gump id, new sequence number —
carrying only that page's entries. There are no client-side `{ page N }` markers,
so pages have to be walked with real clicks; you cannot read them all out of one
gump.

## Control buttons

| Button | Action |
|---|---|
| `504` | Page forward |
| `503` | Page back |
| `5` | Back to root folder |

Confirmed from the inspector's response log:

```
Response Received START
  Gump Sequence: 0xfd92
  Gump ID: 0xc395adb4
  Gump Button: 504          <- forward, root page 1/2 -> 2/2
Response Received END
New Received START
  Gump Sequence: 0xfd9d
  ... 10. Arcane
  Page 2/2
```

## Page structure

Nine entries per page. The last text line is always `Page X/Y`, which gives an
exact page count — no need to guess when walking has wrapped.

**Root folder, page 1/2:**

```
<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>
New Rune
New Runebook
Organize
1. Trammel
2. Ilshenar
3. Tokuno
4. TerMur
5. Mining
6. Homes
7. RO
8. TamingDeed
9. Inscription
<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/2
```

Page 2/2 holds just `10. Arcane`. Entry numbering continues across pages.

**Inside a folder** there is an extra line for the folder's own name, and every
rune is followed by its coordinates:

```
<CENTER><BASEFONT COLOR=#FFFFFF><BIG>Account Runebook</CENTER>
Mining                       <- folder name, absent at root
New Rune
New Runebook
Organize
1. Mining (Malas)
(1118, 1464, -95)
2. Mining (Malas)
(1122, 1456, -95)
...
<BASEFONT COLOR=#FFFFFF><CENTER>Page 1/3
```

## Telling a folder from a rune

**A rune is followed by a coordinate line; a folder is not.** That is the
reliable discriminator. A rune also publishes a second "gate" button at
`entry button + 30000`, which is used as a secondary signal.

## Pairing entry text to buttons

Entry buttons start at `10`. The parser does **not** count lines positionally —
it picks entries out by their `N. Name` pattern and pairs them, in display order,
with the page's entry buttons sorted ascending (excluding controls `1-5`, `503`,
`504`, and gate buttons ≥ 30000).

This matters because the inspector shows text but not button ids, so it is
unknown whether page 2's buttons restart at `10` or continue at `19`. Pairing by
display order is correct either way, and
[`tests/test_harvest_runner.py`](../tests/test_harvest_runner.py) asserts both.

Lines that are not entries — `New Rune`, `New Runebook`, `Organize`, the folder
name, the header, the `Page X/Y` footer — carry no entry button and are skipped
by the same pattern test.

## Three buttons per rune row, and one of them deletes

Inside a folder every rune draws **three** buttons (root folders draw two):

| Button | What it does |
|---|---|
| `entry` (10, 11, ...) | recall |
| `entry + 30000` | open a gate |
| `entry + 60000` | **DELETE the rune** |

The entry range (`10`-`499`) keeps the other two out of the pairing, but the
thing that actually protects you is pairing entries to buttons **sorted
ascending, zipped shortest-first** — the recall buttons always sort first.
Nothing should ever press a `+60000`; a mis-pairing there does not misfire a
recall, it destroys somebody's rune.

## Names are truncated, sometimes mid-phrase

The gump cuts a name wherever its column runs out, and not at a word boundary:

```
1. Britt Mage Shop (Tramm...      <- "Mage Shop" survives
7. Serpents Hold Mage Sho...      <- cut THROUGH it
```

So filtering runes by a phrase cannot be a plain substring test — that drops
Serpents Hold silently. Match the phrase, **or** a name that ends with the
start of it, which is all truncation can leave behind. See `wanted_rune()` in
[`Scripts/ReagentBuyer.py`](../Scripts/ReagentBuyer.py).

## A live folder, 2026-10-24

`Town Vendors` is entry **16**, on root page **2/3** — a folder search that
reads only page 1 never finds it. Inside are 15 runes over two pages, and they
are not all reagent shops: `Britt Carp Shop`, `Britt Blasksmith` and
`Britt Inscribe` sit among twelve `... Mage Shop ...` entries.

## Recalling

Click the entry button itself (e.g. `10`). The `+30000` variant opens a gate
instead.
