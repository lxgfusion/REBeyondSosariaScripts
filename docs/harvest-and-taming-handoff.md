# Harvest runner & animal tamer — handoff

State as of **2026-08-06**. `CLAUDE.md` carries the project conventions and the
Razor Enhanced API gotchas and loads automatically — this file is only the state
of *these two tasks*.

Sibling doc: `docs/resource-order-handoff.md` covers the separate
`resource_order_runner.py` work, which this session did not touch.

---

## 1. Where everything lives

There are **two separate Razor installs**, and scripts are split across them.
This has already bitten once: a fix was made in the repo, the user asked "was
that my `TameAndFill.py`?", and the answer was no — the tester had been running
the unfixed copy for days.

| Install | Deployed scripts |
|---|---|
| `E:\uoclients\RazorEnhanced\Scripts\` | `TameAndFill.py`, `resource_order_runner.py`, `COVFarm.py`, most `diag_*.py` |
| `E:\uoclients\UOAlive_Package\razor\Scripts\` | `harvest_runner.py`, `diag_ar_gump.py`, `diag_vendors.py` |
| `E:\uoclients\UOAlive_Package\razor\Scripts\Mystic Gatherer\` | `harvest_runner.py`, `diag_bods.py` |

Repo is `G:\programming projects\Razor Enhanced Scripts\`.

**The `diag_*.py` diagnostics are no longer in the repo** (removed
2026-08-06 to keep it to the scripts people actually run). They still exist
in the live Razor folders above, and every version of them is recoverable
from git history — `git log --diff-filter=D --name-only` finds them.

**Always check drift before claiming a fix is live:**

```bash
diff --strip-trailing-cr Scripts/harvest_runner.py \
  "E:/uoclients/UOAlive_Package/razor/Scripts/Mystic Gatherer/harvest_runner.py"
```

Deployed copies use **CRLF**; the repo uses LF, so always pass
`--strip-trailing-cr` or the whole file reads as changed.

### Sync status at handoff

| Repo file | Deployed | Drift |
|---|---|---|
| `TameAndFill.py` | `RazorEnhanced\TameAndFill.py` | **in sync** (synced 2026-08-06, `.bak-before-zombie-fix` kept) |
| `resource_order_runner.py` | `RazorEnhanced\` | in sync |
| `diag_bods.py` | `Mystic Gatherer\` | in sync |
| `harvest_runner.py` | `Mystic Gatherer\` | **repo is now AHEAD — live lacks the §2c/§2d fixes.** Also `WOOD_STORAGE_SERIAL`, which is per character and correct (§2e) |
| `harvest_runner.py` | `razor\Scripts\` | **repo is now AHEAD — live lacks the §2c/§2d fixes** |

As of 2026-08-06 the two deployed copies are identical to each other except for
`WOOD_STORAGE_SERIAL`. The `Mystic Gatherer` copy no longer has Lumberjacking
disabled — `CLAUDE.md` still says it does, which is now stale.

---

## 2. Live config — MERGED 2026-08-06

**Done.** The repo copy now carries everything below, with §2c and §2d fixed.
The sections are kept because they record *why* the config looks as it does.

**The deployed copies still carry the two bugs** — the merge went live → repo
only, which is the direction `CLAUDE.md` mandates. Deploying repo → live is a
separate, deliberate step and has not been taken. Until it is, the deployed
carpenter rune is still dead and still duplicated.

The user hand-edits the deployed `harvest_runner.py`. Both deployed copies carry
config the repo does **not**, and one contains a bug. **Pull these into the repo
before doing anything else, or the next sync will destroy them.**

### 2a. A confirmed Carpenter NPC the repo lacks

```python
# Inspected: name "Mallory", tooltip "Carpenter" / "Quest Giver".
{
    "enabled": True,
    "label":   "Carpenter",
    "folder":  ['BOD'],
    "point":   'carpenter',          # rune at 1479, 1790
    "names":   ["Carpenter"],
    "context": ["Bulk Order Info"],  # note: no "Talk" fallback
    "gump":    None,                 # note: opens NO gump
},
```

Two things worth keeping: the context list is `["Bulk Order Info"]` only, and
`gump` is `None` — so this NPC does **not** open a bulk order window, unlike the
smith and scribe. Verify that is intentional before "fixing" it.

### 2b. New runes, enabled live

```python
{"enabled": True, "label": "Tailor rune",    "point": 'Tailor',    "who": ["tailor"]},
{"enabled": True, "label": "Tinker rune",    "point": 'tinker',    "who": ["tinker"]},     # 1434, 1659
{"enabled": True, "label": "Carpenter rune", "point": 'carpenter', "who": ["Carpenter"]},  # BUG
```

### 2c. BUG in the live config — `"who": ["Carpenter"]`

`BOD_PROFESSIONS` keys are **lowercase**: `blacksmith, carpenter, scribe,
tailor, tinker`. The live entry uses `"Carpenter"` with a capital C, so
`expand_bod_locations()` will log *"lists unknown profession 'Carpenter'"* and
that location will do nothing. Fix to `["carpenter"]`.

Either fix the lookup to be case-insensitive, or fix the config — but do one.

**Fixed in the repo** — the `BOD_LOCATIONS` entry now reads `["carpenter"]`.
Reproduced first, to be sure the diagnosis was right: with the live entry
restored, `expand_bod_locations()` logs

```
BOD location Carpenter rune lists unknown profession 'Carpenter'.
Known: blacksmith, carpenter, scribe, tailor, tinker
```

and yields **zero** entries for that rune. The lookup was left case-sensitive;
only the config was changed, per the "do one" note above.

### 2d. Duplicate carpenter

Carpenter now appears **twice**: once as a `VENDORS` entry (2a) and once as a
`BOD_LOCATIONS` entry (2b). Both point at rune `carpenter`. They will be grouped
into one stop by `vendor_stops()` so the travel is not doubled, but the NPC will
be asked twice per round. Decide which one to keep — the `VENDORS` entry is the
one with inspected data.

**Resolved in the repo: the `VENDORS` entry won.** The `BOD_LOCATIONS`
"Carpenter rune" entry is kept but `"enabled": False`, per the convention of
parking config rather than deleting it, and its casing is already corrected so
it works if flipped on.

**The two bugs were interlocked, which matters.** The capital-C bug was *masking*
the duplicate: because `"Carpenter"` resolved to nothing, the rune produced no
vendor entry, so Mallory was only ever asked once. Fixing the casing **alone**
would have activated the duplicate and started asking Mallory twice per round
against a single 3-per-6-hours budget — turning a dead stop into a wasted one.
They had to be fixed together.

Verified after the merge, by running the real `all_vendors()` / `vendor_stops()`:
no unknown-profession log, carpenter appears exactly once, and no stop asks one
profession twice. Six stops, one travel each.

### 2f. Open question on the carpenter — needs an in-game check

The merged `VENDORS` entry keeps the live `"gump": None`, meaning the carpenter
opens no window at all. That is **not verified**, and it is the asymmetric one:

- If `None` is wrong, `answer_vendor_gump()` returns `True` without answering,
  so the round is logged as **"collected"** when nothing was collected — and the
  window is left open for the next vendor to trip over, since `gump_ids()`
  returns `[]` so `clear_stale_gumps()` has nothing to close.
- If a gump list is wrong, the script merely waits, logs loudly, and retries.

So the failure mode of `None` is silent and the failure mode of a list is noisy.
Confirm with the Enhanced Gump Inspector on Mallory: if a bulk order window does
open, change it to `[(0x9BADE6EA, 1), (0xBE0DAD1E, 1)]`.

### 2e. `WOOD_STORAGE_SERIAL` differs per character

- repo: `0x4290200A`
- `Mystic Gatherer`: `0x4247B87B`

This is **correct** — each character carries their own wood storage. Do not
"unify" it. Better fix: make it auto-detect by graphic the way the Bulk Order
Book already does (`BOD_BOOK_SERIAL = 0` + `BOD_BOOK_ID`), which removes the
per-character edit entirely. **Not yet done.**

---

## 3. `harvest_runner.py` — mining + lumberjacking

Merged from two Cral scripts (mining, lumberjacking) that the user had modified.
2995 lines. Runs both jobs from one script.

### Structure

- `JOBS` — a job is a runebook folder + a task (`"mine"` / `"lumber"`).
- `run_job(job, resume=False)` works a job's **entire rune route**; unloading
  happens *inside* it, so a trip home does not end the job.
- `JOB_ROTATION = "route"` — hand over only when the whole route is done.
- `vendor_stops()` groups vendors by rune so a location is travelled to **once**.
- `BOD_PROFESSIONS` × `BOD_LOCATIONS` expands into vendor entries; `"who": "*"`
  means "ask whoever is at this rune", absent professions skipped quietly.
- Per-vendor request budgets so the 30-minute round does not hammer NPCs that
  refresh every 6 hours.

### Confirmed shard facts (do not re-derive)

**Account runebook `[ar`** — gump `0xc395adb4`, server-side paging:

| Button | Action |
|---|---|
| `504` | next page |
| `503` | previous page |
| `5` | back to root |
| `0` | close (what a right-click sends — never send it) |

Nine entries per page, `Page X/Y` in the last text line. Entry buttons start at
`10`. A **rune is followed by a coordinate line; a folder is not** — that is the
discriminator. Full protocol in `docs/account-runebook-gump.md`.

**Vendors** — the title is in the **tooltip**, not the name:

| NPC | Name | Tooltip | Rune | Coords |
|---|---|---|---|---|
| Resource Gatherer | `Davin the Resource Gatherer` | *(none)* | `RO` / `RO` | 1413, 1720 |
| Animal Trainer | `Sherri` | `Animal Trainer`, `Quest Giver` | `BOD` / `tameinscribe` | 1481, 1789 |
| Scribe | `Edie` | `Scribe` | `BOD` / `tameinscribe` | 1477, 1792 |
| Blacksmith | `Cara` (0x00099CA5) | `Blacksmith` | `BOD` / `Blacksmith` | 1417, 1549 |
| Carpenter | `Mallory` | `Carpenter`, `Quest Giver` | `BOD` / `carpenter` | 1479, 1790 |

`BOD` folder runes seen in `[ar`: `Tailor` (1470, 1688), `Blacksmith`
(1418, 1548), `tameinscribe` (1479, 1790), plus `tinker` (1434, 1659) and
`carpenter` added live.

**Bulk order gumps** — small `0x9BADE6EA`, large `0xBE0DAD1E`, both button `1`.
That is why `gump` is a *list*.

**Rate limits (Beyond Sosaria)** — 3 orders per profession per 360 min;
resource gatherer 1 per 30 min. The NPC states the wait
(`An offer may be available in about N minutes`) and `parse_reported_wait()`
believes it in preference to the hardcoded default.

**Order books** — taming `0x4057CC3A`, resource `0x404AC332`. Emptied with the
same `Refill from stock` context entry every key uses; both open gump
`0x06ABCE12`. **No amount is ever sent** — the recorded macro ended with
`SendAdvancedAction(..., ["100"])` but that field is for *withdrawing*.

**Bulk Order Book** — graphic `0x2259`, auto-detected in the pack. Deeds are
graphic `0x2258` — **the same graphic as "A Taming Order"**, so filing runs after
`HOUSE_DEPOSITS` has taken the taming/resource orders out.

**Wood storage** — graphic `0x1BD9` hue `0x0058`. A carried one empties on the
spot with no trip home.

**Lumberjacking** — server `MaxRange` is **2 tiles**, so a rune must land within
2 of a tree. Success line on this shard is
`You chop some ordinary logs and put them into your backpack.`

### Diagnostics

- `DIAGNOSTIC_MODE = True` in `harvest_runner.py` — walks every job's whole
  route, one swing per rune, prints what the server replied, writes
  `%TEMP%\harvest_diag.txt`. **Set back to `False` after.**
- `diag_bods.py` — travels every BOD stop, lists NPCs with titles and distances,
  reports which gump opened. `ANSWER_GUMP = False` costs nothing from the
  3-per-6-hours budget.
- `diag_ar_gump.py`, `diag_vendors.py`, `diag_journal.py`.

---

## 4. `TameAndFill.py` (deployed as `TameAndFill.py`)

Reads taming order deeds in the pack, hunts **only** those species, tames them,
puts each in its deed.

### The zombie bug — fixed 2026-08-06, verify it holds

Reported: hunting boars, the script targeted **zombies**. Root cause was mine —
the ServUO extractor's regex `Body\s*=\s*([^;]+);` also matched a **comparison**:

```csharp
return (Body == 0xCF ? 3 : 0);     // Sheep.cs
```

so body `3` — **the zombie** — was recorded as a sheep body. Two entries were
corrupted; both fixed:

| Species | Was | Now |
|---|---|---|
| sheep | `[0x3, 0xCF, 0xDF]` | `[0xCF, 0xDF]` |
| wild tiger | `[0x4E7]` | `[0x4E6, 0x4E7]` (a ternary in `base(...)` hid one) |

**The structural fix matters more than the data fix.** Body values are now a
*pre-filter only* — `identify()` reads the creature's **name** and requires it to
match the species before targeting anything, and refuses when the name will not
load (`REQUIRE_NAME_MATCH = True`). Plus a `NEVER_TAME_WORDS` backstop.

If regenerating the catalogue, use `(?<![=!<>])=(?!=)` and sanity-check: no
undeclared shared bodies, nothing below ~`0x10`.

### "It ignores cats and chickens" — UNREPRODUCED, 2026-08-06

Reported, then withdrawn ("mine seems to be working fine as is right now").
`diag_tame_candidates.py` dumps taken beside a cat and a chicken show the path
is **healthy**, so there is nothing outstanding here:

| Checked | Result |
|---|---|
| Bodies | cat `0xC9`, chicken `0xD0` — **match the catalogue** |
| Deeds | `A Taming Order -> cat [0/30]`, `-> chicken [0/40]` — both parse |
| Ignore list | hiding nothing |
| Skill / followers | 148.0, 0/5 |
| Verdict | **"WOULD BE TAMED. Nothing in the config blocks this one."** |

Do not go looking for a body-value fix here — the bodies were verified correct
in game. If it recurs, section 5 of the diagnostic is the next cut: it runs the
real `Mobiles.Filter` with `Bodies` set, which is the only structural difference
between the diagnostic and `find_candidates()`.

### `NEVER_TAME_WORDS` matches inside words — real, latent

The same dumps caught `Vela the sorceress -> IGNORED: matched 'orc'`, because
`is_never_tameable()` used a bare substring test and "orc" sits inside
"s-orc-eress". Fixed in `diag_tame_candidates.py` by anchoring only the START of
the word (`\borc` still blocks "orcish" and "orcs").

**`TameAndFill.py` / `TameAndFill.py` still carry the substring version.** Left
alone deliberately: the guard only ever runs on creatures already matching a
catalogue body, and no catalogue species name contains a NEVER word mid-word —
verified by script over all 112 — so the practical impact today is zero. Worth
folding in next time that file is opened for another reason.

### Deed format (from Item Inspector)

```
Name: A Taming Order   ItemID: 0x2258   Root Container: 0x41D40F58 (the backpack)
Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:
```

Two traps, both handled: **properties arrive concatenated** (`KirinFilled`), so
text is de-camelCased before matching; and **`RootContainer` reports the
backpack's item serial**, not `Player.Serial`, so `is_held()` accepts either and
walks the chain.

---

## 5. Testing

```bash
cd "G:\programming projects\Razor Enhanced Scripts"
python tests/test_harvest_runner.py      # 229 checks
python tests/test_tame_animals.py        #  68 checks
python tests/sim_harvest_runner.py       #  65 checks, -v for full log
```

All suites green at handoff, including the other tasks'
(`test_resource_order_runner.py`, `test_covfarm.py`,
`test_petcommandcenter2.py`, `test_extract_re_api.py`).

The suites for the `diag_*` scripts went with those scripts when the repo
was pruned on 2026-08-06.

Tests `exec` the **real script** with stub Razor globals, so there is no copied
logic to drift. `sim_harvest_runner.py` is a full-loop simulation — fake paged
runebook, a pack that fills, trees that run out — and runs the real `run_job()`
end to end. **It proved the job logic correct while the bug was elsewhere**,
which is exactly what it is for.

---

## 6. Open items

1. ~~Merge §2~~ — **done 2026-08-06.**
2. ~~Fix `"who": ["Carpenter"]`~~ — **done**, see §2c.
3. ~~Resolve the duplicate carpenter~~ — **done**, see §2d.
3a. **Deploy the merged repo copy back to the two live folders.** Not done —
   live still has both bugs. Diff first (`--strip-trailing-cr`); the only
   intended difference is `WOOD_STORAGE_SERIAL`, which is per character (§2e).
3b. **Confirm whether the carpenter opens a gump** (§2f) — the one merged value
   that is unverified, and the one whose wrong answer fails silently.
4. **Auto-detect `WOOD_STORAGE_SERIAL`** by graphic, as the BOD book already
   does — removes the last per-character edit.
5. **Unverified profession titles**: `tailor`, `tinker` are guesses;
   `carpenter` is now confirmed as `Mallory` / `Carpenter`. Mobile-Inspect the
   tailor (1470, 1688) and tinker (1434, 1659), or let `diag_bods.py` report.
6. **Never confirmed in-game**: the Greyskull → Arcane Circle path. `Arcane` is
   entry 10 on **root page 2**, so it was unreachable before paging was fixed.
7. **Other scripts may carry the same animal catalogue** — `resource_order_runner.py`
   and others were never checked for the stray `0x3`. Worth a grep.
8. **`mining_runner.py` is the superseded fallback.** Delete once
   `harvest_runner.py` is trusted; it still has the old, buggy vendor matching.
9. **Optional**: cross-check the 112-species catalogue against
    <https://uo.com/wiki/ultima-online-wiki/skills/animal-taming/tameable-creatures/>
    (user supplied). ServUO source is authoritative for a freeshard, but the
    wiki may catch a divergence.

---

## 7. How this project works best

The pattern that has actually found bugs, repeatedly:

1. The user reports a symptom in plain terms.
2. **Ask for the Razor inspector dump** — Enhanced Item / Mobile / Gump
   Inspector. Every real root cause this session came from one, and several of
   my confident hypotheses were wrong until the dump arrived.
3. Reproduce offline in the sim or a unit test.
4. Fix, add a regression test naming the symptom.
5. **Deploy and verify the deployed file**, not the repo one.

Guesses that were wrong and cost a round trip: "the deed step is broken" (it was
a leaked target cursor), "no axe" (it was an unbounded hostile filter), "the
route logic is broken" (the sim proved it correct; it was a pack-weight
hand-off). Ask for the dump early.
