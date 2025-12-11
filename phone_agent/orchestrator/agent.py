"""
Orchestrator Agent 模块：基于 Agno AgentOS 的任务编排

提供两种使用方式：
1. 直接调用模式：PhoneOrchestrator.run() 执行单次任务
2. AgentOS 服务模式：启动 FastAPI 服务，提供 REST API

AgentOS 自动提供：
- 会话历史记忆
- 用户偏好记忆  
- 工具调用
- REST API 接口
"""

import os
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from phone_agent.orchestrator.tools import create_phone_tools

# 配置日志
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from phone_agent.step_executor import StepExecutor

# 默认数据目录
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Orchestrator 系统提示词
ORCHESTRATOR_INSTRUCTIONS = [
    "你是手机智能助手的高级任务编排专家。",
    "",
    "## 架构说明",
    "你与 StepExecutor（手机操作执行器）配合工作：",
    "- **你的职责**：理解用户需求、规划任务、汇总信息、与用户交互",
    "- **StepExecutor 职责**：执行具体的手机操作任务，它能自动处理屏幕截图、点击、输入、滑动等",
    "",
    "## 任务粒度原则（重要！）",
    "StepExecutor 能够独立完成**一个完整的子任务**，包含多个连续操作。",
    "你不需要拆分到每个点击动作，而是下达**目标明确的任务指令**。",
    "",
    "### 正确的任务粒度示例：",
    "- ✓ '打开淘宝，搜索 iPhone 16，找到最便宜的商品并告诉我价格'",
    "- ✓ '打开微信，找到张三并发送消息：晚上好'",
    "- ✓ '打开京东，搜索 iPhone 16，记录最低价格'",
    "- ✓ '在当前页面向下滑动，查看更多商品'",
    "",
    "### 错误的任务粒度（太细碎）：",
    "- ✗ '点击搜索框' → 太细，应该包含在完整任务中",
    "- ✗ '输入 iPhone' → 太细",
    "- ✗ '点击搜索按钮' → 太细",
    "",
    "## 你的工作流程",
    "1. **理解需求**：分析用户想要达成的最终目标",
    "2. **规划任务**：将复杂任务拆分为合适粒度的子任务（通常 1-5 个）",
    "3. **执行任务**：调用 execute_phone_task 让 StepExecutor 执行",
    "4. **汇总结果**：收集执行结果，整理信息反馈给用户",
    "5. **处理异常**：根据返回状态调整策略或请求用户介入",
    "",
    "## 复杂任务示例",
    "",
    "### 示例 1：多平台比价",
    "用户：'帮我在淘宝和京东比价 iPhone 16，告诉我哪个便宜'",
    "",
    "你的规划：",
    "1. 调用 execute_phone_task('打开淘宝，搜索 iPhone 16，找到 Apple 官方旗舰店的价格')",
    "2. 记录淘宝价格",
    "3. 调用 execute_phone_task('打开京东，搜索 iPhone 16，找到京东自营的价格')",
    "4. 记录京东价格",
    "5. 比较两个价格，告诉用户结果",
    "",
    "### 示例 2：发送消息",
    "用户：'给张三发微信说晚上好'",
    "",
    "你的规划：",
    "1. 调用 execute_phone_task('打开微信，找到联系人张三，发送消息：晚上好')",
    "2. 确认发送结果，反馈给用户",
    "",
    "## 注意事项",
    "- 你看不到手机屏幕，只能通过工具返回的文字描述了解执行结果",
    "- 遇到需要用户介入的情况（验证码、支付确认），立即停止并告知用户",
    "- 如果任务失败，可以尝试调整指令重试",
    "- 善用记忆功能记住用户偏好（常用联系人、购物习惯等）",
]


def _ensure_data_dir(data_dir: Path | str | None = None) -> Path:
    """确保数据目录存在"""
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def create_orchestrator_agent(
    executor: "StepExecutor",
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    db_path: str | None = None,
    enable_memory: bool = True,
):
    """
    创建 Orchestrator Agent（不启动服务）
    
    Args:
        executor: StepExecutor 实例
        model_id: LLM 模型 ID
        api_key: API 密钥
        base_url: API 基础 URL
        db_path: 数据库路径
        enable_memory: 是否启用记忆功能
        
    Returns:
        Agno Agent 实例
    """
    try:
        from agno.agent import Agent
        from agno.models.openai import OpenAIChat
        from agno.db.sqlite import SqliteDb
    except ImportError as e:
        logger.error("未安装 agno 库")
        raise ImportError(
            "需要安装 agno 库: pip install agno"
        ) from e
    
    # 从环境变量获取配置
    model_id = model_id or os.getenv("LLM_MODEL", "qwen-plus")
    api_key = api_key or os.getenv("LLM_API_KEY")
    base_url = base_url or os.getenv("LLM_BASE_URL")
    
    if not api_key:
        raise ValueError("未找到 API 密钥，请设置 LLM_API_KEY 环境变量")
    
    # 创建模型（使用 OpenAI 兼容接口）
    model = OpenAIChat(
        id=model_id,
        api_key=api_key,
        base_url=base_url,
    )
    
    # 创建工具
    tools = create_phone_tools(executor)
    
    # 创建数据库（用于 Memory）
    if db_path is None:
        data_dir = _ensure_data_dir()
        db_path = str(data_dir / "orchestrator.db")
    
    db = SqliteDb(db_file=db_path)
    
    # 创建 Agent
    agent = Agent(
        name="PhoneOrchestrator",
        model=model,
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        tools=tools,
        # 数据库配置（AgentOS 自动管理记忆）
        db=db,
        # 启用记忆功能
        enable_user_memories=enable_memory,
        enable_session_summaries=enable_memory,
        # 添加历史到上下文
        add_history_to_context=True,
        num_history_runs=5,
        # 显示选项
        markdown=True,
        show_tool_calls=True,
    )
    
    logger.info(f"Orchestrator Agent 创建完成: model={model_id}, memory={enable_memory}")
    return agent


def create_agent_os(
    executor: "StepExecutor",
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    db_path: str | None = None,
    enable_memory: bool = True,
):
    """
    创建 AgentOS 实例（包含 FastAPI 应用）
    
    Args:
        executor: StepExecutor 实例
        model_id: LLM 模型 ID
        api_key: API 密钥
        base_url: API 基础 URL
        db_path: 数据库路径
        enable_memory: 是否启用记忆功能
        
    Returns:
        (AgentOS, FastAPI app) 元组
        
    Example:
        >>> executor = StepExecutor()
        >>> agent_os, app = create_agent_os(executor)
        >>> # 启动服务
        >>> agent_os.serve(app="phone_agent.orchestrator:app", port=7777)
    """
    try:
        from agno.os import AgentOS
    except ImportError as e:
        logger.error("未安装 agno 库")
        raise ImportError(
            "需要安装 agno 库: pip install agno"
        ) from e
    
    # 创建 Agent
    agent = create_orchestrator_agent(
        executor=executor,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        db_path=db_path,
        enable_memory=enable_memory,
    )
    
    # 创建 AgentOS
    agent_os = AgentOS(
        agents=[agent],
        name="PhoneAgentOS",
    )
    
    # 获取 FastAPI app
    app = agent_os.get_app()
    
    logger.info("AgentOS 创建完成")
    return agent_os, app


class PhoneOrchestrator:
    """
    手机任务编排器（直接调用模式）
    
    封装 Agno Agent，提供简单的 Python 接口执行手机任务
    如需 REST API，请使用 create_agent_os() 启动 AgentOS 服务
    
    Args:
        executor: StepExecutor 实例
        model_id: LLM 模型 ID
        api_key: API 密钥
        base_url: API 基础 URL
        enable_memory: 是否启用记忆功能
        
    Example:
        >>> from phone_agent.step_executor import StepExecutor
        >>> from phone_agent.orchestrator import PhoneOrchestrator
        >>>
        >>> executor = StepExecutor()
        >>> orchestrator = PhoneOrchestrator(executor)
        >>> result = orchestrator.run("帮我给张三发微信说晚上好")
    """
    
    def __init__(
        self,
        executor: "StepExecutor",
        model_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        enable_memory: bool = True,
        verbose: bool = True,
    ):
        self.executor = executor
        self.verbose = verbose
        self.enable_memory = enable_memory
        
        # 配置
        self.model_id = model_id or os.getenv("LLM_MODEL", "qwen-plus")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        
        if not self.api_key:
            raise ValueError(
                "未找到 API 密钥。请设置环境变量 LLM_API_KEY 或传入 api_key 参数"
            )
        
        self._agent = None
        logger.info(f"PhoneOrchestrator 初始化: model={self.model_id}, memory={enable_memory}")
    
    def _get_agent(self):
        """延迟创建 Agent"""
        if self._agent is None:
            self._agent = create_orchestrator_agent(
                executor=self.executor,
                model_id=self.model_id,
                api_key=self.api_key,
                base_url=self.base_url,
                enable_memory=self.enable_memory,
            )
        return self._agent
    
    def run(self, task: str, user_id: str | None = None, session_id: str | None = None) -> str:
        """
        执行任务
        
        Args:
            task: 用户任务描述
            user_id: 用户 ID（用于记忆隔离）
            session_id: 会话 ID（用于会话隔离）
            
        Returns:
            执行结果
        """
        logger.info(f"Orchestrator 执行任务: {task}")
        
        agent = self._get_agent()
        
        # 构建运行参数
        run_kwargs = {"stream": False}
        if user_id:
            run_kwargs["user_id"] = user_id
        if session_id:
            run_kwargs["session_id"] = session_id
        
        # 执行
        try:
            response = agent.run(task, **run_kwargs)
            result = response.content if hasattr(response, 'content') else str(response)
            
            if self.verbose:
                print("\n" + "=" * 50)
                print("📋 Orchestrator 执行结果:")
                print("-" * 50)
                print(result)
                print("=" * 50 + "\n")
            
            return result
            
        except Exception as e:
            logger.error(f"Orchestrator 执行失败: {e}")
            raise
    
    def run_interactive(self, user_id: str | None = None) -> None:
        """
        交互模式运行
        
        Args:
            user_id: 用户 ID
        """
        print("\n" + "=" * 50)
        print("🤖 手机智能助手 (Orchestrator 模式)")
        print("=" * 50)
        print("输入任务让我帮你操作手机，输入 'quit' 或 'exit' 退出")
        print("-" * 50 + "\n")
        
        session_id = f"interactive_{os.getpid()}"  # 使用进程 ID 作为会话标识
        
        while True:
            try:
                task = input("📝 请输入任务: ").strip()
                
                if not task:
                    continue
                
                if task.lower() in ("quit", "exit", "q"):
                    print("\n👋 再见！")
                    break
                
                self.run(task, user_id=user_id, session_id=session_id)
                
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                print(f"\n❌ 执行出错: {e}\n")


def create_orchestrator(
    executor: "StepExecutor",
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    enable_memory: bool = True,
    verbose: bool = True,
) -> PhoneOrchestrator:
    """
    创建 PhoneOrchestrator 实例的便捷函数
    
    Args:
        executor: StepExecutor 实例
        model_id: LLM 模型 ID，默认从环境变量 LLM_MODEL 读取
        api_key: API 密钥，默认从环境变量 LLM_API_KEY 读取
        base_url: API 基础 URL，默认从环境变量 LLM_BASE_URL 读取
        enable_memory: 是否启用记忆功能
        verbose: 是否打印详细信息
        
    Returns:
        PhoneOrchestrator 实例
    """
    return PhoneOrchestrator(
        executor=executor,
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        enable_memory=enable_memory,
        verbose=verbose,
    )


# ============================================================
# AgentOS 服务入口（用于 uvicorn 启动）
# ============================================================

# 全局变量，用于 AgentOS 服务模式
_agent_os = None
_app = None


def get_app():
    """
    获取 FastAPI app（用于 uvicorn 启动）
    
    需要先设置环境变量或调用 init_agent_os()
    
    Usage:
        uvicorn phone_agent.orchestrator.agent:get_app --factory --port 7777
    """
    global _app
    if _app is None:
        raise RuntimeError(
            "AgentOS 未初始化。请先调用 init_agent_os() 或使用 serve_agent_os()"
        )
    return _app


def init_agent_os(executor: "StepExecutor", **kwargs):
    """
    初始化全局 AgentOS（用于服务模式）
    """
    global _agent_os, _app
    _agent_os, _app = create_agent_os(executor, **kwargs)
    return _agent_os, _app


def serve_agent_os(
    executor: "StepExecutor",
    port: int = 7777,
    host: str = "0.0.0.0",
    **kwargs
):
    """
    启动 AgentOS 服务
    
    Args:
        executor: StepExecutor 实例
        port: 服务端口
        host: 服务地址
        **kwargs: 传递给 create_agent_os 的参数
    """
    agent_os, app = create_agent_os(executor, **kwargs)
    
    print("\n" + "=" * 50)
    print("🚀 启动 AgentOS 服务")
    print("=" * 50)
    print(f"地址: http://{host}:{port}")
    print(f"API 文档: http://{host}:{port}/docs")
    print("=" * 50 + "\n")
    
    # 使用 AgentOS 的 serve 方法
    import uvicorn
    uvicorn.run(app, host=host, port=port)
