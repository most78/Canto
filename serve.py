"""Servidor local de Canto: como `python -m http.server`, pero sin caché.

Así el navegador siempre carga la última versión del código tras una
actualización (los módulos JS se quedaban en caché). Sólo escucha en tu PC.

    python serve.py [puerto]
"""
import functools
import http.server
import sys
from pathlib import Path


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    handler = functools.partial(NoCacheHandler, directory=str(Path(__file__).resolve().parent))
    with http.server.ThreadingHTTPServer(('127.0.0.1', port), handler) as server:
        print(f'Canto en http://localhost:{port}/  (Ctrl+C o cierra la ventana para apagarlo)')
        server.serve_forever()


if __name__ == '__main__':
    main()
