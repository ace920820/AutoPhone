"""
Orchestrator 模块：基于 Agno AgentOS 的任务编排层

提供两种使用方式：
1. 直接调用模式：PhoneOrchestrator.run() 执行单次任务
2. AgentOS 服务模式：启动 FastAPI 服务，提供 REST API

AgentOS 自动提供：
- 会话历史记忆
- 用户偏好记忆
- 工具调用
- REST API 接口
"""

from phone_agent.orchestrator.agent import (
    # 直接调用模式
    create_orchestrator,
    PhoneOrchestrator,
    create_orchestrator_agent,
    # AgentOS 服务模式
    create_agent_os,
    serve_agent_os,
    init_agent_os,
    get_app,
)
from phone_agent.orchestrator.tools import PhoneExecutorTool, create_phone_tools

__all__ = [
    # 直接调用模式
    "create_orchestrator",
    "PhoneOrchestrator",
    "create_orchestrator_agent",
    # AgentOS 服务模式
    "create_agent_os",
    "serve_agent_os",
    "init_agent_os",
    "get_app",
    # 工具
    "PhoneExecutorTool",
    "create_phone_tools",
]
