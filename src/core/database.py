"""SQLite database with FTS5 for full-text search."""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager with FTS5 support."""

    def get_startup_by_name_and_source(self, name: str, source: str = None) -> Optional[Dict[str, Any]]:
        """Get a startup by name and source."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if source:
                cursor.execute(
                    "SELECT * FROM startups WHERE name = ? AND source = ?", (name, source)
                )
            else:
                cursor.execute(
                    "SELECT * FROM startups WHERE name = ?", (name,)
                )
            row = cursor.fetchone()
            return dict(row) if row else None

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main startups table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS startups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    short_description TEXT,
                    long_description TEXT,
                    founded_year INTEGER,
                    total_funding_usd REAL,
                    funding_stage TEXT,
                    employee_count TEXT,
                    website_url TEXT,
                    linkedin_url TEXT,
                    crunchbase_url TEXT,
                    headquarters_location TEXT,
                    country TEXT,
                    primary_vertical TEXT,
                    secondary_verticals TEXT,
                    technologies TEXT,
                    keywords TEXT,
                    source TEXT,
                    source_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, source)
                )
            """)

            # FTS5 virtual table for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS startups_fts USING fts5(
                    name,
                    short_description,
                    long_description,
                    technologies,
                    keywords,
                    content='startups',
                    content_rowid='id'
                )
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS startups_ai AFTER INSERT ON startups BEGIN
                    INSERT INTO startups_fts(rowid, name, short_description, long_description, technologies, keywords)
                    VALUES (new.id, new.name, new.short_description, new.long_description, new.technologies, new.keywords);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS startups_ad AFTER DELETE ON startups BEGIN
                    INSERT INTO startups_fts(startups_fts, rowid, name, short_description, long_description, technologies, keywords)
                    VALUES ('delete', old.id, old.name, old.short_description, old.long_description, old.technologies, old.keywords);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS startups_au AFTER UPDATE ON startups BEGIN
                    INSERT INTO startups_fts(startups_fts, rowid, name, short_description, long_description, technologies, keywords)
                    VALUES ('delete', old.id, old.name, old.short_description, old.long_description, old.technologies, old.keywords);
                    INSERT INTO startups_fts(rowid, name, short_description, long_description, technologies, keywords)
                    VALUES (new.id, new.name, new.short_description, new.long_description, new.technologies, new.keywords);
                END
            """)

            # Interaction logs table for CTR tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interaction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    startup_id INTEGER,
                    rank INTEGER,
                    action TEXT,
                    session_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (startup_id) REFERENCES startups(id)
                )
            """)

            # Index for performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_startups_vertical ON startups(primary_vertical)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_startups_funding ON startups(total_funding_usd)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_startups_year ON startups(founded_year)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_query ON interaction_logs(query)"
            )

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def insert_startup(self, startup: Dict[str, Any]) -> Optional[int]:
        """Insert or update a startup record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Convert lists to JSON strings
            if isinstance(startup.get("secondary_verticals"), list):
                startup["secondary_verticals"] = json.dumps(
                    startup["secondary_verticals"]
                )
            if isinstance(startup.get("technologies"), list):
                startup["technologies"] = json.dumps(startup["technologies"])
            if isinstance(startup.get("keywords"), list):
                startup["keywords"] = json.dumps(startup["keywords"])

            try:
                cursor.execute(
                    """
                    INSERT INTO startups (
                        name, short_description, long_description, founded_year,
                        total_funding_usd, funding_stage, employee_count, website_url,
                        linkedin_url, crunchbase_url, headquarters_location, country,
                        primary_vertical, secondary_verticals, technologies, keywords,
                        source, source_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name, source) DO UPDATE SET
                        short_description = excluded.short_description,
                        long_description = excluded.long_description,
                        founded_year = excluded.founded_year,
                        total_funding_usd = excluded.total_funding_usd,
                        funding_stage = excluded.funding_stage,
                        employee_count = excluded.employee_count,
                        website_url = excluded.website_url,
                        linkedin_url = excluded.linkedin_url,
                        crunchbase_url = excluded.crunchbase_url,
                        headquarters_location = excluded.headquarters_location,
                        country = excluded.country,
                        primary_vertical = excluded.primary_vertical,
                        secondary_verticals = excluded.secondary_verticals,
                        technologies = excluded.technologies,
                        keywords = excluded.keywords,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        startup.get("name"),
                        startup.get("short_description"),
                        startup.get("long_description"),
                        startup.get("founded_year"),
                        startup.get("total_funding_usd"),
                        startup.get("funding_stage"),
                        startup.get("employee_count"),
                        startup.get("website_url"),
                        startup.get("linkedin_url"),
                        startup.get("crunchbase_url"),
                        startup.get("headquarters_location"),
                        startup.get("country"),
                        startup.get("primary_vertical"),
                        startup.get("secondary_verticals"),
                        startup.get("technologies"),
                        startup.get("keywords"),
                        startup.get("source"),
                        startup.get("source_id"),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                logger.error(f"Error inserting startup {startup.get('name')}: {e}")
                return None

    def get_startup_by_id(self, startup_id: int) -> Optional[Dict[str, Any]]:
        """Get a startup by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM startups WHERE id = ?", (startup_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None

    def get_all_startups(self) -> List[Dict[str, Any]]:
        """Get all startups."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM startups ORDER BY id")
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def search_fts(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search using FTS5."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Escape special characters for FTS5
            safe_query = query.replace('"', '""')
            cursor.execute(
                f"""
                SELECT s.*, bm25(startups_fts) as score
                FROM startups s
                JOIN startups_fts ON s.id = startups_fts.rowid
                WHERE startups_fts MATCH '"{safe_query}"'
                ORDER BY score
                LIMIT ?
            """,
                (limit,),
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_startups_by_vertical(
        self, vertical: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get startups by vertical."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM startups
                WHERE primary_vertical = ?
                ORDER BY total_funding_usd DESC NULLS LAST
                LIMIT ?
            """,
                (vertical, limit),
            )
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) FROM startups")
            total = cursor.fetchone()[0]

            # Count by vertical
            cursor.execute("""
                SELECT primary_vertical, COUNT(*) as count
                FROM startups
                WHERE primary_vertical IS NOT NULL
                GROUP BY primary_vertical
                ORDER BY count DESC
            """)
            verticals = {row[0]: row[1] for row in cursor.fetchall()}

            # Funding stats
            cursor.execute("""
                SELECT
                    SUM(total_funding_usd) as total_funding,
                    AVG(total_funding_usd) as avg_funding,
                    MAX(total_funding_usd) as max_funding
                FROM startups
                WHERE total_funding_usd IS NOT NULL
            """)
            funding_row = cursor.fetchone()

            # Year range
            cursor.execute("""
                SELECT MIN(founded_year), MAX(founded_year)
                FROM startups
                WHERE founded_year IS NOT NULL
            """)
            year_row = cursor.fetchone()

            return {
                "total_startups": total,
                "verticals": verticals,
                "total_funding": funding_row[0] or 0,
                "avg_funding": funding_row[1] or 0,
                "max_funding": funding_row[2] or 0,
                "min_year": year_row[0],
                "max_year": year_row[1],
                "last_updated": datetime.now().isoformat(),
            }

    def log_interaction(
        self,
        query: str,
        startup_id: int,
        rank: int,
        action: str = "click",
        session_id: str = None,
    ):
        """Log a user interaction for CTR tracking."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO interaction_logs (query, startup_id, rank, action, session_id)
                VALUES (?, ?, ?, ?, ?)
            """,
                (query, startup_id, rank, action, session_id),
            )
            conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = dict(row)

        # Parse JSON fields
        for field in ["secondary_verticals", "technologies", "keywords"]:
            if field in result and result[field]:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        return result

    def get_startup_count(self) -> int:
        """Get total number of startups."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM startups")
            return cursor.fetchone()[0]
