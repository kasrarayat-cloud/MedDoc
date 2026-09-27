# Production dependency lock — 2026-09-27

Prepared, not installed on a production target. All 63 existing application pins are unchanged.
The full fresh-environment resolver found `pip_api` requires `pip`, which had been implicit in
whichever venv bootstrap happened to create. The original failed resolver log is retained.
`pip==26.2.1` is now the explicit 64th pin; no installed application environment was changed.

The production lock is deliberately limited to Ubuntu 24.04 / CPython 3.12 / Linux x86_64.
64 binary wheels (no source builds) were acquired from explicit isolated `https://pypi.org/simple`.
The manifest records names, exact versions, filenames, byte sizes and SHA-256 values; local source
and lock SHA-256 values bind it to the reviewed files. Hashes pin these acquired artifacts; they do
not independently prove upstream code safety or replace a vulnerability review.

The bootstrap validates manifest/version completeness, installs with `--require-hashes`
and `--only-binary=:all:`, uses an explicit PyPI index and isolated pip user/environment settings,
and records the lock digest in its receipt. No host bootstrap or pip install was executed here.

## Verification

- Full offline pip resolution with `--ignore-installed`, `--dry-run`, `--no-index` and all hashes:
  PASS, all 64 pins and their transitive dependencies resolve without an implicit installed package.
- Dependency consistency and existing bootstrap dry-run class: 7 tests PASS. Controls reject changed
  versions, hashes, missing rows, altered provenance, duplicate artifacts and a source-option injection.
- A retained copy of one wheel was byte-modified: real pip hash mode refused it before installation.
- Original wheels and tampered control retained under the root `.runtime/v1-astra-recovery-20260927/`;
  logs and hashes are committed here. No provider calls, patient data, paid purchase or service action.

Official references checked 2026-09-27: [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/)
and [pip command options](https://pip.pypa.io/en/stable/cli/pip/). The target host must still execute and
record the approved installation; this package does not assert that AWS has been provisioned.
