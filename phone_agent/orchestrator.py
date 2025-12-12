from agno.agent import Agent
from agno.models.openai import OpenAIChat
from phone_agent.tools import AutoGLMTools
import os

def create_orchestrator_agent(
    model_id: str = "gpt-4o",
    api_key: str | None = None,
    base_url: str | None = None,
    phone_base_url: str = "http://localhost:8000/v1",
    phone_model_name: str = "autoglm-phone-9b",
    device_id: str | None = None
) -> Agent:
    """
    创建并配置 Phone Orchestrator Agent。
    
    Args:
        model_id: 编排 Agent 使用的模型 ID
        api_key: 编排 Agent 使用的 API Key
        base_url: 编排 Agent 使用的 Base URL
        phone_base_url: Phone Agent 模型服务的 URL
        phone_model_name: Phone Agent 使用的模型名称
        device_id: ADB 设备 ID
        
    Returns:
        Agent: 配置好的 agno Agent 实例
    """
    
    # Initialize the phone tools
    phone_tools = AutoGLMTools(
        base_url=phone_base_url,
        model_name=phone_model_name,
        device_id=device_id
    )

    # Create the orchestrator agent
    agent = Agent(
        model=OpenAIChat(
            id=model_id,
            api_key=api_key,
            base_url=base_url,
            # Qwen/DashScope 不支持 'developer' 角色，将其映射回 'system'
            role_map={"developer": "system"}
        ),
        tools=[phone_tools],
        description="是一个智能手机任务编排专家，能够帮助用户完成跨应用的复杂任务。",
        instructions=[
            "你是一个智能手机任务编排专家。",
            "用户会给你一个复杂的任务（例如：'在小红书找一家好吃的火锅店，然后去大众点评看评分，最后用微信发给朋友'）。",
            "你需要将这个任务分解为多个逻辑清晰、可执行的子步骤。",
            "对于每个子步骤，使用 `run_phone_task` 工具来执行。",
            "在执行下一个步骤之前，请务必根据上一个步骤的返回结果来调整你的计划。如果上一步失败了，尝试通过不同的方式重试或者询问用户。",
            "不要一次性把所有步骤发给工具，必须一步一步执行，确保每一步都成功后再进行下一步。",
            "在调用工具时，给出的任务描述要具体、清晰，包含必要的信息（如应用名称、搜索关键词、具体操作等）。",
            "最终任务完成后，向用户汇报详细的结果。"
        ],
        markdown=True
    )
    
    return agent
