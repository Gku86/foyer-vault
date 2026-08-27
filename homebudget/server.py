#!/usr/bin/env python3
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

WWW = Path(os.environ.get("HOMEBUDGET_WWW", "/app/www")).resolve()
HOST = os.environ.get("HOMEBUDGET_HOST", "0.0.0.0")
PORT = int(os.environ.get("HOMEBUDGET_PORT", "8100"))
INDEX = WWW / "index.html"
VERSION = "1.8.9"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ico": "image/x-icon",
}


def log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        log("%s - %s" % (self.address_string(), fmt % args))

    def _ingress(self) -> str:
        for key in ("X-Ingress-Path", "X-Forwarded-Prefix"):
            value = (self.headers.get(key) or "").rstrip("/")
            if value:
                return value
        return ""

    def _send(self, status: int, body: bytes, content_type: str, cache: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-HomeBudget", VERSION)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _index(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        base = self._ingress()
        if base:
            html = html.replace('<base href="./">', '<base href="%s/">' % base)
            log("ingress base %s" % base)
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", "no-store")

    def _file(self, path: Path) -> None:
        data = path.read_bytes()
        ext = path.suffix.lower()
        ctype = MIME.get(ext) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        cache = "no-store" if ext in {".html", ".js", ".css", ".webmanifest"} else "public, max-age=86400"
        self._send(200, data, ctype, cache)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        rel = unquote(parsed.path).lstrip("/")
        log("GET %s ingress=%s" % (parsed.path, self.headers.get("X-Ingress-Path") or "-"))
        if not rel or rel == "index.html":
            self._index()
            return
        target = (WWW / rel).resolve()
        try:
            target.relative_to(WWW)
        except ValueError:
            self.send_error(403)
            return
        if target.is_file():
            self._file(target)
            return
        self._index()


if __name__ == "__main__":
    if not INDEX.exists():
        raise SystemExit("index.html introuvable dans %s" % WWW)
    log("HomeBudget %s http://%s:%s www=%s" % (VERSION, HOST, PORT, WWW))
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
