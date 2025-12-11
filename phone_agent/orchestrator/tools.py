"""
Tools 模块：将 StepExecutor 封装为 Agno Tool

供 Orchestrator Agent 调用执行手机操作任务

设计原则：
- StepExecutor 能够执行一个完整的任务（包含多个操作步骤）
- Orchestrator 下达的是目标明确的任务指令，而非细碎的单步操作
- 工具返回足够的信息帮助 Orchestrator 做出决策
"""

import logging
from typing import TYPE_CHECKING

# 配置日志
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from phone_agent.step_executor import StepExecutor, ExecutionResult


class PhoneExecutorTool:
    """
    将 StepExecutor 封装为可被 Agno Agent 调用的工具
    
    StepExecutor 具备执行完整任务的能力，它可以：
    - 自动截取屏幕并理解内容
    - 执行多个连续操作（点击、输入、滑动等）
    - 完成一个目标明确的子任务
    
    Args:
        executor: StepExecutor 实例
        
    Example:
        >>> executor = StepExecutor()
        >>> tool = PhoneExecutorTool(executor)
        >>> # 执行完整任务，而非单步操作
        >>> result = tool.execute_phone_task("打开淘宝，搜索 iPhone 16，找到最低价格")
    """
    
    def __init__(self, executor: "StepExecutor"):
        self.executor = executor
        logger.info("PhoneExecutorTool 初始化完成")
    
    def execute_phone_task(self, task: str, max_steps: int = 30) -> str:
        """
        执行手机操作任务
        
        这是 Orchestrator 调用的主要方法。StepExecutor 会自动：
        1. 截取屏幕截图
        2. 理解当前界面
        3. 执行一系列操作（点击、输入、滑动等）
        4. 直到完成任务或达到最大步数
        
        Args:
            task: 任务描述，应该是目标明确的完整任务
                  示例：
                  - "打开淘宝，搜索 iPhone 16，找到最便宜的商品并记录价格"
                  - "打开微信，找到张三并发送消息：晚上好"
                  - "在京东搜索 iPhone 16，查看京东自营的价格"
            max_steps: 该任务的最大执行步数（默认 30 步）
            
        Returns:
            执行结果的文本描述，包含：
            - 任务完成状态
            - 关键信息（如找到的价格、发送结果等）
            - 当前应用和页面状态
        """
        logger.info(f"执行手机任务: {task}")
        
        # 调用 StepExecutor 执行任务
        result = self.executor.execute_subtask(task, max_steps=max_steps)
        
        # 构建信息充分的返回（帮助 Orchestrator 理解结果）
        return self._format_result(result)
    
    def _format_result(self, result: "ExecutionResult") -> str:
        """
        格式化执行结果为文本
        
        包含足够的 UI 状态信息，帮助 Orchestrator 做出正确决策
        """
        # 基本状态
        status = "✓ 成功" if result.success else "✗ 失败"
        lines = [f"{status}: {result.message}"]
        
        # 当前应用信息
        if result.current_app:
            lines.append(f"当前应用: {result.current_app}")
        
        # 页面摘要（帮助 Orchestrator 理解当前状态）
        if result.page_summary:
            lines.append(f"页面状态: {result.page_summary}")
        
        # 弹窗警告
        if result.has_popup:
            lines.append("⚠️ 检测到弹窗，可能需要处理")
        
        # 需要用户介入
        if result.needs_user_input:
            lines.append("⚠️ 需要用户介入（如验证码、支付确认等）")
        
        # 建议重试
        if result.should_retry:
            lines.append("💡 建议重试此操作")
        
        # 执行步数
        lines.append(f"执行步数: {result.step_count}")
        
        return "\n".join(lines)
    
    def get_current_screen_status(self) -> str:
        """
        获取当前屏幕状态（不执行任何操作）
        
        Returns:
            当前屏幕状态描述
        """
        from phone_agent.adb import get_current_app
        
        current_app = get_current_app(self.executor.executor_config.device_id)
        return f"当前应用: {current_app}"


def create_phone_tools(executor: "StepExecutor") -> list:
    """
    创建 Agno 工具函数列表
    
    将 PhoneExecutorTool 的方法转换为 Agno 可用的 tool 函数
    
    Args:
        executor: StepExecutor 实例
        
    Returns:
        工具函数列表，可传递给 Agent 的 tools 参数
    """
    try:
        from agno.tools import tool
    except ImportError as e:
        logger.error("未安装 agno 库")
        raise ImportError("需要安装 agno 库: pip install agno") from e
    
    # 创建 PhoneExecutorTool 实例
    phone_tool = PhoneExecutorTool(executor)
    
    # 主要工具：执行手机任务
    @tool(description="""执行手机操作任务。StepExecutor 会自动处理屏幕截图、理解界面、执行多步操作。
    
任务应该是目标明确的完整任务，例如：
- "打开淘宝，搜索 iPhone 16，找到最便宜的商品并告诉我价格"
- "打开微信，找到张三并发送消息：晚上好"
- "在京东搜索 iPhone 16，查看京东自营的价格"

不要拆分成细碎的单步操作（如"点击搜索框"），StepExecutor 会自动处理这些细节。""")
    def execute_phone_task(task: str) -> str:
        """
        执行手机操作任务
        
        Args:
            task: 目标明确的完整任务描述
        
        Returns:
            执行结果，包含任务完成状态、关键信息和当前页面状态
        """
        return phone_tool.execute_phone_task(task)
    
    # 辅助工具：获取当前状态
    @tool(description="获取当前手机屏幕状态，了解当前在哪个应用。在开始新任务前可以调用此工具了解当前状态。")
    def get_screen_status() -> str:
        """
        获取当前屏幕状态
        
        Returns:
            当前应用名称和基本状态
        """
        return phone_tool.get_current_screen_status()
    
    return [execute_phone_task, get_screen_status]
