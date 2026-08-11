import re
import jieba
from pypinyin import lazy_pinyin, Style
from database import insert_resource
from config import CHANNELS


def extract_title(msg_text: str) -> tuple[str, str]:
    """
    从消息文本中提取名字和显示标题。

    输入: "🎬 光阴之外第33集\n📖 跳过片头 2:10\n📺 状态：4K更新中\n🏷 #光阴之外"
    输出: ("光阴之外", "光阴之外 第33集")
    """
    text = msg_text.strip() if msg_text else ""

    # 优先从 #hashtag 提取名字
    tag_match = re.search(r"#(\S+)", text)
    if tag_match:
        title = tag_match.group(1)
    else:
        # 从第一行提取
        first_line = text.split("\n")[0]
        # 去掉行首 emoji 类字符
        cleaned = re.sub(r"^[^\w一-鿿#]+", "", first_line).strip()
        # 去掉 "第X集" 及后面的内容
        title = re.sub(r"第\d+集.*$", "", cleaned).strip()
        if not title:
            title = cleaned

    # display_title: 第一行去掉行首符号
    first_line = text.split("\n")[0]
    display_title = re.sub(r"^[^\w一-鿿]+", "", first_line).strip()
    if not display_title:
        display_title = title

    return title, display_title


def get_pinyin_info(title: str) -> tuple[str, str]:
    """返回 (全拼无空格, 首字母大写)"""
    full = "".join(lazy_pinyin(title, style=Style.NORMAL))
    first_letters = "".join(lazy_pinyin(title, style=Style.FIRST_LETTER))
    first = first_letters[0].upper() if first_letters and first_letters[0].isalpha() else "#"
    return full, first


def index_message(
    channel_key: str,
    message_id: int,
    msg_text: str,
    message_link: str,
    file_type: str = "",
) -> bool:
    """
    索引一条消息：提取标题 → 计算拼音 → 写入数据库。
    返回 True 表示新增，False 表示已存在或失败。
    """
    orig_title, display_title = extract_title(msg_text)
    if not orig_title:
        return False

    # 拼音从原始标题计算
    pinyin, pinyin_first = get_pinyin_info(orig_title)

    # jieba 分词后空格连接，存入 FTS5 以支持中文搜索
    title_fts = " ".join(jieba.cut_for_search(orig_title))

    result = insert_resource(
        channel_key=channel_key,
        message_id=message_id,
        title=title_fts,
        display_title=display_title,
        pinyin=pinyin,
        pinyin_first=pinyin_first,
        message_link=message_link,
        file_type=file_type,
    )
    return result is not None
