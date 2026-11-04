#!/usr/bin/env python3
"""Read-only GitHub release checker for z4tools."""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = 'z4d3l/z4tools'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=30'
LOCAL_DEV = '1.6.0'


def version_key(tag):
    s = tag.strip().lower().lstrip('v')
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:[-.]?(dev|alpha|beta|rc)(\d*)?)?', s)
    if not match:
        return None
    major, minor, patch, stage, num = match.groups()
    rank = {'dev': 0, 'alpha': 1, 'beta': 2, 'rc': 3, None: 4}[stage]
    return (int(major), int(minor), int(patch), rank, int(num or 0))


def fetch_releases():
    req = urllib.request.Request(API, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'z4tools-update-checker/1.6',
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.load(resp)
    if not isinstance(data, list):
        raise ValueError('unexpected github response')
    return [r for r in data if not r.get('draft') and r.get('tag_name')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', default=LOCAL_DEV, help='installed/development version (default: 1.6.0)')
    parser.add_argument('--json', metavar='PATH', help='save a json report')
    parser.add_argument('--no-pause', action='store_true', help='accepted for compatibility with other z4tools tools')
    args = parser.parse_args()
    print('=== z4tools v1.6 | update checker ===')
    print('read-only: checks public github releases; does not install updates\n')
    current_key = version_key(args.current)
    report = {'repository': REPO, 'current': args.current, 'status': 'unknown', 'latest': None, 'url': None}
    try:
        releases = fetch_releases()
        ranked = [(version_key(r['tag_name']), r) for r in releases]
        ranked = [(key, r) for key, r in ranked if key is not None]
        if not ranked:
            print('[info] no comparable published releases found')
            report['status'] = 'no_comparable_releases'
        else:
            latest_key, latest = max(ranked, key=lambda pair: pair[0])
            tag = latest['tag_name']
            report['latest'] = tag
            report['url'] = latest.get('html_url')
            print(f'local version: {args.current}')
            print(f'newest published release: {tag}')
            print(f'release page: {report["url"] or "unavailable"}')
            if current_key is None:
                report['status'] = 'unrecognized_local_version'
                print('[info] cannot compare your local version format')
            elif latest_key > current_key:
                report['status'] = 'update_available'
                print('[update] a newer published version is available')
            elif latest_key == current_key:
                report['status'] = 'up_to_date'
                print('[ok] local version matches the newest published release')
            else:
                report['status'] = 'ahead_of_releases'
                print('[ok] local development version is ahead of published releases')
            if latest.get('prerelease'):
                print('[info] newest published release is marked as a prerelease')
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        report['status'] = 'check_failed'
        report['error'] = str(exc)
        print(f'[warn] unable to check github: {exc}')
        print('check internet access and try again; no files were changed')
    if args.json:
        dest = Path(args.json).expanduser()
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            print(f'json report: {dest}')
        except OSError as exc:
            print(f'[error] could not write report: {exc}', file=sys.stderr)
            return 1
    return 0 if report['status'] != 'check_failed' else 1


if __name__ == '__main__':
    sys.exit(main())
