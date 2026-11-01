#!/usr/bin/env python3
"""Safe preflight for future phone-triggered visual hot reload.

No runtime writes, RPC calls, or GPU pipeline changes are performed here.
"""
import hashlib
import json
import shutil
from pathlib import Path
from extras import ROOT

SHADERS = ROOT / 'homebrew-launcher' / 'shaders'
FILES = ['launcher.vert.spv', 'launcher.frag.spv', 'launcher.comp.spv']


def status():
    print('\n=== z4tools | hot-reload launcher ===')
    print('status: development preview — live reload NOT implemented')
    print('your saved source and compiled shaders remain available for the next normal launch.')
    print('this check will not modify gpubrew or contact your switch.\n')
    for name in FILES:
        p = SHADERS / name
        if p.is_file():
            b = p.read_bytes()
            print(f'ok: {name} ({len(b)} bytes; sha256 {hashlib.sha256(b).hexdigest()[:12]})')
        else:
            print(f'missing: {name}')
    loop = ROOT / 'homebrew-launcher' / 'launcher-loop.cjs'
    if loop.is_file():
        s = loop.read_text(errors='replace')
        print('existing stop-file listener:', 'found' if 'launcher-loop.stop' in s else 'not found')
    print('live reload requires a host-side request handler, new vulkan pipelines,')
    print('re-recorded command buffers, and verified fallback behavior.')


def menu():
    while True:
        print('\n[1] check hot-reload readiness (read-only)')
        print('[2] explain current limitation')
        print('[0] back')
        try: c = input('choose: ').strip()
        except (EOFError, KeyboardInterrupt): return
        if c == '0': return
        if c == '1': status()
        elif c == '2':
            print('a build alone cannot update pipelines already recorded on the switch.')
            print('no reload signal is sent until the runtime supports safe pipeline replacement.')
        else: print('invalid option')

if __name__ == '__main__': menu()
