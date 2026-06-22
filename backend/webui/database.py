"""
Encrypted key-value store for user preferences.

Uses SQLite with per-value HMAC-CTR encryption.
PBKDF2 key derivation runs once on init; subsequent encrypt/decrypt
uses fast HMAC-SHA256 keystream generation.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading

log = logging.getLogger(__name__)

_enc_key = None
_mac_key = None
_conn = None
_lock = threading.Lock()
_init_complete = False


def init(master_key_b64, db_dir):
    global _enc_key, _mac_key, _conn, _init_complete

    with _lock:
        master_key = base64.b64decode(master_key_b64)
        salt = b"OpenCasa-DB-v1"
        derived = hashlib.pbkdf2_hmac("sha256", master_key, salt, 10000, dklen=64)
        _enc_key = derived[:32]
        _mac_key = derived[32:]

        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "opencasa.db")
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("""CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            mac TEXT NOT NULL
        )""")
        _conn.execute("""CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""")
        _conn.commit()

        cur = _conn.execute("SELECT value FROM meta WHERE key=?", ("verification",))
        row = cur.fetchone()
        if row:
            try:
                decrypt(row[0])
                log.debug("database integrity verified")
            except Exception:
                log.warning("master key mismatch — regenerating database")
                _conn.close()
                _conn = None
                os.remove(db_path)
                _conn = sqlite3.connect(db_path, check_same_thread=False)
                _conn.execute("PRAGMA journal_mode=WAL")
                _conn.execute("""CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    mac TEXT NOT NULL
                )""")
                _conn.execute("""CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )""")
                _conn.commit()

        token = encrypt("OpenCasa-DB-OK")
        _conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("verification", token))
        _conn.commit()
        _init_complete = True
    log.info("database ready at %s", db_path)


def _derive_keystream(nonce, length):
    key = b""
    c = 0
    while len(key) < length:
        key += hmac.new(_enc_key, nonce + c.to_bytes(4, "big"), "sha256").digest()
        c += 1
    return key[:length]


def encrypt(plaintext):
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    nonce = os.urandom(8)
    ks = _derive_keystream(nonce, len(plaintext))
    ct = bytes(a ^ b for a, b in zip(plaintext, ks))
    return base64.b64encode(nonce + ct).decode()


def decrypt(encoded):
    raw = base64.b64decode(encoded)
    nonce, ct = raw[:8], raw[8:]
    ks = _derive_keystream(nonce, len(ct))
    pt = bytes(a ^ b for a, b in zip(ct, ks))
    return pt.decode("utf-8")


def _mac(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hmac.new(_mac_key, data, "sha256").hexdigest()


def _ready():
    return _conn is not None and _init_complete


def get(key):
    if not _ready():
        return None
    with _lock:
        cur = _conn.execute("SELECT value, mac FROM kv WHERE key=?", (key,))
        row = cur.fetchone()
        if not row:
            return None
        enc_val, stored_mac = row
        if not hmac.compare_digest(_mac(enc_val), stored_mac):
            log.warning("integrity check failed for key: %s", key)
            return None
        return decrypt(enc_val)


def set(key, value):
    if not _ready():
        return
    if not isinstance(value, str):
        value = json.dumps(value)
    enc_val = encrypt(value)
    m = _mac(enc_val)
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO kv VALUES (?, ?, ?)", (key, enc_val, m))
        _conn.commit()


def delete(key):
    if not _ready():
        return
    with _lock:
        _conn.execute("DELETE FROM kv WHERE key=?", (key,))
        _conn.commit()


def list_keys(prefix=""):
    if not _ready():
        return []
    with _lock:
        if prefix:
            cur = _conn.execute("SELECT key FROM kv WHERE key LIKE ?", (prefix + "%",))
        else:
            cur = _conn.execute("SELECT key FROM kv")
        return [row[0] for row in cur.fetchall()]
