"""
信息提取 Agent
专门负责从屏幕截图中提取结构化信息。
"""
import json
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

from phone_agent.model import ModelClient, ModelConfig
from phone_agent.adb import get_screenshot, get_current_app
from phone_agent.logging_config import get_logger
from phone_agent.multi_agent.shared_state import SharedState

logger = get_logger("info_agent")


@dataclass
class ExtractionResult:
    """信息提取结果"""
    success: bool
    data: Dict[str, Any]
    raw_response: str
    error: Optional[str] = None


class InfoAgent:
    """
    信息提取 Agent
    
    专门负责从屏幕截图中提取结构化信息，不执行任何操作。
    使用视觉语言模型分析屏幕内容，提取用户请求的信息。
    """
    
    def __init__(
        self,
        model_config: ModelConfig,
        device_id: Optional[str] = None,
        shared_state: Optional[SharedState] = None
    ):
        self.model_client = ModelClient(model_config)
        self.device_id = device_id
        self.shared_state = shared_state
        
        logger.info(f"InfoAgent 初始化完成 - 模型: {model_config.model_name}")
    
    def extract(
        self,
        query: str,
        screenshot_base64: Optional[str] = None,
        current_app: Optional[str] = None
    ) -> ExtractionResult:
        """
        从屏幕提取信息
        
        Args:
            query: 要提取的信息描述
            screenshot_base64: 屏幕截图（base64），如果为 None 则自动获取
            current_app: 当前应用名称，如果为 None 则自动获取
            
        Returns:
            ExtractionResult: 提取结果
        """
        logger.info(f"开始提取信息: {query}")
        
        try:
            # 获取屏幕截图
            if screenshot_base64 is None:
                screenshot = get_screenshot(self.device_id)
                screenshot_base64 = screenshot.base64_data
            
            # 获取当前应用
            if current_app is None:
                current_app = get_current_app(self.device_id)
            
            # 构建提示
            system_prompt = """你是一个专业的信息提取专家。
你的任务是从屏幕截图中提取用户请求的信息，并以 JSON 格式返回。

要求：
1. 仔细分析屏幕内容
2. 提取准确的信息
3. 返回结构化的 JSON 数据
4. 如果无法提取，返回 {"error": "原因"}
5. 只返回 JSON，不要有其他文字"""
            
            user_prompt = f"""当前应用: {current_app}

请从屏幕中提取以下信息: {query}

返回 JSON 格式的结果。"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}"
                            }
                        }
                    ]
                }
            ]
            
            # 请求模型
            response = self.model_client.request(messages)
            raw_response = response.action
            
            # 解析 JSON
            extracted_data = self._parse_json_response(raw_response)
            
            # 检查是否有错误
            if "error" in extracted_data:
                logger.warning(f"提取失败: {extracted_data['error']}")
                result = ExtractionResult(
                    success=False,
                    data=extracted_data,
                    raw_response=raw_response,
                    error=extracted_data["error"]
                )
            else:
                logger.info(f"提取成功: {len(extracted_data)} 个字段")
                result = ExtractionResult(
                    success=True,
                    data=extracted_data,
                    raw_response=raw_response
                )
            
            # 更新共享状态
            if self.shared_state:
                self.shared_state.set("last_extraction", {
                    "query": query,
                    "result": extracted_data,
                    "current_app": current_app
                })
            
            return result
            
        except Exception as e:
            logger.error(f"信息提取异常: {e}", exc_info=True)
            return ExtractionResult(
                success=False,
                data={"error": str(e)},
                raw_response="",
                error=str(e)
            )
    
    def extract_list(
        self,
        item_description: str,
        screenshot_base64: Optional[str] = None
    ) -> ExtractionResult:
        """
        提取列表信息
        
        Args:
            item_description: 列表项描述，例如 "商品"、"联系人"
            screenshot_base64: 屏幕截图
            
        Returns:
            ExtractionResult: 提取结果，data 中包含 "items" 列表
        """
        query = f"提取屏幕上所有的{item_description}，返回列表格式"
        return self.extract(query, screenshot_base64)
    
    def extract_fields(
        self,
        fields: list[str],
        screenshot_base64: Optional[str] = None
    ) -> ExtractionResult:
        """
        提取指定字段
        
        Args:
            fields: 要提取的字段列表，例如 ["店名", "评分", "价格"]
            screenshot_base64: 屏幕截图
            
        Returns:
            ExtractionResult: 提取结果
        """
        fields_str = "、".join(fields)
        query = f"提取以下字段: {fields_str}"
        return self.extract(query, screenshot_base64)
    
    def verify_screen_content(
        self,
        expected_content: str,
        screenshot_base64: Optional[str] = None
    ) -> bool:
        """
        验证屏幕是否包含预期内容
        
        Args:
            expected_content: 预期内容描述
            screenshot_base64: 屏幕截图
            
        Returns:
            bool: 是否包含预期内容
        """
        query = f"屏幕上是否包含: {expected_content}？返回 {{\"contains\": true/false}}"
        result = self.extract(query, screenshot_base64)
        
        if result.success and "contains" in result.data:
            return result.data["contains"]
        
        return False
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析 JSON 响应
        
        Args:
            response: 模型响应
            
        Returns:
            解析后的字典
        """
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            # 如果都失败，返回原始响应
            return {"result": response}
    
    def get_last_extraction(self) -> Optional[Dict[str, Any]]:
        """获取最后一次提取结果"""
        if self.shared_state:
            return self.shared_state.get("last_extraction")
        return None
