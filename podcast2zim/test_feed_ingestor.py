import unittest.mock
from unittest.mock import MagicMock, AsyncMock

import aiohttp
import pytest
from feed_ingestor import FeedIngestor

def test_sanitize_filename() -> None:
    """
    Test filename sanitization logic.
    """
    ingestor = FeedIngestor()
    assert ingestor.sanitize_filename("Valid Name 123") == "Valid Name 123"
    assert ingestor.sanitize_filename("Questionable? *name*") == "Questionable name"
    assert ingestor.sanitize_filename("Multi   Space") == "Multi Space"
    assert ingestor.sanitize_filename("path/traversal:name") == "pathtraversalname"
    
    # Test length truncation
    long_name = "A" * 250
    assert len(ingestor.sanitize_filename(long_name)) == 200

def test_parse_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test parsing logic with a mocked RSS feed.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Monkeypatch fixture for mocking dependencies.
    """
    mock_feed = MagicMock()
    mock_feed.feed = {"title": "Test Podcast"}
    mock_feed.entries = [
        {
            "title": "Episode 1",
            "enclosures": [{"type": "audio/mpeg", "href": "http://example.com/ep1.mp3"}]
        },
        {
            "title": "Episode 2",
            "enclosures": [{"type": "audio/mpeg", "href": "http://example.com/ep2.mp3"}]
        }
    ]

    import feedparser
    monkeypatch.setattr(feedparser, "parse", lambda url: mock_feed)

    ingestor = FeedIngestor()
    result = ingestor.parse_feed("http://fakeurl.com/rss")

    assert result["podcast_title"] == "Test Podcast"
    assert len(result["episodes"]) == 2
    assert result["episodes"][0]["title"] == "Episode 1"
    assert result["episodes"][1]["media_url"] == "http://example.com/ep2.mp3"

@pytest.mark.asyncio
async def test_download_episode_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test successful download of an episode using chunked iteration.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Monkeypatch fixture for mocking dependencies.
    """
    mock_response = AsyncMock()
    mock_response.status = 200
    
    # Mock async generator for iter_chunked
    async def mock_iter_chunked(*args, **kwargs):
        yield b"chunk1"
        yield b"chunk2"

    mock_response.content.iter_chunked = mock_iter_chunked
    mock_response.__aenter__.return_value = mock_response

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get.return_value = mock_response

    mock_file = MagicMock()
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: mock_file)
    mock_file.__enter__.return_value = mock_file

    ingestor = FeedIngestor()
    success = await ingestor.download_episode(
        mock_session, 
        "http://example.com/ep1.mp3", 
        "dummy_path.mp3"
    )

    assert success is True
    assert mock_file.write.call_count == 2
    mock_file.write.assert_any_call(b"chunk1")
    mock_file.write.assert_any_call(b"chunk2")

@pytest.mark.asyncio
async def test_download_episode_retry_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test retry logic on HTTP 500 status.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Monkeypatch fixture for mocking dependencies.
    """
    mock_500_response = AsyncMock()
    mock_500_response.status = 500
    mock_500_response.__aenter__.return_value = mock_500_response

    mock_200_response = AsyncMock()
    mock_200_response.status = 200
    
    # Mock chunks
    async def mock_iter_chunked(*args, **kwargs):
        yield b"test_chunk"
    mock_200_response.content.iter_chunked = mock_iter_chunked
    mock_200_response.__aenter__.return_value = mock_200_response

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.get.side_effect = [mock_500_response, mock_200_response]

    monkeypatch.setattr("builtins.open", MagicMock())
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    ingestor = FeedIngestor(max_retries=3, backoff_factor=0.1)
    success = await ingestor.download_episode(
        mock_session, 
        "http://example.com/ep1.mp3", 
        "dummy_path.mp3"
    )

    assert success is True
    assert mock_session.get.call_count == 2
