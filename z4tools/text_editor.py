#!/usr/bin/env python3
"""z4tools v1.4 fixed-layout text editor. Does not alter shaders or protected labels."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from datetime import datetime
from extras import ROOT, ask

HERE=Path(__file__).resolve().parent
SHADERS=ROOT/'homebrew-launcher/shaders'
ATLAS=SHADERS/'launcher-text.bin'
COORDS=SHADERS/'launcher-text.glsl'
SOURCE=ROOT/'homebrew-launcher/launcher-text.py'
STATE=HERE/'text-values.json'
FIELDS={'title':('TITLE','GPUBrewLauncher',88),'library':('LIBRARY','Your library',26)}

def fontfile():
    for p in (Path(os.environ.get('PREFIX',''))/'share/fonts/TTF/DejaVuSans.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')):
        if p.is_file():return str(p)
    raise RuntimeError('dejavu sans font missing; install a compatible font before editing')

def get_values():
    try:return json.loads(STATE.read_text())
    except (OSError,ValueError):return {}

def set_value(key,value):
    if not value or len(value)>100 or any(ord(c)<32 for c in value):raise ValueError('text must be 1-100 printable characters')
    from PIL import Image,ImageDraw,ImageFont
    if not ATLAS.is_file() or not COORDS.is_file():raise RuntimeError('generated atlas missing')
    glsl=COORDS.read_text()
    field,default,size=FIELDS[key]
    m=re.search(r'\bTEXT_'+field+r'\s*=\s*ivec4\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',glsl)
    if not m:raise RuntimeError('cannot locate '+field+' atlas coordinates')
    x,y,w,h=map(int,m.groups())
    data=ATLAS.read_bytes()
    if len(data)!=1024*2048:raise RuntimeError('unexpected atlas dimensions; no changes made')
    im=Image.frombytes('L',(1024,2048),data)
    draw=ImageDraw.Draw(im)
    font=ImageFont.truetype(fontfile(),size)
    bbox=draw.textbbox((0,0),value,font=font)
    width,height=bbox[2]-bbox[0],bbox[3]-bbox[1]
    if width>w or height>h:
        raise ValueError(f'text does not fit original {field.lower()} region ({width}x{height} vs {w}x{h}); shorten it. font/size/position unchanged.')
    print(f'change {field.lower()} to {value!r}?')
    if not ask('confirm change to gpubrew?'):return
    backup=Path.home()/'z4tools-text-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    shutil.copy2(ATLAS,backup/'launcher-text.bin')
    if STATE.exists():shutil.copy2(STATE,backup/'text-values.json')
    # Only modify the existing rectangle; never change atlas size or GLSL coordinates.
    draw.rectangle((x,y,x+w-1,y+h-1),fill=0)
    draw.text((x-bbox[0],y-bbox[1]),value,font=font,fill=255)
    tmp=ATLAS.with_name(ATLAS.name+'.z4tmp')
    tmp.write_bytes(im.tobytes());tmp.replace(ATLAS)
    values=get_values();values[key]=value
    STATE.write_text(json.dumps(values,indent=2)+'\n')
    print('saved. restore point:',backup)
    print('use hot-reload launcher to preview on the switch without restarting.')
    print('note: rebuilding the launcher may regenerate the atlas from launcher-text.py.')

def apps():
    found=sorted(p for p in (ROOT/'apps').glob('*/app.json') if p.is_file())
    for i,p in enumerate(found,1):
        try:print(f'{i}) {json.loads(p.read_text()).get("name",p.parent.name)}')
        except ValueError:print(f'{i}) {p.parent.name} (invalid json)')
    raw=input('choose app number (0 back): ').strip()
    if not raw.isdigit() or int(raw)==0:return
    if not 1<=int(raw)<=len(found):print('invalid selection');return
    path=found[int(raw)-1]
    meta=json.loads(path.read_text())
    choice=input('[1] name  [2] description  [0] back: ').strip()
    key={'1':'name','2':'description'}.get(choice)
    if not key:return
    print('current:',meta.get(key,''))
    value=input('new '+key+': ').strip()
    if not value or len(value)>(64 if key=='name' else 160) or any(ord(c)<32 for c in value):print('invalid text length or characters');return
    if not ask('confirm modification to app metadata?'):return
    backup=Path.home()/'z4tools-text-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True);shutil.copy2(path,backup/(path.parent.name+'-app.json'))
    meta[key]=value
    temp=path.with_name('app.json.z4tmp');temp.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n');temp.replace(path)
    print('saved. backup:',backup)
    print('app labels use the catalog, not the text atlas. use the existing switch app refresh button to display this change.')

def reload():
    import glob
    loop_file=ROOT/'homebrew-launcher/launcher-loop.cjs'
    runtime_file=ROOT/'homebrew-launcher/app-runtime.cjs'
    if not loop_file.exists() or not runtime_file.exists() or any('z4-text-hot-reload-v1' not in p.read_text() for p in (loop_file,runtime_file)):
        print('you have to install the text hot-reload patch first. use main menu option 9.')
        return
    # Locate the active runtime from the live launcher-loop process, never guess from old temp folders.
    proc=subprocess.run(['ps','-ef'],capture_output=True,text=True)
    matches=[]
    for line in proc.stdout.splitlines():
        if 'node homebrew-launcher/launcher-loop.cjs ' not in line:continue
        m=re.search(r'launcher-loop\.cjs\s+(\S*gpubrewlauncher-[^\s]+)',line)
        if m:matches.append(Path(m.group(1)))
    if len(matches)!=1:
        print('expected exactly one active launcher-loop; found',len(matches));print('do not start a second instance.');return
    d=matches[0]
    loop=(ROOT/'homebrew-launcher/launcher-loop.cjs').read_text()
    runtime=(ROOT/'homebrew-launcher/app-runtime.cjs').read_text()
    if 'z4-text-hot-reload-v1' not in loop or 'z4-text-hot-reload-v1' not in runtime:
        print('you have to install the text hot-reload patch first. use main menu option 9.')
        return
    if not d.is_dir():print('active runtime folder not found:',d);return
    request=d/'z4-text-hot-reload.request'
    if request.exists():print('reload already pending');return
    for ext in ('.done','.failed'):
        (d/('z4-text-hot-reload.request'+ext)).unlink(missing_ok=True)
    request.write_text('reload text atlas\n')
    print('hot reload requested:',d)
    print('check the switch and running termux host log for success. no success claimed until confirmed.')

def menu():
    while True:
        print('\n=== z4tools v1.4 | text editor ===')
        print('[1] launcher title  [2] "Your library"  [3] app names / descriptions')
        print('[4] hot-reload launcher text  [5] show current saved text  [0] back')
        c=input('choose: ').strip()
        try:
            if c=='0':return
            if c in ('1','2'):
                key='title' if c=='1' else 'library'
                print('current:',get_values().get(key,FIELDS[key][1]))
                val=input('new text (blank cancels): ').strip()
                if val:set_value(key,val)
            elif c=='3':apps()
            elif c=='4':reload()
            elif c=='5':print(json.dumps(get_values(),indent=2))
            else:print('invalid option')
        except (RuntimeError,ValueError,OSError,ImportError) as e:print('could not apply:',e)

if __name__=='__main__':menu()
