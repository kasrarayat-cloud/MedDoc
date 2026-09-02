# `lsmod` IS SILENT ABOUT BUILT-INS — AND A KNOWN FIX DOES NOT TRANSFER BY NAME

**Recorded 2026-09-01, by owner ruling #163.**

## The measurement

A CI host was losing RAM to hypervisor ballooning. This programme had met that
exact failure before, on the app VPS, where the cure was recorded plainly:
*unbind the virtio-balloon driver and blacklist the module*. So the first probe
was the obvious one:

```
lsmod | grep -i balloon      ->  (nothing)
```

Which reads as **"no balloon here"** and points the investigation elsewhere.

It was wrong. The balloon was present, bound, and actively reclaiming:

```
/sys/bus/virtio/devices/virtio0/device = 0x0005    ← virtio balloon
driver                                 = virtio_balloon
/boot/config-$(uname -r): CONFIG_VIRTIO_BALLOON=y  ← BUILT IN
```

**`lsmod` lists loadable MODULES.** A driver compiled into the kernel appears in
none of its output, ever. The probe was not broken; it was answering a narrower
question than the one being asked, and its zero was indistinguishable from the
answer that mattered.

## And the fix did not transfer — which is the larger half

The recorded remedy was **blacklist the module**. You cannot blacklist a
built-in. The two boxes had the same *symptom*, the same *device*, and the same
*vendor driver by name* — and completely different remedies, because one shipped
it as a module and one compiled it in.

> **A REMEDY IS BOUND TO A CONFIGURATION, NOT TO A SYMPTOM'S NAME.** "We have
> seen this before and here is what fixed it" is a hypothesis about the new
> machine, and it is tested the same way as any other.

The dangerous version of this is not the failed fix. It is that reaching for the
known remedy *first* makes the probe you run be the one that would confirm it —
and here that probe returned a zero that argued the problem did not exist.

## The practice

- **Ask the OWNER of the state, not a listing of one implementation of it.** For
  a driver that is `/sys/bus/*/devices/*/driver` and the kernel config; `lsmod`
  is a convenience. Same move as *ask `tmux has-session`, not `pgrep -f`*
  ([canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)).
- **When a precedent supplies the remedy, re-derive the PRECONDITION the remedy
  needs.** Here: *does a module exist to blacklist?* One line, and it inverts the
  plan.
- **Record the configuration alongside the fix**, not just the fix. The app VPS
  note said "blacklisted the module" and was true; what it lacked was "on a box
  where it IS a module", which is exactly the fact the next box contradicted.
