import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("theme_maker",Path(__file__).with_name("theme-maker.py"))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rgb,palette,hexc=module.rgb,module.palette,module.hexc

def preview(h):
    p=palette(rgb(h))
    print('palette preview (hex values):')
    for k,v in p.items():print(k,hexc(v))
