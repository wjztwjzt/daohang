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


def get_base_titles(
    channel_key: str, letter: str, page: int = 0, page_size: int = 20
) -> tuple[list[str], int]:
    """获取某频道某字母下不重复的动漫基础名字（去集数/hashtag），返回 (名字列表, 总数)"""
    from utils import normalize_base_title
    from pypinyin import lazy_pinyin, Style
    with get_db() as db:
        rows = db.execute(
            "SELECT DISTINCT display_title FROM resources WHERE channel_key=? AND pinyin_first=?",
            (channel_key, letter),
        ).fetchall()
    # 归一化去重：同一部剧的不同集数/hashtag 归并为一个基础名字
    seen = {}
    for r in rows:
        base = normalize_base_title(r["display_title"])
        if base and base not in seen:
            seen[base] = True
    bases = sorted(seen.keys(), key=lambda t: "".join(lazy_pinyin(t, style=Style.NORMAL)))
    total = len(bases)
    return bases[page * page_size: (page + 1) * page_size], total


def get_resources_by_base_title(
    channel_key: str, base_title: str, page: int = 0, page_size: int = 10
) -> tuple[list[dict], int]:
    """获取某个基础名字下的所有集数"""
    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) FROM resources WHERE channel_key=? AND display_title LIKE ?",
            (channel_key, f"{base_title}%"),
        ).fetchone()[0]
        rows = db.execute(
            "SELECT * FROM resources WHERE channel_key=? AND display_title LIKE ? ORDER BY pinyin LIMIT ? OFFSET ?",
            (channel_key, f"{base_title}%", page_size, page * page_size),
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


def _edit_distance(a: str, b: str) -> int:
    """纯 Python Levenshtein 编辑距离，用于模糊匹配"""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    # 让 a 为较短串，节省内存
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[lb]


def _fts_search_rows(fts_query: str) -> list[dict]:
    """FTS5 精确/前缀匹配，返回按 rank 排序的全部命中行（未分页）"""
    with get_db() as db:
        try:
            rows = db.execute(
                """SELECT r.* FROM resources_fts fts
                   JOIN resources r ON r.id = fts.rowid
                   WHERE resources_fts MATCH ?
                   ORDER BY rank""",
                (fts_query,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(r) for r in rows]


def search_all_resources_fuzzy(
    query_text: str, page: int = 0, page_size: int = 10
) -> tuple[list[dict], int]:
    """模糊搜索：FTS 精确/前缀匹配优先，编辑距离命中的补充在后。

    支持「错一个字 / 漏一个字」也能命中，全匹配永远排前面。
    """
    import jieba
    from utils import normalize_base_title

    query = (query_text or "").strip()
    if not query:
        return [], 0

    merged: list[dict] = []
    seen_ids: set[int] = set()

    # 1) FTS 精确/前缀匹配（优先展示）
    tokens = list(dict.fromkeys(jieba.cut_for_search(query)))
    fts_query = " ".join(f"{t}*" for t in tokens if t.strip())
    if fts_query:
        for row in _fts_search_rows(fts_query):
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                merged.append(row)

    # 2) 编辑距离模糊匹配（错字/漏字）
    #    单字不做模糊（误匹配过多），短词容错 1，长词容错 2
    qlen = len(query)
    if qlen <= 1:
        threshold = 0
    elif qlen <= 3:
        threshold = 1
    else:
        threshold = 2

    if threshold:
        q_norm = query.lower().replace(" ", "")
        with get_db() as db:
            distinct = db.execute(
                "SELECT DISTINCT display_title FROM resources"
            ).fetchall()

        matched: list[tuple[int, str]] = []
        for r in distinct:
            base = normalize_base_title(r["display_title"])
            if not base:
                continue
            b_norm = base.lower().replace(" ", "")
            dist = _edit_distance(q_norm, b_norm)
            if dist <= threshold:
                matched.append((dist, base))

        matched.sort(key=lambda x: (x[0], x[1]))  # 距离小的优先

        for dist, base in matched:
            with get_db() as db:
                rows = db.execute(
                    "SELECT * FROM resources WHERE display_title LIKE ? ORDER BY pinyin",
                    (f"{base}%",),
                ).fetchall()
            for r in rows:
                d = dict(r)
                if d["id"] not in seen_ids:
                    seen_ids.add(d["id"])
                    merged.append(d)

    total = len(merged)
    start = page * page_size
    return merged[start:start + page_size], total


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
