"""Windows/Linux stdlib regression checks using disposable data only."""
import concurrent.futures
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from email.message import Message
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class API(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'backend/app.py').is_file(), 'backend/app.py not implemented')
        spec = importlib.util.spec_from_file_location('app', ROOT / 'backend/app.py')
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)
        self.tmp = tempfile.TemporaryDirectory()
        salt = '0123456789abcdef0123456789abcdef'
        digest = hashlib.pbkdf2_hmac('sha256', b'test-only-password', bytes.fromhex(salt), 600000).hex()
        self.server = self.app.make_server(('127.0.0.1', 0), Path(self.tmp.name), 'tester', salt, digest)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.token = None

    def tearDown(self):
        if hasattr(self, 'server'):
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
            self.tmp.cleanup()

    def req(self, method, path, body=None, raw=None, headers=None):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        headers = {'Content-Type': 'application/json', **(headers or {})}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        payload = raw if raw is not None else (json.dumps(body) if body is not None else None)
        conn.request(method, path, payload, headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def login(self):
        code, data = self.req('POST', '/login', {'username': 'tester', 'password': 'test-only-password'})
        self.assertEqual(code, 200)
        self.token = data['token']

    def test_trusted_proxy_ip_on_public_and_manual_logs(self):
        self.server.trusted_proxy = 'localhost'
        self.login()
        for route in ('/visit', '/logs'):
            with self.subTest(route=route):
                code, _ = self.req('POST', route, {'page': '/'}, headers={
                    'X-Real-IP': '203.0.113.7',
                    'X-Forwarded-For': '198.51.100.99',
                })
                self.assertEqual(code, 201)
                row = self.req('GET', '/logs')[1]['logs'][-1]
                self.assertEqual(row['ip'], '203.0.113.7')

    def test_untrusted_or_invalid_forwarding_uses_peer(self):
        self.login()
        cases = [
            (None, {'X-Real-IP': '203.0.113.7'}),
            ('192.0.2.44', {'X-Real-IP': '203.0.113.7'}),
            ('localhost', {'X-Forwarded-For': '203.0.113.7'}),
            ('localhost', {'X-Real-IP': 'not-an-ip'}),
            ('localhost', {'X-Real-IP': '203.0.113.7, 198.51.100.2'}),
            ('localhost', {'X-Real-IP': 'fe80::1%eth0'}),
        ]
        for proxy, headers in cases:
            self.server.trusted_proxy = proxy
            for route in ('/visit', '/logs'):
                with self.subTest(proxy=proxy, headers=headers, route=route):
                    self.assertEqual(self.req('POST', route, {'page': '/'}, headers=headers)[0], 201)
                    row = self.req('GET', '/logs')[1]['logs'][-1]
                    self.assertEqual(row['ip'], '127.0.0.1')

    def test_proxy_dns_refresh_failure_and_duplicate_headers(self):
        handler = object.__new__(self.app.Handler)
        handler.server = self.server
        handler.client_address = ('127.0.0.1', 1234)
        handler.headers = Message()
        handler.headers['X-Real-IP'] = '2001:0db8::1'
        self.server.trusted_proxy = 'frontend'
        address = lambda ip: [(self.app.socket.AF_INET, self.app.socket.SOCK_STREAM, 6, '', (ip, 0))]
        with patch.object(self.app.socket, 'getaddrinfo', side_effect=[
            address('127.0.0.1'), address('192.0.2.44'), self.app.socket.gaierror('DNS unavailable')
        ]) as resolve:
            self.assertEqual(handler.visitor_ip(), '2001:db8::1')
            self.assertEqual(handler.visitor_ip(), '127.0.0.1')
            self.assertEqual(handler.visitor_ip(), '127.0.0.1')
            self.assertEqual(resolve.call_count, 3)
        handler.headers['X-Real-IP'] = '203.0.113.7'
        self.assertEqual(handler.visitor_ip(), '127.0.0.1')

    def test_public_visit(self):
        self.assertEqual(self.req('POST', '/visit', {'page': '/other'})[0], 400)
        self.assertEqual(self.req('POST', '/visit', {'page': '/'})[0], 201)
        self.assertEqual(self.req('GET', '/visit')[0], 405)
        self.assertEqual(self.req('GET', '/logs')[0], 401)
        self.login()
        row = self.req('GET', '/logs')[1]['logs'][0]
        self.assertEqual(row['page'], '/')
        for _ in range(30):
            code, _ = self.req('POST', '/visit', {'page': '/'})
        self.assertEqual(code, 429)

    def test_crud_count_and_validation(self):
        self.assertEqual(self.req('GET', '/logs')[0], 401)
        self.login()
        self.assertEqual(self.req('POST', '/logs', {'page': '/lab', 'user_agent': 'test'})[0], 201)
        self.assertEqual(self.req('GET', '/logs')[1]['total_hits'], 1)
        for suffix in ('-1', 'abc'):
            self.assertEqual(self.req('DELETE', '/logs?index=' + suffix)[0], 400)
        self.assertEqual(self.req('DELETE', '/logs?index=9')[0], 404)
        self.assertEqual(self.req('POST', '/logs', raw='{')[0], 400)
        self.assertEqual(self.req('POST', '/logs', {'page': ''})[0], 400)
        self.assertEqual(self.req('POST', '/logs', raw='x' * 9000)[0], 413)
        self.assertEqual(self.req('DELETE', '/logs?index=0')[0], 200)
        self.assertEqual(self.req('GET', '/logs')[1], {'total_hits': 0, 'logs': []})
        self.assertEqual(self.req('GET', '/unknown')[0], 404)

    def test_invalid_storage_shape_preserved(self):
        self.login()
        path = Path(self.tmp.name) / 'visitor_logs.json'
        path.write_text('{"wrong": []}')
        self.assertEqual(self.req('GET', '/logs')[0], 500)
        self.assertEqual(self.req('GET', '/health')[0], 503)
        self.assertEqual(path.read_text(), '{"wrong": []}')

    def test_login_rate_limit_and_invalid_fields(self):
        self.assertEqual(self.req('POST', '/login', {'username': [], 'password': 'x'})[0], 400)
        for _ in range(10):
            self.assertEqual(self.req('POST', '/login', {'username': 'tester', 'password': 'bad'})[0], 401)
        self.assertEqual(self.req('POST', '/login', {'username': 'tester', 'password': 'bad'})[0], 429)

    def test_sessions(self):
        self.assertEqual(self.req('POST', '/login', {'username': 'tester', 'password': 'wrong'})[0], 401)
        self.login()
        self.server.sessions[self.token] = time.monotonic() - 1
        self.assertEqual(self.req('GET', '/logs')[0], 401)
        self.login()
        self.assertEqual(self.req('POST', '/logout')[0], 200)
        self.assertEqual(self.req('GET', '/logs')[0], 401)

    def test_storage_and_concurrency(self):
        self.login()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(lambda n: self.req('POST', '/logs', {'page': '/'+str(n)})[0], range(8)))
        self.assertEqual(codes, [201]*8)
        before = self.req('GET', '/logs')[1]
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.server = self.app.make_server(
            ('127.0.0.1', 0), Path(self.tmp.name), 'tester',
            self.server.salt.hex(), self.server.digest.hex(),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.assertEqual(self.req('GET', '/logs')[0], 401)
        self.login()
        self.assertEqual(self.req('GET', '/logs')[1], before)
        path = Path(self.tmp.name) / 'visitor_logs.json'
        path.write_text('broken')
        self.assertEqual(self.req('GET', '/health')[0], 503)
        self.assertEqual(self.req('POST', '/logs', {'page': '/new'})[0], 500)
        self.assertEqual(path.read_text(), 'broken')


if __name__ == '__main__':
    unittest.main()
