'use strict';
// Release 2 (RELEASE-2-SPEC R2-20; lane S): the page's own row text and search rule, run by the shipped app.js over list
// rows as GET /api/encounters serves them - what tests/test_lists.py holds the server's search to. It reads
// {"rows": [list_row, ...], "queries": [text, ...]} on stdin and writes {"texts": [...], "found": [[id, ...], ...]}:
// each row's text as documentRow draws it (the row's textContent: its markup taken away, its characters decoded), and
// for each query the ids of the rows release 1's applySearch keeps shown (the text, lower-cased, includes the query,
// lower-cased and trimmed). Synthetic rows only; nothing is written anywhere.
const fs = require('fs');
const path = require('path');

const app = require(path.join(__dirname, '..', '..', 'studio', 'static', 'studio', 'app.js'));

// app.js escapeHtml's table, read back: one pass, so an escaped '&lt;' stays the four characters it was
const DECODED = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#x60;': '`' };

function rowText(row) {
  const markup = app.documentRow(row);
  return markup.replace(/<[^>]*>/g, '').replace(/&(?:amp|lt|gt|quot|#x27|#x60);/g, entity => DECODED[entity]);
}

const { rows, queries } = JSON.parse(fs.readFileSync(0, 'utf8'));
const texts = rows.map(rowText);
const lowered = texts.map(text => text.toLowerCase());
const found = queries.map(query => {
  const wanted = String(query).toLowerCase().trim();
  return rows.filter((row, index) => !wanted || lowered[index].includes(wanted)).map(row => row.id);
});
process.stdout.write(JSON.stringify({ texts, found }));
