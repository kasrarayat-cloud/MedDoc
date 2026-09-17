# Declared delta: obsolete QuillMD application images, 2026-09-17

The user's latest instruction explicitly authorizes deletion of verified old
QuillMD application/admin implementation and obsolete dedicated resources,
with no migration and **no old-system archive requirement**. That instruction
supersedes prior rollback-image/archive retention for this deleted old
application. Marketing, other projects, shared services, useful credentials,
certificates and domains remain protected.

The first retirement is complete and independently recorded in
`docs/rebuild/retirement-result.json`. Its obsolete application images remain:
85 distinct images with 104 exact tags in
`docs/rebuild/obsolete-image-manifest.json`, captured 2026-09-17T08:33:02Z.
Every candidate was verified unreferenced by **all running and stopped
containers**, with no tag outside these exact repositories:

- `meddoc-pro-transcribe-md`
- `meddoc-pro-transcribe-md-worker`
- `meddoc-pro-meddoc-pro`
- `meddoc-pro-form-detect`
- `meddoc-pro-gotenberg`

Docker reports 24,305,405,245 unique image bytes (about 22.64 GiB) for this
set and 94,466,514,116 logical bytes. Logical size double-counts shared layers;
neither number guarantees reclaimed disk because build cache/layer references
may retain data. The lead measured root disk at 91% used / 28 GB available after
dependencies and browser work; preflight had measured 90% / 30 GB.

Expected change: remove only those 104 pinned image tags using
`docker image rm --no-prune`, without force. No container, volume, network,
build cache, other image, file, credential, service, domain or certificate is
deleted or recreated. No archive/rollback copy is made. Any new image consumer,
changed tag/digest or shared tag refuses the operation.

Must remain unchanged: every running/stopped container and its image/running
state; every unselected image ID; healthy marketing HTTP 200; Caddy/nginx and
all shared ingress configuration. The live maintenance response is a separate
deployment action owned by the lead.

The script and exact manifest must be committed and unmodified before the gate
runs. Script defaults to read-only checks. It repeats consumer/tag checks before
each removal, uses no force/global prune/untagged-parent pruning, and writes
success or partial-progress evidence to
`docs/rebuild/obsolete-image-cleanup-result.json`.

```bash
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260917-quillmd-obsolete-images.md \
  -- python3 scripts/retire-old-quillmd-images.py --execute
```
