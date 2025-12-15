# -*- coding: utf-8 -*-
"""
测试 DecisionAgent 集成到 AutoGLMTools 的效果
"""
import os
import io
import sys

# 设置输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_decompose_task_tool():
    """测试 decompose_task 工具是否正常工作"""
    
    print("=" * 60)
    print("测试 AutoGLMTools.decompose_task 集成")
    print("=" * 60)
    
    # 导入 AutoGLMTools
    from phone_agent.tools import AutoGLMTools
    
    # 初始化（不需要真正的 PhoneAgent 连接来测试 decompose_task）
    print("\n[1] 初始化 AutoGLMTools...")
    
    try:
        tools = AutoGLMTools(
            base_url="http://localhost:8000/v1",  # 不会真正连接
            model_name="autoglm-phone-9b",
            device_id=None
        )
        print("    AutoGLMTools 初始化成功")
        
        # 检查 DecisionAgent 是否可用
        if tools.decision_agent:
            print("    DecisionAgent 已启用")
        else:
            print("    [警告] DecisionAgent 不可用")
            return
            
    except Exception as e:
        print(f"    初始化失败: {e}")
        return
    
    # 测试任务分解
    print("\n[2] 测试任务分解...")
    
    complex_task = """帮我规划明天的午餐。在大众点评找一家静安寺附近评分 4.5 分以上、人均消费150以下的日料餐厅。然后用高德地图查一下从徐家汇开车过去需要多久。发微信给妈妈发一条信息，邀请她来十一点半吃午饭，告诉她是哪家餐厅，地址和从徐家汇过去需要的时间"""
    
    print(f"\n    原始任务: {complex_task[:60]}...")
    print("\n    调用 decompose_task...")
    
    result = tools.decompose_task(complex_task)
    
    print("\n    分解结果:")
    print("-" * 50)
    
    import json
    try:
        data = json.loads(result)
        steps = data.get("steps", [])
        for i, step in enumerate(steps, 1):
            print(f"      步骤 {i}: {step}")
        print("-" * 50)
        print(f"\n    共 {len(steps)} 个步骤")
        
        # 检查关键条件是否保留
        all_text = " ".join(steps).lower()
        checks = [
            ("150", "人均消费条件"),
            ("4.5", "评分条件"),
            ("静安寺", "位置条件"),
            ("日料", "餐厅类型"),
        ]
        
        print("\n[3] 检查关键筛选条件是否保留:")
        all_passed = True
        for keyword, desc in checks:
            found = keyword in all_text
            status = "[OK]" if found else "[X]"
            print(f"      {status} {desc}: '{keyword}'")
            if not found:
                all_passed = False
        
        if all_passed:
            print("\n    [成功] 所有关键条件都已保留!")
        else:
            print("\n    [警告] 部分条件可能丢失")
            
    except json.JSONDecodeError as e:
        print(f"    JSON 解析失败: {e}")
        print(f"    原始结果: {result}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_decompose_task_tool()
