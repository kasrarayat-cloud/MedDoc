// ============================================================================
// The drafted medication list — READ-ONLY, and read-only is the whole design.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS AT ALL, given that owner ruling #109 deleted the Rx
// surface: because that surface had TWO jobs and the ruling named ONE.
//
// The deleted component's own heading toggled between them —
//
//     {props.rxHasWarnings ? 'Prescription safety' : 'Prescriptions'}
//
// — and it rendered whenever there were prescriptions OR warnings. #109 deletes
// the SAFETY surface and the sign gate. It does not delete the doctor's sight
// of their own prescriptions, and deleting the whole component took that with
// it.
//
// ⚠️ THE DEFECT THAT MADE THIS NON-OPTIONAL, MEASURED ON PRODUCTION. The export
// path was untouched: `rxSection()` still emits a MEDICATIONS block into five
// EHR clipboard formats, the PDF and the DOCX. So for one commit, a doctor
// signed and the signed record carried drug, dose, quantity and refills that
// had appeared on NO SCREEN at any point before the signature. 17 of 40
// production visits carry drafted prescriptions; 13 of those are already
// signed. Unseen content entering a signed medical record is the never-ship
// class, and it is why the ruling restored this rather than accepting it.
//
// WHAT THIS DELIBERATELY IS NOT:
//   · no warnings, no severity, no advisory chrome — that is the deleted
//     surface and it stays deleted;
//   · no override control, and nothing that gates signing;
//   · no ADD RX, no edit, no remove.
//
// ⚠️ NAMED OPEN ITEM, RECORDED RATHER THAN DISCOVERED LATER: after R5 a
// drafted prescription has NO edit or remove surface anywhere in the product.
// That is deliberate for now and it re-opens on first doctor contact. A doctor
// who wants a drafted medication changed must edit the note text; the card
// below will not follow them, because it reads `rxDrafts` and the note is
// `soapFinal`. Do not treat that divergence as a bug to fix quietly — it is
// the open item.
// ============================================================================

interface Prescription {
  drug: string;
  strength?: string | null;
  form?: string | null;
  sig?: string | null;
  quantity?: string | null;
  refills?: string | null;
}

interface RxBlob {
  prescriptions?: Prescription[];
}

/** Does this visit have any drafted medication to show? Prescriptions ONLY —
 *  warnings deliberately do not open this card (ruling #109).
 *
 *  ⚠️ `Array.isArray` FIRST, AND IT IS NOT PEDANTRY. The obvious form,
 *  `(blob?.prescriptions?.length ?? 0) > 0`, reads `.length` off whatever is
 *  there — so a malformed `prescriptions: 'nonsense'` returns **true** (8),
 *  while `rxSection()` returns [] and the export prints nothing. That is the
 *  display and the export disagreeing about the same payload, which is the
 *  exact divergence this whole restore exists to close. Caught by
 *  `gate-exported-medications-are-seen.test.ts` on its first run, against my
 *  own first draft of this function. */
export function hasDraftedPrescriptions(rx: unknown): boolean {
  return draftedPrescriptions(rx).length > 0;
}

export function draftedPrescriptions(rx: unknown): Prescription[] {
  const blob = (rx as RxBlob | null) ?? null;
  const list = blob?.prescriptions;
  // Model output persisted as jsonb. A malformed payload must render nothing
  // rather than throw and take the whole review surface down with it.
  return Array.isArray(list) ? list.filter((p) => p && typeof p.drug === 'string') : [];
}

export function PrescriptionsCard({ rx }: { rx: unknown }) {
  const list = draftedPrescriptions(rx);
  if (list.length === 0) return null;

  return (
    <section className="qm-rdoc-gate qm-rdoc-gate-quiet" data-testid="review-doc-prescriptions">
      {/* NO ALARM GLYPH AND NO AMBER. A routine refill must not look like an
          interaction — that was the exact complaint the deleted surface had
          already been fixed for once, and re-introducing the alarm here would
          re-introduce it under a new name. */}
      <div className="qm-rdoc-gate-head">
        <span>Prescriptions</span>
      </div>
      <div className="qm-rdoc-gate-body">
        <ul className="qm-rx-list" data-testid="review-doc-prescriptions-list">
          {list.map((rxItem, i) => (
            <li key={`${rxItem.drug}-${i}`} className="qm-rx-item">
              <div className="qm-rx-name">
                {rxItem.drug}
                {rxItem.strength ? ` ${rxItem.strength}` : ''}
                {rxItem.form ? ` ${rxItem.form}` : ''}
              </div>
              {rxItem.sig ? <div className="qm-rx-sig">{rxItem.sig}</div> : null}
              <div className="qm-rx-meta">
                {/* An em-dash for absent, never a fabricated 0. "Refills: 0" and
                    "the model did not say" are different clinical claims. */}
                <span>Qty {rxItem.quantity ?? '—'}</span>
                <span>Refills {rxItem.refills ?? '—'}</span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
