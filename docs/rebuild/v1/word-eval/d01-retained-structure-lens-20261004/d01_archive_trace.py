"""Source-only readback of retained D01; no criterion or source changes."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E

BASE = Path(__file__).parent
ARCHIVE = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/dev33-final-plan-prepared-20261004/dev-native-application-481b65adb8ff-1791113822219658957/D01')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
sha = lambda b: hashlib.sha256(b).hexdigest()
def parts(path):
    with ZipFile(path) as z:
        return {name: z.read(name) for name in z.namelist()}
def text(el):
    return ''.join(t.text or '' for t in el.iter(W + 't'))
def plain(value):
    return ''.join(value.split())
def run():
    old_path, new_path = ARCHIVE / 'original.docx', ARCHIVE / 'native-ordinary-export.docx'
    old, new = parts(old_path), parts(new_path)
    retained = json.loads((ARCHIVE / 'native-ordinary-export-before-assertions.json').read_text())
    fields, answers = retained['mapping'], retained['reviewed_answers']
    assert sha(old_path.read_bytes()) == retained['original_sha256']
    assert sha(new_path.read_bytes()) == retained['export_sha256']
    old_body = E.fromstring(old['word/document.xml']).find(W + 'body')
    new_body = E.fromstring(new['word/document.xml']).find(W + 'body')
    original_tables, output_tables = old_body.findall(W + 'tbl'), new_body.findall(W + 'tbl')
    original_rows = original_tables[0].findall(W + 'tr')
    output_rows = [row for table in output_tables for row in table.findall(W + 'tr')]
    assert len(original_tables) == 1 and len(original_rows) == 28
    assert len(output_tables) == 2 and [len(t.findall(W+'tr')) for t in output_tables] == [14, 14]
    assert len(output_rows) == 28
    checks = []
    for field in fields:
        loc = field['locator']
        if 'table' not in loc:
            continue
        assert loc['table'] == 0
        row, col = loc['row'], loc['column']
        before = original_rows[row].findall(W+'tc')[col]
        after = output_rows[row].findall(W+'tc')[col]
        expected = str(answers[field['key']]['text'])
        actual = text(after)
        if 'unit' in loc:
            expected = expected.removesuffix(' '+loc['unit'])
        matched = plain(expected) in plain(actual)
        if loc.get('marker'):
            matched = matched and loc['marker'] not in actual
        checks.append({'key':field['key'],'source_row':row,'source_column':col,
                       'output_table':row//14,'output_row':row%14,
                       'source_text_sha256':sha(text(before).encode()),
                       'actual_text_sha256':sha(actual.encode()),'complete_answer':matched})
    assert len(checks) == 58 and all(c['complete_answer'] for c in checks)
    unchanged_cells = []
    writable = {(c['source_row'],c['source_column']) for c in checks}
    for n,(a,b) in enumerate(zip(original_rows,output_rows)):
        for col,(x,y) in enumerate(zip(a.findall(W+'tc'),b.findall(W+'tc'))):
            if (n,col) not in writable:
                unchanged_cells.append({'row':n,'column':col,'visible_text_equal':text(x)==text(y)})
    assert len(unchanged_cells) == 26 and all(c['visible_text_equal'] for c in unchanged_cells)
    controls = []
    for field in fields:
        loc = field['locator']
        if 'sdt_id' not in loc:
            continue
        def lookup(body):
            return [s for s in body.iter(W+'sdt') if s.find(W+'sdtPr/'+W+'id') is not None
                    and s.find(W+'sdtPr/'+W+'id').get(W+'val') == loc['sdt_id']]
        a,b = lookup(old_body),lookup(new_body)
        assert len(a)==len(b)==1
        value = str(answers[field['key']]['text'])
        controls.append({'key':field['key'],'source_id':loc['sdt_id'],
                         'complete_answer':text(b[0].find(W+'sdtContent'))==value})
    assert all(c['complete_answer'] for c in controls)
    result={'source_commit':'481b65adb8ffa97053b694f0de3ba4dbaac72d0a',
            'original_sha256':sha(old_path.read_bytes()),'export_sha256':sha(new_path.read_bytes()),
            'archive':str(ARCHIVE),'original_table_rows':[28],'export_table_rows':[14,14],
            'source_row_14_reader_error':'workflow.py:167–168 selects first output table and row14, which does not exist.',
            'production_cause':['rebuild/documents/service.py:205–206','rebuild/documents/layout.py:127–132'],
            'mapped_cell_answers':checks,'unchanged_cells':unchanged_cells,'sdt_answers':controls,
            'zip_member_names_equal':set(old)==set(new),
            'changed_parts':[n for n in old.keys() & new.keys() if old[n]!=new[n]],
            'missing_parts':sorted(old.keys()-new.keys()),'added_parts':sorted(new.keys()-old.keys()),
            'criterion_status':'Fixed original single-table structure criterion remains failed. Complete mapped-cell readback does not change scoring or award automatic success.',
            'visual_or_native_word':'unverified','DB_render_provider_calls':0}
    (BASE/'d01-adjudication.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'mapped_cell_answers':len(checks),'unchanged_cells':len(unchanged_cells),
                      'controls':len(controls),'structure_criterion':'failed','wrong_answer_readbacks':0}))
if __name__ == '__main__': run()
