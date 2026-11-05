"""Local-only Compose smoke test. Leaves project running; never deletes resources."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
os.chdir(root)
assert os.name == 'nt', 'Run through Windows .venv-win'
password = secrets.token_urlsafe(24)
salt = secrets.token_hex(16)
envfile = root / '.env'
if envfile.exists():
    raise SystemExit('Existing .env preserved: configure smoke credentials deliberately')
config = 'AUTH_USERNAME=local-test\nAUTH_SALT=' + salt + '\nAUTH_PASSWORD_HASH=' + hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex() + '\nFRONTEND_PORT=8090\n'
with envfile.open('x') as output:
    output.write(config)
for args in (['config', '--quiet'], ['build', '--pull=false'], ['up', '-d', '--no-build', '--pull', 'never'], ['exec', '-T', 'frontend', 'nginx', '-t']):
    subprocess.run(['docker', 'compose', *args], check=True)
base = 'http://127.0.0.1:8090'
for attempt in range(60):
    try:
        with urllib.request.urlopen(base+'/api/health', timeout=2) as response:
            assert response.status == 200
        break
    except (OSError, AssertionError):
        if attempt == 59:
            raise
        time.sleep(1)
with urllib.request.urlopen(base+'/login.html') as response:
    assert response.status == 200

def call(method, route, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    req = urllib.request.Request(base+'/api/'+route, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)

token = call('POST', 'login', {'username': 'local-test', 'password': password})['token']
before = call('GET', 'logs', token=token)
call('POST', 'logs', {'page': '/smoke-check', 'user_agent': 'local-smoke'}, token)
after = call('GET', 'logs', token=token)
assert after['total_hits'] == before['total_hits']+1
call('DELETE', 'logs?index='+str(after['total_hits']-1), token=token)
assert call('GET', 'logs', token=token) == before
call('POST', 'logout', token=token)
print('PASS: Compose config/build/start, nginx syntax, proxy health, login, CRUD count decrement, logout')
print('Only loopback port 8090 exposed. Random local-test password discarded; .env retains verifier only.')
print('No container removal, server connection, registry pull or Git operation performed.')
