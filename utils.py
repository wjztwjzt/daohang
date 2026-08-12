import hashlib
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from pypinyin import lazy_pinyin, Style
from config import PAGE_SIZE, CHANNELS, SEARCH_GROUP_LINK


def hash_title(title: str) -> str:
    """将标题哈希为 8 位短字符串，避免 callback_data 超过 64 字节"""
    return hashlib.md5(title.encode()).hexdigest()[:8]


# ── 拼音 ──

def get_pinyin_info(title: str) -> tuple[str, str]:
    full = "".join(lazy_pinyin(title, style=Style.NORMAL))
    first_letters = "".join(lazy_pinyin(title, style=Style.FIRST_LETTER))
    first = first_letters[0].upper() if first_letters and first_letters[0].isalpha() else "#"
    return full, first


# ── 消息链接 ──

def build_message_link(channel_id: int, message_id: int) -> str:
    chat_id = str(channel_id)
    if chat_id.startswith("-100"):
        chat_id = chat_id[4:]
    return f"https://t.me/c/{chat_id}/{message_id}"


# ── 紧凑回调格式 ──
# m|{ch}|a               → 字母选择页
# m|{ch}|l|{letter}|{p}  → 动漫名列表
# m|{ch}|t|{letter}|{hash}|{p} → 集数列表
# s|{key}|{p}            → 搜索结果翻页
# c|start                → 投诉建议
# sm                     → 搜索更多
# h                      → 使用帮助

def cb(*parts) -> str:
    return "|".join(str(p) for p in parts)


def parse_cb(data: str) -> list[str]:
    return data.split("|")


# ── 底部键盘 ──

def build_reply_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(f"{CHANNELS['ranhun']['emoji']} {CHANNELS['ranhun']['name']}"),
                KeyboardButton(f"{CHANNELS['meirifuli']['emoji']} {CHANNELS['meirifuli']['name']}"),
            ],
            [
                KeyboardButton(f"{CHANNELS['youxiudianshiju']['emoji']} {CHANNELS['youxiudianshiju']['name']}"),
                KeyboardButton("🔍 搜索更多"),
            ],
            [
                KeyboardButton("💬 投诉建议"),
                KeyboardButton("❓ 使用帮助"),
            ],
        ],
        resize_keyboard=True,
    )


# ── 内联键盘 ──

def build_inline_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text=f"{CHANNELS['ranhun']['emoji']} {CHANNELS['ranhun']['name']}",
                callback_data=cb("m", "ranhun", "a"),
            ),
            InlineKeyboardButton(
                text=f"{CHANNELS['meirifuli']['emoji']} {CHANNELS['meirifuli']['name']}",
                callback_data=cb("m", "meirifuli", "a"),
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{CHANNELS['youxiudianshiju']['emoji']} {CHANNELS['youxiudianshiju']['name']}",
                callback_data=cb("m", "youxiudianshiju", "a"),
            ),
            InlineKeyboardButton(text="🔍 搜索更多", url=SEARCH_GROUP_LINK),
        ],
        [
            InlineKeyboardButton(text="💬 投诉建议", url="https://t.me/shuangjiad_bot"),
            InlineKeyboardButton(text="❓ 使用帮助", callback_data="h"),
        ],
    ])


def build_letters_keyboard(channel_key: str, letters: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for letter in letters:
        row.append(InlineKeyboardButton(
            text=letter,
            callback_data=cb("m", channel_key, "l", letter, "0"),
        ))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="🔍 搜索更多", url=SEARCH_GROUP_LINK),
        InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_anime_list_keyboard(
    channel_key: str, letter: str, titles: list[str],
    page: int, total: int, page_size: int = 20,
) -> InlineKeyboardMarkup:
    """动漫名列表键盘"""
    total_pages = max(1, (total + page_size - 1) // page_size)
    buttons = []

    for i, t in enumerate(titles):
        idx = page * page_size + i + 1
        buttons.append([InlineKeyboardButton(
            text=f"{idx}. {t}",
            callback_data=cb("m", channel_key, "t", letter, hash_title(t), "0"),
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅ 上一页",
            callback_data=cb("m", channel_key, "l", letter, str(page - 1)),
        ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡ 下一页",
            callback_data=cb("m", channel_key, "l", letter, str(page + 1)),
        ))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="🔍 搜索更多", url=SEARCH_GROUP_LINK),
        InlineKeyboardButton(text="⬅ 返回字母", callback_data=cb("m", channel_key, "a")),
    ])
    buttons.append([
        InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_episode_list_keyboard(
    channel_key: str, letter: str, base_title: str,
    resources: list[dict], page: int, total: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    """集数列表键盘 — 每个按钮是 URL 直接跳转频道消息"""
    total_pages = max(1, (total + page_size - 1) // page_size)
    buttons = []

    for i, res in enumerate(resources):
        idx = page * page_size + i + 1
        buttons.append([InlineKeyboardButton(
            text=f"{idx}. {res['display_title']}",
            url=res["message_link"],
        )])

    title_hash = hash_title(base_title)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅ 上一页",
            callback_data=cb("m", channel_key, "t", letter, title_hash, str(page - 1)),
        ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="➡ 下一页",
            callback_data=cb("m", channel_key, "t", letter, title_hash, str(page + 1)),
        ))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="🔍 搜索更多", url=SEARCH_GROUP_LINK),
        InlineKeyboardButton(text="⬅ 返回动漫列表",
                             callback_data=cb("m", channel_key, "l", letter, "0")),
    ])
    buttons.append([
        InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_search_results_keyboard(
    query_key: str, results: list[dict], page: int, total: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    """搜索结果键盘 — 每项直接 URL 跳转"""
    total_pages = max(1, (total + page_size - 1) // page_size)
    buttons = []

    for i, res in enumerate(results):
        idx = page * page_size + i + 1
        emoji = CHANNELS.get(res["channel_key"], {}).get("emoji", "")
        buttons.append([InlineKeyboardButton(
            text=f"{idx}. [{emoji}] {res['display_title']}",
            url=res["message_link"],
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅ 上页",
            callback_data=cb("s", query_key, str(page - 1)),
        ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="下页 ➡",
            callback_data=cb("s", query_key, str(page + 1)),
        ))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__"),
    ])
    return InlineKeyboardMarkup(buttons)
