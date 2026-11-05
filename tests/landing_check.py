"""Real Windows browser landing visit; adds one intentional demo record."""
import json
import subprocess
import tempfile
import urllib.request

def count():
    raw = subprocess.check_output(['docker','compose','exec','-T','backend','python','-c',"import json;print(len(json.load(open('/var/lib/backend_data/visitor_logs.json'))))"], text=True)
    return int(raw.strip())

before = count()
with tempfile.TemporaryDirectory(prefix='visitor-landing-') as profile:
    result = subprocess.run([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', '--headless=new','--disable-gpu','--no-first-run','--user-data-dir='+profile,'--virtual-time-budget=5000','--dump-dom','http://127.0.0.1:8090/'], capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
    assert result.returncode == 0
    assert 'Memahami sistem' in result.stdout, result.stdout[:400]
assert count() == before + 1, 'Expected one landing visit'
assert urllib.request.urlopen('http://127.0.0.1:8090/api/health').status == 200
print('PASS: real browser root renders landing, adds exactly one visit; health 200')
