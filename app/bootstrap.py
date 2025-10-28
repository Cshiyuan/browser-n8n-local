"""FastAPI application bootstrap and server configuration"""

import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.routes import router
from app.middleware import add_json_serialization, setup_cors
from task.constants import logger
from task.executor import cleanup_all_tasks
from task.storage import get_task_storage

# Initialize task storage
task_storage = get_task_storage()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    logger.info("Browser Use Bridge API starting up...")
    yield
    # Shutdown
    logger.info("Browser Use Bridge API shutting down...")
    await cleanup_all_tasks(task_storage)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(title="Browser Use Bridge API", lifespan=lifespan)

    # Add middleware
    app.middleware("http")(add_json_serialization)
    setup_cors(app)

    # Include router
    app.include_router(router)

    return app


def setup_uvicorn_logging():
    """Configure uvicorn to suppress some of the noisy shutdown logs"""
    # Reduce noise from uvicorn during shutdown
    uvicorn_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger.setLevel(logging.WARNING)

    # Also suppress asyncio warnings during shutdown
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(logging.WARNING)


async def run_server():
    """Run the server with proper asyncio signal handling"""
    port = int(os.environ.get("PORT", 8000))

    # Create FastAPI app
    app = create_app()

    # Configure uvicorn server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False,  # Reduce noise
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    # Set up signal handlers for graceful shutdown
    def signal_handler():
        logger.info("\nReceived shutdown signal, initiating graceful shutdown...")
        server.should_exit = True

    # Register signal handlers (Unix-like systems only)
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)  # type: ignore[arg-type]

    # Start the server
    logger.info(f"Starting Browser Use Bridge API on port {port}")
    logger.info("Press Ctrl+C for graceful shutdown")

    try:
        await server.serve()
    except asyncio.CancelledError:
        logger.info("Server shutdown completed")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
