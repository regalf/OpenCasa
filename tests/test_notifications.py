"""Test notifications module."""

import os
import sys
import json
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

NOTIF_FILE = os.path.join(tempfile.mkdtemp(), "notifications.json")

import webui.notifications as notif_mod
notif_mod.NOTIF_FILE = NOTIF_FILE


class TestNotifications(unittest.TestCase):
    def setUp(self):
        notif_mod.notifications = []
        if os.path.exists(NOTIF_FILE):
            os.remove(NOTIF_FILE)

    def test_push_and_list(self):
        notif_mod.push_notification("app1", "Test Title", "Test Message", "info")
        self.assertEqual(len(notif_mod.notifications), 1)
        n = notif_mod.notifications[0]
        self.assertEqual(n["app_id"], "app1")
        self.assertEqual(n["title"], "Test Title")
        self.assertEqual(n["message"], "Test Message")
        self.assertEqual(n["severity"], "info")
        self.assertFalse(n["read"])

    def test_persistence(self):
        notif_mod.push_notification("app2", "Title", "Msg")
        notif_mod.save_notifications()
        notif_mod.notifications = []
        notif_mod.load_notifications()
        self.assertEqual(len(notif_mod.notifications), 1)
        self.assertEqual(notif_mod.notifications[0]["app_id"], "app2")

    def test_id_unique(self):
        ids = set()
        for i in range(100):
            notif_mod.push_notification("test", f"n{i}", "msg")
            nid = notif_mod.notifications[-1]["id"]
            self.assertNotIn(nid, ids)
            ids.add(nid)

    def test_severity_default(self):
        notif_mod.push_notification("app", "T", "M")
        self.assertEqual(notif_mod.notifications[0]["severity"], "info")


if __name__ == "__main__":
    unittest.main()
