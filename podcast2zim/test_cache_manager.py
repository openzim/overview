import os
from typing import Generator

import pytest

from cache_manager import CacheManager


@pytest.fixture
def cache() -> Generator[CacheManager, None, None]:
    """Provide a temporary database for testing."""
    test_db = "test_downloads.db"
    manager = CacheManager(db_path=test_db)
    yield manager
    manager.close()
    if os.path.exists(test_db):
        os.remove(test_db)


def test_initial_state(cache: CacheManager) -> None:
    """Test that URLs return False before being inserted."""
    assert cache.check_if_downloaded("http://example.com/audio.mp3") is False


def test_mark_and_check_downloaded(cache: CacheManager) -> None:
    """Test inserting and verifying a completed download."""
    url = "http://example.com/ep1.mp3"
    path = "/local/path/ep1.mp3"
    
    cache.mark_as_downloaded(url, path)
    assert cache.check_if_downloaded(url) is True


def test_failed_download_status(cache: CacheManager) -> None:
    """Test that a failed download does not count as completed."""
    url = "http://example.com/ep2.mp3"
    path = "/local/path/ep2.mp3"
    
    cache.mark_as_downloaded(url, path, status="failed")
    assert cache.check_if_downloaded(url) is False


def test_overwrite_status(cache: CacheManager) -> None:
    """Test that we can overwrite a failed status with a completed one."""
    url = "http://example.com/ep3.mp3"
    path = "/local/path/ep3.mp3"
    
    cache.mark_as_downloaded(url, path, status="failed")
    assert cache.check_if_downloaded(url) is False
    
    cache.mark_as_downloaded(url, path, status="completed")
    assert cache.check_if_downloaded(url) is True
