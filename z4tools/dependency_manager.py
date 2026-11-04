#!/usr/bin/env python3
"""z4tools v1.6 dependency manager: read-only dependency audit and install guidance."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

DEPENDENCIES = (
    ('python', 'python', (3, 10), True, 'python'),
    ('node.js', 'node', (22,), True, 'nodejs'),
    ('git', 'git', None, True, 'git'),
    ('bash', 'bash', None, True, 'bash'),
    ('glslangvalidator', 'glslangValidator', None, False, 'glslang'),
    ('spirv-val', 'spirv-val', None, False, 'spirv-tools'),
)


def environment():
    if os.environ.get('TERMUX_VERSION') or 'com.termux' in str(Path.home()):
        return 'termux'
    if sys.platform == 'linux':
        try:
            info = Path('/etc/os-release').read_text(encoding='utf-8')
        except OSError:
            info = ''
        if re.search(r'(?m)^ID=(?:"?)(?:ubuntu|debian)(?:"?)$', info) or re.search(r'(?m)^ID_LIKE=.*\bdebian\b', info):
            return 'debian'
    return 'unsupported'


def version_of(cmd):
    try:
        p = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=6)
        if p.returncode:
            return None, 'version command failed'
        first = (p.stdout or p.stderr).strip().splitlines()
        if not first:
            return None, 'version output empty'
        output = first[0][:180]
        match = re.search(r'\b(?:v)?(\d+)\.(\d+)(?:\.(\d+))?', output)
        return (tuple(int(n or 0) for n in match.groups()) if match else None), output
    except (OSError, subprocess.TimeoutExpired):
        return None, 'version command unavailable'


def inspect(name, command, minimum, required, package):
    exe = sys.executable if command == 'python' else shutil.which(command)
    result = {'name': name, 'command': command, 'required': required, 'package': package,
              'path': str(exe) if exe else None, 'status': None, 'detail': ''}
    if not exe:
        result.update(status='missing', detail='not found on path')
        return result
    if command == 'python':
        version = tuple(sys.version_info[:3])
        detail = platform.python_version()
    else:
        version, detail = version_of(exe)
    result['detail'] = detail
    result['version'] = '.'.join(map(str, version)) if version else None
    if minimum and version is None:
        result['status'] = 'unknown'
    elif minimum and version[:len(minimum)] < minimum:
        result['status'] = 'outdated'
    else:
        result['status'] = 'ok'
    return result


def install_guidance(env, result):
    if env == 'termux':
        packages = {'python':'python', 'nodejs':'nodejs', 'git':'git', 'bash':'bash',
                    'glslang':'glslang', 'spirv-tools':'spirv-tools'}
        pkg = packages.get(result['package'])
        return f'pkg install {pkg}' if pkg else None
    if env == 'debian':
        # Do not claim apt provides a sufficiently new Node.js.
        if result['package'] == 'nodejs':
            return 'check node.js 22+ availability in your configured repositories before installing'
        return f'sudo apt install {result["package"]}'
    return None


def main():
    parser = argparse.ArgumentParser(description='read-only z4tools dependency audit')
    parser.add_argument('--json', metavar='PATH', help='write a json report to this path')
    parser.add_argument('--no-pause', action='store_true', help='accepted for compatibility')
    args = parser.parse_args()
    env = environment()
    results = [inspect(*item) for item in DEPENDENCIES]
    print('=== z4tools v1.6 | dependency manager ===')
    print(f'platform: {env} | read-only audit\n')
    for item in results:
        status = item['status']
        tag = {'ok':'ok', 'missing':'missing', 'outdated':'outdated', 'unknown':'unknown'}[status]
        requirement = 'required' if item['required'] else 'build-related'
        print(f'[{tag}] {item["name"]} ({requirement}) — {item["detail"]}')
        if status != 'ok':
            guidance = install_guidance(env, item)
            if guidance:
                print(f'    suggested: {guidance}')
    counts = {key: sum(item['status'] == key for item in results)
              for key in ('ok','missing','outdated','unknown')}
    print('\nsummary: ' + ', '.join(f'{v} {k}' for k,v in counts.items()))
    print('note: commands are suggestions only; no packages were changed.')
    if args.json:
        dest = Path(args.json).expanduser()
        report = {'schema_version':1, 'platform':env, 'results':results, 'summary':counts}
        try:
            # Refuse to overwrite an existing file or follow a symlink.
            with dest.open('x', encoding='utf-8') as handle:
                json.dump(report, handle, indent=2)
                handle.write('\n')
            print(f'json report saved: {dest}')
        except OSError as exc:
            print(f'could not save report: {exc}', file=sys.stderr)
            return 2
    return 0 if all(x['status'] == 'ok' or not x['required'] for x in results) else 1

if __name__ == '__main__':
    raise SystemExit(main())
