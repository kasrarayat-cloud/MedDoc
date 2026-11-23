# CPT Studio's admin dashboard installed at cpt.quillmd.com/ops (3ce5383ce485 to 2894cda36322), and the live console check

Session `738699b2`, 2026-11-23. Owner direction D395 ("just release the admin dashbaord from the new design"; the controls
chosen: People and roles, Workspaces, Spending and usage, Activity log; the address: "Build now, move later"), recorded
verbatim in the CPT Studio rulings file; declaration `docs/foundation/mutations/20261123-cpt-studio-admin-console-install.md`
(committed 1bf562af6f75 at 05:05:03Z, merged in #1513 as de9d703242b2 at 05:31:39Z). Every phase ran through
`scripts/run-ruled-mutation.sh` from the clean, detached act checkout `/opt/meddoc-pro/.worktrees/cpt-admin-console-act-20261123`
(de9d703242b2, a descendant of the revision that changes nothing under `cpt-studio/` or the door). The declaration's three
operator pre-checks passed there: the 29 byte-identical pathspecs (84 files) exit 0, with the positive control on
operator.py exiting 1; no migration changed; nothing under `cpt-studio/` or the door changed since the revision. Receipts
are in `/home/claude/cpt-studio-install-20261023/`; the act's logs, post-checks and live evidence in
`cpt-admin-console-20261122/release/act/`.

**Result: installed and verified, with the site serving throughout (299 availability samples across the switch, all
200); the live console check passed, 35 of 35; every row of the declaration matched, and the database moved by exactly
the check's declared footprint.**

## The revision

`2894cda36322968ea5dd612876a85d25c0011613`, the merge commit of #1512 (its tree e3f6dc5d828f is the reviewed head
4bba94674's: main had not moved since the branch point). Citation on the revision: CI 45108957893, cpt-studio
45108957970, secrets-scan 45108957993, all success, the same three in both views; on the head: CI 45106442968, cpt-studio
45106442960, secrets-scan 45106442913. Held declarations over the range 3ce5383ce485..2894cda36322: none (first-parent
merges #1512, #1511 and #1510; 23 runtime files, all under cpt-studio/; 8 declarations and reports name one, and every
revision they name is an ancestor of the running revision; the positive control passed).

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 05:32:44 | FIX-AND-GO (disk 89%) | not BLOCK; `docs/preflight-reports/preflight-20261123T053244Z.md` |
| preflight | 05:32:50-05:33:01 | exit 0, "baseline recorded; no blocking problem" | as declared: the quillmd-cpt vhost 259b895dd130... for 9150; 9150 active, 9151 idle, no port problem; the live web and worker on sha256:9486d0bfd111; co-tenants and app.quillmd.com/health/ (200) recorded; nginx -t ok |
| image | 05:33:23-05:33:45 | exit 0, cpt-studio:2894cda36322 = sha256:2b65b45cfab6 | as declared: 610,801,623 bytes, labelled with the revision, the image phase's gate passed; cpt-studio:3ce5383ce485 kept |
| pre-app | 05:34:00-05:34:11 | PRE-APP PASS | as declared: the declared baseline file (0600) exactly the declaration's Baseline block; the dump 48 TABLE DATA (sha256 496df32129329fd1...); the restore migrated with cpt-studio:2894cda36322 applied nothing; the baseline re-read equal to the declared one (read_at, the last audit and the sign-in count aside); jobs_active 0, no run reserved, sending or unreconciled, no reading job; the last audit event 65,463 s old |
| app | 05:34:20-05:37:17 | exit 0 | as declared: migrate "No migrations to apply"; UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS 97 encounters, 8 coded (its note on the Fable tables' existing rows, as before); S1 05:34:40 cpt-studio-web-next on 9151; S2 05:34:44 the old worker parked; S3 05:34:46 the vhost switched 9150 to 9151 (259b895dd130... to f816a27de9e6...), `nginx -t` clean, https 200; S4 05:34:49 the new worker, coding live at effort max ($25 ceiling, 4 documents at once); S5 the old web drained in 130.6 s with 0 open connections, stopped and parked; S6 05:37:11 RECOMPUTE_STATES 8 coded encounters, none changed, 89 kept, and the parked pair of 3ce5383ce485 removed (retire_parked), its image kept. Availability: 299 samples at 0.5 s, all 200, the releases seen 3ce5383ce485 then 2894cda36322 |
| verify | 05:37:46-05:37:52 | exit 0, "installed 2894cda36322 verified; co-tenants and app.quillmd.com unchanged" | as declared |
| post-check after verify | 05:38:00 | exit 0, unexpected differences 0 | the declared baseline proven to be the committed declaration's Baseline block (DECL_FILE); /health/ status ok, database ok, serving 2894cda36322; co-tenants as expected |
| live console check | 05:38:12.97-05:38:14.30 (the evidence's request times) | pass, 35 of 35, 36 requests | below |
| post-check after the check | 05:38:23 | exit 0, unexpected differences 0 | exactly the declared rows: audit_events 1493 to 1494 and audit_event operator.viewed 130 to 131; login_attempts 128 to 130 (the two sign-ins, set aside by the comparison and as declared); the last audit event the check's own (operator.viewed, 05:38:13Z): no member activity in the window |

## The live console check

`console_check_a.py` WITHOUT --acts (the act checkout's ops/verify_login.py for its transport, TLS verified), against
https://cpt.quillmd.com, 36 requests:

- As ops-agent (the operator with no membership): signed in to /ops/; /ops/, /ops/people, /ops/workspaces, the first
  workspace's page, /ops/spending, /ops/activity, /ops/activity/sign-ins and the newest encounter's page each 200 with the
  console's frame, navigation and heading; the four self-served fonts 200, TrueType; signed out, and the session replayed
  answered 404.
- As Gastroenterology's review-agent: signed in to /; every console page 404; the workspace page and the encounter page
  the operator read, by their real ids, 404; that encounter's stored original 404 (graded hard: the encounter page links
  it); the console's own acts posted with ids that name nothing, 404; signed out.
- No act was posted on live; no password was printed or written. The evidence is in
  `act/live-check-20261123T053812Z/console-evidence.json` (0600).

## For the owner

- Sign in at https://cpt.quillmd.com/login/ as **platform-operator** (its password is in
  `/etc/cpt-studio/operator-credentials.json`, root-only, from the operators phase of 2026-11-05). /ops/ opens the console
  in the new design: Encounters, People, Workspaces, Spending and Activity.
- People: add a person to one workspace (the one-time password is shown once, on the page that answers the add: copy it
  then), reset a password, change a role, turn access off and on. Workspaces: create one for an existing specialty.
  Spending and Activity are read-only.
- Written limits: a workspace name made in the console uses the Western European Latin letters, digits and a few marks
  (other scripts are refused; provisioning can still make such a workspace); nothing is deleted from the console; operator
  accounts stay server-only; a server provisioning run puts its own workspace owner back to Owner.
- admin.quillmd.com comes later, in a release of its own with the QuillMD checks that expect a notice there.

## Measured before the act (in the declaration)

The full gate on the revision's tree (Django 702, ops 538, verification 37, walk 97, pip-audit clean); seven refutation
rounds of the change (22, 9, 10, 7, 3, 8 and 3 findings; no high; all 62 repaired and pinned by a test, or written down
as a limit); the install rehearsal on a restored copy of live with the final package (the console check without acts,
its footprint measured over every table's exact row count; then every act; then the switch-back); two read-only review
rounds of the release package (13 then 3 findings, no high), every finding repaired and self-tested.

## Rollback

The previous image (3ce5383ce485, sha256:9486d0bfd111...) is kept. The incident path is the installer's `switch-back` (a
fresh preflight, then act_a.sh switch-back with SWITCH_BACK_DECISION recorded), which recreates the previous pair from that
image; rehearsed on the copy after the acts, it closed no stage and changed no state. Rows the new console writes
(accounts, memberships, workspaces, audit events) are plain rows the previous revision reads.

## Notes for the next release

- The package review again found what the change's refutation could not: a declared baseline file whose mode the pre-app
  gate would have refused between image and app, and an app arm that never read how the newest preflight ended. The
  repaired tools (declare_baseline_a.sh, act_a.sh's app arm, post_check_a.sh's DECL_FILE guard, console_check_a.py's
  framed pages and real-id probes, reh_a.sh's every-table footprint, fill_decl.py's one-pass fill) are the better
  starting point for the next act.
- The old web's drain bound (130.6 s) is most of the app phase's time, as before.
