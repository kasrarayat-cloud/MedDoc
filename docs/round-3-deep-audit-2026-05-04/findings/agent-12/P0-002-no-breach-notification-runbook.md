---
id: A12-P0-002
title: No incident-response or breach-notification runbook exists; HIPAA §164.404 + §164.410 unactionable
severity: P0
domain: docs/incident-response
---

# Issue

QuillMD is about to handle PHI in a 5-doctor pilot. HIPAA imposes legally binding breach-notification deadlines (§164.404 to affected individuals — within 60 days; §164.410 from BA to CE — without unreasonable delay; §164.408 to HHS). The repository has **no incident-response runbook, no breach-notification procedure, no severity ladder, no communication template, and no forensics steps**. If a breach is discovered at 02:00 on a Sunday, the on-call (Kasra, solo) has no checklist to follow and no template to send. The 60-day clock starts on discovery — without a runbook, the first 24-72 hours are improvised and the legal record reflects that.

# Evidence

Repository search:

```
$ find /opt/meddoc-pro -type f -iname "*incident*" -not -path "*/node_modules/*"
(no results)
$ find /opt/meddoc-pro/docs -iname "*breach*"
(no results)
$ ls /opt/meddoc-pro/docs/incidents/  →  no such directory
```

The only references to incident response are aspirational fragments scattered across other documents:

- `docs/ROTATION_RUNBOOK.md:189` says "File in `docs/incidents/`" — the directory is never created.
- `docs/ROTATION_RUNBOOK.md:206` says "Date + operator + rotated-keys list logged in `docs/incidents/rotations.md`" — the file is never created.
- `apps/marketing/src/app/hipaa/page.tsx:172-179` (public HIPAA page) commits to a 60-day notification: "If we become aware of a breach of unsecured PHI, we will notify affected customers within 60 days as required by 45 CFR § 164.410, with a written description of what was disclosed and what mitigations are in place." There is no internal procedure to honour that public commitment.
- `KASRA_HANDOFF.md` §E ("Emergency rollback") covers technical rollback only — not breach assessment, not notification, not regulator filing.
- `docs/HIPAA_COMPLIANCE.md` lists §164.404 / §164.410 / §164.408 nowhere. The "§-controls reviewed" matrix in `LAUNCH_READINESS.md:64-79` covers §164.308 / §164.312 / §164.316 only — the breach-notification subpart is unaddressed.

# Risk

- **Regulatory**: failure to notify within the §164.404 60-day window is itself a HIPAA violation independent of the underlying breach. OCR settlements have explicitly cited "untimely notification" as an aggravating factor (Aetna 2020, Premera 2018).
- **Decision-making under load**: at 02:00 with no runbook, the on-call decides ad hoc whether something is reportable, who to call first, whether to pull the plug or preserve evidence. Each of those decisions has both legal and forensic consequences.
- **State-law overlay**: 47 states + DC + PR + VI have their own breach-notification statutes with shorter windows (some 30 days), specific notice-content requirements, and AG-notification thresholds. Without a runbook the state-by-state matrix is invisible at decision time.
- **BAA flow-down**: when QuillMD is the BA for a doctor's practice, §164.410 obliges QuillMD to notify the CE without unreasonable delay. The CE then has 60 days. A delay at QuillMD compresses the CE's timeline.
- **Pilot launch gate**: pre-pilot is the right time to write this — before the first piece of real PHI lands in the system.

# Recommended fix

Create `docs/INCIDENT_RESPONSE_RUNBOOK.md` covering:

1. **Severity ladder** — SEV-1 (PHI exfiltration confirmed or strongly suspected), SEV-2 (system compromise without confirmed PHI exfil), SEV-3 (degraded service, PHI integrity at risk), SEV-4 (operational anomaly, no PHI risk). Each SEV has a notification timeline and a communication channel.

2. **First-30-minutes checklist** — verify, contain (suspend rotated-out keys + impacted users + bucket access), preserve (snapshot Postgres + MinIO + Redis + caddy logs + container logs + audit_logs table), document (start the incident log file, assign incident ID).

3. **Triage decision tree** — is it a breach under §164.402? Apply the 4-factor risk assessment: nature/extent of PHI, who used/disclosed it, whether PHI was actually acquired/viewed, mitigation. Document each factor's answer.

4. **Notification timeline gantt** — discovery → CE notification (BA flow-down, 60-day max from discovery) → CE-to-individual (60-day max from CE discovery) → HHS (60 days for <500 affected; "without unreasonable delay" for ≥500) → media (≥500 in same state). State-law overlay matrix (NY SHIELD, CA CMIA, MA 201 CMR 17, etc).

5. **Communication templates** —
   - CE-notification email (BA → CE) under §164.410: incident description, identification of affected individuals, types of PHI, mitigation, contact.
   - Individual-notification letter under §164.404: plain-language, mailed, with breach description and self-protection steps.
   - HHS web-form input draft.
   - Press release skeleton for ≥500-affected media notice.

6. **Forensics checklist** — `pg_dump`, MinIO `mc cp`, container logs `docker compose logs > evidence/`, host syslog, Caddy access log, audit_logs export with `EXPLAIN` for the suspect window. Each output goes to `audit-evidence/<incident-id>/` (separate from the existing audit-evidence dir; create the convention).

7. **On-call rotation** — even with a single engineer, document the rotation policy: business hours = Kasra direct, after-hours = Kasra phone (number filed with compliance vault, not in repo), backup = pre-arranged colleague or contractor. Document a third-party contact for the case where Kasra is unreachable for >4 hours.

8. **Post-incident review** — required within 30 days. Template covering root cause, gaps in detection, controls added, audit-trail update.

Cross-reference from `docs/ROTATION_RUNBOOK.md` §7 (which already gestures at "Notify any affected parties — if PHI may have been exposed (real keys on real data), HIPAA breach-notification rules apply. Loop in legal.") — replace the loop-in-legal handwave with a link to the new runbook.

Add a row to `docs/HIPAA_COMPLIANCE.md` for §164.404 / §164.410 / §164.408 and link the new runbook as the evidence column.
