"""
PhoneAgent 模块（向后兼容层）

此模块保留原有 PhoneAgent 接口，实际实现已迁移到 step_executor.py
新代码建议直接使用 StepExecutor

使用方式保持不变：
    >>> from phone_agent import PhoneAgent
    >>> agent = PhoneAgent()
    >>> agent.run("打开微信")
"""

# 从 step_executor 导入所有类，保持向后兼容
from phone_agent.step_executor import (
    StepExecutor,
    ExecutorConfig,
    StepResult,
    ExecutionResult,
)

# 向后兼容的别名
PhoneAgent = StepExecutor
AgentConfig = ExecutorConfig

__all__ = [
    # 向后兼容导出
    "PhoneAgent",
    "AgentConfig", 
    "StepResult",
    # 新增导出
    "StepExecutor",
    "ExecutorConfig",
    "ExecutionResult",
]
