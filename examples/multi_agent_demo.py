#!/usr/bin/env python3
"""
多 Agent 协作演示
展示 PhoneAgent、InfoAgent 和 DecisionAgent 的协同工作。
"""
import os
import sys
import json
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phone_agent.multi_agent.enhanced_tools import EnhancedAutoGLMTools
from phone_agent.multi_agent.shared_state import get_shared_state
from phone_agent.memory import get_memory_manager
from phone_agent.logging_config import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger("multi_agent_demo")

# 加载环境变量
load_dotenv()


def demo_info_agent():
    """演示 InfoAgent 信息提取"""
    print("\n" + "=" * 60)
    print("演示 1: InfoAgent 信息提取")
    print("=" * 60)
    
    tools = EnhancedAutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    # 先打开一个应用
    print("\n1. 打开设置应用...")
    tools.run_phone_task("打开设置")
    
    # 提取屏幕信息
    print("\n2. InfoAgent 提取屏幕信息...")
    info = tools.extract_screen_info("列出屏幕上可见的所有设置项")
    print("提取结果:")
    print(info)
    
    # 提取特定字段
    print("\n3. InfoAgent 提取特定字段...")
    fields = tools.extract_specific_fields("应用名称,版本号")
    print("字段提取:")
    print(fields)
    
    # 验证内容
    print("\n4. InfoAgent 验证屏幕内容...")
    contains = tools.verify_screen_content("设置")
    print(f"屏幕是否包含'设置': {contains}")


def demo_decision_agent():
    """演示 DecisionAgent 智能决策"""
    print("\n" + "=" * 60)
    print("演示 2: DecisionAgent 智能决策")
    print("=" * 60)
    
    tools = EnhancedAutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    # 任务分解
    print("\n1. DecisionAgent 任务分解...")
    task = "在小红书找火锅店，然后去大众点评看评分，最后用微信分享"
    steps = tools.decompose_task(task)
    print("分解结果:")
    print(steps)
    
    # 做出决策
    print("\n2. DecisionAgent 做出决策...")
    context = json.dumps({"current_app": "桌面", "battery": 85})
    decision = tools.make_decision(
        goal="选择下一步操作",
        options="打开小红书,打开大众点评,打开微信",
        context=context
    )
    print("决策结果:")
    print(decision)
    
    # 策略选择
    print("\n3. DecisionAgent 策略选择...")
    strategies = json.dumps([
        {"name": "直接搜索", "description": "直接在当前应用搜索"},
        {"name": "切换应用", "description": "切换到其他应用搜索"},
        {"name": "使用浏览器", "description": "打开浏览器搜索"}
    ])
    strategy = tools.select_best_strategy(
        situation="需要搜索火锅店信息",
        strategies=strategies
    )
    print("策略选择:")
    print(strategy)


def demo_shared_state():
    """演示共享状态管理"""
    print("\n" + "=" * 60)
    print("演示 3: 共享状态管理")
    print("=" * 60)
    
    shared_state = get_shared_state()
    
    # 设置状态
    print("\n1. 设置共享状态...")
    shared_state.set("current_task", "搜索火锅店")
    shared_state.set("target_app", "小红书")
    shared_state.update({
        "search_keyword": "火锅",
        "location": "北京"
    })
    
    # 获取状态
    print("\n2. 获取共享状态...")
    print(f"当前任务: {shared_state.get('current_task')}")
    print(f"目标应用: {shared_state.get('target_app')}")
    
    # 状态快照
    print("\n3. 状态快照:")
    snapshot = shared_state.snapshot()
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    
    # 状态历史
    print("\n4. 状态历史:")
    history = shared_state.get_history(limit=5)
    for record in history:
        print(f"  - {record['action']}: {record.get('key', 'N/A')}")


def demo_memory_system():
    """演示记忆系统"""
    print("\n" + "=" * 60)
    print("演示 4: 记忆系统")
    print("=" * 60)
    
    memory = get_memory_manager()
    
    # 存储交互
    print("\n1. 存储交互历史...")
    interaction_id = memory.store_interaction(
        task="在小红书搜索火锅店",
        result="找到海底捞火锅",
        success=True,
        steps=5,
        duration=15.5,
        metadata={"app": "小红书", "keyword": "火锅"}
    )
    print(f"交互记录 ID: {interaction_id}")
    
    # 召回相似记录
    print("\n2. 召回相似记录...")
    similar = memory.recall_similar("搜索火锅", limit=3)
    print(f"找到 {len(similar)} 条相似记录:")
    for record in similar:
        print(f"  - {record['task'][:50]}... (步骤: {record['steps']})")
    
    # 设置偏好
    print("\n3. 设置用户偏好...")
    memory.set_preference("apps", "favorite", "小红书")
    memory.set_preference("search", "default_location", "北京")
    
    # 获取偏好
    print("\n4. 获取用户偏好...")
    favorite_app = memory.get_preference("apps", "favorite")
    print(f"最喜欢的应用: {favorite_app}")
    
    all_prefs = memory.get_all_preferences()
    print("所有偏好:")
    print(json.dumps(all_prefs, ensure_ascii=False, indent=2))
    
    # 统计信息
    print("\n5. 统计信息...")
    stats = memory.get_statistics()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def demo_collaborative_workflow():
    """演示多 Agent 协作工作流"""
    print("\n" + "=" * 60)
    print("演示 5: 多 Agent 协作工作流")
    print("=" * 60)
    
    tools = EnhancedAutoGLMTools(
        base_url=os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1"),
        model_name=os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b"),
    )
    
    shared_state = get_shared_state()
    memory = get_memory_manager()
    
    print("\n任务: 在小红书搜索火锅店并记录信息")
    
    # 步骤 1: DecisionAgent 分解任务
    print("\n步骤 1: DecisionAgent 分解任务...")
    task = "在小红书搜索火锅店"
    steps_json = tools.decompose_task(task)
    steps_data = json.loads(steps_json)
    steps = steps_data.get("steps", [task])
    print(f"分解为 {len(steps)} 个步骤:")
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    
    # 步骤 2: 检查应用是否安装
    print("\n步骤 2: 检查小红书是否安装...")
    installed = tools.check_app_installed("小红书")
    print(f"小红书: {installed}")
    
    if installed == "未安装":
        print("小红书未安装，任务无法继续")
        return
    
    # 步骤 3: PhoneAgent 执行第一个子任务
    print("\n步骤 3: PhoneAgent 执行任务...")
    result = tools.run_phone_task(steps[0] if steps else task)
    print(f"执行结果: {result}")
    
    # 步骤 4: InfoAgent 提取搜索结果
    print("\n步骤 4: InfoAgent 提取搜索结果...")
    info = tools.extract_screen_info("提取屏幕上的店名和评分")
    print("提取的信息:")
    print(info)
    
    # 步骤 5: 更新共享状态
    print("\n步骤 5: 更新共享状态...")
    shared_state.set("search_result", json.loads(info))
    shared_state.set("task_completed", True)
    
    # 步骤 6: 存储到记忆系统
    print("\n步骤 6: 存储到记忆系统...")
    memory.store_interaction(
        task=task,
        result=result,
        success=True,
        steps=len(steps),
        metadata={"extracted_info": json.loads(info)}
    )
    
    # 步骤 7: 查看共享状态
    print("\n步骤 7: 查看最终共享状态...")
    state_info = tools.get_shared_state_info()
    print("共享状态:")
    print(state_info)
    
    print("\n✅ 多 Agent 协作完成！")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("多 Agent 协作系统演示")
    print("=" * 60)
    
    demos = [
        ("InfoAgent 信息提取", demo_info_agent),
        ("DecisionAgent 智能决策", demo_decision_agent),
        ("共享状态管理", demo_shared_state),
        ("记忆系统", demo_memory_system),
        ("多 Agent 协作工作流", demo_collaborative_workflow),
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
