#!/usr/bin/env python3
"""z4tools 1.7 feature 6: read-only operation previews; never executes operations."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import tarfile
import zipfile

MAX_ITEMS = 100000
MAX_TOTAL = 2 * 1024**3

class PreviewError(Exception): pass

def regular_file(path):
    if path.is_symlink() or not path.is_file():
        raise PreviewError('a regular non-symlink file is required')

def preview_path(value):
    p = PurePosixPath(value)
    if not value or '\\' in value or '\x00' in value or p.is_absolute() or any(x in ('..', '') for x in p.parts) or value.startswith('//'):
        raise PreviewError('unsafe archive member path')
    if p.parts[0] in ('.', '..') or ':' in p.parts[0]:
        raise PreviewError('unsafe archive member path')
    return p

def inspect_archive(path):
    path=Path(path).expanduser()
    regular_file(path)
    entries=[]; total=0; seen=set()
    if path.name.endswith('.tar.gz'):
        try:
            with tarfile.open(path,'r:gz') as z:
                for obj in z:
                    p=preview_path(obj.name)
                    if obj.isdir():
                        continue
                    if not obj.isfile():
                        raise PreviewError('archive contains link or special file')
                    if obj.name in seen:
                        raise PreviewError('duplicate archive member')
                    seen.add(obj.name); total+=obj.size
                    entries.append((str(p),obj.size))
                    if len(entries)>MAX_ITEMS or total>MAX_TOTAL: raise PreviewError('archive exceeds preview limit')
        except (tarfile.TarError,OSError,EOFError) as exc: raise PreviewError('invalid tar.gz archive') from exc
    elif path.name.endswith('.zip'):
        try:
            with zipfile.ZipFile(path) as z:
                for obj in z.infolist():
                    p=preview_path(obj.filename)
                    mode=(obj.external_attr >> 16) & 0xffff
                    if obj.is_dir(): continue
                    if stat.S_IFMT(mode) not in (0,stat.S_IFREG):
                        raise PreviewError('archive contains link or special file')
                    if obj.filename in seen: raise PreviewError('duplicate archive member')
                    seen.add(obj.filename); total+=obj.file_size
                    entries.append((str(p),obj.file_size))
                    if len(entries)>MAX_ITEMS or total>MAX_TOTAL: raise PreviewError('archive exceeds preview limit')
        except (zipfile.BadZipFile,OSError,EOFError) as exc: raise PreviewError('invalid zip archive') from exc
    else:
        raise PreviewError('only .tar.gz and .zip archives supported')
    if not entries: raise PreviewError('archive contains no regular files')
    return entries,total

def show_archive(path):
    entries,total=inspect_archive(path)
    print('archive:',Path(path).expanduser())
    print('files:',len(entries),'uncompressed bytes:',total)
    print('sample entries (up to 12):')
    for name,size in entries[:12]: print(f'  {name} ({size} bytes)')
    if len(entries)>12: print(f'  ... {len(entries)-12} more')
    return entries,total

def config_preview(base,key,new_value,remove=False):
    base=Path(base)
    conf=base/'settings.json'
    if conf.is_symlink(): raise PreviewError('symlink settings file blocked')
    if conf.exists():
        regular_file(conf)
        if conf.stat().st_size>262144: raise PreviewError('settings file too large')
        try: obj=json.loads(conf.read_text())
        except (OSError,ValueError,UnicodeError) as exc: raise PreviewError('invalid settings json') from exc
        if not isinstance(obj,dict): raise PreviewError('settings must be an object')
    else: obj={}
    # Match feature 5 validation without executing its save action.
    sys.path.insert(0,str(base))
    try:
        from config_editor import validate_key, validate_value, display
        validate_key(key)
        if not remove: new_value=validate_value(key,new_value)
    except ImportError as exc:
        raise PreviewError('feature 5 editor missing') from exc
    except Exception as exc:
        raise PreviewError(str(exc)) from exc
    if remove and key not in obj: raise PreviewError('setting does not exist')
    print('operation: remove setting' if remove else 'operation: update setting')
    print('configuration:',conf)
    print('key:',key)
    print('current:',display(key,obj[key]) if key in obj else '<unset>')
    print('proposed:','<unset>' if remove else display(key,new_value))
    print('impact: 1 configuration file; feature 5 will create a history copy before changes')
    print('[preview only] configuration unchanged')

def backup_preview(home):
    launcher=Path(home)/'GPUBrewLauncher'
    if launcher.is_symlink() or not launcher.is_dir(): raise PreviewError('launcher missing or symlinked')
    files=0; total=0
    for p in launcher.rglob('*'):
        rel=p.relative_to(launcher)
        if any(part in ('.git','node_modules') for part in rel.parts): continue
        if p.is_symlink(): raise PreviewError('launcher contains symlink; cannot safely predict backup')
        if p.is_file():
            files+=1;total+=p.stat().st_size
    print('operation: create backup')
    print('source:',launcher)
    print('destination directory:',Path(home)/'gpubrew-backups')
    print('source regular files (excluding .git and node_modules):',files)
    print('estimated source bytes:',total)
    print('output: new compressed tar.gz; actual size/name determined during backup')
    print('[preview only] no backup created')

def app_preview(path, home, dest=None):
    entries,total=show_archive(path)
    destination=Path(dest).expanduser() if dest else None
    if destination is not None and destination.resolve(strict=False) in (Path(home).resolve(),(Path(home)/'GPUBrewLauncher').resolve()):
        raise PreviewError('unsafe deployment directory')
    print('operation: inspect app package for deployment')
    print('proposed deployment input directory:',destination if destination else '<not specified; check deployer settings>')
    print('package entries:',len(entries),'uncompressed bytes:',total)
    print('possible effects when launched via the separate deployer: build, replace existing app, or update files')
    print('note: exact destination and overwrite behavior depend on app-deployer.py; this preview does not simulate its build')
    print('[preview only] nothing extracted, built, or installed')

def restore_preview(path,home):
    archive=Path(path).expanduser()
    regular_file(archive)
    if archive.suffixes[-2:] != ['.tar','.gz']:
        raise PreviewError('production recovery supports .tar.gz only')
    print('operation: production launcher restore (READ ONLY PREVIEW)')
    entries,total=show_archive(archive)
    if not all(n.startswith('GPUBrewLauncher/') for n,_ in entries):
        raise PreviewError('unexpected archive root; production recovery must verify archive independently')
    launcher=Path(home)/'GPUBrewLauncher'
    state=Path(home)/'.z4tools-recovery-state'
    print('would replace:',launcher)
    print('rollback directory:',state)
    print('potential impact: entire existing launcher replaced; original should be retained in a unique rollback directory')
    journal=state/'journal.json'
    if state.is_symlink() or journal.is_symlink(): raise PreviewError('unsafe recovery state')
    if journal.exists(): print('[blocked] recovery journal exists; inspect before any restoration')
    else: print('[info] no recovery journal found')
    print('note: this is an archive inventory, NOT the production engine integrity dry-run')
    print('[preview only] live launcher untouched')

def interactive(base):
    home=Path.home()
    while True:
        print('\n=== operation preview — read only ===')
        print('[1] preview app archive\n[2] preview configuration change\n[3] preview backup creation\n[4] preview launcher restore\n[0] back')
        try: choice=input('choose: ').strip()
        except (EOFError,KeyboardInterrupt): return
        if choice=='0': return
        try:
            if choice=='1':
                p=input('app zip path (blank cancels): ').strip()
                if p: app_preview(p,home)
            elif choice=='2':
                key=input('setting key (blank cancels): ').strip()
                if not key: continue
                action=input('update or remove? [u/r]: ').strip().lower()
                if action=='r': config_preview(base,key,None,True)
                elif action=='u':
                    v=json.loads(input('new value as json: '))
                    config_preview(base,key,v)
                else: print('[cancelled]')
            elif choice=='3': backup_preview(home)
            elif choice=='4':
                p=input('backup .tar.gz path (blank cancels): ').strip()
                if p: restore_preview(p,home)
            else: print('invalid option')
        except (PreviewError,ValueError,OSError) as exc: print('[blocked]',exc)

def main():
    ap=argparse.ArgumentParser(description='read-only z4tools operation preview')
    ap.add_argument('command',choices=('menu','app','config','backup','restore'),nargs='?',default='menu')
    ap.add_argument('--archive');ap.add_argument('--base',default=str(Path(__file__).resolve().parent))
    ap.add_argument('--home',default=str(Path.home()))
    ap.add_argument('--key');ap.add_argument('--value');ap.add_argument('--remove',action='store_true')
    ap.add_argument('--destination')
    a=ap.parse_args()
    try:
        if a.command=='menu': interactive(Path(a.base))
        elif a.command=='app': app_preview(a.archive,a.home,a.destination)
        elif a.command=='backup': backup_preview(a.home)
        elif a.command=='restore': restore_preview(a.archive,a.home)
        elif a.command=='config':
            if not a.key: raise PreviewError('--key required')
            value=None if a.remove else json.loads(a.value)
            config_preview(a.base,a.key,value,a.remove)
    except (PreviewError,ValueError,OSError,TypeError) as exc:
        print('[blocked]',exc,file=sys.stderr);return 2
    return 0

if __name__=='__main__': sys.exit(main())
