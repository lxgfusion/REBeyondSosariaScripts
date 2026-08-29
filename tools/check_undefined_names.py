"""Catch names a surgical patch referenced but never delivered.

Patching four diverging copies piece by piece can leave one calling a helper
that only landed in another. Python will not say so until that line runs in
game, which is the worst place to find out.

Walks the AST, collects every module-level definition, and reports any global
name that is read but never defined and is not a builtin or a Razor API object.
"""
import ast
import builtins
import sys

RAZOR = {
    "Misc", "Player", "Items", "Mobiles", "Journal", "Target", "Gumps",
    "Timer", "Spells", "PathFinding", "Statics", "Sound", "Trade", "AutoLoot",
    "BuyAgent", "SellAgent", "Restock", "Organizer", "Dress", "Friend",
    "CUO", "DPSMeter", "Vendor", "PacketLogger", "ScriptTimer",
}


def defined_names(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, (ast.For, ast.While, ast.If, ast.Try, ast.With)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    names.add(sub.id)
    return names


def local_names(func):
    """Everything bound inside a function: args, assignments, comprehensions."""
    names = set()
    # Arguments of this function AND of every lambda and nested function
    # inside it. Nested scopes see the enclosing one, so treating the whole
    # subtree as a single scope is the right over-approximation here - the
    # thing being hunted is a GLOBAL helper that does not exist anywhere.
    for node in ast.walk(func):
        args = getattr(node, "args", None)
        if isinstance(args, ast.arguments):
            for group in (args.posonlyargs, args.args, args.kwonlyargs):
                for arg in group:
                    names.add(arg.arg)
            if args.vararg:
                names.add(args.vararg.arg)
            if args.kwarg:
                names.add(args.kwarg.arg)
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def check(path):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)

    known = defined_names(tree) | set(dir(builtins)) | RAZOR
    missing = {}

    # Top-level functions only. local_names already walks the whole subtree,
    # so analysing a nested function again on its own would just re-report the
    # enclosing scope's variables as undefined.
    for func in [n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        bound = local_names(func) | known
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in bound:
                    missing.setdefault(node.id, []).append(
                        "%s:%d" % (func.name, node.lineno))

    return missing


def check_module_order(path):
    """Names used at MODULE level before they are defined.

    Module code runs top to bottom, so a constant referenced inside a literal
    has to appear above it - unlike a function body, which is not executed
    until everything is loaded. check() deliberately ignores order, so it
    cannot see this class of fault: RESTOCK_KEYS reading WOOD_STORAGE_CONTEXT
    forty lines before that name existed parsed cleanly and raised NameError
    the moment the script was loaded.
    """
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), path)

    defined = {}
    problems = []
    safe = set(dir(builtins)) | RAZOR

    def runs_now(node):
        """The parts of a top-level statement that execute at import time.

        A def's BODY does not - it runs when called, by which time the whole
        module is loaded. Only its decorators and its argument defaults are
        evaluated at definition time. Walking the body instead reports every
        local variable in the file as out of order, which is what the first
        version of this did.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            parts = list(getattr(node, "decorator_list", []))
            args = getattr(node, "args", None)
            if args is not None:
                parts += [d for d in list(args.defaults) +
                          list(args.kw_defaults) if d is not None]
            parts += list(getattr(node, "bases", []))
            return parts
        return [node]

    for node in tree.body:
        # Names this statement binds WITHIN itself - a for-loop variable, or
        # anything assigned inside an `if __name__` block - are available to
        # the rest of that same statement. Without this every loop variable
        # reads as used-before-defined.
        own = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                own.add(sub.id)
            elif isinstance(sub, ast.ExceptHandler) and sub.name:
                own.add(sub.name)

        # Everything this statement READS as it executes.
        for part in runs_now(node):
            for sub in ast.walk(part):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    if sub.id in safe or sub.id in defined or sub.id in own:
                        continue
                    problems.append((sub.id, getattr(sub, "lineno", 0)))
        # ...and everything it DEFINES, which later statements may use.
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                defined[sub.id] = True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            defined[node.name] = True
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                defined[(alias.asname or alias.name).split(".")[0]] = True

    # Only report names that ARE defined later - anything else is already
    # covered by check() and would just be reported twice.
    later = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            later.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            later.add(node.name)
    return [(name, line) for name, line in problems if name in later]


if __name__ == "__main__":
    bad = 0
    for path in sys.argv[1:]:
        missing = check(path)
        out_of_order = check_module_order(path)
        label = path.split("Scripts")[-1]
        if not missing and not out_of_order:
            print("ok    %s" % label)
            continue
        bad += 1
        print("FAIL  %s" % label)
        for name in sorted(missing):
            print("        %-24s used in %s"
                  % (name, ", ".join(missing[name][:3])))
        for name, line in sorted(set(out_of_order)):
            print("        %-24s used at module level on line %d, before it "
                  "is defined" % (name, line))
    sys.exit(1 if bad else 0)
