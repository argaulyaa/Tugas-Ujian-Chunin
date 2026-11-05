"""Approved backend-only recreation; compares existing storage without reading secrets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

assert os.name == 'nt', 'Use Windows Python'
root = Path(__file__).resolve().parents[1]
os.chdir(root)

def run(args):
    return subprocess.check_output(args)

def inspect():
    return json.loads(run(['docker', 'inspect', 'uts-visitor-log-backend-1']))[0]

def data():
    return run(['docker', 'compose', 'exec', '-T', 'backend', 'python', '-c',
                "import sys,pathlib; sys.stdout.buffer.write(pathlib.Path('/var/lib/backend_data/visitor_logs.json').read_bytes())"])

before = inspect()
mount = next(m for m in before['Mounts'] if m['Destination'] == '/var/lib/backend_data')
assert mount['Type'] == 'volume' and mount['Name'] == 'visitor-log-data'
original = data()
assert len(json.loads(original)) >= 2, 'Need two existing records; do not invent owner data'
subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', '--no-build', '--pull', 'never', 'backend'], check=True)
after = inspect()
assert before['Id'] != after['Id']
assert any(m.get('Name') == mount['Name'] and m['Destination'] == mount['Destination'] for m in after['Mounts'])
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=2) as response:
            assert response.status == 200
        break
    except OSError:
        if attempt == 29:
            raise
        time.sleep(1)
assert data() == original, 'Data changed; preserve volume and investigate'
report = {'result': 'PASS', 'records': len(json.loads(original)),
          'storage_sha256_before_and_after': hashlib.sha256(original).hexdigest(),
          'old_container': before['Id'], 'new_container': after['Id'],
          'volume': mount['Name'], 'proxy_health': 'PASS',
          'scope': 'Exact existing JSON bytes preserved across Compose backend container replacement; no authenticated browser assertion'}
(root / 'evidence').mkdir(exist_ok=True)
(root / 'evidence' / 'persistence.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
