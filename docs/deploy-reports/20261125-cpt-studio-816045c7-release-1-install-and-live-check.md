# CPT Studio release 1 (6ab8e503a400 to 816045c72644): the install of 2026-11-25 and the live check

Session `738699b2`, 2026-11-25. Owner directions D399-D401 and D422 and answers D411-D413, D417 and D419, recorded verbatim in
`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`. Declaration
`docs/foundation/mutations/20261125-cpt-studio-release-1-install.md`: first committed 2e71431b568c (16:28:05Z, merged in #1527),
amended before any phase for D422 and for its own refutation, committed 7df845feb271 at 17:42:44Z, merged in #1528 as
8c1751f2deb4. Every phase ran through `scripts/run-ruled-mutation.sh` (`RULED_ACT_MAX_SECS=9000`) from the clean, detached act
checkout `/opt/meddoc-pro/.worktrees/cpt-r1-act-20261125` (8c1751f2deb4); every start came after the declaration's commit.
Receipts: `/home/claude/cpt-studio-install-20261023/`. The act's logs, the readings and the live check's evidence:
`cpt-r1-20261124/release/act/`.

**Result: installed and serving; the operator's enrolment waits for the owner. Every row of the declaration matched, the site
served throughout the switch (310 availability samples, all 200), nothing was deleted, the live check passed 25 of 25, and the
first post-check read every declared row but exactly the two the setup code makes, as the declaration says while the owner is
not there.**

## The revision

`816045c7264481bc6956285e1ca89991b9fcec2f`, the merge commit of #1525 (head 5a372f5b9a29; the trees are equal). Image
cpt-studio:816045c72644 = sha256:4c81cc9292b6b5c138bbc3c032db7cb80a7816cc60a01f985512d3173a7ccd30; /health/ answers
release_digest `eac720ae88e983ec` and no release.

Citations:
- on the revision: CI 45579306932, cpt-studio 45579306910, secrets-scan 45579306882, all success, read by commit and by branch;
- on the declaration's merge commit 8c1751f2deb4: CI 45671375943, secrets-scan 45671375888, both success before the act.

## Before the first phase

- The health check, report-only (`docs/preflight-reports/preflight-20261125T185206Z.md`): GO. No auto-fix was run.
- The operator's commands in the act checkout: byte identity exit 0 (control exit 1), exactly migrations 0017 and 0018, nothing
  changed between the revision and HEAD, the two stage digests, no placeholder, no rehearsal container.
- The live baseline read again at 18:52Z and at once before preflight (19:00:01Z): equal to the declared one (read 17:42:41Z). The
  first maintenance run's counts read again: orphans=0 unexpected=0 missing=0 past_retention=0, no file under an hour old.

## The act, phase by phase (UTC)

| step | when | result | judged against the declaration |
|---|---|---|---|
| preflight | 19:00:03-19:00:14 | exit 0 | coupling after; 9151 active, 9150 idle; both names resolving to 147.189.172.8 alone; no foreign task of uid 10150 or 10151; quillmd-cpt 1672b98db8cf |
| image | 19:00:21-19:01:08 | exit 0, sha256:4c81cc9292b6 | 0017 and 0018 judged safe; the conversion gate's %PDF-; the converter's self-test "ok, a PDF of 10121 bytes"; LibreOffice 7.4.7.2; cpt-studio:6ab8e503a400 kept |
| db | 19:01:11-19:01:17 | exit 0 | memory.state updated, the cgroup's memory.swap.max max to 0, no restart; log_min_error_statement panic, log_error_verbosity terse |
| converter | 19:01:21-19:01:32 | exit 0 | state started, volume root 10151:10150 0o750, healthy, no network |
| cert | 19:01:35-19:01:46 | exit 0 | stage served (1672b98db8cf, recorded by 6ab8e503a400), no order; both HTTP-01 routes proven |
| https-vhost | 19:01:50-19:02:01 | exit 0 | bbd482895d7926aa... over 1672b98db8cf, upstream 9151; observations one entry, attempt 0, 200; both hosts on the cpt-studio certificate, 421 for a mismatched name, each host on the other's connection; 2 TLS findings, as expected (TLS 1.3 ChaCha20 for each name, D27) |
| preflight again (after-https-vhost) | 19:02:07-19:02:19 | exit 0 | coupling after, quillmd-cpt bbd482895d7926aa, 9151 active |
| pre_app_r1.sh | 19:02:23-19:02:26 | PRE-APP PASS | exactly 0017_r1_security and 0018_r1_availability pending; the first maintenance run exactly as declared; the baseline equal with the db phase's three changes; jobs_active 0, the last audit event 72,695 s old |
| app | 19:02:35-19:05:41 | exit 0 | migrate one attempt, exactly 0017 and 0018; every session ended at S2 (116; SecurityEvent sessions.ended_at_install); S3 9151 to 9150, vhost bbd482895d7926aa to e31ce5801a7bb7b9, https 200; drain 130.6 s, not bounded out; list states: none changed; coding live, effort max, 25 dollars, 4 documents; logs kept ids only for the old web and worker; 310 availability samples from 19:02:57Z, all 200 |
| passages | 19:06:04-19:06:30 | exit 0 | the three files already loaded, nothing new |
| license-note | 19:06:31-19:06:42 | exit 0 | updated 0 |
| verify | 19:06:42-19:06:53 | exit 0, "installed 816045c72644 verified; co-tenants and app.quillmd.com unchanged" | as declared; the same 2 TLS findings |
| manage revoke-operator ops-agent | 19:06:59-19:07:16 | exit 0, "Revoked operator access from ops-agent (1 grant); every session of the account has ended." | by Kasra Rayat, reason sha256 73eb23da67ae |
| live check | 19:07:20-19:07:21 | 25 of 25 | below |
| post-check, first | 19:07:27 | exit 1 on two rows, judged | below |

The worker's first maintenance run (19:04:14Z): maintenance.daily and maintenance.daily_files_removed each once, 0 removed, 0
names hashed, 0 rows pruned, no step failed; maintenance.originals_verified 95 of 95, nothing missing, changed or unreadable.

## The live check

`live_check_r1.py` (084649de4c13c248), once, after revoke-ops-agent: 25 of 25 - health with the revision's digest and no release on
both hosts, no server version, HSTS; /ops/ 404 signed out; the walk's synthetic review agent signing in with the new cookies,
its list and the one named walk document (6c450473-ceb7-4f06-8660-d5794a3cb777) 200, /ops/ as that member 404, its sign-out, the ended
session replayed 401; on admin.quillmd.com, signed out, / and /ops/people to the sign-in, /login/ 200, /api/session 404. It wrote
only its declared footprint.

## The first post-check (while the owner is not there)

`post_check_r1.sh` (4a03afca60aae753), against the committed table (expected-deltas sha256 78c09b16fa6715c0): every declared row -
migrations 16 to 18, the two statement-logging settings, the database's swap, release 1's ten tables (2 access records, 3 rate
windows, the rest 0), one revocation, ops-agent's grant ended - and exactly the two rows the setup code makes, as the declaration's
stop condition says: `r1_table studio_onetimetoken: absent -> 0` and `r1_table studio_securityevent: absent -> 5`. Health, the
co-tenants, the ingress, the database's limits, the converter's seal, ops-agent, the maintenance run and nginx's logs (372 lines,
each with a request id, none holding a '?', nothing buffered to a temporary file) all as declared. It runs again after
issue-enrolment.

## Waiting for the owner

- issue-enrolment once he writes "ready" (D422: nothing else waits for him), then the second post-check, then his own enrolment on
  admin.quillmd.com with his passkey, his 10 recovery codes and one page of the console opened by him. Until then the console is
  closed: cpt.quillmd.com/ops/ answers 404 and admin.quillmd.com admits no session that has not passed a key.
- D22 (a new password for the existing accounts), the 23 earlier copies of the live database and the rehearsal copy, and the
  2026-11-20 documents stay his, as declared.

## The package and its reviews

The release package was refuted by four lenses with a re-test per finding (71 of 75 real: 2 high, 15 medium, 54 low), its script
repairs by two more (nine, one medium) and the edited declaration by three (43), each repaired before the commit; the amendment by
one more lens before its merge. Two mistakes are recorded in DECISIONS: a draft sentence said the owner had been asked about E2's
two Word losses before any message had reached him (D421; corrected before the commit), and the window's weekday once read Tuesday
(corrected).

## Rollback

Not needed. switch-back to the 6ab8e503a400 pair (its image is kept) stands as declared: a fresh preflight, SWITCH_BACK_DECISION in
words; it ends every session again and leaves release 1's stage and database additions.

## Notes for the next release

- E2 leaves a whole document inserted into a Word file (w:altChunk) out of the PDF with no notice: refuse such a file with a
  message instead (the recommendation the owner's D422 answered).
- TLS 1.3 ChaCha20 on the shared listener and the no-swap limits past the next systemd daemon-reload are recorded (the new
  server's or a later release's).
- Swap on the host read 3,843 of 4,095 MB used after the act, as before it.
