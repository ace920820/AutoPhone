"""用于编排手机自动化的主 PhoneAgent 类。"""

import json
import traceback
from dataclasses import dataclass
from typing import Any, Callable, Optional

from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import do, finish, parse_action
from phone_agent.adb import get_current_app, get_screenshot
from phone_agent.config import get_messages, get_system_prompt
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder
from phone_agent.logging_config import get_logger, setup_logging
from phone_agent.tracing import ExecutionTracer
from phone_agent.error_handler import get_error_recovery_manager, ErrorType

# 初始化日志系统
setup_logging()
logger = get_logger("agent")


@dataclass
class AgentConfig:
    """PhoneAgent 的配置。"""

    max_steps: int = 100
    device_id: str | None = None
    lang: str = "cn"
    system_prompt: str | None = None
    verbose: bool = True
    enable_tracing: bool = True  # 是否启用执行跟踪
    save_trace_report: bool = True  # 是否保存跟踪报告

    def __post_init__(self):
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang)


@dataclass
class StepResult:
    """单个 Agent 步骤的结果。"""

    success: bool
    finished: bool
    action: dict[str, Any] | None
    thinking: str
    message: str | None = None


class PhoneAgent:
    """
    AI 驱动的 Android 手机交互自动化 Agent。

    该 Agent 使用视觉语言模型来理解屏幕内容并决定执行操作以完成用户任务。

    Args:
        model_config: AI 模型的配置。
        agent_config: Agent 行为的配置。
        confirmation_callback: 可选的敏感操作确认回调。
        takeover_callback: 可选的接管请求回调。

    Example:
        >>> from phone_agent import PhoneAgent
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> model_config = ModelConfig(base_url="http://localhost:8000/v1")
        >>> agent = PhoneAgent(model_config)
        >>> agent.run("打开微信给张三发消息")
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: AgentConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
        step_callback: Callable[[StepResult], None] | None = None,
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()

        self.model_client = ModelClient(self.model_config)
        self.action_handler = ActionHandler(
            device_id=self.agent_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )

        self._context: list[dict[str, Any]] = []
        self._step_count = 0
        self._tracer: Optional[ExecutionTracer] = None
        self._step_callback = step_callback
        self._is_paused = False
        self._current_app: str = ""
        self._last_error: Optional[str] = None
        self._error_recovery_manager = get_error_recovery_manager()
        
        logger.info(
            f"PhoneAgent 初始化完成 - 模型: {self.model_config.model_name}, "
            f"设备: {self.agent_config.device_id or '默认'}"
        )

    def run(self, task: str) -> str:
        """
        运行 Agent 来完成任务。

        Args:
            task: 任务的自然语言描述。

        Returns:
            Agent 的最终消息。
        """
        self._context = []
        self._step_count = 0
        
        logger.info(f"开始执行任务: {task}")
        
        # 初始化执行跟踪
        if self.agent_config.enable_tracing:
            self._tracer = ExecutionTracer(
                task_description=task,
                metadata={
                    "model": self.model_config.model_name,
                    "device_id": self.agent_config.device_id,
                    "max_steps": self.agent_config.max_steps
                }
            )
            self._tracer.start()

        try:
            # 第一步使用用户提示
            result = self._execute_step(task, is_first=True)

            if result.finished:
                final_message = result.message or "Task completed"
                self._finish_trace(final_message, success=result.success)
                return final_message

            # 继续直到完成或达到最大步数
            while self._step_count < self.agent_config.max_steps:
                result = self._execute_step(is_first=False)

                if result.finished:
                    final_message = result.message or "Task completed"
                    self._finish_trace(final_message, success=result.success)
                    return final_message

            logger.warning(f"任务达到最大步数限制: {self.agent_config.max_steps}")
            self._finish_trace("Max steps reached", success=False)
            return "Max steps reached"
            
        except Exception as e:
            logger.error(f"任务执行异常: {e}", exc_info=True)
            
            # 尝试错误恢复
            recovery_result = self._error_recovery_manager.handle_error(
                e,
                context={
                    "task": task,
                    "step_count": self._step_count,
                    "current_app": self._current_app,
                }
            )
            
            logger.info(f"错误恢复结果: {recovery_result.message}")
            
            if self._tracer:
                self._tracer.fail(f"{str(e)}\n恢复尝试: {recovery_result.message}")
                if self.agent_config.save_trace_report:
                    self._tracer.save_html_report()
            
            # 如果建议重试，可以在这里实现重试逻辑
            if recovery_result.should_retry:
                logger.info(f"建议重试策略: {recovery_result.new_strategy}")
            
            raise

    def step(self, task: str | None = None) -> StepResult:
        """
        执行 Agent 的单个步骤。

        适用于手动控制或调试。

        Args:
            task: 任务描述（仅第一步需要）。

        Returns:
            包含步骤详情的 StepResult。
        """
        is_first = len(self._context) == 0

        if is_first and not task:
            raise ValueError("Task is required for the first step")

        return self._execute_step(task, is_first)

    def reset(self) -> None:
        """重置 Agent 状态以开始新任务。"""
        self._context = []
        self._step_count = 0
        self._tracer = None
        self._is_paused = False
        self._last_error = None
        self._error_recovery_manager.reset_retry_count()
        logger.debug("Agent 状态已重置")
    
    def set_step_callback(self, callback: Callable[[StepResult], None]) -> None:
        """设置步骤回调函数，用于流式反馈。"""
        self._step_callback = callback
        logger.debug("步骤回调已设置")
    
    def pause(self) -> None:
        """暂停任务执行。"""
        self._is_paused = True
        logger.info("任务已暂停")
    
    def resume(self) -> None:
        """恢复任务执行。"""
        self._is_paused = False
        logger.info("任务已恢复")
    
    def get_state(self) -> dict[str, Any]:
        """
        获取当前 Agent 状态。
        
        Returns:
            包含当前状态信息的字典
        """
        return {
            "step_count": self._step_count,
            "is_paused": self._is_paused,
            "is_busy": self._step_count > 0 and not self._is_paused,
            "current_app": self._current_app,
            "last_error": self._last_error,
            "device_id": self.agent_config.device_id,
            "max_steps": self.agent_config.max_steps,
        }
    
    def _finish_trace(self, result: str, success: bool) -> None:
        """完成执行跟踪并保存报告。"""
        if self._tracer:
            self._tracer.finish(result, success)
            if self.agent_config.save_trace_report:
                report_path = self._tracer.save_html_report()
                logger.info(f"执行跟踪报告已保存: {report_path}")

    def _execute_step(
        self, user_prompt: str | None = None, is_first: bool = False
    ) -> StepResult:
        """执行 Agent 循环的单个步骤。"""
        self._step_count += 1
        logger.debug(f"执行步骤 {self._step_count}")

        # 检查是否暂停
        while self._is_paused:
            import time
            time.sleep(0.1)
        
        # 捕获当前屏幕状态
        logger.debug("捕获屏幕截图...")
        screenshot = get_screenshot(self.agent_config.device_id)
        current_app = get_current_app(self.agent_config.device_id)
        self._current_app = current_app
        logger.debug(f"当前应用: {current_app}")

        # 构建消息
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"{user_prompt}\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(current_app)
            text_content = f"** Screen Info **\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        # 获取模型响应
        try:
            logger.debug("请求模型响应...")
            response = self.model_client.request(self._context)
            logger.debug(f"模型响应成功，操作: {response.action[:50]}...")
        except Exception as e:
            logger.error(f"模型请求失败: {e}", exc_info=True)
            self._last_error = f"Model error: {e}"
            if self.agent_config.verbose:
                traceback.print_exc()
            # 记录到跟踪
            if self._tracer:
                self._tracer.add_step(
                    screenshot_base64=screenshot.base64_data,
                    current_app=current_app,
                    thinking="",
                    action={},
                    action_result=f"模型错误: {e}",
                    success=False,
                    error_message=str(e)
                )
            step_result = StepResult(
                success=False,
                finished=True,
                action=None,
                thinking="",
                message=f"Model error: {e}",
            )
            # 触发步骤回调
            if self._step_callback:
                self._step_callback(step_result)
            return step_result

        # 从响应中解析操作
        try:
            action = parse_action(response.action)
            logger.debug(f"解析操作: {action.get('action', 'finish')}")
        except ValueError as e:
            logger.warning(f"操作解析失败，使用原始响应: {e}")
            if self.agent_config.verbose:
                traceback.print_exc()
            action = finish(message=response.action)

        if self.agent_config.verbose:
            # 打印思考过程
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "=" * 50)
            print(f"💭 {msgs['thinking']}:")
            print("-" * 50)
            print(response.thinking)
            print("-" * 50)
            print(f"🎯 {msgs['action']}:")
            print(json.dumps(action, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")

        # 从上下文中移除图像以节省空间
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])

        # 执行操作
        try:
            logger.info(f"执行操作: {action.get('action', 'finish')}")
            result = self.action_handler.execute(
                action, screenshot.width, screenshot.height
            )
            logger.debug(f"操作结果: 成功={result.success}, 完成={result.should_finish}")
        except Exception as e:
            logger.error(f"操作执行失败: {e}", exc_info=True)
            if self.agent_config.verbose:
                traceback.print_exc()
            result = self.action_handler.execute(
                finish(message=str(e)), screenshot.width, screenshot.height
            )

        # 将助手响应添加到上下文
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # 记录到执行跟踪
        if self._tracer:
            self._tracer.add_step(
                screenshot_base64=screenshot.base64_data,
                current_app=current_app,
                thinking=response.thinking,
                action=action,
                action_result=result.message or "成功",
                success=result.success,
                error_message=None if result.success else result.message
            )

        # 检查是否完成
        finished = action.get("_metadata") == "finish" or result.should_finish

        if finished:
            final_msg = result.message or action.get('message', '完成')
            logger.info(f"任务完成: {final_msg}")
            if self.agent_config.verbose:
                msgs = get_messages(self.agent_config.lang)
                print("\n" + "🎉 " + "=" * 48)
                print(
                    f"✅ {msgs['task_completed']}: {result.message or action.get('message', msgs['done'])}"
                )
                print("=" * 50 + "\n")

        step_result = StepResult(
            success=result.success,
            finished=finished,
            action=action,
            thinking=response.thinking,
            message=result.message or action.get("message"),
        )
        
        # 触发步骤回调（流式反馈）
        if self._step_callback:
            try:
                self._step_callback(step_result)
            except Exception as e:
                logger.warning(f"步骤回调执行失败: {e}")
        
        return step_result

    @property
    def context(self) -> list[dict[str, Any]]:
        """获取当前对话上下文。"""
        return self._context.copy()

    @property
    def step_count(self) -> int:
        """获取当前步骤计数。"""
        return self._step_count
