# Explicit ordinary-profile import fixture — 2026-10-04

The unchanged exact `AutoImportWorkflow.test_valid_ordinary_parts_route_allows_large_v3_import_without_generic_batch_flag` reproduced `800 != 100` on `c8578742bba91e87b4edcc52d9eb810afc1af3e7`: one method, 4.684 seconds, actual exit 1. Its original failure and source hashes remain retained.

Sonnet 5.5 defaults to ordinary-v4 when `V3_FIELD_RELATIONS_SWITCH` is unset. Setting only the older boolean false therefore does not select the generic profile. The fixture now explicitly sets both ordinary-profile settings true for its positive control and both false for its disabled-profile control. The original different-model and invalid-rate negative controls remain unchanged, as do the authenticated 101-field original upload, persisted mapping and actual confirmation route. The generic batch flag remains false. Each negative subcase is identified independently.

The same one-method packet passed in 4.858 seconds, actual exit 0, under a 180-second deadline. Before/after test and three application configuration/mapping hashes match; application source was unchanged. Both test databases were destroyed and direct PostgreSQL catalog absence checks returned zero. No provider request occurred. This affected fixture result does not certify the coherent candidate's full CI, Word corpus, private served demonstration or installed application.

Exact logs and hashes are in `verification.json`; raw evidence remains under the protected task-owned directory named there. The serialized QA slot was released after the actual process exit and database absence checks.
