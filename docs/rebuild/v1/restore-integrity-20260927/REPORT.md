# Production restore integrity checker — 2026-09-27

Prepared repair; independent review pending. The former checker accepted nine invented, enabled
trigger names as a valid restore. Root reproduced the false green before changing the checker.
Its own positive fixture had represented integrity by a count alone.

The new release contract binds17 exact table/trigger/event/function definitions and10 function
bodies from reviewed migration SQL, never from the database being checked. It also checks
function schema, language, argument/return type and execution properties, trigger enabled state,
exact full trigger definitions, the public/origin connection context and absence of extra
custom triggers on core tables. The declared count must match the release contract. Fixed
counts are reported; database names or function bodies are not emitted.

Ten focused tests passed, including equal-count definition/body/property replacements, missing,
extra, duplicate, malformed rows, wrong connection context and an operator declaring the old
count. One separate fresh-migration PostgreSQL test passed on isolated55707: actual installed
catalog definitions match the current17-trigger contract. Existing filesystem/invariant/live-
target refusal tests remain in the focused run. No provider or production operation occurred.

Two setup probes were invalid and did not establish a result: system Python lacked psycopg;
the isolated default database had no django_migrations table because test databases are created
and removed per run. Corrected probes used the release venv and fresh Django test database.
Original RED and final outputs are preserved.

This is a point-in-time catalog check, not protection from an owner who can change the checker
and database together. It does not add DELETE/TRUNCATE guards beyond those present in the
reviewed migrations, prove role configuration, or close retention policy. The installed legacy
backup drill remains its original count-only instrument and is not reclassified by this change.
Current target restores must use the artifact's own checker/contract; legacy revision's nine
triggers cannot certify this candidate. Production target, backup pairing, actual recovery and
independent custody are still unverified.
