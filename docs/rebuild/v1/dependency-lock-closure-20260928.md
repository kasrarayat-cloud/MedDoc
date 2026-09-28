# Production dependency closure repair — 2026-09-28

Source base `527930e7b46121abf916904ce78eb5046f195a47`, isolated
`v1-dependency-lock-repair`. No application source, shared tree, deployment,
provider call, network download or package installation changed in this task.

## Failure and correction

The exact base verifier refuses with `dependency_manifest_mismatch`:
requirements declare **89 packages**, while the production manifest still
records **64**. Updating its envelope alone would also fail: the old parser
accepts only version pins and cannot parse the reviewed official model URL.
The old lock, manifest and requirements are preserved in
[before evidence](dependency-lock-closure-20260928/before-requirements-production.manifest.json),
alongside the [exact refusal](dependency-lock-closure-20260928/002-base-red.log).

The format2 manifest and lock now contain the full **89 artifacts: 88 PyPI
wheels plus en_core_web_sm3.8.0**. Every original64 artifact's name, version,
filename, byte count and SHA256 is unchanged. The added25 were recovered from
local pip HTTP cache; every hash matches the previously reviewed
[syntax acquisition record](notes-workflows-20260927/evidence/dependency-lock.json).
All89 wheel bytes, sizes and top-level distribution/version METADATA identities
were checked. The original acquisition date is retained; verification is dated
2026-09-28. No new upstream retrieval is claimed.

Only the literal reviewed `en-core-web-sm` requirement, official
`github.com/explosion/spacy-models` release URL, version3.8.0 and wheel hash
`1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85`
are permitted as a direct URL. The lock additionally requires the matching pip
`--hash` option. A version-only model pin, changed owner/host/version/name/hash,
credentials, query parameters, markers, index directives, alternate source
metadata and duplicate pins refuse even when the enclosing digests are updated.
Other packages remain exact version pins from the sole declared PyPI index.
Artifact filenames must identify their recorded package/version; paths and
unrecorded source fields refuse. Optional `--wheelhouse` verifies an exact local
inventory, rejects missing/extra/symlink artifacts, and checks sizes and hashes.
This is consistency with reviewed acquisition evidence, not independent publisher
attestation or vulnerability clearance.

## Verification and artifact path

- Six focused unittest methods PASS, including17 contract mutations and15
  direct-URL mutations, model hash agreement, actual local inventory refusal
  controls and production installer order/flags.
- Full89-wheel offline pip resolution PASS with `--dry-run --ignore-installed
  --no-index --find-links <verified-wheelhouse> --require-hashes --only-binary`.
  All89 reported download URLs were local files and their hashes match the
  manifest. The private offline probe expresses the model as a version pin so
  pip cannot contact its remote direct URL. It does not replace the shipped lock.
- The installed pip parser separately accepts all89 **shipped lock** entries,
  including the exact model URL fragment and explicit hash. No HTTP was invoked.
- The unchanged production `bootstrap-host.sh` first runs the stdlib verifier,
  then installs `requirements-production.lock` using `pip --isolated`, explicit
  PyPI index, `--require-hashes`, and wheels only. The reviewed model URL is in
  that same lock. No extra installation step or runtime download is introduced.
- `build-release.sh` still builds `quillmd-<reviewed full SHA>.tar.gz` from the
  committed tree; that archive includes both lock and manifest. Bootstrap uses
  the extracted production application path under `/opt/quillmd-production`
  and records the lock SHA in its install receipt. No artifact was deployed and
  no new host or release admission is asserted.

[Focused log](dependency-lock-closure-20260928/013-final-focused.log),
[89-wheel validation](dependency-lock-closure-20260928/014-final-wheel-validation.log),
[offline closure summary](dependency-lock-closure-20260928/015-offline-closure-summary.json),
[pip parsing](dependency-lock-closure-20260928/016-production-pip-parser.json),
[source hashes](dependency-lock-closure-20260928/source-sha256.json).
The root's separate86-package audit and explicit non-PyPI model exception retain
their own scope;89 locked artifacts are not relabeled as89 audited packages.

## Retained instrument failures and limits

The first CLI invocation omitted its required `--root` and exited2; the corrected
exact-base invocation exited1 for the actual contract mismatch. The first wheel
identity script counted vendored METADATA inside pip as a second distribution;
it stopped before writing the new contract. Its initial dependent unittest run
therefore retained19 errors against the old manifest. The corrected byte check
counts only the top-level `.dist-info/METADATA` record; subsequent contract and
focused checks pass. Both failed instruments remain in evidence.

Private runtime (including original bytes and full pip resolution report):
`/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/dependency-lock-repair-20260928/`.
Finished-diff independent refutation is required before integration. This repair
does not alter CI partitions, pricing scanners, application requirements or
clinical behavior, and does not replace exact-head CI.
