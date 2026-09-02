# A ROTATING PIN IS STILL WORTH PINNING — ITS JOB CHANGES FROM "NEVER" TO "GO AND FIND OUT WHY"

**Recorded 2026-09-01, by owner ruling #163.**

## The measurement

A runbook pinned a CI host's SSH host-key fingerprint, with the instruction
**pin this**. After a control-panel *Restart* — nothing else, confirmed by the
owner — **all three host keys had changed**. A reboot does not change host keys.
Read against the pin, that is the signature of a compromised or replaced machine,
and the correct immediate action was taken: **stop, do not accept, escalate.**

It was benign. The mechanism:

```
/var/lib/cloud/instances/615d6c98…    ← old
/var/lib/cloud/instances/559f7b48…    ← current
```

The **cloud-init instance-id changed** across the restart. cloud-init treats a
new instance-id as a FIRST BOOT and its ssh module regenerates every host key.
File mtimes confirmed it exactly: boot `18:44:37`, all three keys written
`18:44:52`.

## What settles it is PERSISTENT IDENTITY, not the key

A reimage and a cloud-init rotation both present new keys. The key itself cannot
distinguish them. What can is whether the machine's own durable state survived:

| check | reimage | rotation |
|---|---|---|
| CI runner registration ids | **new** | **unchanged** — measured `21` / `22` |
| runner labels | rebuilt or absent | unchanged |
| `/var/lib/cloud/instances/` | one directory | **two** |
| filesystem, installs, home dirs | gone | intact |

Every one of those said *rotation*. **Check identity before accepting a key;
never accept a key because the box answered.**

## The generalisable half

The instinct after a benign rotation is to conclude the pin was noise and drop
it. That is the wrong lesson, and so is keeping it unchanged:

> **A pin whose value legitimately rotates does not stop being worth pinning. It
> stops meaning *"this must never change"* and starts meaning *"if this changed,
> establish WHY before you type yes."*** The pin's product was never
> immutability — it was **forcing a conscious decision at exactly the moment
> `StrictHostKeyChecking` would otherwise be waved through.** It delivered that
> here, correctly, on a change that turned out to be harmless.

## The practice

- **Record the rotation CONDITION next to the pin** — "regenerates on a panel
  restart via cloud-init" — so the next reader spends one command establishing
  which case they are in, not an hour deciding whether they are being attacked.
- **Keep the superseded values, dated.** A fingerprint that simply changes with
  no record is indistinguishable from one that was tampered with. The history is
  what makes the next change legible.
- **Name the identity checks in the same place**, or the reader has the alarm
  and not the discriminator.
- ⚠️ **And do not soften the pin to avoid the false alarm.** The false alarm cost
  one message and one paragraph. The failure it guards against is accepting a
  substituted host key on a machine holding CI credentials, and those two costs
  are not comparable — the sibling of *err toward the edge, the edge has a fence*
  ([canon 14](14-err-toward-the-edge-the-edge-has-a-fence.md)).
