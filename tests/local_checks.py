"""Non-destructive Windows bind-mount and headless browser checks."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import urllib.request

assert os.name == 'nt', 'Windows interpreter required'
root = Path(__file__).resolve().parents[1]
os.chdir(root)
evidence = root / 'evidence'
evidence.mkdir(exist_ok=True)

def output(args):
    return subprocess.check_output(args, text=True).strip()

before = output(['docker', 'inspect', 'uts-visitor-log-frontend-1', '--format', '{{.Image}} {{.State.StartedAt}}'])
probe = root / 'frontend' / ('bind-probe-' + secrets.token_hex(8) + '.txt')
try:
    probe.write_text('first', encoding='utf-8')
    assert urllib.request.urlopen('http://127.0.0.1:8090/' + probe.name).read() == b'first'
    probe.write_text('updated-without-rebuild', encoding='utf-8')
    assert urllib.request.urlopen('http://127.0.0.1:8090/' + probe.name).read() == b'updated-without-rebuild'
    assert output(['docker', 'inspect', 'uts-visitor-log-frontend-1', '--format', '{{.Image}} {{.State.StartedAt}}']) == before
finally:
    probe.unlink(missing_ok=True)
print('PASS: actual bind-mount host edit served without image rebuild or container restart')
edge = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
with tempfile.TemporaryDirectory(prefix='visitor-browser-') as profile:
    result = subprocess.run([str(edge), '--headless=new', '--disable-gpu', '--no-first-run',
                             '--user-data-dir=' + profile, '--window-size=1365,900',
                             '--screenshot=' + str(evidence / 'login-desktop.png'),
                             '--dump-dom', 'http://127.0.0.1:8090/login.html'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45)
    assert result.returncode == 0, result.stderr[-500:]
    assert 'id="login-form"' in result.stdout
    assert (evidence / 'login-desktop.png').stat().st_size > 1000
    (evidence / 'login-dom.html').write_text(result.stdout, encoding='utf-8')
    print('PASS: Windows Edge headless rendered real login page and saved desktop screenshot')
report = {'bind_mount_live_edit': True, 'browser_login_render': True,
          'authenticated_browser_flow': 'NOT_TESTED',
          'container_remove_recreate': 'NOT_EXECUTED', 'frontend_image_and_start': before}
(evidence / 'local-checks.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
