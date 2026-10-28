"""Engine @4: provider proposals reconciled with the documented-service inventory (studio/validation/reconcile.py).

Each test builds a fresh synthetic document and a provider response whose passages are exact, then runs the real
routing, the real inventory and the engine. The expected outcome is written here, outside the coding input.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.gi import context as gi_context
from studio.gi import detect
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import ENGINE_VERSION, assess

DAY = date(2026, 10, 14)


def span(text, phrase, nth=0):
    start = -1
    for _ in range(nth + 1):
        start = text.index(phrase, start + 1)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def run(text, codes, *, second=None, second_scope=None, user_values=None):
    facts = gi_context.merge_user_values(gi_context.extract_context(text), user_values or {})
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    response = NormalizedResponse('replay', 'test@1', tuple(codes))
    return assess(text=text, pages=(), context=facts, routing=detect.route(text, day), normalized=response,
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded',
                  second=second, second_scope=second_scope)


def sel(code, *spans):
    return ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING', tuple(spans))


def proposal(result, code):
    found = [p for p in result.proposals if p.code == code and p.bucket != 'alternative']
    assert found, f'{code} not in {[p.code for p in result.proposals]}'
    return found[0]


def check(item, check_id):
    return next(c for c in item.checks if c.id == check_id)


BIDIRECTIONAL = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Same-session upper and lower endoscopy (procedure)
Date of service: 2026-10-14

Place of service: Ambulatory surgery center
Upper endoscopy report
The gastroscope was advanced to the second portion of the duodenum. Mild antral erythema was seen. No gastric ulcer
or mass was identified. Two cold forceps biopsies were taken from the antrum and two from the gastric body.
Colonoscopy report
The colonoscope was advanced to the cecum; the examination was complete and was not cut short. A 9 mm pedunculated
polyp in the sigmoid colon was removed with a hot snare. A separate 12 mm flat lesion in the ascending colon was
biopsied with cold forceps and left in place for a later resection. No other lesion was treated. One clip was placed
prophylactically at the polypectomy site.
Nursing checklist
Recorded by Jo Fictional RN: India ink tattoo [X] Performed [ ] Not performed.
Physician note: no tattoo or other submucosal injection was given at this session.
"""


class StatusFromTheDocumentedServiceTests(SimpleTestCase):
    def test_fragments_about_findings_never_hold_a_documented_biopsy(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('43239', span(text, 'Mild antral erythema was seen.'), span(text, 'No gastric ulcer')),
                            sel('45385', span(text, 'was removed with a hot snare'))])
        self.assertEqual(result.engine_version, ENGINE_VERSION)
        egd = proposal(result, '43239')
        self.assertEqual(egd.status, 'ready', egd.checks)
        support = check(egd, 'evidence.support')
        self.assertEqual(support.status, 'warn')  # the provider cited findings, not the biopsy
        self.assertTrue(any('biopsies were taken' in s['text'] for s in egd.support['source']))
        self.assertEqual(sorted(egd.support['unrelated']), [0, 1])

    def test_a_complete_examination_with_an_unresected_lesion_has_no_incomplete_warning(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('45385', span(text, 'was removed with a hot snare'))])
        colon = proposal(result, '45385')
        self.assertNotIn('service.incomplete', {c.id for c in colon.checks})
        self.assertFalse(any('52 or 53' in m for m in colon.modifier_considerations))

    def test_the_separately_biopsied_lesion_is_unresolved_and_nothing_is_added(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('43239', span(text, 'Two cold forceps biopsies were taken')),
                            sel('45385', span(text, 'was removed with a hot snare'))])
        items = result.completeness['unresolved_items']
        self.assertEqual([(i['family'], i['act']) for i in items], [('gi.colonoscopy', 'biopsy')], items)
        self.assertNotIn('45380', [p.code for p in result.proposals])
        self.assertEqual(result.completeness['state'], 'incomplete')
        self.assertEqual(check_encounter(result, 'services.unresolved').status, 'warn')

    def test_separate_lesions_are_a_modifier_consideration_never_an_assignment(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('45385', span(text, 'was removed with a hot snare')),
                            sel('45380', span(text, 'was\nbiopsied with cold forceps'))])
        biopsy = proposal(result, '45380')
        self.assertTrue(any('59 or XS' in m for m in biopsy.modifier_considerations), biopsy.modifier_considerations)
        # the colonoscopy is accounted for; the upper endoscopy has no proposal in this response and stays unresolved
        self.assertEqual([(i['family'], i['act']) for i in result.completeness['unresolved_items']], [('gi.egd', '')])

    def test_the_conflicting_tattoo_is_a_question_with_both_sides(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('45385', span(text, 'was removed with a hot snare'))])
        conflicts = result.services['conflicts']
        self.assertEqual([c['subject'] for c in conflicts], ['tattoo'])
        roles = {side['role'] for side in conflicts[0]['sides']}
        self.assertEqual(roles, {'nursing', 'physician'})
        question = next(c for c in result.clarifications if c.fact == 'conflict:tattoo')
        self.assertEqual(question.scope, 'service')
        self.assertIn('nursing entry', question.reason)
        self.assertIn('physician entry', question.reason)

    def test_a_tattoo_code_in_conflict_is_held_not_ready(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('45385', span(text, 'was removed with a hot snare')),
                            sel('45381', span(text, 'India ink tattoo [X] Performed'))])
        self.assertEqual(proposal(result, '45381').status, 'needs_clarification')

    def test_the_prophylactic_clip_is_not_reported_separately(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('45385', span(text, 'was removed with a hot snare'))])
        self.assertTrue(any(b['act'] == 'clip' for b in result.completeness['bundled']))


def check_encounter(result, check_id):
    return next(c for c in result.encounter_checks if c.id == check_id)


OFFICE = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Gastroenterology clinic visit - progress note
Date of service: 2026-10-14

Place of service: Office
Patient status: Established; last seen by Dr. Fictional on 2026-05-02.
History: colonoscopy in 2022 with two adenomas removed.
Assessment: bloating improving. Plan: surveillance colonoscopy to be scheduled for 2027.
I spent 34 minutes on the date of the encounter, including review of the prior colonoscopy report and counselling.
"""


class OfficeVisitTests(SimpleTestCase):
    def test_a_historical_reference_in_its_passage_never_excludes_today_s_visit(self):
        text = OFFICE
        result = run(text, [sel('99214', span(text, 'last seen by Dr. Fictional on 2026-05-02'),
                                span(text, 'I spent 34 minutes on the date of the encounter'))])
        visit = proposal(result, '99214')
        self.assertEqual(visit.bucket, 'selected', visit.exclusion_reason)
        self.assertEqual(visit.status, 'ready', [c.detail for c in visit.checks if c.status != 'pass'])
        self.assertEqual(visit.support['unrelated'], [0])  # the earlier visit does not support today's

    def test_the_planned_colonoscopy_is_not_a_missed_service(self):
        result = run(OFFICE, [sel('99214', span(OFFICE, 'I spent 34 minutes'))])
        self.assertEqual(result.completeness['unresolved_items'], [])


class SparseNoteTests(SimpleTestCase):
    def test_every_materially_necessary_question_is_asked_together(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nGI follow-up\n'
                'Evaluated for intermittent dysphagia. Exam unremarkable.\nImpression: dysphagia.\n'
                'Plan: barium swallow.\nDr. Fictional\n')
        result = run(text, [])
        facts = sorted(c.fact for c in result.clarifications)
        self.assertEqual(facts, ['em_basis', 'patient_status', 'service_date', 'setting'])
        self.assertEqual(result.completeness['state'], 'incomplete')


class DateConflictTests(SimpleTestCase):
    def test_a_member_date_unlike_the_document_s_holds_and_says_both(self):
        text = BIDIRECTIONAL
        result = run(text, [sel('45385', span(text, 'was removed with a hot snare'))],
                     user_values={'service_date': '1999-01-01'})
        date_check = check_encounter(result, 'context.service_date')
        self.assertEqual(date_check.status, 'fail')
        self.assertIn('1999-01-01', date_check.detail)
        self.assertIn('2026-10-14', date_check.detail)
        self.assertEqual(proposal(result, '45385').status, 'needs_clarification')


OFFICE_VISIT = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Gastroenterology office visit (gi clinic)
Date of service: 2026-10-14

Place of service: Office
Patient status: Established patient.
Chief complaint
Follow-up of chronic constipation.
Assessment and plan
Chronic idiopathic constipation, improved. Continue polyethylene glycol daily.
Medical decision making
Low: one stable chronic illness; prescription drug management.
Time
Total time on the date of the encounter was 24 minutes.
"""
VISIT_TIME = 'Total time on the date of the encounter was 24 minutes.'


class MemberConflictWordingTests(SimpleTestCase):
    """A member's setting or patient status unlike the document's single value is a conflict (interpretation 11). What
    is asked names both sides; it never says the document gives conflicting values, which it does not."""

    def em(self, text, **user_values):
        result = run(text, [sel('99213', span(text, VISIT_TIME))], user_values=user_values)
        item = proposal(result, '99213')
        return item, {c.fact: c for c in item.clarifications}

    def test_a_member_value_unlike_the_documented_one_is_asked_with_both_sides(self):
        for name, user, documented, label in (('setting', 'asc', 'office', 'place of service'),
                                              ('patient_status', 'new', 'established',
                                               'new or established patient status')):
            with self.subTest(name=name):
                item, asked = self.em(OFFICE_VISIT, **{name: user})
                self.assertEqual(item.status, 'needs_clarification')
                self.assertEqual(asked[name].reason, f'The {label} is in conflict. '
                                 + gi_context.USER_CONFLICT_NOTE.format(user=user, document=documented))
                facts = check(item, 'facts.required')
                self.assertEqual(facts.status, 'warn')
                self.assertIn('Member-entered encounter metadata differs from the document (both kept, neither '
                              f'used): {label}.', facts.detail)
                self.assertNotIn('Conflicting values documented', facts.detail)

    def test_controls_a_documented_conflict_and_an_agreeing_member_value(self):
        text = OFFICE_VISIT.replace('Place of service: Office\n', 'Place of service: Office\nPlace of service: 22\n')
        item, asked = self.em(text)
        self.assertEqual(item.status, 'needs_clarification')
        self.assertTrue(asked['setting'].reason.startswith('The document gives conflicting values for the place of '
                                                           'service: '), asked['setting'].reason)
        self.assertIn('Conflicting values documented: place of service.', check(item, 'facts.required').detail)
        item, asked = self.em(OFFICE_VISIT, setting='office')
        self.assertEqual((item.status, asked), ('ready', {}))


class SecondReviewMergeTests(SimpleTestCase):
    def test_only_a_selected_code_for_an_unresolved_act_is_added(self):
        text = BIDIRECTIONAL
        start = text.index('Colonoscopy report')
        end = text.index('Nursing checklist')
        excerpt = text[start:end]

        def excerpt_span(phrase):
            s = excerpt.index(phrase)
            return EvidenceSpan(0, s + start, s + start + len(phrase), phrase, True)
        second = NormalizedResponse('replay', 'test@1', (
            sel('45380', excerpt_span('biopsied with cold forceps')),
            sel('45385', excerpt_span('removed with a hot snare')),
            sel('45382', excerpt_span('One clip was placed')),
        ))
        result = run(text, [sel('43239', span(text, 'Two cold forceps biopsies were taken')),
                            sel('45385', span(text, 'was removed with a hot snare'))],
                     second=second, second_scope={'start': start, 'end': end, 'items': ['the sigmoid biopsy']})
        added = proposal(result, '45380')
        self.assertEqual(added.bucket, 'selected')
        self.assertEqual(added.support['origin'], 'second_review')
        self.assertIn('second review', added.rationale)
        alternatives = [p.code for p in result.proposals if p.bucket == 'alternative']
        self.assertIn('45382', alternatives)  # it accounts for no unresolved act: informational only
        self.assertEqual([p.code for p in result.proposals if p.bucket == 'selected'].count('45385'), 1)
        self.assertEqual(result.completeness['unresolved_items'], [])
        self.assertEqual(check_encounter(result, 'provider.second_review').status, 'info')


class CatalogueTests(SimpleTestCase):
    def test_coverage_md_is_generated_from_the_catalogue(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / 'COVERAGE.md'
        self.assertEqual(path.read_text(encoding='utf-8'), catalogue.render_markdown(),
                         'COVERAGE.md is stale: regenerate it from studio.gi.catalogue.render_markdown()')

    def test_every_reconciled_code_routes_to_its_own_family(self):
        from studio.gi.profiles import family_for_code
        wrong = {code: (p.family, family_for_code(code)) for code, p in catalogue.CODES.items()
                 if family_for_code(code) != p.family}
        self.assertEqual(wrong, {})

    def test_no_descriptor_is_held(self):
        for code, profile in catalogue.CODES.items():
            self.assertFalse(hasattr(profile, 'descriptor'))


SERVICE_STATEMENT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-14\n\n'
                     'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. {findings}\n')
CECUM_STATEMENT = 'The colonoscope was advanced to the cecum.'


class ServiceStatementIsNotTheActTests(SimpleTestCase):
    """The routing-era reading may only hold: a code's own passage that states the service, not the act the code
    accounts for, never stands for that act. The documented colonoscopy shows no biopsy, or leaves it in doubt, so a
    biopsy code citing only the extent statement is held with the documented service's question, never ready."""

    def test_a_service_statement_never_stands_for_the_act(self):
        for findings in ('The colon was normal.', 'It is unclear whether biopsies were taken.'):
            with self.subTest(findings=findings):
                text = SERVICE_STATEMENT.format(findings=findings)
                item = proposal(run(text, [sel('45380', span(text, CECUM_STATEMENT))]), '45380')
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                self.assertNotIn('read from its own passage by the routing-era reader',
                                 check(item, 'service.status').detail)

    def test_control_a_passage_naming_an_act_the_reader_does_not_read_still_stands(self):
        text = SERVICE_STATEMENT.format(findings='Cecal biopsies x2.')
        item = proposal(run(text, [sel('45380', span(text, 'Cecal biopsies x2.'))]), '45380')
        self.assertEqual(item.status, 'ready')
        self.assertIn('read from its own passage by the routing-era reader', check(item, 'service.status').detail)


class DoubtedActTests(SimpleTestCase):
    """An act the document names and leaves in doubt is held with that passage; it is never called an act the
    document does not show ("The documented colonoscopy shows no forceps biopsy")."""

    def test_the_doubted_act_is_quoted_in_the_reason_and_the_question(self):
        hedge = 'It is unclear whether biopsies were taken.'
        text = SERVICE_STATEMENT.format(findings=hedge)
        item = proposal(run(text, [sel('45380', span(text, CECUM_STATEMENT), span(text, hedge))]), '45380')
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
        self.assertIn(f'does not establish the forceps biopsy as done: “{hedge}”', check(item, 'service.status').detail)
        (asked,) = [c for c in item.clarifications if c.fact == 'performed_status']
        self.assertIn(f'“{hedge}”', asked.question)
        self.assertNotIn('shows no forceps biopsy', asked.question)

    def test_control_an_act_the_document_never_names_is_still_asked_as_missing(self):
        text = SERVICE_STATEMENT.format(findings='The colon was normal.')
        item = proposal(run(text, [sel('45380', span(text, CECUM_STATEMENT))]), '45380')
        (asked,) = [c for c in item.clarifications if c.fact == 'performed_status']
        self.assertIn('shows no forceps biopsy', asked.question)
