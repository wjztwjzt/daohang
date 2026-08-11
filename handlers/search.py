import hashlib
import jieba
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import search_all_resources, get_resource_by_id
from utils import (
    cb,
    parse_cb,
    build_search_results_keyboard,
    build_resource_detail_keyboard,
    build_inline_main_menu,
)
from config import SEARCH_GROUP_LINK, SEARCH_GROUP_NAME, PAGE_SIZE, CHANNELS


def _query_key(text: str) -> str:
    """将搜索词哈希为短 key"""
    return hashlib.md5(text.encode()).hexdigest()[:8]


async def handle_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """用户直接输入文字 → 搜索"""
    query_text = update.message.text.strip()
    if not query_text:
        return

    # 投诉输入状态
    if context.user_data.get("awaiting_complaint"):
        from handlers.complaint import handle_complaint_text
        await handle_complaint_text(update, context)
        return

    # jieba 分词 → FTS5 前缀匹配
    tokens = list(dict.fromkeys(jieba.cut_for_search(query_text)))
    fts_query = " ".join(f"{t}*" for t in tokens if t.strip())

    if not fts_query:
        await update.message.reply_text("请输入有效的搜索关键词。")
        return

    results, total = search_all_resources(fts_query, 0)

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

    # 缓存 FTS 查询信息
    context.user_data[f"s_{qkey}"] = {"fts": fts_query, "total": total, "text": query_text}
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

    results, _ = search_all_resources(cached["fts"], page)
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
