"""Local launcher. Creates an empty demo snapshot; never bundles chapter data."""
import os, json, runpy
from pathlib import Path
root=Path(__file__).resolve().parent
config=root/'.env'
if not config.exists():
 config.write_text((root/'.env.example').read_text())
for line in config.read_text().splitlines():
 if line.strip() and not line.lstrip().startswith('#') and '=' in line:
  key,value=line.split('=',1)
  os.environ.setdefault(key.strip(),value.strip())
private=Path(os.environ.get('HUB_PRIVATE_DIR',str(root/'private')))
private.mkdir(parents=True,exist_ok=True)
if os.environ.get('HUB_PREVIEW')=='1' and not (private/'source-data.json').exists():
 raw={key:[] for key in ['directory','attendance','policy','buddies','academics','calendar','shifts','links']}
 (private/'source-data.json').write_text(json.dumps(raw))
runpy.run_path(str(root/'server.py'),run_name='__main__')
