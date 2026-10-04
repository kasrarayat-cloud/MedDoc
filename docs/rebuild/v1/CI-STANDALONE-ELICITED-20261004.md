# Standalone elicited process-control discovery repair

The actual support job 111533732377 in CI run 37235498240 on candidate
`fc44b4a27366a4ab0514234d374f9f711cb7cfa9` failed with one discovery error.
Its 960 document controls passed. Standalone ops discovery ran 2008 controls
with one error and 17 skips: importing the new elicited process test imported
`core.tests.test_v3_supersession_floor`, then workflow models, before Django's
application registry was ready. The exact retained log is
`rebuild/.runtime/v1-sol-continuation-20261002/release-completion-20261004T200104Z/CI-C2-support-111533732377.log`.

The repair keeps process settings in the process test and materializes lazy
settings before its class override. It does not load the application registry,
create a database, change runtime code, or change CI's partitions or assertions.
The old import failed in a cold standalone process with actual exit 1. The first
repair exposed a separate lazy-settings initialization error and is retained.
The finished repair passed all 20 elicited process, fixed-stage and normalized
grading controls in a cold process, actual exit 0, in 18.730 seconds. Positive
wire/pricing checks and wrong-profile, caller-flag, nonempty-held and unknown
answer refusals remain. Network/database access was denied and attempted zero
times; the Django registry stayed unloaded; all source hashes stayed unchanged.

Exact logs, source inventories, helper and receipt are under
`rebuild/.runtime/v1-sol-continuation-20261002/release-completion-20261004T200104Z/ci-c2-import-repair/`.
These selective controls repair the demonstrated failure; the final candidate
still requires fresh complete CI. No earlier failed result is rewritten.
