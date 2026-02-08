#!/usr/bin/env python3
"""
Update Cloud Scheduler to run the optimizer during configured dayparting windows.

Reads dayparting settings from config.json (timezone, peak_hours, day_multipliers)
and generates a cron schedule aligned to those windows. Prints the exact gcloud
commands and optionally executes them if --apply is provided.

Usage:
  python scripts/update_scheduler_dayparting.py \
    --project amazon-ppc-474902 \
    --region us-central1 \
    --function-name amazon-ppc-optimizer \
    [--job-name amazon-ppc-optimizer-dayparting] \
    [--apply]

Notes:
  - Cloud Scheduler expects IANA timezone identifiers. Common mappings applied:
      US/Eastern -> America/New_York, US/Pacific -> America/Los_Angeles, etc.
  - If your function requires auth, ensure the scheduler service account can mint
    OIDC tokens and has permission to invoke the function.
"""

import argparse
import json
import os
import subprocess
import sys

IANA_MAP = {
    'US/Eastern': 'America/New_York',
    'US/Central': 'America/Chicago',
    'US/Mountain': 'America/Denver',
    'US/Pacific': 'America/Los_Angeles',
    'UTC': 'UTC',
}


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_cron(peak_hours, days):
    """Build a cron expression for every 15 minutes within peak hours and days."""
    hours_str = ','.join(str(h) for h in sorted(set(int(h) for h in peak_hours))) if peak_hours else '*'
    days_str = ','.join(days) if days else '*'
    # Every 15 minutes at selected hours and days
    return f"*/15 {hours_str} * * {days_str}"


def resolve_days(day_multipliers: dict) -> list:
    # Include days where multiplier >= 1.0; fallback to all days if empty
    days = []
    for k, v in (day_multipliers or {}).items():
        try:
            if float(v) >= 1.0:
                days.append(k.title()[:3].upper())  # MON, TUE, ...
        except Exception:
            pass
    if not days:
        days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    return days


def run(cmd: list, dry_run: bool):
    print('> ' + ' '.join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--region', default='us-central1')
    ap.add_argument('--function-name', default='amazon-ppc-optimizer')
    ap.add_argument('--job-name', default='amazon-ppc-optimizer-dayparting')
    ap.add_argument('--config-path', default=os.path.join(os.path.dirname(__file__), '..', 'config.json'))
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--oidc-service-account', default=None, help='Service account email to mint OIDC tokens')
    args = ap.parse_args()

    cfg = load_config(os.path.abspath(args.config_path))
    dp = cfg.get('dayparting', {})

    tz = IANA_MAP.get(str(dp.get('timezone', 'UTC')), 'UTC')
    peak_hours = dp.get('peak_hours', [])
    days = resolve_days(dp.get('day_multipliers', {}))
    cron = build_cron(peak_hours, days)

    # Resolve function URL
    describe_cmd = [
        'gcloud', 'functions', 'describe', args.function_name,
        '--region', args.region,
        '--project', args.project,
        '--gen2',
        '--format', 'value(serviceConfig.uri)'
    ]
    print('Resolving function URL...')
    try:
        url = subprocess.check_output(describe_cmd, text=True).strip()
    except Exception:
        url = ''
    if not url:
        print('WARNING: Failed to resolve function URL; set manually with --function-url')
        return 1

    # Create or update scheduler job
    # Prefer update; if it fails, create.
    base_cmd = [
        'gcloud', 'scheduler', 'jobs', 'update', 'http', args.job_name,
        '--schedule', cron,
        '--time-zone', tz,
        '--http-method', 'GET',
        '--uri', f"{url}?dry_run=false"
    ]
    if args.oidc_service_account:
        base_cmd += ['--oidc-service-account-email', args.oidc_service_account, '--oidc-token-audience', url]

    print(f"Config -> timezone={tz} peak_hours={peak_hours} days={days} cron='{cron}'")
    rc = run(base_cmd, not args.apply)
    if rc != 0:
        create_cmd = [
            'gcloud', 'scheduler', 'jobs', 'create', 'http', args.job_name,
            '--schedule', cron,
            '--time-zone', tz,
            '--http-method', 'GET',
            '--uri', f"{url}?dry_run=false",
            '--location', args.region,
            '--project', args.project,
        ]
        if args.oidc_service_account:
            create_cmd += ['--oidc-service-account-email', args.oidc_service_account, '--oidc-token-audience', url]
        rc = run(create_cmd, not args.apply)

    if rc == 0:
        print('Scheduler job configured.')
    return rc


if __name__ == '__main__':
    sys.exit(main())
