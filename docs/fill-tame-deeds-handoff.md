# FillTameDeeds — handoff

`Scripts/FillTameDeeds.py`, live at `E:\uoclients\RazorEnhanced\Scripts\`.
Current version `2026-10-25.4`. **Not yet run in game.**

## What it is

`TameAndFill.py` (live `2026-09-04.1`) with the whole cow/goat harvest
removed: config, corpse claiming, dagger, `[grab`, storage keys. Deed
scanning, species matching, `identify`, `tame`, peacemaking and `add_to_deed`
are TameAndFill's code unchanged. TameAndFill itself was not touched.

Added:

- **`[ar` round**: walks into `RUNEBOOK_FOLDER = ["FillTameDeeds"]` and visits
  every rune on every page. The book code is lifted from `ReagentBuyer.py`
  (recalls checked against the rune's coordinates, button checked against the
  rune name before pressing, delete buttons never paired). The 2026-07 root
  capture shows a folder called `TamingDeed`. The user named it
  `FillTameDeeds`, so if it is missing the log lists every folder it saw.
- **Kill list**: `HOSTILE_HITS` (332 names) and `HOSTILE_BODIES` (20 bodies
  for random-named monsters like orcs, lizardmen and daemons) come from
  `tools/extract_hostiles.py` over ServUO `Scripts/Mobiles`, using FightMode
  not being Aggressor/None. `OFFICIAL_HOSTILE_NAMES` (240) is UOGuide
  `Category:Monsters` (565 names, fetched 2026-10-25) minus what ServUO
  already has, minus tameables and non-creature pages.
- **Spells**: Magic Arrow under `SPELL_BIG_HITS = 500` (raised from 150 in
  `2026-10-25.2`: the shard is customised and the character has 3,467 Spell
  Damage Increase). Energy Bolt at or over
  it, or when hit points are unknown. A fight is upgraded to Energy Bolt after
  4 arrows if the target is still at 60% or more.
- **Gate**: notoriety 3–6 only (never blue or green). Human bodies only when
  red. A species with an unfilled deed is never attacked. Tooltip
  `(tame)`/`(bonded)`/`(summoned)` is skipped. Body matches need red.
- **Paragons** (tooltip `(Paragon)` or hue `0x501`): never tamed. If the
  species is hostile it is killed with its hits counted ×5, which decides
  the spell (a harpy paragon at 325 is still Magic Arrow, a dragon paragon is
  Energy Bolt). A paragon of a
  passive species is ignored. A paragon of a deed species is not quarry.
- **Escape** below 35% health through `[ar RO RO`, then wait to heal to 90%.

## 2026-10-25.3: fixes from the first runs

**Tamed pets left following you instead of going into their deed.** There
were two causes, both confirmed in ServUO source:

- `"That wasn't even challenging."` (502797) is a **success** message. It
  replaces 502799 when you have owned the creature before. It was in
  `MSG_SKIP`, so the tame was written off. TameAndFill had the same bug, and
  the post-fight journal clear below. Both are fixed there in `2026-10-25.1`,
  with no stray sweep, live and repo.
- `watch_attempt` ran `Journal.Clear()` after every `defend()`. The tame
  keeps running on the server during the fight, so a success that landed
  mid-fight was cleared away. It now checks for success before clearing,
  and `cast_at` reads its own results by journal timestamp, never by
  clearing.
- Backstop: every creature the run tries to tame is remembered
  (`_our_tames`). Any of those still following as a pet (`Player.Pets` or
  `(tame)` in its tooltip) is deeded by `sweep_strays()`, which runs every
  loop and always before leaving a spot, because pets do not recall with
  you. Pets you brought are never touched.

**Monsters got close enough to break casts.** `kill()` used to walk in to 8
tiles before casting. Now:

- It casts from `SPELL_RANGE = 10`, the ServUO range of both spells.
- It looks out to `KILL_RANGE = 14`.
- It waits for something walking in rather than walking to it.
- It only approaches to 10.
- Mid-tame defence range is 10, up from 6.
- A cast broken by a hit (500641) is recast at once. That used to read as "no
  cursor, check reagents", and three of them meant giving up on, and
  ignoring, the monster hitting you.
- After a landed cast it waits 700 ms (`KILL_LAND_MS`, was 2200) and sends
  the second if the first did not kill.

## 2026-10-25.4: stuck at a house

The run sat outside a house with mannequins. The mannequins were not the
target: they are notoriety 7 on a human body, and nothing in the script
looks at either. The likely cause, from ServUO source:

- The taming cursor (`AnimalTaming.InternalTarget`, range 3, `checkLOS
  false`) accepts a creature through a wall. The tick then stops it with
  1049654 "no clear path". That was in `MSG_REPOSITION`, so the script
  walked closer (already within 2), retried, and repeated up to 25 times.
  It is now `MSG_BLOCKED`, and two of those (`TAME_MAX_BLOCKED`), or a
  reposition that walking cannot improve, ends it as `unreachable`.
  `TAME_CREATURE_MAX_MS` (3 min) is the backstop.
- The creature in there was most likely somebody's pet, and `identify()`
  never checked. Now quarry must be notoriety 3 or 6 (`TAME_NOTORIETY`).
  ServUO `Notoriety.cs` makes a wild creature 3, or 6 if a murderer type, and
  a pet takes its owner's colour. Quarry also must not show `(tame)`,
  `(bonded)` or `(summoned)` in its tooltip.

Not confirmed from a log. If it sticks again, the `Found X at N tiles` /
`Taming X (attempt n)` lines will say what it was after.

## To check on the first run

1. Banner `FillTameDeeds v2026-10-25.4`.
2. `N spot(s) in FillTameDeeds: ...`. If not found, read the folder list.
3. First kill: is the spell right for the size?
4. Whether `IsHuman` and `IgnorePets` behave on this shard (both are new
   here).
