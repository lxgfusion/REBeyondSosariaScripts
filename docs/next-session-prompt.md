# Prompt for the next session

Paste this as the first message.

---

Continuing work on the Razor Enhanced scripts.

Read `docs/session-handoff-2026-08-16.md` first — it has the state of all four
scripts, what each fix was, and what is still open. `CLAUDE.md` has the
conventions and the API gotchas and loads automatically.

**The important thing: almost nothing from the last session has been confirmed
in game.** Four scripts changed substantially and only the diagnostics' own
output was ever verified live. Do not build new features on top of that until
we have run them.

Current versions, all committed and pushed (`main` is level with origin):

- `resource_order_runner.py` — `2026-08-13.32`
- `COVFarm.py` — `1.6.0`
- `harvest_runner.py` and `TameAndFill.py` — no version marker yet

What I want to do this session, roughly in order:

1. I will run each script and paste the journal back. Help me read it —
   especially the lines the last session added to answer open questions:
   - `PRIORITY Iron Ingots took nothing: N on hand, N spendable` — settles
     whether Iron is a census problem or just has no orders in the book
   - `The Completed filter ('Yes' in filter box 4 ...) did not narrow the list`
     — means the finished-order pull is filtering the wrong column
   - `pack full by ITEM COUNT: N of M items` — the harvest runner's new
     explanation for why it wants to go home
   - `THREAT: <creature> closed N -> M tiles` — the taming script naming what
     it thinks is coming for me, so I can check it against what I can see

2. Fill in the five missing scale hues in `resource_order_runner.py` from the
   runner's own stock report. Do not guess them.

3. Add a `SCRIPT_VERSION` to `harvest_runner.py` and `TameAndFill.py` and print
   it as the first log line, like the other scripts do.

4. Once I have confirmed the threat detection names the right creatures, wire
   up the attacking half in `TameAndFill.py`. The spell choice already works —
   it weighs base damage against resistance, so it picks Energy Bolt for a
   hiryu rather than Harm.

Two standing rules from last session that saved a lot of time:

- **Ship a diagnostic before a fix** when the cause is not certain. The Copper
  Ingots bug survived three confident-but-wrong diagnoses; the diagnostic found
  it in one run.
- **Shard data comes from ServUO source, not from memory or a wiki.** There are
  extractors in `tools/` for creature resistances and spell damage.

Do not sync `harvest_runner.py` between its four copies — they differ on
purpose, and the live copies carry per-character serials and a Carpenter rune
setting the repo does not. Patch each one surgically.
