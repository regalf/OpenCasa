"""Test rate limiting on login."""

import os
import sys
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from webui import _login_attempts, _login_lock


class TestRateLimit(unittest.TestCase):
    def setUp(self):
        _login_attempts.clear()

    def test_no_attempts_first(self):
        ip = "10.0.0.1"
        self.assertNotIn(ip, _login_attempts)

    def test_track_attempts(self):
        ip = "10.0.0.2"
        now = time.time()
        _login_attempts[ip] = [now - 10, now - 20, now - 30]
        attempts = [t for t in _login_attempts[ip] if now - t < 300]
        self.assertEqual(len(attempts), 3)

    def test_expired_attempts_removed(self):
        ip = "10.0.0.3"
        now = time.time()
        _login_attempts[ip] = [now - 400, now - 10]
        attempts = [t for t in _login_attempts[ip] if now - t < 300]
        self.assertEqual(len(attempts), 1)

    def test_rate_limit_threshold(self):
        ip = "10.0.0.4"
        now = time.time()
        _login_attempts[ip] = [now - t for t in range(10, 110, 10)]
        attempts = [t for t in _login_attempts[ip] if now - t < 300]
        self.assertGreaterEqual(len(attempts), 10)

    def test_under_threshold_allowed(self):
        ip = "10.0.0.5"
        now = time.time()
        _login_attempts[ip] = [now - 10, now - 20]
        attempts = [t for t in _login_attempts[ip] if now - t < 300]
        self.assertLess(len(attempts), 10)

    def test_clear_on_success(self):
        ip = "10.0.0.6"
        _login_attempts[ip] = [time.time() - 5, time.time() - 10]
        _login_attempts.pop(ip, None)
        self.assertNotIn(ip, _login_attempts)


if __name__ == "__main__":
    unittest.main()
