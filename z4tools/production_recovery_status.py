#!/usr/bin/env python3
"""Read-only production recovery status: no state creation, no mutation."""
import json
from pathlib import Path

def main():
    state=Path.home()/'.z4tools-recovery-state'
    journal=state/'journal.json'
    if state.is_symlink() or (state.exists() and not state.is_dir()):
        print('[blocked] invalid recovery state; manual inspection required');return 2
    if journal.is_symlink():
        print('[blocked] journal is symlinked');return 2
    if not journal.exists():
        print('[clear] no production recovery journal')
        print('[safe] production restoration disabled in menu');return 0
    if not journal.is_file() or journal.stat().st_size>16384:
        print('[blocked] invalid journal');return 2
    try:
        obj=json.loads(journal.read_text())
        if not isinstance(obj,dict) or obj.get('version')!=2 or obj.get('phase') not in ('staged','moving_original','original_preserved','completed'):
            raise ValueError('invalid journal')
        ident=obj.get('id')
        if not isinstance(ident,str) or len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):
            raise ValueError('invalid id')
    except (ValueError,UnicodeError,OSError):
        print('[blocked] corrupt recovery journal; manual inspection required');return 2
    phase=obj['phase']
    print('[status]',phase)
    if phase=='completed':
        print('[completed] no rollback needed');return 0
    print('[interrupted] manual inspection required before further operations')
    print('[safe] no automatic changes');return 3
if __name__=='__main__':raise SystemExit(main())
