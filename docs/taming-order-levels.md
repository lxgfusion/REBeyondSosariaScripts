# Taming order levels

## READ THIS FIRST - the Band column is a guess

The **order level** is your shard's, and it lives on the deed:

```
Level: 2Creature Type: KirinFilled: 24/60Gold: 100%Runics:
```

Nothing in this repo has ever read one. Two levels are known, both from the
user on 2026-09-18: **sheep is 1** and **dragon is 3**. Two points do not
determine 112.

**The ranking below is real. The Band column is not.** Ranking comes from the
minimum taming skill ServUO gives each species, already extracted into
`Scripts/TameAndFill.py`'s `ANIMAL_CATALOGUE` and re-read by
`tools/rank_tameables.py` rather than retyped.

### Why the bands cannot be derived

The skill ladder is **evenly spaced**, 6.0 apart, with no clustering to hang
boundaries on:

```
34 distinct min-skill values across 112 species

the widest gaps - a band boundary is least wrong inside one:
     11.1 wide: nothing between 0.0 and 11.1
      6.0 wide: nothing between 11.1 and 17.1
      6.0 wide: nothing between 53.1 and 59.1
      6.0 wide: nothing between 47.1 and 53.1
      6.0 wide: nothing between 41.1 and 47.1
      6.0 wide: nothing between 35.1 and 41.1
      6.0 wide: nothing between 29.1 and 35.1
      6.0 wide: nothing between 23.1 and 29.1

  level 1 (>=   0.0 skill):  47 species
  level 2 (>=  50.0 skill):  36 species
  level 3 (>=  90.0 skill):  29 species
```

Every gap between 17.1 and 59.1 is exactly 6.0 wide. There is no "natural"
three-way split in this data - so any boundary is invented, and CLAUDE.md is
explicit that shard data comes from source or a live dump and never from
memory. The 50 / 90 boundaries below were chosen only to put sheep in band 1
and dragon in band 3. They may well be wrong.

## Getting the real numbers

`Scripts/diag_taming_levels.py` reads `Level:` off every taming order deed in
your pack - bags included - and prints paste-ready rows. Run it holding as many
different deeds as you can and the table fills itself, the same way the granite
hue table did.

It also watches for one thing that would change the shape of this whole
document: **a species that reads two different levels**. If that happens, the
level is a property of the *deed*, not of the creature, and a per-species table
is the wrong idea entirely.

## Confirmed

| Species | Level | Source |
|---|--:|---|
| sheep | 1 | user, 2026-09-18 |
| dragon | 3 | user, 2026-09-18 |

## Ranked by minimum taming skill

Lowest first. A tick marks a confirmed level; everything else in that column is
the band this file guessed.

| # | Species | Min taming | Band | Bodies |
|--:|---|--:|:--:|---|
| 1 | battle chicken lizard | 0.0 | 1 | `0x2CC` |
| 2 | bird | 0.0 | 1 | `0x6` |
| 3 | cat | 0.0 | 1 | `0xC9` |
| 4 | chicken | 0.0 | 1 | `0xD0` |
| 5 | chicken lizard | 0.0 | 1 | `0x2CC` |
| 6 | dog | 0.0 | 1 | `0xD9` |
| 7 | ferret | 0.0 | 1 | `0x117` |
| 8 | gorilla | 0.0 | 1 | `0x1D` |
| 9 | jack rabbit | 0.0 | 1 | `0xCD` |
| 10 | mountain goat | 0.0 | 1 | `0x58` |
| 11 | parrot | 0.0 | 1 | `0x33F` |
| 12 | rabbit | 0.0 | 1 | `0xCD` |
| 13 | rat | 0.0 | 1 | `0xEE` |
| 14 | sewer rat | 0.0 | 1 | `0xEE` |
| 15 | skittering hopper | 0.0 | 1 | `0x12E` |
| 16 | squirrel | 0.0 | 1 | `0x116` |
| 17 | cow | 11.1 | 1 | `0xD8`, `0xE7` |
| 18 | goat | 11.1 | 1 | `0xD1` |
| 19 | pig | 11.1 | 1 | `0xCB` |
| 20 | sheep | 11.1 | **1** (confirmed) | `0xCF`, `0xDF` |
| 21 | eagle | 17.1 | 1 | `0x5` |
| 22 | lowland boura | 19.1 | 1 | `0x2CB` |
| 23 | ruddy boura | 19.1 | 1 | `0x2CB` |
| 24 | bull frog | 23.1 | 1 | `0x51` |
| 25 | corrosive slime | 23.1 | 1 | `0x33` |
| 26 | hind | 23.1 | 1 | `0xED` |
| 27 | slime | 23.1 | 1 | `0x33` |
| 28 | timber wolf | 23.1 | 1 | `0xE1` |
| 29 | boar | 29.1 | 1 | `0x122` |
| 30 | desert ostard | 29.1 | 1 | `0xD2` |
| 31 | forest ostard | 29.1 | 1 | `0xDB` |
| 32 | giant beetle | 29.1 | 1 | `0x317` |
| 33 | giant rat | 29.1 | 1 | `0xD7` |
| 34 | horse | 29.1 | 1 | `0x2`, `0xE2`, `0x580` |
| 35 | pack horse | 29.1 | 1 | `0x123` |
| 36 | pack llama | 29.1 | 1 | `0x124` |
| 37 | ridable llama | 29.1 | 1 | `0xDC` |
| 38 | black bear | 35.1 | 1 | `0xD3` |
| 39 | llama | 35.1 | 1 | `0xDC` |
| 40 | polar bear | 35.1 | 1 | `0xD5` |
| 41 | walrus | 35.1 | 1 | `0xDD` |
| 42 | brown bear | 41.1 | 1 | `0xA7` |
| 43 | cougar | 41.1 | 1 | `0x3F` |
| 44 | deathwatch beetle | 41.1 | 1 | `0xF2` |
| 45 | alligator | 47.1 | 1 | `0xCA` |
| 46 | high plains boura | 47.1 | 1 | `0x2CB` |
| 47 | scorpion | 47.1 | 1 | `0x30` |
| 48 | grey wolf | 53.1 | 2 | `0x19`, `0x1B` |
| 49 | panther | 53.1 | 2 | `0xD6` |
| 50 | snow leopard | 53.1 | 2 | `0x40`, `0x41` |
| 51 | giant spider | 59.1 | 2 | `0x1C` |
| 52 | great hart | 59.1 | 2 | `0xEA` |
| 53 | grizzly bear | 59.1 | 2 | `0xD4` |
| 54 | snake | 59.1 | 2 | `0x34` |
| 55 | wolf spider | 59.1 | 2 | `0x2E0` |
| 56 | gargoyle pet | 65.1 | 2 | `0x2DA` |
| 57 | stone slith | 65.1 | 2 | `0x2DE` |
| 58 | white wolf | 65.1 | 2 | `0x22`, `0x25` |
| 59 | gaman | 68.7 | 2 | `0xF8` |
| 60 | bull | 71.1 | 2 | `0xE8`, `0xE9` |
| 61 | giant ice worm | 71.1 | 2 | `0x59` |
| 62 | greater mongbat | 71.1 | 2 | `0x27` |
| 63 | hell cat | 71.1 | 2 | `0xC9` |
| 64 | iron beetle | 71.1 | 2 | `0x2CA` |
| 65 | mongbat | 71.1 | 2 | `0x27` |
| 66 | blood fox | 72.0 | 2 | `0x58F` |
| 67 | ossein ram | 72.0 | 2 | `0x591` |
| 68 | frost spider | 74.7 | 2 | `0x14` |
| 69 | frenzied ostard | 77.1 | 2 | `0xDA` |
| 70 | giant toad | 77.1 | 2 | `0x50` |
| 71 | bake kitsune | 80.7 | 2 | `0xF6` |
| 72 | lava lizard | 80.7 | 2 | `0xCE` |
| 73 | slith | 80.7 | 2 | `0x2DE` |
| 74 | dire wolf | 83.1 | 2 | `0x17` |
| 75 | imp | 83.1 | 2 | `0x4A` |
| 76 | ridgeback | 83.1 | 2 | `0xBB` |
| 77 | savage ridgeback | 83.1 | 2 | `0xBC` |
| 78 | drake | 84.3 | 2 | `0x3C`, `0x3D` |
| 79 | crimson drake | 85.0 | 2 | `0x58B`, `0x58C` |
| 80 | platinum drake | 85.0 | 2 | `0x589`, `0x58A` |
| 81 | stygian drake | 85.0 | 2 | `0x58E` |
| 82 | hell hound | 85.5 | 2 | `0x62` |
| 83 | ice hound | 85.5 | 2 | `0x62` |
| 84 | predator hellcat | 90.0 | 3 | `0x7F` |
| 85 | dragon | 93.9 | **3** (confirmed) | `0xC`, `0x3B` |
| 86 | fire beetle | 93.9 | 3 | `0xA9` |
| 87 | rune beetle | 93.9 | 3 | `0xF4` |
| 88 | swamp dragon | 93.9 | 3 | `0x31A`, `0x31F` |
| 89 | ki-rin | 95.1 | 3 | `0x84` |
| 90 | nightmare | 95.1 | 3 | `0x74`, `0xB1`, `0xB2`, `0xB3` |
| 91 | skree | 95.1 | 3 | `0x2DD` |
| 92 | unicorn | 95.1 | 3 | `0x7A` |
| 93 | wild tiger | 95.1 | 3 | `0x4E6`, `0x4E7` |
| 94 | cold drake | 96.0 | 3 | `0x3C`, `0x3D` |
| 95 | dread spider | 96.0 | 3 | `0xB` |
| 96 | lion | 96.0 | 3 | `0x592` |
| 97 | tsuki wolf | 96.0 | 3 | `0xFA` |
| 98 | white wyrm | 96.3 | 3 | `0x31`, `0xB4` |
| 99 | hiryu | 98.7 | 3 | `0xF3` |
| 100 | cu sidhe | 101.1 | 3 | `0x115` |
| 101 | reptalon | 101.1 | 3 | `0x114` |
| 102 | dragon wolf | 102.0 | 3 | `0x2CF` |
| 103 | frost mite | 102.0 | 3 | `0x590` |
| 104 | phoenix | 102.0 | 3 | `0x340` |
| 105 | saber-toothed tiger | 102.0 | 3 | `0x588` |
| 106 | triceratops | 102.0 | 3 | `0x587` |
| 107 | greater dragon | 104.7 | 3 | `0xC`, `0x3B` |
| 108 | frost dragon | 105.0 | 3 | `0xC`, `0x3B` |
| 109 | shadow wyrm | 105.0 | 3 | `0x6A` |
| 110 | fire steed | 106.0 | 3 | `0xBE` |
| 111 | dread warhorse | 108.0 | 3 | `0x74` |
| 112 | serpentine dragon | 108.0 | 3 | `0x67` |
---

Regenerate with `python tools/rank_tameables.py --markdown`.
