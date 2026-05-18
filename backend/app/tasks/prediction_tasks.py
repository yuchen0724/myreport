"""预测相关 Celery 后台任务"""

import json
import logging
import lightgbm as lgb
from typing import Optional
from celery.exceptions import Ignore
from app.celery_app import celery_app
from app.config import get_settings
from app.core.database import SessionLocal
from app.services.prediction_service import PredictionService
from app.models.prediction import PredictionModel
from app.utils.feature_engineering import get_feature_columns

logger = logging.getLogger(__name__)

# 任务配置（从 Settings 读取，支持 .env 覆盖）
_settings = get_settings()
PREDICTION_TASK_MAX_RETRIES: int = _settings.prediction_task_max_retries
PREDICTION_TASK_SOFT_TIME_LIMIT: int = _settings.prediction_task_soft_time_limit
PREDICTION_TASK_TIME_LIMIT: int = _settings.prediction_task_time_limit

# Redis 存储训练进度（替代内存字典方案）
# 每条进度用 Redis HASH 存储：train:progress:{task_id}
# HASH 字段: {status, model_id, percent, phase, detail, error}
# 进度 key 有 TTL=7200 秒（2小时），训练结束后自动过期
_PROGRESS_TTL = 7200

_redis_client = None


def _is_unretriable_exc(exc: Exception) -> bool:
    """判断异常是否不应重试（重试也不会有任何改善）"""
    from sqlalchemy.exc import ProgrammingError
    return isinstance(exc, (ValueError, ProgrammingError, AssertionError))


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

_PHASE_PREDICT = "销售预测"


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
    is_retry: bool = False,
) -> int:
    """带进度汇报的训练流程

    Args:
        is_retry: 是否为 Celery 重试调用。重试时复用已有的 DB 模型记录，
                  不会创建新记录，避免残留 state。
    """
    _update_progress(task_id, _PHASE_INIT, "准备训练环境" if not is_retry else f"重试第{task_id[:8]}...")
    db = SessionLocal()

    try:
        service = PredictionService(db)
        train_kwargs = {"train_days": train_days}

        if table_name:
            train_kwargs["table_name"] = table_name

        ds = service.ds_repo.get_by_id(data_source_id)
        if not ds:
            raise ValueError(f"数据源 {data_source_id} 不存在")

        # 重试时复用已有 DB 记录，不创建新记录
        if is_retry:
            model_record = db.query(PredictionModel).filter(
                PredictionModel.task_id == task_id
            ).first()
            if not model_record:
                # 如果找不到（极端情况），才创建新记录
                model_record = service.model_repo.create(
                    data_source_id=data_source_id,
                    model_type="lightgbm",
                    status="training",
                    task_id=task_id,
                    created_by=user_id,
                )
            else:
                _update_progress(task_id, _PHASE_INIT, f"重试中，复用模型记录 id={model_record.id}", model_record.id)
        else:
            # 首次执行：创建模型记录
            model_record = service.model_repo.create(
                data_source_id=data_source_id,
                model_type="lightgbm",
                status="training",
                task_id=task_id,
                created_by=user_id,
            )
            _update_progress(task_id, _PHASE_INIT, f"模型记录已创建，id={model_record.id}", model_record.id)

        _update_progress(task_id, _PHASE_FETCH, f"数据源={data_source_id}，天数={train_days}", model_record.id)

        # 定义拉取回调：数据拉取完成后触发
        def _fetch_callback(batch_no, total_batches, batch_rows):
            pct = int(batch_no / total_batches * 15)  # 拉取阶段 0-15%
            _update_progress(
                task_id, _PHASE_FETCH,
                f"拉取中 {batch_no}/{total_batches} 批, 本批 {batch_rows} 行",
                model_record.id, percent=pct
            )

        # 定义训练回调：每批训练完成后触发
        def _train_callback(batch_no, total_batches, batch_rows):
            pct = 15 + int(batch_no / total_batches * 50)  # 训练阶段 15-65%
            if pct > 65:
                pct = 65
            _update_progress(
                task_id, _PHASE_TRAINING,
                f"训练中 {batch_no}/{total_batches} 批, 本批 {batch_rows} 行",
                model_record.id, percent=pct
            )
            # 热保存：每 5 批保存一次中间模型文件
            if batch_no % 5 == 0:
                import joblib
                import os
                checkpoint_path = os.path.join(service.model_dir, f"lgb_{ds.id}_{model_record.id}.pkl")
                os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
                joblib.dump(model, checkpoint_path)

        feature_cols = get_feature_columns()
        model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=8,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
            num_threads=2,
        )

        # 增量训练：边拉取边喂数据，不累积全量 DataFrame
        model, _, total_rows, train_start, train_end, mae, rmse, _, batch_count = service._fetch_and_train_incremental(
            ds.id, train_days, model, feature_cols,
            table_name=table_name,
            fetch_callback=_fetch_callback,
            train_callback=_train_callback,
        )
        _update_progress(task_id, _PHASE_FETCH, f"增量拉取完成，共 {total_rows} 行训练数据", model_record.id)
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
            train_start_date=train_start,
            train_end_date=train_end,
            train_row_count=total_rows,
            model_metrics={
                "mae": mae,
                "rmse": rmse,
                "batch_count": batch_count,
            },
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


def _train_and_predict_with_progress(
    task_id: str,
    data_source_id: int,
    train_days: int,
    forecast_days: int,
    table_name: Optional[str],
    user_id: Optional[int] = None,
    batch_size: Optional[int] = None,
    batch_unit: Optional[int] = None,
    is_retry: bool = False,
) -> tuple:
    """带进度汇报的训练+预测三阶段流水线

    阶段1: 拉取+训练 (0-55%)
    阶段2: 销售预测 (55-95%)
    阶段3: 完成 (100%)

    Args:
        is_retry: 是否为 Celery 重试调用。重试时复用已有的 DB 模型记录，
                  不会创建新记录，避免残留 state。

    Returns:
        (model_id, result_count) — 模型ID和预测结果条数
    """
    _update_progress(task_id, _PHASE_INIT, "准备训练环境")
    db = SessionLocal()

    try:
        service = PredictionService(db)

        ds = service.ds_repo.get_by_id(data_source_id)
        if not ds:
            raise ValueError(f"数据源 {data_source_id} 不存在")

        # 重试时复用已有 DB 记录，不创建新记录
        if is_retry:
            model_record = db.query(PredictionModel).filter(
                PredictionModel.task_id == task_id
            ).first()
            if not model_record:
                # 极端情况找不到时才创建新记录
                model_record = service.model_repo.create(
                    data_source_id=data_source_id,
                    model_type="lightgbm",
                    status="training",
                    task_id=task_id,
                    created_by=user_id,
                )
            else:
                _update_progress(task_id, "准备数据",
                                 f"重试中，复用模型记录 id={model_record.id}",
                                 model_record.id, percent=3)
        else:
            # 首次执行：创建模型记录
            model_record = service.model_repo.create(
                data_source_id=data_source_id,
                model_type="lightgbm",
                status="training",
                task_id=task_id,
                created_by=user_id,
            )
            _update_progress(task_id, "准备数据",
                             f"查询活跃分组，数据源={data_source_id}",
                             model_record.id, percent=3)

        result_count = 0

        # 定义批次完成回调：分批处理（拉取+训练+预测一体化），进度 5%~85%
        def _batch_complete_callback(chunk_df, batch_no, total_batches):
            nonlocal result_count
            try:
                batch_results = service._predict_from_cache(
                    data_df=chunk_df,
                    model=model,
                    model_record=model_record,
                    forecast_days=forecast_days,
                    progress_callback=None,
                )
                if batch_results:
                    service.result_repo.bulk_save(batch_results)
                    result_count += len(batch_results)
                pct = int(batch_no / total_batches * 80) + 5
                if pct > 85:
                    pct = 85
                _update_progress(
                    task_id, "分批处理",
                    f"处理中 {batch_no}/{total_batches} 批, 预测 {result_count} 条",
                    model_record.id, percent=pct
                )
                # 保存已完成批次数到 Redis，供重试断点续训使用
                try:
                    r = _get_redis()
                    r.hset(_progress_key(task_id), "completed_batches", str(batch_no))
                except Exception:
                    pass
            except Exception as e:
                import traceback
                logger.info(f"[训练+预测] 批次 {batch_no} 预测失败: {e}\n{traceback.format_exc()}")
        feature_cols = get_feature_columns()

        # 重试断点续训：从 Redis 读取已完成批次数，加载 checkpoint 模型
        start_batch = 0
        if is_retry:
            try:
                r = _get_redis()
                cb = r.hget(_progress_key(task_id), "completed_batches")
                if cb:
                    start_batch = int(cb)
                    import os as _os, joblib as _jl
                    ckpt_path = _os.path.join(service.model_dir, f"lgb_{ds.id}_{model_record.id}.pkl")
                    if _os.path.exists(ckpt_path):
                        model = _jl.load(ckpt_path)
                        _update_progress(task_id, "分批处理",
                                         f"断点续训：跳过前 {start_batch} 批",
                                         model_record.id, percent=9)
                        logger.info(f"[训练+预测] 重试断点续训：跳过 {start_batch} 批，加载 checkpoint {ckpt_path}")
                    else:
                        logger.info(f"[训练+预测] 重试断点续训：跳过 {start_batch} 批（无 checkpoint，新建模型）")
            except Exception as e:
                logger.warning(f"[训练+预测] 重试断点续训失败，从头开始: {e}")

        model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=8,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
            num_threads=2,
        )

        # 拉取+训练+预测（每批内部训练完立即预测，不缓存全量数据）
        model, _, total_rows, train_start, train_end, mae, rmse, _, batch_count = service._fetch_and_train_incremental(
            ds.id, train_days, model, feature_cols,
            table_name=table_name,
            batch_size=batch_size or 200,
            batch_unit=batch_unit or 10,
            fetch_callback=None,
            train_callback=None,
            predict_callback=_batch_complete_callback,
            start_batch=start_batch,
        )
        _update_progress(task_id, _PHASE_SAVING, f"验证评估: MAE={mae:.2f}, RMSE={rmse:.2f}", model_record.id, percent=88)

        # 保存模型文件
        import joblib
        import os
        from datetime import datetime

        _update_progress(task_id, _PHASE_SAVING, "保存模型文件", percent=92)
        model_path = os.path.join(service.model_dir, f"lgb_{ds.id}_{model_record.id}.pkl")
        joblib.dump(model, model_path)

        service.model_repo.update_status(
            model_record.id,
            "ready",
            model_path=model_path,
            feature_count=len(feature_cols),
            train_start_date=train_start,
            train_end_date=train_end,
            train_row_count=total_rows,
            model_metrics={
                "mae": mae,
                "rmse": rmse,
                "batch_count": batch_count,
            },
            trained_at=datetime.utcnow(),
        )

        _update_progress(task_id, _PHASE_SAVING, "保存完成", model_record.id, percent=95)

        logger.info(f"[训练+预测] 写入 {result_count} 条预测结果，模型 model_id={model_record.id}")

        # 写入预测历史（成功）
        from app.repositories.prediction_repository import ForecastHistoryRepository
        hist_repo = ForecastHistoryRepository(db)
        hist_repo.create(
            task_id=task_id,
            model_id=model_record.id,
            data_source_id=data_source_id,
            forecast_days=forecast_days,
            result_count=result_count,
            status="success",
            created_by=user_id,
        )

        # 阶段3: 完成
        r = _get_redis()
        key = _progress_key(task_id)
        r.hset(key, mapping={
            "status": "success",
            "model_id": str(model_record.id),
            "error": "",
            "percent": "100",
            "phase": "完成",
            "detail": f"训练+预测完成: MAE={mae:.2f}, 预测{result_count}条",
        })
        r.expire(key, _PROGRESS_TTL)
        logger.info(f"[训练+预测] 全部完成: model_id={model_record.id}, 预测{result_count}条")
        return model_record.id, result_count

    except Exception as e:
        logger.error(f"[训练+预测] 失败: task_id={task_id}, error={e}")
        # 不修改 DB（重试时会被覆盖），只更新 Redis 进度
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
    """异步训练预测模型（人工触发）

    注意：重试时不会重新创建 DB 记录，_train_with_progress 内部会复用已有记录。
    """
    task_id = self.request.id

    # 写入初始状态到 Redis（幂等：重试时覆盖已有 key）
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
            is_retry=self.request.retries > 0,
        )
        return {"model_id": model_id, "status": "success"}
    except Exception as e:
        if _is_unretriable_exc(e):
            # 数据源不存在、DB 参数错误等——重试也没用，直接失败
            logger.warning(
                f"[Celery] 训练任务 {task_id} 因不可重试异常直接失败: "
                f"{type(e).__name__}: {e}"
            )
            r = _get_redis()
            key = _progress_key(task_id)
            _mark_progress_failed(r, key, str(e))
            # 标记 DB 模型为 failed
            _mark_db_model_failed(task_id, str(e))
            raise Ignore()
        # 重试前确保 Redis 状态是 running（覆盖失败状态）
        r = _get_redis()
        key = _progress_key(task_id)
        r.hset(key, mapping={
            "status": "running",
            "percent": "0",
            "phase": "重试中",
            "detail": f"即将重试({self.request.retries + 1}/{self.max_retries + 1})",
        })
        r.expire(key, _PROGRESS_TTL)
        if self.request.retries >= self.max_retries:
            # 最终失败，记录告警
            try:
                from app.core.database import SessionLocal as AlertSL
                from app.services.notification_service import NotificationService
                alert_db = AlertSL()
                try:
                    notif = NotificationService(alert_db)
                    notif.create_alert(
                        task_id=task_id,
                        task_type="train_only",
                        error_message=str(e),
                        alert_message=f"训练任务最终失败（重试用尽）: {str(e)[:200]}",
                        user_id=user_id,
                    )
                    alert_db.commit()
                finally:
                    alert_db.close()
            except Exception:
                pass
        raise self.retry(exc=e, countdown=300)


@celery_app.task(bind=True, max_retries=PREDICTION_TASK_MAX_RETRIES, soft_time_limit=PREDICTION_TASK_SOFT_TIME_LIMIT, time_limit=PREDICTION_TASK_TIME_LIMIT)
def train_and_predict_prediction_async(
    self,
    data_source_id: int,
    train_days: Optional[int] = None,
    forecast_days: Optional[int] = None,
    table_name: Optional[str] = None,
    user_id: Optional[int] = None,
    batch_size: Optional[int] = None,
    batch_unit: Optional[int] = None,
):
    """异步训练+预测（三阶段一键完成）

    训练模型后直接利用缓存数据预测，不重复拉取历史数据。
    """
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
        "detail": "训练+预测任务已提交",
    })
    r.expire(key, _PROGRESS_TTL)

    logger.info(
        f"[Celery] 训练+预测开始: task_id={task_id}, "
        f"data_source_id={data_source_id}, train_days={train_days}, forecast_days={forecast_days}"
    )
    logger.info(f"[Celery] 参数: batch_size={batch_size}, batch_unit={batch_unit}")

    try:
        model_id, result_count = _train_and_predict_with_progress(
            task_id, data_source_id,
            train_days or 365,
            forecast_days or 30,
            table_name,
            user_id=user_id,
            batch_size=batch_size,
            batch_unit=batch_unit,
            is_retry=self.request.retries > 0,
        )
        return {"model_id": model_id, "result_count": result_count, "status": "success"}
    except Exception as e:
        if _is_unretriable_exc(e):
            logger.warning(
                f"[Celery] 训练+预测任务 {task_id} 因不可重试异常直接失败: "
                f"{type(e).__name__}: {e}"
            )
            _mark_progress_failed(r, key, str(e))
            _mark_db_model_failed(task_id, str(e))
            raise Ignore()
        is_last_retry = self.request.retries >= self.max_retries
        if is_last_retry:
            # 所有重试用尽，标记模型为失败并写入失败预测历史，记录告警
            try:
                from app.core.database import SessionLocal as AlertSessionLocal
                from app.models.prediction import PredictionModel, ForecastHistory
                from app.repositories.prediction_repository import ForecastHistoryRepository
                from app.services.notification_service import NotificationService
                fh_db = AlertSessionLocal()
                try:
                    fh_db.query(PredictionModel).filter(
                        PredictionModel.task_id == task_id
                    ).update({"status": "failed", "error_message": str(e)})
                    hist_repo = ForecastHistoryRepository(fh_db)
                    hist_repo.create(
                        task_id=task_id,
                        model_id=None,
                        data_source_id=data_source_id,
                        forecast_days=forecast_days or 30,
                        result_count=0,
                        status="failed",
                        error_message=str(e),
                        created_by=user_id,
                    )
                    # 记录告警
                    try:
                        notif = NotificationService(fh_db)
                        notif.create_alert(
                            task_id=task_id,
                            task_type="train_predict",
                            error_message=str(e),
                            alert_message=f"训练+预测任务最终失败（重试用尽）: {str(e)[:200]}",
                            user_id=user_id,
                        )
                    except Exception:
                        pass
                    fh_db.commit()
                finally:
                    fh_db.close()
            except Exception:
                pass
        else:
            # 还有重试机会，确保 Redis 状态是 running
            r = _get_redis()
            key = _progress_key(task_id)
            r.hset(key, mapping={
                "status": "running",
                "percent": "0",
                "phase": "重试中",
                "detail":                f"即将重试({self.request.retries + 1}/{self.max_retries + 1})",
            })
            r.expire(key, _PROGRESS_TTL)
        raise self.retry(exc=e, countdown=300)


def _predict_with_progress(
    task_id: str,
    data_source_id: int,
    model_id: Optional[int],
    forecast_days: int,
    table_name: Optional[str],
) -> int:
    """带进度汇报的预测流程"""
    r = _get_redis()
    key = _progress_key(task_id)
    r.hset(key, mapping={
        "status": "running",
        "model_id": "",
        "error": "",
        "percent": "0",
        "phase": "初始化",
        "detail": "预测任务已提交",
    })
    r.expire(key, _PROGRESS_TTL)

    db = SessionLocal()
    try:
        service = PredictionService(db)

        def _predict_page_progress(mid: int, store_idx: int, total_stores: int, store_code: str):
            pct = int(store_idx / total_stores * 90)  # 0-90%
            r = _get_redis()
            pk = _progress_key(task_id)
            r.hset(pk, mapping={
                "status": "running",
                "model_id": str(mid),
                "error": "",
                "percent": str(pct),
                "phase": "门店预测",
                "detail": f"预测中 {store_idx}/{total_stores} 店 (门店 {store_code})",
            })
            r.expire(pk, _PROGRESS_TTL)

        count, actual_model_id = service.predict(
            ds_id=data_source_id,
            forecast_days=forecast_days,
            table_name=table_name,
            model_id=model_id,
            progress_callback=_predict_page_progress,
        )

        # 写入预测历史（成功）
        from app.repositories.prediction_repository import ForecastHistoryRepository
        hist_repo = ForecastHistoryRepository(db)
        hist_repo.create(
            task_id=task_id,
            model_id=actual_model_id,
            data_source_id=data_source_id,
            forecast_days=forecast_days,
            result_count=count,
            status="success",
            created_by=None,
        )

        # 成功
        r = _get_redis()
        pk = _progress_key(task_id)
        r.hset(pk, mapping={
            "status": "success",
            "model_id": str(actual_model_id),
            "error": "",
            "percent": "100",
            "phase": "完成",
            "detail": f"预测完成，共 {count} 条记录",
        })
        r.expire(pk, _PROGRESS_TTL)
        return count

    except Exception as e:
        logger.error(f"[Celery] 预测失败: task_id={task_id}, error={e}")
        # 写入预测历史（失败）
        try:
            from app.repositories.prediction_repository import ForecastHistoryRepository
            hist_repo = ForecastHistoryRepository(db)
            hist_repo.create(
                task_id=task_id,
                model_id=None,
                data_source_id=data_source_id,
                forecast_days=forecast_days,
                result_count=None,
                status="failed",
                error_message=str(e),
                created_by=None,
            )
        except Exception:
            pass
        try:
            r = _get_redis()
            pk = _progress_key(task_id)
            r.hset(pk, mapping={
                "status": "failed",
                "model_id": str(model_id) if model_id else "",
                "error": str(e),
                "percent": "0",
                "phase": "失败",
                "detail": str(e),
            })
            r.expire(pk, _PROGRESS_TTL)
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, soft_time_limit=600)
def predict_prediction_model_async(
    self,
    data_source_id: int,
    forecast_days: Optional[int] = None,
    table_name: Optional[str] = None,
    model_id: Optional[int] = None,
):
    """异步预测（人工触发，支持指定模型）"""
    task_id = self.request.id
    logger.info(
        f"[Celery] 异步预测开始: task_id={task_id}, "
        f"data_source_id={data_source_id}, model_id={model_id}, "
        f"forecast_days={forecast_days}"
    )
    try:
        count = _predict_with_progress(
            task_id, data_source_id, model_id,
            forecast_days or 30, table_name,
        )
        return {"count": count, "status": "success"}
    except Exception as e:
        logger.warning(f"[Celery] 预测失败，即将重试: task_id={task_id}, retry={self.request.retries+1}")
        if self.request.retries >= self.max_retries:
            # 最终失败，记录告警
            try:
                from app.core.database import SessionLocal as AlertSL
                from app.services.notification_service import NotificationService
                alert_db = AlertSL()
                try:
                    notif = NotificationService(alert_db)
                    notif.create_alert(
                        task_id=task_id,
                        task_type="predict_only",
                        error_message=str(e),
                        alert_message=f"预测任务最终失败（重试用尽）: {str(e)[:200]}",
                        user_id=None,
                    )
                    alert_db.commit()
                finally:
                    alert_db.close()
            except Exception:
                pass
        raise self.retry(exc=e, countdown=300)


def get_running_task_ids() -> set:
    """获取所有 Redis 中状态为 running 的 task_id 集合"""
    try:
        r = _get_redis()
        if r is None:
            return set()
        keys = r.keys("train:progress:*")
        running = set()
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            task_id = key_str.split(":", 2)[2]
            data = r.hgetall(key_str)
            if data:
                status = data.get(b"status") if isinstance(data.get(b"status"), bytes) else data.get("status", "")
                if isinstance(status, bytes):
                    status = status.decode()
                if status in ("running",):
                    running.add(task_id)
        return running
    except Exception as e:
        import traceback
        traceback.print_exc()
        return set()


def get_async_task_progress(task_id: str) -> dict:
    """查询异步训练/预测任务状态（含进度百分比和阶段描述）

    优先级：1) Redis → 2) Celery AsyncResult → 3) 数据库记录
    """
    # 1) Redis 进度（最快，Worker 重启后仍然存在）
    r = _get_redis()
    key = _progress_key(task_id)
    data = r.hgetall(key)
    if data:
        redis_status = data.get("status", "unknown")
        if isinstance(redis_status, bytes):
            redis_status = redis_status.decode()
        # 如果 Redis 显示 running，交叉验证 Celery 是否已经终结
        if redis_status == "running":
            try:
                result = celery_app.AsyncResult(task_id)
                if result.state == "SUCCESS":
                    r.hset(key, mapping={
                        "status": "success", "percent": "100", "phase": "完成", "detail": "",
                        "error": "", "model_id": str(result.result.get("model_id")) if result.result else "",
                    })
                    return {
                        "status": "success", "model_id": result.result.get("model_id") if result.result else None,
                        "error": None, "percent": 100, "phase": "完成", "detail": "",
                    }
                elif result.state == "FAILURE":
                    err_msg = str(result.result)
                    r.hset(key, mapping={
                        "status": "failed", "percent": "0", "phase": "失败", "detail": err_msg,
                        "error": err_msg, "model_id": "",
                    })
                    return {
                        "status": "failed", "model_id": None,
                        "error": err_msg, "percent": 0, "phase": "失败", "detail": err_msg,
                    }
            except Exception:
                pass
        return {
            "status": redis_status,
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
    """从数据库加载训练进度（兜底方案）

    注意：如果 Redis 中不存在进度 key，即使数据库 status="training"
    也视为"已过期的残留状态"，不返回 running 状态。
    所有实时状态以 Redis 为准。
    """
    try:
        db = SessionLocal()
        from app.models.prediction import PredictionModel
        record = db.query(PredictionModel).filter(PredictionModel.task_id == task_id).first()
        if record:
            status = record.status
            if status == "ready":
                return {
                    "status": "success",
                    "model_id": record.id,
                    "error": None,
                    "percent": 100,
                    "phase": "完成",
                    "detail": f"训练完成, ID={record.id}",
                }
            elif status == "failed":
                return {
                    "status": "failed",
                    "model_id": record.id,
                    "error": record.error_message or "训练失败",
                    "percent": 0,
                    "phase": "失败",
                    "detail": record.error_message or "",
                }
            elif status == "training":
                # Redis key 已过期，训练进程大概率已死，视为 failed
                return {
                    "status": "failed",
                    "model_id": record.id,
                    "error": "训练进程已断开（Redis 进度丢失）",
                    "percent": 0,
                    "phase": "断开",
                    "detail": "训练进程已断开，请重新提交",
                }
            else:
                return {
                    "status": "unknown",
                    "model_id": record.id,
                    "error": None,
                    "percent": 0,
                    "phase": "未知",
                    "detail": "",
                }
        return None
    except Exception:
        return None
    finally:
        db.close()


def _mark_progress_failed(r, key: str, error: str):
    """标记 Redis 进度为失败"""
    try:
        r.hset(key, mapping={
            "status": "failed",
            "percent": "0",
            "phase": "失败",
            "detail": error[:200],
            "error": error[:200],
        })
    except Exception:
        pass


def _mark_db_model_failed(task_id: str, error: str):
    """标记 DB 模型记录为失败"""
    try:
        db = SessionLocal()
        try:
            db.query(PredictionModel).filter(
                PredictionModel.task_id == task_id
            ).update({"status": "failed", "error_message": error[:500]})
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
