"""Mutation proofs for the RR2 guards (RR2-ACC-1, RR2-ACC-2, RR2-ACC-3, RR2-M1, RR2-L1).

Each mutant: its anchor asserted to occur exactly once, the application verified by reading the file back (the mutated
text present, the anchor gone, the sha256 changed), the killing tests run under a deadline, and the original bytes
restored in `finally` and compared by sha256 before the next mutant; a failed restore stops the run. An unmutated baseline
of every label set runs first and must pass, so a kill is never a pre-existing failure."""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/opt/meddoc-pro/.worktrees/v1-residuals/rebuild')
RUN = '/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/rr2repair/run-tests.sh'
EMAIL = ['core.tests.test_account_email_rule']
RACE = ['core.tests.test_invitation_account_race.OneInvitationAcceptedTwiceAtOnce']
LOST = ['core.tests.test_mapping_outcome_unknown']
RESULT = ['core.tests.test_mapping_assistance.MappingAssistance.test_a_charged_mapping_result_is_downloadable_under_the_generation_rule',
          'core.tests.test_mapping_assistance.MappingAssistance.test_an_uncharged_mapping_result_is_never_delivered']

MUTANTS = [
    ('RR2-M1 address length not bounded', 'core/forms.py',
     "    if len(email)>ACCOUNT_EMAIL_MAX_LENGTH: raise forms.ValidationError(ACCOUNT_EMAIL_TOO_LONG)\n", "    pass\n", EMAIL),
    ('RR2-M2 bound taken from the email column (254), not the username column', 'core/forms.py',
     "ACCOUNT_EMAIL_MAX_LENGTH=min(User._meta.get_field('username').max_length,User._meta.get_field('email').max_length,\n",
     "ACCOUNT_EMAIL_MAX_LENGTH=min(User._meta.get_field('email').max_length,\n", EMAIL),
    ('RR2-M3 bound off by one (150 refused)', 'core/forms.py',
     "    if len(email)>ACCOUNT_EMAIL_MAX_LENGTH:", "    if len(email)>=ACCOUNT_EMAIL_MAX_LENGTH:", EMAIL),
    ('RR2-M4 quoted local part accepted', 'core/forms.py',
     "    if '\"' in email: raise forms.ValidationError(ACCOUNT_EMAIL_QUOTED)\n", "    pass\n", EMAIL),
    ('RR2-M5 department acceptance: a used invitation under the lock answers 404 again', 'core/views.py',
     "                        if invite.accepted_at:messages.info(request,INVITATION_ALREADY_ACCEPTED);return redirect('login')\n",
     "                        if invite.accepted_at:raise Http404\n", RACE),
    ('RR2-M6 clinic acceptance: a used invitation under the lock answers 404 again', 'core/clinic_invitations.py',
     "                        if invitation.accepted_at:\n                            messages.info(request, INVITATION_ALREADY_ACCEPTED)\n"
     "                            return redirect('login')\n",
     "                        if invitation.accepted_at:\n                            raise Http404\n", RACE),
    ('RR2-M7 mapping handler: a committed outcome overwritten (no state check under the lock)', 'core/mapping_jobs.py',
     "            if state!='running':return outcome_already_recorded(job,exc,state)\n", "            pass\n", LOST),
    ('RR2-M8 mapping handler: decided without the job row lock', 'core/mapping_jobs.py',
     "            state=Job.objects.select_for_update().get(pk=job.pk).state\n", "            state=Job.objects.get(pk=job.pk).state\n", LOST),
    ('RR2-M9 mapping handler: an in-doubt settlement decided from the ledger', 'core/mapping_jobs.py',
     "    if in_doubt:return hold_for_reconciliation(job,exc,SETTLEMENT_UNKNOWN,action='mapping.reconciliation')\n", "    pass\n", LOST),
    ('RR2-M10 mapping handler: settlement doubt never computed', 'core/mapping_jobs.py',
     "        in_doubt=settling and commit_in_doubt(exc,carrier)\n", "        in_doubt=False\n", LOST),
    ('RR2-M11 mapping handler: settlement doubt never cleared (the adoption read as a settlement)', 'core/mapping_jobs.py',
     "        settle(job,cost,units,rates,provider,request_id,simulated,provider_resource_id=resource_id)\n        settling=False\n",
     "        settle(job,cost,units,rates,provider,request_id,simulated,provider_resource_id=resource_id)\n", LOST),
    ('RR2-M12 mapping handler: its own database failure re-raised, the job left running', 'core/mapping_jobs.py',
     "        except DatabaseError:\n            # The handler's own read", "        except ZeroDivisionError:\n            # The handler's own read", LOST),
    ('RR2-M13 job_result scoped by encounter only (the old query)', 'core/views.py',
     "models.Q(encounter__department__in=visible)|models.Q(mapping_version__template__department__in=visible)",
     "models.Q(encounter__department__in=visible)", RESULT),
    ('RR2-M14 job_result: any mapping job, any department', 'core/views.py',
     "models.Q(mapping_version__template__department__in=visible)),pk=pk)", "models.Q(mapping_version__isnull=False)),pk=pk)", RESULT),
    ('RR2-M15 job_result: uncharged output delivered', 'core/views.py',
     "    if not deliverable(job):raise Http404('Provider output is delivered only for charged requests and usable transcripts.')\n",
     "    pass\n", RESULT),
    ('RR2-M16 mapping page: no result link', 'core/mapping_views.py',
     "    for job in operations:job.deliverable=bool(job.result_path) and deliverable(job)\n",
     "    for job in operations:job.deliverable=False\n", RESULT),
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
    for name, labels in (('email', EMAIL), ('race', RACE), ('lost', LOST), ('result', RESULT)):
        result = run(labels)
        report['baseline'][name] = result
        print('baseline', name, result['summary'], flush=True)
        if result['exit'] != 0:
            print('BASELINE FAILED: stopping', json.dumps(result, indent=1))
            Path(sys.argv[1]).write_text(json.dumps(report, indent=1, ensure_ascii=False))
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
