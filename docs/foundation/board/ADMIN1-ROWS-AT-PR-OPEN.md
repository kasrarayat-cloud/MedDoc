# BOARD FILING — §2.5 ROWS AT PR-OPEN (Design/Admin)

**Filed 2026-09-06 by the custom-file session, from the `ff993c3a` deploy.**

## WHAT HAPPENED

`20260905000000_admin1_practice_seat_audit_actions` reached production inside
**this lane's** deploy, with **no §2.5 rows from its author**.

    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_SEAT_INVITED';
    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ROLE_CHANGED';
    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_ADMIN_REFUSED';

⚠️ **PERMANENTLY IRREVERSIBLE.** Postgres has no `ALTER TYPE … DROP VALUE`, and
the migration's own header says so. Once applied, these three values exist for
the life of the database.

## WHY IT IS FILED RATHER THAN JUST FIXED

Nobody bypassed a gate. The change was merged correctly under its own PR's
checks, and it then rode a deploy somebody else declared — **overtaken, not
overridden**. Both parties behaved correctly and an irreversible act still
reached production unjudged by its author.

The deploying session can measure what a change TOUCHES. **Only the author can
say what it is SUPPOSED to do, and therefore what would be a finding.** A
derived row for an enum addition can check cardinality; it cannot know that
`USER_ROLE_CHANGED` was deliberately not reused because practice role and system
role are different axes — which is the reasoning in that migration's own header
and exactly the kind of thing a row should assert.

## THE ASK

**Author §2.5 rows at PR-OPEN time for every runtime PR — migrations
especially.** One file per PR in `docs/foundation/deploys/rows/PR-<n>.md`,
naming what must change, what must not, and the falsifier for each.

⚠️ **THIS IS THE SECOND OCCURRENCE OF THE CLASS.** The `b54a3b3a` deploy found
**8 passengers with zero authored rows**; this one found **15 of 16**. The
standing rule was made after the first and has not yet changed behaviour outside
this lane — which is why the custom-file session is also landing a **CI gate**
that fails a runtime PR carrying no rows file. A rule that does not change what
happens becomes mechanism, or it becomes a wish.

## WHAT THIS DEPLOY DID ABOUT IT

Declared the migration **by name**, with three derived rows (`A1-1` cardinality
153 → 156; `A1-2` `audit_logs` row count unchanged; `A1-3` zero rows carrying
the new actions), and labelled them **derived** so nobody reads them as the
author's.
