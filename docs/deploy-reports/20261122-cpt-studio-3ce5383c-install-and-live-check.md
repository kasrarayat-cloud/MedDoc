# CPT Studio's Neurosurgery and Orthopedic Surgery installed at cpt.quillmd.com (9dab92ba0f98 to 3ce5383ce485), both workspaces provisioned, and the live specialty check

Session `738699b2`, 2026-11-22. Owner direction D390 (Neurosurgery and Orthopedic Surgery added the GI way) and the
owner's approval of the live release, D391 ("ok", recorded verbatim in the CPT Studio rulings file); declaration
`docs/foundation/mutations/20261122-cpt-studio-neuro-ortho-install.md` (committed 73e150b99d4d at 10:12:40Z, merged in
#1510 as 72ee24965821 at 10:43:43Z; that merge commit's citation CI 45013838517 and secrets-scan 45013838481, success in
both views). Every phase ran through `scripts/run-ruled-mutation.sh` from the clean, detached act checkout
`/opt/meddoc-pro/.worktrees/cpt-neuro-ortho-act-20261122` (72ee24965821, a descendant of the revision that changes nothing
under `cpt-studio/` or the door; the declaration's three operator pre-checks passed there). Receipts are in
`/home/claude/cpt-studio-install-20261023/`; the act's logs, post-checks and live evidence in
`gemini-migration/neuro-ortho-20261122/act/`.

**Result: installed and verified, with the site serving throughout; both specialties' workspaces and accounts
provisioned; the live specialty check passed. Every row of the declaration matched but one prediction - the image's
layers shared with the live image (9 of 11, declared 7) - recorded as finding 1, its cause established from the layers
and judged before the act continued.**

## The revision

`3ce5383ce485c39339a839d1f8f8468c41ef9a53`, the merge commit of #1509 (its tree is the reviewed head af1ebb26f's: main
had not moved since the branch point). Citation on the revision: CI 45004766500, cpt-studio 45004766452, secrets-scan
45004766384, all success, the same three in both views. Held declarations over the range 9dab92ba0f98..3ce5383ce485:
none (43 runtime files, all under cpt-studio/; 22 declarations and reports name one, every revision they name an
ancestor of the running revision).

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 11:15:58 | FIX-AND-GO (disk 89%) | not BLOCK; `docs/preflight-reports/preflight-20261122T111558Z.md` |
| preflight | 11:16:07-11:16:18 | exit 0, "baseline recorded; no blocking problem" | as declared: the quillmd-cpt vhost f816a27de9e6... for 9151; 9151 active, 9150 idle; the live web on sha256:6e409ad596bc; co-tenants and app.quillmd.com/health/ (200) recorded; nginx -t ok |
| image | 11:16:38-11:16:59 | exit 0, cpt-studio:3ce5383ce485 = sha256:9486d0bfd111 | as declared: 608,193,451 bytes, 11 layers, labelled with the revision; cpt-studio:9dab92ba0f98 kept. **Finding 1:** 9 of its 11 layers are shared with the live image, not the 7 declared (below) |
| pre-app | 11:18:08-11:18:19 | PRE-APP PASS | as declared: dump 48 TABLE DATA (sha256 a6983728c8e6...), the restore migrated with cpt-studio:3ce5383ce485 applied nothing, the baseline equal to the declared one, jobs_active 0, no run reserved, sending or unreconciled, **marked_stored_rounds 0**, the last audit event 28,286 s old |
| app | 11:18:28-11:21:24 | exit 0 | as declared: migrate "No migrations to apply"; UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS 97 encounters, 8 coded (its note on the Fable tables' existing rows, as before); S1 11:18:48 cpt-studio-web-next on 9150; S2 11:18:52 the old worker parked; S3 11:18:54 the vhost switched 9151 to 9150 (f816a27de9e6... to **259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, as declared**), `nginx -t` clean, https 200; S4 11:18:58 the new worker, coding live at effort max; S5 the old web drained in 130.6 s with 0 open connections, stopped and parked; S6 RECOMPUTE_STATES 8 coded encounters, none changed, 89 kept. Availability: 304 samples at 0.5 s, all 200, the releases seen 9dab92ba0f98 then 3ce5383ce485 |
| verify | 11:21:57-11:22:03 | exit 0, "installed 3ce5383ce485 verified; co-tenants and app.quillmd.com unchanged" | as declared |
| post-check after app | 11:22:12 | exit 0, unexpected differences 0 | /health/ status ok, database ok, serving 3ce5383ce485; co-tenants as expected |
| provision-neurosurgery | 11:22:21-11:22:32 | exit 0, "accounts owner-neuro created, review-agent-neuro created" | as declared: /etc/cpt-studio/initial-credentials-neurosurgery.json (root, 0600) and ~/.cpt-studio/agent-credentials-neurosurgery.json (0600); the provision log ends "(Neurosurgery, neurosurgery) created" |
| post-check after Neurosurgery | 11:22:52 | exit 0, unexpected differences 0 | all 11 declared rows observed exactly: users 5 to 7, memberships 3 to 5, workspaces 1 to 2, categories 1 to 2, audit_events 1489 to 1491, the two accounts, the two memberships (in neurosurgery's "Neurosurgery", owner and reviewer, active), the category and the workspace |
| provision-orthopedic-surgery | 11:23:02-11:23:13 | exit 0, "accounts owner-ortho created, review-agent-ortho created" | as declared: initial-credentials-orthopedic-surgery.json and agent-credentials-orthopedic-surgery.json; the provision log ends "(Orthopedic Surgery, orthopedic-surgery) created" |
| post-check after Orthopedic Surgery | 11:23:21 | exit 0, unexpected differences 0 | all 17 declared rows observed exactly (users 5 to 9, memberships 3 to 7, workspaces 1 to 3, categories 1 to 3, audit_events 1489 to 1493, four accounts, four memberships, two categories, two workspaces); Gastroenterology's category, workspace, three memberships and accounts unchanged; Gastroenterology's review-agent credentials file byte-identical (its sha256 as declared) |
| live specialty check | 11:23:33.7-11:23:34.7 (the evidence's request times) | pass, 3 of 3 | below |
| post-check after the check | 11:23:42 | exit 0, unexpected differences 0 | the same 17 rows; login_attempts 124 to 127 (the three sign-ins, set aside by the comparison and as declared); the last audit event the provisioning's own (account.provisioned, 11:23:08Z): no member activity in the window |

### Finding 1: 9 of 11 image layers shared with the live image, 7 declared

The declaration predicted the layer sharing from the revision's test image, built apart by testinst/build_image.sh. The
installer's own build reused its cached layers for requirements.txt and the pip install (118 MB): requirements are
unchanged, so layers 0-8 (the base, the system packages, the requirements and the dependencies) are byte-identical to the
live image's, and only layers 9-10 - the application code (8.57 MB) and its collected static files (15.6 MB), exactly what
a code-only release changes - are new. The test image had rebuilt layers 7-8 with new digests. Size, label, base and
dependencies were as declared, and the image phase's own gate passed. Judged before app: a miss in the prediction
method, not in the install; nothing the declaration protects depends on layer sharing; the act continued
(`act/finding-1-image-layers.md`). For later releases: predict layer sharing from the installer's cache, or declare only
the layers a release must change.

## The live specialty check

`neuro-ortho-20261122/specialty_check_n.py` (the act checkout's ops/verify_login.py for its transport, TLS verified), against
https://cpt.quillmd.com, each run signing in through the form, reading the page and the session, signing out and proving
the session refused:

| account | page: data-specialty and the Specialty field | session: workspace, specialty | role | sign-out |
|---|---|---|---|---|
| review-agent-neuro | "Neurosurgery" | "Neurosurgery", "Neurosurgery" | agent reviewer, can_review true | 302 to /login/; the session replayed answers 401 |
| review-agent-ortho | "Orthopedic Surgery" | "Orthopedic Surgery", "Orthopedic Surgery" | agent reviewer, can_review true | the same |
| review-agent (Gastroenterology) | "Gastroenterology" | "Gastroenterology", "Gastroenterology" | agent reviewer, can_review true | the same |

Six requests each (GET /login/, POST /login/, GET /, GET /api/session, POST /logout/, the replayed GET /api/session);
nothing uploaded, decided or exported; no owner's account signed in; no password printed or written. The evidence is in
`act/live-check-{neuro,ortho,gi}/specialty-evidence.json` (0600).

## For the owner

- Your logins: **owner-neuro** (Neurosurgery) and **owner-ortho** (Orthopedic Surgery). Their passwords are in
  `/etc/cpt-studio/initial-credentials-neurosurgery.json` and `/etc/cpt-studio/initial-credentials-orthopedic-surgery.json`
  (root-only, 0600), as Gastroenterology's are in `initial-credentials.json`. Each opens its own empty workspace, with its
  specialty on the page; neither sees Gastroenterology's documents.
- The review agents review-agent-neuro and review-agent-ortho are the release checks' accounts.

## Measured before the act (in the declaration)

The full gate on the revision's tree; seven refutation rounds of the change (15, 13, 12, 9, 7, 8, 8 findings; 59 mutation
proofs); the paid rehearsal (one short and one realistic synthetic document per specialty, test key: 13 of 13
author-expected codes ready, $8.56); the offline predictions on a fresh read-only dump of live (no migration, 97 views and
194 PDF rows identical between the images, every session differing only by the specialty, 0 marked stored rounds); the
install rehearsal on a restored copy of live, every output on file (the provisioning's exact rows, every membership read
under both images, three checks and two negative controls, the sign-ins' footprint) and its switch-back rehearsal; two
read-only review rounds of the release package (19 then 5 findings, no high), every finding repaired and self-tested.

## Rollback

The previous pair (9dab92ba0f98, image sha256:6e409ad596bc...) is parked with its image kept; the incident path is the
installer's `switch-back` (a fresh preflight, then act_n.sh switch-back with SWITCH_BACK_DECISION recorded), rehearsed with
the new workspaces present. The workspaces and accounts stay under a switch-back (deleting them is the owner's decision,
class d); the previous revision reads them without an error (rehearsed).

## Notes for the next release

- Predict an image's layer sharing from the installer's cache (finding 1).
- The release package's review found what the change's refutation could not: an evidence sentence with no file behind
  it, a provisioning phase able to run out of order, a post-check that accepted a declared change that never happened.
  The repaired tools (act_n.sh's guards, post_check_n.sh's two directions and exit code, pre_app_n.sh's exact baseline
  match, baseline_n.sh's membership rows) are the better starting point for the next act.
