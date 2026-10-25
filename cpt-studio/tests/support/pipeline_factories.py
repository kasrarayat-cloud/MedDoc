"""Persisted assessments built from hand-written AssessmentResults. Synthetic data only.

These helpers write the rows the pipeline would have written (EncounterContext,
RoutingRun, ProviderRun) on top of tests/support/factories.py and persist the
result through review.persist_assessment, so tests exercise the real
persistence path without running extraction, routing or a provider.
"""
import hashlib
import itertools
from dataclasses import dataclass, replace
from datetime import timedelta

from django.utils import timezone

from studio import models, review
from studio.gi.profiles import PROFILES, PROFILES_VERSION, family_for_code
from studio.types import (AssessmentResult, Check, ClarificationSpec, EvidenceSpan, ExtractionResult, Fact,
                          FamilyFinding, PageSpan, ProposalAssessment, RoutingResult, ServiceMention, Span,
                          sha256_json, to_jsonable)
from tests.support import factories as f

_counter = itertools.count(1)

GI_NOTE = (
    'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
    'Procedure report\n'
    'Date of service: 2026-10-21\n'
    'Place of service: hospital outpatient endoscopy unit\n'
    'Procedures: EGD with biopsy; colonoscopy with snare polypectomy.\n'
    'EGD: The endoscope was advanced to the second portion of the duodenum. '
    'Cold forceps biopsies were taken from the gastric antrum.\n'
    'Colonoscopy: The colonoscope was advanced to the cecum; the appendiceal orifice was identified. '
    'A 7 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n'
    'Plan: Repeat colonoscopy in 3 years.\n'
)
EGD_PASSAGE = 'Cold forceps biopsies were taken from the gastric antrum.'
SNARE_PASSAGE = 'A 7 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
CECUM_PASSAGE = 'The colonoscope was advanced to the cecum'
PLAN_PASSAGE = 'Repeat colonoscopy in 3 years.'
DATE_PASSAGE = 'Date of service: 2026-10-21'
PROVIDER_DISPLAY = 'PROVIDER-DISPLAY-SENTINEL untrusted wording'
ENGINE_VERSION = 'test-engine@1'
ROUTING_VERSION = 'gi-routing@test'
CONTEXT_VERSION = 'gi-context@test'


def evidence(text, passage, *, occurrence=1, page=1):
    """An exact EvidenceSpan for the ``occurrence``-th appearance of ``passage`` in ``text``."""
    start = -1
    for _ in range(occurrence):
        start = text.index(passage, start + 1)
    return EvidenceSpan(context_index=0, start=start, end=start + len(passage), text=passage, exact=True, page=page)


def check(check_id, status, label='', detail='', source=''):
    return Check(id=check_id, label=label or check_id, status=status, detail=detail or f'{check_id} is {status}.',
                 source=source)


def standard_checks(**statuses):
    """The per-code checks the validation layer records; override a status with e.g. pfs_presence='fail'."""
    rows = (('evidence.exact', 'pass', 'Exact source evidence', 'cpt-studio:evidence@1'),
            ('routing.family', 'pass', 'Service family routing', 'cpt-studio:routing@1'),
            ('service.status', 'pass', 'Service performed on this encounter', 'cpt-studio:status@1'),
            ('cpt.membership', 'not_verified', 'CPT code-set membership for the service date', ''),
            ('cpt.descriptor', 'info', 'CPT descriptor', ''),
            ('pfs.presence', 'pass', 'Present in the CMS fee schedule file', 'cms-pfs-rvu26d RVU26D'),
            ('ncci.ptp', 'not_verified', 'NCCI procedure-to-procedure edits', ''))
    return tuple(check(check_id, statuses.get(check_id.replace('.', '_'), status), label, source=source)
                 for check_id, status, label, source in rows)


def fingerprint(code, family, profile_version, spans, checks, context_values=()):
    return sha256_json({'code': code, 'family': family, 'profile_version': profile_version,
                        'evidence': [span.text for span in spans], 'checks': [(c.id, c.status) for c in checks],
                        'context': list(context_values)})


def proposal(key, code, passages=(), *, text=GI_NOTE, bucket='selected', status=None, family=None, checks=None,
             exclusion_reason='', reinstatable=False, units=1, rationale='', modifiers=(), clarifications=(),
             context_values=(), fingerprint_value=None, code_kind='cpt1', spans=None):
    family = family or family_for_code(code)
    profile_version = PROFILES[family].version
    status = status or {'selected': 'ready', 'excluded': 'excluded', 'alternative': 'informational'}[bucket]
    spans = tuple(spans) if spans is not None else tuple(evidence(text, passage) for passage in passages)
    if checks is None:
        # As the engine records it: an excluded, reinstatable code carries its approval-after-reinstatement gate.
        reinstatement = (check('review.reinstatement', 'pass', 'Approval after reinstatement',
                               source='cpt-studio:reinstatement@1'),) if bucket == 'excluded' else ()
        checks = standard_checks() + reinstatement
    else:
        checks = tuple(checks)
    return ProposalAssessment(
        key=key, bucket=bucket, code=code, code_kind=code_kind, family=family, profile_version=profile_version,
        status=status, exclusion_reason=exclusion_reason, reinstatable=reinstatable, provider_display=PROVIDER_DISPLAY,
        evidence=spans, rationale=rationale or f'Synthetic rationale for {code}.', checks=checks,
        modifier_considerations=tuple(modifiers), units=units,
        fingerprint=fingerprint_value or fingerprint(code, family, profile_version, spans, checks, context_values),
        clarifications=tuple(clarifications))


def clarification(fact, *, scope='proposal', family='', proposal_key='', question=None, reason=None):
    return ClarificationSpec(scope=scope, fact=fact, question=question or f'Please document the {fact}.',
                             reason=reason or f'The {fact} is required and was not documented.', family=family,
                             proposal_key=proposal_key)


def reference_source(**overrides):
    source = {'key': 'cms-pfs-rvu26d', 'kind': 'cms-pfs', 'publisher': 'CMS', 'title': 'PFS relative value file',
              'release': 'RVU26D', 'url': 'https://www.cms.gov/', 'sha256': '0' * 64,
              'effective_start': '2026-10-01', 'effective_end': '2026-12-31', 'applies': True, 'connected': True,
              'license_note': 'CMS public file; descriptors dropped at import.',
              'scope_note': 'Medicare indicators only.'}
    source.update(overrides)
    return source


def result(*proposals, encounter_checks=None, clarifications=(), unsupported=(), reference_sources=None,
           engine_version=ENGINE_VERSION, summary=None):
    buckets = [item.bucket for item in proposals]
    return AssessmentResult(
        profiles_version=PROFILES_VERSION, engine_version=engine_version, proposals=tuple(proposals),
        encounter_checks=tuple(encounter_checks if encounter_checks is not None else (
            check('extraction.status', 'pass', 'Text extraction'),
            check('service_date', 'pass', 'Service date documented'))),
        clarifications=tuple(clarifications), unsupported=tuple(unsupported),
        reference_sources=tuple(reference_sources if reference_sources is not None else (reference_source(),)),
        summary=summary if summary is not None else {
            'selected': buckets.count('selected'), 'alternatives': buckets.count('alternative'),
            'excluded': buckets.count('excluded')})


def standard_result(text=GI_NOTE, **kwargs):
    """Two selected codes, one excluded (planned, reinstatable) and one alternative."""
    return result(
        proposal('sel:0', '43239', [EGD_PASSAGE], text=text),
        proposal('sel:1', '45385', [SNARE_PASSAGE], text=text, modifiers=('Consider whether modifier 59 applies.',)),
        proposal('exc:0', '45378', [PLAN_PASSAGE], text=text, bucket='excluded', reinstatable=True,
                 exclusion_reason='The colonoscopy is planned, not performed on this date.'),
        proposal('alt:0', '45380', [CECUM_PASSAGE], text=text, bucket='alternative'),
        **kwargs)


def facts(text=GI_NOTE, **overrides):
    """Context facts as stored on EncounterContext (name -> Fact JSON)."""
    values = {
        'service_date': Fact(name='service_date', value='2026-10-21', origin='document',
                             evidence=(Span(text.index(DATE_PASSAGE), text.index(DATE_PASSAGE) + len(DATE_PASSAGE),
                                            DATE_PASSAGE),) if DATE_PASSAGE in text else ()),
        'setting': Fact(name='setting', value='hospital_outpatient', origin='document'),
        'billing_context': Fact(name='billing_context', value=None, origin='missing',
                                note='Professional or facility billing is not documented.'),
        'patient_status': Fact(name='patient_status', value=None, origin='missing'),
    }
    for name, value in overrides.items():
        values[name] = value if isinstance(value, Fact) else Fact(name=name, value=value, origin='user')
    return {name: to_jsonable(fact) for name, fact in values.items()}


def context(enc, rev, *, fact_values=None, user_values=None, make_current=True):
    data = fact_values if fact_values is not None else facts(rev.text)
    user_values = dict(user_values or {})
    ctx = models.EncounterContext.objects.create(
        encounter=enc, revision=rev, facts=data, user_values=user_values, version=CONTEXT_VERSION,
        sha256=sha256_json({'facts': data, 'user_values': user_values, 'revision': str(rev.pk)}))
    if make_current:
        enc.current_context = ctx
        enc.save(update_fields=['current_context', 'updated_at'])
    return ctx


def routing(rev):
    span = Span(0, min(len(rev.text), 16), rev.text[:16])
    mention = ServiceMention(family='gi.colonoscopy', status='performed', span=span, sentence=span,
                             section='procedure', cues=('synthetic routing fixture',))
    finding = FamilyFinding(family='gi.colonoscopy', status='performed', mentions=(mention,))
    data = to_jsonable(RoutingResult(version=ROUTING_VERSION, document_kind='procedure_report', findings=(finding,)))
    return models.RoutingRun.objects.create(revision=rev, version=ROUTING_VERSION, result=data,
                                            sha256=sha256_json(data))


def provider_run(enc, rev, *, state='succeeded', provider='replay', usage=None, response=b'{"codes": []}'):
    succeeded = state == models.ProviderRun.SUCCEEDED
    body = {'system': ['cpt'], 'context': [{'type': 'text', 'text': rev.text}]}
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider=provider, adapter_version=f'{provider}@test',
        request_sha256=sha256_json(body), request_body=body, contexts=[rev.text], state=state,
        sent=state not in (models.ProviderRun.NOT_SENT, models.ProviderRun.CANCELLED),
        http_status=200 if succeeded else None, response_bytes=response if succeeded else b'',
        response_sha256=hashlib.sha256(response).hexdigest() if succeeded else '',
        usage=usage if usage is not None else ({'creditsConsumed': 0.0281} if succeeded else {}),
        usage_basis='provider_reported_credits_not_usd' if succeeded else '',
        started_at=timezone.now(), finished_at=timezone.now())


def job(enc, rev, kind, state, **extra):
    return models.Job.objects.create(encounter=enc, revision=rev, kind=kind, state=state,
                                     idempotency_key=f'{kind}:{rev.pk}:{next(_counter)}',
                                     deadline_at=timezone.now() + timedelta(minutes=30), **extra)


def assess(enc, assessment_result, *, rev=None, ctx=None, run=None, routing_run=None, no_provider=False):
    """Persist ``assessment_result`` for the current revision/context, creating any rows not supplied."""
    enc.refresh_from_db()
    rev = rev or enc.current_revision
    ctx = ctx or enc.current_context or context(enc, rev)
    if run is None and not no_provider:
        run = provider_run(enc, rev)
    return review.persist_assessment(encounter=enc, revision=rev, context=ctx, routing_run=routing_run or routing(rev),
                                     provider_run=run, result=assessment_result)


def addendum(enc, usr, text):
    """A recorded ADDENDUM revision appended to the current one (extraction 'ok'), made current."""
    enc.refresh_from_db()
    parent = enc.current_revision
    full = parent.text + f'\n\nADDENDUM\n{text}\n'
    rev = models.SourceRevision.objects.create(
        encounter=enc, number=parent.number + 1, kind=models.SourceRevision.ADDENDUM, parent=parent,
        addendum_text=text, synthetic_attested_by=usr, synthetic_attested_at=timezone.now(), created_by=usr)
    f.record(rev, ExtractionResult(status='ok', method='addendum', text=full,
                                   pages=(PageSpan(page=1, start=0, end=len(full)),)))
    rev.refresh_from_db()
    enc.current_revision = rev
    enc.save(update_fields=['current_revision', 'updated_at'])
    return rev


@dataclass
class Scenario:
    workspace: models.Workspace
    reviewer: models.User
    agent: models.User
    viewer: models.User
    encounter: models.Encounter
    revision: models.SourceRevision
    context: models.EncounterContext

    def membership(self, user):
        return models.Membership.objects.get(user=user, workspace=self.workspace)

    def proposal(self, key, assessment=None):
        self.encounter.refresh_from_db()
        assessment = assessment or self.encounter.current_assessment
        return assessment.proposals.get(key=key)

    def decide(self, key, action, user=None, *, note='', acknowledgement=None, assessment=None):
        user = user or self.reviewer
        if acknowledgement is None:
            acknowledgement = review.ACKNOWLEDGEMENTS[user.actor_kind] if action == 'approve' else ''
        self.encounter.refresh_from_db()
        return review.record_decision(encounter=self.encounter, proposal=self.proposal(key, assessment), action=action,
                                      user=user, membership=self.membership(user), note=note,
                                      acknowledgement=acknowledgement)


def scenario(text=GI_NOTE, *, workspace_name='Gastroenterology'):
    """A workspace with a human reviewer, an agent reviewer and a viewer, and one extracted encounter."""
    ws = f.workspace(workspace_name)
    reviewer = f.member(ws, f.user(f'reviewer{next(_counter)}'))
    agent = f.member(ws, f.user(f'reviewbot{next(_counter)}', actor_kind=models.User.AGENT))
    viewer = f.member(ws, f.user(f'viewer{next(_counter)}'), role=models.Membership.VIEWER)
    enc = f.encounter(ws, reviewer, title='Synthetic EGD and colonoscopy')
    rev = f.pasted_revision(enc, reviewer, text)
    ctx = context(enc, rev)
    return Scenario(workspace=ws, reviewer=reviewer, agent=agent, viewer=viewer, encounter=enc, revision=rev,
                    context=ctx)


def with_fingerprint(item, value):
    return replace(item, fingerprint=value)
