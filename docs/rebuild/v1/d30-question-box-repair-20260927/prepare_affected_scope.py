"""Passive XML/metadata prefilter only. No candidate import, detector or export execution."""
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile
from lxml import etree

CORPUS = Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
HERE = Path(__file__).parent
LEDGER = CORPUS / 'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json'
records = json.loads(LEDGER.read_text())['records']
eligible = [r for r in records if r['offline_filled_copy_replay_supported'] is True]
assert len(eligible) == 33
held = {'D06', 'D19', 'D20', 'D23', 'D24', 'D25', 'D32'}
assert not held.intersection(r['development_id'] for r in eligible)
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
placeholder = re.compile(r'^(?:click (?:or tap )?here to enter (?:text|a date)\.?|choose an item\.?|click or tap to enter a date\.?|'
                         r'enter (?:text|date)(?: here)?\.?|type here\.?|data to be filled in by site\.?|mm/dd/yyyy|dd/mm/yyyy|'
                         r'dd|mm|yy|yyyy|hh|dd/mm/yy|mm/dd/yy)$', re.I)

def through(element, name):
    found = []
    for child in element:
        if child.tag == W + name:
            found.append(child)
        elif child.tag == W + 'sdt':
            content = child.find(W + 'sdtContent')
            if content is not None:
                found.extend(through(content, name))
        elif child.tag == W + 'customXml':
            found.extend(through(child, name))
    return found

results = []
for record in eligible:
    path = CORPUS / record['corpus_file']
    assert path.suffix == '.docx' and sha(path) == record['sha256']
    with ZipFile(path) as archive:
        assert sum(x.file_size for x in archive.infolist()) <= 80 * 1024 * 1024
        body = etree.fromstring(archive.read('word/document.xml'), parser).find(W + 'body')
    shapes = []
    # The candidate only enters root body tables. Keep every one-cell shape,
    # even if its text/control/old claim would later make the rule skip it.
    # This is an intentional upper bound; it cannot be a success measure.
    for n, table in enumerate(child for child in body if child.tag == W + 'tbl'):
        rows = through(table, 'tr')
        if len(rows) != 1:
            continue
        cells = through(rows[0], 'tc')
        if len(cells) != 1:
            continue
        cell = cells[0]
        text = ''.join(t.text or '' for t in cell.iter(W + 't'))
        objects = sorted({etree.QName(x).localname for x in cell.iter()
                          if x.tag in {W + k for k in ('tbl', 'sdt', 'fldChar', 'drawing', 'pict', 'object')}})
        plain = text.strip()
        blank_like = not plain or set(plain) <= set('_ \t.   ') or bool(placeholder.fullmatch(plain))
        shapes.append({'table': n, 'slot': f'word/document.xml#b/tbl[{n}]/tr[0]/tc[0]',
                       'plain_text_empty': not text.strip(), 'object_tags': objects,
                       'blank_like_without_objects': blank_like and not objects,
                       'plain_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'xml_sha256': hashlib.sha256(etree.tostring(table)).hexdigest()})
    results.append({'development_id': record['development_id'], 'path': str(path),
                    'original_sha256': record['sha256'], 'hash_unchanged': sha(path) == record['sha256'],
                    'one_row_one_cell_shapes': shapes, 'possible_rule_entry': bool(shapes),
                    'eligible_blank_box_present': any(s['blank_like_without_objects'] for s in shapes),
                    'expected_map': record['prior_expected_map_path'],
                    'prior_detection': str(CORPUS / 'results/dev-79a5b2ec6597-frozen/detect' / (path.stem + '.json'))})
report = {'scope': 'Passive XML shape upper bound only; no detector/export/provider execution.',
          'rights_ledger_sha256': sha(LEDGER), 'eligible_originals_examined': 33,
          'held_files_not_opened': sorted(held),
          'candidate_commit': '75e545b2a6469b0d188c779f3c4ee9af02dfc7f5',
          'candidate_engine_sha256': '326a4baf7d3331add09f36f78e05d66a8fb75acd4e10bd1c2c952447835efbd1',
          'base_commit': '0b0395a0922f81f5a38526802136197a4bb74b28',
          'records': results}
(HERE / '24-passive-affected-scope-classified.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'eligible': 33, 'potentially_affected': [
    {'id': r['development_id'], 'one_cell_tables': len(r['one_row_one_cell_shapes']),
     'empty_without_objects': sum(x['plain_text_empty'] and not x['object_tags'] for x in r['one_row_one_cell_shapes'])}
    for r in results if r['possible_rule_entry']], 'eligible_blank_box_documents': [
        r['development_id'] for r in results if r['eligible_blank_box_present']]}, indent=2))
