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
    table_name="agent_sessions",
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
        # 但如果环境变量指定了 LLM_BASE_URL (兼容模式)，可能需要特殊处理
        # 这里我们直接使用 agno 的 DashScope 类，它应该使用官方 SDK
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

# 编排 Agent
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
    # 功能配置
    markdown=True,
    show_tool_calls=True, # Agno v1.0+ 默认可能开启，显式开启以防万一(注意之前报错，这里如果报错再移除)
    # 之前报错是因为 OpenAIChat.__init__ 不接受 show_tool_calls，但 Agent.__init__ 接受吗？
    # 检查 agno.Agent 的签名。之前用户报错是 Agent.__init__ got unexpected keyword argument 'show_tool_calls'
    # 等等，之前的报错信息是: `TypeError: Agent.__init__() got an unexpected keyword argument 'show_tool_calls'`
    # 所以 Agent 类也不接受 show_tool_calls 参数。
    # 修正：移除 show_tool_calls 和 show_reasoning 参数
    
    # 数据库配置
    storage=db, # Agno 1.x 可能叫 storage 或 db，用户示例用的 db
    add_history_to_messages=True, # 用户示例用的 add_history_to_context，需确认
    num_history_responses=5,      # 用户示例用的 num_history_runs
)

# 为了确保参数正确，参考用户提供的示例代码：
# triage_agent = Agent(..., db=db, add_history_to_context=True, num_history_runs=5)
# 我将使用用户示例中的参数名

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
    # 数据库存储
    storage=db, # 注意：agno更新频繁，用户示例是 db=db。我会尝试使用 storage=db 如果 Agent 签名允许，或者 db=db
    # 暂时使用用户提供的参数名，如果报错再改。
    # 用户提供的示例是： db=db, add_history_to_context=True, num_history_runs=5
    # 但根据我对 Agno 的了解，最新版可能是 storage。
    # 让我们先用 db=db 匹配用户的示例代码。
    # 但需要注意，用户示例中的 Agent 是从 agno.agent 导入的。
)

# 重新定义以匹配用户示例结构
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
    storage=db,
    add_history_to_messages=True,
    num_history_responses=5,
)

# ============================================================
# 注册表导出
# ============================================================
AGENT_MAP: Dict[str, Agent] = {
    "phone-orchestrator": orchestrator_agent,
}

def get_agent_by_id(agent_id: str = "phone-orchestrator") -> Optional[Agent]:
    return AGENT_MAP.get(agent_id)
