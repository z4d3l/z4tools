#!/usr/bin/env python3
"""z4tools 1.3: verified launcher edits, per-asset palette and attribution."""
import json, re, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime
from extras import ROOT, point, ask
from settings import settings_menu
from theme_maker_bridge import rgb, hexc, palette
HERE=Path(__file__).resolve().parent
FRAG=ROOT/'homebrew-launcher/shaders/launcher.frag'
ATLAS=ROOT/'homebrew-launcher/launcher-text.py'
SDK=ROOT/'sdk/include/draw.glsl'
CONFIG=HERE/'asset-colors.json'
# Only uniquely identifiable color expressions; fail closed on upstream source changes.
ASSETS={
 'accent': ('selected card borders and navigation markers', None),
 'header': ('main animated header gradient', r'(vec3 water=mix\()vec3\([^)]*\)(,vec3\([^)]*\),clamp\(p\.x/2300\.0)'),
 'header_end': ('header gradient second color', r'(vec3 water=mix\(vec3\([^)]*\),)vec3\([^)]*\)(,clamp\(p\.x/2300\.0)'),
 'title': ('gpubrewlauncher title text',r'(col=mix\(col,)vec3\([^)]*\)(,text\(p,vec2\(158,145\),TEXT_TITLE\)\))'),
 'subtitle': ('niftyfork subtitle text',r'(col=mix\(col,)vec3\([^)]*\)(,text\(p,vec2\(164,263\),TEXT_SUBTITLE\)\))'),
 'platform': ('nintendo switch 2 label',r'(col=mix\(col,)vec3\([^)]*\)(,text\(p,vec2\(164,75\),TEXT_PLATFORM\)\))'),
 'header_wave': ('wave highlight on the header',r'(col=mix\(col,)vec3\([^)]*\)(,line\(p\.y-edge,\.8\)\*\.55\))'),
 'selected_tile': ('selected app tile highlight',r'(vec3\(\.88,\.96,1\),selected\),mix\(vec3\(\.10,\.13,\.18\),)vec3\([^)]*\)(,selected\),theme\))'),
 'watermark': ('z4tools attribution text',r'(col=mix\(col,)vec3\([^)]*\)(,text\(p,vec2\(164,299\),TEXT_Z4_WATERMARK\)\))'),
}
PRESETS={'crimson':'#b91c2c','burgundy':'#881337','ruby':'#dc2626','rose':'#e11d48','sapphire':'#2563eb','midnight':'#312e81','cyan':'#0891b2','teal':'#0d9488','gold':'#ca8a04','white':'#ffffff'}

def vec(h):
 return 'vec3('+','.join(f'{x/255:.4f}' for x in rgb(h))+')'

def normalize(h):return hexc(rgb(h))

def load():
 try:
  d=json.loads(CONFIG.read_text());return d if isinstance(d,dict) else {}
 except (OSError,ValueError):return {}

def replace_one(src,pattern,h):
 def sub(m):return m.group(1)+vec(h)+m.group(2)
 out,n=re.subn(pattern,sub,src)
 if n!=1:raise ValueError(f'expected one exact shader match, found {n}; no files changed')
 return out

def watermark_patch(atlas,frag):
 # The watermark lives in the generated text atlas, and the fragment shader renders it
 # directly below the NiftyFork subtitle. The tool reasserts this on future edits.
 label="    ('Z4_WATERMARK', 'z4tools', 14),"
 if "('Z4_WATERMARK'," not in atlas:
  anchor="    ('SUBTITLE', 'NiftyFork V1.0.0', 24),"
  if atlas.count(anchor)!=1:raise ValueError('subtitle atlas anchor missing; refusing to modify')
  atlas=atlas.replace(anchor,anchor+'\n'+label)
 if 'TEXT_Z4_WATERMARK' not in frag:
  anchor='    col=mix(col,vec3(.85,.97,1),text(p,vec2(164,263),TEXT_SUBTITLE));'
  # Account for recolored subtitle in a prior theme edit.
  pat=r'(?m)^(\s*col=mix\(col,vec3\([^)]*\),text\(p,vec2\(164,263\),TEXT_SUBTITLE\)\);)$'
  if len(re.findall(pat,frag))!=1:raise ValueError('subtitle shader anchor missing; refusing to modify')
  frag=re.sub(pat,lambda m:m.group(1)+'\n    col=mix(col,vec3(.85,.97,1),text(p,vec2(164,299),TEXT_Z4_WATERMARK));',frag)
 return atlas,frag

def apply(changes):
 if not FRAG.is_file() or not ATLAS.is_file() or not SDK.is_file():raise FileNotFoundError('gpubrew source not found')
 frag=FRAG.read_text();atlas=ATLAS.read_text();sdk=SDK.read_text()
 atlas,frag=watermark_patch(atlas,frag)
 for key,h in changes.items():
  if key not in ASSETS:raise ValueError('unknown asset '+key)
  h=normalize(h)
  if key=='accent':
   pat=r'(?m)^const vec3 BLUE\s*=\s*vec3\([^;]+;[^\n]*$'
   if len(re.findall(pat,sdk))!=1:raise ValueError('accent source anchor missing')
   sdk=re.sub(pat,'const vec3 BLUE='+vec(h)+'; // z4tools accent '+h,sdk)
  else:frag=replace_one(frag,ASSETS[key][1],h)
 # Validate every edit before touching disk. Atomic replacement per file.
 files={FRAG:frag,ATLAS:atlas,SDK:sdk}
 generated=ROOT/'homebrew-launcher/shaders/draw.glsl'
 if generated.is_file():files[generated]=sdk
 for path,content in files.items():
  temp=path.with_name(path.name+'.z4tools-tmp')
  temp.write_text(content);temp.replace(path)
 return list(files)

def choose_hex():
 print('presets: '+', '.join(f'{k}={v}' for k,v in PRESETS.items()))
 raw=input('preset name or custom #rrggbb (blank cancels): ').strip().lower()
 if not raw:return None
 return normalize(PRESETS.get(raw,raw))

def theme_menu():
 while True:
  print('\033[2J\033[H',end='')  # z4tools-clean-menu-v152
  print('\n=== z4tools v1.5.05 | theme maker ===')
  print('1) theme switcher (live or restart install)')
  print('2) advanced: edit individual launcher assets')
  print('3) inspect saved custom colors')
  print('4) settings / theme options')
  print('5) shader reload diagnostics (development preview)')
  print('6) hot-reload gpubrew theme (apply saved color live)')
  print('0) back')
  c=input('choose: ').strip()
  if c=='0':return
  if c=='5':
   from hot_reload import menu
   menu()
   continue
  if c=='6':
   from live_themes import reload_saved
   reload_saved()
   continue
  if c=='1':
   from live_themes import theme_switcher
   theme_switcher(PRESETS)
   continue
  if c=='4':
   print('settings: palette settings are stored in',CONFIG)
   print('all theme edits require confirmation and a restore point')
   continue
  if c=='3':print(json.dumps(load(),indent=2));continue
  if c!='2':continue
  changes={}
  if c=='1':
   h=choose_hex()
   if h:changes={'accent':h,'header':h,'header_end':hexc(palette(rgb(h))['light'])}
  else:
   keys=list(ASSETS)
   while True:
    print('\nasset color editor (0 to finish)')
    for i,k in enumerate(keys,1):print(f'{i}) {k}: {ASSETS[k][0]}'+(' = '+changes[k] if k in changes else ''))
    raw=input('asset number (0 done): ').strip()
    if raw=='0':break
    if not raw.isdigit() or not 1<=int(raw)<=len(keys):continue
    k=keys[int(raw)-1]
    try:h=choose_hex()
    except ValueError as e:print(e);continue
    if h:changes[k]=h
  if not changes:continue
  print('\nproposed changes:')
  for k,v in changes.items():print(' ',k,'=',v)
  print('the z4tools watermark will be kept below niftyfork v1.0.0.')
  if not ask('confirm these source modifications?'):continue
  if not point():continue
  try:
   paths=apply(changes)
   saved=load();saved.update(changes);CONFIG.write_text(json.dumps(saved,indent=2)+'\n')
   print('updated:',*[str(p.relative_to(ROOT)) for p in paths],sep='\n - ')
   print('build the launcher to apply the changes on your next switch session.')
  except Exception as e:print('edit cancelled/failed:',e)

def ensure_watermark():
 if not ask('add/repair the small z4tools watermark under niftyfork v1.0.0?'):return
 if not point():return
 try:apply({});print('watermark source installed. rebuild to see it.')
 except Exception as e:print('could not apply watermark:',e)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='watermark':ensure_watermark()
 else:theme_menu()
