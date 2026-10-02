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

A CONJOINED CESSATION NAMES ITS SHARED SUBJECT. 'The scope was advanced to the terminal ileum and withdrawn slowly.'
parses 'withdrawn' as a conjunct of the copula's adjective 'advanced', with no subject of its own, so it named nothing
and held EVERY other answer of the note (the owner's colonoscopy form, D02: 14 of 17 answers held on the v3 Word engine).
A conjunct with no subject now ends its head's ('scope', `v3_actors._shared_subjects`); a cessation that names nothing
stays bare. No provider, no network, no database."""
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

    def assert_adopted(self, notes, labels, label, pick):
        fields = form(*labels)
        key = next(f['key'] for f in fields if f['label'] == label)
        answers = self.answers(notes, fields, {label: [pick]})
        self.assertEqual((answers[key]['status'], answers[key]['text']), ('supported', pick), (notes, answers[key]))
        self.assertEqual(g.governed_decisions(notes, fields, {key: answers[key]}), [], notes)
        field_of = next(f for f in fields if f['key'] == key)
        row = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field_of, **answers[key]})
        self.assertEqual((row['status'], row['text']), ('supported', pick), notes)


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


class ConjoinedCessation(Worst):
    DESCRIPTION = 'DESCRIPTION OF PROCEDURE: The scope was advanced to the terminal ileum and withdrawn slowly.'
    D02 = ('BOWEL PREPARATION / BBPS: Good, BBPS 8\nEXTENT OF EXAMINATION: Terminal ileum\n' + DESCRIPTION +
           '\nSPECIMENS: Two polyps sent to pathology.\nESTIMATED BLOOD LOSS: Minimal\nCOMPLICATIONS: None')

    def test_the_d02_description_line_no_longer_holds_every_other_answer(self):
        labels = ('BOWEL PREPARATION / BBPS', 'EXTENT OF EXAMINATION', 'SPECIMENS', 'ESTIMATED BLOOD LOSS',
                  'COMPLICATIONS')
        fields = form(*labels)
        lines = self.D02.split('\n')
        picks = {label: [next(line for line in lines if line.startswith(label + ':'))] for label in labels}
        answers = self.answers(self.D02, fields, picks)
        got = {f['label']: answers[f['key']]['status'] for f in fields}
        self.assertEqual(got, {label: 'supported' for label in labels})
        self.assertEqual(g.governed_decisions(self.D02, fields, answers), [])
        # the same sentence unlabelled, beside an unrelated answer
        self.assert_adopted('The patient attends the clinic every week. The scope was advanced to the terminal ileum '
                            'and withdrawn slowly.', ('Clinic attendance', 'Plan'), 'Clinic attendance',
                            'The patient attends the clinic every week.')

    def test_the_conjunct_ends_its_shared_subject(self):
        self.assert_held('Instrument: Olympus scope.\n' + self.DESCRIPTION, ('Instrument', 'Plan'), 'Instrument',
                         'Instrument: Olympus scope.', shown=self.DESCRIPTION)
        for tail in ('Warfarin was started and stopped.', 'Warfarin was reduced and then withdrawn.'):
            with self.subTest(tail=tail):
                self.assert_held(WARFARIN + ' ' + tail, ('Medications', 'Plan'), 'Medications', WARFARIN, shown=tail)
        self.assert_adopted('The patient attends the clinic every week. Warfarin was started and stopped.',
                            ('Clinic attendance', 'Plan'), 'Clinic attendance', 'The patient attends the clinic every week.')

    def test_a_true_bare_cessation_stays_bare(self):
        # (the last: the active subject of a head with an object is its agent, and the conjunct's own object is elided)
        for tail in ('Stopped last month.', 'It was stopped.', 'The patient quit five years ago.', 'She stopped it.',
                     'The patient started warfarin and then stopped.', 'The cardiologist reviewed her and discontinued.',
                     'The GP reviewed the warfarin and switched to apixaban.'):
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


@override_settings(**SONNET_55_DEFAULT)
class InsteadOnSonnet55Default(InsteadPointsBack, SimpleTestCase):
    model = g.SONNET_5_5


@override_settings(**RELATIONS)
class SupersessionOnSonnet5(SupersessionFloor, SimpleTestCase):
    pass


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
                ('The scope was advanced to the terminal ileum and withdrawn slowly.', {'scope'}, False),
                ('DESCRIPTION OF PROCEDURE: The scope was advanced to the terminal ileum and withdrawn slowly.', {'scope'},
                 False),
                ('Warfarin was started and stopped.', {'warfarin'}, False),
                ('The patient started warfarin and then stopped.', set(), True),
                ('Stopped last month.', set(), True),
                ('It was stopped.', set(), True),
                ('The patient quit five years ago.', set(), True),
                ('She stopped and was switched from warfarin.', {'warfarin'}, True),
                ('The cardiologist reviewed her and discontinued.', set(), True),
                ('The bleeding settled and stopped.', {'bleeding'}, False),
                ('The nurse held the warfarin.', {'warfarin'}, False),
                ('The patient held her breath.', {'breath'}, False)):
            with self.subTest(text=text):
                found, found_bare = self.reading(text)
                self.assertEqual((found, found_bare), (a.keys(ended), bare), text)
