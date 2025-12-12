#!/usr/bin/env python3
"""
编排 Agent 命令行工具 - AI 驱动的手机自动化任务编排系统。

用法:
    python orchestrator_main.py [OPTIONS]
"""

import argparse
import os
import sys
import io
from dotenv import load_dotenv

# 修复 Windows 编码问题
if sys.platform.startswith('win'):
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8')

from main import check_system_requirements, check_model_api

# 加载环境变量
load_dotenv()

def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Phone Agent Orchestrator - Complex task automation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 编排模型选项
    parser.add_argument(
        "--model-id",
        type=str,
        default=os.getenv("LLM_MODEL", os.getenv("ORCHESTRATOR_MODEL", "gpt-4o")),
        help="Orchestrator model ID",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY")),
        help="Orchestrator API Key",
    )

    parser.add_argument(
        "--base-url",
        type=str,
        default=os.getenv("LLM_BASE_URL"),
        help="Orchestrator API Base URL",
    )

    # Phone Agent 模型选项
    parser.add_argument(
        "--phone-base-url",
        type=str,
        default=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        help="Phone Agent Model API base URL",
    )

    parser.add_argument(
        "--phone-model",
        type=str,
        default=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
        help="Phone Agent Model name",
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
        "task",
        nargs="?",
        type=str,
        help="Task to execute (interactive mode if not provided)",
    )

    parser.add_argument(
        "--web",
        action="store_true",
        help="Start the Web Interface",
    )

    return parser.parse_args()

def main():
    """主入口函数。"""
    args = parse_args()

    # 如果请求了 Web 模式，启动 Web 服务器
    if args.web:
        # 从参数设置环境变量，以便注册表可以使用它们
        if args.model_id:
            os.environ["LLM_MODEL"] = args.model_id
        if args.api_key:
            os.environ["LLM_API_KEY"] = args.api_key
        if args.base_url:
            os.environ["LLM_BASE_URL"] = args.base_url
        
        os.environ["PHONE_AGENT_BASE_URL"] = args.phone_base_url
        os.environ["PHONE_AGENT_MODEL"] = args.phone_model
        if args.device_id:
            os.environ["PHONE_AGENT_DEVICE_ID"] = args.device_id
            
        print("\n🚀 Starting AutoPhone Orchestrator Web Interface...")
        print(f"   Orchestrator Model: {args.model_id}")
        print(f"   Phone Agent Model: {args.phone_model}")
        print("   Listening on: http://localhost:8000")
        
        import uvicorn
        from web_main import app
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    # 检查系统要求（ADB 等）
    if not check_system_requirements():
        sys.exit(1)

    # 检查 Phone 模型 API 连接
    if not check_model_api(args.phone_base_url, args.phone_model):
        sys.exit(1)

    # 验证编排 Agent 的 API Key
    if not args.api_key:
        # 同时检查 DASHSCOPE_API_KEY，因为我们正在切换到 DashScope
        if not os.getenv("DASHSCOPE_API_KEY"):
            print("⚠️ Warning: No API Key found for Orchestrator Agent.")
            print("   Please set LLM_API_KEY or DASHSCOPE_API_KEY in your .env file or provide --api-key argument.")

    # 从参数设置环境变量，以便注册表可以使用它们
    if args.model_id:
        os.environ["LLM_MODEL"] = args.model_id
    if args.api_key:
        os.environ["LLM_API_KEY"] = args.api_key
    if args.base_url:
        os.environ["LLM_BASE_URL"] = args.base_url
    
    os.environ["PHONE_AGENT_BASE_URL"] = args.phone_base_url
    os.environ["PHONE_AGENT_MODEL"] = args.phone_model
    if args.device_id:
        os.environ["PHONE_AGENT_DEVICE_ID"] = args.device_id

    print("\n🚀 Initializing Orchestrator Agent (Registry Mode)...")
    print(f"   Orchestrator Model: {args.model_id}")
    print(f"   Phone Agent Model: {args.phone_model} @ {args.phone_base_url}")
    
    try:
        # 在这里导入以确保在注册表初始化之前设置好环境变量
        from phone_agent.registry import get_agent_by_id
        
        agent = get_agent_by_id("phone-orchestrator")
        if not agent:
            raise ValueError("Could not find 'phone-orchestrator' in registry")
            
        print("✅ Orchestrator Agent initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        sys.exit(1)

    # 使用提供的任务运行或进入交互模式
    if args.task:
        print(f"Task: {args.task}\n")
        agent.print_response(args.task, stream=True)
    else:
        # 交互模式
        print("Entering interactive mode. Type 'quit' to exit.\n")
        
        while True:
            try:
                task = input("Enter your task: ").strip()
                
                if task.lower() in ("quit", "exit", "q"):
                    print("Goodbye!")
                    break
                
                if not task:
                    continue
                    
                print()
                agent.print_response(task, stream=True)
                print()
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")

if __name__ == "__main__":
    main()
