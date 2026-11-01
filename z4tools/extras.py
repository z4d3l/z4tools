#!/usr/bin/env python3
"""Z4Tools 1.2 extras. Uses only the Python standard library."""
import json, os, re, shutil, subprocess, sys, time, datetime
from pathlib import Path
ROOT=Path.home()/'GPUBrewLauncher'
STORE=Path.home()/'gpubrew-backups'
LOGDIR=Path.home()/'.z4tools-logs'
HERE=Path(__file__).resolve().parent

def ask(msg):
    return input(msg+' [y/N]: ').strip().lower() in ('y','yes')

def point():
    print('creating automatic restore point before changes...')
    result=subprocess.run(['bash',str(HERE/'backup.sh'),'backup'])
    if result.returncode: print('backup failed; operation cancelled');return False
    try:
        from customize import apply
        apply({})  # maintain the z4tools attribution on every managed modification
    except Exception as e:
        print('watermark validation failed; operation cancelled:',e)
        return False
    return True

def build():
    if not (ROOT/'homebrew-launcher/build-launcher.sh').is_file(): print('launcher build script missing');return
    print('build uses your current crimson source files; it does not reset colors.')
    if not ask('build launcher now?'):return
    if not point():return
    LOGDIR.mkdir(exist_ok=True)
    dest=LOGDIR/('build-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.log')
    start=time.monotonic()
    with dest.open('w') as log:
        proc=subprocess.Popen(['bash','homebrew-launcher/build-launcher.sh'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
        for line in proc.stdout:
            print(line,end='');log.write(line)
        rc=proc.wait()
    elapsed=time.monotonic()-start
    print(f'build {"succeeded" if rc==0 else "FAILED"} (exit {rc}) in {elapsed:.1f}s')
    print('log:',dest)

def diagnostics():
    print('\n=== launcher diagnostics (read-only) ===')
    checks=[('project',ROOT),('launcher',ROOT/'homebrew-launcher/launcher.cjs'),('compute source',ROOT/'homebrew-launcher/shaders/launcher.comp'),('crimson source',ROOT/'sdk/include/draw.glsl'),('build script',ROOT/'homebrew-launcher/build-launcher.sh')]
    for label,path in checks:print(('ok ' if path.exists() else 'MISSING ')+label+': '+str(path))
    for stage in ('vert','frag','comp'):
        p=ROOT/f'homebrew-launcher/shaders/launcher.{stage}.spv'
        print(('ok ' if p.is_file() and p.stat().st_size>0 else 'MISSING ')+p.name+(f' ({p.stat().st_size} bytes)' if p.exists() else ''))
    for cmd in ('node','python3','glslangValidator','spirv-val'):
        print(('ok ' if shutil.which(cmd) else 'missing ')+cmd)
    try:
        txt=(ROOT/'sdk/include/draw.glsl').read_text()
        match=re.search(r'const vec3 BLUE\s*=\s*vec3\(([^)]+)\)',txt)
        print('current accent:',match.group(1) if match else 'not found')
    except OSError:pass
    print('disk free:',round(shutil.disk_usage(ROOT if ROOT.exists() else Path.home()).free/1024**3,2),'gib')
    print('diagnostics do not execute switch-side gpu validation')

def logs():
    files=sorted(LOGDIR.glob('*.log'),key=lambda p:p.stat().st_mtime,reverse=True) if LOGDIR.exists() else []
    # Existing launch logs may be located in run directories; show build logs and manually provided log path.
    print('\n=== saved z4tools build logs ===')
    for i,p in enumerate(files[:15],1):print(f'{i}) {p.name}')
    raw=input('log number, absolute log path, or 0 to back: ').strip()
    if raw in ('','0'):return
    try:p=files[int(raw)-1] if raw.isdigit() and 1<=int(raw)<=len(files) else Path(raw).expanduser()
    except (ValueError,IndexError):print('invalid selection');return
    if not p.is_file():print('file not found');return
    with p.open(errors='replace') as f:
        lines=f.readlines()[-100:]
    for line in lines:
        if re.search(r'error|failed|exception|traceback',line,re.I):print('!! '+line,end='')
        else:print(line,end='')

def timer():
    print('startup timer: start this immediately before your usual start.sh command.')
    input('press enter to start timer...')
    start=time.monotonic()
    print('timer running. press enter when the gpubrew menu is visible.')
    input()
    secs=time.monotonic()-start
    print(f'elapsed: {secs:.1f}s ({secs/60:.2f} minutes)')
    LOGDIR.mkdir(exist_ok=True)
    with (LOGDIR/'startup-times.log').open('a') as f:f.write(f'{datetime.datetime.now().isoformat(timespec="seconds")} {secs:.2f}s\n')
    print('note: this is a manual stopwatch, not an automatic startup-phase profiler.')

def app_manager():
    apps=ROOT/'apps'
    if not apps.is_dir():print('apps folder missing');return
    while True:
        found=sorted(p for p in apps.iterdir() if p.is_dir() and (p/'app.json').is_file() and not p.is_symlink())
        print('\n=== installed apps ===')
        for i,p in enumerate(found,1):
            try:meta=json.loads((p/'app.json').read_text());label=meta.get('name',p.name)
            except Exception:label=p.name
            print(f'{i}) {label} [{p.name}]')
        raw=input('app number for details/manage, 0 to back: ').strip()
        if raw=='0':return
        if not raw.isdigit() or not 1<=int(raw)<=len(found):print('invalid selection');continue
        p=found[int(raw)-1]
        print((p/'app.json').read_text()[:3000])
        print('1) build app  2) uninstall (move to recovery folder)  3) edit name/description/icon  4) settings  0) back')
        action=input('choose: ').strip()
        if action=='3':
            edit_app_metadata(p)
        elif action=='4':
            print('settings: app edits require confirmation and automatic restore points. removed apps go to ~/z4tools-removed-apps.')
        elif action=='1':
            if not (p/'build.cjs').is_file():print('no build.cjs');continue
            if ask('build this app?') and point():subprocess.run(['node',str(p/'build.cjs')],cwd=ROOT)
        elif action=='2':
            if not ask(f'move {p.name} out of installed apps?'):continue
            if not point():continue
            trash=Path.home()/'z4tools-removed-apps';trash.mkdir(exist_ok=True)
            dest=trash/(p.name+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
            if dest.exists():print('destination already exists; cancelled');continue
            p.rename(dest);print('moved to:',dest,'(restore manually if needed)')

def template():
    # Clone the existing known-good starter app, keeping all shaders and build scripts compatible.
    base=ROOT/'apps/hello-world'
    if not (base/'app.json').is_file():print('hello-world template not found in project');return
    name=input('new app id (lowercase letters, numbers, hyphens): ').strip()
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}',name):print('invalid app id');return
    dest=ROOT/'apps'/name
    if dest.exists():print('app already exists; refusing overwrite');return
    label=input('display name (blank uses app id): ').strip() or name
    if not point():return
    try:
        shutil.copytree(base,dest,ignore=shutil.ignore_patterns('*.spv','*.log'))
        manifest=dest/'app.json';data=json.loads(manifest.read_text());data['id']=name;data['name']=label;data['description']='starter app created with z4tools'
        manifest.write_text(json.dumps(data,indent=2)+'\n')
        print('starter created:',dest)
        print('edit the shaders and build with: node apps/'+name+'/build.cjs')
    except Exception as e:
        print('creation failed:',e)
        if dest.exists():shutil.rmtree(dest)

def theme_presets():
    path=HERE/'saved-themes.json'
    try:data=json.loads(path.read_text())
    except Exception:data={}
    while True:
        print('\n=== saved accent palettes ===')
        for k,v in sorted(data.items()):print(k,v)
        print('1) save current accent  2) apply saved accent  3) preview palette  0) back')
        c=input('choose: ').strip()
        if c=='0':return
        if c=='1':
            try:
                text=(ROOT/'sdk/include/draw.glsl').read_text();m=re.search(r'const vec3 BLUE\s*=\s*vec3\(([^)]+)\)',text)
                nums=[float(x.strip()) for x in m.group(1).split(',')]
                color='#'+''.join(f'{max(0,min(255,round(n*255))):02x}' for n in nums)
                name=input('palette name: ').strip()
                if not re.fullmatch('[a-zA-Z0-9_-]{1,30}',name):print('invalid name');continue
                data[name]=color;path.write_text(json.dumps(data,indent=2)+'\n');print('saved',name,color)
            except Exception as e:print('could not read accent:',e)
        elif c=='2':
            name=input('saved palette name: ').strip()
            if name not in data:print('not found');continue
            print('apply using the existing theme maker custom hex option:',data[name]);print('this avoids bypassing its confirmation and validation')
        elif c=='3':
            from theme_maker_bridge import preview
            name=input('hex (#rrggbb): ').strip()
            try:preview(name)
            except Exception as e:print(e)

def main():
    choices={'1':diagnostics,'2':build,'3':logs,'4':timer,'5':app_manager,'6':template,'7':theme_presets,'8':point}
    while True:
        print('\n=== z4tools developer tools ===\n1) launcher diagnostics\n2) one-click launcher builder\n3) error log viewer\n4) startup timer\n5) app manager\n6) app template generator\n7) advanced theme palettes\n8) create restore point\n0) back')
        c=input('choose: ').strip()
        if c=='0':return
        if c in choices:
            try:choices[c]()
            except (OSError,ValueError,KeyboardInterrupt,EOFError) as e:print('operation cancelled/error:',e)
        else:print('invalid option')
if __name__=='__main__':
    arg=sys.argv[1] if len(sys.argv)>1 else ''
    if arg=='app_manager':app_manager()
    elif arg=='template':
        if ask('create a new app template?'):template()
    elif arg=='buildtools':
        while True:
            print('\nlauncher tools: 1) diagnostics 2) build 3) settings 0) back')
            c=input('choose: ').strip()
            if c=='0':break
            if c=='1':diagnostics()
            elif c=='2':build()
            elif c=='3':print('settings: builds are logged in ~/.z4tools-logs and backed up first.')
    elif arg=='logsandtimer':
        while True:
            print('\nlogs/timer: 1) error logs 2) startup timer 3) settings 0) back')
            c=input('choose: ').strip()
            if c=='0':break
            if c=='1':logs()
            elif c=='2':timer()
            elif c=='3':print('settings: startup timer is manual; logs are in ~/.z4tools-logs.')
    else:main()

# v1.3 app metadata editor. Changes require explicit confirmation and restore point.
def edit_app_metadata(app):
    manifest=app/'app.json'
    try:data=json.loads(manifest.read_text())
    except (OSError,ValueError) as e:print('invalid manifest:',e);return
    while True:
        print('\n=== app appearance ===')
        print('name:',data.get('name'))
        print('description:',data.get('description'))
        print('icon:',data.get('icon'))
        print('1) change display name  2) change description  3) replace icon  4) settings  0) back')
        c=input('choose: ').strip()
        if c=='0':return
        if c=='4':
            print('settings: icon must be a png; original icon will be preserved by a restore point.')
            print('changes appear after rebuilding or refreshing the app catalog, as supported by gpubrew.')
            continue
        if c in ('1','2'):
            key='name' if c=='1' else 'description'
            value=input(f'new {key} (blank cancels): ').strip()
            if not value:continue
            if len(value)> (80 if key=='name' else 200):print('too long');continue
            if not ask(f'change {key} to {value!r}?'):continue
            if not point():continue
            data[key]=value
            manifest.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
            print('saved. refresh/rebuild app catalog to see the update.')
        elif c=='3':
            raw=input('absolute path to replacement .png (blank cancels): ').strip()
            if not raw:continue
            src=Path(raw).expanduser()
            if not src.is_file() or src.suffix.lower()!='.png':print('provide an existing png file');continue
            if src.stat().st_size>5*1024*1024:print('icon exceeds 5 mb');continue
            with src.open('rb') as f:signature=f.read(8)
            if signature!=b'\x89PNG\r\n\x1a\n':print('not a png');continue
            # Keep icon inside app folder and preserve the manifest's expected relative location.
            relative=data.get('icon','assets/icon.png')
            if not isinstance(relative,str):print('invalid manifest icon');continue
            dest=(app/relative).resolve()
            if not dest.is_relative_to(app.resolve()) or dest.suffix.lower()!='.png':print('unsafe icon path');continue
            if not ask(f'replace {app.name} icon at {relative}?'):continue
            if not point():continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,dest)
            print('icon replaced. run the app build to regenerate catalog assets if needed.')
