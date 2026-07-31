from unittest.mock import MagicMock, patch

from app.services.sql_correction_service import SqlCorrectionService


def test_candidate_is_excluded_until_reviewed(db_session):
    service = SqlCorrectionService(db_session)
    candidate = service.save_correction(
        data_source_id=1,
        question="统计昨日销售额",
        original_sql="",
        corrected_sql="SELECT SUM(amount) FROM sales WHERE dt = '2026-07-30'",
        review_status="candidate",
        source="ai_execution",
        evidence={"row_count": 1},
    )

    assert candidate.review_status == "candidate"
    assert service.find_matches("统计昨日销售额", 1) == []

    with patch.object(service, "_cache_question_embedding"):
        reviewed = service.review_correction(candidate.id, True, reviewer_id=7)

    assert reviewed.review_status == "verified"
    assert reviewed.verified_by == 7
    llm = MagicMock()
    llm.get_embedding.return_value = None
    with patch("app.services.sql_correction_service.get_llm_client", return_value=llm):
        matches = service.find_matches("统计昨日销售额", 1)
    assert matches[0]["corrected_sql"] == candidate.corrected_sql


def test_manual_duplicate_promotes_candidate(db_session):
    service = SqlCorrectionService(db_session)
    sql = "SELECT COUNT(*) FROM sales WHERE dt = '2026-07-30'"
    candidate = service.save_correction(
        data_source_id=1,
        question="销售记录数量",
        original_sql="",
        corrected_sql=sql,
        review_status="candidate",
        source="auto_repair",
    )

    with patch.object(service, "_cache_question_embedding"):
        promoted = service.save_correction(
            data_source_id=1,
            question="销售记录数量",
            original_sql="SELECT COUNT(*) FROM sale",
            corrected_sql=sql,
            user_id=9,
            review_status="verified",
            source="user_feedback",
        )

    assert promoted.id == candidate.id
    assert promoted.review_status == "verified"
    assert promoted.verified_by == 9


def test_unsafe_correction_is_rejected(db_session):
    service = SqlCorrectionService(db_session)
    try:
        service.save_correction(
            data_source_id=1,
            question="清理数据",
            original_sql="",
            corrected_sql="DELETE FROM sales",
        )
    except ValueError as exc:
        assert "安全校验" in str(exc)
    else:
        raise AssertionError("unsafe correction should be rejected")
