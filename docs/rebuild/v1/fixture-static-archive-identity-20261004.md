# Normal fixture collectstatic identity repair

The actual C3 fixture setup completed normal `collectstatic`, producing 21 public files under `rebuild/staticfiles`. The served identity helper then refused `untracked_runtime_source_refused` before reading credentials: its archive walk allowed only the archive and `.runtime`, while the unchanged application settings explicitly use `STATIC_ROOT=BASE_DIR/'staticfiles'`. All 771 archived source files still matched their original bytes. The original failure is retained; this repair changes neither that C3 archive nor its services.

`ops.verify_fixture_persisted.archive_identity` now verifies the generated static tree before admitting that separate top-level directory. It still verifies every archived source file and refuses any other untracked source. The current accepted inputs are the archive-bound `static/app.css` and `static/app.js`, plus three exact public assets from pinned django-otp 1.7.3. Dependency versions must match the unchanged requirements: Django 5.2.17, django-otp 1.7.3 and WhiteNoise 6.12.0. Each dependency asset must match both its committed SHA-256 identity and the installed distribution's SHA-256 RECORD entry.

For those five unchanged-byte inputs, the verifier independently computes the normal Django MD5 filenames and complete manifest mapping/hash, and the actual WhiteNoise canonical compressed bytes. It compares every original, hashed and compressed output to those expected bytes. The current qualified environment has gzip output and no Brotli output: five originals, five hashed copies, ten gzip copies and one manifest. An environment with Brotli must provide the exact effective compression results from the same normal dependency; its additional outputs remain bounded. This is a read-only computation, not another `collectstatic` run against the actual demo.

The manifest must have the exact mapping, version and hash, serialized by the normal JSON formatter. Finder key order is allowed to vary; extra/duplicate fields, altered bindings and arbitrary JSON are refused. Generated files must be bounded regular files owned by the operator, have one link and mode0600/0644, and remain identical across descriptor/path stat checks. Directories must be operator-owned0700/0755; links, unknown files, unexpected empty directories and changed public metadata refuse. The archive is still checked before this separate generated-tree admission.

This deliberately supports the five currently qualified inputs. URL/import rewriting, a different static source catalogue, changed dependency assets/versions or ineffective compression require additional qualification and currently refuse. It does not skip an arbitrary `staticfiles` tree, copy a saved success flag, weaken source identity, alter application static settings, rebuild the preview or change any clinical/financial state.

Actual finite verification on the finished helper:

| Check | Actual result | Scope |
|---|---|---|
| Original C3 identity against its actual unchanged archive/generated tree | exit1,0.567seconds | Retained `untracked_runtime_source_refused`;771 source files and21 generated files observed |
| Corrected identity against that same actual C3 tree | exit0,0.667seconds | All771 archive files and all21 public assets verified; both byte inventories unchanged; no settings/credentials/DB/socket/service calls |
| Existing and affected source-only reader class | exit0;13 methods,2.900seconds | Includes original archive/health/clinical-example guards and normal storage-backend positive construction |
| Final three changed static methods | exit0;0.691seconds | Genuinely generated manifest/compression positive; altered/missing originals,gzip/manifest, extra nonstatic file/empty directory, file/directory links, hardlinks, writable asset, source alteration, manifest rebinding, wrong dependency asset and wrong Django/OTP/WhiteNoise versions all refuse |

The final three methods are a subset of the 13-method class, not three additional unique methods. Their external driver denied transport/process operations and credential-file reads; no attempt occurred. The tests generate public assets only in their own synthetic temporary directories using the normal `PublicCompressedManifestStaticFilesStorage` backend; they never mutate the C3 demo. Every bounded child was reaped without timeout and its PID was absent afterwards. `git diff --check` passed. No database, browser, provider request, push or service mutation occurred.

Protected raw evidence is `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/release-completion-20261004T200104Z/staticfiles-archive-guard-20261004/`:

| Receipt | SHA-256 |
|---|---|
| Original actual refusal `original-C3-actual-refusal/process.json` | `7ee3485f1dee861973db269d3d6aca80bdac3c335b1d7c16f90c934b04ade088` |
| Corrected actual archive/static proof `corrected-actual-C3-static-identity/process.json` | `d9cb2bb5914970a39ee817d9171d3bab8bf48fb11a5e542bca48cdc7cda35f51` |
| Original13-method class receipt `affected-source-only-methods/process.json` | `cbc142b92ca38d78745a1eb67afe3d339bb817f3ef4d0ccfeebf7eb28195e1b7` |
| Final affected controls `final-affected-static-controls/process.json` | `5f971131109864e1fdc34f6dd7a37e23097bf96771740f492e780526798d0c09` |

Root's original integration failure remains at `private-factory-C3/SOURCE-GUARD-STATIC-ACTUAL-FAILURE.json`, SHA-256 `fe6bcc242305e0cadd593f9f7fd17d3840879647448a4de811d3709dfc252f99`. The finished verifier SHA-256 is `98afce7bcc15e1827294c1d3e4be83474846c49185e0c9aef60cf1ed40bab4b1`; final tests SHA-256 is `29258286bed50e04bd3d34f15a52e178165987a36f6c825e56a70dcfd7568a3e`.

These are source-only admission proofs on the actual retained C3 artifacts. Root must integrate this repair into its separate C4 candidate, review the finished diff, obtain exact-candidate CI and recreate/rebind the normal factory before claiming C4 served identity or browser acceptance. The unrelated actual browser seed-review failure remains unresolved by this fix. Clinical/live-provider qualification, broad Word thresholds and human acceptance retain their independent scope.
