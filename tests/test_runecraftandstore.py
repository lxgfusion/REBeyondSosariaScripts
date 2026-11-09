"""
Offline tests for RuneCraftAndStore.py.
=======================================

    python tests/test_runecraftandstore.py

WHAT IS WORTH TESTING HERE. The script's promise is a NEGATIVE one: it works
out what your gear would need, crafts it, stores it, and **never applies a
rune to anything you own**. A promise like that is not proved by the happy
path working -- it is proved by the apply machinery being unreachable.

So these are structural, read off the shipped source with `ast`. An 11,000
line script that drives gumps cannot be run offline, but "can control ever
reach run_slot_application()?" is a question the call graph answers exactly,
and it is the question that matters.

The rest of the file is upstream's (Omniwrath's) and tested by them; the
gump-press guard shared with the fork has its own suite in
test_omnirunecraftfork.py.
"""

import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "Scripts", "RuneCraftAndStore.py")

# THE FORK IS NOT IN THIS REPO, and this is the only test that wants it.
# RuneCraftAndStore.py is published; OmniRuneCraftFork.py is a local file,
# so section 4 below skips itself rather than failing on a clone. A skip is
# announced, never silent - a comparison that quietly stops happening is
# worse than one that never existed.
FORK = r"E:\uoclients\RazorEnhanced\Scripts\OmniRuneCraftFork.py"

FAILURES = []


def check(label, got, want):
    ok = got == want
    if not ok:
        FAILURES.append(label)
    print("%-4s %-56s got=%-22r want=%r"
          % ("ok" if ok else "FAIL", label, got, want))


def load(path):
    with io.open(path, encoding="utf-8") as handle:
        return ast.parse(handle.read())


def functions(tree):
    """TOP-LEVEL functions only, and LAST definition wins.

    Walking the whole tree would pull in methods - AssumedItem.__init__ is
    one - and compare them against the fork as if they were new module
    functions. Last-wins also matches how Python itself resolves the three
    deliberate overrides in this file, so "what does find_slot_items do
    here" gets the same answer from this test as from the running script.
    """
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            out[node.name] = node
    return out


def calls(funcs, name):
    """Every plain-name function this one calls."""
    node = funcs.get(name)
    if node is None:
        return set()
    return set(i.func.id for i in ast.walk(node)
               if isinstance(i, ast.Call) and isinstance(i.func, ast.Name))


def reachable(funcs, root):
    """Everything reachable from `root`, following plain-name calls."""
    seen, todo = set(), [root]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo.extend(calls(funcs, name))
    return seen


def config(tree):
    out = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], "id", None)):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def main():
    tree = load(SCRIPT)
    funcs = functions(tree)
    conf = config(tree)

    print("=" * 96)
    print("1. IT CANNOT APPLY A RUNE - the promise, proved by reachability")
    print("=" * 96)

    from_main = reachable(funcs, "main")
    check("run_slot_application is unreachable from main()",
          "run_slot_application" in from_main, False)
    check("prepare_and_apply_one_stat is unreachable from main()",
          "prepare_and_apply_one_stat" in from_main, False)
    check("and nothing at all calls prepare_and_apply_one_stat",
          [f for f in funcs if "prepare_and_apply_one_stat" in calls(funcs, f)],
          [])

    # The apply code is still PRESENT - left in so a diff against the fork
    # stays readable - so "unreachable" has to be checked, not "deleted".
    check("the apply code is still in the file, just orphaned",
          "run_slot_application" in funcs, True)

    # AND THE PROGRESS SCREEN STAYS DARK (2026-11-09). The screen that counts
    # breaks and items during an apply run is shared code, and this fork's own
    # run_application_flow() arms it - so "it is never armed" is NOT the
    # guarantee. The guarantee is that arming is not showing, and it rests on
    # a chain of three facts, one per check:
    #
    #   only _apply_progress_redraw() draws,
    #   it refuses unless the state is live,
    #   only apply_progress_pass() sets live,
    #   and only run_slot_application() calls that - which is unreachable
    #   from main(), per the checks above.
    #
    # Checked rather than trusted because the first version of this screen drew
    # on arming, which would have given this script a window reading "Applying
    # to Shoes -- Items: 0 in the pack" for the length of a craft that applies
    # nothing to anything. That is not a progress screen, it is a false
    # statement about what the script is doing.
    check("nothing draws the progress screen but the throttle",
          sorted(f for f in funcs
                 if "_draw_apply_progress" in calls(funcs, f)),
          ["_apply_progress_redraw"])
    check("and only the apply loop can make it live",
          sorted(f for f in funcs
                 if "apply_progress_pass" in calls(funcs, f)),
          ["run_slot_application"])
    check("so the call that would show it is unreachable from main()",
          "apply_progress_pass" in from_main, False)
    # THE GATE ITSELF, not the call graph. A mutation run on 2026-11-09 deleted
    # the `live` test from _apply_progress_redraw() and all three checks above
    # still passed: it changes nobody's callers, it just lets
    # apply_progress_stat() - which IS reachable from main() in this fork -
    # draw. The fork's own suite caught it; this one is the only suite a clone
    # gets, so it has to catch it too.
    _guard = [s for s in funcs["_apply_progress_redraw"].body
              if isinstance(s, ast.If)]
    check("the throttle has a guard at all", bool(_guard), True)
    check("and it refuses to draw unless the screen is live",
          any(isinstance(n, ast.Constant) and n.value == "live"
              for n in ast.walk(_guard[0].test)) if _guard else False, True)

    print()
    print("=" * 96)
    print("2. THE FLOW STORES INSTEAD")
    print("=" * 96)
    flow = calls(funcs, "run_application_flow")
    check("the flow calls the store twin",
          "prepare_and_store_one_stat" in flow, True)
    check("and not the apply one", "prepare_and_apply_one_stat" in flow, False)

    store = calls(funcs, "prepare_and_store_one_stat")
    check("it estimates what the gear needs",
          "estimate_applications_needed" in store, True)
    check("it counts what is already held", "runes_already_held" in store,
          True)
    check("it crafts", "craft_n_runes" in store, True)
    check("it puts the result in the key",
          "absorb_backpack_into_key" in store, True)

    # Counting, not withdrawing: pulling stock out only to put it back is a
    # gump cycle spent undoing itself.
    check("it does NOT withdraw the stock it is adding to",
          "withdraw_runes_from_storage" in store, False)
    held = calls(funcs, "runes_already_held")
    check("the count reads the key's balance",
          "cached_storage_balance" in held, True)
    check("and the pack", "count_rune_amount" in held, True)

    print()
    print("=" * 96)
    print("3. NO PERK DEED IS EVER SPENT")
    print("=" * 96)
    print("   The perk lowers the chance of breaking an ITEM while applying")
    print("   one. Nothing is applied, so a deed here is an hour burned.")
    print()
    DEED = {"use_perk_deed_if_needed", "withdraw_perk_deed",
            "withdraw_perk_deed_from_master_key",
            "withdraw_perk_deed_from_home_chest", "stock_perk_deed_at_start"}
    check("no deed call is reachable from main()",
          sorted(DEED & from_main), [])
    check("the flow does not even look for one",
          sorted(DEED & flow), [])
    check("the Master Key codex is off",
          conf.get("PERK_FROM_MASTER_KEY"), False)
    check("and so is the trip to the home chest",
          conf.get("PERK_FROM_HOME_CHEST"), False)

    # THE DEED IS OUT OF THE SETUP SCREEN TOO. A chest to target and a buff
    # timer to watch are two things to get wrong in exchange for nothing,
    # and a red "not set" row reads as "you are not ready" when you are.
    CHEST = {"find_perk_deed_chest", "perk_deed_chests_here",
             "configured_perk_chest", "deed_expiration_known"}
    check("no perk-chest or deed-timer code runs from main()",
          sorted(CHEST & from_main), [])

    src = io.open(SCRIPT, encoding="utf-8").read()
    grid = src.split("SETUP_ROW_GRID = (")[1].split(")")[0]
    check("the Perk Deed Chest row is off the setup grid",
          "PERK_CHEST_ROW_LABEL" in grid, False)
    check("and the Better Rune Crafting row with it",
          "PERK_STATUS_ROW_LABEL" in grid, False)

    # capture_perk_chest survives as a stub so a diff against the fork
    # still lines up. It must not open a cursor.
    check("targeting a perk chest is disarmed, not merely unreferenced",
          "Target" in calls(funcs, "capture_perk_chest"), False)

    print()
    print("   -- but Infinite Backpack Weight is a DIFFERENT perk --")
    print("      it decides whether the craft respects your weight limit,")
    print("      so its read has to survive all of the above")
    check("the weight check still runs", "weight_limit_applies" in from_main,
          True)
    check("and still reads the perks gump",
          "refresh_gate_cache" in from_main, True)
    check("through the throttle, not raw",
          "read_active_perks" in calls(funcs, "weight_limit_applies"), False)

    print()
    print("=" * 96)
    print("4. IT IS STILL THE FORK UNDERNEATH")
    print("=" * 96)
    if os.path.exists(FORK):
        fork_funcs = functions(load(FORK))
        shared = set(fork_funcs) & set(funcs)
        # EXACTLY, not "most of". The user chose a separate file over a mode
        # in the fork, so divergence is the standing risk here - a fix made
        # in one reaches the other only if somebody carries it. Naming the
        # difference precisely means this test fails the moment the two
        # drift apart for any reason other than the two functions that are
        # SUPPOSED to differ.
        check("nothing of the fork's was lost",
              sorted(set(fork_funcs) - set(funcs)), [])
        check("and it adds exactly the two store functions",
              sorted(set(funcs) - set(fork_funcs)),
              ["prepare_and_store_one_stat", "runes_already_held"])
        check("which is nearly all of it shared", len(shared),
              len(fork_funcs))
    else:
        print("     (skipped: %s is not in this repo, so the three"
              % os.path.basename(FORK))
        print("      fork-comparison checks cannot run here. The rest of"
              " this section can.)")
    check("the updater is still disabled", isinstance(
        [s for s in funcs["update_offer_at_start"].body
         if not isinstance(s, ast.Expr)][0], ast.Return), True)
    check("and it is named apart from the fork",
          conf.get("FORK_VERSION"), "craftandstore-1")

    # The gump-press guard came from the fork and must not have been lost.
    for name in ("perk_press", "gump_button_ids", "gump_textentry_ids"):
        check("the %s guard came across" % name, name in funcs, True)

    print()
    print("=" * 96)
    print("5. IT DOES NOT NEED THE GEAR - 50 assumed items, always")
    print("=" * 96)

    # SHADOWING IS THE MECHANISM, so the order of definition IS the
    # behaviour. An override placed above its original is simply dead.
    at = {}
    for node in load(SCRIPT).body:
        if isinstance(node, ast.FunctionDef):
            at.setdefault(node.name, []).append(node.lineno)
    for name in ("find_slot_items", "snapshot_property_values",
                 "ensure_slot_source"):
        lines = at.get(name, [])
        check("%s is overridden once" % name, len(lines), 2)
        check("  ...and the override comes last", lines[1] > lines[0], True)

    # The count itself is the user's dial, so the test follows the file
    # rather than pinning a number the file is allowed to change. What IS
    # pinned is that everything downstream agrees with it.
    count = conf.get("ASSUMED_ITEM_COUNT")
    check("the count is set and sane", isinstance(count, int) and count > 0,
          True)
    check("and it is the fifty that was asked for", count, 50)
    check("each starting from nothing", conf.get("ASSUMED_START_VALUE"), 0)

    # Run the real overrides. They are pure apart from clear_slot_source().
    env = {"__name__": "assumed_under_test",
           "clear_slot_source": lambda: None}
    wanted = {"AssumedItem", "find_slot_items", "snapshot_property_values",
              "ensure_slot_source"}
    body = [n for n in load(SCRIPT).body
            if (isinstance(n, ast.FunctionDef) and n.name in wanted
                and n.lineno > 9000)
            or (isinstance(n, ast.ClassDef) and n.name in wanted)
            or (isinstance(n, ast.Assign) and len(n.targets) == 1
                and getattr(n.targets[0], "id", "").startswith("ASSUMED_"))]
    exec(compile(ast.Module(body=body, type_ignores=[]), SCRIPT, "exec"), env)

    items = env["find_slot_items"]({"label": "Neck"})
    check("it hands back that many stand-ins", len(items), count)
    check("with distinct serials", len(set(i.Serial for i in items)), count)
    check("all negative, so none can be a real item",
          all(i.Serial < 0 for i in items), True)

    # The "Work 3" feature narrows by serial, which cannot mean anything
    # against twenty identical assumptions - so it must be ignored, not
    # half-honoured into an empty pool.
    check("a serial restriction is ignored rather than emptying the pool",
          len(env["find_slot_items"]({}, restrict_serials=[1, 2, 3])), count)
    check("and in_pack_only changes nothing either",
          len(env["find_slot_items"]({}, in_pack_only=True)), count)

    vals = env["snapshot_property_values"]([], {"label": "In Luck"})
    check("the values match the count, whatever pool is given",
          len(vals), count)
    check("and every one starts at nothing", set(vals), set([0]))
    check("even when handed a pool of another size",
          len(env["snapshot_property_values"]([1, 2], {})), count)

    slot = {"label": "Neck"}
    check("the slot is returned as-is, with no chest prompt",
          env["ensure_slot_source"](slot) is slot, True)

    print()
    print("=" * 96)
    if FAILURES:
        print("%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
