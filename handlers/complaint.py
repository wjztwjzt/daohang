from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup


async def handle_complaint_callback(update: Update, context) -> None:
    """投诉建议 — 引导用户联系 @shuangjiad_bot"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💬 投诉建议\n\n"
        "如有问题或建议，请直接联系 @shuangjiad_bot",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 联系 @shuangjiad_bot", url="https://t.me/shuangjiad_bot")],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data="m|__home__")],
        ]),
    )
