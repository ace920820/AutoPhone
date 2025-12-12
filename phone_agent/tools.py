import os
from typing import Optional
from agno.agent import Agent
from agno.tools import Toolkit
from phone_agent.agent import PhoneAgent, AgentConfig
from phone_agent.model import ModelConfig

class AutoGLMTools(Toolkit):
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model_name: str = "autoglm-phone-9b",
        device_id: Optional[str] = None
    ):
        super().__init__(name="autoglm_tools")
        
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
        
        # 注册工具
        self.register(self.run_phone_task)

    def run_phone_task(self, task_description: str) -> str:
        """
        使用 AutoGLM Phone Agent 在手机上执行指定的任务。
        
        当需要操作手机应用、查找信息或执行具体操作时使用此工具。
        
        Args:
            task_description: 任务的自然语言描述，例如 "打开微信发送消息给张三" 或 "在小红书搜索美食攻略"
            
        Returns:
            str: 任务执行结果的描述
        """
        print(f"\n[AutoGLM] 开始执行子任务: {task_description}")
        try:
            # 重置 agent 状态以开始新任务
            self.phone_agent.reset()
            result = self.phone_agent.run(task_description)
            print(f"[AutoGLM] 任务完成: {result}\n")
            return result
        except Exception as e:
            error_msg = f"任务执行失败: {str(e)}"
            print(f"[AutoGLM] {error_msg}\n")
            return error_msg
