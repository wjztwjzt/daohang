from telegram import Update
from telegram.ext import ContextTypes
from database import (
    get_pinyin_letters,
    get_resources_by_letter,
    get_resource_by_id,
    get_total_count,
)
from indexer import index_message
from utils import (
    cb,
    parse_cb,
    build_message_link,
    build_reply_main_menu,
    build_inline_main_menu,
    build_letters_keyboard,
    build_resource_list_keyboard,
    build_resource_detail_keyboard,
)
from config import CHANNELS, PAGE_SIZE

# ── 底部按钮文字 → channel_key 映射 ──
_MAIN_BTN_MAP = {
    f"{ch['emoji']} {ch['name']}": ch["key"]
    for ch in CHANNELS.values()
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start — 发送底部键盘 + 欢迎消息"""
    total = get_total_count()
    context.user_data.clear()

    await update.message.reply_text(
        f"已收录 {total} 条资源\n\n"
        f"🔍 直接输入名字即可搜索\n"
        f"📂 点击下方按钮浏览频道资源",
        reply_markup=build_reply_main_menu(),
    )


async def handle_reply_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理用户点击底部键盘发来的文字"""
    text = update.message.text.strip()

    # 三个频道按钮
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

    # 其他可能是搜索关键词
    from handlers.search import handle_text_search
    await handle_text_search(update, context)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 m| 前缀回调 — 菜单导航"""
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

    if len(parts) == 3 and parts[2] == "a":
        # m|chan|a → 字母选择
        await _show_letters(query, channel)
    elif len(parts) >= 4 and parts[2] == "l":
        # m|chan|l|letter|page
        letter = parts[3] if len(parts) > 3 else "A"
        page = int(parts[4]) if len(parts) > 4 else 0
        await _show_resource_list(query, context, channel, letter, page)


async def handle_res_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 r|{id} 回调 — 资源详情"""
    query = update.callback_query
    await query.answer()
    parts = parse_cb(query.data)

    resource_id = int(parts[1])
    res = get_resource_by_id(resource_id)
    if not res:
        await query.edit_message_text("该资源已不存在。", reply_markup=build_inline_main_menu())
        return

    channel = CHANNELS.get(res["channel_key"], {})
    text = (
        f"{channel.get('emoji', '📺')} {res['display_title']}\n"
        f"📁 频道：{channel.get('name', '未知')}\n"
        f"📅 收录时间：{res['created_at'] or '未知'}"
    )
    await query.edit_message_text(
        text,
        reply_markup=build_resource_detail_keyboard(res["message_link"]),
    )


async def handle_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 back 回调 — 返回上一级（从 user_data['nav'] 恢复）"""
    query = update.callback_query
    await query.answer()

    nav = context.user_data.get("nav")
    if nav:
        # nav 格式: ("list", channel_key, letter, page) 或 ("letters", channel_key)
        nav_type = nav[0]
        if nav_type == "list":
            _, ch, letter, page = nav
            channel = CHANNELS.get(ch)
            if channel:
                await _show_resource_list(query, context, channel, letter, page)
                return
        elif nav_type == "letters":
            _, ch = nav
            channel = CHANNELS.get(ch)
            if channel:
                await _show_letters(query, channel)
                return
        elif nav_type == "search":
            _, query_key, page = nav
            from handlers.search import _show_search_results
            await _show_search_results(query, context, query_key, page)
            return

    # 回退：返回主菜单
    await _show_home(query, context)


async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """监听频道新消息，自动入库"""
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


# ── 内部辅助：发送新消息（用于 ReplyKeyboard 响应） ──

async def _send_letters(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_key: str) -> None:
    """发送字母选择页（新消息 + 内联按钮）"""
    channel = CHANNELS[channel_key]
    letters = get_pinyin_letters(channel_key)
    if not letters:
        await update.message.reply_text(
            f"{channel['emoji']} {channel['name']} — 暂无资源",
            reply_markup=build_letters_keyboard(channel_key, []),
        )
        return

    context.user_data["nav"] = ("letters", channel_key)
    await update.message.reply_text(
        f"{channel['emoji']} {channel['name']} — 按拼音首字母查找\n"
        f"共 {get_total_count(channel_key)} 条资源，请点击字母：",
        reply_markup=build_letters_keyboard(channel_key, letters),
    )


async def _send_search_more(update: Update) -> None:
    from config import SEARCH_GROUP_LINK, SEARCH_GROUP_NAME
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup as IM
    await update.message.reply_text(
        "🔍 搜索更多资源\n\n"
        "如果在机器人中找不到想要的资源，\n请加入搜索群，在群中发送消息即可激活搜索。",
        reply_markup=IM([
            [InlineKeyboardButton(text=f"📢 加入{SEARCH_GROUP_NAME}", url=SEARCH_GROUP_LINK)],
        ]),
    )


async def _send_complaint_menu(update: Update) -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup as IM
    await update.message.reply_text(
        "💬 投诉建议\n\n"
        "如有问题或建议，请直接联系 @shuangjiad_bot",
        reply_markup=IM([
            [InlineKeyboardButton("💬 联系 @shuangjiad_bot", url="https://t.me/shuangjiad_bot")],
        ]),
    )


async def _send_help(update: Update) -> None:
    await update.message.reply_text(
        "📖 使用帮助\n\n"
        "🔍 搜索：直接输入动漫名或拼音即可搜索\n\n"
        "📂 菜单：点击底部频道按钮 → 拼音首字母 → 资源列表 → 跳转频道消息\n\n"
        "💬 投诉建议：点击底部按钮提交反馈\n\n"
        "🔍 搜索更多：加入搜索群获取帮助",
        reply_markup=build_reply_main_menu(),
    )


# ── 内部辅助：编辑已有消息（用于 InlineKeyboard 回调） ──

async def _show_home(query, context) -> None:
    total = get_total_count()
    context.user_data.pop("nav", None)
    await query.edit_message_text(
        f"已收录 {total} 条资源\n\n🔍 直接输入名字即可搜索",
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


async def _show_resource_list(query, context, channel: dict, letter: str, page: int) -> None:
    resources, total = get_resources_by_letter(channel["key"], letter, page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    if not resources:
        await query.edit_message_text(
            f"{channel['emoji']} {channel['name']} > {letter} — 暂无资源",
            reply_markup=build_letters_keyboard(channel["key"], get_pinyin_letters(channel["key"])),
        )
        return

    # 保存导航状态供"返回"使用
    context.user_data["nav"] = ("list", channel["key"], letter, page)

    await query.edit_message_text(
        f"{channel['emoji']} {channel['name']} > {letter}（第 {page + 1}/{total_pages} 页）",
        reply_markup=build_resource_list_keyboard(channel["key"], letter, resources, page, total),
    )
