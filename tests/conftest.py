"""Pytest configuration and fixtures for Veltrix tests."""
import os
import tempfile
import pytest

# Create a temporary database file for tests
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()

os.environ["OUTPANEL_DB"] = _test_db.name
os.environ["OUTPANEL_ENCRYPTION_KEY"] = "test_key_for_tests_only"
os.environ["OUTPANEL_QUIET"] = "1"
os.environ["OUTPANEL_DISABLE_MONITOR"] = "1"


@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    """Initialize the test database once for the session."""
    from outpanel.db import init_db
    init_db()
    yield
    # Cleanup
    try:
        os.unlink(_test_db.name)
    except OSError:
        pass
