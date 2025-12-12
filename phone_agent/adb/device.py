"""Android 自动化的设备控制工具。"""

import os
import subprocess
import time
from typing import List, Optional, Tuple

from phone_agent.config.apps import APP_PACKAGES
from phone_agent.logging_config import get_logger

# 获取日志器
logger = get_logger("adb.device")


def get_current_app(device_id: str | None = None) -> str:
    """
    获取当前焦点应用的名称。

    Args:
        device_id: 可选的 ADB 设备 ID，用于多设备设置。

    Returns:
        如果识别则返回应用名称，否则返回 "System Home"。
    """
    adb_prefix = _get_adb_prefix(device_id)

    # 使用 UTF-8 编码解决 Windows GBK 编码问题
    result = subprocess.run(
        adb_prefix + ["shell", "dumpsys", "window"], 
        capture_output=True, 
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    output = result.stdout

    # 解析窗口焦点信息
    for line in output.split("\n"):
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            for app_name, package in APP_PACKAGES.items():
                if package in line:
                    return app_name

    return "System Home"


def tap(x: int, y: int, device_id: str | None = None, delay: float = 1.0) -> None:
    """
    在指定坐标处点击。

    Args:
        x: X 坐标。
        y: Y 坐标。
        device_id: 可选的 ADB 设备 ID。
        delay: 点击后的延迟（秒）。
    """
    logger.debug(f"点击: ({x}, {y})")
    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def double_tap(
    x: int, y: int, device_id: str | None = None, delay: float = 1.0
) -> None:
    """
    在指定坐标处双击。

    Args:
        x: X 坐标。
        y: Y 坐标。
        device_id: 可选的 ADB 设备 ID。
        delay: 双击后的延迟（秒）。
    """
    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(0.1)
    subprocess.run(
        adb_prefix + ["shell", "input", "tap", str(x), str(y)], capture_output=True
    )
    time.sleep(delay)


def long_press(
    x: int,
    y: int,
    duration_ms: int = 3000,
    device_id: str | None = None,
    delay: float = 1.0,
) -> None:
    """
    在指定坐标处长按。

    Args:
        x: X 坐标。
        y: Y 坐标。
        duration_ms: 按压时长（毫秒）。
        device_id: 可选的 ADB 设备 ID。
        delay: 长按后的延迟（秒）。
    """
    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix
        + ["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)],
        capture_output=True,
    )
    time.sleep(delay)


def swipe(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int | None = None,
    device_id: str | None = None,
    delay: float = 1.0,
) -> None:
    """
    从起始坐标滑动到结束坐标。

    Args:
        start_x: 起始 X 坐标。
        start_y: 起始 Y 坐标。
        end_x: 结束 X 坐标。
        end_y: 结束 Y 坐标。
        duration_ms: 滑动时长（毫秒）（如果为 None 则自动计算）。
        device_id: 可选的 ADB 设备 ID。
        delay: 滑动后的延迟（秒）。
    """
    logger.debug(f"滑动: ({start_x}, {start_y}) -> ({end_x}, {end_y})")
    adb_prefix = _get_adb_prefix(device_id)

    if duration_ms is None:
        # 根据距离计算时长
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = int(dist_sq / 1000)
        duration_ms = max(1000, min(duration_ms, 2000))  # 限制在 1000-2000ms 之间

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "input",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ],
        capture_output=True,
    )
    time.sleep(delay)


def back(device_id: str | None = None, delay: float = 1.0) -> None:
    """
    按下返回按钮。

    Args:
        device_id: 可选的 ADB 设备 ID。
        delay: 按下返回后的延迟（秒）。
    """
    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "4"], capture_output=True
    )
    time.sleep(delay)


def home(device_id: str | None = None, delay: float = 1.0) -> None:
    """
    按下主页按钮。

    Args:
        device_id: 可选的 ADB 设备 ID。
        delay: 按下主页后的延迟（秒）。
    """
    adb_prefix = _get_adb_prefix(device_id)

    subprocess.run(
        adb_prefix + ["shell", "input", "keyevent", "KEYCODE_HOME"], capture_output=True
    )
    time.sleep(delay)


def launch_app(app_name: str, device_id: str | None = None, delay: float = 1.0) -> bool:
    """
    按名称启动应用。

    Args:
        app_name: 应用名称（必须在 APP_PACKAGES 中）。
        device_id: 可选的 ADB 设备 ID。
        delay: 启动后的延迟（秒）。

    Returns:
        如果应用已启动返回 True，如果未找到应用返回 False。
    """
    logger.info(f"启动应用: {app_name}")
    if app_name not in APP_PACKAGES:
        logger.warning(f"应用未在配置中找到: {app_name}")
        return False

    adb_prefix = _get_adb_prefix(device_id)
    package = APP_PACKAGES[app_name]

    subprocess.run(
        adb_prefix
        + [
            "shell",
            "monkey",
            "-p",
            package,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
        capture_output=True,
    )
    time.sleep(delay)
    return True


def _get_adb_prefix(device_id: str | None) -> list:
    """获取带有可选设备标识符的 ADB 命令前缀。"""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]
