import sqlite3
from contextlib import contextmanager
from config import DB_PATH, DATA_DIR

# ── SQL DDL ──

CREATE_RESOURCES = """
CREATE TABLE IF NOT EXISTS resources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_key     TEXT    NOT NULL,
    message_id      INTEGER NOT NULL,
    title           TEXT    NOT NULL,
    display_title   TEXT    NOT NULL,
    pinyin          TEXT    NOT NULL,
    pinyin_first    TEXT    NOT NULL,
    message_link    TEXT    NOT NULL,
    file_type       TEXT    DEFAULT '',
    created_at      TEXT    DEFAULT (datetime('now','localtime')),
    UNIQUE(channel_key, message_id)
);
"""

CREATE_RESOURCES_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5(
    title,
    pinyin,
    content='resources',
    content_rowid='id',
    tokenize='unicode61'
);
"""

CREATE_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS resources_ai AFTER INSERT ON resources BEGIN
    INSERT INTO resources_fts(rowid, title, pinyin)
    VALUES (new.id, new.title, new.pinyin);
END;

CREATE TRIGGER IF NOT EXISTS resources_ad AFTER DELETE ON resources BEGIN
    INSERT INTO resources_fts(resources_fts, rowid, title, pinyin)
    VALUES ('delete', old.id, old.title, old.pinyin);
END;

CREATE TRIGGER IF NOT EXISTS resources_au AFTER UPDATE ON resources BEGIN
    INSERT INTO resources_fts(resources_fts, rowid, title, pinyin)
    VALUES ('delete', old.id, old.title, old.pinyin);
    INSERT INTO resources_fts(rowid, title, pinyin)
    VALUES (new.id, new.title, new.pinyin);
END;
"""

CREATE_COMPLAINTS = """
CREATE TABLE IF NOT EXISTS complaints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         BIGINT  NOT NULL,
    username        TEXT    DEFAULT '',
    complaint_type  TEXT    NOT NULL DEFAULT 'suggestion',
    content         TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',
    created_at      TEXT    DEFAULT (datetime('now','localtime'))
);
"""

CREATE_CONFIG = """
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT DEFAULT ''
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_resources_channel      ON resources(channel_key);
CREATE INDEX IF NOT EXISTS idx_resources_pinyin_first ON resources(pinyin_first);
CREATE INDEX IF NOT EXISTS idx_resources_pinyin       ON resources(pinyin);
CREATE INDEX IF NOT EXISTS idx_resources_title        ON resources(title);
CREATE INDEX IF NOT EXISTS idx_complaints_user_id     ON complaints(user_id);
"""


def init_db() -> None:
    """初始化数据库 — 建表 + 索引 + 触发器 + 默认配置"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(CREATE_RESOURCES)
    conn.executescript(CREATE_RESOURCES_FTS)
    conn.executescript(CREATE_TRIGGERS)
    conn.executescript(CREATE_COMPLAINTS)
    conn.executescript(CREATE_CONFIG)
    conn.executescript(CREATE_INDEXES)
    conn.executescript("""
        INSERT OR IGNORE INTO config (key, value, description) VALUES
            ('search_group_link', '', '搜索群链接'),
            ('search_group_name', '资源搜索互助群', '搜索群名称'),
            ('search_bot_link', '', '搜索机器人链接'),
            ('search_bot_name', '资源搜索机器人', '搜索机器人名称');
    """)
    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器，自动提交/关闭）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── 资源查询 ──

def get_pinyin_letters(channel_key: str) -> list[str]:
    """获取某频道下有哪些拼音首字母（去重排序）"""
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT pinyin_first FROM resources WHERE channel_key=? ORDER BY pinyin_first",
            (channel_key,),
        ).fetchall()
    return [r["pinyin_first"] for r in rows]


def get_resources_by_letter(
    channel_key: str, letter: str, page: int = 0, page_size: int = 10
) -> tuple[list[dict], int]:
    """按拼音首字母获取资源列表（分页），返回 (资源列表, 总数)"""
    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM resources WHERE channel_key=? AND pinyin_first=?",
            (channel_key, letter),
        ).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM resources WHERE channel_key=? AND pinyin_first=? ORDER BY pinyin LIMIT ? OFFSET ?",
            (channel_key, letter, page_size, page * page_size),
        ).fetchall()
    return [dict(r) for r in rows], total


def get_resource_by_id(resource_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
    return dict(row) if row else None


def search_resources(query: str, page: int = 0, page_size: int = 10) -> tuple[list[dict], int]:
    """FTS5 全文搜索，返回 (资源列表, 总数)"""
    with get_db() as db:
        try:
            total = db.execute(
                "SELECT COUNT(*) FROM resources_fts WHERE resources_fts MATCH ?",
                (query,),
            ).fetchone()[0]
            rows = db.execute(
                """SELECT r.* FROM resources_fts fts
                   JOIN resources r ON r.id = fts.rowid
                   WHERE resources_fts MATCH ?
                   ORDER BY rank LIMIT ? OFFSET ?""",
                (query, page_size, page * page_size),
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS 查询语法错误时返回空
            return [], 0
    return [dict(r) for r in rows], total


def search_all_resources(query: str, page: int = 0, page_size: int = 10) -> tuple[list[dict], int]:
    """全库搜索（不限定频道）"""
    return search_resources(query, page, page_size)


def insert_resource(
    channel_key: str,
    message_id: int,
    title: str,
    display_title: str,
    pinyin: str,
    pinyin_first: str,
    message_link: str,
    file_type: str = "",
) -> int | None:
    try:
        with get_db() as db:
            cur = db.execute(
                """INSERT OR IGNORE INTO resources
                   (channel_key, message_id, title, display_title, pinyin, pinyin_first, message_link, file_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (channel_key, message_id, title, display_title, pinyin, pinyin_first, message_link, file_type),
            )
            return cur.lastrowid if cur.rowcount else None
    except Exception:
        return None


def resource_exists(channel_key: str, message_id: int) -> bool:
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM resources WHERE channel_key=? AND message_id=?", (channel_key, message_id)
        ).fetchone()
    return row is not None


def get_total_count(channel_key: str | None = None) -> int:
    with get_db() as db:
        if channel_key:
            row = db.execute("SELECT COUNT(*) FROM resources WHERE channel_key=?", (channel_key,)).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) FROM resources").fetchone()
    return row[0] if row else 0


# ── 投诉建议 ──

def insert_complaint(user_id: int, username: str, complaint_type: str, content: str) -> int:
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO complaints (user_id, username, complaint_type, content) VALUES (?, ?, ?, ?)",
            (user_id, username, complaint_type, content),
        )
        return cur.lastrowid


# ── 配置读写 ──

def get_config(key: str) -> str | None:
    with get_db() as db:
        row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_config(key: str, value: str) -> None:
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
        )
