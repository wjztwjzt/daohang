from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import (
    get_pinyin_letters,
    get_base_titles,
    get_resources_by_base_title,
    get_total_count,
)
from indexer import index_message
from utils import (
    cb,
    parse_cb,
    hash_title,
    build_message_link,
    build_reply_main_menu,
    build_inline_main_menu,
    build_letters_keyboard,
    build_anime_list_keyboard,
    build_episode_list_keyboard,
)
from config import CHANNELS, PAGE_SIZE

_MAIN_BTN_MAP = {
    f"{ch['emoji']} {ch['name']}": ch["key"]
    for ch in CHANNELS.values()
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    total = get_total_count()
    context.user_data.clear()
    await update.message.reply_text(
        f"已收录 {total} 条资源\n\n"
        f"🔍 直接输入名字即可搜索\n"
        f"📂 点击下方按钮浏览频道资源",
        reply_markup=build_reply_main_menu(),
    )


async def handle_reply_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    channel_key = _MAIN_BTN_MAP.get(text)
    if channel_key:
        await _send_letters(update, context, channel_key)
        return
    if text == "🔍 搜索更多":
        await _send_search_more(update)
        return
    if text == "💬 投诉建议":
        await _send_complaint_menu(update)
        return
    if text == "❓ 使用帮助":
        await _send_help(update)
        return
    from handlers.search import handle_text_search
    await handle_text_search(update, context)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 m| 前缀回调"""
    query = update.callback_query
    await query.answer()
    parts = parse_cb(query.data)  # ["m", channel_key, action, ...]

    if len(parts) < 2:
        return

    channel_key = parts[1]

    if channel_key == "__home__":
        await _show_home(query, context)
        return

    channel = CHANNELS.get(channel_key)
    if not channel:
        return

    action = parts[2] if len(parts) > 2 else ""

    if action == "a":
        # m|chan|a → 字母选择
        await _show_letters(query, channel)

    elif action == "l":
        # m|chan|l|letter|page → 动漫名列表
        letter = parts[3] if len(parts) > 3 else "A"
        page = int(parts[4]) if len(parts) > 4 else 0
        await _show_anime_list(query, context, channel, letter, page)

    elif action == "t":
        # m|chan|t|letter|title_hash|page → 集数列表
        real_letter = parts[3] if len(parts) > 3 else "A"
        title_hash = parts[4] if len(parts) > 4 else ""
        real_page = int(parts[5]) if len(parts) > 5 else 0
        real_base = context.user_data.get("_bt", {}).get(title_hash, "")
        if not real_base:
            await query.edit_message_text("数据已过期，请重新浏览。",
                                           reply_markup=build_inline_main_menu())
            return
        await _show_episode_list(query, context, channel, real_letter, real_base, real_page)


async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.channel_post
    if not msg:
        return

    from config import get_channel_by_id
    channel = get_channel_by_id(msg.chat_id)
    if not channel:
        return

    msg_text = msg.text or getattr(msg, "caption", None) or ""
    if not msg_text.strip():
        return

    message_link = build_message_link(msg.chat_id, msg.message_id)
    file_type = ""
    if msg.video:
        file_type = "video"
    elif msg.document:
        file_type = "document"
    elif msg.photo:
        file_type = "photo"

    success = index_message(
        channel_key=channel["key"],
        message_id=msg.message_id,
        msg_text=msg_text,
        message_link=message_link,
        file_type=file_type,
    )
    if success:
        print(f"[新资源] {channel['name']} - {msg_text.split(chr(10))[0][:50]}")


# ── ReplyKeyboard 响应（发送新消息） ──

async def _send_letters(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_key: str) -> None:
    channel = CHANNELS[channel_key]
    letters = get_pinyin_letters(channel_key)
    if not letters:
        await update.message.reply_text(
            f"{channel['emoji']} {channel['name']} — 暂无资源",
            reply_markup=build_letters_keyboard(channel_key, []),
        )
        return
    await update.message.reply_text(
        f"{channel['emoji']} {channel['name']} — 按拼音首字母查找\n"
        f"共 {get_total_count(channel_key)} 条资源，请点击字母：",
        reply_markup=build_letters_keyboard(channel_key, letters),
    )


async def _send_search_more(update: Update) -> None:
    from config import SEARCH_GROUP_LINK
    await update.message.reply_text(
        "🔍 点击下方按钮加入搜索群 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 加入搜索群", url=SEARCH_GROUP_LINK)]
        ]),
    )


async def _send_complaint_menu(update: Update) -> None:
    await update.message.reply_text(
        "💬 点击下方按钮联系客服 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 联系客服", url="https://t.me/shuangjiad_bot")]
        ]),
    )


async def _send_help(update: Update) -> None:
    await update.message.reply_text(
        "📖 使用帮助\n\n"
        "🔍 搜索：直接输入动漫名或拼音即可搜索\n\n"
        "📂 菜单：底部频道按钮 → 拼音首字母 → 动漫名 → 集数链接\n\n"
        "💬 投诉建议：点击底部按钮联系客服",
        reply_markup=build_reply_main_menu(),
    )


# ── 编辑已有消息（InlineKeyboard 回调） ──

async def _show_home(query, context) -> None:
    context.user_data.pop("nav", None)
    await query.edit_message_text(
        f"已收录 {get_total_count()} 条资源\n\n🔍 直接输入名字即可搜索",
        reply_markup=build_inline_main_menu(),
    )


async def _show_letters(query, channel: dict) -> None:
    letters = get_pinyin_letters(channel["key"])
    if not letters:
        await query.edit_message_text(
            f"{channel['emoji']} {channel['name']} — 暂无资源",
            reply_markup=build_letters_keyboard(channel["key"], []),
        )
        return
    await query.edit_message_text(
        f"{channel['emoji']} {channel['name']} — 按拼音首字母查找\n"
        f"共 {get_total_count(channel['key'])} 条资源，请点击字母：",
        reply_markup=build_letters_keyboard(channel["key"], letters),
    )


async def _show_anime_list(query, context, channel: dict, letter: str, page: int) -> None:
    """显示某字母下的动漫名列表"""
    titles, total = get_base_titles(channel["key"], letter, page)
    total_pages = max(1, (total + 20 - 1) // 20)

    if not titles:
        await query.edit_message_text(
            f"{channel['emoji']} {channel['name']} > {letter} — 暂无资源",
            reply_markup=build_letters_keyboard(channel["key"], get_pinyin_letters(channel["key"])),
        )
        return

    # 存储 hash→title 映射，避免 callback_data 超 64 字节
    bt_map = context.user_data.setdefault("_bt", {})
    for t in titles:
        bt_map[hash_title(t)] = t

    await query.edit_message_text(
        f"{channel['emoji']} {channel['name']} > {letter}（第 {page + 1}/{total_pages} 页）",
        reply_markup=build_anime_list_keyboard(channel["key"], letter, titles, page, total),
    )


async def _show_episode_list(query, context, channel: dict, letter: str, base_title: str, page: int) -> None:
    """显示某动漫的集数列表（URL 按钮直达频道消息）"""
    resources, total = get_resources_by_base_title(channel["key"], base_title, page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    if not resources:
        await query.edit_message_text(
            f"{channel['emoji']} {channel['name']} > {base_title} — 暂无资源",
            reply_markup=build_inline_main_menu(),
        )
        return

    # 确保 base_title 的 hash 存在（翻页按钮需要）
    context.user_data.setdefault("_bt", {})[hash_title(base_title)] = base_title

    await query.edit_message_text(
        f"{channel['emoji']} {channel['name']} > {base_title}（第 {page + 1}/{total_pages} 页）\n"
        f"点击集数直接跳转频道消息：",
        reply_markup=build_episode_list_keyboard(
            channel["key"], letter, base_title, resources, page, total),
    )
