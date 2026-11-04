#!/usr/bin/env python3
"""z4tools v1.7 development configuration editor. Only edits adjacent settings.json."""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time

SETTINGS_NAME = 'settings.json'
BACKUP_NAME = '.config-editor-history'
LOCK_NAME = '.config-editor.lock'
MAX_BYTES = 256 * 1024
SECRET_RE = re.compile(r'(pass|secret|token|key|credential|auth|cookie)', re.I)
DEPLOY_KEY = 'app_deployment_directory'

class Rejected(Exception):
    pass

def safe_file(p):
    if p.is_symlink():
        raise Rejected('symlink settings file blocked')
    if not p.exists():
        return None
    st = p.lstat()
    if not stat.S_ISREG(st.st_mode):
        raise Rejected('settings must be a regular file')
    if st.st_size > MAX_BYTES:
        raise Rejected('settings file too large')
    return st

def load(path):
    st = safe_file(path)
    if st is None:
        return {}, None, None
    raw = path.read_bytes()
    if len(raw)>MAX_BYTES:
        raise Rejected('settings file too large')
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Rejected('invalid settings json; nothing changed') from exc
    if not isinstance(data, dict):
        raise Rejected('settings root must be a json object')
    return data, hashlib.sha256(raw).hexdigest(), raw

def display(name, value):
    if SECRET_RE.search(name):
        return '<redacted>'
    return json.dumps(value, ensure_ascii=False)

def validate_deployment(value):
    if not isinstance(value, str) or not value.strip():
        raise Rejected('deployment directory must be a non-empty path')
    if '\0' in value:
        raise Rejected('invalid path')
    p = Path(value).expanduser()
    if not p.is_absolute():
        raise Rejected('deployment directory must be absolute or start with ~/')
    p = p.resolve(strict=False)
    home = Path.home().resolve()
    protected = (home, home/'GPUBrewLauncher', home/'gpubrew-backups')
    if str(p) == '/':
        raise Rejected('filesystem root is not a deployment destination')
    if any(p==q or q in p.parents for q in protected[1:]):
        raise Rejected('launcher and backup directories are protected')
    if p == home:
        raise Rejected('home directory is not a deployment destination')
    if p.exists() and not p.is_dir():
        raise Rejected('deployment destination exists but is not a directory')
    if p.is_symlink():
        raise Rejected('symlink deployment destination blocked')
    return str(p)

def validate_key(key):
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_\-]{0,79}', key):
        raise Rejected('invalid setting key')
    if SECRET_RE.search(key):
        raise Rejected('credential-like settings are not editable here')
    if key.startswith('_'):
        raise Rejected('private settings are not editable here')

def validate_value(key,value):
    if key == DEPLOY_KEY:
        return validate_deployment(value)
    if isinstance(value, (dict,list)):
        raise Rejected('nested structures cannot be changed through the simple editor')
    if isinstance(value, str) and len(value)>4096:
        raise Rejected('value too long')
    return value

def make_private_dir(path):
    if path.is_symlink():
        raise Rejected('symlink history directory blocked')
    if path.exists():
        if not path.is_dir():
            raise Rejected('history path is not a directory')
        if path.stat().st_mode & 0o077:
            raise Rejected('history permissions are not private (expected 0700)')
        return
    path.mkdir(mode=0o700)
    os.chmod(path,0o700)

def write_backup(history, source_bytes):
    make_private_dir(history)
    # Exclusive create; never overwrite an existing editor backup.
    for i in range(100):
        name = f'previous-{time.time_ns()}-{os.getpid()}-{i}.json'
        path = history/name
        try:
            fd = os.open(str(path), os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            break
        except FileExistsError:
            continue
    else:
        raise Rejected('cannot allocate unique history filename')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(source_bytes)
            f.flush()
            os.fsync(f.fileno())
        dirfd = os.open(str(history), os.O_RDONLY)
        try: os.fsync(dirfd)
        finally: os.close(dirfd)
    except BaseException:
        raise
    return path

def atomic_write(path, content):
    fd, tempname = tempfile.mkstemp(prefix='.config-editor-', dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if path.is_symlink():
            raise Rejected('settings file became a symlink')
        os.replace(tempname,str(path))
        dirfd=os.open(str(path.parent),os.O_RDONLY)
        try: os.fsync(dirfd)
        finally: os.close(dirfd)
    finally:
        if os.path.exists(tempname): os.unlink(tempname)

def lock_directory(base):
    lock=base/LOCK_NAME
    if lock.is_symlink():
        raise Rejected('symlink lock file blocked')
    fd=os.open(str(lock),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise Rejected('another config editor is active')
    return fd

def commit(base, key, value=None, delete=False, confirm=False):
    path=base/SETTINGS_NAME
    fd=lock_directory(base)
    try:
        old, h, oldbytes=load(path)
        validate_key(key)
        new=copy.deepcopy(old)
        if delete:
            if key not in new:
                raise Rejected('setting not present')
            del new[key]
        else:
            value=validate_value(key,value)
            if key in old and old[key] == value:
                print('[unchanged] value is already set'); return False
            new[key]=value
        print('\n=== change preview ===')
        print('config:',path)
        print('setting:',key)
        print('before:',display(key,old[key]) if key in old else '<unset>')
        print('after: ', '<unset>' if delete else display(key,value))
        if not confirm:
            if input('type SAVE to apply (anything else cancels): ').strip() != 'SAVE':
                print('[cancelled] no changes'); return False
        current, current_hash, _ = load(path)
        if h != current_hash or old!=current:
            raise Rejected('settings changed during editing; retry')
        content=(json.dumps(new,indent=2,ensure_ascii=False,sort_keys=True)+'\n').encode('utf-8')
        if len(content)>MAX_BYTES:
            raise Rejected('resulting settings too large')
        if oldbytes is not None:
            backup=write_backup(base/BACKUP_NAME,oldbytes)
            print('[history] previous settings saved privately:',backup.name)
        atomic_write(path,content)
        print('[saved] settings updated')
        return True
    finally: os.close(fd)

def show(base):
    data,_,_=load(base/SETTINGS_NAME)
    print('\n=== z4tools settings ===')
    if not data: print('(no explicit settings)')
    for key in sorted(data): print(f'{key}: {display(key,data[key])}')
    print('[info] no changes made')

def interactive(base):
    while True:
        print('\n=== configuration editor (v1.7) ===')
        print('[1] view settings\n[2] change deployment directory\n[3] set an advanced top-level value\n[4] remove a setting\n[5] show history backups\n[0] back')
        choice=input('choose: ').strip()
        try:
            if choice=='0': return
            if choice=='1': show(base)
            elif choice=='2':
                raw=input('new absolute directory (blank cancels): ').strip()
                if raw: commit(base,DEPLOY_KEY,raw)
            elif choice=='3':
                key=input('setting key (blank cancels): ').strip()
                if not key: continue
                validate_key(key)
                raw=input('new value as json (example: true, 123, "text"): ')
                try: value=json.loads(raw)
                except ValueError: raise Rejected('invalid json value; strings require quotes')
                commit(base,key,value)
            elif choice=='4':
                key=input('setting key to remove (blank cancels): ').strip()
                if key: commit(base,key,delete=True)
            elif choice=='5':
                history=base/BACKUP_NAME
                if history.is_symlink(): raise Rejected('symlink history blocked')
                for p in sorted(history.glob('previous-*.json'))[-15:] if history.exists() else []:
                    print(p.name)
                print('[info] history is never automatically deleted')
            else: print('invalid option')
        except (Rejected, OSError, ValueError) as exc:
            print('[blocked]',exc)

def main():
    parser=argparse.ArgumentParser(description='safe z4tools settings editor')
    parser.add_argument('command',nargs='?',choices=('menu','show','set','delete'),default='menu')
    parser.add_argument('--key')
    parser.add_argument('--json-value')
    parser.add_argument('--yes',action='store_true',help='test automation only; command-line writes require explicit choice')
    args=parser.parse_args()
    base=Path(__file__).resolve().parent
    # Prevent accidental use on installed ~/z4tools; this is dev-only.
    if base.name != 'z4tools' or not (base / 'z4tools.sh').is_file():
        raise Rejected('configuration editor requires a z4tools installation folder')
    if args.command=='menu': interactive(base)
    elif args.command=='show': show(base)
    else:
        if not args.key: raise Rejected('--key required')
        if args.command=='delete': commit(base,args.key,delete=True,confirm=args.yes)
        else:
            if args.json_value is None: raise Rejected('--json-value required')
            try: val=json.loads(args.json_value)
            except ValueError: raise Rejected('invalid json value')
            commit(base,args.key,val,confirm=args.yes)

if __name__=='__main__':
    try: main()
    except (Rejected, OSError, EOFError, KeyboardInterrupt) as exc:
        print('[blocked]',str(exc),file=sys.stderr)
        sys.exit(2)
