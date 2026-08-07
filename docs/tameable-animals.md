# Tameable animals

Every class in ServUO `Scripts/Mobiles` with `Tamable = true`, extracted from
source rather than typed by hand. Body values come from both `Body = ...`
assignments and `BaseMount` `base(name, body, mountItemID, ...)` arguments.

This is the data behind `ANIMAL_CATALOGUE` in
[`Scripts/TameAndFill.py`](../Scripts/TameAndFill.py). Confirm anything
surprising against your own shard - use `diag_deed_target.py` on a
tamed pet to read a live body value.

Species marked `*` share a body value with another species, so a body match
alone does not identify them. See the collisions table below.

Min taming of `-` means the source sets no `MinTameSkill`.

| Species | Bodies | Min taming |
|---|---|---|
| alligator | `0xCA` | 47.1 |
| bake kitsune | `0xF6` | 80.7 |
| battle chicken lizard * | `0x2CC` | - |
| bird | `0x6` | - |
| black bear | `0xD3` | 35.1 |
| blood fox | `0x58F` | 72.0 |
| boar | `0x122` | 29.1 |
| brown bear | `0xA7` | 41.1 |
| bull | `0xE8`, `0xE9` | 71.1 |
| bull frog | `0x51` | 23.1 |
| cat * | `0xC9` | - |
| chicken | `0xD0` | - |
| chicken lizard * | `0x2CC` | - |
| cold drake * | `0x3C`, `0x3D` | 96.0 |
| corrosive slime * | `0x33` | 23.1 |
| cougar | `0x3F` | 41.1 |
| cow | `0xD8`, `0xE7` | 11.1 |
| crimson drake | `0x58B`, `0x58C` | 85.0 |
| cu sidhe | `0x115` | 101.1 |
| deathwatch beetle | `0xF2` | 41.1 |
| desert ostard | `0xD2` | 29.1 |
| dire wolf | `0x17` | 83.1 |
| dog | `0xD9` | - |
| dragon * | `0xC`, `0x3B` | 93.9 |
| dragon wolf | `0x2CF` | 102.0 |
| drake * | `0x3C`, `0x3D` | 84.3 |
| dread spider | `0xB` | 96.0 |
| dread warhorse * | `0x74` | 108.0 |
| eagle | `0x5` | 17.1 |
| ferret | `0x117` | - |
| fire beetle | `0xA9` | 93.9 |
| fire steed | `0xBE` | 106.0 |
| forest ostard | `0xDB` | 29.1 |
| frenzied ostard | `0xDA` | 77.1 |
| frost dragon * | `0xC`, `0x3B` | 105.0 |
| frost mite | `0x590` | 102.0 |
| frost spider | `0x14` | 74.7 |
| gaman | `0xF8` | 68.7 |
| gargoyle pet | `0x2DA` | 65.1 |
| giant beetle | `0x317` | 29.1 |
| giant ice worm | `0x59` | 71.1 |
| giant rat | `0xD7` | 29.1 |
| giant spider | `0x1C` | 59.1 |
| giant toad | `0x50` | 77.1 |
| goat | `0xD1` | 11.1 |
| gorilla | `0x1D` | - |
| great hart | `0xEA` | 59.1 |
| greater dragon * | `0xC`, `0x3B` | 104.7 |
| greater mongbat * | `0x27` | 71.1 |
| grey wolf | `0x19`, `0x1B` | 53.1 |
| grizzly bear | `0xD4` | 59.1 |
| hell cat * | `0xC9` | 71.1 |
| hell hound * | `0x62` | 85.5 |
| high plains boura * | `0x2CB` | 47.1 |
| hind | `0xED` | 23.1 |
| hiryu | `0xF3` | 98.7 |
| horse | `0x2`, `0xE2`, `0x580` | 29.1 |
| ice hound * | `0x62` | 85.5 |
| imp | `0x4A` | 83.1 |
| iron beetle | `0x2CA` | 71.1 |
| jack rabbit * | `0xCD` | - |
| ki-rin | `0x84` | 95.1 |
| lava lizard | `0xCE` | 80.7 |
| lion | `0x592` | 96.0 |
| llama * | `0xDC` | 35.1 |
| lowland boura * | `0x2CB` | 19.1 |
| mongbat * | `0x27` | 71.1 |
| mountain goat | `0x58` | - |
| nightmare * | `0x74`, `0xB1`, `0xB2`, `0xB3` | 95.1 |
| ossein ram | `0x591` | 72.0 |
| pack horse | `0x123` | 29.1 |
| pack llama | `0x124` | 29.1 |
| panther | `0xD6` | 53.1 |
| parrot | `0x33F` | - |
| phoenix | `0x340` | 102.0 |
| pig | `0xCB` | 11.1 |
| platinum drake | `0x589`, `0x58A` | 85.0 |
| polar bear | `0xD5` | 35.1 |
| predator hellcat | `0x7F` | 90.0 |
| rabbit * | `0xCD` | - |
| rat * | `0xEE` | - |
| reptalon | `0x114` | 101.1 |
| ridable llama * | `0xDC` | 29.1 |
| ridgeback | `0xBB` | 83.1 |
| ruddy boura * | `0x2CB` | 19.1 |
| rune beetle | `0xF4` | 93.9 |
| saber-toothed tiger | `0x588` | 102.0 |
| savage ridgeback | `0xBC` | 83.1 |
| scorpion | `0x30` | 47.1 |
| serpentine dragon | `0x67` | 108.0 |
| sewer rat * | `0xEE` | - |
| shadow wyrm | `0x6A` | 105.0 |
| sheep | `0x3`, `0xCF`, `0xDF` | 11.1 |
| skittering hopper | `0x12E` | - |
| skree | `0x2DD` | 95.1 |
| slime * | `0x33` | 23.1 |
| slith * | `0x2DE` | 80.7 |
| snake | `0x34` | 59.1 |
| snow leopard | `0x40`, `0x41` | 53.1 |
| squirrel | `0x116` | - |
| stone slith * | `0x2DE` | 65.1 |
| stygian drake | `0x58E` | 85.0 |
| swamp dragon | `0x31A`, `0x31F` | 93.9 |
| timber wolf | `0xE1` | 23.1 |
| triceratops | `0x587` | 102.0 |
| tsuki wolf | `0xFA` | 96.0 |
| unicorn | `0x7A` | 95.1 |
| walrus | `0xDD` | 35.1 |
| white wolf | `0x22`, `0x25` | 65.1 |
| white wyrm | `0x31`, `0xB4` | 96.3 |
| wild tiger | `0x4E7` | 95.1 |
| wolf spider | `0x2E0` | 59.1 |

## Body collisions

These body values are used by more than one species. `TameAndFill.py` reads the
creature's name before touching anything with one of these bodies, and walks away
if it cannot resolve the name - a missed tame beats a pet with no deed for it.

| Body | Species sharing it |
|---|---|
| `0xC` | dragon, frost dragon, greater dragon |
| `0x27` | greater mongbat, mongbat |
| `0x33` | corrosive slime, slime |
| `0x3B` | dragon, frost dragon, greater dragon |
| `0x3C` | cold drake, drake |
| `0x3D` | cold drake, drake |
| `0x62` | hell hound, ice hound |
| `0x74` | dread warhorse, nightmare |
| `0xC9` | cat, hell cat |
| `0xCD` | jack rabbit, rabbit |
| `0xDC` | llama, ridable llama |
| `0xEE` | rat, sewer rat |
| `0x2CB` | high plains boura, lowland boura, ruddy boura |
| `0x2CC` | battle chicken lizard, chicken lizard |
| `0x2DE` | slith, stone slith |
