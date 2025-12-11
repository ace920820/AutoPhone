#!/usr/bin/env python3
"""
Phone Agent CLI - AI 驱动的手机自动化

支持两种运行模式：
1. 直接模式 (--direct): 使用 AutoGLM 直接执行任务（默认，兼容原有行为）
2. 编排模式 (--orchestrate): 使用 Agno Orchestrator 进行任务规划和执行

Usage:
    python main.py [OPTIONS]
    python main.py --direct "打开微信"           # 直接模式
    python main.py --orchestrate "帮我点杯咖啡"   # 编排模式

Environment Variables (可在 .env 文件中配置):
    # AutoGLM 模型配置（直接模式）
    PHONE_AGENT_BASE_URL: Model API base URL (default: http://localhost:8000/v1)
    PHONE_AGENT_MODEL: Model name (default: autoglm-phone-9b)
    PHONE_AGENT_API_KEY: API key for model authentication (default: EMPTY)
    PHONE_AGENT_MAX_STEPS: Maximum steps per task (default: 100)
    PHONE_AGENT_DEVICE_ID: ADB device ID for multi-device setups
    PHONE_AGENT_LANG: Language for system prompt (cn or en, default: cn)
    
    # Orchestrator LLM 配置（编排模式）
    LLM_API_KEY: Orchestrator LLM API key
    LLM_BASE_URL: Orchestrator LLM API base URL
    LLM_MODEL: Orchestrator LLM model name (default: qwen-plus)
"""

import argparse
import os

# 加载 .env 文件中的环境变量配置
try:
    from dotenv import load_dotenv
    load_dotenv()  # 从 .env 文件加载环境变量
    print("📋 已加载 .env 配置文件")
except ImportError:
    # 如果没有安装 python-dotenv，跳过 .env 文件加载
    pass
import shutil
import subprocess
import sys
from urllib.parse import urlparse

from openai import OpenAI

from phone_agent import PhoneAgent, StepExecutor, ExecutorConfig
from phone_agent.adb import ADBConnection, list_devices
from phone_agent.config.apps import list_supported_apps
from phone_agent.model import ModelConfig


def check_system_requirements() -> bool:
    """
    Check system requirements before running the agent.

    Checks:
    1. ADB tools installed
    2. At least one device connected
    3. ADB Keyboard installed on the device

    Returns:
        True if all checks pass, False otherwise.
    """
    print("🔍 Checking system requirements...")
    print("-" * 50)

    all_passed = True

    # Check 1: ADB installed
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
        # Double check by running adb version
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

    # If ADB is not installed, skip remaining checks
    if not all_passed:
        print("-" * 50)
        print("❌ System check failed. Please fix the issues above.")
        return False

    # Check 2: Device connected
    print("2. Checking connected devices...", end=" ")
    try:
        result = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        # Filter out header and empty lines, look for 'device' status
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

    # If no device connected, skip ADB Keyboard check
    if not all_passed:
        print("-" * 50)
        print("❌ System check failed. Please fix the issues above.")
        return False

    # Check 3: ADB Keyboard installed
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
    Check if the model API is accessible and the specified model exists.

    Checks:
    1. Network connectivity to the API endpoint
    2. Model exists in the available models list

    Args:
        base_url: The API base URL
        model_name: The model name to check
        api_key: The API key for authentication

    Returns:
        True if all checks pass, False otherwise.
    """
    print("🔍 Checking model API...")
    print("-" * 50)

    all_passed = True

    # Check 1: Network connectivity
    print(f"1. Checking API connectivity ({base_url})...", end=" ")
    try:
        # Parse the URL to get host and port
        parsed = urlparse(base_url)

        # Create OpenAI client
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=10.0)

        # Try to list models (this tests connectivity)
        models_response = client.models.list()
        available_models = [model.id for model in models_response.data]

        print("✅ OK")

        # Check 2: Model exists
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

        # Provide more specific error messages
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
    """Parse command line arguments."""
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

    # Model options
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

    # Device options
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

    # Other options
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

    # 运行模式选项
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--direct",
        action="store_true",
        default=True,
        help="直接模式：使用 AutoGLM 直接执行任务（默认）",
    )
    mode_group.add_argument(
        "--orchestrate",
        action="store_true",
        help="编排模式：使用 Agno Orchestrator 进行任务规划",
    )
    
    # Orchestrator 配置
    parser.add_argument(
        "--llm-model",
        type=str,
        default=os.getenv("LLM_MODEL", "qwen-plus"),
        help="Orchestrator LLM 模型名称",
    )
    parser.add_argument(
        "--llm-api-key",
        type=str,
        default=os.getenv("LLM_API_KEY"),
        help="Orchestrator LLM API 密钥",
    )
    parser.add_argument(
        "--llm-base-url",
        type=str,
        default=os.getenv("LLM_BASE_URL"),
        help="Orchestrator LLM API 基础 URL",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="禁用 Orchestrator 的记忆功能",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="用户 ID（用于记忆隔离）",
    )
    
    # AgentOS 服务模式
    parser.add_argument(
        "--serve",
        action="store_true",
        help="启动 AgentOS REST API 服务（编排模式）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7777,
        help="AgentOS 服务端口（默认 7777）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="AgentOS 服务地址（默认 0.0.0.0）",
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
    Handle device-related commands.

    Returns:
        True if a device command was handled (should exit), False otherwise.
    """
    conn = ADBConnection()

    # Handle --list-devices
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

    # Handle --connect
    if args.connect:
        print(f"Connecting to {args.connect}...")
        success, message = conn.connect(args.connect)
        print(f"{'✓' if success else '✗'} {message}")
        if success:
            # Set as default device
            args.device_id = args.connect
        return not success  # Continue if connection succeeded

    # Handle --disconnect
    if args.disconnect:
        if args.disconnect == "all":
            print("Disconnecting all remote devices...")
            success, message = conn.disconnect()
        else:
            print(f"Disconnecting from {args.disconnect}...")
            success, message = conn.disconnect(args.disconnect)
        print(f"{'✓' if success else '✗'} {message}")
        return True

    # Handle --enable-tcpip
    if args.enable_tcpip:
        port = args.enable_tcpip
        print(f"Enabling TCP/IP debugging on port {port}...")

        success, message = conn.enable_tcpip(port, args.device_id)
        print(f"{'✓' if success else '✗'} {message}")

        if success:
            # Try to get device IP
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


def run_direct_mode(args, model_config, executor_config):
    """
    直接模式：使用 StepExecutor (原 PhoneAgent) 直接执行任务
    """
    # 创建执行器
    executor = StepExecutor(
        model_config=model_config,
        executor_config=executor_config,
    )

    # 打印头部信息
    print("=" * 50)
    print("📱 Phone Agent - 直接模式")
    print("=" * 50)
    print(f"Model: {model_config.model_name}")
    print(f"Base URL: {model_config.base_url}")
    print(f"Max Steps: {executor_config.max_steps}")
    print(f"Language: {executor_config.lang}")

    # 显示设备信息
    devices = list_devices()
    if executor_config.device_id:
        print(f"Device: {executor_config.device_id}")
    elif devices:
        print(f"Device: {devices[0].device_id} (auto-detected)")

    print("=" * 50)

    # 执行任务或进入交互模式
    if args.task:
        print(f"\n📝 任务: {args.task}\n")
        result = executor.run(args.task)
        print(f"\n✅ 结果: {result}")
    else:
        # 交互模式
        print("\n进入交互模式，输入 'quit' 退出\n")

        while True:
            try:
                task = input("📝 请输入任务: ").strip()

                if task.lower() in ("quit", "exit", "q"):
                    print("👋 再见!")
                    break

                if not task:
                    continue

                print()
                result = executor.run(task)
                print(f"\n✅ 结果: {result}\n")
                executor.reset()

            except KeyboardInterrupt:
                print("\n\n👋 再见!")
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}\n")


def run_orchestrate_mode(args, model_config, executor_config):
    """
    编排模式：使用 Agno Orchestrator 进行任务规划和执行
    """
    # 检查 Orchestrator 配置
    if not args.llm_api_key:
        print("❌ 编排模式需要配置 LLM API 密钥")
        print("   请设置环境变量 LLM_API_KEY 或使用 --llm-api-key 参数")
        sys.exit(1)
    
    # 延迟导入 orchestrator 模块
    try:
        from phone_agent.orchestrator import create_orchestrator
    except ImportError as e:
        print(f"❌ 导入 Orchestrator 模块失败: {e}")
        print("   请确保已安装 agno 库: pip install agno")
        sys.exit(1)
    
    # 创建 StepExecutor
    executor = StepExecutor(
        model_config=model_config,
        executor_config=executor_config,
    )
    
    # 创建 Orchestrator
    try:
        orchestrator = create_orchestrator(
            executor=executor,
            model_id=args.llm_model,
            api_key=args.llm_api_key,
            base_url=args.llm_base_url,
            enable_memory=not args.no_memory,
            verbose=not args.quiet,
        )
    except Exception as e:
        print(f"❌ 创建 Orchestrator 失败: {e}")
        sys.exit(1)
    
    # 打印头部信息
    print("=" * 50)
    print("🤖 Phone Agent - 编排模式 (Orchestrator)")
    print("=" * 50)
    print(f"Orchestrator LLM: {args.llm_model}")
    print(f"Executor Model: {model_config.model_name}")
    print(f"Memory: {'启用' if not args.no_memory else '禁用'}")
    
    # 显示设备信息
    devices = list_devices()
    if executor_config.device_id:
        print(f"Device: {executor_config.device_id}")
    elif devices:
        print(f"Device: {devices[0].device_id} (auto-detected)")
    
    print("=" * 50)
    
    # 执行任务或进入交互模式
    if args.task:
        print(f"\n📝 任务: {args.task}\n")
        result = orchestrator.run(args.task, user_id=args.user_id)
        print(f"\n✅ 完成")
    else:
        # 交互模式
        orchestrator.run_interactive(user_id=args.user_id)


def run_serve_mode(args, model_config, executor_config):
    """
    AgentOS 服务模式：启动 REST API 服务
    """
    # 检查 Orchestrator 配置
    if not args.llm_api_key:
        print("❌ AgentOS 服务模式需要配置 LLM API 密钥")
        print("   请设置环境变量 LLM_API_KEY 或使用 --llm-api-key 参数")
        sys.exit(1)
    
    # 延迟导入 orchestrator 模块
    try:
        from phone_agent.orchestrator import serve_agent_os
    except ImportError as e:
        print(f"❌ 导入 Orchestrator 模块失败: {e}")
        print("   请确保已安装 agno 库: pip install agno uvicorn")
        sys.exit(1)
    
    # 创建 StepExecutor
    executor = StepExecutor(
        model_config=model_config,
        executor_config=executor_config,
    )
    
    # 打印头部信息
    print("=" * 50)
    print("🚀 Phone Agent - AgentOS 服务模式")
    print("=" * 50)
    print(f"Orchestrator LLM: {args.llm_model}")
    print(f"Executor Model: {model_config.model_name}")
    print(f"Memory: {'启用' if not args.no_memory else '禁用'}")
    print(f"服务地址: http://{args.host}:{args.port}")
    print(f"API 文档: http://{args.host}:{args.port}/docs")
    
    # 显示设备信息
    devices = list_devices()
    if executor_config.device_id:
        print(f"Device: {executor_config.device_id}")
    elif devices:
        print(f"Device: {devices[0].device_id} (auto-detected)")
    
    print("=" * 50)
    
    # 启动 AgentOS 服务
    try:
        serve_agent_os(
            executor=executor,
            port=args.port,
            host=args.host,
            model_id=args.llm_model,
            api_key=args.llm_api_key,
            base_url=args.llm_base_url,
            enable_memory=not args.no_memory,
        )
    except Exception as e:
        print(f"❌ 启动 AgentOS 服务失败: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    args = parse_args()

    # Handle --list-apps (no system check needed)
    if args.list_apps:
        print("Supported apps:")
        for app in sorted(list_supported_apps()):
            print(f"  - {app}")
        return

    # Handle device commands (these may need partial system checks)
    if handle_device_commands(args):
        return

    # Run system requirements check before proceeding
    if not check_system_requirements():
        sys.exit(1)

    # Check model API connectivity and model availability
    if not check_model_api(args.base_url, args.model, args.apikey):
        sys.exit(1)

    # Create configurations
    model_config = ModelConfig(
        base_url=args.base_url,
        model_name=args.model,
        api_key=args.apikey,
    )

    executor_config = ExecutorConfig(
        max_steps=args.max_steps,
        device_id=args.device_id,
        verbose=not args.quiet,
        lang=args.lang,
    )

    # 根据模式运行
    if args.serve:
        # AgentOS 服务模式
        run_serve_mode(args, model_config, executor_config)
    elif args.orchestrate:
        # 编排模式（直接调用）
        run_orchestrate_mode(args, model_config, executor_config)
    else:
        # 直接模式
        run_direct_mode(args, model_config, executor_config)


if __name__ == "__main__":
    main()
