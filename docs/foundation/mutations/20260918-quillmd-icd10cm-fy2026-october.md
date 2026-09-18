# Declared delta: restore the first half of FY2026 — the October 1, 2025 release — 2026-09-18

## Why this exists at all, stated plainly

Selecting a code release by the **encounter's date of service** is more correct than selecting it by
today's date, and it is what the same day's activation ships. It also **takes a working case away**,
and that trade has to be written down where the next incident will find it.

The database holds one release, `FY2026-April`, effective `2026-04-01` → `2026-09-30`. But ICD-10-CM
FY2026 begins **2025-10-01**; the April file is a mid-year update. Under the old rule — "the release
in force *today*" — an encounter documenting a February 2026 visit was validated against that April
release and coded fine. Under the new rule it matches nothing, and the clinician is told no release
covers the date.

> **A correctness fix that silently removes a working case is an accepted-capability loss.** This act
> removes the loss instead of accepting it, because the content to close it was already verified.

## What makes this safe rather than a guess

The CMS April 1 2026 addendum reports **zero additions, zero deletions and zero descriptor
revisions** against the CDC FY2026 base release (`docs/rebuild/terminology.md`). Measured here, the
two extracted code files are **byte-identical**:

    sha256  a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba
      .runtime/terminology/icd10cm-codes-2026.txt          (CDC FY2026 base archive)
      .runtime/terminology/icd10cm_codes_2026_april.txt    (CMS April archive, already imported)

So the 74,719 codes already in the database are exactly the codes in force from 2025-10-01. This act
stores them again under the version and effective period during which they were the current release.

## The command

    cd /opt/meddoc-pro && bash scripts/run-ruled-mutation.sh \
      --declaration docs/foundation/mutations/20260918-quillmd-icd10cm-fy2026-october.md -- \
      rebuild/.venv/bin/python rebuild/ops/with_db_role.py \
        --credentials rebuild/.runtime/db-role-secrets/fresh-db-roles.json \
        --source /opt/meddoc-pro/rebuild --role migrator -- import_terminology \
        --system ICD-10-CM \
        --path rebuild/.runtime/terminology/icd10cm-codes-2026.txt \
        --sha256 a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba \
        --release-version FY2026-October \
        --effective-from 2025-10-01 --effective-until 2026-03-31 \
        --expected-count 74719 \
        --source-url https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/icd10cm-Code%20Descriptions-2026.zip

**Effective period `2025-10-01` → `2026-03-31`, not → `2026-09-30`.** CDC's FY2026 period runs to
September, but the April release superseded it on 2026-04-01 and the importer refuses overlapping
periods for the same system — correctly. What is stored is *which release was in force on a given
date*, which is the question the application asks.

## Order, and the state this act assumes

Run **after** `20260918-quillmd-icd10cm-fy2027.md`. Its preconditions:

| Quantity | Before | After |
| --- | --- | --- |
| `core_codeset` rows | 2 (`FY2026-April`, `FY2027`) | **3** |
| `core_code` rows | 149,598 | **224,317** (149,598 + 74,719) |
| `core_code` rows belonging to `FY2026-April` | 74,719 | 74,719, unchanged |
| `core_code` rows belonging to `FY2027` | 74,879 | 74,879, unchanged |
| `AuditEvent` rows this act writes | — | **exactly one**, `terminology.import` |
| Encounters / patients / code suggestions / jobs | 11 / 3 / 0 / 12 | unchanged |

The new release must read exactly: system `ICD-10-CM`, version `FY2026-October`, `effective_from`
`2025-10-01`, `effective_until` `2026-03-31`, `license_reference` empty, `sha256` as above.

**Coverage check afterwards**, read back through `core.coding.applicable_releases` against a
throwaway object carrying only a `service_date` — no encounter is created, modified or coded:

| date of service | must select |
| --- | --- |
| `2025-09-30` | nothing (FY2025 is not loaded; the refusal is correct and is now the only gap) |
| `2025-10-01` | `FY2026-October` |
| `2026-03-31` | `FY2026-October` |
| `2026-04-01` | `FY2026-April` |
| `2026-09-30` | `FY2026-April` |
| `2026-10-01` | `FY2027` |

## What this act must not do

- It must not modify `FY2026-April` or `FY2027` in any way. The importer refuses to rewrite an
  existing release and refuses an overlapping period; both are the protection, not a promise.
- It must not enable CPT, contact a provider, or read or write clinical content.

**Residual, named rather than closed:** encounters dated before **2025-10-01** still match no
release and are refused with a visible message. Closing that means importing FY2025 and earlier, and
no synthetic or real encounter in this system is dated before 2026-09-17. The refusal is honest and
the gap is stated here so the next reader does not rediscover it as a bug.
