from http.server import ThreadingHTTPServer
from api.quantum import handler

if __name__ == '__main__':
    print('QGrid PsiQDK API: http://127.0.0.1:8787/api/quantum', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8787), handler).serve_forever()
