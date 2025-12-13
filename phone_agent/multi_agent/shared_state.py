"""
共享状态管理模块
提供多 Agent 之间的状态共享和同步。
"""
import threading
from typing import Any, Dict, Optional
from datetime import datetime
import json

from phone_agent.logging_config import get_logger

logger = get_logger("shared_state")


class SharedState:
    """
    多 Agent 共享状态管理器
    
    提供线程安全的状态存储和访问，支持：
    - 键值对存储
    - 状态快照
    - 状态历史记录
    - 状态订阅通知
    """
    
    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._history: list[Dict[str, Any]] = []
        self._max_history = 100
        self._subscribers: Dict[str, list] = {}
        
        logger.debug("SharedState 初始化完成")
    
    def set(self, key: str, value: Any, notify: bool = True) -> None:
        """
        设置状态值
        
        Args:
            key: 状态键
            value: 状态值
            notify: 是否通知订阅者
        """
        with self._lock:
            old_value = self._state.get(key)
            self._state[key] = value
            
            # 记录历史
            self._add_history({
                "action": "set",
                "key": key,
                "old_value": old_value,
                "new_value": value,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.debug(f"状态更新: {key} = {value}")
            
            # 通知订阅者
            if notify:
                self._notify_subscribers(key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取状态值
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值或默认值
        """
        with self._lock:
            value = self._state.get(key, default)
            logger.debug(f"状态读取: {key} = {value}")
            return value
    
    def update(self, updates: Dict[str, Any], notify: bool = True) -> None:
        """
        批量更新状态
        
        Args:
            updates: 要更新的键值对
            notify: 是否通知订阅者
        """
        with self._lock:
            for key, value in updates.items():
                self.set(key, value, notify=False)
            
            logger.debug(f"批量更新 {len(updates)} 个状态")
            
            # 统一通知
            if notify:
                for key, value in updates.items():
                    self._notify_subscribers(key, value)
    
    def delete(self, key: str) -> None:
        """删除状态"""
        with self._lock:
            if key in self._state:
                old_value = self._state.pop(key)
                self._add_history({
                    "action": "delete",
                    "key": key,
                    "old_value": old_value,
                    "timestamp": datetime.now().isoformat()
                })
                logger.debug(f"状态删除: {key}")
    
    def clear(self) -> None:
        """清空所有状态"""
        with self._lock:
            self._state.clear()
            self._add_history({
                "action": "clear",
                "timestamp": datetime.now().isoformat()
            })
            logger.debug("状态已清空")
    
    def snapshot(self) -> Dict[str, Any]:
        """
        获取状态快照
        
        Returns:
            当前状态的副本
        """
        with self._lock:
            return self._state.copy()
    
    def to_json(self) -> str:
        """
        将状态导出为 JSON
        
        Returns:
            JSON 格式的状态字符串
        """
        with self._lock:
            return json.dumps(self._state, ensure_ascii=False, indent=2)
    
    def from_json(self, json_str: str) -> None:
        """
        从 JSON 导入状态
        
        Args:
            json_str: JSON 格式的状态字符串
        """
        with self._lock:
            self._state = json.loads(json_str)
            logger.debug("从 JSON 导入状态")
    
    def get_history(self, limit: Optional[int] = None) -> list[Dict[str, Any]]:
        """
        获取状态历史
        
        Args:
            limit: 返回的历史记录数量限制
            
        Returns:
            历史记录列表
        """
        with self._lock:
            if limit:
                return self._history[-limit:]
            return self._history.copy()
    
    def subscribe(self, key: str, callback: callable) -> None:
        """
        订阅状态变化
        
        Args:
            key: 要订阅的状态键
            callback: 回调函数，接收 (key, value) 参数
        """
        with self._lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            self._subscribers[key].append(callback)
            logger.debug(f"订阅状态: {key}")
    
    def unsubscribe(self, key: str, callback: callable) -> None:
        """取消订阅"""
        with self._lock:
            if key in self._subscribers:
                try:
                    self._subscribers[key].remove(callback)
                    logger.debug(f"取消订阅: {key}")
                except ValueError:
                    pass
    
    def _add_history(self, record: Dict[str, Any]) -> None:
        """添加历史记录（内部方法）"""
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history.pop(0)
    
    def _notify_subscribers(self, key: str, value: Any) -> None:
        """通知订阅者（内部方法）"""
        if key in self._subscribers:
            for callback in self._subscribers[key]:
                try:
                    callback(key, value)
                except Exception as e:
                    logger.error(f"订阅回调执行失败: {e}")
    
    def __repr__(self) -> str:
        return f"SharedState({len(self._state)} keys)"
    
    def __str__(self) -> str:
        return self.to_json()


# 全局共享状态实例
_global_shared_state = SharedState()


def get_shared_state() -> SharedState:
    """获取全局共享状态实例"""
    return _global_shared_state
