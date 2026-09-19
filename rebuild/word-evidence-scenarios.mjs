/** Synthetic inputs for the supported Word review workflow. No provider or database access. */
import assert from 'node:assert/strict';

export function scenario(mapping, mode) {
  assert(['unsupported-missing', 'partial', 'long'].includes(mode));
  assert.equal(mapping.fields.length, 90);
  assert.equal(mapping.requirements.length, 14);
  const values = Object.fromEntries(mapping.fields.map(f => [f.key, '']));
  const variants = Object.fromEntries(mapping.requirements.map(r => [r.key,
    r.variants.some(v => v.id === 'not_documented') ? 'not_documented' :
      r.variants.some(v => v.id === 'trusted') ? 'trusted' : 'original']));
  if (mode === 'partial') {
    values.patient_name = 'SYNTHETIC PARTIALLY MISSING WORD REVIEW';
    values.sdt_1475334564 = mapping.fields.find(f => f.key === 'sdt_1475334564').options[0];
    variants.claim_9 = 'exam_choice';
  }
  if (mode === 'long') {
    for (const field of mapping.fields) {
      if (field.kind === 'choice') {
        values[field.key] = field.options.find(v => !['reflux positive.', 'Asymptomatic'].includes(v));
      } else if (field.kind === 'measurement') {
        const unit = field.locator.unit;
        assert(['mm', 'ms'].includes(unit));
        values[field.key] = (unit === 'mm' ? '3.2' : '400') + ' ' + unit;
      } else values[field.key] = 'SYNTHETIC ' + field.key;
      if (field.key.startsWith('location_')) {
        const side = Number(field.key.split('_')[1]) < 14 ? 'Right' : 'Left';
        values[field.key] = `SYNTHETIC ${side} mapped location ${field.key}: ` +
          `${side} calf anatomical location documented in this synthetic review. `.repeat(65) +
          `END-${field.key.toUpperCase()}`;
      }
    }
    values.patient_name = 'SYNTHETIC LONG MAPPED NAME: ' +
      'Documented synthetic name component '.repeat(400) + 'END-PATIENT-NAME';
    for (const row of mapping.requirements) variants[row.key] = row.default_variant;
    Object.assign(variants, {claim_9: 'exam_choice', claim_19: 'technique_only',
      claim_23: 'original', claim_27: 'original', claim_30: 'selected', claim_31: 'selected',
      claim_32: 'negative', claim_34: 'selected', claim_35: 'selected', claim_36: 'negative'});
  }
  const statements = {};
  for (const row of mapping.requirements) {
    const variant = row.variants.find(v => v.id === variants[row.key]);
    assert(variant, 'No approved statement variant for ' + row.key);
    assert(variant.required_control_keys.every(k => values[k]), 'Missing required control: ' + row.key);
    assert(variant.empty_control_keys.every(k => !values[k]), 'Variant requires empty controls: ' + row.key);
    if (row.kind !== 'assertion') continue;
    statements[row.key] = variant.text_template.replace(/\{([^{}]+)\}/g, (_, key) => {
      if (key.endsWith('_reflux_connector'))
        return values[key.startsWith('right') ? 'sdt_-213273323' : 'sdt_605543147'] === 'is absent.' ? ' ' : ' is ';
      if (key.endsWith('_treatment_connector'))
        return values[key.startsWith('right') ? 'sdt_1706206184' : 'sdt_-1268837810'].startsWith(',') ? '' : ' ';
      assert(key in values, 'Unknown statement token');
      return values[key] || 'Choose an item.';
    });
  }
  const fieldQuotes = Object.fromEntries(mapping.fields.map(f => [f.key,
    values[f.key] ? f.label + ': ' + values[f.key] : '']));
  const statementQuotes = Object.fromEntries(mapping.requirements.filter(r => r.kind === 'assertion')
    .map(r => [r.key, mode === 'unsupported-missing' ? '' : r.label + ': ' + statements[r.key].trim()]));
  const notes = mode === 'unsupported-missing' ? 'SYNTHETIC: the note documents nothing the mapping can support.' :
    ['SYNTHETIC DOCUMENT REVIEW ONLY.', ...Object.values(fieldQuotes).filter(Boolean),
      ...Object.values(statementQuotes)].join('\n');
  assert(notes.length <= 50000, 'Complete synthetic source exceeds the application limit');
  assert(Object.values(values).every(v => typeof v === 'string' && v.length <= 20000));
  return {mode, values, variants, statements, fieldQuotes, statementQuotes, notes,
    missing: Object.values(values).filter(v => !v).length,
    longestMappedAnswer: Math.max(...Object.values(values).map(v => v.length))};
}
