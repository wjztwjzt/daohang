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

# Handler imports
from handlers.menu import (
    start,
    handle_menu_callback,
    handle_res_callback,
    on_channel_post,
)
from handlers.search import handle_text_search, handle_search_callback
from handlers.complaint import handle_complaint_callback
from handlers.search_more import handle_search_more


async def handle_help(update: Update, context) -> None:
    """处理使用帮助按钮"""
    query = update.callback_query
    await query.answer()
    from utils import encode_callback
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    await query.edit_message_text(
        "📖 使用帮助\n\n"
        "🔍 搜索资源：直接输入动漫名或拼音即可搜索。\n\n"
        "📂 菜单导航：点击频道按钮 → 选择拼音首字母 → 浏览资源列表 → 点击跳转到频道消息。\n\n"
        "💬 投诉建议：如有问题或建议，点击投诉建议按钮提交。\n\n"
        "🔍 搜索更多：如果找不到想要的资源，可加入搜索群或使用搜索机器人。\n\n"
        "📌 提示：每个视频资源都关联了频道中的消息链接，点击即可跳转观看。",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🏠 返回主菜单",
                    callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
                ),
            ]
        ]),
    )


async def handle_noop(update: Update, context) -> None:
    """noop 回调 — 不做任何操作"""
    await update.callback_query.answer()


async def post_init(app: Application) -> None:
    """Bot 启动完成后执行的初始化"""
    print(f"Bot @{app.bot.username} 启动成功！")


def main() -> None:
    # 初始化数据库
    print("初始化数据库...")
    init_db()
    print("数据库初始化完成。")

    # 构建 Application
    builder = ApplicationBuilder().token(BOT_TOKEN)
    if PROXY:
        builder = builder.proxy(PROXY)
    builder = builder.post_init(post_init)
    application = builder.build()

    # ── 注册 Handler ──

    # /start 命令
    application.add_handler(CommandHandler("start", start))

    # 频道新消息监听
    application.add_handler(MessageHandler(
        filters.UpdateType.CHANNEL_POST,
        on_channel_post,
    ))

    # 回调：menu| 前缀 → 菜单导航
    application.add_handler(CallbackQueryHandler(
        handle_menu_callback,
        pattern=r"^menu\|",
    ))

    # 回调：res| 前缀 → 资源详情
    application.add_handler(CallbackQueryHandler(
        handle_res_callback,
        pattern=r"^res\|",
    ))

    # 回调：search| 前缀 → 搜索结果翻页
    application.add_handler(CallbackQueryHandler(
        handle_search_callback,
        pattern=r"^search\|",
    ))

    # 回调：complaint| 前缀 → 投诉建议
    application.add_handler(CallbackQueryHandler(
        handle_complaint_callback,
        pattern=r"^complaint",
    ))

    # 回调：search_more
    application.add_handler(CallbackQueryHandler(
        handle_search_more,
        pattern=r"^search_more$",
    ))

    # 回调：help
    application.add_handler(CallbackQueryHandler(
        handle_help,
        pattern=r"^help$",
    ))

    # 回调：noop（无操作）
    application.add_handler(CallbackQueryHandler(
        handle_noop,
        pattern=r"^noop$",
    ))

    # 文字消息 → 搜索（放在最后，优先级最低）
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_search,
    ))

    # 启动轮询
    print("Bot 启动中...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot 已停止。")
        sys.exit(0)
