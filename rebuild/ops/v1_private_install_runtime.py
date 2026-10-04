"""Fixed runtime for activate-v1-private-install.py; never imported by an unmet gate.

Reuses the pinned historical helper transport, private identity/file inventory,
static compiler and preservation conventions. Historical drivers are unchanged.
No method accepts arbitrary host commands, units, database names or secret paths.
"""
from contextlib import contextmanager
import contextlib
import fcntl
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import types

from . import v1_private_install_adapter as protocol
from . import v1_private_install_preparation as p
from . import v1_install_catalog
from .ordinary_generation_activation import environment, SOURCE_PATHS, MODEL, CONTRACT, PROFILE

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
LINEAGE = 'scripts/activate-denial-heading-install.py'
LINEAGE_SHA256 = '5590578db46cb9a498da0a93882cfbdf34eadd54a10b1d69f03aefc3def952cc'
PARTICIPANT_LOCKS = ('backup-monitor/capture.lock', 'automatic-offsite/execution.lock', 'backup-alerts/monitor.lock')


def require(value, message):
    p.require(value, message)


class Backend:
    schema_owner = 'quillmd_owner'

    def __init__(self, source, frozen, relative, declaration, live_source):
        self.source, self.frozen, self.relative = source, frozen, relative
        self.declaration, self.live_source = declaration, live_source
        self.state = PRIVATE / 'v1-private-install' / declaration['target']
        raw = (source / LINEAGE).read_bytes()
        require(p.sha(raw) == LINEAGE_SHA256, 'Reviewed helper lineage changed.')
        self.lineage = types.ModuleType('_v1_install_qualified_lineage')
        self.lineage.__file__ = str(source / LINEAGE)
        exec(compile(raw, self.lineage.__file__, 'exec'), self.lineage.__dict__)
        self.driver = self.lineage.driver
        for module in (self.driver, self.driver.a, self.driver.b):
            module.BASELINE = module.RUNNING_RELEASE = p.BASELINE
            module.EVIDENCE = self.state
        self.phase = 0

    def validate_live(self, declaration, evidence, contract):
        self.live_source(declaration['target'])
        require(os.path.abspath(sys.executable) == str(APP / '.venv/bin/python'),
                'Use the installed reviewed private interpreter; no replacement venv is implied.')
        self.modules = {name: self.driver.a.load(name, relative, declaration['target'])
                        for name, relative in self.driver.b.HELPERS.items() if name != 'backup'}
        self.old, self.word, self.identity, self.storage, self.previous = (
            self.modules[name] for name in ('old', 'word', 'identity', 'storage', 'previous'))
        self.original = self.word.checked_file(APP / '.env', private=True)
        from dotenv import dotenv_values
        old_values = dotenv_values(stream=StringIO(self.original.decode()), interpolate=False)
        require(old_values.get('QUILLMD_STRIPE_MODE', 'test') == 'test'
                and not old_values.get('CPT_LICENSE_ID') and not old_values.get('CPT_LICENSE_EXPIRY'),
                'Preserve test payments and the disabled CPT boundary.')
        sources = {name: (self.source / name).read_bytes() for name in SOURCE_PATHS}
        identity = {'release': declaration['target'], 'model': MODEL, 'ordinary_field_contract': CONTRACT,
                    'request_profile': PROFILE, 'sources': {name: p.sha(raw) for name, raw in sources.items()}}
        self.updated = environment(self.original, p.BASELINE, declaration['target'],
                                   source_identity=identity, source_bytes=sources)
        # Broad Word support is enabled only after B-W1 was actually qualified.
        from .email_activation import _line
        import re
        for name, value in (('QUILLMD_WORD_ENGINE', 'auto'), ('QUILLMD_WORD_AUTO_PREFER_V3', '1'),
                            ('QUILLMD_REGISTRATION', 'invite')):
            pattern = rb'(?m)^(?:export[ \t]+)?' + name.encode() + rb'[ \t]*=[^\r\n]*(?:\r?\n|$)'
            require(len(re.findall(pattern, self.updated)) <= 1, 'Duplicate Word engine setting.')
            self.updated = re.sub(pattern, lambda match: _line(name, value), self.updated) if re.search(pattern, self.updated) else self.updated + _line(name, value)
        self.helper = json.loads(self.word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
        require(self.helper == self.driver.a.managed().IMAGE, 'Qualified fixed helper unavailable.')
        self.driver.b.health(p.BASELINE)
        self.identity.verify_live(p.BASELINE, self.storage)
        self.worker_before = self.old.worker_process()
        self.previous.protected()
        self.inputs = self.word.expected_inputs(declaration['target'])
        require(self.inputs == self.word.expected_inputs(p.BASELINE), 'The installed Word SDK may not be replaced.')
        self.sdk = APP / '.word-sdk' / self.modules['billing'].SDK_RELEASE
        self.artifact = self.word.verify_artifact(self.sdk / 'runtime', self.sdk / 'runtime-manifest.json',
            self.sdk / 'build-proof.json', self.modules['billing'].PIN, self.inputs)
        for kind in ('recovery', 'baseline_static'):
            record = self.frozen[kind]
            path = PRIVATE / record['relative']
            require(path.resolve() == path and path.is_relative_to(PRIVATE), 'Canonical retained evidence path required.')
            raw = self.word.checked_file(path, private=True)
            require(p.sha(raw) == record['sha256'], 'Retained restore/static evidence changed.')
            value = json.loads(raw)
            require(value.get('complete') is True, 'Retained restore/static evidence did not complete.')
            if kind == 'baseline_static':
                require(value.get('target') == p.BASELINE, 'Static evidence is for another installed release.')
                self.static_before = value['static_transition']['after']
        require(self.driver.static_inventory(APP / 'staticfiles') == self.static_before, 'Installed static identity changed.')
        # No network/package mutation: refuse a dependency delta that the existing
        # interpreter cannot satisfy. A reviewed dependency install is a separate
        # preserving step before retry, not a fallback inside this transaction.
        command = [str(APP / '.venv/bin/python'), '-B', '-c',
            'import importlib.metadata as m; from packaging.requirements import Requirement; '
            'from pathlib import Path; '
            'items=[Requirement(s) for s in Path(' + repr(str(self.source / 'rebuild/requirements.txt')) + ').read_text().splitlines() if s and not s.startswith("#")]; '
            'assert all((r.marker is not None and not r.marker.evaluate()) or r.specifier.contains(m.version(r.name),prereleases=True) for r in items)']
        subprocess.run(command, check=True, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.contract = contract

    def create_unused_evidence(self, outcome):
        parent = self.state.parent
        parent.mkdir(mode=0o700, exist_ok=True)
        require(parent.resolve() == parent and stat.S_IMODE(parent.stat().st_mode) == 0o700
                and parent.stat().st_uid == os.getuid(), 'Protected evidence directory required.')
        self.state.mkdir(mode=0o700)
        self.identity.private_write(self.state / 'input-identities.json', {
            'target': self.declaration['target'], 'declaration': self.relative,
            'qualification_sha256': self.frozen['qualification_sha256'], 'catalog': self.frozen['catalog_contract'],
            'baseline': p.BASELINE, 'environment_before_sha256': p.sha(self.original),
            'environment_after_sha256': p.sha(self.updated), 'provider_calls': 0})

    def checkpoint(self, outcome):
        self.identity.private_write(self.state / ('phase-%02d.json' % self.phase), outcome)
        self.phase += 1

    @contextmanager
    def exclude_publication(self):
        from . import activation_exclusion as exclusion
        exclusion.bind_runtime(PRIVATE)
        owner = 'activation:v1:' + self.declaration['target'][:12]
        self.publisher = __import__('ops.install_operations_publisher', fromlist=['scope'])
        self.publisher.scope()
        self.publisher_before = self.publisher.published_row()
        from . import v1_install_participants as participants
        prior = []
        for timer in participants.TIMERS:
            state = self.driver.b.output(['systemctl', 'show', timer, '--property=ActiveState', '--value'])
            require(state in ('active', 'inactive'), 'A private operational timer is transitioning.')
            if state == 'active':
                prior.append(timer)
        timer_record = {'target': self.declaration['target'], 'pid': os.getpid(),
                        'start': participants.start_identity(os.getpid()), 'prior_active': prior}
        participants.validate(timer_record)
        self.identity.private_write(self.state / 'timer-pause.json', timer_record)
        timer_watchdog = participants.spawn(self.state, timer_record, source=self.source)
        participants.action('stop', participants.TIMERS, directory=self.state)
        # The publisher timer uses the existing durable pause/debt/watchdog.
        # Other existing actors already own fixed flock paths. Acquire those
        # locks too: schema/source changes cannot overlap a backup/offsite/check.
        descriptors = []
        watchdog = exclusion.spawn_bootstrap_watchdog(owner, self.source / 'rebuild', PRIVATE)
        require(self.lineage.unit_state(self.lineage.PUBLISHER_TIMER, ('ActiveState', 'UnitFileState')) ==
                {'ActiveState': 'active', 'UnitFileState': 'enabled'}, 'Existing publisher timer must be active and enabled.')
        exclusion.note_timer_paused(owner, prior_active=True)
        self.lineage.systemctl('stop', self.lineage.PUBLISHER_TIMER)
        try:
            exclusion.drain_publisher()
            with exclusion.hold(owner):
                for relative in PARTICIPANT_LOCKS:
                    path = PRIVATE / relative
                    require(path.parent.resolve() == path.parent and path.parent.is_dir(), 'Existing participant state required.')
                    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                    descriptors.append(fd)
                    info = os.fstat(fd)
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                            and stat.S_IMODE(info.st_mode) == 0o600, 'Unsafe participant lock.')
                    deadline = time.monotonic() + 120
                    while True:
                        try:
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                        except BlockingIOError:
                            require(time.monotonic() < deadline, 'Private operational participant did not drain.')
                            time.sleep(0.1)
                try:
                    yield
                except BaseException:
                    self.stop(); self.assert_stopped(); raise
        finally:
            for fd in reversed(descriptors):
                os.close(fd)
            self.lineage.systemctl('start', self.lineage.PUBLISHER_TIMER)
            exclusion.clear_timer_pause(owner)
            with contextlib.suppress(subprocess.TimeoutExpired):
                watchdog.wait(timeout=20)
            if prior:
                participants.action('start', tuple(prior), directory=self.state)
            self.identity.private_write(self.state / 'timers-restored.json', {'restored': prior})
            with contextlib.suppress(subprocess.TimeoutExpired):
                timer_watchdog.wait(timeout=20)

    def stop(self):
        self.word.systemd('stop', self.helper)

    def assert_stopped(self):
        self.driver.b.stopped()

    def snapshot(self, *, before=None):
        from . import backup_restore
        import psycopg
        # This is the existing authenticated backup-role connection procedure.
        # No role/endpoint/env override or superuser fallback is provided.
        with psycopg.connect(**backup_restore.source_options(APP, self.driver.b.ROLES), autocommit=True) as connection:
            connection.execute("SET timezone='UTC'; SET datestyle='ISO, MDY'; SET statement_timeout='600s'")
            connection.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            def query(statement):
                return connection.execute(statement).fetchall()
            def copy_hash(statement):
                with connection.cursor().copy(statement) as stream:
                    return v1_install_catalog.stream_hash(stream)
            value = v1_install_catalog.read(query, copy_hash, before=before)
            require(not any(backup_restore.invariant_counts(query).values()), 'Clinical/financial invariants failed.')
            connection.execute('ROLLBACK')
        value.update(storage={name: self.storage.inventory(Path('/var/lib/quillmd') / name) for name in ('files', 'mail')},
            unit_files=self.driver.b.unit_files(self.word), shared_configs=self.driver.a.shared_configs(self.helper),
            protected=self.previous.protected(), operations=self.driver.a.operational_state(self.word))
        return value

    def retain_recovery(self, before):
        self.assert_stopped()
        require(self.word.checked_file(APP / '.env', private=True) == self.original, 'Environment changed before retention.')
        archive = subprocess.check_output(['git', 'archive', '--format=tar', p.BASELINE, 'rebuild'], cwd=ROOT, timeout=90)
        self.identity.private_write(self.state / 'prior-runtime-manifest.json', self.driver.a.retained_source_manifest(archive))
        for name, raw in (('prior-runtime-source.tar', archive), ('prior-environment.env', self.original)):
            fd = os.open(self.state / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        self.driver.retain_static(APP / 'staticfiles', self.state / 'prior-static.tar', self.static_before)
        self.identity.private_write(self.state / 'stopped-before.json', before)
        # The old restore drill qualifies the mechanism; it does not cover all
        # today's rows. A local encrypted stopped capture is the rollback asset
        # for this migration, not a repeated restore or an offsite/B2 renewal.
        capture = self.state / 'local-final-capture'
        capture.mkdir(mode=0o700)
        command = [str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/backup_restore.py'), 'backup',
                   '--source', str(APP), '--database-credentials', str(self.driver.b.ROLES),
                   '--key-file', str(PRIVATE / 'backup-secrets/fresh-backup-current-20260917.key'), '--output', str(capture)]
        completed = subprocess.run(command, check=True, timeout=600, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'})
        require(len(completed.stdout) <= 65536, 'Final encrypted capture summary is oversized.')
        summary = json.loads(completed.stdout)
        require(summary.get('complete') is True and summary.get('encrypted') is True
                and summary.get('source_commit') == p.BASELINE and summary.get('table_count') == len(before['tables'])
                and summary.get('row_count') == sum(row['rows'] for row in before['rows'].values()),
                'Final local encrypted capture is incomplete or belongs to another population.')
        self.identity.private_write(self.state / 'local-final-capture-summary.json', summary)
        captured = self.snapshot()
        require(captured == before, 'Stopped population/files changed while retaining the migration recovery asset.')

    def advance_source(self, target):
        self.live_source(target)
        subprocess.run(['git', 'merge', '--ff-only', target], cwd=ROOT, check=True, timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        require(self.driver.b.git('rev-parse', 'HEAD') == target
                and not self.driver.b.git('status', '--porcelain', '--untracked-files=no'), 'Source advance was not exact.')

    def migration_plan(self):
        return self.driver.b.output(self.driver.b.management('showmigrations', '--plan'), cwd=APP, timeout=120)

    def migrate(self, leaf):
        require(leaf == p.LEAF, 'Only the declared forward leaf may be applied.')
        subprocess.run(self.driver.b.management('migrate', 'core', leaf, '--noinput'), cwd=APP,
                       check=True, timeout=900, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        # Normal post_migrate publication is part of the captured synthetic
        # contract, including only exact new permission/content-type identities.
        subprocess.run(self.driver.b.management('migrate', '--noinput'), cwd=APP,
                       check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        subprocess.run(self.driver.b.management('check'), cwd=APP, check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def retain_transition(self, before, after):
        self.identity.private_write(self.state / 'stopped-after.json', after)

    def install_assets_and_environment(self):
        self.assert_stopped()
        stage = self.state / 'static-stage'
        self.driver.create_static_stage(stage); self.driver.collect_static(stage)
        staged = self.driver.validate_staged_static(stage, self.identity.static_sources())
        self.static_after = self.driver.install_static(APP / 'staticfiles', stage, self.static_before, staged)
        self.identity.private_write(self.state / 'static-transition.json', {
            'before': self.static_before, 'staged': staged, 'after': self.static_after, 'old_immutable_assets_retained': True})
        self.modules['env'].replace_environment(APP / '.env', self.original, self.updated)

    def verify_installed_stopped(self, before, contract):
        self.assert_stopped()
        protocol.validate_transition(before, self.snapshot(before=before), json.loads((self.source / self.frozen['schema_path']).read_bytes()),
                                     contract, owner=self.schema_owner)
        require(self.word.checked_file(APP / '.env', private=True) == self.updated
                and self.driver.static_inventory(APP / 'staticfiles') == self.static_after,
                'Reviewed environment/static installation differs.')
        self.identity.source_readability(self.helper)

    def start_and_verify(self, target, before, contract):
        self.word.systemd('start', self.helper)
        for attempt in range(45):
            try:
                self.driver.b.health(target); break
            except (RuntimeError, subprocess.SubprocessError, json.JSONDecodeError):
                time.sleep(1)
        else:
            raise RuntimeError('New private release did not become healthy within the bound.')
        self.identity.verify_live(target, self.storage); self.identity.verify_interfaces()
        worker = self.old.worker_process()
        require(worker['systemd_start'] != self.worker_before['systemd_start']
                and worker['kernel_start_utc'] > self.worker_before['kernel_start_utc'], 'Worker restart is unproven.')
        protocol.validate_transition(before, self.snapshot(before=before), json.loads((self.source / self.frozen['schema_path']).read_bytes()),
                                     contract, owner=self.schema_owner)
        require(self.word.verify_artifact(self.sdk / 'runtime', self.sdk / 'runtime-manifest.json',
            self.sdk / 'build-proof.json', self.modules['billing'].PIN, self.inputs) == self.artifact, 'Installed Word SDK changed.')
        subprocess.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT, check=True, timeout=90,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.identity.private_write(self.state / 'served-structural.json', {
            'target': target, 'worker': worker, 'public_cutover_performed': False,
            'representative_synthetic_flow_acceptance': 'Pending separately recorded served verification; structural probes alone do not qualify it.'})

    def verify_publication_restored(self):
        # Unit-driven status publication is nonclinical. No email/remote monitor
        # or offsite attempt is invoked here, and expired B2 remains expired.
        before = self.lineage.invocation_of(self.lineage.PUBLISHER_SERVICE)
        proof = self.lineage.prove_through_the_unit(self.publisher, self.publisher_before, before)
        tick = self.lineage.await_scheduled_tick(self.publisher, proof['row'], proof['unit'])
        require(tick.get('observed') and tick.get('invocation_changed') and tick.get('timer_trigger_advanced')
                and tick.get('row_advanced') and tick.get('result') == 'success' and tick.get('exec_main_status') == '0',
                'A successful new scheduled publication was not observed within the bounded wait.')
        self.identity.private_write(self.state / 'publication-restored.json', {'unit': proof, 'scheduled': tick})
