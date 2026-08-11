import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pypinyin import lazy_pinyin, Style
from config import PAGE_SIZE, CHANNELS


# ── 拼音 ──

def get_pinyin_info(title: str) -> tuple[str, str]:
    """返回 (全拼, 首字母大写)，如 ("guangyinzhiwai", "G")"""
    full = "".join(lazy_pinyin(title, style=Style.NORMAL))
    first_letters = "".join(lazy_pinyin(title, style=Style.FIRST_LETTER))
    first = first_letters[0].upper() if first_letters and first_letters[0].isalpha() else "#"
    return full, first


# ── 消息链接 ──

def build_message_link(channel_id: int, message_id: int) -> str:
    """根据频道 ID 和消息 ID 构建 t.me 跳转链接"""
    # 频道 ID 格式: -100xxxxxxxxx，去掉 -100 前缀即为 c/ 后的部分
    chat_id = str(channel_id)
    if chat_id.startswith("-100"):
        chat_id = chat_id[4:]
    return f"https://t.me/c/{chat_id}/{message_id}"


# ── 回调数据编解码 ──

def encode_callback(prefix: str, **kwargs) -> str:
    """编码回调数据: prefix|k1=v1|k2=v2"""
    parts = [prefix]
    for k, v in kwargs.items():
        encoded = urllib.parse.quote(str(v), safe="")
        parts.append(f"{k}={encoded}")
    return "|".join(parts)


def decode_callback(data: str) -> dict:
    """解码回调数据，返回 {'prefix': 'menu', 'ch': 'ranhun', ...}"""
    parts = data.split("|")
    result = {"prefix": parts[0]}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            result[k] = urllib.parse.unquote(v)
        else:
            result[part] = True
    return result


# ── 搜索词编码 ──

def encode_search_query(query: str) -> str:
    """将搜索词编码为 URL-safe 字符串（截取前 20 位避免过长）"""
    encoded = urllib.parse.quote(query, safe="")
    return encoded[:40]


def decode_search_query(encoded: str) -> str:
    return urllib.parse.unquote(encoded)


# ── 键盘构建 ──

def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    """构建主菜单键盘（6按钮 3行×2列）"""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{CHANNELS['ranhun']['emoji']} {CHANNELS['ranhun']['name']}",
                callback_data=encode_callback("menu", ch="ranhun", action="letters", p="0"),
            ),
            InlineKeyboardButton(
                text=f"{CHANNELS['meirifuli']['emoji']} {CHANNELS['meirifuli']['name']}",
                callback_data=encode_callback("menu", ch="meirifuli", action="letters", p="0"),
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{CHANNELS['youxiudianshiju']['emoji']} {CHANNELS['youxiudianshiju']['name']}",
                callback_data=encode_callback("menu", ch="youxiudianshiju", action="letters", p="0"),
            ),
            InlineKeyboardButton(
                text="🔍 搜索更多",
                callback_data="search_more",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💬 投诉建议",
                callback_data="complaint|start",
            ),
            InlineKeyboardButton(
                text="❓ 使用帮助",
                callback_data="help",
            ),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def build_letters_keyboard(
    channel_key: str, letters: list[str]
) -> InlineKeyboardMarkup:
    """构建拼音首字母选择键盘"""
    buttons = []
    # 每行放 4 个字母按钮
    row = []
    for letter in letters:
        row.append(
            InlineKeyboardButton(
                text=letter,
                callback_data=encode_callback("menu", ch=channel_key, action="list", letter=letter, p="0"),
            )
        )
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # 底部：搜索更多 + 返回主菜单
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔍 搜索更多",
                callback_data="search_more",
            ),
            InlineKeyboardButton(
                text="🏠 返回主菜单",
                callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
            ),
        ]
    )
    return InlineKeyboardMarkup(buttons)


def build_resource_list_keyboard(
    channel_key: str,
    letter: str,
    resources: list[dict],
    page: int,
    total: int,
    page_size: int = PAGE_SIZE,
) -> InlineKeyboardMarkup:
    """构建资源列表键盘"""
    total_pages = (total + page_size - 1) // page_size
    buttons = []

    # 资源按钮：每行 1 个
    for i, res in enumerate(resources):
        idx = page * page_size + i + 1
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{idx}. {res['display_title']}",
                    callback_data=encode_callback(
                        "res", id=str(res["id"]),
                        ret=encode_callback("menu", ch=channel_key, action="list", letter=letter, p=str(page)),
                    ),
                )
            ]
        )

    # 翻页行
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅ 上一页",
                callback_data=encode_callback(
                    "menu", ch=channel_key, action="list", letter=letter, p=str(page - 1)
                ),
            )
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="➡ 下一页",
                callback_data=encode_callback(
                    "menu", ch=channel_key, action="list", letter=letter, p=str(page + 1)
                ),
            )
        )
    if nav_row:
        buttons.append(nav_row)

    # 底部：搜索更多 + 返回字母
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔍 搜索更多",
                callback_data="search_more",
            ),
            InlineKeyboardButton(
                text="⬅ 返回字母",
                callback_data=encode_callback("menu", ch=channel_key, action="letters", p="0"),
            ),
        ]
    )
    # 返回主菜单
    buttons.append(
        [
            InlineKeyboardButton(
                text="🏠 返回主菜单",
                callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


def build_resource_detail_keyboard(
    message_link: str, return_callback: str
) -> InlineKeyboardMarkup:
    """构建资源详情键盘"""
    buttons = [
        [
            InlineKeyboardButton(text="🔗 跳转到频道消息", url=message_link)
        ],
        [
            InlineKeyboardButton(
                text="⬅ 返回列表",
                callback_data=return_callback,
            ),
            InlineKeyboardButton(
                text="🔍 搜索更多",
                callback_data="search_more",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🏠 返回主菜单",
                callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
            )
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def build_search_results_keyboard(
    query_encoded: str, results: list[dict], page: int, total: int, page_size: int = PAGE_SIZE
) -> InlineKeyboardMarkup:
    """构建搜索结果键盘"""
    total_pages = (total + page_size - 1) // page_size
    buttons = []

    for i, res in enumerate(results):
        idx = page * page_size + i + 1
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{idx}. [{CHANNELS.get(res['channel_key'], {}).get('emoji', '')}] {res['display_title']}",
                    callback_data=encode_callback(
                        "res",
                        id=str(res["id"]),
                        ret=encode_callback("search", q=query_encoded, p=str(page)),
                    ),
                )
            ]
        )

    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅ 上页",
                callback_data=encode_callback("search", q=query_encoded, p=str(page - 1)),
            )
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="下页 ➡",
                callback_data=encode_callback("search", q=query_encoded, p=str(page + 1)),
            )
        )
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="🏠 返回主菜单",
                callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


def build_pagination_row(
    prefix: str, page: int, total: int, page_size: int = PAGE_SIZE, **extra
) -> list[InlineKeyboardButton]:
    """构造分页按钮行"""
    total_pages = (total + page_size - 1) // page_size
    row = []
    if page > 0:
        row.append(
            InlineKeyboardButton(
                text="⬅ 上一页",
                callback_data=encode_callback(prefix, p=str(page - 1), **extra),
            )
        )
    row.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="noop",
        )
    )
    if page < total_pages - 1:
        row.append(
            InlineKeyboardButton(
                text="➡ 下一页",
                callback_data=encode_callback(prefix, p=str(page + 1), **extra),
            )
        )
    return row
