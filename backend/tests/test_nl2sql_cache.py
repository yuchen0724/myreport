"""NL2SQL 缓存测试 - 使用 mock Redis 避免依赖真实 Redis 实例"""

import json
import pytest
from unittest.mock import MagicMock, patch, ANY

from app.utils.nl2sql_cache import NL2SQLCache, get_nl2sql_cache


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_redis_client():
    """创建 mock Redis 客户端

    - get() 默认返回 None（缓存 miss）
    - setex() 默认成功
    - ping() 默认成功
    """
    client = MagicMock()
    client.get.return_value = None
    client.setex.return_value = True
    client.ping.return_value = True
    return client


@pytest.fixture
def cache_with_redis(mock_redis_client):
    """返回一个 _get_redis() 返回 mock_redis_client 的 NL2SQLCache 实例"""
    cache = NL2SQLCache(ttl=60)
    # 直接注入 mock，避免 _get_redis 走真实连接逻辑
    cache._redis_client = mock_redis_client
    cache._connection_failed = False
    return cache, mock_redis_client


@pytest.fixture
def cache_no_redis():
    """返回一个 _get_redis() 返回 None 的 NL2SQLCache 实例"""
    cache = NL2SQLCache(ttl=60)
    cache._connection_failed = True
    cache._redis_client = None
    return cache


# ============================================================
# 测试 get_nl2sql_cache —— 单例工厂函数
# ============================================================

class TestGetNl2sqlCache:
    """测试 get_nl2sql_cache 全局单例工厂"""

    def test_returns_singleton(self):
        """多次调用返回同一实例"""
        instance1 = get_nl2sql_cache()
        instance2 = get_nl2sql_cache()
        assert instance1 is instance2

    def test_returns_nl2sql_cache_instance(self):
        """返回值类型正确"""
        instance = get_nl2sql_cache()
        assert isinstance(instance, NL2SQLCache)

    def test_default_ttl_from_config(self):
        """未传 ttl 时使用配置默认值 (3600)"""
        instance = get_nl2sql_cache()
        assert instance.ttl == 3600


# ============================================================
# 测试缓存键生成
# ============================================================

class TestCacheKeyGeneration:
    """测试 _hash_question 和 _make_cache_key"""

    def test_key_format(self):
        """缓存键格式为 nl2sql:{16字符hash}"""
        cache = NL2SQLCache(ttl=60)
        key = cache._make_cache_key("hello", 1)
        assert key.startswith("nl2sql:")
        # hash 部分应为 16 字符十六进制
        hash_part = key.split(":", 1)[1]
        assert len(hash_part) == 16
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_same_input_same_key(self):
        """相同输入产生相同缓存键"""
        cache = NL2SQLCache(ttl=60)
        key1 = cache._make_cache_key("查询销售额", 1)
        key2 = cache._make_cache_key("查询销售额", 1)
        assert key1 == key2

    def test_different_question_different_key(self):
        """不同问题产生不同键"""
        cache = NL2SQLCache(ttl=60)
        assert cache._make_cache_key("查询销售额", 1) != cache._make_cache_key("查询用户", 1)

    def test_different_data_source_different_key(self):
        """不同数据源产生不同键"""
        cache = NL2SQLCache(ttl=60)
        assert cache._make_cache_key("查询销售额", 1) != cache._make_cache_key("查询销售额", 2)

    def test_question_case_insensitive(self):
        """问题大小写不影响键（内部会 lower().strip()）"""
        cache = NL2SQLCache(ttl=60)
        key_upper = cache._make_cache_key("  QUERY Sales  ", 1)
        key_lower = cache._make_cache_key("query sales", 1)
        assert key_upper == key_lower

    def test_key_includes_generation_context(self):
        """不同的 generation 上下文参数产生不同键"""
        cache = NL2SQLCache(ttl=60)
        base_key = cache._make_cache_key(
            "查询销售额", 1,
            group_id=812,
            context="上一轮",
            schema_fingerprint="schema-a",
            llm_fingerprint="llm-a",
            prompt_version="v1",
        )
        assert base_key != cache._make_cache_key(
            "查询销售额", 1,
            group_id=57362,  # 不同 group_id
            context="上一轮",
            schema_fingerprint="schema-a",
            llm_fingerprint="llm-a",
            prompt_version="v1",
        )
        assert base_key != cache._make_cache_key(
            "查询销售额", 1,
            group_id=812,
            context="上一轮",
            schema_fingerprint="schema-b",  # 不同 schema_fingerprint
            llm_fingerprint="llm-a",
            prompt_version="v1",
        )
        assert base_key != cache._make_cache_key(
            "查询销售额", 1,
            group_id=812,
            context="上一轮",
            schema_fingerprint="schema-a",
            llm_fingerprint="llm-b",  # 不同 llm_fingerprint
            prompt_version="v1",
        )

    def test_context_and_group_id_variations(self):
        """验证 context / group_id 为 None 时的处理"""
        cache = NL2SQLCache(ttl=60)
        # None 与缺失不会导致异常
        key_with_none = cache._make_cache_key("test", 1, group_id=None, context=None)
        key_without = cache._make_cache_key("test", 1)
        assert key_with_none == key_without


# ============================================================
# 测试 get() —— Redis 可用
# ============================================================

class TestGetWithRedis:
    """get() 方法 — Redis 可用场景"""

    def test_cache_hit_returns_parsed_json(self, cache_with_redis):
        """缓存命中时返回解析后的 dict"""
        cache, mock_redis = cache_with_redis
        cached_data = {
            "sql": "SELECT * FROM users",
            "explanation": "查询所有用户",
            "confidence": 0.95,
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = cache.get("查询用户", 1)
        assert result == cached_data
        mock_redis.get.assert_called_once()

    def test_cache_miss_returns_none(self, cache_with_redis):
        """缓存未命中时返回 None"""
        cache, mock_redis = cache_with_redis
        mock_redis.get.return_value = None

        result = cache.get("查询用户", 1)
        assert result is None

    def test_make_cache_key_called_properly(self, cache_with_redis):
        """验证 get 中生成的缓存键格式正确"""
        cache, mock_redis = cache_with_redis
        mock_redis.get.return_value = json.dumps({"sql": "SELECT 1"})

        cache.get("hello", 42)
        # 验证调用的 key 以 nl2sql: 开头
        called_key = mock_redis.get.call_args[0][0]
        assert called_key.startswith("nl2sql:")
        assert len(called_key) == len("nl2sql:") + 16

    def test_all_optional_params_forwarded_to_key(self, cache_with_redis):
        """所有可选参数传递到缓存键"""
        cache, mock_redis = cache_with_redis
        mock_redis.get.return_value = json.dumps({"sql": "SELECT 1"})

        cache.get(
            "test", 1,
            group_id=10,
            context="ctx",
            schema_fingerprint="s-fp",
            llm_fingerprint="l-fp",
            prompt_version="v2",
        )
        called_key = mock_redis.get.call_args[0][0]
        # 验证键与直接构造的一致
        expected_key = cache._make_cache_key(
            "test", 1,
            group_id=10,
            context="ctx",
            schema_fingerprint="s-fp",
            llm_fingerprint="l-fp",
            prompt_version="v2",
        )
        assert called_key == expected_key

    def test_invalid_json_returns_none(self, cache_with_redis):
        """Redis 中存了非法 JSON 时返回 None"""
        cache, mock_redis = cache_with_redis
        mock_redis.get.return_value = "not-valid-json{{{"

        result = cache.get("查询用户", 1)
        assert result is None

    def test_redis_error_returns_none(self, cache_with_redis):
        """Redis get 抛出异常时返回 None"""
        cache, mock_redis = cache_with_redis
        mock_redis.get.side_effect = Exception("Connection lost")

        result = cache.get("查询用户", 1)
        assert result is None


# ============================================================
# 测试 get() —— Redis 不可用
# ============================================================

class TestGetNoRedis:
    """get() 方法 — Redis 不可用场景"""

    def test_returns_none_when_redis_unavailable(self, cache_no_redis):
        """Redis 连接失败时 get 返回 None"""
        result = cache_no_redis.get("查询用户", 1)
        assert result is None

    def test_returns_none_regardless_of_input(self, cache_no_redis):
        """无论输入如何，Redis 不可用一律返回 None"""
        assert cache_no_redis.get("any", 1) is None
        assert cache_no_redis.get("", 0, group_id=999) is None


# ============================================================
# 测试 set() —— Redis 可用
# ============================================================

class TestSetWithRedis:
    """set() 方法 — Redis 可用场景"""

    def test_set_returns_true(self, cache_with_redis):
        """set 成功返回 True"""
        cache, _ = cache_with_redis
        result = cache.set("查询用户", 1, sql="SELECT * FROM users")
        assert result is True

    def test_setex_called_with_key_ttl_and_json(self, cache_with_redis):
        """验证 setex 参数：键、TTL、JSON 序列化值"""
        cache, mock_redis = cache_with_redis
        cache.ttl = 300

        cache.set("查询用户", 1, sql="SELECT * FROM users")

        assert mock_redis.setex.called
        call_args = mock_redis.setex.call_args[0]
        key, ttl, value = call_args

        assert key.startswith("nl2sql:")
        assert ttl == 300
        # value 应为合法 JSON
        parsed = json.loads(value)
        assert parsed["sql"] == "SELECT * FROM users"
        assert parsed["data_source_id"] == 1
        assert parsed["confidence"] == 0.9

    def test_set_with_all_params(self, cache_with_redis):
        """set 包含所有可选参数"""
        cache, mock_redis = cache_with_redis
        chart_config = {"type": "bar", "x": "name"}

        cache.set(
            "查询用户", 1,
            sql="SELECT * FROM users",
            explanation="查询所有用户",
            confidence=0.99,
            chart_config=chart_config,
            group_id=10,
            context="ctx",
            schema_fingerprint="s-fp",
            llm_fingerprint="l-fp",
            prompt_version="v2",
        )

        call_args = mock_redis.setex.call_args[0]
        value = json.loads(call_args[2])
        assert value["sql"] == "SELECT * FROM users"
        assert value["explanation"] == "查询所有用户"
        assert value["confidence"] == 0.99
        assert value["chart_config"] == chart_config
        assert value["group_id"] == 10
        # context 仅参与缓存键生成，不存储在缓存值中
        assert "context" not in value
        assert value["schema_fingerprint"] == "s-fp"
        assert value["llm_fingerprint"] == "l-fp"
        assert value["prompt_version"] == "v2"

    def test_set_uses_instance_ttl(self, cache_with_redis):
        """setex 使用实例的 TTL"""
        cache, mock_redis = cache_with_redis
        cache.ttl = 7200

        cache.set("test", 1, sql="SELECT 1")
        _, ttl, _ = mock_redis.setex.call_args[0]
        assert ttl == 7200

    def test_set_error_returns_false(self, cache_with_redis):
        """set 遇到异常返回 False"""
        cache, mock_redis = cache_with_redis
        mock_redis.setex.side_effect = Exception("Write error")

        result = cache.set("test", 1, sql="SELECT 1")
        assert result is False


# ============================================================
# 测试 set() —— Redis 不可用
# ============================================================

class TestSetNoRedis:
    """set() 方法 — Redis 不可用场景"""

    def test_returns_false_when_redis_unavailable(self, cache_no_redis):
        """Redis 连接失败时 set 返回 False"""
        result = cache_no_redis.set("查询用户", 1, sql="SELECT *")
        assert result is False

    def test_returns_false_regardless_of_input(self, cache_no_redis):
        """无论输入如何，Redis 不可用一律返回 False"""
        assert cache_no_redis.set("any", 1, sql="X") is False
        assert cache_no_redis.set("", 0, sql="", group_id=999) is False


# ============================================================
# 测试 _get_redis —— Redis 连接逻辑
# ============================================================

class TestGetRedisConnection:
    """测试 _get_redis 连接/重试逻辑"""

    @patch("app.utils.nl2sql_cache.redis.from_url")
    def test_successful_connection(self, mock_from_url):
        """首次连接成功返回 Redis 客户端"""
        mock_instance = MagicMock()
        mock_instance.ping.return_value = True
        mock_from_url.return_value = mock_instance

        cache = NL2SQLCache(ttl=60)
        # 重置内部状态，模拟首次调用
        cache._redis_client = None
        cache._connection_failed = False

        client = cache._get_redis()
        assert client is mock_instance
        # 验证 ping 被调用
        mock_instance.ping.assert_called_once()
        mock_from_url.assert_called_once()

    @patch("app.utils.nl2sql_cache.redis.from_url")
    def test_connection_failure_sets_flag(self, mock_from_url):
        """连接失败设置 _connection_failed 并返回 None"""
        mock_instance = MagicMock()
        mock_instance.ping.side_effect = Exception("Connection refused")
        mock_from_url.return_value = mock_instance

        cache = NL2SQLCache(ttl=60)
        cache._redis_client = None
        cache._connection_failed = False

        client = cache._get_redis()
        assert client is None
        assert cache._connection_failed is True
        assert cache._redis_client is None

    @patch("app.utils.nl2sql_cache.redis.from_url")
    def test_skips_reconnect_after_failure(self, mock_from_url):
        """连接失败后第二次调用直接返回 None，不再重试"""
        mock_instance = MagicMock()
        mock_instance.ping.side_effect = Exception("Connection refused")
        mock_from_url.return_value = mock_instance

        cache = NL2SQLCache(ttl=60)
        cache._redis_client = None
        cache._connection_failed = False

        # 第一次：失败
        assert cache._get_redis() is None
        assert mock_from_url.call_count == 1

        # 第二次：直接返回 None，不再创建新 client
        assert cache._get_redis() is None
        assert mock_from_url.call_count == 1  # 不应增加

    def test_returns_existing_client(self, mock_redis_client):
        """_redis_client 已存在时直接返回"""
        cache = NL2SQLCache(ttl=60)
        cache._redis_client = mock_redis_client
        cache._connection_failed = False

        client = cache._get_redis()
        assert client is mock_redis_client
