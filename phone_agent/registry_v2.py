"""
Agent 注册表
负责初始化和管理编排 Agent，集成 DashScope 模型和 SQLite 存储。
"""
import os
from typing import Optional, Dict
from dotenv import load_dotenv

from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.sqlite import SqliteDb

from phone_agent.tools import AutoGLMTools

# 加载环境变量
load_dotenv()

# ============================================================
# 配置常量
# ============================================================
DB_FILE = "data/agentos_sessions.db"
PHONE_BASE_URL = os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1")
PHONE_MODEL_NAME = os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b")
PHONE_DEVICE_ID = os.getenv("PHONE_AGENT_DEVICE_ID")

# 确保数据目录存在
os.makedirs("data", exist_ok=True)

# ============================================================
# 数据库存储
# ============================================================
db = SqliteDb(
    db_file=DB_FILE,
    session_table="agent_sessions",
)

# ============================================================
# 模型工厂
# ============================================================
def get_model(model_id: Optional[str] = None):
    """
    获取 DashScope 模型实例
    """
    # 优先使用传入的 ID，否则使用环境变量配置的 LLM_MODEL，最后默认 qwen-plus
    final_model_id = model_id or os.getenv("LLM_MODEL", "qwen-plus")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    
    if not api_key:
        print("⚠️ Warning: No API Key found for DashScope (LLM_API_KEY or DASHSCOPE_API_KEY).")

    return DashScope(
        id=final_model_id,
        api_key=api_key,
        # DashScope 在 agno 中通常不需要手动指定 base_url，SDK 会处理
    )

# ============================================================
# 工具初始化
# ============================================================
phone_tools = AutoGLMTools(
    base_url=PHONE_BASE_URL,
    model_name=PHONE_MODEL_NAME,
    device_id=PHONE_DEVICE_ID
)

# ============================================================
# Agent 定义
# ============================================================

orchestrator_agent = Agent(
    id="phone-orchestrator",
    name="手机任务编排专家",
    model=get_model(),
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
    markdown=True,
    # 数据库存储 - 启用上下文记忆
    db=db,
    add_history_to_context=True,
    num_history_runs=5,
)

# ============================================================
# 注册表导出
# ============================================================
AGENT_MAP: Dict[str, Agent] = {
    "phone-orchestrator": orchestrator_agent,
}

def get_agent_by_id(agent_id: str = "phone-orchestrator") -> Optional[Agent]:
    return AGENT_MAP.get(agent_id)
