// ============================================================================
// transcript-clarity — deterministic unclear-span marking (2026-06-11 L4
// inaudible-span hardening). Fixtures are the REAL measured garble from the
// PriMock57 probe: "sphenitol" @0.61 (a fake drug name Deepgram minted from
// inaudible audio that shipped in a note's plan), "fat pup" @0.38/0.51,
// "sedative" @0.48, stopword dips ("okay" @0.64) that must NOT be marked.
// ============================================================================

import { describe, expect, it } from 'vitest';
import type { DeepgramUtterance, DeepgramWord } from '@meddoc/ai';
import {
  markUnclearTranscript,
  countUnclearMarkers,
  UNCLEAR_MARKER,
  UNCLEAR_WORD_CONFIDENCE,
} from '../transcript-clarity';

function w(word: string, confidence: number, punctuated?: string): DeepgramWord {
  return { word, confidence, start: 0, end: 0, punctuated_word: punctuated ?? word };
}

function utt(words: DeepgramWord[], transcript?: string): DeepgramUtterance {
  return {
    start: 0, end: 1, confidence: 1, channel: 0,
    transcript: transcript ?? words.map((x) => x.word).join(' '),
    words, speaker: 0,
  };
}

describe('markUnclearTranscript — the measured garble cases', () => {
  it('marks the fake drug name ("sphenitol" @0.61 — the HIGH finding), keeping the sentence boundary', () => {
    const u = utt([
      w("it's", 0.94), w('called', 1.0), w('sphenitol', 0.61, 'sphenitol.'),
    ]);
    // NIT-3: the trailing period survives the marking — sentences don't merge.
    expect(markUnclearTranscript(u)).toBe(`it's called ${UNCLEAR_MARKER}.`);
  });

  it('collapses an adjacent low-confidence run into ONE marker ("fat pup")', () => {
    const u = utt([
      w('place', 0.97), w('called', 0.95), w('fat', 0.38), w('pup', 0.51, 'pup.'),
    ]);
    const out = markUnclearTranscript(u);
    expect(out).toBe(`place called ${UNCLEAR_MARKER}.`);
    expect(countUnclearMarkers(out)).toBe(1);
  });

  it('AUDIT WARN-1: a low-confidence dose NUMERAL is marked (digits = always content)', () => {
    const u = utt([w('take', 0.95), w('500', 0.32), w('milligrams', 0.9)]);
    expect(markUnclearTranscript(u)).toBe(`take ${UNCLEAR_MARKER} milligrams`);
  });

  it('AUDIT WARN-3: an open run ABSORBS a low-confidence stopword (no phantom negation)', () => {
    // A 0.31-confidence "no" between garble must NOT surface as confident text.
    const u = utt([
      w('garblea', 0.3), w('no', 0.31), w('garbleb', 0.3), w('allergies', 0.9),
    ]);
    const out = markUnclearTranscript(u);
    expect(out).toBe(`${UNCLEAR_MARKER} allergies`);
    expect(countUnclearMarkers(out)).toBe(1);
  });

  it('a CLEAR stopword still closes a run (absorption needs low confidence)', () => {
    const u = utt([
      w('garblea', 0.3), w('no', 0.98), w('allergies', 0.9),
    ]);
    expect(markUnclearTranscript(u)).toBe(`${UNCLEAR_MARKER} no allergies`);
  });

  it('does NOT mark stopword confidence dips ("okay" @0.64, "or" @0.53) — zero-marker fast path returns the raw transcript', () => {
    const u = utt([w('okay', 0.64, 'Okay,'), w('or', 0.53), w('maybe', 0.9)]);
    // NIT-2: nothing markable → byte-identical to u.transcript.
    expect(markUnclearTranscript(u)).toBe(u.transcript);
  });

  it('does NOT mark 1-2 letter tokens regardless of confidence', () => {
    const u = utt([w('a', 0.35), w('it', 0.41), w('fine', 0.9)]);
    expect(markUnclearTranscript(u)).toBe(u.transcript);
  });

  it('marks a low-confidence content word mid-sentence ("sedative" @0.48)', () => {
    const u = utt([
      w('middle', 0.9), w('ear', 0.88), w('sedative', 0.48),
    ]);
    expect(markUnclearTranscript(u)).toBe(`middle ear ${UNCLEAR_MARKER}`);
  });

  it('threshold boundary: exactly AT the threshold is NOT marked; below is', () => {
    const at = utt([w('penicillin', UNCLEAR_WORD_CONFIDENCE)]);
    expect(markUnclearTranscript(at)).toBe('penicillin');
    const below = utt([w('penicillin', UNCLEAR_WORD_CONFIDENCE - 0.001)]);
    expect(markUnclearTranscript(below)).toBe(UNCLEAR_MARKER);
  });
});

describe('markUnclearTranscript — degradation + edges', () => {
  it('no word-level data → raw transcript unchanged (dictation/legacy rows)', () => {
    const u = utt([], 'verbatim dictation text stays untouched');
    expect(markUnclearTranscript(u)).toBe('verbatim dictation text stays untouched');
  });

  it('words missing confidence are NOT marked (defensive)', () => {
    const broken = { word: 'amoxicillin', start: 0, end: 0 } as DeepgramWord;
    const u = utt([broken, w('daily', 0.9)]);
    expect(markUnclearTranscript(u)).toBe(u.transcript);
  });

  it('ALL words low-confidence → the whole line becomes one marker', () => {
    const u = utt([w('garbled', 0.2), w('noise', 0.3), w('here', 0.1)]);
    expect(markUnclearTranscript(u)).toBe(UNCLEAR_MARKER);
  });

  it('two separated low runs → two markers', () => {
    const u = utt([
      w('took', 0.9), w('mystery', 0.4), w('twice', 0.95), w('garble', 0.3),
    ]);
    const out = markUnclearTranscript(u);
    expect(out).toBe(`took ${UNCLEAR_MARKER} twice ${UNCLEAR_MARKER}`);
    expect(countUnclearMarkers(out)).toBe(2);
  });

  it('uses punctuated_word for clear words when a marker exists in the line', () => {
    const u = utt([
      w('yes', 0.99, 'Yes,'), w('doctor', 0.98, 'doctor.'), w('mumbled', 0.4),
    ]);
    expect(markUnclearTranscript(u)).toBe(`Yes, doctor. ${UNCLEAR_MARKER}`);
  });

  it('is deterministic (same input → same output)', () => {
    const u = utt([w('fat', 0.38), w('pup', 0.51), w('place', 0.9)]);
    expect(markUnclearTranscript(u)).toBe(markUnclearTranscript(u));
  });
});

describe('countUnclearMarkers', () => {
  it('counts occurrences', () => {
    expect(countUnclearMarkers('')).toBe(0);
    expect(countUnclearMarkers(`a ${UNCLEAR_MARKER} b ${UNCLEAR_MARKER}`)).toBe(2);
  });
});
