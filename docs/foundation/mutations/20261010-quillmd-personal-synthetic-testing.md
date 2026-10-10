# Exact personal synthetic clinician enrollment — prospective declaration

Installed baseline: `2f576b78867ef4bded3027d169169df71701ed7b`.
Direct owner authority: `../rulings/2026-10-10-quillmd-personal-synthetic-testing.md`.

## Expected source and schema delta

Add exactly recovered nonstaff clinician `e1a20625-455d-4603-a874-794327b19d10`
with existing department `46a5abdd-36f1-41f0-968f-8c09c39d9daa` to standing
synthetic test admission. Preserve existing actor pairs. Do not alter the old
finite `quillmd_delivery_actor` function or historical finite allowlists/migrations.
Use one new forward SQL migration after `0024_standing_testing_authority`: add a
standing-specific actor helper and replace only the four existing function bodies
whose standing branches currently call the finite actor helper. Retain every
finite branch byte-for-byte. Runtime admission must pin the complete revised
functions and existing enabled trigger definitions. Adapt backup qualification
only for this exact standing pair, preserving historical invariant statements,
manifest keys, encrypted backup primitives and the ten retained reference queries.
Tests, operational documentation and authority records may accompany this change.
No new application tables, columns, triggers, constraints, account or clinical rows.

## Native installation and preservation

Require focused application/actual PostgreSQL tests, independent finished-diff
refutation, complete exact-commit CI and a merge through the reviewed wrapper.
Bind the concrete adapter, merged release and exact source manifest before action.
Use the existing native drain/encrypted backup/preservation procedure. Stop only
the three QuillMD native units, capture a fresh encrypted backup and quiescent
all-table/schema/function/sequence/grant/file/service baseline before migration.
Apply only the single newly unapplied migration through MigrationExecutor in one
transaction, without post_migrate signals or historical replay. The only allowed
row delta is one `django_migrations` row and its sequence advance. Every original
migration row and all other 38 tables retain exact contents. The only schema delta
is the named standing helper plus four qualified function-body replacements.
All table/sequence/retained function ACLs, trigger bindings and enabled state remain
unchanged. Preserve all password/session/MFA/membership state, documents, approved
versions, billing/provider histories and unresolved reservations. No wallet movements.

Publish only coherent merged source from clean main, preserving permissions and
service readability. Runtime environment changes only by release identity. Keep
all ingress/static/private-demo configuration, unrelated projects, existing backups,
rollback material and scheduled-backup controls intact. Maintain 28 GiB reserve.
On failure preserve evidence and recover a known compatible release; never start
incomplete software. Preserve baseline observations from independent requests;
compare the strict migration window while services remain drained.

## Served verification

Verify active exact pair, synthetic-only mode, unchanged nonstaff clinician role,
application runtime_admission and the installed PostgreSQL standing actor helper
on normal served release. Wrong department, unlisted actor, inactive membership,
unauthorized role and finite-campaign use of the added actor must still fail.
Use read-only production transactions and isolated rollback fixtures for negative
mutations. Do not request a new budget, read credentials, log in as the recovered
account, consume its password-setting link, create clinical records or call models.
Retain a token-free explanation of actual served identities and enforcement paths.
