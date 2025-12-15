"""
AutoGLM 工具模块
提供给 Agno Agent 使用的手机操作工具。
"""
import os
import json
from typing import Optional, Callable, Dict, Any
from agno.agent import Agent
from agno.tools import Toolkit
from phone_agent.agent import PhoneAgent, AgentConfig, StepResult
from phone_agent.model import ModelConfig
from phone_agent.logging_config import get_logger
from phone_agent.multi_agent.decision_agent import DecisionAgent

# 获取日志器
logger = get_logger("tools")

class AutoGLMTools(Toolkit):
    """
    AutoGLM 手机操作工具集。
    
    作为 Agno Toolkit 注册到 Orchestrator Agent，
    提供 run_phone_task 方法用于执行手机上的具体任务。
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model_name: str = "autoglm-phone-9b",
        device_id: Optional[str] = None,
        decision_model: Optional[str] = None  # DecisionAgent 使用的模型
    ):
        super().__init__(name="autoglm_tools")
        
        logger.info(f"AutoGLMTools 初始化 - 模型: {model_name}, 设备: {device_id or '默认'}")
        
        # 初始化 PhoneAgent
        model_config = ModelConfig(
            base_url=base_url,
            model_name=model_name
        )
        agent_config = AgentConfig(
            device_id=device_id,
            max_steps=50,  # 限制子任务步数
            verbose=True
        )
        self.phone_agent = PhoneAgent(model_config, agent_config)
        self._step_history: list[Dict[str, Any]] = []
        
        # 初始化 DecisionAgent（用于任务预分解）
        self._init_decision_agent(decision_model)
        
        # 注册所有工具
        self.register(self.run_phone_task)
        self.register(self.get_phone_status)
        self.register(self.extract_screen_info)
        self.register(self.check_app_installed)
        self.register(self.pause_phone_task)
        self.register(self.resume_phone_task)
        self.register(self.get_step_history)
        self.register(self.decompose_task)  # 新增：任务分解工具
        
        logger.info("所有工具已注册: run_phone_task, get_phone_status, extract_screen_info, check_app_installed, pause_phone_task, resume_phone_task, get_step_history, decompose_task")
    
    def _init_decision_agent(self, decision_model: Optional[str] = None):
        """
        初始化 DecisionAgent 用于任务预分解
        
        Args:
            decision_model: 指定使用的模型，默认使用环境变量 LLM_MODEL 或 qwen-plus
        """
        try:
            # 获取 DashScope API 配置
            api_key = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
            base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            model_name = decision_model or os.getenv("LLM_MODEL", "qwen-plus")
            
            if not api_key or api_key == "EMPTY":
                logger.warning("未配置 LLM_API_KEY，DecisionAgent 将不可用")
                self.decision_agent = None
                return
            
            decision_config = ModelConfig(
                base_url=base_url,
                model_name=model_name,
                api_key=api_key
            )
            self.decision_agent = DecisionAgent(decision_config)
            logger.info(f"DecisionAgent 已初始化 - 模型: {model_name}")
            
        except Exception as e:
            logger.error(f"DecisionAgent 初始化失败: {e}")
            self.decision_agent = None

    def run_phone_task(self, task_description: str) -> str:
        """
        使用 AutoGLM Phone Agent 在手机上执行指定的任务。
        
        当需要操作手机应用、查找信息或执行具体操作时使用此工具。
        支持流式反馈，每个步骤的信息会被记录到历史中。
        
        Args:
            task_description: 任务的自然语言描述，例如 "打开微信发送消息给张三" 或 "在小红书搜索美食攻略"
            
        Returns:
            str: 任务执行结果的描述
        """
        logger.info(f"开始执行子任务: {task_description}")
        
        # 检查是否有分解的步骤列表，显示进度
        step_progress = ""
        if hasattr(self, '_decomposed_steps') and self._decomposed_steps:
            # 尝试匹配当前任务是第几步
            for i, step in enumerate(self._decomposed_steps):
                if step in task_description or task_description in step:
                    step_progress = f" [步骤 {i+1}/{len(self._decomposed_steps)}]"
                    break
            else:
                # 如果没匹配到，使用计数器
                if hasattr(self, '_current_step_index'):
                    self._current_step_index += 1
                    if self._current_step_index <= len(self._decomposed_steps):
                        step_progress = f" [步骤 {self._current_step_index}/{len(self._decomposed_steps)}]"
        
        print(f"\n[AutoGLM]{step_progress} 执行: {task_description}")
        
        # 清空步骤历史
        self._step_history = []
        
        # 设置步骤回调用于流式反馈
        def step_callback(step_result: StepResult):
            step_info = {
                "step": self.phone_agent.step_count,
                "success": step_result.success,
                "finished": step_result.finished,
                "action": step_result.action,
                "thinking": step_result.thinking,
                "message": step_result.message,
                "current_app": self.phone_agent._current_app,
            }
            self._step_history.append(step_info)
            
            # 打印进度信息
            action_name = step_result.action.get("action", "unknown") if step_result.action else "unknown"
            status = "✅" if step_result.success else "❌"
            print(f"  {status} 步骤 {self.phone_agent.step_count}: {action_name}")
            logger.debug(f"步骤 {self.phone_agent.step_count} 完成: {action_name}, 成功={step_result.success}")
        
        try:
            # 重置 agent 状态以开始新任务
            self.phone_agent.reset()
            self.phone_agent.set_step_callback(step_callback)
            logger.debug("PhoneAgent 已重置，步骤回调已设置")
            
            result = self.phone_agent.run(task_description)
            
            logger.info(f"✅ 子任务完成: {result}")
            print(f"[AutoGLM] 任务完成: {result}\n")
            return result
            
        except Exception as e:
            error_msg = f"任务执行失败: {str(e)}"
            logger.error(f"❌ 子任务失败: {e}", exc_info=True)
            print(f"[AutoGLM] {error_msg}\n")
            return error_msg
    
    def get_phone_status(self) -> str:
        """
        获取当前手机和 PhoneAgent 的状态信息。
        
        返回包含以下信息的 JSON 字符串：
        - current_app: 当前正在运行的应用
        - step_count: 已执行的步骤数
        - is_busy: 是否正在执行任务
        - is_paused: 是否已暂停
        - last_error: 最后一次错误信息（如果有）
        - device_id: 设备 ID
        
        Returns:
            str: JSON 格式的状态信息
        """
        from phone_agent.adb import get_current_app
        
        try:
            state = self.phone_agent.get_state()
            
            # 获取实时的当前应用
            try:
                current_app = get_current_app(self.phone_agent.agent_config.device_id)
                state["current_app"] = current_app
            except Exception as e:
                logger.warning(f"获取当前应用失败: {e}")
                state["current_app"] = state.get("current_app", "未知")
            
            logger.debug(f"获取手机状态: {state}")
            return json.dumps(state, ensure_ascii=False, indent=2)
            
        except Exception as e:
            error_msg = f"获取状态失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg}, ensure_ascii=False)
    
    def extract_screen_info(self, query: str) -> str:
        """
        从当前屏幕提取信息，不执行任何操作。
        
        使用视觉语言模型分析当前屏幕截图，提取指定的信息。
        这个工具只读取信息，不会改变手机状态。
        
        Args:
            query: 要提取的信息描述，例如 "提取店名和评分" 或 "列出屏幕上的所有商品"
            
        Returns:
            str: 提取的信息（JSON 格式）
        """
        from phone_agent.adb import get_screenshot, get_current_app
        
        logger.info(f"📸 提取屏幕信息: {query}")
        
        try:
            screenshot = get_screenshot(self.phone_agent.agent_config.device_id)
            current_app = get_current_app(self.phone_agent.agent_config.device_id)
            
            # 构建提取信息的提示
            messages = [
                {
                    "role": "system",
                    "content": "你是一个信息提取专家。从屏幕截图中提取用户请求的信息，以 JSON 格式返回。如果无法提取，返回 {\"error\": \"原因\"}。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"当前应用: {current_app}\n\n请从屏幕中提取以下信息: {query}\n\n返回 JSON 格式的结果。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot.base64_data}"
                            }
                        }
                    ]
                }
            ]
            
            # 使用 PhoneAgent 的模型客户端
            response = self.phone_agent.model_client.request(messages)
            
            # 尝试解析为 JSON
            try:
                # 提取 JSON 部分
                import re
                json_match = re.search(r'\{.*\}', response.action, re.DOTALL)
                if json_match:
                    extracted_info = json_match.group()
                else:
                    extracted_info = json.dumps({"result": response.action}, ensure_ascii=False)
            except:
                extracted_info = json.dumps({"result": response.action}, ensure_ascii=False)
            
            logger.info(f"✅ 信息提取完成")
            return extracted_info
            
        except Exception as e:
            error_msg = f"信息提取失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg}, ensure_ascii=False)
    
    def check_app_installed(self, app_name: str) -> str:
        """
        检查指定的应用是否已安装在手机上。
        
        Args:
            app_name: 应用名称，例如 "小红书"、"微信"、"淘宝"
            
        Returns:
            str: "已安装" 或 "未安装" 或错误信息
        """
        from phone_agent.config.apps import get_package_name
        import subprocess
        
        logger.info(f"🔍 检查应用是否安装: {app_name}")
        
        try:
            package_name = get_package_name(app_name)
            if not package_name:
                return f"未知应用: {app_name}（不在支持列表中）"
            
            # 使用 adb 检查应用是否安装
            device_arg = f"-s {self.phone_agent.agent_config.device_id}" if self.phone_agent.agent_config.device_id else ""
            cmd = f"adb {device_arg} shell pm list packages {package_name}"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            installed = package_name in result.stdout
            status = "已安装" if installed else "未安装"
            
            logger.info(f"✅ {app_name} ({package_name}): {status}")
            return status
            
        except Exception as e:
            error_msg = f"检查失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def pause_phone_task(self) -> str:
        """
        暂停当前正在执行的手机任务。
        
        任务会在当前步骤完成后暂停，可以使用 resume_phone_task 恢复。
        
        Returns:
            str: 操作结果
        """
        logger.info("⏸️  暂停任务")
        try:
            self.phone_agent.pause()
            return "任务已暂停"
        except Exception as e:
            error_msg = f"暂停失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def resume_phone_task(self) -> str:
        """
        恢复已暂停的手机任务。
        
        Returns:
            str: 操作结果
        """
        logger.info("▶️  恢复任务")
        try:
            self.phone_agent.resume()
            return "任务已恢复"
        except Exception as e:
            error_msg = f"恢复失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
    
    def get_step_history(self) -> str:
        """
        获取最近一次任务执行的步骤历史。
        
        返回每个步骤的详细信息，包括操作、思考过程、执行结果等。
        
        Returns:
            str: JSON 格式的步骤历史
        """
        logger.debug(f"获取步骤历史，共 {len(self._step_history)} 步")
        return json.dumps(self._step_history, ensure_ascii=False, indent=2)
    
    def decompose_task(self, task: str) -> str:
        """
        将复杂任务分解为具体可执行的子步骤。
        
        对于涉及多个应用、多个筛选条件或多个操作的复杂任务，
        使用此工具先进行分解，然后逐步执行每个子步骤。
        
        分解后的步骤会保留所有关键条件（如价格限制、评分要求等），
        确保执行时不会遗漏重要约束。
        
        Args:
            task: 复杂任务描述，例如 "在大众点评找一家静安寺附近评分4.5以上、
                  人均150以下的日料餐厅，然后用高德地图查路线"
            
        Returns:
            str: JSON 格式的步骤列表，例如 {"steps": ["步骤1", "步骤2", ...]}
        """
        logger.info(f"[DecisionAgent] 开始分解任务: {task[:50]}...")
        
        if not self.decision_agent:
            # DecisionAgent 不可用时，返回原任务作为单一步骤
            logger.warning("DecisionAgent 不可用，返回原任务")
            return json.dumps({"steps": [task], "note": "DecisionAgent 不可用，未进行分解"}, ensure_ascii=False)
        
        try:
            # 调用 DecisionAgent 分解任务
            steps = self.decision_agent.decompose_task(task)
            
            logger.info(f"[DecisionAgent] 任务分解完成，共 {len(steps)} 个步骤")
            
            # 打印分解结果到控制台，让用户看到计划
            print("\n" + "=" * 60)
            print("[DecisionAgent] 任务分解结果")
            print("=" * 60)
            print(f"原始任务: {task[:80]}{'...' if len(task) > 80 else ''}")
            print("-" * 60)
            print(f"分解为 {len(steps)} 个子步骤:")
            for i, step in enumerate(steps, 1):
                print(f"  [{i:2d}] {step}")
            print("=" * 60 + "\n")
            
            # 保存步骤列表供后续追踪
            self._decomposed_steps = steps
            self._current_step_index = 0
            
            return json.dumps({"steps": steps}, ensure_ascii=False, indent=2)
            
        except Exception as e:
            error_msg = f"任务分解失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 失败时返回原任务
            return json.dumps({"steps": [task], "error": error_msg}, ensure_ascii=False)
