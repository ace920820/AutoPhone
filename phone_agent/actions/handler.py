"""用于处理 AI 模型输出的操作处理器。"""

import time
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.adb import (
    back,
    clear_text,
    detect_and_set_adb_keyboard,
    double_tap,
    home,
    launch_app,
    long_press,
    restore_keyboard,
    swipe,
    tap,
    type_text,
)


@dataclass
class ActionResult:
    """操作执行的结果。"""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False


class ActionHandler:
    """
    处理来自 AI 模型输出的操作执行。

    Args:
        device_id: 可选的 ADB 设备 ID，用于多设备设置。
        confirmation_callback: 可选的敏感操作确认回调。
            返回 True 继续，False 取消。
        takeover_callback: 可选的接管请求回调（登录、验证码）。
    """

    def __init__(
        self,
        device_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.device_id = device_id
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover

    def execute(
        self, action: dict[str, Any], screen_width: int, screen_height: int
    ) -> ActionResult:
        """
        执行来自 AI 模型的操作。

        Args:
            action: 来自模型的操作字典。
            screen_width: 当前屏幕宽度（像素）。
            screen_height: 当前屏幕高度（像素）。

        Returns:
            ActionResult 表示成功与否以及是否完成。
        """
        action_type = action.get("_metadata")

        if action_type == "finish":
            return ActionResult(
                success=True, should_finish=True, message=action.get("message")
            )

        if action_type != "do":
            return ActionResult(
                success=False,
                should_finish=True,
                message=f"Unknown action type: {action_type}",
            )

        action_name = action.get("action")
        handler_method = self._get_handler(action_name)

        if handler_method is None:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action: {action_name}",
            )

        try:
            return handler_method(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(
                success=False, should_finish=False, message=f"Action failed: {e}"
            )

    def _get_handler(self, action_name: str) -> Callable | None:
        """获取操作的处理方法。"""
        handlers = {
            "Launch": self._handle_launch,
            "Tap": self._handle_tap,
            "Type": self._handle_type,
            "Type_Name": self._handle_type,
            "Swipe": self._handle_swipe,
            "Back": self._handle_back,
            "Home": self._handle_home,
            "Double Tap": self._handle_double_tap,
            "Long Press": self._handle_long_press,
            "Wait": self._handle_wait,
            "Take_over": self._handle_takeover,
            "Note": self._handle_note,
            "Call_API": self._handle_call_api,
            "Interact": self._handle_interact,
        }
        return handlers.get(action_name)

    def _convert_relative_to_absolute(
        self, element: list[int], screen_width: int, screen_height: int
    ) -> tuple[int, int]:
        """将相对坐标（0-1000）转换为绝对像素。"""
        x = int(element[0] / 1000 * screen_width)
        y = int(element[1] / 1000 * screen_height)
        return x, y

    def _handle_launch(self, action: dict, width: int, height: int) -> ActionResult:
        """处理应用启动操作。"""
        app_name = action.get("app")
        if not app_name:
            return ActionResult(False, False, "No app name specified")

        success = launch_app(app_name, self.device_id)
        if success:
            return ActionResult(True, False)
        return ActionResult(False, False, f"App not found: {app_name}")

    def _handle_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """处理点击操作。"""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)

        # 检查敏感操作
        if "message" in action:
            if not self.confirmation_callback(action["message"]):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

        tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """处理文本输入操作。"""
        text = action.get("text", "")

        # 切换到 ADB 键盘
        original_ime = detect_and_set_adb_keyboard(self.device_id)
        time.sleep(1.0)

        # 清除现有文本并输入新文本
        clear_text(self.device_id)
        time.sleep(1.0)

        type_text(text, self.device_id)
        time.sleep(1.0)

        # 恢复原始键盘
        restore_keyboard(original_ime, self.device_id)
        time.sleep(1.0)

        return ActionResult(True, False)

    def _handle_swipe(self, action: dict, width: int, height: int) -> ActionResult:
        """处理滑动操作。"""
        start = action.get("start")
        end = action.get("end")

        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")

        start_x, start_y = self._convert_relative_to_absolute(start, width, height)
        end_x, end_y = self._convert_relative_to_absolute(end, width, height)

        swipe(start_x, start_y, end_x, end_y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_back(self, action: dict, width: int, height: int) -> ActionResult:
        """处理返回按钮操作。"""
        back(self.device_id)
        return ActionResult(True, False)

    def _handle_home(self, action: dict, width: int, height: int) -> ActionResult:
        """处理主页按钮操作。"""
        home(self.device_id)
        return ActionResult(True, False)

    def _handle_double_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """处理双击操作。"""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        double_tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """处理长按操作。"""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        long_press(x, y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_wait(self, action: dict, width: int, height: int) -> ActionResult:
        """处理等待操作。"""
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_takeover(self, action: dict, width: int, height: int) -> ActionResult:
        """处理接管请求（登录、验证码等）。"""
        message = action.get("message", "User intervention required")
        self.takeover_callback(message)
        return ActionResult(True, False)

    def _handle_note(self, action: dict, width: int, height: int) -> ActionResult:
        """处理笔记操作（内容记录的占位符）。"""
        # 此操作通常用于记录页面内容
        # 实现取决于具体需求
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """处理 API 调用操作（内容摘要的占位符）。"""
        # 此操作通常用于内容摘要
        # 实现取决于具体需求
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """处理交互请求（需要用户选择）。"""
        # 此操作表示需要用户输入
        return ActionResult(True, False, message="User interaction required")

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """使用控制台输入的默认确认回调。"""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """使用控制台输入的默认接管回调。"""
        input(f"{message}\nPress Enter after completing manual operation...")


def parse_action(response: str) -> dict[str, Any]:
    """
    从模型响应中解析操作。

    Args:
        response: 来自模型的原始响应字符串。

    Returns:
        解析后的操作字典。

    Raises:
        ValueError: 如果响应无法解析。
    """
    try:
        # 尝试作为 Python 字典/函数调用进行评估
        response = response.strip()
        if response.startswith("do"):
            action = eval(response)
        elif response.startswith("finish"):
            action = {
                "_metadata": "finish",
                "message": response.replace("finish(message=", "")[1:-2],
            }
        else:
            raise ValueError(f"Failed to parse action: {response}")
        return action
    except Exception as e:
        raise ValueError(f"Failed to parse action: {e}")


def do(**kwargs) -> dict[str, Any]:
    """创建 'do' 操作的辅助函数。"""
    kwargs["_metadata"] = "do"
    return kwargs


def finish(**kwargs) -> dict[str, Any]:
    """创建 'finish' 操作的辅助函数。"""
    kwargs["_metadata"] = "finish"
    return kwargs
