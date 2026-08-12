from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import SEARCH_GROUP_LINK


async def handle_search_more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        f"🔍 点击下方链接加入搜索群获取更多资源 👇\n{SEARCH_GROUP_LINK}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="📢 加入搜索群", url=SEARCH_GROUP_LINK)],
            [InlineKeyboardButton(text="🏠 返回主菜单", callback_data="m|__home__")],
        ]),
    )
