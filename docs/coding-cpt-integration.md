# CPT integration prerequisites and import

As of 2026-10-14, this coding implementation supplies no executed CPT agreement,
licensed catalogue or licensed selection criteria. CPT remains unavailable until
the owner supplies and reviews all three. The synthetic fixtures in
`rebuild/core/tests/test_coding_imports.py` grant no rights and must never become
an application catalogue. Official ICD-10-CM references are a separate import;
see [coding-reference-guide.md](coding-reference-guide.md).

## Evidence required from the owner

`core.coding_licensing.verified_entitlement()` reads a closed JSON manifest with
format `quillmd-cpt-entitlement-v1`. Its required fields are:

| Field | Required evidence or exact application scope |
| --- | --- |
| `agreement` | Executed agreement file, referenced by `filename` and SHA-256. |
| `issuer`, `license_id` | Actual issuer and agreement/license identifier. |
| `product` | `QuillMD`. |
| `users` | `scope: all_authorized_quillmd_users` and a substantive `terms_reference`. |
| `distribution` | `uses` containing exactly `application_display`, `clinical_export`, `coding_suggestions`, plus `terms_reference`. |
| `intended_ai_use` | `uses` containing exactly `coding_assistance`, `provider_processing`; `training: not_authorized_by_this_application`; `terms_reference`. |
| `validity` | Inclusive ISO dates `from` and `until`, covering today. |
| `content_release` | Exact `version`, `effective_from`, `effective_until`, stable credential-free HTTPS `source_url`, CSV `sha256`, and positive integer `code_count`. The content period must fit within the agreement period. |
| `rules` | Licensed rule JSON file, referenced by `filename` and SHA-256. |
| `permission_review` | Human permission-review JSON file, referenced by `filename` and SHA-256. |

The review format is `quillmd-cpt-permission-review-v1`, with exactly
`reviewed_by`, ISO-date `reviewed_at`, `decision: approved`, and `coverage`.
`coverage` must reproduce every manifest field above except `format` and
`permission_review`, including the agreement, content and rules hashes. The
review date must fall within the agreement period and cannot be in the future.
The reviewer must establish that the actual agreement permits those uses; a
manifest cannot create permissions absent from the agreement. Partial user or
distribution coverage does not satisfy this application's current gate.

`CPT_LICENSE_ID` and `CPT_LICENSE_EXPIRY` cannot enable CPT. No purchase,
download, vendor authentication or permission review is performed by this code.

## Licensed content and rule format

Supply a local UTF-8 CSV with exactly `code,description` columns, unique codes,
the reviewed complete release count and the exact reviewed SHA-256. The file
limit is 20 MiB. The importer accepts five numeric characters or four numeric
characters followed by one uppercase letter. Descriptions must be nonempty,
at most 500 characters, and free of control characters.

The companion rule document has exactly `format: quillmd-cpt-rules-v1`,
`release`, `index`, and `tabular`. `release` must equal `content_release`.
`index` contains `{terms, code, reference}` entries; each code must have one
matching entry in `tabular.codes`, and every rule code must be indexed. Each
rule contains `{description, kind, reference, instructions, requirements}`.
Its description must equal the supplied CSV description. Rules may cover only
part of the catalogue; codes without supplied criteria cannot be suggested or
selected through this workflow.

The supported criteria are deliberately finite:

- `kind: procedure`: `requirements` contains licensed `performed_terms` and
  `required_details`. Each detail contains a unique `name`, matching `terms`
  and its authoritative `reference`. Selection requires exact documentation of
  a current performed procedure for the patient, with the required details.
  A plan, negation or historical mention does not establish performance.
- `kind: office_em`: `requirements` contains `setting: outpatient_office`,
  `patient_status` (`new` or `established`), `mdm` and `time`; at least one basis
  must be supplied. MDM criteria contain `required_elements: 2`, permitted
  levels for `problems`, `data` and `risk`, and licensed `evidence_terms` for
  each. An entered level alone is insufficient. Time criteria contain licensed
  integer `minimum`/`maximum`, `basis: total_practitioner_same_day`,
  `total_time_terms` and `excluded_activities`. The source must establish one
  total time value; direct and total time are never added. Qualified
  practitioner, same-day work and excluded separately reported activities are
  checked independently.

Use `core.coding_cpt.validate_rules()` as the exact supported schema. Unknown
rule shapes fail closed. New vendor semantics require a reviewed implementation
change; neither model output nor remembered thresholds can fill missing rules.
No real code, descriptor or time threshold is supplied by this document.

## Private evidence provisioning

The default manifest is
`/opt/meddoc-pro/rebuild/.runtime/owner-contracts/cpt-entitlement-v1.json`.
Set `QUILLMD_CPT_ENTITLEMENT_MANIFEST` to select another absolute path; the
application exposes it as the Django setting `CPT_ENTITLEMENT_MANIFEST`. An
empty, relative, missing or unreadable path remains unavailable.

Keep the manifest and referenced evidence in a private `0700` directory, with
regular single-link `0600` files and no symlink path components. The reader
requires ownership by root or its effective UID, and must actually be able to
read the files. The manifest limit is 256,000 bytes; each referenced agreement,
review or rules file is limited to 20 MiB. Do not commit these files or expose
them through a web/static directory.

The native operator and application service have different UIDs. One `0600`
bundle cannot normally serve both. Provision byte-identical protected copies
for the import identity and runtime identity. For example, use the reviewed
owner directory for import and a private directory under `/var/lib/quillmd`
for runtime. All ancestor directories must permit the intended identity to
traverse them. A root-owned unreadable file is not a valid runtime installation.

Provisioning is a separate declared operation once genuine evidence is
available. Under that operation, use previously unused target directories,
actual verified numeric user/group IDs, and these command shapes. The four
filenames must be the exact manifest name and its three artifact references;
do not recursively copy unrelated owner files. `$REVIEWED_SOURCE` contains the
reviewed originals; `$IMPORT_COPY` and `$RUNTIME_COPY` are absolute destinations:

```bash
test ! -e "$IMPORT_COPY" && test ! -L "$IMPORT_COPY" || exit 1
test ! -e "$RUNTIME_COPY" && test ! -L "$RUNTIME_COPY" || exit 1
sudo install -d -m 0700 -o "$IMPORT_UID" -g "$IMPORT_GID" "$IMPORT_COPY"
sudo install -d -m 0700 -o "$RUNTIME_UID" -g "$RUNTIME_GID" "$RUNTIME_COPY"
for name in "$MANIFEST_FILENAME" "$AGREEMENT_FILENAME" "$RULES_FILENAME" "$REVIEW_FILENAME"; do
  sudo install -m 0600 -o "$IMPORT_UID" -g "$IMPORT_GID" "$REVIEWED_SOURCE/$name" "$IMPORT_COPY/$name"
  sudo install -m 0600 -o "$RUNTIME_UID" -g "$RUNTIME_GID" "$REVIEWED_SOURCE/$name" "$RUNTIME_COPY/$name"
  sudo cmp -- "$IMPORT_COPY/$name" "$RUNTIME_COPY/$name" || exit 1
done
```

Retain the expected hashes and verify both copies against the reviewed
originals. Set the importer environment variable to its copy for that command;
configure the service's managed environment to its runtime copy through the
declared environment-change procedure. Do not print or rewrite the remainder
of its environment. Re-read the actual deployed settings and evidence under
both identities. No evidence or environment change is performed by this guide.

## Supported import and readback

After the coding migration is installed, rehearse the exact licensed feed and
rules against an isolated database first. The production import is a declared
mutation through `scripts/run-ruled-mutation.sh` and the existing owner-role
wrapper. The following is a command shape, not populated execution evidence;
every variable must come from the reviewed operation and manifest:

```bash
QUILLMD_CPT_ENTITLEMENT_MANIFEST="$IMPORT_COPY/$MANIFEST_FILENAME" \
bash scripts/run-ruled-mutation.sh --declaration "$DECLARATION" -- \
  /opt/meddoc-pro/rebuild/.venv/bin/python \
  /opt/meddoc-pro/rebuild/ops/with_db_role.py \
  --credentials "$ROLE_CREDENTIAL_FILE" \
  --source /opt/meddoc-pro/rebuild --role migrator -- \
  import_terminology \
  --system CPT --path "$LICENSED_CSV" --sha256 "$CSV_SHA256" \
  --release-version "$RELEASE_VERSION" \
  --effective-from "$EFFECTIVE_FROM" --effective-until "$EFFECTIVE_UNTIL" \
  --source-url "$SOURCE_URL" --expected-count "$CODE_COUNT"
```

The importer re-reads the entitlement at its transaction boundary and writes
the `CodeSet`, codes, `CodingRelease` criteria/provenance and import audit
atomically. Identical imports are idempotent. Different bytes or metadata for
an existing version, overlapping dates, mismatched descriptors, missing rules
or changed permission evidence are refused; an existing release is never
silently replaced. The import performs no provider request.

Read `core.coding_licensing.cpt_status(service_date)` under the actual runtime
identity after import. Require `available: true`, `license_verified: true`,
`dated_release_verified: true`, and an empty `missing_requirements` list for
the intended date of service. Current agreement validity and service-date
content coverage are separate checks: an expired agreement cannot be enabled
by choosing an earlier encounter date. Retain the manifest/rule hashes, import
audit and date-scoped readback with the operation evidence. Successful fixture
tests or a catalogue import alone do not establish licensed runtime readiness.
