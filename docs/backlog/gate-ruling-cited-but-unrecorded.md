# A LANDING CHECK FOR RULINGS CITED IN SOURCE BUT NOT RECORDED

**Filed 2026-09-02, after the rule was missed THREE TIMES in one session.**

## The rule and its record

`AGENTS.md` § *WAR-ROOM RULINGS ARE RECORDED BY THE RECEIVING SESSION* requires
a ruling's row to land **in the first commit the session makes**, before
anything is built on it.

| ruling | recorded when | found by |
|---|---|---|
| #162–#165 | after four rulings' work was built, proved and committed | an adversarial lens auditing a permission line |
| #167 | after it was committed and cited in shipped source | an adversarial lens auditing documentation |
| #168 | after it was committed | the session itself, immediately |

Detection improved each time. **Behaviour did not change once.**

## Why a habit is the wrong instrument here

Every one of the three happened to a session that had just written about the
previous one. The rule is not being disagreed with, forgotten under pressure, or
skipped for cost — it is simply not attached to any moment that forces it.

## The check, which is one grep

A commit whose diff cites `#N` in tracked source or tests, where
`grep -c '#N' docs/foundation/RULINGS.md` scores **zero**, is refused:

    cited=$(git diff --cached -U0 | grep -oE '#1[0-9]{2}' | sort -u)
    for n in $cited; do
      grep -q -- "$n" docs/foundation/RULINGS.md || refuse "$n cited but unrecorded"
    done

⚠️ **The obvious version has two defects worth pre-empting.** It must read the
STAGED diff, not the working tree, or it judges a different set from the one
being committed. And it must ignore citations inside `docs/` — a canon entry
discussing a historical ruling is not a claim that the ruling is current — or it
will red on every retrospective.

## Why it is filed rather than built

Building it mid-arc is how the last four scope expansions started. It belongs to
the hooks slice with `pre-commit` and `pre-push`, where the other landing checks
already live and where its own arms can be written without competing with a
clinical fix for attention.
