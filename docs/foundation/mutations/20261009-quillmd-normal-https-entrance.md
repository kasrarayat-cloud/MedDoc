# QuillMD fresh-browser normal HTTPS entrance

Declared before installation, relative to exact installed Word release
`7d4cfbb76d8f22c2bdad27707b92799fdf85f75c`.

The normal 443 route required a grant obtained on 9443 and deliberately refused
its own private sign-in route. Fresh owner browsers therefore received a 503
maintenance message despite healthy upstreams. Prior authenticated acceptance
did not prove fresh normal-domain access; preserve that evidence and failure.

The exact reviewed change is `rebuild/core/preview_access.py`, the affected
`test_owner_normal_origin.py`, the new `test_owner_normal_entrance.py`, and this
declaration. Reuse the existing private-credential, browser-bound flow, CSRF,
rate-limit and signed-grant protocol on canonical HTTPS. Anonymous browser reads
reach only sign-in; API requests and application mutations require a grant.
Account verification, owner/invite scope, administrator MFA, synthetic-only
enforcement, renderer restrictions and Word generation/export remain intact.

Use the reviewed code-only recovery procedure: a fresh authenticated encrypted
backup and operation snapshot precede the exact complete-source advancement
and restart of only the three QuillMD services. Expected changes are those four
source paths, the release label and QuillMD unit process state. No migrations,
database, approved-template, static, ingress or unrelated-resource change is
permitted during installation. Preserve original baselines, original failures
and coherent rollback material. On failure recover a proven complete known
source/environment pair; never reset source or replay migrations.

After the protected installation interval, verify a fresh normal-origin browser,
existing doctor account and administrator MFA without using 9443 or carrying an
old access cookie. Verify public DNS and TLS from outside the VPS without a
tunnel/hostname override. Actual owner-desktop success is a separate observation
and must not be substituted with VPS-local acceptance. No paid model request is
authorized or needed for this access recovery.
