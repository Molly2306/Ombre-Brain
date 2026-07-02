# 本地与Upstream的分歧清单

> 每次同步upstream前先读这份文档，避免重复踩坑或覆盖本地专属逻辑

## 一、有意保留本地版本，不采纳upstream（设计分歧）

1. **双连接器架构**：本地保留 /mcp + /mcp-extra 双连接器（server.py），
   upstream已合并为单连接器 /mcp。原因：chat_history工具挂载在/mcp-extra上，用于读取Supabase历史记录。

2. **端口默认值**：本地固定8000，upstream默认18001。原因：与实际部署环境一致。

3. **MCP tool docstring风格**：本地全部改为第一人称视角，upstream为中性第三人称。
   原因：贴合角色人格设定。

4. **hold/grow的LLM自动domain分类**：本地关闭（a1aaeb9），domain统一为空列表，靠目录结构区分状态。
   原因：不让LLM把活的话切成死标签；已验证实际使用中只用到domain="feel"，其他domain过滤未被使用，关闭无实际功能损失。

5. **embedding失败处理策略**：本地保持best-effort降级（关键词+jieba加权兜底），不采纳upstream的
   embedding强制依赖。已实现向量降级计数器（vector_fallback，pulse可见）作为监控替代方案。

## 二、本地专属新增功能（upstream完全没有）

- jieba关键词命中加权重排序（f7209e1，src/tools/breath/search.py）
- 向量通道resolved桶降权70%（520cec6，src/tools/breath/search.py）
- chat_history工具，挂载在/mcp-extra（5281316）
- 向量检索降级计数器vector_fallback，pulse可见（943f7da）
- superseded_by 废止标记机制（f4b423a，涉及 [bucket_manager.py](file:///c:/Users/14586/Ombre-Brain/src/bucket_manager.py), [core.py](file:///c:/Users/14586/Ombre-Brain/src/tools/trace/core.py), [search.py](file:///c:/Users/14586/Ombre-Brain/src/tools/breath/search.py), [surface.py](file:///c:/Users/14586/Ombre-Brain/src/tools/breath/surface.py), [importance.py](file:///c:/Users/14586/Ombre-Brain/src/tools/breath/importance.py)）
- merge_or_create 自动合并加 jieba 关键词二段判定机制及 search.py 重构迁移（833a5bb，涉及 [_common.py](file:///c:/Users/14586/Ombre-Brain/src/tools/_common.py), [search.py](file:///c:/Users/14586/Ombre-Brain/src/tools/breath/search.py)）
- search.py低档过滤 (is_low_tier)
  - commit: 6313d90
  - 文件: src/tools/_common.py, src/tools/breath/search.py
  - 内容: 综合分<40时跳过注入，拦截literal_hit绕过fuzzy_threshold(50)后仍放行的低质量记忆(旧+低重要度+字面命中，实测分数区间约35~40)
  - 范围限制: 仅search.py入口生效。surface.py用decay_score(实测量级0~17.72)，与检索综合分(0~100)量纲完全不同，套用同一阈值会导致100%动态记忆被误杀，已验证不可行，未实施。importance.py无score字段，不适用，已跳过。
  - 后续: surface.py若要做同类过滤，需针对decay_score单独设计阈值，不可复用40这个数字，建议开独立窗口处理

## 三、已采纳upstream的功能（merge-upstream-batch1，2026-07-01）


- API timeout可配置（69a6924/e97e109）
- letter_write恢复ai_name参数（ed34464/8ba1b22）
- OAuth显示名AI_NAME + datetime序列化修复（65551f9/de181ec，含bucket_manager.py归一化，已完成）
- Dashboard认证页JS修复（ee586e8/4e438e6）
- breath importance溢出修复（517d69b）
- import JSON chatter容错（0274cee）
- provider_detect.py、bucket_scoring.py新文件（源自fcb70b4）
- pin配额硬限制检查、importance.py dehydrate失败兜底（fcb70b4部分）

## 四、本轮merge中发现并修复的"隐蔽覆盖事故"

已确认多次cherry-pick因"编辑器打开过期版本文件"导致新功能被无意覆盖：
- de181ec：删除config_api.py里timeout_seconds整条管线
- 8ba1b22：删除config_api.py里AI_NAME/OMBRE_MCP_REQUIRE_AUTH schema，连带破坏OMBRE_HOOK_URL/OMBRE_HOOK_SKIP持久化
- de181ec：删除frontend/dashboard.html和dashboard.html的timeout UI

**教训：不能只看--stat判断"直接搬运"，必须结合pytest交叉验证；纯UI文件（无测试覆盖）需额外人工抽查。**

