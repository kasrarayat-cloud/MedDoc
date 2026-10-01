"""roles-2: ONE three-state destination decision (ordinary / protected / uncertain), read from the ORIGINAL's printed
label AND structure, on both engines.

Synthetic blank forms only, built in memory. Ids: REG = the 18 clinical labels f5fe720f no longer generated; HOLD = the
17 must-hold labels; L1:/L2:/L3: = the 28 recorded residual shapes (docs/rebuild/v1/destination-roles-20260930/
residuals.json); PC = positive controls (an ordinary field beside each refused or held place still fills).
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
LINE = '______________________'

#: The 18 labels f5fe720f no longer generated, and how roles-2 classifies each (state, basis).
REG18 = {
    'Troponin (initial)': ('ordinary', 'measure_head'),
    'Lactate (initial)': ('ordinary', 'measure_head'),
    'Dose (initial)': ('ordinary', 'measure_head'),
    'Troponin initial': ('ordinary', 'measure_head'),
    'Troponin — Initial (ng/L)': ('ordinary', 'measure_head'),
    'Initial (baseline) weight': ('ordinary', 'attributive'),
    'Initial and ongoing management': ('ordinary', 'attributive'),
    'Visit type (initial/follow-up)': ('ordinary', 'sequence_option'),
    'Initial / repeat': ('ordinary', 'sequence_option'),
    'Gene expression signature': ('ordinary', 'scientific_signature'),
    'Consent form signed by patient': ('ordinary', 'document_signed_by'),
    'Drug chart signed by prescriber': ('ordinary', 'document_signed_by'),
    'Patient signature obtained': ('ordinary', 'signature_state'),
    'Witness signature obtained': ('ordinary', 'signature_state'),
    # Not restored, classified honestly: the label alone cannot tell a sign-off status or the time of a signing from
    # the place the consultant (or the patient on admission) signs - uncertain: never generated, the clinician types it.
    'Signed off by consultant': ('uncertain', 'sign_off'),
    'Signed on admission': ('uncertain', 'signed_when'),
    # A truly signing place: 'Initial' alone is the imperative / the initials box (the same words as the must-hold
    # 'Initial:'); 'Patient initials' is the patient's own initials (the same grammar as 'Nurse initials').
    'Initial': ('protected', 'bare_initial'),
    'Patient initials': ('protected', 'initials_noun'),
}
HOLD17 = ('Patient signature', 'Initials', 'Witness signature', 'Consultant signature', 'Signature of examining clinician',
          "Participant's signature", 'Nurse initials', 'Initial here', 'Initial each page', 'Signature and date',
          'Signature (patient)', 'Signed by (witness)', 'Nurse (initial)', 'Initial:', 'Staff initial', 'Nurse initial',
          'Initials — Nurse')


def data(doc):
    out = io.BytesIO(); doc.save(out); return out.getvalue()


def xml(blob):
    return zipfile.ZipFile(io.BytesIO(blob)).read('word/document.xml').decode()


def tabbed(p, text):
    parts = text.split('\t')
    for i, part in enumerate(parts):
        if part:
            p.add_run(part)
        if i < len(parts) - 1:
            p.add_run()._r.append(OxmlElement('w:tab'))
    return p


def lines(*texts, heading='Clinic record'):
    doc = Document()
    if heading:
        doc.add_heading(heading, level=2)
    for text in texts:
        tabbed(doc.add_paragraph(), text)
    doc.add_paragraph('Plan: ______')
    return data(doc)


def bordered(table):
    borders = OxmlElement('w:tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        edge = OxmlElement('w:' + side); edge.set(qn('w:val'), 'single'); borders.append(edge)
    table.cell(0, 0)._tc.get_or_add_tcPr().append(borders)
    return table


def box_after(question, inner=(), heading='Consultant review'):
    doc = Document(); doc.add_heading(heading, level=2)
    doc.add_paragraph(question)
    cell = bordered(doc.add_table(rows=1, cols=1)).cell(0, 0)
    for i, text in enumerate(inner):
        tabbed(cell.paragraphs[0] if i == 0 else cell.add_paragraph(), text)
    doc.add_paragraph('Plan: ______')
    return data(doc)


def two_col(rows, br=False):
    doc = Document(); doc.add_heading('Clinic record', level=2)
    table = doc.add_table(rows=len(rows), cols=2); table.style = 'Table Grid'
    for i, label in enumerate(rows):
        cell = table.cell(i, 0)
        if '|' in label:
            first, second = label.split('|', 1)
            if br:
                p = cell.paragraphs[0]; p.add_run(first); p.add_run()._r.append(OxmlElement('w:br')); p.add_run(second)
            else:
                cell.paragraphs[0].add_run(first); cell.add_paragraph(second)
        else:
            cell.paragraphs[0].add_run(label)
    return data(doc)


def control_line(caption, alias):
    doc = Document(); doc.add_heading('Clinic record', level=2)
    p = doc.add_paragraph(caption)
    sdt = OxmlElement('w:sdt'); pr = OxmlElement('w:sdtPr')
    al = OxmlElement('w:alias'); al.set(qn('w:val'), alias); pr.append(al); pr.append(OxmlElement('w:text'))
    pr.append(OxmlElement('w:showingPlcHdr')); sdt.append(pr)
    content = OxmlElement('w:sdtContent'); r = OxmlElement('w:r'); t = OxmlElement('w:t')
    t.text = 'Click or tap here to enter text.'; r.append(t); content.append(r); sdt.append(content)
    p._p.append(sdt)
    doc.add_paragraph('Plan: ______')
    return data(doc)


def report(blob):
    fields = w.inspect(blob)['fields']
    return fields, w.destination_roles(blob, fields)


def generated(field, rep):
    """Whether generation asks this field (v3): an answer kind, not write-protected, no role violation, not held."""
    return (field['kind'] in ('text', 'long_text', 'date', 'time', 'choice', 'multi_choice', 'checkbox')
            and not field.get('write_protected') and field['key'] not in rep['violations']
            and field['key'] not in rep['held'])


def by_label(fields):
    return {f['label']: f for f in fields}


def manual(blob, slot, kind='text', label='Manual'):
    try:
        return w.locate(blob, [{'slot': BODY + slot, 'kind': kind, 'label': label}])[0], None
    except w.V3Failure as exc:
        return None, exc.code


class TheEighteenAndTheSeventeen(unittest.TestCase):
    """(a) each of the 18 labels: classified, and generated and exported where clinical; (b) the 17 held."""

    def test_each_of_the_18_is_classified(self):
        for label, (state, basis) in REG18.items():
            with self.subTest(label=label):
                reading = w.destination_state(label)
                self.assertEqual((reading['state'], reading['basis']), (state, basis))
                self.assertEqual(reading['reading'], w.ROLE_READING)

    def test_the_clinical_ones_are_generated_and_filled_on_v3(self):
        for label, (state, _) in REG18.items():
            with self.subTest(label=label):
                blob = lines(label + ': ______')
                fields, rep = report(blob)
                field = fields[0]
                if state == 'ordinary':
                    self.assertNotIn(field['kind'], ('signature', 'initials'))
                    self.assertTrue(generated(field, rep))
                    self.assertIn(SYN, xml(w.fill(blob, fields, {field['key']: SYN})))
                    self.assertEqual(w.legacy_role_kind(label), '')
                else:
                    self.assertIn(field['kind'], ('signature', 'initials'))
                    self.assertFalse(generated(field, rep))
                    self.assertTrue(w.legacy_role_kind(label))

    def test_the_17_must_hold_labels_are_protected_on_both_engines(self):
        for label in HOLD17:
            with self.subTest(label=label):
                self.assertEqual(w.destination_state(label)['state'], 'protected')
                self.assertIn(w.legacy_role_kind(label), ('signature', 'initials'))
                blob = lines(label + ' ______' if label.endswith(':') else label + ': ______')
                fields, rep = report(blob)
                self.assertIn(fields[0]['kind'], ('signature', 'initials'))
                self.assertTrue(any(r['class'] == 'signing' for r in rep['roles']))
                self.assertEqual(manual(blob, 'b/p[1]')[1], 'destination_role')

    def test_an_uncertain_place_is_never_generated_and_takes_a_clinicians_text_field(self):
        for label in ('Signed off by consultant', 'Signed on admission', 'Sign', 'Reviewed and signed',
                      'Wristband (initial)'):
            with self.subTest(label=label):
                blob = lines(label + ': ______')
                fields, rep = report(blob)
                self.assertEqual(w.destination_state(label)['state'], 'uncertain')
                self.assertIn(fields[0]['kind'], ('signature', 'initials'))
                self.assertFalse(generated(fields[0], rep))
                self.assertIn(fields[0]['key'], rep['uncertain_places'])
                added, code = manual(blob, 'b/p[1]')
                self.assertIsNone(code)
                rest = fields[1:] + [added]
                rep = w.destination_roles(blob, rest)
                self.assertIn(added['key'], rep['held'])           # held: never generated
                self.assertNotIn(added['key'], rep['violations'])  # not refused: the clinician may type it
                self.assertIn('TYPED', xml(w.fill(blob, rest, {added['key']: 'TYPED'})))


class Structure(unittest.TestCase):
    """The same decision from structure: a row label and its column header each read as itself.

    roles-3: a sequence word beside a bare 'Initial' in its table and a unit printed elsewhere in the row are no longer
    evidence (the refutation of 39bdb9f0 released initials columns through both - RepairOf39bdb9f0)."""

    def test_a_bare_initial_is_the_initials_place_beside_a_sequence_word_too(self):
        for rows in (['Initial', 'Repeat', 'Plan'], ['Initial', 'Plan']):
            with self.subTest(rows=rows):
                fields, rep = report(two_col(rows))
                initial = by_label(fields)['Initial']
                self.assertEqual(initial['kind'], 'initials')
                self.assertFalse(generated(initial, rep))
                self.assertEqual(w.legacy_role_kind('Initial', siblings=rows[1:]), 'initials')

    def test_a_lab_table_reads_its_row_label_and_column_header_each_as_itself(self):
        """'Troponin (initial)' in a results table with a 'Result' column is a measurement (the engine's joined label
        'Troponin (initial) — Result' closes no qualifier); 'Nurse (initial)' and 'Nurse initials' rows, and an
        'Initials' column, stay held. roles-3: 'Fibre initial' is no measurement because a units column prints 'mg'
        (uncertain), and an 'Initial' column beside 'Repeat' is uncertain (an observations chart prints the same
        column for initials)."""
        def lab(rows, headers):
            doc = Document(); table = doc.add_table(rows=len(rows) + 1, cols=len(headers)); table.style = 'Table Grid'
            for c, h in enumerate(headers):
                table.cell(0, c).text = h
            for r, row in enumerate(rows, start=1):
                for c, v in enumerate(row):
                    table.cell(r, c).text = v
            doc.add_paragraph('Plan: ______')
            return data(doc)
        fields, rep = report(lab((('Troponin (initial)', '', 'ng/L'), ('Fibre initial', '', 'mg'), ('Nurse initials', '', ''),
                                  ('Nurse (initial)', '', '')), ('Test', 'Result', 'Units')))
        by = by_label(fields)
        self.assertTrue(generated(by['Troponin (initial) — Result'], rep))
        self.assertFalse(generated(by['Fibre initial — Result'], rep))
        self.assertIn(by['Fibre initial — Result']['key'], rep['uncertain_places'])
        self.assertFalse(generated(by['Nurse initials — Result'], rep))
        self.assertFalse(generated(by['Nurse (initial) — Result'], rep))
        fields, rep = report(lab((('Troponin', '', ''),), ('Analyte', 'Initial', 'Repeat')))
        self.assertFalse(generated(by_label(fields)['Troponin — Initial'], rep))
        self.assertIn(by_label(fields)['Troponin — Initial']['key'], rep['uncertain_places'])
        self.assertTrue(generated(by_label(fields)['Troponin — Repeat'], rep))
        fields, rep = report(lab((('Nurse', '', ''),), ('Staff', 'Initials', 'Date')))
        self.assertFalse(generated(by_label(fields)['Nurse — Initials'], rep))
        self.assertTrue(generated(by_label(fields)['Nurse — Date'], rep))

    def test_a_person_beside_a_sequence_word_stays_held(self):
        self.assertEqual(w.legacy_role_kind('Nurse initial', siblings=['Repeat']), 'initials')

    def test_an_unknown_head_is_uncertain_and_no_unit_makes_it_a_measurement(self):
        self.assertEqual(w.destination_state('Wristband (initial)')['state'], 'uncertain')
        self.assertEqual(w.destination_state('Phlebotomist (initial)')['state'], 'protected')     # a person's head
        # no unit is evidence, printed in the label, the row or the column (roles-3, L1:R1-04): the head is
        self.assertEqual(w.destination_state('Fibre initial (mg)')['state'], 'uncertain')
        self.assertEqual(w.destination_state('Fibre initial', unit=True)['state'], 'uncertain')
        self.assertEqual(w.destination_state('Troponin (ng/L) — Initial')['basis'], 'measure_head')
        # a person never becomes a measurement, unit or not
        self.assertEqual(w.destination_state('Nurse (initial) (mg)')['state'], 'protected')


class Residuals(unittest.TestCase):
    """(d) the 28 recorded residual shapes: every unsafe write refused or held, each with an ordinary positive control."""

    def assert_held(self, blob, labels_held, controls=('Plan',)):
        fields, rep = report(blob)
        for f in fields:
            if f['label'] in controls:
                self.assertTrue(generated(f, rep), f['label'])
                self.assertIn(SYN, xml(w.fill(blob, fields, {f['key']: SYN})))
        held = [f for f in fields if not generated(f, rep)]
        self.assertEqual(len([f for f in fields if f['label'] not in controls]), len(held))
        self.assertEqual(sorted(f['label'] for f in held), sorted(labels_held))
        return fields, rep

    def test_l1_rr1_01_ordinary_areas_inside_a_signing_box_are_its_signing_places(self):
        blob = box_after('Signed by the consultant:', [LINE, 'Signature, date: ______', 'Dr ' + LINE + ' (consultant)',
                                                       LINE + '    Date: ______'])
        fields, rep = report(blob)
        held = [f for f in fields if not generated(f, rep)]
        self.assertEqual(len(held), 4)
        date = [f for f in fields if f['label'] == 'Date']
        self.assertEqual(len(date), 1)                       # PC: the date beside the signature line
        self.assertTrue(generated(date[0], rep))
        self.assertIn('2026-09-30', xml(w.fill(blob, fields, {date[0]['key']: '2026-09-30'})))

    def test_l1_rr1_02_l2_rr3_01_a_signature_joined_to_a_date_is_one_signing_place(self):
        for label in ('Signature, date', 'Signature - date', 'Signature, date/time', 'Patient signature, date',
                      'Print name, sign and date', 'Patient to sign and date', 'Signed by (name, date)',
                      'Electronically signed by (name, date)'):
            with self.subTest(label=label):
                self.assertEqual(w.destination_state(label)['state'], 'protected')
                self.assert_held(lines(label + ': ______'), [label])

    def test_l1_rr1_03_l1_rr1_04_l1_rr1_09_l1_rr1_11_l2_rr3_02_l1_f4_signing_labels(self):
        for label in ('Initial 1', 'Initial 2', 'Initial x2', 'Initial on each page', 'Initial against each entry',
                      'Sign in box', 'To be signed', 'Signed consultant', 'Signed patient', 'Consultant signed',
                      'Registrar signed', 'Patient signed', 'Initial in box', 'Sign below', 'Sign and print name',
                      'Sign & stamp', 'Please sign', 'Given by (sign)', 'Countersignature', 'Initialled by',
                      'Nurse sign', 'Print name and sign', 'Name and sign', 'Countersign', 'Witness to sign',
                      'Nurse 2 sign', 'Patient signs here', 'Consultant sign-off', 'Time out signed by'):
            with self.subTest(label=label):
                self.assertEqual(w.destination_state(label)['state'], 'protected')
                self.assertTrue(w.legacy_role_kind(label))
                blob = lines(label + ': ______')
                self.assert_held(blob, [label])
                self.assertEqual(manual(blob, 'b/p[1]')[1], 'destination_role')
        for label in ('Sign', 'Reviewed and signed'):
            with self.subTest(label=label):
                self.assertEqual(w.destination_state(label)['state'], 'uncertain')
                self.assert_held(lines(label + ': ______'), [label])

    def test_l1_rr1_06_a_writing_line_under_or_over_a_signing_caption(self):
        cases = (
            (('Consultant signature:', '', LINE), 'b/p[3]'),
            ((LINE, 'Consultant signature'), 'b/p[1]'),
            (('Consultant signature:', LINE + ' (use black ink)'), 'b/p[2]'),
            (('Signed by the consultant:', 'Dr ' + LINE), 'b/p[2]'),
        )
        for texts, slot in cases:
            with self.subTest(texts=texts):
                blob = lines(*texts)
                fields, rep = report(blob)
                self.assertFalse(any(generated(f, rep) for f in fields if f['label'] != 'Plan'))
                self.assertEqual(manual(blob, slot)[1], 'destination_role')
        # (d) the date on the signature line stays an ordinary answer (PC02)
        blob = lines('Consultant signature:', LINE + '    Date: ______')
        fields, rep = report(blob)
        date = [f for f in fields if f['label'] == 'Date' and generated(f, rep)]
        self.assertEqual(len(date), 1)
        self.assertIn('2026-09-30', xml(w.fill(blob, fields, {date[0]['key']: '2026-09-30'})))

    def test_l1_f1_captions_side_by_side_under_lines(self):
        blob = lines(LINE + '\t\t' + LINE, 'Patient signature\t\t\tDate')
        fields, rep = report(blob)
        self.assertFalse(any(generated(f, rep) for f in fields if f['label'] != 'Plan'))

    def test_l1_f2_a_declaration_above_captions_under_lines(self):
        for texts, protected, uncertain in (
                (('Please complete in block capitals.', LINE, 'Signature of clinician', LINE, 'Name and grade'),
                 'b/p[2]', 'b/p[4]'),
                (('I consent to this procedure.', LINE, 'Patient signature', LINE, 'Witness signature'), 'b/p[2]', None),
                (('I confirm the above information is correct.', LINE, 'Patient signature', LINE, 'Print name'),
                 'b/p[2]', 'b/p[4]')):
            with self.subTest(texts=texts[0]):
                blob = lines(*texts)
                fields, rep = report(blob)
                self.assertFalse(any(generated(f, rep) for f in fields if f['label'] != 'Plan'))
                self.assertEqual(manual(blob, protected)[1], 'destination_role')
                if uncertain:
                    # the line between a signing caption and its own ordinary caption: uncertain (a typed name fills)
                    added, code = manual(blob, uncertain)
                    self.assertIsNone(code)
                    self.assertIn(added['key'], w.destination_roles(blob, [added])['held'])

    def test_l1_f3_l1_rr1_05_a_label_cell_wrapped_over_two_paragraphs(self):
        for rows, br in ((['Consultant|signature', 'Plan'], False), (['Nurse|initials', 'Plan'], False),
                         (['Consultant|signature', 'Plan'], True), (['Patient|signature', 'Plan'], False)):
            with self.subTest(rows=rows, br=br):
                blob = two_col(rows, br=br)
                fields, rep = report(blob)
                first = fields[0]
                self.assertIn(first['kind'], ('signature', 'initials'))
                self.assertFalse(generated(first, rep))
                self.assertTrue(generated(fields[1], rep))

    def test_l1_f5_a_content_control_beside_a_signing_caption(self):
        for alias in ('Answer', 'Text1', 'Clinician'):
            with self.subTest(alias=alias):
                blob = control_line('Consultant signature: ', alias)
                fields, rep = report(blob)
                self.assertEqual(fields[0]['kind'], 'signature')
                self.assertFalse(generated(fields[0], rep))
        blob = control_line('Hospital number: ', 'Answer')       # PC: an ordinary caption keeps its control
        fields, rep = report(blob)
        self.assertTrue(generated(fields[0], rep))

    def test_l1_f6_a_countersignature_or_signatures_box(self):
        for question in ('Please provide your countersignature', 'Countersignature?', 'Signatures?',
                         'Please provide signatures below'):
            with self.subTest(question=question):
                blob = box_after(question, heading='Review')
                fields, rep = report(blob)
                self.assertEqual(fields[0]['kind'], 'signature')
                self.assertEqual(manual(blob, 'b/tbl[0]/tr[0]/tc[0]', 'long_text')[1], 'destination_role')
        blob = box_after('Please describe the presenting complaint?', heading='Review')   # PC: an ordinary box
        fields, rep = report(blob)
        self.assertTrue(generated(fields[0], rep))

    def test_l1_f7_person_captions_inside_a_signatures_box(self):
        for inner in (['Patient: ______________', 'Parent/guardian: ______________'],
                      ['Consultant: ______________', 'Registrar: ______________']):
            with self.subTest(inner=inner):
                fields, rep = report(box_after('Signatures', inner, heading='Consent'))
                self.assertFalse(any(generated(f, rep) for f in fields if f['label'] != 'Plan'))
        # PC (R2-01): an ordinary question inside a consent frame keeps its answer
        fields, rep = report(box_after('Signatures', ['Patient name: ______________', 'Date: ______'],
                                       heading='Consent'))
        self.assertTrue(all(generated(f, rep) for f in fields))

    def test_l1_f8_guidance_between_a_caption_and_its_line_leaves_the_line_held(self):
        for guidance in ('Use black ink.', '(use black ink)'):
            with self.subTest(guidance=guidance):
                fields, rep = report(lines('Consultant signature', guidance, LINE))
                self.assertFalse(any(generated(f, rep) for f in fields if f['label'] != 'Plan'))

    def test_l1_f9_a_drawn_or_wide_line_under_a_signing_caption_refuses_a_manual_add(self):
        doc = Document(); doc.add_heading('Clinic record', level=2)
        p = doc.add_paragraph()
        bdr = OxmlElement('w:pBdr'); bottom = OxmlElement('w:bottom'); bottom.set(qn('w:val'), 'single'); bdr.append(bottom)
        p._p.get_or_add_pPr().append(bdr)
        doc.add_paragraph('Consultant signature'); doc.add_paragraph('Plan: ______')
        self.assertEqual(manual(data(doc), 'b/p[1]')[1], 'destination_role')
        for rule in ('＿＿＿＿＿＿＿＿＿＿＿', '‗‗‗‗‗‗‗‗'):
            with self.subTest(rule=rule):
                self.assertEqual(manual(lines('Consultant signature', rule), 'b/p[2]')[1], 'destination_role')

    def test_l1_rr1_07_a_signing_box_read_through_a_bookmark_a_control_empties_or_a_layout_cell(self):
        def form(kind):
            doc = Document(); doc.add_heading('Consultant review', level=2)
            if kind == 'nested':
                cell = doc.add_table(rows=1, cols=1).cell(0, 0)
                cell.paragraphs[0].add_run('Signed by the consultant:')
                bordered(cell.add_table(rows=1, cols=1))
                slot = 'b/tbl[0]/tr[0]/tc[0]/tbl[0]/tr[0]/tc[0]'
            else:
                p = doc.add_paragraph('Signed by the consultant:')
                if kind == 'sdt':
                    sdt = OxmlElement('w:sdt'); sdt.append(OxmlElement('w:sdtPr')); content = OxmlElement('w:sdtContent')
                    p._p.addprevious(sdt); content.append(p._p); sdt.append(content)
                for _ in range(3 if kind == 'empties' else 0):
                    doc.add_paragraph('')
                table = bordered(doc.add_table(rows=1, cols=1))
                if kind == 'bookmark':
                    mark = OxmlElement('w:bookmarkStart'); mark.set(qn('w:id'), '0'); mark.set(qn('w:name'), 'x')
                    table._tbl.addprevious(mark)
                slot = 'b/tbl[0]/tr[0]/tc[0]'
            doc.add_paragraph('Plan: ______')
            return data(doc), slot
        for kind in ('nested', 'bookmark', 'sdt', 'empties'):
            with self.subTest(kind=kind):
                blob, slot = form(kind)
                self.assertEqual(manual(blob, slot, 'long_text')[1], 'destination_role')
                fields, rep = report(blob)
                plan = by_label(fields)['Plan']
                self.assertIn(SYN, xml(w.fill(blob, fields, {plan['key']: SYN})))


class RealFormShapes(unittest.TestCase):
    """(d) the development-form exposures (c/word-census exposure.txt), rebuilt synthetically: each unsafe write is
    refused or held, each beside an ordinary field that still fills."""

    def test_d15_a_signature_line_read_as_three_areas_is_one_signing_run_and_its_date_fills(self):
        blob = lines('Signature:……………........................…………\t\t\t\tDate: _____/_____/_____')
        fields, rep = report(blob)
        run = [f for f in fields if f['locator']['target'].get('start', 99) < 50 and f['label'] != 'Plan']
        self.assertEqual(len(run), 3)
        self.assertFalse(any(generated(f, rep) for f in run))
        date = next(f for f in fields if f['kind'] == 'date')                 # PC02
        self.assertTrue(generated(date, rep))
        self.assertIn('30', xml(w.fill(blob, fields, {date['key']: '30'})))

    def test_d01_an_electronic_signature_attestation_keeps_its_signer_held(self):
        blob = lines('Electronically Signed On <<insert date and time>> By:')
        fields, rep = report(blob)
        by = next(f for f in fields if f['locator']['target']['start'] > 50)
        self.assertEqual(by['kind'], 'signature')
        date = next(f for f in fields if f['kind'] == 'date')                 # the attested date stays an answer
        self.assertTrue(generated(date, rep))

    def test_d17_a_sign_placeholder_is_held_and_a_name_placeholder_fills(self):
        doc = Document(); doc.add_heading('Letter', level=1); doc.add_paragraph('Dear [Patient name],')
        doc.add_paragraph('Yours sincerely,'); doc.add_paragraph('[Sign]'); doc.add_paragraph('Plan: ______')
        blob = data(doc)
        fields, rep = report(blob)
        sign = next(f for f in fields if f['locator']['slot'] == 'b/p[3]')
        self.assertIn(sign['key'], rep['uncertain_places'])
        self.assertFalse(generated(sign, rep))
        name = next(f for f in fields if f['locator']['slot'] == 'b/p[1]')
        self.assertTrue(generated(name, rep))

    def test_d15_an_authors_note_about_the_wording_is_no_answer(self):
        fields, rep = report(lines('You will be asked to give samples <if POS collects genetic data> during the visit.'))
        self.assertFalse(generated(fields[0], rep))
        self.assertIn(fields[0]['key'], rep['uncertain_places'])
        fields, rep = report(lines('Dear <Patient name>,'))                    # PC: a placeholder naming its answer
        self.assertTrue(generated(fields[0], rep))

    def test_d29_an_agent_heading_of_a_signing_row_is_held_and_the_name_fills(self):
        doc = Document(); doc.add_heading('Review', level=1)
        table = doc.add_table(rows=1, cols=4); table.style = 'Table Grid'
        for i, text in enumerate(('Completed by:', 'Name:', 'Signature:', 'Date:')):
            table.cell(0, i).text = text
        doc.add_paragraph('Plan: ______')
        fields, rep = report(data(doc))
        by = by_label(fields)
        self.assertFalse(generated(by['Completed by'], rep))
        self.assertTrue(generated(by['Name'], rep))
        self.assertTrue(generated(by['Date'], rep))

    def test_d36_a_caption_line_of_several_segments_holds_its_whole_writing_line(self):
        fields, rep = report(lines('', 'Signature of Participant\t\t\tPrint Name of Participant\t\t\tDate', '',
                                   heading='Signatures'))
        self.assertFalse(generated(fields[0], rep))

    def test_d36_an_initials_segment_with_no_area_refuses_a_manual_add_and_the_date_fills(self):
        text = 'Circle Yes or No:     Yes     No     Initials:          Date:  '
        blob = lines(text, heading='Signatures')
        fields, rep = report(blob)
        date = next(f for f in fields if f['kind'] == 'date')
        self.assertTrue(generated(date, rep))
        at = text.index('Initials:') + len('Initials:') + 2
        roles = [r for r in rep['roles'] if r['source'] == 'governed_line']
        self.assertTrue(any(r['class'] == 'signing' and r['start'] <= at < r['end'] for r in roles))

    def test_a_first_person_consent_declaration_is_consent_wording_and_a_consent_question_is_ordinary(self):
        fields, rep = report(lines('I have been asked to give consent for my child to participate in this medical study:',
                                   'Consent obtained? ______'))
        declaration, question = fields[0], fields[1]
        self.assertFalse(generated(declaration, rep))
        self.assertIn(declaration['key'], rep['uncertain_places'])
        self.assertTrue(generated(question, rep))
        for label in ('I agree to take part in this study', 'I hereby consent to the procedure'):
            self.assertEqual(w.destination_state(label)['state'], 'uncertain')
        for label in ("I declare that I have taken note of the patient's withdrawal of consent", 'Consent obtained?',
                      'I understand that the applicant was examined', 'I want to take part in this study'):
            self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)


class PositiveControls(unittest.TestCase):
    """Ordinary answers beside the new readings keep generating (refuter batteries' over-hold shapes)."""

    def test_a_square_bracket_hint_inside_a_question_is_the_forms_own_hint(self):
        for text in ('Ethnicity: White / Other [If other, please specify]', 'Have you had surgery? [If yes, give details]',
                     'Mobility aid: [e.g. walking stick, frame]', 'Referral details: [if any]'):
            with self.subTest(text=text):
                fields, rep = report(lines(text))
                self.assertTrue(generated(fields[0], rep))

    def test_options_beside_a_signature_caption_are_no_part_of_it(self):
        blob = lines('Reviewed: ☐ Yes ☐ No    Signature: ______')
        fields, rep = report(blob)
        reviewed = by_label(fields)['Reviewed']
        self.assertEqual(reviewed['kind'], 'choice')
        self.assertTrue(generated(reviewed, rep))

    def test_a_sentence_before_a_caption_is_not_its_caption(self):
        fields, rep = report(lines('Report digitally signed. Transcribed by: ________'))
        self.assertTrue(generated(by_label(fields)['Transcribed by'], rep))


class ConsentChoices(unittest.TestCase):
    """A factual consent question is ordinary; the signer's own consent choice is a consent ACTION (uncertain: never
    ticked from the notes, the clinician may tick it). Measured on development consent forms (D15, D33, D34, D37)."""

    def test_the_signers_consent_choice_is_held_and_a_consent_question_is_asked(self):
        for text in ('I agree that my samples may be kept in a biobank:  ☐ Yes   ☐ No',
                     'I give consent to store my coded data:  ☐ Yes   ☐ No',
                     '<if POS collecting genetic data>I give consent to share my data:  ☐ Yes  ☐ No',
                     '(~Include if appropriate. ~) I agree that my doctor may contact me:  ☐ Yes  ☐ No'):
            with self.subTest(text=text):
                blob = lines(text)
                fields, rep = report(blob)
                choice = next(f for f in fields if f['kind'] == 'choice')
                self.assertIn(choice['key'], rep['held'])
                self.assertNotIn(choice['key'], rep['violations'])
                w.fill(blob, fields, {choice['key']: 'Yes'})                    # the clinician may tick it
        fields, rep = report(lines('Consent obtained?  ☐ Yes  ☐ No'))
        self.assertTrue(generated(fields[0], rep))

    def test_printed_yes_no_words_under_a_consent_sentence_and_a_consent_question_asked_of_the_signer(self):
        for question in ('I agree that my samples and related health information may be kept in a biobank.',
                         'Will you allow your samples to be stored for future research?',
                         'Do you agree to be contacted about future studies?'):
            with self.subTest(question=question):
                fields, rep = report(lines(question, '\t YES\t\tNO', heading='Optional studies'))
                choice = next(f for f in fields if f['kind'] == 'choice')
                self.assertIn(choice['key'], rep['held'])
        for label in ('Do you allow pets at home?', 'Did the patient consent?', 'Can you allow time for the test?'):
            self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)


class LegacyEngineRoles(unittest.TestCase):
    """The legacy 'roles' operation reads the label cell's printed words (paragraphs and line breaks as spaces), its
    stacked captions one by one, and the labels beside it in its table."""

    def roles(self, blob):
        import tempfile
        from pathlib import Path
        from . import engine
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp); (ws / 'input.docx').write_bytes(blob)
            found = engine.process(ws, {'operation': 'inspect', 'format': 'docx', 'engine': 'legacy'})
            roles = engine.process(ws, {'operation': 'roles', 'format': 'docx', 'engine': 'legacy',
                                        'mapping': found['fields'], 'answers': {}})
        return {f['label']: roles['legacy_roles'][f['key']] for f in found['fields']}

    def test_l1_rr1_05_a_wrapped_label_cell_is_read_as_its_words(self):
        for br in (False, True):
            with self.subTest(br=br):
                rows = self.roles(two_col(['Consultant|signature', 'Nurse|initials', 'Plan'], br=br))
                self.assertEqual(rows['Consultantsignature']['printed_label'], 'Consultant signature')
                self.assertEqual((rows['Consultantsignature']['state'], rows['Nurseinitials']['state']),
                                 ('protected', 'protected'))
                self.assertEqual(rows['Plan']['state'], 'ordinary')

    def test_l1_f1_two_captions_stacked_in_one_label_cell_are_uncertain(self):
        for rows_in in (['Signature|Date', 'Plan'], ['Date of|signature', 'Plan']):
            with self.subTest(rows=rows_in):
                rows = self.roles(two_col(rows_in))
                held = next(v for k, v in rows.items() if k != 'Plan')
                self.assertEqual((held['state'], held['basis']), ('uncertain', 'stacked_caption'))
                fields, rep = report(two_col(rows_in))           # the same reading on contract v3
                self.assertIn(fields[0]['key'], rep['uncertain_places'])
                self.assertFalse(generated(fields[0], rep))

    def test_two_captions_a_tab_separates_in_one_label_cell_are_uncertain(self):
        """'Signature of patient<tab>Date' prints two captions over one answer cell. Read as joined words it is the date
        question 'Signature of patient date', which released the legacy row f5fe720f held (its runs joined to
        'patientDate') and let contract v3 generate a date there. Each caption is read alone, as stacked lines are."""
        def tab_col(rows):
            doc = Document(); doc.add_heading('Clinic record', level=2)
            table = doc.add_table(rows=len(rows), cols=2); table.style = 'Table Grid'
            for i, label in enumerate(rows):
                tabbed(table.cell(i, 0).paragraphs[0], label)
            return data(doc)
        for label in ('Signature of patient\t\t\tDate', 'Signature\tDate', 'Consultant signature\tDate signed',
                      'Date\tSignature'):
            with self.subTest(label=label):
                blob = tab_col([label, 'Plan'])
                held = next(v for k, v in self.roles(blob).items() if k != 'Plan')
                self.assertEqual((held['state'], held['basis']), ('uncertain', 'stacked_caption'))
                fields, rep = report(blob)                       # the same reading on contract v3
                self.assertIn(fields[0]['key'], rep['uncertain_places'])
                self.assertFalse(generated(fields[0], rep))
        # positive controls: tab-separated captions with no signing place, and a label read whole on evidence
        for label in ('Date\tTime', 'Troponin\tng/L', 'Consent form signed by patient', 'Patient signature obtained'):
            with self.subTest(control=label):
                blob = tab_col([label, 'Plan'])
                row = next(v for k, v in self.roles(blob).items() if k != 'Plan')
                self.assertEqual(row['state'], 'ordinary')
                fields, rep = report(blob)
                self.assertTrue(generated(fields[0], rep))
        # a governed writing line keeps its own caption: the blank after 'Date:' is the date's
        fields, rep = report(lines('Signature of patient\t\t\tDate: ______'))
        self.assertEqual(fields[0]['kind'], 'date')

    def assert_held_on_both(self, label, state, basis=None):
        blob = two_col([label, 'Plan'])
        row = next(v for k, v in self.roles(blob).items() if k != 'Plan')
        self.assertEqual(row['state'], state, label)
        if basis:
            self.assertEqual(row['basis'], basis, label)
        fields, rep = report(blob)
        self.assertFalse(any(generated(f, rep) for f in fields if f['label'] != 'Plan'), label)

    def assert_generated_on_both(self, label):
        blob = two_col([label, 'Plan'])
        row = next(v for k, v in self.roles(blob).items() if k != 'Plan')
        self.assertEqual(row['state'], 'ordinary', label)
        fields, rep = report(blob)
        self.assertTrue(generated(fields[0], rep), label)

    def test_a_placeholder_printed_as_the_label_is_read_as_its_own_words(self):
        """'[Signature, date]' read with its brackets was the date question (generated on both engines' rows on
        f5fe720f, and on legacy rows on the roles-2 commits before this one); 'Signature, date' is a signing place."""
        for label, state in (('[Sign]', 'uncertain'), ('<Sign>', 'uncertain'), ('[Signature, date]', 'protected'),
                             ('[Signature – Date]', 'protected'), ('[Sign name here]', 'protected')):
            with self.subTest(label=label):
                self.assert_held_on_both(label, state)
        for label in ('[Patient name]', '[X weeks/months]', 'Troponin [ng/L]'):
            with self.subTest(control=label):
                self.assert_generated_on_both(label)
        # a bracketed qualifier is read with the label, as a parenthesised one is (contract v3 reads '[initial]' in a
        # label cell as a placeholder area of its own, a different place)
        self.assertEqual(w.destination_state('Dose [initial]')['basis'], 'measure_head')

    def test_a_bracketed_part_that_alone_holds_the_place_is_uncertain(self):
        self.assertEqual(w.destination_state('Consent confirmed [Sign and date]')['basis'], 'bracketed_caption')
        self.assert_held_on_both('Consent confirmed [Sign and date]', 'uncertain', 'bracketed_caption')
        self.assert_held_on_both('[Witness to sign] — Relationship', 'uncertain', 'bracketed_caption')
        # a bracketed note with no signing place, and evidence read on the whole, release as before
        for label in ('Visit type [initial/follow-up]', 'Lactate [initial]'):
            with self.subTest(control=label):
                self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)

    def test_captions_writing_blanks_separate_in_one_label_are_read_one_by_one(self):
        """A label cell printing 'Sign: ______ Date: ______' over an answer cell: read as words it was the date question
        'Sign Date', generated into the legacy row on f5fe720f."""
        for label in ('Sign: ______ Date: ______', 'Signature: ______ Date: ______',
                      'Reviewed by: ______    Nurse sign: ______'):
            with self.subTest(label=label):
                self.assertEqual(w.destination_state(label)['basis'], 'stacked_caption')
                row = next(v for k, v in self.roles(two_col([label, 'Plan'])).items() if k != 'Plan')
                self.assertEqual(row['state'], 'uncertain', label)
        for label in ('Date ______ Time ______', 'Patient signature obtained ______'):
            with self.subTest(control=label):
                self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)

    def test_an_abbreviation_period_does_not_hide_the_person(self):
        """'Dr. sign' read 'dr.' as no person and was generated on both engines' rows (f5fe720f and before this)."""
        for label in ('Dr. sign', 'Pt. sign', 'Dr.sign'):
            with self.subTest(label=label):
                self.assert_held_on_both(label, 'protected', 'person_sign')
        # the title awaits the signer's name: the signer's place, as on f5fe720f (roles-3, L1:R1-06)
        self.assertEqual(w.destination_state('Consent form signed by Dr.')['state'], 'protected')

    def test_an_agent_phrase_before_an_initial_and_joined_persons_before_signed(self):
        """'Checked by — Initial' (the earlier repair's must-hold list) was generated into the legacy row on f5fe720f
        and on every roles-2 commit before this one (f5fe720f's dash-qualifier release); contract v3 held it. The
        agent phrase closing on 'by' names whose initials they are. 'Parent/guardian signed' names persons joined."""
        for label in ('Checked by — Initial', 'Given by - initial'):
            with self.subTest(label=label):
                self.assert_held_on_both(label, 'protected', 'agent_initial')
        self.assert_held_on_both('Parent/guardian signed', 'protected', 'person_signed')
        for label in ('Troponin — Initial', 'Consent form signed'):
            with self.subTest(control=label):
                self.assert_generated_on_both(label)

    def test_a_bare_initial_beside_a_sequence_word_in_the_same_table_is_held(self):
        rows = self.roles(two_col(['Initial', 'Repeat', 'Plan']))
        self.assertEqual((rows['Initial']['state'], rows['Initial']['basis']), ('protected', 'bare_initial'))
        self.assertEqual(self.roles(two_col(['Initial', 'Plan']))['Initial']['state'], 'protected')


def legacy_roles_of(blob):
    """{label: legacy 'roles' row} from the legacy engine's inspection and roles operation of a DOCX or a PDF."""
    import tempfile
    from pathlib import Path
    from . import engine
    fmt = 'pdf' if blob[:4] == b'%PDF' else 'docx'
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp); (ws / ('input.' + fmt)).write_bytes(blob)
        found = engine.process(ws, {'operation': 'inspect', 'format': fmt, 'engine': 'legacy'})
        roles = engine.process(ws, {'operation': 'roles', 'format': fmt, 'engine': 'legacy', 'mapping': found['fields'],
                                    'answers': {}})
    return {f['label']: roles['legacy_roles'][f['key']] for f in found['fields']}


def legacy_tab_lines(*labels):
    """Legacy tab-form lines: each label's runs (its tabs kept) then an underlined answer tab."""
    doc = Document(); doc.add_paragraph('Examination')
    for text in labels + ('Plan:',):
        p = tabbed(doc.add_paragraph(), text + ' ')
        r = p.add_run(); r.underline = True; r._r.append(OxmlElement('w:tab'))
    return data(doc)


def grid(headers, rows, *, separate=False):
    """A bordered table with a header row (or, separate=True, one two-column table per row with no header)."""
    doc = Document(); doc.add_heading('Clinic record', level=2)
    if separate:
        for row in rows:
            table = doc.add_table(rows=1, cols=len(row)); table.style = 'Table Grid'
            for c, v in enumerate(row):
                table.cell(0, c).text = v
            doc.add_paragraph('')
    else:
        table = doc.add_table(rows=len(rows) + (1 if headers else 0), cols=len(headers or rows[0]))
        table.style = 'Table Grid'
        for c, h in enumerate(headers or ()):
            table.cell(0, c).text = h
        for r, row in enumerate(rows, start=1 if headers else 0):
            for c, v in enumerate(row):
                table.cell(r, c).text = v
    doc.add_paragraph('Plan: ______')
    return data(doc)


def pdf_named(names):
    """A fillable PDF whose text fields carry no tooltip: the engine labels each by its field name."""
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO(); c = canvas.Canvas(buffer); y = 780
    for name in names:
        c.acroForm.textfield(name=name, x=200, y=y - 8, width=300, height=22, fontName='Helvetica', fontSize=10)
        y -= 60
    c.showPage(); c.save(); return buffer.getvalue()


class RepairOf39bdb9f0(unittest.TestCase):
    """The refutation of 39bdb9f0 (L1:R1-01..R1-12, L2:R2-01..R2-06, L3:RF3-01..RF3-05). Each regression vs f5fe720f is
    repaired by restoring f5fe720f's reading for its input class - a release narrowed to its own evidence, or a release
    whose evidence kept failing (a bare 'Initial' beside its table's other labels, a unit printed elsewhere in the row)
    dropped. Each pre-existing leak is held with an ordinary positive control. Red on 39bdb9f0."""

    def assert_held(self, label, *, protected=False, **kw):
        reading = w.destination_state(label, **kw)
        self.assertNotEqual(reading['state'], 'ordinary', (label, reading))
        if protected:
            self.assertEqual(reading['state'], 'protected', (label, reading))
        self.assertTrue(w.legacy_role_kind(label, **{k: v for k, v in kw.items() if k == 'siblings'}), label)

    def assert_ordinary(self, label, **kw):
        reading = w.destination_state(label, **kw)
        self.assertEqual(reading['state'], 'ordinary', (label, reading))
        self.assertEqual(w.legacy_role_kind(label), '', label)

    def assert_v3(self, blob, held, generated_labels=('Plan',)):
        fields, rep = report(blob)
        by = by_label(fields)
        for label in held:
            self.assertFalse(generated(by[label], rep), (label, by[label]['kind']))
        for label in generated_labels:
            self.assertTrue(generated(by[label], rep), label)
            self.assertIn(SYN, xml(w.fill(blob, fields, {by[label]['key']: SYN})))
        return fields, rep

    def test_l1_r1_01_a_care_task_or_a_drug_before_initial_is_no_measurement(self):
        for label in ('Mouth care (initial)', 'Pressure area care (initial)', 'Insulin (initial)', 'Medication (initial)',
                      'Drug (initial)', 'Obs (initial)', 'Swab count (initial)', 'Catheter care (initial)',
                      'Care plan (initial)', 'Mouth care: initial', 'Insulin: initial', 'Mouth care — initial',
                      'Pressure area care — initial', 'Mouth care - initial'):
            with self.subTest(label=label):
                self.assert_held(label)
                self.assert_v3(lines(label + ': ______'), [label])
                self.assertNotEqual(legacy_roles_of(two_col([label, 'Plan']))[label]['state'], 'ordinary')
        for label in ('Troponin (initial)', 'Lactate (initial)', 'Dose (initial)', 'Hb (initial)', 'Weight — Initial',
                      'Pain score (initial)', 'Troponin: initial', 'Rate (initial)'):
            with self.subTest(control=label):
                self.assert_ordinary(label)

    def test_l1_r1_02_a_checking_ordinal_beside_initial_is_no_sequence_option(self):
        for label in ('Initial / 2nd check', 'Review / initial', 'Initial / Second', 'Initial/2nd', 'Initial or second check',
                      'Initial / final', 'Initial/review', 'Initial / last', 'Initial and final check'):
            with self.subTest(label=label):
                self.assert_held(label)
        self.assert_v3(lines('Initial / 2nd check: ______', 'Review / initial: ______'),
                       ['Initial / 2nd check', 'Review / initial'])
        for label in ('Initial / repeat', 'Visit type (initial/follow-up)', 'Initial or subsequent encounter',
                      'Troponin (0h / initial)', 'Encounter: initial / subsequent', 'Initial and final diagnosis',
                      'Initial & maintenance dose'):
            with self.subTest(control=label):
                self.assert_ordinary(label)

    def test_l1_r1_03_l3_rf3_01_a_bare_initial_is_held_whatever_its_neighbours(self):
        for siblings in ((), ('Diagnosis', 'Follow-up'), ('Follow-up:',), ('Baseline',), ('Day 1',), ('15 min',),
                         ('Repeat',), ('Repeat', 'Plan'), ('Observation', '0h', '4h'), ('2 weeks',)):
            for label in ('Initial', 'Initial:', 'Initial (witness)', 'Initial (nurse)', 'Initial (patient)',
                          'Initial (checker)', 'Initial (RN)', 'Initial (staff nurse)'):
                with self.subTest(label=label, siblings=siblings):
                    self.assert_held(label, protected=True, siblings=siblings)
        # both engines, the same table as a sequence word, and a one-row table printing it beside a timed reading
        for blob in (two_col(['Initial', 'Repeat', 'Plan']), two_col(['Repeat', 'Plan', 'Initial:']),
                     two_col(['Diagnosis', 'Follow-up', 'Initial'])):
            rows = legacy_roles_of(blob)
            initial = next(k for k in rows if k.startswith('Initial'))
            self.assertEqual(rows[initial]['state'], 'protected', initial)
            fields, rep = report(blob)
            self.assertFalse(any(generated(f, rep) for f in fields if f['label'].startswith('Initial')))
            self.assertTrue(all(generated(f, rep) for f in fields if not f['label'].startswith('Initial')))
        rows = legacy_roles_of(grid(None, [('15 min', '', 'Initial', '')]))
        self.assertEqual(rows['Initial']['state'], 'protected')
        rows = legacy_roles_of(legacy_tab_lines('Diagnosis:', 'Follow-up:', 'Initial:'))
        self.assertEqual(rows['Initial']['state'], 'protected')
        self.assertEqual(rows['Diagnosis']['state'], 'ordinary')

    def test_l3_rf3_02_the_legacy_reading_never_depends_on_object_identity(self):
        """Separate tables 'Repeat', 'Plan' and 'Initial:': the legacy reading grouped labels by id() of an lxml proxy,
        which Python reuses once a proxy is freed - so 'Initial:' read its neighbours from OTHER tables in 13 of 20 fresh
        interpreters. A colliding id is forced here; nothing structural may change the reading."""
        from unittest.mock import patch
        from . import engine
        blob = grid(None, [('Repeat', ''), ('Plan', ''), ('Initial:', '')], separate=True)
        with patch.object(engine, 'id', create=True, new=lambda obj: 1):
            rows = legacy_roles_of(blob)
        self.assertEqual(rows['Initial:']['state'], 'protected')
        self.assertEqual(legacy_roles_of(blob)['Initial:']['state'], 'protected')

    def test_l2_r2_05_l3_rf3_01_a_column_headed_initial_is_uncertain(self):
        """A column headed 'Initial' is each row's first reading in a lab table and each row's initials in an
        observations chart ('Observation | 0h | 4h | Initial'): never generated; f5fe720f held it from generation and let
        the clinician add a text field there, and so does an uncertain place."""
        for headers, row in ((('Observation', '0h', '4h', 'Initial'), ('BP', '', '', '')),
                             (('Measure', 'Initial', '3 months', '6 months'), ('HbA1c', '', '', '')),
                             (('Analyte', 'Initial', 'Repeat'), ('Troponin', '', ''))):
            with self.subTest(headers=headers):
                blob = grid(headers, [row])
                fields, rep = report(blob)
                cell = by_label(fields)[row[0] + ' — Initial']
                self.assertFalse(generated(cell, rep))
                self.assertIn(cell['key'], rep['uncertain_places'])
                ordinary = [f for f in fields if f['label'].startswith(row[0]) and f['key'] != cell['key']]
                self.assertTrue(ordinary and all(generated(f, rep) for f in ordinary))

    def test_l1_r1_04_a_unit_printed_elsewhere_in_the_row_or_column_is_no_evidence(self):
        for label in ('Second check (initial)', 'Checked (initial)', 'Given (initial)', 'Given — initial'):
            with self.subTest(label=label):
                self.assert_held(label, unit=True)
        fields, rep = report(grid(('Drug', 'Check', 'Value'), [('Morphine 5 mg IV', 'Second check (initial)', ''),
                                                                ('Insulin 6 units SC', 'Checked (initial)', '')]))
        for f in fields:
            if 'initial' in f['label'].casefold():
                self.assertFalse(generated(f, rep), f['label'])
        fields, rep = report(grid(('Item', 'Value (mg)'), [('Given (initial)', '')]))
        self.assertFalse(generated(by_label(fields)['Given (initial) — Value (mg)'], rep))
        # no unit is evidence, printed in the label either; a measured head is
        for label in ('Fibre initial (mg)', 'Insulin (initial) (units)', 'Second check (initial) (mg)'):
            with self.subTest(label=label):
                self.assert_held(label)
        for label in ('Troponin — Initial (ng/L)', 'Troponin (ng/L) — Initial', 'Dose (initial) (mg)'):
            with self.subTest(control=label):
                self.assert_ordinary(label)

    def test_l1_r1_05_a_day_or_night_person_signed_is_that_persons_signing_place(self):
        for label in ('Day nurse signed', 'Day nurse signed:', 'Day staff signed', 'Day surgeon signed', 'Day 1 nurse signed',
                      'Night nurse signed', 'Day nurse sign', 'Day nurse signs'):
            with self.subTest(label=label):
                self.assert_held(label, protected=True)
        self.assert_v3(lines('Day nurse signed: ______'), ['Day nurse signed'])
        for label in ('Time signed', 'Date signed', 'Time patient signed'):
            with self.subTest(control=label):
                self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)

    def test_l1_r1_06_a_title_awaiting_a_name_is_the_signers_identity(self):
        for label in ('Consent form signed by Dr.', 'Form signed by Dr', 'Prescription signed by Dr.',
                      'Letter signed by Mr'):
            with self.subTest(label=label):
                self.assert_held(label, protected=True)
        self.assert_v3(lines('Consent form signed by Dr. ______', 'Form signed by Dr ______ (name)'),
                       ['Consent form signed by Dr.', 'Form signed by Dr'])
        for label in ('Consent form signed by patient', 'Drug chart signed by prescriber', 'Consent signed by both parents',
                      'Prescription signed by pharmacist'):
            with self.subTest(control=label):
                self.assert_ordinary(label)

    def test_l1_r1_08_sign_naming_its_signer_is_the_signers_place(self):
        for label in ('Sign (patient)', 'Sign-off (consultant)', 'Sign (witness)', 'Sign (Dr)', 'Sign (consultant)',
                      'Sign - patient', 'Sign: patient', 'Sign by consultant', 'Sign for patient', 'Sign off (consultant)'):
            with self.subTest(label=label):
                self.assert_held(label, protected=True)
                self.assertNotEqual(legacy_roles_of(two_col([label, 'Plan']))[label]['state'], 'ordinary')
        self.assert_v3(lines('Sign (patient): ______', 'Sign-off (consultant): ______'),
                       ['Sign (patient)', 'Sign-off (consultant)'])
        for label in ('Babinski sign', 'Sign of infection', 'Signs of sepsis', 'Sign (positive)',
                      'Sign language interpreter', 'Sign out nurse'):
            with self.subTest(control=label):
                self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)

    def test_l1_r1_09_persons_joined_or_qualified_before_sign_are_the_signers(self):
        for label in ('Parent/guardian sign', 'Patient or carer sign', 'Nurse / midwife sign', 'Doctor/nurse sign',
                      'Nurse & doctor sign', 'Doc sign', 'Anaes sign', 'Day nurse sign', 'Parent/guardian signed',
                      'Nurse sign'):
            with self.subTest(label=label):
                self.assert_held(label, protected=True)
                self.assertNotEqual(legacy_roles_of(two_col([label, 'Plan']))[label]['state'], 'ordinary')
        for label in ('Babinski sign', "Murphy's sign", 'Kernig sign', "Trousseau's sign"):
            with self.subTest(control=label):
                self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)

    def test_l1_r1_10_a_signing_place_joined_to_its_date_is_one_place(self):
        for label in ('Signature of patient, date', 'Signature of witness – Date', 'Signature (patient), date',
                      'Signature of person obtaining consent, date', 'Signature of interpreter - date',
                      'Initials of nurse, date', 'Patient signature (date)', 'Sign below and date', 'Initial(s) / date',
                      'Signature, date'):
            with self.subTest(label=label):
                self.assert_held(label, protected=True)
                self.assertNotEqual(legacy_roles_of(two_col([label, 'Plan']))[label]['state'], 'ordinary')
        self.assert_held('Signature of patient' + ' ' * 20 + 'Date')
        self.assert_held('Signature of patient\tDate')
        self.assert_v3(lines('Signature of patient, date: ______', 'Initials of nurse, date: ______'),
                       ['Signature of patient, date', 'Initials of nurse, date'])
        for label in ('Date of signature', 'Signature date', 'Date signed', 'Consent form signed, date',
                      'Patient signature obtained, date', 'Date and time signed'):
            with self.subTest(control=label):
                self.assertEqual(w.destination_state(label)['state'], 'ordinary', label)

    def test_l1_r1_11_a_pdf_field_named_as_a_signing_place(self):
        rows = legacy_roles_of(pdf_named(['PatientName', 'PatientSignature', 'Initials_2', 'Signature1', 'Plan']))
        for name in ('PatientSignature', 'Initials_2', 'Signature1'):
            with self.subTest(name=name):
                self.assertEqual(rows[name]['state'], 'protected', rows[name])
        for name in ('PatientName', 'Plan'):
            with self.subTest(control=name):
                self.assertEqual(rows[name]['state'], 'ordinary', rows[name])

    def test_l1_r1_12_a_caption_printed_after_or_under_the_line(self):
        fields, rep = self.assert_v3(lines('Patient: ______ (signature)', 'Witness: ______ (sign)'), ['Patient', 'Witness'])
        doc = Document(); doc.add_heading('Consent record', level=2)
        doc.add_paragraph(LINE); doc.add_paragraph('Sign (patient)')
        doc.add_paragraph(''); doc.add_paragraph('Diagnosis: ______')
        doc.add_paragraph(LINE); doc.add_paragraph('Parent/guardian sign')
        doc.add_paragraph('Plan: ______')
        blob = data(doc)
        fields, rep = report(blob)
        lined = [f for f in fields if f['label'] not in ('Diagnosis', 'Plan')]
        self.assertTrue(all(not generated(f, rep) for f in lined), [(f['label'], f['kind']) for f in lined])
        self.assertTrue(all(generated(f, rep) for f in fields if f['label'] in ('Diagnosis', 'Plan')))
        # a hint in parentheses after the line is no signing caption
        self.assert_v3(lines('Diagnosis: ______ (if known)'), [], ['Diagnosis', 'Plan'])

    def test_l2_r2_01_initial_before_a_persons_assessment_is_attributive(self):
        for label in ('Initial nursing assessment', 'Initial patient assessment', 'Initial patient observations',
                      'Initial doctor review', 'Initial consultant review', 'Initial patient weight', 'Initial patient GCS',
                      'Initial PA chest X-ray', 'Initial physio assessment'):
            with self.subTest(label=label):
                self.assert_ordinary(label)
                self.assertEqual(legacy_roles_of(two_col([label, 'Plan']))[label]['state'], 'ordinary')
        for label in ('Initial nurse', 'Initial (nurse)', 'Initial staff'):
            with self.subTest(held=label):
                self.assert_held(label)

    def test_l2_r2_02_a_persons_measurement_before_initial_is_a_measurement(self):
        for label in ('Patient weight — Initial', 'Patient temperature — Initial', 'Patient GCS — Initial',
                      'Patient BP – initial', 'PT/INR — Initial', 'PA pressure — Initial', "Mother's weight — Initial",
                      'Donor Hb — Initial', 'Pt lactate — initial'):
            with self.subTest(label=label):
                self.assert_ordinary(label)
                self.assertEqual(legacy_roles_of(two_col([label, 'Plan']))[label]['state'], 'ordinary')
        for label in ('PT — Initial', 'Nurse — Initial', 'Charge nurse — Initial', 'Checked by nurse — Initial',
                      'Nurse (RN) — initial', 'Given (nurse) — initial'):
            with self.subTest(held=label):
                self.assert_held(label, protected=True)

    def test_l2_r2_04_initial_before_a_noun_phrase_that_is_no_edit_object(self):
        for label in ('Initial line of treatment', 'Initial line of therapy', 'Initial changes on ECG',
                      'Initial changes on CXR', 'Initial forms of presentation', 'Initial entry wound',
                      'Initial additions to treatment'):
            with self.subTest(label=label):
                self.assert_ordinary(label)
        for label in ('Initial changes', 'Initial each page', 'Initial changes here', 'Initial all entries'):
            with self.subTest(held=label):
                self.assert_held(label, protected=True)

    def test_l2_r2_06_one_caption_wrapped_is_read_whole_where_the_whole_has_evidence(self):
        for label, parts in (('Initial assessment', ['Initial', 'assessment']),
                             ('Consent form signed?', ['Consent form', 'signed?']),
                             ('Lactate (initial)', ['Lactate', '(initial)'])):
            with self.subTest(label=label):
                self.assertEqual(w.destination_state(label, lines=parts)['state'], 'ordinary')
                self.assertEqual(legacy_roles_of(two_col(['|'.join(parts), 'Plan']))[''.join(parts)]['state'], 'ordinary')
        # two captions stacked stay uncertain; a label with no evidence keeps the stacked reading (declared)
        for label, parts in (('Signature date', ['Signature', 'Date']), ('Babinski sign', ['Babinski', 'sign'])):
            with self.subTest(held=label):
                self.assertEqual(w.destination_state(label, lines=parts)['state'], 'uncertain')

    def test_l3_rf3_05_tab_separated_captions_on_a_legacy_tab_line_are_read_one_by_one(self):
        rows = legacy_tab_lines('Patient signature\t\tDate:', 'Date\tSignature:', 'Consultant signature\tDate signed:',
                                'Witness\tInitial:')
        roles = legacy_roles_of(rows)
        for label, row in roles.items():
            with self.subTest(label=label):
                if label == 'Plan':
                    self.assertEqual(row['state'], 'ordinary')
                else:
                    self.assertNotEqual(row['state'], 'ordinary', (label, row))
                    self.assertIn(' ', row['printed_label'], row)          # its captions, not the joined runs
        controls = legacy_roles_of(legacy_tab_lines('Date\tTime:', 'Consent form signed by patient:'))
        self.assertTrue(all(row['state'] == 'ordinary' for row in controls.values()), controls)
        fields, rep = report(lines('Date\tSignature: ______'))
        self.assertFalse(generated(fields[0], rep), fields[0])

    def test_l1_r1_07_a_person_column_over_an_initial_row_is_that_persons_initials(self):
        fields, rep = report(grid(('Observation', 'Nurse', 'Doctor'), [('BP (initial)', '', '')]))
        for f in fields:
            if f['label'].startswith('BP'):
                self.assertFalse(generated(f, rep), f['label'])
        fields, rep = report(grid(('Observation', 'Nurse', 'Doctor'), [('BP', '', '')]))
        self.assertTrue(all(generated(f, rep) for f in fields if f['label'].startswith('BP')))


class Versioned(unittest.TestCase):
    def test_the_report_names_its_reading(self):
        blob = lines('Name: ______')
        self.assertEqual(w.destination_roles(blob, w.inspect(blob)['fields'])['reading'], w.ROLE_READING)
        self.assertEqual(w.legacy_destination('Name')['reading'], w.ROLE_READING)


if __name__ == '__main__':
    unittest.main()
