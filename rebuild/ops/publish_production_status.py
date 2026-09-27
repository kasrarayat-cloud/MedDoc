#!/usr/bin/env python3
"""Installed root operator entrypoint, never the web/worker launcher identity."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ops import deployment_profile
from ops.production_operator import private_json, require, OperatorError
from ops.service_launcher import prepare_production_environment, verified_ca_bundle, BoundaryFailure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        profile = deployment_profile.load_production()
        require(os.geteuid() == 0 and Path(__file__).resolve().parents[1] == profile.app_root, 'operator_identity')
        receipt = private_json('/var/lib/quillmd-bootstrap/receipt.json')
        require(receipt.get('profile_sha256') == profile.sha256
                and receipt.get('release_sha') == os.environ.get('QUILLMD_RELEASE_SHA'), 'installed_release')
        prepare_production_environment('worker', profile)
        verified_ca_bundle(profile.ca_bundle, profile.ca_bundle_sha256)
        command = [str(profile.app_root / '.venv/bin/python'), str(profile.app_root / 'manage.py'),
                   'publish_operations_status', '--profile', 'production']
        if args.dry_run:
            command.append('--dry-run')
        os.chdir(profile.app_root)
        os.execv(command[0], command)
    except (OperatorError, deployment_profile.ProfileError, BoundaryFailure, OSError, ValueError):
        print('Production status publication refused: operator or installed target could not be verified.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
