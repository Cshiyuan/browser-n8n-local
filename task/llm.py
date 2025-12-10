"""LLM provider configuration with API Key pool support"""

import os

from browser_use.llm import (
    ChatAnthropic,
    ChatOpenAI,
    ChatGoogle,
    ChatOllama,
    ChatAzureOpenAI,
    ChatAWSBedrock,
)

from task.llm_pool import get_pooled_api_key


def get_llm(ai_provider: str):
    """Get LLM based on provider with API Key rotation support

    Supports multiple API Keys for the same provider using round-robin rotation.
    Configure using environment variables:
    - New format (multiple keys): PROVIDER_API_KEYS=key1,key2,key3
    - Old format (single key): PROVIDER_API_KEY=key (backward compatible)

    Args:
        ai_provider: AI provider name (openai, anthropic, google, etc.)

    Returns:
        LLM instance configured with rotated API Key
    """
    if ai_provider == "anthropic":
        api_key = get_pooled_api_key("anthropic")
        return ChatAnthropic(
            model=os.environ.get("ANTHROPIC_MODEL_ID", "claude-3-opus-20240229"),
            api_key=api_key
        )
    # elif ai_provider == "mistral":
    #     return LLMProvider.MISTRAL(
    #         model=os.environ.get("MISTRAL_MODEL_ID", "mistral-large-latest")
    #     )
    elif ai_provider == "google":
        api_key = get_pooled_api_key("google")
        return ChatGoogle(
            model=os.environ.get("GOOGLE_MODEL_ID", "gemini-1.5-pro"),
            api_key=api_key
        )
    elif ai_provider == "ollama":
        # Ollama 不需要 API Key,保持不变
        return ChatOllama(model=os.environ.get("OLLAMA_MODEL_ID", "llama3"))
    elif ai_provider == "azure":
        # Azure 配置较复杂,暂时保持原样,未来可扩展多 Key 支持
        return ChatAzureOpenAI(
            model=os.environ.get("AZURE_MODEL_ID", "gpt-4o"),
            azure_deployment=os.environ.get("AZURE_DEPLOYMENT_NAME"),
            api_version=os.environ.get("AZURE_API_VERSION", "2023-05-15"),
            azure_endpoint=os.environ.get("AZURE_ENDPOINT"),
        )
    elif ai_provider == "bedrock":
        # Bedrock 使用 AWS 凭证,暂时保持原样
        return ChatAWSBedrock(
            model=os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"
            )
        )
    else:  # default to OpenAI
        api_key = get_pooled_api_key("openai")
        base_url = os.environ.get("OPENAI_BASE_URL")
        model = os.environ.get("OPENAI_MODEL_ID", "gpt-4o")

        if base_url:
            return ChatOpenAI(model=model, base_url=base_url, api_key=api_key)
        else:
            return ChatOpenAI(model=model, api_key=api_key)
