"""预测相关 Celery 后台任务"""

import json
import logging
from typing import Optional
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)

# Redis 存储训练进度（替代内存字典方案）
# 每条进度用 Redis HASH 存储：train:progress:{task_id}
# HASH 字段: {status, model_id, percent, phase, detail, error}
# 进度 key 有 TTL=7200 秒（2小时），训练结束后自动过期
_PROGRESS_TTL = 7200

_redis_client = None


def _get_redis():
    """懒加载 Redis 客户端，避免 import 时连接"""
    global _redis_client
    if _redis_client is None:
        from app.core.redis import redis_client
        _redis_client = redis_client
    return _redis_client


def _progress_key(task_id: str) -> str:
    return f"train:progress:{task_id}"


# 训练阶段常量
_PHASE_INIT = "初始化"
_PHASE_FETCH = "拉取历史数据"
_PHASE_FEATURE = "特征工程"
_PHASE_TRAINING = "模型训练"
_PHASE_SAVING = "保存模型"

_PHASE_WEIGHTS = {
    _PHASE_INIT: 0,
    _PHASE_FETCH: 15,
    _PHASE_FEATURE: 35,
    _PHASE_TRAINING: 65,
    _PHASE_SAVING: 90,
}


def _update_progress(task_id: str, phase: str, detail: str = "", model_id: int = None, percent: int = None):
    """更新任务进度到 Redis

    每次调用覆盖写入 HASH 并刷新 TTL。
    相比内存字典方案：页面刷新/Worker 重启后进度不丢失。
    """
    r = _get_redis()
    key = _progress_key(task_id)
    final_pct = str(percent) if percent is not None else str(_PHASE_WEIGHTS.get(phase, 0))
    r.hset(key, mapping={
        "status": "running",
        "model_id": str(model_id) if model_id else "",
        "error": "",
        "percent": final_pct,
        "phase": phase,
        "detail": detail,
    })
    r.expire(key, _PROGRESS_TTL)


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def train_prediction_model(self, data_source_id: int, train_days: int = 365):
    """定时训练预测模型"""
    logger.info(f"[Celery] 开始训练预测模型: data_source_id={data_source_id}")
    db = SessionLocal()
    try:
        service = PredictionService(db)
        model_id = service.train(data_source_id, train_days)
        logger.info(f"[Celery] 训练完成: model_id={model_id}")
        return {"model_id": model_id, "status": "success"}
    except Exception as e:
        logger.error(f"[Celery] 训练失败: {e}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


def _train_with_progress(
    task_id: str,
    data_source_id: int,
    train_days: int,
    table_name: Optional[str],
    user_id: Optional[int] = None,
) -> int:
    """带进度汇报的训练流程"""
    _update_progress(task_id, _PHASE_INIT, "准备训练环境")
    db = SessionLocal()

    try:
        service = PredictionService(db)
        train_kwargs = {"train_days": train_days}

        if table_name:
            train_kwargs["table_name"] = table_name

        ds = service.ds_repo.get_by_id(data_source_id)
        if not ds:
            raise ValueError(f"数据源 {data_source_id} 不存在")

        # 创建模型记录（拿到 model_id 后后续更新进度可用）
        model_record = service.model_repo.create(
            data_source_id=data_source_id,
            model_type="lightgbm",
            status="training",
            task_id=task_id,
            created_by=user_id,
        )
        _update_progress(task_id, _PHASE_INIT, f"模型记录已创建，id={model_record.id}", model_record.id)

        _update_progress(task_id, _PHASE_FETCH, f"数据源={data_source_id}，天数={train_days}")

        # 定义分页拉取进度回调
        def _fetch_page_progress(page, total, page_rows):
            pct = min(int(page / total * 30), 30)  # 拉取阶段占 0-30%
            _update_progress(
                task_id, _PHASE_FETCH,
                f"拉取中 {page}/{total} 天 (本页 {page_rows} 行)",
                model_record.id, percent=pct
            )

        df = service._fetch_history_data(
            ds.id, train_days, table_name=table_name,
            progress_callback=_fetch_page_progress,
        )
        if len(df) < service.settings.prediction_min_history_days * 10:
            raise ValueError(
                f"历史数据不足({len(df)}行)，需要至少 "
                f"{service.settings.prediction_min_history_days * 10} 行"
            )
        _update_progress(task_id, _PHASE_FETCH, f"已拉取 {len(df)} 行数据", model_record.id)

        from app.utils.feature_engineering import build_features_from_history, get_feature_columns

        _update_progress(task_id, _PHASE_FEATURE, "构造时间特征")
        df_feat = build_features_from_history(df)
        feature_cols = get_feature_columns()
        df_feat = df_feat.dropna(subset=feature_cols).reset_index(drop=True)
        _update_progress(task_id, _PHASE_FEATURE, f"特征维度={len(feature_cols)}，样本数={len(df_feat)}", model_record.id)

        import lightgbm as lgb
        import numpy as np

        _update_progress(task_id, _PHASE_TRAINING, "LightGBM: n_estimators=500, max_depth=8")
        X = df_feat[feature_cols].values
        y = df_feat["actual_sale_untaxed_amt"].values

        model = lgb.LGBMRegressor(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=8,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
        )
        model.fit(X, y)

        y_pred = model.predict(X)
        mae = float(np.mean(np.abs(y - y_pred)))
        rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))
        _update_progress(task_id, _PHASE_TRAINING, f"MAE={mae:.2f}, RMSE={rmse:.2f}", model_record.id)

        import joblib
        import os
        from datetime import datetime

        _update_progress(task_id, _PHASE_SAVING, "保存模型文件")
        model_path = os.path.join(service.model_dir, f"lgb_{ds.id}_{model_record.id}.pkl")
        joblib.dump(model, model_path)

        service.model_repo.update_status(
            model_record.id,
            "ready",
            model_path=model_path,
            feature_count=len(feature_cols),
            train_start_date=df["dt"].min().date(),
            train_end_date=df["dt"].max().date(),
            train_row_count=len(df_feat),
            model_metrics={"mae": mae, "rmse": rmse},
            trained_at=datetime.utcnow(),
        )

        # 训练成功：写入最终状态到 Redis
        r = _get_redis()
        key = _progress_key(task_id)
        r.hset(key, mapping={
            "status": "success",
            "model_id": str(model_record.id),
            "error": "",
            "percent": "100",
            "phase": "完成",
            "detail": f"MAE={mae:.2f}, RMSE={rmse:.2f}",
        })
        r.expire(key, _PROGRESS_TTL)
        return model_record.id

    except Exception as e:
        logger.error(f"[Celery] 训练失败: task_id={task_id}, error={e}")
        # 更新模型记录状态
        try:
            service.model_repo.update_status(
                model_record.id, "failed",
                error_message=str(e),
            )
        except Exception:
            pass
        # 写入失败状态到 Redis
        try:
            r = _get_redis()
            key = _progress_key(task_id)
            r.hset(key, mapping={
                "status": "failed",
                "model_id": str(model_record.id) if model_record else "",
                "error": str(e),
                "percent": "0",
                "phase": "失败",
                "detail": str(e),
            })
            r.expire(key, _PROGRESS_TTL)
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def train_prediction_model_async(
    self,
    data_source_id: int,
    train_days: Optional[int] = None,
    table_name: Optional[str] = None,
    target_field: Optional[str] = None,
    date_field: Optional[str] = None,
    store_field: Optional[str] = None,
    sku_field: Optional[str] = None,
    user_id: Optional[int] = None,
):
    """异步训练预测模型（人工触发）"""
    task_id = self.request.id

    # 写入初始状态到 Redis
    r = _get_redis()
    key = _progress_key(task_id)
    r.hset(key, mapping={
        "status": "running",
        "model_id": "",
        "error": "",
        "percent": "0",
        "phase": "初始化",
        "detail": "任务已提交",
    })
    r.expire(key, _PROGRESS_TTL)

    logger.info(
        f"[Celery] 异步训练开始: task_id={task_id}, "
        f"data_source_id={data_source_id}, train_days={train_days}"
    )

    try:
        model_id = _train_with_progress(
            task_id, data_source_id, train_days or 365, table_name, user_id=user_id,
        )
        return {"model_id": model_id, "status": "success"}
    except Exception as e:
        raise self.retry(exc=e, countdown=300)


def get_async_task_progress(task_id: str) -> dict:
    """查询异步训练任务状态（含进度百分比和阶段描述）

    优先级：1) Redis → 2) Celery AsyncResult → 3) 数据库记录
    """
    # 1) Redis 进度（最快，Worker 重启后仍然存在）
    r = _get_redis()
    key = _progress_key(task_id)
    data = r.hgetall(key)
    if data:
        return {
            "status": data.get("status", "unknown"),
            "model_id": int(data["model_id"]) if data.get("model_id") else None,
            "error": data.get("error") or None,
            "percent": int(data.get("percent", 0)),
            "phase": data.get("phase", ""),
            "detail": data.get("detail", ""),
        }

    # 2) Celery AsyncResult
    try:
        result = celery_app.AsyncResult(task_id)
        if result.state == "SUCCESS":
            return {
                "status": "success", "model_id": result.result.get("model_id") if result.result else None,
                "error": None, "percent": 100,
                "phase": "完成", "detail": "",
            }
        elif result.state == "FAILURE":
            return {
                "status": "failed", "model_id": None,
                "error": str(result.result), "percent": 0,
                "phase": "失败", "detail": str(result.result),
            }
        elif result.state == "PENDING":
            # 3) 数据库记录兜底
            db_progress = _load_db_progress(task_id)
            if db_progress:
                return db_progress
            return {
                "status": "pending", "model_id": None,
                "error": None, "percent": 0,
                "phase": "等待中", "detail": "任务排队中",
            }
        else:
            return {
                "status": result.state.lower(), "model_id": None,
                "error": None, "percent": 0,
                "phase": result.state, "detail": "",
            }
    except Exception:
        # 3) 数据库记录（兜底）
        db_progress = _load_db_progress(task_id)
        if db_progress:
            return db_progress
        return {
            "status": "unknown", "model_id": None,
            "error": "task_id not found", "percent": 0,
            "phase": "未知", "detail": "",
        }


def _load_db_progress(task_id: str) -> dict | None:
    """从数据库加载训练进度（兜底方案）"""
    try:
        db = SessionLocal()
        from app.models.prediction import PredictionModel
        record = db.query(PredictionModel).filter(PredictionModel.task_id == task_id).first()
        if record:
            status = record.status if record.status in ("training", "ready", "failed") else "running"
            return {
                "status": status,
                "model_id": record.id,
                "error": record.error_message,
                "percent": 100 if record.status == "ready" else 0,
                "phase": "完成" if record.status == "ready" else ("失败" if record.status == "failed" else "运行中"),
                "detail": record.error_message or "",
            }
        return None
    except Exception:
        return None
    finally:
        db.close()
