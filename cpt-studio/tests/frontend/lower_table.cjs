'use strict';
// Release 2 (RELEASE-2-SPEC R2-20; lane S, refutation round 1): every code point JavaScript's toLowerCase changes - the
// page's half of the search's lower-casing, which tests/test_lists.py compares with PostgreSQL's pg_c_utf8 over every
// code point. Writes {"unicode": node's Unicode version, "icu": its ICU version, "lowered": {code point: [the code
// points it lower-cases to]}} to stdout. Reads nothing; nothing is written anywhere.
const lowered = {};
for (let point = 1; point <= 0x10ffff; point += 1) {
  if (point >= 0xd800 && point <= 0xdfff) continue; // a lone surrogate is no letter
  const letter = String.fromCodePoint(point);
  const lower = letter.toLowerCase();
  if (lower !== letter) lowered[point] = Array.from(lower, piece => piece.codePointAt(0));
}
process.stdout.write(JSON.stringify({ unicode: process.versions.unicode, icu: process.versions.icu, lowered }));
