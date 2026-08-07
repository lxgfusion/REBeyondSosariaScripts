# Razor Enhanced Scripts

Scripts for the Razor Enhanced assistant for Ultima Online.

## Environment

- **Runtime:** Razor Enhanced's embedded IronPython **3.4** (Python 3.4 syntax +
  f-strings backported from 3.6). No pip, no CPython C extensions.
- **Available stdlib:** the IronPython 3.4 stdlib (`time`, `math`, `re`, `json`,
  `random`, ...). `.NET` types are reachable via `from System... import ...`.
- **Shard target:** a RunUO/ServUO-derived freeshard. Server message strings in
  scripts are taken from ServUO `Scripts/Skills/*.cs` — see `docs/`.
- **API reference:** https://razorenhanced.readthedocs.io/api/index.html

## Resource order runner — current state

Read [`docs/resource-order-handoff.md`](docs/resource-order-handoff.md) before
touching `resource_order_runner.py`. It carries the version history, what is in
`.snapshots/`, the open Copper Ingots issue and its one-line fix, and the config
values the user tunes and that must not be overwritten.

## Where the scripts actually run

**Live folder: `E:\uoclients\RazorEnhanced\Scripts\`** — that is what Razor
loads. `Scripts/` in this repo is the source of truth for history and tests; the
two must be kept in step.

- **Edit the live file, then mirror it back here.** Editing only the repo copy
  cost two full debugging rounds on a bug that was already fixed on disk but not
  in the folder Razor reads.
- **Never blind-copy repo → live.** The live copy carries the user's own tuning
  (`MAX_ORDERS_PER_RUN` was 15 there against 5 here). Diff first; if the only
  differences are config values, mirror live → repo instead.
- **Every script prints a `SCRIPT_VERSION` banner on its first log line.** Bump
  it with each change that goes out. If the journal does not show the expected
  version, Razor is running an old copy — Reload in the Scripting tab, since it
  caches the loaded script even after the file changes.
- The path has moved before (it was `G:\uoclients\...`). If it is missing,
  find it from the title bar of the Razor script window rather than guessing.

### There are TWO script roots

| Script | Live location |
|---|---|
| `resource_order_runner.py`, `diag_resource_orders.py` | `E:\uoclients\RazorEnhanced\Scripts\` |
| `harvest_runner.py` | `E:\uoclients\UOAlive_Package\razor\Scripts\` |
| `tame_animals.py` | not deployed — repo only |

So "the live folder" depends on which script is being edited.

**`harvest_runner.py` is user-managed — do not sync or edit it unasked.** It
exists in four diverging copies on purpose:

- `…\razor\Scripts\harvest_runner.py` — main character, lumberjacking on.
- `…\Scripts\Mystic Gatherer\` — same version, `"enabled": False` on the
  Lumberjacking job. Those characters do not lumberjack yet.
- `…\Scripts\MrGatherer\` — lumberjacking off, but ~900 lines behind the others.
- The repo copy is behind the deployed main by a Carpenter vendor stop and the
  Tailor/Tinker/Carpenter rune entries.

Those differences are work in progress as of 2026-07-28, not drift to be
reconciled. Ask before touching any of them.

## Conventions

- **One file per script, self-contained.** Razor Enhanced runs each `.py` from
  its Scripts folder; cross-file imports need `sys.path` surgery and break when
  users move files. Duplicate a helper rather than build a shared package.
- **Don't delete unreferenced config as "dead".** `TAMING_BOOK` and `RO_BOOK`
  were unused constants in the original mining script and were removed during a
  merge; they turned out to be the serials for the order-book deposits added
  later. Unreferenced shard-specific serials are usually notes-to-self, not
  cruft. Move them to a clearly-marked "not wired up yet" section instead.
- **Put all tunables in a `CONFIG` block at the top**, with units in the name or
  comment (`_MS` suffix for milliseconds). Order the block by how likely the user
  is to edit it — the shard-specific table they must fill in goes **first**, under
  a banner, not buried under timings. Keep such entries self-contained (inline
  the folder/name strings) rather than referencing constants declared elsewhere.
- **Validate user-supplied config at startup and print what was loaded.** A table
  entry missing a required field should be named and skipped loudly. Silent
  no-ops in a config-driven loop are near-impossible to diagnose from in-game.
- **Server message strings live in their own block**, annotated with the cliloc
  number they came from, so they can be checked against shard source.
- **`Journal.Clear()` before any action whose result you read from the journal.**
  `Journal.Search` scans the whole buffer, so stale lines cause false positives.
  Say so in the script docstring — it wipes the user's journal.
- **For passive triggers, use a timestamp cursor, not `Search` + `Clear`.**
  `Journal.GetJournalEntry(cursor)` returns only new lines: one event fires once,
  pre-startup lines are ignored, matching can be case-insensitive, and other
  features' journal state is left alone. Reserve `Search`/`Clear` for
  "I just did X, what happened".
- **Player-typed trigger phrases must match case-insensitively.** A phrase a human
  types into chat will vary in capitalisation and punctuation every time.
- **Chat lines carry the speaker inside the text.** Global chat arrives as
  `System: <Public> Fred Kruger: ...` — `entry.Name` is `System`, not the caller.
  Parse channel and speaker out of the text; never filter callers on `entry.Name`.
- **Split detection from response for anything triggered mid-loop.** A responder
  that travels cannot be called from inside travel waits. Have a `poll_*` that
  only raises a flag (safe anywhere, including long pauses) and act on the flag
  at a safe point. Any pause longer than ~1s in a script with passive triggers
  should be an interruptible pause that polls, or the trigger is simply missed.
- **Never busy-wait.** Every polling loop gets a `Misc.Pause` and a wall-clock
  deadline via `time.time()`.
- **Prompt for item serials, don't hardcode item IDs.** Custom shard items vary;
  `Target.PromptTarget` once at startup is more portable than a graphic ID.
- **Use `Misc.IgnoreObject`** to blacklist mobiles/items already ruled out, and
  document that `Misc.ClearIgnore()` resets it.

## Verified API gotchas

- **Check a signature against the generated reference before writing the call.**
  [`docs/api-reference-generated.md`](docs/api-reference-generated.md) is the
  complete API surface extracted from the Razor Enhanced C# source at tag
  `v1.0.0.14`, by `tools/extract_re_api.py`. That is ground truth. The
  hand-written [`docs/razor-enhanced-api-cheatsheet.md`](docs/razor-enhanced-api-cheatsheet.md)
  covers what these scripts use, with the shard-specific caveats.
- **The build that matters here is 1.0.0.12** (installed under
  `%LOCALAPPDATA%\www.razorenhanced.net\RazorEnhanced.exe_Url_*\`). Its API is
  byte-identical to 1.0.0.11, 1.0.0.13 and 1.0.0.14 — verified by generating the
  reference at each tag and diffing. Regenerate when the user updates.
- **Razor Enhanced changes signatures between builds, and a working script just
  stops.** When a previously working script breaks with no edits, **check
  signatures first**, and prefer a `try/except TypeError` shim over picking one
  form. But verify which form is current before assuming: `Player.Run` takes
  **one** argument (`Run(direction)`) on every build from `0.8.2.245` to
  `1.0.0.14` — the two-argument `Run(direction, checkPosition)` is the *old*
  form, not the new one, and an earlier version of this file had that backwards.
  `Player.ChatSay` accepts both `(msg)` and `(colour, msg)` on all those builds;
  `Gumps.GetLineList(gumpId, dataOnly=False)` has had the second argument
  throughout.
- **`readthedocs.io` is stale** — it is missing `GetGumpRawLayout`,
  `GetLineList`, `HasGump(gumpid)` and others. Don't use it.
  `https://razorenhanced.github.io/doc/api/` is built from 1.0.0.11 and so lags
  the current release, but nothing in the API has moved since, so it is accurate;
  use it for the prose descriptions the generated reference doesn't carry.
- **Always set `RangeMax` on a `Mobiles.Filter`.** Unset means everything the
  client knows about, roughly 18-25 tiles. A "is anything hostile near me" check
  without it is permanently true wherever spawns wander, and whatever it guards
  never runs. Same for any filter used as a yes/no condition.
- `Mobiles.Filter().Name` is an **exact** match, not a substring. Any script that
  finds NPCs by name breaks the moment the shard renames one, and it fails
  silently — the filter just returns an empty list. Match names yourself,
  case-insensitively, and log misses.
- **An NPC's title lives in its tooltip, not its name.** `Mobiles.GetPropStringList`
  on the NPC named `Sherri` returns `Animal Trainer`; `Edie` returns `Scribe`.
  Match vendors on the **title**, not the given name — names get changed by the
  shard, titles rarely do. Check `Name` first (cheap) and fall back to
  `WaitForProps` + `GetPropStringList`. Same shape as the deed-tooltip lesson:
  **whenever a lookup by name fails, check the tooltip before anything else.**
- When an entity lookup fails, dump every candidate in range *with its tooltip*
  into the log. A failure that says only "not found" costs a whole extra
  test-and-report round trip with the user.
- **Context menus are dangerous to substring-match.** A vendor's menu carries
  `Buy`, `Sell`, `Bribe`, `Open Bankbox` and `Train <skill>` right next to the
  entry you want, and every one of those spends gold. Try an **exact** label
  match first (always honour it — it was configured deliberately), then fall
  back to substring while refusing a `CONTEXT_NEVER` blocklist. Send the real
  label back to `ContextReply`, never the search string.
- **Never guess a button id in a runebook or other consequential gump.** Clicking
  an unknown button can recall the character or spend a charge. Leave such config
  empty by default, ship a diagnostic that reads the layout instead, and make any
  click-probe opt-in. The right source of truth is Razor's **Enhanced Gump
  Inspector** — its response log shows the exact button id for each click the
  user makes, which beats probing entirely. Ask for that before writing a probe.
- **Gump paging may be server-side.** A gump whose pages arrive as fresh gumps
  (same gump id, new sequence) has to be walked with real clicks; only
  `{ page N }` markers in the raw layout mean the pages are already in hand. Any
  parser that reads "the gump" sees one page, so lookups silently miss anything
  further in. See `docs/account-runebook-gump.md`.
- **Never index `Gumps.GetLineList` by the text id in the raw layout.** Razor
  Enhanced drops empty strings out of a gump's string table *without leaving a
  gap*, so one blank cell shifts every later index down by one. Confirmed in
  `Razor/Network/Handlers.cs` at `v1.0.0.14`: the read loop only does `x1++`
  when `len > 0`, so the empty slot it just wrote is overwritten by the next
  string. `GetResolvedStringPieces` indexes the same table and inherits the
  fault. Pair by **element order** instead — `GetLineList` returns one entry per
  `text`/`croppedtext` element in layout order (not `textentry`, whose initial
  value is usually the blank that got eaten). Symptom: text from the end of one
  row appears at the start of the next, and ids past the end show as missing.
  The Resource Order Book loses nine strings a page — see
  `docs/resource-order-book-gump.md`.
- **Don't pair gump text to buttons by counting lines.** Match entries by their
  own pattern (`N. Name`) and zip them with the page's sorted entry buttons. That
  survives both per-page and continuous button numbering, and ignores
  non-entry lines like headers and action links.
- **`Gumps.WaitForGump` returns `True` for a gump that is already open** — the
  same trap as `Target.WaitForTarget`. Close or reset any expected gump id
  before the action that should open it, or a leftover window from the previous
  interaction gets answered instead. Symptom: an interaction that works most of
  the time and fails "randomly".
- **An interruption that the caller resumes from must not reset the callee's
  progress.** `run_job()` reset its waypoint on entry so a fresh lap started
  clean — but the main loop re-enters it after a vendor round or a Greyskull
  call, so every interruption sent the route back to rune 1. Take an explicit
  `resume` flag; do not infer "new run" from "function was called".
- **Shared resources hand over between phases.** Mining finished its route with
  225 of 297 usable stones still in the pack, and the wood storage only accepts
  wood — so lumberjacking started with two chops of headroom and spent its whole
  route in a full/unload cycle. When phases share a resource pool, reset it at
  the hand-off.
- **A rotation or hand-off condition must not be a side effect of resource
  limits.** Rotating jobs "after each drop-off" silently broke heavy-resource
  routes: wood filled the pack in one waypoint, so the job rotated away having
  visited one spot. Tie hand-off to *work completed* (a full lap of the route),
  and treat unloading as an interruption the job resumes from, not an exit.
- **Target cursors leak, and a leaked one silently eats the next
  `TargetExecute`.** `Target.WaitForTarget` returns `True` immediately for a
  cursor that is *already* open, so any code path that requests a target and
  then bails on timeout must `Target.Cancel()` before moving on. Symptom: a
  later, unrelated `UseItem` + `WaitForTarget` + `TargetExecute` appears to run
  correctly but the server never receives the target. Always route cursor setup
  through one helper that cancels, clears the queue, and asserts
  `not Target.HasTarget()`.
- `Items.UseItem(item, target)` — the docs explicitly warn the built-in target
  "may not work on some free shards." Prefer `UseItem` then `WaitForTarget` then
  `TargetExecute`. **Confirmed in-game** on this shard: the manual sequence works
  (cancel stale cursor → `UseItem` → `WaitForTarget` → ~400 ms settle →
  `TargetExecute(serial)`); the settle pause and the cursor cancel are both
  required. Don't refactor either away.

- `Player.Run(direction, checkPosition)` is the current signature; older builds
  only have `Player.Run(direction)`. Wrap in `try/except TypeError`.
- `PathFinding.Go` fails against a tile occupied by a mobile — path to an
  adjacent tile instead.
- **Skill-on-creature loops must stay adjacent, not merely in range.** The
  server's stated range limit (7 tiles for taming) is a hard cutoff, not a safe
  working distance — the same tick usually also checks line of sight, which a
  moving creature breaks first. Hold 1 tile and re-close on a short poll
  (~150 ms). Give the approach helper an `accept` fallback distance so it settles
  when terrain stops it a tile short instead of burning its whole timeout.
- UO directions: X grows **east**, Y grows **south**. `North`=(0,-1),
  `Right`=(+1,-1), `East`=(+1,0), `Down`=(+1,+1), `South`=(0,+1),
  `Left`=(-1,+1), `West`=(-1,0), `Up`=(-1,-1).
- `Misc.SendMessage(msg, color, wait)` is the safest overload — the two-arg form
  is ambiguous across numeric overloads.
- `Mobiles.Filter().Bodies` is a `List[Int32]`; use `.Add()` / `.AddRange()`.
- **`Item.Contains` is a snapshot, and it is the ONLY window into a container.**
  It is taken when the container is opened, so once items are spent, merged or
  restacked it goes stale and a changed item can drop out of the list — a
  container holding many stacks of one thing gets under-counted and any budget
  built from it is too low.
  **Asking a different way does not help.** `Items.FindAllByID(id, hue,
  container_serial, ...)` does *not* query the item index — it calls
  `FindBySerial(container)` and iterates that same `Contains` list
  (`Razor/RazorEnhanced/Item.cs`, `v1.0.0.14`). Unioning the two gives you the
  same opinion twice; an earlier version of this note wrongly recommended
  exactly that. Only `container == -1` goes through `ApplyFilter` over the world.
  **The fix is to re-open the container** (`UseItem` + `WaitForContents`) and
  re-read, retrying until `Contains` is non-empty.
  **This applies to `Player.Backpack.Contains` too**, and it is nastier there:
  a before/after diff of the pack is the usual way to prove an action produced
  an item, so a stale snapshot reads as "the action did nothing". That aborted
  the resource-order runner after exactly one order, every time.
- **Cap a loop on the action, not on the success.** The order runner capped on
  orders *completed*, so every deed that was declined or failed to fill cost
  nothing against the limit and it kept pulling — far past the configured
  maximum. Count the irreversible step.
- **Reopen a gump at the TOP of a loop, not the bottom.** Reopening at the
  bottom means one failed reopen ends the loop silently and whatever came
  before gets treated as the whole result. Check `has_gump` at the top, reopen
  if needed, and give every loop exit its own log line — a loop that ends for
  an unlogged reason is indistinguishable from one that finished its work.
- **Check `Container` / `Ground` before assuming where an item lives.** House
  storage is *locked down on the ground* — `Container: None`,
  `RootContainer: None`, `Ground: Yes` — so a backpack search never finds it.
  `Items.FindAllByID(id, hue, -1, range, False)` searches the world; passing
  `Player.Backpack.Serial` searches the pack. Prefer an exact serial when the
  thing never moves, with id/hue as a fallback for when it is replaced.
- `Items.Filter` has **no `Container` field**. Scope a search to the backpack
  with `OnGround = 0` plus an `is_held()` style check — **not**
  `item.RootContainer == Player.Serial`. On this shard `RootContainer` returns
  the *backpack's item serial* (`0x41D40F58`), not the player's mobile serial, so
  that comparison rejects everything you own. Accept either `Player.Serial` or
  `Player.Backpack.Serial`, and walk `item.Container` upward as a fallback for
  items in sub-bags. Verified against a live Item Inspector dump.
- **Tooltip properties arrive concatenated.** A real deed reads
  `Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:` — no separator
  between one property's value and the next property's label. Lowercasing that
  gives `kirinfilled`, so any regex ending in `\b` silently fails to match the
  species. Insert a space at each lower/digit → upper seam
  (`re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", raw)`) before matching. Prefer reading
  a named field (`Creature Type:`) over scanning the whole tooltip; the value
  ends where the next field's label begins.
- Colour is `Item.Hue` but `Mobile.Color`. War mode is `Mobile.WarMode`,
  `Player.WarMode`, and `Mobiles.Filter.Warmode` (lowercase m).

## Identifying creatures

**A body value must never be the sole authority for acting on a creature.** Use
it as a cheap pre-filter for `Mobiles.Filter`, then confirm with the creature's
**name** before targeting anything. Bodies are shared between species, reused by
shards, and — as happened here — can be plain wrong in extracted data. A stray
`0x3` in the sheep entry is the zombie body, and the script duly walked up to
zombies and tried to tame them.

If the name will not load, do nothing. A missed tame costs nothing.

## Shard data

Creature body values, taming skill requirements and server message strings come
from **ServUO source, not memory**. To regenerate or extend:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/ServUO/ServUO.git
git -C ServUO sparse-checkout set Scripts/Mobiles
```

Then grep for `Tamable = true` and pull the body from either a `Body = ...`
assignment or a `BaseMount` `base(name, body, mountItemID, AIType...)` argument.
Watch for `Body = Utility.RandomList(12, 59)` and ternaries — several species
have more than one body. Results live in `docs/tameable-animals.md`.

**Exclude `==` when matching assignments.** `Body\s*=\s*` also matches
`Body == 0xCF ? 3 : 0`, which injected body `3` (a zombie) into the sheep entry.
Use `(?<![=!<>])=(?!=)`. Likewise a ternary in a `base(...)` argument —
`base(name, RandomBool() ? 1254 : 1255, ...)` — is not a bare number and gets
missed; wild tiger lost body `0x4E6` that way.

After regenerating, sanity-check the result before trusting it: no two species
sharing a body unless declared, and no body below ~0x10 (those are humans and
undead, never tameable animals).

Note `Scripts/Services/Revamped Dungeons/...` has paths too long for Windows
checkout; sparse-checkout `Scripts/Mobiles` only.

## Matching shard text to game data

Deed tooltips and creature names are free text, so matching needs care:

- Build a regex per species where separators are flexible:
  `\bki[^a-z0-9]*rin\b` matches `ki-rin`, `ki rin` and `kirin`.
- **Sort candidates longest-name-first.** Otherwise `cat` claims `hell cat` and
  `horse` claims `dread warhorse`.
- Keep the `\b` anchors — without them `rat` matches inside `decorative`.
- Body values are **not unique**. 15 catalogue bodies are shared by two or more
  species (`0x74` is both nightmare and dread warhorse). Anything that acts on a
  species identity must name-verify those, and refuse to act when the name will
  not load.

## Merging scripts

When folding one script into another (they mostly come from the same author and
share infrastructure):

- **Keep the working detection logic of whatever already works.** Mining's
  journal matching is crude but proven; it was left untouched while
  lumberjacking got proper cliloc-verified messages. Record the verified strings
  in a comment for later rather than rewriting a working path.
- Make per-activity state (routes, waypoints) a dict keyed by job name. A single
  global works until there are two folders to walk.
- Where the two scripts solved the same problem differently, take the better one
  and keep the other as a fallback — e.g. find the "Contents" tooltip line by
  name, falling back to indexing line 2.
- Leave the superseded script in place until the merged one is confirmed
  in-game, and say so in the README.

## Testing

```bash
python tests/test_tame_animals.py
```

```bash
python tests/test_harvest_runner.py
```

```bash
python tests/test_extract_re_api.py
```

No Razor runtime needed. `tests/test_tame_animals.py` reads the script, strips
the trailing `main()` call, `exec`s it with stub `Misc`/`Player`/`Items` objects,
and calls the **real** functions — so there is no copied logic to drift. Add
coverage there rather than reimplementing parsing in the test.

Keep a regression assertion for every bug found in-game (e.g. "concatenated
tooltip text does not match", "old `RootContainer == Player.Serial` test fails").
Those two were silent failures — the script reported no deeds and looked healthy.

Beyond the tests, before handing a script over, re-read it for: unbounded loops,
missing `Misc.Pause`, journal reads without a preceding `Journal.Clear()`, and any
hardcoded serial or item ID.

There is no offline harness — scripts are verified in-client. Before handing a
script over, re-read it for: unbounded loops, missing `Misc.Pause`, journal
reads without a preceding `Journal.Clear()`, and any hardcoded serial or item ID.
