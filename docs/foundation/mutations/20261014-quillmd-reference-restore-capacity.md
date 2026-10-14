# QuillMD reference restore capacity — source declaration

Date: 2026-10-14 UTC. Base: `06313135a0e7383f025273cad503bd1574c2dee4`.

This source change raises only the isolated backup restore container's memory and memory-plus-swap limits from 768 MiB to 2 GiB. Keeping those limits equal disables swap. The one CPU limit, network isolation, read-only root filesystem, 512 MiB database tmpfs, image pin, readiness gate, single restore transaction, full table/file verification, and owned-container cleanup remain unchanged. No native database, service, environment, provider request, or backup is changed by this commit. Installation requires its own subsequent declared action.

The complete official coding reference fixture reproduced an OOM kill during a single restore at 768 MiB. A new isolated container restored the identical dump once at 2 GiB in 16.44 seconds, with all 45 table fingerprints equal, all eight checked invariants zero, no OOM kill, and a measured server peak of 1,574,989,824 bytes. These are isolated resource results, not evidence of a native restore. The synthetic fixture contains public official ICD reference data and no patient records or licensed CPT content.

Protected evidence under `rebuild/.runtime/coding-release-20261014/resource-qualification-v1/`:

- `restore768-resource-qualification-v1.json`: `9be05f3045f387629820f3aa088d79993458ee10ea07a86738bc946d9c59eb48` (retained failure).
- `restore2048-resource-qualification-v1.json`: `f69e93f7506b7e60385cf23359921584765afbc459d38f60d00de712bd427500` (successful resource qualification).

The focused test executes the restore orchestration with intercepted Docker transport, checks the qualified capacity and unchanged isolation arguments, and verifies cleanup is still required. Existing backup and restore tests continue to cover authenticated objects, immutable history references, readiness, and failure evidence.
