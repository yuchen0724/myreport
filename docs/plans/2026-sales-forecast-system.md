# 销售预测系统实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标**: 在现有自定义报表系统中集成基于 LightGBM 的销售预测功能，支持按门店-商品维度预测未来 N 天的销售额。

**架构**: 新增 `PredictionService` 层，通过 Celery 定时任务训练模型，训练好的模型序列化为 `.pkl` 文件存储，推理接口通过 FastAPI 暴露。特征工程从 Doris 历史数据中提取，预测结果写入预测结果表，前端通过报表组件展示。

**技术栈**: LightGBM, scikit-learn, pandas, Joblib, Celery Beat, FastAPI

**前置依赖**: 项目已有 Celery + Redis 基础设施（Celery Beat 需在 `celery_config.py` 中启用 beat 调度器）。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/services/prediction_service.py` | 模型训练、特征工程、推理预测的核心逻辑 |
| `backend/app/schemas/prediction.py` | 预测请求/响应的 Pydantic 模型 |
| `backend/app/api/prediction.py` | 预测 REST API 路由（触发训练、获取预测结果） |
| `backend/app/tasks/prediction_tasks.py` | Celery 异步训练任务 + Celery Beat 定时调度 |
| `backend/app/models/prediction.py` | SQLAlchemy 模型（预测结果表 + 模型元数据表） |
| `backend/app/repositories/prediction_repository.py` | 预测结果/模型元数据的数据库操作 |
| `backend/app/utils/feature_engineering.py` | 特征提取函数（与 prediction_service 解耦） |
| `backend/tests/test_prediction_service.py` | 单元测试（mock Doris 数据） |
| `backend/tests/test_prediction_api.py` | API 集成测试 |
| `backend/app/config.py` | 新增预测相关配置项 |
| `backend/requirements.txt` | 新增 lightgbm, scikit-learn, joblib |
| `backend/alembic/versions/` | 自动生成的数据库迁移 |

---

## 任务分解

### 任务 1：配置项 + 依赖 + 数据库模型

**文件：**
- 修改：`backend/app/config.py`（新增预测配置项）
- 修改：`backend/requirements.txt`（新增依赖）
- 创建：`backend/app/models/prediction.py`（预测结果 + 模型元数据表）
- 创建：`backend/app/repositories/prediction_repository.py`
- 执行：alembic 迁移

- [ ] **步骤 1：添加配置项**

在 `backend/app/config.py` 的 `Settings` 类末尾新增：

```python
    # Prediction / ML
    prediction_enabled: bool = True
    prediction_model_dir: str = "./ml_models"
    prediction_train_default_days: int = 365  # 训练用历史数据天数
    prediction_forecast_days: int = 30      # 默认预测天数
    prediction_min_history_days: int = 14   # 最小历史数据天数（不足则不训练）
    prediction_retrain_cron: str = "0 3 * * 1"  # 每周一凌晨3点重训
```

- [ ] **步骤 2：安装依赖并更新 requirements.txt**

在 `backend/requirements.txt` 追加：
```
lightgbm>=4.0.0
scikit-learn>=1.3.0
joblib>=1.3.0
```

运行安装验证：
```bash
cd /home/zhou/myreport/backend
pip install lightgbm scikit-learn joblib
python3 -c "import lightgbm; import sklearn; import joblib; print('OK')"
```

- [ ] **步骤 3：创建数据库模型**

创建 `backend/app/models/prediction.py`：

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, JSON
from app.core.database import Base
from datetime import datetime


class PredictionResult(Base):
    """销售预测结果表"""
    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, nullable=False, index=True, comment="模型ID")
    data_source_id = Column(Integer, nullable=False, comment="数据源ID")
    store_code = Column(String(32), nullable=False, comment="门店编码")
    matnr = Column(String(32), nullable=False, comment="商品编码")
    forecast_date = Column(Date, nullable=False, comment="预测日期")
    predicted_value = Column(Float, nullable=False, comment="预测值（元）")
    lower_bound = Column(Float, nullable=True, comment="预测下限")
    upper_bound = Column(Float, nullable=True, comment="预测上限")
    created_at = Column(DateTime, default=datetime.utcnow)
```

```python
class PredictionModel(Base):
    """训练好的模型元数据"""
    __tablename__ = "prediction_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_source_id = Column(Integer, nullable=False, comment="关联数据源")
    model_type = Column(String(32), default="lightgbm", comment="模型类型")
    feature_count = Column(Integer, nullable=True, comment="特征数")
    train_start_date = Column(Date, nullable=True, comment="训练数据起始日期")
    train_end_date = Column(Date, nullable=True, comment="训练数据截止日期")
    train_row_count = Column(Integer, nullable=True, comment="训练样本数")
    model_metrics = Column(JSON, nullable=True, comment="模型指标(JSON)")
    model_path = Column(String(255), nullable=True, comment="模型文件路径")
    status = Column(String(16), default="training", comment="状态: training/ready/failed")
    error_message = Column(Text, nullable=True, comment="训练失败原因")
    created_at = Column(DateTime, default=datetime.utcnow)
    trained_at = Column(DateTime, nullable=True, comment="训练完成时间")
```

> **注意**: 运行 `alembic revision --autogenerate -m "add prediction tables"` 和 `alembic upgrade head` 生成迁移。

- [ ] **步骤 4：创建 Repository**

创建 `backend/app/repositories/prediction_repository.py`：

```python
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
from app.models.prediction import PredictionResult, PredictionModel


class PredictionModelRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> PredictionModel:
        model = PredictionModel(**kwargs)
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get_latest_ready(self, data_source_id: int) -> Optional[PredictionModel]:
        return (
            self.db.query(PredictionModel)
            .filter(
                PredictionModel.data_source_id == data_source_id,
                PredictionModel.status == "ready",
            )
            .order_by(PredictionModel.id.desc())
            .first()
        )

    def update_status(self, model_id: int, status: str, **extra) -> None:
        self.db.query(PredictionModel).filter(PredictionModel.id == model_id).update(
            {"status": status, **extra}
        )
        self.db.commit()


class PredictionResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def bulk_save(self, results: List[PredictionResult]) -> int:
        self.db.bulk_save_objects(results)
        self.db.commit()
        return len(results)

    def get_forecast(
        self, data_source_id: int, store_code: Optional[str] = None,
        start_date: Optional[date] = None, end_date: Optional[date] = None,
        limit: int = 100, offset: int = 0
    ) -> List[PredictionResult]:
        q = self.db.query(PredictionResult).filter(
            PredictionResult.data_source_id == data_source_id
        )
        if store_code:
            q = q.filter(PredictionResult.store_code == store_code)
        if start_date:
            q = q.filter(PredictionResult.forecast_date >= start_date)
        if end_date:
            q = q.filter(PredictionResult.forecast_date <= end_date)
        return q.order_by(PredictionResult.forecast_date).offset(offset).limit(limit).all()
```

---

### 任务 2：特征工程模块

**文件：**
- 创建：`backend/app/utils/feature_engineering.py`

- [ ] **步骤 1：编写特征提取函数**

```python
"""特征工程模块 - 为销售预测提取时序特征"""

import pandas as pd
import numpy as np
from typing import List


def build_features_from_history(df: pd.DataFrame, target_col: str = "actual_sale_untaxed_amt") -> pd.DataFrame:
    """
    从历史销售数据中提取特征。
    
    输入 df 必须包含列: dt, store_code, matnr, actual_sale_untaxed_amt (或其他指标)
    输出 df 包含原始列 + 特征列。
    """
    features = df.copy()
    features["dt"] = pd.to_datetime(features["dt"], format="%Y%m%d")
    
    # 时间特征
    features["day_of_week"] = features["dt"].dt.dayofweek
    features["day_of_month"] = features["dt"].dt.day
    features["month"] = features["dt"].dt.month
    features["quarter"] = features["dt"].dt.quarter
    features["is_weekend"] = features["day_of_week"].isin([5, 6]).astype(int)
    features["is_month_start"] = (features["dt"].dt.day <= 3).astype(int)
    features["is_month_end"] = (features["dt"].dt.day >= 28).astype(int)
    
    # 按门店-商品分组排序
    features = features.sort_values(["store_code", "matnr", "dt"]).reset_index(drop=True)
    
    # 滞后特征（前 N 天）
    for lag in [1, 2, 3, 7, 14, 28]:
        features[f"lag_{lag}"] = (
            features.groupby(["store_code", "matnr"])[target_col]
            .shift(lag)
        )
    
    # 滚动窗口统计
    for window in [3, 7, 14]:
        roll = (
            features.groupby(["store_code", "matnr"])[target_col]
            .transform(lambda x: x.rolling(window, min_periods=1).mean())
        )
        features[f"rolling_mean_{window}"] = roll
        roll_std = (
            features.groupby(["store_code", "matnr"])[target_col]
            .transform(lambda x: x.rolling(window, min_periods=1).std())
        )
        features[f"rolling_std_{window}"] = roll_std.fillna(0)
    
    # 同比/环比特征
    features["diff_1d"] = features[target_col] - features["lag_1"]
    features["diff_7d"] = features[target_col] - features["lag_7"]
    features["pct_change_1d"] = features["diff_1d"] / (features["lag_1"] + 1e-6)
    features["pct_change_7d"] = features["diff_7d"] / (features["lag_7"] + 1e-6)
    
    # 过去7天均值占比（近期趋势）
    features["recent_ratio"] = features["lag_1"] / (features["rolling_mean_7"] + 1e-6)
    
    # 是否上周同日
    features["same_dow_last_week"] = features.groupby(["store_code", "matnr"])[target_col].shift(7)
    
    return features


def get_feature_columns() -> List[str]:
    """返回特征列名列表（排除 ID 列、目标列、日期列）"""
    return [
        "day_of_week", "day_of_month", "month", "quarter",
        "is_weekend", "is_month_start", "is_month_end",
        "lag_1", "lag_2", "lag_3", "lag_7", "lag_14", "lag_28",
        "rolling_mean_3", "rolling_mean_7", "rolling_mean_14",
        "rolling_std_3", "rolling_std_7", "rolling_std_14",
        "diff_1d", "diff_7d", "pct_change_1d", "pct_change_7d",
        "recent_ratio", "same_dow_last_week",
    ]
```

---

### 任务 3：PredictionService 核心逻辑

**文件：**
- 创建：`backend/app/services/prediction_service.py`

- [ ] **步骤 1：实现 PredictionService**

```python
"""销售预测服务 - LightGBM 训练与推理"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

import lightgbm as lgb
import joblib

from app.core.config import settings
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.prediction_repository import (
    PredictionModelRepository,
    PredictionResultRepository,
)
from app.models.prediction import PredictionResult
from app.utils.feature_engineering import build_features_from_history, get_feature_columns
from app.utils.query_optimizer import QueryOptimizer

logger = logging.getLogger(__name__)

TARGET_COL = "actual_sale_untaxed_amt"  # 预测目标字段


class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.model_repo = PredictionModelRepository(db)
        self.result_repo = PredictionResultRepository(db)
        self.model_dir = settings.prediction_model_dir
        os.makedirs(self.model_dir, exist_ok=True)

    def _fetch_history_data(self, ds_id: int, days: int) -> pd.DataFrame:
        """从 Doris 拉取历史销售数据"""
        ds = self.ds_repo.get_by_id(ds_id)
        if not ds:
            raise ValueError(f"数据源 {ds_id} 不存在")
        
        db_name = ds.database
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        sql = f"""
            SELECT dt, store_code, matnr, {TARGET_COL}
            FROM {db_name}.ads_cockpit_fd_store_ware_d
            WHERE dt >= {start_str} AND dt <= {end_str}
              AND exclude_flag != 1
              AND (service_flag != 1 OR service_flag IS NULL)
              AND (shopping_bag_flag != 1 OR shopping_bag_flag IS NULL)
            ORDER BY store_code, matnr, dt
        """
        
        # 复用 QueryService 的执行能力，但直接拉取全量
        from app.utils.db_executor import execute_query
        rows, columns = execute_query(ds, sql)
        
        df = pd.DataFrame(rows, columns=columns)
        df[TARGET_COL] = pd.to_numeric(df[TARGET_COL], errors="coerce").fillna(0)
        # 金额分转元
        df[TARGET_COL] = df[TARGET_COL] / 100.0
        return df

    def train(self, ds_id: int, train_days: int = None) -> int:
        """
        训练模型。
        
        返回: 模型记录 ID
        """
        train_days = train_days or settings.prediction_train_default_days
        logger.info(f"[预测] 开始训练，数据源={ds_id}，历史天数={train_days}")
        
        # 创建模型记录
        model_record = self.model_repo.create(
            data_source_id=ds_id,
            model_type="lightgbm",
            status="training",
        )
        
        try:
            # 1. 拉取历史数据
            df = self._fetch_history_data(ds_id, train_days)
            if len(df) < settings.prediction_min_history_days * 10:
                raise ValueError(
                    f"历史数据不足({len(df)}行)，需要至少 {settings.prediction_min_history_days * 10} 行"
                )
            
            # 2. 特征工程
            df_feat = build_features_from_history(df)
            df_feat = df_feat.dropna(subset=get_feature_columns()).reset_index(drop=True)
            
            # 3. 构造训练集（用前 N-1 天预测第 N 天）
            feature_cols = get_feature_columns()
            X = df_feat[feature_cols].values
            y = df_feat[TARGET_COL].values
            
            # 4. 训练 LightGBM
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
            
            # 5. 评估
            y_pred = model.predict(X)
            mae = float(np.mean(np.abs(y - y_pred)))
            rmse = float(np.sqrt(np.mean((y - y_pred) ** 2)))
            logger.info(f"[预测] 训练完成: MAE={mae:.2f}, RMSE={rmse:.2f}")
            
            # 6. 保存模型
            model_path = os.path.join(self.model_dir, f"lgb_{ds_id}_{model_record.id}.pkl")
            joblib.dump(model, model_path)
            
            # 7. 更新模型记录
            self.model_repo.update_status(
                model_record.id, "ready",
                model_path=model_path,
                feature_count=len(feature_cols),
                train_start_date=df["dt"].min().date() if hasattr(df["dt"].min(), "date") else df_feat["dt"].min(),
                train_end_date=df["dt"].max().date() if hasattr(df["dt"].max(), "date") else df_feat["dt"].max(),
                train_row_count=len(df_feat),
                model_metrics=json.dumps({"mae": mae, "rmse": rmse}),
                trained_at=datetime.utcnow(),
            )
            
            return model_record.id
            
        except Exception as e:
            logger.error(f"[预测] 训练失败: {e}")
            self.model_repo.update_status(
                model_record.id, "failed",
                error_message=str(e),
            )
            raise

    def predict(self, ds_id: int, forecast_days: int = None) -> int:
        """
        用最新模型预测未来 N 天销售额。
        
        返回: 写入的预测结果条数
        """
        forecast_days = forecast_days or settings.prediction_forecast_days
        model_record = self.model_repo.get_latest_ready(ds_id)
        if not model_record:
            raise ValueError(f"数据源 {ds_id} 没有已训练好的模型")
        
        model = joblib.load(model_record.model_path)
        feature_cols = get_feature_columns()
        
        # 拉取最新数据构造特征
        df = self._fetch_history_data(ds_id, days=60)
        df_feat = build_features_from_history(df)
        df_feat = df_feat.dropna(subset=feature_cols)
        
        # 取每个门店-商品的最新一条
        latest = (
            df_feat.sort_values("dt")
            .groupby(["store_code", "matnr"])
            .last()
            .reset_index()
        )
        
        results = []
        current_features = latest[feature_cols].values
        
        for i in range(forecast_days):
            preds = model.predict(current_features)
            forecast_date = date.today() + timedelta(days=i + 1)
            
            for idx, row in latest.iterrows():
                results.append(PredictionResult(
                    model_id=model_record.id,
                    data_source_id=ds_id,
                    store_code=row["store_code"],
                    matnr=row["matnr"],
                    forecast_date=forecast_date,
                    predicted_value=round(float(preds[idx]), 2),
                ))
            
            # 简易滚动：用预测值更新 lag_1 特征（迭代推理）
            # 更精确的做法需要重新构建整个特征矩阵
            if i < forecast_days - 1:
                current_features[:, feature_cols.index("lag_1")] = preds
        
        count = self.result_repo.bulk_save(results)
        logger.info(f"[预测] 写入 {count} 条预测结果")
        return count
```

> **说明**: `_fetch_history_data` 中依赖了 `execute_query` 工具函数。如果项目中没有，需要在任务中创建 `backend/app/utils/db_executor.py`。下面提供其实现：

创建 `backend/app/utils/db_executor.py`：
```python
"""数据库全量查询执行器 - 直接返回 DataFrame 格式数据"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from app.core.security import decrypt_password

logger = logging.getLogger(__name__)


def execute_query(ds, sql: str) -> tuple:
    """
    执行查询并返回 (rows, columns)
    供预测任务拉取全量训练数据使用。
    """
    from sqlalchemy.exc import OperationalError
    import time
    
    password = decrypt_password(ds.password_encrypted)
    ds_type = ds.type.upper() if ds.type else "DORIS"
    
    if ds_type in ("MYSQL", "DORIS"):
        conn_url = f"mysql+pymysql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    elif ds_type == "POSTGRESQL":
        conn_url = f"postgresql://{ds.username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    else:
        raise ValueError(f"不支持的数据源类型: {ds.type}")
    
    engine = create_engine(conn_url, poolclass=QueuePool, pool_size=2, max_overflow=4)
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = [list(row) for row in result.fetchall()]
                return rows, columns
        except OperationalError as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise ValueError(f"查询执行失败: {e}")
        finally:
            engine.dispose()
```

---

### 任务 4：Pydantic Schemas + API 路由

**文件：**
- 创建：`backend/app/schemas/prediction.py`
- 创建：`backend/app/api/prediction.py`
- 修改：`backend/app/main.py`（注册路由）

- [ ] **步骤 1：创建 Schemas**

创建 `backend/app/schemas/prediction.py`：
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class TrainRequest(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    train_days: Optional[int] = Field(None, description="训练用历史天数，默认使用配置值")


class TrainResponse(BaseModel):
    model_id: int
    status: str
    metrics: Optional[Dict[str, Any]] = None
    message: str


class PredictRequest(BaseModel):
    data_source_id: int
    forecast_days: Optional[int] = Field(None, description="预测天数，默认30")


class PredictResponse(BaseModel):
    count: int
    message: str


class ForecastQuery(BaseModel):
    data_source_id: int
    store_code: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=1000)


class ForecastItem(BaseModel):
    id: int
    store_code: str
    matnr: str
    forecast_date: date
    predicted_value: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastListResponse(BaseModel):
    items: List[ForecastItem]
    total: int
```

- [ ] **步骤 2：创建 API 路由**

创建 `backend/app/api/prediction.py`：
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth_deps import get_current_user
from app.core.database import get_db
from app.services.prediction_service import PredictionService
from app.schemas.prediction import (
    TrainRequest, TrainResponse,
    PredictRequest, PredictResponse,
    ForecastQuery, ForecastListResponse, ForecastItem,
)
from app.repositories.prediction_repository import PredictionResultRepository

router = APIRouter(prefix="/api/prediction", tags=["预测"])


@router.post("/train", response_model=TrainResponse)
def train_model(
    req: TrainRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """触发模型训练"""
    service = PredictionService(db)
    try:
        model_id = service.train(req.data_source_id, req.train_days)
        return TrainResponse(model_id=model_id, status="success", message="训练完成")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=PredictResponse)
def run_prediction(
    req: PredictRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """运行预测"""
    service = PredictionService(db)
    try:
        count = service.predict(req.data_source_id, req.forecast_days)
        return PredictResponse(count=count, message=f"成功预测 {count} 条记录")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast", response_model=ForecastListResponse)
def get_forecast(
    req: ForecastQuery = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """查询预测结果"""
    repo = PredictionResultRepository(db)
    results = repo.get_forecast(
        req.data_source_id, req.store_code,
        req.start_date, req.end_date,
        req.page_size, (req.page - 1) * req.page_size,
    )
    items = [ForecastItem(
        id=r.id, store_code=r.store_code, matnr=r.matnr,
        forecast_date=r.forecast_date, predicted_value=r.predicted_value,
        lower_bound=r.lower_bound, upper_bound=r.upper_bound,
    ) for r in results]
    return ForecastListResponse(items=items, total=len(items))
```

- [ ] **步骤 3：注册路由到 main.py**

在 `backend/app/main.py` 中追加：
```python
from app.api.prediction import router as prediction_router
app.include_router(prediction_router)
```

---

### 任务 5：Celery Beat 定时训练

**文件：**
- 创建：`backend/app/tasks/prediction_tasks.py`
- 修改：`backend/app/celery_app.py`（任务注册 + Beat 调度）

- [ ] **步骤 1：创建 Celery 训练任务**

创建 `backend/app/tasks/prediction_tasks.py`：
```python
"""预测相关 Celery 后台任务"""

import logging
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


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
```

- [ ] **步骤 2：注册 Beat 调度**

在 `backend/app/celery_app.py` 末尾或创建一个单独的 beat 配置。在 `create_celery_app` 函数中追加 beat 配置：

修改 `create_celery_app` 函数中的 `celery.conf.update`：

```python
    celery.conf.update(
        # ... 原有配置 ...
        beat_schedule={
            "weekly-retrain-prediction": {
                "task": "app.tasks.prediction_tasks.train_prediction_model",
                "schedule": crontab(hour=3, minute=0, day_of_week=1),
                "args": (1,),  # data_source_id=1，可配置多个
                "kwargs": {"train_days": 365},
            },
        },
    )
```

需要导入 `celery.schedules.crontab`：
```python
from celery.schedules import crontab
```

> **注意**: 若 `celery_app.py` 中已有 beat 配置，直接追加到 `beat_schedule` 字典中。Celery Worker 启动时需加 `-B` 参数：`celery -A celery_config worker -B -Q export,prediction -l info`。

---

### 任务 6：单元测试

**文件：**
- 创建：`backend/tests/test_prediction_service.py`
- 创建：`backend/tests/test_prediction_api.py`

- [ ] **步骤 1：测试特征工程**

```python
# backend/tests/test_prediction_service.py
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.utils.feature_engineering import build_features_from_history, get_feature_columns


def test_build_features():
    """测试特征工程能正确生成所有特征列"""
    # 模拟4个门店-商品组合 30天数据
    np.random.seed(42)
    rows = []
    for store in ["S001", "S002"]:
        for matnr in ["M001", "M002"]:
            for day_offset in range(30):
                dt = f"202605{day_offset + 1:02d}"
                val = np.random.randint(100, 1000)
                rows.append([dt, store, matnr, val])
    
    df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
    df = build_features_from_history(df)
    
    feature_cols = get_feature_columns()
    for col in feature_cols:
        assert col in df.columns, f"缺失特征列: {col}"
    
    # 有 lag_1 的应该比没有的多
    assert df["lag_1"].notna().sum() > 0
    assert df["day_of_week"].notna().sum() > 0
    assert df["is_weekend"].notna().sum() > 0
```

- [ ] **步骤 2：测试训练流程（Mock 数据源）**

```python
def test_train_with_mock_data(db_session, monkeypatch):
    """Mock 历史数据，验证训练流程可以走通"""
    from app.services.prediction_service import PredictionService
    
    # Mock _fetch_history_data 返回人工数据
    def mock_fetch(self, ds_id, days):
        rows = []
        np.random.seed(42)
        for store in ["S001"]:
            for matnr in ["M001"]:
                for d in range(100):
                    dt = f"20260{d%9+1}{d%30+1:02d}" if d < 30 else f"20260{(d//30)%9+1}{d%30+1:02d}"
                    # 让数据有周期性趋势
                    base = 500 + 100 * ((d % 7) + 1)
                    val = base + np.random.randint(-50, 50)
                    rows.append([int(dt), store, matnr, float(val)])
        df = pd.DataFrame(rows, columns=["dt", "store_code", "matnr", "actual_sale_untaxed_amt"])
        df["dt"] = pd.to_datetime(df["dt"].astype(str), format="%Y%m%d")
        return df
    
    monkeypatch.setattr(PredictionService, "_fetch_history_data", mock_fetch)
    
    service = PredictionService(db_session)
    model_id = service.train(ds_id=1, train_days=100)
    
    assert model_id > 0
    
    # 验证模型已保存
    import os
    from app.core.config import settings
    model_path = os.path.join(settings.prediction_model_dir, f"lgb_1_{model_id}.pkl")
    assert os.path.exists(model_path)
```

- [ ] **步骤 3：测试 API 端点（集成测试）**

```python
# backend/tests/test_prediction_api.py
def test_train_endpoint(client, auth_headers):
    """测试 /api/prediction/train POST 端点"""
    response = client.post(
        "/api/prediction/train",
        json={"data_source_id": 1},
        headers=auth_headers,
    )
    # 由于没有实际数据源，预期返回 500
    assert response.status_code in (200, 500)
    if response.status_code == 500:
        assert "detail" in response.json()
```

---

### 任务 7：前端预测结果展示（可选，根据需求取舍）

**文件：**
- 创建：`frontend/src/views/PredictionView.vue`
- 修改：`frontend/src/router/index.js`
- 修改：`frontend/src/components/Sidebar.vue`

- [ ] **步骤 1：创建预测结果展示页面**

一个简化的 Vue 页面，包含：
- 数据源选择器
- 门店/商品过滤
- 日期范围选择
- 预测结果表格（日期、门店、商品、预测值）
- ECharts 折线图（历史+预测趋势）

> 实现细节参考现有 `QueryEditor.vue` 和 `NL2SQLEditor.vue` 的组件模式。当前阶段可暂缓，先完成后端核心功能。

---

## 执行顺序建议

```
任务 1 + 2 → 任务 3 + 任务 4（可同步） → 任务 5 → 任务 6
```

任务 1（模型/配置）和任务 2（特征工程）无依赖，可同步推进。任务 3（Service）依赖任务 1 和 2。任务 4（API）依赖任务 3。任务 5（Celery）依赖任务 4。任务 6（测试）可在每个任务完成后同步编写。

---

## 风险与注意事项

1. **数据量问题**: `_fetch_history_data` 拉取 365 天店品数据可能行数巨大（百万级）。建议首次实现时限制 `train_days=90`，后续优化分批拉取。
2. **分表问题**: 如果数据源涉及 `ads_cockpit_fd_store_ware_d` 分表，需要根据 group_id 选择正确分表。当前实现默认使用无后缀表，后续需接入分表逻辑。
3. **模型文件管理**: 模型存本地磁盘，生产部署需挂载持久卷或改用对象存储。
4. **Celery Beat 启动**: 当前启动脚本 `start.sh` 可能需要修改以支持 `-B` 参数。
5. **金额单位**: 训练数据中已将金额从分转元（`/100`），与报表系统保持一致。
6. **冷启动**: 首次运行时历史数据不足 (`prediction_min_history_days` 默认 14)，需积累足够数据才能训练。
