"""电报频道资源导航搜索机器人 — 入口"""
import sys
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import BOT_TOKEN, PROXY
from database import init_db

from handlers.menu import (
    start,
    handle_menu_callback,
    handle_reply_menu_text,
    on_channel_post,
)
from handlers.search import handle_text_search, handle_search_callback
from handlers.complaint import handle_complaint_callback
from handlers.search_more import handle_search_more


async def handle_help_cb(update: Update, context) -> None:
    """h 回调 — 使用帮助"""
    query = update.callback_query
    await query.answer()
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    await query.edit_message_text(
        "📖 使用帮助\n\n"
        "🔍 搜索：直接输入动漫名或拼音即可搜索\n\n"
        "📂 菜单：点击底部频道按钮 → 拼音首字母 → 资源列表 → 跳转频道消息\n\n"
        "💬 投诉建议：点击底部按钮提交反馈\n\n"
        "🔍 搜索更多：加入搜索群获取帮助",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="m|__home__")],
        ]),
    )


async def handle_text(update: Update, context) -> None:
    """文字消息入口：先检查是否底部按钮文字，否则走搜索"""
    text = update.message.text.strip()

    # 底部按钮文字
    menu_texts = {"🔥 燃魂动漫", "🎁 每日福利", "📺 优秀电视剧",
                  "🔍 搜索更多", "💬 投诉建议", "❓ 使用帮助"}
    if text in menu_texts:
        from handlers.menu import handle_reply_menu_text
        await handle_reply_menu_text(update, context)
        return

    # 否则走搜索
    await handle_text_search(update, context)


async def post_init(app: Application) -> None:
    print(f"Bot @{app.bot.username} 启动成功！")


def main() -> None:
    print("初始化数据库...")
    init_db()
    print("数据库初始化完成。")

    builder = ApplicationBuilder().token(BOT_TOKEN)
    if PROXY:
        builder = builder.proxy(PROXY)
    builder = builder.post_init(post_init)
    application = builder.build()

    # /start
    application.add_handler(CommandHandler("start", start))

    # 频道新消息
    application.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST, on_channel_post,
    ))

    # 回调：m| 前缀 → 菜单导航
    application.add_handler(CallbackQueryHandler(
        handle_menu_callback, pattern=r"^m\|",
    ))

    # 回调：s| 前缀 → 搜索结果翻页
    application.add_handler(CallbackQueryHandler(
        handle_search_callback, pattern=r"^s\|",
    ))

    # 回调：c| 前缀 → 投诉建议
    application.add_handler(CallbackQueryHandler(
        handle_complaint_callback, pattern=r"^c\|",
    ))

    # 回调：sm / h
    application.add_handler(CallbackQueryHandler(
        handle_search_more, pattern=r"^sm$",
    ))
    application.add_handler(CallbackQueryHandler(
        handle_help_cb, pattern=r"^h$",
    ))

    # 文字消息（按钮 → 菜单 / 其他 → 搜索）
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_text,
    ))

    print("Bot 启动中...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot 已停止。")
        sys.exit(0)
