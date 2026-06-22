"""Test auth module: JWT, password hashing, user management."""

import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import config
config["auth"]["jwt_secret"] = "test-secret-32-bytes-long-for-testing"
config["auth"]["session_ttl"] = "1h"
config["master_key"] = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLXB1cnBvc2VzLW9ubHk="

from webui.auth import (
    _b64url, _b64url_decode,
    parse_ttl, make_token, verify_token,
    hash_password, verify_password,
    create_user, delete_user, list_users, user_count,
)


class TestB64Url(unittest.TestCase):
    def test_roundtrip(self):
        data = b"hello world"
        enc = _b64url(data)
        dec = _b64url_decode(enc)
        self.assertEqual(dec, data)

    def test_padding(self):
        enc = _b64url(b"test")
        self.assertNotIn("=", enc)


class TestParseTtl(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(parse_ttl("1h"), 3600)

    def test_minutes(self):
        self.assertEqual(parse_ttl("30m"), 1800)

    def test_seconds(self):
        self.assertEqual(parse_ttl("45s"), 45)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_ttl("x")


class TestJwt(unittest.TestCase):
    def test_make_and_verify(self):
        token = make_token("alice", is_root=False)
        payload = verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["username"], "alice")
        self.assertFalse(payload["is_root"])

    def test_root_token(self):
        token = make_token("root", is_root=True)
        payload = verify_token(token)
        self.assertTrue(payload["is_root"])

    def test_expired_token(self):
        old = config["auth"]["session_ttl"]
        config["auth"]["session_ttl"] = "0s"
        token = make_token("alice")
        config["auth"]["session_ttl"] = old
        time.sleep(0.01)
        payload = verify_token(token)
        self.assertIsNone(payload)

    def test_tampered_token(self):
        token = make_token("alice")
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsig"
        payload = verify_token(tampered)
        self.assertIsNone(payload)

    def test_malformed_token(self):
        self.assertIsNone(verify_token("not-a-jwt"))
        self.assertIsNone(verify_token("a.b"))
        self.assertIsNone(verify_token("a.b.c.d"))


class TestPassword(unittest.TestCase):
    def test_hash_and_verify(self):
        pw = "my-secure-password-123"
        h = hash_password(pw)
        self.assertTrue(verify_password(pw, h))
        self.assertFalse(verify_password("wrong", h))

    def test_different_salts(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        self.assertNotEqual(h1, h2)

    def test_invalid_stored(self):
        self.assertFalse(verify_password("x", "not-base64"))
        self.assertFalse(verify_password("x", ""))


class TestUserManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import shutil
        shutil.rmtree("/tmp/opencasa_test_db", ignore_errors=True)
        from webui import database as db
        db.init(config["master_key"], "/tmp/opencasa_test_db")
        cls.db = db

    @classmethod
    def tearDownClass(cls):
        from webui.database import _conn
        if _conn:
            _conn.close()
        import shutil
        shutil.rmtree("/tmp/opencasa_test_db", ignore_errors=True)

    def setUp(self):
        for u in list_users():
            delete_user(u["username"])
        self.assertEqual(user_count(), 0)

    def test_create_user(self):
        ok, msg = create_user("alice", "password123")
        self.assertTrue(ok)
        self.assertEqual(msg, "")
        self.assertEqual(user_count(), 1)

    def test_duplicate_user(self):
        create_user("bob", "pass1")
        ok, msg = create_user("bob", "pass2")
        self.assertFalse(ok)

    def test_delete_user(self):
        create_user("charlie", "secret")
        self.assertEqual(user_count(), 1)
        delete_user("charlie")
        self.assertEqual(user_count(), 0)

    def test_list_users(self):
        create_user("user1", "p1")
        create_user("user2", "p2")
        users = list_users()
        usernames = [u["username"] for u in users]
        self.assertIn("user1", usernames)
        self.assertIn("user2", usernames)

    def test_user_roles(self):
        create_user("admin_user", "pass", role="admin")
        users = list_users()
        for u in users:
            if u["username"] == "admin_user":
                self.assertEqual(u["role"], "admin")


if __name__ == "__main__":
    unittest.main()
