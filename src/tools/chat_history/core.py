"""
========================================
tools/chat_history/core.py — 只读查询 Cleo 的 Supabase 聊天记录
========================================
只读工具，让 claude.ai 能读取 Cleo 与用户的原始聊天记录（区别于 Ombre Brain
自己存的"提炼过的记忆"——这里读的是逐字原文）。

关键行为：
- 只读，不做任何写入/更新/删除
- limit 硬上限 50，默认 20，不信任调用方传入的任意值
- 需要环境变量 SUPABASE_URL 和 SUPABASE_KEY（建议用只读权限的 key，不要用service_role这种全权限的key）

对外暴露：chat_history_core(session_id, limit) -> str
========================================
"""
import os
from supabase import create_client

from tools import _runtime

def _get_supabase():
    # 动态获取环境变量，避免启动时强制要求
    _supabase_url = os.environ.get("SUPABASE_URL", "")
    _supabase_key = os.environ.get("SUPABASE_KEY", "")
    if _supabase_url and _supabase_key:
        return create_client(_supabase_url, _supabase_key)
    return None

async def chat_history_core(session_id: str, limit: int = 20) -> str:
    # 不强制使用 _runtime.logger，但可以用它来打日志
    if _runtime.logger:
        _runtime.logger.info(f"[chat_history] query session_id={session_id} limit={limit}")

    client = _get_supabase()
    if not client:
        return "未配置 SUPABASE_URL / SUPABASE_KEY，无法查询聊天记录。"
    if not session_id:
        return "缺少 session_id 参数。"

    actual_limit = limit if (limit and 0 < limit <= 50) else 20

    try:
        result = (
            client.table("messages")
            .select("role, content, created_at")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(actual_limit)
            .execute()
        )
    except Exception as e:
        if _runtime.logger:
            _runtime.logger.warning(f"[chat_history] query failed: {e}")
        return f"查询失败: {e}"

    rows = result.data or []
    if not rows:
        return "没有找到对应的聊天记录。"

    lines = [f"=== 聊天记录（{len(rows)} 条）==="]
    for r in reversed(rows):  # 按时间正序展示，比较符合阅读习惯
        ts = (r.get("created_at") or "")[:19]
        role = r.get("role", "?")
        content = r.get("content", "")
        lines.append(f"\n[{ts}] {role}:\n{content}")
    return "\n".join(lines)
