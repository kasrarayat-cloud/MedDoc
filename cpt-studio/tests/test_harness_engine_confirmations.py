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
from unittest import mock

from django.test import SimpleTestCase, override_settings

from studio.gi import context as gi_context
from studio.gi import detect
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (ConfirmedFinding, EvidenceSpan, Fact, NormalizedResponse, ParticipantInput, ProviderCode,
                          ReferenceSourceInfo, canonical_json, sha256_json)
from studio.validation import checks, engine
from studio.validation.engine import assess
from tests.test_harness_engine import code as participant_code, peer, read, reviewed

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
# Refutation round 2, EV2-1: a status is read on the act its code accounts for, so a status confirmation is read only
# where CPT Studio's readers read its passage's whole sentence as that act with that status. Here 45380 cites the hedge
# while another sentence states the biopsy done, or denies, cancels, plans or dates it: the two readers disagree (or no
# biopsy is documented as done) and it is held on its status - and that sentence truly states the act.
COLON_TOP = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
             'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n')
CECUM_DONE = 'The colonoscope was advanced to the cecum and the examination was completed.\n'
HEDGE = 'It is unclear whether biopsies of the ascending colon lesion were taken.\n'
SIGMOID_SNARE = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
DONE_BX = 'Cold forceps biopsies of the ascending colon lesion were taken.'
NOT_DONE = {'not_performed': 'No biopsies of the ascending colon lesion were obtained.',
            'cancelled': 'Biopsies of the ascending colon lesion were cancelled.',
            'planned': 'Biopsies of the ascending colon lesion are planned at the next colonoscopy.',
            'historical': 'Biopsies of the ascending colon lesion were taken in 2019.'}
DENIED_BX = NOT_DONE['not_performed']


def stating(line, *, extent=True):
    """The colonoscopy with 45380's biopsy left in doubt and ``line`` stating it; without the extent, 45380 and 45385
    are also held on it."""
    return (COLON_TOP + (CECUM_DONE if extent else '') + HEDGE + line + '\n' + SIGMOID_SNARE + SPECIMEN + '\n'
            + ('' if extent else LAND + '\n'))


STATUS_STATED = stating(DONE_BX)  # 45380 held on its status (the readers disagree), 45385 ready
STATUS_DENIED = stating(DENIED_BX)
STATUS_AND_EXTENT_DENIED = stating(DENIED_BX, extent=False)
TIME = 'Time statement: 25 minutes spent on the date of the visit.'
VISIT = (HEAD + 'Office visit (fictional)\nDate of service: 2026-10-14\nPlace of service: Office\n'
         'Established patient seen for heartburn. Examination unremarkable.\nAssessment: GERD.\n'
         'Plan: Omeprazole 20 mg daily.\n' + TIME + '\n')
SEEN = 'Established patient seen for heartburn'
# An EGD documented with no extent and no EGD code beside a coded colonoscopy: a service-scope extent question.
EGD_UNCODED = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\n'
               'Place of service: Ambulatory surgery center\n'
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
# An ERCP held on its cannulation: the same path serves every required fact the readers take from the document.
STENT = 'A plastic stent was placed.'
CONTRAST = 'Contrast filled the duct.'
ERCP = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
        'Procedure: ERCP\nThe duodenoscope was advanced to the major papilla. ' + STENT + '\n' + CONTRAST + '\n')


def info(key, kind, release):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=f'{release} synthetic', release=release,
                               url='https://www.cms.gov/synthetic', sha256='0' * 64, effective_start='2026-10-01',
                               effective_end='2026-12-31', license_note='licence', scope_note='scope')


PFS_INFO = info('cms-pfs-rvu26d', 'cms-pfs', 'RVU26D')
MUE_INFO = info('cms-mue-practitioner-2026q4', 'cms-mue-practitioner', '2026-Q4')
CODES = {'45378': ('2', None), '45380': ('3', '45378'), '45384': ('3', '45378'), '45385': ('3', '45378'),
         '45330': ('2', None), '45331': ('3', '45330'), '43235': ('2', None), '43239': ('3', '43235'),
         '43274': ('0', None)}
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


# A configured participant that read nothing: an assessment a model participant took part in, where each decidable
# proposal records the identity a confirmation of its question is bound to (support['identity']).
CONFIGURED = (ParticipantInput('astra', 'failed', reason='HTTP 529 (synthetic)'),)


def run(text, codes=(), confirmed=(), *, provider_status='succeeded', bind=True, **kwargs):
    """``codes``: the proposal provider's selected codes, (code, quote) pairs. ``bind``: each proposal confirmation of
    a list given that names no proposal yet is bound as the confirmation endpoint binds it (bound) on these same
    inputs; an iterator is given to the engine as it is."""
    if bind and isinstance(confirmed, (list, tuple)):
        confirmed = [bound(c, text, codes, provider_status=provider_status, **kwargs) for c in confirmed]
    selected = tuple(ProviderCode('selected', 'cpt', value, 'UNVERIFIED PROVIDER WORDING', (span(text, quote),))
                     for value, quote in codes)
    response = NormalizedResponse('corti', 'test@1', selected) if provider_status == 'succeeded' else None
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, DAY),
                  normalized=response, reference=REFERENCE, service_date=DAY, provider_status=provider_status,
                  confirmed=confirmed, **kwargs)  # as given: an iterator reaches the engine as one


def confirm(text, phrase, *, fact, family, value, key='', scope='', by=('fable',), cid='conf-1', reviewer=REVIEWER,
            evidence=None):
    spans = (span(text, phrase),) if evidence is None else evidence
    return ConfirmedFinding(scope or ('proposal' if key else 'service'), fact, family, key, value, spans, tuple(by),
                            reviewer, cid)


def binding(item):
    """What a confirmation of a question of ``item`` is bound to (HARNESS.md 12.5): its code and identity."""
    return {'proposal_code': item.code, 'proposal_identity': item.support['identity']}


def bound(c, text, codes=(), **kwargs):
    """``c`` as the confirmation endpoint records it: bound to the proposal whose question it is - the proposal at its
    key on the assessment these inputs make without any confirmation, with a participant configured (as every
    assessment that reads a confirmation has one) - by that proposal's code and identity, never by the key alone.
    Unchanged when it is no proposal's question, names one already, or no proposal holds its key."""
    if not isinstance(c, ConfirmedFinding) or c.scope != 'proposal' or c.proposal_code:
        return c
    kwargs['participants'] = kwargs.get('participants') or CONFIGURED
    found = [p for p in run(text, codes, bind=False, **kwargs).proposals
             if p.key == c.proposal_key and 'identity' in p.support]
    return replace(c, **binding(found[0])) if found else c


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


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
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
                                                               value='second part of duodenum')])  # CPT Studio's words
        self.assertEqual(after.clarifications, ())
        self.assertEqual(after.proposals, before.proposals)  # no proposal of the family: none reads it
        applied = encounter_check(after, 'confirmations.applied')
        self.assertIn('extent reached of the documented Upper GI endoscopy (EGD, esophagoscopy, POEM) = second part of '
                      f'duodenum, {WORDS} (“{DUODENUM}”)', applied.detail)
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

    def test_any_other_required_fact_takes_the_confirmed_value(self):
        before = run(ERCP, (('43274', STENT),))
        self.assertEqual(questions(proposal(before, 'sel:0')), [('proposal', 'gi.ercp', 'cannulation')])
        after = run(ERCP, (('43274', STENT),), [confirm(ERCP, CONTRAST, fact='cannulation', family='gi.ercp',
                                                        key='sel:0', value='successful')])  # CPT Studio's words
        item = proposal(after, 'sel:0')
        self.assertEqual((item.status, questions(item)), ('ready', []))
        self.assertIsNone(check(item, 'service.incomplete'))
        self.assertIn(f'cannulation outcome = successful, {WORDS} (“{CONTRAST}”)',
                      check(item, 'facts.required').detail)

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


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ConfirmedStatusTests(SimpleTestCase):
    def test_a_status_confirmed_performed_is_decided_on_its_passage(self):
        before = run(STATUS_STATED, STATUS_CODES)
        held = proposal(before, 'sel:0')
        self.assertEqual((held.code, held.status, questions(held)),
                         ('45380', 'needs_clarification', [('proposal', 'gi.colonoscopy', 'performed_status')]))
        after = run(STATUS_STATED, STATUS_CODES, [confirm(STATUS_STATED, DONE_BX, fact='performed_status',
                                                          family='gi.colonoscopy', key='sel:0', value='performed')])
        item = proposal(after, 'sel:0')
        self.assertEqual((item.code, item.bucket, item.status, questions(item)), ('45380', 'selected', 'ready', []))
        status = check(item, 'service.status')
        self.assertEqual((status.status, status.source), ('pass', checks.CONFIRMATION_SOURCE))
        self.assertTrue(status.detail.startswith(f'Performed on the date of service: {WORDS} (“{DONE_BX}”). CPT '
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
        after = run(STATUS_DENIED, STATUS_CODES, [confirm(STATUS_DENIED, DENIED_BX, fact='performed_status',
                                                          family='gi.colonoscopy', key='sel:0', value='not performed')])
        self.assertEqual([(p.key, p.code, p.bucket, p.status) for p in after.proposals],
                         [('sel:1', '45385', 'selected', 'ready'), ('sel:0', '45380', 'excluded', 'excluded')])
        item = proposal(after, 'sel:0')
        self.assertTrue(item.reinstatable)
        self.assertEqual(item.exclusion_reason, f'Not performed on the date of service (documented as negated): {WORDS} '
                                                f'(“{DENIED_BX}”). Reinstate if this code is supported.')
        self.assertEqual(check(item, 'service.status').status, 'fail')
        self.assertEqual(check(item, 'review.reinstatement').status, 'pass')
        # the reconciliation as usual: the biopsy code is no longer an active proposal
        self.assertNotIn('45380', [code for codes in after.completeness['covered'].values() for code in codes])

    def test_a_planned_or_historical_value_is_worded_as_such(self):
        for value, word in (('planned', 'planned'), ('historical', 'historical'), ('cancelled', 'cancelled'),
                            ('not_performed', 'negated')):
            text = stating(NOT_DONE[value])  # the passage the readers read with that status
            after = run(text, STATUS_CODES, [confirm(text, NOT_DONE[value], fact='performed_status',
                                                     family='gi.colonoscopy', key='sel:0', value=value)])
            self.assertIn(f'(documented as {word})', proposal(after, 'sel:0').exclusion_reason, value)

    def test_a_second_confirmation_on_the_confirmed_assessment_is_bound_to_its_proposal(self):
        excluded = confirm(STATUS_AND_EXTENT_DENIED, DENIED_BX, fact='performed_status', family='gi.colonoscopy',
                           key='sel:0', value='not_performed', cid='conf-a')
        first = run(STATUS_AND_EXTENT_DENIED, STATUS_CODES, [excluded], participants=CONFIGURED)
        self.assertEqual([(p.key, p.code, p.bucket) for p in first.proposals],
                         [('sel:1', '45385', 'selected'), ('sel:0', '45380', 'excluded')])
        self.assertEqual(questions(proposal(first, 'sel:1')), [('proposal', 'gi.colonoscopy', 'extent')])
        # a reviewer answers 45385's extent question as that assessment asks it: the identity 45385 records there is the
        # one these inputs give it without any confirmation, so the next assessment finds it
        unconfirmed = run(STATUS_AND_EXTENT_DENIED, STATUS_CODES, participants=CONFIGURED)
        self.assertEqual(binding(proposal(first, 'sel:1')), binding(proposal(unconfirmed, 'sel:1')))
        extent = replace(confirm(STATUS_AND_EXTENT_DENIED, LAND, fact='extent', family='gi.colonoscopy', key='sel:1',
                                 value='cecum', cid='conf-b'), **binding(proposal(first, 'sel:1')))
        second = run(STATUS_AND_EXTENT_DENIED, STATUS_CODES, [excluded, extent], participants=CONFIGURED)
        self.assertEqual((proposal(second, 'sel:1').code, proposal(second, 'sel:1').status), ('45385', 'ready'))
        self.assertEqual(proposal(second, 'sel:0'), proposal(first, 'sel:0'))
        self.assertEqual(second, run(STATUS_AND_EXTENT_DENIED, STATUS_CODES, [extent, excluded],
                                     participants=CONFIGURED))  # whatever the order

    def test_a_value_that_is_neither_performed_nor_not_performed_is_not_read(self):
        before = run(STATUS_ONLY, STATUS_CODES)
        for value in ('attempted_incomplete', 'incomplete', 'unclear', 'yes', 'performed in part'):
            after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, SPECIMEN, fact='performed_status',
                                                            family='gi.colonoscopy', key='sel:0', value=value)])
            self.assertEqual(without_confirmations(after), before, value)
            self.assertIn('its value is neither performed nor a status documenting the service as not performed',
                          encounter_check(after, 'confirmations.ignored').detail, value)


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
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
            self.assertIn("the confirmation of extent reached for proposal sel:0 (45385): its passage is not an exact "
                          "slice of this revision's text", warn.detail)
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
        self.assertIn('the confirmation of separate em for proposal sel:0 (99213): a confirmation answers whether a '
                      'code was performed or a required fact the readers take from the document',
                      encounter_check(after, 'confirmations.ignored').detail)

    def test_a_confirmation_never_approves_anything(self):
        after = run(STATUS_STATED, STATUS_CODES, [confirm(STATUS_STATED, DONE_BX, fact='performed_status',
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
                  confirm(STATUS_ONLY, SPECIMEN, fact='extent', family='gi.colonoscopy', key='sel:0',
                          value='cecum'),  # the extent is read
                  confirm(STATUS_ONLY, SPECIMEN, fact='extent', family='gi.colonoscopy', value='cecum')):  # nor asked
            after = run(STATUS_ONLY, STATUS_CODES, [c])
            self.assertEqual(without_confirmations(after), before, c)
            self.assertIn(engine.NOT_OPEN, encounter_check(after, 'confirmations.ignored').detail, c)
        # a confirmation naming no proposal of these inputs is bound to none: never read by the key it names
        nowhere = confirm(STATUS_ONLY, SPECIMEN, fact='performed_status', family='gi.colonoscopy', key='sel:7',
                          value='performed')
        after = run(STATUS_ONLY, STATUS_CODES, [nowhere])
        self.assertEqual(without_confirmations(after), before)
        self.assertIn(engine.UNBOUND, encounter_check(after, 'confirmations.ignored').detail)

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

    def test_a_passage_shorter_than_any_located_quote_is_not_read(self):
        """I7 (refutation round 1, EV-3): a quote with fewer than 8 non-space characters is never located, so it is
        never a participant's located passage - "NOT", a slice of the synthetic banner, is not read; 8 characters
        are."""
        before = run(STATUS_ONLY, STATUS_CODES)
        for passage in ('NOT', 'Specime', ' jar 2, a'):
            after = run(STATUS_ONLY, STATUS_CODES, [confirm(STATUS_ONLY, passage, fact='performed_status',
                                                            family='gi.colonoscopy', key='sel:0', value='performed',
                                                            by=('astra',))])
            self.assertEqual(without_confirmations(after), before, passage)
            self.assertIn(engine.TOO_SHORT, encounter_check(after, 'confirmations.ignored').detail, passage)
        # eight characters are read - here "biopsies" in the sentence that states the biopsy done (refutation round 2,
        # EV2-1: the passage is read in its whole sentence, as the act the code accounts for)
        read_ = run(STATUS_STATED, STATUS_CODES, [confirm(STATUS_STATED, 'biopsies', fact='performed_status',
                                                          family='gi.colonoscopy', key='sel:0', value='performed',
                                                          evidence=(span(STATUS_STATED, 'biopsies', nth=1),))])
        self.assertEqual(proposal(read_, 'sel:0').status, 'ready')

    def test_confirmations_of_one_question_that_disagree_are_all_left_unread(self):
        before = run(TWO_EXTENTS, COLON_CODES)
        a = confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum', cid='a')
        b = replace(a, value='terminal ileum', confirmation_id='b')
        after = run(TWO_EXTENTS, COLON_CODES, [a, b])
        self.assertEqual(without_confirmations(after), before)
        detail = encounter_check(after, 'confirmations.ignored').detail
        self.assertIn('2 confirmations not read', detail)
        self.assertIn(engine.DISAGREEING, detail)
        # two status confirmations each read on its own passage (refutation round 2, EV2-1: the biopsy stated done, and
        # stated planned), which disagree: neither is read
        text = STATUS_STATED + NOT_DONE['planned'] + '\n'
        status_a = confirm(text, DONE_BX, fact='performed_status', family='gi.colonoscopy', key='sel:0',
                           value='performed', cid='a')
        status_b = confirm(text, NOT_DONE['planned'], fact='performed_status', family='gi.colonoscopy', key='sel:0',
                           value='planned', cid='b')
        both = run(text, STATUS_CODES, [status_a, status_b])
        self.assertEqual(without_confirmations(both), run(text, STATUS_CODES))
        self.assertEqual(both.completeness['confirmations']['ignored'],
                         [{'id': 'a', 'why': engine.DISAGREEING}, {'id': 'b', 'why': engine.DISAGREEING}])

    def test_confirmations_that_agree_are_read_together(self):
        a = confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum', cid='a')
        b = replace(a, value='  Cecum ', confirmation_id='b', located_by=('astra', 'fable'),
                    confirmed_by='Second Synthetic-Reviewer (fictional)')
        item = proposal(run(TWO_EXTENTS, COLON_CODES, [a, b]), 'sel:0')
        self.assertEqual((item.status, item.support['confirmed']), ('ready', ['a', 'b']))
        detail = check(item, 'facts.required').detail
        self.assertIn(f"extent reached = cecum, {WORDS}; and from Astra's and Fable's located passage by Second "
                      'Synthetic-Reviewer (fictional)', detail)


# EV-4: a confirmed value the readers would read as an incomplete procedure - an extent short of the depth the procedure
# calls for, a failed cannulation - is read as they read the same fact.
COLON_HEAD = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n')
POLYP_LINE = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
SHORT_PREP = 'The colonoscope was advanced only to the splenic flexure because of poor preparation.'
PHOTOS = 'Photos: splenic flexure reached, scope withdrawn.'
SHORT_READ = COLON_HEAD + SHORT_PREP + '\n' + POLYP_LINE  # the readers read the extent: short of the cecum
SHORT_UNREAD = COLON_HEAD + POLYP_LINE + PHOTOS + '\n'  # they read none: the photos line is no reach they read
ERCP_HEAD = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
             'Procedure: ERCP\nThe duodenoscope was advanced to the major papilla. ' + STENT + '\n')
NO_ACCESS = 'Duct access note: no cannulation achieved; procedure ended.'
ERCP_READ = ERCP_HEAD + 'Cannulation of the bile duct failed despite multiple attempts.\n'
ERCP_UNREAD = ERCP_HEAD + NO_ACCESS + '\n'
ANTRUM = 'Biopsies of the gastric antrum were taken with cold forceps.'
EGD_UNREAD = (HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\nProcedure: EGD\n' + ANTRUM + '\n' + DUODENUM
              + '\n')  # an EGD calls for the duodenal bulb


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class IncompleteTests(SimpleTestCase):
    """HARNESS.md 11.3: "the engine reads the confirmed fact as documented by the cited passage" - through the readers'
    own path (I2), so a confirmed fact that they would read as an incomplete procedure gives the proposal their
    incomplete result: the service.incomplete warn and the modifier 52/53 consideration (refutation round 1, EV-4)."""

    def test_a_confirmed_extent_short_of_the_cecum_is_read_as_the_readers_read_one(self):
        read_ = proposal(run(SHORT_READ, (('45385', SNARE),)), 'sel:0')
        self.assertEqual(check(read_, 'service.incomplete').status, 'warn')  # the readers' own reading of it
        before = proposal(run(SHORT_UNREAD, (('45385', SNARE),)), 'sel:0')
        self.assertEqual(questions(before), [('proposal', 'gi.colonoscopy', 'extent')])
        after = proposal(run(SHORT_UNREAD, (('45385', SNARE),), [confirm(
            SHORT_UNREAD, PHOTOS, fact='extent', family='gi.colonoscopy', key='sel:0', value='splenic flexure')]),
            'sel:0')
        self.assertEqual((after.status, questions(after)), ('ready', []))
        warn = check(after, 'service.incomplete')
        self.assertEqual((warn.status, warn.source), ('warn', checks.CONFIRMATION_SOURCE))
        self.assertIn(f'extent reached = splenic flexure, {WORDS} (“{PHOTOS}”)', warn.detail)
        self.assertIn('short of the cecum', warn.detail)
        self.assertIn('Kept for review: not treated as completed and not excluded.', warn.detail)
        self.assertEqual(after.modifier_considerations, read_.modifier_considerations)  # the 52/53 consideration
        self.assertIn('Service status: incomplete (performed in part)', after.rationale)
        self.assertIn('read as incomplete (performed in part)', check(after, 'service.status').detail)
        self.assertNotEqual(after.fingerprint, proposal(run(SHORT_UNREAD, (('45385', SNARE),), [confirm(
            SHORT_UNREAD, PHOTOS, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum')]),
            'sel:0').fingerprint)
        # an extent at or beyond the cecum is a completed examination, as before
        for value in ('cecum', 'terminal ileum'):
            complete = proposal(run(SHORT_UNREAD, (('45385', SNARE),), [confirm(
                SHORT_UNREAD, PHOTOS, fact='extent', family='gi.colonoscopy', key='sel:0', value=value)]), 'sel:0')
            self.assertEqual(complete.status, 'ready', value)
            self.assertIsNone(check(complete, 'service.incomplete'), value)
            self.assertEqual(complete.modifier_considerations, before.modifier_considerations, value)
            self.assertIn('Service status: performed', complete.rationale, value)

    def test_a_confirmed_failed_cannulation_is_read_as_the_readers_read_one(self):
        read_ = proposal(run(ERCP_READ, (('43274', STENT),)), 'sel:0')
        self.assertEqual(check(read_, 'service.incomplete').status, 'warn')
        self.assertEqual(questions(proposal(run(ERCP_UNREAD, (('43274', STENT),)), 'sel:0')),
                         [('proposal', 'gi.ercp', 'cannulation')])
        failed = proposal(run(ERCP_UNREAD, (('43274', STENT),), [confirm(
            ERCP_UNREAD, NO_ACCESS, fact='cannulation', family='gi.ercp', key='sel:0', value='failed')]), 'sel:0')
        warn = check(failed, 'service.incomplete')
        self.assertEqual(warn.status, 'warn')
        self.assertIn(f'cannulation outcome = failed, {WORDS} (“{NO_ACCESS}”)', warn.detail)
        self.assertIn('a failed cannulation', warn.detail)
        self.assertEqual(failed.modifier_considerations, read_.modifier_considerations)
        self.assertIn('Service status: incomplete (performed in part)', failed.rationale)
        succeeded = proposal(run(ERCP_UNREAD, (('43274', STENT),), [confirm(
            ERCP_UNREAD, NO_ACCESS, fact='cannulation', family='gi.ercp', key='sel:0', value='successful')]), 'sel:0')
        self.assertEqual(succeeded.status, 'ready')
        self.assertIsNone(check(succeeded, 'service.incomplete'))

    def test_an_upper_extent_is_placed_against_the_depth_the_named_procedure_calls_for(self):
        codes = (('43239', ANTRUM[:-1]),)
        self.assertEqual(questions(proposal(run(EGD_UNREAD, codes), 'sel:0')), [('proposal', 'gi.egd', 'extent')])
        short = proposal(run(EGD_UNREAD, codes, [confirm(EGD_UNREAD, ANTRUM, fact='extent', family='gi.egd',
                                                        key='sel:0', value='stomach')]), 'sel:0')
        self.assertIn('short of the duodenal bulb', check(short, 'service.incomplete').detail)
        for value in ('duodenal bulb', 'second part of duodenum'):
            deep = proposal(run(EGD_UNREAD, codes, [confirm(EGD_UNREAD, DUODENUM, fact='extent', family='gi.egd',
                                                           key='sel:0', value=value)]), 'sel:0')
            self.assertEqual(deep.status, 'ready', value)
            self.assertIsNone(check(deep, 'service.incomplete'), value)

    def test_a_value_cpt_studio_cannot_place_is_not_read(self):
        """Fail closed: a value that is not one of routing's landmarks (for the extent) or successful or failed (for a
        cannulation) cannot be read as complete or incomplete, so it answers nothing and the question stays open."""
        for text, codes, phrase, fact, family, value in (
                (SHORT_UNREAD, (('45385', SNARE),), PHOTOS, 'extent', 'gi.colonoscopy', 'ileocolic anastomosis'),
                (SHORT_UNREAD, (('45385', SNARE),), PHOTOS, 'extent', 'gi.colonoscopy', 'splenic flexure only'),
                (SHORT_UNREAD, (('45385', SNARE),), PHOTOS, 'extent', 'gi.colonoscopy', 'incomplete: splenic flexure'),
                (ERCP_UNREAD, (('43274', STENT),), NO_ACCESS, 'cannulation', 'gi.ercp', 'no cannulation achieved'),
                (ERCP_UNREAD, (('43274', STENT),), NO_ACCESS, 'cannulation', 'gi.ercp', 'bile duct cannulated')):
            before = run(text, codes)
            after = run(text, codes, [confirm(text, phrase, fact=fact, family=family, key='sel:0', value=value)])
            self.assertEqual(without_confirmations(after), before, value)
            self.assertIn(engine.UNPLACED, encounter_check(after, 'confirmations.ignored').detail, value)


# EV-1: a revision's assessments do not keep their keys - a code a first reading listed with no located quote is
# selected, at its first reading's place, once its peer review locates it; a later reading or a new answer selects
# other codes - so a question's key names another proposal later. Each passage below leaves its code's act in doubt,
# and the specimen log documents one act each.
DOUBTS = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
          'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
          'The colonoscope was advanced to the cecum and the examination was completed.\n'
          'It is unclear whether biopsies of the ascending colon lesion were taken.\n'
          'It is unclear whether the sigmoid polyp was removed with a hot snare.\n'
          'Specimen log: jar 1, sigmoid polyp, hot snare.\n' + SPECIMEN + '\n')
HEDGED_SNARE = 'the sigmoid polyp was removed with a hot snare'
JAR_1 = 'Specimen log: jar 1, sigmoid polyp, hot snare.'
UNLOCATED_SNARE = 'hot snare polypectomy of the sigmoid polyp'  # not in the text: never evidence
# Refutation round 2, EV2-1: the specimen lines name neither act, so a status is confirmed on a sentence that states
# each act done; the codes cite the hedges, so the two readers disagree and each stays held on its status.
DONE_SNARE = 'The sigmoid polyp was removed with a hot snare.'
DOUBTS_STATED = DOUBTS + DONE_BX + '\n' + DONE_SNARE + '\n'


def rows(result):
    return [(p.key, p.code, p.status) for p in result.proposals]


def made_for(result, key, phrase, cid='conf-1', text=DOUBTS_STATED):
    """A reviewer's confirmation that the code of proposal ``key`` of ``result`` was performed, on ``phrase``, bound to
    that proposal as the confirmation endpoint binds it."""
    return replace(confirm(text, phrase, fact='performed_status', family='gi.colonoscopy', key=key,
                           value='performed', by=('astra',), cid=cid), **binding(proposal(result, key)))


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class BindingTests(SimpleTestCase):
    """A confirmation answers the proposal it was made for, wherever that proposal's key is later, and never the
    proposal that holds its key afterwards (HARNESS.md 11.3, 12.5)."""

    def assertNeverAnswers(self, result, key, code):
        item = proposal(result, key)
        self.assertEqual((item.code, item.status), (code, 'needs_clarification'))
        self.assertNotIn('confirmed', item.support)
        self.assertNotIn('confirmed from', check(item, 'service.status').detail)

    def test_a_peer_review_never_selects_a_code_ahead_so_the_confirmation_stays_with_its_proposal(self):
        """Moved by refutation round 6 (R6-MEANING, the session's D14). A peer review's additional code selected
        ahead of the first reading's 45380 (both the participant's own proposals under Corti's failure), and the
        confirmation followed 45380 to its new key. A participant's code is never selected now: the peer review's 45385
        is listed, 45380 is Corti's and keeps its key, and the confirmation made for it is read for it there. That a
        confirmation follows its proposal wherever its key moves is pinned below by a new answer of the proposal
        provider, the one way keys still move."""
        first = [participant_code(DOUBTS_STATED, '45385', UNLOCATED_SNARE),
                 participant_code(DOUBTS_STATED, '45380', UNCLEAR)]
        codes = (('45380', UNCLEAR),)
        one = run(DOUBTS_STATED, codes, participants=[read('astra', first)])
        self.assertEqual(rows(one), [('sel:0', '45380', 'needs_clarification'), ('altp:0', '45385', 'informational')])
        made = made_for(one, 'sel:0', DONE_BX)  # on assess #1: 45380's biopsy, on the passage stating it done
        later = [reviewed('astra', first, peer('astra', additional=[
            participant_code(DOUBTS_STATED, '45385', HEDGED_SNARE)]))]
        self.assertEqual(rows(run(DOUBTS_STATED, codes, participants=later)),
                         [('sel:0', '45380', 'needs_clarification'), ('altp:0', '45385', 'informational')])
        two = run(DOUBTS_STATED, codes, [made], participants=later)
        kept = proposal(two, 'sel:0')
        self.assertEqual((kept.code, kept.status, kept.support['confirmed']), ('45380', 'ready', ['conf-1']))
        self.assertEqual([(a['code'], a['proposal_key']) for a in two.completeness['confirmations']['applied']],
                         [('45380', 'sel:0')])
        self.assertIn('45380 (sel:0): performed on the date of service',
                      encounter_check(two, 'confirmations.applied').detail)

    def test_a_participant_read_after_reconcile_never_takes_the_confirmation(self):
        """Moved by refutation round 6 (R6-MEANING, the session's D14): Astra's reading, read after a reconcile,
        selected its 45385 ahead of 45380 (both the participants' own proposals under Corti's failure). It is listed
        now, never selected, so it takes no key and no confirmation, and Corti's 45380 reads its own. (Refutation cycle
        2 had held it; cycle 3 lists a participant's code for an act read in doubt itself again.)"""
        fable = read('fable', [participant_code(DOUBTS_STATED, '45380', UNCLEAR)])
        early = [ParticipantInput('astra', 'unknown', reason='the outcome of its request is unknown'), fable]
        codes = (('45380', UNCLEAR),)
        one = run(DOUBTS_STATED, codes, participants=early)
        self.assertEqual(rows(one), [('sel:0', '45380', 'needs_clarification')])
        made = made_for(one, 'sel:0', DONE_BX)
        later = [read('astra', [participant_code(DOUBTS_STATED, '45385', HEDGED_SNARE)]), fable]
        two = run(DOUBTS_STATED, codes, [made], participants=later)
        self.assertEqual([(key, code) for key, code, _ in rows(two)], [('sel:0', '45380'), ('altp:0', '45385')])
        listed = proposal(two, 'altp:0')
        self.assertEqual((listed.status, listed.support.get('confirmed')), ('informational', None))
        self.assertEqual((proposal(two, 'sel:0').code, proposal(two, 'sel:0').status), ('45380', 'ready'))

    def test_a_new_answer_that_selects_a_code_ahead_never_takes_the_confirmation(self):
        # moved by refutation round 6 (R6-MEANING, the session's D14): 45385 was Astra's own proposal (sel:1); it is
        # Corti's here, Astra recorded on it, since a participant's code is never a proposal now
        astra = [read('astra', [participant_code(DOUBTS_STATED, '45385', HEDGED_SNARE)])]
        one = run(DOUBTS_STATED, (('45380', UNCLEAR), ('45385', HEDGED_SNARE)), participants=astra)
        self.assertEqual(rows(one), [('sel:0', '45380', 'needs_clarification'),
                                     ('sel:1', '45385', 'needs_clarification')])
        made = made_for(one, 'sel:1', DONE_SNARE)  # 45385's snare removal, on the passage stating it done
        # another context: the proposal provider now also selects 45384 on the hedged snare passage, ahead of 45385
        two = run(DOUBTS_STATED, (('45380', UNCLEAR), ('45384', HEDGED_SNARE), ('45385', HEDGED_SNARE)), [made],
                  participants=astra)
        self.assertEqual([(key, code) for key, code, _ in rows(two)], [('sel:0', '45380'), ('sel:1', '45384'),
                                                                      ('sel:2', '45385')])
        self.assertNeverAnswers(two, 'sel:1', '45384')
        self.assertNeverAnswers(two, 'sel:0', '45380')
        self.assertEqual((proposal(two, 'sel:2').code, proposal(two, 'sel:2').status), ('45385', 'ready'))

    def test_a_proposal_read_from_other_passages_is_another_proposal(self):
        """A confirmation made for 45380 read from one passage is not read for 45380 read from another: the reviewer
        confirmed the question that reading raised (the identity changes with the passages, never with the checks).
        Moved by refutation round 6 (R6-MEANING, the session's D14): the participants' 45380 read from more passages
        (Astra's quote joining Fable's) was the case; a participant's quotes are read by no reader now, so it is Corti's
        45380 cited on another passage."""
        fable = read('fable', [participant_code(DOUBTS_STATED, '45380', UNCLEAR)])
        one = run(DOUBTS_STATED, (('45380', UNCLEAR),), participants=[fable])
        made = made_for(one, 'sel:0', DONE_BX)
        other = (('45380', 'It is unclear whether biopsies'),)
        before = run(DOUBTS_STATED, other, participants=[fable])
        after = run(DOUBTS_STATED, other, [made], participants=[fable])
        self.assertEqual(without_confirmations(after), before)
        self.assertNeverAnswers(after, 'sel:0', '45380')
        self.assertIn(engine.MOVED, encounter_check(after, 'confirmations.ignored').detail)
        self.assertEqual(after.completeness['confirmations']['ignored'], [{'id': 'conf-1', 'why': engine.MOVED}])

    def test_a_confirmation_that_names_no_proposal_is_never_read_by_its_key(self):
        before = run(STATUS_ONLY, STATUS_CODES, participants=CONFIGURED)
        unbound = confirm(STATUS_ONLY, SPECIMEN, fact='performed_status', family='gi.colonoscopy', key='sel:0',
                          value='performed')
        for c in (unbound, replace(unbound, proposal_code='45380'),
                  replace(unbound, proposal_identity=binding(proposal(before, 'sel:0'))['proposal_identity'])):
            after = run(STATUS_ONLY, STATUS_CODES, [c], participants=CONFIGURED, bind=False)
            self.assertEqual(without_confirmations(after), before, c)
            self.assertIn(engine.UNBOUND, encounter_check(after, 'confirmations.ignored').detail, c)

    # Refutation round 2, FG2-1: the identity is the sha256 of the proposal's code, family, profile version, cited
    # passages, units and the context values its decision depends on (HARNESS.md 12.5, engine._identity). Each case
    # keeps the code and the passages and changes one of the rest: the confirmation made for the proposal as it was is
    # not read for it as it is now - it is listed as moved - so dropping any of them from the identity fails here.
    def assertMoved(self, made, result, key):
        item = proposal(result, key)
        self.assertEqual(item.status, 'needs_clarification')
        self.assertNotIn('confirmed', item.support)
        self.assertEqual(result.completeness['confirmations'], {'applied': [], 'ignored': [{'id': 'conf-1',
                                                                                           'why': engine.MOVED}]})

    def extent_made(self, text, codes, **kwargs):
        """The confirmation of sel:0's extent, bound to sel:0 as these inputs make it."""
        made = bound(confirm(text, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum'), text,
                     codes, **kwargs)
        self.assertEqual(proposal(run(text, codes, [made], bind=False, participants=CONFIGURED, **kwargs),
                                  'sel:0').status, 'ready')  # the control: it answers that proposal
        return made

    def test_another_service_date_is_another_proposal(self):
        made = self.extent_made(TWO_EXTENTS, COLON_CODES)
        later = TWO_EXTENTS.replace('Date of service: 2026-10-14', 'Date of service: 2026-10-21')
        self.assertEqual(len(later), len(TWO_EXTENTS))  # the passages stay where they were
        result = assess(text=later, pages=(), context=gi_context.extract_context(later),
                        routing=detect.route(later, date(2026, 10, 21)),
                        normalized=NormalizedResponse('corti', 'test@1', tuple(
                            ProviderCode('selected', 'cpt', v, 'UNVERIFIED PROVIDER WORDING', (span(later, q),))
                            for v, q in COLON_CODES)),
                        reference=REFERENCE, service_date=date(2026, 10, 21), provider_status='succeeded',
                        participants=CONFIGURED, confirmed=[made])
        self.assertEqual(proposal(result, 'sel:0').code, '45385')
        self.assertMoved(made, result, 'sel:0')

    def test_another_billing_or_setting_of_a_visit_is_another_proposal(self):
        codes = (('99213', SEEN),)
        for name, value in (('billing_context', 'professional'), ('setting', 'hospital_outpatient')):
            with self.subTest(name):
                made = bound(confirm(VISIT, TIME, fact='em_basis', family='gi.office_em', key='sel:0', value='time'),
                             VISIT, codes)
                context = {**gi_context.extract_context(VISIT), name: Fact(name, value, 'document')}
                self.assertNotEqual(context[name], gi_context.extract_context(VISIT).get(name))
                result = assess(text=VISIT, pages=(), context=context, routing=detect.route(VISIT, DAY),
                                normalized=NormalizedResponse('corti', 'test@1', (ProviderCode(
                                    'selected', 'cpt', '99213', 'UNVERIFIED PROVIDER WORDING', (span(VISIT, SEEN),)),)),
                                reference=REFERENCE, service_date=DAY, provider_status='succeeded',
                                participants=CONFIGURED, confirmed=[made])
                self.assertMoved(made, result, 'sel:0')

    def test_other_units_are_another_proposal(self):
        made = self.extent_made(TWO_EXTENTS, COLON_CODES)
        twice = (('45385', SNARE), ('45385', SNARE), ('45380', BIOPSY))  # the same code selected twice: two units
        result = run(TWO_EXTENTS, twice, [made], bind=False, participants=CONFIGURED)
        self.assertEqual((proposal(result, 'sel:0').code, proposal(result, 'sel:0').units), ('45385', 2))
        self.assertMoved(made, result, 'sel:0')

    def test_another_profile_version_is_another_proposal(self):
        made = self.extent_made(TWO_EXTENTS, COLON_CODES)
        from studio.gi.profiles import PROFILES
        revised = replace(PROFILES['gi.colonoscopy'], version=PROFILES['gi.colonoscopy'].version + '-revised')
        with mock.patch.dict(engine.PROFILES, {'gi.colonoscopy': revised}):
            result = run(TWO_EXTENTS, COLON_CODES, [made], bind=False, participants=CONFIGURED)
        self.assertMoved(made, result, 'sel:0')

    def test_the_identity_is_recorded_only_with_a_participant_and_never_moves_with_checks_or_confirmations(self):
        plain = run(STATUS_STATED, STATUS_CODES)
        self.assertFalse(any('identity' in p.support for p in plain.proposals))  # none configured: unchanged (I1)
        configured = run(STATUS_STATED, STATUS_CODES, participants=CONFIGURED)
        self.assertTrue(all(len(p.support['identity']) == 64 for p in configured.proposals))
        confirmed = run(STATUS_STATED, STATUS_CODES, [confirm(STATUS_STATED, DONE_BX, fact='performed_status',
                                                              family='gi.colonoscopy', key='sel:0', value='performed')],
                        participants=CONFIGURED)
        self.assertEqual(proposal(confirmed, 'sel:0').status, 'ready')
        self.assertNotEqual(proposal(confirmed, 'sel:0').fingerprint, proposal(configured, 'sel:0').fingerprint)
        self.assertEqual([binding(p) for p in confirmed.proposals], [binding(p) for p in configured.proposals])
        # a code's identity is its own reading: another code beside it changes its checks, never its identity
        alone = run(STATUS_STATED, (('45385', SNARE),), participants=CONFIGURED)
        self.assertNotEqual(proposal(alone, 'sel:0').fingerprint, proposal(configured, 'sel:1').fingerprint)
        self.assertEqual(binding(proposal(alone, 'sel:0')), binding(proposal(configured, 'sel:1')))


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
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

    def test_an_iterator_is_read_once_as_the_sequence_it_yields(self):
        """An exhausted or empty iterator is no input (I1); a non-empty one is read as its items, never dropped."""
        c = bound(confirm(TWO_EXTENTS, LAND, fact='extent', family='gi.colonoscopy', key='sel:0', value='cecum'),
                  TWO_EXTENTS, COLON_CODES)
        self.assertEqual(run(TWO_EXTENTS, COLON_CODES, iter(())), run(TWO_EXTENTS, COLON_CODES))
        self.assertEqual(run(TWO_EXTENTS, COLON_CODES, (x for x in [c])), run(TWO_EXTENTS, COLON_CODES, [c]))
        self.assertEqual(assess(text=TWO_EXTENTS, pages=(), context=gi_context.extract_context(TWO_EXTENTS),
                                routing=detect.route(TWO_EXTENTS, DAY), normalized=None, reference=REFERENCE,
                                service_date=DAY, provider_status='failed', participants=iter(())),
                         run(TWO_EXTENTS, provider_status='failed'))

    def test_keys_and_fingerprints_are_the_same_whatever_the_order_given(self):
        given = [confirm(STATUS_AND_EXTENT_DENIED, DENIED_BX, fact='performed_status', family='gi.colonoscopy',
                         key='sel:0', value='not_performed', cid='a'),
                 confirm(STATUS_AND_EXTENT_DENIED, LAND, fact='extent', family='gi.colonoscopy', key='sel:1',
                         value='cecum', cid='b'),
                 confirm(STATUS_AND_EXTENT_DENIED, LAND, fact='extent', family='gi.egd', key='sel:1', value='cecum',
                         cid='c')]
        first = run(STATUS_AND_EXTENT_DENIED, STATUS_CODES, given)
        for order in (given[::-1], [given[1], given[2], given[0]]):
            again = run(STATUS_AND_EXTENT_DENIED, STATUS_CODES, order)
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
