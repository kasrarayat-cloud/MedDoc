# A GUARD PROVEN ONLY ON ITS EMPTY BRANCH IS UNPROVEN — MANUFACTURE THE CONDITION

**Recorded 2026-09-01, by owner ruling #163, from the CI-box balloon cure.**

## The measurement

A systemd oneshot was written to unbind a virtio-balloon device at every boot,
because the hypervisor had reclaimed 6.3 of 8 GB and livelocked the machine. The
unbind had already been done by hand, so when the new unit was started to check
it:

```
systemctl start unbind-virtio-balloon.service   ->  exit 0
Active: active (exited)
```

**Green, and worthless.** With nothing bound, the unit's loop iterated over an
empty glob and exited 0 without touching anything. That green says *"the script
parses and its no-op branch works"* — it says nothing whatever about the branch
that has to work at 04:00 after an unattended reboot.

So the condition was **manufactured**: the device was deliberately re-bound, and
the unit run against it.

```
devices bound: 1
journal:       "unbound virtio0"
devices bound: 0
MemTotal:      8,125,636 -> 8,131,780 kB
```

That is the proof. The first run was a formality wearing its clothes.

## The generalisable half

> **A guard's green is only worth what the STATE it ran against could have
> revealed.** Run a fixer when there is nothing to fix, a validator when the
> input is already valid, a cleanup when the tree is already clean — and the
> pass is a fact about the environment, not about the code.

The trap is specific and comfortable: **the fix has usually just been applied by
hand**, which is exactly why the condition is absent when you go to test the
automation of it. The moment you are most likely to verify a repair unit is the
moment its trigger no longer exists.

⚠️ **AND IT IS NOT THE SAME AS "THE MUTATION DID NOT APPLY".** That failure is an
edit which silently did nothing (see *A MUTATION PROOF ASSERTS ITS OWN
APPLICATION*). Here the unit ran perfectly, did exactly what it should have done
given its input, and reported honestly. Nothing malfunctioned. **The defect is in
what was asked of it** — a correct answer to a question that could not
discriminate.

## The practice

- **Name the branch the green exercised, out loud, before believing it.** "This
  proves the no-op path" is a sentence that ends the illusion in five words.
- **Manufacture the condition.** Re-break what you fixed, plant the file, re-bind
  the device, dirty the tree. It is usually one command, and it is the only thing
  that converts the run into evidence.
- **Assert the OBSERVABLE, not the exit code** — `devices bound: 1 -> 0`, a log
  line naming the object, a number that moved. `exit 0` is compatible with doing
  nothing at all, which is precisely the outcome under test.
- **Keep the no-op run too.** Idempotence matters — a boot-time unit will meet
  the empty case on most boots. Both branches are real; only one of them was
  being confused for coverage.

**Related:** [canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)'s
*a control aimed where the answer is predetermined is not a control* — same
family, one step earlier: there the target made the result inevitable, here the
absent condition did.
