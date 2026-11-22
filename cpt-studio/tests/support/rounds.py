"""Synthetic scenarios for the customer API, decisions, exports and the operator console (lane B of the Fable coding
build; line identity from the fix pass, FIX-SPEC section 1). Synthetic text only; no real document, no network: a round
is either coded through the real pipeline with a fake coder (tests.support.coding) answering messages built here - each
section under its line marker, each review naming its line - or written directly in the shape studio.jobs stores."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client, override_settings
from django.utils import timezone

from studio import audit, jobs, models, state
from studio.fable import client as fable_client
from tests.support import coding as f

# The review attestations (studio.decisions.ACKNOWLEDGEMENTS), repeated so this module imports nothing it tests.
ACKNOWLEDGEMENTS = {
    'human': ('I read the whole source document, not only the quoted passages, and it supports this code as a '
              'service performed at this encounter. The coding review can be wrong. This synthetic review is not '
              'clinical approval or billing advice.'),
    'agent': ('I am an automated agent. I read the whole source document, not only the quoted passages, and it '
              'supports this code as a service performed at this encounter. The coding review can be wrong. This '
              'agent-executed synthetic review is not clinical approval or billing advice.'),
}

Round = models.CodingRound
ROOT = Path(settings.BASE_DIR)


def scan_customer():
    """ops/scan_customer.py, the shipped reader of the contract and the denylist (loaded from its file: ops is no
    package)."""
    name = 'laneb_scan_customer'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / 'ops' / 'scan_customer.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def denylist():
    return json.loads((ROOT / 'ops' / 'verification' / 'customer-denylist.json').read_text(encoding='utf-8'))


def review(line, code='45385', verdict='agree', **kwargs):
    """A checker review naming the reader line it reviews (FIX-SPEC 1)."""
    return {'line': line, **f.review(code, verdict, **kwargs)}


def missed(code, status='ready', *, units=1, modifiers=(), reason='The note documents it.', question=None,
           evidence=None):
    return {'code': code, 'units': units, 'modifiers': list(modifiers), 'status': status, 'reason': reason,
            'evidence': evidence if evidence is not None else [], 'question': question}


def reader_message(result, *, sections=None, used=None, stop='end_turn'):
    """A reader answer with one section per code under its marker (LINE L<n> <code>, in the list's order), each
    citing the document, then the final JSON. ``sections`` replaces the analysis blocks."""
    blocks = [f.text_block('I read the whole note.\n')]
    if sections is None:
        for number, item in enumerate(result.get('codes', []), start=1):
            blocks.append(f.text_block(f"\nLINE L{number} {item['code']}\n"))
            blocks.append(f.text_block('The polyp was removed by snare.', [f.page_cite('removed by cold snare', 1)]))
    else:
        blocks += list(sections)
    blocks.append(f.text_block(f.fenced(result)))
    return f.message(blocks, used=used, stop=stop)


def checker_message(result, *, sections=None, used=None, stop='end_turn'):
    """A checker answer with one section per review (REVIEW <its line> <code>) and per missed code (MISSED M<k>
    <code>), each citing the document, then the final JSON."""
    blocks = [f.text_block('I read the whole note first.\n')]
    if sections is None:
        for item in result.get('reviews', []):
            line = item.get('line') if isinstance(item.get('line'), str) else 'L0'
            blocks.append(f.text_block(f"\nREVIEW {line} {item['code']}\n"))
            blocks.append(f.text_block('The snare removal is documented.', [f.page_cite('cold snare', 2)]))
        for number, item in enumerate(result.get('missed_codes', []), start=1):
            blocks.append(f.text_block(f"\nMISSED M{number} {item['code']}\n"))
            blocks.append(f.text_block('The snare removal is documented.', [f.page_cite('cold snare', 2)]))
    else:
        blocks += list(sections)
    blocks.append(f.text_block(f.fenced(result)))
    return f.message(blocks, used=used, stop=stop)


# A reader and checker pair for a done round: a ready code, a code needing an answer, a code the checker disputes and
# a code the checker added; quotes cited on pages 1 and 2. Lines: L1 45385, L2 45380, L3 43239, L4 43251, M1 45378.
READER = f.reader_result(
    [f.code('45385', 'ready', reason='A 6 mm sigmoid polyp was removed by cold snare.'),
     f.code('45380', 'needs_answer', question='Was a biopsy taken from a separate site?',
            reason='A biopsy may have been taken.'),
     f.code('43239', 'ready', reason='An upper endoscopy with biopsy is documented.'),
     f.code('43251', 'not_supported', reason='No snare was used in the upper tract.')],
    questions=[{'question': 'Was a biopsy taken from a separate site?', 'affects': ['45380']}],
    problems=['The note is not signed.'])
CHECKER = f.checker_result(
    [review('L1', '45385', 'agree', reason='The snare removal is documented.'),
     review('L2', '45380', 'agree', status='needs_answer'),
     review('L3', '43239', 'disagree', reason='The biopsy site is not stated.'),
     review('L4', '43251', 'agree', status='not_supported')],
    missed=[missed('45378', reason='A diagnostic colonoscopy is documented.',
                   evidence=[{'quote': 'colonoscopy to the cecum', 'page': 1}])],
    questions=[{'question': 'Which site was biopsied during the upper endoscopy?', 'affects': ['43239']}])


class CustomerCase:
    """Mixin for a TestCase: an originals directory of its own, a workspace with a reviewer, a viewer and an agent, and
    a member of another workspace."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._originals = tempfile.TemporaryDirectory()
        cls._override = override_settings(ORIGINALS_DIR=Path(cls._originals.name))
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._originals.cleanup()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.ws = f.workspace('Gastroenterology')
        self.reviewer = f.member(self.ws)
        self.viewer = f.member(self.ws, role=models.Membership.VIEWER)
        self.agent = f.member(self.ws)
        models.User.objects.filter(pk=self.agent.pk).update(actor_kind=models.User.AGENT, display_name='Reviewbot')
        self.agent.refresh_from_db()
        self.other_ws = f.workspace('Another practice')
        self.outsider = f.member(self.other_ws)

    def client_for(self, user, **kwargs):
        client = Client(**kwargs)
        client.force_login(user)
        return client

    def use(self, fake):
        patcher = mock.patch.object(fable_client, 'coder', return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def run_next(self):
        job = jobs.claim_next()
        assert job is not None, 'no job was queued'
        jobs.run_job(job)
        return job

    def code_round(self, encounter, reader=READER, checker=CHECKER, *, reader_msg=None, checker_msg=None):
        """Run the encounter's queued round through the real stage with a fake coder answering ``reader`` and
        ``checker`` (or the messages given); the round, read again."""
        self.use(f.FakeCoder(reader=f.succeeded(reader_msg or reader_message(reader)),
                             checker=f.succeeded(checker_msg or checker_message(checker))))
        self.run_next()
        return state.latest_round(encounter)

    def decide(self, encounter, line, code, action, *, user=None, round_number=None, kind='human', note='',
               decision=None):
        """POST a decision as the page sends it (FIX-SPEC 1): the round shown, the line, its code; an undo names the
        decision it undoes (FIX-SPEC-2 section 5) - by default the one the page shows the member now."""
        client = self.client_for(user or self.reviewer)
        if round_number is None:
            round_number = state.latest_round(encounter).number
        body = {'round': round_number, 'line': line, 'code': code, 'action': action, 'note': note,
                'acknowledgement': ACKNOWLEDGEMENTS[kind] if action == 'approve' else ''}
        if action == 'revoke':
            if decision is None:
                rows = client.get(f'/api/encounters/{encounter.pk}').json().get('codes') or []
                shown = next((row['decision'] for row in rows if row.get('line') == line and row.get('decision')), None)
                decision = (shown or {}).get('id')
            body['decision'] = decision
        return client.post(f'/api/encounters/{encounter.pk}/decisions', data=json.dumps(body),
                           content_type='application/json')

    def report_text(self, encounter, kind, user=None):
        """Make the PDF report through the API, naming the round the page shows (FIX-SPEC-2 section 5), download it and
        return its text as pypdf reads it: every page, joined, white space squeezed to single spaces. The PDF is the only
        report made since 2026-11-21 (the TXT and CSV exports it replaced were plain text)."""
        from pypdf import PdfReader  # a dev requirement, as for every test that reads a PDF
        client = self.client_for(user or self.reviewer)
        shown = client.get(f'/api/encounters/{encounter.pk}').json().get('round') or {}
        made = client.post(f'/api/encounters/{encounter.pk}/reports', data=json.dumps(
            {'kind': kind, 'fmt': 'pdf', 'round': shown.get('number')}), content_type='application/json')
        assert made.status_code == 201, made.content
        data = client.get(made.json()['download_url']).content
        return ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages).split())

    def encounter(self, *, user=None, title='Synthetic colonoscopy note', service_date='2026-11-02',
                  insurance='medicare', pdf=True):
        """An encounter with revision 1 (an uploaded PDF, or pasted text) and NO round yet."""
        user = user or self.reviewer
        enc = f.encounter(self.ws, user, service_date=service_date, insurance=insurance, title=title)
        revision = f.upload(enc, user) if pdf else f.paste(enc, user)
        audit.record(self.ws, 'encounter.created', encounter=enc, actor=user, kind=revision.kind)  # as intake does
        return enc

    def started(self, **kwargs):
        """An encounter whose round 1 is queued (trigger upload)."""
        enc = self.encounter(**kwargs)
        jobs.start_round(enc, enc.current_revision, Round.UPLOAD, enc.created_by)
        return enc

    def done(self, **kwargs):
        """An encounter whose round 1 was coded (READER and CHECKER) through the pipeline."""
        enc = self.started(**kwargs)
        self.code_round(enc)
        enc.refresh_from_db()
        return enc


def write_round(encounter, *, state_=Round.DONE, codes=(), questions=(), problems=(), citations=None, trigger=None,
                failure_kind='', error=''):
    """A round written directly in the shape studio.jobs stores, the encounter's state refreshed. A code row without
    a line is given the next one of its kind (L1.. for the reader's rows, M1.. for the checker's), in order."""
    last = Round.objects.filter(encounter=encounter).order_by('-number').first()
    number = last.number + 1 if last else 1
    now = timezone.now()
    numbered, counts = [], {'L': 0, 'M': 0}
    for item in codes:
        letter = 'M' if item.get('listed_by') == 'checker' else 'L'
        counts[letter] += 1
        numbered.append(item if 'line' in item else {'line': f'{letter}{counts[letter]}', **item})
    round_ = Round.objects.create(
        encounter=encounter, revision=encounter.current_revision, number=number,
        trigger=trigger or (Round.UPLOAD if number == 1 else Round.ANSWERS),
        context=jobs.context_snapshot(encounter), state=state_, codes=numbered, questions=list(questions),
        problems=list(problems), citations=citations or {}, failure_kind=failure_kind, error=error,
        started_at=now, finished_at=now if state_ in (Round.DONE, Round.FAILED, Round.CANCELLED) else None)
    state.refresh(encounter)
    return round_


def row(code, status, *, reason='Documented.', units=1, modifiers=(), question=None, agrees=True,
        check_reason='Agreed.', evidence=None, listed_by='reader', line=None):
    """One combined code row as studio.fable.result.combine stores it (``line`` given by write_round when absent)."""
    check = None if listed_by == 'checker' else {
        'agrees': agrees, 'verdict': None if agrees is None else ('agree' if agrees else 'disagree'),
        'reason': check_reason if agrees is not None else None, 'question': None, 'correct_code': code,
        'correct_units': units, 'correct_modifiers': list(modifiers) if modifiers is not None else None,
        'correct_status': status, 'evidence': [],
        'reviews': 0 if agrees is None else 1, 'unmatched': 0, 'unplaced': 0}
    out = {'code': code, 'units': units, 'modifiers': list(modifiers) if modifiers is not None else None,
           'listed_status': status, 'reason': reason, 'question': question,
           'evidence': evidence if evidence is not None else [{'quote': 'evidence quote', 'page': 1}],
           'status': status, 'listed_by': listed_by, 'second_check': check}
    return {'line': line, **out} if line is not None else out
