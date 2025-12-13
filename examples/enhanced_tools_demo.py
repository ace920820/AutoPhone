#!/usr/bin/env python3
"""
增强工具调用模式演示
展示流式反馈、状态查询和错误处理功能
"""
import os
import sys
import json
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phone_agent.tools import AutoGLMTools
from phone_agent.logging_config import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger("enhanced_demo")

# 加载环境变量
load_dotenv()


def demo_streaming_feedback():
    """演示流式反馈功能"""
    print("\n" + "=" * 60)
    print("演示 1: 流式反馈")
    print("=" * 60)
    
    # 初始化工具
    tools = AutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    # 执行任务（会自动显示流式进度）
    print("\n执行任务: 打开设置")
    result = tools.run_phone_task("打开设置")
    print(f"\n最终结果: {result}")
    
    # 查看步骤历史
    print("\n步骤历史:")
    history = json.loads(tools.get_step_history())
    for i, step in enumerate(history, 1):
        print(f"  步骤 {i}: {step['action'].get('action', 'unknown')} - {'成功' if step['success'] else '失败'}")


def demo_status_query():
    """演示状态查询功能"""
    print("\n" + "=" * 60)
    print("演示 2: 状态查询")
    print("=" * 60)
    
    tools = AutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    # 查询初始状态
    print("\n1. 查询初始状态:")
    status = json.loads(tools.get_phone_status())
    print(json.dumps(status, ensure_ascii=False, indent=2))
    
    # 检查应用是否安装
    print("\n2. 检查应用安装状态:")
    apps_to_check = ["微信", "小红书", "淘宝", "不存在的应用"]
    for app in apps_to_check:
        result = tools.check_app_installed(app)
        print(f"  {app}: {result}")


def demo_info_extraction():
    """演示信息提取功能"""
    print("\n" + "=" * 60)
    print("演示 3: 信息提取")
    print("=" * 60)
    
    tools = AutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    # 先打开一个应用
    print("\n1. 打开设置应用...")
    tools.run_phone_task("打开设置")
    
    # 提取屏幕信息
    print("\n2. 提取屏幕信息...")
    info = tools.extract_screen_info("列出屏幕上可见的所有设置项")
    print("提取的信息:")
    print(json.dumps(json.loads(info), ensure_ascii=False, indent=2))


def demo_pause_resume():
    """演示暂停和恢复功能"""
    print("\n" + "=" * 60)
    print("演示 4: 暂停和恢复")
    print("=" * 60)
    
    tools = AutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    print("\n注意: 这个演示需要在多线程环境中才能看到效果")
    print("在实际使用中，可以在任务执行过程中调用 pause_phone_task()")
    
    # 演示暂停
    print("\n1. 暂停任务:")
    result = tools.pause_phone_task()
    print(f"  {result}")
    
    # 查询状态
    print("\n2. 查询状态:")
    status = json.loads(tools.get_phone_status())
    print(f"  is_paused: {status['is_paused']}")
    
    # 恢复任务
    print("\n3. 恢复任务:")
    result = tools.resume_phone_task()
    print(f"  {result}")


def demo_orchestrator_usage():
    """演示 Orchestrator 如何使用增强工具"""
    print("\n" + "=" * 60)
    print("演示 5: Orchestrator 智能使用工具")
    print("=" * 60)
    
    tools = AutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    # 模拟 Orchestrator 的智能决策流程
    print("\n任务: 在小红书搜索火锅店")
    
    # 步骤 1: 检查应用是否安装
    print("\n步骤 1: 检查小红书是否安装...")
    installed = tools.check_app_installed("小红书")
    print(f"  结果: {installed}")
    
    if installed == "未安装":
        print("  决策: 小红书未安装，无法执行任务")
        return
    
    # 步骤 2: 查询当前状态
    print("\n步骤 2: 查询当前手机状态...")
    status = json.loads(tools.get_phone_status())
    print(f"  当前应用: {status['current_app']}")
    print(f"  是否忙碌: {status['is_busy']}")
    
    # 步骤 3: 执行任务
    print("\n步骤 3: 执行搜索任务...")
    result = tools.run_phone_task("打开小红书搜索火锅店")
    print(f"  结果: {result}")
    
    # 步骤 4: 提取搜索结果
    print("\n步骤 4: 提取搜索结果...")
    info = tools.extract_screen_info("提取屏幕上的店名和评分")
    print("  提取的信息:")
    print(json.dumps(json.loads(info), ensure_ascii=False, indent=2))
    
    # 步骤 5: 查看执行历史
    print("\n步骤 5: 查看执行历史...")
    history = json.loads(tools.get_step_history())
    print(f"  总共执行了 {len(history)} 个步骤")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("增强工具调用模式演示")
    print("=" * 60)
    
    demos = [
        ("流式反馈", demo_streaming_feedback),
        ("状态查询", demo_status_query),
        ("信息提取", demo_info_extraction),
        ("暂停和恢复", demo_pause_resume),
        ("Orchestrator 智能使用", demo_orchestrator_usage),
    ]
    
    print("\n可用演示:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    print("  0. 运行所有演示")
    
    try:
        choice = input("\n请选择要运行的演示 (0-5): ").strip()
        
        if choice == "0":
            for name, demo_func in demos:
                try:
                    demo_func()
                except Exception as e:
                    print(f"\n❌ 演示 '{name}' 失败: {e}")
                    import traceback
                    traceback.print_exc()
        elif choice.isdigit() and 1 <= int(choice) <= len(demos):
            name, demo_func = demos[int(choice) - 1]
            demo_func()
        else:
            print("无效的选择")
    
    except KeyboardInterrupt:
        print("\n\n演示已中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
