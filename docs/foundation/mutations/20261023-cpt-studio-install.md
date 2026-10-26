# Prospective declaration: CPT Studio at cpt.quillmd.com (synthetic, login-protected)

Authority: the owner's directive recorded in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md ("Install a protected
synthetic demonstration at cpt.quillmd.com with normal HTTPS verification",
"Use a valid trusted certificate", "Use the existing authorized Corti
account", "Keep provider credentials server-side", "Preserve app.quillmd.com
and unrelated services"), under the 2026-10-23 standing authority it cites.
This is a new standalone service: no QuillMD source, database, users, files,
units or environment are shared, promoted or edited. No purchase, agreement,
new ACME account, real-patient processing or provider request is part of it.

Revision installed: 29e4d1f52939427ee277287e585b479912122679 (the merge commit of
PR #1435; image tag cpt-studio:29e4d1f52939).
Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision
29e4d1f52939427ee277287e585b479912122679 --receipts /home/claude/cpt-studio-install-20261023`, in this order:
preflight, secrets, image, db, app, reference, provision, http-vhost, cert,
https-vhost, verify. Read each receipt before the next phase. ops/INSTALL.md
describes every check.

## Baseline (read-only, 2026-10-26T19:07Z; the preflight receipt is binding)

- /etc/nginx/sites-available sha256: dealhunter cbc089226d5f9f55f3543ee277f16e7e91f08f2ea6737141d7471e155b3c4ebd;
  dealmason 6fd1916b6444caf394d30f49fe7d3e943b5cdf322e0bfe009bb5bd7724979c74;
  default ce0901350a021608139b5639cf4ccd7717bef8c3a9e4f79031eb46386b67b03f;
  leathererp 31988a1ddea72ae44c7dd92aa707424e5a64c8ddd692721476ef3a5a6221e791;
  quillmd e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638;
  quillmd-email-preview c212671e1f33b5b8cbde914e67f546d72ab1241fa829de3ec2587f4b8cfa9b1a;
  quillmd-staging 965e41b7398c0dfd667826a2fa2f18f4d61fc323a87234981dbd33379c5275ad;
  voice.kasitcorp.com 051f70eaec42aa7c7736cefb59668b9b082989ca076c31924a320635600f96eb;
  quillmd-email-preview.htpasswd root:www-data 0640 (not readable; presence only).
  /etc/nginx/nginx.conf 196a622ce459de81985338b381d55f5ba357bfa3d7a22a56551c76a4b5504dca; conf.d empty.
- sites-enabled: dealhunter, dealmason, leathererp, quillmd (../sites-available/quillmd),
  quillmd-email-preview, quillmd-staging, voice.kasitcorp.com. No quillmd-cpt.
- Local routing (HEAD through local nginx, per Host/SNI): 55 name/port pairs,
  identical across three samples. cpt.quillmd.com currently lands on the
  default servers: :80 → 200 (dealhunter), :443 → dealmason certificate
  36247855cc857bb0…, exactly as an unknown host does.
- https://app.quillmd.com/health/ → 200 {"status": "ok", "data_mode": "synthetic-only",
  "surface": "doctor", "release": "67acb2628b84c2be25f379a15168aa802350c060"}.
- scripts/check-cotenants.sh → exit 0: quillmd.com 200, www 200, app 302, admin 503, pro 410.
- Docker: 57 containers (21 running), 39 volumes, 13 networks; none of
  cpt-studio-db/-web/-worker, cpt-studio-net, cpt-studio-pg, cpt-studio-files
  exists (cpt-studio-test-pg is the session's disposable test database, not
  touched). Ports 127.0.0.1:9150 and 55451 free. uid 10150 runs no task on the
  host (uid 10001 is used by the voiceassistmain-agent containers, which is why
  the image does not use it). The pinned helper and postgres images are present.
- DNS: cpt.quillmd.com A 147.189.172.8, no AAAA.
- Let's Encrypt lineages referenced by enabled vhosts: quillmd.com,
  staging.quillmd.com, voice.kasitcorp.com (dealmason and leathererp use their
  own certificates). The full list, renewal-config hashes and the single ACME
  account id are recorded by path in the preflight receipt; key material is
  never opened.
- Every figure above equals the 2026-10-23 22:05Z look this declaration was
  drafted from; none moved in the three days between.

## Expected changes, per phase

- preflight: none. One random ACME probe file is written to
  /var/www/certbot/.well-known/acme-challenge/ and removed.
- secrets: new /etc/cpt-studio/ (root 0700) holding app.env and db.env (root
  0600, generated inside the root helper, never displayed) and
  corti-credentials.env (byte copy of /etc/quillmd-corti-test/credentials.env,
  10150:10150 0400; only its four key names are checked).
- image: new local image tagged with the revision's first 12 characters, built
  from git archive of 29e4d1f52939427ee277287e585b479912122679 cpt-studio/
  (base python:3.12-slim-bookworm pinned by digest).
- db: new bridge network cpt-studio-net, volumes cpt-studio-pg and
  cpt-studio-files, container cpt-studio-db (postgres 17.11-alpine pinned by
  digest, uid 70, all capabilities dropped, 512 MiB, 127.0.0.1:55451,
  restart unless-stopped).
- app: migrations into the new empty database; containers cpt-studio-web
  (127.0.0.1:9150, 768 MiB) and cpt-studio-worker (1.5 GiB), read-only root,
  tmpfs /tmp, cap-drop ALL, no-new-privileges, uid 10150, no swap, no core
  dumps, restart unless-stopped. Provider mode live with
  CPT_STUDIO_AUTHORIZATION_REF=docs/foundation/rulings/2026-10-23-cpt-studio-gi.md
  (confirmed by the lead: the directive's "Use the existing authorized Corti
  account"); the Corti credentials are mounted read-only into the worker
  only, after the application's own loader has parsed them in that mount
  layout with no network (before migrations, so a bad file changes nothing).
  The installer itself sends no provider request; the first live request
  happens during browser verification, under the single-flight, bounded,
  duplicate-safe controls of the application.
- reference: the two pinned CMS zips (RVU26D sha256 521ff0f4…06e6, 6,181,360
  bytes; 2026-Q4 practitioner MUE sha256 45743367…0d00, 407,831 bytes) copied
  into cpt-studio-files/reference/ and imported as two ReferenceSource rows
  (code-keyed facts only, descriptors dropped) with the pinned release, URL
  and window and the retrieval times the operator states for the downloads
  (--pfs-retrieved-at, --mue-retrieved-at). Arguments: --pfs-zip
  /home/claude/cpt-studio-reference-20261026/rvu26d-updated-08-26-2026.zip
  --pfs-retrieved-at 2026-10-16T20:26:58Z (its download record) --mue-zip
  /home/claude/cpt-studio-reference-20261026/medicare-ncci-2026-q4-practitioner-services-mue-table.zip
  --mue-retrieved-at 2026-10-23T21:01:44Z (the downloaded file's own time; no
  separate record). Both copies were checked against the pinned sizes and
  sha256 before this declaration was committed.
- provision (--owner-username owner): Category gastroenterology, one
  Gastroenterology workspace, one human owner account ("owner") and one agent
  reviewer account labelled as an automated agent;
  /etc/cpt-studio/initial-credentials.json (root 0600, both)
  and /home/claude/.cpt-studio/agent-credentials.json (0600, agent only).
- http-vhost: new /etc/nginx/sites-available/quillmd-cpt (HTTP stage: ACME
  path and a 301 to https only) and the sites-enabled symlink; nginx reload.
- cert: new lineage cpt.quillmd.com (webroot /var/www/certbot, existing
  account, --keep-until-expiring); the host certbot timer renews it.
- https-vhost: quillmd-cpt replaced by the HTTPS stage (byte-identical HTTP
  block plus the :443 block proxying to 127.0.0.1:9150); nginx reload.
- verify: none.

## Must not change

The quillmd vhost (e9aa049d…7638) and every other sites-available file listed
above; nginx.conf and conf.d; every sites-enabled entry other than the new
quillmd-cpt; the local routing of all 55 co-tenant name/port pairs and of an
unknown host (status and certificate per SNI); app.quillmd.com /health/ (status
and release); check-cotenants.sh results; every container running at preflight
(same id, still running); every existing volume; every other Let's Encrypt
lineage and its renewal config, and the ACME account set; the QuillMD rebuild,
its database, users and files. No `nginx -t` warning may be added.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say
ok. In particular: secrets reports names/modes only; image reports the
revision label, user 10150, English OCR, passing Django checks and a WSGI load
as its own user on a read-only root; app reports
health {status ok, service cpt-studio, data_mode synthetic-only, database ok,
release 29e4d1f52939427ee277287e585b479912122679} through 127.0.0.1:9150 and a
worker that stayed up;
http-vhost proves the ACME probe is served for cpt.quillmd.com and the 301;
cert records the lineage by path with other lineages unchanged; https-vhost
proves https://cpt.quillmd.com/health/ with normal certificate verification
and SNI, one copy each of HSTS, nosniff, Referrer-Policy and X-Robots-Tag, a
444 for a mismatched SNI, and the ACME path still served; verify finds no
difference from the preflight baseline beyond the expected changes.

## Rollback per phase

Vhost phases restore the exact previous file state automatically on any
failed check (validate, reload). rollback-vhost removes quillmd-cpt only when
its bytes are this installer's, validates, reloads and proves cpt.quillmd.com
routes like an unknown host again; the lineage is kept. app restores the
parked web/worker pair automatically on failure; rollback-app removes web and
worker and keeps the database, volumes, image and secrets (applied migrations
are not reversed). provision discards its staged credentials on failure.
secrets, db, image and reference are left in place; removing them is a manual,
separately declared act.

## Stop conditions

Stop and diagnose — do not rerun — on any non-zero phase exit; any routing,
health, check-cotenants or file-hash difference; any new nginx warning; a
quillmd vhost sha256 that is not e9aa049d…7638; DNS other than A
147.189.172.8 alone; anything other than exactly one ACME account (certbot is
never allowed to register one); partial or altered secrets; a leftover
*-previous container or staged credentials file; ports 9150/55451 held by
anything else; any task outside CPT Studio running as uid 10150; or a receipt
that does not say ok.
