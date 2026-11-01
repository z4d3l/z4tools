#!/usr/bin/env python3
"""z4tools v1.5.05: persist themes and choose live or restart activation."""
import json,re,subprocess,sys
from pathlib import Path
from datetime import datetime
HERE=Path(__file__).resolve().parent
STATE=HERE/'live-theme.json'
CTRL=Path.home()/'z4-accent-live'/'z4_accent.py'

def normalize(value):
 from theme_maker_bridge import rgb,hexc
 return hexc(rgb(value))

def save(name,color):
 data={'name':name,'hex':normalize(color),'at':datetime.now().isoformat()}
 temp=STATE.with_suffix('.json.tmp')
 temp.write_text(json.dumps(data,indent=2)+'\n')
 temp.replace(STATE)
 print('saved',data['name'],data['hex'],'for automatic restoration on next launcher startup')
 return data

def live(data):
 if not CTRL.is_file():
  print('live controller missing; theme is saved for next restart')
  return
 result=subprocess.run([sys.executable,str(CTRL),'set',data['hex']],check=False)
 if result.returncode:
  print('live request failed; theme remains saved for next restart')
 else:
  print('live request sent; allow about 10 seconds to display')

def reload_saved():
 try: data=json.loads(STATE.read_text())
 except (OSError,ValueError):
  print('no saved theme');return
 live(data)

def theme_switcher(presets):
 keys=list(presets)
 while True:
  print('\033[2J\033[H',end='')  # z4tools-clean-menu-v152
  print('\n=== z4tools v1.5.05 | theme switcher ===')
  for i,k in enumerate(keys,1):print(f'{i:>2}) {k:<18} {presets[k]}')
  print(' c) custom hex   r) hot-reload saved   s) status   0) back')
  try:choice=input('choose: ').strip().lower()
  except (EOFError,KeyboardInterrupt):return
  if choice=='0':return
  if choice=='r':reload_saved();continue
  if choice=='s':
   if CTRL.is_file():subprocess.run([sys.executable,str(CTRL),'status'],check=False)
   else:print('live controller missing')
   continue
  if choice=='c':
   try:color=normalize(input('hex #rrggbb: ').strip())
   except ValueError as e:print(e);continue
   name='custom'
  elif choice.isdigit() and 1<=int(choice)<=len(keys):
   name=keys[int(choice)-1];color=presets[name]
  else:print('invalid choice');continue
  print('apply',name,color)
  print('1) hot-reload now (no restart)')
  print('2) install on next gpubrew restart (no live change)')
  print('0) cancel')
  mode=input('method: ').strip()
  if mode not in ('1','2'):continue
  data=save(name,color)
  if mode=='1':
   # z4tools-accent-setup-v151
   from accent_setup import checks,setup
   if all(ok for _,ok in checks()):
    live(data)
   else:
    print('live accent patch not fully installed')
    if setup():print('setup complete; restart gpubrew if prompted, then retry live mode')
    else:print('live mode unavailable; theme saved for next launch')

  else:print('queued for next gpubrew startup; current theme stays unchanged')
