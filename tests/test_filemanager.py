"""Test file manager module: path validation, blocked paths, listing."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import config

from webui.filemanager import (
    _check_path,
    handle_list_files, handle_read_file, handle_write_file,
    handle_delete_file, handle_mkdir, handle_rename_file,
)

# Re-import with CONFIG_PATH set
import importlib
import webui.filemanager as fm
importlib.reload(fm)
from webui.filemanager import _is_blocked


def make_handler():
    handler = Mock()
    handler._send_error = Mock(return_value=None)
    handler._send_json = Mock(return_value=None)
    handler._is_root = False
    return handler


class TestIsBlocked(unittest.TestCase):
    def test_not_blocked_normal_file(self):
        self.assertFalse(_is_blocked("/home/user/file.txt"))

    def test_not_blocked_outside_config(self):
        self.assertFalse(_is_blocked("/tmp/test.txt"))


class TestCheckPath(unittest.TestCase):
    def setUp(self):
        config["filesystem"]["allowed_prefixes"] = ["/home", "/tmp", "/opt"]

    def test_allowed_path(self):
        handler = make_handler()
        self.assertTrue(_check_path("/home/user/file.txt", handler))

    def test_blocked_outside_prefix(self):
        handler = make_handler()
        result = _check_path("/etc/shadow", handler)
        self.assertFalse(result)

    def test_allowed_tmp(self):
        handler = make_handler()
        self.assertTrue(_check_path("/tmp/test", handler))

    def test_root_user_bypasses(self):
        handler = make_handler()
        handler._is_root = True
        self.assertTrue(_check_path("/etc/shadow", handler))


class TestFileOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        config["filesystem"]["allowed_prefixes"] = [cls.tmpdir]

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def setUp(self):
        self.handler = make_handler()

    def test_list_files(self):
        os.makedirs(os.path.join(self.tmpdir, "subdir"), exist_ok=True)
        open(os.path.join(self.tmpdir, "test.txt"), "w").close()
        handle_list_files(self.handler, self.tmpdir)
        args, _ = self.handler._send_json.call_args
        entries = args[0]["entries"]
        names = [e["name"] for e in entries]
        self.assertIn("subdir", names)
        self.assertIn("test.txt", names)

    def test_read_file(self):
        path = os.path.join(self.tmpdir, "readme.txt")
        with open(path, "w") as f:
            f.write("hello test")
        handle_read_file(self.handler, path)
        args, _ = self.handler._send_json.call_args
        self.assertEqual(args[0]["content"], "hello test")

    def test_write_file(self):
        path = os.path.join(self.tmpdir, "new.txt")
        self.handler._json_body = lambda: {"path": path, "content": "written content"}
        handle_write_file(self.handler)

    def test_mkdir(self):
        newdir = os.path.join(self.tmpdir, "newdir")
        self.handler._json_body = lambda: {"path": newdir}
        handle_mkdir(self.handler)
        self.assertTrue(os.path.isdir(newdir))

    def test_delete_file(self):
        path = os.path.join(self.tmpdir, "todelete.txt")
        open(path, "w").close()
        self.handler._json_body = lambda: {"path": path}
        handle_delete_file(self.handler)
        self.assertFalse(os.path.exists(path))

    def test_rename_file(self):
        src = os.path.join(self.tmpdir, "old.txt")
        dst = os.path.join(self.tmpdir, "new.txt")
        open(src, "w").close()
        self.handler._json_body = lambda: {"old_path": src, "new_path": dst}
        handle_rename_file(self.handler)
        self.assertFalse(os.path.exists(src))
        self.assertTrue(os.path.exists(dst))

    def test_blocked_path_returns_403(self):
        handle_read_file(self.handler, "/etc/shadow")
        self.assertTrue(self.handler._send_error.called)


if __name__ == "__main__":
    unittest.main()
