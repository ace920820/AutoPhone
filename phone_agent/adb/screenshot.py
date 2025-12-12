"""用于捕获 Android 设备屏幕的截图工具。"""

import base64
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Tuple

from PIL import Image
from phone_agent.logging_config import get_logger

# 获取日志器
logger = get_logger("adb.screenshot")


@dataclass
class Screenshot:
    """表示捕获的截图。"""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False


def get_screenshot(device_id: str | None = None, timeout: int = 10) -> Screenshot:
    """
    从已连接的 Android 设备捕获截图。

    Args:
        device_id: 可选的 ADB 设备 ID，用于多设备设置。
        timeout: 截图操作的超时时间（秒）。

    Returns:
        包含 base64 数据和尺寸的 Screenshot 对象。

    Note:
        如果截图失败（例如在支付页面等敏感屏幕上），
        将返回黑色备用图像并设置 is_sensitive=True。
    """
    temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{uuid.uuid4()}.png")
    adb_prefix = _get_adb_prefix(device_id)
    
    logger.debug(f"开始截图 - 设备: {device_id or '默认'}")

    try:
        # 执行截图命令
        # 使用 UTF-8 编码解决 Windows GBK 编码问题
        result = subprocess.run(
            adb_prefix + ["shell", "screencap", "-p", "/sdcard/tmp.png"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )

        # 检查截图失败（敏感屏幕）
        output = result.stdout + result.stderr
        if "Status: -1" in output or "Failed" in output:
            logger.warning("截图失败: 可能是敏感屏幕")
            return _create_fallback_screenshot(is_sensitive=True)

        # 将截图拉取到本地临时路径
        # 使用 UTF-8 编码解决 Windows GBK 编码问题
        subprocess.run(
            adb_prefix + ["pull", "/sdcard/tmp.png", temp_path],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='replace'
        )

        if not os.path.exists(temp_path):
            logger.warning("截图文件不存在")
            return _create_fallback_screenshot(is_sensitive=False)

        # 读取并编码图像
        img = Image.open(temp_path)
        width, height = img.size

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # 清理
        os.remove(temp_path)

        logger.debug(f"截图成功: {width}x{height}")
        return Screenshot(
            base64_data=base64_data, width=width, height=height, is_sensitive=False
        )

    except Exception as e:
        logger.error(f"截图错误: {e}")
        return _create_fallback_screenshot(is_sensitive=False)


def _get_adb_prefix(device_id: str | None) -> list:
    """获取带有可选设备标识符的 ADB 命令前缀。"""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """当截图失败时创建黑色备用图像。"""
    logger.debug(f"创建备用截图 - 敏感屏幕: {is_sensitive}")
    default_width, default_height = 1080, 2400

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    buffered = BytesIO()
    black_img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=default_width,
        height=default_height,
        is_sensitive=is_sensitive,
    )
