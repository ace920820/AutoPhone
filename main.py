#!/usr/bin/env python3
"""
Phone Agent 命令行工具 - AI 驱动的手机自动化。

用法:
    python main.py [OPTIONS]

环境变量:
    PHONE_AGENT_BASE_URL: 模型 API 基础 URL（默认: http://localhost:8000/v1）
    PHONE_AGENT_MODEL: 模型名称（默认: autoglm-phone-9b）
    PHONE_AGENT_API_KEY: 模型认证 API 密钥（默认: EMPTY）
    PHONE_AGENT_MAX_STEPS: 每个任务的最大步数（默认: 100）
    PHONE_AGENT_DEVICE_ID: 多设备设置中的 ADB 设备 ID
"""

import argparse
import os
import shutil
import subprocess
import sys
import io
from urllib.parse import urlparse

# 修复 Windows 编码问题
if sys.platform.startswith('win'):
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8')

from openai import OpenAI

from phone_agent import PhoneAgent
from phone_agent.adb import ADBConnection, list_devices
from phone_agent.agent import AgentConfig
from phone_agent.config.apps import list_supported_apps
from phone_agent.model import ModelConfig


def check_system_requirements() -> bool:
    """
    在运行 Agent 之前检查系统要求。

    检查项:
    1. ADB 工具是否已安装
    2. 是否至少连接了一个设备
    3. 设备上是否已安装 ADB Keyboard

    Returns:
        如果所有检查通过返回 True，否则返回 False。
    """
    print("🔍 Checking system requirements...")
    print("-" * 50)

    all_passed = True

    # 检查 1: ADB 是否已安装
    print("1. Checking ADB installation...", end=" ")
    if shutil.which("adb") is None:
        print("❌ FAILED")
        print("   Error: ADB is not installed or not in PATH.")
        print("   Solution: Install Android SDK Platform Tools:")
        print("     - macOS: brew install android-platform-tools")
        print("     - Linux: sudo apt install android-tools-adb")
        print(
            "     - Windows: Download from https://developer.android.com/studio/releases/platform-tools"
        )
        all_passed = False
    else:
        # 通过运行 adb version 进行二次确认
        try:
            result = subprocess.run(
                ["adb", "version"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version_line = result.stdout.strip().split("\n")[0]
                print(f"✅ OK ({version_line})")
            else:
                print("❌ FAILED")
                print("   Error: ADB command failed to run.")
                all_passed = False
        except FileNotFoundError:
            print("❌ FAILED")
            print("   Error: ADB command not found.")
            all_passed = False
        except subprocess.TimeoutExpired:
            print("❌ FAILED")
            print("   Error: ADB command timed out.")
            all_passed = False

    # 如果 ADB 未安装，跳过剩余检查
    if not all_passed:
        print("-" * 50)
        print("❌ System check failed. Please fix the issues above.")
        return False

    # 检查 2: 设备是否已连接
    print("2. Checking connected devices...", end=" ")
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        # 过滤标题和空行，查找 'device' 状态
        devices = [line for line in lines[1:] if line.strip() and "\tdevice" in line]

        if not devices:
            print("❌ FAILED")
            print("   Error: No devices connected.")
            print("   Solution:")
            print("     1. Enable USB debugging on your Android device")
            print("     2. Connect via USB and authorize the connection")
            print("     3. Or connect remotely: python main.py --connect <ip>:<port>")
            all_passed = False
        else:
            device_ids = [d.split("\t")[0] for d in devices]
            print(f"✅ OK ({len(devices)} device(s): {', '.join(device_ids)})")
    except subprocess.TimeoutExpired:
        print("❌ FAILED")
        print("   Error: ADB command timed out.")
        all_passed = False
    except Exception as e:
        print("❌ FAILED")
        print(f"   Error: {e}")
        all_passed = False

    # 如果没有设备连接，跳过 ADB Keyboard 检查
    if not all_passed:
        print("-" * 50)
        print("❌ System check failed. Please fix the issues above.")
        return False

    # 检查 3: ADB Keyboard 是否已安装
    print("3. Checking ADB Keyboard...", end=" ")
    try:
        result = subprocess.run(
            ["adb", "shell", "ime", "list", "-s"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        ime_list = result.stdout.strip()

        if "com.android.adbkeyboard/.AdbIME" in ime_list:
            print("✅ OK")
        else:
            print("❌ FAILED")
            print("   Error: ADB Keyboard is not installed on the device.")
            print("   Solution:")
            print("     1. Download ADB Keyboard APK from:")
            print(
                "        https://github.com/senzhk/ADBKeyBoard/blob/master/ADBKeyboard.apk"
            )
            print("     2. Install it on your device: adb install ADBKeyboard.apk")
            print(
                "     3. Enable it in Settings > System > Languages & Input > Virtual Keyboard"
            )
            all_passed = False
    except subprocess.TimeoutExpired:
        print("❌ FAILED")
        print("   Error: ADB command timed out.")
        all_passed = False
    except Exception as e:
        print("❌ FAILED")
        print(f"   Error: {e}")
        all_passed = False

    print("-" * 50)

    if all_passed:
        print("✅ All system checks passed!\n")
    else:
        print("❌ System check failed. Please fix the issues above.")

    return all_passed


def check_model_api(base_url: str, model_name: str, api_key: str = "EMPTY") -> bool:
    """
    检查模型 API 是否可访问以及指定的模型是否存在。

    检查项:
    1. 到 API 端点的网络连接
    2. 模型是否存在于可用模型列表中

    Args:
        base_url: API 基础 URL
        model_name: 要检查的模型名称
        api_key: 认证用的 API 密钥

    Returns:
        如果所有检查通过返回 True，否则返回 False。
    """
    print("🔍 Checking model API...")
    print("-" * 50)

    all_passed = True

    # 检查 1: 网络连接
    print(f"1. Checking API connectivity ({base_url})...", end=" ")
    try:
        # 解析 URL 获取主机和端口
        parsed = urlparse(base_url)

        # 创建 OpenAI 客户端
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=10.0)

        # 尝试列出模型（这会测试连接性）
        models_response = client.models.list()
        available_models = [model.id for model in models_response.data]

        print("✅ OK")

        # 检查 2: 模型是否存在
        """
        print(f"2. Checking model '{model_name}'...", end=" ")
        if model_name in available_models:
            print("✅ OK")
        else:
            print("❌ FAILED")
            print(f"   Error: Model '{model_name}' not found.")
            print(f"   Available models:")
            for m in available_models[:10]:  # Show first 10 models
                print(f"     - {m}")
            if len(available_models) > 10:
                print(f"     ... and {len(available_models) - 10} more")
            all_passed = False
        """

    except Exception as e:
        print("❌ FAILED")
        error_msg = str(e)

        # 提供更具体的错误信息
        if "Connection refused" in error_msg or "Connection error" in error_msg:
            print(f"   Error: Cannot connect to {base_url}")
            print("   Solution:")
            print("     1. Check if the model server is running")
            print("     2. Verify the base URL is correct")
            print(f"     3. Try: curl {base_url}/models")
        elif "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
            print(f"   Error: Connection to {base_url} timed out")
            print("   Solution:")
            print("     1. Check your network connection")
            print("     2. Verify the server is responding")
        elif (
            "Name or service not known" in error_msg
            or "nodename nor servname" in error_msg
        ):
            print(f"   Error: Cannot resolve hostname")
            print("   Solution:")
            print("     1. Check the URL is correct")
            print("     2. Verify DNS settings")
        else:
            print(f"   Error: {error_msg}")

        all_passed = False

    print("-" * 50)

    if all_passed:
        print("✅ Model API checks passed!\n")
    else:
        print("❌ Model API check failed. Please fix the issues above.")

    return all_passed


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Phone Agent - AI-powered phone automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with default settings
    python main.py

    # Specify model endpoint
    python main.py --base-url http://localhost:8000/v1

    # Use API key for authentication
    python main.py --apikey sk-xxxxx

    # Run with specific device
    python main.py --device-id emulator-5554

    # Connect to remote device
    python main.py --connect 192.168.1.100:5555

    # List connected devices
    python main.py --list-devices

    # Enable TCP/IP on USB device and get connection info
    python main.py --enable-tcpip

    # List supported apps
    python main.py --list-apps
        """,
    )

    # 模型选项
    parser.add_argument(
        "--base-url",
        type=str,
        default=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        help="Model API base URL",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
        help="Model name",
    )

    parser.add_argument(
        "--apikey",
        type=str,
        default=os.getenv("PHONE_AGENT_API_KEY", "EMPTY"),
        help="API key for model authentication",
    )

    parser.add_argument(
        "--max-steps",
        type=int,
        default=int(os.getenv("PHONE_AGENT_MAX_STEPS", "100")),
        help="Maximum steps per task",
    )

    # 设备选项
    parser.add_argument(
        "--device-id",
        "-d",
        type=str,
        default=os.getenv("PHONE_AGENT_DEVICE_ID"),
        help="ADB device ID",
    )

    parser.add_argument(
        "--connect",
        "-c",
        type=str,
        metavar="ADDRESS",
        help="Connect to remote device (e.g., 192.168.1.100:5555)",
    )

    parser.add_argument(
        "--disconnect",
        type=str,
        nargs="?",
        const="all",
        metavar="ADDRESS",
        help="Disconnect from remote device (or 'all' to disconnect all)",
    )

    parser.add_argument(
        "--list-devices", action="store_true", help="List connected devices and exit"
    )

    parser.add_argument(
        "--enable-tcpip",
        type=int,
        nargs="?",
        const=5555,
        metavar="PORT",
        help="Enable TCP/IP debugging on USB device (default port: 5555)",
    )

    # 其他选项
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress verbose output"
    )

    parser.add_argument(
        "--list-apps", action="store_true", help="List supported apps and exit"
    )

    parser.add_argument(
        "--lang",
        type=str,
        choices=["cn", "en"],
        default=os.getenv("PHONE_AGENT_LANG", "cn"),
        help="Language for system prompt (cn or en, default: cn)",
    )

    parser.add_argument(
        "task",
        nargs="?",
        type=str,
        help="Task to execute (interactive mode if not provided)",
    )

    return parser.parse_args()


def handle_device_commands(args) -> bool:
    """
    处理设备相关命令。

    Returns:
        如果处理了设备命令（应该退出）返回 True，否则返回 False。
    """
    conn = ADBConnection()

    # 处理 --list-devices
    if args.list_devices:
        devices = list_devices()
        if not devices:
            print("No devices connected.")
        else:
            print("Connected devices:")
            print("-" * 60)
            for device in devices:
                status_icon = "✓" if device.status == "device" else "✗"
                conn_type = device.connection_type.value
                model_info = f" ({device.model})" if device.model else ""
                print(
                    f"  {status_icon} {device.device_id:<30} [{conn_type}]{model_info}"
                )
        return True

    # 处理 --connect
    if args.connect:
        print(f"Connecting to {args.connect}...")
        success, message = conn.connect(args.connect)
        print(f"{'✓' if success else '✗'} {message}")
        if success:
            # 设置为默认设备
            args.device_id = args.connect
        return not success  # 如果连接成功则继续

    # 处理 --disconnect
    if args.disconnect:
        if args.disconnect == "all":
            print("Disconnecting all remote devices...")
            success, message = conn.disconnect()
        else:
            print(f"Disconnecting from {args.disconnect}...")
            success, message = conn.disconnect(args.disconnect)
        print(f"{'✓' if success else '✗'} {message}")
        return True

    # 处理 --enable-tcpip
    if args.enable_tcpip:
        port = args.enable_tcpip
        print(f"Enabling TCP/IP debugging on port {port}...")

        success, message = conn.enable_tcpip(port, args.device_id)
        print(f"{'✓' if success else '✗'} {message}")

        if success:
            # 尝试获取设备 IP
            ip = conn.get_device_ip(args.device_id)
            if ip:
                print(f"\nYou can now connect remotely using:")
                print(f"  python main.py --connect {ip}:{port}")
                print(f"\nOr via ADB directly:")
                print(f"  adb connect {ip}:{port}")
            else:
                print("\nCould not determine device IP. Check device WiFi settings.")
        return True

    return False


def main():
    """主入口函数。"""
    args = parse_args()

    # 处理 --list-apps（不需要系统检查）
    if args.list_apps:
        print("Supported apps:")
        for app in sorted(list_supported_apps()):
            print(f"  - {app}")
        return

    # 处理设备命令（这些可能需要部分系统检查）
    if handle_device_commands(args):
        return

    # 在继续之前运行系统要求检查
    if not check_system_requirements():
        sys.exit(1)

    # 检查模型 API 连接和模型可用性
    if not check_model_api(args.base_url, args.model, args.apikey):
        sys.exit(1)

    # 创建配置
    model_config = ModelConfig(
        base_url=args.base_url,
        model_name=args.model,
        api_key=args.apikey,
    )

    agent_config = AgentConfig(
        max_steps=args.max_steps,
        device_id=args.device_id,
        verbose=not args.quiet,
        lang=args.lang,
    )

    # 创建 Agent
    agent = PhoneAgent(
        model_config=model_config,
        agent_config=agent_config,
    )

    # 打印标题
    print("=" * 50)
    print("Phone Agent - AI-powered phone automation")
    print("=" * 50)
    print(f"Model: {model_config.model_name}")
    print(f"Base URL: {model_config.base_url}")
    print(f"Max Steps: {agent_config.max_steps}")
    print(f"Language: {agent_config.lang}")

    # 显示设备信息
    devices = list_devices()
    if agent_config.device_id:
        print(f"Device: {agent_config.device_id}")
    elif devices:
        print(f"Device: {devices[0].device_id} (auto-detected)")

    print("=" * 50)

    # 使用提供的任务运行或进入交互模式
    if args.task:
        print(f"\nTask: {args.task}\n")
        result = agent.run(args.task)
        print(f"\nResult: {result}")
    else:
        # 交互模式
        print("\nEntering interactive mode. Type 'quit' to exit.\n")

        while True:
            try:
                task = input("Enter your task: ").strip()

                if task.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break

                if not task:
                    continue

                print()
                result = agent.run(task)
                print(f"\nResult: {result}\n")
                agent.reset()

            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
