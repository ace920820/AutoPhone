"""
Memory 配置模块：基于 Agno SqliteDb 的本地存储

负责：
- 用户偏好记忆（常用联系人、喜好等）
- 会话历史存储
- 确保数据安全（本地存储，不上传云端）
"""

import os
import logging
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 默认数据目录
DEFAULT_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def ensure_data_dir(data_dir: Path | str | None = None) -> Path:
    """
    确保数据目录存在
    
    Args:
        data_dir: 数据目录路径，默认为项目根目录下的 data/
        
    Returns:
        数据目录路径
    """
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"数据目录: {data_dir}")
    return data_dir


def create_memory_db(
    db_name: str = "orchestrator.db",
    data_dir: Path | str | None = None,
):
    """
    创建 Agno SqliteDb 实例用于 Memory 存储
    
    Args:
        db_name: 数据库文件名
        data_dir: 数据目录路径
        
    Returns:
        SqliteDb 实例
    
    Example:
        >>> db = create_memory_db()
        >>> agent = Agent(db=db, enable_user_memories=True)
    """
    try:
        from agno.db.sqlite import SqliteDb
    except ImportError as e:
        logger.error("未安装 agno 库，请运行: pip install agno")
        raise ImportError(
            "需要安装 agno 库才能使用 Memory 功能。\n"
            "请运行: pip install agno"
        ) from e
    
    # 确保数据目录存在
    data_dir = ensure_data_dir(data_dir)
    db_path = data_dir / db_name
    
    logger.info(f"创建 Memory 数据库: {db_path}")
    
    # 创建 SqliteDb 实例
    db = SqliteDb(
        db_file=str(db_path),
        id="phone_orchestrator_db",
    )
    
    return db


def get_db_path(
    db_name: str = "orchestrator.db",
    data_dir: Path | str | None = None,
) -> str:
    """
    获取数据库文件路径（不创建 SqliteDb 实例）
    
    Args:
        db_name: 数据库文件名
        data_dir: 数据目录路径
        
    Returns:
        数据库文件路径字符串
    """
    data_dir = ensure_data_dir(data_dir)
    return str(data_dir / db_name)
