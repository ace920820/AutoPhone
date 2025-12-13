"""
错误处理和恢复模块
提供智能错误检测、分类和恢复策略。
"""
import re
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from phone_agent.logging_config import get_logger

logger = get_logger("error_handler")


class ErrorType(Enum):
    """错误类型枚举"""
    APP_CRASH = "app_crash"
    NETWORK_ERROR = "network_error"
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    MODEL_ERROR = "model_error"
    ADB_ERROR = "adb_error"
    UNKNOWN = "unknown"


@dataclass
class RecoveryResult:
    """恢复结果"""
    success: bool
    action_taken: str
    message: str
    should_retry: bool = False
    new_strategy: Optional[str] = None


class ErrorClassifier:
    """错误分类器"""
    
    ERROR_PATTERNS = {
        ErrorType.APP_CRASH: [
            r"app.*crash",
            r"application.*stopped",
            r"force.*close",
            r"应用.*崩溃",
            r"程序.*停止",
        ],
        ErrorType.NETWORK_ERROR: [
            r"network.*error",
            r"connection.*failed",
            r"timeout",
            r"网络.*错误",
            r"连接.*失败",
            r"超时",
        ],
        ErrorType.ELEMENT_NOT_FOUND: [
            r"element.*not.*found",
            r"cannot.*find",
            r"找不到.*元素",
            r"无法.*定位",
        ],
        ErrorType.PERMISSION_DENIED: [
            r"permission.*denied",
            r"access.*denied",
            r"权限.*拒绝",
            r"访问.*被拒",
        ],
        ErrorType.MODEL_ERROR: [
            r"model.*error",
            r"api.*error",
            r"模型.*错误",
            r"API.*错误",
        ],
        ErrorType.ADB_ERROR: [
            r"adb.*error",
            r"device.*not.*found",
            r"设备.*未找到",
        ],
    }
    
    @classmethod
    def classify(cls, error: Exception) -> ErrorType:
        """
        分类错误类型
        
        Args:
            error: 异常对象
            
        Returns:
            ErrorType: 错误类型
        """
        error_msg = str(error).lower()
        
        for error_type, patterns in cls.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_msg, re.IGNORECASE):
                    logger.debug(f"错误分类: {error_type.value} (匹配模式: {pattern})")
                    return error_type
        
        logger.debug(f"错误分类: unknown (未匹配任何模式)")
        return ErrorType.UNKNOWN


class ErrorRecoveryManager:
    """错误恢复管理器"""
    
    def __init__(self):
        self.recovery_strategies: Dict[ErrorType, Callable] = {
            ErrorType.APP_CRASH: self._recover_from_crash,
            ErrorType.NETWORK_ERROR: self._recover_from_network,
            ErrorType.ELEMENT_NOT_FOUND: self._recover_from_missing_element,
            ErrorType.TIMEOUT: self._recover_from_timeout,
            ErrorType.PERMISSION_DENIED: self._recover_from_permission,
            ErrorType.MODEL_ERROR: self._recover_from_model_error,
            ErrorType.ADB_ERROR: self._recover_from_adb_error,
        }
        self.retry_counts: Dict[str, int] = {}
        self.max_retries = 3
    
    def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """
        处理错误并尝试恢复
        
        Args:
            error: 异常对象
            context: 错误上下文信息
            
        Returns:
            RecoveryResult: 恢复结果
        """
        error_type = ErrorClassifier.classify(error)
        logger.info(f"处理错误: {error_type.value} - {str(error)}")
        
        # 检查重试次数
        error_key = f"{error_type.value}_{context.get('task', 'unknown')}"
        retry_count = self.retry_counts.get(error_key, 0)
        
        if retry_count >= self.max_retries:
            logger.warning(f"错误 {error_type.value} 已达到最大重试次数 ({self.max_retries})")
            return RecoveryResult(
                success=False,
                action_taken="max_retries_reached",
                message=f"已达到最大重试次数 ({self.max_retries})，放弃恢复",
                should_retry=False
            )
        
        # 增加重试计数
        self.retry_counts[error_key] = retry_count + 1
        
        # 执行恢复策略
        if error_type in self.recovery_strategies:
            strategy = self.recovery_strategies[error_type]
            result = strategy(error, context)
            logger.info(f"恢复策略执行完成: {result.action_taken}, 成功={result.success}")
            return result
        
        # 默认策略：简单重试
        return self._default_recovery(error, context)
    
    def reset_retry_count(self, task: str = None):
        """重置重试计数"""
        if task:
            keys_to_remove = [k for k in self.retry_counts.keys() if task in k]
            for key in keys_to_remove:
                del self.retry_counts[key]
        else:
            self.retry_counts.clear()
        logger.debug("重试计数已重置")
    
    def _recover_from_crash(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从应用崩溃恢复"""
        logger.info("尝试从应用崩溃恢复...")
        
        app_name = context.get("app")
        if not app_name:
            return RecoveryResult(
                success=False,
                action_taken="no_app_info",
                message="无法恢复：缺少应用信息",
                should_retry=False
            )
        
        try:
            # 这里可以添加重启应用的逻辑
            # 例如：launch_app(app_name)
            
            return RecoveryResult(
                success=True,
                action_taken="restart_app",
                message=f"已尝试重启应用: {app_name}",
                should_retry=True,
                new_strategy="从头开始执行任务"
            )
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            return RecoveryResult(
                success=False,
                action_taken="restart_failed",
                message=f"重启应用失败: {str(e)}",
                should_retry=False
            )
    
    def _recover_from_network(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从网络错误恢复"""
        logger.info("尝试从网络错误恢复...")
        
        return RecoveryResult(
            success=True,
            action_taken="wait_and_retry",
            message="网络错误，等待后重试",
            should_retry=True,
            new_strategy="等待 5 秒后重试"
        )
    
    def _recover_from_missing_element(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从元素未找到恢复"""
        logger.info("尝试从元素未找到恢复...")
        
        return RecoveryResult(
            success=True,
            action_taken="relocate_element",
            message="元素未找到，尝试重新定位",
            should_retry=True,
            new_strategy="重新截图并使用 VLM 定位元素"
        )
    
    def _recover_from_timeout(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从超时恢复"""
        logger.info("尝试从超时恢复...")
        
        return RecoveryResult(
            success=True,
            action_taken="extend_timeout",
            message="操作超时，延长等待时间后重试",
            should_retry=True,
            new_strategy="增加超时时间"
        )
    
    def _recover_from_permission(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从权限拒绝恢复"""
        logger.info("权限被拒绝，需要人工介入")
        
        return RecoveryResult(
            success=False,
            action_taken="permission_denied",
            message="权限被拒绝，需要用户手动授权",
            should_retry=False,
            new_strategy="请求人工接管"
        )
    
    def _recover_from_model_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从模型错误恢复"""
        logger.info("尝试从模型错误恢复...")
        
        return RecoveryResult(
            success=True,
            action_taken="retry_model_call",
            message="模型调用失败，重试",
            should_retry=True,
            new_strategy="重新调用模型"
        )
    
    def _recover_from_adb_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """从 ADB 错误恢复"""
        logger.info("尝试从 ADB 错误恢复...")
        
        return RecoveryResult(
            success=False,
            action_taken="adb_error",
            message="ADB 连接错误，请检查设备连接",
            should_retry=False,
            new_strategy="检查设备连接状态"
        )
    
    def _default_recovery(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> RecoveryResult:
        """默认恢复策略"""
        logger.info("使用默认恢复策略...")
        
        return RecoveryResult(
            success=True,
            action_taken="simple_retry",
            message="未知错误，尝试简单重试",
            should_retry=True,
            new_strategy="重试当前操作"
        )


# 全局错误恢复管理器实例
_error_recovery_manager = ErrorRecoveryManager()


def get_error_recovery_manager() -> ErrorRecoveryManager:
    """获取全局错误恢复管理器实例"""
    return _error_recovery_manager
