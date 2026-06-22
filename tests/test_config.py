"""Test config loading, deep_merge, and save_config."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import load_config, save_config, deep_merge, config, DEFAULT_CONFIG
import copy


class TestDeepMerge(unittest.TestCase):
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        deep_merge(base, {"b": 3})
        self.assertEqual(base["b"], 3)

    def test_nested_merge(self):
        base = {"auth": {"enabled": True, "port": 80}}
        deep_merge(base, {"auth": {"port": 443}})
        self.assertEqual(base["auth"]["enabled"], True)
        self.assertEqual(base["auth"]["port"], 443)

    def test_new_key(self):
        base = {"a": 1}
        deep_merge(base, {"b": 2})
        self.assertEqual(base["b"], 2)

    def test_deepcopy_protects_default(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        deep_merge(cfg, {"auth": {"jwt_secret": "custom"}})
        self.assertNotEqual(DEFAULT_CONFIG["auth"]["jwt_secret"], "custom")
        self.assertEqual(cfg["auth"]["jwt_secret"], "custom")


class TestLoadSaveConfig(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "opencasa.json")
        with open(self.config_path, "w") as f:
            json.dump({"server": {"port": 8080}}, f)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        global config
        config.clear()
        config.update(copy.deepcopy(DEFAULT_CONFIG))

    def test_load_config(self):
        load_config(self.config_path)
        self.assertEqual(config["server"]["port"], 8080)

    def test_save_and_reload(self):
        from webui import CONFIG_PATH as orig_path
        load_config(self.config_path)
        config["server"]["port"] = 9999
        save_config()
        with open(self.config_path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["server"]["port"], 9999)

    def test_load_nonexistent(self):
        load_config("/nonexistent/path.json")
        self.assertEqual(config["server"]["port"], DEFAULT_CONFIG["server"]["port"])


if __name__ == "__main__":
    unittest.main()
