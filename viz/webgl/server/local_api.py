from http.server import ThreadingHTTPServer
from api.quantum import handler as QuantumHandler
from .physics_service import execute_physics


class handler(QuantumHandler):
    def execute_job(self, settings):
        if self.path.split('?')[0] == '/api/physics':
            return execute_physics(settings)
        return super().execute_job(settings)

if __name__ == '__main__':
    print('QGrid PsiQDK API: http://127.0.0.1:8787/api/quantum', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8787), handler).serve_forever()
