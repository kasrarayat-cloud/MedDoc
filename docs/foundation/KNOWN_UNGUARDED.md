# KNOWN_UNGUARDED — surfaces that are SEEN, judged, and left without an app guard

**Opened 2026-09-07 by ruling #210.** A surface listed here is one somebody
looked at and decided not to guard **at the application layer**, with the reason
written down and the condition that would change the decision named.

> ⚠️ **AN UNANSWERED QUESTION DECAYS.** This file exists because "out of scope"
> that is not recorded is indistinguishable, six weeks later, from a surface
> nobody examined — and *unknown* becomes *probably fine* through nothing but
> repetition. That is the same failure the tracked-fixture allowlist was created
> to stop: read it, adjudicate it, **write the decision down**.

> ⚠️ **AND "UNGUARDED" HERE NEVER MEANS "UNENFORCED".** Every row below is
> covered by a **data-layer** invariant. This file records the absence of the
> *friendly refusal*, not the absence of the rule. A row whose invariant is only
> a habit does not belong here — it belongs in a fix.

---

## §1 — the last-owner invariant (ruling #210)

**Enforcement:** the `users_last_owner_guard` trigger, migration
`20260907040000_admin5_last_owner_trigger`. It refuses any `UPDATE` or `DELETE`
that would leave a practice with members but **zero active OWNERs**, whatever
door the write arrives through.

**Friendly refusal (`wouldStrandPractice`):** `transcribe-md`'s admin
`suspend` and `soft-delete` routes, per #210.

### The doors deliberately left without the friendly refusal

| # | door | what it writes | why no app guard |
|---|---|---|---|
| 1 | `apps/meddoc-pro/src/app/system-admin/actions.ts:66` — deactivate | `isActive:false`, `deactivatedAt`, `deactivatedBy` | the app is decommissioned — see the caveat below |
| 2 | `apps/meddoc-pro/src/app/system-admin/actions.ts:229` — delete user | hard `prisma.user.delete` | same |

**What was checked and is NOT on this list, so the enumeration is falsifiable
rather than a shrug:**

- `actions.ts:341` (generic profile edit) writes `name`, `email` and the
  **legacy** `role` (`DOCTOR|ADMIN|STAFF`) only — never `practiceRole`, never an
  activity column. **It cannot reduce the count**, so it is not a door.
- `actions.ts:109` (reactivate) and `:387` (password reset) *increase* or do not
  touch the count.
- `transcribe-md`'s `changeMemberRoleAction` is guarded in the application
  already (ADMIN-5) and is not on this list.
- `POST /api/settings/delete-account` **is** a reducing door and is **not**
  listed here, because it is not unguarded: the trigger covers it, and #210
  names only the admin suspend/soft-delete routes for the app-layer message.
  Its behaviour is unchanged for the case that matters — a solo owner deleting
  their own account tears the practice down, which exemption 2 permits.

### ⚠️ THE PREMISE, CORRECTED — "the app is deleted" is TRUE AT THE EDGE AND FALSE IN THE TREE

Ruling #210 scopes these two doors out on the grounds that *"that app is deleted,
serves 410"*. **The 410 is real and the deletion is not.** Measured 2026-09-07:

| claim | what is actually true |
|---|---|
| serves 410 | ✅ `HTTP/2 410`, and it comes from the **HOST nginx** — `/etc/nginx/sites-enabled/quillmd:95`, `return 410 "MedDoc Pro was decommissioned on 2026-05-04 and taken offline on 2026-08-04."` — never reaching Caddy or the app |
| the app is deleted | ❌ `apps/meddoc-pro/` is **still in the tree**; `docker-compose.yml:92` still defines the service; the `Caddyfile` still carries a `pro.quillmd.com` block; the container `meddoc-pro-meddoc-pro-1` is **`Exited (143) 4 weeks ago`** — stopped, not removed |

**So the doors are unreachable today because of ONE LINE IN AN nginx CONFIG**,
which is a deployment fact and not a code fact. A single revival command plus a
config edit restores them, and neither action would look like re-opening a
security hole to whoever performed it.

⚠️ **AMENDED 2026-09-09, ruling #307 — THE COMPOSE DOOR IS GONE AND THE CHEAPER
ONE IS NOT.** The row above measured `docker-compose.yml:92` as still defining
the service; #307 removed that definition, so the compose-mediated revival named
in the original wording no longer resolves. **The container OBJECT survives the
service removal**: `meddoc-pro-meddoc-pro-1` is still `Exited (143)` with its
image, network alias and a currently-valid `DATABASE_URL` baked in, and
`docker start meddoc-pro-meddoc-pro-1` revives it **without reading any compose
file at all**. So the sentence's force is unchanged and its verb is different —
which is precisely why the argument for #210 was never allowed to rest on the
app being gone.

**This does not change the ruling's conclusion — it changes what the conclusion
rests on.** The right reason these doors are out of scope is the second half of
#210's own sentence: **"until the trigger makes them moot."** The trigger makes
them moot the day it ships, because they write to `users` and `users` is where
the refusal lives. The app-layer guard would only add a nicer error message to
an admin page nobody can currently load.

**What would put them back in scope:** the trigger being dropped or weakened.
Not the app being restored — a restored meddoc-pro is refused by the database
exactly like everything else. **That asymmetry is the argument for #210.**

---

## How to add a row

Name the door with `FILE:LINE`, what it writes, which **data-layer** invariant
covers it, and **the condition that would change the decision**. A row without
that last field is a note, not a record — and a note is what this file exists
to stop being enough.
