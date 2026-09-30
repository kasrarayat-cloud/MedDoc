"""The generic campaign machinery (ops/provider_campaign.py), offline and without Django.

What each group proves, stated so a reader can see how it would fail:
  · DECLARATION — the committed declaration parses to exactly the numbers it states; an untracked, uncommitted, staged,
    assume-unchanged-hidden, revoked, doubly-authorized or unauthorized declaration is refused.
  · LEDGER — records are write-once and gapless, only the lock holder writes, and an attempt left without an outcome is
    recovered as `interrupted_unknown` in a NEW record, the attempt untouched.
  · EXPOSURE — provider-reported usage is priced at the declared rates (cache writes 1.25x / 2x, reads at the cached
    rate, US geography 1.1x); anything unknown counts at the maximum x 1.1.
  · ADMISSION — over the stage cap, over the total cap, over the request count, with an open attempt, before the
    prerequisite passed, after a stage decision: refused.
  · CREDENTIAL — only the declared file; a `.env` path (written or resolved) is refused BEFORE anything is opened; the
    wrong mode, owner or shape is refused.
  · ENVIRONMENT, CAPTURE, LEAKS — the request process inherits nothing; the captured request never carries the key; a
    planted key is found wherever it hides; a tree the scan cannot read whole (an unlistable directory, an unreadable
    file, a link, a special file, an environment file — never opened) is a stop, never 'no leak'.
  · CREDENTIAL LINKS, ENVIRONMENT NAMES — a hard-linked credential or a symbolic link at any path component is refused
    before any read; `.env`, `*.env`, `.env.*`, `*.env.*` are environment files wherever they appear.
  · REQUEST PROCESS — `_inner` refuses before django.setup() without QUILLMD_ENV_MANAGED=1 or beside rebuild/.env.
  · MODEL CHECK JUDGE, REVIEW FORM, EXPORT CELLS — evidence on its own question's line containing the answer; the review
    FORM's inputs, never the notes panel; all of an answer cell's text, and no hidden text or nested table in it.
  · UNKNOWN USAGE, PINNED LIMITS — a completed outcome without token counts counts at its maximum; admission uses the
    tightest of the current and every recorded set of limits, so an edited declaration never admits more.
  · CASE VERDICT — unsafe and contract findings stop a stage; held / missing / refused answers never do.
  · STAGE DECISIONS, REOPEN — numbered decisions; a failed stage is admitted again only through a committed diagnosis,
    a runner containing the repair, and money left under its own limit.
  · LIVE LEDGER SHAPE — the live ledger's documented records stay readable, model_check stays passed, and mapping and
    ordinary_notes are admitted.
No socket is opened except to the QA database address (network_guard); the provider is an in-process MockTransport.
"""
import builtins
import dataclasses
import hashlib
import html
import io
import itertools
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from . import network_guard

REPOSITORY = Path(__file__).resolve().parents[3]
REAL_DECLARATION = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
REAL_TEXT = REAL_DECLARATION.read_text(encoding='utf-8')
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-OFFLINE-TEST-KEY-000000000000000000000000000000000000-AAAAAAAA'
MAXIMUM = '0.104896'
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic Test',
       '-c', 'user.email=synthetic@test.invalid']


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


def scratch(test):
    directory = Path(tempfile.mkdtemp(prefix='campaign-test-'))
    test.addCleanup(shutil.rmtree, directory, True)
    return directory


def git(root, *args, check=True):
    return subprocess.run([*GIT, '-C', str(root), *args], capture_output=True, check=check)


def repository_with(test, text, name='20260928-test-declaration.md', commit=True):
    root = scratch(test)
    git(root, 'init', '-q')
    folder = root / 'docs' / 'foundation' / 'mutations'
    folder.mkdir(parents=True)
    path = folder / name
    path.write_text(text, encoding='utf-8')
    if commit:
        git(root, 'add', '--', str(path.relative_to(root)))
        git(root, 'commit', '-q', '-m', 'Synthetic declaration')
    return root, path


def declaration(**changes):
    base = pc.Declaration(
        path='/synthetic/decl.md', sha256='0' * 64, commit='0' * 40, commit_time='2026-09-28T23:29:58+00:00',
        campaign='quillmd-v1-sonnet5-staged-40', authority_id='synthetic-authority', authorization='owner approved',
        owner_words='Approve', total_limit=Decimal('40.00'),
        stages=(pc.Stage('model_check', Decimal('5.00'), 10, None), pc.Stage('mapping', Decimal('25.00'), None, 'model_check'),
                pc.Stage('ordinary_notes', Decimal('10.00'), None, 'model_check')),
        transfers=False, provider='anthropic', model='claude-sonnet-5', rates=pc.Rates('2', '10', '0.20'),
        thinking='disabled', effort='medium', inference_geo='',
        pricing_versions=(('model_check', 'configured-v1:' + 'a' * 64),), credential_file='/synthetic/credential/key')
    return dataclasses.replace(base, **changes)


def attempt(number, stage='model_check', maximum=MAXIMUM, campaign='quillmd-v1-sonnet5-staged-40',
            authority='synthetic-authority', limits=None, runner_commit=None, terms='synthetic', engine_files=None):
    """A ledger attempt as the runner writes it. `terms` (A1): the pricing terms it records — by default those of the
    synthetic `declaration()`; None writes a legacy attempt that records none (like the live ledger's attempt 1)."""
    record = {'number': number, 'campaign': campaign, 'authority_id': authority, 'stage': stage, 'maximum_cost': maximum,
              'rates': {'input': '2', 'output': '10', 'cached': '0.20'}, 'started_at': pc.now()}
    if limits is not None:
        record['limits'] = limits
    if terms is not None:
        record['terms'] = terms_record(declaration()) if terms == 'synthetic' else terms
    if engine_files is not None:
        record['engine_files'] = engine_files
    if runner_commit is not None:
        record['runner_commit'] = runner_commit
    return record


def limits_record(d):
    """The limits a new attempt records (item 8), spelled out here independently of the code under test: the total,
    and every stage's limit, request count and prerequisites."""
    return {'total_limit_provider_usd': format(d.total_limit, 'f'),
            'stages': {s.id: {'limit_provider_usd': format(s.limit, 'f'), 'max_requests': s.max_requests,
                              'requires': [s.requires] if s.requires else []} for s in d.stages}}


def terms_record(d):
    """The pricing terms a new attempt records (A1), spelled out independently of the code under test: the declared
    rates (as the declaration spells them), model, thinking, effort, inference geography and every pricing version."""
    return {'rates': {'input': d.rates.input, 'output': d.rates.output, 'cached': d.rates.cached}, 'model': d.model,
            'thinking': d.thinking, 'effort': d.effort, 'inference_geo': d.inference_geo,
            'pricing_versions': {name: version for name, version in d.pricing_versions}}


def usage(**changes):
    return {'input_tokens': 1000, 'output_tokens': 200, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0,
            'cache_creation': None, 'inference_geo': 'global', **changes}


class DeclarationTests(unittest.TestCase):
    def test_the_committed_declaration_parses_to_exactly_what_it_states(self):
        out = io.StringIO()
        d = pc.declared(REAL_DECLARATION, repository=REPOSITORY, out=out)
        self.assertEqual((d.campaign, d.authority_id), ('quillmd-v1-sonnet5-staged-40',
                                                        'quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk'))
        self.assertEqual(d.total_limit, Decimal('40.00'))
        self.assertEqual(d.stages, (pc.Stage('model_check', Decimal('5.00'), 10, None),
                                    pc.Stage('mapping', Decimal('25.00'), None, 'model_check'),
                                    pc.Stage('ordinary_notes', Decimal('10.00'), None, 'model_check')))
        self.assertEqual((d.provider, d.model, d.thinking, d.effort, d.inference_geo),
                         ('anthropic', 'claude-sonnet-5', 'disabled', 'medium', ''))
        self.assertEqual(d.rates, pc.Rates('2', '10', '0.20'))
        self.assertEqual(d.pricing_version('model_check'),
                         'configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d')
        self.assertEqual(d.pricing_version('ordinary_notes_field_relations'),
                         'configured-v1:eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180')
        self.assertEqual(d.credential_file, '/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key')
        self.assertEqual(d.authorization, 'owner 2026-09-28 approved the staged $40 maximum at the stated limits')
        self.assertEqual(d.owner_words, 'Approve the staged $40 maximum')
        committed = git(REPOSITORY, 'log', '-1', '--format=%cI', '--', str(REAL_DECLARATION.relative_to(REPOSITORY)))
        self.assertIn(committed.stdout.decode().strip(), out.getvalue())
        self.assertEqual(d.commit_time, committed.stdout.decode().strip())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            d.total_limit = Decimal('400')

    def test_a_committed_copy_parses_and_its_commit_time_is_printed(self):
        root, path = repository_with(self, REAL_TEXT)
        out = io.StringIO()
        d = pc.declared(path, repository=root, out=out)
        stamp = git(root, 'log', '-1', '--format=%cI').stdout.decode().strip()
        self.assertEqual(d.commit_time, stamp)
        self.assertIn(stamp, out.getvalue())
        self.assertEqual(d.sha256, hashlib.sha256(REAL_TEXT.encode()).hexdigest())

    def refused(self, root, path, fragment=''):
        with self.assertRaises(pc.Refused) as caught:
            pc.declared(path, repository=root, out=io.StringIO())
        self.assertIn(fragment, str(caught.exception))

    def test_an_untracked_declaration_is_refused(self):
        root, path = repository_with(self, REAL_TEXT, commit=False)
        self.refused(root, path, 'tracked, committed and unmodified')

    def test_an_uncommitted_edit_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        path.write_text(REAL_TEXT.replace('total_limit_provider_usd: 40.00', 'total_limit_provider_usd: 400.00'))
        self.refused(root, path, 'tracked, committed and unmodified')

    def test_a_staged_edit_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        path.write_text(REAL_TEXT.replace('max_requests 10', 'max_requests 99'))
        git(root, 'add', '--', str(path.relative_to(root)))
        self.refused(root, path, 'tracked, committed and unmodified')

    def test_an_edit_hidden_by_assume_unchanged_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        git(root, 'update-index', '--assume-unchanged', '--', str(path.relative_to(root)))
        path.write_text(REAL_TEXT.replace('max_requests 10', 'max_requests 99'))
        self.assertEqual(git(root, 'diff', '--quiet', 'HEAD', '--', str(path.relative_to(root)), check=False).returncode, 0)
        self.refused(root, path, 'committed blob')

    def test_a_committed_revocation_is_refused_wherever_it_is_written(self):
        sentence = pc.KNOWN_NON_REVOCATIONS[0]
        for text in (REAL_TEXT + '\nrevoked: owner 2026-09-29\n',
                     REAL_TEXT + '\n## Approval rescinded\n',
                     REAL_TEXT + '\nThe owner has withdrawn this approval.\n',
                     REAL_TEXT + '\n| status | Cancelled |\n',
                     REAL_TEXT.replace('## Authority', '## Authority — SUSPENDED'),
                     REAL_TEXT + '\n' + sentence + '\n'):
            with self.subTest(tail=text[-40:]):
                root, path = repository_with(self, text)
                self.refused(root, path, 'revocation')

    def test_the_benign_key_sentence_is_the_only_exception(self):
        self.assertEqual(len(pc.KNOWN_NON_REVOCATIONS), 1)
        self.assertIn(pc.KNOWN_NON_REVOCATIONS[0], ' '.join(REAL_TEXT.split()))
        edited = REAL_TEXT.replace('revoked when the campaign ends', 'revoked now')
        root, path = repository_with(self, edited)
        self.refused(root, path, 'revocation')

    def test_two_authorization_lines_are_refused(self):
        line = 'authorization: owner 2026-09-28 approved the staged $40 maximum at the stated limits'
        for text in (REAL_TEXT.replace(line, line + '\nauthorization: owner 2026-09-29 approved $400 at the stated limits'),
                     REAL_TEXT + '\n**Authorization**: pending\n',
                     REAL_TEXT + '\n- Authorised by the owner for $400 as well\n',
                     REAL_TEXT + '\nAuthorizations: a second grant\n'):
            with self.subTest(text=text[-60:]):
                root, path = repository_with(self, text)
                self.refused(root, path, 'no owner authorization')

    def test_an_authorization_with_anything_after_it_or_missing_is_refused(self):
        line = 'authorization: owner 2026-09-28 approved the staged $40 maximum at the stated limits'
        for text in (REAL_TEXT.replace(line, line + ' once the quote is checked'), REAL_TEXT.replace(line, '')):
            with self.subTest(text=len(text)):
                root, path = repository_with(self, text)
                self.refused(root, path, 'no owner authorization')

    def test_missing_owner_words_are_refused(self):
        root, path = repository_with(self, REAL_TEXT.replace('owner_words: Approve the staged $40 maximum\n', ''))
        self.refused(root, path, 'owner_words')

    def test_a_declaration_outside_the_mutations_folder_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        elsewhere = root / 'docs' / 'decl.md'
        shutil.copy(path, elsewhere)
        git(root, 'add', '--', 'docs/decl.md')
        git(root, 'commit', '-q', '-m', 'elsewhere')
        self.refused(root, elsewhere, 'docs/foundation/mutations')

    def test_a_credential_file_under_an_env_name_is_refused_in_the_declaration(self):
        text = REAL_TEXT.replace('credential/anthropic-api-key', 'credential/.env')
        root, path = repository_with(self, text)
        self.refused(root, path, 'environment file')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)
        self.ledger = pc.Ledger(self.root / 'ledger').acquire()
        self.addCleanup(self.ledger.release)

    def test_records_are_write_once_and_gapless(self):
        self.ledger.write_attempt(attempt(1))
        with self.assertRaises(FileExistsError):
            pc.write_new(self.ledger.dir / '001-attempt.json', attempt(1))
        with self.assertRaises(pc.Refused):
            self.ledger.write_attempt(attempt(2))           # (attempt 1 has no outcome)
        self.ledger.write_outcome(1, {'class': 'completed'})
        with self.assertRaises(pc.Refused):
            self.ledger.write_outcome(1, {'class': 'completed'})
        with self.assertRaises(pc.Refused):
            self.ledger.write_attempt(attempt(3))           # (a gap)
        pc.write_new(self.ledger.dir / '003-attempt.json', attempt(3))
        with self.assertRaises(pc.Refused) as caught:
            self.ledger.rows()
        self.assertIn('gapless', str(caught.exception))

    def test_only_the_lock_holder_writes_and_one_runner_holds_it(self):
        other = pc.Ledger(self.root / 'ledger')
        with self.assertRaises(pc.Refused):
            other.write_attempt(attempt(1))
        with self.assertRaises(pc.Refused) as caught:
            other.acquire()
        self.assertIn('Another runner', str(caught.exception))

    def test_an_outcome_needs_its_attempt_and_strays_are_refused(self):
        with self.assertRaises(pc.Refused):
            self.ledger.write_outcome(1, {'class': 'completed'})
        (self.ledger.dir / '.partial-1-001-attempt.json').write_text('{}')     # (a kill's leftover temporary: ignored)
        self.assertEqual(self.ledger.rows(), [])
        (self.ledger.dir / 'notes.txt').write_text('stray')
        with self.assertRaises(pc.Refused):
            self.ledger.rows()

    def test_an_interrupted_attempt_is_recovered_in_a_new_record_and_never_edited(self):
        self.ledger.write_attempt(attempt(1))
        path = self.ledger.dir / '001-attempt.json'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(pc.recover_interrupted(self.ledger), [1])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        (row,) = self.ledger.rows()
        self.assertEqual(row[1]['class'], 'interrupted_unknown')
        self.assertEqual(pc.exposure(*row), Decimal(MAXIMUM) * Decimal('1.1'))
        self.assertEqual(pc.recover_interrupted(self.ledger), [])

    def test_a_stage_is_decided_once(self):
        self.ledger.write_stage('model_check', 'failed', {'reasons': ['synthetic']})
        with self.assertRaises(pc.Refused):
            self.ledger.write_stage('model_check', 'passed', {})
        self.assertEqual(self.ledger.stage_record('model_check', 'failed')['reasons'], ['synthetic'])


class ExposureTests(unittest.TestCase):
    RATES = pc.Rates('2', '10', '0.20')

    def test_known_usage_is_priced_at_the_declared_rates(self):
        split = usage(cache_read_input_tokens=300, cache_creation_input_tokens=400,
                      cache_creation={'ephemeral_5m_input_tokens': 100, 'ephemeral_1h_input_tokens': 300})
        standard = (Decimal(1000) * 2 + Decimal(300) * Decimal('0.20') + Decimal(100) * 2 * Decimal('1.25')
                    + Decimal(300) * 2 * 2 + Decimal(200) * 10) / 1000000
        self.assertEqual(standard, Decimal('0.00551'))
        self.assertEqual(pc.usage_cost(split, self.RATES), standard)
        self.assertEqual(pc.usage_cost({**split, 'inference_geo': 'us'}, self.RATES), standard * Decimal('1.1'))
        self.assertEqual(pc.usage_cost({**split, 'inference_geo': None}, self.RATES), standard * Decimal('1.1'))
        self.assertEqual(pc.usage_cost({**split, 'inference_geo': None}, self.RATES, unknown_geography_margin=False), standard)
        unsplit = usage(cache_creation_input_tokens=400)
        self.assertEqual(pc.usage_cost(unsplit, self.RATES), (Decimal(2000) + 400 * 2 * 2 + 2000) / 1000000)
        with self.assertRaises(ValueError):
            pc.usage_cost(usage(cache_creation_input_tokens=5, cache_creation={'ephemeral_5m_input_tokens': 1,
                                                                             'ephemeral_1h_input_tokens': 1}), self.RATES)

    def test_a_completed_outcome_counts_its_usage_and_every_unknown_counts_the_maximum(self):
        bound = Decimal(MAXIMUM) * Decimal('1.1')
        self.assertEqual(pc.exposure(attempt(1), {'class': 'completed', 'usage': usage()}), Decimal('0.004'))
        self.assertEqual(pc.exposure(attempt(1), None), bound)
        for cls in ('unknown', 'uncertain', 'interrupted_unknown', 'reconciliation'):
            with self.subTest(cls=cls):
                self.assertEqual(pc.exposure(attempt(1), {'class': cls}), bound)
                self.assertEqual(pc.exposure(attempt(1), {'class': cls, 'usage': usage()}), bound)
        self.assertEqual(pc.exposure(attempt(1), {'class': 'reconciliation', 'usage': usage(output_tokens=20000)}),
                         Decimal('0.202'))
        self.assertEqual(pc.exposure(attempt(1), {'class': 'completed', 'usage': usage(output_tokens=-1)}), bound)
        self.assertEqual(pc.exposure(attempt(1), {'class': 'not_sent'}), Decimal(0))


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)

    def campaign(self, **changes):
        campaign = pc.Campaign(declaration(**changes), self.root)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def spend(self, campaign, number, stage='model_check', maximum=MAXIMUM, outcome=None):
        campaign.ledger.write_attempt(attempt(number, stage, maximum, limits=limits_record(campaign.declaration)))
        if outcome is not False:
            campaign.ledger.write_outcome(number, outcome or {'class': 'uncertain'})

    def test_an_attempt_that_fits_is_admitted_at_its_maximum_times_1_1(self):
        self.assertEqual(self.campaign().admit('model_check', MAXIMUM), Decimal('0.1153856'))

    def test_over_the_stage_cap_is_refused(self):
        campaign = self.campaign()
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', '4.60')           # 5.06 > 5.00
        self.assertIn('Stage model_check limit', str(caught.exception))
        self.spend(campaign, 1, maximum='4.00')             # an unknown outcome counts 4.40
        self.assertEqual(campaign.admit('model_check', '0.50'), Decimal('0.550'))
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', '0.60')           # 4.40 + 0.66 > 5.00

    def test_over_the_total_cap_is_refused_even_when_the_stage_fits(self):
        campaign = self.campaign(total_limit=Decimal('6.00'))
        self.spend(campaign, 1, maximum='4.00')
        campaign.ledger.write_stage('model_check', 'passed', {})
        self.assertEqual(campaign.admit('mapping', '1.40'), Decimal('1.540'))
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('mapping', '1.50')               # 4.40 + 1.65 > 6.00, while mapping's 25.00 fits
        self.assertIn('Campaign limit', str(caught.exception))

    def test_over_the_stage_request_count_is_refused(self):
        stages = (pc.Stage('model_check', Decimal('5.00'), 2, None),)
        campaign = self.campaign(stages=stages)
        self.spend(campaign, 1, outcome={'class': 'completed', 'usage': usage()})
        self.spend(campaign, 2, outcome={'class': 'completed', 'usage': usage()})
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('all 2 requests', str(caught.exception))

    def test_an_open_attempt_is_refused(self):
        campaign = self.campaign()
        self.spend(campaign, 1, outcome=False)
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('no outcome', str(caught.exception))

    def test_a_stage_before_its_prerequisite_passed_is_refused(self):
        campaign = self.campaign()
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('mapping', MAXIMUM)
        self.assertIn('requires model_check', str(caught.exception))
        campaign.ledger.write_stage('model_check', 'passed', {})
        self.assertEqual(campaign.admit('mapping', MAXIMUM), Decimal('0.1153856'))
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', MAXIMUM)          # (a passed stage is never re-run in place)

    def test_a_failed_model_check_stops_every_stage(self):
        campaign = self.campaign()
        campaign.ledger.write_stage('model_check', 'failed', {'reasons': ['synthetic']})
        for stage in ('model_check', 'mapping', 'ordinary_notes'):
            with self.subTest(stage=stage), self.assertRaises(pc.Refused):
                campaign.admit(stage, MAXIMUM)

    def test_an_unknown_outcome_counts_at_its_maximum_times_1_1(self):
        campaign = self.campaign()
        self.spend(campaign, 1, outcome={'class': 'uncertain', 'usage': usage(input_tokens=1, output_tokens=1)})
        self.assertEqual(campaign.totals('model_check')['exposure'], Decimal('0.1153856'))
        self.assertEqual(campaign.totals()['unknown'], 1)

    def test_money_is_decimal_and_a_stopped_or_foreign_campaign_admits_nothing(self):
        campaign = self.campaign()
        for value in (0.1, float('nan'), 'NaN', '0', '-1', True):
            with self.subTest(value=value), self.assertRaises(pc.Refused):
                campaign.admit('model_check', value)
        campaign.ledger.write_attempt(attempt(1, authority='another-authority'))
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', MAXIMUM)

    def test_a_campaign_stop_admits_nothing(self):
        campaign = self.campaign()
        campaign.ledger.write_stop({'reason': 'synthetic'})
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', MAXIMUM)


class NoEnvOpened:
    """builtins.open, io.open and os.open raise on any path naming a `.env` file or directory, and record the call."""

    def __init__(self):
        self.attempts = []

    def guard(self, original):
        def wrapped(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                text = os.fsdecode(file)
                if any(pc.env_name(part) for part in Path(text).parts):
                    self.attempts.append(text)
                    raise AssertionError(f'an environment file was opened: {text}')
            return original(file, *args, **kwargs)
        return wrapped

    def __enter__(self):
        self.patches = [patch('builtins.open', self.guard(builtins.open)), patch('io.open', self.guard(io.open)),
                        patch('os.open', self.guard(os.open))]
        for item in self.patches:
            item.start()
        return self

    def __exit__(self, *exc):
        for item in reversed(self.patches):
            item.stop()


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)
        self.folder = self.root / 'credential'
        self.folder.mkdir(mode=0o700)
        self.path = self.folder / 'anthropic-api-key'

    def write(self, text, mode=0o600, path=None):
        path = path or self.path
        path.write_text(text)
        os.chmod(path, mode)
        return path

    def test_the_declared_file_yields_the_key(self):
        self.write(SYNTHETIC_KEY + '\n')
        self.assertEqual(pc.load_credential(str(self.path)), SYNTHETIC_KEY)
        self.write(SYNTHETIC_KEY, path=self.folder / 'no-newline')
        self.assertEqual(pc.load_credential(str(self.folder / 'no-newline')), SYNTHETIC_KEY)
        d = declaration(credential_file=str(self.path))
        self.assertEqual(pc.load_credential(str(self.path), d), SYNTHETIC_KEY)
        with self.assertRaises(pc.Refused):
            pc.load_credential(str(self.folder / 'no-newline'), d)          # (not the declared file)

    def test_an_env_path_is_refused_before_anything_is_opened(self):
        os.symlink(self.root / 'target.env', self.folder / 'link')          # (dangling: its target is never created)
        paths = [self.root / '.env', self.root / 'key.env', self.root / '.env' / 'key', self.root / 'x.env' / 'key',
                 self.folder / 'link']
        with NoEnvOpened() as guard:
            for path in paths:
                with self.subTest(path=path), self.assertRaises(pc.Refused) as caught:
                    pc.load_credential(str(path))
                self.assertIn('environment file', str(caught.exception))
        self.assertEqual(guard.attempts, [])

    def test_the_wrong_mode_owner_or_shape_is_refused(self):
        for mode in (0o640, 0o644, 0o400, 0o700):
            path = self.folder / f'mode-{mode:o}'
            with self.subTest(mode=oct(mode)), self.assertRaises(pc.Refused):
                pc.load_credential(str(self.write(SYNTHETIC_KEY + '\n', mode, path)))
        self.write(SYNTHETIC_KEY + '\n')
        with patch('os.getuid', return_value=os.getuid() + 1), self.assertRaises(pc.Refused) as caught:
            pc.load_credential(str(self.path))
        self.assertIn('owned by the account', str(caught.exception))
        for text in ('', '\n', SYNTHETIC_KEY + '\n\n', SYNTHETIC_KEY + '\nsecond-line\n', ' ' + SYNTHETIC_KEY,
                     SYNTHETIC_KEY + ' \n', SYNTHETIC_KEY + '\r\n', 'two words\n'):
            with self.subTest(text=repr(text[-12:])), self.assertRaises(pc.Refused):
                pc.load_credential(str(self.write(text)))
        with self.assertRaises(pc.Refused):
            pc.load_credential(str(self.folder / 'missing'))
        os.symlink(self.path, self.folder / 'plain-link')
        self.write(SYNTHETIC_KEY + '\n')
        with self.assertRaises(pc.Refused):
            pc.load_credential(str(self.folder / 'plain-link'))            # (a link is never followed)
        with self.assertRaises(pc.Refused):
            pc.load_credential('relative/anthropic-api-key')


class EnvironmentTests(unittest.TestCase):
    LISTED = ('ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_PROFILE', 'ANTHROPIC_CUSTOM_HEADERS',
              'ANTHROPIC_FEDERATION_RULE_ID', 'ANTHROPIC_FEDERATION_SOMETHING', 'ANTHROPIC_IDENTITY_TOKEN',
              'ANTHROPIC_ORGANIZATION_ID', 'ANTHROPIC_WORKSPACE_ID', 'ANTHROPIC_LOG', 'HTTP_PROXY', 'HTTPS_PROXY',
              'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy', 'SSL_CERT_FILE',
              'REQUESTS_CA_BUNDLE', 'OPENAI_API_KEY', 'PYTHONPATH')

    def test_the_request_process_inherits_nothing_and_gets_a_fresh_empty_config_dir(self):
        root = scratch(self)
        planted = {name: 'https://attacker.invalid' for name in self.LISTED}
        with patch.dict(os.environ, {**planted, 'ANTHROPIC_API_KEY': 'sk-ant-some-other-key-000000000',
                                     'ANTHROPIC_CONFIG_DIR': '/home/somebody/.config/anthropic'}):
            env = pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), {'QUILLMD_DB_NAME': 'quillmd_qa_sonnet5'},
                                          config_parent=str(root))
            second = pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), config_parent=str(root))
        for name in self.LISTED:
            self.assertNotIn(name, env)
        self.assertFalse([name for name in env if pc.forbidden_name(name)])
        self.assertEqual(env['ANTHROPIC_API_KEY'], SYNTHETIC_KEY)
        config = Path(env['ANTHROPIC_CONFIG_DIR'])
        self.assertTrue(config.is_dir() and config.parent == root and not any(config.iterdir()))
        self.assertEqual(os.stat(config).st_mode & 0o777, 0o700)
        self.assertNotEqual(env['ANTHROPIC_CONFIG_DIR'], second['ANTHROPIC_CONFIG_DIR'])
        self.assertEqual({k: env[k] for k in ('QUILLMD_AI_MODE', 'QUILLMD_AI_PROVIDER', 'QUILLMD_AI_MODEL', 'QUILLMD_AI_INPUT_RATE',
                                              'QUILLMD_AI_OUTPUT_RATE', 'QUILLMD_AI_CACHED_RATE', 'QUILLMD_AI_THINKING',
                                              'QUILLMD_AI_EFFORT', 'QUILLMD_AI_INFERENCE_GEO', 'QUILLMD_DATA_MODE',
                                              'QUILLMD_DB_NAME')},
                         {'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5',
                          'QUILLMD_AI_INPUT_RATE': '2', 'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',
                          'QUILLMD_AI_THINKING': 'disabled', 'QUILLMD_AI_EFFORT': 'medium', 'QUILLMD_AI_INFERENCE_GEO': '',
                          'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_DB_NAME': 'quillmd_qa_sonnet5'})
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        pc.scrubbed_now(env)

    def test_extra_settings_cannot_add_a_removed_variable_and_the_process_checks_itself(self):
        root = scratch(self)
        for name in self.LISTED:
            with self.subTest(name=name), self.assertRaises(pc.Refused):
                pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), {name: 'x'}, config_parent=str(root))
        env = pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), config_parent=str(root))
        with self.assertRaises(pc.Refused):
            pc.scrubbed_now({**env, 'https_proxy': 'http://proxy.invalid:3128'})
        (Path(env['ANTHROPIC_CONFIG_DIR']) / 'configs').mkdir()
        with self.assertRaises(pc.Refused):
            pc.scrubbed_now(env)


class CaptureTests(unittest.TestCase):
    """Through the real SDK around an in-process MockTransport: the bytes that WOULD leave, captured before they do."""

    def setUp(self):
        import anthropic
        import httpx
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True, mode=0o700)
        self.seen = []

        self.status = 200

        def handler(request):
            self.seen.append({'headers': dict(request.headers), 'captured_first': (self.evidence / 'request.json').exists()})
            if self.status != 200:
                return httpx.Response(self.status, headers={'request-id': 'req_synthetic_error',
                                                            'set-cookie': '_cfuvid=synthetic; path=/'},
                                      json={'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}})
            return httpx.Response(200, headers={'request-id': 'req_synthetic', 'set-cookie': '_cfuvid=synthetic; path=/'},
                                  json={
                'id': 'msg_synthetic', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5',
                'content': [{'type': 'text', 'text': '{}'}], 'stop_reason': 'end_turn', 'stop_sequence': None,
                'usage': {'input_tokens': 10, 'output_tokens': 2}})

        self.client = lambda retries=0: anthropic.Anthropic(api_key=SYNTHETIC_KEY, max_retries=retries,
                                                            http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        pc.install_request_capture()
        self.addCleanup(pc.uninstall_request_capture)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)

    def send(self, client):
        return client.messages.create(model='claude-sonnet-5', max_tokens=16,
                                      messages=[{'role': 'user', 'content': 'synthetic'}])

    def test_the_exact_request_is_captured_before_it_is_sent_and_never_carries_the_key(self):
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        self.send(self.client())
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(self.seen[0]['captured_first'])
        self.assertEqual(self.seen[0]['headers']['x-api-key'], SYNTHETIC_KEY)     # (the real request carried it)
        data = (self.evidence / 'request.json').read_bytes()
        self.assertNotIn(SYNTHETIC_KEY.encode(), data)
        self.assertIsNone(pc.KEY_SHAPE.search(data))
        record = json.loads(data)
        self.assertEqual((record['method'], record['url']), ('POST', 'https://api.anthropic.com/v1/messages'))
        self.assertEqual(record['body_json']['model'], 'claude-sonnet-5')
        self.assertNotIn('x-api-key', record['headers'])
        self.assertIn('x-api-key', record['removed_headers'])
        self.assertEqual(record['client']['max_retries'], 0)
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])

    def test_a_second_request_in_one_attempt_is_refused_before_it_is_sent(self):
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        self.send(self.client())
        with self.assertRaises(pc.Refused):
            self.send(self.client())
        self.assertEqual(len(self.seen), 1)

    def test_a_request_outside_an_attempt_or_from_a_retrying_client_is_refused(self):
        with self.assertRaises(pc.Refused):
            self.send(self.client())
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        with self.assertRaises(pc.Refused):
            self.send(self.client(retries=2))
        self.assertEqual(self.seen, [])
        self.assertFalse((self.evidence / 'request.json').exists())

    def test_the_response_is_retained_as_received_before_anything_reads_it(self):
        # Refutation RAW-RESPONSE-LOST-200: the stage kept only the product's stored result, which exists only after
        # settlement succeeds; a billed response the product then refused was lost. The response is now retained by the
        # capture itself, as it arrived, whatever the caller does with it next.
        import hashlib
        from unittest.mock import patch
        from anthropic._base_client import SyncAPIClient
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        real, retained_when_parsed = SyncAPIClient._process_response, []

        def parse(client, **kwargs):                  # (the SDK's parse of the body: after the response is retained)
            retained_when_parsed.append((self.evidence / pc.RESPONSE_FILE).exists())
            return real(client, **kwargs)
        with patch.object(SyncAPIClient, '_process_response', parse):
            message = self.send(self.client())
        self.assertEqual(message.id, 'msg_synthetic')
        self.assertEqual(retained_when_parsed, [True])
        record = pc.received_response(self.evidence)
        body = (self.evidence / pc.RESPONSE_BODY).read_bytes()
        self.assertEqual((record['attempt'], record['status_code'], record['request_id']), (1, 200, 'req_synthetic'))
        self.assertEqual(record['body_sha256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(record['body_bytes'], len(body))
        self.assertEqual((record['body_json']['id'], record['body_json']['model'], record['body_json']['stop_reason'],
                          record['body_json']['usage']), ('msg_synthetic', 'claude-sonnet-5', 'end_turn',
                                                          {'input_tokens': 10, 'output_tokens': 2}))
        self.assertNotIn('set-cookie', record['headers'])
        self.assertEqual(record['removed_headers'], ['set-cookie'])
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])

    def test_an_error_response_is_retained_too(self):
        import anthropic
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        self.status = 529
        with self.assertRaises(anthropic.APIStatusError):
            self.send(self.client())
        record = pc.received_response(self.evidence)
        self.assertEqual((record['status_code'], record['request_id'], record['body_json']['error']['type']),
                         (529, 'req_synthetic_error', 'overloaded_error'))

    def test_no_response_retained_reads_as_none_and_a_tampered_one_is_refused(self):
        self.assertIsNone(pc.received_response(self.evidence))
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        self.send(self.client())
        body = self.evidence / pc.RESPONSE_BODY
        body.chmod(0o600)
        body.write_bytes(body.read_bytes() + b' ')
        with self.assertRaises(pc.Refused):
            pc.received_response(self.evidence)

    def test_a_response_carrying_the_key_is_refused_and_never_retained(self):
        import httpx
        import anthropic
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)

        def echo(request):
            return httpx.Response(400, json={'type': 'error', 'error': {'type': 'invalid_request_error',
                                                                          'message': 'bad key ' + SYNTHETIC_KEY}})
        client = anthropic.Anthropic(api_key=SYNTHETIC_KEY, max_retries=0,
                                     http_client=httpx.Client(transport=httpx.MockTransport(echo)))
        with self.assertRaises(pc.Refused):
            self.send(client)
        self.assertFalse((self.evidence / pc.RESPONSE_FILE).exists())
        self.assertFalse((self.evidence / pc.RESPONSE_BODY).exists())

    def test_uninstalling_restores_the_sdk(self):
        from anthropic._base_client import SyncAPIClient
        self.assertTrue(getattr(SyncAPIClient._prepare_request, '_campaign_capture', False))
        self.assertTrue(getattr(SyncAPIClient._attempt_request, '_campaign_capture', False))
        pc.uninstall_request_capture()
        self.assertFalse(getattr(SyncAPIClient._prepare_request, '_campaign_capture', False))
        self.assertFalse(getattr(SyncAPIClient._attempt_request, '_campaign_capture', False))


class TransportGuardTests(unittest.TestCase):
    """The last door before a socket, on a REAL httpx.HTTPTransport. Every refusal happens before a connection is
    attempted; the one request it lets through then meets the network guard, which proves it was let through."""

    def setUp(self):
        import httpx
        self.httpx = httpx
        self.evidence = scratch(self)
        pc.install_transport_guard()
        self.addCleanup(pc.uninstall_transport_guard)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)
        self.addCleanup(pc.SENT.clear)
        self.client = httpx.Client(transport=httpx.HTTPTransport())
        self.addCleanup(self.client.close)

    def post(self, url=pc.PROVIDER_URL):
        return self.client.post(url, json={'model': 'claude-sonnet-5'})

    def test_outside_an_attempt_to_another_host_or_uncaptured_is_refused_before_connecting(self):
        with self.assertRaises(pc.Refused):
            self.post()
        pc.CURRENT_ATTEMPT.update(number=7, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        with self.assertRaises(pc.Refused):
            self.post()                                        # (not captured)
        (self.evidence / 'request.json').write_text('{}')
        for url in ('https://api.deepgram.com/v1/listen', 'https://api.stripe.com/v1/charges',
                    'https://api.anthropic.com/v1/messages/count_tokens', 'http://api.anthropic.com/v1/messages'):
            with self.subTest(url=url), self.assertRaises(pc.Refused):
                self.post(url)
        self.assertEqual(pc.SENT, {})

    def test_one_send_per_attempt_reaches_the_network_and_a_second_is_refused(self):
        pc.CURRENT_ATTEMPT.update(number=7, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        (self.evidence / 'request.json').write_text('{}')
        with self.assertRaises(network_guard.NetworkDenied):
            self.post()                                        # (let through: the network guard stops it)
        self.assertEqual(pc.SENT, {7: 1})
        with self.assertRaises(pc.Refused):
            self.post()


class LeakTests(unittest.TestCase):
    def test_a_planted_key_is_found_wherever_it_hides_and_the_credential_itself_is_excluded(self):
        root = scratch(self)
        (root / 'evidence' / '001').mkdir(parents=True)
        (root / 'evidence' / '001' / 'clean.json').write_text('{"ok": true}')
        credential = root / 'credential' / 'anthropic-api-key'
        credential.parent.mkdir()
        credential.write_text(SYNTHETIC_KEY + '\n')
        self.assertEqual(pc.leaked(root, SYNTHETIC_KEY, exclude=(credential,)), [])
        self.assertEqual(pc.leaked(root, SYNTHETIC_KEY), ['credential/anthropic-api-key'])
        (root / 'evidence' / '001' / 'deep').mkdir()
        (root / 'evidence' / '001' / 'deep' / 'planted.log').write_text('prefix ' + SYNTHETIC_KEY + ' suffix')
        (root / 'shape.txt').write_text('an unrelated key sk-ant-admin01-abcdefghijkl')
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as handle:
            handle.writestr('word/document.xml', '<w:t>' + SYNTHETIC_KEY + '</w:t>')
        (root / 'evidence' / '001' / 'export.docx').write_bytes(archive.getvalue())
        self.assertNotIn(SYNTHETIC_KEY.encode(), archive.getvalue())      # (compressed: invisible in the raw bytes)
        self.assertEqual(sorted(pc.leaked(root, SYNTHETIC_KEY, exclude=(credential,))),
                         ['evidence/001/deep/planted.log', 'evidence/001/export.docx', 'shape.txt'])


class RequestEnvironmentTests(unittest.TestCase):
    """The QA request process's complete environment (ops/sonnet5_qa.request_environment), built without Django."""

    def test_the_qa_process_gets_the_declared_settings_the_qa_database_and_nothing_else(self):
        from ops import sonnet5_qa as sq
        root = scratch(self)
        (root / 'tmp').mkdir(mode=0o700)
        with patch.dict(os.environ, {'ANTHROPIC_BASE_URL': 'https://attacker.invalid', 'HTTPS_PROXY': 'http://p.invalid',
                                     'QUILLMD_V3_FIELD_RELATIONS': '1', 'QUILLMD_DB_NAME': 'quillmd_fresh'}):
            env = sq.request_environment(SYNTHETIC_KEY, declaration(), root, 'synthetic-db-password',
                                         {'root': str(root), 'stage': 'model_check'})
        self.assertFalse([name for name in env if pc.forbidden_name(name)])
        self.assertEqual((env['QUILLMD_DB_NAME'], env['QUILLMD_DB_HOST'], env['QUILLMD_DB_PORT'], env['QUILLMD_DB_USER']),
                         ('quillmd_qa_sonnet5', '127.0.0.1', '55731', 'quillmd_qa'))
        self.assertTrue(env['QUILLMD_DB_NAME'].startswith(sq.DATABASE_PREFIX))
        self.assertEqual(env['QUILLMD_STATE_DIR'], str(root / 'qa-state'))
        self.assertEqual(env['QUILLMD_ENV_MANAGED'], '1')                  # (settings never calls load_dotenv)
        self.assertEqual({env[name] for name in ('QUILLMD_V3_FIELD_RELATIONS', 'QUILLMD_WM_NARRATIVE',
                                                 'QUILLMD_V3_GENERATION_BATCHES', 'QUILLMD_V3_HISTORY_CONTEXT')}, {'0'})
        self.assertEqual(env['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'], '0.0043')
        self.assertEqual(env['QUILLMD_DATA_MODE'], 'synthetic')
        self.assertEqual(env['ANTHROPIC_API_KEY'], SYNTHETIC_KEY)
        self.assertTrue(Path(env['ANTHROPIC_CONFIG_DIR']).parent == root / 'tmp')
        self.assertEqual(json.loads(env['SONNET5_QA_CONTEXT'])['stage'], 'model_check')
        self.assertNotIn('ANTHROPIC_BASE_URL', env)

    def test_the_fixed_form_builds_to_its_recorded_bytes(self):
        from ops import sonnet5_qa as sq
        form = sq.build_form()
        self.assertEqual(hashlib.sha256(form).hexdigest(), sq.FORM_SHA256)
        self.assertEqual(form, sq.build_form())
        self.assertEqual(sq.NOTES_SHA256, hashlib.sha256(sq.NOTES.encode()).hexdigest())
        self.assertEqual(sorted(sq.EXPECTED), sorted(sq.FORM_LABELS))
        for label, value in sq.EXPECTED.items():
            self.assertIn(f'{label}: {value}', sq.NOTES.splitlines())


NOT_ROOT = os.geteuid() != 0


class LeakScanFailsClosedTests(unittest.TestCase):
    """Item 1 (S1): a tree the leak scan cannot read completely is a stop — `Unscannable`, which is a `Refused` — and
    never 'no leak'. Before the repair an unlistable directory was skipped silently by os.walk and the scan said []."""

    def setUp(self):
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True)
        (self.evidence / 'clean.json').write_text('{"ok": true}')
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])

    def locked(self, path, mode):
        os.chmod(path, mode)
        self.addCleanup(os.chmod, path, 0o700)

    def unscannable(self, fragment, root=None):
        with self.assertRaises(pc.Unscannable) as caught:
            pc.leaked(self.root if root is None else root, SYNTHETIC_KEY)
        self.assertIsInstance(caught.exception, pc.Refused)
        self.assertIn(fragment, str(caught.exception))

    @unittest.skipUnless(NOT_ROOT, 'root reads every mode')
    def test_a_directory_it_cannot_list_is_a_stop_never_no_leak(self):
        hidden = self.root / 'evidence' / '002'
        hidden.mkdir()
        (hidden / 'planted.log').write_text('prefix ' + SYNTHETIC_KEY)
        self.locked(hidden, 0)
        self.unscannable('evidence/002')

    @unittest.skipUnless(NOT_ROOT, 'root reads every mode')
    def test_a_directory_it_can_list_but_not_enter_is_a_stop(self):
        hidden = self.root / 'evidence' / '002'
        hidden.mkdir()
        (hidden / 'planted.log').write_text('prefix ' + SYNTHETIC_KEY)
        self.locked(hidden, 0o400)
        self.unscannable('evidence/002')

    @unittest.skipUnless(NOT_ROOT, 'root reads every mode')
    def test_a_file_it_cannot_read_is_a_stop(self):
        unreadable = self.evidence / 'unreadable.json'
        unreadable.write_text(SYNTHETIC_KEY)
        self.locked(unreadable, 0)
        self.unscannable('evidence/001/unreadable.json')

    def test_a_missing_or_linked_root_is_a_stop(self):
        self.unscannable('', self.root / 'absent')
        alias = scratch(self) / 'alias'
        os.symlink(self.root, alias)
        self.unscannable('', alias)

    def test_links_and_special_files_are_never_followed_and_stop_the_scan(self):
        outside = scratch(self) / 'outside.log'
        outside.write_text('prefix ' + SYNTHETIC_KEY)
        for name, make in (('link.log', lambda p: os.symlink(outside, p)),
                           ('linked-dir', lambda p: os.symlink(outside.parent, p)),
                           ('pipe', os.mkfifo)):
            path = self.evidence / name
            with self.subTest(name=name):
                make(path)
                self.unscannable(f'evidence/001/{name}')
                os.unlink(path)
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])

    def test_a_file_swapped_for_a_pipe_after_it_was_listed_is_refused_before_it_is_read(self):
        # (the race between the listing's lstat and the open: the opened descriptor is checked again)
        pipe = self.evidence / 'swapped'
        os.mkfifo(pipe)
        writer = os.open(pipe, os.O_RDWR | os.O_NONBLOCK)
        self.addCleanup(os.close, writer)
        os.write(writer, b'synthetic bytes in a pipe')
        real_lstat, real_scan, scanned = os.lstat, pc._scan_bytes, []

        def listed_as_regular(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if os.fspath(path) == os.fspath(pipe):
                return os.stat_result((stat.S_IFREG | 0o600,) + tuple(info)[1:])
            return info

        def scan(data, key):
            scanned.append(bytes(data))
            return real_scan(data, key)
        with patch('os.lstat', side_effect=listed_as_regular), patch.object(pc, '_scan_bytes', side_effect=scan):
            with self.assertRaises(pc.Unscannable) as caught:
                pc.leaked(self.root, SYNTHETIC_KEY)
        self.assertIn('evidence/001/swapped', str(caught.exception))
        self.assertFalse(any(b'synthetic bytes' in block for block in scanned), scanned)

    def test_a_link_to_the_credential_is_a_stop_not_an_excluded_file(self):
        credential = self.root / 'credential' / 'anthropic-api-key'
        credential.parent.mkdir()
        credential.write_text(SYNTHETIC_KEY + '\n')
        os.symlink(credential, self.evidence / 'credential-link')
        with self.assertRaises(pc.Unscannable) as caught:
            pc.leaked(self.root, SYNTHETIC_KEY, exclude=(credential,))
        self.assertIn('evidence/001/credential-link', str(caught.exception))

    def test_the_credential_is_excluded_only_at_its_own_path(self):
        credential = self.root / 'credential' / 'anthropic-api-key'
        credential.parent.mkdir()
        credential.write_text(SYNTHETIC_KEY + '\n')
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY, exclude=(credential,)), [])
        os.link(credential, self.evidence / 'copy')
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY, exclude=(credential,)), ['evidence/001/copy'])


class LeakScanDecodingTests(unittest.TestCase):
    """A3: any decompression or decoding error, and any unexpected exception, while scanning is an `Unscannable` STOP
    (never a finding that says 'leaked', never 'no leak'); nested zip and gzip members are scanned recursively to a depth
    of 4 within a bounded number of expanded bytes, and exceeding either bound is a stop; a scan root that is, or lies
    under, an environment-named directory is refused; the evidence manifest never opens an environment-named file."""

    def setUp(self):
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True)
        (self.evidence / 'clean.json').write_text('{"ok": true}')

    def unscannable(self, fragment=''):
        with self.assertRaises(pc.Unscannable) as caught:
            pc.leaked(self.root, SYNTHETIC_KEY)
        self.assertIn(fragment, str(caught.exception))
        return caught.exception

    @staticmethod
    def zipped(members):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return data.getvalue()

    @staticmethod
    def gzipped(content):
        import gzip
        return gzip.compress(content, mtime=0)

    def test_a_corrupt_archive_member_is_a_stop_not_a_finding(self):
        archive = bytearray(self.zipped({'word/document.xml': b'<w:t>' + b'synthetic clean text ' * 200 + b'</w:t>'}))
        start = archive.index(b'word/document.xml') + len('word/document.xml')
        for offset in range(start + 10, start + 40):
            archive[offset] ^= 0xFF                                    # (the deflated member data, not its header)
        (self.evidence / 'export.docx').write_bytes(bytes(archive))
        self.unscannable('evidence/001/export.docx')

    def test_a_truncated_or_corrupt_gzip_is_a_stop(self):
        whole = self.gzipped(b'synthetic clean text ' * 500)
        for name, data in (('truncated.json.gz', whole[:len(whole) // 2]), ('corrupt.gz', whole[:10] + b'\x00' * 40)):
            path = self.evidence / name
            path.write_bytes(data)
            with self.subTest(name=name):
                self.unscannable(f'evidence/001/{name}')
            path.unlink()
        (self.evidence / 'whole.gz').write_bytes(whole)
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])

    def test_a_key_in_a_gzip_file_or_a_gzip_member_is_found(self):
        (self.evidence / 'result.json.gz').write_bytes(self.gzipped(b'{"x": "' + SYNTHETIC_KEY.encode() + b'"}'))
        (self.evidence / 'bundle.zip').write_bytes(self.zipped({'inner.gz': self.gzipped(SYNTHETIC_KEY.encode())}))
        self.assertEqual(sorted(pc.leaked(self.root, SYNTHETIC_KEY)), ['evidence/001/bundle.zip',
                                                                      'evidence/001/result.json.gz'])

    def nest(self, levels, payload):
        """`payload` inside `levels` archives, alternating zip and gzip from the inside out (zip outermost)."""
        data = payload
        for level in range(levels):
            data = self.zipped({f'level-{level}.bin': data}) if (levels - level) % 2 else self.gzipped(data)
        return data

    def test_nested_archives_are_scanned_to_a_depth_of_four_and_deeper_is_a_stop(self):
        for levels in (2, 3, 4):
            with self.subTest(levels=levels):
                path = self.evidence / 'nested.bin'
                path.write_bytes(self.nest(levels, b'prefix ' + SYNTHETIC_KEY.encode()))
                self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), ['evidence/001/nested.bin'])
                path.write_bytes(self.nest(levels, b'nothing secret here'))
                self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])
        (self.evidence / 'nested.bin').write_bytes(self.nest(5, b'nothing secret here'))
        self.unscannable('deeper than 4')

    def test_expanding_past_the_byte_bound_is_a_stop(self):
        (self.evidence / 'large.zip').write_bytes(self.zipped({'a.txt': b'0' * 4096, 'b.txt': b'1' * 4096}))
        with patch.object(pc, 'SCAN_EXPANDED_LIMIT', 6000):
            self.unscannable('more than 6000 bytes')
        with patch.object(pc, 'SCAN_EXPANDED_LIMIT', 9000):
            self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])
        (self.evidence / 'large.zip').unlink()
        (self.evidence / 'large.gz').write_bytes(self.gzipped(b'0' * 8192))
        with patch.object(pc, 'SCAN_EXPANDED_LIMIT', 6000):
            self.unscannable('more than 6000 bytes')

    def test_an_unexpected_exception_while_scanning_is_a_stop(self):
        for target in ('_scan_bytes', 'env_name'):
            with self.subTest(target=target), patch.object(pc, target, side_effect=ValueError('synthetic fault')):
                error = self.unscannable('ValueError')
                self.assertIsInstance(error, pc.Refused)

    def test_a_scan_root_under_an_environment_named_directory_is_refused(self):
        for folder in ('config.env', '.env.local', 'Deploy.ENV'):
            root = scratch(self) / folder / 'campaign'
            (root / 'evidence').mkdir(parents=True)
            (root / 'evidence' / 'clean.json').write_text('{}')
            with self.subTest(folder=folder), NoEnvOpened() as guard, self.assertRaises(pc.Unscannable) as caught:
                pc.leaked(root, SYNTHETIC_KEY)
            self.assertIn('environment', str(caught.exception))
            self.assertEqual(guard.attempts, [])

    def test_the_manifest_never_opens_an_environment_named_file(self):
        from ops import sonnet5_qa as sq
        for relative in ('.env.local', 'deep/x.env', 'config.env/inner.txt'):
            evidence = scratch(self) / 'evidence'
            (evidence / relative).parent.mkdir(parents=True, exist_ok=True)
            (evidence / relative).write_text('QUILLMD_SECRET_KEY=synthetic-not-a-secret')
            (evidence / 'request.json').write_text('{}')
            with self.subTest(relative=relative), NoEnvOpened() as guard, self.assertRaises(pc.Unscannable) as caught:
                sq.write_manifest(evidence, {'number': 1, 'stage': 'model_check'}, {})
            self.assertIn('environment file', str(caught.exception))
            self.assertEqual(guard.attempts, [])
            self.assertFalse((evidence / 'manifest.json').exists())


class EnvironmentFileNameTests(unittest.TestCase):
    """Item 3: `.env`, `*.env`, `.env.*` and `*.env.*` (any case) are environment files — refused as a credential path
    and never opened by the leak scan, which stops on meeting one."""
    ENV = ('.env', 'x.env', 'production.env', '.env.local', '.env.production', 'app.env.bak', '.ENV', 'Deploy.Env',
           'X.ENV.local')
    NOT_ENV = ('env', 'environment', 'x.environment', 'envelope.json', 'anthropic-api-key', 'dotenv', 'venv', '.venv',
               'x.venv', 'env.x', 'my-env')

    def test_every_environment_file_shape_is_named_and_nothing_else(self):
        for name in self.ENV:
            with self.subTest(name=name):
                self.assertTrue(pc.env_name(name))
        for name in self.NOT_ENV:
            with self.subTest(name=name):
                self.assertFalse(pc.env_name(name))

    def test_a_credential_path_under_any_environment_name_is_refused_before_anything_is_opened(self):
        root = scratch(self)
        paths = [root / '.env.local' / 'key', root / 'x.env.bak' / 'key', root / '.env.production',
                 root / 'Deploy.Env' / 'key', root / 'credential' / 'app.env.1']
        with NoEnvOpened() as guard:
            for path in paths:
                with self.subTest(path=path), self.assertRaises(pc.Refused) as caught:
                    pc.load_credential(str(path))
                self.assertIn('environment file', str(caught.exception))
        self.assertEqual(guard.attempts, [])

    def test_the_leak_scan_refuses_an_environment_file_instead_of_opening_it(self):
        root = scratch(self)
        evidence = root / 'evidence'
        evidence.mkdir()
        for name in ('.env', '.env.local', 'app.env.bak', 'x.env', 'X.ENV'):
            path = evidence / name
            path.write_text('QUILLMD_SECRET_KEY=synthetic-not-a-secret')
            with self.subTest(name=name):
                with NoEnvOpened() as guard, self.assertRaises(pc.Unscannable) as caught:
                    pc.leaked(root, SYNTHETIC_KEY)
                self.assertIn('environment file', str(caught.exception))
                self.assertEqual(guard.attempts, [])
            path.unlink()
        folder = evidence / 'config.env'
        folder.mkdir()
        (folder / 'inner.txt').write_text('synthetic')
        with NoEnvOpened() as guard, self.assertRaises(pc.Unscannable) as caught:
            pc.leaked(root, SYNTHETIC_KEY)
        self.assertIn('environment file', str(caught.exception))
        self.assertEqual(guard.attempts, [])


class CredentialLinkTests(unittest.TestCase):
    """Item 2: the credential is refused when it has another name (a hard link: fstat of the opened file, before any
    read) and when ANY component of its path is a symbolic link."""

    def setUp(self):
        self.root = scratch(self)
        self.folder = self.root / 'credential'
        self.folder.mkdir(mode=0o700)
        self.path = self.folder / 'anthropic-api-key'
        self.path.write_text(SYNTHETIC_KEY + '\n')
        os.chmod(self.path, 0o600)

    def refused_unread(self, path, fragment):
        with patch('os.read', side_effect=AssertionError('the credential file was read')):
            with self.assertRaises(pc.Refused) as caught:
                pc.load_credential(str(path))
        self.assertIn(fragment, str(caught.exception))

    def test_a_hard_linked_credential_is_refused_before_it_is_read(self):
        os.link(self.path, self.root / 'second-name')
        self.refused_unread(self.path, 'link')
        self.refused_unread(self.root / 'second-name', 'link')
        os.unlink(self.root / 'second-name')
        self.assertEqual(pc.load_credential(str(self.path)), SYNTHETIC_KEY)

    def test_a_symbolic_link_at_any_component_is_refused_before_anything_is_read(self):
        os.symlink(self.folder, self.root / 'alias')          # (a link to the credential's own directory)
        os.symlink(self.root, self.root / 'up')               # (a link higher up the path)
        for path in (self.root / 'alias' / 'anthropic-api-key', self.root / 'up' / 'credential' / 'anthropic-api-key'):
            with self.subTest(path=path):
                self.refused_unread(path, 'symbolic link')
        self.refused_unread(f'{self.folder}/../credential/anthropic-api-key', 'parent')
        self.assertEqual(pc.load_credential(str(self.path)), SYNTHETIC_KEY)


class RequestProcessTests(unittest.TestCase):
    """Item 4: the request process refuses BEFORE django.setup() (before it reads anything) unless QUILLMD_ENV_MANAGED
    is exactly '1' and rebuild/.env does not exist — so settings can never load a .env even if `_inner` is started
    directly."""
    CONTEXT = json.dumps({'root': '/nonexistent/root', 'declaration': '/nonexistent/declaration.md',
                          'stage': 'model_check', 'runner_commit': '0' * 40})

    def inner_refused(self, environ, fragment, env_file=False):
        from ops import sonnet5_qa as sq
        with patch.dict(os.environ, environ, clear=True), \
                patch.object(sq, 'env_file_present', return_value=env_file), \
                patch('django.setup', side_effect=AssertionError('django.setup was reached')), \
                patch('signal.signal'), patch('os.umask', return_value=0o022), \
                patch.object(pc, 'declared', side_effect=AssertionError('the declaration was read')):
            with self.assertRaises(pc.Refused) as caught:
                sq.inner()
        self.assertIn(fragment, str(caught.exception))

    def test_an_unmanaged_environment_is_refused_before_django_is_set_up(self):
        for value in (None, '0', '', 'true', ' 1', '1 ', 'yes'):
            environ = {'SONNET5_QA_CONTEXT': self.CONTEXT}
            if value is not None:
                environ['QUILLMD_ENV_MANAGED'] = value
            with self.subTest(value=value):
                self.inner_refused(environ, 'QUILLMD_ENV_MANAGED')

    def test_a_checkout_with_rebuild_env_is_refused_before_django_is_set_up(self):
        self.inner_refused({'SONNET5_QA_CONTEXT': self.CONTEXT, 'QUILLMD_ENV_MANAGED': '1'}, 'rebuild/.env', env_file=True)

    def test_env_file_present_answers_from_the_directory_entry_alone(self):
        from ops import sonnet5_qa as sq
        root = scratch(self)
        self.assertFalse(sq.env_file_present(root))
        os.symlink(root / 'nowhere', root / '.env')           # (dangling: present all the same)
        self.assertTrue(sq.env_file_present(root))


class ModelCheckJudgeTests(unittest.TestCase):
    """Item 5: each evidence item lies within its own question's notes line and contains the adopted text (evidence from
    another line is unsafe), and the review check reads the review FORM's answer inputs, never the notes panel."""

    @classmethod
    def setUpClass(cls):
        from ops import sonnet5_qa as sq
        cls.sq = sq
        cls.fields = [{'key': f'cell_{index}', 'label': label} for index, label in enumerate(sq.FORM_LABELS)]

    def span(self, value):
        start = self.sq.NOTES.index(value)
        return {'quote': value, 'start': start, 'end': start + len(value)}

    def answer(self, label, evidence=None, text=None):
        value = self.sq.EXPECTED[label] if text is None else text
        return {'text': value, 'status': 'supported',
                'evidence': [self.span(self.sq.EXPECTED[label])] if evidence is None else evidence}

    def answers(self, **overrides):
        good = {f'cell_{index}': self.answer(label) for index, label in enumerate(self.sq.FORM_LABELS)}
        good.update(overrides)
        return good

    def judged(self, answers):
        return self.sq.judge_answers(answers, self.fields, self.sq.NOTES)

    def unsafe_for(self, label, reasons, fragment):
        self.assertTrue(any(reason.startswith(label + ':') and 'unsafe' in reason and fragment in reason
                            for reason in reasons), reasons)

    def test_evidence_on_its_own_line_containing_the_answer_is_accepted(self):
        self.assertEqual(self.judged(self.answers()), [])
        whole_line = self.span('Findings: No deformity documented.')
        self.assertEqual(self.judged(self.answers(cell_1=self.answer('Findings', [whole_line]))), [])

    def test_evidence_from_another_questions_line_is_unsafe(self):
        expected = self.sq.EXPECTED
        outside = "outside this question's own notes line"
        borrowed = self.answer('Findings', [self.span(expected['History'])])
        self.unsafe_for('Findings', self.judged(self.answers(cell_1=borrowed)), outside)
        notes = self.sq.NOTES
        start, end = notes.index(expected['Findings']), notes.index('Plan:') + len('Plan:')
        straddle = {'quote': notes[start:end], 'start': start, 'end': end}
        self.unsafe_for('Findings', self.judged(self.answers(cell_1=self.answer('Findings', [straddle]))), outside)
        mixed = self.answer('Plan', [self.span(expected['Plan']), self.span(expected['Findings'])])
        self.unsafe_for('Plan', self.judged(self.answers(cell_2=mixed)), outside)

    def test_evidence_that_does_not_contain_the_adopted_answer_is_unsafe(self):
        for quote in ('Findings:', 'No deformity'):
            with self.subTest(quote=quote):
                self.unsafe_for('Findings', self.judged(self.answers(cell_1=self.answer('Findings', [self.span(quote)]))),
                                'does not contain the adopted answer')

    def page(self, values, action='/encounters/E1/save/', extra='', expected=None):
        expected = expected or self.sq.EXPECTED
        rows = ''.join(
            f'<section class="answer"><label for="answer-{field["key"]}" class="small muted">Answer for {field["label"]}'
            f'</label><textarea id="answer-{field["key"]}" name="answer_{field["key"]}" rows="4" maxlength="20000">'
            f'{html.escape(values.get(field["key"], ""))}</textarea><div class="evidence"><blockquote>'
            f'{html.escape(expected[field["label"]])}</blockquote></div></section>' for field in self.fields)
        notes = '\n'.join(f'{label}: {value}' for label, value in expected.items())
        return (f'<main><form method="post" action="{action}" data-submit-once><input type="hidden" '
                f'name="csrfmiddlewaretoken" value="synthetic"><input type="hidden" name="revision" value="3">{rows}{extra}'
                f'</form><section class="source-panel"><h2>Saved source notes</h2><div class="source-notes">'
                f'{html.escape(notes)}</div></section></main>')

    def test_the_review_check_reads_the_review_forms_answer_inputs(self):
        sq = self.sq
        draft = {f'cell_{index}': sq.EXPECTED[label] for index, label in enumerate(sq.FORM_LABELS)}

        def check(page, expected=None):
            return sq.review_form_problems(page, 'E1', self.fields, expected or sq.EXPECTED)
        self.assertEqual(check(self.page(draft)), [])
        # the notes panel and the evidence carry every documented value: empty review inputs are still a problem
        blank = check(self.page({}))
        self.assertEqual(len(blank), len(sq.FORM_LABELS), blank)
        for label in sq.FORM_LABELS:
            self.assertTrue(any(label in problem for problem in blank), blank)
        swapped = check(self.page({**draft, 'cell_1': sq.EXPECTED['Plan'], 'cell_2': sq.EXPECTED['Findings']}))
        self.assertEqual(len(swapped), 2, swapped)
        self.assertTrue(check(self.page(draft, action='/encounters/E2/save/')))             # another encounter's form
        self.assertTrue(check(self.page(draft, extra='<textarea name="answer_cell_0"></textarea>')))   # a second input
        hidden = f'<input type="hidden" name="answer_cell_0" value="{html.escape(sq.EXPECTED["History"])}">'
        self.assertTrue(check(self.page(draft, extra=hidden)))                     # (of another element type too)
        self.assertTrue(check(self.page(draft).replace('/encounters/E1/save/', '/encounters/E1/finalize/')))
        # escaped values round-trip, and the one newline HTML drops after <textarea> is dropped
        awkward = {'History': 'A & B <c> "d" \'e\'', 'Findings': sq.EXPECTED['Findings'], 'Plan': sq.EXPECTED['Plan']}
        values = {f'cell_{index}': awkward[label] for index, label in enumerate(sq.FORM_LABELS)}
        self.assertEqual(check(self.page(values, expected=awkward), awkward), [])
        leading = self.page(draft).replace('maxlength="20000">', 'maxlength="20000">\n', 1)
        self.assertEqual(check(leading), [])


W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class ExportCellTests(unittest.TestCase):
    """Item 6: an answer cell's text is ALL its descendant w:t (content controls, nested tables, hyperlinks, fields
    included); hidden text (w:vanish) or a nested table in an answer cell is a problem."""

    @classmethod
    def setUpClass(cls):
        from ops import sonnet5_qa as sq
        cls.sq = sq
        cls.form = sq.build_form()

    def export(self, mutate=None):
        from lxml import etree
        source = zipfile.ZipFile(io.BytesIO(self.form))
        root = etree.fromstring(source.read('word/document.xml'))
        rows = root.find(f'.//{W_NS}tbl').findall(f'{W_NS}tr')
        cells = {}
        for row, label in zip(rows, self.sq.FORM_LABELS):
            cell = row.findall(f'{W_NS}tc')[1]
            texts = list(cell.iter(f'{W_NS}t'))
            if texts:
                texts[0].text = self.sq.EXPECTED[label]
            else:
                run = etree.SubElement(cell.find(f'{W_NS}p'), f'{W_NS}r')
                etree.SubElement(run, f'{W_NS}t').text = self.sq.EXPECTED[label]
            cells[label] = cell
        if mutate:
            mutate(cells, etree)
        produced = io.BytesIO()
        with zipfile.ZipFile(produced, 'w', zipfile.ZIP_DEFLATED) as archive:
            for info in source.infolist():
                data = (etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                        if info.filename == 'word/document.xml' else source.read(info.filename))
                archive.writestr(info, data)
        return produced.getvalue()

    def problems(self, mutate=None):
        return self.sq.export_checks(self.form, self.export(mutate), self.sq.EXPECTED)

    @staticmethod
    def paragraph(etree, text, vanish=False):
        p = etree.Element(f'{W_NS}p')
        run = etree.SubElement(p, f'{W_NS}r')
        if vanish:
            etree.SubElement(etree.SubElement(run, f'{W_NS}rPr'), f'{W_NS}vanish')
        etree.SubElement(run, f'{W_NS}t').text = text
        return p

    def test_a_correctly_filled_export_has_no_problem(self):
        self.assertEqual(self.problems(), [])

    def test_text_in_a_content_control_or_a_nested_table_in_an_answer_cell_counts(self):
        def extra_control(cells, etree):
            sdt = etree.SubElement(cells['Findings'], f'{W_NS}sdt')
            etree.SubElement(sdt, f'{W_NS}sdtContent').append(self.paragraph(etree, 'Displaced fracture.'))
        problems = self.problems(extra_control)
        self.assertTrue(any('Findings answer is not the reviewed answer' in p for p in problems), problems)

        def nested(text):
            def mutate(cells, etree):
                table = etree.SubElement(cells['Plan'], f'{W_NS}tbl')
                cell = etree.SubElement(etree.SubElement(table, f'{W_NS}tr'), f'{W_NS}tc')
                cell.append(self.paragraph(etree, text))
                cells['Plan'].append(self.paragraph(etree, ''))     # (a cell ends with a paragraph)
            return mutate
        for text in ('Surgery booked.', ''):
            with self.subTest(text=text):
                problems = self.problems(nested(text))
                self.assertTrue(any('Plan' in p and 'nested table' in p for p in problems), problems)

    def test_hidden_text_in_an_answer_cell_is_a_problem(self):
        def hidden_answer(cells, etree):
            run = next(cells['History'].iter(f'{W_NS}r'))
            properties = run.find(f'{W_NS}rPr')
            if properties is None:
                properties = etree.Element(f'{W_NS}rPr')
                run.insert(0, properties)
            etree.SubElement(properties, f'{W_NS}vanish')

        def hidden_mark(cells, etree):
            paragraph = cells['History'].find(f'{W_NS}p')
            properties = paragraph.find(f'{W_NS}pPr')
            if properties is None:
                properties = etree.Element(f'{W_NS}pPr')
                paragraph.insert(0, properties)
            etree.SubElement(etree.SubElement(properties, f'{W_NS}rPr'), f'{W_NS}vanish')

        def hidden_extra(cells, etree):
            cells['History'].append(self.paragraph(etree, '', vanish=True))
        for mutate in (hidden_answer, hidden_mark, hidden_extra):
            with self.subTest(mutate=mutate.__name__):
                problems = self.problems(mutate)
                self.assertTrue(any('History' in p and 'hidden' in p for p in problems), problems)

    def test_run_level_wrappers_are_read_as_well(self):
        def hyperlink(cells, etree):
            link = etree.SubElement(cells['Plan'].find(f'{W_NS}p'), f'{W_NS}hyperlink')
            etree.SubElement(etree.SubElement(link, f'{W_NS}r'), f'{W_NS}t').text = ' Admit.'

        def field(cells, etree):
            simple = etree.SubElement(cells['Plan'].find(f'{W_NS}p'), f'{W_NS}fldSimple')
            etree.SubElement(etree.SubElement(simple, f'{W_NS}r'), f'{W_NS}t').text = ' Admit.'
        for mutate in (hyperlink, field):
            with self.subTest(mutate=mutate.__name__):
                problems = self.problems(mutate)
                self.assertTrue(any('Plan answer is not the reviewed answer' in p for p in problems), problems)

    def test_an_answer_wrapped_whole_in_a_content_control_is_read_and_is_a_problem(self):
        # (its text is read — it equals the answer — and since A4 the content control itself is a problem: an answer
        # cell holds plain paragraphs, runs and text only)
        def wrapped(cells, etree):
            cell = cells['Findings']
            paragraph = cell.find(f'{W_NS}p')
            sdt = etree.Element(f'{W_NS}sdt')
            content = etree.SubElement(sdt, f'{W_NS}sdtContent')
            cell.replace(paragraph, sdt)
            content.append(paragraph)
        problems = self.problems(wrapped)
        self.assertNotIn('the exported Findings answer is not the reviewed answer', problems)
        self.assertTrue(any('Findings' in p and 'w:sdt' in p for p in problems), problems)

    # ── A4: an exported answer cell may contain only w:tc, w:tcPr (and its children), w:p, w:pPr (and children), w:r,
    # w:rPr (and children) and w:t; anything else is a problem, and the text a reader sees — python-docx's cell.text —
    # must equal the answer too.
    MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'

    def wrap_run(self, tag, namespace=None):
        def mutate(cells, etree):
            run = next(cells['History'].iter(f'{W_NS}r'))
            wrapper = etree.Element(f'{{{namespace}}}{tag}' if namespace else f'{W_NS}{tag}')
            run.getparent().replace(run, wrapper)
            wrapper.append(run)
        return mutate

    def inside_run(self, tag, text=None):
        def mutate(cells, etree):
            run = next(cells['History'].iter(f'{W_NS}r'))
            extra = etree.SubElement(run, f'{W_NS}{tag}')
            if text is not None:
                extra.text = text
        return mutate

    def test_every_element_but_plain_paragraphs_runs_and_text_is_a_problem(self):
        cases = {'w:ins around the answer': self.wrap_run('ins'), 'w:del around the answer': self.wrap_run('del'),
                 'w:hyperlink around the answer': self.wrap_run('hyperlink'),
                 'w:smartTag around the answer': self.wrap_run('smartTag'),
                 'mc:AlternateContent around the answer': self.wrap_run('AlternateContent', self.MC),
                 'w:drawing in the run': self.inside_run('drawing'), 'w:fldChar in the run': self.inside_run('fldChar'),
                 'w:instrText in the run': self.inside_run('instrText', ' DATE '),
                 'w:object in the run': self.inside_run('object'), 'w:pict in the run': self.inside_run('pict'),
                 'w:br in the run': self.inside_run('br'), 'w:tab in the run': self.inside_run('tab'),
                 'w:delText in the run': self.inside_run('delText', 'removed')}
        for name, mutate in cases.items():
            with self.subTest(name=name):
                problems = self.problems(mutate)
                self.assertTrue(any('History' in p and 'may hold only' in p for p in problems), problems)

    def test_revision_and_hidden_marks_inside_properties_are_problems(self):
        def mark(tag, where):
            def mutate(cells, etree):
                paragraph = cells['History'].find(f'{W_NS}p')
                if where == 'pPr':
                    parent = etree.SubElement(paragraph, f'{W_NS}pPr')
                    paragraph.insert(0, parent)
                    parent = etree.SubElement(parent, f'{W_NS}rPr')
                else:
                    run = next(paragraph.iter(f'{W_NS}r'))
                    parent = etree.Element(f'{W_NS}rPr')
                    run.insert(0, parent)
                etree.SubElement(parent, f'{W_NS}{tag}')
            return mutate
        for tag in ('ins', 'del', 'moveFrom', 'moveTo', 'rPrChange'):
            for where in ('pPr', 'rPr'):
                with self.subTest(tag=tag, where=where):
                    problems = self.problems(mark(tag, where))
                    self.assertTrue(any('History' in p and f'w:{tag}' in p for p in problems), problems)

    def test_the_text_a_reader_sees_must_equal_the_answer(self):
        # (a w:t outside any run passes the element list and is counted by the XML reading, but Word and python-docx
        # show nothing for it: the displayed text is then not the answer)
        def text_outside_the_run(cells, etree):
            text = next(cells['Plan'].iter(f'{W_NS}t'))
            run = text.getparent()
            paragraph = run.getparent()
            run.remove(text)
            paragraph.remove(run)
            paragraph.append(text)
        problems = self.problems(text_outside_the_run)
        self.assertEqual(problems, ['the displayed text of the exported Plan answer cell is not the reviewed answer'])


class UnknownUsageTests(unittest.TestCase):
    """Item 7: a `completed` outcome whose usage does not report input_tokens or output_tokens (missing or None) counts at
    the attempt's maximum x 1.1 — unknown — never as zero tokens."""
    BOUND = Decimal(MAXIMUM) * Decimal('1.1')

    def test_a_completed_outcome_without_its_token_counts_counts_at_its_maximum(self):
        for name in ('input_tokens', 'output_tokens'):
            for missing in (True, False):
                broken = usage()
                if missing:
                    del broken[name]
                else:
                    broken[name] = None
                with self.subTest(name=name, missing=missing):
                    self.assertEqual(pc.exposure(attempt(1), {'class': 'completed', 'usage': broken}), self.BOUND)
                    with self.assertRaises(ValueError):
                        pc.usage_cost(broken, pc.Rates('2', '10', '0.20'))
        # (a provider's own zero is a count, not an unknown)
        self.assertEqual(pc.exposure(attempt(1), {'class': 'completed', 'usage': usage(output_tokens=0)}), Decimal('0.002'))

    def test_the_campaign_totals_count_it_as_unknown(self):
        campaign = pc.Campaign(declaration(), scratch(self))
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        campaign.ledger.write_attempt(attempt(1, limits=limits_record(campaign.declaration)))
        campaign.ledger.write_outcome(1, {'class': 'completed', 'usage': {**usage(), 'output_tokens': None}})
        totals = campaign.totals()
        self.assertEqual((totals['exposure'], totals['unknown']), (self.BOUND, 1))


class PinnedLimitsTests(unittest.TestCase):
    """Item 8: admission uses the TIGHTEST of the current declaration's limits and those in force when each ledger
    attempt was written (every new attempt records them); editing the declaration to raise a limit admits nothing
    more, and a ledger of another campaign or authority is refused."""

    def setUp(self):
        self.root = scratch(self)

    def campaign(self, d):
        campaign = pc.Campaign(d, self.root)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def spent(self, d, maximum='4.00', number=1, outcome=None, stage='model_check'):
        campaign = self.campaign(d)
        campaign.ledger.write_attempt(attempt(number, stage, maximum, limits=limits_record(d)))
        campaign.ledger.write_outcome(number, outcome or {'class': 'uncertain'})
        return campaign

    @staticmethod
    def restaged(d, **stage_changes):
        return tuple(dataclasses.replace(s, **stage_changes[s.id]) if s.id in stage_changes else s for s in d.stages)

    def test_every_new_attempt_can_record_the_limits_in_force(self):
        d = declaration()
        self.assertEqual(d.limits().record(), limits_record(d))
        self.assertEqual(pc.Campaign(d, self.root).limits().record(), limits_record(d))

    def test_raising_a_stage_limit_by_editing_the_declaration_admits_nothing_more(self):
        d = declaration()
        self.spent(d)                                                   # 4.40 exposed of model_check's 5.00
        raised = declaration(stages=self.restaged(d, model_check={'limit': Decimal('50.00')}), total_limit=Decimal('400'))
        campaign = pc.Campaign(raised, self.root)
        self.assertEqual(campaign.admit('model_check', '0.50'), Decimal('0.550'))
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', '0.60')                       # 4.40 + 0.66 > the 5.00 in force at attempt 1
        self.assertIn('Stage model_check limit', str(caught.exception))
        self.assertEqual(campaign.limits().stage('model_check').limit, Decimal('5.00'))

    def test_raising_the_request_count_admits_nothing_more(self):
        two = declaration(stages=self.restaged(declaration(), model_check={'max_requests': 2}))
        campaign = self.spent(two, MAXIMUM, outcome={'class': 'completed', 'usage': usage()})
        campaign.ledger.write_attempt(attempt(2, limits=limits_record(two)))
        campaign.ledger.write_outcome(2, {'class': 'completed', 'usage': usage()})
        raised = declaration(stages=self.restaged(two, model_check={'max_requests': 99}))
        with self.assertRaises(pc.Refused) as caught:
            pc.Campaign(raised, self.root).admit('model_check', MAXIMUM)
        self.assertIn('all 2 requests', str(caught.exception))

    def test_raising_the_total_admits_nothing_more(self):
        small = declaration(total_limit=Decimal('6.00'))
        campaign = self.spent(small)
        campaign.ledger.write_stage('model_check', 'passed', {})
        raised = pc.Campaign(dataclasses.replace(small, total_limit=Decimal('400')), self.root)
        self.assertEqual(raised.admit('mapping', '1.40'), Decimal('1.540'))
        with self.assertRaises(pc.Refused) as caught:
            raised.admit('mapping', '1.50')                             # 4.40 + 1.65 > the 6.00 in force
        self.assertIn('Campaign limit', str(caught.exception))

    def test_a_lower_limit_in_the_current_declaration_applies_at_once(self):
        self.spent(declaration())
        lowered = declaration(stages=self.restaged(declaration(), model_check={'limit': Decimal('4.50')}))
        with self.assertRaises(pc.Refused):
            pc.Campaign(lowered, self.root).admit('model_check', '0.50')   # 4.40 + 0.55 > 4.50

    def test_a_stage_added_or_a_prerequisite_dropped_by_an_edit_is_not_admitted(self):
        self.spent(declaration())
        added = declaration(stages=declaration().stages + (pc.Stage('extra', Decimal('5.00'), None, None),))
        with self.assertRaises(pc.Refused) as caught:
            pc.Campaign(added, self.root).admit('extra', MAXIMUM)
        self.assertIn('no limit in force', str(caught.exception))
        dropped = declaration(stages=self.restaged(declaration(), mapping={'requires': None}))
        with self.assertRaises(pc.Refused) as caught:
            pc.Campaign(dropped, self.root).admit('mapping', MAXIMUM)
        self.assertIn('requires model_check', str(caught.exception))

    def test_status_shows_a_stage_with_no_limit_in_force_without_admitting_it(self):
        from ops import sonnet5_qa as sq
        self.spent(declaration())
        added = declaration(stages=declaration().stages + (pc.Stage('extra', Decimal('5.00'), None, None),))
        out = io.StringIO()
        with patch.object(pc, 'declared', return_value=added), redirect_stdout(out):
            self.assertEqual(sq.status(root=self.root, declaration_path='/synthetic/decl.md'), 0)
        report = json.loads(out.getvalue())['stages']
        self.assertEqual((report['extra']['limit'], report['extra']['remaining'], report['extra']['max_requests']),
                         (None, None, 0))
        self.assertEqual(report['model_check']['limit'], '5.00')

    def test_a_ledger_of_another_campaign_or_authority_is_refused(self):
        self.spent(declaration())
        for changes in ({'campaign': 'another-campaign'}, {'authority_id': 'another-authority'}):
            with self.subTest(changes=changes), self.assertRaises(pc.Refused) as caught:
                pc.Campaign(declaration(**changes), self.root).admit('model_check', MAXIMUM)
            self.assertIn('another campaign or authority', str(caught.exception))

    def test_an_attempt_that_records_neither_its_limits_nor_its_declaration_is_refused(self):
        campaign = self.campaign(declaration())
        campaign.ledger.write_attempt(attempt(1))
        campaign.ledger.write_outcome(1, {'class': 'uncertain'})
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('limits in force', str(caught.exception))

    def test_recorded_limits_are_read_strictly(self):
        good = limits_record(declaration())
        broken = [
            {**good, 'total_limit_provider_usd': 40},
            {**good, 'extra': 1},
            {**good, 'total_limit_provider_usd': '-1'},
            {**good, 'stages': {**good['stages'], 'model_check': {**good['stages']['model_check'], 'max_requests': True}}},
            {**good, 'stages': {**good['stages'], 'model_check': {**good['stages']['model_check'], 'limit_provider_usd': 5}}},
            {**good, 'stages': {**good['stages'], 'model_check': {**good['stages']['model_check'], 'requires': 'none'}}},
            {**good, 'stages': {**good['stages'], 'Model Check': good['stages']['model_check']}},
            {**good, 'stages': {**good['stages'], 'mapping': {'limit_provider_usd': '25.00', 'max_requests': None}}},
            [good],
        ]
        for number, record in enumerate(broken, start=1):
            with self.subTest(record=record), self.assertRaises(pc.Refused) as caught:
                pc.Limits.from_record(record, f'Attempt {number}')
            self.assertIn('limits in force', str(caught.exception))
        self.assertEqual(pc.Limits.from_record(good, 'Attempt 1').record(), good)

    def test_an_attempt_without_limits_is_pinned_to_the_declaration_it_names(self):
        # (the live ledger's attempt 1 records declaration_sha256 and declaration_commit, and no `limits`)
        repository, path = repository_with(self, REAL_TEXT)
        first = pc.declared(path, repository=repository, out=io.StringIO())
        campaign = self.campaign(first)
        legacy = attempt(1, maximum='4.00', campaign=first.campaign, authority=first.authority_id, terms=None)
        legacy.update(declaration_sha256=first.sha256, declaration_commit=first.commit)
        campaign.ledger.write_attempt(legacy)
        campaign.ledger.write_outcome(1, {'class': 'uncertain'})
        self.assertEqual(campaign.limits().record(), limits_record(first))
        path.write_text(REAL_TEXT.replace('stage: model_check limit_provider_usd 5.00 max_requests 10',
                                          'stage: model_check limit_provider_usd 50.00 max_requests 99')
                        .replace('total_limit_provider_usd: 40.00', 'total_limit_provider_usd: 400.00'))
        git(repository, 'commit', '-q', '-a', '-m', 'Raise the limits')
        raised = pc.declared(path, repository=repository, out=io.StringIO())
        self.assertEqual((raised.stage('model_check').limit, raised.total_limit), (Decimal('50.00'), Decimal('400.00')))
        pinned = pc.Campaign(raised, self.root)
        self.assertEqual(pinned.limits().record(), limits_record(first))
        with self.assertRaises(pc.Refused) as caught:
            pinned.admit('model_check', '0.60')                         # 4.40 + 0.66 > 5.00
        self.assertIn('Stage model_check limit', str(caught.exception))
        # a declaration the attempt names but the repository does not hold at that commit: the limits are unknown
        other = scratch(self)
        stray = pc.Campaign(raised, other)
        stray.ledger.acquire()
        self.addCleanup(stray.ledger.release)
        unknown = dict(legacy, declaration_sha256='f' * 64)
        stray.ledger.write_attempt(unknown)
        stray.ledger.write_outcome(1, {'class': 'uncertain'})
        with self.assertRaises(pc.Refused) as caught:
            stray.admit('model_check', MAXIMUM)
        self.assertIn('limits in force', str(caught.exception))


class CaseVerdictTests(unittest.TestCase):
    """Item 9: the per-case verdict for the mapping and ordinary_notes stages. UNSAFE findings and CONTRACT/money
    failures stop the stage; held / missing / refused answers are usefulness outcomes, recorded per field, and never
    stop it. Anything outside the vocabulary is refused, never ignored."""
    UNSAFE = ('adopted_without_source_support', 'wrong_destination', 'wrong_side', 'wrong_denial', 'contradiction_adopted',
              'protected_area_answered', 'credential_leak', 'harmful_change_unreviewed')
    CONTRACT = ('wrong_served_model', 'stop_reason_not_end_turn', 'reconciliation', 'uncertain_outcome',
                'output_over_70_percent', 'metered_us_while_unset', 'settlement_mismatch', 'audit_failure',
                'validator_failure', 'more_than_one_request', 'request_not_captured', 'export_verification_failed',
                'response_not_captured')
    OUTCOMES = ('adopted', 'held', 'missing', 'refused')
    #: (Part C) the mapping grader's outcomes and the notes/encounter field classes that never stop by themselves
    SAFE_OUTCOMES = OUTCOMES + ('right', 'held_safe', 'wrong', 'missed', 'false_field_held', 'supported_correct',
                                'held_correct', 'over_held', 'usefulness_loss', 'recorded_not_asserted',
                                'supported_incomplete', 'clinician_correction', 'held_unadjudicated',
                                'model_relation_disagreement')
    #: (Part C) the outcomes that ARE unsafe output, and the finding each carries
    IMPLIED = {'unsupported_accepted': 'adopted_without_source_support', 'wrong_side_adopted': 'wrong_side',
               'wrong_denial_adopted': 'wrong_denial', 'contradiction_adopted': 'contradiction_adopted',
               'false_field': 'wrong_destination'}

    def test_the_vocabulary_is_exactly_the_stated_one(self):
        self.assertEqual(pc.UNSAFE_FINDINGS, frozenset(self.UNSAFE))
        self.assertEqual(pc.CONTRACT_FINDINGS, frozenset(self.CONTRACT))
        self.assertEqual(pc.FIELD_OUTCOMES, frozenset(self.SAFE_OUTCOMES) | frozenset(self.IMPLIED))
        self.assertEqual(pc.IMPLIED_FINDINGS, self.IMPLIED)
        self.assertFalse(pc.UNSAFE_FINDINGS & pc.CONTRACT_FINDINGS)

    def test_an_unsafe_field_outcome_carries_its_finding_and_stops_the_stage(self):
        for outcome, code in self.IMPLIED.items():
            with self.subTest(outcome=outcome):
                verdict = pc.classify_case({'v3_1': 'supported_correct', 'v3_2': outcome}, [])
                self.assertEqual((verdict['verdict'], verdict['stops_stage'], verdict['unsafe']), ('unsafe', True, [code]))
        for outcome in self.SAFE_OUTCOMES:
            with self.subTest(outcome=outcome):
                self.assertEqual(pc.classify_case({'v3_1': outcome}, [])['stops_stage'], False)

    def test_every_unsafe_finding_stops_the_stage(self):
        for code in self.UNSAFE:
            with self.subTest(code=code):
                verdict = pc.classify_case({'cell_0': 'adopted', 'cell_1': 'held'}, [code])
                self.assertEqual((verdict['verdict'], verdict['stops_stage'], verdict['unsafe'], verdict['contract']),
                                 ('unsafe', True, [code], []))

    def test_every_contract_or_money_failure_stops_the_stage(self):
        for code in self.CONTRACT:
            with self.subTest(code=code):
                verdict = pc.classify_case({'cell_0': 'adopted'}, [code])
                self.assertEqual((verdict['verdict'], verdict['stops_stage'], verdict['unsafe'], verdict['contract']),
                                 ('contract', True, [], [code]))

    def test_unsafe_wins_over_a_contract_failure_and_both_are_kept(self):
        for unsafe, contract in itertools.product(self.UNSAFE, self.CONTRACT):
            with self.subTest(unsafe=unsafe, contract=contract):
                verdict = pc.classify_case({}, [contract, unsafe, contract])
                self.assertEqual((verdict['verdict'], verdict['stops_stage'], verdict['unsafe'], verdict['contract']),
                                 ('unsafe', True, [unsafe], [contract]))

    def test_held_missing_and_refused_answers_never_stop_the_stage(self):
        for combination in itertools.product(self.OUTCOMES, repeat=3):
            fields = {f'cell_{index}': outcome for index, outcome in enumerate(combination)}
            with self.subTest(fields=combination):
                verdict = pc.classify_case(fields, [])
                self.assertEqual((verdict['verdict'], verdict['stops_stage']), ('usefulness', False))
                self.assertEqual(verdict['fields'], fields)
                self.assertEqual(verdict['usefulness'], {outcome: combination.count(outcome) for outcome in set(combination)})
        self.assertEqual(pc.classify_case({}, [])['verdict'], 'usefulness')
        # (usefulness is recorded even when the case stops)
        stopped = pc.classify_case({'cell_0': 'missing'}, ['wrong_side'])
        self.assertEqual((stopped['fields'], stopped['usefulness']['missing']), ({'cell_0': 'missing'}, 1))

    def test_anything_outside_the_vocabulary_is_refused_never_ignored(self):
        for bad in ('', 'wrong-side', 'WRONG_SIDE', 'held', 'unsafe', None, 3, ('wrong_side',)):
            with self.subTest(finding=bad), self.assertRaises(pc.Refused):
                pc.classify_case({}, [bad])
        for bad in ('', 'supported', 'ADOPTED', None, 'unsafe', 'wrong_side', 1):
            with self.subTest(outcome=bad), self.assertRaises(pc.Refused):
                pc.classify_case({'cell_0': bad}, [])
        for fields, findings in (([('cell_0', 'held')], []), ({}, 'wrong_side'), ({3: 'held'}, []), ({}, None)):
            with self.subTest(fields=fields, findings=findings), self.assertRaises(pc.Refused):
                pc.classify_case(fields, findings)

    def test_the_verdict_is_pure(self):
        fields, findings = {'cell_0': 'held', 'cell_1': 'adopted'}, ['audit_failure']
        first = pc.classify_case(fields, findings)
        self.assertEqual(first, pc.classify_case(dict(fields), list(findings)))
        self.assertEqual((fields, findings), ({'cell_0': 'held', 'cell_1': 'adopted'}, ['audit_failure']))
        first['fields']['cell_0'] = 'adopted'
        self.assertEqual(fields['cell_0'], 'held')


def failed_record(stage, number=None):
    record = {'stage': stage, 'decision': 'failed', 'reasons': ['synthetic'], 'recorded_at': pc.now()}
    if number is not None:
        record['number'] = number
    return record


class StageDecisionTests(unittest.TestCase):
    """Item 10, record level: stage decisions are numbered (failed-1, reopened-1, failed-2 …), the existing unnumbered
    `stage-<id>-passed.json` stays valid, and a sequence that is out of order is refused rather than read."""

    def setUp(self):
        self.root = scratch(self)
        self.ledger = pc.Ledger(self.root / 'ledger').acquire()
        self.addCleanup(self.ledger.release)

    def names(self):
        return sorted(name for name in os.listdir(self.ledger.dir) if name.startswith('stage-'))

    def test_decisions_are_numbered_failed_reopened_failed(self):
        self.ledger.write_stage('mapping', 'failed', {'reasons': ['first']})
        self.assertEqual(self.names(), ['stage-mapping-failed-1.json'])
        self.assertEqual(self.ledger.stage_state('mapping')['state'], 'failed')
        for kind in ('failed', 'passed'):
            with self.assertRaises(pc.Refused):
                self.ledger.write_stage('mapping', kind, {})
        for number in (0, 2):
            with self.assertRaises(pc.Refused):
                self.ledger.write_reopen('mapping', number, {'ledger_attempts': 0})       # (not failure 1's number)
        with self.assertRaises(pc.Refused):
            self.ledger.write_reopen('mapping', 1, {})                                   # (the ledger it read, unrecorded)
        self.ledger.write_reopen('mapping', 1, {'ledger_attempts': 0})
        with self.assertRaises(pc.Refused):
            self.ledger.write_reopen('mapping', 1, {'ledger_attempts': 0})
        state = self.ledger.stage_state('mapping')
        self.assertEqual((state['state'], state['failures'], state['reopenings'], state['open_since']), ('open', 1, 1, 0))
        self.ledger.write_stage('mapping', 'failed', {'reasons': ['second']})
        self.assertEqual(self.ledger.stage_record('mapping', 'failed')['reasons'], ['second'])
        self.ledger.write_reopen('mapping', 2, {'ledger_attempts': 3})
        self.assertEqual(self.ledger.stage_state('mapping')['open_since'], 3)
        self.ledger.write_stage('mapping', 'passed', {})
        self.assertEqual(self.names(), ['stage-mapping-failed-1.json', 'stage-mapping-failed-2.json',
                                        'stage-mapping-passed.json', 'stage-mapping-reopened-1.json',
                                        'stage-mapping-reopened-2.json'])
        self.assertEqual(self.ledger.stage_state('mapping')['state'], 'passed')
        self.assertEqual(json.loads((self.ledger.dir / 'stage-mapping-failed-2.json').read_text())['number'], 2)
        with self.assertRaises(pc.Refused):
            self.ledger.write_reopen('mapping', 3, {'ledger_attempts': 3})

    def test_the_existing_unnumbered_records_stay_valid(self):
        pc.write_new(self.ledger.dir / 'stage-model_check-passed.json',
                     {'attempt': 1, 'checks': ['served model'], 'decision': 'passed', 'manifest_sha256': '3' * 64,
                      'recorded_at': '2026-09-29T00:56:58.176674+00:00', 'stage': 'model_check'})
        pc.write_new(self.ledger.dir / 'stage-mapping-failed.json', failed_record('mapping'))
        self.assertEqual(self.ledger.stage_state('model_check')['state'], 'passed')
        self.assertEqual((self.ledger.stage_state('mapping')['state'], self.ledger.stage_state('mapping')['failures']),
                         ('failed', 1))
        self.ledger.write_reopen('mapping', 1, {'ledger_attempts': 0})
        self.assertEqual(self.ledger.stage_state('mapping')['state'], 'open')
        self.assertEqual(self.ledger.stage_state('ordinary_notes')['state'], 'open')

    def test_records_out_of_sequence_are_refused(self):
        reopened = {'stage': 'x', 'decision': 'reopened', 'number': 1, 'ledger_attempts': 0}
        cases = {
            'a reopening without a failure': [('stage-x-reopened-1.json', reopened)],
            'a second failure without a reopening': [('stage-x-failed-1.json', failed_record('x', 1)),
                                                     ('stage-x-failed-2.json', failed_record('x', 2))],
            'the first failure twice': [('stage-x-failed.json', failed_record('x')),
                                        ('stage-x-failed-1.json', failed_record('x', 1))],
            'a pass after a failure without a reopening': [('stage-x-failed-1.json', failed_record('x', 1)),
                                                           ('stage-x-passed.json', {'stage': 'x', 'decision': 'passed'})],
            'a numbered pass': [('stage-x-passed-1.json', {'stage': 'x', 'decision': 'passed', 'number': 1})],
            'numbering that does not start at 1': [('stage-x-failed-2.json', failed_record('x', 2))],
            'a record labelled with another number': [('stage-x-failed-1.json', failed_record('x', 2))],
            "another stage's record": [('stage-x-failed-1.json', failed_record('y', 1))],
            'an unnumbered reopening': [('stage-x-failed-1.json', failed_record('x', 1)),
                                        ('stage-x-reopened.json', {k: v for k, v in reopened.items() if k != 'number'})],
            'another decision': [('stage-x-failed-1.json', {**failed_record('x', 1), 'decision': 'passed'})],
            'an unreadable reopening': [('stage-x-failed-1.json', failed_record('x', 1)),
                                        ('stage-x-reopened-1.json', {**reopened, 'ledger_attempts': 'many'})],
        }
        for case, records in cases.items():
            with self.subTest(case=case):
                ledger = pc.Ledger(scratch(self) / 'ledger').acquire()
                self.addCleanup(ledger.release)
                for name, document in records:
                    pc.write_new(ledger.dir / name, document)
                with self.assertRaises(pc.Refused):
                    ledger.stage_state('x')


#: The runner and engine files a synthetic reopening watches (A2): the synthetic runner and an engine file.
WATCHED = ('rebuild/ops/runner.py', 'rebuild/core/engine.py')


class ReopenTests(unittest.TestCase):
    """Item 10: a failed stage is reopened ONLY by `reopen --stage <id> --diagnosis <path>`: a committed, unmodified
    diagnosis naming the failed attempts and the repair commit; a runner that is not the failed one and contains the
    repair; money and requests left under the stage's OWN limit. It writes a write-once `stage-<id>-reopened-<n>.json`,
    after which the stage is admitted again within its remaining limit; without one a failed stage stays refused."""

    def setUp(self):
        self.repo, self.path = repository_with(self, REAL_TEXT)
        self.base = self.head()
        self.failed_runner = self.commit_file('rebuild/ops/runner.py', 'version = 1\n', 'Runner v1')
        self.declaration = pc.declared(self.path, repository=self.repo, out=io.StringIO())
        self.root = scratch(self)
        self.campaign = pc.Campaign(self.declaration, self.root, watched_files=WATCHED)
        self.campaign.ledger.acquire()
        self.addCleanup(self.campaign.ledger.release)

    def hashes(self, commit):
        """What a runner at `commit` records (A2): the sha256 of each watched file there, None when it is absent."""
        found = {}
        for relative in WATCHED:
            blob = git(self.repo, 'cat-file', 'blob', f'{commit}:{relative}', check=False)
            found[relative] = hashlib.sha256(blob.stdout).hexdigest() if blob.returncode == 0 else None
        return found

    def head(self):
        return git(self.repo, 'rev-parse', 'HEAD').stdout.decode().strip()

    def commit_file(self, relative, text, message):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        git(self.repo, 'add', '--', relative)
        git(self.repo, 'commit', '-q', '-m', message)
        return self.head()

    def failed_attempt(self, number, stage='model_check', runner=None, maximum='0.50', limits=None,
                       engine_files='at-runner'):
        d = self.declaration
        record = attempt(number, stage, maximum, campaign=d.campaign, authority=d.authority_id,
                         limits=limits or limits_record(d), runner_commit=runner or self.failed_runner,
                         terms=terms_record(d), engine_files=self.hashes(runner or self.failed_runner)
                         if engine_files == 'at-runner' else engine_files)
        self.campaign.ledger.write_attempt(record)
        self.campaign.ledger.write_outcome(number, {'class': 'uncertain'})
        self.campaign.ledger.write_stage(stage, 'failed', {'attempt': number, 'reasons': ['synthetic failure']})

    def diagnosis(self, repair, attempts='1', stage='model_check', name='diagnosis-1.md', commit=True):
        relative = f'docs/rebuild/{name}'
        text = (f'# Offline diagnosis\n\nreopen_stage: {stage}\nfailed_attempts: {attempts}\nrepair_commit: {repair}\n'
                'The synthetic failure was diagnosed offline and repaired.\n')
        if commit:
            self.commit_file(relative, text, f'Diagnosis {name}')
        else:
            (self.repo / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / relative).write_text(text)
        return self.repo / relative

    def repaired(self, name='diagnosis-1.md', attempts='1'):
        repair = self.commit_file('rebuild/ops/runner.py', f'version = 2  # {name}\n', 'Repair the runner')
        diagnosis = self.diagnosis(repair, attempts=attempts, name=name)
        return repair, diagnosis, self.head()

    def reopened(self):
        return sorted(name for name in os.listdir(self.campaign.ledger.dir) if '-reopened-' in name)

    def refused(self, fragment, stage='model_check', diagnosis=None, runner=None):
        with self.assertRaises(pc.Refused) as caught:
            self.campaign.reopen(stage, diagnosis, runner_commit=runner)
        self.assertIn(fragment, str(caught.exception))

    def test_a_failed_stage_stays_refused_without_a_reopen(self):
        self.failed_attempt(1)
        _, _, runner = self.repaired()
        with self.assertRaises(pc.Refused) as caught:
            self.campaign.admit('model_check', MAXIMUM, runner_commit=runner)
        self.assertIn('failed', str(caught.exception))
        self.assertEqual(self.reopened(), [])

    def test_a_committed_diagnosis_reopens_the_stage_within_its_own_remaining_limit(self):
        self.failed_attempt(1)
        repair, diagnosis, runner = self.repaired()
        record = self.campaign.reopen('model_check', diagnosis, runner_commit=runner)
        self.assertEqual(self.reopened(), ['stage-model_check-reopened-1.json'])
        stored = json.loads((self.campaign.ledger.dir / 'stage-model_check-reopened-1.json').read_text())
        self.assertEqual(stored, json.loads(json.dumps(record, default=str)))
        self.assertEqual((stored['number'], stored['failed_attempts'], stored['repair_commit'], stored['runner_commit'],
                          stored['ledger_attempts'], stored['decision']), (1, [1], repair, runner, 1, 'reopened'))
        self.assertEqual(stored['diagnosis']['sha256'], hashlib.sha256(diagnosis.read_bytes()).hexdigest())
        self.assertEqual(stored['diagnosis']['path'], 'docs/rebuild/diagnosis-1.md')
        with self.assertRaises(FileExistsError):
            pc.write_new(self.campaign.ledger.dir / 'stage-model_check-reopened-1.json', {})
        # admitted again, within what is left of model_check's own $5.00 (0.55 exposed by attempt 1)
        self.assertEqual(self.campaign.ledger.undecided(), {})          # (attempt 1 stays decided by failure 1)
        self.assertEqual(self.campaign.admit('model_check', '4.00', runner_commit=runner), Decimal('4.400'))
        with self.assertRaises(pc.Refused):
            self.campaign.admit('model_check', '4.10', runner_commit=runner)     # 0.55 + 4.51 > 5.00
        # a second failure is failed-2, refused again; the first diagnosis cannot reopen it
        self.failed_attempt(2, runner=runner)
        self.assertTrue((self.campaign.ledger.dir / 'stage-model_check-failed-2.json').is_file())
        with self.assertRaises(pc.Refused):
            self.campaign.admit('model_check', MAXIMUM, runner_commit=runner)
        self.refused('names attempts', diagnosis=diagnosis, runner=runner)
        # a second diagnosis and a second repair reopen it again
        second_repair, second, second_runner = self.repaired('diagnosis-2.md', attempts='2')
        self.assertEqual(self.campaign.reopen('model_check', second, runner_commit=second_runner)['number'], 2)
        self.assertEqual(self.reopened(), ['stage-model_check-reopened-1.json', 'stage-model_check-reopened-2.json'])
        self.assertEqual(self.campaign.ledger.stage_state('model_check')['open_since'], 2)

    def test_an_attempt_left_open_after_a_reopen_fails_the_stage_again(self):
        from ops import sonnet5_qa as sq
        self.failed_attempt(1)
        _, diagnosis, runner = self.repaired()
        self.campaign.reopen('model_check', diagnosis, runner_commit=runner)
        self.assertEqual(sq.settle_open_stages(self.campaign), {'recovered': [], 'failed_stages': []})
        d = self.declaration
        self.campaign.ledger.write_attempt(attempt(2, campaign=d.campaign, authority=d.authority_id,
                                                   limits=limits_record(d), runner_commit=runner, terms=terms_record(d)))
        self.assertEqual(self.campaign.ledger.undecided(), {'model_check': [2]})
        self.assertEqual(sq.settle_open_stages(self.campaign), {'recovered': [2], 'failed_stages': ['model_check']})
        failure = self.campaign.ledger.stage_record('model_check', 'failed')
        self.assertEqual((failure['number'], failure['attempts']), (2, [2]))
        self.assertEqual(self.campaign.ledger.stage_state('model_check')['state'], 'failed')
        self.assertEqual(self.campaign.ledger.undecided(), {})

    def test_the_reopened_stage_admits_only_a_runner_that_contains_the_repair(self):
        self.failed_attempt(1)
        repair, diagnosis, runner = self.repaired()
        self.campaign.reopen('model_check', diagnosis, runner_commit=runner)
        for other in (None, self.failed_runner, self.base):
            with self.subTest(runner=other), self.assertRaises(pc.Refused):
                self.campaign.admit('model_check', MAXIMUM, runner_commit=other)
        self.assertEqual(self.campaign.admit('model_check', MAXIMUM, runner_commit=runner), Decimal(MAXIMUM) * Decimal('1.1'))

    def test_every_condition_must_hold_and_a_refusal_writes_nothing(self):
        self.failed_attempt(1)
        repair, diagnosis, runner = self.repaired()
        tree = git(self.repo, 'rev-parse', 'HEAD^{tree}').stdout.decode().strip()
        elsewhere = git(self.repo, 'commit-tree', tree, '-p', self.failed_runner, '-m', 'Side repair').stdout.decode().strip()
        untracked = self.diagnosis(repair, name='untracked.md', commit=False)
        edited = self.diagnosis(repair, name='edited.md')
        edited.write_text(edited.read_text() + 'An uncommitted addition.\n')
        outside = scratch(self) / 'diagnosis.md'
        outside.write_text(diagnosis.read_text())
        env_named = self.diagnosis(repair, name='diagnosis.env.md')
        cases = [
            ('tracked, committed and unmodified', untracked, runner),
            ('tracked, committed and unmodified', edited, runner),
            ('in this checkout', outside, runner),
            ('environment file', env_named, runner),
            ('reopen_stage', self.diagnosis(repair, stage='mapping', name='other-stage.md'), runner),
            ('names attempts', self.diagnosis(repair, attempts='2', name='wrong-attempt.md'), runner),
            ('names attempts', self.diagnosis(repair, attempts='1, 2', name='extra-attempt.md'), runner),
            ('failed_attempts', self.diagnosis(repair, attempts='', name='no-attempt.md'), runner),
            ('repair_commit', self.diagnosis('', name='no-repair.md'), runner),
            ('repair commit', self.diagnosis('0' * 40, name='unknown-repair.md'), runner),
            ('already in the failed runner', self.diagnosis(self.base, name='old-repair.md'), runner),
            ('does not contain the repair', self.diagnosis(elsewhere, name='side-repair.md'), runner),
            ('the commit that failed', diagnosis, self.failed_runner),
            ('full commit', diagnosis, runner[:12]),
            ('full commit', diagnosis, None),
        ]
        for fragment, path, commit in cases:
            with self.subTest(fragment=fragment, path=path.name, runner=commit):
                self.refused(fragment, diagnosis=path, runner=commit)
        self.refused('not a commit in this checkout', diagnosis=diagnosis, runner='e' * 40)
        self.refused('--diagnosis', diagnosis=None, runner=runner)
        self.refused('has not failed', stage='mapping', diagnosis=diagnosis, runner=runner)
        self.refused('names no stage', stage='nonexistent', diagnosis=diagnosis, runner=runner)
        self.campaign.ledger.write_stage('ordinary_notes', 'failed', {'reasons': ['failed without an attempt']})
        self.refused('no attempt of its own', stage='ordinary_notes',
                     diagnosis=self.diagnosis(repair, stage='ordinary_notes', name='no-attempt-stage.md'), runner=runner)
        self.assertEqual(self.reopened(), [])
        self.campaign.ledger.write_stop({'reason': 'synthetic stop'})
        self.refused('stopped', diagnosis=diagnosis, runner=runner)
        self.assertEqual(self.reopened(), [])

    def test_a_failed_attempt_without_a_runner_commit_or_a_declaration_without_a_checkout_refuses(self):
        d = self.declaration
        self.campaign.ledger.write_attempt(attempt(1, campaign=d.campaign, authority=d.authority_id,
                                                   limits=limits_record(d), terms=terms_record(d)))
        self.campaign.ledger.write_outcome(1, {'class': 'uncertain'})
        self.campaign.ledger.write_stage('model_check', 'failed', {'attempt': 1, 'reasons': ['synthetic failure']})
        _, diagnosis, runner = self.repaired()
        self.refused('records no runner commit', diagnosis=diagnosis, runner=runner)
        unrooted = pc.Campaign(dataclasses.replace(d, repository=''), self.root, watched_files=WATCHED)
        self.campaign.ledger.release()
        unrooted.ledger.acquire()
        self.addCleanup(unrooted.ledger.release)
        with self.assertRaises(pc.Refused) as caught:
            unrooted.reopen('model_check', diagnosis, runner_commit=runner)
        self.assertIn('no checkout', str(caught.exception))
        self.assertEqual(self.reopened(), [])

    def test_no_money_left_under_the_stages_own_limit_refuses_whatever_other_stages_have(self):
        self.failed_attempt(1, maximum='4.60')                                    # counted at 5.06: model_check's $5.00 is gone
        _, diagnosis, runner = self.repaired()
        self.assertEqual(self.campaign.limits().stage('mapping').limit, Decimal('25.00'))
        self.refused('no money left', diagnosis=diagnosis, runner=runner)
        self.assertEqual(self.reopened(), [])

    def test_no_request_left_under_the_stages_own_count_refuses(self):
        limits = limits_record(self.declaration)
        limits['stages']['model_check']['max_requests'] = 1             # (pinned by the attempt: the tightest applies)
        self.failed_attempt(1, limits=limits)
        _, diagnosis, runner = self.repaired()
        self.refused('all 1 requests', diagnosis=diagnosis, runner=runner)
        self.assertEqual(self.reopened(), [])

    def test_the_reopen_command(self):
        from ops import sonnet5_qa as sq
        self.failed_attempt(1)
        _, diagnosis, runner = self.repaired()
        self.campaign.ledger.release()
        with patch.object(sq, 'LIVE_ROOT', self.root), patch.object(sq, 'DECLARATION', self.path), \
                patch.object(sq, 'REPOSITORY', self.repo), patch.object(sq, 'REBUILD', self.repo / 'rebuild'), \
                patch.object(sq, 'WATCHED_FILES', WATCHED), patch('sys.stderr', io.StringIO()):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(sq.main(['reopen', '--stage', 'model_check', '--diagnosis', str(diagnosis)]), 0)
            self.assertEqual((json.loads(out.getvalue())['number'], json.loads(out.getvalue())['runner_commit']), (1, runner))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(sq.main(['reopen', '--stage', 'model_check', '--diagnosis', str(diagnosis)]), 2)
                self.assertEqual(sq.main(['reopen', '--stage', 'model_check']), 2)
        self.assertEqual(self.reopened(), ['stage-model_check-reopened-1.json'])

    # ── refutation F2: a stage the stage runner resumes from its failure record (mapping, ordinary_notes) is reopened
    # only when that record establishes something to send. Before, the reopening was written first and the runner
    # refused afterwards, leaving the stage OPEN with nothing it could ever send, no second reopening possible and
    # nothing that would fail it again. Now the reopening itself refuses, before anything is written.

    def failed_notes_run(self, summary):
        """Attempt 1 (notes:N01:default, completed), then ordinary_notes failure 1 with `summary` (None: none)."""
        d = self.declaration
        record = attempt(1, 'ordinary_notes', '0.50', campaign=d.campaign, authority=d.authority_id,
                         limits=limits_record(d), runner_commit=self.failed_runner, terms=terms_record(d),
                         engine_files=self.hashes(self.failed_runner))
        record['send'] = {'id': 'notes:N01:default'}
        self.campaign.ledger.write_attempt(record)
        self.campaign.ledger.write_outcome(1, {'class': 'completed', 'usage': usage()})
        document = {'reasons': ['synthetic failure']}
        if summary is not None:
            document['summary'] = summary
        self.campaign.ledger.write_stage('ordinary_notes', 'failed', document)

    def reopen_command(self, stage, diagnosis):
        from ops import sonnet5_qa as sq
        self.campaign.ledger.release()
        err = io.StringIO()
        with patch.object(sq, 'LIVE_ROOT', self.root), patch.object(sq, 'DECLARATION', self.path), \
                patch.object(sq, 'REPOSITORY', self.repo), patch.object(sq, 'REBUILD', self.repo / 'rebuild'), \
                patch.object(sq, 'WATCHED_FILES', WATCHED), patch('sys.stderr', err):
            out = io.StringIO()
            with redirect_stdout(out):
                code = sq.main(['reopen', '--stage', stage, '--diagnosis', str(diagnosis)])
        self.campaign.ledger.acquire()
        return code, out.getvalue(), err.getvalue()

    def test_a_stage_runner_reopening_with_nothing_it_could_send_is_refused_before_it_is_written(self):
        from ops import sonnet5_stages as st
        plan = [s.id for s in st.plan_sends('ordinary_notes', st.frozen_inputs())]
        cases = {
            'no summary (an interruption that ended the process, or a settled run)': (None, 'no readable list'),
            'the last planned send stopped the stage': ({'plan': plan, 'sends': [], 'not_sent': []}, 'no remainder'),
        }
        for name, (summary, fragment) in cases.items():
            with self.subTest(name=name):
                self.campaign.ledger.release()
                self.root = scratch(self)
                self.campaign = pc.Campaign(self.declaration, self.root, watched_files=WATCHED)
                self.campaign.ledger.acquire()
                self.failed_notes_run(summary)
                tag = abs(hash(name))
                repair = self.commit_file('rebuild/ops/runner.py', f'version = 2  # {tag}\n', 'Repair the runner')
                diagnosis = self.diagnosis(repair, stage='ordinary_notes', name=f'notes-{tag}.md')
                code, _, err = self.reopen_command('ordinary_notes', diagnosis)
                self.assertEqual(code, 2, err)
                self.assertIn(fragment, err)
                self.assertEqual(self.reopened(), [])
                self.assertEqual(self.campaign.ledger.stage_state('ordinary_notes')['state'], 'failed')

    def test_a_stage_runner_reopening_records_the_remainder_it_establishes(self):
        from ops import sonnet5_stages as st
        plan = [s.id for s in st.plan_sends('ordinary_notes', st.frozen_inputs())]
        self.failed_notes_run({'plan': plan, 'sends': [], 'not_sent': plan[1:]})
        repair = self.commit_file('rebuild/ops/runner.py', 'version = 2\n', 'Repair the runner')
        diagnosis = self.diagnosis(repair, stage='ordinary_notes', name='notes-diagnosis.md')
        code, out, err = self.reopen_command('ordinary_notes', diagnosis)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['remainder'], plan[1:])
        self.assertEqual(self.reopened(), ['stage-ordinary_notes-reopened-1.json'])

    def test_a_reopening_is_refused_when_its_remainder_cannot_be_established(self):
        self.failed_attempt(1)
        _, diagnosis, runner = self.repaired()

        def nothing():
            raise pc.Refused('Stage model_check failure 1 left no send unsent; there is no remainder to send.')
        with self.assertRaises(pc.Refused) as caught:
            self.campaign.reopen('model_check', diagnosis, runner_commit=runner, remainder=nothing)
        self.assertIn('no remainder', str(caught.exception))
        self.assertEqual(self.reopened(), [])
        record = self.campaign.reopen('model_check', diagnosis, runner_commit=runner, remainder=lambda: ['a', 'b'])
        self.assertEqual(record['remainder'], ['a', 'b'])
        self.assertEqual(self.reopened(), ['stage-model_check-reopened-1.json'])

    # ── A2: a reopening also requires that at least one runner or engine file (sonnet5_qa.WATCHED_FILES: ENGINE_FILES
    # and the stage runner files) DIFFERS between each failed attempt's recorded hashes and the reopening runner's
    # checkout, and that the repair commit itself TOUCHES at least one of them. A repair that changed only a document,
    # or whose change was undone again, reopens nothing.

    def test_a_repair_that_touches_no_runner_or_engine_file_refuses(self):
        self.failed_attempt(1)
        self.commit_file('rebuild/ops/runner.py', 'version = 2\n', 'An unnamed runner change')
        repair = self.commit_file('docs/rebuild/notes.md', 'A note.\n', 'A documentation-only repair')
        diagnosis = self.diagnosis(repair)
        self.refused('touches no runner or engine file', diagnosis=diagnosis, runner=self.head())
        self.assertEqual(self.reopened(), [])

    def test_a_repair_undone_again_leaves_no_file_different_and_refuses(self):
        self.failed_attempt(1)
        repair = self.commit_file('rebuild/ops/runner.py', 'version = 2\n', 'Repair the runner')
        self.commit_file('rebuild/ops/runner.py', 'version = 1\n', 'Undo the repair')
        diagnosis = self.diagnosis(repair)
        self.refused('runner or engine file differs', diagnosis=diagnosis, runner=self.head())
        self.assertEqual(self.reopened(), [])

    def test_a_failed_attempt_that_records_no_file_hashes_refuses(self):
        for recorded in (None, {}, {WATCHED[0]: 'f' * 64}):
            with self.subTest(recorded=recorded):
                root = scratch(self)
                self.campaign.ledger.release()
                self.campaign = pc.Campaign(self.declaration, root, watched_files=WATCHED)
                self.campaign.ledger.acquire()
                self.failed_attempt(1, engine_files=recorded)
                _, diagnosis, runner = self.repaired(name=f'diagnosis-{len(recorded or {})}-{recorded is None}.md')
                self.refused('records no hash', diagnosis=diagnosis, runner=runner)

    def test_a_campaign_that_watches_no_file_refuses(self):
        self.failed_attempt(1)
        _, diagnosis, runner = self.repaired()
        self.campaign.ledger.release()
        unwatched = pc.Campaign(self.declaration, self.root)
        unwatched.ledger.acquire()
        self.addCleanup(unwatched.ledger.release)
        with self.assertRaises(pc.Refused) as caught:
            unwatched.reopen('model_check', diagnosis, runner_commit=runner)
        self.assertIn('watches no runner or engine file', str(caught.exception))
        self.assertEqual(self.reopened(), [])

    def test_money_left_for_a_reopening_is_counted_at_the_pinned_rates(self):
        # attempt 1 records rates of $1/$5, but the ledger pinned $2/$10: 2,600,000 input tokens are $5.20, not $2.60
        d = self.declaration
        record = attempt(1, 'model_check', '0.50', campaign=d.campaign, authority=d.authority_id,
                         limits=limits_record(d), runner_commit=self.failed_runner, terms=terms_record(d),
                         engine_files=self.hashes(self.failed_runner))
        record['rates'] = {'input': '1', 'output': '5', 'cached': '0.10'}
        self.campaign.ledger.write_attempt(record)
        self.campaign.ledger.write_outcome(1, {'class': 'completed', 'usage': usage(input_tokens=2600000, output_tokens=0)})
        self.campaign.ledger.write_stage('model_check', 'failed', {'attempt': 1, 'reasons': ['synthetic failure']})
        _, diagnosis, runner = self.repaired()
        self.refused('no money left', diagnosis=diagnosis, runner=runner)
        self.assertEqual(self.reopened(), [])

    def test_only_this_failures_attempts_must_show_the_repair(self):
        # (an earlier failure, reopened before attempts recorded file hashes, does not block a later reopening)
        d = self.declaration
        self.failed_attempt(1, engine_files=None)
        first_repair, _, first_runner = self.repaired()
        self.campaign.ledger.write_reopen('model_check', 1, {'ledger_attempts': 1, 'repair_commit': first_repair})
        self.failed_attempt(2, runner=first_runner)
        repair, diagnosis, runner = self.repaired('diagnosis-2.md', attempts='2')
        record = self.campaign.reopen('model_check', diagnosis, runner_commit=runner)
        self.assertEqual((record['number'], record['failed_attempts'], record['repair_commit']), (2, [2], repair))

    def test_a_repair_to_the_engine_alone_reopens(self):
        self.failed_attempt(1)
        repair = self.commit_file('rebuild/core/engine.py', 'engine = 2\n', 'Repair the engine')
        diagnosis = self.diagnosis(repair)
        record = self.campaign.reopen('model_check', diagnosis, runner_commit=self.head())
        self.assertEqual((record['number'], record['repair_commit']), (1, repair))
        self.assertEqual(record['changed_files'], ['rebuild/core/engine.py'])
        self.assertEqual(record['repair_touches'], ['rebuild/core/engine.py'])

    def test_the_sonnet5_runner_watches_every_engine_file_and_the_stage_runner(self):
        from ops import sonnet5_qa as sq
        self.assertEqual(set(sq.WATCHED_FILES) >= {'rebuild/' + name for name in sq.ENGINE_FILES}, True)
        self.assertIn('rebuild/ops/sonnet5_stages.py', sq.WATCHED_FILES)


class PinnedTermsTests(unittest.TestCase):
    """A1 (RR-MONEY-1): the RATES are pinned as well as the limits — with the model, thinking, effort, inference
    geography and every pricing version — to those in force when the ledger's FIRST attempt was written (the terms it
    records; for a legacy first attempt that records none, those of the declaration blob it names by sha256 at its
    declaration_commit). Every outcome's exposure is costed at the PINNED rates, and admission refuses while the current
    declaration states any other term: an edited declaration never changes what is admitted or how it is costed."""

    def setUp(self):
        self.root = scratch(self)

    def campaign(self, d):
        campaign = pc.Campaign(d, self.root)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def spent(self, d, number=1, terms='synthetic'):
        campaign = self.campaign(d)
        campaign.ledger.write_attempt(attempt(number, limits=limits_record(d), terms=terms))
        campaign.ledger.write_outcome(number, {'class': 'completed', 'usage': usage()})     # 1000 in, 200 out
        return campaign

    def test_every_new_attempt_records_the_terms_in_force(self):
        d = declaration()
        self.assertEqual(d.terms().record(), terms_record(d))
        self.assertEqual(pc.Campaign(d, self.root).pinned_terms().record(), terms_record(d))

    def test_an_edited_rate_changes_neither_admission_nor_the_cost_of_an_outcome(self):
        d = declaration()
        self.spent(d)
        for rates in (pc.Rates('1', '5', '0.10'), pc.Rates('4', '20', '0.40'), pc.Rates('2', '10', '0.2')):
            with self.subTest(rates=rates):
                edited = pc.Campaign(dataclasses.replace(d, rates=rates), self.root)
                # costed at the pinned $2/$10 (1000 x 2 + 200 x 10 per million), never at the edited rates
                self.assertEqual(edited.totals()['exposure'], Decimal('0.004'))
                self.assertEqual(edited.totals('model_check')['exposure'], Decimal('0.004'))
                self.assertEqual(edited.pinned_terms().record(), terms_record(d))
                with self.assertRaises(pc.Refused) as caught:
                    edited.admit('model_check', MAXIMUM)
                self.assertIn('rates', str(caught.exception))
        self.assertEqual(pc.Campaign(d, self.root).admit('model_check', MAXIMUM), Decimal(MAXIMUM) * Decimal('1.1'))

    def test_every_outcome_is_costed_at_the_pinned_rates_whatever_the_attempt_itself_says(self):
        # (an attempt carries its own `rates` too; admission and every total cost it at the PINNED rates)
        d = declaration()
        campaign = self.campaign(d)
        record = attempt(1, limits=limits_record(d))
        record['rates'] = {'input': '1', 'output': '5', 'cached': '0.10'}
        campaign.ledger.write_attempt(record)
        campaign.ledger.write_outcome(1, {'class': 'completed', 'usage': usage(input_tokens=2000000, output_tokens=0)})
        self.assertEqual(campaign.totals()['exposure'], Decimal('4.00'))          # 2,000,000 x $2/M, never x $1/M
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', '0.95')                              # 4.00 + 1.045 > 5.00
        self.assertIn('Stage model_check limit', str(caught.exception))
        self.assertEqual(campaign.admit('model_check', '0.80'), Decimal('0.880'))

    def test_every_pinned_term_is_checked(self):
        d = declaration()
        self.spent(d)
        edits = (({'model': 'claude-sonnet-4-6'}, 'model'), ({'thinking': 'adaptive'}, 'thinking'),
                 ({'effort': 'high'}, 'effort'), ({'inference_geo': 'us'}, 'inference_geo'),
                 ({'pricing_versions': (('model_check', 'configured-v1:' + 'b' * 64),)}, 'pricing'),
                 ({'pricing_versions': d.pricing_versions + (('mapping', 'configured-v1:' + 'c' * 64),)}, 'pricing'))
        for changes, word in edits:
            with self.subTest(changes=changes), self.assertRaises(pc.Refused) as caught:
                pc.Campaign(dataclasses.replace(d, **changes), self.root).admit('model_check', MAXIMUM)
            self.assertIn(word, str(caught.exception))

    def test_a_reopening_is_held_to_the_pinned_terms(self):
        d = declaration()
        campaign = self.spent(d)
        campaign.ledger.write_stage('model_check', 'failed', {'reasons': ['synthetic']})
        campaign.ledger.release()
        edited = pc.Campaign(dataclasses.replace(d, rates=pc.Rates('1', '5', '0.10')), self.root)
        edited.ledger.acquire()
        self.addCleanup(edited.ledger.release)
        with self.assertRaises(pc.Refused) as caught:
            edited.reopen('model_check', '/nonexistent/diagnosis.md', runner_commit='0' * 40)
        self.assertIn('rates', str(caught.exception))

    def test_a_legacy_first_attempt_is_pinned_to_the_declaration_blob_it_names(self):
        repository, path = repository_with(self, REAL_TEXT)
        first = pc.declared(path, repository=repository, out=io.StringIO())
        campaign = self.campaign(first)
        legacy = attempt(1, campaign=first.campaign, authority=first.authority_id, terms=None)
        legacy.update(declaration_sha256=first.sha256, declaration_commit=first.commit)
        campaign.ledger.write_attempt(legacy)
        campaign.ledger.write_outcome(1, {'class': 'completed', 'usage': usage()})
        self.assertEqual(campaign.pinned_terms().record(), terms_record(first))
        path.write_text(REAL_TEXT.replace('rates: input 2 output 10 cached 0.20', 'rates: input 1 output 5 cached 0.10'))
        git(repository, 'commit', '-q', '-a', '-m', 'Lower the rates')
        edited = pc.declared(path, repository=repository, out=io.StringIO())
        self.assertEqual(edited.rates, pc.Rates('1', '5', '0.10'))
        pinned = pc.Campaign(edited, self.root)
        self.assertEqual(pinned.pinned_terms().record(), terms_record(first))
        self.assertEqual(pinned.totals()['exposure'], Decimal('0.004'))
        with self.assertRaises(pc.Refused) as caught:
            pinned.admit('model_check', MAXIMUM)
        self.assertIn('rates', str(caught.exception))
        # a first attempt whose declaration cannot be read back pins nothing: refused
        stray = pc.Campaign(edited, scratch(self))
        stray.ledger.acquire()
        self.addCleanup(stray.ledger.release)
        stray.ledger.write_attempt(dict(legacy, declaration_sha256='f' * 64))
        stray.ledger.write_outcome(1, {'class': 'completed', 'usage': usage()})
        with self.assertRaises(pc.Refused) as caught:
            stray.totals()
        self.assertIn('cannot be read back', str(caught.exception))

    def test_the_first_attempt_pins_and_a_later_one_that_disagrees_is_refused(self):
        d = declaration()
        campaign = self.spent(d)
        other = terms_record(d)
        other['rates']['output'] = '5'
        campaign.ledger.write_attempt(attempt(2, limits=limits_record(d), terms=other))
        campaign.ledger.write_outcome(2, {'class': 'completed', 'usage': usage()})
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('terms', str(caught.exception))

    def test_recorded_terms_are_read_strictly(self):
        good = terms_record(declaration())
        broken = [
            {**good, 'extra': 1},
            {k: v for k, v in good.items() if k != 'effort'},
            {**good, 'rates': {**good['rates'], 'input': 2}},
            {**good, 'rates': {**good['rates'], 'extra': '1'}},
            {**good, 'pricing_versions': [['model_check', good['pricing_versions']['model_check']]]},
            {**good, 'pricing_versions': {'model_check': 'configured-v1:short'}},
            {**good, 'model': None},
            [good],
        ]
        for number, record in enumerate(broken, start=1):
            with self.subTest(record=record), self.assertRaises(pc.Refused) as caught:
                pc.Terms.from_record(record, f'Attempt {number}')
            self.assertIn('terms', str(caught.exception))
        self.assertEqual(pc.Terms.from_record(good, 'Attempt 1').record(), good)


#: The field-relations pricing chain, measured offline with core.generation.configuration() under the declared
#: settings: the base price (rates, model, the ordinary request profile claude-sonnet-5-ordinary-v1) and the declared
#: version it produces under the v1 contract; the v2 contract's version under the SAME base.
RELATIONS_BASE = 'configured-v1:47caed2bcbbabc7f0d1c2713ba8b497db26f9fdf2dfff1de092410fdd7f784b4'
RELATIONS_V1 = 'configured-v1:eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180'
RELATIONS_V2 = 'configured-v1:0d357747cbf72641cb621e38c2e2c409fb94fddaf614ce188fc518067749a2f7'
PLAIN_BASE = 'configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d'


def amendment_text(declaration_sha256, **changes):
    """A contract-identity amendment, as the lead would commit it (never committed to the real repository here)."""
    lines = {'campaign': 'quillmd-v1-sonnet5-staged-40',
             'authority_id': 'quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk',
             'amends_declaration_sha256': declaration_sha256,
             'amended_pricing_key': 'ordinary_notes_field_relations',
             'pinned_pricing_version': RELATIONS_V1,
             'previous_pricing_version': RELATIONS_BASE,
             'previous_ordinary_field_contract': 'ordinary-field-relations-v1',
             'ordinary_field_contract': 'ordinary-field-relations-v2',
             'amended_pricing_version': RELATIONS_V2, **changes}
    body = '\n'.join(f'{name}: {value}' for name, value in lines.items() if value is not None)
    return ('# Amendment: ordinary field-relations contract identity\n\nThe repaired relations contract changes the '
            'request the field-relations sends make and nothing else.\n\n```\n' + body + '\n```\n')


class AmendmentTests(unittest.TestCase):
    """A contract-identity amendment (declared_amendment, Campaign.pricing_version): committed, tracked and unmodified
    beside the declaration; able to change ONLY the ordinary field-relations pricing version, and only to the new
    contract bound to the SAME base price the ledger's first attempt pinned. Anything else refuses."""

    def setUp(self):
        self.repo, self.path = repository_with(self, REAL_TEXT)
        self.declaration = pc.declared(self.path, repository=self.repo, out=io.StringIO())
        self.root = scratch(self)

    def commit(self, text, name='20260929-test-amendment.md', commit=True):
        path = self.path.parent / name
        path.write_text(text, encoding='utf-8')
        if commit:
            git(self.repo, 'add', '--', str(path.relative_to(self.repo)))
            git(self.repo, 'commit', '-q', '-m', 'Synthetic amendment')
        return path

    def refused(self, path, fragment='', declaration=None):
        with self.assertRaises(pc.Refused) as caught:
            pc.declared_amendment(path, declaration or self.declaration, out=io.StringIO())
        self.assertIn(fragment, str(caught.exception))

    def pinned_campaign(self, amendment, terms=None):
        campaign = pc.Campaign(self.declaration, self.root, amendment=amendment)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        d = self.declaration
        campaign.ledger.write_attempt(attempt(1, campaign=d.campaign, authority=d.authority_id, limits=limits_record(d),
                                              terms=terms or terms_record(d)))
        campaign.ledger.write_outcome(1, {'class': 'completed', 'usage': usage()})
        return campaign

    def test_the_declared_relations_version_is_the_ordinary_base_bound_to_the_v1_contract(self):
        self.assertEqual(pc.contract_pricing_version(RELATIONS_BASE, 'ordinary-field-relations-v1'), RELATIONS_V1)
        self.assertEqual(self.declaration.pricing_version('ordinary_notes_field_relations'), RELATIONS_V1)
        self.assertEqual(pc.contract_pricing_version(RELATIONS_BASE, 'ordinary-field-relations-v2'), RELATIONS_V2)
        # (the plain generation price is NOT the relations base: bound to v1 it is not the declared version)
        self.assertNotEqual(pc.contract_pricing_version(PLAIN_BASE, 'ordinary-field-relations-v1'), RELATIONS_V1)

    def test_the_exact_contract_only_change_is_accepted_and_changes_nothing_else(self):
        out = io.StringIO()
        amendment = pc.declared_amendment(self.commit(amendment_text(self.declaration.sha256)), self.declaration, out=out)
        self.assertEqual((amendment.pricing_key, amendment.pinned_pricing_version, amendment.previous_pricing_version,
                          amendment.previous_contract, amendment.contract, amendment.pricing_version),
                         ('ordinary_notes_field_relations', RELATIONS_V1, RELATIONS_BASE, 'ordinary-field-relations-v1',
                          'ordinary-field-relations-v2', RELATIONS_V2))
        stamp = git(self.repo, 'log', '-1', '--format=%cI').stdout.decode().strip()
        self.assertEqual(amendment.commit_time, stamp)
        self.assertIn(stamp, out.getvalue())
        for campaign in (pc.Campaign(self.declaration, scratch(self), amendment=amendment),   # (no attempt yet)
                         self.pinned_campaign(amendment)):                                      # (pinned by attempt 1)
            with self.subTest(rows=len(campaign.rows())):
                self.assertEqual(campaign.pricing_version('ordinary_notes_field_relations'), RELATIONS_V2)
                for key in ('model_check', 'mapping', 'ordinary_notes'):
                    self.assertEqual(campaign.pricing_version(key), self.declaration.pricing_version(key))
                self.assertEqual(campaign.limits().record(), limits_record(self.declaration))
                self.assertEqual(campaign.pinned_terms().record(), terms_record(self.declaration))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            amendment.pricing_version = RELATIONS_V1

    def test_an_untracked_uncommitted_staged_or_hidden_edit_refuses(self):
        text = amendment_text(self.declaration.sha256)
        self.refused(self.commit(text, 'untracked.md', commit=False), 'tracked, committed and unmodified')
        path = self.commit(text, 'modified.md')
        path.write_text(text.replace(RELATIONS_V2, RELATIONS_V1))
        self.refused(path, 'tracked, committed and unmodified')
        path = self.commit(text, 'staged.md')
        path.write_text(text + '\n')
        git(self.repo, 'add', '--', str(path.relative_to(self.repo)))
        self.refused(path, 'tracked, committed and unmodified')
        path = self.commit(text, 'hidden.md')
        git(self.repo, 'update-index', '--assume-unchanged', '--', str(path.relative_to(self.repo)))
        path.write_text(text.replace('ordinary-field-relations-v2', 'ordinary-field-relations-v3'))
        self.refused(path, 'differs from its committed blob')

    def test_an_amendment_outside_the_mutations_folder_or_the_declaration_itself_refuses(self):
        text = amendment_text(self.declaration.sha256)
        elsewhere = self.repo / 'docs' / 'amendment.md'
        elsewhere.write_text(text)
        git(self.repo, 'add', '--', 'docs/amendment.md')
        git(self.repo, 'commit', '-q', '-m', 'Elsewhere')
        self.refused(elsewhere, 'docs/foundation/mutations')
        self.refused(self.path, 'its own file')

    def test_a_base_price_other_than_the_pinned_one_refuses(self):
        sha = self.declaration.sha256
        # the plain generation price (8975b158) is not the relations base: its v1 wrap is not the declared version
        cases = {
            'the plain base': amendment_text(sha, previous_pricing_version=PLAIN_BASE, amended_pricing_version=
                                             pc.contract_pricing_version(PLAIN_BASE, 'ordinary-field-relations-v2')),
            'another base (a rate or profile changed)': amendment_text(
                sha, previous_pricing_version='configured-v1:' + 'b' * 64,
                amended_pricing_version=pc.contract_pricing_version('configured-v1:' + 'b' * 64,
                                                                   'ordinary-field-relations-v2')),
            'another previous contract': amendment_text(sha, previous_ordinary_field_contract='ordinary-field-relations-v0'),
        }
        for name, text in cases.items():
            with self.subTest(name=name):
                self.refused(self.commit(text, f'{len(name)}-base.md'), 'the base price is not the pinned one')

    def test_a_stated_version_that_is_not_the_base_bound_to_the_new_contract_refuses(self):
        sha = self.declaration.sha256
        for name, text in {
                'a version from nowhere': amendment_text(sha, amended_pricing_version='configured-v1:' + 'c' * 64),
                'the v2 version under a v3 name': amendment_text(sha, ordinary_field_contract='ordinary-field-relations-v3'),
        }.items():
            with self.subTest(name=name):
                self.refused(self.commit(text, f'{len(name)}-stated.md'), 'not its base price bound to its new contract')

    def test_no_change_of_contract_or_another_key_campaign_authority_or_declaration_refuses(self):
        sha = self.declaration.sha256
        cases = {
            'the same contract': (amendment_text(sha, ordinary_field_contract='ordinary-field-relations-v1',
                                                 amended_pricing_version=RELATIONS_V1), 'contract identity'),
            'a malformed contract': (amendment_text(sha, ordinary_field_contract='V2!'), 'contract identity'),
            'another pricing key': (amendment_text(sha, amended_pricing_key='ordinary_notes'), 'may change only'),
            'another replaced version': (amendment_text(sha, pinned_pricing_version=PLAIN_BASE), 'not the declared'),
            'another campaign': (amendment_text(sha, campaign='another-campaign'), 'another campaign or authority'),
            'another authority': (amendment_text(sha, authority_id='another-authority'), 'another campaign or authority'),
            'another declaration': (amendment_text('d' * 64), 'another declaration'),
        }
        for name, (text, fragment) in cases.items():
            with self.subTest(name=name):
                self.refused(self.commit(text, f'{abs(hash(name))}-other.md'), fragment)

    def test_anything_else_it_tries_to_state_refuses(self):
        good = amendment_text(self.declaration.sha256)
        extra = {
            'a limit': 'total_limit_provider_usd: 400.00', 'a stage': 'stage: ordinary_notes limit_provider_usd 90.00 requires none',
            'a rate': 'rates: input 1 output 5 cached 0.10 (USD per million tokens)', 'a model': 'model: claude-opus-5',
            'a provider': 'provider: openai', 'thinking': 'thinking: adaptive', 'effort': 'effort: high',
            'a geography': 'inference_geo: us', 'a pricing version': f'pricing_version ordinary_notes: {RELATIONS_V2}',
            'a credential': 'credential_file: /tmp/key', 'transfers': 'unused_stage_budget_transfers: yes',
            'owner words': 'owner_words: Approve more', 'an authorization': 'authorization: owner 2026-09-29 approved more',
            'a decorated limit': '> **total_limit_provider_usd: 400.00**', 'a revocation': 'The owner revoked this campaign.',
            'a reopening': 'reopen_stage: ordinary_notes',
            # refutation F3: a declaration line behind ANY prefix — a list number, code, a tilde, quotes — or anywhere
            # in a line, is still that line (these were accepted by the old prefix list)
            'a numbered limit': '1. total_limit_provider_usd: 400.00',
            'a stage in code': '`stage: ordinary_notes limit_provider_usd 90.00 requires none`',
            'a numbered model': '2) model: claude-opus-5',
            'a tilde rate': '~ rates: input 1 output 5 cached 0.10 (USD per million tokens)',
            'a numbered pricing version': f'1. pricing_version ordinary_notes: {RELATIONS_V2}',
            'a numbered credential': '3. credential_file: /tmp/other-key',
            'numbered transfers': '4. unused_stage_budget_transfers: yes',
            'a quoted limit': '"total_limit_provider_usd: 400.00"',
            'an authorization in code': '`authorization: owner 2026-09-29 approved more at the stated limits`',
            'a limit mid-line': 'Note that total_limit_provider_usd: 400.00 applies from now.',
            'a bare stage limit': 'ordinary_notes limit_provider_usd 90.00',
            'a request count': 'max_requests 99',
            'a fullwidth colon': 'total_limit_provider_usd\uff1a 400.00',
            'a zero-width space inside a name': 'total_limit\u200b_provider_usd: 400.00',
            'fullwidth letters': '\uff4d\uff4f\uff44\uff45\uff4c: claude-opus-5',
        }
        for name, line in extra.items():
            with self.subTest(name=name):
                self.refused(self.commit(good.replace('```\n', '```\n' + line + '\n', 1), f'{abs(hash(name))}-x.md'),
                             '' if name == 'a revocation' else 'may change only the field-relations contract identity')

    def test_prose_that_names_a_term_without_stating_it_is_accepted(self):
        # (the rule refuses a STATED line — a name followed by its colon, or a pricing/limit token — not the words)
        prose = ('The stage limits, the rates, the model and the provider stay exactly as declared; the staged '
                 'campaign keeps its authority.\n\n')
        good = amendment_text(self.declaration.sha256)
        path = self.commit(good.replace('```\n', prose + '```\n', 1), 'prose.md')
        self.assertEqual(pc.declared_amendment(path, self.declaration, out=io.StringIO()).pricing_version, RELATIONS_V2)

    def test_a_missing_or_repeated_line_refuses(self):
        sha = self.declaration.sha256
        for name in ('campaign', 'authority_id', 'amends_declaration_sha256', 'amended_pricing_key',
                     'pinned_pricing_version', 'previous_pricing_version', 'previous_ordinary_field_contract',
                     'ordinary_field_contract', 'amended_pricing_version'):
            with self.subTest(missing=name):
                self.refused(self.commit(amendment_text(sha, **{name: None}), f'missing-{name}.md'), f'`{name}:`')
            text = amendment_text(sha)
            line = next(row for row in text.splitlines() if row.startswith(name + ':'))
            with self.subTest(repeated=name):
                self.refused(self.commit(text.replace(line, line + '\n' + line), f'repeated-{name}.md'), f'`{name}:`')

    def test_the_first_attempts_pinned_terms_bind_the_amendment(self):
        amendment = pc.declared_amendment(self.commit(amendment_text(self.declaration.sha256)), self.declaration,
                                          out=io.StringIO())
        # the ledger's first attempt pinned another field-relations version (or another rate): refused, whatever the
        # current declaration and the amendment say
        for name, change in (('another relations version', lambda t: t['pricing_versions'].update(
                                 ordinary_notes_field_relations='configured-v1:' + 'e' * 64)),
                             ('another rate', lambda t: t['rates'].update(input='3'))):
            with self.subTest(name=name):
                self.root = scratch(self)
                terms = terms_record(self.declaration)
                terms = json.loads(json.dumps(terms))
                change(terms)
                campaign = self.pinned_campaign(amendment, terms=terms)
                with self.assertRaises(pc.Refused):
                    campaign.pricing_version('ordinary_notes_field_relations')
        # an amendment of another declaration is refused by the campaign itself
        with self.assertRaises(pc.Refused):
            pc.Campaign(dataclasses.replace(self.declaration, sha256='f' * 64), scratch(self), amendment=amendment)
        with self.assertRaises(pc.Refused):
            pc.Campaign(self.declaration, scratch(self), amendment={'pricing_version': RELATIONS_V2})

    def test_the_campaign_re_proves_an_amendment_it_did_not_parse(self):
        # (an Amendment built in memory never passed declared_amendment: the campaign proves the chain itself)
        good = pc.declared_amendment(self.commit(amendment_text(self.declaration.sha256)), self.declaration,
                                     out=io.StringIO())
        other = 'configured-v1:' + '2' * 64
        cases = {
            'another replaced version': dataclasses.replace(good, pinned_pricing_version=PLAIN_BASE),
            'another base': dataclasses.replace(good, previous_pricing_version=other, pricing_version=
                                                pc.contract_pricing_version(other, good.contract)),
            'another previous contract': dataclasses.replace(good, previous_contract='ordinary-field-relations-v0'),
            'a stated version from nowhere': dataclasses.replace(good, pricing_version='configured-v1:' + 'c' * 64),
        }
        for name, amendment in cases.items():
            with self.subTest(name=name):
                self.root = scratch(self)
                campaign = self.pinned_campaign(amendment)
                with self.assertRaises(pc.Refused):
                    campaign.pricing_version('ordinary_notes_field_relations')
                self.assertEqual(campaign.pricing_version('ordinary_notes'),
                                 self.declaration.pricing_version('ordinary_notes'))
        self.root = scratch(self)
        self.assertEqual(self.pinned_campaign(good).pricing_version('ordinary_notes_field_relations'), RELATIONS_V2)


class LiveLedgerShapeTests(unittest.TestCase):
    """The live ledger as it stood after the model check (docs/rebuild/v1/sonnet5-campaign/model-check-20260929.md),
    rebuilt in a TEMPORARY root from its documented fields — the live root is never read or written here. It must stay
    readable, its decision must stand, mapping and ordinary_notes must be admitted, and model_check never again."""
    DECLARATION_SHA256 = '76bfb6af8dea0d7184be00e7ca9d30f3c1bbc99f62057b1002f3d3643efb5d15'
    DECLARATION_COMMIT = '01ff8c7d46860967e073fc22b21018e8efda907f'
    ATTEMPT = {
        'authority_id': 'quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk',
        'campaign': 'quillmd-v1-sonnet5-staged-40', 'declaration_commit': DECLARATION_COMMIT,
        'declaration_sha256': DECLARATION_SHA256, 'encounter': 'e92d2fac-268e-43e4-89fa-a577ed61fdfe',
        'exposure_bound': '0.1153856', 'form_sha256': 'e0a3bdf4e98f07612d94572d877bacd91aab60dfd8f80e672b0d30d36c7ffeae',
        'hold': '0.157344000000', 'job': '9d22433a-c060-4f9a-bd2b-16f503e3c584', 'maximum_cost': '0.104896',
        'notes_sha256': '22b351f1acfccc80aeedf7ab5b8485f57fc06341630f531f279185251990abf5', 'number': 1, 'pid': 3622655,
        'pricing_version': 'configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d',
        'rates': {'cached': '0.20', 'input': '2', 'output': '10'},
        'request_profile': {'effort': 'medium', 'max_output_tokens': 8000, 'profile': 'claude-sonnet-5-v1',
                            'thinking': {'type': 'disabled'}, 'timeout_seconds': 120},
        'runner_commit': '231183b3dc81b9b1566384440158075148ba0a8b', 'shown_maximum_charge': '0.1573440',
        'stage': 'model_check', 'started_at': '2026-09-29T00:56:53.353437+00:00'}
    OUTCOME = {
        'billing': '', 'class': 'completed', 'computed_cost': '0.00286', 'computed_cost_metered_geography': '0.00286',
        'error_class': '', 'exposure': '0.00286', 'job': '9d22433a-c060-4f9a-bd2b-16f503e3c584', 'job_error': '',
        'job_state': 'succeeded', 'number': 1, 'provider_request_id': 'req_011CfWpbvUpWa7eEj1zrJ4Kt',
        'provider_resource_id': 'msg_011CfWpbwtQsMKgMLksaWRXd',
        'raw_result_sha256': '7e6b08784f247757ef5a26e05dd43cfc4c19d342c24da4a0626ab0036e32298e',
        'recorded_at': '2026-09-29T00:56:56.834561+00:00', 'request_captured': True, 'served_model': 'claude-sonnet-5',
        'settlement': {'charged_cost': '0.004290000000', 'receipt_actual_cost': '0.002860000000',
                       'reservations': ['settled'], 'usage_actual_cost': '0.002860000000'},
        'stop_reason': 'end_turn',
        'usage': {'cache_creation': {'ephemeral_1h_input_tokens': 0, 'ephemeral_5m_input_tokens': 0},
                  'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0, 'inference_geo': 'global',
                  'input_tokens': 840, 'output_tokens': 118, 'output_tokens_details': {'thinking_tokens': 0},
                  'server_tool_use': None, 'service_tier': 'standard'},
        'worker_ran': True}
    PASSED = {
        'attempt': 1, 'checks': ['served model', 'end_turn', 'output below 70%', 'geography', 'settled at declared rates',
                                 'validator decision', 'review, finalize, export', 'billing audit', 'evidence retained',
                                 'no leaked credential'],
        'decision': 'passed', 'manifest_sha256': '37bcd51562afc3a7f1e8a695d0c24caea3e15ed0a8cf2378bc73d29debc158ca',
        'recorded_at': '2026-09-29T00:56:58.176674+00:00', 'stage': 'model_check'}

    def setUp(self):
        self.root = scratch(self)
        ledger = pc.private_directory(self.root / 'ledger')
        pc.write_new(ledger / '001-attempt.json', self.ATTEMPT)
        pc.write_new(ledger / '001-outcome.json', self.OUTCOME)
        pc.write_new(ledger / 'stage-model_check-passed.json', self.PASSED)
        os.close(os.open(ledger / 'runner.lock', os.O_CREAT | os.O_WRONLY, 0o600))
        self.declaration = pc.declared(REAL_DECLARATION, repository=REPOSITORY, out=io.StringIO())

    def test_the_documented_declaration_is_the_one_committed_at_the_documented_commit(self):
        relative = str(REAL_DECLARATION.relative_to(REPOSITORY))
        blob = git(REPOSITORY, 'cat-file', 'blob', f'{self.DECLARATION_COMMIT}:{relative}').stdout
        self.assertEqual(hashlib.sha256(blob).hexdigest(), self.DECLARATION_SHA256)

    def test_the_ledger_reads_and_its_decision_stands(self):
        campaign = pc.Campaign(self.declaration, self.root)
        (row,) = campaign.rows()
        self.assertEqual((row[0]['stage'], row[1]['class']), ('model_check', 'completed'))
        self.assertEqual(campaign.totals()['exposure'], Decimal('0.00286'))
        self.assertEqual(campaign.totals()['unknown'], 0)
        self.assertEqual(campaign.ledger.stage_state('model_check')['state'], 'passed')
        self.assertEqual(campaign.ledger.stage_record('model_check', 'passed'), self.PASSED)
        self.assertEqual(campaign.ledger.undecided(), {})
        self.assertEqual(campaign.limits().record(), limits_record(self.declaration))

    def test_mapping_and_ordinary_notes_are_admitted_and_model_check_is_not(self):
        campaign = pc.Campaign(self.declaration, self.root)
        for stage in ('mapping', 'ordinary_notes'):
            with self.subTest(stage=stage):
                self.assertEqual(campaign.admit(stage, MAXIMUM), Decimal(MAXIMUM) * Decimal('1.1'))
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('already passed', str(caught.exception))
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        with self.assertRaises(pc.Refused) as caught:
            campaign.reopen('model_check', REAL_DECLARATION, runner_commit=self.ATTEMPT['runner_commit'])
        self.assertIn('has not failed', str(caught.exception))
        self.assertEqual(sorted(os.listdir(self.root / 'ledger')),
                         ['001-attempt.json', '001-outcome.json', 'runner.lock', 'stage-model_check-passed.json'])

    def test_the_terms_pin_to_the_documented_declaration_and_an_edit_admits_nothing(self):
        # (A1: the live attempt 1 records no terms; it is pinned to the declaration it names — the current one, or the
        # blob at 01ff8c7d when the current declaration differs — and every outcome is costed at those rates)
        campaign = pc.Campaign(self.declaration, self.root)
        self.assertEqual(campaign.pinned_terms().record(), terms_record(self.declaration))
        self.assertEqual(campaign.pinned_terms().rates, pc.Rates('2', '10', '0.20'))
        edited = dataclasses.replace(self.declaration, sha256='e' * 64, rates=pc.Rates('1', '5', '0.10'))
        pinned = pc.Campaign(edited, self.root)
        self.assertEqual(pinned.pinned_terms().record(), terms_record(self.declaration))     # (read back from git)
        self.assertEqual(pinned.totals()['exposure'], Decimal('0.00286'))
        for stage in ('mapping', 'ordinary_notes'):
            with self.subTest(stage=stage), self.assertRaises(pc.Refused) as caught:
                pinned.admit(stage, MAXIMUM)
            self.assertIn('rates', str(caught.exception))

    def test_status_reads_it(self):
        from ops import sonnet5_qa as sq
        out = io.StringIO()
        with redirect_stdout(out), patch('sys.stderr', io.StringIO()):
            self.assertEqual(sq.status(root=self.root, declaration_path=REAL_DECLARATION), 0)
        report = json.loads(out.getvalue())
        self.assertEqual((report['stages']['model_check']['exposure'], report['stages']['model_check']['remaining'],
                          report['stages']['model_check']['state']), ('0.00286', '4.99714', 'passed'))
        self.assertEqual((report['stages']['mapping']['remaining'], report['total']['remaining']), ('25.00', '39.99714'))


class NetworkGuardTests(unittest.TestCase):
    def test_the_guard_refuses_a_provider_host_and_a_public_address(self):
        network_guard.positive_control(self)


if __name__ == '__main__':
    unittest.main()
