# Process-argument credential exposure incident

- Detected: 2026-07-19T22:56:54Z
- Scope: local/shared-service process listing in the release engineering environment
- Production mutation: none
- Repository mutation: none
- PHI exposure: none observed
- Credential value retained in this evidence: no

## Incident

A broad read-only process listing returned an existing service credential embedded in a process command line. The value was exposed in transient tool output. It is intentionally omitted from this record and must not be copied into release evidence, logs, commits, or messages.

## Containment

- Stopped using broad process listings that include command arguments.
- Will use PID/name-only or explicitly redacted diagnostics if process inspection is necessary.
- The exposed value will not be used or reproduced.
- Production and the frozen release head remain untouched.

## Required disposition

The service owner must identify the affected environment from protected process configuration, rotate the exposed credential through the approved secret-management path, restart the affected service safely, and verify dependent health. Rotation evidence must contain identifiers and timestamps only, never the credential value. Until that occurs, credential rotation is a release blocker for production authorization.
