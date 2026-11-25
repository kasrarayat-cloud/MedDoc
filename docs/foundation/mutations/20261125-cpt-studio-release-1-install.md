# Prospective declaration: CPT Studio release 1 (6ab8e503a400 to 816045c72644), the security and HIPAA code items, installed blue/green with the site kept online: the front door republished in place, the database's swap and statement logging set without a restart, the sealed Word converter, migrations 0017 and 0018, every session ended once at the switch, then ops-agent's operator grant revoked and the platform operator's setup code issued

<!-- Drafted 2026-11-25 by a read-only drafting agent from cpt-studio/ops/install.py and ops/INSTALL.md at aacf52b569db,
the release package and the rehearsal's record; brought to the revision by the lead (session 738699b2) after refutation
rounds 3 and 4 and the decisions D409-D419, and corrected after the package's review (D420). The comments name the functions each claim was read from, for checking. -->

HIPAA impact: none: synthetic-only unchanged

<!-- RELEASE-1-SPEC 6.1 (document 03, 03.8.3; register O06): the line, verbatim. The "ePHI security evaluation" the same
paragraph requires (register A28) is its own section below, before the stop conditions. -->

Authority: the owner's directions of 2026-11-23 and 2026-11-24 recorded verbatim, with this programme's interpretation,
in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its D399-D415, D417 and D418 sections, landed with PR #1525; its
D419, D420, D421 and D422 sections and the correction of D412's weekday, with this declaration's PRs, #1527 and the one that
amends it) and RULINGS.md rows; the build
specification is /home/claude/cpt-studio-hipaa-20261124/RELEASE-1-SPEC.md (outside the repository; its section 6 is this
install):

- D399: "ive seen in Gi when i open the doc tabs it open slow and al ittle bit laggy my question is let say we get 1000
  customer to use our web site despite of vps is our websitre and admin secure enought against the attacks or any
  hidding login to intruopt us and also what if 1000 customer uplaod more than 50 per day it would be 50000 fiels per day
  i want you to audit and check every aspect of this situation i wanna make sure my site is secure and fast to use this
  is high proirty for me and remove new custoemr design and orothopedic test casue i will take of it alter or i let you
  know later not improtant". Interpretation (a): a report-only audit of cpt.quillmd.com and admin.quillmd.com for
  security (hidden logins included), the GI document tabs' speed, and the load of 1,000 customers at 50 uploads a day;
  nothing fixed without the owner's go; (b): the doctor-app restyle and the Orthopedic Surgery acceptance test are
  removed from the priorities until the owner says otherwise.
- D400: "PErfect ok for back alrtet and other thigns liek for releasing i will switch to the another better vps so we
  can choose backup over there but after all of this report which one of this we can fix adn take care veen if we want
  to move for another vps so we wouldnt feel heache and gap security". Interpretation: backups, alerting and the host's
  own hardening (SSH, firewall, its own disk, no co-tenants) are set up on the new server; the code and installer fixes
  travel with the release and are worth doing now.
- The HIPAA job, 2026-11-24: "ok thats a perfect side also before we strating the jobs i want to also u downlaod the
  Hippa plugins anything that we need for hippa and we have to make sure our website is Hippa as well what do you say for
  that i kinda want to add hippa job too". Interpretation: a HIPAA gap check of CPT Studio before the releases, its code
  items built into release 1 with the security fixes; the policy and contract items drafted as paperwork for the owner or
  an advisor. CPT Studio stays synthetic-only until the BAA question is closed and release 1b's items (F1's wiring, A10,
  A12, D5, E4) are installed.
- D401: "i already conatcting with claude for baa so strat the work waht very you needrun as much as any parrlerl or job
  you need" and, the same day, "make sure site is online dont turn if the live". Interpretation (a): the plan the owner
  approved runs - the HIPAA gap check, then release 1 (the security fixes and the HIPAA code items) built in parallel
  lanes in worktrees and through every gate, then the GI speed release, then growth, then the new server, then the
  paperwork; (b): the live site stays online throughout: every install is blue/green through the ruled-act door, the
  standby switch, never a stop; (c): the BAA with Anthropic is the owner's own contact; no agreement, key or payment is
  made by any session.
- The build's record (D402-D408: the session's decisions, recorded, not the owner's): Lane 1 (#1522), Lane 5 (#1523) and
  Lane 4 (#1524) merged on their own; Lanes 2, 3 and 6 as one integration branch (PR #1525), their halves landing
  together. D407: the Word inflation-ratio refusal removed (crafted XML ends in the converter's own out-of-memory kill,
  other documents unaffected); a switch-back to a revision without disposal refused while a practice is closed or a
  document destroyed (the first closure or destruction ends the way back to every revision before release 1: an
  accepted-capability loss the owner takes with the first disposal he orders - none is ordered by this act); 20 live
  sessions per account per kind; 10 password checks per account per 15 minutes on /account/. D408: the session cap never
  ends a pending sign-in that can still complete; a signed-in session's link names its door; every change to one
  account's sessions takes that account's row lock first; one ledger limit; no row-changing disposal step while a
  revision without disposal serves; rollback-app back to a revision without the session policy ends every session; the
  stop signal never raised between a destroying transaction's commit and its recorded outcome. Recorded, not repaired,
  each low: failclosed-9, rollback-4, rollback-5, coding-0, coding-1, phi-2, secondfactor-0, -2 and -3. D409: this
  install takes no copy of live (below). D410, D414-D416: refutation rounds 3 and 4 and their repairs (below).
- The owner's answers for this act (D411-D413, D417, D419 and D422): the security official is Kasra Rayat (D411; what he
  accepted is D417's eight items and D419's five points, each named under "The residual risk" below, and E2's Word
  refusals and removal only as the owner decisions below record his answer); the two manage
  acts are signed BY "Kasra Rayat" (--by) and run by session 738699b2; the window is Wednesday 2026-11-25, 11:00
  AM-12:00 PM Pacific (19:00-20:00 UTC), the hour the act starts in: the session's
  reading of his "tommarrow mortning is perfect ... liek around 11 or 12am pacefic time" ("12am" read as noon; put to
  him in the session at 2026-11-25T02:42:46Z and not corrected; his D422 direction, in reply to messages that named
  11:00 AM Pacific, is read as the confirmation D412 left open; D412's record and one of the session's messages called that day Tuesday, a slip he was told of in the
  message D419 answers, its correction appended to DECISIONS.md and to the rulings file); the operator's second factor
  is a passkey on the owner's computer (D3 changed), the ten recovery codes its backup; no session reads, shows or
  prints the setup code - the owner reads it himself on the server; and D419 is his "yes", at 2026-11-25 15:27:28Z, to
  five points the session put to him: (1) the install folder's 23 earlier full copies of the live database, (2) no copy
  of live taken before this install, so none to restore if data itself were lost, (3) D10's loss, (4) the Word limits
  and (5) D22, each below; and D422 is his direction, at 2026-11-25 17:30:15Z, in reply to the question on E2's two Word
  losses: "Stop asking my Yes just do what ever we need it to have to do" - read as yes to both, and as the direction to run
  this act at its hour without waiting for a further word from him; it is not read as permission to delete data, to spend
  or agree anything, or to make or hand out a key. This declaration, first committed as 2e71431b568c, is amended by it
  before any phase: what waited for his word no longer does, but his own enrolment and, were one ever found, the removal of a stored
  file (class d; the stop conditions).

The owner decisions of RELEASE-1-SPEC section 8 stand at their recommended answers until the owner rules, but for what is
put off: D22's act (below) and, to release 1b, D16's wiring (F1) and D29's workflow (A12) (cptstudio/settings.py says so
of every policy value). Of the four classes that reach the owner, this act
touches these. Answered by him: D30 (a: the window, announced to the practices: Wednesday 2026-11-25, 11:00 AM-12:00 PM
Pacific (19:00-20:00 UTC), as read from the owner's answer D412; the service is synthetic-only, so the owner is the one
person told, and he was asked not to use CPT Studio or the console from 10:00 AM Pacific until told it is finished,
D419); D3 (d: the operator's authenticator, a passkey on the owner's computer (D412), with the ten recovery codes its
backup and a second passkey recommended); D10 (b, an accepted-capability loss, D419 (3): from S3, whatever grant it
holds, no automated account opens the console, so the live check proves the console's gate, not an operator's page; the
automated suite covers the page and the owner opens one by hand after enrolling); the Word limits of E1 (b, an
accepted-capability loss, D419 (4): the D358 line below; part of the Word conversion limits the owner approved as a
group: audit Tier 1 item 11, in the list the session gave him on D400's question (then "awaiting his go"), and his go,
D401; RELEASE-1-SPEC section 9 item 15, the cap against the synthetic acceptance set,
was not confirmed - that set stays sealed; E2's refusals and the imported document it takes out (w:altChunk), in the same
line, also class b, are not among D419's points: put to him in the session at 2026-11-25T16:15:09Z, each in plain words (a file damaged inside or built in a way Word does not
produce, refused; a document inserted whole into a Word file, left out of the PDF with no notice), with the session's
recommendation (yes for this install, no real customer; such a file refused with a message in the next release), and
answered at 2026-11-25T17:30:15Z with "Stop asking my Yes just do what ever we need it to have to do": read as yes to both, an accepted-capability loss (D422)). Not decided by
the owner in words: D1 (a: the idle limits), the session's recommended answer, shown to him on 2026-11-24 and not ruled
(D402's list); D15 (a: owners alone see their team), D20 (a: the recovery codes kept by him, as D411's record reads his
naming as the security official and as he was told on 2026-11-25, D417 (7); the reset from the server is
ops/INSTALL.md's Emergency access, and a second human operator is added when a second person joins) and, of no class,
D27 (TLS findings recorded, never an undo), recommended answers of RELEASE-1-SPEC section 8 put to him for a ruling in no
list (none of the three is in D402's; of the specification he was given the file's name alone, on 2026-11-24, as the build
plan); and D21's second half
(b, carried as A8: this revision's switch-back refuses Corti, Astra, the earlier Fable participant and the earlier
interpreter live; app already took none of them; put to him on 2026-11-24, no answer recorded
(ops/INSTALL.md's Known limits and install.py call it "an accepted capability loss": no acceptance is on record), and his
directions D351,
D352 and D358 had already dropped those engines; judged no capability lost: the one pair it returns to, 6ab8e503a400's,
reads none of those modes, and an older revision's own installer is unchanged). In force at its recommended answer, for
counsel: D25's retention (the daily maintenance deletes sign-in rows older than 2,192 days, studio/maintenance.py;
access and audit rows are kept). The one deletion of stored documents this act can make is the first maintenance run's
removal of files no row names (class d; the specification's item D3, not the owner's decision D3): declared below as
none, any other count is PRE-APP STOP, and the owner is asked before any stored file is removed. The record of his
answers: docs/foundation/rulings/2026-10-23-cpt-studio-gi.md and RULINGS.md's rows of 2026-11-25 - D3 (the passkey,
D412) and D30 in its D411-D413 sections, D10 and the Word limits in its D419 section. Not taken by this act: D11, D12
and D21's first half (deleting ops-agent's login file, today's operator password file and the earlier vendors' key
copies: deletions, the owner's), the 23 earlier copies of the live database in /home/claude/cpt-studio-install-20261023
(pre-app-*.dump, 0600, not encrypted, 9 of them made after 2026-11-20 00:20Z, so they may hold that day's documents:
untouched by this act, and he decides about them with counsel: class d, D419 (1)), D22 (flagging every human account for
a password change: recommended yes, right after the install (the specification's 6.1, step 12), and put to the owner as
yes on 2026-11-24; a separate step, under its own declaration, when he says: D419 (5)), D14 and D25's destruction half
(disposal, with counsel), D18 (the malware scan, release 1b).

It stands on the standing directions this install keeps:
- D358: no coding instruction, model, effort, figure, decision rule or list-state rule changes: studio/fable/ but
  document.py (and the new docx_package.py), studio/decisions.py, studio/state.py and the physician report's code are
  byte-identical (below). The one change to a coding request is D358 (a)'s file safety: the request sent for a document
  both revisions take is unchanged but for the Word cleaning. What changes on the coding path (studio/jobs.py,
  intake.py, storage.py, fable/document.py and the new docx_package.py; plumbing and file safety only, D358 (a)),
  reviewed by the coding-path lens (RELEASE-1-SPEC 2.4): (1) a Word file becomes the PDF the coder is sent inside the
  sealed converter (E3), its package cleaned first (E2: field codes that read other files and embedded objects
    neutralised, and a document imported through w:altChunk taken out with its text, which 6ab8e503a400 leaves in the
  package; what LibreOffice 7.4 shows of one was not measured), and a Word file that converts today is refused
  ("The Word file could not be opened.") when a part
  inflates over 32 MiB or the package over 64 MiB (E1, the class-b loss of D419 (4); 6ab8e503a400: 512 MiB in all, no
  limit per part), or a part is not the size its zip header says (E1, not among D419's points; put to him with E2's as a file damaged inside,
  D421 and D422), when a part other than an
  SVG picture declares a DTD, when a part holding field or object markup is not well-formed XML, when a field to be
  removed is not closed, or when what is to be removed declares namespaces of its own or lies in a part that is not UTF-8
  or that cannot be edited safely (E2); a converter that is down
  or full, or package checks past 10 s, fail the round busy; on the image's LibreOffice 7.4 every field shape for which
  the cleaning keeps the earlier package renders identically, and the one difference is a live INCLUDETEXT the cleaning
  neutralises, in a field whose PAGE a tracked change deleted: 7.4 read the deleted PAGE (the page number) in the
  earlier package and shows the field's stored result now; 7.4 read the named file in no shape, before the cleaning or
  after it (lead/rehearsal/RESULT.md, the C5 table, shape J: the safe direction); and jobs.py changes for every
  document, PDF, text and paste included, with no request changed: (2) before each token count the worker writes the
  audit event provider.counting (system; a name the baseline does not hold; two in an ordinary round), and when that row
  cannot be written that request is neither counted nor sent and the round fails 'failed' (the specification's item D4);
  (3) an original or a stored conversion is read only from the practice's own folder (storage.read_own_original): an
  original named elsewhere fails the round 'storage' with nothing counted or sent, a stored conversion is made again;
  (4) a closed practice takes no upload (intake.py) and starts, resumes or claims no coding (its queued job is
  cancelled), and a destroyed document starts none (the specification's item D1; this act closes and destroys nothing).
  <!-- verified: git diff --quiet 6ab8e503a400 5a372f5b9a29 on those paths exits 0 (the byte-identity command below; 47
  files). jobs.py: _code, _worst_case, _stored_conversion, _keep_view, start_round, resume, claim_next; intake._create;
  storage.read_own_original, in_practice_folder; document.convert_docx; docx_package: MAX_PART_BYTES, MAX_PACKAGE_BYTES,
  PACKAGE_SECONDS, _check_sizes, _remove_active_content -->
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved):
  QuillMD's vhost is not written by this release (it stays the pinned after state); quillmd-cpt is replaced in place
  twice, each with one graceful, host-global reload (https-vhost, then app's S3); every http-level name the new stage
  adds to the shared nginx is cpt_*; every QuillMD host keeps its answer and its certificate.
  <!-- install.py: phase_https_vhost, switch_upstream, publish_vhost; deploy/nginx/cpt-quillmd-https.conf -->
- D396 and its coupling invariant: every HTTPS stage of this revision names admin.quillmd.com on 443, so the quillmd
  vhost stays b3ab66023547... and admin.quillmd.com stays the console's.
  <!-- install.py: QUILLMD_VHOST_AFTER, read_coupling, coupling_problem (phase_https_vhost expects 'after') -->
- D360's install conditions: no unresolved critical or high finding; every suite green; CI green on the merged commit;
  this declaration committed before the act; the rehearsal on a restored copy of live passed (not met as recorded by the
  revision's own image: changed for this act by the lead's decision D409, recorded, not the owner's); preflight not
  BLOCK; the act only through the door; a check on the live site afterwards; a report either way. The rehearsal on a
  restored copy of live ran on 2026-11-24 on earlier heads (0017 applied on real rows; below); under D409 (the lead's
  decision, on the HIPAA plan's NEW-VPS 0.2: no copy of live before the 2026-11-20 documents are decided with counsel)
  the revision's own image is rehearsed on synthetic data only, and this act makes no copy of live, its own choice under
  D409 and D419 (2): its check before app reads live read-only.
- D401 (b) and (c): no phase stops the site (the database is updated in place, both nginx changes are graceful reloads,
  app is the blue/green switch), and no session makes an agreement, key or payment.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only
(`SYNTHETIC_ONLY = True` unchanged). No purchase, agreement, key or payment change is part of this act, and no paid
request is made by it: no phase sends anything to a vendor (every one-shot runs with the coder disabled; there is no
access check), and the cert phase orders nothing (the lineage is not due). No account or workspace is created, and no
password is set by the install. Two ruled acts change account state: ops-agent's operator grant is revoked, and the
platform operator is issued a single-use setup code with which the owner himself sets its password and enrols its keys.
<!-- install.py: oneshot (provider calls disabled), runtime_env, phase_manage, issue_setup_code -->

Revision to install: `816045c7264481bc6956285e1ca89991b9fcec2f`, the merge commit of PR #1525 (head `5a372f5b9a2920ef9d4f347ec3e1eed1c4476cdc`; its
tree equals the head's: `git diff --quiet 5a372f5b9a2920ef9d4f347ec3e1eed1c4476cdc 816045c7264481bc6956285e1ca89991b9fcec2f` exits 0; its first
parent, dbab85967dcecb9574e565cd2dcfd5e342bfb1a5, is the merge commit of #1524 itself: main had not moved since, so nothing under cpt-studio/ or
scripts/ changed between). Image tag cpt-studio:`816045c72644`.
Its citation, on the revision: `CI 45579306932, cpt-studio 45579306910 and secrets-scan 45579306882, all success, read by commit and by branch at 2026-11-25T15:37Z`. The PR head's citation: `CI 45575888268, cpt-studio 45575888421 and secrets-scan 45575889813, all success, read by commit and by branch at 2026-11-25T15:37Z`. An earlier head,
18749c4af201, failed the cpt-studio workflow: its CI gate required by name a browser-walk test release 1 had renamed;
5a372f5b9a29 changes scripts/ci/verify-cpt-studio.sh only. cpt-studio is not a required check; it is required here.

It replaces the live revision 6ab8e503a40050c08c01c965441fa56583fb5e03 (image cpt-studio:6ab8e503a400, id
sha256:6ee79ec888ac27e9bf6f9508508bd1bd2b0f0acac185259e4448d0ed2ed27d6c, its web on 127.0.0.1:9151 since release 2's switch on 2026-11-23), installed under
docs/foundation/mutations/20261123-cpt-studio-admin-host-ingress-install.md (PR #1519, 258700a8a; its report PR #1520).
That image is kept as the rollback image (switch-back). That declaration and its receipts stay as they are.
<!-- release 2's report (docs/deploy-reports/20261123-cpt-studio-6ab8e503-ingress-install-and-live-check.md): image
cpt-studio:6ab8e503a400 = sha256:6ee79ec888ac...; app 9150 to 9151; switch.vhost_sha_after 1672b98db8cf... -->

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000` (act_r1.sh sets it
when the variable is not set and passes on any other value; each log's "door watchdog ceiling" line must read 9000), as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 816045c7264481bc6956285e1ca89991b9fcec2f --receipts /home/claude/cpt-studio-install-20261023`
plus each phase's fixed arguments (cpt-r1-20261124/release/act_r1.sh: release 2's act_i.sh, reviewed in three rounds and
used for its install, with this release's names, phases and order, and its rules for the two manage acts, a reissue of the
setup code and the declaration's placeholders; sha256 300a253629cab966).

Phases, in this order:
1. preflight;
2. image;
3. db;
4. converter;
5. cert;
6. https-vhost;
7. preflight again (TAG after-https-vhost): the baseline app and verify compare against, taken after the republish;
   then, not a phase, pre_app_r1.sh (read-only on the live database), its log ending PRE-APP PASS;
8. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes the
   live pair runs with;
9. passages;
10. license-note;
11. verify;
12. manage, act_r1.sh's revoke-ops-agent: `--command revoke-operator --username ops-agent --reason-file /home/claude/cpt-r1-20261124/release/reasons/revoke-ops-agent.txt --by "Kasra Rayat"`;
13. manage, act_r1.sh's issue-enrolment: `--command issue-enrolment --username platform-operator --reason-file /home/claude/cpt-r1-20261124/release/reasons/issue-enrolment.txt --by "Kasra Rayat"`.

Then, not phases and in this order: the live check (live_check_r1.py), post_check_r1.sh once, and the owner's own
enrolment on admin.quillmd.com inside the setup code's 30 minutes (below). When he is not there, item 13 waits for him, and
the live check and a first post-check run before it, and post_check_r1.sh again after it (the stop conditions say how each is
judged).
<!-- act_r1.sh: its case statement (ARGS per phase; INSTALLER_PHASE=manage for the two acts); post_check_r1.sh's header
("after app, verify, the two manage acts and the live check") -->

act_r1.sh refuses: a REV other than this declaration's "Revision to install"; a DECL other than
docs/foundation/mutations/<date>-cpt-studio-release-1-install.md and an ACT that does not begin with
/opt/meddoc-pro/.worktrees/cpt-r1-act- and a digit (the act's own path, below, is the operator's to name); any installer
argument on its own command line; a checkout with a tracked file modified or staged (untracked files are not looked at:
the operator's own check below) or not detached, a REV that is not HEAD or its ancestor, any change under cpt-studio/,
scripts/run-ruled-mutation.sh, scripts/lib or scripts/check-cotenants.sh between REV and HEAD, and a declaration that is
not tracked or differs from its commit; a phase run twice under one log; a second run of a changing phase, unless the
first's failure is proven twice - its log's last line records the door's non-zero exit, and exactly one receipt of that
phase and revision written inside that run says ok false - and RERUN_DECISION records the decision in words (then only
after a preflight newer than the failed run, whose log is kept as act-r1-<phase>.attempt-<n>.log; a phase that ended exit
0, or whose end is unknown, never runs again through it, but for issue-enrolment's reissue, below); TAG on a changing
phase; image without a newest preflight that ended exit 0; db without the image log ending exit 0, converter without
db's, cert without converter's, https-vhost without cert's; app without PRE_APP_LOG (pre_app_r1.sh's newest log for this
revision, ending PRE-APP PASS), without image, db, converter, cert and https-vhost logs ending exit 0, without a
preflight newer than https-vhost that is the newest and ended exit 0, or with the pre-app log older than that preflight;
app after a switch-back that ended exit 0 (a new install is a new declaration); passages and verify before app,
license-note before passages; revoke-ops-agent before license-note, issue-enrolment before revoke-ops-agent, and either unless the newest verify log is newer than license-note's and than any
switch-back that did not end exit 0, and itself ended exit 0, or after a switch-back that ended exit 0; a
manage act whose REASON_FILE is not a 0600 regular file named by a path that begins with
/home/claude/cpt-r1-20261124/release/reasons/ and ends .txt (read as written: a '..' in it is not resolved), holding a
reason in words (12 or more characters that are not space, three words or more), or whose BY is not in the form of a name
(two words or more, each starting with a capital letter; a form only: a capitalised role such as 'Security Officer'
passes it and the installer's own list of roles, and is refused, nothing recorded in the database, by the application's
command) - the two acts' REASON_FILE and BY are those of phases 12 and 13, "Kasra Rayat" for both, and anything else is a
stop before the act; switch-back without SWITCH_BACK_DECISION in words and a preflight that ended exit 0 newer than every
app, passages, license-note, manage (a reissue's included) and switch-back log.
<!-- act_r1.sh: refuse(), words(), NAME_RE, the REISSUE block, the RERUN block (FAILED_RECEIPT python),
newest_preflight(), after(), newest_ok(), verified(), the case "$PHASE" order block, the checkout checks before the door
call -->

The installer gives the web and the worker the same coder settings as the live pair: the revision's settings.py
defaults, unchanged by this release (effort max, the 25 US dollar per-document ceiling, 4 documents at once).
<!-- install.py: runtime_env, CODING_EFFORT, coding_figures; the settings.py diff touches neither figure -->

Run them from a clean, detached checkout of the merge commit that lands this declaration as amended (the amending PR's, not #1527's c8c8ed3d9ad3)
(/opt/meddoc-pro/.worktrees/cpt-r1-act-20261125). That commit must be a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh, scripts/lib/ or scripts/check-cotenants.sh. Read each receipt
before the next phase.

Not run: secrets, reference, provision, operators, http-vhost, ingress, ingress-rollback and rollback-vhost, and every
manage command but the two above (grant-operator, reset-second-factor, clear-signin-failures, require-password-change -
so D22 is not applied - dispose and export-workspace). switch-back is the incident path after a successful app, and
rollback-app the one after an app that stopped half way (below), each only by a decision recorded in words under this
declaration. act_r1.sh refuses rollback-app, so it is run by hand from the act checkout:
`RULED_ACT_MAX_SECS=9000 bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20261125-cpt-studio-release-1-install.md -- python3 -B cpt-studio/ops/install.py --phase rollback-app --revision 816045c7264481bc6956285e1ca89991b9fcec2f --receipts /home/claude/cpt-studio-install-20261023`,
its output kept as /home/claude/cpt-r1-20261124/release/act/act-r1-rollback-app.log. No document is sent by the install.

Between 6ab8e503a40050c08c01c965441fa56583fb5e03 and the revision, these are byte-identical (`git diff --quiet` with the
pathspecs below: exit 0 at the PR head 5a372f5b9a29, 2026-11-25, 47 files; at the revision: exit 0, 47 files, 2026-11-25):
the coder's prompts, client, answer reading, pricing and credentials loader (studio/fable/ but document.py and the new
docx_package.py), studio/decisions.py (the approval rules), studio/state.py (the list states), the physician report
(physician_report.py, physician_pdf.py and every file of report_fonts/), the reference data (studio/reference/),
migrations 0001 to 0016, the Dockerfile and its .dockerignore, and the HTTP stage (deploy/nginx/cpt-quillmd-http.conf:
the :80 block every renewal reads). Positive control for the byte-identity command: the same `git diff --quiet` on
cpt-studio/studio/fable/document.py exits 1.

These change (at the PR head 5a372f5b9a29: 166 files under cpt-studio/, 71 added and 95 modified, 44,608 insertions and
1,757 deletions; at the revision: the same 166 files, 44,608 insertions and 1,757 deletions): the application (studio/: the sign-in throttle, the session policy and
store, the second factor and its views, the read records, security events, rate windows, disposal and record bundles,
the daily maintenance, file encryption built off, the console, the API and the customer views, storage and intake, the
coding stage (jobs.py: the count record, own-folder reads and closed-practice refusals above, and the maintenance tick),
document.py's converter client, the Word package cleaner and the converter server), the settings and the two urlconfs,
the migrations 0017_r1_security and 0018_r1_availability, the templates and static files (five new templates, two new
scripts), eight new management commands (clear_signin_failures, dispose, export_workspace, issue_enrolment,
require_password_change, reset_second_factor, sweep_orphan_files, verify_originals) and three changed (grant_operator,
provision, revoke_operator), deploy/entrypoint.sh (the converter role), deploy/gunicorn.conf.py (the access line's request
id and session reference), the HTTPS template, the requirements (webauthn 3.0.1, cryptography 50.0.1, cbor2 6.2.1,
pyasn1 0.6.5, pyasn1_modules 0.4.2, pyOpenSSL 26.4.0), the installer and its tests, the verification tools (verify_login.py,
scan_customer.py and walk.cjs speak release 1's client version), and the docs (API.md, ARCHITECTURE.md, CORE-UX-DESIGN.md,
ops/INSTALL.md). Outside cpt-studio/: scripts/check-cotenants.sh (#1521: admin.quillmd.com's row narrowed to the console's
302 to /login/); scripts/ci/verify-cpt-studio.sh (#1525, 5a372f5b9a29: the walk tests the CI gate requires by name, the
operator-gate test's old name, which said "and the operator reads the encounter", replaced by its two release-1 names -
A11, D10; run by CI alone, by no phase and in no image); release 2's declaration and report (#1519, #1520); and #1525's
docs-only commits (docs/foundation/RULINGS.md and docs/foundation/rulings/2026-10-23-cpt-studio-gi.md: the D399-D415, D417
and D418 directions, answers and records).
<!-- git diff --stat / --name-status 6ab8e503a400..5a372f5b9a29 -->

Before preflight the health check is run, report-only (its stop condition, below), and the operator runs, in the act's
checkout:
- `git status --porcelain --untracked-files=all --ignored -- cpt-studio scripts`, printing nothing (act_r1.sh and the
  installer look at tracked files only, and a module beside install.py would be imported in place of the standard
  library's), and `echo "${RULED_ACT_MAX_SECS:-unset}"`, printing unset or 9000;
- `git diff --quiet 6ab8e503a40050c08c01c965441fa56583fb5e03 HEAD -- cpt-studio/studio/fable ':(exclude)cpt-studio/studio/fable/document.py' ':(exclude)cpt-studio/studio/fable/docx_package.py' cpt-studio/studio/decisions.py cpt-studio/studio/state.py cpt-studio/studio/physician_report.py cpt-studio/studio/physician_pdf.py cpt-studio/studio/report_fonts cpt-studio/studio/reference cpt-studio/deploy/Dockerfile cpt-studio/deploy/.dockerignore cpt-studio/deploy/nginx/cpt-quillmd-http.conf ':(glob)cpt-studio/studio/migrations/000[1-9]_*.py' ':(glob)cpt-studio/studio/migrations/001[0-6]_*.py'`, exit 0;
- `git diff --name-only 6ab8e503a40050c08c01c965441fa56583fb5e03 HEAD -- cpt-studio/studio/migrations`, printing exactly
  cpt-studio/studio/migrations/0017_r1_security.py and cpt-studio/studio/migrations/0018_r1_availability.py;
- `git diff --name-only 816045c7264481bc6956285e1ca89991b9fcec2f HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib scripts/check-cotenants.sh`,
  printing nothing;
- the revision's HTTPS stage rendered for each port as the installer renders it (`git show 816045c7264481bc6956285e1ca89991b9fcec2f:cpt-studio/deploy/nginx/cpt-quillmd-https.conf`,
  @@DOMAIN@@ cpt.quillmd.com and @@UPSTREAM@@ 127.0.0.1:<port>, sha256 of the result): 9150 `e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792`, 9151
  `bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9`;
  <!-- install.py: rendered_vhosts, render, upstream. Positive control of that rendering: 6ab8e503a400's template gives
  d0e4fc5ca1cc... (9150) and 1672b98db8cf... (9151), exactly the two stages release 2 declared. The template is unchanged since aacf52b569db (`git diff --quiet aacf52b569db
  816045c7264481bc6956285e1ca89991b9fcec2f -- cpt-studio/deploy/nginx` exits 0, checked again at the merge commit), and the installer's own rendered_vhosts
  gives these two values at 5a372f5b9a29. -->
- `grep -nE '[{][{][A-Z][A-Z0-9_]*[}][}]' docs/foundation/mutations/20261125-cpt-studio-release-1-install.md`,
  printing nothing: no placeholder of this draft is left (act_r1.sh refuses the same: an upper-case name in double braces, or half of one, or a less-than sign written directly
  before one of its upper-case names, or a guillemet; Docker's own format strings such as '{{.Names}}' are not placeholders);
- `docker ps --filter label=org.quillmd.cpt-r1=1 --format '{{.Names}} {{.Status}}'`, printing no running container
  (pre_app_r1.sh refuses one named cpt-r1-rh-*; preflight refuses any task of uid 10150 or 10151 outside CPT Studio and
  verify any of uid 10150 alone: the rehearsal's web, worker and converter run as those uids, so the rehearsal is
  stopped first); the harness's internal network cpt-r1-ngx-net may stay (no container on it; removing a network is the
  owner's);
  <!-- install.py: foreign_uid_tasks is called by phase_preflight (APP_UID and CONVERTER_UID) and phase_verify (APP_UID)
  only -->
- at once before preflight,
  `diff <(grep -vE '^(read_at|last_audit|login_attempts|sessions) ' /home/claude/cpt-r1-20261124/release/declared-baseline-20261125.txt) <(bash /home/claude/cpt-r1-20261124/release/baseline_r1.sh | grep -vE '^(read_at|last_audit|login_attempts|sessions) ')`,
  printing nothing, exit 0 (read-only; read_at, the last audit, the sign-in count and the session count aside): live
  still reads as the Baseline block. A difference stops the act before any phase; pre_app_r1.sh makes this comparison
  again only after db, converter, cert and https-vhost, and nothing passes it by under this committed declaration.
- then `bash /home/claude/cpt-r1-20261124/lead/measure/measure_pre_counts.sh` (read-only, the same step pre_app_r1.sh makes),
  whose last line must read the declared orphan, unexpected, missing and past-retention counts (below; with a file no row
  names under an hour old it prints no such line and exits 7); the rows to hash beside them are read, not gated (a name may
  pass 30 days). A difference in those four, or that exit, stops the act before any phase.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; cpt-r1-20261124/release/held_check_r1.sh
with this range): run on 2026-11-25T15:35Z on 6ab8e503a400..816045c72644 (cpt-r1-20261124/release/held_check_r1.sh): 82 runtime files, 80 of them
under cpt-studio/; positive control, deploy-prod.sh named by 69 files; 46 declarations and reports name one of the files; the 26
declarations and 11 reports that name full revisions name only ancestors of the running revision; nine declarations
(2026-09-11 to 2026-09-18) name no full revision and were read: each names scripts/check-cotenants.sh alone, as the check they
ran; none is held. The range's first-parent merges on main: #1519 (release 2's declaration), #1520 (its
report), #1521 (the co-tenant check narrowed), #1522 (Lane 1), #1523 (Lane 5), #1524 (Lane 4) and #1525.

## Delta shipped (6ab8e503a400 to the revision)

**This is a TREE, not one change**: the range carries release 2's two documents, QuillMD's narrowed co-tenant check and
release 1's four merges. Its runtime changes are release 1's and the co-tenant check:

- **The front door** (deploy/nginx/cpt-quillmd-https.conf; A1-A4, B6). The HTTPS stage keeps one server block for both
  hosts, its 444 guard for any other Host and its 421 guard for any other TLS name, and gains: http-level definitions
  named cpt_* only (a geo exempting 127.0.0.1, ::1 and 147.189.172.8; maps keying a client by its IPv4 address or IPv6
  /64, by $uri and never the query string; five limit_req zones and six limit_conn zones; the cpt_studio log format);
  411 for a chunked body or a POST, PUT or PATCH with no length; TLSv1.2 and 1.3 with the AES-GCM suites asked for,
  session tickets off, server_tokens off; the access log /var/log/nginx/cpt-studio-access.log (the path without its
  query string, nginx's request id, the application's X-CPT-Actor sign-in reference) and cpt-studio-error.log (warn);
  request bodies of at most 64 KiB but the upload (20m) and a review's answers (1m), refused 413 above it before any of
  it is read, and held in memory (client_body_buffer_size 20m); 15 s header and body timeouts, 60 s send; one proxied
  location holding every limit - all requests 30 r/s (burst 120), the sign-in 60 r/min (burst 40), writes 5 r/s (burst
  30), uploads 60 r/min (burst 60), report exports 6 r/min (burst 6), 40 connections, 20 downloads per client and 24 in
  all, 4 large bodies per client and 40 in all, 40 small bodies per client - answering a plain 429; 60 s upstream
  timeouts; responses held in memory (96 x 256k buffers) and never written to a temporary file
  (proxy_max_temp_file_size 0); the request id passed upstream and X-CPT-Actor hidden from the browser; HttpOnly, Secure
  and SameSite=Strict for both session cookie names (the old one and the __Host- one) and Secure, SameSite=Strict for
  every other cookie, so the stage works with the previous revision's web too.
- **The database container** (A3, A5): memory and memory + swap 512m with its own cgroup allowing no swap; a failed
  statement logged without its text or values (log_min_error_statement panic, log_error_verbosity terse).
- **The converter** (A7, E1-E3): Word files are converted by cpt-studio-converter - no network, no secret, no files
  volume, its own uid - over a socket on the cpt-studio-convert volume; the worker requires it and never converts
  in-process in production; the package is cleaned before conversion.
- **Sign-in and sessions** (B1, B4-B7; cptstudio/settings.py): a name's failed sign-ins slow it down (after 5 in 15
  minutes, 30 s doubling to 15 minutes; 10 per name and address; 50 per address) instead of locking it, a device or
  address that signed in within 90 days skipping the delay; a password staff set from this release on must be changed at
  its first sign-in and stops working after 72 hours unchanged; passwords of 15 characters at least where one is set;
  idle sign-out after 15 minutes for members and 10 for operators, a warning 2 minutes before, 8 hours at most; 20 live
  sessions per account per kind; `__Host-cptstudio_session`, `__Host-cptstudio_csrf` and `__Host-cptstudio_device` under
  HTTPS, the old `cptstudio_session` and `cptstudio_csrf` deleted from a browser on its first answer; /health/ through
  nginx answers `release_digest` (the first 16 hex of sha256 of "cpt-studio-release:" and the revision) and no release;
  the client version customer-2026-11-24.
  <!-- settings.py diff (SIGNIN_*, KNOWN_DEVICE_DAYS, STAFF_PASSWORD_UNUSED_SECONDS, PASSWORD_MIN_LENGTH, SESSION_IDLE_*,
  SESSION_MAX_*, SESSION_LIVE_PER_ACCOUNT, SESSION_COOKIE_NAME, CSRF_COOKIE_NAME); throttle.device_cookie_name;
  sessions.OLD_COOKIE_NAMES and SessionPolicyMiddleware.finish; views.health; client_contract.VERSION -->
- **The operator's console** (B2, B3, C2, C3): only on admin.quillmd.com, only for a human account holding a standing
  grant whose session passed a security key or passkey there (WebAuthn bound to admin.quillmd.com); every other request
  meets an unknown URL's 404, cpt.quillmd.com/ops/ included, but that a signed-out one on admin.quillmd.com is sent to the
  sign-in (302; 303 for anything but a GET or HEAD); a change of people, roles, passwords or access asks for the
  key again after 5 minutes; no automated account holds operator power whatever grant row it has; lists show reference
  codes, and a document's content opens for 15 minutes, in that session, with a recorded reason.
  <!-- operator.is_operator (actor_kind HUMAN), operator.may_use_console, operator.operator_view; settings WEBAUTHN_RP_ID,
  SECOND_FACTOR_STEP_UP_SECONDS, CONTENT_GRANT_SECONDS -->
- **Records** (C1, A2, A13, D4): every view and download of a document writes an AccessRecord before the answer leaves
  (none written, none served), but for the page's own poll of a document within 60 s of that sign-in's record of it, and
  for the same list read again within 60 s, which is counted on the first read's record (AccessRecordRepeat); security
  events (SecurityEvent: ids, counts and fixed words); the web's access line carries the request id and session reference; before the installer removes a container its log is kept ids only in
  /var/log/cpt-studio/containers/, and every one-shot and root-helper run is one line of
  /var/log/cpt-studio/oneshots-<date>.log (both root-only, 14 days).
  <!-- api.py 159-176 (read_audit.record, 503 when the row cannot be written); install.py keep_container_log,
  ids_only_lines, journal, flush_journal, LOG_KEEP_DAYS -->
- **Practices** (C4-C6, D1, D2; RELEASE-1-SPEC section 4, not re-read here): an owner sees the team and can turn a person
  off; report, upload and bundle limits (10 reports per member per 10 minutes and 60 per practice per hour, 30 uploads
  and 10 bundles per member per 10 minutes) answered 429 with a sentence, a repeated report returning the stored copy;
  Word documents download as their converted PDF by default; disposal and return tools, run only as ruled acts (none by
  this act).
- **The daily maintenance and the weekly check** (D3): the worker's tick removes stale conversion folders every hour and,
  once a day under an advisory lock, prunes dead session links, expired sessions and day-old rate windows, replaces
  sign-in names older than 30 days that match no account by their keyed hash, and removes the files no row names that
  are over an hour old; once a week it re-reads up to 200 stored originals and 200 converted PDFs against their sha256.
  <!-- maintenance.run_daily, verify_originals, run_due, tick; jobs.work (sweep every STALE_SWEEP_SECONDS = 60) -->
- **Off in this release**: encryption of stored files (F1: FILES_ENCRYPTION 'off') and the malware scan (D5:
  MALWARE_SCAN 'off'), both release 1b.
- **The installer** (A6, A8, A13, 6.2): the db phase's A3 and A5 parts, the converter phase and the manage phase's ruled
  acts; the migrate one-shot's 5 s lock timeout (3 more attempts); every session ended at a switch between a revision
  before release 1's session policy and one with it; the disposal refusal of any way back to a revision without
  disposal; legacy live modes (Corti, Astra, the earlier Fable participant and interpreter) refused in app and
  switch-back (no BAA); no automated account made an operator; no operator password written to a file.
- **QuillMD's co-tenant check** (#1521): admin.quillmd.com's row expects only the console's 302 to
  https://admin.quillmd.com/login/ (QuillMD's old notice is now a finding); the act checkout's copy is the one every
  phase runs.

## What the owner and members see after the install

- At the switch (S2 to S3) everyone is signed out once - every session row is deleted and the cookie names change - and
  signs in again; a page left open across the switch is sent to the sign-in page at its next read (401), and an act sent
  from it after S3 (an answer, a decision, an upload) is refused (403: the CSRF cookie's name changed; nothing recorded)
  with the page's sentence to reload; only a page still open after the same browser signed in again in another tab is
  told a new version is available, at its next read (409: its client version customer-2026-11-22 is no longer served).
  Coding pauses from S2, while the old worker finishes the document it is on, to S4; uploads are accepted and wait in
  the queue.
- Members afterwards: the sign-in slowdown, the idle sign-out and the session cap above; /account/ to change one's own
  password and sign out everywhere; the practice owner's team panel; the per-person limits; Word downloads as PDF; every
  read recorded. The doctor's coding (but for the Word cleaning, the refusals and the busy converter of the D358 line
  above, and the
  count record, own-folder reads and refusals for a closed practice or a destroyed document it names for the coding
  stage), its review, the decisions and the PDF report's code are those of today (D358, above).
- The owner, as the operator: from S3 the console is closed until he has enrolled - cpt.quillmd.com/ops/ answers 404 to
  everyone and admin.quillmd.com admits no session that has not passed a key there. After issue-enrolment he reads the
  setup code himself from /etc/cpt-studio/operator-enrolment.json over SSH (`sudo cat`; root 0600; no session reads,
  shows or prints it: D413), opens https://admin.quillmd.com/login/enrol within 30 minutes, enters the code and a new
  password twice (15 characters at least; the code works once), registers his passkey on his computer (D412), writes
  down the 10 recovery codes shown once (D20's recommended answer: kept sealed, by the security official), and lands in the console signed
  in; a second passkey on another device, added on the console's security page, is recommended. At
  cpt.quillmd.com an operator account's sign-in is refused like a wrong password (it holds no membership: B3).
  <!-- install.py issue_setup_code (the document: url https://admin.quillmd.com/login/enrol, valid_seconds 1800);
  second_factor.issue_setup_code (expires ENROLMENT_CODE_SECONDS), claim_setup_code; second_factor_views._start_enrolment
  (validate_password, set_password, end_sessions, SecurityEvent password.changed), _finish_enrolment (store_key,
  new_recovery_codes: RECOVERY_CODE_COUNT 10, SecurityEvent second_factor.enrolled, LoginAttempt signed_in, login) -->
- QuillMD's visitors: nothing changes on quillmd.com, www.quillmd.com, app.quillmd.com or pro.quillmd.com.

## Cost and time

No paid request, and no certificate order. The image build: about 10 s on this host with every layer in the build cache
(the rehearsal images of ef859c7388ba and ca1fa02f5da6, 7 s and 10 s; their requirements.txt is the revision's); the
Dockerfile is unchanged but requirements.txt is not, so without the cache the pip layer is rebuilt and fetches the pinned
versions from PyPI. Measured on this host by release 2's install (2026-11-23, its report): preflight 11 s,
cert 16 s, the preflight again 11 s, app 3 min 1 s (no job active at its pre-app check), verify 11 s. Bounded by the
code for what is
new here: db, one docker update and one configuration reload; the converter, its 20 s start period and at most 60 polls
2 s apart; https-vhost, one reload, the public checks and 16 TLS probes of at most 20 s each; app, at least the S5 drain
(130 to 600 s) plus S2's wait for the old worker's current stage (about a second when it is idle, at most 3,600 s: the
door's 9,000 s ceiling covers two such waits and a margin); each manage act, two one-shots (manage migrate --check, then
the act). The live check took 2 s on the rehearsal stack (17:33:25 to 17:33:27Z); the owner's enrolment about 10 minutes
(RELEASE-1-SPEC 6.1, step 12b, an estimate). The converter adds a container of up to 1.5 GiB of memory and two CPUs (D9).
<!-- install.py: phase_image, CONVERTER_LIMITS, CONVERTER_CPUS, wait_converter (60 x 2 s), converter_args
(--health-start-period 20s), tls_probe (timeout 20), TLS_REFUSED_PROBES (7) plus the default probe per host,
DRAIN_MIN/MAX_SECONDS, STOP_SECONDS['worker'], check_door_ceiling -->

## Measured before this declaration

**The full gate** (scripts/ci/verify-cpt-studio.sh on the revision's tree): the cpt-studio workflow on the revision, run 45579306910, success (and on the PR head, run 45575888421, success). The lead's full suite on the tree of
the round-4 repairs at 2026-11-25T06:55:35Z (lead/suite-l4/summary.txt; its cpt-studio/ equals the revision's: `git diff
--quiet 57a8a77eee5b 816045c7264481bc6956285e1ca89991b9fcec2f -- cpt-studio` exits 0): check and migrations exit 0, the Django suite 1,438 tests OK (1
skipped), ops 897 OK, verification 38 OK, the walk's node tests 59 of 59 and the app's 147 of 147, RESULT PASS. The earlier
heads' suites passed as each round's repairs landed (D402-D418): round 1's in lead/int-suite-5, round 2's in
lead/suite-int-r2a and -r2b, round 3's in lead/suite-int-r3.

**The refutation**: Lanes 2, 4, 5 and 6 refuted before their merges (refute-lane2, -lane4, -lane5, -lane6: Lane 2 four
lenses (second factor, lockout, session, bypass), 21 findings repaired; Lane 4 three rounds (8 findings, the eighth -
the audit trail a disposal keeps, D25 - answered in the certificate's own text; 6 on round 1's repairs, two high; 3 and
a ruling on round 2's, one high), every one repaired before #1524; Lane 5 two rounds (5 findings repaired, then nothing
found on the repairs) before #1523; Lane 6 three lenses (edge, installer, rollback), 17 findings repaired); then an
integrated refutation of the whole release - nine read-only lenses and a verifier per finding: 50 findings, 39 real (1
high, 11 medium, 27 low), 11 judged not defects - and five repair builders (records and second factor, Word conversion,
disposal, installer, sessions), each repair with a failing-then-passing test and mutation proofs, each branch's full
suite passing (D407); round 2, nine lenses aimed at round 1's repairs: 31 real findings, five medium, eleven caused by
round 1's repairs, one medium regression (the session cap let a password alone end the operator's own pending sign-in),
so the stopping rule (no high finding, no medium regression) was not met and four builders repaired again (D408); round
3, six lenses over the round-2 repair diff: 29 real (four medium, 15 of them regressions of round 2) and four repair
builders (D410); round 4, five lenses over the round-3 repairs (the acts lens alone after an API overload): 17 findings,
16 real, every one low (12 from four lenses, 4 from the acts lens), four distinct regressions of round 3, no high and no
medium regression, so the stopping rule held (D415, D418). The lead repaired the cheap exact ones (57a8a77e, eight
findings: three code repairs - regression-0, disposal-0 and installer-1 - each with a failing-then-passing test and a
mutation proof (D416, L4-1 to L4-3); one correction of ops/INSTALL.md, installer-2, its pin tests changed with it, no
mutation proof; four findings on real-clock tests, rows-2 to rows-5, the tests alone changed, held at one moment, no
mutation proof, checked at every boundary position of the rows lens's own harness); the rest are recorded. Those repairs
were not refuted by a further round; the full suite ran on them.

**The rehearsal** (lead/rehearsal/RESULT.md), throwaway objects only (live only read: the dump below and its database
container's limits, 15:20Z); rh.py's docker commands through the harness's guard, the others (the image builds, the
memory test of 2026-11-24, r4-rest.sh's queries and the test copies of pre_app_r1.sh, baseline_r1.sh and
post_check_r1.sh's reads) direct, naming no live object: on real components with synthetic data (2026-11-24,
14:41-14:56Z; R0 = 6ab8e503a400, R1 = the integration head then): A3's control (64 KiB posts over HTTP/1.1 and HTTP/2
and a slow 8 MiB download left two client_temp files and one proxy_temp file behind the old stage, none behind release
1's); A5's control (a failing insert's statement and values in the database log before the settings, its error line
alone after); the image's two gates; the converter sealed and healthy; release 1's stage in front of the old web
(health, list, upload 201); 0017 applied under a live R0 (73 of 73 reads 200); the forward switch, a switch-back and a
second forward, each with its health loop at 200 throughout. Re-run on the repaired head 496c69d36d9b (17:20-17:25Z):
0017 and 0018 under a live R0 (83 of 83 200); the end of every session (one SecurityEvent sessions.ended_at_install); an
R0 cookie answered 401 and deleted on R1; DISPOSAL_COUNTS {closed 0, destroyed 0} at the switch-back; the round-1
finding of a session coming back on a second forward closed end to end. On a restored copy of live (the dump of
15:15:49Z, read-only, sha256 ec70c369f57f4151, restored into a tmpfs database with every session row deleted first): 99
of 99 documents read 200 by R0, by R1 after its migration (every existing table's count unchanged but Django's own
three: django_migrations 31 to 33, django_content_type 44 to 54, auth_permission 176 to 216; 10 new tables, all empty),
by R0 again (the switch-back) and by R1 again. Not rehearsed: the operator's second factor (it needs an authenticator),
the installer's S1-S6 orchestration itself (its parts were run, not install.main), certbot and DNS, the host's nginx
build and co-tenant blocks, real stage times. On the revision (migration 0018 was amended and install.py changed after
496c69d36d9b; 51 files under cpt-studio/ differ from it, 8,625 insertions and 647 deletions:
`git diff --shortstat 496c69d36d9b 816045c7264481bc6956285e1ca89991b9fcec2f -- cpt-studio`): the rehearsal of 2026-11-25 07:05-07:52Z on
ca1fa02f5da6 (cpt-r1-test:ca1fa02f5da6; `git diff --quiet ca1fa02f5da6cca23d0aa017475da9ee4822ad51 816045c7264481bc6956285e1ca89991b9fcec2f --
cpt-studio scripts/run-ruled-mutation.sh scripts/lib scripts/check-cotenants.sh` exits 0, so the cpt-studio/ that ships
is the one rehearsed and the repository's scripts the act runs are unchanged since; with all of `scripts` it exits 1, on
scripts/ci/verify-cpt-studio.sh alone, the CI gate, which no phase runs), in the act's order, forward only (no
switch-back), on synthetic data only and no copy of live (D409): the db phase's settings and swap limit, the converter
and the republished front door in front of 6ab8e503a400's web; the read-only pre-app check PASS (a first attempt stopped
at the db phase's own declared changes, a defect of the package fixed and proved to stop at any other, the negative
controls act-5 and act-6); migrations 0017 and 0018 applied exactly under the serving web, the list loop 98 of 98 200
(25 by the end of the migration; RESULT.md's 218 and 145 also count the 120 lines of the 04:37Z run in the same log); the
end of every session (1, one SecurityEvent); the switch, the health loop 63 of 63 200 when read (RESULT.md's 213 also
counts that run's 150); the first maintenance run exactly as the pre-app check predicted (1 orphan removed, no name hashed, no
sign-in row past retention); the live check 25 of 25 (07:51:41Z, its second start; the first, 07:50:57Z, could not read
the mounted tree and made no request); the post-check's release-1 reads, exit 1 on two differences of the rehearsal
alone (the converter's volume is a bind there; no ops-agent grant): the settings, limits and nginx reads as declared,
the converter and ops-agent reads first run to a pass on live.

**The release package's own tests** (TESTS.md): bash -n on every script and the BY rule; baseline_r1.sh on live (read-only, exit 0, 234 lines);
act_r1.sh through its simulation (a real git checkout, a stub door writing the installer's receipts, log times 60 s apart),
78 of 78 - the declared order end to end, every phase before its predecessor refused, the manage acts' reason file, BY and
verify rules, the newest pre-app log, the rerun, reissue and switch-back rules, the placeholder guard - with thirteen mutants of
the guards added after the package's review killed (and before it 13 of the ordering guards, then three of the placeholder
guard); pre_app_r1.sh whole against the rehearsal in the act's order (PASS; two negative controls stopped with exit 7), and its
repaired counts and gate with stubs, 12 of 12 (the version reviewed first fails 11 of them), the same step read on live
(read-only); post_check_r1.sh's bindings to this declaration, its maintenance read and its log reader with stubs, 32 of 32, the
maintenance read also run on the rehearsal's database; live_check_r1.py's credentials shapes and lost answers, 15 of 15; 23
mutants of those three scripts killed; live_check_r1.py 25 of 25 against the rehearsal (07:51:41Z, a flat credentials file,
before its repairs) with a negative control against 6ab8e503a400 behind the same stage (exit 1, 10 checks failing). Still to be
run on live only: post_check_r1.sh's ingress, certificate and public reads, the converter's volume and ops-agent's grant.

**The release package's review**: four lenses - this declaration's facts, the scripts, the safety of the act, and the owner's words - and one
independent re-test per finding, 2026-11-25 08:11-09:38Z, on the package as it then stood (this text at sha256
736cfd3c5cdd6c99, act_r1.sh 8ea25b59eb9b9398): 75 findings, 71 real (2 high, 15 medium, 54 low), 4 not; every one repaired in
the scripts or corrected in this text (DECISIONS D420). The script repairs were then refuted by two more lenses: nine findings,
one medium and eight low, all repaired or narrowed. The edited text was read again by three more (facts, the owner's words, the
procedures): 43 findings, 2 high, 10 medium and 31 low, all corrected - the two highs one false event, a question to the owner
written down before it had been put to him (D421) - and not read again by a further lens. The package as run (sha256, first 16): act_r1.sh 300a253629cab966,
pre_app_r1.sh b1027ef9c91805f6, post_check_r1.sh 4a03afca60aae753, baseline_r1.sh d5b0f7a51d3a615a,
live_check_r1.py 084649de4c13c248, and lead/measure/measure_pre_counts.sh b4cb8615b5590dd6 (pre_app_r1.sh's step 2
alone, for the counts read before this commit); release 2's baseline_i.sh fb6ae0e5f0d96fa5 and
install-judge/live_baseline_j.sh 791ef3b531021b6c, unchanged.

## Baseline (read-only, `2026-11-25T17:42:41Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_r1.sh are binding)

Read with these commands, all read-only (SELECT and SHOW only, in a read-only transaction, through the database
container's own psql; the container's own cgroup files and docker inspect; counts, names and states only, never a
document, response or credential):

    (umask 077; bash /home/claude/cpt-r1-20261124/release/baseline_r1.sh > /home/claude/cpt-r1-20261124/release/declared-baseline-20261125.txt)
    ( cd /opt/meddoc-pro/.worktrees/cpt-r1-docs-20261125 && bash scripts/check-cotenants.sh )
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:6ab8e503a400 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
    sha256sum /etc/nginx/sites-available/quillmd /etc/nginx/sites-available/quillmd-cpt; readlink /etc/nginx/sites-enabled/quillmd-cpt
    the certificate names served for admin.quillmd.com, cpt.quillmd.com and app.quillmd.com (openssl s_client against 127.0.0.1:443, as post_check_r1.sh reads them)

baseline_r1.sh is release 2's baseline_i.sh unchanged (install-judge/live_baseline_j.sh plus every category, workspace,
membership, the password-hash digest, the operator grants and the audit events by name) plus release 1's rows: the
session count, the database's two statement-logging settings, release 1's tables (absent until 0017 and 0018 apply), the
database container's cgroup memory.max and memory.swap.max, and its HostConfig memory, memory + swap and /dev/shm.
<!-- The block below: baseline_r1.sh's output exactly, each line indented four spaces, from its read_at line up to the
co-tenants reading (pre_app_r1.sh and post_check_r1.sh extract that span with awk and diff it with the declared baseline
file). Its release-1 rows: sessions <n>, setting log_error_verbosity default, setting log_min_error_statement error,
r1_table <each of the ten tables 0017 and 0018 create> absent, db_cgroup memory.max 536870912, db_cgroup memory.swap.max
max, db_hostconfig memory 536870912 memory_swap 536870912 shm 134217728. Expected in the other readings: co-tenants every
row judged and as expected, admin.quillmd.com included (302 to https://admin.quillmd.com/login/); containers
cpt-studio-web (127.0.0.1:9151->8000/tcp, healthy) and cpt-studio-worker of 6ab8e503a400's image, cpt-studio-db
postgres:17.11-alpine on 127.0.0.1:55451, no cpt-studio-converter; ingress quillmd b3ab66023547..., quillmd-cpt
1672b98db8cf... behind the link /etc/nginx/sites-available/quillmd-cpt; admin.quillmd.com and cpt.quillmd.com served
the cpt-studio certificate (exactly those two names), app.quillmd.com QuillMD's. -->

    read_at 2026-11-25T17:42:41Z
    transaction_read_only on
    encounters 101
    revisions 102
    source_files 95
    contexts 106
    routing_runs 116
    provider_runs 311
    provider_runs_sent 275
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1538
    reports 209
    jobs 665
    jobs_active 0
    users 9
    memberships 7
    workspaces 3
    login_attempts 145
    reference_sources 2
    reference_facts 34665
    studio_migrations 16
    studio_migration_last 0016_fable_coding
    studio_providerexchange 264
    studio_toolcall 173
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 29
    studio_memberanswerrevocation 6
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_clarification.answer_id present
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_memberanswer.question present
    column studio_reportartifact.audience present
    member_answers_standing 23
    member_answers_by_value cannot_confirm 17
    member_answers_by_value not_documented 12
    run_participant anthropic appraisal succeeded 4
    run_participant anthropic coding_checker succeeded 12
    run_participant anthropic coding_reader succeeded 12
    run_participant anthropic interpretation succeeded 3
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 44
    run_participant astra peer_review succeeded 46
    run_participant fable independent succeeded 45
    run_participant fable peer_review failed 1
    run_participant fable peer_review succeeded 41
    credits_sum 4.452079999999999826
    usage_keys anthropic cache_creation,cache_creation_input_tokens,cache_read_input_tokens,fallback_credit,inference_geo,input_tokens,iterations,output_tokens,output_tokens_details,server_tool_use,service_tier,speed
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state awaiting_answer 5
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready 3
    encounter_state ready_for_review 8
    encounter_state reviewed 33
    run anthropic appraisal succeeded t f 4
    run anthropic coding_checker succeeded t f 12
    run anthropic coding_reader succeeded t f 12
    run anthropic interpretation succeeded t f 3
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded f t 7
    run astra independent succeeded t f 37
    run astra peer_review succeeded f t 2
    run astra peer_review succeeded t f 44
    run corti primary not_sent f f 4
    run corti primary succeeded f t 13
    run corti primary succeeded t f 81
    run corti second_review succeeded t f 2
    run fable independent succeeded f t 7
    run fable independent succeeded t f 38
    run fable peer_review failed t f 1
    run fable peer_review succeeded f t 2
    run fable peer_review succeeded t f 39
    job analyze succeeded 89
    job appraise succeeded 3
    job assess succeeded 186
    job astra cancelled 3
    job astra succeeded 45
    job astra_peer succeeded 46
    job code succeeded 12
    job extract succeeded 90
    job fable cancelled 4
    job fable succeeded 45
    job fable_peer cancelled 1
    job fable_peer succeeded 41
    job interpret succeeded 3
    job predict succeeded 94
    job question succeeded 1
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit operator.password_reset 2026-11-24T22:50:50Z 67911
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account owner-neuro human t owner t
    account owner-ortho human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    account review-agent-neuro agent t reviewer t
    account review-agent-ortho agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-events@3 6
    assessments_by_engine cpt-studio-validation@10 57
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8
    assessments_by_engine cpt-studio-validation@8 6
    assessments_by_engine cpt-studio-validation@9 23
    contexts_by_version gemini-context@2 3
    contexts_by_version gi-context@1 12
    contexts_by_version gi-context@2 26
    contexts_by_version gi-context@3 19
    contexts_by_version gi-context@4 35
    contexts_by_version gi-context@5 11
    current_context_by_version gemini-context@2 3
    current_context_by_version gi-context@1 12
    current_context_by_version gi-context@2 24
    current_context_by_version gi-context@3 7
    current_context_by_version gi-context@4 31
    current_context_by_version gi-context@5 11
    current_context_by_version none 13
    routing_by_version gemini-routing@2 3
    routing_by_version gi-routing@10 11
    routing_by_version gi-routing@11 8
    routing_by_version gi-routing@12 11
    routing_by_version gi-routing@3 12
    routing_by_version gi-routing@4 38
    routing_by_version gi-routing@5 7
    routing_by_version gi-routing@6 7
    routing_by_version gi-routing@7 7
    routing_by_version gi-routing@9 12
    studio_eventinventory 3
    studio_interpreterhold 0
    studio_interpreterholdrelease 0
    studio_providerhold 0
    studio_providerholdrelease 0
    column studio_assessment.event_inventory_id present
    column studio_assessment.interpretation present
    column studio_encountercontext.earlier_assessment_id present
    column studio_encountercontext.event_inventory_id present
    column studio_eventinventory.appraisal_run_id present
    jobs_reading appraise succeeded 3
    jobs_reading interpret succeeded 3
    jobs_reading question succeeded 1
    runs_interpreter anthropic appraisal 4
    runs_interpreter anthropic interpretation 3
    assessments_new_path 6
    contexts_new_path 3
    decisions_on_current_assessments approve 52 32
    decisions_on_current_assessments reinstate 1 1
    decisions_on_current_assessments reject 6 6
    decisions_on_current_assessments revoke 2 1
    studio_codinground 12
    studio_codinganswer 0
    studio_codedecision 20
    studio_exportartifact 15
    jobs_code succeeded 12
    runs_coding coding_checker succeeded 12
    runs_coding coding_reader succeeded 12
    interpreter_holds_standing 0
    categories 3
    category gastroenterology gi-profiles@3 present
    category neurosurgery fable-coding@1 present
    category orthopedic-surgery fable-coding@1 present
    workspace gastroenterology Gastroenterology present
    workspace neurosurgery Neurosurgery present
    workspace orthopedic-surgery Orthopedic_Surgery present
    member demo-reviewer gastroenterology Gastroenterology reviewer t
    member owner gastroenterology Gastroenterology owner t
    member owner-neuro neurosurgery Neurosurgery owner t
    member owner-ortho orthopedic-surgery Orthopedic_Surgery owner t
    member review-agent gastroenterology Gastroenterology reviewer t
    member review-agent-neuro neurosurgery Neurosurgery reviewer t
    member review-agent-ortho orthopedic-surgery Orthopedic_Surgery reviewer t
    password_hashes_digest 8ad5bae08e6247d917a60b817327b4414640daef5a3dcf15e756f4d7346b40b7
    operator_grant ops-agent standing
    operator_grant platform-operator standing
    audit_event account.provisioned 7
    audit_event assessment.created 186
    audit_event assessment.recompute_queued 12
    audit_event assessment.refreshed 20
    audit_event coding.round_done 12
    audit_event coding.round_queued 12
    audit_event context.changed 17
    audit_event decision.recorded 83
    audit_event detail.answered 32
    audit_event detail.revoked 6
    audit_event encounter.created 101
    audit_event export.created 15
    audit_event operator.password_reset 2
    audit_event operator.viewed 134
    audit_event pipeline.resumed 8
    audit_event pipeline.stopped 8
    audit_event provider.finished 275
    audit_event provider.reused 31
    audit_event provider.second_review_requested 2
    audit_event provider.sending 275
    audit_event report.generated 209
    audit_event revision.addendum 1
    audit_event revision.extracted 90
    sessions 116
    setting log_error_verbosity default
    setting log_min_error_statement error
    r1_table studio_accessrecord absent
    r1_table studio_accessrecordrepeat absent
    r1_table studio_securityevent absent
    r1_table studio_disposalevent absent
    r1_table studio_ratewindow absent
    r1_table studio_onetimetoken absent
    r1_table studio_secondfactorcredential absent
    r1_table studio_secondfactorrecoverycode absent
    r1_table studio_filekey absent
    r1_table studio_sessionaccountlink absent
    db_cgroup memory.max 536870912
    db_cgroup memory.swap.max max
    db_hostconfig memory 536870912 memory_swap 536870912 shm 134217728
    --- co-tenants
    HOST                   EXPECTED  OBSERVED
      🟢 quillmd.com          200       200
      🟢 www.quillmd.com      200       200
      🟢 app.quillmd.com      302       302
      🟢 admin.quillmd.com    302>https://admin.quillmd.com/login/ 302 → https://admin.quillmd.com/login/
      🟢 pro.quillmd.com      410       410
    🟢 every judged co-tenant answers its expected status (4 distinct codes — the probe discriminates).
    --- containers
    cpt-studio-db postgres:17.11-alpine Up 10 days 127.0.0.1:55451->5432/tcp
    cpt-studio-web 6ee79ec888ac Up 46 hours (healthy) 127.0.0.1:9151->8000/tcp
    cpt-studio-worker 6ee79ec888ac Up 46 hours 8000/tcp
    --- image
    sha256:6ee79ec888ac27e9bf6f9508508bd1bd2b0f0acac185259e4448d0ed2ed27d6c 6ab8e503a40050c08c01c965441fa56583fb5e03
    --- ingress
    b3ab66023547790e861c3d12b39d8b268de8748ba6453f830194a4df6e4a3dbb  /etc/nginx/sites-available/quillmd
    1672b98db8cfb9253b85187ce49bf483f47c636daae5138cadc995e5160a9bbf  /etc/nginx/sites-available/quillmd-cpt
    quillmd-cpt link /etc/nginx/sites-available/quillmd-cpt
    admin.quillmd.com served: admin.quillmd.com cpt.quillmd.com
    cpt.quillmd.com served: admin.quillmd.com cpt.quillmd.com
    app.quillmd.com served: admin.quillmd.com app.quillmd.com pro.quillmd.com quillmd.com www.quillmd.com

## Expected changes, per phase

Every phase, both preflights, cert, passages, license-note and verify included, ends, beside what its bullet says, by
appending one line per one-shot and root-helper run it made (time, phase, fixed name, exit code, the declaration and its
commit, a manage act's --by name; never an argument's value or an output) to /var/log/cpt-studio/oneshots-<date>.log
(root 0600), through one more root-helper run with /var/log mounted read-write; the receipt's oneshot_log reads written
true, that file and its number of lines, nothing pruned. The first preflight makes /var/log/cpt-studio and its containers
folder (root 0700) and that file; none of them is on the host before it (2026-11-25). That helper deletes only its own
files there dated more than 14 days back, none in this act, and no rollback removes any of them. "None" and "nothing
changes" below are apart from this and the receipts.
<!-- install.py: run_helper and oneshot (journal), phase_image's own journal calls, main's finally (flush_journal),
H_JOURNAL, _LOG_DIRS, LOG_KEEP_DAYS -->

- **preflight:** none (one probe file written to the ACME webroot and removed, and admin's challenge route probed the
  same way). Its receipt records the baseline: the coupling after (the quillmd vhost b3ab66023547...; quillmd-cpt
  1672b98db8cf..., 6ab8e503a400's HTTPS stage for 9151, behind the installer's link, naming both hosts on 443); 9151
  held by cpt-studio-web alone, 9150 free, no cpt-studio-web-next; 55451 the database's; both names resolving to A
  147.189.172.8 alone, no AAAA; the pinned helper and postgres images present; exactly one ACME account and the webroot
  writable; admin's HTTP-01 route answering through QuillMD's :80 block; co-tenant routing and
  https://app.quillmd.com/health/; scripts/check-cotenants.sh passing, admin.quillmd.com skipped and not judged; no task
  of uid 10150 or of the converter's uid 10151 outside CPT Studio; the coder's Anthropic source, when present, root 0600
  in a root 0700 directory (coding_source present: the live pair codes live, and app reads the copy the secrets phase
  made); at least 10 GiB free on /.
  <!-- install.py: phase_preflight, read_coupling, coupling_problem, web_port_layout, port_problem, foreign_uid_tasks
  (APP_UID, CONVERTER_UID), cotenant_check (judged_skipped), acme_probe, acme_problems, coding_source_problems, le_state -->
- **image:** a new local image cpt-studio:`816045c72644`, built from git archive of the revision's cpt-studio/ and
  labelled with the revision. Before anything is built, every migration after 0005 is read (with ast) and must be
  additive for a pair that does not know it: 0017 and 0018 pass (new tables, nullable columns with no database default,
  non-unique indexes, constraints on tables they create). Then: the revision label, user 10150:10150 and the baked
  release; `manage check`; the WSGI load as the image's own user on a read-only root; `soffice --version` naming
  LibreOffice; anthropic 2.11.0; the conversion gate (a synthetic Word file converted in-process under the worker's
  limits with no network, its PDF starting %PDF-); and, new, the converter's own self-test under the converter's user and
  limits with no network, which must print "cpt-studio converter self-test: ok, a PDF of ...". cpt-studio:6ab8e503a400
  is kept.
  <!-- install.py: phase_image, migration_safety, migration_verdict, image_soffice, image_anthropic, image_conversion,
  image_converter_self_test, has_converter -->
- **db:** no restart and no connection dropped. The network and both volumes are ensured (they exist) and the files
  volume's root re-asserted (10150, 0700). The database container must be ours, running, on the pinned image,
  loopback-only, unless-stopped, on cpt-studio-net, with every capability dropped, core dumps off and a 128 MiB
  /dev/shm (the installer's db_args have set each since the first install, 9f00fdbe1; anything else refuses, changing
  nothing). A3: its HostConfig reads
  512m/512m while its own cgroup's memory.swap.max reads `max` (the 2026-11-24 readings; the Baseline block's db_cgroup
  row is binding), so the change is made - the container has run since 2026-11-14T20:58:09Z, more than 7 days, and its
  memory.peak plus its swap's high-water mark (114,360,320 and 32,563,200 bytes at 2026-11-24T15:20Z) is far below 80% of
  512 MiB - as `docker update --memory 512m --memory-swap 512m` on the running container: the receipt's memory.state
  `updated`, memory.after reading memory.swap.max 0. Then A5: `ALTER SYSTEM SET log_min_error_statement = 'panic'`,
  `ALTER SYSTEM SET log_error_verbosity = 'terse'` and `SELECT pg_reload_conf()` (kept in postgresql.auto.conf on the data
  volume), read back on fresh connections: statement_logging.shown {log_min_error_statement panic, log_error_verbosity
  terse}.
  <!-- install.py: phase_db, ensure_network, ensure_volume, files_volume_helper (H_FILES_VOLUME), db_container_problems
  (memory=False first), wait_db_ready, db_memory (DB_PEAK_MIN_UPTIME_DAYS 7, DB_PEAK_SHARE 0.8, the docker update),
  db_cgroup, db_statement_logging, db_settings_shown, DB_LOG_SETTINGS. The readings quoted are RESULT.md's "Live's
  database container" section and TESTS.md's. -->
- **converter:** the volume cpt-studio-convert created (labelled, role convert) and its root given to 10151:10150 0750
  through the root helper, read back before anything starts; no converter exists, so cpt-studio-converter is started
  from cpt-studio:816045c72644: network none, no environment file, no files volume, no credential, user 10151:10150,
  read-only root, every capability dropped, no new privileges, 1536m without swap, 128 pids, a 1g /tmp tmpfs, no core
  dump, two CPUs, init, restart unless-stopped, stop timeout 80 s, the convert volume alone at /run/cpt-convert, a health
  check pinging its socket every 10 s. It must become healthy with no restart and pass the seal checks. The running
  worker of 6ab8e503a400 never uses it (it converts in-process, as today).
  <!-- install.py: phase_converter, ensure_volume, H_CONVERT_VOLUME, converter_args, hardening, wait_converter,
  service_problems (role converter), converter_problems -->
- **cert:** the stage it stands on read first - `served`: quillmd-cpt 1672b98db8cf..., recorded by release 2's app
  receipt, proxying to 9151, which the running web publishes; the coupling (after); both names resolving to
  147.189.172.8 alone; exactly one ACME account; both HTTP-01 routes proven. Then one certbot run in the root helper's
  chroot: `certbot certonly --webroot -w /var/www/certbot -d cpt.quillmd.com -d admin.quillmd.com --cert-name cpt-studio
  --non-interactive --keep-until-expiring --account <the one account>`. The lineage was ordered on 2026-11-23 and is not
  due, so no order is expected and nothing changes; the receipt records the lineage's paths (the receipt https-vhost
  requires). Every other lineage's renewal conf and live directory, and the ACME account set, unchanged.
  <!-- install.py: phase_cert, cert_stage, recorded_vhosts, live_web_port, H_CERTBOT, le_state, other_lineages -->
- **https-vhost:** quillmd-cpt replaced in place by this revision's HTTPS stage for 9151, the port cpt-studio-web
  publishes: `bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9` over 1672b98db8cf... (an earlier HTTPS stage a successful receipt here recorded,
  proxying to 9151 and naming the admin host on 443, as the phase requires); the coupling stays after; nginx -t with no
  new warning; one graceful reload (`sudo -n /usr/sbin/nginx -t`, `sudo -n /usr/bin/systemctl reload nginx`); verified
  through the public path while 6ab8e503a400 serves: https://cpt.quillmd.com/health/ answering that revision (its
  release, as an older web answers through nginx) with the four policy headers once each; admin.quillmd.com served the
  cpt-studio certificate with those headers, /api/session 404, GET and HEAD / 302 to /login/, the sign-in page and its
  static files 200; the two hosts served certificates naming the same hosts; 421 for either host on a connection opened
  for app.quillmd.com; each host served on the other's connection; http://cpt.quillmd.com/ 301 to https; both HTTP-01
  routes; co-tenant routing and app.quillmd.com as the first preflight recorded. On any failure the replaced bytes are
  written back and nginx reloaded with them. The TLS policy is then probed (the host's openssl against 127.0.0.1:443 for
  each name) and recorded, never undone (D27): expected at least TLS 1.3 ChaCha20 accepted for both names, since CPT's
  block is not the shared listener's default server (ops/INSTALL.md, Known limits); each finding is named in the report.
  From here the limits, logs, buffers, TLS settings, version hiding and both cookie lines apply to the old web too.
  <!-- install.py: phase_https_vhost (require_receipt cert, unrecorded_ingress_problem, serving_web_port, names_host_on,
  coupling_problem expected after, running_web), publish_vhost, vhost_operation('replace'), https_checks, admin_checks,
  admin_answers, health_ok (has_health_digest), public_health, acme_probe, ingress_checks, tls_policy_report,
  tls_policy_problems -->
- **preflight again (TAG after-https-vhost):** none; its receipt records the after-republish baseline: quillmd-cpt
  `bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9` behind the installer's link, the coupling after, 9151 active and 9150 free, the converter running.
- **Before app, read-only on the live database** (pre_app_r1.sh, with DECLARED_BASELINE /home/claude/cpt-r1-20261124/release/declared-baseline-20261125.txt; no
  copy of live is made, D409): the declared baseline file (mode 0600 or 0400) equal, exactly, to this declaration's
  Baseline block from its read_at line up to the co-tenants reading; every applied row of live's django_migrations, read
  in a read-only transaction through the database container's own psql, against the migrations on disk in
  cpt-studio:816045c72644 (a throwaway container of that image named cpt-r1-rh-migrations-<hex>, no network, the
  harness's synthetic environment, MigrationLoader with no connection): the pending set exactly studio.0017_r1_security
  and studio.0018_r1_availability, and nothing applied on live missing from the image; the first maintenance run's
  expected changes, counts only - the orphan files it will remove (a listing of cpt-studio-files mounted read-only into a
  throwaway container of the pinned postgres image with no network: names, kinds and modification times, never a file's
  bytes, zero-byte files included, against studio_sourcefile.storage_name and studio_codinground.view_pdf_storage_name,
  older than an hour), the entries it leaves alone as unexpected, the names those two columns hold with no file (missing),
  the sign-in rows whose typed name it will hash (older than 30 days, matching no account, ignoring case) and the sign-in
  rows past the six-year retention it will delete - and it stops unless the orphan, unexpected, missing and past-retention
  counts it reads equal the one set of them this declaration holds (below), read before the commit, and when a file no row
  names is under an hour old (young: the run may find it older); the rows to hash are
  printed, not gated (a name may pass 30 days between the two readings); baseline_r1.sh read again and equal to the
  declared baseline with exactly the db phase's three declared changes made to it - log_error_verbosity default to terse,
  log_min_error_statement error to panic, the database's own cgroup memory.swap.max max to 0 (each line required once; a
  db phase that did not take, or changed anything else, stops here) - and but for read_at, the last audit, the sign-in
  count and the session count; the gates (jobs_active 0, runs_reserved_or_sending 0, runs_unreconciled_unknown 0, no
  reading job queued or running, the last audit event at least 600 s old); no cpt-r1-rh-* container running. Its log ends
  "PRE-APP PASS"; the counts it prints, the declared ones but for the rows to hash, are what the first maintenance run is
  judged by (below).
  <!-- pre_app_r1.sh: steps 1-5 (its header); ro_sql, the migrations reader, the orphan listing, the comparison with the
  declared counts (declared, observed), the gates -->
- **app (the blue/green switch, from 9151 to 9150: the receipt's details.ports):** before anything starts - the coupling
  read again, the converter of this revision running healthy and sealed, the database, the coder's credentials copy
  (10150:10150 0400) read by the application's own loader with no network. **Migrate applies exactly
  studio.0017_r1_security and studio.0018_r1_availability**, the one-shot waiting at most 5 s for a table's lock (up to
  three more attempts, 10 s apart, on a lock timeout alone):
  - 0017 creates eight tables - AccessRecord, DisposalEvent, FileKey, OneTimeToken, RateWindow, SecondFactorCredential,
    SecondFactorRecoveryCode, SecurityEvent - with their indexes, the new tables' foreign keys and RateWindow's one
    unique constraint, and adds twelve nullable columns with no database default to existing tables (AuditEvent client,
    request_id, sign_in_ref; Encounter destroyed_at; LoginAttempt door, outcome, sign_in_ref; OperatorGrant
    authorization_ref, review_by; User password_change_required_at, password_changed_at; Workspace closed_at) and one
    non-unique index on LoginAttempt (client, created_at);
  - 0018 creates two tables - AccessRecordRepeat and SessionAccountLink (with one unique constraint) - adds LoginAttempt
    client_key (nullable, no default) and ten non-unique indexes: two on AccessRecord, seven on LoginAttempt (four of
    them partial, one on Upper(username)) and one on SessionAccountLink.
  No existing row is changed by either. The migrate command itself adds rows to three of Django's own tables and to no
  other existing table: django_migrations +2 and, for the ten new models (Django's post-migrate step),
  django_content_type +10 (44 to 54) and auth_permission +40 (176 to 216); the baseline reads neither of these two, so
  they are not in the expected-deltas file (on the restored copy every other existing table's count unchanged, 10 new
  tables empty). Then, read and recorded, never refused on: the stages of a kind this worker does not run; no design v1
  row (refused otherwise); the install counts (encounters and those coded, jobs by kind and state, provider runs by
  purpose and state, unknown outcomes and runs in flight, the four tables of 0016, standing holds), which must equal the
  Baseline block's, but for the coded count, which has no row there (recorded; at most studio_codinground). The switch,
  with an availability record of https://cpt.quillmd.com/health/ every 0.5 s from before S1 to the end of S5 (migrate,
  the reads before S1, and S6 are not sampled):
  - **S1** cpt-studio-web-next starts on 127.0.0.1:9150 (768m without swap, read-only, no bind mount) and answers
    /health/ there with the revision, its sign-in page and every static file it names, and the admin host's own answers
    on its loopback port;
  - **S2** the old worker parked (`docker stop --time 3600`: its current stage finishes, nothing new is claimed); then,
    because 6ab8e503a400's tree has no studio/sessions.py and this revision's has (release 1's session policy), every
    session is ended in this revision's image: in one transaction (lock timeout 30 s) every django_session row deleted
    and one SecurityEvent `sessions.ended_at_install` written (the count, both revisions, the actor label installer); the
    receipt's sessions_ended says how many;
  - **S3** quillmd-cpt's upstream switched: `bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9` replaced atomically by this revision's stage for 9150,
    `e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792`, the two differing in their proxy_pass line alone (switch.vhost_sha_before and
    switch.vhost_sha_after); nginx -t with no new warning; one graceful reload; verified through the public path:
    /health/ answering `release_digest` `eac720ae88e983ec` and no release (B7), the admin host on the cpt-studio
    certificate with its answers, the 421 guard, each host on the other's connection, co-tenants and app.quillmd.com
    as the preflight after https-vhost recorded. From here the web sets `__Host-cptstudio_session` (Secure, HttpOnly,
    Path=/, no Domain, SameSite Strict), `__Host-cptstudio_csrf` (Secure, Path=/, readable by the page) and, on a sign-in,
    `__Host-cptstudio_device` (HttpOnly, 90 days), and deletes a browser's `cptstudio_session` and `cptstudio_csrf`;
  - **S4** the new worker starts with the coding step live, the Anthropic copy mounted read-only into it alone, the
    convert volume mounted read-only, told the socket and that the converter is required;
  - **S5** the old web drained (at least 130 s, until 10 quiet one-second samples, at most 600 s), stopped (30 s), parked
    as cpt-studio-web-previous, and cpt-studio-web-next renamed cpt-studio-web;
  - **S6** the stored list states recomputed with this revision's derivation - state.py is byte-identical, so none is
    expected to change - then the parked pair's logs kept ids only (/var/log/cpt-studio/containers/web-6ab8e503a400-<UTC>.log
    and worker-6ab8e503a400-<UTC>.log, root 0600; the receipt's logs_kept gives each file's sha256 and its lines kept and
    dropped, never a line) and the parked pair removed (its image kept).
  About 60 s after S4 the new worker's first sweep runs the maintenance, both parts due at once because neither of their
  SecurityEvents exists yet: the daily run (dead session links and expired sessions removed; no rate window is a day old;
  sign-in rows older than 30 days whose name matches no account get the name's keyed hash in its place, rows kept; no
  sign-in row is older than the six-year retention; the files under the originals folder that no row names and that are
  over an hour old removed; stale conversion folders removed) with its SecurityEvents `maintenance.daily` and
  `maintenance.daily_files_removed`, and the weekly check reading up to 200 stored originals and 200 converted PDFs again
  against their sha256, with `maintenance.originals_verified` and one `storage.original_mismatch` per file missing,
  changed or unreadable (expected none). The daily run's counts are declared here, read read-only 2026-11-25T17:42:43Z,
  before this amended text was committed, by lead/measure/measure_pre_counts.sh (its step is pre_app_r1.sh's own step 2;
  pre_app_r1.sh's log cannot exist earlier, since it needs this declaration and the built image): `orphans=0 unexpected=0 missing=0 past_retention=0` (and names_hashed_rows=0).
  pre_app_r1.sh's reading at the act is the binding one (above). The declared count of orphan files is 0, so the first
  maintenance run removes no stored file; if it were ever more than 0, the owner is asked before any stored file is
  removed (class d: deletion of data). post_check_r1.sh (PRE_APP_LOG: the log app ran on) then reads the run's two
  records, counts only, each once: sweep_orphans and sweep_deleted must equal that log's orphans, sweep_failed be 0,
  signin_names_hashed equal its names_hashed_rows and login_attempts_pruned its past_retention; a different count in
  maintenance.daily or maintenance.daily_files_removed, or a step either names as failed, is a finding. Since refutation
  round 4 (disposal-0) the daily run removes the session store's dead links, the expired sessions and the day-old rate
  windows in short transactions of their own before its recorded transaction; the counts and the events are the same.
  Once its migrate has applied a migration, app has had its one attempt under this declaration, however it ended (the
  refusal for a co-tenant deploy since the preflight included, which the installer makes only after migrate):
  pre_app_r1.sh then stops and act_r1.sh refuses a second app; the way on is a new declaration. After a failure at S5 or
  S6 switch-back is refused too (it needs a successful app receipt of this revision).
  <!-- install.py: phase_app (coupling_problem, unrecorded_ingress_problem, converter_problem, check_credential_files,
  check_credential_parsing, migrate_bounded: MIGRATE_LOCK_TIMEOUT 5s, MIGRATE_LOCK_RETRIES 3, MIGRATE_RETRY_PAUSE 10),
  UNRUNNABLE_STAGES, v1_rows, install_counts (INSTALL_COUNTS), _app_after_counts, replace_services, replacement_plan,
  switch_problems, switch_services (S1-S5), service_args, hardening, wait_service, smoke_web (admin=serves_admin_host),
  park, sessions_end_needed, has_session_policy (SESSION_POLICY_FILES), end_every_session (END_EVERY_SESSION),
  switch_upstream, https_checks, health_ok, release_digest, drain_web, retire_live_web, RECOMPUTE_STATES,
  retire_parked, keep_container_log, AvailabilityRecorder (switch_services: started before S1, stopped after S5),
  ingress_checks (switch_services, after migrate), require_receipt_entry (phase_switch_back); migrations
  0017_r1_security.py and 0018_r1_availability.py; Django's post-migrate rows as counted on the restored copy
  (lead/rehearsal/logs/counts-r2-2-premigrate.txt and counts-r2-3-migrated.txt);
  settings.py and sessions.SessionPolicyMiddleware.finish for the cookies; studio/jobs.py work() (sweep after
  STALE_SWEEP_SECONDS = 60, _maintain) and studio/maintenance.py tick, run_due, _due, run_daily, verify_originals
  (VERIFY_SAMPLE 200). ops/INSTALL.md does not mention this first maintenance run. -->
- **passages:** the three committed files (byte-identical since 6ab8e503a400) imported by the application's idempotent
  importer, one one-shot each, after `manage migrate --check` passes: nothing new (studio_passagesource and
  studio_referencepassage as the Baseline block reads them).
  <!-- install.py: phase_passages, passage_files -->
- **license-note:** no reference source holds the old note (both rows' md5 is 40a09bcd128dd18569a0a01e4fc4cffe, the
  corrected text's, in the 2026-11-23 baseline; the Baseline block above is binding): "no reference source holds the old
  licence note; nothing changed", updated 0.
  <!-- install.py: phase_license_note, LICENSE_NOTE_FIX, license_note_problem; md5 of LICENSE_NOTE_NEW computed by the
  drafter -->
- **verify:** nothing changes. Against the preflight after https-vhost: quillmd-cpt this revision's stage for 9150, the
  port the running web publishes (`e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792`), the quillmd vhost the after state, every other sites-available
  file, the links, nginx.conf and conf.d as recorded; routing, app.quillmd.com and the co-tenant check unchanged; the
  co-tenants' containers the same running containers; no volume gone; no other lineage changed; the database running,
  labelled, loopback-only, its cgroup allowing no swap and its two settings read panic and terse; the web and worker of
  this image hardened (no swap, no core dump, the web on 9150 with no bind mount, the worker holding only the credentials
  file, read-only); the converter of this revision sealed and healthy; nothing parked or incoming left; the HTTPS checks
  for this revision (the digest through nginx, the policy headers, the admin host, the 421 guard, each host on the
  other's connection); both HTTP-01 routes; no foreign task of uid 10150. The TLS probes again, recorded (D27).
  <!-- install.py: phase_verify, live_web_port, rendered_vhosts, nginx_file_state, ingress_checks, cotenant_check,
  containers, volumes, other_lineages, db_container_problems, db_cgroup_problems, db_settings_shown, service_problems,
  converter_problem, https_checks, tls_policy_report, acme_probe, foreign_uid_tasks -->
- **manage revoke-operator ops-agent:** in a one-shot of this image, once `manage migrate --check` passes, the reason
  handed over as a RAM-only file (its sha256 and size in the receipt, its text redacted from every output kept), `--by`
  Kasra Rayat: every grant of ops-agent that no revocation ended gets one OperatorRevocation (the grant rows stay), every
  session of the account ends, and one SecurityEvent `operator.revoked` is written. The command prints "Revoked operator
  access from ops-agent (1 grant); every session of the account has ended." ops-agent held no console from S3 already (an
  automated account is never an operator in this revision, whatever its grant); the revocation makes it hold across a
  switch-back (6ab8e503a400 honours OperatorRevocation). Its login file (~/.cpt-studio/ops-agent-credentials.json) is left
  untouched: deleting it is the owner's (D11).
  <!-- install.py: phase_manage, MANAGE_COMMANDS, manage_argv, read_reason_file, RamFiles, oneshot, redact_output;
  management/commands/revoke_operator.py; operator.revoke, operator.is_operator; legacy_operator_files -->
- **manage issue-enrolment platform-operator:** the installer makes a setup code (5 groups of 5 characters, about 124
  bits), stages the root-only document /etc/cpt-studio/operator-enrolment.json (the url https://admin.quillmd.com/login/enrol,
  the username, the code, issued_at, valid_seconds 1800, the revision, synthetic_only) through the root helper, and hands
  the code to `manage issue_enrolment` as a RAM-only --code-file with the reason and `--by` Kasra Rayat: one OneTimeToken
  (operator_setup, its sha256 only, expiring 30 minutes after it is issued), earlier unused codes revoked (there are
  none), one SecurityEvent `second_factor.setup_issued`; the command prints the account and token ids and the expiry,
  never the code. Only then is the staged document committed (root 0600); a command that fails or prints the code keeps no
  code. The receipt names the file and valid_seconds, never the code; no session reads the file. Today's
  /etc/cpt-studio/operator-credentials.json is left untouched: deleting it once the operator has chosen a new password is
  the owner's (D12).
  <!-- install.py: issue_setup_code (new_setup_code, root_file stage/commit/discard, printed_code), OPERATOR_ENROLMENT,
  ENROLMENT_CODE_SECONDS; management/commands/issue_enrolment.py; second_factor.issue_setup_code -->

**Database deltas against the baseline:** after app, passages, license-note, verify, the two manage acts and the live
check, exactly these (post_check_r1.sh's expected-deltas file,
/home/claude/cpt-r1-20261124/release/expected-deltas-20261125.txt, 0600, lines `<key> <before> <after>`, made from this
committed table in the act checkout and never typed, with
`(umask 077; awk '/^[*][*]Database deltas against the baseline:[*][*]/{d=1} /^The six SecurityEvents/{d=0} d && /^    [^ ]/{sub(/^    /,""); print}' docs/foundation/mutations/20261125-cpt-studio-release-1-install.md > /home/claude/cpt-r1-20261124/release/expected-deltas-20261125.txt)`;
post_check_r1.sh refuses (exit 2) a deltas file, revision, stage digest or start time that is not this declaration's, or a
PRE_APP_LOG act-r1-app.log does not name;
read_at, last_audit, login_attempts and sessions are set aside by the comparison):

    studio_migrations 16 18
    studio_migration_last 0016_fable_coding 0018_r1_availability
    setting log_error_verbosity default terse
    setting log_min_error_statement error panic
    db_cgroup memory.swap.max max 0
    r1_table studio_accessrecord absent 2
    r1_table studio_accessrecordrepeat absent 0
    r1_table studio_securityevent absent 6
    r1_table studio_disposalevent absent 0
    r1_table studio_ratewindow absent 3
    r1_table studio_onetimetoken absent 1
    r1_table studio_secondfactorcredential absent 0
    r1_table studio_secondfactorrecoverycode absent 0
    r1_table studio_filekey absent 0
    r1_table studio_sessionaccountlink absent 0
    studio_operatorrevocation 0 1
    operator_grant ops-agent standing ended

The six SecurityEvents: sessions.ended_at_install (S2), maintenance.daily, maintenance.daily_files_removed and
maintenance.originals_verified (the worker's first maintenance), operator.revoked and second_factor.setup_issued; a
storage.original_mismatch would make seven or more, and is a finding. Every other row of the baseline unchanged: every
count, every account and membership, every workspace and category, the password-hash digest, every audit event count,
the encounter states, the jobs and runs, the reference sources and passages, the 0016 tables, db_cgroup memory.max and
the db_hostconfig row. The live check's own rows are its footprint below. post_check_r1.sh (DECL_FILE the committed
declaration in the act checkout; STAGE_9150 `e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792`,
STAGE_9151 `bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9`; PRE_APP_LOG the pre-app log app ran on (the one
act-r1-app.log names), ending PRE-APP PASS; ACT_STARTED the start line of act-r1-image.log) judges both directions and exits non-zero on any
finding: /health/ through nginx status ok, database ok and the digest `eac720ae88e983ec` with no release; the act
checkout's co-tenant check; the ingress read back (the quillmd vhost the pinned after state; quillmd-cpt behind the
installer's link naming both hosts on 443 and its sha256 this revision's stage for the port cpt-studio-web publishes -
9150 `e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792`; admin.quillmd.com and cpt.quillmd.com served
the cpt-studio certificate; app.quillmd.com still QuillMD's; https://admin.quillmd.com/ 302 to /login/); release 1's
structural reads (the two settings panic and terse; the database container 536870912/536870912 with memory.swap.max 0;
the converter network none, healthy, 10151:10150, read-only root, the convert volume alone and no secret's name in its
environment; ops-agent holding no standing grant; the first maintenance run's two records equal to PRE_APP_LOG's counts
with no failed step; nginx's error log since the act began with nothing buffered to a temporary file (an absent or
unreadable log is a finding), and every access line since then with a request id; that none holds a query string is the
stage's own log format, judged byte for byte above, and lines holding a '?' - an encoded %3F in the path, which $uri
decodes, or a user agent's - are counted, never a stop). A non-zero exit stops the act until it is judged; when the comparison itself
differs it lists every audit event since the baseline's last one; a member's own activity in the window is named in the report (each ordinary
coding round in the window adds two provider.counting rows, system, beside today's coding events; post_check_r1.sh lists
audit events only: rows a member's reads and sign-ins add to release 1's tables are read separately, read-only, by actor
and time).
<!-- post_check_r1.sh: bound() (the deltas file, revision, stage digests and start time), the comparison (rows(),
ignored_prefixes, the expected loop), health digest case, the co-tenant call, the ingress block (after_pin, cpt_names,
served/APP_STAGE, names()), the release-1 reads (settings, db_limits, db_swap, conv_*, revoked, maintenance), the log
reader; jobs._worst_case (provider.counting, once per token count). The count 6 is the code's: END_EVERY_SESSION,
maintenance.run_daily (DAILY_EVENT, REMOVED_EVENT), verify_originals (VERIFIED_EVENT; MISMATCH_EVENT per problem),
operator.revoke, issue_enrolment.handle. baseline_r1.sh reads all ten release-1 tables; studio_accessrecordrepeat (0018)
stays 0: the live check reads the list once and one document's detail once. -->

## After the install: the live check (ordinary use, not a phase)

cpt-r1-20261124/release/live_check_r1.py, once, after both manage acts (after revoke-ops-agent alone while the owner is not
there: the stop conditions), as
`python3 -I /home/claude/cpt-r1-20261124/release/live_check_r1.py --tree /opt/meddoc-pro/.worktrees/cpt-r1-act-20261125/cpt-studio --revision 816045c7264481bc6956285e1ca89991b9fcec2f --customer-credentials /home/claude/.cpt-studio/agent-credentials.json --encounter 6c450473-ceb7-4f06-8660-d5794a3cb777 --out /home/claude/cpt-r1-20261124/release/act/live-check-20261125`
(the walk's own synthetic review agent; the file is the installer's credentials document, and the one account in its
`accounts` list is read for its username and password - a flat document is read too - and nothing of either is printed;
the evidence folder must be new). Every connection is verified against the system's roots and the host name. 25 checks:
for each of cpt.quillmd.com and admin.quillmd.com, /health/ 200 with `release_digest` `eac720ae88e983ec` and no
release, a Server header naming no version, and HSTS; on cpt.quillmd.com, /ops/ signed out 404, /login/ 200 setting
`__Host-cptstudio_csrf` (Secure, Path=/, no Domain), the sign-in with the form's own token 302 to / setting
`__Host-cptstudio_session` (Secure, HttpOnly, Path=/, no Domain), /api/session and /api/encounters 200 with the tree's
client version, the detail of the walk's synthetic document 6c450473-ceb7-4f06-8660-d5794a3cb777 200 (read only when the list names it;
D361: on live the walk opens its own synthetic documents only, never the first one listed), /ops/ as that member 404, the sign-out 302 to /login/, and
the ended session replayed 401; on admin.quillmd.com, signed out, / 302 to /login/, /login/ 200, /ops/people 302 to the
sign-in, /api/session 404. Every answer is kept as its status, header names, cookie names and attributes and location -
never a body - and summary.json; exit 0 only when every check passes.
<!-- live_check_r1.py: main() (the accounts list), ask() (ssl.create_default_context; a lost answer is Answer(0)),
Check.keep, host_cookie_ok, jar_update -->
No act is posted on live. Its database footprint, by the code: studio_loginattempt +1 (set aside by the comparison),
last_login set on the review agent, one session row and its account link created at the sign-in and deleted by the
sign-out, rate windows for the sign-in's places (taken and given back, rows kept), and AccessRecord rows for the list read
and the detail read; no audit event and no security event. Measured on the rehearsal's synthetic database (no copy of
live, D409): the rehearsal run of 2026-11-25 07:51:41Z on cpt-r1-test:ca1fa02f5da6, 25 of 25 - AccessRecord +2
(member.list, member.detail), RateWindow +3 rows (signin.fail.client, signin.fail.pair, signin.inflight.user, each with
count 0: given back, the rows kept), SessionAccountLink 0, LoginAttempt +1 (signed_in at the cpt door); every row
baseline_r1.sh prints (the sessions, the encounter states and the password digest among them) compared before,
07:50:58Z, and after, 07:51:53Z: beside read_at and last_audit's age, only login_attempts, studio_accessrecord and
studio_ratewindow differ. Not measured: the last sign-ins (last_login on the review agent is by the code) and six
framework tables baseline_r1.sh does not count (auth_group, auth_group_permissions, auth_permission,
django_content_type, studio_user_groups, studio_user_user_permissions). A request that gets no answer reads as an answer
with status 0, so a run that loses an answer fails (exit 1, summary.json written) and still signs out; AccessRecord then
reads 0 to 2, and only when the sign-in's own answer or the sign-out was lost can the session row and its link stay
(studio_sessionaccountlink 1; its key is in no file, it idles out after 15 minutes, and its rows go with the first daily
maintenance after its 8 hours). Such a run is judged; the check may then run once more, into live-check-20261125-2, its
own rows added (AccessRecord +2, RateWindow up to +3, LoginAttempt +1): post_check_r1.sh, bound to the table above, then
exits 1 on the rows where the two runs together differ from it (r1_table studio_accessrecord, studio_ratewindow and, after a
lost sign-in answer or sign-out, studio_sessionaccountlink), judged by the two runs' summaries, and 0 where they add up to it.
<!-- throttle.Door.refusal/_take_inflight_place/record/give_back (FAIL_CLIENT, FAIL_PAIR, INFLIGHT_USER: rate.hit then
give_back, the rows stay), read_audit.record via api.py, session_store.SessionStore.save/delete (_delete_row_and_links).
The code suggests AccessRecord 2, RateWindow 3 and SessionAccountLink 0; only the rehearsal's measurement is declared. -->

Then post_check_r1.sh, with the expected-deltas file above: once, after both manage acts; when the owner is not there, a first
time after the live check and again after issue-enrolment (the stop conditions).

## Then: the owner's enrolment (his own act, inside the code's 30 minutes)

Once the post-check that follows issue-enrolment has ended, the owner reads the code from /etc/cpt-studio/operator-enrolment.json and enrols at
https://admin.quillmd.com/login/enrol (above). It writes, as his own activity and outside the post-check: the setup code
used, a claim token made and used, and one used webauthn_challenge token for the key's prompt (OneTimeToken +2; one
more, unused, per prompt cancelled and asked again within 5 minutes; a further key's or a later sign-in's challenge
replaces the used one and adds none; a setup started, left unfinished and reissued also keeps its revoked claim), his
new password (the password-hash digest changes; password_changed_at set), one SecondFactorCredential per key, 10
SecondFactorRecoveryCode rows, SecurityEvents password.changed, second_factor.enrolled and one second_factor.key_added
per further key, one admin-door LoginAttempt (signed_in), a session with its link, and a rate window for the setup
code's place. Then he opens one page of the console himself (D10, D419 (3)): as his own activity, one AccessRecord per
data page opened (measured: /ops/, /ops/spending, /ops/activity, /ops/activity/reads; none for /ops/security; by the
code, ops.list for the list, ops.detail for a document's page, and ops.content_open if he opens its content). Read
afterwards, read-only, with baseline_r1.sh: one passkey enrolled (D412; a second, on another device, is recommended),
named in the report. If the 30 minutes pass unused the code expires and the console stays closed; a new code is issued
only through act_r1.sh's reissue path - ENROLMENT_REISSUE_DECISION recorded in words, only after an issue-enrolment that
ended exit 0 and whose code's 30 minutes have ended, at most twice, each logged as
act-r1-issue-enrolment.reissue-<n>.log; after a reissue that did not end exit 0 neither a further reissue nor
RERUN_DECISION runs it: a further code is then a new declaration - and each reissue revokes the unused earlier code (one
more OneTimeToken and one more second_factor.setup_issued each).
<!-- second_factor_views._start_enrolment, _finish_enrolment, enrol; second_factor.claim_setup_code (SETUP_CLAIM_PURPOSE),
second_factor_views.enrol_options, second_factor.registration_options / _store_challenge (CHALLENGE_PURPOSE),
new_recovery_codes; operator.index, encounter_page, content_open (read_audit.record); act_r1.sh's reissue block
(ENROLMENT_REISSUE_DECISION, PREV_END, AGE) -->

## Must not change

Every encounter and every row of every table apart from the declared rows above (the schema's additions, migrate's 2
django_migrations, 10 django_content_type and 40 auth_permission rows, the sessions ended at S2, the six security
events, the revocation, the setup code, the live check's footprint, the first maintenance's renamed sign-in rows, and a
member's own activity, named in the report); every account's kind, activity and memberships, every workspace and
category, every operator grant row, and every password hash (the digest) until the owner's own enrolment; the decisions,
coding rounds, exports, reference sources, facts and passages; the database container (its id, image, ports,
capabilities, mounts) and its data volume but for the schema, the rows above and postgresql.auto.conf's two settings;
the files volume but for the files no row names that the first daily maintenance removes (the declared count, above:
pre_app_r1.sh stops at any other); every file in /etc/cpt-studio/ but the new operator-enrolment.json; every nginx vhost
but quillmd-cpt, the quillmd vhost staying the pinned after state b3ab66023547...; nginx.conf and conf.d; every
certificate lineage and renewal conf (checked as cert and verify compare them: renewal confs by digest, live directories
by name), and the ACME account; QuillMD's :80 block, its Caddy and its containers; the HTTP answers and certificates of
quillmd.com, www.quillmd.com, app.quillmd.com and pro.quillmd.com, and https://app.quillmd.com/health/;
admin.quillmd.com's console answer (302 to /login/) and its cpt-studio certificate; every image (nothing is removed; the
parked pair's containers are, after their logs are kept).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0, the coupling after, with the baseline above; image exit 0
with the image id recorded, 0017 and 0018 judged safe, the conversion gate's %PDF- and the converter's self-test line;
db exit 0, memory.state `updated` with memory.after's cgroup reading memory.swap.max 0, statement_logging.shown panic
and terse; converter exit 0, state `started`, the volume root 10151:10150 0o750, healthy; cert exit 0, stage `served`
(1672b98db8cf...), the lineage's paths recorded, no other lineage or account changed; https-vhost exit 0, vhost_sha256
`bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9`, upstream_port 9151, replaced 1672b98db8cf..., the coupling after, every public check passing, the
TLS findings recorded; preflight again exit 0; pre_app_r1.sh ending PRE-APP PASS; app exit 0 with migrate applying
exactly 0017_r1_security and 0018_r1_availability (migrate_attempts 1; 2 to 4, each after a lock timeout alone, are
declared above and named in the report), the install counts equal to the baseline's but for the
coded count, which has no row there, the switch applied (details.ports 9151 to 9150), sessions_ended naming 6ab8e503a400
and the revision with a count and an event id,
switch.vhost_sha_before `bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9` and switch.vhost_sha_after `e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792`, the availability record with
no sample other than 200, the drain not bounded out, no list state changed, logs_kept for the web and the worker; passages
exit 0 (three files, nothing new); license-note exit 0, updated 0; verify exit 0; revoke-ops-agent exit 0 (the
revocation's sentence, by Kasra Rayat, the reason's sha256 73eb23da67ae05ae67df8b8bc23548942fe4f70e1aa53fb7e2efb0950b9c72ed); issue-enrolment exit 0 (setup_code.file
/etc/cpt-studio/operator-enrolment.json, valid_seconds 1800; the reason's sha256 3ccb66cd5c9ca979d9dbd9f06d418369c8f606fbb30ee448cf512beface01c44); the live check
25 of 25; post_check_r1.sh with /home/claude/cpt-r1-20261124/release/expected-deltas-20261125.txt: exit 0, 0 unexpected; scripts/check-cotenants.sh. Afterwards,
the owner's enrolment read as above. post_check_r1.sh runs after the live check, once - or, when the owner was not there, a first time before issue-enrolment
(then exit 1 on the setup code's two rows: the stop conditions) and again after it: run after verify it would report
ops-agent's standing grant and the declared rows as findings.

## Rollback per phase, and its limits

- preflight, verify, image, passages, license-note: nothing to undo (nothing is expected to change but the log lines
  every phase appends under /var/log/cpt-studio, above, which stay; the image is kept).
- db: nothing to undo. The swap limit and the two settings stay through any switch-back (6ab8e503a400 runs on them: they
  change what the database may swap and what it logs, nothing it answers); taking the settings back would be an act of
  its own. The swap limit lasts only until the host's next systemd daemon-reload (What is not claimed).
- converter: the container and its volume stay, unused by an older worker; removing them is not part of any rollback
  here.
- cert: nothing to undo (nothing is expected to change but those log lines).
- https-vhost before success: the installer's own undo writes back the replaced bytes (1672b98db8cf...) and reloads.
  After success the stage stays and serves 6ab8e503a400's web as it serves this revision's (above). Taking it back is
  6ab8e503a400's own https-vhost of its template, under a new declaration.
- app before the switch (S1, S2): the incoming web removed and the old worker running again (one whose stop was asked for and
  not finished still runs then, and exits once its stage ends: it is started again by hand, as the receipt says); an end
  of the sessions that was started may have ended every session (the receipt says so). After the switch (S3, S4): when it can finish, the
  installer's own undo returns the 6ab8e503a400 pair, never stopping the serving web (ops/INSTALL.md's failure matrix).
    When a close names a record (a coding outcome left unknown and not reconciled) or, at S3 before nginx read the switched
  file, does not finish, the undo returns 6ab8e503a400's web and removes cpt-studio-web-next but leaves cpt-studio-worker
  stopped (held; the receipt says why): the site is served, coding is stopped, rollback-app refuses (it removes only this
  revision's pair), and the worker is started by hand (`docker start cpt-studio-worker`) only once the record is cleared
  on the serving web's console - or, after that S3 close, which may name none, once what stopped it is resolved (nginx never
  routed to the incoming web) - by a decision recorded in words. When the undo cannot finish (S3: the vhost not put back,
  or, once nginx may have read the switched file, nginx not proven to run the old one or a close, put-back or stop that
  does not finish; S4: a close, put-back, stop or switch back that fails), or the installer is killed
  between the old worker's parking and the new worker's start, cpt-studio-web-next is left beside cpt-studio-web, the
  old worker parked and no worker running: the site is served, uploads queue, coding is stopped, and preflight, app,
  switch-back and both manage acts refuse. The way back is rollback-app, by hand through the door (above: act_r1.sh
  refuses it; no preflight, it reads its own baseline where it switches nginx back; run again, its output under a further
  name, while its receipt asks for it). An unknown outcome leaves the worker held as above where quillmd-cpt names the
  old web; where it names the incoming web rollback-app stops there, and the record is cleared only on this revision's
  console, which no setup code opens here: under a new declaration. The parked worker is never started by hand. Then the
  act ends; a new install is a new declaration. A killed run
  writes no receipt: first read quillmd-cpt's proxy_pass port, `docker ps -a` and nginx's workers, and let nobody reload
  nginx before the recovery, because a reload moves traffic to the port the file names (ops/INSTALL.md, Recovery notes).
  S5, or a kill once the new worker runs: the new pair serves and codes and nothing is undone. S6 (the recompute, a log
  copy or a removal failing): the same, with the parked pair left. After either the act ends: app, switch-back and
  rollback-app refuse, act_r1.sh runs no later phase (passages, license-note, verify and the two manage acts all need an
  app that ended exit 0: ops-agent's grant stands, though this revision gives it no console; no setup code is issued, so
  the console stays closed), and what is left is cleared by hand as ops/INSTALL.md's Recovery notes say, under a new
  declaration. After an S5 failure no switch-back to 6ab8e503a400 is left; after an S6 failure one exists only once an
  app under that new declaration has succeeded. A kill before the old worker is parked leaves 6ab8e503a400 serving and
  cpt-studio-web-next to remove by hand (its worker started again if it was stopped), under a new declaration. 0017 and
  0018, once applied, stay applied through every failed app, undo and switch-back (migrations are not reversed;
  6ab8e503a400 runs on them).
  <!-- install.py: undo_switch (S1, S2, S5), undo_switch_s3, undo_switch_s4, finish_back, return_to_old_web,
  keep_layout, phase_rollback_app (its routing refusal while admin.quillmd.com is moved), rollback_from_keep,
  rollback_back, own_baseline, switch_problems, web_port_layout, switch_back_target; act_r1.sh's order block;
  ops/INSTALL.md, app (S1-S6) and Recovery notes -->
  After a successful app the incident path is `switch-back` (a fresh preflight, then
  act_r1.sh switch-back with SWITCH_BACK_DECISION recorded, arguments `--provider-mode disabled --coding-mode live
  --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the pair it replaced and its modes): the
  6ab8e503a400 pair returns on 9151 through this revision's stage for 9151 (`bbd482895d7926aa40b8ec49eedfe152b1fc0c511700f7f51a84d7708359f1a9`), which stays, every
  session ended again at B4 (that revision has no session policy), its worker converting in-process and the converter
  left running unused. It refuses, starting and stopping nothing, while any practice is closed or any document destroyed
  (6ab8e503a400 has no studio/disposal.py; this act disposes of nothing, so the way back stays open until the owner
  orders a first disposal - D407's accepted-capability loss), while this revision holds records an older revision would
  act on or show wrongly, and without a fresh preflight. After it: the protections go back to today's for as long as it
  runs - a password-only console reachable on cpt.quillmd.com and admin.quillmd.com, the hard lockout, no read records,
  the release shown in /health/; ops-agent stays revoked once revoke-ops-agent has run (before it, its grant stands, 6ab8e503a400 honours it, and act_r1.sh
  then refuses the manage act); the operator signs in with his password alone (the one he chose
  at enrolment, or today's if he had not enrolled), and a password reset on the older console during a switch-back is
  not forced to change under release 1 (rollback-5);
  release 1's verification tools report fail against that pair (they speak release 1's client version: rollback-4), so
  that revision's own tools are run from a checkout of it. A switch-back is an incident: short, recorded, and followed by
  a switch forward under a new declaration (act_r1.sh refuses app and both manage acts after a successful switch-back).
  <!-- install.py: phase_switch_back (coupling_problem, switch_back_target, has_converter(prev), replacement_plan,
  check_credential_files, undo_hazards / switch_back_hazards, disposal_refusal, has_disposal, DISPOSAL_COUNTS),
  switch_back_services (B2-B9), sessions_end_needed, legacy_live_problem; act_r1.sh switch-back ARGS -->
- The first maintenance run (about 60 s after S4, during S5, whatever S5 and S6 do) is permanent: no undo, switch-back
  or rerun returns an orphan file, a typed sign-in name that was hashed or a pruned row. 6ab8e503a400 names files by the
  same two columns, so a switch-back loses no document it serves.
- The two manage acts are not undone: in this revision no automated account can be granted again (and a re-grant of a
  revoked account needs a declaration approving it in its own line, which this one does not hold); an unused setup code
  expires in 30 minutes, and its root-only file stays until the owner removes it. A revoke-ops-agent that recorded its
  revocation and then failed is not repeated to exit 0 (the command refuses: no grant stands), so issue-enrolment is
  then a new declaration.
- A changing phase whose failure is proven twice (its log records the door's non-zero exit, and the installer's receipt
  written inside that run says ok false) runs again only through act_r1.sh with RERUN_DECISION recorded in words, after
  a preflight newer than the failed run (app only when it failed before its migrate applied anything: then pre_app_r1.sh
  again with TAG, which passes only while 0017 and 0018 are both still pending); the failed run's log is kept as
  act-r1-<phase>.attempt-<n>.log. A phase that ended exit 0 never runs again, but for issue-enrolment's reissue (above).
  A run whose end is unknown - no exit line, no receipt (a killed installer), or a receipt saying ok - is never repeated
  by act_r1.sh: it is a stop, its outcome read from the vhost's port, the containers and the receipts directory (a
  killed installer writes none), and decided by hand as above.
- An older revision's installer runs only once this revision's switch-back has returned that revision's pair: switch back
  revision by revision, newest first, each with its own installer (ops/INSTALL.md, Reinstalling an older revision). Its
  app refuses this revision's stage (an HTTPS stage it does not render); its own https-vhost is the way to take that
  stage back, under a new declaration.
  <!-- install.py: replacement_plan ("an earlier revision ... which this revision does not render for its port"),
  phase_https_vhost (in place over a recorded stage naming admin) -->
- The receipts and the images stay; the parked containers do not (retire_parked). This act makes no copy of live, so it
  has no restore point: each of the 21 upgrades since 2026-10-27 kept a pre-app dump, the only data-level way back, and
  the encrypted safety copy RELEASE-1-SPEC 1.3 expects before app is not taken, this act's own choice (D409, the lead's:
  0017 and 0018 only add; the owner was told and answered yes, D419 (2)). Nothing here takes back a migration, the
  sessions ended at S2, or what the first maintenance run removes or rewrites. The newest copies are of the database
  alone and older than this act (release 2's pre-app dump, 2026-11-23 19:19Z; the rehearsal's, 2026-11-24 15:15Z):
  restoring one deletes every row made since and is not part of this act.

## What is not claimed

- That nothing is spooled to disk at the edge on live: proven on the rehearsal by inotify on release 1's stage; on live
  only by nginx's own error log holding no "buffered to a temporary file" line since the act began (the live check
  uploads nothing). nginx's in-memory buffers can still be paged to the host's unencrypted swap file (spec section 7,
  item 5).
- That the no-swap limits outlast the host's next systemd daemon-reload: Docker's runtime gives systemd MemoryMax alone
  for a container whose memory + swap equals its memory and writes memory.swap.max 0 itself, so a daemon-reload (an
  unattended upgrade of a package with a unit - the last, nginx's, on 2026-11-22 at 06:28:23Z - or a co-tenant's deploy)
  writes max back for the database (as live's reads today), the web, the worker and the converter, until the container
  is started again or, for the database, a later db phase. verify reads the database's cgroup alone (the others'
  HostConfig), and nothing reads any of them between installs. During the act such a reload stops pre_app, verify or the
  post-check (db_cgroup memory.swap.max max), and db does not run again through act_r1.sh: decided under a new
  declaration. A limit systemd itself holds, or no swap, is a later release's or the new server's.
- That the TLS policy is in force on the shared listener: CPT's block is not its default server, so TLS 1.3 ChaCha20 is
  accepted (ops/INSTALL.md, Known limits); recorded, never undone (D27); the fix is CPT's own nginx on the new server.
- That the operator's second factor was rehearsed: it needs an authenticator, and is first used by the owner on live.
- That an operator's document page is read on live by any check of this act (D10, the class-b loss the owner accepted in
  D419 (3)): the live check proves the console's gate only.
- That the installer's S1-S6 orchestration, certbot and DNS, the host's nginx build and co-tenant blocks, or the coding
  pause with 1 and 4 documents in progress were rehearsed (RESULT.md, "Not rehearsed here"; spec 6.4).
- That the way back was rehearsed on the revision: both rehearsals of 2026-11-25 (ef859c7388ba, ca1fa02f5da6) ran
  forward only. The last switch-back and second forward ran on 496c69d36d9b (2026-11-24 17:23Z; its parts, never
  install.main's B2-B9), and the last Word file converted by the worker over the converter's socket was on 3048931b5c28,
  on bind mounts (RESULT.md). The act and its checks code nothing and send no document through the running worker and
  converter (the image phase's two synthetic conversions are one-shots): a member's first Word upload is the first use.
- That the site's availability is sampled outside S1 to S5 of app, or on admin.quillmd.com or a co-tenant: there D401
  (b) rests on how each phase acts and on its own checks after it has acted (https-vhost polls /health/ up to 30 times
  after its reload and passes at the first good answer). /health/ runs SELECT 1 alone, so a wait for a table's lock in
  migrate delays members' reads without a sample other than 200.
- What the first weekly check finds (read from its SecurityEvents after the act); the first daily run's counts are
  declared from the read-only reading before the commit (above), which pre_app_r1.sh reads again before app, stopping at
  any other orphan, unexpected, missing or past-retention count, and at a file no row names that is under an hour old (the
  names to hash are read and printed, not gated); a file written after that second reading and an hour old, unnamed, by
  the run, or a name aged past 30 days by then, would change the run by its own count (found by post_check_r1.sh and
  named in the report).
- That the copy routine of RELEASE-1-SPEC 1.3 is in place, or that this act can be restored from a copy: 1.3 recommends
  the routine before this install so that its safety copy follows it; this act takes no copy of live instead (D409, D419
  (2); Rollback). Copies of live made earlier stay, unencrypted: the 2026-11-24 rehearsal's
  (lead/rehearsal/live/live-20261124T151549Z.dump, 0600, outside the repository, session rows included), entered in
  release/PACKAGE-TODO.md (A2; no copies register exists yet: document 03's Appendix L is still a blank form), its
  destruction the owner's with counsel (D409, class d); and what document 01's R-08 already lists (action 7), untouched
  by this act: the 49 dumps - the 23 in the receipts directory among them, the ones put to the owner (D419 (1)), and the
  nine of those made after 2026-11-20 00:20Z, which wait for counsel (section 9) - and the 18 cptg_* databases restored
  from live dumps on the shared test server.
- That release 1b's items are installed: F1's wiring (encryption off), A10 (least-privilege database roles), A12 (the
  weekly scan), D5 (the malware scan), E4 (a neutral document title). Doctors sign in with a password alone (D2); D22 is
  not applied, so today's staff-set member passwords are not flagged for a change (a separate step when the owner says,
  D419 (5)).
- That RELEASE-1-SPEC A9 (an asset inventory written into the receipts) is in this installer: the drafter found it in no
  phase.
- That the own-folder predicate covers a hard link or a copy made by someone with write access to the store (it covers
  a crafted or corrupted row and symbolic links); that another address of an IPv6 /64 whose only sign-ins predate
  release 1 is a known address before that /64's first release-1 sign-in (INTEGRATION-TODO 23 and 37).
- That every session made on the older web in the seconds between S2's end and the end of S5's drain is ended: it keeps
  its row (it signs nobody in on release 1), and an app's own S3 or S4 undo returns the older web without ending
  sessions again (ops/INSTALL.md, Known limits).
- That a member's activity during the act can be told from the act's rows by post_check_r1.sh alone: it lists audit
  events only.
- The recorded lows of D407, D408, D410, D414, D415 and D418, and spec section 7's open list (the shared host, local
  processes trusted, the live cluster's superuser role, records on the data's box, swap, the AI vendor's retention and
  BAA, the switch-back window, the paperwork).
- Past the known limits written in cpt-studio/ARCHITECTURE.md, API.md and ops/INSTALL.md, and in the refutation
  dispositions.

## ePHI security evaluation (RELEASE-1-SPEC 6.1; register A28; document 03, 03.8.3)

<!-- Drafted 2026-11-25 by a read-only agent that read code, the release package and the programme's records only, then
edited by the lead (session 738699b2), which had read the documents of 2026-11-20 (document 01, section 9; D352, D353),
and, for the package review's findings, by an editing agent of that session (2026-11-25, 15:30-15:51Z).
So document 03, 03.8.3's condition on an agent's draft (no access to PHI; a draft policy, not yet adopted) is not
claimed for this section. No agent signs it: what the security official accepted of its residual risk is below (D417,
D419). -->

**What changes, and its effect on confidentiality, integrity and availability.** Confidentiality gains: the console
behind a second factor on the admin host only, no automated operator and ops-agent's grant revoked, operators shown less
by default, idle sign-out and capped sessions, `__Host-` cookies, no release in /health/, nothing spooled to disk at the
edge (shown on the rehearsal; on live not claimed, above), a database that logs no statement text and, until the host's
next systemd daemon-reload (What is not claimed), does not swap, Word files converted with no network, secret or file
access. It adds: edge logs on the shared host, where 6ab8e503a400's stage keeps none (access_log off, error_log
/dev/null crit) - an access log with the path without its query string, the client's address, the request id, the
session reference and the browser string, and nginx's error log, with the client's address, whose request line, upstream
address and Referer can carry a query string (ops/INSTALL.md, Known limits; today's parameters hold no patient detail);
ids-only copies of the container logs a deploy removes (a running container's own log is not filtered: an error's text
or a query string can reach it; FLOW-12, outside release 1); and access records (ids and counts, never content). It
makes no copy of the database (D409). Integrity gains: a record of every read,
written before the answer (fail closed) - a page's polls within 60 s of a recorded read write none, and the same list read
again within 60 s is counted on the first read's record;
the weekly sha256 check of stored files; tested disposal and return tools (not run). It changes: the first daily
maintenance removes the files no row names (the declared count, above; any other stops the act before app) and rewrites
unmatched sign-in names older than 30 days to keyed hashes; the migrations only add.
Availability gains: front-door limits, a slowdown instead of a lockout, per-person limits. It costs: everyone signed out
once, a coding pause from S2 to S4 (60 minutes at most on the declared path; longer in the layout rollback-app
resolves), the console closed until the owner enrols; a converter that is down fails Word rounds as busy; a Word file over
E1's size limits (D419 (4)) or of the shapes E2 refuses is refused, and a document imported into one is taken out with its text (neither among D419's
points: his answer stands with the owner decisions above; the D358 line); limits sized for 20 people behind one address.

**The ePHI stores and flows touched (named, never their contents).** Stores: the cptstudio database in cpt-studio-db
(volume cpt-studio-pg: the schema extended, every session deleted, two settings); the files volume cpt-studio-files
(read by the weekly check; the files no row names removed by the daily run, the declared count); the new volume
cpt-studio-convert (the socket only) and the converter's /tmp tmpfs (Word files in memory while converted); nginx's
request and response buffers (memory); /var/log/nginx/cpt-studio-access.log and cpt-studio-error.log;
/var/log/cpt-studio/ (ids-only container log copies, one-shot journals); the receipts directory
/home/claude/cpt-studio-install-20261023 (this act's receipts: ids, counts and digests, never a document; the directory
also keeps, untouched by this act, the 23 pre-app dumps of earlier installs, pre-app-*.dump, 0600: unencrypted copies of
the whole live database, session rows and password hashes included, nine of them made after 2026-11-20 00:20Z; document
01, R-08 and section 9; D419 (1)); the pre-app check's log (counts and names of migrations only); the live check's
evidence folder (statuses and header names only). The live stores, and those nine dumps, may hold the documents of
2026-11-20 (document 01, section 9: the host is treated as possibly holding PHI until the documents are determined not
to be PHI or are disposed of). Flows: the browser to nginx to the web on both hosts; the web and the worker to the
database; the worker to the converter over a socket with no network; the worker's coding sends to Anthropic, unchanged
in endpoint, model, effort and figures, the PDF of a Word document now made by the converter after its package is
cleaned; the live check's read of its practice's list and of the walk's own synthetic document there (D361: never
another document); the installer's probes (no PHI); the pre-app check's read-only queries (counts and migration names).

**The access changes.** ops-agent revoked (OperatorRevocation; its sessions ended; SecurityEvent operator.revoked); agent
accounts refused as operators by the code whatever their grants; the operator's second factor (a security key or
passkey bound to admin.quillmd.com, a step-up after 5 minutes for privilege changes, a single-use setup code of 30
minutes stored as its sha256 only, 10 recovery codes); the console on the admin host only, cpt.quillmd.com/ops/ answering
404; every session ended once at the switch; members' idle limits, passwords staff set from this release on that must be
changed and expire (today's are not flagged: D22), sign out everywhere, a practice owner able to turn a person off. No
account created, no role or membership changed.

**New subcontractors:** none. No vendor's terms, retention, model, endpoint or fallback change; the BAA with Anthropic
remains the owner's open contact (D401 (c)).

**The policy sections affected.** Document 02: Policies 1 (access control), 2 (unique IDs), 3 (authentication, passwords
and MFA), 4 (automatic logoff), 5 (audit logging and activity review), 6 (encryption at rest and in transit), 7
(integrity), 8 (workstation and device use: the console's neutral titles), 9 (media and copies) and 10 (AI agent
operations), and Appendix A (the TLS check at every install). Document 03: 03.1.5 (containment), 03.1.6 (incident
reports' counts, in part), 03.1.8 (detection, in part), 03.2.9 (the read and token-count records), 03.3.5 (disaster
recovery: the verification commands), 03.3.6 (emergency access), 03.4.3 (authorization and supervision), 03.4.5
(termination), 03.4.6 (changes to practice members), 03.4.8 (AI agent sessions and automated accounts), 03.5.5
(malicious software), 03.5.7 (password management), 03.7.10 (earlier vendors), 03.8.2 (the register's first entry:
ops-agent's grant decided again), 03.8.3 (this entry), 03.10.3 (access: the record bundle), 03.11.2, 03.11.3 and 03.11.7
(return, closure and destruction: the tools, none run by this act), the summary tables of Parts 1, 4, 10 and 11, and
Appendices A.4 and G. Their [PLANNED - release 1] markers for what this act installs (not D5's in 03.1.5 and 03.5.5, nor
E4's in Policy 1 and 03.7.5, nor A12's in 03.8.5) are updated in the same change, that is with the act's report, once
its checks have passed, in the paperwork drafts outside the repository
(/home/claude/cpt-studio-hipaa-20261124/paperwork/, documents 02 and 03); nothing is published.

**The risks added or removed** (document 01's register): reduced - R-03 (operator credential or session), R-04 (a
member's account), R-05 in part (edge temporary files; database swap until the host's next systemd daemon-reload; F1
off), R-09 (who read what), R-13 (emergency aids), R-14 (floods and lockouts), R-15 and R-16 (the sealed converter),
R-17 (agent and operator access), R-19 (return and destroy tools exist), R-20 in part (the database's own log and the
console's lists; error text in the application's logs stays: FLOW-12 and E4 not installed), R-21 (idle sessions), R-22
(the weekly check), R-23 in part (cookies; TLS on the shared listener not in force), R-25 (no switch-back into an
earlier vendor's live mode; the pair it returns to still sends to Anthropic: R-01). Added or not reduced - R-08
(unchanged: this act makes no copy of live; the 23 dumps of earlier installs
above, nine of them made after 2026-11-20 00:20Z, and the 2026-11-24 rehearsal copy stay for the owner and counsel,
D402, D409, D419 (1)); R-06, R-10, R-12 (the shared host, no outside alerting, no backup: the new server's; R-12 also
added to by this act: no pre-app dump, which each upgrade since 2026-10-27 kept, D409, D419 (2)); R-01, R-28 (the AI
vendor: contract, retention, model and endpoint unchanged, still no BAA; D4's audit row before every token count is the
one change to them); R-18 (the 2026-11-20 documents: unchanged, the owner's to decide about with counsel, no decision
recorded); a switch-back to 6ab8e503a400 brings
back every weakness release 1 closes for as long as it runs; the console now depends on one operator's authenticators
(R-13).

**The residual risk** is the list above, the spec's section 7 and "What is not claimed". Of it Kasra Rayat (the security
official, D411) accepted in words only what he was shown: the eight items of D417 and the five points of D419 (E2's Word
refusals and the imported document it takes out, costs named above, stand as the owner decisions record his answer, D422). D417's
were put to him in plain words on 2026-11-25 at 07:08Z and accepted at 07:46Z (his message carries no date; the record
dates it) as "ia ccept thye risk dont worry we are in test phase we got no real customer keep that gap ill fix it
later": (1) the shared server until the new one, with no off-site backup and no outside alerts; (2) stored files not
encrypted and uploads not scanned until release 1b; (3) doctors signing in with a password only; (4) the Anthropic BAA
still his own; (5) the 2026-11-20 documents and the one kept rehearsal copy staying until he decides with counsel; (6) a
switch-back bringing the old weaknesses back for as
long as it runs; (7) the console depending on one passkey and the recovery codes; (8) a handful of low findings
recorded, not repaired. D419's were put to him on 2026-11-25 at 09:42Z and answered "yes" at 15:27:28Z: (1) the 23
earlier full copies of the live database in the install folder, not encrypted, nine of them made after 2026-11-20 00:20Z
and so perhaps holding that day's documents, untouched by this act, his to decide about with counsel (class d); (2) no
copy of live taken before this install, so none to restore if data itself were lost (he was told that the install only
adds tables and settings and that the old version can be switched back: what else it changes, and when no switch-back
is left, are in S2, the first maintenance run and Rollback, above); (3) no automated account able to
sign in to the admin console after the install, so the live check proves the console's gate and opens no page as an
operator, and he opens one page himself after he enrols (D10, class b); (4) a Word file that unpacks to more than 64
MiB, or has one part over 32 MiB, refused, where 6ab8e503a400 accepted up to 512 MiB (class b); (5) D22 not part of this
install, a separate step when he says. Every other risk of the three is recorded by the session, not accepted by him in
words: among them the rest of the spec's section 7 (the root-equal docker group and the unencrypted disk and swap of
item 1; items 2, 3, 4, 5, 9 and, but for the copies of D419 (1), 10; the vendor's 30-day retention of item 7) and, of
"What is not claimed", the no-swap limits, the TLS policy not in force, what was not rehearsed, A9, A10, A12 and E4, the
sessions of S2 to S5, and D418's three lows, found after he was shown the eight. So what RELEASE-1-SPEC 6.1 and
document 03, 03.8.3 ask for - the residual risk, accepted and dated by the security official - is met for those items
alone: this section's text was not put to him, and the approval of the evaluation that D411's record gives him is not
recorded.

**The register's other rows** (document 01; this act neither adds nor closes them, and each stays as the register has
it): R-07 (AI agent sessions read PHI and pass it to an AI service without a BAA: High; document 01's section 9 applies
it to this host today, beside R-05, R-06 and R-08) - this act does its ops-agent part only (C3, A6, A11 and
revoke-ops-agent) and is itself run by such a session on that host; R-11 (no incident response or breach notification
process: High, open with the 2026-11-20 documents) - D4's record and A13's kept logs are its only parts here; R-24, R-29
and R-30, touched only by A4 and B7 (the TLS list, versions hidden), item D2's return tools and this entry with its
HIPAA impact line; R-02, R-26 and R-27, untouched. R-07 and R-11 were not among the points the security official
answered (D417, D419) and are not part of his acceptance above.

## Stop conditions

- Any phase exiting non-zero; pre_app_r1.sh ending PRE-APP STOP. A read-only step that stopped is judged; when what
  stopped it lies outside this release and is over (a co-tenant's deploy or restart, an answer that was lost), it runs
  again under a new TAG: preflight; pre_app_r1.sh, but not over a moved row or another count (below); verify, after a
  preflight (TAG), since it compares with the newest one. Both manage acts need a verify that ended exit 0 (act_r1.sh):
  a verify that stops on CPT Studio's own state is decided as a live-check failure is (the last condition), and no manage act follows it; until a verify passes, or a new declaration is in, the console stays closed.
- A receipt or reading that differs from this declaration: a difference not declared here is THE finding, whatever its
  explanation - apart, in a reading after PRE-APP PASS, from a member's own activity, identified from the audit events
  and release 1's tables and named in the report. Before PRE-APP PASS nothing is exempt: a row moved since the Baseline
  reading is a stop, before any phase when the reading taken again before preflight (above) shows it, and after that at
  pre_app_r1.sh (one upload, decision, export or console view of a record ends it PRE-APP STOP, and a further run with
  TAG cannot pass). The act then goes on only under a new declaration with the baseline read again (once db has run, its
  three db-phase rows read terse, panic and 0, and their three lines leave the expected deltas).
- pre_app_r1.sh reading any pending migration set other than exactly studio.0017_r1_security and
  studio.0018_r1_availability, or migrate in app applying anything else.
- pre_app_r1.sh reading an orphan, unexpected, missing or past-retention count other than the one declared, or a file no
  row names that is under an hour old (it ends PRE-APP STOP): removing a stored document is the owner's (class d), so he is asked
  before any stored file is removed - his yes goes on only under a new declaration holding that count - and the 2026-11-20
  documents are his to decide about with counsel, no decision recorded (D402, D409).
- An encounter's stored state changing in app.
- The db receipt's memory state anything but `updated` (on a second run of db, after a failure that followed its docker
  update, `as installed` with its cgroup reading memory.swap.max 0 is right, as `replaced` or `present` is on a second run
  of converter; a start of the database container less than 7 days before the
  db phase - a host reset, say - would make it `skipped`, and verify would then refuse the swap): decided under a new
  declaration.
- Any sample other than 200 in app's availability record (S1 to the end of S5); or an https-vhost receipt whose
  details.observations is not one entry, attempt 0, status 200 (a later attempt is an outage the phase polled through):
  judged before the next phase.
- The citation not success in both views.
- A held declaration found.
- Preflight BLOCK (the health check), or the installer's preflight refusing. Every run of the health check from this
  declaration's commit to the act's report is report-only: none of its auto-fixes is run (no restart of a QuillMD
  container, no build-cache prune), as D329 (5) declined its prune. A QuillMD container it reads unhealthy, or a host it
  reads 502, 503 or 504, is a stop, decided by hand; a yellow flag alone (disk, memory, load, swap) is not.
- The door's ceiling reached.
- The owner is waited for in one place only, his own enrolment (D422; the removal of a stored file stays his, class d, above: the
  act stops for it): the act runs at its hour, and app starts whether or not
  he is there (from S3 the console is closed until he enrols). issue-enrolment is run once he says he is ready (told at
  2026-11-25T17:33:15Z to write "ready"; he needs the server over SSH and admin.quillmd.com open), since the setup code lives
  30 minutes. While he is not there, the live check runs after
  revoke-ops-agent, and post_check_r1.sh after it, which then ends exit 1 on exactly the two rows the setup code makes
  (r1_table studio_onetimetoken 0 where the table reads 1, r1_table studio_securityevent 5 where it reads 6) and is judged
  by them; any other difference, but a member's own activity (above) and the rows of a second live check (its section), is a finding.
  post_check_r1.sh runs again after issue-enrolment, before he reads the code: exit 0, unless the worker's next daily run (due 24
  hours after the first) came before it. Then it exits 1 on the later runs' own records alone - r1_table studio_securityevent 6
  plus 2 per later daily run and 1 per later weekly check, r1_table studio_ratewindow 0 from the second later daily run (which
  prunes the live check's three), and the maintenance read, which takes the first run's two records alone - and is judged by
  them, as a first post-check run that late is. A host daemon-reload since (db_cgroup memory.swap.max max: What is not claimed)
  is decided under a new declaration, as there. Neither holds back his enrolment. When app has not
  started within 15 minutes of PRE-APP PASS, preflight and pre_app_r1.sh run again first, each under a new TAG: a co-tenant
  deploy since the newest preflight spends app's one attempt (the installer compares with it only after migrate).
- The end of the announced window (Wednesday 2026-11-25, 19:00-20:00Z): no changing phase up to app starts after 20:00Z (the act then
  ends and a new declaration names another hour), but for switch-back and rollback-app, the incident paths, which neither the
  hour nor his absence holds back. Once app has ended exit 0, the phases after it are completed whatever the hour, never left
  half done - issue-enrolment when the owner is there, as above: one that starts or ends after 20:00Z is not a difference. Until
  he comes the act's report is written on the first post-check as judged, naming issue-enrolment as waiting and the console as
  closed; it is run under this declaration when he comes, but never after a switch-back (act_r1.sh refuses it).
- What the security official was shown (D417's eight items and D419's five points, in the evaluation, and E2's two Word losses,
  class b, the D358 line: D422) not accepted by him, on the record, before the commit of this amended text (E2's at 17:30:15Z,
  after 2e71431b568c and before any phase).
- quillmd.com, www.quillmd.com, app.quillmd.com or pro.quillmd.com changing its answer or certificate, or
  app.quillmd.com's health; admin.quillmd.com answering anything but the console's 302 to /login/ with the cpt-studio
  certificate.
- A TLS finding is recorded and reported, never a stop (D27).
- The live check failing, or the post-check finding a difference: judged, then reported. A defect found there is fixed
  and installed under a new declaration, or the site is switched back. It is never patched in place.
