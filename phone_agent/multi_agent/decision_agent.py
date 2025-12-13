"""
决策 Agent
负责根据当前状态和可选操作做出智能决策。
"""
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from phone_agent.model import ModelClient, ModelConfig
from phone_agent.logging_config import get_logger
from phone_agent.multi_agent.shared_state import SharedState

logger = get_logger("decision_agent")


@dataclass
class DecisionResult:
    """决策结果"""
    success: bool
    decision: str
    reasoning: str
    confidence: float = 0.0
    alternatives: List[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class DecisionAgent:
    """
    决策 Agent
    
    根据当前状态、历史信息和可选操作，做出智能决策。
    支持多种决策场景：
    - 任务分解
    - 策略选择
    - 错误恢复
    - 优先级排序
    """
    
    def __init__(
        self,
        model_config: ModelConfig,
        shared_state: Optional[SharedState] = None
    ):
        self.model_client = ModelClient(model_config)
        self.shared_state = shared_state
        
        logger.info(f"DecisionAgent 初始化完成 - 模型: {model_config.model_name}")
    
    def decide(
        self,
        context: Dict[str, Any],
        options: List[str],
        goal: str
    ) -> DecisionResult:
        """
        做出决策
        
        Args:
            context: 当前上下文信息
            options: 可选操作列表
            goal: 决策目标
            
        Returns:
            DecisionResult: 决策结果
        """
        logger.info(f"开始决策: {goal}")
        logger.debug(f"上下文: {context}")
        logger.debug(f"选项: {options}")
        
        try:
            # 构建提示
            system_prompt = """你是一个智能决策专家。
你的任务是根据当前状态和可选操作，选择最佳方案。

要求：
1. 仔细分析当前状态
2. 评估每个选项的优缺点
3. 选择最优方案
4. 给出清晰的推理过程
5. 返回 JSON 格式：
{
  "decision": "选择的操作",
  "reasoning": "推理过程",
  "confidence": 0.0-1.0,
  "alternatives": ["备选方案1", "备选方案2"]
}"""
            
            user_prompt = f"""目标: {goal}

当前状态:
{json.dumps(context, ensure_ascii=False, indent=2)}

可选操作:
{json.dumps(options, ensure_ascii=False, indent=2)}

请分析并选择最佳操作，返回 JSON 格式的决策结果。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # 请求模型
            response = self.model_client.request(messages)
            
            # 解析响应
            decision_data = self._parse_decision_response(response.action)
            
            result = DecisionResult(
                success=True,
                decision=decision_data.get("decision", options[0] if options else ""),
                reasoning=decision_data.get("reasoning", ""),
                confidence=decision_data.get("confidence", 0.5),
                alternatives=decision_data.get("alternatives", [])
            )
            
            logger.info(f"决策完成: {result.decision} (置信度: {result.confidence})")
            
            # 更新共享状态
            if self.shared_state:
                self.shared_state.set("last_decision", {
                    "goal": goal,
                    "decision": result.decision,
                    "reasoning": result.reasoning,
                    "confidence": result.confidence
                })
            
            return result
            
        except Exception as e:
            logger.error(f"决策异常: {e}", exc_info=True)
            return DecisionResult(
                success=False,
                decision="",
                reasoning="",
                error=str(e)
            )
    
    def decompose_task(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        任务分解
        
        Args:
            task: 复杂任务描述
            context: 上下文信息
            
        Returns:
            子任务列表
        """
        logger.info(f"任务分解: {task}")
        
        try:
            system_prompt = """你是任务分解专家。
将复杂任务分解为可执行的子步骤。

要求：
1. 步骤要具体、可执行
2. 步骤之间有逻辑顺序
3. 每个步骤都是原子操作
4. 返回 JSON 格式：{"steps": ["步骤1", "步骤2", ...]}"""
            
            context_str = ""
            if context:
                context_str = f"\n\n当前上下文:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
            
            user_prompt = f"""任务: {task}{context_str}

请将任务分解为具体的执行步骤，返回 JSON 格式。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.model_client.request(messages)
            data = self._parse_decision_response(response.action)
            
            steps = data.get("steps", [])
            logger.info(f"任务分解完成: {len(steps)} 个步骤")
            
            return steps
            
        except Exception as e:
            logger.error(f"任务分解异常: {e}", exc_info=True)
            return [task]  # 失败时返回原任务
    
    def select_strategy(
        self,
        situation: str,
        strategies: List[Dict[str, Any]]
    ) -> DecisionResult:
        """
        策略选择
        
        Args:
            situation: 当前情况描述
            strategies: 可选策略列表，每个策略包含 name 和 description
            
        Returns:
            DecisionResult: 选择的策略
        """
        logger.info(f"策略选择: {situation}")
        
        options = [s["name"] for s in strategies]
        context = {
            "situation": situation,
            "strategies": strategies
        }
        
        return self.decide(
            context=context,
            options=options,
            goal="选择最适合当前情况的策略"
        )
    
    def prioritize(
        self,
        items: List[str],
        criteria: str
    ) -> List[str]:
        """
        优先级排序
        
        Args:
            items: 待排序项目列表
            criteria: 排序标准
            
        Returns:
            排序后的列表
        """
        logger.info(f"优先级排序: {len(items)} 个项目")
        
        try:
            system_prompt = """你是优先级排序专家。
根据给定标准对项目进行排序。

返回 JSON 格式：{"sorted_items": ["项目1", "项目2", ...]}"""
            
            user_prompt = f"""排序标准: {criteria}

待排序项目:
{json.dumps(items, ensure_ascii=False, indent=2)}

请按照标准排序，返回 JSON 格式。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.model_client.request(messages)
            data = self._parse_decision_response(response.action)
            
            sorted_items = data.get("sorted_items", items)
            logger.info(f"排序完成")
            
            return sorted_items
            
        except Exception as e:
            logger.error(f"排序异常: {e}", exc_info=True)
            return items  # 失败时返回原列表
    
    def should_retry(
        self,
        error: str,
        attempt_count: int,
        max_attempts: int = 3
    ) -> bool:
        """
        判断是否应该重试
        
        Args:
            error: 错误信息
            attempt_count: 当前尝试次数
            max_attempts: 最大尝试次数
            
        Returns:
            bool: 是否应该重试
        """
        if attempt_count >= max_attempts:
            return False
        
        # 使用决策模型判断
        context = {
            "error": error,
            "attempt_count": attempt_count,
            "max_attempts": max_attempts
        }
        
        result = self.decide(
            context=context,
            options=["重试", "放弃"],
            goal="判断是否应该重试"
        )
        
        return result.decision == "重试"
    
    def _parse_decision_response(self, response: str) -> Dict[str, Any]:
        """解析决策响应"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            return {"decision": response}
    
    def get_last_decision(self) -> Optional[Dict[str, Any]]:
        """获取最后一次决策结果"""
        if self.shared_state:
            return self.shared_state.get("last_decision")
        return None
