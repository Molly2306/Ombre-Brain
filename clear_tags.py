#!/usr/bin/env python3
# ============================================================
# 清空所有已有记忆桶的 tags（一刀切）
# 用法：python clear_tags.py
# ============================================================
import os
import sys
import frontmatter

BUCKETS_DIR = os.environ.get("OMBRE_BUCKETS_DIR", "buckets")

def clear_tags():
    count = 0
    cleared = 0
    for dirpath, _, filenames in os.walk(BUCKETS_DIR):
        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            filepath = os.path.join(dirpath, fname)
            try:
                post = frontmatter.load(filepath)
                if "tags" in post and post["tags"]:
                    post["tags"] = []
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(frontmatter.dumps(post))
                    cleared += 1
                    print(f"  ✓ {fname}")
                count += 1
            except Exception as e:
                print(f"  ✗ {fname}: {e}")

    print(f"\n完成：{count} 个桶，{cleared} 个清空标签")

if __name__ == "__main__":
    clear_tags()
