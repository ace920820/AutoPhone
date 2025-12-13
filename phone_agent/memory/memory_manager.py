"""
记忆管理系统
提供长期记忆存储、检索和用户偏好管理。
"""
import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from phone_agent.logging_config import get_logger

logger = get_logger("memory_manager")


class MemoryManager:
    """
    记忆管理器
    
    功能：
    - 存储交互历史
    - 记录用户偏好
    - 语义搜索（基于关键词）
    - 统计分析
    """
    
    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = db_path
        
        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"MemoryManager 初始化完成 - 数据库: {db_path}")
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 交互历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                result TEXT,
                success BOOLEAN,
                steps INTEGER,
                duration REAL,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 用户偏好表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category, key)
            )
        """)
        
        # 应用使用统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_name TEXT NOT NULL,
                action TEXT,
                count INTEGER DEFAULT 1,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 关键词索引表（简单的语义搜索）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interaction_id INTEGER,
                keyword TEXT NOT NULL,
                FOREIGN KEY (interaction_id) REFERENCES interactions(id)
            )
        """)
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_keywords_keyword 
            ON keywords(keyword)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_timestamp 
            ON interactions(timestamp DESC)
        """)
        
        conn.commit()
        conn.close()
        
        logger.debug("数据库表初始化完成")
    
    def store_interaction(
        self,
        task: str,
        result: str,
        success: bool = True,
        steps: int = 0,
        duration: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        存储交互历史
        
        Args:
            task: 任务描述
            result: 执行结果
            success: 是否成功
            steps: 执行步骤数
            duration: 执行时长（秒）
            metadata: 额外元数据
            
        Returns:
            交互记录 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        
        cursor.execute("""
            INSERT INTO interactions (task, result, success, steps, duration, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task, result, success, steps, duration, metadata_json))
        
        interaction_id = cursor.lastrowid
        
        # 提取关键词
        keywords = self._extract_keywords(task)
        for keyword in keywords:
            cursor.execute("""
                INSERT INTO keywords (interaction_id, keyword)
                VALUES (?, ?)
            """, (interaction_id, keyword))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"存储交互记录: ID={interaction_id}, 任务={task[:50]}...")
        return interaction_id
    
    def recall_similar(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        召回相似的历史记录
        
        Args:
            query: 查询文本
            limit: 返回数量限制
            
        Returns:
            相似记录列表
        """
        keywords = self._extract_keywords(query)
        
        if not keywords:
            return self.get_recent_interactions(limit)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 基于关键词匹配
        placeholders = ",".join(["?" for _ in keywords])
        cursor.execute(f"""
            SELECT DISTINCT i.id, i.task, i.result, i.success, i.steps, i.timestamp
            FROM interactions i
            JOIN keywords k ON i.id = k.interaction_id
            WHERE k.keyword IN ({placeholders})
            ORDER BY i.timestamp DESC
            LIMIT ?
        """, (*keywords, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "task": row[1],
                "result": row[2],
                "success": row[3],
                "steps": row[4],
                "timestamp": row[5]
            })
        
        conn.close()
        
        logger.debug(f"召回 {len(results)} 条相似记录")
        return results
    
    def get_recent_interactions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的交互记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, task, result, success, steps, timestamp
            FROM interactions
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "id": row[0],
                "task": row[1],
                "result": row[2],
                "success": row[3],
                "steps": row[4],
                "timestamp": row[5]
            })
        
        conn.close()
        return results
    
    def set_preference(
        self,
        category: str,
        key: str,
        value: Any,
        user_id: str = "default"
    ) -> None:
        """
        设置用户偏好
        
        Args:
            category: 偏好类别，例如 "apps", "settings"
            key: 偏好键
            value: 偏好值
            user_id: 用户 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        value_json = json.dumps(value, ensure_ascii=False)
        
        cursor.execute("""
            INSERT OR REPLACE INTO preferences (user_id, category, key, value, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, category, key, value_json))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"设置偏好: {category}.{key} = {value}")
    
    def get_preference(
        self,
        category: str,
        key: str,
        user_id: str = "default",
        default: Any = None
    ) -> Any:
        """获取用户偏好"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT value FROM preferences
            WHERE user_id = ? AND category = ? AND key = ?
        """, (user_id, category, key))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return default
    
    def get_all_preferences(
        self,
        category: Optional[str] = None,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """获取所有偏好"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute("""
                SELECT key, value FROM preferences
                WHERE user_id = ? AND category = ?
            """, (user_id, category))
        else:
            cursor.execute("""
                SELECT category, key, value FROM preferences
                WHERE user_id = ?
            """, (user_id,))
        
        preferences = {}
        for row in cursor.fetchall():
            if category:
                preferences[row[0]] = json.loads(row[1])
            else:
                cat, key, value = row
                if cat not in preferences:
                    preferences[cat] = {}
                preferences[cat][key] = json.loads(value)
        
        conn.close()
        return preferences
    
    def record_app_usage(self, app_name: str, action: str = "open") -> None:
        """记录应用使用"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO app_usage (app_name, action, count, last_used)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(rowid) DO UPDATE SET
                count = count + 1,
                last_used = CURRENT_TIMESTAMP
        """, (app_name, action))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"记录应用使用: {app_name} - {action}")
    
    def get_frequently_used_apps(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取常用应用"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT app_name, action, count, last_used
            FROM app_usage
            ORDER BY count DESC, last_used DESC
            LIMIT ?
        """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "app_name": row[0],
                "action": row[1],
                "count": row[2],
                "last_used": row[3]
            })
        
        conn.close()
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总交互次数
        cursor.execute("SELECT COUNT(*) FROM interactions")
        total_interactions = cursor.fetchone()[0]
        
        # 成功率
        cursor.execute("SELECT COUNT(*) FROM interactions WHERE success = 1")
        successful_interactions = cursor.fetchone()[0]
        success_rate = successful_interactions / total_interactions if total_interactions > 0 else 0
        
        # 平均步骤数
        cursor.execute("SELECT AVG(steps) FROM interactions WHERE steps > 0")
        avg_steps = cursor.fetchone()[0] or 0
        
        # 最常用应用
        cursor.execute("""
            SELECT app_name, SUM(count) as total
            FROM app_usage
            GROUP BY app_name
            ORDER BY total DESC
            LIMIT 5
        """)
        top_apps = [{"app": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "total_interactions": total_interactions,
            "successful_interactions": successful_interactions,
            "success_rate": round(success_rate, 2),
            "average_steps": round(avg_steps, 1),
            "top_apps": top_apps
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简单实现）"""
        # 移除标点符号，分词
        import re
        words = re.findall(r'\w+', text.lower())
        
        # 过滤停用词（简单版本）
        stopwords = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        return list(set(keywords))[:10]  # 最多10个关键词
    
    def clear_old_records(self, days: int = 30) -> int:
        """清理旧记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM interactions
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days,))
        
        deleted = cursor.rowcount
        
        # 清理孤立的关键词
        cursor.execute("""
            DELETE FROM keywords
            WHERE interaction_id NOT IN (SELECT id FROM interactions)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"清理了 {deleted} 条旧记录")
        return deleted


# 全局记忆管理器实例
_global_memory_manager = None


def get_memory_manager(db_path: str = "data/memory.db") -> MemoryManager:
    """获取全局记忆管理器实例"""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = MemoryManager(db_path)
    return _global_memory_manager
