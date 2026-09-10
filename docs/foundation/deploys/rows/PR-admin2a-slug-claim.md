# §2.5 AUTHOR ROWS — ADMIN-2a, a human-chosen practice slug

**Written before the act**, per ruling #184 and the ADMIN-1 board filing
(`docs/foundation/board/ADMIN1-ROWS-AT-PR-OPEN.md`). Branch
`feat/admin2a-slug-claim`, based on `origin/main` `6fcd21d0`. Ruling #310.

**CODE-ONLY. The expected delta is: nothing but the image ids.** No migration,
no new `AuditAction` label, no environment variable, no flag. Runtime files:
`lib/practice-write.ts` (the label guard, the P2002 arm, the optional
compare-and-set), `actions/practice-settings.ts` (new server action),
`app/settings/page.tsx` and `app/settings/practice-slug-claim.tsx` (the
owner-only control on `/settings/members`).

⚠️ **THIS DEPLOY PERFORMS NO RE-SLUG.** The RELAY row once said "a one-time
re-slug of the 195". Under #310(b) that step was dropped, and the change is
recorded on the row. A slug moves only when an OWNER submits the claim form
AFTER the deploy — and never at deploy time. **N2 is the falsifier for that.**

## BASELINE — measured 2026-09-10T18:53Z, read-only (`default_transaction_read_only=on`)

These values were measured on the base commit. Other lanes (ADMIN-6, #226) may
move some of them before this ships. **Re-take the baseline IMMEDIATELY before
the deploy. The claim is that the DELTA across the deploy is zero; it is not a
claim about these particular numbers.**

| quantity | value at baseline |
|---|---|
| `practices` rows | 199 |
| `practices` with `slug LIKE 'solo-%'` | 195 |
| `md5(string_agg(slug, ',' ORDER BY id))` over `practices` | `84f72db0fb5b16d7212766ff5f2db043` |
| `audit_logs` with action in (`PRACTICE_UPDATED`, `PRACTICE_ARCHIVED`, `PRACTICE_RESTORED`) | 0 |
| `_prisma_migrations` rows | 117 |
| `AuditAction` enum labels | 161 |
| `practices` columns | 10 |
| `transcribe_visits` / of them `SIGNED` | 58 / 40 |
| `transcribe_md_patients` / `patients` | 46 / 0 |
| production slugs the WIDENED guard would refuse (the new names, `--` in positions 3–4, `xn--`) | 0 / 0 / 0 |

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **A2a-C1** | image ids of `transcribe-md` and `transcribe-md-worker` | the baseline image ids | new image ids | this IS the change |
| **A2a-C2** | the literal `ADMIN-2a one-time owner claim of a machine slug` (the audit `reason` string) in the shipped server bundle | **0 files** | **≥ 1 file** | ⚠️ this is a STRING LITERAL, not a local name, so minification cannot erase it. If it is absent, the server action did not ship |
| **A2a-C3** | the literal `mta-sts` in the shipped server bundle | **0 files** | **≥ 1 file** | the widened reserved set shipped. Take the control first: `autodiscover` must be absent before the deploy too |

## MUST NOT CHANGE — across the deploy itself

| # | row | expectation | falsifier |
|---|---|---|---|
| **A2a-N1** | `practices` rows / `solo-%` rows | equal to the pre-deploy baseline | a deploy that moves either one has created, deleted or re-slugged practices, and nothing in this change does any of those |
| **A2a-N2** | `md5(string_agg(slug, ',' ORDER BY id))` | **byte-identical** to the pre-deploy baseline | ⚠️ **THE NO-RE-SLUG ROW.** Any movement means a slug changed at deploy time, and this change deliberately performs no bulk re-slug |
| **A2a-N3** | `PRACTICE_UPDATED/ARCHIVED/RESTORED` audit rows | equal to the pre-deploy baseline | only a person submitting a form can add one. Movement during the deploy window, with no such request in the access log, is the finding |
| **A2a-N4** | `_prisma_migrations` / `AuditAction` labels / `practices` columns | equal to the baseline | code-only. Movement means another migration rode along unnamed |
| **A2a-N5** | clinical counts: `transcribe_visits`, `SIGNED`, `transcribe_md_patients`, `patients` | equal to the pre-deploy baseline | **never omitted.** This change touches no clinical table |

## VERIFY — structural, mutating nothing

    # positive control FIRST: the instrument answers about this table at all
    psql -tAc "SELECT count(*) FROM information_schema.columns WHERE table_name='practices';"   # 10

    # N1 / N2
    psql -tAc "SELECT count(*), count(*) FILTER (WHERE slug LIKE 'solo-%'),
                      md5(string_agg(slug, ',' ORDER BY id)) FROM practices;"

    # N3
    psql -tAc "SELECT count(*) FROM audit_logs WHERE action::text IN
               ('PRACTICE_UPDATED','PRACTICE_ARCHIVED','PRACTICE_RESTORED');"

    # N4
    psql -tAc "SELECT (SELECT count(*) FROM _prisma_migrations),
                      (SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
                        WHERE t.typname='AuditAction');"

    # N5
    psql -tAc "SELECT (SELECT count(*) FROM transcribe_visits),
                      (SELECT count(*) FROM transcribe_visits WHERE status::text='SIGNED'),
                      (SELECT count(*) FROM transcribe_md_patients),
                      (SELECT count(*) FROM patients);"

    # C2 / C3: grep the built server output inside the running container.
    # ⚠️ THE BUILD IS AT /app/apps/transcribe-md/.next, NOT /app/.next. The
    # first draft of this block grepped `.next/server` from the container's
    # workdir (/app), which does not exist. With 2>/dev/null that returns 0 for
    # EVERY string, so "before = 0" would have been true for the wrong reason
    # and "after >= 1" could never pass. Caught because the control `staging`
    # also read 0. POSITIVE CONTROL FIRST, every time:
    docker exec meddoc-pro-transcribe-md-1 sh -c \
      "cd /app/apps/transcribe-md && grep -rl 'VIEWED_SETTINGS' .next/server | wc -l"   # >= 1 (measured 1)
    docker exec meddoc-pro-transcribe-md-1 sh -c \
      "cd /app/apps/transcribe-md && grep -rl 'ADMIN-2a one-time owner claim of a machine slug' .next/server | wc -l"   # 0 -> >= 1
    docker exec meddoc-pro-transcribe-md-1 sh -c \
      "cd /app/apps/transcribe-md && grep -rl 'mta-sts' .next/server | wc -l"   # 0 -> >= 1

    # BEFORE values, measured 2026-09-10 on the running image at the corrected
    # path: VIEWED_SETTINGS 1 (control), the claim literal 0, mta-sts 0,
    # autodiscover 0, practice-slug-claim 0 (server and static).

⚠️ **NO PRODUCTION CLAIM IS PART OF VERIFICATION.** Submitting the form is a
production mutation of a real practice's row. The full walk (owner claims →
second claim refused → non-owner shown nothing) belongs on QA against the
byte-identical image. The only production step allowed is DOM *presence* of
`data-testid="practice-slug-claim"` on `/settings/members` for the synthetic
smoke-doctor account — viewed, not submitted.

⚠️ **CORRECTED BEFORE COMMIT, AND THE CORRECTION MATTERS FOR WHAT THE CHECK
CAN SEE.** An earlier draft of this line said the smoke doctor is *"an OWNER
of a solo practice"*. Measured read-only on 2026-09-10: the account IS an
active `OWNER` of an active practice, but that practice's slug is **NOT** a
machine `solo-` slug. So production will render the **claimed, read-only**
state (`data-testid="practice-slug-claimed"`), and the claim FORM
(`practice-slug-input`) **cannot be observed on production without a real
practice's owner**. The form is proven only by unit tests and on QA. Do not
read presence of the section as presence of the form.
