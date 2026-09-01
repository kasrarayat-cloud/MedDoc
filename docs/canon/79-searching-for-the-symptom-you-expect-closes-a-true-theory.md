# SEARCHING FOR THE SYMPTOM YOU EXPECT IS HOW A TRUE THEORY GETS CLOSED

**Recorded 2026-09-01, by owner ruling #163, from the CI-box outage.**

The memory theory was right from the first hour. It was nearly abandoned because
the grep written to test it searched for the wrong words.

## The measurement

A CI host became unresponsive. The working hypothesis was memory exhaustion, and
the checklist said *name the cause from the kernel log*. So:

```
journalctl -b -1 | grep -icE "out of memory|oom-kill|killed process"   ->  0
journalctl -b -1 | grep -icE "no space left|I/O error|EXT4-fs error"   ->  0
```

**Zero on both.** Read plainly that closes memory *and* disk and leaves nothing.

The instrument was fine — the same journal returned **208,237 lines**. The token
list was wrong. What the log actually contained was:

    systemd-journald: Under memory pressure, flushing caches.
    systemd-resolved: Under memory pressure, flushing caches.

plus docker healthchecks degrading `19.7s → 34.3s → 1m9.5s → "failed fatally"`,
and `sar` recording available memory at **883 MB → 143 MB → 26 MB**.

**The OOM killer never fired.** The machine livelocked *before* the killer
engaged — thrashing, unable to schedule, not killing anything. `oom-kill` is the
signature of a system that recovered by sacrificing a process. A system that
never recovers never writes it.

## The generalisable half

> **A hypothesis names a MECHANISM. A grep names a STRING. When the two are
> chosen in the same breath, the grep tests your vocabulary and reports the
> answer as though it tested the machine.**

The failure is not a missing token — it is that the token list was derived from
the *expected outcome* of the mechanism rather than from the mechanism's whole
range. "Memory exhaustion" has at least three distinct log signatures — OOM
kill, allocation failure, and sustained pressure without either — and only the
first was searched for. **The one that was skipped is the one that describes a
box too far gone to kill anything.**

## The practice

- **Before believing a zero, ask what a POSITIVE would have looked like** — and
  whether the mechanism has more than one positive. If it has three, search for
  three.
- **Read the tail regardless.** The decisive lines here were found by reading
  what the log *did* say in its final hour, not by asking whether it said the
  expected thing. A greppable theory is a hypothesis about wording.
- **Two zeroes covering opposite explanations is a signal about the SEARCH**, not
  a finding about the system — the sibling of
  [canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)'s
  *two zeroes with opposite meanings is one broken instrument*, one level up: the
  instrument works and the QUESTION is malformed.

**Related:** [canon 30](30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md)
— a sweep is defeated by an incomplete token list at least as often as by a
missing form. That entry is about sweeping code. This is the same defect aimed at
a diagnosis, where the cost is not a missed occurrence but an abandoned true
explanation.
