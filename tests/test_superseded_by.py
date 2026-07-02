import pytest
from unittest.mock import MagicMock

import tools._runtime as rt
from tools.breath.search import surface_search
from tools.breath.surface import surface_default
from tools.breath.importance import surface_by_importance
from tools.trace.core import trace_core
from decay_engine import DecayEngine


class EchoDehydrator:
    async def dehydrate(self, content, meta=None):
        return content


class MockEmbeddingEngine:
    def __init__(self):
        self.enabled = True

    async def search_similar(self, query, top_k=20):
        # 返回空，走关键字搜索
        return []

    async def generate_and_store(self, bucket_id, content):
        pass


def install_runtime(bucket_mgr):
    rt.config = {
        "surfacing": {
            "breath_max_results": 20,
            "breath_max_tokens": 10000,
        }
    }
    rt.bucket_mgr = bucket_mgr
    rt.dehydrator = EchoDehydrator()
    rt.logger = MagicMock()
    rt.fire_webhook = None
    rt.mark_op = None
    rt.embedding_engine = MockEmbeddingEngine()
    rt.vector_fallback = None
    # 注入真正的衰减引擎
    rt.decay_engine = DecayEngine(bucket_mgr.config, bucket_mgr)


@pytest.mark.asyncio
async def test_trace_superseded_by_update(bucket_mgr):
    """测试用例 1：创建测试桶，用 trace 设置 superseded_by='other_id' 成功落盘并保存元数据。"""
    install_runtime(bucket_mgr)
    bucket_id = await bucket_mgr.create(content="Memory to be superseded", domain=["test"])
    
    # 验证新创建的桶中，frontmatter里没有 superseded_by 字段
    bucket_before = await bucket_mgr.get(bucket_id)
    assert "superseded_by" not in bucket_before["metadata"]

    # 运行 trace_core 设置 superseded_by
    result = await trace_core(bucket_id, superseded_by="target_bucket_123")
    assert "superseded_by=target_bucket_123" in result

    # 验证元数据已落盘并保存
    bucket_after = await bucket_mgr.get(bucket_id)
    assert bucket_after["metadata"]["superseded_by"] == "target_bucket_123"


@pytest.mark.asyncio
async def test_superseded_by_filters_regular_breath(bucket_mgr):
    """测试用例 2：常规有 query 检索及无 query 浮现、以及按重要度召回，均无法搜索到该已废止桶。"""
    install_runtime(bucket_mgr)
    
    # 创建被废止桶
    bucket_superseded = await bucket_mgr.create(content="Important apple pie recipe", importance=10, domain=["test"])
    await trace_core(bucket_superseded, superseded_by="newer_apple_pie_recipe")

    # 创建正常桶
    bucket_normal = await bucket_mgr.create(content="Important banana bread recipe", importance=10, domain=["test"])

    # 1. 验证常规有 query 检索过滤
    search_res = await surface_search(query="Important", max_results=5, max_tokens=1000, domain="", valence=-1, arousal=-1, tag_filter=[])
    assert bucket_normal in search_res
    assert bucket_superseded not in search_res

    # 2. 验证常规无 query 浮现过滤
    surface_res = await surface_default(max_results=5, max_tokens=1000, tag_filter=[])
    assert bucket_normal in surface_res
    assert bucket_superseded not in surface_res

    # 3. 验证按重要度召回过滤
    importance_res = await surface_by_importance(importance_min=9, max_tokens=1000, tag_filter=[])
    assert bucket_normal in importance_res
    assert bucket_superseded not in importance_res


@pytest.mark.asyncio
async def test_superseded_by_clear_restores_visibility(bucket_mgr):
    """测试用例 3：调用 trace 传入 superseded_by='\\clear' 能清空废止标记，使其可重新被常规检索/浮现到。"""
    install_runtime(bucket_mgr)
    bucket_id = await bucket_mgr.create(content="Temporary deprecated memory", importance=10, domain=["test"])
    
    # 废止
    await trace_core(bucket_id, superseded_by="newer_version")
    
    # 验证常规浮现不可见
    surface_res_1 = await surface_default(max_results=5, max_tokens=1000, tag_filter=[])
    assert bucket_id not in surface_res_1

    # 清除废止标记
    clear_result = await trace_core(bucket_id, superseded_by="\\clear")
    assert "superseded_by=" in clear_result

    # 验证元数据已清空（不一定是 None，可能为空字符串，但 not superseded_by 应为 True）
    bucket = await bucket_mgr.get(bucket_id)
    assert not bucket["metadata"].get("superseded_by")

    # 验证重新被常规检索/浮现召回
    surface_res_2 = await surface_default(max_results=5, max_tokens=1000, tag_filter=[])
    assert bucket_id in surface_res_2


@pytest.mark.asyncio
async def test_dont_surface_and_superseded_by_isolation(bucket_mgr):
    """测试用例 4：回归验证 dont_surface=1 的设置流程不受影响，两者过滤行为不冲突。"""
    install_runtime(bucket_mgr)
    bucket_id = await bucket_mgr.create(content="Memory for isolation test", importance=10, domain=["test"])

    # 设置 dont_surface=1
    await trace_core(bucket_id, dont_surface=1)
    bucket = await bucket_mgr.get(bucket_id)
    assert bucket["metadata"]["dont_surface"] is True
    assert "superseded_by" not in bucket["metadata"]

    # dont_surface=1 的桶：常规无 query 浮现过滤掉，但有 query 检索可以查到
    surface_res = await surface_default(max_results=5, max_tokens=1000, tag_filter=[])
    assert bucket_id not in surface_res

    search_res = await surface_search(query="isolation", max_results=5, max_tokens=1000, domain="", valence=-1, arousal=-1, tag_filter=[])
    assert bucket_id in search_res


@pytest.mark.asyncio
async def test_superseded_by_direct_id_lookup(bucket_mgr):
    """测试用例 5：通过 ID 直接查询接口 rt.bucket_mgr.get(bucket_id) 仍能读到完整内容，证明不被删除。"""
    install_runtime(bucket_mgr)
    bucket_id = await bucket_mgr.create(content="Deprecated but read-only archive", domain=["test"])
    await trace_core(bucket_id, superseded_by="another_id")

    # 直接 get 依然成功返回完整数据
    bucket = await bucket_mgr.get(bucket_id)
    assert bucket is not None
    assert bucket["id"] == bucket_id
    assert bucket["content"] == "Deprecated but read-only archive"
    assert bucket["metadata"]["superseded_by"] == "another_id"
