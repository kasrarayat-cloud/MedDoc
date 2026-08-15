# §2.5 DECLARATION — `.dockerignore` nested-pattern fix

**Written and committed BEFORE the act.** This is a BUILD-PATH change: it alters
what enters the docker build context, and therefore what every future image is
built from. It ships no new application code.

## THE DEFECT, PROVED RATHER THAN ASSERTED

A bare directory name in `.dockerignore` matches **only at the context root**.
`node_modules` did not exclude `apps/transcribe-md/node_modules`; `.next` did not
exclude `apps/*/.next`. Both were entering the context and being copied over the
installed ones by `COPY . .`.

Demonstrated on a minimal context (`a/node_modules`, `a/.next`, `node_modules`),
built twice:

| `.dockerignore` | what reached the image |
|---|---|
| `node_modules` + `.next` (bare) | `/ctx/a/.next/marker.txt`, `/ctx/a/node_modules/marker.txt` — **the ROOT copies excluded, both NESTED ones through** |
| `**/node_modules` + `**/.next` | **nothing** — with a positive control showing `/ctx` still holds `a` and `.dockerignore`, so the zero is exclusion and not a broken walk |

Measured in this repository: **~27 MB** of nested workspace `node_modules` and
**391 MB** of `apps/*/.next` (marketing 68M, transcribe-md 192M, meddoc-pro
131M) were being shipped into every build context.

⚠️ **IT FAILS LOUDLY ONLY FROM A WORKTREE.** On 2026-08-14 a build from a git
worktree died with `cannot replace to directory /app/apps/transcribe-md/
node_modules with file`, because the nested path is a SYMLINK there. In
`/opt/meddoc-pro` those paths are real directories, so the identical mistake
succeeds silently while overlaying host modules onto the image's.

## MUST CHANGE

- image ids for `transcribe-md` and `transcribe-md-worker`
- the build context shrinks; nested `node_modules` and `.next` no longer appear
  inside the image

## MUST NOT CHANGE

- **nothing but the image ids.** No application code ships in this change.
- migrations stay **104** (RC-2's, applied by the deploy before this one)
- **every clinical count**: visits, signed, patients, templates, `audit_logs`
  monotonic
- the twin tables are NOT touched by this change
- **the secrets block is untouched.** `apps/*/.next/standalone/**/.env` stays,
  deliberately: it is this bug's own footprint — somebody hit the `.next` gap and
  patched one env path inside it rather than the pattern — and defence in depth
  on a secrets block is not something to trim while fixing build hygiene.

## SCOPE — ENUMERATED, NOT ASSUMED

Four other bare patterns (`.git`, `.claude`, `backups`, `docs`) were checked and
need no `**/`: the only nested `docs` and `.claude` live under
`landing-monolith/`, and the only nested `.git` under `.local/` — all already
excluded outright. Fixing them would be motion without effect.

## ⚠️ WHAT WOULD MAKE ME ROLL BACK

- the image build failing (this change's only real risk is a build that no
  longer finds something it was accidentally being handed)
- any application behaviour difference at all — there should be none
- a container failing to start on the new image

## ROLLBACK

Image tag `:pre-dockerignore-20260815`. Reverting the `.dockerignore` line is
also sufficient and affects nothing already running.
