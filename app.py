"""Browser Use Bridge API - Main entry point

This file has been refactored. The application logic is now organized in:
- app/: FastAPI application, routes, models, middleware
- task/: Task execution, browser automation, LLM configuration
- task_storage/: Task storage abstraction layer
"""

import asyncio
import sys

from dotenv import load_dotenv

from app.bootstrap import run_server, setup_uvicorn_logging
from task.constants import logger

# Load environment variables from .env file
load_dotenv()


# Run server if executed directly
if __name__ == "__main__":
    setup_uvicorn_logging()

    try:
        # Use asyncio.run with proper exception handling
        asyncio.run(run_server())
    except KeyboardInterrupt:
        # This should rarely be reached due to signal handling above
        pass  # Silent shutdown - the signal handler already logged the message
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

    logger.info("Browser Use Bridge API stopped")
    sys.exit(0)
