"""
结构化日志工具
提供 JSON 格式日志输出，便于日志收集和分析
"""
import logging
import json
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from contextvars import ContextVar
import uuid

# 请求ID上下文变量
request_id_var: ContextVar[str] = ContextVar('request_id', default='')

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        
        # 避免重复添加 handler
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)
            self.logger.propagate = False
    
    def _log(self, level: str, message: str, **kwargs):
        """记录日志"""
        extra = {
            "request_id": request_id_var.get() or str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            **kwargs
        }
        getattr(self.logger, level.lower())(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log("CRITICAL", message, **kwargs)


class JsonFormatter(logging.Formatter):
    """JSON 格式日志Formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone(timedelta(hours=8))).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, 'request_id', ''),
        }
        
        # 添加额外字段
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def get_logger(name: str, level: str = "INFO") -> StructuredLogger:
    """获取结构化日志记录器"""
    return StructuredLogger(name, level)


# 全局日志记录器
app_logger = get_logger("myreport", "INFO")
api_logger = get_logger("myreport.api", "INFO")
query_logger = get_logger("myreport.query", "INFO")