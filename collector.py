"""
历史消息收集脚本 — 使用 Telethon 一次性收集三个频道的历史消息。

用法:
  python collector.py                     # 收集所有频道
  python collector.py --channel ranhun    # 只收集指定频道
  python collector.py --limit 500         # 每个频道最多收集 500 条
  python collector.py --resume            # 断点续传（跳过已存在的数据）
"""
import asyncio
import argparse
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

from config import (
    API_ID,
    API_HASH,
    PHONE,
    PASSWORD,
    SESSION_NAME,
    CHANNELS,
    PROXY,
    DATA_DIR,
)
from database import init_db, resource_exists
from indexer import index_message
from utils import build_message_link


async def collect_channel(
    client: TelegramClient,
    channel: dict,
    limit: int = 0,
    resume: bool = False,
) -> int:
    """
    收集单个频道的历史消息。
    返回本次新入库的数量。
    """
    channel_id = channel["id"]
    channel_name = channel["name"]
    channel_key = channel["key"]

    print(f"\n{'='*50}")
    print(f"开始收集: {channel_name} (ID: {channel_id})")
    print(f"{'='*50}")

    new_count = 0
    skipped_count = 0
    error_count = 0

    try:
        entity = await client.get_entity(channel_id)
    except Exception as e:
        print(f"  ❌ 无法访问频道: {e}")
        return 0

    try:
        messages = client.iter_messages(
            entity,
            limit=limit if limit > 0 else None,
            wait_time=1.0,  # 请求间隔，避免 FloodWait
        )
    except Exception as e:
        print(f"  ❌ 遍历消息失败: {e}")
        return 0

    async for msg in messages:
        try:
            if not isinstance(msg, Message):
                continue

            # 跳过非资源类消息（无文本且无媒体）
            msg_text = msg.text or getattr(msg, 'caption', None) or ""
            if not msg_text.strip():
                continue

            # 断点续传：跳过已存在的
            if resume and resource_exists(channel_key, msg.id):
                skipped_count += 1
                if skipped_count % 100 == 0:
                    print(f"  ⏭ 已跳过 {skipped_count} 条已有数据...")
                continue

            # 判断文件类型
            file_type = ""
            if msg.video:
                file_type = "video"
            elif msg.document:
                file_type = "document"
            elif msg.photo:
                file_type = "photo"

            message_link = build_message_link(channel_id, msg.id)

            success = index_message(
                channel_key=channel_key,
                message_id=msg.id,
                msg_text=msg_text,
                message_link=message_link,
                file_type=file_type,
            )

            if success:
                new_count += 1
            else:
                skipped_count += 1

            # 进度提示
            if new_count % 50 == 0 and new_count > 0:
                print(f"  ✅ 已收录 {new_count} 条新资源...")

        except FloodWaitError as e:
            print(f"  ⚠️ FloodWait: 等待 {e.seconds} 秒...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ⚠️ 处理消息出错: {e}")
            continue

    print(f"\n  📊 {channel_name} 收集完成:")
    print(f"     新增: {new_count}")
    print(f"     跳过: {skipped_count}")
    if error_count:
        print(f"     错误: {error_count}")

    return new_count


async def main(args: argparse.Namespace) -> None:
    # 初始化数据库
    init_db()

    # 检查配置
    if not API_ID or not API_HASH:
        print("❌ 错误: 请先在 .env 中配置 API_ID 和 API_HASH")
        print("   申请地址: https://my.telegram.org/apps")
        sys.exit(1)

    # 选择目标频道
    if args.channel:
        target = args.channel
        if target not in CHANNELS:
            print(f"❌ 未知频道 '{target}'，可选: {', '.join(CHANNELS.keys())}")
            sys.exit(1)
        targets = [CHANNELS[target]]
    else:
        targets = [ch for ch in CHANNELS.values() if ch["id"]]

    if not targets:
        print("❌ 没有配置有效的频道 ID，请检查 .env 中频道配置。")
        sys.exit(1)

    print("目标频道:")
    for ch in targets:
        print(f"  - {ch['emoji']} {ch['name']} (ID: {ch['id']})")

    # 连接 Telethon
    proxy = None
    if PROXY:
        proxy = {
            "proxy_type": PROXY[0],
            "addr": PROXY[1],
            "port": PROXY[2],
        }

    client = TelegramClient(
        str(DATA_DIR / SESSION_NAME),
        API_ID,
        API_HASH,
        proxy=proxy,
    )

    print("\n连接 Telegram...")
    await client.start(phone=PHONE, password=PASSWORD or None)
    print("✅ 登录成功！")

    # 收集数据
    total_new = 0
    for channel in targets:
        new = await collect_channel(
            client,
            channel,
            limit=args.limit,
            resume=args.resume,
        )
        total_new += new

    print(f"\n{'='*50}")
    print(f"🎉 全部完成！共新增 {total_new} 条资源。")
    print(f"{'='*50}")

    await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="收集频道历史消息")
    parser.add_argument(
        "--channel", "-c",
        type=str,
        default="",
        help="指定频道 key（ranhun/meirifuli/youxiudianshiju）",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="限制收集条数（0 表示不限）",
    )
    parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="断点续传模式，跳过已入库的消息",
    )
    args = parser.parse_args()

    asyncio.run(main(args))
