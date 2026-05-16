"""
性能指标收集器
"""
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RequestMetric:
    """请求指标"""
    path: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SlowQueryMetric:
    """慢查询指标"""
    sql: str
    data_source_id: int
    data_source_name: str
    execution_time_ms: float
    row_count: int
    user_id: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsCollector:
    """性能指标收集器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._metrics: List[RequestMetric] = []
        self._max_metrics = 1000  # 最多保留1000条
        self._lock = threading.Lock()
        
        # 启动时间
        self.start_time = datetime.now(timezone.utc)
        
        # 计数统计
        self._request_count = 0
        self._error_count = 0
        self._total_duration = 0.0

        # 慢查询配置
        self.slow_query_threshold_ms = 5000  # 默认 5 秒
        self._slow_queries: List[SlowQueryMetric] = []
        self._max_slow_queries = 200  # 最多保留200条
    
    def record_request(self, method: str, path: str, status_code: int, duration_ms: float):
        """记录请求指标"""
        with self._lock:
            self._request_count += 1
            if status_code >= 400:
                self._error_count += 1
            self._total_duration += duration_ms
            
            metric = RequestMetric(
                path=path,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms
            )
            self._metrics.append(metric)
            
            # 保持最大数量
            if len(self._metrics) > self._max_metrics:
                self._metrics = self._metrics[-self._max_metrics:]

    def record_slow_query(self, sql: str, data_source_id: int, data_source_name: str,
                          execution_time_ms: float, row_count: int, user_id: int):
        """记录慢查询"""
        with self._lock:
            metric = SlowQueryMetric(
                sql=sql,
                data_source_id=data_source_id,
                data_source_name=data_source_name,
                execution_time_ms=execution_time_ms,
                row_count=row_count,
                user_id=user_id,
            )
            self._slow_queries.append(metric)
            if len(self._slow_queries) > self._max_slow_queries:
                self._slow_queries = self._slow_queries[-self._max_slow_queries:]

    def get_slow_queries(self, limit: int = 50) -> List[Dict]:
        """获取最近的慢查询列表"""
        with self._lock:
            return [
                {
                    "sql": m.sql,
                    "data_source_id": m.data_source_id,
                    "data_source_name": m.data_source_name,
                    "execution_time_ms": round(m.execution_time_ms, 2),
                    "row_count": m.row_count,
                    "user_id": m.user_id,
                    "timestamp": m.timestamp.isoformat(),
                }
                for m in self._slow_queries[-limit:]
            ]
    
    def get_summary(self) -> Dict:
        """获取指标摘要"""
        with self._lock:
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            
            # 按路径分组统计
            path_stats: Dict[str, Dict] = {}
            for m in self._metrics:
                key = f"{m.method} {m.path}"
                if key not in path_stats:
                    path_stats[key] = {"count": 0, "total_ms": 0, "errors": 0}
                path_stats[key]["count"] += 1
                path_stats[key]["total_ms"] += m.duration_ms
                if m.status_code >= 400:
                    path_stats[key]["errors"] += 1
            
            # 计算平均响应时间
            avg_duration = self._total_duration / self._request_count if self._request_count > 0 else 0
            
            # 最近请求统计
            recent_metrics = self._metrics[-100:]
            recent_avg = sum(m.duration_ms for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
            
            return {
                "uptime_seconds": round(uptime, 2),
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "error_rate": round(self._error_count / self._request_count * 100, 2) if self._request_count > 0 else 0,
                "avg_response_time_ms": round(avg_duration, 2),
                "recent_avg_response_time_ms": round(recent_avg, 2),
                "requests_per_second": round(self._request_count / uptime, 2) if uptime > 0 else 0,
                "top_endpoints": self._get_top_endpoints(path_stats, 5),
            }
    
    def _get_top_endpoints(self, path_stats: Dict, limit: int) -> List[Dict]:
        """获取最频繁访问的端点"""
        sorted_endpoints = sorted(
            path_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:limit]
        
        return [
            {
                "endpoint": endpoint,
                "count": stats["count"],
                "avg_ms": round(stats["total_ms"] / stats["count"], 2),
                "error_count": stats["errors"]
            }
            for endpoint, stats in sorted_endpoints
        ]
    
    def get_recent_metrics(self, limit: int = 50) -> List[Dict]:
        """获取最近的请求指标"""
        with self._lock:
            return [
                {
                    "method": m.method,
                    "path": m.path,
                    "status_code": m.status_code,
                    "duration_ms": round(m.duration_ms, 2),
                    "timestamp": m.timestamp.isoformat()
                }
                for m in self._metrics[-limit:]
            ]
    
    def reset(self):
        """重置指标"""
        with self._lock:
            self._metrics.clear()
            self._slow_queries.clear()
            self._request_count = 0
            self._error_count = 0
            self._total_duration = 0.0


# 全局指标收集器
metrics_collector = MetricsCollector()
