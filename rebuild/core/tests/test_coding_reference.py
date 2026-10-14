"""Pure reference tests; invented A/S/Q categories are synthetic, not coding advice.

The small official paths below were established from the FY2027 Index/Tabular
before this parser was authored. They are public classification excerpts, not
clinical records. Full-release replays are an additional import qualification.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.coding_terminology import parse_reference, search_index, validate_code, reference_digest
from core.management.commands.import_coding_reference import (
    MANIFEST_FORMAT, official_url, prepare_reference, read_pinned_file,
)


def synthetic_reference(*, instruction='', other='', chapter_instruction=''):
    index = '''<ICD10CM.index><version>2027</version><letter><title>A</title>
      <mainTerm><title>Alpha <nemod>(mild)</nemod></title><code>A00.0</code>
        <term><title>specified</title><code>A00.1</code></term></mainTerm>
      <mainTerm><title>Alias</title><see>Alpha, specified</see></mainTerm>
      <mainTerm><title>Missing alias</title><see>Unresolved target</see></mainTerm>
      <mainTerm><title>Advisory</title><code>A00.0</code><seeAlso>Alpha</seeAlso></mainTerm>
      <mainTerm><title>GERD</title><code>A00.0</code></mainTerm>
      <mainTerm><title>History</title><term><title>family</title><term><title>alpha</title>
        <code>A00.0</code></term></term><term><title>personal</title><term><title>alpha</title>
        <code>A00.1</code></term></term></mainTerm>
      </letter></ICD10CM.index>'''
    tabular = f'''<ICD10CM.tabular><version>2027</version><chapter><name>1</name>
      <desc>Synthetic chapter</desc>{chapter_instruction}<section id="A00-A09">
      <desc>Synthetic section</desc><diag><name>A00</name><desc>Synthetic category</desc>
      {instruction}<diag><name>A00.0</name><desc>Synthetic zero</desc></diag>
      <diag><name>A00.1</name><desc>Synthetic one</desc></diag></diag>{other}
      </section></chapter></ICD10CM.tabular>'''
    return parse_reference(index, tabular, {'A00.0': 'Synthetic zero', 'A00.1': 'Synthetic one'})


class CodingReferenceParsingTests(SimpleTestCase):
    def test_hierarchy_default_nonessential_modifier_and_stable_identity(self):
        first, second = synthetic_reference(), synthetic_reference()
        self.assertEqual(first, second)
        alpha = search_index(first, 'alpha')[0]
        self.assertEqual(alpha['code'], 'A00.0')
        self.assertEqual(alpha['nonessential_modifiers'], ['(mild)'])
        child = next(e for e in first['index'] if e['parent_id'] == alpha['id'])
        self.assertEqual(child['path'], ['Alpha (mild)', 'specified'])
        self.assertEqual(child['id'], alpha['children'][0])
        self.assertNotEqual(child['id'], alpha['id'])
        self.assertEqual(child['code'], 'A00.1')

    def test_exact_head_default_is_returned_with_qualified_children(self):
        rows = search_index(synthetic_reference(), 'Alpha')
        self.assertEqual(rows[0]['default_code'], 'A00.0')
        self.assertTrue(any(e['code'] == 'A00.1' and e['path'][-1] == 'specified' for e in rows))

    def test_family_qualifier_cannot_disappear_into_personal_history(self):
        rows = search_index(synthetic_reference(), 'family history alpha')
        self.assertEqual([r['code'] for r in rows], ['A00.0'])
        self.assertIn('family', rows[0]['path'])

    def test_search_uses_index_terms_not_code_or_dictionary_description(self):
        ref = synthetic_reference()
        self.assertEqual(search_index(ref, 'A00.0'), [])
        self.assertEqual(search_index(ref, 'Synthetic zero'), [])
        self.assertEqual(search_index(ref, 'GERD')[0]['code'], 'A00.0')

    def test_cross_reference_is_not_fabricated_alias_code(self):
        rows = search_index(synthetic_reference(), 'Alias')
        alias = next(e for e in rows if e['title'] == 'Alias')
        self.assertIsNone(alias['code'])
        self.assertTrue(alias['requires_review'])
        target = next(e for e in rows if e['id'] == alias['cross_references'][0]['resolved_ids'][0])
        self.assertEqual(target['code'], 'A00.1')
        unresolved = search_index(synthetic_reference(), 'Missing alias')[0]
        self.assertFalse(unresolved['cross_references'][0]['resolved'])
        self.assertTrue(unresolved['requires_review'])

    def test_advisory_see_also_does_not_erase_owned_default(self):
        alias = search_index(synthetic_reference(), 'Advisory')[0]
        self.assertEqual(alias['code'], 'A00.0')
        self.assertFalse(alias['requires_review'])
        self.assertEqual(alias['see_also'], ['Alpha'])

    def test_model_reference_and_dict_have_identical_results(self):
        ref = synthetic_reference()
        obj = SimpleNamespace(**ref)
        self.assertEqual(search_index(obj, 'Alpha'), search_index(ref, 'Alpha'))
        self.assertEqual(validate_code(obj, 'a000', []), validate_code(ref, 'A00.0', []))

    def test_return_values_cannot_mutate_reference_evidence(self):
        ref = synthetic_reference(instruction='<includes><note>Synthetic instruction</note></includes>')
        before = deepcopy(ref)
        rows = search_index(ref, 'Alpha'); rows[0]['path'].append('changed')
        rows[0]['children'].clear()
        check = validate_code(ref, 'A00.0', [])
        check['instructions'][0]['references'].append({'invented': True})
        self.assertEqual(ref, before)

    def test_parent_categories_are_not_reportable(self):
        result = validate_code(synthetic_reference(), 'A00')
        self.assertFalse(result['valid'])
        self.assertEqual(result['errors'], ['not_reportable_in_release'])

    def test_required_seventh_characters_expand_from_complete_code_file(self):
        index = '<ICD10CM.index><version>2027</version><letter><mainTerm><title>Synthetic injury</title><code>S00.0</code></mainTerm></letter></ICD10CM.index>'
        tab = '''<ICD10CM.tabular><version>2027</version><chapter><name>19</name>
          <section id="S00-S09"><diag><name>S00</name><desc>Synthetic injury</desc>
          <sevenChrNote><note>Seventh character required</note></sevenChrNote>
          <sevenChrDef><extension char="A">Synthetic initial encounter</extension>
          <extension char="D">Synthetic subsequent encounter</extension></sevenChrDef>
          <diag><name>S00.0</name><desc>Synthetic injury without expansion nodes</desc></diag>
          </diag></section></chapter></ICD10CM.tabular>'''
        ref = parse_reference(index, tab, {'S00.0XXA': 'Synthetic initial', 'S00.0XXD': 'Synthetic subsequent'})
        self.assertTrue(validate_code(ref, 'S00.0XXA', [])['valid'])
        self.assertEqual(validate_code(ref, 'S00.0XXA', [])['governing_node'], 'S00.0')
        self.assertFalse(validate_code(ref, 'S00.0', [])['valid'])
        self.assertFalse(validate_code(ref, 'S00.0XXS', [])['valid'])
        bad = parse_reference(index, tab, {'S00.0XXS': 'Synthetic invalid extension'})
        self.assertEqual(validate_code(bad, 'S00.0XXS', [])['errors'], ['seventh_character_definition_mismatch'])

    def test_inherited_instructions_keep_all_source_nodes_and_distinct_types(self):
        ref = synthetic_reference(
            instruction='<includes><note>Parent inclusion</note></includes><inclusionTerm><note>Parent term</note></inclusionTerm><excludes2><note>Separate condition (A00.1)</note></excludes2>',
            chapter_instruction='<notes><note>Unrecognized clinical chapter rule</note></notes>')
        result = validate_code(ref, 'A00.0', ['A00.0', 'A00.1'])
        self.assertTrue(result['valid'])
        self.assertTrue(result['requires_review'])
        self.assertEqual([n['kind'] for n in result['instructions']], ['notes', 'includes', 'inclusionTerm', 'excludes2'])
        self.assertEqual([n['source_id'] for n in result['instructions']], ['chapter:1', 'A00', 'A00', 'A00'])

    def test_excludes1_conflict_and_missing_context_require_review(self):
        ref = synthetic_reference(instruction='<excludes1><note>Synthetic exclusion (A00.1)</note></excludes1>')
        self.assertTrue(validate_code(ref, 'A00.0')['requires_review'])
        self.assertFalse(validate_code(ref, 'A00.0', [])['requires_review'])
        result = validate_code(ref, 'A00.0', ['A00.0', 'A00.1'])
        self.assertFalse(result['valid'])
        self.assertIn('excludes1_selected_code_conflict', result['errors'])

    def test_excludes1_category_range_and_prefix_references(self):
        for text in ['A00-A09', 'A00.-', 'A00.1-']:
            with self.subTest(text=text):
                ref = synthetic_reference(instruction=f'<excludes1><note>Synthetic exclusion ({text})</note></excludes1>')
                self.assertFalse(validate_code(ref, 'A00.0', ['A00.1'])['valid'])

    def test_etiology_additional_and_code_also_are_not_satisfied_by_code_presence(self):
        for kind in ['codeFirst', 'useAdditionalCode', 'codeAlso']:
            with self.subTest(kind=kind):
                ref = synthetic_reference(instruction=f'<{kind}><note>Synthetic conditional rule (A00.1)</note></{kind}>')
                self.assertTrue(validate_code(ref, 'A00.0', ['A00.1'])['requires_review'])

    def test_unknown_and_empty_instructions_are_not_silently_dropped(self):
        ref = synthetic_reference(instruction='<codeAlso><note/></codeAlso>')
        result = validate_code(ref, 'A00.0', [])
        self.assertTrue(result['requires_review'])
        self.assertTrue(result['instructions'][0]['empty_source_note'])
        with self.assertRaises(ValueError):
            synthetic_reference(instruction='<newRule><note>Do not ignore me</note></newRule>')

    def test_invalid_selected_codes_and_limits_refuse(self):
        ref = synthetic_reference()
        for selection in [['A00'], ['made up'], 'A00.0', [False]]:
            with self.subTest(selection=selection):
                self.assertFalse(validate_code(ref, 'A00.0', selection)['valid'])
        for limit in [True, 0, 101, 1.5]:
            with self.assertRaises(ValueError):
                search_index(ref, 'Alpha', limit=limit)

    def test_malformed_xml_entities_versions_and_unbound_dictionary_refuse(self):
        ix = '<ICD10CM.index><version>2027</version><letter><mainTerm><title>Alpha</title><code>A00.0</code></mainTerm></letter></ICD10CM.index>'
        tb = '<ICD10CM.tabular><version>2027</version><chapter><name>1</name><section id="A00-A09"><diag><name>A00</name><desc>Synthetic</desc></diag></section></chapter></ICD10CM.tabular>'
        for index, tab, codes in [
            ('<!DOCTYPE x [<!ENTITY e "x">]>' + ix, tb, {'A00.0':'Synthetic'}),
            (ix, tb.replace('2027', '2026'), {'A00.0':'Synthetic'}),
            (ix, tb, {'B00.0':'Unbound'}),
            (ix, tb, {'A00.0':'One', 'A000':'Two'}),
            (ix.replace('</ICD10CM.index>', '<newRule/></ICD10CM.index>'), tb, {'A00.0':'Synthetic'}),
            (ix.replace('<title>Alpha</title>', '<title>Alpha<newRule/></title>'), tb, {'A00.0':'Synthetic'}),
        ]:
            with self.subTest(index=index[:35], codes=codes), self.assertRaises(ValueError):
                parse_reference(index, tab, codes)


class OfficialExpectedPathTests(SimpleTestCase):
    # FY2027 CMS Index XML SHA248e4a13..., Tabular d778c97a..., codes3c0583a3...;
    # the public source links and full hashes are in docs/coding-reference-guide.md.
    # Deliberately minimal excerpts: these are NOT importable full releases.
    def test_family_personal_symptom_and_screening_paths_stay_distinct(self):
        index = '''<ICD10CM.index><version>2027</version><letter>
          <mainTerm><title>History</title><term><title>family<nemod>(of)</nemod></title>
            <term><title>colonic polyps</title><code>Z83.719</code>
              <term><title>adenomatous and serrated</title><code>Z83.710</code></term>
              <term><title>hyperplastic</title><code>Z83.711</code></term></term>
            <term><title>polyps<nemod>(colon)</nemod></title><code>Z83.719</code>
              <seeAlso>History, family, colonic polyps</seeAlso></term></term>
            <term><title>personal<nemod>(of)</nemod></title><term><title>neoplasm</title>
              <term><title>benign</title><term><title>colon polyp</title><code>Z86.0100</code></term></term></term></term>
          </mainTerm><mainTerm><title>Bloating</title><code>R14.0</code></mainTerm>
          <mainTerm><title>Heartburn</title><code>R12</code></mainTerm>
          <mainTerm><title>GERD<nemod>(gastroesophageal reflux disease)</nemod></title><code>K21.9</code>
            <seeAlso>Disease, gastroesophageal reflux</seeAlso></mainTerm>
          <mainTerm><title>Screening<nemod>(for)</nemod></title><term><title>colonoscopy</title><code>Z12.11</code></term></mainTerm>
          </letter></ICD10CM.index>'''
        codes = {'Z83.719':'Family history of colon polyps, unspecified',
                 'Z83.710':'Family history of adenomatous and serrated polyps',
                 'Z83.711':'Family history of hyperplastic colon polyps',
                 'Z86.0100':'Personal history of colon polyps, unspecified',
                 'R14.0':'Abdominal distension (gaseous)', 'R12':'Heartburn',
                 'K21.9':'Gastro-esophageal reflux disease without esophagitis',
                 'Z12.11':'Encounter for screening for malignant neoplasm of colon'}
        nodes = ''.join(f'<diag><name>{code}</name><desc>{desc}</desc></diag>' for code, desc in codes.items())
        # Synthetic wrapper; exact public Index paths and code descriptors above.
        tab = f'<ICD10CM.tabular><version>2027</version><chapter><name>1</name><section id="fixture">{nodes}</section></chapter></ICD10CM.tabular>'
        ref = parse_reference(index, tab, codes)
        expected = {'family history colon polyps':'Z83.719', 'family history colonic polyps':'Z83.719',
                    'family history colonic polyps hyperplastic':'Z83.711',
                    'personal history colon polyp':'Z86.0100', 'bloating':'R14.0',
                    'heartburn':'R12', 'GERD':'K21.9', 'screening colonoscopy':'Z12.11'}
        for term, code in expected.items():
            with self.subTest(term=term):
                self.assertEqual(search_index(ref, term)[0]['code'], code)
        self.assertFalse(validate_code(ref, 'Z83.71')['valid'])
        self.assertFalse(validate_code(ref, 'Z86.010')['valid'])

    def test_exact_general_symptom_guidance_is_visible_without_blanket_hold(self):
        note = ('This chapter includes symptoms, signs, abnormal results of clinical or other '
                'investigative procedures, and ill-defined conditions regarding which no '
                'diagnosis classifiable elsewhere is recorded.')
        for year in ['2026', '2027']:
            for changed in [False, True]:
                with self.subTest(year=year, changed=changed):
                    text = note + (' New unreviewed condition.' if changed else '')
                    ix = f'<ICD10CM.index><version>{year}</version><letter><mainTerm><title>Heartburn</title><code>R12</code></mainTerm></letter></ICD10CM.index>'
                    tab = f'''<ICD10CM.tabular><version>{year}</version><chapter><name>18</name>
                      <notes><note>{text}</note></notes><section id="R10-R19"><diag><name>R12</name>
                      <desc>Heartburn</desc><excludes1><note>functional dyspepsia (K30)</note></excludes1>
                      </diag></section></chapter></ICD10CM.tabular>'''
                    result = validate_code(parse_reference(ix, tab, {'R12':'Heartburn'}), 'R12', [])
                    self.assertTrue(result['valid'])
                    self.assertEqual(result['requires_review'], changed)
                    self.assertEqual(len(result['instructions']), 2)
                    self.assertEqual(len(result['unresolved_instructions']), int(changed))
                    self.assertEqual(len(result['review_instruction_ids']), int(changed))

    def test_family_follow_up_is_explicit_conditional_and_remains_for_source_evaluation(self):
        ix = '<ICD10CM.index><version>2027</version><letter><mainTerm><title>History</title><term><title>family</title><term><title>colonic polyps</title><code>Z83.719</code></term></term></mainTerm></letter></ICD10CM.index>'
        tab = '''<ICD10CM.tabular><version>2027</version><chapter><name>21</name>
          <section id="Z77-Z99"><codeAlso><note>any follow-up examination (Z08-Z09)</note></codeAlso>
          <diag><name>Z83.719</name><desc>Family history of colon polyps, unspecified</desc></diag>
          </section></chapter></ICD10CM.tabular>'''
        ref = parse_reference(ix, tab, {'Z83.719':'Family history of colon polyps, unspecified'})
        result = validate_code(ref, 'Z83.719', [])
        self.assertTrue(result['valid'])
        self.assertTrue(result['requires_review'])
        self.assertEqual(len(result['unresolved_instructions']), 1)
        instruction = result['unresolved_instructions'][0]
        self.assertEqual(instruction['rule'], 'post_treatment_follow_up')
        self.assertEqual(instruction['condition'], 'documented_post_treatment_follow_up')
        self.assertEqual(instruction['scope'], 'conditional')
        self.assertEqual(result['review_instruction_ids'], [instruction['id']])
        self.assertEqual(instruction['related_codes'], ['Z08', 'Z09'])
        # A forged scope annotation cannot erase an actual conditional rule.
        ref['tabular']['nodes']['section:Z77-Z99']['instructions'][0]['scope'] = 'general_guidance'
        self.assertTrue(validate_code(ref, 'Z83.719', [])['requires_review'])

    def test_personal_history_and_screening_conditions_are_preserved_not_auto_waived(self):
        index = '''<ICD10CM.index><version>2027</version><letter><mainTerm><title>History</title>
          <term><title>personal</title><term><title>colon polyp</title><code>Z86.0100</code></term></term>
          </mainTerm><mainTerm><title>Screening</title><term><title>colonoscopy</title><code>Z12.11</code></term>
          </mainTerm></letter></ICD10CM.index>'''
        tab = '''<ICD10CM.tabular><version>2027</version><chapter><name>21</name>
          <section id="Z00-Z13"><notes><note>Nonspecific abnormal findings disclosed at the time of these examinations are classified to categories R70-R94.</note></notes>
          <diag><name>Z12</name><desc>Encounter for screening for malignant neoplasms</desc>
          <useAdditionalCode><note>code to identify any family history of malignant neoplasm (Z80.-)</note></useAdditionalCode>
          <excludes1><note>encounter for diagnostic examination-code to sign or symptom</note></excludes1>
          <diag><name>Z12.11</name><desc>Encounter for screening for malignant neoplasm of colon</desc></diag></diag></section>
          <section id="Z77-Z99"><diag><name>Z86</name><desc>Personal history of certain other diseases</desc>
          <codeFirst><note>any follow-up examination after treatment (Z09)</note></codeFirst>
          <diag><name>Z86.0100</name><desc>Personal history of colon polyps, unspecified</desc></diag>
          </diag></section></chapter></ICD10CM.tabular>'''
        codes = {'Z12.11':'Encounter for screening for malignant neoplasm of colon',
                 'Z86.0100':'Personal history of colon polyps, unspecified'}
        for year in ['2026', '2027']:
            with self.subTest(year=year):
                ref = parse_reference(index.replace('2027', year), tab.replace('2027', year), codes)
                personal = validate_code(ref, 'Z86.0100', [])
                self.assertTrue(personal['requires_review'])
                self.assertEqual([n['rule'] for n in personal['unresolved_instructions']], ['post_treatment_follow_up'])
                self.assertEqual(personal['unresolved_instructions'][0]['kind'], 'codeFirst')
                screening = validate_code(ref, 'Z12.11', [])
                self.assertTrue(screening['requires_review'])
                self.assertEqual([n['rule'] for n in screening['unresolved_instructions']],
                                 ['family_history_malignancy', 'screening_versus_diagnostic_exam'])
                self.assertEqual(screening['instructions'][0]['scope'], 'general_guidance')
        changed = parse_reference(index, tab.replace('any follow-up examination after treatment (Z09)',
                                                    'any follow-up examination after treatment (Z09); new condition'), codes)
        note = validate_code(changed, 'Z86.0100', [])['unresolved_instructions'][0]
        self.assertIsNone(note['rule'])
        self.assertEqual(note['scope'], 'unresolved')
        future = parse_reference(index.replace('2027','2028'), tab.replace('2027','2028'), codes)
        self.assertTrue(all(n['scope'] == 'unresolved' or n['rule'] == 'excludes1_selected_code_conflict'
                            for n in validate_code(future, 'Z12.11', [])['unresolved_instructions']))


class CodingReferenceManifestTests(SimpleTestCase):
    def test_pinned_read_refuses_changed_bytes_symlinks_and_oversize(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'reference'; path.write_bytes(b'official bytes')
            pin = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(read_pinned_file(str(path), pin, 100), b'official bytes')
            link = Path(directory) / 'link'; link.symlink_to(path)
            for target, sha, maximum in [(str(link), pin, 100), (str(path), '0'*64, 100),
                                          (str(path), pin, 2), ('relative', pin, 100)]:
                with self.assertRaises(CommandError):
                    read_pinned_file(target, sha, maximum)

    def test_official_url_refuses_lookalike_credentials_and_non_https(self):
        official_url('https://www.cms.gov/files/zip/2027-code-tables-tabular-index.zip')
        for value in ['https://www.cms.gov.evil.example/file', 'http://ftp.cdc.gov/file',
                      'https://user@www.cms.gov/file', 'https://www.cms.gov/file?q=changed',
                      'https://www.cms.gov:8443/file', 'https://www.cms.gov/file#fragment']:
            with self.assertRaises(CommandError):
                official_url(value)

    def test_closed_manifest_and_duplicate_keys_refuse_before_payload_reads(self):
        for raw in [b'{}', b'{"format":"x","format":"x"}', b'{"format":NaN}']:
            with patch('core.management.commands.import_coding_reference.read_pinned_file', return_value=raw) as reader:
                with self.assertRaises(CommandError):
                    prepare_reference('/synthetic/manifest.json', '0'*64)
                self.assertEqual(reader.call_count, 1)

    def test_manifest_fiscal_interval_counts_and_complete_inputs_are_required(self):
        manifest = {'format':MANIFEST_FORMAT, 'release':{
            'id':'00000000-0000-4000-8000-000000000001','system':'ICD-10-CM','version':'FY2027',
            'effective_from':'2026-10-01','effective_until':'2027-09-30',
            'sha256':'1'*64,'source_url':'https://www.cms.gov/codes.zip'},
            'files':{},'expected_code_count':74879,'expected_index_entry_count':81642,
            'expected_tabular_diagnosis_count':47025}
        for field, value in [('expected_code_count',True), ('expected_index_entry_count',1),
                             ('expected_tabular_diagnosis_count',39999), ('files',{})]:
            changed = deepcopy(manifest); changed[field] = value
            with patch('core.management.commands.import_coding_reference.read_pinned_file', return_value=json.dumps(changed).encode()):
                with self.assertRaises(CommandError):
                    prepare_reference('/synthetic/manifest.json','0'*64)
        changed = deepcopy(manifest); changed['release']['effective_until'] = '2028-01-01'
        with patch('core.management.commands.import_coding_reference.read_pinned_file', return_value=json.dumps(changed).encode()):
            with self.assertRaises(CommandError):
                prepare_reference('/synthetic/manifest.json','0'*64)

    def test_reference_digest_binds_all_reference_and_provenance_values(self):
        ref = synthetic_reference(); value = {**ref, 'provenance': {'release':'synthetic'}}
        before = reference_digest(value)
        changed = deepcopy(value); changed['tabular']['codes']['A00.0'] = 'Changed description'
        self.assertNotEqual(reference_digest(changed), before)
        changed = deepcopy(value); changed['provenance']['release'] = 'different'
        self.assertNotEqual(reference_digest(changed), before)
