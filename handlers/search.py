import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import search_all_resources_fuzzy
from utils import (
    parse_cb,
    build_search_results_keyboard,
    build_inline_main_menu,
)
from config import SEARCH_GROUP_LINK, SEARCH_GROUP_NAME, PAGE_SIZE


def _query_key(text: str) -> str:
    """将搜索词哈希为短 key"""
    return hashlib.md5(text.encode()).hexdigest()[:8]


async def handle_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """用户直接输入文字 → 搜索（精确/前缀优先，模糊补充）"""
    query_text = update.message.text.strip()
    if not query_text:
        return

    results, total = search_all_resources_fuzzy(query_text, 0)

    if not results:
        await update.message.reply_text(
            f"未找到与「{query_text}」相关的资源。\n\n"
            f"💡 建议：尝试更短关键词 / 拼音搜索 / 加入搜索群",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📢 加入{SEARCH_GROUP_NAME}", url=SEARCH_GROUP_LINK)]
            ]),
        )
        return

    qkey = _query_key(query_text)

    # 缓存搜索词（翻页时重新执行模糊搜索）
    context.user_data[f"s_{qkey}"] = {"text": query_text, "total": total}
    context.user_data["nav"] = ("search", qkey, 0)

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    await update.message.reply_text(
        f"🔍「{query_text}」— 共 {total} 条（第 1/{total_pages} 页）",
        reply_markup=build_search_results_keyboard(qkey, results, 0, total),
    )


async def handle_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 s|{key}|{page} 回调 — 翻页 / 跳转资源"""
    query = update.callback_query
    await query.answer()
    parts = parse_cb(query.data)  # ["s", key, page]

    qkey = parts[1] if len(parts) > 1 else ""
    page = int(parts[2]) if len(parts) > 2 else 0

    await _show_search_results(query, context, qkey, page)


async def _show_search_results(query, context, qkey: str, page: int) -> None:
    cached = context.user_data.get(f"s_{qkey}")
    if not cached:
        await query.edit_message_text("搜索结果已过期，请重新搜索。",
                                       reply_markup=build_inline_main_menu())
        return

    results, _ = search_all_resources_fuzzy(cached["text"], page)
    if not results:
        await query.edit_message_text("翻页数据为空。",
                                       reply_markup=build_inline_main_menu())
        return

    total = cached["total"]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    context.user_data["nav"] = ("search", qkey, page)

    await query.edit_message_text(
        f"🔍「{cached['text']}」— 共 {total} 条（第 {page + 1}/{total_pages} 页）",
        reply_markup=build_search_results_keyboard(qkey, results, page, total),
    )
