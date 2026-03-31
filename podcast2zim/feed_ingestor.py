import asyncio
import logging
import re
from typing import List, Dict, Optional, Any

import aiohttp
import feedparser

logger = logging.getLogger(__name__)

class FeedIngestor:
    """
    Handles parsing of podcast RSS feeds and asynchronous downloads.

    Attributes
    ----------
    max_retries : int
        Maximum number of retry attempts for a download.
    backoff_factor : float
        Exponential factor for backoff timing.
    timeout : int
        HTTP request timeout in seconds.
    chunk_size : int
        Size of the chunks to read/write for memory efficiency.
    user_agent : str
        User-Agent header to use during HTTP requests.
    """

    def __init__(
        self, 
        max_retries: int = 5, 
        backoff_factor: float = 2.0, 
        timeout: int = 30,
        chunk_size: int = 1024 * 1024, # 1 MB chunks
        user_agent: str = "Podcast2Zim/1.0"
    ) -> None:
        """
        Initialize the FeedIngestor with configurable settings.

        Parameters
        ----------
        max_retries : int, optional
            Max retries for downloads, by default 5.
        backoff_factor : float, optional
            Exponential backoff multiplier, by default 2.0.
        timeout : int, optional
            Request timeout in seconds, by default 30.
        chunk_size : int, optional
            Chunk size in bytes for downloading files, by default 1MB.
        user_agent : str, optional
            User string to send on GET requests, by default Podcast2Zim/1.0.
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.user_agent = user_agent

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a string to be a safe filename, preserving spaces and hyphens.
        
        Parameters
        ----------
        filename : str
            The original string to sanitize.
            
        Returns
        -------
        str
            A filesystem-safe filename up to 200 characters.
        """
        # Remove characters that aren't alphanumeric, space, dot, or hyphen
        safe = re.sub(r'[^\w\s.-]', '', filename)
        # Collapse multiple spaces
        safe = re.sub(r'\s+', ' ', safe)
        # Strip leading/trailing whitespaces and limit to 200 chars
        return safe.strip()[:200]

    def parse_feed(self, url: str) -> Dict[str, Any]:
        """
        Extract podcast title and episodes from an RSS feed URL.

        Parameters
        ----------
        url : str
            The RSS feed URL.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing 'podcast_title' and a list of 'episodes'
            where each episode is a dict with 'title' and 'media_url'.
        """
        feed = feedparser.parse(url)
        podcast_title = feed.feed.get("title", "Unknown Podcast")
        episodes = []

        for entry in feed.entries:
            title = entry.get("title", "Untitled Episode")
            enclosures = entry.get("enclosures", [])
            media_url: Optional[str] = None
            
            for enc in enclosures:
                if enc.get("type", "").startswith("audio/"):
                    media_url = enc.get("href")
                    break
            
            if media_url:
                episodes.append({
                    "title": title,
                    "media_url": media_url
                })
        
        return {
            "podcast_title": podcast_title,
            "episodes": episodes
        }

    async def _bounded_download(
        self,
        semaphore: asyncio.Semaphore,
        session: aiohttp.ClientSession,
        media_url: str,
        file_path: str
    ) -> bool:
        """
        Download with concurrency limits imposed by a a semaphore limit.
        """
        async with semaphore:
            return await self.download_episode(session, media_url, file_path)

    async def download_episode(
        self, 
        session: aiohttp.ClientSession, 
        media_url: str, 
        file_path: str
    ) -> bool:
        """
        Download a single .mp3 file in chunks with exponential backoff retries.

        Handles TimeoutError and HTTP 429/500/502/503/504 errors.

        Parameters
        ----------
        session : aiohttp.ClientSession
            The aiohttp session to use.
        media_url : str
            The direct URL to the .mp3 file.
        file_path : str
            The destination path on disk.

        Returns
        -------
        bool
            True if download succeeded, False otherwise.
        """
        for attempt in range(self.max_retries):
            try:
                async with session.get(media_url, timeout=self.timeout) as response:
                    if response.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(self.chunk_size):
                                f.write(chunk)
                        return True
                    
                    if response.status in (429, 500, 502, 503, 504):
                        logger.warning(
                            f"HTTP {response.status} for {media_url}. "
                            f"Retrying ({attempt + 1}/{self.max_retries})...."
                        )
                    else:
                        logger.error(f"HTTP {response.status} for {media_url}. Permanent failure.")
                        return False

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(
                    f"Connection error for {media_url}: {e}. "
                    f"Retrying ({attempt + 1}/{self.max_retries})...."
                )

            if attempt < self.max_retries - 1:
                wait_time = self.backoff_factor * (2 ** attempt)
                await asyncio.sleep(wait_time)
        
        logger.error(f"Exhausted retries for {media_url}.")
        return False

    async def download_all(self, feed_data: Dict[str, Any], output_dir: str, max_concurrent: int = 5) -> List[bool]:
        """
        Coordinate bounded asynchronous downloading of all episodes in the feed.

        Parameters
        ----------
        feed_data : Dict[str, Any]
            The output from parse_feed.
        output_dir : str
            Directory to save downloaded files.
        max_concurrent : int, optional
            Maximum number of concurrent downloads allowed, by default 5.

        Returns
        -------
        List[bool]
            List of success statuses for each episode.
        """
        headers = {"User-Agent": self.user_agent}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async with aiohttp.ClientSession(headers=headers) as session:
            tasks = []
            for episode in feed_data["episodes"]:
                safe_title = self.sanitize_filename(episode["title"])
                # Backup to index if title completely invalid
                if not safe_title:
                   safe_title = "unknown_episode"
                
                file_path = f"{output_dir}/{safe_title}.mp3"
                tasks.append(self._bounded_download(semaphore, session, episode["media_url"], file_path))
            
            return await asyncio.gather(*tasks)
