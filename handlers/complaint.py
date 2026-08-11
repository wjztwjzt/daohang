from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import insert_complaint
from utils import build_reply_main_menu


async def handle_complaint_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "c|start":
        await query.edit_message_text(
            "请选择反馈类型：",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📝 提交建议", callback_data="c|t|suggestion"),
                    InlineKeyboardButton("⚠️ 投诉举报", callback_data="c|t|complaint"),
                ],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="m|__home__")],
            ]),
        )

    elif data.startswith("c|t|"):
        complaint_type = data.split("|")[2]
        type_label = "建议" if complaint_type == "suggestion" else "投诉"
        context.user_data["awaiting_complaint"] = complaint_type
        await query.edit_message_text(
            f"请输入您的{type_label}内容（文字消息）：\n\n发送 /cancel 取消操作。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("取消", callback_data="c|cancel")],
            ]),
        )

    elif data == "c|cancel":
        context.user_data.pop("awaiting_complaint", None)
        await query.edit_message_text(
            "已取消。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 返回主菜单", callback_data="m|__home__")],
            ]),
        )


async def handle_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    complaint_type = context.user_data.pop("awaiting_complaint", None)
    if not complaint_type:
        return

    content = update.message.text.strip()
    if not content:
        await update.message.reply_text("内容不能为空，请重新输入。")
        context.user_data["awaiting_complaint"] = complaint_type
        return

    user = update.effective_user
    insert_complaint(
        user_id=user.id,
        username=user.username or user.full_name or "",
        complaint_type=complaint_type,
        content=content,
    )

    type_label = "建议" if complaint_type == "suggestion" else "投诉"
    await update.message.reply_text(
        f"✅ 已收到您的{type_label}，我们会尽快处理！",
        reply_markup=build_reply_main_menu(),
    )
