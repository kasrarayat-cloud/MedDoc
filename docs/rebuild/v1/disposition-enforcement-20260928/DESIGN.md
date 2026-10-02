# Empty-draft disposition: bounded execution design

Approved scope: an exactly empty, unreviewed and unfinalized encounter draft, created within an explicitly signed prospective policy cohort. No defaults supply a retention duration or legal rule. Patient, template/original, account, financial, audit, hold, signature, consent and finalized export evidence remain protected. Jobs, batches, coding suggestions, any matching historical hold, preserved history, prior review action or nonempty clinical/review state refuse this adapter.

An independent authority signs the closed policy envelope; an authenticated custodian admits it prospectively. A maker prepares an exact PostgreSQL row snapshot; a different authenticated custodian approves its digest. Execution locks that source row, takes the preservation lock, repeats eligibility and identity checks, persists and fsyncs a signed instruction into the independent journal, then writes a tombstone and deletes precisely that empty row in one DB transaction. New records remain append-only. A journal write followed by DB rollback suppresses the target through the same clinical reader and direct processing checks; the exact interrupted instruction can retry. The journal has an independently signed head checkpoint; hashes alone are not authorization.

On a quarantined restored target, replay verifies the independent chain and exact signed checkpoint before importing durable suppression. Conflicting restored content is preserved; replay never releases quarantine or deletes external copies. Local-only journal configuration is not proof of an independent backup system or its latest head. External journal custody/checkpoint issuance, external copy adapters, wider record classes, and broad restore admission remain unfinished integration/authority boundaries.

Must change: additive policy/instruction/approval/tombstone/completion records and DB guards; shared clinical access/processing barriers; explicit administration flow. Must not change: existing immutable financial/audit/hold history or guards, installed configuration/DB, default-off status, or any real record. Lock order is source row before preservation, with explicit concurrent hold/job witnesses. Only synthetic fixtures execute deletion in this work.

## UI research and reference lock (before implementation)

Refero skill applied. Live Refero tools are unavailable in this session. Read the bundled craft-details and copywriting references and three existing product screens: `disposition_review.html`, `restore_preparation.html`, and `retention_holds.html`, with their existing `app.css` components. Direct build uses this product design system, not a new visual language.

Designing a web administration flow for verified custodians. Goal: admit externally signed authority and act on one exactly identified empty draft after a second custodian's review. Main risk: confusing a proposal with execution or a restored target with admission. The memorable functional detail is the visible separation between the exact target/digest and the final destructive action.

Primary reference: disposition review. Preserve white canvas, current system typography, quiet bordered sections, monospace identities, native labelled forms, and bounded records with details. Borrow restore preparation's explicit unavailable/quarantined state and retention holds' exact-scope confirmation. Existing danger button color is reserved for actual deletion. No new CSS, illustrations, animation, dashboards or status statistics. Public signed envelopes may be pasted; private signing keys are never entered here.

| Decision | Reference / constraint | Role and rationale |
|---|---|---|
| Separate ordered admission, preparation, approval and execution sections | Existing disposition review and accepted authority design | Makes distinct human decisions inspectable; authenticated request user supplies identity. |
| Default unavailable with no mutation forms | Restore preparation + default-off requirement | An unset installation offers no actionable deletion control. |
| Exact target ID, digest, timestamp and reviewer visible | Retention holds + exact reviewed target requirement | Operators can compare identities without clinical content. |
| Explicit checkbox and danger-labelled deletion button | Craft guide destructive-action confirmation + existing danger token | Submission clearly acknowledges the specific effect. |
| Quarantine shows replay only | Accepted restore design | Clinical service admission remains unavailable after replay. |
| Native labels, paste, details, inline errors, existing submit-once behavior | Craft forms/focus guide | Keyboard and mobile use preserve current interaction conventions. |
| Bounded recent history and pagination | Existing disposition review | No unbounded record rendering or source snapshots in HTML. |

Render at desktop1280 and mobile390 after implementation. Check heading/action clarity, focus/labels and horizontal overflow against these references. Retain screenshots privately; no filled clinical artifacts enter Git.
