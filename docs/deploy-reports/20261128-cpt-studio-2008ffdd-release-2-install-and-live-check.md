# CPT Studio release 2 (816045c72644 to 2008ffddc946): the install of 2026-11-28 and the live check

Session `799ffbc5`, 2026-11-28. Owner directions recorded verbatim in
`/home/claude/cpt-studio-completion-20261106/gemini-migration/DECISIONS.md`: D457 (his reply to the install message,
09:38:19.903Z), D458 (16:52:54.735Z) and D459 (16:59:20.481Z, after the act; it is about release 3). Declaration
`docs/foundation/mutations/20261128-cpt-studio-release-2-install.md`: last commit 73b87c758e6f (10:13:21Z), merged in #1538
as 20047eb48630. Every phase ran through `scripts/run-ruled-mutation.sh` (`RULED_ACT_MAX_SECS` unset, the door's 9000)
from the clean act checkout `/opt/meddoc-pro/.worktrees/cpt-r2-act-20261128` (20047eb48630); every start came after the
declaration's commit. Receipts: `/home/claude/cpt-studio-install-20261023/`. The act's logs, the readings and the live
check's evidence: `/home/claude/cpt-r2-20261125/release/act/`; the lead's log: `/home/claude/cpt-r2-20261125/lead/STATE.md`.

**Result: installed, verified and complete. Every row of the declaration matched, the site served throughout the switch
(302 availability samples, all 200), nothing was deleted, the live check passed 43 of 43, the post-check ended exit 0
with 0 unexpected differences, and release 2's web answered no 5xx in its first hour.**

## The revision

`2008ffddc946be142e8b856b4003e4c4959b1dd7`, the merge commit of #1537. Image cpt-studio:2008ffddc946 =
sha256:42b745b6a5dce70f99d1d1065ceff13c585fbf9a0ed78167cd78adcc77d010f8 (LibreOffice 7.4.7.2); /health/ answers
release_digest `d730927df8f953c8`, database ok.

Citations:
- on the revision: CI 46127033034, cpt-studio 46127033085, secrets-scan 46127032997, all success;
- on the declaration's merge commit 20047eb48630: CI 46137232829, secrets-scan 46137232836, both success before the act.

## The hour

The declared window: from 15:00Z (07:00 Pacific), about 3 hours; no changing phase up to app after its end; once app
ended exit 0, the phases after it complete whatever the hour. **The act began at 16:26Z, not 15:00Z**: the session was
paused from about 14:59Z to 16:25Z by the account's weekly usage limit (every running agent died with it); the owner
logged in with another account and said "Continue" at 16:25:05Z. No phase had run before the pause (the only reading
was step b's at 14:41:24Z). Every changing phase up to app ran inside the window; the hour told to the owner was not
moved by a continuation or by the maintenance rows, so no new declaration and no message about the hour were needed.

## Before the first phase

- The health check, report-only (`docs/preflight-reports/preflight-20261128T144053Z.md`): FIX-AND-GO, disk 88%
  (yellow). Earlier the same day the disk was 91%: the build cache was pruned and 47 clean lens sandboxes of
  2026-11-06 were removed (`preflight-20261128T140448Z.md`).
- The operator's reads in the act checkout (`lead/step-b.sh`, the declaration's own commands): status nothing,
  RULED_ACT_MAX_SECS unset, byte identity exit 0, exactly migrations 0019, 0020 and 0021, nothing changed between the
  revision and HEAD, stages 3532f50c8f74 (9150) and 57e1bec0fd22 (9151), no placeholder, no rehearsal container; at
  14:41:23Z and again at 16:26:08Z.
- `baseline_diff_r2.sh`: BASELINE PASS at 14:41:24Z and at 16:26:09Z, at once before preflight (205 rows exactly, 32
  coding rows as finished coding moves them).

## The act, phase by phase (UTC)

| phase | ended | receipt summary |
|---|---|---|
| preflight | 16:26:28 | baseline recorded; no blocking problem |
| image | 16:27:57 | built cpt-studio:2008ffddc946 = sha256:42b745b6a5dc |
| converter | 16:28:16 | cpt-studio-converter running sha256:42b745b6a5dc with no network (replaced), healthy |
| cert | 16:28:34 | lineage cpt-studio for cpt.quillmd.com and admin.quillmd.com present |
| https-vhost | 16:28:51 | both hosts served through 2008ffddc946's stage (replaced e31ce5801a7b, recorded by 816045c72644); observations one entry, attempt 0, status 200; TLS policy 2 findings (TLSv1.3 ChaCha20), recorded, never a stop (D27) |
| preflight (TAG after-https-vhost) | 16:29:37 | ok |
| pre_app_r2.sh | 16:29:39 | PRE-APP PASS: jobs 0, code jobs 0, runs reserved or sending 0, unknown 0, web connections 2 (59 and 57 s), every table within 100 times its declared rows |
| app | 16:32:39 | web and worker running sha256:42b745b6a5dc (coding live, effort high); blue/green 9150 to 9151; S1 16:30:00.518, S2 16:30:02.998, S3 16:30:05.327, S4 16:30:09.290, S5 16:30:18.895; 302 availability samples, 0 not 200; one migrate attempt; install counts 102 encounters, 13 coded |
| passages | 16:33:11 | imported from 3 files; idempotent |
| license-note | 16:33:22 | no reference source holds the old note; nothing changed |
| verify | 16:33:33 | installed 2008ffddc946 verified; co-tenants and app.quillmd.com unchanged; TLS policy 2 findings (D27) |

## The live check

`live_check_r2.py` once, 16:33:45-16:33:47Z, as the synthetic agent account on the recorded walk document: 43 of 43
passed (hashed immutable assets on both hosts, the three lists in release 2's shape with their totals, the walk
document, an empty search, release 1's client answered 409 client_outdated on a list and on the search, /ops/ 404 to a
member, sign-out and the ended session's replay 401, the console's fonts and routes signed out). Evidence:
`release/act/live-check-20261128`.

## The post-check

`post_check_r2.sh` at 16:40:23-16:40:27Z (S1 + 623 s): exit 0, **unexpected differences 0**. The seven expected deltas
exactly: the five indexes valid on their tables, the last migration 0018 to 0021, the migrations 18 to 21. Health ok on
the revision's digest; co-tenants as expected; the ingress read back (the quillmd vhost the pinned after state,
quillmd-cpt the revision's stage for 9151, both CPT hosts on the cpt-studio certificate, app.quillmd.com on QuillMD's);
the converter sealed; ops-agent holds no grant; the web started at S1, no restart, oom_kill 0, one master and four
workers none after S3; the worker started at S4, no restart; the record equation and the phases' order held.

## The hour after

`access_report_r2.sh act` at 17:30:35Z, the script as declared: release 2's first hour from S3, **5xx 0** to any request
but /health/ (the hour before 0, context only); /health/ set aside, 314 requests after (5xx 0) and 8 before (5xx 0):
none to judge. The baseline read afterwards (17:31Z) differs from the post-check's after reading only in ordinary use
(sign-in attempts, access records and rate windows of an admin sign-in during the hour); the clinical counts are equal.

## The owner's look (step i) and the opens reading (step j)

Not asked and not run. The owner's D458 (2026-11-28T16:52:54.735Z), verbatim: "Do what ever you need to do and dotn
ask me question but make sure you not using a lot". He had already said at D457 that he judges the speed on live
himself. So no class-c answer exists for this release and none is recorded as given; a later word of his about the
speed is recorded beside this report, dated.

## The package and its reviews

The package (`/home/claude/cpt-r2-20261125/release/`) was derived from release 1's, reviewed in four rounds (truth,
scripts, safety, owner; a re-test per finding) until round 4 (D-R2-57), rehearsed three times (the third on the merge
commit), and run as declared: every script's sha256 matched "The package as run" at every phase.

## Rollback

Not needed. A switch-back to release 1's pair (cpt-studio:816045c72644, its image kept) stands as declared: a fresh
preflight, SWITCH_BACK_DECISION in words; release 2's indexes and stage stay.

## Notes for the next release

- The session's usage is a real constraint: an account's weekly limit stopped every agent at once mid-window. A window
  should start with no heavy agent work running, and a waiter that ends the turn should not be the only thing between
  the lead and the window's start.
- TLS 1.3 ChaCha20 on the shared listener is recorded again (D27).
- The worker's RestartCount is 1 from the host's boot of 2026-11-26 (06:48Z), before this act; release 2's own
  containers started clean.
- Release 3 installs next (ICD-10-CM and the auto-answer agent, for every category: D459).
