#!/usr/bin/env python3
import sys,pathlib,subprocess,shutil,datetime,json,time,hashlib
root=pathlib.Path.home()/'GPUBrewLauncher'; shader=root/'homebrew-launcher/shaders/launcher.frag'; loop=root/'homebrew-launcher/launcher-loop.cjs'; source=pathlib.Path(__file__).with_name('launcher.frag'); marker='// z4-accent-live-v1'
colors={'crimson':0,'blue':1,'purple':2,'pink':3}
def runtime():
 base=pathlib.Path('/data/data/com.termux/files/usr/tmp'); matches=[]
 for d in base.glob('gpubrewlauncher-*'):
  for f in d.glob('launcher*-loop.json'):
   try:
    j=json.loads(f.read_text())
    if not j.get('completed') and (d/'launcher-auto.json').exists():matches.append(d)
   except Exception:pass
 if len(set(matches))!=1:raise SystemExit(f'expected one active launcher runtime; found {len(set(matches))}')
 return matches[0]
def backup(f):
 dest=f.with_name(f.name+'.z4-accent-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
 shutil.copy2(f,dest);print('backup:',dest)
def main():
 op=sys.argv[1] if len(sys.argv)>1 else 'help'
 if op=='install':
  # Never modify files that an active launcher may be reading.
  for proc in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
   try:
    cmd=proc.read_bytes().replace(b'\x00',b' ').decode(errors='ignore')
    if 'homebrew-launcher/launcher-loop.cjs' in cmd or 'homebrew-launcher/launcher.cjs' in cmd:
     raise SystemExit('launcher process still running; stop GPUBrewLauncher normally before installing')
   except (PermissionError, FileNotFoundError, ProcessLookupError):pass
  if not shader.exists() or not loop.exists():raise SystemExit('launcher files missing')
  s=loop.read_text(); original=shader.read_text()
  if 'z4Accent(' in original:raise SystemExit('dynamic shader already installed; refusing duplicate')
  if marker in s:raise SystemExit('controller already installed')
  if 'const z4Pending=await fs.access(z4Request)' not in s or 'await startWorker();console.log(' not in s:raise SystemExit('unknown launcher loop version; no changes')
  if '#include "launcher-state.glsl"' not in original or 'vec3 water=mix(' not in original:raise SystemExit('unknown shader; no changes')
  # Source equality required: prevents overwriting custom edits since prototype was made.
  original_sha='ffd5b72401a01ebaa7f5daf29841da2ec334a6e67b50bd7a292f4aaef6cdcaa1'
  if hashlib.sha256(original.encode()).hexdigest()!=original_sha:raise SystemExit('shader differs from uploaded crimson version; no changes')
  if not shutil.which('glslangValidator') or not shutil.which('spirv-val'):raise SystemExit('missing shader tools')
  stage=root/'z4tools-accent-test/z4-dynamic-accent';stage.mkdir(parents=True,exist_ok=True)
  for glsl in (root/'homebrew-launcher/shaders').glob('*.glsl'):shutil.copy2(glsl,stage/glsl.name)
  shutil.copy2(source,stage/'launcher.frag')
  subprocess.run(['glslangValidator','-V','--target-env','vulkan1.0','-S','frag','-I.','-o','launcher.frag.spv','launcher.frag'],cwd=stage,check=True)
  subprocess.run(['spirv-val','--target-env','vulkan1.0','launcher.frag.spv'],cwd=stage,check=True)
  backup(shader);backup(loop)
  snippet='''\n   // z4-accent-live-v1: handle a requested accent while the GPU worker is stopped.\n   const z4AccentRequest=path.join(directory,'z4-accent.request');\n   if(await fs.access(z4AccentRequest).then(()=>true,()=>false)){\n    let z4Ack;\n    try{\n     const requested=(await fs.readFile(z4AccentRequest,'utf8')).trim();\n     const choices={crimson:0,blue:1,purple:2,pink:3};\n     if(!Object.prototype.hasOwnProperty.call(choices,requested))throw Error('Unknown accent');\n     if(runtime.active)throw Error('Return to launcher menu before changing accent');\n     await stopWorker();\n     await sdkRuntime.atBoundary();\n     const value=Buffer.alloc(4);value.writeFloatLE(choices[requested]);\n     await rpc.write(prepared.controls.mapped+972,value);\n     z4Ack={status:'accent-applied',accent:requested,shaderSwapped:false,at:new Date().toISOString()};\n     await prepareFrame();await startWorker();\n    }catch(error){\n     z4Ack={status:'error',error:error.message,at:new Date().toISOString()};\n     if(thread===null){try{await prepareFrame();await startWorker();}catch(e){z4Ack.restartError=e.message;}}\n    }\n    await fs.writeFile(path.join(directory,'z4-accent.ack.json'),JSON.stringify(z4Ack,null,2));\n    await fs.unlink(z4AccentRequest).catch(()=>{});\n    continue;\n   }\n'''
  anchor="   const z4Request=path.join(directory,'z4-text-hot-reload.request');"
  if s.count(anchor)!=1:raise SystemExit('unexpected loop anchor')
  s=s.replace(anchor,snippet+anchor)
  # Install GLSL source and compiled SPIR-V only while launcher is stopped.
  shutil.copy2(source,shader);shutil.copy2(stage/'launcher.frag.spv',shader.with_suffix('.frag.spv'))
  loop.write_text(s)
  check=subprocess.run(['node','--check',str(loop)],capture_output=True,text=True)
  if check.returncode:raise SystemExit('javascript syntax failed: '+check.stderr)
  print('installed. restart GPUBrewLauncher normally once; then use set blue')
 elif op=='set':
  # z4tools-v1.5-hex
  if len(sys.argv)<3 or (sys.argv[2] not in colors and not __import__('re').fullmatch(r'#[0-9a-fA-F]{6}',sys.argv[2])):raise SystemExit('usage: set crimson|blue|purple|pink|#rrggbb')
  d=runtime(); req=d/'z4-accent.request'; ack=d/'z4-accent.ack.json'
  if req.exists():raise SystemExit('previous request pending')
  if ack.exists():ack.unlink()
  req.write_text(sys.argv[2]);print('request sent:',sys.argv[2]);print('wait a few seconds, then run: python z4_accent.py status')
 elif op=='status':
  d=runtime();f=d/'z4-accent.ack.json';print(f.read_text() if f.exists() else 'no acknowledgment yet')
 else:print('usage: python z4_accent.py install|set blue|status')
if __name__=='__main__':main()
