"""Pytest configuration and fixtures for Veltrix tests."""
import os
import sys
import tempfile

# Create a temporary database file for tests BEFORE any imports
_test_db_path = os.path.join(tempfile.gettempdir(), "veltrix_test.db")

os.environ["OUTPANEL_DB"] = _test_db_path
os.environ["OUTPANEL_ENCRYPTION_KEY"] = "test_key_for_tests_only"
os.environ["OUTPANEL_QUIET"] = "1"
os.environ["OUTPANEL_DISABLE_MONITOR"] = "1"
os.environ["OUTPANEL_LOG_FILE"] = ""

# Now import and initialize
from outpanel.db import init_db
init_db()
