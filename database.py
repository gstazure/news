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

            # Table for hierarchical workflow management
            conn.execute('''
                CREATE TABLE IF NOT EXISTS workflow_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    type TEXT NOT NULL CHECK(type IN ('search_result', 'parsed_news', 'generated_post')),
                    title TEXT NOT NULL,
                    url TEXT,
                    content TEXT,
                    word_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES workflow_items (id)
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_workflow_parent_id ON workflow_items(parent_id)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_workflow_type ON workflow_items(type)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_items(status)
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
        workflow_count = conn.execute('SELECT COUNT(*) FROM workflow_items').fetchone()[0]
        print(f"\nDatabase Statistics:")
        print(f"Articles stored: {article_count}")
        print(f"Generated posts stored: {post_count}")
        print(f"Workflow items stored: {workflow_count}")
        
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
        
        if workflow_count > 0:
            print("\nLast 3 workflow items:")
            items = conn.execute('SELECT type, title, status, created_at FROM workflow_items ORDER BY created_at DESC LIMIT 3').fetchall()
            for item in items:
                print(f"- {item['type']}: {item['title'][:50]}... ({item['status']})")

    # Workflow management methods
    def create_workflow_item(self, item_type: str, title: str, url: str = None, content: str = None, 
                           parent_id: int = None, metadata: dict = None):
        """Create a new workflow item"""
        conn = self._get_conn()
        word_count = len(content.split()) if content else 0
        metadata_json = json.dumps(metadata) if metadata else None
        
        with conn:
            cursor = conn.execute('''
                INSERT INTO workflow_items (parent_id, type, title, url, content, word_count, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (parent_id, item_type, title, url, content, word_count, metadata_json))
            item_id = cursor.lastrowid
            conn.commit()
            print(f"DEBUG: Created workflow item {item_id} - Type: {item_type}, Title: {title[:50]}...")
            return item_id

    def update_workflow_item(self, item_id: int, **kwargs):
        """Update workflow item fields"""
        conn = self._get_conn()
        
        # Build dynamic update query
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in ['status', 'title', 'content', 'url', 'metadata']:
                if field == 'metadata' and isinstance(value, dict):
                    value = json.dumps(value)
                elif field == 'content' and value:
                    # Update word count when content changes
                    kwargs['word_count'] = len(value.split())
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if 'word_count' in kwargs:
            update_fields.append("word_count = ?")
            values.append(kwargs['word_count'])
        
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(item_id)
            
            query = f"UPDATE workflow_items SET {', '.join(update_fields)} WHERE id = ?"
            with conn:
                conn.execute(query, values)
                conn.commit()
                print(f"DEBUG: Updated workflow item {item_id}")

    def get_workflow_item(self, item_id: int):
        """Get a single workflow item"""
        conn = self._get_conn()
        cur = conn.execute('SELECT * FROM workflow_items WHERE id = ?', (item_id,))
        row = cur.fetchone()
        if row:
            item = dict(row)
            if item['metadata']:
                item['metadata'] = json.loads(item['metadata'])
            return item
        return None

    def get_workflow_items(self, parent_id: int = None, item_type: str = None, status: str = None):
        """Get workflow items with optional filtering"""
        conn = self._get_conn()
        
        query = 'SELECT * FROM workflow_items WHERE 1=1'
        params = []
        
        if parent_id is not None:
            if parent_id == 0:  # Root items
                query += ' AND parent_id IS NULL'
            else:
                query += ' AND parent_id = ?'
                params.append(parent_id)
        
        if item_type:
            query += ' AND type = ?'
            params.append(item_type)
            
        if status:
            query += ' AND status = ?'
            params.append(status)
        
        query += ' ORDER BY created_at DESC'
        
        cur = conn.execute(query, params)
        items = []
        for row in cur.fetchall():
            item = dict(row)
            if item['metadata']:
                item['metadata'] = json.loads(item['metadata'])
            items.append(item)
        return items

    def get_workflow_hierarchy(self):
        """Get all workflow items organized in hierarchical structure"""
        conn = self._get_conn()
        
        # Get all items
        cur = conn.execute('SELECT * FROM workflow_items ORDER BY created_at ASC')
        all_items = []
        for row in cur.fetchall():
            item = dict(row)
            if item['metadata']:
                item['metadata'] = json.loads(item['metadata'])
            item['children'] = []
            all_items.append(item)
        
        # Build hierarchy
        item_dict = {item['id']: item for item in all_items}
        root_items = []
        
        for item in all_items:
            if item['parent_id'] is None:
                root_items.append(item)
            else:
                parent = item_dict.get(item['parent_id'])
                if parent:
                    parent['children'].append(item)
        
        return root_items

    def close(self):
        """Close the connection for this thread if it exists"""
        if hasattr(thread_local, "conn"):
            thread_local.conn.close()
            del thread_local.conn

# Create a singleton instance
db = Database()
