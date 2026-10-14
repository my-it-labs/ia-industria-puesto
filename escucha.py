"""Responde en un puerto para comprobar que el host llega al contenedor."""
from http.server import BaseHTTPRequestHandler, HTTPServer


class Respuesta(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, formato, *args):
        return


HTTPServer(("0.0.0.0", 8080), Respuesta).serve_forever()
