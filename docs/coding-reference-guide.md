# Official outpatient coding references

The coding service searches an imported official ICD-10-CM Alphabetic Index and
checks the result against the same release's Tabular List and complete codes
file. A model supplies clinical search terms and selects a supplied Index entry;
its proposed code or description is not a terminology source. Clinical
documentation, service date, patient ownership, certainty, relevance and
sequencing remain separate requirements.

## Sources and dates verified on 2026-10-14

The [CMS release page](https://www.cms.gov/medicare/coding-billing/icd-10-codes)
and [NCHS release page](https://www.cdc.gov/nchs/icd/icd-10-cm/files.html) identify
these distinct service-date releases. Preserve historical imports even when
their code dictionaries have identical hashes.

| Release | Inclusive service dates | Reportable codes |
| --- | --- | ---: |
| FY2026 October | 2025-10-01 through 2026-03-31 | 74,719 |
| FY2026 April | 2026-04-01 through 2026-09-30 | 74,719 |
| FY2027 October | 2026-10-01 through 2027-09-30 | 74,879 |

FY2027 authoritative downloads:

- [CMS Index/Tabular archive](https://www.cms.gov/files/zip/2027-code-tables-tabular-index.zip),
  SHA-256 `37baa476323714be16f95c9b2c96812bf6f3623d9f15188866e584dc529b0298`.
- [NCHS codes archive](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2027/icd10cm-code-descriptions-2027.zip),
  SHA-256 `93e3ad6004badf470c55bfe679b748ae88fd9b2b421851e409eec382c7713b9a`.
- [FY2027 official guidelines](https://www.cms.gov/files/document/fy-2027-icd-10-cm-coding-guidelines.pdf),
  SHA-256 `1f0065b609b678e98f85bf047b3b012c6a88ba3222e42be2f2435889e05738ab`.

The extracted FY2027 Index XML is
`248e4a133996f986ba98821a411f0e8afee632a2de1d98f23e02fba8b6fd8a15`,
Tabular XML is
`d778c97a5bb9da7d71645610e277f8db3bd302befa3b08d71dd5043715a74b2a`,
and complete codes text is
`3c0583a38ee0e848f7dc0ac8ce88e8f001bbba8c6385ed825d44d46f6e5297c9`.
The separately downloaded CMS and NCHS Index/Tabular XML bytes agree. This
release contains 81,642 Index entries and 47,025 Tabular diagnosis nodes.
XML leaves are not the reportable code universe: seventh-character expansions
are represented by the complete codes file.

Historical official archives:

- [FY2026 October Index/Tabular](https://www.cms.gov/files/zip/2026-code-tables-tabular-and-index.zip),
  SHA-256 `abfc45a54e4edc215cbaa2f0d18b30112db2bf9141857c9f8902390a495e6696`.
- [FY2026 April Index/Tabular](https://www.cms.gov/files/zip/april-1-2026-code-tables-tabular-index.zip),
  SHA-256 `c623e47143c156d1427fe7cd2bee7ac1ae6994bdd2196b9ec27d4a3219bcfd48`.
- [FY2026 October codes](https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/ICD10CM/2026/icd10cm-Code%20Descriptions-2026.zip),
  SHA-256 `a852eb91b3344ae38476e63816976ee1eeb94dcced7151118324f060e8499f88`.
- [FY2026 April codes](https://www.cms.gov/files/zip/april-1-2026-code-descriptions-tabular-order.zip),
  SHA-256 `4fd9d8b37f02ab42827c7e7be30595c005b0cc3a6bae7a515e3f4c86b6918688`.
- [FY2026 guidelines](https://www.cms.gov/files/document/fy-2026-icd-10-cm-coding-guidelines.pdf),
  SHA-256 `2e87b3b088d6032edf6cda8c946cf342619df0c07237055a0e3be68410a0c267`.

Both historical complete code files have SHA-256
`a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba`.
The reference import still binds each release's own interval, Index/Tabular
archive and provenance; it does not replace a previous release.

## Import contract

Import the complete codes file through the existing `import_terminology`
command first. Then prepare a reviewed local JSON manifest with exactly:

```json
{
  "format": "icd10cm-official-reference-manifest-v1",
  "release": {
    "id": "actual-existing-CodeSet-UUID",
    "system": "ICD-10-CM",
    "version": "FY2027",
    "effective_from": "2026-10-01",
    "effective_until": "2027-09-30",
    "sha256": "actual-complete-codes-file-sha256",
    "source_url": "exact-existing-CodeSet-official-source-url"
  },
  "files": {
    "codes": {"path": "/absolute/codes.txt", "sha256": "actual-sha256", "source_url": "official-archive-url", "archive": {"path": "/absolute/codes.zip", "sha256": "actual-archive-sha256", "member": "exact/archive/member.txt"}},
    "index": {"path": "/absolute/index.xml", "sha256": "actual-sha256", "source_url": "official-archive-url", "archive": {"path": "/absolute/tables.zip", "sha256": "actual-archive-sha256", "member": "exact/archive/index.xml"}},
    "tabular": {"path": "/absolute/tabular.xml", "sha256": "actual-sha256", "source_url": "official-archive-url", "archive": {"path": "/absolute/tables.zip", "sha256": "actual-archive-sha256", "member": "exact/archive/tabular.xml"}},
    "guidelines": {"path": "/absolute/guidelines.pdf", "sha256": "actual-sha256", "source_url": "official-pdf-url", "archive": null}
  },
  "expected_code_count": 74879,
  "expected_index_entry_count": 81642,
  "expected_tabular_diagnosis_count": 47025
}
```

This is a schema example, not executable provenance. Supply genuine pins and
the existing release UUID. The source URL is the independently verified source
of the pinned archive/PDF; the importer does not fetch or authenticate a URL.

```bash
python manage.py import_coding_reference --manifest /absolute/reviewed.json --manifest-sha256 ACTUAL_MANIFEST_SHA256
```

The command performs bounded stable reads, verifies every extracted file against
its exact archive member, rejects duplicate manifest keys/unknown structures,
checks complete counts and fiscal year, then requires the existing CodeSet
metadata and every code/description pair to match. It requires PostgreSQL in a
`quillmd_` database and shares the terminology writer lock. Creation is atomic
and audited. Repeating the identical manifest is idempotent; changed evidence,
dictionary or reference is refused, never overwritten. A changed path changes
manifest provenance: preserve the reviewed paths for an idempotent replay.
No clinical record is read or changed by this command.

## Pure API and instruction handling

`parse_reference(index_xml, tabular_xml, code_dictionary)` returns `index` and
`tabular`. Both raw XML hashes and the canonical dictionary digest are retained.
`search_index(reference, terms, limit=30)` accepts that dictionary or a
`CodingRelease` instance. It searches official Index path text only and returns
stable entry IDs, full paths, parent/child relationships, default codes,
nonessential modifiers and See/See-also relationships. A mandatory See has to be
followed to its separately supplied target; a missing or ambiguous target is
held. An advisory See-also does not erase a usable default (guideline I.A.17).
Table-dependent or unresolved instructions are held; the implementation does
not invent a Neoplasm/Drug/External Cause table resolution.

`validate_code(reference, code, selected_codes=None)` returns `valid`,
`reportable`, authoritative `description`, all inherited `instructions`,
`errors`, `requires_review`, `review_instruction_ids` and
`unresolved_instructions`. `valid` means structural reportability and explicit
Tabular constraints passed, not that the patient's documentation supports it.
Category-only and missing seventh-character codes are not reportable. Includes,
inclusion terms, Excludes1/2, code-first, additional-code, code-also and seventh
character notes retain their source-node identity and stable instruction ID.
Excludes1 selections conflict; Excludes2 does not prohibit coexistence. Prose
sequencing/etiology conditions do not become satisfied merely because a related
code was selected. Empty or unrecognized instructions require review.

The exact general chapter 18 and 21 notes, and the section Z00–Z13 note about
classifying nonspecific abnormal findings, were compared in all three official
releases above. They remain visible as `general_guidance`, rather than holding
every symptom/reason code. Changed text or a new fiscal year is not covered by
that recognition. This distinction does not waive clinical documentation,
integral-symptom or performed-procedure rules.

One exact section Z77–Z99 instruction is represented as a condition:
`rule=post_treatment_follow_up`,
`condition=documented_post_treatment_follow_up`, related codes Z08/Z09.
Guideline I.C.21.c.8 (page 101) limits those codes to surveillance after completed
treatment when the condition no longer exists. The engine must resolve that
condition from the whole source; merely obtaining old records does not document
such a visit. Absent qualifying documentation cannot justify inventing a
follow-up code. Ambiguous follow-up wording remains a question. All other
unresolved instructions continue to hold their affected recommendation.

The exact Z86 code-first instruction for follow-up after treatment has that same
condition, with Z09 as its related code. For Z12, the instruction to additionally
code family history of malignancy remains conditional on that documented family
history; its absence does not justify inventing a Z80 code. Z12's diagnostic-exam
Excludes1 prose is represented separately as
`rule=screening_versus_diagnostic_exam`. It requires an affirmative source review
of screening purpose and the absence of a related diagnostic indication. An
asymptomatic planned screening encounter can qualify; a symptom-driven test
cannot be relabelled screening. These instructions remain unresolved in the
terminology validator until the engine supplies the corresponding source-bound
resolution. The guideline permits screening alongside other health problems;
an unrelated symptom does not universally prohibit a screening code.

## Independently established expected cases

These expectations were established from the official Index, Tabular and
guidelines before implementation:

- Family history of colon polyps without documented histology follows
  History → family → colonic polyps to Z83.719. A relative's age does not prove
  adenomatous, serrated or hyperplastic histology. Z83.71 is a nonreportable
  parent. Personal history Z86.0100 and patient polyp K63.5 describe different
  facts and cannot substitute for the family-history route.
- Bloating maps to R14.0; heartburn to R12. Confirmed gastro-esophageal reflux
  without esophagitis has the K21.9 route. A suspected outpatient diagnosis is
  not coded as confirmed: use documented symptoms/reason to the highest known
  certainty (IV.H). Integral symptoms are not automatically additional to an
  established diagnosis (I.B.4–5).
- A planned colonoscopy or review of an earlier report does not prove a
  procedure was performed. Z12.11 requires a documented screening purpose;
  evaluation of symptoms is not automatically screening (I.C.21.c.5).
- A prior appendectomy is neither current appendicitis nor a current
  appendectomy service. Relevant acquired-absence status has a separate
  Index/Tabular route; historical detail is not automatically a current claim.
- Contradictory patient ownership or diagnosis documentation requires
  clarification (I.A.19); negated conditions and a relative's disease are not
  the patient's confirmed diagnoses. Historical and current statements must
  be compared with their dates, rather than treated as a contradiction solely
  because their words differ.

The [CMS E/M guide](https://www.cms.gov/files/document/mln006764-evaluation-management-services.pdf)
requires setting, patient relationship, medical necessity and either the
applicable time or MDM requirements. Referral alone does not establish a new
patient. Direct time included in a documented total is not added a second time.
Twenty direct minutes and thirty-five total minutes do not independently identify
an office E/M service. No CPT catalogue is supplied by this public ICD reference;
electronic CPT use requires the applicable licensed feed and entitlement, as
described by the [AMA licensing FAQ](https://www.ama-assn.org/practice-management/cpt/cpt-licensing-frequently-asked-questions-faqs).
