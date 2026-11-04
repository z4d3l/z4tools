#!/usr/bin/env python3
"""z4tools v1.6 health check. Read-only, stdlib only."""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('Z4TOOLS_LAUNCHER_DIR', str(Path.home() / 'GPUBrewLauncher'))).expanduser()


def result(name, status, detail, suggestion=None):
    return dict(name=name, status=status, detail=detail, suggestion=suggestion)


def check_file(name, path, required=True):
    if not path.is_file():
        return result(name, 'fail' if required else 'info', 'missing: ' + str(path), 'check the launcher installation' if required else None)
    if not os.access(path, os.R_OK):
        return result(name, 'fail', 'not readable: ' + str(path), 'check file permissions')
    return result(name, 'ok', 'present and readable')


def check_syntax(name, path, kind):
    if not path.is_file():
        return result(name, 'fail', 'source file missing')
    if kind == 'python':
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            return result(name, 'ok', 'valid python syntax')
        except (OSError, UnicodeError, SyntaxError) as exc:
            return result(name, 'fail', str(exc)[:180])
    node = shutil.which('node')
    if not node:
        return result(name, 'unknown', 'node unavailable; cannot check javascript')
    try:
        p = subprocess.run([node, '--check', str(path)], capture_output=True, text=True, timeout=15)
        if p.returncode == 0:
            return result(name, 'ok', 'valid javascript syntax')
        return result(name, 'fail', (p.stderr or p.stdout).strip()[-180:] or 'node --check failed')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result(name, 'unknown', str(exc)[:180])


def check_disk():
    try:
        usage = shutil.disk_usage(ROOT if ROOT.exists() else Path.home())
        free_gib = usage.free / (1024 ** 3)
        if free_gib < 0.5:
            return result('available storage', 'warn', f'{free_gib:.2f} gib free', 'consider freeing storage before builds')
        return result('available storage', 'ok', f'{free_gib:.2f} gib free')
    except OSError as exc:
        return result('available storage', 'unknown', str(exc))


def check_tool(name, executable, required=True):
    path = shutil.which(executable)
    if path:
        return result(name, 'ok', path)
    return result(name, 'fail' if required else 'warn', 'not found on path', 'install dependency using the dependency manager')


def check_git():
    if not ROOT.is_dir():
        return result('launcher git status', 'unknown', 'launcher directory missing')
    if not shutil.which('git'):
        return result('launcher git status', 'unknown', 'git unavailable')
    try:
        p = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain=v1', '--untracked-files=normal'], capture_output=True, text=True, timeout=15)
        if p.returncode:
            return result('launcher git status', 'info', 'launcher is not a readable git worktree')
        lines = p.stdout.splitlines()
        untracked = sum(line.startswith('??') for line in lines)
        tracked = len(lines) - untracked
        return result('launcher git status', 'info' if lines else 'ok', f'{tracked} tracked changes, {untracked} untracked entries' if lines else 'clean working tree')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('launcher git status', 'unknown', str(exc)[:180])


def run_checks():
    checks = []
    platform = 'termux' if os.environ.get('PREFIX', '').startswith('/data/data/com.termux/') else 'linux/other'
    checks.append(result('environment', 'ok' if platform == 'termux' else 'info', platform))
    checks.append(result('python version', 'ok' if sys.version_info >= (3, 10) else 'fail', sys.version.split()[0]))
    for name, cmd, required in [('bash', 'bash', True), ('node.js', 'node', True), ('git', 'git', True), ('glslangvalidator', 'glslangValidator', False), ('spirv-val', 'spirv-val', False)]:
        checks.append(check_tool(name, cmd, required))
    checks.append(result('launcher directory', 'ok' if ROOT.is_dir() else 'fail', str(ROOT)))
    runtime = ROOT / 'homebrew-launcher'
    checks.append(result('runtime directory', 'ok' if runtime.is_dir() else 'fail', str(runtime)))
    js = runtime / 'launcher-loop.cjs'
    py = runtime / 'catalog-assets.py'
    checks.append(check_file('launcher javascript', js))
    checks.append(check_file('asset catalog script', py))
    checks.append(check_file('z4tools menu', HERE / 'z4tools.sh'))
    checks.append(check_file('launcher shader source', runtime / 'shaders' / 'launcher.frag', required=False))
    if js.is_file():
        checks.append(check_syntax('launcher javascript syntax', js, 'javascript'))
    if py.is_file():
        checks.append(check_syntax('asset catalog python syntax', py, 'python'))
    checks.append(check_disk())
    checks.append(check_git())
    checks.append(check_file('advanced compatibility checker', HERE / 'compatibility_check.py'))
    checks.append(check_file('dependency manager', HERE / 'dependency_manager.py'))
    return checks


def main():
    ap = argparse.ArgumentParser(description='read-only z4tools system health check')
    ap.add_argument('--json', metavar='PATH', help='write a json report to this file')
    ap.add_argument('--no-pause', action='store_true', help='exit without prompting')
    args = ap.parse_args()
    checks = run_checks()
    counts = {s: sum(c['status'] == s for c in checks) for s in ('ok', 'warn', 'fail', 'info', 'unknown')}
    overall = 'attention required' if counts['fail'] else 'review warnings' if counts['warn'] else 'checks passed (limited coverage)'
    print('=== z4tools v1.6 | system health check ===')
    print('read-only; does not launch or modify gpubrewlauncher\n')
    for c in checks:
        print(f"[{c['status']}] {c['name']} — {c['detail']}")
        if c.get('suggestion') and c['status'] != 'ok':
            print('       suggestion: ' + c['suggestion'])
    print('\nsummary: ' + ', '.join(f'{counts[s]} {s}' for s in counts))
    print('overall: ' + overall)
    print('note: passing checks do not prove the launcher runs or renders correctly.')
    if args.json:
        target = Path(args.json).expanduser()
        payload = dict(tool='z4tools health check', version='1.6-dev', timestamp=datetime.now(timezone.utc).isoformat(), launcher_path=str(ROOT), overall=overall, counts=counts, checks=checks)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
            print('json report: ' + str(target))
        except OSError as exc:
            print('could not write json report: ' + str(exc), file=sys.stderr)
            return 2
    if not args.no_pause and sys.stdin.isatty():
        try:
            input('\npress enter to return...')
        except (EOFError, KeyboardInterrupt):
            pass
    return 1 if counts['fail'] else 0


if __name__ == '__main__':
    sys.exit(main())
