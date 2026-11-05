"""Single-process coursework API. Configure password verifier through environment."""
import hashlib
import hmac
import ipaddress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import tempfile
import threading
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def read_logs(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            raise OSError('Invalid storage') from exc
        if not isinstance(data, list) or not all(
            isinstance(row, dict) and all(isinstance(row.get(k), str)
                                         for k in ('page', 'ip', 'timestamp', 'user_agent'))
            for row in data
        ):
            raise OSError('Invalid storage')
        return data

    def save_logs(self, data):
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             delete=False) as output:
                name = output.name
                json.dump(data, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # ponytail: no request logs to avoid accidental credential/token retention.

    def reply(self, code, data):
        raw = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def body(self):
        if self.headers.get('Transfer-Encoding'):
            raise ValueError('Unsupported transfer encoding')
        size = int(self.headers.get('Content-Length', '0'))
        if size < 1:
            raise ValueError('JSON body required')
        if size > 8192:
            raise OverflowError('Body too large')
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('JSON content type required')
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError('JSON object required')
        return data

    def visitor_ip(self):
        peer = self.client_address[0]
        forwarded = self.headers.get_all('X-Real-IP', [])
        if not self.server.trusted_proxy or len(forwarded) != 1:
            return peer
        try:
            # Resolve on each write so a recreated proxy's old IP is not trusted.
            addresses = socket.getaddrinfo(
                self.server.trusted_proxy, None, type=socket.SOCK_STREAM
            )
            if not any(ipaddress.ip_address(item[4][0]) == ipaddress.ip_address(peer)
                       for item in addresses):
                return peer
            if '%' in forwarded[0]:
                return peer
            return str(ipaddress.ip_address(forwarded[0]))
        except (OSError, ValueError):
            return peer  # DNS failure or malformed forwarding fails closed.

    def authorized(self):
        token = self.headers.get('Authorization', '').removeprefix('Bearer ')
        now = time.monotonic()
        with self.server.lock:
            self.server.sessions = {k: v for k, v in self.server.sessions.items() if v > now}
            return token if token in self.server.sessions else None

    def route(self, method):
        self.connection.settimeout(5)
        route = urlsplit(self.path)
        server = self.server
        if route.path == '/health' and method == 'GET':
            try:
                with server.lock:
                    server.read_logs()
                    if not os.access(server.path.parent, os.W_OK):
                        raise OSError('Storage unavailable')
                return self.reply(200, {'status': 'ok'})
            except (OSError, ValueError):
                return self.reply(503, {'error': 'Storage unavailable'})
        if route.path == '/visit':
            if method != 'POST':
                return self.reply(405, {'error': 'Method not allowed'})
            data = self.body()
            if data != {'page': '/'}:
                raise ValueError('Landing page required')
            agent = self.headers.get('User-Agent', '')[:1024]
            visitor_ip = self.visitor_ip()
            now = time.monotonic()
            with server.lock:
                if now - server.visit_window >= 60:
                    server.visit_window, server.visits = now, 0
                # ponytail: global limit bounds memory; per-IP limits belong at the production proxy.
                if server.visits >= 30:
                    return self.reply(429, {'error': 'Try again later'})
                server.visits += 1
                logs = server.read_logs()
                logs.append({'page': '/', 'user_agent': agent, 'ip': visitor_ip,
                             'timestamp': datetime.now(timezone.utc).isoformat()})
                server.save_logs(logs)
            return self.reply(201, {'status': 'recorded'})
        if route.path == '/login' and method == 'POST':
            data = self.body()
            username, password = data.get('username'), data.get('password')
            if (not isinstance(username, str) or not isinstance(password, str)
                    or len(username) > 100 or len(password) > 256):
                raise ValueError('Invalid credentials format')
            # ponytail: single predefined account; global bounded window avoids unbounded IP maps.
            now = time.monotonic()
            with server.lock:
                if now - server.login_window >= 60:
                    server.login_window, server.attempts = now, 0
                if server.attempts >= 10:
                    return self.reply(429, {'error': 'Try again later'})
                server.attempts += 1
            digest = hashlib.pbkdf2_hmac('sha256', password.encode(), server.salt, 600000)
            if (not hmac.compare_digest(username, server.username)
                    or not hmac.compare_digest(digest, server.digest)):
                return self.reply(401, {'error': 'Invalid credentials'})
            token = secrets.token_urlsafe(32)
            with server.lock:
                server.sessions = {k: v for k, v in server.sessions.items() if v > now}
                if len(server.sessions) >= 100:
                    return self.reply(429, {'error': 'Session limit'})
                server.sessions[token] = now + 1800
            return self.reply(200, {'token': token, 'expires_in': 1800})
        if route.path not in ('/logs', '/logout'):
            return self.reply(404, {'error': 'Not found'})
        token = self.authorized()
        if not token:
            return self.reply(401, {'error': 'Authentication required'})
        if route.path == '/logout':
            if method != 'POST':
                return self.reply(405, {'error': 'Method not allowed'})
            with server.lock:
                server.sessions.pop(token, None)
            return self.reply(200, {'status': 'logged out'})
        if method == 'POST':
            data = self.body()
            page, agent = data.get('page'), data.get('user_agent', '')
            visitor_ip = self.visitor_ip()
            if (not isinstance(page, str) or not page.strip() or len(page) > 500
                    or not isinstance(agent, str) or len(agent) > 1024):
                raise ValueError('Invalid log fields')
        if method == 'DELETE':
            query = parse_qs(route.query, keep_blank_values=True)
            indices = query.get('index', [])
            if len(indices) != 1 or not indices[0].isascii() or not indices[0].isdecimal():
                raise ValueError('Nonnegative index required')
            index = int(indices[0])
        with server.lock:
            logs = server.read_logs()
            if method == 'POST':
                logs.append({'page': page.strip(), 'user_agent': agent, 'ip': visitor_ip,
                             'timestamp': datetime.now(timezone.utc).isoformat()})
                server.save_logs(logs)
            elif method == 'DELETE':
                if index >= len(logs):
                    return self.reply(404, {'error': 'Index not found'})
                logs.pop(index)
                server.save_logs(logs)
            result = {'total_hits': len(logs), 'logs': [dict(row, index=i) for i, row in enumerate(logs)]}
        self.reply(201 if method == 'POST' else 200, result)

    def handle_method(self, method):
        try:
            self.route(method)
        except OverflowError:
            self.reply(413, {'error': 'Body too large'})
        except (ValueError, UnicodeError):
            # Corrupt storage is an internal error, not client input.
            self.reply(400, {'error': 'Invalid request'})
        except (OSError, TypeError):
            self.reply(500, {'error': 'Storage or connection error'})

    def do_GET(self):
        self.handle_method('GET')

    def do_POST(self):
        self.handle_method('POST')

    def do_DELETE(self):
        self.handle_method('DELETE')


def make_server(address, data_dir, username, salt, digest, trusted_proxy=None):
    salt, digest = bytes.fromhex(salt), bytes.fromhex(digest)
    if not username or len(salt) < 16 or len(digest) != 32:
        raise ValueError('Valid authentication configuration required')
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / 'visitor_logs.json'
    try:
        with path.open('x', encoding='utf-8') as output:
            output.write('[]')
    except FileExistsError:
        pass
    server = Server(address, Handler)
    server.path, server.username, server.salt, server.digest = path, username, salt, digest
    server.trusted_proxy = trusted_proxy
    server.lock = threading.Lock()
    server.sessions, server.attempts, server.login_window = {}, 0, time.monotonic()
    server.visits, server.visit_window = 0, time.monotonic()
    return server


if __name__ == '__main__':
    server = make_server(('0.0.0.0', 5000), Path(os.environ.get('DATA_DIR', '/var/lib/backend_data')),
                         os.environ['AUTH_USERNAME'], os.environ['AUTH_SALT'],
                         os.environ['AUTH_PASSWORD_HASH'], os.environ.get('TRUSTED_PROXY'))
    try:
        server.serve_forever()
    finally:
        server.server_close()
