"""
Phone Agent 结构化日志配置模块。

提供统一的日志记录功能，支持：
- 控制台彩色输出
- 文件日志记录
- JSON 格式结构化日志
- 不同级别的日志分离
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional
import json


# ============================================================
# 日志目录配置
# ============================================================
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


# ============================================================
# 自定义日志格式化器
# ============================================================
class ColoredFormatter(logging.Formatter):
    """
    控制台彩色日志格式化器。
    不同级别使用不同颜色显示。
    """
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',     # 青色
        'INFO': '\033[32m',      # 绿色
        'WARNING': '\033[33m',   # 黄色
        'ERROR': '\033[31m',     # 红色
        'CRITICAL': '\033[35m',  # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        # 添加颜色
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname_colored = f"{color}{record.levelname}{self.RESET}"
        record.msg_colored = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """
    JSON 格式日志格式化器。
    用于结构化日志输出，便于日志分析。
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加额外字段
        if hasattr(record, 'extra_data'):
            log_data['data'] = record.extra_data
            
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data, ensure_ascii=False)


# ============================================================
# 日志器工厂
# ============================================================
class LoggerFactory:
    """
    日志器工厂类。
    提供统一的日志器创建和配置。
    """
    
    _loggers: dict[str, logging.Logger] = {}
    _initialized: bool = False
    
    @classmethod
    def setup(
        cls,
        level: int = logging.INFO,
        console_output: bool = True,
        file_output: bool = True,
        json_output: bool = True,
    ) -> None:
        """
        初始化日志系统。
        
        Args:
            level: 日志级别
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
            json_output: 是否输出 JSON 格式日志
        """
        if cls._initialized:
            return
            
        # 根日志器配置
        root_logger = logging.getLogger("phone_agent")
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        
        # 控制台处理器
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            
            # Windows 环境下检查是否支持 ANSI 颜色
            if sys.platform.startswith('win'):
                try:
                    # 尝试启用 Windows ANSI 支持
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                    use_color = True
                except:
                    use_color = False
            else:
                use_color = True
            
            if use_color:
                console_format = ColoredFormatter(
                    '%(asctime)s | %(levelname_colored)-8s | %(name)s | %(message)s',
                    datefmt='%H:%M:%S'
                )
            else:
                console_format = logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                    datefmt='%H:%M:%S'
                )
            console_handler.setFormatter(console_format)
            root_logger.addHandler(console_handler)
        
        # 文件处理器（普通格式）
        if file_output:
            log_file = os.path.join(LOG_DIR, f"phone_agent_{datetime.now().strftime('%Y%m%d')}.log")
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_format = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            root_logger.addHandler(file_handler)
        
        # JSON 文件处理器
        if json_output:
            json_file = os.path.join(LOG_DIR, f"phone_agent_{datetime.now().strftime('%Y%m%d')}.json")
            json_handler = RotatingFileHandler(
                json_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            json_handler.setLevel(level)
            json_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(json_handler)
        
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取指定名称的日志器。
        
        Args:
            name: 日志器名称（通常使用模块名）
            
        Returns:
            配置好的日志器实例
        """
        # 确保已初始化
        if not cls._initialized:
            cls.setup()
        
        full_name = f"phone_agent.{name}" if not name.startswith("phone_agent") else name
        
        if full_name not in cls._loggers:
            cls._loggers[full_name] = logging.getLogger(full_name)
            
        return cls._loggers[full_name]


# ============================================================
# 便捷函数
# ============================================================
def get_logger(name: str) -> logging.Logger:
    """
    获取日志器的便捷函数。
    
    Args:
        name: 日志器名称
        
    Returns:
        日志器实例
    """
    return LoggerFactory.get_logger(name)


def setup_logging(
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True,
    json: bool = True
) -> None:
    """
    初始化日志系统的便捷函数。
    
    Args:
        level: 日志级别
        console: 是否输出到控制台
        file: 是否输出到文件
        json: 是否输出 JSON 格式
    """
    LoggerFactory.setup(level, console, file, json)


# ============================================================
# 带额外数据的日志辅助函数
# ============================================================
class LoggerAdapter(logging.LoggerAdapter):
    """
    支持额外数据的日志适配器。
    """
    
    def process(self, msg, kwargs):
        extra = kwargs.get('extra', {})
        if 'extra_data' in extra:
            # 保留 extra_data 用于 JSON 格式化器
            pass
        return msg, kwargs


def log_with_data(logger: logging.Logger, level: int, msg: str, data: dict = None, **kwargs):
    """
    记录带额外数据的日志。
    
    Args:
        logger: 日志器
        level: 日志级别
        msg: 日志消息
        data: 额外数据字典
    """
    extra = kwargs.pop('extra', {})
    if data:
        extra['extra_data'] = data
    logger.log(level, msg, extra=extra, **kwargs)
