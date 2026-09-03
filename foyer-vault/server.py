#!/usr/bin/env python3
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

DATA = Path(os.environ.get("FOYER_DATA", "/data"))
VAULT = DATA / "vault.json"
VAPID = DATA / "vapid.json"
PUSHS = DATA / "push.json"
BLOBS = DATA / "blobs"
OPTIONS = Path("/data/options.json")
HOST = os.environ.get("FOYER_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOYER_PORT", "8099"))
MAX_BODY = 5 * 1024 * 1024
MAX_BLOB = 4 * 1024 * 1024
MAX_BLOBS_TOTAL = 64 * 1024 * 1024
MAX_SUBS = 50
BLOB_ID = re.compile(r"^[a-zA-Z0-9_-]{8,80}$")


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
    member_id = str(body.get("memberId") or body.get("accountId") or "").strip()
    username = str(body.get("username") or "").strip()
    device_id = str(body.get("deviceId") or "").strip()
    label = str(body.get("label") or "").strip()
    kept = []
    for item in load_subs():
        if not isinstance(item, dict):
            continue
        same_endpoint = str(item.get("endpoint") or "") == endpoint
        same_device = bool(device_id) and str(item.get("deviceId") or "") == device_id
        if same_endpoint or same_device:
            if not username:
                username = str(item.get("username") or "").strip()
            if not member_id:
                member_id = str(item.get("memberId") or item.get("accountId") or "").strip()
            if not device_id:
                device_id = str(item.get("deviceId") or "").strip()
            if not label:
                label = str(item.get("label") or "").strip()
            continue
        kept.append(item)
    row = {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
    if member_id:
        row["memberId"] = member_id
    if username:
        row["username"] = username
    if device_id:
        row["deviceId"] = device_id
    if label:
        row["label"] = label
    kept.append(row)
    save_subs(kept[-MAX_SUBS:])


def _add_account(ids: set, names: set, acc_id: str, acc_name: str) -> None:
    acc_id = (acc_id or "").strip()
    acc_name = (acc_name or "").strip().lower()
    hit = (acc_id and acc_id in ids) or (acc_name and acc_name in names)
    if acc_id and hit:
        ids.add(acc_id)
    if acc_name and hit:
        names.add(acc_name)


def _walk_vault_identities(data: dict, ids: set, names: set) -> dict:
    name_by_id = {}
    accounts = data.get("accounts") if isinstance(data, dict) else None
    if isinstance(accounts, list):
        for _ in range(3):
            for item in accounts:
                if not isinstance(item, dict):
                    continue
                acc_id = str(item.get("id") or "").strip()
                acc_name = str(item.get("username") or "").strip()
                _add_account(ids, names, acc_id, acc_name)
                if acc_id and acc_name:
                    name_by_id[acc_id] = acc_name
                for alias in item.get("aliasIds") or []:
                    alias_id = str(alias or "").strip()
                    _add_account(ids, names, alias_id, acc_name)
                    if alias_id and acc_name:
                        name_by_id[alias_id] = acc_name
    shared = data.get("shared") if isinstance(data, dict) else None
    if isinstance(shared, dict):
        for item in shared.get("pushDevices") or []:
            if not isinstance(item, dict):
                continue
            acc_id = str(item.get("accountId") or "").strip()
            acc_name = str(item.get("username") or "").strip()
            _add_account(ids, names, acc_id, acc_name)
            if acc_id and acc_name:
                name_by_id[acc_id] = acc_name
        for household in shared.get("households") or []:
            if not isinstance(household, dict):
                continue
            _add_account(ids, names, str(household.get("ownerAccountId") or ""), str(household.get("ownerUsername") or ""))
            snap = household.get("snapshot") if isinstance(household.get("snapshot"), dict) else {}
            for row in snap.get("collaborators") or []:
                if not isinstance(row, dict):
                    continue
                _add_account(ids, names, str(row.get("accountId") or ""), str(row.get("username") or ""))
        for invite in list(shared.get("householdInvites") or []) + list(shared.get("invites") or []):
            if not isinstance(invite, dict):
                continue
            _add_account(ids, names, str(invite.get("fromAccountId") or ""), str(invite.get("fromUsername") or ""))
            _add_account(ids, names, str(invite.get("toAccountId") or ""), str(invite.get("toUsername") or ""))
    return name_by_id


def vault_identities(member_id: str = "", username: str = ""):
    ids = set()
    names = set()
    if member_id:
        ids.add(member_id)
    needle = username.strip().lower()
    if needle:
        names.add(needle)
    name_by_id = {}
    if VAULT.exists():
        try:
            data = json.loads(VAULT.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                name_by_id = _walk_vault_identities(data, ids, names)
        except Exception:
            pass
    for item in load_subs():
        if not isinstance(item, dict):
            continue
        mid = str(item.get("memberId") or item.get("accountId") or "").strip()
        uname = str(item.get("username") or "").strip()
        _add_account(ids, names, mid, uname)
        if mid and uname:
            name_by_id[mid] = uname
    return ids, names, name_by_id


def vault_account_ids(member_id: str, username: str) -> set:
    ids, _names, _names_by_id = vault_identities(member_id, username)
    return ids


def repair_sub_usernames(subs: list) -> list:
    _ids, _names, name_by_id = vault_identities()
    changed = False
    for item in subs:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("memberId") or item.get("accountId") or "").strip()
        uname = str(item.get("username") or "").strip()
        if uname or not mid:
            continue
        found = name_by_id.get(mid) or ""
        if found:
            item["username"] = found
            changed = True
    if changed:
        save_subs(subs)
    return subs


def sub_matches(item: dict, ids: set, username: str, name_by_id=None) -> bool:
    mid = str(item.get("memberId") or item.get("accountId") or "").strip()
    if mid and mid in ids:
        return True
    uname = str(item.get("username") or "").strip().lower()
    needle = username.strip().lower()
    if needle and uname and uname == needle:
        return True
    if needle and mid and isinstance(name_by_id, dict):
        mapped = str(name_by_id.get(mid) or "").strip().lower()
        if mapped == needle:
            return True
    return False


def subscriber_index() -> tuple:
    by_member: dict = {}
    by_user: dict = {}
    devices = []
    seen = set()
    for item in repair_sub_usernames(load_subs()):
        if not isinstance(item, dict):
            continue
        mid = str(item.get("memberId") or item.get("accountId") or "").strip()
        uname = str(item.get("username") or "").strip()
        label = str(item.get("label") or "").strip()
        device_id = str(item.get("deviceId") or "").strip()
        if mid:
            by_member[mid] = int(by_member.get(mid) or 0) + 1
        if uname:
            key = uname.lower()
            by_user[key] = int(by_user.get(key) or 0) + 1
        fingerprint = device_id or str(item.get("endpoint") or "")[:24]
        if fingerprint and fingerprint not in seen:
            seen.add(fingerprint)
            devices.append({"username": uname, "label": label or "appareil", "memberId": mid, "deviceId": device_id})
    return by_member, by_user, devices


def send_push(title: str, body: str, url: str, exclude: str, member_id: str, username: str = "", member_ids=None) -> dict:
    extra = [str(item).strip() for item in (member_ids or []) if str(item).strip()]
    if not member_id and not username and not extra:
        return {"ok": False, "error": "Destinataire manquant.", "sent": 0}
    try:
        from pywebpush import webpush  # noqa: F401
    except Exception:
        return {"ok": False, "error": "pywebpush manquant sur le module", "sent": 0}
    vapid = ensure_vapid()
    payload = json.dumps({"title": title, "body": body, "url": url or "/"}, ensure_ascii=False)
    ids, _names, name_by_id = vault_identities(member_id, username)
    for item in extra:
        ids.add(item)
    sent = 0
    gone = []
    last_error = ""
    matched = 0
    for item in repair_sub_usernames(load_subs()):
        if not isinstance(item, dict):
            continue
        endpoint = str(item.get("endpoint") or "")
        if not endpoint:
            continue
        if exclude and endpoint == exclude:
            continue
        if not sub_matches(item, ids, username, name_by_id):
            continue
        matched += 1
        keys = item.get("keys") if isinstance(item.get("keys"), dict) else {}
        try:
            deliver_webpush({"endpoint": endpoint, "keys": keys}, payload, vapid)
            sent += 1
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            last_error = str(exc)[:180]
            if status in (404, 410):
                gone.append(endpoint)
            sys.stdout.write("push fail %s %s\n" % (endpoint[:48], exc))
            sys.stdout.flush()
    if gone:
        keep = [item for item in load_subs() if not (isinstance(item, dict) and item.get("endpoint") in gone)]
        save_subs(keep)
    if sent < 1 and last_error:
        return {
            "ok": False,
            "sent": 0,
            "error": "Le service de notifications a refusé l’envoi. Réactivez les notifications sur l’appareil, puis renvoyez.",
        }
    if sent < 1 and matched == 0:
        return {"ok": True, "sent": 0}
    return {"ok": True, "sent": sent}


def drop_sub(endpoint: str) -> None:
    endpoint = endpoint.strip()
    if not endpoint:
        return
    save_subs([item for item in load_subs() if not (isinstance(item, dict) and item.get("endpoint") == endpoint)])


def deliver_webpush(subscription_info: dict, payload: str, vapid: dict) -> None:
    from pywebpush import webpush

    claims = {"sub": "mailto:homebudget@users.noreply.github.com"}
    base = {
        "subscription_info": subscription_info,
        "data": payload,
        "vapid_private_key": vapid["private_pem"],
        "vapid_claims": claims,
        "content_encoding": "aes128gcm",
    }
    try:
        webpush(ttl=86400, timeout=15, headers={"Urgency": "high"}, **base)
        return
    except TypeError:
        pass
    try:
        webpush(ttl=86400, timeout=15, **base)
        return
    except TypeError:
        pass
    webpush(**{k: v for k, v in base.items() if k != "content_encoding"}, ttl=86400)


def blob_path(blob_id: str) -> Optional[Path]:
    if not BLOB_ID.match(blob_id):
        return None
    BLOBS.mkdir(parents=True, exist_ok=True)
    return BLOBS / (blob_id + ".bin")


def blob_listing() -> dict:
    BLOBS.mkdir(parents=True, exist_ok=True)
    files = []
    total = 0
    for path in sorted(BLOBS.glob("*.bin")):
        size = path.stat().st_size
        total += size
        files.append({"id": path.stem, "bytes": size})
    return {"files": files, "totalBytes": total, "maxBytes": MAX_BLOBS_TOTAL, "maxFileBytes": MAX_BLOB}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS")

    def _route(self) -> str:
        return unquote(urlparse(self.path).path).rstrip("/") or "/"

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

    def _read_bytes(self, limit: int):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > limit:
            return None
        return self.rfile.read(length)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = self._route()
        if path == "/health":
            if not self._auth():
                return
            stats = blob_listing()
            self._json(200, {"ok": True, "blobs": {"count": len(stats["files"]), "bytes": stats["totalBytes"]}})
            return
        if path == "/push/key":
            if not self._auth():
                return
            try:
                vapid = ensure_vapid()
                by_member, by_user, devices = subscriber_index()
                self._json(
                    200,
                    {
                        "publicKey": vapid["public"],
                        "subscribers": len(load_subs()),
                        "byMember": by_member,
                        "byUser": by_user,
                        "devices": devices,
                    },
                )
            except Exception as exc:
                self._json(500, {"error": str(exc)})
            return
        if path == "/blobs":
            if not self._auth():
                return
            self._json(200, blob_listing())
            return
        if path.startswith("/blobs/"):
            if not self._auth():
                return
            target = blob_path(path.split("/", 2)[-1])
            if target is None:
                self._json(400, {"error": "id invalide"})
                return
            if not target.exists():
                self.send_response(404)
                self._cors()
                self.end_headers()
                return
            data = target.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
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
        path = self._route()
        if path.startswith("/blobs/"):
            if not self._auth():
                return
            blob_id = path.split("/", 2)[-1]
            target = blob_path(blob_id)
            if target is None:
                self._json(400, {"error": "id invalide"})
                return
            body = self._read_bytes(MAX_BLOB)
            if body is None:
                self.send_response(413)
                self._cors()
                self.end_headers()
                return
            stats = blob_listing()
            existing = target.stat().st_size if target.exists() else 0
            if stats["totalBytes"] - existing + len(body) > MAX_BLOBS_TOTAL:
                self.send_response(413)
                self._cors()
                self.end_headers()
                return
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(body)
            tmp.replace(target)
            self.send_response(204)
            self._cors()
            self.end_headers()
            return
        if path != "/vault":
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

    def do_DELETE(self) -> None:
        path = self._route()
        if not path.startswith("/blobs/"):
            self.send_response(404)
            self._cors()
            self.end_headers()
            return
        if not self._auth():
            return
        target = blob_path(path.split("/", 2)[-1])
        if target is None:
            self._json(400, {"error": "id invalide"})
            return
        if target.exists():
            target.unlink()
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self) -> None:
        path = self._route()
        if path == "/blobs/gc":
            if not self._auth():
                return
            body = self._read_json()
            if body is None or body is False or not isinstance(body, dict):
                self._json(400, {"error": "JSON invalide"})
                return
            keep_raw = body.get("keep")
            keep = set()
            if isinstance(keep_raw, list):
                for item in keep_raw:
                    if isinstance(item, str) and BLOB_ID.match(item):
                        keep.add(item)
            deleted = 0
            BLOBS.mkdir(parents=True, exist_ok=True)
            for file in list(BLOBS.glob("*.bin")):
                if file.stem not in keep:
                    file.unlink()
                    deleted += 1
            self._json(200, {"ok": True, "deleted": deleted})
            return
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
        member_id = str(body.get("memberId") or body.get("accountId") or "").strip()
        username = str(body.get("username") or "").strip()
        raw_ids = body.get("memberIds")
        member_ids = []
        if isinstance(raw_ids, list):
            for item in raw_ids:
                value = str(item or "").strip()
                if value:
                    member_ids.append(value)
        result = send_push(title, text, url, exclude, member_id, username, member_ids)
        self._json(200 if result.get("ok") else 501, result)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    BLOBS.mkdir(parents=True, exist_ok=True)
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
