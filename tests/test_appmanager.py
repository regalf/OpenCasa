"""Test appmanager module — permissions, app scanning, pledge computation."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import config

DB_DIR = "/tmp/opencasa_test_appmgr"
MK = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLXB1cnBvc2VzLW9ubHk9"


class TestSafeId(unittest.TestCase):
    def test_valid_ids(self):
        from webui.appmanager import _safe_id
        self.assertTrue(_safe_id("my-app"))
        self.assertTrue(_safe_id("hello_world"))
        self.assertTrue(_safe_id("test123"))
        self.assertTrue(_safe_id("a"))

    def test_invalid_ids(self):
        from webui.appmanager import _safe_id
        self.assertFalse(_safe_id("My App"))
        self.assertFalse(_safe_id("app/foo"))
        self.assertFalse(_safe_id("a.b"))
        self.assertFalse(_safe_id(""))


class TestPledgePromises(unittest.TestCase):
    def test_no_permissions(self):
        from webui.appmanager import _compute_pledge_promises
        self.assertEqual(_compute_pledge_promises([]), "stdio rpath")

    def test_network_client(self):
        from webui.appmanager import _compute_pledge_promises
        self.assertEqual(_compute_pledge_promises(["network:client"]),
                         "stdio rpath inet dns")

    def test_network_server(self):
        from webui.appmanager import _compute_pledge_promises
        self.assertEqual(_compute_pledge_promises(["network:server"]),
                         "stdio rpath inet")

    def test_network_client_and_server(self):
        from webui.appmanager import _compute_pledge_promises
        result = _compute_pledge_promises(["network:client", "network:server"])
        self.assertIn("inet", result)
        self.assertIn("dns", result)
        self.assertNotIn("proc", result)

    def test_system_exec(self):
        from webui.appmanager import _compute_pledge_promises
        result = _compute_pledge_promises(["system:exec"])
        self.assertEqual(result, "stdio rpath proc exec")

    def test_files_write_adds_wpath_cpath(self):
        from webui.appmanager import _compute_pledge_promises
        result = _compute_pledge_promises(["files:write"])
        self.assertIn("wpath", result)
        self.assertIn("cpath", result)

    def test_all_permissions(self):
        from webui.appmanager import _compute_pledge_promises
        perms = ["network:client", "network:server", "files:write", "system:exec"]
        result = _compute_pledge_promises(perms)
        for p in ["stdio", "rpath", "inet", "dns", "proc", "exec", "wpath", "cpath"]:
            self.assertIn(p, result)

    def test_network_client_implies_inet(self):
        from webui.appmanager import _compute_pledge_promises
        r1 = _compute_pledge_promises(["network:client"])
        r2 = _compute_pledge_promises(["network:client", "network:client"])
        self.assertEqual(r1, r2)


class TestNeedsNetwork(unittest.TestCase):
    def test_needs_client(self):
        from webui.appmanager import _needs_network
        self.assertTrue(_needs_network(["network:client"]))

    def test_needs_server(self):
        from webui.appmanager import _needs_network
        self.assertTrue(_needs_network(["network:server"]))

    def test_no_network(self):
        from webui.appmanager import _needs_network
        self.assertFalse(_needs_network([]))
        self.assertFalse(_needs_network(["files:read"]))
        self.assertFalse(_needs_network(["system:exec"]))


class TestPermKey(unittest.TestCase):
    def test_with_username(self):
        from webui.appmanager import _perm_key
        self.assertEqual(_perm_key("myapp", "admin"),
                         "_app_perm_state:admin:myapp")

    def test_without_username(self):
        from webui.appmanager import _perm_key
        self.assertEqual(_perm_key("myapp"),
                         "_app_perm_state:myapp")
        self.assertEqual(_perm_key("myapp", None),
                         "_app_perm_state:myapp")


class TestPermissionState(unittest.TestCase):
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

    def test_set_and_get_perm_state(self):
        from webui.appmanager import _set_perm_state, _get_perm_state
        _set_perm_state("testapp", "admin", {"network:server": True})
        state = _get_perm_state("testapp", "admin")
        self.assertEqual(state, {"network:server": True})

    def test_get_nonexistent_returns_empty(self):
        from webui.appmanager import _get_perm_state
        self.assertEqual(_get_perm_state("nonexistent", "admin"), {})

    def test_confirm_and_get_state(self):
        from webui.appmanager import confirm_app, _get_perm_state
        confirm_app("testapp", ["network:server", "files:write"], username="admin")
        state = _get_perm_state("testapp", "admin")
        self.assertEqual(state, {"network:server": True, "files:write": True})

    def test_confirm_without_username(self):
        from webui.appmanager import confirm_app, get_permission_state
        confirm_app("testapp", ["system:monitor"], username=None)
        state = get_permission_state("testapp", None)
        self.assertEqual(state, {})

    def test_set_app_permission_toggle_off(self):
        from webui.appmanager import confirm_app, set_app_permission, _get_perm_state
        confirm_app("testapp", ["network:server", "files:write"], username="admin")
        set_app_permission("testapp", "files:write", False, username="admin")
        state = _get_perm_state("testapp", "admin")
        self.assertEqual(state, {"network:server": True, "files:write": False})

    def test_set_app_permission_without_username(self):
        from webui.appmanager import set_app_permission, _get_perm_state
        self.assertTrue(set_app_permission("testapp", "files:read", False, username=None))
        state = _get_perm_state("testapp", None)
        self.assertEqual(state, {"files:read": False})

    def test_get_granted_permissions(self):
        from webui.appmanager import confirm_app, set_app_permission, _get_granted_permissions
        confirm_app("testapp", ["network:server", "files:write"], username="admin")
        granted = _get_granted_permissions("testapp", "admin")
        self.assertEqual(set(granted), {"network:server", "files:write"})
        set_app_permission("testapp", "files:write", False, username="admin")
        granted = _get_granted_permissions("testapp", "admin")
        self.assertEqual(granted, ["network:server"])

    def test_get_granted_no_state_falls_to_manifest(self):
        from webui.appmanager import _get_granted_permissions
        self.assertEqual(_get_granted_permissions("nonexistent"), [])

    def test_is_app_confirmed_no_permissions(self):
        from webui.appmanager import is_app_confirmed
        self.assertTrue(is_app_confirmed("testapp", [], "admin"))

    def test_is_app_confirmed_unconfirmed_returns_false(self):
        from webui.appmanager import is_app_confirmed
        self.assertFalse(is_app_confirmed("testapp", ["network:server"], "admin"))

    def test_is_app_confirmed_after_confirm(self):
        from webui.appmanager import confirm_app, is_app_confirmed
        confirm_app("testapp", ["network:server"], username="admin")
        self.assertTrue(is_app_confirmed("testapp", ["network:server"], "admin"))

    def test_is_app_confirmed_migration_from_legacy(self):
        from webui.database import set as db_set
        from webui.appmanager import is_app_confirmed
        legacy = json.dumps({"permissions": ["network:server", "files:write"]})
        db_set("_app_confirm:legacy-app", legacy)
        self.assertTrue(
            is_app_confirmed("legacy-app", ["network:server", "files:write"], "admin")
        )


class TestAlive(unittest.TestCase):
    def test_alive_own_pid(self):
        from webui.appmanager import _alive
        self.assertTrue(_alive(os.getpid()))

    def test_dead_pid(self):
        from webui.appmanager import _alive
        self.assertFalse(_alive(999999999))


class TestScanApps(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="opencasa_test_apps_")
        config["apps_dir"] = self.tmpdir
        from webui.appmanager import APPS_DIR
        self._orig_apps_dir = APPS_DIR
        import webui.appmanager as am
        am.APPS_DIR = self.tmpdir
        am._cache = []
        am._cache_ts = 0.0

    def tearDown(self):
        import webui.appmanager as am
        am.APPS_DIR = self._orig_apps_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_manifest(self, app_id, overrides=None):
        app_dir = os.path.join(self.tmpdir, app_id)
        os.makedirs(app_dir, exist_ok=True)
        manifest = {
            "name": app_id.title(),
            "description": f"{app_id} description",
            "version": "1.0",
            "entry": "app.py",
            "type": "tool",
            "permissions": [],
        }
        if overrides:
            manifest.update(overrides)
        with open(os.path.join(app_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f)
        with open(os.path.join(app_dir, "app.py"), "w") as f:
            f.write("#!/usr/bin/env python3\nprint('hello')")
        return app_dir

    def test_scan_returns_apps(self):
        from webui.appmanager import scan_all, get_app
        self._write_manifest("hello")
        apps = scan_all()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["id"], "hello")
        self.assertEqual(apps[0]["name"], "Hello")

    def test_scan_skips_no_manifest(self):
        from webui.appmanager import scan_all
        d = os.path.join(self.tmpdir, "no-manifest")
        os.makedirs(d)
        apps = scan_all()
        self.assertEqual(len(apps), 0)

    def test_scan_skips_invalid_id(self):
        from webui.appmanager import scan_all
        self._write_manifest("has space")
        apps = scan_all()
        self.assertEqual(len(apps), 0)

    def test_get_app_returns_copy(self):
        from webui.appmanager import scan_all, get_app
        self._write_manifest("myapp")
        scan_all()
        a1 = get_app("myapp")
        a2 = get_app("myapp")
        self.assertEqual(a1, a2)
        self.assertIsNot(a1, a2)

    def test_get_app_nonexistent(self):
        from webui.appmanager import get_app
        self.assertIsNone(get_app("nonexistent"))

    def test_icon_path(self):
        from webui.appmanager import icon_path, scan_all
        d = self._write_manifest("withicon", {"icon": "icon.svg"})
        svg = os.path.join(d, "icon.svg")
        with open(svg, "w") as f:
            f.write("<svg></svg>")
        scan_all()
        self.assertEqual(icon_path("withicon"), svg)

    def test_icon_path_nonexistent(self):
        from webui.appmanager import icon_path
        self.assertIsNone(icon_path("noicon"))

    def test_scan_cache_ttl(self):
        from webui.appmanager import scan_all
        self._write_manifest("app1")
        r1 = scan_all()
        self._write_manifest("app2")
        r2 = scan_all()
        self.assertEqual(len(r1), 1)

    def test_parse_manifest_fields(self):
        from webui.appmanager import scan_all, get_app
        self._write_manifest("webapp", {
            "author": "Test Author",
            "port": 19000,
            "type": "web",
            "autostart": True,
            "permissions": ["network:server"],
            "has_widget": True,
            "open_in": "tab",
        })
        scan_all()
        app = get_app("webapp")
        self.assertEqual(app["author"], "Test Author")
        self.assertEqual(app["port"], 19000)
        self.assertEqual(app["type"], "web")
        self.assertTrue(app["autostart"])
        self.assertEqual(app["permissions"], ["network:server"])
        self.assertTrue(app["has_widget"])
        self.assertEqual(app["open_in"], "tab")


class TestListApps(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="opencasa_test_list_")
        config["apps_dir"] = self.tmpdir
        import webui.appmanager as am
        self._orig_apps_dir = am.APPS_DIR
        am.APPS_DIR = self.tmpdir
        am._cache = []
        am._cache_ts = 0.0

    def tearDown(self):
        import webui.appmanager as am
        am.APPS_DIR = self._orig_apps_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_apps_structure(self):
        from webui.appmanager import list_apps, APP_USER
        import webui.appmanager as am
        am.APP_USER = config.get('app_user', 'opencasa')
        result = list_apps()
        self.assertIn("apps", result)
        self.assertIn("app_user_ready", result)
        self.assertIn("port_pool", result)
        self.assertIn("used_ports", result)


if __name__ == "__main__":
    unittest.main()
