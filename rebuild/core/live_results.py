"""Read-only job/result snapshots shared by initial HTML, polling and enqueue replies."""
import hashlib
import json

from .jobs import public_error


def result_snapshot(encounter, jobs):
    latest=jobs[0] if jobs else None
    job=({'id':str(latest.pk),'kind':latest.kind,'state':latest.state,
          'display_error':public_error(latest),'revision':latest.revision} if latest else None)
    version={'revision':encounter.revision,'status':encounter.status,
             'answers':encounter.answers,'template_review':encounter.template_review,
             'latest_job':job}
    return {'encounter_id':str(encounter.pk),'revision':encounter.revision,
            'status':encounter.status,'pending':any(j.state in ('queued','running','reconciliation') for j in jobs),
            'latest_job':job,'result_version':hashlib.sha256(
                json.dumps(version,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def answer_preview(encounter):
    """Apply the same governing reader as the review page before displaying text."""
    from .generation import governance_for,as_currently_governed
    fields=encounter.template_version.fields
    governance=governance_for(encounter.notes,fields,
        [r['label'] for r in encounter.template_version.review_requirements],answers=encounter.answers)
    result=[]
    for field in fields:
        answer=encounter.answers.get(field['key'],{'text':'','status':'missing'})
        if encounter.status!='finalized':
            answer=as_currently_governed(governance,encounter.notes,{**field,**answer},
                bool(encounter.template_version.document_backend))
        result.append({'label':field['label'],'text':answer.get('text',''),'status':answer.get('status','missing')})
    return result
