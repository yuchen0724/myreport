"""Runtime semantic-layer context for LLM prompts."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_semantic_runtime_context(
    db: Session,
    data_source_id: int,
    question: Optional[str] = None,
    max_chars: int = 12000,
) -> str:
    """Build a prompt-ready semantic-layer context block for LLM calls."""
    try:
        from app.services.nl2sql_service import NL2SQLService
        from app.services.query_service import QueryService

        service = NL2SQLService(QueryService(db), db)
        semantic_doc = service._load_semantic_doc(data_source_id)
        if not semantic_doc:
            return (
                "## 运行时语义层约束\n"
                "- 当前数据源未找到 `semantic/` 语义层文档；不要臆造字段、表关系或指标口径。\n"
                "- 如需生成 SQL 或解释指标，必须基于已知工具返回的 schema/语义指标；不确定时应明确说明缺少语义层依据。\n"
            )

        selected_doc = service._select_relevant_schema_prompt(question or "", semantic_doc)
        if len(selected_doc) > max_chars:
            selected_doc = selected_doc[:max_chars].rstrip() + "\n\n...（语义层文档已按长度截断）"

        doc_names = service._get_loaded_doc_names(data_source_id)
        doc_names_text = ", ".join(doc_names) if doc_names else "未记录文件名"
        return (
            "## 运行时语义层约束\n"
            "- 下面的语义层文档是当前数据源的数据逻辑来源，回答、工具选择、SQL 生成和异常解读必须优先遵守。\n"
            "- 必须按文档理解指标口径、字段含义、维度、表关联、日期字段、过滤条件和业务含义。\n"
            "- 如果语义层文档与实时 schema 或模型常识冲突，以语义层文档为准；不得自行发明字段、维度、JOIN 或指标计算方式。\n"
            "- 如果用户问题命中可用语义指标，应优先使用统一指标工具或指标定义，而不是自由拼接新口径。\n\n"
            f"## 已加载语义层文档\n{doc_names_text}\n\n"
            f"## 语义层文档内容\n{selected_doc}"
        )
    except Exception as exc:
        logger.warning("构建运行时语义层上下文失败: %s", exc, exc_info=True)
        return (
            "## 运行时语义层约束\n"
            "- 语义层上下文加载失败；不要臆造字段、表关系或指标口径。\n"
            "- 如需生成 SQL 或解释指标，必须明确说明缺少语义层依据，并优先使用可用语义指标或 schema 工具核验。\n"
        )
