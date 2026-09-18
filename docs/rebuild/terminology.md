# Maintained terminology for the fresh application

This is an import of official reference terminology into the new application,
not a migration of old application data. No old accounts, patient records,
documents, balances or history are read. Source checks were performed on
2026-09-17.

## Current ICD-10-CM release

[CDC's release page](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html) identifies
the April 1, 2026 release as applicable through September 30, 2026. The
[CMS ICD-10 page](https://www.cms.gov/medicare/coding-billing/ICD-10-codes)
links the complete April code-description archive and specifies the same period.
FY2027 is already published but starts October 1, 2026; it must not be used for
September services.

The following official files were fetched directly over HTTPS into ignored
`rebuild/.runtime/terminology/`. No archive or downloaded terminology is tracked.

| Public artifact | SHA-256 | Finding |
| --- | --- | --- |
| [CDC FY2026 base archive](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/icd10cm-Code%20Descriptions-2026.zip) | `a852eb91b3344ae38476e63816976ee1eeb94dcced7151118324f060e8499f88` | Complete code file: 74,719 rows |
| [CDC April description archive](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026-update/icd10cm-Code%20Descriptions-April-1-2026.zip) | `5d89cd7df3ed01be5effc74f17c0e1538b0a0a296b814a5fdbde39b7c7c5b048` | Contains two PDF format guides, **no code text file** |
| [CMS complete April archive](https://www.cms.gov/files/zip/april-1-2026-code-descriptions-tabular-order.zip) | `4fd9d8b37f02ab42827c7e7be30595c005b0cc3a6bae7a515e3f4c86b6918688` | Complete code and order files plus April addenda |

The imported file is `Code Descriptions/icd10cm_codes_2026.txt` from the CMS
archive, cached as `.runtime/terminology/icd10cm_codes_2026_april.txt`:

- Exactly **74,719** unique codes; 6,413,824 bytes; strict UTF-8 decoding.
- Text SHA-256: `a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba`.
- Its bytes equal the complete CDC FY2026 base code file. The CMS April code
  addendum reports zero additions, zero deletions and zero descriptor revisions.
- Stored release: `ICD-10-CM`, `FY2026-April`, inclusive dates
  `2026-04-01` through `2026-09-30`.
- `M25.532` is present with description “Pain in left wrist”. Decimal placement
  is normalized after the first three code characters; descriptions are retained
  without shortening. Current `QA0.*` categories with an alphabetic second
  character and `U` categories are included; older numeric-second-character
  regular expressions would omit valid codes.

The tabular XML is not used as a substitute for the full code file. Its leaf
elements do not expand all required seventh-character combinations; treating
those leaves as the complete code universe would silently lose valid codes.
Similarly, an addendum is not a full release. The importer rejects order files,
addenda, malformed rows, duplicates, invalid UTF-8, oversized descriptions,
checksum mismatch and mismatched declared counts. ICD imports require at least
70,000 entries and an official CDC/CMS HTTPS provenance URL.

Hashes above are independently measured download hashes, not a claim of a
publisher digital signature. An operator must obtain the file from the official
release link and verify the declared release dates/count before importing.

## Reproduce the import

With the official archive downloaded and only its full code text member copied
to the ignored cache, run from `rebuild/`:

```bash
.venv/bin/python manage.py import_terminology \
  --system ICD-10-CM \
  --path .runtime/terminology/icd10cm_codes_2026_april.txt \
  --sha256 a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba \
  --release-version FY2026-April \
  --effective-from 2026-04-01 --effective-until 2026-09-30 \
  --expected-count 74719 \
  --source-url https://www.cms.gov/files/zip/april-1-2026-code-descriptions-tabular-order.zip
```

The management command refuses database names outside the fresh `quillmd_`
namespace. It writes the version, effective dates, provenance URL and source
text hash to `CodeSet`, imports `Code` rows atomically, and records a terminology
audit event. Repeating an identical import verifies all stored code/descriptions
without a second write or audit event. Modified or overlapping releases are
refused; existing releases are never overwritten.

FY2027 is prepared and declared, **not yet imported** — see the section below
for its state and the act that will run it. The application selects the release whose effective period contains the **encounter's date of
service or discharge** — not today's date. A release whose fiscal year has
ended keeps answering for encounters inside it, and a release that has not
started yet is not applied to earlier visits.
This command provides controlled maintenance, not an automatic feed service.
The present release is a code/description dictionary; April tabular instructions,
exclusions and sequencing rules are **not** implemented as a coding engine.
Suggestions remain limited to codes explicitly present in documented notes,
with source evidence and clinician acceptance. No diagnosis inference is added.

## FY2027 — the October 1, 2026 release (VERIFIED AND DECLARED, NOT YET IMPORTED)

⚠️ **State, so this section cannot be read as an act that happened.** The file
below has been downloaded, hashed and parsed with the production parser, and the
import is declared at
`docs/foundation/mutations/20260918-quillmd-icd10cm-fy2027.md`. It has **not**
run: the live database holds one release (`FY2026-April`) and 74,719 codes. The activation that must precede it was
refused by a database guard on its first attempt (see `CHECKPOINT.md`) and is being retried. Until
it runs, the standing instruction remains — import the verified FY2027 file
before 1 October 2026, or from that date coding returns nothing for every new
encounter, with a warning rather than an error.

[CDC's release page](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html) states,
for this release: *"FY27 ICD-10-CM codes should be used for healthcare services
provided from October 1, 2026, through September 30, 2027"*, and *"This release
replaces the FY26, April 1, 2026, release"* — replaces it **prospectively**.
September services keep FY2026-April, which is why both releases are stored and
neither is overwritten.

| Public artifact | SHA-256 | Finding |
| --- | --- | --- |
| [CDC FY2027 code-description archive](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/icd10cm-code-descriptions-2027.zip) | `93e3ad6004badf470c55bfe679b748ae88fd9b2b421851e409eec382c7713b9a` | 2,192,779 bytes; contains the code file, the order file, both addenda and two format guides. ⚠️ **Measured at download; the archive itself is not retained**, so this row is re-checkable only by downloading it again. The extracted code file below IS retained, and its hash is what the importer enforces |

The imported member is `icd10cm-code-descriptions-2027/icd10cm-codes-2027.txt`,
cached at the ignored path `.runtime/terminology/icd10cm-codes-2027.txt`:

- Exactly **74,879** unique codes (FY2026-April had 74,719); 6,425,201 bytes;
  strict UTF-8; CRLF line endings, which `splitlines()` handles.
- Text SHA-256: `3c0583a38ee0e848f7dc0ac8ce88e8f001bbba8c6385ed825d44d46f6e5297c9`.
- Parsed with the production parser before any import: every row satisfied the
  codes-file format, first `A00.0`, last `U09.9`, longest description 228
  characters, 74,664 of the codes carrying a decimal.
- Release to be stored: `ICD-10-CM`, `FY2027`, inclusive dates `2026-10-01`
  through `2027-09-30`.

### Reproduce it

```bash
cd /opt/meddoc-pro/rebuild
.venv/bin/python manage.py import_terminology \
  --system ICD-10-CM \
  --path .runtime/terminology/icd10cm-codes-2027.txt \
  --sha256 3c0583a38ee0e848f7dc0ac8ce88e8f001bbba8c6385ed825d44d46f6e5297c9 \
  --release-version FY2027 \
  --effective-from 2026-10-01 --effective-until 2027-09-30 \
  --expected-count 74879 \
  --source-url https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/icd10cm-code-descriptions-2027.zip
```

The importer refuses an effective period that overlaps an existing release of
the same system, so a mistyped start date is rejected rather than silently
shadowing FY2026. It never rewrites an existing release: re-running an
identical import re-verifies every stored code and writes nothing.

Because this adds 74,879 irreversible rows to the private database, it runs
through `scripts/run-ruled-mutation.sh` with the committed declaration
`docs/foundation/mutations/20260918-quillmd-icd10cm-fy2027.md`.

### How the applicable release is chosen

`core/coding.applicable_releases(encounter)` is the only implementation:

    effective_from <= encounter.service_date <= effective_until

Both readers use it — `suggest()` when proposing codes and the acceptance view
when a clinician accepts one — so the two cannot disagree at a fiscal-year
boundary. The stored suggestion names the release and the date of service it
was validated for, and the audit row records the service date, the releases
consulted and whether any ICD-10-CM release covered that date at all. A date no
release covers produces a visible refusal, not an empty list.

Boundary behaviour is tested directly in
`rebuild/core/tests/test_code_release_dates.py`: 30 September 2026 selects
FY2026-April, 1 October 2026 selects FY2027, and a September encounter coded
the following December still selects FY2026-April.

## CPT remains blocked pending a suitable license and feed

[AMA's licensing FAQ](https://www.ama-assn.org/practice-management/cpt/cpt-licensing-frequently-asked-questions-faqs)
states that CPT use in electronic products requires licensing. No CPT descriptors
were downloaded or imported from an unlicensed source, and no subscription was
purchased. The owner must obtain an AMA or authorized-distributor agreement that
covers QuillMD's intended product use, a maintained authorized data feed, the
license reference and expiry, and any required notices/distribution terms.

For a supplied licensed feed, the command accepts strict UTF-8 CSV with exactly
`code,description` columns and `--system CPT`. Use explicit source-file hash,
count, release version, inclusive effective dates and a stable HTTPS provenance
URL with no embedded credentials or signed query parameters. The private
environment must contain `CPT_LICENSE_ID` and `CPT_LICENSE_EXPIRY` (`YYYY-MM-DD`).
The license must still be current and cover the entire imported effective
period. The license ID is stored in `CodeSet.license_reference`; its expiry is
recorded in the import audit event. Runtime suggestion/acceptance also checks
current license status. No actual CPT content is bundled in tests: their
procedure description is explicitly synthetic.

## Verification

All **13 targeted tests passed** in an isolated `test_quillmd_terminology`
database, which Django destroyed after the run. Tests cover strict parsing,
rejecting partial/incorrect source formats,
duplicate/oversized descriptions, unlicensed/expired CPT, checksum/count errors,
atomic writes, idempotent imports, immutable release contents and overlapping
effective periods, including current alphanumeric ICD categories.

The real public-reference import into **`quillmd_fresh`** completed and readback
confirmed 74,719 current code rows, one import audit event, and zero CPT rows.
Repeating the same full import returned `Already verified` and preserved the
single audit event. Sentinels `M25.532`, `QA0.0101`, and `U07.1` were read back
with the official descriptors. No old-system database was accessed during this
terminology import.
