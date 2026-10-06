"""Immutable clinician transcript edits and explicit default-patient context.

Additive for code rollback. Reversal refuses while any review evidence exists.
The clinical text is protected by an append-only table and preservation lock;
there is no clinical text in ordinary audit metadata or a new orphan file.
"""
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations,models
from django.db.migrations.exceptions import IrreversibleError

SQL='''CREATE FUNCTION quillmd_transcript_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE scoped_encounter uuid; source_version integer; encounter_state text; dept uuid; source_text text;
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed' THEN
  RAISE EXCEPTION 'Transcript preservation requires read committed isolation';
 END IF;
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Transcript reviews are append-only'; END IF;
 -- Match encounter mutation/hold ordering: row first, preservation lock second.
 SELECT revision,status,department_id,notes INTO source_version,encounter_state,dept,source_text FROM core_encounter
  WHERE id=NEW.encounter_id FOR UPDATE;
 PERFORM pg_advisory_xact_lock(716849203517);
 SELECT encounter_id INTO scoped_encounter FROM core_job
  WHERE id=NEW.job_id AND kind='transcription' AND state='succeeded'
    AND config->>'transcript_review_required'='true' AND result_sha256=NEW.result_sha256;
 IF scoped_encounter IS DISTINCT FROM NEW.encounter_id OR source_version IS DISTINCT FROM NEW.source_revision
    OR encounter_state IN ('finalized','redacted') OR NEW.span_end<=NEW.span_start
    OR NEW.span_end-NEW.span_start<>char_length(NEW.reviewed_text)
    OR NEW.span_end>char_length(source_text)
    OR substring(source_text FROM NEW.span_start+1 FOR NEW.span_end-NEW.span_start) IS DISTINCT FROM NEW.reviewed_text
    OR NEW.source_sha256!~'^[0-9a-f]{64}$' OR NEW.raw_sha256!~'^[0-9a-f]{64}$'
    OR NEW.result_sha256!~'^[0-9a-f]{64}$' OR NEW.reviewed_sha256!~'^[0-9a-f]{64}$'
 THEN RAISE EXCEPTION 'Transcript review requires the exact usable source and current notes'; END IF;
 IF NOT EXISTS(SELECT 1 FROM core_membership m JOIN core_user u ON u.id=m.user_id
   WHERE m.user_id=NEW.reviewed_by_id AND m.department_id=dept AND m.active AND u.is_active
     AND (NOT NEW.patient_context OR m.role IN ('owner','clinician')))
 THEN RAISE EXCEPTION 'Transcript context requires an authorized clinician'; END IF;
 IF NEW.patient_context AND NEW.context_token='' THEN RAISE EXCEPTION 'Transcript context must be evidence-bound'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER transcript_review_preservation BEFORE INSERT OR UPDATE OR DELETE ON core_transcriptreview
 FOR EACH ROW EXECUTE FUNCTION quillmd_transcript_review_guard();
CREATE TRIGGER transcript_review_no_truncate BEFORE TRUNCATE ON core_transcriptreview
 FOR EACH STATEMENT EXECUTE FUNCTION quillmd_preservation_no_truncate();'''
REVERSE='''DROP TRIGGER transcript_review_no_truncate ON core_transcriptreview;
DROP TRIGGER transcript_review_preservation ON core_transcriptreview;
DROP FUNCTION quillmd_transcript_review_guard();'''

def refuse_evidence(apps,schema_editor):
    if apps.get_model('core','TranscriptReview').objects.exists():
        raise IrreversibleError('Transcript review evidence cannot be removed; use code rollback without schema reversal.')

class Migration(migrations.Migration):
    dependencies=[('core','0035_import_manifest'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='TranscriptReview',fields=[
        ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
        ('created_at',models.DateTimeField(auto_now_add=True)),
        ('source_revision',models.PositiveIntegerField()),('source_sha256',models.CharField(max_length=64)),
        ('raw_sha256',models.CharField(max_length=64)),('result_sha256',models.CharField(max_length=64)),
        ('reviewed_sha256',models.CharField(max_length=64)),('reviewed_text',models.TextField()),
        ('span_start',models.PositiveIntegerField()),('span_end',models.PositiveIntegerField()),
        ('patient_context',models.BooleanField(default=False)),('context_token',models.TextField(blank=True)),
        ('encounter',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='transcript_reviews',to='core.encounter')),
        ('job',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='transcript_reviews',to='core.job')),
        ('reviewed_by',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='+',to=settings.AUTH_USER_MODEL)),
    ],options={'constraints':[models.UniqueConstraint(fields=('job','source_revision'),name='transcript_review_source_once')]}),
        migrations.RunSQL(SQL,REVERSE),migrations.RunPython(migrations.RunPython.noop,refuse_evidence)]
