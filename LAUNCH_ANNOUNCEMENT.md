# Pilot launch — announcement drafts
*Three variants. Kasra picks which to post where.*

---

## Variant A — Twitter / X (≤280 chars)

> QuillMD is in pilot. HIPAA-compliant AI medical scribe — record the visit, the SOAP note writes itself, you sign it. Admin dashboard with full audit trail.
>
> Open to 5 doctors. Reply if you spend more than an hour a day on charting.

(279 chars)

---

## Variant B — LinkedIn (~180 words)

Doctors spend two hours on charting for every hour of patient care. That's what QuillMD is built to fix.

QuillMD records the visit (audio in the room or dictation after), transcribes it with medical-grade speech recognition, and generates a structured SOAP note the doctor reviews and signs. Diagnosis codes, prescriptions, referrals — all drafted from the conversation, all editable, all auditable.

The hard parts of "AI in medicine" are the parts you don't see: HIPAA §164.312 audit controls on every PHI access, threat detection on the export surface, encrypted-at-rest storage on the roadmap, single-session enforcement, no training on your data. The product passes its own internal audit before any patient touches it.

Today we're opening a 5-doctor pilot. Looking for clinicians who:
- Spend more than an hour a day on documentation,
- Want to evaluate honestly (find what's wrong, not just what's nice),
- Are comfortable with a 30-day commitment.

Reply or DM if that's you. Tehran-based, global-friendly.

— Kasra

---

## Variant C — Long-form internal note / blog (~520 words)

### Why

Every doctor I know runs the same loop. See the patient. Listen carefully. Then sit down for hours after clinic and write up what just happened. The good ones type fast. The conscientious ones type slow. Either way, the actual medical thinking happens in the room and the rest is bureaucratic transcription.

There are existing scribes — human ones (expensive, slow), and AI ones (mostly demos, mostly not HIPAA-compliant, mostly not honest about what they actually do with your data). QuillMD is what I wanted to exist when I started looking and couldn't find.

### What

QuillMD is a medical scribe that runs the visit pipeline end-to-end:

- **Record**: doctor opens the app, hits record. Audio goes to MinIO (private bucket, doctor's instance) immediately. No cloud-syncing it through three intermediaries.
- **Transcribe**: Deepgram Nova-3-Medical handles the speech-to-text. Multi-speaker diarization tags who said what.
- **Structure**: a six-layer Anthropic Claude pipeline turns the transcript into a real SOAP note — speaker roles, clinical entities, SOAP draft, self-critique pass, polish pass, then optional automation layers (ICD/CPT coding, Rx drafting, referrals, patient summary).
- **Sign**: doctor reviews, edits, signs. The signed note is what's authoritative; the AI's draft is just a starting point.
- **Export**: PDF, DOCX, clipboard, or email-to-self for paste-into-EHR.

Behind the scenes there's an admin dashboard at `admin.quillmd.com`: live audit feed, a six-detector security panel (failed-login bursts, cross-tenant probes, bulk PHI access, external-domain export attempts, privilege escalations, export volume spikes), a HIPAA-findings checklist that's actually clickable, per-doctor cost tracking to the cent, user-management with proper destructive-action confirmation gates.

### HIPAA + safety, the parts you don't see

- §164.312(b) audit controls: every state-mutating action writes an audit row with user/IP/timestamp/UTC. Soft-delete preserves rows for the 7-year retention window — no admin endpoint hard-deletes user, audit, or PHI.
- §164.312(a)(2)(iv) encryption at rest: documented for pilot launch (Hetzner data-center physical access), full disk encryption planned for the first 30 days post-pilot.
- Single-session enforcement, JWT TTL 8h on the clinical surfaces, force-logout chain that takes effect on the very next request.
- No training. No third-party data sharing. The audio + transcript belong to the practice.

### The pilot

5 doctors. 30-day commitment. Looking for clinicians who'll actually tell me what's broken — not what's polite. The right pilot doctor has clear pain ("I spent X hours on notes last week") and a willingness to use the product as their actual documentation tool, not a side-by-side comparison.

In return: free for the pilot window, white-glove setup, direct line to me. After the pilot we figure out pricing together.

### How feedback flows back

Pilot doctors get my number. There's no ticket queue. If something breaks at 11pm I want to hear about it at 11pm. The admin dashboard surfaces issues to me automatically (threat panel + audit feed), but the qualitative stuff — "the SOAP draft missed the ROS section" — needs a human.

If you're a doctor or you know one who fits, reach out. Tehran-based founder, available in your timezone.

— Kasra
