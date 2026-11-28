# Prospective declaration: CPT Studio release 2 (816045c72644 to 2008ffddc946), the speed release, installed blue/green with the site kept online: the Word converter replaced by release 2's, the front door republished in place with the search counted as a read, migrations 0019 to 0021 (indexes only), the web's four processes in 1 GiB, nobody signed out

<!-- Drafted 2026-11-27 by the release package builder (a subagent of the lead's session) from RELEASE-2-SPEC section 9,
cpt-studio/ops/install.py and ops/INSTALL.md at the integration head ccb350d0b04e7448c178e9ee0bc263cc7190a535, release 1's
committed declaration (docs/foundation/mutations/20261125-cpt-studio-release-1-install.md), its package and the owner's
recorded words. Every value known only at the act is a placeholder: an upper-case name in double braces, each listed in
PLACEHOLDERS.md with who fills it and from what read; act_r2.sh refuses this file while one is left. The comments name the
functions each claim was read from, for checking. Values read at ccb350d0b, the integration head when this was drafted
(history: B is a680d837b since D-R2-60), are given in comments as references only: the
revision is the merge commit of PR #1537, which does not exist yet. Repaired after the package review's round 1 under the
lead's decisions (/home/claude/cpt-r2-20261125/release/PKG-ROUND1-DECISIONS.md, outside the repository, recorded as D-R2-53
and D-R2-55; each finding's answer in release/ANSWERS-R1.md), after its round 2 under the lead's decisions R2P-1 to
R2P-7 (/home/claude/cpt-r2-20261125/release/PKG-ROUND2-DECISIONS.md, recorded as D-R2-55; release/ANSWERS-R2.md), and after
its round 3 under the lead's decisions R3P-1 to R3P-6 (/home/claude/cpt-r2-20261125/release/PKG-ROUND3-DECISIONS.md,
recorded as D-R2-55; release/ANSWERS-R3.md), and after its round 4 under the lead's decisions R4P-1 to R4P-3
(/home/claude/cpt-r2-20261125/release/PKG-ROUND4-DECISIONS.md, which D-R2-57 records with the review's end;
release/ANSWERS-R4.md). D-R2-54 is not the package's: it is the B measurement's dispositions. Finalized on 2026-11-28
(release/FINALIZE-NOTES.md): B is a680d837b0d1e9895683cb1eb27b3dc59a1af03e, B's third session (laneM/b3: the B
measurement's D-R2-54 (1) and D-R2-60), D-R2-58 to D-R2-60 are cited where they bear, the second rehearsal's values and
its finding G4 are carried, and every value that existed then is filled. Filled on 2026-11-28 (the
lead's declaration fill: a subagent of session 799ffbc5, which neither stages nor commits) from the reads PLACEHOLDERS.md
names: PR #1537's merge commit 2008ffddc946 and its parents, both citations in both views, b_stands_r2.sh, the final
suite's second run (the first disclosed), the speed gate, the held check, the stage digests (N9's command, its positive
control on 816045c72644 giving e31ce5801a7b... and bbd482895d79...), the diff counts and the byte-identity reading, the
declared baseline of 09:40:41Z with the co-tenant and walk readings, the container, image and ingress readings of
2026-11-28T09:56:41Z, the owner's one message and his reply read verbatim from the session transcript, and 0feb039be (D-R2-55
completed, D-R2-61) under Authority, D-R2-61 cited where the rehearsal's narrowing and the lead's ruling Q10's B
revision bear. -->

HIPAA impact: none: synthetic-only unchanged

<!-- RELEASE-2-SPEC 9.3: the line, verbatim, as release 1's. The ePHI security evaluation (register A28) is its own
section below, before the stop conditions. -->

Authority: the owner's directions recorded verbatim in DECISIONS.md (D399, D400, D401, D422, D425, D433) and the
session's records around them (D421, D424, D427, D428, D434: the session's records, not the owner's words), with this
programme's interpretation, in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (their sections) and RULINGS.md rows;
the build specification is /home/claude/cpt-r2-20261125/design/RELEASE-2-SPEC.md (outside
the repository; its section 9 is this install, its section 10 the session's decisions D-R2-1 to D-R2-61, recorded in the
tracked rulings by 2d28fc8d5 (D-R2-1 to D-R2-53), 2e34942ea (D-R2-54, the B measurement's dispositions), a680d837b
(D-R2-55 to D-R2-57) and 23f813345 (D-R2-58 to D-R2-60), each docs only on the integration branch, and 0feb039be
(D-R2-55 completed, and D-R2-61), docs only, the first commit of this declaration's own branch (D-R2-61 (4)), each
copied verbatim from section 10 - D-R2-55's entry as a680d837b recorded it holding R3P-1's count alone, so its other
citations below stand on 0feb039be (2026-11-28T08:43:58Z, branch docs/cpt-r2-install-declaration-20261128, its parent the revision: D-R2-55's entry completed with round 1's Q2, Q3, Q9, Q11, Q12 and owner-9, round 2's R2P-1 to R2P-7 and round 3's R3P-1 to R3P-6, its first entry kept as written; docs/foundation/RULINGS.md and docs/foundation/rulings/2026-10-23-cpt-studio-gi.md alone, 52 lines added, 0 removed); D-R2-53 and D-R2-55 are the lead's
rulings on this package's first three reviews, the "lead's ruling Qn", "R2Pn" and "R3Pn" cited below, D-R2-57 its
fourth review's end with the rulings R4P-1 to R4P-3 cited below, D-R2-56 the standby's idle stage as built, and D-R2-54
the B measurement's dispositions - its rows accepted in the open, each within a written bound, told to the owner in the
install message: D-R2-54 (3) -, D-R2-58 release 1's switch-back checks on release 2's schema, run before B, D-R2-59 the
reading of "no other work on the host" during B, and D-R2-60 B's third session (laneM/b3, a680d837b) with its two rows
outside D-R2-54's list, accepted post hoc by the lead and told to the owner with a stop, and D-R2-61 the rehearsal's
decisions RH-1 to RH-7 - its tooling repairs recorded as made, section 9.1 item 3 narrowed with a replacement for
each (the image's suites, the bench's browser flows, the held-document pause: RH-3 to RH-5), B's revision for the
lead's ruling Q10 a680d837b, and these rulings as this branch's first commit):

- D399: "ive seen in Gi when i open the doc tabs it open slow and al ittle bit laggy my question is let say we get 1000
  customer to use our web site despite of vps is our websitre and admin secure enought against the attacks or any
  hidding login to intruopt us and also what if 1000 customer uplaod more than 50 per day it would be 50000 fiels per day
  i want you to audit and check every aspect of this situation ... this is high proirty for me ...". Interpretation (a): the
  report-only audit of 2026-11-23/24 (REPORT section 4, its Tier 1 items); release 2 is its speed half: the GI document
  tabs, the paged lists and the web process (audit PERF-1, PERF-2, PERF-5 to PERF-12, SCALE-6). Interpretation (b), the
  rest of his message as recorded: the doctor-app restyle and the orthopedic test are removed from the priorities until he
  says otherwise.
- D400: "... which one of this we can fix adn take care veen if we want to move for another vps ...". Interpretation:
  the code and installer fixes travel with the releases, "the GI speed fixes, paging + indexes" among them; the host's
  own items wait for the new server.
- D401: "i already conatcting with claude for baa so strat the work waht very you needrun as much as any parrlerl or job
  you need" and "make sure site is online dont turn if the live". Interpretation (a): the approved plan runs - release 1,
  then the GI speed release, this one; (b): the live site stays online throughout: blue/green through the ruled-act
  door, never a stop; (c): no session makes an agreement, key or payment.
- D421 and D422, the Word losses: release 1's E2 refused a file damaged inside or built in a way Word does not produce,
  and removed a document inserted whole into a Word file (w:altChunk) with no notice; both put to the owner at 2026-11-25T16:15:09Z with the recommendation, as D421 summarises it (its summary, not the
  words put to him), yes for that day and the second one fixed in the next release (such a file refused with a message,
  nothing dropped silently) (D421); answered at 17:30:15Z: "Stop asking my Yes just do what ever we need it to have to do"
  (D422), read as yes to both losses and as the direction to run release 1's install at its hour without waiting for a
  further word from him (its record: "The session stops asking yes/no questions for this install"; RULINGS.md,
  OWNER-DECISION: "run release 1's install without a further yes from the owner"); not read as permission to delete data,
  to spend or agree anything, or to make or hand out a key. D424 recorded "the E2 w:altChunk refusal in the next release"
  as the session's own remaining item: this release. Applying D422 to release 2 - no yes or no asked, its new Word
  refusals and its hour told, not asked - is the session's reading (D427, D428: RULINGS.md rows RECORDED, not
  OWNER-DECISION); no word of the owner's since D422 extends it. The standard for release 2's class-b losses is therefore
  the recorded one, D428 (C10: told once, not asked), and this declaration cites D428 for it.
- D425: "there is no serious data base to move you can delete it if you wnat all that data was test and syntetic" (in
  reply to the list of what stays his). Read for this act as: live's database and files stay where they are and nothing
  is moved; this act deletes no copy and moves nothing (the kept set stays his, or counsel's, class d).
- D428 (a session record: told, not asked, at 2026-11-26T00:01:51Z, in these words - the standard C10 names): "Some
  Word files are now refused, with a sentence asking for a PDF: a file with another document inserted in it; a file that
  links to outside documents; a file
  with an embedded object that has no picture. Release 1 coded these files with that part missing and didn't say so. The
  cost is that such files no longer go through at all. Word files that are already uploaded get the same check if
  they're coded again." R2-30's refusal fallback, PICT and SVG previews and a Word file whose package is not in the one
  canonical form the gate admits were told to him the same way (once, not asked, as D428 was), in the one message that also
  told him the install hour first told (OWNER_TOLD_HOURS names each hour told) and B's residuals - D-R2-54's sentence
  and D-R2-60's two rows with their numbers (the lead's rulings Q2 and R3P-2, D-R2-55; D-R2-54 (3); D-R2-60), at
  2026-11-28T09:10:54.069Z, in these words (D-R2-35, D-R2-45, D-R2-46; section 11 of the specification) - the message's
  item 1, verbatim from the session transcript, each of its lines after the "> " that marks the quotation:

  > **1. Some Word files will now be refused instead of coded.**
  > - **What gets refused:** some Word files that release 1 coded completely, and some files that Word 2007 itself writes. The doctor is asked to save the file as a PDF and upload that instead.
  > - **Which files:**
  >   - files with PICT or SVG preview pictures
  >   - Word 2007 files carrying "[trash]" entries
  >   - documents built from scratch by Microsoft's Open XML SDK
  >   - pandoc files made with a reference document
  >   - files from the docx npm package with multi-word font names
  >   - files with archive comments or forced-zip64 headers
  > - **Not tested:** other EHR exporters, Google Docs, Pages and WPS.
  > - **Already uploaded:** Word files release 1 coded completely are refused if they're coded again after the install.
  > - **The doctor's message isn't accurate for these files.** It says: "This Word file has another document inserted in it, which cannot be read here. Open it in Word, save it as a PDF and upload the PDF." Most of these files have no inserted document.
  > - **This is reversible.** Each kind of file can be allowed again later, once we have a real sample to test.
  > - **A separate case:** a Word file where a field that pulls in another file sits inside a kept field's instructions is now refused with the same message. For one such shape, release 1 was already silently dropping words on the live server's LibreOffice. Some other field types release 1 coded completely.

  His reply by this declaration's commit: "no need to test and round for another speed test ill try it on live and let you know just focus to finish the jobs asap i gotta test whole the thigns audit agents speed dictation everything hopefully soon" (2026-11-28T09:38:19.903Z, verbatim from the session transcript), recorded as his words and read as neither an acceptance nor a refusal (the session's record D457 reads it as no stop and no re-measure); and, at 2026-11-28T09:43:58.588Z, verbatim from the session transcript: "Release 3 is my high priority just give me a relastic time once you told me it takes saturaday now you say monday or tuesday what is the relasitc time?" (about release 3's timing, answered in the session; recorded as his words and read as neither an acceptance nor a refusal). Unlike D428's files,
  release 1 codes the canonical gate's files completely, and some are files Word 2007 itself writes; for those the doctor
  is shown the inserted-document sentence, which is not true of them (review owner-2): the words told him say so.
- D433: "i approve do it but you dont have to do run full like just test 5 files as long as it keep the quality we cang
  change it and i give you permission for that". D434: the paid test on five synthetic GI documents, the same codes,
  units and modifiers at effort "high" as at "max", 83.8% less cost: the coder's effort becomes "high" in this release
  (R2-33, D-R2-38). The change is named here, and below, as the one change to a coding request.

The owner's classes this act touches. (a) No product decision without precedent: the speed items are in the list the
session gave him on D400's question (then "awaiting his go") and carry out his go, D401 (a), and the look keeps D393's
approved design but for the audit's approved fixes. (b) An accepted-capability change, named under "What the owner and
members see" below: some Word files that convert today are refused with a message; told once, not asked, by the recorded
standard D428 (C10): D428's message and the one message of 2026-11-28T09:10:54.069Z; his reply by this declaration's
commit: "no need to test and round for another speed test ill try it on live and let you know just focus to finish the jobs asap i gotta test whole the thigns audit agents speed dictation everything hopefully soon" (2026-11-28T09:38:19.903Z, verbatim from the session transcript), recorded as his words and read as neither an acceptance nor a refusal (the session's record D457 reads it as no stop and no re-measure); and, at 2026-11-28T09:43:58.588Z, verbatim from the session transcript: "Release 3 is my high priority just give me a relastic time once you told me it takes saturaday now you say monday or tuesday what is the relasitc time?" (about release 3's timing, answered in the session; recorded as his words and read as neither an acceptance nor a refusal). (c) One acceptance only his eyes can give, asked after the install, after the live check,
the post-check and the hour-after reading, and never after a switch-back (below; the lead's ruling R3P-6). (d) No money, key or
deletion of data: no paid request is made by the act, no key is made or
handed out, and nothing is deleted but what the scheduled maintenance of release 1 removes on its own schedule (below);
D425's kept set is untouched.

It stands on the standing directions this install keeps:
- D358 as amended by D433 and D434: no coding instruction, model, figure, decision rule or list-state rule changes. The
  coder's prompts, client, answer reading, pricing and credentials loader (studio/fable/ but document.py and
  docx_package.py), studio/decisions.py, the physician report's code and fonts and the reference data are byte-identical
  (the command below). The one change to a coding request is its effort: output_config.effort "high" instead of "max"
  (R2-33; the request otherwise byte-identical to release 1's, pinned by R2-3's tests). studio/state.py changes by
  extraction only, proved by its tests (D-R2-16): no stored list state is expected to change at S6. The Word path
  (studio/fable/document.py, docx_package.py and studio/converter_server.py) refuses what is named below and changes
  nothing else in a document it accepts but R2-30's QUOTE shell, which puts a removed field's words back in the PDF, and
  R2-29 step 5's kept picture, an id only expat finds (8,055 of 8,055 random documents that needed neither a refusal nor
  R2-30's edit byte-identical; 21 real files coded unchanged; the 7.4 corpus: 309 shapes, 771 packages (B refusing 156 shapes before any conversion), 769 converted to a PDF - the two that are not, shape 093's base and r1 packages (E07, a header relationship with TargetMode="internal"), failed the same way in lane D's round 4 - and 0 accepted shapes losing a token: step 6 of the rehearsal on the merge commit, re-run after its M1 repair, its gate line at 2026-11-28T10:06:52Z (rehearsal-3/logs/steps/step-06-corpus-rerun.out; rehearsal-3/corpus/compare.txt, sha256 first 16 99cb5f8acb4489d8, equal to lane D's round-4 compare-7.4.txt but for its temporary folder names and shape 180's DATE field, which prints the day of the conversion)).
  <!-- verified at ccb350d0b: git diff --quiet 816045c72644 HEAD with the byte-identity pathspecs exits 0; the same on
  cpt-studio/studio/fable/document.py exits 1; studio/state.py 24 insertions, 5 deletions; settings.CODING_EFFORT 'high';
  install.CODING_EFFORT 'high' (ops/install.py:232) -->
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved):
  QuillMD's vhost is not written (it stays the pinned after state); quillmd-cpt is replaced in place twice, each with one
  graceful, host-global reload (https-vhost, then app's S3); the new map entry is cpt_*-scoped; every QuillMD host keeps
  its answer and its certificate.
- D396's coupling invariant: every HTTPS stage of this revision names admin.quillmd.com on 443, so the quillmd vhost stays
  b3ab66023547... and admin.quillmd.com stays the console's.
- D360's install conditions: no unresolved critical or high finding in the shipped code (the integrated pass's last
  round found test-guard gaps, recorded, D-R2-51, below); every suite green; CI green on the merged commit; this
  declaration committed before the act; the rehearsal passed (9.1 item 3 as D-R2-61 narrows it, on the test instance, synthetic data only, as
  release 1's under D409); preflight not BLOCK; the act only through the door; a check on the live site afterwards; a
  report either way.
- D401 (b) and (c): no phase stops the site (the converter is replaced beside the running site, both nginx changes are
  graceful reloads, app is the blue/green switch), and no session makes an agreement, key or payment.

The integration and deployment owner is session `738699b2` (and its successor session `799ffbc5` since the host restart
of 2026-11-26, D436). CPT Studio stays standalone and synthetic-only (`SYNTHETIC_ONLY = True` unchanged). No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it: no phase sends anything to a
vendor (every one-shot runs with the coder disabled), and the cert phase orders nothing unless the lineage is due. No
account, workspace, membership or password is created or changed, and no session is ended.

Revision to install: `2008ffddc946be142e8b856b4003e4c4959b1dd7`, the merge commit of PR #1537 (head `23f813345075b475bf6ce4325104449bddc001c5`; its tree equals the
head's: `git diff --quiet 23f813345075b475bf6ce4325104449bddc001c5 2008ffddc946be142e8b856b4003e4c4959b1dd7` exits 0; its first parent, `9bb88a4ab2b3aaa940d0a1a639439d5d84cf8b49`, is
main as it stood). Image tag cpt-studio:`2008ffddc946`. Its citation, on the revision: `CI 46127033034, cpt-studio 46127033085 and secrets-scan 46127032997, all success, read by commit (the full sha) and by branch (main, filtered to that sha) at 2026-11-28T09:57:05Z, the same three runs in both views; the revision holds no other workflow`. The PR
head's citation: `CI 46121093248, cpt-studio 46121093274 and secrets-scan 46121093263, all success, read by commit (the full sha) and by branch (feat/cpt-r2-integration-20261126, filtered to that sha) at 2026-11-28T09:57:05Z, the same three runs in both views`.

It replaces the live revision 816045c7264481bc6956285e1ca89991b9fcec2f (image cpt-studio:816045c72644, id
sha256:4c81cc9292b6b5c138bbc3c032db7cb80a7816cc60a01f985512d3173a7ccd30, its web on 127.0.0.1:9150 since release 1's
switch on 2026-11-25, its converter started from that image the same day), installed under
docs/foundation/mutations/20261125-cpt-studio-release-1-install.md (PRs #1527 and #1528; its report #1529). That image is
kept as the rollback image (switch-back). That declaration and its receipts stay as they are.
<!-- release 1's receipts in /home/claude/cpt-studio-install-20261023: image-20261125T190102565013Z.json (the image id),
app-20261125T190535693796Z.json (ports 9151 to 9150, switch.vhost_sha_after e31ce5801a7b..., coding live at effort max,
figures 4 documents and 25 USD), converter-20261125T190128938076Z.json (started) -->

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000` (act_r2.sh sets it
when the variable is not set and passes on any other value; each log's "door watchdog ceiling" line must read 9000: app
may wait 3,600 s for each worker it stops, ops/install.py check_door_ceiling), as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 2008ffddc946be142e8b856b4003e4c4959b1dd7 --receipts /home/claude/cpt-studio-install-20261023`
plus each phase's fixed arguments (cpt-r2-20261125/release/act_r2.sh: release 1's act_r1.sh, reviewed and used for its
install, with this release's names, phases and order; sha256 17ef3e589ee1cf29).

Phases, in this order (RELEASE-2-SPEC 9.4):
1. preflight;
2. image;
3. converter;
4. cert;
5. https-vhost;
6. preflight again (TAG after-https-vhost): the baseline app compares co-tenant routing and app.quillmd.com against.
   9.4 asks for it only if a co-tenant deployed since step 1; act_r2.sh requires it every time, as release 1's did,
   because app compares with the newest preflight only after its migrate, so an unnoticed co-tenant deploy would spend
   app's one attempt (the lead's decision Q5, D-R2-53: always required, superseding 9.4's "only if"); then, not a phase,
   pre_app_r2.sh (read-only on the live database), its log ending PRE-APP PASS - after a WAIT, a preflight and
   pre_app_r2.sh again, each under the same new TAG (the lead's ruling R3P-4, D-R2-55);
7. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes the
   live pair runs with;
8. passages;
9. license-note;
10. verify.

Then, not phases and in this order: the live check (live_check_r2.py); post_check_r2.sh once (no sooner than ten minutes
after app's S1); the access-log reading, `access_report_r2.sh act`, once S3 + 1 h has passed (the hour after is release
2's web's first hour, from S3, read from app's receipt); then the owner's acceptance question (below), asked once, after
the live check and after both of 9.8's readings, and only while release 2 serves - never after a switch-back, when he is
told the switch-back in one line instead (the lead's ruling R3P-6, D-R2-55; review round 3 owner-1), and withdrawn by
a switch-back decided after it was sent and before his opens are read (the lead's ruling R4P-2, D-R2-57, and decision
RH-7; review round 4 owner-0) - (it ends the
lead's turn: the lead's ruling R2P-7, D-R2-55; review round 2 owner-0; only a genuine message of his that answers it is
his answer, never a task notification or any other input, and no answer within 24 hours is recorded as "no answer",
which judges nothing: the lead's ruling R3P-6; review round 3 truth-3, owner-0); and, after his answer, the access-log
reading of his opens, `access_report_r2.sh opens`, only when no switch-back was decided (review owner-9, scripts-7;
the lead's ruling R4P-2). There is no db phase (no database
setting changes) and no ruled act through --phase manage.
<!-- act_r2.sh: its case statement (ARGS per phase); post_check_r2.sh's header (S1 + 600 s); access_report_r2.sh's
modes -->

act_r2.sh refuses: a REV other than this declaration's "Revision to install"; a DECL other than
docs/foundation/mutations/<date>-cpt-studio-release-2-install.md and an ACT that does not begin with
/opt/meddoc-pro/.worktrees/cpt-r2-act- and a digit; any installer argument on its own command line; a checkout with a
tracked file modified or staged, or not detached, a REV that is not HEAD or its ancestor, any change under cpt-studio/,
scripts/run-ruled-mutation.sh, scripts/lib or scripts/check-cotenants.sh between REV and HEAD, a declaration that is not
tracked or differs from its commit, and a declaration still holding a placeholder; an ACT other than the act checkout the declaration names in
parentheses (review round 2 truth-5); a changing phase while a script of the package is not the one "The package as run"
names (sha256, first 16, compared at every phase and written into each log; a read-only phase and switch-back only
record a difference: review round 2 truth-8); a phase run twice under one log (but image, and converter after it, once
more under a new declaration that continues the act after a PRE-APP STOP or the window's end, before any app: the
earlier log, ended exit 0 under the other declaration, kept as act-r2-<phase>.decl-<its sha256, first 16>.log, a kept
attempt of the phase staying beside it; the lead's ruling R2P-5, D-R2-55; review round 2 truth-3, scripts-1); a second run of a changing phase, unless the first's failure is proven twice - its log's last line records the door's
non-zero exit, and exactly one receipt of that phase and revision written inside that run says ok false - and
RERUN_DECISION_FILE names the file holding the decision (then only after a preflight newer than the failed run, whose
log is kept as
act-r2-<phase>.attempt-<n>.log; a phase that ended exit 0, or whose end is unknown, never runs again through it); TAG on a
changing phase; image without a newest preflight that ended exit 0; converter without the image log ending exit 0 under this declaration, by path and sha256 (review round 4 scripts-4), cert
without converter's, https-vhost without cert's; app without PRE_APP_LOG (pre_app_r2.sh's newest log for this revision,
ending PRE-APP PASS), without image, converter, cert and https-vhost logs ending exit 0, without a preflight newer than
https-vhost that is the newest and ended exit 0, or with the pre-app log older than that preflight or more than 900 s
newer than it (preflight to PASS, never to now: review round 4 scripts-1); app with
act-r2-image.log or act-r2-converter.log naming another declaration, by path or sha256 (the lead's ruling R3P-3, D-R2-55:
after a continuation under a new declaration, image and then converter run again under it first); app with an image,
converter, cert or https-vhost log of another revision (a continuation keeps the act's revision: cert and https-vhost never run again, so a new
revision is a new act; review round 4 scripts-3); app with another
pre-app reading between that preflight and the one it runs on (a WAIT, a stop on the quiet window, a PASS not taken
within 15 minutes: a preflight runs again, then pre_app_r2.sh - the lead's ruling R3P-4, D-R2-55); app after a
switch-back that ended exit 0 (a new install is a new declaration); passages and verify before app, license-note before
passages; db, manage, rollback-app and every phase this declaration does not run; switch-back without
SWITCH_BACK_DECISION_FILE and a preflight that ended exit 0 newer than every app, passages, license-note and switch-back
log (their kept attempts included); the variables SWITCH_BACK_DECISION and RERUN_DECISION (a decision is never text on a
command line: prose is never a shell argument, review safety-1); and a decision file that is not a regular file of this
user's in /home/claude/cpt-r2-20261125/release/reasons/, named with lowercase letters, digits and hyphens and ending
.txt, mode 0600, holding one line with no control character, in words (12 or more characters that are not space, three
words or more). The decision, its file's path and the first 16 characters of its sha256 are written into the phase's log.
<!-- act_r2.sh: refuse(), words(), read_decision(), the RERUN block (FAILED_RECEIPT python), newest_preflight(), after(),
newest_ok(), the case "$PHASE" order block, the checkout checks before the door call; sim/sim_act_r2.py drives each arm -->

The installer gives the web and the worker the coder settings of this revision: effort "high" (CODING_EFFORT, the one
change: R2-33, D434), the 25 US dollar per-document ceiling and 4 documents at once (unchanged). It gives the same effort to
any pair it starts, release 1's pair on a switch-back included (D-R2-49: D434 measured release 1's image at "high").
<!-- install.py: CODING_EFFORT, runtime_env, service_args, coding_figures; settings.py CODING_EFFORT -->

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-r2-act-20261128). That commit must be a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh, scripts/lib/ or scripts/check-cotenants.sh. Read each receipt
before the next phase (`python3 -I /home/claude/cpt-r2-20261125/release/receipt.py 2008ffddc946be142e8b856b4003e4c4959b1dd7 <phase>`).

Not run: secrets, reference, provision, operators, db, http-vhost, ingress, ingress-rollback and rollback-vhost, and every
manage command. switch-back is the incident path after a successful app, and rollback-app the one after an app that
stopped half way (below), each only by a decision recorded in words under this declaration. act_r2.sh refuses
rollback-app, so it is run by hand in the act checkout, in a subshell that names it (the door's paths are the
checkout's own, and the working folder outside it never changes):
`(cd /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128 && RULED_ACT_MAX_SECS=9000 bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20261128-cpt-studio-release-2-install.md -- python3 -B cpt-studio/ops/install.py --phase rollback-app --revision 2008ffddc946be142e8b856b4003e4c4959b1dd7 --receipts /home/claude/cpt-studio-install-20261023) > /home/claude/cpt-r2-20261125/release/act/act-r2-rollback-app.log 2>&1`,
its output kept as that log. No document is sent by the install.

Between 816045c7264481bc6956285e1ca89991b9fcec2f and the revision, these are byte-identical (`git diff --quiet` with the
pathspecs below: exit 0, over the 50 files the pathspecs cover at the revision (`git ls-files --with-tree=` the revision, in a clean worktree at it), read at 2026-11-28T09:56:54Z; its positive control, below, exits 1): the coder's prompts, client, answer reading, pricing and credentials loader
(studio/fable/ but document.py and docx_package.py), studio/decisions.py (the approval rules), the physician report
(physician_report.py, physician_pdf.py and every file of report_fonts/), the reference data (studio/reference/),
migrations 0001 to 0018, the Dockerfile, its .dockerignore and entrypoint.sh, requirements.txt (so the image's packages,
anthropic 2.11.0 among them, are release 1's), and the HTTP stage (deploy/nginx/cpt-quillmd-http.conf: the :80 block
every renewal reads). Positive control for the byte-identity command: the same `git diff --quiet` on
cpt-studio/studio/fable/document.py exits 1.
<!-- at ccb350d0b: exit 0 over 50 files; the positive control exits 1 -->

These change (123 files, 33,536 insertions and 666 deletions - 34 added, 89 modified, none deleted; under cpt-studio/ 118 files, 32 added and 86 modified, 30,982 insertions and 652 deletions (`git diff --shortstat` and `--name-status`, 816045c7264481bc6956285e1ca89991b9fcec2f to the revision, read at 2026-11-28T09:56:54Z)): the web process (deploy/gunicorn.conf.py: 4 sync processes, preload, warm-up and
gc.freeze, connections kept 3,600 s with health checks in the web only, recycling after 10,000 to 11,000 requests;
cptstudio/wsgi.py and the new cptstudio/warm.py; settings.py), a database that cannot be reached answered 503 with
Retry-After (the new studio/db_unavailable.py, last in MIDDLEWARE; handler500 in cptstudio/urls.py and urls_admin.py;
bundle_api.py), the lists, the search and their records (studio/api.py,
customer.py, the new paging.py, read_audit.py, the client contract customer-2026-11-26), the detail's reads
(state.py by extraction), the document viewer (studio/static/studio/app.js, its PDF worker made ready ahead, page
memory wiped at every end), the console's fonts by hashed name (ops_base.html), the three migrations, the Word refusals
(studio/fable/document.py, docx_package.py, converter_server.py, jobs.py's stored-conversion check), the front door
(deploy/nginx/cpt-quillmd-https.conf: one map entry and its comment, the capacity comment corrected, no zone changed),
the installer (ops/install.py: WEB_LIMITS 1g, the coder's effort, the kept life-cycle lines, the image's smoke check of the
worker's command) and its tests, the bench (ops/bench, never in the image), the verification tools (they speak
customer-2026-11-26), and the documents. Outside cpt-studio/: scripts/ci/verify-cpt-studio.sh (run by CI alone, by no
phase and in no image), docs/foundation/RULINGS.md and docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (the
recorded directions), and release 1's declaration, its amendment and report and D425's record (#1527 to #1530,
documents only).
<!-- git diff --stat 816045c72644..ccb350d0b: 123 files, 32,252 insertions, 644 deletions; under cpt-studio/ 118 files (32
added, 86 modified), 30,133 insertions, 630 deletions; runtime files 51 (50 under cpt-studio/, and
scripts/ci/verify-cpt-studio.sh) -->

Before preflight the health check is run, report-only (its stop condition, below), and the operator runs, each read of
the act's checkout with `git -C /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128` and every other path absolute, so no step changes the working folder (review
truth-0, scripts-3, safety-3):
- `git -C /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128 status --porcelain --untracked-files=all --ignored -- cpt-studio scripts`, printing nothing (act_r2.sh and the
  installer look at tracked files only, and a module beside install.py would be imported in place of the standard
  library's), and `echo "${RULED_ACT_MAX_SECS:-unset}"`, printing unset or 9000;
- `git -C /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128 diff --quiet 816045c7264481bc6956285e1ca89991b9fcec2f HEAD -- cpt-studio/studio/fable ':(exclude)cpt-studio/studio/fable/document.py' ':(exclude)cpt-studio/studio/fable/docx_package.py' cpt-studio/studio/decisions.py cpt-studio/studio/physician_report.py cpt-studio/studio/physician_pdf.py cpt-studio/studio/report_fonts cpt-studio/studio/reference cpt-studio/deploy/Dockerfile cpt-studio/deploy/.dockerignore cpt-studio/deploy/entrypoint.sh cpt-studio/requirements.txt cpt-studio/deploy/nginx/cpt-quillmd-http.conf ':(glob)cpt-studio/studio/migrations/000[1-9]_*.py' ':(glob)cpt-studio/studio/migrations/001[0-8]_*.py'`, exit 0;
- `git -C /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128 diff --name-only 816045c7264481bc6956285e1ca89991b9fcec2f HEAD -- cpt-studio/studio/migrations`, printing exactly
  cpt-studio/studio/migrations/0019_r2_document_lists.py, cpt-studio/studio/migrations/0020_r2_run_lookups.py and
  cpt-studio/studio/migrations/0021_r2_round_sweep.py;
- `git -C /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128 diff --name-only 2008ffddc946be142e8b856b4003e4c4959b1dd7 HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib scripts/check-cotenants.sh`,
  printing nothing;
- the revision's HTTPS stage rendered for each port as the installer renders it (`git -C /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128 show 2008ffddc946be142e8b856b4003e4c4959b1dd7:cpt-studio/deploy/nginx/cpt-quillmd-https.conf`,
  @@DOMAIN@@ cpt.quillmd.com and @@UPSTREAM@@ 127.0.0.1:<port>, sha256 of the result): STAGE_9150 `3532f50c8f7420c415962195be7635748d97d4b9c423df5d8190ba7fe12e578d` and
  STAGE_9151 `57e1bec0fd2260daf14230cb44d42fb5e35e58cad1fae141d842c5ff45ef0f19`;
  <!-- install.py: rendered_vhosts, render, upstream. Positive control of that rendering: 816045c72644's template gives
  e31ce5801a7b... (9150) and bbd482895d79... (9151), exactly the two stages release 1 declared. At ccb350d0b the
  template gives 3532f50c8f7420c415962195be7635748d97d4b9c423df5d8190ba7fe12e578d (9150) and
  57e1bec0fd2260daf14230cb44d42fb5e35e58cad1fae141d842c5ff45ef0f19 (9151); recomputed at the revision. -->
- `grep -nE '\{\{[A-Z]|[A-Z0-9_]\}\}' /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128/docs/foundation/mutations/20261128-cpt-studio-release-2-install.md`,
  printing nothing: no placeholder of this draft is left, half-filled ones among them - act_r2.sh's own brace pattern,
  which RUNBOOK-r2.md item 8 runs before the commit with the guard's other forms (the lead's decision RH-7), and
  act_r2.sh refuses the same;
- `docker ps --filter label=org.quillmd.cpt-r2=1 --format '{{.Names}} {{.Status}}'` and the same for
  org.quillmd.cpt-r1=1, printing no running container (the rehearsal's web, worker and converter run as uids 10150 and
  10151, which preflight refuses outside CPT Studio; pre_app_r2.sh refuses one named cpt-r1-rh-* or cpt-r2-rh-*);
- at once before preflight, `bash /home/claude/cpt-r2-20261125/release/baseline_diff_r2.sh` (REV, ACT, DECL and
  DECLARED_BASELINE=/home/claude/cpt-r2-20261125/release/declared-baseline-20261128.txt in its environment;
  read-only), its last line `BASELINE PASS`, exit 0: live still reads as the Baseline block but for the set-aside rows
  and, after a member's finished coding, the coding rows (both below; baseline_compare_r2.py, the one comparison
  pre_app_r2.sh runs too). It binds the declared file to this declaration's Baseline block exactly, keeps its own reading
  (0600, named with its sha256) and fails closed: an empty or missing input, a failed read or any variable its caller's shell
  holds (SET_ASIDE or any other) cannot make it pass (review scripts-1, safety-2: the first draft's inline diff passed on nothing). `BASELINE WAIT`
  (exit 4): a job queued or running, or a send in flight, in the reading - whatever the declared baseline held (the
  lead's ruling R2P-6, D-R2-55; review round 2 safety-1) - wait until it has ended and the window is quiet, and run it
  again. Anything else (a difference, an error, no output) stops the act before any phase; pre_app_r2.sh makes this
  comparison again after converter, cert and https-vhost.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; cpt-r2-20261125/release/held_check_r2.sh
with this range): 816045c7264481bc6956285e1ca89991b9fcec2f to 2008ffddc946be142e8b856b4003e4c4959b1dd7, run by the lead with HELD_TREE a worktree at the revision (held_check_r2.sh 8a54a8aca76b1a3c, as "The package as run" names it; its output lead/held-check-2008ffddc.txt, written 2026-11-28T09:10:06Z, sha256 first 16 25dd3bea2abe6bab): 51 runtime files (50 under cpt-studio/); its positive control, deploy-prod.sh named by 70 files; 36 documents naming a runtime file of the range, 25 declarations and 11 reports, every revision each names an ancestor of the running revision; possibly held: 0. The range's first-parent merges on main: #1527 (release 1's declaration), #1528 (its
amendment), #1529 (its report), #1530 (D425's record), #1531 (lane F), #1532 (lane W), #1533 (lane P), #1534 (lane S),
#1535 (lane M), #1536 (lane D) and #1537 (the integration).
<!-- at ccb350d0b (2026-11-27): 51 runtime files, 50 under cpt-studio/; positive control 70 files; 36 documents naming one
of them, 25 declarations and 11 reports, every named revision an ancestor of 816045c72644; possibly held: 0 -->

## Delta shipped (816045c72644 to the revision)

**This is a TREE, not one change**: the range carries release 1's four documents (#1527 to #1530), release 2's six lanes
(#1531 to #1536) and their integration (#1537). Its runtime changes are release 2's:

- **The web process** (R2-4 to R2-9; D-R2-17). gunicorn runs four sync processes forked from one master that has loaded
  and warmed the application (both URLconfs, every template, the static manifest, the password hashers; no database
  read), with the database connections closed and the loaded objects frozen before the fork; each process opens its
  own connection before its first request and keeps it 3,600 s, checked at each request (the worker and the commands keep
  60 s and no check); a process is recycled after 10,000 to 11,000 requests; the container's limit is 1 GiB without swap
  (WEB_LIMITS) instead of 768 MiB; the web imports no AI library (the worker loads the SDK at its start); a worker killed
  for memory or failing to boot is kept in the ids-only log a deploy writes.
  <!-- deploy/gunicorn.conf.py; cptstudio/wsgi.py, warm.py; settings.py DATABASES (CONN_MAX_AGE, CONN_HEALTH_CHECKS,
  connect_timeout); install.py WEB_LIMITS (:2963), KEPT_LOG_FORMATS -->
- **A database that cannot be reached** (I1-15, I2-4). A lost or unusable connection (an InterfaceError; an
  OperationalError with no SQLSTATE, class 08 or 57P01 to 57P03) is answered 503 with `Retry-After: 5` on both hosts
  instead of Django's HTML 500, and nothing of the request is served. Under /api/ the answer is the API's JSON: for a read,
  the NOT_RECORDED sentence; for a change, "This action is not available right now. Reload the page to see the latest
  state.", which says neither that the change was kept nor that it was not. Elsewhere it is the plain "Service Unavailable
  (503)" page. Every other database error stays Django's 500; a loss in Django's own session write stays its 400 (I1-20).
  <!-- studio/db_unavailable.py; settings.py MIDDLEWARE; cptstudio/urls.py and urls_admin.py handler500; bundle_api.py
  raise_if_lost (review truth-2, part 1; part 2, the console's converted PDF, was refuted: unchanged) -->
- **The document viewer** (R2-10 to R2-18). A PDF worker is made ready ahead, one per document; page 1 is drawn at once;
  one fade per page load; a re-open is drawn from page memory after a 304 the server records (`member.inline`, filters
  `{"shown_from": "page_memory"}`, written before it is answered; a row that cannot be written answers 503); the view is
  asked for at the click; the page shell carries the session; page memory (at most 6 PDFs and 24 MiB a tab, ArrayBuffers
  only) is overwritten and dropped at every end, `pagehide` included. The view's ETag is an HMAC shown as a UUID, never a
  hash (D-R2-7).
- **Lists, search and their records** (R2-19 to R2-24; D-R2-10 to D-R2-13, D-R2-26, D-R2-27). Overview, Documents and
  the Review queue come a page at a time (50 rows, 5 on the Overview; `GET /api/encounters?list=documents|queue|recent`,
  answering `{encounters, next, total, workspace}`, every row with `opens_pdf`); a Documents list of more than 200
  documents is searched on the server (`POST /api/encounters/search`, the words in the body only, never stored or
  logged); each list page or search writes one `member.list` record naming the documents it served; later pages and
  searches are limited to 120 a minute per member; the client contract version is customer-2026-11-26, so a release-1
  tab is told to reload.
- **The detail's reads, the console's fonts, the front door** (R2-25 to R2-27). One read of the round and its decisions
  per detail; the console's four fonts by hashed name, immutable; a search counted as a read at the front door (the vhost's
  one new map entry), the capacity comment corrected.
- **Word** (R2-28 to R2-31; D-R2-18, D-R2-23, D-R2-33 to D-R2-46). Every inserted document that holds content is refused,
  of any format, and on purpose an External `altChunk` and every `w:subDoc`; an object or control that would leave no
  picture is refused (a PDF preview counts as a picture; PICT and SVG previews do not); R2-30 keeps the words of a removed
  field inside another field's result, and its fallback refuses the H01 shape; a package not in the one canonical form
  the gate admits is refused (the canonical package gate); the same check runs before a stored conversion is reused; the
  refusal's sentence reaches the doctor and the record. Release 1's own refusals still run first, with their reasons.
- **The migrations** (R2-23; section 6; D-R2-15): 0019_r2_document_lists (studio_encounter: studio_enc_ws_time and
  studio_enc_ws_queue, both partial), 0020_r2_run_lookups (studio_providerrun: studio_run_round, an expression index, and
  studio_run_in_flight, both partial), 0021_r2_round_sweep (studio_codinground: studio_round_open, partial): plain
  `AddIndex`, one table each, no column, table, constraint, RunPython or RunSQL.
- **The coder's effort** (R2-33, D-R2-38): "high" in place of "max"; nothing else in a request changes.
- **The installer** (R2-6, R2-9, R2-33): WEB_LIMITS ('1g', 128, '256m'); CODING_EFFORT 'high'; the image phase loads the
  web application and the worker's command (`import cptstudio.wsgi, studio.management.commands.run_worker`); the kept
  life-cycle lines.
  <!-- install.py: WEB_LIMITS (:2963), CODING_EFFORT (:232), phase_image's smoke (:7058-7060), KEPT_LOG_FORMATS -->

## What the owner and members see after the install

- Faster opens, lists and search.
- A tab open across the switch asks to reload: from S3 its next customer API call answers 409 `client_outdated` and the
  page shows "CPT Studio was updated — reload the page to continue."; its downloads and in-page views keep working
  (outside the contract). After a switch-back, a release-2 tab meets release 1's 409 the same way, and a document still
  queued or being coded at the switch-back's closes (B4, B7) reads Stopped until a member presses Resume (Rollback per
  phase, switch-back; review round 4 safety-2).
- Nobody is signed out: release 1 and release 2 share release 1's session policy, so app ends no session.
- Coding pauses from S2, while the old worker finishes the document it is on, to S4; uploads are accepted and shown as
  queued. About 5 seconds when nothing is coding (S2 to S4 always holds S3's switch: 4.3 to 6.4 s in this host's 17
  blue/green installs that ended no session, app receipts 2026-11-05 to 2026-11-23; release 1's 8.7 s with its session
  end), then the new worker's start, which is why the window is a quiet hour; at most 60 minutes (STOP_SECONDS['worker']).
  <!-- review truth-6: details.steps of every blue/green app receipt in /home/claude/cpt-studio-install-20261023 -->
- The Word refusals start at phase converter for a fresh conversion (release 1's worker shows the general sentence for
  a refused file until S4), and at S4 for a round that reuses a stored conversion (C8).
- QuillMD's visitors: nothing changes on quillmd.com, www.quillmd.com, app.quillmd.com or pro.quillmd.com.

**The accepted-capability change** (class b; told once, not asked, by the recorded standard D428, C10: D428's message
and 2026-11-28T09:10:54.069Z; his reply by this declaration's commit: "no need to test and round for another speed test ill try it on live and let you know just focus to finish the jobs asap i gotta test whole the thigns audit agents speed dictation everything hopefully soon" (2026-11-28T09:38:19.903Z, verbatim from the session transcript), recorded as his words and read as neither an acceptance nor a refusal (the session's record D457 reads it as no stop and no re-measure); and, at 2026-11-28T09:43:58.588Z, verbatim from the session transcript: "Release 3 is my high priority just give me a relastic time once you told me it takes saturaday now you say monday or tuesday what is the relasitc time?" (about release 3's timing, answered in the session; recorded as his words and read as neither an acceptance nor a refusal)): some Word files that convert today are refused with a
message, among them files release 1 coded completely and files Word 2007 itself writes. That covers every inserted
document that holds content, of any format; an `altChunk` whose relationship is External and every `w:subDoc`, refused
on purpose (C9); and an object or control that would leave nothing, a PICT or SVG preview included (D-R2-45). Failing
closed, it also covers an `altChunk` whose Internal target no reading resolves, a package whose Unicode Path names
differ from its stored names (D-R2-43), and a package not in the one canonical form the gate admits, whatever generator wrote
it (the canonical package gate, D-R2-46: the Open XML SDK's from-scratch documents, the docx npm package's multi-word
embedded font names, pandoc with --reference-doc, an archive comment added by a re-zipping tool, a forced-zip64 local
header, Office 2007's `[trash]/` entries; each refused with the save-as-PDF message, never silently coded - for these
files the message names an inserted document they do not hold (document.py's inserted_document sentence; review owner-2)
- and each admissible later as a measured exception from a real sample). It also applies at the next round of a document
whose conversion was stored before the install (C8). R2-30's fallback refusal is named here too (D-R2-36): a kept field,
not `HYPERLINK`, `TOC`, `QUOTE` or `STYLEREF`, whose stored result a reader sees while a removed field stood in its
instruction. For its H01 shape release 1 already loses those words on the live LibreOffice 7.4 without saying so, so for
that shape the trade is D428's kind; some other field types release 1 coded completely (D-R2-36; review round 2
owner-2). It is the session's decision (D427, D428, D-R2-36, D-R2-45, D-R2-46) under D421's principle and its reading
of D422: D422 answered yes, for release 1's install, to both losses put to him (a file damaged inside or built in a way
Word does not produce, refused; a document inserted whole into a Word file, left out of the PDF with no notice), and the
recommendation's next-release half named only the inserted document, refused with a message (C9, D427, later limited it
to one that holds content); PICT and SVG previews and the canonical package gate also refuse files release 1 coded
completely, the gate among them files Word 2007 itself writes, which is more than the first loss D422 said yes to (a
file built in a way Word does not produce, as D421 summarises it: the session's words, not his) (review owner-1, and its
round 2; round 4 owner-2).

**Trade-offs accepted** (lane D rounds 1 and 2, D-R2-39, D-R2-43):
- an oversized Word file (past release 1's size limits) whose view was made before release 1 is refused at its next
  round, with the general sentence, as a fresh conversion of it is;
- a round begun on release 1's worker and resumed after S4 finishes on its own PDF: where that PDF is release 1's
  conversion, R2-30's words, and a picture release 1's package lost (a renamed name, an id only expat finds), stay missing
  in that one round; its reads, its view and its quote pages stay on one PDF, and the next round converts afresh;
- the converter is never rolled back to release 1's after S4 (Rollback, below).

## Cost and time

No paid request, and no certificate order unless the lineage is due. The image build: requirements.txt and the
Dockerfile are release 1's, so the pip layer comes from the build cache when it holds release 1's layers
(the second rehearsal's build step, cache warm: release 1's docker build 0.5 s and its whole step 10.2 s, B's docker
build 0.4 s and its whole step 8.0 s, both images served wholly from the build cache - their ids the first run's, no
RUN step run and nothing fetched; a build without cached layers not measured: the lead's decision RH-6). Measured on
this host by release 1's install (2026-11-25, D423; each phase's start and end lines
in cpt-r1-20261124/release/act/): preflight 11 s, image 47 s, converter 11 s (its first start; a replacement adds the
old converter's stop, at most 80 s), cert 11 s, https-vhost 11 s, the preflight again 12 s, app 3 min 6 s (migrate one
attempt, the drain 130.6 s, no job active), passages 26 s, license-note 11 s, verify 11 s. Bounded by the code for what
is new here: converter, the old converter's stop (at most 80 s, CONVERTER_STOP_SECONDS: a conversion in progress
finishes) and the new one's 20 s start period and at most 60 polls 2 s apart; app, at least the S5 drain (130 to 600 s)
plus S2's wait for the old worker's current stage (1 to 2.5 s when it is idle on this host's receipts, at most 3,600 s:
the door's 9,000 s ceiling covers two such waits and a margin); the migrations, 8.9, 6.9 and 3.0 ms at live's sizes
(section 6). The web needs at most 1 GiB instead of 768 MiB during and after S1, and during the switch both webs run (1
GiB and 768 MiB).
<!-- install.py: CONVERTER_STOP_SECONDS (80), wait_converter (60 x 2 s), converter_args (--health-start-period 20s),
DRAIN_MIN/MAX_SECONDS (:126), STOP_SECONDS (:91), check_door_ceiling (needs 2 x 3600 + margin = 9000 for app);
release 1's act logs and D423 for its times -->

## Measured before this declaration

**The full gate**: the lead's final full suite on the revision's tree, in the worktree /opt/meddoc-pro/.worktrees/cpt-r2-speed-20261128 (its head the revision and its status empty, each checked before the run), on a quiet host (the release-2 quiet hold set and both suite slots held: lead/STATE.md 08:42:55Z to 09:09:35Z): run 2, 2026-11-28T08:57:47Z to 09:09:20Z (lead/final-2008ffddc/suite-2.out), check and migrations exit 0, the Django suite 1,670 tests OK (1 skipped), ops 1,044 OK, verification 39 OK, the walk's node tests 105 of 105 and the app's 222 of 222: RESULT PASS. Run 1, 08:42:47Z to 08:54:33Z (lead/final-2008ffddc/suite-1.out), failed on one test alone, ops test_bench.BenchTabPaintTests (339.7 not at least 340: the bench tool's own test, ops/bench, never in the image), everything else passing as in run 2; that test run alone passed 3 of 3 (lead/final-2008ffddc/benchtabpaint-alone.log) and the suite was run once more, as the lead's rule says (lead/STATE.md 08:57:42Z). pip-audit is not run by the suite tool (no network); it runs in the cpt-studio workflow (scripts/ci/verify-cpt-studio.sh), success on the revision, run 46127033085. The cpt-studio workflow on the revision: CI 46127033034, cpt-studio 46127033085 and secrets-scan 46127032997, all success, read by commit (the full sha) and by branch (main, filtered to that sha) at 2026-11-28T09:57:05Z, the same three runs in both views; the revision holds no other workflow. The walk's local
browser gate (`ops/test_walk.cjs`, Playwright, D-R2-20: at least 104 tests, 0 failed, 0 skipped): `ops/test_walk.cjs` in run 2 of the final suite on the revision, 2026-11-28T08:57:47Z to 09:09:20Z (lead/final-2008ffddc/suite-2/node-test_walk.log): # tests 105, # pass 105, # fail 0, # cancelled 0, # skipped 0, # todo 0; run 1 the same, 105 of 105, none failed or skipped. The
browser speed gate (`ops/test_viewer_speed.cjs`, Playwright, on the merge commit: a runbook step on the release head,
since no CI job and no installer phase runs it - D-R2-52, D-R2-57; the lead's ruling R4P-1; review round 4 truth-0),
run in a worktree created at the merge commit (/opt/meddoc-pro/.worktrees/cpt-r2-speed-20261128), its head the merge
commit and its status empty, each read just before each run (the lead's decision RH-7): every test passing - `# pass`
equal to `# tests`, at least 18 (18 at 69e0529f2) - and none failed, cancelled, skipped or todo; a run where V16 alone
failed is recorded beside its one re-run, which passed whole: one run, in /opt/meddoc-pro/.worktrees/cpt-r2-speed-20261128: read just before it, at 2026-11-28T08:54:33Z, its head 2008ffddc946be142e8b856b4003e4c4959b1dd7 and its status empty (0 lines); then `(cd /opt/meddoc-pro/.worktrees/cpt-r2-speed-20261128/cpt-studio && node --test --test-reporter=tap ops/test_viewer_speed.cjs)`, with CPT_WALK_TEST_PORTS=9960-9999, 08:54:33Z to 08:55:46Z: # tests 18, # pass 18, # fail 0, # cancelled 0, # skipped 0, # todo 0, V16 among the passes, so no re-run (lead/final-2008ffddc/speed-1.tap; lead/final-2008ffddc.log).

**The acceptance bench, B against A** (section 8; A = 816045c72644's tree, B = a680d837b0d1e9895683cb1eb27b3dc59a1af03e's
tree: laneM/b3, B's third session, judged with --b-revision a680d837b0d1e9895683cb1eb27b3dc59a1af03e - the B
measurement's D-R2-54 (1) measured B again after laneM/b2's session on ccb350d0b, which is history; bench-r2 frozen,
D-R2-49; the acceptance table derived from the A/A of 2026-11-26, aa6; during B, agents that only read and write files
were allowed beside the driver, which kept its own load gates: D-R2-59, laneM/b3/mem.log): laneM/b3/VERDICT.json, B's third session (A B A B A B, every group, release 1's tree the other tree for the whole
driver: lead/b-run3.sh), the frozen bench-r2 (68345fb9f) with the derived table (e085bccc50bd18fd), judged with
`--b-revision a680d837b0d1e9895683cb1eb27b3dc59a1af03e`, started 2026-11-28T00:45:45Z, the driver and the judge each
exit 0 (04:44:13Z, 04:44:14Z); its trees A 816045c7264481bc6956285e1ca89991b9fcec2f and B
a680d837b0d1e9895683cb1eb27b3dc59a1af03e. The verdict line: FAIL, valid - no INVALID round and none superseded - with
169 PASS, 7 FAIL, 6 REPORT and 4 EXTERNAL of 186 rows. Five FAILs are inside D-R2-54 (2)'s written bounds and accepted
as declared: opaque-P1 200.15 ms (bound <= 240 and <= 0.40 A = 245.3), server-list-100 16.8 ms (<= 30 and <= A 22.6),
session-18000 12.4 ms (<= 20 and <= A 22.0), detail-10-p95 105.9 ms (<= 150 and <= A 202.8) and plans.no_seq_scan (its
flagged statements the documents list's whole-list COUNT alone). Two FAILs are outside D-R2-54's list, and under
D-R2-54 (2) they stop the release: documents-usable-100-P1 (B 209.1 ms against 0.6 A = 207.42 ms, A 345.7: 39.5% faster
than release 1 against a 40% target) and memory-list (B 139.5 MiB against A + 23.88 = 138.78 MiB, A 114.9: 0.72 MiB
over the allowance for the waiting worker and the kept copies). They are not re-judged and stay FAIL; release 2
proceeds with both by the lead's post-hoc decision, made with the values in hand and told to the owner with his stop
(D-R2-60). The rows the B measurement's D-R2-54 (1) fixed pass (long-tasks-max-P1 129.5 ms against 160, standby-delay
504 ms against at least 500), and so do quote-mark-P0 (31.5 ms against 34.25) and memory-signed-out (65.8 MiB against
67.04). B stands for the
revision only because every file the revision changes since a680d837b is a document - a name ending .md, or a file under docs/ (`b_stands_r2.sh`, ending B STANDS; its positive
control, the non-documents since 816045c72644, above 0; the lead's ruling Q10, D-R2-53, B's revision a680d837b by D-R2-61 (3); review truth-10): on the revision, in the worktree /opt/meddoc-pro/.worktrees/cpt-r2-speed-20261128 made at it (2026-11-28T08:42:25Z, lead/b-stands-2008ffddc.txt; lead/STATE.md 08:42:55Z): the files the merge changes since B, 2 - docs/foundation/RULINGS.md and docs/foundation/rulings/2026-10-23-cpt-studio-gi.md; of them not a document: 0; its positive control, the files that are not documents between release 1 and the merge: 115; B STANDS. D-R2-50's hand-run signed-in cold row:
run by hand in B's third session's window, after its driver and judge, as declared (lead/d-r2-50/DECLARED.md;
lead/b-run3.sh), on B's tree a680d837b: B50a at 04:44:14Z, A50 at 04:44:51Z and B50b at 04:46:07Z, each exit 0
(lead/d-r2-50/run3-*.log, out3/), every first path /api/encounters, every status 200, load at most 1.53, no error. The
two B runs pooled: 34 lifetimes (17 and 17), the largest first request 112.0 ms (112.048 ms, B50a; B50b's largest
103.9 ms), medians 90.0 and 84.3 ms; release 1 (A50, context only, judging nothing) median 1,949 ms, largest 2,295 ms.
Over the declared 100 ms, so the residual is accepted in the open as D-R2-50 declared (D-R2-54 (2), the cold row;
D-R2-60), its value and reason given: release 1's first request paid about two seconds, release 2's about a tenth of a
second; bench-r3 fixes the row. B's rows accepted in the open by D-R2-54 (2), each only within its written bound (quote marking at P0,
opacity at P1, memory after sign-out, the documents list's whole-list COUNT, three rows whose gain is not shown, and the
cold row), with B's third session's values, and D-R2-60's two rows outside that list, each with its numbers and his
stop, told to the owner, not asked, in the one message of 2026-11-28T09:10:54.069Z (D-R2-54 (3); D-R2-60; the lead's
ruling R3P-2, D-R2-55; review round 3 truth-0, owner-3), in these words - the message's item 3, verbatim from the
session transcript, each of its lines after the "> " that marks the quotation:

> **3. Speed results accepted with limits.**
> The speed test accepted some of release 2's results only within limits written down before it:
> - quote marking and memory after sign-out passed their own checks;
> - opening a page on a slow computer took 200.15 ms against a 240 ms limit;
> - the documents list's full count, and three results whose speed-up the test can't measure at its noise level, each stayed within its limit;
> - the first request after a restart took at most 112 ms, against release 1's 1,949 ms.
>
> Two results missed their limits and still count as failures. I'm going ahead with them anyway; I decided that after seeing the numbers:
> - a list of 100 documents becomes usable on a slow computer in 209.1 ms against a 207.42 ms limit, which is 39.5% faster than release 1 against a 40% target;
> - browser memory on the list is 139.5 MiB against an allowance of 138.78 MiB, 0.72 MiB over.
>
> If you say stop on these two, I'll fix both and run the full speed test again, which adds about a day.

**The Word corpus on LibreOffice 7.4** (9.1 item 1): five runs on the synthetic packages, the last on lane D's gated head
476d68ec9 (309 shapes, 771 packages, 0 accepted shapes losing a token, D-R2-46); on the revision's image in the
rehearsal on the merge commit (runbook item 2; the second run, on B's revision, left step 6 out): 309 shapes, 771 packages (B refusing 156 shapes before any conversion), 769 converted to a PDF - the two that are not, shape 093's base and r1 packages (E07, a header relationship with TargetMode="internal"), failed the same way in lane D's round 4 - and 0 accepted shapes losing a token: step 6 of the rehearsal on the merge commit, re-run after its M1 repair, its gate line at 2026-11-28T10:06:52Z (rehearsal-3/logs/steps/step-06-corpus-rerun.out; rehearsal-3/corpus/compare.txt, sha256 first 16 99cb5f8acb4489d8, equal to lane D's round-4 compare-7.4.txt but for its temporary folder names and shape 180's DATE field, which prints the day of the conversion).

**The refutation**: each lane refuted before its merge (lane F two rounds, W two, P four, S three, M two, D four and the
gate's differential round, D-R2-36 to D-R2-46); then the integrated pass over the whole diff, three rounds: round 1
(INT-ROUND1-FIXES.md, D-R2-49), round 2 (17 findings, 15 real; I2-1 to I2-4, all held), round 3 on round 2's repairs (14
real: 1 HIGH and 3 MEDIUM, all gaps in the tests that guard "search words never reach a URL, header, log or record",
each shown by a mutant the tests miss, the re-testers stating "nothing leaks today"; 10 LOW): the pass ended there
(D-R2-51), the four guard gaps and the ten lows recorded for 2.1, before any real patient (What is not claimed).

**The rehearsal on the test instance** (9.1 item 3, as D-R2-61 (2) narrows it; cpt-r2-20261125/release/rehearsal_r2.sh, synthetic data only, no copy
of live): the second run, `/home/claude/cpt-r2-20261125/rehearsal/RESULT.md` (2026-11-28, 07:00:34Z to 07:18:38Z; the first run,
which failed on its own tooling, kept whole at /home/claude/cpt-r2-20261125/rehearsal-run1), B_REV
a680d837b0d1e9895683cb1eb27b3dc59a1af03e (B's revision) and r0 816045c72644, synthetic data only, the package as run
the rehearsal fixer's final list (rehearsal_r2.sh f5683e5c0b4e7392): the lead's order ran end to end - check,
selftest, build, net, db, harness, stage, forward, etag before, bench, etag after, pause, step 13's post-check reads on
B's web, back, again, teardown - and every automated step exited 0 and passed its gate. Forward: the migrate one
attempt, applying exactly 0019_r2_document_lists, 0020_r2_run_lookups and 0021_r2_round_sweep; its health loop 300 of
300 samples 200, read whole. Step 9 by the load loop (the lead's decision RH-4, D-R2-61): the office model through the
rehearsal nginx over TLS, SNI and Host cpt.quillmd.com, at 101 documents (333 requests) and at 5000 (463),
0 answers 429 and no 5xx at either; 8 re-opens answered 304 = 8 new web 304 lines = 8 new member.inline rows from page
memory; every GATE PASS. Back and again: every sample 200, each loop 300 of 300 read whole. Step 13 (post_check_r2.sh's
reads on B's web after forward, by hand through re-bound copies): the 7 declared deltas each expected, the other 82
differences every one step 9's bench data loaded after the baseline; release 2's reads all passed - one master and
four workers each started by S3, 1 GiB with no swap, exactly 4 database connections, B's worker since S4, the five
indexes valid, member.list rows naming their documents, no stray security event; the audit-events listing alone did
not answer in its form, its since empty on a stage with no audit event (G4: runbook item 8 now stops on a declared
baseline without a last_audit row, and post_check_r2.sh no longer reaches the listing without one). Findings that
qualify the greens: G1, forward's list loop, sending release 1's client header, read whole is 24 x 200 then 176 x 409
after S3 (B's designed answer to a page of another release; the step reads only the slice before the switch); G2, the
stage runs no release-1 converter, so the replacement of a running one is not rehearsed; G3, CODING_PAUSE_0 is the
harness's time; G5, the process read's margin after S3 about a second. Not rehearsed, and none of them a pass: step 5
(removed by the lead's decision RH-3, D-R2-61: SUITE_RESULT is the suite gate), step 6, the
corpus (left out of the lead's order: CORPUS_74), bench.cjs's browser flows (no browser container: RH-4, D-R2-61), the coding
pause with a held document (no tooling: RH-5, D-R2-61) and the converter's replacement (G2). No release-2 defect was seen. On the merge commit, from a fresh folder (runbook item 2): the third run, /home/claude/cpt-r2-20261125/rehearsal-3/RESULT.md (2026-11-28, 09:15:01Z to 09:33:31Z; B_REV 2008ffddc946be142e8b856b4003e4c4959b1dd7, its cpt-studio tree a680d837b's; the package as run the finalization's list, 52 of 52): every automated step exited 0 and every gate the second run passed passed again - the build (B's image cpt-r2-test:2008ffddc946, its 11 filesystem layers equal to a680d837b's image's), forward's migrate one attempt applying exactly 0019 to 0021 and its health loop 300 of 300 read whole, step 9 by the load loop (0 answers 429 at 101 and at 5000 documents; 8 re-opens answered 304 = 8 new web 304 lines = 8 new member.inline rows; memory.peak 314,519,552 bytes, 299.9 MiB), step 13's reads on B's web (the 7 declared deltas each expected, the 82 other differences step 9's bench data, release 2's reads all passed, the audit listing now in its designed G4 form), back and again each 300 of 300, and teardown's label check printing nothing (09:33:23Z and 09:33:31Z; nothing again at 10:08:13Z, after the re-run below); G1, G2 and G4 recur by the rehearsal's own design or input, named and not judged, G3 and G5 as figures (CODING_PAUSE_0 4.4 s), and M2 is recorded (the bench files name a680d837b, the request mix's source). Its step 6, the corpus, read no package (M1: the packages 0600 under umask 077, the converter's uid 10150 read none, so its gate passed on nothing) and was the run's stop; the lead repaired rehearsal_r2.sh (every package made readable, and a run with a PermissionError or no PDF refused: f9254ca5d6e683fb, the earlier f5683e5c0b4e7392 kept as lead/rehearsal_r2.sh.before-m1) and ran step 6 alone again in that folder, 09:40:29Z to 10:06:52Z: every package readable, no PermissionError, 769 PDFs, its gate line "accepted shapes losing a token: 0" and no refusal (logs/steps/step-06-corpus-rerun.out; CORPUS_74). Not rehearsed, and none of them a pass: step 5 (RH-3), bench.cjs's browser flows (RH-4), the pause with a held document (RH-5) and the replacement of a running release-1 converter (G2). The
web's memory.peak under its real 1 GiB limit: 315,039,744 bytes (300.4 MiB), B's web in the second run, read by step 9
after the office model's load loop at 07:07:52Z, GATE PASS against 768 MiB (D-R2-17: the
fallback of 3 processes at 768m only if it passes 768 MiB). The coding pause in the rehearsal (its stop-worker to start-worker
time, 0.1 s resolution, recorded and not gated - the lead's decision RH-5, D-R2-61; no real switch_upstream there, so not this
host's figure, which is under "What the owner and members see"): 4.4 s (the second run: S2's stop of the old worker
issued at 07:03:55.9Z to S4's start of B's worker returned at 07:04:00.4Z, rehearsal/logs/coding-pause-0.txt; the
harness's own time - three harness calls, the old worker's stop, the vhost's render, nginx -t and reload, and its 1.5 s
settle - a fair upper figure for the rehearsal, not the installer's S2 to S4: G3) with no document in progress; with
one: not rehearsed (no tooling holds a document).

**The release package's own tests** (cpt-r2-20261125/release/TESTS.md): TESTS.md's summary after the finalization of 2026-11-28, every run on a copy of the package
(/home/claude/cpt-r2-20261125/fzbuild/runs/): post_check_r2.sh's stub test 119 of 119, the walk and B test 44 of 44,
the nginx log readers 83 of 83, the set-aside rows 10 of 10, the read scripts' SQL 20 of 20, act_r2.sh's simulator 157
of 157, the documents' checks 133 of 133 and their mutants 106 of 106 caught, the read scripts' mutants on the two
changed scripts (b_stands_r2.sh B01 to B11, post_check_r2.sh Q53 to Q55) each caught with its controls passing and
all 182 anchors exactly once; unchanged since round 4 and the light check, at its last count: the pre-app test 51 of
51, the comparison test 71 of 71, the live check's test 31 of 31, act_r2.sh's mutants and the read scripts' other
mutants, and the rehearsal's load tools 17 of 17 (18 with --chromium); the new tests on the pre-finalization package
fail exactly their new and changed checks (the positive controls). **The package's review**
(four lenses - truth, scripts, safety, owner - and a re-test per finding, as D420): four lenses each round and a re-test per finding, as D420 recorded release 1's: round 1 (refute-pkg/RESULT.json) 3
HIGH, 12 MEDIUM and 21 LOW real, 5 not real, each answered in ANSWERS-R1.md under PKG-ROUND1-DECISIONS.md; round 2
(refute-pkg2/RESULT.json) 3 HIGH, 7 MEDIUM and 16 LOW real and the round-1 checks, ANSWERS-R2.md under
PKG-ROUND2-DECISIONS.md; round 3 (refute-pkg3/RESULT.json) 1 HIGH, 9 MEDIUM and 9 LOW real and the round-2 checks,
ANSWERS-R3.md under PKG-ROUND3-DECISIONS.md; round 4 (refute-pkg4/RESULT.json) 0 HIGH, 2 MEDIUM and 12 LOW real, and 11
of 11 round-3 checks with no HIGH or MEDIUM left, ANSWERS-R4.md under PKG-ROUND4-DECISIONS.md, after which the review
ended (D-R2-57); its one independent check (refute-pkg4/check-light): R4P-2 and R4P-3 closed, R4P-1 closed with a LOW,
every package test count equal to TESTS.md, four runbook findings, repaired under the lead's decision RH-7; the first
rehearsal's findings repaired under RH-1 to RH-7 (ANSWERS-REHEARSAL.md), the second's G4 by the finalization
(FINALIZE-NOTES.md). The package as run
(sha256, first 16; act_r2.sh compares the first eight at every phase and post_check_r2.sh its own three, a difference a
stop: review round 2 truth-8): act_r2.sh 17ef3e589ee1cf29, pre_app_r2.sh 04a247c1e7a21bc5, post_check_r2.sh
9d45300ec5c2a8b0, baseline_r2.sh dcf5401032366595, baseline_compare_r2.py 1898ec852339b814,
baseline_diff_r2.sh e0b93a321a125b27, live_check_r2.py 2767bb618b831708, access_report_r2.sh
b9b5e7d0829e34f4, and the three reads made before this commit, walk_check_r2.sh 45a54500e1b7fb03,
b_stands_r2.sh dc0d59ca2cad3dcf and held_check_r2.sh 8a54a8aca76b1a3c (review round 3 truth-5); release 1's baseline_r1.sh d5b0f7a51d3a615a, release 2 of the admin
move's baseline_i.sh fb6ae0e5f0d96fa5 and install-judge/live_baseline_j.sh 791ef3b531021b6c, unchanged.

## Baseline (read-only, `2026-11-28T09:40:41Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_r2.sh are binding)

Read with these commands, all read-only (SELECT and SHOW only, in a read-only transaction, through the database
container's own psql; the container's own cgroup files and docker inspect; counts, names, states and ages only, never a
document, response or credential):

    (umask 077; bash /home/claude/cpt-r2-20261125/release/baseline_r2.sh > /home/claude/cpt-r2-20261125/release/declared-baseline-20261128.txt)
    ( cd /opt/meddoc-pro/.worktrees/cpt-r2-docs-20261128 && bash scripts/check-cotenants.sh )
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:816045c72644 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'
    sha256sum /etc/nginx/sites-available/quillmd /etc/nginx/sites-available/quillmd-cpt; readlink /etc/nginx/sites-enabled/quillmd-cpt
    the certificate names served for admin.quillmd.com, cpt.quillmd.com and app.quillmd.com (openssl s_client against 127.0.0.1:443, as post_check_r2.sh reads them)

baseline_r2.sh is release 1's baseline_r1.sh unchanged plus release 2's rows: encounters_coded (the install counts'
"coded"), encounters_round_state_outside_eight (expected 0), jobs_code_active, table_rows and table_bytes of
studio_encounter, studio_providerrun, studio_codinground and studio_accessrecord, one `index <name> <state>` row for
each of the five new indexes (absent before app), the times of the newest maintenance.daily and
maintenance.originals_verified events (last_maintenance_daily, last_maintenance_weekly: the window is placed away from
their next due times), and the serving web's database connections and their ages.

**The rows set aside** by every comparison of this declaration (baseline_compare_r2.py, which pre_app_r2.sh and
baseline_diff_r2.sh run, and post_check_r2.sh), because ordinary use and release 1's own daily maintenance move them by
themselves: read_at,
last_audit (the newest audit event's row), login_attempts, sessions, r1_table studio_accessrecord, r1_table
studio_accessrecordrepeat, r1_table studio_ratewindow, r1_table studio_sessionaccountlink, r1_table studio_securityevent,
table_rows studio_accessrecord, every table_bytes row, last_maintenance_daily, last_maintenance_weekly,
web_db_connections and web_db_connection_ages. Each is still read, and kept in that run's reading file
(baseline_diff_r2.sh's baseline-r2-before-preflight-<stamp>.txt and pre_app_r2.sh's baseline-r2-pre-app-<stamp>.txt,
each named with its sha256 in its output; post_check_r2.sh's baseline-r2-after-<stamp>.txt); the read records' rows are
held to section 6's rule (at most 100 times their declared count) before app, every security event since the Baseline
reading is read by name after app (any but the scheduled maintenance's a finding, a weekly check's
storage.original_mismatch between the reading and image included: review scripts-11), and the web's connections are
gated before app (at most 2, each younger than 600 s) and after it (in its first hour exactly 4; after it at most 4, none
older than the web).

**The coding rows** (the lead's ruling Q7, D-R2-53, 9.2's "Jobs of kind code running or queued. If any, wait"): the rows a
member's coding moves - a retry or answers to the coder's questions, the round they start, its code job and its two
sends. They are: the totals jobs, provider_runs, provider_runs_sent, audit_events, studio_codinground,
studio_codinganswer, encounters_coded, table_rows studio_codinground and table_rows studio_providerrun; the gate rows
jobs_active, jobs_code_active and runs_reserved_or_sending; the per-state rows job code, jobs_code and encounter_state;
the coding runs' rows (run, run_participant and runs_coding of the purposes coding_reader and coding_checker); and the
audit events of the coding path, audit_event answers.recorded, coding.round_queued, coding.round_done,
coding.round_failed, provider.sending, provider.finished, provider.counting and provider.count_failed. Between the
Baseline reading and pre_app_r2.sh they may differ only as a finished coding moves them (baseline_compare_r2.py): no job
queued or running and no send in flight (else a wait: a preflight and pre_app_r2.sh again, each under the same new TAG,
once it has ended and the window is quiet: the lead's ruling R3P-4), nothing removed, every total equal to the sum of its parts (only code jobs and coding sends added; job code and
jobs_code alike; the rounds and coding.round_queued alike; the answers with answers.recorded; the encounter states
adding up to the unchanged encounters, and moving, as the encounters coded do, only with a round or a code job; each
code job added with its round; no row of an ended job or send - succeeded, failed, cancelled, not_sent, unknown -
falling: review round 1 scripts-2's re-test); each moved row is named in the pre-app log, and post_check_r2.sh and app's counts are then judged against the reading that
run kept. A decision, an export, an upload, a stop or a resume, a reconcile, a hold, any other job kind, run purpose or
audit event is not a coding row.
Every other row is compared exactly.
<!-- The block below: baseline_r2.sh's output exactly, each line indented four spaces, from its read_at line up to the
co-tenants reading (pre_app_r2.sh and post_check_r2.sh extract that span with awk and diff it with the declared baseline
file). Expected: studio_migrations 18, studio_migration_last 0018_r1_availability, the five index rows absent,
encounters_round_state_outside_eight 0, jobs_code_active 0, web_db_connections at most 2, a last_audit row holding a
time (the newest audit event: post_check_r2.sh's audit listing takes its since from it, and RUNBOOK-r2.md item 8 stops
without one - the second rehearsal's G4); containers cpt-studio-web
(127.0.0.1:9150->8000/tcp, healthy) and cpt-studio-worker of 816045c72644's image, cpt-studio-converter of the same
image, cpt-studio-db postgres:17.11-alpine on 127.0.0.1:55451; ingress quillmd b3ab66023547..., quillmd-cpt
e31ce5801a7b... behind the link /etc/nginx/sites-available/quillmd-cpt; admin.quillmd.com and cpt.quillmd.com served the
cpt-studio certificate (exactly those two names), app.quillmd.com QuillMD's. Filled on 2026-11-28: the block is
/home/claude/cpt-r2-20261125/release/declared-baseline-20261128.txt whole (255 rows, read_at 2026-11-28T09:40:41Z,
its stderr file empty, sha256 first 16 ab76269e7965c8c9; jobs_active, jobs_code_active, runs_reserved_or_sending,
runs_unreconciled_unknown and encounters_round_state_outside_eight each 0; last_audit holding a time; db_cgroup
536870912 and 0; web_db_connections 2, aged 106 and 45 s); the co-tenant reading at 09:40:42Z
(lead/cotenants-20261128.txt); the container, image and ingress readings at 2026-11-28T09:56:41Z. -->

    read_at 2026-11-28T09:40:41Z
    transaction_read_only on
    encounters 102
    revisions 103
    source_files 96
    contexts 106
    routing_runs 116
    provider_runs 313
    provider_runs_sent 277
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1547
    reports 209
    jobs 666
    jobs_active 0
    users 9
    memberships 7
    workspaces 3
    login_attempts 158
    reference_sources 2
    reference_facts 34665
    studio_migrations 18
    studio_migration_last 0018_r1_availability
    studio_providerexchange 264
    studio_toolcall 173
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 29
    studio_memberanswerrevocation 6
    studio_operatorgrant 2
    studio_operatorrevocation 1
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
    run_participant anthropic coding_checker succeeded 13
    run_participant anthropic coding_reader succeeded 13
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
    encounter_state awaiting_answer 6
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready 3
    encounter_state ready_for_review 8
    encounter_state reviewed 33
    run anthropic appraisal succeeded t f 4
    run anthropic coding_checker succeeded t f 13
    run anthropic coding_reader succeeded t f 13
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
    job code succeeded 13
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
    last_audit coding.round_done 2026-11-26T01:23:17Z 202644
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
    current_context_by_version none 14
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
    studio_codinground 13
    studio_codinganswer 0
    studio_codedecision 20
    studio_exportartifact 15
    jobs_code succeeded 13
    runs_coding coding_checker succeeded 13
    runs_coding coding_reader succeeded 13
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
    password_hashes_digest 6b7c3a851f6519e554a422100c4d1ccaf66392d30379c247125b46720627feee
    operator_grant ops-agent ended
    operator_grant platform-operator standing
    audit_event account.provisioned 7
    audit_event assessment.created 186
    audit_event assessment.recompute_queued 12
    audit_event assessment.refreshed 20
    audit_event coding.round_done 13
    audit_event coding.round_queued 13
    audit_event context.changed 17
    audit_event decision.recorded 83
    audit_event detail.answered 32
    audit_event detail.revoked 6
    audit_event encounter.created 102
    audit_event export.created 15
    audit_event operator.password_reset 2
    audit_event operator.viewed 134
    audit_event pipeline.resumed 8
    audit_event pipeline.stopped 8
    audit_event provider.counting 2
    audit_event provider.finished 277
    audit_event provider.reused 31
    audit_event provider.second_review_requested 2
    audit_event provider.sending 277
    audit_event report.generated 209
    audit_event revision.addendum 1
    audit_event revision.extracted 90
    sessions 0
    setting log_error_verbosity terse
    setting log_min_error_statement panic
    r1_table studio_accessrecord 64
    r1_table studio_accessrecordrepeat 4
    r1_table studio_securityevent 12
    r1_table studio_disposalevent 0
    r1_table studio_ratewindow 6
    r1_table studio_onetimetoken 3
    r1_table studio_secondfactorcredential 1
    r1_table studio_secondfactorrecoverycode 10
    r1_table studio_filekey 0
    r1_table studio_sessionaccountlink 0
    db_cgroup memory.max 536870912
    db_cgroup memory.swap.max 0
    db_hostconfig memory 536870912 memory_swap 536870912 shm 134217728
    encounters_coded 13
    encounters_round_state_outside_eight 0
    jobs_code_active 0
    table_rows studio_encounter 102
    table_rows studio_providerrun 313
    table_rows studio_codinground 13
    table_rows studio_accessrecord 64
    table_bytes studio_encounter 196608
    table_bytes studio_providerrun 8798208
    table_bytes studio_codinground 344064
    table_bytes studio_accessrecord 229376
    index studio_enc_ws_queue absent
    index studio_enc_ws_time absent
    index studio_round_open absent
    index studio_run_in_flight absent
    index studio_run_round absent
    last_maintenance_daily 2026-11-27T19:05:00Z
    last_maintenance_weekly 2026-11-25T19:04:14Z
    web_db_connections 2
    web_db_connection_ages 106,45
    --- co-tenants
    HOST                   EXPECTED  OBSERVED
      🟢 quillmd.com          200       200
      🟢 www.quillmd.com      200       200
      🟢 app.quillmd.com      302       302
      🟢 admin.quillmd.com    302>https://admin.quillmd.com/login/ 302 → https://admin.quillmd.com/login/
      🟢 pro.quillmd.com      410       410
    🟢 every judged co-tenant answers its expected status (4 distinct codes — the probe discriminates).
    --- containers
    cpt-studio-worker 4c81cc9292b6 Up 2 days 8000/tcp
    cpt-studio-web 4c81cc9292b6 Up 2 days (healthy) 127.0.0.1:9150->8000/tcp
    cpt-studio-converter 4c81cc9292b6 Up 2 days (healthy) 
    cpt-studio-db postgres:17.11-alpine Up 2 days 127.0.0.1:55451->5432/tcp
    --- image
    sha256:4c81cc9292b6b5c138bbc3c032db7cb80a7816cc60a01f985512d3173a7ccd30 816045c7264481bc6956285e1ca89991b9fcec2f
    --- ingress
    b3ab66023547790e861c3d12b39d8b268de8748ba6453f830194a4df6e4a3dbb  /etc/nginx/sites-available/quillmd
    e31ce5801a7bb7b9536138ed45249cc337e1b200a3d4abe3e420e1add7e92792  /etc/nginx/sites-available/quillmd-cpt
    quillmd-cpt link /etc/nginx/sites-available/quillmd-cpt
    admin.quillmd.com served: admin.quillmd.com cpt.quillmd.com
    cpt.quillmd.com served: admin.quillmd.com cpt.quillmd.com
    app.quillmd.com served: admin.quillmd.com app.quillmd.com pro.quillmd.com quillmd.com www.quillmd.com

## Expected changes, per phase

Every phase, both preflights, cert, passages, license-note and verify included, ends, beside what its bullet says, by
appending one line per one-shot and root-helper run it made to /var/log/cpt-studio/oneshots-<date>.log (root 0600),
through one more root-helper run; the receipt's oneshot_log reads written true. That helper deletes only its own files
there dated more than 14 days back. "None" and "nothing changes" below are apart from this and the receipts.

In numbers, fixed before the act (RELEASE-2-SPEC 9.3): **web** - new image ids; 4 web processes instead of 2; the memory
limit 1g instead of 768m; 4 database connections from the web's address instead of at most 2, kept since its processes
started for the web's first hour (after it each process renews its connection at its first request past the hour and
holds none until a request runs a query: at most 4, none older than the web) instead of younger than about 90 s;
**migrations** - 0019, 0020 and 0021 applied, 5 valid indexes; **vhost** - a
new sha, with one map entry and one comment changed (19 lines: 13 added, 6 removed), and no zone changed;
**converter** - a new image; **contract** - the client version customer-2026-11-26; **sessions** - 0 ended;
**records** - `member.list` rows now carry `encounter_ids`, one per document they served; **events** - 0 security events
from the act (the scheduled maintenance's own aside, below); **clinical counts** - unchanged.

- **preflight:** none. Its receipt records the baseline: the coupling after (the quillmd vhost b3ab66023547...;
  quillmd-cpt e31ce5801a7b..., 816045c72644's HTTPS stage for 9150, behind the installer's link, naming both hosts on
  443); 9150 held by cpt-studio-web alone, 9151 free, no cpt-studio-web-next; 55451 the database's; both names resolving to
  A 147.189.172.8 alone; the pinned helper and postgres images present; exactly one ACME account and the webroot writable;
  co-tenant routing and https://app.quillmd.com/health/; scripts/check-cotenants.sh passing; no task of uid 10150 or
  10151 outside CPT Studio; the coder's Anthropic source root 0600 in a root 0700 directory; at least 10 GiB free on /.
  <!-- install.py: phase_preflight, read_coupling, coupling_problem, web_port_layout, foreign_uid_tasks -->
- **image:** a new local image cpt-studio:`2008ffddc946`, built from git archive of the revision's cpt-studio/ and labelled
  with the revision. Before anything is built, every migration after 0005 is read (with ast) and must be additive for a
  pair that does not know it: 0019, 0020 and 0021 pass ("an index (writes are not refused)"). Then: the revision label,
  user 10150:10150 and the baked release; `manage check`; the WSGI load and the worker's command
  (`import cptstudio.wsgi, studio.management.commands.run_worker`) as the image's own user on a read-only root, which warms
  both URLconfs and every template (R2-4, R2-5); `soffice --version` naming LibreOffice; anthropic 2.11.0; the conversion
  gate; the converter's self-test ("cpt-studio converter self-test: ok, a PDF of ..."). cpt-studio:816045c72644 is kept.
  <!-- install.py: phase_image, migration_safety, migration_verdict (0019-0021 safe, read at ccb350d0b), image_soffice,
  image_anthropic, image_conversion, image_converter_self_test -->
- **converter:** the convert volume and its root (10151:10150 0750) re-asserted; the running cpt-studio-converter of
  816045c72644 is not this revision's, so its log is kept ids only (/var/log/cpt-studio/containers/converter-816045c72644-<UTC>.log),
  it is stopped with 80 s for a conversion in progress, removed, and cpt-studio-converter is started from
  cpt-studio:2008ffddc946 with release 1's seal (network none, no environment file, no files volume, no credential, user
  10151:10150, read-only root, every capability dropped, no new privileges, 1536m without swap, 128 pids, a 1g /tmp
  tmpfs, two CPUs, restart unless-stopped, the convert volume alone): healthy with no restart; the receipt's state
  `replaced`. A Word conversion asked for in the seconds between fails as busy and can be retried. From here release 2's
  refusals apply to every fresh conversion; release 1's worker still running reads the refusal's kind alone and shows the
  general sentence.
  <!-- install.py: phase_converter (:7099-7137), keep_container_log, converter_args, wait_converter, CONVERTER_STOP_SECONDS -->
- **cert:** the stage it stands on read first - `served`: quillmd-cpt e31ce5801a7b..., recorded by release 1's app
  receipt, proxying to 9150; the coupling (after); both HTTP-01 routes proven; one certbot run with
  `--keep-until-expiring`: no order unless due; the receipt records the lineage's paths (the receipt https-vhost requires).
  Every other lineage and the ACME account unchanged.
- **https-vhost:** quillmd-cpt replaced in place by this revision's HTTPS stage for 9150, the port cpt-studio-web
  publishes: STAGE_9150 over e31ce5801a7b... (a stage release 1's app receipt recorded, proxying to 9150 and naming the
  admin host on 443, as the phase requires); the coupling stays after; nginx -t with no new warning; one graceful reload;
  verified through the public path while 816045c72644 serves: https://cpt.quillmd.com/health/ answering that revision's
  digest, the admin host's answers, the 421 guard, each host on the other's connection, http://cpt.quillmd.com/ 301,
  both HTTP-01 routes, co-tenant routing and app.quillmd.com as the first preflight recorded. On any failure the replaced
  bytes are written back and nginx reloaded with them. The TLS policy is probed and recorded, never undone (D27). From
  here a search would count only in cpt_all (release 1's web has no search route: it answers 404 there).
  <!-- install.py: phase_https_vhost (:9781), publish_vhost, https_checks, tls_policy_report -->
- **preflight again (TAG after-https-vhost):** none; its receipt records the after-republish baseline: quillmd-cpt
  STAGE_9150 behind the installer's link, the coupling after, 9150 active and 9151 free, the new converter running.
- **Before app, read-only on the live database** (pre_app_r2.sh, with DECLARED_BASELINE
  /home/claude/cpt-r2-20261125/release/declared-baseline-20261128.txt; no copy of live is made): the declared
  baseline file (mode 0600 or 0400) equal, exactly, to this declaration's Baseline block from its read_at line up to the
  co-tenants reading; every applied row of live's django_migrations against the migrations on disk in
  cpt-studio:2008ffddc946 (a throwaway container cpt-r2-rh-migrations-<stamp>, no network, no database, MigrationLoader with
  no connection): the pending set exactly studio.0019_r2_document_lists, studio.0020_r2_run_lookups and
  studio.0021_r2_round_sweep, nothing applied on live missing from the image; baseline_r2.sh read again into a kept
  reading (named with its sha256 in the log: app's counts and the post-check are judged against it) and compared with the
  declared baseline by baseline_compare_r2.py - equal but for the rows set aside, and the coding rows only as a member's
  finished coding moves them (Baseline, above; each moved row named); the gates: jobs_active 0, jobs_code_active 0 and
  runs_reserved_or_sending 0 (a code job queued or running, or a send in flight, is a wait: a preflight and pre_app_r2.sh
  again, each under the same new TAG, once it has ended and the window is quiet, and that run can pass - the lead's
  rulings Q7, D-R2-53, and R3P-4, D-R2-55; review scripts-2 and round 3 scripts-2),
  runs_unreconciled_unknown 0, no reading job queued or running, the last audit event at least 600 s old,
  encounters_round_state_outside_eight 0, each of the four tables' rows at most 100 times its declared count (section 6:
  more is a stop, the index builds re-measured at that size on the test server and this declaration amended), the
  database's own cgroup reading memory.swap.max 0 and memory.max 536870912 (verify requires both after app; a host
  daemon-reload resets the swap limit and this act has no db phase to set it again), the serving web's database
  connections at most 2, each younger than 600 s; no cpt-r1-rh-* or cpt-r2-rh-* container running. Its log ends
  "PRE-APP PASS".
  <!-- pre_app_r2.sh: steps 1, 3, 4, 5 (its header) -->
- **app (the blue/green switch, from 9150 to 9151: the receipt's details.ports):** before anything starts - the coupling
  read again, the converter of this revision running healthy and sealed, the database, the coder's credentials copy read
  by the application's own loader with no network. **Migrate applies exactly studio.0019_r2_document_lists,
  studio.0020_r2_run_lookups and studio.0021_r2_round_sweep**, the one-shot waiting at most 5 s for a table's lock (up to
  three more attempts, 10 s apart, on a lock timeout alone): each a plain CREATE INDEX on one table in its own transaction
  (a SHARE lock: writers to that table wait while it builds, readers never do; 8.9, 6.9 and 3.0 ms at live's sizes).
  No existing row is changed; django_migrations gains 3 rows and no other existing table one (no model is added, so
  Django's post-migrate step adds no content type or permission). Then, read and recorded, never refused on: the stages
  of a kind this worker does not run; no design v1 row (refused otherwise); the install counts (encounters and those
  coded, jobs by kind and state, provider runs by purpose and state, unknown outcomes and runs in flight, the four tables
  of 0016, standing holds), which must equal the rows of the reading pre_app_r2.sh kept (named with its sha256 in the
  pre-app log: the Baseline block's but for the set-aside rows and the coding rows a member's finished coding moved; the
  lead's rulings Q7 and R2P-4, D-R2-53, D-R2-55), coded included (baseline_r2.sh's encounters_coded). The switch, with an availability record of https://cpt.quillmd.com/health/ every 0.5 s from before
  S1 to the end of S5:
  - **S1** cpt-studio-web-next starts on 127.0.0.1:9151 (1g without swap, 128 pids, read-only, no bind mount), its four
    processes forked from the warmed master, and answers /health/ there with the revision, its sign-in page and every
    static file it names, and the admin host's own answers on its loopback port;
  - **S2** the old worker parked (`docker stop --time 3600`: its current stage finishes, nothing new is claimed); 816045c72644
    and this revision share release 1's session policy, so no session is ended and the receipt carries no
    sessions_ended;
  - **S3** quillmd-cpt's upstream switched: STAGE_9150 replaced atomically by this revision's stage for 9151, STAGE_9151,
    the two differing in their proxy_pass line alone (switch.vhost_sha_before and switch.vhost_sha_after); nginx -t with
    no new warning; one graceful reload; verified through the public path: /health/ answering `release_digest`
    `d730927df8f953c8` and no release, the admin host on the cpt-studio certificate with its answers, the 421 guard, each host
    on the other's connection, co-tenants and app.quillmd.com as the preflight after https-vhost recorded. From here a
    release-1 tab's next customer API call answers 409;
  - **S4** the new worker starts with the coding step live at effort "high", the Anthropic copy mounted read-only into it
    alone, the convert volume mounted read-only, told the socket and that the converter is required; it loads the SDK
    at its start; from here a stored conversion is checked before it is reused (C8);
  - **S5** the old web drained (at least 130 s, until 10 quiet one-second samples, at most 600 s), stopped (30 s), parked
    as cpt-studio-web-previous, and cpt-studio-web-next renamed cpt-studio-web;
  - **S6** the stored list states recomputed with this revision's derivation (state.py changed by extraction only: none
    is expected to change), then the parked pair's logs kept ids only (/var/log/cpt-studio/containers/web-816045c72644-<UTC>.log
    and worker-816045c72644-<UTC>.log, root 0600) and the parked pair removed (its image kept).
  Once its migrate has applied a migration, app has had its one attempt under this declaration, however it ended:
  pre_app_r2.sh then stops (the pending set is no longer 0019 to 0021) and act_r2.sh refuses a second app; the way on is
  a new declaration. After a failure at S5 or S6 switch-back is refused too (it needs a successful app receipt).
  <!-- install.py: phase_app (:7322-7369), migrate_bounded (:7307, MIGRATE_LOCK_TIMEOUT 5s, MIGRATE_LOCK_RETRIES 3,
  MIGRATE_RETRY_PAUSE 10), install_counts (INSTALL_COUNTS), switch_services (S1-S5 at :5945-5970), service_args
  (hardening(*WEB_LIMITS) for the web), sessions_end_needed, switch_upstream (:5672), drain_web, RECOMPUTE_STATES,
  retire_parked, keep_container_log -->
- **The daily maintenance** (release 1's, D3, on its own schedule): the worker runs it once a day under an advisory lock
  and the weekly originals check once a week, each due by the time of its last SecurityEvent. If a due time falls inside
  the act, the old worker before S2 or the new one about 60 s after S4 runs it, with its records (maintenance.daily and
  maintenance.daily_files_removed, maintenance.originals_verified on the weekly day): release 1's standing behaviour,
  declared and judged in release 1's act, not this one's. post_check_r2.sh reads those records by name and count; any other
  security event since the Baseline reading is a finding. The last daily run's time is read with the baseline
  (last_maintenance_daily and last_maintenance_weekly, 2026-11-27T19:05:00Z and 2026-11-25T19:04:14Z in the Baseline block at 2026-11-28T09:40:41Z, as read before the owner's message (lead/STATE.md, 09:10:42Z): next due about 2026-11-28T19:05Z to 19:06Z and 2026-12-02T19:04Z, neither inside the told hour), so the window can be placed away from the
  next due times.
- **passages:** the three committed files (byte-identical since 816045c72644: studio/reference/) imported by the
  application's idempotent importer, one one-shot each, after `manage migrate --check` passes: nothing new.
- **license-note:** no reference source holds the old note (the Baseline block's md5 rows): "no reference source holds
  the old licence note; nothing changed", updated 0.
- **verify:** nothing changes. Against the preflight after https-vhost: quillmd-cpt this revision's stage for 9151, the
  port the running web publishes (STAGE_9151), the quillmd vhost the after state, every other sites-available file, the
  links, nginx.conf and conf.d as recorded; routing, app.quillmd.com and the co-tenant check unchanged; the co-tenants'
  containers the same running containers; no volume gone; no other lineage changed; the database running, labelled,
  loopback-only, its cgroup allowing no swap and its two settings read panic and terse; the web and worker of this image
  hardened (memory and swap equal, so no swap; the web on 9151 with no bind mount; its 1g is read by post_check_r2.sh);
  the converter of this revision sealed and healthy; nothing parked or
  incoming left; the HTTPS checks for this revision; both HTTP-01 routes; no foreign task of uid 10150. The TLS probes
  again, recorded (D27).
  <!-- install.py: phase_verify (:10309-10420) -->

**Database deltas against the baseline:** after app, passages, license-note, verify and the live check, exactly these,
against the reading app ran on (pre_app_r2.sh's kept reading: the Baseline block's rows, but for the set-aside rows and,
after a member's finished coding, the coding rows that run named) (post_check_r2.sh's expected-deltas file,
/home/claude/cpt-r2-20261125/release/expected-deltas-20261128.txt, 0600, lines `<key> <before> <after>`, made from
this committed table in the act checkout and never typed, with
`(umask 077; awk '/^[*][*]Database deltas against the baseline:[*][*]/{d=1} /^The rows set aside/{d=0} d && /^    [^ ]/{sub(/^    /,""); print}' /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128/docs/foundation/mutations/20261128-cpt-studio-release-2-install.md > /home/claude/cpt-r2-20261125/release/expected-deltas-20261128.txt)`;
post_check_r2.sh refuses (exit 2) a deltas file, revision, stage digest, start time, pre-app log, or a reading that is not
the one the pre-app log names by its path and sha256, that is not this declaration's; and an app or image receipt not
under this declaration's path and sha256 (the lead's ruling R3P-3)):

    studio_migrations 18 21
    studio_migration_last 0018_r1_availability 0021_r2_round_sweep
    index studio_enc_ws_queue absent valid:studio_encounter
    index studio_enc_ws_time absent valid:studio_encounter
    index studio_round_open absent valid:studio_codinground
    index studio_run_in_flight absent valid:studio_providerrun
    index studio_run_round absent valid:studio_providerrun

The rows set aside by the comparison are those named under Baseline; every other row of the reading app ran on unchanged: every
count, every account, membership, workspace and category, the password-hash digest, every audit event count, the
encounter states, the jobs and runs, the reference sources and passages, the 0016 tables, release 1's tables but the five
set aside, encounters_coded, encounters_round_state_outside_eight 0, jobs_code_active 0, the three tables' rows, the
database container's cgroup and HostConfig rows. post_check_r2.sh (DECL_FILE the committed declaration in the act
checkout; STAGE_9150 and STAGE_9151 above; PRE_APP_LOG the pre-app log act-r2-app.log names, by its absolute name, ending
PRE-APP PASS and naming its kept reading; ACT_STARTED the start line of the act's first image log: act-r2-image.log, or
after a continuation the earliest kept act-r2-image.decl-<digest>.log) judges both directions and exits
non-zero on any finding: /health/ through
nginx status ok, database ok and the digest `d730927df8f953c8` with no release; the act checkout's co-tenant check; the
ingress read back (the quillmd vhost the pinned after state; quillmd-cpt behind the installer's link naming both hosts on
443 and its sha256 STAGE_9151, cpt-studio-web publishing 127.0.0.1:9151 and app's receipt reading 9150 to 9151; the search
entry exactly once and every zone line as release 1's stage declares it; admin.quillmd.com and cpt.quillmd.com served the
cpt-studio certificate; app.quillmd.com still QuillMD's; https://admin.quillmd.com/ 302 to /login/); release 1's controls
(the two settings panic and terse; the converter on this revision's image, network none, healthy, 10151:10150,
read-only root, the convert volume alone and no secret's name in its environment; ops-agent holding no standing grant);
release 2's reads (the five indexes valid on their tables and 0021 the last migration; the web 1073741824/1073741824 with
128 pids, started at S1, RestartCount 0, not OOMKilled, memory.events oom_kill 0 - 9.8's switch-back reading, only what
the kernel and Docker report (the lead's ruling R2P-2, D-R2-55); its gunicorn processes in the kernel's process table
(docker top) exactly one master and four workers, each worker started by S3 - a younger worker replaced one after a
kill, an exit, a timeout or gunicorn's designed recycle (deploy/gunicorn.conf.py max_requests), which a flood of
requests can reach and nothing here tells apart, so it is a stop until judged, never a switch-back by itself (review
round 1 truth-1's round-3 check); gunicorn's lines on the web's stderr read and printed, never judged (a client's text
can write a whole line of any of gunicorn's forms onto that stream, a traceback printing a multipart boundary with %0A
decoded, and docker logs keeps only the newest ~50 MiB of the web's output, so a flood can push the start's lines out;
stdout's access lines and Django's lines are not read: review truth-1, scripts-9), memory.current and memory.peak
printed; the worker running this revision since S4, RestartCount 0, not OOMKilled, memory.events oom_kill 0 (review
round 2 safety-4: a worker restarted or killed for memory is a stop until judged); the web's database connections, read inside the web's
first hour, exactly 4, each no older than the web, the oldest older than 90 s, and read after it at most 4, each no older
than the web (review scripts-8); every member.list row since S4 naming exactly as many documents as its count, and at
least one naming some; no security event since the Baseline reading but the scheduled maintenance's own (review
scripts-11); the record equation since S4, per kind - the 200 and 304 answers on the list and search,
the detail, the document's original or view (one sum: the inline view and the download share a route), the report
download and the bundle equal to the served rows plus the counted repeats (G1, the lead's ruling: member.inline and
member.download judged as one count against the view's route, since no log field separates them); app's install counts
equal to the reading app ran on, 9150 to 9151, every availability sample 200, no session ended, coding live at effort
"high"; nginx's error log since the act began with nothing buffered to a temporary file (nginx's own words at a line's
start) and every access line with a request id, every file that holds that span read - the live file and its rotated ones,
.1 and .N.gz (nginx rotates daily at 00:00 UTC), and a span its files do not reach back to whole a finding, never a pass
(review scripts-0, safety-0); and the phases after app, from the installer's own receipts: the newest passages,
license-note and verify receipts of this revision under this declaration each ok true, passages after app, license-note
after passages, verify after license-note (review scripts-5; release 1's verified(), gone with its manage acts), and a
verify that compared with a preflight taken after app ended named, what app changed among the items verify alone reads
then judged by hand (review round 1 scripts-5's re-test)). Every receipt it reads names this declaration by its path and
its sha256 (the receipt's door.declaration and door.declaration_sha256: the lead's ruling R3P-3, D-R2-55): after a
continuation under a new declaration, image and converter ran again under it (the lead's ruling R2P-5), and act_r2.sh
refuses app until they did. A non-zero exit stops the act until it is judged; when the comparison itself differs it lists every audit event since the
baseline's last one (its since the Baseline block's last_audit row, which runbook item 8 requires before the commit;
without one holding a time the listing is not reached and the post-check says so: the second rehearsal's G4), and a
member's own activity is named in the report.
<!-- post_check_r2.sh: bound(), the reading app ran on (READING, its sha256), the comparison (rows(), aside(), the
expected loop), health, the co-tenant call, the ingress block, the vhost block, the release-1 controls, the release-2
reads (GUNICORN_LINE, the connections' two windows), the counts block, the log reader (run_of, cat_run), the record
equation and the phases' receipts -->

## After the install: the live check (ordinary use, not a phase)

cpt-r2-20261125/release/live_check_r2.py, once, after verify, as
`python3 -I /home/claude/cpt-r2-20261125/release/live_check_r2.py --tree /opt/meddoc-pro/.worktrees/cpt-r2-act-20261128/cpt-studio --revision 2008ffddc946be142e8b856b4003e4c4959b1dd7 --customer-credentials /home/claude/.cpt-studio/agent-credentials.json --encounter 6c450473-ceb7-4f06-8660-d5794a3cb777 --out /home/claude/cpt-r2-20261125/release/act/live-check-20261128`
(the walk's own synthetic review agent; the file is the installer's credentials document, read for the username and
password of its one account, nothing of either printed; the evidence folder must be new). It refuses (exit 2), before any request, an --encounter
that is not one of the walk's two recorded synthetic documents - its WALK_DOCUMENTS, the same two walk_check_r2.sh
pins, one list in two scripts that tests/t_docs.py holds equal (the lead's ruling R4P-3, D-R2-57; review round 4
safety-0, scripts-2) - so a document a member uploaded is never read, and its summary names which of the two it read
(gi-01 or gi-02), never an id. The walk document was checked
at the Baseline reading, read-only (the lead's ruling Q9, D-R2-55: walk_check_r2.sh - its id one of the walk's recorded
synthetic documents, gi-01 6c450473-ceb7-4f06-8660-d5794a3cb777 or gi-02 255e92ac-c7c0-4702-b2d0-2fa221aaed87 (D361),
and the document made by one of its practice's agent members, never only a document that exists: the lead's ruling
R3P-5, D-R2-55, review round 3 safety-0 - its practice, its agent members - each one whose oldest active
membership is that practice, the practice the lists serve (review round 2 safety-3) - and its place
in the Documents list, which the live check pages five times at most): `bash /home/claude/cpt-r2-20261125/release/walk_check_r2.sh 6c450473-ceb7-4f06-8660-d5794a3cb777` at the Baseline reading (2026-11-28T09:40:42Z, lead/walk-check-20261128.txt): walk_recorded gi-01; walk_encounter present; walk_workspace gastroenterology Gastroenterology; walk_agent_members review-agent; walk_created_by review-agent agent; walk_rank 10; "the walk document (gi-01) is present, made by its practice's agent member review-agent (the practice's agent member(s): review-agent), and the live check's five pages of 50 reach it (10 newer)"; WALK DOCUMENT OK. Every connection is verified
against the system's roots and the host name. Its checks (9.6), each kept as status, header names, cookie names and
attributes, location and, for a JSON answer, its key names and row count - never a body, a title or an id: for each host
/health/ 200 with `release_digest` `d730927df8f953c8` and no release, no Server version, HSTS; on cpt.quillmd.com /ops/
signed out 404, /login/ and its `__Host-cptstudio_csrf` cookie, the sign-in and its `__Host-cptstudio_session` cookie,
/api/session 200; the page shell carrying a session whose keys are GET /api/session's, and naming its hashed static
files (app.js's hash this tree's, each 200 and immutable); the three lists 200 in the new shape; the walk's document,
looked for on the Documents list page by page (at most five), read once when listed; a search for a marker that
matches nothing answering an empty page; release 1's client header answering 409 client_outdated on a list and on the
search; /ops/ as the member 404; the sign-out 302 to /login/ and the ended session replayed 401; on admin.quillmd.com,
signed out, / 302 to /login/, /login/ 200 naming the console's four fonts by this tree's hashed names (each 200 and
immutable), /ops/people 302 to the sign-in, /api/session 404. It makes no view read; exit 0 only when every check passes.
<!-- live_check_r2.py: main(), page_ok, key_shape, static_ok, hashed -->
Its database footprint, by the code: studio_loginattempt +1, last_login set on the review agent, one session row and its
account link made at the sign-in and removed by the sign-out, rate windows for the sign-in's places and one for the
member's later pages and search (list.member), and one AccessRecord per list page, search and detail it read (at least
five); no audit event and no security event. Every row of it is set aside by the comparison; the record equation
counts it.

## The access log, the hour before against the hour after (counts and milliseconds only)

`bash /home/claude/cpt-r2-20261125/release/access_report_r2.sh act` (REV and DECL in its environment), once S3 + 1 h has
passed (it refuses before): the hour before S1 against release 2's web's first hour, from S3 - the switch, when release
2's web starts serving - to S3 + 1 h, both read from app's own receipt (details.steps.S1 and S3, cut to the second), never
typed and never app's end (review scripts-7: an hour after from app's end counted none of S3 to S6); per host and route
template with ids removed, the requests, the 2xx/3xx/4xx/5xx and 429 and 503 counts, the document view's answers by
status (304 among them), each route's p50 and p95 of nginx's own request time; then 9.8's reading, which the lead's
ruling R3P-1 (D-R2-55) makes a COUNT, stricter than 9.8's "a 5xx rate above the hour before": every 5xx release 2's web
answers in its first hour, from S3, to any request other than /health/ - on either host it serves (cpt.quillmd.com and
admin.quillmd.com, whose console code release 2 also changes: review round 3 safety-1) or any other host the vhost
logged, a member's, a stranger's or the act's own request alike - is listed (its time, method, route template with ids
removed, status), and so is a line whose status cannot be read; ANY one is STOP AND JUDGE (exit 1): an incident, in
which the lead decides switch-back or not, recorded, before anything else. A count cannot be diluted by traffic: rounds
2 and 3 found the rate held down by the availability record's samples, then by the live check's own twenty-odd
requests, a stranger's sweep or the console's traffic (review round 2 truth-0, scripts-0, safety-0; round 3 scripts-0).
The hour before's 5xx are listed beside it as context only, never judged; every request to /health/ - the availability
record's samples (every 0.5 s from S1 to the end of S5: about 292 in the hour after at release 1's timings, up to about
1,230 at the 600 s drain), verify's, the live check's and the post-check's reads, any monitor - is set aside in both
windows by the path nginx logged, its count and its 5xx printed and each 5xx of it listed (the lead's ruling R2P-1,
D-R2-55); /health/ is judged only where the act reads it - the availability record's own samples (S1 to the end of S5,
its end printed from app's receipt; step e requires every one of them 200) and the single reads of verify, the live
check and the post-check - so any other /health/ 5xx in the hour after, inside the record's span or after
the record's end (a monitor's) is judged by nothing but that listing: it is read by hand and recorded in the act's
report, each one (review round 3 scripts-3; round 4 scripts-0, safety-1). Every file that holds the windows is read: the live
cpt-studio-access.log and its rotated files by name (.1, .2.gz and on, each number once, none missing; nginx rotates its
logs daily at 00:00 UTC, /etc/logrotate.d/nginx), a .gz passing gunzip -t, back to one last written before the hour
before begins; when no line read is older than the hour before (what was read decides, never a file's time alone), when
one does not read whole, or when a file moved while it was read (each file's inode, and a rotated file's size, read
before and after: a rotation), it says it cannot tell and judges nothing (exit 3, a stop until read whole: review
scripts-0, safety-0 and their re-tests). Each line is split on its quotes first, so a
path holding a decoded space cannot shift the status (review safety-5). It prints no address, id, query string, user agent
or sign-in reference; a path that is not the application's own route words (ops/install.py ROUTE_WORDS) and ids, or that
has more than seven parts, is "other", and a method outside GET, HEAD, POST, PUT, PATCH, DELETE and OPTIONS is "OTHER", so
no stranger's text is printed (review safety-4). After the owner's answer,
`bash /home/claude/cpt-r2-20261125/release/access_report_r2.sh opens <the question sent> <his answer + 10 min>` reads his
window the same way against the same hour before S1: counts and timings, the view's answers by route and status, and a
5xx line that is counts only (9.8's rule is the first reading's); his window holds every member's requests, so the
view's answers are printed per sign-in too, each numbered in the order it first appears (the sign-in reference nginx
logs, which never leaves the reading: review owner-9's re-test). It refuses (exit 2), reading nothing, a window that
ends after a switch-back of this revision began - any switch-back receipt of it started since S3, whatever its outcome,
or one whose start cannot be read (the lead's ruling R4P-2, D-R2-57: the question was withdrawn, and his opens may
have been served by release 1).

## Then: the owner's own check (class c, asked once, after the live check, the post-check and the hour-after reading, and only while release 2 serves)

*"Release 2 is installed. When you have a minute, open three GI documents, going back to Documents between them, then
open the first one again. Do they open fast now?"* Asked in its own message, the last of its turn, after the live check,
post_check_r2.sh and `access_report_r2.sh act` (the question is what asks him to look: review owner-9, the lead's ruling
owner-9, D-R2-55; it ends the lead's turn, so both of 9.8's readings come first: the lead's ruling R2P-7; review round 2
owner-0), and only while release 2 serves: never after a switch-back (whichever rule or judgment decided it), when
release 1's pair serves and he is told the switch-back in one line instead, and neither the question nor the opens
reading is made under this declaration (the lead's ruling R3P-6, D-R2-55; review round 3 owner-1); nor while an
incident is open (a STOP AND JUDGE, or an objection after app: the objection stop below), when the question waits for
the lead's recorded decision (review round 3 owner-2's check). Before it is sent,
the session writes its own id and the question's words to /home/claude/cpt-r2-20261125/lead/STATE.md and sets a wake
for 24 hours and 5 minutes later (a background wait, as for S3 + 1 h: its notification is not his answer, but if none
has come by then, "no answer" is recorded and the act's report follows: review round 3 owner-0's check); the question's
time is read from the transcript and added there on the next input (review round 3 owner-0). Only a genuine message of
his that answers it is his answer: a task notification never is, nor a reminder, another session's message or a message
of his on another matter - any of those records nothing as his answer and starts no class-c step (an objection in it is still the objection
stop's incident), and the question is not asked
again (the lead's ruling R3P-6; review round 3 truth-3, owner-0: the harness wakes the session when any background task
ends, so the input that next wakes it is most often not his). The session that acts on his answer - this one, or a new
one reading STATE.md and the transcript from the question on - records its time and words in STATE.md and the act's
report, and runs the opens reading ten minutes after it, unless a switch-back was decided by then. A switch-back decided
after the question was sent and before the opens reading runs - before his answer, or in the ten minutes after it -
(whichever rule or judgment decided it, the incident an objection after app opens among them) withdraws the question:
the one-line switch-back message also tells him it no longer stands; the opens reading is not run (access_report_r2.sh
opens refuses a window that ends after a switch-back of this revision began); his answer, or a reply of his after the
switch-back, is recorded verbatim, with its time and the switch-back's, as his words, never as release 2's class-c
answer; and the question is asked again after a switch forward, under its new declaration (the lead's ruling R4P-2,
D-R2-57, and decision RH-7; review round 4 owner-0; round 3 owner-1's check). No answer within 24 hours of the question is recorded as "no
answer", which judges nothing: the opens reading is not run (so it is never asked to read an hour nginx's 14 daily
rotations have dropped), and a reply after it is recorded beside it, dated (the lead's ruling R3P-6). If he
says no, his answer is the next finding. The evidence is `access_report_r2.sh opens` over his window, from the question to
his answer + 10 minutes (above), by route and status only: his three first opens answer 200; his second open of the first
document is drawn from page memory after a 304 the server records (R2-15), so one 304 on the view is expected, and 0 (a
reload or a new sign-in between his opens wipes page memory, R2-18) is recorded as read, not a finding. His window counts
every member's requests: the 304 counts as his second open drawn from page memory only when one sign-in's view answers
in the window are exactly his four (200 3, 304 1); any other count is recorded as the window's, not as his, and not as
evidence for R2-15 (review owner-9's re-test).

## Must not change

Every encounter and every row of every table apart from the declared rows above (the three migrations' rows and five
indexes, the live check's footprint, the scheduled maintenance's own records, and a member's own activity, named in the
report); every account's kind, activity and memberships, every workspace and category, every operator grant row and
revocation, and every password hash (the digest); the decisions, coding rounds, exports, reference sources, facts and
passages; every release-1 control the post-check reads: the cookie names (`__Host-cptstudio_session`,
`__Host-cptstudio_csrf`), the policy headers (HSTS, no Server version), the console's 404 on the doctors' host,
/health/'s digest form (the release never named through nginx), the database's statement logging (panic and terse);
the database container (its id, image, ports, capabilities, mounts, limits and cgroup) and its data volume but for the
schema's three migrations and five indexes; the files volume; every file in /etc/cpt-studio/; every nginx vhost but
quillmd-cpt, the quillmd vhost staying the pinned after state b3ab66023547...; nginx.conf and conf.d; every
certificate lineage and renewal conf, and the ACME account; QuillMD's :80 block, its Caddy and its containers; the HTTP
answers and certificates of quillmd.com, www.quillmd.com, app.quillmd.com and pro.quillmd.com, and
https://app.quillmd.com/health/; admin.quillmd.com's console answer (302 to /login/) and its cpt-studio certificate;
the co-tenants' routing; every image (nothing is removed; release 1's converter and its parked pair's containers are,
after their logs are kept).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0, the coupling after, with the baseline above; image exit 0
with the image id recorded, 0019, 0020 and 0021 judged safe, the conversion gate's %PDF- and the converter's self-test
line; converter exit 0, state `replaced` (the replaced container 816045c72644's, its log kept), the volume root 10151:10150
0o750, healthy; cert exit 0, stage `served` (e31ce5801a7b...), the lineage's paths recorded, no other lineage or account
changed; https-vhost exit 0, vhost_sha256 STAGE_9150, upstream_port 9150, replaced e31ce5801a7b..., the coupling after,
every public check passing, details.observations one entry, attempt 0, status 200, the TLS findings recorded; preflight
again exit 0; pre_app_r2.sh ending PRE-APP PASS; app exit 0 with migrate applying exactly 0019, 0020 and 0021
(migrate_attempts 1; 2 to 4, each after a lock timeout alone, are declared above and named in the report), the install
counts equal to the reading pre_app_r2.sh kept (its log names it, with its sha256: the lead's ruling R2P-4), the switch applied (details.ports 9150 to 9151), no sessions_ended,
switch.vhost_sha_before STAGE_9150 and switch.vhost_sha_after STAGE_9151, the availability record with no sample other
than 200, the drain not bounded out, no list state changed, logs_kept for the web and the worker, coding live at effort
"high"; passages exit 0 (three files, nothing new); license-note exit 0, updated 0; verify exit 0; the live check, every
check passed; post_check_r2.sh with /home/claude/cpt-r2-20261125/release/expected-deltas-20261128.txt exit 0,
unexpected differences 0; the access report, no 5xx from release 2's web in its first hour to any request but /health/
(any one an incident, judged by the lead and recorded: the lead's ruling R3P-1); scripts/check-cotenants.sh.

## Rollback per phase, and its limits

- preflight, verify, image, passages, license-note: nothing to undo (but the log lines every phase appends under
  /var/log/cpt-studio, which stay; the image is kept).
- converter: not undone by any phase of this declaration. Before S4 release 1's worker uses release 2's converter and shows
  the general sentence for a refused file; release 1's converter is never started again after S4 (below). Taking the
  converter back to release 1's before S4 would be release 1's own converter phase, under a new declaration.
- cert: nothing to undo.
- https-vhost before success: the installer's own undo writes back the replaced bytes (e31ce5801a7b...) and reloads. After
  success the stage stays and serves 816045c72644's web as it serves this revision's (the search entry answers 404 there).
  Taking it back is 816045c72644's own https-vhost of its template, under a new declaration.
- app before the switch (S1, S2): the incoming web removed and the old worker running again (one whose stop was asked for
  and not finished still runs then, and exits once its stage ends: it is started again by hand, as the receipt says).
  After the switch (S3, S4): when it can finish, the installer's own undo returns the 816045c72644 pair, never stopping the
  serving web (ops/INSTALL.md's failure matrix); when a close names a record or the undo cannot finish, the layouts and the
  way back are release 1's (rollback-app by hand through the door, act_r2.sh refusing it; no worker started by hand but
  by a decision recorded in words; let nobody reload nginx before the recovery: a reload moves traffic to the port the
  file names), under a new declaration. S5, or a kill once the new worker runs: the new pair serves and codes and nothing
  is undone; S6 (the recompute, a log copy or a removal failing): the same, with the parked pair left; after either the
  act ends and what is left is cleared by hand as ops/INSTALL.md's Recovery notes say, under a new declaration. 0019 to 0021,
  once applied, stay applied through every failed app, undo and switch-back (migrations are not reversed; release 1's pair
  runs on them, section 6, D-R2-58).
  <!-- install.py: undo_switch, undo_switch_s3, undo_switch_s4, finish_back, phase_rollback_app, keep_layout -->
- After a successful app the incident path is `switch-back` (RELEASE-2-SPEC 9.7): a fresh preflight, then act_r2.sh
  switch-back with SWITCH_BACK_DECISION_FILE naming the 0600 file in /home/claude/cpt-r2-20261125/release/reasons/ that
  holds the recorded decision (written with an editor or the Write tool and made 0600 with chmod, never on a command line:
  the runbook's incident path; the lead's ruling R2P-3; review round 2 truth-1's and safety-2's checks), arguments `--provider-mode disabled --coding-mode live
  --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` (the pair it replaced, 816045c72644, in its own
  modes): the 816045c72644 pair returns on 9150 through this revision's stage for 9150 (STAGE_9150), which stays.
  - Release 1's web and worker run on the new indexes, which stay: release 1's Django suite passed on a database
    release 2's migrations built (1,438 tests OK, 1 skipped, as on its own schema in the same session), and its
    statements keep their plans or take release 2's indexes for faster ones (D-R2-58, lead/i1-8/RESULT.json).
  - The release-2 vhost stays and works with release 1: the search entry is harmless (release 1 answers 404 to that path).
    Taking it back is an https-vhost of release 1's template.
  - The release-2 converter stays. Release 1's worker shows the general sentence for a refused Word file; no content is
    dropped silently in a fresh conversion. A round that reuses a stored conversion is not checked by release 1's worker
    (that check is release 2's worker's, C8). A round begun on release 1's worker and resumed after the next S4 finishes on
    its own PDF (the trade-off above).
  - **The converter is never rolled back to release 1's after S4.** Release 1's converter converts a file only release 2
    refuses, with its import or object left out, and release 2's worker would code that PDF
    (`test_release_1s_worker_and_converter_meet_release_2s_across_the_switch` pins that direction; D-R2-39).
  - Open release-2 pages meet release 1's 409 and reload into release 1's page. Nobody is signed out.
  - A document whose coding is still queued or running at B4 or B7 is not coded by release 1's worker. B4 closes every
    coding job created or started since release 2's pair was created - an upload release 2's web accepted while B3
    waits for its worker's current documents among them - and B7 every one created since B4, on either web - an upload
    on release 1's page during B6's drain among them. Each is failed with the installer's note and its round cancelled,
    so the document reads Stopped until a member presses Resume (release 1's own Resume queues the round again, reusing
    any read already paid for); a round with a request in flight is failed as unknown and waits for an operator's
    reconcile (install.py CLOSE_STAGES, close_undone_stages; ops/INSTALL.md, Known limits 8). The switch-back receipt's
    details.closes (first and second: stopped, unknown, code_failed, rounds) count them, and the act's report names
    those counts (review round 4 safety-2).
  - WEB_LIMITS gives release 1's web 1g, which it does not need and does not mind; release 2's installer starts release 1's
    pair at effort "high" (D-R2-49; D434 measured release 1's image at "high").
  - It refuses, starting and stopping nothing, while this revision holds records an older revision would act on or show
    wrongly, and without a fresh preflight. A closed practice or a destroyed document does not refuse it: release 1's
    D407 rule (disposal_refusal) refuses only a way back to a revision without studio/disposal.py, and 816045c72644 has
    one (ops/INSTALL.md: a switch-back to a revision that has disposal is not affected; review truth-4).
  - A switch-back is an incident: short, recorded, and followed by a switch forward under a new declaration (act_r2.sh
    refuses app after a successful switch-back; pre_app_r2.sh would stop on the applied migrations).
  - The owner is told the switch-back in one line, told, not asked; the class-c question is not sent under this
    declaration - one already sent whose opens reading has not run (unanswered, or answered less than ten minutes
    before) is withdrawn in that same line, and his answer or a reply of his after it is recorded as his words, never as
    the class-c answer (the lead's ruling R4P-2, D-R2-57, and decision RH-7) - and its opens reading is not
    made (the lead's ruling R3P-6, D-R2-55; review round 3 owner-1; round 4 owner-0).
  <!-- install.py: phase_switch_back (:7465), switch_back_target, converter_problem(prev_image), service_args
  (WEB_LIMITS, CODING_EFFORT); act_r2.sh switch-back ARGS -->
- A changing phase whose failure is proven twice (its log records the door's non-zero exit, and the installer's receipt
  written inside that run says ok false) runs again only through act_r2.sh with RERUN_DECISION_FILE naming the 0600 file in
  /home/claude/cpt-r2-20261125/release/reasons/ that holds the recorded decision (a switch-back's rerun names
  SWITCH_BACK_DECISION_FILE as well), after a
  preflight newer than the failed run (app only when it failed before its migrate applied anything: then pre_app_r2.sh
  again with TAG, which passes only while 0019 to 0021 are all still pending); the failed run's log is kept as
  act-r2-<phase>.attempt-<n>.log. A run whose end is unknown - no exit line, no receipt, or a receipt saying ok - is
  never repeated by act_r2.sh: it is a stop, its outcome read from the vhost's port, the containers and the receipts, and
  decided by hand.
- The receipts and the images stay. This act makes no copy of live, so it has no restore point (D409, kept); nothing
  here takes back a migration (indexes only: dropping them is never needed for any pair).

## What is not claimed

- That Firefox and Safari were measured (D-R2-24: measured in Chromium only).
- That live was load-tested: it never is; the after-install timings come from the access log's own numbers, on little
  traffic (the hour after, and the owner's window).
- That a 5xx in release 2's first hour is release 2's own fault: the count lists every 5xx the vhost logged from S3 to any
  request but /health/ - a stranger's provoked one, the act's own, or one nginx logged at the end of a request the old
  web began before S3 among them - and the lead judges each (the lead's ruling R3P-1: STOP AND JUDGE, never a pass).
- That /health/ is judged across release 2's first hour: the availability record judges its own samples, S1 to the end
  of S5, and verify, the live check and the post-check their own single reads; any other /health/ answer in the hour
  after (a monitor's, inside the record's span or after it) is set aside from 9.8's count and judged by nothing but its
  listing, read by hand (the lead's ruling R2P-1; review round 3 scripts-3; round 4 scripts-0, safety-1).
- That the console is read signed in after the install: admin.quillmd.com's 5xx count in 9.8's reading, but no check
  signs in to it (the live check and the post-check read it signed out; review round 3 safety-1).
- That the bench's gates are as strong as their names (D-R2-49): records.fail_closed misses the frame fallback's bytes;
  records.marker and marker_in_files see the search words only as typed; left.no_hash_header passes a sha256 written as
  a UUID; bluegreen.x3 cannot fail for two of its three clauses; plans.no_seq_scan counts a whole-list COUNT that
  D-R2-37 accepts; bluegreen.x2 is blind to its own case (integrated round 2, exact-0). Their claims are carried by the
  CI tests the integrated rounds strengthened, by FailClosedTests and by the lead's one-off checks; the bench fixes land
  as bench-r3 after B.
- That B met every row's gate as written: D-R2-54 (2) accepts rows in the open, each only within its written bound -
  quote-mark-P0 (B median <= 75 ms, the second click no worse than 1.1 A + 15), opaque-P1 (B <= 240 ms and <= 0.40 A),
  memory-signed-out (B <= A + 2.0 MiB), plans.no_seq_scan (the documents list's whole-list COUNT alone may Seq Scan),
  detail-10-p95, server-list-100 and session-18000 as "gain not shown" (B within section 8's 150, 30 and 20 ms and no
  worse than A in the same session), and the cold row as D-R2-50 declared; a value past its bound is a FAIL that stands
  (told to the owner in the one message: D-R2-54 (3); review round 3 truth-0); and two rows outside D-R2-54's list stay
  FAIL as B's third session measured them - documents-usable-100-P1 (B 209.1 ms against 0.6 A = 207.42 ms) and
  memory-list (B 139.5 MiB against A + 23.88 = 138.78 MiB) - not re-judged: release 2 proceeds with them by the lead's
  post-hoc decision, made with the values in hand and told to the owner with his stop (D-R2-60).
- That B ran on an idle host: during B's third session agents that only read and write files were allowed beside its
  driver - no test, suite, build, browser, bench, docker or image process (D-R2-59) - and the driver kept its own gates (a round
  starts at a 1-minute load of at most 5; a sample above 8 makes it INVALID: none was), the load logged every 15 s
  (laneM/b3/mem.log).
- That release 1's statements keep, on release 2's schema, the plans they had: D-R2-58 corrects section 6 - they keep
  their plans or take release 2's indexes for faster ones - and the check's declared Seq Scan clause failed as it
  stands (release 1's whole-practice list and its queue COUNT Seq Scan, identically on release 1's own schema), not
  re-judged; the switch-back claim rests on its time comparisons (the list 111 against 123 ms, the queue COUNT 8.7
  against 15.0 ms).
- That the tests guarding "search words never reach a URL, header, log or record" are closed: the integrated pass's last
  round showed four gaps in them (guards-0 HIGH, guards-1 to guards-3 MEDIUM), each with a mutant the tests miss; no round
  found a leak in the shipped code; the guard is rebuilt as a closed world in 2.1, before any real patient (D-R2-51),
  with round 3's ten lows.
- That the record equation holds for a document's poll (X-CPT-Poll writes at most one row a minute per sign-in and
  document): post_check_r2.sh judges a difference by kind, and a member's own poll is named in the report.
- That the no-swap limits outlast the host's next systemd daemon-reload (release 1's note, unchanged): a reload writes
  memory.swap.max back to max for the database, the web, the worker and the converter until each container starts
  again; nothing reads them between installs.
- That the TLS policy is in force on the shared listener (CPT's block is not its default server; D27).
- That nothing is spooled to disk at the edge on live beyond nginx's own error log holding no "buffered to a temporary
  file" line since the act began.
- That a Word file from a generator not measured here is accepted (the canonical package gate's known limit, class b);
  that LibreOffice's text from tracked deletions, literal IFs and unresolved references is kept out of the PDF the coder is
  sent (section 12, open).
- That the switch-back was rehearsed as the installer runs it: the rehearsal's back step (REHEARSAL.md step 11) runs its
  parts by hand through release 1's re-bound harness (start, stop, vhost, rename), never install.main's B2-B9
  (phase_switch_back: its hazard reads, B4's ingress checks, B4's and B7's closes and put-backs, the sessions' end,
  switch_upstream, drain_web), and starts release 1's pair with release 1's own service_args (web 768m, effort "max",
  coding disabled), not with this revision's, which a switch-back gives it (web 1g, effort "high", coding live; review
  safety-6). Whether those parts and the second switch forward ran on the revision's own image, and the coding pause with
  documents in progress: back (step 11) and again (step 12) ran in the second run, each exit 0 with every health
  sample 200 (each loop 300 of 300, read whole), by the rehearsal's own parts by hand - never install.main's B2-B9 -
  with release 1's pair under release 1's own service_args, on B's image (cpt-r2-test:a680d837b0d1,
  sha256:bb51667ac38f..., built from a680d837b) and release 1's (cpt-r2-test:816045c72644): the revision's own image
  only as far as b_stands_r2.sh's B STANDS and runbook item 2's run on the merge commit (REHEARSAL_MERGE_RESULT) show;
  the coding pause with documents in progress: not rehearsed (no tooling holds a document: the lead's decision RH-5, D-R2-61).
- That the rehearsal's three steps by hand ran - the bench's open, lists and office flows through the rehearsal nginx, the
  coding pause with a held document, and the package's read scripts' SQL on the rehearsal's own database: each is "not
  rehearsed" until run and recorded in its RESULT (the lead's ruling Q12, D-R2-55). The third ran: the first run's step 13
  (rehearsal-run1/RESULT.md: BASELINE PASS, PRE-APP PASS, the walk check's OK and its two STOPs, on release 1's stage)
  and the second run's (post_check_r2.sh's reads on B's web, each in its form but the audit listing, G4). The first two
  stay not rehearsed - the browser flows (no browser container; step 9 ran the load loop instead: the lead's decision
  RH-4, D-R2-61) and the pause with a held document (no tooling: RH-5, D-R2-61) - and so does the replacement of a running
  release-1 converter (the stage starts none: G2); the corpus, left out of the second run, ran in the run on the merge
  commit (CORPUS_74).
- That a member's coding between the Baseline reading and app is judged by more than its rows: the coding rows may move as
  a finished coding moves them (the lead's ruling Q7, D-R2-53), each moved row named in the pre-app log; what the coder answered is
  never read.
- That the installer's S1-S6 orchestration, certbot and DNS, the host's nginx build and co-tenant blocks were rehearsed
  beyond what REHEARSAL.md's record says.
- What the scheduled maintenance removes or rewrites if its due time falls inside the act (release 1's standing
  behaviour, read by count).
- Past the known limits written in cpt-studio/ARCHITECTURE.md, API.md and ops/INSTALL.md, and in the refutation
  dispositions (INT-ROUND1-FIXES.md, INT-ROUND1B-FIXES.md, INT-ROUND2-FIXES.md, INT-ROUND3-DECISIONS.md and the lanes').

## ePHI security evaluation (register A28)

<!-- Drafted by the release package builder from the specification's 9.3 list, the code at ccb350d0b and release 1's
evaluation. No agent signs it: the residual risk is the security official's to accept (D411: Kasra Rayat). -->

**What changes, and its effect on confidentiality, integrity and availability.**
- The list records now name their documents (stronger): every list page and search writes one `member.list` row naming
  the documents it served, in order, with its list and cursor - never the words searched.
- A tab keeps up to 6 PDFs and 24 MiB in page memory, as ArrayBuffers, overwritten and dropped at every end (sign-out,
  idle sign-out, a closed tab, `pagehide`): new handling, within the rule (D-R2-5).
- A re-open from page memory is recorded before it is answered, as `member.inline` with `shown_from` page_memory; a row
  that cannot be written answers 503 and nothing is drawn (D-R2-6).
- The search words travel in POST bodies, never in an address, a query string, a log line or a record; they are visible
  in `pg_stat_activity` only while the statement runs.
- The web's database connections live up to an hour (one idle server process per gunicorn process).
- Word (integrity): no document is coded with silently missing content. This holds for every round coded after the
  install but one begun on release 1's worker and resumed after S4, which finishes on its own PDF (the session's
  trade-off above, D-R2-39, D-R2-43; not an acceptance by the security official); the
  package check also covers rounds that reuse a conversion stored before the install (C8).
- Availability: faster opens and lists; a coding pause S2 to S4 (about 5 seconds when idle: 4.3 to 6.4 s S2 to S4 on this
  host's receipts, then the new worker's start; 60 minutes at most); a Word conversion asked for during the converter's
  replacement fails as busy and can be retried; a database that cannot be reached answers 503 with Retry-After, not 500;
  some Word files are refused with a message (the class-b change above).
- No new subcontractor; no vendor's terms, retention, model, endpoint or fallback change; the coder's effort changes
  ("high"), its endpoint and model do not; the BAA with Anthropic remains the owner's open contact, not yet signed (D401
  (c); D429's record).
- No access change: no account, role, membership, grant or session is changed by the act.

**The ePHI stores and flows touched (named, never their contents).** Stores: the cptstudio database in cpt-studio-db
(three migrations adding indexes; the read records growing as before, now naming the listed documents); the files volume
cpt-studio-files (mounted read-write into the web and the worker, as before: the web writes each upload, removes a
failed upload's file, and reads the originals and converted PDFs it serves; the worker reads each document it codes,
writes the PDF a Word document is converted to, and its daily run removes the files no row names; review truth-3);
cpt-studio-convert (the socket only) and the new converter's /tmp tmpfs; the browser's page memory (above); nginx's
buffers (memory); /var/log/nginx/cpt-studio-access.log and cpt-studio-error.log (the access log also counts the search's
POST, its words never in it); /var/log/cpt-studio/ (ids-only copies of release 1's converter, web and worker logs,
one-shot journals); the receipts directory /home/claude/cpt-studio-install-20261023 (this act's receipts: ids, counts
and digests; the directory also keeps, untouched by this act, the nine pre-app dumps D425 kept; the tenth copy it kept,
the 2026-11-24 rehearsal dump, is not in this directory but at
/home/claude/cpt-r1-20261124/lead/rehearsal/live/live-20261124T151549Z.dump (0600), also untouched by this act; the ten
may hold the documents of 2026-11-20, D352; review truth-8, owner-3); the audit's two files copied from live before
2026-11-23 and the browser evidence beside them, which D-R2-25 adds to D425's kept set and release 2 never opens or
reuses: /home/claude/cpt-admin-host-20261123/audit-20261123/work/perf/gi-rows.json and
/home/claude/cpt-admin-host-20261123/audit-20261123/work/verify-uploads-5/gi-rows.json (found by name, never opened);
the pre-app check's log (counts and migration names); the live check's evidence folder (statuses, header names and key
names); the access report's output (counts and milliseconds, by the application's own route words and ids). The live
stores may hold the documents of 2026-11-20 (document 01, section 9; D352), and, known and unchanged by this act, D429's
documents: made from a doctor's real charts, said by the owner to be changed to synthetic, never opened by any session;
D429's record flags that documents made from a doctor's real charts may still hold identifiers (dates, record numbers)
and that no Anthropic BAA is signed yet (the lead's ruling Q3, D-R2-55; review owner-7). Flows: the browser to nginx to the web
on both hosts; the web and the worker to the database and to the files volume; the worker to the converter over a socket
with no network; the worker's coding sends to Anthropic, unchanged in endpoint and model, at effort "high"; the live
check's reads of its practice's lists, one search for a marker and the walk's own synthetic document (one of its two recorded ones, the only
--encounter it takes: the lead's ruling R4P-3); the installer's
probes (no PHI); the pre-app and post-check read-only queries (counts, names and ages).

**The residual risk, dated, for the security official** (D411: the owner): the list above, the specification's open
items (section 12), "What is not claimed", and release 1's accepted items as they stand today: D417's eight and D419's
(3) to (5), unchanged; D419 (1) now nine copies, not 23 (D425 deleted the install folder's other 14 on 2026-11-25; the
nine of 2026-11-20 to 2026-11-23 and the rehearsal copy stay his, or counsel's); D419 (2) was his yes for release 1's
install only (review owner-4). Release 2 adds to them: this act also takes no copy of live, so it has no restore point
(D409, kept: the lead's decision, not put to him for this act); page memory holding up to 6 PDFs per tab for as long as the tab is open and signed in; the
four test-guard gaps of D-R2-51 until 2.1; the bench gates weaker than their names (D-R2-49); the class-b Word refusals
and their trade-offs. Not put to him: recorded by the session, not accepted by him in words (no runbook step shows it, and the one message of 2026-11-28T09:10:54.069Z told him the hour, the class-b notice and B's speed residuals, not this list).

## Stop conditions

These stop the act before the next phase, or, where written, lead to a switch-back (RELEASE-2-SPEC 9.8, with release 1's
that still apply):
- Any phase exiting non-zero; pre_app_r2.sh ending PRE-APP STOP. A read-only step that stopped is judged; when what
  stopped it lies outside this release and is over (a co-tenant's deploy or restart, an answer that was lost), it runs
  again under a new TAG: preflight; pre_app_r2.sh, after a preflight under the same new TAG (act_r2.sh refuses app on a
  preflight older than an earlier pre-app reading: the lead's ruling R3P-4), but not over a moved row or another count
  (below); verify, after a preflight (TAG), since it compares with the newest one; a verify that stops on CPT Studio's own state is decided as a
  live-check failure is (the last condition). post_check_r2.sh reads passages', license-note's and verify's newest
  receipts: none of them ok, or out of that order after app, is a finding there too (review scripts-5); a verify that
  compared with a preflight taken after app ended is named there, and what app changed among the items verify alone
  reads is then judged by hand (review round 1 scripts-5's re-test).
- A pre-app count other than declared: a compared row moved since the Baseline reading is a stop, before any phase when
  the reading taken again before preflight shows it (baseline_diff_r2.sh: BASELINE STOP), and after that at
  pre_app_r2.sh (one upload, decision or export ends it PRE-APP STOP, and a further run with TAG cannot pass; a console
  view of a record does not, since it writes only a read record and session state, rows set aside under Baseline: review
  truth-5); after such a row the act goes on only under a new declaration with the baseline read again, image run again
  under it (the lead's ruling R2P-5, D-R2-55; review scripts-2's re-test: this sentence once followed the coding rows'
  exception and read as if it applied to them). The coding rows (Baseline) are the declared exception: they may move as a
  member's finished coding moves them, each moved row named, and the counts are then judged against the reading
  pre_app_r2.sh kept (the lead's ruling Q7, D-R2-53). A host daemon-reload since the
  reading (db_cgroup memory.swap.max max) is decided under a new declaration, as in release 1.
- A table more than 100 times its declared rows (section 6).
- A stored state with a round outside today's eight.
- A job queued or running, or a send in flight, at baseline_diff_r2.sh (BASELINE WAIT, whatever the declared baseline
  held: the lead's ruling R2P-6, D-R2-55; review round 2 safety-1) or pre_app_r2.sh: a wait - the same read again once it
  has ended and the window is quiet (a preflight, then pre_app_r2.sh, each under the same new TAG: app compares with the
  newest preflight only after its migrate, and act_r2.sh refuses app on a preflight older than a pre-app reading made
  before the one it runs on - the lead's ruling R3P-4, D-R2-55; review round 3 scripts-2), which can pass when only the
  coding rows moved, as a finished coding moves them (the lead's ruling Q7, D-R2-53; review scripts-2: the first draft's
  wait could never pass).
- The web's database connections before app other than at most 2, each younger than 600 s.
- The database's own cgroup reading anything but memory.swap.max 0 and memory.max 536870912 at pre_app_r2.sh (verify would
  refuse after app; release 1's db phase is what sets it, and this act has none): decided under a new declaration. The
  Baseline block's db_cgroup rows are read with that in mind before the commit.
- pre_app_r2.sh reading any pending migration set other than exactly 0019_r2_document_lists, 0020_r2_run_lookups and
  0021_r2_round_sweep, or migrate in app applying anything else; `migration_verdict` not safe (the image phase refuses).
- A migrate failure other than a lock timeout.
- Any non-200 sample in app's availability record (S1 to the end of S5); or an https-vhost receipt whose
  details.observations is not one entry, attempt 0, status 200: judged before the next phase.
- **Switch-back:** the web container killed for memory or restarting within its first 10 minutes (post_check_r2.sh's web
  read: RestartCount, OOMKilled, Running and StartedAt against S1, and memory.events oom_kill - only what the kernel and
  Docker report, never a line a client's text can write: the lead's ruling R2P-2, D-R2-55; review truth-1 and its
  re-tests). The web's gunicorn processes from the kernel's process table other than one master and four workers, each
  started by S3: a stop until judged, never a switch-back by itself - a younger worker replaced one after a kill, an
  exit, a timeout or gunicorn's designed recycle, which nothing here tells apart (review round 1 truth-1's round-3
  check). The worker restarted or killed for memory since S4
  (post_check_r2.sh's worker reads; review round 2 safety-4): a stop until judged - 9.8 names the web, so whether it is a
  switch-back is the lead's call.
- **Stop and judge (9.8's 5xx, as the lead's ruling R3P-1 makes it, D-R2-55):** any 5xx release 2's web answered in its
  first hour, from S3, to a request other than /health/, on either host it serves or any other the vhost logged, or a
  line whose status cannot be read (`access_report_r2.sh act`: a count, never a rate, stricter than 9.8's "a 5xx rate
  above the hour before"; both windows from app's receipt; the hour before printed as context only; every request to
  /health/ set aside in both windows by the path nginx logged, its count and 5xx printed and each 5xx listed (the lead's
  ruling R2P-1); every rotated file of the log read; the status from the server's own field, so a crafted path cannot
  shift it: review scripts-7, scripts-0, safety-0, safety-5; round 3 scripts-0, safety-1): an incident, in which the lead
  decides switch-back or not, recorded, before anything else. Its "cannot tell" (exit 3) is a stop until the windows are
  read whole, never a pass.
- An undeclared difference in the post-check. That is the finding (§2.5's rule), never explained away - apart from a
  member's own activity, identified from the audit events and the record tables and named in the report.
- A changed clinical count: app's install counts other than the reading app ran on (pre_app_r2.sh's kept reading, by
  its path and sha256: the Baseline block's rows but for the set-aside rows and the coding rows its PASS log names; the
  lead's rulings Q7 and R2P-4), or a compared count after.
- An encounter's stored state changing in app.
- The citation not success in both views; a held declaration found.
- Preflight BLOCK (the health check), or the installer's preflight refusing. Every run of the health check from this
  declaration's commit to the act's report is report-only: none of its auto-fixes is run (no restart of a QuillMD
  container, no build-cache prune). A QuillMD container it reads unhealthy, or a host it reads 502, 503 or 504, is a stop,
  decided by hand; a yellow flag alone (disk, memory, load, swap) is not.
- The door's ceiling reached.
- A script of the package not the one "The package as run" names (sha256, first 16): act_r2.sh refuses a changing phase
  (exit 9) and records the difference in a read-only phase's or a switch-back's log; post_check_r2.sh refuses (exit 2)
  when post_check_r2.sh, live_check_r2.py or access_report_r2.sh is not as named; access_report_r2.sh is compared before
  the runbook's steps h and j (review round 2 truth-8; round 3 truth-1).
- The window (Saturday 2026-11-28 from 15:00 UTC (07:00 Pacific, PST), about 3 hours, ending before the daily maintenance due at about 19:05 UTC, chosen by the lead away from the maintenance's due times read before the hour was told (the
  lead's ruling Q11, D-R2-55; review round 3 truth-4), and told to the owner, not asked, in the message of
  2026-11-28T09:10:54.069Z (the one message, which named the hour; no later message moved it) whose words name it - the one message that also carried the class-b notice and B's residuals
  (D-R2-54's sentence and D-R2-60's two rows), or, when a continuation or the baseline's maintenance rows moved the hour, a one-line message of its own,
  the last of its turn, telling him the new hour (the lead's rulings Q2 and R3P-6, D-R2-55 - R3P-6 for a continuation;
  for the maintenance rows, the package's own step for review round 3 truth-4, told the same way: review round 4
  truth-2, owner-1 -, under the recorded standard D428, C10, and D427 for the hour; release 1's hour was his answer,
  D412); every hour told to him for this install, each with its message's
  time: one hour, never moved: the one message of 2026-11-28T09:10:54.069Z, which opens "Release 2 installs **today, Saturday 28 November, at 15:00 UTC, which is 7:00 AM Pacific**. It takes about 3 hours, including an hour of watching, and finishes before the server's daily maintenance at 19:05 UTC. You don't need to do anything. If you object to anything below, say stop before then and the install won't start." and whose item 2 reads "**2. The time:** 15:00 UTC (7:00 AM Pacific) today, about 3 hours." - the Baseline block's maintenance rows (2026-11-28T09:40:41Z) put no due time inside it): no changing phase up to app starts after its end (the act then ends and a new declaration
  names another hour, told to him as R3P-6 says), but for switch-back and rollback-app, the incident paths. Once app has ended exit 0, the phases after it are completed whatever the hour.
  When app has not started within 15 minutes of PRE-APP PASS, preflight and pre_app_r2.sh run again first, each under a
  new TAG, pre_app_r2.sh at once after its preflight (act_r2.sh refuses app on a preflight more than 900 s older than
  the pre-app reading it runs on: review round 4 scripts-1).
- The owner's class-b notice (R2-30's fallback, PICT and SVG previews, the canonical package gate's generators) not told
  to him, on the record, before the commit of this declaration (told, not accepted: the recorded standard D428, C10;
  release 1 required his acceptance on the record); or told in words that say or imply that release 1 coded the canonical
  gate's files with a part missing, or that Word never writes them, or that leave out that the doctor is shown the
  inserted-document sentence for them (review owner-2), or that leave out that release 1 coded them completely, that
  some are files Word 2007 itself writes, that the sentence is not true of them, or that files already uploaded are
  refused when coded again (review owner-2's re-test); or in words that put R2-30's fallback among files release 1 coded
  completely without saying that release 1 already dropped its H01 shape's words on LibreOffice 7.4 (D-R2-36; review
  round 2 owner-2); or a message that did not end its turn, this one or a one-line message that told him a moved hour (review owner-8;
  review round 4 owner-1); or that message without D-R2-54's one
  sentence on B's rows accepted in the open (D-R2-54 (3); the lead's ruling R3P-2, D-R2-55: exactly three told items -
  the hour, the class-b notice and B's residuals, that sentence with D-R2-60's two rows), or without D-R2-60's two rows,
  each with its numbers, and that he may say stop (D-R2-60), or carrying anything that asks (the Dictation owner batch is not part
  of it: it goes in its own message when it is ready).
- **The owner objecting** to the notice, D-R2-54's residuals or the hour when told, or to D-R2-60's two rows: the act
  does not start under this declaration (the lead's rulings Q2 and R3P-2, D-R2-55; D-R2-54 (3)); for D-R2-60's rows both
  are then fixed - the list's usable time at P1, the kept-copy budget - and B is measured again in full (D-R2-60). The
  message needs no answer, so his reply can come
  at any time: an objection that comes once the act has started stops it before the next phase up to app, his words
  recorded; from converter on, release 2's refusals stay live until a new declaration decides, and his objection to them
  is answered by release 1's own converter phase before S4 (Rollback per phase, converter), never after S4 (review round
  2 owner-5). An objection that comes once app has started does not stop the post-install readings - passages,
  license-note, verify, the live check, post_check_r2.sh and access_report_r2.sh act run and judge as written - his
  words are recorded, and it opens an incident in which the lead decides switch-back, recorded in the act's report,
  before the class-c question: the question is not sent while the incident is open, and one already sent is withdrawn
  by a switch-back the incident decides (the lead's rulings R3P-6, D-R2-55, and R4P-2, D-R2-57; review round 3 owner-2;
  round 4 owner-0).
- **The residual risk not accepted:** "The residual risk, dated, for the security official" (above) put to him before
  the commit and not accepted by him in words - a refusal, or no answer by the commit: the act does not start under this
  declaration (review round 2 owner-4). Not put to him (no runbook step puts it: the session's reading of D422, D427, and
  specification section 11), it is recorded as such and is no stop.
- B not standing: `b_stands_r2.sh` on the revision not ending B STANDS (a file other than a document changed since
  a680d837b, B's revision in B's third session, laneM/b3: D-R2-60): B is measured again on the revision before this
  declaration is committed (the lead's ruling Q10, D-R2-53; B's revision a680d837b: D-R2-61 (3)).
- The Baseline block without a last_audit row holding a time (RUNBOOK-r2.md item 8; the second rehearsal's G4): this
  declaration is not committed until the lead has decided; post_check_r2.sh lists no audit events without that row.
- D-R2-55's archive entry not holding the package rulings this declaration cites it for - round 1's Q2, Q3, Q9, Q11, Q12
  and owner-9, round 2's R2P-1 to R2P-7 and round 3's R3P-1 to R3P-6 - and those citations not changed to the lead's
  other record (D_R2_55_RECORD, under Authority): this declaration is not committed (RUNBOOK-r2.md item 4).
- The browser speed gate not all passed on the revision: `ops/test_viewer_speed.cjs` on the merge commit (runbook item
  1) with `# pass` other than `# tests`, `# tests` under 18, or any test failed, cancelled, skipped or todo, or run in a
  worktree whose head was not the merge commit or whose status was not empty - a run where V16 alone failed allows one
  re-run, both recorded, and the re-run must pass whole: this declaration is not committed (the lead's ruling R4P-1,
  D-R2-57, and decision RH-7; D-R2-52; review round 4 truth-0).
- The walk document not checked: `walk_check_r2.sh` at the Baseline reading not ending WALK DOCUMENT OK - its id one of
  the walk's recorded synthetic documents (D361) and the document made by one of its practice's agent members, never
  only a document that exists (the lead's ruling R3P-5, D-R2-55; review round 3 safety-0): the walk's other recorded
  document is named before the commit; if both fail, a new walk document is a package change under a new declaration,
  walk_check_r2.sh's and live_check_r2.py's one list updated - there is no live check without a walk document (the
  lead's rulings Q9, D-R2-55, and R4P-3, D-R2-57); a document a member uploaded is never a walk document.
- quillmd.com, www.quillmd.com, app.quillmd.com or pro.quillmd.com changing its answer or certificate, or
  app.quillmd.com's health; admin.quillmd.com answering anything but the console's 302 to /login/ with the cpt-studio
  certificate.
- A TLS finding is recorded and reported, never a stop (D27).
- The live check failing, or the post-check finding a difference: judged, then reported. A defect found there is fixed
  and installed under a new declaration, or the site is switched back. It is never patched in place.
