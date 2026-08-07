# Razor Enhanced Scripts

Automation scripts for [Razor Enhanced](https://razorenhanced.net/), the Ultima
Online assistant. Written for its embedded IronPython 3.4 runtime and targeted
at a RunUO/ServUO-derived freeshard.

## Scripts

| Script | What it does |
|---|---|
| [`Scripts/tame_animals.py`](Scripts/tame_animals.py) | Reads the taming order deeds in your pack and hunts only those species. Walks to each one, tames it, and puts it in the deed for its species. |
| [`Scripts/diag_deeds.py`](Scripts/diag_deeds.py) | Troubleshooting. Dumps every item you carry with the verdict the tamer would reach — whether it reads as a deed, and which species it names. |
| [`Scripts/COVFarm.py`](Scripts/COVFarm.py) | **Camps the Slasher of Veils and kills it from range.** Waits for the spawn, opens with Wildfire, then holds a set distance while spamming Nether Blast until it dies. Matches the monster on its name, with the body only as a pre-filter. Breaks off below a configurable health percentage. |
| [`Scripts/petcommandcenter2.py`](Scripts/petcommandcenter2.py) | **Deploy and shrink your pets by speaking a phrase.** Say one phrase to release every pet statue in your pack and issue the guard command; say another to shrink the nearest pets back in. Set `SETUP_MODE = True` and it walks you through targeting your statues and shrink tool, then prints a finished config block to paste in — no reading item IDs out of the inspector. |
| [`Scripts/diag_tame_candidates.py`](Scripts/diag_tame_candidates.py) | Troubleshooting. **Run this when the tamer ignores a species.** Scans with *no* body filter and reproduces the tamer's decision for every creature in range, naming the reason. Catches the silent case where the shard's body value differs from the catalogue — the scan filter never returns those creatures, so nothing is logged at all. Also reports what Razor's ignore list is hiding. Read-only. |
| [`Scripts/diag_deed_target.py`](Scripts/diag_deed_target.py) | Troubleshooting. Tries five deed double-click-and-target sequences against one already-tamed pet to find which your shard accepts. |
| [`Scripts/harvest_runner.py`](Scripts/harvest_runner.py) | **Mining + lumberjacking on one script.** Account-runebook travel, per-job rune routes, smelting, drop-off runs, vendor rounds, meditation-backed mana, and the Greyskull call-out. |
| [`Scripts/mining_runner.py`](Scripts/mining_runner.py) | Superseded by `harvest_runner.py`. Kept as a working fallback until the integrated script is confirmed in-game — delete it once it is. |
| [`Scripts/diag_ar_gump.py`](Scripts/diag_ar_gump.py) | Troubleshooting. Dumps the account runebook gump — layout, text, buttons, page markers — to a file. |
| [`Scripts/diag_vendors.py`](Scripts/diag_vendors.py) | Troubleshooting. Lists nearby NPCs with the exact names Razor sees and their context menu entries. |
| [`Scripts/diag_journal.py`](Scripts/diag_journal.py) | Troubleshooting. Live journal tap — prints every incoming line with its type, speaker and text, and whether it matches a watch phrase. |
| [`Scripts/resource_order_runner.py`](Scripts/resource_order_runner.py) | **Fills resource orders.** Counts the chest's ingots by hue, takes orders it can afford out of the book, fills them, then recalls to `RO > RO` and drags the completed deeds to the Resource Gatherer. Keeps 100 of each metal behind. Confirmed end-to-end in game. |
| [`Scripts/diag_order_names.py`](Scripts/diag_order_names.py) | Walks all 540 pages of the Resource Order Book and records the exact name of every resource it asks for, with counts. Read-only. Run once to stop guessing at names. |
| [`Scripts/diag_resource_orders.py`](Scripts/diag_resource_orders.py) | Groundwork for the resource-order filler. Does the chest ingot census and fill budget for real, and dumps the order book's two gumps with each row paired to its own button. Read-only. |

## Installing a script

1. Copy the `.py` file into your Razor Enhanced scripts directory (the folder
   configured under the **Scripting** tab).
2. In Razor Enhanced, open **Scripting**, hit **Reload**, select the script.
3. Optionally bind it to a hotkey.

## `tame_animals.py`

### The deeds decide what gets hunted

There is nothing to configure and no prompts. Put your taming order deeds in your
backpack and run it. It reads each deed, works out which species it is for, and
hunts **only** those. No unicorn deed means unicorns are never approached.

1. Scan the pack. Each deed's name and tooltip is matched against a catalogue of
   112 tameable species — see [`docs/tameable-animals.md`](docs/tameable-animals.md).
2. The creature search filter is built from just those species' body values.
3. Chase the nearest match, tame it, put it in that species' deed.
4. Rescan after every success and every `DEED_RESCAN_MS`, so a deed that fills
   up drops out of the hunt and a newly added one joins it.

### Requirements

- Taming order deeds in your backpack.
- Enough Animal Taming for the species those deeds name. Species above your
  skill are reported and skipped rather than attempted.
- At least one free follower slot.

### Shared body values

Some species are indistinguishable by body: a **nightmare and a dread warhorse
are both body `0x74`**, and there are 14 other collisions. For those the script
reads the creature's *name* before touching it, and walks away if the name won't
load. A missed tame beats a tamed pet with no deed to hold it.

Name matching tolerates punctuation and spacing, so a deed saying `Ki-Rin`,
`Ki Rin` or `kirin` all resolve to the same species, and longer names win over
shorter ones — `hell cat` never resolves as `cat`, `dread warhorse` never as
`horse`.

### The deed format it reads

Confirmed against a live deed via Razor's Enhanced Item Inspector:

```
Name:   A Taming Order          ItemID: 0x2258
Serial: 0x4302A461              Root Container: 0x41D40F58  (the backpack)

A Taming Order
Weight: 1 Stone
Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:
```

Two things about that text drive the implementation:

- **Properties arrive concatenated** — `KirinFilled`, `2Creature`. There is no
  separator between one property's value and the next one's label. The script
  inserts a space at each lower/digit → upper seam before matching, otherwise
  `kirinfilled` never matches the species `ki-rin`.
- **`Creature Type:` is read as a field**, not found by scanning the whole
  tooltip. The value ends where the next field's label starts. Field labels are
  configurable via `DEED_SPECIES_FIELDS`.

`Filled: 24/60` is read too — a deed at `60/60` is full and is dropped from the
hunt list (`SKIP_FULL_DEEDS`), and progress is shown in the `DEBUG` scan output.

### If it finds no deeds

An item only counts as a deed if its name or tooltip contains one of
`DEED_NAME_HINTS` (default `order`, `deed`, `contract`) **and** it names a
species in the catalogue. Run [`Scripts/diag_deeds.py`](Scripts/diag_deeds.py) —
it prints every item you carry, the exact tooltip text read from it, and which of
those two checks failed. It changes nothing, so it's safe to run any time.

### Configuration

Deed discovery:

| Setting | Default | Effect |
|---|---|---|
| `DEED_NAME_HINTS` | `["order","deed","contract"]` | Words that mark an item as a deed. `[]` accepts any item naming a species. |
| `DEED_SPECIES_FIELDS` | `["creature type", …]` | Tooltip fields naming the species, most specific first. |
| `DEED_PROGRESS_FIELDS` | `["filled", …]` | Tooltip fields holding `24/60` style progress. |
| `SKIP_FULL_DEEDS` | `True` | Drop deeds already at capacity from the hunt list. |
| `DEED_GRAPHICS` | `[]` | Restrict the scan to these item IDs. Learned automatically otherwise. |
| `DEED_RESCAN_MS` | `60000` | How often to re-read the pack. |
| `NARROW_RESCAN` | `True` | After the first scan, only re-check graphics that already matched. Faster. |
| `MAX_PACK_SCAN` | `300` | Tooltip-read cap for very full packs. |

What to hunt:

| Setting | Default | Effect |
|---|---|---|
| `ONLY_ANIMALS` | `[]` | Whitelist. Restrict to these species even if you hold other deeds. |
| `NEVER_ANIMALS` | `[]` | Blacklist. Never hunt these even holding a deed. |
| `EXTRA_ANIMALS` | `[]` | Shard-custom species: `("name", [body, ...], min_tame)`. Body collisions with the catalogue are detected automatically and name-verified. |
| `SKIP_ABOVE_SKILL` | `True` | Skip species whose minimum taming skill you lack. |

Distance handling — the creature wanders while being tamed, and the server
re-checks both range and line of sight on every taming tick, so the script stays
**adjacent** rather than trailing:

| Setting | Default | Effect |
|---|---|---|
| `STAY_DIST` | `1` | Distance held during an attempt. `1` = adjacent. Re-closes every `POLL_MS` (150 ms). |
| `TAME_START_DIST` | `2` | Will open or continue an attempt from here without re-approaching. The server itself allows 3. |
| `LEASH_DIST` | `7` | Server's own cutoff. Past this the attempt is abandoned and a pathfound approach is redone. |
| `SETTLE_STEPS` | `6` | Steps at `TAME_START_DIST` without improving before accepting it — stops the script grinding against terrain trying to touch a creature it can't reach. |
| `STALL_STEPS` | `40` | Steps without getting any closer before writing the creature off. |

Other behaviour: `SCAN_RANGE` (18 tiles), `MAX_TAME_ATTEMPTS`,
`TAME_ATTEMPT_TIMEOUT`, and the `DEED_*` timings. `DEBUG` is on by default and
prints the pack scan plus every journal line the deed produces — turn it off once
things are confirmed working.

### The deed sequence (confirmed working)

Verified in-game via `diag_deed_target.py`, sequence 1:

1. Cancel any stale target cursor and confirm `Target.HasTarget()` is false.
2. `Items.UseItem(deed)`.
3. `Target.WaitForTarget(4000, False)`.
4. Pause `DEED_SETTLE_MS` (400 ms).
5. `Target.TargetExecute(petSerial)`.
6. Pause `DEED_RESULT_MS` (1500 ms), then confirm the pet is gone.

Steps 1 and 4 are load-bearing. **Step 1 was the original bug**:
`Target.WaitForTarget` returns `True` for a cursor that is *already* open, so a
cursor leaked by an earlier action swallowed the deed's target — the deed
double-clicked, a cursor sat open, and nothing was added. The taming loop leaked
one every time its own `WaitForTarget` timed out and it re-issued `UseSkill`.

The combined `Items.UseItem(deed, pet)` form is deliberately **not** used: the
Razor docs warn its built-in target "may not work on some free shards."

If the deed step ever breaks again, stand next to one already-tamed animal and run
[`Scripts/diag_deed_target.py`](Scripts/diag_deed_target.py). It tries five
sequences and stops at the first that consumes the pet, dumping the deed tooltip
and journal at each step.

### Caveats

- **It clears your journal** before every taming attempt. That is how it avoids
  reading a stale result. Don't run it when you need your journal history.
- It assumes the deed **consumes** the pet. If your deed leaves the pet standing,
  the script reports that the deed did not take.
- It does not fight. Creatures that need to be subdued first are skipped.
- Ruled-out creatures go on Razor's global ignore list. `Misc.ClearIgnore()` or a
  restart resets it.

## `harvest_runner.py`

Mining and lumberjacking on one script, driven by the account runebook (`[ar`).
Both original scripts are by Cral; this merges them so travel, mana, drop-off,
the vendor round and the Greyskull response are shared rather than duplicated.

### Jobs

```python
JOBS = [
    {"enabled": True, "name": "Mining",        "folder": ['Mining'], "task": "mine"},
    {"enabled": True, "name": "Lumberjacking", "folder": ['Lumber'], "task": "lumber"},
]
```

Each job names a runebook folder and a harvesting task. A job runs until its
**whole rune route** has been worked, then the next job starts.

| `JOB_ROTATION` | Switches jobs… |
|---|---|
| `"route"` *(default)* | after every rune in the folder has been worked once |
| `"dropoff"` | after each drop-off run |
| `"timer"` | every `JOB_TIME_MS` |
| `"never"` | never — stays on the first enabled job |

**Use `"route"`.** Wood is far heavier than ore, so a lumber run fills the pack
after one or two trees. Under `"dropoff"` that meant: chop one spot → pack full →
go home → *rotate away to mining*, with the rest of the lumber route never
visited. Under `"route"` a full pack is just a trip home — the script unloads,
returns to **the same spot**, and carries on for as many trips as it takes.

Unloading happens *inside* the job, so the route position survives it. Returning
home no longer resets or skips waypoints. A vendor round or Greyskull call
**resumes** the lap rather than restarting it — `run_job(job, resume=True)`.

`DROPOFF_BETWEEN_JOBS` (on by default) empties the pack when switching jobs.
Measured from a real trace: mining handed lumberjacking **225 of its 297 usable
stones**, and the wood storage only accepts wood — so lumber had two chops of
headroom and spent the route in a full/unload cycle instead of chopping.
`PACK_HANDOVER_LEVEL` (0.15) is the threshold that triggers it.

### Hostiles

| Setting | Default | Effect |
|---|---|---|
| `ABORT_ON_HOSTILES` | `True` | Skip to the next rune when something hostile is close. |
| `HOSTILE_RANGE` | `8` | Tiles. **Not optional** — see below. |
| `HOSTILE_NOTORIETIES` | `[4, 5, 6]` | Criminal, enemy, murderer. |
| `HOSTILE_SKIP_LIMIT` | `3` | Consecutive skips before harvesting anyway. |

The filter originally had **no `RangeMax`**, so it reported any criminal, enemy
or murderer anywhere the client could see — 18–25 tiles. In an area with
wandering spawns that is permanently true, and every hit skipped a waypoint, so
a route could burn from rune 1 to rune 9 without a single swing and then report
itself complete.

`HOSTILE_SKIP_LIMIT` is the backstop: after three skips in a row the script
harvests anyway rather than silently consuming the route, and says so.

### Axes

Found by **graphic first** (`AXE_IDS`, from ServUO), then by remembered serial,
then by name. Names are last because an item's `Name` is often empty until its
properties load — a name-only search returns nothing once the axe has been
stowed, which aborted the whole lumber job.

Meditation no longer disarms pre-emptively. It only frees hands if the server
actually answers `Your hands must be free to cast spells or meditate.`, so a
low-mana moment doesn't put your axe back in the pack for no reason.

**Set one job's `enabled` to `False` and the script behaves exactly like the
single-purpose version it came from.**

Jobs are validated at startup — a missing folder or an unknown task is named and
skipped rather than failing silently mid-run.

### What the merge changed

| Area | Before | Now |
|---|---|---|
| Runebook navigation | Two copies, only the lumber one page-aware | One page-aware navigator |
| Routes / waypoints | Single global | Per-job, so each folder keeps its own position |
| Weight check | Mining indexed tooltip line 2; lumber searched for "Contents" | Lumber's method, with mining's as fallback |
| Key restock | Two separate routines | One `RESTOCK_KEYS` table covering both |
| Hostile check | Lumber only | Shared, via `ABORT_ON_HOSTILES` |

Three bugs carried over from the originals were fixed:

- **`Player.UnEquipItemByLayer(layer, wait)` takes a Boolean**, not a timeout —
  the original passed `5000`.
- **Item names can be null.** The axe search called `.Name.lower()` unguarded and
  would throw on any unnamed item in the pack.
- **Page-walk duplication.** If the `Page X/Y` footer claims more pages than the
  next button delivers, the walk re-parsed the same page and duplicated every
  rune on it. The walk now verifies the page actually advanced.

### House deposits (order books)

`HOUSE_DEPOSITS` hands the taming and resource order books in on every drop-off
run — regardless of pack weight, which is why they aren't just `RESTOCK_KEYS`
entries (those only fire when the pack is full).

```python
HOUSE_DEPOSITS = [
    {"enabled": True, "label": "Taming orders",   "serial": 0x4057CC3A},
    {"enabled": True, "label": "Resource orders", "serial": 0x404AC332},
]
HOUSE_DEPOSIT_CONTEXT = ["Refill from stock"]
HOUSE_DEPOSIT_GUMP = 0x06ABCE12
```

The books use the **same `Refill from stock` entry as every other key**, and
pressing it deposits everything of that type at once. So this goes through the
same `context_select` as the keys and vendors, with the same exact-match-first
and `CONTEXT_NEVER` guards.

**No amount is ever sent.** The recorded macro ended with:

```
Gumps.SendAdvancedAction(0x6abce12, 0, [], [0], ["100"])
```

That is deliberately not reproduced. The deposit completes on the context reply;
the gump is just the book's window and its text field is for **withdrawing**, so
writing `"100"` into it risks pulling 100 items back out. The window is closed
instead, and a test asserts `SendAdvancedAction` appears nowhere in the deposit
path.

**Both books share one gump id**, so each deposit closes any stale window first —
`WaitForGump` returns `True` for an already-open gump, which would otherwise make
the second book answer the first one's window.

Deposits run *before* the chest sweep, same as the wood storage — specific
consumers get first refusal.

### Bulk order deeds

Deeds received from the scribe are dragged into a carried Bulk Order Book. **No
per-character editing is needed** — the book is found automatically:

```python
BOD_BOOK_BY_CHARACTER = {}   # optional: {"Hattori Hanzo": 0x413F54D6}
BOD_BOOK_SERIAL = 0          # optional: a specific book
BOD_BOOK_ID = 0x2259         # otherwise: first book of this graphic in the pack
```

Resolution is per-character map → explicit serial → graphic in the pack. The last
one is the default, so all three characters run the same file unedited. The
startup log says which book was found and how, plus its current deed count.

**A bulk order deed and a taming order share ItemID `0x2258`.** Two things keep
them apart:

1. `HOUSE_DEPOSITS` runs first, so `Refill from stock` has already taken the
   taming and resource orders out of the pack.
2. `BOD_EXCLUDE_TEXT` skips anything whose tooltip marks it as one of those.

The book itself also refuses taming and resource orders, so (2) is only there to
avoid pointless drag attempts — an empty list is safe, just noisier in the log.

Filing runs after the vendor round as well as at drop-off, since that's when
deeds are handed over. Every deed moved is logged by name, and the book's
`Deeds In Book: N` count is read before and after so a silent rejection shows up.

### Storage and drop-off

`RESTOCK_KEYS` lists containers that swallow harvested resources. Each is
single-clicked and answered with `Refill from stock`.

```python
{
    "label": "Wood Storage",
    "serial": 0x4290200A,          # tried first
    "id": 0x1BD9, "hue": 0x0058,   # fallback if the serial is gone
    "where": "world", "range": 12, # on the ground, not in the pack
}
```

**`where` matters.** The Wood Storage is *locked down on the ground at the
house* — the Item Inspector shows `Container: None`, `Root Container: None`,
`Ground: Yes`. The original searched `Player.Backpack.Serial` for it, so it could
never be found. `"world"` searches the ground within `range` tiles; `"pack"`
searches the backpack.

The wood storage is configured by four settings at the very top of the file, so
you can move it without touching `RESTOCK_KEYS`:

```python
WOOD_STORAGE_WHERE  = "world"      # "world" = locked down at the house
                                   # "pack"  = carried, empties on the spot
WOOD_STORAGE_SERIAL = 0x4290200A
WOOD_STORAGE_ID     = 0x1BD9
WOOD_STORAGE_HUE    = 0x0058
```

**A carried key never triggers a trip home.** When the pack fills, the script
first tries only storage it can find *on the player*, decided by where the item
actually is — not by `WOOD_STORAGE_WHERE`. If the key is in your pocket it
empties at the tree and the route carries straight on; the drop-off run only
happens when nothing carried can take the load.

Order in `dropoff()` is **storage first, then the chest.** `PURGE_ID` includes
logs and boards as a sweep, so running the chest first would empty the wood into
it before the Wood Storage ever saw it.

> This reverses the original mining order, where the chest ran before the keys.
> Ingots now get offered to the keys first. If that's wrong for mining, swap the
> two calls back in `dropoff()`.

### Lumberjacking

Needs an axe or hatchet in hand or pack; it equips one automatically.
`AXE_WORDS` / `AXE_EXCLUDE` control matching — `war axe` is excluded, `large
battle axe` is not.

Messages are from ServUO `Lumberjacking.cs`, plus the shard's own `You chop`
success line the original relied on:

| Message | Cliloc | Handling |
|---|---|---|
| `You chop` | shard | keep chopping |
| `You hack at the tree for a while` | 500495 | failed swing, keep chopping |
| `There's not enough wood here to harvest` | 500493 | next rune |
| `You can't use an axe on that` | 500489 | next rune |
| `You can't place any wood into your backpack` | 500497 | drop off |
| `You broke your axe` | 500499 | find another |

The server's lumberjacking `MaxRange` is **2 tiles**, so each rune has to land
within 2 tiles of a tree.

Mining's own detection is deliberately left exactly as the working original — the
verified ServUO strings are listed in a comment for future tuning, but nothing
that currently works was rewritten.

### Razor Enhanced signature changes that broke the original

Two API signatures changed underneath the script, which is why it stopped
working without being edited. Both are now called through shims that try the
current form and fall back to the old one:

| Was | Now |
|---|---|
| `Player.ChatSay(msg)` | `Player.ChatSay(colour, msg)` |
| `Gumps.GetLineList(gumpId)` | `Gumps.GetLineList(gumpId, dataOnly)` |

`Player.ChatSay` is what sends `[ar` to open the runebook, and
`Gumps.GetLineList` is what reads the folder and destination names out of it —
so between them they account for travel failing entirely.

### The Greyskull call-out

Global chat reaches the journal like this:

```
System: <Public> Fred Kruger: By The Power Of Greyskull!
```

Note that `entry.Name` is **`System`** — the actual speaker is buried in the
text. The script parses the channel and caller out of the line itself, so caller
filtering works on `Fred Kruger` rather than on `System`.

| Setting | Default | Effect |
|---|---|---|
| `GREYSKULL_PHRASES` | `["by the power of greyskull"]` | Matched **case-insensitively** as substrings. |
| `GREYSKULL_ALLOWED_CALLERS` | `[]` | **Empty = anyone can call it.** Add names only to restrict. |
| `GREYSKULL_REQUIRE_CHANNEL` | `""` | Empty = any channel. Set to `"Public"` to accept only `<Public>`. |
| `GREYSKULL_IGNORE_SELF` | `False` | Off, so calling it out yourself still works. |
| `GREYSKULL_HOLD_MS` | `20000` | How long to hold at the circle. |

Two bugs were fixed here:

**Case-sensitive matching.** The old code did an exact `Journal.Search` for
`"By The Power Of Greyskull!"`. Since that phrase is typed by hand, any variation
in capitalisation missed silently. Matching is now case-insensitive.

**Long waits swallowed the chant.** `checkGreyskull()` was only called from three
places, none of which run during meditation — and `ensure_mana()` can block for
90 seconds. Detection is now split from the response: `poll_greyskull()` only
raises a flag and is safe to call anywhere, including from inside travel waits,
while `checkGreyskull()` acts on the flag at the top of the main loop. Every long
pause now uses `interruptible_pause()`, which keeps listening. With a chant
pending, meditation also stops at the travel floor instead of topping up to full.

Detection uses a journal **timestamp cursor** rather than `Search` + `Clear`, so
one chant fires exactly once, chants said before the script started are ignored,
and the mining and meditation journal checks are left undisturbed.

If it still doesn't trigger, run [`Scripts/diag_journal.py`](Scripts/diag_journal.py)
and say it — that prints every journal line with its Type, speaker and text, and
says whether it would have matched.

### Mana management

Nothing travels on an empty pool. `ensure_mana()` runs before every recall and
retries a travel that bounced off "Insufficient mana".

| Setting | Default | Effect |
|---|---|---|
| `MIN_MANA_TO_TRAVEL` | `20` | Floor before any recall. Recall costs 11 on stock RunUO; the rest is headroom for a failed cast. |
| `MANA_TARGET` | `0` | Meditate up to this. `0` means to full. |
| `MEDITATION_TIMEOUT` | `90000` | Total ms to spend recovering before giving up. |
| `DISARM_FOR_MEDITATION` | `True` | Stow held items — meditation refuses to start with full hands. |

Two things stop meditation outright, both detected and handled:

- **`Your hands must be free to cast spells or meditate.`** — the script stows
  whatever is held and retries.
- **`Regenative forces cannot penetrate your armor!`** — metal armour blocks
  meditation completely. There is no way around it in script; it falls back to
  standing still for passive regeneration and says so once. If you mine in metal,
  swap to leather or expect slow recovery.

### Vendors — the `VENDORS` table

**This is the first thing in the script**, above every other setting, because it
is the config most likely to need editing. Every NPC the script talks to is
listed there and nothing else needs changing to add, remove or rename one.

```python
{
    "enabled": True,
    "label":   "Inscription Orders",
    "folder":  ['Inscription'],                       # runebook folder path
    "point":   'Inscription',                         # rune name
    "names":   ["Sahale the scribe", "Sahale", "scribe"],   # NPC, substring
    "context": ["Bulk Order Info", "Bulk Order", "Talk"],   # tried in order
    "gump":    (0x9bade6ea, 1),                       # optional follow-up
}
```

Each entry is self-contained — folder and rune name are inline, so there are no
separate constants elsewhere to keep in sync.

| Field | Notes |
|---|---|
| `enabled` | `False` skips a stop without deleting it. |
| `folder` | Folder path, e.g. `['RO']` or `['Work', 'RO']` when nested. |
| `point` | Rune name, matched case-insensitively as a substring. |
| `names` | Matched case-insensitively as **substrings** against the NPC's name *and* its tooltip. List several; first match wins. **This is the field that usually needs fixing.** |
| `context` | Menu entries tried in order until one is accepted. Prefer the exact label. |
| `gump` | `(gumpid, buttonid)` to answer afterwards, or `None`. |

### Context entries

Confirmed from `diag_vendors.py`:

| NPC | Menu | Entry used |
|---|---|---|
| Sherri | Open Paperdoll, Stable Pet, **Talk**, Buy, Sell, Train Animal Lore, Train Animal Taming, Train Veterinary | `Talk` |
| Edie | Open Paperdoll, **Bulk Order Info**, Bribe, Claim Rewards, Buy, Sell, Train Evaluating Intelligence, Train Inscription | `Bulk Order Info` |

Note what sits alongside them: **Buy, Sell, Bribe, Open Bankbox** and
**Train &lt;skill&gt;** — all of which cost gold. Selection therefore runs in two
passes:

1. An **exact** label match, always honoured. If you configured it verbatim, you
   meant it.
2. Otherwise a substring match, which refuses anything hitting `CONTEXT_NEVER`
   (`buy`, `sell`, `bribe`, `open bankbox`, `train `).

So a sloppy `context` value of `"Taming"` will **not** buy Train Animal Taming,
while configuring `"Train Animal Taming"` exactly still works if that is what you
want.

What gets sent to `Misc.ContextReply` is the real label read from the menu, not
your search string — so `"Bulk Order Info"` still works if the live entry reads
slightly differently.

### Bulk order gumps

`gump` accepts a **list** of `(gumpid, buttonid)` pairs, tried in order, because
large and small bulk orders may not use the same gump id:

```python
"gump": [(0x9bade6ea, 1)],
```

Two things address bulk orders intermittently not being accepted:

- **Stale gumps are closed first.** `Gumps.WaitForGump` returns `True` for a gump
  that is *already open* — the same trap as `Target.WaitForTarget`. A window left
  over from the previous vendor made the script answer the wrong one, which looks
  random from the outside.
- **The whole interaction retries** `VENDOR_RETRIES` times.

If the expected gump still doesn't appear, the log names the id that opened
instead:

```
[Harvest] Inscription Orders: expected gump 0x9BADE6EA but 0xXXXXXXXX opened
          instead. Add (0xXXXXXXXX, <button>) to this vendor's "gump" list.
```

Add that pair to the list. If the button number is also unknown, the Enhanced
Gump Inspector's response log shows it when you click Accept by hand.

**A vendor's title is usually in its tooltip, not its name.** Confirmed with the
Enhanced Mobile Inspector:

| NPC | `Name` | Properties |
|---|---|---|
| Resource Gatherer | `Davin the Resource Gatherer` | *(empty)* |
| Animal Trainer | `Sherri` | `Animal Trainer`, `Quest Giver` |
| Scribe | `Edie` | `Scribe` |

Matching only the name could never find Sherri or Edie. `find_vendors` now checks
the name first (cheap) and falls back to the tooltip, so **match on the title**
rather than a given name the shard may change — `Sahale the scribe` is already
gone, replaced by `Edie`.

`Mobiles.Filter().Name` is also an **exact** match, which is why the original
loop silently did nothing the moment an NPC was renamed.

When a lookup fails, the log now lists every NPC standing there with its tooltip,
so the real title is visible without running a separate diagnostic.

**Startup validation.** The table is printed and checked when the script starts.
An entry missing its NPC names, rune name, or context entries is called out and
skipped rather than failing silently mid-round:

```
[Mine] Vendor round:
[Mine]   Resource Orders        RO -> RO   NPC: Resource Gatherer, Resource
[Mine]   Taming Deeds           SKIPPED - no NPC names
[Mine]       Fill it in at the top of this script, or set "enabled": False.
```

Run [`Scripts/diag_vendors.py`](Scripts/diag_vendors.py) beside an NPC to get its
real name and context entries verbatim.

### Runebook pages

Confirmed by gump inspection — full protocol in
[`docs/account-runebook-gump.md`](docs/account-runebook-gump.md):

| Button | Action |
|---|---|
| `504` | Page forward |
| `503` | Page back |
| `5` | Back to root |

Paging is **server-side**: each click returns a fresh gump carrying only that
page's nine entries, so pages must genuinely be walked. The `Page X/Y` footer
gives an exact page count, so walking is bounded rather than guessed.

This was the actual bug. Folder lookup and the mining route both only ever saw
page 1 — so `Arcane` (page 2 of the root) was unreachable, and a 3-page mining
folder ran the same 9 runes forever instead of all 12.

Two details the parser depends on:

- **A rune is followed by a coordinate line, a folder is not.** That's how they
  are told apart, rather than by guessing at button ids.
- **Entries are found by their `N. Name` text**, then paired with the page's
  entry buttons in display order. The inspector shows text but not button ids, so
  it's unknown whether page 2 restarts at button `10` or continues at `19` —
  pairing by display order is correct either way, and the tests assert both.

If the runebook changes, re-run [`Scripts/diag_ar_gump.py`](Scripts/diag_ar_gump.py).
Its click-probe stays off by default — blind-clicking runebook buttons can recall
you or spend a charge. Both diagnostics write a full dump to `%TEMP%` and print
the path.

## Diagnosing a job that fails

Set `DIAGNOSTIC_MODE = True` at the top of
[`Scripts/harvest_runner.py`](Scripts/harvest_runner.py) and run it. It walks
**every rune of every job**, takes one harvest swing at each, and prints exactly
what the server replied — then stops. No rotation, no vendor round, no drop-off.

This debugs the real code path rather than a parallel copy, and writes the whole
trace to `%TEMP%\harvest_diag.txt`.

Per waypoint it reports the axe found, pack and mana, the task's return value,
every journal line verbatim, and — the important one — which message bucket
matched:

```
======== Lumberjacking waypoint 3 of 9 ========
[Harvest] Lumberjacking waypoint 3/9: Lumber (Malas)
[Harvest]    axe: gargish axe (0x402119CB, id 0x48B2)
[Harvest]    pack: 40/125 items, 210/400 stones   mana: 74/100
[Harvest]    task returned: ok
[Harvest]    journal: You chop some logs and put them in your pack.
[Harvest]    matched: SUCCESS
```

If it says `matched: NOTHING`, the shard's wording isn't in any `LUMBER_*` list
and that is the bug — copy the raw line into the right one. It also unloads when
the pack fills so the trace keeps producing real swings rather than a run of
`full`.

Set it back to `False` for normal running.

## Tests

```bash
python tests/test_tame_animals.py
python tests/test_harvest_runner.py
python tests/sim_harvest_runner.py        # -v for every script log line
```

Both run under normal CPython 3 — no client, no Razor. Each loads the real script
with stub Razor globals and calls the actual functions, so the tests cannot drift
from the implementation.

- `test_tame_animals.py` — 43 checks: species matching, the live deed tooltip,
  container ownership, catalogue invariants.
- `sim_harvest_runner.py` — a **full-loop simulation**. Builds a fake world (paged
  runebook, a pack that fills, a wood key, trees that run out) and runs the real
  `run_job()` end to end for both jobs. Covers: each job working all 9 runes, the
  wood key carried vs at the house, two jobs rotating over two laps, a hostile
  permanently in range, and the diagnostic mode itself. Where the unit tests
  check functions in isolation, this checks that a job actually *finishes its
  route*.
- `test_harvest_runner.py` — 79 checks against a fake runebook whose pages are the
  verbatim text captured from the Gump Inspector, plus a fake journal fed the
  real `System: <Public> Fred Kruger: ...` line format. Covers page parsing,
  folder/rune discrimination, cross-page folder lookup, `goNext` visiting all 12
  runes across 3 pages before wrapping, chat-line parsing, case-insensitive
  call-out matching, any-caller-triggers behaviour, single-fire per chant, and
  vendor-table validation.
- `test_resource_order_runner.py` — 41 checks on the filler: hue-keyed stock,
  the per-metal reserve, row/button pairing including the amt-0 row that opens
  every page, deed tooltip parsing, and the config values that go live.
- `test_resource_orders.py` — checks on the resource-order groundwork: deed
  tooltip de-concatenation and field parsing, the ingot census (split stacks
  summed before the reserve, custom graphics, tooltip-as-name fallback), the
  fill budget, and gump row/button pairing by Y coordinate including a row that
  renders fewer cells than its neighbours.
- `test_extract_re_api.py` — 9 checks on the API extractor in `tools/`, one per
  C# declaration shape that an earlier version of the parser silently dropped
  (nested class with the brace on the next line, `public static int Hits { get`,
  `= new()` field initialisers, single-line method bodies, instance methods).

## Reference

- **[Harvest & taming handoff](docs/harvest-and-taming-handoff.md)** — current
  state, unmerged live config, confirmed shard facts, open items.
- [Account Runebook gump](docs/account-runebook-gump.md) — `[ar` protocol: page
  buttons, page structure, folder vs rune, entry/button pairing.
- [Resource Order Book gump](docs/resource-order-book-gump.md) — both gumps
  mapped button by button, the row-button numbering across pages, the ore
  hue table, and the Razor Enhanced empty-string bug that shifts gump text ids.
- [Tameable animals](docs/tameable-animals.md) — 112 species, body values, min
  taming skill, and the 15 body collisions.
- [API cheatsheet](docs/razor-enhanced-api-cheatsheet.md) — the calls these
  scripts use, with the shard-specific caveats, for `Mobiles`, `Player`,
  `Journal`, `Target`, `Items`, `Misc`, `PathFinding`, `Gumps`, `Spells`,
  `Timer` and `Statics`.
- [Generated API reference](docs/api-reference-generated.md) — the **complete**
  surface: 68 classes, every overload, extracted from the Razor Enhanced C#
  source at tag `v1.0.0.14`. Ground truth when a signature is in doubt.
- [Animal taming messages](docs/animal-taming-messages.md) — cliloc table and
  range rules.
- [Official Razor Enhanced API docs](https://razorenhanced.github.io/doc/api/) —
  built from 1.0.0.11, so it lags the current release, but the API has not moved
  since; good for the prose descriptions. The older
  `razorenhanced.readthedocs.io` is stale enough to be misleading — avoid it.

## Keeping the API reference current

Razor Enhanced has a history of changing signatures between builds, which breaks
scripts with no edits. The reference is regenerated from source rather than
transcribed:

```bash
git clone --depth 1 --filter=blob:none --sparse --branch v1.0.0.14 https://github.com/RazorEnhanced/RazorEnhanced.git RE
```

```bash
git -C RE sparse-checkout set Razor/RazorEnhanced
```

```bash
RE_TAG=v1.0.0.14 python tools/extract_re_api.py RE/Razor/RazorEnhanced docs/api-reference-generated.md
```

The installed build is whatever version folder exists under
`%LOCALAPPDATA%\www.razorenhanced.net\RazorEnhanced.exe_Url_*\` — currently
**1.0.0.12**, whose API is identical to 1.0.0.14.
