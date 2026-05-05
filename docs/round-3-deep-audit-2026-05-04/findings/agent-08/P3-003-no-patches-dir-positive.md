---
id: A08-P3-003
title: No patch-package overrides — clean upstream story (positive)
severity: P3
domain: dependency-hygiene-supply-chain
status: open-positive
---

## Issue (positive observation)

The repo has **no `patches/` directory** and no `patch-package` script in any
`package.json`. There are zero monkey-patches against upstream dependencies.

## Evidence

```bash
$ ls /opt/meddoc-pro/patches 2>&1
ls: cannot access '/opt/meddoc-pro/patches': No such file or directory

$ grep -r '"patch-package"' apps/*/package.json packages/*/package.json package.json 2>&1
# (no output)
```

## Why this matters

`patch-package` overrides are technical debt with sharp edges:

- They invisibly fork upstream code, so an `npm audit` reporting a CVE on the patched
  package is misleading — the patched code may have introduced its own vuln.
- Every minor upstream bump risks a hunk-rejection that's easy to miss.
- They're a recurring source of "why is this dep broken in production but fine on my
  laptop?" tickets.

Carrying zero patches means every dep we ship is bit-identical to the upstream tarball npm
shipped. That's the right starting point for a HIPAA-compliant medical app, and worth
documenting as deliberate.

## Recommended fix

No fix. Keep doing this. If a future dep bug forces a patch, prefer:

1. **`overrides`** with a forked + patched version published to a private npm scope.
2. **A documented npm fork** under @meddoc/<pkg>-fork with public-trail commits.

…in that order, before reaching for `patch-package`.

## Cross-domain hooks

- A08-P3-001 (overrides): any future emergency patch should land here, not in a
  `patches/` dir.
