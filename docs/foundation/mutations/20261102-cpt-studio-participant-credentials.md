# Prospective declaration: CPT Studio participant credentials (the installer's secrets phase only)

Authority: the owner's directive of 2026-11-02 ("Wire them through the existing installer/secret mechanism and run
minimal authorized synthetic access checks"), recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md
with this session's interpretation (b), under the 2026-11-01 harness directive and the 2026-10-23 standing synthetic
authority it cites. No QuillMD source, database, units, files or environment are touched. No provider request,
purchase or agreement is part of this act (the access checks are a separate step, outside this door).

Revision: e3c05bc007c66f5145b8621309e5727c541e858a, the head of feat/cpt-studio-harness-20261101 (draft PR #1459),
whose installer knows the harness participants' credentials (installed CPT Studio, 80df1831d168, does not). Only the
`secrets` phase runs, from a clean checkout of the commit that lands this declaration (a descendant of the revision
that changes nothing under cpt-studio/ or the door):

    bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md -- \
      python3 -B cpt-studio/ops/install.py --phase secrets --revision e3c05bc007c66f5145b8621309e5727c541e858a \
      --receipts /home/claude/cpt-studio-install-20261102

No other phase runs under this declaration. The release is NOT installed by it: the harness is still under refutation,
and its install will have its own declaration.

## Baseline (read-only, 2026-11-02T05:57Z)

- `/etc/cpt-studio/`: root:root 0700; `app.env` root:root 0600; `corti-credentials.env` 10150:10150 0400; `db.env`
  root:root 0600; `initial-credentials.json` root:root 0600. Nothing else.
- `/etc/cpt-studio-provider-sources/`: root:root 0700 with exactly `anthropic.env` and `openai.env`, each a regular
  root:root 0600 file within 32,000 bytes holding its required key only (ANTHROPIC_API_KEY, OPENAI_API_KEY), checked
  05:52Z by key name and format, no value read out.
- Containers: `cpt-studio-web` 1f603dddd9aa and `cpt-studio-worker` 083b9af8657a on image sha256:88544c7cd33f, started
  2026-10-31T12:55:27Z and 12:55:30Z; `cpt-studio-db` 1c5498b3aacc (postgres:17.11-alpine, sha256:1bea307dfb3e),
  started 2026-10-30T22:01:02Z.

## Expected delta

MUST change:
- `/etc/cpt-studio/openai-credentials.env` and `/etc/cpt-studio/anthropic-credentials.env` created, each a regular
  10150:10150 0400 file copied from its source, with the receipt's key names OPENAI_API_KEY and ANTHROPIC_API_KEY
  (and no optional key); the receipt's participant states read `copied` (or the installer's word for a new copy).

MUST NOT change:
- the three-file set and `initial-credentials.json` (the receipt's secrets state reads `present`); the two source
  files and their directory; any CPT Studio container, image, volume or network (the three containers keep their ids,
  images and start times); nginx, certificates, QuillMD's units and files, every other service.

Stop conditions (no further step until judged): a receipt or log that shows a credential value; a secrets state other
than `present`; a participant state that is not a fresh copy; any change outside the MUST list.

Undo (if judged necessary): remove the two new files through the installer's root helper path; nothing else was
created. The running services never read them (they run 80df1831d168, which has no participant settings).
