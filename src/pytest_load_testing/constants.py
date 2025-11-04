"""Shared constants and stash keys for pytest-xdist-load-testing."""
from typing import Any

import pytest

# Stash keys for storing state
stash_key_session = pytest.StashKey[pytest.Session]()
stash_key_scheduler = pytest.StashKey[Any]()  # Type: LoadTestScheduler
stash_key_has_been_run = pytest.StashKey[bool]()

# User property key for stop signal (used by public API)
LOAD_TEST_STOP_SIGNAL = "load_test_stop"

