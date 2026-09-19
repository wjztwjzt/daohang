from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import COMPLAINT_BOT_LINK


async def handle_complaint_callback(update: Update, context) -> None:
    """提交投稿 — 引导用户联系客服机器人提交资源"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        f"📤 点击下方链接提交投稿 👇\n{COMPLAINT_BOT_LINK}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 提交投稿", url=COMPLAINT_BOT_LINK)],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="m|__home__")],
        ]),
    )
