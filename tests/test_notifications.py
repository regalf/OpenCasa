"""Test notifications module (database-backed, per-user)."""

import os
import sys
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import config

DB_DIR = "/tmp/opencasa_test_notif"
MK = "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLXB1cnBvc2VzLW9ubHk9"


class TestNotifications(unittest.TestCase):
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
        from webui.notifications import clear_notifications
        clear_notifications("testuser")

    def test_push_and_list(self):
        from webui.notifications import push_notification, get_notifications
        n = push_notification("app1", "Test Title", "Test Message", "info", "testuser")
        notifs = get_notifications("testuser")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["app_id"], "app1")
        self.assertEqual(notifs[0]["title"], "Test Title")
        self.assertEqual(notifs[0]["message"], "Test Message")
        self.assertEqual(notifs[0]["severity"], "info")
        self.assertFalse(notifs[0]["read"])

    def test_per_user_isolation(self):
        from webui.notifications import push_notification, get_notifications
        push_notification("app1", "User1 Notif", "", "info", "user1")
        push_notification("app2", "User2 Notif", "", "info", "user2")
        self.assertEqual(len(get_notifications("user1")), 1)
        self.assertEqual(len(get_notifications("user2")), 1)
        self.assertEqual(get_notifications("user1")[0]["app_id"], "app1")
        self.assertEqual(get_notifications("user2")[0]["app_id"], "app2")

    def test_id_unique(self):
        from webui.notifications import push_notification, get_notifications
        ids = set()
        for i in range(100):
            n = push_notification("test", f"n{i}", "msg", "info", "testuser")
            self.assertNotIn(n["id"], ids)
            ids.add(n["id"])

    def test_severity_default(self):
        from webui.notifications import push_notification, get_notifications
        push_notification("app", "T", "M", "info", "testuser")
        self.assertEqual(get_notifications("testuser")[0]["severity"], "info")

    def test_delete(self):
        from webui.notifications import push_notification, get_notifications, delete_notification
        n1 = push_notification("app", "First", "msg", "info", "testuser")
        push_notification("app", "Second", "msg", "info", "testuser")
        self.assertEqual(len(get_notifications("testuser")), 2)
        self.assertTrue(delete_notification(n1["id"], "testuser"))
        self.assertEqual(len(get_notifications("testuser")), 1)
        self.assertEqual(get_notifications("testuser")[0]["title"], "Second")

    def test_clear(self):
        from webui.notifications import push_notification, get_notifications, clear_notifications
        push_notification("app", "A", "", "info", "testuser")
        push_notification("app", "B", "", "info", "testuser")
        self.assertEqual(len(get_notifications("testuser")), 2)
        clear_notifications("testuser")
        self.assertEqual(len(get_notifications("testuser")), 0)

    def test_empty_username_returns_empty(self):
        from webui.notifications import get_notifications, push_notification
        self.assertEqual(get_notifications(None), [])
        self.assertEqual(get_notifications(""), [])


if __name__ == "__main__":
    unittest.main()
