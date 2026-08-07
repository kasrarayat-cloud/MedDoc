# Ingress TLS outage — every public hostname, ~6h15m — 2026-08-07

**Severity: P1.** `app.quillmd.com` (pilot doctors log in here), `quillmd.com` and
`www.quillmd.com` returned **502 Bad Gateway** from 08:33 UTC to 14:48 UTC.
Measured at detection: **`/login` 0 of 30 requests succeeded.** After the fix:
**30 of 30.**

Nothing was lost and nothing was written wrong. No clinical count moved
(`26 visits · 15 patients · 16 signed · 196 users · 197 practices`, byte-identical
before and after). The app and worker containers were healthy and correct
throughout — they were simply unreachable.

---

## 1. What broke

Ingress is `internet → host nginx (owns :80/:443) → Caddy at 127.0.0.1:8443 →
app containers`. nginx re-encrypts to Caddy with `proxy_ssl_name $host` and
`proxy_ssl_verify off` (`/etc/nginx/sites-enabled/quillmd:36-38`).

Caddy had **no certificate** for `quillmd.com`, `www.quillmd.com` or
`app.quillmd.com`. Every fresh TLS handshake was answered with
`tlsv1 alert internal error` (alert 80), and nginx turned that into a 502:

    SSL_do_handshake() failed (SSL: error:0A000438:SSL routines::tlsv1 alert
    internal error:SSL alert number 80) while SSL handshaking to upstream,
    upstream: "https://127.0.0.1:8443/login", host: "app.quillmd.com"

**501 occurrences**, first at **08:33:39**. The previous log file
(`error.log.1`, ending 2026-08-06 22:16) contains **zero**. The onset is exact.

## 2. Why it broke — three things, and only the third is a surprise

**(a) Public ACME cannot succeed on this hop, and never could.** Both challenge
types are blocked by the topology itself:

| Challenge | Why it fails |
|---|---|
| `tls-alpn-01` | nginx owns `:443`, so the ALPN handshake never reaches Caddy — `remote error: tls: no application protocol` |
| `http-01` | nginx owns `:80` and serves `/.well-known/acme-challenge` from `/var/www/certbot`, so Caddy's token **404s** |

Caddy retried every ~10 minutes for two months, fell back to
**acme-staging**, and renewed nothing. Attempt 19 was still in flight at
detection.

**(b) The certificates expired.** `admin.quillmd.com`'s on-disk cert is dated
**Apr 25**; at detection Caddy logged `remaining: -1235090s` — expired 14 days
earlier.

**(c) ⚠️ THE EXPIRY WAS INVISIBLE, AND THAT IS THE ACTUAL DEFECT.** nginx does
not verify the upstream certificate, so an **expired** cert on this hop works
perfectly. Caddy kept serving the expired certs **from its in-memory cache** and
nothing anywhere reported a problem.

certmagic's storage clean then removed them from disk
(`/data/caddy/last_clean.json` = **2026-08-06 15:04**), leaving the memory cache
as the only copy. The host rebooted at **08:31:29**; the cache went with it;
Caddy came back holding only `admin.quillmd.com` and a self-signed cert for the
bare IP.

    /data/caddy/certificates/
      acme-v02.api.letsencrypt.org-directory/admin.quillmd.com/   ← expired Apr 25
      local/147.189.172.8/                                        ← self-signed

**So the failure was armed on 2026-08-06 and fired on the next restart.** A
reboot is not the cause; it is the trigger that revealed a state that had been
wrong for weeks.

### Why it looked intermittent

nginx reuses upstream TLS sessions. Requests riding an **already-resumed**
session kept working (`"resumed": true` in Caddy's access log), so `/visits`
answered 307 and `/board` answered 200 in the same second that `/` and `/login`
answered 502. The first read of the symptom — *"path-specific"* — was wrong.
Only a **fresh-handshake** probe per SNI separated the two:

    quillmd.com        FAIL (alert 80)      app.quillmd.com    FAIL (alert 80)
    www.quillmd.com    FAIL (alert 80)      admin.quillmd.com  HANDSHAKE OK

`admin` was the control: it worked precisely because it was the one name whose
cert survived the storage clean.

## 3. ⚠️ THE FIX WAS FILED 65 DAYS AGO AND MISCLASSIFIED AS COSMETIC

`docs/qa-reports/site-down-20260603.md` §9.5, follow-up **5 of 6**, priority
🟢:

> **🟢 Caddy ACME noise** — Caddy still retries LE every ~10 min and now never
> needs to. Add `tls internal` to the quillmd Caddy blocks.

It was never executed. The word that did the damage is **"noise"**: the retries
were treated as log spam, when the certificates those retries were failing to
renew are the ones this hop actually serves. The same report's §6.2 had already
recorded *"Certs aren't expired (~46 days left), so this is **latent, not the
outage**"* — true when written, and 46 days is a deadline, not an all-clear.
Nothing carried that date forward.

Meanwhile `docs/DEPLOYMENT_RUNBOOK.md` §5.6 has asserted since 2026-07-28 that
Caddy *"sits behind it on `127.0.0.1:8443` **with its own internal certs** and is
not involved."* **That sentence was false for two months.** It described the
intended design, was read as a description of the running system, and so the gap
between the two was never visible to anybody reading either document.

> **A follow-up whose priority was set by how ANNOYING the symptom is, rather
> than by what the symptom is a symptom OF, is a defect with a due date nobody
> wrote down.**

## 4. The fix

`tls internal` on all four site blocks in `Caddyfile` — Caddy's own CA issues
the hop's certificate. nginx never verifies it and a browser never sees it, so a
publicly-trusted cert was never needed here. It also ends the ACME retries
permanently, because there is nothing left to obtain.

The public certificate is unchanged and remains nginx's, at
`/etc/letsencrypt/live/quillmd.com/fullchain.pem`, renewed by certbot with the
deploy hook installed on 2026-07-28 (runbook §5.6). **This change does not touch
it.**

### ⚠️ A FILE BIND-MOUNT BINDS THE INODE — the edit did not reach the container

`docker-compose.yml` binds `/opt/meddoc-pro/Caddyfile` (a **file**, not a
directory). An editor that writes-then-renames replaces the inode, so the
container kept the orphaned original:

    host inode 655733   container inode 656165   → `grep -c 'tls internal'` = 0

`caddy reload` answered **`config is unchanged`**, correctly.

⚠️ **AND `caddy validate` HAD ALREADY REPORTED `Valid configuration`** — it runs
inside the container, so it validated the **old** file. A green from a check that
never saw the change is the vacuous-assertion class in its purest form; it was
caught only because the applied-count assertion was run against the container
rather than the host. Rewriting in place did not help either — the mount is
pinned to an inode that is no longer reachable by path. `docker compose up -d`
also declined (no config-hash change).

**`--force-recreate` is what re-resolves the bind**, and it is the better proof
anyway: it verifies the fix from a **cold start**, which is the exact transition
that caused the outage.

## 5. Verification — declared before it ran

**MUST change:** 8443 handshakes for `quillmd.com`/`www`/`app` go alert-80 → OK,
issuer `Caddy Local Authority`; `admin`'s issuer moves off the expired LE cert;
`/login` 502 → 200 sustained; no new `SSL_do_handshake() failed`.

**MUST NOT change:** app/worker image ids, migrations, clinical counts, the
container census, `pro.quillmd.com` 410, host nginx config and its public cert.

Measured — the entire baseline diff, and nothing else moved:

    - quillmd.com        alert number 80          + issuer=CN = Caddy Local Authority - ECC Intermediate
    - www.quillmd.com    alert number 80          + issuer=CN = Caddy Local Authority - ECC Intermediate
    - app.quillmd.com    alert number 80          + issuer=CN = Caddy Local Authority - ECC Intermediate
    - admin.quillmd.com  issuer=Let's Encrypt E7  + issuer=CN = Caddy Local Authority - ECC Intermediate
    - meddoc-pro-caddy-1 Up 6 hours               + meddoc-pro-caddy-1 Up 40 seconds

    /login          0/30 → 30/30
    containers      20/20 identical
    image ids       transcribe-md a9280a75… · worker cc913dd3…   UNCHANGED
    migrations      90                                            UNCHANGED
    clinical        26 visits · 15 patients · 16 signed · 196 users · 197 practices · 10560 audit
    co-tenants      307 / 404 / 200 / 200 / 410                   UNCHANGED

⚠️ **ONE STATED WEAKNESS IN THE VERIFICATION.** "Zero handshake failures since
the fix" was first computed over a **window containing no log lines at all** — a
true statement about an empty set, which is worth nothing. The honest form, with
the boundary given: `error.log`'s last line **of any kind** is `14:48:08`,
**34 seconds before** Caddy restarted at `14:48:42`; there are no error lines at
14:49 or later; and `access.log` is demonstrably live over the same window
(105 `/login` requests recorded). Both controls are stated because the first one
failed.

## 6. Carried

- **`pro.quillmd.com` also took `tls internal`.** Its container is stopped and
  nginx 410s it at the edge, so the block is unreachable today — it is included
  so that no name in this file can re-arm the same failure.
- **The expired `admin.quillmd.com` LE cert and the ACME account data remain on
  disk**, now unused. Not deleted in this change: deleting state during an
  incident fix is how a rollback stops being possible.
- **This class has no monitor.** The only signal was user-visible 502s, and the
  standing checks are all green — correctly, since none of them looks at the
  ingress hop. `bash scripts/check-*.sh` cannot see this. A fresh-handshake probe
  per SNI is the check that would have caught it two months early, and it does
  not exist yet.
