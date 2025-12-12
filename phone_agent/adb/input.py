"""Android 设备文本输入的输入工具。"""

import base64
import subprocess
from typing import Optional


def type_text(text: str, device_id: str | None = None) -> None:
    """
    使用 ADB 键盘在当前焦点输入框中输入文本。

    Args:
        text: 要输入的文本。
        device_id: 可选的 ADB 设备 ID，用于多设备设置。

    Note:
        需要在设备上安装 ADB Keyboard。
        参见: https://github.com/nicnocquee/AdbKeyboard
    """
    adb_prefix = _get_adb_prefix(device_id)
    encoded_text = base64.b64encode(text.encode("utf-8")).decode("utf-8")

    # 使用 UTF-8 编码解决 Windows GBK 编码问题
    subprocess.run(
        adb_prefix
        + [
            "shell",
            "am",
            "broadcast",
            "-a",
            "ADB_INPUT_B64",
            "--es",
            "msg",
            encoded_text,
        ],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )


def clear_text(device_id: str | None = None) -> None:
    """
    清除当前焦点输入框中的文本。

    Args:
        device_id: 可选的 ADB 设备 ID，用于多设备设置。
    """
    adb_prefix = _get_adb_prefix(device_id)

    # 使用 UTF-8 编码解决 Windows GBK 编码问题
    subprocess.run(
        adb_prefix + ["shell", "am", "broadcast", "-a", "ADB_CLEAR_TEXT"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )


def detect_and_set_adb_keyboard(device_id: str | None = None) -> str:
    """
    检测当前键盘并在需要时切换到 ADB 键盘。

    Args:
        device_id: 可选的 ADB 设备 ID，用于多设备设置。

    Returns:
        原始键盘 IME 标识符，用于稍后恢复。
    """
    adb_prefix = _get_adb_prefix(device_id)

    # 获取当前 IME
    # 使用 UTF-8 编码解决 Windows GBK 编码问题
    result = subprocess.run(
        adb_prefix + ["shell", "settings", "get", "secure", "default_input_method"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    current_ime = (result.stdout + result.stderr).strip()

    # 如果尚未设置，切换到 ADB 键盘
    if "com.android.adbkeyboard/.AdbIME" not in current_ime:
        # 使用 UTF-8 编码解决 Windows GBK 编码问题
        subprocess.run(
            adb_prefix + ["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

    # 预热键盘
    type_text("", device_id)

    return current_ime


def restore_keyboard(ime: str, device_id: str | None = None) -> None:
    """
    恢复原始键盘 IME。

    Args:
        ime: 要恢复的 IME 标识符。
        device_id: 可选的 ADB 设备 ID，用于多设备设置。
    """
    adb_prefix = _get_adb_prefix(device_id)

    # 使用 UTF-8 编码解决 Windows GBK 编码问题
    subprocess.run(
        adb_prefix + ["shell", "ime", "set", ime], 
        capture_output=True, 
        text=True,
        encoding='utf-8',
        errors='replace'
    )


def _get_adb_prefix(device_id: str | None) -> list:
    """获取带有可选设备标识符的 ADB 命令前缀。"""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]
