"""Release-bound PostgreSQL integrity definitions for a production restore drill.

Expected bodies come from reviewed migration SQL, never the inspected database.
This is a point-in-time catalog check, not protection against a privileged owner.
Keep the migration parity test and this contract in the same reviewed change.
"""
import hashlib

CATALOG = '''SELECT c.relname,t.tgname,p.proname,t.tgtype,t.tgenabled,
    pg_get_triggerdef(t.oid),pn.nspname,p.prosrc,p.oid::regproc::text,
    p.pronargs,l.lanname,p.prorettype='pg_catalog.trigger'::regtype,
    p.prosecdef,p.proconfig,p.proisstrict,p.provolatile,p.proparallel
    FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
    JOIN pg_namespace n ON n.oid=c.relnamespace
    JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace
    JOIN pg_language l ON l.oid=p.prolang
    WHERE NOT t.tgisinternal AND n.nspname='public'
      AND (left(c.relname,5)='core_' OR left(p.proname,7)='quillmd')
    ORDER BY c.relname,t.tgname'''
CONTEXT = "SELECT current_schema(),current_setting('session_replication_role')"


def assess(rows, context, declared_count):
    """Return counts/fixed labels only; a replacement cannot choose its own expected identity."""
    expected = {(table, name): (function, kind) for table, name, function, kind in GUARDS}
    present = {}
    malformed = 0
    enabled = 0
    for row in rows:
        if len(row) != 17 or (row[0], row[1]) in present:
            malformed += 1
            continue
        present[(row[0], row[1])] = row
        enabled += row[4] in ('O', 'A')
    mismatched = 0
    for (table, name), (function, kind) in expected.items():
        row = present.get((table, name))
        if row is None:
            continue
        (_, _, actual_function, actual_kind, state, definition, namespace, body, sql_function,
         nargs, language, returns_trigger, security_definer, config, strict, volatility, parallel) = row
        event = {7:'INSERT', 23: 'INSERT OR UPDATE', 27: 'DELETE OR UPDATE', 19: 'UPDATE', 34: 'TRUNCATE', 31: 'INSERT OR DELETE OR UPDATE'}[kind]
        each = 'ROW' if kind & 1 else 'STATEMENT'
        wanted = (f'CREATE TRIGGER {name} BEFORE {event} ON public.{table} '
                  f'FOR EACH {each} EXECUTE FUNCTION {sql_function}()')
        valid = (actual_function == function and actual_kind == kind and state in ('O', 'A')
                 and definition == wanted and namespace == 'public' and nargs == 0
                 and language == 'plpgsql' and returns_trigger is True and security_definer is False
                 and config is None and strict is False and volatility == 'v' and parallel == 'u'
                 and isinstance(body, str)
                 and hashlib.sha256(body.encode()).hexdigest() == FUNCTION_SHA256[function])
        mismatched += not valid
    missing = len(expected.keys() - present.keys())
    unexpected = len(present.keys() - expected.keys())
    context_valid = list(context) == [('public', 'origin')]
    declaration_valid = type(declared_count) is int and declared_count == len(expected)
    return {'found': len(rows), 'enabled': enabled, 'expected': len(expected),
            'missing': missing, 'unexpected': unexpected, 'definition_mismatches': mismatched,
            'malformed': malformed, 'context_valid': context_valid,
            'declaration_matches_release': declaration_valid,
            'passed': not (missing or unexpected or mismatched or malformed)
                      and context_valid and declaration_valid}

FUNCTION_SHA256 = {
    'quillmd_import_manifest_guard': '12e845b63bcda1eea6e7beb04ccbfd43cae4a8d0be741f2be144c3781416f2a1',
    'quillmd_disposition_instruction': '0f5cb4e0ba4702422b07a889f9fd3e2f7c6b60b0c6e7e5bc2e324994e8d0e5bf',
    'quillmd_append_only': '8d5ec86a531621ac1de53c85109dfb5122f9142b1cb66dcfc377e0945d869764',
    'quillmd_batch_event_guard': 'b3ab717bf72d0b4f67ac36fb487ca491ae07b6846d78b0d216ab4b7864e7d29a',
    'quillmd_batch_guard': '46ea1e09a3598d289b5df9b114a4a4b8e74a314591a9abb6253510da78960c4f',
    'quillmd_batch_job_guard': '7c5d4fd727d326316f13c2d6b6b562fffe1144ff5cac18a016a0777d3d3608f5',
    'quillmd_batch_part_guard': '96683f9a1eec23b40f2f13b52198870c7405b1434c14daea6fb25b8a743536fb',
    # 0031: the 0003 body plus the confirmation gate (an unconfirmed contract v3 mapping starts no document) and the
    # hold (a document on one is never finalized).
    'quillmd_encounter_guard': '580e426b543a237ad47fd28b427b522eae312320259793b7f3052101d33c55ae',
    # 0032: the 0025 body plus one path, a hold or release replayed from the journal whose replay marker names this
    # exact row (its journaled custodian, or the replaying one only when that account is absent; a release only when
    # the two markers' signed entries name two custodians). Every other hold or release keeps 0025's rules.
    'quillmd_hold_instruction': '519d29c84134b93600a90c01293f7acf7a8d19e863b84484e3fb04bded606984',
    'quillmd_job_financial_guard': 'bbc4d75781636526a07bdbb1d4e705eb642a57c81776161b192dad88c1b8dd26',
    'quillmd_livemode_guard': '231e4fd6d5f23b0b38d9b4353add5b26cb31b62c571ccb0987e06705cf6b32cf',
    'quillmd_mapping_job_scope_guard': '0ebc170e576db208a2c8fea78fa2c46652aead48ef2a88af27bb21254cfc7954',
    'quillmd_mapping_template_guard': '8c7d8e4b6e59981318f27e5688dd8be86e3fefee3a0c33620c77e5d60235eea9',
    'quillmd_payment_evidence_guard': '4c4c2a8c49133266a8bf61181f1d6ca764ee8e98d5de262cb59eac99190520bd',
    'quillmd_preservation_no_truncate': '4b27c571c6ce810b1796def72d81d70d00aa9734bf176df9effe4c44c735d94b',
    'quillmd_preserve_clinical_row': '7a0571d09b15f3fbd37663478bf957d67bbf2e0491c63e93458905306749cf82',
    'quillmd_reconciliation_evidence_guard': 'e25b0f7d604223287b30f2955bc167c34ce889460ac612757d88a93b1f828bdd',
    'quillmd_refuse_truncate': '1f42decb7308aa5ee0a2f5425bd3ca1e8edf244ef3ff5a3faffe0c1dd6b4f447',
    'quillmd_webhook_evidence_guard': '797abc46124f7f810165cd8058731387c10bbad141f840f8fddc5b0b5f732f8c',
    'quillmd_disposition_reference': 'd8091118ccf9ad4ed1e00604ce628216fb5f5b3b36e47125a5319486f344cd97',
    'quillmd_disposition_target': '9f3949efe49112a1f02594dcfb53dd71ba8379131829578988840cc6230588c1',
    'quillmd_execution_instruction': '417bcc1b439787326df46c391db750fbaa5e5d8f65e8ea69c1b26e0a109c3aa1',
    'quillmd_restore_import': '503a47b91f8c453a0452f3b87b4e30a0d49f4f547e36862008812ac7dd3332bb',
    # 0032: a hold replayed 'target_absent' applies when its target row is inserted again with its id.
    'quillmd_restore_absent_hold': '19ba238b0a2ed70262a2a1f03e10186f324db8a5d6c5b87f7284086e740b420a',
    # 0033: redaction requests and tombstones, a redacted document's emptiness, and no new work for it.
    'quillmd_redaction_guard': '06511e5c9b0d09a54fca7316aa95bcc8bef54c81a567771b9f972410b5048b73',
    # 0034: the coding ledger: frozen finalized codes, immutable suggestion identity, accepted codes never deleted.
    'quillmd_coding_guard': '28d3e14e2b8f4e21f60c4674951625e62866c242948b0ce6fcaf8ba6d8e1db71',
    # 0036/0037: append-only clinical transcript reviews and refusal of false redaction around them.
    'quillmd_transcript_review_guard': '4e0d9b0e69eb9f678f0d5c95bd086cd4236442a3f1da8a4edf7e531f05f6dfcd',
    'quillmd_transcript_redaction_guard': 'f27d1b0038852f1f8e3cb207151455eeb780f0a4fc08ccb82cc91d13f75bef81',
}

GUARDS = (
    ('core_templateversion', 'quillmd_import_manifest_guard', 'quillmd_import_manifest_guard', 7),
    ('core_auditevent', 'audit_append_only', 'quillmd_append_only', 27),
    ('core_codesuggestion', 'code_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_codesuggestion', 'code_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_costreconciliation', 'reconciliation_evidence_immutable', 'quillmd_reconciliation_evidence_guard', 27),
    ('core_department', 'department_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_department', 'department_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_encounter', 'encounter_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_encounter', 'encounter_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_encounter', 'encounter_scope', 'quillmd_encounter_guard', 23),
    ('core_generationbatch', 'generation_batch_immutable', 'quillmd_batch_guard', 27),
    ('core_generationbatch', 'generation_batch_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_generationbatch', 'generationbatch_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_generationbatchevent', 'generation_batch_event_scope', 'quillmd_batch_event_guard', 7),
    ('core_generationbatchevent', 'generationbatchevent_append_only', 'quillmd_append_only', 27),
    ('core_generationbatchevent', 'generationbatchevent_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_generationbatchpart', 'generation_batch_part_scope', 'quillmd_batch_part_guard', 7),
    ('core_generationbatchpart', 'generationbatchpart_append_only', 'quillmd_append_only', 27),
    ('core_generationbatchpart', 'generationbatchpart_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_generationbatchresponse', 'generationbatchresponse_append_only', 'quillmd_append_only', 27),
    ('core_generationbatchresponse', 'generationbatchresponse_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_job', 'generation_batch_job_identity', 'quillmd_batch_job_guard', 19),
    ('core_job', 'job_financial_immutable', 'quillmd_job_financial_guard', 19),
    ('core_job', 'job_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_job', 'job_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_job', 'mapping_job_scope', 'quillmd_mapping_job_scope_guard', 23),
    ('core_ledgerentry', 'ledger_append_only', 'quillmd_append_only', 27),
    ('core_ledgerentry', 'ledger_no_truncate', 'quillmd_refuse_truncate', 34),
    ('core_mappingconfirmation', 'mapping_confirmation_append_only', 'quillmd_append_only', 27),
    ('core_patient', 'patient_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_patient', 'patient_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_payment', 'payment_evidence_immutable', 'quillmd_payment_evidence_guard', 27),
    ('core_payment', 'payment_no_truncate', 'quillmd_refuse_truncate', 34),
    ('core_preservedfile', 'preserved_file_append_only', 'quillmd_append_only', 27),
    ('core_preservedfile', 'preserved_file_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_preservedrecord', 'preserved_record_append_only', 'quillmd_append_only', 27),
    ('core_preservedrecord', 'preserved_record_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_providerreceipt', 'receipt_append_only', 'quillmd_append_only', 27),
    ('core_retentionhold', 'retention_hold_append_only', 'quillmd_append_only', 27),
    ('core_retentionhold', 'retention_hold_insert', 'quillmd_hold_instruction', 7),
    ('core_retentionhold', 'retention_hold_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_retentionholdrelease', 'retention_release_append_only', 'quillmd_append_only', 27),
    ('core_retentionholdrelease', 'retention_release_insert', 'quillmd_hold_instruction', 7),
    ('core_retentionholdrelease', 'retention_release_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_template', 'mapping_template_source', 'quillmd_mapping_template_guard', 19),
    ('core_template', 'template_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_template', 'template_preservation', 'quillmd_preserve_clinical_row', 27),
    ('core_templateversion', 'mapping_immutable', 'quillmd_append_only', 27),
    ('core_usage', 'usage_append_only', 'quillmd_append_only', 27),
    ('core_webhookevent', 'webhook_evidence_immutable', 'quillmd_webhook_evidence_guard', 27),
    ('core_webhookevent', 'webhook_livemode_immutable', 'quillmd_livemode_guard', 19),
    ('core_webhookevent', 'webhook_no_truncate', 'quillmd_refuse_truncate', 34),
    ('core_dispositionplan', 'dispositionplan_immutable', 'quillmd_append_only', 27),
    ('core_dispositionplan', 'dispositionplan_insert', 'quillmd_disposition_instruction', 7),
    ('core_dispositionplan', 'dispositionplan_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_dispositionrequest', 'dispositionrequest_immutable', 'quillmd_append_only', 27),
    ('core_dispositionrequest', 'dispositionrequest_insert', 'quillmd_disposition_instruction', 7),
    ('core_dispositionrequest', 'dispositionrequest_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_dispositionreview', 'dispositionreview_immutable', 'quillmd_append_only', 27),
    ('core_dispositionreview', 'dispositionreview_insert', 'quillmd_disposition_instruction', 7),
    ('core_dispositionreview', 'dispositionreview_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_restorepreparation', 'restorepreparation_immutable', 'quillmd_append_only', 27),
    ('core_restorepreparation', 'restorepreparation_insert', 'quillmd_disposition_instruction', 7),
    ('core_restorepreparation', 'restorepreparation_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_codesuggestion', 'code_disposition', 'quillmd_disposition_reference', 23),
    ('core_dispositionapproval', 'dispositionapproval_immutable', 'quillmd_append_only', 27),
    ('core_dispositionapproval', 'dispositionapproval_insert', 'quillmd_execution_instruction', 7),
    ('core_dispositionapproval', 'dispositionapproval_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_dispositioncompletion', 'dispositioncompletion_immutable', 'quillmd_append_only', 27),
    ('core_dispositioncompletion', 'dispositioncompletion_insert', 'quillmd_execution_instruction', 7),
    ('core_dispositioncompletion', 'dispositioncompletion_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_dispositioninstruction', 'dispositioninstruction_immutable', 'quillmd_append_only', 27),
    ('core_dispositioninstruction', 'dispositioninstruction_insert', 'quillmd_execution_instruction', 7),
    ('core_dispositioninstruction', 'dispositioninstruction_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_dispositionpolicyadmission', 'dispositionpolicyadmission_immutable', 'quillmd_append_only', 27),
    ('core_dispositionpolicyadmission', 'dispositionpolicyadmission_insert', 'quillmd_execution_instruction', 7),
    ('core_dispositionpolicyadmission', 'dispositionpolicyadmission_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_dispositiontombstone', 'dispositiontombstone_immutable', 'quillmd_append_only', 27),
    ('core_dispositiontombstone', 'dispositiontombstone_insert', 'quillmd_execution_instruction', 7),
    ('core_dispositiontombstone', 'dispositiontombstone_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_encounter', 'encounter_disposition', 'quillmd_disposition_target', 31),
    ('core_generationbatch', 'batch_disposition', 'quillmd_disposition_reference', 23),
    ('core_job', 'job_disposition', 'quillmd_disposition_reference', 23),
    ('core_retentionholdreplay', 'retentionholdreplay_append_only', 'quillmd_append_only', 27),
    ('core_retentionholdreplay', 'retentionholdreplay_insert', 'quillmd_restore_import', 7),
    ('core_retentionholdreplay', 'retentionholdreplay_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_restoreadmission', 'restoreadmission_append_only', 'quillmd_append_only', 27),
    ('core_restoreadmission', 'restoreadmission_insert', 'quillmd_restore_import', 7),
    ('core_restoreadmission', 'restoreadmission_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_organization', 'organization_absent_hold', 'quillmd_restore_absent_hold', 7),
    ('core_department', 'department_absent_hold', 'quillmd_restore_absent_hold', 7),
    ('core_patient', 'patient_absent_hold', 'quillmd_restore_absent_hold', 7),
    ('core_encounter', 'encounter_absent_hold', 'quillmd_restore_absent_hold', 7),
    ('core_redactionrequest', 'redactionrequest_insert', 'quillmd_redaction_guard', 7),
    ('core_redactionrequest', 'redactionrequest_append_only', 'quillmd_append_only', 27),
    ('core_redactionrequest', 'redactionrequest_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_redactiontombstone', 'redactiontombstone_insert', 'quillmd_redaction_guard', 7),
    ('core_redactiontombstone', 'redactiontombstone_append_only', 'quillmd_append_only', 27),
    ('core_redactiontombstone', 'redactiontombstone_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_encounter', 'encounter_redaction', 'quillmd_redaction_guard', 23),
    ('core_job', 'job_redaction', 'quillmd_redaction_guard', 7),
    ('core_generationbatch', 'batch_redaction', 'quillmd_redaction_guard', 7),
    ('core_codesuggestion', 'code_redaction', 'quillmd_redaction_guard', 7),
    ('core_codeset', 'terminology_release_append_only', 'quillmd_append_only', 27),
    ('core_codeset', 'terminology_release_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_code', 'terminology_code_append_only', 'quillmd_append_only', 27),
    ('core_code', 'terminology_code_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_codesuggestion', 'code_ledger', 'quillmd_coding_guard', 31),
    ('core_transcriptreview', 'transcript_review_preservation', 'quillmd_transcript_review_guard', 31),
    ('core_transcriptreview', 'transcript_review_no_truncate', 'quillmd_preservation_no_truncate', 34),
    ('core_redactiontombstone', 'redactiontombstone_transcript', 'quillmd_transcript_redaction_guard', 7),
)
