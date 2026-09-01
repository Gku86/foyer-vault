#!/usr/bin/env python3
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

WWW = Path(os.environ.get("HOMEBUDGET_WWW", "/app/www")).resolve()
HOST = os.environ.get("HOMEBUDGET_HOST", "0.0.0.0")
PORT = int(os.environ.get("HOMEBUDGET_PORT", "8100"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WWW), **kwargs)

    def guess_type(self, path):
        if str(path).endswith(".js"):
            return "text/javascript"
        return super().guess_type(path)

    def end_headers(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html") or parsed.path.endswith(".html"):
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        rel = unquote(parsed.path).lstrip("/")
        target = (WWW / rel).resolve() if rel else WWW
        try:
            target.relative_to(WWW)
        except ValueError:
            self.send_error(403)
            return
        if rel and target.is_file():
            return super().do_GET()
        self.path = "/index.html"
        return super().do_GET()


if __name__ == "__main__":
    if not (WWW / "index.html").exists():
        raise SystemExit(f"index.html introuvable dans {WWW}")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.serve_forever()
