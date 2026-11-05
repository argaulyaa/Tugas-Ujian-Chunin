"""Windows Edge check: unauthenticated dashboard redirects with visible notice."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import subprocess
import tempfile

class Notice(HTMLParser):
    visible = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == 'login-notice':
            self.visible = 'hidden' not in attrs

edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
with tempfile.TemporaryDirectory(prefix='visitor-redirect-') as profile:
    result = subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-first-run',
        '--user-data-dir=' + profile, '--virtual-time-budget=5000', '--dump-dom',
        'http://127.0.0.1:8090/' + (sys.argv[1] if len(sys.argv) > 1 else 'visitor-log.html')], capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=45)
    assert result.returncode == 0, 'Edge failed'
    parser = Notice()
    parser.feed(result.stdout)
    assert 'data-view="login"' in result.stdout, 'Dashboard did not redirect'
    assert parser.visible, 'Login notice is missing or hidden'
    assert 'Silakan login terlebih dahulu' in result.stdout
    print('PASS: unauthenticated index redirects to login with visible dedicated notice')
