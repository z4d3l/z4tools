#!/usr/bin/env python3
"""Read-only compatibility report for Z4Tools and GPUBrewLauncher."""
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import sys

HOME = Path.home()
Z4 = HOME / 'z4tools'
ROOT = HOME / 'GPUBrewLauncher'
LOOP = ROOT / 'homebrew-launcher' / 'launcher-loop.cjs'
SHADER_DIR = ROOT / 'homebrew-launcher' / 'shaders'


def report(label, status, detail=''):
    symbol = {'ok':'[ok]', 'warn':'[!!]', 'unknown':'[??]'}[status]
    print(f'{symbol} {label}' + (f' — {detail}' if detail else ''))
    return status


def has_marker(file, markers):
    try:
        data = file.read_text(errors='replace')
        return any(marker in data for marker in markers)
    except OSError:
        return False


def main():
    print('\033[2J\033[H', end='')
    print('=== z4tools | compatibility checker v1.5.3 ===')
    print('read-only: no files or settings will be changed\n')
    results=[]
    results.append(report('python', 'ok' if sys.version_info >= (3, 10) else 'warn', sys.version.split()[0]))
    for command in ('node','glslangValidator','git'):
        executable=shutil.which(command)
        results.append(report(command, 'ok' if executable else 'warn', executable or 'not found in path'))
    results.append(report('gpubrewlauncher folder', 'ok' if ROOT.is_dir() else 'warn', str(ROOT)))
    results.append(report('launcher runtime', 'ok' if LOOP.is_file() else 'warn', str(LOOP)))
    results.append(report('z4tools main menu', 'ok' if (Z4/'z4tools.sh').is_file() else 'warn'))
    results.append(report('accent patch manager', 'ok' if (Z4/'accent_setup.py').is_file() else 'warn', 'menu integration not verified' if (Z4/'accent_setup.py').is_file() else 'not found'))
    results.append(report('live accent controller', 'ok' if (HOME/'z4-accent-live/z4_accent.py').is_file() else 'warn'))
    results.append(report('live theme switcher', 'ok' if (Z4/'live_themes.py').is_file() else 'warn'))
    results.append(report('live runtime marker', 'ok' if has_marker(LOOP, ['z4-accent-live','z4tools-v1.5']) else 'unknown', 'marker check only'))
    results.append(report('startup theme restore marker', 'ok' if has_marker(LOOP,['z4tools-v1.5.05-auto-restore']) else 'unknown', 'marker check only'))
    state=Z4/'live-theme.json'
    if state.is_file():
        try:
            obj=json.loads(state.read_text())
            color=obj.get('hex')
            import re
            valid=isinstance(color,str) and bool(re.fullmatch(r'#[0-9a-fA-F]{6}',color))
            results.append(report('saved accent configuration','ok' if valid else 'warn',str(color)))
        except (ValueError,OSError):
            results.append(report('saved accent configuration','warn','unreadable json'))
    else:
        results.append(report('saved accent configuration','unknown','no theme saved yet'))
    results.append(report('shader folder', 'ok' if SHADER_DIR.is_dir() else 'warn'))
    results.append(report('clean menu patch', 'ok' if has_marker(Z4/'z4tools.sh',['z4tools-clean-menu-v152']) else 'unknown', 'marker check only'))
    print('\nsummary:',sum(x=='ok' for x in results),'detected,',sum(x=='warn' for x in results),'attention,',sum(x=='unknown' for x in results),'unverified')
    print('note: detected files/markers do not prove a patch works at runtime.')
    try: input('\npress enter to return to z4tools...')
    except (EOFError,KeyboardInterrupt):pass

if __name__=='__main__':main()
