from app.utils.nl2sql_cache import NL2SQLCache


def test_nl2sql_cache_key_includes_generation_context():
    cache = NL2SQLCache(ttl=60)

    base_key = cache._make_cache_key(
        "查询销售额",
        1,
        group_id=812,
        context="上一轮",
        schema_fingerprint="schema-a",
        llm_fingerprint="llm-a",
        prompt_version="v1",
    )

    assert base_key != cache._make_cache_key(
        "查询销售额",
        1,
        group_id=57362,
        context="上一轮",
        schema_fingerprint="schema-a",
        llm_fingerprint="llm-a",
        prompt_version="v1",
    )
    assert base_key != cache._make_cache_key(
        "查询销售额",
        1,
        group_id=812,
        context="上一轮",
        schema_fingerprint="schema-b",
        llm_fingerprint="llm-a",
        prompt_version="v1",
    )
    assert base_key != cache._make_cache_key(
        "查询销售额",
        1,
        group_id=812,
        context="上一轮",
        schema_fingerprint="schema-a",
        llm_fingerprint="llm-b",
        prompt_version="v1",
    )
