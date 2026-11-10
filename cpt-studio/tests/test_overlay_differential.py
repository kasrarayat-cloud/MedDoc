"""The differential harness of the new path's overlay (Gemini migration slice S11; design/FINAL.md 8.1, Engine A's
mitigation made mandatory): for each scenario of the existing review_view suites, a fixture builder gives two projections
of the same stored proposals - the legacy-readable services record the legacy engine made, and an event_coding record
with the same sessions, acts, lesions and doubts (``project``) - and the two overlays' Views must be equal, field by
field, under every decision and member answer the scenario's own suites exercise.

The scenarios are the suites' own: tests.test_cux_r2_overlay's inputs (tests.test_cux_review's shapes - denied, the
misread box, selected, siblings, the pair, the EGD, the two E/M levels - and the hedged snare, the office visits beside a
denied colonoscopy, the anoscopy), R8 D15's EGD inside an upper EUS (tests.test_cux_hold) and P-ADMIT2's competition
(tests.test_h3_repairs). They cover the refutation cases review_view's comments name: L7-01 (a member's answer never lifts
a hold), L3-8 (a reinstated code asks what its gate waits for), L4-5 (a rival a member answered away), B-05 (the
same-day visit a reinstated procedure holds), D14 (a reinstated therapeutic code holds the base), R8 D15 (the base
within an EUS) and P-ADMIT2 (the competing hold released by a rejection).

What the projection carries is what the events engine stores (FINAL 7.8, 7.11): a session per documented service with
its label, kind, inclusion and its reportable and doubted acts (as engine.base_included reads them); each decidable code's
session, acts and lesions; each lesion's words and the lesions it is DISTINCT from (in the projection, every other lesion
of its service: the legacy reader's lesions are distinct by id); and on each proposal the summary and the reinstatement
waits the engine records structured. Two differences are by design and are kept out of the compared scenarios, each
asserted absent rather than silently skipped: an act a procedure line lists and the report contradicts (the legacy rule's
' (listed, not stated done)' wording; the events engine has no such reading), and an examination-only EUS code (the
events engine reads it as its family's base, FINAL 7.3; the legacy reader never did).

Synthetic data only, DB-free.
"""
import dataclasses
from dataclasses import replace

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.gi import services as gi_services
from studio.interpretation import combination, mapping, overlay
from studio.types import from_jsonable, to_jsonable
from studio.validation import reconcile, review_view
from tests.test_cux_r2_overlay import INPUTS, shape_of
from tests.test_cux_review import DAY

FIELDS = [field.name for field in dataclasses.fields(review_view.View)]
UNAVAILABLE = ('not_documented', 'cannot_confirm')


# --- the projection ---------------------------------------------------------------------------------------------------

def _entry(service, act) -> dict:
    return {'event': act.id, 'kind': act.kind, 'label': reconcile.act_label(act.kind),
            'lesion': f'{service.id}:{act.lesion}' if act.lesion else None,
            'describe': reconcile.describe_act(service, act)}


def _reportable(service, act) -> bool:
    entry = catalogue.entry(service.family)
    return (act.status == 'performed' and act.role in ('physician', 'unknown') and entry is not None
            and act.kind in entry.acts and not reconcile._bundled(service, act))


def _doubted(service, act) -> bool:
    entry = catalogue.entry(service.family)
    return (gi_services.listed_in_doubt(act) and act.role in ('physician', 'unknown') and entry is not None
            and act.kind in entry.acts and not reconcile._bundled(service, act))


def project(stored, services) -> tuple:
    """(the stored rows as the events engine stores them, completeness carrying the event_coding of the same
    sessions, acts, lesions and doubts) of a legacy assessment's ``stored`` rows and services record."""
    inventory = from_jsonable(gi_services.ServiceInventory, services)
    sessions, lesions, acts_of = {}, {}, {}
    for service in inventory.services:
        for act in service.acts:
            assert not gi_services.listed_contradicted(act), 'a by-design difference (module docstring)'
            acts_of[act.id] = (service, act)
        sessions[service.id] = {
            'family': service.family, 'event': '', 'part_of': service.included_in or '',
            'label': reconcile.service_label(service), 'kind': service.kind, 'unresolved': False,
            'done': service.status in ('performed', 'incomplete'), 'incomplete': service.status == 'incomplete',
            'examinations': [],
            'reportable': [_entry(service, act) for act in service.acts if _reportable(service, act)],
            'doubted': [_entry(service, act) for act in service.acts if _doubted(service, act)]}
        for lesion in service.lesions:
            lesions[f'{service.id}:{lesion.id}'] = {
                'words': None, 'landmark': 'not_stated', 'multiplicity': 'single',
                'distinct_from': [f'{service.id}:{other.id}' for other in service.lesions if other.id != lesion.id],
                'label': reconcile.lesion_words(service, lesion.id)}
    codes, rows = {}, []
    for p in stored:
        support = dict(p.support or {})
        ids = [str(act.get('id')) for act in support.get('acts') or () if isinstance(act, dict)]
        found = [acts_of[eid] for eid in ids if eid in acts_of]
        if review_view.decidable(p):
            codes[p.key] = {'session': support.get('service') or '', 'events': [act.id for _, act in found],
                            'lesions': sorted({f'{service.id}:{act.lesion}' for service, act in found if act.lesion})}
        support['acts'] = [{'id': act.id, 'kind': act.kind, 'label': reconcile.act_label(act.kind),
                            'status': act.status} for _, act in found]
        support['summary'] = review_view.summary(p, inventory)
        waits = [{'fact': wait['fact'], 'question': wait['question']} for wait in review_view._reinstatement_waits(p)
                 if wait['fact'] != review_view.DOCUMENTATION_FACT]
        check = next((c for c in p.checks if c.get('id') == review_view.REINSTATEMENT_CHECK), None)
        if check is not None and review_view.DATE_WAIT in str(check.get('detail') or ''):
            waits.insert(0, {'fact': overlay.DATE_WAIT_FACT, 'question': review_view.DATE_WAIT})
        if waits:
            support['reinstatement_waits'] = waits
        rows.append(replace(p, support=to_jsonable(support)))
    coding = {'version': overlay.CODING_VERSION, 'sessions': sessions, 'codes': codes, 'lesions': lesions}
    return rows, {'event_coding': coding}


# --- the comparison ---------------------------------------------------------------------------------------------------

class Scenario:
    def __init__(self, name, stored, services, retrieval=(), reference_sources=(), service_date=None):
        self.name, self.stored, self.services = name, list(stored), services
        self.kwargs = {'retrieval': retrieval, 'reference_sources': reference_sources, 'service_date': service_date}
        for p in self.stored:
            profile = catalogue.code_profile(p.code)
            exam_only = (profile is not None and not profile.base and bool(profile.covers)
                         and all(kind in mapping.EXAMINATION_KINDS for kind in profile.covers))
            assert not exam_only, f'{name}: {p.code} is a by-design difference (module docstring)'
        self.projected, self.completeness = project(self.stored, services)

    def legacy(self, decisions, answers=()):
        return review_view.review_view(self.stored, decisions, services=self.services, answers=answers, **self.kwargs)

    def new(self, decisions, answers=()):
        return overlay.review_view(self.projected, decisions, completeness=self.completeness, answers=answers,
                                   **self.kwargs)

    def differences(self, decisions, answers=()):
        legacy, new = self.legacy(decisions, answers), self.new(decisions, answers)
        if set(legacy) != set(new):
            return [('keys', sorted(legacy), sorted(new))]
        out = []
        for key in legacy:
            for name in FIELDS:
                if getattr(legacy[key], name) != getattr(new[key], name):
                    out.append((key, legacy[key].code, name, getattr(legacy[key], name), getattr(new[key], name)))
        return out

    def states(self):
        """(decisions, answers) the scenario's suites exercise: no decision; each single decision a reviewer can record
        (reject a selected code, reinstate an excluded one, approve a ready one or a reinstated one) and the pairs that
        hold or release (reinstate one and approve another, reject one and approve another); each under no answer and
        under each open question of the plain view answered either way (a code's, and a documented service's)."""
        decidable = [p for p in self.stored if review_view.decidable(p)]
        singles = [{p.key: ('reject' if p.bucket == 'selected' else 'reinstate')} for p in decidable]
        singles += [{p.key: 'approve'} for p in decidable if p.bucket == 'selected']
        pairs = [{**one, other.key: 'approve'} for one in singles for other in decidable
                 if other.key not in one and other.bucket == 'selected']
        pairs += [{p.key: review_view.Decided('approve', ('XS',))} for p in decidable if p.bucket == 'selected']
        for decisions in [{}] + singles + pairs:
            yield decisions, ()
            plain = self.legacy(decisions)
            for p in decidable:
                for question in plain[p.key].questions:
                    for value in UNAVAILABLE:
                        code = p.code if question.get('scope') == 'proposal' else ''
                        yield decisions, ({'code': code, 'family': question['family'], 'fact': question['fact'],
                                           'value': value},)


def scenarios():
    for name in INPUTS:
        shape = shape_of(name)
        yield Scenario(name, shape.stored, to_jsonable(shape.result.services), shape.retrieval,
                       to_jsonable(shape.result.reference_sources), DAY)
    from tests.test_cux_hold import EUS, EUS_FNA, EUS_REACH, run, sel, span
    for label, codes in (('D15 the EGD base beside its EUS', [('43242', EUS_FNA), ('43235', EUS_REACH)]),
                         ('D15 the EGD base alone', [('43235', EUS_REACH)])):
        result = run(EUS, [sel(code, span(EUS, phrase)) for code, phrase in codes])
        yield Scenario(label, [review_view.stored_from(p) for p in result.proposals], to_jsonable(result.services),
                       (), to_jsonable(result.reference_sources))
    from tests.test_h3_repairs import CompetitionReviewTests
    competition = CompetitionReviewTests('test_both_are_held_until_one_is_rejected_then_the_other_is_ready')
    competition.setUp()
    yield Scenario('P-ADMIT2 competing codes', competition.rows, to_jsonable(competition.result.services), (),
                   to_jsonable(competition.result.reference_sources))


# What each compared state exercised, so a harness that agrees only on states where nothing moves fails here (each
# refutation case review_view's comments name must be reached at least once)
EXERCISED = {
    'D14: a base held again beside a reinstated or a counted code': lambda v: 'base_included' in v.added,
    'a base released by a rejection': lambda v: 'base_included' in v.released,
    'approve withheld by the base rule': lambda v: v.withheld_by == 'services.base_included',
    'R8 D15: a base within an EUS': lambda v: any('endoscopic portion' in str(c.get('detail'))
                                                  for c in v.checks if c.get('id') == 'services.base_included'),
    'P-ADMIT2: a competing hold released': lambda v: 'competing_codes' in v.released,
    'L7-01: a code a member answered away': lambda v: v.reason == 'detail_unavailable',
    'L3-8: a reinstated code asks what its gate waits for': lambda v: v.bucket == 'excluded' and bool(v.added)
    and v.added[-1] not in ('base_included', 'separate_em'),
    'B-05: a visit a reinstated same-day procedure holds': lambda v: v.same_day_held,
    'a separate-lesion modifier review': lambda v: v.modifier_review is not None,
    'its claims-manual citation': lambda v: bool((v.modifier_review or {}).get('sources')),
    'the blocker of a decision no longer supported': lambda v: bool(v.blocker),
    'an endoscopic-family check recomputed': lambda v: 'pfs.endoscopic_base' in v.recomputed,
}


class DifferentialTests(SimpleTestCase):
    def test_the_two_overlays_agree_field_by_field_on_every_scenario_state(self):
        compared, failures, by_scenario, exercised = 0, [], {}, {name: 0 for name in EXERCISED}
        for scenario in scenarios():
            for decisions, answers in scenario.states():
                differences = scenario.differences(decisions, answers)
                compared += 1
                by_scenario[scenario.name] = by_scenario.get(scenario.name, 0) + 1
                if differences:
                    failures.append((scenario.name, decisions, answers, differences[:3]))
                views = scenario.new(decisions, answers).values()
                for name, seen in EXERCISED.items():
                    exercised[name] += any(seen(view) for view in views)
        self.assertEqual(failures[:5], [], f'{len(failures)} of {compared} states differ')
        self.assertGreaterEqual(compared, 300)
        self.assertEqual(len(by_scenario), len(INPUTS) + 3)
        self.assertEqual([name for name, n in exercised.items() if not n], [], exercised)

    def test_the_harness_is_live_a_projection_that_drops_what_the_overlay_reads_differs(self):
        # negative controls: each removes from the event coding one thing a seam reads, and the comparison must see it
        shape = next(scenario for scenario in scenarios() if scenario.name == 'siblings')
        decisions = {}
        self.assertEqual(shape.differences(decisions), [])
        coding = shape.completeness['event_coding']
        for label, change in (
                ('the base rule reads the reportable acts', lambda c: [s.update(reportable=[])
                                                                       for s in c['sessions'].values()]),
                ('the modifier review reads distinctness', lambda c: [l.update(distinct_from=[])
                                                                      for l in c['lesions'].values()]),
                ('the session of each code', lambda c: [e.update(session='') for e in c['codes'].values()])):
            with self.subTest(label):
                import copy
                saved = copy.deepcopy(coding)
                change(coding)
                try:
                    self.assertNotEqual(shape.differences(decisions), [])
                finally:
                    coding.clear()
                    coding.update(saved)
        self.assertEqual(shape.differences(decisions), [])
