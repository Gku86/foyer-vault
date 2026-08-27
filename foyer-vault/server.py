#!/usr/bin/env python3
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ.get("FOYER_DATA", "/data"))
VAULT = DATA / "vault.json"
VAPID = DATA / "vapid.json"
PUSHS = DATA / "push.json"
OPTIONS = Path("/data/options.json")
HOST = os.environ.get("FOYER_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOYER_PORT", "8099"))
MAX_BODY = 5 * 1024 * 1024
MAX_SUBS = 50


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


def b64url(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def ensure_vapid() -> dict:
    if VAPID.exists():
        try:
            data = json.loads(VAPID.read_text(encoding="utf-8"))
            if data.get("public") and data.get("private_pem"):
                return data
        except Exception:
            pass
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    data = {"private_pem": private_pem, "public": b64url(public)}
    DATA.mkdir(parents=True, exist_ok=True)
    VAPID.write_text(json.dumps(data), encoding="utf-8")
    return data


def load_subs() -> list:
    if not PUSHS.exists():
        return []
    try:
        data = json.loads(PUSHS.read_text(encoding="utf-8"))
        subs = data.get("subscriptions")
        return subs if isinstance(subs, list) else []
    except Exception:
        return []


def save_subs(subs: list) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = PUSHS.with_suffix(".tmp")
    tmp.write_text(json.dumps({"subscriptions": subs}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PUSHS)


def upsert_sub(body: dict) -> None:
    endpoint = str(body.get("endpoint") or "").strip()
    keys = body.get("keys") if isinstance(body.get("keys"), dict) else {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        raise ValueError("subscription incomplete")
    member_id = str(body.get("memberId") or "").strip()
    row = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
    if member_id:
        row["memberId"] = member_id
    subs = [item for item in load_subs() if isinstance(item, dict) and item.get("endpoint") != endpoint]
    subs.append(row)
    save_subs(subs[-MAX_SUBS:])


def drop_sub(endpoint: str) -> None:
    endpoint = endpoint.strip()
    if not endpoint:
        return
    save_subs([item for item in load_subs() if not (isinstance(item, dict) and item.get("endpoint") == endpoint)])


def send_push(title: str, body: str, url: str, exclude: str, member_id: str) -> dict:
    try:
        from pywebpush import webpush
    except Exception:
        return {"ok": False, "error": "pywebpush manquant sur le module", "sent": 0}
    vapid = ensure_vapid()
    payload = json.dumps({"title": title, "body": body, "url": url or "/"}, ensure_ascii=False)
    sent = 0
    gone = []
    for item in load_subs():
        if not isinstance(item, dict):
            continue
        endpoint = str(item.get("endpoint") or "")
        if not endpoint or endpoint == exclude:
            continue
        if member_id and str(item.get("memberId") or "") != member_id:
            continue
        keys = item.get("keys") if isinstance(item.get("keys"), dict) else {}
        try:
            webpush(
                subscription_info={"endpoint": endpoint, "keys": keys},
                data=payload,
                vapid_private_key=vapid["private_pem"],
                vapid_claims={"sub": "mailto:homebudget@local"},
            )
            sent += 1
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410) or (hasattr(exc, "__class__") and exc.__class__.__name__ == "WebPushException" and status in (404, 410)):
                gone.append(endpoint)
            sys.stdout.write("push fail %s %s\n" % (endpoint[:48], exc))
            sys.stdout.flush()
    if gone:
        keep = [item for item in load_subs() if not (isinstance(item, dict) and item.get("endpoint") in gone)]
        save_subs(keep)
    return {"ok": True, "sent": sent}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS")

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

    def _json(self, code: int, payload) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return False

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.rstrip("/") or "/"
        if path == "/health":
            if not self._auth():
                return
            self._json(200, {"ok": True})
            return
        if path == "/push/key":
            if not self._auth():
                return
            try:
                vapid = ensure_vapid()
                self._json(200, {"publicKey": vapid["public"], "subscribers": len(load_subs())})
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return
        if path != "/vault":
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

    def do_POST(self) -> None:
        path = self.path.rstrip("/") or "/"
        if path not in ("/push/subscribe", "/push/unsubscribe", "/push/send"):
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        if not self._auth():
            return
        body = self._read_json()
        if body is None or body is False or not isinstance(body, dict):
            self._json(400, {"error": "JSON invalide"})
            return
        if path == "/push/subscribe":
            try:
                upsert_sub(body)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(200, {"ok": True, "subscribers": len(load_subs())})
            return
        if path == "/push/unsubscribe":
            drop_sub(str(body.get("endpoint") or ""))
            self._json(200, {"ok": True, "subscribers": len(load_subs())})
            return
        title = str(body.get("title") or "HomeBudget").strip()[:80]
        text = str(body.get("body") or "").strip()[:240]
        url = str(body.get("url") or "/").strip() or "/"
        exclude = str(body.get("excludeEndpoint") or "")
        member_id = str(body.get("memberId") or "").strip()
        result = send_push(title, text, url, exclude, member_id)
        self._json(200 if result.get("ok") else 501, result)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    try:
        ensure_vapid()
    except Exception as exc:
        sys.stdout.write("vapid init skipped: %s\n" % exc)
        sys.stdout.flush()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Foyer Vault listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
