"""Test encrypted database module."""

import json
import os
import sys
import shutil
import unittest
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import config

DB_DIR = "/tmp/opencasa_test_db2"
MK = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLXB1cnBvc2VzLW9ubHk9"


class TestDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config["master_key"] = MK
        shutil.rmtree(DB_DIR, ignore_errors=True)
        from webui.database import init
        init(config["master_key"], DB_DIR)

    @classmethod
    def tearDownClass(cls):
        from webui.database import _conn
        if _conn:
            _conn.close()
        shutil.rmtree(DB_DIR, ignore_errors=True)

    def setUp(self):
        from webui.database import list_keys, delete
        for k in list_keys():
            delete(k)

    def test_set_and_get(self):
        from webui.database import get, set
        set("greeting", "hello world")
        self.assertEqual(get("greeting"), "hello world")

    def test_get_nonexistent(self):
        from webui.database import get
        self.assertIsNone(get("no_such_key"))

    def test_delete(self):
        from webui.database import get, set, delete
        set("temp", "value")
        self.assertEqual(get("temp"), "value")
        delete("temp")
        self.assertIsNone(get("temp"))

    def test_overwrite(self):
        from webui.database import get, set
        set("key", "v1")
        set("key", "v2")
        self.assertEqual(get("key"), "v2")

    def test_list_keys(self):
        from webui.database import get, set, delete, list_keys
        set("a:1", "x")
        set("a:2", "y")
        set("b:1", "z")
        keys = list_keys("a:")
        self.assertIn("a:1", keys)
        self.assertIn("a:2", keys)
        self.assertNotIn("b:1", keys)

    def test_list_all(self):
        from webui.database import get, set, list_keys
        set("k1", "v1")
        set("k2", "v2")
        keys = list_keys()
        self.assertIn("k1", keys)
        self.assertIn("k2", keys)

    def test_json_value(self):
        from webui.database import get, set
        data = {"nested": ["list", 42, True]}
        set("json_key", data)
        self.assertEqual(get("json_key"), json.dumps(data))

    def test_empty_string(self):
        from webui.database import get, set
        set("empty", "")
        self.assertEqual(get("empty"), "")

    def test_unicode(self):
        from webui.database import get, set
        set("unicode", "caffè àèìòù ñ ñ")
        self.assertEqual(get("unicode"), "caffè àèìòù ñ ñ")

    def test_encrypt_decrypt(self):
        from webui.database import encrypt, decrypt
        ct = encrypt("secret")
        self.assertNotEqual(ct, "secret")
        self.assertEqual(decrypt(ct), "secret")

    def test_long_value(self):
        from webui.database import get, set
        long_str = "x" * 100000
        set("long", long_str)
        self.assertEqual(get("long"), long_str)

    def test_concurrent_access(self):
        from webui.database import get, set
        errors = []
        def worker(n):
            try:
                for i in range(20):
                    set(f"concurrent:{n}:{i}", str(i))
                    get(f"concurrent:{n}:{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
