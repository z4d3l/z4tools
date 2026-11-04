#!/usr/bin/env python3
"""z4tools v1.6: read-only diagnostic bundle exporter."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

TOOLS = {
    'health_check': 'health_check.py',
    'compatibility': 'compatibility_check.py',
    'dependencies': 'dependency_manager.py',
    'dashboard': 'system_dashboard.py',
    'updates': 'update_checker.py',
}
SENSITIVE_KEYS = re.compile(r'(token|password|passwd|secret|api.?key|authorization|cookie|credential|private.?key)', re.I)
SENSITIVE_VALUE = re.compile(r'(?i)(bearer\s+\S+|gh[pousr]_[a-z0-9_]+|github_pat_[a-z0-9_]+|(?:token|password|secret|api[_-]?key)\s*[:=]\s*\S+)')

def scrub_string(value, home):
    value = value.replace(home, '~') if home else value
    value = SENSITIVE_VALUE.sub('[redacted]', value)
    return value

def scrub(obj, home):
    if isinstance(obj, dict):
        return {str(k): ('[redacted]' if SENSITIVE_KEYS.search(str(k)) else scrub(v, home)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(x, home) for x in obj]
    if isinstance(obj, str):
        return scrub_string(obj, home)
    return obj

def run_report(name, filename, directory, home):
    path = directory / filename
    if not path.is_file():
        return {'status': 'unavailable', 'reason': 'script not found'}
    with tempfile.TemporaryDirectory(prefix='z4diag-') as tmp:
        report = Path(tmp) / 'report.json'
        cmd = [sys.executable, str(path), '--json', str(report), '--no-pause']
        try:
            proc = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=35, input='', env={**os.environ, 'PYTHONUNBUFFERED': '1'})
        except subprocess.TimeoutExpired:
            return {'status': 'unavailable', 'reason': 'timed out after 35 seconds'}
        except OSError as exc:
            return {'status': 'unavailable', 'reason': scrub_string(str(exc), home)}
        if not report.is_file():
            return {'status': 'unavailable', 'reason': 'no json report generated', 'exit_code': proc.returncode}
        try:
            data = json.loads(report.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            return {'status': 'unavailable', 'reason': 'invalid json report', 'exit_code': proc.returncode}
        return {'status': 'collected', 'exit_code': proc.returncode, 'report': scrub(data, home)}

def main():
    parser = argparse.ArgumentParser(description='create a shareable, redacted z4tools diagnostic zip')
    parser.add_argument('--output', help='destination zip file (default: ~/z4tools-diagnostics-YYYYMMDD-HHMMSS.zip)')
    parser.add_argument('--no-pause', action='store_true', help='compatibility with other z4tools scripts')
    args = parser.parse_args()
    home = str(Path.home())
    directory = Path(__file__).resolve().parent
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    dest = Path(args.output).expanduser() if args.output else Path.home() / f'z4tools-diagnostics-{stamp}.zip'
    dest = dest.resolve()
    if dest.suffix.lower() != '.zip':
        parser.error('--output must end in .zip')
    dest.parent.mkdir(parents=True, exist_ok=True)
    print('=== z4tools v1.6 | export diagnostics ===')
    print('read-only collection; no raw logs, no automatic upload')
    results = {}
    for name, filename in TOOLS.items():
        print(f'checking {name}...', flush=True)
        results[name] = run_report(name, filename, directory, home)
        print(f'  {results[name]["status"]}')
    bundle = {
        'format': 'z4tools-diagnostics-v1',
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'privacy_note': 'best-effort redaction of home paths and common credential patterns; review before sharing',
        'reports': results,
    }
    overview = ['z4tools v1.6 diagnostic bundle', '', 'collection status:']
    overview += [f'- {name}: {result["status"]}' for name, result in results.items()]
    overview += ['', 'privacy: home directory paths and common credential fields are redacted.', 'review diagnostics.json before sharing; redaction is not guaranteed exhaustive.', 'no raw logs included.']
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('diagnostics.json', json.dumps(bundle, indent=2, ensure_ascii=False) + '\n')
        z.writestr('README.txt', '\n'.join(overview) + '\n')
    print(f'export created: {dest}')
    print('important: inspect the zip contents before sharing; automatic redaction cannot guarantee privacy.')
    return 0 if any(x['status'] == 'collected' for x in results.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
