from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import COMPLAINT_BOT_LINK, COMPLAINT_BOT_NAME


async def handle_complaint_callback(update: Update, context) -> None:
    """投诉建议 — 引导用户联系客服机器人"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        f"💬 点击下方链接联系客服 👇\n{COMPLAINT_BOT_LINK}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 联系 {COMPLAINT_BOT_NAME}", url=COMPLAINT_BOT_LINK)],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="m|__home__")],
        ]),
    )
