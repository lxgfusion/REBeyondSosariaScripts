"""
Deed-targeting diagnostic.
==========================

Run this when tame_animals.py tames fine but will not add the pet to the deed.

It asks you to target a taming order deed and an already-tamed pet, then tries
five different double-click-and-target sequences one at a time, reporting exactly
what the client and server did at each step. It stops the moment the pet is
consumed - that tells us which sequence your shard accepts.

Because a working sequence consumes the pet, you only get one shot per pet. Have
one tamed animal standing next to you and nothing else selected.

Everything is printed to the Razor message window. Copy the output back.
"""

import time


DEED_TARGET_TIMEOUT = 4000
RESULT_PAUSE = 1500
PROPS_TIMEOUT = 1500

HUE_INFO = 0x03B2
HUE_GOOD = 0x0044
HUE_WARN = 0x0035
HUE_BAD = 0x0021
HUE_STEP = 0x0480


def log(text, hue=HUE_INFO):
    Misc.SendMessage("[Diag] " + text, hue, False)


def rule(text):
    log("---- " + text + " ----", HUE_STEP)


def journal_lines():
    try:
        return [e.Text for e in Journal.GetJournalEntry(0.0)]
    except Exception as err:
        log("Could not read journal: %s" % err, HUE_BAD)
        return []


def dump_journal():
    lines = journal_lines()
    if not lines:
        log("journal: (silent)", HUE_WARN)
        return
    for line in lines:
        log("journal: %s" % line, HUE_INFO)


def clear_cursor():
    Target.ClearQueue()
    if Target.HasTarget():
        log("A cursor was already open - cancelling it.", HUE_WARN)
        Target.Cancel()
        Misc.Pause(300)
        Target.ClearQueue()
    still = Target.HasTarget()
    if still:
        log("Cursor is STUCK open. This alone would break the deed step.", HUE_BAD)
    return not still


def pet_gone(serial):
    return Mobiles.FindBySerial(serial) is None


def report_state(label):
    log("%s: HasTarget=%s" % (label, Target.HasTarget()), HUE_INFO)


# =============================================================================
# STRATEGIES
# =============================================================================

def strat_baseline(deed_serial, pet_serial):
    """What tame_animals.py does: cursor, short settle, TargetExecute(serial)."""
    clear_cursor()
    Journal.Clear()
    Items.UseItem(deed_serial)
    got = Target.WaitForTarget(DEED_TARGET_TIMEOUT, False)
    log("WaitForTarget -> %s" % got, HUE_INFO)
    if not got:
        dump_journal()
        return False
    report_state("after cursor")
    Misc.Pause(400)
    Target.TargetExecute(pet_serial)
    Misc.Pause(RESULT_PAUSE)
    report_state("after TargetExecute")
    dump_journal()
    return pet_gone(pet_serial)


def strat_long_settle(deed_serial, pet_serial):
    """Same, but wait a full second before answering the cursor."""
    clear_cursor()
    Journal.Clear()
    Items.UseItem(deed_serial)
    got = Target.WaitForTarget(DEED_TARGET_TIMEOUT, False)
    log("WaitForTarget -> %s" % got, HUE_INFO)
    if not got:
        dump_journal()
        return False
    Misc.Pause(1000)
    Target.TargetExecute(pet_serial)
    Misc.Pause(RESULT_PAUSE)
    report_state("after TargetExecute")
    dump_journal()
    return pet_gone(pet_serial)


def strat_mobile_object(deed_serial, pet_serial):
    """Pass the Mobile object to TargetExecute instead of the raw serial."""
    mob = Mobiles.FindBySerial(pet_serial)
    if mob is None:
        log("Pet is not in the mobile list any more.", HUE_WARN)
        return False
    clear_cursor()
    Journal.Clear()
    Items.UseItem(deed_serial)
    got = Target.WaitForTarget(DEED_TARGET_TIMEOUT, False)
    log("WaitForTarget -> %s" % got, HUE_INFO)
    if not got:
        dump_journal()
        return False
    Misc.Pause(400)
    Target.TargetExecute(mob)
    Misc.Pause(RESULT_PAUSE)
    report_state("after TargetExecute(Mobile)")
    dump_journal()
    return pet_gone(pet_serial)


def strat_setlast(deed_serial, pet_serial):
    """Prime Razor's last-target first, then answer the cursor."""
    clear_cursor()
    Journal.Clear()
    Target.SetLast(pet_serial, True)
    Misc.Pause(300)
    Items.UseItem(deed_serial)
    got = Target.WaitForTarget(DEED_TARGET_TIMEOUT, False)
    log("WaitForTarget -> %s" % got, HUE_INFO)
    if not got:
        dump_journal()
        return False
    Misc.Pause(400)
    Target.TargetExecute(pet_serial)
    Misc.Pause(RESULT_PAUSE)
    report_state("after SetLast + TargetExecute")
    dump_journal()
    return pet_gone(pet_serial)


def strat_useitem_target(deed_serial, pet_serial):
    """Items.UseItem's built-in target. Docs warn it fails on some freeshards."""
    clear_cursor()
    Journal.Clear()
    try:
        Items.UseItem(deed_serial, pet_serial, True)
    except TypeError:
        Items.UseItem(deed_serial, pet_serial)
    Misc.Pause(RESULT_PAUSE)
    report_state("after UseItem(deed, pet)")
    dump_journal()
    if Target.HasTarget():
        log("Cursor left open - the built-in target did not answer it.", HUE_WARN)
        Target.Cancel()
    return pet_gone(pet_serial)


STRATEGIES = [
    ("1. baseline (400ms settle, serial)", strat_baseline),
    ("2. long settle (1000ms, serial)", strat_long_settle),
    ("3. TargetExecute(Mobile object)", strat_mobile_object),
    ("4. SetLast then TargetExecute", strat_setlast),
    ("5. Items.UseItem(deed, pet)", strat_useitem_target),
]


# =============================================================================
# MAIN
# =============================================================================

def describe_deed(deed):
    log("Deed serial : 0x%X" % deed.Serial, HUE_INFO)
    log("Deed graphic: 0x%X" % deed.ItemID, HUE_INFO)
    log("Deed name   : %s" % (deed.Name or "(none)"), HUE_INFO)
    log("Deed hue    : %d" % deed.Hue, HUE_INFO)
    log("Deed root   : 0x%X (you are 0x%X)" % (deed.RootContainer, Player.Serial), HUE_INFO)
    Items.WaitForProps(deed, PROPS_TIMEOUT)
    try:
        props = Items.GetPropStringList(deed)
    except Exception as err:
        log("Could not read tooltip: %s" % err, HUE_BAD)
        return
    if not props:
        log("Tooltip is empty - keyword matching will not work on this deed.", HUE_WARN)
        return
    for line in props:
        log("tooltip: %s" % line, HUE_INFO)


def describe_pet(mob):
    log("Pet serial  : 0x%X" % mob.Serial, HUE_INFO)
    log("Pet body    : 0x%X" % mob.Body, HUE_INFO)
    log("Pet name    : %s" % (mob.Name or "(none)"), HUE_INFO)
    log("Pet notor.  : %d  (1 = innocent/yours)" % mob.Notoriety, HUE_INFO)
    log("Pet distance: %d tiles" % Player.DistanceTo(mob), HUE_INFO)


def main():
    rule("deed targeting diagnostic")

    log("Target your taming order deed.", HUE_WARN)
    deed_serial = Target.PromptTarget("The taming order deed", HUE_WARN)
    if deed_serial is None or deed_serial <= 0:
        log("Cancelled.", HUE_BAD)
        return
    deed = Items.FindBySerial(deed_serial)
    if deed is None:
        log("That serial is not an item Razor can see.", HUE_BAD)
        return

    log("Now target the tamed animal you want added.", HUE_WARN)
    pet_serial = Target.PromptTarget("The tamed animal", HUE_WARN)
    if pet_serial is None or pet_serial <= 0:
        log("Cancelled.", HUE_BAD)
        return
    pet = Mobiles.FindBySerial(pet_serial)
    if pet is None:
        log("That serial is not a mobile Razor can see.", HUE_BAD)
        return

    rule("deed")
    describe_deed(deed)
    rule("pet")
    describe_pet(pet)

    rule("cursor hygiene")
    if clear_cursor():
        log("No stale cursor. Good starting state.", HUE_GOOD)

    for label, fn in STRATEGIES:
        if pet_gone(pet_serial):
            break
        rule(label)
        try:
            worked = fn(deed.Serial, pet_serial)
        except Exception as err:
            log("Strategy raised: %s" % err, HUE_BAD)
            worked = False
        if worked:
            rule("SUCCESS")
            log("'%s' worked. Tell Claude which number this was." % label, HUE_GOOD)
            return
        log("No effect.", HUE_WARN)
        Misc.Pause(1000)

    if pet_gone(pet_serial):
        rule("pet consumed")
        log("The pet is gone - one of the sequences above landed.", HUE_GOOD)
        return

    rule("all sequences failed")
    log("None of the five worked. Copy the whole log back - the tooltip and "
        "journal lines will say why.", HUE_BAD)


main()
