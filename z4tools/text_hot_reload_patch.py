#!/usr/bin/env python3
import pathlib, shutil, sys, datetime
root=pathlib.Path.home()/'GPUBrewLauncher'
loop=root/'homebrew-launcher/launcher-loop.cjs'
runtime=root/'homebrew-launcher/app-runtime.cjs'
marker='z4-text-hot-reload-v1'
def patch():
    a=loop.read_text(); b=runtime.read_text()
    if marker in a and marker in b:
        print('patch already installed, no need to patch')
        return
    if marker in a or marker in b:
        print('incomplete patch detected; no changes made. restore both files from your backup first.')
        return
    print('this modifies two gpubrew runtime source files; a restart is required to activate it.')
    if input('install text hot-reload patch? type YES: ').strip() != 'YES':
        print('cancelled'); return
    target="   if(!appRequest&&!serviceRequest&&!connectionChanged)continue;"
    replacement="""   const z4Request=path.join(directory,'z4-text-hot-reload.request');
   const z4Pending=await fs.access(z4Request).then(()=>true,()=>false);
   if(!appRequest&&!serviceRequest&&!connectionChanged&&!z4Pending)continue; // z4-text-hot-reload-v1"""
    if a.count(target)!=1: raise RuntimeError('launcher-loop structure differs; no changes made')
    a=a.replace(target,replacement)
    target2="   const previousApp=runtime.active?.app,commands=await runtime.afterBatch();"
    replacement2="""   if(z4Pending){
    try{
     if(runtime.active)throw Error('Return to the launcher menu before text reload');
     await runtime.reloadTextAtlas();
     await fs.rename(z4Request,z4Request+'.done');
     console.log('z4: text atlas hot-reloaded');
    }catch(e){
     console.error('z4: reload failed:',e.message);
     await fs.rename(z4Request,z4Request+'.failed').catch(()=>{});
    }
   }
   const previousApp=runtime.active?.app,commands=await runtime.afterBatch();"""
    if a.count(target2)!=1: raise RuntimeError('launcher-loop boundary differs; no changes made')
    a=a.replace(target2,replacement2)
    target3=" runtime.close=async()=>{await runtime.active?.service?.close();};"
    replacement3=""" runtime.reloadTextAtlas=async()=>{ // z4-text-hot-reload-v1
  const font=await fs.readFile(path.join(__dirname,'shaders/launcher-text.bin'));
  check(font.length===catalogTools.ATLAS_BYTES,'Menu type atlas changed size');
  await rpc.write(mapped+1024,font);
 };
 runtime.close=async()=>{await runtime.active?.service?.close();};"""
    if b.count(target3)!=1: raise RuntimeError('app-runtime structure differs; no changes made')
    b=b.replace(target3,replacement3)
    import subprocess
    for line in subprocess.run(['ps','-ef'],capture_output=True,text=True).stdout.splitlines():
        if __import__('re').search(r'\s(?:/\S*/)?node\s+homebrew-launcher/launcher-loop\.cjs\s+', line):
            print('launcher is currently running. stop it before installing this patch.')
            return
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup=pathlib.Path.home()/('z4-hot-reload-backup-'+stamp)
    backup.mkdir(parents=True)
    shutil.copy2(loop,backup/loop.name);shutil.copy2(runtime,backup/runtime.name)
    try:
        loop.write_text(a)
        runtime.write_text(b)
    except Exception:
        shutil.copy2(backup/loop.name,loop)
        shutil.copy2(backup/runtime.name,runtime)
        raise
    print('patched; backups:',backup)
    print('IMPORTANT: patch becomes active only after a fresh launcher startup.')
def request():
    import os, tempfile
    candidates = [pathlib.Path(tempfile.gettempdir())]
    for key in ('TMPDIR', 'PREFIX'):
        value = os.environ.get(key)
        if value:
            base = pathlib.Path(value)
            candidates.append(base if key == 'TMPDIR' else base / 'tmp')
    # Preserve the legacy Termux fallback without assuming it exists on Linux.
    candidates.append(pathlib.Path('/data/data/com.termux/files/usr/tmp'))
    dirs = sorted({p.resolve() for base in candidates if base.is_dir()
                   for p in base.glob('gpubrewlauncher-*') if p.is_dir()})
    if not dirs: raise SystemExit('no runtime directories found')
    print('runtime directories:')
    for i,d in enumerate(dirs):print(i,d)
    if len(dirs)!=1:raise SystemExit('multiple runtimes found; pass the exact directory as an argument')
    d=dirs[0]
    if (d/'z4-text-hot-reload.request').exists():raise SystemExit('request already pending')
    (d/'z4-text-hot-reload.request').write_text('reload text atlas\n')
    print('request submitted:',d)
if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else ''
    if cmd=='install':patch()
    elif cmd=='request':request()
    else:print('usage: python z4_hot_reload.py install|request')
