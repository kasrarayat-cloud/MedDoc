"""Two hold-only relation floors (2026-10-02), on the ordinary field-relations path, through the v4 wire with the worst
relations a model can send (every unit it does not select 'independent': `relation_wire`).

SUPERSESSION (refutation finding RV4H-2, docs/rebuild/v1/standing-campaign/relations-v4-refutation-20261002.md). The
cessation floor read 'stopped' and 'no longer takes', and nothing else ended an answer: with the model calling the next
sentence independent, 'The patient takes warfarin 5 mg daily.' was ADOPTED as the Medications answer beside 'Warfarin has
been switched to apixaban.', '... was replaced by apixaban', '... was changed to apixaban', '... is on hold for surgery'
and '... was withheld today'. A statement that switches, replaces, substitutes, swaps, changes to, withholds or puts on
hold a thing now ENDS that thing for the floors exactly as a cessation does (`v3_actors._superseded`, `_on_hold`): the
answer claiming it is held and shown with that line, a supersession naming nothing leans on another line (a bare
cessation), and it never releases anything.

A CONJOINED CESSATION STILL NAMES NOTHING (withdrawn 2026-10-02 after refutation RS-1 to RS-5 and F-AGENT-RELEASE).
54fb4e74 let a conjunct with no subject end its head's ('The scope was advanced to the terminal ileum and withdrawn
slowly.' ended 'scope'); that RELEASED a stopped medication as current ('Haematology reviewed and stopped.', 'Her INR
was checked and stopped.'). Every conjunct reads as on ab58c98f, and D02's description line holds every other answer on
the v3 relations path again: a declared residual. No provider, no network, no database."""
import json
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_actors as a, v3_field_relations as r
from .test_v3_field_relations import relation_wire
from .test_v3_field_relations_contract import RELATIONS
from .test_v3_ordinary_notes import LIVE, field

#: The candidate's claude-sonnet-5-5 default: the field-relations contract taken with the switch unset.
SONNET_55_DEFAULT = dict(LIVE, AI_MODEL=g.SONNET_5_5, V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_SWITCH=None,
                         V3_HISTORY_CONTEXT=False, V3_GENERATION_BATCHES=False)
WARFARIN = 'The patient takes warfarin 5 mg daily.'
#: RV4H-2's inputs: each ADOPTED the warfarin sentence on ab58c98f with the model calling it independent.
SUPERSEDING = ('Warfarin has been switched to apixaban.', 'Warfarin was replaced by apixaban last month.',
               'The warfarin was changed to apixaban.', 'The warfarin is on hold for surgery.',
               'Warfarin was withheld today.')
#: The other shapes the parse reads: an old-value preposition, a substitute's 'for', a swap, an active replacer, an
#: imperative hold, a verbless 'on hold', a reduced passive, a participle the tagger calls a proper noun (bare), and a
#: supersession naming nothing but a pronoun (bare).
SHAPES = ('The patient was switched from warfarin to apixaban.', 'Apixaban was substituted for warfarin.',
          'Warfarin was swapped for apixaban.', 'Apixaban replaced warfarin.', 'Hold warfarin for five days.',
          'Warfarin on hold.', 'Warfarin withheld.', 'Warfarin held for surgery.', 'The warfarin was changed over to '
          'apixaban.', 'The nurse held the warfarin.', 'We held warfarin today.', 'Withheld today.',
          'She was switched to apixaban.', 'Switched to apixaban.')


def form(*labels):
    return [field(f'f{i}', label, 'long_text') for i, label in enumerate(labels, 1)]


def raw(notes, fields, body, model):
    asked, context, _ = g.v3_generation_fields(fields)
    return {'anthropic_response': SimpleNamespace(model=model, stop_reason='end_turn',
                                                  content=[SimpleNamespace(type='text', text=json.dumps(body))]),
            'ordinary_field_contract': r.CONTRACT, 'notes': notes, 'fields': asked, 'full_catalogue': fields,
            'context_labels': context, 'requested_model': model}


class Worst:
    """The whole reader (parse -> records -> validate_selections -> v3_adopted) on the worst wire, and a stored supported
    copy read by the page, save and finalization."""
    model = g.SONNET_5

    def answers(self, notes, fields, picks):
        keyed = {next(f['key'] for f in fields if f['label'] == label): quotes for label, quotes in picks.items()}
        return r.validated(raw(notes, fields, relation_wire(notes, fields, keyed), self.model))

    def assert_held(self, notes, labels, label, pick, shown=None):
        fields = form(*labels)
        key = next(f['key'] for f in fields if f['label'] == label)
        answer = self.answers(notes, fields, {label: [pick]})[key]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), (notes, answer))
        if shown is not None:
            # the page shows the line that holds it
            self.assertIn(shown, [c['quote'] for c in answer['held_candidate']['context']], notes)
        stored = {k: v for k, v in answer.items() if k != 'held_candidate'}
        start = notes.index(pick)
        stored.update(status='supported', text=pick, evidence=[{'quote': pick, 'start': start, 'end': start + len(pick)}])
        self.assertEqual(g.governed_decisions(notes, fields, {key: stored}), [label], notes)
        field_of = next(f for f in fields if f['key'] == key)
        row = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field_of, **stored})
        self.assertEqual((row['status'], row['text']), ('conflict', ''), notes)

    def assert_cases_held(self, cases, label='Medications'):
        for answer, tail in cases:
            joiner = '' if tail.startswith('\n') else ' '
            for notes in (answer + joiner + tail, tail.lstrip('\n') + ('\n' if joiner == '' else ' ') + answer):
                with self.subTest(notes=notes):
                    self.assert_held(notes, (label, 'Plan'), label, answer, shown=tail.lstrip('\n'))

    def assert_adopted(self, notes, labels, label, pick):
        fields = form(*labels)
        key = next(f['key'] for f in fields if f['label'] == label)
        answers = self.answers(notes, fields, {label: [pick]})
        # (a line labelled with its own question answers with its value)
        text = pick.split(':', 1)[1].strip() if pick.startswith(label + ':') else pick
        self.assertEqual((answers[key]['status'], answers[key]['text']), ('supported', text), (notes, answers[key]))
        self.assertEqual(g.governed_decisions(notes, fields, {key: answers[key]}), [], notes)
        field_of = next(f for f in fields if f['key'] == key)
        row = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field_of, **answers[key]})
        self.assertEqual((row['status'], row['text']), ('supported', text), notes)


class SupersessionFloor(Worst):
    def test_rv4h_2_a_supersession_holds_what_it_supersedes_whatever_the_model_says(self):
        for tail in SUPERSEDING:
            for notes in (WARFARIN + ' ' + tail, tail + ' ' + WARFARIN,
                          # with a spoken heading, and the answer under it
                          'Medications. ' + WARFARIN + ' ' + tail + ' Plan. The patient will return in a week.'):
                with self.subTest(notes=notes):
                    self.assert_held(notes, ('Medications', 'Plan'), 'Medications', WARFARIN)
            # shown with the line that supersedes it
            with self.subTest(shown=tail):
                self.assert_held(WARFARIN + ' ' + tail, ('Medications', 'Plan'), 'Medications', WARFARIN, shown=tail)

    def test_every_shape_the_parse_reads_holds_the_superseded_answer(self):
        for tail in SHAPES:
            with self.subTest(tail=tail):
                self.assert_held(WARFARIN + ' ' + tail, ('Medications', 'Plan'), 'Medications', WARFARIN, shown=tail)
        # a labelled plan line supersedes the medication answer too
        self.assert_held(WARFARIN + '\nPlan: switch warfarin to apixaban.', ('Medications', 'Plan'), 'Medications',
                         WARFARIN, shown='Plan: switch warfarin to apixaban.')

    def test_a_supersession_ends_only_what_it_supersedes(self):
        # what replaced it is not ended: 'switched from aspirin' ends aspirin, not warfarin
        self.assert_adopted(WARFARIN + ' Warfarin was switched from aspirin.', ('Medications', 'Plan'), 'Medications',
                            WARFARIN)
        self.assert_held('The patient takes aspirin. Warfarin was switched from aspirin.', ('Medications', 'Plan'),
                         'Medications', 'The patient takes aspirin.', shown='Warfarin was switched from aspirin.')
        for tail in ('Warfarin has been switched to apixaban.', 'Warfarin was replaced by apixaban.',
                     'Apixaban was substituted for warfarin.', 'Warfarin was swapped for apixaban.',
                     'Apixaban replaced warfarin.'):
            with self.subTest(tail=tail):
                self.assert_adopted('The patient takes apixaban. ' + tail, ('Medications', 'Plan'), 'Medications',
                                    'The patient takes apixaban.')
        # an unrelated thing superseded leaves the answer to the model, as before
        self.assert_adopted(WARFARIN + ' Aspirin was switched to clopidogrel.', ('Medications', 'Plan'), 'Medications',
                            WARFARIN)

    def test_change_is_read_only_as_a_change_to_or_from(self):
        for tail in ('Dressing changed daily.', 'There is no change in symptoms.', 'Her symptoms have changed.',
                     'No changes were made.', 'She switches between two inhalers.', 'The patient held her breath.',
                     'The light was switched on.'):
            with self.subTest(tail=tail):
                self.assert_adopted(WARFARIN + ' ' + tail, ('Medications', 'Plan'), 'Medications', WARFARIN)
        # a switch that starts something ends nothing
        self.assert_adopted('The patient uses a CPAP machine at night. The CPAP machine was switched on.',
                            ('Sleep', 'Plan'), 'Sleep', 'The patient uses a CPAP machine at night.')
        # ... and 'changed daily' does not end the thing it changes either: the dressing answer stays the model's
        self.assert_adopted('The patient has a dressing on the left shin. Dressing changed daily.',
                            ('Wound care', 'Plan'), 'Wound care', 'The patient has a dressing on the left shin.')
        # while 'changed to' does
        self.assert_held('The patient has a dressing on the left shin. The dressing was changed to a hydrocolloid.',
                         ('Wound care', 'Plan'), 'Wound care', 'The patient has a dressing on the left shin.')

    def test_a_supersession_never_releases(self):
        # a bare cessation stays bare beside a supersession naming something
        for notes in ('The patient attends the clinic every week. She stopped and was switched from warfarin.',
                      'The patient attends the clinic every week. The patient quit. Warfarin was switched to apixaban.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, ('Clinic attendance', 'Plan'), 'Clinic attendance',
                                 'The patient attends the clinic every week.')
        # and a cessation still ends what it ends
        self.assert_held(WARFARIN + ' Warfarin was stopped and apixaban was started.', ('Medications', 'Plan'),
                         'Medications', WARFARIN)

    def test_a_supersession_naming_nothing_leans_on_another_line(self):
        for tail in ('She was switched to apixaban.', 'Withheld today.', 'Switched to apixaban.'):
            with self.subTest(tail=tail):
                self.assert_held('The patient attends the clinic every week. ' + tail, ('Clinic attendance', 'Plan'),
                                 'Clinic attendance', 'The patient attends the clinic every week.', shown=tail)
        # (a hold naming nothing is not one: 'held overnight' says nothing it ended)
        self.assert_adopted('The patient attends the clinic every week. The patient was held overnight for observation.',
                            ('Clinic attendance', 'Plan'), 'Clinic attendance',
                            'The patient attends the clinic every week.')

    def test_rsl_1_fronted_imperatives_and_gerunds_the_tagger_reads_as_nouns(self):
        # (refutation RSL-1, F-UNLISTED-MISSES) the verb tagged a noun or proper noun before the drug it supersedes
        self.assert_cases_held((
            ('The patient takes gliclazide 80 mg twice daily.', 'Switch gliclazide to insulin.'),
            ('The patient takes metformin 500 mg twice daily.', 'Withhold metformin.'),
            ('The patient takes sertraline 50 mg daily.', 'Substitute citalopram for sertraline.'),
            (WARFARIN, 'HOLD WARFARIN.'), (WARFARIN, 'SWITCH WARFARIN TO APIXABAN.'),
            (WARFARIN, 'Withholding warfarin for 5 days.'), (WARFARIN, 'Withholding warfarin today.'),
            (WARFARIN, 'Substitute apixaban for warfarin.'),
            ('Medications: bisoprolol 5 mg daily.', '\nPlan: switch bisoprolol to atenolol.'),
            ('Medications: warfarin 5 mg daily.', '\nPlan: Withholding warfarin.')))
        # ... and only the drug it supersedes: the replacement a fronted verb names is not ended
        self.assert_adopted('The patient takes insulin at night. Switch gliclazide to insulin.', ('Medications', 'Plan'),
                            'Medications', 'The patient takes insulin at night.')
        self.assert_adopted('The patient takes citalopram 20 mg daily. Substitute citalopram for sertraline.',
                            ('Medications', 'Plan'), 'Medications', 'The patient takes citalopram 20 mg daily.')

    def test_rsl_2_fragments_whose_verb_hangs_on_what_it_supersedes(self):
        self.assert_cases_held((
            (WARFARIN, 'Held warfarin.'), ('The patient takes amlodipine 5 mg daily.', 'Holding amlodipine.'),
            ('The patient takes bisoprolol 5 mg daily.', 'Hold bisoprolol.'), (WARFARIN, 'WARFARIN HELD.'),
            (WARFARIN, 'Warfarin: held for surgery.'), (WARFARIN, 'Warfarin: held.'), (WARFARIN, 'Warfarin (held).'),
            ('Medications: metformin 500 mg twice daily.', '\nPlan: Held metformin.'),
            ('The patient takes clopidogrel 75 mg daily.', 'Changed clopidogrel to ticagrelor.')))

    def test_rsl_3_a_present_tense_replacer_is_not_what_it_replaces(self):
        self.assert_cases_held((
            (WARFARIN, 'Apixaban replaces warfarin.'),
            ('The patient takes atenolol 50 mg daily.', 'Bisoprolol replaces atenolol.'),
            ('The patient takes omeprazole 20 mg daily.', 'Lansoprazole now replaces omeprazole.'),
            ('Medications: warfarin 5 mg daily.', '\nPlan: Apixaban replaces warfarin.')))
        # the replacer stays the model's
        for tail in ('Apixaban replaces warfarin.', 'The cardiologist replaces warfarin with apixaban.'):
            with self.subTest(tail=tail):
                self.assert_adopted('The patient is on apixaban. ' + tail, ('Medications', 'Plan'), 'Medications',
                                    'The patient is on apixaban.')

    def test_rsl_4_an_answer_naming_the_superseded_drug_anywhere_in_it(self):
        # (the answer-side reader had dropped a drug tagged as an adverb or compound, a third list item, upper case)
        switched = 'Warfarin has been switched to apixaban.'
        self.assert_cases_held((
            ('The patient takes apixaban 5 mg twice daily.', 'Apixaban has been switched to warfarin.'),
            ('The patient takes apixaban 5 mg twice daily.', 'Apixaban was replaced by warfarin.'),
            ('The patient takes apixaban 5 mg twice daily.', 'Apixaban was withheld today.'),
            ('The patient takes apixaban 5 mg twice daily.', 'Apixaban is on hold for surgery.'),
            ('The patient takes metformin, ramipril and warfarin.', switched),
            ('The patient takes metformin 500 mg twice daily, ramipril 10 mg daily and warfarin 5 mg daily.', switched),
            ('The patient is on metformin, ramipril and warfarin.', switched),
            ('The patient takes WARFARIN 5 MG DAILY.', switched), ('The patient takes 5 mg of warfarin daily.', switched),
            ('The patient takes omeprazole 20 mg daily.', 'Omeprazole has been switched to lansoprazole.'),
            # the cessation it shares the arm with (adopted on ab58c98f too)
            ('The patient takes apixaban 5 mg twice daily.', 'Apixaban was stopped.')))
        self.assert_adopted('The patient takes apixaban 5 mg twice daily. ' + switched, ('Medications', 'Plan'),
                            'Medications', 'The patient takes apixaban 5 mg twice daily.')

    def test_each_verb_form_and_old_value_preposition_is_pinned(self):
        # (refutation F01-F07, F09, F10: each mutant survived the suite)
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            'Warfarin was switched on Monday to apixaban.', 'The GP replaces warfarin with apixaban.',
            'Replace warfarin with apixaban.', 'We will replace warfarin with apixaban.',
            'Please withhold the warfarin tonight.', 'Withhold warfarin today.', 'Change warfarin to apixaban.',
            'Please change warfarin to apixaban.', 'Please swap warfarin for apixaban.', 'The GP swaps warfarin for apixaban.',
            'We will substitute apixaban for warfarin.', 'The GP substitutes apixaban for warfarin.',
            'Her anticoagulant was changed from warfarin to apixaban.',
            'Her anticoagulant was swapped from warfarin to apixaban.')))

    def test_bare_and_keyed_readings_are_pinned(self):
        clinic = 'The patient attends the clinic every week.'
        # (F02) a later supersession that cannot be bare does not cancel an earlier bare one
        self.assert_held(clinic + ' She was switched to apixaban and the patient was held overnight.',
                         ('Clinic attendance', 'Plan'), 'Clinic attendance', clinic)
        # (F16, F17) 'on hold' after a noun ends that noun only; swapping 'between' ends nothing
        for tail in ('Warfarin on hold.', 'She swaps between two inhalers.'):
            with self.subTest(tail=tail):
                self.assert_adopted(clinic + ' ' + tail, ('Clinic attendance', 'Plan'), 'Clinic attendance', clinic)

    def test_a_supersession_conjunct_shares_no_subject(self):
        # (the withdrawal holds for supersessions too: what a conjunct superseded is never read from its head's subject)
        self.assert_cases_held(((WARFARIN, 'The dose was reviewed and switched to apixaban.'),
                                (WARFARIN, 'Her INR was checked and withheld.'),
                                ('Medications: warfarin 5 mg daily.', '\nPlan: INR was 6.2 and withheld.')))

    def test_an_agent_switching_names_nothing_it_ended(self):
        # A person subject of an active supersession is its agent, never its theme: what it ended is unnamed (bare).
        self.assert_cases_held(((WARFARIN, 'The cardiologist switched to apixaban.'),
                                (WARFARIN, 'We switched to apixaban.'), (WARFARIN, 'Haematology switched to apixaban.'),
                                (WARFARIN, 'The endoscopist switched to apixaban.'),
                                (WARFARIN, 'The pharmacy switched to apixaban.')))

    def test_o2_o10_an_old_value_under_the_replacement_and_a_conjunct_own_object(self):
        # (refutation O2) 'to' read as an infinitive marker hangs 'from' under the replacement: still the old value
        for notes, label, answer in (
                ('The patient attends the anticoagulation clinic every week. The patient was switched to apixaban from '
                 'warfarin.', 'Clinic attendance', 'The patient attends the anticoagulation clinic every week.'),
                ('Oxygen: 2 L/min via nasal cannula.\nShe was switched to nasal cannula from a face mask overnight.',
                 'Oxygen', 'Oxygen: 2 L/min via nasal cannula.'),
                # (O10) a conjunct with its own object ends that object, not the head's subject
                ('Registrar: Dr Example Synthetic\nThe registrar was called and discontinued the heparin infusion.',
                 'Registrar', 'Registrar: Dr Example Synthetic')):
            with self.subTest(notes=notes):
                self.assert_adopted(notes, (label, 'Plan'), label, answer)
        self.assert_held(WARFARIN + ' The patient was switched to apixaban from warfarin.', ('Medications', 'Plan'),
                         'Medications', WARFARIN)


class RoundTwoRepairs(Worst):
    """Round-2 refutation of e3a77077 (refute-sup-r2/result.json): coverage gaps the base adopts too, each closed as a
    HOLD by `v3_actors._superseded_repaired`, read BESIDE e3a77077's reading and united with it (nothing it held is
    released), and by the answer side ('named_keys')."""
    APIXABAN = 'The patient takes apixaban 5 mg twice daily.'

    def test_r2r_h1_a_clinician_the_parser_hangs_the_verb_on_is_its_agent(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            'The haematologist withheld today.', 'The cardiologist withheld today.',
            'The anaesthetist withheld before the procedure.', 'The anaesthetist held for surgery.')))

    def test_r2r_p1_pending_names_the_condition_not_what_is_held(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            'Warfarin held pending surgery.', 'Warfarin withheld pending review.', 'Warfarin withheld pending colonoscopy.',
            'Warfarin withheld pending INR result.', 'Withheld pending review.',
            'The cardiologist withheld pending review.')) + (
            (self.APIXABAN, 'Apixaban held pending surgery.'), (self.APIXABAN, 'Apixaban withheld pending colonoscopy.'),
            ('Medications: warfarin 5 mg daily.', '\nPlan: Warfarin held pending surgery.')))

    def test_c_rsl4_an_answer_naming_its_drug_as_an_adverb_or_a_dosage_form(self):
        self.assert_cases_held((
            ('The patient takes apixaban twice daily.', 'Apixaban was stopped.'),
            ('The patient takes apixaban twice daily.', 'Apixaban has been switched to warfarin.'),
            ('The patient takes apixaban twice daily.', 'Held apixaban.'),
            ('The patient takes apixaban daily.', 'Apixaban was stopped.'),
            ('The patient takes apixaban 5 mg tablets twice daily.', 'Apixaban was stopped.'),
            ('The patient takes edoxaban daily.', 'Hold edoxaban.'),
            ('The patient takes amlodipine daily.', 'Amlodipine was stopped.'),
            ('The patient takes apixaban at night.', 'Apixaban has been switched to warfarin.')))
        self.assert_adopted('The patient takes apixaban twice daily. Warfarin was stopped.', ('Medications', 'Plan'),
                            'Medications', 'The patient takes apixaban twice daily.')

    def test_c_rsl3_an_upper_or_title_case_replacer(self):
        self.assert_cases_held((
            (WARFARIN, 'APIXABAN REPLACES WARFARIN.'), (WARFARIN, 'Apixaban Replaces Warfarin.'),
            (WARFARIN, 'APIXABAN NOW REPLACES WARFARIN.'),
            ('The patient takes atenolol 50 mg daily.', 'BISOPROLOL REPLACES ATENOLOL.'),
            ('The patient takes omeprazole 20 mg daily.', 'LANSOPRAZOLE NOW REPLACES OMEPRAZOLE.')))
        self.assert_adopted('The patient is on apixaban. APIXABAN REPLACES WARFARIN.', ('Medications', 'Plan'),
                            'Medications', 'The patient is on apixaban.')

    def test_c_rsl2_an_upper_case_dose_held(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            'WARFARIN 5 MG HELD.', 'WARFARIN 5 MG OD HELD.', 'WARFARIN 5 MG DAILY HELD.', 'WARFARIN HELD X 5 DAYS.')) + (
            ('The patient takes amlodipine 5 mg daily.', 'AMLODIPINE 5 MG HELD.'),))

    def test_sup2f_1_a_subject_keeps_its_own_prepositional_phrase(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            'Anticoagulation with warfarin was switched to apixaban.',
            'Her anticoagulation with warfarin has been held for surgery.',
            'Treatment with warfarin was changed to apixaban.',
            'The prescription for warfarin was changed to apixaban.')) + (
            ('The patient takes methotrexate 15 mg weekly.', 'Therapy with methotrexate was withheld.'),))

    def test_sup2f_2_a_date_is_not_an_old_value(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            'Warfarin was switched to apixaban from Monday.', 'Warfarin was changed to apixaban from next week.',
            'Warfarin was switched over to apixaban from Monday.', 'Warfarin switches to apixaban from Monday.')) + (
            ('The patient takes atenolol 50 mg daily.', 'Atenolol switches to bisoprolol from Monday.'),))

    def test_sup2f_3_a_present_form_acts_on_its_subject_unless_it_replaces(self):
        self.assert_cases_held((
            ('The patient takes clopidogrel 75 mg daily.', 'Clopidogrel hold for 7 days before surgery.'),
            ('The patient takes lithium 400 mg nightly.', 'Lithium hold until levels back.'),
            ('The patient takes aspirin 75 mg and clopidogrel 75 mg daily.', 'Aspirin and clopidogrel hold for 7 days.'),
            ('Medications: apixaban 5 mg twice daily.', '\nPlan: Apixaban hold for 48 hours before surgery.'),
            # (SUP2F-M3: a replacement read as an open complement)
            ('The patient takes atenolol 50 mg daily.', 'Atenolol changes to bisoprolol.')))

    def test_lows_agents_labels_particles_possessives_and_old_values(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            # R2R-A1: an agent held, nothing it held is named
            'The cardiologist held.', 'Haematology held.', 'The anaesthetist held.', 'We held.', 'The surgical team held.',
            # C-RSL1: a drug label then an imperative
            'HOLD: WARFARIN.',
            # C-AGENT-SHAPE-MISSES, SUP2F-4
            'The SHO switched to apixaban.', 'The prescriber switched to apixaban.', 'The care home switched to apixaban.',
            'The SHO changed to apixaban.', 'The care home swapped to apixaban.', 'Paediatrics switched to apixaban.',
            'Orthopaedics switched to apixaban.',
            # C-POSSESSIVE
            'Held patient\u2019s warfarin.')) + (
            ('The patient takes metformin 500 mg twice daily.', 'Metformin: withhold.'),
            ('The patient takes metformin 500 mg twice daily.', 'Metformin - withhold.'),
            # C-CHANGED-OVER
            ('The patient takes clopidogrel 75 mg daily.', 'Changed clopidogrel over to ticagrelor.'),
            # SUP2F-5: the old value under 'onto'
            ('The patient takes atenolol 50 mg daily.', 'She was changed onto bisoprolol from atenolol.')))

    def test_a_named_supersession_holds_only_what_it_names(self):
        # (mutants P06, P13, P14 survived the holds above: each turns these named readings bare, holding every answer)
        clinic = 'The patient attends the clinic every week.'
        for tail in ('Clopidogrel hold for 7 days before surgery.', 'She was changed onto bisoprolol from atenolol.'):
            with self.subTest(tail=tail):
                self.assert_adopted(clinic + ' ' + tail, ('Clinic attendance', 'Plan'), 'Clinic attendance', clinic)
        # and 'changed onto' with no old value names nothing it ended
        self.assert_cases_held((('The patient takes atenolol 50 mg daily.', 'She was changed onto bisoprolol.'),))

    def test_m1_to_m5_each_arm_of_the_agent_and_bare_readings_is_pinned(self):
        self.assert_cases_held(tuple((WARFARIN, tail) for tail in (
            # M1: names_carer, names_person, AGENT_NOUNS, the -ian ending
            'The nurse switched to apixaban.', 'The registrar switched to apixaban.',
            'The consultant switched to apixaban.', 'The team switched to apixaban.',
            'The ward switched to apixaban.', 'The MDT switched to apixaban.', 'The practice switched to apixaban.',
            'The anticoagulation service switched to apixaban.', 'The hospital switched to apixaban.',
            'The obstetrician switched to apixaban.', 'The geriatrician switched to apixaban.',
            # M2: the explicit patient switched names nothing it ended
            'The patient was switched to apixaban.', 'The patient has been changed to apixaban.',
            # M5: a pronoun withheld names nothing it ended
            'They were withheld before surgery.')) + (
            # M4: a drug the tagger reads as a verb in apposition
            ('The patient takes one drug, namely metformin.', 'Metformin was withheld today.'),))


    def test_foreign_switch_and_patient_change_have_distinct_medication_ownership(self):
        # The four retained CI failures expected a foreign husband's own switch
        # to end the patient's explicit warfarin. Whole-source actor proof
        # separates those owners; the old failed blocks remain evidence.
        for foreign in ('Her husband switched to apixaban.',
                'Her husband was switched to apixaban.',
                'Her husband switched from warfarin to apixaban.',
                'Her husband was switched from warfarin to apixaban.'):
            for notes in (WARFARIN + ' ' + foreign, foreign + ' ' + WARFARIN):
                with self.subTest(foreign=foreign, notes=notes):
                    self.assert_adopted(notes, ('Medications', 'Plan'), 'Medications', WARFARIN)
                    self.assert_held(notes, ('Medications', 'Plan'), 'Medications', foreign)
        # Explicit patient, ambiguous personal-pronoun and clinician-agent
        # changes still end the patient's answer even if marked independent.
        self.assert_cases_held(tuple((WARFARIN, change) for change in (
            'The patient switched to apixaban.', 'The patient was switched to apixaban.',
            'She was switched to apixaban.', 'They were switched to apixaban.',
            'The doctor switched to apixaban.', 'Switched to apixaban.',
            'Warfarin was replaced by apixaban.', 'Warfarin was stopped.')))


class ConjoinedCessation(Worst):
    """WITHDRAWN 2026-10-02 (refutation RS-1 to RS-5, F-AGENT-RELEASE): 54fb4e74 let a cessation conjunct with no subject
    of its own end its head's subject, and df29952c guarded the agent of a transitive head. Both RELEASED a stopped
    medication as current ('Haematology reviewed and stopped.', 'The cardiologist was consulted and stopped them.', 'Her
    INR was checked and stopped.', 'The cardiologist agreed and stopped.'): who or what a cessation ends cannot be read
    from a subject the sentence omits. Every conjunct reads exactly as on ab58c98f, so D02's 'The scope was advanced to
    the terminal ileum and withdrawn slowly.' is a bare cessation again (a declared residual on the v3 relations path)."""
    DESCRIPTION = 'DESCRIPTION OF PROCEDURE: The scope was advanced to the terminal ileum and withdrawn slowly.'
    D02 = ('BOWEL PREPARATION / BBPS: Good, BBPS 8\nEXTENT OF EXAMINATION: Terminal ileum\n' + DESCRIPTION +
           '\nSPECIMENS: Two polyps sent to pathology.\nESTIMATED BLOOD LOSS: Minimal\nCOMPLICATIONS: None')
    #: RS-1 (an intransitive head's agent), RS-2 (a passive head, an active conjunct with its own pronoun object), RS-3
    #: (a measurement or a linking verb's subject), RS-4 (a treatment, an unaccusative conjunct), RS-5 (a class word),
    #: F-AGENT-RELEASE and the false greens F11 / F12 / F18: each HELD on ab58c98f and must stay held.
    RELEASES = (
        ('The patient takes warfarin 5 mg daily.', 'Medications', ('Haematology reviewed and stopped.',
         'The cardiologist reviewed and discontinued.', 'The cardiologist was consulted and stopped them.',
         'Her INR was checked and stopped.', 'The INR was high and stopped.', 'The cardiologist agreed and stopped.',
         'Cardiology reviewed and stopped.', 'Anticoagulation was reviewed and stopped.',
         'The patient was reviewed, the INR checked and stopped.', 'The cardiologist advised her to reduce and stop.',
         'Her symptoms remained resolved.', 'Warfarin was given a trial and stopped.',
         'Warfarin was started and stopped.')),
        ('The patient takes ramipril 5 mg daily.', 'Medications', ('Potassium was 6.1 and stopped.',
                                                                    'Her potassium was high and discontinued.')),
        ('The patient takes lithium 400 mg nightly.', 'Medications', ('Levels were toxic and stopped.',)),
        ('The patient has a cough.', 'Current symptoms', ('Antibiotics were given and resolved.',)),
    )

    def test_a_conjoined_cessation_names_nothing_it_ended_and_holds_as_on_ab58c98f(self):
        for answer, label, tails in self.RELEASES:
            for tail in tails:
                for notes in (answer + ' ' + tail, tail + ' ' + answer):
                    with self.subTest(notes=notes):
                        self.assert_held(notes, (label, 'Plan'), label, answer, shown=tail)
        # (F15: a conjunct with its own subject ends only that subject, as on ab58c98f)
        self.assert_adopted('The patient takes apixaban. Apixaban was started and warfarin was stopped.',
                            ('Medications', 'Plan'), 'Medications', 'The patient takes apixaban.')

    def test_declared_residual_the_d02_description_line_holds_every_other_answer(self):
        # The bare 'withdrawn slowly' holds every other answer on the v3 relations path, exactly as on ab58c98f (the
        # legacy default engine adopts them). Not released by any reading: what it withdrew is not in the sentence.
        labels = ('BOWEL PREPARATION / BBPS', 'EXTENT OF EXAMINATION', 'SPECIMENS', 'ESTIMATED BLOOD LOSS',
                  'COMPLICATIONS')
        fields = form(*labels)
        lines = self.D02.split('\n')
        picks = {label: [next(line for line in lines if line.startswith(label + ':'))] for label in labels}
        answers = self.answers(self.D02, fields, picks)
        self.assertEqual({f['label']: answers[f['key']]['status'] for f in fields},
                         {label: 'conflict' for label in labels})
        for f in fields:
            self.assertIn(self.DESCRIPTION, [c['quote'] for c in answers[f['key']]['held_candidate']['context']])

    def test_a_true_bare_cessation_stays_bare(self):
        for tail in ('Stopped last month.', 'It was stopped.', 'The patient quit five years ago.', 'She stopped it.',
                     'The patient started warfarin and then stopped.', 'The cardiologist reviewed her and discontinued.',
                     # (F-VACUOUS-GP-ROW: 'gp' is too short to be a key, so the row named a clinician that is one)
                     'The cardiologist reviewed the warfarin and switched to apixaban.'):
            with self.subTest(tail=tail):
                self.assert_held('The patient attends the clinic every week. ' + tail, ('Clinic attendance', 'Plan'),
                                 'Clinic attendance', 'The patient attends the clinic every week.', shown=tail)


class InsteadPointsBack(Worst):
    """(examined with RV4H-2) 'The patient will instead be admitted for surgery.' after a Plan answer was ADOPTED with the
    model calling it independent; the fronted 'Instead, ...' already held as a connective (DEPENDS). 'instead' on the
    clause's own head now points back wherever it stands; DEPENDS reaches the line before it (and on through other
    questions' plain labelled values), as for any connective."""
    PLAN = 'The patient will be discharged home.'

    def test_instead_holds_the_line_it_replaces(self):
        for tail in ('The patient will instead be admitted for surgery.', 'The patient will be admitted instead.',
                     'Instead, the patient will be admitted.'):
            with self.subTest(tail=tail):
                self.assert_held(self.PLAN + ' ' + tail, ('Plan', 'Assessment'), 'Plan', self.PLAN, shown=tail)

    def test_instead_of_names_what_it_replaces_and_does_not_point_back(self):
        self.assert_adopted('The patient attends the clinic every week. The patient takes apixaban instead of warfarin.',
                            ('Clinic attendance', 'Plan'), 'Clinic attendance', 'The patient attends the clinic every week.')
        self.assert_adopted(self.PLAN + ' The patient walks daily.', ('Plan', 'Assessment'), 'Plan', self.PLAN)


@override_settings(**RELATIONS)
class InsteadOnSonnet5(InsteadPointsBack, SimpleTestCase):
    pass


@override_settings(**dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False, V3_GENERATION_BATCHES=False))
class InsteadOnTheDefaultPath(SimpleTestCase):
    def test_instead_changes_nothing_on_the_default_path(self):
        # (refutation F13) 'instead' feeds only 'dependent' (the relation floors), never 'standalone', which the default
        # path's rules (a) and (b) read: the default path adopts the plan exactly as it does beside an unrelated line.
        from .test_v3_ordinary_notes import run
        self.assertFalse(g.field_relations_enabled())
        fields = [field('v3_3', 'Plan', 'long_text'), field('v3_7', 'Assessment', 'long_text')]
        plan = 'The patient will be discharged home.'
        for tail in ('The patient walks daily.', 'The patient will instead be admitted for surgery.',
                     'The patient will be admitted instead.'):
            notes = plan + '\n\n' + tail
            with self.subTest(notes=notes):
                self.assertEqual(run(notes, {'Plan': [plan]}, fields=fields)['Plan']['status'], 'supported')


@override_settings(**SONNET_55_DEFAULT)
class InsteadOnSonnet55Default(InsteadPointsBack, SimpleTestCase):
    model = g.SONNET_5_5


@override_settings(**RELATIONS)
class SupersessionOnSonnet5(SupersessionFloor, SimpleTestCase):
    pass


@override_settings(**RELATIONS)
class RoundTwoOnSonnet5(RoundTwoRepairs, SimpleTestCase):
    pass


@override_settings(**SONNET_55_DEFAULT)
class RoundTwoOnSonnet55Default(RoundTwoRepairs, SimpleTestCase):
    model = g.SONNET_5_5


@override_settings(**SONNET_55_DEFAULT)
class SupersessionOnSonnet55Default(SupersessionFloor, SimpleTestCase):
    model = g.SONNET_5_5

    def test_the_default_takes_the_relations_contract(self):
        self.assertTrue(g.field_relations_enabled())


@override_settings(**RELATIONS)
class ConjoinedCessationOnSonnet5(ConjoinedCessation, SimpleTestCase):
    pass


@override_settings(**SONNET_55_DEFAULT)
class ConjoinedCessationOnSonnet55Default(ConjoinedCessation, SimpleTestCase):
    model = g.SONNET_5_5


class Reading(SimpleTestCase):
    """What the floors read of one sentence (`v3_actors._floor_reading`): ended keys and whether it names nothing."""

    def reading(self, text):
        from core import v3_syntax
        doc = v3_syntax.docs([text])[0]
        words = [t for t in doc if t.idx >= (text.index(':') + 1 if ':' in text else 0)]
        found = a._floor_reading(words, next(iter(doc.sents)).root)
        return found['ceased_keys'], found['bare_cessation']

    def test_what_each_reading_ends(self):
        for text, ended, bare in (
                ('Warfarin has been switched to apixaban.', {'warfarin'}, False),
                ('Warfarin was switched from aspirin.', {'aspirin'}, False),
                ('The patient was switched from warfarin to apixaban.', {'warfarin'}, False),
                ('Apixaban was substituted for warfarin.', {'warfarin'}, False),
                ('Warfarin was substituted with apixaban.', {'warfarin'}, False),
                ('Warfarin was replaced by apixaban last month.', {'warfarin'}, False),
                ('Apixaban replaced warfarin.', {'warfarin'}, False),
                ('Warfarin was swapped for apixaban.', {'warfarin'}, False),
                ('The warfarin is on hold for surgery.', {'warfarin'}, False),
                ('Put warfarin on hold.', {'warfarin'}, False),
                ('Warfarin was put on hold before the procedure.', {'warfarin'}, False),
                ('The dose was changed from 5 mg to 10 mg.', {'dose'}, False),
                ('She was switched to apixaban.', set(), True),
                ('Withheld today.', set(), True),
                ('The patient is on hold for surgery.', set(), True),
                ('The patient was held overnight for observation.', set(), False),
                ('Dressing changed daily.', set(), False),
                ('There is no change in symptoms.', set(), False),
                ('She switches between two inhalers.', set(), False),
                ('The light was switched on.', set(), False),
                # every conjunct reads as on ab58c98f (the withdrawn subject sharing, refutation RS-1 to RS-5)
                ('The scope was advanced to the terminal ileum and withdrawn slowly.', set(), True),
                ('DESCRIPTION OF PROCEDURE: The scope was advanced to the terminal ileum and withdrawn slowly.', set(),
                 True),
                ('Warfarin was started and stopped.', set(), True),
                ('Haematology reviewed and stopped.', set(), True),
                ('The cardiologist was consulted and stopped them.', set(), True),
                ('Her INR was checked and stopped.', set(), True),
                ('Potassium was 6.1 and stopped.', set(), True),
                ('The cardiologist agreed and stopped.', set(), True),
                ('The patient started warfarin and then stopped.', set(), True),
                ('Stopped last month.', set(), True),
                ('It was stopped.', set(), True),
                ('The patient quit five years ago.', set(), True),
                ('She stopped and was switched from warfarin.', {'warfarin'}, True),
                ('The cardiologist reviewed her and discontinued.', set(), True),
                ('The bleeding settled and stopped.', set(), True),
                ('The nurse held the warfarin.', {'warfarin'}, False),
                ('The patient held her breath.', {'breath'}, False),
                # (refutation RSL-1 to RSL-3, O2) the verb the tagger reads as a noun, a verb hanging on what it
                # supersedes, a present-tense replacer, the old value under the replacement
                ('Switch gliclazide to insulin.', {'gliclazide'}, False),
                ('Withhold metformin.', {'metformin'}, False),
                ('Substitute citalopram for sertraline.', {'sertraline'}, False),
                ('HOLD WARFARIN.', {'warfarin'}, False),
                ('Withholding warfarin for 5 days.', {'warfarin'}, False),
                ('Held warfarin.', {'warfarin'}, False),
                ('Holding amlodipine.', {'amlodipine'}, False),
                ('WARFARIN HELD.', {'warfarin'}, False),
                ('Warfarin (held).', {'warfarin'}, False),
                ('Warfarin: held for surgery.', set(), True),
                ('Changed clopidogrel to ticagrelor.', {'clopidogrel'}, False),
                ('Apixaban replaces warfarin.', {'warfarin'}, False),
                ('Lansoprazole now replaces omeprazole.', {'omeprazole'}, False),
                ('Bisoprolol replaces atenolol.', set(), True),
                ('The GP replaces warfarin with apixaban.', {'warfarin'}, False),
                ('The patient was switched to apixaban from warfarin.', {'warfarin'}, False),
                ('Warfarin switched to apixaban.', {'warfarin'}, False),
                ('The cardiologist switched to apixaban.', set(), True),
                ('Haematology switched to apixaban.', set(), True),
                ('She was switched to apixaban and the patient was held overnight.', set(), True)):
            with self.subTest(text=text):
                found, found_bare = self.reading(text)
                self.assertEqual((found, found_bare), (a.keys(ended), bare), text)
