import sqlite3
import threading
from typing import Optional


class CacheManager:
    """Manages SQLite database caching for podcast episode downloads."""

    def __init__(self, db_path: str = "downloads.db") -> None:
        """Initialize the CacheManager and ensure the database schema exists."""
        self.db_path = db_path
        self._lock = threading.Lock()

        with self._lock:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._create_tables()

    def _create_tables(self) -> None:
        """Create the downloads table if it does not already exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                episode_url TEXT PRIMARY KEY,
                file_path TEXT,
                download_status TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def check_if_downloaded(self, url: str) -> bool:
        """Check whether the given URL has been marked as completed.

        Parameters
        ----------
        url : str
            The episode download URL.

        Returns
        -------
        bool
            True if status is 'completed', False otherwise.
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT download_status FROM downloads WHERE episode_url = ?",
                (url,)
            )
            row = cursor.fetchone()
            if row and row[0] == "completed":
                return True
            return False

    def mark_as_downloaded(self, url: str, path: str, status: str = "completed") -> None:
        """Record an episode download status to the database.

        Parameters
        ----------
        url : str
            The episode download URL.
        path : str
            The local file path where it was saved (or where it failed).
        status : str, optional
            The download status, by default "completed".
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO downloads (episode_url, file_path, download_status)
                VALUES (?, ?, ?)
                ON CONFLICT(episode_url) DO UPDATE SET
                    file_path=excluded.file_path,
                    download_status=excluded.download_status
                """,
                (url, path, status)
            )
            self.conn.commit()

    def close(self) -> None:
        """Close the SQLite database connection safely."""
        with self._lock:
            self.conn.close()
