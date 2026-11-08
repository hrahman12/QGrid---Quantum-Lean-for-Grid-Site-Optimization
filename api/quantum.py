"""Vercel Python function and local API handler for bounded, real PsiQDK jobs."""
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from viz.webgl.server.search_service import execute

LOCK = threading.Lock()

class handler(BaseHTTPRequestHandler):
    def respond(self, status, data):
        body = json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.respond(200, {'service': 'QGrid PsiQDK', 'status': 'ready', 'execution': 'POST a bounded settings object; native runtime is verified when a job runs.'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                return self.respond(413, {'error': 'Request must contain at most 8 KB of JSON.'})
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or 'settings' not in payload:
                raise ValueError('Provide a settings object.')
            if not LOCK.acquire(blocking=False):
                return self.respond(429, {'error': 'The simulator is busy. Try again after the current run.'})
            try:
                result = execute(payload['settings'])
            finally:
                LOCK.release()
            self.respond(200, result)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self.respond(400, {'error': str(error)})
        except subprocess.TimeoutExpired:
            self.respond(504, {'error': 'PsiQDK simulation timed out; no result was fabricated.'})
        except Exception:
            self.respond(503, {'error': 'The PsiQDK native worker is unavailable or failed. Check the server runtime. No fallback result was returned.'})

    def log_message(self, *_):
        pass
