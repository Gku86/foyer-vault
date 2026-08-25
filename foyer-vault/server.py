#!/usr/bin/env python3
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ.get("FOYER_DATA", "/data"))
VAULT = DATA / "vault.json"
OPTIONS = Path("/data/options.json")
HOST = os.environ.get("FOYER_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOYER_PORT", "8099"))
MAX_BODY = 5 * 1024 * 1024


def load_secret() -> str:
    env = os.environ.get("FOYER_SECRET", "")
    if env:
        return env
    if OPTIONS.exists():
        try:
            data = json.loads(OPTIONS.read_text(encoding="utf-8"))
            return str(data.get("secret") or "")
        except Exception:
            return ""
    return ""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")

    def _auth(self) -> bool:
        secret = load_secret()
        header = self.headers.get("Authorization", "")
        expected = "Bearer " + secret
        if not secret or header != expected:
            self.send_response(401)
            self._cors()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return False
        return True

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            if not self._auth():
                return
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if self.path.rstrip("/") != "/vault":
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        if not self._auth():
            return
        if not VAULT.exists():
            self.send_response(404)
            self._cors()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"empty")
            return
        payload = VAULT.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def do_PUT(self) -> None:
        if self.path.rstrip("/") != "/vault":
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        if not self._auth():
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > MAX_BODY:
            self.send_response(413)
            self._cors()
            self.end_headers()
            return
        body = self.rfile.read(length)
        try:
            json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(400)
            self._cors()
            self.end_headers()
            return
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = VAULT.with_suffix(".tmp")
        tmp.write_bytes(body)
        tmp.replace(VAULT)
        self.send_response(204)
        self._cors()
        self.end_headers()


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Foyer Vault listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
