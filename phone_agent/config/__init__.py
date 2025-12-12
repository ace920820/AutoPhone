"""Phone Agent 的配置模块。"""

from phone_agent.config.apps import APP_PACKAGES
from phone_agent.config.i18n import get_message, get_messages
from phone_agent.config.prompts_en import SYSTEM_PROMPT as SYSTEM_PROMPT_EN
from phone_agent.config.prompts_zh import SYSTEM_PROMPT as SYSTEM_PROMPT_ZH


def get_system_prompt(lang: str = "cn") -> str:
    """
    根据语言获取系统提示词。

    Args:
        lang: 语言代码，'cn' 表示中文，'en' 表示英文。

    Returns:
        系统提示词字符串。
    """
    if lang == "en":
        return SYSTEM_PROMPT_EN
    return SYSTEM_PROMPT_ZH


# 默认使用中文以保持向后兼容
SYSTEM_PROMPT = SYSTEM_PROMPT_ZH

__all__ = [
    "APP_PACKAGES",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_ZH",
    "SYSTEM_PROMPT_EN",
    "get_system_prompt",
    "get_messages",
    "get_message",
]
