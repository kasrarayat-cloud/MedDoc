# SEC-01 — `@anthropic-ai/sdk` insecure default file permissions in Local Filesystem Memory tool

**Severity:** SEC moderate (npm audit)
**Reachable from production runtime?** NO — we don't use the local-filesystem memory tool

## What

`@anthropic-ai/sdk` ships a `LocalFilesystemMemoryTool` helper that
creates files with default permissions (typically 0644 — world-
readable). On a multi-tenant filesystem this could leak prompts /
responses written via the tool.

Source: GitHub Advisory GHSA-xxxx (npm audit moderate severity)

## Reachable from prod?

No. We use the SDK strictly for API calls (`new Anthropic({ apiKey
}).messages.create(...)`). The Local Filesystem Memory Tool is a
separate helper class that ships with the SDK but is NOT instantiated
anywhere in our worker pipeline. Verified via:
```bash
rg 'LocalFilesystemMemoryTool|FilesystemMemoryTool|memory_tool' apps/ packages/
# 0 hits
```

## Recommended remediation

`npm update @anthropic-ai/sdk` on next maintenance window. No
emergency fix needed because the vulnerable surface is unused.

## Risk if NOT fixed
- npm audit continues to flag this in CI (annoyance only)
- If a future feature decides to use the FS memory tool, the
  vulnerable version is in place

## Status
Plan-only. Bundle with next maintenance update.
