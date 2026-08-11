from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from pypinyin import lazy_pinyin, Style
from config import PAGE_SIZE, CHANNELS


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


# ── 紧凑回调格式（杜绝 64 字节限制） ──
# m|{ch}|a              → 字母选择页
# m|{ch}|l|{letter}|{p} → 资源列表
# r|{id}                → 资源详情（返回信息存在 user_data['nav']）
# s|{key}|{p}           → 搜索结果翻页
# c|start / c|t|{type} / c|cancel
# sm                    → 搜索更多
# h                     → 使用帮助

def cb(*parts) -> str:
    """构建回调数据，参数直接拼接"""
    return "|".join(str(p) for p in parts)


def parse_cb(data: str) -> list[str]:
    """解析回调数据，返回 parts 列表"""
    return data.split("|")


# ── 底部键盘（ReplyKeyboardMarkup — 首页 6 按钮） ──

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


# ── 内联键盘（InlineKeyboardMarkup — 各级导航） ──

def build_inline_main_menu() -> InlineKeyboardMarkup:
    """内联版主菜单（作为 /start 消息的后备）"""
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
            InlineKeyboardButton(text="🔍 搜索更多", callback_data="sm"),
        ],
        [
            InlineKeyboardButton(text="💬 投诉建议", callback_data="c|start"),
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
        InlineKeyboardButton(text="🔍 搜索更多", callback_data="sm"),
        InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_resource_list_keyboard(
    channel_key: str, letter: str, resources: list[dict],
    page: int, total: int, page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    total_pages = (total + page_size - 1) // page_size
    buttons = []

    for i, res in enumerate(resources):
        idx = page * page_size + i + 1
        # 返回信息存 user_data['nav']，回调只传资源 ID
        buttons.append([InlineKeyboardButton(
            text=f"{idx}. {res['display_title']}",
            callback_data=cb("r", res["id"]),
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
        InlineKeyboardButton(text="🔍 搜索更多", callback_data="sm"),
        InlineKeyboardButton(text="⬅ 返回字母", callback_data=cb("m", channel_key, "a")),
    ])
    buttons.append([
        InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_resource_detail_keyboard(message_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🔗 跳转到频道消息", url=message_link)],
        [
            InlineKeyboardButton(text="⬅ 返回", callback_data="back"),
            InlineKeyboardButton(text="🔍 搜索更多", callback_data="sm"),
        ],
        [InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__")],
    ])


def build_search_results_keyboard(
    query_key: str, results: list[dict], page: int, total: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    total_pages = (total + page_size - 1) // page_size
    buttons = []

    for i, res in enumerate(results):
        idx = page * page_size + i + 1
        emoji = CHANNELS.get(res["channel_key"], {}).get("emoji", "")
        buttons.append([InlineKeyboardButton(
            text=f"{idx}. [{emoji}] {res['display_title']}",
            callback_data=cb("r", res["id"]),
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
