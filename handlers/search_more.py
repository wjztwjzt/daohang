from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import SEARCH_GROUP_LINK, SEARCH_GROUP_NAME
from utils import encode_callback


async def handle_search_more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理搜索更多按钮 — 显示搜索群链接"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔍 搜索更多资源\n\n"
        "如果在机器人中找不到想要的资源，\n"
        "请加入搜索群，在群中发送消息即可激活搜索。",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"📢 加入{SEARCH_GROUP_NAME}",
                    url=SEARCH_GROUP_LINK,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 返回主菜单",
                    callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
                ),
            ],
        ]),
    )
