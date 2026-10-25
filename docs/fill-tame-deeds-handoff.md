# FillTameDeeds — handoff

`Scripts/FillTameDeeds.py`, live at `E:\uoclients\RazorEnhanced\Scripts\`.
Current version `2026-10-25.2`. **Not yet run in game.**

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

## To check on the first run

1. Banner `FillTameDeeds v2026-10-25.2`.
2. `N spot(s) in FillTameDeeds: ...`. If not found, read the folder list.
3. First kill: is the spell right for the size?
4. Whether `IsHuman` and `IgnorePets` behave on this shard (both are new
   here).
