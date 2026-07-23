import pytest

from jobq.errors import ConfigError
from jobq.settings import SETTINGS_KEYS, Settings, load


def test_keys_use_deadline():
    assert "deadline_ms" in SETTINGS_KEYS
    assert "timeout_ms" not in SETTINGS_KEYS


def test_load_defaults():
    s = load()
    assert s.deadline_ms == 5000
    assert s.max_retries == 3
    assert s.batch_size == 20
    assert s.queue_name == "default"


def test_validate_rejects_nonpositive_deadline():
    s = Settings(deadline_ms=0, max_retries=1, batch_size=1, queue_name="q")
    with pytest.raises(ConfigError):
        s.validate()
