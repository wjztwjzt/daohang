"""修复已有数据：从 display_title 重新提取标题 + 重算拼音"""
import re
import jieba
from pypinyin import lazy_pinyin, Style
from database import get_db
from utils import normalize_base_title


def fix_all() -> None:
    with get_db() as db:
        rows = db.execute("SELECT id, display_title FROM resources").fetchall()
        print(f"共 {len(rows)} 条数据，开始修复...")
        fixed = 0

        for r in rows:
            dt = r["display_title"]
            # 重新提取基础标题（去 hashtag + 去中英文集数后缀）
            new_title = normalize_base_title(dt)
            if not new_title:
                new_title = dt

            # 重算拼音
            full = "".join(lazy_pinyin(new_title, style=Style.NORMAL))
            first_letters = "".join(lazy_pinyin(new_title, style=Style.FIRST_LETTER))
            first = first_letters[0].upper() if first_letters and first_letters[0].isalpha() else "#"

            # jieba 分词：基础名 + 完整标题都入 FTS5
            title_fts = " ".join(jieba.cut_for_search(new_title)) + " " + " ".join(
                jieba.cut_for_search(dt)
            )

            # 更新
            db.execute(
                "UPDATE resources SET title=?, pinyin=?, pinyin_first=? WHERE id=?",
                (title_fts, full, first, r["id"]),
            )
            fixed += 1
            if fixed % 500 == 0:
                print(f"  已修复 {fixed}/{len(rows)}...")

    print(f"修复完成: {fixed} 条")


if __name__ == "__main__":
    fix_all()
