// ============================================================================
// R2 + R3 — THE OWNER'S UPLOADED TEMPLATE WAS NEVER USED, AND NOTHING SAID SO.
// ----------------------------------------------------------------------------
// Forensic, 2026-08-27/28. His GI consultation form is PROSE — headings,
// paragraphs, underscore rules. The Template Twin compiler looks for Word
// content controls, found zero, and quarantined the upload at 20:53:57Z with
// NO_FILLABLE_FIELDS. He signed a note against that template at 21:06:31Z —
// 12 minutes 34 seconds later — having been shown nothing.
//
// His FILE was never altered (sha256 intact at rest). What went wrong is that
// his DOCUMENT was never used, and three separate mechanisms then made the
// generated substitute look like his form had been edited:
//
//   R3(a) visit-export.ts   every "[not documented]" became "—" on EVERY line,
//                           though the contract said TABLE CELLS. Whole prose
//                           sections collapsed to a bare em-dash. His original
//                           contains ZERO em-dashes; so does the stored note.
//   R3(b) header-fields.ts  a curated allowlist built for an OPERATIVE note
//                           ("surgeon", "date_of_surgery") silently dropped
//                           "Referring MD" and "Age" from his GI header.
//                           3 fields in, 1 survived.
//   R3(c) build-soap-prompt his defaultText scaffold went into the model prompt
//                           as writable prose and came back in the note, reading
//                           as text the AI wrote about his patient.
//
// This gate pins all four repairs. It is STATIC by necessity — the behaviour
// needs a database, a model and a browser — and the WALK is what exercises it.
// Saying which is which is the point.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  SCAFFOLD_CONFIRM_MARKER,
  SCAFFOLD_REFERENCE_OPEN,
  stripScaffoldMarkers,
} from '@/worker/note-templates/build-soap-prompt';
import { canonicalHeaderKey, genericHeaderKey } from '@/lib/note-template-parse/header-fields';
import { sanitizeExportedSoap } from '@/lib/visit-export';

const REPO = join(__dirname, '../../../../..');
const R = (p: string) => readFileSync(join(REPO, p), 'utf8');

describe('R3(a) · the em-dash rewrite honours its own contract', () => {
  it('a PROSE section that is undocumented never collapses to a bare em-dash', () => {
    const out = sanitizeExportedSoap('## Past Surgical History\n[not documented]\n');
    // the owner's symptom, stated as an assertion
    expect(out).not.toMatch(/^\s*—\s*$/m);
    expect(out).toContain('Not documented.');
  });

  it('a TABLE cell still becomes an em-dash — the documented behaviour is kept', () => {
    const out = sanitizeExportedSoap(
      '## Measurements\n| Vessel | Result |\n| --- | --- |\n| GSV | [not documented] |\n',
    );
    expect(out).toContain('—');
    expect(out).toContain('| GSV |');
  });

  it('non-vacuity: prose content is passed through untouched', () => {
    const body = '## Impression\nStable, no new findings.\n';
    expect(sanitizeExportedSoap(body)).toContain('Stable, no new findings.');
  });
});

describe('R3(b) · an unrecognised header label is captured, never dropped', () => {
  it("the owner's three GI header fields all survive", () => {
    // measured from his uploaded .docx: "Referring MD", "Patient", "Age"
    const keys = ['Referring MD', 'Patient', 'Age'].map(
      (l) => canonicalHeaderKey(l) ?? genericHeaderKey(l),
    );
    expect(keys.every(Boolean)).toBe(true);
    expect(new Set(keys).size, 'each label must get its own key').toBe(3);
    // the one the operative-note allowlist already knew
    expect(canonicalHeaderKey('Patient')).toBe('patient_name');
    // ⚠️ and the two it silently deleted now have keys
    expect(canonicalHeaderKey('Referring MD')).toBeNull();
    expect(genericHeaderKey('Referring MD')).toBe('custom_referring_md');
    expect(genericHeaderKey('Age')).toBe('custom_age');
  });

  it('the drop site no longer discards on a null canonical key', () => {
    const src = R('apps/transcribe-md/src/lib/note-template-parse/header-fields.ts');
    expect(src).toContain('?? genericHeaderKey(rawLabel)');
    expect(src, 'the old silent drop must be gone').not.toContain('if (!key || seenKeys.has(key)) continue;');
    // ⚠️ but the PHI guard is the one drop that MUST remain
    expect(src).toContain('detectStructuredPhi(rawLabel).length > 0');
  });
});

describe('R3(c) · prompt scaffolding never becomes a record', () => {
  it('the marker is no longer appended to the prompt', () => {
    const src = R('apps/transcribe-md/src/worker/note-templates/build-soap-prompt.ts');
    expect(src).not.toContain('${s.defaultText}\\n${SCAFFOLD_CONFIRM_MARKER}');
    expect(src).toContain('SCAFFOLD_REFERENCE_OPEN');
  });

  it('stripScaffoldMarkers removes the marker and the fence, and nothing else', () => {
    const note = [
      '## History of Present Illness',
      SCAFFOLD_REFERENCE_OPEN,
      'The patient is a pleasant 61-year-old.',
      SCAFFOLD_CONFIRM_MARKER,
      '## Plan',
      'Repeat in 5 years.',
    ].join('\n');
    const out = stripScaffoldMarkers(note);
    expect(out).not.toContain(SCAFFOLD_CONFIRM_MARKER);
    expect(out).not.toContain(SCAFFOLD_REFERENCE_OPEN);
    // the doctor's content is untouched
    expect(out).toContain('The patient is a pleasant 61-year-old.');
    expect(out).toContain('Repeat in 5 years.');
    expect(out).toContain('## Plan');
  });

  it('it is idempotent and safe on empty input', () => {
    expect(stripScaffoldMarkers('')).toBe('');
    const once = stripScaffoldMarkers(`a\n${SCAFFOLD_CONFIRM_MARKER}\nb`);
    expect(stripScaffoldMarkers(once)).toBe(once);
  });

  it('L4 applies it at the storage boundary', () => {
    const src = R('apps/transcribe-md/src/worker/layers/04-generate-soap.ts');
    expect(src).toContain('stripScaffoldMarkers(verified.fullBody)');
  });
});

describe('R2 · silence is illegal', () => {
  it('the save action RETURNS the twin outcome, not just a console.warn', () => {
    const src = R('apps/transcribe-md/src/actions/note-template-lifecycle.ts');
    expect(src).toContain('twinNotice');
    expect(src).toContain('twinFailureCode');
    // ⚠️ the CONSEQUENCE, not just the reason — a code is not a sentence
    expect(src).toContain('standard layout rather');
    expect(src).toContain('NO_FILLABLE_FIELDS');
  });

  it('the upload UI surfaces it', () => {
    const src = R('apps/transcribe-md/src/app/settings/note-format/note-format-manager.tsx');
    expect(src).toContain('saved.twinNotice');
  });

  it('a visit bound to an uncertified template carries a banner', () => {
    const src = R('apps/transcribe-md/src/app/visits/[id]/page.tsx');
    expect(src).toContain('visit-uncertified-template-banner');
    expect(src).toContain('templateUncertified');
    // ⚠️ only when a template IS bound — an untemplated visit is a different
    // situation and must not be told a promise was broken
    expect(src).toContain('!!visit.noteTemplate &&');
  });

  it('positive control: these matchers can fail', () => {
    const src = R('apps/transcribe-md/src/actions/note-template-lifecycle.ts');
    expect(src).not.toContain('aStringThatIsNotInThisFile');
  });
});
