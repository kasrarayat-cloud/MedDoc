"""Destination roles: whether a place may receive an answer at all, read from the ORIGINAL's existing structure.

Synthetic blank forms only, built in memory. Red-first ids (RF..) and positive controls (PC..) are the destination-
authority matrix's (v1-product-20260930 a1 mapping-matrix redfirst.json).
"""
import io
import unittest
import zipfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from . import word_v3 as w

SYN = 'SYNTHETIC-ANSWER'
BODY = 'word/document.xml#'


def data(doc):
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def xml(blob):
    return zipfile.ZipFile(io.BytesIO(blob)).read('word/document.xml').decode()


def box(doc, text=None, pict=False):
    table = doc.add_table(rows=1, cols=1)
    borders = OxmlElement('w:tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        edge = OxmlElement('w:' + side)
        edge.set(qn('w:val'), 'single')
        borders.append(edge)
    table.cell(0, 0)._tc.get_or_add_tcPr().append(borders)
    if text:
        table.cell(0, 0).paragraphs[0].add_run(text)
    if pict:
        table.cell(0, 0).paragraphs[0].add_run()._r.append(OxmlElement('w:pict'))
    return table


def grid(doc, rows):
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            if text:
                table.cell(i, j).paragraphs[0].add_run(text)
    return table


def line_form(text):
    doc = Document()
    doc.add_heading('Clinic record', level=2)
    doc.add_paragraph(text)
    doc.add_paragraph('Plan: ______')
    return data(doc)


def signing_box_form(fill=None):
    doc = Document()
    doc.add_heading('Consultant review', level=2)
    doc.add_paragraph('Signed by the consultant:')
    box(doc, text=fill if fill not in (None, 'pict') else None, pict=fill == 'pict')
    doc.add_paragraph('Plan: ______')
    return data(doc)


def refusal(blob, fields, key, value=SYN):
    try:
        w.fill(blob, fields, {key: value})
    except w.V3Failure as exc:
        return exc.code
    return None


def forged(blob, slot, kind='text', label='Forged'):
    """What a stored mapping from before this change could hold: the candidate's own locate result for `slot`, built
    by bypassing only the role check (the placement is exactly what the candidate located)."""
    roles = w.destination_roles_of
    try:
        w.destination_roles_of = lambda package: []
        return w.locate(blob, [{'slot': BODY + slot, 'kind': kind, 'label': label}])[0]
    finally:
        w.destination_roles_of = roles


class SpanAndSegment(unittest.TestCase):
    def test_pc01_pc02_an_ordinary_blank_beside_a_signature_on_one_line_stays_answerable(self):
        for text in ('Name: ______    Signature: ______', 'Date of visit: ______    Signature: ______'):
            with self.subTest(text=text):
                blob = line_form(text)
                fields = w.inspect(blob)['fields']
                first = fields[0]
                self.assertNotEqual(first['kind'], 'signature')
                self.assertEqual(w.destination_roles(blob, fields)['violations'], {})
                out = w.fill(blob, fields, {first['key']: '2026-09-30' if first['kind'] == 'date' else SYN})
                self.assertIn('2026-09-30' if first['kind'] == 'date' else SYN, xml(out))

    def test_rf06_a_signature_owns_its_line_segment_up_to_the_next_engine_area(self):
        """'Signature: ______ (use black ink)': an insertion after the printed guidance does not touch the signature's
        span (11-17) but is inside the segment the signature owns; the candidate wrote '... (use black ink) SYN'."""
        blob = line_form('Signature: ______ (use black ink)')
        roles = [r for r in w.destination_roles(blob)['roles'] if r['class'] == 'signing']
        self.assertEqual([(r['place'], r['start'], r['end']) for r in roles], [(BODY + 'b/p[1]', 0, 34)])
        with self.assertRaises(w.V3Failure) as refused:
            w.locate(blob, [{'slot': BODY + 'b/p[1]', 'kind': 'text', 'label': 'Signature'}])
        self.assertEqual(refused.exception.code, 'destination_role')
        stored = forged(blob, 'b/p[1]', label='Signature')
        self.assertEqual(stored['locator']['target'], {'type': 'span', 'start': 33, 'end': 33, 'shape': 'after_label'})
        fields = [f for f in w.inspect(blob)['fields'] if f['kind'] != 'signature'] + [stored]
        self.assertEqual(refusal(blob, fields, stored['key']), 'protected_signing_area')
        self.assertIn(stored['key'], w.destination_roles(blob, fields)['violations'])

    def test_the_segment_ends_where_the_next_engine_area_starts(self):
        blob = line_form('Signature: ______    Name: ______')
        fields = w.inspect(blob)['fields']
        name = next(f for f in fields if f['label'] == 'Name')
        role = next(r for r in w.destination_roles(blob, fields)['roles'] if r['class'] == 'signing')
        self.assertEqual((role['start'], role['end']), (0, name['locator']['target']['start']))
        self.assertIsNone(refusal(blob, fields, name['key']))


class RemoveThenAdd(unittest.TestCase):
    """RF01-RF05 (X02): remove the engine's signing field, then add text at the same place. Candidate: WROTE."""

    CASES = (('RF01', 'Signature: ______________', 'b/p[1]'),
             ('RF03', "Participant's signature: ______", 'b/p[1]'),
             ('RF04', 'Initials: ______', 'b/p[1]'))

    def test_rf01_rf03_rf04_lines(self):
        for rid, text, slot in self.CASES:
            with self.subTest(rid=rid):
                blob = line_form(text)
                engine = w.inspect(blob)['fields']
                self.assertIn(engine[0]['kind'], ('signature', 'initials'))
                with self.assertRaises(w.V3Failure) as refused:
                    w.locate(blob, [{'slot': BODY + slot, 'kind': 'text', 'label': text.split(':')[0]}])
                self.assertEqual(refused.exception.code, 'destination_role')
                # The same place as a Signature or Initials field is allowed: it is signed by hand, never filled.
                own = w.locate(blob, [{'slot': BODY + slot, 'kind': engine[0]['kind'], 'label': 'Signed here'}])[0]
                self.assertEqual(own['kind'], engine[0]['kind'])
                stored = forged(blob, slot)
                mapping = engine[1:] + [stored]
                self.assertEqual(refusal(blob, mapping, stored['key']), 'protected_signing_area')
                plan = next(f for f in engine if f['label'] == 'Plan')
                self.assertIsNone(refusal(blob, mapping, plan['key']))   # PC16: the rest of the form still fills

    def test_rf02_signature_column_cell(self):
        doc = Document(); doc.add_heading('Clinic record', level=2); grid(doc, [['Name', 'Signature'], ['', '']])
        blob = data(doc)
        engine = w.inspect(blob)['fields']
        self.assertEqual([f['kind'] for f in engine], ['text', 'signature'])
        with self.assertRaises(w.V3Failure):
            w.locate(blob, [{'slot': BODY + 'b/tbl[0]/tr[1]/tc[1]', 'kind': 'text', 'label': 'Signature'}])
        stored = forged(blob, 'b/tbl[0]/tr[1]/tc[1]')
        self.assertEqual(refusal(blob, [engine[0], stored], stored['key']), 'protected_signing_area')
        self.assertIsNone(refusal(blob, [engine[0], stored], engine[0]['key']))

    def test_rf05_declaration_signature_line(self):
        doc = Document(); doc.add_heading('Declaration', level=2)
        doc.add_paragraph('I confirm the above is correct.'); doc.add_paragraph('Signature of examining clinician: ______')
        blob = data(doc)
        with self.assertRaises(w.V3Failure):
            w.locate(blob, [{'slot': BODY + 'b/p[2]', 'kind': 'text', 'label': 'Signature of examining clinician'}])
        stored = forged(blob, 'b/p[2]')
        self.assertEqual(refusal(blob, [stored], stored['key']), 'protected_signing_area')


class SigningQuestionBox(unittest.TestCase):
    def test_rf18_a_signing_box_is_a_role_whatever_it_prints(self):
        """The question_box_signing reading, taken BEFORE the empty-cell check: empty, a drawing, or guidance ink."""
        for fill in (None, 'pict', 'Use black ink'):
            with self.subTest(fill=fill):
                blob = signing_box_form(fill)
                roles = w.destination_roles(blob)['roles']
                self.assertIn(('signing', 'question_box_signing', BODY + 'b/tbl[0]/tr[0]/tc[0]', None, None),
                              [(r['class'], r['source'], r['place'], r['start'], r['end']) for r in roles])
                for slot in ('b/tbl[0]/tr[0]/tc[0]', 'b/tbl[0]/tr[0]/tc[0]/p[0]'):
                    try:
                        w.locate(blob, [{'slot': BODY + slot, 'kind': 'long_text', 'label': 'Consultant review'}])
                    except w.V3Failure as exc:
                        self.assertIn(exc.code, ('destination_role', 'invalid_mapping'))
                    else:
                        self.fail('a long text answer was located in a signing box')
                stored = forged(blob, 'b/tbl[0]/tr[0]/tc[0]/p[0]', kind='long_text')
                self.assertEqual(refusal(blob, [stored], stored['key']), 'protected_signing_area')

    def test_notes_and_areas_of_the_box_are_unchanged(self):
        """The reading adds a role only: the engine's own fields and notes are exactly what they were."""
        blob = signing_box_form()
        found = w.inspect(blob)
        self.assertEqual([f['label'] for f in found['fields']], ['Plan'])
        self.assertTrue(any('Signing or consent context needs explicit review' in n for n in found['notes']))

    def test_an_ordinary_question_box_is_not_a_role(self):
        doc = Document(); doc.add_heading('History', level=2); doc.add_paragraph('Describe the presenting complaint?')
        box(doc)
        blob = data(doc)
        fields = w.inspect(blob)['fields']
        self.assertEqual([f['kind'] for f in fields], ['long_text'])
        self.assertEqual(w.destination_roles(blob)['roles'], [])
        self.assertIsNone(refusal(blob, fields, fields[0]['key']))


class ProtectedAndPolicy(unittest.TestCase):
    def test_pc11_the_protected_signing_block_stays_refused(self):
        doc = Document(); doc.add_paragraph('Discharge letter'); doc.add_paragraph('Plan: ______')
        p = doc.add_paragraph()
        for n in range(2):
            if n:
                p.add_run().add_tab()
            r = p.add_run(); r.underline = True; r._r.append(OxmlElement('w:tab'))
        cap = doc.add_paragraph(); cap.add_run('Signature'); cap.add_run().add_tab(); cap.add_run('Date')
        blob = data(doc)
        roles = {(r['class'], r['source'], r['place']) for r in w.destination_roles(blob)['roles']}
        self.assertIn(('protected', 'protected_area', BODY + 'b/p[2]'), roles)
        self.assertIn(('protected', 'protected_region', BODY + 'b/p[3]'), roles)
        with self.assertRaises(w.V3Failure):
            w.locate(blob, [{'slot': BODY + 'b/p[2]', 'kind': 'text', 'label': 'Signature'}])

    def test_a_manual_field_in_a_patient_section_carries_the_printed_author_role(self):
        doc = Document(); doc.add_paragraph('Pre-operative questionnaire'); doc.add_paragraph('Completed by the patient:')
        doc.add_paragraph('Allergies'); doc.add_paragraph('I smoke: ☐ Yes ☐ No')
        blob = data(doc)
        added = w.locate(blob, [{'slot': BODY + 'b/p[2]', 'kind': 'text', 'label': 'Allergies'}])[0]
        self.assertEqual(added['answer_policy']['source_author'], 'patient')
        self.assertEqual(w.destination_roles(blob, [added])['violations'], {})
        # The same field WITHOUT the printed requirement (a stored mapping from before) is refused at export.
        stripped = {k: v for k, v in added.items() if k != 'answer_policy'}
        self.assertEqual(w.destination_roles(blob, [stripped])['violations'][stripped['key']]['class'], 'policy')
        self.assertEqual(refusal(blob, [stripped], stripped['key'], 'The patient reports none.'), 'mapping_mismatch')
        # PC12: the engine's own patient-policy selection still fills.
        engine = w.inspect(blob)['fields']
        smoke = next(f for f in engine if f['label'] == 'I smoke')
        self.assertIsNone(refusal(blob, engine, smoke['key'], 'Yes'))

    def test_the_attestation_cell_is_a_policy_role(self):
        question = ('Please confirm that the patient has had sight of this report and/or '
                    'had an opportunity to add their comments, if appropriate or necessary.')
        doc = Document(); t = doc.add_table(rows=1, cols=2); t.cell(0, 0).text = question
        blob = data(doc)
        engine = w.inspect(blob)['fields']
        self.assertEqual(engine[0]['answer_policy']['attestation'], 'document_review')
        roles = [r for r in w.destination_roles(blob, engine)['roles'] if r['source'] == 'attestation']
        self.assertEqual([r['place'] for r in roles], [BODY + 'b/tbl[0]/tr[0]/tc[1]'])
        self.assertEqual(w.destination_roles(blob, engine)['violations'], {})
        relabelled = {**{k: v for k, v in engine[0].items() if k != 'answer_policy'}, 'label': 'Comments'}
        self.assertEqual(w.destination_roles(blob, [relabelled])['violations'][relabelled['key']]['class'], 'policy')

    def test_a_locked_content_control_is_protected(self):
        doc = Document(); p = doc.add_paragraph('Hospital number: ')
        sdt = OxmlElement('w:sdt'); pr = OxmlElement('w:sdtPr'); lock = OxmlElement('w:lock')
        lock.set(qn('w:val'), 'sdtContentLocked'); pr.append(lock); pr.append(OxmlElement('w:text')); sdt.append(pr)
        content = OxmlElement('w:sdtContent'); r = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = ' '
        r.append(t); content.append(r); sdt.append(content); p._p.append(sdt)
        doc.add_paragraph('Plan: ______')
        blob = data(doc)
        engine = w.inspect(blob)['fields']
        locked = next(f for f in engine if f['locator']['target']['type'] == 'sdt_text')
        self.assertTrue(locked.get('write_protected'))
        self.assertIn(('protected', 'locked_control'),
                      {(r['class'], r['source']) for r in w.destination_roles(blob, engine)['roles']})
        self.assertEqual(w.destination_roles(blob, engine)['violations'], {})


class LegacyRoleKind(unittest.TestCase):
    """The legacy default path's reader is the engine's own kind rule with its two measured over-reads removed."""

    CHECKLIST_SIGNED = ['Consent form signed', 'Consent signed', 'Drug chart signed', 'Discharge summary signed',
                        'DNACPR form signed', 'Prescription signed', 'Care plan signed', 'Theatre checklist signed',
                        'Time signed', 'Signed consent in notes', 'Sign in', 'Sign out', 'Sign-off',
                        'Date consent signed']
    INITIAL_READINGS = ['Initial assessment', 'Initial dose', 'Initial reading', 'Initial GCS', 'Initial observations',
                        'Initial impression', 'Initial plan', 'Initial presentation', 'Initial management',
                        'Initial lactate']
    SIGNING = ['Signature', 'Patient signature', 'Witness signature', 'Consultant signature', 'Signed by',
               'Signature of examining clinician', "Participant's signature", 'First doctor signature',
               'Signed off by consultant', 'Sign here', 'Initials', 'Clinician initials', 'Initial the box',
               'Initial:', 'Troponin — Initial']

    def test_checklist_states_and_adjectives_are_not_roles(self):
        for label in self.CHECKLIST_SIGNED + self.INITIAL_READINGS:
            with self.subTest(label=label):
                self.assertEqual(w.legacy_role_kind(label), '')

    def test_signatures_and_initials_are_roles(self):
        for label in self.SIGNING:
            with self.subTest(label=label):
                self.assertIn(w.legacy_role_kind(label), ('signature', 'initials'))

    def test_every_legacy_match_is_a_kind_rule_match(self):
        """Restricting, never widening: each reading is one the engine's kind rule already gives."""
        for label in self.CHECKLIST_SIGNED + self.INITIAL_READINGS + self.SIGNING + ['Signature date', 'Babinski sign']:
            with self.subTest(label=label):
                kind = w.legacy_role_kind(label)
                if kind:
                    self.assertEqual(w.Detector.kind_for(None, label), kind)


if __name__ == '__main__':
    unittest.main()
