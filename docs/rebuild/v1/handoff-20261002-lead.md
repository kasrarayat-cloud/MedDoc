# QuillMD V1 — lead handoff, 2026-10-02 (end of session)

Authority: `quillmd-v1-private-api-testing-standing-20260930` (standing, no monetary ceiling, synthetic only, QA only).
This file is the starting point for whoever continues. **No V1-readiness claim is made.** Nothing was installed or
deployed: the installed release is still `dedac162`, untouched. All work is on the candidate branch
`v1/release-integration` (worktree `/opt/meddoc-pro/.worktrees/v1-release-integration`) and feature branches.

## 1. Where things stand

| item | state |
|---|---|
| candidate on origin | `b62422e8` — CI green (CI + secrets-scan) |
| candidate local, not yet pushed | `e578471b` (role suggestions merged, default OFF) — full core suite was running at hand-off; push only after it passes (see §6, step 1) |
| model | `claude-sonnet-5-5` everywhere in QA; proven through the QA worker (model check PASS in every campaign) |
| installed release | `dedac162`, unchanged |
| live API spend this programme (calculated, list rates) | standing campaigns 1–5: **$1.415167**; historical staged campaign (closed): $0.130880. Provider-billed figures are not readable with a Messages key. |

## 2. Integrated into the candidate this session (in order)

| commit | what | proof |
|---|---|---|
| `f55d6434` | runner paces generations to the app's own limit (30 Generate / user / 600 s) and names a refused Generate | 18/18 runner tests; mutants M1/M2 killed |
| `fdcc7db2` | relations contract **v4** (each field's relations = a partition of unit ids; ~5× capacity per request) | refutation: 630k parse mutations + 63k end-to-end verdicts, NOTHING FOUND |
| `5d31c260`, `c1fe4ab4` | **supersession hold floor**: 'switched/replaced/changed to/held/withheld/on hold' end the thing for the floors (hold-only); closes the base leak 'Apixaban was stopped.' vs an apixaban answer | 3 refutation rounds; final release lens 0 of 12,544 cases released vs base |
| `8aa5acc7`, `b62422e8` | **7A operations**: redaction/retention (tombstones, journal replay, sweep), billing scope, dictated ICD-10 codes (CPT stays disabled: never suggested/displayed/accepted/exported/audited by value); migrations 0033/0034; isolation matrix classifies the new routes | 7 refutation rounds, last round LOW/INFO only; core/documents/ops green except known host-only tests |
| `e578471b` (local) | **explicit-accept role suggestions**, `QUILLMD_ROLE_SUGGESTIONS` default `0` (byte-identical to before) | 5 refutation rounds, last round LOW only |

Earlier in the same programme (before this session's later half) the candidate also gained: 7A identity hardening
(`b01e9cfa`), 5.5 mapping with per-request id enums + adaptive thinking (`95297a91`), relations v3 (`08183b6d`), a
provider 400 treated as a definite uncharged failure (`9c2ffa92`), runner smart-format and transcription-relations
terms. Records: `docs/rebuild/v1/standing-campaign/`.

**Not integrated, by decision:** spoken-heading release (`1a05bc5a`) and other-question heading hold (`b75ffef1`) —
confirmed MEDIUM leaks/over-holds; Word EC1 (finalizer's name into signature rows) — HIGH, withdrawn; Word EC4/EC5
(instruction pairing, numbered-slot section names) — HIGH in three consecutive rounds, withdrawn; the conjoined-cessation
subject inheritance — HIGH releases of stopped medications, withdrawn. Pattern behind all of them: **a release decided by
reading wording or an omitted subject never closed** (`docs/rebuild/v1/standing-campaign/relations-v4-refutation-20261002.md`).

## 3. Live claude-sonnet-5-5 results (synthetic, QA worker)

| campaign | declaration | result | USD |
|---|---|---|---|
| 1 | `20261001-…testing.md` | model check PASS; notes 28/28 PASS (relations 26 correct / default 6, 0 unsafe); mapping FAILED attempt 32 (invented ids) | 0.277733 |
| 2 | `20261001-…testing-2.md` | mapping **10/10 PASS** (assist 36 right / 2 wrong / 0 missed / 10 held vs deterministic 36/3/9/0); transcription PASS, 0 answers | 0.296481 |
| 3 | `20261002-…testing.md` | relations v2 schema too complex (provider 400) | 0.280683 |
| 4 | `20261002-…testing-2.md` | notes PASS (v3: 27 correct / 9 over-held / 40 held-correct / **0 unsafe**); colonoscopy stopped by the app rate limit (not a batch) | 0.289633 |
| 5 | `20261002-…testing-3.md` | notes PASS (**v4: 27 / 9 / 40 / 0 unsafe**, same as v3); voice-first **4/4 PASS end to end** (pacing waited 188.8 s), **0 answers adopted** | 0.270637 |

Ordinary notes on the 5.5 relations default: **27 of 35 reference fields correct, 0 unsafe** (default request: 6–7).
Voice-first: Deepgram nova-3-medical + smart formatting transcribes the synthetic speech well; every answer is held by
the **patient-attribution rule** (a subjectless or "The clinician documents…" statement is the patient's only when the
note's first line presents the patient and only one side is named). Two model picks that the hold caught would have
been wrong. **Human-microphone dictation was never measured** (only synthesized speech).

## 4. Custom Word (first priority) — honest status

- **Default engine = legacy** (standing decision 2026-09-28: only legacy may ship until the Word gate B-W1 is measured).
  Legacy supports the owner's colonoscopy form D02 fully (17/0/7 on every path measured).
- **v3 engine (non-default)** accepts every one of the 50 measured inputs; of the **37 development/synthetic forms legacy
  refuses at upload, v3 finalizes and downloads 32** (validator passes except D05, whose original fails too), refuses 5 at
  the 100-answer-area cap (D11, D15, D28, D29, D35). This is the main lever for "upload a common Word form".
- **Word EC3 branch** `fix/v2-word-engine-v3` @ `278eb1a8` (NOT integrated): fail-closed withdrawal of answer areas in a
  cell vertically merged beside 2+ rows. Parity check over 1,239 inputs: every kept field identical to base; 575 inputs
  differ only by EC3 withdrawals; one declared exception (15 kept signing/protected fields lose a side prefix). Needs one
  narrow refutation, then integration (§6 step 3).
- **D02 on v3 + relations**: 0/17 held (bare 'withdrawn slowly' cessation, an opposed-claim pair, the consent rule).
  Declared residual; legacy unaffected.
- **The 18 'initial'/'signed' labels** the destination-roles salvage stopped generating: built as explicit-accept
  suggestions (`QUILLMD_ROLE_SUGGESTIONS`), default OFF, needs the owner decision in §5 before it is switched on.
- **Not measured**: the Word gate B-W1 (54/60 overall, 18/20 holdout, ≥75 % per family). The reserved holdout was never
  opened. No native-Word rendering check (validator only).

## 5. Decisions only the owner can make (with the recommendation)

1. **Role suggestions on real signing places.** With the feature on, 15 of the 17 must-hold signing/initials labels also
   get a suggestion (only wording separates them from the 18 regressions). Nothing is written without the clinician's
   click, which is audited. *Recommend:* accept (a), then fix V-1 (§7) and run a live qualification before enabling.
2. **Voice-first attribution.** May a dictated note that never presents the patient have its subjectless statements read
   as the patient's? *Recommend:* keep the hold; instead offer a one-click "this note is about the patient" confirmation
   at transcript review (an explicit-accept design, consistent with everything that survived refutation).
3. **Word engine route.** Keep legacy default; consider an *auto* mode (legacy where legacy accepts, v3 otherwise — no
   loss on legacy forms by construction) once EC3 is integrated and B-W1 is measured.
4. **Supersession over-holds.** A supersession naming nothing ('switched to the supine position') holds every answer in
   the note (14 D02 answers on such phrasing); keep the polysemous verbs 'hold'/'replace'? *Recommend:* keep (fails
   closed) and narrow only against the integrated base (§6 step 4).
5. **Billing visibility (R3B-3).** An owner of one department sees other departments' organization-paid held requests,
   including requester emails. Keep, or show the department name instead of the email.
6. Still open from before: patient-evidence floor for clinician-subject statements; headings that are not printed
   questions; `.doc` support; EC1 (the finalizer's own signer row is not filled on v3); session lifetime / re-enrolment
   window; sole-admin lockout; retention schedule (preserve everything until set); readiness thresholds; CPT product-use
   rights (CPT stays fully disabled until then).

## 6. Exact next steps for whoever continues (in order)

1. **Push the role-suggestion merge** `e578471b`: confirm the full core run is green (known host-only failures:
   `test_wm_narrative.ReviewCost.test_round_13…` wall-clock; ops `test_sonnet5_stages_plain…field_relations_version`),
   take BOTH CI views, push, wait for CI.
2. **Rotate the QA database password** (see §8) when no test run is open.
3. **Word EC3**: run one narrow refutation of `278eb1a8` (lenses: wrong mapping left by the pass; parity vs `b01e9cfa`),
   then merge into the candidate; re-run the isolation matrix and documents list.
4. **Supersession narrowing** (O-2/O-3: 'wrist'/'histology' read as agents; agent 'hold' with a complement) — measured
   only against the integrated base `c1fe4ab4`; refute before merge.
5. **Role suggestions V-1** (before anyone turns the setting on): reserve output budget for the role answers.
6. **Word gate B-W1** through the app on the development set, then (only as the final measurement) the holdout.
7. **Demo**: rebuild the QA demo environment on the final candidate; show campaign drafts labelled LIVE with request
   ids, fixture for new clicks, synthetic audio with the human-microphone gap stated.

## 7. Known residual risks (declared, not hidden)

- Role suggestions V-1: under '1' the role answers share the '0' output budget; near the cap the whole generation fails
  closed. RS4O-1 (LOW). Unaccepted suggestions are stored in answers, the API and the provider-result download.
- Supersession: brand/generic names, arrows ('Warfarin -> apixaban'), unlisted verbs ('superseded by', 'transitioned
  to'), class readings ('Anticoagulation: held.') stay with the model's judgement; 'INR 6.2, held.' not caught.
- Relations: an answer picked from another printed question's spoken section is adopted on the model's word; capacity
  under adaptive thinking leaves thinking no reserved room (fail-closed; live profile uses between_tools).
- 7A: R6R-1 (a dictation quoted after a redaction's journal append + a restore pairing inside a one-minute window leaves
  the file unreferenced); coding edge shapes R6C-1..5.
- CI: a runner whose apt mirror is slow can push `core-2` past its 30-minute limit (seen once: apt 10 min); cite the
  descendant rather than re-running the cancelled commit.

## 8. Operations and hygiene (read before running anything)

- **QA database password exposure (OPS-1).** A refuter ran a test runner under `bash -x`, which printed the synthetic QA
  PostgreSQL password (container `v1-sonnet5-qa-pg`, `127.0.0.1:55731`, synthetic data only) into its transcript. The
  shared runner `rebuild/.runtime/v1-sonnet55-20261001/mapping-r1/run.sh` now reads the password inside the child from
  `rebuild/.runtime/v1-sonnet5-campaign/qa-db/password` (0600). **Rotate it** (§6 step 2): connect as `quillmd_qa`,
  `ALTER ROLE quillmd_qa PASSWORD '<new>'`, rewrite the file atomically at 0600. Never trace a runner; never put the
  password on a command line.
- **Disk at 91 % (28 GB free).** `rm`/`shred` are denied to the agent. The owner can reclaim ~9 GB of verified-safe
  scratch with `bash /opt/meddoc-pro/rebuild/.runtime/v1-sonnet55-20261001/reclaim-user-run.sh` (shreds documents first,
  stops on any shred failure).
- Tests: always through a copy of `mapping-r1/run.sh` (QA PostgreSQL, fixture AI, random secret, TMPDIR outside
  `/opt/meddoc-pro/rebuild`). CI's ops partition is `python -m unittest discover -s ops -p 'test_*.py'` from `rebuild/`.
- Live sends only via `bash scripts/run-ruled-mutation.sh --declaration <committed md> -- rebuild/.venv/bin/python -B
  rebuild/ops/standing_qa.py run --stage <stage> --declaration <same>`; a re-measure is a NEW declaration file
  (`<date>-quillmd-v1-standing-api-testing-<n>.md`); pricing lines from `standing_qa.py pricing`.
- Shared tree `/opt/meddoc-pro` stays on `main`; never `git -C` it mutatingly; feature work in worktrees
  (`scripts/link-worktree-venv.sh` for the venv). Prose via `git commit -F`. Two CI views before every push.
- Task ledger with every branch and status: `rebuild/.runtime/v1-sonnet55-20261001/task-ledger.json`. Refutation results
  per round: `rebuild/.runtime/v1-sonnet55-20261001/refute-*/result.json`.

## 9. What was not done

No public launch, real patient data, deploy, contract, purchase or live Stripe act. The Word gate and the holdout were
not measured. No human-microphone recording. The demo environment was not rebuilt. No V1-readiness claim.
