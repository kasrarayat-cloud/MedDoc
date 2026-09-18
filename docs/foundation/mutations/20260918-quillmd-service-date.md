# Private activation of date-of-service code selection — 2026-09-18

This act ships migration `core.0014_encounter_service_date` and the reviewed code with it, from the running release
`5f673a3b` to the cited merge, and restarts the three private services on it. It runs through
`scripts/activate-service-date.py`, which the ruled-mutation runner invokes with this committed declaration.

## The tree this act ships

The act fast-forwards permanent main from `5f673a3b` to the cited target and declares every change in that range:

1. **Documentation merged since `5f673a3b`** (PR #1198): the milestone close-out — checkpoint, owner actions,
   patient-data release requirements and storage-encryption notes.
2. **Length bounds on recordings.** Measurement returns `Bounds(confirmed, measured)`: `measured` is the conservative
   upper bound the charge limit is held against, `confirmed` is the length that is certainly present. The incomplete-
   output marker reads `confirmed`, so a transcript can never be described as complete by a number that was rounded up
   for billing. MP3 frames inside trailing tags are counted at their own duration and, beyond eight stray headers, the
   file is refused with a re-export instruction instead of being priced short. No pricing rule changes: the limit is
   still held against the conservative figure.
3. **Restore readiness.** `restore_ready()` requires the PostgreSQL init-complete marker, `pg_isready` and a
   `SELECT 1` returning 1, because the entrypoint's temporary initialisation server answers `pg_isready` before the
   real server exists. Failures record the stage and the exception class, never raw stderr.
4. **Date-of-service code selection** (this migration): `Encounter.service_date`, `applicable_releases(encounter)` as
   the single rule both the suggestion and the acceptance path read, disclosure when no release covers a date, and the
   date of service shown on the coding tab.
5. **A non-secret configuration report**, `manage.py configuration_status`, so that answering *is this credential
   configured* never requires reading the private environment file.
6. **Guard maintenance**: the recording-limit activation's path guard is pinned to the range it actually shipped
   instead of a moving HEAD, and this activation gets the equivalent guard.

Not in the range, and refused by the activator if present: service units, the document sandbox, the service launcher,
the storage helper and the Python requirements. The compiled Word inputs must be identical.

## Expected delta, declared before the act

Database. Migration 0014 creates no model, so Django's post-migrate bookkeeping adds no content type and no permission.
The whole delta:

- `core_encounter.service_date`, `date`, NOT NULL, **no default**, added at the end of the table.
- Exactly **11** encounter rows gain a value. Every one of them was recorded on **2026-09-17 UTC**, so after the act
  `SELECT service_date, count(*) FROM core_encounter GROUP BY 1` must read exactly `2026-09-17=11`, and
  `service_date <> (created_at AT TIME ZONE 'UTC')::date` must match **0** rows.
- One `django_migrations` row, `core / 0014_encounter_service_date`.
- **No constraint changes. No index changes. No table created or dropped.** The activator compares the full
  `pg_constraint` and `pg_indexes` listings before and after and refuses any difference.

Everything else must be identical, and is asserted row by row:

| Quantity | Before | After |
| --- | --- | --- |
| Tables | 35 | 35 |
| Encounters | 11 | 11 |
| Patients | 3 | 3 |
| Jobs | 12 | 12 |
| Code suggestions | 0 | 0 |
| Terminology releases | 1 | 1 |
| Terminology codes | 74,719 | 74,719 |
| Audit events | 361 | 361 |
| Per-table row fingerprints, with the new column removed for comparison | — | identical |
| `/var/lib/quillmd/files`, `/var/lib/quillmd/mail` inventories | — | identical |

⚠️ **The clinical counts are in the table deliberately.** This act touches the table that holds encounters. If the
encounter, patient or suggestion count moves at all, the act has done something nobody asked for, and the only way to
know is to have written the numbers down while they were still true.

## Protected resources and checks

Must remain unchanged: every other tenant's containers, the marketing site, the ingress, the encrypted volume layout,
the compiled Word runtime and its pinned helper image, the installed unit files, private files and mail bytes, and all
credentials. `scripts/check-cotenants.sh` runs before and after. The environment file is rewritten **only** to replace
the release line, byte-compared before and after, and the act refuses if anything else in it differs.

Preconditions the activator refuses without: a merged PR whose merge commit is the target, a full citation on that
commit, the services running the baseline synthetic-only, a plaintext-free restore proof covering the current row
count, no queued or running job, schema history through 0013 only, and the pinned migration bytes
(`198da2a8ee94d5c4e2ee392b3bd98ccd7f08dacb10b5ba730c2b2e84e27befa4`) carrying exactly three operations in order:
`AddField`, `RunPython(adopt_recorded_date)`, `AlterField`.

**Reversibility.** Reversing the migration drops the column, so the backfilled dates are not recoverable by re-running
anything; that is stated in the migration's own reverse function rather than implied. The data they were derived from
(`created_at`) is not touched, so the backfill can be recomputed exactly. On any failure the activator fails closed:
the services stay stopped and the recorded state is inspected before anything else runs.

No provider request is made. No clinical content is read, written or exported.
