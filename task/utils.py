"""Utility functions for task management"""

import os

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
