import sqlite3
from pathlib import Path

import re
import sqlite3
from pathlib import Path

BASE_DIRECTORY = Path(__file__).resolve().parent
DATA_DIRECTORY = BASE_DIRECTORY / "data"
DATABASE_PATH = DATA_DIRECTORY / "atlas.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def initialize_database() -> None:
    DATA_DIRECTORY.mkdir(exist_ok=True)

    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL,
                source_location TEXT NOT NULL,
                access_role TEXT NOT NULL DEFAULT 'employee',
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS knowledge_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                owner TEXT NOT NULL,
                access_role TEXT NOT NULL DEFAULT 'employee',
                current_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS article_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('draft', 'published', 'archived')),
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (article_id)
                    REFERENCES knowledge_articles(id),

                UNIQUE (article_id, version)
            );

            CREATE TABLE IF NOT EXISTS article_sources (
                article_id INTEGER NOT NULL,
                source_document_id INTEGER NOT NULL,

                FOREIGN KEY (article_id)
                    REFERENCES knowledge_articles(id),

                FOREIGN KEY (source_document_id)
                    REFERENCES source_documents(id),

                PRIMARY KEY (article_id, source_document_id)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search USING fts5(
                article_id UNINDEXED,
                version_id UNINDEXED,
                title,
                content,
                tokenize = 'porter unicode61'
            );
            """
        )
        connection.commit()

def seed_demo_data() -> None:
    sources = [
        (
            "Hardware Returns Policy",
            "Imported document",
            "Support Operations / Policies",
            "employee",
            (
                "Customers may return company-issued hardware "
                "within 14 calendar days of receipt. Devices must "
                "include all accessories and must not show accidental damage."
            ),
        ),
        (
            "Malaysia Returns Addendum",
            "Imported document",
            "Malaysia Operations / Returns",
            "support",
            (
                "Malaysia follows the global hardware return window. "
                "Enterprise contract exceptions remain governed by "
                "the signed customer agreement."
            ),
        ),
        (
            "Remote Access Runbook",
            "Imported document",
            "IT Service Desk / Runbooks",
            "employee",
            (
                "Employees requesting VPN access must complete "
                "multi-factor authentication enrollment and receive "
                "manager approval before access is provisioned."
            ),
        ),
    ]

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT OR IGNORE INTO source_documents (
                title,
                source_type,
                source_location,
                access_role,
                content
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            sources,
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO knowledge_articles (
                slug,
                title,
                owner,
                access_role,
                current_version
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "malaysia-hardware-returns",
                "Hardware returns — Malaysia",
                "Malaysia Support Operations",
                "support",
                1,
            ),
        )

        article = connection.execute(
            """
            SELECT id
            FROM knowledge_articles
            WHERE slug = ?
            """,
            ("malaysia-hardware-returns",),
        ).fetchone()

        connection.execute(
            """
            INSERT OR IGNORE INTO article_versions (
                article_id,
                version,
                content,
                status,
                created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                article["id"],
                1,
                (
                    "Customers in Malaysia may return company-issued "
                    "hardware within 14 calendar days of receipt. "
                    "Enterprise contract exceptions follow the signed "
                    "customer agreement."
                ),
                "published",
                "Demo administrator",
            ),
        )

        source_rows = connection.execute(
            """
            SELECT id
            FROM source_documents
            WHERE title IN (?, ?)
            """,
            (
                "Hardware Returns Policy",
                "Malaysia Returns Addendum",
            ),
        ).fetchall()

        for source in source_rows:
            connection.execute(
                """
                INSERT OR IGNORE INTO article_sources (
                    article_id,
                    source_document_id
                )
                VALUES (?, ?)
                """,
                (article["id"], source["id"]),
            )

        connection.commit()


def list_sources() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                title,
                source_type,
                source_location,
                access_role,
                content,
                created_at
            FROM source_documents
            ORDER BY title
            """
        ).fetchall()

    return [dict(row) for row in rows]

ROLE_ACCESS = {
    "employee": ("employee",),
    "support": ("employee", "support"),
    "admin": ("employee", "support", "admin"),
}

def refresh_search_index() -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM knowledge_search")

        connection.execute(
            """
            INSERT INTO knowledge_search (
                article_id,
                version_id,
                title,
                content
            )
            SELECT
                knowledge_articles.id,
                article_versions.id,
                knowledge_articles.title,
                article_versions.content
            FROM article_versions
            JOIN knowledge_articles
                ON knowledge_articles.id = article_versions.article_id
            WHERE article_versions.status = 'published'
              AND article_versions.version = knowledge_articles.current_version
            """
        )
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "for",
    "have",
    "how",
    "i",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "what",
    "when",
    "where",
    "who",
    "why",
}

def build_search_query(question: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", question.lower())

    meaningful_words = [
        word
        for word in words
        if len(word) > 1 and word not in STOP_WORDS
    ]

    unique_words = list(dict.fromkeys(meaningful_words))
    selected_words = unique_words[:12]

    return " OR ".join(f'"{word}"' for word in selected_words) 

def search_knowledge(
    question: str,
    role: str = "support",
    limit: int = 3,
) -> list[dict]:
    search_query = build_search_query(question)

    if not search_query:
        return []

    allowed_roles = ROLE_ACCESS.get(
        role,
        ROLE_ACCESS["employee"],
    )

    role_placeholders = ", ".join(
        "?" for _ in allowed_roles
    )

    sql = f"""
        SELECT
            CAST(knowledge_search.article_id AS INTEGER) AS article_id,
            CAST(knowledge_search.version_id AS INTEGER) AS version_id,
            knowledge_articles.title,
            knowledge_articles.owner,
            knowledge_articles.access_role,
            knowledge_articles.current_version,
            article_versions.content AS content,
            snippet(
                knowledge_search,
                3,
                '',
                '',
                ' … ',
                35
            ) AS excerpt,
            bm25(
                knowledge_search,
                0.0,
                0.0,
                3.0,
                1.0
            ) AS score
        FROM knowledge_search
        JOIN article_versions
            ON article_versions.id =
               CAST(knowledge_search.version_id AS INTEGER)
        JOIN knowledge_articles
            ON knowledge_articles.id =
               CAST(knowledge_search.article_id AS INTEGER)
        WHERE knowledge_search MATCH ?
          AND knowledge_articles.access_role IN ({role_placeholders})
          AND article_versions.status = 'published'
          AND article_versions.version =
              knowledge_articles.current_version
        ORDER BY score
        LIMIT ?
    """

    parameters = [
        search_query,
        *allowed_roles,
        limit,
    ]

    with get_connection() as connection:
        rows = connection.execute(
            sql,
            parameters,
        ).fetchall()

        results = []

        for row in rows:
            result = dict(row)

            source_rows = connection.execute(
                """
                SELECT
                    source_documents.title,
                    source_documents.source_type,
                    source_documents.source_location,
                    source_documents.content
                FROM article_sources
                JOIN source_documents
                    ON source_documents.id =
                       article_sources.source_document_id
                WHERE article_sources.article_id = ?
                ORDER BY source_documents.title
                """,
                (result["article_id"],),
            ).fetchall()

            result["sources"] = [
                dict(source)
                for source in source_rows
            ]

            results.append(result)

        return results      