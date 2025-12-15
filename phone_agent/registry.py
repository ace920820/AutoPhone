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

from phone_agent.logging_config import get_logger, setup_logging

# 初始化日志系统
setup_logging()
logger = get_logger("registry")

# 加载环境变量
load_dotenv()
logger.debug("环境变量已加载")

# ============================================================
# 配置常量
# ============================================================
DB_FILE = "data/agentos_sessions.db"
PHONE_BASE_URL = os.getenv("PHONE_AGENT_BASE_URL", "http://localhost:8000/v1")
PHONE_MODEL_NAME = os.getenv("PHONE_AGENT_MODEL", "autoglm-phone-9b")
PHONE_DEVICE_ID = os.getenv("PHONE_AGENT_DEVICE_ID")

# 确保数据目录存在
os.makedirs("data", exist_ok=True)
logger.debug(f"数据目录已创建: data/")

# ============================================================
# 数据库存储
# ============================================================
logger.debug(f"初始化 SQLite 数据库: {DB_FILE}")
db = SqliteDb(
    db_file=DB_FILE,
    session_table="agent_sessions",
)
logger.info("SQLite 会话存储已初始化")

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
    base_url = os.getenv("LLM_BASE_URL")
    
    logger.debug(f"创建 DashScope 模型: {final_model_id}")
    
    if not api_key:
        logger.warning("未找到 DashScope API Key (LLM_API_KEY 或 DASHSCOPE_API_KEY)")

    model = DashScope(
        id=final_model_id,
        api_key=api_key,
        base_url=base_url, # 显式传入 base_url，解决默认使用国际版端点导致 CN Key 报错的问题
    )
    logger.info(f"DashScope 模型已初始化: {final_model_id}")
    return model

# ============================================================
# 工具初始化
# ============================================================
logger.info("开始初始化 Agent 注册表")
from phone_agent.tools import AutoGLMTools

logger.debug(f"初始化 AutoGLM 工具: model={PHONE_MODEL_NAME}, url={PHONE_BASE_URL}")
phone_tools = AutoGLMTools(
    base_url=PHONE_BASE_URL,
    model_name=PHONE_MODEL_NAME,
    device_id=PHONE_DEVICE_ID
)
logger.info("AutoGLM 工具已初始化")

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
        
        # 任务分解指导
        "【重要】对于复杂任务（涉及多个应用、多个筛选条件如价格/评分限制、或包含'然后'/'并且'等连接词），"
        "请先使用 `decompose_task` 工具将任务分解为具体步骤。这能确保所有筛选条件（如'人均150以下'、'评分4.5以上'）都被明确保留。",
        
        "对于每个子步骤，使用 `run_phone_task` 工具来执行。",
        "在执行下一个步骤之前，请务必根据上一个步骤的返回结果来调整你的计划。如果上一步失败了，尝试通过不同的方式重试或者询问用户。",
        "不要一次性把所有步骤发给工具，必须一步一步执行，确保每一步都成功后再进行下一步。",
        "在调用工具时，给出的任务描述要具体、清晰，包含必要的信息（如应用名称、搜索关键词、具体筛选条件等）。",
        
        # 筛选条件强调
        "【筛选条件】当任务包含价格、评分、距离等筛选条件时，必须在每个相关步骤中明确提及这些条件，"
        "例如：'筛选人均消费150元以下的餐厅'而不是简单的'选择一家餐厅'。",
        
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
    agent = AGENT_MAP.get(agent_id)
    if agent:
        logger.debug(f"获取 Agent: {agent_id}")
    else:
        logger.warning(f"Agent 未找到: {agent_id}")
    return agent

logger.info("Agent 注册表初始化完成")
