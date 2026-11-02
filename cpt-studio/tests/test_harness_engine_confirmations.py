"""HARNESS.md 11.3: the validation engine's reading of reviewer-confirmed findings (studio.types.ConfirmedFinding).

A participant's located passage, accepted by an owner or reviewer with an attestation, answers the open question the
readers' hold raised: a required fact (extent, the E/M basis, ...), or whether a proposal's code was performed. Each test
builds a synthetic document and the proposal provider's answer, runs the real routing, the real documented-service
inventory and the engine, first without the confirmation (the hold is asserted, so a reader change cannot make a test
vacuous) and then with it. The expected outcome is written here, outside the coding input.

The claims: a confirmation answers exactly the open question it was made for and nothing else; whatever uses it says
so ("confirmed from Fable's located passage by <reviewer>") and records support['confirmed']; it never approves
anything; one whose passage is not an exact slice of the revision text, or that is malformed, is not read and is listed
in an encounter warning; everything else (same-day rules, base inclusion, references, the other questions) applies as
usual; keys and fingerprints are deterministic. Synthetic data only; nothing is sent.
"""
from dataclasses import replace
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (ConfirmedFinding, EvidenceSpan, Fact, NormalizedResponse, ProviderCode,
                          ReferenceSourceInfo, canonical_json, sha256_json)
from studio.validation import checks, engine
from studio.validation.engine import assess

DAY = date(2026, 10, 14)
REVIEWER = 'Rowan Synthetic-Reviewer (fictional)'
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
LAND = 'Landmarks photographed: appendiceal orifice and ileocecal valve.'
SNARE = 'was removed with a hot snare'
BIOPSY = 'was biopsied with cold forceps'
UNCLEAR = 'biopsies of the ascending colon lesion were taken'
SPECIMEN = 'Specimen log: jar 2, ascending colon lesion, cold forceps.'
# Two colonoscopy codes, each held on the extent: routing reads no extent ("Landmarks photographed" is not one).
TWO_EXTENTS = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
               'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
               'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
               'A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.\n' + LAND + '\n')
# 45380 held on its status (the biopsy is left in doubt) and on the extent; 45385 on the extent alone.
STATUS_AND_EXTENT = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
                     'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
                     'It is unclear whether biopsies of the ascending colon lesion were taken.\n'
                     'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
                     + SPECIMEN + '\n' + LAND + '\n')
# The same with the extent read (advanced to the cecum): 45380 held on its status alone, 45385 ready.
STATUS_ONLY = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
               'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
               'The colonoscope was advanced to the cecum and the examination was completed.\n'
               'It is unclear whether biopsies of the ascending colon lesion were taken.\n'
               'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n' + SPECIMEN + '\n')
TIME = 'Time statement: 25 minutes spent on the date of the visit.'
VISIT = (HEAD + 'Office visit (fictional)\nDate of service: 2026-10-14\nPlace of service: Office\n'
         'Established patient seen for heartburn. Examination unremarkable.\nAssessment: GERD.\n'
         'Plan: Omeprazole 20 mg daily.\n' + TIME + '\n')
SEEN = 'Established patient seen for heartburn'
# An EGD documented with no extent and no EGD code beside a coded colonoscopy: a service-scope extent question.
EGD_UNCODED = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
               'Procedure: EGD\nBiopsies of the gastric antrum were taken with cold forceps.\n'
               'Photo documentation: duodenal bulb and second portion.\n'
               'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was completed.\n'
               'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n')
DUODENUM = 'Photo documentation: duodenal bulb and second portion.'  # a passage the readers do not read as an extent
# An E/M with no basis beside a same-day sigmoidoscopy: held on its status, its basis and the separate E/M.
VISIT_AND_SIG = (HEAD + 'Office visit and same-day procedure (fictional)\nDate of service: 2026-10-14\n'
                 'Place of service: Office\nEstablished patient seen for rectal bleeding.\n'
                 'Procedure: Flexible sigmoidoscopy. The sigmoidoscope was advanced to 50 cm. Two cold forceps biopsies '
                 'were taken.\n' + TIME + '\n')


def info(key, kind, release):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=f'{release} synthetic', release=release,
                               url='https://www.cms.gov/synthetic', sha256='0' * 64, effective_start='2026-10-01',
                               effective_end='2026-12-31', license_note='licence', scope_note='scope')


PFS_INFO = info('cms-pfs-rvu26d', 'cms-pfs', 'RVU26D')
MUE_INFO = info('cms-mue-practitioner-2026q4', 'cms-mue-practitioner', '2026-Q4')
CODES = {'45378': ('2', None), '45380': ('3', '45378'), '45385': ('3', '45378'), '45330': ('2', None),
         '45331': ('3', '45330'), '43235': ('2', None), '43239': ('3', '43235')}
PFS_ROWS = {(code, ''): {'status': 'A', 'global_days': '000', 'mult_proc': mult, 'endo_base': base, 'pctc': '0'}
            for code, (mult, base) in CODES.items()}
PFS_ROWS[('99213', '')] = {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': None, 'pctc': '0'}
MUE_ROWS = {key: {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of Service Edit: Policy'},
                  'rationale': 'Anatomic Consideration'} for key in PFS_ROWS}
REFERENCE = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {PFS_INFO.key: PFS_ROWS, MUE_INFO.key: MUE_ROWS})


def span(text, phrase, nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.index(phrase, start + 1)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def run(text, codes=(), confirmed=(), *, provider_status='succeeded', **kwargs):
    """``codes``: the proposal provider's selected codes, (code, quote) pairs."""
    selected = tuple(ProviderCode('selected', 'cpt', value, 'UNVERIFIED PROVIDER WORDING', (span(text, quote),))
                     for value, quote in codes)
    response = NormalizedResponse('corti', 'test@1', selected) if provider_status == 'succeeded' else None
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, DAY),
                  normalized=response, reference=REFERENCE, service_date=DAY, provider_status=provider_status,
                  confirmed=tuple(confirmed), **kwargs)


def confirm(text, phrase, *, fact, family, value, key='', scope='', by=('fable',), cid='conf-1', reviewer=REVIEWER,
            evidence=None):
    spans = (span(text, phrase),) if evidence is None else evidence
    return ConfirmedFinding(scope or ('proposal' if key else 'service'), fact, family, key, value, spans, tuple(by),
                            reviewer, cid)


def proposal(result, key):
    found = [p for p in result.proposals if p.key == key]
    assert len(found) == 1, f'{key}: {[(p.key, p.code, p.bucket) for p in result.proposals]}'
    return found[0]


def check(item, check_id):
    return next((c for c in item.checks if c.id == check_id), None)


def encounter_check(result, check_id):
    return next((c for c in result.encounter_checks if c.id == check_id), None)


def questions(item):
    return [(q.scope, q.family, q.fact) for q in item.clarifications]


def without_confirmations(result):
    """The result with what reading confirmations adds taken out: their encounter checks and completeness record."""
    complete = {k: v for k, v in result.completeness.items() if k != 'confirmations'}
    return replace(result, completeness=complete,
                   encounter_checks=tuple(c for c in result.encounter_checks if not c.id.startswith('confirmations.')))


WORDS = f"confirmed from Fable's located passage by {REVIEWER}"
COLON_CODES = (('45385', SNARE), ('45380', BIOPSY))
STATUS_CODES = (('45380', UNCLEAR), ('45385', SNARE))


class ConfirmedFactTests(SimpleTestCase):
    def test_a_proposal_extent_question_takes_the_confirmed_value_on_its_passage(self):
        before = run(TWO_EXTENTS, COLON_CODES)
        self.assertEqual([(p.key, p.code, p.status) for p in before.proposals],
                         [('sel:0', '45385', 'needs_clarification'), ('sel:1', '45380', 'needs_clarification')])
        self.assertEqual(questions(proposal(before, 'sel:0')), [('proposal', 'gi.colonoscopy', 'extent')])
        after = run(TWO_EXTENTS, COLON_CODES, [confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy',
                                                       key='sel:0', value='cecum')])
        item = proposal(after, 'sel:0')
        self.assertEqual((item.code, item.bucket, item.status, questions(item)), ('45385', 'selected', 'ready', []))
        facts = check(item, 'facts.required')
        self.assertEqual(facts.status, 'pass')
        self.assertIn(f"{checks.CONFIRMED_HEADING}: extent reached = cecum, {WORDS} (“{LAND}”).", facts.detail)
        self.assertNotIn('Documented: extent', facts.detail)  # never presented as the readers' own reading
        self.assertIn(f'{checks.CONFIRMED_HEADING}: extent reached = cecum, {WORDS} (“{LAND}”).', item.rationale)
        self.assertTrue(item.rationale.startswith('Selected by corti.'), item.rationale)
        self.assertEqual(item.support['confirmed'], ['conf-1'])
        self.assertNotEqual(item.fingerprint, proposal(before, 'sel:0').fingerprint)
        # the other proposal's own extent question is another question: untouched
        self.assertEqual(proposal(after, 'sel:1'), proposal(before, 'sel:1'))
        applied = encounter_check(after, 'confirmations.applied')
        self.assertEqual(applied.status, 'info')
        self.assertIn(f'extent reached of 45385 (sel:0) = cecum, {WORDS} (“{LAND}”)', applied.detail)
        self.assertIn('A confirmation never approves a code: approval stays a separate decision.', applied.detail)
        self.assertIsNone(encounter_check(after, 'confirmations.ignored'))
        self.assertEqual(after.completeness['confirmations']['applied'][0]['ids'], ['conf-1'])
        self.assertEqual(after.completeness['confirmations']['ignored'], [])
        # nothing else moves: the other encounter checks, the encounter questions, the services
        self.assertEqual([c for c in after.encounter_checks if c.id != 'confirmations.applied'],
                         list(before.encounter_checks))
        self.assertEqual((after.clarifications, after.services, after.unsupported, after.reference_sources),
                         (before.clarifications, before.services, before.unsupported, before.reference_sources))

    def test_answering_every_proposal_never_raises_the_question_again_at_the_service(self):
        """The documented colonoscopy states no extent either: its service question is asked only through the
        proposals' (a proposal asking it hides it). Both answered, it is never asked again at the service."""
        both = [confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key=key, value='cecum',
                        cid=f'conf-{key}') for key in ('sel:0', 'sel:1')]
        after = run(TWO_EXTENTS, COLON_CODES, both)
        self.assertEqual([(p.key, p.status) for p in after.proposals], [('sel:0', 'ready'), ('sel:1', 'ready')])
        self.assertEqual(after.clarifications, ())
        self.assertEqual(after.completeness['state'], 'complete_pending_review')

    def test_a_service_extent_question_takes_the_confirmed_value(self):
        before = run(EGD_UNCODED, (('45385', SNARE),))
        self.assertEqual([(q.scope, q.family, q.fact) for q in before.clarifications], [('service', 'gi.egd', 'extent')])
        after = run(EGD_UNCODED, (('45385', SNARE),), [confirm(EGD_UNCODED, DUODENUM, fact='extent', family='gi.egd',
                                                               value='second part of the duodenum')])
        self.assertEqual(after.clarifications, ())
        self.assertEqual(after.proposals, before.proposals)  # no proposal of the family: none reads it
        applied = encounter_check(after, 'confirmations.applied')
        self.assertIn('extent reached of the documented Upper GI endoscopy (EGD, esophagoscopy, POEM) = second part of '
                      f'the duodenum, {WORDS} (“{DUODENUM}”)', applied.detail)
        self.assertEqual(after.completeness['confirmations']['applied'][0]['scope'], 'service')

    def test_an_em_basis_question_takes_the_cited_passage_as_its_basis(self):
        before = run(VISIT, (('99213', SEEN),))
        self.assertEqual(questions(proposal(before, 'sel:0')), [('proposal', 'gi.office_em', 'em_basis')])
        after = run(VISIT, (('99213', SEEN),), [confirm(VISIT, TIME, fact='em_basis', family='gi.office_em',
                                                        key='sel:0', value='total time: 25 minutes')])
        item = proposal(after, 'sel:0')
        self.assertEqual((item.status, questions(item)), ('ready', []))
        self.assertIn('basis for the visit level (total time or medical decision making) = total time: 25 minutes, '
                      f'{WORDS} (“{TIME}”)', check(item, 'facts.required').detail)
        self.assertEqual(item.support['confirmed'], ['conf-1'])

    def test_a_service_em_basis_question_is_answered_for_the_family(self):
        before = run(VISIT)
        self.assertEqual([(q.scope, q.family, q.fact) for q in before.clarifications],
                         [('service', 'gi.office_em', 'em_basis')])
        after = run(VISIT, (), [confirm(VISIT, TIME, fact='em_basis', family='gi.office_em', value='total time')])
        self.assertEqual(after.clarifications, ())
        self.assertIsNotNone(encounter_check(after, 'confirmations.applied'))

    def test_a_confirmed_value_never_replaces_a_value_the_readers_read(self):
        documented = checks.FactState('extent', Fact('extent', 'cecum', 'document'), '')
        missing = checks.FactState('extent', None, 'missing')
        answer = engine._Answer('service', 'gi.colonoscopy', '', '', 'extent', 'terminal ileum',
                                (span(TWO_EXTENTS, LAND),), ('conf-1',), WORDS)
        answers = engine._Answers({'extent': answer})
        self.assertIs(answers.state(documented), documented)
        confirmed = answers.state(missing)
        self.assertEqual((confirmed.problem, confirmed.fact.value, confirmed.confirmed),
                         ('', 'terminal ileum', f'{WORDS} (“{LAND}”)'))


class ConfirmedStatusTests(SimpleTestCase):
    def test_a_status_confirmed_performed_is_decided_on_its_passage(self):
        before = run(STATUS_ONLY, STATUS_CODES)
        held = proposal(before, 'sel:0')
        self.assertEqual((held.code, held.status, questions(held)),
                         ('45380', 'needs_clarification', [('proposal', 'gi.colonoscopy', 'performed_status')]))
        after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, SPECIMEN, fact='performed_status',
                                                        family='gi.colonoscopy', key='sel:0', value='performed')])
        item = proposal(after, 'sel:0')
        self.assertEqual((item.code, item.bucket, item.status, questions(item)), ('45380', 'selected', 'ready', []))
        status = check(item, 'service.status')
        self.assertEqual((status.status, status.source), ('pass', checks.CONFIRMATION_SOURCE))
        self.assertTrue(status.detail.startswith(f'Performed on the date of service: {WORDS} (“{SPECIMEN}”). CPT '
                                                 "Studio's own readers held it: "), status.detail)
        self.assertIn(check(held, 'service.status').detail, status.detail)  # the readers' own reading stays beside it
        self.assertIn(f'Service status: performed ({WORDS}).', item.rationale)
        self.assertEqual((item.support['state'], item.support['reason'], item.support['confirmed']),
                         ('performed', 'confirmed', ['conf-1']))
        self.assertIn(WORDS, item.support['detail'])
        self.assertIn(WORDS, check(item, 'evidence.support').detail)
        self.assertEqual(check(item, 'evidence.support').status, 'not_applicable')
        self.assertEqual(proposal(after, 'sel:1'), proposal(before, 'sel:1'))
        self.assertEqual(item.evidence, held.evidence)  # the provider's passages: the confirmed one is never added

    def test_a_status_confirmed_not_performed_is_excluded_reinstatable_and_keys_stay(self):
        """The status path excludes it (reinstatable: the existing Reinstate path is unchanged). Its key stays sel:0,
        and 45385 keeps sel:1, so the key a later question names is the same proposal before and after."""
        after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, UNCLEAR, fact='performed_status',
                                                        family='gi.colonoscopy', key='sel:0', value='not performed')])
        self.assertEqual([(p.key, p.code, p.bucket, p.status) for p in after.proposals],
                         [('sel:1', '45385', 'selected', 'ready'), ('sel:0', '45380', 'excluded', 'excluded')])
        item = proposal(after, 'sel:0')
        self.assertTrue(item.reinstatable)
        self.assertEqual(item.exclusion_reason, f'Not performed on the date of service (documented as negated): {WORDS} '
                                                f'(“{UNCLEAR}”). Reinstate if this code is supported.')
        self.assertEqual(check(item, 'service.status').status, 'fail')
        self.assertEqual(check(item, 'review.reinstatement').status, 'pass')
        # the reconciliation as usual: the biopsy code is no longer an active proposal
        self.assertNotIn('45380', [code for codes in after.completeness['covered'].values() for code in codes])

    def test_a_planned_or_historical_value_is_worded_as_such(self):
        for value, word in (('planned', 'planned'), ('historical', 'historical'), ('cancelled', 'cancelled'),
                            ('not_performed', 'negated')):
            after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, UNCLEAR, fact='performed_status',
                                                            family='gi.colonoscopy', key='sel:0', value=value)])
            self.assertIn(f'(documented as {word})', proposal(after, 'sel:0').exclusion_reason, value)

    def test_a_second_confirmation_on_the_confirmed_assessment_finds_its_proposal_by_the_same_key(self):
        excluded = confirm(STATUS_AND_EXTENT, UNCLEAR, fact='performed_status', family='gi.colonoscopy', key='sel:0',
                           value='not_performed', cid='conf-a')
        first = run(STATUS_AND_EXTENT, STATUS_CODES, [excluded])
        self.assertEqual([(p.key, p.code, p.bucket) for p in first.proposals],
                         [('sel:1', '45385', 'selected'), ('sel:0', '45380', 'excluded')])
        self.assertEqual(questions(proposal(first, 'sel:1')), [('proposal', 'gi.colonoscopy', 'extent')])
        # a reviewer answers 45385's extent question as that assessment asks it: proposal sel:1
        extent = confirm(STATUS_AND_EXTENT, LAND, fact='extent', family='gi.colonoscopy', key='sel:1', value='cecum',
                         cid='conf-b')
        second = run(STATUS_AND_EXTENT, STATUS_CODES, [excluded, extent])
        self.assertEqual((proposal(second, 'sel:1').code, proposal(second, 'sel:1').status), ('45385', 'ready'))
        self.assertEqual(proposal(second, 'sel:0'), proposal(first, 'sel:0'))
        self.assertEqual(second, run(STATUS_AND_EXTENT, STATUS_CODES, [extent, excluded]))  # whatever the order

    def test_a_value_that_is_neither_performed_nor_not_performed_is_not_read(self):
        before = run(STATUS_ONLY, STATUS_CODES)
        for value in ('attempted_incomplete', 'incomplete', 'unclear', 'yes', 'performed in part'):
            after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, SPECIMEN, fact='performed_status',
                                                            family='gi.colonoscopy', key='sel:0', value=value)])
            self.assertEqual(without_confirmations(after), before, value)
            self.assertIn('its value is neither performed nor a status documenting the service as not performed',
                          encounter_check(after, 'confirmations.ignored').detail, value)


class GuardTests(SimpleTestCase):
    def test_a_passage_that_is_not_an_exact_slice_of_the_text_is_not_read(self):
        before = run(TWO_EXTENTS, COLON_CODES)
        good = span(TWO_EXTENTS, LAND)
        for bad in ((replace(good, start=good.start + 1),), (replace(good, text=LAND.upper()),),
                    (replace(good, context_index=1),), (replace(good, exact=False),),
                    (EvidenceSpan(0, len(TWO_EXTENTS) - 3, len(TWO_EXTENTS) + 9, 'off the end', True),),
                    (good, replace(good, end=good.end + 2))):  # one bad span among good ones: the whole is not read
            after = run(TWO_EXTENTS, COLON_CODES, [confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy',
                                                           key='sel:0', value='cecum', evidence=bad)])
            self.assertEqual(without_confirmations(after), before, bad)
            warn = encounter_check(after, 'confirmations.ignored')
            self.assertEqual(warn.status, 'warn')
            self.assertIn("the confirmation of extent reached for proposal sel:0: its passage is not an exact slice of "
                          "this revision's text", warn.detail)
            self.assertIsNone(encounter_check(after, 'confirmations.applied'))
            self.assertEqual(after.completeness['confirmations'], {'applied': [], 'ignored': [
                {'id': 'conf-1', 'why': "its passage is not an exact slice of this revision's text"}]})

    def test_a_confirmation_never_touches_another_question(self):
        """45380 asks two questions (its status and the extent): the extent's answer leaves the status question, and
        45385's own extent question, as they were."""
        before = run(STATUS_AND_EXTENT, STATUS_CODES)
        self.assertEqual(questions(proposal(before, 'sel:0')), [('proposal', 'gi.colonoscopy', 'performed_status'),
                                                                ('proposal', 'gi.colonoscopy', 'extent')])
        after = run(STATUS_AND_EXTENT, STATUS_CODES, [confirm(STATUS_AND_EXTENT, LAND, fact='extent',
                                                              family='gi.colonoscopy', key='sel:0', value='cecum')])
        item = proposal(after, 'sel:0')
        self.assertEqual((item.status, questions(item)),
                         ('needs_clarification', [('proposal', 'gi.colonoscopy', 'performed_status')]))
        self.assertEqual(check(item, 'service.status'), check(proposal(before, 'sel:0'), 'service.status'))
        self.assertEqual(proposal(after, 'sel:1'), proposal(before, 'sel:1'))

    def test_a_confirmed_code_can_still_be_held_for_another_reason(self):
        """The same-day E/M rule applies as usual: an E/M whose basis is confirmed beside a same-day sigmoidoscopy is
        still held on its status and on the separately identifiable E/M - and that question is not one a confirmation
        answers."""
        codes = (('99213', 'Established patient seen for rectal bleeding'), ('45331', 'Two cold forceps biopsies'))
        before = run(VISIT_AND_SIG, codes)
        self.assertEqual(questions(proposal(before, 'sel:0')), [('proposal', 'gi.office_em', 'performed_status'),
                                                                ('proposal', 'gi.office_em', 'em_basis'),
                                                                ('proposal', 'gi.office_em', 'separate_em')])
        after = run(VISIT_AND_SIG, codes, [
            confirm(VISIT_AND_SIG, TIME, fact='em_basis', family='gi.office_em', key='sel:0', value='time', cid='a'),
            confirm(VISIT_AND_SIG, TIME, fact='separate_em', family='gi.office_em', key='sel:0', value='yes', cid='b')])
        item = proposal(after, 'sel:0')
        self.assertEqual((item.status, questions(item)), ('needs_clarification', [
            ('proposal', 'gi.office_em', 'performed_status'), ('proposal', 'gi.office_em', 'separate_em')]))
        self.assertEqual(check(item, 'em.same_day_procedure'), check(proposal(before, 'sel:0'), 'em.same_day_procedure'))
        self.assertIn('the confirmation of separate em for proposal sel:0: a confirmation answers whether a code was '
                      'performed or a required fact the readers take from the document',
                      encounter_check(after, 'confirmations.ignored').detail)

    def test_a_confirmation_never_approves_anything(self):
        after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, SPECIMEN, fact='performed_status',
                                                        family='gi.colonoscopy', key='sel:0', value='performed')])
        self.assertEqual({p.status for p in after.proposals}, {'ready'})
        self.assertTrue({p.status for p in after.proposals} <= {'ready', 'needs_clarification', 'excluded',
                                                               'informational'})
        self.assertFalse(any(p.reinstatable for p in after.proposals if p.bucket == 'selected'))
        self.assertEqual(after.summary['ready'], 2)  # ready to decide; approval is a member's separate decision
        self.assertNotIn('approved', canonical_json(after).decode('utf-8'))

    def test_a_question_this_assessment_does_not_ask_is_not_answered(self):
        before = run(STATUS_ONLY, STATUS_CODES)
        for c in (confirm(STATUS_ONLY, SPECIMEN, fact='performed_status', family='gi.colonoscopy', key='sel:1',
                          value='performed'),  # 45385 is not held on its status
                  confirm(STATUS_ONLY, SPECIMEN, fact='performed_status', family='gi.egd', key='sel:0',
                          value='performed'),  # another family
                  confirm(STATUS_ONLY, SPECIMEN, fact='performed_status', family='gi.colonoscopy', key='sel:7',
                          value='performed'),  # no such proposal
                  confirm(STATUS_ONLY, SPECIMEN, fact='extent', family='gi.colonoscopy', key='sel:0',
                          value='cecum'),  # the extent is read
                  confirm(STATUS_ONLY, SPECIMEN, fact='extent', family='gi.colonoscopy', value='cecum')):  # nor asked
            after = run(STATUS_ONLY, STATUS_CODES, [c])
            self.assertEqual(without_confirmations(after), before, c)
            self.assertIn(engine.NOT_OPEN, encounter_check(after, 'confirmations.ignored').detail, c)

    def test_the_service_date_and_other_context_facts_never_come_this_way(self):
        before = run(VISIT, (('99213', SEEN),))
        for fact, scope in (('service_date', 'encounter'), ('service_date', 'service'), ('setting', 'proposal'),
                            ('patient_status', 'service')):
            c = confirm(VISIT, 'Date of service: 2026-10-14', fact=fact, family='gi.office_em', value='2026-10-14',
                        scope=scope, key='sel:0' if scope == 'proposal' else '')
            after = run(VISIT, (('99213', SEEN),), [c])
            self.assertEqual(without_confirmations(after), before, fact)
            self.assertIn(engine.CONTEXT_ONLY, encounter_check(after, 'confirmations.ignored').detail, fact)

    def test_a_malformed_confirmation_is_not_read(self):
        base = confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum')
        before = run(TWO_EXTENTS, COLON_CODES)
        for changed, why in (({'confirmed_by': '  '}, 'it names no reviewer'),
                             ({'located_by': ()}, 'it names neither Astra nor Fable'),
                             ({'located_by': ('gemini',)}, 'it names neither Astra nor Fable'),
                             ({'located_by': ('corti',)}, 'it names neither Astra nor Fable'),  # 11.3: no candidate
                             ({'confirmation_id': ''}, 'it has no confirmation id'),
                             ({'value': ' '}, 'it confirms no value'),
                             ({'evidence': ()}, 'it cites no passage'),
                             ({'family': 'gi.unknown'}, 'it names no service family CPT Studio knows'),
                             ({'scope': 'proposal', 'proposal_key': ''}, 'it names no proposal'),
                             ({'scope': 'service'}, 'a service question names no proposal'),
                             ({'scope': 'service', 'proposal_key': '', 'fact': 'performed_status'},
                              'whether a code was performed is a question about a proposal'),
                             ({'scope': 'claim'}, 'its scope is neither a service nor a proposal question'),
                             ({'value': 7}, 'its value is not text')):
            after = run(TWO_EXTENTS, COLON_CODES, [replace(base, **changed)])
            self.assertEqual(without_confirmations(after), before, changed)
            self.assertIn(why, encounter_check(after, 'confirmations.ignored').detail, changed)
        with self.assertRaises(ValueError):
            run(TWO_EXTENTS, COLON_CODES, [{'fact': 'extent'}])

    def test_confirmations_of_one_question_that_disagree_are_all_left_unread(self):
        before = run(TWO_EXTENTS, COLON_CODES)
        a = confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum', cid='a')
        b = replace(a, value='terminal ileum', confirmation_id='b')
        after = run(TWO_EXTENTS, COLON_CODES, [a, b])
        self.assertEqual(without_confirmations(after), before)
        detail = encounter_check(after, 'confirmations.ignored').detail
        self.assertIn('2 confirmations not read', detail)
        self.assertIn(engine.DISAGREEING, detail)
        status_a = confirm(STATUS_ONLY, SPECIMEN, fact='performed_status', family='gi.colonoscopy', key='sel:0',
                           value='performed', cid='a')
        status_b = replace(status_a, value='planned', confirmation_id='b')
        self.assertEqual(without_confirmations(run(STATUS_ONLY, STATUS_CODES, [status_a, status_b])),
                         run(STATUS_ONLY, STATUS_CODES))

    def test_confirmations_that_agree_are_read_together(self):
        a = confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum', cid='a')
        b = replace(a, value='  Cecum ', confirmation_id='b', located_by=('astra', 'fable'),
                    confirmed_by='Second Synthetic-Reviewer (fictional)')
        item = proposal(run(TWO_EXTENTS, COLON_CODES, [a, b]), 'sel:0')
        self.assertEqual((item.status, item.support['confirmed']), ('ready', ['a', 'b']))
        detail = check(item, 'facts.required').detail
        self.assertIn(f"extent reached = cecum, {WORDS}; and from Astra's and Fable's located passage by Second "
                      'Synthetic-Reviewer (fictional)', detail)


class DeterminismTests(SimpleTestCase):
    def test_none_given_is_the_engine_as_before(self):
        for text, codes in ((TWO_EXTENTS, COLON_CODES), (STATUS_ONLY, STATUS_CODES), (VISIT, (('99213', SEEN),))):
            plain = assess(text=text, pages=(), context=gi_context.extract_context(text),
                           routing=detect.route(text, DAY),
                           normalized=NormalizedResponse('corti', 'test@1', tuple(
                               ProviderCode('selected', 'cpt', v, 'UNVERIFIED PROVIDER WORDING', (span(text, q),))
                               for v, q in codes)),
                           reference=REFERENCE, service_date=DAY, provider_status='succeeded')
            self.assertEqual(run(text, codes), plain)
            self.assertEqual(sha256_json(run(text, codes)), sha256_json(plain))
            self.assertNotIn('confirmations', plain.completeness)

    def test_keys_and_fingerprints_are_the_same_whatever_the_order_given(self):
        given = [confirm(STATUS_AND_EXTENT, UNCLEAR, fact='performed_status', family='gi.colonoscopy', key='sel:0',
                         value='not_performed', cid='a'),
                 confirm(STATUS_AND_EXTENT, LAND, fact='extent', family='gi.colonoscopy', key='sel:1', value='cecum',
                         cid='b'),
                 confirm(STATUS_AND_EXTENT, LAND, fact='extent', family='gi.egd', key='sel:1', value='cecum', cid='c')]
        first = run(STATUS_AND_EXTENT, STATUS_CODES, given)
        for order in (given[::-1], [given[1], given[2], given[0]]):
            again = run(STATUS_AND_EXTENT, STATUS_CODES, order)
            self.assertEqual(again, first)
            self.assertEqual(sha256_json(again), sha256_json(first))
        self.assertEqual([(p.key, p.code) for p in first.proposals], [('sel:1', '45385'), ('sel:0', '45380')])

    def test_the_fingerprint_follows_the_confirmed_value_and_passage_never_who_confirmed(self):
        def fingerprint(**changed):
            c = replace(confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum'),
                        **changed)
            return proposal(run(TWO_EXTENTS, COLON_CODES, [c]), 'sel:0').fingerprint
        base = fingerprint()
        self.assertEqual(fingerprint(confirmed_by='Another Synthetic-Reviewer (fictional)', confirmation_id='other',
                                     located_by=('astra',)), base)
        self.assertNotEqual(fingerprint(value='terminal ileum'), base)
        self.assertNotEqual(fingerprint(evidence=(span(TWO_EXTENTS, 'ascending colon'),)), base)
