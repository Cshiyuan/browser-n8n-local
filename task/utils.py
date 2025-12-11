"""Utility functions for task management"""

import os
import asyncio
from datetime import datetime, UTC
from typing import Optional, Dict, Any

from task.constants import logger


def get_sensitive_data():
    """Extract sensitive data from environment variables"""
    sensitive_data = {}
    for key, value in os.environ.items():
        if key.startswith("X_") and value:
            sensitive_data[key] = value
    return sensitive_data


def prepare_task_environment(task_id: str, _user_id: str):
    """Placeholder for task-specific setup logic"""
    logger.info(f"Initializing environment for task {task_id}")


async def trigger_webhook(
    webhook_url: str,
    task_id: str,
    status: str,
    event_type: str,
    result: Optional[Any] = None,
    error: Optional[str] = None,
    max_retries: int = 3
) -> bool:
    """
    Trigger webhook callback to notify external system (e.g., n8n)
    
    Args:
        webhook_url: The URL to send the webhook POST request to
        task_id: The task identifier
        status: Task status (completed, failed, etc.)
        event_type: Event type (task.completed, task.failed)
        result: Task execution result (for successful completion)
        error: Error message (for failures)
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        bool: True if webhook was successfully triggered, False otherwise
    """
    if not webhook_url:
        logger.debug(f"No webhook URL configured for task {task_id}, skipping webhook")
        return False
    
    # Construct webhook payload
    payload: Dict[str, Any] = {
        "event": event_type,
        "task_id": task_id,
        "status": status,
        "timestamp": datetime.now(UTC).isoformat() + "Z",
    }
    
    # Add result or error based on status
    if status == "completed" and result is not None:
        payload["result"] = {
            "final_result": str(result),
        }
    elif status == "failed" and error:
        payload["error"] = error
    
    # Import httpx only when needed
    try:
        import httpx
    except ImportError:
        logger.error("httpx is not installed. Cannot send webhook. Please install httpx: pip install httpx")
        return False
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Browser-Use-Webhook/1.0"
                    }
                )
                
                if 200 <= response.status_code < 300:
                    logger.info(f"✅ Webhook triggered successfully for task {task_id} (event: {event_type})")
                    return True
                else:
                    logger.warning(f"⚠️ Webhook returned status {response.status_code} for task {task_id}")
        
        except httpx.TimeoutException:
            logger.warning(
                f"⏱️ Webhook timeout for task {task_id}, "
                f"attempt {attempt + 1}/{max_retries}"
            )
        except Exception as e:
            logger.error(
                f"❌ Webhook error for task {task_id}, "
                f"attempt {attempt + 1}/{max_retries}: {e}"
            )
        
        # Exponential backoff before retry (1s, 2s, 4s)
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    
    logger.error(f"❌ Webhook failed after {max_retries} attempts for task {task_id}")
    return False
