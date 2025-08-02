import sqlite3
import json
from datetime import datetime
from pathlib import Path
from threading import local

thread_local = local()

class Database:
    def __init__(self):
        self.db_path = str(Path(__file__).parent / 'forum_bot.db')
        self._init_db()

    def _get_conn(self):
        if not hasattr(thread_local, "conn"):
            thread_local.conn = sqlite3.connect(self.db_path, timeout=20)
            thread_local.conn.row_factory = sqlite3.Row
            # Enable foreign keys and WAL mode for each connection
            thread_local.conn.execute("PRAGMA foreign_keys = ON")
            thread_local.conn.execute("PRAGMA journal_mode=WAL")
        return thread_local.conn

    def _init_db(self):
        """Initialize the database tables"""
        conn = sqlite3.connect(self.db_path, timeout=20)  # Add timeout
        try:
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Table for storing extracted articles
            conn.execute('''
                CREATE TABLE IF NOT EXISTS extracted_articles (
                    url TEXT PRIMARY KEY,
                    title TEXT,
                    text TEXT,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table for storing generated posts
            conn.execute('''
                CREATE TABLE IF NOT EXISTS generated_posts (
                    url TEXT,
                    topic TEXT,
                    output JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (url, topic)
                )
            ''')
            conn.commit()
            
            # Test write access
            conn.execute("INSERT OR REPLACE INTO extracted_articles (url, title, text) VALUES (?, ?, ?)",
                       ('test_url', 'test_title', 'test_text'))
            conn.commit()
            conn.execute("DELETE FROM extracted_articles WHERE url = ?", ('test_url',))
            conn.commit()
            
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Database initialization error: {e}")
            raise
        finally:
            conn.close()

    def save_article(self, url: str, title: str, text: str):
        """Save or update extracted article"""
        conn = self._get_conn()
        with conn:
            conn.execute('''
                INSERT OR REPLACE INTO extracted_articles (url, title, text)
                VALUES (?, ?, ?)
            ''', (url, title, text))
            conn.commit()  # Explicitly commit
            print(f"DEBUG: Saved article with URL: {url}")

    def get_article(self, url: str) -> dict:
        """Get extracted article if it exists"""
        conn = self._get_conn()
        cur = conn.execute('''
            SELECT title, text, extracted_at
            FROM extracted_articles
            WHERE url = ?
        ''', (url,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None

    def save_generated_post(self, url: str, topic: str, output: dict):
        """Save generated post output"""
        conn = self._get_conn()
        with conn:
            conn.execute('''
                INSERT OR REPLACE INTO generated_posts (url, topic, output)
                VALUES (?, ?, ?)
            ''', (url, topic, json.dumps(output)))
            conn.commit()  # Explicitly commit
            print(f"DEBUG: Saved generated post - URL: {url}, Topic: {topic}")

    def get_generated_post(self, url: str, topic: str) -> dict:
        """Get generated post if it exists"""
        conn = self._get_conn()
        cur = conn.execute('''
            SELECT output, created_at
            FROM generated_posts
            WHERE url = ? AND topic = ?
        ''', (url, topic))
        row = cur.fetchone()
        if row:
            return {
                'output': json.loads(row['output']),
                'created_at': row['created_at']
            }
        return None

    def get_all_articles(self):
        """Get all articles in the database"""
        conn = self._get_conn()
        cur = conn.execute('SELECT * FROM extracted_articles')
        return [dict(row) for row in cur.fetchall()]

    def get_all_posts(self):
        """Get all generated posts in the database"""
        conn = self._get_conn()
        cur = conn.execute('SELECT * FROM generated_posts')
        return [dict(row) for row in cur.fetchall()]

    def print_database_stats(self):
        """Print statistics about the database content"""
        conn = self._get_conn()
        article_count = conn.execute('SELECT COUNT(*) FROM extracted_articles').fetchone()[0]
        post_count = conn.execute('SELECT COUNT(*) FROM generated_posts').fetchone()[0]
        print(f"\nDatabase Statistics:")
        print(f"Articles stored: {article_count}")
        print(f"Generated posts stored: {post_count}")
        
        if article_count > 0:
            print("\nLast 3 articles:")
            articles = conn.execute('SELECT url, title, extracted_at FROM extracted_articles ORDER BY extracted_at DESC LIMIT 3').fetchall()
            for article in articles:
                print(f"- {article['title']} ({article['url']})")
        
        if post_count > 0:
            print("\nLast 3 generated posts:")
            posts = conn.execute('SELECT url, topic, created_at FROM generated_posts ORDER BY created_at DESC LIMIT 3').fetchall()
            for post in posts:
                print(f"- Topic: {post['topic']}, URL: {post['url']}")

    def close(self):
        """Close the connection for this thread if it exists"""
        if hasattr(thread_local, "conn"):
            thread_local.conn.close()
            del thread_local.conn

# Create a singleton instance
db = Database()
