"""Constants and enums for task management"""

import logging
import os
from enum import Enum


# Agent configuration constants
MAX_HISTORY_ITEMS = int(os.environ.get("MAX_HISTORY_ITEMS", "10"))

# LLM Pool configuration
SUPPORTED_POOLED_PROVIDERS = ["openai", "anthropic", "google"]


# Define task status enum
class TaskStatus(str, Enum):
    CREATED = "created"  # Task is initialized but not yet started
    RUNNING = "running"  # Task is currently executing
    FINISHED = "finished"  # Task has completed successfully
    STOPPED = "stopped"  # Task was manually stopped
    PAUSED = "paused"  # Task execution is temporarily paused
    FAILED = "failed"  # Task encountered an error and could not complete
    STOPPING = "stopping"  # Task is in the process of stopping (transitional state)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("browser-use-bridge")
