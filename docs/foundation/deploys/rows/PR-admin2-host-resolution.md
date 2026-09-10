# §2.5 AUTHOR ROWS — ADMIN-2 host → practice resolution (branch `feat/admin2-host-resolution`)

**Written before the act**, per ruling #184 and the ADMIN-1 board filing: a
passenger without author rows is a FINDING, not a pass. The PR number is not
known at writing time; rename this file to `PR-<n>.md` when the PR opens and
keep the body byte-identical.

**Lane:** Design/Admin, under ruling #310. **Ruling:** #196 (the subdomain
model). **CODE-ONLY — no migration, no compose change, no env change.**

**THE ONE-LINE DECLARATION:** *nothing but the image ids* — with ONE declared
behaviour change for FORGED requests only (row AH2-C3), which no structural
count can see and which is therefore verified on QA, not in production.

Runtime files: `src/lib/practice-host.ts` (new), `src/lib/auth.ts`,
`src/lib/nextauth.ts`, `src/lib/api-error.ts`, `src/actions/auth.ts`,
`src/app/login/page.tsx`. Everything else in the diff is tests and docs.

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **AH2-C1** | the transcribe-md and worker image ids | the baseline ids | new ids | this IS the change; an unchanged id means the build did not carry the branch |
| **AH2-C2** | the string `PRACTICE_HOST_REFUSED` in the shipped SERVER bundle (`.next/server`) | **0 files** | **>= 1** | a string literal survives minification (a local identifier would not — measure the literal, not a name). Absent means the resolver is not in the image |
| **AH2-C3** | a signed-in `GET /login` on `app.` with a forged `X-Forwarded-Host: admin.quillmd.com` | redirects to `/admin` | redirects to the clinician home | ⚠️ **QA ONLY, on the byte-identical build, with the synthetic account.** Never probed in production — it needs a session, and a real doctor's session is never a smoke target. The honest-request path (no forged header) must be unchanged on both hosts |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **AH2-N1** | `PRACTICE_HOST_ROUTING` in the running `transcribe-md` and worker containers' `Config.Env` | **absent**, before and after (`docker inspect … --format '{{json .Config.Env}}'`) | ⚠️ **THE FLAG ROW.** Present with any value means the reconcile could be live before any ingress exists; `true` would refuse every sign-in on a host no DNS resolves yet — harmless only by luck |
| **AH2-N2** | `PRACTICE_HOST_ROUTING` in the CLIENT bundle (`.next/static`) | **0 files** | the flag is server-only by design; a hit means something in a client component reads it, and a client must never decide tenancy |
| **AH2-N3** | `AUTH_COOKIE_DOMAIN` in the running `transcribe-md` `Config.Env` | **empty**, unchanged | a `.quillmd.com` cookie would reach `admin.` and every practice subdomain (`Caddyfile:180-183` requires host-only). This PR deliberately does not set it |
| **AH2-N4** | audit rows with `errorCode = 'PRACTICE_HOST_REFUSED'` | **0 → 0** | with the flag off, `authorize()` never reaches the check; one row means the flag is on somewhere |
| **AH2-N5** | `_prisma_migrations` row count | unchanged | code-only; movement means a migration rode unnamed |
| **AH2-N6** | `practices` row count and `slug like 'solo-%'` count | unchanged (last measured by the plumbing recon at `6fcd21d0`: **199 / 195**) | this PR reads `Practice.slug` and never writes a practice row; `gate-admin3a-practice-write` still pins the three writers |
| **AH2-N7** | **clinical counts — visits, signed visits, patients** | **unchanged** from the deploying session's own baseline | ⚠️ **NEVER OMITTED, per §2.5.** Not pre-filled here: this author had no reason to read them and did not; the deploying session captures them in its baseline before the act and compares after |
| **AH2-N8** | co-tenant HTTP status (the hosts `verify-post-reboot.sh` checks) | unchanged | a code-only transcribe-md deploy must not move another tenant |

## VERIFY — structural, mutating nothing

    # AH2-N1 / N3 — positive control first: the instrument sees the env at all
    docker inspect meddoc-pro-transcribe-md-1 --format '{{json .Config.Env}}' | tr ',' '\n' | grep -c 'AUTH_URL='            # 1 (control)
    docker inspect meddoc-pro-transcribe-md-1 --format '{{json .Config.Env}}' | tr ',' '\n' | grep -c 'PRACTICE_HOST_ROUTING' # 0
    docker inspect meddoc-pro-transcribe-md-worker-1 --format '{{json .Config.Env}}' | tr ',' '\n' | grep -c 'PRACTICE_HOST_ROUTING' # 0
    docker inspect meddoc-pro-transcribe-md-1 --format '{{json .Config.Env}}' | tr ',' '\n' | grep 'AUTH_COOKIE_DOMAIN='     # AUTH_COOKIE_DOMAIN=

    # AH2-C2 / N2 — inside the new image
    docker exec meddoc-pro-transcribe-md-1 sh -c "grep -rl 'PRACTICE_HOST_REFUSED' .next/server | wc -l"   # >= 1
    docker exec meddoc-pro-transcribe-md-1 sh -c "grep -rl 'PRACTICE_HOST_ROUTING' .next/static | wc -l"   # 0

    # AH2-N4
    psql -tAc "SELECT count(*) FROM audit_logs WHERE \"errorCode\" = 'PRACTICE_HOST_REFUSED';"            # 0 -> 0

⚠️ **THE CONTROL ON C2 IS THE BEFORE VALUE.** `PRACTICE_HOST_REFUSED` does not
exist anywhere in the pre-deploy image, so a `>= 1` after is movement the
branch caused — not a string that was always there. Measure the before on the
old image in the baseline, not by assumption.

## WHAT THIS DEPLOY DOES NOT DO — so nobody judges it against the wrong promise

No practice is reachable on its own hostname after this deploy. That needs every
ingress leg on the ADMIN-2 RELAY row (wildcard DNS, host-nginx acme + 443
blocks, per-subdomain certificates, the Caddy wildcard block) **and** the flag
turned on — each a separate, declared act owned by the deploy owner / owner.
