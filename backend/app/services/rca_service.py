"""RCA 根因分析服务"""
import uuid
import logging
from datetime import date, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.models.rca import RcaMetricConfig, RcaAnalysisTask, RcaAnomaly
from app.models.data_source import DataSource
from app.utils.rca_sql_builder import RcaSqlBuilder
from app.utils.db_executor import execute_query

logger = logging.getLogger(__name__)


class RcaService:
    def __init__(self, db: Session):
        self.db = db

    # ── 指标配置 CRUD ──

    def list_configs(self) -> List[RcaMetricConfig]:
        return (
            self.db.query(RcaMetricConfig)
            .filter(RcaMetricConfig.enabled == True)
            .order_by(RcaMetricConfig.id)
            .all()
        )

    def create_config(self, data: dict, user_id: int) -> RcaMetricConfig:
        config = RcaMetricConfig(**data, created_by=user_id)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def delete_config(self, config_id: int) -> bool:
        c = self.db.query(RcaMetricConfig).filter(RcaMetricConfig.id == config_id).first()
        if not c:
            return False
        self.db.delete(c)
        self.db.commit()
        return True

    def update_config(self, config_id: int, data: dict) -> Optional[RcaMetricConfig]:
        c = self.db.query(RcaMetricConfig).filter(RcaMetricConfig.id == config_id).first()
        if not c:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(c, k, v)
        self.db.commit()
        self.db.refresh(c)
        return c

    # ── 分析任务 ──

    def trigger_analysis(self, request: dict, user_id: int) -> RcaAnalysisTask:
        """创建分析任务（pending 状态，由 execute_analysis 执行）"""
        task_id = str(uuid.uuid4())
        config = self.db.query(RcaMetricConfig).filter(
            RcaMetricConfig.id == request["metric_config_id"]
        ).first()
        if not config:
            raise ValueError(f"指标配置不存在: {request['metric_config_id']}")

        task = RcaAnalysisTask(
            task_id=task_id,
            metric_config_id=config.id,
            analysis_date=request.get("analysis_date", date.today()),
            period_days=request.get("period_days", 7),
            status="pending",
            created_by=user_id,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def execute_analysis(self, task_id_str: str) -> Dict[str, Any]:
        """执行分析（由 Celery task 或 API 同步调用）"""
        task = (
            self.db.query(RcaAnalysisTask)
            .filter(RcaAnalysisTask.task_id == task_id_str)
            .first()
        )
        if not task:
            raise ValueError(f"任务不存在: {task_id_str}")

        config = (
            self.db.query(RcaMetricConfig)
            .filter(RcaMetricConfig.id == task.metric_config_id)
            .first()
        )

        # 获取数据源对象
        ds = self.db.query(DataSource).filter(DataSource.id == config.data_source_id).first()
        if not ds:
            raise ValueError(f"数据源不存在: {config.data_source_id}")

        task.status = "running"
        self.db.commit()

        try:
            builder = RcaSqlBuilder(config.source_table, config.group_id)
            p = task.period_days
            ce = task.analysis_date
            cs = (ce - timedelta(days=p)).strftime("%Y%m%d")
            ce_s = ce.strftime("%Y%m%d")
            be = ce - timedelta(days=p)
            bs = (be - timedelta(days=p)).strftime("%Y%m%d")
            be_s = be.strftime("%Y%m%d")

            # 1. 总体变化
            total_sql = builder.build_comparison_sql(
                config.metric_field, cs, ce_s, bs, be_s
            )
            total_change = 0
            try:
                rows, cols = execute_query(ds, total_sql)
                if rows and cols:
                    col_map = {c: i for i, c in enumerate(cols)}
                    total_change = rows[0][col_map.get("change_pct", 0)] or 0
            except Exception as e:
                logger.warning(f"Total comparison query failed: {e}")

            # 2. 维度下钻
            anomalies = []
            for dim in (config.drill_dimensions or [])[:4]:
                drill_sql = builder.build_drill_down_sql(
                    config.metric_field, cs, ce_s, bs, be_s, dim
                )
                try:
                    rows, cols = execute_query(ds, drill_sql)
                except Exception as e:
                    logger.warning(f"Drill-down query failed for {dim}: {e}")
                    continue

                if not rows or not cols:
                    continue

                col_map = {c: i for i, c in enumerate(cols)}
                # 去重：dim_name 可能因 JOIN 产生重复，取第一个
                seen = set()
                for row in rows:
                    if len(seen) >= 5:
                        break
                    dim_val = row[col_map["dim_val"]]
                    if dim_val in seen:
                        continue
                    seen.add(dim_val)
                    change_pct = row[col_map.get("change_pct", 0)] or 0
                    if abs(change_pct) >= config.threshold_value:
                        dim_path = {dim: dim_val}
                        dim_name = row[col_map.get("dim_name")] if "dim_name" in col_map else None
                        if dim_name:
                            dim_path["name"] = dim_name
                        a = RcaAnomaly(
                            task_id=task_id_str,
                            metric_name=config.name,
                            dimension_path=dim_path,
                            current_value=row[col_map.get("current_val", 0)],
                            baseline_value=row[col_map.get("baseline_val", 0)],
                            change_pct=change_pct,
                            severity="critical" if abs(change_pct) >= 30 else "warning",
                            contribution_pct=row[col_map.get("contribution_pct", 0)],
                        )
                        self.db.add(a)
                        anomalies.append(a)

            # 3. 保存结果
            task.status = "completed"
            task.anomaly_count = len(anomalies)
            task.summary = {
                "total_change_pct": float(total_change),
                "anomaly_count": len(anomalies),
                "metric_name": config.name,
                "period_days": p,
            }
            from datetime import datetime, timezone
            task.completed_at = datetime.now(timezone.utc)
            self.db.commit()

            return {"status": "completed", "anomaly_count": len(anomalies)}

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            self.db.commit()
            logger.error(f"RCA analysis failed: {e}", exc_info=True)
            raise

    # ── 查询 ──

    def get_anomalies(self, task_id: str) -> List[RcaAnomaly]:
        return (
            self.db.query(RcaAnomaly)
            .filter(RcaAnomaly.task_id == task_id)
            .order_by(RcaAnomaly.change_pct)
            .all()
        )

    def list_tasks(self, limit: int = 20) -> List[RcaAnalysisTask]:
        return (
            self.db.query(RcaAnalysisTask)
            .order_by(RcaAnalysisTask.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_task(self, task_id: str) -> bool:
        task = (
            self.db.query(RcaAnalysisTask)
            .filter(RcaAnalysisTask.task_id == task_id)
            .first()
        )
        if not task:
            return False
        # 先删关联的异常记录
        self.db.query(RcaAnomaly).filter(RcaAnomaly.task_id == task_id).delete()
        self.db.delete(task)
        self.db.commit()
        return True

    def drill_down(self, request: dict) -> List[dict]:
        """手动下钻查询"""
        task = (
            self.db.query(RcaAnalysisTask)
            .filter(RcaAnalysisTask.task_id == request["task_id"])
            .first()
        )
        if not task:
            raise ValueError("任务不存在")

        config = (
            self.db.query(RcaMetricConfig)
            .filter(RcaMetricConfig.id == task.metric_config_id)
            .first()
        )

        ds = self.db.query(DataSource).filter(DataSource.id == config.data_source_id).first()
        if not ds:
            raise ValueError(f"数据源不存在: {config.data_source_id}")

        builder = RcaSqlBuilder(config.source_table, config.group_id)
        p = task.period_days
        ce = task.analysis_date
        cs = (ce - timedelta(days=p)).strftime("%Y%m%d")
        ce_s = ce.strftime("%Y%m%d")
        be = ce - timedelta(days=p)
        bs = (be - timedelta(days=p)).strftime("%Y%m%d")
        be_s = be.strftime("%Y%m%d")

        dim = request.get(
            "dimension",
            config.drill_dimensions[0] if config.drill_dimensions else "operation_category1_name",
        )
        parent_filters = request.get("filters") or {}

        sql = builder.build_drill_down_sql(
            config.metric_field, cs, ce_s, bs, be_s, dim, parent_filters
        )
        rows, cols = execute_query(ds, sql)
        if not rows or not cols:
            return []
        return [dict(zip(cols, row)) for row in rows]
