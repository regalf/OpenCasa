#!/usr/bin/env python3
"""Run all OpenCasa tests."""
import sys
import unittest

if __name__ == "__main__":
    suite = unittest.TestLoader().discover(".", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
