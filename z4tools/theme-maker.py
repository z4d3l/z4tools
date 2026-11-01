#!/usr/bin/env python3
"""GPUBrewLauncher accent theme maker. Python 3 standard library only."""
from pathlib import Path
import re, colorsys, shutil, subprocess, sys

PRESETS = {
    '1': ('crimson', '#b91c2c'),
    '2': ('ruby', '#dc2626'),
    '3': ('burgundy', '#881337'),
    '4': ('rose', '#e11d48'),
    '5': ('purple', '#7c3aed'),
    '6': ('midnight violet', '#5b21b6'),
    '7': ('sapphire', '#2563eb'),
    '8': ('cyan', '#0891b2'),
    '9': ('teal', '#0d9488'),
    '10': ('emerald', '#059669'),
    '11': ('amber', '#d97706'),
    '12': ('gold', '#ca8a04'),
}

def rgb(h):
    h = h.strip().lstrip('#')
    if len(h) == 3 and re.fullmatch('[0-9a-fA-F]{3}', h):
        h = ''.join(c * 2 for c in h)
    if not re.fullmatch('[0-9a-fA-F]{6}', h):
        raise ValueError('enter a valid hex color, like #b91c2c')
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def hexc(c):
    return '#' + ''.join(f'{max(0,min(255,round(v))):02x}' for v in c)

def blend(a,b,t):
    return tuple(round(x*(1-t)+y*t) for x,y in zip(a,b))

def glsl(c):
    return 'vec3(' + ','.join(f'{v/255:.4f}' for v in c) + ')'

def palette(c):
    return {
        'base':c,
        'deep':blend(c,(7,8,16),.76),
        'dark':blend(c,(9,10,20),.47),
        'mid':blend(c,(255,255,255),.15),
        'light':blend(c,(255,255,255),.43),
        'bright':blend(c,(255,255,255),.64),
        'pale':blend(c,(255,255,255),.80),
    }

def replace_line(s, prefix, replacement):
    # Only target the known launcher visuals, never app-specific shaders.
    lines=s.splitlines(keepends=True)
    matches=[i for i,l in enumerate(lines) if l.lstrip().startswith(prefix)]
    if len(matches)!=1:
        raise RuntimeError(f'expected exactly one launcher line starting with {prefix!r}, found {len(matches)}; no files changed')
    i=matches[0]
    indent=lines[i][:len(lines[i])-len(lines[i].lstrip())]
    lines[i]=indent+replacement+'\n'
    return ''.join(lines)

def update(root,p):
    sdk=root/'sdk/include/draw.glsl'
    frag=root/'homebrew-launcher/shaders/launcher.frag'
    if not sdk.is_file() or not frag.is_file():
        raise FileNotFoundError('cannot find sdk/include/draw.glsl and homebrew-launcher/shaders/launcher.frag')
    a=sdk.read_text(); b=frag.read_text()
    # Preserve the existing symbol used throughout the launcher shader.
    pat=r'(?m)^const vec3 BLUE\s*=\s*vec3\([^;]+;[^\n]*$'
    if len(re.findall(pat,a))!=1:
        raise RuntimeError('sdk accent definition not found; no files changed')
    a=re.sub(pat, f'const vec3 BLUE={glsl(p["base"])}; // generated accent {hexc(p["base"])}',a)
    # Header gradient and its layered highlights. Keep non-accent UI colors intact.
    b=replace_line(b,'vec3 water=mix(',f'vec3 water=mix({glsl(p["deep"])},{glsl(p["mid"])},clamp(p.x/2300.0+p.y/1500.0,0.0,1.0));')
    b=re.sub(r'(?m)^([ \t]*)col=mix\(col,mix\(vec3\([^)]*\),vec3\([^)]*\),depth/3\.0\),sheet\*\.65\);$',lambda m:m.group(1)+f'col=mix(col,mix({glsl(p["dark"])},{glsl(p["light"])},depth/3.0),sheet*.65);',b)
    # The prefix above may match another line in future versions; fail safely if so.
    b=re.sub(r'(?m)^([ \t]*)col=mix\(col,vec3\([^)]*\),line\(p\.y-edge,\.8\)\*\.55\);$',lambda m:m.group(1)+f'col=mix(col,{glsl(p["light"])},line(p.y-edge,.8)*.55);',b)
    # Replace other accent-only constants by their shader statement anchors.
    for anchor, value in [
        ('col=mix(col,vec3(.95,.34,.42),strand*', 'light'),
        ('col=mix(col,vec3(.73,.18,.28),ribbon*', 'mid'),
        ('col=mix(col,vec3(.58,.20,.29),line(p.y-height', 'mid'),
        ('col=mix(col,vec3(.96,.64,.66),fill(distanceToCenter', 'pale'),
        ('col=mix(col,vec3(.95,.73,.76),text(p,vec2(164,75)', 'pale'),
        ('col=mix(col,vec3(.98,.80,.82),text(p,vec2(164,263)', 'pale'),
        ('col=mix(col,vec3(.97,.62,.67),line(length(emblem)', 'light'),
    ]:
        for i,line in enumerate(b.splitlines()):
            if line.lstrip().startswith(anchor):
                b=re.sub(r'(?m)^(\s*col=mix\(col,)vec3\([^)]*\)',lambda m:m.group(1)+glsl(p[value]),b,count=1)
                break
    # Header-specific multi-color gradients.
    b=re.sub(r'mix\(vec3\(\.52,\.20,\.30\),vec3\(\.92,\.55,\.60\),sea\)',f'mix({glsl(p["dark"])},{glsl(p["light"])},sea)',b)
    # Keep theme source synchronized with generated shader copy, when present.
    out=[(sdk,a),(frag,b)]
    generated=root/'homebrew-launcher/shaders/draw.glsl'
    if generated.is_file(): out.append((generated,a))
    # Write only after all validation has passed; keep .bak originals once.
    for path,content in out:
        backup=path.with_name(path.name+'.theme-backup')
        if not backup.exists(): shutil.copy2(path,backup)
        path.write_text(content)
    return [str(path.relative_to(root)) for path,_ in out]

def main():
    root=Path.home()/'GPUBrewLauncher'
    while True:
        print('\n=== z4tools | theme maker ===')
        for k,(name,h) in PRESETS.items(): print(f' {k:>2}. {name:<18} {h}')
        print('  c. custom hex')
        print('  0. back to main menu')
        try:
            choice=input('choose a color: ').strip().lower()
        except (EOFError,KeyboardInterrupt):
            print('\nreturning to main menu');return 0
        if choice in ('0','b','back','exit','q'):
            return 0
        if choice in PRESETS:
            name,h=PRESETS[choice]
        elif choice in ('c','custom'):
            try: h=input('hex color (#rrggbb, blank to cancel): ').strip()
            except (EOFError,KeyboardInterrupt): print('\nreturning to main menu');return 0
            if not h: continue
            name='custom'
        else:
            print('invalid selection');continue
        try: p=palette(rgb(h))
        except ValueError as e: print(e);continue
        print(f'\n{name} palette:')
        for label,c in p.items():print(f'  {label:<8} {hexc(c)}')
        print(f'\nproject: {root}')
        try: answer=input('apply these colors? [y/N]: ').strip().lower()
        except (EOFError,KeyboardInterrupt): print('\nreturning to main menu');return 0
        if answer!='y':continue
        if subprocess.run(["bash",str(Path(__file__).with_name("backup.sh")),"backup"]).returncode != 0:
            print("restore point failed; theme change cancelled");continue
        try: modified=update(root,p)
        except (OSError,RuntimeError) as e:print('error:',e);continue
        print('\nupdated:')
        for filename in modified:print('  '+filename)
        print('original files backed up as *.theme-backup')
        try: rebuild=input('\nrebuild launcher now? [y/N]: ').strip().lower()
        except (EOFError,KeyboardInterrupt): print('\nreturning to main menu');return 0
        if rebuild=='y':
            result=subprocess.run(['bash','homebrew-launcher/build-launcher.sh'],cwd=root)
            if result.returncode:print('build failed; see error above')
            else:print('build finished. restart the launcher using your usual process.')
        else:
            print('to build later: cd ~/GPUBrewLauncher && bash homebrew-launcher/build-launcher.sh')
        # Always return to the main menu after applying a theme.
        return 0

if __name__=='__main__':sys.exit(main())
