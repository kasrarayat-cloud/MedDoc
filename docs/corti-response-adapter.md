# Corti response adapter — offline preparation only

This adapter consumes retained JSON and prepares an inert clinician replay.
It is not registered as a live provider, view, task or acceptance route. It has
no provider client, credentials, database writes, clinical export hooks or
activation switch. The original single-call evidence and its FAIL verdict are
inputs and remain unchanged.

## Selection and verification boundaries

`rebuild/core/corti_response.py` accepts original text contexts and an explicit
service date. Only objects in the top-level `codes` array can become
`proposed_selections`. Candidates, nested alternatives, unknown fields and the
complete provider response remain in diagnostics. Malformed selected records
and normalized duplicates are quarantined; candidates cannot repair them.

Every proposal retains the original code, display text and evidence. ICD dots
are normalized for lookup, without rewriting the provider value. Evidence is
checked against its original context index and end-exclusive source offsets.
Missing/invalid evidence, unknown codes, missing releases, unauthorized source
records and overlapping releases produce explicit non-actionable states.
Textually exact evidence is not automatically clinically relevant evidence.

All proposals have `approved=false`, `selectable=false` and clinical applicability
requiring clinician review. `dashboard_activation_allowed` is always false.
Provider fields with those names cannot override these properties.

## Terminology trust boundary

`DatedTerminology` accepts **trusted caller-supplied** catalogue releases. The
response cannot supply a release, authorization or verification state. The
offline ICD loader verifies the full existing official source file against its
audited hash, count and CDC/CMS provenance, then applies inclusive service-date
coverage. There is no nearest-year fallback.

A verified term means dated catalogue membership and a reference description;
it does not mean clinical approval, sequencing approval or reimbursement. When
descriptions differ, both remain visible. The adapter has no per-code correction
table, CPT time thresholds or replacement descriptor for the observed defect.

The replay loads the already retained official FY2027 ICD-10-CM source. The
separate private audit also checks official Index/Tabular instructions for the
two diagnosis selections. No authorized CPT source was established: the current
static runtime configuration resolves to the absent default entitlement manifest.
The CPT result therefore remains selected by the provider but terminology-unverified.

`CatalogRelease` is not a license checker. It must never be constructed from a
browser/provider payload or used as a bypass for `coding_licensing.cpt_status()`.
A future live bridge must enforce that existing current-entitlement, dated-content
and licensed-criteria gate under the actual runtime identity. No CPT loader or
live bridge is provided by this preparation.

## Reproduce a private replay

Run from the isolated checkout, with an existing retained evidence directory and
a **different** private output directory. The input directory must contain its
original `sha256-manifest.json`, request, raw response, transport, expectations,
and evaluation. No imports or downloads occur.

```bash
python3 rebuild/ops/replay_corti_response.py \
  --evidence-dir /home/claude/quillmd-corti-test/20261016-single \
  --output-dir /home/claude/quillmd-corti-test/a-new-private-replay \
  --service-date 2026-10-16 \
  --icd-metadata /home/claude/quillmd-corti-test/adapter-replay-20261016/icd-metadata.json \
  --icd-file /opt/meddoc-pro/rebuild/.runtime/coding-release-20261014/terminology-review/fy2027-official-codes.txt
```

Omit both ICD options to demonstrate unavailable terminology. The tool verifies
the original manifest and raw hashes, writes new files exclusively with private
permissions, rechecks all original hashes and preserves the original FAIL.
It refuses to overwrite previous replay files. The preview is a local HTML file,
uses no external resources or JavaScript and exposes no clinical controls.

Focused tests require only Python's standard library:

```bash
PYTHONPATH=rebuild python3 -m unittest core.tests.test_corti_response -v
```

The test catalogue is explicitly synthetic and grants no CPT rights. Actual
retained-response replay, source audit and browser evidence stay in the private
artifact directory; they are not committed as a clinical catalogue or fixture.

## Activation remains blocked

The original response-quality FAIL is unresolved. Its CPT display defect is
present in the provider's raw bytes; no upstream catalogue/version was included
in retained metadata, so a particular terminology version cannot be blamed.
Authorized CPT content and criteria covering the encounter date remain missing.
The adapter is intentionally disconnected from provider execution and clinician
acceptance/audit persistence. Existing gates and broader validation would be
required before any separately authorized activation. A single saved response
does not establish production readiness.
