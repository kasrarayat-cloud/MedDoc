"""Mutation proofs for the RS-1/2/3/5 and RA-LOW-1 guards. Each mutant: anchor asserted to occur exactly once, application
verified by reading the file back, the killing tests run under a deadline, and the original bytes restored in `finally`
and compared by sha256 before the next mutant. An unmutated baseline of every label set runs first and must pass."""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/opt/meddoc-pro/.worktrees/v1-residuals/rebuild')
RUN = '/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/pyenv/run-tests.sh'
JOBS = ['core.tests.test_settlement_outcome_unknown', 'core.tests.test_settlement_database_error',
        'core.tests.test_billing_policy.AbsorbedPlatformFailure']
MAPPING = ['core.tests.test_mapping_assistance.MappingAssistance.test_a_reversal_that_fails_holds_the_mapping_job_with_its_key_and_charge']
EMAIL = ['core.tests.test_account_email_rule']

OLD_MAPPING_BLOCK = """        absorbing=False
        try:
            with transaction.atomic():
                job.save(update_fields=['state','error','finished_at','request_key'])
                if unsent:release(job)
                # ⚠️ In the same transaction as the failed state (RS-3, as core.jobs): a reversal that fails never leaves a
                # 'failed' job charged with its request key freed, which let the same mapping be bought again.
                if known and not declined:absorbing=True;absorb_failed_job(job);absorbing=False
        except Exception as absorb_error:
            if not absorbing:raise
            from .jobs import ABSORPTION_FAILED, hold_for_reconciliation
            hold_for_reconciliation(job,exc,ABSORPTION_FAILED,billing='platform_failure',absorb_error=absorb_error,
                                    action='mapping.reconciliation')
            return True
"""
REVERTED_MAPPING_BLOCK = """        with transaction.atomic():
            job.save(update_fields=['state','error','finished_at','request_key'])
            if unsent:release(job)
        if known and not declined:
            try:absorb_failed_job(job)
            except Exception as absorb_error:
                audit(job.user,'usage.absorb_failed',job.pk,department=job.department,error_class=type(absorb_error).__name__)
"""

MUTANTS = [
    ('RS1-M1 in-doubt settlement treated as established', 'core/jobs.py',
     "        in_doubt=settling and commit_in_doubt(exc,carrier)\n", "        in_doubt=False\n", JOBS),
    ('RS1-M2 a COMMIT the server refused counted as in doubt (connection identity ignored)', 'core/jobs.py',
     "    if not isinstance(error,DatabaseError) or carrier is None or connection.connection is carrier: return False\n",
     "    if not isinstance(error,DatabaseError) or carrier is None: return False\n", JOBS),
    ('RS1-M3 a statement error counted as in doubt (commit frame ignored)', 'core/jobs.py',
     "        if trace.tb_frame.f_code is commit: return True\n", "        if trace.tb_frame.f_code is not None: return True\n", JOBS),
    ('RS2-M4 the handler failure re-raised instead of held', 'core/jobs.py',
     "            usable_connection()\n            hold_for_reconciliation(job,exc,OUTCOME_UNRECORDED)\n",
     "            raise\n", JOBS),
    ('RS2-M5 no connection repair before the handler reads', 'core/jobs.py',
     "    if not connection.in_atomic_block: connection.close_if_unusable_or_obsolete()\n", "    return None\n", JOBS),
    ('RS1-M6 no committed-state guard under the job lock', 'core/jobs.py',
     "            # this lock until it ends, and one that committed (the adoption) has already ended the job.\n"
     "            state=Job.objects.select_for_update().get(pk=job.pk).state\n"
     "            if state!='running': return outcome_already_recorded(job,exc,state)\n",
     "            # this lock until it ends, and one that committed (the adoption) has already ended the job.\n"
     "            state=Job.objects.select_for_update().get(pk=job.pk).state\n", JOBS),
    ('RS3-M7 a failed reversal swallowed, the failed state kept (the old handler)', 'core/jobs.py',
     "                absorbing=True; absorb_failed_job(job); absorbing=False\n",
     "                try: absorb_failed_job(job)\n                except Exception: pass\n", JOBS),
    ('RS5-M8 every fixture failure called a validation failure', 'core/jobs.py',
     "                job.error=FIXTURE_VALIDATION if isinstance(exc,ValidationError) else FIXTURE_PLATFORM_ERROR.format(\n",
     "                job.error=FIXTURE_VALIDATION if True else FIXTURE_PLATFORM_ERROR.format(\n", JOBS),
    ('RS3-M9 mapping: the old handler (reversal outside the failed-state transaction, failure swallowed)', 'core/mapping_jobs.py',
     OLD_MAPPING_BLOCK, REVERTED_MAPPING_BLOCK, MAPPING),
    ('RA-M10 non-ASCII addresses accepted', 'core/forms.py',
     "    if not email.isascii(): raise forms.ValidationError(ACCOUNT_EMAIL_NOT_ASCII)\n", "    pass\n", EMAIL),
    ('RA-M11 lowercased before the ASCII check (the Kelvin sign folds to k)', 'core/forms.py',
     "    email=(value or '').strip()\n    if not email.isascii(): raise forms.ValidationError(ACCOUNT_EMAIL_NOT_ASCII)\n    return email.lower()\n",
     "    email=(value or '').strip().lower()\n    if not email.isascii(): raise forms.ValidationError(ACCOUNT_EMAIL_NOT_ASCII)\n    return email\n", EMAIL),
    ('RA-M12 no refusal of an address the lookup already answers', 'core/forms.py',
     "        if account_created_meanwhile(email): raise forms.ValidationError(ACCOUNT_EXISTS)\n", "        pass\n", EMAIL),
    ('RA-M13 department invitation issued without the rule', 'core/forms.py',
     "    def clean_email(self): return account_email(self.cleaned_data['email'])\nclass DepartmentForm",
     "class DepartmentForm", EMAIL),
    ('RA-M14 clinic invitation issued without the rule (the old clean_email)', 'core/forms.py',
     "    def clean_email(self): return account_email(self.cleaned_data['email'])\nclass MfaResetForm",
     "    def clean_email(self): return self.cleaned_data['email'].lower().strip()\nclass MfaResetForm", EMAIL),
    ('RA-M15 first administrator created without the rule', 'core/management/commands/bootstrap_first_admin.py',
     "            require(canonical == email, 'first_admin_email')\n", "            pass\n", EMAIL),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(labels, deadline=900):
    started = time.monotonic()
    try:
        done = subprocess.run([RUN, *labels, '-v', '2'], capture_output=True, text=True, timeout=deadline)
        output = done.stdout + done.stderr
        code = done.returncode
    except subprocess.TimeoutExpired as expired:
        output = (expired.stdout or b'').decode() if isinstance(expired.stdout, bytes) else (expired.stdout or '')
        code = 'timeout'
    failures = []
    for block in re.split(r'\n={20,}\n', output):
        head = re.match(r'(FAIL|ERROR): (\S+) \(([^)]*)\)( \(([^)]*)\))?', block.strip())
        if head:
            lines = [line for line in block.strip().splitlines() if re.match(r'^[A-Za-z_.]+(Error|Exception|Exit)\b', line)]
            failures.append({'kind': head.group(1), 'test': head.group(2), 'subtest': head.group(5),
                             'raised': lines[-1][:160] if lines else ''})
    summary = [line for line in output.splitlines() if re.match(r'^(Ran \d+|OK|FAILED)', line)]
    return {'exit': code, 'seconds': round(time.monotonic() - started, 1), 'summary': summary, 'failures': failures}


def main():
    report = {'baseline': {}, 'mutants': []}
    for name, labels in (('jobs', JOBS), ('mapping', MAPPING), ('email', EMAIL)):
        result = run(labels)
        report['baseline'][name] = result
        print('baseline', name, result['summary'], flush=True)
        if result['exit'] != 0:
            print('BASELINE FAILED: stopping', json.dumps(result, indent=1))
            sys.exit(2)
    for name, relative, old, new, labels in MUTANTS:
        path = ROOT / relative
        original = path.read_bytes()
        before = sha(path)
        text = original.decode('utf-8')
        count = text.count(old)
        entry = {'mutant': name, 'file': relative, 'anchor_occurrences': count, 'sha256_before': before}
        if count != 1:
            entry['result'] = 'NOT APPLIED (anchor count %d)' % count
            report['mutants'].append(entry)
            print(name, entry['result'], flush=True)
            continue
        try:
            path.write_text(text.replace(old, new), encoding='utf-8')
            applied = path.read_text(encoding='utf-8')
            entry['applied'] = new in applied and applied.count(old) == 0 and sha(path) != before
            if not entry['applied']:
                entry['result'] = 'NOT APPLIED (read-back)'
            else:
                result = run(labels)
                entry.update(result)
                entry['result'] = 'KILLED' if result['exit'] != 0 and result['failures'] else 'SURVIVED'
        finally:
            path.write_bytes(original)
            entry['sha256_after_restore'] = sha(path)
            entry['restored'] = entry['sha256_after_restore'] == before
        report['mutants'].append(entry)
        print(name, entry.get('result'), 'restored=%s' % entry['restored'],
              [f"{f['kind']} {f['test']}{' '+f['subtest'] if f['subtest'] else ''}: {f['raised'][:70]}" for f in entry.get('failures', [])],
              flush=True)
        if not entry['restored']:
            print('RESTORE FAILED: stopping')
            break
    Path(sys.argv[1]).write_text(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
