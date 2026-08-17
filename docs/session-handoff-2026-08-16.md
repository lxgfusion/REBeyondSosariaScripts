# Session handoff — 2026-08-16

State at the end of a long session. `CLAUDE.md` carries the conventions and the
API gotchas and loads automatically; this file is only what changed, what is
still unproven, and what to do next.

Everything below is **committed and pushed** — `main` is level with
`github.com/lxgfusion/REBeyondSosariaScripts`.

---

## THE ONE THING THAT MATTERS MOST

**Almost none of this session's work has been confirmed in game.** Four scripts
were changed, several of them substantially, and the only things actually
verified live are the diagnostics' own output. Before building anything new,
get a real run of each and read the first journal line for the version.

| Script | Version | Verified in game? |
|---|---|---|
| `resource_order_runner.py` | `2026-08-13.32` | **no** — Copper fix, board hues, scales, priorities, order collection, finished-order pull all unproven |
| `harvest_runner.py` | (no version marker) | **no** — smelt order, cursor leak, pack weight all unproven |
| `COVFarm.py` | `1.6.0` | chest binning worked at `1.2.0`; `CHEST_ACTION` and the master key path are **unproven** |
| `TameAndFill.py` | (no version marker) | **no** — peacemaking, threat detection, resistances all unproven |

Two of these have **no `SCRIPT_VERSION`**, against the project's own rule that
every script prints one on its first log line. Worth adding: without it there
is no way to tell which copy Razor actually loaded.

---

## resource_order_runner.py — `2026-08-13.32`

Live at `E:\uoclients\RazorEnhanced\Scripts\`, byte-identical to the repo.

### What was fixed, and how it was found

The **Copper Ingots** bug took four attempts and three wrong diagnoses. The
handoff at the time said the cause was "confirmed"; it was not. What actually
happened:

1. "The page cap is too low" — wrong. Copper collides, so the diluted branch
   already allowed 20 pages against a 9-page result.
2. "The budget is too low" — wrong. `diag_copper_stock.py` returned
   `THE CENSUS SEES IT: 31487 Copper`.
3. "It never gets a turn" — wrong. Simulating the real rotation put Copper in
   reach by lap 4 at worst.
4. **Right:** submitting a new Name filter does **not** reset the page. The
   runner never reopens the book between resources, so it started Copper's
   scan wherever the last resource stopped — and all 26 Copper orders are on
   pages 1–2 of 10. Fixed by `rewind_to_first_page()`.

The lesson is in `CLAUDE.md` terms: each of the three wrong answers explained
the symptom, and none was tested against the live gump until a diagnostic did
it. **Ship the diagnostic first.**

### Everything else added

- **Board hues.** All nine woods, confirmed from a live chest dump. 320,420
  boards came into stock at once. Eight name their wood on the stack's third
  tooltip line; `0x0000` carries no wood line at all, which is how the default
  wood renders — the same way plain iron is the one ingot with no third line.
- **Scale hues — INCOMPLETE, see below.**
- **`PRIORITY_RESOURCES`** — worked first every lap. `RESOURCES` is sorted by
  how many orders the book held when harvested, which says nothing about the
  chest: Iron Ingots sat at #78 of 79. The rotation offset advances by the
  rotated part only, or pinning two would starve two others.
- **Replacement orders.** Each hand-in clears the cooldown, so the runner
  Talks to the Gatherer after every deed, parks the new order in the loot bag
  (`0x42385515`), and deposits them with "Fill from backpack" at Start Fill.
- **Finished-order pull.** Filters the Completed column to `Yes` and takes 15
  a lap until none remain. Each withdrawal is checked against the deed itself.
- **Stray gumps and world saves.** `tidy_gumps()` at four points;
  `"The world will save in 30 seconds"` pauses it for 45s via a timestamp
  cursor.

### OPEN — scale hues, five still unknown

```python
SCALE_HUES = {
    "Green Scales":  0x0851,     # confirmed in game
    # "Yellow Scales": 0x0000,   # <- these five need matching by eye
    # "Blue Scales":   0x0000,
    # "Red Scales":    0x0000,
    # "White Scales":  0x0000,
    # "Black Scales":  0x0000,
}
```

The hues seen in the chest dump awaiting a colour: `0x0455`, `0x066D`,
`0x08A8`, `0x08FD` — plus `0x08AF` ("Medusa scales") and `0x08B0` ("sea
serpent scales"), which are their own creatures rather than dragon colours.

**How to fill it:** run the runner once. The stock report prints every scale
hue it does not recognise with a paste-ready line. Do NOT guess — pouring red
into a green order cannot be undone.

`Delicate Scales` is deliberately absent: that stack really is named "delicate
scales" and has its own graphic `0x573A`, so the plain name path already works.

### Watch for on the next run

- `PRIORITY Iron Ingots took nothing: N on hand, N spendable` — this line was
  added to settle whether Iron is a census problem or simply has no orders. The
  book held **1** Iron order at harvest time.
- `The Completed filter ('Yes' in filter box 4, the last column) did not narrow
  the list` — means the column mapping is wrong; the message names the box and
  the before/after counts.

---

## harvest_runner.py — four copies, all patched

| Copy | Path |
|---|---|
| repo (GitHub) | `Scripts/harvest_runner.py` |
| main character | `…\UOAlive_Package\razor\Scripts\` |
| MrGatherer | `…\razor\Scripts\MrGatherer\` |
| Mystic Gatherer | `…\razor\Scripts\Mystic Gatherer\` |

**`CLAUDE.md` is stale about these.** It says the repo copy is *behind* the
deployed main; it is now **ahead**, carrying the Carpenter vendor stop and the
Tailor/Tinker rune entries. It also says MrGatherer is ~900 lines behind; the
user has since made it identical to main.

**Live has `"Carpenter rune"` enabled with `"who": ["Carpenter"]`; the repo has
it disabled** (moved to `VENDORS`, casing corrected). That is why fixes were
applied **surgically to each live copy** rather than copied from the repo — a
straight copy would silently flip that config. Keep doing that.

### Three bugs fixed, one caused by another

1. **Smelt before the keys.** Ore is not what the keys take, so a full pack of
   ore was refused and carted home while the Ingot key sat unused. And
   `dropoff()` ran unconditionally after the smelt, so the character went home
   with a nearly empty pack every time. `unload_in_place()` fixes both.
2. **`smelt()` leaked a target cursor** — no `clear_cursor()` and no cancel on
   timeout. `WaitForTarget` returns True for a cursor that is already open, so
   a leftover one was answered instead and then ate the **mining tool's**
   target: the character stood there swinging at nothing, silently. Survivable
   while smelt only ran on key refusal; fix 1 made it run on every full pack.
   **This was a regression I introduced.**
3. **`pack_has_room()` weighed the wrong thing** and read "unknown" as "full".
   Weight came from the backpack tooltip — that is the *container's* capacity
   (`0/60000 Stones`), not what the character can lift. Now `Player.Weight /
   Player.MaxWeight` (81 of 495 on a 130-str character). It also read the
   tooltip without asking for properties, so mid-run it returned `None` and
   that became "full", reported through `debug()` and therefore silent.

Also: `dropoff()` smelts first (ore is in neither `PURGE_ID` nor any key, so it
stranded); resources whose key is in the pack are never swept into the one-way
chest (`KEY_BACKED_IDS`); the ingot key is configurable with **no pinned
serial** so one copy works for every character.

The repo copy additionally got a **configuration index** and 30 settings
documented. That is repo-only, by request.

### OPEN

- **Mystic Gatherer's `WOOD_STORAGE_SERIAL` is `0x4290200A`, the same as main's.**
  It used to be `0x4247B87B`, and that serial was the *only* per-character
  difference. Either set that character's own, or set it to `0` so the graphic
  lookup finds whichever key is in their pack — which is what the ingot key
  does and why it needs no per-character editing.
- No `SCRIPT_VERSION` in any copy.

---

## COVFarm.py — `1.6.0`

The reward chests took four attempts, and each failure taught something:

1. Pinned `0x09AB` — but the chests use **many** graphics. Level 1 alone
   appeared as `0x09AB/0x047E`, `0x0E7C/0x089F`, `0x0E40/0x0979`; Level 5 as
   `0x0E40/0x04F2`.
2. Required a `Level N` tooltip line — too narrow.
3. Excluded `0x0E41` to protect the order runner's storage chests — **and that
   blocked a real reward chest**, because reward chests use that graphic too.
4. Matched on name only, and it still failed: **`Item.Name` is empty until the
   properties are asked for**, so a name-only match skipped exactly the chest
   that had just dropped. Now matches name **and tooltip**, and re-opens the
   pack first because `Contains` is a snapshot.

`CHEST_ACTION` is now `"trash"` (deletes), `"key"` (hands to the master key,
destroys nothing) or `"keep"`. Printed at startup so a destructive setting is
never a surprise. Guards: backpack only, and both storage serials refused
outright.

`CAMP_POINT = (750, 475)` is fixed rather than wherever the script started.

### OPEN

- `CHEST_ACTION = "key"` has never been run. The master key menu labels are a
  guess ordered `["Fill from backpack", "Refill from stock"]` — if neither is
  on the menu it presses **nothing** and prints what the menu offered.
- There is a **`COVFarm2.py`** in the live folder, same size. Not touched.

---

## TameAndFill.py — peacemaking, threats, resistances

### Peacemaking (working, unproven)

Messages taken verbatim from ServUO `Scripts/Skills/Peacemaking.cs`. Each
outcome acted on differently: "no chance of calming" is permanent, "already
being calmed" counts as calm, a plain failure retries then **tames anyway**.

**The trap:** with no instrument the skill does nothing and the server sends
**no message at all**. Preflight says outright whether it will work.

`PEACE_WHEN = "aggressive"` plays only at `dragon`, `drake`, `wyvern`, `wyrm`,
`hiryu`. Unicorns and ki-rin are peaceful and are left alone. Anything already
in war mode is calmed whatever it is called.

### Threat detection — REPORT ONLY

UO has no "who is targeting me". Inferred the way a player does it: a creature
that has locked on **turns grey and moves towards you**.

Grey alone is worthless — the animal being tamed is grey, adjacent, and stays
that way for the whole attempt. So a threat must be **both** a hostile
notoriety **and** closing across successive checks, and the tame target is
excluded by serial.

**`THREAT_ATTACK` is `False` and there is no `Player.Attack` call anywhere in
the file.** A test asserts both. Detection ships first so it can be checked
against what is actually on screen.

### Resistances and spell choice

110 species from ServUO `Scripts/Mobiles` via `tools/extract_resistances.py`.
Midpoints of the declared ranges.

Two things the source settled that assumption got wrong:

- **A zero resistance is real, not missing.** ServUO only calls
  `SetResistance` for what a creature resists — a chicken declares Physical and
  nothing else. The first extractor required all five and silently dropped half
  the catalogue.
- **"Lowest resistance" is the wrong rule.** Base damage matters as much. A
  hiryu resists cold 20 and energy 45, so lowest-resistance says Harm — but
  Harm is base 17 against Energy Bolt's 40, so the bolt lands 22 where Harm
  lands 13.6. `best_spell_against()` maximises `base × (100 − resist)`, which
  picks Energy Bolt and matches what happens in game.

`SPELL_TABLE` covers Magery and Mysticism from `tools/extract_spells.py`.
**Absent rather than guessed:** Poison Strike, Wither (Necromancy), Wildfire,
Thunderstorm, Essence of Wind (Spellweaving), Earthquake (Magery) — their
damage is not a plain `GetNewAosDamage` call. That leaves **poison
undeliverable**, which matters: a dragon's lowest resistance is poison.

**Wildfire is SPELLWEAVING**, not Mysticism — `Scripts/Spells/Spellweaving/`.

`KILL_ON_SIGHT_WORDS = ["lesser hiryu"]` — no taming order exists for them, and
the catalogue confirms it from the other side. Note the substring trap:
`"lesser hiryu"` contains `"hiryu"`, so anything asking both questions must ask
kill-on-sight first. Nothing acts on this list yet.

---

## Removed from the repo

`buy_vendor_key.py` and its test, and `harvest_runner - Copy.py`. The vendor
script was **never run in game**; the live copy is kept at
`E:\uoclients\RazorEnhanced\Scripts\` deliberately for later. Restore both with:

```bash
git checkout e0fbc94^ -- Scripts/buy_vendor_key.py tests/test_buy_vendor_key.py
```

---

## Verifying

```bash
cd "G:/programming projects/Razor Enhanced Scripts"
for t in tests/test_*.py; do printf "%-40s " "$t"; python "$t" 2>&1 | tail -1; done
```

Six suites, all green at handoff. `test_resource_order_runner.py` is 523 checks.

Deploy targets differ per script — see the table in
`docs/harvest-and-taming-handoff.md`, and **diff before copying** anything into
`harvest_runner`'s three live copies.

---

## Next, in the order I would do it

1. **Run each script once and report back.** Nothing else is worth building on
   top of five unverified changes.
2. **Fill in the five scale hues** from the runner's own report.
3. **Add `SCRIPT_VERSION` to `harvest_runner.py` and `TameAndFill.py`**, and
   print it as the first log line.
4. **Check the threat-detection lines** against what is on screen, then wire
   the attack — Magery/Mysticism spells are already chosen correctly.
5. Fix Mystic Gatherer's `WOOD_STORAGE_SERIAL`.
6. Optional: measure Poison Strike so poison becomes deliverable, which would
   change the answer for dragons.
