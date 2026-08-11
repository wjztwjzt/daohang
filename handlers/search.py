import jieba
from telegram import Update
from telegram.ext import ContextTypes
from database import search_all_resources, get_resource_by_id
from utils import (
    encode_callback,
    decode_callback,
    encode_search_query,
    decode_search_query,
    build_search_results_keyboard,
    build_resource_detail_keyboard,
)
from config import SEARCH_GROUP_LINK, SEARCH_GROUP_NAME, PAGE_SIZE


async def handle_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理用户直接输入的文字 — 执行搜索"""
    query_text = update.message.text.strip()
    if not query_text:
        return

    # 检查是否在投诉建议输入状态
    if context.user_data.get("awaiting_complaint"):
        from handlers.complaint import handle_complaint_text
        await handle_complaint_text(update, context)
        return

    # jieba 分词 + FTS5 查询
    tokens = list(jieba.cut_for_search(query_text))
    # 去重 + 拼接 FTS5 查询（每个词加 * 前缀匹配）
    unique_tokens = list(dict.fromkeys(tokens))
    fts_query = " ".join(f"{t}*" for t in unique_tokens if t.strip())

    if not fts_query:
        await update.message.reply_text("请输入有效的搜索关键词。")
        return

    results, total = search_all_resources(fts_query, 0)

    if not results:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        await update.message.reply_text(
            f"未找到与「{query_text}」相关的资源。\n\n"
            f"💡 建议：\n"
            f"1. 尝试更短的关键词\n"
            f"2. 尝试拼音搜索\n"
            f"3. 加入搜索群获取帮助",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📢 加入{SEARCH_GROUP_NAME}", url=SEARCH_GROUP_LINK)]
            ]),
        )
        # 缓存搜索结果供翻页使用（保留原搜索词用于更精确的翻页）
        return

    # 缓存搜索结果
    query_encoded = encode_search_query(query_text)
    cache_key = f"search_{query_encoded}"
    context.user_data[cache_key] = {
        "fts_query": fts_query,
        "total": total,
        "query_text": query_text,
    }

    # 发送搜索结果（新消息，非编辑）
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    await update.message.reply_text(
        f"🔍 搜索「{query_text}」— 共 {total} 条结果（第 1/{total_pages} 页）",
        reply_markup=build_search_results_keyboard(query_encoded, results, 0, total),
    )


async def handle_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 search| 前缀的回调 — 搜索结果翻页 + 跳转资源详情"""
    query = update.callback_query
    await query.answer()
    data = decode_callback(query.data)

    query_encoded = data.get("q", "")
    page = int(data.get("p", "0"))

    cache_key = f"search_{query_encoded}"
    cached = context.user_data.get(cache_key, {})

    if not cached:
        await query.edit_message_text("搜索结果已过期，请重新搜索。")
        return

    fts_query = cached["fts_query"]
    total = cached["total"]

    results, _ = search_all_resources(fts_query, page)
    if not results:
        await query.edit_message_text("翻页数据为空，请重新搜索。")
        return

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    await query.edit_message_text(
        f"🔍 搜索「{cached['query_text']}」— 共 {total} 条结果（第 {page + 1}/{total_pages} 页）",
        reply_markup=build_search_results_keyboard(query_encoded, results, page, total),
    )
