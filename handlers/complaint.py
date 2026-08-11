from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import insert_complaint
from utils import encode_callback


async def handle_complaint_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理投诉建议相关的回调"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "complaint|start":
        await query.edit_message_text(
            "请选择反馈类型：",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📝 提交建议", callback_data="complaint|type|suggestion"),
                    InlineKeyboardButton("⚠️ 投诉举报", callback_data="complaint|type|complaint"),
                ],
                [
                    InlineKeyboardButton(
                        "🏠 返回主菜单",
                        callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
                    ),
                ],
            ]),
        )

    elif data.startswith("complaint|type|"):
        complaint_type = data.split("|")[2]
        type_label = "建议" if complaint_type == "suggestion" else "投诉"
        context.user_data["awaiting_complaint"] = complaint_type
        await query.edit_message_text(
            f"请输入您的{type_label}内容（文字消息）：\n\n"
            f"发送 /cancel 取消操作。",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "取消",
                        callback_data="complaint|cancel",
                    ),
                ]
            ]),
        )

    elif data == "complaint|cancel":
        context.user_data.pop("awaiting_complaint", None)
        await query.edit_message_text(
            "已取消。",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🏠 返回主菜单",
                        callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
                    ),
                ]
            ]),
        )


async def handle_complaint_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理投诉建议的文字输入"""
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
        f"✅ 已收到您的{type_label}，我们会尽快处理！感谢反馈。",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🏠 返回主菜单",
                    callback_data=encode_callback("menu", ch="__home__", action="main", p="0"),
                ),
            ]
        ]),
    )
