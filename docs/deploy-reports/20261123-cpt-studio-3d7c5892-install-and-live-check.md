# CPT Studio's admin host installed in the app (2894cda36322 to 3d7c589261bd), release 1 of the admin.quillmd.com move, and the live check

Session `738699b2`, 2026-11-23. Owner direction D396 ("jsut move to admin.quillmd.com and lemme walk into live one"),
recorded verbatim in the CPT Studio rulings file with PR #1515; declaration
`docs/foundation/mutations/20261123-cpt-studio-admin-host-app-install.md` (committed 49eb7a0da3bb at 10:37:35Z, merged in
#1516 as 5ee9cbbddfb1 at 11:01:42Z). Every phase ran through `scripts/run-ruled-mutation.sh` from the clean, detached act
checkout `/opt/meddoc-pro/.worktrees/cpt-admin-host-act-20261123` (5ee9cbbd). The declaration's three operator
pre-checks passed there: the head detached and clean; the committed declaration byte-identical to the reviewed one
(sha256 226a5fcb7462aaa7); the revision to the act checkout changing only the declaration, the 27 byte-identical
pathspecs (82 files) and all of `cpt-studio/` identical to the revision. Receipts are in
`/home/claude/cpt-studio-install-20261023/`; the act's logs, post-checks and live evidence in
`cpt-admin-host-20261123/release/act/`.

**Result: installed and verified, with the site serving throughout (302 availability samples across the switch, all
200). The live check passed 46 of 46, the admin host's ten read-only probes included. Every row of the declaration
matched, and the database moved by exactly the check's declared footprint.** admin.quillmd.com still answers QuillMD's
notice in public, as declared: release 2 moves the web front end.

## The revision

`3d7c589261bd3370a3f1178de1f03c3bef98334e`, the merge commit of #1515 (its tree 0d0ba9a255c7 is the reviewed head
fc5b528e4's). Citation on the revision: CI 45149819630, cpt-studio 45149819620, secrets-scan 45149819817, all success,
the same three in both views, read twice; on the head: CI 45145637657, cpt-studio 45145637894, secrets-scan 45145637686.

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 11:02:44 | FIX-AND-GO (disk 89%) | not BLOCK; `docs/preflight-reports/preflight-20261123T110244Z.md` |
| preflight | 11:03:14-11:03:20 | exit 0, "baseline recorded; no blocking problem" | as declared: 9151 active, 9150 idle, no port problem; the quillmd-cpt vhost f816a27de9e6... for 9151; co-tenants and app.quillmd.com/health/ (200) recorded; nginx -t ok; the tree a descendant of the revision without a runtime change; the declaration's commit and sha256 recorded by the door |
| image | 11:03:31-11:03:52 | exit 0, cpt-studio:3d7c589261bd = sha256:5f440b960f8b | as declared: 610,870,159 bytes; cpt-studio:2894cda36322 kept |
| pre-app | 11:03:59-11:04:10 | PRE-APP PASS | as declared: the declared baseline file (0600) exactly the declaration's Baseline block; the dump 48 TABLE DATA (sha256 f209ad0bff22671a...); the restore migrated with cpt-studio:3d7c589261bd applied nothing; the baseline re-read equal to the declared one (read_at, the last audit and the sign-in count aside); jobs_active 0, runs_reserved_or_sending 0, runs_unreconciled_unknown 0, no reading job, the last audit 19,557 s old |
| app | 11:04:16-11:07:12 | exit 0 | as declared: migrate "No migrations to apply"; states recomputed, none changed (8 coded kept, 89 kept); unrunnable stages stuck 0; install counts 97 encounters, 8 coded, 0 holds (its note on the Fable tables' existing rows, unchanged since the previous release); S1 11:04:36 the incoming web on 9150; S3 11:04:42 to S4 11:04:46 the switch 9151 to 9150 (https 200 twice); the old web drained 130.3 s with 0 connections left; the previous pair retired |
| verify | 11:07:32-11:07:35 | exit 0, "installed 3d7c589261bd verified; co-tenants and app.quillmd.com unchanged" | as declared |
| post-check after verify | 11:07:41 | exit 0, unexpected differences 0 | the declared baseline proven to be the committed declaration's Baseline block (DECL_FILE); /health/ status ok, database ok, serving 3d7c589261bd; co-tenants as expected |
| live check | 11:07:52.27-11:07:53.66 (the evidence's request times) | pass, 46 of 46; 36 requests and 11 admin-host requests | below |
| post-check after the check | 11:07:59 | exit 0, unexpected differences 0 | exactly the declared rows: audit_events 1494 to 1495 and audit_event operator.viewed 131 to 132; login_attempts 131 to 133 (the two sign-ins, set aside by the comparison and as declared) |
| co-tenants | 11:08 | every co-tenant answers its expected status (4 distinct codes) | admin.quillmd.com still 503, QuillMD's notice, as declared |

## The live check

`console_check_h.py` WITHOUT --acts (the act checkout's ops/verify_login.py for its transport, TLS verified), against
https://cpt.quillmd.com, with `--admin-loopback http://127.0.0.1:9150 --admin-release 3d7c589261bd...`:

- Before any request to cpt.quillmd.com: the new web's /health/ on the loopback, with Host admin.quillmd.com, named the
  revision.
- The cpt arm, 35 checks, as the previous release's: the operator's console pages framed, the fonts, the session ended;
  the member's 404 on every console page and on the real ids; the console's own acts with ids that name nothing, 404.
- The admin host on the new web, 10 checks: /health/ naming the revision; GET and HEAD / 302 to /login/; /api/session
  404 (cpt.quillmd.com's 401 from the same web the control); the operator sign-in page 200; /ops/people signed out 302 to
  /login/?next=%2Fops%2Fpeople; /ops 302 to /ops/; PUT /login/ and POST /ops/people/add with a valid CSRF token and
  Origin https://cpt.quillmd.com, each 403 from the admin host's own-origin rule; and admin.arm_complete.
- No act was posted on live; no password was printed or written. The evidence:
  `act/live-check-20261123T110752Z/console-evidence.json` (0600).

## For the owner

- Nothing changes in a browser yet: https://cpt.quillmd.com/ops/ is the console as before, and admin.quillmd.com still
  shows QuillMD's notice. Release 2 moves admin.quillmd.com onto this app (its own certificate covering both names, the
  web front end, and the QuillMD checks that expect a notice there), and then admin.quillmd.com opens the operator
  sign-in.

## Measured before the act (in the declaration)

The full gate on the revision's tree (Django 722, ops 538, verification 37, walk 97, pip-audit clean); the design
refutation that split the move into two releases; two refutation rounds of the finished diff (9 and 8 findings, no
high, every one repaired); the install rehearsal on a restored copy of live with the final package (the check without
acts, its footprint measured over every table's exact row count; then every act; then the switch-back); two read-only
review rounds of the release package (6 then 5 findings, no high), every finding repaired, the round-2 repairs verified
with the lens's own batteries.

## Rollback

The previous image (2894cda36322, sha256:2b65b45cfab6...) is kept. The incident path is the installer's `switch-back`
(a fresh preflight, then act_h.sh switch-back with SWITCH_BACK_DECISION recorded), which recreates the previous pair from
that image; rehearsed on the copy after the acts, it closed no stage and changed no state. Under the previous revision
the admin host's urlconf is gone, and nothing public changes, since the front end does not route admin.quillmd.com to
the app before release 2.

## Notes for the next release

- The package review again found what the change's refutation could not: the new admin probes could have signed the
  real accounts in on live through a loopback the --acts guard never compared, and round 1's repair of one probe could
  itself have written a row on live were the rule it tests missing. A repaired probe gets the same question as the code
  it probes: what does it write when the thing it checks is broken?
- The old web's drain bound (130.3 s) is most of the app phase's time, as before.
