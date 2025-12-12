#!/usr/bin/env python3
"""
Orchestrator Agent CLI - AI-powered phone automation with task orchestration.

Usage:
    python orchestrator_main.py [OPTIONS]
"""

import argparse
import os
import sys
from dotenv import load_dotenv

from phone_agent.orchestrator import create_orchestrator_agent
from main import check_system_requirements, check_model_api

# Load environment variables
load_dotenv()

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Phone Agent Orchestrator - Complex task automation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Orchestrator Model options
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

    # Phone Agent Model options
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

    # Device options
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

    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()

    # Check system requirements (ADB, etc)
    if not check_system_requirements():
        sys.exit(1)

    # Check phone model API connectivity
    if not check_model_api(args.phone_base_url, args.phone_model):
        sys.exit(1)

    # Verify API Key for Orchestrator
    if not args.api_key:
        # Check for DASHSCOPE_API_KEY as well since we are switching to DashScope
        if not os.getenv("DASHSCOPE_API_KEY"):
            print("⚠️ Warning: No API Key found for Orchestrator Agent.")
            print("   Please set LLM_API_KEY or DASHSCOPE_API_KEY in your .env file or provide --api-key argument.")

    # Set environment variables from args so registry can pick them up
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
        # Import here to ensure env vars are set before registry initialization
        from phone_agent.registry import get_agent_by_id
        
        agent = get_agent_by_id("phone-orchestrator")
        if not agent:
            raise ValueError("Could not find 'phone-orchestrator' in registry")
            
        print("✅ Orchestrator Agent initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        sys.exit(1)

    # Run with provided task or enter interactive mode
    if args.task:
        print(f"Task: {args.task}\n")
        agent.print_response(args.task, stream=True)
    else:
        # Interactive mode
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
