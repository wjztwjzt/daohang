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
    encode_callback,
    decode_callback,
    build_message_link,
    build_main_menu_keyboard,
    build_letters_keyboard,
    build_resource_list_keyboard,
    build_resource_detail_keyboard,
)
from config import CHANNELS, PAGE_SIZE


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令 — 显示主菜单"""
    total = get_total_count()
    welcome = (
        f"欢迎使用资源导航机器人！\n"
        f"已收录 {total} 条资源\n\n"
        f"请选择功能："
    )
    await update.message.reply_text(
        welcome,
        reply_markup=build_main_menu_keyboard(),
    )


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理所有 menu| 前缀的回调 — 路由到具体处理函数"""
    query = update.callback_query
    await query.answer()
    data = decode_callback(query.data)

    action = data.get("action", "")
    channel_key = data.get("ch", "")

    if channel_key == "__home__":
        await _show_main_menu(query)
        return

    channel = CHANNELS.get(channel_key)
    if not channel:
        await query.edit_message_text("频道不存在，请返回主菜单。")
        return

    if action == "letters":
        await _show_letters(query, channel)
    elif action == "list":
        letter = data.get("letter", "A")
        page = int(data.get("p", "0"))
        await _show_resource_list(query, channel, letter, page)
    else:
        await _show_main_menu(query)


async def handle_res_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 res| 前缀的回调 — 显示资源详情"""
    query = update.callback_query
    await query.answer()
    data = decode_callback(query.data)

    resource_id = int(data.get("id", "0"))
    return_callback = data.get("ret", "")

    res = get_resource_by_id(resource_id)
    if not res:
        await query.edit_message_text("该资源已不存在，请返回主菜单。")
        return

    channel = CHANNELS.get(res["channel_key"], {})
    text = (
        f"{channel.get('emoji', '📺')} {res['display_title']}\n"
        f"📁 频道：{channel.get('name', '未知')}\n"
        f"📅 收录时间：{res['created_at'] or '未知'}"
    )
    await query.edit_message_text(
        text,
        reply_markup=build_resource_detail_keyboard(
            message_link=res["message_link"],
            return_callback=return_callback or encode_callback("menu", ch="__home__", action="main", p="0"),
        ),
    )


async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """监听频道新消息，自动入库"""
    msg = update.channel_post
    if not msg:
        return

    chat_id = msg.chat_id
    from config import get_channel_by_id

    channel = get_channel_by_id(chat_id)
    if not channel:
        return

    # 提取消息文本
    msg_text = msg.text or msg.caption or ""
    if not msg_text.strip():
        return

    message_link = build_message_link(chat_id, msg.message_id)
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


# ── 内部辅助 ──

async def _show_main_menu(query) -> None:
    total = get_total_count()
    await query.edit_message_text(
        f"已收录 {total} 条资源\n\n请选择功能：",
        reply_markup=build_main_menu_keyboard(),
    )


async def _show_letters(query, channel: dict) -> None:
    letters = get_pinyin_letters(channel["key"])
    if not letters:
        await query.edit_message_text(
            f"{channel['emoji']} {channel['name']} — 暂无资源\n"
            f"请先收集频道数据，或使用搜索功能。",
            reply_markup=build_letters_keyboard(channel["key"], []),
        )
        return

    await query.edit_message_text(
        f"{channel['emoji']} {channel['name']} — 按拼音首字母查找\n"
        f"共收录 {get_total_count(channel['key'])} 条资源，请选择首字母：",
        reply_markup=build_letters_keyboard(channel["key"], letters),
    )


async def _show_resource_list(query, channel: dict, letter: str, page: int) -> None:
    resources, total = get_resources_by_letter(channel["key"], letter, page)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    if not resources:
        await query.edit_message_text(
            f"{channel['emoji']} {channel['name']} > {letter} — 暂无资源",
            reply_markup=build_letters_keyboard(channel["key"], get_pinyin_letters(channel["key"])),
        )
        return

    await query.edit_message_text(
        f"{channel['emoji']} {channel['name']} > {letter}（第 {page + 1}/{total_pages} 页）",
        reply_markup=build_resource_list_keyboard(channel["key"], letter, resources, page, total),
    )
