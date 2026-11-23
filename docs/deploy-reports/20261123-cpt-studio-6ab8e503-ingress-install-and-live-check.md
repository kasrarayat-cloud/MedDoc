# admin.quillmd.com moved onto CPT Studio (3d7c589261bd to 6ab8e503a400), release 2 of the admin.quillmd.com move, and the live check

Session `738699b2`, 2026-11-23. Owner direction D396 ("jsut move to admin.quillmd.com and lemme walk into live one"),
recorded verbatim in the CPT Studio rulings file with PR #1515. Declaration
`docs/foundation/mutations/20261123-cpt-studio-admin-host-ingress-install.md`: committed 51346672a5c6 at 18:39:31Z and
merged in #1519 as 258700a8a79d at 19:15:34Z. Every phase ran through `scripts/run-ruled-mutation.sh` from the clean,
detached act checkout `/opt/meddoc-pro/.worktrees/cpt-admin-host-ingress-act-20261123` (258700a8). The door printed the
declaration's commit before each start; every start came after it.

The declaration's three pre-preflight commands were extracted from the committed file, not retyped, and run there at
19:16:07Z: exit 0, empty, empty, as declared. Receipts are in `/home/claude/cpt-studio-install-20261023/`. The act's logs,
post-checks and live evidence are in `cpt-admin-host-20261123/release2/act/`.

**Result: installed and verified. admin.quillmd.com now answers CPT Studio's operator sign-in and console through the
public path, with the cpt-studio certificate. Every row of the declaration matched, the site served throughout the
switch (310 availability samples, all 200), the live check passed 61 of 61 including the operator's walk on
https://admin.quillmd.com, and the database moved by exactly the check's declared footprint.**

## The revision

`6ab8e503a40050c08c01c965441fa56583fb5e03`, the merge commit of #1518. Its tree equals the reviewed head 19938d109's.

Citations:
- on the revision: CI 45193463059, cpt-studio 45193463092 and secrets-scan 45193463097, all success, read twice in both
  views;
- on the declaration's merge commit (docs only): secrets-scan 45247053871 success, CI 45247053760 running when this report
  was written.

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 19:16:17 | FIX-AND-GO (disk 89.00%) | not BLOCK; `docs/preflight-reports/preflight-20261123T191617Z.md` |
| preflight | 19:16:32-19:16:43 | exit 0, "baseline recorded; no blocking problem" | as declared: the coupling before (the quillmd vhost e9aa049d...); 9150 active, 9151 idle; both names resolving to 147.189.172.8 alone; admin's HTTP-01 route passed; co-tenants as expected with admin left to the installer; nginx -t ok, its warning the baseline |
| image | 19:17:13-19:17:35 | exit 0, cpt-studio:6ab8e503a400 = sha256:6ee79ec888ac | as declared; cpt-studio:3d7c589261bd kept |
| cert | 19:17:52-19:18:08 | exit 0, the cpt-studio lineage for cpt.quillmd.com and admin.quillmd.com | as declared: one webroot order on the existing ACME account, both challenge routes proven first, renewal conf cpt-studio.conf; no other lineage changed; nothing served the new certificate yet (the stage still 259b895dd130...) |
| ingress | 19:18:30-19:18:41 | exit 0, "admin.quillmd.com moved onto quillmd-cpt" | as declared: moved; the receipt's vhost_sha256 d0e4fc5ca1cc... (the stage named before the act); the quillmd vhost e9aa049d... to b3ab66023547..., line 26 alone; the replaced stage 259b895dd130... saved byte for byte; its intent written first; nginx warnings unchanged; 421 for either host on app.quillmd.com's connection; each host served on the other's connection; http to https 301; admin's /api/session 404, GET and HEAD / 302 to /login/, the sign-in page 200; the certificate naming exactly cpt.quillmd.com and admin.quillmd.com |
| check at once | 19:18:41 | admin 302 to https://admin.quillmd.com/login/ | the act checkout's check-cotenants.sh: every judged co-tenant as expected, admin through its second state |
| preflight again (after-ingress) | 19:19:10-19:19:21 | exit 0 | the coupling after (the quillmd vhost b3ab66023547..., quillmd-cpt naming admin); ports unchanged |
| pre-app | 19:19:43 | PRE-APP PASS | as declared: the declared baseline file exactly the committed Baseline block; the dump 48 TABLE DATA (sha256 90a6722ff78597ee); its restore migrated with cpt-studio:6ab8e503a400 applied nothing; the baseline re-read equal to the declared one; jobs_active 0, runs_reserved_or_sending 0, runs_unreconciled_unknown 0, no reading job, the last audit event 29,522 s old |
| app | 19:20:16-19:23:17 | exit 0 | as declared: migrate "No migrations to apply"; details.ports 9150 to 9151; S1 19:20:38, S3 19:20:47 to S4 19:20:51 the switch; switch.vhost_sha_after 1672b98db8cf... and switch.vhost_sha_before / replacement.vhost_sha256 d0e4fc5ca1cc..., as the declaration names them; states recomputed, none changed (8 coded, 89 kept); 310 availability samples, none other than 200; the old web drained 130 s with 0 connections left; the parked 3d7c589261bd pair removed, its image kept |
| verify | 19:23:42-19:23:53 | exit 0, "installed 6ab8e503a400 verified; co-tenants and app.quillmd.com unchanged" | as declared |
| post-check after verify | 19:24:08 | exit 0, unexpected differences 0 | the declared baseline proven to be the committed declaration's Baseline block; /health/ status ok, database ok, serving the revision; co-tenants as expected. The ingress read back: the quillmd vhost the pinned after state; quillmd-cpt behind the installer's link naming both hosts on 443; quillmd-cpt the revision's stage for 9151, the port cpt-studio-web publishes (1672b98db8cf); admin and cpt served the cpt-studio certificate; app.quillmd.com still served QuillMD's; https://admin.quillmd.com/ 302 to /login/ |
| live check | 19:24:22.49-19:24:23.75 (the evidence's request times) | pass, 61 of 61 | below |
| post-check after the check | 19:24 | exit 0, unexpected differences 0 | exactly the declared rows: audit_event operator.viewed 132 to 133 and audit_events 1495 to 1496; the sign-ins set aside as declared; the ingress read back as after verify |

## The live check

`console_check_i.py` (sha256 2af075e4f7eaf6dd) was run once with the act checkout's ops/verify_login.py, against
https://cpt.quillmd.com, without --acts, using `--admin-loopback http://127.0.0.1:9151` (read from docker port before the
run), `--admin-release` set to the revision, `--admin-public https://admin.quillmd.com` and `--admin-walk`. 61 checks
passed and none failed or warned. It made 36 requests to the cpt site, 11 to the admin host on its loopback and 16
through https://admin.quillmd.com.

- **Before any request to cpt.quillmd.com:** /health/ named the revision on the new web's loopback and through
  https://admin.quillmd.com.
- **The cpt arm:** unchanged from release 1, and passed.
- **The loopback admin arm:** 10 read-only checks, passed.
- **The public arm:** https://admin.quillmd.com/health/ named the revision, and its certificate carried exactly
  cpt.quillmd.com and admin.quillmd.com, verified against the system trust store and the host name. The read-only probes
  passed through the public path, including both foreign-origin requests answered 403 by the admin host's own-origin
  rule.
- **The walk:**
  - the operator signed in on https://admin.quillmd.com/login/: 302 to /ops/, a session given;
  - /ops/people answered 200, the console;
  - the operator signed out with 302, and the session replayed was sent to /login/?next=%2Fops%2Fpeople;
  - the member's sign-in was refused with 400 and no session.
- **Completeness:** `admin.arm_complete` reported that all 25 admin checks ran.

The check's own Secret test found no password in the output or the evidence. One line of the output contains the word
"password": the console path /ops/people/<id>/password, which the member was answered 404 on.

## For the owner

admin.quillmd.com opens CPT Studio's operator sign-in, then the console. Sign in as `platform-operator`, which holds a
standing operator grant. Its password is in `/etc/cpt-studio/operator-credentials.json`, readable by root only; this
report names the path, not the contents. cpt.quillmd.com is unchanged for members. QuillMD's sites (quillmd.com, www,
app and pro) answered and were certified exactly as before, at every step.

## Measured before the act (in the declaration)

- **The code:** two refutation rounds of the finished diff, the stopping rule met; mutants R1-R13 and M1-M18.
- **The full gate:** green.
- **Rehearsals:** four of the app half on restored copies of live, each with 50 checks as live runs them, 58 with the acts,
  the same footprint, and a clean switch-back.
- **The release package's review:** three rounds with two lenses each, 37 findings in all. Round 3 met the stopping rule.
  Every repair was pinned by a mutant.
- **Mutants re-run on the final files:**
  - all 17 live-check mutants caught;
  - 13 of 14 act-script mutants caught;
  - one equivalent (Mf): the rule it deletes is enforced twice more.
- **Held declarations:** none, after the held check's own tool was repaired.

## Rollback

Not needed. If it ever is, the declaration's paths stand:
- switch-back to the 3d7c589261bd pair (its image is kept), which also serves the admin host;
- then, to undo the move itself, a preflight newer than the switch-back and ingress-rollback. That gives the quillmd
  vhost its before state and quillmd-cpt the saved stage 259b895dd130... byte for byte, and puts admin.quillmd.com back
  on QuillMD's notice.

Each step takes its own recorded decision, in words, and a fresh preflight.

## Notes for the next release

- QuillMD's scripts/check-cotenants.sh still accepts admin's two states. The declared follow-up PR narrows the row to the
  console's 302, now that the move is installed.
- The shared tree's copies of QuillMD's checks (at c8b54991) predate admin's 302. Until QuillMD's deploy surface is next
  brought to main, a run of those copies reports admin.quillmd.com 302 against their 503: declared, not a finding.
- The uptime monitor already read app.quillmd.com DOWN on every run (a stale 503 row, reported before). The move adds an
  admin line to that standing alert until the shared tree is brought to main.
- One operator error in this session, recorded: a leak check written for the live check's output opened the two
  synthetic agent credential files (by path) to search for their passwords. It failed on its first key lookup, read out
  and printed no credential value, and was unnecessary: the check's own Secret test covers it. It is recorded as a
  standing lesson, and credentials stay by path only.
