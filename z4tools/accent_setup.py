#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys
H=Path.home(); R=H/'GPUBrewLauncher'; Z=H/'z4tools'
CHECKS=[
 ('live runtime',R/'homebrew-launcher/launcher-loop.cjs','z4-accent-live-v1'),
 ('custom color runtime',R/'homebrew-launcher/launcher-loop.cjs','z4tools-v1.5-rgb666'),
 ('automatic restoration',R/'homebrew-launcher/launcher-loop.cjs','z4tools-v1.5.05-auto-restore'),
 ('synced accent shader',R/'homebrew-launcher/shaders/launcher.frag','z4Accent(BLUE)'),
 ('custom color shader',R/'homebrew-launcher/shaders/launcher.frag','z4tools v1.5 dynamic accent'),
 ('live controller',H/'z4-accent-live/z4_accent.py','z4tools-v1.5-hex'),
]
def checks():
 out=[]
 for name,p,marker in CHECKS:
  try:ok=marker in p.read_text()
  except OSError:ok=False
  out.append((name,ok))
 p=R/'homebrew-launcher/shaders/launcher.frag.spv'
 out.append(('compiled shader',p.is_file() and p.stat().st_size>0))
 return out
def yes(question):
 try:return input(question+' [y/N]: ').strip().lower()=='y'
 except (KeyboardInterrupt,EOFError):return False
def running():
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:
   s=p.read_bytes().replace(b'\x00',b' ').decode(errors='ignore')
   if 'homebrew-launcher/launcher-loop.cjs' in s or 'homebrew-launcher/launcher.cjs' in s:return True
  except OSError:pass
 return False
def setup():
 results=checks()
 print('\n=== accent hot-load patch setup ===')
 for name,ok in results:print(('ok: ' if ok else 'missing: ')+name)
 if all(ok for _,ok in results):
  print('no need to patch, already patched');return True
 print('some accent components are missing')
 if not yes('install missing patches?'):
  print('cancelled');return False
 if running():
  print('stop gpubrew normally before modifying runtime or shaders');return False
 for path in [H/'z4tools-v1.5-live-themes/install.py',H/'z4tools-v1.5.05/install.py']:
  if all(ok for _,ok in checks()):break
  if not path.is_file():continue
  if not yes('check installer '+str(path)+'?'):continue
  if subprocess.run([sys.executable,str(path),'check'],check=False).returncode:continue
  if yes('run this installer (backups created)?'):
   subprocess.run([sys.executable,str(path),'install'],check=False)
 if all(ok for _,ok in checks()):
  print('no need to patch, already patched');return True
 print('patch still incomplete. no further automatic changes attempted.')
 return False
if __name__=='__main__':setup()
