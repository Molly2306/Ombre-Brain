import pytest
from unittest.mock import MagicMock, AsyncMock

import tools._runtime as rt
from tools._common import merge_or_create


class EchoDehydrator:
    async def dehydrate(self, content, meta=None):
        return content

    async def analyze(self, content):
        return {
            "domain": [],
            "valence": 0.5,
            "arousal": 0.3,
            "tags": [],
            "suggested_name": "Test",
        }


def install_runtime(bucket_mgr):
    rt.config = {
        "merge_threshold": 75,
        "limits": {
            "max_bucket_bytes": 50 * 1024,
        }
    }
    rt.bucket_mgr = bucket_mgr
    rt.dehydrator = EchoDehydrator()
    rt.logger = MagicMock()
    rt.embedding_engine = MagicMock()
    rt.embedding_engine.enabled = False  # 禁用向量引擎，减少干扰


@pytest.mark.asyncio
async def test_merge_boost_overlap_success(bucket_mgr):
    """用例A: v_score在65~75区间 + 非数字关键词重合(唯一重合词'体重') + 数字不同 -> 验证刚好达到 0.5 阈值触发合并"""
    install_runtime(bucket_mgr)

    # 1. 先建一个已存在的桶
    # 非数字词表: {'记录', '体重'} (长度为 2)
    exist_id = await bucket_mgr.create(content="记录体重68", domain=["test"])

    # 2. Mock search 返回该桶，并且分数在 65~75 之间 (如 70)
    original_search = bucket_mgr.search
    async def mock_search(content, limit=1, domain_filter=None):
        bucket = await bucket_mgr.get(exist_id)
        bucket["score"] = 70.0
        return [bucket]
    
    bucket_mgr.search = mock_search

    try:
        # 3. 运行 merge_or_create
        # 非数字词表: {'测量', '体重'} (长度为 2)
        # 重合非数字词为 {'体重'}，overlap 为 1 / 2 = 0.5，刚好卡在 0.5 边界
        result_id, is_merged, _ = await merge_or_create(
            content="测量体重68.5",
            tags=[],
            importance=5,
            domain=[],
            valence=0.5,
            arousal=0.3,
            raw_merge=True,
        )

        # 4. 验证触发了合并 (is_merged 为 True，且返回的 id 是原桶 id)
        assert is_merged is True
        assert result_id == exist_id

        # 5. 验证内容已被追加合并
        bucket_after = await bucket_mgr.get(exist_id)
        assert "68.5" in bucket_after["content"]
    finally:
        bucket_mgr.search = original_search


@pytest.mark.asyncio
async def test_merge_boost_overlap_fail(bucket_mgr):
    """用例B: v_score在65~75区间 + 关键词完全不重合 -> 验证不合并、正常新建桶"""
    install_runtime(bucket_mgr)

    exist_id = await bucket_mgr.create(content="今天测了体重是68斤", domain=["test"])

    original_search = bucket_mgr.search
    async def mock_search(content, limit=1, domain_filter=None):
        bucket = await bucket_mgr.get(exist_id)
        bucket["score"] = 70.0
        return [bucket]
    
    bucket_mgr.search = mock_search

    try:
        # 传入完全没有关键词重合的文本
        result_id, is_merged, _ = await merge_or_create(
            content="明天要去买一台新的显示器",
            tags=[],
            importance=5,
            domain=[],
            valence=0.5,
            arousal=0.3,
            raw_merge=True,
        )

        # 验证没有触发合并，创建了新桶
        assert is_merged is False
        assert result_id != exist_id
    finally:
        bucket_mgr.search = original_search


@pytest.mark.asyncio
async def test_merge_boost_high_score(bucket_mgr):
    """用例C: v_score>75 -> 验证走原有自动合并路径不受影响(回归)"""
    install_runtime(bucket_mgr)

    exist_id = await bucket_mgr.create(content="测试原有的自动合并", domain=["test"])

    original_search = bucket_mgr.search
    async def mock_search(content, limit=1, domain_filter=None):
        bucket = await bucket_mgr.get(exist_id)
        bucket["score"] = 80.0 # 超过 merge_threshold=75
        return [bucket]
    
    bucket_mgr.search = mock_search

    try:
        # 即使内容有些不同，但向量相似度高也应该直接合并
        result_id, is_merged, _ = await merge_or_create(
            content="明天的任务是测试原有的自动合并",
            tags=[],
            importance=5,
            domain=[],
            valence=0.5,
            arousal=0.3,
            raw_merge=True,
        )

        assert is_merged is True
        assert result_id == exist_id
    finally:
        bucket_mgr.search = original_search


@pytest.mark.asyncio
async def test_merge_boost_low_score(bucket_mgr):
    """用例D: v_score<65 -> 验证正常新建桶不受影响(回归)"""
    install_runtime(bucket_mgr)

    exist_id = await bucket_mgr.create(content="今天测了体重是68斤", domain=["test"])

    original_search = bucket_mgr.search
    async def mock_search(content, limit=1, domain_filter=None):
        bucket = await bucket_mgr.get(exist_id)
        bucket["score"] = 60.0 # 低于二段判定底限 65
        return [bucket]
    
    bucket_mgr.search = mock_search

    try:
        # 即使关键词有重合，但向量分数太低也不合并
        result_id, is_merged, _ = await merge_or_create(
            content="今天又测了体重是68.5斤",
            tags=[],
            importance=5,
            domain=[],
            valence=0.5,
            arousal=0.3,
            raw_merge=True,
        )

        assert is_merged is False
        assert result_id != exist_id
    finally:
        bucket_mgr.search = original_search
