# Razor Enhanced API cheatsheet

Hand-written quick reference for the calls these scripts actually use.

**Re-verified 2026-07-27 against the C# source** at tag `v1.0.0.14`, not against
any published doc site. For the complete, machine-generated surface — every
overload of every class — see
[`api-reference-generated.md`](api-reference-generated.md), and regenerate it
with `tools/extract_re_api.py` when a new build ships.

## Which build is this accurate for

- Installed on this machine: **1.0.0.12** (`%LOCALAPPDATA%\www.razorenhanced.net\RazorEnhanced.exe_Url_*\`).
- Latest release: **1.0.0.14** (2026-07-16).
- The API surface is **byte-identical across 1.0.0.11 → 1.0.0.14**, so anything
  here applies to all of them.
- https://razorenhanced.github.io/doc/api/ is built from **1.0.0.11** — three
  builds behind, but not actually wrong, because nothing in the API moved.
- `readthedocs.io` is much older and is missing whole methods. Don't use it.

Signatures are as the source declares them; `→` shows the return type.

## Mobiles

```
Mobiles.ApplyFilter(filter)                  -> List[Mobile]
Mobiles.FindBySerial(serial)                 -> Mobile
Mobiles.Select(mobiles, selector)            -> Mobile
Mobiles.Message(mobile|serial, hue, msg, wait)
Mobiles.SingleClick(mobile|serial)
Mobiles.UseMobile(mobile|serial)
Mobiles.WaitForProps(mobile|serial, delay)
Mobiles.WaitForStats(mobile|serial, delay)
Mobiles.GetPropValue(mob|serial, name)       -> Single
Mobiles.GetPropStringList(mob|serial)        -> List[String]
Mobiles.GetPropStringByIndex(mob|serial, i)  -> String
Mobiles.ContextExist(mob|serial, name)       -> Int32
Mobiles.GetTrackingInfo()                    -> Mobiles.TrackingInfo
```

### Mobiles.Filter

| Property | Type | Default / notes |
|---|---|---|
| `Enabled` | Boolean | `True` |
| `Name` | String | exact name match |
| `Bodies` | List[Int32] | `.Add()` / `.AddRange()` |
| `RangeMin` / `RangeMax` | Double | `-1` = unset |
| `Female`, `Friend`, `Paralized`, `Poisoned`, `Blessed` | Int32 | `-1` = any |
| `Warmode` | Int32 | `-1` any, `0` peace, `1` war |
| `IsGhost`, `IsHuman` | Int32 | `-1` = any |
| `Serials` | List[Int32] | `.Add()` |
| `Notorieties` | List[Byte] | 1 innocent, 2 friend, 3 grey/animal, 4 criminal, 5 enemy, 6 murderer |
| `Hues` | List[Int32] | `.Add()` |
| `ZLevelMin` / `ZLevelMax` | Double | `-1` = unset |
| `CheckIgnoreObject` | Boolean | excludes the global ignore list |
| `IgnorePets` | Boolean | excludes your own pets |
| `CheckLineOfSight` | Boolean | `False` |

`Graphics` is an alias for `Bodies` — same underlying list, either name works.
`CheckLineOfSite` (sic) is a second alias for `CheckLineOfSight`; both spellings
exist in the source.

### Mobile properties

`Serial` `Body` `Name` (String), `Position` (Point3D), `Hits` `HitsMax`
`Notoriety` `Color` (Int32), `Direction` (String), `Backpack` (Item),
`Properties` (List[Property]), and Booleans: `IsGhost` `IsHuman` `Visible`
`InParty` `PropsUpdated` `Flying` `Paralized` `Poisoned` `WarMode` `YellowHits`
`Female`.

Note the property is `WarMode` on `Mobile` but `Player.WarMode` on Player, and
`Warmode` (lowercase m) on `Mobiles.Filter`.

## Player

```
Player.PathFindTo(x, y, z) | PathFindTo(Point3D)
Player.PathFindTo(x, y, maxretry, run, stopifstuck, ignoremobile, resync, debug)
Player.Run(direction)                        -> Boolean
Player.Walk(direction)                       -> Boolean
Player.UseSkill(skillname)
Player.UseSkill(skillname, wait)
Player.UseSkill(skillname, target, wait)     # target: Int32 | Mobile | Item
Player.GetSkillValue(skillname)              -> Double
Player.GetRealSkillValue(skillname)          -> Double
Player.GetSkillCap(skillname)                -> Double
Player.DistanceTo(mobile|item|serial)        -> Int32
Player.InRange(entity|serial, range)         -> Boolean
Player.InRangeMobile(mobile|serial, range)   -> Boolean
Player.InRangeItem(item|serial, range)       -> Boolean
Player.BuffsExist(buffname, okayToGuess)     -> Boolean
Player.BuffTime(buffname)                    -> Int32
Player.Attack(mobile|serial) / AttackLast()
Player.SetWarMode(warflag)
Player.HeadMessage(color, msg)
Player.ChatSay(msg) | ChatSay(color, msg)
Player.EquipItem(item|serial) / UnEquipItemByLayer(layer, wait)
Player.GetItemOnLayer(layer)                 -> Item
Player.ToggleAlwaysRun()
```

`Player.Run` and `Player.Walk` take **one** argument on every build from
`0.8.2.245` through `1.0.0.14`. A two-argument `Run(direction, checkPosition)`
belongs to a much older build — keep the `try/except TypeError` shim, but expect
the one-argument form to be the one that works.

Properties: `Position` (Point3D), `Mount` `Backpack` `Bank` `Quiver` (Item),
`Serial` `Hits` `HitsMax` `Mana` `ManaMax` `Stam` `StamMax` `Str` `Dex` `Int`
`Gold` `Luck` `Weight` `MaxWeight` `Followers` `FollowersMax` `Body` `Map`
(Int32), `Name` `Direction` `KarmaTitle` (String), `Pets` (List[Mobile]),
`Buffs` (List[String]), `Visible` `WarMode` `IsGhost` `Poisoned` `Paralized`
`Female` `Connected` (Boolean), plus the full resist/property set
(`FireResistance`, `LowerManaCost`, `FasterCasting`, ...).

Directions accepted: `North South East West Up Down Left Right`.

## Journal

```
Journal.Search(text)                         -> Boolean
Journal.SearchByName(text, name)             -> Boolean
Journal.SearchByType(text, type)             -> Boolean
Journal.WaitJournal(text, delay)             -> Boolean
Journal.WaitJournal(List[String], delay)     -> String
Journal.Clear()
Journal.GetJournalEntry(afterTimestamp|afterEntry) -> List[JournalEntry]
Journal.GetTextByType(type, addname)         -> List[String]
Journal.GetTextBySerial(serial, addname)     -> List[String]
```

`Search` scans the entire buffer — clear it before reading a fresh result.

## Target

```
Target.WaitForTarget(delay, noshow=False)    -> Boolean
Target.WaitForTargetOrFizzle(delay=5000, noshow=False) -> Boolean
Target.HasTarget(targetFlag="Any")           -> Boolean
Target.TargetExecute(item|serial|mobile)
Target.TargetExecute(x, y, z[, staticID])
Target.TargetExecuteRelative(mobile|serial, offset)
Target.TargetResource(item|serial, resource_name|resource_number)
Target.TargetType(graphic, color, range, selector, notoriety) -> Boolean
Target.SetLast(mobile) | SetLast(serial, wait)
Target.PromptTarget(message, color)          -> Int32
Target.PromptGroundTarget(message, color)    -> Point3D
Target.Cancel() / Self() / Last() / ClearLast() / ClearQueue()
Target.GetLast() -> Int32 | GetLastAttack() -> Int32
```

`HasTarget` takes an optional flag — `"Any"` (default), `"Beneficial"`,
`"Harmful"` or `"Neutral"`. Anything else raises `ArgumentOutOfRangeException`,
so don't pass a bare `True`.

`WaitForTargetOrFizzle` is the one to use after casting: plain `WaitForTarget`
sits out the full delay when the spell fizzles.

## Items

```
Items.FindByID(itemid, color, container, range|recursive, considerIgnoreList) -> Item
Items.FindBySerial(serial)                   -> Item
Items.UseItem(item|serial[, target][, wait])
Items.UseItemByID(itemid, color)             -> Boolean
Items.ApplyFilter(filter)                    -> List[Item]
Items.WaitForProps(item|serial, delay)
Items.GetPropStringList(item|serial)         -> List[String]
Items.Message(item|serial, hue, message)
```

### Items.Filter

| Property | Type | Default |
|---|---|---|
| `Enabled` | Boolean | `True` |
| `Name` | String | |
| `Graphics` | List[Int32] | `.Add()` |
| `Hues` | List[Int32] | `.Add()` |
| `Serials` | List[Int32] | `.Add()` |
| `Layers` | List[String] | |
| `OnGround`, `IsContainer`, `IsCorpse`, `IsDoor`, `Movable`, `Multi` | Int32 | `-1` = any |
| `RangeMin` / `RangeMax` | Double | `-1` |
| `ZRangeMin` / `ZRangeMax` | Double | `-1` |
| `CheckIgnoreObject` | Boolean | `False` |

There is **no `Container` field**. To restrict a search to your backpack, filter
with `OnGround = 0` and then apply your own held-item check.

Do **not** test `item.RootContainer == Player.Serial`. On this shard
`RootContainer` returns the *backpack's item serial* (`0x41D40F58`), not the
player's mobile serial, so that comparison rejects everything you own. Accept
either `Player.Serial` or `Player.Backpack.Serial`, and walk `item.Container`
upward as a fallback for items in sub-bags.

### Item properties

`Serial` `ItemID` `Amount` `Hue` `Container` `RootContainer` `Weight`
`Durability` `MaxDurability` (Int32), `Name` `Layer` (String), `Position`
(Point3D), `Contains` (List[Item]), `Properties` (List[Property]), and Booleans
`OnGround` `Visible` `Movable` `Deleted` `IsContainer` `IsCorpse` `IsPotion`
`IsResource` `PropsUpdated`.

Note the colour field is `Item.Hue` but `Mobile.Color`.

## Gumps

```
Gumps.HasGump()                              -> Boolean   # any gump open
Gumps.HasGump(gumpid)                        -> Boolean   # that gump open
Gumps.CurrentGump()                          -> UInt32
Gumps.AllGumpIDs()                           -> List[UInt32]
Gumps.WaitForGump(gumpid|[gumpids], delay)   -> Boolean
Gumps.ResetGump()
Gumps.CloseGump(gumpid)
Gumps.SendAction(gumpid, buttonid)
Gumps.SendAdvancedAction(gumpid, buttonid, switches[, textlist_id, textlist_str])
Gumps.GetLineList(gumpId, dataOnly=False)    -> List[String]
Gumps.GetLine(gumpId, line_num)              -> String
Gumps.GetGumpRawLayout(gumpid)               -> String
Gumps.GetGumpText(gumpid) / GetGumpRawText(gumpid) -> List[String]
Gumps.GetGumpData(gumpid)                    -> Gumps.GumpData
```

`WaitForGump` returns `True` for a gump that is **already open**. Call
`Gumps.ResetGump()` (or `CloseGump`) before the action that should open the one
you want, or you answer a leftover window. `AllGumpIDs()` and `CurrentGump()`
are the quickest way to see what is actually on screen when a gump interaction
misbehaves — including the server-side paging case in
[`account-runebook-gump.md`](account-runebook-gump.md), where each page arrives
as a fresh gump under the same id.

`SendAdvancedAction` is what fills in text entries and checkboxes; `SendAction`
only presses a button. Pressing a button with plain `SendAction` on a gump that
has text entries submits those entries **empty**, which clears any filter or
typed value the gump was holding.

**`GetLineList` cannot be indexed by the layout's text ids.** Razor drops empty
strings from the gump's string table without leaving a gap, so one blank cell
shifts every later index. Pair by element order — one entry per
`text`/`croppedtext` in layout order. See the note in `CLAUDE.md` and the worked
example in [`resource-order-book-gump.md`](resource-order-book-gump.md).

## Spells

```
Spells.Cast(name[, target|mobile][, wait=True][, waitAfter=0])
Spells.CastMagery / CastNecro / CastChivalry / CastBushido / CastNinjitsu
Spells.CastSpellweaving / CastMysticism / CastMastery / CastCleric / CastDruid
Spells.Interrupt()
```

Pair a cast with `Target.WaitForTargetOrFizzle(delay)` rather than
`WaitForTarget`, so a fizzle doesn't cost the whole timeout.

## Timer

```
Timer.Create(name, delay[, message])
Timer.Check(name)                            -> Boolean   # True while running
Timer.Remaining(name)                        -> Int32     # milliseconds
```

A named countdown maintained by Razor. Useful as a deadline that survives across
functions, but `time.time()` is still the right tool for a local polling loop.

## Statics

```
Statics.GetLandID(x, y, map) / GetLandZ(x, y, map)      -> Int32
Statics.GetLandName(staticID) / GetTileName(staticID)   -> String
Statics.GetTileFlag(staticID, flagname)                 -> Boolean
Statics.GetLandFlag(staticID, flagname)                 -> Boolean
Statics.GetStaticsTileInfo(x, y, map)                   -> List[Statics.TileInfo]
Statics.GetStaticsLandInfo(x, y, map)                   -> Statics.TileInfo
Statics.CheckDeedHouse(x, y)                            -> Boolean
```

For a given `(x, y, map)` there is exactly **one** Land tile but any number of
Static tiles — mind which one a check is asking about.

## Misc

```
Misc.Pause(millisec)
Misc.SendMessage(msg[, color][, wait])
Misc.ScriptRun(scriptfile) / ScriptStatus(scriptfile) -> Boolean
Misc.IgnoreObject(serial|mob|item)
Misc.CheckIgnoreObject(serial|mob|item)      -> Boolean
Misc.ClearIgnore()
Misc.WaitForContext(serial|mob|item, delay)  -> List[Misc.Context]
Misc.ContextReply(serial|mob|item, menu_name|menu_num)
Misc.NoOperation() / Resync() / Beep() / FocusUOWindow()
Misc.SetSharedValue(name, value) / ReadSharedValue(name) -> Object
Misc.DistanceSqrt(point_a, point_b)          -> Double
```

## PathFinding

```
PathFinding.Go(route)                        -> Boolean
PathFinding.GetPath(dst_x, dst_y, ignoremob) -> List[Tile]
PathFinding.RunPath(path, timeout, debugMessage, useResync) -> Boolean
PathFinding.Tile(x, y)                       -> Tile
```

`PathFinding.Route` fields: `X` `Y` `MaxRetry` `Timeout` `StopIfStuck`
`IgnoreMobile` `DebugMessage` `UseResync`. A-star based. Pathing to a tile
occupied by a mobile does not work — aim at an adjacent tile.

## Coordinate / direction reference

X grows east, Y grows south (RunUO `Direction` enum order):

| Name | dx, dy | Compass |
|---|---|---|
| `North` | 0, -1 | N |
| `Right` | +1, -1 | NE |
| `East` | +1, 0 | E |
| `Down` | +1, +1 | SE |
| `South` | 0, +1 | S |
| `Left` | -1, +1 | SW |
| `West` | -1, 0 | W |
| `Up` | -1, -1 | NW |
