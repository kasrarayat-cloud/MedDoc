// New content for the /structures concepts. The SOAP/headline/trust/sub constants are
// imported by each concept directly from ../motion/shared (single source of truth); this
// module only adds the structure-specific data: a fully SYNTHETIC, no-PHI doctor↔patient
// transcript (S1 + S4) and the four chapters (S3). The transcript is fictional and maps
// line-for-line onto the shared SOAP sample so the "note from what was said" claim holds.

export type Utterance = { who: 'dr' | 'pt'; text: string; soap?: 'S' | 'O' | 'A' | 'P' };

export const TRANSCRIPT: Utterance[] = [
  { who: 'dr', text: 'Good to see you again. How have things been since we adjusted the lisinopril?' },
  { who: 'pt', text: "Alright, I think. I've been checking at home like you asked — it's been about 150 over 90 most mornings.", soap: 'S' },
  { who: 'dr', text: "Let's take a look today. 148 over 92, heart rate 78. And your lungs are clear.", soap: 'O' },
  { who: 'dr', text: "So the pressure is still higher than I'd like — the hypertension isn't controlled yet.", soap: 'A' },
  { who: 'dr', text: "I'd like to add amlodipine, 5 milligrams, and recheck in four weeks.", soap: 'P' },
];

// The single transcript line that scrolls under S1's waveform.
export const LIVE_LINE = "…it's been about 150 over 90 most mornings…";

export type Chapter = { n: string; title: string; body: string };

export const CHAPTERS: Chapter[] = [
  { n: 'Listen', title: 'It listens to the visit', body: 'Ambient capture, in the room. No typing, no dictation, no “say that again for the mic.”' },
  { n: 'Draft', title: 'It drafts the note', body: 'A structured SOAP note, written from what was actually said — while you’re still with the patient.' },
  { n: 'Verify', title: 'It verifies every line', body: 'Each line is anchored to the transcript. Anything it can’t ground is flagged to a review lane, not invented.' },
  { n: 'Sign', title: 'You sign', body: 'You read it, you change what you want, you sign. Always. The note is yours — QuillMD just wrote the first draft.' },
];
