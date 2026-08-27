#!/usr/bin/env python3
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

WWW = Path(os.environ.get("HOMEBUDGET_WWW", "/app/www")).resolve()
HOST = os.environ.get("HOMEBUDGET_HOST", "0.0.0.0")
PORT = int(os.environ.get("HOMEBUDGET_PORT", "8100"))
INDEX = WWW / "index.html"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WWW), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        return

    def _ingress(self) -> str:
        for key in ("X-Ingress-Path", "X-Forwarded-Prefix"):
            value = (self.headers.get(key) or "").rstrip("/")
            if value:
                return value
        return ""

    def end_headers(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "", "/index.html") or parsed.path.endswith(".html"):
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def _send_index(self) -> None:
        html = INDEX.read_text(encoding="utf-8").replace("{{BASE}}", self._ingress())
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        rel = unquote(parsed.path).lstrip("/")
        target = (WWW / rel).resolve() if rel else WWW
        try:
            target.relative_to(WWW)
        except ValueError:
            self.send_error(403)
            return
        if rel and target.is_file() and target.name != "index.html":
            return super().do_GET()
        self._send_index()


if __name__ == "__main__":
    if not INDEX.exists():
        raise SystemExit(f"index.html introuvable dans {WWW}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.serve_forever()
