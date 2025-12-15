"""
增强的多 Agent 工具集
整合 PhoneAgent、InfoAgent 和 DecisionAgent 的混合架构工具。
"""
import json
from typing import Optional, Dict, Any

from agno.tools import Toolkit

from phone_agent.agent import PhoneAgent, AgentConfig, StepResult
from phone_agent.model import ModelConfig
from phone_agent.multi_agent.info_agent import InfoAgent
from phone_agent.multi_agent.decision_agent import DecisionAgent
from phone_agent.multi_agent.shared_state import SharedState, get_shared_state
from phone_agent.logging_config import get_logger

logger = get_logger("enhanced_tools")


class EnhancedAutoGLMTools(Toolkit):
    """
    增强的 AutoGLM 工具集 - 混合多 Agent 架构
    
    整合三个专业 Agent：
    - PhoneAgent: 执行手机操作
    - InfoAgent: 提取屏幕信息
    - DecisionAgent: 智能决策
    
    通过 SharedState 实现状态共享和协作。
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model_name: str = "autoglm-phone-9b",
        device_id: Optional[str] = None,
        orchestrator_model: Optional[str] = None
    ):
        super().__init__(name="enhanced_autoglm_tools")
        
        logger.info(f"EnhancedAutoGLMTools 初始化 - 模型: {model_name}, 设备: {device_id or '默认'}")
        
        # 共享状态
        self.shared_state = get_shared_state()
        
        # 初始化 PhoneAgent
        phone_model_config = ModelConfig(
            base_url=base_url,
            model_name=model_name
        )
        phone_agent_config = AgentConfig(
            device_id=device_id,
            max_steps=50,
            verbose=True
        )
        self.phone_agent = PhoneAgent(phone_model_config, phone_agent_config)
        
        # 初始化 InfoAgent
        self.info_agent = InfoAgent(
            model_config=phone_model_config,
            device_id=device_id,
            shared_state=self.shared_state
        )
        
        # 初始化 DecisionAgent（可以使用不同的模型）
        decision_model_config = ModelConfig(
            base_url=base_url,
            model_name=orchestrator_model or model_name
        )
        self.decision_agent = DecisionAgent(
            model_config=decision_model_config,
            shared_state=self.shared_state
        )
        
        self._step_history: list[Dict[str, Any]] = []
        
        # 注册所有工具
        self._register_tools()
        
        logger.info("所有 Agent 和工具已初始化完成")
    
    def _register_tools(self):
        """注册所有工具"""
        # PhoneAgent 工具
        self.register(self.run_phone_task)
        self.register(self.get_phone_status)
        self.register(self.pause_phone_task)
        self.register(self.resume_phone_task)
        
        # InfoAgent 工具
        self.register(self.extract_screen_info)
        self.register(self.extract_list_items)
        self.register(self.extract_specific_fields)
        self.register(self.verify_screen_content)
        
        # DecisionAgent 工具
        self.register(self.make_decision)
        self.register(self.decompose_task)
        self.register(self.select_best_strategy)
        
        # 状态管理工具
        self.register(self.get_shared_state_info)
        self.register(self.get_step_history)
        self.register(self.check_app_installed)
        
        logger.debug("已注册 15 个工具方法")
    
    # ========== PhoneAgent 工具 ==========
    
    def run_phone_task(self, task_description: str) -> str:
        """
        执行手机操作任务（PhoneAgent）
        
        Args:
            task_description: 任务描述
            
        Returns:
            执行结果
        """
        logger.info(f"📱 PhoneAgent 执行任务: {task_description}")
        print(f"\n[PhoneAgent] 开始执行: {task_description}")
        
        self._step_history = []
        
        def step_callback(step_result: StepResult):
            step_info = {
                "agent": "PhoneAgent",
                "step": self.phone_agent.step_count,
                "success": step_result.success,
                "action": step_result.action,
                "thinking": step_result.thinking,
            }
            self._step_history.append(step_info)
            self.shared_state.set(f"phone_step_{self.phone_agent.step_count}", step_info)
            
            action_name = step_result.action.get("action", "unknown") if step_result.action else "unknown"
            status = "✅" if step_result.success else "❌"
            print(f"  {status} 步骤 {self.phone_agent.step_count}: {action_name}")
        
        try:
            self.phone_agent.reset()
            self.phone_agent.set_step_callback(step_callback)
            
            result = self.phone_agent.run(task_description)
            
            self.shared_state.set("last_phone_task", {
                "task": task_description,
                "result": result,
                "steps": self.phone_agent.step_count
            })
            
            logger.info(f"✅ PhoneAgent 任务完成: {result}")
            print(f"[PhoneAgent] 完成: {result}\n")
            return result
            
        except Exception as e:
            error_msg = f"任务执行失败: {str(e)}"
            logger.error(f"❌ PhoneAgent 失败: {e}", exc_info=True)
            print(f"[PhoneAgent] {error_msg}\n")
            return error_msg
    
    def get_phone_status(self) -> str:
        """获取手机和 PhoneAgent 状态"""
        from phone_agent.adb import get_current_app
        
        try:
            state = self.phone_agent.get_state()
            
            try:
                current_app = get_current_app(self.phone_agent.agent_config.device_id)
                state["current_app"] = current_app
            except Exception as e:
                logger.warning(f"获取当前应用失败: {e}")
            
            return json.dumps(state, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def pause_phone_task(self) -> str:
        """暂停 PhoneAgent 任务"""
        try:
            self.phone_agent.pause()
            return "任务已暂停"
        except Exception as e:
            return f"暂停失败: {str(e)}"
    
    def resume_phone_task(self) -> str:
        """恢复 PhoneAgent 任务"""
        try:
            self.phone_agent.resume()
            return "任务已恢复"
        except Exception as e:
            return f"恢复失败: {str(e)}"
    
    # ========== InfoAgent 工具 ==========
    
    def extract_screen_info(self, query: str) -> str:
        """
        从屏幕提取信息（InfoAgent）
        
        Args:
            query: 要提取的信息描述
            
        Returns:
            JSON 格式的提取结果
        """
        logger.info(f"📸 InfoAgent 提取信息: {query}")
        
        try:
            result = self.info_agent.extract(query)
            
            if result.success:
                logger.info(f"✅ InfoAgent 提取成功")
                return json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                logger.warning(f"⚠️ InfoAgent 提取失败: {result.error}")
                return json.dumps({"error": result.error}, ensure_ascii=False)
                
        except Exception as e:
            error_msg = f"信息提取异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg}, ensure_ascii=False)
    
    def extract_list_items(self, item_description: str) -> str:
        """
        提取列表项（InfoAgent）
        
        Args:
            item_description: 列表项描述，例如 "商品"、"联系人"
            
        Returns:
            JSON 格式的列表
        """
        logger.info(f"📋 InfoAgent 提取列表: {item_description}")
        
        try:
            result = self.info_agent.extract_list(item_description)
            
            if result.success:
                return json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"error": result.error}, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def extract_specific_fields(self, fields: str) -> str:
        """
        提取指定字段（InfoAgent）
        
        Args:
            fields: 逗号分隔的字段列表，例如 "店名,评分,价格"
            
        Returns:
            JSON 格式的字段值
        """
        logger.info(f"🔍 InfoAgent 提取字段: {fields}")
        
        try:
            field_list = [f.strip() for f in fields.split(",")]
            result = self.info_agent.extract_fields(field_list)
            
            if result.success:
                return json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"error": result.error}, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def verify_screen_content(self, expected_content: str) -> str:
        """
        验证屏幕内容（InfoAgent）
        
        Args:
            expected_content: 预期内容描述
            
        Returns:
            "是" 或 "否"
        """
        logger.info(f"✓ InfoAgent 验证内容: {expected_content}")
        
        try:
            contains = self.info_agent.verify_screen_content(expected_content)
            return "是" if contains else "否"
        except Exception as e:
            return f"验证失败: {str(e)}"
    
    # ========== DecisionAgent 工具 ==========
    
    def make_decision(self, goal: str, options: str, context: str = "{}") -> str:
        """
        做出决策（DecisionAgent）
        
        Args:
            goal: 决策目标
            options: 逗号分隔的选项列表
            context: JSON 格式的上下文信息
            
        Returns:
            JSON 格式的决策结果
        """
        logger.info(f"🤔 DecisionAgent 决策: {goal}")
        
        try:
            option_list = [o.strip() for o in options.split(",")]
            context_dict = json.loads(context) if context != "{}" else {}
            
            result = self.decision_agent.decide(
                context=context_dict,
                options=option_list,
                goal=goal
            )
            
            if result.success:
                return json.dumps({
                    "decision": result.decision,
                    "reasoning": result.reasoning,
                    "confidence": result.confidence,
                    "alternatives": result.alternatives
                }, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"error": result.error}, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def decompose_task(self, task: str, context: str = "{}") -> str:
        """
        任务分解（DecisionAgent）
        
        Args:
            task: 复杂任务描述
            context: JSON 格式的上下文信息
            
        Returns:
            JSON 格式的步骤列表
        """
        logger.info(f"📋 DecisionAgent 任务分解: {task}")
        
        try:
            context_dict = json.loads(context) if context != "{}" else None
            steps = self.decision_agent.decompose_task(task, context_dict)
            
            return json.dumps({"steps": steps}, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def select_best_strategy(self, situation: str, strategies: str) -> str:
        """
        选择最佳策略（DecisionAgent）
        
        Args:
            situation: 当前情况描述
            strategies: JSON 格式的策略列表
            
        Returns:
            JSON 格式的选择结果
        """
        logger.info(f"🎯 DecisionAgent 策略选择: {situation}")
        
        try:
            strategy_list = json.loads(strategies)
            result = self.decision_agent.select_strategy(situation, strategy_list)
            
            if result.success:
                return json.dumps({
                    "selected_strategy": result.decision,
                    "reasoning": result.reasoning,
                    "confidence": result.confidence
                }, ensure_ascii=False, indent=2)
            else:
                return json.dumps({"error": result.error}, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    # ========== 状态管理工具 ==========
    
    def get_shared_state_info(self) -> str:
        """获取共享状态信息"""
        try:
            snapshot = self.shared_state.snapshot()
            return json.dumps(snapshot, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    
    def get_step_history(self) -> str:
        """获取步骤执行历史"""
        return json.dumps(self._step_history, ensure_ascii=False, indent=2)
    
    def check_app_installed(self, app_name: str) -> str:
        """检查应用是否安装"""
        from phone_agent.config.apps import get_package_name
        import subprocess
        
        try:
            package_name = get_package_name(app_name)
            if not package_name:
                return f"未知应用: {app_name}"
            
            device_arg = f"-s {self.phone_agent.agent_config.device_id}" if self.phone_agent.agent_config.device_id else ""
            cmd = f"adb {device_arg} shell pm list packages {package_name}"
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            installed = package_name in result.stdout
            return "已安装" if installed else "未安装"
            
        except Exception as e:
            return f"检查失败: {str(e)}"
