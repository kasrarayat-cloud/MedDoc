# Corti CPT dependency — held

The 2026-10-16 prediction returned selected CPT **99213**. In the subsequent
single agent task, this account's `coding-expert` **actual `list_code_systems`
result omitted CPT from 26 configured systems**. This is a tested limitation
of that connector route, not a claim that Corti prediction lacks CPT support.

**Missing external capability:** account-accessible CPT descriptor and relevant
E/M-rule lookup/verification with authoritative source attribution, CPT content
release, and effective dates covering **2026-10-16**. Software/model versions
are not CPT releases. Selected-code support, descriptor/rule correctness and
dated-source provenance remain unresolved; missing provenance does not prove
99213 wrong. CPT activation remains held. Commercial CPT rights and dashboard
integration acceptance are separate requirements.

Evidence remains private and unchanged under
`/home/claude/quillmd-corti-test/agent-verification-20261016/`:
`observation-recovery/001-existing-task.raw.json`,
`observation-recovery/002-trace-01.raw.json`, and `assessment.json`.
The original trial FAIL and adapter commit `b998d9613` are preserved.

## Offline context-ID repair

`core.corti_agent_recovery` accepts bare UUID and `ctx.UUID` context IDs without
rewriting them. Recovery parses the saved acceptance even when the failed
transport log has no task/context fields, makes one read through a GET-only
interface, and requires the returned task/context identity to match exactly.
It has no authentication, submission, creation, polling, retry or resumption
path. A future transport must separately disable its own retries. The original
one-shot runner remains immutable failure evidence; no live caller is connected
by this repair.

Focused checks:

```bash
PYTHONPATH=rebuild python3 -m unittest core.tests.test_corti_agent_recovery -v
python3 rebuild/ops/replay_corti_agent_recovery.py \
  --evidence-dir /home/claude/quillmd-corti-test/agent-verification-20261016 \
  --output /home/claude/quillmd-corti-test/context-repair-20261016/a-new-offline-result.json
```

The second command supplies the recorded GET response locally and blocks socket
connections; it performs no provider calls. This parser repair does not resolve
any CPT verification or provenance dependency.
