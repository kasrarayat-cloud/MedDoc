# A RULE THAT DEPENDS ON REMEMBERING HAS A FAILURE RATE — MEASURE IT, THEN MECHANIZE

**Recorded 2026-09-02, from three consecutive failures of one rule in one
session.**

## The rule and its record

`AGENTS.md` requires the receiving session to record a war-room ruling in the
FIRST commit it makes, before building anything on it. It exists because a
ruling that lives only in a transcript lets a later session reach the opposite
conclusion just as confidently.

| ruling | recorded | caught by |
|---|---|---|
| #162–#165 | after four rulings' work was built, proved and committed | a lens auditing an unrelated permission line |
| #167 | after it was committed and cited by number in shipped source | a lens auditing documentation |
| #168 | after it was committed | the session itself, immediately |

## ⚠️ THE FINDING IS NOT THE THREE MISSES. IT IS WHAT IMPROVED AND WHAT DID NOT.

**Detection improved every time** — from an unrelated audit, to a documentation
audit, to self-catch within a minute. **Behaviour did not change once.** All
three happened to a session that had just written about the previous one; the
second and third happened while the archive containing the apology was open.

> **Writing a lesson down does not cause obedience to it. Nor does having just
> written it down. Nor does having been corrected for it twice.**

That is not a claim about carelessness. The rule is not disagreed with, not
expensive, and not forgotten under load — it is simply **not attached to any
moment that forces it**. Every other landing obligation in this repository has
a hook, a script, or a CI gate. This one had a paragraph.

## The cure, and why it is cheap

    cited=$(git diff --cached -U0 | grep -oE '#1[0-9]{2}' | sort -u)
    for n in $cited; do
      grep -q -- "$n" docs/foundation/RULINGS.md || refuse "$n cited but unrecorded"
    done

⚠️ Two defects to pre-empt: read the **staged** diff, or it judges a different
set from the one being committed; and ignore citations inside `docs/`, or every
retrospective discussing a historical ruling reds.

## The generalisable move

**When a process rule fails twice, stop restating it and start counting.** The
count is the argument: three failures under three escalating levels of vigilance
is evidence about the INSTRUMENT, not about the operator — the same reading
canon applies to a heuristic falsified three times.

⚠️ **AND DO NOT BUILD THE CURE MID-ARC.** The fix here is one grep, and it was
still deferred to its own slice: four scope expansions in this session began as
a small obviously-correct addition to work already in flight. A rule about
landing discipline is a poor thing to land carelessly.
