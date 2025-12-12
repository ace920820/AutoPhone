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
        default=os.getenv("ORCHESTRATOR_MODEL", "gpt-4o"),
        help="Orchestrator model ID (default: gpt-4o)",
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

    # Verify OpenAI API Key for Orchestrator
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ Warning: OPENAI_API_KEY environment variable is not set.")
        print("   The orchestrator agent requires an OpenAI API key to function.")
        print("   Please set it in your environment or .env file.")
        # We don't exit here, allowing the agno framework to handle the error if it occurs

    print("\n🚀 Initializing Orchestrator Agent...")
    print(f"   Orchestrator Model: {args.model_id}")
    print(f"   Phone Agent Model: {args.phone_model} @ {args.phone_base_url}")
    
    try:
        agent = create_orchestrator_agent(
            model_id=args.model_id,
            phone_base_url=args.phone_base_url,
            phone_model_name=args.phone_model,
            device_id=args.device_id
        )
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
