"""Run locally in Windows PowerShell; never send credentials to chat."""
import getpass
import hashlib
import os
from pathlib import Path
import secrets
import shutil

if os.name != 'nt':
    raise SystemExit('Use Windows .venv-win Python')
root = Path(__file__).resolve().parent
username = input('Local account username: ').strip()
if (not username or len(username) > 100 or not username.isascii()
        or not all(c.isalnum() or c in '._-' for c in username)):
    raise SystemExit('Use 1-100 ASCII letters, numbers, dot, underscore or hyphen')
password = getpass.getpass('Password (hidden, minimum 12 characters): ')
if len(password) < 12 or len(password) > 256 or password != getpass.getpass('Repeat password: '):
    raise SystemExit('Password length or confirmation invalid; nothing changed')
salt = secrets.token_hex(16)
digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
path = root / '.env'
if path.exists():
    if input('Replace existing local account verifier? Type YES: ') != 'YES':
        raise SystemExit('Cancelled; nothing changed')
    backup = root / ('.env.backup-' + secrets.token_hex(4))
    shutil.copy2(path, backup)
    print('Private recovery copy retained; do not commit .env* files.')
# ponytail: single local account and fixed loopback port; no remote provisioning.
with path.open('w', encoding='utf-8') as output:
    output.write(f'AUTH_USERNAME={username}\nAUTH_SALT={salt}\nAUTH_PASSWORD_HASH={digest}\nFRONTEND_PORT=8090\n')
print('Verifier saved. Password was not stored or printed. Existing container config has NOT changed.')
print('Ask for a scoped backend restart/recreation before using the account in Docker.')
