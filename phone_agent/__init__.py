"""
Phone Agent - AI 驱动的手机自动化框架

提供两种使用模式：
1. 直接模式：使用 StepExecutor (原 PhoneAgent) 直接执行任务
2. 编排模式：使用 Orchestrator + StepExecutor，支持任务分解和记忆功能

使用示例：
    # 直接模式（向后兼容）
    >>> from phone_agent import PhoneAgent
    >>> agent = PhoneAgent()
    >>> agent.run("打开微信")
    
    # 编排模式（推荐）
    >>> from phone_agent import StepExecutor
    >>> from phone_agent.orchestrator import create_orchestrator
    >>> executor = StepExecutor()
    >>> orchestrator = create_orchestrator(executor)
    >>> orchestrator.run("帮我给张三发微信说晚上好")
"""

# 向后兼容导出
from phone_agent.agent import (
    PhoneAgent,
    AgentConfig,
    StepResult,
    # 新增
    StepExecutor,
    ExecutorConfig,
    ExecutionResult,
)

__version__ = "0.1.0"

__all__ = [
    # 向后兼容
    "PhoneAgent",
    "AgentConfig",
    "StepResult",
    # 新增
    "StepExecutor", 
    "ExecutorConfig",
    "ExecutionResult",
]
