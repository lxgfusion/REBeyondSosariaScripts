# Animal Taming server messages

Extracted from ServUO `Scripts/Skills/AnimalTaming.cs` (RunUO lineage — most
freeshards keep these verbatim). Verify against your shard's source if any
branch of a script misfires.

| Cliloc | Text | Meaning |
|---|---|---|
| 502789 | Tame which animal? | target cursor prompt |
| 1010597 | You start to tame the creature. | attempt began (you) |
| 1010598 | *begins taming a creature.* | attempt began (bystanders) |
| **502799** | **It seems to accept you as master.** | **success** |
| **502798** | **You fail to tame the creature.** | soft fail — retry |
| 502805 | You seem to anger the beast! | soft fail — retry |
| 502794 | The animal is too angry to continue taming. | soft fail — retry |
| 502795 | You are too far away to continue taming. | out of range mid-attempt |
| 1049654 | You do not have a clear path to the animal you are taming... | LOS broken |
| 502804 | That animal looks tame already. | already tame |
| 502797 | That wasn't even challenging. | already yours |
| 1049655 | That creature cannot be tamed. | untameable species |
| 502801 | You can't tame that! | invalid target |
| 502806 | You have no chance of taming this creature. | skill too low |
| 1005615 | This animal has had too many owners and is too upset for you to tame. | owner cap |
| 1049652 | That creature can only be tamed by females. | gender lock |
| 1049653 | That creature can only be tamed by males. | gender lock |
| 1054025 | You must subdue this creature before you can tame it! | must damage first |
| 1049611 | You have too many followers to tame that creature. | control slots full |
| 502802 | Someone else is already taming this. | contested |
| 502796 | You are dead, and cannot continue taming. | ghost |

## Ranges

- **Initial target:** must be within **3 tiles** of the creature.
- **Continuing the attempt:** the server re-checks `InRange(creature, 7)` on each
  tick; drifting past 7 tiles aborts with 502795.

Practical consequence: **stay adjacent for the whole attempt.** The 7-tile figure
is the hard cutoff, not a safe working distance — the same tick also runs the
line-of-sight check (1049654), which a wandering creature breaks long before it
gets 7 tiles away. Trailing at 3-4 tiles loses attempts to trees, walls and
corners. `TameAndFill.py` holds `STAY_DIST = 1` and re-closes every 150 ms.

## Species reference

| Creature | Body | Hex | Min tame skill |
|---|---|---|---|
| Unicorn | 122 | `0x7A` | 95.1 |
| Ki-Rin | 132 | `0x84` | 95.1 |

Both are 2-control-slot mounts on stock RunUO/ServUO.
