# THE CONTAINER'S `grep` IS NOT YOUR `grep` — AND IT DISAGREES SILENTLY, IN THE DIRECTION THAT READS AS ABSENCE

**Recorded 2026-09-05, from the structural verification of the composed deploy.**

> **A COUNT TAKEN INSIDE THE CONTAINER IS NOT THE SAME MEASUREMENT AS THE SAME
> COMMAND TAKEN ON THE HOST.** The app image ships BusyBox. Production
> verification is *"grep the built chunk"*, so the instrument that answers the
> most-repeated question in this programme is not the one anybody tested it with.

## The measurement

Same file, same pattern, same flags, two greps:

| where | command | result |
|---|---|---|
| inside the container (BusyBox v1.37.0) | `grep -o -F "data-skin=rounds]" <file> \| wc -l` | **1** |
| inside the container | `grep -o -E "data-skin=rounds]" <file> \| wc -l` | **290** |

**`-F` and `-E` differ by 289 on identical input.** GNU `grep -o -F` returns
every occurrence; BusyBox's does not. Nothing warns, nothing exits non-zero, and
`1` is a perfectly plausible answer to *"is this token in the bundle?"* — it is
the answer that means **yes, once**, when the truth is **yes, 290 times**.

## Why this class is worse than a wrong number

⚠️ **IT FAILS TOWARD ABSENCE, WHICH IS THE ANSWER THAT ENDS AN ENQUIRY.** The
questions asked of a shipped bundle are *did the flag inline?*, *did this
passenger's code reach the image?* A low or zero count reads as **"the deploy did
not land"** — alarming and therefore investigated. But the same defect pointed
the other way, at a token that *should* be gone, returns a small number that
reads as **"nearly clean"** and gets waved through.

⚠️ **AND `grep -c` EXITS 1 AT ZERO.** Under `set -e`, or in any pipeline whose
status is read, a legitimate zero *kills the script* rather than reporting a
zero. So `|| true` on a counting grep is not sloppiness — it is load-bearing,
and removing it as tidy-up converts a measurement into a crash.

## The practice

- **Take structural counts on the HOST**, against the file the container serves,
  or `docker cp` the artifact out and measure it with the grep you know.
- If a count must be taken inside, use **`-E`**, never `-F`, and
  **positive-control it in the same breath** — grep for a token that MUST be
  present and assert it is large. On this deploy the control was `practiceId`
  at **143 files**; without it, four zeros for the tokens under test would have
  been believed.
- ⚠️ **AND CONTROL THE PATH BEFORE THE PATTERN.** The first reading of those
  four tokens used `/app/.next`, which does not exist — the server runs from
  `/app/apps/transcribe-md/.next`. It returned **the same four zeros**, and they
  were *correct by accident*: right answer, broken instrument. The control was
  what separated them, and it is the only thing that could have.

## The general form

> **AN INSTRUMENT INHERITED FROM THE ENVIRONMENT IS AN UNTESTED DEPENDENCY.**
> `grep`, `sed`, `awk`, `date`, `stat` and `readlink` all have BusyBox variants
> that accept the same flags and answer differently. The name being identical is
> exactly what makes the substitution invisible: nothing in the command, the
> exit code or the output says which implementation replied.

This is the same family as *a probe that matches itself* and *a control aimed
where the answer is predetermined* — the check is well-formed and the universe
is wrong. Here the wrong universe is **whose `grep` is running.**
