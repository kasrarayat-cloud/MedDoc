#!/usr/bin/env python3
"""Cited private activation of deterministic audio submission: reviewed code only, no migration; default is read-only.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B <worktree>/scripts/activate-audio-submission.py \
        --target FULL_MERGE_SHA --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/audio-submission-activation-<label>.json [--execute]

The executing form runs only through scripts/run-ruled-mutation.sh with the committed declaration.

⚠️ THIS ONE CARRIES NO MIGRATION, AND THAT MAKES ITS DECLARATION STRICTER RATHER THAN LOOSER. A migration-carrying
activation has a declared delta to judge against, so it can say 'everything except these rows changed, and that was
expected'. Here the expected delta is EMPTY: every table, column, constraint, index, migration-history row and row
fingerprint must be byte-identical before and after, and so must every private file. A difference of any kind is the
finding, because nothing in this change is entitled to produce one.

⚠️ THE TREE IS ADVANCED TO THE TARGET BEFORE THIS RUNS, AND THE FIRST VERSION ADVANCED IT ITSELF. That was wrong,
and the ruled-mutation gate caught it by refusing: the gate checks that the declaration is TRACKED and COMMITTED in
the tree the act runs in, and this activation's declaration ships in the very commit it is activating. So while the
tree still sat at the previous head, the declaration existed only in a worktree the gate cannot see, and it reported
`tracked: no`. **An activation whose declaration is invisible to its own gate is a gate that cannot fire.**

The fix is the honest ordering rather than a louder path: `main` carries the declaration, the shared tree is
fast-forwarded to it, and only then does the act run. Advancing the tree is reversible bookkeeping and is not part of
the act; the act is the release line and the restart. Doing it first is what makes the declaration's commit
timestamp — provably before the act — visible to the thing that has to check it.

⚠️ AND THE TREE'S HEAD IS NOT THE RUNNING RELEASE. The reviewed integrity-and-cleanup work merged to main as BASELINE
without being deployed, so main is one release ahead of what the services answer. Three facts, not one: the tree's HEAD,
the release the services report, and the target. An activator that assumes they move together cannot describe this.

The new runtime dependency is ffmpeg. It is not optional to VERIFY even though it is optional to RUN: without it the
application degrades silently and correctly — every recording is submitted exactly as uploaded — which is the hardest
kind of absence to notice afterwards.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
HERE = Path(__file__).resolve().parent
BASELINE = '8de5dd491de78b4e628364096c50ed68b161ef19'          # the tree's HEAD BEFORE it was fast-forwarded
RUNNING_RELEASE = '5f8050df5e79c0d7948185850914f1c161fcbc1f'    # what the services answer
SHIPPED = 'cd428f7062d3d624787d927c41130692017d5a84'            # the target this act actually ran on
DECL = 'docs/foundation/mutations/20260918-quillmd-audio-submission.md'
SELF = 'scripts/activate-audio-submission.py'
CURRENT_MIGRATION = '0014_encounter_service_date'
TABLE_COUNT = 35
MEDIA_TOOLS = ('ffmpeg', 'ffprobe')
# Every tracked path that may differ between the RUNNING RELEASE and the target, so the activation judges the whole
# tree rather than the half this session wrote. The first group merged as BASELINE and has never been deployed.
ALLOWED = {
    # PR #1203 — integrity and cleanup milestone, merged and never activated
    '.github/workflows/test.yml', 'docs/rebuild/CHECKPOINT.md', 'docs/rebuild/backup-restore.md',
    'docs/rebuild/checks-that-passed-without-looking.md', 'docs/rebuild/legacy-inventory.md',
    'docs/rebuild/owner-actions.md', 'docs/rebuild/terminology.md', 'rebuild/.gitignore',
    'rebuild/core/tests/test_code_release_dates.py', 'rebuild/core/tests/test_exercised.py',
    'rebuild/core/tests/test_wm_workflow.py', 'rebuild/exercised.py',
    'rebuild/ops/test_service_date_activation.py', 'scripts/activate-service-date.py',
    # deterministic audio submission
    'docs/rebuild/audio-submission.md', 'rebuild/core/jobs.py', 'rebuild/core/media.py',
    'rebuild/core/management/commands/configuration_status.py', 'rebuild/core/tests/test_audio_submission.py',
    'rebuild/core/tests/test_configuration_status.py', 'rebuild/core/tests/test_recording_limit.py',
    'rebuild/ops/test_audio_submission_activation.py', SELF, DECL,
}
UNITS = ['quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker')]
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.run(command, check=True, **kwargs)


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def schema():
    sql = """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') FROM
      (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,numeric_precision,numeric_scale
       FROM information_schema.columns WHERE table_schema='public') c"""
    return json.loads(output(PSQL + [sql]))


def tables():
    names = output(PSQL + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"]).splitlines()
    require(all(re.fullmatch('[a-z_][a-z_0-9]*', name) for name in names), 'Unexpected table name.')
    return names


def fingerprints(names):
    """Row fingerprints per table. No comparable= form: a code-only activation declares NOTHING may differ, so there is
    nothing to subtract, and offering a subtraction would be offering an excuse."""
    rows = {}
    for table in names:
        data = subprocess.check_output(
            PSQL + [f'COPY (SELECT (to_jsonb(t))::text AS value FROM "{table}" t ORDER BY value) TO STDOUT'], timeout=600)
        rows[table] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return rows


def constraints():
    sql = """SELECT coalesce(jsonb_agg(jsonb_build_array(c.conrelid::regclass::text, c.conname, c.contype::text, c.confrelid::regclass::text,
                 pg_get_constraintdef(c.oid)) ORDER BY c.conrelid::regclass::text, c.conname),'[]')
             FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'"""
    return [tuple(row) for row in json.loads(output(PSQL + [sql]))]


def indexes():
    return [tuple(row) for row in json.loads(output(PSQL + [
        "SELECT coalesce(jsonb_agg(jsonb_build_array(tablename,indexname,indexdef) ORDER BY tablename,indexname),'[]') FROM pg_indexes WHERE schemaname='public'"]))]


def clinical_counts():
    """The row counts a deploy must never move. Named separately from the fingerprints because a fingerprint answers
    'did anything change' and this answers 'did a document, a visit or a signature change', which is the question
    somebody will ask first."""
    return {name: int(output(PSQL + [sql])) for name, sql in (
        ('encounters', 'SELECT count(*) FROM core_encounter'),
        ('finalized', "SELECT count(*) FROM core_encounter WHERE status='finalized'"),
        ('jobs', 'SELECT count(*) FROM core_job'),
        ('usage_rows', 'SELECT count(*) FROM core_usage'),
        ('provider_receipts', 'SELECT count(*) FROM core_providerreceipt'),
        ('audit_events', 'SELECT count(*) FROM core_auditevent'))}


def media_tools():
    """Where each tool resolves, and its version. ffmpeg is the new runtime dependency; ffprobe was already one."""
    found = {}
    for name in MEDIA_TOOLS:
        path = output(['bash', '-lc', 'command -v ' + name + ' || true'])
        require(path.startswith('/') and os.access(path, os.X_OK), name + ' is not installed, so the reviewed submission path cannot run.')
        found[name] = {'path': path, 'version': output([path, '-version']).splitlines()[0][:120]}
    return found


def worker_process():
    """Identify the worker by START TIME, COMMAND and SERVICE MEMBERSHIP, not by PID.

    A PID is reused, and a PID read from one place and checked in another describes whatever happens to hold it now.
    These four facts together cannot be satisfied by a stale or unrelated process: systemd's own record of when it
    started the main process, the kernel's record of when that PID started, the command it is running, and the cgroup
    that says it belongs to this unit.
    """
    unit = 'quillmd-fresh-worker.service'
    pid = int(output(['systemctl', 'show', unit, '--property=MainPID', '--value']))
    require(pid > 0, 'The worker has no main process.')
    cgroup = Path(f'/proc/{pid}/cgroup').read_text().strip()
    require(unit in cgroup, 'The worker PID is not a member of its own service cgroup.')
    command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    # ⚠️ IT IS NOT THE LAUNCHER'S COMMAND LINE, AND ASSERTING THAT WAS WRONG. service_launcher.py EXECS the surface,
    # replacing itself, so the main process reads `<venv>/bin/python <app>/manage.py worker` — measured on the live
    # service, which is why this is checked against the running host and not only against the source. The interpreter
    # path is asserted too: it ties the process to the deployed tree rather than to any python that happens to be here.
    require(str(APP / '.venv/bin/python') in command and 'manage.py' in command and command.split()[-1] == 'worker',
            'The worker main process is not the reviewed worker command: ' + command[:120])
    # /proc/<pid>/stat field 22 is start time in clock ticks since boot; boot time comes from /proc/stat.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
    ticks = int(fields[19])
    boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime'))
    started = datetime.fromtimestamp(boot + ticks / os.sysconf('SC_CLK_TCK'), timezone.utc)
    systemd_started = output(['systemctl', 'show', unit, '--property=ExecMainStartTimestamp', '--value'])
    return {'pid': pid, 'cgroup': cgroup, 'command': command, 'kernel_start_utc': started.isoformat(),
            'systemd_start': systemd_started, 'unit': unit}


def retained_unchanged(before, now):
    """Reports retained before the act are unchanged; reports other sessions add meanwhile are allowed."""
    return all(now.get(name) == row for name, row in before.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    # HEAD IS THE TARGET, not the previous head: the tree is fast-forwarded before this runs, so the declaration the
    # ruled-mutation gate must find is tracked and committed in this tree. BASELINE is still asserted — as the commit
    # the tree came FROM — because the range being judged runs from the RUNNING RELEASE and must contain both.
    require(output(['git', 'branch', '--show-current']) == 'main'
            and output(['git', 'rev-parse', 'HEAD']) == args.target
            and output(['git', 'rev-parse', 'origin/main']) == args.target, 'Unexpected source release.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target])
    run(['git', 'merge-base', '--is-ancestor', RUNNING_RELEASE, BASELINE])
    # The declaration must be visible HERE, in this tree, or the gate that reads it cannot fire.
    run(['git', 'ls-files', '--error-unmatch', DECL], stdout=subprocess.DEVNULL)
    changed = set(output(['git', 'diff', '--name-only', RUNNING_RELEASE, args.target]).splitlines())
    require(changed <= ALLOWED and DECL in changed and 'rebuild/core/media.py' in changed,
            'Target changes paths outside the declared set: ' + ', '.join(sorted(changed - ALLOWED)))
    require(output(['git', 'diff', '--name-only', RUNNING_RELEASE, args.target, '--', 'rebuild/core/migrations']) == '',
            'This activation declares NO migration; the target adds one.')
    require(subprocess.check_output(['git', 'show', args.target + ':' + SELF]) == (HERE.parent / SELF).read_bytes(),
            'Activator differs from the reviewed target.')
    require(output(['git', 'diff', '--name-only', RUNNING_RELEASE, args.target, '--', 'rebuild/deploy', 'rebuild/documents',
                    'rebuild/ops/private_storage.py', 'rebuild/ops/service_launcher.py', 'rebuild/requirements.txt']) == '',
            'Units, document sandbox, launcher, storage helpers and dependencies are outside this activation.')
    helpers = {'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
               'previous': 'scripts/update-private-beta.py', 'storage': 'rebuild/ops/private_storage.py',
               'billing': 'scripts/activate-billing-policy.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(),
                'Existing qualified helper changed.')
        modules[name] = load('audio_submission_' + name, relative)
    word, identity, previous, storage, billing = (modules[k] for k in ('word', 'identity', 'previous', 'storage', 'billing'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    health = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{p}/health/']))
              for p in (9130, 9131)]
    require(all(h.get('release') == RUNNING_RELEASE and h.get('data_mode') == 'synthetic-only' for h in health),
            'The private services must be up on the recorded running release, synthetic-only.')
    tools = media_tools()
    worker_before = worker_process()
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('decrypted_files_written') == 0 and backup.get('restore_database_on_tmpfs_without_swap') is True,
            'The restore proof must come from the plaintext-free restore check.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unresolved jobs require inspection; never replay a provider request.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + CURRENT_MIGRATION + "'"]) == '1',
            'Expected the fresh schema through core 0014.')
    latest = output(PSQL + ["SELECT name FROM django_migrations WHERE app='core' ORDER BY id DESC LIMIT 1"])
    require(latest == CURRENT_MIGRATION, 'The schema is not at the migration this activation was reviewed against: ' + latest)
    names = tables()
    require(len(names) == TABLE_COUNT, 'Expected the current tables.')
    live_rows = sum(int(output(PSQL + [f'SELECT count(*) FROM "{t}"'])) for t in names)
    require(live_rows == backup.get('row_count'), 'The restore proof does not cover the current rows; take a fresh backup first.')
    protected = previous.protected()
    retained = word.retained_reports()
    env_before = word.checked_file(APP / '.env', private=True)
    old_line = ('QUILLMD_RELEASE_SHA=' + RUNNING_RELEASE).encode()
    require(env_before.splitlines().count(old_line) == 1, 'Expected current private release setting.')
    env_after = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$', ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
    require(env_after != env_before and env_after.count(b'\n') == env_before.count(b'\n'),
            'Release replacement did not apply cleanly.')
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE) == word.expected_inputs(RUNNING_RELEASE),
            'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', billing.PIN, inputs)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper)
            and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned local helper required.')
    for name in ('files', 'mail'):
        storage.inventory(STATE / name)
    for unit in UNITS:
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                'Installed service policy differs from reviewed source.')
    identity.verify_live(RUNNING_RELEASE, storage)
    result_path = Path(args.result)
    lock = PRIVATE / '.audio-submission-activation.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'audio-submission-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and not lock.exists() and not lock.is_symlink(),
            'Choose unused private operation evidence; a prior lock needs inspection.')
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Audio-submission activation preflight passed: reviewed code, no migration, %s and %s present, restore proof, '
          'no pending jobs.' % MEDIA_TOOLS, flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECL).name
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL])
            == subprocess.check_output(['git', 'show', commit + ':' + DECL]), 'Committed absolute declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target])
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid()})
    result = {'complete': False, 'previous_head': BASELINE, 'running_release_before': RUNNING_RELEASE,
              'target': args.target, 'started_at': datetime.now(timezone.utc).isoformat(), 'provider_calls': 0,
              'migration': None, 'media_tools': tools, 'worker_before': worker_before,
              'backup_report': args.backup_report, 'backup_run_id': backup.get('backup_run_id'),
              'artifact': artifact, 'helper_image': helper, 'retained_reports_before': retained,
              'stage': 'stopping_private_services'}
    try:
        word.systemd('stop', helper)
        for unit in UNITS:
            require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Service did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
                'Job appeared before stop.')
        old_tables = tables()
        require(old_tables == names, 'Tables changed before the act.')
        result['schema_before'] = schema()
        result['constraints_before'], result['indexes_before'] = constraints(), indexes()
        result['database_before'] = fingerprints(old_tables)
        result['clinical_before'] = clinical_counts()
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed.')
        result['stage'] = 'verifying_no_schema_work_is_pending'
        # A code-only activation must find NOTHING to migrate. `showmigrations --plan` listing an unapplied entry, or
        # `makemigrations --check` wanting one, means the reviewed code and the live schema disagree — and the right
        # response is to stop, not to apply something nobody declared.
        credentials = PRIVATE / 'db-role-secrets/fresh-db-roles.json'
        word.checked_file(credentials, private=True, limit=16384)
        plan = output([str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'), '--credentials',
                       str(credentials), '--source', str(APP), '--role', 'migrator', '--', 'migrate', '--plan'], cwd=APP)
        require('[ ]' not in plan, 'The reviewed code expects a migration this activation does not declare.')
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'makemigrations', '--check', '--dry-run'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_permissions'] = word.static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('audio-submission-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment differs from release-only update.')
        result['stage'] = 'starting_and_verifying'
        word.systemd('start', helper)
        for attempt in range(60):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5',
                                             f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
                if all(h.get('release') == args.target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Release health failed.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        worker_after = worker_process()
        require(worker_after['systemd_start'] != worker_before['systemd_start']
                and worker_after['kernel_start_utc'] > worker_before['kernel_start_utc'],
                'The worker did not actually restart onto the reviewed code.')
        result['worker_after'] = worker_after
        result['media_tools_after'] = media_tools()
        require(result['media_tools_after'] == tools, 'The media tools changed during the activation.')
        # The declared delta is EMPTY. Everything below asserts that, and any difference is the finding.
        require(tables() == old_tables, 'A table was created or dropped.')
        require(schema() == result['schema_before'], 'The schema changed.')
        require(constraints() == result['constraints_before'], 'A constraint changed.')
        require(indexes() == result['indexes_before'], 'An index changed.')
        require(fingerprints(old_tables) == result['database_before'], 'Application data changed.')
        require(clinical_counts() == result['clinical_before'], 'A document, job, usage or audit count moved.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'],
                'Private bytes changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                     installed / 'build-proof.json', billing.PIN, inputs) == artifact,
                'Word runtime changed.')
        require(retained_unchanged(retained, word.retained_reports()) and previous.protected() == protected,
                'Retained or shared resources changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                    'Unit policy changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_existing_rows_identical=True,
                      no_schema_delta=True, all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after),
                      finished_at=datetime.now(timezone.utc).isoformat())
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, failure_message=str(error)[:400],
                      finished_at=datetime.now(timezone.utc).isoformat())
        # Fail closed: services stay stopped until the recorded state is inspected.
        try:
            word.systemd('stop', helper)
            result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False
            result['stop_failure_kind'] = type(stop_error).__name__
        if not result_path.exists():
            identity.private_write(result_path, result)
        else:
            identity.private_write(result_path.with_name(result_path.stem + '-publication-failure.json'), result)
        raise
    print('Audio-submission activation completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
