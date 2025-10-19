"""Agent creation and configuration"""

from typing import Optional

from browser_use import Browser


def create_agent_config(
    instruction: str, llm, sensitive_data: dict, browser: Optional[Browser] = None
):
    """Create agent configuration dictionary"""
    agent_kwargs = {
        "task": instruction,
        "llm": llm,
        "sensitive_data": sensitive_data,
    }

    if browser:
        agent_kwargs["browser"] = browser

    return agent_kwargs
