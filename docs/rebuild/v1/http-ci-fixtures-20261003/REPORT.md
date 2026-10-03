# Persisted configuration and active-route isolation CI repairs

Base commit: `3d612a4f51f5b8ee5803928b7bd7b8fca2236da2`. Only `core/tests/test_stripe_credentials.py` and `core/tests/test_isolation_matrix.py` changed, plus this evidence. No application, authorization, source, destination-role, billing or import guard was changed.

The original official failures are bound to CI run `37158506012`, source `15f87bb2e7a487225711fa52c8092e279767ad01`. Six relevant failure blocks are retained unchanged in `original-failure-blocks.json`; the original complete log remains in the clinical runtime evidence. These failures do not demonstrate a billing page crash or unauthorized access.

## Stripe configuration test

The old database-free `SimpleTestCase` called the entire `integration_status()` interface. That interface now reads persisted ICD release metadata. Django correctly prohibited that database query; the test's assignment failed and its later out-of-context assertion raised `UnboundLocalError` for its own local `payments` variable.

Only the full integration-interface method moved to a database-isolated `TestCase`. Pure credential parsing and checkout authorization tests stay database-free. All original configured/unconfigured payment wording assertions remain, inside their subtest scope. The new persisted metadata control verifies a current ICD release, expired coverage and a coverage gap while preserving both release rows and creating no job, reservation, usage, payment or ledger entry. Payment requests remain mocked and uncalled. This does not verify a real Stripe payment or installed ICD datastore.

## Active authorization versus retired endpoint absence

`destination_roles.suggestions_enabled()` unconditionally withdraws note-derived signing offers under the October 3 signing rule. `AccessMiddleware` therefore uses `quillmd.urls_doctor`, which never mounts the `accept_role_suggestion` endpoint. Its older enabled-setting test expected GET 405 and an owner response other than 404; both expectations described the withdrawn endpoint.

The original route pattern and object isolation decision remain explicitly recorded as historical constants. Its absence has a separate contract test: owner, sibling-department clinician and other-clinic clinician all receive 404 for GET/POST under both old setting values; requests use the actual doctor URLconf and complete core-table snapshots remain unchanged. These twelve absence checks **are not access-control proof**.

The active object matrix retains every current route and its authorized positive control: **21 active object routes, 126 intruder method checks and 21 authorized owner route controls**. A newly mounted pattern using an existing route name still fails classification. The new SOAP start route is explicitly classified and exercised in three denied cross-department creation attempts.

An additional positive control uploads a genuine three-row DOCX with patient signature, initials and ordinary Plan; verifies original hash/import binding; creates a document; saves a clinician's own ordinary Plan correction; verifies the persisted edited text and actor through the authorized API; and preserves both blank signing areas and the immutable original. Three other-department actors cannot overwrite that saved answer and cause no core-table changes. This positive control proves a real persisted manual workflow rather than inferring functionality from a redirect. It creates no generation job or provider request.

The retained **124 served access-control checks**, their tested revision, raw evidence and denominator are unchanged. The current focused checks supplement that record; they do not silently replace it or claim the retired endpoint is active.

## Verification and limits

The two focused modules passed **24/24 methods, no skips, 58.235 seconds, actual process exit 0**. The dedicated synthetic PostgreSQL test database was destroyed. `git diff --check` passed. `VERIFICATION.json` records test and assertion counts, while `source-manifest.json` binds the actual tested source and the unchanged application files. Runtime evidence is under `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/http-ci-fixtures` with its exit log adjacent.

No provider, live payment, installed database, service or public surface was mutated. Final required CI on the integrated release commit remains root's responsibility. Separate Word/clinical failure clusters require their actual source-bound refusals and affected checks; this packet does not reinterpret those failures as passing.
