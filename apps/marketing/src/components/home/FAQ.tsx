/**
 * FAQ — Phase 7 v6 (Apple Product).
 *
 * Single hairline-bordered list panel. 7 plain Q + A blocks (not toggle-able)
 * to match the production source-of-truth content.
 */
type QA = { q: string; a: string };

const ITEMS: QA[] = [
  {
    q: 'Is QuillMD a covered entity or a business associate?',
    a: 'Business associate. We sign a BAA before any practice goes live, and our infrastructure is HIPAA-compliant end to end. Your practice remains the covered entity; we never act as one on your behalf.',
  },
  {
    q: 'Where does the audio go after the visit?',
    a: "Audio is stored encrypted in our US-east-1 MinIO cluster, retained per your practice's policy (default 30 days), and then permanently deleted. The transcript and SOAP note remain. You can purge audio earlier from any visit detail view.",
  },
  {
    q: 'Which EHRs do you export to?',
    a: 'Epic, Athena, Cerner, eCW, and a generic plain-text format. Most practices copy-paste; the formatter handles the section labels each EHR expects. Direct integrations are on the 2026 roadmap.',
  },
  {
    q: 'Can I edit the SOAP before signing?',
    a: 'Yes. Every section is editable until you tap "Sign". After that, the note is immutable and any further edits create an addendum with a timestamp and audit entry — the same pattern your malpractice carrier expects.',
  },
  {
    q: 'What if a recommendation is wrong?',
    a: 'Override it. Every ICD-10, CPT, and Rx warning has an explicit override path that captures your reason. We use that data — fully de-identified — to improve the model for your specialty over time.',
  },
  {
    q: 'How fast does a visit process?',
    a: 'Median 47 seconds for a 12-minute visit, including transcription, SOAP drafting, ICD-10 + CPT coding, and Rx safety checks. The pipeline is parallel; no single layer blocks the others.',
  },
  {
    q: 'Who is behind QuillMD?',
    a: "Solo founder, son of an internist who dictated until midnight for 30 years. Built this so the next generation doesn't have to.",
  },
];

export function FAQ() {
  return (
    <section className="stage" id="faq">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">07 / FAQ</span>
        </div>
        <h2 className="stage-h2 reveal delay-1">
          Short answers <span className="quiet">to the questions doctors ask first.</span>
        </h2>

        <div className="faq-list reveal delay-2">
          {ITEMS.map((item) => (
            <div key={item.q} className="faq-item">
              <h3 className="faq-q">{item.q}</h3>
              <p className="faq-a">{item.a}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
