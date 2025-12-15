# -*- coding: utf-8 -*-
"""
DecisionAgent 任务分解能力测试脚本
测试复杂任务是否能被正确分解为可执行的子步骤
"""
import os
import io
import sys

# 设置输出编码为 UTF-8，解决 Windows GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from phone_agent.multi_agent.decision_agent import DecisionAgent
from phone_agent.model import ModelConfig


def test_task_decomposition():
    """测试任务分解能力"""
    
    # 使用 DashScope API（Qwen3）
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "EMPTY":
        print("[X] 错误: 未设置 LLM_API_KEY 环境变量")
        return
    
    # 初始化 DecisionAgent - 使用 qwen-plus 或 qwen-turbo
    model_config = ModelConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus",  # 可改为 qwen-turbo 更便宜
        api_key=api_key
    )
    
    print("=" * 60)
    print("DecisionAgent 任务分解测试 (Task Decomposition)")
    print("=" * 60)
    
    decision_agent = DecisionAgent(model_config)
    
    # 测试任务 - 用户的真实复杂任务
    complex_task = """帮我规划明天的午餐。在大众点评找一家静安寺附近评分 4.5 分以上、人均消费150以下的日料餐厅。然后用高德地图查一下从徐家汇开车过去需要多久。发微信给妈妈发一条信息，邀请她来十一点半吃午饭，告诉她是哪家餐厅，地址和从徐家汇过去需要的时间"""
    
    print(f"\n[原始任务]\n{complex_task}\n")
    print("-" * 60)
    
    # 分解任务
    print("\n[DecisionAgent] 正在分解任务...\n")
    steps = decision_agent.decompose_task(complex_task)
    
    print("[分解结果]:")
    print("-" * 40)
    for i, step in enumerate(steps, 1):
        print(f"  步骤 {i}: {step}")
    print("-" * 40)
    
    # 分析分解质量
    print("\n[分解质量分析]:")
    
    # 检查关键筛选条件是否被保留
    all_steps_text = " ".join(steps).lower()
    
    checks = [
        ("静安寺", "位置条件"),
        ("4.5", "评分条件"),
        ("150", "人均消费条件"),
        ("日料", "餐厅类型"),
        ("高德", "导航应用"),
        ("徐家汇", "出发地点"),
        ("微信", "发送消息"),
        ("妈妈", "联系人"),
        ("十一点半", "时间"),
    ]
    
    print()
    for keyword, description in checks:
        found = keyword in all_steps_text
        status = "[OK]" if found else "[X]"
        print(f"  {status} {description}: '{keyword}' {'已包含' if found else '未包含'}")
    
    # 返回步骤数量
    print(f"\n共分解为 {len(steps)} 个步骤")
    
    return steps


def test_decision_making():
    """测试决策能力 - 模拟 PhoneAgent 执行中遇到的选择"""
    
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key or api_key == "EMPTY":
        return
    
    model_config = ModelConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus",
        api_key=api_key
    )
    
    print("\n" + "=" * 60)
    print("DecisionAgent 决策能力测试 (Decision Making)")
    print("=" * 60)
    
    decision_agent = DecisionAgent(model_config)
    
    # 模拟场景：搜索结果页有多家餐厅，需要选择
    context = {
        "current_app": "大众点评",
        "current_screen": "搜索结果页",
        "task": "找静安寺附近评分4.5以上、人均150以下的日料餐厅",
        "search_results": [
            {"name": "�的とや·とんかつ", "rating": 4.8, "price": 186, "distance": "1.2km"},
            {"name": "银座寿司", "rating": 4.6, "price": 128, "distance": "0.8km"},
            {"name": "山本居酒屋", "rating": 4.5, "price": 145, "distance": "1.5km"},
            {"name": "花丸乌冬", "rating": 4.3, "price": 65, "distance": "0.5km"},
        ]
    }
    
    options = [
        "选择鮨とや·とんかつ（评分4.8，人均186）",
        "选择银座寿司（评分4.6，人均128）",
        "选择山本居酒屋（评分4.5，人均145）",
        "选择花丸乌冬（评分4.3，人均65）",
        "继续滑动查看更多"
    ]
    
    print(f"\n[模拟场景]:")
    print(f"  任务目标: {context['task']}")
    print(f"\n  搜索结果:")
    for r in context['search_results']:
        print(f"    - {r['name']}: 评分{r['rating']}, 人均¥{r['price']}")
    
    print(f"\n[DecisionAgent] 正在决策...\n")
    
    result = decision_agent.decide(
        context=context,
        options=options,
        goal="选择最符合用户要求的餐厅"
    )
    
    print("[决策结果]:")
    print("-" * 40)
    print(f"  选择: {result.decision}")
    print(f"  推理: {result.reasoning}")
    print(f"  置信度: {result.confidence}")
    if result.alternatives:
        print(f"  备选: {result.alternatives}")
    print("-" * 40)
    
    # 检查是否正确排除了人均186的选项
    if "186" not in result.decision and ("128" in result.decision or "145" in result.decision):
        print("\n[OK] DecisionAgent 正确排除了超预算选项！")
    elif "186" in result.decision:
        print("\n[X] DecisionAgent 仍然选择了超预算选项")
    
    return result


if __name__ == "__main__":
    print("\n>>> 开始测试 DecisionAgent\n")
    
    # 测试 1: 任务分解
    steps = test_task_decomposition()
    
    # 测试 2: 决策能力
    decision = test_decision_making()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
