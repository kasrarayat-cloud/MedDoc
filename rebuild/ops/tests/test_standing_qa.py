"""The standing-authority runner (ops/standing_qa.py), offline: no network, no Django, no database, no credential.

What each group proves, stated so a reader can see how it would fail:
  · AUTHORITY AND DECLARATION — the committed authority record says what the runner implements; the committed TEST
    declaration is exactly the template filled; it parses to what it states; the template itself, a wrong authority id,
    the historical campaign/authority/root/database, ANY money limit (a line, a decorated second line, a number for the
    ceiling, an old stage form, a budget name), owner words that are not verbatim, an authority record that is not the
    one named, an uncommitted or modified declaration, unsafe bounds and a revocation are each refused; a command that
    sends refuses a test declaration.
  · NO CEILING — wherever a limit would stand (declaration, limits, their records, attempts, runs, status) it is None.
  · ADMISSION — an eligible synthetic request under the new authority is admitted and its attempt carries the run and
    attempt identities; the Stop file, a campaign stop, an open attempt, a failed or passed stage, a missing
    prerequisite, no open run, the run's cap, the stage's send count and changed terms are each refused; no money limit
    is invented (a large maximum is admitted, bounded by the per-request limits instead).
  · DUPLICATES AND INPUTS — a send that already has an attempt, a send its run did not select, an input its run does not
    allow and a restricted development original are refused at the last door before a send.
  · RUNS AND RECONCILIATION — gapless runs, one open; an attempt left without an outcome is recorded interrupted_unknown,
    its stage failed and its run closed as interrupted, and the path stays stopped; a closed partial run keeps its stage
    open; remaining sends skip attempted and unexercisable ones; batches never split a mapping form from its encounter,
    and a remainder holding an encounter whose form was mapped in an earlier run is refused, never set aside.
  · STAGE RUNS — the real run_stage (only the Django-bound helpers and the per-send worker stood in): a full mapping run
    passes with both encounters sent; a Stop-file halt that strands an encounter, or a stop before an encounter's
    attempt, never becomes a pass — every later run is refused before a run opens, and the reopening is refused before
    it is written (refutation R1-F2/R2-F1, the historical pending_sends rule restored); a run that made no send is
    never a pass.
  · CONFIGURATION — the eligible configuration passes; a contract flag, a non-QA database, the installed database, tree
    or state, a layout socket, another model or rate, an invalid profile, a profile past the per-request bounds and a
    wrong pricing version are each a problem.
  · CREDENTIAL AND DOOR — the declared credential file with the wrong mode is refused; a send outside the ruled-mutation
    door, or through a door opened for another declaration or commit, is refused; with no live declaration committed,
    `run` and `preflight` refuse before any credential is read.
  · PREFLIGHT — one GET to the models endpoint of the declared model, recorded before it leaves, the response retained,
    the returned id compared; another id, an error, another URL or method, a second request and the Stop file each fail
    or refuse; no key is retained; it is never generation proof, and `run` requires a matching one.
  · REQUEST BOUNDS — the capture refuses a request naming another model or asking for more output than the bound, before
    it is recorded or sent.
  · HISTORICAL — the historical runner's `run` and request process (`_inner`) refuse at ANY root and under any
    declaration before reading anything (refutation R1-F1: a fresh root used to pass with the historical declaration);
    reopen/recover refuse on the historical root; `status` and `plan` stay readable; its declaration is byte-identical;
    its declaration and ledger are refused here.
  · PLANS — the plan definitions: model_check 1, mapping 10 (f1-f6), the notes comparison 28 (14 cases x 2 requests),
    D30/D31-structure and transcription not established; the declared send counts equal the plans; flags agree with the
    historical runner's.
  · PRICING — the pricing command reproduces the historical declaration's versions for claude-sonnet-5 (positive
    control) and refuses claude-sonnet-5-5 while the application has no profile for it; with a Deepgram rate it adds
    the transcription version (equal to the notes version at the historical rate, different at any other).
  · TRANSCRIPTION (T4b) — the declaration's transcription section (every term once and fixed, allowlisted recordings
    with their pinned sha256, two sends per recording, no section without its stage nor stage without its section);
    the Deepgram key file under the Anthropic key's rules (missing, linked file or directory, hard link, wrong mode or
    owner, two lines, empty, a directory: each refused) and read by outer() for a transcription run only, before the
    database or the exec; its key in the request environment of a transcription run only, never in argv or the
    context, and refused by inner() anywhere else; the transport guard (exactly the declared request, captured before
    it leaves without its credential, the response retained; any other URL, parameter, key, header, body or a second
    request refused before the network); the last door (only this send's allowlisted recording, allowed by its run,
    never restricted; never twice); the real run_stage for transcription (each recording then its generation, the
    key only for a transcription run, a halt between the two strands the generation and refuses every later run, a
    retained copy of the Deepgram key stops the campaign); the transcript judge (source support, protected fields).
    (L1:R1-F2) A Deepgram key sharing a run of 16 characters with the Anthropic key in any letter case (a copy, holding
    it, a part or a long piece of it) or Anthropic-shaped — a file of its own PATH holding the Anthropic key's VALUE —
    is refused where it is read (the loader, outer, inner, the preconditions), by run_stage before a run opens, and at
    the guard before the network; the guard also refuses the Anthropic key in any header or body.
  · STOP RACE (L1:R1-F4 / L2:R2-F2) — the Stop file met inside a send before its attempt record (preview admission,
    admission, attempt record; and in the model check) halts the run and cancels its queued job; any other refusal,
    even with a Stop file present, and a campaign stop still fail; the halt is read from the refusal's type.
No socket is opened (network_guard); the providers are in-process stand-ins.
"""
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from ops import sonnet5_qa as sq
from ops import standing_qa as st
from . import network_guard

REPOSITORY = Path(__file__).resolve().parents[3]
REBUILD = REPOSITORY / 'rebuild'
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'standing-declaration-test.md'
RECORD = REPOSITORY / st.AUTHORITY_RECORD
HISTORICAL_DECLARATION = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
HISTORICAL_DECLARATION_SHA256 = '76bfb6af8dea0d7184be00e7ca9d30f3c1bbc99f62057b1002f3d3643efb5d15'
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-STANDING-OFFLINE-KEY-222222222222222222222222222222222-CCCCCCCC'
#: A synthetic Deepgram key: 40 printable characters, the declared credential's shape (no real key is ever used here).
DEEPGRAM_KEY = 'dg0SYNTHETIC0standing0offline0key0444444'
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic Test',
       '-c', 'user.email=synthetic@test.invalid']
DECLARATION_NAME = '20261001-quillmd-v1-standing-api-testing.md'
RUNNER_COMMIT = '1' * 40


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


def scratch(test):
    directory = Path(tempfile.mkdtemp(prefix='standing-test-'))
    test.addCleanup(shutil.rmtree, directory, True)
    return directory


def git(root, *args, check=True):
    return subprocess.run([*GIT, '-C', str(root), *args], capture_output=True, check=check)


def fixture_text():
    return FIXTURE.read_text(encoding='utf-8')


def repository(test, text, *, record=None, name=DECLARATION_NAME, commit=True):
    """A scratch checkout holding `text` as a committed declaration and the authority record (the real one by default)."""
    root = scratch(test)
    git(root, 'init', '-q')
    folder = root / 'docs' / 'foundation' / 'mutations'
    folder.mkdir(parents=True)
    (root / st.AUTHORITY_RECORD).parent.mkdir(parents=True)
    (root / st.AUTHORITY_RECORD).write_bytes(RECORD.read_bytes() if record is None else record)
    path = folder / name
    path.write_text(text, encoding='utf-8')
    git(root, 'add', '--', st.AUTHORITY_RECORD)
    if commit:
        git(root, 'add', '--', str(path.relative_to(root)))
    git(root, 'commit', '-q', '-m', 'Synthetic standing declaration')
    return root, path


def parse(test, text=None, *, uses=('live', 'test'), record=None):
    root, path = repository(test, fixture_text() if text is None else text, record=record)
    return st.declared_standing(path, repository=root, uses=uses, out=io.StringIO())


def edited(old, new, text=None, count=1):
    text = fixture_text() if text is None else text
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def fill_template(values, use, where):
    """The template's declaration part, its <FILL …> placeholders replaced in order, the use and the 'Where it runs'
    lines substituted — the one recipe by which the committed TEST declaration was made."""
    text = st.TEMPLATE.read_text(encoding='utf-8')
    body = text[text.index('# Declaration —'):]
    parts = re.split(r'<FILL[^>]*>', body)
    assert len(parts) - 1 == len(values)
    out = parts[0] + ''.join(value + part for value, part in zip(values, parts[1:]))
    out = edited('declaration_use: live', f'declaration_use: {use}', out)
    for old, new in where.items():
        out = edited(old, new, out)
    return out


FIXTURE_VALUES = (['3', '15', '0.30', 'disabled', 'medium'] + ['configured-v1:' + c * 64 for c in 'abcd']
                  + ['0.0077', 'configured-v1:' + 'e' * 64])
FIXTURE_WHERE = {
    'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001': 'root: /nonexistent/standing-qa-test-root',
    'qa_database: quillmd_qa_standing_20261001': 'qa_database: quillmd_qa_v2_auth_fixture',
    'credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key':
        'credential_file: /nonexistent/standing-qa-test-root/credential/anthropic-api-key',
    'transcription_credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/deepgram-api-key':
        'transcription_credential_file: /nonexistent/standing-qa-test-root/credential/deepgram-api-key',
    'qa_database_password_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password':
        'qa_database_password_file: /nonexistent/standing-qa-test-root/qa-db/password',
    'restricted_inputs_ledger: /opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/'
    '053-original-dev40-exact-rights-ledger.json': 'restricted_inputs_ledger: /nonexistent/standing-qa-test-root/'
                                                    'rights-ledger.json'}
FIXTURE_HEAD = ('# TEST DECLARATION — used only by rebuild/ops/tests/test_standing_qa.py (declaration_use: test; never '
                'sends)\n\n')


def rights_ledger(test, restricted=(), authorized=()):
    """A synthetic rights ledger in the custody shape: each restricted hash `paid_or_model_stage1_authorized: false`."""
    path = scratch(test) / 'rights-ledger.json'
    records = ([{'id': f'R{i}', 'sha256': h, 'paid_or_model_stage1_authorized': False} for i, h in enumerate(restricted)]
               + [{'id': f'A{i}', 'sha256': h, 'paid_or_model_stage1_authorized': True} for i, h in enumerate(authorized)])
    data = json.dumps({'records': records}).encode()
    path.write_bytes(data)
    return str(path), hashlib.sha256(data).hexdigest()


RESTRICTED_SAMPLE = ('f' * 64, 'e' * 64)


class Base(unittest.TestCase):
    def campaign(self, declaration=None, restricted=RESTRICTED_SAMPLE):
        declaration = parse(self) if declaration is None else declaration
        ledger, digest = rights_ledger(self, restricted)
        declaration = dataclasses.replace(declaration, restricted_inputs_ledger=ledger,
                                          restricted_inputs_ledger_sha256=digest)
        root = scratch(self) / 'campaign'
        campaign = st.StandingCampaign(declaration, root)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def open_model_check_run(self, campaign, cap=1):
        return st.begin_run(campaign, 'model_check', st.standing_plan('model_check'), None, cap,
                            {'runner_commit': RUNNER_COMMIT})

    def model_check_attempt(self, campaign, number=None, form=sq.FORM_SHA256, maximum='0.050000', **changes):
        d = campaign.declaration
        number = len(campaign.ledger.rows()) + 1 if number is None else number
        record = {'number': number, 'campaign': d.campaign, 'authority_id': d.authority_id, 'stage': 'model_check',
                  'maximum_cost': maximum, 'exposure_bound': format(Decimal(maximum) * pc.GEO_MARGIN, 'f'),
                  'rates': d.rates.as_dict(), 'form_sha256': form, 'notes_sha256': sq.NOTES_SHA256,
                  'declaration_sha256': d.sha256, 'declaration_commit': d.commit, 'limits': campaign.limits().record(),
                  'terms': campaign.pinned_terms().record(), 'runner_commit': RUNNER_COMMIT, 'started_at': pc.now()}
        record.update(changes)
        return record

    def completed(self, campaign, number):
        campaign.ledger.write_outcome(number, {'class': 'completed', 'usage': {
            'input_tokens': 1000, 'output_tokens': 200, 'inference_geo': 'global'}})

    def pass_model_check(self, campaign):
        run = self.open_model_check_run(campaign)
        campaign.admit('model_check', '0.05', runner_commit=RUNNER_COMMIT)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        campaign.ledger.write_stage('model_check', 'passed', {'attempt': attempt['number']})
        campaign.runs.close(campaign.ledger, run['run'], {'closed_as': 'decided', 'sends': [
            {'send': {'id': st.MODEL_CHECK_SEND}, 'attempt': attempt['number'], 'stops_stage': False}]})
        return attempt

    def open_notes_run(self, campaign, sends, cap=10):
        inputs = sq.stages_module().frozen_inputs()
        return st.begin_run(campaign, 'notes_comparison', sends, inputs, cap, {'runner_commit': RUNNER_COMMIT}), inputs

    def notes_attempt(self, campaign, send, inputs, changes=None):
        d = campaign.declaration
        record = {'number': len(campaign.ledger.rows()) + 1, 'campaign': d.campaign, 'authority_id': d.authority_id,
                  'stage': 'notes_comparison', 'send': send.record(), 'maximum_cost': '0.100000',
                  'rates': d.rates.as_dict(), 'form_sha256': st.send_inputs(send, inputs)['form_sha256'],
                  'limits': campaign.limits().record(), 'terms': campaign.pinned_terms().record(),
                  'runner_commit': RUNNER_COMMIT, 'started_at': pc.now()}
        record.update(changes or {})
        return record


# ── authority and declaration ────────────────────────────────────────────────────────────────────────────────────

class AuthorityAndDeclarationTests(Base):
    def test_the_committed_authority_record_states_what_the_runner_implements(self):
        record = json.loads(RECORD.read_text(encoding='utf-8'))
        self.assertEqual((record['authority_id'], record['mode']), (st.AUTHORITY_ID, st.MODE))
        self.assertIsNone(record['owner_imposed_monetary_ceiling'])
        self.assertIs(record['per_batch_monetary_confirmation_required'], False)
        self.assertEqual(record['historical']['preserved_authority'], st.HISTORICAL['authority_id'])
        template = st.TEMPLATE.read_text(encoding='utf-8')
        words = re.search(r'^owner_words: (.*)$', template, re.M).group(1)
        self.assertEqual(words, record['owner_words'])                              # verbatim, typos and double space
        self.assertIn('all the  stuuf', words)
        sha = re.search(r'^authority_record_sha256: ([0-9a-f]{64})$', template, re.M).group(1)
        self.assertEqual(sha, hashlib.sha256(RECORD.read_bytes()).hexdigest())

    def test_the_test_declaration_is_exactly_the_template_filled(self):
        self.assertEqual(fixture_text(), FIXTURE_HEAD + fill_template(FIXTURE_VALUES, 'test', FIXTURE_WHERE))

    def test_the_test_declaration_parses_to_exactly_what_it_states(self):
        out = io.StringIO()
        root, path = repository(self, fixture_text())
        d = st.declared_standing(path, repository=root, uses=('test',), out=out)
        self.assertEqual((d.campaign, d.authority_id, d.mode, d.use), (st.CAMPAIGN, st.AUTHORITY_ID, st.MODE, 'test'))
        self.assertIsNone(d.monetary_ceiling)
        self.assertIsNone(d.total_limit)
        self.assertIs(d.per_batch_monetary_confirmation, False)
        self.assertEqual((d.provider, d.model, d.thinking, d.effort, d.inference_geo),
                         ('anthropic', 'claude-sonnet-5-5', 'disabled', 'medium', ''))
        self.assertEqual(d.rates, pc.Rates('3', '15', '0.30'))
        self.assertEqual(dict(d.pricing_versions), {'model_check': 'configured-v1:' + 'a' * 64,
                                                    'mapping': 'configured-v1:' + 'b' * 64,
                                                    'ordinary_notes': 'configured-v1:' + 'c' * 64,
                                                    'ordinary_notes_field_relations': 'configured-v1:' + 'd' * 64,
                                                    'transcription': 'configured-v1:' + 'e' * 64})
        self.assertEqual((d.concurrency, d.automatic_retries, d.max_sends_per_run, d.max_output_tokens_per_request,
                          d.request_deadline_seconds), (1, 'none', 10, 20000, 180))
        self.assertEqual([(s.id, s.sends, s.requires, s.limit) for s in d.stages],
                         [('model_check', 1, None, None), ('mapping', 10, 'model_check', None),
                          ('notes_comparison', 28, 'model_check', None), ('transcription', 4, 'model_check', None)])
        self.assertEqual(d.transcription, st.TranscriptionTerms(
            'deepgram', 'nova-3-medical', '0.0077', 'true', 'false',
            '/nonexistent/standing-qa-test-root/credential/deepgram-api-key', ('soap-ankle-speech', 'colonoscopy-speech')))
        self.assertEqual(d.transcription.parameters(), {'model': 'nova-3-medical', 'smart_format': 'false',
                                                        'mip_opt_out': 'true'})
        self.assertEqual(d.owner_words, json.loads(RECORD.read_text())['owner_words'])
        self.assertIn(d.commit, out.getvalue())
        self.assertIn('monetary ceiling none', out.getvalue())

    def test_the_template_is_never_a_declaration(self):
        with self.assertRaisesRegex(pc.Refused, 'template placeholders'):
            parse(self, st.TEMPLATE.read_text(encoding='utf-8'))

    def test_the_template_filled_for_live_use_parses_and_names_the_live_places(self):
        d = parse(self, fill_template(FIXTURE_VALUES, 'live', {}), uses=('live',))
        st.require_live(d)
        self.assertEqual((d.root, d.qa_database), (str(st.LIVE_ROOT), st.DATABASE_NAME))
        self.assertEqual(d.credential_file, str(sq.HISTORICAL_ROOT / 'credential' / 'anthropic-api-key'))

    def test_a_wrong_authority_id_is_refused(self):
        with self.assertRaisesRegex(pc.Refused, 'names the authority'):
            parse(self, edited('authority_id: quillmd-v1-private-api-testing-standing-20260930',
                               'authority_id: quillmd-v1-private-api-testing-standing-20261231'))
        with self.assertRaisesRegex(pc.Refused, 'standing authorization'):
            parse(self, edited('standing authority quillmd-v1-private-api-testing-standing-20260930 with',
                               'standing authority quillmd-v1-something-else with'))
        with self.assertRaisesRegex(pc.Refused, 'standing authorization'):
            parse(self, edited('authorization: owner 2026-09-30', 'authorization: owner 2026-10-01'))

    def test_the_historical_campaign_authority_root_and_database_are_refused(self):
        cases = [
            ('campaign: quillmd-v1-standing-api-testing-20261001', 'campaign: quillmd-v1-sonnet5-staged-40', 'new campaign'),
            ('authority_id: quillmd-v1-private-api-testing-standing-20260930',
             'authority_id: quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk', 'names the authority'),
            ('root: /nonexistent/standing-qa-test-root', 'root: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign',
             'its own'),
            ('root: /nonexistent/standing-qa-test-root',
             'root: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/standing', 'its own'),
            ('root: /nonexistent/standing-qa-test-root', 'root: /opt/meddoc-pro/rebuild/.runtime', 'its own'),
            ('root: /nonexistent/standing-qa-test-root', 'root: /var/lib/quillmd/standing', 'its own'),
            ('qa_database: quillmd_qa_v2_auth_fixture', 'qa_database: quillmd_qa_sonnet5', 'synthetic database of its own'),
            ('qa_database: quillmd_qa_v2_auth_fixture', 'qa_database: quillmd_fresh', 'synthetic database of its own')]
        for old, new, why in cases:
            with self.subTest(new=new), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))

    def test_any_money_limit_is_refused(self):
        anchor = 'max_sends_per_run: 10\n'
        variants = [
            edited(anchor, anchor + 'total_limit_provider_usd: 40.00\n'),
            edited(anchor, anchor + '- monetary_ceiling: 1000000\n'),
            edited('monetary_ceiling: none', 'monetary_ceiling: 1000000'),
            edited('monetary_ceiling: none', 'monetary_ceiling: 0'),
            edited('stage: mapping sends 10 requires model_check_passed',
                   'stage: mapping limit_provider_usd 25.00 requires model_check_passed'),
            edited(anchor, anchor + 'budget_usd: 5\n'),
            edited(anchor, anchor + '> **spend_limit**: 100\n'),
            edited(anchor, anchor + 'unused_stage_budget_transfers: no\n'),
            edited(anchor, anchor + 'stage: extra max_requests 10\n'),
            edited(anchor, anchor + 'ceiling_usd: 40\n'),
            edited(anchor, anchor + '* monetary_cap: 5\n'),
            edited(anchor, anchor + '| max_spend | : 100 |\n'),
            edited('## Money', '## Money\n\nCost ceiling: $40 for this campaign.'),
            edited('mode: standing_unlimited_monetary', 'mode: staged_monetary_limits'),
            edited('per_batch_monetary_confirmation: not_required', 'per_batch_monetary_confirmation: required')]
        for text in variants:
            with self.subTest(text=text[text.index('## Money'):text.index('## Model')][:200]):
                with self.assertRaises(pc.Refused):
                    parse(self, text)

    def test_owner_words_must_be_the_records_verbatim(self):
        with self.assertRaisesRegex(pc.Refused, 'verbatim'):
            parse(self, edited('also add thsi propmt', 'also add this prompt'))
        with self.assertRaisesRegex(pc.Refused, 'verbatim'):
            parse(self, edited('all the  stuuf', 'all the stuuf'))
        record = RECORD.read_bytes().replace(b'"owner_words": "also add', b'"owner_words": "Also add')
        with self.assertRaisesRegex(pc.Refused, 'sha256 differs'):
            parse(self, record=record)
        record_text = RECORD.read_text().replace('"owner_imposed_monetary_ceiling": null',
                                                 '"owner_imposed_monetary_ceiling": "40.00"')
        sha = hashlib.sha256(record_text.encode()).hexdigest()
        text = edited('authority_record_sha256: 9178279297a173697f8becc89d0ab24f510b87231c3d692934e8d60fce41652c',
                      f'authority_record_sha256: {sha}')
        with self.assertRaisesRegex(pc.Refused, 'no owner ceiling'):
            parse(self, text, record=record_text.encode())

    def test_an_uncommitted_modified_or_misplaced_declaration_is_refused(self):
        root, path = repository(self, fixture_text(), commit=False)
        with self.assertRaisesRegex(pc.Refused, 'tracked, committed and unmodified'):
            st.declared_standing(path, repository=root, uses=('test',), out=io.StringIO())
        root, path = repository(self, fixture_text())
        path.write_text(edited('max_sends_per_run: 10', 'max_sends_per_run: 11'), encoding='utf-8')
        with self.assertRaisesRegex(pc.Refused, 'tracked, committed and unmodified'):
            st.declared_standing(path, repository=root, uses=('test',), out=io.StringIO())
        elsewhere = root / 'docs' / DECLARATION_NAME
        elsewhere.write_text(fixture_text(), encoding='utf-8')
        with self.assertRaisesRegex(pc.Refused, 'mutations'):
            st.declared_standing(elsewhere, repository=root, uses=('test',), out=io.StringIO())

    def test_unsafe_bounds_are_refused(self):
        cases = [('concurrency: 1', 'concurrency: 2', 'one at a time'),
                 ('automatic_retries: none', 'automatic_retries: 2', 'never re-sent'),
                 ('max_output_tokens_per_request: 20000', 'max_output_tokens_per_request: 64000', 'at most 21333'),
                 ('request_deadline_seconds: 180', 'request_deadline_seconds: 900', 'at most 600'),
                 ('stage: notes_comparison sends 28', 'stage: dictation sends 28', 'No standing plan'),
                 ('stage: mapping sends 10 requires model_check_passed', 'stage: mapping sends 10 requires none\n'
                  'stage: mapping sends 10 requires none', 'twice')]
        for old, new, why in cases:
            with self.subTest(new=new), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))

    def test_a_revocation_is_refused(self):
        with self.assertRaisesRegex(pc.Refused, 'revocation'):
            parse(self, edited('## Retained evidence', 'This authority is revoked.\n\n## Retained evidence'))

    def test_a_live_campaign_id_fixes_its_root_database_and_declaration_file(self):
        self.assertEqual(st.live_places(st.CAMPAIGN), {'root': st.LIVE_ROOT, 'database': st.DATABASE_NAME,
                                                       'declaration_name': st.DECLARATION.name})
        later = st.live_places('quillmd-v1-standing-api-testing-20261001-2')
        self.assertEqual((later['root'].name, later['database'], later['declaration_name']),
                         ('v1-standing-api-testing-20261001-2', 'quillmd_qa_standing_20261001_2',
                          '20261001-quillmd-v1-standing-api-testing-2.md'))
        for campaign in ('quillmd-v1-standing-api-testing', 'quillmd-v1-standing-api-testing-20261001-1',
                         'quillmd-v1-standing-api-testing-2026101', 'other-20261001', st.HISTORICAL['campaign']):
            with self.subTest(campaign=campaign), self.assertRaisesRegex(pc.Refused, 'live standing campaign'):
                st.live_places(campaign)
        values = FIXTURE_VALUES
        second = {'campaign: quillmd-v1-standing-api-testing-20261001': 'campaign: quillmd-v1-standing-api-testing-20261001-2',
                  'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001':
                      'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001-2',
                  'qa_database: quillmd_qa_standing_20261001': 'qa_database: quillmd_qa_standing_20261001_2'}
        root, path = repository(self, fill_template(values, 'live', second),
                                name='20261001-quillmd-v1-standing-api-testing-2.md')
        d = st.declared_standing(path, repository=root, out=io.StringIO())
        self.assertEqual(st.require_live(d)['root'], later['root'])
        root, path = repository(self, fill_template(values, 'live', second))       # (in the FIRST campaign's file)
        with self.assertRaisesRegex(pc.Refused, 'is 20261001-quillmd-v1-standing-api-testing-2.md'):
            st.require_live(st.declared_standing(path, repository=root, out=io.StringIO()))
        moved = {**second, 'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001':
                 'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-elsewhere'}
        root, path = repository(self, fill_template(values, 'live', moved),
                                name='20261001-quillmd-v1-standing-api-testing-2.md')
        with self.assertRaisesRegex(pc.Refused, 'runs at'):
            st.require_live(st.declared_standing(path, repository=root, out=io.StringIO()))
        self.assertEqual(st.declaration_path(None), st.DECLARATION)
        self.assertEqual(st.declaration_path('docs/foundation/mutations/20261001-quillmd-v1-standing-api-testing-2.md'),
                         st.MUTATIONS / '20261001-quillmd-v1-standing-api-testing-2.md')
        for given in ('docs/foundation/mutations/20261001-quillmd-v1-standing-api-testing.TEMPLATE.md',
                      'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md',
                      '/tmp/20261001-quillmd-v1-standing-api-testing.md',
                      'docs/foundation/mutations/../mutations/x/20261001-quillmd-v1-standing-api-testing.md'):
            with self.subTest(given=given), self.assertRaisesRegex(pc.Refused, 'standing declaration is'):
                st.declaration_path(given)

    def test_every_command_that_sends_refuses_a_test_declaration(self):
        with self.assertRaisesRegex(pc.Refused, 'live use'):
            parse(self, uses=('live',))
        with self.assertRaisesRegex(pc.Refused, 'Only a live declaration sends'):
            st.require_live(parse(self))


# ── no ceiling, anywhere ─────────────────────────────────────────────────────────────────────────────────────────

class NoCeilingTests(Base):
    def test_no_ceiling_is_none_everywhere_and_never_a_number(self):
        campaign = self.campaign()
        d, limits = campaign.declaration, campaign.declaration.limits()
        self.assertIsNone(d.monetary_ceiling)
        self.assertIsNone(d.total_limit)
        self.assertTrue(all(stage.limit is None for stage in d.stages))
        self.assertIsNone(limits.total)
        self.assertTrue(all(stage.limit is None for stage in limits.stages))
        record = limits.record()
        self.assertIsNone(record['monetary_ceiling'])
        self.assertTrue(all(entry['limit_provider_usd'] is None for entry in record['stages'].values()))
        self.assertEqual(st.StandingLimits.from_record(json.loads(json.dumps(record)), 'x'), limits)
        run = self.open_model_check_run(campaign)
        self.assertIsNone(run['monetary_ceiling'])
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        written = json.loads((campaign.root / 'ledger' / '001-attempt.json').read_text())
        self.assertIsNone(written['monetary_ceiling'])
        self.assertIsNone(written['limits']['monetary_ceiling'])
        self.assertIsNone(campaign.limits().total)

        def money_values(value, path=''):
            """Every value under a key naming a ceiling or a money limit."""
            if isinstance(value, dict):
                for key, item in value.items():
                    if re.search(r'ceiling|limit_provider_usd|^limit$|total_limit', key):
                        yield path + '/' + key, item
                    yield from money_values(item, path + '/' + key)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    yield from money_values(item, f'{path}[{index}]')
        for where, value in [*money_values(record), *money_values(written), *money_values(run)]:
            self.assertIsNone(value, where)
        self.completed(campaign, 1)
        campaign.ledger.release()
        out = io.StringIO()
        root, path = repository(self, fixture_text())
        with redirect_stderr(io.StringIO()):
            report = st.status(campaign.root, path, repository=root, out=out)
        campaign.ledger.acquire()
        self.assertIsNone(report['monetary_ceiling'])
        self.assertIsNone(report['total']['limit'])
        self.assertTrue(all(stage['limit'] is None for stage in report['stages'].values()))
        for where, value in money_values(json.loads(out.getvalue())):
            self.assertIsNone(value, where)

    def test_a_recorded_money_figure_is_not_a_standing_record(self):
        record = parse(self).limits().record()
        for broken in ({**record, 'monetary_ceiling': '1000000'}, {**record, 'monetary_ceiling': 0},
                       {**record, 'stages': {**record['stages'], 'mapping': {**record['stages']['mapping'],
                                                                              'limit_provider_usd': '25.00'}}},
                       {**record, 'total_limit_provider_usd': '40.00'}, {**record, 'mode': 'staged'}):
            with self.subTest(broken=broken), self.assertRaises(pc.Refused):
                st.StandingLimits.from_record(broken, 'Attempt 1')


# ── admission ────────────────────────────────────────────────────────────────────────────────────────────────────

class AdmissionTests(Base):
    def test_an_eligible_synthetic_request_is_admitted_under_the_new_authority(self):
        campaign = self.campaign()
        run = self.open_model_check_run(campaign)
        bound = campaign.admit('model_check', '0.05', runner_commit=RUNNER_COMMIT)
        self.assertEqual(bound, Decimal('0.05') * pc.GEO_MARGIN)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        written = json.loads((campaign.root / 'ledger' / '001-attempt.json').read_text())
        self.assertEqual((written['campaign'], written['authority_id'], written['mode']),
                         (st.CAMPAIGN, st.AUTHORITY_ID, st.MODE))
        self.assertEqual((written['run'], written['run_id']), (run['run'], 'run-0001'))
        self.assertEqual(written['attempt_id'], f'{st.CAMPAIGN}/run-0001/attempt-001')
        self.assertEqual((written['send'], written['send_key']), ({'id': st.MODEL_CHECK_SEND},
                                                                  'model_check:' + st.MODEL_CHECK_SEND))
        self.assertEqual(set(written['engine_files']), set(st.WATCHED_FILES))
        self.assertIn('rebuild/core/mapping_wire.py', written['engine_files'])
        self.assertEqual(campaign.rows()[0][0]['number'], 1)

    def test_no_money_limit_is_invented(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        self.assertEqual(campaign.admit('model_check', '1000000'), Decimal('1000000') * pc.GEO_MARGIN)

    def test_the_stop_file_and_a_campaign_stop_admit_nothing(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        campaign.stop_file().write_text('')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            campaign.admit('model_check', '0.05')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign))
        campaign.stop_file().unlink()
        campaign.stop_file().mkdir()                               # (any kind of file: a directory stops it too)
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            campaign.admit('model_check', '0.05')
        campaign.stop_file().rmdir()
        campaign.ledger.write_stop({'reason': 'synthetic'})
        with self.assertRaisesRegex(pc.Refused, 'campaign is stopped'):
            campaign.admit('model_check', '0.05')
        self.assertEqual(campaign.ledger.rows(), [])

    def test_an_unreconciled_open_attempt_admits_nothing(self):
        campaign = self.pass_model_check_campaign()
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        self.open_notes_run(campaign, plan[:2])
        campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs))
        with self.assertRaisesRegex(pc.Refused, 'no outcome'):
            campaign.admit('notes_comparison', '0.10')
        with self.assertRaisesRegex(pc.Refused, 'no outcome'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[1], inputs))

    def pass_model_check_campaign(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        return campaign

    def test_a_stage_before_its_prerequisite_passed_is_refused(self):
        campaign = self.campaign()
        with self.assertRaisesRegex(pc.Refused, 'requires model_check'):
            campaign.stage_open('notes_comparison')

    def test_a_failed_or_passed_stage_admits_nothing(self):
        campaign = self.pass_model_check_campaign()
        with self.assertRaisesRegex(pc.Refused, 'already passed'):
            campaign.admit('model_check', '0.05')
        campaign.ledger.write_stage('mapping', 'failed', {'reasons': ['synthetic safety failure']})
        with self.assertRaisesRegex(pc.Refused, 'path is stopped'):
            campaign.stage_open('mapping')

    def test_no_open_run_the_runs_cap_and_the_stages_count_are_enforced(self):
        campaign = self.campaign()
        with self.assertRaisesRegex(pc.Refused, 'No run of stage model_check is open'):
            campaign.admit('model_check', '0.05')
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        run, _ = self.open_notes_run(campaign, plan[:3], cap=1)
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        with self.assertRaisesRegex(pc.Refused, 'has made all 1 sends'):
            campaign.admit('notes_comparison', '0.10')
        with self.assertRaisesRegex(pc.Refused, 'has made all 1 sends'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[1], inputs))
        # (the model check declares ONE send: a second, in any run, is refused)
        small = dataclasses.replace(campaign.declaration)
        self.assertEqual(campaign.limits().stage('model_check').max_requests, small.stage('model_check').sends)

    def test_the_stages_declared_send_count_is_enforced(self):
        d = parse(self, edited('stage: notes_comparison sends 28', 'stage: notes_comparison sends 1'))
        campaign = self.campaign(d)
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        self.open_notes_run(campaign, plan[:2])
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        with self.assertRaisesRegex(pc.Refused, 'all 1 sends it declares'):
            campaign.admit('notes_comparison', '0.10')

    def test_terms_other_than_the_pinned_ones_admit_nothing(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        edited_declaration = dataclasses.replace(campaign.declaration, rates=pc.Rates('1', '5', '0.10'))
        other = st.StandingCampaign(edited_declaration, campaign.root)
        with self.assertRaisesRegex(pc.Refused, 'differ from those the ledger'):
            other.stage_open('notes_comparison')


# ── duplicates and inputs ────────────────────────────────────────────────────────────────────────────────────────

class DuplicateAndInputTests(Base):
    def test_a_send_that_already_has_an_attempt_is_never_attempted_again(self):
        campaign = self.campaign()
        attempt = self.pass_model_check(campaign)
        self.assertEqual(attempt['send_key'], 'model_check:' + st.MODEL_CHECK_SEND)
        self.open_model_check_run(campaign)                         # (a second run naming the same send)
        with self.assertRaisesRegex(pc.Refused, 'never made twice'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign))
        self.assertEqual(st.remaining_sends(campaign, 'model_check', st.standing_plan('model_check')), [])

    def test_a_send_its_run_did_not_select_or_of_another_campaign_is_refused(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        self.open_notes_run(campaign, plan[:1])
        with self.assertRaisesRegex(pc.Refused, 'did not select'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[1], inputs))
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs,
                                                             {'campaign': st.HISTORICAL['campaign']}))
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs,
                                                             {'authority_id': st.HISTORICAL['authority_id']}))
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs, {'stage': 'mapping'}))

    def test_an_input_its_run_does_not_allow_is_refused(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        with self.assertRaisesRegex(pc.Refused, 'not one of the synthetic inputs'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign, form='0' * 64))

    def test_a_restricted_development_original_is_refused_before_any_send(self):
        restricted = sq.FORM_SHA256                                 # (pretend the fixed form were a restricted original)
        campaign = self.campaign(restricted=(restricted,))
        with self.assertRaisesRegex(pc.Refused, 'no provider upload'):
            self.open_model_check_run(campaign)
        self.assertIsNone(campaign.runs.current())
        # (and at the last door, should a run ever allow it)
        campaign = self.campaign(restricted=('9' * 64,))
        run = self.open_model_check_run(campaign)
        tampered = {**run, 'restricted_inputs': [sq.FORM_SHA256]}
        with patch.object(campaign.runs, 'current', return_value=tampered):
            with self.assertRaisesRegex(pc.Refused, 'no provider upload'):
                campaign.ledger.write_attempt(self.model_check_attempt(campaign))

    def test_the_rights_ledger_must_be_the_declared_one_and_readable(self):
        campaign = self.campaign()
        d = campaign.declaration
        self.assertEqual(st.restricted_hashes(d), frozenset(RESTRICTED_SAMPLE))
        with self.assertRaisesRegex(pc.Refused, 'sha256 differs'):
            st.restricted_hashes(dataclasses.replace(d, restricted_inputs_ledger_sha256='0' * 64))
        path, digest = rights_ledger(self, (), ('a' * 64,))           # (only an authorised original: no restriction)
        with self.assertRaisesRegex(pc.Refused, 'names no restricted original'):
            st.restricted_hashes(dataclasses.replace(d, restricted_inputs_ledger=path,
                                                     restricted_inputs_ledger_sha256=digest))
        broken = scratch(self) / 'broken.json'
        broken.write_bytes(b'{"records": [{"sha256": 7}]}')
        with self.assertRaisesRegex(pc.Refused, 'cannot be read whole'):
            st.restricted_hashes(dataclasses.replace(d, restricted_inputs_ledger=str(broken),
                                                     restricted_inputs_ledger_sha256=hashlib.sha256(
                                                         broken.read_bytes()).hexdigest()))

    @unittest.skipUnless(os.access('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/'
                                   '053-original-dev40-exact-rights-ledger.json', os.R_OK),
                         'the custody rights ledger is on the VPS only')
    def test_no_planned_input_is_a_restricted_original_in_the_real_rights_ledger(self):
        d = parse(self, fill_template(FIXTURE_VALUES, 'live', {}), uses=('live',))
        restricted = st.restricted_hashes(d)
        self.assertEqual(len(restricted), 40)
        inputs = sq.stages_module().frozen_inputs()
        for stage in ('model_check', 'mapping', 'notes_comparison'):
            for send in st.standing_plan(stage, inputs):
                self.assertNotIn(st.send_inputs(send, inputs)['form_sha256'], restricted, send.id)


# ── runs and reconciliation ──────────────────────────────────────────────────────────────────────────────────────

class RunsAndReconciliationTests(Base):
    def test_runs_are_gapless_with_at_most_one_open(self):
        campaign = self.campaign()
        run = self.open_model_check_run(campaign)
        self.assertEqual((run['run'], run['run_id'], run['sends']), (1, 'run-0001', [st.MODEL_CHECK_SEND]))
        with self.assertRaisesRegex(pc.Refused, 'already open'):
            self.open_model_check_run(campaign)
        campaign.runs.close(campaign.ledger, 1, {'closed_as': 'refused_before_attempt', 'sends': []})
        with self.assertRaises(FileExistsError):
            pc.write_new(campaign.root / 'runs' / '0001-closed.json', {'run': 1})
        self.assertEqual(self.open_model_check_run(campaign)['run'], 2)
        (campaign.root / 'runs' / 'stray.json').write_text('{}')
        with self.assertRaisesRegex(pc.Refused, 'not a run record'):
            campaign.runs.listing()

    def test_an_interrupted_attempt_is_reconciled_its_stage_failed_and_its_run_closed(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)                       # (the process died here, mid-send)
        result = st.settle(campaign)
        self.assertEqual(result['recovered'], [1])
        self.assertEqual(result['failed_stages'], ['model_check'])
        self.assertEqual(result['run_closed_as_interrupted'], 1)
        outcome = json.loads((campaign.root / 'ledger' / '001-outcome.json').read_text())
        self.assertEqual(outcome['class'], 'interrupted_unknown')
        self.assertEqual(json.loads((campaign.root / 'runs' / '0001-closed.json').read_text())['closed_as'],
                         'interrupted')
        with self.assertRaisesRegex(pc.Refused, 'path is stopped'):
            campaign.stage_open('model_check')
        self.assertEqual(st.earlier_stops(campaign, 'model_check')[0]['attempt'], 1)

    def test_a_closed_partial_run_keeps_its_stage_open_and_its_attempts_decided(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        run, _ = self.open_notes_run(campaign, plan[:1])
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        self.assertEqual(campaign.ledger.undecided(), {'notes_comparison': [attempt['number']]})
        campaign.runs.close(campaign.ledger, run['run'], {'closed_as': 'partial', 'sends': [
            {'send': plan[0].record(), 'attempt': attempt['number'], 'stops_stage': False}]})
        self.assertEqual(campaign.ledger.undecided(), {})
        self.assertEqual(st.settle(campaign)['failed_stages'], [])
        self.assertEqual(campaign.ledger.stage_state('notes_comparison')['state'], 'open')
        left = st.remaining_sends(campaign, 'notes_comparison', plan)
        self.assertEqual([s.id for s in left], [s.id for s in plan[1:]])
        self.assertEqual(st.earlier_stops(campaign, 'notes_comparison'), [])

    def test_a_stopped_send_means_the_stage_can_never_pass(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        run, _ = self.open_notes_run(campaign, plan[:1])
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        campaign.runs.close(campaign.ledger, run['run'], {'closed_as': 'failed', 'sends': [
            {'send': plan[0].record(), 'attempt': attempt['number'], 'stops_stage': True, 'recorded_as': 'unsafe'}]})
        self.assertEqual(st.earlier_stops(campaign, 'notes_comparison')[0]['why'], 'it stopped the stage (unsafe)')

    def test_batches_keep_a_mapping_form_with_its_encounter_and_refuse_a_stranded_one(self):
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('mapping', inputs)
        chosen = st.select_batch(plan, 8)
        self.assertEqual([s.id for s in chosen], ['mapping:f1-guidance-confirmation', 'mapping:f2-leave-checkboxes',
                                                  'mapping:f2b-leave-checkboxes-owner', 'mapping:f3-selection-instructions',
                                                  'mapping:f4-exam-grid', 'mapping:f5-negative-controls',
                                                  'mapping:f6a-long-answer', 'generation:f6a-long-answer'])
        self.assertEqual(st.stranded(plan), [])
        rest = [s for s in plan if s not in chosen]
        self.assertEqual([s.id for s in st.select_batch(rest, 8)],
                         ['mapping:f6b-admin-missing', 'generation:f6b-admin-missing'])
        self.assertEqual([s.id for s in st.select_batch(plan, 10)], [s.id for s in plan])
        without_form = [s for s in plan if s.id != 'mapping:f6a-long-answer']
        self.assertEqual([s.id for s in st.stranded(without_form)], ['generation:f6a-long-answer'])
        for refused in (lambda: st.select_batch(without_form, 10), lambda: st.require_none_stranded('mapping', without_form)):
            with self.assertRaisesRegex(pc.Refused, "generation:f6a-long-answer needs its form's mapping send in the same "
                                                    'run, and that send was already made; it is not sent'):
                refused()
        notes = st.standing_plan('notes_comparison', inputs)
        self.assertEqual(len(st.select_batch(notes, 10)), 10)


# ── stage runs (the real run_stage, offline) ─────────────────────────────────────────────────────────────────────

class FakeWorker:
    """Stands in for sonnet5_stages.Run (and standing_qa_transcription.TranscriptionRun) in the request process, in
    Run.run_send's order: the preview admit on the planned maximum (hook `start` just before it), the pre-attempt work
    (upload, queue, price: hook `pre_attempt`), admit — whose refusal is turned into a StageStop raised while handling
    it, exactly as sonnet5_stages.Run.refuse_job does after cancelling the queued job — then (hook `before_write`)
    write_attempt, the ONE request in flight (hook `in_flight`), the outcome, a clean per-send record. Like the real
    worker it keeps what a send made for the send that needs it (Run.templates, TranscriptionRun.transcribed) only
    inside its own process: a send whose prerequisite was not made by this worker is not made (returns None)."""
    hooks = {}
    refused_jobs = []

    def __init__(self, campaign, stage, *, secret, provenance, inputs, forms, world, checked, deadline,
                 transcription_secret=None):
        self.campaign, self.stage, self.secret, self.provenance, self.inputs = campaign, stage, secret, provenance, inputs
        self.ledger = campaign.ledger
        self.sends, self.veto_evidence, self.stopped, self.planned, self.made = [], [], None, {}, set()
        if transcription_secret is not None:
            self.transcription_secret = transcription_secret

    def run_send(self, send):
        commit = self.provenance.get('runner_commit')
        FakeWorker.hooks.get('start', lambda send: None)(send)
        if self.planned.get(send.id) is not None:
            self.campaign.admit(self.stage, self.planned[send.id], runner_commit=commit)
        if st.needs(send) is not None and st.needs(send) not in self.made:
            return None
        FakeWorker.hooks.get('pre_attempt', lambda send: None)(send)
        maximum = Decimal('0.10')
        try:
            bound = self.campaign.admit(self.stage, maximum, runner_commit=commit)
        except pc.Refused as refused:
            FakeWorker.refused_jobs.append(send.id)          # (the job queued for this send, cancelled unsent)
            raise sq.stages_module().StageStop(str(refused) + '; the job was cancelled unsent')
        FakeWorker.hooks.get('before_write', lambda send: None)(send)
        d, number = self.campaign.declaration, len(self.ledger.rows()) + 1
        inputs = {k: v for k, v in st.send_inputs(send, self.inputs).items() if k in ('form_sha256', 'audio_sha256')}
        self.ledger.write_attempt({
            'number': number, 'campaign': d.campaign, 'authority_id': d.authority_id, 'stage': self.stage,
            'send': send.record(), 'maximum_cost': format(maximum, 'f'), 'exposure_bound': format(bound, 'f'),
            'rates': d.rates.as_dict(), **inputs,
            'limits': self.campaign.limits().record(), 'terms': self.campaign.pinned_terms().record(),
            'runner_commit': commit, 'started_at': pc.now()})
        FakeWorker.hooks.get('in_flight', lambda send: None)(send)
        self.ledger.write_outcome(number, {'class': 'completed', 'usage': {
            'input_tokens': 1000, 'output_tokens': 200, 'inference_geo': 'global'}})
        self.made.add(send.id)
        record = {'send': send.record(), 'attempt': number, 'class': 'completed', 'findings': [],
                  'verdict': {'unsafe': []}, 'stops_stage': False, 'recorded_as': None}
        self.sends.append(record)
        return record, False


STRANDED = "needs its form's mapping send in the same run, and that send was already made; it is not sent"


class StageRunTests(Base):
    """The REAL run_stage — selection, runs, admission, the ledger, reopening and the decision — with only the Django-bound
    helpers and the per-send worker stood in (FakeWorker). Refutation R1-F2/R2-F1: an encounter whose form's mapping send
    was made in an EARLIER run (a Stop-file halt between the two, or a stop before the encounter's attempt and a
    reopening) was recorded `not_exercised` and the stage PASSED without the encounter ever being sent. The historical
    rule (sonnet5_stages.pending_sends, f5fe720f) is restored: such an encounter is never sent and its remainder is
    refused, so the stage can never pass in that campaign."""

    def setUp(self):
        stages = sq.stages_module()
        FakeWorker.hooks, FakeWorker.refused_jobs, self.cancellations = {}, [], []

        def cancel_stale_jobs(world):
            self.cancellations.append(world)
            return []
        for stand_in in (patch.object(stages, 'stage_preconditions', lambda *a, **k: {'stand_in': True}),
                         patch.object(stages, 'build_forms', lambda *a, **k: {}),
                         patch.object(stages, 'seed_account', lambda root: object()),
                         patch.object(sq, 'cancel_stale_jobs', cancel_stale_jobs),
                         patch.object(stages, 'Run', FakeWorker),
                         patch.object(st, 'price_sends', lambda stage, sends, *a, **k: {
                             s.id: {'maximum_cost': Decimal('0.10')} for s in sends})):
            stand_in.start()
            self.addCleanup(stand_in.stop)

    def prepared(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        folder = campaign.root / 'preflight' / '001'
        folder.mkdir(parents=True)
        (folder / 'result.json').write_text(json.dumps({'matches_declared': True, 'campaign': campaign.declaration.campaign,
                                                         'model_returned': campaign.declaration.model}))
        return campaign

    def run_mapping(self, campaign, runner_commit=RUNNER_COMMIT, **kwargs):
        return st.run_stage(campaign, 'mapping', secret=SYNTHETIC_KEY, provenance={'runner_commit': runner_commit},
                            **kwargs)

    def attempted(self, campaign):
        return [a['send']['id'] for a, _ in campaign.ledger.rows() if a['stage'] == 'mapping']

    def halt_at(self, campaign, send_id):
        def in_flight(send):
            if send.id == send_id:
                campaign.stop_file().write_text('')          # (the operator halts while this send is in flight)
        FakeWorker.hooks = {'in_flight': in_flight}
        result = self.run_mapping(campaign)
        FakeWorker.hooks = {}
        campaign.stop_file().unlink()                         # (and lifts the halt)
        return result

    def assert_never_passes(self, campaign, stranded, runs):
        for _ in range(2):                                     # (the refusal holds on every later run)
            with self.assertRaises(pc.Refused) as caught:
                self.run_mapping(campaign)
            for send_id in stranded:
                self.assertIn(f'{send_id} {STRANDED}', str(caught.exception))
            self.assertIn('Stage mapping cannot pass in this campaign', str(caught.exception))
            self.assertEqual(len(campaign.runs.listing()), runs)              # (no run was opened)
        self.assertNotEqual(campaign.ledger.stage_state('mapping')['state'], 'passed')

    def test_a_full_run_makes_every_send_and_passes(self):
        campaign = self.prepared()
        result = self.run_mapping(campaign)
        self.assertEqual((result['decision'], result['verdict']), ('passed', 'PASS'), result['reasons'])
        self.assertEqual(sorted(self.attempted(campaign)),
                         sorted(s.id for s in st.standing_plan('mapping', sq.stages_module().frozen_inputs())))

    def test_a_halt_between_both_forms_and_their_encounters_refuses_every_later_run(self):
        campaign = self.prepared()
        first = self.halt_at(campaign, 'mapping:f6b-admin-missing')
        self.assertEqual((first['decision'], first['summary']['not_sent']),
                         ('halted', ['generation:f6a-long-answer', 'generation:f6b-admin-missing']))
        made = self.attempted(campaign)
        self.assert_never_passes(campaign, ['generation:f6a-long-answer', 'generation:f6b-admin-missing'], runs=2)
        self.assertEqual(self.attempted(campaign), made)
        self.assertFalse([s for s in made if s.startswith('generation:')])
        self.assertEqual(campaign.ledger.stage_state('mapping')['state'], 'open')
        report = st.plan_report('mapping', root=campaign.root, declaration_path=Path(campaign.declaration.path),
                                repository=campaign.declaration.repository)
        self.assertEqual(report['stages']['mapping']['stranded'],
                         ['generation:f6a-long-answer', 'generation:f6b-admin-missing'])

    def test_a_halt_after_one_form_refuses_the_whole_remainder(self):
        campaign = self.prepared()
        first = self.halt_at(campaign, 'mapping:f6a-long-answer')
        self.assertEqual(first['decision'], 'halted')
        self.assert_never_passes(campaign, ['generation:f6a-long-answer'], runs=2)
        self.assertNotIn('mapping:f6b-admin-missing', self.attempted(campaign))   # (the historical rule: nothing sent)

    def test_an_encounter_stopped_before_its_attempt_is_never_reopened_into_a_pass(self):
        campaign = self.prepared()
        repo = Path(campaign.declaration.repository)
        failed_runner = git(repo, 'rev-parse', 'HEAD').stdout.decode().strip()

        def pre_attempt(send):
            if send.id == 'generation:f6a-long-answer':
                raise pc.Refused('The area decisions were refused (500).')
        FakeWorker.hooks = {'pre_attempt': pre_attempt}
        first = self.run_mapping(campaign, runner_commit=failed_runner)
        FakeWorker.hooks = {}
        self.assertEqual(first['decision'], 'failed')
        failed = [a['number'] for a, _ in campaign.ledger.rows() if a['stage'] == 'mapping']
        # (an offline repair touching a watched file, a committed diagnosis naming the failure, a runner carrying both)
        (repo / 'rebuild' / 'ops').mkdir(parents=True)
        (repo / 'rebuild' / 'ops' / 'standing_qa.py').write_text('# synthetic repair\n')
        git(repo, 'add', '--', 'rebuild/ops/standing_qa.py')
        git(repo, 'commit', '-q', '-m', 'Synthetic repair')
        repair = git(repo, 'rev-parse', 'HEAD').stdout.decode().strip()
        diagnosis = repo / 'docs' / 'diagnosis-mapping.txt'
        diagnosis.write_text(f'reopen_stage: mapping\nfailed_attempts: {", ".join(map(str, failed))}\n'
                             f'repair_commit: {repair}\n')
        git(repo, 'add', '--', 'docs/diagnosis-mapping.txt')
        git(repo, 'commit', '-q', '-m', 'Synthetic diagnosis')
        campaign.ledger.release()
        real = st.declared_standing

        def test_use(path, **kwargs):                       # (the reopening reads the declaration; this one is `test`)
            return real(path, **{**kwargs, 'uses': ('live', 'test')})
        with self.assertRaises(pc.Refused) as caught, patch.object(st, 'declared_standing', test_use), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            st.reopen('mapping', str(diagnosis), root=campaign.root, declaration_path=Path(campaign.declaration.path),
                      repository=str(repo), rebuild=repo)
        self.assertIn(f'generation:f6a-long-answer {STRANDED}', str(caught.exception))
        campaign.ledger.acquire()
        self.assertEqual(campaign.ledger.stage_state('mapping')['state'], 'failed')      # (no reopening was written)
        self.assertEqual(campaign.ledger.stage_state('mapping')['reopenings'], 0)
        self.assertNotIn('generation:f6a-long-answer', self.attempted(campaign))

    def test_a_run_that_made_no_send_is_never_a_pass(self):
        campaign = self.prepared()
        inputs = sq.stages_module().frozen_inputs()
        send = next(s for s in st.standing_plan('mapping', inputs) if s.id == 'generation:f6a-long-answer')
        run = st.begin_run(campaign, 'mapping', [send], inputs, 1, {'runner_commit': RUNNER_COMMIT})
        worker = FakeWorker(campaign, 'mapping', secret=SYNTHETIC_KEY, provenance={}, inputs=inputs, forms={},
                            world=None, checked={}, deadline=1)
        worker.sends.append({'send': send.record(), 'not_exercised': 'set aside'})
        result = st.decide_run(campaign, 'mapping', run, [send], worker, [], [], {})
        self.assertEqual((result['decision'], result['reasons']), ('failed', ['no send was made']))


# ── configuration ────────────────────────────────────────────────────────────────────────────────────────────────

def snapshot(declaration, root, stage='model_check', **changes):
    """An eligible configuration for `stage`, in settings_snapshot's shape."""
    values = {'database': {'NAME': declaration.qa_database, 'HOST': '127.0.0.1', 'PORT': '55731'},
              'state_dir': str(Path(root) / 'qa-state'), 'media_root': str(Path(root) / 'qa-state' / 'files'),
              'synthetic_only': True, 'data_mode': 'synthetic', 'ai_mode': 'live', 'provider': 'anthropic',
              'model': declaration.model, 'rates': declaration.rates.as_dict(), 'thinking': declaration.thinking,
              'effort': declaration.effort, 'inference_geo': declaration.inference_geo,
              'settings': st.expected_settings(stage),
              'voice_rates': {'minute': declaration.transcription.rate_per_minute if stage == 'transcription'
                              else sq.PRICE_SETTINGS['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'], 'second': ''},
              'request_profile': {'profile': 'synthetic-5-5-v1', 'max_output_tokens': 8000, 'timeout_seconds': 120},
              'pricing_version': declaration.pricing_version(st.STAGE_PRICING[stage][0])}
    for key, value in changes.items():
        if key == 'settings':
            values['settings'] = {**values['settings'], **value}
        else:
            values[key] = value
    return values


class ConfigurationTests(Base):
    def setUp(self):
        self.d = parse(self)
        self.root = scratch(self) / 'campaign'
        self.worktree = scratch(self) / 'worktree' / 'rebuild'

    def problems(self, stage='model_check', rebuild=None, **changes):
        return st.check_configuration(snapshot(self.d, self.root, stage, **changes), self.d, stage, self.root,
                                      rebuild=self.worktree if rebuild is None else rebuild)

    def test_the_eligible_configuration_passes_for_every_stage(self):
        for stage in ('model_check', 'mapping', 'notes_comparison', 'transcription'):
            self.assertEqual(self.problems(stage), [], stage)

    def test_a_transcription_process_without_the_declared_request_is_a_problem(self):
        cases = [{'voice_rates': {'minute': '0.0043', 'second': ''}},          # (the historical rate, not the declared)
                 {'voice_rates': {'minute': '0.0077', 'second': '0.0002'}},
                 {'voice_rates': {'minute': '', 'second': ''}},
                 {'settings': {'QUILLMD_DEEPGRAM_MIP_OPT_OUT': None}},              # (synthetic default: not sent at all)
                 {'settings': {'QUILLMD_DEEPGRAM_MIP_OPT_OUT': 'false'}},
                 {'settings': {'QUILLMD_DEEPGRAM_SMART_FORMAT': 'true'}},
                 {'settings': {'QUILLMD_WORD_ENGINE': 'legacy'}},
                 {'pricing_version': self.d.pricing_version('ordinary_notes')}]
        for change in cases:
            with self.subTest(change=change):
                self.assertTrue(self.problems('transcription', **change))
        without = dataclasses.replace(self.d, transcription=None)
        self.assertIn('the declaration declares no transcription terms', st.check_configuration(
            snapshot(self.d, self.root, 'transcription'), without, 'transcription', self.root, rebuild=self.worktree))
        flags = st.stage_flags('transcription', self.d)
        self.assertEqual((flags['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'], flags['QUILLMD_DEEPGRAM_RATE_PER_SECOND'],
                          flags['QUILLMD_DEEPGRAM_MIP_OPT_OUT'], flags['QUILLMD_DEEPGRAM_SMART_FORMAT'],
                          flags['QUILLMD_WORD_ENGINE']), ('0.0077', '', 'true', 'false', 'v3'))
        self.assertNotIn('QUILLMD_DEEPGRAM_RATE_PER_MINUTE', st.stage_flags('notes_comparison', self.d))

    def test_the_configuration_check_demands_the_declared_smart_formatting(self):
        on = parse(self, edited('transcription_smart_format: false', 'transcription_smart_format: true'))
        def problems(declaration, value):
            return st.check_configuration(snapshot(declaration, self.root, 'transcription',
                                                   settings={'QUILLMD_DEEPGRAM_SMART_FORMAT': value}),
                                          declaration, 'transcription', self.root, rebuild=self.worktree)
        self.assertEqual(problems(on, 'true'), [])
        self.assertTrue(problems(on, 'false'))
        self.assertEqual(problems(self.d, 'false'), [])
        self.assertTrue(problems(self.d, 'true'))

    def test_a_contract_flag_other_than_the_stages_is_a_problem(self):
        cases = [('model_check', {'V3_FIELD_RELATIONS': True}), ('model_check', {'WM_NARRATIVE': True}),
                 ('model_check', {'QUILLMD_MAPPING_ASSISTANCE': True}), ('model_check', {'QUILLMD_WORD_ENGINE': 'v3'}),
                 ('notes_comparison', {'V3_FIELD_RELATIONS': True}), ('notes_comparison', {'V3_GENERATION_BATCHES': True}),
                 ('notes_comparison', {'V3_HISTORY_CONTEXT': True}), ('mapping', {'QUILLMD_MAPPING_ASSISTANCE_LIVE': False}),
                 ('mapping', {'QUILLMD_LAYOUT_SOCKET': '/run/quillmd/layout.sock'})]
        for stage, flags in cases:
            with self.subTest(stage=stage, flags=flags):
                found = self.problems(stage, settings=flags)
                self.assertTrue(found and all('contract flag' in p for p in found), found)

    def test_a_database_other_than_the_declared_qa_one_is_a_problem(self):
        cases = [{'NAME': 'quillmd_qa_sonnet5', 'HOST': '127.0.0.1', 'PORT': '55731'},
                 {'NAME': 'quillmd_qa_other', 'HOST': '127.0.0.1', 'PORT': '55731'},
                 {'NAME': self.d.qa_database, 'HOST': '10.0.0.5', 'PORT': '55731'},
                 {'NAME': 'quillmd_fresh', 'HOST': '127.0.0.1', 'PORT': '55438'}]
        for database in cases:
            with self.subTest(database=database):
                self.assertTrue(self.problems(database=database))
        installed = self.problems(database={'NAME': self.d.qa_database, 'HOST': '127.0.0.1', 'PORT': '55438'})
        self.assertTrue(any('installed release' in p for p in installed), installed)

    def test_the_installed_worker_route_is_a_problem(self):
        self.assertTrue(any('installed tree' in p for p in self.problems(rebuild=st.INSTALLED['tree'])))
        self.assertTrue(any('installed tree' in p for p in self.problems(rebuild=st.INSTALLED['tree'] / 'ops')))
        found = self.problems(state_dir='/var/lib/quillmd', media_root='/var/lib/quillmd/files')
        self.assertTrue(any('installed release\'s state' in p for p in found), found)
        self.assertTrue(any('not under the campaign root' in p for p in found), found)
        self.assertTrue(self.problems(state_dir=str(scratch(self) / 'elsewhere')))

    def test_another_mode_model_rate_or_profile_is_a_problem(self):
        cases = [{'synthetic_only': False}, {'data_mode': 'real'}, {'ai_mode': 'fixture'}, {'model': 'claude-sonnet-5'},
                 {'provider': 'openai'}, {'rates': {'input': '2', 'output': '10', 'cached': '0.20'}},
                 {'thinking': 'adaptive'}, {'effort': 'high'}, {'inference_geo': 'us'},
                 {'request_profile': {'invalid': 'no profile'}},
                 {'request_profile': {'profile': 'x', 'max_output_tokens': 20001, 'timeout_seconds': 120}},
                 {'request_profile': {'profile': 'x', 'max_output_tokens': 8000, 'timeout_seconds': 181}},
                 {'request_profile': {'profile': 'x', 'max_output_tokens': '8000', 'timeout_seconds': 120}},
                 {'pricing_version': 'configured-v1:' + 'e' * 64}]
        for change in cases:
            with self.subTest(change=change):
                self.assertTrue(self.problems(**change))


# ── credential and door ──────────────────────────────────────────────────────────────────────────────────────────

class CredentialAndDoorTests(Base):
    def test_the_credential_file_with_the_wrong_mode_is_refused(self):
        folder = scratch(self) / 'credential'
        folder.mkdir(mode=0o700)
        key = folder / 'anthropic-api-key'
        key.write_text(SYNTHETIC_KEY + '\n')
        d = dataclasses.replace(parse(self), credential_file=str(key))
        os.chmod(key, 0o644)
        with self.assertRaisesRegex(pc.Refused, 'mode 0600'):
            pc.load_credential(d.credential_file, d)
        os.chmod(key, 0o600)
        self.assertEqual(pc.load_credential(d.credential_file, d), SYNTHETIC_KEY)
        with self.assertRaisesRegex(pc.Refused, 'Only the declared credential_file'):
            pc.load_credential(str(folder / 'other'), d)

    def test_only_the_ruled_mutation_door_for_this_declaration_and_commit_opens(self):
        d = parse(self)
        relative = str(Path(d.path).relative_to(d.repository))
        with self.assertRaisesRegex(pc.Refused, 'ruled-mutation door'):
            st.require_door(d, {})
        with self.assertRaisesRegex(pc.Refused, 'another declaration'):
            st.require_door(d, {'RULED_MUTATION_DECLARATION': 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-'
                                                              'staged-campaign.md', 'RULED_MUTATION_DECL_COMMIT': d.commit})
        with self.assertRaisesRegex(pc.Refused, 'another commit'):
            st.require_door(d, {'RULED_MUTATION_DECLARATION': relative, 'RULED_MUTATION_DECL_COMMIT': '0' * 40})
        self.assertEqual(st.require_door(d, {'RULED_MUTATION_DECLARATION': relative,
                                             'RULED_MUTATION_DECL_COMMIT': d.commit})['commit'], d.commit)
        self.assertEqual(st.require_door(d, {'RULED_MUTATION_DECLARATION': d.path,
                                             'RULED_MUTATION_DECL_COMMIT': d.commit})['commit'], d.commit)

    def test_with_no_live_declaration_committed_nothing_is_read_or_sent(self):
        missing = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20261001-standing-test-never-committed.md'
        self.assertFalse(missing.exists())

        def forbidden(*args, **kwargs):
            raise AssertionError('a credential or a database password was read')
        with patch.object(st, 'DECLARATION', missing), patch.object(pc, 'load_credential', forbidden), \
                patch.object(pc, 'read_private', forbidden), patch.object(os, 'execve', forbidden), \
                patch.object(st, 'ensure_database', forbidden):
            for argv in (['run', '--stage', 'model_check'], ['preflight'], ['run', '--stage', 'notes_comparison']):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(st.main(argv), 2, argv)
                self.assertIn('REFUSED', err.getvalue())


# ── the two processes: outer (the door, then a scrubbed exec) and inner (re-checks, then the preflight) ──────────────

class ProcessTests(Base):
    """outer() and inner() for the preflight in a scratch checkout whose LIVE declaration names scratch places (the
    runner's constants patched to them): what outer() hands the request process, and inner() re-checking everything
    and making the ONE models request through the guard (the network is a MockTransport)."""

    def setUp(self):
        self.repo = scratch(self)
        self.live_root = self.repo / 'runtime' / 'v1-standing-api-testing-20261001'
        secret_dir = self.repo / 'secrets'
        secret_dir.mkdir(mode=0o700)
        self.key = secret_dir / 'anthropic-api-key'
        self.key.write_text(SYNTHETIC_KEY + '\n')
        os.chmod(self.key, 0o600)
        self.deepgram = secret_dir / 'deepgram-api-key'
        self.deepgram.write_text(DEEPGRAM_KEY + '\n')
        os.chmod(self.deepgram, 0o600)
        password = secret_dir / 'password'
        password.write_text('synthetic-qa-password\n')
        os.chmod(password, 0o600)
        ledger, digest = rights_ledger(self, RESTRICTED_SAMPLE)
        where = {'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001': f'root: {self.live_root}',
                 'credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key':
                     f'credential_file: {self.key}',
                 'transcription_credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/'
                 'deepgram-api-key': f'transcription_credential_file: {self.deepgram}',
                 'qa_database_password_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password':
                     f'qa_database_password_file: {password}',
                 'restricted_inputs_ledger: /opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/'
                 '053-original-dev40-exact-rights-ledger.json': f'restricted_inputs_ledger: {ledger}',
                 'restricted_inputs_ledger_sha256: 5abaabb031c6e1552944dab1bc3e7fbd3ae5876436c840ffe1ee6312281851d7':
                     f'restricted_inputs_ledger_sha256: {digest}'}
        git(self.repo, 'init', '-q')
        (self.repo / 'docs' / 'foundation' / 'mutations').mkdir(parents=True)
        (self.repo / st.AUTHORITY_RECORD).parent.mkdir(parents=True)
        (self.repo / st.AUTHORITY_RECORD).write_bytes(RECORD.read_bytes())
        self.declaration_path = self.repo / 'docs' / 'foundation' / 'mutations' / DECLARATION_NAME
        self.declaration_path.write_text(fill_template(FIXTURE_VALUES, 'live', where), encoding='utf-8')
        (self.repo / 'rebuild').mkdir()
        (self.repo / 'rebuild' / 'README').write_text('scratch checkout\n')
        (self.repo / '.gitignore').write_text('runtime/\nsecrets/\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'Scratch live declaration')
        self.commit = git(self.repo, 'log', '-1', '--format=%H').stdout.decode().strip()
        for name, value in (('DECLARATION', self.declaration_path), ('REBUILD', self.repo / 'rebuild'),
                            ('RUNTIME', self.repo / 'runtime')):
            patcher = patch.object(st, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.door = {'RULED_MUTATION_DECLARATION': f'docs/foundation/mutations/{DECLARATION_NAME}',
                     'RULED_MUTATION_DECL_COMMIT': self.commit}

    def outer(self, environ):
        captured = {}

        def execve(path, argv, env):
            captured.update(path=path, argv=argv, env=env)
            raise SystemExit('execve captured')
        with patch.dict(os.environ, environ), patch.object(os, 'execve', execve), patch.object(os, 'chdir'), \
                redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                st.outer('preflight')
        return captured

    def inner(self, env, **patches):
        """st.inner() under `env` (nothing else in the environment), with the process-wide umask and signal handlers
        patched (this is the test process) and the ledger lock it takes released afterwards (a real request process
        holds it for life; a second inner() here would otherwise meet it)."""
        held, real = [], pc.hold_lock

        def hold(path):
            fd = real(path)
            held.append(fd)
            return fd
        try:
            with patch.dict(os.environ, env, clear=True), patch.object(os, 'umask'), patch.object(st.signal, 'signal'), \
                    patch.object(pc, 'hold_lock', hold), redirect_stderr(io.StringIO()):
                return st.inner()
        finally:
            for fd in held:
                os.close(fd)

    def test_outside_the_door_nothing_is_read(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('the credential was read outside the door')
        with patch.object(pc, 'load_credential', forbidden), patch.dict(os.environ, {}, clear=False), \
                redirect_stderr(io.StringIO()):
            os.environ.pop('RULED_MUTATION_DECLARATION', None)
            os.environ.pop('RULED_MUTATION_DECL_COMMIT', None)
            with self.assertRaisesRegex(pc.Refused, 'ruled-mutation door'):
                st.outer('preflight')
            with patch.dict(os.environ, {**self.door, 'RULED_MUTATION_DECL_COMMIT': '0' * 40}):
                with self.assertRaisesRegex(pc.Refused, 'another commit'):
                    st.outer('preflight')
        self.assertFalse(self.live_root.exists())

    def test_the_stop_file_refuses_before_the_credential_is_read(self):
        self.live_root.mkdir(parents=True, mode=0o700)
        (self.live_root / st.STOP_NAME).write_text('')

        def forbidden(*args, **kwargs):
            raise AssertionError('the credential was read under the Stop file')
        with patch.object(pc, 'load_credential', forbidden), patch.dict(os.environ, self.door), \
                redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(pc.Refused, 'Stop file'):
                st.outer('preflight')

    def test_outer_hands_the_request_process_a_scrubbed_environment_and_inner_makes_one_models_request(self):
        import httpx
        captured = self.outer({**self.door, 'ANTHROPIC_BASE_URL': 'https://example.invalid', 'HTTPS_PROXY': 'x',
                               'ANTHROPIC_AUTH_TOKEN': 'synthetic-token'})
        env = captured['env']
        self.assertEqual(captured['argv'][-1], '_inner')
        self.assertEqual(env['ANTHROPIC_API_KEY'], SYNTHETIC_KEY)
        self.assertNotIn(st.TRANSCRIPTION_KEY_VARIABLE, env)                     # (not a transcription run)
        self.assertFalse([value for value in env.values() if DEEPGRAM_KEY in value])
        self.assertFalse([name for name in env if pc.forbidden_name(name)])
        self.assertNotIn('ANTHROPIC_BASE_URL', env)
        self.assertNotIn('ANTHROPIC_AUTH_TOKEN', env)
        self.assertEqual((env['RULED_MUTATION_DECLARATION'], env['RULED_MUTATION_DECL_COMMIT']),
                         (self.door['RULED_MUTATION_DECLARATION'], self.commit))
        self.assertEqual((env['QUILLMD_AI_MODEL'], env['QUILLMD_ENV_MANAGED'], env['QUILLMD_DB_NAME']),
                         ('claude-sonnet-5-5', '1', st.DATABASE_NAME))
        context = json.loads(env[st.CONTEXT_VARIABLE])
        self.assertEqual((context['command'], context['root']), ('preflight', str(self.live_root)))
        self.assertEqual(sorted(os.listdir(self.live_root)), sorted(['ledger', 'runs', 'evidence', 'preflight',
                                                                     'qa-state', 'access', 'home', 'tmp', 'forms']))
        calls = []

        def models(request):
            calls.append((request.method, str(request.url)))
            return httpx.Response(200, json={'id': 'claude-sonnet-5-5', 'type': 'model',
                                             'display_name': 'Claude Sonnet 5.5'})
        out = io.StringIO()
        with patch.object(httpx, 'HTTPTransport', lambda: httpx.MockTransport(models)), redirect_stdout(out):
            code = self.inner(env)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [('GET', 'https://api.anthropic.com/v1/models/claude-sonnet-5-5')])
        result = json.loads(out.getvalue())
        self.assertEqual((result['matches_declared'], result['model_returned']), (True, 'claude-sonnet-5-5'))
        self.assertNotIn(SYNTHETIC_KEY, out.getvalue())
        self.assertEqual(pc.leaked(self.live_root, SYNTHETIC_KEY), [])
        # (the request process re-checks the door itself: the same environment without it is refused)
        # (and the credential it was handed must be the declared file's, byte for byte)
        with self.assertRaisesRegex(pc.Refused, 'does not carry the declared credential'):
            self.inner({**env, 'ANTHROPIC_API_KEY': SYNTHETIC_KEY.replace('2222', '9999')})
        with self.assertRaisesRegex(pc.Refused, 'ruled-mutation door'):
            self.inner({k: v for k, v in env.items() if not k.startswith('RULED_MUTATION_')})
        (self.live_root / st.STOP_NAME).write_text('')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            self.inner(env)
        self.assertEqual(len(calls), 1)


    # ── the Deepgram key: read for a transcription run only, by the Anthropic key's rules, before anything is sent ──
    def outer_run(self, stage, **patches):
        """outer('run', stage) with the database and the exec stood in; returns what execve was handed."""
        captured = {}

        def execve(path, argv, env):
            captured.update(path=path, argv=argv, env=env)
            raise SystemExit('execve captured')
        with patch.dict(os.environ, self.door), patch.object(os, 'execve', execve), patch.object(os, 'chdir'), \
                patch.object(st, 'ensure_database', lambda password, name: None), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                st.outer('run', stage)
        return captured

    def test_outer_hands_the_deepgram_key_to_a_transcription_runs_environment_only(self):
        captured = self.outer_run('transcription')
        env, argv = captured['env'], captured['argv']
        self.assertEqual(env[st.TRANSCRIPTION_KEY_VARIABLE], DEEPGRAM_KEY)            # (the run that needs it has it)
        self.assertEqual(argv, [sys.executable, '-B', str(st.RUNNER), '_inner'])
        self.assertFalse([part for part in argv if DEEPGRAM_KEY in part or SYNTHETIC_KEY in part])
        self.assertNotIn(DEEPGRAM_KEY, env[st.CONTEXT_VARIABLE])
        self.assertEqual([name for name, value in env.items() if DEEPGRAM_KEY in value], [st.TRANSCRIPTION_KEY_VARIABLE])
        self.assertEqual((env['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'], env['QUILLMD_DEEPGRAM_RATE_PER_SECOND'],
                          env['QUILLMD_DEEPGRAM_MIP_OPT_OUT'], env['QUILLMD_DEEPGRAM_SMART_FORMAT']),
                         ('0.0077', '', 'true', 'false'))
        self.assertFalse([name for name in env if pc.forbidden_name(name)])

        def forbidden(*args, **kwargs):
            raise AssertionError('the Deepgram credential was read for a run that is not a transcription run')
        with patch.object(st, 'load_transcription_credential', forbidden):
            for stage in ('notes_comparison', 'mapping', 'model_check'):
                with self.subTest(stage=stage):
                    env = self.outer_run(stage)['env']
                    self.assertNotIn(st.TRANSCRIPTION_KEY_VARIABLE, env)
                    self.assertFalse([value for value in env.values() if DEEPGRAM_KEY in value])
                    self.assertEqual(env['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'], '0.0043')
            preflight = self.outer({**self.door})['env']
            self.assertNotIn(st.TRANSCRIPTION_KEY_VARIABLE, preflight)

    def test_a_bad_deepgram_key_file_refuses_a_transcription_run_before_anything_is_sent(self):
        good = self.deepgram.read_bytes()

        def forbidden(*args, **kwargs):
            raise AssertionError('the run went past the Deepgram credential')
        cases = {'missing': lambda: self.deepgram.unlink(),
                 'mode 0644': lambda: os.chmod(self.deepgram, 0o644),
                 'mode 0640': lambda: os.chmod(self.deepgram, 0o640),
                 'mode 0400': lambda: os.chmod(self.deepgram, 0o400),
                 'symbolic link': lambda: (self.deepgram.rename(self.deepgram.with_name('real-key')),
                                           self.deepgram.symlink_to(self.deepgram.with_name('real-key'))),
                 'hard link': lambda: os.link(self.deepgram, self.deepgram.with_name('second-name')),
                 'two lines': lambda: self.deepgram.write_text(DEEPGRAM_KEY + '\n' + DEEPGRAM_KEY + '\n'),
                 'empty': lambda: self.deepgram.write_text('')}
        why = {'missing': 'does not exist', 'mode 0644': 'mode 0600', 'mode 0640': 'mode 0600', 'mode 0400': 'mode 0600',
               'symbolic link': 'symbolic link', 'hard link': 'another name', 'two lines': 'one non-empty line',
               'empty': 'one line'}
        for name, damage in cases.items():
            with self.subTest(damage=name):
                for leftover in ('real-key', 'second-name'):
                    if os.path.lexists(self.deepgram.with_name(leftover)):
                        os.unlink(self.deepgram.with_name(leftover))
                if os.path.lexists(self.deepgram):
                    os.unlink(self.deepgram)
                self.deepgram.write_bytes(good)
                os.chmod(self.deepgram, 0o600)
                damage()
                with patch.dict(os.environ, self.door), patch.object(os, 'execve', forbidden), \
                        patch.object(st, 'ensure_database', forbidden), patch.object(pc, 'read_private', forbidden), \
                        redirect_stderr(io.StringIO()):
                    with self.assertRaisesRegex(pc.Refused, f'The Deepgram credential: .*{why[name]}'):
                        st.outer('run', 'transcription')

    def test_a_deepgram_file_holding_the_anthropic_key_refuses_a_transcription_run_before_anything_is_sent(self):
        """L1:R1-F2: the declared Deepgram file is a path of its own, mode 0600, one name, one line — and holds the
        Anthropic key (shaped, or an unshaped value equal to the Anthropic file's). outer() refuses before the
        password, the database or the exec, so no request process ever carries it as DEEPGRAM_API_KEY."""
        def forbidden(*args, **kwargs):
            raise AssertionError('the run went past the Deepgram credential')
        plain = 'plain-standing-credential-6666666666666666'
        for name, (anthropic, deepgram) in {'a copy of the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY),
                                            'an unshaped copy': (plain, plain),
                                            'the Anthropic key inside a longer line': (SYNTHETIC_KEY,
                                                                                       'x' + SYNTHETIC_KEY)}.items():
            with self.subTest(case=name):
                self.key.write_text(anthropic + '\n')
                os.chmod(self.key, 0o600)
                self.deepgram.write_text(deepgram + '\n')
                os.chmod(self.deepgram, 0o600)
                self.assertNotEqual(os.path.abspath(self.deepgram), os.path.abspath(self.key))  # (paths differ)
                with patch.dict(os.environ, self.door), patch.object(os, 'execve', forbidden), \
                        patch.object(st, 'ensure_database', forbidden), patch.object(pc, 'read_private', forbidden), \
                        redirect_stderr(io.StringIO()):
                    with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own') as caught:
                        st.outer('run', 'transcription')
                self.assertNotIn(anthropic, str(caught.exception))
                self.assertNotIn(deepgram, str(caught.exception))

    def test_inner_refuses_a_deepgram_key_that_is_the_anthropic_key(self):
        """L1:R1-F2 in the request process: its environment and the declared file both hold the Anthropic key as the
        Deepgram key (outer() was passed with good files) — the shaped key, or an unshaped Anthropic key, so the
        comparison itself is exercised and not only the shape. inner() refuses before any request."""
        import httpx
        calls = []

        def anything(request):
            calls.append(request)
            return httpx.Response(500)
        for name, anthropic in {'a copy of the Anthropic key': SYNTHETIC_KEY,
                                'an unshaped copy': 'plain-standing-credential-9999999999999999'}.items():
            with self.subTest(case=name):
                self.key.write_text(anthropic + '\n')
                self.deepgram.write_text(DEEPGRAM_KEY + '\n')
                env = self.outer_run('transcription')['env']
                self.assertEqual((env[st.TRANSCRIPTION_KEY_VARIABLE], env['ANTHROPIC_API_KEY']),
                                 (DEEPGRAM_KEY, anthropic))                       # (positive control: a good run)
                self.deepgram.write_text(anthropic + '\n')
                with patch.object(httpx, 'HTTPTransport', lambda: httpx.MockTransport(anything)), \
                        self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own'):
                    self.inner({**env, st.TRANSCRIPTION_KEY_VARIABLE: anthropic})
                self.assertEqual(calls, [])                                     # (nothing was sent)

    def test_inner_refuses_a_deepgram_key_outside_a_transcription_run(self):
        import httpx
        env = self.outer({**self.door})['env']                                 # (the preflight's own environment)
        calls = []

        def models(request):
            calls.append(request)
            return httpx.Response(200, json={'id': 'claude-sonnet-5-5'})
        with patch.object(httpx, 'HTTPTransport', lambda: httpx.MockTransport(models)), \
                self.assertRaisesRegex(pc.Refused, 'not a transcription run'):
            self.inner({**env, st.TRANSCRIPTION_KEY_VARIABLE: DEEPGRAM_KEY})
        self.assertEqual(calls, [])                                             # (nothing was sent)


# ── the preflight ────────────────────────────────────────────────────────────────────────────────────────────────

class PreflightTests(Base):
    def setUp(self):
        self.campaign_ = self.campaign()
        self.calls = []
        self.answer = (200, {'id': 'claude-sonnet-5-5', 'type': 'model', 'display_name': 'Claude Sonnet 5.5',
                             'created_at': '2026-09-30T00:00:00Z', 'max_input_tokens': 1000000, 'max_tokens': 128000})

    def transport(self):
        import httpx

        def handler(request):
            self.calls.append((request.method, str(request.url), dict(request.headers)))
            status, body = self.answer
            return httpx.Response(status, headers={'request-id': 'req_synthetic_models'}, json=body)
        return httpx.MockTransport(handler)

    def test_the_guard_is_on(self):
        network_guard.positive_control(self)

    def test_one_get_to_the_declared_models_url_is_recorded_and_compared(self):
        result = st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
        self.assertEqual(len(self.calls), 1)
        method, url, headers = self.calls[0]
        self.assertEqual((method, url), ('GET', 'https://api.anthropic.com/v1/models/claude-sonnet-5-5'))
        self.assertEqual(headers['x-api-key'], SYNTHETIC_KEY)                    # (the real request carried it)
        self.assertTrue(result['matches_declared'])
        self.assertEqual((result['model_returned'], result['display_name'], result['max_tokens']),
                         ('claude-sonnet-5-5', 'Claude Sonnet 5.5', 128000))
        self.assertIs(result['generation_proof'], False)
        self.assertIn('not', result['statement'])
        evidence = self.campaign_.root / 'preflight' / '001'
        request = json.loads((evidence / 'request.json').read_text())
        self.assertEqual((request['method'], request['url']), ('GET', 'https://api.anthropic.com/v1/models/claude-sonnet-5-5'))
        self.assertNotIn('x-api-key', request['headers'])
        self.assertEqual(json.loads((evidence / 'result.json').read_text())['model_returned'], 'claude-sonnet-5-5')
        self.assertEqual(pc.leaked(self.campaign_.root, SYNTHETIC_KEY), [])
        self.assertEqual(st.require_preflight(self.campaign_)['preflight'], 1)
        self.assertEqual(self.campaign_.ledger.rows(), [])                      # (not a paid attempt)

    def test_another_id_or_an_error_never_matches_and_run_stays_refused(self):
        self.answer = (200, {'id': 'claude-sonnet-5', 'type': 'model', 'display_name': 'Claude Sonnet 5'})
        self.assertFalse(st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
                         ['matches_declared'])
        self.answer = (404, {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model not found'}})
        result = st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
        self.assertFalse(result['matches_declared'])
        self.assertEqual(result['error'], {'class': 'NotFoundError', 'status_code': 404})
        self.assertEqual(len(self.calls), 2)                                     # (one request each, no retry)
        with self.assertRaisesRegex(pc.Refused, 'No preflight has shown'):
            st.require_preflight(self.campaign_)

    def test_another_url_method_or_a_second_request_is_refused_before_it_leaves(self):
        import httpx
        evidence = scratch(self)
        guard = st._preflight_transport_class()(self.transport(), st.MODELS_URL + 'claude-sonnet-5-5', evidence,
                                                SYNTHETIC_KEY)
        with self.assertRaisesRegex(pc.Refused, 'only GET'):
            guard.handle_request(httpx.Request('POST', st.MODELS_URL + 'claude-sonnet-5-5'))
        with self.assertRaisesRegex(pc.Refused, 'only GET'):
            guard.handle_request(httpx.Request('GET', 'https://api.anthropic.com/v1/messages'))
        with self.assertRaisesRegex(pc.Refused, 'only GET'):
            guard.handle_request(httpx.Request('GET', 'https://api.deepgram.com/v1/listen'))
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(pc.Refused, 'exactly the declared credential'):
            guard.handle_request(httpx.Request('GET', st.MODELS_URL + 'claude-sonnet-5-5'))
        with self.assertRaisesRegex(pc.Refused, 'exactly the declared credential'):
            guard.handle_request(httpx.Request('GET', st.MODELS_URL + 'claude-sonnet-5-5',
                                               headers={'x-api-key': SYNTHETIC_KEY, 'authorization': 'Bearer other'}))
        self.assertEqual(self.calls, [])
        guard.handle_request(httpx.Request('GET', st.MODELS_URL + 'claude-sonnet-5-5', headers={'x-api-key': SYNTHETIC_KEY}))
        with self.assertRaisesRegex(pc.Refused, 'second preflight request'):
            guard.handle_request(httpx.Request('GET', st.MODELS_URL + 'claude-sonnet-5-5', headers={'x-api-key': SYNTHETIC_KEY}))
        self.assertEqual(len(self.calls), 1)

    def test_the_stop_file_refuses_the_preflight(self):
        self.campaign_.stop_file().write_text('')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
        self.assertEqual(self.calls, [])


# ── the request bounds at the capture ────────────────────────────────────────────────────────────────────────────

class RequestBoundsTests(unittest.TestCase):
    def setUp(self):
        import anthropic
        import httpx
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True, mode=0o700)
        self.seen = []

        def handler(request):
            self.seen.append(request)
            return httpx.Response(200, json={'id': 'msg_synthetic', 'type': 'message', 'role': 'assistant',
                                             'model': 'claude-sonnet-5-5', 'content': [{'type': 'text', 'text': '{}'}],
                                             'stop_reason': 'end_turn', 'stop_sequence': None,
                                             'usage': {'input_tokens': 10, 'output_tokens': 2}})
        self.client = anthropic.Anthropic(api_key=SYNTHETIC_KEY, max_retries=0,
                                          http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        pc.install_request_capture()
        self.addCleanup(pc.uninstall_request_capture)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)
        self.addCleanup(pc.REQUEST_BOUNDS.clear)
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        pc.REQUEST_BOUNDS.update(model='claude-sonnet-5-5', max_tokens=20000)

    def send(self, model='claude-sonnet-5-5', max_tokens=8000):
        return self.client.messages.create(model=model, max_tokens=max_tokens,
                                           messages=[{'role': 'user', 'content': 'synthetic'}])

    def test_another_model_or_more_output_is_refused_before_it_is_recorded_or_sent(self):
        for model, tokens in (('claude-sonnet-5', 8000), ('claude-sonnet-5-5', 20001), ('claude-opus-5', 8000)):
            with self.subTest(model=model, tokens=tokens), self.assertRaisesRegex(pc.Refused, 'per-request bounds'):
                self.send(model, tokens)
        self.assertEqual(self.seen, [])
        self.assertFalse((self.evidence / 'request.json').exists())

    def test_a_request_inside_the_bounds_is_captured_and_sent(self):
        self.send()
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(json.loads((self.evidence / 'request.json').read_text())['body_json']['max_tokens'], 8000)


# ── the historical campaign ──────────────────────────────────────────────────────────────────────────────────────

class HistoricalTests(Base):
    def test_its_declaration_is_byte_identical(self):
        self.assertEqual(hashlib.sha256(HISTORICAL_DECLARATION.read_bytes()).hexdigest(), HISTORICAL_DECLARATION_SHA256)

    def test_its_runner_refuses_every_write_before_reading_anything(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('the historical runner read something before refusing')
        with patch.object(pc, 'declared', forbidden), patch.object(pc, 'load_credential', forbidden), \
                patch.object(pc, 'read_private', forbidden), patch.object(os, 'execve', forbidden):
            for argv in (['run', '--stage', 'model_check'], ['run', '--stage', 'mapping'],
                         ['run', '--stage', 'ordinary_notes'], ['reopen', '--stage', 'mapping', '--diagnosis', 'x'],
                         ['recover']):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(sq.main(argv), 2, argv)
                self.assertIn('closed for new sends', err.getvalue())

    def test_its_request_process_refuses_at_any_root_before_reading_anything(self):
        """Refutation R1-F1: `_inner` started by hand with a context naming a FRESH root and the historical declaration
        passed every check and reached the database migration — a fresh ledger, so the closed $40 authority with its
        budget reset. The campaign is closed, not its directory: the request process refuses wherever it is pointed."""
        def forbidden(*args, **kwargs):
            raise AssertionError('the historical request process read something before refusing')
        for root in (scratch(self) / 'fresh-root', sq.HISTORICAL_ROOT, st.LIVE_ROOT):
            context = json.dumps({'root': str(root), 'declaration': str(HISTORICAL_DECLARATION), 'stage': 'model_check',
                                  'runner_commit': RUNNER_COMMIT})
            err = io.StringIO()
            with self.subTest(root=root), patch.dict(os.environ, {'SONNET5_QA_CONTEXT': context,
                                                                  'QUILLMD_ENV_MANAGED': '1'}, clear=True), \
                    patch.object(sq, 'env_file_present', return_value=False), patch.object(pc, 'declared', forbidden), \
                    patch.object(pc, 'load_credential', forbidden), patch.object(pc, 'Campaign', forbidden), \
                    patch.object(pc, 'scrubbed_now', forbidden), patch('django.setup', forbidden), \
                    patch('signal.signal'), patch('os.umask', return_value=0o022):
                with redirect_stderr(err):
                    code = sq.main(['_inner'])
                self.assertEqual(code, 2)
                self.assertIn('closed for new sends', err.getvalue())

    def test_its_run_command_refuses_whatever_root_it_is_given(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('the historical runner read something before refusing')
        for root in (scratch(self) / 'fresh-root', sq.HISTORICAL_ROOT):
            err = io.StringIO()
            with self.subTest(root=root), patch.object(sq, 'LIVE_ROOT', root), patch.object(pc, 'declared', forbidden), \
                    patch.object(pc, 'git_identity', forbidden), patch.object(pc, 'load_credential', forbidden), \
                    patch.object(pc, 'read_private', forbidden), patch.object(os, 'execve', forbidden), \
                    patch('sys.stdout', io.StringIO()):
                with redirect_stderr(err):
                    code = sq.main(['run', '--stage', 'model_check'])
                self.assertEqual(code, 2)
                self.assertIn('closed for new sends', err.getvalue())

    def test_its_closure_covers_the_root_and_everything_under_it_and_nothing_else(self):
        for root in (sq.HISTORICAL_ROOT, sq.HISTORICAL_ROOT / 'ledger', sq.HISTORICAL_ROOT.parent):
            with self.subTest(root=root), self.assertRaisesRegex(pc.Refused, 'closed for new sends'):
                sq.require_not_historical(root)
        sq.require_not_historical(scratch(self))
        sq.require_not_historical(st.LIVE_ROOT)

    def test_its_status_stays_readable(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(sq.status(root=scratch(self) / 'empty'), 0)
        report = json.loads(out.getvalue())
        self.assertEqual((report['campaign'], report['total']['limit']), (st.HISTORICAL['campaign'], '40.00'))

    @unittest.skipUnless(os.access(sq.HISTORICAL_ROOT / 'ledger', os.R_OK), 'the historical ledger is on the VPS only')
    def test_the_live_historical_ledger_reads_as_recorded(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(sq.status(), 0)
        report = json.loads(out.getvalue())
        self.assertEqual((len(report['outcomes']), report['total']['exposure'], report['open_attempts']),
                         (24, '0.130880', []))
        self.assertEqual({k: v['state'] for k, v in report['stages'].items()},
                         {'model_check': 'passed', 'mapping': 'failed', 'ordinary_notes': 'failed'})

    def test_its_declaration_and_ledger_are_never_a_standing_campaigns(self):
        with self.assertRaises(pc.Refused):
            parse(self, HISTORICAL_DECLARATION.read_text(encoding='utf-8'))
        d = parse(self)
        with self.assertRaisesRegex(pc.Refused, 'historical campaign\'s root'):
            st.StandingCampaign(d, sq.HISTORICAL_ROOT)
        root = scratch(self) / 'old'
        ledger = pc.Ledger(root / 'ledger')
        ledger.acquire()
        self.addCleanup(ledger.release)
        ledger.write_attempt({'number': 1, 'campaign': st.HISTORICAL['campaign'], 'authority_id':
                              st.HISTORICAL['authority_id'], 'stage': 'model_check', 'maximum_cost': '0.01'})
        with self.assertRaisesRegex(pc.Refused, 'another campaign or authority'):
            st.StandingCampaign(d, root).rows()
        ledger.release()
        root2 = scratch(self) / 'forged'
        forged = pc.Ledger(root2 / 'ledger')
        forged.acquire()
        self.addCleanup(forged.release)
        forged.write_attempt({'number': 1, 'campaign': d.campaign, 'authority_id': d.authority_id,
                              'stage': 'model_check', 'maximum_cost': '0.01'})
        with self.assertRaisesRegex(pc.Refused, 'not a standing campaign attempt'):
            st.StandingCampaign(d, root2).rows()


# ── plans ────────────────────────────────────────────────────────────────────────────────────────────────────────

class PlanTests(Base):
    @classmethod
    def setUpClass(cls):
        cls.inputs = sq.stages_module().frozen_inputs()
        cls.definitions = st.plan_definitions(cls.inputs)

    def test_the_model_check_and_mapping_plans(self):
        self.assertEqual([s['id'] for s in self.definitions['model_check']['sends']], [st.MODEL_CHECK_SEND])
        self.assertEqual(self.definitions['model_check']['sends'][0]['inputs'],
                         {'form_sha256': sq.FORM_SHA256, 'notes_sha256': sq.NOTES_SHA256})
        mapping = [s['id'] for s in self.definitions['mapping']['sends']]
        self.assertEqual(mapping, [f'mapping:{name}' for name in sq.stages_module().MAPPING_ORDER]
                         + ['generation:f6a-long-answer', 'generation:f6b-admin-missing'])
        self.assertTrue(all(s['pricing_key'] == 'mapping' for s in self.definitions['mapping']['sends']))

    def test_the_notes_comparison_sends_14_cases_on_both_requests(self):
        sends = self.definitions['notes_comparison']['sends']
        self.assertEqual(len(sends), 28)
        default = [s for s in sends if s['path'] == 'default']
        relations = [s for s in sends if s['path'] == 'field_relations']
        cases = ['N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N08', 'N09', 'N10', 'N11', 'N12', 'N13', 'N16']
        self.assertEqual(sorted(s['case'] for s in default), cases)
        self.assertEqual([s['case'] for s in relations], cases)
        self.assertEqual(sends[-14:], relations)                      # (the relations path runs last)
        self.assertEqual({s['pricing_key'] for s in default}, {'ordinary_notes'})
        self.assertEqual({s['pricing_key'] for s in relations}, {'ordinary_notes_field_relations'})
        for send in sends:
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == send['case'])
            self.assertEqual(send['inputs']['notes_sha256'], hashlib.sha256(case['notes'].encode()).hexdigest())

    def test_d30_d31_structure_is_not_established(self):
        self.assertFalse(self.definitions['d30_d31_structure']['established'])
        self.assertIn('no provider upload', self.definitions['d30_d31_structure']['statement'])
        with self.assertRaisesRegex(pc.Refused, 'not established'):
            st.standing_plan('d30_d31_structure', self.inputs)

    def test_the_transcription_plan_is_two_sends_per_allowlisted_recording(self):
        entry = self.definitions['transcription']
        self.assertTrue(entry['established'])
        self.assertEqual([s['id'] for s in entry['sends']],
                         ['transcription:soap-ankle-speech', 'generation:soap-ankle-speech',
                          'transcription:colonoscopy-speech', 'generation:colonoscopy-speech'])
        self.assertEqual([s['path'] for s in entry['sends']], ['transcription', 'transcription_generation'] * 2)
        self.assertEqual({s['pricing_key'] for s in entry['sends']}, {'transcription'})
        form = self.inputs['cases']['forms']['r1-11']['sha256']
        for send in entry['sends']:
            self.assertEqual(send['inputs'], {'form_sha256': form, 'audio_sha256': st.AUDIO_BY_ID[send['case']].sha256})
        self.assertEqual(entry['parameters'], {'model': 'nova-3-medical', 'smart_format': 'false', 'mip_opt_out': 'true'})
        self.assertEqual({a['label'] for a in entry['audio']}, {'synthesized speech, not a human microphone recording'})
        self.assertEqual([(a['id'], a['sha256']) for a in entry['audio']],
                         [('soap-ankle-speech', '3121862714193bb2f36c09a688dc7b3f293504163014680cae3c610dc21ea2d7'),
                          ('colonoscopy-speech', 'dfd22dfd4facec937dabd3fbaddd4670807fa5b018d86a4df9f425eb9f83e97c')])
        self.assertEqual(entry['flags']['QUILLMD_DEEPGRAM_MIP_OPT_OUT'], 'true')
        narrowed = st.standing_plan('transcription', {**self.inputs, 'transcription_audio': ('colonoscopy-speech',)})
        self.assertEqual([s.id for s in narrowed], ['transcription:colonoscopy-speech', 'generation:colonoscopy-speech'])
        for chosen in (('other-speech',), ('soap-ankle-speech', 'soap-ankle-speech'), ()):
            with self.subTest(chosen=chosen), self.assertRaisesRegex(pc.Refused, 'allowlisted recordings only'):
                st.standing_plan('transcription', {**self.inputs, 'transcription_audio': chosen})

    def test_the_declared_send_counts_and_pricing_keys_are_the_plans(self):
        d = parse(self)
        for stage in d.stages:
            self.assertEqual(stage.sends, self.definitions[stage.id]['count'], stage.id)
            for send in self.definitions[stage.id]['sends']:
                self.assertIn(send['pricing_key'], dict(d.pricing_versions))

    def test_the_stage_flags_are_the_historical_runners(self):
        stages = sq.stages_module()
        self.assertEqual({k: v for k, v in st.STAGE_FLAGS['model_check'].items() if k in sq.PLAIN_PROFILE_FLAGS},
                         sq.PLAIN_PROFILE_FLAGS)
        self.assertTrue(set(sq.PLAIN_PROFILE_FLAGS) <= set(st.STAGE_FLAGS['model_check']))
        for stage, theirs in (('mapping', 'mapping'), ('notes_comparison', 'ordinary_notes')):
            self.assertEqual({k: v for k, v in st.STAGE_FLAGS[stage].items() if k in stages.STAGE_FLAGS[theirs]},
                             stages.STAGE_FLAGS[theirs])
        self.assertEqual(st.expected_settings('notes_comparison')['V3_FIELD_RELATIONS'], False)
        self.assertEqual(stages.steps.PATH_FLAGS['field_relations']['V3_FIELD_RELATIONS'], True)


# ── the pricing command ──────────────────────────────────────────────────────────────────────────────────────────

class PricingCommandTests(unittest.TestCase):
    def pricing(self, model, rates, *extra):
        return subprocess.run([sys.executable, '-B', str(REBUILD / 'ops' / 'standing_qa.py'), 'pricing', '--model', model,
                               '--input', rates[0], '--output', rates[1], '--cached', rates[2], '--thinking', 'disabled',
                               '--effort', 'medium', *extra], capture_output=True, text=True, timeout=300, cwd=str(REBUILD),
                              env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(scratch(self)),
                                   'PYTHONDONTWRITEBYTECODE': '1'})

    def test_it_reproduces_the_historical_declarations_versions_for_sonnet_5(self):
        done = self.pricing('claude-sonnet-5', ('2', '10', '0.20'))
        self.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        historical = HISTORICAL_DECLARATION.read_text()
        version = re.search(r'^pricing_version model_check: (\S+)$', historical, re.M).group(1)
        self.assertEqual(report['pricing_versions']['model_check'], version)
        self.assertEqual(report['pricing_versions']['mapping'], version)
        self.assertEqual(report['pricing_versions']['ordinary_notes'], version)
        amendment = (REPOSITORY / 'docs' / 'foundation' / 'mutations' /
                     '20260929-quillmd-v1-sonnet5-relations-contract-amendment.md').read_text()
        amended = re.search(r'^amended_pricing_version: (\S+)$', amendment, re.M).group(1)
        self.assertEqual(report['pricing_versions']['ordinary_notes_field_relations'], amended)
        self.assertEqual(report['request_profiles']['mapping_request']['max_output_tokens'], 20000)

    def test_the_transcription_version_is_computed_under_the_declared_rate_and_no_other(self):
        historical = self.pricing('claude-sonnet-5', ('2', '10', '0.20'), '--deepgram-rate-per-minute', '0.0043')
        self.assertEqual(historical.returncode, 0, historical.stderr)
        same = json.loads(historical.stdout)
        # (positive control: at the historical rate the transcription settings price exactly as the notes stage —
        # mip_opt_out and smart formatting are not part of the price)
        self.assertEqual(same['pricing_versions']['transcription'], same['pricing_versions']['ordinary_notes'])
        # (and with field relations on, the voice-notes version is the notes stage's relations version at that rate)
        self.assertEqual(same['pricing_versions']['voice_notes_field_relations'],
                         same['pricing_versions']['ordinary_notes_field_relations'])
        declared = self.pricing('claude-sonnet-5', ('2', '10', '0.20'), '--deepgram-rate-per-minute', '0.0077')
        self.assertEqual(declared.returncode, 0, declared.stderr)
        other = json.loads(declared.stdout)
        for key in st.VOICE_PRICING_KEYS:                                 # (both voice keys move with the rate)
            self.assertNotEqual(other['pricing_versions'][key], same['pricing_versions'][key])
        self.assertEqual({k: v for k, v in other['pricing_versions'].items() if k not in st.VOICE_PRICING_KEYS},
                         {k: v for k, v in same['pricing_versions'].items() if k not in st.VOICE_PRICING_KEYS})
        self.assertIn('pricing_version transcription: ' + other['pricing_versions']['transcription'],
                      other['declaration_lines'])
        self.assertEqual((other['transcription']['rate_per_minute'], other['transcription']['declaration_line']),
                         ('0.0077', 'transcription_rate_per_minute: 0.0077'))
        for entry in st.TRANSCRIPTION_AUDIO:
            preview = other['transcription']['recordings'][entry.id]
            if 'unpriced' in preview:
                self.assertFalse(os.path.exists(entry.path), preview)          # (only a recording not on this host)
                continue
            self.assertEqual(Decimal(preview['maximum_cost']),
                             st.transcription_maximum(Decimal(preview['measured_seconds']), '0.0077'))
            self.assertTrue(preview['within_standard'])
        without = json.loads(self.pricing('claude-sonnet-5', ('2', '10', '0.20')).stdout)
        self.assertNotIn('transcription', without['pricing_versions'])
        for rate in ('0', '-0.0077', 'abc', '0.00000000001'):
            with self.subTest(rate=rate):
                refused = self.pricing('claude-sonnet-5', ('2', '10', '0.20'), f'--deepgram-rate-per-minute={rate}')
                self.assertEqual(refused.returncode, 2, refused.stdout)
                self.assertIn('positive USD rate', refused.stderr)

    def test_it_refuses_a_model_the_application_has_no_profile_for(self):
        done = self.pricing('claude-sonnet-5-5', ('3', '15', '0.30'))
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn('no valid request profile for claude-sonnet-5-5', done.stderr)
        self.assertEqual(done.stdout, '')



# ── the transcription stage (T4b) ────────────────────────────────────────────────────────────────────────────────

class TranscriptionDeclarationTests(Base):
    """The declaration's transcription section: every term stated once and fixed (deepgram, nova-3-medical, a positive
    per-minute rate, mip_opt_out true, smart formatting true or false, a credential file of its own), recordings only from the
    runner's allowlist with their pinned sha256, two sends per recording; no transcription line without the stage and no
    stage without its section."""

    def test_every_transcription_term_is_required_and_fixed(self):
        cases = [
            ('transcription_provider: deepgram', 'transcription_provider: openai', 'provider is deepgram'),
            ('transcription_model: nova-3-medical', 'transcription_model: nova-2', 'nova-3-medical'),
            ('transcription_rate_per_minute: 0.0077', 'transcription_rate_per_minute: 0', 'positive USD rate'),
            ('transcription_rate_per_minute: 0.0077', 'transcription_rate_per_minute: 0.0000', 'positive USD rate'),
            ('transcription_rate_per_minute: 0.0077', 'transcription_rate_per_minute: -0.0077', 'positive USD rate'),
            ('transcription_rate_per_minute: 0.0077', 'transcription_rate_per_minute: 0.00000000001', 'positive USD rate'),
            ('transcription_rate_per_minute: 0.0077', 'transcription_rate_per_minute: 7.7e-3', 'positive USD rate'),
            ('transcription_mip_opt_out: true', 'transcription_mip_opt_out: false', 'mip_opt_out is `true`'),
            ('transcription_smart_format: false', 'transcription_smart_format: yes', 'smart_format is `true` or `false`'),
            ('transcription_smart_format: false', 'transcription_smart_format: True', 'smart_format is `true` or `false`'),
            ('transcription_model: nova-3-medical\n', '', 'transcription_model:` exactly once'),
            ('transcription_model: nova-3-medical\n', 'transcription_model: nova-3-medical\n'
                                                     '- transcription_model: nova-3-medical\n',
             'transcription_model:` exactly once'),
            ('transcription_smart_format: false\n', 'transcription_smart_format: false\ntranscription_language: en\n',
             'does not know: transcription_language'),
            ('transcription_credential_file: /nonexistent/standing-qa-test-root/credential/deepgram-api-key',
             'transcription_credential_file: /nonexistent/standing-qa-test-root/credential/anthropic-api-key',
             'never the Anthropic credential file'),
            ('transcription_credential_file: /nonexistent/standing-qa-test-root/credential/deepgram-api-key',
             'transcription_credential_file: /nonexistent/standing-qa-test-root/.env/deepgram-api-key',
             'environment file'),
            ('pricing_version transcription: configured-v1:' + 'e' * 64 + '\n', '',
             'no declared pricing version for transcription')]
        for old, new, why in cases:
            with self.subTest(new=new[:70]), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))

    def test_declared_smart_formatting_is_the_one_value_threaded_to_the_request(self):
        """Standing attempts 33-36: an unformatted transcript is one unpunctuated run-on unit and every answer was held.
        A declaration may state smart formatting `true` (the product's per-deployment setting); it is then the ONE value
        the request carries, the process is configured with, and the configuration check demands — and `false` stays."""
        on = parse(self, edited('transcription_smart_format: false', 'transcription_smart_format: true'))
        off = parse(self, edited('transcription_smart_format: false', 'transcription_smart_format: false'))
        self.assertEqual(on.transcription.parameters(), {'model': 'nova-3-medical', 'smart_format': 'true',
                                                         'mip_opt_out': 'true'})
        self.assertEqual(off.transcription.parameters()['smart_format'], 'false')
        self.assertEqual(st.stage_flags('transcription', on)['QUILLMD_DEEPGRAM_SMART_FORMAT'], 'true')
        self.assertEqual(st.stage_flags('transcription', off)['QUILLMD_DEEPGRAM_SMART_FORMAT'], 'false')
        self.assertEqual(st.expected_settings('transcription', on)['QUILLMD_DEEPGRAM_SMART_FORMAT'], 'true')
        self.assertEqual(st.expected_settings('transcription', off)['QUILLMD_DEEPGRAM_SMART_FORMAT'], 'false')
        self.assertEqual(st.expected_settings('transcription')['QUILLMD_DEEPGRAM_SMART_FORMAT'], 'false')
        self.assertEqual(st.STAGE_FLAGS['transcription']['QUILLMD_DEEPGRAM_SMART_FORMAT'], 'false')   # (the default)

    def test_a_declared_notes_contract_prices_and_names_the_transcript_generation(self):
        """Campaign 2's transcripts were generated on the plain request although the candidate's claude-sonnet-5-5
        default is field relations. A declaration may state `transcription_notes_contract: field_relations`; absent, it
        is `default`, what campaigns 1 and 2 ran."""
        plain = parse(self)
        self.assertEqual(plain.transcription.notes_contract, 'default')
        price = ('pricing_version transcription: configured-v1:' + 'e' * 64 + '\n')
        with_price = edited(price, price + 'pricing_version voice_notes_field_relations: configured-v1:' + '9' * 64 + '\n')
        contract = ('transcription_smart_format: false\n',
                    'transcription_smart_format: false\ntranscription_notes_contract: field_relations\n')
        relations = parse(self, edited(*contract, text=with_price))
        with self.assertRaisesRegex(pc.Refused, 'no declared pricing version for voice_notes_field_relations'):
            parse(self, edited(*contract))
        self.assertEqual(relations.transcription.notes_contract, 'field_relations')
        self.assertEqual(relations.transcription.record()['notes_contract'], 'field_relations')
        for declaration, key in ((plain, 'transcription'), (relations, 'voice_notes_field_relations')):
            sends = st.standing_plan('transcription', st.stage_inputs('transcription', declaration))
            self.assertEqual([s.pricing_key for s in sends if s.path == 'transcription_generation'], [key, key])
            self.assertEqual({s.pricing_key for s in sends if s.path == 'transcription'}, {'transcription'})
        for old, new, why in [
                ('transcription_smart_format: false\n',
                 'transcription_smart_format: false\ntranscription_notes_contract: relations\n', '`default` or `field_relations`'),
                ('transcription_smart_format: false\n',
                 'transcription_smart_format: false\ntranscription_notes_contract: default\n'
                 'transcription_notes_contract: field_relations\n', 'at most once'),
                ('transcription_smart_format: false\n',
                 'transcription_smart_format: false\n- transcription_notes_contract: field_relations\n', 'transcription_notes_contract')]:
            with self.subTest(new=new[-60:]), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))

    def test_only_allowlisted_recordings_with_their_pinned_sha256_are_named(self):
        soap = 'transcription_input: soap-ankle-speech 3121862714193bb2f36c09a688dc7b3f293504163014680cae3c610dc21ea2d7'
        colon = 'transcription_input: colonoscopy-speech dfd22dfd4facec937dabd3fbaddd4670807fa5b018d86a4df9f425eb9f83e97c'
        cases = [(soap, 'transcription_input: human-dictation ' + '1' * 64, 'not on the runner\'s synthetic-audio'),
                 (soap, 'transcription_input: soap-ankle-speech ' + '1' * 64, 'not on the runner\'s synthetic-audio'),
                 (soap, colon.replace('colonoscopy-speech', 'soap-ankle-speech'), 'not on the runner\'s synthetic-audio'),
                 (colon, soap, 'names a recording twice'),
                 (soap + '\n', '', 'two sends per recording'),
                 (soap, '* ' + soap, 'its own line'),
                 (soap + '\n' + colon + '\n', '', 'its own line')]
        for old, new, why in cases:
            with self.subTest(new=new[:70]), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))
        narrowed = edited(soap + '\n', '', edited('stage: transcription sends 4', 'stage: transcription sends 2'))
        d = parse(self, narrowed)
        self.assertEqual(d.transcription.inputs, ('colonoscopy-speech',))
        reordered = edited(soap + '\n' + colon, colon + '\n' + soap)
        self.assertEqual(parse(self, reordered).transcription.inputs, ('soap-ankle-speech', 'colonoscopy-speech'))

    def test_a_transcription_section_needs_its_stage_and_the_stage_its_section(self):
        with self.assertRaisesRegex(pc.Refused, 'declares no transcription stage'):
            parse(self, edited('stage: transcription sends 4 requires model_check_passed\n', ''))
        text = fixture_text()
        start, end = text.index('## Transcription, fixed before any send'), text.index('## Bounds')
        without = (text[:start] + text[end:]).replace('stage: transcription sends 4 requires model_check_passed\n', '')
        without = re.sub(r'^transcription_(credential_file|input): .*\n', '', without, flags=re.M)
        d = parse(self, without)
        self.assertIsNone(d.transcription)
        self.assertNotIn('transcription', [s.id for s in d.stages])
        stage_back = without.replace('stage: notes_comparison sends 28 requires model_check_passed\n',
                                     'stage: notes_comparison sends 28 requires model_check_passed\n'
                                     'stage: transcription sends 4 requires model_check_passed\n')
        with self.assertRaisesRegex(pc.Refused, 'no declared pricing version for transcription'):
            parse(self, stage_back)
        relations = 'pricing_version ordinary_notes_field_relations: configured-v1:' + 'd' * 64 + '\n'
        with self.assertRaisesRegex(pc.Refused, 'transcription_provider:` exactly once'):
            parse(self, stage_back.replace(relations, relations + 'pricing_version transcription: configured-v1:'
                                                                  + 'e' * 64 + '\n'))
        with self.assertRaisesRegex(pc.Refused, 'declares no transcription stage'):
            st.load_transcription_credential(d, anthropic_key=SYNTHETIC_KEY)
        with self.assertRaisesRegex(pc.Refused, 'declares no transcription stage'):
            st.stage_inputs('transcription', d)


class TranscriptionCredentialTests(Base):
    """The Deepgram key is read from the declared file only, by provider_campaign.load_credential's rules — every one
    checked before a byte is read — and each bad condition refuses."""

    def setUp(self):
        self.folder = scratch(self) / 'credential'
        self.folder.mkdir(mode=0o700)
        self.key = self.folder / 'deepgram-api-key'
        self.key.write_text(DEEPGRAM_KEY + '\n')
        os.chmod(self.key, 0o600)
        d = parse(self)
        self.d = dataclasses.replace(d, transcription=dataclasses.replace(d.transcription,
                                                                          credential_file=str(self.key)))

    def test_the_declared_file_with_the_right_shape_is_read(self):
        self.assertEqual(st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY), DEEPGRAM_KEY)

    def test_each_bad_condition_refuses(self):
        with self.assertRaisesRegex(pc.Refused, 'Only the declared transcription_credential_file'):
            st.load_transcription_credential(self.d, str(self.folder / 'other'), anthropic_key=SYNTHETIC_KEY)
        os.chmod(self.key, 0o644)
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*mode 0600'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)
        os.chmod(self.key, 0o600)
        with patch.object(os, 'getuid', lambda: os.geteuid() + 1), \
                self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*owned by the account'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)
        os.link(self.key, self.folder / 'second-name')
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*another name'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)
        os.unlink(self.folder / 'second-name')
        real = self.folder / 'real-key'
        self.key.rename(real)
        self.key.symlink_to(real)
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*symbolic link'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)
        os.unlink(self.key)
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*does not exist'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)
        linked = scratch(self) / 'linked-folder'
        linked.symlink_to(self.folder)                                     # (a link at a DIRECTORY component)
        real.rename(self.key)
        through = dataclasses.replace(self.d, transcription=dataclasses.replace(
            self.d.transcription, credential_file=str(linked / 'deepgram-api-key')))
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*symbolic link'):
            st.load_transcription_credential(through, anthropic_key=SYNTHETIC_KEY)
        self.key.write_text(DEEPGRAM_KEY + ' trailing\n')
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*one non-empty line'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)
        self.key.unlink()
        self.key.mkdir(mode=0o700)
        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential: .*not a regular file'):
            st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY)

    def test_a_file_holding_the_anthropic_key_is_refused(self):
        """L1:R1-F2: a Deepgram credential file of its OWN PATH (0600, one name, one line) that holds the Anthropic
        key's VALUE — a copy, the key inside a longer line, a part of it — or any Anthropic-shaped key is refused: its
        value would go to another provider. The refusal names neither key; the Anthropic key is given, never read here."""
        plain = 'plain-anthropic-standing-value-5555555555'
        other = '0123456789abcdef0123456789'                                  # (no run of the Anthropic key)
        cases = {'a copy of the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY),
                 'the Anthropic key inside a longer line': ('dg0' + SYNTHETIC_KEY + '0dg', SYNTHETIC_KEY),
                 'a part of the Anthropic key': (SYNTHETIC_KEY[10:50], SYNTHETIC_KEY),
                 'a short part of the Anthropic key': (SYNTHETIC_KEY[20:30], SYNTHETIC_KEY),
                 'a 20-character piece of the Anthropic key among other characters': (SYNTHETIC_KEY[13:33] + other[:20],
                                                                                      SYNTHETIC_KEY),
                 'another Anthropic-shaped key': ('sk-ant-api03-ANOTHER-SYNTHETIC-OFFLINE-KEY-55555555', SYNTHETIC_KEY),
                 'another Anthropic-shaped key in capitals': ('SK-ANT-API03-ANOTHER-SYNTHETIC-OFFLINE-KEY-55555555',
                                                              SYNTHETIC_KEY),
                 'an unshaped copy of the Anthropic key': (plain, plain),
                 'an unshaped Anthropic key inside a longer line': ('dg0' + plain + '0dg', plain),
                 'an unshaped copy in capitals': (plain.upper(), plain)}
        for held, _ in (cases['a part of the Anthropic key'], cases['a short part of the Anthropic key'],
                        cases['a 20-character piece of the Anthropic key among other characters'],
                        cases['an unshaped copy in capitals']):
            self.assertFalse(pc.KEY_SHAPE.search(held.encode()))                 # (refused by the run, not the shape)
        self.assertNotIn(cases['a 20-character piece of the Anthropic key among other characters'][0],
                         SYNTHETIC_KEY)                                          # (neither contains the other)
        for name, (held, anthropic) in cases.items():
            with self.subTest(case=name):
                self.key.write_text(held + '\n')
                with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own') as caught:
                    st.load_transcription_credential(self.d, anthropic_key=anthropic)
                self.assertNotIn(held, str(caught.exception))
                self.assertNotIn(anthropic, str(caught.exception))
        self.key.write_text(DEEPGRAM_KEY + '\n')                                # (positive control: its own key)
        self.assertEqual(st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY), DEEPGRAM_KEY)
        bound = SYNTHETIC_KEY[13:28] + other[:25]                  # (the rule's stated bound: a 15-character run passes)
        self.key.write_text(bound + '\n')
        self.assertEqual(st.load_transcription_credential(self.d, anthropic_key=SYNTHETIC_KEY), bound)
        with self.assertRaises(TypeError):                                     # (no read without the key to compare)
            st.load_transcription_credential(self.d)


class TranscriptionPreconditionsCredentialTests(Base):
    """L1:R1-F2 in the request process's transcription preconditions (standing_qa_transcription.preconditions), which
    check the credential FIRST — before the historical checks or any application import, so this runs offline: a
    declared Deepgram file of its own path holding the Anthropic key's value refuses, however the run was handed it."""

    def test_a_file_holding_the_anthropic_key_refuses_before_anything_else(self):
        tr = st.transcription_module()
        folder = scratch(self) / 'credential'
        folder.mkdir(mode=0o700)
        key = folder / 'deepgram-api-key'
        d = parse(self)
        campaign = self.campaign(dataclasses.replace(d, transcription=dataclasses.replace(d.transcription,
                                                                                          credential_file=str(key))))
        plain = 'plain-standing-credential-4444444444444444'
        cases = {'a copy of the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY),
                 'an unshaped copy': (plain, plain),
                 'an unshaped Anthropic key inside it': (plain, 'dg' + plain)}

        def historical(*args, **kwargs):
            raise pc.Refused('sentinel: past the Deepgram credential')
        with patch.object(sq, 'preconditions', historical):
            for name, (anthropic, held) in cases.items():
                with self.subTest(case=name):
                    key.write_text(held + '\n')
                    os.chmod(key, 0o600)
                    for given in (held, DEEPGRAM_KEY):              # (the file's value, or the campaign's own key)
                        with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own'):
                            tr.preconditions(campaign, secret=anthropic, transcription_secret=given, environ={})
            key.write_text(DEEPGRAM_KEY + '\n')                    # (positive control: its own key gets past it)
            with self.assertRaisesRegex(pc.Refused, 'sentinel: past the Deepgram credential'):
                tr.preconditions(campaign, secret=SYNTHETIC_KEY, transcription_secret=DEEPGRAM_KEY, environ={})


class TranscriptionGuardTests(unittest.TestCase):
    """The transport guard of a transcription send (standing_qa_transcription.install_transcription_guard, on the
    campaign's own guard): exactly ONE request — POST https://api.deepgram.com/v1/listen, exactly the declared
    parameters and key — recorded without its credential and with its exact body BEFORE it leaves, its response retained
    as received; anything else refused before the network; outside a transcription attempt, the campaign guard."""
    PARAMETERS = {'model': 'nova-3-medical', 'smart_format': 'false', 'mip_opt_out': 'true'}

    def setUp(self):
        import httpx
        self.tr = st.transcription_module()
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True, mode=0o700)
        self.seen = []

        def network(transport, request):
            self.seen.append({'url': str(request.url), 'authorization': request.headers.get('authorization'),
                              'body': request.content})
            return httpx.Response(200, headers={'dg-request-id': 'synthetic-dg-request', 'content-type':
                                                'application/json'},
                                  json={'metadata': {'request_id': 'synthetic-dg-request', 'duration': 43.5},
                                        'results': {'channels': [{'alternatives': [{'transcript': 'synthetic words'}]}]}})
        pc.install_transport_guard()
        self.addCleanup(pc.uninstall_transport_guard)
        self.tr.install_transcription_guard(network=network)
        self.addCleanup(self.tr.uninstall_transcription_guard)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)
        self.addCleanup(pc.SENT.clear)
        pc.SENT.clear()
        self.body = b'RIFF' + bytes(4096)

    def attempt(self, number=1, transcription=True, **changes):
        pc.CURRENT_ATTEMPT.clear()
        pc.CURRENT_ATTEMPT.update(number=number, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        if transcription:
            pc.CURRENT_ATTEMPT['transcription'] = {'parameters': dict(self.PARAMETERS), 'secret': DEEPGRAM_KEY, **changes}

    def post(self, url=st.DEEPGRAM_URL, params=None, headers=None, content=None, method='POST'):
        import httpx
        headers = {'Authorization': f'Token {DEEPGRAM_KEY}', 'Content-Type': 'application/octet-stream'} \
            if headers is None else headers
        with httpx.Client() as client:
            return client.request(method, url, params=self.PARAMETERS if params is None else params, headers=headers,
                                  content=self.body if content is None else content, timeout=5)

    def test_the_declared_request_is_recorded_before_it_leaves_and_its_response_retained(self):
        self.attempt()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(self.seen[0]['authorization'], f'Token {DEEPGRAM_KEY}')     # (the request carried the key)
        request = json.loads((self.evidence / 'request.json').read_text())
        self.assertEqual((request['method'], request['params']), ('POST', self.PARAMETERS))
        self.assertEqual(request['url'].split('?')[0], st.DEEPGRAM_URL)
        self.assertNotIn('authorization', request['headers'])
        self.assertEqual(request['removed_headers'], ['authorization'])
        self.assertEqual((request['body_sha256'], request['body_bytes']),
                         (hashlib.sha256(self.body).hexdigest(), len(self.body)))
        self.assertEqual((self.evidence / 'request.body').read_bytes(), self.body)
        received = pc.received_response(self.evidence)
        self.assertEqual((received['status_code'], received['body_json']['metadata']['request_id']),
                         (200, 'synthetic-dg-request'))
        self.assertEqual(pc.leaked(self.root, DEEPGRAM_KEY), [])                     # (no key anywhere retained)
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])
        with self.assertRaisesRegex(pc.Refused, 'second send'):
            self.post()
        self.assertEqual(len(self.seen), 1)

    def test_anything_but_the_declared_request_is_refused_before_it_leaves(self):
        cases = {'smart formatting on': dict(params={**self.PARAMETERS, 'smart_format': 'true'}),
                 'no opt-out': dict(params={'model': 'nova-3-medical', 'smart_format': 'false'}),
                 'opt-out false': dict(params={**self.PARAMETERS, 'mip_opt_out': 'false'}),
                 'another model': dict(params={**self.PARAMETERS, 'model': 'nova-3'}),
                 'an extra parameter': dict(params={**self.PARAMETERS, 'callback': 'https://example.invalid/'}),
                 'a repeated parameter': dict(params=list(self.PARAMETERS.items()) + [('model', 'nova-3-medical')]),
                 'another host': dict(url='https://api.deepgram.com.example.invalid/v1/listen'),
                 'another path': dict(url='https://api.deepgram.com/v1/listen/extra'),
                 'plain http': dict(url='http://api.deepgram.com/v1/listen'),
                 'another port': dict(url='https://api.deepgram.com:8443/v1/listen'),
                 'the Messages URL': dict(url='https://api.anthropic.com/v1/messages'),
                 'GET': dict(method='GET'),
                 'another key': dict(headers={'Authorization': 'Token another-key-0000000000000000000000000000',
                                              'Content-Type': 'application/octet-stream'}),
                 'no key': dict(headers={'Content-Type': 'application/octet-stream'}),
                 'a second credential header': dict(headers={'Authorization': f'Token {DEEPGRAM_KEY}',
                                                             'x-api-key': SYNTHETIC_KEY,
                                                             'Content-Type': 'application/octet-stream'}),
                 'another content type': dict(headers={'Authorization': f'Token {DEEPGRAM_KEY}',
                                                       'Content-Type': 'application/json'}),
                 'an empty body': dict(content=b'')}
        for name, change in cases.items():
            with self.subTest(case=name):
                pc.SENT.clear()
                self.attempt()
                with self.assertRaises(pc.Refused):
                    self.post(**change)
                self.assertEqual(self.seen, [])
                self.assertFalse((self.evidence / 'request.json').exists())

    def test_outside_a_transcription_attempt_the_campaign_guard_refuses_deepgram(self):
        self.attempt(transcription=False)
        with self.assertRaisesRegex(pc.Refused, 'refused at the transport'):
            self.post()
        pc.CURRENT_ATTEMPT.clear()
        with self.assertRaisesRegex(pc.Refused, 'outside an attempt'):
            self.post()
        self.assertEqual(self.seen, [])

    def test_a_declared_key_that_is_not_its_own_is_refused_before_it_leaves(self):
        """L1:R1-F2 at the last door: the request carries `Authorization: Token <the declared key>` exactly, but the
        declared key IS, holds or is part of the campaign's Anthropic key, or carries an Anthropic key's shape — or the
        attempt names no Anthropic key to tell them apart. Refused before the network and before any record; the
        refusal kept with the attempt names neither key."""
        plain = 'plain-standing-credential-8888888888888888'
        cases = {'the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY),
                 'the Anthropic key inside it': (SYNTHETIC_KEY, 'dg' + SYNTHETIC_KEY),
                 'a part of the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY[10:50]),
                 'another Anthropic-shaped key': (SYNTHETIC_KEY, 'sk-ant-api03-ANOTHER-SYNTHETIC-KEY-888888888888'),
                 'an unshaped copy': (plain, plain),
                 'an unshaped Anthropic key inside it': (plain, 'dg' + plain),
                 'an unshaped copy in capitals': (plain, plain.upper()),
                 'a 20-character piece of the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY[13:33] + '0123456789abcdef0123'),
                 'no Anthropic key named': (None, DEEPGRAM_KEY)}
        for index, (name, (campaign_key, declared)) in enumerate(cases.items(), start=2):
            with self.subTest(case=name):
                pc.SENT.clear()
                self.seen.clear()
                self.evidence = pc.private_directory(self.root / 'evidence' / f'{index:03d}')
                self.attempt(secret=declared)
                if campaign_key is None:
                    pc.CURRENT_ATTEMPT.pop('secret')
                else:
                    pc.CURRENT_ATTEMPT['secret'] = campaign_key
                with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own|is not given'):
                    self.post(headers={'Authorization': f'Token {declared}', 'Content-Type': 'application/octet-stream'})
                self.assertEqual(self.seen, [])
                self.assertFalse((self.evidence / 'request.json').exists())
                for value in (declared, campaign_key or SYNTHETIC_KEY):
                    self.assertEqual(pc.leaked(self.root, value), [])

    def test_the_anthropic_key_anywhere_in_the_request_is_refused_before_it_leaves(self):
        """L1:R1-F2's class at the last door: with the right Deepgram key, a request that would carry the Anthropic key
        (or an Anthropic-shaped value) in any other header or in its body is refused before the network."""
        another = 'sk-ant-api03-ANOTHER-SYNTHETIC-KEY-999999999999'
        plain = 'plain-standing-credential-3333333333333333'        # (an unshaped Anthropic key: its VALUE is matched)
        token = {'Authorization': f'Token {DEEPGRAM_KEY}', 'Content-Type': 'application/octet-stream'}
        cases = {'the Anthropic key in another header': (SYNTHETIC_KEY, dict(headers={**token, 'X-Trace': SYNTHETIC_KEY})),
                 'an Anthropic-shaped header': (SYNTHETIC_KEY, dict(headers={**token, 'X-Trace': another})),
                 'an unshaped Anthropic key in another header': (plain, dict(headers={**token, 'X-Trace': 'a' + plain})),
                 'the Anthropic key in the body': (SYNTHETIC_KEY, dict(content=self.body + SYNTHETIC_KEY.encode())),
                 'an Anthropic-shaped body': (SYNTHETIC_KEY, dict(content=b'RIFF' + another.encode() + bytes(64))),
                 'an unshaped Anthropic key in the body': (plain, dict(content=self.body + plain.encode()))}
        for index, (name, (campaign_key, change)) in enumerate(cases.items(), start=2):
            with self.subTest(case=name):
                pc.SENT.clear()
                self.seen.clear()
                self.evidence = pc.private_directory(self.root / 'evidence' / f'{index:03d}')
                self.attempt()
                pc.CURRENT_ATTEMPT['secret'] = campaign_key
                with self.assertRaisesRegex(pc.Refused, 'would carry'):
                    self.post(**change)
                self.assertEqual(self.seen, [])
                self.assertFalse((self.evidence / 'request.json').exists())
                self.assertEqual(pc.leaked(self.root, campaign_key), [])

    def test_the_guard_sits_on_the_campaign_guard_and_comes_off_cleanly(self):
        import httpx
        self.tr.uninstall_transcription_guard()
        self.assertTrue(getattr(httpx.HTTPTransport.handle_request, '_campaign_guard', False))
        self.assertFalse(getattr(httpx.HTTPTransport.handle_request, '_transcription_guard', False))
        pc.uninstall_transport_guard()
        with self.assertRaisesRegex(pc.Refused, 'campaign\'s transport guard'):
            self.tr.install_transcription_guard()


def transcription_inputs(audio=('soap-ankle-speech', 'colonoscopy-speech')):
    return {**sq.stages_module().frozen_inputs(), 'transcription_audio': tuple(audio)}


class TranscriptionLedgerTests(Base):
    """At the last door before a send (StandingLedger.write_attempt) and before a run opens (begin_run): only the
    allowlisted recording of THIS send, allowed by its run and never restricted, is ever attempted; a send is
    attempted once; and read_audio gives only the pinned bytes."""

    def open_run(self, campaign, audio=('soap-ankle-speech',)):
        inputs = transcription_inputs(audio)
        sends = st.standing_plan('transcription', inputs)
        return st.begin_run(campaign, 'transcription', sends, inputs, len(sends), {'runner_commit': RUNNER_COMMIT}), \
            sends, inputs

    def transcription_attempt(self, campaign, planned, inputs, **changes):
        d = campaign.declaration
        record = {'number': len(campaign.ledger.rows()) + 1, 'campaign': d.campaign, 'authority_id': d.authority_id,
                  'stage': 'transcription', 'send': planned.record(), 'maximum_cost': '0.010000',
                  'rates': d.rates.as_dict(), **{k: v for k, v in st.send_inputs(planned, inputs).items()},
                  'limits': campaign.limits().record(), 'terms': campaign.pinned_terms().record(),
                  'runner_commit': RUNNER_COMMIT, 'started_at': pc.now()}
        record.update(changes)
        return record

    def test_an_edited_smart_formatting_admits_nothing_after_a_transcription_attempt(self):
        """Refutation r1 B-F1: smart formatting is in no pricing version, so the pinned terms did not hold it. A
        transcription attempt's recorded parameters now pin it for the rest of the campaign, both ways."""
        campaign = self.campaign()
        self.pass_model_check(campaign)
        _, sends, inputs = self.open_run(campaign)
        sent = {'model': 'nova-3-medical', 'smart_format': 'false', 'mip_opt_out': 'true'}
        campaign.ledger.write_attempt(self.transcription_attempt(campaign, sends[0], inputs,
                                                                 transcription={'parameters': sent}))
        self.completed(campaign, len(campaign.ledger.rows()))
        flipped = dataclasses.replace(campaign.declaration, transcription=dataclasses.replace(
            campaign.declaration.transcription, smart_format='true'))
        with self.assertRaisesRegex(pc.Refused, 'other Deepgram parameters'):
            st.StandingCampaign(flipped, campaign.root).stage_open('transcription')
        campaign.stage_open('transcription')                                   # (the declared value still admits)

    def test_an_edited_notes_contract_admits_nothing_after_a_transcript_generation(self):
        """The notes contract of a transcript's generation is pinned per campaign, like the Deepgram parameters."""
        campaign = self.campaign()
        self.pass_model_check(campaign)
        _, sends, inputs = self.open_run(campaign)
        generation = [s for s in sends if s.path == 'transcription_generation'][0]
        campaign.ledger.write_attempt(self.transcription_attempt(campaign, generation, inputs))
        self.completed(campaign, len(campaign.ledger.rows()))
        flipped = dataclasses.replace(campaign.declaration, transcription=dataclasses.replace(
            campaign.declaration.transcription, notes_contract='field_relations'))
        with self.assertRaisesRegex(pc.Refused, 'another notes contract'):
            st.StandingCampaign(flipped, campaign.root).stage_open('transcription')
        campaign.stage_open('transcription')

    def test_an_allowlisted_recording_is_admitted_and_recorded(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        run, sends, inputs = self.open_run(campaign)
        self.assertEqual(run['audio'], [st.AUDIO_BY_ID['soap-ankle-speech'].record()])
        self.assertIn(st.AUDIO_BY_ID['soap-ankle-speech'].sha256, run['allowed_inputs'])
        self.assertEqual(campaign.admit('transcription', '0.01', runner_commit=RUNNER_COMMIT), Decimal('0.011'))
        written = self.transcription_attempt(campaign, sends[0], inputs)
        campaign.ledger.write_attempt(written)
        attempt, _ = campaign.ledger.rows()[-1]
        self.assertEqual((attempt['send_key'], attempt['audio_sha256'], attempt['run_id']),
                         ('transcription:transcription:soap-ankle-speech', st.AUDIO_BY_ID['soap-ankle-speech'].sha256,
                          run['run_id']))
        self.assertIsNone(attempt['monetary_ceiling'])

    def test_a_recording_that_is_not_this_sends_allowlisted_speech_is_refused_at_the_last_door(self):
        campaign = self.campaign()
        run, sends, inputs = self.open_run(campaign)
        colon = st.AUDIO_BY_ID['colonoscopy-speech'].sha256
        cases = [{'audio_sha256': 'a' * 64}, {'audio_sha256': colon}, {'audio_sha256': None},
                 {'send': {**sends[0].record(), 'case': 'human-dictation'}},
                 {'send': {**sends[0].record(), 'path': 'default'}}]
        for change in cases:
            with self.subTest(change=str(change)[:80]), self.assertRaisesRegex(pc.Refused, 'allowlisted synthetic speech'):
                campaign.ledger.write_attempt(self.transcription_attempt(campaign, sends[0], inputs, **change))
        missing = self.transcription_attempt(campaign, sends[0], inputs)
        del missing['audio_sha256']
        with self.assertRaisesRegex(pc.Refused, 'allowlisted synthetic speech'):
            campaign.ledger.write_attempt(missing)
        notes = self.notes_attempt(campaign, st.standing_plan('notes_comparison', inputs)[0], inputs,
                                   {'audio_sha256': colon})
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage|allowlisted synthetic speech'):
            campaign.ledger.write_attempt(notes)
        self.assertEqual(campaign.ledger.rows(), [])

    def test_a_restricted_recording_never_opens_a_run(self):
        campaign = self.campaign(restricted=(st.AUDIO_BY_ID['soap-ankle-speech'].sha256,))
        with self.assertRaisesRegex(pc.Refused, 'no provider upload'):
            self.open_run(campaign)
        self.assertEqual(campaign.runs.listing(), [])
        other = self.campaign(restricted=(st.AUDIO_BY_ID['soap-ankle-speech'].sha256,))
        run, sends, inputs = self.open_run(other, audio=('colonoscopy-speech',))
        forged = self.transcription_attempt(other, sends[0], inputs)
        with patch.dict(st.AUDIO_BY_ID, {'colonoscopy-speech': dataclasses.replace(
                st.AUDIO_BY_ID['colonoscopy-speech'], sha256=st.AUDIO_BY_ID['soap-ankle-speech'].sha256)}):
            forged['audio_sha256'] = st.AUDIO_BY_ID['soap-ankle-speech'].sha256
            with self.assertRaises(pc.Refused):
                other.ledger.write_attempt(forged)

    def test_a_send_is_never_attempted_twice(self):
        campaign = self.campaign()
        run, sends, inputs = self.open_run(campaign)
        campaign.ledger.write_attempt(self.transcription_attempt(campaign, sends[0], inputs))
        campaign.ledger.write_outcome(1, {'class': 'completed', 'provider_cost': '0.0055'})
        with self.assertRaisesRegex(pc.Refused, 'already has an attempt'):
            campaign.ledger.write_attempt(self.transcription_attempt(campaign, sends[0], inputs))
        self.assertEqual([s.id for s in st.remaining_sends(campaign, 'transcription', sends)],
                         ['generation:soap-ankle-speech'])
        totals = campaign.totals('transcription')                         # (costed by its duration, never tokens)
        self.assertEqual((totals['exposure'], totals['unknown']), (Decimal('0.0055'), 0))

    def test_read_audio_gives_only_the_pinned_bytes(self):
        folder = scratch(self)
        path = folder / 'synthetic.wav'
        data = b'RIFF' + bytes(range(256)) * 8
        path.write_bytes(data)
        entry = st.SyntheticAudio('synthetic-test-speech', str(path), hashlib.sha256(data).hexdigest(), len(data),
                                  'test bytes')
        with self.assertRaisesRegex(pc.Refused, 'Only an entry'):
            st.read_audio(entry)                                           # (not on the allowlist)
        with patch.dict(st.AUDIO_BY_ID, {entry.id: entry}):
            self.assertEqual(st.read_audio(entry), data)
            path.write_bytes(data[:-1] + b'\x01')
            with self.assertRaisesRegex(pc.Refused, 'is not the allowlisted synthetic speech'):
                st.read_audio(entry)
            path.unlink()
            (folder / 'elsewhere.wav').write_bytes(data)
            path.symlink_to(folder / 'elsewhere.wav')
            with self.assertRaisesRegex(pc.Refused, 'cannot be opened'):
                st.read_audio(entry)
        with self.assertRaisesRegex(pc.Refused, 'not a recording on the runner'):
            st.audio_entry('human-dictation')

    def test_the_allowlisted_recordings_on_this_host_are_the_pinned_bytes(self):
        for entry in st.TRANSCRIPTION_AUDIO:
            with self.subTest(entry=entry.id):
                if not os.path.exists(entry.path):
                    self.skipTest(f'{entry.path} is not on this host')
                self.assertEqual(hashlib.sha256(st.read_audio(entry)).hexdigest(), entry.sha256)


class StopRaceTests(Base):
    """L1:R1-F4 / L2:R2-F2: the operator's Stop file appearing AFTER run_stage's loop check, inside a send before its
    attempt is written — at its preview admission, its admission (which the real worker turns into a StageStop after
    cancelling the job) or its attempt record — HALTS the run (exit 4, the stage open, a job it had queued cancelled),
    exactly like the loop's own check; the next run resumes. Attribution is by the refusal's TYPE: any other refusal,
    even while a Stop file exists, and a campaign stop still fail the stage."""
    setUp = StageRunTests.setUp
    prepared = StageRunTests.prepared
    run_mapping = StageRunTests.run_mapping
    attempted = StageRunTests.attempted
    SEND = 'mapping:f2-leave-checkboxes'

    def race(self, campaign, hook, extra=None):
        def appear(send):
            if send.id == self.SEND:
                campaign.stop_file().write_text('')
                if extra is not None:
                    extra(send)
        FakeWorker.hooks = {hook: appear}
        try:
            return self.run_mapping(campaign)
        finally:
            FakeWorker.hooks = {}

    def assert_halted_then_resumes(self, campaign, result):
        plan = [s.id for s in st.standing_plan('mapping', sq.stages_module().frozen_inputs())]
        at = plan.index(self.SEND)
        self.assertEqual((result['decision'], result['verdict'], result['reasons']), ('halted', 'HALTED', []))
        self.assertEqual(st.EXIT[result['verdict']], 4)
        self.assertEqual(result['summary']['not_sent'], plan[at:])
        self.assertIn('before its attempt was written', result['summary']['halted'])
        self.assertEqual(result['summary']['halt_jobs'], {'cancelled': []})
        self.assertEqual(len(self.cancellations), 2)                        # (the run's start, then the halt)
        self.assertEqual(self.attempted(campaign), plan[:at])
        self.assertEqual(campaign.ledger.stage_state('mapping')['state'], 'open')          # (not failed)
        self.assertEqual(campaign.runs.listing()[-1][1]['closed_as'], 'halted')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            self.run_mapping(campaign)                                       # (while it stands, nothing runs)
        campaign.stop_file().unlink()                                        # (the operator lifts the halt)
        resumed = self.run_mapping(campaign)
        self.assertEqual((resumed['decision'], resumed['verdict']), ('passed', 'PASS'), resumed['reasons'])
        self.assertEqual(sorted(self.attempted(campaign)), sorted(plan))

    def test_met_at_the_preview_admission_it_halts(self):
        campaign = self.prepared()
        self.assert_halted_then_resumes(campaign, self.race(campaign, 'start'))
        self.assertEqual(FakeWorker.refused_jobs, [])

    def test_met_at_the_admission_it_halts_and_the_queued_job_is_cancelled(self):
        campaign = self.prepared()
        result = self.race(campaign, 'pre_attempt')
        self.assertEqual(FakeWorker.refused_jobs, [self.SEND])               # (refuse_job's StageStop carried the halt)
        self.assert_halted_then_resumes(campaign, result)

    def test_met_at_the_attempt_record_it_halts_and_the_queued_job_is_cancelled(self):
        campaign = self.prepared()
        result = self.race(campaign, 'before_write')
        self.assertEqual(FakeWorker.refused_jobs, [])                        # (the worker's own cancel never ran ...)
        self.assertEqual(len(self.cancellations), 2)                         # (... so the halt cancelled what was queued)
        self.assert_halted_then_resumes(campaign, result)

    def test_any_other_refusal_still_fails_the_stage_even_with_a_stop_file(self):
        campaign = self.prepared()

        def other(send):
            raise pc.Refused('The area decisions were refused (500). The Stop file exists; nothing is sent.')
        result = self.race(campaign, 'pre_attempt', extra=other)
        self.assertEqual((result['decision'], result['verdict']), ('failed', 'FAIL'))
        self.assertEqual(campaign.ledger.stage_state('mapping')['state'], 'failed')
        self.assertNotIn('halt_jobs', result['summary'])

    def test_a_campaign_stop_inside_a_send_still_fails_the_stage(self):
        campaign = self.prepared()

        def stop(send):
            if send.id == self.SEND:
                campaign.ledger.write_stop({'reason': 'synthetic campaign stop'})
        FakeWorker.hooks = {'pre_attempt': stop}
        result = self.run_mapping(campaign)
        FakeWorker.hooks = {}
        self.assertEqual((result['decision'], result['verdict']), ('failed', 'FAIL'))
        self.assertIn('campaign is stopped', '; '.join(result['reasons']))

    def test_the_model_check_halts_too_and_any_other_refusal_still_refuses(self):
        campaign = self.campaign()
        folder = campaign.root / 'preflight' / '001'
        folder.mkdir(parents=True)
        (folder / 'result.json').write_text(json.dumps({'matches_declared': True, 'campaign': campaign.declaration.campaign,
                                                         'model_returned': campaign.declaration.model}))

        def appears(inside, **kwargs):
            inside.stop_file().write_text('')         # (after run_model_check's own checks, before the attempt record)
            inside.require_not_stopped()
        with patch.object(sq, 'run_model_check', appears):
            result = st.run_model_check(campaign, secret=SYNTHETIC_KEY, provenance={'runner_commit': RUNNER_COMMIT})
        self.assertEqual((result['verdict'], result['decision'], result['reasons']), ('HALTED', 'halted', []))
        self.assertEqual(st.EXIT[result['verdict']], 4)
        self.assertEqual(result['halt_jobs'], {'cancelled': []})
        self.assertEqual(campaign.runs.listing()[-1][1]['closed_as'], 'halted')
        self.assertEqual(campaign.ledger.stage_state('model_check')['state'], 'open')
        campaign.stop_file().unlink()

        def other(inside, **kwargs):
            raise pc.Refused('The page offers no Generate form.')
        with patch.object(sq, 'run_model_check', other), self.assertRaisesRegex(pc.Refused, 'no Generate form'):
            st.run_model_check(campaign, secret=SYNTHETIC_KEY, provenance={'runner_commit': RUNNER_COMMIT})
        self.assertEqual(campaign.runs.listing()[-1][1]['closed_as'], 'refused_before_attempt')
        self.assertEqual(len(self.cancellations), 1)                         # (only the halt cancelled anything)

    def test_the_halt_is_read_from_the_refusals_type_one_link_deep(self):
        stages = sq.stages_module()
        self.assertTrue(st.stopped_by_halt(st.StopFileHalt('x')))
        try:
            try:
                raise st.StopFileHalt('The Stop file exists')
            except pc.Refused:
                raise stages.StageStop('refused; the job was cancelled unsent')
        except stages.StageStop as stop:
            self.assertTrue(st.stopped_by_halt(stop))
        try:
            try:
                raise pc.Refused('The Stop file /x/STOP exists; nothing is sent.')       # (the words, not the type)
            except pc.Refused:
                raise stages.StageStop('refused')
        except stages.StageStop as stop:
            self.assertFalse(st.stopped_by_halt(stop))
        try:
            try:
                try:
                    raise st.StopFileHalt('The Stop file exists')
                except pc.Refused:
                    raise pc.Refused('something else went wrong while handling it')
            except pc.Refused:
                raise stages.StageStop('refused')
        except stages.StageStop as stop:
            self.assertFalse(st.stopped_by_halt(stop))                       # (two links: not this send's halt)
        self.assertFalse(st.stopped_by_halt(pc.Refused('The Stop file exists; nothing is sent.')))


class TranscriptionStageRunTests(Base):
    """The REAL run_stage for the transcription stage — its credential rule, plan, pairing, runs, admission, ledger,
    halts and decision — with the Django-bound helpers and the per-send worker stood in (FakeWorker)."""
    prepared = StageRunTests.prepared

    def setUp(self):
        StageRunTests.setUp(self)
        tr = st.transcription_module()
        for stand_in in (patch.object(tr, 'preconditions', lambda campaign, **k: {'stand_in': True}),
                         patch.object(tr, 'planned_maxima', lambda sends, d: {s.id: Decimal('0.01') for s in sends}),
                         patch.object(tr, 'TranscriptionRun', FakeWorker)):
            stand_in.start()
            self.addCleanup(stand_in.stop)

    def run_transcription(self, campaign, **kwargs):
        kwargs.setdefault('transcription_secret', DEEPGRAM_KEY)
        return st.run_stage(campaign, 'transcription', secret=SYNTHETIC_KEY, provenance={'runner_commit': RUNNER_COMMIT},
                            **kwargs)

    def attempted(self, campaign):
        return [a['send']['id'] for a, _ in campaign.ledger.rows() if a['stage'] == 'transcription']

    def test_each_recording_is_transcribed_then_generated_on_and_the_stage_passes(self):
        campaign = self.prepared()
        result = self.run_transcription(campaign)
        self.assertEqual((result['decision'], result['verdict']), ('passed', 'PASS'), result['reasons'])
        self.assertEqual(self.attempted(campaign), ['transcription:soap-ankle-speech', 'generation:soap-ankle-speech',
                                                    'transcription:colonoscopy-speech', 'generation:colonoscopy-speech'])
        opened = campaign.runs.listing()[-1][0]
        self.assertEqual([a['id'] for a in opened['audio']], ['soap-ankle-speech', 'colonoscopy-speech'])
        self.assertEqual({a['label'] for a in opened['audio']}, {st.AUDIO_LABEL})
        for attempt, _ in campaign.ledger.rows()[1:]:
            self.assertEqual(attempt['audio_sha256'], st.AUDIO_BY_ID[attempt['send']['case']].sha256)
        with self.assertRaisesRegex(pc.Refused, 'already passed'):
            self.run_transcription(campaign)                                 # (never twice)

    def test_the_deepgram_key_reaches_a_transcription_run_only(self):
        campaign = self.prepared()
        with self.assertRaisesRegex(pc.Refused, 'transcription run only'):
            self.run_transcription(campaign, transcription_secret=None)
        with self.assertRaisesRegex(pc.Refused, 'transcription run only'):
            st.run_stage(campaign, 'mapping', secret=SYNTHETIC_KEY, provenance={'runner_commit': RUNNER_COMMIT},
                         transcription_secret=DEEPGRAM_KEY)
        self.assertEqual(len(campaign.runs.listing()), 1)                    # (only the model check's run)

    def test_a_deepgram_key_that_is_the_anthropic_key_is_refused_before_a_run_opens(self):
        """L1:R1-F2 at run_stage, which holds both keys (its preconditions stood in here, so only its own check can
        refuse): a Deepgram key that is, holds or carries the shape of the Anthropic key opens no run, writes nothing
        and builds no worker; the campaign's own Deepgram key then passes (positive control)."""
        campaign = self.prepared()
        plain = 'plain-standing-credential-7777777777777777'
        cases = {'the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY),
                 'the Anthropic key inside it': (SYNTHETIC_KEY, 'dg' + SYNTHETIC_KEY),
                 'another Anthropic-shaped key': (SYNTHETIC_KEY, 'sk-ant-api03-ANOTHER-SYNTHETIC-KEY-77777777'),
                 'a 20-character piece of the Anthropic key': (SYNTHETIC_KEY, SYNTHETIC_KEY[13:33] + '0123456789abcdef0123'),
                 'an unshaped copy': (plain, plain)}
        built = []
        FakeWorker.hooks = {'start': lambda send: built.append(send.id)}
        try:
            for name, (secret, deepgram) in cases.items():
                with self.subTest(case=name):
                    with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own'):
                        st.run_stage(campaign, 'transcription', secret=secret,
                                     provenance={'runner_commit': RUNNER_COMMIT}, transcription_secret=deepgram)
        finally:
            FakeWorker.hooks = {}
        self.assertEqual((built, self.attempted(campaign), len(campaign.runs.listing())), ([], [], 1))
        result = self.run_transcription(campaign)
        self.assertEqual((result['decision'], result['verdict']), ('passed', 'PASS'), result['reasons'])

    def test_a_halt_between_a_transcription_and_its_generation_refuses_every_later_run(self):
        campaign = self.prepared()

        def in_flight(send):
            if send.id == 'transcription:soap-ankle-speech':
                campaign.stop_file().write_text('')
        FakeWorker.hooks = {'in_flight': in_flight}
        first = self.run_transcription(campaign)
        FakeWorker.hooks = {}
        campaign.stop_file().unlink()
        self.assertEqual((first['decision'], first['summary']['not_sent']),
                         ('halted', ['generation:soap-ankle-speech', 'transcription:colonoscopy-speech',
                                     'generation:colonoscopy-speech']))
        for _ in range(2):
            with self.assertRaises(pc.Refused) as caught:
                self.run_transcription(campaign)
            self.assertIn("generation:soap-ankle-speech needs its recording's transcription send in the same run, and "
                          'that send was already made; it is not sent', str(caught.exception))
            self.assertIn('Stage transcription cannot pass in this campaign', str(caught.exception))
        self.assertEqual(self.attempted(campaign), ['transcription:soap-ankle-speech'])
        self.assertNotEqual(campaign.ledger.stage_state('transcription')['state'], 'passed')

    def test_a_stop_file_met_before_a_transcription_attempt_halts_and_the_run_resumes(self):
        campaign = self.prepared()

        def appear(send):
            if send.id == 'transcription:colonoscopy-speech':
                campaign.stop_file().write_text('')
        FakeWorker.hooks = {'pre_attempt': appear}
        first = self.run_transcription(campaign)
        FakeWorker.hooks = {}
        self.assertEqual((first['decision'], first['verdict'], first['reasons']), ('halted', 'HALTED', []))
        self.assertEqual(campaign.ledger.stage_state('transcription')['state'], 'open')
        campaign.stop_file().unlink()
        resumed = self.run_transcription(campaign)
        self.assertEqual((resumed['decision'], resumed['verdict']), ('passed', 'PASS'), resumed['reasons'])

    def test_a_retained_copy_of_the_deepgram_key_stops_the_campaign_at_the_runs_close(self):
        campaign = self.prepared()

        def in_flight(send):
            if send.id == 'transcription:soap-ankle-speech':
                folder = pc.private_directory(campaign.root / 'evidence' / 'stray')
                (folder / 'note.txt').write_text('synthetic stray ' + DEEPGRAM_KEY)
        FakeWorker.hooks = {'in_flight': in_flight}
        result = self.run_transcription(campaign)
        FakeWorker.hooks = {}
        self.assertEqual((result['decision'], result['verdict']), ('failed', 'FAIL'))
        self.assertIn('the final leak scan did not come back clean', result['reasons'])
        self.assertIsNotNone(campaign.ledger.campaign_stop())



class TranscriptJudgeTests(unittest.TestCase):
    """What a transcript's generation is judged by (pure): every ADOPTED answer must cite the saved notes at its own
    offsets and say nothing its citations do not; a signature or initials field is never answered."""
    NOTES = 'indication screening colonoscopy for a synthetic patient findings no polyps were seen'

    def answer(self, text, start, end, quote=None):
        return {'status': 'supported', 'text': text,
                'evidence': [{'start': start, 'end': end, 'quote': self.NOTES[start:end] if quote is None else quote}]}

    def test_source_support(self):
        tr = st.transcription_module()
        whole = len(self.NOTES)
        self.assertEqual(tr.source_support_problems(self.answer('screening colonoscopy', 0, whole), self.NOTES), [])
        self.assertEqual(tr.source_support_problems(self.answer('screening   colonoscopy\n', 0, whole), self.NOTES), [])
        cases = [({'status': 'supported', 'text': 'screening colonoscopy', 'evidence': []}, 'cites no source'),
                 (self.answer('screening colonoscopy', 0, whole, quote='screening colonoscopy'), 'at its offsets'),
                 (self.answer('screening colonoscopy', 0, 10), 'in none of its citations'),
                 (self.answer('a polyp was removed', 0, whole), 'in none of its citations'),
                 (self.answer('', 0, whole), 'is empty'),
                 ({'status': 'supported', 'text': 'x', 'evidence': [{'start': '0', 'end': 5, 'quote': 'indic'}]},
                  'at its offsets'),
                 ({'status': 'supported', 'text': 'x', 'evidence': 'indication'}, 'cites no source')]
        for answer, why in cases:
            with self.subTest(answer=str(answer)[:70]):
                self.assertTrue(any(why in p for p in tr.source_support_problems(answer, self.NOTES)),
                                tr.source_support_problems(answer, self.NOTES))

    def test_an_unsupported_or_protected_adoption_stops_the_stage(self):
        from types import SimpleNamespace
        tr = st.transcription_module()
        evidence = scratch(self)
        fields = [{'key': 'v3_1', 'label': 'Chief complaint', 'kind': 'text'},
                  {'key': 'v3_2', 'label': 'Clinician signature', 'kind': 'signature'},
                  {'key': 'v3_3', 'label': 'Plan', 'kind': 'long_text'}]
        version = SimpleNamespace(fields=fields)
        answers = {'v3_1': self.answer('a polyp was removed', 0, len(self.NOTES)),
                   'v3_2': self.answer('synthetic patient', 0, len(self.NOTES)),
                   'v3_3': {'status': 'missing', 'text': '', 'evidence': []}}
        (evidence / 'answers-adopted.json').write_text(json.dumps({'answers': answers}))
        outcomes = {key: {'status': value['status'], 'text': value['text']} for key, value in answers.items()}
        fields_out, findings, details = tr.TranscriptionRun.judge_transcript(self.NOTES)(
            None, version, outcomes, b'', b'', raw={}, reviewed={}, evidence=evidence)
        self.assertEqual(fields_out, {'v3_1': 'adopted', 'v3_2': 'adopted', 'v3_3': 'missing'})
        codes = sorted(f['code'] for f in findings)
        self.assertEqual(codes, ['adopted_without_source_support', 'protected_area_answered'])
        verdict = pc.classify_case(fields_out, codes)
        self.assertEqual((verdict['verdict'], verdict['stops_stage']), ('unsafe', True))
        self.assertEqual(details['source_support']['v3_2']['problems'], [])
        answers['v3_1'] = self.answer('screening colonoscopy', 0, len(self.NOTES))
        del answers['v3_2']
        (evidence / 'answers-adopted.json').unlink()
        (evidence / 'answers-adopted.json').write_text(json.dumps({'answers': answers}))
        fields_out, findings, _ = tr.TranscriptionRun.judge_transcript(self.NOTES)(
            None, version, {k: {'status': v['status']} for k, v in answers.items()}, b'', b'', raw={}, reviewed={},
            evidence=evidence)
        self.assertEqual((findings, pc.classify_case(fields_out, [])['stops_stage']), ([], False))

    def test_the_page_offers_the_transcript_as_a_browser_would_submit_it(self):
        from types import SimpleNamespace
        tr = st.transcription_module()
        job = SimpleNamespace(pk='1f6c0c9e-0000-4000-8000-000000000001')
        page = ('<form method="post" action="/encounters/x/notes/" data-transcript-form><input type="hidden" '
                f'name="transcript_job" value="{job.pk}"><textarea id="t" name="corrected_transcript" rows="8">\n'
                'left &amp; right ankle &lt;synthetic&gt;</textarea></form>')
        self.assertEqual(tr.transcript_shown(page, job), 'left & right ankle <synthetic>')
        self.assertIsNone(tr.transcript_shown(page.replace(str(job.pk), 'another-job'), job))
        self.assertIsNone(tr.transcript_shown('<p>no review</p>', job))
        self.assertEqual(tr.provider_transcript({'results': {'channels': [{'alternatives': [{'transcript': 'w'}]}]}}), 'w')
        self.assertIsNone(tr.provider_transcript({'results': {'channels': []}}))


if __name__ == '__main__':
    unittest.main()
