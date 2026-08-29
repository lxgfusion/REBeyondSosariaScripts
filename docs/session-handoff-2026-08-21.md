# Session handoff — 2026-08-21

`CLAUDE.md` carries the conventions and API gotchas and loads automatically.
This is only what changed, what is unproven, and what to do next.

| Script | Version | Verified in game? |
|---|---|---|
| `harvest_runner.py` | `2026-08-21.15` | partly — crashes are real and reported, fixes are not confirmed |
| `resource_order_runner.py` | `2026-08-20.39` | **no** — granite/scales/Mythril all unproven |
| `TameAndFill.py` | `2026-08-16.1` | no |
| `COVFarm.py` | `1.6.0` | no |

`resource_order_runner.py` is **committed and pushed** (`29e64b0`). Everything
else is uncommitted.

---

## THE ONE THING THAT MATTERS MOST

**Two of the three crashes this session were ClassicUO bugs, not script bugs.**
Do not chase them in Python. Read the ClassicUO source first — it is open and
the answers were in it both times.

### Crash 1 — recv buffer overflow

```
System.ArgumentException: Argument_DestinationTooShort
  ClassicUO.Network.CircularBuffer.Enqueue
  ClassicUO.Network.PacketHandlers.Append
  ClassicUO.Network.Plugin.OnPluginRecv_new
```

Razor injects packets into the client faster than it drains them.
`Misc.SendMessage` is delivered *through that path*, so every log line is
network pressure. Mitigated by `LOG_DEDUPE_MS` / `LOG_MAX_PER_SECOND`
(see below). **Not fixed — only made less likely.**

### Crash 2 — RequestMove, and this one is a plain ClassicUO defect

```
System.NullReferenceException
  at ClassicUO.Network.Plugin.RequestMove(Int32, Boolean)
```

From `src/ClassicUO.Client/Network/Plugin.cs`:

```csharp
internal static bool RequestMove(int dir, bool run)
{
    return Client.Game.UO.World.Player.Walk((Direction)dir, run);
}
```

**No null check on `World.Player`.** The method immediately below it,
`GetPlayerPosition`, *does* check. `World.Player` is null across recalls, gate
travel and world reloads — and this script recalls constantly then walks
immediately. That is the crash.

Worked around by `player_ready()` (refuses to call the pathfinder unless the
character is really in the world) and `wait_for_player()` after every recall.
**Worth reporting upstream** — it is a two-line fix in ClassicUO.

They are on **ClassicUO DEV_BUILD 1.1.0.334**. A stable build is worth trying
as a comparison.

---

## harvest_runner.py — `2026-08-21.15`

Five copies. All five now have **byte-identical code halves**; they differ only
in the CONFIG block. `tools/check_undefined_names.py` verifies every copy.

| Copy | Jobs | Stone storage | Wood / Ingot / Stone serials |
|---|---|---|---|
| `…\razor\Scripts\` (`main`) | mining | off | `(live)` / `0` / `0` |
| `…\Scripts\Hanzo\` | mining | **on** `(live)` | `(live)` / `(live)` |
| `…\Scripts\MrGatherer\` | mining | **on** `(live)` | `(live)` / `(live)` |
| `…\Scripts\Mystic Gatherer\` | **lumber** | off | `(live)` / `(live)` |
| repo | both | off | all `0` — it is published to GitHub |

### What went in this session

- **Area sweeps.** Both jobs work a whole area per rune instead of one spot.
  Spot spacing comes from ServUO bank sizes: mining `8x8`, lumber `4x3` (so the
  lumber steps are per-axis, 4 across and 3 down). A bank that reports empty is
  remembered and the rest of it skipped.
- **Store at 90% weight** (`PACK_STORE_AT`), with a measured reserve underneath
  so one more yield cannot overshoot.
- **Stuck guards**, in the order they fire: path leg 5s → rooted-while-walking
  20s → per spot 15s (rolling, resets on every productive swing) → 45s
  producing nothing abandons the rune.
- **Say `skip`** in game to move to the next rune. Self-only, matched on the
  journal entry's `Serial`, so several dummy accounts skip independently.
- **`BOD_ENABLED`** — one switch turns off every bulk order (all five stops,
  the Carpenter, filing, the book) and leaves Resource Orders and Taming Deeds
  running.
- **Stone Storage** for granite, same shape as the other two keys. Granite is in
  `KEY_BACKED_IDS` so it stays out of the one-way chest.
- **Crash reporter** — writes traceback, last 40 log lines and state to
  `%TEMP%\harvest_crash_<Character>.txt`. **It cannot catch either crash above**
  (the client dies, Python never runs).
- **Log rate limiting** — `LOG_DEDUPE_MS = 4000`, `LOG_MAX_PER_SECOND = 12`.
  Suppression never hides a line from the crash trail.

### Cleanup done

All four live copies had **25 duplicated config names** (repo had none) — around
280 dead lines each, and editing the first copy of any of them did nothing,
because Python takes the last. Rebuilt from the repo carrying each character's
real settings, including the **Carpenter rune enabled** state. 5,500 → 5,216
lines.

Also removed `lumber_area_offsets` and `visit_vendor` (dead), and **wired**
`forget_sweeps` at startup rather than deleting it — Razor keeps a script loaded
between runs, so sweep state can outlive a Reload.

### OPEN

- Every fix above is **unproven in game**.
- `MINE_AREA_INCLUDE_SAND = False`, so the 179 `SAND_TILES` serve a disabled
  feature. ~20 lines; drop them if you want.
- `main` still has `INGOT_KEY_SERIAL = 0`.

---

## resource_order_runner.py — `2026-08-20.39`

### Identification, all from live Item Inspector dumps

- **Granite** — all nine hues. `GRANITE_IDS = [0x1779]`.
- **Ingots** — all confirmed; **Iron was already correct**. Added **Mythril**
  (`0x0057`), this shard's own metal, which had 146 unfillable orders.
- **Perfect Emerald** (`0x3194`) — was missing from `RESOURCES` entirely.
- **Scales** — all six. Blue is **sea serpent** `0x08B0`; the shard accepts them.
  Medusa `0x08AF` is deliberately NOT mapped — it has its own book entries.

### The bug that caused `0/429`

Every granite stack is *named* `<amount> high quality granite` whatever metal it
is, and there is a resource called High Quality Granite. So the `by: "name"`
fallback claimed **every** granite stack, and a Valorite stack was offered to
fill a High Quality order.

Two guards came out of it, both worth keeping:

- A hue-family member with no hue listed is marked `UNMATCHABLE` rather than
  left matching by name. **Unidentified must mean invisible, never mistaken.**
  The disarming is surgical — a blunter rule broke `Delicate Scales`.
- Hue uniqueness is validated **per family, not globally**. `0x0000` is
  legitimately both Regular Boards and High Quality Granite. The global check
  called that a clash and **refused to start**.

### Other fixes

- `census()` now reopens the chests and retries before believing a resource is
  gone — `chest_stacks()` always did. A resource missing from the census got a
  budget of 0 and was skipped **in silence**.
- No resource is ever skipped silently now; the line names it and its numbers.
- Fill passes scale with the stack count instead of a flat 6.

---

## Verifying

```bash
cd "G:/programming projects/Razor Enhanced Scripts"
for t in tests/test_*.py; do printf "%-40s " "$t"; python "$t" 2>&1 | tail -1; done
python tools/check_undefined_names.py Scripts/*.py "E:/uoclients/UOAlive_Package/razor/Scripts/harvest_runner.py"
```

Six suites, all green. `test_resource_order_runner.py` is 780 checks.

---

## HOW TO EDIT THE FIVE COPIES — read this before touching them

Every patcher failure this session came from the same two causes. There were
**six**.

1. **Regex.** A greedy `.*` with `re.DOTALL` twice ate from the anchor to the
   last matching line in the whole file — once destroying `RESTOCK_KEYS`
   entirely while leaving the file *syntactically valid*. **Do not build these
   edits with regex.**
2. **Guards keyed on a name that also appears in the code being spliced**, so
   the guard skipped an insert that was genuinely needed.

**What has never failed: splice a whole known-good region and carry the config
forward.** The file splits at the `# HELPERS` banner — everything above is
config, everything below is code. Replace the code half wholesale.

Two more traps, both of which bit:

- **Verify VALUES, not text.** A rebuild flipped the JOBS flags on three
  characters because both lines are the byte-identical string
  `"enabled": True,` and a positional replace hit the wrong one. Comparing
  `ast.literal_eval` output caught it; a diff would not have.
- **A syntax check is not evidence.** Run
  `tools/check_undefined_names.py` on every copy afterwards. It has caught four
  real breakages this session, including one that would have removed all key
  restocking.

---

## Next, in the order I would do it

1. **Run each script and report back.** Nothing here is confirmed in game.
2. **Report the `RequestMove` null check to ClassicUO** — it is a two-line fix
   and it is crashing a real user.
3. Try a **stable ClassicUO build** on MrGatherer as a comparison.
4. Confirm the order runner fills granite, Mythril and the scales.
5. Commit the harvest runner work — it is the only script still uncommitted.
