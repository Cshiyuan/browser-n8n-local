"""Agent creation and configuration"""

from typing import Literal, Optional

from browser_use import BrowserSession


def create_agent_config(
    instruction: str,
    llm,
    sensitive_data: dict,
    browserSession: Optional[BrowserSession] = None,
    use_vision: Optional[bool | Literal['auto']] = None,
    output_model: Optional[type] = None,
):
    """Create agent configuration dictionary

    Args:
        instruction: Task instruction for the agent
        llm: Language model instance
        sensitive_data: Dictionary of sensitive data (passwords, API keys, etc.)
        browserSession: Optional BrowserSession instance
        use_vision: Whether to use vision capabilities ('auto', True, or False)
        output_model: Optional Pydantic model class for structured output

    Returns:
        Dictionary of agent configuration parameters
    """
    agent_kwargs = {
        "task": instruction,
        "llm": llm,
        "sensitive_data": sensitive_data,
    }

    if browserSession is not None:
        agent_kwargs["browser_session"] = browserSession

    if use_vision is not None:
        agent_kwargs["use_vision"] = use_vision

    if output_model is not None:
        agent_kwargs["output_model_schema"] = output_model

    return agent_kwargs
