"""Utility functions for task management"""

import os

from task.constants import MEDIA_DIR, logger


def get_sensitive_data():
    """Extract sensitive data from environment variables"""
    sensitive_data = {}
    for key, value in os.environ.items():
        if key.startswith("X_") and value:
            sensitive_data[key] = value
    return sensitive_data


def prepare_task_environment(task_id: str, _user_id: str):
    """Prepare task environment and media directory"""
    # Create task media directory up front
    task_media_dir = MEDIA_DIR / task_id
    task_media_dir.mkdir(exist_ok=True, parents=True)
    logger.info(f"Created media directory for task {task_id}: {task_media_dir}")
    return task_media_dir
