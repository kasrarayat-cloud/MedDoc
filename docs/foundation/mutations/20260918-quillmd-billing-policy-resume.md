# Private billing-policy activation resume — 2026-09-18

The declared activation of release d2e45b533396390c36d1ffa681c188126be556ce
(declaration 20260917-quillmd-billing-policy.md @ fd3af1af) ran at
2026-09-18T01:30Z and stopped at stage applying_two_new_tables. Migration
core.0012_billing_policy was applied once; core_costreconciliation and
core_platformcost exist and are empty; schema and catalog checks passed. The
guard then refused because the activator expected all 33 existing tables to be
row-identical, while Django's post-migrate bookkeeping legitimately added two
django_content_type rows (core.costreconciliation, core.platformcost) and eight
auth_permission rows (add/change/delete/view for each). No other existing row
changed. The activator stopped the three private services, kept its lock and
wrote its failure result. Permanent main is fast-forwarded to d2e45b53; the
protected environment still names release 8f8a6763; collectstatic did not run.
This is a guard-expectation defect, not data damage.

Expected delta of this resume, declared before the act: none in the database.
All 35 tables keep identical rows across the restart, including the ten
bookkeeping rows and the single 0012 history row; the two new tables stay
empty. Private originals, exports, receipts and mail bytes unchanged. The
installed units, the pinned Word runtime and the six protected shared
containers unchanged. Static assets are collected with the reviewed public
permission policy. Only the release line of the protected environment changes,
to the resume merge SHA, and the same three units start. Zero provider calls,
zero migration commands. Public statuses remain www 200, app/admin 503, pro 410.

Only three tracked paths may differ between d2e45b53 and the resume target:
scripts/resume-billing-policy.py, rebuild/ops/test_billing_resume.py and this
declaration. The resume runs read-only first from permanent main and proves
the recorded partial state by hash (failure result and original lock), by
schema/catalog equality with the recorded post-migration state, by row
fingerprints of every existing table excluding exactly the ten bookkeeping
rows, by the bookkeeping rows themselves, by stopped services, by unchanged
private files and by the authenticated restore proof of backup
20260917T234313Z-56be2efa. It then runs once through run-ruled-mutation.sh with
this committed declaration: fast-forward main to the resume target, Django
check, collectstatic, replace only the release line, start the same units,
verify same-PID identity proofs, interfaces, health at the exact target,
fingerprints, files, units and co-tenants; write an exclusive 0600 result and a
hash-bound backlink that resolves the original activation lock. Any failure
stops the services and retains the lock and evidence; never rerun blindly.
Never rerun the original activator or the migration.

Afterwards: the read-only console check, the read-only billing audit and a new
encrypted backup with isolated restore proof. No claim of invoice
reconciliation, Stripe, Resend delivery, offsite restoration or independent
testing follows from this resume.
