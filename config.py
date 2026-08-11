import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env_or(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip() or default


# ── Bot 配置 ──
BOT_TOKEN = _env_or("BOT_TOKEN")

# ── Telethon 配置 ──
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = _env_or("API_HASH")
PHONE = _env_or("PHONE")
PASSWORD = _env_or("PASSWORD")
SESSION_NAME = _env_or("SESSION_NAME", "collector_session")

# ── 数据库 ──
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "daohang.db"

# ── 分页 ──
PAGE_SIZE = 10

# ── 频道定义 ──
CHANNELS = {
    "ranhun": {
        "key": "ranhun",
        "id": int(os.getenv("CHANNEL_RANHUN_ID", "0")),
        "username": _env_or("CHANNEL_RANHUN_USERNAME", "@ranhun"),
        "name": "燃魂动漫",
        "emoji": "🔥",
    },
    "meirifuli": {
        "key": "meirifuli",
        "id": int(os.getenv("CHANNEL_MEIRIFULI_ID", "0")),
        "username": _env_or("CHANNEL_MEIRIFULI_USERNAME", "@meirifuli"),
        "name": "每日福利",
        "emoji": "🎁",
    },
    "youxiudianshiju": {
        "key": "youxiudianshiju",
        "id": int(os.getenv("CHANNEL_YOUXIUDIANSHIJU_ID", "0")),
        "username": _env_or("CHANNEL_YOUXIUDIANSHIJU_USERNAME", "@youxiudianshiju"),
        "name": "优秀电视剧",
        "emoji": "📺",
    },
}

# channel_id -> channel_key 反向映射
CHANNEL_ID_MAP = {ch["id"]: ch["key"] for ch in CHANNELS.values() if ch["id"]}


def get_channel_by_id(chat_id: int) -> dict | None:
    """根据 chat_id 获取频道配置"""
    key = CHANNEL_ID_MAP.get(chat_id)
    return CHANNELS.get(key) if key else None


def get_channel(key: str) -> dict | None:
    return CHANNELS.get(key)


# ── 外部链接 ──
SEARCH_GROUP_LINK = _env_or("SEARCH_GROUP_LINK", "https://t.me/your_search_group")
SEARCH_GROUP_NAME = _env_or("SEARCH_GROUP_NAME", "资源搜索互助群")

# ── 代理配置 ──
PROXY = None
if os.getenv("PROXY_ENABLED", "0") == "1":
    PROXY = (
        _env_or("PROXY_TYPE", "socks5"),
        _env_or("PROXY_HOST", "127.0.0.1"),
        int(os.getenv("PROXY_PORT", "10809")),
    )

# ── 回调前缀 ──
CB_MENU = "menu"
CB_RES = "res"
CB_SEARCH = "search"
CB_COMPLAINT = "complaint"
CB_SEARCH_MORE = "search_more"
CB_HELP = "help"
