"""
StepExecutor: 步骤执行器，基于原 PhoneAgent 改造
负责使用 AutoGLM 执行具体的手机操作子任务
"""

import json
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import do, finish, parse_action
from phone_agent.adb import get_current_app, get_screenshot
from phone_agent.config import get_messages, get_system_prompt
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder

# 配置日志
logger = logging.getLogger(__name__)


@dataclass
class ExecutorConfig:
    """StepExecutor 配置"""
    
    max_steps: int = 100              # 单个子任务最大步数
    subtask_max_steps: int = 10       # execute_subtask 默认最大步数
    device_id: str | None = None      # ADB 设备 ID
    lang: str = "cn"                  # 语言
    system_prompt: str | None = None  # 系统提示词
    verbose: bool = True              # 是否打印详细信息
    
    def __post_init__(self):
        # 如果未指定系统提示词，使用默认的
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang)


@dataclass
class StepResult:
    """单步执行结果（内部使用）"""
    
    success: bool                     # 是否成功
    finished: bool                    # 是否完成任务
    action: dict[str, Any] | None     # 执行的动作
    thinking: str                     # 模型思考过程
    message: str | None = None        # 结果消息


@dataclass
class ExecutionResult:
    """
    脱敏的执行结果，返回给 Orchestrator
    不包含截图、坐标等敏感信息
    """
    
    success: bool                     # 是否成功
    message: str                      # 执行结果描述
    
    # 关键 UI 状态（脱敏但信息充分，解决 Context 丢失问题）
    current_app: str | None = None    # 当前应用名
    page_summary: str | None = None   # 页面主要内容摘要（从 thinking 中提取）
    has_popup: bool = False           # 是否有弹窗
    available_actions: list[str] = field(default_factory=list)  # 当前可用操作提示
    
    # 控制信息
    needs_user_input: bool = False    # 是否需要用户介入
    should_retry: bool = False        # 是否建议重试
    step_count: int = 0               # 执行了多少步


class StepExecutor:
    """
    步骤执行器：接收子任务，使用 AutoGLM 完成
    
    核心逻辑保持与原 PhoneAgent 一致，新增 execute_subtask() 方法
    供 Orchestrator 调用
    
    Args:
        model_config: 模型配置（AutoGLM）
        executor_config: 执行器配置
        confirmation_callback: 敏感操作确认回调
        takeover_callback: 人工接管回调
    
    Example:
        >>> from phone_agent.step_executor import StepExecutor
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> executor = StepExecutor()
        >>> # 直接模式（兼容原 PhoneAgent）
        >>> result = executor.run("打开微信")
        >>> # 子任务模式（供 Orchestrator 调用）
        >>> exec_result = executor.execute_subtask("打开微信")
    """
    
    def __init__(
        self,
        model_config: ModelConfig | None = None,
        executor_config: ExecutorConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.model_config = model_config or ModelConfig()
        self.executor_config = executor_config or ExecutorConfig()
        
        # 初始化模型客户端和动作处理器
        self.model_client = ModelClient(self.model_config)
        self.action_handler = ActionHandler(
            device_id=self.executor_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )
        
        # 内部状态
        self._context: list[dict[str, Any]] = []
        self._step_count = 0
        self._last_thinking = ""  # 保存最后一次思考，用于提取页面摘要
        
        logger.info("StepExecutor 初始化完成")
    
    def execute_subtask(
        self, 
        subtask: str, 
        max_steps: int | None = None
    ) -> ExecutionResult:
        """
        执行一个子任务（供 Orchestrator 调用）
        
        Args:
            subtask: 子任务描述，如 "打开微信"、"搜索张三"
            max_steps: 该子任务的最大步数，默认使用配置值
            
        Returns:
            ExecutionResult: 脱敏的执行结果
        """
        max_steps = max_steps or self.executor_config.subtask_max_steps
        
        logger.info(f"开始执行子任务: {subtask} (最大步数: {max_steps})")
        
        # 重置状态
        self._context = []
        self._step_count = 0
        self._last_thinking = ""
        
        # 执行子任务
        try:
            while self._step_count < max_steps:
                is_first = self._step_count == 0
                result = self._execute_step(
                    user_prompt=subtask if is_first else None,
                    is_first=is_first
                )
                
                if result.finished:
                    # 获取当前 UI 状态
                    current_app = get_current_app(self.executor_config.device_id)
                    
                    logger.info(f"子任务完成: {result.message}")
                    
                    return ExecutionResult(
                        success=result.success,
                        message=result.message or "子任务完成",
                        current_app=current_app,
                        page_summary=self._extract_page_summary(),
                        has_popup=self._detect_popup(),
                        available_actions=self._get_available_actions(),
                        needs_user_input=False,
                        should_retry=False,
                        step_count=self._step_count,
                    )
            
            # 超过最大步数
            current_app = get_current_app(self.executor_config.device_id)
            logger.warning(f"子任务超时: {subtask}")
            
            return ExecutionResult(
                success=False,
                message=f"子任务执行超时（已执行 {max_steps} 步）",
                current_app=current_app,
                page_summary=self._extract_page_summary(),
                has_popup=self._detect_popup(),
                should_retry=True,
                step_count=self._step_count,
            )
            
        except Exception as e:
            logger.error(f"子任务执行异常: {e}")
            traceback.print_exc()
            
            return ExecutionResult(
                success=False,
                message=f"执行异常: {str(e)}",
                should_retry=True,
                step_count=self._step_count,
            )
    
    def run(self, task: str) -> str:
        """
        直接运行任务（兼容原 PhoneAgent 接口）
        
        Args:
            task: 自然语言任务描述
            
        Returns:
            最终消息
        """
        logger.info(f"直接模式执行任务: {task}")
        
        self._context = []
        self._step_count = 0
        
        # 第一步
        result = self._execute_step(task, is_first=True)
        
        if result.finished:
            return result.message or "任务完成"
        
        # 继续执行直到完成或达到最大步数
        while self._step_count < self.executor_config.max_steps:
            result = self._execute_step(is_first=False)
            
            if result.finished:
                return result.message or "任务完成"
        
        return "达到最大步数限制"
    
    def step(self, task: str | None = None) -> StepResult:
        """
        执行单步（用于调试）
        
        Args:
            task: 任务描述（仅首次需要）
            
        Returns:
            StepResult: 单步结果
        """
        is_first = len(self._context) == 0
        
        if is_first and not task:
            raise ValueError("首次执行需要提供任务描述")
        
        return self._execute_step(task, is_first)
    
    def reset(self) -> None:
        """重置执行器状态"""
        self._context = []
        self._step_count = 0
        self._last_thinking = ""
        logger.info("执行器状态已重置")
    
    def _execute_step(
        self, 
        user_prompt: str | None = None, 
        is_first: bool = False
    ) -> StepResult:
        """执行单步（内部方法）"""
        self._step_count += 1
        
        # 获取当前屏幕状态
        screenshot = get_screenshot(self.executor_config.device_id)
        current_app = get_current_app(self.executor_config.device_id)
        
        # 构建消息
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.executor_config.system_prompt)
            )
            
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"{user_prompt}\n\n{screen_info}"
            
            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, 
                    image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"** Screen Info **\n\n{screen_info}"
            
            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, 
                    image_base64=screenshot.base64_data
                )
            )
        
        # 调用模型获取响应
        try:
            response = self.model_client.request(self._context)
            self._last_thinking = response.thinking  # 保存思考过程
        except Exception as e:
            if self.executor_config.verbose:
                traceback.print_exc()
            return StepResult(
                success=False,
                finished=True,
                action=None,
                thinking="",
                message=f"模型调用错误: {e}",
            )
        
        # 解析动作
        try:
            action = parse_action(response.action)
        except ValueError:
            if self.executor_config.verbose:
                traceback.print_exc()
            action = finish(message=response.action)
        
        # 打印详细信息
        if self.executor_config.verbose:
            msgs = get_messages(self.executor_config.lang)
            print("\n" + "=" * 50)
            print(f"💭 {msgs['thinking']}:")
            print("-" * 50)
            print(response.thinking)
            print("-" * 50)
            print(f"🎯 {msgs['action']}:")
            print(json.dumps(action, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")
        
        # 移除图片以节省上下文空间
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])
        
        # 执行动作
        try:
            result = self.action_handler.execute(
                action, screenshot.width, screenshot.height
            )
        except Exception as e:
            if self.executor_config.verbose:
                traceback.print_exc()
            result = self.action_handler.execute(
                finish(message=str(e)), screenshot.width, screenshot.height
            )
        
        # 添加助手响应到上下文
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )
        
        # 检查是否完成
        finished = action.get("_metadata") == "finish" or result.should_finish
        
        if finished and self.executor_config.verbose:
            msgs = get_messages(self.executor_config.lang)
            print("\n" + "🎉 " + "=" * 48)
            print(
                f"✅ {msgs['task_completed']}: {result.message or action.get('message', msgs['done'])}"
            )
            print("=" * 50 + "\n")
        
        return StepResult(
            success=result.success,
            finished=finished,
            action=action,
            thinking=response.thinking,
            message=result.message or action.get("message"),
        )
    
    def _extract_page_summary(self) -> str | None:
        """
        从最后一次思考中提取页面摘要
        用于解决 Context 丢失问题
        """
        if not self._last_thinking:
            return None
        
        # 从 thinking 中提取关键信息（简化处理）
        # 实际可以使用更复杂的提取逻辑
        thinking = self._last_thinking
        
        # 提取前 200 个字符作为摘要
        if len(thinking) > 200:
            return thinking[:200] + "..."
        return thinking
    
    def _detect_popup(self) -> bool:
        """
        检测当前是否有弹窗
        从最后一次思考中判断
        """
        if not self._last_thinking:
            return False
        
        # 检查思考中是否提到弹窗相关词汇
        popup_keywords = ["弹窗", "对话框", "提示框", "确认框", "广告", "popup", "dialog"]
        thinking_lower = self._last_thinking.lower()
        
        return any(keyword in thinking_lower for keyword in popup_keywords)
    
    def _get_available_actions(self) -> list[str]:
        """
        获取当前可用的操作提示
        """
        # 返回基本可用操作（可根据实际情况扩展）
        return ["点击", "滑动", "输入", "返回", "主页"]
    
    @property
    def context(self) -> list[dict[str, Any]]:
        """获取当前对话上下文"""
        return self._context.copy()
    
    @property
    def step_count(self) -> int:
        """获取当前步数"""
        return self._step_count


# 为了向后兼容，保留 PhoneAgent 别名
PhoneAgent = StepExecutor
AgentConfig = ExecutorConfig
