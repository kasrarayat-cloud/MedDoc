"""Read-only AWS metadata projection. No documents, resource names or provider messages are published.

Only the installed production operator calls this module. AWS CLI reads are bounded,
use isolated configuration, explicit assumed read roles, and automatic pagination;
a truncated result is unknown, never success. This is capture evidence, not a restore drill.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess

from .production_operator import OperatorError, private_json, require

MAX_ITEMS = 200
WINDOWS = {'RDS': 26 * 3600, 'EBS': 2 * 3600}
ENVIRONMENT = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'AWS_CONFIG_FILE': '/dev/null',
               'AWS_SHARED_CREDENTIALS_FILE': '/dev/null', 'AWS_IGNORE_CONFIGURED_ENDPOINT_URLS': 'true',
               'AWS_EC2_METADATA_V1_DISABLED': 'true', 'AWS_MAX_ATTEMPTS': '2', 'AWS_PAGER': ''}
KEYS = {'format', 'profile_sha256', 'database_arn', 'database_resource_id', 'state_volume_arn',
        'kms_key_arn', 'copy_kms_key_arn', 'source_vault_arn', 'copy_vault_arn',
        'source_read_role_arn', 'copy_read_role_arn'}


def stamp(value):
    require(isinstance(value, str), 'timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timestamp_timezone')
    return result


def fresh(value, now, seconds):
    age = (now - stamp(value)).total_seconds()
    return 0 <= age <= seconds


def validate(config, profile, receipt):
    require(isinstance(config, dict) and set(config) == KEYS and config['format'] == 1
            and config['profile_sha256'] == profile.sha256, 'backup_configuration')
    region = re.escape(profile.region)
    database = re.fullmatch(r'arn:aws:rds:' + region + r':([0-9]{12}):db:'
                            + re.escape(profile.database_instance), config['database_arn'])
    require(database is not None, 'backup_database')
    source = database[1]
    volume = re.fullmatch(r'arn:aws:ec2:' + region + ':' + source + r':volume/(vol-[a-f0-9]{17})',
                          config['state_volume_arn'])
    require(volume is not None and volume[1] == receipt.get('state_volume'), 'backup_volume')
    require(isinstance(config['database_resource_id'], str) and
            re.fullmatch(r'db-[A-Za-z0-9]+', config['database_resource_id']), 'backup_database_resource')
    copy = re.fullmatch(r'arn:aws:backup:' + region + r':([0-9]{12}):backup-vault:[A-Za-z0-9_-]{2,50}',
                        config['copy_vault_arn'])
    require(copy is not None and copy[1] != source, 'backup_copy_account')
    for prefix, account in (('source', source), ('copy', copy[1])):
        require(re.fullmatch(r'arn:aws:backup:' + region + ':' + account + r':backup-vault:[A-Za-z0-9_-]{2,50}',
                             config[prefix + '_vault_arn']), 'backup_vault')
        require(re.fullmatch(r'arn:aws:iam::' + account + r':role/[A-Za-z0-9_+=,.@/-]+',
                             config[prefix + '_read_role_arn']), 'backup_read_role')
        key = 'kms_key_arn' if prefix == 'source' else 'copy_kms_key_arn'
        require(re.fullmatch(r'arn:aws:kms:' + region + ':' + account + r':key/[a-f0-9-]{36}', config[key]), 'backup_key')
    return config


class AWS:
    def __init__(self, region):
        self.region = region
        self.environments = {}

    def request(self, scope, service, operation, *args):
        result = subprocess.run(['/usr/local/bin/aws', service, operation, '--region', self.region,
                                 '--output', 'json', '--no-cli-pager', '--no-cli-auto-prompt',
                                 '--cli-connect-timeout', '5', '--cli-read-timeout', '10', *args],
                                env=self.environments.get(scope, ENVIRONMENT), capture_output=True, timeout=25)
        require(result.returncode == 0 and len(result.stdout) <= 4 * 1024 * 1024, 'aws_read')
        data = json.loads(result.stdout)
        require(isinstance(data, dict) and not data.get('NextToken') and not data.get('Marker'), 'aws_incomplete')
        return data

    def assume(self, scope, arn):
        result = self.request(None, 'sts', 'assume-role', '--role-arn', arn,
                              '--role-session-name', 'quillmd-backup-status', '--duration-seconds', '900')
        credentials = result.get('Credentials', {})
        require(all(isinstance(credentials.get(key), str) and credentials[key]
                    for key in ('AccessKeyId', 'SecretAccessKey', 'SessionToken')), 'aws_credentials')
        self.environments[scope] = dict(ENVIRONMENT, AWS_ACCESS_KEY_ID=credentials['AccessKeyId'],
                                       AWS_SECRET_ACCESS_KEY=credentials['SecretAccessKey'],
                                       AWS_SESSION_TOKEN=credentials['SessionToken'])
        identity = self.request(scope, 'sts', 'get-caller-identity')
        account = arn.split(':')[4]
        expected = 'arn:aws:sts::' + account + ':assumed-role/' + arn.rsplit('/', 1)[1] + '/quillmd-backup-status'
        require(identity.get('Account') == account and identity.get('Arn') == expected, 'aws_identity')


def listed(aws, scope, operation, key, *args):
    # CLI paginates service pages; --max-items puts a finite bound on the final
    # merged list. Any continuation token means the bounded result is incomplete.
    response = aws.request(scope, 'backup', operation, *args, '--page-size', '100', '--max-items', str(MAX_ITEMS))
    require(not response.get('NextToken') and not response.get('Marker'), 'aws_incomplete')
    rows = response.get(key)
    require(isinstance(rows, list) and len(rows) <= MAX_ITEMS and all(isinstance(row, dict) for row in rows), 'aws_rows')
    return rows


def collect(profile, config, aws, now):
    """Pure projection aside from the injected read-only transport; exact resources are mandatory."""
    aws.assume('source', config['source_read_role_arn'])
    aws.assume('copy', config['copy_read_role_arn'])
    response = aws.request('source', 'rds', 'describe-db-instances', '--db-instance-identifier', profile.database_instance)
    rows = response.get('DBInstances', [])
    require(isinstance(rows, list) and len(rows) == 1, 'rds_count')
    db = rows[0]
    require(db.get('DBInstanceArn') == config['database_arn'] and db.get('DbiResourceId') == config['database_resource_id']
            and db.get('DBInstanceIdentifier') == profile.database_instance and db.get('DBName') == profile.database_name
            and db.get('Endpoint', {}).get('Address') == profile.database_host
            and db.get('Endpoint', {}).get('Port') == profile.database_port, 'rds_identity')
    require(db.get('StorageEncrypted') is True and db.get('KmsKeyId') == config['kms_key_arn']
            and db.get('Engine') == 'postgres', 'rds_protection')
    automated = aws.request('source', 'rds', 'describe-db-instance-automated-backups',
                            '--dbi-resource-id', config['database_resource_id'], '--page-size', '20', '--max-items', '2')
    require(not automated.get('NextToken') and not automated.get('Marker'), 'aws_incomplete')
    backups = automated.get('DBInstanceAutomatedBackups')
    require(isinstance(backups, list) and len(backups) == 1 and isinstance(backups[0], dict), 'rds_backup_count')
    backup = backups[0]
    require(backup.get('DBInstanceArn') == config['database_arn']
            and backup.get('DbiResourceId') == config['database_resource_id']
            and backup.get('DBInstanceIdentifier') == profile.database_instance
            and backup.get('Region') == profile.region and backup.get('Encrypted') is True
            and backup.get('KmsKeyId') == config['kms_key_arn'] and backup.get('Engine') == 'postgres', 'rds_backup_identity')
    # DBInstance has only LatestRestorableTime. The actual earliest/latest
    # window belongs to DBInstanceAutomatedBackup.RestoreWindow, not DBCluster.
    window = backup.get('RestoreWindow', {})
    earliest = stamp(window.get('EarliestTime'))
    latest = min(stamp(window.get('LatestTime')), stamp(db.get('LatestRestorableTime')))
    window_current = (db.get('DBInstanceStatus') == 'available' and db.get('BackupRetentionPeriod') == 35
                      and backup.get('Status') == 'active' and backup.get('BackupRetentionPeriod') == 35
                      and fresh(window.get('LatestTime'), now, 900) and fresh(db.get('LatestRestorableTime'), now, 900)
                      and earliest < latest <= now and (now - latest).total_seconds() <= 900)
    vault = aws.request('copy', 'backup', 'describe-backup-vault',
                        '--backup-vault-name', config['copy_vault_arn'].rsplit(':', 1)[1])
    require(vault.get('BackupVaultArn') == config['copy_vault_arn']
            and vault.get('EncryptionKeyArn') == config['copy_kms_key_arn'], 'copy_vault_identity')
    locked = vault.get('Locked') is True and bool(vault.get('LockDate')) and stamp(vault['LockDate']) <= now
    counts = {'expected_resources': 2, 'source_resources_current': 0, 'copy_resources_current': 0,
              'failed_backup_jobs': 0, 'failed_copy_jobs': 0, 'incomplete_backup_jobs': 0, 'incomplete_copy_jobs': 0}
    oldest_source = oldest_copy = None
    for resource_type, resource in (('RDS', config['database_arn']), ('EBS', config['state_volume_arn'])):
        age = WINDOWS[resource_type]
        after = (now - timedelta(seconds=age)).isoformat()
        jobs = listed(aws, 'source', 'list-backup-jobs', 'BackupJobs', '--by-resource-arn', resource,
                      '--by-backup-vault-name', config['source_vault_arn'].rsplit(':', 1)[1], '--by-created-after', after)
        copies = listed(aws, 'source', 'list-copy-jobs', 'CopyJobs', '--by-resource-arn', resource,
                        '--by-destination-vault-arn', config['copy_vault_arn'], '--by-created-after', after)
        point_sets = {}
        for scope in ('source', 'copy'):
            points = listed(aws, scope, 'list-recovery-points-by-backup-vault', 'RecoveryPoints',
                            '--backup-vault-name', config[scope + '_vault_arn'].rsplit(':', 1)[1],
                            '--by-resource-arn', resource, '--by-created-after', after)
            require(all(point.get('ResourceArn') == resource and point.get('ResourceType') == resource_type
                        and point.get('BackupVaultArn') == config[scope + '_vault_arn'] for point in points), 'recovery_point_identity')
            key = 'kms_key_arn' if scope == 'source' else 'copy_kms_key_arn'
            point_sets[scope] = {point['RecoveryPointArn']: point for point in points
                                 if point.get('RecoveryPointArn') and point.get('Status') in ('COMPLETED', 'AVAILABLE')
                                 and point.get('IsEncrypted') is True and point.get('EncryptionKeyArn') == config[key]
                                 and fresh(point.get('CreationDate'), now, age)}
        require(all(job.get('ResourceArn') == resource and job.get('ResourceType') == resource_type
                    and job.get('BackupVaultArn') == config['source_vault_arn'] for job in jobs), 'backup_job_identity')
        require(all(job.get('ResourceArn') == resource and job.get('ResourceType') == resource_type
                    and job.get('DestinationBackupVaultArn') == config['copy_vault_arn']
                    and job.get('SourceBackupVaultArn') == config['source_vault_arn'] for job in copies), 'copy_job_identity')
        for kind, found in (('backup', jobs), ('copy', copies)):
            counts['failed_' + kind + '_jobs'] += sum(job.get('State') in ('FAILED', 'ABORTED', 'EXPIRED', 'PARTIAL')
                or (job.get('State') == 'COMPLETED' and job.get('MessageCategory') != 'SUCCESS') for job in found)
            counts['incomplete_' + kind + '_jobs'] += sum(job.get('State') not in ('COMPLETED', 'FAILED', 'ABORTED', 'EXPIRED', 'PARTIAL') for job in found)
        good_jobs = [job for job in jobs if job.get('State') == 'COMPLETED' and job.get('MessageCategory') == 'SUCCESS'
                     and fresh(job.get('CreationDate'), now, age) and fresh(job.get('CompletionDate'), now, age)
                     and job.get('RecoveryPointArn') in point_sets['source']]
        sources = {job['RecoveryPointArn'] for job in good_jobs}
        good_copies = [job for job in copies if job.get('State') == 'COMPLETED' and job.get('MessageCategory') == 'SUCCESS'
                       and fresh(job.get('CreationDate'), now, age) and fresh(job.get('CompletionDate'), now, age)
                       and job.get('SourceRecoveryPointArn') in sources
                       and job.get('DestinationRecoveryPointArn') in point_sets['copy']]
        counts['source_resources_current'] += bool(sources)
        counts['copy_resources_current'] += bool(good_copies)
        if sources:
            latest_source = max(stamp(point_sets['source'][key]['CreationDate']) for key in sources)
            oldest_source = min(oldest_source, latest_source) if oldest_source else latest_source
        if good_copies:
            latest_copy = max(stamp(job['CompletionDate']) for job in good_copies)
            oldest_copy = min(oldest_copy, latest_copy) if oldest_copy else latest_copy
    current = (counts['source_resources_current'] == counts['copy_resources_current'] == 2 and locked and window_current
               and counts['failed_backup_jobs'] == counts['failed_copy_jobs'] == 0)
    details = {'provider': 'AWS Backup and RDS', **counts, 'capture_status': 'current' if current else 'attention_required',
               'copy_vault_lock_final': bool(locked), 'rds_window_current': window_current,
               'rds_earliest_restorable_utc': earliest.isoformat(), 'rds_latest_restorable_utc': latest.isoformat(),
               'oldest_current_capture_utc': oldest_source.isoformat() if oldest_source else 'unavailable',
               'oldest_current_copy_utc': oldest_copy.isoformat() if oldest_copy else 'unavailable',
               'restore_drill': 'separate evidence required', 'delivered_alerts': 'separate evidence required'}
    return {'condition': 'aws_capture_current' if current else 'aws_capture_attention', 'severity': 'warning', 'healthy': False,
            'action': ('Capture metadata is current. ' if current else 'Check backup coverage, copy failures, vault lock and RDS recovery window. ')
                      + 'Restore drills and delivered alerts require separate evidence.',
            'offsite': details, 'offsite_recovery_verified': False, 'outside_host_failure_detection': False,
            'clinical_content_included': False}, 0


def status(profile):
    try:
        require(os.geteuid() == 0 and Path(__file__).resolve().parents[1] == profile.app_root, 'operator_identity')
        receipt = private_json('/var/lib/quillmd-bootstrap/receipt.json')
        require(receipt.get('profile_sha256') == profile.sha256, 'installed_profile')
        config = validate(private_json(profile.operator_directory / 'backup-status.json'), profile, receipt)
        return collect(profile, config, AWS(profile.region), datetime.now(timezone.utc))
    except (OperatorError, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        # Provider stderr, configuration values, ARNs, tags and names never enter logs or DB.
        return {'condition': 'aws_backup_unknown', 'severity': 'failure', 'healthy': False,
                'action': 'AWS backup metadata is unavailable or incomplete. Check the operator configuration and read-role access.',
                'offsite': {'provider': 'AWS Backup and RDS', 'capture_status': 'unknown',
                            'restore_drill': 'separate evidence required'},
                'offsite_recovery_verified': False, 'outside_host_failure_detection': False,
                'clinical_content_included': False}, 1
